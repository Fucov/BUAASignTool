> [!important]
> 请严格遵循学校相关规章制度，合理使用本工具。严禁用于恶意并发请求、破坏系统稳定性等违规行为。若引起服务器异常，作者将立即终止项目维护。
# BUAA Sign Tool (北航课程打卡系统)

一款专为北航学子打造的极简主义桌面端课程辅助工具。支持查看每周课表、课程状态追踪，以及校内/校外环境下的**一键自动打卡**功能。

---

## 💡 项目大致介绍

本项目旨在解决北航学生日常上课打卡的繁琐流程，提供一个安静、高效、无打扰的桌面端操作体验。

### ✨ 核心特性
- **极简主义 UI (Minimalism)**：拒绝视觉噪音，专注核心信息，提供如同高端画廊般的清爽体验。
- **双模网络穿透**：
  - **校内直连**：在校园网环境下，仅需学号即可一秒无感登录。
  - **校外穿透 (WebVPN)**：深度解析 Wengine VPN 协议，支持通过 cURL 凭证在校外实现内网 API 穿透调用。
- **高并发数据流**：基于多线程异步拉取全周课表，自动合并多教师/多时段的冗余课程节点。
- **单体桌面应用**：基于 `pywebview` 架构，前端采用原生 JS/HTML/CSS，轻量、跨平台、无繁重依赖。

---

## 📖 项目使用教程

### 1. 环境准备(使用exe版本可以跳过环境准备步骤)
确保你的电脑已安装 Python 3.8+，并在项目根目录运行以下命令安装依赖：
```bash
pip install -r requirements.txt
```
*(注：核心依赖包括 `requests`, `pywebview`, `pycryptodome`)*

启动程序：
```bash
python app.py
```

### 2. 校外使用 (WebVPN 穿透模式) ⚠️

> [!caution]
> 下文提及的 **cURL 命令** 包含您的统一身份认证核心凭证（相当于您的账号密码）。
> **绝对不要将您的 cURL 命令发送给任何人，或上传至任何公开网络！**
> 本软件仅在本地内存中解析该凭证，绝不会将其上传至任何第三方服务器。

由于学校 WebVPN 的底层安全限制，在校外网络使用本软件需手动同步一次浏览器产生的会话凭证。具体步骤如下：

#### 第一步：获取身份凭证 (cURL)
1. **登录大厅**：在浏览器（推荐 Chrome 或 Edge）中访问 [d.buaa.edu.cn](https://d.buaa.edu.cn/)，完成统一身份认证登录，进入蓝色资源大厅。
2. **打开控制台**：按下 `F12` 键打开开发者工具，切换到 **“网络 (Network)”** 面板。
3. **捕获请求**：`CTRL+R`刷新页面，在左侧列表中找到任意一条请求。
4. **复制 cURL**：
   - 右键点击该请求。
   - 选择 **“复制 (Copy)”** -> **“复制为 cURL (bash)”** 或 **“复制为 cURL (cmd)”**。
   - <img width="2512" height="1370" alt="Image" src="https://github.com/user-attachments/assets/8e169d77-0e4b-48c9-802d-9bf5bc1a3c64" />

#### 第二步：在软件中导入并登录
1. 打开 BUAA Sign Tool，在左侧边栏的“网络环境”下拉框中选择 **“非校园网 (WebVPN)”**。
2. 此时会展开一个文本框，将刚才复制的 cURL 完整粘贴进去。
3. 输入你的学号，点击登录即可。
   -  <img width="1730" height="1121" alt="image" src="https://github.com/user-attachments/assets/cc5d2bea-6001-4893-874a-53d5058420fe" />

#### 附：cURL 示例参考
软件会自动从您粘贴的命令中提取 `_zte_cid_` 与 `wengine_vpn_ticket...`，您复制的内容大致应如下所示：

**curl(cmd) 示例：**
```cmd
curl ^"[https://d.buaa.edu.cn/user/portal_groups?_t=1773728057653](https://d.buaa.edu.cn/user/portal_groups?_t=1773728057653)^" ^
  -H ^"Accept: application/json, text/plain, */*^" ^
  -H ^"Accept-Language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6^" ^
  -H ^"Connection: keep-alive^" ^
  -b ^"_zte_cid_=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx; show_vpn=0; heartbeat=1; show_faq=0; wrdvpn_upstream_ip=xx.xx.xx.xx; wengine_vpn_ticketd_buaa_edu_cn=xxxxxxxxxxxxxxxx; route=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx; refresh=1^" ^
  -H ^"Referer: [https://d.buaa.edu.cn/](https://d.buaa.edu.cn/)^" ^
  -H ^"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...^"
```

**curl(bash) 示例：**
```bash
curl '[https://d.buaa.edu.cn/user/portal_groups?_t=1773728057653](https://d.buaa.edu.cn/user/portal_groups?_t=1773728057653)' \
  -H 'Accept: application/json, text/plain, */*' \
  -H 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6' \
  -H 'Connection: keep-alive' \
  -b '_zte_cid_=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx; show_vpn=0; heartbeat=1; show_faq=0; wrdvpn_upstream_ip=xx.xx.xx.xx; wengine_vpn_ticketd_buaa_edu_cn=xxxxxxxxxxxxxxxx; route=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx; refresh=1' \
  -H 'Referer: [https://d.buaa.edu.cn/](https://d.buaa.edu.cn/)' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...'
```

### 3. 校内直连模式
如果您当前处于校园网环境，只需在软件中选择“校园直连”，输入学号即可直接进入系统，无需粘贴 cURL。

---

## ⚖️ 免责声明

1. **非官方性质**：本项目为个人开发的开源学习交流项目，与北京航空航天大学官方、信息化办公室及 iClass 平台开发方无任何关联。
2. **安全与隐私**：本项目为**纯本地运行**架构。用户输入的学号、cURL 凭证均仅在本地内存与配置文件中流转，程序绝不包含任何恶意收集、上传隐私数据的代码。请用户妥善保管自己的账号凭据。
3. **使用风险**：本软件仅用于辅助查看课表及简化签到流程。**用户须自行承担使用本软件所带来的一切风险。** 作者不对因使用本软件导致的签到失败、考勤异常、账号被封禁或其他任何直接/间接损失承担任何法律及连带责任。
4. **合理使用**：请遵循学校相关规章制度，合理使用本工具，切勿用于恶意刷接口、破坏系统稳定性等违规行为。**若引起校方注意或服务器压力，作者将随时下架并终止维护此项目。**

