/**
 * 北航课程助手 — 前端交互枢纽 / i18n
 */

const DICT = {
    'zh': {
        logoSub: '极简 · 高效',
        segDirect: '校园直连',
        segVpn: '校外穿透 (WebVPN)',
        lblUid: '学号',
        phUid: '输入学号',
        lblVpnTitle: '网络凭证 (cURL)',
        phCurl: '在此粘贴 cURL 指令...',
        lblSemester: '学期第一周 (年-月-日)',
        btnLoginDirect: '登 录',
        btnLoginVpn: '解析并登录',
        btnLogout: '退出登录',
        lblTimeCtrl: '时间控制',
        btnReset: '本周',
        btnReload: '刷新',
        btnBatch: '一键打卡',
        lblStatBlocks: '排课数',
        lblStatDone: '已签到',
        lblWelcomeTitle: 'BUAA 课程助手',
        lblWelcomeSub: '等待身份校验',
        tooltip: '在校外需进行凭证同步：\n1. 登录 d.buaa.edu.cn\n2. F12 打开网络 (Network) 标签\n3. 右键刷新后的请求 ➔ Copy ➔ Copy as cURL\n4. 粘贴至下方输入框',
        weekPrefix: '第 ',
        weekSuffix: ' 周',
        wkDays: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
        emptyDay: '今日无课',
        cardSign: '签到',
        cardDone: '已完成',
        cardBadgePending: '未签',
        cardBadgeDone: '已签',
        
        statBlocks: (total, done) => `${total} 节课 / 已签 ${done}`,
        // Log parts
        msgSysReady: '系统环境就绪。',
        msgLoginIssue: '正在申请鉴权...',
        msgLoginOk: '认证通过。',
        msgLogingOut: '注销指令已提交。',
        msgLoadFail: '数据解析遇阻:',
        msgBatchLaunch: '触发批量签到序列...',
        msgSignLaunch: '尝试签到区块:',
    },
    'en': {
        logoSub: 'Minimalism · Utility',
        segDirect: 'Direct Connection',
        segVpn: 'WebVPN Tunnel',
        lblUid: 'Student ID',
        phUid: 'Enter ID',
        lblVpnTitle: 'Auth Token (cURL)',
        phCurl: 'Paste cURL here...',
        lblSemester: 'Semester Pivot (Y-M-D)',
        btnLoginDirect: 'Sign In',
        btnLoginVpn: 'Parse & Connect',
        btnLogout: 'Sign Out',
        lblTimeCtrl: 'Time Frame',
        btnReset: 'Current',
        btnReload: 'Refresh',
        btnBatch: 'Execute All',
        lblStatBlocks: 'Blocks',
        lblStatDone: 'Verified',
        lblWelcomeTitle: 'Minimalism Sign.',
        lblWelcomeSub: 'Awaiting Authentication',
        tooltip: 'WebVPN tunneling requires Cookie syncing:\n1. Login via d.buaa.edu.cn\n2. Open DevTools (F12) -> Network\n3. Right-click any request -> Copy as cURL\n4. Paste payload here',
        weekPrefix: 'Week ',
        weekSuffix: '',
        wkDays: ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'],
        emptyDay: 'Null Reference',
        cardSign: 'EXECUTE',
        cardDone: 'VERIFIED',
        cardBadgePending: 'PENDING',
        cardBadgeDone: 'SIGNED',

        statBlocks: (total, done) => `${total} BLK / ${done} DONE`,
        msgSysReady: 'System Operational.',
        msgLoginIssue: 'Allocating Session...',
        msgLoginOk: 'Authentication Granted.',
        msgLogingOut: 'Session Terminated.',
        msgLoadFail: 'Operation Aborted:',
        msgBatchLaunch: 'Executing Batch Routine...',
        msgSignLaunch: 'Deploying block:',
    }
};

const app = {
    currentWeek: 1,
    isLoggedIn: false,
    mode: 'direct', 
    logOpen: false,
    lang: 'zh', // 'zh' or 'en'

    $(id) { return document.getElementById(id); },

    // ==========================================
    // Core Control
    // ==========================================
    toggleLang() {
        this.lang = this.lang === 'zh' ? 'en' : 'zh';
        this.$('langBtn').textContent = this.lang === 'zh' ? 'EN' : '中';
        this.applyLanguage();
        if (this.isLoggedIn) {
            this.updateWeekDisplay();
            this.loadWeek(); // Reload grid with new lang
        }
    },

    applyLanguage() {
        const d = DICT[this.lang];
        this.$('lblLogoSub').textContent = d.logoSub;
        this.$('segDirect').textContent = d.segDirect;
        this.$('segVpn').textContent = d.segVpn;
        this.$('lblUid').textContent = d.lblUid;
        this.$('studentId').placeholder = d.phUid;
        this.$('lblVpnTitle').textContent = d.lblVpnTitle;
        this.$('curlText').placeholder = d.phCurl;
        this.$('lblSemester').textContent = d.lblSemester;
        this.$('btnLogout').textContent = d.btnLogout;
        this.$('lblTimeCtrl').textContent = d.lblTimeCtrl;
        this.$('btnReset').textContent = d.btnReset;
        this.$('btnReload').textContent = d.btnReload;
        this.$('btnBatch').textContent = d.btnBatch;
        this.$('lblStatBlocks').textContent = d.lblStatBlocks;
        this.$('lblStatDone').textContent = d.lblStatDone;
        this.$('lblWelcomeTitle').textContent = d.lblWelcomeTitle;
        this.$('lblWelcomeSub').textContent = d.lblWelcomeSub;
        if (this.$('lblVpnTooltip')) this.$('lblVpnTooltip').title = d.tooltip;

        // Update login button immediately as well
        if (!this.isLoggedIn) {
            this.$('loginBtn').textContent = this.mode === 'vpn' ? d.btnLoginVpn : d.btnLoginDirect;
        } else {
            this.$('loginBtn').textContent = '...';
        }
    },

    switchMode(modeTarget) {
        if (this.isLoggedIn) return; 
        
        this.mode = modeTarget;
        this.$('segDirect').className = `seg-btn ${modeTarget === 'direct' ? 'active' : ''}`;
        this.$('segVpn').className = `seg-btn ${modeTarget === 'vpn' ? 'active' : ''}`;
        
        this.$('vpnInputArea').style.display = modeTarget === 'vpn' ? 'block' : 'none';
        this.$('loginBtn').textContent = modeTarget === 'vpn' ? DICT[this.lang].btnLoginVpn : DICT[this.lang].btnLoginDirect;
    },

    getSemester() {
        return { year: this.$('yearInput').value, month: this.$('monthInput').value, day: this.$('dayInput').value };
    },

    // ==========================================
    // UI Pipeline
    // ==========================================
    toast(msg) {
        const el = document.createElement('div');
        el.className = `toast`;
        el.textContent = "> " + msg;
        this.$('toastContainer').appendChild(el);
        setTimeout(() => {
            el.style.animation = 'toast-out 0.3s cubic-bezier(0.2, 0, 0, 1) forwards';
            setTimeout(() => el.remove(), 300);
        }, 3000);
    },

    pushLog(msg, type = 'info') {
        const body = this.$('logBody');
        const time = new Date().toLocaleTimeString('en-GB', { hour12: false });
        
        const plainMsg = msg.replace(/<[^>]+>/g, '');
        this.$('logLatest').textContent = `[${time}] ${plainMsg}`;
        if (type === 'error') this.$('logLatest').style.color = '#000';
        else if (type === 'warning') this.$('logLatest').style.color = '#D97706';
        else this.$('logLatest').style.color = '#555';

        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `<span class="log-time">${time}</span><span class="log-msg ${type}">${msg}</span>`;
        // 改为 prepend 放在最顶部，符合上新下旧的用户习惯
        body.prepend(entry);
        body.scrollTop = 0;
    },

    toggleLog() {
        this.logOpen = !this.logOpen;
        const tray = document.querySelector('.log-tray');
        const body = this.$('logBody');
        
        if (this.logOpen) {
            tray.classList.add('open');
            body.style.display = 'block';
        } else {
            tray.classList.remove('open');
            body.style.display = 'none';
        }
    },

    showLoading(show) {
        this.$('loadingOverlay').style.display = show ? 'flex' : 'none';
    },

    truncate(text, max) {
        return text && text.length > max ? text.slice(0, max - 1) + '…' : text;
    },

    // ==========================================
    // API Bindings
    // ==========================================
    async login() {
        const d = DICT[this.lang];
        const studentId = this.$('studentId').value.trim();
        if (!studentId) return this.toast(this.lang === 'zh' ? '缺少 UID' : 'Missing UID');

        let curlText = '';
        if (this.mode === 'vpn') {
            curlText = this.$('curlText').value.trim();
            if (!curlText) return this.toast(this.lang === 'zh' ? '请粘帖 cURL' : 'cURL Missing');
        }

        const btn = this.$('loginBtn');
        const status = this.$('loginStatus');
        btn.disabled = true;
        btn.textContent = '...';
        status.textContent = '';
        this.pushLog(d.msgLoginIssue, 'info');

        try {
            let result;
            if (this.mode === 'vpn') {
                result = await window.pywebview.api.login_vpn(studentId, curlText);
            } else {
                result = await window.pywebview.api.login_direct(studentId);
            }

            if (result.success) {
                this.isLoggedIn = true;
                status.textContent = `UID: ${result.userId} (Online)`;
                this.pushLog(`${d.msgLoginOk} (${result.userId})`, 'success');

                btn.style.display = 'none';
                this.$('logoutBtn').style.display = 'block';
                this.$('studentId').disabled = true;
                this.$('curlText').disabled = true;
                ['yearInput', 'monthInput', 'dayInput', 'segDirect', 'segVpn'].forEach(i => this.$(i).disabled = true);

                this.$('weekPanel').style.display = 'block';
                this.$('statsPanel').style.display = 'flex';

                await this.jumpToCurrentWeek();
            } else {
                status.textContent = `Access Denied: ${result.error}`;
                this.pushLog(`Denied: ${result.error}`, 'error');
                btn.disabled = false;
                btn.textContent = this.mode === 'vpn' ? d.btnLoginVpn : d.btnLoginDirect;
            }
        } catch (e) {
            status.textContent = 'System Fault.';
            this.pushLog(`Crash: ${e}`, 'error');
            btn.disabled = false;
            btn.textContent = this.mode === 'vpn' ? d.btnLoginVpn : d.btnLoginDirect;
        }
    },

    logout() {
        const d = DICT[this.lang];
        this.isLoggedIn = false;
        
        const btn = this.$('loginBtn');
        btn.style.display = 'block';
        btn.disabled = false;
        btn.textContent = this.mode === 'vpn' ? d.btnLoginVpn : d.btnLoginDirect;
        
        this.$('logoutBtn').style.display = 'none';
        ['studentId', 'curlText', 'yearInput', 'monthInput', 'dayInput', 'segDirect', 'segVpn'].forEach(i => this.$(i).disabled = false);
        this.$('loginStatus').textContent = '';

        this.$('weekPanel').style.display = 'none';
        this.$('statsPanel').style.display = 'none';
        this.$('welcomeView').style.display = 'flex';
        this.$('scheduleView').style.display = 'none';

        this.pushLog(d.msgLogingOut, 'warning');
    },

    // ==========================================
    // Data Navigation
    // ==========================================
    updateWeekDisplay() {
        const d = DICT[this.lang];
        this.$('weekDisplay').textContent = `${d.weekPrefix}${this.currentWeek}${d.weekSuffix}`;
    },

    prevWeek() { if (this.currentWeek > 1) { this.currentWeek--; this.updateWeekDisplay(); this.loadWeek(); } },
    nextWeek() { if (this.currentWeek < 18) { this.currentWeek++; this.updateWeekDisplay(); this.loadWeek(); } },

    async jumpToCurrentWeek() {
        const sem = this.getSemester();
        this.currentWeek = await window.pywebview.api.get_current_week(sem.year, sem.month, sem.day);
        this.updateWeekDisplay();
        this.loadWeek();
    },

    async loadWeek() {
        this.showLoading(true);
        this.$('welcomeView').style.display = 'none';
        this.$('scheduleView').style.display = 'flex';

        const sem = this.getSemester();
        try {
            const data = await window.pywebview.api.get_week_courses(this.currentWeek, sem.year, sem.month, sem.day);
            this.renderSchedule(data);
        } catch (e) {
            this.pushLog(`${DICT[this.lang].msgLoadFail} ${e}`, 'error');
        }
        this.showLoading(false);
    },

    // ==========================================
    // Rasterization
    // ==========================================
    renderSchedule(data) {
        const grid = this.$('scheduleGrid');
        grid.innerHTML = '';
        const d = DICT[this.lang];

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

            const header = document.createElement('div');
            header.className = `day-header${dayData.isToday ? ' is-today' : ''}`;
            const headerStat = coursesCount > 0 ? d.statBlocks(coursesCount, daySigned) : '&nbsp;';
            header.innerHTML = `
                <div class="day-name">${d.wkDays[i]}</div>
                <div class="day-date">${dayData.date}</div>
                <div class="day-stat">${headerStat}</div>
            `;
            col.appendChild(header);

            const body = document.createElement('div');
            body.className = 'day-body';

            if (coursesCount === 0) {
                body.innerHTML = `<div class="empty-day">${d.emptyDay}</div>`;
            } else {
                const sorted = dayData.courses.sort((a, b) => (a.classBeginTime || '').localeCompare(b.classBeginTime || ''));
                sorted.forEach(course => body.appendChild(this.buildCard(course, d)));
            }
            col.appendChild(body);
            grid.appendChild(col);
        }

        this.$('totalCourses').textContent = totalCourses;
        this.$('signedCourses').textContent = signedCourses;
    },

    buildCard(course, d) {
        const card = document.createElement('div');
        const isSigned = String(course.signStatus) === '1';
        card.className = `course-card ${isSigned ? 'signed' : 'unsigned'}`;

        const name = course.courseName || 'Class';
        const begin = (course.classBeginTime || '').slice(11, 16);
        const end = (course.classEndTime || '').slice(11, 16);
        const classroom = course.classroomName || '';
        const building = (course.teachBuildName || '').trim();
        const storey = (course.storeyName || '').trim();
        
        const locParts = [building, storey, classroom].filter(p => p && p !== 'null');
        const location = locParts.join(' ') || (this.lang === 'zh' ? '未知' : 'Unknown');

        const teachers = course.teachers || [];
        let teacherText = teachers.length === 1 ? teachers[0] : teachers.join(' & ');

        const ids = JSON.stringify(course.courseSchedIds || [course.id]).replace(/"/g, '&quot;');
        const escapedName = name.replace(/'/g, "\\'");

        card.innerHTML = `
            <div class="card-header">
                <span class="course-name">${this.truncate(name, 22)}</span>
                <span class="sign-badge ${isSigned ? 'signed' : 'unsigned'}">${isSigned ? d.cardBadgeDone : d.cardBadgePending}</span>
            </div>
            <div class="card-meta">
                <span>[${begin} - ${end}]</span>
                <span>${this.truncate(location, 18)}</span>
                <span>${teacherText}</span>
            </div>
            <div class="card-action">
                <button class="btn-sign ${isSigned ? 'signed' : ''}"
                        onclick="${isSigned ? '' : `app.signCourse(${ids}, '${escapedName}')`}">
                    ${isSigned ? d.cardDone : d.cardSign}
                </button>
            </div>
        `;
        return card;
    },

    // ==========================================
    // Executions
    // ==========================================
    async signCourse(ids, name) {
        this.pushLog(`${DICT[this.lang].msgSignLaunch} ${name}...`);
        try {
            const result = await window.pywebview.api.sign_course(JSON.stringify(ids));
            if (result.success > 0) {
                this.toast(`Block: ${name} (Pass)`);
                this.loadWeek();
            } else {
                this.toast(`Denied`);
            }
        } catch (e) {
            this.pushLog(`Crash: ${e}`, 'error');
        }
    },

    async batchSign() {
        const sem = this.getSemester();
        this.pushLog(`${DICT[this.lang].msgBatchLaunch} (W${this.currentWeek})...`);
        try {
            const result = await window.pywebview.api.batch_sign_week(this.currentWeek, sem.year, sem.month, sem.day);
            this.toast(`Batch Run: [${result.success}/${result.total}]`);
            this.loadWeek();
        } catch (e) {
            this.pushLog(`Crash: ${e}`, 'error');
        }
    }
};

window.app = app; 

window.addEventListener('pywebviewready', () => {
    app.applyLanguage();
    app.pushLog(DICT[app.lang].msgSysReady);
    app.$('studentId').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') app.login();
    });
});
