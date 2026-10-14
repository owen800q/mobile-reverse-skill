---
title: '[原创] BBA：开源 VA 沙箱，分身进程里直接跑 Frida Gum'
url: https://bbs.kanxue.com/thread-293209.htm
tid: 293209
author: 藤血虫
date: '2026-10-13'
tags: [Android安全, 原创, 工具脚本, 逆向分析, 系统相关, 源码框架]
crawled_at: '2026-10-14T08:55:17+00:00'
replies: 13
---

仓库：<https://github.com/openbba0/bba>

BBA 是一个 Android 应用分身沙箱，做法和常见的 VA 一样：不把访客装成系统里的另一个应用，而是把 APK 记进宿主自己的包数据库，用 Manifest 里预先声明的桩组件把进程拉起来，再在桩进程里换上访客自己的 `LoadedApk`、`Application` 和数据目录。宿主包名 `com.android.bba`，引擎包名 `com.android.bb`。同一包名可以开多份，用 `userId` 区分，0 是第一份。

和只做虚拟化的 VA 不同，arm64 上这份沙箱把 Frida Gum 的 Interceptor、Stalker 和一套 QuickJS 绑定放进了 `libbba.so`。开发机用 Spindle 把脚本送进指定分身，用法接近 Frida 命令行。

内核看到的 uid 始终是宿主的 uid。访客以为自己有独立包名、独立进程名、独立数据目录，这些是 Java 层改写和路径重定向做出来的。

## 三种进程

`BlackBoxCore.doAttachBaseContext` 按进程名分成三类。主进程和访客都不自己实现虚拟系统，两边都通过 `SystemCallProvider.call("VM")` 向 `:black` 要 Binder。

![image](https://bbs.kanxue.com/upload/attach/202610/757606_EGJZ4W2TEAZRKM9.webp)

金色箭头是控制：主进程拉起 `:black`，`:black` 再用桩 ContentProvider 叫醒 `:pN`。浅色箭头是 Binder：访客把 `IBActivityThread` 交回去，主进程和访客都用 `call("VM")` 取同一套虚拟服务。

| 进程 | 进程名 | 做什么 |
|-|-|-|
| Main | `com.android.bba` | 界面、装包、请求启动分身。第一次要用虚拟服务时，把 `:black` 拉起来。 |
| Server | `com.android.bba:black` | 虚拟包管理、活动栈、进程槽位、通知、账号、定位。Spindle 的 TCP `127.0.0.1:2408` 只在这里监听。守护进程默认开着，避免这个进程被冻住之后查包失败。 |
| VApp | `com.android.bba:p0` … `:p49` | 一个槽位一个访客进程。`BActivityThread` 在这里绑定真应用。绑定之后，调试器看到的进程名会被改成访客自己的进程名。 |

关系可以收成三条：

1. 主进程拉起 `:black`，再用 `call("VM")` 取服务、请求启动分身。
2. `:black` 分配空闲槽位，调用对应的桩 ContentProvider，把 `:pN` 叫醒，并把 `AppConfig` 送进去。
3. 访客交回 `IBActivityThread`。`:black` 对这条 Binder 做 `linkToDeath`。主进程和访客之后都用 `call("VM")` 取同一套虚拟服务。

更细的图和字段说明在仓库的 `docs/vapp-runtime.html`。

## 一次启动经过什么

1. 界面调用 `BlackBoxCore.launchApk(packageName, userId)`，请求进到 `:black` 里的活动栈。
2. `BProcessManagerService` 挑一个空闲的 `bpid`（0 到 49）。同一个包、同一个 `userId`、同一个进程名只占一个槽。
3. 桩 Provider 的 `android:process` 就是 `:pN`。系统为了处理这次 `call`，把访客进程拉起来。
4. 系统真正启动的是影子 Intent，组件是 `ProxyActivity$P<n>`。访客的 Intent、`ActivityInfo`、`userId` 塞在 extra 里。
5. `HCallbackProxy` 换掉 `ActivityThread.mH` 的回调，在框架创建 Activity 之前把事务改回访客的类。还没绑定就先 `bindApplication`，再把消息插回队列头。
6. `handleBindApplication` 换上访客的 `LoadedApk`，改 `argv0`，打开 IO 重定向，装上按包名登记的 Java hook，向 `:black` 注册 Spindle，然后才调用 `Application.onCreate`。

## 路径和 native

访客看到的 `/data/data/<包名>`、`/sdcard`、`/proc/self/cmdline` 会被重定向到宿主目录下的 `blackbox/`。Java 侧用前缀树保存规则，最长匹配；同一套规则再挂到 libc，避免 native 打开文件绕过去。已经位于 `/blackbox/` 下的路径不再改写。

native 库是 `libbba.so`。符号用 xdl 解析，inline hook 用 Frida Gum 的 Interceptor，不再另链一份 Dobby。arm64 上还静态链了 Capstone、Stalker 和 QuickJS。Stalker 会把自己所在的 `libbba.so` 可执行段排除掉。当前应用模块只编 `arm64-v8a`，链接时加了 `-z,max-page-size=16384`，适配 16 KB 页。

Java hook 是另一条线。SandHook / Xposed 兼容层在 `:beer` 模块。隐藏 API 用注解描述，编译期生成反射代理，生成类在 `black.android.*`。

## Spindle

Spindle 是开发机和进程之间的一条通道，用法接近 Frida 命令行。开发机只连 `:black` 的环回端口 2408，不读系统属性。主进程和分身都是普通 agent，通过 Binder 注册、收脚本、回日志。USB 调试时客户端做 `adb forward tcp:0 tcp:2408`。

\```
python3 tools/spindle -U -f com.example.app -l tools/test_js_api.js
python3 tools/spindle -U -n com.example.app -l tools/test_native_hook.js
python3 tools/spindle -U --list
\```

帧是小端 4 字节长度加正文，单帧最大 1 MB，和一次 Binder 事务的上限对齐。脚本到达 arm64 进程后由 QuickJS 执行，提供 `Interceptor`、`Stalker`、`Java`、`Memory`、`Process` 和 `console`。协议图在 `docs/spindle.html`。

## 模块

- `:app`：Kotlin 界面。应用列表、设置、GMS、伪造定位、关于页。
- `:core`：虚拟化引擎。系统服务、Binder 代理、IO 重定向、`libbba.so`。
- `:beer`：SandHook 与 Xposed 兼容层。
- `:reflection` / `:compiler`：隐藏 API 的注解和生成器。

欢迎提 issue，也欢迎直接改。运行时的细节以 `docs/vapp-runtime.html` 和 `docs/spindle.html` 为准。

---

# 回复

## 回复 by Wika (#2)

???????????

## 回复 by wx_摁。 (#3)

???

## 回复 by Yangser (#4)

好开兄弟

## 回复 by 欲拭泪 (#5)

好开兄弟

## 回复 by 温泉划水鱼 (#6)

怎么没了

## 回复 by 爱喝星冰乐 (#7)

666666666

## 回复 by 九黎 (#8)

？？？？？？

## 回复 by xingbing (#9)

什么逆向分析工具？

## 回复 by 我就是小熊猫 (#10)

如开

## 回复 by 藤血虫 (#11)

>
> [Wika](https://bbs.kanxue.com/user-845899.htm)
>  ???????????
>

开了

## 回复 by fjqisba (#12)

沙箱要做稳定，貌似有大量的适配工作啊![image](https://bbs.kanxue.com/view/img/face/073.gif)

## 回复 by 藤血虫 (#13)

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  fjqisba](https://bbs.kanxue.com/user-729528.htm)
>  沙箱要做稳定，貌似有大量的适配工作啊[em_073]
>

里面最重要功能是可以用集成轻量级的frida， 用于免root 分析app

## 回复 by Ahzn (#14)

虚拟盘就真得可以这样调用吗》
