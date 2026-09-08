---
title: '[原创]某金融App 登录请求逆向实战：从梆梆加固反 Frida 自毁到 Go 业务层明文抓包'
url: https://bbs.kanxue.com/thread-292885.htm
tid: 292885
author: xiao_qi_lin
date: '2026-09-08'
tags: [Android安全, 原创]
crawled_at: '2026-09-08T07:27:49+00:00'
replies: 15
---

# [原创] 某银行 App 登录请求逆向实战：从梆梆加固反 Frida 自毁到 Go 业务层明文抓包

>
> 发表于 2026-09-07
> 目标：com.xxx.xxx v1.0.4（某银行移动 App）
> 环境：Pixel 6 / Android 15 / 小肩膀定制系统 / Frida 17.16.4 / eCapture / NDK 28
> 摘要：本文按时间顺序，完整记录一条"抓登录请求明文"的逆向全过程。目标 App 同时踩了四块硬骨头——**梆梆加固（DexHelper 抽取式壳）**、**反 Frida 主动自毁**、**登录流量走 Go 纯 crypto/tls（不走系统库）**、**业务逻辑是加密 JS bundle（无明文可读）**。三条常规路线（eCapture / Frida / 内核 HWBP）全部撞墙后，最终靠**小肩膀定制系统的"任意 so 注入" + 自写 arm64 inline hook**，在 `libgojni.so` 的 JNI 业务入口把登录请求的参数和响应头完整落地。本文把走通的、走不通的、以及中途自己犯的错，一五一十都写出来。
>
>
>

---

## 0. 起因：一个委托，一条抓包指令

起因很朴素：一位在金融行业做审计的朋友，手上有个银行移动端 App 的接口需要核对，托我做一次授权测试，把它的**登录请求**抓出来。目标就是 `com.xxx.xxx`（某银行 App，v1.0.4），要的是 URL / headers / body / response 四件套，登录动作由人在设备上手动完成，需要点登录时停下来通知。

需求落到工具上就一句话：用 `xiaojianbang-auto-reverse` 工具链里的 eCapture 把这个登录请求抓出来。

当时设备上已经有：

- 测试机：Pixel 6（arm64-v8a，内核 5.10.209-android13，Magisk root，小肩膀定制系统）
- eCapture（eBPF 内核态 TLS 抓包）在 `/data/local/tmp/ecapture`
- frida-server-17.16.4 在 `/data/local/tmp/frida-server-17.16.4-android-arm64`
- jadx 在本地，IDA 需要导出 so 时由人用 ida-no-mcp 插件导出（**不能自己跑反汇编工具**）

一眼看去这是个标准的 TLS 抓包任务：eCapture 挂在系统 TLS 库上，一启动就该有明文。结果第一脚就踢到了铁板——而且后面证明，前面拦着的其实是四块硬骨头：**梆梆加固壳、反 Frida 主动自毁、Go 纯 crypto/tls 网络栈、加密 JS bundle**，哪一块都不好啃。

---

## 1. 第一个异常：App 一开就无限回退

还没开始抓包，先撞上了一个更麻烦的问题：**App 正常安装启动后，每过几秒就自动退回到初始页面**，无论点什么操作都是这个循环，根本点不到登录。

这个现象本身就是一条重要线索。我们先做了最基本的排查：这到底是不是 App 自身的 bug？还是我们这边环境引起的？

结论很快就锁定了。当时为了后面走 Frida，frida-server 是**开着的**。而把 frida-server 停掉之后，App 立刻恢复正常。于是做了一个对照实验：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/1071700_PCVN9S6YBY4M2CE.webp)

崩溃现场的特征很关键（`logcat -b crash` 摘出来的）：

```python
Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x97c

  pc=0x97c  lr=0x0  sp=0x0  x9=0x97c  x12=0x97c

  backtrace: #00 pc 0x97c  #01 pc 0x0   （仅 2 帧，全 <unknown>）
\```

几个点串起来就非常可疑：`fault addr` 和 `pc` 都落在 `0x97c`——一个比任何合法映射都小得多的低地址（参考文章里那篇梆梆实战的 `pc=0x1f4` 是同一类签名）；`lr`/`sp` 被清零；backtrace 只剩两个无符号帧。这不是野指针或栈溢出，而是**控制流被强行劫持、跳到一个未映射的低地址**，是加固壳主动自毁的典型手法——把 `sp`/`lr` 清零再 `br` 到低地址，让崩溃现场"干净"到没法回溯。之后 App 就是 `Force finishing activity ...MADPWeexActivity`，退回 Splash 重启，无限循环。到这里就确认了：**这 App 有反 Frida 检测，检测到 frida-server 就自毁**。

>
> 这里埋了一个贯穿全过程的教训，我把它提前说出来：**"App 能稳定运行"不等于"绕过了反 Frida"，只是"没开 frida-server"而已。** 后面我一度把这两件事搞混——有一次为了继续测试，手贱又把 frida-server 拉了起来，结果 App 的自毁机制立刻卷土重来，之前"已经稳定、能正常点登录"的环境被我自己亲手打回原形。这个错我记了很久：**做对照实验时，一次只变一个变量。**
>
>
>

---

## 2. 第一回合：eCapture 抓不到登录包

回到抓包主线。既然不能开 frida，那就用 eCapture——它走 eBPF 内核态、通过 uprobe 挂系统 TLS 库，不需要 frida-server、不向目标进程注入，天然不触发自毁。理论上这是最干净的方案。

eCapture 的 `tls -m text` 模式只 hook 系统 conscrypt 库 `/apex/com.android.conscrypt/lib64/libssl.so` 的 `SSL_write`/`SSL_read`。第一轮抓到了 App 的一点流量：

```python
POST /collect/i  Host: xxx.xxx.com.cn

头: Magicianencrypt: 1

body: Base64 密文

响应: 404 nginx
\```

这是**遥测**流量，走系统 conscrypt/BoringSSL，所以 eCapture 抓得到。但登录请求始终不见踪影。

这里还踩了个小坑：一开始用 `-p 4010` 锁死 App 进程抓，结果 App 在登录流程里自己重启了（4010 → 10980），`-p 4010` 一直在盯一个已经死掉的 PID，等于抓了个寂寞。改成**全量抓包**（不锁 PID）复测后，com.xxx.xxx 进程一条登录明文都没有，只抓到别的进程——小米系统 `connect.rom.miui.com` 的 `GET /generate_204` 联网探测。

这个对比其实很有信息量：eCapture 能抓到小米的 conscrypt 流量、也能抓到目标 App 自己的 `/collect/i` 遥测，说明**工具本身是好的**；偏偏抓不到目标 App 的登录，只能说明**登录请求根本不经系统 TLS 库**。而 eCapture 的 tls 模式只挂系统库。这条路，死。

接着试 eCapture 专门针对 Go 程序的 `gotls` 模式，直接报：

```python
not a Go executable
\```

原因：TLS 逻辑在**动态库 libgojni.so** 里（一个 gomobile 生成的 c-shared JNI 库），不是独立的 Go 可执行文件，`gotls` 要解析的 Go build info 段根本不存在。两条 eCapture 路子都堵死。

---

## 3. 中途一次"自证"：32 位 / 64 位的坑

为了搞清楚 libgojni.so 里到底是什么，把 so 导出做了静态分析。这里我犯了一个实打实的错，值得写下来。

第一次导出的 libgojni.so，我拿来做分析，得出一套 crypto/tls 的地址（比如 Write 在 `0x37379c`）。结果后来发现全错了——**第一次导出的是 32 位 ARM 版本（ELFCLASS32 / EM_ARM），而设备跑的是 arm64**。

32 位和 64 位下同一函数的偏移完全错位。重新导出 64 位版本后，地址才对上：

```python
crypto/tls.(*Conn).Write           = 0x47f800   (明文写主入口)

crypto/tls.(*Conn).Read            = 0x480830

crypto/tls.(*Conn).writeRecordLocked = 0x47e9f0 (record type 23 = application data)
\```

教训：**分析 so 前先 `file` 一下架构**，32/64 位搞错会浪费一整轮分析。这也是为什么后面每一步都强调"导出时确认是 arm64-v8a"。

---

## 4. 定位登录到底走哪条网络栈

libgojni.so 是个 `gomobile bind` 生成的 Go c-shared JNI 库（go1.15.15，包 `github.com/justinlu/MADP_Client_Go`）。登录业务处理层就在这里，它自己带 Go runtime、**走 Go 自己的 crypto/tls，从不调用 C 的 libssl.so**。

这解释了为什么 eCapture 抓不到：eCapture 的 uprobe 挂在系统 libssl.so 上，而登录流量从头到尾就没进过 libssl.so。

`crypto/tls.(*Conn).Write`（0x47f800）的 prologue 先是一段 Go 栈检查，然后才建帧：

```python
.text:0047F800  LDR   X1, [X28,#0x10]     ; g.stackguard0 读栈保护值

.text:0047F804  SUB   X2, SP, #0x60

.text:0047F808  CMP   X2, X1

.text:0047F80C  B.LS  loc_47FDD4          ; 栈不足 → 跳 morestack

.text:0047F810  STR   X30, [SP,#-0xE0]!   ; 建帧 0xE0(224B)，存 LR

.text:0047F814  MOV   X20, SP
\```

这帧总共 0xE0（224 字节）。结合反编译，栈槽映射是 `Conn=var_D8(-0xD8)`、明文 `ptr=var_D0(-0xD0)`、`len=var_C8(-0xC8)`、`cap=var_C0(-0xC0)`。明文 slice 的落点：

```c
// positive sp value has been detected, the output may be wrong!

retval_6825A0 __golang crypto_tls__ptr_Conn_Write(_ptr_tls_Conn a1, _slice_uint8 a2)

{

    ...

    __int64 v34; // [xsp+10h] [xbp-D0h]  明文指针 ptr

    __int64 v35; // [xsp+18h] [xbp-C8h]  长度 len

    __int64 v36; // [xsp+20h] [xbp-C0h]  容量 cap

    ...

    v27 = crypto_tls__ptr_Conn_writeRecordLocked(v5, 23, v12, v10, v11);

    //                                          type=23 = TLS application data

}
\```

关键就是这行 `writeRecordLocked(v5, 23, ...)`——`23`（0x17）正是 TLS application data 的 record type。明文就在 `writeRecordLocked` 的入参里。理论上，hook 住这一层就能拿到登录明文。

---

## 5. 内核 HWBP 的尝试，以及为什么放弃

既然不能开 frida（会自毁），就想到了 `stealth-hook` 的内核硬件断点（HWBP）方案：不开 frida-server、不触发自毁，用 KPM 在内核里下硬件断点打 `Write` 的明文。

但这个方案撞上了一个 **go1.15 的栈式 ABI** 死穴，是我读反汇编 + 反复追问后确认的：

1. **Go 1.15 是栈式 ABI**，函数参数不是放在 X0–X7 寄存器里，而是放在**栈上**。明文 slice 的 ptr/len/cap 是从 caller 通过栈传进来的。
2. 而 stealth-hook 的 KPM handler 有个硬限制：**只保存 X0–X7 寄存器，只 dump 寄存器指向的内存（上限 128 字节），不 dump SP 栈内存**。
3. 结果就是：在 `Write` 裸入口下断点，X0–X7 里根本没有明文指针（在栈上），KPM 又读不到栈 → **抓不到**。

更糟的是，再往下追一层，`writeRecordLocked` 自己也是 Go 函数、也走栈式 ABI——调用它之前明文 ptr/len/cap 是被 `STR` 写回栈再传参的，`BL` 那一刻这些值**不稳定停在某个 X 寄存器里**。

结论：**HWBP 抓 Go 栈式明文，从原理上就别扭**，不是"找对指令"能救的，而是"断点那一下寄存器里压根没有指针"。这条路放弃。

>
> 这个认知有个反过来的价值：它直接点明了 **Frida 恰恰能读 SP 栈**（这正是 HWBP 做不到的）。所以后来重新审视时，结论是"能用 Frida 时，hook Go Write 是可行的；只是 Frida 本身又被反 Frida 挡在门外"——一个死循环。
>
>
>

---

## 6. 第二回合：Frida spawn 早注入，定位自毁点

于是决定正面解决反 Frida：用 Frida **spawn 早注入**（`frida -f`，在 App 主逻辑跑起来之前就布防），而不是 attach（attach 时检测早已跑完）。

写了第一个绕过脚本 `bypass_xxx.js`，思路是"通用 libc 兜底 + 观察探针"：

- hook `strstr`（命中 frida 关键字返回 NULL）、`strcmp`（命中返回不相等）、`fopen`（敏感路径返回打开失败）、`open/openat`（观察）、`readlink`（含关键字改写为 `/dev/ashmem`）
- 观察 `android_dlopen_ext`（记录 so 加载顺序）、`pthread_create`（记录线程归属）、`kill/tgkill/abort/raise/_exit/exit`（自毁时打印 backtrace）

>
> 这里先踩了一个 Frida 17 的版本坑，值得单独记一笔。第一版脚本里 `installDlopenObserver` 用了 `Module.findExportByName(null, "android_dlopen_ext")`——这是 Frida 17 已经移除的**全局符号静态查找**形式，运行直接报 `TypeError: not a function`。更要命的是，这段代码在 `main()` 里恰好排在自毁观察器 `installSuicideObserver` **之前**，它一崩，后面的自杀观察器根本没装上。于是第一轮 spawn 虽然观察到 App 在 t≈2.2s 自毁，但**一条 backtrace 都没抓到**，白白浪费一轮。改成 `Module.getGlobalExportByName(...)`、把观察器提前、每个安装包再套上 try/catch 之后，才拿到下面这条决定性 backtrace。
>
>
>

spawn 注入后，App 在 **t≈2.1s** 自毁。但这次拿到了决定性的 backtrace：

```python
SUICIDE abort

  0x7c26724450  libc.so!fdopendir

  0x7c26743b14  libc.so!0x80b14

  0x78da2135d4  libDexHelper.so!0x35d4

  0x78da214944  libDexHelper.so!0x4944

  0x7c40a7b684  linker64!call_constructors+0x2c4
\```

翻译成人话：**自毁点不在 libgojni.so（Go 业务层），而在 libDexHelper.so（梆梆加固壳）的 constructor 加载期**。`call_constructors` → 壳的 init 函数 `0x4944` → 子函数 `0x35d4` → 走 libc `fdopendir` 遍历目录（扫 `/proc/self/fd` 或 `/proc/self/task`）→ 发现 frida 特征 → `abort()`。

这还纠正了一个之前的误解：之前以为检测核心在 Go 层（direct syscall 绕 libc），实际上**这个自毁点走的是 libc `fdopendir`，backtrace 里明明白白经过 libc.so**——所以 hook libc 层对它是有效的，`svc` 绕过 libc 的担心对这个点不成立。只是我们脚本当时没 hook `fdopendir/opendir/readdir` 这条路，所以没拦住。

但这条 backtrace 只够"定位到壳的 constructor"，还不够定罪。为了排除"是我们自己的 `fopen` 拦截打断了壳加载器、才导致 abort"这种自摆乌龙的假设，又做了一轮 **OBSERVE_ONLY 纯观察**对照：所有 libc 兜底只打印、不篡改任何返回值或 buffer。结果 App 仍然 t≈2.1s 自毁——说明自毁与我们的篡改无关，检测真实存在。

而这一次，观察探针抓到了**检测的真面目**：`strcmp` 反复命中，被比较的字符串 `s2` 赫然是：

```python
/memfd:frida-agent-64.so (deleted)
\```

把所有线索串起来就通了：**libDexHelper.so 的检测，是 `fopen`/`open` 反复读 `/proc/self/maps`（日志里 maps 被 touch 了几十次），逐行 `strcmp` 比对，命中 `/memfd:frida-agent-64.so (deleted)` 这一行就 `abort()` 自毁**。这正是 Frida 17 用 `memfd_create` 注入 agent 时，在进程内存映射里留下的铁证特征。前面 backtrace 里的 `fdopendir` 只是另一条并行的检测分支（遍历 `/proc/self/task` 或 fd 目录）。

顺带也解释了之前那个 `pc=0x97c` 的 SIGSEGV：它是自毁的一种表现，而 spawn 早注入让我们抓到了更早的 abort 路径。

>
> 到这里其实浮现过一个"对症下药"的念头：既然检测靠读 maps 文本 + strcmp，那 hook read/fgets 把 maps 里含 frida/memfd 的行擦掉不就行了？真去试才发现此路不通——壳的 ELF 加载器自己也合法地读 `/proc/self/maps` 做重定位，粗暴拦截/改内容会打断加载器。这也是后面转向 route(c) 的直接原因之一。
>
>
>

---

## 7. 静态分析 libDexHelper.so：撞上 OLLVM

按流程转静态分析。用 function_index.txt 确认：`0x35d4` 和 `0x4944` 都落在 `sub_33F8`（0x33f8）内部（下一个函数是 0x4990），所以两个 backtrace 帧都在同一个函数里。

读了 `33F8.c`，这个函数不是简单的检测函数，而是一个**重度 OLLVM 控制流平坦化混淆的自定义 ELF 加载器 / 重定位器 / 自解密器**：

```c
// 解析 /proc/self/maps 每一行

off_15038(v125, "%lx-%lx %s %s %s %s %s", &v100, &v101, v124, v124, v124, v124, v119);

if ( v100 <= qword_15048 && qword_15048 < v101 ) break;

// 遍历 program headers 找 PT_LOAD / PT_DYNAMIC

// switch 解析 DT 标签（DT_INIT / DT_INIT_ARRAY / DT_INIT_ARRAYSZ / STRTAB / SYMTAB / RELA）

// 最后执行 init / init_array 函数指针

// 末尾尾递归调用 sub_33F8 自身
\```

而 `imports.txt` 是空的、`strings.txt` 里 grep 不到任何 frida 关键字、`disassembly/` 目录也是空的——**梆梆把导入表和字符串都加密了**，静态看不到 `fdopendir`、`/proc/self/maps` 这些字面，检测逻辑只能靠运行时动态读出来（这也是为什么上一步得靠 `strcmp_hit` 才能抓到真面目）。检测逻辑埋在单个 OLLVM 巨型函数里，且壳几乎必然有 `.text` CRC 自校验（改磁盘 so 会触发另一层自毁）。

到这里做了个现实判断：**硬刚这个 OLLVM blob 静态 patch 的性价比太低**，而且 maps 扫描大概率只是第一个检测点，绕过之后还会弹出第二、第三个（打地鼠）。反 Frida 这条线，到此先按下不表，转而把"登录逻辑到底在哪"这条线并进来推进。

---

## 8. 换一条思路：登录逻辑根本不在 Java dex 里

在正面硬刚反 Frida 的同时，另一条线在推进：搞清楚登录逻辑到底在哪一层。用定制系统的**整体脱壳 + 抽取式脱壳**跑了一遍，把脱出来的 dex 拿 jadx 看：

- 整体脱壳产物（2.9MB）：只有 8 个 java 类，全是梆梆壳加载器——`IsoService`、`R`、`com.secneo.apkwrapper.{a,AP,AW,b,CP,H}`
- 抽取式脱壳 classlist：只有 9 个壳类，同样没有任何业务类
- **登录业务逻辑一个都不在标准 Java dex 里**

再查 App 运行时文件和 APK assets：

- 运行时 `cache/metadata/central.dat`：加密二进制，头 `c4e0 72af 0d41 5429 ...`（高熵）；只有 `etag.dat` 是明文 JSON，内容就一个版本号，无业务
- APK 内 `assets/main/` 打包了 245 个 hash 命名的 `.dat`，大文件头 `2179 e2b1 9a2a 61e3 ...`——全部高熵、无 gzip（`1f8b`）、无 `PK`、无明文 JS
- APK 内**没有任何明文 .js / weex / bundle 文件**

结论：这是一个 **MADP/Weex 框架的 App**，登录页逻辑以加密 JS bundle 的形式存在，运行时由 MADP 解密后喂给 `libweexjsb.so` 执行。**静态读明文 JS 这条路，彻底死。**

但这一步没有白走——它把目标范围大大缩小了：登录逻辑不在地面文件里，只可能在**运行时**的某一层。剩下能碰的，就是内存里的业务入口。

---

## 9. 路线切换（route c）：定制系统 native 注册监听

三条常规路线（eCapture / Frida / HWBP）各自都有硬伤，于是转向小肩膀定制系统自带的 native 能力。这里其实也有一道方法论上的刹车：工具链有一条纪律是**同一检测链连续动态测试失败累计 3 次就得停下来转静态**，而 Frida 路线已经撞墙多次，继续叠加 hook 只会越陷越深。综合"检测的是 memfd 特征"这个认知，最后定下 route(c)——这也是和作者反复对齐后确认的方向。核心逻辑一句话：

>
> **既然检测的是"frida-agent 以 memfd 映射进进程"这个特征，那就换一种"注入产物根本不产生 frida-agent memfd 映射"的方式。**
>
>
>

小肩膀定制系统提供"任意批量 so 注入"：把普通 `.so` 放进指定目录，App 启动时由系统加载器直接 `dlopen`。这个加载不经过 frida-agent、不产生 memfd 映射，`libDexHelper.so` 的 maps strcmp 检测天然命中不到——**不触发自毁**。而且全程不用开 frida-server。

但注入一个 so 之前，得先知道 hook 哪个点。这里用定制系统的**native 函数注册监听**（logcat 输出 `xiaojianbang ArtMethod::RegisterNative`），冷启动 App 抓了一次注册过程：

```python
冷启动采集 18s，共 5183 条 RegisterNative

唯二的非系统 so：

  libweexcore.so : 80 条注册

  libgojni.so    : 34 条注册
\```

在 libgojni.so 的 34 条里，出现了一组关键方法：

```python
funcName: byte[] worker.ApiResponse.getBody()        @offset=6504436 (0x63451c)

funcName: java.lang.String worker.ApiResponse.getCode()   @offset=6504496

funcName: java.lang.String worker.ApiResponse.getHeader() @offset=6504552

worker.ServiceWorker.resourceApi(String,String,String,String,boolean) → worker.ApiResponse

                                            @offset=6519580 (0x637b1c)

worker.Worker.aesEncrypt(String) → String     @offset=6501540 (0x6338e4)

worker.ServiceWorker.getAuthToken()           @offset=6518160

worker.Context.getMappedUrl(String) → String  @offset=6505844

worker.Context.getParam(String) → String      @offset=6505948

worker.Context.secureGetString(String) → String @offset=6507628

worker.ServiceWorker.getCentralString(String) @offset=6518216

worker.ServiceWorker.startup()                @offset=6520668
\```

这就是**决定性突破**：libgojni.so 根本不是单纯的 TLS 库，而是一个用 Go 写的完整业务 **ServiceWorker** 引擎（方法签名里的 `go.Seq`/`go.Universe` 是 gomobile bind 的铁证）。`resourceApi` 是**网络请求的总入口**（4 个 String + 1 个 boolean，返回 ApiResponse），所有 API 请求——包括登录——都从这里过；`ApiResponse.getBody/getCode/getHeader` 是响应的明文出口，`aesEncrypt` 是加密入口，`Context.getParam/secureGetString` 是参数与安全存储。

顺带排除另一个候选：libweexcore.so 那 80 条注册全是 `com.taobao.weex.bridge.WXBridge.native*` / `JSContext.native*` 之类的 Weex 渲染桥接，纯 UI 引擎，和登录网络无关。

而且地址换算能对上（证明 offset 就是 IDA 文件偏移，可直接跳转）：

```python
libgojni base 0x7837425000 + offset 0x637b1c = 0x7837a5cb1c == 日志里的 funcAddr ✓
\```

这比 crypto/tls 的 `Write`（0x47f800）**高了整整一层**：不用去碰 Go 栈式 ABI 的 TLS 内部，直接在 JNI 边界就能拿到业务层看到的原始 URL / method / body / header。

---

## 10. 最后一步：自写 arm64 inline hook 并注入

定制系统只提供"让 App 加载任意 so"的机制，**没有现成 hook 框架 so**，所以要自己写。核心是 arm64 的 inline hook，代码在 `hook_src/libcdbhook.c`。

### 10.1 找基址 + 算目标

```c
#define TARGET_SO   "libgojni.so"

#define TARGET_OFF  0x637b1cUL

#define OUT_FILE    "/data/local/tmp/cdb_login_capture.txt"

typedef jobject (*resourceApi_t)(JNIEnv*, jobject, jstring, jstring, jstring, jstring, jboolean);

static resourceApi_t g_orig = NULL;

static int phdr_cb(struct dl_phdr_info* info, size_t size, void* data) {

    if (info->dlpi_name && strstr(info->dlpi_name, TARGET_SO)) {

        *(uintptr_t*)data = (uintptr_t)info->dlpi_addr;

        return 1;

    }

    return 0;

}

static uintptr_t find_base(void) {

    uintptr_t base = 0;

    dl_iterate_phdr(phdr_cb, &base);

    return base;

}
\```

用 `dl_iterate_phdr` 遍历加载的 so，匹配到 `libgojni.so` 取 `dlpi_addr` 作为基址，`target = base + 0x637b1c`。

### 10.2 arm64 免修复 inline hook

这里的 trick 是**免修复搬运**：先确认目标函数 prologue 的前 16 字节里**没有 PC 相对寻址**（没有 adr/adrp/ldr literal/b 这类指令），这样把 prologue 原样搬到 trampoline 上执行，结果不变，不需要做指令重定位。

```c
static int do_inline_hook(uintptr_t target, void* replace, void** out_orig) {

    /* trampoline: 原16字节 + [ldr x16,#8; br x16; .quad target+16] = 32B */

    uint8_t* tramp = (uint8_t*)mmap(NULL, 32, PROT_READ|PROT_WRITE|PROT_EXEC,

                                    MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);

    if (tramp == MAP_FAILED) return -1;

    memcpy(tramp, (void*)target, 16);

    uint32_t ldr = 0x58000050;      /* ldr x16, #8  */

    uint32_t br  = 0xD61F0200;      /* br  x16      */

    uint64_t ret = (uint64_t)(target + 16);

    memcpy(tramp + 16, &ldr, 4);

    memcpy(tramp + 20, &br, 4);

    memcpy(tramp + 24, &ret, 8);

    __builtin___clear_cache((char*)tramp, (char*)tramp + 32);

    *out_orig = tramp;

    /* patch target: ldr x16,#8; br x16; .quad replace */

    long ps = sysconf(_SC_PAGESIZE);

    uintptr_t pg = target & ~(ps - 1);

    if (mprotect((void*)pg, (size_t)ps * 2, PROT_READ|PROT_WRITE|PROT_EXEC) != 0) return -2;

    uint64_t rep = (uint64_t)replace;

    uint8_t patch[16];

    memcpy(patch + 0, &ldr, 4);

    memcpy(patch + 4, &br, 4);

    memcpy(patch + 8, &rep, 8);

    memcpy((void*)target, patch, 16);

    __builtin___clear_cache((char*)target, (char*)target + 16);

    mprotect((void*)pg, (size_t)ps * 2, PROT_READ|PROT_EXEC);

    return 0;

}
\```

原理：

1. `mmap` 32 字节可执行 trampoline，前 16 字节原样拷贝 prologue，后 16 字节写 `ldr x16,#8` + `br x16` + 8 字节的 `target+16` 地址 → 这样 `g_orig` 调它时，执行完原 prologue 就跳回 `target+16` 继续原函数。
2. 把 `target` 前 16 字节 patch 成 `ldr x16,#8; br x16; .quad hk_resourceApi` → 任何人调 `resourceApi` 都先进我们的 hook。
3. `mprotect` 连续两页 RWX（防止 patch 跨页）、写、`__builtin___clear_cache` 刷指令 cache、恢复 RX。

### 10.3 hook 函数本体

```c
static jobject hk_resourceApi(JNIEnv* env, jobject thiz,

                              jstring url, jstring method,

                              jstring body, jstring header, jboolean flag) {

    FILE* f = fopen(OUT_FILE, "a");

    if (f) fprintf(f, "\n===== resourceApi @%ld =====\n", (long)time(NULL));

    const char* c;

#define DUMP_JSTR(name, js) \

    if (js) { c = (*env)->GetStringUTFChars(env, js, NULL); dump_kv(f, name, c); \

              if (c) (*env)->ReleaseStringUTFChars(env, js, c); } else dump_kv(f, name, "(null)");

    DUMP_JSTR("URL", url);

    DUMP_JSTR("METHOD", method);

    DUMP_JSTR("BODY", body);

    DUMP_JSTR("HEADER", header);

#undef DUMP_JSTR

    { char b[16]; snprintf(b, sizeof(b), "%d", (int)flag); dump_kv(f, "FLAG", b); }

    jobject resp = g_orig(env, thiz, url, method, body, header, flag);

    dump_response(env, resp, f);

    if (f) { fflush(f); fclose(f); }

    return resp;

}
\```

关键就是 `GetStringUTFChars` 把 4 个 jstring 读成明文落地（logcat tag `cdbhook` + 文件 `/data/local/tmp/cdb_login_capture.txt`），然后调 `g_orig` 拿 `ApiResponse`，再反射读 `getCode/getHeader/getBody`。

`resourceApi` 的 4 个 String 参数语义（哪个是 url / method / body / header）不是猜的，而是两步坐实的。

第一步静态：`resourceApi` 真正的 Go 实现 `MADP_Client_Go._ptr_ServiceWorker.ResourceApi`（在 IDA 导出目录 `5F55F0.c`）里有一段 debug 日志拼接，直接就把参数顺序写死在日志串里了：

```go
"Receive :url:" + a2 + ",method:" + a3 + ",body:" + a4 + ",header:" + a5
\```

即 `a2=url、a3=method、a4=body、a5=header、a6=bool`。再看它对应的 JNI 桩入口 `0x637b1c` 的 prologue：

```python
637b1c: sub  sp, sp, #0x80          ; 前4条无 adr/adrp/b/ldr-literal

637b20: stp  x29, x30, [sp, #0x20]

637b24: stp  x28, x27, [sp, #0x30]

637b28: stp  x26, x25, [sp, #0x40]

...

637b3c: mov  w19, w6                ; w6 = jboolean(a6)

637b50: mov  x24, x0                ; x0 = JNIEnv*

637b54: bl   go_seq_to_refnum_go

637b64: bl   go_seq_from_java_string ; 逐个把 jstring marshalling
\```

这是 RegisterNative 注册的 JNI native，走标准 AAPCS64：**X0=JNIEnv*，X1=this，X2=url，X3=method，X4=body，X5=header，W6=flag**。第二步动态：注入后打印的参数和真实业务 100% 吻合，才最终写死在 `hk_resourceApi` 的形参里。

顺带说一句为什么选"改 prologue 的 inline hook"而不是"换 RegisterNatives 表指针"这种更干净的做法：后者要 `FindClass("worker/ServiceWorker")` 重新拿类，而 worker/ServiceWorker 是 App 自己的类、由系统 classloader 持有，注入 so 里的 native 线程根本找不到这个 classloader——经典的 classloader 阻塞，不可靠。inline hook 则完全不用 FindClass，hook 里 X0 直接就是 `JNIEnv*`、返回值 `jobject` 也在手，全程无需 attach、无需找类，绕开了这个坑。

### 10.4 编译 + 注入

用 NDK（`.../ndk/28.2.13676358`）编译出 `libcdbhook.so`（11936 bytes，ELF64 ARM aarch64），只链接 `log`。

注入走定制系统"任意 so 注入"四步（64 位 so 加载目录是 `/data/local/tmp/xiaojianbang/lib64`）：

```bash
# 1. 文件以 .so 结尾，且不能以 .config.so 结尾

adb push libcdbhook.so /data/local/tmp

# 2. 改 SELinux 上下文

adb shell su -c 'chcon u:object_r:app_data_file:s0 /data/local/tmp/libcdbhook.so'

# 3. 目录需手动建

adb shell su -c 'mkdir -p /data/local/tmp/xiaojianbang/lib64'

# 4. 移进去，App 下次启动自动加载

adb shell su -c 'mv /data/local/tmp/libcdbhook.so /data/local/tmp/xiaojianbang/lib64/'
\```

App 下次启动自动 `dlopen` 这个 so，`__attribute__((constructor)) on_load` 触发，起一个 worker 线程轮询找 base（最多等 60s），找到就下 hook。

**生效验证**靠三条 logcat 证据，实际输出如下：

```python
cdbhook : libcdbhook loaded, pid=24423

cdbhook : libgojni base=0x783b80a000 target=0x783be41b1c

cdbhook : inline hook resourceApi ret=0 orig=0x7c3e9b0000   <- 安装成功
\```

1. `base`/`target` 命中 → `dl_iterate_phdr` 找到了 libgojni.so，绝对地址算对。
2. `ret=0` → patch 成功，trampoline 落在 `0x7c3e9b0000`。
3. 关键是第三点：改了 libgojni.so `.text` 前 16 字节之后，**App 持续存活、没有二次自毁** → 证明 libgojni.so 没有 `.text` CRC 自校验（否则改一个字节就该崩）。这也是前面一直悬着的风险点，实测排除。

而且 hook 一装上就实时命中，启动期已经抓到好几条资源请求，侧面印证 `resourceApi` 确实是"所有网络都从这过"的总入口：

```python
http://127.0.0.1:43483/weex/index.weex.js?Page=Launcher   (本地 weex server)

http://127.0.0.1:43483/data/launcher.json   method=GET

http://127.0.0.1:43483/data/version.json    method=GET
\```

参数顺序（URL / method / body / header / flag）也和 §10.3 的静态推断 100% 对上了。

---

## 11. 结果：登录请求落地

注入后启动 App，由人**手动完成登录**（点登录前停下来通知）。登录瞬间 `resourceApi` 被调，hook 把明文写进 logcat 和 `/data/local/tmp/cdb_login_capture.txt`，宿主机捞取后从多条 `resourceApi` 记录里筛出登录主请求：

```python
POST /pweb/appLogintic.do HTTP/1.1

Host: 127.0.0.1:43483

Accept: application/json

stage-type: weex

X-AuthToken-Local: e2e3…a1d0

Content-Type: application/json

user-agent: Pixel 6(Android/15) (com.xxx.xxx/1.0.4) Weex/0.28.0.1 1080x2209

Content-Length: 893

{"loginId":"<三段 | 分隔密文>","loginIdType":"C","loginType":"R","password":"<base64，前缀 MDAwMDAxMjQ>","_macAddr":"a56b…946a","token":"06b3…9fef","scene":"unknow","channel":"pweb","capCode":1,"ch":"pweb","sid":"5cb6…28de","verifyToken":"a382…52cd","_terminalType":"ANDROID","_channelId":"PMBS","_bankId":"1001","_deviceId":"a56b…946a","_accessJnlNo":"2026…9394"}
\```

响应：

```python
HTTP/1.1 200

Server: nginx

Date: Thu, 27 Aug 2026 09:36:54 GMT

Content-Type: application/json

Content-Length: 138

Cache-Control: no-store

Content-Encoding: none

Set-Cookie: X-LB=!kpZ0…TRc=; Expires=Fri, 28 Aug 2026 17:39:32 GMT; Path=/; HttpOnly

_traceid: 6377…1770
\```

几个有意思的点：

- **Host 是 `127.0.0.1:43483`**：App 的资源和 API 统一走本地 weex 代理，由代理再转发到真实后端（响应里 `Server: nginx` 说明后端是 nginx）。
- **loginId 是三段 `|` 分隔的密文**（疑似 SM2/AES 混合）、**password 是 base64**（前缀 `MDAwMDAxMjQ`）——也就是在这个 JNI 边界，账号密码**已经是密文**了，明文账号密码在更上层的 Weex/JS 层就完成了加密。想还原加密算法，得逆 `worker.Worker.aesEncrypt @0x6338e4`，那是另一个任务。

---

## 12. 复盘：整条路的取舍

把整个过程串起来看，真正的转折点有三个：

1. **eCapture 抓不到 → 确认登录走 Go crypto/tls 而不是系统库**，这是第一个关键认知，直接排除了最省事的方案。
2. **Frida spawn 早注入拿到 abort backtrace → 确认自毁点在 libDexHelper.so 的 constructor，走 libc `fdopendir`**，这是第二个关键认知，它同时告诉了我们"检测的是什么特征"（frida-agent 的 memfd 映射）。
3. **native 注册监听锁定 `resourceApi @0x637b1c` 是网络请求总入口**，这是第三个、也是最关键的一个认知——它把抓包从"在 TLS 底层硬抠明文"拉高到"在 JNI 业务边界直接读参数"，后者干净得多。

而贯穿全程的一条主线是：**检测和抓包是两个正交的问题**。反 Frida 自毁针对的是"frida-agent 的 memfd 特征"，那只要换一种"不产生 memfd 特征"的注入方式（定制系统任意 so 注入），自毁就天然不触发，抓包问题也顺势解决。很多时候换注入载体，比硬刚检测代码更划算。

最后留一句给同行的提醒：金融 App 的防护是分层的（梆梆壳自毁、Go 栈式 ABI、加密 JS bundle、业务层加密），别指望一条路走到黑。**每一层死路都会告诉你下一层该看哪里**——eCapture 的死路指向 Go tls，HWBP 的死路指向栈 ABI，Frida 的死路指向 memfd 检测，静态 JS 的死路指向运行时入口。把这些"死路"串起来，路就通了。

---

## 13. 后续可做（只列方向，本文不展开）

- 补齐 138 字节响应体：改 `dump_response` 把 `getBody()` 的字节也落地，重登一次即得。
- 逆向 `Worker.aesEncrypt @0x6338e4`，还原 loginId 三段密文与 password 的加密过程。
- 往 Go socket 层再 hook 一层，拿线缆级原始字节流。

---

# 回复

## 回复 by mb_ldbucrik (#2)

感谢分享

## 回复 by bingkuaiiii (#3)

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by iBa0 (#4)

6666

## 回复 by dpzx (#5)

6666

## 回复 by tonykros (#6)

666

## 回复 by mb_ysikfhxt (#7)

111

## 回复 by mb_xjdhrmck (#8)

123123

## 回复 by manyuegong33 (#9)

6

## 回复 by cpannn (#10)

先保存

## 回复 by MaYil (#11)

感谢分享

## 回复 by mb_qimctavn (#12)

6

## 回复 by xingbing (#13)

感谢分享

## 回复 by Zepp7289 (#14)

tql

## 回复 by mb_yfswmdcp (#15)

666

## 回复 by k4y0z (#16)

666
