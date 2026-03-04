# BUAASignTool — 北航课程打卡助手

北京航空航天大学 iClass 平台桌面端签到工具，通过直接调用接口完成课程打卡。

> 本项目为开源工具，使用者需遵守学校相关规定，因使用产生的一切后果由使用者本人承担。

<!-- 截图占位 -->
<!-- ![主界面截图](./screenshots/main.png) -->

## 功能特性

- **极简主义界面** — 基于 pywebview + HTML/CSS/JS 构建，黑白灰设计语言
- **周视图课表** — 7列网格化布局，清晰展示每日课程安排
- **智能合并** — 同一课程多位教师自动合并为一张卡片
- **签到状态** — 已签/未签一目了然，已签到课程自动禁用打卡按钮
- **一键打卡** — 支持单课签到和整周批量打卡
- **连接复用** — `requests.Session` 加速课表加载
- **命令行版** — CLI 版本支持无图形环境使用

<!-- 课表截图占位 -->
<!-- ![课表展示](./screenshots/schedule.png) -->

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行 GUI 版

```bash
python app.py
```

1. 输入学号，设置学期起始日期
2. 点击「登录」，系统自动加载当前周课表
3. 点击卡片上的「签到」按钮完成打卡，或使用「一键打卡」

<!-- 操作流程截图占位 -->
<!-- ![操作流程](./screenshots/workflow.png) -->

### 运行 CLI 版

```bash
python ClassSignToolCLI.py
```

支持：指定单日 / 日期范围 / 连续打卡三种模式。

## 技术架构

| 层 | 技术 |
|----|------|
| 前端 | HTML + CSS + JavaScript（极简主义设计） |
| 桌面容器 | pywebview（系统原生 WebView） |
| 后端逻辑 | Python 3 + requests |
| 通信 | pywebview JS-Python API Bridge |

**API 接口：**
- 登录：`https://iclass.buaa.edu.cn:8346/app/user/login.action`
- 课表：`https://iclass.buaa.edu.cn:8346/app/course/get_stu_course_sched.action`
- 签到：`http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action`

## 项目结构

```
BUAASignTool/
├── app.py                 # GUI 主程序（pywebview 后端）
├── ClassSignToolCLI.py    # CLI 版本
├── requirements.txt
├── README.md
└── web/
    ├── index.html         # 页面结构
    ├── style.css          # 极简样式
    └── app.js             # 前端逻辑
```

## 常见问题

**Q: 为什么不需要密码？**
登录接口仅需学号即可获取会话，无需密码。

**Q: 打卡失败？**
常见原因：教师未开启签到、已超时、已打过卡、或网络问题。

**Q: 会被检测到吗？**
请求与官方 App 一致，但任何自动化工具都有风险，请遵守校规。