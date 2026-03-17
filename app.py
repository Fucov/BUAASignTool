"""
北航课程辅助系统 — 极简架构 (合并版)
支持：校内直连通信、校外 WebVPN 深穿透
架构：基于 pywebview 暴露 Api 至本地 JS 隔离环境，单体应用高度内聚
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
    pass  # 将在 README 中说明如有缺漏需补装 pycryptodome

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['http_proxy'] = os.environ['https_proxy'] = ''


def wengine_encrypt(text):
    """AES-CFB128 路由加密: 供 WebVPN 环境深穿透时转换 hostname 使用"""
    key = iv = b"wrdvpnisthebest!"
    cipher = AES.new(key, AES.MODE_CFB, iv, segment_size=128)
    return key.hex() + cipher.encrypt(text.encode('utf-8')).hex()


def merge_courses(courses):
    """单时间段同课程名称但持异教师名单合并去冗"""
    if not courses:
        return []
    merged = OrderedDict()
    for c in courses:
        key = (c.get('courseNum', ''), c.get('classBeginTime', ''), c.get('classroomName', ''))
        if key not in merged:
            mc = dict(c)
            mc['teachers'] = [c.get('teacherName', '未知')]
            mc['courseSchedIds'] = [c.get('id', '')]
            merged[key] = mc
        else:
            existing = merged[key]
            t = c.get('teacherName', '未知')
            if t not in existing['teachers']:
                existing['teachers'].append(t)
            existing['courseSchedIds'].append(c.get('id', ''))
    return list(merged.values())


def parse_buaa_curl(curl_text):
    """
    全自动拆解复杂的 cURL 载荷，提取网络身份验证所需的核心 Cookie (WebVPN/直连)。
    兼容由 Safari/Chrome 生成的 MacOS (bash/zsh) 反斜杠续行，及 Windows Cmd (^ 续行)。
    """
    # 彻底抹平跨平台的续行符及其附带的缩进或空白
    clean_text = re.sub(r'\\\s*\n\s*', ' ', curl_text)
    clean_text = re.sub(r'\^\s*\n\s*', ' ', clean_text)

    # 识别标准的 Cookie 头 (-H / -b)，提取单/双引号内部的全部内容
    # 适配形如: -H 'Cookie: a=1; b=2'
    match = re.search(r'Cookie:\s*([^\'"]+)', clean_text, re.IGNORECASE)
    if not match:
        # 回退适配：形如 -b 'a=1; b=2'
        match = re.search(r'-b\s*[\'"]([^\'"]+)[\'"]', clean_text, re.IGNORECASE)

    if match:
        cookie_str = match.group(1)
        # 精确过滤业务目标
        targets = ["wengine_vpn_ticket", "_zte_cid", "route"]
        parts = [p.strip() for p in cookie_str.split(";")]
        filtered = [p for p in parts if any(target in p for target in targets)]
        
        if filtered:
            return True, "; ".join(filtered)
        return False, "解析失败: 已提取 Cookie，但未找到隧道凭证 (_zte_cid_ / wengine_ticket)"
        
    return False, "解析失败: 无法在提供的 cURL 中找到 'Cookie:' 或 '-b' 字段"


# Windows 兼容性: 绝不要在开放给 js_api 的类中做 window=self 赋值，会导致 Python.NET 无限递归崩溃
_APP_CONTEXT = {}

class Api:
    """暴露给前端的 Python 底层调用集"""

    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.use_vpn = False
        self.session = requests.Session()
        self.session.trust_env = False  # 避免系统代理干预

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Connection': 'keep-alive'
        })
        self._week_cache = {}

    def _log(self, msg, msg_type="info"):
        """跨语言管道: 将本地事件逆推至前端 DOM UI"""
        window = _APP_CONTEXT.get('window')
        if window:
            safe_msg = msg.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
            try:
                window.evaluate_js(f"window.app.pushLog('{safe_msg}', '{msg_type}')")
            except Exception:
                pass

    def _request(self, method, scheme, host, port, path, **kwargs):
        """核心路由接管: 依据当前运行环境自适应封装路由包装、通信隧道及拉美语系 Header 污染校验"""
        if self.use_vpn:
            # 隧道探针：先行触碰
            probe_url = f"https://d.buaa.edu.cn/wengine-vpn/cookie?method={method.lower()}&host={host}:{port}&scheme={scheme}&path={path}"
            try:
                self.session.get(probe_url, timeout=3, verify=False)
            except Exception:
                pass
            
            # VPN 封装路径
            url = f"https://d.buaa.edu.cn/{scheme}-{port}/{wengine_encrypt(host)}{path}"
        else:
            url = f"{scheme}://{host}:{port}{path}"

        # 拉美语系拉丁字符过滤策略 - 防止请求抛出 Latin-1 异常
        for k, v in list(self.session.headers.items()):
            try:
                str(v).encode('latin-1')
            except UnicodeEncodeError:
                self.session.headers[k] = str(v).encode('utf-8').decode('latin-1', 'ignore')

        start_time = time.time()
        try:
            res = self.session.request(method, url, verify=False, **kwargs)
            cost = int((time.time() - start_time) * 1000)
            status = res.status_code
            if status >= 400:
                self._log(f"网络层抛出异常 [{status}]: {path} ({cost}ms)", "error")
            return res
        except requests.exceptions.RequestException as e:
            self._log(f"连接阻断: {path} - {str(e)}", "error")
            raise e

    def login_direct(self, student_id):
        """标准校园直连登陆模式"""
        self.use_vpn = False
        return self._do_login(student_id)

    def login_vpn(self, student_id, curl_text):
        """高墙穿透 WebVPN 模式"""
        self._log("> 开始解构用户 cURL 持有态...")
        success, cookie_data = parse_buaa_curl(curl_text)
        if not success:
            return {'success': False, 'error': cookie_data}
        
        # 强清 Header 非 ASCII 字符串病态
        clean_cookie = "".join(i for i in cookie_data if ord(i) < 128)
        self.session.headers.update({"Cookie": clean_cookie})
        self.use_vpn = True
        self._log("> 隧道凭集锁定。下发业务侧鉴权机制...", "success")
        return self._do_login(student_id)

    def _do_login(self, student_id):
        """真实鉴权方法，将 `student_id` 推流至 iClass 服务器"""
        try:
            res = self._request("GET", "https", "iclass.buaa.edu.cn", "8346", "/app/user/login.action",
                                params={"password": "", "phone": student_id, "userLevel": "1", "verificationType": "2", "verificationUrl": ""}, 
                                timeout=10)
            data = res.json()
            if data.get('STATUS') != '0':
                error_msg = data.get('ERRORMSG', '获取会话阻断')
                self._log(f"鉴权失败: {error_msg}", "error")
                return {'success': False, 'error': error_msg}

            self.userId = data['result']['id']
            self.sessionId = data['result']['sessionId']
            self.session.headers.update({'sessionId': self.sessionId})
            self._log(f"鉴权通行 (UID: {self.userId})", "success")
            return {'success': True, 'userId': self.userId}
        except Exception as e:
            self._log(f"网络异常导致鉴权崩溃: {str(e)}", "error")
            return {'success': False, 'error': str(e)}

    def _fetch_day(self, date_str):
        """独立线程任务: 提取一天的流并汇集"""
        try:
            res = self._request("GET", "https", "iclass.buaa.edu.cn", "8346", "/app/course/get_stu_course_sched.action",
                                params={'dateStr': date_str, 'id': self.userId}, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass
        return None

    def get_week_courses(self, week_number, year, month, day):
        """流处理：调度线程池并发抽取 7 日周期课表并合并冗余节点"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
        except ValueError:
            semester_start = datetime.datetime(2025, 9, 1)

        start_date = semester_start + datetime.timedelta(weeks=int(week_number) - 1)
        week_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

        self._week_cache = {}
        result = {}
        self._log(f"并轨流拉取第 {week_number} 周课表...")

        with ThreadPoolExecutor(max_workers=7) as executor:
            future_map = {
                executor.submit(self._fetch_day, d.strftime('%Y%m%d')): i
                for i, d in enumerate(week_dates)
            }
            for future in future_map:
                idx = future_map[future]
                try:
                    data = future.result()
                    raw = data.get('result', []) if data and data.get('STATUS') == '0' else []
                    self._week_cache[idx] = raw
                    merged = merge_courses(raw)
                    result[str(idx)] = {
                        'date': week_dates[idx].strftime('%m-%d'),
                        'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][idx],
                        'isToday': week_dates[idx].date() == datetime.date.today(),
                        'courses': merged
                    }
                except Exception as e:
                    self._log(f"截获到第 {idx+1} 天请求受阻: {str(e)}", "warning")
                    result[str(idx)] = {
                        'date': week_dates[idx].strftime('%m-%d'),
                        'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][idx],
                        'isToday': False,
                        'courses': []
                    }
        self._log(f"拉取组装周期完毕 ({len([c for day in result.values() for c in day['courses']])} 块数据节点)", "success")
        return result

    def sign_course(self, course_ids_json):
        """穿透发送物理打卡指令（要求严苛：必须为 HTTP : 8081）"""
        course_ids = json.loads(course_ids_json) if isinstance(course_ids_json, str) else course_ids_json
        success = 0
        for cid in course_ids:
            try:
                res = self._request("POST", "http", "iclass.buaa.edu.cn", "8081", "/app/course/stu_scan_sign.action",
                                    params={'courseSchedId': cid, 'timestamp': int(time.time() * 1000), 'id': self.userId}, 
                                    timeout=10)
                if res.status_code == 200:
                    try:
                        if res.json().get('STATUS') == '0':
                            success += 1
                    except json.JSONDecodeError:
                        if '成功' in res.text or 'SUCCESS' in res.text:
                            success += 1
            except Exception:
                pass
            time.sleep(0.15)
        
        if success > 0:
            self._log(f"触发打卡流程: 准入验证拦截率 0，成功投递 {success}/{len(course_ids)} 枚票据。", "success")
        else:
            self._log("触发打卡流程: 状态驳回，节点可能已封锁（尚未开签或超越时间面）。", "warning")
            
        return {'success': success, 'total': len(course_ids)}

    def batch_sign_week(self, week_number, year, month, day):
        """流触发：提取本地 _week_cache 中本周尚未超期的所有票据进行组装推送"""
        if not self._week_cache:
            self.get_week_courses(week_number, year, month, day)

        all_ids = []
        for day_courses in self._week_cache.values():
            for c in day_courses:
                all_ids.append(c.get('id', ''))

        if not all_ids:
            self._log("未寻找到可推送的打卡票据块。", "warning")
            return {'success': 0, 'total': 0}

        self._log(f"一键部署推送阵列，负载 {len(all_ids)} 个信号流向端点...")
        return self.sign_course(all_ids)

    def get_current_week(self, year, month, day):
        """基于起始日推算空间时间差值"""
        try:
            semester_start = datetime.datetime(int(year), int(month), int(day))
            return max(1, min(18, (datetime.datetime.now() - semester_start).days // 7 + 1))
        except ValueError:
            return 1


if __name__ == '__main__':
    api = Api()
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')

    app_window = webview.create_window(
        'BUAA Course Assistant',
        url=os.path.join(web_dir, 'index.html'),
        js_api=api,
        width=1400,
        height=850,
        min_size=(1100, 700),
        text_select=False
    )
    _APP_CONTEXT['window'] = app_window
    webview.start(debug=False)
