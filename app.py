"""
北航课程打卡系统 — pywebview 后端
通过 js_api 将 Python 方法暴露给前端 JavaScript 调用
"""

import os
import json
import time
import datetime
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import requests
import webview


# --- 课程合并 ---
def merge_courses(courses):
    """将同一课程编号 + 同一时间段 + 同一教室的多位教师合并为一条"""
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


class Api:
    """暴露给前端的 Python API"""

    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BUAASignTool/2.0", "Connection": "keep-alive"}
        )
        self._week_cache = {}

    def login(self, student_id):
        """登录并返回结果"""
        try:
            url = "https://iclass.buaa.edu.cn:8346/app/user/login.action"
            params = {
                "password": "",
                "phone": student_id,
                "userLevel": "1",
                "verificationType": "2",
                "verificationUrl": "",
            }
            res = self.session.get(url, params=params, timeout=10)
            data = res.json()
            if data.get("STATUS") != "0":
                return {"success": False, "error": data.get("ERRORMSG", "登录失败")}
            self.userId = data["result"]["id"]
            self.sessionId = data["result"]["sessionId"]
            self.session.headers.update({"sessionId": self.sessionId})
            return {"success": True, "userId": self.userId}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _fetch_day(self, date_str):
        """获取单日课程原始数据"""
        try:
            url = (
                "https://iclass.buaa.edu.cn:8346/app/course/get_stu_course_sched.action"
            )
            params = {"dateStr": date_str, "id": self.userId}
            res = self.session.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
            return None
        except Exception:
            return None

    def get_week_courses(self, week_number, year, month, day):
        """并发获取一周课表，返回 7 天数据（已合并教师）"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
        except ValueError:
            semester_start = datetime.datetime(2025, 9, 1)

        start_date = semester_start + datetime.timedelta(weeks=int(week_number) - 1)
        week_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

        self._week_cache = {}
        result = {}

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
                except Exception:
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

        return result

    def sign_course(self, course_ids_json):
        """签到一个或多个课程ID"""
        course_ids = (
            json.loads(course_ids_json)
            if isinstance(course_ids_json, str)
            else course_ids_json
        )
        success = 0
        for cid in course_ids:
            try:
                url = (
                    f"http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action"
                    f"?courseSchedId={cid}&timestamp={int(time.time() * 1000)}"
                )
                r = self.session.post(url, params={"id": self.userId}, timeout=10)
                if r.status_code == 200:
                    try:
                        if r.json().get("STATUS") == "0":
                            success += 1
                    except json.JSONDecodeError:
                        if "成功" in r.text or "SUCCESS" in r.text:
                            success += 1
            except Exception:
                pass
            time.sleep(0.1)
        return {"success": success, "total": len(course_ids)}

    def batch_sign_week(self, week_number, year, month, day):
        """一键打卡本周所有课程"""
        if not self._week_cache:
            self.get_week_courses(week_number, year, month, day)

        all_ids = []
        for day_courses in self._week_cache.values():
            for c in day_courses:
                all_ids.append(c.get("id", ""))

        if not all_ids:
            return {"success": 0, "total": 0}

        return self.sign_course(all_ids)

    def get_current_week(self, year, month, day):
        """计算当前是第几周"""
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

    window = webview.create_window(
        "北航课程打卡系统",
        url=os.path.join(web_dir, "index.html"),
        js_api=api,
        width=1400,
        height=850,
        min_size=(1100, 700),
        text_select=False,
    )
    webview.start(debug=False)
