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
import webbrowser
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import requests
import urllib3
import webview
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from iclass_client import (
    classify_sign_response,
    extract_iclass_login_name,
    get_network_urls as build_network_urls,
    get_sso_login_url,
    is_status_ok,
    status_means_no_data,
    server_time_offset_from_date,
)
from versioning import (
    CURRENT_VERSION,
    GITHUB_LATEST_RELEASE_API,
    GITHUB_RELEASES_PAGE,
    is_newer_version,
)

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

# ==========================================
# API 路径（区分直连和 VPN）
# ==========================================

def get_network_urls(use_vpn):
    """获取网络 URL，参照 Rust 版本的 network_urls"""
    return build_network_urls(use_vpn)


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
        self.server_time_offset_ms = 0

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

    def check_for_updates(self):
        """Check the latest published GitHub release without blocking app startup."""
        try:
            client = requests.Session()
            client.trust_env = False
            response = client.get(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"BUAASignTool/{CURRENT_VERSION}",
                },
                timeout=(4, 8),
            )
            response.raise_for_status()
            release = response.json()
            latest_version = str(release.get("tag_name", "")).strip()
            if not latest_version:
                raise ValueError("最新 Release 缺少版本标签")

            return {
                "success": True,
                "currentVersion": CURRENT_VERSION,
                "latestVersion": latest_version,
                "releaseName": str(release.get("name", "")).strip(),
                "updateAvailable": is_newer_version(latest_version),
                "releaseUrl": GITHUB_RELEASES_PAGE,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": f"网络请求失败: {e}",
            }
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return {
                "success": False,
                "error": f"Release 信息解析失败: {e}",
            }

    def open_releases_page(self):
        """Open only this project's trusted GitHub Releases page."""
        try:
            opened = webbrowser.open(GITHUB_RELEASES_PAGE, new=2)
            return {"success": bool(opened)}
        except Exception as e:
            return {"success": False, "error": str(e)}

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

    def _fetch_login_form(self, username, password):
        """加载 CAS 页面并保留当前页面要求的全部表单字段。"""
        login_entry = get_sso_login_url(self.use_vpn)
        response = self.session.get(login_entry, timeout=15, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        form = soup.select_one("form#loginForm, form#fm1, form[action]")
        if form is None:
            raise ValueError(f"无法解析统一认证登录表单（最终地址: {response.url}）")

        action_url = urljoin(response.url, form.get("action") or response.url)
        fields = {}
        for element in form.select("input[name]"):
            name = (element.get("name") or "").strip()
            input_type = (element.get("type") or "").lower()
            if not name or input_type in ("submit", "button", "image"):
                continue
            if input_type == "checkbox" and not element.has_attr("checked"):
                continue
            fields[name] = element.get("value", "")

        if not fields.get("execution"):
            raise ValueError("统一认证页面缺少 execution 参数，页面结构可能已更新")
        if "captchaId=" in response.text or "config.captcha" in response.text:
            raise ValueError("统一认证要求验证码，请先在浏览器完成一次认证后重试")

        fields.update({"username": username.strip(), "password": password})
        fields.setdefault("submit", "登录")
        fields.setdefault("type", "username_password")
        fields.setdefault("_eventId", "submit")
        return response.url, action_url, fields

    def _sso_login(self, username, password):
        """完成直连或 WebVPN 的统一身份认证，共享同一 cookie 会话。"""
        self._log("正在连接统一身份认证服务...")
        login_url, action_url, fields = self._fetch_login_form(username, password)
        response = self.session.post(
            action_url,
            data=fields,
            headers={"Referer": login_url},
            allow_redirects=True,
            timeout=20,
            verify=False,
        )
        response.raise_for_status()

        body = response.text
        soup = BeautifulSoup(body, "html.parser")
        error = soup.select_one("#msg, .login-error, .errors, .alert-danger, .error")
        if error and error.get_text(" ", strip=True):
            raise ValueError(f"统一认证失败: {error.get_text(' ', strip=True)}")
        if soup.select_one("form#loginForm input[name='execution'], form#fm1 input[name='execution']"):
            raise ValueError("统一认证失败：账号或密码错误，或账号需要先处理安全提示")
        self._log("统一身份认证成功", "success")

    def _resolve_iclass_login_name(self):
        """逐跳访问 MyCenter，提取 iClass 临时 loginName。"""
        urls = self._urls or get_network_urls(self.use_vpn)
        current_url = urls["my_center"]
        for _ in range(8):
            response = self.session.get(
                current_url, allow_redirects=False, timeout=15, verify=False
            )
            login_name = extract_iclass_login_name(response.url)
            if login_name:
                return login_name

            location = response.headers.get("Location")
            if location:
                login_name = extract_iclass_login_name(location)
                if login_name:
                    return login_name
                current_url = urljoin(response.url, location)
                continue

            login_name = extract_iclass_login_name(response.text)
            if login_name:
                return login_name
            raise ValueError(
                f"iClass MyCenter 未返回 loginName（HTTP {response.status_code}，"
                f"最终地址: {response.url}）"
            )
        raise ValueError("iClass MyCenter 跳转超过 8 次仍未返回 loginName")

    def login_direct(self, student_id, password=""):
        """校内直连也必须先通过统一身份认证。"""
        if not student_id or not password:
            return {"success": False, "error": "请输入学号和统一认证密码"}
        try:
            self._reset_session()
            self.use_vpn = False
            self._urls = get_network_urls(False)
            self._sso_login(student_id, password)
            return self._do_login(self._resolve_iclass_login_name())
        except Exception as e:
            self._log(f"登录失败: {e}", "error")
            return {"success": False, "error": str(e)}

    def login_vpn(self, vpn_username, vpn_password):
        """校外 WebVPN 登录"""
        self._log("正在解析 VPN 认证...")
        if not vpn_username or not vpn_password:
            return {"success": False, "error": "请输入账号和密码"}

        try:
            self._reset_session()
            self.use_vpn = True
            self._urls = get_network_urls(True)
            self._sso_login(vpn_username, vpn_password)
            return self._do_login(self._resolve_iclass_login_name())
        except Exception as e:
            self._log(f"登录失败: {e}", "error")
            return {"success": False, "error": str(e)}

    def _do_login(self, login_name):
        """使用 MyCenter 产生的临时 loginName 换取 iClass 会话。"""
        try:
            urls = self._urls or get_network_urls(self.use_vpn)
            res = self.session.get(
                urls["user_login"],
                params={
                    "phone": login_name,
                    "password": "",
                    "userLevel": "1",
                    "verificationType": "2",
                    "verificationUrl": "",
                },
                timeout=10,
                verify=False,
            )
            res.raise_for_status()
            self.server_time_offset_ms = server_time_offset_from_date(
                res.headers.get("date"),
                use_vpn=self.use_vpn,
            )
            data = res.json()
            
            if not is_status_ok(data):
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
            return {
                "success": True,
                "userId": self.userId,
                "userName": self.userName,
            }
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
            
            if not is_status_ok(data):
                return None

            semesters = data.get("result", [])
            current = None
            for sem in semesters:
                if str(sem.get("yearStatus", "")) == "1":
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
            
            if status_means_no_data(data):
                return []
            if not is_status_ok(data):
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
            
            if not is_status_ok(data):
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
            
            if status_means_no_data(data):
                return []
            if not is_status_ok(data):
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
            res.raise_for_status()
            data = res.json()
            if not is_status_ok(data) and not status_means_no_data(data):
                raise ValueError(data.get("ERRMSG", data.get("ERRORMSG", "课程接口返回失败")))
            self._cache_course_names(data)
            return data
        except Exception as e:
            self._log(f"{date_str} 课程获取失败: {e}", "warning")
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
            semester_start = datetime.datetime(2026, 9, 7)

        start_date = semester_start + datetime.timedelta(weeks=int(week_number) - 1)
        week_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

        self._week_cache = {}
        self._course_names = {}
        result = {}
        failed_days = []
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
                    if data is None:
                        failed_days.append(idx)
                    raw = (
                        data.get("result", [])
                        if data and is_status_ok(data)
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
                    failed_days.append(idx)
                    self._log(f"第 {idx + 1} 天数据获取失败: {str(e)}", "warning")
                    result[str(idx)] = {
                        "date": week_dates[idx].strftime("%m-%d"),
                        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][idx],
                        "isToday": False,
                        "courses": [],
                    }
        if len(failed_days) == len(week_dates):
            raise RuntimeError("一周课程接口全部请求失败，请检查登录状态或网络")

        total = len([c for day in result.values() for c in day['courses']])
        if failed_days:
            self._log(f"有 {len(failed_days)} 天课程获取失败，已显示其余结果", "warning")
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
                timestamp_response = self.session.get(
                    urls["sign_timestamp"], timeout=10, verify=False
                )
                timestamp_response.raise_for_status()
                timestamp_data = timestamp_response.json()
                timestamp = str(timestamp_data.get("timestamp", "")).strip()
                if not timestamp:
                    raise ValueError("签到服务器未返回 timestamp")
                
                # iClass 要求课程与时间在 query，用户 id 在表单体。
                res = self.session.post(
                    sign_url,
                    params={
                        "courseSchedId": cid,
                        "timestamp": timestamp,
                    },
                    data={"id": self.userId},
                    headers={"sessionId": self.sessionId},
                    timeout=10,
                    verify=False,
                )
                
                if res.status_code == 200:
                    try:
                        resp_data = res.json()
                        classification = classify_sign_response(resp_data)

                        if classification.status == "success":
                            success += 1
                            results.append({"id": cid, "name": display_name, "status": "success"})
                            self._log(f"{display_name} 签到成功", "success")
                        elif classification.status == "skipped":
                            skipped += 1
                            results.append({"id": cid, "name": display_name, "status": "skipped"})
                            self._log(f"{display_name} 已签到", "info")
                        else:
                            failed += 1
                            results.append({"id": cid, "name": display_name, "status": "failed"})
                            self._log(f"{display_name} 签到失败: {classification.message}", "warning")
                    except json.JSONDecodeError:
                        text = res.text
                        if "成功" in text or "SUCCESS" in text:
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
