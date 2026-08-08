---
title: '[原创]ZAFrida UI：把 Frida 的“参数地狱/脚本散落/模板复制粘贴”收进 PyCharm/IDEA 的右键菜单里'
url: https://bbs.kanxue.com/thread-289967.htm
tid: 289967
author: afishlong
date: '2026-02-06'
tags: [Android安全, 原创, 程序开发, 源码框架, 工具脚本]
crawled_at: '2026-08-08T10:26:07+00:00'
replies: 22
---

>
> 适用读者：日常用 Frida 做 Android/iOS 逆向、渗透测试、协议分析、Hook 调试的人；习惯在 PyCharm/IntelliJ 里写 Python + JS 的人。
>
>
>

---

## 0x00 背景：Frida 好用，但“命令行工作流”不够工程化

Frida 本身没问题，问题通常出在我们的工作流：

- **参数经常拼错**：`-U/-D/-H`、`-f/-p/-N/-F`、包名/进程名/脚本路径、extra args……切一次目标就要重来一遍。
- **上下文切换成本高**：IDE 写 JS → 终端执行 → 看日志 → 再回 IDE 改脚本；多个设备/多个 App/多个工程时更难受。
- **脚本管理混乱**：PoC、长期维护脚本、不同 App 的 agent.js 混在一起，Android/iOS 也混。
- **模板靠复制粘贴**：常用 Hook 片段（Java.perform、Interceptor.attach、SSL Pinning Bypass……）一遍遍拷；想临时禁用又怕删掉。

**ZAFrida UI 的目标很明确：不替代 Frida，而是把 frida-tools 的能力用 UI/工程化方式包装起来，让“跑脚本”和“管理脚本”更像一个长期可维护项目。**

---

## 0x01 一句话说明白：它到底干嘛的？

**ZAFrida UI 是一个集成在 PyCharm/IntelliJ 的 Frida 图形化插件：你在 JS 编辑区右键就能 Run/Attach 当前脚本，并且会根据脚本所在路径自动切换到对应的 Frida 项目（设备/包名/连接方式/参数）；同时提供右键 Snippets 和复选框式模板系统，把 Hook 脚本当“积木”拼。**

---

## 0x02 效果先看图

## 开源地址:[zafrida-ui github 开源地址](https://github.com/yilongmd/zafrida-ui)![image](https://bbs.kanxue.com/upload/attach/202603/924191_XACAR46W9X8UYYT.webp) ![image](https://bbs.kanxue.com/upload/attach/202602/924191_66D24MRXMN9U6RT.webp) ![image](https://bbs.kanxue.com/upload/attach/202602/924191_E7BAWH6GA7X7SFJ.webp) ![image](https://bbs.kanxue.com/upload/attach/202602/924191_F5WTH3Z5725E94J.webp) ![image](https://bbs.kanxue.com/upload/attach/202602/924191_PRPPAMEAC5P3BPB.webp)

## 0x03 解决的核心痛点

### 痛点 1：编辑器里写着 agent.js，但运行得去终端，且经常跑错设备/包名/工程

**ZAFrida UI 的关键操作：编辑区右键 “Run Frida JS / Attach Frida JS”。**

- **Run Frida JS**：以当前 JS 文件作为主脚本执行（默认 Spawn）。
- **Attach Frida JS**：把当前 JS 文件注入到已运行目标（Attach）。
- 运行前自动保存文件。
- **最关键：根据当前 JS 所在路径，自动定位/切换到脚本所属的 Frida Project**

>
> 这一步的“爽点”在于：**你不再从“终端参数”出发，而是从“脚本文件”出发。**
> PoC 时尤其明显：打开脚本 → 右键 Run → 看输出 → 改脚本。
>
>
>

快捷键（默认）：

- Windows / Linux：`Ctrl + Alt + S`
- macOS：`⌘ + ⌥ + S`
 ![image](https://bbs.kanxue.com/upload/attach/202602/924191_NDPQFDFBQZR5HWV.webp)

---

### 痛点 2：常用 Hook 片段靠复制粘贴

ZAFrida UI 在编辑器右键里内置 **ZAFrida Frida Snippets**（示例）：

- `Java.perform` 包裹块
- hook Java method 模板
- 打印 Java 栈
- `Interceptor.attach`
- backtrace（ACCURATE / FUZZY）
- enumerate modules等

 ![image](https://bbs.kanxue.com/upload/attach/202602/924191_EEF2KSTDT98AJZT.webp)

---

### 痛点 3：一个 IDE 工程里多个目标 App，Android/iOS 脚本混着放，配置散落

ZAFrida UI 引入了**轻量级“Frida 项目制”**，核心是两类 XML：

- **工作区注册表**（IDE 项目根目录）：`zafrida-workspace.xml`
记录当前 IDE 工程下有哪些 ZAFrida 子项目 + 上次选中的项目。
- **每个子项目配置**（子项目目录内）：`zafrida-project.xml`
记录包名/脚本/设备/连接方式/extra args/上次目标等。

并且创建项目时自动区分目录：

- Android 项目默认放在：`android/<projectName>/`
- iOS 项目默认放在：`ios/<projectName>/`

你可以把它理解为：**在一个 PyCharm/IDEA 工程里，专门为 Frida 再建了一层“工作上下文管理”。**

 ![image](https://bbs.kanxue.com/upload/attach/202602/924191_4J4QRR3JYETHWYR.webp)

---

### 痛点 4：模板开关难维护——删了找不回，不删又容易忘记启用状态

ZAFrida UI 的“核心创新点”在模板系统：**复选框式模板管理**。

- 勾选：自动把模板代码注入到主脚本中（插入一个带 marker 的 block）。
- 取消勾选：**不删除**，而是自动用块注释 `/* ... */` 包起来。
- 好处很实际：
	1. 可回滚、可审计；
	2. 多模板组合时不容易“删错”；
	3. 团队协作时“为什么没生效”一眼看出来；
	4. 适合长期维护脚本。

>
> 内置模板覆盖 Android/iOS 常见场景（例如 SSL Pinning Bypass、Method Hook、Native Hook、FS 监控等）。
> 说明：具体模板效果与目标实现有关，仍需按场景调整；工具侧提供的是工程化的“装配/管理”。
>
>
>

---

## 0x04 安装与环境

### 4.1 环境要求

- PyCharm 或 JetBrains 系列 IDE（建议 2024.3+）
- 本地 Python3 + 已安装 `frida-tools`
- 设备侧按你平时的 Frida 工作流准备：USB/Remote/Gadget 均可

### 4.2 插件安装

两种方式：

1. IDE 插件市场搜：`ZAFrida`
2. 或者下载本地包后从磁盘安装（适合内网/自编译）

| 1 | `GitHub: https://github.com/yilongmd/zafrida-ui` |
|-|-|

### 4.3 Frida 可执行文件路径

进入：
`Settings -> Tools -> ZAFrida`

如果插件没自动识别到 `frida / frida-ps / frida-ls-devices`，在这里手动配置即可。

---

## 0x05 快速上手（3 分钟跑起来）

1）在 Project View 右键：

- `New Frida Project`
- 选择平台 Android / iOS，输入项目名

2）进入 ZAFrida ToolWindow（右侧），选择：

- Device（USB / Remote / Gadget）
- Run Script（通常 agent.js）
- Target（包名/进程）
- 需要的话填 Extra args

3）点击：

- **Run**：Spawn 模式启动目标并注入
- **Attach**：附加到已运行进程注入

4）更快的方式（推荐）：直接打开脚本文件，在编辑区右键：

- **Run Frida JS** / **Attach Frida JS**

---

## 0x06 四个核心功能的“专业拆解”

### 6.1 “右键 Run Frida JS”为什么能自动切项目？

它的逻辑不是玄学，本质是一个**可预测的目录标记扫描**：

- 每个 ZAFrida 项目目录下有 `zafrida-project.xml`
- 当你在编辑器里对某个 `xxx.js` 右键 Run：
	- 从该脚本所在目录向上回溯
	- 在 IDE 根目录范围内寻找最近的 `zafrida-project.xml`
	- 找到即认为这个脚本属于该项目
	- 自动激活该项目，并在 Run 面板里把当前脚本设为 Run Script，然后执行

这类设计对逆向工作非常关键：**“脚本在哪里，就在哪个上下文里跑”**，减少“跑错设备/跑错包/跑错参数”的低级事故。

---

### 6.2 Snippets 为什么不是“鸡肋功能”？

逆向时常见节奏是：**试探 → 验证 → 改脚本 → 再试探**。
这类节奏最怕被“样板代码”打断。

右键 Snippets 做到的是：

- 快速插入常用结构
- 支持撤销/重做（符合 IDE 编辑器一致性）

这不是“多几个模板”的问题，而是把“写 Hook 的体力活”从工作流里剥离。

---

### 6.3 项目制管理对“多目标”更重要

在真实工作里，你很少只搞一个 App。项目制让你做到：

- **每个 App 一套上下文**：脚本、目标、连接方式、extra args、日志都能留在项目里
- Android/iOS 物理隔离目录，避免混淆
- 切项目即恢复状态，减少重复配置

团队协作也有价值：
把 `android/<app>/` 或 `ios/<app>/` 整个目录(git)交给同事, 可以同时维护

---

### 6.4 “取消勾选=注释而非删除”的意义

看起来是小细节，实际是工程化差异：

- 删除：短期爽，长期痛（找回困难、对比困难、误删概率高）
- 注释：可追溯、可复用、可对比、可组合

尤其当你维护“长期 hook 脚本库”时，模板的启用/禁用应该像开关，而不是“手工删改源代码”。

---

## 0x07 其它实用点

- 支持 USB / Remote / Gadget 多模式连接，不用手拼 `-U/-H/...`
- Run/Attach 分离：启动期 Hook 与运行期注入逻辑可以拆开
- 控制台输出 + 项目内日志落盘（便于复盘/留证）

---

## 0x08 写在最后：这个项目最想解决什么？

**一句话：让 Frida 的日常逆向工作从“终端参数驱动”变成“脚本/项目驱动”。**

- 你面对的是脚本文件：右键就跑
- 你维护的是项目上下文：切换就恢复
- 你组合的是模板积木：勾选就生效，取消就注释

---

---

# 回复

## 回复 by tDasm (#2)

*2026-2-7 10:04*

1、为什么要做成插件？完全可以做成独立exe文件在windows下运行。
2、为什么还要写js？完全可以自动生成。所有hook都有共性，根据不同类型的hook自动生成js，然后组合起来。

例如，hook java类方法，只是类名不同和方法名不同，其他js代码都一样。

## 回复 by afishlong (#3)

*2026-2-7 15:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  1、为什么要做成插件？完全可以做成独立exe文件在windows下运行。2、为什么还要写js？完全可以自动生成。所有hook都有共性，根据不同类型的hook自动生成js，然后组合起来。例如，hook ...
>
>

1、为什么要写成插件: 独立的exe巨大的缺点就是连JS编辑器你都要自己编写:
1.插件你就有优秀的JS编辑器(还有代码提示, 还能ai智能提示), 且可以直接运行Python(方便RPC);
2.在调试器要经常使用控制台和Frida交互, 独立exe又需要开发一个控制台, 以前的Frida UI一直不好用就是因为这个
2、当你用Frida调试的app越来越多后, 你就会发现, 还是得JS来的方便

## 回复 by tDasm (#4)

*2026-2-7 18:18*

>
> [afishlong](https://bbs.kanxue.com/user-924191.htm)
>
>  1、为什么要写成插件: 独立的exe巨大的缺点就是连JS编辑器你都要自己编写:
> 1.插件你就有优秀的JS编辑器(还有代码提示, 还能ai智能提示), 且可以直接运行Python(方便RPC);
>  ...
>
>

1要别人还要装集成ide？编辑js可以调用记事本。不需要写编辑器。
2自动生成js，几乎不需要自己写。最多只要修改js增加功能。现在都AI了还要自己写？没有AI都能自动生成何况还有？

## 回复 by afishlong (#5)

*2026-2-7 20:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>
>
>
>
>
>
>  afishlong
>
>
>
>  1、为什么要写成插件: 独立的exe巨大的缺点就是连JS编辑器你都要自己编写:
> 1.插件你就有优秀的JS编辑器(还有 ...
>
>

那你就继续使用记事本+命令行即可
1、集成IDE
1.你开发不用IDE吗?
2.你写Python也是用的记事本?
3.调用记事本那不是搞笑吗?
4.代码高亮呢?
5.frida js代码提示呢?
6.git代码版本管理+团队合作呢?
2、百分百用ai吗? 看来你frida用的不多啊

## 回复 by afishlong (#6)

*2026-2-7 20:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>
>
>
>
>
>
>  afishlong
>
>
>
>  1、为什么要写成插件: 独立的exe巨大的缺点就是连JS编辑器你都要自己编写:
> 1.插件你就有优秀的JS编辑器(还有 ...
>
>

Q1：为什么要开发成PyCharm等IDE的插件?
可以充分使用IDE的编辑能力, git集成, 项目管理能力

Q2：使用IDE的编辑JS脚本有什么优势?
代码高亮, 补全, 折叠等编辑功能
AI辅助编程(如CodeWhisperer, Copilot等)
版本管理(git等), 团队协作
多文件管理
多项目管理

Q3：每次调试为什么要保存日志?
首先不管是哪个操作系统Console的输出都是临时的, 关闭命令行/关闭IDE就没了
其次Console是有容量限制的, 输出过多会被截断
最后日志文件方便后续分析和分享

## 回复 by tDasm (#7)

*2026-2-7 21:17*

你不觉得你的理由很牵强？把一个简单的事复杂化，安装python带编辑器吗？从来就是用记事本写python代码。当然能力不同，有些人必须依赖集成ide。都自动生成js了，有些人还在手工码代码。拼命强调编辑器的重要。

## 回复 by afishlong (#8)

*2026-2-7 22:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  你不觉得你的理由很牵强？把一个简单的事复杂化，安装python带编辑器吗？从来就是用记事本写python代码。当然能力不同，有些人必须依赖集成ide。都自动生成js了，有些人还在手工码代码。拼命强调编 ...
>
>

666, 跟"从来就是用记事本写python代码"的大佬比不了

## 回复 by Imxz (#9)

*2026-2-8 18:30*

tql

## 回复 by wx_ㅤ_683 (#10)

*2026-2-9 11:46*

输出中文会乱码

## 回复 by afishlong (#11)

*2026-2-10 14:51*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  输出中文会乱码
>
>

是控制台输入的日志中文有乱码是吗?

## 回复 by Loopher (#12)

*2026-2-10 15:41*

不错的,不过这个脚本是否能支持frida高版本的API变化,有些脚本无法跑起来

## 回复 by afishlong (#13)

*2026-2-12 02:47*

>
> [Loopher](https://bbs.kanxue.com/user-723906.htm)
>
>  不错的,不过这个脚本是否能支持frida高版本的API变化,有些脚本无法跑起来
>
>

具体哪个版本的Frida呢，我测试适配下，我平时都是使用16.5多一点。

## 回复 by mb_empsallg (#14)

*2026-2-12 10:41*

这个东西对我来说 很有用  感谢大佬开源 已star

## 回复 by afishlong (#15)

*2026-2-12 17:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_empsallg](https://bbs.kanxue.com/user-1006824.htm)
>
>  这个东西对我来说 很有用 感谢大佬开源 已star
>
>

![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by wx_ㅤ_683 (#16)

*2026-2-22 13:04*

>
> [afishlong](https://bbs.kanxue.com/user-924191.htm)
>
>  是控制台输入的日志中文有乱码是吗?
>
>

对

## 回复 by afishlong (#17)

*2026-2-28 19:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  对
>
>

我修复了, 你看看还有没, 你的PyCharm默认是什么编码? 是utf-8还是其他?

## 回复 by afishlong (#18)

*2026-2-28 19:55*

方便的话给我截个图

## 回复 by fjqisba (#19)

*2026-2-28 20:01*

有AI了，还需要吗

## 回复 by afishlong (#20)

*2026-2-28 20:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  fjqisba](https://bbs.kanxue.com/user-729528.htm)
>
>  有AI了，还需要吗
>
>

有AI还是敲打命令, 自动生成的js也得附加, 这个只是方便管理Frida项目, 让多个App调试更方便而已. 后续也可以搞个ZA FridaUI-MCP, 这样就可以直接让AI帮我们动态调试了

## 回复 by user_adb (#21)

*2026-3-5 16:29*

>
> [afishlong](https://bbs.kanxue.com/user-924191.htm)
>
>  我修复了, 你看看还有没, 你的PyCharm默认是什么编码? 是utf-8还是其他?
>
>
>

pycharm默认编码模式UTF-8,为啥控制台输出日志中，中文还是乱码的，需要怎么解决。

## 回复 by afishlong (#22)

*2026-3-5 20:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_magic_rookie](https://bbs.kanxue.com/user-939450.htm)
>
>  pycharm默认编码模式UTF-8,为啥控制台输出日志中，中文还是乱码的，需要怎么解决。
>
>

下一个版本0.3.0会修复哈

## 回复 by afishlong (#23)

*2026-3-5 20:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_magic_rookie](https://bbs.kanxue.com/user-939450.htm)
>
>  pycharm默认编码模式UTF-8,为啥控制台输出日志中，中文还是乱码的，需要怎么解决。
>
>

0.3.0会更新, 如果是你提交的issues麻烦查看一下我的回复
