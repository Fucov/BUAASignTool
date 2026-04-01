/**
 * 北航课程助手 — 前端逻辑 / 国际化
 */

const DICT = {
    'zh': {
        logoSub: '极简 · 高效',
        segDirect: '校园直连',
        segVpn: '校外网络',
        lblUid: '学号',
        phUid: '输入学号',
        lblVpnUid: '账号',
        phVpnUid: '统一认证账号',
        lblVpnPwd: '密码',
        phVpnPwd: '统一认证密码',
        lblStudentId: '学号',
        phStudentId: '输入学号',
        lblSemester: '学期基准日',
        btnLoginDirect: '登 录',
        btnLoginVpn: 'VPN 登录',
        btnLogout: '退出登录',
        lblTimeCtrl: '时间控制',
        btnReset: '本周',
        btnReload: '刷新',
        btnBatch: '一键签到',
        lblStatBlocks: '排课数',
        lblStatDone: '已签到',
        lblWelcomeTitle: 'BUAA 课程助手',
        lblWelcomeSub: '请在左侧登录',
        weekPrefix: '第 ',
        weekSuffix: ' 周',
        wkDays: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
        emptyDay: '今日无课',
        cardSign: '签到',
        cardDone: '已完成',
        cardBadgePending: '未签',
        cardBadgeDone: '已签',
        statBlocks: (total, done) => `${total} 节 / 已签 ${done}`,
        msgSysReady: '就绪。',
        msgLoginIssue: '正在登录...',
        msgLoginOk: '登录成功。',
        msgLogingOut: '已退出登录。',
        msgLoadFail: '加载失败:',
        msgBatchLaunch: '正在批量签到...',
        msgSignLaunch: '正在签到:',
        errNoStudentId: '请输入学号',
        errNoVpnCreds: '请输入账号和密码',
    },
    'en': {
        logoSub: 'Minimalism · Utility',
        segDirect: 'Direct',
        segVpn: 'WebVPN',
        lblUid: 'Student ID',
        phUid: 'Enter ID',
        lblVpnUid: 'Username',
        phVpnUid: 'SSO Username',
        lblVpnPwd: 'Password',
        phVpnPwd: 'SSO Password',
        lblStudentId: 'Student ID',
        phStudentId: 'Enter ID',
        lblSemester: 'Semester Start',
        btnLoginDirect: 'Sign In',
        btnLoginVpn: 'VPN Login',
        btnLogout: 'Sign Out',
        lblTimeCtrl: 'Time Frame',
        btnReset: 'Current',
        btnReload: 'Refresh',
        btnBatch: 'Sign All',
        lblStatBlocks: 'Blocks',
        lblStatDone: 'Signed',
        lblWelcomeTitle: 'BUAA Sign Tool',
        lblWelcomeSub: 'Please sign in',
        weekPrefix: 'Week ',
        weekSuffix: '',
        wkDays: ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'],
        emptyDay: 'No classes',
        cardSign: 'SIGN',
        cardDone: 'DONE',
        cardBadgePending: 'PENDING',
        cardBadgeDone: 'SIGNED',
        statBlocks: (total, done) => `${total} / ${done} signed`,
        msgSysReady: 'Ready.',
        msgLoginIssue: 'Signing in...',
        msgLoginOk: 'Signed in.',
        msgLogingOut: 'Signed out.',
        msgLoadFail: 'Load failed:',
        msgBatchLaunch: 'Batch signing...',
        msgSignLaunch: 'Signing:',
        errNoStudentId: 'Student ID required',
        errNoVpnCreds: 'Username and password required',
    }
};

const app = {
    currentWeek: 1,
    isLoggedIn: false,
    mode: 'direct',
    logOpen: false,
    lang: 'zh',
    _courseCache: null,
    _signingCourse: null,

    $(id) { return document.getElementById(id); },

    // ==========================================
    // 核心控制
    // ==========================================
    toggleLang() {
        this.lang = this.lang === 'zh' ? 'en' : 'zh';
        this.$('langBtn').textContent = this.lang === 'zh' ? 'EN' : '中';
        this.applyLanguage();
        if (this.isLoggedIn) {
            this.updateWeekDisplay();
            this.loadWeek();
        }
    },

    applyLanguage() {
        const d = DICT[this.lang];
        this.$('lblLogoSub').textContent = d.logoSub;
        this.$('segDirect').textContent = d.segDirect;
        this.$('segVpn').textContent = d.segVpn;
        this.$('lblUid').textContent = d.lblUid;
        this.$('studentId').placeholder = d.phUid;
        this.$('lblVpnUid').textContent = d.lblVpnUid;
        this.$('vpnUsername').placeholder = d.phVpnUid;
        this.$('lblVpnPwd').textContent = d.lblVpnPwd;
        this.$('vpnPassword').placeholder = d.phVpnPwd;
        this.$('lblStudentId').textContent = d.lblStudentId;
        this.$('studentIdProxy').placeholder = d.phStudentId;
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

        // 切换显示对应的输入区域
        if (modeTarget === 'vpn') {
            this.$('directInputArea').style.display = 'none';
            this.$('vpnInputArea').style.display = 'block';
        } else {
            this.$('directInputArea').style.display = 'block';
            this.$('vpnInputArea').style.display = 'none';
        }

        this.$('loginBtn').textContent = modeTarget === 'vpn' ? DICT[this.lang].btnLoginVpn : DICT[this.lang].btnLoginDirect;
    },

    getSemester() {
        return { year: this.$('yearInput').value, month: this.$('monthInput').value, day: this.$('dayInput').value };
    },

    // ==========================================
    // 界面工具
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
    // 登录与认证
    // ==========================================
    async login() {
        const d = DICT[this.lang];
        const btn = this.$('loginBtn');
        const status = this.$('loginStatus');
        btn.disabled = true;
        btn.textContent = '...';
        status.textContent = '';
        this.pushLog(d.msgLoginIssue, 'info');

        try {
            let result;

            if (this.mode === 'vpn') {
                const vpnUsername = this.$('vpnUsername').value.trim();
                const vpnPassword = this.$('vpnPassword').value;
                const studentIdProxy = this.$('studentIdProxy').value.trim();
                
                if (!vpnUsername || !vpnPassword) {
                    status.textContent = d.errNoVpnCreds;
                    btn.disabled = false;
                    btn.textContent = d.btnLoginVpn;
                    this.toast(d.errNoVpnCreds);
                    return;
                }
                // 传入可选的学号参数
                result = await window.pywebview.api.login_vpn(vpnUsername, vpnPassword, studentIdProxy || null);
            } else {
                const studentId = this.$('studentId').value.trim();
                if (!studentId) {
                    status.textContent = d.errNoStudentId;
                    btn.disabled = false;
                    btn.textContent = d.btnLoginDirect;
                    this.toast(d.errNoStudentId);
                    return;
                }
                result = await window.pywebview.api.login_direct(studentId);
            }

            if (result.success) {
                this.isLoggedIn = true;
                const nameDisplay = result.userName ? ` (${result.userName})` : '';
                status.textContent = `UID: ${result.userId}${nameDisplay}`;
                this.pushLog(`${d.msgLoginOk} (${result.userId}${nameDisplay})`, 'success');

                btn.style.display = 'none';
                this.$('logoutBtn').style.display = 'block';
                this.$('studentId').disabled = true;
                this.$('vpnUsername').disabled = true;
                this.$('vpnPassword').disabled = true;
                this.$('studentIdProxy').disabled = true;
                ['yearInput', 'monthInput', 'dayInput', 'segDirect', 'segVpn'].forEach(i => this.$(i).disabled = true);

                this.$('weekPanel').style.display = 'block';
                this.$('statsPanel').style.display = 'flex';

                await this.jumpToCurrentWeek();
            } else {
                status.textContent = `登录失败: ${result.error}`;
                this.pushLog(`失败: ${result.error}`, 'error');
                btn.disabled = false;
                btn.textContent = this.mode === 'vpn' ? d.btnLoginVpn : d.btnLoginDirect;
            }
        } catch (e) {
            status.textContent = '连接异常';
            this.pushLog(`异常: ${e}`, 'error');
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
        ['studentId', 'vpnUsername', 'vpnPassword', 'studentIdProxy', 'yearInput', 'monthInput', 'dayInput', 'segDirect', 'segVpn'].forEach(i => this.$(i).disabled = false);
        this.$('loginStatus').textContent = '';

        this.$('weekPanel').style.display = 'none';
        this.$('statsPanel').style.display = 'none';
        this.$('welcomeView').style.display = 'flex';
        this.$('scheduleView').style.display = 'none';

        this.pushLog(d.msgLogingOut, 'warning');
    },

    // ==========================================
    // 周次导航
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
            this._courseCache = data;  // 缓存数据
            this.renderSchedule(data);
        } catch (e) {
            this.pushLog(`加载失败，请检查网络`, 'error');
        }
        this.showLoading(false);
    },

    // ==========================================
    // 课表渲染
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

        // 课程签到按钮 - 使用 this 传递卡片引用
        const btnHtml = isSigned
            ? `<button class="btn-sign signed" disabled>${d.cardDone}</button>`
            : `<button class="btn-sign" onclick="app.signCourseByCard(this.closest('.course-card'))">${d.cardSign}</button>`;

        card.className = `course-card ${isSigned ? 'signed' : 'unsigned'}`;
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
                ${btnHtml}
            </div>
        `;
        
        // innerHTML 之后存储课程数据
        card._courseData = course;
        return card;
    },

    // ==========================================
    // 签到操作
    // ==========================================
    signCourseByCard(card) {
        // 防止重复点击
        if (this._signingCourse) {
            this.toast('签到中，请稍候...');
            return;
        }
        
        const courseData = card._courseData;
        if (!courseData) return;
        
        const courseName = courseData.courseName || '未知课程';
        const courseId = courseData.id;
        const courseSchedIds = courseData.courseSchedIds || [courseId];
        
        this._signingCourse = courseName;
        this.pushLog(`正在签到: ${courseName}...`);
        
        // 调用后端签到
        window.pywebview.api.sign_course(JSON.stringify(courseSchedIds), JSON.stringify([courseName]))
            .then(result => {
                this._signingCourse = null;
                if (result.success > 0) {
                    // 签到成功，无感更新卡片状态
                    this._updateCardSigned(card, true);
                    this.toast('签到成功');
                } else if (result.skipped > 0) {
                    this._updateCardSigned(card, true);
                    this.toast('已签到');
                } else {
                    this.toast('签到失败，请稍后重试');
                }
            })
            .catch(e => {
                this._signingCourse = null;
                this.toast('签到失败，请稍后重试');
            });
    },
    
    _updateCardSigned(card, isSigned) {
        const d = DICT[this.lang];
        
        // 检查是否已经更新过，避免重复计数
        const badge = card.querySelector('.sign-badge');
        const wasAlreadySigned = badge && badge.classList.contains('signed');
        
        // 更新卡片样式
        card.className = `course-card ${isSigned ? 'signed' : 'unsigned'}`;
        
        // 更新徽章
        if (badge) {
            badge.className = `sign-badge ${isSigned ? 'signed' : 'unsigned'}`;
            badge.textContent = isSigned ? d.cardBadgeDone : d.cardBadgePending;
        }
        
        // 更新按钮
        const btn = card.querySelector('.btn-sign');
        if (btn) {
            btn.className = `btn-sign ${isSigned ? 'signed' : ''}`;
            btn.disabled = isSigned;
            btn.textContent = isSigned ? d.cardDone : d.cardSign;
        }
        
        // 更新课程数据缓存
        const courseData = card._courseData;
        if (courseData) {
            courseData.signStatus = '1';
        }
        
        // 只有从"未签到"变成"已签到"时才更新统计
        if (isSigned && !wasAlreadySigned) {
            const signedCount = parseInt(this.$('signedCourses').textContent) || 0;
            const totalCount = parseInt(this.$('totalCourses').textContent) || 0;
            this.$('signedCourses').textContent = Math.min(signedCount + 1, totalCount);
        }
    },

    batchSign() {
        if (this._signingCourse) {
            this.toast('签到中，请稍候...');
            return;
        }
        
        this._signingCourse = 'batch';
        this.pushLog(`一键签到中，请稍候...`);
        this.$('btnBatch').disabled = true;
        
        const sem = this.getSemester();
        window.pywebview.api.batch_sign_week(this.currentWeek, sem.year, sem.month, sem.day)
            .then(result => {
                this._signingCourse = null;
                this.$('btnBatch').disabled = false;
                
                if (result.success > 0 || result.skipped > 0) {
                    // 根据结果更新 UI
                    this._refreshCardsByResult(result.results || []);
                    const msg = result.success > 0 
                        ? `签到成功: ${result.success}`
                        : (result.total === 0 ? `本周暂无待签到课程` : `已全部签到`);
                    this.toast(msg);
                } else if (result.total === 0) {
                    this.toast(`本周暂无待签到课程`);
                } else {
                    this.toast(`签到完成`);
                }
            })
            .catch(e => {
                this._signingCourse = null;
                this.$('btnBatch').disabled = false;
                this.toast(`签到失败，请稍后重试`);
            });
    },
    
    _refreshCardsByResult(results) {
        // 根据签到结果更新卡片 - 使用 ID 匹配
        const cards = document.querySelectorAll('.course-card');
        let updatedCount = 0;
        
        for (const res of results) {
            if (res.status === 'success' || res.status === 'skipped') {
                const courseId = res.id;
                // 找到对应的卡片
                for (const card of cards) {
                    const courseData = card._courseData;
                    if (courseData && (courseData.id === courseId || (courseData.courseSchedIds && courseData.courseSchedIds.includes(courseId)))) {
                        const badge = card.querySelector('.sign-badge');
                        if (badge && !badge.classList.contains('signed')) {
                            this._updateCardSigned(card, true);
                            updatedCount++;
                        }
                        break;
                    }
                }
            }
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
    app.$('vpnPassword').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') app.login();
    });
});
