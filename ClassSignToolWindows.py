import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import requests
import json
import time
import datetime
import threading
from tkinter import messagebox, scrolledtext


class CourseSignApp:
    def __init__(self):
        self.userId = None
        self.sessionId = None
        self.current_week_courses = {}
        # 北航2024-2025学年秋季学期开始日期
        self.semester_start = datetime.datetime(2024, 9, 2)

        # 创建主窗口
        self.root = ttk.Window(
            title="北航课程打卡系统",
            themename="minty",
            size=(1400, 850),
            position=(50, 50),
            resizable=(True, True)
        )

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        # 标题区域
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 25))

        title_label = ttk.Label(
            header_frame,
            text="✈️ 北航课程打卡系统",
            font=("微软雅黑", 22, "bold"),
            bootstyle=PRIMARY
        )
        title_label.pack(side=LEFT)

        # 登录状态
        self.login_status = ttk.Label(
            header_frame,
            text="🔴 未登录",
            bootstyle=DANGER,
            font=("微软雅黑", 12)
        )
        self.login_status.pack(side=RIGHT, padx=(0, 10))

        # 创建内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=BOTH, expand=True)

        # 左侧控制面板
        control_panel = ttk.Labelframe(content_frame, text="控制面板", width=280, padding=15)
        control_panel.pack(side=LEFT, fill=Y, padx=(0, 20))
        control_panel.pack_propagate(False)

        # 右侧内容区域
        content_panel = ttk.Frame(content_frame)
        content_panel.pack(side=RIGHT, fill=BOTH, expand=True)

        # 设置控制面板内容
        self.setup_control_panel(control_panel)

        # 设置内容面板
        self.setup_content_panel(content_panel)

        # 状态栏
        self.status_var = tk.StringVar(value="👋 欢迎使用北航课程打卡系统")
        status_bar = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            relief=SUNKEN,
            anchor=W,
            font=("微软雅黑", 10)
        )
        status_bar.pack(fill=X, pady=(20, 0))

    def setup_control_panel(self, parent):
        """设置控制面板"""
        # 学号输入
        ttk.Label(parent, text="学号:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 8))
        self.student_id_var = tk.StringVar()
        student_id_entry = ttk.Entry(
            parent,
            textvariable=self.student_id_var,
            font=("微软雅黑", 11),
            width=22
        )
        student_id_entry.pack(fill=X, pady=(0, 20))

        # 学期设置
        ttk.Label(parent, text="学期设置:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 8))

        # 学期开始日期选择 - 使用简单的输入框
        date_frame = ttk.Frame(parent)
        date_frame.pack(fill=X, pady=(0, 15))

        ttk.Label(date_frame, text="第一周周一:", font=("微软雅黑", 10)).pack(anchor=W)

        # 使用简单的输入框代替DateEntry
        date_input_frame = ttk.Frame(date_frame)
        date_input_frame.pack(fill=X, pady=(5, 0))

        # 年
        self.year_var = tk.StringVar(value="2024")
        year_entry = ttk.Entry(
            date_input_frame,
            textvariable=self.year_var,
            font=("微软雅黑", 9),
            width=6
        )
        year_entry.pack(side=LEFT, padx=(0, 5))
        ttk.Label(date_input_frame, text="年", font=("微软雅黑", 9)).pack(side=LEFT, padx=(0, 10))

        # 月
        self.month_var = tk.StringVar(value="9")
        month_combo = ttk.Combobox(
            date_input_frame,
            textvariable=self.month_var,
            values=[str(i) for i in range(1, 13)],
            state="readonly",
            font=("微软雅黑", 9),
            width=4
        )
        month_combo.pack(side=LEFT, padx=(0, 5))
        ttk.Label(date_input_frame, text="月", font=("微软雅黑", 9)).pack(side=LEFT, padx=(0, 10))

        # 日
        self.day_var = tk.StringVar(value="2")
        day_combo = ttk.Combobox(
            date_input_frame,
            textvariable=self.day_var,
            values=[str(i) for i in range(1, 32)],
            state="readonly",
            font=("微软雅黑", 9),
            width=4
        )
        day_combo.pack(side=LEFT, padx=(0, 5))
        ttk.Label(date_input_frame, text="日", font=("微软雅黑", 9)).pack(side=LEFT)

        # 登录按钮
        login_btn = ttk.Button(
            parent,
            text="🚀 登录系统",
            command=self.login,
            bootstyle=SUCCESS,
            width=22
        )
        login_btn.pack(fill=X, pady=(10, 20))

        # 分隔线
        ttk.Separator(parent, bootstyle=SECONDARY).pack(fill=X, pady=(0, 20))

        # 周数选择
        ttk.Label(parent, text="选择周数:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 10))

        self.week_var = tk.StringVar(value="第 1 周")

        # 创建自定义样式的周数选择器
        week_frame = ttk.Frame(parent)
        week_frame.pack(fill=X, pady=(0, 15))

        # 周数下拉框
        week_combo = ttk.Combobox(
            week_frame,
            textvariable=self.week_var,
            values=[f"第 {i} 周" for i in range(1, 19)],
            state="readonly",
            font=("微软雅黑", 11),
            height=12
        )
        week_combo.pack(fill=X)
        week_combo.bind('<<ComboboxSelected>>', lambda e: self.load_week_courses())

        # 周数导航按钮
        nav_frame = ttk.Frame(parent)
        nav_frame.pack(fill=X, pady=(0, 15))

        ttk.Button(
            nav_frame,
            text="◀ 上一周",
            command=self.previous_week,
            bootstyle=OUTLINE,
            width=10
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            nav_frame,
            text="下一周 ▶",
            command=self.next_week,
            bootstyle=OUTLINE,
            width=10
        ).pack(side=RIGHT)

        # 刷新按钮
        refresh_btn = ttk.Button(
            parent,
            text="🔄 刷新课表",
            command=self.load_week_courses,
            bootstyle=INFO,
            width=22
        )
        refresh_btn.pack(fill=X, pady=(0, 20))

        # 快速操作区域
        ttk.Label(parent, text="快速操作:", font=("微软雅黑", 12, "bold")).pack(anchor=W, pady=(0, 10))

        # 当前周按钮
        current_week_btn = ttk.Button(
            parent,
            text="📅 跳转到当前周",
            command=self.jump_to_current_week,
            bootstyle=OUTLINE,
            width=22
        )
        current_week_btn.pack(fill=X, pady=(0, 10))

        # 一键打卡按钮
        batch_sign_btn = ttk.Button(
            parent,
            text="✅ 一键打卡本周",
            command=self.batch_sign_week,
            bootstyle=WARNING,
            width=22
        )
        batch_sign_btn.pack(fill=X, pady=(0, 10))

    def setup_content_panel(self, parent):
        """设置内容面板"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=BOTH, expand=True)

        # 周视图标签页
        week_view_frame = ttk.Frame(notebook, padding=15)
        notebook.add(week_view_frame, text="📅 周视图")

        self.setup_week_view(week_view_frame)

        # 日志标签页
        log_frame = ttk.Frame(notebook, padding=15)
        notebook.add(log_frame, text="📝 操作日志")

        self.setup_log_view(log_frame)

    def setup_week_view(self, parent):
        """设置周视图"""
        # 创建星期标题 - 使用更现代的设计
        days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        day_frame = ttk.Frame(parent)
        day_frame.pack(fill=X, pady=(0, 15))

        for i, day in enumerate(days):
            # 创建带阴影效果的标题卡片
            day_card = ttk.Frame(
                day_frame,
                relief=RAISED,
                borderwidth=1,
                padding=12
            )
            day_card.grid(row=0, column=i, sticky="ew", padx=2)
            day_frame.columnconfigure(i, weight=1)

            day_label = ttk.Label(
                day_card,
                text=day,
                anchor=CENTER,
                font=("微软雅黑", 12, "bold"),
                bootstyle=INVERSE,
                padding=5
            )
            day_label.pack(fill=BOTH, expand=True)

        # 课程内容区域 - 使用现代化卡片设计
        self.course_container = ttk.Frame(parent)
        self.course_container.pack(fill=BOTH, expand=True)

        # 初始化课程网格
        self.day_frames = []
        for i in range(7):
            # 使用Labelframe创建更美观的日容器
            day_courses = ttk.Labelframe(
                self.course_container,
                text="",  # 空文本，我们会在后面添加日期
                padding=8,
                bootstyle="secondary"
            )
            day_courses.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.course_container.columnconfigure(i, weight=1)
            self.day_frames.append(day_courses)

    def setup_log_view(self, parent):
        """设置日志视图"""
        self.log_text = scrolledtext.ScrolledText(
            parent,
            wrap=WORD,
            width=80,
            height=25,
            font=("Consolas", 10),
            bg="#f8f9fa",
            relief=FLAT
        )
        self.log_text.pack(fill=BOTH, expand=True)
        self.log_text.config(state=DISABLED)

    def log_message(self, message, message_type="info"):
        """添加日志消息"""
        self.log_text.config(state=NORMAL)

        # 根据消息类型设置图标和颜色
        icons = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️"
        }

        colors = {
            "success": "#28a745",
            "error": "#dc3545",
            "warning": "#ffc107",
            "info": "#17a2b8"
        }

        icon = icons.get(message_type, "ℹ️")
        color = colors.get(message_type, "#17a2b8")

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        # 创建标签
        tag_name = f"tag_{message_type}"
        self.log_text.tag_config(tag_name, foreground=color)

        self.log_text.insert(END, f"[{timestamp}] {icon} ", "info")
        self.log_text.insert(END, f"{message}\n", tag_name)
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

    def validate_input(self):
        """验证输入"""
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showerror("输入错误", "请输入学号")
            return False
        if not student_id.isdigit():
            messagebox.showerror("输入错误", "学号必须是数字")
            return False

        # 验证日期输入
        try:
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            day = int(self.day_var.get())
            datetime.datetime(year, month, day)
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的日期")
            return False

        return True

    def get_semester_start_date(self):
        """获取学期开始日期"""
        try:
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            day = int(self.day_var.get())
            return datetime.datetime(year, month, day)
        except ValueError:
            # 如果日期无效，使用默认日期
            return datetime.datetime(2024, 9, 2)

    def login(self):
        """登录系统"""
        if not self.validate_input():
            return

        def do_login():
            self.status_var.set("🔄 正在登录...")
            self.login_status.config(text="🟡 登录中...", bootstyle=WARNING)

            try:
                student_id = self.student_id_var.get().strip()

                url = 'https://iclass.buaa.edu.cn:8346/app/user/login.action'
                para = {
                    'password': '',  # 不需要密码
                    'phone': student_id,
                    'userLevel': '1',
                    'verificationType': '2',
                    'verificationUrl': ''
                }

                res = requests.get(url=url, params=para, timeout=10)
                userData = json.loads(res.text)

                if userData.get('STATUS') != '0':
                    error_msg = userData.get('ERRORMSG', '未知错误')
                    self.log_message(f"登录失败: {error_msg}", "error")
                    self.login_status.config(text="🔴 登录失败", bootstyle=DANGER)
                    self.status_var.set("❌ 登录失败")
                    return

                self.userId = userData['result']['id']
                self.sessionId = userData['result']['sessionId']

                # 更新学期开始日期
                self.semester_start = self.get_semester_start_date()

                self.log_message(f"登录成功! 用户ID: {self.userId}", "success")
                self.login_status.config(text="🟢 已登录", bootstyle=SUCCESS)
                self.status_var.set("✅ 登录成功，正在加载课表...")

                # 登录成功后加载当前周课表
                self.root.after(100, self.jump_to_current_week)

            except Exception as e:
                self.log_message(f"登录错误: {str(e)}", "error")
                self.login_status.config(text="🔴 登录错误", bootstyle=DANGER)
                self.status_var.set("❌ 登录错误")

        # 在新线程中执行登录
        threading.Thread(target=do_login, daemon=True).start()

    def calculate_week_dates(self, week_number):
        """计算指定周数的日期范围"""
        # 计算指定周数的周一日期
        start_date = self.semester_start + datetime.timedelta(weeks=week_number - 1)

        # 计算一周的日期（周一到周日）
        week_dates = []
        for i in range(7):
            current_date = start_date + datetime.timedelta(days=i)
            week_dates.append(current_date)

        return week_dates

    def get_current_week(self):
        """获取当前周数"""
        today = datetime.datetime.now()
        delta = today - self.semester_start
        current_week = delta.days // 7 + 1
        return max(1, min(18, current_week))  # 限制在1-18周范围内

    def jump_to_current_week(self):
        """跳转到当前周"""
        current_week = self.get_current_week()
        self.week_var.set(f"第 {current_week} 周")
        self.load_week_courses()

    def previous_week(self):
        """切换到上一周"""
        current_week = int(self.week_var.get().split()[1])
        if current_week > 1:
            self.week_var.set(f"第 {current_week - 1} 周")
            self.load_week_courses()

    def next_week(self):
        """切换到下一周"""
        current_week = int(self.week_var.get().split()[1])
        if current_week < 18:
            self.week_var.set(f"第 {current_week + 1} 周")
            self.load_week_courses()

    def load_week_courses(self):
        """加载指定周数的课程"""
        if not self.userId or not self.sessionId:
            messagebox.showwarning("警告", "请先登录系统")
            return

        def load_courses():
            try:
                week_number = int(self.week_var.get().split()[1])
                week_dates = self.calculate_week_dates(week_number)

                self.status_var.set(f"🔄 正在加载第{week_number}周课表...")
                self.log_message(f"开始加载第{week_number}周课表", "info")

                # 清空现有课程显示
                for day_frame in self.day_frames:
                    for widget in day_frame.winfo_children():
                        widget.destroy()

                # 添加日期标签
                for day_idx, date in enumerate(week_dates):
                    # 设置日期标题
                    self.day_frames[day_idx].configure(text=date.strftime("%m月%d日"))

                    # 添加星期标签
                    weekday_label = ttk.Label(
                        self.day_frames[day_idx],
                        text=date.strftime("%A"),
                        font=("微软雅黑", 10, "bold"),
                        anchor=CENTER,
                        bootstyle=INVERSE if date.date() == datetime.datetime.now().date() else SECONDARY,
                        padding=5
                    )
                    weekday_label.pack(fill=X, pady=(0, 10))

                # 获取每周课程
                for day_idx, date in enumerate(week_dates):
                    date_str = date.strftime('%Y%m%d')
                    self.fetch_day_courses(day_idx, date, date_str)

                self.status_var.set(f"✅ 第{week_number}周课表加载完成")
                self.log_message(f"第{week_number}周课表加载完成", "success")

            except Exception as e:
                self.log_message(f"加载课表错误: {str(e)}", "error")
                self.status_var.set("❌ 课表加载失败")

        threading.Thread(target=load_courses, daemon=True).start()

    def fetch_day_courses(self, day_idx, date, date_str):
        """获取某天的课程并显示"""
        try:
            json_data = self.get_course_schedule(date_str)

            if json_data and json_data['STATUS'] == '0' and 'result' in json_data:
                courses = json_data['result']

                # 在主线程中更新UI
                self.root.after(0, lambda: self.display_day_courses(day_idx, date, courses))
            else:
                error_msg = json_data.get('ERRORMSG', '未知错误') if json_data else '获取失败'
                self.log_message(f"{date_str} 获取课程失败: {error_msg}", "warning")

        except Exception as e:
            self.log_message(f"获取{date_str}课程错误: {str(e)}", "error")

    def get_course_schedule(self, dateStr):
        """获取指定日期的课程表"""
        url = 'https://iclass.buaa.edu.cn:8346/app/course/get_stu_course_sched.action'
        para = {
            'dateStr': dateStr,
            'id': self.userId
        }
        headers = {
            'sessionId': self.sessionId,
        }

        try:
            res = requests.get(url=url, params=para, headers=headers, timeout=10)
            return json.loads(res.text)
        except Exception as e:
            self.log_message(f"网络请求失败: {str(e)}", "error")
            return None

    def display_day_courses(self, day_idx, date, courses):
        """显示某天的课程"""
        day_frame = self.day_frames[day_idx]

        if not courses:
            no_course_label = ttk.Label(
                day_frame,
                text="🎉 今天没有课程",
                foreground="gray",
                font=("微软雅黑", 11),
                anchor=CENTER,
                padding=20
            )
            no_course_label.pack(fill=BOTH, expand=True)
            return

        # 显示课程 - 使用现代化卡片设计
        for course in courses:
            # 创建课程卡片 - 使用更现代的设计
            course_card = ttk.Frame(
                day_frame,
                relief=RAISED,
                borderwidth=1,
                padding=12
            )
            course_card.pack(fill=X, pady=6, padx=2)

            course_name = course['courseName']
            class_begin = course['classBeginTime'][11:16]
            class_end = course['classEndTime'][11:16]
            course_sched_id = course['id']
            location = course.get('classroomName', '未知地点')
            teacher = course.get('teacherName', '未知教师')

            # 课程标题 - 更突出的设计
            title_frame = ttk.Frame(course_card)
            title_frame.pack(fill=X, pady=(0, 10))

            title_label = ttk.Label(
                title_frame,
                text=course_name,
                font=("微软雅黑", 11, "bold"),
                anchor=W,
                bootstyle=PRIMARY
            )
            title_label.pack(side=LEFT, fill=X, expand=True)

            # 时间标签
            time_label = ttk.Label(
                title_frame,
                text=f"{class_begin}-{class_end}",
                font=("微软雅黑", 10, "bold"),
                bootstyle=SUCCESS
            )
            time_label.pack(side=RIGHT)

            # 课程详情 - 使用图标和文字并排布局
            details_frame = ttk.Frame(course_card)
            details_frame.pack(fill=X, pady=(0, 12))

            # 第一行：地点和教师
            info_frame = ttk.Frame(details_frame)
            info_frame.pack(fill=X, pady=(0, 8))

            # 地点信息
            location_frame = ttk.Frame(info_frame)
            location_frame.pack(side=LEFT, fill=X, expand=True)

            ttk.Label(
                location_frame,
                text="📍",
                font=("微软雅黑", 10)
            ).pack(side=LEFT)

            ttk.Label(
                location_frame,
                text=location,
                font=("微软雅黑", 9)
            ).pack(side=LEFT, padx=(5, 0))

            # 教师信息
            teacher_frame = ttk.Frame(info_frame)
            teacher_frame.pack(side=RIGHT)

            ttk.Label(
                teacher_frame,
                text="👨‍🏫",
                font=("微软雅黑", 10)
            ).pack(side=LEFT)

            ttk.Label(
                teacher_frame,
                text=teacher,
                font=("微软雅黑", 9)
            ).pack(side=LEFT, padx=(5, 0))

            # 打卡按钮 - 更醒目的设计
            sign_btn = ttk.Button(
                course_card,
                text="✅ 课程打卡",
                bootstyle=SUCCESS,
                command=lambda cid=course_sched_id, name=course_name: self.sign_course(cid, name),
                width=20
            )
            sign_btn.pack(fill=X, pady=(5, 0))

    def sign_course(self, course_sched_id, course_name):
        """课程打卡"""

        def do_sign():
            try:
                self.status_var.set(f"🔄 正在为 {course_name} 打卡...")
                self.log_message(f"开始打卡: {course_name}", "info")

                success = self.sign_course_request(course_sched_id)

                if success:
                    self.log_message(f"打卡成功: {course_name}", "success")
                    self.status_var.set(f"✅ 打卡成功: {course_name}")
                    messagebox.showinfo("成功", f"{course_name} 打卡成功！")
                else:
                    self.log_message(f"打卡失败: {course_name}", "error")
                    self.status_var.set(f"❌ 打卡失败: {course_name}")
                    messagebox.showerror("错误", f"{course_name} 打卡失败！")

            except Exception as e:
                error_msg = f"打卡过程错误: {str(e)}"
                self.log_message(error_msg, "error")
                self.status_var.set("❌ 打卡过程出错")
                messagebox.showerror("错误", error_msg)

        threading.Thread(target=do_sign, daemon=True).start()

    def batch_sign_week(self):
        """一键打卡本周所有课程"""
        if not self.userId or not self.sessionId:
            messagebox.showwarning("警告", "请先登录系统")
            return

        def do_batch_sign():
            try:
                week_number = int(self.week_var.get().split()[1])
                week_dates = self.calculate_week_dates(week_number)

                self.status_var.set(f"🔄 正在一键打卡第{week_number}周所有课程...")
                self.log_message(f"开始一键打卡第{week_number}周所有课程", "info")

                total_courses = 0
                success_count = 0

                for date in week_dates:
                    date_str = date.strftime('%Y%m%d')
                    json_data = self.get_course_schedule(date_str)

                    if json_data and json_data['STATUS'] == '0' and 'result' in json_data:
                        courses = json_data['result']
                        total_courses += len(courses)

                        for course in courses:
                            course_sched_id = course['id']
                            course_name = course['courseName']

                            if self.sign_course_request(course_sched_id):
                                self.log_message(f"打卡成功: {course_name}", "success")
                                success_count += 1
                            else:
                                self.log_message(f"打卡失败: {course_name}", "error")

                self.status_var.set(f"✅ 一键打卡完成: {success_count}/{total_courses} 成功")
                self.log_message(f"一键打卡完成: 成功 {success_count}/{total_courses} 门课程",
                                 "success" if success_count == total_courses else "warning")

            except Exception as e:
                self.log_message(f"一键打卡错误: {str(e)}", "error")
                self.status_var.set("❌ 一键打卡失败")

        threading.Thread(target=do_batch_sign, daemon=True).start()

    def sign_course_request(self, courseSchedId):
        """执行课程打卡请求"""
        params = {
            'id': self.userId
        }
        current_timestamp_milliseconds = int(time.time() * 1000)
        url = f'http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action?courseSchedId={courseSchedId}&timestamp={current_timestamp_milliseconds}'

        try:
            r = requests.post(url=url, params=params, timeout=10)
            return r.ok
        except Exception as e:
            self.log_message(f"打卡请求失败: {str(e)}", "error")
            return False

    def run(self):
        """运行应用程序"""
        self.root.mainloop()


def main():
    app = CourseSignApp()
    app.run()


if __name__ == "__main__":
    main()