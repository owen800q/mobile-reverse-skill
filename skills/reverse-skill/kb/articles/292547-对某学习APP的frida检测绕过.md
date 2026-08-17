---
title: '[原创]对某学习APP的frida检测绕过'
url: https://bbs.kanxue.com/thread-292547.htm
tid: 292547
author: wes1meanon
date: '2026-08-17'
tags: [Android安全, 原创]
crawled_at: '2026-08-17T01:32:51+00:00'
replies: 10
---

# 对某学习APP的frida检测绕过

这个App的frida检测机制 集中在`libDexHelper.so`和`libmsaoaidsec.so`两个so里面，主要思路都是一步步dump，trace到相关检测函数入口位置，再交给ai静态分析关键逻辑，写出绕过脚本
*哎，AI真王朝了，力大砖飞，我们的逆向究竟会变成什么样子...*

## libDexHelper.so

首先Hook了so的加载发现到DexHelper就闪退了，所以需要看看是什么问题，使用`hook_init.js`去hook拿到输出，分析出大致流程如下

\```
so加载 -> init -> 多次call_constructors -> android_dlopen_ext结束 -> dlopen("libc.so", RTLD_NOW) -> Process terminated
\```

而在dlopen到又一次call_constructors的调用都指向一个offset：

\```
0x70f3c57544  libDexHelper.so + 0x4a544
\```

更完整一点的调用栈就是：

\```
libDexHelper.so + 0x4a544
libDexHelper.so + 0x4a544
libDexHelper.so + 0x37a40
libDexHelper.so + 0x3596c
libart.so + 0x46ae64
libopenjdkjvm.so + 0x5360
boot.oat + 0x9c940
\```

毋庸质疑so肯定是有smc的，需要去dump，我们直接在`android_dlopen_ext`返回之后dump发现我们hook到之后，没dump就被kill了。猜测一下很有可能是自Hook了`open`，`write`这些函数，这是很多安全/游戏厂商的常用手段

\```
[SoDump] output: /data/local/tmp/libDexHelper.so_0x7171aa3000_memdump.so
Error: Permission denied
    at dumpModule (E:\Test\Work\--------\6.7.7_anti_frida\dump_so.js:79)
    at onLeave (E:\Test\Work\--------\6.7.7_anti_frida\dump_so.js:166)
Process terminated
[2312DRAABC::com.--------.mobile ]->
\```

我们直接拿syscall去dump即可，部分没有权限的内存空间也要dump下来防止遗漏，用`syscall_dump.js`成功dump。其实也想在`JNI_OnLoad`加载之后去dump(`syscall_Load_dump.js`)，但是发现frida就是死在JNI_OnLoad里面

\```
[JniDump] ========================================
[JniDump] JNI_OnLoad enter
[JniDump] addr: 0x70f6c4a018
[JniDump] offset: libDexHelper.so + 0x33018
[JniDump] vm: 0xb400007188a22e00
[JniDump] reserved: 0x0
[JniDump] caller: 0x7185185e64
[JniDump] caller offset: libart.so + 0x46ae64
[JniDump] ========================================
Process terminated
\```

改一下脚本在`JNI_OnLoad`之前dump，这应该就是我们能dump的最晚时机了，解密应该会更完全一点

```log
[JniDump] ========================================
[JniDump] dump reason: JNI_OnLoad_enter
[JniDump] module: libDexHelper.so
[JniDump] base: 0x70f2e98000
[JniDump] size: 0x129000
[JniDump] path: /data/app/~~rQzi3tAFqHBlWrFpOm7m5A==/com.--------.mobile-exvsiXgJRbXfwGfAbBJQwQ==/lib/arm64/libDexHelper.so
[JniDump] out : /data/data/com.--------.mobile/files/libDexHelper.so_0x70f2e98000_after_JNI_OnLoad_memdump.so
[JniDump] fd: 90
[JniDump] mprotect whole module readable
[JniDump] mprotect pages total=297 ok=297 fail=0
[JniDump] dump finished
[JniDump] saved: /data/data/com.--------.mobile/files/libDexHelper.so_0x70f2e98000_after_JNI_OnLoad_memdump.so
[JniDump] unreadable before retry: 0
[JniDump] zero filled pages: 0
[JniDump] ========================================
Process terminated
\```

现在大致流程就是这样，我们将dump下来的so拿到bn里面分析

\```
libDexHelper.so 加载完成
-> JNI_OnLoad 进入
-> 入口处 dump 成功
-> JNI_OnLoad 内部继续执行
-> 进程被 kill / terminate
\```

dump下来的so使用sofixer修复之后大部分地方都可以反编译了

我们之前通过svc在JNI_OnLoad结束之后进行了dump，我们直接复用之前的so，然后拿之前的so加载Hook脚本，在加几个函数来个大满贯hook

我们使用带了`init_array`调用监控的脚本去hook，发现崩溃不仅在`init_array`第一个调用结束之后崩溃，而且指向匿名内存，并且第二个调用还未开始，很有可能是在`init_array`第一个函数中创建线程去kill的，Claude看过linker64了，说脚本肯定没问题

\```
[android_dlopen_ext] path : /data/app/~~rQzi3tAFqHBlWrFpOm7m5A==/com.--------.mobile-exvsiXgJRbXfwGfAbBJQwQ==/lib/arm64/libDexHelper.so
[android_dlopen_ext] flags: 0x2
[android_dlopen_ext] extinfo: 0x7fd78bdf20
>>> [#1] CALL init_array @ 0x779cc8d650 (libDexHelper.so + 0x2f650) for 'libDexHelper.so'
<<< [#1] DONE init_array @ 0x779cc8d650 (libDexHelper.so + 0x2f650) for 'libDexHelper.so'
[android_dlopen_ext] handle: 0xad0715354bd48a2b
==============================
Process crashed: Bad access due to invalid address

......

    lr  00000078e6b0610c  sp  0000007fd78bdee0  pc  00000078e6b06130  pst 0000000080001000
1 total frames
backtrace:
      #00 pc 0000000000000130  <anonymous:78e6b06000>
***
[2312DRAABC::com.--------.mobile ]->
\```

这里app版本更新到6.7.8了，重新dump并且hook了一遍，结果不变，fix一下到bn里面看看

\```
[android_dlopen_ext] path : /data/app/~~h0YzYCcRX4xFSmKUejHKAA==/com.--------.mobile-0382fGhoiO1SDD5DI9qaPQ==/lib/arm64/libDexHelper.so
[android_dlopen_ext] flags: 0x2
[android_dlopen_ext] extinfo: 0x7fe6e77c00
>>> [#1] CALL DT_INIT @ 0x7aa7729098 (libDexHelper.so + 0x128098) for 'libDexHelper.so'
<<< [#1] DONE DT_INIT @ 0x7aa7729098 (libDexHelper.so + 0x128098) for 'libDexHelper.so'
>>> [#2] CALL DT_INIT_ARRAY @ 0x7aa7630650 (libDexHelper.so + 0x2f650) for 'libDexHelper.so'
<<< [#2] DONE DT_INIT_ARRAY @ 0x7aa7630650 (libDexHelper.so + 0x2f650) for 'libDexHelper.so'
[android_dlopen_ext] handle: 0xf5ec6bbf7a0cd67d
==============================
\```

奇怪，找不到线程创建，而且kill发生在dlopen返回之后（其实写到这里突然想到还有JNI_OnLoad了......）

但是通过字符串找到两个比较可疑的函数

```javascript
const TARGET_FUNCS = [
    {
        name: 'sub_431bc4',
        offset: 0x31bc4,
        retType: 'void',
    },
    {
        name: 'sub_457c58',
        offset: 0x57c58,
        retType: 'int64',
    },
];
\```

不出所料，调用来自`JNI_OnLoad`

\```
========== ENTER sub_431bc4 ==========
addr = 0x7aa48c2bc4 (libDexHelper.so + 0x31bc4)
arg1 = 256
arg2 = -1230861953
arg3 = 0xfff
---- registers ----
pc = 0x7aa48c2bc4
lr = 0x7aa48ca560
sp = 0x7fe6e76430
Backtrace:
    #0 0x7aa48ca560 0x7aa48ca560 libDexHelper.so!0x39560
    #1 0x7aa48ca560 0x7aa48ca560 libDexHelper.so!0x39560
    #2 0x7aa48c696c 0x7aa48c696c libDexHelper.so!JNI_OnLoad+0x2954
\```

来到这里发现这是一个jump，这里应该是一个动态跳转，但是我们结合打印出来的调用栈就可以轻松定位

 ![image](https://bbs.kanxue.com/upload/attach/202608/1069914_6PN526PR2DBU59K.webp)

我们可以考虑借助`Frida Stalker`进行Trace，从`JNI_OnLoad`调用开始Trace，而且似乎会在`sub_432774`中有非常大量的循环，看了一下，这里面是一个对Java层API的批量入口点检查，避免Java函数被Hook

这里是最上层的入口，里面内部进行大量的循环检测

\```
libDexHelper.so+0x33364  0x7a1a450364  add x2, sp, #0xa8
libDexHelper.so+0x33368  0x7a1a450368  mov x0, xzr
libDexHelper.so+0x3336c  0x7a1a45036c  bl #0x7a1a44f774
libDexHelper.so+0x32774  0x7a1a44f774  stp x28, x27, [sp, #-0x60]!
libDexHelper.so+0x32778  0x7a1a44f778  stp x26, x25, [sp, #0x10]
\```

对应调用就是这里

\```
0043337c                if (sub_432774(nullptr, 0x503e12, &var_c78) & 1
0043337c                    && (uint32_t)var_a67 != 0x77)
0043337c                {
00433380                    int64_t x0_20 = var_c78;
⚠️0043338c                    int64_t var_c70;
0043338c                    0x42cfc0(x0_20, var_c70 - x0_20, 3);
0043337c                }
\```

我们随便二分法找个靠后的offset开始trace，看看哪些会被触发

慢慢跟着offset向后追，如果发现进了循环就找顶层的trace向后设置trace（BN反编译代码有点抽象，汇编和伪C一团乱麻......）

如果卡住了就多等一会在trace，一路trace跟踪发现进入`sub_436bb8`之后被kill掉了，在`0x3596c`下Hook无法去Trace到，所以我们需要继续进入到里面去Trace

![image](https://bbs.kanxue.com/upload/attach/202608/1069914_WPRV48FGUR9NK28.webp)

\```
0x37144 → 0x38024(未命中)
   ↓
0x37a3c → 0x37a40 → 0x385ec
\```

到`0x385ec`的时候很明显发现只有2000多条trace，但是结尾也不是类似kill指令那种

这里很明显还动了`pthread_create`函数，这里看起来像是将`pthread_create`拿到之后进行了调用，然后后面也做了一些fd之类的检测

 ![image](https://bbs.kanxue.com/upload/attach/202608/1069914_64FMRVRF3JVBKUE.webp)

`sub_452944`内部也很明显发现了疑似maps的扫描和sleep相关的调用，这里大致定位之后就可以交给claude了，重点入口函数就是`sub_436bb8`

 ![image](https://bbs.kanxue.com/upload/attach/202608/1069914_FU5N7AA6W5NA2FK.webp)

>
> # libDexHelper.so 反 Frida 机制分析与绕过报告
>
>
>
> >
> > 目标：com.--------.mobile 6.7.8（---）
> > 加固壳：libDexHelper.so（爱加密 / SecNeo 系）
> > 平台：Android 14（API 34），arm64
> > 镜像基址：`0x400000`（Binary Ninja 中「地址 = 文件 offset + 0x400000」）
> > 状态：**libDexHelper.so 反调试已绕过，App 可继续启动**；下一关为 `libmsaoaidsec.so`
> >
> >
> >
>
>
>
>
> ---
>
>
> ## 1. 总体结论
>
>
> libDexHelper.so 在 `JNI_OnLoad` 阶段执行一整套反调试/反 Hook 逻辑，入口为 `sub_436bb8`。它的防护是**多线程、多手段、分散触发**的：
>
>
> - 检测到 Frida 后不一定立刻退出，而是通过「跳非法地址崩溃 / 写加密文件上报 / 破坏 ART 执行 / 静默 exit」等多种方式，且分布在主线程与多个检测线程中。
> - 核心是一个通用的「代码是否被 inline hook」检测原语 `sub_432774`，被 4 个上层检测复用。
> - 因此单点封堵 kill 无效，**根治方式是让核心检测原语 `sub_432774` 与 `isHooked` 统一返回「未 Hook」**。
>
>
> 最终以 6 组 Hook 通过该库全部检测（见第 6 节）。
>
>
>
>
> ---
>
>
> ## 2. 执行入口与调用链
>
>
>
>
> ```python
> System.loadLibrary("DexHelper")
>   → libart JavaVMExt::LoadNativeLibrary
>     → JNI_OnLoad
>       → sub_436bb8               # 反调试总入口(巨型函数, ~0x436bb8-0x43c8xx)
>           ├─ sub_452944          # inline-hook 检测(检 libc!pthread_create 等)
>           ├─ sub_448f14          # IO-hook/PLT 替换框架 + 反 heap-dump
>           ├─ /proc/self/task 扫描 → sub_431bc4(0x100 frida)   # Frida 线程名检测
>           ├─ /proc/self/fd 扫描  → linjector 检测
>           ├─ sub_433028          # 批量 Java 入口点检测(内部调 sub_432774)
>           ├─ 多个 pthread_create # 常驻检测线程(maps 扫描/ptrace/sleep 等)
>           └─ ART 层 dex 解密加载 + Runtime 字段改写
> ```
>
>
>
>
> ---
>
>
> ## 3. 核心检测机制详解
>
>
> ### 3.1 `sub_431bc4(category, magic, 0xfff)` —— 中央 kill / 上报原语
>
>
>
>
> ```c
> flags = *(*(0x502de0) + 0x164);           // 全局反调试配置位图
> if ((flags & category) == 0) {            // 该检测项未在配置启用
>     sp = 0; lr = 0;                       // 清栈指针
>     jump((magic & 0xfff) & 0xfffffffc);   // 跳非法低地址 → 主动崩溃
> } else {                                  // 已启用
>     // 按 category 选检测名字符串, 校验 integrity, 写 envc.push 加密文件上报
>     sub_430aac(name, 1, magic);
>     return;
> }
> ```
>
>
> - 调用到该函数时**检测已成立**，两分支都是「处理威胁」。
> - `magic & 0xfff & 0xfffffffc`（如 `0xb6a2897f → 0x97c`）是非法低地址，对应早期「Bad access due to invalid address」崩溃。
> - **category 位 → 检测名映射**：
>
>
>
>
> | bit | 名称 | bit | 名称 | bit | 名称 |
> |-|-|-|-|-|-|
> | 0x1 | root | 0x100 | **frida** | 0x8000 | bl |
> | 0x2 | usb? | 0x200 | **hook** | 0x10000 | developer |
> | 0x4 | emu | 0x400 | integrity | 0x20000 | unsource |
> | 0x8 | appmon? | 0x800 | signature | 0x40000 | location |
> | 0x10 | proxy | 0x1000 | debug |  |  |
> | 0x20 | polling | 0x2000 | rom |  |  |
> | 0x40 | inject | 0x4000 | display |  |  |
> | 0x80 | xposed |  |  |  |  |
>
>
> - `sub_430aac` / `sub_431094` 操作一个名为 `envc.push` 的加密文件，用于持久化上报检测结果。
>
>
> ### 3.2 `sub_432774(arg1, code_addr, out)` —— 核心 hook 检测原语 ★
>
>
> 检测 `code_addr` 处的代码开头是否被 inline hook（trampoline 跳转特征等）。返回 `&1` 表示检测到 Hook。**被 4 处复用**：
>
>
>
>
> | 调用者 | 检测对象 |
> |-|-|
> | `isHooked`（0x4326e0） | Java 方法的 ArtMethod entry_point |
> | `sub_433028`（0x43336c） | 批量 Java 入口点 / 内部数据 |
> | `sub_452944`（0x452a74） | native 库导出符号 |
> | `sub_4612cc`（0x463634/670/718） | 其它检测 |
>
>
> 各调用者在 `sub_432774` 返回 0 时均走「环境干净」分支，不读输出 buffer → **恒返回 0 即可安全绕过所有 hook 检测**。
>
>
> ### 3.3 `android::art::ArtMethod::isHooked(env, method)` —— 0x4326e0
>
>
>
>
> ```c
> ArtMethod* m = FromReflectedMethod(method);
> void* entry  = *(m + entry_point_offset);   // 方法 AOT/解释器入口
> int r = sub_432774(NULL, entry, &buf);      // 检测 entry 是否被 hook
> return r & (buf.byte == 0);
> ```
>
>
> - 作为 native 方法通过 `RegisterNatives` 注册，供 Java 反调试代码调用。
> - 检测的 framework 方法 entry 位于 `boot-framework.oat`；Frida 在场时 `sub_432774` 读该 entry 越界 → 崩溃 pc 落在 `boot-framework.oat`。
>
>
> ### 3.4 `sub_452944(version, libname, symname)` —— inline-hook 检测
>
>
> - 用 `process_vm_readv`（syscall `0x10e`）读进程内存中符号开头字节，与磁盘 ELF 原始字节比对，不一致即判定被 inline hook，返回 1。
> - 调用点 `0x4385ec` 检测 `libc.so!pthread_create`，返回 1 即 `jump(0x10dc)` 走 kill。
>
>
> ### 3.5 `sub_448f14` —— IO-hook / PLT 替换框架 + 反 heap-dump
>
>
> - 给 `libc/libbinder/libutils/libcutils/libart/libperfetto_hprof` 的 `read/pread/mmap/write/open/pthread_create` 等批量挂 PLT/GOT 钩子（重定向到自身 `sub_450xxx`），并处理文件访问重定向规则（解密 `RES_RULE`）。
> - **反 heap-dump**：解析 `libperfetto_hprof.so` 的 `g_signal_pipe_fds`（Android 11+ heap profiling 信号管道），写 `-1` 禁用它。
> - 崩溃点 `sub_448f14+0x104c`（0x449f5c）：`*x0_112 = 0xffffffff`。Frida 环境下符号解析地址异常导致写崩溃。
>
>
> ### 3.6 线程名 / 注入物检测（`sub_436bb8` 内）
>
>
> - 遍历 `/proc/self/task/*/comm`，匹配 Frida 特征线程名 `gmain` / `gum-js-loop` / `gdbus` → `sub_431bc4(0x100 frida)`。
> - 遍历 `/proc/self/fd`，readlink 匹配 `linjector` → 注入检测。
> - 读取使用 raw syscall（openat/read），绕过 libc 层 Hook。
>
>
>
>
> ---
>
>
> ## 4. 崩溃点演进与定位过程
>
>
>
>
> | 阶段 | 现象 | 根因 | 处理 |
> |-|-|-|-|
> | 1 | 崩 `libDexHelper.so+0x49f5c` | `sub_448f14` 写 perfetto `g_signal_pipe_fds` | `FIX_PERFETTO` 重定向符号到合法内存 |
> | 2 | `sub_431bc4(0x100 frida)` 触发 | `/proc/self/task` 扫到 Frida 线程 | `replace` `sub_431bc4` → void |
> | 3 | 崩 `boot-framework.oat` / 静默退出 | `isHooked`/批量检测经 `sub_432774` 读 entry 越界 | `replace` `sub_432774`、`isHooked` → 0 |
> | 4 | App 继续加载业务 SO | libDexHelper 全部检测通过 ✔ | —— |
>
>
>
> >
> > 备注：绕过后日志里 `boot*.oat` 的 access-violation 是 **ART 正常的隐式 SIGSEGV**（null-check / GC read-barrier），由 ART 自身 handler 恢复，非崩溃。异常处理器已改为仅关注 libDexHelper 内异常。
> >
> >
> >
>
>
>
>
> ---
>
>
> ## 5. 关键地址速查表（镜像基址 0x400000）
>
>
>
>
> | 符号 | 地址 | offset | 作用 |
> |-|-|-|-|
> | `sub_436bb8` | 0x436bb8 | 0x36bb8 | 反调试总入口(JNI_OnLoad 调用) |
> | `sub_432774` | 0x432774 | 0x32774 | **核心 hook 检测原语** |
> | `isHooked` | 0x4326e0 | 0x326e0 | ArtMethod entry hook 检测 |
> | `sub_431bc4` | 0x431bc4 | 0x31bc4 | kill / 上报原语 |
> | `sub_430aac` | 0x430aac | 0x30aac | 写 envc.push 上报 |
> | `sub_452944` | 0x452944 | 0x52944 | inline-hook 检测(process_vm_readv) |
> | `sub_448f14` | 0x448f14 | 0x48f14 | IO-hook 框架 + 反 heap-dump |
> | `sub_441bc4` | 0x441bc4 | 0x41bc4 | 自实现 ELF 符号解析器 |
> | `sub_433028` | 0x433028 | 0x33028 | 批量 Java 入口点检测 |
> | 全局配置指针 | 0x502de0 | 0x102de0 | `*(*(0x502de0)+0x164)` = 检测位图 |
>
>
>
>
> ---
>
>
> ## 6. 最终绕过方案（hook.js）
>
>
>
>
> | 开关 | 目标 | 手段 | 说明 |
> |-|-|-|-|
> | `BYPASS_SUB432774` | `sub_432774` | replace→0 | **核心**，让所有 hook 检测判定「干净」 |
> | `BYPASS_ISHOOKED` | `isHooked` | replace→0 | 双保险，Java 层入口 |
> | `BYPASS_KILL` | `sub_431bc4` | replace→void | 屏蔽 kill/上报，防跳非法地址 |
> | `BYPASS_INLINE_CHK` | `sub_452944` | onLeave→0 | 屏蔽 inline-hook 检测 |
> | `FIX_PERFETTO` | `sub_441bc4` | 重定向 `g_signal_pipe_fds` | 修 0x449f5c 写崩溃 |
> | `WATCH_KILL`/`BLOCK_SELF_KILL`/`BLOCK_EXIT` | exit/kill/tgkill/pthread_kill | attach/replace | 拦截并观察退出 |
> | 异常处理器 | libDexHelper 内 SIGSEGV | 仅观测，其余放行 | 避免拦截 ART 隐式异常 |
> | `HOOK_TOP`/`HOOK_JAVASCAN` | sub_436bb8/sub_432774 观测 | 默认关 | 侵入式 attach 易与壳冲突 |
>
>
> 关键取舍：
>
>
> - **优先 `replace` 核心原语而非逐个堵 kill**：检测点分散多线程，堵不完；`sub_432774`/`isHooked` 是所有 hook 判定的收敛点。
> - **异常处理器只看 libDexHelper**：ART 大量使用 SIGSEGV 做隐式检查，全量拦截既是噪音也影响稳定，改为定向放行。
>
>
> 运行：
>
>
>
>
> ```bash
> frida -U -f com.--------.mobile -l hook.js --no-pause
> ```
>
>
>
>
> ---
>
>
> ## 7. 遗留 / 后续方向
>
>
> 1. **`libmsaoaidsec.so`（字节 anti-frida 库）**：libDexHelper 通过后，启动流程会加载它，是下一个卡点。其常见手段：
> 	- 常驻线程轮询 `/proc/self/maps`、`/proc/self/task` 检测 frida-agent / gum / 线程名；
> 	- `init_array` 中提前反调试；
> 	- `pthread_create` 反注册（隐藏线程名）。
> 	建议同样思路：先 `init_array` + `pthread_create` 监控定位其检测线程，再定点封堵。
> 2. **根治线程名检测**：Frida 的 `gmain`/`gum-js-loop`/`gdbus`/`pool-frida-*` 线程名是最强特征，考虑用 gadget/改名方案从源头消除，可减少多处检测触发。
> 3. **配置位图 `*(*(0x502de0)+0x164)`**：可在稳定时机 dump，反推服务端下发了哪些检测项。
>
>
>
>
> ---
>
>
> ## 8. 附：判断「已绕过」的标志
>
>
> 日志出现以下业务库加载即表示 libDexHelper 关卡通过：
>
>
>
>
> ```python
> libframework-connectivity-jni.so / libforcedarkimpl.so
> libDWIMECore.so / libfntvcrash.so / libsecuritylib.so ...
> ```
>
>
>

绕过脚本exp（需要更换本机linker64的定位 `call_constructors` 内部调用 .init/.init_array 的位点地址）：

```js
'use strict';

// Frida 15/16/17 兼容层 【新增】
if (typeof Module.findExportByName === "undefined") {
    Module.findExportByName = function(modName, symbolName) {
        if (modName === null) {
            // 全局查找符号：遍历全部模块匹配导出（模拟旧行为）
            const modules = Process.enumerateModules();
            for (const m of modules) {
                const addr = m.getExportByName(symbolName);
                if (addr !== null) return addr;
            }
            return null;
        } else {
            const mod = Process.getModuleByName(modName);
            return mod ? mod.getExportByName(symbolName) : null;
        }
    };
}

/*
 * frida -U -f com.--------.mobile -l hook_func.js
 *
 * 适配：
 *   Android arm64
 *   Frida 17.x
 *   linker64 反汇编基址 0x400000
 */

const TARGET_SO = 'libDexHelper.so';

/*
 * IDA 里显示：
 *   sub_431bc4 @ 0x431bc4
 *   sub_457c58 @ 0x457c58
 *
 * 若 IDA image base = 0x400000，则 Frida offset 为：
 *   0x431bc4 - 0x400000 = 0x31bc4
 *   0x457c58 - 0x400000 = 0x57c58
 */
const TARGET_FUNCS = [
    {
        name: 'sub_431bc4',
        offset: 0x31bc4,
        retType: 'void',
    },
    {
        name: 'sub_457c58',
        offset: 0x57c58,
        retType: 'int64',
    },
];

let targetHooked = false;
let linkerHooked = false;
let seq = 0;

/*
 * 如果你确认 IDA 没有 0x400000 image base，而 0x431bc4 本身就是 RVA，
 * 把上面的 offset 改回：
 *
 *   sub_431bc4: 0x431bc4
 *   sub_457c58: 0x457c58
 */

function log(s) {
    console.log('[DexHelperHook] ' + s);
}

function safeReadCString(p) {
    try {
        if (p && !p.isNull()) {
            return Memory.readCString(p);
        }
    } catch (e) {}
    return null;
}

function shortSoName(path) {
    if (!path) {
        return 'unknown';
    }
    const idx = path.lastIndexOf('/');
    if (idx >= 0) {
        return path.substring(idx + 1);
    }
    return path;
}

function ptrInRange(mod, addr) {
    return addr.compare(mod.base) >= 0 &&
           addr.compare(mod.base.add(mod.size)) < 0;
}

function moduleOffsetString(addr) {
    try {
        const m = Process.findModuleByAddress(addr);
        if (!m) {
            return '<unknown module>';
        }
        return m.name + ' + 0x' + addr.sub(m.base).toString(16);
    } catch (e) {
        return '<unknown module>';
    }
}

function printBacktrace(context) {
    let bt = [];

    try {
        bt = Thread.backtrace(context, Backtracer.ACCURATE);
    } catch (e) {
        try {
            bt = Thread.backtrace(context, Backtracer.FUZZY);
        } catch (_) {
            console.log('Backtrace failed: ' + e);
            return;
        }
    }

    console.log('Backtrace:');
    bt.forEach(function (addr, i) {
        let sym = '';
        try {
            sym = DebugSymbol.fromAddress(addr).toString();
        } catch (e) {
            sym = moduleOffsetString(addr);
        }
        console.log('    #' + i + ' ' + addr + ' ' + sym);
    });
}

function dumpTargetFuncArgs(name, args) {
    if (name === 'sub_431bc4') {
        /*
         * void sub_431bc4(int32_t arg1, int32_t arg2, int64_t arg3)
         */
        console.log('arg1 = ' + args[0].toInt32());
        console.log('arg2 = ' + args[1].toInt32());
        console.log('arg3 = ' + args[2]);
        return;
    }

    if (name === 'sub_457c58') {
        /*
         * int64_t sub_457c58(int64_t arg1, int32_t arg2, void* arg3)
         */
        console.log('arg1 = ' + args[0]);
        console.log('arg2 = ' + args[1].toInt32());
        console.log('arg3 = ' + args[2]);
        return;
    }

    console.log('x0 = ' + args[0]);
    console.log('x1 = ' + args[1]);
    console.log('x2 = ' + args[2]);
    console.log('x3 = ' + args[3]);
}

function hookTargetFunctions(reason) {
    if (targetHooked) {
        return true;
    }

    const mod = Process.findModuleByName(TARGET_SO);
    if (!mod) {
        return false;
    }

    log('Hooking ' + TARGET_SO + ', reason=' + reason);
    log('base=' + mod.base + ', size=0x' + mod.size.toString(16) + ', path=' + mod.path);

    const targets = [];

    for (let i = 0; i < TARGET_FUNCS.length; i++) {
        const item = TARGET_FUNCS[i];
        const addr = mod.base.add(item.offset);

        log(item.name + ' offset=0x' + item.offset.toString(16) + ', addr=' + addr);

        if (!ptrInRange(mod, addr)) {
            log('[-] ' + item.name + ' out of module range, skip all hooks');
            log('    module range: ' + mod.base + ' - ' + mod.base.add(mod.size));
            return false;
        }

        targets.push({
            name: item.name,
            addr: addr,
            retType: item.retType,
        });
    }

    for (let j = 0; j < targets.length; j++) {
        const t = targets[j];

        Interceptor.attach(t.addr, {
            onEnter(args) {
                console.log('');
                console.log('========== ENTER ' + t.name + ' ==========');
                console.log('addr = ' + t.addr + ' (' + moduleOffsetString(t.addr) + ')');

                dumpTargetFuncArgs(t.name, args);

                console.log('---- registers ----');
                console.log('pc = ' + this.context.pc);
                console.log('lr = ' + this.context.lr);
                console.log('sp = ' + this.context.sp);

                printBacktrace(this.context);
            },

            onLeave(retval) {
                if (t.retType !== 'void') {
                    console.log('========== LEAVE ' + t.name + ' ==========');
                    console.log('retval = ' + retval);
                }
            }
        });

        log('[+] attached ' + t.name + ' @ ' + t.addr);
    }

    targetHooked = true;
    log('[+] target hooks installed');
    return true;
}

function describeInitCall(func, sonamePtr) {
    let soname = safeReadCString(sonamePtr);
    if (!soname) {
        soname = 'unknown';
    }

    const shortName = shortSoName(soname);

    let moduleName = '';
    let offset = '';
    let modulePath = '';

    try {
        const m = Process.findModuleByAddress(func);
        if (m) {
            moduleName = m.name;
            modulePath = m.path;
            offset = '0x' + func.sub(m.base).toString(16);
        }
    } catch (e) {}

    return {
        func: func,
        soname: shortName,
        sonameRaw: soname,
        module: moduleName,
        modulePath: modulePath,
        off: offset,
    };
}

function isTargetInitInfo(info) {
    if (!info) {
        return false;
    }

    if (info.soname === TARGET_SO) {
        return true;
    }

    if (info.module === TARGET_SO) {
        return true;
    }

    if (info.sonameRaw && info.sonameRaw.indexOf(TARGET_SO) !== -1) {
        return true;
    }

    if (info.modulePath && info.modulePath.indexOf(TARGET_SO) !== -1) {
        return true;
    }

    return false;
}

function locStr(info) {
    if (info.module) {
        return info.module + ' + ' + info.off;
    }
    return '<unknown module>';
}

function getThreadStack(map, tid) {
    let s = map[tid];
    if (!s) {
        s = [];
        map[tid] = s;
    }
    return s;
}

function hookLinkerInitArray() {
    if (linkerHooked) {
        return;
    }

    /*
     * 全部偏移依据 linker64 反汇编核对，IDA base = 0x400000：
     *
     *   __dl__ZN6soinfo17call_constructorsEv @ 0x461290
     *   RVA = 0x61290
     *
     *   DT_INIT:
     *     0x461444  blr x20      => RVA 0x61444
     *     0x461448  返回落点     => RVA 0x61448
     *     func = x20
     *     soname = x21
     *
     *   DT_INIT_ARRAY:
     *     0x461580  blr x28      => RVA 0x61580
     *     0x461584  返回落点     => RVA 0x61584
     *     func = x28
     *     soname = x20
     */
    const HOOKS = [
        {
            tag: 'DT_INIT',
            call: 0x56874,
            ret: 0x56878,
            funcReg: 'x20',
            nameReg: 'x21',
        },
        {
            tag: 'DT_INIT_ARRAY',
            call: 0x568BC,
            ret: 0x568C0,
            funcReg: 'x28',
            nameReg: 'x20',
        },
    ];

    const linker = Process.findModuleByName('linker64');
    if (!linker) {
        log('[-] linker64 not found');
        return;
    }

    log('[+] linker64 @ ' + linker.base + ', size=0x' + linker.size.toString(16));
    log('[+] hook DT_INIT / DT_INIT_ARRAY call sites');

    const pendingByTid = {};

    HOOKS.forEach(function (h) {
        const callAddr = linker.base.add(h.call);
        const retAddr = linker.base.add(h.ret);

        if (!ptrInRange(linker, callAddr)) {
            log('[-] ' + h.tag + ' callAddr out of range: ' + callAddr);
            return;
        }

        if (!ptrInRange(linker, retAddr)) {
            log('[-] ' + h.tag + ' retAddr out of range: ' + retAddr);
            return;
        }

        log('[+] ' + h.tag + ' call hook @ ' + callAddr + ' linker64 + 0x' + h.call.toString(16));
        log('[+] ' + h.tag + ' ret  hook @ ' + retAddr + ' linker64 + 0x' + h.ret.toString(16));

        /*
         * 调用前：
         *   当前 PC 命中 blr 指令地址。
         *   这时 x20/x28 仍然保存着即将被调用的 init 函数地址。
         *
         * 关键点：
         *   如果这个 init 函数属于 libDexHelper.so，就在 blr 真正执行前安装目标函数 hook。
         */
        Interceptor.attach(callAddr, {
            onEnter(args) {
                const tid = this.threadId;
                const stack = getThreadStack(pendingByTid, tid);

                let func = ptr(0);
                let sonamePtr = ptr(0);

                try {
                    func = this.context[h.funcReg];
                    sonamePtr = this.context[h.nameReg];
                } catch (e) {}

                const info = describeInitCall(func, sonamePtr);
                info.id = ++seq;
                info.tag = h.tag;
                info.tid = tid;

                stack.push(info);

                const line =
                    '>>> [#' + info.id + '] CALL ' + h.tag +
                    ' @ ' + info.func +
                    ' (' + locStr(info) + ')' +
                    " for '" + info.soname + "'" +
                    ' tid=' + tid;

                if (isTargetInitInfo(info)) {
                    console.log('');
                    console.log('[DexHelperHook] [TARGET INIT] ' + line);

                    /*
                     * 这里是最关键的位置：
                     * libDexHelper.so 已经 map 完成，constructor 还没真正 blr 进去。
                     * 此时 hook base + offset，能覆盖 init 中即将调用的目标函数。
                     */
                    hookTargetFunctions('before ' + h.tag + ' constructor call');

                    console.log('[DexHelperHook] Target init caller backtrace:');
                    printBacktrace(this.context);
                } else {
                    /*
                     * 如果你想看所有 so 的 init 调用，可以取消下面这行注释。
                     */
                    // console.log(line);
                }
            }
        });

        /*
         * 调用返回后：
         *   如果某个 constructor 内反调试导致崩溃/退出/卡死，
         *   对应的 DONE 不会出现。
         */
        Interceptor.attach(retAddr, {
            onEnter(args) {
                const tid = this.threadId;
                const stack = getThreadStack(pendingByTid, tid);
                const info = stack.pop();

                if (!info) {
                    return;
                }

                if (isTargetInitInfo(info)) {
                    console.log(
                        '[DexHelperHook] <<< [#' + info.id + '] DONE ' + info.tag +
                        ' @ ' + info.func +
                        ' (' + locStr(info) + ')' +
                        " for '" + info.soname + "'" +
                        ' tid=' + tid
                    );
                }
            }
        });
    });

    linkerHooked = true;
}

function hookDlopenFallback() {
    const names = [
        'android_dlopen_ext',
        'dlopen',
    ];

    names.forEach(function (name) {
        const addr = Module.findExportByName(null, name);
        if (!addr) {
            return;
        }

        log('[+] hook ' + name + ' @ ' + addr);

        Interceptor.attach(addr, {
            onEnter(args) {
                this.path = null;

                try {
                    if (args[0] && !args[0].isNull()) {
                        this.path = Memory.readCString(args[0]);
                    }
                } catch (e) {}

                if (this.path && this.path.indexOf(TARGET_SO) !== -1) {
                    log(name + ' onEnter: ' + this.path);
                }
            },

            onLeave(retval) {
                if (this.path && this.path.indexOf(TARGET_SO) !== -1) {
                    log(name + ' onLeave: ' + this.path + ', retval=' + retval);

                    /*
                     * 注意：
                     * 这里通常已经晚于 DT_INIT / DT_INIT_ARRAY。
                     * 只是兜底，防止 linker call-site hook 没命中。
                     */
                    hookTargetFunctions(name + '.onLeave fallback');
                }
            }
        });
    });
}

function hookLinkerSymbolFallback() {
    /*
     * 有些系统 linker64 的 call site 偏移不一致。
     * 这个 fallback 尝试通过符号名找 call_constructors / call_array / call_function。
     * 如果系统符号被裁剪，可能找不到，没关系。
     */
    const linker = Process.findModuleByName('linker64');
    if (!linker) {
        return;
    }

    let symbols = [];
    try {
        symbols = linker.enumerateSymbols();
    } catch (e) {
        return;
    }

    symbols.forEach(function (sym) {
        const n = sym.name || '';

        const interesting =
            n.indexOf('call_constructors') !== -1 ||
            n.indexOf('call_array') !== -1 ||
            n.indexOf('call_function') !== -1;

        if (!interesting) {
            return;
        }

        log('[+] linker symbol fallback found: ' + n + ' @ ' + sym.address);
    });
}

function main() {
    log('script loaded');

    /*
     * 如果脚本加载时目标 so 已经在内存中，先尝试直接 hook。
     * 这种情况可能已经错过 init，但能覆盖后续调用。
     */
    hookTargetFunctions('already loaded');

    /*
     * 关键 hook：
     * 在 linker64 执行 DT_INIT / DT_INIT_ARRAY 的 blr 前拦截。
     */
    hookLinkerInitArray();

    /*
     * 打印一下符号 fallback 信息，辅助确认当前系统 linker 情况。
     */
    hookLinkerSymbolFallback();

    /*
     * 兜底。
     */
    hookDlopenFallback();

    log('init done');
}

setImmediate(main);
\```

## libmsaoaidsec.so

*从此开始我换了个安卓16的设备，下面脚本都是frida17版本*

把之前的脚本注入，全部按预期绕过，卡在`load SO: libc.so`后就Process terminated，我们放开异常捕获，发现

```python
[pthread_create] libmsaoaidsec.so 检测线程 entry offset=0x1c544
[pthread_create] libmsaoaidsec.so 检测线程 entry offset=0x1b8d4
[pthread_create] libmsaoaidsec.so 检测线程 entry offset=0x26e5c
\```

但是没打出 [NEUTER]或者KILL，大概率是在`.init_array` 之类的早期构造函数里同步执行检测+kill了,想用`Stalker`follow一下syscall，结果直接崩

看到上面ai表现这么好，这个so也比较经典了，那么直接写提示词交给ai，*感觉ai王朝了啊...*

不出所料是类似SMC出的exit，检测时间在`.init_proc`

>
> # libmsaoaidsec.so 加载期反 Frida 分析报告
>
>
>
> >
> > 目标:`libmsaoaidsec.so`(Android arm64,ELF64 AArch64,base=0,所有偏移即文件偏移)
> > 分析方式:IDA Pro 9.0 + ida-pro-mcp 直连反编译,全部结论有地址/字符串交叉引用依据
> > 库身份:JNI_OnLoad 日志标签 `NagaLinker v8.83`(娜迦/Naga 加固体系的加载期反调试库)
> >
> >
> >
>
>
> ## 0. 一句话结论
>
>
> 杀进程的"真凶"不是 kill/tgkill/exit 符号,而是运行时解密出的 28 字节内联 shellcode:
>
>
>
>
> ```asm
> movz x8, #94        ; AArch64 __NR_exit_group = 94
> svc  #0
> ret
> ```
>
>
> 由 `sub_234E0 / sub_26334 / sub_269AC / sub_260B0` 四个执行器 mmap RWX 后直接执行,
> 完全不经过 libc 符号。
>
>
>
>
> ---
>
>
> ## 1. .init_array 与 DT_INIT 全貌
>
>
> 用 ELF 动态段解析(非猜测)得到:
>
>
>
>
> | 项目 | 地址 | 内容 |
> |-|-|-|
> | DT_INIT | `0x14400` | `.init_proc`(0x14400–0x148A0),控制流平坦化状态机 |
> | DT_INIT_ARRAY | `0x46F80`(0x30 字节) | 5 个有效指针 + 1 个 0 终止 |
> | DT_FINI_ARRAY | `0x46FB0` | `0x83F0`(start)+ 0 |
>
>
> ### 1.1 .init_array 五个函数(均无检测逻辑,纯 C++ 静态初始化)
>
>
>
>
> | 函数 | 地址 | 角色 |
> |-|-|-|
> | sub_83FC | 0x83FC | 注册两个 atexit(nullsub) |
> | sub_8448 | 0x8448 | 清零 0x4D370 起的一组全局 |
> | sub_8460 | 0x8460 | `pthread_key_create(&dword_5D3A8, sub_28DD8)` + atexit(sub_28DBC),TLS 键 |
> | sub_84B4 | 0x84B4 | 把 0x5D3C8~0x5D420 一组 qword 置 1(once_flag 表) |
> | sub_85A8 | 0x85A8 | 同上,0x5D428~0x5D480 一组 |
>
>
> ### 1.2 .init_proc(0x14400)线性化主流程
>
>
>
>
> ```python
> 读 canary
> *off_47FB8 = sub_123F0();       // ro.build.version.sdk → 存全局
> sub_12550();                     // persist.sys.dalvik.vm.lib 是否含 "art"
> sub_12440();                     // release_or_codename 含 'S'/"12"/security_patch → 修正 SDK 值
> if (*off_47FB8 > 23) *off_47ED8 = 1;
> if (sub_25A48() 为奇数) return;   // 门控:配置 dword_48850==218 时跑 sub_23B18 的 cmdline/maps 扫描
> 读取 /proc/<pid>/cmdline; v10 = strchr(buf, ':')
> 若含 ':' → 直接进 sub_13728 链(不设 dword_49014,线程2 会立即杀)
> 若无 ':' → sub_1BEC4: dword_49014 = getpid(); 然后 sub_1B924() ← 线程大管家
> sub_13728() → sub_2701C()(线程3) + sub_198D8()(DEX CRC32 校验) + sub_95C8()
> sub_23AD4(); v7 = sub_C830(); if (v7==1) { sub_95C8(); sub_9150()(线程5) }
> ```
>
>
> 所以 **.init_proc 就是"同步检测 + 线程调度者"**。
>
>
>
>
> ---
>
>
> ## 2. 五个线程与派生关系(全部有 xref 依据)
>
>
>
>
> | 线程入口 | 作用 | 派生者 |
> |-|-|-|
> | `sub_1C544` @0x1C544 | Frida 看门狗:扫 task/status 线程名、/proc/self/fd、/proc/self/maps+ELF 指纹 | `sub_1CEF8`(被 sub_1B924 调) |
> | `sub_1B8D4` @0x1B8D4 | TracerPid / PPid / T 态看门狗 | `sub_1B924` 直接调 |
> | `sub_26E5C` @0x26E5C | CRC32 模块特征扫描 | `sub_2701C`(被 sub_13728 调) |
> | `sub_8CAC` @0x8CAC | ART 内部结构完整性校验(版本门控) | `sub_9150`(被 init_proc 调) |
> | `sub_19E0C` @0x19E0C | ADB 检测(sys.usb.config 含 "adb") | `sub_1B924`,需 sub_CA28()==167 |
>
>
> 实际只观察到 3 个线程(0x1c544/0x1b8d4/0x26e5c),后两个被配置表门控
> (203/204/167/218/248/249/777 等常量)在部分设备上不创建。
>
>
> ### 2.1 自解析 dlopen/dlsym(不导入 pthread_create)
>
>
> 库的导入表**没有 pthread_create**。三个派生函数都是同一套路:运行时在栈上拼密文、
> 用 3 字节密钥(`99 A7 EC`)解密出 `"libc.so"` 与 `"pthread_create"`,然后
> `dlopen("libc.so",2) + dlsym(...)`,以 `(attr, 0, 入口, arg)` 调用。
>
>
> - sub_1B924 @0x1BA5C / 0x1BA84
> - sub_2701C @0x2721C
> - sub_9150 @0x9548 / 0x9568
> - sub_1CEF8 则 `dlopen("libart.so")` + dlsym 三个 `_ZN3art...PrettyMethod...` 变体
> (密钥 `99 A7 A9`,明文串位于 0x305F8 / 0x30626 / 0x3064D),并把解析到的 ART 函数指针
> 作为线程 1 的参数。
>
>
> 另有自实现 ELF 解析器(sub_18240 / sub_1806C,解析 PHDR/SHDR/.got/.dynstr/.rel.*
> 及 DT_ANDROID_* 标签)和自建符号注册表(qword_49248,sub_8784 构建、sub_8734 查询;
> JNI_OnLoad 通过它转发真正的 JNI_OnLoad)。
>
>
> ### 2.2 同步检测(不走线程)
>
>
> - init_proc 内 sub_25A48 → sub_23B18:cmdline / maps 字符串扫描(门控 dword_48850==218)
> - sub_13728 链内 sub_198D8 → sub_19694:对 `classes.dex...N` 做 **CRC32 完整性校验**
> (sub_16720 即标准 CRC32,0xFFFFFFFF 初值 + 表 0x2FAEC),不匹配走 sub_11FA4
>
>
>
>
> ---
>
>
> ## 3. 三种杀进程机制(全部有证据)
>
>
> ### 3.1 机制 A — libc exit(0)
>
>
>
>
> | 函数 | exit(0) 位置 | 检测内容 |
> |-|-|-|
> | sub_1BFAC | 0x1C150 | 遍历 `/proc/self/task/%s/status`,第一行命中 `gum-js-loop`(0x4904A)或 `gmain`(0x49056) |
> | sub_1C158 | 0x1C264 | 遍历 `/proc/self/fd` 符号链接,命中 `linjector`(0x4906A) |
> | sub_1C26C | 0x1C53C | 解析 `/proc/self/maps`,收集 `/data/local/tmp` 下 r-x 映射,mmap 后 ELF 解析,命中 `frida-agent`(0x4909F)或 `_AGENT_1.0`(0x49094) |
>
>
> 以上特征串在 sub_1C544 内用密钥 `99 A7 A9` 解密(0x49030~0x4909F),已逐一验证。
>
>
> ### 3.2 机制 B — 内联 exit_group(0) shellcode(核心)
>
>
> `sub_234E0` @0x234E0(同模板:sub_26334 @0x26334、sub_269AC @0x269AC、sub_260B0 @0x260B0)
> 全部执行同一流程:
>
>
> 1. 从 `xmmword_30760` 取 28 字节密文
> 2. 用 0x30794 起的 3 个 dword(99 A7 A9)逐字节 XOR(首字节强制 = 8)
> 3. `*(dword0) += 3008`
> 4. `mmap(0, 0x1C, PROT_READ|WRITE|EXEC, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)`
> 5. 拷贝 + `__clear_cache` + 调用 + munmap
>
>
> 精确复刻解密算法后反汇编:
>
>
>
>
> ```asm
> 0xD2800BC8   movz x8, #94        ; AArch64 __NR_exit_group = 94(已核实)
> 0xD4000001   svc  #0
> 0xD65F03C0   ret
> 0xD503201F   nop ×4
> ```
>
>
> 即 `exit_group(0)` —— **零 libc 调用、无 kill/tgkill/exit/syscall 符号痕迹**,
> 这就是符号级 hook 全部扑空的原因。
>
>
> 调用点:
>
>
> - `sub_11FA4` @0x11FA4(线程2/ADB 的杀点)→ sub_198D8(DEX 校验)→ `sub_234E0(0)`
> - `sub_1CEF8` 解析 PrettyMethod 失败 → `sub_234E0(0)`
> - 线程 1 主循环每轮调 `sub_26334(a1)`(首轮即执行,相当于自杀倒计时)
> - 线程 3(sub_26E5C)与 sub_8CAC → `sub_269AC(0)` / `sub_260B0(0)`
>
>
> ### 3.3 机制 C — fork + ptrace 反调试
>
>
> `sub_1B380` @0x1B380:
>
>
>
>
> ```c
> prctl(PR_SET_DUMPABLE, 1);               // 0x1B3D4
> v28 = dlsym(libc, "fork")();             // 符号名已解密验证 = "fork"
> if (v28 < 1) return sub_11FA4();         // fork 失败 → 杀
> // 父进程: 开 sub_1AB2C 线程管理子进程
> // 子进程: 若 dword_49014<=0 或 getpid()==dword_49014 → exit(1)
> //         否则 ptrace(PTRACE_CONT, <父pid>, 0, 信号) 循环  → 独占 ptrace 权限
> ```
>
>
> 配合线程 2 的判定:
>
>
> - `sub_1AE48`:读 `/proc/<pid>/status` 的 `TracerPid:`(特征串 "TracerPid:" 已解密验证)
> - `sub_1AB54`:读 `/proc/<tracerpid>/status` 的 `PPid:` 是否等于 dword_49014(本进程 pid)
> —— **只有自己 fork 的子进程 ptrace 自己才放行**,外部调试器一律杀
> - `sub_1B730`:遍历 `/proc/<pid>/task/*/stat`,任何线程状态为 `T`(stopped)即返回 777 触发杀
>
>
>
>
> | 优先级 | 偏移(函数) | 作用 | 建议 hook | 签名(NativeCallback) |
> |-|-|-|-|-|
> |  |  |  |  |  |
> | P0 | `0x234E0` sub_234E0 | 内联 exit_group(0) 执行器 | Interceptor.replace 为 no-op | `void(uint32_t)` |
> | P0 | `0x26334` sub_26334 | 线程1 自杀倒计时 | replace no-op | `void(int64_t)` |
> | P0 | `0x269AC` sub_269AC | 线程3/ART 线程 exit_group | replace no-op | `void(int64_t)` |
> | P0 | `0x260B0` sub_260B0 | ART 线程 exit_group | replace no-op | `void(int64_t)` |
> | P0 | `0x11FA4` sub_11FA4 | TracerPid/T态/ADB 的统一杀点 | replace no-op | `void(void)` |
> | P1 | `0x1AE48` sub_1AE48 | 查 TracerPid | replace 恒返回 0 | `int(void)` |
> | P1 | `0x1AB54` sub_1AB54 | 查 tracer 的 PPid | replace 恒返回 1 | `int(uint32_t)` |
> | P1 | `0x1B730` sub_1B730 | T 态任务扫描 | replace 恒返回 0 | `int(void)` |
> | P1 | `0x1BFAC` sub_1BFAC | task/status 线程名扫描 | replace 恒返回 NULL | `void*(void)` |
> | P1 | `0x1C158` sub_1C158 | fd 符号链接扫描 | replace 恒返回 NULL | `void*(void)` |
> | P1 | `0x1C26C` sub_1C26C | maps+/data/local/tmp ELF 指纹 | replace 恒返回 0 | `int(void)` |
> | P1 | `0x1678C` sub_1678C | 模块 CRC32 特征扫描(线程3) | replace 恒返回 0 | `int(void)` |
> | P2 | `0x19A58` sub_19A58 | ADB 线程判定 | replace 恒返回 0 | `uint32_t(void*)` |
> | P2 | `0x8CAC` sub_8CAC | ART 结构校验线程 | replace no-op | `int(void)` |
> | P2 | `0x19E0C` sub_19E0C | ADB 检测线程 | replace no-op | `void(void)` |
> | P2 | `0x1B380` sub_1B380 | fork+ptrace 反调试 | replace no-op | `int(void*, void*)` |
>
>
>

那么依旧利用已有的 `pthread_create`，一次性把 P0(4 个 `exit_group` 执行器 + 统一杀点)全部 patch 掉,再patchP1直接调用libc`exit(0)`的点，p2暂时不管；

同时把所有的调用栈打印之类的全部去掉，这种trace开销很大会把agent卡死， *这个神秘问题卡了我好久呜呜*

这样就过了检测了,

带调用栈打印的完整脚本（可能会有trace过多造成的环境问题,自行删除即可）：

```js
/*
 * libDexHelper.so 6.7.8 anti-frida 分析 / 绕过脚本
 * (Frida 17.x API 版本)
 *
 * 镜像基址 = 0x400000 (BN 中地址 - offset)
 *   sub_431bc4  (kill/report 原语)      offset 0x31bc4
 *   sub_452944  (inline-hook 检测)       offset 0x52944
 *   sub_432774  (Java 入口点批量检查)    offset 0x32774
 *   sub_436bb8  (顶层反调试入口)         offset 0x36bb8
 *
 * 用法:
 *   frida -U -f com.--------.mobile -l hook.js --no-pause
 * 或 attach:
 *   frida -U com.--------.mobile -l hook.js
 */

'use strict';

// ============ 配置 ============
const MODULE = 'libDexHelper.so';
const IMAGE_BASE = 0x400000;

// 是否绕过 kill: 让 sub_431bc4 在“未检测到”分支不跳非法地址，直接安全返回
const BYPASS_KILL = true;
// 是否绕过 inline-hook 检测: 让 sub_452944 恒返回 0
const BYPASS_INLINE_CHK = true;
// 是否打印 backtrace
const PRINT_BT = true;

// !!! 侵入式 hook 开关 !!!
// sub_436bb8 是 sub_448f14 的父函数, sub_432774 调用极频繁;
// attach 它们的 trampoline 会与加固壳自身的 .text 校验/PLT patch 冲突, 导致 0x449f5c 崩溃。
// 默认关闭, 只保留 sub_431bc4 / sub_452944 两个必要 hook。
const HOOK_TOP = false;       // hook sub_436bb8
const HOOK_JAVASCAN = false;  // hook sub_432774
// 异常处理器: 若崩在 libDexHelper.so 内, 试探性地把 pc+4 跳过该指令继续执行
const SKIP_LIBDEX_FAULT = false;
// 修复 0x449f5c 崩溃: hook sub_441bc4(ELF符号解析器), 把 g_signal_pipe_fds 返回值
// 重定向到合法可写内存, 使 "*x0_112 = 0xffffffff" 不再崩溃
const FIX_PERFETTO = true;

// 监控/拦截进程退出: 抓 "谁 kill 了进程"
const WATCH_KILL = true;       // hook exit/abort/kill/tgkill 打印来源
const BLOCK_SELF_KILL = true;  // 吞掉 kill/tgkill/tkill/pthread_kill 的自杀调用
const BLOCK_EXIT = true;       // 吞掉来自 libDexHelper 的 exit/_exit/abort (危险, 但用于探测)

const OFF = {
    kill:       0x31bc4,
    inlineChk:  0x52944,
    javaScan:   0x32774,
    top:        0x36bb8,
    symResolve: 0x41bc4,   // sub_441bc4: 自实现 ELF 符号解析
    isHooked:   0x326e0,   // ArtMethod::isHooked(env, method): 检测 ART 方法 entry 是否被 hook
};

// 绕过 ArtMethod::isHooked, 直接返回 0(未 hook), 避免 sub_432774 读 entry_point 越界崩溃
const BYPASS_ISHOOKED = true;
// 绕过核心 hook 检测原语 sub_432774, 恒返回 0(未 hook)。
// 它被 isHooked / sub_433028(批量) / sub_452944(inline) / sub_4612cc 调用, 是所有 hook 检测的根。
const BYPASS_SUB432774 = true;

// category bit -> 检测名
const CATEGORY = {
    0x1: 'root',
    0x2: 'usb?',
    0x4: 'emu',
    0x8: 'appmon?',
    0x10: 'proxy',
    0x20: 'polling',
    0x40: 'inject',
    0x80: 'xposed',
    0x100: 'frida',
    0x200: 'hook',
    0x400: 'integrity',
    0x800: 'signature',
    0x1000: 'debug',
    0x2000: 'rom',
    0x4000: 'display',
    0x8000: 'bl',
    0x10000: 'developer',
    0x20000: 'unsource',
    0x40000: 'location',
};

function catName(v) {
    return CATEGORY[v.toInt32 ? v.toInt32() : v] || ('0x' + Number(v).toString(16));
}

function bt(ctx, base) {
    if (!PRINT_BT) return '';
    try {
        return Thread.backtrace(ctx, Backtracer.FUZZY)
            .map(a => {
                const off = a.sub(base);
                const inMod = off.compare(0) >= 0 && off.compare(0x200000) < 0;
                return '    ' + a + (inMod ? ('  ' + MODULE + '+0x' + off.toString(16)) : ('  ' + (DebugSymbol.fromAddress(a) || '')));
            })
            .join('\n');
    } catch (e) { return '    <bt err ' + e + '>'; }
}

function hexArg(a) {
    if (a === undefined || a === null) return 'null';
    return a.toString();
}

function safeCStr(p) {
    try {
        if (p.isNull()) return 'null';
        return JSON.stringify(p.readUtf8String());
    } catch (e) {
        try { return JSON.stringify(p.readCString()); } catch (e2) { return '<' + p + '>'; }
    }
}

function install(base) {
    console.log('[*] ' + MODULE + ' base = ' + base);
    globalThis.__DEX_BASE = base;

    const killAddr = base.add(OFF.kill);
    const inlineAddr = base.add(OFF.inlineChk);
    const javaScanAddr = base.add(OFF.javaScan);
    const topAddr = base.add(OFF.top);

    // ---- sub_431bc4: kill / report ----
    // void sub_431bc4(int category, int magic, int arg3)
    if (BYPASS_KILL) {
        // 用 replace 完全接管: 打印后直接返回, 既不上报也不 jump 非法地址
        const origType = new NativeFunction(killAddr, 'void', ['int', 'int', 'int']);
        Interceptor.replace(killAddr, new NativeCallback(function (cat, magic, arg3) {
            const c = cat >>> 0, m = magic >>> 0, a3 = arg3 >>> 0;
            console.log('\n========== sub_431bc4 (KILL/REPORT) [BYPASSED] ==========');
            console.log('  category = 0x' + c.toString(16) + '  (' + catName(c) + ')');
            console.log('  magic    = 0x' + m.toString(16));
            console.log('  jumpTargetIfCrash = 0x' + ((m & a3 & 0xfffffffc) >>> 0).toString(16));
            // 不调用原函数, 直接返回
        }, 'void', ['int', 'int', 'int']));
        void origType;
    } else {
        Interceptor.attach(killAddr, {
            onEnter(args) {
                this.cat = args[0].toInt32() >>> 0;
                this.magic = args[1].toInt32() >>> 0;
                this.arg3 = args[2].toInt32() >>> 0;
                const jumpTarget = (this.magic & this.arg3 & 0xfffffffc) >>> 0;
                console.log('\n========== sub_431bc4 (KILL/REPORT) ==========');
                console.log('  category = 0x' + this.cat.toString(16) + '  (' + catName(this.cat) + ')');
                console.log('  magic    = 0x' + this.magic.toString(16));
                console.log('  arg3     = 0x' + this.arg3.toString(16));
                console.log('  -> 若走崩溃分支, jump target = 0x' + jumpTarget.toString(16) + ' (非法地址)');
                console.log(bt(this.context, base));
            },
            onLeave(retval) {
                console.log('  <== sub_431bc4 returned (未崩溃)');
            }
        });
    }

    // ---- sub_452944: inline-hook 检测 ----
    Interceptor.attach(inlineAddr, {
        onEnter(args) {
            this.ver = args[0].toInt32();
            this.lib = safeCStr(args[1]);
            this.sym = safeCStr(args[2]);
            console.log('\n---- sub_452944 (INLINE-HOOK CHECK) ----');
            console.log('  version = ' + this.ver);
            console.log('  lib     = ' + this.lib);
            console.log('  symbol  = ' + this.sym);
            console.log(bt(this.context, base));
        },
        onLeave(retval) {
            console.log('  sub_452944 ret = ' + retval + '  (1=检测到hook)');
            if (BYPASS_INLINE_CHK && retval.toInt32() === 1) {
                console.log('  [BYPASS] 强制返回 0');
                retval.replace(0);
            }
        }
    });

    // ---- sub_432774: Java 入口点批量检查 (量大, 只计数; 默认关闭, 易冲突) ----
    if (HOOK_JAVASCAN) {
        let javaScanCount = 0;
        Interceptor.attach(javaScanAddr, {
            onEnter(args) {
                javaScanCount++;
                if (javaScanCount <= 3) {
                    console.log('[sub_432774] Java入口点检查 #' + javaScanCount);
                } else if (javaScanCount % 500 === 0) {
                    console.log('[sub_432774] 调用次数 = ' + javaScanCount);
                }
            }
        });
    }

    // ---- sub_436bb8: 顶层入口 (默认关闭, 是崩溃函数的父函数, 极易冲突) ----
    if (HOOK_TOP) {
        Interceptor.attach(topAddr, {
            onEnter(args) {
                console.log('\n############ sub_436bb8 ENTER (顶层反调试) ############');
                console.log(bt(this.context, base));
            },
            onLeave(retval) {
                console.log('############ sub_436bb8 LEAVE ret=' + retval + ' ############');
            }
        });
    }
    void javaScanAddr; void topAddr;

    // ---- sub_441bc4: ELF 符号解析器, 修复 perfetto g_signal_pipe_fds 崩溃 ----
    if (FIX_PERFETTO) {
        const symAddr = base.add(OFF.symResolve);
        const fakePerfetto = Memory.alloc(64);  // 合法可写, 供 *x0_112=-1 / x0_112[1]=-1 写入
        fakePerfetto.writeByteArray(new Array(64).fill(0));
        Interceptor.attach(symAddr, {
            onEnter(args) {
                this.sym = safeCStr(args[1]);
            },
            onLeave(retval) {
                if (this.sym && this.sym.indexOf('g_signal_pipe_fds') !== -1) {
                    console.log('\n[FIX_PERFETTO] sub_441bc4("g_signal_pipe_fds") 原返回=' + retval
                        + ' -> 重定向到合法内存 ' + fakePerfetto);
                    retval.replace(fakePerfetto);
                }
            }
        });
    }

    // ---- dump 全局反调试配置 flags: [[base+0x102de0]] + 0x164 ----
    try {
        const gotSlot = base.add(0x102de0);          // 0x502de0
        const cfgPtr = gotSlot.readPointer();          // -> 全局结构
        const cfg = cfgPtr.readPointer();              // -> 实际 config
        const flags = cfg.add(0x164).readU32();
        console.log('\n[*] 反调试配置 flags @[[0x502de0]]+0x164 = 0x' + flags.toString(16));
        const enabled = [];
        Object.keys(CATEGORY).forEach(k => {
            const bit = parseInt(k);
            if (flags & bit) enabled.push(CATEGORY[k] + '(0x' + bit.toString(16) + ')');
        });
        console.log('    启用的检测项: ' + (enabled.length ? enabled.join(', ') : '(无, 命中即崩溃)'));
    } catch (e) {
        console.log('[!] dump config 失败: ' + e);
    }

    // ---- sub_432774: 核心 hook 检测原语, 恒返回 0 ----
    if (BYPASS_SUB432774) {
        const p = base.add(OFF.javaScan);
        Interceptor.replace(p, new NativeCallback(function (a1, a2, a3) {
            return 0; // 0 = 未检测到 hook, 所有调用者走"环境干净"分支
        }, 'int', ['pointer', 'pointer', 'pointer']));
        console.log('[*] sub_432774 @ ' + p + ' 已接管 (核心检测原语, 恒返回 0)');
    }

    // ---- ArtMethod::isHooked: 强制返回 0 (未 hook) ----
    if (BYPASS_ISHOOKED) {
        const p = base.add(OFF.isHooked);
        let cnt = 0;
        Interceptor.replace(p, new NativeCallback(function (env, method) {
            cnt++;
            if (cnt <= 5) console.log('[BYPASS_ISHOOKED] isHooked() 调用 #' + cnt + ' -> 返回 0');
            return 0;
        }, 'int', ['pointer', 'pointer']));
        console.log('[*] isHooked @ ' + p + ' 已接管 (恒返回 0)');
    }

    if (WATCH_KILL) installKillWatch(base);

    console.log('[*] hooks installed. BYPASS_KILL=' + BYPASS_KILL + ' BYPASS_INLINE_CHK=' + BYPASS_INLINE_CHK);
}

// ============ 进程退出监控 / 拦截 ============
function installKillWatch(base) {
    const MY_PID = Process.id;
    const LETHAL = [4, 6, 9, 11, 15, 19]; // ILL/ABRT/KILL/SEGV/TERM/STOP

    function raFrom(ctx) {
        // 用浅 backtrace 判断是否来自 libDexHelper
        try {
            const frames = Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 8);
            for (const a of frames) {
                const off = a.sub(base);
                if (off.compare(0) >= 0 && off.compare(0x200000) < 0) {
                    return MODULE + '+0x' + off.toString(16);
                }
            }
            return frames.length ? ('' + frames[0]) : '?';
        } catch (e) { return '?'; }
    }

    // ---- exit / _exit / _Exit / abort ----
    // Frida 17: Module.findExportByName(null, name) 已移除, 改用 Module.findGlobalExportByName(name)
    ['exit', '_exit', '_Exit', 'abort'].forEach(name => {
        const p = Module.findGlobalExportByName(name);
        if (!p) return;
        Interceptor.attach(p, {
            onEnter(args) {
                const from = raFrom(this.context);
                let raStr = '?';
                try {
                    const ra = this.returnAddress;
                    const o = ra.sub(base);
                    raStr = (o.compare(0) >= 0 && o.compare(0x200000) < 0) ? (MODULE + '+0x' + o.toString(16)) : ('' + ra);
                } catch (e) {}
                console.log('\n[KILL] ' + name + '(' + (name === 'abort' ? '' : args[0]) + ')  ra=' + raStr + '  from=' + from);
                console.log(bt(this.context, base));
                const fromDex = (from.indexOf(MODULE) === 0) || (raStr.indexOf(MODULE) === 0);
                if (BLOCK_EXIT && fromDex) {
                    console.log('  [BLOCK] 挂起线程, 阻止 ' + name + ' 退出');
                    Thread.sleep(999999); // onEnter 永不返回 -> 原函数不执行
                }
            }
        });
    });

    // ---- kill(pid, sig) ----
    const killP = Module.findGlobalExportByName('kill');
    if (killP) {
        const orig = new NativeFunction(killP, 'int', ['int', 'int']);
        Interceptor.replace(killP, new NativeCallback(function (pid, sig) {
            console.log('\n[KILL] kill(pid=' + pid + ', sig=' + sig + ')');
            if (BLOCK_SELF_KILL && (pid === MY_PID || pid === 0 || pid === -1) && LETHAL.indexOf(sig) !== -1) {
                console.log('  [BLOCK] 吞掉自杀 kill');
                return 0;
            }
            return orig(pid, sig);
        }, 'int', ['int', 'int']));
    }

    // ---- tgkill(tgid, tid, sig) ----
    const tgkillP = Module.findGlobalExportByName('tgkill');
    if (tgkillP) {
        const orig = new NativeFunction(tgkillP, 'int', ['int', 'int', 'int']);
        Interceptor.replace(tgkillP, new NativeCallback(function (tgid, tid, sig) {
            console.log('\n[KILL] tgkill(tgid=' + tgid + ', tid=' + tid + ', sig=' + sig + ')');
            if (BLOCK_SELF_KILL && (tgid === MY_PID || tgid === 0) && LETHAL.indexOf(sig) !== -1) {
                console.log('  [BLOCK] 吞掉自杀 tgkill');
                return 0;
            }
            return orig(tgid, tid, sig);
        }, 'int', ['int', 'int', 'int']));
    }

    // ---- tkill(tid, sig) ----
    const tkillP = Module.findGlobalExportByName('tkill');
    if (tkillP) {
        const orig = new NativeFunction(tkillP, 'int', ['int', 'int']);
        Interceptor.replace(tkillP, new NativeCallback(function (tid, sig) {
            console.log('\n[KILL] tkill(tid=' + tid + ', sig=' + sig + ')');
            if (BLOCK_SELF_KILL && LETHAL.indexOf(sig) !== -1) {
                console.log('  [BLOCK] 吞掉 tkill');
                return 0;
            }
            return orig(tid, sig);
        }, 'int', ['int', 'int']));
    }

    // ---- pthread_kill(thread, sig) ----
    const pkP = Module.findGlobalExportByName('pthread_kill');
    if (pkP) {
        const orig = new NativeFunction(pkP, 'int', ['pointer', 'int']);
        Interceptor.replace(pkP, new NativeCallback(function (thr, sig) {
            console.log('\n[KILL] pthread_kill(sig=' + sig + ')');
            if (BLOCK_SELF_KILL && LETHAL.indexOf(sig) !== -1) {
                console.log('  [BLOCK] 吞掉 pthread_kill');
                return 0;
            }
            return orig(thr, sig);
        }, 'int', ['pointer', 'int']));
    }

    // ---- raw syscall: exit_group(94) / kill(129) / tgkill(131) / tkill(130) ----
    const scP = Module.findGlobalExportByName('syscall');
    if (scP) {
        Interceptor.attach(scP, {
            onEnter(args) {
                const nr = args[0].toInt32();
                if (nr === 94 || nr === 93) {  // exit_group / exit
                    console.log('\n[KILL] syscall(exit_group/exit=' + nr + ', code=' + args[1] + ')  from=' + raFrom(this.context));
                    console.log(bt(this.context, base));
                } else if (nr === 129 || nr === 130 || nr === 131) { // kill/tkill/tgkill
                    console.log('\n[KILL] syscall(nr=' + nr + ' kill-family)  from=' + raFrom(this.context));
                }
            }
        });
    }

    console.log('[*] kill-watch 已安装 (pid=' + MY_PID + ') BLOCK_SELF_KILL=' + BLOCK_SELF_KILL + ' BLOCK_EXIT=' + BLOCK_EXIT);
}

// ============ SIGSEGV 崩溃定位 ============
// 反调试常主动触发非法访问来 kill; 捕获它可以看到崩溃 pc / 匿名内存地址
Process.setExceptionHandler(function (details) {
    const base = globalThis.__DEX_BASE;
    const pc = details.context.pc;
    // 诊断模式: 不再只盯 libDexHelper.so, 只把 ART/boot.oat 自身的隐式检查噪音过滤掉,
    // 其余(包括 libmsaoaidsec.so / 匿名内存 等)全部打印出来, 方便定位新的崩溃点。
    const pcMod = Process.findModuleByAddress(pc);
    const pcModName = pcMod ? pcMod.name : null;
    const isArtNoise = pcModName === 'libart.so' || (pcModName && pcModName.indexOf('boot') === 0 && pcModName.indexOf('.oat') !== -1);
    if (isArtNoise) {
        return false; // ART 隐式 null-check / GC read-barrier / suspend-check, 交给 ART 自己处理
    }
    try {
        console.log('\n!!!!!!!!!! EXCEPTION !!!!!!!!!!');
        console.log('  type    = ' + details.type);
        console.log('  address = ' + details.address);
        console.log('  pc      = ' + pc);
        if (base) {
            const off = pc.sub(base);
            if (off.compare(0) >= 0 && off.compare(0x200000) < 0) {
                console.log('  pc in ' + MODULE + '+0x' + off.toString(16));
            } else {
                console.log('  pc module = ' + (pcMod ? (pcMod.name + '+0x' + pc.sub(pcMod.base).toString(16)) : '<anonymous/unknown>'));
            }
        } else {
            console.log('  pc module = ' + (pcMod ? (pcMod.name + '+0x' + pc.sub(pcMod.base).toString(16)) : '<anonymous/unknown>'));
        }
        // 寄存器 dump: lr 指向调用来源, 定位谁 call 到坏地址
        const ctx = details.context;
        try {
            const lr = ctx.lr, sp = ctx.sp;
            console.log('  lr      = ' + lr);
            const lrMod = Process.findModuleByAddress(lr);
            console.log('  lr module = ' + (lrMod ? (lrMod.name + '+0x' + lr.sub(lrMod.base).toString(16)) : '<unknown>'));
            console.log('  sp      = ' + sp);
            // 关键寄存器
            const regs = [];
            for (let i = 0; i <= 30; i++) {
                const r = ctx['x' + i];
                if (r === undefined) continue;
                const rm = Process.findModuleByAddress(r);
                regs.push('  x' + i + '=' + r + (rm ? (' (' + rm.name + '+0x' + r.sub(rm.base).toString(16) + ')') : ''));
            }
            console.log(regs.join('\n'));
        } catch (e) { console.log('  reg dump err: ' + e); }

        console.log('  backtrace:');
        console.log(bt(details.context, base || ptr(0)));

        // 试探: 崩在 libDexHelper.so 内则跳过该指令 (pc+=4) 继续
        if (SKIP_LIBDEX_FAULT && base) {
            const off = pc.sub(base);
            if (off.compare(0) >= 0 && off.compare(0x200000) < 0) {
                console.log('  [SKIP] pc += 4, 跳过 ' + MODULE + '+0x' + off.toString(16));
                details.context.pc = pc.add(4);
                return true; // 吞掉异常, 继续执行
            }
        }
    } catch (e) {
        console.log('exc handler err: ' + e);
    }
    // 返回 false: 不吞掉异常, 让进程按原逻辑继续(通常崩溃), 仅用于观测
    return false;
});

// ============ libmsaoaidsec.so 绕过 (基于 IDA 逆向报告, NagaLinker v8.83) ============
// 结论: 真正杀进程是内联 exit_group(0) shellcode(mmap RWX 后直接 svc, 不经过
// libc 符号), 外加 fork+ptrace 反调试, 符号级 hook(kill/tgkill/exit)完全无效。
// 拦截时机: 该 so 首次调用 pthread_create 时(sub_1B924/2701C/9150 等), 说明
// .init_proc 已经映射完并正在同步执行 —— 这是 JS 侧能拿到 base 的最早时机,
// 在这一刻(仍处于该 so 自己的调用栈里, 早于新线程被 OS 调度)一次性把 P0/P1
// 全部 patch 掉, 再顺带清空当前这个线程的入口。
const SEC_MODULE = 'libmsaoaidsec.so';
const WATCH_SEC = true;
const NEUTER_SEC_THREADS = false;  // P0/P1 已摘掉杀招, 让线程正常跑完, 避免主线程等待收尾信号卡死
const PATCH_SEC_P0 = true;         // P0: 4 个 exit_group 执行器 + 统一杀点 sub_11FA4
const PATCH_SEC_P1 = true;         // P1: TracerPid/T态/maps/fd/CRC32 等检测原语恒返回"未命中"
const PATCH_SEC_P2 = false;        // P2: ADB 检测 / ART 结构校验 / fork+ptrace(风险更高, 默认关)

const SEC_OFF = {
    // P0 — 杀进程执行器
    exitExec1: 0x234E0,   // void sub_234E0(uint32_t)  内联 exit_group shellcode 执行器
    exitExec2: 0x26334,   // void sub_26334(int64_t)   线程1 每轮调用, 首轮即自杀倒计时
    exitExec3: 0x269AC,   // void sub_269AC(int64_t)
    exitExec4: 0x260B0,   // void sub_260B0(int64_t)
    killPoint: 0x11FA4,   // void sub_11FA4(void)      统一杀点(TracerPid/T态/ADB/CRC32 都走它)
    // P1 — 检测原语
    tracerPid:    0x1AE48, // int sub_1AE48(void)        读 TracerPid
    tracerPPid:   0x1AB54, // int sub_1AB54(uint32_t)    tracer 的 PPid 是否等于自己
    taskTState:   0x1B730, // int sub_1B730(void)        遍历 task/*/stat 找 T 态
    taskNameScan: 0x1BFAC, // void* sub_1BFAC(void)      task/%s/status 找 gum-js-loop/gmain
    fdScan:       0x1C158, // void* sub_1C158(void)      /proc/self/fd 找 linjector
    mapsScan:     0x1C26C, // int sub_1C26C(void)        maps + ELF 指纹找 frida-agent
    crcScan:      0x1678C, // int sub_1678C(void)        模块 CRC32 特征扫描(线程3)
    // P2 — 低优先级
    adbJudge:     0x19A58, // uint32_t sub_19A58(void*)
    artCheck:     0x8CAC,  // int sub_8CAC(void)
    adbDetect:    0x19E0C, // void sub_19E0C(void)
    forkPtrace:   0x1B380, // int sub_1B380(void*, void*)
};

function patchSecModule(base) {
    function noop(off, retType, argTypes, retVal) {
        try {
            Interceptor.replace(base.add(off), new NativeCallback(function () {
                return retVal;
            }, retType, argTypes));
            console.log('  [PATCH] ' + SEC_MODULE + '+0x' + off.toString(16) + ' -> no-op(ret=' + retVal + ')');
        } catch (e) {
            console.log('  [!] patch 0x' + off.toString(16) + ' 失败: ' + e);
        }
    }

    if (PATCH_SEC_P0) {
        noop(SEC_OFF.exitExec1, 'void', ['uint32'], undefined);
        noop(SEC_OFF.exitExec2, 'void', ['int64'], undefined);
        noop(SEC_OFF.exitExec3, 'void', ['int64'], undefined);
        noop(SEC_OFF.exitExec4, 'void', ['int64'], undefined);
        noop(SEC_OFF.killPoint, 'void', [], undefined);
    }
    if (PATCH_SEC_P1) {
        noop(SEC_OFF.tracerPid, 'int', [], 0);
        noop(SEC_OFF.tracerPPid, 'int', ['uint32'], 1);
        noop(SEC_OFF.taskTState, 'int', [], 0);
        noop(SEC_OFF.taskNameScan, 'pointer', [], NULL);
        noop(SEC_OFF.fdScan, 'pointer', [], NULL);
        noop(SEC_OFF.mapsScan, 'int', [], 0);
        noop(SEC_OFF.crcScan, 'int', [], 0);
    }
    if (PATCH_SEC_P2) {
        noop(SEC_OFF.adbJudge, 'uint32', ['pointer'], 0);
        noop(SEC_OFF.artCheck, 'int', [], 0);
        noop(SEC_OFF.adbDetect, 'void', [], undefined);
        noop(SEC_OFF.forkPtrace, 'int', ['pointer', 'pointer'], 0);
    }
    console.log('[*] ' + SEC_MODULE + ' P0/P1/P2 patch 完成 (P0=' + PATCH_SEC_P0 + ' P1=' + PATCH_SEC_P1 + ' P2=' + PATCH_SEC_P2 + ')');
}

function installSecModuleWatch() {
    const pthreadCreate = Module.findGlobalExportByName('pthread_create');
    if (!pthreadCreate) return;
    const patchedThreadAddrs = new Set();
    let secBasePatched = false;
    Interceptor.attach(pthreadCreate, {
        onEnter(args) {
            const startRoutine = args[2];
            const m = Process.findModuleByAddress(startRoutine);
            if (!(m && m.name === SEC_MODULE)) return;

            // 第一次抓到该 so 的 pthread_create 调用: 立刻整体 patch P0/P1/P2,
            // 此时仍处于该 so 自己的调用栈内, 新线程还没被 OS 调度起来。
            if (!secBasePatched) {
                secBasePatched = true;
                console.log('\n[*] ' + SEC_MODULE + ' base = ' + m.base + ' (首次 pthread_create 命中, 开始 patch)');
                patchSecModule(m.base);
            }

            const off = startRoutine.sub(m.base);
            const key = startRoutine.toString();
            console.log('[pthread_create] ' + SEC_MODULE + ' 检测线程 entry offset=0x' + off.toString(16));
            if (NEUTER_SEC_THREADS && !patchedThreadAddrs.has(key)) {
                patchedThreadAddrs.add(key);
                try {
                    Interceptor.replace(startRoutine, new NativeCallback(function () {
                        console.log('  [NEUTER] ' + SEC_MODULE + '+0x' + off.toString(16) + ' 检测线程已被清空, 直接返回');
                        return NULL;
                    }, 'pointer', ['pointer']));
                } catch (e) {
                    console.log('  [!] replace 失败(可能已被处理过): ' + e);
                }
            }
        }
    });
    console.log('[*] ' + SEC_MODULE + ' 的 pthread_create 监控已装好 (NEUTER_SEC_THREADS=' + NEUTER_SEC_THREADS + ')');
}

if (WATCH_SEC) installSecModuleWatch();

// ============ 等待模块加载 ============
function tryInstall() {
    const m = Process.findModuleByName(MODULE);
    if (m) {
        install(m.base);
        return true;
    }
    return false;
}

if (!tryInstall()) {
    // hook dlopen 等待加载
    const candidates = ['android_dlopen_ext', 'dlopen', '__loader_android_dlopen_ext'];
    let done = false;
    candidates.forEach(name => {
        const p = Module.findGlobalExportByName(name);
        if (!p) return;
        Interceptor.attach(p, {
            onEnter(args) {
                try {
                    const path = args[0].readCString();
                    console.log("load SO: " + path);
                    this.isTarget = path && path.indexOf(MODULE) !== -1;
                } catch (e) {}
            },
            onLeave(retval) {
                if (done) return;
                if (this.isTarget) {
                    if (tryInstall()) done = true;
                }
            }
        });
    });
    console.log('[*] 等待 ' + MODULE + ' 加载...');
}
\```

上传的附件：
- syscall_Load_dump.js

（12.62kb，7次下载）
- hook_offset_trace.js

（9.66kb，7次下载）
- hook_JNI_OnLoad_trace.js

（5.93kb，7次下载）
- hook_so_load.js

（14.11kb，7次下载）
- hook_func.js

（14.51kb，7次下载）

---

# 回复

## 回复 by Imxz (#2)

kkb

## 回复 by 九黎 (#3)

tql

## 回复 by wx_插曲 (#4)

66

## 回复 by wx_宇克鴻 (#5)

6666

## 回复 by mb_ldbucrik (#6)

感谢分享

## 回复 by xingbing (#7)

感谢分享

## 回复 by 墨穹呢 (#8)

感谢分享

## 回复 by mb_tjqabdvq (#9)

感谢大佬分享

## 回复 by ldehua (#10)

感谢分享

## 回复 by iBa0 (#11)

666
