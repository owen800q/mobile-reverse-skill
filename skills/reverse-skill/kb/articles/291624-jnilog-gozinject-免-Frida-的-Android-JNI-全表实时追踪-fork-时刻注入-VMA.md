---
title: '[原创]jnilog + gozinject：免 Frida 的 Android JNI 全表实时追踪（fork 时刻注入 + VMA 隐藏）'
url: https://bbs.kanxue.com/thread-291624.htm
tid: 291624
author: Arsylk
date: '2026-06-16'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T13:51:02+08:00'
replies: 15
---

**翻译声明**：本文由英文原文经 AI 翻译整理，可能存在表述或技术细节上的偏差。如有歧义，请以  [英文原文](https://github.com/Arsylk/jnilog)及源码为准。

# jnilog + gozinject：免 Frida 的 Android JNI 全表实时追踪

> 一个注入的 ARM64 `.so` 即可 hook 完整的 Android `JNINativeInterface`（228 项）函数表，把 JNI 活动渲染成**带类型、带颜色、带符号化**的实时追踪。`jnilog` 负责追踪；`gozinject` 在进程 **fork 时刻**完成加载——不用 `ptrace`、不用调试器 attach，并可对目标进程隐藏 VMA。

![image](https://bbs.kanxue.com/upload/attach/202606/1008914_WF22AHPZAV2X3CN.webp)

| 工具 | 角色 | 版本与形态 |
|-|-|-|
| [`jnilog`](https://github.com/Arsylk/jnilog) | JNI 追踪载荷 | `1.1.0`；Android/arm64 cgo 共享库；hook 全部 228 个 JNI 表项 |
| [`gozinject`](https://github.com/Arsylk/gozinject) | 加载器/注入器 | `1.0.0`；Android/arm64 Go 注入器；root，zygote fork 时刻加载 |

一句话：`gozinject` 趁应用原生反篡改尚未武装时，把 `libjnilog.so` 送进全新的应用进程；随后 `jnilog` 记录 JNI 边界上的每一次调用，并附带足以直接用于逆向的类型信息。

---

## 目标应用

![image](https://bbs.kanxue.com/upload/attach/202606/1008914_BFDW5ZW2Q5HGTQM.webp)![image](https://bbs.kanxue.com/upload/attach/202606/1008914_VPBFUP4DZ5C6YF3.webp)

本次抓取目标是 `myphotocom.allfasttranslate.transationtranslator`（“All Photo Translator”，版本 `10.278.00`），一款免费含广告的 OCR/翻译应用，是个相当真实的分析目标：

- `targetSdk 30`，360 加固（`libjiagu_64.so`、`com.stub.StubApp`、`com.qihoo.util.QHClassLoader`）
- 集成 Facebook / Firebase / AdMob SDK
- 首个可见 Activity 之前有大量原生引导（bootstrap）逻辑

一次冷启动在前 35 秒内产生了 **5,599 个 JNI 事件**。

---

## 追踪输出长什么样

冷启动早期，直接来自 logcat：

```
[FindClass] "android/os/Build$VERSION" -> android.os.Build$VERSION @ 0x72efb80fd0
[GetStaticIntField] android.os.Build$VERSION.SDK_INT: int -> 36 @ 0x72efb8106c
[RegisterNatives] com.stub.StubApp {interface14(int): java.lang.String @0x72efb57f1c, mark(): void @0x72efbbc2fc, ...}
[GetStaticFieldID] com.stub.StubApp.needX86Bridge: boolean -> 0x3056 @ 0x72efb5ce34
[GetStaticFieldID] android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE: int -> 0xac0e @ 0x72efc4aa3c
[GetStaticFieldID] android.content.pm.PackageManager.GET_SIGNATURES: int -> 0xbe5a @ 0x72efbb3830
```

不打开反汇编器，从上往下读就已经有价值：`SDK_INT` 暴露加固壳正在走的设备/ROM 判定路径，`needX86Bridge` 是 Jiagu 的 x86 桥接决策，`FLAG_DEBUGGABLE` 是一次反调试检查，`GET_SIGNATURES` 开始一次签名/篡改校验。

**关于地址列**：上面每个调用方都是裸地址 `0x72ef…`——本阶段 Jiagu 引导逻辑运行在已解密的匿名内存里，没有文件映射的模块可作基准，裸地址就是最诚实的结果。一旦执行落入已映射的 `libjiagu_64.so`，同一列就符号化为 `libjiagu_64.so!<offset>`，给出稳定、与重定位无关的位置：

每行 `Call*Method` 都可能有独立的返回行，两者用单调递增的 `#id` 关联，因此多线程交错写入 logcat 仍可读，调用即便在返回前崩溃也依然可见。下面是应用读取 Android ID 并把它带入原生代码：

```
[CallStaticObjectMethodV] #63a android.provider.Settings$Secure::getString(...ApplicationContentResolver@e09d4c1, "android_id") @ 0x72efb59a30
[CallStaticObjectMethodV] #63a -> "79debbe244469315"
[GetStringUTFChars] #63b ("79debbe244469315") @ 0x72efbaed2c
```

重点不只是 `getString()` 被调用了——返回值被配对、被渲染，紧接着就能看到它通过 `GetStringUTFChars` 跨入原生内存。输出是带类型的：`jstring` 渲染为带引号的字符串，`jclass` 渲染为点分类名，数组按上限截断显示元素，对象返回值被渲染出来而不是留下一个不透明句柄。

---

## jnilog 工作原理

`libjnilog.so` = Go 运行时 + C hook 层，由 `go build -buildmode=c-shared` 构建。加载时其构造函数解析 ART/JNI 入口、找到存活的 `JavaVM`，复制一份 `JNINativeInterface` 表、替换表项、临时改写页保护完成替换，此后每个线程的 `JNIEnv` 都路由经这张被 hook 的表。当前覆盖全表 **228 项**（方法调用 93、字段 36、查找 5、注册 2、引用 9、字符串 12、数组 44、异常 7、类/对象/缓冲区/其它 20）；难以手写维护的几族用 X-macro 生成。

**热路径不回调 Go。** 早期版本用 C→Go 的 cgo 回调，但在受保护应用上，每事件的 cgo 跨越所引发的 Go 调度活动本身就是一个完整性信号。当前改用一条二进制事件管道：

```
hook 入口 -> 栈上事件编码 -> AF_UNIX SOCK_DGRAM 发送 -> Go reader goroutine
```

数据报上限 `8192` 字节，字符串带长度前缀、分帧字节转义、截断回退到安全的 UTF-8 边界。消费端落后时，hook 丢弃事件而非阻塞应用线程，并周期性汇总丢弃计数。对象渲染也被安全地延迟：只有消费线程就绪才创建全局引用，所有权仅在数据报确实送达时才转交 Go，否则 hook 自行删除引用——否则泄漏的全局引用最终会耗尽 VM 的引用表。

**自给自足的 C 核心。** C hook 层在自身热路径上刻意避开可被重定向（reroutable）的 libc 调用：`str*/mem*`、`snprintf`、`malloc`、mutex/futex、`send/open/read/mprotect`（内联 `svc #0` 系统调用）、以及 `dladdr`/符号化（私有 `/proc/self/maps` + `.dynsym`）全部仓库内自实现。一道 `readelf` 导入门禁强制这点——任何已迁移的 libc 符号一旦重新出现在动态导入里，构建即失败。这并不是说整个进程零 libc 痕迹（Go 运行时仍有冷启动导入），而是更窄也更有用的主张：执行在 JNI hook 入口上的那段 C 桥接，避开了加固壳与同进程日志器最常 hook 的那些 libc 符号。

下面是真实抓取里的电话服务 hook 字符串，以及随后解密出的原生库加载级联：

---

## gozinject 如何加载

`gozinject` 不 attach 运行中的应用，而是在 **fork 时刻**捕获目标：

1. 解析目标 UID 与主 Activity，清除该 UID 现有的 `/proc/vma_hide` 条目。
2. 把载荷暂存到 `/data/data/<pkg>/.org.chromium.<random>.tmp`。
3. 字节级 patch zygote `libandroid_runtime.so` 里的 `android_os_Process_setArgV0`，再用 `am start` 启动应用。
4. 匹配到的子进程在 fork 后、应用代码尚未完全运行时命中 `setArgV0`；一段 428 字节的桩按 zygote PID + 应用 UID 过滤，映射一块 256 KiB 的 RWX stage 并跳入。
5. 4 KiB 的 stage 恢复原始 `setArgV0`，按序 `dlopen` 每个载荷，删除暂存文件，经 mailbox 上报进度。
6. 注入器恢复被改写的页，把载荷 `soinfo` 从链接器链表中摘除，并可选地对同 UID 的 `/proc/maps` 隐藏载荷/stage 的 VMA。

`vma_hide` 是唯一需要内核协助的层。没有该模块时，注入与 `soinfo` 摘除仍然有效，但载荷映射在 `/proc/self/maps` 中仍可见。设想的威胁模型是运行在应用 UID 内的反篡改扫描器；root 权限的读取者按设计可绕过该过滤。

---

## 配置、构建与运行

配置默认读 `/data/local/tmp/jnilog.json`（或 `JNILOG_CONFIG`）；无配置即“记录一切”。include 列表为空表示全开，一旦填入 `functions`/`categories` 就切换到白名单模式，`exclude` 始终优先；类别有 `methods / fields / lookups / strings / arrays / refs / exceptions`。`log_sinks` 当前默认在 logcat 之外再加一个异步文件 sink（带缓冲、周期 flush、受 `log_queue_size` 限流，溢出丢行而不阻塞 hook 线程）。`tools/jnilogcfg` 是独立的 Go 模块，提供 TUI/CLI 编辑并经 adb 推送配置。

![image](https://bbs.kanxue.com/upload/attach/202606/1008914_Z3QXQVAVUK5Z2SR.webp)

```
# 构建 jnilog
cd /opt/github/jnilog
export ANDROID_NDK_HOME=/path/to/android-ndk
xmake b jnilog

# 用 gozinject 注入并流式查看
cd /opt/github/gozinject
xmake run --pkg=myphotocom.allfasttranslate.transationtranslator \
          --lib=/opt/github/jnilog/dist/libjnilog.so \
          --debug --logcat --logtag=JniLog
```

当前 logcat tag 是 `JNILogPayload`；若你按旧 tag（如 `JniLog`）过滤，可能载荷在正常工作，而你的过滤器把每一行追踪都藏了起来。

---

## 小结

对加固密集的 Android 目标，JNI 边界往往正是那些有趣事实变得具体的地方：包名、签名校验、设备 ID、权限查询、解密后的库加载、原生方法注册、字节数组载荷与框架调用。`jnilog` 把这条边界变成一份带类型的实时记录；`gozinject` 通过尽早加载（无需对运行中进程 `ptrace` attach）、并清理掉同进程反篡改最先检查的加载器痕迹，让这份记录在更难的目标上也成为可能。

它既不是万能绕过，也不是对任意载荷行为的隐身保证，而是一条聚焦的分析流水线：尽早加载、隐藏加载器表面、精确记录 JNI，并让各种取舍始终可见。

---

**代码：**[github.com/Arsylk/jnilog](https://github.com/Arsylk/jnilog) ｜ **加载器：**[github.com/Arsylk/gozinject](https://github.com/Arsylk/gozinject)

*仅供经授权的逆向工程、应用分析与安全研究使用。*

---

# 回复

## 回复 by jyotidwi (#2)

*2026-6-16 17:00*

thanks for sharing

## 回复 by mb_iesvmzqc (#3)

*2026-6-16 17:01*

thanks for sharing

## 回复 by 哈哥 (#4)

*2026-6-16 17:30*

thanks for sharing

## 回复 by 温泉划水鱼 (#5)

*2026-6-17 11:32*

感谢分享

## 回复 by XCicada (#6)

*2026-6-17 14:40*

thanks for sharing

## 回复 by 九黎 (#7)

*2026-6-17 14:49*

thanks for sharing

## 回复 by New对象处 (#8)

*2026-6-17 14:58*

six six six

## 回复 by hyz111 (#9)

*2026-6-18 10:49*

thanks for sharing

## 回复 by 啊你好哇123 (#10)

*2026-6-18 12:57*

这个要root才能使用吗

## 回复 by x1a0f3n9 (#11)

*2026-6-21 01:00*

thanks for sharing

## 回复 by Imxz (#12)

*2026-6-21 09:31*

tql

## 回复 by 宛枫 (#13)

*2026-6-21 22:48*

感谢分享，十分有用

## 回复 by Mengz3 (#14)

*2026-6-22 12:02*

thanks for sharing

## 回复 by x1a0f3n9 (#15)

*2026-6-26 17:07*

试用了一下，非常好用![image](https://bbs.kanxue.com/view/img/face/039.gif)，特别注入工具，很稳定

## 回复 by 宛枫 (#16)

*2026-7-1 23:38*

vma_hide这个内核模块没有仓库地址吗? 找了一圈没找到![image](https://bbs.kanxue.com/view/img/face/051.gif)
