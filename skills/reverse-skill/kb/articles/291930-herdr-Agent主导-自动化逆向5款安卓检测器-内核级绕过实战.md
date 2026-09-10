---
title: herdr Agent主导:自动化逆向5款安卓检测器,内核级绕过实战
url: https://bbs.kanxue.com/thread-291930.htm
tid: 291930
author: 秋落
date: '2026-07-09'
tags: [Android安全, 逆向分析, 脱壳反混淆]
crawled_at: '2026-09-10T08:16:46+00:00'
replies: 11
attachments:
- {filename: src_kpm.zip, aid: '399692', path: ../attachments/291930/src_kpm.zip, url: 'https://bbs.kanxue.com/attach-download-399692-572cdae6ea94aac9233cdc56dbfc8b9c@3A0U00ViyWDyWL0CcIDtVw==.htm', size: 37.91kb，95次下载, downloaded: true}
---

# Claude cowork 模式搭配 herdr:Agent 主导、高度自动化逆向 5 款 Android 检测器 APP,并落地内核 KPM / TrickyStore 对抗

>
> 用 Claude Code 的 cowork(多 Agent 团队)模式配合 herdr(经 MCP 操控 IDA/JADX/Frida/unidbg 等交互式工具),以 Agent 为主逆向 5 款 Android 环境 / 可信状态检测器 APP(前四款偏 root/RASP,第五款偏 Key Attestation / TrickyStore 检测),并把对抗落地成内核 KPM 模块(第五款另叠 keystore2 层 TrickyStore fork)。
>
>
> 工作流:主 Agent 只做分配与判断,子 Agent 在 herdr 多窗格里并行干活(idalib 无头反编译 / Frida 动态校验 / unidbg 脱机执行);人主要做授权与纠偏。
>
>
>

![多 Agent 协作模式](https://bbs.kanxue.com/upload/attach/202607/662006_UENKWV64ERA8PW5.png)

部署设备:Pixel 4 (flame) / Android 13 (TP1A.221005.002) / 内核 4.14.276 / APatch(KernelPatch)。
对抗模块:自研 `riskhider.kpm`(APatch KernelPatch Module,arm64)+ 自编 TrickyStoreOSS fork(第五款 keystore2 层,见 第十五节)。
最终状态:前四款(Hunter、ZygiskDetector、Momo(mahoshojo)、Launch)在 Pixel 4 / 内核 4.14 上以 KPM `v1.4.6` 有截图实测(见第十六节);第五款密钥认证(wu.keyChain.test,Pixel 6 Pro / Android 15,KPM + 自编 TrickyStore fork)有 app UI 实测截图(见第十六节),证明证书链 / TEE / bootloader 等展示项通过;rooted/hooked 未单独贴图,按 KPM 设计与无 Frida 运行环境处理(环境层说明见 15.7)。

文章结构:先讲逆向怎么厘清每个检测器的检测点,再讲 KPM 由实测驱动的逐版修复(第五款延伸到 keystore2 层 TrickyStore fork 的源码对抗),最后是收尾配置与踩坑。结论尽量附证据(代码 / dmesg / 反编译 / 运行记录),未触发、未明确、仅字典级之处均标注清楚。

>
> 关于设备差异:各检测器的逆向分析在不同机器上做(例如 Hunter 的动态证据采自 Pixel 6 Pro / Android 15),而 KPM 的部署、对抗实测都在上面的 Pixel 4 / 内核 4.14 上。下文凡涉及"分析基线"与"部署设备"不一致处会注明。
>
>
>

---

**基础概念**

- **syscall(系统调用)**:用户程序请求内核干活的入口,比如开文件 `openat`、读文件 `read`、查文件信息 `stat`。检测和对抗的主战场就在这一层。
- **libc / PLT**:libc 是 C 标准库,平时程序都通过它的函数(如 `openat`)间接发系统调用;PLT 是动态库函数调用的跳转表。市面上的 hook 工具大多守在 libc/PLT 这层拦截。
- **裸 svc / 裸系统调用**:不经过 libc 函数,直接用一条 `SVC #0` 指令陷入内核发起的系统调用。好处是守在 libc 那层的 hook 拦不到它。
- **hook**:在某个函数或调用路径上"截胡",改它的行为或返回值。**inline hook** 是其中一种:直接改写目标函数开头几条指令(叫"函数序言/prologue")成一条跳转(`B`/`BR`),劫持到自己的代码。
- **trampoline(跳板)**:hook 时插入的一小段中转代码,先跳到它、它再跳回去。
- **RVA**:函数在模块文件里的相对地址(偏移)。
- **OLLVM(控制流平坦化)**:一种代码混淆,把正常的 if/循环打散成"一个大循环 + 状态分发器",反编译器经常因此把函数参数个数、流程都看错。asm 里那些 `0x….` 魔数就是它的"状态值"。

**进程 / 内存相关**

- **maps / smaps**:`/proc/<pid>/maps` 列出一个进程的内存映射(哪段内存对应哪个库/文件);`smaps` 是带详细统计(如 `Private_Dirty`)的版本。
- **map_files**:`/proc/<pid>/map_files/`,一组指向各内存映射文件的符号链接;它走 `readlinkat` 读链接、不经过 `read(maps)`,是绕过"清洗 maps 文本"的另一条出口。
- **COW(写时复制)/ Private_Dirty**:多个进程本来共享同一份只读代码内存;一旦有人改写它(比如 inline hook),内核就单独复制一份给改写方,并在 smaps 里把这页记成"私有已改"(`Private_Dirty > 0`)。所以关键库 r-xp 代码页 `Private_Dirty>0` 是 inline patch / COW 的**强可疑信号**——但它本身只说明该页在本进程私有且脏,需结合库名、映射权限与完整性比对确认,不等于必然是恶意 hook。
- **comm / cmdline**:`comm` 是线程名(每个线程可以不一样),`cmdline` 是整个进程的命令行(argv[0],通常是 app 包名)。判断"是不是 app 自己"要用 cmdline,不能用 comm。
- **mounts / mountinfo**:`/proc` 下记录当前挂载情况的文件;root 方案会在这里留下 overlay/tmpfs/`/data/adb` 之类痕迹。
- **st_dev / st_ino / nlink**:`stat` 返回的设备号 / inode 号 / 硬链接数。常用来比对 `/debug_ramdisk` 是不是被单独挂载了(正常机它和根 `/` 同设备号)。
- **statfs / f_type**:查文件系统类型的系统调用,`f_type` 区分 tmpfs / ext4 等。
- **ENOENT**:系统调用返回的"文件不存在"错误码;"路径隐藏"就是用它把文件假装成不存在。

**检测 / 对抗相关**

- **KPM**:KernelPatch Module,跑在内核里的对抗模块,能改写系统调用表,在 syscall 这层"做手脚"。
- **门控(gate)**:一个判断开关,决定某段逻辑要不要执行、或某个结果算不算"脏"。
- **side-channel(侧信道)**:不直接读目标文件,而是通过权限、耗时等"间接现象"反推是否有 root。比如测一段代码的执行耗时,root 框架的拦截会引入额外延迟。
- **attestation(密钥证明)**:由 TEE 硬件签名的设备状态证书(含是否解锁、验证启动状态)。**设备原有硬件密钥产生的那把真实 TEE 签名,软件层伪造不了**;但可在 keystore2 层用一份**有效且未吊销的 keybox** 重签出检测器接受的证书链(即 TrickyStore 的做法)。
- **TrickyStore / keybox**:在 keystore2 服务层**替换/重签** Key Attestation 证书链的注入框架——不是伪造 TEE 那把原始签名,而是拿一份有效 keybox 另签一条检测器接受的链;keybox 即它重签用的证书+私钥盒(须有效未吊销)。第五款还自编了它的 fork。
- **keystore2**:Android 密钥服务(Binder 接口 `IKeystoreService`),attestation 证书链在此生成;检测器可直接截它 generateKey 的 reply Parcel 字节做指纹。
- **cowork / 多 Agent 团队**:Claude Code 的协作模式——主 Agent 拆分任务、多个子 Agent 并行执行,各有独立上下文。
- **herdr**:终端复用器;经 MCP 让 Agent 直接操控多窗格里的交互式工具(gdb/frida/unidbg),发命令 + `capture-pane` 读输出,形成"操作-观察"闭环。
- **零宽字符**:屏幕上不显示、宽度为零的 Unicode 字符(如 U+200B/U+200D);被拿来当 0/1,把敏感字符串"隐写"成肉眼看不见的位串。
- **isolatedProcess / 隔离进程**:以高 uid(90000+)、低权限运行的独立进程;常被检测器用来绕过"只针对 app uid"的门控。
- **unidbg**:在电脑上用模拟器跑手机 native 代码的工具;部分系统调用靠人工建模,和真机有出入,所以它的结果要分清"真机行为"还是"模拟器误差"。
- **证据等级**(全文标注约定):`Confirmed`/`✓闭环` = 静态+动态都对上;`Static`/`△静态` = 只有静态证据、本环境没真跑到;`Dynamic` = 只有运行日志、内部没完全还原;`Inferred`/`推断` = 由上下文推的,还需进一步验证;`字典级` = 只在字符串/调用点字典里查到名字,没做单点验证。

**本文章给 KPM 五个功能起的代号(贯穿全文)**

- **A = 路径隐藏**:对黑名单路径的访问返回 ENOENT(假装文件不存在)。
- **B = exec 阻断**:阻止运行黑名单里的程序。
- **C = /proc 内容清洗**:读 `/proc/.../{maps,smaps,mounts,...}` 时,把含痕迹的行整行删掉或同长度抹掉。
- **D = statfs 伪造**:把 overlay/tmpfs 的文件系统类型改成 ext4。
- **E = su 伪造**:对 `/debug_ramdisk` 的 `stat` 返回和根 `/` 一样的设备号/inode、硬链接数=2(注意是"正常返回伪造值",不是 ENOENT)。

---

## 一、为什么是 KPM,不是 Frida

本文章实证的 Hunter 有个典型特征:它故意发裸 `svc #0` 系统调用绕开 libc/PLT/inline hook(`safe_syscall_via_trampoline`,反编译见 第六节)。用户态 libc/PLT hook 拦不到这条裸 svc 读取路径,而 frida 自身的痕迹(`gum-js-loop`/`gmain` 线程、RWX 页、`re.frida.server`)反而是检测项。

裸 svc 仍要陷入内核。KernelPatch 的 `fp_hook_syscalln` 替换的是内核 `sys_call_table` 条目,所以对 riskhider 已挂的那些 syscall(faccessat/openat/newfstatat/statx/read 等 12 个),无论调用方走 libc 还是裸 svc 都会被拦(未挂的 syscall 号不在此列);而且 KPM 不向目标进程注入用户态线程/代码段,因此不会留下本轮这些检测器命中的 Frida/Xposed 用户态特征(并非"零痕迹",见 第十四节)。这是选 KPM 的根本原因。

代价:Frida 只在分析期用来定性(厘清检测语义),不作长期方案。版本上,Frida 17 起 Java/ObjC bridge 不再默认随 GumJS agent 内置(REPL 与 frida-trace 出于兼容仍内置 bridges,自写 agent 可显式 `import` frida-java-bridge;见官方 Bridges 文档)。实践中 Android 13 / SDK 33 上用 frida-server 16.5.9 更稳,Android 15 / SDK 35 上观察到 `Java` bridge / `Java.perform` 可用性问题。另外分析 Momo 时,空 attach 本身就会扰动受保护进程触发检测,所以 frida 数值只做定性、不当干净基线。

---

## 二、通用检测原理:正常环境 vs root/frida 环境的可观测差异

这些检测器(以及常见的同类 root/RASP 检测器)干的是同一件事:枚举一台"正常未改机"在各观测面上应该长什么样,再看当前设备偏离了多少。它们不是"证明有 root",而是"找与干净基线不一致的点"。每个检测点都能写成一句话:

\```
measure(当前环境) != expected(正常环境) ⇒ 判风险
\```

逆向这几个 app,就是把它们"在比哪些差异点"一条条挖出来。下表按观测面分类,每条给【正常机的值】/【被改机的值】/【哪个 app 这么测】/【底层 syscall】——这张表就是后面 KPM 要逐条抹平、并用来反验分析的目标清单。

| # | 观测面 | 正常机 | root/frida 机 | 谁这么测 | 底层 |
|-|-|-|-|-|-|
| A | root 文件存在性 | su/magisk/ksu/apatch/xposed/`/data/adb/*`/`/data/local/tmp/*` 不存在 | 存在 | Launch `checkSuFiles`(access+faccessat 双实现)、Hunter `checkRiskFile`/`checkRootFromAVCLog`(连 AVC 日志侧信道)、Momo PATH 扫 `%s/su`/`%s/magisk` | faccessat/openat/(logcat) |
| B | 挂载形态 | `/system` 只读 ext4/erofs,无 `/debug_ramdisk`,无 overlay/`/adb/modules` | APatch `/debug_ramdisk` tmpfs、magisk overlay/bind、`/adb/modules` | Hunter `detect_root_mark_in_proc_mounts_maps`(mounts/mountinfo/mountstats/df)、Momo mountinfo `upperdir=`/`/adb/modules/`、Launch `checkSuspiciousMounts`+statfs f_type | read(/proc/*/mounts*)、statfs |
| C | 进程内存映射 | 只有自己的 base.apk/系统库 | 多出注入库(libzygisk/frida-gadget/lsposed)、匿名 rwxp 页、memfd:jit-cache 异常、libart 被拆成小段 | Hunter `getZhenxiMapCheck`/`getZhenxiInfoInjection`、ZygiskDetector 扫**自身** maps/smaps、Launch `checkMemoryHooks`、密钥认证(读 maps 扫 frida/zygisk/lsposed/signkiller 等多项) | read(/proc/self/maps,smaps)、getdents64+readlinkat(map_files) |
| D | 线程名 | 无 `gum-js-loop`/`gmain` | frida 有 | Hunter `getZhenxiInfo5`(逐 tid 读 status) | read(/proc/self/task/*/status) |
| E | 代码段完整性 | `.text` 内存==磁盘,smaps r-xp `Private_Dirty=0` | inline hook 后内存≠磁盘、COW 致 `Private_Dirty>0`、函数序言被改成 `B`/`BR` | Hunter CRC 双链、Launch `checkLibraryIntegrity`/`detectSmapsHook`/`checkFunctionHook` | 内存vs磁盘字节比对、read(/proc/self/smaps) |
| F | stat 设备号/链接数 | `/debug_ramdisk` 与 `/` 同 st_dev、挂载点 nlink=2 | APatch 独立 tmpfs → st_dev 不同、nlink=3 | ZygiskDetector:`su=(stat("/") 与 stat("/debug_ramdisk") 的 (st_dev,st_ino) 不一致)`,同门 `d=stat -c %h`(需 nlink=2);密钥认证同款 `stat` 比 `/` 与 `/debug_ramdisk` 的 st_dev | newfstatat/statx |
| G | 属性/环境 | `verifiedbootstate=green`、`flash.locked=1`、`ro.debuggable=0`、`ro.secure=1`、无 adbd socket | orange/unlocked/1/0、有 `/dev/socket/adbd` | Hunter `getZhenxiInfoH`、Momo sel14/sel19、Launch `getBuildProperty` | 属性区读 / access(/dev/socket/adbd) |
| H | 反调试 | TracerPid=0、PR_GET_DUMPABLE 正常 | 被调试时 TracerPid≠0 | Momo `scan_status_tracerpid`、Launch `checkDebugger` | read(/proc/self/status)/prctl |
| I | 时序侧信道 | 裸 syscall 与 libc 耗时接近 | hook trampoline / APatch·KSU 引入额外延迟,耗时差异超阈值 | Launch `detectTimingAnomaly`(>3.0,迭代 5000)、Hunter `SideChanne`(ratio>1.4 判 APatch、>2.2 判 KSU) | clock_gettime + 计时 |
| J | TEE/硬件 | attestation rootOfTrust `deviceLocked=true`/`verifiedBootState=Verified`(硬件签) | unlocked/Unverified | Hunter TEE 链、密钥认证(Key Attestation `RootOfTrust.deviceLocked`,主力) | KeyStore(binder)→Keymaster |
| K | 框架/包(binder) | PackageManager 查不到管理器包、反射查不到 Xposed 类 | 查到 `me.bmax.apatch` 等、查到注入类 | Launch `checkXposedJava`、Momo sel5(ART JavaVMExt + 栈扫 `XC_MethodHook`) | binder |

把这些差异面归并,无非三类:

1. **文件/挂载/属性差异(A·B·G)**:root 在文件系统与属性上留下的痕迹。
2. **进程内存差异(C·D·E·F·H)**:frida/注入/hook/调试在**自身进程**的内存、线程、stat、status 上留下的痕迹(C/D/E/F/H 全部读 `/proc/self/*`;注入库如 libzygisk 虽源自 zygote,但经 fork 的 COW 出现在 app 自身 maps/map_files 里,读 self 即见,无需读父进程)。
3. **时序/硬件/binder 差异(I·J·K)**:不走文件 / proc syscall,而是暴露在执行耗时(时序侧信道)、TEE 硬件签名的启动状态、binder 查询结果上的痕迹。

第 1、2 类多数最终都依赖文件 / /proc / stat / statfs 这类 syscall 可见面,这是 KPM 能在内核层统一还原、当主力的部分。但第 2 类里有几样 KPM 抹不平,要单独处理:代码段完整性(内存映像 vs 磁盘字节比对,要求被校验库 .text 内存==磁盘)、时序侧信道(基于硬件计时,文件层骗不过)、ART/JNI 内部结构遍历(如 Momo 走 JavaVMExt::VisitRoots,不读 /proc)。第 3 类(属性 / TEE / binder)KPM 更够不着,分别交给 resetprop、TrickyStore、HMA。第五款密钥认证除了 C/F/J 这几条基线差异,还反过来查注入器本身:keybox 诱饵标记、ASN.1 标签序、keystore2 reply Parcel 字节探针专抓 TrickyStore,这类不算"正常 vs 改机"的基线差异,归第四节 keystore2 行与第十五节。下一节按"哪一层差异交给谁治"展开。

---

## 三、各检测器的标志性手法

通用差异面(第二节)落到每个 app,会长出各自的招牌招数,下面每个只挑最有特点的几条。

### Hunter:把检测做成"用户态 hook 够不着"

- 借 linker 的指令发系统调用(`safe_syscall_via_trampoline @ 0x248cc4`):读敏感文件不调用 libc,而是到 linker64 代码里找现成的 `SVC #0`,填好系统调用号跳过去执行。守在 libc/PLT 层的 `openat/read` hook 拦不到;直接改这段跳转又会触发它对这 48 字节的完整性自检。只能下沉到内核 syscall 层。
- 多进程交叉验证 + Binder 回传:Manifest 起 `:hunter_server_iso`(isolatedProcess)和 `:hunter_server_twin`(useAppZygote)两独立进程各跑一遍检测,结果经 `YouAreLoser.TC.onTransact → MainActivity.n0` Binder 回传主进程 UI;主进程 hook 再多,子进程照样命中(KPM 因此要把门控扩到隔离进程 uid 90000)。
- AVC 日志侧信道(`checkRootFromAVCLog`):`logcat -c` → 对敏感路径做 ls/open/access/getxattr/readlink → `logcat | grep 'avc: denied'`。文件即便被 ENOENT 藏掉,只要 kernel 打过一条 AVC denial 就能反推存在。【前提待核实】普通 app 无 `READ_LOGS` 权限时 `logcat` 通常只能读自身 uid 的日志,而 AVC denial 由 logd/内核上下文写入、不归属触发进程 uid,故此路径能否在无特权 app 上真取到 avc 行需实测确认。
- 时序侧信道判 root 种类(`SideChanne @ 0xE43BC`):mmap 一页 RWX 拷入 probe 机器码,测 4 组 timing 比值,`ratio>1.4` 判 APatch/KP、`>2.2` 判 KernelSU(实测 `ratio0:1.604 ratio1:1.658` → APatch)。硬件计时,文件层伪装不掉。
- CRC 自检不读 `/proc/self/maps`:定位模块代码段(r-x 区间)主要遍历 linker 内部的已加载 .so 清单(`dl_iterate_phdr` + `getauxval(AT_PHDR)`),maps 只当备路径,绕开唯一能被 libc-hook 做手脚的环节。

### ZygiskDetector:检测逻辑根本不在代码里

- 逻辑藏在序列化对象流:`assets/MUS.LOVE` 是 EIDE 低代码工具导出的 Java 序列化流(`AC ED 00 05`),顶层 HashMap → `Object[5]` 指令 → 条件是预编译 MVEL2 AST。反编译 Java 字节码看不到,常量还用零宽字符编码(U+200B=0 / U+200D=1)。
- su 不查文件,比 stat 值:`su = (Os.stat("/") 与 Os.stat("/debug_ramdisk") 的 (st_dev, st_ino) 不一致)`,值比较、不比 nlink。正常机两者同设备号,APatch 的 /debug_ramdisk 是独立 tmpfs(33 vs 64773)→ 不等。同门还有 `d = stat -c %h /debug_ramdisk`(挂载点硬链接数,需 =2)。藏文件没用,得让 stat 返回正常 `dev/ino` 且 `nlink=2`。
- 扫的是自身 maps/smaps:`hooked/injected` 读 `/proc/self/maps`、`/proc/self/smaps`,`indexOf` 找 `zygisk/frida/lsposed/signkiller/rwxp/data adb/toybox` 等标记,命中即脏。(`ps -o ppid=` 是 `traced` 的 `ppid1==ppid2` 一致性校验用的,不参与 maps 扫描;Zygisk 痕迹经 fork 的 COW 继承进自身进程,读 self 即得——何况 app(uid 10xxx)读父 zygote(uid 0)的 maps 会被 ptrace 凭据检查 + SELinux 挡成 EACCES,根本读不到。)
- 内核版本 + 反清洗自探针:`supported` 大致是"内核≥5",为 false 时整个 maps 结构块休眠(黄色 "Unsupported Kernel");同时自己 mmap 一个 RWX 页,要求 `/proc/self/maps` 里看得到 rwx,否则 `rwx==-1` 判脏,专治无脑清洗 maps。

### Momo(mahoshojo):只有正常环境才回真数据,检测到就把输出清零

- SIGSYS/seccomp 正向探针:装一个 SIGSYS(31) handler,主动发一个预期被 seccomp 拦下的 syscall(实测记录 `X8=0xAC`,但 0xAC=172=getpid 属 seccomp 白名单、通常不会被 TRAP,该 syscall 号需回二进制复核,见 8.5);handler 真以 signo=31 跑到就置 `g_sigsys_seccomp_probe_seen=1`。`get(16)` 读它,1 才健康,0 反报 "Seccomp 未开启"。盲目清零 selector 会踩这个反向位。
- 返回给清空,不报错:`check([B)V` 是十几个检测函数的汇合点,任一命中就 `memset(buf,0)` 把返回 Java 的字节数组抹零;全干净才回写 `SHA3-256(input ‖ "vvb_rikka" ‖ 设备指纹)`。无异常无提示,上层无法区分自己是否被判脏。
- 走 ART 内部结构查 Xposed:`JavaVMExt::VisitRoots` 把 ART mirror object 转 JNI local ref,遍历线程栈 `memcmp(class, "de.robv.android.xposed.XC_MethodHook", 0x24)`,命中置 `dword_2C690=3`。
- linker 扫描器解析 bionic 内部全局(`0x1D8AC`):不读 maps 文本,直接解 `__dl__ZL6solist`/`somain`/`g_ld_preloads`/`soinfo::get_realpath`,walk soinfo 链表对比 `libriru`。对 frida 极敏感,空 attach 即触发。

### Launch:自带对照组

- 每个检测点双实现:`checkSuFilesNative`(libc `access`)+ `checkSuFilesSyscall`(裸 `syscall(faccessat)`)共享同一份数据,只 hook libc 会让两者不一致,不一致本身就是 hook 信号。
- 三层信任模型:同一项检测在 JAVA、NATIVE(libc)、SYSCALL(裸系统调用)各跑一遍。`getMostTrustworthyResult` 取最可信一层(优先级 SYSCALL > NATIVE > JAVA,任一层报真即判风险);`hasInconsistentResults` 则是三层对不上就当"有 hook"。对抗必须让内核层把 libc 与裸 syscall 还原成同一份结果,只改一层会被一致性检查反咬。
- 时序差分:`detectTimingAnomaly` 比较 libc 与裸 syscall 同一操作的耗时(实测阈值 3.0、迭代 5000 次)判 inline-hook;native 层做 `totalTime/count` 阈值判断,Java 如何构造 totalTime 见 9.10。
- 完整性硬约束:`checkLibraryIntegrity` 内存映像逐字节 vs 磁盘比对;`detectSmapsHook` 查 r-xp 代码段 `Private_Dirty>0`(COW);`checkFunctionHook` 反汇编函数序言看是否被改成 `B/BR`。它实际校验的库的 .text 内改写都会暴露(未列入校验的库不在此列)。

### 密钥认证:把检测钉进 keystore2 服务层,用自埋标记反过来诱捕注入器

- 自有 keybox 诱饵标记,反向诱捕 hook(CheckAtt):导入自带 `Wuying` keybox 再读回查标记。无差别替换证书链的注入器会把标记也换掉而暴露,逼注入必须选择性(放过 app 自己 import 的非 attestation 证书)。
- 检测点下沉到 keystore2 Binder/Parcel 字节(ErrCheck):反射隐藏 AIDL 截 generateKey 的 reply 原始字节,看 attest-key 链异常栈有无 `Parcel.createException`、扫 mod-time 字节签名与授权槽表 sanity。用户态改返回值碰不到这层。
- 查结构不查内容,ASN.1 标签序(`checkTagOrderMisordered`):只看授权列表 tag 是否升序,乱序/重复即判篡改。
- 同第七节载体,把"反注入"做成主业:逻辑同在 `MUS.LOVE`+util.dex,`deviceLocked` 同 TEE 签名;这款逼出 keystore2 服务层的二次开发对抗,实现细节(行号 / OID / 字节签名 / 精确 tag)详第十五节。

---

## 四、对抗侧分层:每一层差异交给谁治

把这些检测器的信号摊开,会发现它们按层清晰分布,而 KPM 只能管 syscall 那一层。这张表是整个工程的地图:

| 层 | 典型信号 | 对抗工具 |
|-|-|-|
| **syscall** | root 文件(su/magisk/apex/xposed)、mounts/mountinfo(overlay/tmpfs/APatch source)、/proc maps·smaps 的 marker 行(整行清洗;`smaps Private_Dirty` 字段的伪造是另一回事,见第9.13节)、statfs f_type、stat dev/ino(`/debug_ramdisk`)、SELinux `*_file_contexts` 的 `su_exec` 标签 | **KPM(riskhider)** |
| **binder / PackageManager** | `getPackageInfo("me.bmax.apatch")` 找 root 管理器包、反射查注入的 LSPosed 类 | LSPosed + HideMyApplist(KPM 碰不到 binder) |
| **properties** | `ro.boot.verifiedbootstate`(orange)、`flash.locked` | resetprop / VBMeta Disguiser |
| **TEE attestation** | KeyStore 证书链的 `rootOfTrust.deviceLocked`/`verifiedBootState`(Keymaster 硬件签) | TrickyStore + 有效 keybox(keystore 服务层重签证书链) |
| **keystore2 服务层** | keystore2 Binder reply Parcel 字节、attest-key 链 generateKey 异常栈、ASN.1 标签序、自有 keybox 诱饵标记(第五款 ErrCheck/CheckAtt) | **自编 TrickyStore fork**:选择性注入 + 标签去重升序 + Parcel 行为忠实(见第十五节) |
| **环境/硬件** | adb_enabled、TEE/StrongBox key attestation(硬件根验签) | 关 USB 调试;强硬件/远端验签 **KPM 不覆盖,需单独评估**,靠文件/proc 清洗解决不了 |

一个反复被验证的原则:对抗要做在环境/系统层,通用治本。长期落地不应依赖 per-app 改检测结果变量,那种做法只能证明 UI/变量层可控,并不能证明环境面已被处理(换台 app、换个检测点就失效)。KPM 的价值正在于在 syscall 这一层做"通用的干净视图",而不是逐个 app 改它算出来的结果。但 syscall 面之外(TEE / keystore2 层)KPM 够不着,第五款的 deviceLocked / 诱饵标记 / 标签序 / Parcel 探针就必须靠 keybox 重签 + 自编 TrickyStore fork 等服务层手段(见本表 TEE / keystore2 行与第十五节)。

---

## 五、逆向方法论

工具组合:IDA(idalib MCP,无头反编译/交叉引用)做静态还原,frida(分析期定性)+ unidbg(脱机跑 native,绕开"空 attach 即扰动"问题)做动态。一个反复出现的纪律:判定标准是"检测算法、命中原因、绕过点三者之间的因果关系",五步证据(JNI 锚定 → 静态还原 → 上报点 LR 对回 → UI 三元组 → bypass 复测)缺一即降级,绝不升格为"已确认"。

一个真实教训:逆向结论要对着二进制反复验,别被早前的标注带跑。本文章分析过程中一度把 Hunter 的 netlink 检测错标在 `sub_DDB9C`;回头实读 libhunter.so 才确认 `0xDDB9C` 其实是 `/proc/mounts`·mountinfo·maps + `df` 扫描(sub_DC230),真正发 `socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE)` + RTM_GETLINK 的是 `sub_E34AC`(用 find-string 定位串再 xrefs_to 验证)。同一份二进制、同一次分析,纯属标注笔误,已据此更正 6.1。

为什么是 cowork + herdr。逆向用的工具全是交互式 REPL(IDA/idalib、frida、unidbg、gdb),起来就不退出,传统上只能人坐那儿一条条敲。herdr MCP 把这层接进了 Agent:`execute-command` 用 rawMode 把命令发进窗格(REPL 不退出,普通模式会一直等到超时),再 `capture-pane` 把输出读回来。"发命令 → 读输出 → 推理 → 下一条"就成了闭环,Agent 从"建议你敲什么"变成自己动手调、自己看结果、自己定位。

主 Agent 只动脑,活全下放。一个 Claude 从 IDA 一路串到 unidbg,既慢、上下文又很快爆掉,所以拆成团队:主 Agent 拆任务、看结果、拍板,子 Agent 各占一个 herdr 窗格分别跑 idalib / frida / unidbg,并行推进。主 Agent 最容易手痒自己下场分析,得按住它当管理层、把活分下去;多窗格能同时跑起来就基本对了。

几条踩出来的经验。开局先看它开的是多窗格还是单窗口:单窗口、要靠鼠标滚轮翻屏的多半降智了,删掉项目记忆重开,直到它肯铺多窗格;中转断流是常态,子 Agent 会突然挂,做好随时重启的准备;unidbg 最吃力,我的做法是先把相关文章喂给主 Agent 消化,再让它指导 unidbg 子 Agent;人只在关键处点 `yes` 纠偏,模型在跑时可以去干别的,但别离太久。

闭环靠"自己逆出来的检测"当预言机。改完 bypass / KPM / TrickyStore fork,不是凭感觉说"应该好了",而是拿前面逆出来的检测逻辑回测、看目标信号翻没翻;密钥认证那三个 fork patch,就是"逆原理 → 改 → 重编 → Frida 复测看翻没翻"一个个钉下来的。

### 五·实录:多 Agent 怎么真正分工

这一节给出多 Agent 在 herdr 里实际跑起来的样子:1 个 herder(主 Agent)+ 3 个常驻子 Agent(`ida` / `frida` / `unidbg`),各占一个 herdr 窗格、各绑一种工具与职责,herder 通过窗格读写投递任务、收回执、做交叉验证。下面按"建队 → 角色绑定 → 并行干活 → herder 收口"四步看它怎么运转。

#### 这套多 Agent 模型的三个要件

1. **拓扑:herder 不下场,只编排。** 四个 Claude 实例跑在同一个 herdr 会话的 2×2 网格里:`herder(w9:p7)` 标着"本会话/只编排",`ida(w9:p8)` / `frida(w9:pB)` / `unidbg(w9:pC)` 是三个 worker。herder 自己不开 IDA、不写 frida 脚本,它的全部工作是拆任务、读三个窗格的输出、把一个 Agent 的结论喂给另一个去验。
2. **信道:窗格读写就是 Agent 间的 RPC。** herder 跟 worker 之间没有共享内存,唯一的通信方式是 herdr 窗格:

	- **投递** = `herdr pane send-text <id> "<文本>"`(把指令写进目标窗格的 REPL 输入框)+ `herdr pane send-keys <id> Enter`(提交);
	- **读回** = `herdr pane read <id> --source recent --lines N`(等价于轮询 `capture-pane`,把 worker 的最新输出抓回 herder 的上下文)。
	一来一回就是一次远程调用:herder 投一段任务、轮询窗格直到 worker 打印出结果、再把结果纳入自己的推理。三个窗格各自是独立的 REPL,起来就不退出,所以 worker 的工具状态(IDA 数据库、frida session、unidbg 镜像)在多轮任务之间一直活着,不用每次重开。
3. **分工:按"工具 + 证据类型"切,不按文件切。** 三个 worker 不是各分几个文件,而是各管逆向证据链上的一环:`ida` 出静态(反编译、枚举检测函数、还原伪码),`frida` 出动态(hook 上报点、抓 backtrace、把 LR 对回 RVA),`unidbg` 出脱机复算(离线跑 JNI、验证命中项与返回值)。同一个检测点,herder 会让 ida 先给静态结论、再让 frida/unidbg 从另一条证据线印证——这正好对应第五节"五步证据缺一即降级"的纪律,只不过把五步拆给了不同 Agent 并行去取。

#### ① 建团队:一条命令铺出 2×2,三个 worker 待命

herder 用一条布局命令把会话切成 2×2 网格,并在三个窗格里各起一个 Claude Code 实例。截图右下角能看到三个 worker 都是 `Opus 4.8 (1M context)`、状态 `idle · claude`,herder 自己在左上标注"只编排";团队骨架就位,但还没绑定职责,herder 此时主动停下等"继续"。

![image](https://bbs.kanxue.com/upload/attach/202607/662006_HEYEMD2EP55WH9X.png)

#### ② 角色绑定:先握手,再派活

这一步 herder 给每个窗格投一段角色绑定指令,内容各不相同:

- → `w9:p8`:"你是 ida 子 Agent,本团队负责 Hunter 静态反编译(检测函数枚举+伪码还原)。现在只做就绪握手:请回复一行『ida ready · 待命』,先不要开始任何分析,等 herder 下发具体目标。"
- → `w9:pB`:"你是 frida 子 Agent,本团队负责动态 trace 风控上报点(hook 采集/上报调用链)……请回复『frida ready · 待命』,先不要 attach 任何进程……"
- → `w9:pC`:"你是 unidbg 子 Agent,本团队负责脱机执行检测逻辑(离线跑 JNI/验证命中项与返回值)……请回复『unidbg ready · 待命』,先不要加载任何 so……"

三个窗格分别回了 `ida ready · 待命` / `frida ready · 待命` / `unidbg ready · 待命`;这一轮只握手、不干活,目的是先把"谁负责哪条证据线"钉死,避免 worker 抢跑、各做各的。herder 这边贴出的"投递 / 读回回执"表(下图左)正是上面信道机制的实例:三行分别对应三个窗格的 `send-text → send-keys Enter` 投递与 `capture-pane` 读回。角色一旦绑定,后面 herder 只需说"ida 去反编译 sub_E34AC""frida 去 hook 上报点",worker 就各就各位。

![image](https://bbs.kanxue.com/upload/attach/202607/662006_6994UYZPX9BRFWW.png)

#### ③ 并行干活:三条证据线同时推进

绑定完成后 herder 把同一个检测器的活拆成三股并行下发,三个窗格各自在自己的 REPL 里干、互不阻塞。下面两张是其中两股的实跑产物:

ida 子 Agent(静态线):反编译 Hunter 的 netlink root 检测 `sub_E34AC`,认出 `socket(AF_NETLINK, SOCK_RAW, NETLINK_ROUTE)` + `RTM_GETLINK` + 命中字符串 `"netlink Find Permission"`,把"它发 netlink 查网卡来判 root"的静态结论交回 herder(对应 6.1 节)。

![ida 子 Agent:sub_E34AC netlink root 检测反编译](https://bbs.kanxue.com/upload/attach/202607/662006_TBKKNZ86V3Z6AGQ.png)

frida 子 Agent(动态线):在真机上定位 native 风险汇聚/上报点 `build_native_ListItemBean_risk @ 0x278658`,抓 backtrace 把每个命中项的 `LR` 对回具体检测函数(如 `getZhenxiInfo3` / `/proc/mounts`)。这一步是 herder 做交叉验证的关键:ida 给的是"这个函数长这样",frida 给的是"运行时这个函数真的被调到、真的把结果报上去了"——两条线对上,herder 才把该检测点从"△静态"升格为"已确认"(对应 6.0.3 与 6.终)。

![image](https://bbs.kanxue.com/upload/attach/202607/662006_CAK7CE9Z9RQ3D5M.png)

#### ④ herder 收口:把三个窗格的产出拼成一份结论

干活之后 herder 综合三个窗格的产出,落成一条带证据等级的结论。两个典型收口:

Momo(ida 静态 + frida 动态两条线对账):还原 `native_get_env_detection_flags @ 0xE564` 的正反双向投毒、以及 `byte_2C6E4` 健康位"必须靠内核真投递 SIGSYS(signo=31)才置 1"这种反直觉逻辑,靠的是两条证据线对齐:`ida` 给出字节级反汇编(健康位安装器 `0x8898`、读取+投毒路由 `0x116D8`,确认命中时不立即 return 而是写进累加器 v7、统一在 `0x835CBED5` 终态汇聚),`frida` 给出运行时的 selector→健康值→毒值→延迟暴露点对照表,实测"把所有 selector 盲目清零反而踩雷"(有的位 1 才健康)。两边对上,herder 才定稿(对应第八节)。这一轮 `unidbg` 窗格是 `blocked`,先去跑了个 Hunter 的离线测试被中止,Momo 这条线没用上它,符合第五节"unidbg 最吃力"的实情。

![image](https://bbs.kanxue.com/upload/attach/202607/662006_G2Q3AWXM6AG9U2E.png)

密钥认证(herder 主动裁掉一个 worker):它读完检测载体后给出结论"检测全在 `util.dex` 纯 Java、无 native 落点,unidbg 不适用",于是这一轮只派 ida(反编译 `ErrCheck` 的 keystore2 Binder/Parcel 双探针)和 frida(写 bypass + trace),unidbg 窗格闲置。该用几个 Agent 由任务性质决定,不是越多越好(对应第十五节)。

![image](https://bbs.kanxue.com/upload/attach/202607/662006_VCCNZZE22Z9WASR.png)

---

## 六、深度逆向(一)Hunter(com.zhenxi.hunter)

>
> **逆向分析基线**:Hunter / `lib/arm64-v8a/libhunter.so` /
> `SHA256 e575daabdeab10b41351286367a77fdb4c0e2ae3aa8d66af7495e046b4a63123` / IDA imagebase `0x0`;
> 分析期测试环境 Pixel 6 Pro / Android 15 (AP4A.241205.013) / SDK 35 / Frida 17.9.7。
>
>
>

本章按检测类别组织,尽量保留原样摘录的代码块(伪代码 / asm / frida trace / `[evidence:*]` 日志 / 命中字符串),字典级 / 未细拆项单独标注。判定沿用前言五步证据门(JNI 锚定 → 静态还原 → 上报点 LR 对回 → UI 来源 → bypass 复测),缺一只能标 `△静态` 或 `字典级`。

---

### 6.0 公共基础设施

#### 6.0.1 JNI 批量注册:绕过 RegisterNatives 监控(检测点#2)

链路(`JNI_OnLoad @ 0x2c36f8`):

\```
HunterPreload (Zygote 预加载)
 ↓ dlopen libhunter.so
JNI_OnLoad @ 0x2c36f8
 ├─ checkProcessTag (byte_2F3A68 & 1) 失败 → abort
 ├─ GetEnv(JNI_VERSION_1_6), NULL → abort
 ├─ HunterJniHelper::init(env)
 ├─ FindClass + 全局缓存 7 个类
 ├─ art_register_natives_batch(env, NativeEngine, off_2EF1F0, 60) ← 直接 patch ArtMethod
 ├─ art_register_natives_batch(env, ChooseUtils, off_2EF1D8, 1)
 ├─ uname.sysname == "Unidbg" → return -1
 ├─ InitProperties
 └─ return 0x10006
\```

不依赖普通 JNI 导出名,通过 ArtMethod 直接 patch 注册;运行时枚举 `off_2EF1F0` 表(每项 `{name*, sig*, fn*}` = 24 字节,共 60 项,完整表见 第6节.终.D)。本文章 SO 层下沉脚本 `hook_native_bypass_so.js` 明确分类并 `Interceptor.replace` 了其中 **25 个 detection 入口**(其余 35 项为 `popen` / `MD5` / 工具方法 / 信息查询 / 未细化分类的 detection)。

`art_register_natives_batch @ 0xA5C54` 静态伪代码:

```c
// libhunter.so+0xA5C54
bool art_register_natives_batch(JNIEnv *env, jclass clazz,
 JNINativeMethod *methods, size_t count) {
 if (get_sdk_level > 33)
 return false; // Android 14+ / SDK 34+ 直接放弃此路径
 for (size_t i = 0; i < count; i++) {
 jmethodID mid = env->GetMethodID(clazz, methods[i].name, methods[i].signature);
 if (!mid) {
 env->ExceptionClear;
 mid = env->GetStaticMethodID(clazz, methods[i].name, methods[i].signature);
 if (!mid) return false;
 }
 void *art_method;
 if (g_sdk_level < 30) {
 art_method = (void *)mid; // mid 即 ArtMethod*
 } else {
 jobject m = env->ToReflectedMethod(clazz, mid, JNI_TRUE);
 art_method = (void *)env->GetLongField(m, g_fid_Executable_artMethod);
 }
 if (!art_method_set_native_entry(g_sdk_level, art_method, methods[i].fnPtr))
 return false;
 }
 return true;
}
\```

`art_method_set_native_entry @ 0xA4C80` 完整伪代码(含 SDK 31-33 BUG 标注):

```c
// libhunter.so+0xA4C80
__int64 art_method_set_native_entry(int sdk_level, void *art_method, void *fnPtr) {
 std::string libart_path;
 build_libart_path(&libart_path); // sub_1AFA80
 const char *sym;
 if (sdk_level > 30) {
 sym = "_ZN3art11ClassLinker14RegisterNativeEPNS_6ThreadEPNS_9ArtMethodEPKv";
 } else {
 sym = "_ZN3art9ArtMethod14RegisterNativeEPKv";
 if (!libart_dlsym(libart_path.c_str, sym))
 sym = "_ZN3art9ArtMethod14RegisterNativeEPKvb"; // Android 7/8 备选
 }
 void *fn = libart_dlsym(libart_path.c_str, sym); // sub_1A82D4 自实现 dlsym
 if (!fn) return 0;
 g_art_RegisterNative_fn = fn; // cache @ off_2EF7C8
 if (sdk_level > 30) {
 void *thread_fp = libart_dlsym(libart_path.c_str,
 "_ZN3art6Thread14CurrentFromGdbEv");
 if (!thread_fp) return 0;
 void *class_linker = get_art_class_linker(sdk_level); // sub_A3CCC
 if (!class_linker) return 0;
 // BUG: X1 应是 ((Thread*(*))thread_fp) 的结果,而不是函数指针本身
 ((void (*)(void *, void *, void *, const void *))fn)
 (class_linker, thread_fp, art_method, fnPtr);
 } else if (sdk_level == 30) {
 ((void (*)(void *, const void *))fn)(art_method, fnPtr);
 } else {
 ((void (*)(void *, const void *, bool))fn)(art_method, fnPtr, true);
 }
 return 1;
}
\```

libart.so 路径按 SDK 选(`build_libart_path / sub_1AFA80`):≤28 `/system/lib64/libart.so`;29 `/apex/com.android.runtime/lib64/libart.so`;≥30 `/apex/com.android.art/lib64/libart.so`。dlsym 目标符号:>30 用 `ClassLinker::RegisterNative(Thread*, ArtMethod*, void const*)`;==30 用 `ArtMethod::RegisterNative(void const*)`;<30 用 `ArtMethod::RegisterNative(void const*, bool)`。

自实现 dlsym `libart_dlsym @ 0x1A82D4`(绕 libdl hook,取 @hide 符号):

```c
// libhunter.so+0x1A82D4
void *libart_dlsym(const char *path, const char *symbol) {
 void *handle = custom_dlopen(path); // sub_1AFF14
 if (!handle) return NULL;
 void *fn = custom_dlsym(handle, symbol); // sub_1B00B8 (.dynsym)
 if (!fn) fn = custom_dlsym_fallback(handle, symbol); // sub_1B0720 (.symtab @hide)
 custom_dlclose(handle); // sub_1B0060
 return fn;
}
\```

Runtime 锚点 `get_art_class_linker @ 0xA3CCC`:dlsym `_ZN3art7Runtime9instance_E`,失败回退 dlsym `_ZN3art17SmallIrtAllocator10DeallocateEPNS_8IrtEntryE`,再按 SDK 偏移读 `Runtime->class_linker_`。缓存:`g_art_class_linker @ qword_2EF7C0`、`g_art_RegisterNative_fn @ off_2EF7C8`、`g_fid_Executable_artMethod @ qword_2EF7D0`。

已确认 BUG:SDK 31-33 路径 `Thread*` 参数错传(详 第6节.终.缺陷 #3)。反汇编 `sub_A4C80`(`0x0a5224..0x0a5254`):

```asm
;; libhunter.so, sub_A4C80 内部
0x0a5224 ADRL X1, aZn3art6thread1 ; "_ZN3art6Thread14CurrentFromGdbEv"
0x0a522c BL sub_1A82D4 ; libart_dlsym(libart_path, "..CurrentFromGdb..")
0x0a5230 MOV X21, X0 ; X21 ← libart_dlsym 返回值 = 函数指针,未调用
0x0a5234 ADD X0, SP, #0x1B0+var_170
0x0a5238 BL std::string::~string ; 析构临时 std::string
0x0a523c CBZ X21, loc_A5278 ; null 检查
0x0a5240 BL sub_A3CCC ; get_art_class_linker;X0 ← class_linker
0x0a5244 CBZ X0, loc_A5624 ; class_linker null 检查
0x0a5248 LDP X2, X3, [SP,#0x1B0+var_188] ; X2 ← art_method,X3 ← fnPtr
0x0a524c MOV X1, X21 ; X1 ← CurrentFromGdb 函数指针(本应是 Thread*)
0x0a5250 LDR X8, [SP,#0x1B0+var_190] ; X8 ← g_art_RegisterNative_fn
0x0a5254 BLR X8 ; ClassLinker::RegisterNative(class_linker,
 ; 函数指针冒充 Thread*, art_method, fnPtr)
\```

`0x0a5230 MOV X21, X0` 后从未 `BLR X21`,直接 `0x0a524c MOV X1, X21` 把函数指针送进 `Thread*` 参数槽。SDK > 33 入口已 `return false` 显式禁用,SDK 31-33 仍进此分支(静态推断);实测设备 SDK=35 走 batch return false 回落 `env->RegisterNatives`,未踩到该分支,31-33 实机的实际崩溃/异常未复现,影响取决于对应版本 ART 实现。

动态枚举 60 项表:

```js
const NATIVE_METHODS_TABLE = 0x2EF1F0, COUNT = 60, ENTRY_SIZE = 24;
for (let i = 0; i < COUNT; i++) {
 const entry = base.add(NATIVE_METHODS_TABLE + i * ENTRY_SIZE);
 const name = entry.readPointer.readCString;
 const sig = entry.add(8).readPointer.readCString;
 const fnPtr = entry.add(16).readPointer;
 console.log(`#${i} ${name} ${sig} rva=${fnPtr.sub(base)}`);
}
\```

实测关键行:

\```
#02 getZhenxiInfo5 (Landroid/content/Context;)Lcom/zhenxi/hunter/bean/ListItemBean; rva=0x2a4760
#13 getZhenxiInfo3 Lcom/zhenxi/hunter/bean/ListItemBean; rva=0x2b476c
#25 getZhenxiLoctionCrc Ljava/util/HashMap; rva=0x2ae064
#45 getZhenxiMapCheck Lcom/zhenxi/hunter/bean/ListItemBean; rva=0x291858
#53 CheckVpn Lcom/zhenxi/hunter/bean/ListItemBean; rva=0x2aaf44
#59 SideChanne Ljava/lang/String; rva=0x2b3bd4
\```

`getZhenxiInfoH` 不在 60 项表内:它是 Java wrapper `getZhenxiInfoH(key) -> getPropInline(key, true)`,后者进 native `getZhenxiInfoZ(key)` fallback 或 `/dev/__properties__` 解析。bypass 25 入口实测:

\```
[null] getZhenxiInfo3 rva=0x2b476c
... (共 25 行)
[null] checkZygisk rva=0x2a93f8
[crc] getZhenxiLoctionCrc rva=0x2ae064
[+] native bypass installed: 25 ok, 1 missing
\```

`1 missing` = `getZhenxiInfoH`(印证不在 batch 表)。证据等级:`✓闭环`。

#### 6.0.2 安全 syscall 跳板:借 linker SVC 绕开 libc 监控(检测点#3)

链路:

\```
safe_syscall_via_trampoline(sysno, ...) @ 0x248cc4
 ├─ use_secure_syscall_trampoline_enabled @ 0x1b2288 总开关
 ├─ InitSecureTrampolinePage @ 0x1b22c0 惰性 init, mutex 保护
 │ ├─ FindLinkerSyscallAddr("/linker64", 93) @ 0x1b1c9c
 │ ├─ mmap RWX → 拷 48B 模板 → mprotect R-X
 │ └─ NEON 算 baseline checksum → ctx[+0x28]
 ├─ get_trampoline_id_tag @ 0x1b21b4 读 "runtime_syscall_code"
 ├─ calc_additive_checksum(page, 48) @ 0x261f14 失配重建,再失配 exit(9)
 └─ ((fn)page)(sysno, a1..a6) 跳板执行 → linker64 内裸 SVC #0
\```

48 字节跳板模板 `.rodata @ 0x651FC..0x6522C`:

\```
fd 7b be a9 STP X29, X30, [SP,#-0x20]!
e8 03 00 aa MOV X8, X0 ; X8 = sysno
e0 03 01 aa MOV X0, X1 ; 参数左移一格
e1 03 02 aa MOV X1, X2
e2 03 03 aa MOV X2, X3
e3 03 04 aa MOV X3, X4
e4 03 05 aa MOV X4, X5
e5 03 06 aa MOV X5, X6
91 00 00 58 LDR X17, [PC,#+0x10] ; 读 page+0x30 处的 SVC #0 地址
20 02 3f d6 BLR X17 ; 跳 linker64 内裸 SVC #0
fd 7b c2 a8 LDP X29, X30, [SP],#0x20
c0 03 5f d6 RET
[+0x30: .quad <linker SVC#0 addr>]
\```

`FindLinkerSyscallAddr` 在 `/proc/self/maps` 中筛 pathname 含 `/linker64`、r-x 段,4 字节步进匹配 bionic syscall stub:

| 偏移(相对 n12) | 字节模式 / 等价反汇编 |
|-|-|
| `n12-12` | `MOVZ/MOVN W8, #imm`,要求 `imm == 93`(mask `(v11 & 0x1F80001F) == 0x12800008`) |
| `n12-8` | `0xD4000001` = `SVC #0` |
| `n12-4` | `0xB140041F` = `CMN X0, #0x1000` |
| `n12+0` | `0xDA809400` = `CSNEG X0, X0, X0, LS`(即 `cneg x0,x0,hi`;op=1/o2=1,非 CSINV) |
| `n12+4` | 与 `0xFF000010` 与后 `== 0x54000000`（B.cond） |
| `n12+8` | `0xD65F03C0` = `RET` |

匹配后返回 `start + (n12-8)`(即 SVC #0 那条指令),而非 stub 入口。跳板自己已把 sysno 放进 X8,跳到 `MOVZ W8, #93` 会被覆盖成 exit;直接跳 SVC #0 保留 X8。`93 = SYS_exit`,作为 SVC 定位锚。`id_tag` 字面量 `0x5dd44`,全局构造器 `sub_1B3088`:

```c
strcpy(&dest_@0x2F09E8, "(runtime_syscall_code"); // 首字 '(' (0x28) 是 libc++ SSO 控制字节,长度 20
\```

`g_secure_trampoline_ctx` 结构:`+0x00 page`、`+0x08 length=48`、`+0x10 std::string id_tag`、`+0x28 baseline_sum`、`+0x30 initialized=1`。

被动取证(`verify_4_5_passive.js`)ctx 实测:

\```
ctx 指针 0xb40000752359c1b0 (arena 分配, TBI/Scudo top-byte 指针标签,非硬件 MTE)
ctx[+0x00] page 0x773e804000
ctx[+0x08] length 48
ctx[+0x10] id_tag "runtime_syscall_code" (20 字节 SSO)
ctx[+0x28] sum 0x14E0
ctx[+0x30] init 1
page 权限 r-x；page 首 48B 与 .rodata 模板 100% 一致
page[+0x30] 0x7741a00694 (缓存 SVC 地址)
\```

`page[+0x30]` 反查 linker stub:`@stub-4 = 0xd2800ba8 = MOVZ X8,#93`、`@stub = 0xd4000001 = SVC #0`、`@stub+4 = 0xb140041f = CMN X0,#0x1000`,所在段 `0x77419ee000-0x7741b0e000 r-x /apex/com.android.runtime/bin/linker64`。累加和三向一致:

\```
calc_additive_checksum(page=0x773e804000, len=48) → 0x14E0 (静态推算)
Frida JS 读 page 前 48B 朴素 byte sum → 0x14E0 (动态)
ctx[+0x28] baseline_sum → 0x14E0 (ctx 读取)
\```

调用面分布(`verify_4_5_7_call_surface_v2.js`,30s,5300+ 次样本):

| sysno | 名称 | 静态 callsite 数 | 运行时次数 | 运行时 % |
|-|-|-|-|-|
| 78 | `readlinkat` | 6 | 4251 | 80.2% |
| 56 | `openat` | 2 | 461 | 8.7% |
| 57 | `close` | 1 | 456 | 8.6% |
| 63 | `read` | 1 | 76 | 1.4% |
| 207 | `recvfrom` | 1 | 28 | 0.5% |
| 62 | `lseek` | 1 | 12 | 0.2% |
| 101 | `nanosleep` | 1 | 12 | 0.2% |
| 43 | `statfs` | 2 | 2 | 0.04% |
| 80 | `fstat` | 1 | 1 | 0.02% |
| 160 | `uname` | 1 | 1 | 0.02% |
| 129 | **`kill`** | **102** | **0** | **0%** |
| 167 | `prctl` | 1 | 0 | — |
| 9 | `lgetxattr` | 1 | 0 | — |
| 462 | `mseal` | 1 | 0 | — |

`kill` 102 个 callsite(每条检测失败分支各写一次 SIGKILL,代表"分散冗余"非"频繁"),本轮命中 0 次说明未进 SIGKILL 分支。命名 syscall 包装器 `0x1AFE4C..0x1AFEF8`:`ssyscall_openat(56) / openat_atfdcwd(56) / read(63) / lseek(62) / close(57) / nanosleep(101) / readlinkat(78)`。不在跳板列表的有:`write`、`mmap`、`mprotect`、`getdents64`、`newfstatat(79)`。对抗效果:`Interceptor.attach(libc.so syscall)` 永不触发;PLT/inline-hook 具名包装无效;入口 inline-hook 触发 `calc_additive_checksum` 失配重建,再失配 `exit(9)`。证据等级:`✓闭环`。

#### 6.0.3 风险项汇聚点 `build_native_ListItemBean_risk`(检测点#4)

\```
libhunter.so+0x278658, size 0x8EC, 被 22 caller × 83 callsite 调用,引用 com/zhenxi/hunter/bean/ListItemBean
\```

Hex-Rays 把 OLLVM 平坦化后错认为 1 参,真实签名 6 参:

```c
void build_native_ListItemBean_risk(
 JNIEnv* env, // X0
 std::string* title, // X1 — 栈上 std::string,由 sub_2447A8(out, lit) 构造
 std::string* detail, // X2
 int risk, // W3 — 0 / 1
 int Type, // W4 — 1..4 类别
 int ShowPriority // W5 — 0..11 子优先级
);
\```

读 std::string(SSO/long 自适应):

```js
function readStdString(p) {
 const firstByte = p.readU8;
 if ((firstByte & 1) === 0) { // SSO 短串
 const size = firstByte >> 1;
 if (size <= 0) return '';
 return p.add(1).readUtf8String(size);
 }
 const size = p.add(8).readU64.toNumber; // long 形式
 const dataPtr = p.add(16).readPointer;
 return dataPtr.readUtf8String(size);
}
\```

W3/W4/W5 enum 分布(83 callsite 静态扫描):W3 `0×66(80%) / 1×17(20%)`,`1` 几乎只在严重路径(APK 签名失败 / Find Others Process / file lib error / Linker hooked+kill);但 `W3=0 ≠ 非高危`(InfoF checkLibCheckSum W3=0 但 UI 是 Deadly)。W4 `3×44 / 1×17 / 2×15 / 4×7`,对应 Java `FB.a/b/c/d`。W5 子类别:0 misc;1 Root mount;3 APK 签名/Maps Hide/Base;4 Process/File lib/Binder;6 Library checksum;7 Info7;8 Frida;9 Info6;10 Linker hook/Risk file;11 Simulator。

22 caller × 83 callsite 完整字典(粗体为最可能 title,`<dyn>` 纯动态拼接):

| Caller | callsite | (W3, W4, W5) | 关键字面量 |
|-|-|-|-|
| `CheckVpn` | `0x2ab014` | (0, 1, 0) | "tun" "ppp" "pptp" **"Find Vpn Native"** |
| `checkFromZygote` | `0x2ac0f8` | (0, 1, 0) | **"Zygote Check Find Risk Mark"** |
| `checkRiskFile` | `0x2ace44` | (1, 2, 10) | **"Find Risk File"** + 25 条 `/data/local/tmp/*` |
| `checkRootFromAVCLog` | `0x2aaec4` | (0, 1, 1) | **"Find Root File In Sniff"** |
| `checkZygisk` | `0x2a9690` | (0, 2, 0) | `<dyn>` |
| `getZhenxiInfoCBinder` | `0x28cd08` | (0, 3, 4) | **"find system server hook"** |
| `getZhenxiInfoEnv` | `0x28d3a4` | (0, 4, 0) | **"Get Env Info"** |
| `getZhenxiInfoMPNI` | `0x2994f4` | (0, 1, 0) | "/oat/arm64/" **"Find Mark ELF"** |
| `getZhenxiInfoVV` | `0x2c2854` | (0, 3, 4) | `<dyn>` |
| `getZhenxiInfo3` × 7 | `0x2b490c..0x2b4ed4` | (0, 1, 1) | "Check Find Root In Linker" / **"Check Find Root Permission"** / **"Find Root Mark In Mountinfo"** |
| `getZhenxiInfo4` × 4 | `0x2a3f30..0x2a43f8` | (0/1, 3/4, 4) | **"Find Others Process"** + "find other process" + "ps error" |
| `getZhenxiInfo5` × 3 | `0x2a47f4 / 0x2a5204 / 0x2a5470` | (0, 2, 8) | **"Find Frida Mark"** + "gum-js-loop" / "gmain" / `<dyn>` |
| `getZhenxiInfo6` × 2 | `0x2a6084 / 0x2a6294` | (0/1, 2/3, 9) | `<dyn>` |
| `getZhenxiInfo7` × 2 | `0x2a65ec / 0x2a662c` | (0/1, 3, 7) | `<dyn>` |
| `getZhenxiInfoF` × 8 | `0x2ada3c..0x2adf74` | (0, 3/4, 6) | **"checkLibCheckSum"** / **"checkLinkerCheckSum"** |
| `getZhenxiInfoL` × 2 | `0x2a87b8 / 0x2a91c8` | (0/1, 3, 10) | **"Find Linker Is Hook"** / **"Check Linker Crc Error"** |
| `getZhenxiInfoO` × 5 | `0x2bec24..0x2bf71c` | (0, 2, 11) | **"Find Simulator OpCode Mark!"** / **"Find Simulator Env Mark!"** / **"Find Simulator Mount Mark!"** |
| `getZhenxiInfo0` × 6 | `0x2c00d4..0x2c15d8` | (0/1, 3, 3/4) | "Insufficient permissions" / **"Check App Sign Error From Path Lib"** / **"Mem Find Mark"** |
| `getZhenxiInfo2` × 11 | `0x29d6c0..0x2a0304` | (0/1, 3, 3) | **"HunterCheckApkSignError"** + 11 子原因 |
| `getZhenxiInfoBase` × 19 | `0x292e18..0x2952a4` | (0, 1/2/3, 多种) | **"Linker Find Hook Mark"** / "lsposed" / "zygisk" / **"Find Prop Modify Mark"** / **"Find Hook Mark"** / **"Base Check Inline Flag"** / **"Find Mnt Mark"** / **"Find Magisk Modules Mark"** / **"Seccomp Check Arch Find Mark"** / **"Check Signal Not Match"** / **"Check Uname Spoofing"** |
| `getZhenxiMapCheck` × 3 | `0x2923e8 / 0x292434 / 0x2924b4` | (0, 2/3, 0) | **"libart.so piecewise ,memory is not legal"** / **"find libart.so hooked"** |
| `sub_2A1C38` × 2 | `0x2a2c20 / 0x2a2c68` | (0, 3, 3) | **"Check Maps Find Hide"** |

hook `0x278658` 闭环输出:

\```
[ReportRiskItem]
 arg1: Check Find Root In Mounts
 arg2: com.zhenxi.hunter:hunter_main_process
/proc/mounts->APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
ReportRiskItem this->lr: libhunter.so+0x2b4a88
\```

对回方法:`this.context.lr - 4` = 静态 callsite RVA。LR `0x2B4A88` 落在 `getZhenxiInfo3 @ 0x2B476C` 内。`arg2` 是动态上下文(路径/线程名/接口名),静态字典没有,取证价值最高。兜底 bypass 按 title 名单丢弃(`BLOCK_TITLE_NEEDLES` 含 `Check Find Root` / `Find Others Process` / `Find Frida Mark` / `Find Vpn Native` / `检测到libart.so被修改` / `HunterCheckApkSignError` 等)。证据等级:`✓闭环`。

#### 6.0.4 防崩前置:`maps_precheck_readable @ 0xC6520` unmapped hole bug

凡触发 checksum / maps-RX / ELF 段枚举的脚本都应先装 `block_bad_precheck`。该预检未证明 `[addr, addr+size)` 被可读 mapping 完整覆盖,跨 unmapped hole 后续 NEON 批量读取可能 SIGSEGV。

```js
function block_bad_precheck(modbase) {
 const badOnce = new Set;
 function untag(p) { return ptr(p).and(ptr("0x00ffffffffffffff")); }
 function isFullyReadable(addr, size) {
 if (size === 0) return false;
 let cur = untag(addr);
 const end = cur.add(size);
 while (cur.compare(end) < 0) {
 const r = Process.findRangeByAddress(cur);
 if (r === null) return false;
 if (!r.protection.includes("r")) return false;
 const rangeEnd = r.base.add(r.size);
 cur = rangeEnd.compare(end) < 0 ? rangeEnd : end;
 }
 return true;
 }
 Interceptor.attach(modbase.add(0xC6520), {
 onEnter(args) { this.p = args[0]; this.size = args[1].toUInt32; this.ppp = this.context.lr.sub(modbase); },
 onLeave(retval) {
 if (retval.toInt32 === 0) return;
 if (!isFullyReadable(this.p, this.size)) {
 const key = untag(this.p).toString + ":" + this.size;
 if (!badOnce.has(key)) { badOnce.add(key);
 console.log("block bad precheck", untag(this.p), "size", ptr(this.size), "off", this.ppp); }
 retval.replace(0);
 }
 }
 });
}
\```

实测拦下片段:

\```
block bad precheck 0x773acbe000 size 0x7000 off 0xc68a4
block bad precheck 0x7741a35000 size 0x1266d8 off 0xc7828
block bad precheck 0x774059e000 size 0x1000 off 0xc68a4
\```

`off 0xC68A4` 在 `sub_C687C`(parse_elf_rx_segments 内 ELF 读出后预检);`off 0xC7828` 在 `scan_rx_segment_neon_sum @ 0xC772C`(RX 段扫描)。两个 LR 模式覆盖两条独立完整性检查链路的越界点,在检测点#5/#8/#20/#21 的实测中反复出现。

---

### 6.1 Root 文件 / 挂载 / maps 检测

#### 6.1.1 `/proc/mounts` Root/APatch 检测(检测点#6)

链路:

\```
Java: GC.run -> NativeEngine.getZhenxiInfo3
JNI : NativeEngine_getZhenxiInfo3 @ 0x2B476C
核心: detect_root_mark_in_proc_mounts_maps @ 0xD5E34
辅助: file_contains_any_marker @ 0x1A6300
上报: ReportRiskItem LR 0x2B4A88
UI : "Check Find Root In Mounts"
\```

`getZhenxiInfo3` 是 7 路短路链:

| 顺序 | 子函数 RVA | UI title | 主要监测点 |
|-|-|-|-|
| 1 | `0xD2CDC` | `Check Find Root File` | 固定 root/hook 文件路径、`/proc/<pid>/attr/*`、OverlayFS、`/data/adb/modules`、mount namespace、`/proc/modules` |
| 2 | `0xD5E34` | `Check Find Root In Mounts` | `/proc/mounts`、`mountinfo`、线程 maps、`df -h` 中的 root/APatch/Magisk marker |
| 3 | `0xD703C` | `Check Find Root Mark` | `/data/adb*`、Magisk/LSPosed/Riru marker、`/proc/fs/jbd2` 与 ext4 loop 痕迹 |
| 4 | `0xD9604` | `Check Find Root Magisk Mode` | 当前版本直接 `return 0`,保留分支 |
| 5 | `0xD216C` | `Check Find Root In Linker` | `dl_iterate_phdr` 收集 linker 已加载 ELF,匹配可疑 Zygisk engine |
| 6 | `0xDDB9C` | `Check Find Root Permission` | `/proc/mounts`·`mountinfo`·`maps` + `df -h` 扫描(实测 sub_DC230;netlink 探针实为独立函数 `0xE34AC`) |
| 7 | `0xDF51C` | `Find Root Mark In Mountinfo` | `/proc/self/exe` 类型、`/proc/self/mountinfo` overlay/system/bin 痕迹 |

入口伪代码:

```c
// libhunter.so+0x2B476C
jobject NativeEngine_getZhenxiInfo3(JNIEnv *env) {
 if (check_root_file_and_namespace) // sub_D2CDC
 return ReportRiskItem(env, "Check Find Root File ", detail, FB_Info, 1);
 if (detect_root_mark_in_proc_mounts_maps) // sub_D5E34
 return ReportRiskItem(env, "Check Find Root In Mounts ", last_mounts_detail, FB_Info, 1);
 if (check_root_mark_data_adb_and_jbd2) // sub_D703C
 return ReportRiskItem(env, "Check Find Root Mark ", detail, FB_Info, 1);
 if (check_magisk_mode_reserved) // sub_D9604, return 0
 return ReportRiskItem(env, "Check Find Root Magisk Mode ", detail, FB_Info, 1);
 if (check_root_in_linker_loaded_elf) // sub_D216C
 return ReportRiskItem(env, "Check Find Root In Linker ", detail, FB_Info, 1);
 if (check_root_mounts_maps_df(env)) // sub_DDB9C(/proc/mounts·mountinfo·maps + df;非 netlink,netlink 见 sub_E34AC)
 return ReportRiskItem(env, "Check Find Root Permission", detail, FB_Info, 1);
 if (check_mountinfo_overlay_system_bin) // sub_DF51C
 return ReportRiskItem(env, "Find Root Mark In Mountinfo", detail, FB_Info, 1);
 return NULL;
}
\```

`detect_root_mark_in_proc_mounts_maps @ 0xD5E34` 读 6 源:`/proc/mounts` → `/proc/self/mounts` → `/proc/self/mountstats` → `/proc/self/mountinfo` → `/proc/self/task/<tid>/maps` → `popen("df -h")`。18 项 marker 向量(`sub_D116C @ 0xD116C`):

\```
/riru, riru-, /edxp, lsposed,
magisk, Magisk, /appwidget, /debug_ramdisk,
dex2oat, apatch, Apatch, APatch,
kernelsu, kernelSu, zygisk, revanced,
/data/adb/modules, sukisu
\```

`file_contains_any_marker @ 0x1A6300` 纯 substring(不解析 mount 字段):

```c
bool file_contains_any_marker(const char *path, vector<string> *markers, string *out) {
 FILE *fp = fopen(path, "re");
 if (fp == NULL) { cout << "file_include open file fail " << path << " " << strerror(errno); return false; }
 string line;
 while (getline(fp, line)) {
 cout << "file_include checking " << path << " " << line;
 for (string &marker : *markers) {
 if (marker.empty) continue;
 if (line.find(marker) != string::npos) {
 cout << "file_include find " << path << " " << line;
 *out = line; fclose(fp); return true;
 }
 }
 }
 fclose(fp); return false;
}
\```

主路径命中实测:

\```
[evidence:mounts] NativeEngine_getZhenxiInfo3 entered
[evidence:mounts] detect_root_mark_in_proc_mounts_maps entered
[evidence:mounts-file] file_contains_any_marker path=/proc/mounts
 markers=/riru|riru-|/edxp|lsposed|magisk|Magisk|/appwidget|/debug_ramdisk|dex2oat|apatch|Apatch|APatch|kernelsu|kernelSu|zygisk|revanced|/data/adb/modules|sukisu
[evidence:mounts-file] path=/proc/mounts ret=0x1
 hit=APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
[evidence:mounts] detect_root_mark_in_proc_mounts_maps ret=0x1
[evidence:report] title=Check Find Root In Mounts lr=libhunter.so+0x2b4a88 (rva=0x2b4a88)
 detail=com.zhenxi.hunter:hunter_main_process
 /proc/mounts->APatch /debug_ramdisk tmpfs rw,seclabel,relatime 0 0
[evidence:mounts] NativeEngine_getZhenxiInfo3 ret=0x7737909809
[evidence:ui] title=Check Find Root In Mounts risk=Info type=1
 data=com.zhenxi.hunter:hunter_main_process
[evidence:ui] title=Check Find Root In Mounts risk=Info type=1
 data=com.zhenxi.hunter:hunter_server_iso:com.zhenxi.hunter.ZhenxiServer:hunter_iso_service
\```

命中行同时命中 `APatch` 和 `/debug_ramdisk` 两个 marker,只替换其一不够。短路链强制 miss 实验(`trace_info3_branch_experiment.js`):

\```
[+] FORCE_MISS={"rootFile":false,"mounts":true,"rootMark":false,"linker":false,"permission":true,"mountinfo":false}
[info3-branch-ret] sub_D2CDC title="Check Find Root File" ret=0x0
[info3-branch-ret] sub_D5E34 title="Check Find Root In Mounts" ret=0x1
[info3-force] sub_D5E34 real ret=0x1 forced to 0 so the next branch can run
[info3-branch-ret] sub_D703C title="Check Find Root Mark" ret=0x0
[info3-branch-ret] sub_D9604 title="Check Find Root Magisk Mode" ret=0x0
[info3-branch-ret] sub_D216C title="Check Find Root In Linker" ret=0x0
[info3-branch-ret] sub_DDB9C title="Check Find Root Permission" ret=0x1
[info3-force] sub_DDB9C real ret=0x1 forced to 0 so the next branch can run
[info3-branch-ret] sub_DF51C title="Find Root Mark In Mountinfo" ret=0x0
[info3] NativeEngine_getZhenxiInfo3 ret=0x0
\```

本设备真实命中两点:`sub_D5E34`(mounts APatch)和 `sub_DDB9C`(`/proc/mounts`·mountinfo·maps + df 扫描;非 netlink,netlink 探针实为 `sub_E34AC`)。`file_contains_any_marker` 是通用 helper,同会话复用不同 marker 向量(`docker|lxc_volumns` / 模拟器 12 路径)。bypass `NativeEngine.getZhenxiInfo3 -> null`,但 `:hunter_server_iso` / `:hunter_server_twin` 子进程仍可 Binder 回传(详 第6节.终.多进程)。证据等级:`✓闭环`。

#### 6.1.2 libart maps 分片/Hook 检测(检测点#7)

链路:

\```
Java: NativeEngine.getZhenxiMapCheck
JNI : NativeEngine_getZhenxiMapCheck @ 0x291858
输入: /proc/self/maps 解析结果
上报: ReportRiskItem LR 0x2924B8(size==0x1000 立即上报分支)
UI : "find libart.so hooked 0"
\```

引用字符串:`libart.so` / `libart.so piecewise ,memory is not legal` / `check map legal error` / `open maps error`。伪代码:

```c
// libhunter.so+0x291858
maps = parse_maps_to_linked_list(-1);
if (maps == NULL)
 return ReportRiskItem(env, "check map legal error ", "open maps error ", NoRisk_or_Deadly, 3);
libart_piece_count = 0; detail = "";
for each map_node:
 if pathname contains "libart.so":
 libart_piece_count++;
 detail += pathname + "|" + decimal(map_node.size) + "|" + map_node.perms + "|"
 + hex(map_node.start) + "->" + hex(map_node.end) + "\n";
 if map_node.size == 0x1000:
 return ReportRiskItem(env, "find libart.so hooked " + decimal(map_node.size),
 format_map_node(map_node), Deadly, 3);
if libart_piece_count >= 6:
 return ReportRiskItem(env, "libart.so piecewise ,memory is not legal ", detail, Deadly, 2);
return NULL;
\```

关键地址:`0x29188C parse_maps_to_linked_list(-1)`、`0x291D40 strstr(pathname,"libart.so")`、`0x292358 if size==4096`、`0x292480 title="find libart.so hooked "+size`、`0x2924B8 ReportRiskItem`、`0x2923B4 if count<6 return NULL`、`0x2923CC "piecewise"`、`0x2923EC ReportRiskItem`。两个独立判定:单段 `size==0x1000` 立即上报;分片 `count>=6` 报 piecewise(静态/间接证据,本环境未触发)。只看 maps 形态,不校验文件内容。实测:

\```
[evidence:art-map] NativeEngine_getZhenxiMapCheck entered
[evidence:report] title=find libart.so hooked 0 lr=libhunter.so+0x2924b8 (rva=0x2924b8)
 detail=map item path ->
 name ->
 []
 exec address start-> 0x0
 exec address end-> 0x0
 perm ->
 inode -> 0
 mem size -> 0
 pid-> 16657
[evidence:ui] title=find libart.so hooked 0 risk=Deadly type=0 data=map item path ->
\```

>
> 注【待核实】:伪代码触发条件 `size==0x1000`、title 拼 `"hooked "+size`,命中本应打印 "hooked 4096";实测却是 "hooked 0" 且节点 start/end/size/inode 全 0。要么触发条件并非精确 `==0x1000`,要么 Frida 读到了清零/错位的 map 节点(instrumentation artifact),需回 IDB 核对 `0x292358` 分支与 `format_map_node` 字段。
>
>
>

bypass `NativeEngine.getZhenxiMapCheck -> null`。证据等级:`✓闭环`(piecewise 分支间接 ✓)。

#### 6.1.3 maps 隐藏检测 `sub_2A1C38`(字典级)

`sub_2A1C38 @ 0x2A1C38` 2 callsite(`0x2a2c20 / 0x2a2c68`,W3=0/W4=3/W5=3),title 候选 **"Check Maps Find Hide"**。仅字典级、未细拆。证据等级:`字典级`。

---

### 6.2 完整性自检:CRC 双链 + checksum(检测点#5 / 检测点#8)

Hunter 对 `libart.so` / `libc.so` / `linker64` / `libhunter.so` 做运行时 r-x 段累加和自检,两条独立链路。

链路总览:

\```
链路 1:Java 驱动的 CRC 比较
 NativeEngine.getZhenxiLoctionCrc : HashMap
 ↓ Java_NativeEngine_getZhenxiLoctionCrc @ 0x2AE064
 ↓ anti_inject_collect_results(rb_tree) @ 0xC8670
 ↓ sub_1A57DC: 红黑树 → Java HashMap (path → sum)
 ↓ Java YouAreLoser.ig.apply: local=parseLong(map.get(path)); remote=item.b
 if (local!=0 && remote!=0 && local!=remote) → "ISO CRC NOT MATCH LOCALITY CRC"

链路 2:后台 task,不经 Java
 task_MAIN_CRC_check @ 0x2D6804
 ├─ check_libc_elf_checksum_status @ 0xC90A0
 ├─ check_libart_elf_checksum_status @ 0xC9130
 └─ sub_C8FD0(libhunter_path)
 ↓ ReportRiskItem("检测到libart.so被修改" / "检测到libc.so被修改" / ...)
\```

共享底层算法栈:

\```
scan_modules_for_path(path) @ 0xC8500
 ├─ parse_elf_rx_segments(s, path) @ 0xC6F14 ── ELF 文件 baseline(ssyscall_openat/read/lseek/close)
 │ 遍历 PT_LOAD with PF_X,NEON sum → s->segs[i].file_checksum,cache qword_2EF8B0
 └─ scan_rx_segment_neon_sum(start, end, perms, s, path) @ 0xC772C ── 内存侧实测
 maps_precheck_readable 先过,NEON 128-bit 加宽累加,v5 += 段 sum
\```

NEON 字节累加和(与跳板 baseline、parse_elf_rx_segments 同源):

\```
sum = 0
for each 16 bytes from ptr:
 vmovl_u8 / vmovl_high_u8 把 16 个 u8 拆成 8x u16，再拆成 4x u32
 8 个 u32 通道并行 vaddw 加进 8 个 u64 累加器
最后 vaddvq_s64 合并 8 个 u64 → 返回该段总和
\```

纯 sum、无取模、无 lookup table:`sum = Σ(byte)`。`scan_rx_segment_neon_sum @ 0xC772C`:

```c
uint32_t scan_rx_segment_neon_sum(uintptr_t start, uintptr_t end, char *perms, ElfRxBaseline *s, const char *path) {
 if (perms[0..3] != "r-x*") return 0;
 uint32_t v5 = 0;
 for (i = 0; i < s->n_segs; i++) {
 uintptr_t mem_ptr = start + s->segs[i].offset;
 size_t size = s->segs[i].size;
 if (!maps_precheck_readable((void *)mem_ptr, size)) v14 = 0;
 else v14 = NEON_sum(mem_ptr, size);
 v5 += v14;
 }
 return v5; // 不原地比对,只返回所有段 sum 之和
}
\```

找 r-x 区间主备两路:主路径 hunter 自实现 DSO 列表 `g_dso_list_head`(`dl_iterate_phdr + getauxval(AT_PHDR)`);备路径 `/proc/self/maps`(`parse_maps_to_linked_list(-1)`,走 libc fopen,是整条链唯一可被 libc-hook 干扰处)。Java 侧比较 `YouAreLoser.ig.apply`:

```java
Object apply(Object obj) {
 rD item = (rD) obj;
 String path = item.a;
 long remote = item.b;
 long local = parseLong(nativeHashMap.get(path));
 if (local != 0 && remote != 0 && local != remote) triggerDetection;
 return hH.a;
}
\```

实测 libart.so 各段(只有 r-xp 返回非零):

\```
[crc-rx] path=/apex/com.android.art/lib64/libart.so start=0x74718a0000 end=0x747205c000 size=0x7bc000 perms=r-xp
[crc-rx] path=/apex/com.android.art/lib64/libart.so segmentChecksum=846246994 ret=0x3270b452
[crc-module] scan_modules_for_path path=/apex/com.android.art/lib64/libart.so checksum=846246994 ret=0x3270b452
\```

libhunter.so 模块 checksum = 各非零段 sum 累加(数学验证):

\```
r-xp 0x73d4221000.. segmentChecksum=252930381 / 0xf13694d
rwxp 0x73d42e7000.. segmentChecksum=748020 / 0xb69f4
r-xp 0x73d42ea000.. segmentChecksum=763632 / 0xba6f0
252930381 + 748020 + 763632 = 254442033
0xf13694d + 0xb69f4 + 0xba6f0 = 0xf2a7a31 ✓
\```

`rwxp` 段 checksum 不必然为 0(libhunter 0xb69f4 vs linker64 0)。Java CRC 比较命中:

\```
[evidence:crc-java] ig.apply path=/apex/com.android.art/lib64/libart.so remote=846246994 ret=YouAreLoser.qH@2187160
[evidence:ui] title=ISO CRC NOT MATCH LOCALITY CRC risk=Deadly type=0 data=/apex/com.android.art/lib64/libart.so
[Java MainActivity.n0]
 title=ISO CRC NOT MATCH LOCALITY CRC
 data=/apex/com.android.art/lib64/libart.so
locality crc -> 856386775
remote service crc -> 846246994
\```

`local=856386775 ≠ remote=846246994` → 触发。链路 2 native 直接上报:

\```
[evidence:checksum] check_libart_elf_checksum_status entered
block bad precheck 0x7741a35000 size 0x1266d8 lr ... off 0xc7828
[evidence:checksum] check_libart_elf_checksum_status ret=0x1
[evidence:report] title=检测到libart.so被修改 lr=libhunter.so+0x2ada40 (rva=0x2ada40)
[evidence:ui] title=检测到libart.so被修改 risk=Deadly type=6
\```

LR `0x2ada40` 落在 `getZhenxiInfoF @ 0x2AD9A8` 内（`0x2ada40-0x2AD9A8=0x98`）。`block_bad_precheck` 多轮拦截分别在 `off 0xc68a4`(sub_C687C)和 `off 0xc7828`(scan_rx_segment_neon_sum)反复触发,印证两条独立链路越界点。libhunter.so CRC 值动态变化(`258223051` / `252914579` / 本节 `254442033`),是对运行时 RX 段/映射状态采样的特征,不是静态文件 CRC。

检测点#8 链路 2 `getZhenxiInfoF @ 0x2AD9A8` 内 8 callsite(W3=0/W4=3 或 4/W5=6):

```c
uint32_t check_libart_elf_checksum_status { return check_elf_checksum(build_libart_path); } // 0xC9130
uint32_t check_libc_elf_checksum_status { return check_elf_checksum(get_libc_path); } // 0xC90A0
uint32_t check_linker64_elf_checksum_status { return check_elf_checksum(get_linker64_path); } // 0xC89BC
\```

bypass 两层:`getZhenxiLoctionCrc` 让 HashMap 全 value="0"（ig.apply 因 local=0 跳过）+ `ig.apply` 对目标 path 返回 NoRisk + `getZhenxiInfoF -> null` + 必带 `block_bad_precheck`:

\```
[bypass:crc] ig.apply skip compare path=/apex/com.android.art/lib64/libart.so remote=846246994
[bypass:checksum] NativeEngine.getZhenxiInfoF -> null
\```

`task_MAIN_CRC_check` 后台任务仍可能触发,需 JNI 入口 replace 或 0x278658 兜底。证据等级:`✓闭环`。

---

### 6.3 注入 / 匿名可执行内存检测(检测点#9)

链路:

\```
Java: GC.m -> NativeEngine.getZhenxiInfoInjection
JNI : NativeEngine_getZhenxiInfoInjection @ 0x28DF24
内部: 6 个子检测,任一非空返回
UI : "Hunter Find Unknown Exec Item From Mian" (注意 "Mian" 是原 typo)
\```

Java 触发:

```java
String s = NativeEngine.getZhenxiInfoInjection;
if (s != null && !s.isEmpty)
 n0(new ListItemBean("Hunter Find Unknown Exec Item From Mian", FB.c, App.getCheckFrom + s));
\```

6 子检测:

| 子函数 | 检测对象 | 标志字符串 |
|-|-|-|
| `0x100AAC` | 匿名/未知路径可执行内存(rwxp+inode=0+path 空或 ?) | `"mem, suspicious execution procedure ->"` / `"find rwx item 111"` / `"libc_malloc"` / `"scudo"` |
| `0x102814` | memfd JIT cache mapping | `"memfd:jit-cache"` / `"memfd:jit-zygote-cache"` |
| `0x103610` | maps 行格式异常 | `<dyn>` |
| `0x104D54` | missing page(可执行但 mapping 缺失页) | `"missing page, suspicious execution procedure ->"` / `"pid ->"` |
| `0x105ACC` | NativeBridge/AndroidRuntime hook | `dlopen("/system/lib64/libandroid_runtime.so")` + `_ZN7android14AndroidRuntime10getRuntimeEv` / `"Found Hook NativeBridge"` |
| `0x10610C` | 匿名内存/jit-cache 一致性 | `"Found suspicious anonymous memory"` / `"find inconsistent dalvik-zygote-jit-code-cache :"` / `"[anon:dalvik-zygote-jit-code-cache]"` / `"/memfd:jit-cache"` |

伪代码:

```c
// libhunter.so+0x28DF24
jstring NativeEngine_getZhenxiInfoInjection(JNIEnv *env) {
 string out;
 if (sdk >= 30) out += detect_unknown_exec_or_rwx_maps; // 0x100AAC
 if (out.empty) out += detect_jit_cache_maps; // 0x102814
 if (out.empty) out += detect_extra_maps_anomaly; // 0x103610
 if (out.empty) out += detect_missing_page_exec_anomaly; // 0x104D54
 if (out.empty) out += detect_nativebridge_runtime_hook; // 0x105ACC
 if (out.empty) out += detect_suspicious_anonymous_memory;// 0x10610C
 if (out.empty) return NULL_or_empty;
 return NewStringUTF(result);
}
\```

默认命中(0x100AAC)完整返回字符串:

\```
mem, suspicious execution procedure ->
pid ->4325/com.zhenxi.hunter:hunter_main_process
map item path ->
7727002000-7727012000 rwxp 00000000 00:00 0 ?
name -> []
exec address start-> 0x7727002000
exec address end-> 0x7727012000
perm -> rwxp
inode -> 0
mem size -> 65536
pid-> 4325
------------------------------
find rwx item 111
\```

6 子检测拆分(`trace_injection_subchecks_template.js`):

\```
sub_100AAC / anonymous/unknown executable maps and RWX: outLen=3131
 7727012000-7727022000 rwxp 00000000 00:00 0 ? size=65536
 773e719000-773e71a000 rwxp 00000000 00:00 0 ? size=4096
sub_102814 / memfd JIT cache maps: outLen=0
sub_103610 / extra maps anomaly formatting: outLen=0
sub_104D54 / missing page executable anomaly: outLen=0
sub_105ACC / NativeBridge/AndroidRuntime hook: outLen=0
sub_10610C / anonymous memory / jit-cache consistency scan: outLen=3106
 Found suspicious anonymous memory:
 7727012000-7727022000 rwxp ... size=65536
 773acbe000-773acc5000 rwxp ... size=28672
\```

当前环境命中 `0x100AAC`(默认)+ `0x10610C`(辅助);`0x102814/103610/104D54/105ACC` 未命中。Frida agent 主进程匿名 RWX 区是触发主因。bypass `getZhenxiInfoInjection -> ""`（Java 端 `!s.isEmpty` 不满足,源头 bypass）。证据等级:`✓闭环`(部分子检测未命中)。

---

### 6.4 其他进程扫描(检测点#10)

链路:

\```
Java: NativeEngine.getZhenxiInfo4(Context)
JNI : NativeEngine_getZhenxiInfo4 @ 0x2A2D98
上报: ReportRiskItem LR 0x2A3F6C (第一阶段) / 0x2A43B0 (第二阶段)
UI : "Find Others Processmay be risks main pid (...)" / "Find Others Process"
\```

两阶段:阶段1 `opendir("/proc")` + `/proc/<pid>/comm|cmdline`(helper `sub_1A5304`),关键字 `HUNTER_TRACER / install / hunter / linker / app_ / twin`;阶段2 `popen("ps -ef")`(`sub_D0DA4` 动态 `dlopen("libc.so")/dlsym("popen")`),逐行过滤 `!contains("hunter") && !contains("install")`,累计 >=3 上报。【待核实/前提】(1) 阶段1 匹配集三处不一致:正文列 `HUNTER_TRACER/install/hunter/linker/app_/twin`,伪代码却是工具名黑名单 `{sh,logcat,grep,getprop,…}`,实测命中又是 `logcat/ls`——需回 `sub_1A5304` 确认是按 cmdline 关键字还是 comm 工具名匹配;(2) 阶段1 跨进程可见性依赖设备未强制 hidepid,stock 机 `hidepid=2` 时 app 仅见自身 uid 进程,扫不到 shell uid 的 logcat/ls。伪代码:

```c
// libhunter.so+0x2A2D98
jobject NativeEngine_getZhenxiInfo4(JNIEnv *env, jobject context) {
 int main_pid = getpid;
 DIR *dir = opendir("/proc");
 while ((de = readdir(dir)) != NULL) {
 if (!is_decimal_pid(de->d_name)) continue;
 pid = atoi(de->d_name);
 if (pid == main_pid) continue;
 name = read_proc_pid_cmdline_or_comm(pid);
 if (name in {"sh","logcat","grep","getprop", ...})
 append("other pid -> %d(pid name: %s)\n", pid, name);
 }
 if (!result.empty)
 return ReportRiskItem(env, "Find Others Processmay be risks main pid (...)", result);
 if (sdk >= 30) {
 popen_fn = dlsym(dlopen("libc.so"), "popen");
 fp = popen_fn("ps -ef", "r");
 while (fgets(line, 0x1000, fp))
 { ps_detail += line; if (!contains(line,"hunter") && !contains(line,"install")) count++; } // detail 累加全量;过滤仅决定 count 阈值
 if (count >= 3) return ReportRiskItem(env, "Find Others Process", ps_detail);
 }
 return NULL;
}
\```

第一阶段命中:

\```
[evidence:report] title=Find Others Processmay be risks main pid (24499) lr=libhunter.so+0x2a3f6c (rva=0x2a3f6c)
 detail=other pid -> 24714(pid name: logcat)
other pid -> 24737(pid name: ls)
[evidence:ui] title=Find Others Processmay be risks main pid (24499) risk=NoRisk type=4
\```

第二阶段命中(会把 twin 进程 + `ps -ef` 本身写入 detail):

\```
[evidence:report] title=Find Others Process lr=libhunter.so+0x2a43b0 (rva=0x2a43b0)
 detail=UID PID PPID C STIME TTY TIME CMD
 u0_a280 9820 836 ... com.zhenxi.hunter:hunter_server_twin
 u0_a280 10055 9706 ... ps -ef
\```

`risk=NoRisk` 信息项,但暴露分析环境。bypass `getZhenxiInfo4 -> null`。证据等级:`✓闭环`。

---

### 6.5 APatch/KP/KernelSU side-channel timing 检测(检测点#11)

链路:

\```
Java: MainActivity.S -> NativeEngine.SideChanne
JNI : NativeEngine_SideChanne @ 0x2B3BD4
核心: detect_root_side_channel_apatch_kernelsu @ 0xE43BC
UI : "Check Root For SideChanne"
\```

算法:mmap 一页 0x1000 (RWX) → 拷 0x270 字节 probe 机器码(.rodata src__8)→ `__clear_cache` → 调用收集 4 组 timing(每组 10 个)s/s_1/s_2/s_3 → `sub_E60A4`(均值)/`sub_E63E8`(离散度)→ munmap。阈值判定:

```c
baseline_avg = sub_E60A4(s, 10); sample1_avg = sub_E60A4(s_1,10); ...
baseline_dev = sub_E63E8(s, baseline_avg); ...
if (baseline_dev*10 > baseline_avg) return false;
if (sample1_dev*10 >= sample1_avg) return false; // 同理 sample2/3
if (sample1_avg <= baseline_avg) return false; // 同理 sample2/3
ratio0 = (sample2_avg - baseline_avg) / (sample1_avg - baseline_avg);
ratio1 = (sample3_avg - baseline_avg) / (sample1_avg - baseline_avg);
if (ratio0 > 2.2 && ratio1 > 2.2) return set_result("KernelSU Installed (High Latency)", ratio0, ratio1);
if (ratio0 > 1.4 && ratio1 > 1.4) return set_result("APatch/KP Installed (Mid Latency)", ratio0, ratio1);
return false;
\```

静态字符串:`Side-Channel Detected: KernelSU Installed (High Latency) ratio0:` / `Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:` / `ratio1:`。Java 触发:

```java
public static ListItemBean S {
 String s = NativeEngine.SideChanne;
 if (s == null) return null;
 return new ListItemBean("Check Root For SideChanne", FB.a, s);
}
\```

实测命中:

\```
[evidence:side-channel] detect_root_side_channel_apatch_kernelsu ret=0x1
 data=Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:1.604278 ratio1:1.657754
[evidence:ui] title=Check Root For SideChanne risk=Info type=0
 data=Side-Channel Detected: APatch/KP Installed (Mid Latency) ratio0:1.604278 ratio1:1.657754
\```

另一轮 `ratio0:1.595745 ratio1:1.648936`,同档。基于 timing,文件系统层欺骗无效。bypass `SideChanne -> null`(返回空串 Java 仍会包空 data 风险项,须 null)。证据等级:`✓闭环`(KernelSU >2.2 档本环境未达,间接 ✓)。

---

### 6.6 TEE / Verified Boot / 解锁状态检测(检测点#12)

`"当前手机已经被解锁"` 文案有两条独立来源:

\```
链路 A:TEE attestation
 j40.b -> iW.d(new GC(..),"tee_check_thread") -> new z5(ctx, pm).b -> ((t5)v10.c).b -> YouAreLoser.e rootOfTrust
 判定: e.c = deviceLocked (false→解锁);e.b = verifiedBootState (1/2/3→patched)
 UI : "当前手机已经被解锁" / "Find Verified Boot Mark"

链路 B:getprop
 j40.a -> NativeEngine.getZhenxiInfoH("ro.boot.verifiedbootstate")
 判定: "orange"→当前手机已经被解锁;"yellow"→当前设备机型&ROM 可能被修改!
\```

链路 A Java:

```java
V1 v10 = new z5(mainActivity0, mainActivity0.getPackageManager).b;
if (v10 == null) {
 mainActivity0.n0(new ListItemBean("Tee is not supported or destroyed", FB.d));
} else {
 e e0 = ((t5)v10.c).b;
 if (!e0.c) n0(new ListItemBean("当前手机已经被解锁", FB.a, "tee check device unlock"));
 if (e0.b == 1 || e0.b == 2 || e0.b == 3)
 n0(new ListItemBean("Find Verified Boot Mark", FB.a, "the boot.img maybe have been patched\n" + e0));
}
\```

`e0.b`:0=Verified / 1=Self-signed / 2=Unverified / 3=Failed。链路 B Java:

```java
String s = NativeEngine.getZhenxiInfoH("ro.boot.verifiedbootstate");
if (s.equals("orange")) arrayList.add(new ListItemBean("当前手机已经被解锁", FB.a, s));
if (s.equals("yellow")) arrayList.add(new ListItemBean("当前设备机型&ROM可能被修改!", FB.a, s));
\```

`getZhenxiInfoH` 是 Java wrapper(不在 60 项 batch 表),调 `getPropInline(key,true)` → native `getZhenxiInfoZ` fallback 或 `/dev/__properties__`。实测:

\```
[evidence:bootstate-java] NativeEngine.getZhenxiInfoH(ro.boot.verifiedbootstate) -> orange
[evidence:ui] title=当前手机已经被解锁 risk=Info type=0 data=tee check device unlock
[evidence:ui] title=Find Verified Boot Mark risk=Info type=0 data=the boot.img maybe have been patched
[evidence:ui] title=当前手机已经被解锁 risk=Info type=0 data=orange
\```

UI 展开:`verifiedBootKey: 0000... / deviceLocked: false / verifiedBootState: Unverified`。两条独立须分别绕:链路 A `z5.b` 伪造 `V1(deviceLocked=true, verifiedBootState=0)`;链路 B `getZhenxiInfoH("ro.boot.verifiedbootstate") -> "green"` 或 `j40.a -> 空 ArrayList`。证据等级:`✓闭环`。

---

### 6.7 环境采集

#### 6.7.1 环境变量采集(检测点#13)

链路:`NativeEngine.getZhenxiInfoEnv` → `0x28CDB0`,ReportRiskItem LR `0x28D3A8`,UI `"Get Env Info"` risk=NoRisk type=4。伪代码:

```c
// libhunter.so+0x28CDB0
jobject NativeEngine_getZhenxiInfoEnv(JNIEnv *env) {
 std::string detail;
 for (char **p = environ; *p != NULL; ++p) { detail += *p; detail += "\n"; }
 return ReportRiskItem(env, "Get Env Info", detail, FB_NoRisk_or_Info, 0);
}
\```

实测:

\```
[evidence:report] title=Get Env Info lr=libhunter.so+0x28d3a8 (rva=0x28d3a8)
[evidence:ui] title=Get Env Info risk=NoRisk type=0 data=PATH=/product/bin:...
\```

detail 涵盖 `PATH / ANDROID_ROOT=/system / BOOTCLASSPATH / ANDROID_SOCKET_zygote / TMPDIR=/data/user/0/com.zhenxi.hunter/cache`。信息画像项。bypass `getZhenxiInfoEnv -> null`。证据等级:`✓闭环`。

#### 6.7.2 通用文件 marker 检测(检测点#14)

链路:`NativeEngine.getZhenxiInfoK(path, markers)` → `0x2B93BC`,核心 `file_contains_any_marker @ 0x1A6300`,UI 取决于调用方(如 `"当前手机可能是模拟器&云手机"`)。伪代码:

```c
// libhunter.so+0x2B93BC
jstring NativeEngine_getZhenxiInfoK(JNIEnv *env, jclass, jstring path, jobjectArray markers) {
 vector<string> native_markers;
 for (int i = 0; i < env->GetArrayLength(markers); i++)
 native_markers.push_back(GetStringUTFChars(markers[i]));
 if (file_contains_any_marker(path, native_markers, &hit_line))
 return NewStringUTF(hit_line.c_str);
 return NULL;
}
\```

Java 使用(`y00.java`):

```java
String[] markers = {"docker", "lxc_volumns"};
String s = NativeEngine.getZhenxiInfoK("/proc/mounts", markers);
if (s == null) { s = NativeEngine.getZhenxiInfoK("/proc/self/mountstats", markers);
 if (s == null) s = NativeEngine.getZhenxiInfoK("/proc/self/mountinfo", markers); }
if (s != null) arrayList0.add(new ListItemBean("当前手机可能是模拟器&云手机", FB.b, "(mounts异常)\n" + s));
\```

模拟器/云手机 markers 12 项实测:

\```
[evidence:file-marker] path=/proc/self/mountinfo markers=/mnt/shared/Sharefolder|/tiantian.conf|/data/share1|/hardware_device.conf|/mnt/shared/products|/mumu_hardware.conf|/Andy.conf|/mnt/windows/BstSharedFolder|/bst.conf|/mnt/shared/Applications|/ld.conf|/vboxsf
[evidence:file-marker-ret] path=/proc/self/mountinfo ret=0x0
\```

`getZhenxiInfoK` 是通用工具,检测属性取决于调用方(root markers / docker / 模拟器路径),全量 bypass 会破坏正常调用,应按 path×markers 细化。证据等级:`✓闭环`。

---

### 6.8 风险文件路径检测(检测点#15)

链路:

\```
Java: MainActivity.onCreate -> CancellationTokenSource.ۨۜۚ(this, NativeEngine.checkRiskFile)
JNI : NativeEngine_checkRiskFile @ 0x2AC514
辅助: sub_1A6228 @ 0x1A6228 (access(path, F_OK) == 0)
上报: callsite 0x2ace44 (W3=1, W4=2, W5=10)
UI : "Find Risk File"
\```

`sub_1A6228` 只做 `access(path, F_OK)==0`(不读内容、不 stat、不看 SELinux label)。25 条路径表:

| 类别 | 路径 |
|-|-|
| 投屏 | `/data/local/tmp/vysor.pwd`, `/data/local/tmp/oat/arm64/scrcpy-server.odex`, `/data/local/tmp/mqc-scrcpy.jar` |
| 触屏/操控 | `/data/local/tmp/minicap.so`, `minicap`, `mini`, `mini/minicap`, `minitouch` |
| 触动/按键精灵 | `/data/local/tmp/tc/mobileagent`, `tc/input3.sh`, `tc/mainputjar7`, `com.cyjh.mobileanjian.id`, `com.cyjh.mobileanjianen.id` |
| UI 自动化 | `/data/local/tmp/uiautomator-stub.jar` |
| 云手机/云控 | `/data/local/tmp/cloudtestig/cloudscreen`, `cloudtesting/touchserver`, `juejinAzykb/`, `juejinAzykb/TouchService.jar`, `maxpresent.jar` |
| 截屏 SO | `/data/local/tmp/screen-shread10x64.so`, `screen-shread5x32.so` |
| Shizuku | `/data/local/tmp/shizuku`, `shizuku_starter` |
| 设备信息 | `/data/local/tmp/mobile_info.properties` |
| 一键玩 | `/data/local/tmp/yijianwanservice.apk` |

伪代码:

```c
// libhunter.so+0x2AC514
jobject NativeEngine_checkRiskFile(JNIEnv *env) {
 paths = { /* 25 条上表 */ };
 for (path in paths)
 if (access(path, F_OK) == 0)
 return ReportRiskItem(env, "Find Risk File", "find risk file "+path, /*risk=*/1, /*Type=*/2, /*ShowPriority=*/10);
 return NULL;
}
\```

本设备 25 路径均不存在:

\```
[evidence:risk-file] NativeEngine_checkRiskFile entered
[evidence:risk-file] NativeEngine_checkRiskFile ret=0x0
[evidence:risk-file-java] NativeEngine.checkRiskFile -> <null>
\```

要实测命中需主动构造路径文件。bypass `checkRiskFile -> null` 或 SO 层 replace。证据等级:`△静态闭环 / 当前环境未命中`。

---

### 6.9 AVC denial 日志侧信道(检测点#16)

链路:

\```
Java: GC.run case 16 -> NativeEngine.checkRootFromAVCLog
JNI : NativeEngine_checkRootFromAVCLog @ 0x2AAE54
核心: sub_E0AA8(pid_string) @ 0xE0AA8 (size 0x2B28)
上报: callsite 0x2aaec4 (W3=0, W4=1, W5=1)
UI : "Find Root File In Sniff"
\```

包装层:

```c
// libhunter.so+0x2AAE54
jobject NativeEngine_checkRootFromAVCLog(JNIEnv *env) {
 string pid = to_string(getpid);
 if (!sub_E0AA8(pid)) return NULL;
 return ReportRiskItem(env, "Find Root File In Sniff", get_last_root_mounts_detail, ...);
}
\```

`sub_E0AA8` 算法骨架:

\```
1. logcat -c
2. 对一组 root 敏感路径,4 种探测逐一尝试:
 a) ls <path> (popen) b) open (__open_2) c) access d) getxattr(security.selinux) e) readlink
3. usleep 等 AVC 落地
4. logcat -d -b main -b system -b events -b kernel | grep 'avc: denied' | grep -Ei '(<paths>)'
5. 解析 AVC 输出 path="..." / name="..." 是否出现目标路径片段
6. 即使 access/open 都失败,只要 kernel 记录过 AVC denial,即视作命中
\```

关键 libc callee:`close / access / __open_2 / getxattr / readlink / usleep`。静态字符串:`file_include open file fail` / `checkRootFileFromAVC File` / `checkRootFileFromAVC log info ->` / `likely exists (detected via AVC denial log). Detailed log:` / `sniffing of the root file path ...`。敏感路径表(`sub_D14B0 @ 0xD14B0`):

\```
/debug_ramdisk, /debug_ramdisk/su
/data/adb/, /data/adb/modules, /data/adb/modules/
/data/adb/ap, /data/adb/ap/bin, /data/adb/ap/log,
/data/adb/ap/log/bin/{apd, magiskpolicy, magiskmount, kpatch, resetprop}
/data/adb/ap/{modules.img, package_config, su_path, version}
/data/adb/kpatch, /data/adb/magisk, /data/adb/lspd
/sbin/.magisk, /sbin/.magisk/modules/{riru_lsposed, zygisk_lsposed}
/system/bin/magisk, /system/bin/magisk32
/system/etc/init/magisk, /system/etc/init/magisk.rc
/system/addon.d/99-magisk.sh
/cache/magisk.log, /cache/.disable_magisk
apatch / Apatch / APatch
kernelsu / kernelSu
\```

实测未触发:

\```
[evidence:avc-log] NativeEngine_checkRootFromAVCLog entered
[evidence:avc-log] NativeEngine_checkRootFromAVCLog ret=0x0
[evidence:avc-log-java] NativeEngine.checkRootFromAVCLog -> <null>
\```

仅隐藏文件不够,即使 access/open 返回 ENOENT,kernel 历史 AVC denial 仍可被反推;须拦 logcat 输出 / 清 AVC entry / 内核侧阻止生成 denial。bypass `checkRootFromAVCLog -> null`。证据等级:`△静态闭环 / 未触发`。

---

### 6.10 包名 ELF 白名单扫描(检测点#17)

链路:`NativeEngine.getZhenxiInfoMPNI("com.zhenxi.hunter")` → `0x298374`,callsite `0x2994f4`(W3=0/W4=1/W5=0),UI `"Find Mark ELF"`。两阶段。阶段1 自保护硬门槛:

```c
if (byte_2F3A68 != 1 || (byte_2F3A6C & 1) == 0) {
 log: "checkProcessTag error" + "File:" + "F:/HunterNew/app/src/main/cpp/main.cpp" + Line
 log: "native kill self process"
 dump threads (sub_1A3988(pid, tid, 0, "Zhenxi"))
 log: "KILL_PROCESS"
 safe_syscall_via_trampoline(__NR_kill, pid, 9) ← 三连自杀
 abort
}
\```

泄露开发环境路径 `F:/HunterNew/app/src/main/cpp/main.cpp`。阶段2 maps 包名 ELF 白名单扫描:

```c
pkg_str = GetStringUTFChars(jpkg);
path = "/proc/" + to_string(getpid) + "/maps";
fd = ssyscall_openat(AT_FDCWD, path, O_RDONLY, 0);
maps = parse_maps_to_linked_list(-1);
for each map_node in maps:
 if !strstr_(map_node.pathname, pkg_str): continue;
 // 跳过白名单 8 项: xcrash / sentry / hunter / libc++_shared / libdatastore_shared_counter.so
 // / libBugly / /data/data/<pkg>/code_cache/ / /oat/arm64/
 if (perms[0]=='r' && start[0..3] == 7F 45 4C 46):
 detail += pathname + "\n";
if !detail.empty:
 build_native_ListItemBean_risk(env, "Find Mark ELF", detail, 0, 1, 0);
return null;
\```

实测:

\```
[evidence:mpni] NativeEngine_getZhenxiInfoMPNI entered
[evidence:mpni] NativeEngine_getZhenxiInfoMPNI ret=0x0
[evidence:mpni-java] NativeEngine.getZhenxiInfoMPNI(com.zhenxi.hunter) -> <null>
\```

正确结论:自保护标签通过,maps 包名 ELF 白名单扫描未发现额外可疑映射(非"没有该检测")。防"以 app 同包名注入额外 native 库"。bypass `getZhenxiInfoMPNI(pkg) -> null`。证据等级:`△静态闭环 / 未触发`。

---

### 6.11 APK 签名一致性(检测点#18)

链路:`NativeEngine.getZhenxiInfo2(Context)` → `0x29AEFC`,11 个 callsite(RVA `0x29d6c0..0x2a0304`,W3=0/1,W4=3,W5=3),UI `"HunterCheckApkSignError"` + 11 子原因。预期签名指纹(hardcoded):

\```
"MYAAKzWEBR" ── base64 substr 前 10 字符
"4d5941414b7a57454252" ── 上述 base64 的 hex 表示(20 字符)
\```

7 步检查链(从 11 callsite 字面量还原):

\```
1. 反射拿 APK 路径 ctx.getApplicationInfo.publicSourceDir
 失败 → "getApkPath == null" / "check apk sign apk path == null" → "HunterCheckApkSignError"
2. ssyscall_openat 打开 base.apk
 失败 → "open fd cache error";成功 → "start native open base.apk success" / "native apk sign check open fd"
3. read_certificate 提取签名 (sub_C1EF0 / sub_BCE34 zip parse + cert extract)
 失败 → "apk read_certificate empty" → "HunterCheckApkSignError"
4. base64.substr(0,10) != "MYAAKzWEBR" → "check app sign hex fail" → "HunterCheckApkSignError"
 日志 "getApkSign apk sign base64 substr"
5. hex(base64) != "4d5941414b7a57454252" → "check app sign hex fail";日志 "native check hex success"
6. /proc/self/fd/<fd> readlinkat 反查真实路径
 失败 → "readlinkat error" / "check apk sign path error";不匹配 → "check apk sign path fail"
 日志 "native apk check fd path success"
7. fstat 验 inode/uid/gid
 "check apk sign path fail __NR_fstat<0" / "fstat error" / "check apk sign gid&uid fail" / "check apk sign inode fail"
 成功 → "check apk sign success! uid->" + " gid-> " + " maps ->" + "native apk check inode&uid&gid success"
\```

`"MYAAKzWEBR"` 是 hunter APK 真实签名开头,重打包重签后这 10 字符改变即被检出。本设备官方 APK:

\```
[evidence:apk-sign] NativeEngine_getZhenxiInfo2 entered
[evidence:apk-sign] NativeEngine_getZhenxiInfo2 ret=0x0
\```

检测目标是防 hunter 自身被重打包。bypass `getZhenxiInfo2(ctx) -> null`(或确保不重打包)。证据等级:`△静态闭环 / 未触发`。

---

### 6.12 system_server hook 检测(检测点#19)

链路:`NativeEngine.getZhenxiInfoCBinder` → `0x28C9BC`,callsite `0x28cd08`(W3=0/W4=3/W5=4),UI `"find system server hook"`。伪代码:

```c
jobject NativeEngine_getZhenxiInfoCBinder(JNIEnv* env) {
 if (checkProcessTag 失败) → kill self (同 第6.10节 阶段 1)
 v2 = sub_CDFC4; // OLLVM thunk → sub_CDAD4
 sub_CE000(v15, v2); // 把 v2 处理成 std::string,放进 v15
 char v3 = sub_251C18(v15); // 解密(同 第6.0.2节 跳板的 runtime_syscall_code 解码器)
 if ((v3 & 1) != 0) { sub_CEB40; return NULL; } // 通过 = 没命中
 else {
 build_native_ListItemBean_risk(env, "find system server hook", detail, 0, 3, 4);
 return bean;
 }
}
\```

`sub_CDFC4 / sub_CDAD4 / sub_CE000` 无字符串纯 OLLVM,从上下文推断:从 binder/service 取一个值(IBinder 接口 hash / system_server 状态 / ServiceManager native binder pointer),解密后与 hardcoded 预期值比对,不匹配 → system_server 链有 hook 中转。`sub_251C18` 是跳板模块同款解密器。实测未命中:

\```
[evidence:cbinder] NativeEngine_getZhenxiInfoCBinder entered
[evidence:cbinder] NativeEngine_getZhenxiInfoCBinder ret=0x0
[evidence:cbinder-java] NativeEngine.getZhenxiInfoCBinder -> <null>
\```

检测 Binder IPC 中间是否有人(VirtualXposed / SandHook IBinder proxy)。`sub_CDFC4/CDAD4/CE000` 精确算法待补。bypass `getZhenxiInfoCBinder -> null`。证据等级:`△静态闭环 / 内部 callee 未完全还原`。

---

### 6.13 VPN 接口检测(检测点#20)

链路:

\```
Java: NativeEngine.CheckVpn
JNI : NativeEngine_CheckVpn @ 0x2AAF44 (idx=53)
入口: sub_A8BE4 @ 0xA8BE4 (NETLINK 枚举链表头)
辅助: sub_AA914 @ 0xAA914 (ctx 初始化, 0x2000 buffer)
 sub_AAA4C @ 0xAAA4C (socket + 发 dump 请求)
 sub_AB81C @ 0xAB81C (循环 recvfrom + 派发回调)
 sub_A8CC8 @ 0xA8CC8 (nlmsg 解析回调)
上报: callsite 0x2ab014 (W3=0, W4=1, W5=0)
UI : "Find Vpn Native"
\```

算法骨架:

\```
NETLINK socket(AF_NETLINK=16, SOCK_RAW|SOCK_CLOEXEC=0x80003, NETLINK_ROUTE=0)
顺序发两条 dump:type=18 RTM_GETLINK → type=22 RTM_GETADDR,nlmsghdr flags=0x301
recvfrom 走 safe_syscall_via_trampoline(207, fd, buf, 0x2000, 0, 0, 0)
sub_A8CC8 回调:
 type=16 RTM_NEWLINK → operator new(0x1D8) 新节点,扫 rtattr 找 IFLA_IFNAME(rta_type=3) 拷到 node+448,头插链表
 type=20 RTM_NEWADDR → 按 ifa_index 匹配已建链表
for node in head:
 if my_strcmp(name,"tun")==0 || my_strcmp(name,"ppp")==0 || my_strcmp(name,"pptp")==0:
 build_native_ListItemBean_risk(env, "Find Vpn Native", name, /*risk=*/0, /*Type=*/1, /*ShowPriority=*/0); return bean
return NULL
\```

链表节点 `struct LinkNode { next@+0x00; name@+0x08(=&this[0x1C0]); flags@+0x10; ifindex@+0x38; name_buffer[24]@+0x1C0; }`,总 size 0x1D8。动态(`verify_4_7_checkvpn.js`,无 VPN/WiFi 已连)实测对照:

\```
[S2] socket(AF_NETLINK=16, type=0x80003 ✓SOCK_RAW|SOCK_CLOEXEC, proto=0 ✓NETLINK_ROUTE)
[S3] 一次 CheckVpn 调用内 50 帧 RTM_NEWLINK(=16) 后 7 帧 RTM_NEWADDR(=20)
[S7] 50 个接口 IFLA_IFNAME 全部正确解出,与 ip link 一致
[S8] 7 次 RTM_NEWADDR 全部正确关联 (lo×2, dummy0×1, wlan0×4)
[S9] 设备存在 tunl0(ipip tunnel,前 3 字符="tun") 但 CheckVpn return 0x0 ← my_strcmp 精确比较硬证据
[S11] return = 0x0 ✓ NULL
\```

设备完整接口快照(50 个全被扫到,真实 kernel 接口表未被 `/proc/net/dev` 欺骗):

\```
lo, dummy0, ifb0, ifb1, tunl0, gre0, gretap0, erspan0,
ip_vti0, ip6_vti0, sit0, ip6tnl0, ip6gre0,
rmnet0..rmnet29 (Qualcomm modem),
dummy (额外), aware_nmi0, wlan0, wlan1, wpan0, dit0, radiotap0
\```

`tunl0` 前 3 字符是 `"tun"` 但没命中,等价 `strcmp("tunl0","tun")!=0`。实现弱点(详 第6节.终.缺陷 #4):`my_strcmp` 精确比较 + 仅 3 个裸字符串 `tun/ppp/pptp`,真实 VPN 接口几乎都是 `tun0/ppp0/wg0/xfrm0`,存在明显漏检风险。S4/S5(发送方向 flags=0x301)本轮未 hook,诚实标"未验证"。本会话也观察到 `+0xc68a4`(sub_C687C)×2、`+0xc7828`(scan_rx_segment_neon_sum)×2,与 CheckVpn 无关,加强两条独立完整性链路论断。bypass:hook 入口 return 0 / hook sub_A8CC8 改写 name / KPM netlink 侧 filter / 不动(用户场景 OpenVPN/WireGuard 接口名本就不裸叫 tun/ppp/pptp)。证据等级:`✓闭环`。

---

### 6.14 Frida 线程名扫描 + buffered reader bug(检测点#21)

链路:

\```
Java: NativeEngine.getZhenxiInfo5(Context)
JNI : NativeEngine_getZhenxiInfo5 @ 0x2A4760 (idx=2)
核心: sub_C6A84 @ 0xC6A84 (线程扫描)
辅助: strstr_ @ 0x1AFD4C / ssyscall_openat / ssyscall_read / ssyscall_close
上报: 3 callsite,W3=0, W4=2, W5=8
UI : "Find Frida Mark" / "gum-js-loop" 或 "gmain"
\```

`sub_C6A84` 完整伪代码:

```c
int sub_C6A84(void) {
 DIR* dirp = opendir("/proc/self/task");
 if (!dirp) return -1;
 int n2 = 0;
 for (each readdir entry) {
 if (d_name == "." or "..") continue;
 char buf[256];
 snprintf(buf, 256, "/proc/self/task/%s/status", d_name);
 int fd = ssyscall_openat(AT_FDCWD, buf, O_RDONLY, 0);
 if (fd < 1) continue;
 char ptr[256]; memset(ptr, 0, 256);
 size_t n255 = 0;
 size_t v9 = qword_2EFCB8; // GLOBAL cursor
 size_t v10 = qword_2EFCC0; // GLOBAL end
 while (n255 != 255) {
 if (v9 >= v10) {
 v10 = ssyscall_read(fd, &ptr_, 1024); // GLOBAL buffer
 qword_2EFCB8 = 0; qword_2EFCC0 = v10;
 if (v10 < 1) break;
 v9 = 0;
 }
 uint8_t c = ptr_[v9++];
 qword_2EFCB8 = v9;
 if (c == '\n') break;
 ptr[n255++] = c;
 }
 ssyscall_close(fd);
 if (strstr_(ptr, "gum-js-loop")) { n2 = 1; break; }
 else if (strstr_(ptr, "gmain")) { n2 = 2; break; }
 }
 closedir(dirp);
 return n2;
}
\```

三个全局 buffered reader 状态(`.bss`):`ptr_ @ 0x2EF8B8`(1024B buffer)、`qword_2EFCB8`(cursor)、`qword_2EFCC0`(end),这三个状态跨 tid 迭代从不重置,是 bug 源头。`getZhenxiInfo5` 分发:

| `sub_C6A84` 返回 | 分支 | callsite | title / detail | 自杀? |
|-|-|-|-|-|
| `2` | gmain 命中 | `0x2a5204` | "Find Frida Mark" / "gmain" | 三连 `safe_syscall(129=kill, pid, 9)` |
| `1` | gum-js-loop 命中 | `0x2a47f4` | "Find Frida Mark" / "gum-js-loop" | 仅上报 |
| 其它 `0`/`-1` | 无命中 | `0x2a5470` | OLLVM 解码 `<dyn>`,detail 空 | — |

第二轮决定性证据(`verify_4_9_v2_read_count.js`):`sub_C6A84` 一次调用内 `ssyscall_read` **仅触发 2 次**(77 tid 预期应数十次):

\```
read #01 fd=171 ret=1024 head="Name:\ter_main_process\nUmask:\t0077\nState:\tR (running)\nTgid:\t5491..."
read #02 fd=171 ret=1024 head="Name:\tmali-cmar-backe\nUmask:\t0077\nState:\tS (sleeping)\nTgid:\t5491..."
\```

两次 fd 都是 `171`,不是同一 tid(Linux close 后开 open 复用最低空闲 fd)。buffered reader 跨 fd 不重置的运行展开:

| 阶段 | 行为 | cursor 变化 |
|-|-|-|
| tid #1 | open(fd=171)→read 1024B→解出首行 `Name:\ter_main_process\n`→close | 0 → ~22 |
| tid #2 | open(fd=171 reused)→cursor(22)<end(1024)→**不 read**→消费残留 22..32 = `Umask:\t0077\n`(**非该 tid 数据**)→close | 22 → ~32 |
| tid #3..~#30 | 持续消费第一次 read 残留 ~1000 字节 | 32 → ~1024 |
| ~tid #30 | cursor 到 1024→read 触发(read#2),fd=171 此时属 mali-cmar-backe | 1024 → 0 |

净效果:77 tid 中实际只有 ~2 个 Name 字段被真扫(`er_main_process` / `mali-cmar-backe`),其余从未触达 `strstr_`,显著降低 `gum-js-loop`/`gmain` 命中概率。第一轮 F8(Frida 在跑但 `sub_C6A84` 返 0)只是必要不充分;第二轮查明原因。本轮 bug 已显著降低命中概率,当前脚本未专门绕 Info5 也未触发风险项;若后续版本每次 open 后重置 cursor/end,需单独处理 `sub_C6A84` / `strstr_` / `/proc/self/task/*/status` 读取面。证据等级:`✓闭环(含 bug)`。

---

### 6.15 模拟器 / 容器检测

#### 6.15.1 模拟器 OpCode/Env/Mount 检测 `getZhenxiInfoO`(字典级)

`getZhenxiInfoO @ 0x2BE8EC` 5 callsite(`0x2bec24..0x2bf71c`,W3=0/W4=2/W5=11),title 候选 **"Find Simulator OpCode Mark!"** / **"Find Simulator Env Mark!"** / **"Find Simulator Mount Mark!"**。未细做。证据等级:`字典级 / 未细拆`。

#### 6.15.2 容器/模拟器 mount marker(经 `getZhenxiInfoK`,检测点#14)

`docker / lxc_volumns`(容器)与 12 项模拟器共享目录路径(`/vboxsf` / `/bst.conf` / `/mumu_hardware.conf` 等),经通用 helper `getZhenxiInfoK` → `file_contains_any_marker`,实测见 第6.7.2节。证据等级:`✓闭环`。

---

### 6.16 注册表内其余 detection(字典级)

| UI/title 候选 | Java 入口 | Native RVA | callsite | (W3,W4,W5) | 状态 |
|-|-|-|-|-|-|
| `Mem Find Mark` / `Check App Sign Error From Path Lib` / `Insufficient permissions` | `getZhenxiInfo0` | `0x2BFDD0` | 6 callsite `0x2c00d4..0x2c15d8` | (0/1,3,3/4) | 字典级 / 未细拆 |
| `Find Linker Is Hook` / `Check Linker Crc Error` | `getZhenxiInfoL` | `0x2A8724` | 2 callsite `0x2a87b8 / 0x2a91c8` | (0/1,3,10) | 字典级 / 未细拆 |
| `Zygote Check Find Risk Mark` | `checkFromZygote` | `0x2ABCD0` | 1 callsite `0x2ac0f8` | (0,1,0) | 字典级 / 未细拆 |
| Zygisk 相关 `<dyn>` | `checkZygisk` | `0x2A93F8` | 1 callsite `0x2a9690` | (0,2,0) | 字典级 / 未细拆 |
| `getZhenxiInfoVV` `<dyn>` | `getZhenxiInfoVV` | `0x2C1850` | `0x2c2854` | (0,3,4) | 字典级 / 未细拆 |
| `getZhenxiInfo6` `<dyn>` | `getZhenxiInfo6` | `0x2A5544` | 2 callsite `0x2a6084 / 0x2a6294` | (0/1,2/3,9) | 字典级 / 未细拆 |
| `getZhenxiInfo7` `<dyn>` | `getZhenxiInfo7` | `0x2A636C` | 2 callsite `0x2a65ec / 0x2a662c` | (0/1,3,7) | 字典级 / 未细拆 |
| `getZhenxiInfoSH` | `getZhenxiInfoSH` | `0x28D578` | — | — | 字典级 / 未细拆 |

#### 6.16.1 反 hook 全家桶 `getZhenxiInfoBase`(字典级)

`getZhenxiInfoBase @ 0x29288C` 19 callsite(`0x292e18..0x2952a4`,W3=0/W4=1/2/3/W5 多种),是"全家桶":Linker Hook / Magisk / Mount / Seccomp / Signal / Uname 等多类检测打包在一个 JNI 入口。title 候选:

\```
"Linker Find Hook Mark" / "lsposed" / "zygisk" / "Find Prop Modify Mark" /
"Find Hook Mark" / "Base Check Inline Flag" / "Find Mnt Mark" /
"Find Magisk Modules Mark" / "Seccomp Check Arch Find Mark" /
"Check Signal Not Match" / "Check Uname Spoofing"
\```

未逐 callsite 对回。证据等级:`字典级 / 待拆`。

---

#### 6.终.多进程 Binder 上报机制(检测点#22)

即使主进程检测入口已 bypass,子进程仍可能通过 Binder 把 `ListItemBean` 传回主进程 UI。Manifest:

```xml
<service android:name=".ZhenxiServer"
 android:process=":hunter_server_iso"
 android:isolatedProcess="true"/>
<service android:name=".ZhenxiServerTwin"
 android:process=":hunter_server_twin"
 android:useAppZygote="true"/>
\```

主进程三层 bypass 全装后仍有 `Check Find Root In Mounts` 漏网,UI 兜底打出 Java 栈:

\```
[java:ui:TRACE] first hit needle="Check Find Root" title="Check Find Root In Mounts "
java.lang.Exception
 at com.zhenxi.hunter.MainActivity.n0(Native Method)
 at YouAreLoser.TC.v(Unknown Source:2)
 at YouAreLoser.TC.onTransact(Unknown Source:54)
 at android.os.Binder.execTransactInternal(Binder.java:1391)
 at android.os.Binder.execTransact(Binder.java:1335)
\```

`[ReportRisk]` 行未出现——这条 risk 未经主进程 `0x278658` 汇聚点。`YouAreLoser.TC` 是 AIDL stub,`onTransact` 解包后 `TC.v(bean) -> MainActivity.n0(bean)`。同一 detection data 前缀区分主进程 / 隔离进程:

\```
[evidence:ui] title=Check Find Root In Mounts data=com.zhenxi.hunter:hunter_main_process
[evidence:ui] title=Check Find Root In Mounts data=com.zhenxi.hunter:hunter_server_iso:com.zhenxi.hunter.ZhenxiServer:hunter_iso_service
\```

子进程独立加载 libhunter.so 跑一遍 detection,结果 Binder 传回。Frida 默认只 attach 主进程,子进程 SO 层 hook 未装。三种下沉方案:A UI 兜底 `MainActivity.n0` 按 title 名单丢弃(实测可用);B `TC.v`/`TC.onTransact` Binder 层丢弃;C 多进程 spawn(`--enable-spawn-gating`)让子进程也装 hook(最彻底但调试复杂)。证据等级:`✓闭环`。

#### 6.终.已确认实现缺陷(检测点#23)

KPM 设计**不应**依赖这些缺陷做长效绕过(作者修起来都很容易):

| # | 缺陷 | 位置 | 静态证据 | 动态证据 | 修复成本 |
|-|-|-|-|-|-|
| 1 | `maps_precheck_readable` 不验证目标范围全被可读 mapping 覆盖,unmapped hole 误判可读 | `0xC6520` | 函数体只检查"重叠且 perms[0]!='r'" | `block_bad_precheck` 多次拦下 `addr=0x7741a35000 size=0x1266d8 off 0xc7828` 等越界(第6.2节/第6.0.4节) | ~5 行 C |
| 2 | `sub_C6A84` buffered reader(`ptr_/qword_2EFCB8/CC0`)跨 fd 不重置 | `0xC6A84` | 三个全局 .bss 在 fd 迭代中从不重置(IDA xref) | 77 tid 实际只触发 2 次 `ssyscall_read`,Frida gum-js-loop 漏检(第6.14节) | 2 行,每次 open 后重置 cursor/end |
| 3 | `art_register_natives_batch` SDK 31-33 路径 `ClassLinker::RegisterNative` 的 `Thread*` 错传成函数指针(未调 `CurrentFromGdb`) | `0xA5254` | asm `MOV X1, X21`(X21=dlsym 函数指针,未调) → `BLR X8`;SDK>33 显式禁用一致 | SDK=35 走 RegisterNatives 回落,`verify_register_natives.js` 间接印证 | 1 行,补 `((Thread*(*))CurrentFromGdb)` |
| 4 | `CheckVpn` 用 `my_strcmp` 精确比较 + 仅 3 个裸字符串,`tun0/ppp0/wg0/xfrm0` 漏检 | `0x2AAF44` | `my_strcmp` = strcmp 等价;名单只有 `tun/ppp/pptp` | 设备 `tunl0` 存在但不命中,return 0(第6.13节) | 2-3 行,改 strncmp 或扩名单 |

KPM 原则:优先基于数据源的内核侧对抗(隐藏文件 / procfs、maps、netlink 返回 / 过滤 syscall 读写 / 阻断 SELinux audit),而非利用 hunter 自己的 bug;拦 detect 函数入口仍要面对 第6.2节 CRC 链。

#### 6.终.检测点总表(检测点#24)

| UI/日志标题 | Java 入口 | Native RVA | 内部核心 RVA | 闭环度 |
|-|-|-|-|-|
| `Check Find Root In Mounts` | `getZhenxiInfo3` | `0x2B476C` | `0xD5E34` 读 6 源 + 18 marker | ✓闭环 |
| `Check Find Root Permission` | `getZhenxiInfo3` | `0x2B476C` | `0xDDB9C` `/proc/mounts`·mountinfo·maps + df 扫描(netlink 探针另在 `0xE34AC`) | ✓闭环 |
| `find libart.so hooked` | `getZhenxiMapCheck` | `0x291858` | size==0x1000 / count>=6 双判 | ✓闭环 |
| `ISO CRC NOT MATCH LOCALITY CRC` | `getZhenxiLoctionCrc`+`ig.apply` | `0x2AE064` | `0xC8670` RX 段 NEON sum + Java 比较 | ✓闭环 |
| `检测到libart.so被修改` 等 | `getZhenxiInfoF` | `0x2AD9A8` | `0xC9130 / 0xC90A0 / 0xC89BC` | ✓闭环 |
| `Hunter Find Unknown Exec Item From Mian` | `getZhenxiInfoInjection` | `0x28DF24` | `0x100AAC` + 5 子检测 | ✓闭环 |
| `Find Others Process` | `getZhenxiInfo4` | `0x2A2D98` | `/proc/<pid>/comm` + `popen("ps -ef")` | ✓闭环 |
| `Check Root For SideChanne` | `SideChanne` | `0x2B3BD4` | `0xE43BC` timing ratio | ✓闭环 |
| `当前手机已经被解锁` | `z5.b` / `j40.a` getprop | Java 主导 | TEE rootOfTrust + `ro.boot.verifiedbootstate` | ✓闭环 |
| `Find Verified Boot Mark` | `z5.b` | Java 主导 | `e.b == 1/2/3` | ✓闭环 |
| `Get Env Info` | `getZhenxiInfoEnv` | `0x28CDB0` | 遍历 environ | ✓闭环 |
| `当前手机可能是模拟器&云手机` | `getZhenxiInfoK` | `0x2B93BC` | path × markers 逐行匹配 | ✓闭环 |
| `Find Vpn Native` | `CheckVpn` | `0x2AAF44` | `0xA8BE4` NETLINK_ROUTE + my_strcmp | ✓闭环 |
| `Find Frida Mark` | `getZhenxiInfo5` | `0x2A4760` | `0xC6A84` buffered reader 扫线程名 | ✓闭环(含 bug) |
| `Find Risk File` | `checkRiskFile` | `0x2AC514` | 25 条 `/data/local/tmp/*` access | △静态闭环/未触发 |
| `Find Root File In Sniff` | `checkRootFromAVCLog` | `0x2AAE54` | `0xE0AA8` logcat avc:denied 侧信道 | △静态闭环/未触发 |
| `Find Mark ELF` | `getZhenxiInfoMPNI` | `0x298374` | 进程标签自保护 + maps 包名 ELF 白名单 | △静态闭环/未触发 |
| `HunterCheckApkSignError` 多种 | `getZhenxiInfo2` | `0x29AEFC` | path/cert/base64/hex/fd readlink/fstat 7 步 | △静态闭环/未触发 |
| `find system server hook` | `getZhenxiInfoCBinder` | `0x28C9BC` | `sub_CDFC4/CDAD4/CE000/251C18`(纯 OLLVM) | △静态闭环/callee 未还原 |
| ROM 属性多种 | `getZhenxiInfoH(key)` | Java wrapper(不在 batch) | `getPropInline`:`getZhenxiInfoZ` / `/dev/__properties__` | ✓链路已收敛 |
| `Find Simulator OpCode Mark!` 等 | `getZhenxiInfoO` | `0x2BE8EC` | `0x2bec24..0x2bf71c` 5 callsite 4 子类 | 字典级/未细拆 |
| `Linker Find Hook Mark` 等 19 类 | `getZhenxiInfoBase` | `0x29288C` | 19 callsite 全家桶 | 字典级/待拆 |
| `Mem Find Mark` 等 | `getZhenxiInfo0` | `0x2BFDD0` | 6 callsite APK lib mem | 字典级/未细拆 |
| `Find Linker Is Hook` 等 | `getZhenxiInfoL` | `0x2A8724` | 2 callsite | 字典级/未细拆 |
| `Zygote Check Find Risk Mark` | `checkFromZygote` | `0x2ABCD0` | 1 callsite | 字典级/未细拆 |
| Zygisk 相关 | `checkZygisk` | `0x2A93F8` | 1 callsite `<dyn>` | 字典级/未细拆 |
| `Check Maps Find Hide` | `sub_2A1C38` | `0x2A1C38` | 2 callsite | 字典级/未细拆 |

闭环度统计:`✓闭环` 14+(第6.1节/6.2/6.3/6.4/6.5/6.6/6.7/6.13/6.14 + 多进程);`△静态闭环/未触发` 5(checkRiskFile / checkRootFromAVCLog / getZhenxiInfoMPNI / getZhenxiInfo2 / getZhenxiInfoCBinder);`字典级` 多条(InfoBase 19 callsite、InfoO 5 子类、Info0/InfoL/checkFromZygote/checkZygisk/sub_2A1C38)。

#### 6.终.D 完整 60 项 `off_2EF1F0` 注册表(IDA MCP `get_bytes(0x2EF1F0, 1440)` 实读)

\```
#00 getZhenxiInfo2 (Landroid/content/Context;)L..ListItemBean; 0x29aefc
#01 getZhenxiInfo4 (Landroid/content/Context;)L..ListItemBean; 0x2a2d98
#02 getZhenxiInfo5 (Landroid/content/Context;)L..ListItemBean; 0x2a4760
#03 getZhenxiInfo6 (Landroid/content/Context;Ljava/lang/String;)L..; 0x2a5544
#04 getZhenxiInfo7 (Landroid/content/Context;)L..ListItemBean; 0x2a636c
#05 getZhenxiInfo8 V 0x2a66ac
#06 getZhenxiInfo9 V 0x299640
#07 getZhenxiInfoE V 0x2ae010
#08 getZhenxiInfoF L..ListItemBean; 0x2ad9a8 ← checksum
#09 getZhenxiInfoL L..ListItemBean; 0x2a8724 ← Linker hook
#10 getZhenxiInfoM ([Ljava/lang/Class;Z)[[Ljava/lang/Object; 0x2b7f9c
#11 getZhenxiInfoO (Landroid/content/Context;)L..ListItemBean; 0x2be8ec ← 模拟器
#12 getZhenxiInfo1 [Ljava/lang/String; 0x2b5224
#13 getZhenxiInfo3 L..ListItemBean; 0x2b476c ← /proc/mounts root
#14 getZhenxiInfoC (I)V 0x2a77a8
#15 getZhenxiInfoZ (Ljava/lang/String;)Ljava/lang/String; 0x2b34a8 ← prop native fallback
#16 getZhenxiInfoP Z 0x2b1af8
#17 getZhenxiInfoQ Z 0x2b244c
#18 getZhenxiInfoI (Ljava/lang/String;)I 0x2bdc70
#19 getZhenxiInfoT V 0x2b8a14
#20 getZhenxiInfoK (Ljava/lang/String;[Ljava/lang/String;)L..String; 0x2b93bc ← 通用文件 marker
#21 getZhenxiInfoXX Ljava/util/ArrayList; 0x2bbb98
#22 getZhenxiInfoLL (Ljava/lang/String;)Ljava/util/ArrayList; 0x2ba438
#23 popen (Ljava/lang/String;)Ljava/lang/String; 0x2ae400
#24 popen_list (Ljava/lang/String;Ljava/lang/String;)L..ArrayList; 0x2b01d4
#25 getZhenxiLoctionCrc Ljava/util/HashMap; 0x2ae064 ← 模块 CRC
#26 getZhenxiInfoVV L..ListItemBean; 0x2c1850
#27 getZhenxiInfo0 (Ljava/lang/String;)L..ListItemBean; 0x2bfdd0 ← APK lib mem
#28 getZhenxiInfoMark V 0x2c29f4
#29 getZhenxiInfoMM Z 0x2b1f88
#30 getZhenxiInfoAtt V 0x2c30a8
#31 getZhenxiInfoNHIL Ljava/util/ArrayList; 0x289e94
#32 getZhenxiInfoHMP (Ljava/util/ArrayList;Ljava/lang/String;)V 0x289db8
#33 getZhenxiInfoMPNI (Ljava/lang/String;)L..ListItemBean; 0x298374 ← 包名 ELF 白名单
#34 getZhenxiInfoLLLI Ljava/util/ArrayList; 0x28d44c
#35 getZhenxiInfoOFLI Ljava/util/ArrayList; 0x297790
#36 getZhenxiInfoSH L..ListItemBean; 0x28d578
#37 getZhenxiInfoEnv L..ListItemBean; 0x28cdb0 ← 环境变量
#38 getZhenxiInfoCBinder L..ListItemBean; 0x28c9bc ← system_server hook
#39 getZhenxiInfoMapELF Ljava/util/ArrayList; 0x290958
#40 getZhenxiInfoInjection Ljava/lang/String; 0x28df24 ← 匿名 RWX
#41 getZhenxiInfoApkEnv L..ListItemBean; 0x2a1dac
#42 getZhenxiInfoOFRL Ljava/util/ArrayList; 0x295878
#43 getZhenxiInfoBase Ljava/util/ArrayList; 0x29288c ← 全家桶 19 callsite
#44 runInZygisk V 0x291690
#45 getZhenxiMapCheck L..ListItemBean; 0x291858 ← libart maps 分片
#46 check_jvm_method (Ljava/lang/reflect/Method;)Ljava/lang/String; 0x2ad350
#47 getZhenxiInfoTwin (I)V 0x2a6e70
#48 getZhenxiInfoTwinStart Z 0x2b28dc
#49 DetectHardwareBreakpoints V 0x2ad0b4
#50 checkRiskFile L..ListItemBean; 0x2ac514 ← 25 条 /data/local/tmp
#51 checkFromZygote Ljava/util/ArrayList; 0x2abcd0
#52 initHunterBase (Landroid/content/Context;)V 0x2ab0a4
#53 CheckVpn L..ListItemBean; 0x2aaf44 ← VPN NETLINK
#54 checkZygisk L..ListItemBean; 0x2a93f8
#55 getCPUFingerprinting Ljava/lang/String; 0x2a92a0
#56 checkRootFromAVCLog L..ListItemBean; 0x2aae54 ← AVC 侧信道
#57 getLibBaseInfo Ljava/lang/String; 0x2a9764
#58 MD5 (Ljava/lang/String;)Ljava/lang/String; 0x2b4fbc
#59 SideChanne Ljava/lang/String; 0x2b3bd4 ← APatch/KP timing
\```

返回类型以 `ListItemBean`(单条风险项,主力 detection)、`ArrayList`(风险/信息列表)、`String`(prop/marker/注入/指纹/MD5/SideChanne/popen)为主,另有 `V`(初始化/状态修改)、`Z`(状态查询),以及 `HashMap`(getZhenxiLoctionCrc)/`I`/`[String`(getZhenxiInfo1 uname)/`[[Object`(getZhenxiInfoM 反射)/`(Context)V`(initHunterBase)各 1(逐项以上方 60 项表为准)。`getZhenxiInfoH` 不在表内(Java wrapper → getPropInline → getZhenxiInfoZ / `/dev/__properties__`)。

#### 6.终.关键 RVA 速查表(附录 B 节选)

\```
JNI_OnLoad 0x2c36f8 / art_register_natives_batch 0x0a5c54 / art_method_set_native_entry 0x0a4c80
SDK31-33 BUG callsite 0x0a5254 / safe_syscall_via_trampoline 0x248cc4 / InitSecureTrampolinePage 0x1b22c0
FindLinkerSyscallAddr 0x1b1c9c / calc_additive_checksum 0x261f14 / build_native_ListItemBean_risk 0x278658
maps_precheck_readable 0x0c6520 / file_contains_any_marker 0x1a6300
anti_inject_collect_results 0x0c8670 / scan_modules_for_path 0x0c8500 / parse_elf_rx_segments 0x0c6f14
scan_rx_segment_neon_sum 0x0c772c / check_libc/libart/linker64_elf_checksum_status 0x0c90a0/0x0c9130/0x0c89bc
task_MAIN_CRC_check 0x2d6804
detect_root_mark_in_proc_mounts_maps 0x0d5e34 / build_mount_markers(18 项) 0x0d116c
detect_root_side_channel_apatch_kernelsu 0xe43bc / sub_C6A84(Frida 线程) 0x0c6a84
sub_E0AA8(AVC 侧信道) 0x0e0aa8 / sub_D14B0(AVC 路径) 0x0d14b0 / sub_1A6228(access F_OK) 0x1a6228
sub_A8BE4(NETLINK VPN 入口) 0x0a8be4 / sub_A8CC8(nlmsg 回调) 0x0a8cc8 / strstr_ 0x1afd4c
数据结构: off_2EF1F0(60 项表)/ qword_2EF8B0(elf cache)/ qword_2EFCB8(reader cursor)/ qword_2EFCC0(reader end)
 ptr_@0x2EF8B8(1024B buffer)/ xmmword_2F09E8("(runtime_syscall_code")/ byte_2F3A68(PROCESS_TAG)
 byte_2F3A6C(OnLoad 标记)/ g_sdk_level dword_2F0880
\```

---

## 七、深度逆向(二)ZygiskDetector(wu.Zygisk.Detector)

>
> 样本:`ZygiskDetector_1.7.5.apk`,运行包名 `wu.Zygisk.Detector`。
> 与 RiskDetector/Hunter/Garuda 不同,本检测器**没有自有 native `.so` 检测库**。检测主路径完全在
> Java/MVEL 脚本层:`assets/MUS.LOVE`(Java 序列化对象图 + 内嵌 MVEL2 表达式 AST)被反序列化为
> `LOVES` 页面表,`assets/util.dex` 运行时释放并由 `DexClassLoader` 加载,脚本通过 `com.wuying.*`
> 辅助类执行 shell / 读 /proc / 算哈希 / 解零宽字符串。
> 证据等级:**Confirmed**=静态证据与动态日志一致;**Static only**=反编译/脚本产物支持但当前运行
> 未触发;**Dynamic only**=运行日志观察到但静态结构未完全还原;**Inferred / 【推断】**=由上下文/AST 结构
> 推断,公式未 100% 锤死;**【实测】**=运行期数值佐证。
> 本章按"先实证文件格式 → 解释器 → 放行门 → mainpage 深层结构块 → su 当前唯一墙 → 变量归类 → 对抗
> 落地 → 残留未确认"的顺序展开。引用位置直接给到工程路径。
>
>
>

---

### 7.1 检测载体:这是一份"序列化的低代码程序",不是 native,不是源码

ZygiskDetector 的核心保护方式不是把检测逻辑编译成不可见的 native 逻辑,而是把规则**数据化**后交给
Java 层解释器执行。这就是为什么 JADX 反编译 `classes.dex` 看不到检测规则——规则不在 Java 方法里,
而是作为序列化**数据**存在,必须让 app 自己 `readObject` 后再从内存 dump。

总体数据流:

\```
APK 启动
 -> com.eide.eideapp.Application / RunnerActivity
 -> Utils.parseLoves(context)
 -> assets/MUS.LOVE 反序列化为 LOVES 页面/脚本对象
 -> RunnerActivity 按页面创建 Executor
 -> Executor 执行 LOVES 中的指令数组
 -> 运行时释放并加载 assets/util.dex
 -> 脚本调用 com.wuying.* 辅助类
 -> 读取 /proc、执行 shell、计算 APK/DEX 哈希、扫描 maps/smaps
 -> 写入 injected/hooked/rwx/frida/zygisk 等变量
 -> 组合 code/reason
 -> UI 渲染 Error/Reason/Code 或通过状态
\```

#### MUS.LOVE 文件头魔数(实证,Confirmed)

`xxd assets/MUS.LOVE | head`:

\```
00000000: aced 0005 7372 0011 6a61 7661 2e75 7469 ....sr..java.uti
 6c2e 4861 7368 4d61 70 l.HashMap
00000050: ...74 0008 6d61 696e 7061 6765 t..mainpage
\```

解码:

\```
AC ED 00 05 = Java 序列化流魔数 STREAM_MAGIC(版本 5)
73 72 = 'sr' = TC_OBJECT / TC_CLASSDESC,声明顶层对象是 java.util.HashMap
74 00 08 "mainpage" = TC_STRING(长度 8),即顶层 HashMap 的一个 page key
\```

#### 顶层结构 = 页面表 `HashMap<页面名, Object[][]>`(Confirmed)

\```
顶层 java.util.HashMap 的 key = 页面名: main / mainpage / blacklist / denied
value 在流中类型 = [[Ljava.lang.Object; (Object[][] 指令数组)
单条指令 = Object[5]:
 [opcode, 参数, 条件/表达式, 目标变量, 源码行号]
\```

#### 条件/表达式 = 预编译的 MVEL2 AST 对象(Confirmed)

`strings assets/MUS.LOVE` 命中以下类名:

\```
org.mvel2.compiler.ExecutableAccessor
org.mvel2.ast.BinaryOperation / BooleanNode / And / ASTNode
org.mvel2.ParserContext
\```

指令里的条件不是明文字符串,而是序列化的 **MVEL2**(MVFLEX Expression Language)编译节点。
`ExecutableAccessor.value=` 携带的就是 `((count < 50) && zygisk)` 这类表达式。

#### 加载与解释它的代码(静态反编译实证,Confirmed)

| 位置 | 作用 |
|-|-|
| `src/com/eide.eideapp/util/Utils.java:347` | `private static Map LOVES;` —— 运行时持有反序列化后的程序 |
| `src/com/eide.eideapp/util/Utils.java:1535` | `parseLoves(Context)` —— 把资产 `MUS.LOVE` 反序列化进 `LOVES`(调用链被混淆包装) |
| `src/com/eide.eideapp/util/Executor.java:1197` | `new ObjectInputStream(inputStream)` → `readObject` |
| `src/com/eide.eideapp/util/Executor.java:5980` | `getValue(Object[])` —— 操作数求值器(操作数标签 0..6) |

结论:`MUS.LOVE` 是低代码 Android 可视化构建器 `com.eide.eideapp`(EIDE)的"已编译程序",以 Java
序列化对象图存储,内嵌 MVEL2 作为表达式引擎;`MUS.LOVE` 只是该序列化程序的资产文件名(解释器内部
称 `LOVES`)。`RunnerActivity` 维护全局/页面变量表 `appVarMap`、`pageVarMap`,通过 `getPageExecutor(int)`
从页面脚本 `Object[][]` 创建 `Executor`。

---

### 7.2 还原方法:借 app 自己反序列化,从内存 dump AST

直接从 `MUS.LOVE` 文件硬解析需要先解决序列化对象格式、类定义、混淆类型和 MVEL 对象结构;运行时 Hook
绕开这些——等 app 把对象装配好以后,直接从 `Utils.LOVES` 取出最终语义对象。

Hook 反序列化完成点(`hook/dump_mus_love_ast.js`):

\```
- Hook android.app.Application.attach(Context),拿到 app ClassLoader
- 用这个 ClassLoader 访问 com.eide.eideapp.util.Utils
- Hook Utils.parseLoves(Context),在原方法返回后读取静态字段 Utils.LOVES
- 启动若没自然触发,则 fallback 主动调用 Utils.parseLoves(context)
- Java 反射递归遍历 LOVES,输出 [AST] 行
\```

AST 行格式:

\```
[AST] LOVES[page][...path...] KIND detail
\```

节点种类:`MAP`(顶层页面表)/`ARRAY`(指令数组,多为 Object[][] 或 Object[])/`OBJECT`(普通
Java/MVEL 对象,`ExecutableAccessor.value=` 往往是条件表达式源码)/`LEAF`(字符串、整数、布尔等叶子,
变量名、opcode、常量常在此)/`FIELD`/`REF`(对象引用复用,后续建 id→value 映射)/`LIMIT`、`DEPTH_LIMIT`、
`ARRAY_TRUNCATED`(dump 不完整,需 focused dump)。

路径是稳定锚点,例如:

\```
LOVES[main][3][0][1][1][2][30] # main 页面某指令数组的第 30 条指令
# page=main base=LOVES[main][3][0][1][1][2] declaredLength=221 parsedInstructions=221
\```

`main` 页面解析出 221 条指令(declaredLength=221 / parsedInstructions=221,Confirmed)。
`missing_or_truncated != 0` 时完整性不可信,需重新 dump。

操作码证据等级:`getValue` 操作数标签 0..6 为 Confirmed;
语句操作码大部分 Confirmed/Strong,`op11/33/55/69` 为 Inferred;语句调度器本身受 smali 级控制流平坦化
阻断,**未做字节码证明级符号执行**。

---

### 7.3 util.dex 释放路径、Executor/Utils 解析、CryUtil 零宽编码

#### util.dex 释放路径(Dynamic,Android 13 运行记录)

`assets/util.dex` 会释放为:

\```
/data/user/0/wu.Zygisk.Detector/files/dex/a5e79f160201b3eef3d4b2b6fc28e893.dex
\```

`com.wuying.*` 辅助类(`src/com/wuying/*`,Confirmed):

\```
CommandExecutor.executeCommand(Context, String) -> Runtime.getRuntime.exec,返回 stdout
FileUtil.start -> 递归枚举目录
Cut.cutFromString(path, marker) -> 按 marker 切割文件内容,用于 maps/smaps 局部提取
CryUtil.decrypt -> 零宽字符串解码,恢复隐藏常量
\```

#### CryUtil 零宽编码解码表(Confirmed,静态代码确认)

`com.wuying.CryUtil` 将 U+200B/U+200D 零宽字符映射成二进制并 UTF-8 解码
:

\```
U+200B -> 二进制 '0'
U+200D -> 二进制 '1'
每 8 bit -> 合成一个字节
最后按 UTF-8 输出字符串
\```

已确认解出的关键常量(`mainpage` maps 检测块依赖,没有解码这些零宽常量,maps 块语义无法闭合):

\```
/dev/ashmem
/memfd:jit-cache (deleted)
base.apk
[anon:dalvik-local ref table]
[anon:thread signal stack]
/system/bin/app_process64
stat -c %i /bin/
stat -c %i /data/
\```

#### 还原原理示例:mainpage 第 56 条从对象图到伪代码(Confirmed 结构)

原始 focused dump 关键行:

\```
[AST] LOVES[mainpage][...][56] ARRAY class=[Ljava.lang.Object; length=5
[AST] LOVES[mainpage][...][56][0] LEAF class=java.lang.Integer value=1
[AST] LOVES[mainpage][...][56][1] NULL
[AST] LOVES[mainpage][...][56][2] ARRAY class=[Ljava.lang.Object; length=2
[AST] LOVES[mainpage][...][56][2][0] OBJECT class=org.mvel2.compiler.ExecutableAccessor value=((count < Literal<50>) && zygisk)
[AST] LOVES[mainpage][...][56][2][1] ARRAY class=[[Ljava.lang.Object; length=18
\```

第一层控制结构还原:

\```
Object[5] 指令结构:
 [0] opcode = 1
 [1] 参数区 = null
 [2][0] 条件表达式 = ((count < 50) && zygisk)
 [2][1] 条件成立后执行的子指令数组,长度 18
 [3] 目标变量 = null
 [4] 行号/源码序号
\```

对应:

```java
if ((count < 50) && zygisk) {
 // 执行 18 条子指令
}
\```

第 1 条子指令把 `/proc/self/maps` 读入 `map`:

\```
[AST] LOVES[mainpage][...][56][2][1][1] ARRAY length=5
[AST] LOVES[mainpage][...][56][2][1][1][0] LEAF value=50
[AST] LOVES[mainpage][...][56][2][1][1][1][0][1] LEAF value=cut
[AST] LOVES[mainpage][...][56][2][1][1][1][1][1] LEAF value=cutFromString
[AST] LOVES[mainpage][...][56][2][1][1][1][3][1] LEAF value=/proc/self/maps
[AST] LOVES[mainpage][...][56][2][1][1][1][5][1] LEAF value=
[AST] LOVES[mainpage][...][56][2][1][1][3] LEAF value=map
[AST] LOVES[mainpage][...][56][2][1][1][4] LEAF value=156
\```

槽位语义:

\```
opcode 50 -> 静态/反射方法调用
参数 cut -> 调用对象/类别名
参数 cutFromString -> 方法名
参数 /proc/self/maps -> 第一个实参
参数 "" -> 第二个实参
target map -> 返回值写入 map
line 156 -> 源脚本行号/序号
\```

还原:

```java
map = cut.cutFromString("/proc/self/maps", "");
\```

紧跟两条子指令(operator 解析已确认 `op45 = substringFrom(indexOf(marker))`、`op37 = indexOf`):

\```
- line=158 op=45 target='exi1' args=[5:'map', 5:'decryptedA']
- line=159 op=37 target='temp1' args=[5:'exi1', 5:'decryptedB']
\```

```java
exi1 = map.substring(map.indexOf(decryptedA));
temp1 = exi1.indexOf(decryptedB);
\```

零宽解码补明文:

\```
decryptedA = "/dev/ashmem"
decryptedB = "/memfd:jit-cache (deleted)"
\```

整理后的 mainpage maps 块伪代码:

```java
if ((count < 50) && zygisk) {
 map = Cut.cutFromString("/proc/self/maps", "");

 exi1 = map.substring(map.indexOf("/dev/ashmem"));
 temp1 = exi1.indexOf("/memfd:jit-cache (deleted)");

 exi2 = map.substring(map.indexOf("base.apk"));
 temp2 = exi2.indexOf("/memfd:jit-cache (deleted)");

 if (supported1 && temp1 == -1) {
 zygisk1 = true;
 }
 if ((temp2 == -1) && supported1) {
 zygisk2 = true;
 }
 if ((temp2 == -1) && supported2) {
 zygisk2 = true;
 }

 // 后续继续围绕 dalvik/thread stack/app_process/property 映射做距离和顺序判断
}
\```

`com.wuying.CommandExecutor.executeCommand` 用 `Runtime.getRuntime.exec` 执行命令并返回 stdout
;动态运行观察到执行 `stat -c %h /sdcard/Android/data/`、
根目录/系统目录 inode 检查、`ls /sdcard/` 等命令(Dynamic)。

---

### 7.4 main insn 220 的放行条件(共 7 项)

放行布尔式:

```java
clean = injected==0 && hooked==0 && traced==0
 && hex==hex1 && hex2==hex3 && dex_md5==fuckyou && dexes==null
\```

逐项数据源 / 算法 / 干净值(Confirmed/Static):

| 变量 | 怎么算 | 数据源 | 干净值 | KPM 能管? |
|-|-|-|-|-|
| **hooked** | 自身 RWX 探针(`/proc/self/maps` 必须看得到 rwx,否则 `rwx==-1` 判脏)+ 扫**自身** `/proc/self/maps` 找标记 | /proc 文件读 | 0 | syscall 可见,C 整行删除自身 maps 标记行 |
| **injected** | 扫**自身** `/proc/self/smaps` 同一批标记 | /proc 文件读 | 0 | C 整行删除自身 smaps |
| **traced** | 默认=1,仅当 `ppid 一致 && TracerPid==0 && sys.boot.reason=="" && sensors>=20` 才清 0(与 7.10 分解一致,TEE 不是 traced 合取项) | /proc/self/status + 属性 + binder | 0 | 真机自然过 |
| **hex==hex1** | `sha256sum <cache>/classes.dex` 对比 `7d22aec4…8a0a0` | shell+文件 | 相等 | app 自身完整性,不改 app 自然过 |
| **hex2==hex3** | 包签名摘要对比 `a40da80a…f5dc9` | PackageManager(binder) | 相等 | app 自身完整性,不改 app 自然过 |
| **dex_md5==fuckyou** | `assets/util.dex` 内嵌标记 `dex/a5e79f…ASSHOLE` | apk 读 | 相等 | app 自身完整性,不改 app 自然过 |
| **dexes==null** | `ls <cache>` 没有多余 `classes2.dex` | shell | null | app 自身完整性,不改 app 自然过 |

`hooked`/`injected` 扫的标记(`indexOf`,命中即脏):

\```
/lib/arm64/(signkiller) zygisk zloader frida lsposed rwxp
data/local/tmp data/adb toybox docker + result==""/null
\```

注意:这是 `indexOf` 命中判脏,**没有任何「su/magisk 文件是否存在」的检查**。所以 riskhider 的 A(路径
ENOENT 隐藏 su/magisk)与 D(statfs 伪造)对过这个 app 完全无用。

`main` 页面规则族:

\```
/proc/self/maps 与 /proc/self/smaps 扫描
/proc/self/status 中 TracerPid 检查
PPid 一致性检查
zygisk frida lsposed rwx rwxp signkiller adb toybox tmp 关键字/状态扫描
classes.dex / APK 内 DEX 哈希校验:dex_md5、hex/hex1/hex2/hex3、dexmod1/dexmod2
应用专项路径检查:com.tencent.mobileqq、com.tencent.mm、com.heyteago
\```

动态运行典型失败值(Dynamic,设备/进程相关,不作跨环境常量):

\```
injected=1
hooked=1
rwx=850
frida/frida1 命中
tracer=0
selinux=0
tee=0
sensors=37
code=1 1 0 850 0 0 0 0 15453 15453 0 0 0 37
\```

---

### 7.5 内核 4.14 上 mainpage maps 结构块不参与判定

`zygisk1 / zygisk2 / zygisk3 / zygisk4` **全部以 `supported1` 或 `supported2` 为前置**,而
`supported1 / supported2` 是**内核版本门**:

| 设备内核 | supported1 | supported2 | 后果 |
|-|-|-|-|
| **4.14.276(本机)** | **false** | **false**【实测】 | zygisk1-4 的判定分支**根本不执行** |
| 5.x(真机未测) | 推断 true(未实机) | 推断 true(未实机) | 分支才会启用;**这些分支只在本机 force `supported=true` 实验点亮过**,supported 公式未 100% 锤死,真实 5.x 自然触发未验证 |

>
> 一句话(避免被表格误读为确定结论):**4.14 实测 `supported=false`,整块休眠;只有 5.x 或 force-`supported`=true 才点亮这些分支,而目前只在本机靠 force 点亮过,真实 5.x 设备上的自然触发未验证。**
>
>
>

实测默认值(force_pass 前,内核 4.14):

\```
temp1=1218 temp2=2635 temp3=-1 temp4=-1 temp5=-1
supported1=false supported2=false
zygisk1=false zygisk2=false zygisk3=false zygisk4=false → zygisk=false
\```

结论:早期"~12 个 maps 结构变量都要处理"的判断在 4.14 上并不成立;hook 里把
supported 强成 true 只是为了测试才点亮它们。真机 4.14 上它们不参与判定。

#### supported 内核门控公式

\```
spkernel = "5.4."
if (kernelver > 4 && spkernel != 0) { kernel = "4." ... } 【推断公式细节】
【实测】4.14.276 → kernelver=4 → supported1=false, supported2=false
\```

语义:只有 ≥5.x 内核才启用 maps 结构检测。

---

### 7.6 zygisk1-4 精确条件与阈值(静态 + force-supported 实验确认,仅 5.x 才生效)

标记字母 ↔ 零宽常量解码表:

\```
A = /dev/ashmem
B = /memfd:jit-cache (deleted)
C = base.apk
D = [anon:dalvik-local ref table]
E = [anon:scudo:secondary]
F = /system/bin/app_process64
G = \n (换行)
H = 空格
I = [anon:thread signal stack]
J = /dev/__properties__/...bootloader_prop:s0
\```

四个 zygisk 子条件精确式:

\```
zygisk1 = supported1 && (maps.substringAfter(A).indexOf(B) == -1)
 # ashmem 段后找不到 jit-cache memfd

zygisk2 = (temp2 == -1) && (supported1 || supported2)
 temp2 = maps.substringAfter(C).indexOf(B)
 # base.apk 后找不到 jit-cache memfd

zygisk3 (两条任一):
 (a) supported1 && temp3 > -1 && temp3 < 1000 && zygisk1 && zygisk2
 temp3 = 在 lastIndexOf(D) ±5000 归一化窗口里找 "E\n \nE" 的位置
 (b) supported2 && temp4 == -1
 temp4 = maps.substring(lastIndexOf(F), +600).indexOf(空格)
 # app_process64 区 600 字节内无空格

zygisk4 = temp5_1 == -1 && supported1 && temp5 > 58 && zygisk1 && zygisk2
 temp5 = 三连 [anon:thread signal stack] 模式 首末出现的字节距离
 temp5_1 = 全局有无 [anon:scudo:secondary]
\```

阈值清单(静态/实验进入确认):`temp3 < 1000`、`temp5 > 58`、归一化窗口 `±5000`、app_process64 区 `+600`。

折叠与计数:

\```
zygisk = zygisk1 || zygisk2 || zygisk3 || zygisk4 || exclude

count: 该块 if (count < 50 && zygisk) 进入后 count++ → "进入次数上限 50"的重入护栏
 (force 里直接置 count=50 即跳出该块,故 7.13 称其为循环块),不是"扫描计数"
\```

前提:`supported` 在 4.14 为 false → 整块不跑。阈值已由静态/force 实验确认,但本机(4.14)不自然触发,真实 5.x 设备上的自然触发未验证。

---

### 7.7 UI 四结果:颜色与条件(insn 88,【AST 位置实测 + 条件推断】)

AST 里四个结果串的位置确定:

| 分支 | 颜色 | 字符串 | 触发条件【推断】 |
|-|-|-|-|
| [0] | #880000 红 | **Zygisk Found** | `zygisk == true` |
| [3] | #880000 红 | **Su Found** | `(su |
| [4] | #BBBB00 黄 | **Unsupported Kernel** | `(supported1 && supported2) == false` |
| [5] | #33CC33 绿 | **Zygisk And Su Not Found** | `zygisk == false && su == false` = **放行** |

实测当前看到的是 [3] "Su Found",反推:

\```
zygisk == false (结构块哑火,符合)
su == true
\```

→ 这台设备上唯一拦着的是 `su`;其余分支都没命中:zygisk1-4 命中会显示 [0]"Zygisk Found",`d`(d>2)并入 `(d>2)||su` 的 su 门、命中显示 [3]"Su Found"(与 7.8/7.13 一致),supported 为假会显示 [4]"Unsupported Kernel"。

---

### 7.8 su 的精确算法(本机 4.14 实测唯一阻断项)

>
> v1.2.9 + Frida 实测修正:早期分析曾把 su 当对象引用比较、或当 st_dev 单值
> 比较——**均不完整**。真值如下。
>
>
>

基础数值:

\```
rootdev = Os.stat("/").st_dev 实测 = 64773
debugdev = Os.stat("/debug_ramdisk").st_dev 实测 = 33 (APatch 独立 tmpfs)
su = (rootdev != debugdev) → 64773 != 33 → true
\```

Frida 实测的完整语义:

\```
- su 比 (st_dev, st_ino) 两者:只改 st_dev 不够(v1.2.6 因此失败);不比 st_nlink。
- 第二处:d = parseInt(`stat -c %h /debug_ramdisk`) (nlink/硬链接数)
 (d > 2) || su 同门;设备 nlink=3 → 需读成 2。
- app 脚本无 try/catch:ENOENT/命令失败 → 崩 → 卡 UI(绝不能用 ENOENT)。
- 落地解(v1.2.9):/debug_ramdisk stat 成功返回 dev/ino = "/" 的值 + nlink=2。
\```

要 su=false 的精确条件:

\```
让 Os.stat("/debug_ramdisk").st_dev == 64773(= "/" 的 st_dev),据 v1.2.6"只改 st_dev 不够"教训 st_ino 一并伪造成 "/" 的值
正常机语义:/debug_ramdisk 与 / 同 st_dev(同一文件系统)→ debugdev==rootdev → su=false
【待核实】基础公式(上面 su=(rootdev!=debugdev))只比 st_dev,而实测记录"比 (st_dev,st_ino) 两者"——st_ino 究竟是 su 公式的比较项、还是 KPM 伪造时为保 stat 一致性需一并改的字段,需回真机/IDB 确认
\```

双 syscall 路径:

\```
Android Os.stat → bionic fstatat(AT_FDCWD, ...) → 内核 newfstatat(主路径)
部分路径可能走 statx
→ 两条都要覆盖(riskhider v1.2.6 已两条都 hook,KPM 改 st_dev@偏移 / st_ino)
\```

调用顺序(after-hook 缓存正确性):

\```
app 先 stat("/") (insn3)
再 stat("/debug_ramdisk") (insn5)
→ after-hook 缓存 / 的 st_dev 再回写,顺序正确
\```

为何 ENOENT 有害:`(d>2)||su` 里只 ENOENT `/debug_ramdisk` → `debugdev` 变空,`空 != rootdev` 仍为 **true** → 反而还是 su;且 app 无 try/catch,ENOENT 直接崩溃卡 UI。
正解是 stat 成功返回伪造的 dev/ino + nlink=2,绝不 ENOENT。

---

### 7.9 d / b / c / gap / smaps 数值(本机不参与"Su Found",备查)

\```
b = parseInt(`stat -c %i /bin/`) 【解码实测】
c = parseInt(`stat -c %i /data/`) 【解码实测】
gap = b - c
if (b - c) 守 insn88 块 【推断:正常机两挂载点 inode 关系固定】

d = parseInt(`stat -c %h /debug_ramdisk`) (= 硬链接数 nlink)
正常机挂载点 nlink = 2 → d > 2 表示被改
(d > 2) → 走 [0] "Zygisk Found";本机看到的是 Su Found,说明 d 没触发

rs1 = /proc/self/smaps 的 Rss:
sd1 = /proc/self/smaps 的 Shared_Dirty:
rf1 = /proc/self/smaps 的 Referenced:
(rs1 > 0 && sd1 > 0 && rf1 > 0) 测某注入区驻留页 → 本机同理未触发
\```

注意:`d` 不是 maps 结构变量,而是 `stat -c %h /debug_ramdisk`(硬链接数),
靠 nlink=2 解决——以 NAILED 结论 + CHANGELOG v1.2.9 为准。

---

### 7.10 traced 与黑名单 / 完整性派生(多源)

traced 环境一致性(真机自然过):

\```
ppid1, ppid2 = `ps -o ppid=` + /proc/self/status PPid → 相等(真机自然)
tracer = /proc/self/status TracerPid → 0(无调试器自然)
selinux = SystemProperties.get("sys.boot.reason") → ""(被 SELinux 拒→空,自然)
sensors = SensorManager.getSensorList (binder) → ≥20(真机 37,自然)
traced = 上面合取 → 0
\```

sensors 走 binder,KPM 碰不到,但真机本来就 ≥20(反模拟器阈值)。

完整性 / 黑名单 / 终值:

\```
dexes = `ls <cache>` 找 classes2.dex 干净值 null 不改 app 自然过
black = 黑名单页(QQ/微信/无影/MediaDrm/GSF) 干净值 false 部分(A 隐藏文件;MediaDrm/GSF 是 binder)
userspace= ? 干净值 0 派生
ok, okkk = 终判标志 派生 派生
\```

---

### 7.11 各变量按"由哪一层对抗处理"归类

\```
| 能搞定的层 | 变量组 | 数量 |
| KPM-C(maps/smaps 删行) | ① 全部标记 + hooked/injected | ~21 |
| KPM-E(st_dev) | ② su/rootdev/debugdev | 3 |
| KPM 可做但脆 | ③ st_ino(inode)、⑥ supported(uname) | ~3 |
| 真机自然过 | ⑦ traced 全组、⑧ dexes | ~6 |
| KPM 很难/做不到 | ④ rs1/sd1/rf1(smaps 数值)、⑤ zygisk1-4+count+i/j/k/l+temp5_1+exclude(maps 结构) | ~12 |
| binder / 派生 | sensors、black、ok/okkk/userspace/zygisk | ~5 |
\```

分组细节:

\```
① 自身 maps/smaps 字符串标记 —— C(整行删除) 已覆盖
 signkiller zygisk zl frida lsposed rwxp tmp adb toy nul (+1 变体)
 = read /proc/self/maps 与 /proc/self/smaps 的 indexOf,干净值 -1
 hooked, injected = 上面 OR 出来的,干净值 0
 注:rwxp 不能删整行/会破坏 maps;但 line-drop 删的是含 zygisk/frida/lsposed/data adb 的
 注入行,通常 rwxp 也在那些行上一并消失。

② su / 设备号 —— E(st_dev 伪造) 部分
 su = ( (stat("/").st_dev, st_ino) != (stat("/debug_ramdisk").st_dev, st_ino) ) // 值比较,不比 nlink
 d = parseInt(stat -c %h /debug_ramdisk) // 同门: (d>2)||su,需 nlink=2
 E 把 /debug_ramdisk 的 st_dev 改成 / 的;但 su 还和 d 在 (d>2)||su 同句,光 su=false 不够

③ inode / 多用户 —— st_ino 伪造 可做但脆
 st_ino=parseInt(stat -c %i <path>) 干净值 ≤2(正常机挂载点 inode=2)
 b,c=stat -c %i 两路径,gap=b-c 守 insn88(不在 force 表,自然 OK / b==c)

④ smaps 数值字段 —— 很脆,不建议
 rs1/sd1/rf1 = read /proc/self/smaps 解析 Rss:/Shared_Dirty:/Referenced:
 要使 (rs1>0 && sd1>0 && rf1>0) 不成立,改数值字段极脆(数字宽度、多区域),误改易崩

⑤ mainpage 隐藏 zygisk-maps 结构块 —— KPM 很难
 zygisk1-4 = read /proc/self/maps 的位置/结构分析(memfd 是否紧邻 base.apk/ashmem、
 thread signal stack 区间距离、app_process64 邻域、dalvik ref table 邻域)
 count/temp5_1/i/j/k/l/exclude = 循环计数/临时量
 C 删行反而改变了位置,可能更触发;syscall 层基本搞不定

⑥ 内核版本 —— uname 风险
 supported1/supported2 = 解析内核版本(5.4. / 4.);改版本号可能影响 app 其它逻辑

⑦ traced —— 真机自然过 / sensors 是 binder(见 第7.10节)

⑧ 完整性 / 黑名单 / 终值 —— 多源(见 第7.10节)
\```

---

### 7.12 卡 Loading 的根因(已定位)与为何 A 无用且卡死

根因:

\```
CommandExecutor 用 Runtime.exec + readLine 读 stdout 直到 EOF(无 waitFor、无超时)。
检测开头就跑 `ps -o ppid=` 拿 zygote pid。
只要某个被 spawn 的子进程不干净退出/不关 stdout,主线程就永远卡在 readLine → UI 永远 Loading。
日志里 211 次同批库 statfs = 子进程被反复启动,正是卡在 exec 阶段。
\```

为何 A(路径 ENOENT 隐藏)无用且是卡死元凶:

\```
- 放行门里没有 su/magisk 文件存在性检查 → A 对过这个 app 完全无用
- A 对子进程每个 *at 调用拦截 → 最可能让子进程异常 → 子进程不干净退出 → readLine 永卡
- 同理解释"frida 时也卡":frida 同样重度干扰子进程
- 实测把 KPM 调到最小(只清 maps)后 app 不崩不卡;经实测,卡 Loading 出现在"只剩 A"时
\```

C(整行删除)必须正确处理的坑:

\```
1. rwx==-1 自探针:app 自己 mmap 一个 RWX 页,要求在 /proc/self/maps 里看得到 "rwx"。
 → C 绝不能删含 rwx 的行(删除标记里没有 rwx,安全);也不能把整个 maps 读坏。
2. 自身 maps 标记行删掉后,result 仍须非空(否则 result=="" 也判脏)。整行删除只删命中行、
 保留其余,天然非空。
3. /lib/arm64/(signkiller)标记:注入库在自身 maps 里的路径特征;但被测 app 自身
 /data/app/.../lib/arm64/ 正常库路径也含它 → 删这类行会破坏 app。当前 C 的 pkg= 自我豁免行保护 app 自身库行;
 注入库行(不含 app 包名)才删。/lib/arm64/ 暂未加入删除标记(太宽,会误伤),
 靠 zygisk/lsposed/data/adb 同行标记覆盖注入库行。
\```

---

### 7.13 对抗落地:本机 4.14 为何 C+E 即可(附前提)

本机判定链(综合 NAILED 结果行 [3]/[4]):看到 [3] "Su Found" ⇒ `zygisk==false`(maps 结构块在 4.14 哑火,
supported 门控)且 `su==true`。所以本机唯一拦路 = `su = (rootdev != debugdev)` 的 (st_dev,st_ino) 值
比较(+ 同门的 d=nlink)。

\```
C(procfilter,清自身 maps/smaps) → hooked/injected=0 [放行门 7 项里的 2 项]
E(st_dev/st_ino 伪造)+ nlink=2 → su=false、d=2 [本机 4.14 实测唯一阻断项]
完整性 4 项(hex/hex2/dex_md5/dexes) + traced → 不改 app + 真机 自然过
maps 结构块 zygisk1-4 → 内核 4.14 supported=false 哑火,不参与判定
\```

KPM 对抗配置:

\```
pkg=wu.Zygisk.Detector # 自我豁免(包名含 zygisk,否则自崩)
uid=<它的uid>
pathhide off # 关 A(无用且致卡)
execblock off # 关 B(无用)
fsfake off # 关 D(无用)
procfilter on # 开 C(唯一需要的:清自身 maps/smaps)
verbose on
# 另需 E:newfstatat/statx 把 /debug_ramdisk 的 stat 改成 dev/ino=/ + nlink=2,成功返回(绝不 ENOENT)
\```

预期:不再卡 Loading;`hooked/injected` 因自身 maps/smaps 被清而=0;su 因 (st_dev,st_ino) 伪造而=false;
完整性/traced 自然过 → 结果落在黄色 [4] "Unsupported Kernel"(4.14 内核上限,su/zygisk 均未检出),结果层通过(本机 supported 门控恒 false,不会走到绿色 [5] 那一档)。若仍报 hooked/injected →
`dmesg | grep 'line-drop'` 确认自身 maps/smaps 真被删了哪些行,按需补标记。

层次分工结论(经 v1.2.9 修正后):

\```
- su 是 (st_dev,st_ino) 值比较(不比 nlink),正属 KPM syscall 层可处理的面。**结果层面已观察到通过/降级为黄色 "Unsupported Kernel"**;但本章未贴出 `[sufake]` 在 `/debug_ramdisk` stat 上 firing、改写 dev/ino 的 dmesg 逐条证据,严格说仍需补这条日志闭环(见下方[待确认])。
- "~12 个 maps 结构硬骨头"在内核 4.14 上全部休眠(supported 门控),不参与判定。
- 早期"KPM 补地鼠补不完、改用 Java HashMap 层强制"的结论作废。
- force_pass_ui.js(Java HashMap.put 层强制全部变量)仅作调试/验证;长期落地不应依赖 per-app 改结果变量——它只证明 UI/变量层可控,不证明环境面已处理
 (antidetect-general-not-perapp 原则),不是落地方案。
\```

>
> 备查:`force_pass_ui.js` 推荐表:
> `injected/hooked/traced/black/userspace`=0/false;`signkiller..nul`(+1 变体)=-1;`ppid1/ppid2`=同 pid;
> `tracer`=0;`selinux`="";`sensors`=37;`hexmod1/2`、`dexmod1/2`=0;`dexes`=null;`rootdev/debugdev`=
> 都 `'same-device'`;`su/exclude`=false;`okkk`=true;`count`=50(跳出 mainpage zygisk 循环块);
> `supported1/2`、`zygisk1-4`=false。
>
>
>

## 八、深度逆向(三)Momo(io.github.vvb2060.mahoshojo)

样本:`io.github.vvb2060.mahoshojo`,native `libmahoshojo.so`(175984 字节),Java 层为高度混淆的单字母包(`defpackage/W3`、`Hn`、`Ei`、`Fi`、`Hf` 等)。本章对该 SO 的检测面做系统性还原;证据等级沿用 Confirmed / High / Static / Dynamic / Inferred / pending,逆向没覆盖的(尤其 KPM 逐项映射)一律标"未明确",不补编。

---

### 8.0 分析边界与证据等级(必须先读)

证据边界:

- 静态分析是还原完整控制流与 helper 语义的主要手段。
- 动态:真机 Frida 已恢复可用,有完整 trace 佐证。
- 关键陷阱:这条最新 Frida trace **不是干净未修改的判定**,它打了两处运行时补丁才跑完 `get(1..27)`。
- unidbg 能跑 `JNI_OnLoad` 与 `App.get(I)I -> 0xE564`,但结果依赖环境建模,只能当受控模拟,不是真机判定。

两处运行时补丁,这是理解后续所有动态数值的总前提:

| RVA | Patch | 含义 |
|-|-|-|
| `0x15188` | 把直 `SVC 0` 改成 `MOV X0,#0` | 中和 `0xE564` 内联的 `kill(pid, SIGKILL)`;未打补丁的活动 trace 在 selector sweep 时直接被信号 9 杀死。 |
| `0x1D8AC` | 整个 scanner 返回改 `0` | 绕过 Frida 敏感的 linker/loader 扫描,使 selector 17 不会终止整轮 sweep。 |

被中和的 kill 三连:

\```
0x15180: MOV W1, #9 ; SIGKILL
0x15184: MOV X8, #0x81 ; __NR_kill
0x15188: SVC 0 ; kill(pid, 9) 内联在 0xE564 里
\```

空 attach 即扰动(本样本的整体特征):

\```
Frida attach 本身就改变可观测进程环境。
libmahoshojo.so 在 JNI/init/get 路径采样该环境。
部分检查在任何用户 hook 逻辑生效之前就已触发。
\```

具体原因:`/proc/self/maps` 内容与可执行映射、Frida gadget/agent/trampoline 副作用、匿名可执行页或被改的运行时映射布局、linker/libart/libc 扫描状态、Magisk/Zygisk/Xposed/Riru 注入痕迹、`/dev/socket/adbd`/boot 属性/mount namespace/uid/pid/map 一致性、UI 进程本地 `App.get` 采样与隔离 service Binder 采样的跨进程一致性。

另一处分析坑——dump 文件 RVA 布局陷阱:`libmahoshojo.initarray.dump.bin` 是 RVA-layout 内存 dump,不是 file-offset 正确的 ELF;`ro.build.version.sdk` 可以出现在 dump 文件偏移 `0x2B800`,而 IDA 虚拟地址 `0x2B800` 是 0。IDA 必须用 `libmahoshojo.initarray.patched.so`。

---

### 8.1 总体架构:side-effect 取样器 + 选择子聚合 + 字节数组 sink

核心链:

\```
init/JNI_OnLoad
 -> scan_status_tracerpid 0xD844
 -> detect_root_magisk_maps_apk_env 0x87BC
 -> native_get_env_detection_flags 0xE564 / App.get(int)
 -> native_get2_detection_string 0x15798 / App.get2(int)
 -> native_check_byte_array 0x15C48 / App.check(byte[])
 -> scan_linker_loader_integrity 0x1D8AC
\```

架构本质:

>
> The SO is side-effect oriented. `0x87BC` writes global flags; `0xE564`, `0x15798`, and `0x15C48` later read those globals and combine them with live checks.
>
>
>

即:`0x87BC` 是一个 staged sampler,在构造/init 阶段把环境扫一遍,把结论写进一组全局字节标志(`g_*`);随后 `0xE564`(选择子聚合器)、`0x15798`(字符串导出)、`0x15C48`(字节数组 sink)读这些全局,再叠加实时检查产出对外可见结果。盲目把所有值清零是错的:

- `App.get(5)` 必须保持真实 `0`,强制 `1` 触发 Xposed UI 警告。
- `App.get(9)` 必须保持真实 app UID,强制 `99000` 破坏 `W3.g == Os.getuid`。
- service 端 `Gi.get(16)` 必须为 `1`,返回 `0` 触发 "Seccomp 未开启"。

主函数清单:

| RVA | Name | Role |
|-|-|-|
| `0x87BC` | `detect_root_magisk_maps_apk_env` | 写 root/Magisk/maps/APK/path 全局,主要副作用驱动。 |
| `0xE564` | `native_get_env_detection_flags` | Java `App.get(I)I` 选择子聚合器,返回 UI/service flags。 |
| `0x1D8AC` | `scan_linker_loader_integrity` | linker/loader/maps scanner,Frida 敏感,重度嵌套 OLLVM。 |

---

### 8.2 JNI 注册:三方法 + 运行时 init gate

`JNI_OnLoad` 注册类 `io/github/vvb2060/mahoshojo/App`,三个 native 方法:

- `get(I)I -> 0xE564 native_get_env_detection_flags`
- `get2(I)Ljava/lang/String; -> 0x15798 native_get2_detection_string`
- `check([B)V -> 0x15C48 native_check_byte_array`

`JNI_OnLoad` 还读 `ro.build.version.sdk`,并初始化 `g_runtime_init_status`(来自 `init_runtime_detection_state@0x51B8`);status `3` 走 `JNI_OnLoad` 的失败/bad 分支。写入证据:

```asm
0xE4FC: BL init_runtime_detection_state ; 0x51B8
0xE500: ADRP X8, g_runtime_init_status
0xE504: STR W0, [X8, g_runtime_init_status]
0xE510: CMP W0, #3 ; status 3 走失败分支
\```

`init_runtime_detection_state@0x51B8` 还原伪代码:

```c
sub_7AA4; // probe_art_javavmext_roots
if (!dword_2C690)
 return 0;
sub_5638(jni_env); // scan_stacktrace_for_xposed_hook
return dword_2C690;
\```

也就是说 selector 5(Xposed 路由)的真正源头在 init 阶段就已经算好,缓存进 `g_runtime_init_status`,详见 8.6.2。

ART root visitor / Xposed 检测细节——decoder 规则:`0x5E14 is_prime_u64` 是质数判定;编码串解码方式是选 `p >= length` 的下一个质数,`decoded[i] = encoded[i] ^ ((i + length) % p)`。解出的 `0x7AA4 probe_art_javavmext_roots` 串:

| Address | Decoded string | Static role |
|-|-|-|
| `0x4944` | `dalvik/system/BaseDexClassLoader` | JNI `FindClass` 目标,仅 SDK ≥ 21 用。 |
| `0x4A13` | `_ZN3art9JavaVMExt10VisitRootsEPNS_11RootVisitorE` | ART 内部符号,经 `dl_iterate_phdr` helper 解析。 |
| `0x46AD` | `_ZN3art9JavaVMExt19SweepJniWeakGlobalsEPNS_15IsMarkedVisitorE` | ART 内部符号。 |

`0x51F8` 是两个 visitor 都会到达的检测体:调 `sub_5B94`/`sub_5EA4`,命中目标类/对象时把 `dword_2C690` 从 `0` 升到 `1`,后续 marker 命中升 `2`,`0x5638` 栈扫描再升 `3`。`sub_51F8` 解出的标志串包含 `me/weishu/epic/art2/EpicNative`、`me/weishu/epic/art2/EpicBridge`、`de/robv/android/xposed/DexposedBridge`。【待核实】`de/robv/android/xposed/DexposedBridge` 是非标准混名(标准为 `de.robv.android.xposed.XposedBridge`,`DexposedBridge` 实属 `com.taobao.android.dexposed`),需回 IDB 核对是笔误还是真实变体检测串。

---

### 8.3 共享反调试:`scan_status_tracerpid 0xD844`(含 PR_GET_DUMPABLE 坑)

这是跨所有主要导出路径的公共反调试 gate。调用方:

\```
0x87E4 来自 0x87BC
0x9394 来自 0x87BC
0xE5C0 来自 0xE564
0x157E0 来自 get2 (0x15798)
0x15C74 来自 check([B) (0x15C48)
\```

动态证据:

\```
strncmp lr=0xde84 args="TracerPid:\t0\n", "TracerPid" ret=0
\```

还原行为:

```c
for each line in /proc/<pid>/status or /proc/self/status:
 if strncmp(line, "TracerPid", 9) == 0:
 parse tracer pid
 if tracer pid != 0:
 g_tracerpid_detected_flag = 1
\```

unidbg 确认的逐指令行为:

- `0xD93C`:直 `openat(AT_FDCWD, "/proc/<pid>/status", 0x80000, 0)`,`x8=0x38`。
- `0xDF24`:`fgets` / checked `fgets` 逐行读。
- `0xDE80`:`strncmp(line, "TracerPid", 9)`。
- `0xDE84`:`strncmp` 返回,对 `TracerPid:\t0` 返回 `0`。
- `0xDA48`:写 `g_tracerpid_detected_flag`。
- `0xD9D0` / `0xDA18`:还 gate 在 mount device minor 与本地状态上。

代表性 clean-profile trace:

\```
[pc] App.get(1) rva=0xd93c status openat svc ... s1="/proc/1518/status"
[pc] App.get(1) rva=0xdf24 fgets call ... s0="TracerPid:\t0\n"
[pc] App.get(1) rva=0xde80 strncmp(line, TracerPid, 9) call ... s0="TracerPid:\t0\n" s1="TracerPid"
[pc] App.get(1) rva=0xde84 strncmp return ... strncmp_ret_w0=0
[pc] App.get(1) rva=0xda48 WRITE g_tracerpid_detected_flag ... store_w8=1
\```

**PR_GET_DUMPABLE 坑**:即使 `TracerPid: 0`、文本干净,`g_tracerpid_detected_flag` 在 unidbg 里仍被写成 `1`。源头不是被解析的 TracerPid 行,而是 `scan_status_tracerpid` 内部的 `PR_GET_DUMPABLE` 分支——unidbg 对 `prctl(PR_GET_DUMPABLE)` 返回 `1`。把 unidbg 的 `PR_GET_DUMPABLE` 从 `1` 改成 `0` 后:

\```
scan_status_tracerpid
 -> reads /proc/<pid>/status
 -> finds "TracerPid:\t0\n"
 -> strncmp("TracerPid", line, 9) == 0
 -> atoi(line + 10) == 0
 -> reads g_tracerpid_detected_flag
 -> selector 26 reads g_tracerpid_detected_flag at 0x114CC
 -> final return at 0x15794
\```

校正后:`0xDA48` 写 `g_tracerpid_detected_flag=0`,`0x114CC` 读 `0`,`get(26)=0`。结论:该误报是 unidbg 的 `PR_GET_DUMPABLE=1` 行为造成,而非真机 TracerPid 命中。真机 Frida(killpatched)snapshot 里 `g_tracerpid_detected_flag=0`。

g_tracerpid 全局读写点:

```asm
0xDA44/0xDA48 scan_status_tracerpid write g_tracerpid_detected_flag(0x2C6E8)
0xDBC4/0xDBC8 scan_status_tracerpid read
0x114C8/0x114CC native_get_env... read ; selector 26
0x15DD8/0x15DE0 native_check_byte_array read ; 第二道 dirty gate
\```

注意 `scan_status_tracerpid` 还写 `g_initarray_state_seed`(`0xDC2C STR W0, [g_initarray_state_seed]`)和读/写 `g_mount_data_suspicious_flag`(`0xDEA8`)。该函数不是纯反调试,它兼做 init seed 与 mount 状态的副作用写入。

---

### 8.4 环境取样器:`detect_root_magisk_maps_apk_env 0x87BC`

范围 `0x87BC`-`0xCB24`,size `0x4368`;字符串引用 70、调用 112、全局引用 88。职责:扫 `/proc/%d/mountinfo`、`/proc/%d/maps`、APK/odex 路径状态、APK Sig Block marker、`/proc/%d/fd/%d` SELinux 标签、dex2oat cmdline/属性、`$PATH` 中 `magisk`/`su`,然后写一组全局。

输出全局表:

| Global | RVA | 含义 |
|-|-|-|
| `g_mount_proc_overlay_seen_flag` | `0x2C6BC` | `/proc`、overlay、`/dev/root`、mount marker 已见。 |
| `g_mount_data_suspicious_flag` | `0x2C6C0` | `/data` mount device 元组或 maps/path 不一致。 |
| `g_magisk_path_seen_flag` | `0x2C6C4` | mountinfo/path 含 Magisk/APatch/ZygiskSU 风格 marker。 |
| `g_app_process_seen_flag` | `0x2C6C8` | app_process marker 已见。 |
| `g_system_bin_app_process_flag` | `0x2C6CC` | `/system/bin/app_process` marker 已见。 |
| `g_app_data_path_seen_flag` | `0x2C6D0` | app data path marker 已见。 |
| `g_maps_uid_or_pid_value` | `0x2C6D4` | 从 maps/path 解析出的 UID/PID 样值。 |
| `g_apk_sig_or_path_suspicious_flag` | `0x2C6D8` | APK 签名/path 元数据可疑。 |
| `g_path_su_found_flag` | `0x2C6DC` | `$PATH/su` 存在。 |
| `g_path_magisk_found_flag` | `0x2C6E0` | `$PATH/magisk` 存在。 |

另有 mount device 元组缓存:`g_mount_dev_major_a 0x2BAE4` / `g_mount_dev_minor_a 0x2BAE8` / `g_mount_dev_major_b 0x2BAEC` / `g_mount_dev_minor_b 0x2BAF0`,以及 `g_apk_signature_result 0x2BAF4`、`g_dex2oat_inline_result 0x2BAF8`、`g_initarray_state_seed 0x2BAE0`。

#### 8.4.1 mountinfo 区:Magisk/overlay 全 writer asm

字符串地标:

\```
0x8980 "/proc/%d/mountinfo"
0x8bd8 " / /proc "
0x8c7c " /dev/root "
0x8ccc " / /data "
0x8ddc "/adb/modules/"
0x8e98 " - overlay "
0x8f0c "upperdir="
0x8f70 "magisk"
0x8f9c "%*d %*d %d:%d" ; 解析 mount dev major:minor
0x9138 "errors=remount-ro"
0x9790 " /vendor/"
0x9bbc " /system_ext/"
0x9c38 "%*s %*c%*c%*c%c"
\```

确认的 Magisk writer:

```asm
0x8F08 LDR X0, [X28,#0xE8] ; [unflat] 2-way via cave: eq ? 0x92d0 : 0x8f6c
0x8F0C ADRL X1, "upperdir="
0x8F14 BL sub_1C378
0x8F34 MOV W8, #1
0x8F38 ADRP X9, g_magisk_path_seen_flag
0x8F3C STRB W8, [X9, g_magisk_path_seen_flag] ; g_magisk_path_seen_flag = 1
\```

`0x8F08` 起的完整 flattened state 常量:

```asm
0x8f18: MOV W8, #0x65B6
0x8f1c: MOV W9, #0x7F20
0x8f20: CMP X0, #0
0x8f24: MOVK W8, #0x4B1B,LSL#16 ; not-found state 0x4B1B65B6
0x8f28: MOVK W9, #0xDCD0,LSL#16 ; found state 0xDCD07F20
0x8f2c: CSEL W8, W9, W8, EQ
0x8f34: MOV W8, #1 ; [unflat] deterministic -> 0x8ed4
0x8f3c: STRB W8, [g_magisk_path_seen_flag]
0x8f40: MOV W8, #0x65ED9141 ; next state
0x8f48: B loc_8ED4
\```

第二 writer:

```asm
0x92e8: LDRB W8, [g_magisk_path_seen_flag] ; [unflat] 2-way via cave: eq ? 0x8dd8 : 0x8ed4
0x92f0: MOV W9, #0x65ED9141
0x92f8: CMP W8, #0
0x92fc: MOV W8, #0x553B2E8A
0x9304: CSEL W8, W9, W8, NE
0x930c: MOV W8, #1 ; [unflat] deterministic -> 0x92e8
0x9310: ADRP X9, g_magisk_path_seen_flag
0x9314: STRB W8, [X9, g_magisk_path_seen_flag]
0x9318: MOV W8, #0xBD52D387
0x9320: B loc_92E8
\```

动态低扰动 writer 捕获确认这是真命中而非静态误匹配:

\```
line="/adb/modules/zygisk_lsposed/bin/dex2oat32 ... - f2fs /dev/block/dm-37 ..."
site=0x8F3C, W8=1
\```

具体触发是 APatch/ZygiskSU/LSPosed 风格 mountinfo 内容,落在 `/adb/modules/...` 下。第三处涉及 `g_mount_proc_overlay_seen_flag` writer:

```asm
0x8c34/0x8c38 STRB g_mount_proc_overlay_seen_flag
0x8d1c/0x8d20 STRB g_mount_proc_overlay_seen_flag
0x92d4/0x92d8 STRB g_mount_proc_overlay_seen_flag
\```

#### 8.4.2 `/data` mount device 元组

mount dev major/minor 用 `%*d %*d %d:%d` 解析后存进 `g_mount_dev_*`(`0x8fa0`-`0x90d8`):

```asm
0x8fa0: ADRP X2, g_mount_dev_major_b
0x8fa4: ADRP X3, g_mount_dev_minor_b
0x90b4: ADRP X8, g_mount_data_suspicious_flag ; [unflat] deterministic -> 0x8b84
0x90bc: STRB W9, [X8, g_mount_data_suspicious_flag]
0x90d4: LDRSW X10, [g_mount_dev_minor_b]
0x911c: ADRP X2, g_mount_dev_major_a
0x9120: ADRP X3, g_mount_dev_minor_a
\```

抑制 Magisk writer 后,真机 snapshot 仍显示:

\```
get(4) => 1
get(14) => 1 before adbd hook
get(19) => 1 before verifiedbootstate hook
mount_dev_major_a=253, mount_dev_minor_a=37
mount_dev_major_b=0, mount_dev_minor_b=5
\```

结论:`get(4)` 不是单纯的 Magisk path flag,它受解析出的 mount device major/minor 状态与"干净哨兵期望"影响。精确 selector 合并点仍需 `0xE564` 深 CFG 切片(pending)。`g_mount_data_suspicious_flag` 第二处 writer 在 maps 路径 `0x9e8c/0x9e94`,被标 "preserved unresolved state where target mapping was not unique"。

#### 8.4.3 maps / APK / app path 区

字符串地标:

\```
0x9470 "/proc/%d/maps"
0x9868 "/system/bin/app_process"
0x98F0 "io.github.vvb2060.mahoshojo"
0x9994 "base.odex"
0x9ECC " /data/app/"
0xA100 ".apk"
0xA4A4 "base.apk"
0xAD34 "/memfd:jit-cache"
0xAD78 " /data/adb/"
0xBD68 "APK Sig Block 42"
\```

解读:app maps 被解析出期望的 APK/base.odex/base.apk 布局;`/data/adb` 与 `memfd:jit-cache` 是可疑进程 marker;`APK Sig Block 42` 用作 APK 签名/path 完整性证据。`g_maps_uid_or_pid_value` 由 `%*s %*s %*s %*s %u`(`0xa2c0`)解析,后续用于比对 APK/path owner 或 inode 样值:

```asm
0xa2bc: ADRP X29, g_maps_uid_or_pid_value ; AI: parses maps line fields and updates g_maps_uid_or_pid_value
0xa2c4: ADD X29, X29, g_maps_uid_or_pid_value
0xa2d4: LDR W8, [X29]
\```

`g_apk_signature_result` 在 `0xa800/0xa808` 与 `0xc18c/0xc198` 写入;`g_dex2oat_inline_result` 在 `0xc840/0xc84c` 写入。

#### 8.4.4 PATH 扫描:su / magisk

字符串地标 `0xC950 "%s/magisk"`、`0xC9F4 "%s/su"`。还原行为:

```c
for each entry in getenv("PATH"):
 if access("%s/magisk", F_OK) == 0:
 g_path_magisk_found_flag = 1
 if access("%s/su", F_OK) == 0:
 g_path_su_found_flag = 1
\```

writer asm:

```asm
0xca74: ADRP X1, g_path_su_found_flag
0xca78: STRB W8, [X1, g_path_su_found_flag]
0xca8c: ADRP X1, g_path_magisk_found_flag
0xca90: STRB W8, [X1, g_path_magisk_found_flag]
\```

reader 在 `0xE564`:`g_path_magisk_found_flag` 读于 `0xe984/0xe988`,`g_path_su_found_flag` 读于 `0x146c0/0x146c4`。注意 PATH magisk 与 mountinfo magisk 是**两条独立信号**。

---

### 8.5 SIGSYS / seccomp 探针

安装在 `0x87BC` 内:

```asm
0x8898: ADRP X1, sigsys_handler_set_seccomp_probe_seen
0x889c: MOV W0, #0x1F ; SIGSYS = 31
0x88a0: ADD X1, X1, sigsys_handler_set_seccomp_probe_seen
0x88a4: BL .signal ; signal(31, handler)
0x88c0: MOV X8, #0xAC ; 直 syscall
0x88c4: SVC 0
\```

handler `sigsys_handler_set_seccomp_probe_seen@0xE020`:

```asm
0xE020: sigsys_handler_set_seccomp_probe_seen(signo)
0xE024: CMP W0, #0x1F ; SIGSYS = 31
0xE070: load comparison result
0xE084: STRB W12, [g_sigsys_seccomp_probe_seen] ; W12 = 1
\```

还原逻辑:

```c
signal(SIGSYS, sigsys_handler_set_seccomp_probe_seen);
syscall(0xAC);
service_seccomp_ok = g_sigsys_seccomp_probe_seen;
\```

selector 16 读取点:`0x116D8 LDRB W29, [g_sigsys_seccomp_probe_seen]`。全局 `g_sigsys_seccomp_probe_seen 0x2C6E4` 仅 4 个 xref:写于 `0xE04C/0xE084`(handler),读于 `0x116D8/0x116DC`(`0xE564`)。动态 hook 确认 `libc signal(SIGSYS=31, handler=base+0xE020)`。

极性反常:绝大多数 dirty selector 用 `0` 表示干净,但 service 端 `get(16)` 是健康正向位——`1` 表示 SIGSYS/seccomp 探针确实跑过,`0` 被 Java 渲染为 `Seccomp 未开启。`。

动态注意:脚本在 `libmahoshojo.so` 加载前 hook libc `signal`/`sigaction`,以便构造期 `0x87BC` 即使先于 RVA hook 运行,SIGSYS 注册仍可见。绝不默认 hook handler 体 `0xE020`,在 signal handler 上下文跑 JS 不安全。service 自然调用确认:`Gi.get(16) => 1`。注:`0xAC`(172)在 arm64 是 getpid,标准 seccomp 不会把它 TRAP 成 SIGSYS——此处为何被陷入(是否依赖特定过滤策略、或号需复核)标 pending,不影响"健康位=1 才算 seccomp 在位"的结论。

---

### 8.6 选择子聚合器:`native_get_env_detection_flags 0xE564` 逐 selector

范围 `0xE564`-`0x15798`,size `0x7234`;字符串引用 114、调用 137、全局引用 53。入口先调 `scan_status_tracerpid`(`0xe5c0`),把 selector 参数路由进 OLLVM state 常量,再把 `0x87BC` 全局与实时检查合并。

selector 状态初始化常量表(Selector Map V1 静态切片):每个 selector 在 `0xE5F4`-`0xE890` 初始化一个 `var_16xx = 常量`,例:`5 -> var_1698=0x5071E485`、`14 -> var_16D0=0x5FB4FE12`、`16 -> var_16D4=0xA497C8A2`、`19 -> var_16B4=0xBC2DD379`、`20 -> var_16A8=0x0DAB1E44`、`24 -> var_16E4=0x69603CC3`、`26 -> var_16E0=0x9BDFEEFD`、`27 -> var_16DC=0x59AAEC75 / var_16D8=0x131421A8`。完整 27 行见 8.10 汇总表。

字符串地标全清单:

\```
0xf034 "/sdcard/Download/magisk_patched.img"
0xf0b8 "/data/system/taichi"
0xf150 "/data/system/thanos"
0xf1d4 "/sdcard/TWRP"
0xf240 "/dev/socket/adbd"
0xf334 "/system/addon.d"
0xf4ec "libriru"
0xf5f4 "ro.boot.verifiedbootstate"
0xf8b4 "Riru"
0xf944 "LSPosed"
0xfa14 / 0xfa38 / 0xfb60 / 0xfb68 "Magisk"
0xfca0 "zygisk"
0xff24 "/system/bin/app_process"
0x10020 "/memfd:jit-cache"
0x1042c "/system/bin/screencap"
0x105fc "/system/bin/bootanimation"
0x10804 "/system/bin/appwidget"
0x108d0 "/system/bin/bu"
0x10a2c "/data/adb/"
0x10e88 "green"
0x10f90 "/system/bin/install-recovery.sh"
\```

#### 8.6.1 selector 4 — pty/devpts 行为探针(polarity pending)

unidbg 确认路径:

\```
0x11C28 openat(AT_FDCWD, "/dev/ptmx", 0x80102) -> fd 3
0x153F0 sub_192BC(fd=3, request=0x80045430, buf) -> 0
0x15390 sub_192BC(fd=3, request=0x40045431, buf) -> 0
0x15630 openat(AT_FDCWD, "/dev/pts/0", 0x80102) -> fd 4
0x155B0 sub_192BC(fd=4, request=0x5412, "MahoShojo") -> 0
0x154AC close one pty fd
0x1550C close second pty fd
0x15720 stores W22 candidate 0
0x15734 candidate is not positive
0x15758 loads var_1640 = 0xFFFFFFFF
0x15794 returns -1
\```

关键:早先"`get(4)=-1` 是缺 `/dev/ptmx`"的说法被推翻;校正后 `/dev/ptmx`、`/dev/pts/0`、全部 ioctl/helper 调用都成功,最终 `-1` 是 pty 路径成功后在 `0x156D4` 种下 `W24=-1`、经 close 路径带进 `var_1640`。这是 pty/devpts 行为探针,不是简单存在性检查。`-1` 是"clean/not suspicious"还是"unsupported result" 仍 pending,需 `0x155DC-0x15758` 局部状态恢复。真机 killpatched trace `get(4)=1`。format helper 为 `0x16E9C format_devpts_path`,格式化 `/dev/pts/%u`。

#### 8.6.2 selector 5 — runtime/Xposed init status(High)

完整 selector→state→global 链:

\```
0xE5A0 MOV W23, W2 ; selector 参数
0xE664 CMP W23, #5
0xE67C selector 5 把 state 0x5071E485 写进 var_1698
0xF4B8 state 0x1878DC28 handler 加载 var_1698
0x10CA4 匹配 state 0x7575C645
0x10CB8 ADRP X8, g_runtime_init_status
0x10CBC LDR W29, [X8, g_runtime_init_status]
0x116E0/0x10CC0 风格路径设最终 state 0x835CBED5
0x15758 LDR W0, [SP+var_1640]
0x15794 RET
\```

即 selector 5 不是直 Java 字符串比较,而是绕 `g_runtime_init_status` 的 selector wrapper(该缓存在 `JNI_OnLoad` 经 `init_runtime_detection_state` 写,见 8.2)。`get(5)=0` 干净;强制 `1` 映射到 Java `Fi.e` / `找到 Xposed 框架。`。

`sub_5638 scan_stacktrace_for_xposed_hook` 用 JNI 反射调 `Thread.currentThread.getStackTrace`,遍历栈帧 `getClassName`,与解码目标比较:

```asm
0x5B18 memcmp(candidate_class_name, "de.robv.android.xposed.XC_MethodHook", 0x24)
0x5B38 dword_2C690 = 3 on match
\```

更早 Frida 静态切片:`0xE664 CMP W23,#5`;selector 5 取 `0xE67C` 的 non-LT arm,`var_1698=0x5071E485`;`0xEA0C` 处理 state `0x5071E485` 加载 `var_16BC`;selector 5 设 `var_16BC=0x7575C645`;`0x10CA4` 匹配 `0x7575C645`;`0x10CB8` 读 `g_runtime_init_status`。

动态坑:Frida 直接 `App.get(5/16)` 不可靠,即使 `JNI_OnLoad` 返回后,主动调用也会在 Java 返回前 stall。用被动 trace,让 app 自然调。

#### 8.6.3 selector 14 — `/dev/socket/adbd`(High)

asm:

```asm
0xf240: ADRL X0, aDevSocketAdbd ; "/dev/socket/adbd"
0xf248: MOV W1, WZR ; F_OK
0xf24c: BL .access
0xf250: CMP W0, #0
0xf254: CSET W8, EQ
0xf25c: STRB W8, [SP, var_14A0]
\```

还原:`selector14_dirty = access("/dev/socket/adbd", F_OK) == 0;`。动态 hook 确认:

\```
patch access sel=14 lr=0xf250 path="/dev/socket/adbd" old=0 new=-1
get(14) => 0
\```

真机 `get(14)=1`(adbd 存在),hide 后 `0`。

#### 8.6.4 selector 16 — seccomp/SIGSYS 缓存健康位(High)

selector→state 链:

\```
0xE790 CMP W23, #0x10 ; 16
0xE79C selector 16 选 state 0xA497C8A2 进 var_16D4
0x10C44 loads var_16D4
0x10BBC handles state 0xA497C8A2 and loads var_16A0 ; selector16: var_16A0=0x8D6529E6
0xEC54 matches state 0x8D6529E6
0xEC60 routes to 0x116D8
0x116D8 ADRP X8, g_sigsys_seccomp_probe_seen
0x116DC LDRB W29, [X8, g_sigsys_seccomp_probe_seen]
0x116E0 state 0x835CBED5
0x15758 LDR W0, [SP+var_1640]
0x15794 RET
\```

`0x116D8` 窗口完整 asm(注意原注释误标为 dex2oat,实为 seccomp probe):

```asm
0x116d8: ADRP X8, g_sigsys_seccomp_probe_seen
0x116dc: LDRB W29, [X8, g_sigsys_seccomp_probe_seen]
0x116e0: MOV W9, #0x835CBED5
0x116e8: B loc_E8E8
\```

UI 进程 `get(16)=0`,service 端健康值 `1`(见 8.5)。

#### 8.6.5 selector 17 — 见 8.7 专节(linker scanner)

#### 8.6.6 selector 19 — `ro.boot.verifiedbootstate`(High)

属性读 asm:

```asm
0xf5f4: ADRL X0, aRoBootVerified ; "ro.boot.verifiedbootstate"
0xf618: BL .__system_property_get
0xf61c: CMP W0, #0
0xf620: CSET W8, GT
\```

clean 比较 asm:

```asm
0x10e80: ADD X8, SP, s2
0x10e84: LDR X0, [X8, #0x30] ; s1 = value
0x10e88: ADRL X1, aGreen ; "green"
0x10e90: BL .strcmp
0x10eac: CMP W0, #0
\```

还原:`dirty = property_exists && strcmp(value, "green") != 0;`。动态 hook:

\```
patch property sel=19 lr=0xf61c name="ro.boot.verifiedbootstate"
oldValue="orange" -> "green"
get(19) => 0
\```

unidbg 用 `SystemPropertyHook` provider 返回 `green` 后 `0x10E94 strcmp_ret_w0=0`,`get(19)=0`。真机 `ro.boot.verifiedbootstate="orange"`,`get(19)=1`。

#### 8.6.7 selector 20 — `check_proc_selinux_context 0x18BAC`(High,helper-return 直传)

caller `0x15160 BL check_proc_selinux_context`,helper 返回 `W0` 直接进 `W29` 再进共享 `get(I)` 返回 funnel。helper 用串 `/proc/%d`、`/proc`、`security.selinux`、期望 SELinux context `u:object_r:proc:s0`。unidbg 确认 UID-owner 子路径:

\```
0x18CC8 newfstatat/stat64("/proc/<pid>", ...)
0x18D54 syscall 148 getresuid(...)
0x18DD4 compare stat_uid with ruid
0x18DE8 CSET EQ
0x18DEC STRB var_89
0x18EA4 reads var_89 = 1
0x18EBC selects state 0xE1123B54
0x18F90 sets return candidate W8 = 1
0x19064 stores var_1D4 = 1
0x19298 returns var_1D4
native get final return = 1
\```

当前 `get(20)=1` 走 `/proc/<pid>` stat UID == `getresuid` ruid 早分支,**不**到达 `getxattr("/proc","security.selinux",...)`(`0x18FD4/0x18FD8`)。要验 SELinux-string 子路径需让首次 UID 比较失败。真机 killpatched 下 `get(20)=0`,caller 直传 helper 结果。两处 unidbg/真机 polarity 不同,因 stat UID / getresuid 在两环境取值不同——这是模型差异不是矛盾。

#### 8.6.8 selector 21 / 22 — `get(I)I` 默认/无效结果链(非检测)

`get(21)`/`get(22)` 整数路径走同一 dispatcher 默认链返回 `-1`,**不**触独立检测器:

\```
0x10BF4 reads g_apk_signature_result = 1
0x10C14 selects next state 0x0162561A
0xF30C state 0x0162561A
0x11CE8 -> next state 0xE3326227
0xED40 loads var_1680 = 0xF0B5DC41
0x10C60 loads var_16B4 = 0xBC2DD379
0xF420 loads var_16E4 = 0xFB186F53
0xEFBC loads var_16AC = 0xE4CBE4CE
0xF52C loads var_16A4 = 0x11045B24
dispatcher then reaches 0x10E0C59B -> 0x3BC22656
0x10DF0 sets W29 = 0xFFFFFFFF and next state 0x835CBED5
0x15758 loads var_1640 = 0xFFFFFFFF
return -1
\```

真实 selector 21/22 数据在 `get2(I)String`,见 8.8。不要把 `get(21)=-1`/`get(22)=-1` 当"检测到坏环境"。

#### 8.6.9 selector 24 — app-data/maps path 分类器(final meaning pending)

CSEL 分支 asm:

```asm
0x134A4 ADRP X8, g_app_data_path_seen_flag
0x134A8 LDRB W8, [X8, g_app_data_path_seen_flag]
0x134AC MOV W9, #0x87047681
0x134B4 CMP W8, #0
0x134B8 MOV W8, #0x766811A4
0x134C0 CSEL W9, W8, W9, NE
0x134C4 B 0x15434
\```

即 `flag==0 -> state 0x87047681`,`flag!=0 -> state 0x766811A4`。但两路都汇聚到 `0x15434` merge funnel 写 `var_165C=1`,最终都返回 `1`:

\```
selector 24
 -> read g_app_data_path_seen_flag
 -> flag == 0
 -> choose flattened state 0x87047681
 -> 0x15434 merge block (var_1640=0xD737282B, var_165C=0)
 -> var_165C = 1
 -> 0x11BE0 loads var_165C into dispatcher state/value path
 -> var_1640 = 1
 -> 0x15758 loads var_1640 into W0
 -> return 1
\```

强制 `g_app_data_path_seen_flag=1` 验证:state 确实变 `0x766811A4`,但仍收敛回同 merge 返回 `1`。结论:该 flag 控制本地 flattened state transition,但在当前 normalized profile 下不足以单独改变 selector-24 最终返回。早分块涉及 `0x133E8 "zygisk" -> find_subrange_bounded -> 0x1340C` 与 `0x1369C "/data/"` 路径分类,但当前 profile 未进入这些子状态。注:真机 killpatched `get(24)=0`,与 normalized unidbg 不同,source semantics 保持 pending。

#### 8.6.10 selector 26 — tracer/debug 结果(High,见 8.3 PR_GET_DUMPABLE)

读 `g_tracerpid_detected_flag` 于 `0x114CC`,真机/校正后 `0`;unidbg 未校正时因 `PR_GET_DUMPABLE=1` 误为 `1`。真机 `ro.debuggable="0"`、`ro.secure="1"`,`get(26)=0`。

#### 8.6.11 其余 selector 的实时检查源(`native_get_env_detection_flags_latest.c` confirmed)

具体如下:

- `ro.debuggable`:属性为 `1` 则 dirty(`0x1138C`)。
- `ro.secure`:期望 `1`,异常或 `0` 为 dirty(`0x11478`)。
- `g_tracerpid_detected_flag`:由 `scan_status_tracerpid` 返回并并入 get。
- `/sys/fs/selinux/enforce`:打开/读或 `fstatat` fallback(`0x14BC8/0x14C08`);non-enforcing 或坏读状态贡献 selector 结果。
- `/system/bin/install-recovery.sh`、`/vendor/bin/install-recovery.sh`、`init.svc.ota_cleanup`、`init.svc.flash_recovery`、`init.svc.vendor.flash_recovery`:recovery/OTA service artifact。

selector 10(install-recovery 双路径)、11(`ro.crypto.state="encrypted"`)、12/13(`dalvik.vm.dex2oat-flags` 空 + `0x170EC("inline-max-code-units=")==0`)、15(magisk_patched.img/TWRP/thanos/taichi 全缺)、18(`/system/addon.d` 缺)的真机取值与判定见 8.10 汇总。

Magisk/app_process 全局 merge 是 selector 路由里的 reader 侧:

```asm
0x11b28: ADRP X8, g_magisk_path_seen_flag
0x11b2c: ADRP X9, g_system_bin_app_process_flag
0x11b30: LDRB W8, [g_magisk_path_seen_flag]
0x11b34: LDRB W9, [g_system_bin_app_process_flag]
0x11b3c: ORR W8, W8, W9
0x11b40: TST W8, #1
0x11b54: CSEL W9, ... ; found 0xE41B4475 : clean 0xD332019E
\```

还原:`dirty = g_magisk_path_seen_flag | g_system_bin_app_process_flag;`。PATH magisk reader:

```asm
0xe984: ADRP X8, g_path_magisk_found_flag
0xe988: LDRB W8, [g_path_magisk_found_flag]
0xe98c: MOV W9, #0x4475
0xe994: MOVK W9, #0xE41B,LSL#16
0xe998: STR W8, [SP, var_1684]
\```

Riru/Magisk/Zygisk/memfd marker 是一组路由检查而非单 strcmp:helper `0x1C378 sub_1C378`(contains)、`0x1CC7C sub_1CC7C`(suffix)、`0x26C6C bounded_range_compare_at_offset`。selector 5 的 Xposed 警告来自这一路由组,不是单条比较。Zygisk 检测以多处 bounded range scan 出现:`0xFCA0` lowercase `zygisk` 经 `string_view_contains_bytes`,`0x12AE8/0x12C3C`、`0x1328C/0x133DC` 重复 bounded substring scan。

#### 8.6.12 `0x170EC` / `0x18BAC` 返回极性

`0x170EC resolve_dalvik_property_area`:构造 `/dev/__properties__/u:object_r:%s:s0`,先试 `exported_dalvik_prop` 再 `dalvik_config_prop`,用 `read_full_retry_eintr` 读属性区,经 `sub_1C63C` 搜文本;命中返回 `1`,miss/失败返回 `0`。callsite `0xF4F4`:`CMP W0,#0; CSET W8,NE; STR W8,[SP+var_1688]`,非零=本地正向 flag。callsite `0x1169C`:返回入 `W23` 进 dex2oat inline-property 状态机,非直接 boolean(pending)。

`0x18BAC check_proc_selinux_context`:callsite `0x15160`(`0xE564`)helper 返回直进 funnel(selector 20);callsite `0x15DA0`(`0x15C48`)helper 返回 OR 进第二道 dirty 聚合(`0x15DC4`),`W0!=0` 走 zero-output 分支。

---

### 8.7 linker/loader 完整性扫描:`scan_linker_loader_integrity 0x1D8AC`

范围 `0x1D8AC`-`0x25170`,size `0x78C4`;7329 指令、1274 基本块;主 dispatcher `0x1DA58`,register-backed state in `W8`。由 `0xE564` 在 `0xEB24` 唯一调用(selector 17 路径)。

#### 8.7.1 返回语义陷阱

需注意:多个"看似最终值"其实是诊断中间值:

- 权威 scanner 返回是栈变量 `var_4B8`,在 `0x250C8` LDR,`0x250E8` RET。
- `byte_2C738` **不是**最终 dirty 结果,是深 linker/soinfo 路径的 cached availability gate。
- `0x1F114` 写的 `1` 是 maps/linker 一致性扫描的中间 staged 候选,不是最终判定。

直接栈访问点:

```asm
0x1DA50 STR WZR, [SP+var_4B8] ; 清最终返回候选
0x1F114 STR W9, [SP+var_4B8] ; 存临时 scan/mismatch flag (W9=1)
0x250C8 LDR W0, [SP+var_4B8] ; 加载权威最终返回
0x250E8 RET
\```

v10 unidbg trace 的"矛盾"解释:`0x1F100 scan_result_count_w8=2`、`0x1F114 stores_result_flag_w9=1`,但 `0x250C8 var_4B8=0`、`0x250E8 ret=0`。`0x1F114` 写 1 后,函数仍可经 clean/guard 路径在 `0x250C8` 前清/覆盖 `var_4B8`。所以 selector 17 的 `0x1F114` 探针只是 phase 探针,不是 verdict 探针。

`0x1F114` 中间 flag 来源:

```asm
0x1E6C4 STR W12, [SP+var_4BC]
0x1EFDC MOV W8, #2
0x1EFE0 STR W8, [SP+var_4BC] ; 迭代器对 exhausted/equal 时 var_4BC=2
0x1F0F4 LDR W8, [SP+var_4BC]
0x1F100 CMP W8, #2
0x1F10C CSEL W8, 0x4CC45691, 0x0C7CF20E, EQ
0x1F114 STR W9, [SP+var_4B8] ; W9 = 1
\```

#### 8.7.2 OLLVM 恢复状态

递归 Miasm run 命令与边界:`recursive_deflatten.py --rva 0x1D8AC --end 0x25170 --max-layers 16`,在 layer 11 故意中断,只作 graph evidence 不作 patch。代表性恢复 dispatcher:

| Layer | Dispatcher | Entry | State | 结果 |
|-|-|-|-|-|
| 1 | `0x1DA58` | `0x1D8AC` | `X8` | 26 states/25 transitions/10 rewrites/6 trampolines/8 unresolved;stage=PASS,dry=FAIL |
| 6 | `0x1F56C` | `0x1F42C` | `X15` | 13/12/8/3/1;stage=PASS,dry=FAIL |
| 7 | `0x1E4BC` | `0x1E44C` | `X9` | 12/6/3/1 sink/2;stage=PASS,dry=PASS |
| 9 | `0x1DE4C` | `0x1DDDC` | `X9` | 等价 layer7;stage=PASS,dry=PASS |
| 10 | `0x1E100` | `0x1D8AC` | `X8` | 5/5/2 sinks/3;stage=PASS,dry=PASS |

主要 blocker:`LDARB W8,[X8]` 出现在 `0x1D8D4` 与 `0x1DD14`,当前 Miasm lifter 未实现 `LDARB`,注入 havoc 使部分边保守;需 trampoline 的层 dry-run 失败;`0x2478C`/`0x24878` 附近有 code/data 边界警告。`0x1D8AC` 序言 asm:

```asm
0x1d8ac: STP X29, X30, [SP,#var_60]!
0x1d8c4: SUB SP, SP, #0x560
0x1d8c8: ADRP X8, byte_2C708
0x1d8d4: LDARB W8, [X8] ; lifter 不支持,recovery 注入 havoc
\```

stage_verify:`smap_states=26, unique_case_bodies=25, transitions=25, case_b_rewrites=10, twoway_trampolines=6, unresolved_edges=8, preserve_dispatcher=true`。current patch stance:safe for graph/comments,not safe as full IDB/file deobfuscation patch yet。

#### 8.7.3 maps/ELF/linker phases 与字符串 pivot

字符串与角色:

\```
0x2BFA0 "/proc/self/maps" 运行时 map 源
0x2BF94 "r" fopen 模式
0x2BF84 "r--p" 只读私有 map 过滤
0x2BF8C "r-xp" 可执行私有 map 过滤
0x2BFB0 ".strtab" ELF section 查找
0x2BFB8 ".symtab" ELF section 查找
0x2C000 "ro.build.version.sdk" SDK-gated loader/soinfo offset
0x2C018 "__dl__ZL4vdso"
0x2C030 "__dl__ZNK6soinfo10get_sonameEv"
0x2C050 "__dl__ZNK6soinfo12get_realpathEv"
0x2C0D0 "__dl__ZL18g_ld_preload_names"
0x2C0F0 "__dl__ZL13g_ld_preloads"
0x2C110 "__dl__ZL6somain"
0x2C120 "__dl__ZL6solist"
0x2C130 "/linker" maps-path needle 用于发现 linker mapping
0x2C140 "/data/misc/apexdata/com.android.art/dalvik-cache/"
0x2C278 "libriru" 对 path/name 缓冲的子串 needle
\```

maps 解析阶段:`fopen("/proc/self/maps","r")` -> `getline` -> `strtoul(lineptr,endptr,16)` 解析首地址 -> 按 `r-xp`(xref `0x1FF7C/0x1FF8C/0x2017C/0x20188`)与 `r--p`(xref `0x1FAF4/0x1FCE0/0x1FCEC`)分类 -> 用 `heap_buffer_reserve_or_alloc`/`heap_buffer_append_or_copy`/`memmove`/`memcpy` 建内部 vector。ELF/symbol 阶段:检查 `.strtab`/`.symtab`,说明 scanner 不只找 maps 文本子串,还建模 ELF/module 元数据并用 symbol/string table 结构验证。

linker-global 阶段缓存写入:

\```
0x21EF8 qword_2C710 = "/linker" pivot 附近 linker/module 查找的 deref 结果(indexed solist/soinfo 数组基)
0x21F7C qword_2C718 = "__dl__ZL6somain" deref 结果
0x21F98 qword_2C720 = "__dl__ZL13g_ld_preloads" 查找结果
0x21F9C "__dl__ZL18g_ld_preload_names" 紧接经 list insertion/lookup 处理,不直存 qword_2C720
\```

注:旧简写"`qword_2C718=g_ld_preloads`/`qword_2C720=g_ld_preload_names`"已校正为上表。这些 qword 也被 `0xE564` 读:`qword_2C710` 于 `0xFE14/0x13B74`、`qword_2C718` 于 `0xFE1C/0x13B6C`、`qword_2C720` 于 `0x12628/0x12668`。soinfo helper:`0x243E8` 解析 `soinfo::get_realpath`,`0x24408` 解析 `soinfo::get_soname`,存进 `off_2C728`/`off_2C730`。

SDK-gated soinfo layout:读 `ro.build.version.sdk` -> `atoi` -> 恢复 C 显示 SDK≥26 vs 旧布局分支,next 指针与 realpath/soname 访问 SDK 敏感。helper:`sub_26144@0x26144` 建 soinfo entry vector(`a1[0..2]`=begin/current/end,从 `qword_2C710` 起,follow `qword_2C280 + current_soinfo` 的 next 指针);`sub_1BD50@0x1BD50` 是长度感知字典序 less-than(min(len) memcmp,相等则短串在前);`linker_module_list_insert_or_lookup@0x1ACB8` 用它做有序模块/符号 list 插入查找。

#### 8.7.4 byte_2C738 availability gate 逻辑

```asm
0x24AA0 LDR X8, qword_2C710
0x24AAC LDR X9, qword_2C718
0x24AB4 CMP X8, #0
0x24AB8 CSET W8, NE
0x24ABC CMP X9, #0
0x24AC0 AND W9, W25, W8
0x24DEC AND W8, W21, #1
0x24DF4 STRB W8, [byte_2C738]
\```

即 `byte_2C738 = prior linker/vdso/soinfo availability bit && qword_2C710!=0 && qword_2C718!=0`。控制流分叉:

\```
0x1DFF4 reads byte_2C738
 != 0 -> state 0xDB8D1127 -> 0x1F020 deep scan path
 == 0 -> state 0x68EA1291 -> 0x1DA4C clear path
\```

`byte_2C708`/`byte_2C709` 是 `__cxa_guard` 风格 lazy-init 守卫(用 `pthread_mutex_lock`/`pthread_cond_wait`/`pthread_cond_broadcast` 与 guard ownership syscall),不是环境检测(串 `0x1e908 "__cxa_guard_acquire"`)。

#### 8.7.5 libriru needle flow

`qword_2C278` 由 `decrypt.efb9da7eacd14797` 初始化,IDB 当前解码为 `libriru`,在 scanner 内作子串 needle:

\```
0x1D004/0x1D008/0x1D014 decrypt/init refs
0x1DDC4 qword_2C278 地址实体化
0x1DF10/0x1DF1C 作 substring needle 读取
0x1E434 备路径地址实体化
0x1E580/0x1E58C 作 substring needle 读取
\```

#### 8.7.6 unidbg FAKE_LINKER 实验与坑

plain unidbg `get(17)=-1` 是 harness artifact:缺 bionic linker 内部,在 `0x24830 LDR X8,[X9,X8]`(`qword_2C710==0`)处 `Read memory failed: address=0x0, size=8`(592-614)。所有缓存 linker 指针为零:`q2C710=0, q2C718=0, q2C720=0, q2C728=0, q2C730=0`。

`MAHOSHOJO_FAKE_LINKER=true` 模型(env 控制,默认关):分配假 `qword_2C710` solist 数组/假 soinfo/假符号;按符号名 hook `gnu_hash_lookup_or_guard_helper@0x25170`;hook 两个 `BLR X8` soinfo callsite——`0x1DBC4` -> `get_realpath(soinfo*) -> "/apex/com.android.runtime/bin/linker64"`,`0x1EED0` -> `get_soname(soinfo*) -> "linker64"`。

校准坑:callsite hook 必须 resume 在 `PC=callsite+4`(用 stale LR 会重入错状态造假循环);hook range 可能在下一条指令也触发,需精确地址判断;guest scanner 后续在 `0x1E7B8` 对 vector begin 指针调 `.free`,该指针对 guest libc 无效,harness 仅当 `X0==fakeVectorEntries` 时跳过这一次 free。早期单假 soinfo 导致 `get_soname` 无限循环(outer dispatcher 在 `0x548F821F`/`0x851B15D2` 循环),因 scanner 期望真实 soinfo/solist 遍历有终止边。

校正后正常返回:

\```
0x1EED0 soinfo::get_soname(fake_soinfo) -> "linker64"
0x1DBC4 soinfo::get_realpath(fake_soinfo) -> "/apex/com.android.runtime/bin/linker64"
0x1E7B8 skips fake vector free for ptr=0x12044000
0x1F100 scan_result_count_w8 = 2
0x1F114 temporarily stores scan result flag W9 = 1
0x250C8 return candidate var_4B8 = 0
0x250E8 scan_linker_loader_integrity returns W0 = 0
\```

caller 验证:

```asm
0xEB24 calls scan_linker_loader_integrity
0xEB28 receives W0 = 0
0xEB30 CMP W0, #0
0xEB40 CSEL W9, clean_state=0x1B7CD6F9, bad_state=0x80537E2D, EQ
0xEB4C briefly stores local scan17 flag var_1688 = 1
0x15758 final path later loads var_1640 = 0
0x15794 returns get(17) = 0
\```

边界声明:这验证静态路径并移除 unidbg 误报,但不是真机绕过证明;真机应仍对比 `/proc/self/maps`、linker 符号、solist 布局、Frida 加入的可执行映射。

#### 8.7.7 Frida 检测候选总结

该 scanner 通过组合检测 Frida:`/proc/self/maps` 中额外可执行/可读映射、linker solist/soinfo 与 maps 行不匹配、preload/preload-name 元数据、缺失或异常的 vdso/linker 符号解析、SDK 特定 soinfo 布局不一致。仅隐藏 `/proc/self/maps` 字符串可能不够,若 linker 内部仍暴露不一致 module view;仅 patch `get(17)` 返回则丢失诊断信号。这正是空 Frida attach 能在 selector 级 hook 前就污染环境采样的原因。

---

### 8.8 `get2`(0x15798)与 `check([B)`(0x15C48):两道 dirty gate + SHA3 sink

#### 8.8.1 `native_get2_detection_string 0x15798`

range `0x15798`-`0x15C48`,size `0x4B0`。入口调 `scan_status_tracerpid`(`0x157E0`),读 `g_apk_signature_result`(`0x157E4`)、`g_initarray_state_seed`(`0x157E8`)、`g_mount_data_suspicious_flag`(`0x157F8/0x1581C`)。dirty 态返回空串。selector 21 返回 build fingerprint fragment(经 `build_device_fingerprint_string@0x16F7C`,`0x1592C`);selector 22 返回 `readlink("/proc/%d/ns/mnt")`(串 `0x15AE8`,经 `sub_16F08`/`0x15AF8` 格式化,`strdup` 后 NewStringUTF,`0x15BE8`)。真机 confirmed:

\```
get2(21) = "google/flame/flame:13/TP1A.221005.002/9012097:user/release-keys"
get2(22) = "mnt:[4026532672]"
\```

`build_device_fingerprint_string 0x16F7C` 拼接:`ro.product.brand` / `ro.product.name` / `ro.product.device` : `ro.build.version.release` : `ro.build.id` : `ro.build.version.incremental`(后者还读 `ro.build.type`、`ro.build.tags`)。

#### 8.8.2 `native_check_byte_array 0x15C48`:两道 dirty gate 全列

range `0x15C48`-`0x16240`,size `0x5F8`;唯一字符串 `0x15F84 "vvb_rikka"`。入口调 `scan_status_tracerpid`(`0x15C74`),`GetArrayLength`(`0x15CA8`,输入须≥32 字节才到 digest 路径)。

第一道 gate:

\```
g_system_bin_app_process_flag & 1
g_magisk_path_seen_flag & 1
g_path_su_found_flag & 1
g_apk_signature_result != 1
g_initarray_state_seed != 0
input byte array length < 32
\```

第一道 gate 全局读取 asm:

```asm
0x15cac LDR W8, g_apk_signature_result
0x15cb0/0x15cbc LDR W9, g_initarray_state_seed
0x15cd0/0x15ce0 LDRB W10, g_path_su_found_flag
0x15cdc/0x15cf4 LDRB W9, g_magisk_path_seen_flag
0x15cec/0x15cf8 LDRB W11, g_system_bin_app_process_flag
\```

第二道 gate,从 `check_proc_selinux_context` 检查后开始(`0x15DA0`,注释 "Second dirty gate starts after /proc SELinux context check"):

\```
g_mount_data_suspicious_flag & 1
g_apk_sig_or_path_suspicious_flag & 1
g_mount_proc_overlay_seen_flag & 1
g_app_data_path_seen_flag & 1
g_app_process_seen_flag & 1
g_runtime_init_status != 0
check_proc_selinux_context(...) != 0
g_dex2oat_inline_result == 1
g_maps_uid_or_pid_value == 0
g_tracerpid_detected_flag != 0
\```

第二道 gate 全局读取 asm:

```asm
0x15da4/0x15da8 LDR W8, g_runtime_init_status
0x15dac/0x15db4 LDR W10, g_dex2oat_inline_result
0x15db0/0x15dbc LDRB W9, g_app_process_seen_flag
0x15db8/0x15dc0 LDR W12, g_maps_uid_or_pid_value
0x15dcc/0x15ddc LDRB W11, g_app_data_path_seen_flag
0x15dd8/0x15de0 LDR W10, g_tracerpid_detected_flag
0x15df0/0x15df4 LDRB W12, g_mount_proc_overlay_seen_flag
0x15e08/0x15e0c LDRB W10, g_apk_sig_or_path_suspicious_flag
0x15e18/0x15e1c LDRB W9, g_mount_data_suspicious_flag
\```

任一 gate 命中 -> dirty 路径:`memset(byteArrayElements, 0, length)` 然后 `ReleaseByteArrayElements(..., mode=0)`,Java 收到全零数据。

#### 8.8.3 SHA3 干净路径

clean 态:

\```
SHA3-256(input_byte_array || "vvb_rikka" || build_fingerprint)
\```

关键调用:

\```
0x15E70 build_device_fingerprint_string
0x15F80 sha3_256_absorb_update(input)
0x15FAC sha3_256_absorb_update("vvb_rikka")
0x15FC4 sha3_256_absorb_update(fingerprint)
0x161A8 keccak_f1600_permute ; 最终 Keccak-f[1600]
0x161F0 BLR X8 ; 写回 Java byte[] 前 32 字节
\```

SHA3 内部:`0x19744 sha3_256_absorb_update`(sponge absorb,context layout `+0`partial word/`+8`25 lanes/`+208`byte offset/`+212`lane index/`+216`capacity words),`0x19D64 keccak_f1600_permute`(24 轮 theta/rho/pi/chi/iota)。该 sink 是多个缓存检测影响外部可见输出的汇聚点。

---

### 8.9 Java 结果管线:W3 / Hn / Ei / Fi + UI 映射表

结果管线:

\```
App.get/Binder get
 -> W3 local UI sample
 -> Hn service sample
 -> Ei combines W3/Hn/other checks
 -> Fi stores final flags
 -> Hf/No render UI
\```

关键文件:`jadx_momo_base/sources/defpackage/{C0783zi,W3,Hn,Ei,Fi,Hf}.java`、`jadx_momo_res/resources/res/values-zh-rCN/strings.xml`。

W3 本地采样构造:`new W3(get(1),get(2),get(4),get(5),get(7),get(8),get(9),get(10),get(11),get(13),get(14),get(15),get(17),get(18),get(19),get(23),get(24),get(25),get(26),get(27))`。字段映射:`a=get(1) b=get(2) c=get(4) d=get(5) e=get(7) f=get(8) g=get(9) h=get(10) i=get(11) j=get(13) k=get(14) l=get(15) m=get(17) n=get(18) o=get(19) p=get(23) q=get(24) r=get(25) s=get(26) t=get(27)`。`W3.u` 标本地采样无效若任一值为负或 `W3.g != Os.getuid`,故 `get(9)` 必须保持真实 UID。

Hn service 采样选择子 `1,2,6,7,8,10,11,13,14,16,17,18,19,23,24,25,26,27`:`a=get(1) b=get(2) c=get(6) d=get(7) e=get(8) f=get(10) g=get(11) h=get(13) i=get(14) j=get(16) k=get(17) l=get(18) m=get(19) n=get(23) o=get(24) p=get(25) q=get(26) r=get(27)`。

UI 警告映射:

| UI 文案 | 资源 | Fi 字段 | 原因 |
|-|-|-|-|
| `找到 Xposed 框架。` | `0x7f100037` | `Fi.e` | `W3.d / App.get(5)` 被强制 `1`;真实干净值 `0`。 |
| `Seccomp 未开启。` | `0x7f100034` | `Fi.l` | service `Hn.j / Gi.get(16)` 为 `0`;健康值 `1`。 |
| `服务无响应` | service bind 链 | — | `MahoService.onBind` 当 `App.get(9) % 100000 < 90000` 返回 null。 |

service respawn loop 根因:`MahoService.onBind` 内 `if (App.get(9) % 100000 >= 90000) return this.d; return null;`。返回 null 导致隔离进程无 owner 被系统拆除、client 重试、循环。修法是 hook onBind 直返 `this.d`,**不要**全局强改 `App.get(9)`(强改 99000 过 onBind uid gate 但破坏 `W3.g==Os.getuid`)。

passing run 应有的干净日志:

\```
W3.<init> raw=0,0,0,0,0,0,10238,0,0,0,0,0,0,0,0,0,0,0,0,0
Hn.<init> raw=0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0
C0153et.<init> detail=false,false,false,false,false
Fi.<init> argc=22 args=0,false,...(全 false)
Bf.k Fi code=0 w=false ...
No.x Fi code=0 w=false ...
\```

解读:`Fi.a==0` 无 fatal code;`Fi.w==false` 无主环境损坏标志;`C0153et.f==false` 无 detail 标志;所有渲染结果标志 false。

---

### 8.10 检测面汇总表(selector → state → source → 真机值)

本表合并静态 V1 与 Frida active trace 两路数据。真机列为 killpatched active trace(0x15188+0x1D8AC 已补丁),unidbg 列为 `PR_GET_DUMPABLE=0` normalized profile。

| Sel | state 常量 (var) | source 解读 | 真机 | unidbg | 证据 |
|-|-|-|-|-|-|
| 1 | `var_1694=0xD737282B` | 通用 root/mount/init 缓存状态,merge pending | 0 | 0 | Static route |
| 2 | `var_16B8=0xBCAEFA94` | pending | 0 | 0 | Static route |
| 3 | `var_1670=0x950DD849` | pending | 0 | 0 | Static route |
| 4 | `var_1674=0x1878DC28` | pty/devpts 行为探针,polarity pending | 1 | -1 | Static+unidbg |
| 5 | `var_1698=0x5071E485` | `g_runtime_init_status` Xposed wrapper | 0 | 0 | High |
| 6 | `var_16BC=0x8254A6F4` | pending;unidbg 撞不支持 syscall NR=148@0x10D08 | -1 | -1 | Static route |
| 7 | `var_167C=0xF1DFFFDD` | 含 mount/proc/global 状态,pending | 1 | 0 | Static route |
| 8 | `var_16C4=0x54D3AB00` | pending | 0 | 0 | Static route |
| 9 | `var_16C0=0x46C7E55F` | UID/进程身份值,须 == Os.getuid | 10238 | -1 | Static+Java |
| 10 | `var_16C8=0x4D618E31` | install-recovery.sh 双路径 access | 0 | 0 | Dynamic |
| 11 | `var_1678=0x84757517` | `ro.crypto.state="encrypted"` | 0 | 0 | Dynamic |
| 12 | `var_1690=0x4E97B23A` | dex2oat-flags 空 + `0x170EC("inline-max-code-units=")==0` | 0 | 0 | Dynamic |
| 13 | `var_1680=0xF0B5DC41` | 同 12 dex2oat inline leg | 0 | 0 | Dynamic |
| 14 | `var_16D0=0x5FB4FE12` | `access("/dev/socket/adbd")==0` dirty | 1 | 0 | High |
| 15 | `var_16CC=0x7F594D70` | magisk_patched.img/TWRP/thanos/taichi 全缺 | 0 | 0 | Dynamic |
| 16 | `var_16D4=0xA497C8A2` | SIGSYS seccomp 缓存位,service 健康值 1 | 0(UI) | 0 | High |
| 17 | 路由 state `0x325F5313`,`0xEB24->0x1D8AC` | linker/loader 完整性 scanner | 0(bypass) | 0(fakelinker) | High |
| 18 | `var_16A4=0x06CB80B9` | `access("/system/addon.d")==-1` | 0 | 0 | Dynamic |
| 19 | `var_16B4=0xBC2DD379` | `verifiedbootstate != "green"` dirty | 1 | 0(green) | High |
| 20 | `var_16A8=0x0DAB1E44` / `var_16AC=0xE4CBE4CE` | `check_proc_selinux_context` 直传 | 0 | 1 | High(source) |
| 21 | 无独立 get(I) state | 默认/无效链,真实数据在 get2(21) | -1 | -1 | Med-high |
| 22 | 无独立 get(I) state | 默认/无效链,真实数据在 get2(22) | -1 | -1 | Med-high |
| 23 | `var_16AC=0x572B38FF` | pending | 0 | 0 | Static route |
| 24 | `var_16E4=0x69603CC3` | app-data/maps path 分类器,merge pending | 0 | 1 | Static+unidbg |
| 25 | `var_16B0=0xE50C82CD` | APK/path suspicious(读 `g_apk_sig_or_path_suspicious_flag`@0xF550) | 0 | 0 | Med-high |
| 26 | `var_16E0=0x9BDFEEFD` | `g_tracerpid_detected_flag` tracer/debug | 0 | 0 | High |
| 27 | `var_16DC=0x59AAEC75` / `var_16D8=0x131421A8` | Android log/framework marker scan,mapping pending | 0 | 0 | Static route |

极性提醒:多数 dirty selector 用 `0`=clean,但并非全是 dirty boolean;`get(9)` 是身份/UID 值;service 端 `get(16)` 是健康正向位(`1` 期望);`get(21)/get(22)` 整数结果不可当环境判定。

最新全局 snapshot(killpatched active sweep):

\```
g_initarray_state_seed=0 g_apk_signature_result=1
g_dex2oat_inline_result=4294967295 g_mount_proc_overlay_seen_flag=0
g_mount_data_suspicious_flag=0 g_magisk_path_seen_flag=1
g_app_process_seen_flag=0 g_system_bin_app_process_flag=0
g_app_data_path_seen_flag=0 g_maps_uid_or_pid_value=55176
g_apk_sig_or_path_suspicious_flag=0 g_path_su_found_flag=0
g_path_magisk_found_flag=0 g_sigsys_seccomp_probe_seen=0
g_tracerpid_detected_flag=0 g_runtime_init_status=0
\```

---

### 8.11 KPM(C+E)/Frida 分工

未明确。现有 Momo 逆向分析全部围绕 libmahoshojo.so 的静态/unidbg/Frida 逆向,**没有任何 KPM(内核模块)章节、没有 C 检测器/E 检测器编号、没有 riskhider/APatch KPM 与 Frida 的分工映射**。因此本样本的 "KPM(C+E)/Frida 分工" 在现有 Momo 逆向分析里无对应内容,逐项标注为"未明确",不予补编。

现有分析给出的"分工"仅是动态验证策略层面的工具选择(非内核/Frida 治理分工):

- Frida 版本:本目标用 `16.5.7`(`.frida1657`)更稳,`17.x` 在 AppZygote/service 时序更易破坏;selector sweep 临时用过 `17.8.0`(496-509)。
- 远程 attach:用 `frida -H 127.0.0.1:8888`,不用 `frida -U`(USB attach/spawn 撞 Gadget/closed-connection)。
- unidbg 定位:受控模拟,复现 `/proc/status`、`/proc/mountinfo`、`/proc/maps` 行为而不引入 Frida 扰动。

若后续要做内核层/Frida 治理分工,需另起逆向,与现有分析无承接关系。

---

## 九、深度逆向(四)Launch(com.xff.launch)

>
> 本章对 `com.xff.launch`(launch_v1.1.3.apk)内置的 Native 检测库 `lib/arm64-v8a/liblaunch.so` 做系统性拆解(pending / 未明确处均标注)。
> 证据来源:对 `liblaunch.so` 的逆向分析;Java 源码取自 JADX 对 `com.xff.launch` 的反编译(classes5.dex / classes4.dex)。
> 证据等级:给出 RVA 的为强证据;反编译标"(内联)"的如实转述并标注"(内联)";未给出的标"未明确"。
>
>
>

---

### 9.0 总体概览

liblaunch.so 是一个**纯防御型反 Root / 反 Hook / 反调试 / 反模拟器检测库**,通过 JNI 暴露给 Java 层 `com.xff.launch.detector.NativeDetector` 调用。它本身**未见返回值签名 / 防篡改聚合,也无攻击性逻辑**,只负责"采集证据 + 返回布尔/字符串"给上层风控逻辑。

反编译对它的定位:

```python
这是一个纯防御型反 Root / 反 Hook / 反调试 / 反模拟器检测库,通过 JNI 暴露给
Java 层 com.xff.launch.detector.NativeDetector 调用。它本身无攻击性逻辑、对自身返回值也无防篡改聚合,
只负责"采集证据 + 返回布尔/字符串"给上层风控逻辑。
\```

导入表特征印证此定位:大量 `access / lstat / stat / readlink / opendir / readdir / __system_property_get / ptrace / dl_iterate_phdr / syscall / dlopen / dlsym`,无加密、无网络上报(仅有 `socket/connect/inet_addr`,用于个别端口探测,见 第9.19节)。

最终结论:liblaunch.so 是一套工程完整、但对自身结果无防篡改的检测探针集合:它具备系统库完整性校验、函数序言与 SMAPS hook 探针(见 9.11–9.13),但没有对 native 返回值的签名或防篡改聚合,也无代码混淆。价值在于"多维度采集 + 自带对照组",整体强度取决于 Java 风控层如何聚合与校验这些原始信号。

---

### 9.1 样本指纹

| 项目 | 值 | 证据 |
|-|-|-|
| 模块名 | `liblaunch.so` |  |
| 架构 | ARM64 (AArch64),APK 内同时提供 armeabi-v7a / x86 / x86_64 |  |
| 镜像大小 | `0x36AA0` |  |
| MD5 (arm64) | `5fa41d87db4c614f25494134b9dcf14c` |  |
| SHA256 (arm64) | `c23d8fc6ae1e37f43616f612f59e80f078d4804b80443ccade2b21b6824dbe66` |  |
| 函数总数 | 550(命名 324) |  |
| 字符串总数 | 771 |  |
| 主要语言 | C++(libc++ `__ndk1`,大量 `std::string` / `stringstream`) |  |
| JNI 导出数 | 约 100 个,全属 `com.xff.launch.detector.NativeDetector`(外加 1 个 `MainActivity.stringFromJNI` demo 桩) |  |
| APK 实测 native 方法声明数 | **100 个**(`grep -c "native " NativeDetector.java` = 100) | 实测 |

补充:`AndroidManifest.xml`、`classes.dex`(11.4 MB,含 Kotlin 运行时)以及 `lib/{arm64-v8a,armeabi-v7a,x86,x86_64}/liblaunch.so` 多架构变体均存在于源件目录。另外,armeabi-v7a/x86/x86_64 为**同源多架构编译,逻辑一致**。

---

### 9.2 整体架构:Native / Syscall 双实现设计

该库几乎每个检测点都提供两个变体:

| 变体后缀 | 实现方式 | 例子 |
|-|-|-|
| `...Native` | 调用 **libc 封装函数**(`access` / `stat` / `open` / `readlink`) | `checkSuFilesNative` → `access` |
| `...Syscall` | 直接 **`syscall` 裸系统调用**,绕过 libc | `checkSuFilesSyscall` → `syscall(__NR_faccessat,…)` |

`checkSuFilesNative` 与 `checkSuFilesSyscall` 共享同一份 SU 路径表(`sub_197AC`),**唯一区别是探测原语**。反编译对照:

```c
// Native (0x1AD7C)
if (!access(v2, 0)) { /* 命中 */ }

// Syscall (0x1C108)
if (!linux_eabi_syscall(__NR_faccessat, -100 /*AT_FDCWD*/, v2, 0, 0)) { /* 命中 */ }
\```

**设计意图:** 若攻击者只 Hook 了 libc 层(Frida/Substrate 的常规做法),`...Native` 会被骗过,但 `...Syscall` 直接走 SVC,Hook 不到 ⇒ 上层只要发现"两个变体结果不一致",即可判定 libc 被 Hook。这是一种**自带对照组的反 Hook 策略**。

这一设计在 Java 侧被升级为三层模型(见 第9.3节),`...Syscall` 拿到的对照值与 `...Native` 的比对结果直接成为"层间矛盾 = Hook 信号"的判据。

---

### 9.3 JAVA || NATIVE || SYSCALL 三层信任模型(Java 代码原样摘录)

native 的 Native/Syscall 双实现,在 Java 侧被升级为**三层模型** `DetectionLayer = { JAVA, NATIVE, SYSCALL }`。枚举定义(`model/DetectionLayer.java`,实测原样):

```java
package com.xff.launch.model;

public enum DetectionLayer {
 JAVA,
 NATIVE,
 SYSCALL
}
\```

每个检测点封装为 `model/DetectionItem`,三层各存一个布尔(`Map<DetectionLayer, Boolean> layerResults`)。写入接口:

```java
public void setLayerResult(DetectionLayer layer, boolean detected) {
 this.layerResults.put(layer, Boolean.valueOf(detected));
}
\```

聚合逻辑核心 —— **取信任度最高且为真的结果(SYSCALL > NATIVE > JAVA)**:

```java
public boolean getMostTrustworthyResult {
 if (this.layerResults.containsKey(DetectionLayer.SYSCALL) && this.layerResults.get(DetectionLayer.SYSCALL).booleanValue) {
 return true;
 }
 if (this.layerResults.containsKey(DetectionLayer.NATIVE) && this.layerResults.get(DetectionLayer.NATIVE).booleanValue) {
 return true;
 }
 return this.layerResults.containsKey(DetectionLayer.JAVA) && this.layerResults.get(DetectionLayer.JAVA).booleanValue;
}
\```

注意:这本质就是一个**短路 OR**——任一层为真即判风险,只是按 SYSCALL→NATIVE→JAVA 的优先级返回。它并未对返回值做任何签名/防篡改(见 第9.21节 弱点 2)。

**三层结果不一致 → 本身就是 Hook 信号**:

```java
public boolean hasInconsistentResults {
 if (this.layerResults.size < 2) {
 return false;
 }
 Boolean first = null;
 for (Boolean result : this.layerResults.values) {
 if (first == null) {
 first = result;
 } else if (!first.equals(result)) {
 return true;
 }
 }
 return false;
}
\```

判"是否检出"则是任一层为真:

```java
public boolean isDetected {
 return this.layerResults.values.stream.anyMatch(new Predicate {
 @Override
 public final boolean test(Object obj) {
 return ((Boolean) obj).booleanValue;
 }
 });
}
\```

**这正是 第9.2节 native 双实现设计的"消费端"**:`getMostTrustworthyResult` 让裸 syscall 层拥有最高话语权(libc 被 Hook 也骗不过它);`hasInconsistentResults` 一旦发现 JAVA/NATIVE/SYSCALL 分歧,就在详情后追加 `(检测层不一致)`——层间矛盾被当作额外的入侵证据。

`HookDetector` 中对两个聚合方法的实际调用:

```java
if (item.getMostTrustworthyResult) { ... }
...
if (item.hasInconsistentResults) { ... }
...
boolean finalResult = item.getMostTrustworthyResult;
Log.d("HookDetector", "getMostTrustworthyResult: " + finalResult);
\```

---

### 9.4 检测点分类清单(约 100 个 JNI)

库导出约 100 个 JNI 函数(实测 NativeDetector.java native 声明计数 = 100)。下表为按机制分类的全量清单(实测 `grep "native " NativeDetector.java` 逐条;分类沿用)。

**完整 native 方法清单(实测原样,100 条):**

```java
// —— 时序基准(6)
public native long benchmarkLibcAccess(int i);
public native long benchmarkLibcOpenat(int i);
public native long benchmarkLibcStat(int i);
public native long benchmarkSyscallAccess(int i);
public native long benchmarkSyscallOpenat(int i);
public native long benchmarkSyscallStat(int i);
// —— Root/框架 文件目录类
public native boolean checkAPatchNative;
public native boolean checkAPatchSyscall;
public native String checkAllSystemLibrariesIntegrity;
public native boolean checkAndroidRuntimeIntegrity;
public native boolean checkAnonymousExecutableMemory;
public native boolean checkAppProcessNative;
public native boolean checkAppProcessSyscall;
public native boolean checkArtHooksSyscall;
public native boolean checkDebuggerNative;
public native boolean checkDebuggerSyscall;
public native boolean checkEmulatorNative;
public native boolean checkEmulatorSyscall;
public native boolean checkFileIntegritySyscall(String str);
public native boolean checkFridaNative;
public native boolean checkFridaSyscall;
public native boolean checkFunctionHook(String str, String str2);
public native boolean checkHiddenMapsSyscall;
public native boolean checkInlineHooksSyscall;
public native boolean checkKernelSUNative;
public native boolean checkKernelSUSyscall;
public native boolean checkLSPosedMemoryNative;
public native boolean checkLSPosedMemorySyscall;
public native boolean checkLSPosedNative;
public native boolean checkLSPosedSyscall;
public native boolean checkLSPosedSystemWide;
public native boolean checkLibartIntegrity;
public native boolean checkLibcHooksSyscall;
public native boolean checkLibcIntegrity;
public native boolean checkLibraryHooksNative;
public native boolean checkLibraryIntegrity(String str);
public native boolean checkMagiskNative;
public native boolean checkMagiskSyscall;
public native boolean checkMemoryHooksNative;
public native boolean checkMemoryHooksSyscall;
public native boolean checkMemoryIntegrityNative;
public native boolean checkMemoryIntegritySyscall;
public native boolean checkMountInfoNative;
public native boolean checkMountInfoSyscall;
public native boolean checkMountNamespaceNative;
public native boolean checkMountNamespaceSyscall;
public native String checkProcFileSyscall(String str);
public native boolean checkPtraceNative;
public native boolean checkQemuNative;
public native boolean checkQemuSyscall;
public native boolean checkRiruNative;
public native boolean checkRiruSyscall;
public native boolean checkRiruZygiskNative;
public native boolean checkRiruZygiskSyscall;
public native boolean checkRootHidingNative;
public native boolean checkRootHidingSyscall;
public native boolean checkSmapsIntegrity;
public native boolean checkSuFilesNative;
public native boolean checkSuFilesSyscall;
public native boolean checkSukiSUNative;
public native boolean checkSukiSUSyscall;
public native boolean checkSuspiciousAnonMemorySyscall;
public native int checkSuspiciousFdsNative;
public native int checkSuspiciousFdsSyscall;
public native int checkSuspiciousMapsNative;
public native int checkSuspiciousMapsSyscall;
public native boolean checkSuspiciousMountsNative;
public native boolean checkSuspiciousMountsSyscall;
public native boolean checkXposedNative;
public native boolean checkXposedSyscall;
public native boolean checkZygiskNative;
public native boolean checkZygiskSyscall;
public native boolean checkZygoteParentNative;
public native int countAnonymousRwxMemory;
public native int countZygiskModulesSyscall;
public native boolean detectTimingAnomaly(long j, long j2, float f);
public native boolean fileExistsNative(String str);
public native boolean fileExistsSyscall(String str);
public native String getAnonymousRwxDetails;
public native String getBootParam(String str);
public native String getBootParamSyscall(String str);
public native String getBuildPropertyNative(String str);
public native String getBuildPropertySyscall(String str);
public native String getCpuHardware;
public native String getCpuHardwareSyscall;
public native String getCpuSerial;
public native String getCpuSerialSyscall;
public native String getLSPosedDetails;
public native String getSELinuxContextNative;
public native String getSystemProperty(String str);
public native int getTracerPid;
public native String getZygoteInfo;
public native boolean isSymlinkNative(String str);
public native boolean isSymlinkSyscall(String str);
public native String readFileSyscall(String str);
public native String readKernelFile(String str);
public native String readlinkNative(String str);
public native String readlinkSyscall(String str);
public native String realpathNative(String str);
public native String realpathSyscall(String str);
\```

**按机制归类:**

| 类别 | JNI 方法(节选) |
|-|-|
| Root 文件/二进制 | `checkSuFiles{Native,Syscall}`、`checkMagisk{Native,Syscall}`、`checkKernelSU*`、`checkAPatch*`、`checkSukiSU*`、`checkRootHiding*` |
| 挂载/命名空间 | `checkSuspiciousMounts*`、`checkMountInfo*`、`checkMountNamespace*` |
| Xposed / 框架 | `checkXposed*`、`checkLSPosed{Native,Syscall,Memory*,SystemWide}`、`getLSPosedDetails`、`checkRiru{Native,Syscall}`、`checkRiruZygisk*`、`checkZygisk*`、`countZygiskModulesSyscall` |
| Hook 检测 | `checkFridaNative/Syscall`、`checkMemoryHooks*`、`checkLibcHooksSyscall`、`checkArtHooksSyscall`、`checkInlineHooksSyscall`、`checkLibraryHooksNative`、`checkFunctionHook` |
| 内存/匿名页 | `checkAnonymousExecutableMemory`、`checkSuspiciousAnonMemorySyscall`、`countAnonymousRwxMemory`、`getAnonymousRwxDetails`、`checkHiddenMapsSyscall`、`checkSuspiciousMaps*`、`checkSmapsIntegrity` |
| 调试/反调试 | `checkDebugger{Native,Syscall}`、`checkPtraceNative`、`getTracerPid` |
| 模拟器 / QEMU | `checkEmulator{Native,Syscall}`、`checkQemu{Native,Syscall}` |
| 完整性校验 | `checkLibcIntegrity`、`checkLibartIntegrity`、`checkLibraryIntegrity`、`checkAllSystemLibrariesIntegrity`、`checkMemoryIntegrity*`、`checkFileIntegritySyscall`、`checkAndroidRuntimeIntegrity` |
| 时序差分(反 Hook) | `benchmarkSyscall{Openat,Access,Stat}`、`benchmarkLibc{Openat,Access,Stat}`、`detectTimingAnomaly` |
| 进程/环境信息 | `checkZygoteParentNative`、`getZygoteInfo`、`getSELinuxContextNative`、`checkAppProcess*`、`getCpuSerial*`、`getCpuHardware*`、`getBootParam*`、`getSystemProperty`、`getBuildProperty*`、`readKernelFile` |
| 文件原语(给上层复用) | `fileExists*`、`readFileSyscall`、`readlink*`、`isSymlink*`、`realpath*`、`checkProcFileSyscall`、`checkSuspiciousFds*` |

日志 TAG 体现内部模块划分:`RootDetector` / `HookDetector` / `IntegrityDetector` / `EmulatorDetector` / `DebugDetector`(均通过 `__android_log_print` 输出,**便于动态分析时直接 logcat 观察命中项**)。

---

### 9.5 检测点详解 ①:SU / Root 文件扫描(sub_197AC / sub_1AD7C / sub_1C108)

`sub_197AC` 用一次性 guard(`byte_35CF0`)构造一个 `std::vector<std::string>`(`qword_35CD8`..`qword_35CE0`),硬编码以下路径:

```python
/system/bin/su /system/xbin/su /sbin/su
/data/local/su /data/local/bin/su /data/local/xbin/su
/system/sd/xbin/su /system/bin/failsafe/su
/vendor/bin/su /su/bin/su
/system/xbin/busybox /system/bin/busybox
\```

两个变体共享上述路径表,仅探测原语不同:

```c
// checkSuFilesNative → sub_1AD7C(强证据,RVA 0x1AD7C)
if (!access(v2, 0)) { /* 命中:文件可访问 */ }

// checkSuFilesSyscall → sub_1C108(强证据,RVA 0x1C108)
if (!linux_eabi_syscall(__NR_faccessat, -100 /*AT_FDCWD*/, v2, 0, 0)) { /* 命中 */ }
\```

命中后日志:`SU file found (native): %s` / `SU file found (syscall): %s`(`RootDetector` TAG)。

Java 侧补充:`RootDetector` 除调用上述 native 方法外,还在 Java 端用 `PackageManager` 查 Root 管理器、用 `SU_PATHS` 做文件存在性判定。

---

### 9.6 检测点详解 ②:Magisk / KernelSU / APatch / SukiSU / RootHiding 目录探测

各检测器命中 `/data/adb/` 系列特征(`HookDetector` TAG;部分走 `RootDetector`)。`checkMagiskNative` 对应 `sub_1AE08`,以 `/data/adb` Magisk 特征为判据。

同族 native 方法(实测):`checkKernelSU{Native,Syscall}`、`checkAPatch{Native,Syscall}`、`checkSukiSU{Native,Syscall}`、`checkRootHiding{Native,Syscall}`、`checkMagisk{Native,Syscall}`,均成对提供 libc/syscall 双实现。各自具体路径表未逐一展开(逐条路径未明确),但其证据面落在 `/data/adb/` 目录系列。

启发式补充(Java 层):由 **KernelSU/Magisk 的存在推断 ReZygisk**;读 `ro.boot.flash.locked` / `ro.boot.verifiedbootstate` 推断 BootLoader 解锁状态,做加权。

---

### 9.7 检测点详解 ③:Zygisk / ReZygisk 七步探测(checkZygiskSyscall / sub_269C0)

`checkZygiskSyscall`(`sub_269C0`,~0x1D98 字节,强证据 RVA 0x269C0)是全库**最庞大**的检测函数,内含 `[1/7]`…`[7/7]` 七步。探测点样例:

```python
/data/adb/modules/.zygisk
/data/adb/modules/rezygisk
/data/adb/modules/rezygisk/module.prop
…（共 7 组,覆盖 Zygisk/ReZygisk 多种实现）
\```

配套统计接口:`countZygiskModulesSyscall`(返回 int 模块计数)、`checkZygiskNative`(libc 对照)。未逐条列出全部 7 步路径(剩余 4 组路径的精确字符串未明确),但明确"共 7 组,覆盖 Zygisk/ReZygisk 多种实现"。

Java 侧 Zygisk 受限处理:当三层全 false 时,`detectZygisk` 区分"未检出"与"被 SELinux 限制",给出 `UNKNOWN` 状态并提示"把本应用加入 LSPosed 作用域可启用完整检测"——可见这是**面向研究者的自测工具**。

---

### 9.8 检测点详解 ④:Riru 检测(checkRiruSyscall / checkRiruNative)

`checkRiruSyscall` 组合"`/proc/self/maps` 扫描 + 目录存在性"(速查表中标注为"(内联)"):

```python
/data/adb/riru /dev/riru
\```

即:既扫 `/proc/self/maps` 看是否有 riru 注入痕迹,又直接探测 `/data/adb/riru`、`/dev/riru` 两个目录是否存在。配套有 `checkRiruZygisk{Native,Syscall}`(Riru 版 Zygisk 的派生探测)。

---

### 9.9 检测点详解 ⑤:libc 周边 Hook 扫描(checkLibcHooksSyscall / sub_1541C)

全程裸 syscall 读取 maps,然后做**定位 + 窗口扫描**(强证据 RVA 0x1541C):

1. `syscall(openat, AT_FDCWD, "/proc/self/maps", O_RDONLY)` → `read` 最多 0x10000 字节 → `close`;
2. `memchr` 定位字符串 `"libc.so"`(常量 `0x6362696C`="libc" + `0x6F732E63`="c.so");
3. 在 libc 映射所在偏移的 **±2000 字节窗口**内,搜索已知 Hook 框架特征。

Hook 框架特征常量表(原样摘录):

| 特征常量 | 解码 | 含义 |
|-|-|-|
| `0x64697266` + `'a'` | `"frida"` | Frida |
| `0x7461727473627573` + `'e'` | `"substrate"` | Cydia Substrate |
| `0x7962626F6462696C` | `"libdobby"` | Dobby Hook 框架 |

判据:**判断 libc 映射附近是否混入了 Hook 引擎的映射**。注意常量是 ASCII 小端编码,例如 `0x64697266` 按字节序为 `66 72 69 64` = `f r i d`,再拼上 `'a'` 得 `"frida"`;`0x6362696C` = `6C 69 62 63` = `l i b c`。

弱点:仅匹配 `frida/substrate/libdobby` 三个**固定字符串**,改名或匿名映射的 Hook 引擎可规避。

---

### 9.10 检测点详解 ⑥:时序差分检测(benchmark* + detectTimingAnomaly)

成对的基准函数测量"单次调用纳秒数",用 `clock_gettime(CLOCK_MONOTONIC_RAW=4)` 计时,循环 `count` 次取均值。反编译对照(强证据 RVA 0x177F4 / 0x178B4):

```c
// benchmarkSyscallStat (0x177F4):裸 syscall
linux_eabi_syscall(__NR_fstatat, -100, "/system/build.prop", &st, 0);

// benchmarkLibcStat (0x178B4):libc
stat("/system/build.prop", &st);

return (end - start) / count; // 平均每次耗时(ns)
\```

`detectTimingAnomaly(count, totalTime, threshold)`(0x1796C)极简(强证据 RVA 0x1796C):

```c
return count >= 1 && (float)totalTime / count > threshold;
\```

注意 native 签名为 `detectTimingAnomaly(long count, long totalTime, float threshold)`(实测:`public native boolean detectTimingAnomaly(long j, long j2, float f);`),公式中的 `(float)totalTime / count > threshold` 是 **native helper 对入参 `totalTime/count` 做阈值判断**;至于 Java caller 传入的 `totalTime` 是原始耗时、libc 与裸 syscall 的差值还是比值,需看 caller(待补)——因此不宜直接断言为"libc/syscall 比值 > 阈值"。

**原理:** libc 函数若被 inline-hook,会引入额外跳转/trampoline 开销;对比"裸 syscall 耗时"与"libc 耗时"做时序差分、超过阈值 ⇒ 判定被 Hook(是差值还是比值取决于 Java caller 如何构造 totalTime,见 native 签名说明)。对 openat / access / stat 三类高频调用各做一组(对应 `benchmark{Syscall,Libc}{Openat,Access,Stat}` 共 6 个 native 方法)。

Java 侧实参(第9.21节 印证):`detectTimingAnomaly(...,3.0f)`,**迭代 5000 次**——即阈值 3.0、采样 5000 次。`SideChannelDetector` 负责编排这组方法。

---

### 9.11 检测点详解 ⑦:函数级 Inline Hook 检测(checkFunctionHook / sub_2D0B0)

`checkFunctionHook(libName, funcName)` 取两个 Java 字符串,经 `sub_2D0B0` 处理(强证据 RVA 0x2D0B0)。反编译:

```c
h = dlopen(libName, RTLD_NOW);
addr = dlsym(h, funcName);
dlclose(h);
// 检查函数序言指令
// - B 指令 (opcode 0x14000000, 掩码 0xFC000000) → "Inline hook detected: B instruction at +%d"
// - BR 指令 → "Inline hook detected: BR instruction at +%d"
\```

即**反汇编目标函数开头若干指令,若序言被替换为无条件跳转 `B`/`BR`(典型 trampoline 特征)即判定被挂钩**(`IntegrityDetector` TAG)。`B` 指令在 AArch64 的 opcode 匹配值为 `0x14000000`(高 6 位 `000101`),检测时用掩码 `0xFC000000` 取高 6 位后比对;`BR Xn` 是寄存器间接跳转,二者都是 trampoline 把原函数首指令改写成"跳到 hook stub"的典型特征。

Java 侧消费——对 libc.so 五个关键函数逐一检测:

```java
String[][] criticalFunctions = {
 new String[]{"libc.so", "open"},
 new String[]{"libc.so", "openat"},
 new String[]{"libc.so", "read"},
 new String[]{"libc.so", "access"},
 new String[]{"libc.so", "stat"}
};
int length = criticalFunctions.length;
for (int i = 0; i < length; i++) {
 String[] funcInfo = criticalFunctions[i];
 boolean isHooked = hookDetector.nativeDetector.checkFunctionHook(funcInfo[0], funcInfo[1]);
 ...
}
\```

(行413 实测:`boolean isHooked = hookDetector.nativeDetector.checkFunctionHook(libName, funcName);`)这印证:`detectMemoryIntegrity` 对 `libc.so` 的 `open/openat/read/access/stat` 五个关键函数逐一 `checkFunctionHook`。

---

### 9.12 检测点详解 ⑧:库完整性校验(checkLibraryIntegrity / sub_2CD40 及封装)

`sub_2CD40(libName)` 流程(日志可直接观察,强证据 RVA 0x2CD40):

```python
"=== Checking integrity of %s ==="
→ 在 /proc/self/maps 中定位该库的内存映射(否则 "Library %s not loaded in memory")
→ 取磁盘文件路径(否则 "Failed to get path for %s")
→ 比对【内存中字节】 vs 【磁盘文件字节】
→ 一致: "%s integrity check PASSED"
→ 不一致:"!!! INTEGRITY VIOLATION DETECTED in %s !!!"
\```

关键告警字符串(原样,IOC):`!!! INTEGRITY VIOLATION DETECTED in %s !!!`。

封装入口:

- `checkLibcIntegrity` → `sub_2D174`(目标 `libc.so`,RVA 0x2D174)
- `checkLibartIntegrity` → `sub_2D268`(目标 `libart.so`,RVA 0x2D268)
- `checkAllSystemLibrariesIntegrity` → `sub_2DA4C`(RVA 0x2DA4C),**遍历多库并返回违规库名列表字符串**(`NewStringUTF`)给 Java。
- `checkAndroidRuntimeIntegrity`(目标 `libandroid_runtime.so`,实测 native 声明存在; 印证三库一并校验)。

对它校验范围内的库的 `.text` 做运行时改写,会让内存映像与磁盘只读副本产生差异(未被它列入校验的库不在此列),因此这是对抗 inline hook 较强的一层约束。

Java 侧消费:`detectMemoryIntegrity` 对 `libc.so / libart.so / libandroid_runtime.so` 调完整性校验。HookDetector 中的实际日志串:

```java
Log.d("HookDetector", "Checking libc.so integrity...");
...
Log.d("HookDetector", "libc.so result: " + (libcClean ? "CLEAN" : "HOOKED"));
...
detailBuilder.append("• libc.so 被篡改\n");
\```

弱点:完整性比对依赖"能读到干净磁盘副本",若攻击者同时挂钩文件读取路径即可投喂干净字节(本库虽用 syscall 缓解,但仍是单点)。

---

### 9.13 检测点详解 ⑨:SMAPS 代码段完整性(checkSmapsIntegrity / Private_Dirty)

`detectSmapsHook` 调 `checkSmapsIntegrity` 读 `/proc/self/smaps`,检查关键库 `r-xp` 代码段的 **`Private_Dirty > 0`**——在该检测覆盖的 r-xp 代码页内,inline patch 通常会使页 COW、`Private_Dirty` 变正。"几乎无法绕过"是该 app 的 **UI 文案/工程判断**,非本文章断言。

UI 详情串:

```java
item.addDetectionDetail(" SMAPS 分析", "代码段完整性检测",
 "分析 /proc/self/smaps 发现关键库的代码段 (r-xp) 存在 Private_Dirty 页\n\n"
 + "这意味着:\n• 只读代码段被修改\n• 触发了 Copy-on-Write\n• 存在 Inline Hook\n\n"
 + "可能的注入源:\n• Xposed/LSPosed\n• Frida\n• Zygisk 模块",
 DetectionLayer.SYSCALL, "????");

item.addDetectionDetail(" 检测原理", "内存取证技术",
 "SMAPS (Shared Memory Area Stats) 提供了进程内存映射的详细统计信息\n\n"
 + "检测步骤:\n1. 读取 /proc/self/smaps\n2. 定位关键库 (libart.so/libc.so) 的代码段\n"
 + "3. 检查 Private_Dirty 字段\n4. Private_Dirty > 0 → 代码被修改\n\n"
 + "优势: 几乎无法绕过，因为修改只读内存必然触发 COW",
 DetectionLayer.NATIVE, "");
\```

相关 native 入口还有 `checkInlineHooksSyscall`(标"(内联)",走 `/proc/self/smaps` 扫描)与 `checkMemoryIntegritySyscall`(标"(内联)",`/proc/self/maps` + 字节比对)。

---

### 9.14 检测点详解 ⑩:build.prop / 系统属性双路读取(getBuildPropertySyscall / sub_17B24)

裸 syscall `openat("/system/build.prop")` → `read` → 按 `'='` 分割解析 `key=value`,用于读取 `ro.*` 模拟器/调试特征属性(强证据 RVA 0x17B24);另有 `getSystemProperty` 走 `__system_property_get`。两路并存同样用于"libc vs 直接读文件"的交叉验证。

成对方法(实测):`getBuildPropertyNative` / `getBuildPropertySyscall`、`getBootParam` / `getBootParamSyscall`、`getCpuSerial` / `getCpuSerialSyscall`、`getCpuHardware` / `getCpuHardwareSyscall` —— 全部 Native/Syscall 双轨,用于设备指纹与模拟器属性交叉验证(由 `DeviceLegitimacyDetector` 编排)。

伪代码(转述):

```c
// getBuildPropertySyscall (0x17B24)
fd = syscall(__NR_openat, AT_FDCWD, "/system/build.prop", O_RDONLY);
read(fd, buf, ...);
// 逐行按 '=' 分割,匹配请求的 key 返回 value
\```

---

### 9.15 检测点详解 ⑪:模拟器 / QEMU、调试 / 反调试、内存异常(其余成对探针)

以下检测点未做逐条反编译,按 native 声明与分类如实转述(证据级别:native 声明=强证据,内部细节=未明确):

- **模拟器**:`checkEmulator{Native,Syscall}`、`checkQemu{Native,Syscall}`。读 `ro.*` 属性、QEMU 特征文件判定(细节未明确)。
- **调试/反调试**:`checkDebugger{Native,Syscall}`、`checkPtraceNative`、`getTracerPid`。`getTracerPid` 读 `/proc/self/status` 的 `TracerPid` 字段(典型实现;未给反编译,标转述)。
- **匿名可执行内存 / RWX**:`checkAnonymousExecutableMemory`、`checkSuspiciousAnonMemorySyscall`、`countAnonymousRwxMemory`、`getAnonymousRwxDetails`、`checkHiddenMapsSyscall`、`checkSuspiciousMaps{Native,Syscall}`(返回 int 计数)。扫 `/proc/self/maps` 找匿名 `rwx` 段——Frida/动态注入常见痕迹。
- **挂载/命名空间**:`checkSuspiciousMounts{Native,Syscall}`、`checkMountInfo{Native,Syscall}`、`checkMountNamespace{Native,Syscall}`。读 `/proc/self/mountinfo`、对比 mount namespace 找 Magisk overlay/bind-mount 痕迹。
- **可疑 fd**:`checkSuspiciousFds{Native,Syscall}`(返回 int 计数)。扫 `/proc/self/fd` 找指向被删除/可疑文件的描述符。
- **ART / 库 Hook**:`checkArtHooksSyscall`、`checkLibraryHooksNative`、`checkMemoryHooks{Native,Syscall}`。
- **LSPosed 专项**:`checkLSPosedNative/Syscall`、`checkLSPosedMemoryNative/Syscall`、`checkLSPosedSystemWide`、`getLSPosedDetails`(返回详情字符串)。

---

### 9.16 文件原语层(给上层复用的通用工具)

库导出一批"裸文件操作原语",供 Java 层灵活复用,并同样保持 Native/Syscall 双轨:

```java
public native boolean fileExistsNative(String str);
public native boolean fileExistsSyscall(String str);
public native String readFileSyscall(String str);
public native String readKernelFile(String str);
public native boolean isSymlinkNative(String str);
public native boolean isSymlinkSyscall(String str);
public native String readlinkNative(String str);
public native String readlinkSyscall(String str);
public native String realpathNative(String str);
public native String realpathSyscall(String str);
public native String checkProcFileSyscall(String str);
public native String getSELinuxContextNative;
\```

`ReadlinkDetector` 用 `readlink*`/`realpath*`/`isSymlink*` 检查软链接/路径伪装;`ZygoteDetector` 用 `checkZygoteParentNative`、`getZygoteInfo`、`checkAppProcess*` 验证进程血缘。

---

### 9.17 JNI → 内部实现速查表

(合并实测补充)

| JNI 导出 | 内部函数 / RVA | 机制 | 证据 |
|-|-|-|-|
| `checkSuFilesNative` | `sub_1AD7C` | `access` 遍历 SU 路径表 | 强 |
| `checkSuFilesSyscall` | `sub_1C108` | `syscall(faccessat)` 遍历同表 | 强 |
| `checkMagiskNative` | `sub_1AE08` | `/data/adb` Magisk 特征 | 强 |
| `checkZygiskSyscall` | `sub_269C0` | 7 步 Zygisk/ReZygisk 探测 | 强 |
| `checkRiruSyscall` | (内联) | maps + `/data/adb/riru`、`/dev/riru` | 转述 |
| `checkLibcHooksSyscall` | `sub_1541C` (内联描述) | maps 中 libc 周边搜 frida/substrate/libdobby | 强 |
| `checkInlineHooksSyscall` | (内联) | `/proc/self/smaps` 扫描 | 转述 |
| `checkMemoryIntegritySyscall` | (内联) | `/proc/self/maps` + 字节比对 | 转述 |
| `checkFunctionHook` | `sub_2D0B0` | dlsym + 序言 B/BR 指令检查 | 强 |
| `checkLibraryIntegrity` | `sub_2CD40` | 内存映像 vs 磁盘文件比对 | 强 |
| `checkLibcIntegrity` | `sub_2D174` | 同上,目标 libc.so | 强 |
| `checkLibartIntegrity` | `sub_2D268` | 同上,目标 libart.so | 强 |
| `checkAllSystemLibrariesIntegrity` | `sub_2DA4C` | 遍历系统库,返回违规列表字符串 | 强 |
| `benchmarkSyscallStat` | `0x177F4` | `clock_gettime` 计时裸 syscall | 强 |
| `benchmarkLibcStat` | `0x178B4` | `clock_gettime` 计时 libc | 强 |
| `detectTimingAnomaly` | `0x1796C` | native 层 `totalTime/count > 阈值`(Java caller 如何构造 totalTime 待补) | 强 |
| `getBuildPropertySyscall` | `0x17B24` | 裸读 `/system/build.prop` | 强 |

---

### 9.18 IOC / 特征字符串清单

**SU/Root 路径**(第9.5节 全表):

```python
/system/bin/su /system/xbin/su /sbin/su
/data/local/su /data/local/bin/su /data/local/xbin/su
/system/sd/xbin/su /system/bin/failsafe/su
/vendor/bin/su /su/bin/su
/system/xbin/busybox /system/bin/busybox
\```

**Magisk/Zygisk/Riru 目录:**

```python
/data/adb/modules /data/adb/modules/.zygisk
/data/adb/modules/rezygisk /data/adb/modules/rezygisk/module.prop
/data/adb/riru /dev/riru
\```

**proc / 系统接口:**

```python
/proc/self/maps /proc/self/smaps /proc/cpuinfo /system/build.prop
\```

**Hook 框架内存特征字符串:** `frida`、`substrate`、`libdobby`(编码常量见 第9.9节)。

**日志 TAG:** `RootDetector` `HookDetector` `IntegrityDetector` `EmulatorDetector` `DebugDetector`

**关键告警串:** `!!! INTEGRITY VIOLATION DETECTED in %s !!!`、`SU file found (native): %s`、`SU file found (syscall): %s`、`=== Checking integrity of %s ===`、`%s integrity check PASSED`、`Library %s not loaded in memory`、`Failed to get path for %s`、`Inline hook detected: B instruction at +%d`、`Inline hook detected: BR instruction at +%d`

**Xposed/LSPosed 包名与类名(Java 层 IOC,实测 HookDetector.java):**

```python
de.robv.android.xposed.installer de.robv.android.xposed
org.lsposed.manager org.meowcat.edxposed.manager
de.robv.android.xposed.XposedBridge de.robv.android.xposed.XposedHelpers
org.lsposed.lspd.core.Startup
org.lsposed.lspd.hooker.HandleBindAppHooker
io.github.lsposed.lsplant.LSPlant
/system/framework/XposedBridge.jar /system/lib/libxposed_art.so
/system/lib64/libxposed_art.so /system/xposed.prop
\```

**Frida 探测端口:** `127.0.0.1:27042`(timeout=100ms)。

**杂项路径:** `/sdcard/`、`/tmp/`(部分模拟器/可写目录判定)。

---

### 9.19 网络与外部交互

导入仅 `socket / connect / setsockopt / inet_addr / close`,无完整 C2 逻辑,典型用途是探测 **Frida 默认调试端口**(如 27042)或本地回环服务是否可连。无证据表明本库自身进行任何远程上报——上报应由 Java 风控层完成。

Java 侧对应实现:

```java
socket.connect(new InetSocketAddress("127.0.0.1", 27042), 100);
\```

---

### 9.20 Java 层补充逻辑(native 之外)

(实测代码印证)

**`NativeDetector` 门面**:单例(`getInstance`),`static { System.loadLibrary("launch"); }` 加载本库,**约 100 个 native 方法声明与导出表 1:1 对应**,无任何额外逻辑。

**`HookDetector.checkXposedJava`**:

- `PackageManager` 查 `XPOSED_PACKAGES`:

```java
private static final String[] XPOSED_PACKAGES = {
 "de.robv.android.xposed.installer", "de.robv.android.xposed",
 "org.lsposed.manager", "org.meowcat.edxposed.manager"};
\```

- 抛异常读栈帧找 `xposed` 类名;
- `ClassLoader.getSystemClassLoader.loadClass("de.robv.android.xposed.XposedBridge")`;
- `Class.forName("de.robv.android.xposed.XposedBridge")` 取 Bridge 版本。

**LSPosed 内存类探测**:

```java
String[] lsposedClasses = {
 "de.robv.android.xposed.XposedBridge",
 "de.robv.android.xposed.XposedHelpers",
 "org.lsposed.lspd.core.Startup",
 "org.lsposed.lspd.hooker.HandleBindAppHooker",
 "io.github.lsposed.lsplant.LSPlant"};
\```

**`HookDetector.checkFridaJava`**:`Socket.connect("127.0.0.1", 27042, timeout=100)`——探测 Frida 默认端口(对应 native 导入的 `socket/connect/inet_addr`)。

**`checkLoadedDexFiles` / `checkInMemoryDexClassLoader`**:反射 `VMRuntime`/`VMDebug`/`DexFile`,查 `InMemoryDexClassLoader`、`cookie=`,以及 LSPlant/LSPosed 内存类(`org.lsposed.lspd.core.Startup`、`io.github.lsposed.lsplant.LSPlant`)。

**`detectMemoryIntegrity`**:对 `libc.so/libart.so/libandroid_runtime.so` 调完整性校验,并对 `libc.so` 的 `open/openat/read/access/stat` 五个关键函数逐一 `checkFunctionHook`(序言 B/BR 检测,见 第9.11节)。

**`detectSmapsHook`**:`checkSmapsIntegrity` 读 `/proc/self/smaps`,检查关键库 `r-xp` 代码段的 `Private_Dirty > 0`——覆盖到的 r-xp 代码页内 inline patch 通常使页 COW、`Private_Dirty` 变正;"几乎无法绕过"为该 app 的 UI 文案/工程判断,非本文章断言。

**Zygisk 受限处理**:三层全 false 时 `detectZygisk` 区分"未检出"与"被 SELinux 限制",给 `UNKNOWN` 状态并提示"把本应用加入 LSPosed 作用域可启用完整检测"。

**启发式加权**:由 KernelSU/Magisk 推断 ReZygisk;读 `ro.boot.flash.locked` / `ro.boot.verifiedbootstate` 推断 BootLoader 解锁状态。

**检测器编排表**:

| 检测器类 | 负责的组 | 调用的 native(NATIVE/SYSCALL 层) |
|-|-|-|
| `RootDetector` | Root | `checkSuFiles/Magisk/KernelSU/APatch/SukiSU/RootHiding/SuspiciousMounts {Native,Syscall}` + Java `PackageManager` 查 Root 管理器、`SU_PATHS` 文件存在性 |
| `HookDetector` | Hook | `checkXposed/Frida{Native,Syscall}`、LSPosed 组合(`checkLSPosed*`+`checkRiruZygisk*`+`checkAnonymousExecutableMemory`)、`checkZygisk*`、`checkSmapsIntegrity`、`checkLib{c,art}Integrity`+`checkAndroidRuntimeIntegrity`+`checkFunctionHook` |
| `EmulatorDetector` | 模拟器 | `checkEmulator/Qemu{Native,Syscall}` |
| `DebugDetector` | 调试 | `checkDebugger{Native,Syscall}`、`checkPtraceNative`、`getTracerPid` |
| `SideChannelDetector` | 侧信道 | `benchmark{Syscall,Libc}{Openat,Access,Stat}` + `detectTimingAnomaly`、SELinux(`readFileSyscall`/`getBuildPropertyNative`) |
| `ReadlinkDetector` | 软链接/路径 | `readlink*`/`realpath*`/`isSymlink*` |
| `ZygoteDetector` | Zygote | `checkZygoteParentNative`、`getZygoteInfo`、`checkAppProcess*` |
| `DeviceLegitimacyDetector` | 设备指纹 | `getCpuSerial*`/`getCpuHardware*`/`getBootParam*`/`getSystemProperty` |

---

### 9.21 强项与弱点(防御视角)

**强项:**

1. Native/Syscall 双轨 + 时序差分,对单纯的 libc 层 Hook 有较强对照能力;
2. 库完整性(内存 vs 磁盘字节比对)对 inline hook / .text patch 是硬约束,NOP 单点检测无法消除差异;
3. `checkFunctionHook` 直接看序言 B/BR,能抓 trampoline;
4. SMAPS `Private_Dirty` 检测利用 COW 物理特性,UI 自述"几乎无法绕过"。

**弱点 / 绕过面:**

1. **大量关键路径 / IOC 明文硬编码**,无混淆,可被静态枚举并在内核/挂载层隐藏对应路径;
2. 多数核心 boolean 检测入口**各自独立返回**,未见返回值签名 / 防篡改聚合——上层 Java 若被 Hook,可逐个返回 `false`(本库未保护自身返回值);`getMostTrustworthyResult` 只是简单 OR(第9.3节),不签名;
3. **大量 `__android_log_print` 明文日志**会泄漏命中逻辑,便于逆向定位与逐项消音;
4. 完整性比对依赖"能读到干净磁盘副本",若攻击者同时挂钩文件读取路径即可投喂干净字节(本库虽用 syscall 缓解,但仍是单点);
5. libc Hook 扫描仅匹配 `frida/substrate/libdobby` 三个固定字符串,改名或匿名映射的 Hook 引擎可规避。

**Java 源码对 native 结论的印证 / 修正**:

| native 推断(第9.1节–第9.19节) | Java 源码印证 |
|-|-|
| 纯检测、无攻击、无自身保护 | `NativeDetector` 无混淆,UI 直接展示结果,逻辑透明 |
| Native/Syscall 双轨为反 Hook 对照组 | `getMostTrustworthyResult`(syscall 优先)+ `hasInconsistentResults`(层间矛盾=Hook 信号)坐实 |
| 时序反 Hook(native 阈值 3.0) | `detectTimingAnomaly(...,3.0f)`,迭代 5000 次;Java caller 如何构造 totalTime 待补(见 9.10) |
| `socket/connect` 用于探端口 | `checkFridaJava` 连 `127.0.0.1:27042` |
| SMAPS/完整性较难绕(目标自述) | app 的 UI 文案称"修改只读内存必触发 COW,几乎无法绕过"——为其工程判断,非本文章断言 |
| 更像研究 / 自测工具形态(是否用于线上 SDK 未验证) | 大量 `Log.d/w` 全程打点 + UI 可视化 + "加入 LSPosed 作用域"自测提示 |

**补充结论:** Java 层没有引入任何对 native 返回值的签名/防篡改聚合——`getMostTrustworthyResult` 只是简单 OR。因此"无返回值防篡改聚合"这一判断在 Java 侧得到加强:整套系统是一套多维度、但对自身完全透明的检测能力演示,适合作为反作弊检测点的参考实现,而非可直接抗对抗的生产级方案。

---

### 9.22 对抗视角(KPM / resetprop / mount-ns 治本对照)

结合本库设计,从反检测工程(KPM 内核层 + LSPosed/HMA binder 层 + resetprop 属性层)角度对每一检测面给出"治本"判断。证据级别:本节为对抗推论,非逐条断言,凡无直接证据支撑的标注。

**(1) 为何 KPM 必须保证 Native 与 Syscall 结果一致。**
本库的核心反 Hook 武器是"双轨对照"(第9.2节)与三层模型的 `hasInconsistentResults`(第9.3节)。若反检测只在 libc 层(`access`/`stat`)做手脚,`...Native` 返回 false 而 `...Syscall`(走 `__NR_faccessat` SVC)返回 true,层间矛盾立即被当作 Hook 信号上报。因此**对这类文件/stat/access 的 Native/Syscall 双轨检测,若要不改 app 业务逻辑、做通用环境层隐藏,就应在内核 syscall 入口统一生效**(KPM 在 `faccessat`/`fstatat`/`openat` 等 syscall 层拦截),使 libc 路径与裸 syscall 路径看到完全相同的结果,否则会触发它的层间一致性检查。注意这只覆盖双轨的 Native/Syscall 面;Launch 还有 Java 层路径(PackageManager 查包、Socket 探 frida 端口、ClassLoader 查 Xposed 类、属性读取),那些不在 syscall 双轨里,得另由 binder 层(HMA)/属性层(resetprop)处理。对应记忆条目"Anti-detect: general not per-app""ZygiskDetector su defeat"(syscall 级隐藏、stat dev/ino 伪装而非 ENOENT)在此同样适用:SU 文件、`/data/adb/*`、`/dev/riru` 的隐藏都要在 syscall 层做,且 Native/Syscall 双路径表现一致。

**(2) resetprop 补哪块。**
`getBuildPropertyNative`/`getBuildPropertySyscall`(第9.14节)+ `getSystemProperty`(`__system_property_get`)+ `getBootParam*` 构成"属性双路 + property 服务"三路读取。resetprop 修改 `__system_property` 内存区只能盖住 `getSystemProperty` 这一类函数;**`getBuildPropertySyscall` 直接裸读 `/system/build.prop` 文件,resetprop 盖不住**——需要在文件层(bind-mount 一个干净 build.prop)或 KPM 在 `openat("/system/build.prop")` 读路径上做内容替换,才能让"property 服务值"与"文件值"一致。`ro.boot.flash.locked` / `ro.boot.verifiedbootstate`(第9.20节 启发式)同理需要 property + bootparam 两路一并处理。

**(3) 挂载/命名空间隐藏。**
`checkSuspiciousMounts*`/`checkMountInfo*`/`checkMountNamespace*`(第9.15节)读 `/proc/self/mountinfo` 找 overlay/bind-mount 痕迹。对应记忆"RASP detection layer division":这类要靠 mount namespace 隔离(在独立 mount-ns 内清理 Magisk overlay)而非改返回值;残留收敛到统一包名。

**(4) 完整性 / SMAPS 是 KPM 也难以绕过的一层。**
`checkLibraryIntegrity`(内存 vs 磁盘字节比对,第9.12节)+ `checkSmapsIntegrity`(Private_Dirty,第9.13节)针对的是"在被采样的映射/窗口内,改了 .text 通常会留下物理痕迹"。反检测若用 inline hook 改它**所校验**的 libc/libart 的 `.text`,在这些被采样的页上内存与磁盘会不一致、对应页 `Private_Dirty>0`。**治本是不要改目标库 .text**:用 KPM 在 syscall 层做隐藏(不碰用户态代码段),或用 PLT/GOT 重定向而非 inline patch(GOT 改写是否会被本库捕获,目前未明确;从当前材料看未见 GOT 完整性检测,可能是可利用缝隙)。若必须 inline hook,需同时挂钩 `openat`/`read`(给完整性校验投喂干净磁盘字节)且让 smaps 的 Private_Dirty 归零——后者在用户态几乎不可行,只能内核层伪造 smaps 输出。

**(5) Frida 端口与匿名 RWX。**
`checkFridaJava` 连 `127.0.0.1:27042`(第9.19节)→ 改 Frida 端口即可;`checkLibcHooksSyscall` 仅匹配三个固定字符串(第9.9节)、`countAnonymousRwxMemory` 扫匿名 rwx(第9.15节)→ Frida gadget 改名 + 用文件映射而非匿名 rwx 段可规避。这些是本库相对薄弱、对抗成本最低的面。

**对抗优先级小结:** 最难绕的是完整性/SMAPS(第9.12节/第9.13节)与双轨一致性(第9.2节/第9.3节);最易绕的是固定字符串 libc 扫描与 Frida 端口(第9.9节/第9.19节)。KPM 的价值在于:对文件/stat/access 这类 **Native/Syscall 双轨**检测,在内核统一 syscall 出口让两轨看到一致视图,从根上消解本库的对照组设计。**注意属性链不在此列**——`getBuildPropertySyscall` 裸读 `/system/build.prop`,resetprop 盖不住,属性面仍需 resetprop / bootparam / 文件层另行配套。

---

*分析基于 arm64-v8a 变体;armeabi-v7a/x86/x86_64 为同源多架构编译,逻辑一致。Java 源码取自 JADX 对 `com.xff.launch` 的反编译(classes5.dex/classes4.dex)。*

---

## 十、KPM 架构(最终落地方案)

### 10.1 五个功能,一个门控

`riskhider.c` 在内核 `sys_call_table` 层挂 12 个 hook(实测 init 日志的 syscall 号):

\```
+faccessat 48 +faccessat2 439 +openat 56 (A before-hook:命中黑名单前拦)
+newfstatat 79 +statx 291 (E after-hook:返回后改 dev/ino/nlink)
+readlinkat 78 (map_files after-hook:按解析后 target 判黑名单)
+execve 221 +execveat 281 (B before-hook)
+read 63 +pread64 67 (C after-hook)
+statfs 43 +fstatfs 44 (D after-hook)
done: 12/12 hooks
\```

- **A 路径隐藏**:命中黑名单 → `-ENOENT`。
- **B exec 阻断**:execve/execveat 命中 → `-ENOENT`。
- **C /proc 内容清洗**:read/pread64 读 `/proc/<pid>/{maps,smaps,status,cmdline,mounts,mountinfo}` 与 SELinux `*_file_contexts`,对 maps/smaps/mounts/mountinfo 整行删除命中行,对 status/cmdline/file_contexts 同长度擦除。
- **D statfs 伪造**:overlay/tmpfs 的 f_type 改成 ext4。
- **E su 伪造**:newfstatat/statx 在 `/debug_ramdisk` 上**成功返回** `/` 的 dev/ino + nlink=2。

门控 `should_hide`(v1.4.x):

```c
if (g_global) {
 int appid = uid % 100000;
 candidate = (appid>=10000 && appid<=19999) || // 普通 app
 (appid>=90000 && appid<=99999); // 隔离进程(见 第11.3节)
} else if (g_target_uid>=0 && uid==g_target_uid) candidate = 1;
else if (g_target_comm[0]) candidate = ci_contains(get_task_comm(current), g_target_comm);
if (!candidate) return 0;
/* 命中门控后,可信工具(APatch/HMA 管理器)永不隐藏 —— 见 第11.5节 */
\```

运行时一行配置,APatch 持久化重放;`mode=java`(A/B/D 关、C/E 开)、`mode=native`(A/B/C/D/E 开——E 是 Hunter/Launch 抹 `/debug_ramdisk` st_dev 的必需项,见第十二/十五节)。

### 10.2 三个构建坑(都来自 KP 加载器真实报错)

1. `unknown symbol: memset / kp_rw_mem / tlsf_*` —— KP 加载器只链接 KP 自己导出的符号。对策:去堆(栈分块擦除),`memset/memcpy/memmove` 自带在 `compat_mem.c`。
2. `unsupported RELA relocation: 311`(R_AARCH64_ADR_GOT_PAGE)—— NDK clang 默认 PIC 走 GOT,KP 不支持。对策:`-fno-pic -fno-pie -mcmodel=small`,且**别加 `-fno-plt`**。
3. KPM 的 load/control supercall 需**真 SuperKey**(`is_authed`),字面量 "su" 不行。

---

### 10.3 KPM 作为分析正确性的验证(闭环方法)

逆向阶段对每个检测点只能给出"推断:app 测的是这个差异"。推断对不对,需要一个**判决实验**:在 KPM 里只抹平这一个差异,看 app 的判定是否随之翻转。

- 抹平后 app 从"报"变"不报" ⇒ 这个差异点找对了。
- 抹平后 app 仍报 ⇒ 分析漏了 / 找错了,回去重逆,直到找到真正的差异点。

这把"逆向结论"从纸面推断变成了可证伪的实验。第十一节那串迭代史,本质全是这个闭环在跑:

| 分析推断(app 测的差异) | KPM 抹平手段 | 验证现象 | 反推结论 |
|-|-|-|-|
| ZygiskDetector 测 `/debug_ramdisk` 的 st_dev | E:newfstatat 改 st_dev | 仍报 Su Found | 推断不全,还要改 st_ino(v1.2.6→1.2.9) |
| Hunter 测 `/proc/mounts` 的 APatch/dex2oat 行 | C:line-drop | uid 10247 干净但仍报 | 隔离进程 uid 90000 漏网 → 补门控(v1.3.6) |
| C 已清 maps 文本 | C:read 清洗 | map_files 仍泄漏 libzygisk | 差异有第二条出口 readlinkat → 补 `af_readlinkat`(v1.4.0) |
| global 抹平所有 app | global gate | app 卡死 / 自伤 | 抹过头把 app 自己文件也抹了 → 路径自豁免(v1.4.6) |

每一行都是"KPM 抹平 → app 反馈 → 反推分析盲点"的一次迭代。所以 KPM 不只是落地对抗方案,也是检验逆向分析是否到位的标尺。但要把话说准,**这只能证明:在 Pixel 4 / Android 13 / 内核 4.14 / 当前配置 / 当次测试窗口里,这 4 个 app 已被触发的主要检测面都被覆盖了**——不能证明"完整"。理由很实在:① 未触发的分支(本文章标 `△未触发` / 字典级的那些)没被这次实验检验到;② 5.x 内核会唤醒 ZygiskDetector 的 maps 结构块,届时是否还能 C+E 拿下未验证;③ Momo 的 KPM(C+E)逐项覆盖映射在其逆向分析里本就"未明确"(见 第八节)。所以准确表述是"当前环境主要检测面已覆盖",而非"分析完整"。这就是"分析 → KPM 验证 → 落地"闭环的收口。

---

## 十一、迭代加固:每个版本对应一个实测暴露的 bug

### 11.1 su 伪造三次失败(v1.2.6 → v1.2.9)

- v1.2.6 只改 st_dev → 无效(还要 ino)。
- v1.2.7 改 ENOENT → 卡死(app 无 try/catch)。
- v1.2.8 整结构克隆 → 把 `/` 的 `nlink=27` 也克隆,`stat -c %h /debug_ramdisk` 读到 27,`(d>2)` 触发。
- v1.2.9 收敛方案:after-hook 写 `dev@0/ino@8`(=缓存的 `/`)+ `nlink@20=2`;statx 对应 `dev@0x88/ino@0x20/nlink@0x10`。**结果层面**降级为黄色 "Unsupported Kernel"、su/zygisk 未检出;严格说这是结果层收敛——本文章未贴 `[sufake]` firing 改写 dev/ino 的逐条 dmesg(见 第7.13节 残留点)。

### 11.2 dex2oat 误报(v1.3.5)

`dex2oat` 这个词太普通:Hunter 只是拿它在整行里做子串查找,不看它出现在路径哪一段、属于哪种挂载。而本文章测试机(该 Android 12+ 环境)上有一条**正常的系统挂载** `/dev/block/dm-37 /apex/com.android.art/bin/dex2oat32 f2fs ro,…`(设备号 / 文件系统 / 路径细节随设备、ROM、版本而变),里面正好含 "dex2oat",于是被误判成 root 痕迹。修法:把 `dex2oat`、`/appwidget` 也加进 C 的清洗词表,让它把这一行整行删掉;dmesg 实测 `/proc/<pid>/mounts: line-drop 1024 -> 891 bytes`(掉的就是这条 + APatch 那条)。

### 11.3 隔离进程绕过 app-uid 门控(v1.3.6)

Hunter 用 `hunter_server_iso`(uid 90000)隔离进程读 `/proc/mounts`,绕开"只 gate 10000–19999"。实测:

\```
uid 10247(主进程) grep dex2oat/debug_ramdisk/APatch /proc/mounts → 0 (干净)
uid 90000(隔离) 同样 grep → 4 (泄漏)
\```

修法:global 门控加 `appid 90000–99999`。

### 11.4 map_files 旁路整个 C 清洗(v1.3.7 → v1.4.0)

C 清洗的是 `read` 出来的 maps 内容,但 `/proc/<pid>/map_files/` 是一组按地址命名的符号链接,走 `getdents64`+`readlinkat`,不经过 read(maps)。实测 uid 10236 的 map_files 仍 readlink 出 3 个 `libzygisk.so`(源自 Zygisk 注入 zygote、经 fork 的 COW 出现在其 map_files 里):

\```
maps = 0 (C 已清)
smaps = 0 (C 已清)
map_files = 3 ← libzygisk.so 从这里泄漏
\```

第一版(v1.3.8)修错:判断输入路径含 `/map_files/`,但 `ls -l` 用 dirfd+相对名(arg1 是裸条目名)→ 判断永不成立。v1.4.0 改对:**只看 readlinkat 解析出的 target**,target 命中黑名单就 `-ENOENT`。

### 11.5 global 模式自伤连环(v1.4.1 → v1.4.6)

切 `global=1` 后丢了 per-app `pkg=` 自我保护,凡 app 自己路径/maps 含 marker(典型 `wu.Zygisk.Detector` 含 `zygisk`)就把它自己的文件也藏了。最致命的 dmesg:

\```
hide: uid=10236 -> ENOENT /data/misc/apexdata/com.android.art/dalvik-cache/arm64/
 data@user@0@wu.Zygisk.Detector@files@dex@a5e79f160201b3eef3d4b2b6fc28e893.odex
\```

app 加载不了自己编译的 .odex → 卡 Loading / 服务 ANR(Momo、Hunter、ZygiskDetector 一起卡)。`cache/classes.dex`、`files/dex/<md5>.dex` 又正好是 ZygiskDetector 完整性校验文件 → 误报。两轮踩坑:

1. 想用进程身份判"自包名",但 `get_task_comm` 是线程级的——干活的后台线程(Profile Saver、Jit pool)和 `Runtime.exec` 的子进程(`sha256sum`/`toybox`)comm 都不是包名。改 `get_cmdline`(进程级 argv[0]),但**放在 syscall 热路径上,检测器疯狂探测 marker 路径时每次都锁 mmap + 读用户态 argv → 全 app ANR**(v1.4.4 引入、v1.4.5 撤掉的回归)。
2. v1.4.5 正解:**纯路径自豁免**,不查进程身份。app 私有命名空间无条件放行:`/data/data`、`/data/user(_de)`、`/data/misc/profiles`、`Android/data|obb`、`/dalvik-cache`、`/data/misc/gpu`、`/data/misc/apexdata`。安全前提:跨 app 访问这些目录本被 SELinux 挡死,豁免只放过调用方自己的文件;注入物在 `/data/adb` 不在这些根下,照样隐藏。
3. v1.4.6 把同一逻辑补到 C 的按行清洗(`line_has_marker`),修好 ZygiskDetector 的"版本显示"退化(之前 C 把它自己 base.apk/dex 的 maps 行也删了,打乱 mainpage maps-block 解析)。

还有验证方法的教训:每次 GUI 重载,参数框反复掉成空 → `args=""` → `glob=0`,测了半天测的是没生效的模块。对策:让 init 日志打印真实版本号(早期硬编码 `1.2.6` 误导很久),每次重载用 `status` 确认 `glob=1`。

---

## 十二、对抗结果

| App | 包名 | 类型 | 靠什么过 |
|-|-|-|-|
| ZygiskDetector | wu.Zygisk.Detector | Java/MVEL | KPM C+E。**结果层面通过**:黄 "Unsupported Kernel"(4.14 内核上限)、su/zygisk 未检出;`/debug_ramdisk` stat 伪造的逐条 dmesg 可作补证 |
| Hunter | com.zhenxi.hunter | native RASP | KPM 的 C(清洗 mounts/maps/map_files)+ E + TrickyStore(TEE)+ VBMeta(orange);root 文件存在性这一路在该机未触发(全局 A 关)。**机制按 SHA256 `e575` 的二进制逆向;截图机装的是另一构建(SHA256 `ca1d`),只证明该机当前配置下结果通过,RVA/分支需按截图机的二进制复核** |
| Momo | io.github.vvb2060.mahoshojo | native/JNI + Java | 该机截图表现正常;实测配置=全局 C+E。**注:当前未证明 C+E 覆盖 Momo 各检测项,因果机理待补(第八节逐项 KPM 映射标"未明确")** |
| Launch | com.xff.launch | native 检测矩阵 | KPM 的 C+E(覆盖 stat/maps/mounts,并让 libc 与裸 syscall 一致)+ resetprop(属性面)。Java 层 PackageManager / `SU_PATHS` 文件与包存在性在该机靠干净环境 / HMA 或未触发(全局 A 关);裸读 `/system/build.prop` 那一路 resetprop 盖不住,需另证 |

Hunter `orange` 走 VBMeta Disguiser——它默认 `bootloader_props_spoof=false` 不伪装该属性,要手动改 `=true`;`tee check device unlock` 走 TrickyStore——用有效 keybox 在 keystore2 层重签 rootOfTrust(替换出检测器接受的 attestation 链,非伪造 TEE 原签)。

---

## 十三、收尾配置

`v1.4.6`(**外部 `riskhider_kpm` 工作仓库**标记为本地 tag `v1.4.6-stable`;本 doc 归档为其快照,**无此 tag**,见 CHANGELOG)。开机加载参数:

\```
global=1 verbose=1 pathhide=0 execblock=0 fsfake=0 exempt=10245 exempt=10232
\```

全局只开 **C(/proc 清洗)+ E(su 伪造)**;A/B/D 关——A 对 ZygiskDetector 这类脚本检测器无用、且会卡死它们(`Runtime.exec + readLine 到 EOF`),但对 Hunter 这类 native 文件存在性检测可能需按 uid 单独启用;D 让 ZygiskDetector 退化。`exempt` 豁免 HMA(uid 10245)与 APatch 管理器(uid 10232)。配套 TrickyStore + VBMeta Disguiser + resetprop。

为什么不是一套配置打天下:脚本检测器(ZygiskDetector)要 C+E、A 会卡死它;native 检测器(Hunter)需要 A 才能藏 root 文件。最终选"全局 C+E、A/B/D 关"作安全基线。**若某个 native 样本实际命中"文件存在性"检测,仍需针对该 uid/包单独启用 A 或做更窄的路径策略**——TrickyStore/VBMeta/resetprop 只补 TEE / bootloader / 属性面,替代不了 root 文件隐藏。

---

## 十四、踩坑沉淀

1. KP 加载器只认 KP 导出符号;其余 `kallsyms_lookup_name` 运行时解析,且要 `-fno-pic`(别 `-fno-plt`)。
2. 门控到 app 后,凡名字/路径含黑名单标记的**自身文件**都会被自己藏掉致崩 → 按路径根自豁免;**别在 syscall 热路径做 `get_cmdline` 之类锁 mmap/读用户态的操作**(ANR)。
3. 检测器会用**隔离进程(uid 90000+)**和 **`/proc/<pid>/map_files` readlink** 绕过常规门控/清洗,两者都得单独覆盖。
4. in-process Xposed/frida hook 是**可检测**的(hook_framework / 层间不一致)。相比之下,**本轮测试中** KPM(内核)和 system_server 侧 hook **没有在用户态留下被这几个检测器命中的 Frida/Xposed 痕迹**——但这不是"零痕迹":KPM 仍可能有时序、内核符号/模块、异常返回模式、加载日志或内核版本兼容性等可被更强检测利用的痕迹,只是不在本轮这 4 个 app 的检测面里。
5. 逆向结论对着手上这份二进制反复验(别硬编 RVA,函数靠字符串/xref 定位);KPM 重载靠**真实版本号日志**确认,别信 `load` 返回。
6. 分层对抗:syscall→KPM,binder→HMA,属性→resetprop/VBMeta,TEE→TrickyStore。各司其职,不要用一层硬扛另一层。

---

## 十五、深度逆向(五)密钥认证(wu.keyChain.test 2.0.5)—— Key Attestation 检测 + KPM/TrickyStore 双层对抗

>
> 与前四款不同:这是一款 **Key Attestation / TrickyStore 检测器**,光靠 KPM(syscall 层)只能过环境检测,**证书层必须在 keystore2 层用有效 keybox 替换/重签出检测器接受的链 + 二次开发 TrickyStore fork** 才能过。这一章把"环境层 KPM + 证书层 keybox + 反 TrickyStore 源码对抗"的完整链路补进来。
>
>
> 分析/部署设备:Pixel 6 Pro / Android 15 / APatch(与前四款的 Pixel 4 / 内核 4.14 不同;本章所有结论基于此机)。证据等级沿用全文约定。
>
>
>

### 15.0 总体概览

- 载体与 第七节 ZygiskDetector **同族**:易安卓 EIDE 运行器 + `assets/MUS.LOVE`(序列化 MVEL AST)+ `assets/util.dex`(`com.wuying.*` 辅助类);`classes.dex/classes2.dex` 与 ZygiskDetector **字节级同哈希**(Confirmed,SHA-256 一致)。
- 但业务不同:它专做 **Android Key Attestation** 校验(证书链 / 可信根 / RootOfTrust),并内置 **反 TrickyStore 三件套**(keybox 诱饵标记 / ASN.1 标签序 / keystore2 Binder-Parcel 探针)。
- 分层:环境层(root/hook)交给 KPM;证书层(已解锁/诱饵标记/标签序/Parcel 探针)交给"有效 keybox + 自编 TrickyStore fork"。证书层那几项经诊断通过;环境层 rooted/hooked 本文章未单独贴图,按 KPM 设计与无 Frida 运行环境处理(Frida 诊断下会被污染、不作数)。

### 15.1 检测面:3 层 6 点(检测点总表)

| # | 检测点 | 实现位置 | 原理(Confirmed) | 治理层 |
|-|-|-|-|-|
| 1 | rooted | MUS.LOVE mainpage | `Os.stat("/").st_dev != Os.stat("/debug_ramdisk").st_dev`(实测 65030 vs 37) | KPM(syscall) |
| 2 | hooked | MUS.LOVE main 页 | 读 `/proc/self/maps`,`indexOf` 扫 signkiller/zygisk/zloader/frida/lsposed/rwxp/`data/local/tmp`/`data/adb`/docker(多项 OR)+ maps 空/null | KPM(syscall) |
| 3 | 引导已解锁(lock) | util.dex KeyAttestationHelper | attestation 扩展 `RootOfTrust.deviceLocked`(TEE 签名,OID 1.3.6.1.4.1.11129.2.1.17) | keybox / TrickyStore |
| 4 | 诱饵标记(attResult) | util.dex CheckAtt | 生成 `PURPOSE_ATTEST_KEY` 临时键 → 导入自带 `Wuying` keybox 覆盖 alias → 读回查 "Wuying";被 keystore hook 替换则丢标记 → "Tampered Attestation" | fork 改注入 |
| 5 | 标签序(tampered) | util.dex KeyAttestationHelper | `checkTagOrderMisordered`:授权列表 tag 须升序(704≤705、且 tag10 不排在 tag704 之后),乱序=注入痕迹 | fork 改注入 |
| 6 | ErrCheck(fishy) | util.dex ErrCheck(7817 行) | 反射 keystore2 隐藏 AIDL,跑两段 attest-key 链 generateKey,**异常栈含 `android.os.Parcel.createException` 即判 hook**;另有 Parcel 字节指纹(mod-time 签名 `0x1_0000_0001`/`0x18_0000_0001` + 授权槽表 sanity) | fork 改注入 |

1、2 是环境层(内核 stat/maps,syscall 能改);3-6 是证书层(TEE 私钥签名,syscall 改不到,只能 keybox 重签 + 让注入"忠实")。

### 15.2 载体与还原方法(同 第七节 思路)

- `MUS.LOVE` 魔数 `aced0005`(Java 序列化),顶层 `HashMap<页面名, Object[][]>`;条件/表达式是预编译 MVEL2 AST 对象(同 第7.1节)。
- 还原:借 app 自己反序列化,Frida dump `Utils.LOVES` AST → 转伪代码(`out/dumps/*.complete.pseudo`,三页 main/mainpage/mainpage1 全 AST 实证,无 `<unparsed>` 残留);编译后的 accessor 右值(如 `Os.stat`)用运行时 hook `HashMap.put` 取真实值。
- util.dex 字符串混淆 = **StringFog**(XOR key 写死成 charset 名 `"UTF-8"`),写通用解码器一把解开;ErrCheck 另用每类 `short[]` 池 + 控制流平坦化,需 `jadx --comments-level debug` 出 smali 回退。

### 15.3 util.dex 四个辅助类(证书层检测的实体)

- `KeyAttestationHelper.start(ctx)`:生成 EC 密钥取证书链 → 解析 attestation 扩展 → 可信根公钥逐字节比对(硬编码 Google/AOSP/Knox 根)→ `checkTagOrderMisordered` 查标签序 → 产出 raw(含 DeviceLocked/VerifiedBootState/...)。
- `CheckAtt.start()`:**keybox 诱饵标记**,内嵌 `Wuying` keybox base64,导入读回查标记。
- `TeeAttestation.Start()`:反射 `KeyInfo.isInsideSecureHardware()` 查 TEE 硬件背书。
- `ErrCheck.start()`:**keystore2 Binder/Parcel 级探针**,反射隐藏 AIDL(`android.system.keystore2.IKeystoreService`),动态代理截 generateKey reply Parcel,双探针(错误栈 + Parcel 字节指纹)。

### 15.4 环境层对抗(1、2)—— 复用 riskhider KPM

- 模块 E(sufake):`newfstatat`/`statx` 对 `/debug_ramdisk` 返回 `/` 的 `st_dev`/`st_ino`、`nlink=2`,**stat 成功不 ENOENT** → `rooted=false`。正是 第7.13节 / 第十节 那招。
- 模块 C(procfilter):整行过滤 `/proc/self/maps` 里 frida/zygisk/lsposed/magisk/`data/adb` 等 → `hooked=0`(同时隐藏 TrickyStore 自身的 `/data/adb/tricky_store` 痕迹)。
- 门控:`uid=10278 sufake=1 procfilter=1 pathhide=1 fsfake=1`。**踩坑**:args 必须半角 ASCII——曾打成全角 `uID＝10278` 导致 `uid=-1` 未生效(dmesg `recv "uID＝10278"` + `uid=-1` 一眼看穿)。

### 15.5 证书层对抗(3)—— TrickyStore + keybox 筛选

- `deviceLocked` 是 TEE 签名,改不了 → 用**有效 keybox** 重签一份 `deviceLocked=true / VerifiedBootState=Verified` 的 attestation(TrickyStore 本质)。
- keybox **批量校验脚本**:对手上 22 个 keybox 解析证书链 → 查序列号是否命中 app 的 `assets/list.json` 吊销名单(1654 条,Google CRL 格式)→ 查叶/根证书是否过期 → 查根是否真 Google 根。结论:仅 **keybox11** 未吊销 + 未过期 + Google 硬件根可用(keybox10 根证书已过期淘汰,其余均已吊销)。
- 装 TrickyStore + keybox11 → `引导已解锁` 消失;但触发 app 的反 TrickyStore(4/5/6)→ 进入 15.6。

### 15.6 反 TrickyStore 对抗(4、5、6):二次开发 TrickyStore fork

原版 TrickyStore 自 v1.1.0 起**闭源** → fork 开源 **TrickyStoreOSS** 自行编译,逐个"逆原理 → 改源码 → 重编 → 推设备 → Frida 复测信号翻转"迭代,落地 **3 个 patch**(零 app 专属硬编码,纯按 keystore 行为判断):

| Patch | 检测点 | 根因(Confirmed) | 修法 | 改动文件 |
|-|-|-|-|-|
| ① | 诱饵标记 attResult | CheckAtt 用 `PURPOSE_ATTEST_KEY` 把 fork 诱进"生成缓存"路径,再 `setEntry` 导入 Wuying 覆盖,而 fork 不复查 import → getKeyEntry 吐回缓存的 keybox,丢了 "Wuying" | hook **importKey** 事务:alias 被重新导入时清掉 `keys`/`keyPairs`/`skipLeafHacks` 缓存 → getKeyEntry 回落到 `hackCertificateChain` 的 OID 守卫路径(leaf 无 attestation OID 的 Wuying 证书原样放过) | `SecurityLevelInterceptor.kt` |
| ② | 标签序 tampered | `hackAttestExtension` 把 704/705/706/718/719 **追加在授权列表末尾且降序**、且与原有标签**重复** → 破坏了检测点5(15.1)所查的 704/705/706 升序 | 去重(剔除原有的 704/705/706/718/719)+ 加入新值后**按 tagNo 升序排序** | `CertificateHack.kt` |
| ③ | ErrCheck fishy | fork 对 attest-key 链(`purpose 含 ATTEST_KEY(7)` 或带 `attestationKeyDescriptor`)走"生成模式"失败 → keystore2 抛 `-8 Failed to load attest key / Alias must be specified` → 经 `Parcel.createException` 浮现 → 探针命中 | needHack 分支对 attest-key 链 generateKey **放行(Skip)给真实 keystore2 让它成功**;真实 attestation 仍由后续 getKeyEntry leaf-hack 重签产出,deviceLocked 不受影响 | `SecurityLevelInterceptor.kt` |

定位手法:Frida hook `HashMap.put` 看 attResult/tampered/fishy 真实翻转;hook `android.os.Parcel.createException` 抓到 keystore2 的 attest-key 加载错误(确认是错误栈探针而非 Parcel 指纹);派子 agent 深读 ErrCheck 7817 行确认探针是"两段 attest-key 链 + 异常栈含 createException 即判 true"。

构建坑(都来自真实报错):

1. 系统 `java-21-openjdk` 是 **JRE 无 javac** → 用 Android Studio 自带 **JBR(JDK 21)**。
2. `git clone` 没拉 submodule **LSPlt** → CMake `add_subdirectory` 失败 → `git submodule update --init`。
3. **SELinux 限 /data/local/tmp exec** → frida-server 从 `/data/adb` 启动。
4. 组件齐套:SDK platform-36 / build-tools-36 / NDK 28.2.13676358 / CMake 3.31.4 / Gradle 9。

### 15.7 验证结果(Frida 诊断,attestation 层)

```python
attResult = Normal Attestation tampered = false fishy = false lock = true
tricky/except/exception = -1
\```

**证书层与反 TrickyStore 相关诊断项(attResult / tampered / fishy / lock / tricky;lock 属 attestation RootOfTrust)全部通过**。注:`rooted`/`hooked`(环境层 1/2)在 Frida 诊断里会被注入污染(maps 含 frida),**不以此处为准**;rooted/hooked 本文章未单独贴图,按 KPM 设计与无 Frida 运行环境处理。

### 15.8 通用性(与前四款的本质区别)

- fork 的 3 patch 判断依据是**通用 keystore 行为**(importKey 事务 / attest-key 链 / 标签序),零包名/类名/诱饵标记硬编码 → **对同类 import-canary / tag-order / attest-key-chain probe 具备迁移性**;但不同 app 的 keystore 调用时序、异常判断、证书解析细节可能不同,仍需按目标 app 复测。换 app 主要改配置(KPM uid 门控、TrickyStore target.txt、keybox 放置)。
- 边界:覆盖"诱饵标记 / 标签序 / attest-key 链探针 + 环境层"几类主流手法;全新手法需照同法再补。
- 这一款把对抗从"以 KPM(syscall 面)为主、辅以现成层工具(TrickyStore/VBMeta/resetprop)"延伸到"在 keystore2 服务层二次开发注入器":证书层 deviceLocked 只能 keybox 重签,KPM 够不到,这是与前四款本质不同的一层。

### 15.9 残留与边界

- 证书层对抗构件就两样:打了 3 个 patch 的 TrickyStoreOSS fork(改动见 15.6)+ 一个未吊销的有效 keybox(环境层另有 KPM,见 15.4)。
- KPM 重启后是否自载,取决于 APatch 配置。
- 第五款的证书层 / 反 TrickyStore 诊断是在 Frida 下测的;rooted/hooked 会被注入污染;本文章未单独贴其无 Frida 截图,按 KPM 设计与无 Frida 运行环境处理。

---

## 十六、最终成果(实测截图)

设备:Pixel 4(flame)/ Android 13 / kernel 4.14.276 / APatch,配置见第十三节(全局 C+E + TrickyStore + VBMeta Disguiser + resetprop)。下面是前四款检测器在该机上的实测结果(截图只证明这些样本在当前配置下通过;逆向机制按各章基线,跨版本 RVA/分支需复核)。第五款密钥认证部署在 Pixel 6 Pro / Android 15,以 KPM + 自编 TrickyStore fork 通过证书层 / 反 TrickyStore 相关诊断项(诊断见 15.7),环境层 rooted/hooked 未单独贴图,按 KPM 设计与无 Frida 运行环境处理;下图中"谷歌硬件根证书""引导加载程序已锁定"两条均通过,证书链全"有效"、可信执行环境"正常"。

### Hunter(com.zhenxi.hunter)

![Hunter 实测:未发现风险](https://bbs.kanxue.com/upload/attach/202607/662006_5HHUH7TEN3PQQFS.png)

### ZygiskDetector(wu.Zygisk.Detector,1.7.5)

![ZygiskDetector 实测:Unsupported Kernel](https://bbs.kanxue.com/upload/attach/202607/662006_ZGFDWYUCMARRYQY.png)

### Momo(io.github.vvb2060.mahoshojo,4.4.1)

![Momo 实测:环境正常](https://bbs.kanxue.com/upload/attach/202607/662006_447NR6NVP5RJCN5.png)

### Launch(com.xff.launch)

![image](https://bbs.kanxue.com/upload/attach/202607/662006_7BB5BHNBV2CRR25.png)

### 密钥认证(wu.keyChain.test,2.0.5)

![image](https://bbs.kanxue.com/upload/attach/202607/662006_723AYX4FJ6FW2ZS.png)

### 凯悦酒店(com.Hyatt.hyt)

![凯悦酒店 实测:正常运行](https://bbs.kanxue.com/upload/attach/202607/662006_2MTA29R98SR8W7W.png)

### 洲际优悦会(com.ihg.apps.android)

![洲际优悦会 实测:正常运行](https://bbs.kanxue.com/upload/attach/202607/662006_VBVUJ5VAQZTA878.png)

### 万豪(com.marriott.mrt)

## ![万豪 实测:正常运行](https://bbs.kanxue.com/upload/attach/202607/662006_QKV2XSW5V7B234N.png)

## 附件

- [src_kpm.zip](../attachments/291930/src_kpm.zip) — 37.91kb，95次下载

---

# 回复

## 回复 by 秋落 (#2)

*2026-7-9 13:11*

本文在r0ysue老师指导下完成

## 回复 by wangzehua (#3)

*2026-7-9 16:35*

有权限读/proc/<ppid>/maps？

## 回复 by 秋落 (#4)

*2026-7-9 17:24*

>
> [wangzehua](https://bbs.kanxue.com/user-377240.htm)
>  有权限读/proc//maps？
>

重新审核了目标APP 是我写错了， 实际就是读自身 maps/smaps 做 indexOf 找 zygisk/frida/lsposed/signkiller/rwxp/adb/toybox 标记，感谢纠正

## 回复 by mb_bvvcoitr (#5)

*2026-7-10 23:59*

r0ysue 是不是开了个培训班？不深入了解底层原理，对抗也只能照葫芦画瓢。拿 Zygisk Detector 的检测举例，有没有想过为什么要看 libandroid_runtime.so 的 RSS 值？因为 PLT hook 通常需要解析 ELF header 寻找符号，而 zygisk 需要在应用进程 fork 后重新做 unhook （实际上就是一次新的 PLT hook），因此会把一些 page 变成 presented。不懂原理的话很难举一反三。

## 回复 by 秋落 (#6)

*2026-7-11 00:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_bvvcoitr](https://bbs.kanxue.com/user-1006272.htm)
>  r0ysue&nbsp;是不是开了个培训班？不深入了解底层原理，对抗也只能照葫芦画瓢。拿&nbsp;Zygisk&nbsp;Detector&nbsp;的检测举例，有没 ...
>

工作流:主 Agent 只做分配与判断,子 Agent 在 herdr 多窗格里并行干活(idalib 无头反编译 / Frida 动态校验 / unidbg 脱机执行);人主要做授权与纠偏。有偏差我觉得也在意料之中。app分析ai全自动完成。 效果已经非常不错了，节省了很大一部分时间。

## 回复 by bluegatar (#7)

*2026-7-12 08:50*

大佬的文章很棒，方方面面都讲到了，就是太长得看1个月![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 小黄鸭爱学习 (#8)

*2026-7-13 16:24*

Ai确实节约工作量，细节当然要靠人工调整

## 回复 by B.M.K (#9)

*2026-7-14 18:03*

ai写的文章读起来真费劲

## 回复 by 全靠赛博牛马 (#10)

*2026-7-15 17:42*

>
> [B.M.K](https://bbs.kanxue.com/user-983263.htm)
>  ai写的文章读起来真费劲
>

你没有ai吗?

## 回复 by ShoppingChen (#11)

大佬，想学习，能给我资料和插件么？有偿。![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by 秋落 (#12)

>
> [ShoppingChen](https://bbs.kanxue.com/user-946259.htm)
>  大佬，想学习，能给我资料和插件么？有偿。[em_086]
>

没有什么特别的内容在里面 重点就是利用了Ai 完成了本次逆向
