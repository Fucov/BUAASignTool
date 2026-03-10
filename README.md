
# BUAASignTool — 北航课程打卡助手

**BUAASignTool** 是一款专为北京航空航天大学 iClass 平台设计的桌面端辅助工具。它通过原生接口调用，帮助同学在 PC 端快速完成课程签到与课表查看，摆脱手机 App 的束缚。

> **免责声明**：本项目仅供学习交流使用。使用者需严格遵守学校相关规定，因使用本工具产生的一切后果（如违规记录等）由使用者本人承担。

---

## 🚀 快速下载（推荐）

如果你不想配置 Python 环境，可以直接下载我们已经打包好的**绿色免安装版**：

1. 前往 **[Releases 页面](https://github.com/Fucov/BUAASignTool/releases)**。
2. 下载最新版本的 `BUAASignTool_v1.0.exe` (Windows)。
3. 双击即可运行，无需安装任何依赖。

---

## ✨ 功能特性

* **极简主义界面** — 基于 `pywebview` + 原生前端技术构建，黑白灰工业风设计。
* **智能周视图** — 7列网格化布局，自动同步教务系统每日课程安排。
* **高效打卡** —
* **一键全签**：支持整周课程批量自动打卡。
* **单课手动**：精准控制每一节课的签到状态。


* **状态实时同步** — 已签/未签状态一目了然，签到成功后自动禁用按钮防止误操作。
* **双模运行** —
* **GUI 模式**：直观、易用，适合日常使用。
* **CLI 模式**：极简、极速，适合无图形环境或极客用户。



---

## 🛠️ 开发者指南

如果你希望自行构建或修改代码：

### 环境要求

* Python 3.8+
* Windows / macOS / Linux (需安装对应的 WebView2 运行库)

### 运行步骤

```bash
# 1. 克隆项目
git clone https://github.com/Fucov/BUAASignTool.git
cd BUAASignTool

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python app.py  # 启动图形界面
# 或
python ClassSignToolCLI.py  # 启动命令行版

```

---

## 🏗️ 技术架构与逻辑

### 核心技术栈

| 模块 | 实现方案 |
| --- | --- |
| **UI 渲染** | HTML5 + CSS3 + Vanilla JS (极简设计) |
| **桌面容器** | `pywebview` (原生系统 WebView 桥接) |
| **网络请求** | `requests.Session` (保持会话，连接复用) |
| **API 交互** | 基于 `webview.js_api` 的异步通信 |

### 项目结构

```text
BUAASignTool/
├── app.py                 # GUI 主入口
├── ClassSignToolCLI.py    # CLI 命令行入口
├── icon.ico               # 程序图标
├── web/                   # 前端资源目录
│   ├── index.html         # 结构
│   ├── style.css          # 样式
│   └── app.js             # 交互逻辑
└── requirements.txt       # 依赖声明

```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么登录不需要密码？**
iClass 接口设计允许通过学号验证会话。为了保护隐私，本工具不接触、不存储您的任何密码。

**Q: 点击签到没有反应？**
请确认：1. 教师已开启签到；2. 当前在签到时间范围内；3. 网络连接正常。

**Q: 是否会产生封号风险？**
本工具发出的请求特征与官方 App 完全一致，但频繁、异常的自动化操作仍可能引起注意，请适度使用。

---

## 📝 开源协议

本项目基于 [MIT License](https://www.google.com/search?q=LICENSE) 开源。

**Project Link:** [https://github.com/Fucov/BUAASignTool](https://github.com/Fucov/BUAASignTool)

---

**如果你觉得这个工具有帮到你，欢迎给仓库点个 ⭐️ Star！**
