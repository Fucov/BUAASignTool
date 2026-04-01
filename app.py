"""
北航课程助手 (BUAA Sign Tool)
支持校内直连与校外 WebVPN 两种网络模式。
基于 pywebview + 原生前端的单体桌面应用。

支持双端口兜底机制和 SSO VPN 登录。
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
from bs4 import BeautifulSoup

try:
    from Crypto.Cipher import AES
except ImportError:
    pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["http_proxy"] = os.environ["https_proxy"] = ""


# ==========================================
# 常量定义
# ==========================================

PRIMARY_PORT = "8347"
FALLBACK_PORT = "8346"
PRIMARY_SIGN_PORT = "8081"

# SSO 登录地址
SSO_LOGIN_URL = "https://d.buaa.edu.cn/https/77726476706e69737468656265737421e3e44ed225256951300d8db9d6562d/login"
SSO_SERVICE_PARAM = "service=https%3A%2F%2Fd.buaa.edu.cn%2Flogin%3Fcas_login%3Dtrue"

# VPN 预加密服务 ID（iClass 服务的固定标识）
VPN_SERVICE_ID = "77726476706e69737468656265737421f9f44d9d342326526b0988e29d51367ba018"

API_PATHS = {
    "login": "/app/user/login.action",
    "course_schedule": "/app/course/get_stu_course_sched.action",
    "sign": "/app/course/stu_scan_sign.action",
}


def wengine_encrypt(text):
    """AES-CFB128 加密，用于 WebVPN hostname 转换"""
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


_APP_CONTEXT = {}


class Api:
    """前端可调用的后端 API 接口"""

    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.userName = None
        self.use_vpn = False
        self.session = requests.Session()
        self.session.trust_env = False

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
        self._course_names = {}

    def _log(self, msg, msg_type="info"):
        """将日志推送到前端界面"""
        window = _APP_CONTEXT.get("window")
        if window:
            safe_msg = msg.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")
            try:
                window.evaluate_js(f"window.app.pushLog('{safe_msg}', '{msg_type}')")
            except Exception:
                pass

    def _get_vpn_url(self, path):
        """构建 VPN 代理 URL（使用预加密的服务 ID）"""
        return f"https://d.buaa.edu.cn/https-{PRIMARY_PORT}/{VPN_SERVICE_ID}{path}"

    def _get_direct_url(self, host, port, path):
        """构建直连 URL"""
        return f"https://{host}:{port}{path}"

    def _is_iclass_url(self, url):
        """检查 URL 是否是 iClass 相关"""
        return "iclass.buaa.edu.cn" in url or "d.buaa.edu.cn/https-834" in url

    def _is_vpn_portal_home(self, url):
        """检查 URL 是否是 VPN 门户首页"""
        try:
            parsed = urllib3.util.parse_url(url)
            return parsed.host == "d.buaa.edu.cn" and "/login" not in parsed.path
        except Exception:
            return False

    def _request(self, method, host, port, path, use_fallback=True, **kwargs):
        """统一的网络请求方法"""
        ports_to_try = [port]
        if use_fallback and port == PRIMARY_PORT:
            ports_to_try.append(FALLBACK_PORT)

        last_error = None
        for try_port in ports_to_try:
            if self.use_vpn:
                url = self._get_vpn_url(path)
            else:
                url = self._get_direct_url(host, try_port, path)

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

                if try_port != self._current_port:
                    self._current_port = try_port
                    if use_fallback:
                        self._log(f"切换到端口 {try_port}", "info")

                return res

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                self._log(f"连接失败 (端口 {try_port}): {last_error}", "warning")
                continue

        self._log(f"连接失败: {path} - {last_error}", "error")
        raise requests.exceptions.RequestException(last_error)

    def _fetch_execution_token(self):
        """从 SSO 登录页面获取 execution 令牌"""
        sso_url = f"{SSO_LOGIN_URL}?{SSO_SERVICE_PARAM}"
        try:
            response = self.session.get(sso_url, timeout=10, verify=False)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            execution_input = soup.find('input', {'name': 'execution'})
            if execution_input and execution_input.get('value'):
                return execution_input['value']

            match = re.search(r'name="execution"\s+value="([^"]+)"', response.text)
            if match:
                return match.group(1)

            raise ValueError("无法从 SSO 页面解析 execution 参数")
        except Exception as e:
            self._log(f"获取 SSO 页面失败: {e}", "error")
            raise

    def _vpn_sso_login(self, username, password):
        """
        通过统一身份认证登录 WebVPN。
        """
        try:
            self._log("正在连接 SSO 认证服务...")
            execution = self._fetch_execution_token()
            self._log("已获取认证令牌，正在登录...", "info")

            sso_url = f"{SSO_LOGIN_URL}?{SSO_SERVICE_PARAM}"
            response = self.session.post(
                sso_url,
                data={
                    "username": username,
                    "password": password,
                    "submit": "登录",
                    "type": "username_password",
                    "execution": execution,
                    "_eventId": "submit",
                },
                headers={"Referer": sso_url},
                allow_redirects=True,
                timeout=15,
                verify=False,
            )

            final_url = response.url
            self._log(f"SSO 响应 URL: {final_url}", "info")

            if self._is_iclass_url(final_url):
                self._log("VPN 登录成功 (直达 iClass)", "success")
                return True

            if self._is_vpn_portal_home(final_url):
                self._log("已进入 VPN 门户，正在建立 iClass 隧道...")
                probe_url = self._get_vpn_url("/")
                probe_response = self.session.get(probe_url, timeout=10, verify=False)
                probe_final_url = probe_response.url

                if self._is_iclass_url(probe_final_url):
                    self._log("VPN 隧道建立成功", "success")
                    return True

                self._log(f"探测响应 URL: {probe_final_url}", "info")
                raise ValueError(f"建立 VPN 隧道失败")

            if response.status_code == 401:
                raise ValueError("账号或密码错误")

            raise ValueError(f"登录失败，最终 URL: {final_url}")

        except ValueError:
            raise
        except Exception as e:
            self._log(f"VPN 登录异常: {e}", "error")
            raise

    def login_direct(self, student_id):
        """校内直连登录"""
        self.use_vpn = False
        return self._do_login(student_id)

    def login_vpn(self, vpn_username, vpn_password, student_id=None):
        """
        校外 WebVPN 登录。
        Args:
            vpn_username: 统一身份认证账号
            vpn_password: 统一身份认证密码
            student_id: 可选，学号（用于替签功能）
        """
        self._log("正在解析 VPN 认证...")
        if not vpn_username or not vpn_password:
            return {"success": False, "error": "请输入账号和密码"}

        try:
            self._vpn_sso_login(vpn_username, vpn_password)
            self.use_vpn = True
            # 使用传入的学号，如果没有则使用账号
            target_id = student_id.strip() if student_id and student_id.strip() else vpn_username
            return self._do_login(target_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _do_login(self, student_id):
        """执行登录请求"""
        try:
            res = self._request(
                "GET",
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
            self.userName = result.get("realName", result.get("name", ""))
            
            if not self.userId or not self.sessionId:
                self._log("登录成功但获取用户信息不完整，尝试回退端口...", "warning")
                try:
                    res = self._request(
                        "GET",
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
                        self.userName = result.get("realName", result.get("name", self.userName))
                        self._current_port = FALLBACK_PORT
                        self._log(f"回退到端口 {FALLBACK_PORT} 成功", "info")
                except Exception as e:
                    self._log(f"回退登录也失败: {e}", "warning")

            if not self.userId or not self.sessionId:
                return {"success": False, "error": "登录成功但用户信息不完整"}

            self.session.headers.update({"sessionId": self.sessionId})
            name_display = f" ({self.userName})" if self.userName else ""
            self._log(f"登录成功 (UID: {self.userId}{name_display})", "success")
            return {"success": True, "userId": self.userId, "userName": self.userName}
        except Exception as e:
            self._log(f"登录异常: {str(e)}", "error")
            return {"success": False, "error": str(e)}

    def _fetch_day(self, date_str):
        """获取指定日期的课表数据"""
        try:
            res = self._request(
                "GET",
                "iclass.buaa.edu.cn",
                PRIMARY_PORT,
                API_PATHS["course_schedule"],
                params={"dateStr": date_str, "id": self.userId},
                timeout=10,
            )
            if res.status_code == 200:
                data = res.json()
                self._cache_course_names(data)
                return data
        except Exception:
            pass
        return None

    def _cache_course_names(self, data):
        """缓存课程 ID 到课程名称的映射"""
        if not data or "result" not in data:
            return
        for course in data.get("result", []):
            course_id = course.get("id", "")
            course_name = course.get("courseName", course.get("course_name", ""))
            if course_id and course_name:
                self._course_names[course_id] = course_name

    def get_week_courses(self, week_number, year, month, day):
        """并发获取一周课表并合并重复课程"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
        except ValueError:
            semester_start = datetime.datetime(2025, 9, 1)

        start_date = semester_start + datetime.timedelta(weeks=int(week_number) - 1)
        week_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

        self._week_cache = {}
        self._course_names = {}
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
                        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][idx],
                        "isToday": week_dates[idx].date() == datetime.date.today(),
                        "courses": merged,
                    }
                except Exception as e:
                    self._log(f"第 {idx + 1} 天数据获取失败: {str(e)}", "warning")
                    result[str(idx)] = {
                        "date": week_dates[idx].strftime("%m-%d"),
                        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][idx],
                        "isToday": False,
                        "courses": [],
                    }
        total = len([c for day in result.values() for c in day['courses']])
        self._log(f"课表加载完成，共 {total} 门课程", "success")
        return result

    def sign_course(self, course_ids, course_names=None):
        """
        发送签到请求。
        Args:
            course_ids: 课程 ID 列表
            course_names: 课程名称列表
        """
        # 统一处理为列表
        if isinstance(course_ids, str):
            try:
                course_ids = json.loads(course_ids)
            except:
                course_ids = [course_ids]
        if isinstance(course_names, str):
            try:
                course_names = json.loads(course_names)
            except:
                course_names = [course_names]
        if not course_names:
            course_names = []
        if not isinstance(course_ids, list):
            course_ids = [course_ids]

        success = 0
        failed = 0
        results = []

        for i, cid in enumerate(course_ids):
            course_name = None
            if i < len(course_names) and course_names[i]:
                course_name = course_names[i]
            if not course_name:
                course_name = self._course_names.get(cid, "")

            display_name = course_name if course_name else cid[:8] + "..."

            try:
                timestamp = int(time.time() * 1000) + 36000
                res = self._request(
                    "POST",
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
                            results.append({"id": cid, "name": display_name, "status": "success"})
                            self._log(f"{display_name} 签到成功", "success")
                        else:
                            failed += 1
                            err_msg = resp_data.get("ERRMSG", resp_data.get("ERRORMSG", "未知错误"))
                            results.append({"id": cid, "name": display_name, "status": "failed", "error": err_msg})
                            self._log(f"{display_name} 签到失败: {err_msg}", "warning")
                    except json.JSONDecodeError:
                        if "成功" in res.text or "SUCCESS" in res.text:
                            success += 1
                            results.append({"id": cid, "name": display_name, "status": "success"})
                            self._log(f"{display_name} 签到成功", "success")
                        else:
                            failed += 1
                            results.append({"id": cid, "name": display_name, "status": "failed"})
                else:
                    failed += 1
                    results.append({"id": cid, "name": display_name, "status": "failed", "error": f"HTTP {res.status_code}"})
                    self._log(f"{display_name} HTTP {res.status_code}", "warning")
            except Exception as e:
                failed += 1
                results.append({"id": cid, "name": display_name, "status": "failed", "error": str(e)[:50]})
                self._log(f"{display_name} 异常: {str(e)[:50]}", "warning")
            time.sleep(0.15)

        if success > 0:
            self._log(f"签到完成: {success}/{len(course_ids)} 成功", "success" if failed == 0 else "warning")
        else:
            self._log("签到失败：可能尚未开放签到或已过签到时间", "warning")

        return {"success": success, "total": len(course_ids), "failed": failed, "results": results}

    def batch_sign_week(self, week_number, year, month, day):
        """批量签到本周所有课程"""
        if not self._week_cache:
            self.get_week_courses(week_number, year, month, day)

        all_ids = []
        all_names = []
        for day_courses in self._week_cache.values():
            for c in day_courses:
                cid = c.get("id", "")
                all_ids.append(cid)
                name = c.get("courseName", "")
                if not name:
                    name = self._course_names.get(cid, "")
                all_names.append(name)

        if not all_ids:
            self._log("本周暂无可签到的课程", "warning")
            return {"success": 0, "total": 0}

        self._log(f"正在批量签到 {len(all_ids)} 门课程...")
        return self.sign_course(all_ids, all_names)

    def get_current_week(self, year, month, day):
        """根据学期起始日计算当前周数"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
            return max(1, min(18, (datetime.datetime.now() - semester_start).days // 7 + 1))
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
