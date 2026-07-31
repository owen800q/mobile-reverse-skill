---
title: '[原创]AI逆向50页长文掌握 IDA Pro MCP 逆向分析利器'
url: https://bbs.kanxue.com/thread-286813.htm
tid: 286813
author: 棕熊
date: '2025-05-13'
tags: [Android安全, 原创, 工具脚本, 基础理论, 逆向分析]
crawled_at: '2026-07-31T15:52:53+08:00'
replies: 813
---

## 前言

本教程旨在提供一份详尽的、手把手级别的指南，帮助您配置和使用 IDA Pro MCP 进行逆向分析。
为什么突然发这个帖子，因为我认为https://github.com/mrexodia/ida-pro-mcp做的非常好，如果你能跟着我配置完这一个项目，那么其他的ai相关的环境以及工具都可以直接上手了，所以发出的目的就是以一个说明书的形式完整的带大家配一下ai工具的环境，以后出了新的工具也不用再学习了。
教程写的很详细，有50页pdf长度，都是作者从0开始手把手配置的环境，肯定可以跑通。
当然我认为ai一定对带来对攻防对等的收益，所以今天带来优秀作品IDA Pro MCP的macOS和Windows配置手把手教程，推荐大家以cursor为主来使用，当然有能力的朋友可以尝试国外的大模型，能带来焕然一新的感觉。
此外，文中会提及获取常见大模型 API Key 的合规渠道。工具本身并无好坏之分，关键在于如何运用。无论是革新传统的逆向分析方法论，还是仅仅解决某个具体的技术疑点，IDA Pro MCP 都能在你逆向的时候帮你一把。千万不要过度依赖ai分析，语意的大模型提供思路很好，在汇编级别，字节级别的内存操作，请相信你自己的直觉，不要盲目信从大模型。
如果教程有不懂的地方欢迎留言，我会随时补充！

## 步骤一：准备大模型 API Key

要使用 IDA Pro MCP，首先需要一个大模型服务的 API Key。以下介绍几种国内较为合规的获取渠道，主要以 DeepSeek 为例。您可以根据自己的需求选择其中一种。

### 渠道一：DeepSeek

- **官方网站:** <https://www.deepseek.com/>
- **API 管理平台:** <https://platform.deepseek.com/usage>

新用户通常会有免费额度。老用户可以按需充值，最低充值金额一般为 10 元。

![DeepSeek 充值界面](https://bbs.kanxue.com/upload/attach/202505/967562_EEM4KKZKRRV54CZ.png)

请按照 DeepSeek 平台的指引完成实名认证和充值。之后，在用户中心或 API 管理页面创建一个新的 API Key。**请务必妥善保管您的 API Key，防止泄露。**

![DeepSeek API Key 创建界面](https://bbs.kanxue.com/upload/attach/202505/967562_YPHTP47YTMTYT6E.png)

获取 API Key 后，我们可以使用 `curl` 命令测试 API 是否可用。请将 `<DeepSeek API Key>` 替换为您自己的 Key。

**示例 Key (已被修改，仅作演示):** `sk-0a78dd928fef46899bf1a45d31666666`

| 1234567891011 | `curl https:``//api``.deepseek.com``/chat/completions` `\``-H` `"Content-Type: application/json"` `\``-H` `"Authorization: Bearer <DeepSeek API Key>"` `\``-d '{``"model"``:` `"deepseek-chat"``,``"messages"``: [``{``"role"``:` `"system"``,` `"content"``:` `"You are a helpful assistant."``},``{``"role"``:` `"user"``,` `"content"``:` `"Hello!"``}``],``"stream"``:` `false``}'` |
|-|-|

**替换后的命令:**

| 1234567891011 | `curl https:``//api``.deepseek.com``/chat/completions` `\``-H` `"Content-Type: application/json"` `\``-H` `"Authorization: Bearer sk-0a78dd928fef46899bf1a45d31666666"` `\``-d '{``"model"``:` `"deepseek-chat"``,``"messages"``: [``{``"role"``:` `"system"``,` `"content"``:` `"You are a helpful assistant."``},``{``"role"``:` `"user"``,` `"content"``:` `"Hello!"``}``],``"stream"``:` `false``}'` |
|-|-|

![curl 测试 DeepSeek API 成功截图](https://bbs.kanxue.com/upload/attach/202505/967562_B9QRAVDDHC5VF42.png)

如果终端成功输出了 AI 的回复消息，则表示您的 DeepSeek API Key 配置成功。

### 渠道二：硅基流动 (SiliconFlow)

- **官方网站:** <https://siliconflow.cn/>

![硅基流动官网截图](https://bbs.kanxue.com/upload/attach/202505/967562_6CD7CWCARRJTZ6D.png)

登录后，请先完成实名认证，然后在 API 密钥管理页面创建新的 Key。

![硅基流动 API Key 创建界面](https://bbs.kanxue.com/upload/attach/202505/967562_5C7M47QJ73V6972.png)

**示例 Key (仅作演示):** `sk-bvygzuetqdtrslnybmzqmcnufvjtmdhgubqiepentgnkncccc`

请确保您的账户有足够的余额。新用户通常有赠送额度，也可以留意官方活动或特定渠道获取优惠。

使用以下 `curl` 命令测试 API，将 `你的key` 替换为您的 SiliconFlow API Key。这里以 `Qwen/Qwen2.5-72B-Instruct` 模型为例，您可以在其模型广场选择其他可用模型。

| 1234567891011 | `curl https:``//api``.siliconflow.cn``/v1/chat/completions` `\``-H` `"Content-Type: application/json"` `\``-H` `"Authorization: Bearer 你的key"` `\``-d '{``"model"``:` `"Qwen/Qwen2.5-72B-Instruct"``,``"messages"``: [``{``"role"``:` `"system"``,` `"content"``:` `"You are a helpful assistant."``},``{``"role"``:` `"user"``,` `"content"``:` `"Hello!"``}``],``"stream"``:` `false``}'` |
|-|-|

如果返回类似以下的 JSON 响应，则表示请求成功：

```
{"id":"0196c292f544b02f3e5a5365310e8390","object":"chat.completion","created":1747021133,"model":"Qwen/Qwen2.5-72B-Instruct","choices":[{"index":0,"message":{"role":"assistant","content":"Hello! How can I assist you today?"},"finish_reason":"stop"}],"usage":{"prompt_tokens":21,"completion_tokens":9,"total_tokens":30},"system_fingerprint":""}
```

### 渠道三：火山引擎方舟平台 (VolcEngine Ark)

您可以通过火山引擎方舟平台调用包括 DeepSeek 在内的多种大模型。

1. **访问模型页面:** 前往火山引擎方舟平台的 DeepSeek 模型详情页：<https://console.volcengine.com/ark/region:ark+cn-beijing/model/detail?Id=deepseek-r1>
![火山引擎 DeepSeek 模型页面](https://bbs.kanxue.com/upload/attach/202602/967562_FM2MTGBFRF7QTNS.png)
2. **点击“推理”:** 在页面右下角找到并点击【推理】按钮。
3. **创建 API Key:** 在弹出的“快捷 API 接入”页面，点击【创建 API Key】按钮。
![火山引擎快捷 API 接入](https://bbs.kanxue.com/upload/attach/202602/967562_7UR754QVYRRZ7BN.png)
4. **获取 API Key:** 创建成功后，在页面右下角点击【选择 API Key 并复制】。同时，您还需要记录下 **API 地址 (Endpoint)** 和 **模型 ID (Model ID)**。
![火山引擎获取 API Key](https://bbs.kanxue.com/upload/attach/202602/967562_VBWATRFFZT3HKR7.png)

集齐 API Key、API 地址和模型 ID 这三个要素后，您就可以在支持火山引擎接口的客户端中配置并使用了。

### 渠道四：阿里云通义千问 (Alibaba Tongyi)

- **官方网站:** <https://www.aliyun.com/product/tongyi>

阿里云提供了通义千问系列模型，包括性能强大的 Qwen2 等。您可以访问其官网了解详情并申请 API Key。

### 更多渠道

除了上述渠道，百度文心、智谱 AI 等国内厂商也提供了各自的大模型服务。您可以根据自己的需求和偏好，自行探索和选择合适的模型及 API 服务。

## 步骤二：选择并配置 MCP 客户端

### 理解 MCP (Model Context Protocol)

在深入配置之前，让我们先简单理解一下什么是 MCP。

MCP (Model Context Protocol) 是一种协议，旨在让 AI 模型能够更智能地理解和利用当前工作环境中的上下文信息。当您与 AI 对话时，支持 MCP 的客户端（或称为“载体”）会自动收集相关的上下文信息（例如当前打开的文件、选中的代码片段、项目结构等），并将其提供给 AI 模型。

早期使用大模型时，一个常见的挑战是如何有效地提供上下文。例如，如果您想让 AI 修改代码，仅仅告诉它“请修改我的代码”是远远不够的。一个更有效的方法是，将相关的头文件 (`.h`)、源文件 (`.c`, `.cpp` 等) 以及描述业务逻辑的代码片段都提供给 AI。这样，AI 才能更准确地理解您的意图并生成高质量的代码。

MCP 的目标就是自动化这个过程。它通过标准化上下文信息的收集和传输方式，让 AI 应用（如 VS Code 插件、独立客户端等）能够无缝地与 IDA Pro 这类专业工具集成，从而在逆向分析等复杂场景下发挥 AI 的最大潜力。

优秀的 AI 编程助手，如 Cursor，正是通过高效的上下文管理（包括向量化索引、上下文压缩等技术）实现了出色的代码理解和生成能力，从而获得了广泛应用。IDA Pro MCP 遵循了类似的理念，将 MCP 的能力带入了逆向工程领域。

### 客户端一：VS Code 插件 (Cline / RooCode)

Cline 和 RooCode 是两款支持 MCP 的 VS Code 插件，可以将 VS Code 作为 IDA Pro MCP 的客户端。

#### 安装

1. 打开 VS Code。
2. 点击左侧边栏的“扩展”图标 (Extensions)。
![VS Code 扩展商店图标](https://bbs.kanxue.com/upload/attach/202505/967562_93BGJY6MUDMFT9J.png)
3. 在搜索框中输入 `Cline` 或 `RooCode`。
![image](https://bbs.kanxue.com/upload/attach/202505/967562_YUPMVPV5FGZTP2J.png)
4. 找到对应的插件并点击“安装”(Install)。

#### 初始化配置

安装完成后，通常需要进行初始化配置，主要是设置您的大模型 API Key。

1. 打开 Cline 或 RooCode 的设置界面（通常可以通过点击插件图标或使用命令面板 `Ctrl+Shift+P` / `Cmd+Shift+P` 搜索插件名称找到）。
2. 选择“使用自己的 API Key”(Use your own API key)。
![选择使用自己的 API Key](https://bbs.kanxue.com/upload/attach/202505/967562_8WSXTB7ZNY8FQA9.png)
![API Key 配置入口](https://bbs.kanxue.com/upload/attach/202505/967562_Z4N4TWURXF75CQ3.png)

#### 配置 API Key

根据您选择的 API 服务商进行配置：

- **DeepSeek:**

	- 选择 `AI Provider` 为 `DeepSeek`。
	- 在 `API Key` 字段中填入您的 DeepSeek API Key。
	- （可选）根据需要配置 `Model` 等其他参数。
	![配置 DeepSeek API Key](https://bbs.kanxue.com/upload/attach/202505/967562_7XDR6GYWND955EE.png)
	- 配置完成后，尝试发送一条消息进行测试。如果成功收到回复，则配置成功。
	![DeepSeek 配置成功测试](https://bbs.kanxue.com/upload/attach/202505/967562_UW2YZ9F7VX4P5S3.png)
- **硅基流动 (SiliconFlow) 或其他 OpenAI 兼容接口:**

	- 选择 `AI Provider` 为 `OpenAI Compatible`。
	![选择 OpenAI Compatible](https://bbs.kanxue.com/upload/attach/202505/967562_V4FCAMGHFGFAJJW.png)
	- 在 `Base URL` 字段中填入 API 服务商提供的 Base URL。对于硅基流动，通常是 `https://api.siliconflow.cn/v1`。
	- 在 `API Key` 字段中填入您的 API Key。
	- 在 `Model` 字段中填入您想使用的模型名称（例如 `Qwen/Qwen2.5-72B-Instruct`）。请确保该模型在服务商处可用。
	![配置 OpenAI 兼容接口](https://bbs.kanxue.com/upload/attach/202505/967562_6GXUKRX5U29H52R.png)
	- 如果配置遇到问题，可以查阅插件的官方文档或相关社区寻求帮助，例如参考文章：<https://deepseek.csdn.net/67b87cf03c9cd21f4cb9c548.html>

**注意:**

- Cline 和 RooCode 的配置流程类似。如果在一个插件中配置失败，可以尝试另一个。
- 使用这些插件调用大模型会消耗 Token。建议关注 API 服务商的定价和用量，或寻找优惠渠道。
- 自行部署本地模型通常效果不如云端 API，且配置复杂，不推荐初学者尝试。

### 客户端二：Claude Desktop (需付费订阅)

Claude Desktop 是 Anthropic 官方提供的桌面客户端，也支持 MCP。

- **官方文档:** <https://modelcontextprotocol.io/quickstart/user>

**安装前提:**

- 需要有效的 Claude 订阅（通常需要付费）。
- 需要安装 Node.js 和 uv (一个 Rust 编写的 Python 包管理器)。

**安装教程参考:**

- Node.js: <https://blog.csdn.net/Small_Yogurt/article/details/104968169> (或其他可靠教程)
- uv: <https://www.cnblogs.com/wang_yb/p/18635441> (或其他可靠教程)

![Claude Desktop 截图](https://bbs.kanxue.com/upload/attach/202505/967562_HH2AUGGGKZSVNTV.png)

由于可能涉及地区限制和付费订阅，这里不做详细展开。如果您已有 Claude 订阅并完成了 Node.js 和 uv 的安装，可以参考官方文档进行配置。

### 客户端三：Cursor (推荐)

Cursor 是一款强大的、以 AI 为核心的代码编辑器，内置了对多种大模型的支持，并且可以直接接入 MCP。

![Cursor 编辑器截图](https://bbs.kanxue.com/upload/attach/202505/967562_AQQHE9YSJZ8YG4H.png)

**优点:**

- 通常可以免费使用性能较好的模型（有一定额度限制）。
- 用户体验流畅，与 AI 交互自然。
- 社区活跃，有多种获取使用次数的方式（请注意合规性）。

如果您已经在使用 Cursor，那么将其作为 IDA Pro MCP 的客户端是一个非常方便的选择。

## 步骤三：部署 IDA Pro MCP (macOS)

本节将指导您如何在 macOS 环境下安装和配置 `ida-pro-mcp` 插件。

### 前置条件

- **IDA Pro 版本:** `ida-pro-mcp` 插件要求 IDA Pro 8.3 或更高版本。在 macOS 上，常见的 IDA 版本可能较旧。请确保您拥有兼容的 IDA Pro 版本（例如 9.x）。
- **Homebrew:** macOS 的包管理器。如果尚未安装，请先安装 Homebrew。

### 1. 安装 Homebrew

如果您的系统尚未安装 Homebrew，请打开终端并执行以下命令：

| 1 | `/bin/bash` `-c` `"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
|-|-|

如果遇到网络问题，可以参考国内镜像源的帮助文档进行安装：

- 清华大学开源软件镜像站: <https://mirrors.tuna.tsinghua.edu.cn/help/homebrew/>
- 其他教程参考:
	- <https://zhuanlan.zhihu.com/p/547898033>
	- <https://cloud.tencent.com/developer/article/2486985>

### 2. 安装 Python 3.11

`ida-pro-mcp` 依赖 Python 3.11 或更高版本。IDA Pro 自带的 Python 版本可能不满足要求，因此需要使用 Homebrew 单独安装。

| 1 | `brew` `install` `python@3.11` |
|-|-|

安装完成后，查看 Python 3.11 的安装信息，特别是安装路径：

| 1 | `brew info python@3.11` |
|-|-|

您会看到类似以下的输出：

| 12345678910111213141516171819202122232425 | `=``=``> python@``3.11``: stable` `3.11``.``12` `(bottled)``Interpreted, interactive,` `object``-``oriented programming language``https:``/``/``http://www.python.org``/``Installed``/``opt``/``homebrew``/``Cellar``/``python@``3.11``/``3.11``.``12` `(``3``,``306` `files,` `62.1MB``)` `*`  `# <--- 记下这个路径``Poured` `from` `bottle using the formulae.brew.sh API on` `2025``-``05``-``12` `at` `17``:``15``:``19``From: https:``/``/``mirrors.tuna.tsinghua.edu.cn``/``git``/``homebrew``/``homebrew``-``core.git``/``Formula``/``p``/``python@``3.11``.rb``License: Python``-``2.0``=``=``> Dependencies``Build: pkgconf ✔``Required: mpdecimal ✔, openssl@``3` `✔, sqlite ✔, xz ✔``=``=``> Caveats``Python` `is` `installed as``/``opt``/``homebrew``/``bin``/``python3.``11` `Unversioned` `and` `major``-``versioned symlinks `python`, `python3`, `python``-``config`, `python3``-``config`, `pip`, `pip3`, etc. pointing to```python3.``11```, `python3.``11``-``config`, `pip3.``11``` etc., respectively, are installed into``/``opt``/``homebrew``/``opt``/``python@``3.11``/``libexec``/``bin` `You can install Python packages with``pip3.``11` `install <package>``They will install into the site``-``package directory``/``opt``/``homebrew``/``lib``/``python3.``11``/``site``-``packages` `... (省略其他信息) ...` |
|-|-|

请记下 `Installed` 下方的路径，例如 `/opt/homebrew/Cellar/python@3.11/3.11.12`。这个路径在后续步骤中会用到。

### 3. (可选) 安装 Node.js 和 uv

如果您计划使用需要 Node.js 或 uv 的 MCP 客户端（如 Claude Desktop），可以通过 Homebrew 安装：

| 123456 | `brew` `install` `node``brew` `install` `uv` `# 验证安装``node --version``uv --version` |
|-|-|

### 4. 切换 IDA Pro 的 Python 环境

IDA Pro 需要知道使用哪个 Python 解释器。我们需要将其指向刚刚安装的 Python 3.11。

1. 在“访达”(Finder) 中找到您的 IDA Pro 应用程序。
2. 右键点击 IDA Pro 图标，选择“显示包内容”(Show Package Contents)。
![右键点击 IDA Pro](https://bbs.kanxue.com/upload/attach/202505/967562_AF7T2AUEH6VYQ2C.png)
![显示包内容](https://bbs.kanxue.com/upload/attach/202505/967562_98C7RGMJQ25TF2U.png)
3. 导航到 `Contents/MacOS` 目录。
4. 在此目录下打开终端（可以在访达窗口顶部右键点击路径栏，选择“新建位于文件夹位置的终端窗口”）。
5. 执行以下命令，将 `<python_install_path>` 替换为您在步骤 2 中记下的 Python 3.11 安装路径：

| 1 | `.``/idapyswitch` `--force-path <python_install_path>``/Frameworks/Python``.framework``/Versions/3``.11``/Python` |
|-|-|

**示例:** 如果您的 Python 3.11 安装路径是 `/opt/homebrew/Cellar/python@3.11/3.11.12`，则命令为：

| 1 | `.``/idapyswitch` `--force-path` `/opt/homebrew/Cellar/python``@3.11``/3``.11.12``/Frameworks/Python``.framework``/Versions/3``.11``/Python` |
|-|-|

![执行 idapyswitch 命令](https://bbs.kanxue.com/upload/attach/202505/967562_D8AWHZE4F8G53G9.png)

成功执行后，通常不会有任何输出。

### 5. 安装 `ida-pro-mcp` Python 包

现在，我们需要在 Python 3.11 环境中安装 `ida-pro-mcp` 包。

1. 打开终端，进入 Python 3.11 的 `bin` 目录。该目录通常位于您记下的安装路径下。
**示例:**

| 1 | `cd` `/opt/homebrew/Cellar/python``@3.11``/3``.11.12``/bin` |
|-|-|

![进入 Python 3.11 bin 目录](https://bbs.kanxue.com/upload/attach/202505/967562_WSRFBFJA538297K.png)
![bin 目录内容](https://bbs.kanxue.com/upload/attach/202505/967562_JEHFUX9NMXACMFM.png)
2. 使用该目录下的 `pip3.11` 安装 `ida-pro-mcp`。**请确保您的网络可以访问 GitHub。** 需要干啥我不多说了

| 1 | `.``/pip3``.11` `install` `--upgrade git+https:``//github``.com``/mrexodia/ida-pro-mcp` |
|-|-|

### 6. 安装 MCP 插件到 IDA Pro

`ida-pro-mcp` 包安装完成后，还需要将其作为插件安装到 IDA Pro 中。

1. 首先，找到 `ida-pro-mcp` 的安装位置和可执行文件路径。在 Python 3.11 的 `bin` 目录下执行：

| 1 | `.``/pip3``.11 show -f ida-pro-mcp` |
|-|-|

输出会包含类似以下信息：

| 1234567891011121314 | `Name: ida``-``pro``-``mcp``Version:` `1.3``.``0``Summary: Vibe reversing with IDA Pro``Home``-``page:``Author: mrexodia``Author``-``email:``License:``Location:` `/``opt``/``homebrew``/``lib``/``python3.``11``/``site``-``packages` `# <--- 包安装位置``Requires: mcp``Required``-``by:``Files:``..``/``..``/``..``/``bin``/``ida``-``pro``-``mcp` `# <--- 可执行文件相对路径``..``/``..``/``..``/``bin``/``idalib``-``mcp``... (省略其他文件) ...` |
|-|-|
2. 根据 `Location` 和 `Files` 中的可执行文件相对路径，拼接出 `ida-pro-mcp` 可执行文件的绝对路径。
**示例:**
`Location` 是 `/opt/homebrew/lib/python3.11/site-packages`
可执行文件相对路径是 `../../../bin/ida-pro-mcp`
拼接后的绝对路径是 `/opt/homebrew/lib/python3.11/site-packages/../../../bin/ida-pro-mcp`，这通常会解析为 `/opt/homebrew/bin/ida-pro-mcp`。

*更可靠的方法是直接使用 `which` 命令（如果 `pip` 将可执行文件放到了 PATH 中）或者直接在 Python 3.11 的 `bin` 目录下查找 `ida-pro-mcp` 可执行文件。*
假设可执行文件路径为 `/opt/homebrew/bin/ida-pro-mcp`。
3. 执行安装命令：

| 1 | `/opt/homebrew/bin/ida-pro-mcp` `--``install` |
|-|-|

*(请将 `/opt/homebrew/bin/ida-pro-mcp` 替换为您找到的实际可执行文件路径)*

![执行 ida-pro-mcp --install 命令](https://bbs.kanxue.com/upload/attach/202505/967562_FJ6SH2DS48SHSTR.png)

这个命令会将 `ida-pro-mcp` 插件复制到 IDA Pro 的插件目录中。

### 7. 检查 MCP 客户端连接

安装完成后，启动 IDA Pro。如果一切顺利，`ida-pro-mcp` 插件会自动加载。

然后，启动您选择的 MCP 客户端（Cline, RooCode, Claude Desktop, Cursor 等）。在客户端的 MCP Server 设置或连接部分，应该能看到名为 `github.com/mrexodia/ida-pro-mcp` 的服务器。

- **Cline:**
![Cline 检测到 IDA Pro MCP Server](https://bbs.kanxue.com/upload/attach/202505/967562_GN289SDWRZZYJFW.png)
- **RooCode:**
![RooCode 检测到 IDA Pro MCP Server](https://bbs.kanxue.com/upload/attach/202505/967562_VPCR34NRE93S76X.png)
- **Claude Desktop:**
![Claude Desktop 检测到 IDA Pro MCP Server](https://bbs.kanxue.com/upload/attach/202505/967562_VRZBUFXBXWKKTVJ.png)
- **Cursor:**
![Cursor 检测到 IDA Pro MCP Server](https://bbs.kanxue.com/upload/attach/202505/967562_8FWKWFX2BG22MMK.png)

### 理解 MCP 连接机制

所有支持 MCP 的客户端都遵循相同的协议。当 IDA Pro MCP 插件运行时，它会启动一个本地 HTTP 服务器（默认为 `http://localhost:13337`）。MCP 客户端通过连接这个服务器来与 IDA Pro 交互。

在客户端的设置中，通常会有一个管理 MCP Server 连接的地方。

![MCP Server 配置入口](https://bbs.kanxue.com/upload/attach/202505/967562_YQ42DPEG3QFU9XF.png)

点击配置，您可以看到类似 JSON 的配置信息，定义了可用的 MCP Server。

![MCP Server JSON 配置示例](https://bbs.kanxue.com/upload/attach/202505/967562_NKARY674MD8KYFT.png)

理论上，您可以将这个 JSON 配置复制到任何兼容 MCP 的客户端中使用。

### 实战演示：使用 Cursor 分析示例程序

让我们以一个简单的示例程序（假设名为 `xiaoyuan`）来演示如何使用 IDA Pro MCP 和 Cursor 进行分析。

**准备工作:**

1. **解决 Python 环境依赖问题:** 切换到 Python 3.11 后，您可能会发现之前安装的一些 IDA 插件（如 Keypatch，依赖 unicorn）无法使用，因为它们安装在旧的 Python 环境中。
![Keypatch 报错](https://bbs.kanxue.com/upload/attach/202505/967562_7FWFUZN3ZBD8B2B.png)
您需要使用 Python 3.11 的 `pip` (即 `pip3.11`) 重新安装这些依赖包。进入 Python 3.11 的 `bin` 目录执行：

| 1 | `.``/pip3``.11` `install` `six unicorn yara-python` `# 根据实际需要的包进行安装` |
|-|-|

![使用 pip3.11 安装依赖](https://bbs.kanxue.com/upload/attach/202505/967562_8KHV9WU6JTZNHUR.png)
安装完成后，重启 IDA Pro，插件应该就能正常加载了。
2. **启动 IDA Pro 和 MCP Server:** 打开 `xiaoyuan` 程序，并确保 IDA Pro 的 Output 窗口显示 MCP Server 已启动。

| 1 | `[MCP] Server started at http:``/``/``localhost:``13337` |
|-|-|
3. **连接 Cursor:** 打开 Cursor，确保它已连接到 `github.com/mrexodia/ida-pro-mcp` 服务器。

**开始分析:**

1. 在 IDA Pro 中，导航到您感兴趣的函数或代码段。
2. 在 Cursor 中，向 AI 提问。由于 Cursor 通过 MCP 连接了 IDA Pro，它可以自动获取 IDA 当前的上下文信息（如当前函数、地址等）。

**示例提问:** "@ida 请分析当前函数的功能"
![在 Cursor 中提问](https://bbs.kanxue.com/upload/attach/202505/967562_8J8JWJUMFMSEKX9.png)

Cursor 会将问题和从 IDA 获取的上下文一起发送给大模型。
3. **查看分析结果:** AI 模型会返回分析结果。
![Cursor 返回分析结果](https://bbs.kanxue.com/upload/attach/202505/967562_DC47CUHN35VV53Z.png)
4. **让 AI 添加注释:** 您可以进一步要求 AI 将分析结果作为注释添加到 IDA Pro 中。

**示例提问:** "@ida 将上述分析结果作为注释添加到函数起始位置"
![要求 Cursor 添加注释](https://bbs.kanxue.com/upload/attach/202505/967562_EM38WCGD7JBNXCQ.png)
5. **在 IDA Pro 中查看效果:** 切换回 IDA Pro，您会看到 AI 添加的注释。
![image](https://bbs.kanxue.com/upload/attach/202505/967562_YY56TS9BD5SNK6U.png)
![image](https://bbs.kanxue.com/upload/attach/202505/967562_4A6D6A988VCVVRA.png)

**案例分析 (xiaoyuan):**

假设 `xiaoyuan` 实现了一个哈希算法。通过上述步骤，Cursor (背后的大模型) 分析了从 IDA Pro 获取的函数代码，并给出了它的功能判断。

![Cursor 分析 xiaoyuan 为哈希函数](https://bbs.kanxue.com/upload/attach/202505/967562_78DM798Y9K7TJ76.png)

这个例子展示了 AI 如何借助 MCP 提供的上下文信息，辅助逆向工程师理解代码逻辑，甚至自动添加注释，极大地提高了分析效率。

## 步骤四：部署 IDA Pro MCP (Windows)

本节介绍在 Windows 环境下配置 IDA Pro MCP 的步骤。我们将以 IDA Pro 8.3 版本为例，因为许多用户可能仍在使用此版本以兼容其他插件。

### 1. 安装 Python 3.11

与 macOS 类似，Windows 环境也需要安装 Python 3.11 或更高版本。

1. **下载安装程序:** 访问 Python 官方网站下载 Python 3.11 的 Windows 安装程序。建议选择 64 位版本。

	- 官方下载页面: <https://www.python.org/downloads/release/python-3110/> (请选择合适的 Windows installer)
2. **运行安装程序:**

	- **重要:** 在安装界面，**不要**勾选 "Add Python 3.11 to PATH" 选项，以避免与系统中可能存在的其他 Python 版本冲突。
	- 选择 "Customize installation" (自定义安装) 或记下 "Install Now" 下方显示的默认安装路径。
	![Windows Python 安装界面](https://bbs.kanxue.com/upload/attach/202505/967562_AU5EZJJJAXKBZGE.png)
	- 完成安装。
3. **查找 Python 安装路径:** 如果您不确定安装路径，可以通过以下方法查找：

	- 在 Windows 开始菜单中搜索 "Python 3.11"。
	- 右键点击 "Python 3.11 (64-bit)" 或类似条目，选择 "打开文件所在的位置"(Open file location)。
	![开始菜单搜索 Python](https://bbs.kanxue.com/upload/attach/202505/967562_YEDT7HBWZXZKDXX.png)
	- 这通常会打开一个包含快捷方式的文件夹。再次右键点击 Python 快捷方式，选择 "打开文件所在的位置"。
	![打开快捷方式位置](https://bbs.kanxue.com/upload/attach/202505/967562_ZVAY56XK7T489T8.png)
	- 这样就能找到 Python 的实际安装目录。记下 `python.exe` 所在的完整路径。
	![找到 Python 实际路径](https://bbs.kanxue.com/upload/attach/202505/967562_UW2YZ9F7VX4P5S3.png)
	**示例路径:** `C:\Users\YourUsername\AppData\Local\Programs\Python\Python311\` (请替换 `YourUsername`)
	**`python.exe` 路径:** `C:\Users\YourUsername\AppData\Local\Programs\Python\Python311\python.exe`
	**`python3.dll` 路径:** `C:\Users\YourUsername\AppData\Local\Programs\Python\Python311\python3.dll` (或 `python311.dll`)**替代方案 (特定 IDA 版本):**
如果您使用的是集成了 Python 环境的 IDA Pro 版本，它可能自带了合适的 Python 3.11 环境。您可以直接使用其内置的 Python 路径。
![特定 IDA 内置 Python 环境](https://bbs.kanxue.com/upload/attach/202505/967562_VSD96MK8W9FCCDC.png)

### 2. 切换 IDA Pro 的 Python 环境

与 macOS 类似，需要告知 IDA Pro 使用新安装的 Python 3.11。

1. 打开命令提示符 (cmd) 或 PowerShell。
2. 执行 `idapyswitch.exe` 命令。该程序位于 IDA Pro 的安装目录下。您需要提供 IDA Pro 的路径和 Python 3.11 的 `python3.dll` (或 `python311.dll`) 的路径。

| 1 | `"C:\Path\To\Your\IDA Pro\idapyswitch.exe"` `--force-path` `"C:\Path\To\Your\Python311\python3.dll"` |
|-|-|

**请务必将命令中的路径替换为您自己的实际路径！**

**示例:**

| 1 | `"C:\Users\jiqiu2021\Desktop\IDA_Pro_v8.3_Portable\idapyswitch.exe"` `--force-path` `"C:\Users\jiqiu2021\AppData\Local\Programs\Python\Python311\python3.dll"` |
|-|-|

成功执行后通常没有输出。

### 3. 安装 `ida-pro-mcp` Python 包

使用 Python 3.11 的 `pip` 来安装 `ida-pro-mcp`。

1. 打开命令提示符或 PowerShell，并导航到 Python 3.11 的 `Scripts` 目录（如果 `pip` 不在系统 PATH 中），或者直接使用 `python.exe -m pip`。
**示例 (使用 `python.exe -m pip`):** 这里一定要能访问github 一定要做我们心里想的那件科字开头的东西

| 1 | `"C:\Path\To\Your\Python311\python.exe"` `-m pip` `install` `--upgrade git+https:``//github``.com``/mrexodia/ida-pro-mcp` |
|-|-|

*(请替换 Python 路径)*

**注意:** 确保您的网络可以访问 GitHub。如果遇到网络问题，可能需要配置 pip 的代理或使用国内镜像源。

![Windows 安装 ida-pro-mcp](https://bbs.kanxue.com/upload/attach/202505/967562_594FAEMKGKNSU2M.png)

### 4. 安装 MCP 插件到 IDA Pro

与 macOS 类似，需要执行安装命令将插件复制到 IDA Pro。

1. 找到 `ida-pro-mcp.exe` 可执行文件的路径。可以使用 `pip show -f ida-pro-mcp` 命令查找。

| 1 | `"C:\Path\To\Your\Python311\python.exe"` `-m pip show -f ida-pro-mcp` |
|-|-|

*(请替换 Python 路径)*

输出会包含类似信息：

| 123456789 | `Name: ida``-``pro``-``mcp``Version:` `1.3``.``0``...``Location: C:\Users\jiqiu2021\AppData\Local\Programs\Python\Python311\Lib\site``-``packages` `# <--- 包安装位置``...``Files:``..\..\Scripts\ida``-``pro``-``mcp.exe` `# <--- 可执行文件相对路径``..\..\Scripts\idalib``-``mcp.exe``...` |
|-|-|
2. 根据 `Location` 和 `Files` 中的相对路径，拼接出 `ida-pro-mcp.exe` 的绝对路径。
**示例:**
`Location`: `C:\Users\jiqiu2021\AppData\Local\Programs\Python\Python311\Lib\site-packages`
相对路径: `..\..\Scripts\ida-pro-mcp.exe`
绝对路径: `C:\Users\jiqiu2021\AppData\Local\Programs\Python\Python311\Scripts\ida-pro-mcp.exe`
3. 执行安装命令：

| 1 | `"C:\Path\To\Your\Python311\Scripts\ida-pro-mcp.exe"` `--``install` |
|-|-|

*(请将路径替换为实际的可执行文件路径)*

![Windows 执行安装命令](https://bbs.kanxue.com/upload/attach/202505/967562_RQ9KYGYQ46K7JMA.png)

### 5. 检查安装情况和效果展示

1. **启动 IDA Pro:** 打开 IDA Pro，加载一个文件。检查 Output 窗口是否显示 MCP Server 已启动。
![image](https://bbs.kanxue.com/upload/attach/202505/967562_64W8KY84R5JEWWS.png)
2. **启动 MCP 客户端:** 打开您选择的 MCP 客户端 (Cline, RooCode, Cursor, Claude Desktop 等)。
3. **检查连接:** 确认客户端已连接到 `github.com/mrexodia/ida-pro-mcp` 服务器。

	- **Claude Desktop:**
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_YJCY5RRCQPYXUW8.png)
	- **Cursor:**
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_CMKFVT6F9RBN262.png)
	- **Cline:**
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_NA3YEHKSK5XD3NX.png)
4. **进行测试:** 尝试使用客户端与 IDA Pro 交互，例如让 AI 分析函数或添加注释。

	- **Claude 示例:**
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_3NHU5W4J4CZBN6K.png)
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_B2ZESSQ65VNDMNB.png)
	- **Cline 示例:**
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_KMUPMGYVGDXRD7J.png)
	![image](https://bbs.kanxue.com/upload/attach/202505/967562_A3Y2XCX28SKRHEA.png)

## 结语

AI 的浪潮已经到来，将其融入逆向工程的工作流是大势所趋。IDA Pro MCP 为我们提供了一个强大的框架，将 AI 的分析能力与 IDA Pro 的专业功能相结合。

希望本教程能帮助您顺利配置并开始使用这一利器。我们鼓励您积极探索，将 AI 技术应用于实际的逆向分析任务中，发掘更多可能性。

我是棕熊，爱你么么么哒～ 上面的文章被ai优化过了，原稿在附件的压缩包里，html是优化过的文章的。

上传的附件：
- libRequestEncoder.so

（898.03kb，232次下载）
- 一文带你使用IDA Pro MCP进行逆向.md.zip

（5.54MB，594次下载）

---

# 回复

## 回复 by 快乐的小跳蛙 (#2)

*2025-5-13 09:21*

前排膜拜下

## 回复 by zzw_xjx (#3)

*2025-5-13 09:24*

前排膜拜下

## 回复 by 简单的简单 (#4)

*2025-5-13 09:48*

前排膜拜下

## 回复 by 非洲棒棒 (#5)

*2025-5-13 09:56*

6

## 回复 by yangshuang (#6)

*2025-5-13 10:13*

6

## 回复 by KingSelyF (#7)

*2025-5-13 10:18*

太强了

## 回复 by wangzehua (#8)

*2025-5-13 10:21*

66666666

## 回复 by Ram98 (#9)

*2025-5-13 10:22*

666

## 回复 by 涿州飞神 (#10)

*2025-5-13 10:26*

66666

## 回复 by 放手一搏 (#11)

*2025-5-13 10:28*

膜拜大佬

## 回复 by 只爱夜巴黎 (#12)

*2025-5-13 10:33*

膜拜大佬

## 回复 by Xxxxczh (#13)

*2025-5-13 10:39*

6666

## 回复 by baitongling (#14)

*2025-5-13 10:53*

1

## 回复 by 丶咖啡猫丶 (#15)

*2025-5-13 10:54*

666

## 回复 by kreedz (#16)

*2025-5-13 10:54*

膜拜大佬

## 回复 by 风晨小生 (#17)

*2025-5-13 10:56*

前排膜拜下

## 回复 by ONewTach (#18)

*2025-5-13 10:57*

666

## 回复 by JOE_TR13 (#19)

*2025-5-13 11:01*

666

## 回复 by mb_bcsiicbe (#20)

*2025-5-13 11:02*

666

## 回复 by mb_lizfxfno (#21)

*2025-5-13 11:14*

666

## 回复 by jiaoshichun (#22)

*2025-5-13 11:16*

666

## 回复 by mb_ldbucrik (#23)

*2025-5-13 11:21*

感谢分享

## 回复 by supercuglong (#24)

*2025-5-13 11:27*

6666666666666666

## 回复 by koflfy (#25)

*2025-5-13 11:31*

mark，追佬牛逼

## 回复 by mJqalJqN (#26)

*2025-5-13 11:31*

1

## 回复 by kxblah (#27)

*2025-5-13 11:53*

koflfy   1
  25 楼
mark，追佬牛逼

## 回复 by uni7corn (#28)

*2025-5-13 12:29*

66666666

## 回复 by eroy (#29)

*2025-5-13 12:47*

前排膜拜下

## 回复 by study0x1 (#30)

*2025-5-13 13:27*

666

## 回复 by matrump (#31)

*2025-5-13 14:05*

追追追追佬牛逼

## 回复 by wake0p (#32)

*2025-5-13 14:20*

学习了，感谢大佬分享

## 回复 by ngiokweng (#33)

*2025-5-13 14:28*

![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by wx_kx26570 (#34)

*2025-5-13 14:36*

回复或点赞可查看完整内容

## 回复 by 0x00day (#35)

*2025-5-13 14:57*

誓死追随大佬

## 回复 by mb_tbvvbfot (#36)

*2025-5-13 16:03*

膜拜棕熊大佬！！

## 回复 by C0rax (#37)

*2025-5-13 16:49*

学习一下

## 回复 by mb_jpkymxtc (#38)

*2025-5-13 17:21*

mark，牛逼。

## 回复 by SnowRen (#39)

*2025-5-13 17:26*

膜拜大佬

## 回复 by yezheyu (#40)

*2025-5-13 17:29*

感谢大佬，测试成功![image](https://bbs.kanxue.com/upload/attach/202505/840122_R9JTQBBXZFTWQDF.webp)

## 回复 by gjianbo (#41)

*2025-5-13 17:39*

楼主历害,感谢分享

## 回复 by 院士 (#42)

*2025-5-13 19:25*

厉害的大佬。

## 回复 by 暴强 (#43)

*2025-5-13 20:47*

牛，好东西！！！！

## 回复 by mb_gninzeph (#44)

*2025-5-13 22:02*

1

## 回复 by wx_hook_996 (#45)

*2025-5-13 22:24*

6666666666666666

## 回复 by fujing (#46)

*2025-5-13 22:25*

谢你的贡献，论坛因你而更加精彩！

## 回复 by mb_qrlsimls (#47)

*2025-5-13 22:29*

mark，追佬牛逼

## 回复 by parktest0325 (#48)

*2025-5-13 23:22*

66666666666

## 回复 by kingking888 (#49)

*2025-5-14 00:58*

666

## 回复 by nszy007 (#50)

*2025-5-14 01:36*

看看完整内容

## 回复 by 低调的大头 (#51)

*2025-5-14 08:27*

厉害！

## 回复 by loqich (#52)

*2025-5-14 08:55*

感谢分享

## 回复 by Roger (#53)

*2025-5-14 09:17*

mark

## 回复 by sisess (#54)

*2025-5-14 09:27*

666

## 回复 by webappsec (#55)

*2025-5-14 09:35*

学习一下

## 回复 by mb_qimctavn (#56)

*2025-5-14 09:37*

为你点赞！

## 回复 by email123 (#57)

*2025-5-14 10:19*

膜拜大佬

## 回复 by guijingwen (#58)

*2025-5-14 10:23*

666

## 回复 by nevinhappy (#59)

*2025-5-14 10:32*

666

## 回复 by mb_shzsxtje (#60)

*2025-5-14 10:32*

感谢大佬分享

## 回复 by pxhb (#61)

*2025-5-14 11:26*

666666666

## 回复 by chengtao (#62)

*2025-5-14 11:44*

大佬威武，与时俱进

## 回复 by 随风而行aa (#63)

*2025-5-14 11:54*

看看

## 回复 by jdong (#64)

*2025-5-14 14:01*

mark，追佬牛逼

## 回复 by 编程两年半 (#65)

*2025-5-14 14:03*

6666666

## 回复 by GEKEZYX (#66)

*2025-5-14 14:13*

666

## 回复 by zylyy (#67)

*2025-5-14 14:14*

1

## 回复 by G0Fl1er (#68)

*2025-5-14 14:47*

学习一下![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by MaYil (#69)

*2025-5-14 15:49*

感谢分享

## 回复 by wx_AI图灵小助手 (#70)

*2025-5-14 16:19*

666666666666666666

## 回复 by enze (#71)

*2025-5-14 16:27*

666

## 回复 by Am1re (#72)

*2025-5-14 17:27*

膜拜大佬

## 回复 by Editor (#73)

*2025-5-14 17:46*

![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by mb_uvyukvot (#74)

*2025-5-14 18:30*

1

## 回复 by 王叔叔 (#75)

*2025-5-14 19:07*

![image](https://bbs.kanxue.com/view/img/face/003.gif)6666666666666

## 回复 by 末日大哥 (#76)

*2025-5-14 19:08*

666学习一下

## 回复 by mb_sngdtqxn (#77)

*2025-5-14 19:45*

大大减少逆向的门槛

## 回复 by 奶思兔 (#78)

*2025-5-14 21:14*

将理论转化为现实，厉害了！

## 回复 by wx_错爱 (#79)

*2025-5-14 22:55*

感谢分享

## 回复 by Evan_422 (#80)

*2025-5-15 00:59*

mark一下

## 回复 by luckbbs (#81)

*2025-5-15 09:19*

膜拜大佬

## 回复 by mb_tsjjaidx (#82)

*2025-5-15 09:42*

膜拜大佬！

## 回复 by 肖安111 (#83)

*2025-5-15 09:44*

666

## 回复 by αβγδεξπ (#84)

*2025-5-15 10:00*

感谢分享

## 回复 by 蓝色水瓶 (#85)

*2025-5-15 10:03*

mark，牛人

## 回复 by AK1988DA (#86)

*2025-5-15 10:27*

1

## 回复 by lackone (#87)

*2025-5-15 10:51*

mark

## 回复 by mb_jnmxfjku (#88)

*2025-5-15 11:13*

666

## 回复 by iBa0 (#89)

*2025-5-15 11:33*

AI脑容量太小了 实际根本没啥用吧

## 回复 by zgm1210006 (#90)

*2025-5-15 11:37*

真是太强了，感谢讲解

## 回复 by mb_eizetlni (#91)

*2025-5-15 12:57*

mark，追佬牛逼

## 回复 by option (#92)

*2025-5-15 13:13*

学习AI的应用

## 回复 by dig_grave (#93)

*2025-5-15 13:49*

mark

## 回复 by 青丝梦 (#94)

*2025-5-15 14:39*

111111111111111

## 回复 by berh (#95)

*2025-5-15 14:47*

666666666

## 回复 by 金奔腾 (#96)

*2025-5-15 15:30*

学习学习

## 回复 by mb_gnehsaia (#97)

*2025-5-15 15:49*

6

## 回复 by Sin hx (#98)

*2025-5-15 16:03*

码

## 回复 by 大魔头 (#99)

*2025-5-15 16:32*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_homnvxow (#100)

*2025-5-15 16:58*

666

## 回复 by iforgiven (#101)

*2025-5-15 17:56*

![image](https://bbs.kanxue.com/view/img/face/079.gif)666

## 回复 by 雪很冷1 (#102)

*2025-5-16 02:43*

为你点赞！

## 回复 by mb_uekrtlsh (#103)

*2025-5-16 03:11*

666

## 回复 by 杭州李白 (#104)

*2025-5-16 11:09*

666

## 回复 by likeke (#105)

*2025-5-16 13:49*

666

## 回复 by gudubuku (#106)

*2025-5-16 15:45*

mark，追佬牛逼

## 回复 by xianhuimin (#107)

*2025-5-16 15:46*

学习下，

## 回复 by X66iaM (#108)

*2025-5-16 16:00*

sixsixsix

## 回复 by guols (#109)

*2025-5-16 16:31*

ok

## 回复 by 墨穹呢 (#110)

*2025-5-16 22:19*

感谢分享

## 回复 by fengyunabc (#111)

*2025-5-17 00:14*

感谢分享。

## 回复 by 绿林科技 (#112)

*2025-5-17 00:40*

谢谢分享！

## 回复 by brain_Z (#113)

*2025-5-17 12:47*

牛逼

## 回复 by mb_tvmcbdnl (#114)

*2025-5-17 13:58*

查看学习

## 回复 by 街道办事处 (#115)

*2025-5-17 14:43*

666

## 回复 by suiyingjie (#116)

*2025-5-17 14:47*

666

## 回复 by zhangtheo (#117)

*2025-5-17 15:36*

666666666

## 回复 by 程序Dylan (#118)

*2025-5-17 15:39*

mark，牛逼 ，赞！过来学习一下。感谢大佬分享。

## 回复 by 天涯共何时 (#119)

*2025-5-17 15:53*

666先赞后看·

## 回复 by stonenb (#120)

*2025-5-17 16:26*

厉害，谢谢分享。

## 回复 by frmzero (#121)

*2025-5-17 16:53*

学习一下，谢谢分享。

## 回复 by sabason (#122)

*2025-5-17 21:15*

不错

## 回复 by cobe (#123)

*2025-5-17 21:58*

6666

## 回复 by 雅鸦歌 (#124)

*2025-5-17 22:20*

mark

## 回复 by mb_weyfdhks (#125)

*2025-5-18 12:38*

mark

## 回复 by fmam (#126)

*2025-5-18 13:27*

666

## 回复 by mb_ifjlatem (#127)

*2025-5-18 16:16*

前排膜拜下

## 回复 by wx_6ang (#128)

*2025-5-18 23:10*

666![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by Tee8088 (#129)

*2025-5-19 08:08*

要学习一下

## 回复 by eJinX (#130)

*2025-5-19 08:15*

学习强国

## 回复 by haogl (#131)

*2025-5-19 08:53*

回复来看看，先谢过楼主！

## 回复 by fangliangz (#132)

*2025-5-19 09:50*

666

## 回复 by ztxbeyond (#133)

*2025-5-19 14:18*

感谢分享

## 回复 by ATrueMan (#134)

*2025-5-19 19:39*

study

## 回复 by 英俊 (#135)

*2025-5-19 19:57*

学习一下。

## 回复 by console_ (#136)

*2025-5-20 08:03*

1111

## 回复 by ovo_帮我不c (#137)

*2025-5-20 09:34*

66

## 回复 by mb_ohgmgmnu (#138)

*2025-5-20 09:35*

666

## 回复 by 本菜很懒 (#139)

*2025-5-20 09:39*

牛了个牛

## 回复 by 乙太 (#140)

*2025-5-20 10:15*

nb

## 回复 by MisCy (#141)

*2025-5-20 10:16*

留个脚印????，后续慢慢学习

## 回复 by xxyiyi (#142)

*2025-5-20 10:33*

紧跟时代潮流

## 回复 by lookaside (#143)

*2025-5-20 16:03*

666

## 回复 by mb_hdptcgkk (#144)

*2025-5-20 17:40*

6

## 回复 by mb_dybhojzi (#145)

*2025-5-20 19:36*

666666666

## 回复 by 郭伟_547157 (#146)

*2025-5-21 13:24*

mark，追佬牛逼

## 回复 by wx_满满的水 (#147)

*2025-5-21 14:15*

666

## 回复 by 孤梦拾遗 (#148)

*2025-5-21 14:31*

膜拜下

## 回复 by 橄榄绿o (#149)

*2025-5-21 15:05*

前排膜拜下

## 回复 by BRUCEVIP (#150)

*2025-5-22 00:53*

666

## 回复 by git_35205FeghPS (#151)

*2025-5-22 09:37*

太厉害了

## 回复 by 李小木子 (#152)

*2025-5-24 07:44*

6

## 回复 by mb_dgsueauw (#153)

*2025-5-24 15:27*

666

## 回复 by fenfei331 (#154)

*2025-5-24 21:47*

666

## 回复 by mb_wqxcnczj (#155)

*2025-5-25 17:59*

666666

## 回复 by mb_wpnapfpn (#156)

*2025-5-25 19:04*

6666666666666666

## 回复 by jiegua (#157)

*2025-5-26 11:18*

666

## 回复 by gusong (#158)

*2025-5-26 11:22*

感谢楼主分享

## 回复 by Gryffindoss (#159)

*2025-5-26 15:46*

66666

## 回复 by mb_xfywpeij (#160)

*2025-5-26 15:59*

学习一下，谢谢分享。

## 回复 by 梓曰 (#161)

*2025-5-26 16:28*

666

## 回复 by lizhenzhe (#162)

*2025-5-26 17:14*

感谢分享

## 回复 by mb_kglcxzom (#163)

*2025-5-26 17:18*

感谢分享

## 回复 by wx_小豆豆 (#164)

*2025-5-26 20:58*

1

## 回复 by doujia (#165)

*2025-5-27 08:40*

666

## 回复 by szukodf (#166)

*2025-5-27 09:30*

学习了，谢谢大佬

## 回复 by mb_ucbmgqsi (#167)

*2025-5-27 17:24*

666

## 回复 by mb_ykavguun (#168)

*2025-5-27 19:33*

666

## 回复 by pianpu (#169)

*2025-5-28 09:19*

学习一下

## 回复 by mb_ghaqakki (#170)

*2025-5-28 13:41*

6666

## 回复 by 茅山小僧 (#171)

*2025-5-28 14:16*

学习一下

## 回复 by onwyc123 (#172)

*2025-5-28 14:33*

66

## 回复 by 空谈误国 (#173)

*2025-5-28 16:47*

mark

## 回复 by wx_！_336 (#174)

*2025-5-28 22:29*

1

## 回复 by CH13hh (#175)

*2025-5-28 22:34*

tql

## 回复 by myios (#176)

*2025-5-28 22:48*

6666666666

## 回复 by mb_enqsfnpo (#177)

*2025-5-29 09:11*

mark 666

## 回复 by mb_syeqamnt (#178)

*2025-5-29 14:45*

NB

## 回复 by mb_hhehkqkw (#179)

*2025-5-29 16:26*

66666666

## 回复 by cnhuaWu (#180)

*2025-5-30 15:44*

666666

## 回复 by daxia200N (#181)

*2025-5-30 15:51*

66666666

## 回复 by git_74492rayinaw (#182)

*2025-5-30 16:39*

6666

## 回复 by Kokoi (#183)

*2025-5-30 19:00*

感谢分享

## 回复 by mb_bdcmralb (#184)

*2025-5-31 15:22*

666666666

## 回复 by mb_cawopqfr (#185)

*2025-5-31 17:41*

1

## 回复 by homea_qwq (#186)

*2025-5-31 20:45*

1

## 回复 by mb_fidppcok (#187)

*2025-6-2 11:32*

前排膜拜下

## 回复 by lbunknow (#188)

*2025-6-3 10:14*

无敌

## 回复 by fzyspark (#189)

*2025-6-3 11:16*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by b1n_ (#190)

*2025-6-3 13:36*

追佬牛逼

## 回复 by Lovino流诺 (#191)

*2025-6-4 08:55*

666666666666666666

## 回复 by wx_南瓜豆腐 (#192)

*2025-6-4 09:59*

牛牛牛

## 回复 by xychzq (#193)

*2025-6-4 14:50*

可以

## 回复 by LeeLinux (#194)

*2025-6-4 16:50*

66666666666666666666666

## 回复 by 财神爷999 (#195)

*2025-6-5 19:13*

很好，用上了

## 回复 by hansion丶 (#196)

*2025-6-6 09:23*

666666666666

## 回复 by wx_huhu_859 (#197)

*2025-6-7 00:43*

1

## 回复 by musha (#198)

*2025-6-7 07:13*

感谢分享  666666666666

## 回复 by mb_drpshfdg (#199)

*2025-6-7 10:14*

牛逼

## 回复 by asuralove (#200)

*2025-6-7 21:41*

666

## 回复 by mb_uydiuxjd (#201)

*2025-6-8 06:02*

mark，追大佬牛逼

## 回复 by JadeFox (#202)

*2025-6-8 23:25*

666666

## 回复 by wx_D_755717 (#203)

*2025-6-9 15:38*

666666666

## 回复 by wois杨 (#204)

*2025-6-9 15:47*

感谢分享

## 回复 by wx_nnn7h (#205)

*2025-6-9 15:57*

6666666666666666

## 回复 by fireflypro (#206)

*2025-6-9 16:06*

這個討論對我很有幫助，謝謝！

## 回复 by mb_wgjydnix (#207)

*2025-6-9 17:50*

666666

## 回复 by mb_xdnobbtp (#208)

*2025-6-9 21:01*

666

## 回复 by suexian (#209)

*2025-6-9 22:18*

666

## 回复 by mb_kclqqlmy (#210)

*2025-6-10 00:25*

膜拜

## 回复 by 李刚ctt (#211)

*2025-6-10 10:46*

![image](https://bbs.kanxue.com/view/img/face/004.gif)666

## 回复 by Tomtree (#212)

*2025-6-10 15:16*

666

## 回复 by 烬奇小云 (#213)

*2025-6-10 15:26*

666

## 回复 by mb_lqtnraus (#214)

*2025-6-11 15:45*

感谢分享

## 回复 by git_56701jackt88 (#215)

*2025-6-11 22:40*

666666

## 回复 by 呱呱呱000 (#216)

*2025-6-12 14:44*

666

## 回复 by mb_euphpkii (#217)

*2025-6-12 15:30*

666

## 回复 by 膨胀 (#218)

*2025-6-12 17:12*

>
> [WMBa0](https://bbs.kanxue.com/user-971547.htm)
>
>  AI脑容量太小了 实际根本没啥用吧
>
>

实际就是ai在一本正经的胡说八道

## 回复 by git_94819guofudong (#219)

*2025-6-12 18:11*

666

## 回复 by wx_h0p4 (#220)

*2025-6-13 09:15*

感谢分享

## 回复 by tcc0lin (#221)

*2025-6-13 10:31*

1

## 回复 by Azhan_ (#222)

*2025-6-13 10:58*

mark，追佬牛逼

## 回复 by mb_udqqrnhy (#223)

*2025-6-13 11:32*

666

## 回复 by 菜鸟也想飞 (#224)

*2025-6-13 14:19*

感谢分享与写作！

## 回复 by 7zai (#225)

*2025-6-13 15:13*

太厉害了，膜拜

## 回复 by rm_rf_* (#226)

*2025-6-13 17:41*

66666

## 回复 by 韩厉 (#227)

*2025-6-14 01:20*

6

## 回复 by luckyl (#228)

*2025-6-14 03:38*

有了AI加持分析变得更加高效了~![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by 如一 (#229)

*2025-6-15 16:58*

666

## 回复 by mb_jwvcvtfi (#230)

*2025-6-15 17:10*

6666666

## 回复 by wx_小丑鱼 (#231)

*2025-6-16 09:40*

mark

## 回复 by wx_Jeff (#232)

*2025-6-16 14:48*

1

## 回复 by joy0s (#233)

*2025-6-16 14:49*

666

## 回复 by eewwqq (#234)

*2025-6-17 02:36*

感觉分享，按照教程学习！

## 回复 by 蜂助手HR (#235)

*2025-6-17 10:16*

佬，看广州岗位吗？

## 回复 by 老衲很年轻 (#236)

*2025-6-17 10:59*

666,万物皆可MCP

## 回复 by ZACSN12 (#237)

*2025-6-17 16:41*

6666

## 回复 by Ddddz (#238)

*2025-6-18 17:02*

666

## 回复 by mb_dobsqwmv (#239)

*2025-6-19 14:18*

前排膜拜下

## 回复 by wujimaa (#240)

*2025-6-19 16:47*

5666666

## 回复 by carlcurist (#241)

*2025-6-20 16:34*

感谢分享

## 回复 by 晨曦。 (#242)

*2025-6-21 13:33*

非常有用，目前还有白嫖方式 使用TraeCN来启动mcp 免费调用

## 回复 by forpubtest (#243)

*2025-6-21 15:47*

666

## 回复 by KKKKKXXXXX (#244)

*2025-6-21 16:24*

真不错，学习了

## 回复 by 无语了啊～嗝 (#245)

*2025-6-21 17:40*

666

## 回复 by wx_王志红 (#246)

*2025-6-23 09:39*

为你点赞！

## 回复 by wx_最爱老大 (#247)

*2025-6-23 14:31*

看看看看

## 回复 by wx_kx56309 (#248)

*2025-6-23 16:26*

66666666666666666666

## 回复 by mb_ajgkdedt (#249)

*2025-6-24 19:59*

11

## 回复 by logeye (#250)

*2025-6-24 20:22*

mark，追佬牛逼

## 回复 by mb_jdkgqohe (#251)

*2025-6-24 20:34*

66666666

## 回复 by Kvancy (#252)

*2025-6-26 10:14*

感谢分享

## 回复 by wx_小伟_338 (#253)

*2025-6-26 10:27*

学习学习

## 回复 by 林动11 (#254)

*2025-6-26 10:33*

太强了

## 回复 by wx_papaya (#255)

*2025-6-27 11:52*

感谢分享

## 回复 by daymissed (#256)

*2025-6-27 17:24*

刚好学习一波,感谢分享

## 回复 by 斑斓夜话 (#257)

*2025-6-27 17:28*

Mark,真的非常详细.

## 回复 by baronSDI (#258)

*2025-6-28 17:08*

自然语言调用万物的时代

## 回复 by XJ。 (#259)

*2025-7-1 20:34*

666

## 回复 by 小白指挥 (#260)

*2025-7-1 22:54*

666

## 回复 by lidongld (#261)

*2025-7-2 11:32*

6666666666666666

## 回复 by mb_whnzcvcj (#262)

*2025-7-3 14:55*

牛

## 回复 by invywyh (#263)

*2025-7-9 09:31*

6666666666666666666666666666

## 回复 by mb_xdqrjlmu (#264)

*2025-7-10 01:10*

看看支持支持

## 回复 by 滴滴滴滴滴 (#265)

*2025-7-10 01:22*

1

## 回复 by 万事笔通 (#266)

*2025-7-10 14:39*

感谢分享

## 回复 by whe (#267)

*2025-7-10 16:45*

6666666666666666

## 回复 by 特洛伊Troye (#268)

*2025-7-11 10:06*

太强了

## 回复 by D.roooock (#269)

*2025-7-11 10:12*

mark，追佬牛逼

## 回复 by batter (#270)

*2025-7-11 10:21*

牛贴留印，感谢教学。

## 回复 by shush (#271)

*2025-7-11 10:26*

啊

## 回复 by mb_wuevwbec (#272)

*2025-7-11 10:57*

感谢分享

## 回复 by maxcl (#273)

*2025-7-11 15:19*

谢谢分享

## 回复 by 安小卓 (#274)

*2025-7-13 12:30*

感谢大佬，谢谢

## 回复 by wx_掉伞小能手 (#275)

*2025-7-13 23:33*

mark，追佬牛逼

## 回复 by Eng伦 (#276)

*2025-7-15 01:30*

666

## 回复 by mb_ybvqgbkl (#277)

*2025-7-15 11:28*

666

## 回复 by wx_辉_740 (#278)

*2025-7-16 13:52*

mark，追佬牛逼

## 回复 by 自称宅男 (#279)

*2025-7-16 17:27*

大

## 回复 by mb_nszigedb (#280)

*2025-7-17 13:44*

66666

## 回复 by 星雨心愿 (#281)

*2025-7-21 11:33*

与时俱进

## 回复 by Youngs (#282)

*2025-7-21 15:47*

mark

## 回复 by 墨殇yl (#283)

*2025-7-21 18:36*

1

## 回复 by 龙岱客 (#284)

*2025-7-22 10:56*

谢谢分享，准备上手试试

## 回复 by 终身英俊帅 (#285)

*2025-7-22 23:27*

mark，追佬牛逼

## 回复 by AcheronHana (#286)

*2025-7-23 11:59*

感谢分享啊啊啊啊啊啊

## 回复 by shawn996 (#287)

*2025-7-23 16:34*

mark，追佬牛逼

## 回复 by mb_ndttieme (#288)

*2025-7-23 16:48*

你的帖子非常有用，感谢分享！

## 回复 by wx_大表哥_160292 (#289)

*2025-7-24 10:34*

6

## 回复 by 新青年 (#290)

*2025-7-24 15:56*

大佬，按照步骤操作了，但是@ida 并没有相关的东西，![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_ilyviizj (#291)

*2025-7-26 13:20*

666

## 回复 by chionyuna (#292)

*2025-7-28 16:18*

666

## 回复 by log2 (#293)

*2025-7-28 22:05*

6

## 回复 by cppbbc (#294)

*2025-7-29 09:50*

6666

## 回复 by HEX010 (#295)

*2025-7-29 14:04*

非常棒精细的讲解

## 回复 by SkyerHw (#296)

*2025-7-29 15:17*

666

## 回复 by 西埔 (#297)

*2025-7-30 19:22*

666666，学习学习

## 回复 by cowkx (#298)

*2025-8-1 15:13*

感谢分享

## 回复 by mb_afnbxjqv (#299)

*2025-8-1 15:20*

感谢分享

## 回复 by yyyyy——— (#300)

*2025-8-4 15:07*

6666

## 回复 by Mr_hello (#301)

*2025-8-4 19:22*

牛逼

## 回复 by mb_irhdtnzm (#302)

*2025-8-5 08:19*

i

## 回复 by 1ocker (#303)

*2025-8-5 13:55*

cy

## 回复 by mb_vrsbdpln (#304)

*2025-8-5 15:17*

666

## 回复 by lazybulazy (#305)

*2025-8-5 15:44*

牛牛牛

## 回复 by SwordWorth (#306)

*2025-8-5 22:26*

赞美之词溢于言表

## 回复 by mb_drpveoin (#307)

*2025-8-7 04:20*

1

## 回复 by git_27068Lych1e1 (#308)

*2025-8-8 17:59*

感谢

## 回复 by mb_gsdrmtak (#309)

*2025-8-11 03:55*

mark da   佬牛逼

## 回复 by hanjiefang (#310)

*2025-8-11 09:32*

感谢分享

## 回复 by 飆汗吉米 (#311)

*2025-8-11 22:26*

感谢分享

## 回复 by OneShell (#312)

*2025-8-12 09:43*

mark一个，感谢大佬

## 回复 by wx_Test_620798 (#313)

*2025-8-13 10:35*

tql

## 回复 by mb_eltlxelx (#314)

*2025-8-13 14:18*

66666

## 回复 by mb_iunhvspv (#315)

*2025-8-13 14:30*

太强了把

## 回复 by jmpcall (#316)

*2025-8-13 15:34*

棕熊医生666

## 回复 by 孤独的街 (#317)

*2025-8-13 15:44*

追佬牛逼

## 回复 by zx_930374 (#318)

*2025-8-13 21:49*

666

## 回复 by 梦在飞翔SHS (#319)

*2025-8-13 22:10*

6666

## 回复 by mb_qupzepyf (#320)

*2025-8-14 09:01*

6666666666666666

## 回复 by mb_donutrph (#321)

*2025-8-14 11:15*

666

## 回复 by kx_211103 (#322)

*2025-8-14 12:51*

66666666666

## 回复 by mb_pdeivpxj (#323)

*2025-8-14 17:02*

大佬nb！！！

## 回复 by 山竹笠 (#324)

*2025-8-15 10:50*

666

## 回复 by mb_wpjwiixj (#325)

*2025-8-15 22:52*

好的，我约到问题了，  File "C:\Users\liu\source\repos\ida-pro-mcp\src\ida_pro_mcp\server.py", line 358, in install_mcp_servers
    data = f.read().strip()
           ^^^^^^^^
UnicodeDecodeError: 'gbk' codec can't decode byte 0xa4 in position 152: illegal multibyte sequence，翻译下错误在哪，怎么解决

## 回复 by mb_evdvtmnq (#326)

*2025-8-17 00:23*

感谢大佬分享

## 回复 by mb_wpjwiixj (#327)

*2025-8-17 14:30*

照着这个办法，成功安装了两台电脑，但是第三台死活不行，就是到了vscode和cursor上就是没有ida-pro-mcp的配置文件，也没有安装上。这是怎么回事。

## 回复 by mb_mqqcehlc (#328)

*2025-8-17 15:46*

是追老？那有救了

## 回复 by mb_uktygsmq (#329)

*2025-8-18 01:35*

666

## 回复 by hackdaliu (#330)

*2025-8-18 10:12*

mark一下，有空学习

## 回复 by fkueihcy (#331)

*2025-8-18 16:14*

感谢分享

## 回复 by Old_Yuan (#332)

*2025-8-18 16:36*

666

## 回复 by mb_harsdzld (#333)

*2025-8-18 19:07*

666

## 回复 by number_Z (#334)

*2025-8-19 10:27*

感谢大佬分享

## 回复 by wen666 (#335)

*2025-8-19 14:06*

6

## 回复 by Q老Q (#336)

*2025-8-19 15:55*

6

## 回复 by 彼此_277064 (#337)

*2025-8-19 18:32*

6666666

## 回复 by rongkao (#338)

*2025-8-20 06:08*

mark，追佬牛逼mark，追佬牛逼

## 回复 by 金钱蒲 (#339)

*2025-8-20 09:31*

好好学习天天向上

## 回复 by mb_hkuaavkk (#340)

*2025-8-20 13:49*

good

## 回复 by mb_tqikhame (#341)

*2025-8-20 15:35*

大模型的tokens很贵，代码很多，分析一个估计就得欠费了

## 回复 by 晓欣 (#342)

*2025-8-22 22:04*

有没有PDF文档下载看呢？能不能自己搭本地MCP呢

## 回复 by Brinmon (#343)

*2025-8-24 13:48*

666

## 回复 by wx_铁牛 (#344)

*2025-8-25 12:06*

AI抢饭碗了

## 回复 by 阿钟wilsion (#345)

*2025-8-25 14:45*

kakakak

## 回复 by mb_nrghcjsb (#346)

*2025-8-27 15:26*

大佬研究的真细，学习

## 回复 by hejincai (#347)

*2025-8-28 17:01*

666

## 回复 by apxar (#348)

*2025-8-28 19:53*

66

## 回复 by smile1110 (#349)

*2025-8-29 01:15*

6666

## 回复 by mb_fnafvzmz (#350)

*2025-8-29 03:10*

黑客在线接单QQ3917936792

## 回复 by lweizhoucn (#351)

*2025-8-29 12:03*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_hocfusch (#352)

*2025-8-29 16:04*

6666666666666

## 回复 by mb_wmwmyzqz (#353)

*2025-8-30 17:25*

666

## 回复 by 九月心情 (#354)

*2025-8-30 18:03*

mark,学习学习

## 回复 by Sin_hx (#355)

*2025-9-1 14:33*

nb

## 回复 by mb_qqihqaoo (#356)

*2025-9-2 12:47*

6666666

## 回复 by Kris1337 (#357)

*2025-9-2 20:17*

![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by FJYC (#358)

*2025-9-4 09:31*

666666

## 回复 by ftpgrtmrj (#359)

*2025-9-6 01:06*

mark，追佬牛逼

## 回复 by mb_pmgifpme (#360)

*2025-9-6 13:50*

1

## 回复 by Cr2zy (#361)

*2025-9-6 14:29*

666

## 回复 by mb_mkxcxdeq (#362)

*2025-9-7 02:03*

标记了一处地点

## 回复 by mb_hfpmtthz (#363)

*2025-9-7 09:17*

6666

## 回复 by 威兹曼 (#364)

*2025-9-7 09:53*

感谢分享

## 回复 by 我不在冷 (#365)

*2025-9-7 10:00*

mark

## 回复 by mb_akowpmjs (#366)

*2025-9-7 23:36*

6666

## 回复 by 那就去个名字 (#367)

*2025-9-8 13:57*

学习了

## 回复 by mb_zamcrfks (#368)

*2025-9-8 14:47*

666

## 回复 by mb_xojpdlxv (#369)

*2025-9-8 14:59*

666

## 回复 by mb_kbvfxrln (#370)

*2025-9-8 17:32*

强

## 回复 by 乐枫大大 (#371)

*2025-9-10 21:54*

666

## 回复 by bedaway (#372)

*2025-9-11 10:45*

6666

## 回复 by mb_zsllxbhg (#373)

*2025-9-11 15:12*

牛逼牛逼

## 回复 by Doorsman (#374)

*2025-9-12 15:29*

强

## 回复 by ch3nmo (#375)

*2025-9-12 17:18*

6

## 回复 by LuciferArmy (#376)

*2025-9-12 18:06*

666

## 回复 by 流星沦落 (#377)

*2025-9-12 23:04*

牛逼牛逼牛逼

## 回复 by xxjj678 (#378)

*2025-9-12 23:11*

666

## 回复 by GeneralN (#379)

*2025-9-13 14:35*

6666666666666666

## 回复 by mb_ceolvvry (#380)

*2025-9-13 15:08*

666

## 回复 by quanIngo (#381)

*2025-9-13 16:31*

学习一下

## 回复 by 金戈铁马fly (#382)

*2025-9-13 17:39*

认真学习，感谢分享，大佬牛叉

## 回复 by mb_fbkkoldx (#383)

*2025-9-13 20:35*

????，膜拜下

## 回复 by mb_heqvlbnm (#384)

*2025-9-13 23:34*

1

## 回复 by mb_oexcbhhi (#385)

*2025-9-15 12:54*

666

## 回复 by mb_goqnmbff (#386)

*2025-9-15 13:57*

6666666666666666

## 回复 by w七喜w (#387)

*2025-9-15 23:19*

6666666666666

## 回复 by wx_Kubo (#388)

*2025-9-16 11:37*

666

## 回复 by wqey (#389)

*2025-9-16 14:09*

mark

## 回复 by mb_jmkwanzm (#390)

*2025-9-18 14:33*

66666

## 回复 by mb_uorljqmy (#391)

*2025-9-19 11:26*

666

## 回复 by faker1 (#392)

*2025-9-21 01:44*

666

## 回复 by mb_pnyyaazf (#393)

*2025-9-21 16:29*

感谢分享

## 回复 by Batterman (#394)

*2025-9-21 22:34*

666666

## 回复 by basketwill (#395)

*2025-9-21 22:50*

66666666666

## 回复 by mb_kuxrlshc (#396)

*2025-9-23 23:01*

qqq

## 回复 by mb_kuxrlshc (#397)

*2025-9-23 23:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  koflfy](https://bbs.kanxue.com/user-111569.htm)
>
>  mark，追佬牛逼
>
>

mark，追佬牛逼

## 回复 by mb_yocotole (#398)

*2025-9-24 23:30*

6666666666

## 回复 by mb_dwksysag (#399)

*2025-9-25 17:18*

学习一下

## 回复 by mb_cavlhbum (#400)

*2025-9-26 14:23*

66666666666666666666

## 回复 by mb_mrjjcxgk (#401)

*2025-9-26 14:25*

666

## 回复 by Circ1e (#402)

*2025-9-26 15:27*

6666

## 回复 by yizhidae (#403)

*2025-9-27 20:58*

感谢分享，我顶

## 回复 by _515548 (#404)

*2025-9-28 17:07*

6

## 回复 by xeiyu (#405)

*2025-9-29 08:10*

666

## 回复 by Cowsor (#406)

*2025-9-29 10:14*

66666

## 回复 by mb_nmqxkune (#407)

*2025-9-29 15:56*

有没有大佬最近想增加些收入，来接点活吧，忙不过来了~有想法私信我哈![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by lzhip (#408)

*2025-9-30 17:34*

mark，谢谢

## 回复 by Freax (#409)

*2025-9-30 17:40*

我搭了一个千问的接口，测试了curl没问题，但是cline一直报错API Request Failed 还有 Cannot use checkpoints in Desktop directory ，有人遇到过吗？求教怎么解决

![image](https://bbs.kanxue.com/upload/attach/202509/920571_XRERYK46GXJ4C9G.webp)

## 回复 by gggtaotao (#410)

*2025-9-30 19:36*

厉害

## 回复 by 乌鸡哥 (#411)

*2025-9-30 22:19*

666

## 回复 by mb_uzbjdpsq (#412)

*2025-10-1 18:18*

66666

## 回复 by moodykeke (#413)

*2025-10-1 18:45*

学无止境，终身钻研

## 回复 by mb_axzxhstj (#414)

*2025-10-2 11:39*

感谢分享

## 回复 by wandering (#415)

*2025-10-2 15:11*

看不懂

## 回复 by zwjiang (#416)

*2025-10-2 16:18*

学习学习

## 回复 by SkyShadow (#417)

*2025-10-5 15:11*

666

## 回复 by mb_rbinpkib (#418)

*2025-10-5 15:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Murphy857 (#419)

*2025-10-5 19:14*

大佬牛逼

## 回复 by xiao_yuan (#420)

*2025-10-6 10:20*

谢谢你的细致分析，受益匪浅！

## 回复 by mb_yzxcrpkp (#421)

*2025-10-6 14:36*

66666666

## 回复 by mb_dfmuaysg (#422)

*2025-10-6 14:43*

666

## 回复 by mb_tpjhaiii (#423)

*2025-10-8 11:41*

牛逼看看大佬

## 回复 by tjxiaowu (#424)

*2025-10-8 16:45*

mark，追佬牛逼

## 回复 by Ssssss_303289 (#425)

*2025-10-9 01:07*

mark

## 回复 by 蒙尘_993683 (#426)

*2025-10-9 09:29*

666

## 回复 by mb_ofwlaiwa (#427)

*2025-10-9 11:49*

学习

## 回复 by 羡仙 (#428)

*2025-10-9 15:39*

感谢分享

## 回复 by mb_xovepwar (#429)

*2025-10-9 16:25*

1

## 回复 by xautzbl_270908 (#430)

*2025-10-9 17:21*

666

## 回复 by mb_qebgiazc (#431)

*2025-10-9 17:41*

6666666666666666666666666666666666

## 回复 by newstu1987 (#432)

*2025-10-10 13:18*

mark,lao

## 回复 by 算了吧 (#433)

*2025-10-10 16:57*

牛的大佬

## 回复 by 残枫 (#434)

*2025-10-11 15:40*

mark，追佬牛逼

## 回复 by 秦王绕柱 (#435)

*2025-10-11 16:19*

mark

## 回复 by i意写书 (#436)

*2025-10-13 13:47*

hahaha

## 回复 by BLACKRanger (#437)

*2025-10-13 15:55*

2121212121212

## 回复 by Kevin衡 (#438)

*2025-10-13 18:58*

受益匪浅

## 回复 by wx_陈庆文 (#439)

*2025-10-13 19:10*

6666666666666

## 回复 by mb_axkkxqfb (#440)

*2025-10-14 10:33*

6666

## 回复 by mb_qomvcxzc (#441)

*2025-10-14 11:47*

膜拜

## 回复 by oneshot1900 (#442)

*2025-10-14 16:01*

666

## 回复 by 练习生 (#443)

*2025-10-14 16:05*

666666

## 回复 by 半醉半醒 (#444)

*2025-10-14 23:49*

6666666大佬牛

## 回复 by smallguitar (#445)

*2025-10-15 15:38*

感谢分享

## 回复 by hybcx (#446)

*2025-10-15 16:29*

666

## 回复 by 逆向晨 (#447)

*2025-10-17 13:22*

6666666666666666666666666666666666

## 回复 by Kiana1024 (#448)

*2025-10-19 10:37*

感谢大佬分享！

## 回复 by git_82850wxt201 (#449)

*2025-10-20 16:09*

wow

## 回复 by Snowman_Liam (#450)

*2025-10-20 18:44*

6666

## 回复 by hbkccccc (#451)

*2025-10-20 18:48*

66666666

## 回复 by mb_bfghjvta (#452)

*2025-10-20 20:26*

结合 AI，很强

## 回复 by 平板车 (#453)

*2025-10-21 21:03*

追佬牛逼

## 回复 by Oo风之恋oO (#454)

*2025-10-22 00:13*

能不能更详细一些

## 回复 by flylove (#455)

*2025-10-22 10:00*

大佬厉害

## 回复 by atomxw (#456)

*2025-10-24 15:09*

感谢大佬分享

## 回复 by imliuxin (#457)

*2025-10-24 15:38*

好

## 回复 by 毛毛毛毛虫 (#458)

*2025-10-25 18:11*

学习一下

## 回复 by zhongdong (#459)

*2025-10-26 11:11*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_zzyb (#460)

*2025-10-26 12:24*

111323

## 回复 by mb_ppbnomlu (#461)

*2025-10-28 16:11*

6666

## 回复 by muskccc (#462)

*2025-10-28 16:20*

666

## 回复 by M4rg4tr01d (#463)

*2025-10-29 09:17*

666

## 回复 by h旋风h (#464)

*2025-10-29 11:27*

前排膜拜下

## 回复 by git_56867guozijing-zjk (#465)

*2025-10-29 13:21*

哇哦

## 回复 by wyhacket (#466)

*2025-10-29 17:45*

mark，追佬牛逼

## 回复 by mb_gtdpycmd (#467)

*2025-10-31 16:19*

hhh

## 回复 by Theffth (#468)

*2025-10-31 21:32*

膜拜大佬！

## 回复 by mb_kepupbga (#469)

*2025-11-1 22:32*

6666

## 回复 by 不再后悔 (#470)

*2025-11-3 16:54*

追佬牛逼

## 回复 by 问心无愧 (#471)

*2025-11-3 20:18*

6

## 回复 by ID蝴蝶 (#472)

*2025-11-4 00:20*

大佬太强了

## 回复 by mb_ixkssjin (#474)

*2025-11-4 12:57*

学习他

## 回复 by mb_ijwwkejd (#475)

*2025-11-4 19:59*

6666666666666666

## 回复 by 五BT (#476)

*2025-11-4 22:10*

mark，追佬牛逼

## 回复 by 宛枫 (#477)

*2025-11-5 08:36*

感谢分享

## 回复 by mb_cvbrdzmz (#478)

*2025-11-5 19:26*

11111

## 回复 by Noguess9 (#479)

*2025-11-7 18:23*

11

## 回复 by wx_阿白_486 (#480)

*2025-11-9 23:22*

文章这么长，希望回复后看到的是分了段的吧![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by wx_漾 (#481)

*2025-11-12 15:43*

666666666666

## 回复 by mb_svxtaqec (#482)

*2025-11-12 22:37*

66666

## 回复 by Delevy (#483)

*2025-11-13 08:20*

6666

## 回复 by wx_她也终为过往. (#484)

*2025-11-13 09:41*

666

## 回复 by mb_hjztuivn (#485)

*2025-11-13 10:21*

学习了

## 回复 by 渗透 (#486)

*2025-11-13 15:10*

感谢分享

## 回复 by mb_jyqajgwu (#487)

*2025-11-13 16:28*

学习

## 回复 by 林蓝 (#488)

*2025-11-13 19:29*

6666666

## 回复 by mb_euhyowpw (#489)

*2025-11-13 21:09*

666

## 回复 by hwfyff (#490)

*2025-11-15 23:12*

感谢分享

## 回复 by mb_yfobxtpj (#491)

*2025-11-17 08:59*

膜拜

## 回复 by woaiziyou (#492)

*2025-11-17 10:15*

mark，追佬牛逼

## 回复 by 嗟来嗟来 (#493)

*2025-11-17 18:01*

牛逼 拥抱ai

## 回复 by git_86967Fredhardycnm (#494)

*2025-11-18 00:53*

六百六十六

## 回复 by caoxiancc (#495)

*2025-11-18 07:15*

mark，追佬牛逼

## 回复 by mb_emjsepie (#496)

*2025-11-18 20:41*

mark，追佬牛逼

## 回复 by wx_Egoist (#497)

*2025-11-19 17:49*

666

## 回复 by JmpShellCode (#498)

*2025-11-20 13:17*

mark

## 回复 by 七海种马 (#499)

*2025-11-21 12:01*

666

## 回复 by tiantian313 (#500)

*2025-11-24 16:14*

赞一个

## 回复 by Ryanhn717 (#501)

*2025-11-25 10:01*

学习一下

## 回复 by mb_ynaaahps (#502)

*2025-11-26 10:02*

感谢分享

## 回复 by mb_ejimlmwd (#503)

*2025-11-26 17:02*

mark，追佬牛逼

## 回复 by scpczc (#504)

*2025-11-26 17:12*

太强了

## 回复 by wx_随波逐流、 (#505)

*2025-11-27 07:53*

666666666666

## 回复 by 飞猫的世界 (#506)

*2025-11-27 10:00*

感谢分享，学习了

## 回复 by 冰河R (#507)

*2025-11-27 16:09*

6666

## 回复 by mb_tppxggoi (#508)

*2025-11-29 16:00*

666666666666![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_gccsplhk (#509)

*2025-11-29 16:04*

7666666666666666666666

## 回复 by 尐进 (#510)

*2025-11-30 16:12*

mark

## 回复 by mb_rbidlyeu (#511)

*2025-11-30 17:39*

666666666666666

## 回复 by mb_wqvhhpxn (#512)

*2025-12-1 11:07*

牛逼

## 回复 by Ms135 (#513)

*2025-12-1 12:28*

66666666666

## 回复 by djxh (#514)

*2025-12-1 17:54*

666

## 回复 by mb_xfrjqald (#515)

*2025-12-2 00:35*

![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_pmwkabcl (#516)

*2025-12-2 03:31*

6

## 回复 by iPythonCoder (#517)

*2025-12-2 09:40*

谢谢你的细致分析，受益匪浅！

## 回复 by kagayaki (#518)

*2025-12-2 22:30*

666

## 回复 by SPX-4801 (#519)

*2025-12-3 10:36*

66666

## 回复 by 机车王子 (#520)

*2025-12-3 15:44*

谢谢你的细致分析，受益匪浅！

## 回复 by mb_weyfdhks (#521)

*2025-12-3 16:51*

666

## 回复 by cooljuly (#522)

*2025-12-4 13:48*

学习一下

## 回复 by wolf_lc (#523)

*2025-12-4 13:55*

6666666666666666

## 回复 by nanxm (#524)

*2025-12-6 20:36*

感谢分享感谢分享感谢分享

## 回复 by lazylord (#525)

*2025-12-6 23:51*

66666666666666

## 回复 by Heiyiren123 (#526)

*2025-12-8 13:34*

感谢分享，很有启发！

## 回复 by wx_瘦的我好焦灼 (#527)

*2025-12-8 16:02*

111

## 回复 by 钱钱钱￥ (#528)

*2025-12-8 16:04*

111

## 回复 by mb_xpeetrfy (#529)

*2025-12-9 23:42*

666

## 回复 by mb_pqpaveus (#530)

*2025-12-11 11:03*

看一下内容。

## 回复 by kienmanowa (#531)

*2025-12-11 11:32*

感谢分享

## 回复 by iboy6 (#532)

*2025-12-11 15:18*

666

## 回复 by xiusi (#533)

*2025-12-11 20:36*

666

## 回复 by mb_yyvcbkli (#534)

*2025-12-12 12:13*

学习一下先进经验

## 回复 by TenProtect (#535)

*2025-12-12 15:51*

6666

## 回复 by pinggle (#536)

*2025-12-13 15:18*

学习，感谢分享

## 回复 by mb_rxasmcok (#537)

*2025-12-14 15:53*

good

## 回复 by Parrot233 (#538)

*2025-12-14 16:13*

非常棒

## 回复 by Ansse (#539)

*2025-12-14 19:56*

牛啊 大佬，已经开始结合ai来逆向食用了

## 回复 by LoeweErr (#540)

*2025-12-15 14:00*

666

## 回复 by 天水姜伯约 (#541)

*2025-12-16 14:41*

666

## 回复 by mb_dagesnbs (#542)

*2025-12-16 15:18*

44

## 回复 by Abiu~ (#543)

*2025-12-17 16:53*

666

## 回复 by 0xNOPE (#544)

*2025-12-17 18:11*

mark，最近恰好看这方面的资料

## 回复 by 云霄IT (#545)

*2025-12-17 18:50*

1

## 回复 by huangjw (#546)

*2025-12-17 19:09*

火钳刘明

## 回复 by 小光开摆 (#547)

*2025-12-18 01:53*

mark，追佬牛逼

## 回复 by cbctan (#548)

*2025-12-21 21:21*

![image](https://bbs.kanxue.com/view/img/face/079.gif)追佬牛逼

## 回复 by mb_fonsowqm (#549)

*2025-12-22 10:27*

666

## 回复 by logeye (#550)

*2025-12-22 12:51*

666

## 回复 by ps_ps (#551)

*2025-12-22 14:21*

666

## 回复 by SX_DomOne (#552)

*2025-12-22 17:34*

谢谢你的细致分析，受益匪浅！

## 回复 by 飞机上唱山歌 (#553)

*2025-12-22 18:05*

1

## 回复 by mb_jhusdqvh (#554)

*2025-12-24 16:26*

123

## 回复 by user_adb (#555)

*2025-12-25 11:22*

66666

## 回复 by wx_鱼泡泡 (#556)

*2025-12-25 14:47*

膜拜一下

## 回复 by cici5000 (#557)

*2025-12-25 17:24*

666

## 回复 by foofo888 (#558)

*2025-12-26 20:25*

大佬牛逼，研究研究

## 回复 by uh21iugdh1 (#559)

*2025-12-31 04:16*

学习一下，这几天正在配环境

## 回复 by jccforever (#560)

*2025-12-31 08:14*

前排膜拜下

## 回复 by 左叶的风 (#561)

*2025-12-31 10:02*

感谢分享

## 回复 by quarkfc2025 (#562)

*2025-12-31 22:05*

非常感谢！

## 回复 by Xpert (#563)

*2026-1-1 15:56*

66666666666666666

## 回复 by mb_knfwljtn (#564)

*2026-1-1 19:10*

666

## 回复 by xiaocaiji123 (#565)

*2026-1-4 14:37*

155566

## 回复 by wx_Abyss (#566)

*2026-1-6 11:02*

追佬牛逼

## 回复 by _THINCT (#567)

*2026-1-6 11:34*

mark，追佬牛逼

## 回复 by 逃课 (#568)

*2026-1-6 13:07*

这是个好东西，必须学习

## 回复 by 生命练习生 (#569)

*2026-1-7 15:29*

666

## 回复 by oyefer (#570)

*2026-1-7 22:18*

与时俱进，火钳刘明

## 回复 by 华安9527 (#571)

*2026-1-8 14:26*

6666

## 回复 by wx_K4i. (#572)

*2026-1-8 15:37*

6666666666666666

## 回复 by linkkkkk (#573)

*2026-1-9 09:56*

感谢分享

## 回复 by x1aob1n (#574)

*2026-1-9 14:15*

666

## 回复 by zhaojibo (#575)

*2026-1-9 15:14*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by tjytjy (#576)

*2026-1-9 19:19*

666

## 回复 by git_94730eaydwshawke-gif (#577)

*2026-1-9 19:28*

666

## 回复 by ttiandaye (#578)

*2026-1-11 00:17*

感谢分享，前排膜拜下

## 回复 by git_26561Avz3il (#579)

*2026-1-11 01:34*

mark，追佬牛逼

## 回复 by wx_lll_652 (#580)

*2026-1-11 06:47*

学习了

## 回复 by mb_lkngxxnw (#581)

*2026-1-12 17:42*

666

## 回复 by mb_eweeremm (#582)

*2026-1-13 00:20*

6666666666666666

## 回复 by 大大大大师 (#583)

*2026-1-13 05:34*

1111111111111

## 回复 by JWPL (#584)

*2026-1-13 06:20*

感谢分享

## 回复 by mb_xzhbdodk (#585)

*2026-1-14 10:54*

666

## 回复 by 舵手 (#586)

*2026-1-14 18:50*

mark

## 回复 by mb_kgyloqxd (#587)

*2026-1-14 19:29*

追佬牛逼

## 回复 by 云雕 (#588)

*2026-1-15 17:33*

mark，追佬牛逼

## 回复 by 茄子不茄 (#589)

*2026-1-16 17:50*

666

## 回复 by mb_jwjzvbhv (#590)

*2026-1-16 18:36*

学习一下 感谢分享

## 回复 by 3cly (#591)

*2026-1-18 18:40*

1

## 回复 by mb_koixqizd (#592)

*2026-1-18 18:42*

学习

## 回复 by mb_uvehnaix (#593)

*2026-1-19 12:37*

66666666

## 回复 by mb_soepmyqi (#594)

*2026-1-20 17:19*

666666666666666

## 回复 by mb_jppvcvny (#595)

*2026-1-21 20:56*

1

## 回复 by 祸祸 (#596)

*2026-1-22 19:24*

大佬牛逼

## 回复 by caxfan (#597)

*2026-1-23 12:05*

感谢分享

## 回复 by Snark (#598)

*2026-1-24 16:54*

1

## 回复 by mb_oysbcaej (#599)

*2026-1-25 22:26*

学习

## 回复 by mb_msrzcskt (#600)

*2026-1-27 11:23*

6666

## 回复 by mb_ripshzdx (#601)

*2026-1-27 12:07*

膜拜一下

## 回复 by mb_lecktyto (#602)

*2026-1-28 10:20*

mark，追佬牛逼

## 回复 by mryoufx (#603)

*2026-1-28 10:48*

膜拜大佬

## 回复 by Xhani (#604)

*2026-1-28 15:46*

1

## 回复 by mb_fywmigrm (#605)

*2026-1-28 16:45*

1111

## 回复 by 张three (#606)

*2026-1-31 07:45*

6666

## 回复 by wx_new Star (#607)

*2026-2-1 14:30*

666

## 回复 by mb_vtwabawz (#608)

*2026-2-1 14:32*

mark，追佬牛逼888

## 回复 by mb_dbgckqtz (#609)

*2026-2-2 00:04*

111111111111111111111

## 回复 by 不知世事 (#610)

*2026-2-3 16:22*

学习

## 回复 by wonhurry (#611)

*2026-2-3 16:56*

我记得之前版本也有python脚本可以调用ai分析，有什么不一样吗

## 回复 by wx_向阳. (#612)

*2026-2-4 01:00*

666666

## 回复 by mb_lohnfwgv (#613)

*2026-2-4 23:33*

膜拜下

## 回复 by Johnson_133533 (#614)

*2026-2-5 16:00*

mark mark

## 回复 by xinhu (#615)

*2026-2-5 16:06*

666666666

## 回复 by ljcnot (#616)

*2026-2-5 16:38*

学习一下

## 回复 by kccp (#617)

*2026-2-5 18:51*

up

## 回复 by 闷声发大财. (#618)

*2026-2-7 09:41*

666

## 回复 by wx_1_816 (#619)

*2026-2-11 11:38*

66666666

## 回复 by zangl (#620)

*2026-2-12 03:46*

膜拜

## 回复 by tarchen (#621)

*2026-2-14 10:04*

谢谢分享，仔细学习。

## 回复 by mb_ppryzjtf (#622)

*2026-2-14 11:31*

111

## 回复 by mb_lzybjqdn (#623)

*2026-2-14 22:40*

感谢分享

## 回复 by shuangmou (#624)

*2026-2-19 12:56*

看看大佬

## 回复 by kanshan (#625)

*2026-2-19 16:58*

![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by git_67295gffhgjfhfjg (#626)

*2026-2-20 16:45*

感谢分享

## 回复 by mb_vrgcfbbe (#627)

*2026-2-20 19:46*

追佬牛逼

## 回复 by hb6106 (#628)

*2026-2-21 10:56*

膜拜下

## 回复 by mb_etgbvvic (#629)

*2026-2-22 21:16*

666666

## 回复 by moobrsne (#630)

*2026-2-23 11:21*

6666

## 回复 by 老皮一號 (#631)

*2026-2-23 13:49*

感謝分享

## 回复 by mb_buuvbtph (#632)

*2026-2-23 21:03*

6666666666，学习学习

## 回复 by gryh193 (#633)

*2026-2-25 13:45*

666

## 回复 by Aimees (#634)

*2026-2-25 18:31*

nb

## 回复 by mb_ugryjzdr (#635)

*2026-3-3 16:27*

666

## 回复 by yuanyouran (#636)

*2026-3-3 18:53*

感谢分享，学习了！

## 回复 by fengvmu (#637)

*2026-3-4 13:39*

666

## 回复 by yuanyouran (#638)

*2026-3-4 14:50*

感谢分享

## 回复 by 二木先生 (#639)

*2026-3-4 19:22*

good，前来学习

## 回复 by N1l (#640)

*2026-3-5 09:59*

666

## 回复 by 简简单单看看 (#641)

*2026-3-5 10:44*

学习了

## 回复 by RRRRoma (#642)

*2026-3-5 21:55*

感谢分享

## 回复 by mb_ygxdlbdi (#643)

*2026-3-6 14:27*

mark

## 回复 by 研究汽车的猫 (#644)

*2026-3-6 14:40*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by wx_凯子胡 (#645)

*2026-3-7 10:59*

6666666666666666666

## 回复 by 兔子经纪人 (#646)

*2026-3-9 17:43*

mark666

## 回复 by mb_doidlnho (#647)

*2026-3-9 19:47*

666

## 回复 by xmgood (#648)

*2026-3-9 23:07*

这教程写的太好了，太专业了

## 回复 by mb_etkbumod (#649)

*2026-3-10 20:44*

mark

## 回复 by 我靠三二一 (#650)

*2026-3-11 13:20*

感谢分享

## 回复 by 一学徒工 (#651)

*2026-3-11 15:40*

1111111111

## 回复 by mb_shqpjxff (#652)

*2026-3-12 10:26*

mark

## 回复 by StartAoA (#653)

*2026-3-12 13:30*

Mark

## 回复 by sunplus (#654)

*2026-3-15 08:39*

感谢分享

## 回复 by TheAClown (#655)

*2026-3-15 22:13*

感谢分享

## 回复 by Elizabeth_262001 (#656)

*2026-3-16 14:44*

厉害

## 回复 by wx_霿凇 (#657)

*2026-3-16 14:56*

666

## 回复 by xiaochijie (#658)

*2026-3-16 15:05*

感谢分享

## 回复 by mb_vfwoyxlq (#659)

*2026-3-16 16:30*

感谢分享

## 回复 by mb_ktasfpbp (#660)

*2026-3-16 16:45*

1

## 回复 by zjgcjy (#661)

*2026-3-17 16:58*

111111

## 回复 by 海绵海绵海绵 (#662)

*2026-3-19 11:15*

6666666666666666牛逼

## 回复 by git_64382nas298041-code (#663)

*2026-3-20 11:43*

1

## 回复 by 内存管理 (#664)

*2026-3-25 16:57*

666

## 回复 by 止战之殇wuha (#665)

*2026-3-25 17:58*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by vector (#666)

*2026-3-30 10:15*

厉害

## 回复 by sky_blue (#667)

*2026-3-30 11:01*

666666

## 回复 by XCicada (#668)

*2026-3-30 14:04*

膜拜

## 回复 by mb_coqbxbgr (#669)

*2026-3-31 11:02*

1

## 回复 by zengaven (#670)

*2026-3-31 11:18*

11111111111111111111

## 回复 by 天地一逆旅 (#671)

*2026-3-31 14:24*

牛x，大佬

## 回复 by WinDEI (#672)

*2026-3-31 21:48*

mark

## 回复 by 杀老师 (#673)

*2026-4-1 10:53*

牛逼

## 回复 by 黑色心跳 (#674)

*2026-4-1 12:19*

学习

## 回复 by hahao (#675)

*2026-4-1 13:44*

感谢分享

## 回复 by Lame_Crow (#676)

*2026-4-2 15:10*

mark

## 回复 by mb_pwtdwvrv (#677)

*2026-4-6 11:54*

我去，666

## 回复 by mb_gphkbymg (#678)

*2026-4-6 14:38*

学习学习

## 回复 by wx_hanhan_Fe (#679)

*2026-4-7 09:21*

orz

## 回复 by 子归 (#680)

*2026-4-7 11:19*

AI加持,无所不能啊啊

## 回复 by mb_wjytplsl (#681)

*2026-4-7 14:59*

666

## 回复 by wx_Huber Barrientos (#682)

*2026-4-8 13:14*

66666

## 回复 by mb_dsvrufqa (#683)

*2026-4-10 11:30*

666666666

## 回复 by 啥也不会2 (#684)

*2026-4-10 15:08*

66666666666

## 回复 by APlus (#685)

*2026-4-10 15:59*

6

## 回复 by shupuyun (#686)

*2026-4-11 04:11*

感谢分享

## 回复 by mb_kendzvcd (#687)

*2026-4-12 11:22*

66666666666

## 回复 by xerik (#688)

*2026-4-14 17:28*

66666666666

## 回复 by wx_L_ (#689)

*2026-4-14 19:53*

666

## 回复 by k4y0z (#690)

*2026-4-15 10:21*

666

## 回复 by mb_uikdudgo (#691)

*2026-4-17 04:05*

22222

## 回复 by spdfdfer (#692)

*2026-4-17 15:59*

666

## 回复 by sir678 (#693)

*2026-4-17 17:49*

牛逼牛逼

## 回复 by mb_lkdeiaju (#694)

*2026-4-18 20:12*

111111111

## 回复 by 火星farmer (#695)

*2026-4-19 08:30*

6666666666666666，大佬牛逼！

## 回复 by 自在游 (#696)

*2026-4-19 22:19*

干货

## 回复 by cx52038 (#697)

*2026-4-21 18:22*

666

## 回复 by 一栋奥特曼 (#698)

*2026-4-21 20:11*

666

## 回复 by 倔强石头 (#699)

*2026-4-22 11:13*

学习了

## 回复 by yinshen (#700)

*2026-4-22 15:30*

膜拜大佬

## 回复 by 郭达 (#701)

*2026-4-23 11:44*

666

## 回复 by mb_krrfgtfd (#702)

*2026-4-23 14:10*

mark

## 回复 by git_44857niuniu524 (#703)

*2026-4-23 14:26*

666

## 回复 by LoginUser (#704)

*2026-4-23 15:14*

感谢分享

## 回复 by ͚̮͙͙͇ (#705)

*2026-4-24 02:02*

大佬牛逼

## 回复 by lostin9772 (#706)

*2026-4-27 17:25*

太强了

## 回复 by mb_ccvvhvhb (#707)

*2026-4-27 22:31*

666

## 回复 by 进击的Snow (#708)

*2026-4-28 15:58*

666

## 回复 by 进击的Snow (#709)

*2026-4-28 15:58*

666

## 回复 by 进击的Snow (#710)

*2026-4-28 15:58*

66666666666666666666![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 进击的Snow (#711)

*2026-4-28 15:58*

66666666666666666666

## 回复 by 进击的Snow (#712)

*2026-4-28 15:58*

66666666666666666666

## 回复 by 进击的Snow (#713)

*2026-4-28 15:58*

77777777777777777

## 回复 by 进击的Snow (#714)

*2026-4-28 15:59*

谢谢你

## 回复 by mb_eubpihhp (#715)

*2026-4-30 17:12*

感谢大佬分享

## 回复 by mb_gatolgsc (#716)

*2026-4-30 18:51*

Mark一下，谢谢

## 回复 by jstqyymwy (#717)

*2026-5-1 08:28*

看看????

## 回复 by xzchina (#718)

*2026-5-2 06:31*

前排前排

## 回复 by 风_158566 (#719)

*2026-5-2 14:31*

谢谢分享

## 回复 by mb_cqnikugm (#720)

*2026-5-3 22:26*

666666666666666666666

## 回复 by lychee (#721)

*2026-5-3 23:36*

感谢分享

## 回复 by zz胡 (#722)

*2026-5-5 14:07*

66666666666

## 回复 by mb_rtyzyhmr (#723)

*2026-5-6 14:03*

1

## 回复 by czt^_^ (#724)

*2026-5-6 16:25*

666啊

## 回复 by mb_jfqdmtyv (#725)

*2026-5-7 16:19*

aaa

## 回复 by mb_ssjlfpnk (#726)

*2026-5-8 10:28*

膜拜

## 回复 by 罗可 (#727)

*2026-5-9 18:17*

jjjjjj

## 回复 by mb_osxdmntv (#728)

*2026-5-10 00:18*

6666

## 回复 by mb_rbfpkjqw (#729)

*2026-5-10 20:04*

111111111

## 回复 by git_49999huanptd2011 (#730)

*2026-5-11 13:40*

666

## 回复 by 086Love (#731)

*2026-5-11 14:17*

学习

## 回复 by Aques (#732)

*2026-5-12 15:39*

6

## 回复 by wx_敬博 (#733)

*2026-5-12 22:47*

牛牛牛6666

## 回复 by mb_guabqeqo (#734)

*2026-5-14 09:57*

期待更多优质内容的分享，论坛有你更精彩！

## 回复 by 信仰666 (#735)

*2026-5-14 10:07*

感谢分享

## 回复 by ventest (#736)

*2026-5-14 11:04*

厉害

## 回复 by 星辰北天 (#737)

*2026-5-14 20:32*

感谢分享

## 回复 by mb_yjiuccxa (#738)

*2026-5-15 10:15*

666

## 回复 by 中国特色互联网 (#739)

*2026-5-18 07:18*

不错

## 回复 by 矽阳 (#740)

*2026-5-20 12:37*

6666666666666666

## 回复 by situhaonan (#741)

*2026-5-20 12:45*

感谢分享

## 回复 by ziyunlll (#742)

*2026-5-20 17:26*

感谢分享

## 回复 by Stherfuty (#743)

*2026-5-21 17:33*

感谢分享

## 回复 by m杜 (#744)

*2026-5-25 11:10*

666

## 回复 by 58582404 (#745)

*2026-5-27 22:25*

感谢分享

## 回复 by yyy123 (#746)

*2026-5-27 23:37*

厉害![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_太阳花田向日葵 (#747)

*2026-5-29 12:06*

学习一下

## 回复 by mb_cviyuksx (#748)

*2026-5-29 16:03*

666

## 回复 by mb_wxigbkeg (#749)

*2026-5-29 16:50*

666

## 回复 by git_56402Syy040316 (#750)

*2026-6-1 16:21*

111

## 回复 by Deterior (#751)

*2026-6-2 11:30*

大佬  opencode 里面如何使用？ 我这边 IDA Pro 里面已经显示启动， 在终端中也能正常请求， 但是集成到 opencode 的时候， mcp 一直不显示, 配置文件是这样的

| 1234567891011 | `{``"$schema"``:``"https://opencode.ai/config.json"``,``"disabled_providers"``: [],``"mcp"``: {``"ida-pro-mcp"``: {``"type"``:``"remote"``,``"url"``:``"http://127.0.0.1:13337/mcp"``,``"enabled"``: true``}``}``}` |
|-|-|

## 回复 by wx_Oh.漏 (#752)

*2026-6-5 14:55*

1111

## 回复 by 杰森66988 (#753)

*2026-6-7 21:26*

mark

## 回复 by WinMainE (#754)

*2026-6-8 13:10*

6666

## 回复 by mb_ealiidqb (#755)

*2026-6-8 13:44*

mark，追佬牛逼

## 回复 by ying爵 (#756)

*2026-6-8 13:52*

感谢分享

## 回复 by mb_umxhjwar (#757)

*2026-6-9 09:44*

666

## 回复 by mb_ejnbqbhk (#758)

*2026-6-10 20:28*

好

## 回复 by wx_友情 (#759)

*2026-6-12 21:04*

mark，追佬牛逼

## 回复 by rsevenrafe (#760)

*2026-6-13 09:50*

感谢分享

## 回复 by chengdrgon (#761)

*2026-6-13 11:24*

感谢分享

## 回复 by mb_kdnzjvdt (#762)

*2026-6-13 18:25*

6

## 回复 by mb_ezmrnfsu (#763)

*2026-6-13 19:11*

666

## 回复 by wx_奔放奔放奔放 (#764)

*2026-6-14 17:51*

66666666666666

## 回复 by limfcn (#765)

*2026-6-15 10:37*

认真学习中

## 回复 by Mayri (#766)

*2026-6-16 22:19*

感谢分享

## 回复 by 伊苏尔德 (#767)

*2026-6-17 10:41*

6

## 回复 by mb_xiycqmtm (#768)

*2026-6-17 18:35*

mark，追佬牛逼

## 回复 by mb_gkbxtfri (#769)

*2026-6-18 10:20*

感谢分享

## 回复 by wx_leo_346548 (#770)

*2026-6-18 10:32*

mark

## 回复 by wx_key_489 (#771)

*2026-6-19 02:35*

6666666666666

## 回复 by wx_WantC (#772)

*2026-6-19 05:09*

过来学习

## 回复 by tkschip (#773)

*2026-6-22 17:04*

感谢，学习

## 回复 by newstyle (#774)

*2026-6-22 18:34*

感谢分享，很实用

## 回复 by 满眼含泪 (#775)

*2026-6-22 19:01*

好

## 回复 by woliu (#776)

*2026-6-22 19:40*

mark，追佬牛逼

## 回复 by mb_tjataolt (#777)

*2026-6-23 18:33*

666

## 回复 by git_88931Cloud2Group (#778)

*2026-6-23 18:57*

mark，追佬牛逼

## 回复 by git_34231nguyenvantiennani (#779)

*2026-6-25 14:58*

11

## 回复 by 楼中镜 (#780)

*2026-6-25 20:08*

大佬 牛逼的 谢谢

## 回复 by mb_dlljjfcf (#781)

*2026-6-27 09:22*

6666

## 回复 by mb_gixgtcfn (#782)

*2026-6-27 22:55*

大佬牛逼

## 回复 by wx_' 养猪仙人 (#783)

*2026-6-28 02:29*

前排膜拜下

## 回复 by DavidRLiu (#784)

*2026-6-28 18:54*

感谢老师的分享，学习一下

## 回复 by wtxpwh (#785)

*2026-6-29 07:52*

666，不错

## 回复 by mb_jtkiocxd (#786)

*2026-6-29 18:35*

6666

## 回复 by 智童 (#787)

*2026-7-1 01:36*

??????????

## 回复 by 智童 (#788)

*2026-7-1 01:37*

?????????

## 回复 by 智童 (#789)

*2026-7-1 01:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_kx26570](https://bbs.kanxue.com/user-798345.htm)
>  回复或点赞可查看完整内容
>

??????????

## 回复 by mb_ctvogkot (#790)

*2026-7-1 09:54*

牛b！！！！！！！！！！！

## 回复 by D_ZH0u (#791)

*2026-7-1 17:31*

6666666666

## 回复 by v9d0g (#792)

*2026-7-2 16:02*

感谢分享

## 回复 by lodestar68 (#793)

*2026-7-4 16:25*

3xxxxxxxxxxxxxx

## 回复 by wx_骁_155 (#794)

*2026-7-5 13:57*

666

## 回复 by mb_xodpzczn (#795)

*2026-7-5 17:38*

NIU

## 回复 by aizhiqun (#796)

*2026-7-5 21:38*

膜拜

## 回复 by mb_huagqssz (#797)

*2026-7-6 10:32*

666

## 回复 by git_94143ILoveZhangZhe1314 (#798)

*2026-7-6 17:30*

1

## 回复 by git_94143ILoveZhangZhe1314 (#799)

*2026-7-6 17:30*

1

## 回复 by Iceshara (#800)

*2026-7-7 22:15*

666

## 回复 by mb_uickdiho (#801)

*2026-7-9 08:16*

感谢分享

## 回复 by 进击的Snow (#802)

*2026-7-9 09:09*

66

## 回复 by wx_白鸟之诗 (#803)

*2026-7-17 10:41*

6666666666666666

## 回复 by liowmark (#804)

*2026-7-17 14:12*

学习学习

## 回复 by BiaoW (#805)

*2026-7-17 17:39*

666

## 回复 by mb_axpeuqgo (#806)

*2026-7-18 16:23*

mark，来学习了

## 回复 by mb_vlfbadbl (#807)

666

## 回复 by kudos5566 (#808)

6

## 回复 by wx_星_446920 (#809)

66666

## 回复 by yuntao.lee (#810)

学习大佬，膜拜

## 回复 by mb_fxzlatwb (#811)

mark！

## 回复 by wx_茄子豆角伴芹菜 (#812)

6666

## 回复 by BitWarden (#813)

666

## 回复 by git_51354IsoumaNaN (#814)

6666666666666

## 回复 by junbo (#815)

666
