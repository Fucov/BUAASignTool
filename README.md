# BUAASignTool — Minimalism Arch.

北京航空航天大学 iClass 桌面端辅助工具。基于纯净的单体架构设计与极度克制的极简主义美学。支持**中英双语**切换。

> 免责协议：本项目为自动化网络请求的实验性容器，请基于个人判断决定是否部署。因越权操作导致的问题由接入者自行承担。

## The Core

- **单片机架构 (Monolithic)** — 将直连层、校外隧道探针与通信解析汇聚为单一 `app.py`。
- **虚空极简 (Void Aesthetics)** — 剔除全部环境阴影、圆角。通过 1px 线切割呈现数据。使用深邃的 Console 格式重绘日记。
- **跨栈容器 (Tunneling)** — 抛弃复杂的本地设置，侧边栏内置完善正则解析的 cURL 引擎，支持高墙 WebVPN 环境的深穿透一键接管。
- **线程组装 (Parallelism)** — `requests.Session()` 与 7 核心 `ThreadPoolExecutor` 使区块课表合并呈现。
- **极速热替 (Local i18n)** — 全局字典式注入，支持秒切极简的业务态全英文/中文标识。

## 部署引导

### 1. 挂载环境依赖

必须将本机环境与本项目所需清单对其，尤其是 AES 加密隧道需要的组件：

```bash
pip install -r requirements.txt
```

*(列表：`pywebview`, `requests`, `pycryptodome`)*

### 2. 升起应用

```bash
python app.py
```

### 3. 操作矩阵
- **内网环境 (Direct)**: 选择 `校园直连` -> 填入 UID 学号 -> 点击部署。
- **WebVPN 环境 (Tunneling)**: 选择 `校外穿透` -> 点击 `ⓘ` 查看提示并将其指导作为实践 -> 粘贴浏览器拦截出的 cURL 结构 -> 点击部署。

## 网络接口映射 (API Topology)

- `app.py` 内部使用智能探针。
- **鉴权节点**: `https-8346 /app/user/login.action`
- **区块组装**: `https-8346 /app/course/get_stu_course_sched.action`
- **穿透打击**: `http-8081 /app/course/stu_scan_sign.action` 

## Q&A 

- **无 cURL 响应?** 确保在 d.buaa.edu.cn F12 的网络面板 (Network) 内提取的是 "Copy as cURL (cmd / bash)" 或者 "Copy as cURL" 均可，最新正则已可自动规避 MacOS (`\`) 和 Windows (`^`) 的转义污染。
- **打卡提示驳回?** 节点已被封锁（老师未开放签到），或在非校园/非隧道的无效域被阻绝。
