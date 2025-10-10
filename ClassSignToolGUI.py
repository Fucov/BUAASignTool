import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip
import requests
import json
import time
import datetime
import threading
from tkinter import messagebox, scrolledtext


# --- 文本截断辅助函数 ---
def truncate_text(text, max_length):
    """如果文本超过最大长度，则截断并添加'...'"""
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text


# --- 课程卡片UI组件 (最终设计) ---
class CourseCard(ttk.Labelframe):
    """
    最终版课程卡片：
    - 修复了重复图标的BUG。
    - 课程标题居中，详细信息左对齐，排版更专业。
    - ToolTip功能完全可用。
    """

    def __init__(self, parent, course_data, sign_command, **kwargs):
        course_name = course_data.get('courseName', '未知课程')
        truncated_name = truncate_text(course_name, 15)

        # 使用 ttk.Labelframe 实现类似圆角和带标题的边框效果
        super().__init__(parent, text=f" {truncated_name} ", bootstyle="primary", padding=15, **kwargs)

        # 为卡片标题添加悬浮提示
        if course_name != truncated_name:
            ToolTip(self, text=course_name, bootstyle="light-inverse", delay=500)

        location = course_data.get('classroomName', '未知地点')
        teacher = course_data.get('teacherName', '未知教师')
        class_begin = course_data['classBeginTime'][11:16]
        class_end = course_data['classEndTime'][11:16]
        truncated_loc = truncate_text(location, 14)
        truncated_teacher = truncate_text(teacher, 10)

        # --- 内部细节布局 ---
        # 详细信息左对齐，更易阅读
        details_frame = ttk.Frame(self)
        details_frame.pack(fill=X, pady=(5, 0))
        details_frame.columnconfigure(1, weight=1)

        # 时间 (一行搞定，避免重复图标)
        time_label = ttk.Label(details_frame, text=f"🕒 {class_begin} - {class_end}", font=("微软雅黑", 10))
        time_label.grid(row=0, column=0, columnspan=2, sticky='w')

        # 地点
        loc_label = ttk.Label(details_frame, text=f"📍 {truncated_loc}", font=("微软雅黑", 10))
        loc_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=(8, 0))
        if location != truncated_loc:
            ToolTip(loc_label, text=location, bootstyle="light-inverse", delay=500)

        # 教师 (修复了重复图标的问题)
        teacher_label = ttk.Label(details_frame, text=f"👨‍ {truncated_teacher}", font=("微软雅黑", 10))
        teacher_label.grid(row=2, column=0, columnspan=2, sticky='w', pady=(8, 0))
        if teacher != truncated_teacher:
            ToolTip(teacher_label, text=teacher, bootstyle="light-inverse", delay=500)

        # 打卡按钮
        sign_btn = ttk.Button(self, text="✅ 课程打卡", bootstyle="outline-success", command=sign_command)
        sign_btn.pack(fill=X, pady=(20, 0))


# --- 主程序类 ---
class CourseSignApp:
    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.semester_start = datetime.datetime(2025, 9, 1)
        self.mouse_on_canvas = False  # 用于修复滚动BUG的标志位

        # 全新主题: 使用明亮、专业的 'cosmo' 主题
        self.root = ttk.Window(title="北航课程打卡系统", themename="cosmo", size=(1400, 850), position=(50, 50),
                               resizable=(True, True))
        self.root.minsize(1200, 750)
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=25)
        main_frame.pack(fill=BOTH, expand=True)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 25))
        title_label = ttk.Label(header_frame, text="✈️ 北航课程打卡系统", font=("微软雅黑", 24, "bold"),
                                bootstyle=PRIMARY)
        title_label.pack(side=LEFT)
        self.login_status = ttk.Label(header_frame, text="🔴 未登录", bootstyle=DANGER, font=("微软雅黑", 12))
        self.login_status.pack(side=RIGHT, padx=(0, 10), pady=5)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=BOTH, expand=True)
        control_panel = ttk.Labelframe(content_frame, text="控制面板", width=320, padding=20)
        control_panel.pack(side=LEFT, fill=Y, padx=(0, 25))
        control_panel.pack_propagate(False)
        content_panel = ttk.Frame(content_frame)
        content_panel.pack(side=RIGHT, fill=BOTH, expand=True)
        self.setup_control_panel(control_panel)
        self.setup_content_panel(content_panel)
        self.status_var = tk.StringVar(value="👋 欢迎使用北航课程打卡系统")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=SUNKEN, anchor=W, font=("微软雅黑", 10))
        status_bar.pack(side=BOTTOM, fill=X, pady=(15, 0))

    def setup_control_panel(self, parent):
        ttk.Label(parent, text="学号:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 5))
        self.student_id_var = tk.StringVar(value="")
        ttk.Entry(parent, textvariable=self.student_id_var, font=("微软雅黑", 11)).pack(fill=X, pady=(0, 15))
        ttk.Label(parent, text="学期设置:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 5))
        date_frame = ttk.Labelframe(parent, text="第一周周一日期", padding=10)
        date_frame.pack(fill=X, pady=(0, 10))
        self.year_var = tk.StringVar(value="2025")
        ttk.Spinbox(date_frame, from_=2020, to=2030, textvariable=self.year_var, width=5).pack(side=LEFT, fill=X,
                                                                                               expand=True)
        ttk.Label(date_frame, text="年").pack(side=LEFT, padx=5)
        self.month_var = tk.StringVar(value="9")
        ttk.Combobox(date_frame, textvariable=self.month_var, values=[str(i) for i in range(1, 13)], state="readonly",
                     width=3).pack(side=LEFT)
        ttk.Label(date_frame, text="月").pack(side=LEFT, padx=5)
        self.day_var = tk.StringVar(value="1")
        ttk.Combobox(date_frame, textvariable=self.day_var, values=[str(i) for i in range(1, 32)], state="readonly",
                     width=3).pack(side=LEFT)
        ttk.Label(date_frame, text="日").pack(side=LEFT, padx=(5, 0))
        ttk.Button(parent, text="🚀 登录系统", command=self.login, bootstyle=SUCCESS).pack(fill=X, pady=(10, 20),
                                                                                          ipady=5)
        ttk.Separator(parent).pack(fill=X, pady=(0, 20))
        ttk.Label(parent, text="周数选择:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 5))
        self.week_var = tk.StringVar(value="第 1 周")
        week_combo = ttk.Combobox(parent, textvariable=self.week_var, values=[f"第 {i} 周" for i in range(1, 19)],
                                  state="readonly", font=("微软雅黑", 11), height=12)
        week_combo.pack(fill=X)
        week_combo.bind('<<ComboboxSelected>>', lambda e: self.load_week_courses())
        nav_frame = ttk.Frame(parent)
        nav_frame.pack(fill=X, pady=(8, 15))
        ttk.Button(nav_frame, text="◀ 上一周", command=self.previous_week, bootstyle="outline-primary").pack(side=LEFT,
                                                                                                             fill=X,
                                                                                                             expand=True,
                                                                                                             padx=(0,
                                                                                                                   5))
        ttk.Button(nav_frame, text="下一周 ▶", command=self.next_week, bootstyle="outline-primary").pack(side=RIGHT,
                                                                                                         fill=X,
                                                                                                         expand=True)
        ttk.Button(parent, text="🔄 刷新课表", command=self.load_week_courses, bootstyle="info").pack(fill=X,
                                                                                                     pady=(0, 20))
        ttk.Separator(parent).pack(fill=X, pady=(0, 20))
        ttk.Label(parent, text="快速操作:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 10))
        ttk.Button(parent, text="📅 跳转到当前周", command=self.jump_to_current_week, bootstyle="outline-info").pack(
            fill=X, pady=(0, 10))
        ttk.Button(parent, text="✅ 一键打卡本周", command=self.batch_sign_week, bootstyle=WARNING).pack(fill=X,
                                                                                                        pady=(0, 10))

    def setup_content_panel(self, parent):
        notebook = ttk.Notebook(parent, bootstyle="primary")
        notebook.pack(fill=BOTH, expand=True)
        week_view_frame = ttk.Frame(notebook, padding=(15, 10))
        notebook.add(week_view_frame, text="  📅 周视图课表  ")
        self.setup_week_view(week_view_frame)
        log_frame = ttk.Frame(notebook, padding=10)
        notebook.add(log_frame, text="  📝 操作日志  ")
        self.setup_log_view(log_frame)

    def setup_week_view(self, parent):
        self.day_headers_frame = ttk.Frame(parent)
        self.day_headers_frame.pack(fill=X, pady=(0, 10))
        for i in range(7):
            self.day_headers_frame.grid_columnconfigure(i, weight=1, uniform="day_cols")
        content_wrapper = ttk.Frame(parent)
        content_wrapper.pack(fill=BOTH, expand=True)
        self.course_canvas = tk.Canvas(content_wrapper, highlightthickness=0, bg=self.root.cget('bg'))
        self.course_scrollbar = ttk.Scrollbar(content_wrapper, orient=VERTICAL, command=self.course_canvas.yview,
                                              bootstyle="round-primary")
        self.course_canvas.configure(yscrollcommand=self.course_scrollbar.set)
        self.course_scrollbar.pack(side=RIGHT, fill=Y)
        self.course_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.course_container = ttk.Frame(self.course_canvas)
        self.container_id = self.course_canvas.create_window((0, 0), window=self.course_container, anchor="nw")
        self.day_frames = []
        for i in range(7):
            self.course_container.grid_columnconfigure(i, weight=1, uniform="day_cols")
            day_inner_frame = ttk.Frame(self.course_container)
            day_inner_frame.grid(row=0, column=i, sticky="nsew", padx=5, pady=5)
            self.day_frames.append(day_inner_frame)
        self.course_canvas.bind("<Configure>", self._on_canvas_configure)
        # 核心BUG修复: 使用Enter和Leave事件代替winfo_containing
        self.course_canvas.bind("<Enter>", self._on_canvas_enter)
        self.course_canvas.bind("<Leave>", self._on_canvas_leave)
        self.root.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")

    def _on_canvas_enter(self, event):
        self.mouse_on_canvas = True

    def _on_canvas_leave(self, event):
        self.mouse_on_canvas = False

    def _on_canvas_configure(self, event):
        self.course_canvas.itemconfig(self.container_id, width=event.width)

    def _on_mouse_wheel(self, event):
        # 核心BUG修复: 基于标志位判断，不再调用winfo_containing
        if self.mouse_on_canvas:
            self.course_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ... (后续所有逻辑函数完全不变) ...
    def setup_log_view(self, parent):
        self.log_text = scrolledtext.ScrolledText(parent, wrap=WORD, font=("Consolas", 10), relief=FLAT, bd=5)
        self.log_text.pack(fill=BOTH, expand=True)
        self.log_text.config(state=DISABLED)

    def log_message(self, message, message_type="info"):
        self.root.after(0, self._log_message_ui, message, message_type)

    def _log_message_ui(self, message, message_type):
        self.log_text.config(state=NORMAL)
        icons = {"success": "✅", "error": "❌", "warning": "⚠️", "info": "ℹ️"}
        colors = {"success": "#28a745", "error": "#dc3545", "warning": "#ffc107", "info": "#17a2b8"}
        icon, color = icons.get(message_type, "ℹ️"), colors.get(message_type, "#17a2b8")
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        tag_name = f"tag_{message_type}_{int(time.time() * 1000)}"
        self.log_text.tag_config(tag_name, foreground=color)
        self.log_text.insert(END, f"[{timestamp}] {icon} ", f"tag_icon_{message_type}")
        self.log_text.insert(END, f"{message}\n", tag_name)
        self.log_text.see(END);
        self.log_text.config(state=DISABLED)

    def validate_input(self):
        student_id = self.student_id_var.get().strip()
        if not student_id or not student_id.isdigit(): messagebox.showerror("输入错误",
                                                                            "请输入有效的数字学号"); return False
        try:
            datetime.datetime(int(self.year_var.get()), int(self.month_var.get()), int(self.day_var.get()))
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的学期开始日期"); return False
        return True

    def get_semester_start_date(self):
        try:
            return datetime.datetime(int(self.year_var.get()), int(self.month_var.get()), int(self.day_var.get()))
        except ValueError:
            return datetime.datetime(2025, 9, 1)

    def login(self):
        if self.validate_input(): threading.Thread(target=self._execute_login, daemon=True).start()

    def _execute_login(self):
        self.status_var.set("🔄 正在登录...");
        self.root.after(0, lambda: self.login_status.config(text="🟡 登录中...", bootstyle=WARNING))
        try:
            student_id = self.student_id_var.get().strip()
            url, params = 'https://iclass.buaa.edu.cn:8346/app/user/login.action', {'password': '', 'phone': student_id,
                                                                                    'userLevel': '1',
                                                                                    'verificationType': '2',
                                                                                    'verificationUrl': ''}
            res = requests.get(url=url, params=params, timeout=10)
            userData = res.json()
            if userData.get('STATUS') != '0':
                error_msg = userData.get('ERRORMSG', '未知错误');
                self.log_message(f"登录失败: {error_msg}", "error")
                self.root.after(0, lambda: self.login_status.config(text="🔴 登录失败", bootstyle=DANGER));
                self.status_var.set(f"❌ 登录失败: {error_msg}");
                return
            self.userId, self.sessionId = userData['result']['id'], userData['result']['sessionId']
            self.semester_start = self.get_semester_start_date()
            self.log_message(f"登录成功! 用户ID: {self.userId}", "success")
            self.root.after(0, lambda: self.login_status.config(text="🟢 已登录", bootstyle=SUCCESS));
            self.status_var.set("✅ 登录成功，正在加载课表...")
            self.root.after(100, self.jump_to_current_week)
        except requests.exceptions.RequestException as e:
            self.log_message(f"网络连接错误: {e}", "error");
            self.root.after(0, lambda: self.login_status.config(text="🔴 网络错误", bootstyle=DANGER));
            self.status_var.set("❌ 登录时网络错误")
        except Exception as e:
            self.log_message(f"登录时发生未知错误: {e}", "error");
            self.root.after(0, lambda: self.login_status.config(text="🔴 登录错误", bootstyle=DANGER));
            self.status_var.set("❌ 登录时发生未知错误")

    def calculate_week_dates(self, week_number):
        start_date = self.semester_start + datetime.timedelta(weeks=week_number - 1)
        return [start_date + datetime.timedelta(days=i) for i in range(7)]

    def get_current_week(self):
        return max(1, min(18, (datetime.datetime.now() - self.semester_start).days // 7 + 1))

    def jump_to_current_week(self):
        self.week_var.set(f"第 {self.get_current_week()} 周");
        self.load_week_courses()

    def previous_week(self):
        current_week = int(self.week_var.get().split()[1])
        if current_week > 1: self.week_var.set(f"第 {current_week - 1} 周"); self.load_week_courses()

    def next_week(self):
        current_week = int(self.week_var.get().split()[1])
        if current_week < 18: self.week_var.set(f"第 {current_week + 1} 周"); self.load_week_courses()

    def load_week_courses(self):
        if not self.userId: messagebox.showwarning("警告", "请先登录系统"); return
        threading.Thread(target=self._execute_load_courses, daemon=True).start()

    def _execute_load_courses(self):
        try:
            week_number = int(self.week_var.get().split()[1])
            week_dates = self.calculate_week_dates(week_number)
            self.status_var.set(f"🔄 正在加载第 {week_number} 周课表...");
            self.log_message(f"开始加载第 {week_number} 周课表", "info")
            self.root.after(0, self._clear_course_display)
            self.root.after(0, lambda: self._update_week_headers(week_dates))
            for day_idx, date in enumerate(week_dates): self.fetch_day_courses(day_idx, date.strftime('%Y%m%d'))
            self.status_var.set(f"✅ 第 {week_number} 周课表加载完成");
            self.log_message(f"第 {week_number} 周课表加载完成", "success")
            self.root.after(100, lambda: self.course_canvas.configure(scrollregion=self.course_canvas.bbox("all")))
        except Exception as e:
            self.log_message(f"加载课表时发生错误: {e}", "error");
            self.status_var.set("❌ 课表加载失败")

    def _clear_course_display(self):
        for header in self.day_headers_frame.winfo_children(): header.destroy()
        for day_frame in self.day_frames:
            for widget in day_frame.winfo_children(): widget.destroy()

    def _update_week_headers(self, week_dates):
        days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        for i, date in enumerate(week_dates):
            is_today = date.date() == datetime.date.today()
            header_style, text_style = ("primary", "inverse-primary") if is_today else ("light", "dark")
            header_card = ttk.Frame(self.day_headers_frame, padding=8, bootstyle=header_style, relief="raised",
                                    borderwidth=1)
            header_card.grid(row=0, column=i, sticky="ew", padx=5)
            ttk.Label(header_card, text=days[i], font=("微软雅黑", 12, "bold"), bootstyle=text_style).pack()
            ttk.Label(header_card, text=date.strftime("%m-%d"), font=("微软雅黑", 9), bootstyle=text_style).pack()

    def fetch_day_courses(self, day_idx, date_str):
        try:
            json_data = self.get_course_schedule(date_str)
            courses = json_data.get('result', []) if json_data and json_data.get('STATUS') == '0' else []
            self.root.after(0, lambda: self.display_day_courses(day_idx, courses))
        except Exception as e:
            self.log_message(f"获取 {date_str} 课程时发生错误: {e}", "error")

    def get_course_schedule(self, dateStr):
        try:
            url, params, headers = f'https://iclass.buaa.edu.cn:8346/app/course/get_stu_course_sched.action', {
                'dateStr': dateStr, 'id': self.userId}, {'sessionId': self.sessionId}
            res = requests.get(url, params=params, headers=headers, timeout=10)
            return res.json() if res.status_code == 200 else None
        except requests.exceptions.RequestException as e:
            self.log_message(f"网络请求失败: {e}", "error");
            return None

    def display_day_courses(self, day_idx, courses):
        day_frame = self.day_frames[day_idx]
        if not courses:
            ttk.Label(day_frame, text="🎉\n无课程安排", bootstyle="secondary", font=("微软雅黑", 10),
                      justify=CENTER).pack(pady=50, fill=X)
            return
        for course in courses:
            CourseCard(day_frame, course,
                       lambda cid=course['id'], name=course['courseName']: self.sign_course(cid, name)).pack(fill=X,
                                                                                                             pady=5)

    def sign_course(self, course_sched_id, course_name):
        threading.Thread(target=self._execute_sign, args=(course_sched_id, course_name), daemon=True).start()

    def _execute_sign(self, course_sched_id, course_name):
        self.status_var.set(f"🔄 正在为 {course_name} 打卡...");
        self.log_message(f"开始打卡: {course_name}", "info")
        try:
            if self.sign_course_request(course_sched_id):
                self.log_message(f"打卡成功: {course_name}", "success");
                self.status_var.set(f"✅ 打卡成功: {course_name}")
                self.root.after(0, lambda: messagebox.showinfo("成功", f"{course_name} 打卡成功！"))
            else:
                self.log_message(f"打卡失败: {course_name}", "error");
                self.status_var.set(f"❌ 打卡失败: {course_name}")
                self.root.after(0, lambda: messagebox.showerror("错误",
                                                                f"{course_name} 打卡失败！\n可能是重复打卡或不在有效时间内。"))
        except Exception as e:
            self.log_message(f"打卡过程发生错误: {e}", "error");
            self.status_var.set("❌ 打卡过程出错")
            self.root.after(0, lambda: messagebox.showerror("错误", f"打卡过程发生错误: {e}"))

    def batch_sign_week(self):
        if not self.userId: messagebox.showwarning("警告", "请先登录系统"); return
        threading.Thread(target=self._execute_batch_sign, daemon=True).start()

    def _execute_batch_sign(self):
        try:
            week_number = int(self.week_var.get().split()[1])
            self.status_var.set(f"🔄 正在一键打卡第 {week_number} 周...");
            self.log_message(f"开始一键打卡第 {week_number} 周所有课程", "info")
            all_courses = [course for date in self.calculate_week_dates(week_number) for course in
                           (self.get_course_schedule(date.strftime('%Y%m%d')) or {}).get('result', [])]
            total, success = len(all_courses), 0
            for i, course in enumerate(all_courses):
                self.status_var.set(f"🔄 ({i + 1}/{total}): {truncate_text(course['courseName'], 20)}")
                if self.sign_course_request(course['id']):
                    self.log_message(f"打卡成功: {course['courseName']}", "success"); success += 1
                else:
                    self.log_message(f"打卡失败: {course['courseName']} (可能已打卡)", "warning")
                time.sleep(0.2)
            summary = f"一键打卡完成: 成功 {success} / {total} 门课程"
            self.status_var.set(f"✅ {summary}");
            self.log_message(summary, "success" if success == total else "warning")
            self.root.after(0, lambda: messagebox.showinfo("完成", summary))
        except Exception as e:
            self.log_message(f"一键打卡时发生错误: {e}", "error");
            self.status_var.set("❌ 一键打卡失败")

    def sign_course_request(self, courseSchedId):
        try:
            params, url = {
                'id': self.userId}, f'http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action?courseSchedId={courseSchedId}&timestamp={int(time.time() * 1000)}'
            r = requests.post(url, params=params, timeout=10)
            if r.status_code == 200:
                try:
                    return r.json().get('STATUS') == '0'
                except json.JSONDecodeError:
                    return '成功' in r.text or 'SUCCESS' in r.text
            return False
        except requests.exceptions.RequestException as e:
            self.log_message(f"打卡网络请求失败: {e}", "error");
            return False

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = CourseSignApp()
    app.run()