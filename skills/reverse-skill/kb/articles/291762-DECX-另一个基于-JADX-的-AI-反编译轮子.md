---
title: '[原创]DECX：另一个基于 JADX 的 AI 反编译轮子'
url: https://bbs.kanxue.com/thread-291762.htm
tid: 291762
author: jygzyc
date: '2026-06-23'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:06:20+00:00'
replies: 77
---

# DECX：另一个基于 JADX 的 AI 反编译轮子

## 起因

前段时间用 jadx-ai-mcp 分析 APK，跑了几个小时，体验确实不错。Claude 能自己调 tool 读反编译代码、看导出组件、跟调用链，省了不少手动翻代码的功夫。

有一天晚上我想把 APK 丢到服务器上跑，本地 Claude 连过去用——本地风扇太吵了。结果发现不行。jadx-ai-mcp 的 Python MCP server 要通过 HTTP 连 JADX 插件的 API，而那个 API 只有在 JADX GUI 启动后才存在。

我当时觉得这很正常——JADX 本来就是个桌面工具。但后来仔细想了想：JADX 的反编译引擎 JadxDecompiler 是一个纯 Java 类，new 出来就能用。它根本不依赖 GUI。那为什么 MCP server 非得挂在 GUI 上？

这个念头改变了一切。如果 MCP server 能跟反编译引擎在同一个进程里跑，不经过 GUI，那整个工具链的形态就完全不同了。这就是 DECX 的起点。

## 架构：把核心逻辑从 GUI 里拆出来

jadx-ai-mcp 的架构是三层串联，这存在一个核心问题：MCP 协议层和反编译能力被 GUI 进程边界隔开了，MCP 离不开 GUI。

```Plain
JADX GUI 进程
  └── 插件（Java，内置 HTTP :8650）
        ↑ HTTP
  Python server
        ↑ MCP
  AI 客户端
\```

DECX 的做法是把所有能力放进一个独立的 decx-core 模块里。这个模块不依赖任何 UI 组件，只需要一个 JadxDecompiler 对象就能提供完整的反编译能力。所有代码——API 接口、Service 实现、MCP Tool 定义——全在core中实现

```Plain
┌─ decx-plugin (JADX GUI 内嵌)
decx-core ──────────┤
                    └─ decx-server (standalone fat jar)
                         ↑ 被它管理
                    decx-cli (TypeScript, 可选)
\```

`decx-core` 是一切的根基。它提供了一套**与传输层无关的 API/Services/MCP 实现**，不管你是通过 JADX 插件、独立jar、还是 TypeScript CLI 来用，底下的逻辑完全相同。

这层关系用 Kotlin 代码表达就是 `Decx` 的全局对象：

```Kotlin
object Decx {
    // 创建 API —— 同上，server/plugin/cli 都用这个
    fun api(decompiler, cacheEnabled = true, uiService = null): DecxApi

    // 创建 HTTP server —— plugin 和 standalone 都用
    fun httpServer(api, port): DecxServer

    // 创建 MCP server —— 同上，完全一样
    fun mcpServer(api, port): DecxMcpServer

    // 暴露 routes 和 tools —— 给外部做文档/检查用
    val routeGroups: List<DecxRouteGroup>
    val mcpTools: List<McpTool>
}
\```

同一个 **`Decx.mcpServer(api, port)`**，在 JADX 插件里调用和在 standalone jar 里调用，返回的是同一个类、同一套 29 个工具、同一种 MCP 协议实现。

```Plain
decx-core（独立模块，零 UI 依赖）
  ├── DecxApi           反编译能力的统一接口
  ├── DecxApiImpl       实现层，委派给各 Service
  ├── DecxRoutes        HTTP 路由表（按 common/context/android/ui 分组）
  ├── DecxServer        HTTP server（Javalin）
  ├── McpHttpServer     MCP server（Kotlin SDK + Ktor CIO）
  ├── McpToolRegistry   29 个 MCP tool 定义 + 参数校验
  └── DecompileGuard    异常防护，反编译失败自动 skip

         ↓ 三种接入方式，共用同一个 core

  ┌─ decx-plugin（JADX GUI 插件）
  ├─ decx-server（standalone fat jar）
  └─ decx-cli（TypeScript，管理 server 生命周期）
\```

### API 接口设计

```Kotlin
interface DecxApi {
    // Common Service
    fun getClasses(filter: DecxFilter): DecxApiResult
    fun searchGlobalKey(key: String, filter: DecxFilter): DecxApiResult
    fun searchClassKey(cls: String, key: String, filter: DecxFilter): DecxApiResult
    fun searchMethod(mth: String): DecxApiResult
    fun getMethodSource(mth: String, smali: Boolean): DecxApiResult

    // Context Service
    fun getClassSource(cls: String, smali: Boolean, filter: DecxFilter): DecxApiResult
    fun getClassContext(cls: String): DecxApiResult
    fun getMethodContext(mth: String): DecxApiResult
    fun getMethodCfg(mth: String): DecxApiResult
    fun getMethodXref(mth: String): DecxApiResult
    fun getFieldXref(fld: String): DecxApiResult
    fun getClassXref(cls: String): DecxApiResult
    fun getImplementOfInterface(iface: String): DecxApiResult
    fun getSubclasses(cls: String): DecxApiResult

    // Android Service
    fun getAppManifest(): DecxApiResult
    fun getExportedComponents(filter: DecxFilter): DecxApiResult
    fun getDeepLinks(): DecxApiResult
    // ... 等等

    // UI Service（仅 GUI 模式可用）
    fun getSelectedText(): DecxApiResult
    fun getSelectedClass(): DecxApiResult
}
\```

### Route 和 Tool 的一对一映射

DecxRoutes 定义 HTTP 路由，McpToolRegistry 定义 MCP tool。两者通过 routePath 一一对应：

```Kotlin
// DecxRoutes.kt — HTTP 路由
DecxRoute("/api/decx/get_classes", DecxKind.CLASSES) { api, params ->
    api.getClasses(params.filter())
}

// McpToolRegistry.kt — MCP tool（同一个 routePath）
routeTool(
    name = "get_classes",
    description = "Return class symbols from the current JADX project...",
    routePath = "/api/decx/get_classes",    // ← 和上面一样
    properties = filterProperties(),
    toPayload = { args ->
        linkedMapOf("filter" to filterPayload(args), "page" to pageArg(args))
    }
)
\```

## How To Use

由于核心架构和上层分离，我们能够直接使用 Decx 的独立 Jar，也可以使用 Jadx Plugin 的方式，为了方便使用，我也提供了几种方案。

### Server

`decx-server` 打成 fat jar 后，不需要 JADX GUI，不过建议还是使用 Cli / Plugin ，会更方便。

```bash
$ java -jar decx-server.jar --help
DECX Server — Java Intelligence Analysis Platform

Usage:
  java -jar decx-server.jar <file> [options]

Arguments:
  <file>                   Path to APK, DEX, JAR, AAR, or class file

DECX Options:
  -p, --port <port>           HTTP server port (default: 25419)
  --mcp                       Also start MCP Streamable HTTP server at http://127.0.0.1:<port+1>/mcp
  --no-mcp                    Disable MCP server (default)

JADX Options:
  All standard jadx-cli options are supported. Common ones:
  -j, --threads-count <n>     Processing threads count
  --show-bad-code             Show inconsistent code
  --no-imports                Disable use of import statements
  --no-inline-anonymous       Disable anonymous classes inline
  -r, --no-res                Do not decode resources
  --no-debug-info             Disable debug info parsing
  --deobf                     Activate deobfuscation
  --escape-unicode            Escape non-ASCII characters in strings
  --log-level <level>         Set log level (quiet, progress, error, warn, info, debug)

  For full list of options, see: https://github.com/skylot/jadx

Examples:
  java -jar decx-server.jar app.apk
  java -jar decx-server.jar classes.dex --port 9000
  java -jar decx-server.jar app.apk --mcp
  java -jar decx-server.jar library.jar -j 8 --no-res --show-bad-code
  java -jar decx-server.jar app.apk --deobf --no-imports

MCP:
  Enable with --mcp. MCP listens on HTTP port + 1, e.g. --port 9000 exposes http://127.0.0.1:9001/mcp

API Endpoints:
  POST /api/decx/get_classes        Get classes (params: filter)
  POST /api/decx/get_class_source       Get class source (params: cls, smali, filter.limit)
  POST /api/decx/get_method_source      Get method source (params: mth, smali)
  POST /api/decx/search_global_key      Search globally (params: key, search)
  POST /api/decx/search_class_key       Grep one class (params: cls, key, grep)
  POST /api/decx/search_method          Search methods (params: mth)
  POST /api/decx/get_method_xref        Method cross-references (params: mth)
  POST /api/decx/get_app_manifest       Get AndroidManifest.xml
  POST /api/decx/get_exported_components  Get exported components
  GET  /health                           Health check

DECX version: 3.4.0
JADX core:   (bundled)

License: GNU General Public License v3.0
Source:      https://github.com/jygzyc/decx

CLI tool connects to this server using: decx -P <port>
\```

### Jadx Plugin

这是最简单的使用方法了，打开 Jadx ，在插件列表里找到 Decx，安装即可。

### Cli

`decx-cli` 是 TypeScript 写的，管理 standalone server 的生命周期。通过 `--help` 命令能够看到怎么使用，当然，也可以直接安装对应的 decx-cli skill 来使用。

```Bash
$ decx --help
Usage: decx [options] [command]

DECX - Decompiler + X, CLI for deeper analysis of decompiled Java code, powered by JADX and custom
extensions

Options:
  -V, --version   output the version number
  -h, --help      display help for command

Commands:
  process         Start, inspect, list, and stop DECX analysis server sessions
  code [options]  Query decompiled classes, methods, source, control flow, and cross references
  ard [options]   Android app, framework, resource, permission, and device analysis commands
  self            Install and update the bundled decx-server.jar and npm CLI package
  help [command]  display help for command
\```

这里稍微讲一下`decx ard framework run` ，这是是 DECX 独有的能力——从连接的 Android 设备自动采集整个框架相关的代码并打包整合分析：

```bash
$ decx ard framework --help
Usage: decx ard framework [options] [command]

Build DECX-readable framework jars from connected devices or local framework file directories.

Options:
  -h, --help               display help for command

Commands:
  collect [options]        Pull framework files from a connected Android device
  process [options] <oem>  Process local framework sources and pack framework_<brand>_<vendor>.jar
  run [options]            Collect, process, pack, and optionally open a framework jar
  open [options] [jar]     Open a generated or explicit framework jar in DECX
  help [command]           display help for command
\```

整个过程包括四步流水线：

\```
[collect]
  adb shell → 扫描 /system/framework + /apex + /system_ext
  自动探测 OEM（ro.product.brand → xiaomi/huawei/samsung/...）
  adb pull 文件到本地

[process]
  解压所有 APEX → 提取 apex_payload.img → 提取 DEX
  处理 jar/apk 里的 classes.dex
  失败文件跳过不中断

[pack]
  所有 DEX 打进 framework_xxx_xxx.jar（单一 fat jar）

[open]
  启动 standalone DECX session
\```

这样，针对厂商魔改的框架代码，就能够去进行整合性分析，而这套流程的前提就是 `decx-core` 能脱离 GUI 独立运行。没有这个前提，CLI 没法自动启动 server；没有 server，framework jar 只能手动丢进 JADX GUI。

## One More thing...

既然已经做到这里了，那不如更近一步，做一些用来处理真实漏洞挖掘和分析的 skill 吧！

这里必须要感谢 https://github.com/oritera/Cairn 给了我启发——能不能将漏洞挖掘的过程做成一整套skill，但是不局限于漏洞知识，而是发挥模型本身的能力。

### `decx-app-vulnhunt`：APK 漏洞挖掘

这可能是五个 skill 里最核心的一个。它做的不是"用 AI 搜一下有没有漏洞"这种笼统的事，而是一套严格的 **subagent 委托 + 证据图** 流程。

主 agent 不碰代码。它的工作只有五件事：初始化项目、启动 DECX session、把具体的分析意图委托给 subagent、读取 subagent 的 JSON 摘要、按风险矩阵决定是否升级为正式漏洞。主 agent 跑 `decx code` 或读源码是违规的——所有分析都在 subagent 里完成。

subagent 收到一个 intent goal（比如"收集攻击面：导出组件、deep link、AIDL、动态 receiver" 或 "跟踪某个 entrypoint 到 sink，证明 5-tuple"），自己创建 intent、跑 `decx code` 查询、写 fact 和 edge 到证据图、solve 后返回结构化 JSON 摘要。subagent 不能"推理"出漏洞——必须通过 `decx code` 读到源码，用源码行作为 evidence。`validate*`、`check*` 这类方法名不算证据（可能只是命名习惯，不代表真的有校验逻辑）。

证据门要求 **5 种事实全部存在且由 ****`proves`**** 边连接**才能升级为正式漏洞：

| 类型 | 证明什么 |
|-|-|
| `entrypoint` | 导出组件，攻击者能调的入口 |
| `reachability` | 攻击者控制的输入能到达后续节点 |
| `control` | 攻击者控制的字段到达了 sink 参数 |
| `guard` | 保护机制被绕过、缺失、或放行 |
| `sink` + `impact` | 危险操作及其可见后果 |

复合漏洞链由五种边组合：`enable`（A 创建 B 需要的入口）、`carry`（A 传输数据给 B）、`amplify`（A 放大 B 的影响）、`bypass`（A 打穿 B 的保护）、`observe`（A 让 B 的影响可见）。

漏洞模式覆盖 30+ 种应用层场景：Intent 重定向、Bundle/key 失配、WebView JS bridge、Provider 数据泄露/SQL 注入/路径穿越、broadcast 劫持、PendingIntent 滥用、fragment 注入、task hijack、动态 dex 加载、跨 app 数据通道等。

### `decx-framework-vulnhunt`：Android 框架层漏洞挖掘

跟 app-vulnhunt 同样的 subagent 委托架构和证据图流程，但面向框架层 Binder 服务。证据门是 **6-tuple**，比 app 多一层 `identity` + `guard` 的 caller 身份证明：

| 类型 | 证明什么 |
|-|-|
| `service-entrypoint` | Binder 服务暴露了方法 |
| `binder-reachability` | 非特权 app 能触达这个方法 |
| `control` | 攻击者控制的参数到达了 sink |
| `identity` + `guard` | caller 身份和权限检查在 trust boundary 处的状态 |
| `sink` | 特权操作被执行 |
| `impact` | 系统级可见后果 |

框架层没有"导出组件"的概念——入口是 AIDL 方法和 Binder Stub/Proxy。reachability 要求证明 unprivileged call context 能真正到达方法实现，不是只看方法签名有没有 `@EnforcePermission`。

漏洞模式覆盖框架层特有的 10 种：权限缺失、`clearCallingIdentity` 后以 system 身份执行、caller 身份/package/user 混淆、Intent launch 特权滥用、ContentProvider 代理、callback/token 延迟身份问题、竞态条件（TOCTOU）、transition controller 劫持、Intent 校验-执行 gap（`getType()` 两阶段变化）、native socket/HIDL/HAL 等厂商攻击面。

框架层漏洞挖掘的前提是能拿到 Android 框架源码——就是 `decx ard framework run` 做的事。

### `decx-report`：漏洞报告自动生成

从证据图读取已确认的漏洞链，自动生成 HTML 或 Markdown 报告。四个等权重章节（目标情况→问题说明→组合链利用→安全建议）。报告不改写证据——`decx-report` 只从已确认的 evidence 中读取，不创造内容。

### `decx-poc`：漏洞 PoC 自动构建

从一条 verified chain 自动生成可编译的 Android PoC 应用。8 种攻击面模板（Activity/Broadcast/Provider/Service/Intent/WebView/Framework Service），每种硬编码了对应攻击面的正确利用模式。Sink 7 项重验证，任一失败标记 `dead-end` 不继续。

### `decx-cli`：基础设施

统一 decx-cli 命令行的参数规则、session 管理、告诉模型怎么使用 Decx。

### 五个 Skill 组成的闭环

\```
decx-cli 管理 session + 执行命令
    ↓
decx-app-vulnhunt / decx-framework-vulnhunt
  主 agent 委托 → subagent 分析 → 证据图 → 风险判定
    ↓
decx-report 从证据图生成报告
    ↓
decx-poc 从 verified chain 构建 PoC
\```

从 APK/框架丢给 AI 到拿到报告和 PoC 。decx + skill 完成整个 逆向 → 漏洞 → 报告 → PoC 的闭环。

## 结语

这个项目起源于实际的工作需求，但是也是因为有了 Jadx，jadx-ai-mcp，cairn 这些项目帮我打了底，才能有动力去实现这一套轮子。

项目地址：https://github.com/jygzyc/decx

---

# 回复

## 回复 by wx_插曲 (#2)

*2026-6-23 15:56*

66676

## 回复 by 夜惜风雨 (#3)

*2026-6-23 16:14*

6666666666

## 回复 by 温泉划水鱼 (#4)

*2026-6-23 16:25*

kk

## 回复 by x1a0f3n9 (#5)

*2026-6-23 20:52*

有用，感谢分享，jadx的gui好用但是问题实在太多了

## 回复 by jygzyc (#6)

*2026-6-23 20:59*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  有用，感谢分享，jadx的gui好用但是问题实在太多了
>

有问题的话可以提交issue，高强度更新![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by jyotidwi (#7)

*2026-6-23 21:18*

tql

## 回复 by mb_rjdrqvpa (#8)

*2026-6-23 21:34*

佬，你这个项目和jadx mcp有什么区别，优点？除了不依赖jadx GUI+找漏洞，对于逆向，有什么帮助？

## 回复 by mb_roiscepd (#9)

*2026-6-23 21:35*

tql

## 回复 by jygzyc (#10)

*2026-6-23 23:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>  佬，你这个项目和jadx mcp有什么区别，优点？除了不依赖jadx GUI+找漏洞，对于逆向，有什么帮助？
>

工程化和自动化

## 回复 by mb_pfgnxxyq (#11)

*2026-6-23 23:19*

666

## 回复 by mb_ysikfhxt (#12)

*2026-6-24 08:46*

111

## 回复 by buluo533 (#13)

*2026-6-24 09:24*

学习了

## 回复 by 千谦 (#14)

*2026-6-24 09:34*

666

## 回复 by 恋~ (#15)

*2026-6-24 09:35*

6666

## 回复 by lbunknow (#16)

*2026-6-24 09:51*

666

## 回复 by mb_zoyhhbnr (#17)

*2026-6-24 10:02*

666

## 回复 by Snowman_Liam (#18)

*2026-6-24 10:17*

6666

## 回复 by wx_北极星_493 (#19)

*2026-6-24 11:03*

看看

## 回复 by _Mask_ (#20)

*2026-6-24 11:18*

看看

## 回复 by mb_euhyowpw (#21)

*2026-6-24 11:49*

666

## 回复 by xingbing (#22)

*2026-6-24 14:56*

学习了

## 回复 by amwpecel (#23)

*2026-6-24 15:39*

9999

## 回复 by 随风而行aa (#24)

*2026-6-24 15:45*

看看

## 回复 by shuangmou (#25)

*2026-6-24 17:21*

感谢分享

## 回复 by 熊猫吃鱼 (#26)

*2026-6-24 17:40*

66666

## 回复 by qqsunqiang (#27)

*2026-6-24 20:17*

谢楼主

## 回复 by ldehua (#28)

*2026-6-24 21:49*

学习了

## 回复 by YoungBai (#29)

*2026-6-25 08:45*

666

## 回复 by mb_elqwyvnm (#30)

*2026-6-25 17:28*

看看大

## 回复 by 张恒_884729 (#31)

*2026-6-25 17:42*

1111111112

## 回复 by 52bug (#32)

*2026-6-26 07:40*

看一看

## 回复 by ulong9527 (#33)

*2026-6-26 08:46*

66666

## 回复 by zzw_xjx (#34)

*2026-6-26 08:56*

感谢分享

## 回复 by huangjw (#35)

*2026-6-26 09:32*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 淡然出尘 (#36)

*2026-6-26 17:28*

感谢分享

## 回复 by mb_ebihoycp (#37)

*2026-6-26 17:55*

感谢分享

## 回复 by s1nec-1o (#38)

*2026-6-26 18:01*

1

## 回复 by 墨穹呢 (#39)

*2026-6-26 18:01*

感谢分享

## 回复 by Midsw (#40)

*2026-6-26 18:04*

666666666666

## 回复 by FMNS (#41)

*2026-6-26 20:48*

6666

## 回复 by mb_undccabr (#42)

*2026-6-27 21:24*

666666666666666666666

## 回复 by zylyy (#43)

*2026-6-28 02:52*

666

## 回复 by mb_qqihqaoo (#44)

*2026-6-28 12:27*

666666

## 回复 by LoginUser (#45)

*2026-6-29 08:59*

感谢分享

## 回复 by 4Chan (#46)

*2026-6-29 15:14*

学习一下

## 回复 by tobecome (#47)

*2026-6-29 16:33*

666

## 回复 by fuqiuluo73 (#48)

*2026-6-29 16:39*

感谢分享

## 回复 by yyyyy——— (#49)

*2026-6-29 17:50*

666666

## 回复 by Kaedehara (#50)

*2026-6-30 00:26*

1111

## 回复 by starrynight (#51)

*2026-6-30 09:14*

感谢分享

## 回复 by r0reborn (#52)

*2026-6-30 10:00*

6666

## 回复 by mb_qimctavn (#53)

*2026-6-30 11:11*

6

## 回复 by 喜欢就去抢啊 (#54)

*2026-6-30 13:06*

感谢分享

## 回复 by 阿牛 (#55)

*2026-6-30 14:30*

直接变成命令行工具？

## 回复 by mJqalJqN (#56)

*2026-6-30 14:34*

1

## 回复 by zzcc (#57)

*2026-6-30 15:17*

有集成的ai不

## 回复 by zzcc (#58)

*2026-6-30 15:18*

感谢分享

## 回复 by SeanMelon (#59)

*2026-6-30 15:54*

666

## 回复 by 寻梦之璐 (#60)

*2026-6-30 15:58*

1111

## 回复 by mb_cbgtaveo (#61)

*2026-6-30 16:42*

66666666666

## 回复 by wx_三生三世 (#62)

*2026-6-30 19:14*

学习

## 回复 by GangJust (#63)

*2026-7-1 15:23*

![image](https://bbs.kanxue.com/view/img/face/056.gif)好巧不巧，前段时间刚好也让AI造了一个轮子(主要就是解决jadx爆内存的问题)：https://github.com/DexClub/dexclub-cli.git

## 回复 by iBa0 (#64)

*2026-7-2 08:16*

3666

## 回复 by CheRevir (#65)

*2026-7-3 16:20*

666

## 回复 by sonnysu (#66)

*2026-7-3 16:43*

感谢分享

## 回复 by mb_exbhobav (#67)

*2026-7-4 16:37*

感谢分享

## 回复 by mb_mlnrhmls (#68)

*2026-7-5 10:29*

66

## 回复 by LeYiAo (#69)

*2026-7-6 06:23*

前人栽树

## 回复 by AAA撒拉嘿 (#70)

*2026-7-6 09:02*

感谢分享

## 回复 by jygzyc (#71)

*2026-7-6 11:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  GangJust](https://bbs.kanxue.com/user-915328.htm)
>  [em_056]好巧不巧，前段时间刚好也让AI造了一个轮子(主要就是解决jadx爆内存的问题)：https://github.com/DexClub/dexclub-cli.git
>

学习学习![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 乐观的李阔 (#72)

*2026-7-7 09:13*

666

## 回复 by 呼吸24K纯氧 (#73)

*2026-7-7 09:23*

看看隐藏

## 回复 by 云觞 (#74)

*2026-7-7 23:14*

6666

## 回复 by wx_kx92911 (#75)

*2026-7-9 09:53*

感谢分析

## 回复 by mb_tkkolqmp (#76)

*2026-7-13 22:54*

感谢分享

## 回复 by 洪堡企鹅 (#77)

*2026-7-16 10:51*

666

## 回复 by wx_天马行空之Apple (#78)

*2026-7-16 11:34*

感谢奉献
