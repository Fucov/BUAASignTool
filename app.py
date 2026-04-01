"""
北航课程助手 (BUAA Sign Tool)
支持校内直连与校外 WebVPN 两种网络模式。
基于 pywebview + 原生前端的单体桌面应用。

支持双端口兜底机制：优先使用 8347 端口，失败时自动回退到 8346 端口。
"""

import os
import re
import json
import time
import datetime
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import requests
import urllib3
import webview

try:
    from Crypto.Cipher import AES
except ImportError:
    pass  # 如需 WebVPN 功能，请安装 pycryptodome

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["http_proxy"] = os.environ["https_proxy"] = ""


# ==========================================
# 常量定义
# ==========================================

# API 端口配置 - 8347 为新端口，8346 为旧端口兜底
PRIMARY_PORT = "8347"
FALLBACK_PORT = "8346"

# 签到端口配置
PRIMARY_SIGN_PORT = "8081"
FALLBACK_SIGN_PORT = "8081"  # 签到端口保持不变

# API 路径配置
API_PATHS = {
    "login": "/app/user/login.action",
    "course_schedule": "/app/course/get_stu_course_sched.action",
    "sign": "/app/course/stu_scan_sign.action",
    # 新增：8347 专用端点
    "semester_list": "/app/course/get_base_school_year.action",
    "course_list": "/app/choosecourse/get_myall_course.action",
    "course_detail": "/app/my/get_my_course_sign_detail.action",
}


def wengine_encrypt(text):
    """AES-CFB128 加密，用于 WebVPN 模式下的 hostname 转换"""
    key = iv = b"wrdvpnisthebest!"
    cipher = AES.new(key, AES.MODE_CFB, iv, segment_size=128)
    return key.hex() + cipher.encrypt(text.encode("utf-8")).hex()


def merge_courses(courses):
    """合并同一时段、同一课程下不同教师的重复记录"""
    if not courses:
        return []
    merged = OrderedDict()
    for c in courses:
        key = (
            c.get("courseNum", ""),
            c.get("classBeginTime", ""),
            c.get("classroomName", ""),
        )
        if key not in merged:
            mc = dict(c)
            mc["teachers"] = [c.get("teacherName", "未知")]
            mc["courseSchedIds"] = [c.get("id", "")]
            merged[key] = mc
        else:
            existing = merged[key]
            t = c.get("teacherName", "未知")
            if t not in existing["teachers"]:
                existing["teachers"].append(t)
            existing["courseSchedIds"].append(c.get("id", ""))
    return list(merged.values())


def parse_buaa_curl(curl_text):
    """
    从 cURL 命令中提取 WebVPN 所需的 Cookie。
    兼容 bash/zsh (反斜杠续行) 和 Windows Cmd (^ 续行) 两种格式。
    """
    # 清理跨平台续行符
    clean_text = curl_text.replace("^", "")
    clean_text = re.sub(r"\\\s*\n\s*", " ", clean_text)
    clean_text = re.sub(r"\n\s*", " ", clean_text)

    # 匹配 Cookie 头：-H 'Cookie: ...' 或 -b '...'
    match = re.search(r'Cookie:\s*([^\'"]+)', clean_text, re.IGNORECASE)
    if not match:
        # 尝试 -b 格式
        match = re.search(r'-b\s*[\'"]([^\'"]+)[\'"]', clean_text, re.IGNORECASE)

    if match:
        cookie_str = match.group(1)
        # 筛选 VPN 相关的 Cookie 字段
        targets = ["wengine_vpn_ticket", "_zte_cid", "route"]
        parts = [p.strip() for p in cookie_str.split(";")]
        filtered = [p for p in parts if any(target in p for target in targets)]

        if filtered:
            return True, "; ".join(filtered)
        return (
            False,
            "解析失败：Cookie 中未找到 VPN 凭证 (_zte_cid_ / wengine_vpn_ticket)",
        )

    return False, "解析失败：cURL 中未找到 Cookie 字段"


# 注意：不要在 js_api 类中持有 window 引用，否则 Windows 下会触发 Python.NET 递归崩溃
_APP_CONTEXT = {}


class Api:
    """前端可调用的后端 API 接口，支持双端口兜底机制"""

    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.use_vpn = False
        self.session = requests.Session()
        self.session.trust_env = False  # 忽略系统代理

        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
            }
        )
        self._week_cache = {}
        self._current_port = PRIMARY_PORT
        self._sign_port = PRIMARY_SIGN_PORT

    def _log(self, msg, msg_type="info"):
        """将日志推送到前端界面"""
        window = _APP_CONTEXT.get("window")
        if window:
            safe_msg = msg.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
            try:
                window.evaluate_js(f"window.app.pushLog('{safe_msg}', '{msg_type}')")
            except Exception:
                pass

    def _get_vpn_url(self, host, port, path):
        """构建 WebVPN 代理 URL"""
        encrypted_host = wengine_encrypt(f"{host}:{port}")
        return f"https://d.buaa.edu.cn/https-{port}/{encrypted_host}{path}"

    def _request(self, method, scheme, host, port, path, use_fallback=True, **kwargs):
        """
        统一的网络请求方法，支持双端口兜底机制。

        Args:
            method: HTTP 方法
            scheme: http 或 https
            host: 目标主机
            port: 目标端口
            path: 请求路径
            use_fallback: 是否启用端口回退
            **kwargs: 其他请求参数

        Returns:
            requests.Response 对象
        """
        ports_to_try = [port]
        if use_fallback and port == PRIMARY_PORT:
            ports_to_try.append(FALLBACK_PORT)

        last_error = None
        for try_port in ports_to_try:
            if self.use_vpn:
                url = self._get_vpn_url(host, try_port, path)
            else:
                url = f"{scheme}://{host}:{try_port}{path}"

            # 修正 Header 中的非 Latin-1 字符，防止请求异常
            for k, v in list(self.session.headers.items()):
                try:
                    str(v).encode("latin-1")
                except UnicodeEncodeError:
                    self.session.headers[k] = (
                        str(v).encode("utf-8").decode("latin-1", "ignore")
                    )

            start_time = time.time()
            try:
                res = self.session.request(method, url, verify=False, **kwargs)
                cost = int((time.time() - start_time) * 1000)
                status = res.status_code

                if status >= 400:
                    self._log(f"请求失败 [{status}]: {path} ({cost}ms)", "warning")
                    last_error = f"HTTP {status}"
                    continue

                # 记录当前工作的端口
                if try_port != self._current_port:
                    self._current_port = try_port
                    # if use_fallback:
                    #     self._log(f"切换到端口 {try_port}", "info")

                return res

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                self._log(f"连接失败 (端口 {try_port}): {last_error}", "warning")
                continue

        # 所有端口都失败
        self._log(f"连接失败: {path} - {last_error}", "error")
        raise requests.exceptions.RequestException(last_error)

    def login_direct(self, student_id):
        """校内直连登录"""
        self.use_vpn = False
        return self._do_login(student_id)

    def login_vpn(self, student_id, curl_text):
        """校外 WebVPN 登录"""
        self._log("正在解析 cURL...")
        success, cookie_data = parse_buaa_curl(curl_text)
        if not success:
            return {"success": False, "error": cookie_data}

        # 移除 Cookie 中的非 ASCII 字符
        clean_cookie = "".join(i for i in cookie_data if ord(i) < 128)
        self.session.headers.update({"Cookie": clean_cookie})
        self.use_vpn = True
        self._log("Cookie 已提取，正在登录...", "success")
        return self._do_login(student_id)

    def _do_login(self, student_id):
        """执行登录请求，优先使用 8347 端口，自动回退到 8346"""
        try:
            res = self._request(
                "GET",
                "https",
                "iclass.buaa.edu.cn",
                PRIMARY_PORT,
                API_PATHS["login"],
                params={
                    "password": "",
                    "phone": student_id,
                    "userLevel": "1",
                    "verificationType": "2",
                    "verificationUrl": "",
                },
                timeout=10,
            )
            data = res.json()
            if data.get("status") != "0" and data.get("STATUS") != "0":
                error_msg = data.get("ERRORMSG", data.get("ERRMSG", "服务器拒绝登录"))
                self._log(f"登录失败: {error_msg}", "error")
                return {"success": False, "error": error_msg}

            result = data.get("result", data)
            self.userId = str(result.get("id", ""))
            self.sessionId = result.get("sessionId", "")
            if not self.userId or not self.sessionId:
                self._log("登录成功但获取用户信息不完整，尝试回退端口...", "warning")
                try:
                    res = self._request(
                        "GET",
                        "https",
                        "iclass.buaa.edu.cn",
                        FALLBACK_PORT,
                        API_PATHS["login"],
                        params={
                            "password": "",
                            "phone": student_id,
                            "userLevel": "1",
                            "verificationType": "2",
                            "verificationUrl": "",
                        },
                        use_fallback=False,
                        timeout=10,
                    )
                    data = res.json()
                    if data.get("status") == "0" or data.get("STATUS") == "0":
                        result = data.get("result", data)
                        self.userId = str(result.get("id", self.userId))
                        self.sessionId = result.get("sessionId", self.sessionId)
                        self._current_port = FALLBACK_PORT
                        self._log(f"回退到端口 {FALLBACK_PORT} 成功", "info")
                except Exception as e:
                    self._log(f"回退登录也失败: {e}", "warning")

            if not self.userId or not self.sessionId:
                return {"success": False, "error": "登录成功但用户信息不完整"}

            self.session.headers.update({"sessionId": self.sessionId})
            self._log(f"登录成功 (UID: {self.userId}, 端口: {self._current_port})", "success")
            return {"success": True, "userId": self.userId}
        except Exception as e:
            self._log(f"登录异常: {str(e)}", "error")
            return {"success": False, "error": str(e)}

    def _fetch_day(self, date_str):
        """获取指定日期的课表数据，优先使用主端口"""
        try:
            res = self._request(
                "GET",
                "https",
                "iclass.buaa.edu.cn",
                PRIMARY_PORT,
                API_PATHS["course_schedule"],
                params={"dateStr": date_str, "id": self.userId},
                timeout=10,
            )
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    def get_week_courses(self, week_number, year, month, day):
        """并发获取一周课表并合并重复课程"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
        except ValueError:
            semester_start = datetime.datetime(2025, 9, 1)

        start_date = semester_start + datetime.timedelta(weeks=int(week_number) - 1)
        week_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

        self._week_cache = {}
        result = {}
        self._log(f"正在加载第 {week_number} 周课表...")

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_map = {
                executor.submit(self._fetch_day, d.strftime("%Y%m%d")): i
                for i, d in enumerate(week_dates)
            }
            for future in future_map:
                idx = future_map[future]
                try:
                    data = future.result()
                    raw = (
                        data.get("result", [])
                        if data and data.get("STATUS") == "0"
                        else []
                    )
                    self._week_cache[idx] = raw
                    merged = merge_courses(raw)
                    result[str(idx)] = {
                        "date": week_dates[idx].strftime("%m-%d"),
                        "weekday": [
                            "周一",
                            "周二",
                            "周三",
                            "周四",
                            "周五",
                            "周六",
                            "周日",
                        ][idx],
                        "isToday": week_dates[idx].date() == datetime.date.today(),
                        "courses": merged,
                    }
                except Exception as e:
                    self._log(f"第 {idx + 1} 天数据获取失败: {str(e)}", "warning")
                    result[str(idx)] = {
                        "date": week_dates[idx].strftime("%m-%d"),
                        "weekday": [
                            "周一",
                            "周二",
                            "周三",
                            "周四",
                            "周五",
                            "周六",
                            "周日",
                        ][idx],
                        "isToday": False,
                        "courses": [],
                    }
        total = len([c for day in result.values() for c in day['courses']])
        self._log(f"课表加载完成，共 {total} 门课程", "success")
        return result

    def sign_course(self, course_ids_json):
        """
        发送签到请求。

        使用 8081 端口，timestamp 额外增加 36000ms 以确保服务器时间同步。
        """
        course_ids = (
            json.loads(course_ids_json)
            if isinstance(course_ids_json, str)
            else course_ids_json
        )
        success = 0
        failed = 0
        for cid in course_ids:
            try:
                timestamp = int(time.time() * 1000) + 36000
                res = self._request(
                    "POST",
                    "http",
                    "iclass.buaa.edu.cn",
                    PRIMARY_SIGN_PORT,
                    API_PATHS["sign"],
                    params={
                        "courseSchedId": cid,
                        "timestamp": timestamp,
                        "id": self.userId,
                    },
                    timeout=10,
                )
                if res.status_code == 200:
                    try:
                        resp_data = res.json()
                        if resp_data.get("STATUS") == "0" or resp_data.get("status") == "0":
                            success += 1
                            self._log(f"课程 {cid[:8]}... 签到成功", "success")
                        else:
                            failed += 1
                            err_msg = resp_data.get("ERRMSG", resp_data.get("ERRORMSG", "未知错误"))
                            self._log(f"课程 {cid[:8]}... 签到失败: {err_msg}", "warning")
                    except json.JSONDecodeError:
                        if "成功" in res.text or "SUCCESS" in res.text:
                            success += 1
                        else:
                            failed += 1
                else:
                    failed += 1
                    self._log(f"课程 {cid[:8]}... HTTP {res.status_code}", "warning")
            except Exception as e:
                failed += 1
                self._log(f"课程 {cid[:8]}... 异常: {str(e)[:50]}", "warning")
            time.sleep(0.15)

        if success > 0:
            self._log(
                f"签到完成: {success}/{len(course_ids)} 成功",
                "success" if failed == 0 else "warning",
            )
        else:
            self._log(
                "签到失败：可能尚未开放签到或已过签到时间",
                "warning",
            )

        return {"success": success, "total": len(course_ids), "failed": failed}

    def batch_sign_week(self, week_number, year, month, day):
        """批量签到本周所有课程"""
        if not self._week_cache:
            self.get_week_courses(week_number, year, month, day)

        all_ids = []
        for day_courses in self._week_cache.values():
            for c in day_courses:
                all_ids.append(c.get("id", ""))

        if not all_ids:
            self._log("本周暂无可签到的课程", "warning")
            return {"success": 0, "total": 0}

        self._log(f"正在批量签到 {len(all_ids)} 门课程...")
        return self.sign_course(all_ids)

    def get_current_week(self, year, month, day):
        """根据学期起始日计算当前周数"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
            return max(
                1, min(18, (datetime.datetime.now() - semester_start).days // 7 + 1)
            )
        except ValueError:
            return 1


if __name__ == "__main__":
    api = Api()
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

    app_window = webview.create_window(
        "BUAA Course Assistant",
        url=os.path.join(web_dir, "index.html"),
        js_api=api,
        width=1400,
        height=850,
        min_size=(1100, 700),
        text_select=False,
    )
    _APP_CONTEXT["window"] = app_window
    webview.start(debug=False)
