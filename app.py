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

# ==========================================
# API 路径（区分直连和 VPN）
# ==========================================

def get_network_urls(use_vpn):
    """获取网络 URL，参照 Rust 版本的 network_urls"""
    if use_vpn:
        base = f"https://d.buaa.edu.cn/https-8347/{VPN_SERVICE_ID}"
        return {
            "service_home": base,
            "user_login": f"{base}/app/user/login.action",
            "course_list": f"{base}/app/choosecourse/get_myall_course.action",
            "semester_list": f"{base}/app/course/get_base_school_year.action",
            "course_sign_detail": f"{base}/app/my/get_my_course_sign_detail.action",
            "scan_sign": f"{base}/app/course/stu_scan_sign.action",
            "course_schedule_by_date": f"{base}/app/course/get_stu_course_sched.action",
        }
    else:
        base = "https://iclass.buaa.edu.cn:8347"
        return {
            "service_home": base,
            "user_login": f"{base}/app/user/login.action",
            "course_list": f"{base}/app/choosecourse/get_myall_course.action",
            "semester_list": f"{base}/app/course/get_base_school_year.action",
            "course_sign_detail": f"{base}/app/my/get_my_course_sign_detail.action",
            "scan_sign": "http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action",
            "course_schedule_by_date": f"{base}/app/course/get_stu_course_sched.action",
        }


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
            # 如果当前课程已签到，合并后也标记为已签到
            if str(c.get("signStatus", "")) == "1":
                mc["signStatus"] = "1"
            merged[key] = mc
        else:
            existing = merged[key]
            t = c.get("teacherName", "未知")
            if t not in existing["teachers"]:
                existing["teachers"].append(t)
            existing["courseSchedIds"].append(c.get("id", ""))
            # 如果任一课程已签到，合并后标记为已签到
            if str(c.get("signStatus", "")) == "1":
                existing["signStatus"] = "1"
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
        self._urls = None

    def _reset_session(self):
        """重置会话，清除 cookies"""
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
        """构建 VPN 代理 URL"""
        return f"https://d.buaa.edu.cn/https-8347/{VPN_SERVICE_ID}{path}"

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

    def _fetch_execution(self):
        """从 SSO 登录页面获取 execution 令牌"""
        try:
            response = self.session.get(SSO_LOGIN_URL, timeout=10, verify=False)
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

    def _vpn_login(self, username, password):
        """通过统一身份认证登录 WebVPN"""
        try:
            self._log("正在连接 SSO 认证服务...")
            execution = self._fetch_execution()
            self._log("已获取认证令牌，正在登录...", "info")

            response = self.session.post(
                SSO_LOGIN_URL,
                data={
                    "username": username,
                    "password": password,
                    "submit": "登录",
                    "type": "username_password",
                    "execution": execution,
                    "_eventId": "submit",
                },
                headers={"Referer": SSO_LOGIN_URL},
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
                urls = get_network_urls(True)
                probe_url = urls["service_home"] + "/"
                probe_response = self.session.get(probe_url, timeout=10, verify=False)
                probe_final_url = probe_response.url

                if self._is_iclass_url(probe_final_url):
                    self._log("VPN 隧道建立成功", "success")
                    return True

                self._log(f"探测响应 URL: {probe_final_url}", "info")
                raise ValueError("建立 VPN 隧道失败")

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
        self._urls = get_network_urls(False)
        return self._do_login(student_id)

    def login_vpn(self, vpn_username, vpn_password, student_id=None):
        """校外 WebVPN 登录"""
        self._log("正在解析 VPN 认证...")
        if not vpn_username or not vpn_password:
            return {"success": False, "error": "请输入账号和密码"}

        try:
            # 重置会话以清除旧的 cookies
            self._reset_session()
            self._vpn_sso_login(vpn_username, vpn_password)
            self.use_vpn = True
            self._urls = get_network_urls(True)
            # 如果没有提供学号，使用 VPN 账号作为学号
            target_id = student_id.strip() if student_id and student_id.strip() else vpn_username
            return self._do_login(target_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _vpn_sso_login(self, username, password):
        """通过统一身份认证登录 WebVPN（内部方法）"""
        try:
            self._log("正在连接 SSO 认证服务...")
            execution = self._fetch_execution()
            self._log("已获取认证令牌，正在登录...", "info")

            response = self.session.post(
                SSO_LOGIN_URL,
                data={
                    "username": username,
                    "password": password,
                    "submit": "登录",
                    "type": "username_password",
                    "execution": execution,
                    "_eventId": "submit",
                },
                headers={"Referer": SSO_LOGIN_URL},
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
                urls = get_network_urls(True)
                probe_url = urls["service_home"] + "/"
                probe_response = self.session.get(probe_url, timeout=10, verify=False)
                probe_final_url = probe_response.url

                if self._is_iclass_url(probe_final_url):
                    self._log("VPN 隧道建立成功", "success")
                    return True

                self._log(f"探测响应 URL: {probe_final_url}", "info")
                raise ValueError("建立 VPN 隧道失败")

            if response.status_code == 401:
                raise ValueError("账号或密码错误")

            raise ValueError(f"登录失败，最终 URL: {final_url}")

        except ValueError:
            raise
        except Exception as e:
            self._log(f"VPN 登录异常: {e}", "error")
            raise

    def _do_login(self, student_id):
        """执行登录请求"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["user_login"],
                params={
                    "phone": student_id,
                    "password": "",
                    "userLevel": "1",
                    "verificationType": "2",
                    "verificationUrl": "",
                },
                timeout=10,
                verify=False,
            )
            res.raise_for_status()
            data = res.json()
            
            if data.get("STATUS") != "0" and data.get("status") != "0":
                error_msg = data.get("ERRMSG", data.get("ERRORMSG", "服务器拒绝登录"))
                self._log(f"登录失败: {error_msg}", "error")
                return {"success": False, "error": error_msg}

            result = data.get("result", data)
            self.userId = str(result.get("id", ""))
            self.sessionId = result.get("sessionId", "")
            self.userName = result.get("realName", result.get("name", ""))

            if not self.userId or not self.sessionId:
                self._log("登录成功但获取用户信息不完整", "warning")
                return {"success": False, "error": "登录成功但用户信息不完整"}

            self.session.headers.update({"sessionId": self.sessionId})
            name_display = f" ({self.userName})" if self.userName else ""
            self._log(f"登录成功 (UID: {self.userId})", "success")
            return {"success": True, "userId": self.userId}
        except Exception as e:
            self._log(f"登录异常: {str(e)}", "error")
            return {"success": False, "error": str(e)}

    def _get_semester_code(self):
        """获取当前学期代码"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["semester_list"],
                params={"userId": self.userId, "type": "2"},
                headers={"sessionId": self.sessionId},
                timeout=10,
                verify=False,
            )
            res.raise_for_status()
            data = res.json()
            
            if data.get("STATUS") != "0":
                return None

            semesters = data.get("result", [])
            current = None
            for sem in semesters:
                if sem.get("yearStatus") == "1":
                    current = sem.get("code")
                    break
            if not current and semesters:
                current = semesters[0].get("code")
            return current
        except Exception:
            return None

    def _get_courses(self, semester_code):
        """获取课程列表"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["course_list"],
                params={
                    "user_type": "1",
                    "id": self.userId,
                    "xq_code": semester_code,
                },
                headers={"sessionId": self.sessionId},
                timeout=10,
                verify=False,
            )
            res.raise_for_status()
            data = res.json()
            
            if data.get("STATUS") != "0":
                return []

            courses = []
            for item in data.get("result", []):
                course_id = item.get("course_id", "")
                if course_id:
                    courses.append({
                        "name": item.get("course_name", "未知课程") or "未知课程",
                        "id": course_id,
                    })
            return courses
        except Exception:
            return []

    def _get_course_detail(self, course_id):
        """获取单个课程的签到详情"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            url = f"{urls['course_sign_detail']}?id={self.userId}&courseId={course_id}&sessionId={self.sessionId}"
            res = self.session.get(url, timeout=10, verify=False)
            res.raise_for_status()
            data = res.json()
            
            if data.get("STATUS") != "0":
                return []
            return data.get("result", [])
        except Exception:
            return []

    def _get_course_by_date(self, date_str):
        """按日期获取课程"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["course_schedule_by_date"],
                params={"id": self.userId, "dateStr": date_str},
                headers={"sessionId": self.sessionId},
                timeout=10,
                verify=False,
            )
            res.raise_for_status()
            data = res.json()
            
            if data.get("STATUS") == "2":
                return []
            if data.get("STATUS") != "0":
                return []
            return data.get("result", [])
        except Exception:
            return []

    def _normalize_date(self, raw_date):
        """规范化日期显示"""
        digits = ''.join(c for c in raw_date if c.isdigit())
        if len(digits) >= 8:
            return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
        return raw_date

    def _normalize_time(self, raw_time):
        """规范化时间显示"""
        raw_time = raw_time.strip()
        if not raw_time:
            return ""
        parts = raw_time.split()
        time_part = parts[-1] if len(parts) > 1 else raw_time
        time_parts = time_part.split(':')
        hour = time_parts[0] if time_parts else ""
        minute = time_parts[1] if len(time_parts) > 1 else ""
        if hour and minute:
            return f"{hour.zfill(2)}:{minute}"
        return time_part

    def _fetch_day(self, date_str):
        """获取指定日期的课表数据"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["course_schedule_by_date"],
                params={"id": self.userId, "dateStr": date_str},
                headers={"sessionId": self.sessionId},
                timeout=10,
                verify=False,
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
                    
                    # 处理课程数据，确保 signStatus 正确
                    processed = []
                    for c in raw:
                        # signStatus 可能是 "1", "0", None, 或字段不存在
                        raw_status = c.get("signStatus", "")
                        sign_status = str(raw_status) if raw_status is not None else ""
                        processed.append({
                            "id": c.get("id", ""),
                            "courseName": c.get("courseName", ""),
                            "courseNum": c.get("courseNum", ""),
                            "classBeginTime": c.get("classBeginTime", ""),
                            "classEndTime": c.get("classEndTime", ""),
                            "classroomName": c.get("classroomName", ""),
                            "teachBuildName": c.get("teachBuildName", ""),
                            "storeyName": c.get("storeyName", ""),
                            "teacherName": c.get("teacherName", ""),
                            "signStatus": sign_status,
                        })
                    
                    merged = merge_courses(processed)
                    # 缓存也存储处理后的数据，供 batch_sign_week 使用
                    self._week_cache[idx] = merged
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
        参照 Rust 版本的 sign_now 方法。
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
        skipped = 0
        failed = 0
        results = []

        urls = self._urls or get_network_urls(self.use_vpn)
        sign_url = urls["scan_sign"]

        for i, cid in enumerate(course_ids):
            course_name = None
            if i < len(course_names) and course_names[i]:
                course_name = course_names[i]
            if not course_name:
                course_name = self._course_names.get(cid, "")

            display_name = course_name if course_name else cid[:8] + "..."

            try:
                timestamp = str(int(time.time() * 1000) + 36000)
                
                # 参照 Rust 版本：POST 请求，参数放在 query string
                res = self.session.post(
                    sign_url,
                    params={
                        "id": self.userId,
                        "courseSchedId": cid,
                        "timestamp": timestamp,
                    },
                    headers={"sessionId": self.sessionId},
                    timeout=10,
                    verify=False,
                )
                
                if res.status_code == 200:
                    try:
                        resp_data = res.json()
                        # 处理 STATUS 可能是数字或字符串
                        status_raw = resp_data.get("STATUS", resp_data.get("status", ""))
                        status = str(status_raw)
                        
                        if status == "0":
                            success += 1
                            results.append({"id": cid, "name": display_name, "status": "success"})
                            self._log(f"{display_name} 签到成功", "success")
                        else:
                            err_msg = str(resp_data.get("ERRMSG", resp_data.get("ERRORMSG", "")))
                            if "已签到" in err_msg:
                                skipped += 1
                                results.append({"id": cid, "name": display_name, "status": "skipped"})
                                self._log(f"{display_name} 已签到", "info")
                            else:
                                failed += 1
                                results.append({"id": cid, "name": display_name, "status": "failed"})
                                self._log(f"{display_name} 签到失败", "warning")
                    except json.JSONDecodeError:
                        text = res.text
                        if "成功" in text or "SUCCESS" in text or "status" in text.lower():
                            success += 1
                            results.append({"id": cid, "name": display_name, "status": "success"})
                            self._log(f"{display_name} 签到成功", "success")
                        else:
                            failed += 1
                            results.append({"id": cid, "name": display_name, "status": "failed"})
                else:
                    failed += 1
                    results.append({"id": cid, "name": display_name, "status": "failed"})
                    self._log(f"{display_name} 网络错误: {res.status_code}", "warning")
            except Exception as e:
                failed += 1
                results.append({"id": cid, "name": display_name, "status": "failed"})
                self._log(f"{display_name} 请求异常", "warning")
            time.sleep(0.15)

        total = len(course_ids)
        if skipped > 0:
            self._log(f"签到完成: {success}/{total} 成功，{skipped} 已跳过", "success" if failed == 0 else "warning")
        elif success > 0:
            self._log(f"签到完成: {success}/{total} 成功", "success" if failed == 0 else "warning")
        else:
            self._log("签到完成: 本周暂无待签到课程", "info")

        return {"success": success, "total": total, "skipped": skipped, "failed": failed, "results": results}

    def batch_sign_week(self, week_number, year, month, day):
        """批量签到本周所有课程（自动跳过已签到）"""
        if not self._week_cache:
            self.get_week_courses(week_number, year, month, day)

        all_ids = []
        all_names = []
        for day_courses in self._week_cache.values():
            for c in day_courses:
                cid = c.get("id", "")
                # 检查是否已签到
                sign_status = str(c.get("signStatus", ""))
                if sign_status == "1":
                    name = c.get("courseName", cid)
                    self._log(f"跳过已签到: {name}", "info")
                    continue
                all_ids.append(cid)
                name = c.get("courseName", "")
                if not name:
                    name = self._course_names.get(cid, "")
                all_names.append(name)

        if not all_ids:
            self._log("本周暂无待签到课程", "info")
            return {"success": 0, "total": 0, "skipped": 0}

        self._log(f"正在批量签到 {len(all_ids)} 门课程...")
        result = self.sign_course(all_ids, all_names)
        
        # 签到成功后更新本地缓存
        if result.get("success", 0) > 0:
            for res_item in result.get("results", []):
                if res_item.get("status") == "success":
                    cid = res_item.get("id", "")
                    for day_courses in self._week_cache.values():
                        for c in day_courses:
                            if c.get("id") == cid:
                                c["signStatus"] = "1"
                                break
        
        return result

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
