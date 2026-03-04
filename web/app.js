/**
 * 北航课程打卡系统 — 前端逻辑
 */

const app = {
    currentWeek: 1,
    logOpen: false,
    isLoggedIn: false,

    $(id) { return document.getElementById(id); },

    getSemester() {
        return {
            year: this.$('yearInput').value,
            month: this.$('monthInput').value,
            day: this.$('dayInput').value
        };
    },

    toast(msg, type = '') {
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = msg;
        this.$('toastContainer').appendChild(el);
        setTimeout(() => {
            el.style.animation = 'toast-out 0.3s ease forwards';
            setTimeout(() => el.remove(), 300);
        }, 3000);
    },

    log(msg, type = 'info') {
        const body = this.$('logBody');
        const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `<span class="log-time">${time}</span><span class="log-msg ${type}">${msg}</span>`;
        body.appendChild(entry);
        body.scrollTop = body.scrollHeight;
    },

    showLoading(show) {
        this.$('loadingOverlay').style.display = show ? 'flex' : 'none';
    },

    truncate(text, max) {
        return text && text.length > max ? text.slice(0, max - 1) + '…' : text;
    },

    // --- Login ---
    async login() {
        const studentId = this.$('studentId').value.trim();
        if (!studentId) {
            this.toast('请输入学号', 'error');
            return;
        }

        const btn = this.$('loginBtn');
        const status = this.$('loginStatus');
        btn.disabled = true;
        btn.textContent = '登录中…';
        status.textContent = '';
        status.className = 'status-text';

        try {
            const result = await window.pywebview.api.login(studentId);
            if (result.success) {
                this.isLoggedIn = true;
                status.textContent = `已登录 · ${result.userId}`;
                status.className = 'status-text success';
                this.log('登录成功', 'success');
                this.toast('登录成功');

                // 切换按钮状态
                btn.style.display = 'none';
                this.$('logoutBtn').style.display = 'block';
                this.$('studentId').disabled = true;
                this.$('yearInput').disabled = true;
                this.$('monthInput').disabled = true;
                this.$('dayInput').disabled = true;

                // 显示周数面板和统计
                this.$('weekPanel').style.display = 'block';
                this.$('statsPanel').style.display = 'flex';

                // 跳转当前周
                const sem = this.getSemester();
                const week = await window.pywebview.api.get_current_week(sem.year, sem.month, sem.day);
                this.currentWeek = week;
                this.updateWeekDisplay();
                this.loadWeek();
            } else {
                status.textContent = result.error;
                status.className = 'status-text error';
                this.log(`登录失败: ${result.error}`, 'error');
                this.toast('登录失败', 'error');
                btn.disabled = false;
                btn.textContent = '登录';
            }
        } catch (e) {
            status.textContent = '网络异常';
            status.className = 'status-text error';
            this.log(`登录异常: ${e}`, 'error');
            btn.disabled = false;
            btn.textContent = '登录';
        }
    },

    // --- Logout ---
    logout() {
        this.isLoggedIn = false;

        // 恢复登录区
        const btn = this.$('loginBtn');
        btn.style.display = 'block';
        btn.disabled = false;
        btn.textContent = '登录';
        this.$('logoutBtn').style.display = 'none';
        this.$('studentId').disabled = false;
        this.$('yearInput').disabled = false;
        this.$('monthInput').disabled = false;
        this.$('dayInput').disabled = false;
        this.$('loginStatus').textContent = '';
        this.$('loginStatus').className = 'status-text';

        // 隐藏周数和统计
        this.$('weekPanel').style.display = 'none';
        this.$('statsPanel').style.display = 'none';

        // 显示欢迎页
        this.$('welcomeView').style.display = 'flex';
        this.$('scheduleView').style.display = 'none';

        this.log('已退出登录', 'warning');
        this.toast('已退出登录');
    },

    // --- Week Navigation ---
    updateWeekDisplay() {
        this.$('weekDisplay').textContent = `第 ${this.currentWeek} 周`;
    },

    prevWeek() {
        if (this.currentWeek > 1) {
            this.currentWeek--;
            this.updateWeekDisplay();
            this.loadWeek();
        }
    },

    nextWeek() {
        if (this.currentWeek < 18) {
            this.currentWeek++;
            this.updateWeekDisplay();
            this.loadWeek();
        }
    },

    async jumpToCurrentWeek() {
        const sem = this.getSemester();
        this.currentWeek = await window.pywebview.api.get_current_week(sem.year, sem.month, sem.day);
        this.updateWeekDisplay();
        this.loadWeek();
    },

    // --- Load Week ---
    async loadWeek() {
        this.showLoading(true);
        this.$('welcomeView').style.display = 'none';
        this.$('scheduleView').style.display = 'block';
        this.log(`加载第 ${this.currentWeek} 周课表…`);

        const sem = this.getSemester();
        try {
            const data = await window.pywebview.api.get_week_courses(
                this.currentWeek, sem.year, sem.month, sem.day
            );
            this.renderSchedule(data);
            this.log(`第 ${this.currentWeek} 周加载完成`, 'success');
        } catch (e) {
            this.log(`加载失败: ${e}`, 'error');
            this.toast('课表加载失败', 'error');
        }
        this.showLoading(false);
    },

    // --- Render ---
    renderSchedule(data) {
        const grid = this.$('scheduleGrid');
        grid.innerHTML = '';

        let totalCourses = 0;
        let signedCourses = 0;

        for (let i = 0; i < 7; i++) {
            const dayData = data[String(i)];
            const col = document.createElement('div');
            col.className = 'day-column';

            const coursesCount = dayData.courses.length;
            const daySigned = dayData.courses.filter(c => String(c.signStatus) === '1').length;
            totalCourses += coursesCount;
            signedCourses += daySigned;

            const statText = coursesCount > 0 ? `${coursesCount}课 · ${daySigned}签` : '无课';

            const header = document.createElement('div');
            header.className = `day-header${dayData.isToday ? ' is-today' : ''}`;
            header.innerHTML = `
                <div class="day-name">${dayData.weekday}</div>
                <div class="day-date">${dayData.date}</div>
                <div class="day-stat">${statText}</div>
            `;
            col.appendChild(header);

            const body = document.createElement('div');
            body.className = 'day-body';

            if (coursesCount === 0) {
                body.innerHTML = '<div class="empty-day">无课程</div>';
            } else {
                const sorted = dayData.courses.sort((a, b) =>
                    (a.classBeginTime || '').localeCompare(b.classBeginTime || '')
                );
                sorted.forEach(course => body.appendChild(this.createCourseCard(course)));
            }
            col.appendChild(body);
            grid.appendChild(col);
        }

        this.$('totalCourses').textContent = totalCourses;
        this.$('signedCourses').textContent = signedCourses;
    },

    createCourseCard(course) {
        const card = document.createElement('div');
        const isSigned = String(course.signStatus) === '1';
        card.className = `course-card ${isSigned ? 'signed' : 'unsigned'}`;

        const name = course.courseName || '未知课程';
        const begin = (course.classBeginTime || '').slice(11, 16);
        const end = (course.classEndTime || '').slice(11, 16);
        const classroom = course.classroomName || '';
        const building = (course.teachBuildName || '').trim();
        const storey = (course.storeyName || '').trim();
        const courseType = course.courseType || '';
        const teachers = course.teachers || [course.teacherName || '未知'];

        const locParts = [building, storey, classroom].filter(p => p && p !== 'null');
        const location = locParts.join(' ') || '未知';

        let teacherText;
        if (teachers.length === 1) teacherText = teachers[0];
        else if (teachers.length <= 2) teacherText = teachers.join(' / ');
        else teacherText = `${teachers[0]} 等${teachers.length}人`;

        const ids = JSON.stringify(course.courseSchedIds || [course.id]);
        const escapedIds = ids.replace(/"/g, '&quot;');
        const escapedName = name.replace(/'/g, "\\'");

        card.innerHTML = `
            <div class="card-header">
                <span class="course-name">${this.truncate(name, 18)}</span>
                <span class="sign-badge ${isSigned ? 'signed' : 'unsigned'}">${isSigned ? '已签' : '未签'}</span>
            </div>
            <div class="card-meta">
                <span>${begin}–${end} · ${courseType}</span>
                <span>${this.truncate(location, 16)}</span>
                <span>${teacherText}</span>
            </div>
            <div class="card-action">
                <button class="btn-sign ${isSigned ? 'signed' : ''}"
                        onclick="${isSigned ? '' : `app.signCourse(${escapedIds}, '${escapedName}')`}"
                        title="${isSigned ? '已完成签到' : '点击签到'}">
                    ${isSigned ? '已签到' : '签到'}
                </button>
            </div>
        `;

        return card;
    },

    // --- Sign ---
    async signCourse(ids, name) {
        this.log(`签到: ${name}…`);
        this.toast(`正在签到…`);

        try {
            const result = await window.pywebview.api.sign_course(JSON.stringify(ids));
            if (result.success > 0) {
                this.log(`签到成功: ${name} (${result.success}/${result.total})`, 'success');
                this.toast(`${name} 签到成功`, 'success');
                this.loadWeek();
            } else {
                this.log(`签到失败: ${name}`, 'error');
                this.toast(`签到失败`, 'error');
            }
        } catch (e) {
            this.log(`签到异常: ${e}`, 'error');
            this.toast('签到失败', 'error');
        }
    },

    async batchSign() {
        const sem = this.getSemester();
        this.log(`一键打卡第 ${this.currentWeek} 周…`);
        this.toast('正在一键打卡…');

        try {
            const result = await window.pywebview.api.batch_sign_week(
                this.currentWeek, sem.year, sem.month, sem.day
            );
            const msg = `完成: ${result.success}/${result.total}`;
            this.log(msg, result.success > 0 ? 'success' : 'warning');
            this.toast(msg, result.success > 0 ? 'success' : 'error');
            this.loadWeek();
        } catch (e) {
            this.log(`一键打卡异常: ${e}`, 'error');
            this.toast('一键打卡失败', 'error');
        }
    },

    // --- Log Drawer ---
    toggleLog() {
        this.logOpen = !this.logOpen;
        this.$('logDrawer').classList.toggle('open', this.logOpen);
    }
};

window.addEventListener('pywebviewready', () => {
    app.log('系统就绪');
    app.$('studentId').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') app.login();
    });
});
