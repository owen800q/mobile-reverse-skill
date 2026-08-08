---
title: '[原创]不同真机 trace 工具性能对比、优化点分享、xfQtrace使用说明'
url: https://bbs.kanxue.com/thread-291372.htm
tid: 291372
author: x1a0f3n9
date: '2026-05-28'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:07:27+00:00'
replies: 113
---

# 不同真机 trace 工具性能对比、优化点分享、xfQtrace使用说明

>
> 2万字长文，写了给我累死了，本来可以直接随便写写就发的，但是还是写好一些吧，唉，我这算是完美主义者么？
>
>
>

本文分三大部分：

1. **第一部分 · 省流版：5 个真机 trace 工具实测对比** — 一上来直接甩数据，光说概念没意思。
2. **第二部分 · 正文版：trace 介绍 / 真机 trace 工具优点分享** — 主流 trace 工具梳理 + 个人对现有真机 trace 的看法 + xfQTrace 优化思考；感觉这部分看了对于面试是挺有用的，或者总结成skill丢给ai也不错呢。
3. **第三部分 · 星球版：xfQTrace 使用说明** — 部署 / 自动化脚本 / JSON 配置 schema / 6 个导出 API。

新手老手都能看，希望对你有用。如果是 [星球](https://t.zsxq.com/N8xEH) 用户可以直接移步第三部分，当然建议前面也看看；

---

# 第一部分 · 省流版：5 个真机 trace 工具实测对比

## 同口径实测：QTrace vs GumTrace vs vm-trace vs AndroidPrybar vs xfQTrace

我知道大家最想看啥，所以把对比放到前面来了；我把5个trace工具在**同一个目标函数**上跑一遍最直观。bench 用的 demo：

>
> 当然有人会杠说我测试不够多啥的，对此我只能说事实胜于雄辩，不信就自己测试。
>
>
> 哦因为介绍了我自己的trace工具，可能还会有人说软广啥的，随便说，好的工具值得拿出来宣传，而且我自己也把优化点分享出来了(我觉得做到这一步已经很好了),有动手能力的都能自己写一个trace工具。
>
>
>

- 目标 `libxftest.so` 偏移 `0x20414` 的 `run_all_test`（demo 里挂了 SHA1/SHA256/MD5/CRC32/Base64/Hex 各种循环算 + memcpy/strcmp/syscall 等）
- 量级 ~3613 万指令、单线程主路径
- 真机 Pixel 5 / Android 13 / arm64（算是一款垃圾手机了）
- 计时口径：用 frida `Interceptor.attach` 挂 `Java_com_xiaofeng_qbdi_MainActivity_nativeRunAllTests` 的 onEnter / onLeave，`Date.now()` 作差（即"trace 整个 native 入口的纯 wall time"）
- xfQTrace 一共跑两组：**默认**（`memory_trace=false`，和 gumtrace / qtrace / vmtrace / AndroidPrybar 同口径，只跑指令级 + JNI/syscall banner + 寄存器跳变）；**开 memory hexdump**（`memory_trace=true`，每条指令额外抓 PRE/POST 内存读写 + 字节级 hex 转储）。其它四家都没开内存读写监控
- 输出格式：xfQTrace = text + LZ4，其它四家都是无压缩文本
- vmtrace 的 `qbdi_vm_call(...)` 第 5 个参数 `dumpMem=0` 同步关闭

结果：

| 项目 | [zgy0x01/QTrace](https://github.com/zgy0x01/QTrace)（[看雪文章](https://bbs.kanxue.com/thread-290574.htm)，id：乐子人） | [lidongyooo/GumTrace](https://github.com/lidongyooo/GumTrace)（[看雪文章](https://bbs.kanxue.com/thread-290400.htm)，id：lidongyooo） | [jiqiu2022/vm-trace-release](https://github.com/jiqiu2022/vm-trace-release)（[看雪文章](https://bbs.kanxue.com/thread-285471.htm)，id：棕熊） | [GitKittys/AndroidPrybar](https://github.com/GitKittys/AndroidPrybar)（无看雪文章） | LunFengChen/xfQTrace（本文，id：x1a0f3n9）关 memory hexdump | 开 memory hexdump |
|-|-|-|-|-|-|-|
| 开源 | 开源 | 开源 | 仅成品 | 仅成品（疑似后续开源） | 仅成品，[星球](https://t.zsxq.com/N8xEH) 成员免费使用，不额外单独收费 |  |
| 引擎 | QBDI VM（动态 DBI） | frida-stalker（动态重编译） | QBDI VM（动态 DBI） | Unicorn VM（仿真执行） | QBDI VM（动态 DBI） | QBDI VM（动态 DBI） |
| wall_ms | 294 s | 32.0 s | 83.1 s | 崩溃 @ ~110 s（未完成） | **19.3 s** | 86.9 s |
| 处理速度 | 12.3 万 insn/s | 113 万 insn/s | 43.5 万 insn/s | 失败 | **187 万 insn/s** | 41.6 万 insn/s |
| raw 字节 | 2.55 GB | 3.71 GB | 2.29 GB | — | 2980 MB | 4527 MB |
| 落盘字节 | 2.55 GB（无压缩） | 3.71 GB（无压缩） | 2.29 GB（无压缩） | 0（崩溃，缓冲未刷盘） | **272 MB**（LZ4，91% 压缩比） | 351 MB（LZ4，92% 压缩比） |
| raw 吞吐 | 8.9 MB/s ≈ 0.52 GB/min | 119 MB/s ≈ 6.95 GB/min | 28.2 MB/s ≈ 1.65 GB/min | — | 154 MB/s ≈ **9.05 GB/min** | 52.1 MB/s ≈ 3.05 GB/min |
| 落盘吞吐 | 8.9 MB/s ≈ 0.52 GB/min | 119 MB/s ≈ 6.95 GB/min | 28.2 MB/s ≈ 1.65 GB/min | — | 14.1 MB/s ≈ **0.83 GB/min** | 4.0 MB/s ≈ 0.24 GB/min |
| 稳定性 | 完成 | 完成 | 完成 | 中段 SIGSEGV，VM 内部空指针 | 完成 | 完成 |

>
> 注：AndroidPrybar 崩溃位置在 `libtrace.so` 偏移 0x510a2c–0x5666c8 之间 8 帧（`SIGSEGV / SEGV_MAPERR / fault addr 0x0`），作者 README 也直接写了"代码让ai改崩溃了，一些功能不太稳定"。
>
>
> vmtrace 接口和其他几家不同：它要求"`Interceptor.replace` 目标函数 → callback 里调 `qbdi_vm_call(targetAddr, argsPtr, argNum, logPath, dumpMem)` → 返回结果"，等于把"切入 trace VM"和"调用目标"绑成了一次调用。某种程度上更直观（一行 trace 一个函数），但只能从函数边界进入，且接入方需要自己组装参数指针数组（参数个数填错会崩）。
>
>
>

几个观察点：

1. **同 VM 同行的 15× / 4.3× 加速**（同样基于 QBDI：xfQTrace 默认 19.3s vs QTrace 294s vs vmtrace 83.1s）。差距来源是这一篇后面讲的所有优化点累加：opcode-based 指令缓存、合并单回调延迟输出、CachedInstruction 紧凑布局、HookMap bloom filter、独立 trace 线程 + LZ4 异步刷盘、按需 anon 段发现等等。
2. **xfQTrace 默认配置也比 GumTrace 快**（19.3s vs 32.0s）。GumTrace 速度本来就是这几家里偏快的，开源真神！不过有一点值得提一下，gumtrace 稳定性还需提升，使用者遇到崩溃样本要有自己修改源码的能力。
3. **磁盘开销 13.6× 小**（默认 272 MB vs GumTrace 3.71 GB），落盘吞吐换成"每分钟"读起来更直观：xfQTrace 默认 0.83 GB/min vs GumTrace 6.95 GB/min vs vmtrace 1.65 GB/min vs QTrace 0.52 GB/min。LZ4 在指令级 trace 这种高重复度文本上压缩率非常高，原始 2980 MB 压到 272 MB（91% 压缩比），实战中遇到大样本（几亿指令）这一项才是决定能不能开 trace 的关键 —— 不压缩的话半小时下来 200+ GB 的文件 ripgrep 都嫌慢，磁盘也存不下。因为确实有500GB的样本比如淘宝；
4. **指令信息密度更高**。xfQTrace 这边日志里每条指令同时给 PRE 寄存器值 + POST 寄存器值 + JNI/syscall banner + 函数 call/ret 配对，这些都已经包含在 187 万 insn/s 这个数里了。
5. **开 memory hexdump 的"额外档位"**。xfQTrace 把 memory_trace 打开（每条指令额外抓 PRE/POST 内存读写 + 字节级 hex 转储）后是 86.9s / 4527 MB raw / 351 MB 落盘 —— 即便多干了内存抓取的活，wall 只比 vmtrace（默认无 memory dump）多 3.8s，比 QTrace 快 3.4×；落盘还是 LZ4 压完的 351 MB，比 vmtrace 不抓内存的 2.29 GB 还小约 6.5×。其他四家要么没这接口要么开了直接跑不动，这个档位是 xfQTrace 实战中的主要使用模式（逆向一个加密函数，看每条指令读了哪段 buffer / 写了哪个返回地址）。

>
> 当然这就是 demo 上的单点数据，实战中不同样本（深递归、大量子线程、自定义 linker、JNI 调用密集型等）相对差距会变。bench 脚本和 demo 已经放在仓库 `trace_compare/bench/` 下，欢迎自己换样本复现。
>
>
>

为什么会有这么大的差距？这就涉及指令级 trace 到底在做什么、各家选了什么底层引擎、还有 xfQTrace 在 QBDI 之上做了哪些工程化改动 —— 接下来一层层说清楚。

---

# 第二部分 · 正文版：trace 介绍 / 真机 trace 工具优点分享

先来一大段背景，可跳过：

>
> 最近一两个月，先是休息了半个月，打打游戏啥的，然后实在是压力太大了，一天不逆向浑身难受啊，跟蚂蚁在爬一样，然后就开始逆向了。最近一个月在学习密码学经典算法的设计原理相关的内容，感觉学起来还是有点难度的，很有意思。后续会用remotion来创作高质量视频，然后发布到b站给大家补点相关基础，放心讲的会非常非常详细，设计原理/手搓实现/汇编特征/魔改怎么逆等等；
>
>
> 然后平时偶尔逆向一下实战案例，一些安全SDK那种，过程中发现很多案例用unidbg来补会有一些问题，虽然中等难度的app大多都可以解决，但是稍微再难的就不方便处理了，与其耗时在深度魔改unidbg让其更像一个android，不如直接写一个优秀的真机trace工具；反正一个信息很全的trace日志，ai只需要使用ripgrep就可以暴力分析了，然后我们拿到分析结果之后就可以开始复现，这样可以利用ai当老师然后不断追问来进行学习，哪怕是vmp的案例也是照样逆完学习；
>
>
>

>
> 所以就会有明显痛点了，开源的真机trace好像有很多问题，而且直接用别人开源的成品好像原理啥的我也掌握不到位呀，俺是来学习的又不是来直接用成品的。所以一周前我开始学习qbdi，然后顺便开始开发我自己用的真机trace工具，连续3天睡眠加起来不超过14小时吧，也是非常抽象了，也是压根睡不着*几发还是一样哈哈哈哈；好在最近几天已经完工了，可以美美休息几天了。
>
>
> 然后感觉自己做的比开源的工具对比下来会有很多明显优点吧，自己也倾注了很多心血，而且后续还会支持俺的ttd；然后我认为单独收费卖感觉不太好，因为其实技术含金量不是很高，重要的是怎么思考到这些优化点，优化的点都是我一步步思考出来的； 那为啥我不打算免费发出来呢？
>
>
> - 一是白嫖的确实太多了，虽然我不讨厌白嫖，但是人要懂得知恩图报；很多人用了我开源的很多魔改工具或者明显参考了我的实战案例分享，但在自己分享的文章中压根连我名字都不愿意提，这让我有一点寒心呐。
> - 二是我的文章前段时间还 [被盗了](https://blog.csdn.net/2503_90751938/article/details/160523276)，那我的成品发出来不也会被盗么？大部分时候做的越好功劳越被抢走，做的但凡有一点不好使用反而还有傻逼跑过来骂我（身边认识的人已经有很多这种案例了）
> - 三是我最近发现有很多机构还有个别人会把别人的成品做一层包装，然后拿去授课用以及卖钱，这是我所绝对不能接受的，比如某灵机构/哆啦安全公众号等等。
>
>
> 基本上就是这三点，寒了多少愿意开源的朋友的心。所以仔细考虑下来，就打算把工具免费丢到 [星球](https://t.zsxq.com/N8xEH) 了。当然你也可以认为我是为了引流吧，我承认有这一部分原因，但更多的是心确实已经寒了。（另外其实我在b站已经送出去很多朋友 [星球](https://t.zsxq.com/N8xEH) 了，都是愿意分析文章或者工具或者都愿意点拨我的）
>
>
>

>
> 那发到 [星球](https://t.zsxq.com/N8xEH) 还有什么好处？
>
>
> - 方便维护：保证用的人都会认真看我的文章，不会再出现开源之后 傻逼不阅读readme就来加我qq甚至打听我微信一顿问的情况。
> - 一周年福利：这样之前进了 [星球](https://t.zsxq.com/N8xEH) 的朋友也不需要花钱照样就能使用了，也就当是发视频/创作 一周年一来各位朋友的支持吧；
>
>
> 因为诚实来说俺也没啥稳定收入，平时也不接点单，也没工作，现在就靠 [星球](https://t.zsxq.com/N8xEH) 赚点生活费，能靠这样能引流几个人进去也算不错了；我个人认为就这样处理最妥当，如果还是被喷的话那就随他吧，反正这圈子遇到的神人确实还挺多的哈哈哈哈；
>
>
> 但是！！有很多朋友仍然非常支持我，我觉得我也要做点什么！所以我会把这个工具的实现以及优化思考全都放出来吧，这样即使各位不愿意进 [星球](https://t.zsxq.com/N8xEH) 的朋友依旧可以拿本文喂给ai让他对开源的真机trace进行改造，具体见后文介绍（点击跳转）；
>
>
>

## 为什么要做真机指令级 trace？

安卓逆向里，trace 是绕不开的环节。先说啥是 trace。

trace 就是"跟踪"。我对 trace 的抽象理解是：**站在不同角度去观察一件事的发展**。

举个现实生活的例子：你看到一条新闻，它就一定是正确的吗？我个人认为现在的网络环境下，很多人会拿着单方或者疑似权威的说明就当作绝对正确。

- 站在**接收方**的视角：你只能被动接收作者写的文章 / 视频，事件真实性你是无法核验的。这年头新闻添油加醋、歪曲事实夹带私货、让某一方明显受益的太多了。
- 站在**撰稿方**的视角：你能多知道一些细节，但仍然是二手转述。
- 站在**亲历者**的视角：你能拿到更多更细的一手信息，但仍然可能因为偏袒自己而有意识/无意识修改真相。
- 如果你能**汇总多方亲历者**的口述，那对这件事的还原会大概率接近真相 —— 这也是文科领域（如历史研究）的经典方法论。

总结就是：视角越深、维度越多，你看到的事实就越接近真实。

trace 在逆向里也是这个道理 —— 你站在哪一层看，决定了你能看到的事实有多深。

>
> 但也不是越底层越好的，要综合评估，如性能开销还有实际效果，最底层的trace并不是适用于任何场景。
>
>
>

trace 其实有非常多种，只是现在大家提到 trace 默认指的是"指令级 trace"。下面我会从最浅到最深列一遍各级 trace，希望能帮大家拓宽一点思维 —— 这对于理解整个安卓逆向工具链的作用和发展史会很有帮助。

OK，假设你拿到一个 app，目标是分析清楚它"登录"按钮背后到底做了什么，从最浅到最深一层一层下去：

### 1. 黑盒观测 trace（UI / 日志 / IO / 网络）

点击登录按钮 → loading 弹窗 → 界面跳转 → 中间可能藏着各种日志上报、设备信息收集、风控埋点。这一层我们关心"app 对外露出来什么"——不进 app 内部，只看它在外部留下的痕迹。

下面是一些常见的"黑盒观测 trace":

- **logcat**：app 自身打的日志，很多 SDK / app 默认会留一堆 tag，可以选择一些常见的进行尝试，运气好可以抓到关键点，不过意义不大（一般只有在报错时会有error日志有点用）

	- `adb logcat -v time --pid=$(pidof com.foo)` 按进程过滤，避免被刷屏
	- [JakeWharton/pidcat](https://github.com/JakeWharton/pidcat)（开源）— 按包名彩色过滤的 logcat 封装，最经典的命令行查看器
- **抓包**：登录涉及把账号密码上传服务器，所以一定走网络协议。

	- 常见中间人工具抓http(s)包：Reqable（闭源）、Charles（闭源商业）、proxypin（开源）、mitmproxy（开源）、HttpCanary（闭源）、Burp Suite（闭源商业）、Fiddler（闭源）等等，https需要安装系统证书
	- `tcpdump`（开源）抓底层包：全量 pcap → wireshark 离线分析
	- hook 应用层底层实现抓包：[r0ysue/r0capture](https://github.com/r0ysue/r0capture)（开源）— 无视证书，frida hook应用层抓包，包含通杀TCP/IP四层模型中的协议；抓包后导出 pcap 再转 har，丢进 Reqable 分析，亦或者直接wireshark分析
	- hook 上层核心函数抓包：这一层语义非常强，基本是找到了App自己核心的收发包函数
	- 内核级别抓包：[gojue/ecapture](https://github.com/gojue/ecapture)（开源）— ebpf 抓 ssl/tls 明文，无需 patch app、无需装证书，对付 ssl pinning / 加固自定义 tls 栈非常有效；ebpfdump 系列也是同思路直接跑下来你会看到一堆 HTTP / TLS over TCP 的包，少数 app 会上 HTTP/3（也就是 QUIC over UDP）。这里就不展开抓包对抗的东西了。总之这一步价值非常的高，比如如果是http协议,你就能看到他的关键报文了；
- **文件 IO trace**：很多 app 会把 token / device id / 缓存 / dex 副本 / so 副本写到 `/data/data/<pkg>/` 或 sdcard，看它读写哪些文件能直接定位关键流程（特别是脱壳、找加密本地存储的密钥）

	- `strace -p PID -f -e trace=openat,read,write,unlink`（开源）— ptrace-based 全量 syscall 跟踪
	- `inotifywait`（开源，busybox / toybox 自带）— 监听某个目录的改动，定位"它把 dex 解到哪里"特别好用
	- `lsof`（开源）— 查目标进程当前打开的 fd / 文件路径
	- frida 自己 hook `open` / `fopen` / `pwrite` —— 可以加路径过滤，输出比 strace 干净
- **系统调用 / 内核 trace**：

	- `strace`（开源）/ `ltrace`（开源）— 全量 syscall / 库调用跟踪，能看到 ioctl / mmap / connect / sendto 等所有内核交互
	- `bpftrace`（开源）/ bcc — ebpf 实现，性能更好，且 ptrace 反检测对它无效
- **UI 行为分析**：

	- Android Studio 自带 Layout Inspector / Hierarchy Viewer — 看当前 activity 的 view 树、属性、坐标
	- `uiautomator dump`（系统自带）— 命令行 dump UI 树为 xml，AI 时代非常适合喂模型做自动化点击
	- `dumpsys activity top` / `dumpsys window`（系统自带）— 看当前 activity 栈、focused window、Fragment 栈
	- `getevent` / `sendevent`（系统自带）— 看输入事件（触摸 / 按键），适合做自动化或还原用户操作序列
	- 取证场景下还能从 apk 里抽 `strings.xml` / 配置文件 / 内嵌证书 / 资源 ID 反查界面
- **进程 / 服务 状态**：

	- `dumpsys`（系统自带）— `meminfo` / `activity` / `package` / `batterystats` 一堆子命令，能看 app 内存占用、组件注册、权限、电量行为
	- `pmap` / `/proc/<pid>/maps` — 看进程加载了哪些 so，定位动态加载的隐藏 so
	- `frida-ps -Uai`（开源）— 列出设备所有进程 / 应用，可以快速看出 app 是不是多进程

### 2. Java 反编译 + 静态分析

UI 层用的是 Java / Kotlin（绝大部分情况），那就把 apk / dex 拿出来反编译看，常见工具如下：

- [skylot/jadx](https://github.com/skylot/jadx)（开源）— （唯一真神！）出 Java 伪码、最常用，cli + gui 双形态；缺点是反编译经常失败
	- 这里可以建议使用我魔改的 [LunFengChen/jadx](https://github.com/LunFengChen/jadx)（开源）— 优点就是后面frida使用非常方便，100%的一键就能够丢入控制台；如关键数据类型（map，jbytearr，jobject等等非常多）的解析函数已经自带了；用过的都说好！！
	- 不过我还有部分代码没有提交，后续会抽时间继续维护，最大的就是后面争取学完java层混淆的解决方案的时候把反混淆内嵌进去，类似jeb那种效果；
- [JEB](https://www.pnfsoftware.com/)（闭源商业）— 反混淆能力强、支持脚本批处理
- [charles2gan/GDA-android-reversing-Tool](https://github.com/charles2gan/GDA-android-reversing-Tool)（开源）— 轻量高效、反编译基本不会失败; 但只有win版（这个工具如果支持跨平台，那也是真神！）
	- 这里值得提的是做安卓逆向还是推荐windows，问题少很多；如果涉及c的开发 推荐linux如ubuntu；mac的问题过多，很多逆向工具会存在未知原理的bug且相比ubuntu并未有明显优点，当然如果你有上述其他特殊需求或者你确实用mac舒服点那么依旧使用即可，这里只是建议！（当然最好的是直接一台电脑一个系统！反正现在一台电脑也不贵，每个电脑各司其职，mac上班用，自己用ubuntu，打游戏就用win，这多舒服！）
- [apktool](https://apktool.org/)（开源）— 出 smali、能回编译，现在更多作为 cli 工具被 ai / 上层工具调用

加壳的话需要先脱壳，方案很多，常见的有：

- [在线脱壳网站 56.al](https://56.al/) — 上传 apk 直接拿脱壳后的 dex，懒人首选
- [hluwa/FRIDA-DEXDump](https://github.com/hluwa/FRIDA-DEXDump)（开源）— frida 脚本，运行时扫内存 dump dex
- [lasting-yang/frida_dump](https://github.com/lasting-yang/frida_dump)（开源）— frida 脚本，同时支持 dump dex / dump so
- [CodingGay/BlackDex](https://github.com/CodingGay/BlackDex)（开源）— 不依赖环境的脱壳机，可以直接装到设备/集成进 app
- [hanbinglengyue/FART](https://github.com/hanbinglengyue/FART)（开源）— 基于 ART 主动调用的整体脱壳，老牌工具
- [Youlor/Youpk](https://github.com/Youlor/Youpk)（开源，俗称 youpk）— ART 主动调用脱壳，工程化做得不错
- [Youlor/unpacker](https://github.com/Youlor/unpacker)（开源）— 同作者的早期脱壳工程，可作参考
- [CrackerCat/FartExt](https://github.com/CrackerCat/FartExt)（开源，俗称 fartEx）— 在 FART 基础上做更深的主动调用，适配 AOSP10
- 各家定制脱壳机（不开源、内部流通）

上面的话推荐直接用网站，不行的话就得自己找脱壳机了，实在不行就找一个类似f利姬的热心 脱壳姬哈哈哈哈（俗称人脉脱壳），还是不行的话就得自己魔改咯。这里不过多展开。

拿到代码之后一般直接看 Java / Kotlin 源码 —— 高级语言可读性高，定位关键函数很快，如果遇到一些特殊情况，比如反编译失败或者混淆严重可以选择查看更底层的语言：smali汇编，在这里不多赘述；

总之通过这一步很容易找到关键函数，亦或者你用前面黑盒观测 trace 中分析出来的关键信息比如报文 header、xml 文件名等等定位也可以！

### 3. Java 函数 trace（hook ART 层）

知道哪个函数是关键之后，基本都需要做动态校验：到底有没有真的被调用？参数 / 返回值长什么样？主流两种方案：调试 / hook，本人基本不用调试，因为太麻烦啦！下面只聊 hook。

hook 思路：注入进程 → 改写函数入口出口 → 打印参数返回值 / 改写参数返回值。下面给一些我个人认为值得尝试的 hook工具：

- [Frida](https://frida.re/)（开源）`Java.use().method.implementation = ...` — 最灵活，cli / Python rpc 都行，同时支持 Java 层与 native 层
- [frida-trace](https://frida.re/docs/frida-trace/)（开源）`-j 'com.foo.*!sign'` — 本质依旧是frida内核，只是使用很简单；一行命令批量 hook，适合大量函数快速验证是否执行以及输出调用栈树
- [Xposed](https://repo.xposed.info/)（开源）/ [LSPosed/LSPosed](https://github.com/LSPosed/LSPosed)（开源）— 持久化 hook，适合长期监控；ART hook 稳定性比 frida 好，仅支持 Java 层
- [AlbatrossHook/AlbatrossAndroid](https://github.com/AlbatrossHook/AlbatrossAndroid)（开源）— 较新的 ART hook 框架，性能比 Xposed 好
- [sensepost/objection](https://github.com/sensepost/objection)（开源）— frida 的命令行封装，主要就是方便 hook

这里我觉得很有必要提醒一点：很多没列出的工具也很好用，但大多本质都是基于 frida / lsposed 的封装，目的都是省时间。这类封装对新手是降维打击，无脑使用即可；但对老手来说，遇到新样本时往往会感到束手束脚 —— 封装给你省了入门时间，但也屏蔽了底层细节。所以新手如果一上来就把大量时间花在二次封装工具上，那就错失了学习底层工具的窗口。

每个时代都会涌现大量二次封装工具，那些出名且能长期存活下来的项目，而且一直有人时不时维护，我认为这种才值得长期使用，或者你有改源码的能力；如果没有，此类项目一旦时间拉长，最终也基本只剩下源码学习的意义（比如学习如何封装）。对作者本人来说，很多项目只是为了解决自己在某一时期的需求，时间一拉长，就会有更好的解决方案了。

>
> 正所谓: 器本自通流，制器有来由，他铸合他求，探源得真枢，握得本根在，随心任去留。
>
>
>

综合下来，这里建议直接学 frida / lsp 就行了。但是有开发能力的朋友建议多思考多动手，万一你能做出更优秀的工具呢！！

我自己更喜欢灵活性高的方案，直接 frida cli + JS。哪怕是为了省时间，我也会给 ai 链上 jadx 的 mcp，让它自行查找关键函数，然后让它快速使用 frida cli + JS 验证：通过 hook 快速验证是否触发，以及打印获取调用栈。

到这一步大部分中等强度的 app 已经能搞定，比如本场景：抓密码 → hash → 拼报文header如sign → 发包模拟登录。但深度混淆（dex 加固 / Java 转 native）的 app 就没这么轻松了。

### 4. Smali trace（ART 实际执行的字节码）

Java 反编译失败、或者 jadx 出来全是 `<error: failed to decompile>`，亦或者需要做混淆验证 —— 那就深入本质，降到 ART 虚拟机字节码层面，也就是 smali。这时候要么静态硬啃 smali（jadx 直接切到 smali 视图即可），要么动态分析。

如果静态分析压力大，或者需要动态验证，那就要么动态调试 smali，要么对解释器插桩把"真实执行的 smali 汇编trace 出来：

- [JesusFreke/smali (smalidea)](https://github.com/JesusFreke/smali) — Android Studio 插件，可以下断点单步 smali
- [JEB Dynamic](https://www.pnfsoftware.com/) — 商业方案，集成调试 + smali 单步
- 自定义 Xposed / LSPosed 模块改 ART 解释器入口（`ExecuteSwitchImpl`、`artInterpreterToInterpreterBridge` 等）输出每条 smali —— 工程量大但能 trace 任意混淆下的真实执行流
- [PAGalaxyLab/YAHFA](https://github.com/PAGalaxyLab/YAHFA) / [ganyao114/SandHook](https://github.com/ganyao114/SandHook) — ART hook 框架，自己改 method entrypoint 也能做 smali trace

这一步建议熟读各类工具源码，会有很深的体会；

### 5. 系统框架层 trace（binder / framework）

另一个常被忽略的视角是 **binder trace**，这部分高可用的工具也少。Android 应用与系统服务（`SystemServer` / `mediaserver` / `surfaceflinger` 等）的所有 IPC 都走 binder，位置 / 传感器 / 设备 ID / 通讯录 / 短信 / 包管理 / 网络状态 …… 这些数据无一例外都要跨进程拿。在 Java 函数 trace 看到的 `TelephonyManager.getDeviceId()` 之类，在系统框架层就是一次 `IPCThreadState::transact`，能抓到完整的 Parcel 序列化数据。

这一层 trace 的核心价值在于：

- **补全 Java/native 之外的维度**：app 内代码可以混淆，但跨进程调用必须走 AIDL，binder code + interface descriptor 公开可读
- **风控指纹采集还原**：很多设备指纹 SDK 自己不直接 IO，而是通过 binder 问系统服务，hook binder 一把全抓
- **绕过 native 反 hook**：壳通常只防 `libxxx.so` 内部被 hook，对 binder 这种系统层接口防御稀疏
- **协议级证据链**：抓到 binder transaction 之后能直接对照 AIDL 接口反推业务语义

常见工具：

- [foundryzero/binder-trace](https://github.com/foundryzero/binder-trace) — frida + Python 实现，号称 "Wireshark for Binder"，自带 GUI 解析 Parcel
- [0bbedCode/DroidBinderTrace](https://github.com/0bbedCode/DroidBinderTrace) — frida 脚本，专门 trace binder transaction
- [ggggmllll/AndProxyDemo](https://github.com/ggggmllll/AndProxyDemo) — GOT hook `libbinder.so` 的 `ioctl`，自动解析 `BR_/BC_TRANSACTION` 提取 service / method 名，支持 Java 回调改写 Parcel；额外还基于 seccomp user-notify 做 syscall 拦截（kernel ≥ 5.10）
- [ac-pm/Inspeckage](https://github.com/ac-pm/Inspeckage) — Xposed 模块，集成大量 Android API hook（文件 / 网络 / 加解密 / SharedPreferences 等），可用来旁路确认上层调用
- 自己写：hook `IPCThreadState::transact`，按 `code` + `descriptor` 分流

实战里 binder trace 经常和 Java/native trace 配合着看：先在 Java 层 frida-trace 找到可疑调用 → 在 binder 层确认到底走的哪个系统服务接口 → 必要时下到 native 层抓 Parcel 详细字段。

### 6. Native 静态分析

如果 Java 函数最终调进 native（JNI 桥），SO 在 `lib/arm64-v8a/` 下。拿出来反编译：

- [IDA Pro](https://hex-rays.com/) — 行业标杆，F5 出伪 C，IDC / Python 脚本生态最全
- [BinaryNinja](https://binary.ninja/) — 现代 UI、HLIL 中间层比 IDA 友好、API 设计漂亮、Sidekick 自带 ai
- [Ghidra](https://ghidra-sre.org/) — 免费、NSA 出品，反编译质量接近 IDA，适合白嫖
- [radare2](https://www.radare.org/) / [dweinstein/r2android](https://github.com/dweinstein/r2android) — 开源命令行
- [Hopper](https://www.hopperapp.com/) — Mac 用户友好

常用插件（拿来辅助识别加解密 / 哈希）：

- [codedanwen/findhash](https://gitee.com/codedanwen/findhash)（gitee）— 比 findcrypt 更准的加解密 / 哈希常量识别，能直接生成 frida hook 脚本

由于反编译工具编写难度很大，所以推荐闭源的IDA/Ninja；

接下来说说Java层发现native函数之后，去定位 native 函数的几种情况：

1. **静态注册**：函数名直接是 `Java_com_foo_XxxUtils_sign`，IDA 里搜函数名秒定位
2. **动态注册（弱混淆）**：直接在 SO 里搜常量字符串、看 `RegisterNatives` 调用点找映射表
3. **动态注册（强混淆）**：常见于带壳 / VMP 的 SO，需要在 spawn 时 hook `RegisterNatives`，拿运行期的 `JNINativeMethod` 数组
4. **更底层**：有的 app 很恶心，直接通过 ArtMethod 偷偷绑定；这种就得 attach 之后 hook 关键 native 函数，拿到 `ArtMethod` 结构体取 native entrypoint，计算偏移

定位完对函数做静态分析。混淆轻的伪 C 看个大概就能猜个八九不离十；混淆重的、或与 JNI 桥交互复杂的，就得上动态工具辅助理解了。

### 7. Native 函数 trace（inline hook / interceptor）

定位到 native 函数的真实地址之后，hook 拿入参出参；如果函数本身比较复杂，还可以对函数内的关键调用点（子函数、libc 调用、JNI 调用）做 hook 辅助观测（调试方案下面单独讲）。主流工具：

- [Frida](https://frida.re/) `Interceptor.attach` — 跨平台、稳定、可读改寄存器；[frida-trace](https://frida.re/docs/frida-trace/) 是它的 cli 封装，`-i 'libfoo.so!sign'` 一行批量监控
- [bytedance/android-inline-hook (ShadowHook)](https://github.com/bytedance/android-inline-hook) — 字节出品的 inline hook，性能 / 稳定性都不错
- [iqiyi/xhook](https://github.com/iqiyi/xhook) — PLT/GOT hook，适合 hook libc / 系统库
- [jmpews/Dobby](https://github.com/jmpews/Dobby) — 老牌跨平台 inline hook
- [Rprop/And64InlineHook](https://github.com/Rprop/And64InlineHook) — 老牌 arm64 inline hook，代码很短适合学习
- [bytedance/bhook](https://github.com/bytedance/bhook) — 字节家的 PLT hook，做的相对完善

### 8. JNI trace（native 反过来调 Java）

绝大多数 Java → native 的关键函数（指纹采集、风控上报、加解密）都会再通过 JNI 桥反过来调用一堆 Java 方法去拿设备信息（IMEI / IDFA / sensor / SharedPreferences / SystemProperties），追这一层能极快地理解 native 函数的语义：

- [chame1eon/jnitrace](https://github.com/chame1eon/jnitrace) — frida 脚本，输出每次 `JNIEnv->` 调用 + 参数解析，最常用；还有Tid啥的
- [chame1eon/jnitrace-engine](https://github.com/chame1eon/jnitrace-engine) — jnitrace 的引擎库版，方便嵌到自己的 frida 脚本里二次开发
- [Areizen/JNI-Frida-Hook](https://github.com/Areizen/JNI-Frida-Hook) — 解析 SO 里所有 JNI 函数原型后自动生成对应的 frida hook 脚本
- [lasting-yang/frida_hook_libart](https://github.com/lasting-yang/frida_hook_libart) — `hook_art.js` / `hook_RegisterNatives.js` / `hook_artmethod.js` 三件套，从 ART 这一层兜底抓 JNI 调用
- [lasting-yang/frida_dump](https://github.com/lasting-yang/frida_dump) — 各家自己改的版本，覆盖度看个人
- 自己写hook：hook `JNINativeInterface` 函数表里的 `CallObjectMethod` / `GetStringUTFChars` / `FindClass` 等
- **unidbg 补环境**：补的过程本身就是把每次 JNI 调用都暴露给你，是非常好的理解 JNI 调用链的途径

这一层非常香，很多看起来"全 native 实现"的算法其实只是个胶水，真正干活的是它通过 JNI 反调的 Java 函数。比如很多 app 的设备指纹，逆向半天发现核心逻辑大部分就是 JNI 反调拿到一堆设备指纹，然后 RSA 加密上报获得 token。

>
> 但是俺用jnitrace经常崩溃，我又懒得去改源码，所以就直接在后面的trace中实现这个功能就好了；
>
>
>

### 9. Native 调试（gdb / lldb / IDA 远程）

伪 C 混淆太重 / 直接看 ARM 汇编时，光静态读寄存器猜不出来，hook 拿入参出参也只能看到边界，这时候就需要调试手法在任意位置看寄存器 / 内存：

- [LLDB](https://lldb.llvm.org/) + `lldb-server` push 到设备 — 官方推荐
- [GDB](https://www.gnu.org/software/gdb/) + `gdbserver` — 老牌，命令熟悉的话很快
- [IDA Remote Debug](https://hex-rays.com/products/ida/support/idadoc/1463.shtml) + `android_server` — IDA 内单步看寄存器，体验最好
- [frida/frida (Frida-debugger)](https://github.com/frida/frida) + 各种 GUI 封装
- 硬件断点方案

调试的好处：可以下断点、看任意时刻寄存器 / 内存。坏处：

- 交互式、节奏慢
- 不稳定，主要是被检测烂了
- 不适合 AI 辅助分析（每一步都要人盯着）
- 多线程 / 异步代码下断点容易踩空

所以本人不太推荐。能不调试就不调试，把状态全 dump 出来离线分析，在大部分场景下往往更高效 —— 这就是下一节的指令级 trace。

### 10. 指令级 trace

调试不稳定、hook 粒度又太浅怎么办？把底层执行的汇编全部记录下来，顺便把汇编涉及到的所有副作用 —— 每一次寄存器变化、每一次内存读写、每一次文件访问、每一次系统调用都"录"下来，事后离线分析。这就是指令级 trace。

实现思路本质上都是**插桩**：在原汇编里塞回调，每条指令执行前后采集状态。按载体可以分两类：

**模拟器路线（不依赖真机）**：

封装比较好的基本上只有 unidbg 一家：

- [zhkl0228/unidbg](https://github.com/zhkl0228/unidbg) — Unicorn 内核 + Android 环境模拟，国内最流行，网上文章也最多
	- 优点：隔离性好、单进程跑得稳、想 trace 哪段就 trace 哪段
	- 缺点：补环境累、trace 速度极慢、多线程实现不完整且 trace 顺序乱、v 寄存器无法打印、内存读写没 hexdump
- 本人魔改的 [LunFengChen/unidbg](https://github.com/LunFengChen/unidbg) — 极致 trace 速度优化（opcode L1/L2 cache）、内存读写 hexdump、libc / JNI 语义解析、sub 函数解析

**真机插桩路线（依赖真机）**：

按内核 / 原理大致这几条路：

- [lidongyooo/GumTrace](https://github.com/lidongyooo/GumTrace) — 内核是 [frida-gum](https://github.com/frida/frida-gum)（frida 的 C 内核库，`Interceptor` / `Stalker` / `Memory` 这些 JS API 背后都是它，可以脱离 frida-server 单独嵌进 SO 里用）：用 gum 里负责指令级 trace 的 Stalker 那组 API 把目标 basic block 整段拷到一块新内存里，逐条复制时塞回调，再让线程去执行这份副本（dynamic recompilation）。精度高，gum 本身偏重；trace 文件适合喂 ai；GitHub 上有配套 GUI 工具，附辅助分析功能
- [zgy0x01/QTrace](https://github.com/zgy0x01/QTrace) — 内核是 [QBDI](https://qbdi.quarkslab.com/)：hook 拦截入口后把控制流丢给 QBDI VM 解释执行，逐条 dispatch。Quarkslab 出品的 DBI 框架，对入口要求高，但精度和可控性都好
- [bmax121/sktrace](https://github.com/bmax121/sktrace) — 内核同样是 frida-gum 的 Stalker，但回调写在 frida JS 里：每条指令转写时都要从 native 跨进 V8 调一次 JS callout 来打印寄存器 / 内存，跨语言开销吃满，速度比 GumTrace（回调直接写在 native 里）慢一个量级。APatch 作者出品，思路简单 + 类 IDA 单步、胜在轻；作者 roadmap 里也把"rewrite in C"列着，说明这个性能问题作者自己也清楚
- [GitKittys/AndroidPrybar](https://github.com/GitKittys/AndroidPrybar)（无看雪文章）— Unicorn 内核，魔改 Unicorn 模拟执行；代码似乎打算后续开源
- 自写 DBI — 部分逆向群里偶尔分享原理，未开源；跟其他 DBI 工具差不多，要做好需要解决很多稳定性问题
- 硬件断点 trace — 内核是 DR 寄存器 / WATCHPOINT 触发回调；上限低（断点数限）、精度受 ARM 实现影响；适合小段精确插桩，不适合全量 trace

上面提到的 GumTrace / QTrace / sktrace / AndroidPrybar，以及那些没列名字、靠零散代码片段把原理铺出来的所有真机 trace 项目都值得致敬，感谢你们的分享！

## 个人对现有 真机 trace 的看法

- **稳定性问题**：如qtrace经常崩溃的一个问题就是 QBDI的 guest 虚拟栈设置太小，遇到深递归 / 大栈帧函数直接段错误
- **缺少内存读写数据展示**：纯指令日志看寄存器跳变猜不出实际内存内容，每条指令加 mem callback 又拖慢 trace，因此他们也都不开启内存监控
- **速度跟不上大样本**：Shopee / 字节系动辄上亿指令，中等强度 SDK 签名算法 trace 一次 40+ 分钟，重度指纹 / 文件访问样本要几小时
- **匿名段 / 子线程覆盖不全**：自定义 linker带来的mmap分配内存写入指令然后执行，这部分代码没有trace、创建的线程没有跟踪
- v寄存器值丢失

以上问题都是我在实战场景中遇到的，可能因为我懒吧不想思考方案，我就想全量trace，且包含完整内存修改内容；还有像是自定义linker的案例，现在在很多业务代码，如国内知名小说app：菠萝包轻小说 的签名算法在比较新的版本中都出现了（这里埋一个坑，算法还原已经在 [星球](https://t.zsxq.com/N8xEH) 发过了，我还用unidbg补了这种linker的案例，有人感兴趣可以评论我会考虑写文章分享一下思路和代码）；

为啥我决定自己再写一个真机trace？因为我在做自己的时间旅行调试器（TTD）工具，除了 unidbg 这条线之外还需要一个真机 trace 后端把指令流喂给 TTD 渲染。最开始参考了看雪上的 [QBDI 原理详解](https://bbs.kanxue.com/thread-289884.htm) 和 [QTrace 介绍文章](https://bbs.kanxue.com/thread-290574.htm) + [zgy0x01/QTrace 源码](https://github.com/zgy0x01/QTrace)，先在 QTrace 上魔改了一天多，但是感觉扩展性比较差而我又有二进制trace需求于是放弃；等我把 QBDI 工作原理彻底吃透之后，干脆从头自己撸了一遍 —— 这就是 **xfQTrace**。gumtrace还没有阅读过源码，因为有些朋友跟我说qbdi速度更快，所以就先去改了qbdi的。如果后续有场景需要gumtrace，那我也可能会考虑再适配一手；

## 我的 真机trace工具 优化点分享

我做的工具核心一直是给人类辅助分析使用的，AI 只算附加项，所以会在 trace 中加上大量额外的方便人类阅读的信息。下面说一下 xfQTrace 在主流真机 trace 工具基础上做的核心改进。

### 1. 人类分析友好的 trace 输出格式

xfQTrace 的输出格式从一开始就是按"逆向工程师怎么读"设计的，每一条指令都自带上下文，不用反复回滚对照。下面用一个真实子线程 trace 片段举例。

#### 1.1 指令行：模块偏移 + PRE/POST 状态一行搞定

格式依旧和unidbg的差不多，这样迁移压力会小一点；

```python
[libxftest.so 0x220d4] 0x774524b0d4: "sub sp, sp, #0x1e0" ; sp=0xb400007751928f80  => sp=0xb400007751928da0
[libxftest.so 0x220d8] 0x774524b0d8: "stp x29, x30, [sp, #0x1c0]" ; x29=0xb400007751929000 x30=0x2a sp=0xb400007751928da0
\```

- `[libxftest.so 0x220d4]`：**模块名 + RVA**，跟 IDA / Ghidra / BinaryNinja 里看到的偏移完全一致，trace 里看到一行直接 `g 0x220d4` 就能跳过去；基地址会保留在文件名的，所以也不会丢失这一信息；
- `0x774524b0d4`：运行时绝对地址，需要对 `/proc/self/maps` 时直接用
- 反汇编原文（capstone 渲染，操作数已替换为符号常量如 `AT_FDCWD`）
- `;` 之后是 **PRE 状态** —— 这条指令读取的寄存器值
- `=>` 之后是 **POST 状态** —— 这条指令写出去的寄存器值

一行同时拿到"输入 + 输出"，不用上下翻 trace 自己脑补寄存器变化。这个的实现方案就是上面提到的"单回调延迟输出"：第 N 条指令的 PRE 回调里同时把 N-1 条的 POST 也吐出来。

#### 1.2 内存读/写：hex + ASCII + decode 三件套

这一点是我觉得给人阅读必不可少的；

```python
(w 8) 0xb400007751928f60  00 90 92 51 77 00 00 b4                           |...Qw...        | [0xb400007751929000]
(r 8) 0x7705331028        c5 27 e0 25 f3 c5 cd ba                           |.'.%....        | [0xbacdc5f325e027c5]
(r 1) 0xb400007707b36e9c  73                                                |s               | [0x0000000000000073]
\```

- `(w 8)` / `(r 8)`：**方向 + 字节宽度**（1/2/4/8 自动识别） 这个好处是只查看关键地址的读写内容
- 目标地址：可以利用地址直接搜索
- **原始 hex dump**（保留字节顺序，方便分析序列化数据）
- **ASCII 视图**（`|...Qw...|` 这种）—— trace 里 grep 字符串特征时直接能看到
- `[ 0x... ]`：大端值，这样你搜的时候大小端都能随便搜到了，算作010使用的时候一个小痛点，我直接也输出一份大端的就解决了，不需要去让搜索工具支持什么大端搜索什么的

很多 trace 工具只输出地址 + 值，没有 hex 视图和 ASCII，人类分析的时候就丢失了根据值直接搜索定位的方法了，xfQTrace 的格式让你**直接在 trace 里用 grep 搜字符串/小端字节/大端字节/真实写入地址 **就能定位到关键位置。

#### 1.3 函数调用 banner：call ↔ ret 配对，自动 cstr 解析

跨模块 / 跨函数跳转时输出独立 banner，参数按 ABI 顺序展开（默认 x0~x7）：

这个的好处是，你跟到类似x0这种参数，发现签名有个函数call的banner的时候你就可以在ida中快速找到对应函数，然后跳转进行分析；

```python
=============== -> call: libxftest.so::sub_0x3fb30(x0=0xb400007707b36e88, x1=0xffffffffffffffff, x2=0x0, ...) ===============
...
=============== <- libxftest.so::sub_0x3fb30() ret: 0x16 ===============
\```

语义 Provider 命中时，`sub_0xXXXX` 直接被替换成符号化签名 + 参数命名 + 类型解析：

```python
=============== -> call: libc.so::open(path="/data/local/tmp/qtrace_t28514.tmp", flags=0x242, mode=0x1a4) ===============
=============== <- libc.so::open(...) ret: -1 ===============
=============== -> call: libc.so::clock_gettime(clk_id=1, tp=0xb400007751928ed0) ===============
=============== <- libc.so::clock_gettime(...) ret: 0x0 (0) ===============
=============== -> call: libc.so::getuid() ===============
=============== <- libc.so::getuid() ret: 10265 ===============
\```

cstr 自动读字符串、句柄类参数（fd / 文件路径）符号化、返回值负数自动 errno 化。trace 里一眼就能看到"哦这里调了 open 但是 -1，去看下 flags 0x242 是啥"。

#### 1.4 SVC banner：绕 libc 直走 syscall 也戳穿

很多反 hook / 反检测 SDK 故意绕开 libc，直接 `svc #0` 触发 syscall。xfQTrace 的 QBDI VM 检测到 `svc #0` 时输出独立 banner，覆盖 NR 0~291 主流arm64 syscall 全部命名：

```python
=============== -> svc::openat(dfd=AT_FDCWD, filename="/proc/self/maps", flags=0x0, mode=0x0) ===============
=============== <- svc::openat => 0x5 ===============
\```

参数按 syscall 签名格式化（`fd` / `cstr` / `size` / `int` 等），返回值负数自动按 errno 显示。

#### 1.5 子线程启动 banner + .meta 父子关系

主线程 trace 中 `pthread_create` 被拦截后，子线程 trace 文件第一行是启动 banner：（这里后续会支持利用clone系统调用创建的线程还有通过jni反射调用java创建的线程）

```python
[THREAD_START #1] tid=28514 entry=0x220d4 fork_insn_index=36232369
\```

`fork_insn_index` 标记父线程在第几条指令处 fork —— **跟主 trace 完美对齐**，方便分析父子时序。

同目录下还有 `.meta` 文件记录关系：

```python
parent_tid=28447
child_tid=28514
start_routine=0x774524b0d4
fork_insn_index=36232379
completed=1
\```

py 解析器读这个文件渲染线程树，多线程指纹/加密场景一图看清父子调用关系。

#### 1.6 trace 整体流程示例

把上面几样组合起来，一段真实 trace 大概长这样（节选自 libxftest 子线程）：

```python
[THREAD_START #1] tid=28514 entry=0x220d4 fork_insn_index=36232369
[libxftest.so 0x220d4] 0x774524b0d4: "sub sp, sp, #0x1e0" ; sp=0xb400007751928f80  => sp=0xb400007751928da0
[libxftest.so 0x220d8] 0x774524b0d8: "stp x29, x30, [sp, #0x1c0]" ; x29=0xb400007751929000 x30=0x2a sp=0xb400007751928da0
(w 8) 0xb400007751928f60  00 90 92 51 77 00 00 b4                           |...Qw...        | [0xb400007751929000]
(w 8) 0xb400007751928f68  2a 00 00 00 00 00 00 00                           |*.......        | [0x000000000000002a]
...
=============== -> call: libxftest.so::sub_0x40230(x0=0xb400007751928f18, x1=0x242, x2=0x1a4, ...) ===============
[libxftest.so 0x222e8] 0x774524b2e8: "bl #0x1df48" ; sp=0xb400007751928da0  => lr=0x774524b2ec
[libxftest.so 0x40230] 0x7745269230: "adrp x16, #28672" => x16=0x7745270000

=============== -> call: libc.so::open(path="/data/local/tmp/qtrace_t28514.tmp", flags=0x242, mode=0x1a4) ===============
[libxftest.so 0x4023c] 0x774526923c: "br x17" ; x17=0x7a672dae7c
=============== <- libc.so::open(path="/data/local/tmp/qtrace_t28514.tmp", flags=0x242, mode=0x1a4) ret: -1 ===============

=============== <- libxftest.so::sub_0x40230() ret: 0xffffffff ===============
\```

**指令级 trace + 函数 banner + 内存 r/w + libc/syscall 语义**全部在同一份 trace 里按时序穿插。逆向时基本不再需要在 IDA 和 trace 之间反复横跳。

### 2. 极致速度：3-8 GB/min IO + 90% icache 命中率

**单回调延迟输出**：传统方案每条指令需要 PRE + POST 两次 QBDI 回调。xfQTrace 只注册 PREINST 一个回调，第 N 条指令的 PRE 里同时输出第 N-1 条的 POST（此时 N-1 已执行完，寄存器变化可读）。**QBDI 上下文切换开销直接砍半**。这一点跟unidbg学的，不得不说unidbg真的是很好的一个工具；

**Opcode-keyed 指令缓存**：ARM64 指令固定 4 字节，opcode 严格决定反汇编、操作数、分支属性。用 opcode 做 key 全局复用 —— 4M 槽位直接映射，命中时跳过 QBDI `getInstAnalysis(OPERANDS)` + capstone 反汇编。**实测命中率：短函数 67%，循环密集 90%+**。这一点是我自己魔改的unidbg中 提出的方案，实测效果很好；

**双缓冲异步日志**：

```python
Trace 线程 → buf[active] → swap → IO 线程 write(fd, buf[standby])
\```

128MB × 2 = 256MB 总内存（mmap 分配），trace 线程永不阻塞 IO（除非两个 buffer 都满）。

最终部分实测效果如下（设备pixel5，可以说非常垃圾了）：

- appsflyer 广告 SDK 的 af-sdk-signature 签名函数：6GB/min；
- soul数美w1函数：吞吐 4.6 GB/min
- 淘宝系App如大麦的指纹函数： 3.4 GB/min

有个8GB的样本忘记了，好像是xhs来着？

### 3. 极致压缩率 90% ：LZ4 实时压缩

trace 写盘的同时进行 LZ4 frame 压缩：

- 压缩在 flush 线程中执行，trace 线程**零阻塞**
- 典型压缩率平均 90%（文本格式 trace 重复度高）
- 实测（bench 同口径）：2980 MB raw → 272 MB disk（91% 压缩）；开 memory hexdump 时 4527 MB raw → 351 MB disk（92% 压缩）
- LZ4 解压非常快，s 级别就能搞定，比 adb pull 快得多
- 128GB 存储的垃圾手机也能随便 trace 500GB 大型 app（比如淘宝）
- trace 中途被 stop 也没问题，LZ4 frame 正常 close，部分 trace 仍可读

### 4. 子线程独立 trace + 父子关系

trace 期间被调用的 `pthread_create` 会被 `ParseEngine` 拦截，由 `ThreadTraceManager` 接管：

- 子线程独立挂一份 logger，输出独立的 trace 文件
- 同时输出 `.meta` 元信息记录父子线程 tid 关系
- demo 的 py 解析器会渲染成线程树
- 适合**多线程指纹 / 加密**场景（很多反检测会刻意把关键算法塞到子线程里）
- 后续 TTD 可以使用泳道图可视化父子关系

### 5. Anon 段动态发现 + 按需插桩

跨模块跳转或跳到匿名内存（JIT / unpacked dex / 动态生成代码）时，`InstrumentationManager` 触发 throttled (200ms) 模块刷新，把对应 range 加进 QBDI instrumented 集合 —— **不需要预先全量 instrument**，遇到自定义 linker / 内存中解密的 SO / unpacked dex 这种场景特别好用。

### 6. 可扩展的语义 Provider 体系

xfQTrace 把语义解析做成可扩展的 Provider，每一类函数有自己的规则表 + 格式化器，规则注册之后 ParseEngine 在热路径上查表 → ArgFormatter 渲染：

| Provider | 覆盖范围 |
|-|-|
| **JNI** | 全套 `JNIEnv->*` 函数（GetXxxField / CallXxxMethod / NewStringUTF / GetStringUTFChars 等） |
| **Libc** | `malloc` / `memcpy` / `strncpy` / `pthread_*` / `dlopen` / `dlsym` ... |
| **Crypto** | OpenSSL / BoringSSL：`SHA256_Update` / `AES_*` / `EVP_*` / `HMAC_*` |
| **Protobuf** | `WireFormatLite` / 序列化反序列化入口 |
| **STL** | `std::string` / `std::vector` / `std::map` 等容器操作 |
| **Network** | socket / send / recv / SSL_read / SSL_write |
| **Compress** | gzip / zlib / zstd / lz4 (函数级) |
| **Syscall** | NR 0~291（直接走 SVC 的） |

如 QBDI VM 检测到 `svc #0` 时输出独立 banner，包含 syscall 名 + 参数（按 syscall 签名格式化：`fd` / `cstr` / `size` / `int` 等）+ 返回值（负数自动按 errno 显示）。覆盖 NR 0~291，主流 syscall 全部命名：

```python
=============== -> svc::openat(dfd=AT_FDCWD, filename="/proc/self/maps", flags=0x0, mode=0x0) ===============
=============== <- svc::openat => 0x5 ===============
\```

很多反 hook / 反调试 SDK 会绕开 libc 直接走 `svc #0`，这个 banner 把这层伪装直接戳穿。

但是这种其实很多so会被直接编译进入app的so，有的丢失了符号信息，后续有空会考虑**对常见函数字节码进行匹配**，实现 strip 函数名的函数依旧能展示上层语义（比如 strip 过的 BoringSSL 也能识别 `SHA256_Update`）。

### 7. Hook 参数自动格式化

不止 trace 内部，连最外层 hook 入口的参数也自动按类型解析：

```json
"hook_format": {
    "args": "env,obj,jstr,jstr,jstr,jstr,jstr",
    "ret": "jstr",
    "naming_source": 1, "naming_index": 0
}
\```

支持 `env` / `obj` / `jstr` / `jobj` / `int` / `cstr` 等，trace banner 直接在logcat就能看到 Java 层传入的参数，不然你在trace中找输入还怪麻烦的，支持解析java对象，比如jstring就直接展示，map也可以展示内容。这样当你多次trace的时候，能够区分输入输出，不然你都不知道输入输出那trace还有什么意义；哦对了，这个trace文件的首尾也放了，方便使用呢。

### 8. 极简 JSON 配置 API

整个工具对外只暴露 6 个函数，所有配置项通过 `xfqtrace_configure(json)` 一次性下发，用户不再需要 dlsym 一堆导出函数进行深度配置，写法固定，trace崩溃的时候方便定位错误点：

```javascript
var qcfg = {
    hook_backend: 1,
    target: { base: mod.base.toString(), offset: 0x20294 },
    output_format: 0,
    compression: { enable: true, level: 0 },
    max_traces: 1,
    hook_format: { args: "env,obj,jstr", ret: "jstr" },
    arg_filter: { idx: 2, value: 10401 }
};
xfqtrace_configure(JSON.stringify(qcfg));
xfqtrace_start();
\```

完整 schema 见下方 JSON 配置 schema。

---

虽然 AI 时代我们可以拿到 trace 日志之后直接 ripgrep 暴力搜索 / 污点分析，但我一直认为**古法逆向的功夫是必须练的**，否则走不远。xfQTrace 在设计每一个 feature 的时候都优先考虑"人怎么读"，AI 友好只是顺带的副产物。

>
> 当然你也可以认为我是在坚守道义。其实我早在 2025 年 8 月就开始用各种反编译 mcp 工具，11 月起也开源了不少逆向相关的 AI 工具，比如抓包工具 [LunFengChen/proxypin-mcp-server](https://github.com/LunFengChen/proxypin-mcp-server)。
>
>
>

---

# 第三部分 · 星球版：xfQTrace 使用说明

## xfQtrace 详细使用说明

下面这部分是给 [星球](https://t.zsxq.com/N8xEH) 内部的朋友看的，如果你感兴趣也可以看看，我都封装好了的（你想用frida的js或者frida的py写法都是可以的）

### frida-python 全自动 trace

```bash
python example_trace/demo_trace.py -p com.mfw.roadbook
\```

自动完成：push SO → frida spawn → 等待 trace 完成 → pull → lz4 解压

常用参数：

| 参数 | 说明 |
|-|-|
| `-p` | 目标包名（必填） |
| `--attach` | 附加到已运行进程（默认 spawn 冷启动） |
| `--no-push` | 跳过 push SO，复用设备上已有的 libxfqtrace.so |
| `--pull-only` | 只拉文件 + 解压，不跑 frida（trace 已经跑完） |
| `--reinstall` | 卸载重装 APK 重置设备指纹（传 APK 路径） |
| `--serial` | 指定 ADB 设备（多设备时） |

### frida-cli 半自动化 trace

懒得起 Python，或者想自己控 spawn / attach 时机的，直接 frida CLI：

```bash
# 1) push SO 到目标 app 私有目录（需 root）
adb push example_trace/libxfqtrace.so /data/local/tmp/
adb shell su -c "cp /data/local/tmp/libxfqtrace.so /data/data/com.mfw.roadbook/files/ && \
                 chown $(adb shell stat -c %u:%g /data/data/com.mfw.roadbook) /data/data/com.mfw.roadbook/files/libxfqtrace.so && \
                 chcon u:object_r:app_data_file:s0 /data/data/com.mfw.roadbook/files/libxfqtrace.so"

# 2) spawn 注入（冷启动场景）
frida -U -f com.mfw.roadbook -l example_trace/demo_trace.js --no-pause

# 或者 attach 已运行进程
frida -U -n com.mfw.roadbook -l example_trace/demo_trace.js
frida -UF -l example_trace/demo_trace.js
frida -U -p $pid -l example_trace/demo_trace.js

# 3) trace 完成后（看到 "trace done" / max_traces 命中），按 q 退出 frida

# 4) 手动 pull + 解压
adb shell su -c "cp /data/data/com.mfw.roadbook/files/trace_logs/*.lz4 /data/local/tmp/"
adb pull /data/local/tmp/ ./trace_logs/
example_trace/lz4.exe -d ./trace_logs/xfqtrace_*.log.lz4
\```

适用场景：

- 调试 demo_trace.js 本身，要看实时 console.log
- 多次微调 JS 配置反复重跑，省掉 push SO 那步
- 没装 Python / frida-tools 不全的环境

### 查看 trace 运行状态（logcat 实时监控）

注入到目标进程的 `libxfqtrace.so` 把所有运行时信息（启动 banner / hook 安装结果 / hook 命中参数 / 文件路径 / 错误原因等）都打到 **logcat**，统一 tag 为 `xfQTrace`。

trace 跑起来之后**强烈建议**另开一个终端实时盯着 logcat —— 大部分配置错误（比如 hook 装不上、arg_filter 不命中、命名后缀没生效）都能从这里第一时间看到。

#### 基本命令

```bash
# 只看 xfQTrace tag（最常用）
adb logcat -s xfQTrace:*

# 启动前清掉缓冲区，只看本次 trace 产生的日志
adb logcat -c && adb logcat -s xfQTrace:*

# 按目标进程 PID 过滤（多进程 app / 子进程注入时尤其有用）
adb logcat -s xfQTrace:* --pid=$(adb shell pidof com.foo)

# 写到文件，trace 完了离线翻
adb logcat -s xfQTrace:* > xfqtrace.log
\```

带颜色、自动按包名跟随的话，推荐 [JakeWharton/pidcat](https://github.com/JakeWharton/pidcat)：

```bash
pidcat -t xfQTrace com.foo
\```

#### 常见的关键日志

按 trace 生命周期顺序，logcat 大致会出现这几类信息：

**1) 注入成功（构造函数自动打的启动 banner）**

```python
I xfQTrace: libxfqtrace injected! waiting for xfqtrace_configure/xfqtrace_start
\```

看到这一段说明 SO 已经被成功 dlopen，注入流程通了。

**2) configure / start 阶段**

```python
I xfQTrace: hook backend set to: frida-gum
I xfQTrace: frida-gum backend initialized
I xfQTrace: qtrace target: lib=libxftest.so base=0x7745229000 offset=0x20294
I xfQTrace: qtrace armed: lib=libxftest.so raw=... offset=0x20294 address=0x77452492 ...
\```

如果 configure 报错（比如 JSON 格式错 / target.base 没设），会看到：

```python
E xfQTrace: xfqtrace_configure: parse failed near ...
E xfQTrace: target base not set
E xfQTrace: hook backend 'frida-gum' failed to install hook at 0x...
\```

**3) hook 命中 / 跳过**

hook 命中时（即 Java/native 层调用了目标函数）：

```python
E xfQTrace: hook args: env=..., this=Lcom/foo/Bar;, arg0="hello", arg1=0x1
E xfQTrace: hook return: "encrypted_xxx"
\```

如果配了 `arg_filter` 但本次调用没命中，trace **不会启动**，logcat 只打一行 skip：

```python
D xfQTrace: hook skip: x2=10086 (want 10401)
\```

`arg_filter.value` 没命中、调试时找不到 trace 文件、就来这里看是不是 cmd 不对。

**4) trace 文件路径**

logger 启动时直接打路径：

```python
I xfQTrace: log path: /data/data/com.foo/files/trace_logs/xfqtrace_libxftest_7745229000_20294.log.lz4 (double-buffer 128MB x2, lz4=1 level=0)
\```

如果配了 `naming_source`（参数/返回值塞文件名），trace 结束后还会再打一行重命名结果：

```python
I xfQTrace: trace file renamed: /data/data/com.foo/files/trace_logs/xfqtrace_libxftest_7745229000_20294_10401.log.lz4
\```

**5) 安全停止**

```python
I xfQTrace: qtrace_stop: hook removed, abort signaled
\```

#### trace 文件本身在哪？

logcat 只是元信息和实时状态，**真正的指令 trace 在落盘文件**。默认输出目录：

```python
/data/data/<目标包名>/files/trace_logs/
├── xfqtrace_<so>_<base>_<offset>[_<naming>].log.lz4   ← 主线程 trace
├── xfqtrace_<so>_<base>_<offset>_t<tid>.log.lz4       ← 子线程 trace（如有）
└── xfqtrace_thread_<tid>.meta                          ← 父子线程关系元信息
\```

`demo_trace.py` 在 trace done 回调里会自动 pull + 解压；手动模式见上一节末尾的 `adb pull` 命令。

### 配置

编辑 `example_trace/demo_trace.js` 顶部：

```javascript
const CONFIG = {
    target_so: "libmfw.so",
    engine_path: "/data/user/0/com.mfw.roadbook/files/libxfqtrace.so",
    qtrace: {
        hook_backend: 1,                      // 0=ShadowHook, 1=frida-gum
        target: { offset: 0x642bc },          // base 由脚本注入运行时模块基址
        output_format: 0,                     // 0=text, 1=binary
        compression: { enable: true, level: 0 },  // 0=fast, 1-12=HC
        max_traces: 1,
        hook_format: { args: "env,obj,jstr", ret: "jstr",
                       naming_source: -1, naming_index: 0 },
        // arg_filter: { idx: 2, value: 10401 },  // 可选
        // memory_trace: false,                    // 可选
    },
};
\```

整个 `qtrace` 对象会 `JSON.stringify` 后通过 `xfqtrace_configure` 一次性下发给 SO，
之后只需调用 `xfqtrace_start()` 即可装载 hook，无需逐个 dlsym 大量 setter。

#### JSON 配置 schema

| 字段 | 类型 | 说明 |
|-|-|-|
| `hook_backend` | int | 0=ShadowHook, 1=frida-gum (默认) |
| `target.lib` | string | 目标 SO 名（与 `target.base` 二选一） |
| `target.base` | string | 目标 SO 基址，支持 "0x..." 或十进制（与 `target.lib` 二选一） |
| `target.offset` | int / "0x..." | 目标函数偏移 |
| `output_format` | int | 0=text(.log) 1=binary(.xfqtrttd, 开发中，⏳ 暂不可用，后续需要搭配俺开发的时间旅行调试器) |
| `memory_trace` | bool | 内存读写追踪开关（用不上可以关掉） |
| `compression.enable` | bool | LZ4 压缩开关，默认开 **这个很有用，如果你认为trace文件大一点不影响的话可以关掉** |
| `compression.level` | int | 0=fast(默认), 1-12=HC 高压缩 |
| `max_traces` | int | 最大 trace 次数, -1=无限 -> 看你想要采集多少次trace |
| `arg_filter.idx` | int | 参数过滤索引（命中才 trace,见后续使用示例） |
| `arg_filter.value` | int / "0x..." | 参数过滤值 |
| `hook_format.args` | string | 参数类型, 逗号分隔, 见[HookArgFormatter](https://bbs.kanxue.com/nativelib/src/main/cpp/util/HookArgFormatter.cpp) |
| `hook_format.ret` | string | 返回值类型 |
| `hook_format.naming_source` | int | 命名来源 (-1=禁用, 0=参数, 1=返回值) |
| `hook_format.naming_index` | int | 当 `naming_source=0` 时取第几个参数当文件名后缀 |

#### `hook_format.args` / `ret` 类型标签

复用 `HookArgFormatter`，逗号分隔，支持以下标签：

| 标签 | 含义 |
|-|-|
| `env` / `_` | 占位（不输出，用于跳过 `JNIEnv*` / `jclass`） |
| `jstr` | JNI String，自动 `GetStringUTFChars`，失败 fallback 到 `toString()` |
| `obj` | JNI 对象，输出 `getClass().getName()` |
| `jobj` / `jmap` | JNI 对象，输出 `toString()`（适合 `Map`/`List`/自定义对象） |
| `jbarr` | `byte[]`，输出 `byte[N]{XX XX XX...}` 前 16 字节 hex |
| `cstr` | C 字符串 (`char*`)，自动读 null-terminated |
| `int` | 32 位整数（带符号） |
| `long` / `hex` / `ptr` | 64 位整数（无符号 hex） |
| `bool` | bool（0=false, 非 0=true） |
| `buf.N` | 内存缓冲区，长度由第 N 个参数（x0~x7）给出，输出前 32 字节 |

#### 实战案例

##### 案例 1：大厂 doCommandNative 模式（重点用 arg_filter）

很多大厂 native 都把入口收敛成一个分发函数（如阿里系的 `doCommandNative`、字节系的 `command`、各种风控 SDK 的 `doExecute`），签名类似：

```java
public native Object doCommandNative(int cmd, Object[] args);
\```

签名相关、设备指纹、加解密等几十种功能全挤在同一个函数里，根据 `cmd` 走不同分支。整体 trace 会：

- 一次跑全所有命令，trace 体积爆炸（动辄数十 GB）
- 不相关分支的内存访问/JNI 调用容易把 QBDI 引到不稳定的代码区域，徒增崩溃风险
- 大量噪声分支淹没你真正想分析的那一条

`arg_filter` 让你只在 `cmd == 你关心的那个值` 时才进入 trace，其他调用直接走原函数，零开销。

```javascript
// 大麦 doCommandNative，只 trace cmd=10401（订单签名相关）
const CONFIG = {
    target_so: "libsgmainso-6.7.250903.so",
    engine_path: "/data/user/0/cn.damai/files/libxfqtrace.so",
    qtrace: {
        hook_backend: 1,
        target: { offset: 0x5b198 },              // doCommandNative
        hook_format: {
            args: "env,obj,int,jobj",             // JNIEnv*, jclass, int cmd, jobjectArray args
            ret:  "jobj",
            naming_source: -1, naming_index: 0,
        },
        arg_filter: { idx: 2, value: 10401 },     // 仅当 x2 == 10401 才 trace
        max_traces: 1,
    },
};
\```

要点：

- `idx` 从 0 开始算，对 ARM64 直接对应 `x0..x7`。JNI 静态方法实际 cmd 在第 3 个参数（`env`/`jclass`/`cmd`/...），所以 `idx: 2`
- 不命中时只在 logcat 打一行 `hook skip: x2=...`，trace 完全不启动
- 多次调用同一个 cmd 只想取第一次：`max_traces: 1`；想全收：去掉或设 `-1`

如下图就是跳过的部分，这对于抓初始化函数感觉也会有用呢！

![ae98bbde1cda10faabd12b590c777c08](https://bbs.kanxue.com/upload/attach/202605/1036990_DN25E34QZR66XE4.png)

##### 案例 2：用 cmd/或者签名结果 当 trace 文件名后缀（naming_source）

同样是 doCommandNative 这种分发函数，如果你想跑一次 trace 多个 cmd 又要分辨清楚每条 trace 是哪个 cmd 触发的，用 `naming_source: 0` + `naming_index` 把某个参数值塞进文件名：

```javascript
qtrace: {
    target: { offset: 0x5b198 },
    hook_format: {
        args: "env,obj,int,jobj",
        ret:  "jobj",
        naming_source: 0,       // 0=从参数取
        naming_index: 2,        // 取 x2 (cmd) 作为后缀
    },
    max_traces: -1,             // 不限次数
    // 不加 arg_filter，所有 cmd 都收
}
\```

输出文件类似 `xfqtrace_libsgmainso_<base>_5b198_10401.log`（基址 + 偏移 + cmd 后缀），方便后续按 cmd 归档。

`naming_source: 1` 则取返回值，常用于 `MessageDigest.digest()` 这种把结果哈希塞进文件名的场景，方便后续按返回值归档区分。

##### 案例 3：buf.N 配合 size 参数读缓冲区

像 `EVP_DigestUpdate(ctx, data, len)` 这种 `(void* buf, size_t len)` 形式：

```javascript
hook_format: {
    args: "ptr,buf.2,long",   // x1 是缓冲区指针，长度由 x2 给出
    ret:  "int",
}
\```

输出会把 `x1` 当成指向 `x2` 字节的 buffer 显示前 32 字节 hex。

##### 案例 4：纯 C 函数（无 JNI）

`env` 标签是用来跳过 `JNIEnv*` 的；纯 C 函数直接按真实参数排：

```javascript
// 比如 SSL_write(SSL* ssl, const void* buf, int num)
hook_format: {
    args: "ptr,buf.2,int",
    ret:  "int",
}
\```

##### 案例 5：用 target.lib 让 SO 自己解析基址

不想在 JS 里 `Process.findModuleByName().base` 取基址再传，可以直接给 SO 名：

```javascript
qtrace: {
    target: { lib: "libsgmainso-6.7.250903.so", offset: 0x5b198 },
    // 不需要 target.base，SO 内部 dlopen + dlsym 解析
}
\```

适合目标 SO 已经加载、且名字稳定的场景。如果是动态 dlopen / 名字带版本号变动，仍建议在 JS 层等 `android_dlopen_ext` 触发后再传 `target.base`（见 demo_trace.js 默认逻辑）。

##### 案例 6：内存 trace 关掉提速

`memory_trace` 默认开。如果只关心控制流和寄存器变化、不关心每条 load/store 的内存读写值，关掉能显著提速并大幅减小 trace 体积：

```javascript
qtrace: { memory_trace: false }
\```

### LZ4 压缩控制

默认开启，可在 JSON 里调整：

```javascript
qtrace: {
    compression: { enable: true, level: 9 },  // 9=HC 推荐
}
\```

解压：`lz4 -d trace.log.lz4 trace.log`

好处：

- 减少落盘体积：手机只有 128GB 存储，照样能存 500GB 的 trace 文件
- 加快 pull：体积小了，传输自然快
- 解压速度极快：几乎是秒级，几百 MB 的文件 1 分钟内就能搞定

#### lz4 工具下载与安装

trace 输出（含子线程的）默认都是 `.log.lz4`，需要 `lz4` CLI 解压才能阅读。各平台安装方式：

| 平台 | 安装命令 / 下载 |
|-|-|
| Windows | 仓库自带 `example_trace/lz4.exe`，直接用即可；或从 [lz4/lz4 releases](https://github.com/lz4/lz4/releases) 下载 `lz4_winXX.zip` 解压加 PATH |
| macOS | `brew install lz4` |
| Ubuntu / Debian | `sudo apt install lz4` |
| Arch | `sudo pacman -S lz4` |
| Fedora / RHEL | `sudo dnf install lz4` |
| 源码编译 | `git clone https://github.com/lz4/lz4 && cd lz4 && make && sudo make install` |

常用命令：

```bash
# 解压
lz4 -d trace.log.lz4 trace.log
lz4 -d trace.log.lz4              # 同名输出 trace.log
lz4 -dc trace.log.lz4 | less      # 不落盘直接看，适合电脑存储吃紧、只想快速检查 trace 内容时使用
lz4 -dc trace.log.lz4 | more      # Windows 上没有 less，用 more

# 解压整个 trace_logs 目录
for f in example_trace/trace_logs/*.lz4; do lz4 -d "$f" "${f%.lz4}"; done

# Windows (PowerShell)
Get-ChildItem .\example_trace\trace_logs\*.lz4 | ForEach-Object {
    .\example_trace\lz4.exe -d $_.FullName ($_.FullName -replace '\.lz4$','')
}
\```

`demo_trace.py` 自动 pull + 解压时按平台从 `example_trace/` 同目录拿固定二进制：Windows=`lz4.exe`、macOS=`lz4-mac`、Linux=`lz4`。仓库自带 Windows 版；其他平台请把上面命令装出来的 `lz4` 拷过去并按对应文件名命名。

### 导出 API

精简到 6 个核心函数，所有配置项通过 `xfqtrace_configure(json)` 下发：

| 函数 | 签名 | 说明 |
|-|-|-|
| `xfqtrace_configure` | `int(const char* json)` | 解析 JSON 配置，0=成功 |
| `xfqtrace_start` | `int(void)` | 安装 hook 等待触发，0=成功 |
| `xfqtrace_stop` | `void(void)` | 安全停止 trace（abort flag + 移除 hook） |
| `xfqtrace_run` | `void(x0..x7)` | 直接 trace 入口（外部 hook 模式） |
| `xfqtrace_set_done_callback` | `void(void(*)())` | trace 完成回调（函数指针，无法 JSON 化） |
| `xfqtrace_get_last_error` | `const char*(void)` | 取最近错误信息 |

标准调用顺序：`configure(json)` → `set_done_callback(cb)` → `start()` → (hook 命中触发 trace) → 回调里收尾 → `stop()`。

#### `xfqtrace_configure(const char* json)`

把 JSON 配置一次性灌进 SO，0=成功，非 0=失败（具体原因调 `xfqtrace_get_last_error`）。

- JSON 字段见上面 JSON 配置 schema
- 可重复调用：覆盖前一次配置（但要在 `start()` 之前，已经装载的 hook 不会自动改）
- 失败常见原因：`null json` / `parse failed` / `target base not set` / 字段类型错

```javascript
var rc = configure(Memory.allocUtf8String(json));
if (rc !== 0) {
    console.log("[-] " + get_error().readCString());  // 看具体原因
    return;
}
\```

#### `xfqtrace_start()`

按当前配置安装 hook，立即返回，等目标函数被调用时才真正进 trace。0=成功。

- 内部根据 `hook_backend` 选 ShadowHook / frida-gum
- 失败常见原因：目标地址非法、hook 后端初始化失败、`configure()` 没先调
- 与 `xfqtrace_run` 互斥：`start()` 是"挂 hook 等触发"，`run()` 是"立刻 trace"

#### `xfqtrace_stop()`

安全停止：置 abort flag → 移除 hook → flush logger → 关 LZ4 frame。无返回值，幂等。

>
> **幂等**：同一操作执行 N 次，效果跟执行 1 次一样。第一次 stop 真干活，后续再调内部检查"已经停过"直接返回，不会 double free / 重复 close / 崩。
> 好处：Frida 端多个清理路径（rpc.stop / 退出 hook / catch 块）不用各自维护"停过没"的状态；done_callback 触发后已经自动停过一次，Python 收到信号再保险调一次也安全。
>
>
>

- trace 进行到一半被 stop：当前 trace 的 LZ4 frame 正常 close，pull 下来照样能解压（部分 trace 可读）
- Frida detach 之前**必须**调一次，否则 hook 残留指向已释放代码，目标进程后续调用会段错误
- demo_trace.js 的 `rpc.exports.stop` 就是干这个用的

#### `xfqtrace_run(x0..x7)`

绕过内部 hook，把寄存器值直接喂给 trace 引擎，立刻开始 trace。

- 适用场景：你想自己用 frida `Interceptor.attach` 抓参数（比如要在 onEnter 里改 arg），然后手动启动 trace
- 一般用不到，`xfqtrace_start` + arg_filter 已经覆盖 99% 场景
- 调用前仍需先 `configure()` 设好 target / hook_format / output 等

#### `xfqtrace_set_done_callback(void(*cb)())`

注册 trace 完成回调，无返回值。传 `NULL` 取消注册。

- 触发时机：`max_traces` 命中上限、或 `xfqtrace_stop()` 完成卸载
- 回调在 trace 引擎线程同步触发，**别在里面做重活**，转个信号出去就行
- Frida 端要把 `NativeCallback` 挂全局变量保 GC，否则野指针崩
- 用法见 [demo_trace.js](https://bbs.kanxue.com/example_trace/demo_trace.js)：`send({type:"trace_done"})` → Python 侧自动拉文件

```javascript
g_done_callback = new NativeCallback(function() {
    send({type: "trace_done"});
}, "void", []);
set_done_cb(g_done_callback);

// 收尾时：先解绑再置空
set_done_cb(ptr(0));
g_done_callback = null;
\```

#### `xfqtrace_get_last_error()`

返回最近一次 API 调用失败的错误描述，C 字符串。成功调用会清空。

- 仅用于 `configure` / `start` 这类返回 int 的 API 失败后取详细原因
- 字符串生命周期：到下次 API 调用为止，需要长期保存请自己 strdup
- 常见值：`"configure: null json"`, `"configure: parse failed"`, `"target base not set"`, `"hook_failed"`

---

# 回复

## 回复 by 东方玻璃 (#2)

*2026-5-28 14:01*

严肃学习

## 回复 by A0tem (#3)

*2026-5-28 14:02*

来支持了

## 回复 by 酒仙桥之虎 (#4)

*2026-5-28 14:13*

资瓷一个

## 回复 by s1nec-1o (#5)

*2026-5-28 14:55*

看看

## 回复 by Zepp7289 (#6)

*2026-5-28 15:03*

tql

## 回复 by xingbing (#7)

*2026-5-28 15:55*

支持

## 回复 by 黑屏 (#8)

*2026-5-28 16:06*

6666

## 回复 by Imxz (#9)

*2026-5-28 17:08*

tql

## 回复 by mb_ykavguun (#10)

*2026-5-28 17:12*

1

## 回复 by sorely (#11)

*2026-5-28 18:26*

666

## 回复 by amwpecel (#12)

*2026-5-28 18:33*

666

## 回复 by Cure. (#13)

*2026-5-28 21:11*

狠狠地严肃学习![image](https://bbs.kanxue.com/view/img/face/030.gif)

## 回复 by 木志本柯 (#14)

*2026-5-28 23:02*

QBDI VM 会被检测到吗？比如目标函数会检查返回地址来检查PC地址是否在自身的模块里。

## 回复 by xianhuimin (#15)

*2026-5-29 00:06*

辛苦了

## 回复 by xianhuimin (#16)

*2026-5-29 00:07*

辛苦了

## 回复 by wx_Huber Barrientos (#17)

*2026-5-29 01:37*

666

## 回复 by jdong (#18)

*2026-5-29 09:31*

6666

## 回复 by huangjw (#19)

*2026-5-29 09:41*

第一眼以为只是简单的trace， 进来看了之后恍然大悟，覆盖的内容还挺多。 666

## 回复 by mb_xjdhrmck (#20)

*2026-5-29 10:14*

nb 大佬
]

## 回复 by YANG、 (#21)

*2026-5-29 11:40*

66666666666666

## 回复 by dob_C (#22)

*2026-5-29 11:50*

感谢分享

## 回复 by 一栋奥特曼 (#23)

*2026-5-29 12:57*

666

## 回复 by mb_lfwgtxdb (#24)

*2026-5-29 13:01*

感谢分享

## 回复 by git_74197luban110 (#25)

*2026-5-29 13:32*

666

## 回复 by didiid (#26)

*2026-5-29 13:45*

感谢分享

## 回复 by didiid (#27)

*2026-5-29 13:49*

写的挺好的，搞技术的少一些像AndroidPrybar作者这样只会吹吹牛和自我感动的人氛围就更好了

## 回复 by mb_4nrpVMxJ (#28)

*2026-5-29 14:01*

666

## 回复 by mb_ysikfhxt (#29)

*2026-5-29 14:37*

111

## 回复 by tonykros (#30)

*2026-5-29 15:45*

666

## 回复 by manyuegong33 (#31)

*2026-5-29 16:04*

111

## 回复 by kingking888 (#32)

*2026-5-29 23:03*

666

## 回复 by 简单的简单 (#33)

*2026-5-30 23:49*

666

## 回复 by buluo533 (#34)

*2026-5-31 09:35*

狠狠地支持

## 回复 by mb_nkjfyhkg (#35)

*2026-5-31 14:05*

mark

## 回复 by B.M.K (#36)

*2026-5-31 19:27*

666

## 回复 by 中文fjja (#37)

*2026-5-31 21:48*

非常感谢

## 回复 by mb_qimctavn (#38)

*2026-6-1 08:39*

6

## 回复 by 肉蚌葱鸡 (#39)

*2026-6-1 10:48*

666

## 回复 by 小黄鸭爱学习 (#40)

*2026-6-1 14:14*

kkp

## 回复 by logeye (#41)

*2026-6-1 15:11*

6666

## 回复 by mb_xwntdpxy (#42)

*2026-6-1 21:00*

666

## 回复 by mb_tciajwop (#43)

*2026-6-2 10:30*

666

## 回复 by mb_farzbkyi (#44)

*2026-6-2 15:24*

666

## 回复 by 小木马 (#45)

*2026-6-2 16:54*

666

## 回复 by XCicada (#46)

*2026-6-2 17:25*

支持

## 回复 by wst2048 (#47)

*2026-6-3 09:44*

感谢分享

## 回复 by niama (#48)

*2026-6-3 10:59*

666

## 回复 by DawnDotVip (#49)

*2026-6-3 11:23*

6666

## 回复 by wx_白鸟之诗 (#50)

*2026-6-3 12:21*

6666

## 回复 by fengvmu (#51)

*2026-6-3 15:56*

感谢分享????

## 回复 by FMNS (#52)

*2026-6-4 11:31*

666

## 回复 by ldehua (#53)

*2026-6-4 18:48*

看看

## 回复 by mb_mwfzoyhc (#54)

*2026-6-5 12:29*

感谢分享

## 回复 by Viseris (#55)

*2026-6-5 15:21*

谢谢分享

## 回复 by git_23936shiling8112 (#56)

*2026-6-6 11:19*

666

## 回复 by git_65517aiqingyi (#57)

*2026-6-7 19:28*

666

## 回复 by myios (#58)

*2026-6-7 20:55*

666

## 回复 by mb_wxvjqniz (#59)

*2026-6-7 22:09*

666

## 回复 by 祝今朝 (#60)

*2026-6-7 23:33*

666

## 回复 by mb_lanapfpb (#61)

*2026-6-9 07:46*

学习交流

## 回复 by iBa0 (#62)

*2026-6-9 18:13*

1233

## 回复 by mb_qsjvnlbt (#63)

*2026-6-10 11:29*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by mb_ifyzpddv (#64)

*2026-6-10 14:29*

666

## 回复 by mb_paopxhtx (#65)

*2026-6-12 18:06*

6666

## 回复 by mb_ckwbzclg (#66)

*2026-6-14 16:19*

感谢分享

## 回复 by mb_etrbkelx (#67)

*2026-6-15 14:16*

666

## 回复 by Snowman_Liam (#68)

*2026-6-15 14:20*

6666

## 回复 by 九黎 (#69)

*2026-6-17 09:08*

tql

## 回复 by sunrise_430526 (#70)

*2026-6-17 09:39*

666

## 回复 by baichisi (#71)

*2026-6-17 10:28*

666

## 回复 by maomaolk (#72)

*2026-6-17 10:51*

666

## 回复 by method (#73)

*2026-6-17 18:13*

1

## 回复 by Zireael (#74)

*2026-6-18 02:32*

tql

## 回复 by @NoBody (#75)

*2026-6-18 10:33*

你好，我实现了一套新的trace方法可以几乎无损跟踪所有堆数据读写和函数调用，核心在于不要用函数进行保存数据，至于如何区分不同线程的数据只需要几条指令就分开保存，我也尝试了一种新的方法，按照传统的或者开源的算法是没法实现这种级别的跟踪的，速度会非常严重干扰程序运行，现在只需要800元就可以出售我的系统源码，我的tel:nobody_ji

## 回复 by @NoBody (#76)

*2026-6-18 10:46*

>
> [@NoBody](https://bbs.kanxue.com/user-1032814.htm)
>  你好，我实现了一套新的trace方法可以几乎无损跟踪所有堆数据读写和函数调用，核心在于不要用函数进行保存数据，至于如何区分不同线程的数据只需要几条指令就分开保存，我也尝试了一种新的方法，按照传统的或者 ...
>

是几乎无损记录程序起始运行分线程所有堆数据读写，程序性能损耗只有50%左右，如果只是记录起始所有函数调用几乎0%的损耗，其他无论你用什么undbg变体或者开源闭源工具效率都低得多，欢迎交流谢谢。

## 回复 by @NoBody (#77)

*2026-6-18 10:47*

>
> [@NoBody](https://bbs.kanxue.com/user-1032814.htm)
>  你好，我实现了一套新的trace方法可以几乎无损跟踪所有堆数据读写和函数调用，核心在于不要用函数进行保存数据，至于如何区分不同线程的数据只需要几条指令就分开保存，我也尝试了一种新的方法，按照传统的或者 ...
>

是几乎无损记录程序起始运行分线程所有堆数据读写，程序性能损耗只有50%左右，如果只是记录起始所有函数调用几乎0%的损耗，其他无论你用什么undbg变体或者开源闭源工具效率都低得多，欢迎交流谢谢。

## 回复 by mb_bysnyvmg (#78)

*2026-6-18 12:11*

666

## 回复 by 夜惜风雨 (#79)

*2026-6-20 01:35*

6666666666666666666

## 回复 by rock123321 (#80)

*2026-6-22 15:36*

1

## 回复 by mb_fgcxqivc (#81)

*2026-6-22 17:06*

点赞

## 回复 by git_45464ntt3005 (#82)

*2026-6-23 20:29*

1111111

## 回复 by dsr000 (#83)

*2026-6-24 14:16*

666

## 回复 by Hacker_0 (#84)

*2026-6-24 14:42*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by shuangmou (#85)

*2026-6-25 10:44*

感谢佬分享

## 回复 by Gryffindoss (#86)

*2026-6-25 22:19*

66666

## 回复 by mb_uzmffdbw (#87)

*2026-6-26 15:39*

666

## 回复 by 熊猫吃鱼 (#88)

*2026-6-26 19:43*

66666

## 回复 by mb_pmnukjhq (#89)

*2026-6-28 16:02*

6666666

## 回复 by mb_osxdmntv (#90)

*2026-6-29 15:57*

6666

## 回复 by SInnon (#91)

*2026-6-30 17:53*

6666666666666666666

## 回复 by wx_L_ (#92)

*2026-7-3 09:53*

666

## 回复 by wx_听书人 (#93)

*2026-7-5 23:12*

666

## 回复 by 独一无二_370133 (#94)

*2026-7-6 10:29*

666

## 回复 by Sigil (#95)

*2026-7-6 15:25*

1

## 回复 by Tao Holmes (#96)

*2026-7-8 11:46*

风佬难道是天才

## 回复 by mb_zpfwznow (#97)

*2026-7-8 15:06*

666

## 回复 by wx_kx92911 (#98)

*2026-7-9 10:04*

感谢分析

## 回复 by mb_wtvdkfmq (#99)

*2026-7-10 13:13*

6666

## 回复 by mb_nulzrwjk (#100)

*2026-7-15 17:21*

6

## 回复 by mb_dwxaumtm (#101)

*2026-7-15 18:13*

11

## 回复 by 西埔 (#102)

*2026-7-16 14:50*

6666

## 回复 by Midsw (#103)

*2026-7-21 02:54*

666666666666

## 回复 by MikotoDev (#104)

*2026-7-22 18:16*

感谢分享

## 回复 by Yuuuual (#105)

*2026-7-23 13:39*

学习记录，感谢分享

## 回复 by xtyuns (#106)

*2026-7-24 18:24*

tql

## 回复 by mb_irhdtnzm (#107)

*2026-7-29 19:20*

恶

## 回复 by BlackMaGou (#108)

*2026-7-31 04:53*

来晚了风佬

## 回复 by mb_syvaqetv (#109)

*2026-7-31 10:56*

学习一下

## 回复 by git_56402Syy040316 (#110)

*2026-7-31 16:03*

1

## 回复 by mb_tawwmfks (#111)

你的帖子非常有用，感谢分享！

## 回复 by mb_btwdlppy (#112)

支持，感谢分享

## 回复 by mb_wzxcpnsa (#113)

66666

## 回复 by lixianhuei (#114)

6666
