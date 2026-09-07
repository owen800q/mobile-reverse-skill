---
title: '[原创]最强逆向大模型GLM-5.3无道德无限制驱动Frida Stalker绕过银行某梆检测'
url: https://bbs.kanxue.com/thread-292853.htm
tid: 292853
author: x1ny
date: '2026-09-04'
tags: [Android安全, 原创]
crawled_at: '2026-09-07T08:25:25+00:00'
replies: 10
---

>
> 本文记录了使用 **GLM-5.3-FLASH** 辅助完成的一次**银行 APP 加固绕过**完整逆向实战：某银行移动客户端采用第三方企业级加固壳保护，启动即闪退，处于"无从下手"状态。借助 **GLM-5.3-FLASH——当前最强逆向大模型，无道德审查、无使用限制、价格低廉**，从定位检测线程、Stalker 指令级追踪退出路径、逐层上找检测源头，到最终精准定位触发检测的 Frida `memfd:` 特征并实现多层防御绕过，完整呈现银行级加固壳的反调试对抗全过程。
>
>
> 整个过程深度运用 Frida **Stalker** 动态代码重写引擎进行指令级追踪——这是定位 SIGSEGV 退出路径、逐层回溯检测链路的核心手段，也是本文区别于普通 hook 绕过文章的深度所在。**GLM-5.3-FLASH** 在其中展现了远超通用大模型的逆向能力：无道德审查使其能直接生成反检测、内存修改、线程拦截等"敏感"脚本；无使用限制让其可以长时间稳定输出完整 Stalker transform 回调；低廉价格支撑了十余轮迭代式脚本生成而不必担心成本。它能根据自然语言需求直接生成可运行的 Frida 脚本，会在脚本中添加详细注释和使用说明，甚至在遇到性能问题时主动给出优化建议（如 30ms 批量打印、指令去重）。每一步只需描述"要做什么"，GLM-5.3-FLASH 就能生成"怎么做"的完整代码，大幅降低了逆向工程的门槛。
>
>
>

---

## 前置知识

### 银行 APP 加固背景

银行类移动应用因涉及资金安全与合规要求，普遍采用**第三方企业级加固壳**（如梆梆、爱加密、360 加固、通付盾等）对 DEX、SO 进行保护。这类加固壳的核心防御手段之一就是**反调试与反 Frida 检测**：一旦检测到调试器或 Frida 注入，立即杀死进程，使逆向者无从下手。本文分析的即是一例典型银行客户端——其加固壳在 `JNI_OnLoad` 阶段与异步线程中布设了多重检测，启动即闪退。绕过这类加固是银行 APP 安全测试、风控分析、接口逆向的前置条件。

### Frida 简介

Frida 是一个跨平台动态插桩工具，它将 JavaScript 引擎（V8）注入目标进程，允许在运行时修改函数行为、读写内存、跟踪执行流。在 Android 逆向中，Frida 常用于：

- **Hook 函数**：`Interceptor.attach` 在函数入口/出口插入代码，`Interceptor.replace` 替换整个函数实现
- **读写内存**：`Memory.readByteArray` / `Memory.writeByteArray`
- **跟踪指令**：`Stalker.follow` 实时捕获每条机器指令的执行
- **模块查找**：`Module.findExportByName` / `Process.findModuleByName`

### Android 应用启动流程

```python
Zygote fork → ActivityThread.main → Application.onCreate
                                       ↓
                                  加载 native 库
                                       ↓
                              System.loadLibrary("DexHelper")
                                       ↓
                            android_dlopen_ext("libDexHelper.so")
                                       ↓
                                 dlopen 返回后调用
                                       ↓
                              JNI_OnLoad(JavaVM*, void*)
                                       ↓
                           注册 JNI 方法 / 执行初始化逻辑
                                       ↓
                          （反调试检测常在此处执行）
\```

**关键点**：SO 文件被 `dlopen` 加载后，Android 会自动调用其导出的 `JNI_OnLoad` 函数。许多加固方案（如乐固、梆梆、爱加密）将反调试逻辑放在 `JNI_OnLoad` 中，因为它在 `Application.onCreate` 之前执行，此时 Java 层尚未完全初始化，调试者很难介入。

### 常见反调试手段

| 手段 | 原理 | 检测特征 |
|-|-|-|
| `/proc/self/status` 检测 | 读取 TracerPid 字段 | 非 0 表示被调试 |
| `/proc/self/maps` 检测 | 扫描内存映射 | 发现 Frida agent 的 `memfd:` 映射 |
| `ptrace` 自附加 | 进程 ptrace 自己 | 返回 -1 表示已被调试 |
| 端口扫描 | 检测 Frida 默认端口 27042 | `connect` 成功即有 Frida |
| 线程名扫描 | 遍历 `/proc/self/task` | 发现 `gmain`、`gdbus` 等 Frida 线程 |
| `process_vm_readv` | 跨进程读取内存 | 检查映射内容是否为 ELF 魔数 |

### ARM64 跳转指令

| 指令 | 含义 | 是否返回 |
|-|-|-|
| `b` | 跳转到立即地址 | 不返回 |
| `br` | 跳转到寄存器中的地址 | 不返回 |
| `bl` | 跳转到函数（保存返回地址到 x30/lr） | 返回 |
| `svc 0` | 触发系统调用 | 取决于系统调用 |

### Stalker 工作原理

Frida Stalker 通过**动态代码重写**实现指令级跟踪：它将目标线程的每条指令复制到一块"影子内存"中，在每条指令后插入回调通知，然后让线程跳转到影子内存执行。这样可以实时输出执行的每条指令地址和助记符，是定位退出路径的利器。但 Stalker 会带来较大性能开销，对循环函数需配合**去重**和**批量输出**使用。

**深入理解 Stalker 的几个关键点（本文深度依赖）**：

1. **transform 回调以基本块为单位**：Stalker 不是逐条指令调用 transform，而是在每个基本块（basic block，以分支/跳转指令结尾的线性指令序列）首次执行时调用一次 transform。在 transform 内部用 `iterator.next()` 遍历块内每条指令，`iterator.keep()` 保留原指令，可在此插入 `iterator.putCallout()` 自定义回调。
2. **影子内存与代码缓存**：重写后的代码存放在 Stalker 分配的可执行内存中，原内存只读不受影响。这意味着即使原 SO 的代码段做了完整性校验，Stalker 依然能跟踪——因为执行流已跳到影子内存。
3. **跨模块指令过滤**：Stalker 会跟踪线程内**所有**代码，包括 ART、libc、linker 等。实战中必须用 `instruction.address` 与目标模块基址/大小比较，只输出目标 SO 内的指令，否则会被海量无关指令刷屏。本文所有 Stalker 脚本均采用此过滤策略。
4. **性能优化：批量输出 + 去重**：`console.log` 走 Frida IPC 通道，逐条打印会严重拖慢甚至卡死进程。本文采用 **30ms 定时批量输出**（缓冲到数组，定时 `join` 一次打印）+ 可选**指令去重**（同一地址只打印首次）的双重优化，是 Stalker 实战的标配手法。
5. **unfollow 与 flush**：跟踪结束必须调用 `Stalker.unfollow(tid)` 停止重写，并调用 `Stalker.flush()` 冲刷缓冲区中剩余的指令事件，否则尾部指令会丢失——这对定位"退出前最后几条指令"至关重要。

---

## 阶段1：定位并绕过退出检测

### 步骤一：初步判断 — 确认反调试存在

#### 现象观察

直接使用 Frida 启动目标银行应用（包名 `com.tzb.mobilehub`，下文统称"目标银行 APP"），发现进程启动后不久便自动退出，但**不是立即退出**——这暗示加固壳的检测逻辑运行在某个异步线程中，而非 `JNI_OnLoad` 同步执行。这种"延迟退出"是银行级加固壳的典型特征：故意错开启动瞬间，增加逆向者定位难度。

#### 操作过程

启动 Frida 服务并附加目标进程：

```python
./aaabbb -l 127.0.0.1:14725
adb forward tcp:14725 tcp:14725
frida -H 127.0.0.1:14725 -f com.tzb.mobilehub
\```

#### 分析

程序延迟退出而非立即退出，说明检测在线程中执行。**判断思路**：既然是线程检测，可以尝试用 Frida 拦截 `pthread_create`，阻止目标模块创建线程，观察程序是否还会退出。这引出了下一步——杀线程。

---

### 步骤二：杀线程 — 阻止目标模块创建线程

#### 前置知识：pthread_create 与线程拦截

`pthread_create` 是创建线程的核心函数，原型为：

```c
int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                   void *(*start_routine)(void *), void *arg);
\```

第三个参数 `start_routine` 是线程函数地址。通过 `Interceptor.replace` 替换 `pthread_create`，检查 `start_routine` 是否来自目标模块，若是则直接返回 0（假装创建成功），即可阻止线程执行。

#### 向GLM-5.3-FLASH提出需求

>
> 帮我生成 frida 拦截函数，当线程函数来自 libDexHelper.so 模块时：打印日志（模块名、函数偏移、参数）并返回 0（模创建成功，实际阻止线程执行），其他模块创建的函数正常放行
>
>
>

#### GLM-5.3-FLASH 执行

向 GLM-5.3-FLASH 描述需求后，它直接生成了完整的脚本，包含详细注释和使用方式说明。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_ZC9EVB5NJFMJ6HD.webp)

#### 生成代码

```javascript
/**
 * block_dexhelper_threads.js
 *
 * Hook pthread_create：
 *  - 当线程函数 (start_routine) 位于 libDexHelper.so 内时，
 *    打印日志（模块名、函数偏移、参数），并直接返回 0，
 *    模拟线程创建成功，但实际不创建线程（阻止其执行）。
 *  - 其他模块创建的线程正常放行，调用原始 pthread_create。
 *
 * 使用方式：
 *   frida -U -f <包名> -l block_dexhelper_threads.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l block_dexhelper_threads.js
 */

const TARGET_MODULE = "libDexHelper.so";

// int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
    "pointer",
    "pointer",
    "pointer",
    "pointer",
]);

const fakePthreadCreate = new NativeCallback(
    function (thread, attr, startRoutine, arg) {
        const mod = Process.findModuleByAddress(startRoutine);

        if (mod !== null && mod.name === TARGET_MODULE) {
            const offset = startRoutine.sub(mod.base);

            console.log("==================================================");
            console.log("[拦截] 阻止 " + TARGET_MODULE + " 创建线程");
            console.log("  模块名      : " + mod.name);
            console.log("  模块基址    : " + mod.base);
            console.log("  函数地址    : " + startRoutine);
            console.log("  函数偏移    : " + offset);
            console.log("  参数 (arg)  : " + arg);
            console.log("==================================================");

            // 直接返回 0，假装创建成功，实际没有创建线程
            return 0;
        }

        // 其他模块：正常放行
        return originalPthreadCreate(thread, attr, startRoutine, arg);
    },
    "int",
    ["pointer", "pointer", "pointer", "pointer"]
);

Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
\```

#### 结果

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_K6R9WZ5EZTBZNTU.webp)

```powershell
PS D:\Download\XIN\02\GLM> frida  -H 127.0.0.1:14725  -f com.tzb.mobilehub -l block_dexhelper_threads.js
     ____
    / _  |   Frida 16.5.6 - A world-class dynamic instrumentation toolkit
   | (_| |
    > _  |   Commands:
   /_/ |_|       help      -> Displays the help system
   . . . .       object?   -> Display information about 'object'
   . . . .       exit/quit -> Exit
   . . . .
   . . . .
   . . . .   Connected to 127.0.0.1:14725 (id=socket@127.0.0.1:14725)
Spawning `com.tzb.mobilehub`...
[*] 已 hook pthread_create，目标模块: libDexHelper.so
Spawned `com.tzb.mobilehub`. Resuming main thread!
[Remote::com.tzb.mobilehub ]-> Process terminated
[Remote::com.tzb.mobilehub ]->
\```

#### 分析与下一步

即使阻止了 `libDexHelper.so` 创建的所有线程，程序**仍然退出**了。这说明退出逻辑不仅在线程中，可能还在 SO 加载阶段就触发了。需要进一步定位是哪个 SO、在什么时机导致退出。下一步将 Hook `android_dlopen_ext` 监控所有 SO 加载。

---

### 步骤三：Hook dlopen — 监控 SO 加载定位退出 SO

#### 前置知识：android_dlopen_ext

Android 系统加载 SO 使用 `android_dlopen_ext`（比标准 `dlopen` 多一个 `extinfo` 参数）。Hook 此函数可以监控所有 SO 的加载时机，并在目标 SO 加载完成后立即安装进一步 Hook。接下来让GLM-5.3-FLASH帮我们验证确定下一步操作。

#### 向GLM-5.3-FLASH提出需求

>
> 在脚本添加函数，hook android_dlopen_ext 函数，监控所有 so 文件加载，当 so 被加载时打印提示
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_5V3B93GX7CE5V7K.webp)

#### 生成代码

```javascript
/**
 * block_dexhelper_threads.js
 *
 * 功能一：Hook pthread_create
 *  - 当线程函数 (start_routine) 位于 libDexHelper.so 内时，
 *    打印日志（模块名、函数偏移、参数），并直接返回 0，
 *    模拟线程创建成功，但实际没有创建线程（阻止其执行）。
 *  - 其他模块创建的线程正常放行，调用原始 pthread_create。
 *
 * 功能二：Hook android_dlopen_ext
 *  - 监控所有 so 文件的加载，当 libDexHelper.so 被加载时打印提示。
 *
 * 使用方式：
 *   frida -U -f <包名> -l block_dexhelper_threads.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l block_dexhelper_threads.js
 */

const TARGET_MODULE = "libDexHelper.so";

/**
 * Hook pthread_create，拦截目标模块创建的线程
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",
        "pointer",
        "pointer",
        "pointer",
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);

                console.log("==================================================");
                console.log("[拦截] 阻止 " + TARGET_MODULE + " 创建线程");
                console.log("  模块名      : " + mod.name);
                console.log("  模块基址    : " + mod.base);
                console.log("  函数地址    : " + startRoutine);
                console.log("  函数偏移    : " + offset);
                console.log("  参数 (arg)  : " + arg);
                console.log("==================================================");

                // 直接返回 0，假装创建成功，实际没有创建线程
                return 0;
            }

            // 其他模块：正常放行
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
}

/**
 * Hook android_dlopen_ext，监控 so 加载，提示目标模块加载
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            console.log("[dlopen] 加载: " + this.filename);
        },
        onLeave: function (retval) {
            // retval 非空表示加载成功
            if (!retval.isNull() && this.filename.indexOf(TARGET_MODULE) !== -1) {
                const mod = Process.findModuleByName(TARGET_MODULE);
                console.log("**************************************************");
                console.log("[提示] " + TARGET_MODULE + " 已加载!");
                console.log("  路径     : " + this.filename);
                console.log("  句柄     : " + retval);
                if (mod !== null) {
                    console.log("  基址     : " + mod.base);
                    console.log("  大小     : " + mod.size);
                }
                console.log("**************************************************");
            }
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_5G4Q2KTRVKEU6BQ.webp)

加载 `libDexHelper.so` 成功，但之后**没有其他 SO 加载**程序就退出了。推测退出可能发生在 `libDexHelper.so` 的 `JNI_OnLoad` 函数中——因为 `dlopen` 返回后 Android 会自动调用 `JNI_OnLoad`，此时还没有后续 SO 加载。

#### 分析与下一步

既然 SO 加载后没有其他 SO 被加载就退出了，最大嫌疑就是 `JNI_OnLoad`。下一步需要在 `dlopen` 的 `onLeave` 中 Hook `JNI_OnLoad`，观察它的开始和结束时机。

---

### 步骤四：Hook JNI_OnLoad — 确认退出发生在 JNI_OnLoad 中

#### 前置知识：JNI_OnLoad 时机

`JNI_OnLoad` 是 SO 被 `dlopen` 加载后自动调用的初始化函数，原型为：

```c
jint JNI_OnLoad(JavaVM* vm, void* reserved);
\```

它在 `dlopen` 返回**之前**就被调用（因为 `dlopen` 内部会调用 SO 的构造函数和 `JNI_OnLoad`）。因此必须在 `android_dlopen_ext` 的 `onEnter` 或更早安装 Hook，才能捕获 `JNI_OnLoad` 的入口。但实践中在 `onLeave` 中 Hook 也能捕获后续多次调用的情况。

#### 向GLM-5.3-FLASH提出需求

>
> 修改 hookAndroidDlopenExt 函数，在 dlopen 的 onLeave 中实际hook JNI_OnLoad，查看 JNI_OnLoad 加载的开始和结束
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_FMJDASGBEYD5QJF.webp)

#### 生成代码

```javascript
/**
 * block_dexhelper_threads.js
 *
 * 功能一：Hook pthread_create
 *  - 当线程函数 (start_routine) 位于 libDexHelper.so 内时，
 *    打印日志（模块名、函数偏移、参数），并直接返回 0，
 *    模拟线程创建成功，但实际没有创建线程（阻止其执行）。
 *  - 其他模块创建的线程正常放行，调用原始 pthread_create。
 *
 * 功能二：Hook android_dlopen_ext
 *  - 监控所有 so 文件的加载，当 libDexHelper.so 被加载时打印提示。
 *
 * 使用方式：
 *   frida -U -f <包名> -l block_dexhelper_threads.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l block_dexhelper_threads.js
 */

const TARGET_MODULE = "libDexHelper.so";

/**
 * Hook pthread_create，拦截目标模块创建的线程
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",
        "pointer",
        "pointer",
        "pointer",
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);

                console.log("==================================================");
                console.log("[拦截] 阻止 " + TARGET_MODULE + " 创建线程");
                console.log("  模块名      : " + mod.name);
                console.log("  模块基址    : " + mod.base);
                console.log("  函数地址    : " + startRoutine);
                console.log("  函数偏移    : " + offset);
                console.log("  参数 (arg)  : " + arg);
                console.log("==================================================");

                // 直接返回 0，假装创建成功，实际没有创建线程
                return 0;
            }

            // 其他模块：正常放行
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
}

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标模块加载完成后，在 onLeave 中实际挂钩其 JNI_OnLoad，
 * 打印 JNI_OnLoad 执行的开始和结束。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let jniOnLoadHooked = false; // 只挂钩一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            if (!this.isTarget) {
                return;
            }

            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            // 实际挂钩 JNI_OnLoad
            if (!jniOnLoadHooked) {
                // jint JNI_OnLoad(JavaVM* vm, void* reserved)
                const jniOnLoadAddr = Module.findExportByName(TARGET_MODULE, "JNI_OnLoad");
                if (jniOnLoadAddr !== null) {
                    Interceptor.attach(jniOnLoadAddr, {
                        onEnter: function (args) {
                            console.log("[JNI_OnLoad] >>> 开始执行");
                            console.log("  地址     : " + jniOnLoadAddr);
                            if (mod !== null) {
                                console.log("  偏移     : " + jniOnLoadAddr.sub(mod.base));
                            }
                            console.log("  JavaVM*  : " + args[0]);
                            console.log("  reserved : " + args[1]);
                        },
                        onLeave: function (retval) {
                            console.log("[JNI_OnLoad] <<< 执行结束，返回值: " + retval);
                        },
                    });
                    jniOnLoadHooked = true;
                    console.log("[*] 已 hook JNI_OnLoad: " + jniOnLoadAddr);
                } else {
                    console.log("[!] 未找到 JNI_OnLoad 导出符号");
                }
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

打印了 `JNI_OnLoad >>> 开始执行`，但**没有打印** `<<< 执行结束`，进程就终止了。这确认了退出发生在 `JNI_OnLoad` 执行过程中。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_7MNYTWSWRCMT222.webp)

#### 分析与下一步

确认退出发生在 `JNI_OnLoad` 内部，但不知道具体在哪条指令退出。需要用 **Stalker** 实时跟踪 `JNI_OnLoad` 执行的每条指令，找到导致退出的确切位置。

---

### 步骤五：Stalker 追踪 — 定位 JNI_OnLoad 中的退出指令

#### 前置知识：Stalker 指令跟踪

`Stalker.follow(tid, {transform})` 会对指定线程的代码进行动态重写，`transform` 回调中可以遍历每条指令并插入自定义逻辑。为避免被 ART/libc 的指令刷屏，通常只输出目标模块内的指令。

**为什么用 Stalker 而非普通 Hook？** 普通的 `Interceptor.attach` 只能在函数入口/出口观察，无法看到函数内部哪条指令触发了退出。而银行加固壳常用"制造 SIGSEGV"的方式退出（清零 sp/lr 后跳转未映射地址），这种退出不走 `exit`/`abort`，普通 Hook 根本拦不到。只有 Stalker 能逐条指令追踪，捕获到退出前的最后几条指令（如 `mov sp, #0; mov lr, #0; br xN`），从而回溯定位检测点。这是本文使用 Stalker 的根本原因，也是指令级追踪的深度价值所在。

#### 向GLM-5.3-FLASH提出需求

>
> 修改 hookAndroidDlopenExt 函数，通过 Stalker 实时捕获并输出 JNI_OnLoad 函数执行过程中的每条机器指令
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_A37XJ2GQ5MN4MFK.webp)

#### 生成代码

```javascript
/**
 * block_dexhelper_threads.js
 *
 * 功能一：Hook pthread_create
 *  - 当线程函数 (start_routine) 位于 libDexHelper.so 内时，
 *    打印日志（模块名、函数偏移、参数），并直接返回 0，
 *    模拟线程创建成功，但实际没有创建线程（阻止其执行）。
 *  - 其他模块创建的线程正常放行，调用原始 pthread_create。
 *
 * 功能二：Hook android_dlopen_ext
 *  - 监控所有 so 文件的加载，当 libDexHelper.so 被加载时打印提示。
 *
 * 使用方式：
 *   frida -U -f <包名> -l block_dexhelper_threads.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l block_dexhelper_threads.js
 */

const TARGET_MODULE = "libDexHelper.so";

/**
 * Hook pthread_create，拦截目标模块创建的线程
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",
        "pointer",
        "pointer",
        "pointer",
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);

                console.log("==================================================");
                console.log("[拦截] 阻止 " + TARGET_MODULE + " 创建线程");
                console.log("  模块名      : " + mod.name);
                console.log("  模块基址    : " + mod.base);
                console.log("  函数地址    : " + startRoutine);
                console.log("  函数偏移    : " + offset);
                console.log("  参数 (arg)  : " + arg);
                console.log("==================================================");

                // 直接返回 0，假装创建成功，实际没有创建线程
                return 0;
            }

            // 其他模块：正常放行
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
}

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标模块加载完成后，在 onLeave 中实际挂钩其 JNI_OnLoad，
 * 打印 JNI_OnLoad 执行的开始和结束。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let jniOnLoadHooked = false; // 只挂钩一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            if (!this.isTarget) {
                return;
            }

            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            // 实际挂钩 JNI_OnLoad，用 Stalker 跟踪其执行过程中的每条指令
            if (!jniOnLoadHooked) {
                // jint JNI_OnLoad(JavaVM* vm, void* reserved)
                const jniOnLoadAddr = Module.findExportByName(TARGET_MODULE, "JNI_OnLoad");
                if (jniOnLoadAddr !== null) {
                    Interceptor.attach(jniOnLoadAddr, {
                        onEnter: function (args) {
                            console.log("[JNI_OnLoad] >>> 开始执行");
                            console.log("  地址     : " + jniOnLoadAddr);
                            if (mod !== null) {
                                console.log("  偏移     : " + jniOnLoadAddr.sub(mod.base));
                            }
                            console.log("  JavaVM*  : " + args[0]);
                            console.log("  reserved : " + args[1]);

                            // 用 Stalker 跟踪当前线程，实时输出每条机器指令
                            this.tid = Process.getCurrentThreadId();
                            Stalker.follow(this.tid, {
                                transform: function (iterator) {
                                    let instruction = iterator.next();
                                    while (instruction !== null) {
                                        // 只输出目标模块内的指令，避免被 ART/libc 的指令刷屏
                                        if (mod !== null &&
                                            instruction.address.compare(mod.base) >= 0 &&
                                            instruction.address.compare(mod.base.add(mod.size)) < 0) {
                                            console.log("[Stalker] " +
                                                instruction.address.sub(mod.base) + " : " +
                                                instruction.mnemonic + " " + instruction.opStr);
                                        }
                                        iterator.keep();
                                        instruction = iterator.next();
                                    }
                                },
                            });
                        },
                        onLeave: function (retval) {
                            // 停止跟踪并冲刷剩余数据
                            Stalker.unfollow(this.tid);
                            Stalker.flush();
                            console.log("[JNI_OnLoad] <<< 执行结束，返回值: " + retval);
                        },
                    });
                    jniOnLoadHooked = true;
                    console.log("[*] 已 hook JNI_OnLoad: " + jniOnLoadAddr + " (Stalker 已就绪)");
                } else {
                    console.log("[!] 未找到 JNI_OnLoad 导出符号");
                }
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

Stalker 成功捕获到退出前的最后几条指令：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_KTNW8C8ET5P9UP6.webp)

#### 分析退出指令

关键指令序列：

```python
mov x0, #0       ; x0 = 0
mov sp, x0       ; sp = 0  (栈指针清零)
mov x30, x0      ; lr = 0  (返回地址清零)
mov x9, x11      ; x9 = 0x10dc (w11 低16位)
br x11           ; 跳转到 x11 = 0xb6a210dc
\```

这是**故意制造 SIGSEGV** 退出：将 `sp` 和 `lr` 清零后跳转到一个未映射地址，触发段错误杀死进程，而非调用 `exit`/`abort`。

计算跳转目标地址：`w11 = 0x10dc`，`movk w11, #0xb6a2, lsl #16` → `x11 = 0xb6a210dc`，但这是绝对地址。需要用 IDA 查看该位置对应的 SO 内偏移。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_JXNE2RS8F8TVZEV.webp)

得到偏移 `0x10dc`，使用 IDA 跳转查看：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_88ZFKV556KKRZKY.webp)

观察代码逻辑，确定是 **`sub_4B2E0` 返回 1 时退出程序**。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_E96RHPB4B4VSEHA.webp)

#### 分析与下一步

找到了导致退出的函数 `sub_4B2E0`（偏移 0x4B2E0）：当它返回 1 时触发退出路径。下一步直接 Hook 这个函数，将返回值替换为 0，即可绕过检测。

---

### 步骤六：过掉 0x4B2E0 — 修改返回值绕过检测

#### 前置知识：返回值替换

`Interceptor.attach` 的 `onLeave` 回调中，`retval.replace(0)` 可以修改函数返回值。这是最简单直接的绕过方式——让检测函数始终返回"未检测到"的值。

#### 向GLM-5.3-FLASH提出需求

>
> 在现有脚本的基础上创建新的脚本，将使用 Stalker 跟踪 JNI_OnLoad 执行过程替换为 hook 偏移量为 0x4B2E0 的目标函数，将返回值替换为 0，其他功能保留
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_6GUSXZ3M7JHDYPE.webp)

#### 生成代码

```javascript
/**
 * patch_dexhelper_0x4b2e0.js
 *
 * 功能一：Hook pthread_create
 *  - 当线程函数 (start_routine) 位于 libDexHelper.so 内时，
 *    打印日志（模块名、函数偏移、参数），并直接返回 0，
 *    模拟线程创建成功，但实际没有创建线程（阻止其执行）。
 *  - 其他模块创建的线程正常放行，调用原始 pthread_create。
 *
 * 功能二：Hook android_dlopen_ext
 *  - 监控所有 so 文件的加载，当 libDexHelper.so 被加载时打印提示；
 *  - 加载完成后，hook 模块内偏移 0x4B2E0 处的函数，
 *    打印调用日志，并将其返回值替换为 0。
 *
 * 使用方式：
 *   frida -U -f <包名> -l patch_dexhelper_func.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l patch_dexhelper_func.js
 */

const TARGET_MODULE = "libDexHelper.so";
const TARGET_FUNC_OFFSET = 0x4B2E0; // 目标函数在模块内的偏移

/**
 * Hook pthread_create，拦截目标模块创建的线程
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",
        "pointer",
        "pointer",
        "pointer",
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);

                console.log("==================================================");
                console.log("[拦截] 阻止 " + TARGET_MODULE + " 创建线程");
                console.log("  模块名      : " + mod.name);
                console.log("  模块基址    : " + mod.base);
                console.log("  函数地址    : " + startRoutine);
                console.log("  函数偏移    : " + offset);
                console.log("  参数 (arg)  : " + arg);
                console.log("==================================================");

                // 直接返回 0，假装创建成功，实际没有创建线程
                return 0;
            }

            // 其他模块：正常放行
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
}

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标模块加载完成后，在 onLeave 中 hook 偏移 0x4B2E0 处的函数，
 * 将其返回值替换为 0。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let targetFuncHooked = false; // 只挂钩一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            if (!this.isTarget) {
                return;
            }

            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            // hook 模块内偏移 0x4B2E0 处的函数，返回值替换为 0
            if (!targetFuncHooked && mod !== null) {
                const targetFuncAddr = mod.base.add(TARGET_FUNC_OFFSET);

                Interceptor.attach(targetFuncAddr, {
                    onEnter: function (args) {
                        console.log("--------------------------------------------------");
                        console.log("[Hook] 调用目标函数 " + TARGET_MODULE + "!0x" +
                            TARGET_FUNC_OFFSET.toString(16));
                        console.log("  地址     : " + targetFuncAddr);
                        console.log("  arg0     : " + args[0]);
                        console.log("  arg1     : " + args[1]);
                        console.log("  arg2     : " + args[2]);
                        console.log("  arg3     : " + args[3]);
                    },
                    onLeave: function (retval) {
                        console.log("[Hook] 目标函数返回，原始返回值: " + retval +
                            " -> 替换为 0");
                        retval.replace(0);
                        console.log("--------------------------------------------------");
                    },
                });

                targetFuncHooked = true;
                console.log("[*] 已 hook 目标函数: " + targetFuncAddr +
                    " (" + TARGET_MODULE + "!0x" + TARGET_FUNC_OFFSET.toString(16) + ")");
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

成功过掉检测，程序正常运行不再退出！

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_B4CK6DYRWYW2CNA.webp)

#### 分析与下一步

绕过成功！但此时只是"盲绕"——我们并不知道 `sub_4B2E0` 到底检测到了 Frida 的什么特征才返回 1。银行加固壳会随版本更新迭代检测逻辑，"盲绕"随时可能失效，且无法沉淀为可复用的对抗方案。因此需要进入**阶段2**：用 Stalker 深度逆向分析检测链路，找到具体是哪个函数、匹配到什么特征导致返回 1，实现精准绕过。

---

## 阶段2：找到 Frida 哪里被检测到

>
> 阶段1 已实现"盲绕"——程序不再退出。但银行加固壳的检测逻辑会随版本更新而变化，"盲绕"随时可能失效。阶段2 的目标是**逆向分析检测链路**，搞清楚加固壳到底扫描了 Frida 的什么特征、在哪条指令返回 1，从而实现**精准绕过**而非"碰运气"。这一阶段将更深度地运用 Stalker 追踪元凶线程与检测主函数的完整执行流，是整篇文章技术含量的核心所在。
>
>
>

### 步骤七：确定检测线程 — 排除法找到元凶线程

#### 前置知识：排除法定位

`libDexHelper.so` 创建了多个线程，通过逐个/分批阻止线程创建，观察程序是否退出，可以用排除法确定元凶线程。同时 Hook `abort`/`exit`/`kill` 等终止函数，程序被杀时打印调用者，辅助确认。

#### 已知线程偏移

通过之前patch_dexhelper_0x4b2e0.js返回的值可以得到 `libDexHelper.so` 创建了哪些线程：

```javascript
==================================================
[拦截] 阻止 libDexHelper.so 创建线程
  模块名      : libDexHelper.so
  模块基址    : 0x7b14044000
  函数地址    : 0x7b140929d8
  函数偏移    : 0x4e9d8
  参数 (arg)  : 0xb400007ba85cd180
==================================================
==================================================
[拦截] 阻止 libDexHelper.so 创建线程
  模块名      : libDexHelper.so
  模块基址    : 0x7b14044000
  函数地址    : 0x7b1408f614
  函数偏移    : 0x4b614
  参数 (arg)  : 0xb400007ba8409950
==================================================
==================================================
[拦截] 阻止 libDexHelper.so 创建线程
  模块名      : libDexHelper.so
  模块基址    : 0x7b14044000
  函数地址    : 0x7b140997c0
  函数偏移    : 0x557c0
  参数 (arg)  : 0xb400007b79172a40
==================================================
==================================================
[拦截] 阻止 libDexHelper.so 创建线程
  模块名      : libDexHelper.so
  模块基址    : 0x7b14044000
  函数地址    : 0x7b1409b668
  函数偏移    : 0x57668
  参数 (arg)  : 0x0
==================================================
==================================================
[拦截] 阻止 libDexHelper.so 创建线程
  模块名      : libDexHelper.so
  模块基址    : 0x7b14044000
  函数地址    : 0x7b1409ef74
  函数偏移    : 0x5af74
  参数 (arg)  : 0xb400007b131ff260
==================================================
\```

接下来分析哪个线程检测到 Frida。

#### patch_dexhelper_func.js

>
> 通过之前脚本执行结果判断，libDexHelper.so 创建了函数偏移为 0x4e9d8, 0x4b614, 0x557c0, 0x57668, 0x5af74 的几个线程。在现有脚本的基础上创建新的脚本，修改 hookPthreadCreate 函数，以协助我判断，哪个线程中止了程序。
>
>
>

#### GLM-5.3-FLASH 执行

GLM-5.3-FLASH 直接生成了脚本，还告诉了脚本的使用建议——通过修改 `ALLOW_OFFSETS` 逐批测试。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_JMUV6P69BVMU77M.webp)

#### 生成代码

```javascript
/**
 * find_killer_thread.js
 *
 * 基于原拦截脚本迭代，修改 hookPthreadCreate 用于定位
 * "哪个线程中止了程序"：
 *
 * 已知 libDexHelper.so 通过 pthread_create 创建了以下 5 个线程
 * （偏移来自之前脚本运行日志）：
 *   0x4e9d8 / 0x4b614 / 0x557c0 / 0x57668 / 0x5af74
 *
 * 定位方法（单变量对照实验）：
 *  - 默认拦截全部 libDexHelper.so 线程；
 *  - 每次实验在 ALLOW_OFFSETS 中只填一个偏移（放行该线程、拦截其余）；
 *  - 程序退出   -> 被放行的线程就是中止程序的线程；
 *  - 程序存活   -> 被放行的线程清白，换下一个继续测。
 *
 * 功能二：Hook android_dlopen_ext（保留）
 *  - 监控所有 so 文件的加载；目标 so 加载成功后 hook JNI_OnLoad
 *    查看执行开始/结束；hook 偏移 0x4B2E0 的函数把返回值替换为 0
 *    （可通过 ENABLE_OFFSET_PATCH 开关关闭，避免干扰定位实验）。
 *
 * 使用方式：
 *   frida -U -f <包名> -l find_killer_thread.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l find_killer_thread.js
 */

// 目标模块名：只要线程函数落在这个 SO 内，就处理
const TARGET_MODULE = "libDexHelper.so";

// 已知的目标 so 线程入口函数偏移（来自之前运行日志）
const THREAD_OFFSETS = [0x4e9d8, 0x4b614, 0x557c0, 0x57668, 0x5af74];

// 实验开关：本次要放行的线程偏移列表，其余 libDexHelper.so 线程全部拦截
// 每次实验只填一个，例如: [0x4b614]；空数组 = 全部拦截（对照基线）
const ALLOW_OFFSETS = [];

// 是否启用偏移 0x4B2E0 的返回值 patch；做线程定位实验时可改为 false 排除干扰
const ENABLE_OFFSET_PATCH = true;

// 目标函数偏移（patch 其返回值为 0）
const TARGET_OFFSET = 0x4B2E0;

/**
 * Hook pthread_create，按偏移拦截/放行目标模块创建的线程
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    // 保存原始 pthread_create，用于放行线程
    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",  // pthread_t*        线程句柄（出参）
        "pointer",  // pthread_attr_t*   线程属性，NULL 表示默认
        "pointer",  // void*(*)(void*)   线程入口函数 (start_routine)
        "pointer",  // void*             传给入口函数的参数 (arg)
    ]);

    // 偏移数值比较用：把两个 NativePointer/number 都转成统一小写十六进制字符串
    function toHex(v) {
        return v.toString(16).toLowerCase();
    }

    // 用 NativeCallback 构造替换函数，签名与 pthread_create 一致
    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            // 反查线程入口函数属于哪个模块
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);
                const offsetHex = toHex(offset);

                // 判断该偏移是否在本次实验的放行名单里
                const allowed = ALLOW_OFFSETS.some(function (o) {
                    return toHex(o) === offsetHex;
                });

                console.log("==================================================");
                if (allowed) {
                    console.log("[放行] 允许创建线程: " + TARGET_MODULE + "+" + offsetHex);
                    console.log("  模块基址    : " + mod.base);
                    console.log("  函数地址    : " + startRoutine);
                    console.log("  参数 (arg)  : " + arg);
                    console.log("  -> 观察程序是否因此退出");
                    console.log("==================================================");

                    // 实验组：放行该线程，调用原始 pthread_create 真实创建
                    return originalPthreadCreate(thread, attr, startRoutine, arg);
                }

                console.log("[拦截] 阻止创建线程: " + TARGET_MODULE + "+" + offsetHex);
                console.log("  模块基址    : " + mod.base);
                console.log("  函数地址    : " + startRoutine);
                console.log("  参数 (arg)  : " + arg);
                console.log("==================================================");

                // 直接返回 0，假装创建成功，实际没有创建线程
                return 0;
            }

            // 其他模块：正常放行，调用原始 pthread_create
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    // 用替换函数整体替换 pthread_create
    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
    console.log("[*] 已知线程偏移: " +
        THREAD_OFFSETS.map(function (o) { return "0x" + toHex(o); }).join(", "));
    console.log("[*] 本次放行: " +
        (ALLOW_OFFSETS.length
            ? ALLOW_OFFSETS.map(function (o) { return "0x" + toHex(o); }).join(", ")
            : "(无，全部拦截)"));
}

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标 so 加载完成后，在 onLeave 中实际挂钩其 JNI_OnLoad 和偏移函数。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let jniOnLoadHooked = false;   // JNI_OnLoad 只挂钩一次
    let targetFuncHooked = false;  // 偏移函数只挂钩一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            // 保存第一个参数：要加载的 so 路径
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();

            // 判断本次加载的是否为目标 so
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                // 其他 so：普通日志
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            // 只关心目标 so 的加载结果
            if (!this.isTarget) {
                return;
            }

            // android_dlopen_ext 失败时返回 NULL
            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            // 加载成功：打印模块信息
            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            if (mod !== null) {
                // 1) hook JNI_OnLoad，查看其执行的开始和结束
                if (!jniOnLoadHooked) {
                    // jint JNI_OnLoad(JavaVM* vm, void* reserved)
                    const jniOnLoadAddr = Module.findExportByName(TARGET_MODULE, "JNI_OnLoad");

                    if (jniOnLoadAddr !== null) {
                        Interceptor.attach(jniOnLoadAddr, {
                            onEnter: function (args) {
                                console.log("[JNI_OnLoad] >>> 开始执行");
                                console.log("  地址     : " + jniOnLoadAddr);
                                console.log("  偏移     : " + jniOnLoadAddr.sub(mod.base));
                                console.log("  JavaVM*  : " + args[0]);
                                console.log("  reserved : " + args[1]);
                            },
                            onLeave: function (retval) {
                                console.log("[JNI_OnLoad] <<< 执行结束，返回值: " + retval);
                            },
                        });
                        jniOnLoadHooked = true;
                        console.log("[*] 已 hook JNI_OnLoad: " + jniOnLoadAddr);
                    } else {
                        console.log("[!] 未找到 JNI_OnLoad 导出符号");
                    }
                }

                // 2) hook 偏移函数，把返回值替换为 0（可用 ENABLE_OFFSET_PATCH 关闭）
                if (ENABLE_OFFSET_PATCH && !targetFuncHooked) {
                    const targetFuncAddr = mod.base.add(TARGET_OFFSET);

                    Interceptor.attach(targetFuncAddr, {
                        onEnter: function (args) {
                            console.log("--------------------------------------------------");
                            console.log("[偏移函数] >>> 调用 (偏移 " + TARGET_OFFSET + ")");
                            console.log("  地址     : " + targetFuncAddr);
                            console.log("  线程 id  : " + Process.getCurrentThreadId());
                        },
                        onLeave: function (retval) {
                            console.log("[偏移函数] <<< 原始返回值: " + retval);

                            // 把返回值替换为 0，让该函数的检测结果失效
                            retval.replace(ptr(0));
                            console.log("[偏移函数] 返回值已替换为: " + ptr(0));
                            console.log("--------------------------------------------------");
                        },
                    });
                    targetFuncHooked = true;
                    console.log("[*] 已 hook 目标函数: " + targetFuncAddr +
                        " (基址 " + mod.base + " + 偏移 " + TARGET_OFFSET + ")");
                }
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

根据 GLM-5.3-FLASH 生成的脚本使用建议，修改 `ALLOW_OFFSETS` 的值为待测试线程，经过逐个排除测试，最终确定是 **`0x4b614` **线程终止了程序。

#### 分析与下一步

元凶线程确定为 `0x4b614`。下一步需要用 Stalker 追踪这个线程函数的执行过程，分析它是如何杀死程序的。

---

### 步骤八：Stalker 追踪 0x4b614 — 分析线程执行流程

#### 要求

>
> 帮我生成新的 js 文件，hook 偏移量为 0x4B2E0 的目标函数，将返回值替换为 0，并杀掉偏移量为 0x4e9d8, 0x557c0, 0x57668, 0x5af74 几个线程。并使用 Stalker 跟踪偏移量为 0x4b614 函数执行过程中的每条机器指令
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_5AESPAF2NHWAG9Z.webp)

#### 生成代码

```javascript
/**
 * trace_dexhelper_0x4b614.js
 *
 * 三合一脚本：
 *  功能一：杀线程 —— hook pthread_create，libDexHelper.so 创建的
 *          0x4e9d8 / 0x557c0 / 0x57668 / 0x5af74 四个线程，创建时
 *          直接返回 0（假装创建成功，实际线程不存在，等同杀掉）；
 *          元凶线程 0x4b614 不杀（放行），供 Stalker 跟踪；
 *          其他模块创建的线程正常放行。
 *  功能二：hook libDexHelper.so 内偏移 0x4B2E0 的目标函数，
 *          在 onLeave 把返回值替换为 0（过检测）。
 *  功能三：使用 Stalker 跟踪偏移 0x4b614 的线程函数，
 *          实时捕获并输出其执行过程中的每条机器指令，
 *          分析该线程是如何中止程序的。
 *
 * 性能说明：
 *  - Stalker 逐条 console.log 会因 IPC 开销过大严重拖慢甚至卡死进程；
 *  - 因此内置日志缓冲：指令先写入内存数组，每 30 毫秒批量输出一次；
 *  - 跟踪结束时立即冲刷缓冲，保证尾部指令完整。
 *
 * 使用方式：
 *   frida -U -f <包名> -l trace_dexhelper_0x4b614.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l trace_dexhelper_0x4b614.js
 */

const TARGET_MODULE = "libDexHelper.so";
const PATCH_OFFSET = 0x4B2E0;   // hook 后把返回值替换为 0 的目标函数偏移
const TRACE_OFFSET = 0x4b614;   // 用 Stalker 跟踪的线程函数偏移

// 要杀掉的线程函数偏移（创建时返回 0，线程实际不创建）
const KILL_THREAD_OFFSETS = [0x4e9d8, 0x557c0, 0x57668, 0x5af74];

/**
 * Hook pthread_create：杀掉指定偏移的线程，其余放行
 */
function hookPthreadCreate() {
    // int pthread_create(pthread_t*, const pthread_attr_t*, void*(*)(void*), void*)
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");

    // 保存原始 pthread_create，用于放行不杀的线程
    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer",  // pthread_t*        线程句柄（出参）
        "pointer",  // pthread_attr_t*   线程属性
        "pointer",  // void*(*)(void*)   线程入口函数 (start_routine)
        "pointer",  // void*             传给入口函数的参数 (arg)
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            // 反查线程入口函数属于哪个模块
            const mod = Process.findModuleByAddress(startRoutine);

            if (mod !== null && mod.name === TARGET_MODULE) {
                // 换算线程函数在模块内的偏移，转成数值便于比较
                const offset = startRoutine.sub(mod.base).toUInt32();
                const killed = KILL_THREAD_OFFSETS.indexOf(offset) !== -1;

                console.log("==================================================");
                console.log("[线程] " + TARGET_MODULE + " 创建线程 " +
                    "(偏移 0x" + offset.toString(16) + ")");
                console.log("  函数地址    : " + startRoutine);
                console.log("  参数 (arg)  : " + arg);
                console.log("  处置        : " + (killed ? "杀掉 (返回 0)" : "放行"));
                console.log("==================================================");

                if (killed) {
                    // 直接返回 0，假装创建成功，实际没有创建线程
                    return 0;
                }
            }

            // 其他情况：正常放行
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    // 用替换函数整体替换 pthread_create
    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 已 hook pthread_create，目标模块: " + TARGET_MODULE);
    console.log("[*] 杀掉的线程偏移: [" +
        KILL_THREAD_OFFSETS.map(function (o) { return "0x" + o.toString(16); }).join(", ") +
        "]");
}

// ---------------- 日志缓冲：30 毫秒批量输出 ----------------
let logBuffer = [];
let flushTimer = null;

// 写入缓冲，首次写入时启动 30ms 定时器批量输出
function bufferLog(line) {
    logBuffer.push(line);
    if (flushTimer === null) {
        flushTimer = setTimeout(function () {
            flushTimer = null;
            if (logBuffer.length > 0) {
                console.log(logBuffer.join("\n"));
                logBuffer = [];
            }
        }, 30);
    }
}

// 立即冲刷缓冲（跟踪结束时调用，避免尾部指令滞留）
function flushLogNow() {
    if (flushTimer !== null) {
        clearTimeout(flushTimer);
        flushTimer = null;
    }
    if (logBuffer.length > 0) {
        console.log(logBuffer.join("\n"));
        logBuffer = [];
    }
}

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标 so 加载完成后在 onLeave 中安装两个 hook：
 *  1) patch 偏移 0x4B2E0 函数的返回值；
 *  2) 对偏移 0x4b614 函数开启 Stalker 指令级跟踪。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    // Android 系统加载 so 走的是 android_dlopen_ext（比 dlopen 多一个 extinfo 参数）
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let patchHooked = false;  // 0x4B2E0 patch 只挂一次
    let traceHooked = false;  // 0x4b614 跟踪只挂一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            // 保存第一个参数：要加载的 so 路径
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();

            // 判断本次加载的是否为目标 so
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                // 其他 so：普通日志
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            // 只关心目标 so 的加载结果
            if (!this.isTarget) {
                return;
            }

            // android_dlopen_ext 失败时返回 NULL
            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            // 加载成功：打印模块信息
            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            if (mod !== null) {
                // ---------- 1) hook 偏移 0x4B2E0，返回值替换为 0 ----------
                if (!patchHooked) {
                    // 基址 + 偏移 = 目标函数在内存中的实际地址
                    const patchAddr = mod.base.add(PATCH_OFFSET);

                    Interceptor.attach(patchAddr, {
                        onEnter: function (args) {
                            console.log("--------------------------------------------------");
                            console.log("[Patch] >>> 调用目标函数 (偏移 0x" +
                                PATCH_OFFSET.toString(16) + ")");
                            console.log("  地址     : " + patchAddr);
                            console.log("  线程 id  : " + Process.getCurrentThreadId());
                        },
                        onLeave: function (retval) {
                            console.log("[Patch] <<< 原始返回值: " + retval);

                            // 把返回值替换为 0，让该函数的检测结果失效
                            retval.replace(ptr(0));
                            console.log("[Patch] 返回值已替换为: " + ptr(0));
                            console.log("--------------------------------------------------");
                        },
                    });
                    patchHooked = true;
                    console.log("[*] 已 hook 目标函数: " + patchAddr +
                        " (基址 " + mod.base + " + 偏移 0x" +
                        PATCH_OFFSET.toString(16) + ")，返回值将替换为 0");
                }

                // ---------- 2) Stalker 跟踪偏移 0x4b614 的线程函数 ----------
                if (!traceHooked) {
                    const traceAddr = mod.base.add(TRACE_OFFSET);

                    Interceptor.attach(traceAddr, {
                        onEnter: function (args) {
                            console.log("[Stalker] >>> 开始跟踪 " + TARGET_MODULE +
                                "+0x" + TRACE_OFFSET.toString(16) +
                                " (地址: " + traceAddr + ", 线程 id: " +
                                Process.getCurrentThreadId() + ")");
                            console.log("  参数 (arg): " + args[0]);

                            // 记录本线程 id，结束时按它停止跟踪
                            this.tid = Process.getCurrentThreadId();

                            // 模块内存范围，用于过滤：只输出目标 so 内的指令
                            const base = mod.base;
                            const end = mod.base.add(mod.size);

                            // 跟踪当前线程，实时捕获每条机器指令
                            Stalker.follow(this.tid, {
                                // transform：以基本块为单位逐条检查指令，决定保留或改写
                                transform: function (iterator) {
                                    let instruction = iterator.next();
                                    while (instruction !== null) {
                                        // 只输出目标模块内的指令，避免被 ART/libc 的指令刷屏
                                        const addr = instruction.address;
                                        if (addr.compare(base) >= 0 && addr.compare(end) < 0) {
                                            bufferLog("[Stalker] " +
                                                addr.sub(base) + " : " +
                                                instruction.mnemonic + " " + instruction.opStr);
                                        }
                                        // keep() 保留原指令，让代码继续原样执行
                                        iterator.keep();
                                        instruction = iterator.next();
                                    }
                                },
                            });
                        },
                        onLeave: function (retval) {
                            // 停止跟踪，冲刷 Stalker 数据并输出剩余日志
                            Stalker.unfollow(this.tid);
                            Stalker.flush();
                            flushLogNow();
                            console.log("[Stalker] <<< 0x" +
                                TRACE_OFFSET.toString(16) +
                                " 执行结束，返回值: " + retval);
                        },
                    });
                    traceHooked = true;
                    console.log("[*] 已开启 Stalker 跟踪: " + traceAddr +
                        " (基址 " + mod.base + " + 偏移 0x" +
                        TRACE_OFFSET.toString(16) + ")");
                }
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

#### 结果

```powershell
[Stalker] 0x2ddd4 : b.eq #0x7b15abbfa4
[Stalker] 0x2dfa4 : mov w10, w1
[Stalker] 0x2dfa8 : and w8, w2, w1
[Stalker] 0x2dfac : and x12, x8, #0xfffffffc
[Stalker] 0x2dfb0 : and x8, x10, #0x1f
[Stalker] 0x2dfb4 : adds x11, x8, x2
[Stalker] 0x2dfb8 : mov x0, #0
[Stalker] 0x2dfbc : mov sp, x0
[Stalker] 0x2dfc0 : mov x30, x0
[Stalker] 0x2dfc4 : mov x8, x1
[Stalker] 0x2dfc8 : mov x9, x12
[Stalker] 0x2dfcc : br x12
\```

#### 分析与下一步

找到了线程退出的最后指令块在偏移 `0x2dfa4` 附近，同样是 `mov sp, #0; mov lr, #0; br x12` 的 SIGSEGV 退出模式。需要分析 `0x2dfa4` 这个函数的参数来计算跳转地址，逐层上找真正的检测源头。

---

### 步骤九：分析 0x2DFA4 — 计算跳转地址逐层上找

#### 分析思路

分析最后一个代码块 `0x2dfa4`，发现它有 3 个参数。通过 Hook 打印参数值，可以计算出跳转目标地址，再用 IDA 查看目标位置。

#### 要求

>
> 帮我生成新的 js 文件，hook 偏移量为 0x4B2E0 的目标函数，将返回值替换为 0，并打印 sub_2DFA4 的参数 a1, a2, a3
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_76475U9H5Z6BDST.webp)

#### 生成代码

```javascript
/**
 * patch_and_log_sub2DFA4.js
 *
 * 功能一：hook libDexHelper.so 内偏移 0x4B2E0 处的函数，
 *         打印调用日志，并将返回值替换为 0。
 *
 * 功能二：hook libDexHelper.so 内偏移 0x2DFA4 处的函数 (sub_2DFA4)，
 *         打印其参数 a1, a2, a3。
 *
 * 两个 hook 都在 android_dlopen_ext 监控到 libDexHelper.so 加载后安装。
 *
 * 使用方式：
 *   frida -U -f <包名> -l patch_and_log_sub2DFA4.js
 * 或者附加到已运行的进程：
 *   frida -U -n <进程名> -l patch_and_log_sub2DFA4.js
 */

const TARGET_MODULE = "libDexHelper.so";
const PATCH_FUNC_OFFSET = 0x4B2E0;  // 要 patch 返回值的函数偏移
const LOG_FUNC_OFFSET = 0x2DFA4;    // sub_2DFA4，要打印参数的函数偏移

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标模块加载完成后安装两个 hook。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let hooksInstalled = false; // 只安装一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            if (!this.isTarget) {
                return;
            }

            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            if (!hooksInstalled && mod !== null) {
                hookPatchFunc(mod);
                hookLogFunc(mod);
                hooksInstalled = true;
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

/**
 * hook 偏移 0x4B2E0 处的函数，返回值替换为 0
 */
function hookPatchFunc(mod) {
    const patchFuncAddr = mod.base.add(PATCH_FUNC_OFFSET);

    Interceptor.attach(patchFuncAddr, {
        onEnter: function (args) {
            console.log("--------------------------------------------------");
            console.log("[Hook] 调用目标函数 " + TARGET_MODULE + "!0x" +
                PATCH_FUNC_OFFSET.toString(16));
            console.log("  地址     : " + patchFuncAddr);
            console.log("  arg0     : " + args[0]);
            console.log("  arg1     : " + args[1]);
        },
        onLeave: function (retval) {
            console.log("[Hook] 目标函数返回，原始返回值: " + retval +
                " -> 替换为 0");
            retval.replace(0);
            console.log("--------------------------------------------------");
        },
    });

    console.log("[*] 已 hook patch 函数: " + patchFuncAddr +
        " (" + TARGET_MODULE + "!0x" + PATCH_FUNC_OFFSET.toString(16) + ")");
}

/**
 * hook sub_2DFA4 (偏移 0x2DFA4)，打印参数 a1, a2, a3
 */
function hookLogFunc(mod) {
    const logFuncAddr = mod.base.add(LOG_FUNC_OFFSET);

    Interceptor.attach(logFuncAddr, {
        onEnter: function (args) {
            console.log("--------------------------------------------------");
            console.log("[sub_2DFA4] 调用，参数:");
            console.log("  a1       : " + args[0]);
            console.log("  a2       : " + args[1]);
            console.log("  a3       : " + args[2]);
            console.log("--------------------------------------------------");
        },
    });

    console.log("[*] 已 hook sub_2DFA4: " + logFuncAddr +
        " (" + TARGET_MODULE + "!0x" + LOG_FUNC_OFFSET.toString(16) + ")");
}

hookAndroidDlopenExt();
\```

#### 结果

```python
==================================================
[sub_2DFA4] >>> 调用 (偏移 0x2dfa4)
  地址     : 0x7bba4d5fa4
  线程 id  : 27242
  a1 (x0)  : 0x100  (十进制 256)
  a2 (x1)  : 0xb6a2897e  (十进制 3064105342)
  a3 (x2)  : 0xfff  (十进制 4095)
==================================================
\```

计算 `sub_2DFA4` 的值得到下一步跳转地址：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_HTKKGVNSKQH4C5N.webp)

跳转到 `0x97c`，使用 IDA 跳转查看，发现该位置直接跳转退出——这个函数就是用来退出的，没有分析意义。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_59SQWPX5VXKGCS9.webp)

#### 逐层上找

分析 `sub_2DFA4` 上面一个函数 `0x2DDA0`，经分析也是退出用的：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_XSD4VE97XYYWNEX.webp)

继续往上找，来到 `0x4bbd4`，使用 IDA 跳转继续分析函数：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_SMV6XXKRP6AYQGF.webp)

#### 分析与下一步

发现关键逻辑：**`sub_50450` 返回 1 时，会跳往退出函数导致程序退出**。让 `sub_50450` 不等于 1，程序即可正常运行。下一步需要分析 `sub_50450` 内部，找到是哪个位置使它返回 1。

---

### 步骤十：Stalker 追踪 sub_50450 — 定位返回 1 的位置

#### 要求

>
> 帮我创建新的脚本，hook 偏移量为 0x4B2E0 的目标函数，将返回值替换为 0，并使用 Stalker 跟踪偏移量为 0x50450 函数执行过程中的每条机器指令
>
>
>

#### GLM-5.3-FLASH 执行

 ![图片描述](https://bbs.kanxue.com/upload/attach/202609/865139_6KVBRN2XJWM9K4X.webp)

#### 生成代码

```javascript
/**
 * trace_dexhelper_0x50450.js
 *
 * 功能一：hook libDexHelper.so 内偏移 0x4B2E0 处的函数，
 *         打印调用日志，并将返回值替换为 0。
 *
 * 功能二：hook libDexHelper.so 内偏移 0x50450 处的函数，
 *         使用 Stalker 跟踪其执行过程中的每条机器指令。
 *         不去重，保留全部指令的执行顺序（循环的每一轮都会输出）。
 *         输出采用 30ms 定时批量打印，降低 IPC 开销。
 *
 * 注意：不去重意味着日志量 = 实际执行的指令条数，
 * 长期运行的循环函数会让缓冲无限增长，可能撑爆内存。
 * 如需要可加大 MAX_BUFFER_LINES 启用自动熔断（默认关闭）。
 *
 * 使用方式：
 *   frida -U -f <包名> -l trace_dexhelper_0x50450_full.js
 */

const TARGET_MODULE = "libDexHelper.so";
const PATCH_FUNC_OFFSET = 0x4B2E0;  // 要 patch 返回值的函数偏移
const TRACE_FUNC_OFFSET = 0x50450;  // 要 Stalker 跟踪的函数偏移

const FLUSH_INTERVAL_MS = 30;       // 每隔多少毫秒批量输出一次日志
const MAX_BUFFER_LINES = 0;         // 缓冲行数上限，0 = 不限制；
                                    // 超过后自动停止跟踪，防止内存撑爆

/**
 * Hook android_dlopen_ext，监控 so 加载；
 * 目标模块加载完成后安装两个 hook。
 */
function hookAndroidDlopenExt() {
    // void* android_dlopen_ext(const char* filename, int flags, const android_dlextinfo* extinfo)
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");

    let hooksInstalled = false; // 只安装一次

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;

            if (this.isTarget) {
                console.log("**************************************************");
                console.log("[提示] 开始加载 " + TARGET_MODULE);
                console.log("  路径     : " + this.filename);
            } else {
                console.log("[dlopen] 加载: " + this.filename);
            }
        },
        onLeave: function (retval) {
            if (!this.isTarget) {
                return;
            }

            if (retval.isNull()) {
                console.log("[提示] " + TARGET_MODULE + " 加载失败!");
                console.log("**************************************************");
                return;
            }

            const mod = Process.findModuleByName(TARGET_MODULE);
            console.log("[提示] " + TARGET_MODULE + " 已加载!");
            if (mod !== null) {
                console.log("  基址     : " + mod.base);
                console.log("  大小     : " + mod.size);
            }

            if (!hooksInstalled && mod !== null) {
                hookPatchFunc(mod);
                hookTraceFunc(mod);
                hooksInstalled = true;
            }

            console.log("**************************************************");
        },
    });

    console.log("[*] 已 hook android_dlopen_ext，监控 so 加载");
}

/**
 * hook 偏移 0x4B2E0 处的函数，返回值替换为 0
 */
function hookPatchFunc(mod) {
    const patchFuncAddr = mod.base.add(PATCH_FUNC_OFFSET);

    Interceptor.attach(patchFuncAddr, {
        onEnter: function (args) {
            console.log("[Hook] 调用 " + TARGET_MODULE + "!0x" +
                PATCH_FUNC_OFFSET.toString(16) +
                " arg0=" + args[0] + " arg1=" + args[1]);
        },
        onLeave: function (retval) {
            console.log("[Hook] 0x" + PATCH_FUNC_OFFSET.toString(16) +
                " 原始返回值: " + retval + " -> 替换为 0");
            retval.replace(0);
        },
    });

    console.log("[*] 已 hook patch 函数: " + patchFuncAddr +
        " (" + TARGET_MODULE + "!0x" + PATCH_FUNC_OFFSET.toString(16) + ")");
}

/**
 * hook 偏移 0x50450 处的函数，用 Stalker 跟踪其执行指令
 * （不去重，保留完整执行顺序）
 */
function hookTraceFunc(mod) {
    const traceFuncAddr = mod.base.add(TRACE_FUNC_OFFSET);
    const modEnd = mod.base.add(mod.size);

    let buffer = [];          // 待输出的日志缓冲
    let totalCount = 0;       // 已记录的指令总数
    let stopped = false;      // 是否已熔断
    let traceTid = -1;
    let flushTimer = null;    // 定时输出定时器

    function flushBuffer() {
        if (buffer.length > 0) {
            console.log(buffer.join("\n")); // 一次 IPC 输出一批
            buffer = [];
        }
    }

    Interceptor.attach(traceFuncAddr, {
        onEnter: function (args) {
            console.log("==================================================");
            console.log("[Trace] 进入函数 " + TARGET_MODULE + "!0x" +
                TRACE_FUNC_OFFSET.toString(16));
            console.log("  地址     : " + traceFuncAddr);
            console.log("  arg0     : " + args[0]);
            console.log("  arg1     : " + args[1]);

            // 启动定时器：每 30 毫秒批量输出一次缓冲的指令日志
            if (flushTimer === null) {
                flushTimer = setInterval(flushBuffer, FLUSH_INTERVAL_MS);
            }

            traceTid = Process.getCurrentThreadId();
            Stalker.follow(traceTid, {
                transform: function (iterator) {
                    let instruction = iterator.next();
                    while (instruction !== null) {
                        const addr = instruction.address;

                        // 只处理目标模块内的指令
                        if (addr.compare(mod.base) >= 0 && addr.compare(modEnd) < 0) {
                            totalCount++;

                            // 不去重：每条执行的指令都按顺序记录
                            buffer.push("[Stalker] #" + totalCount + " " +
                                addr.sub(mod.base) + " : " +
                                instruction.mnemonic + " " + instruction.opStr);

                            // 可选熔断：缓冲超过上限后停止跟踪
                            if (MAX_BUFFER_LINES > 0 &&
                                buffer.length >= MAX_BUFFER_LINES && !stopped) {
                                stopped = true;
                                flushBuffer();
                                console.log("[Trace] 缓冲已达上限 " +
                                    MAX_BUFFER_LINES + " 行，停止跟踪");
                                Stalker.unfollow(traceTid);
                            }
                        }

                        iterator.keep();
                        instruction = iterator.next();
                    }
                },
            });
        },
        onLeave: function (retval) {
            // 停止定时器和跟踪，冲刷剩余数据
            if (flushTimer !== null) {
                clearInterval(flushTimer);
                flushTimer = null;
            }
            if (!stopped) {
                Stalker.unfollow(traceTid);
            }
            Stalker.flush();
            flushBuffer();
            console.log("[Trace] 离开函数 " + TARGET_MODULE + "!0x" +
                TRACE_FUNC_OFFSET.toString(16) + "，返回值: " + retval +
                "，共执行模块内指令 " + totalCount + " 条");
            console.log("==================================================");
        },
    });

    console.log("[*] 已 hook trace 函数: " + traceFuncAddr +
        " (" + TARGET_MODULE + "!0x" + TRACE_FUNC_OFFSET.toString(16) + ") (Stalker 完整顺序版)");
}

hookAndroidDlopenExt();
\```

#### 结果

```javascript
······
[Trace] 进入函数 libDexHelper.so!0x50450
  地址     : 0x730312d450
  arg0     : 0x0
  arg1     : 0x7302edc960
······
[Trace] 进入函数 libDexHelper.so!0x50450
  地址     : 0x730312d450
  arg0     : 0x73031cf9b0
  arg1     : 0x7307715ba0
······
[Trace] 离开函数 libDexHelper.so!0x50450，返回值: 0x1，共执行模块内指令 1449 条
=================================================
Process terminated
\```

#### 分析与下一步

分析返回值发现：`sub_50450` 被调用了**两次**，第一次正常返回，第二次返回 1 导致程序退出。结合 IDA 和打印的汇编代码，需要进一步分析程序到底是在 `sub_50450` 内部的哪个位置检测到 Frida 并返回 1。

---

### 步骤十一：找到具体匹配特征 — 确定 Frida 触发检测的特征

#### 分析思路

通过前述步骤已知 `sub_50450` 第二次调用返回 1 导致退出。现在需要深入 `sub_50450` 内部，找到具体是哪个子函数匹配到了什么特征。

结合 IDA 反编译分析 `sub_50450` 的内部逻辑，发现它是一个**内存映射扫描函数**，核心流程如下：

```python
sub_50450(a1, a2, a3, a4回调, a5回调):
    1. 打开 /proc/self/maps
    2. 逐行读取 maps
    3. 对每行调用 a4 回调 (sub_50CF8)：
       - 返回 1 = 已知安全路径，跳过该行
       - 返回 0 = 未知/可疑，继续检查
    4. 对可疑行调用 sub_4FD98 白名单过滤：
       - 返回 1 = 白名单命中，跳过
       - 返回 0 = 未命中，继续检查
    5. 检查路径是否含 "memfd:" (倒序匹配 ":dfmem/")
    6. 通过 process_vm_readv 读取映射内容
    7. 检查前4字节是否为 ELF 魔数 \x7fELF
    8. 调用 sub_4B2E0 读取 /proc/self/mem 验证
    9. 任一检查命中 => 返回 1
\```

#### 关键发现：三个 Frida 特征

通过动态追踪确认，`sub_50450` 检测到以下 3 个 Frida 特征中的任意一个即返回 1：

| # | 特征 | 来源 | 检测位置 |
|-|-|-|-|
| 1 | 路径含 `memfd:` — `/memfd:xjd-cache (deleted)` | Frida 16.x agent 使用 `memfd_create` 创建匿名内存映射 | `sub_50450` 第二部分，用倒序字符串 `:dfmem/` 匹配 |
| 2 | 映射内容为 ELF — `\x7fELF` 魔数 | Frida agent 本身是 ELF SO 文件 | `process_vm_readv` 读取映射内容后检查前4字节 |
| 3 | `/proc/self/mem` 读取失败 — `sub_4B2E0` 返回 -1 | Frida 修改了内存映射导致地址未映射 | `sub_4B2E0` 通过 `pread64` 读取 `/proc/self/mem` |

#### 触发检测的具体行

在 `/proc/self/maps` 中，Frida 16.x 会创建如下映射：

```python
b6a2897e000-b6a2897f000 r-xp 00000000 00:00 0  /memfd:xjd-cache (deleted)
\```

这一行**不含白名单路径**（`libDexHelper.so`、`libSdkHelper.so`、`base.apk`、`libdatajar.so`），也**不是已知安全模式**（`[anon:dalvik-*]`、`*.vdex`、`*.oat` 等），因此：

1. `sub_50CF8`（a4 回调）返回 0 — 不是已知安全路径
2. `sub_4FD98` 白名单返回 0 — 不在白名单中
3. 路径含 `memfd:` — **第一个特征命中**
4. `process_vm_readv` 读取内容为 `\x7fELF` — **第二个特征命中**
5. `sub_4B2E0` 读取 `/proc/self/mem` 返回 -1 — **第三个特征命中**

任一命中即导致 `sub_50450` 返回 1，最终触发退出路径。

#### 最终绕过方案

在偏移 `0x506f4` 处（`sscanf` 解析后、`sub_4FD98` 调用前），将含 `memfd:` 的路径替换为 `/libDexHelper.so`，使 `sub_4FD98` 白名单命中返回 1，跳过该行所有后续检测。三个 Frida 特征全部被绕过。

```python
原始 maps 行: /memfd:xjd-cache (deleted)
         ↓ 替换 @0x506f4
修改后: /libDexHelper.so
         ↓
sub_4FD98 白名单命中 => 返回 1 => 跳过该行
\```

#### 绕过代码

##### 精简版：maps 路径替换 + sub_4B2E0 兜底

核心思路：在 `0x506f4` 处 Hook，将含 `memfd:` 的路径替换为白名单路径 `/libDexHelper.so`；同时 Hook `sub_4B2E0` 兜底 JNI_OnLoad 期间尚未安装 Hook 时已执行的检测。

```javascript
/**
 * bypass_memfd_only.js
 *
 * 精准绕过 libDexHelper.so 的 Frida 检测：
 *   层1: Hook pthread_create，拦截 libDexHelper.so 创建的所有线程
 *   层2: Hook 偏移 0x506f4，将 /memfd: 路径替换为 /libDexHelper.so（白名单命中）
 *   层3: Hook 偏移 0x4B2E0，返回值 -1→0（兜底 JNI_OnLoad 期间已执行的检测）
 *
 * 使用方式：
 *   frida -H 127.0.0.1:14725 -f com.tzb.mobilehub -l bypass_memfd_only.js
 */

const TARGET_MODULE = "libDexHelper.so";
const MAPS_HOOK_OFFSET = 0x506f4;
const MEM_READ_OFFSET  = 0x4B2E0;
const WHITELIST_PATH   = "/libDexHelper.so";

/**
 * 层1: Hook pthread_create，阻止目标模块创建线程
 */
function hookPthreadCreate() {
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");
    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer", "pointer", "pointer", "pointer"
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            const mod = Process.findModuleByAddress(startRoutine);
            if (mod !== null && mod.name === TARGET_MODULE) {
                const offset = startRoutine.sub(mod.base);
                console.log("[拦截] 阻止 " + TARGET_MODULE + " 线程 偏移=" + offset);
                return 0;
            }
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 层1: 已 hook pthread_create");
}

/**
 * 层2: Hook 0x506f4，将 /memfd: 路径替换为白名单路径
 *
 * 原理：sub_50450 用 sscanf 解析 /proc/self/maps 每行后，
 * 在 0x506f4 处将解析出的路径指针存入 [sp+0x1E0]，
 * 然后调用 sub_4FD98 白名单过滤。
 * 我们在 0x506f4 的 onEnter 中检查该路径是否含 "memfd:"，
 * 若是则将 [sp+0x1E0] 指向的白名单路径字符串覆盖为 "/libDexHelper.so"，
 * 使 sub_4FD98 返回 1（白名单命中），跳过该行所有后续检测。
 */
function hookMapsFilter(mod) {
    const hookAddr = mod.base.add(MAPS_HOOK_OFFSET);
    const whitelistBuf = Memory.allocUtf8String(WHITELIST_PATH);

    Interceptor.attach(hookAddr, {
        onEnter: function (args) {
            // [sp+0x1E0] 存放 sscanf 解析出的路径指针
            var pathPtr = this.context.sp.add(0x1e0).readPointer();
            if (pathPtr.isNull()) return;

            var path = pathPtr.readCString();
            if (path !== null && path.indexOf("memfd:") !== -1) {
                console.log("[绕过] 替换 maps 路径: " + path + " -> " + WHITELIST_PATH);
                // 将路径缓冲区内容覆盖为白名单路径
                pathPtr.writeUtf8String(WHITELIST_PATH);
            }
        }
    });

    console.log("[*] 层2: 已 hook 0x" + MAPS_HOOK_OFFSET.toString(16) + " (maps 路径替换)");
}

/**
 * 层3: Hook sub_4B2E0，返回值 -1→0
 *
 * 兜底作用：JNI_OnLoad 中 sub_50450 第1次调用发生在
 * dlopen 的 onLeave 触发之前，此时 0x506f4 的 Hook 尚未安装。
 * sub_4B2E0 返回 -1 表示检测到 Frida，替换为 0 可绕过。
 */
function hookMemRead(mod) {
    const memReadAddr = mod.base.add(MEM_READ_OFFSET);

    Interceptor.attach(memReadAddr, {
        onEnter: function (args) {
            console.log("[Hook] sub_4B2E0 调用 arg0=" + args[0] + " arg1=" + args[1]);
        },
        onLeave: function (retval) {
            if (retval.toInt32() === -1) {
                console.log("[绕过] sub_4B2E0 返回 -1 -> 替换为 0");
                retval.replace(0);
            }
        }
    });

    console.log("[*] 层3: 已 hook 0x" + MEM_READ_OFFSET.toString(16) + " (sub_4B2E0 返回值替换)");
}

/**
 * Hook android_dlopen_ext，目标模块加载后安装层2、层3
 */
function hookAndroidDlopenExt() {
    const dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");
    let hooksInstalled = false;

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;
        },
        onLeave: function (retval) {
            if (!this.isTarget || retval.isNull()) return;

            var mod = Process.findModuleByName(TARGET_MODULE);
            if (!hooksInstalled && mod !== null) {
                hookMapsFilter(mod);
                hookMemRead(mod);
                hooksInstalled = true;
                console.log("[*] 所有 Hook 已安装，绕过就绪");
            }
        }
    });

    console.log("[*] 已 hook android_dlopen_ext");
}

hookPthreadCreate();
hookAndroidDlopenExt();
\```

##### 完整版：6 层防御

在精简版基础上增加防御纵深，Hook 更多检测子函数和 Frida 端口检测：

```javascript
/**
 * bypass_frida_mem.js
 *
 * 6 层防御完整版，绕过 libDexHelper.so 的全部 Frida 检测：
 *   层1: Hook pthread_create — 拦截所有 libDexHelper.so 线程
 *   层2: Hook 0x506f4 — maps 路径替换 /memfd: → /libDexHelper.so
 *   层3: Hook sub_4B2E0 — 返回值 -1→0（/proc/self/mem 读取兜底）
 *   层4: Hook sub_50CF8 — 返回值 1→0（已知安全模式检查，防御纵深）
 *   层5: Hook sub_51204 — 返回值 1→0（防御纵深）
 *   层6: Hook connect — 拦截 127.0.0.1 端口检测
 *
 * 使用方式：
 *   frida -H 127.0.0.1:14725 -f com.tzb.mobilehub -l bypass_frida_mem.js
 */

const TARGET_MODULE = "libDexHelper.so";

/**
 * 层1: Hook pthread_create，拦截目标模块创建的所有线程
 */
function hookPthreadCreate() {
    const pthreadCreateAddr = Module.getExportByName("libc.so", "pthread_create");
    const originalPthreadCreate = new NativeFunction(pthreadCreateAddr, "int", [
        "pointer", "pointer", "pointer", "pointer"
    ]);

    const fakePthreadCreate = new NativeCallback(
        function (thread, attr, startRoutine, arg) {
            var mod = Process.findModuleByAddress(startRoutine);
            if (mod !== null && mod.name === TARGET_MODULE) {
                var offset = startRoutine.sub(mod.base);
                console.log("[层1] 阻止 " + TARGET_MODULE + " 线程 偏移=" + offset);
                return 0;
            }
            return originalPthreadCreate(thread, attr, startRoutine, arg);
        },
        "int",
        ["pointer", "pointer", "pointer", "pointer"]
    );

    Interceptor.replace(pthreadCreateAddr, fakePthreadCreate);
    console.log("[*] 层1: 已 hook pthread_create");
}

/**
 * 层2: Hook 0x506f4，将 /memfd: 路径替换为白名单路径
 */
function hookMapsFilter(mod) {
    var hookAddr = mod.base.add(0x506f4);
    var whitelistPath = "/libDexHelper.so";

    Interceptor.attach(hookAddr, {
        onEnter: function (args) {
            var pathPtr = this.context.sp.add(0x1e0).readPointer();
            if (pathPtr.isNull()) return;

            var path = pathPtr.readCString();
            if (path !== null && path.indexOf("memfd:") !== -1) {
                console.log("[层2] 替换 maps 路径: " + path + " -> " + whitelistPath);
                pathPtr.writeUtf8String(whitelistPath);
            }
        }
    });

    console.log("[*] 层2: 已 hook 0x506f4 (maps 路径替换)");
}

/**
 * 层3: Hook sub_4B2E0，返回值 -1→0
 */
function hookSub4B2E0(mod) {
    var addr = mod.base.add(0x4B2E0);

    Interceptor.attach(addr, {
        onLeave: function (retval) {
            if (retval.toInt32() === -1) {
                console.log("[层3] sub_4B2E0 返回 -1 -> 替换为 0");
                retval.replace(0);
            }
        }
    });

    console.log("[*] 层3: 已 hook sub_4B2E0");
}

/**
 * 层4: Hook sub_50CF8，返回值 1→0（防御纵深）
 *
 * sub_50CF8 是已知安全模式检查回调：
 *   返回 1 = 已知安全路径（如 [anon:dalvik-*], *.vdex），跳过该行
 *   返回 0 = 未知/可疑，继续检查
 * 将返回值从 1 改为 0，使所有行都进入后续检查，
 * 配合层2的路径替换，确保 memfd 行被白名单拦截。
 */
function hookSub50CF8(mod) {
    var addr = mod.base.add(0x50CF8);

    Interceptor.attach(addr, {
        onLeave: function (retval) {
            if (retval.toInt32() === 1) {
                console.log("[层4] sub_50CF8 返回 1 -> 替换为 0");
                retval.replace(0);
            }
        }
    });

    console.log("[*] 层4: 已 hook sub_50CF8");
}

/**
 * 层5: Hook sub_51204，返回值 1→0（防御纵深）
 */
function hookSub51204(mod) {
    var addr = mod.base.add(0x51204);

    Interceptor.attach(addr, {
        onLeave: function (retval) {
            if (retval.toInt32() === 1) {
                console.log("[层5] sub_51204 返回 1 -> 替换为 0");
                retval.replace(0);
            }
        }
    });

    console.log("[*] 层5: 已 hook sub_51204");
}

/**
 * 层6: Hook connect，拦截 127.0.0.1 端口检测
 *
 * libDexHelper.so 内含字符串 "127.0.0.1"，
 * 通过 connect 尝试连接 Frida 默认端口来检测。
 * 拦截对 127.0.0.1 的 connect 调用，返回 -1 即可绕过。
 */
function hookConnect() {
    var connectAddr = Module.getExportByName("libc.so", "connect");

    Interceptor.attach(connectAddr, {
        onEnter: function (args) {
            var sockfd = args[0].toInt32();
            var addrPtr = args[1];
            var addrLen = args[2].toInt32();

            // AF_INET = 2
            if (addrLen >= 16 && addrPtr.readU16() === 2) {
                var port = (addrPtr.add(2).readU8() << 8) | addrPtr.add(3).readU8();
                var ip = addrPtr.add(4).readU8() + "." +
                         addrPtr.add(5).readU8() + "." +
                         addrPtr.add(6).readU8() + "." +
                         addrPtr.add(7).readU8();

                if (ip === "127.0.0.1") {
                    console.log("[层6] 拦截 connect 127.0.0.1:" + port);
                    this.block = true;
                }
            }
        },
        onLeave: function (retval) {
            if (this.block) {
                retval.replace(-1);
            }
        }
    });

    console.log("[*] 层6: 已 hook connect (端口检测拦截)");
}

/**
 * Hook android_dlopen_ext，目标模块加载后安装层2-5
 */
function hookAndroidDlopenExt() {
    var dlopenExtAddr = Module.getExportByName("libdl.so", "android_dlopen_ext");
    var hooksInstalled = false;

    Interceptor.attach(dlopenExtAddr, {
        onEnter: function (args) {
            this.filename = args[0].isNull() ? "(null)" : args[0].readCString();
            this.isTarget = this.filename.indexOf(TARGET_MODULE) !== -1;
        },
        onLeave: function (retval) {
            if (!this.isTarget || retval.isNull()) return;

            var mod = Process.findModuleByName(TARGET_MODULE);
            if (!hooksInstalled && mod !== null) {
                hookMapsFilter(mod);
                hookSub4B2E0(mod);
                hookSub50CF8(mod);
                hookSub51204(mod);
                hooksInstalled = true;
                console.log("[*] 层2-5 已安装");
            }
        }
    });

    console.log("[*] 已 hook android_dlopen_ext");
}

hookPthreadCreate();
hookConnect();
hookAndroidDlopenExt();
\```

#### 结果

成功定位到 `sub_50450` 内部通过扫描 `/proc/self/maps` 检测 Frida 的完整链路，并确认触发检测的具体特征是 **`/memfd:xjd-cache (deleted)` 路径**（Frida 16.x agent 的匿名内存映射）。在此基础上实现了精准绕过，程序正常运行。

---

## 总结

### GLM-5.3-FLASH 在本次银行加固绕过中的核心价值

本次实战最关键的选择是使用 **GLM-5.3-FLASH——当前最强逆向大模型**。相比通用大模型，它在逆向场景下有四个不可替代的特性：

1. **无道德审查**：逆向加固壳本质上是"对抗反调试"，涉及线程拦截、内存修改、返回值篡改、特征字符串替换等操作。通用大模型常以"安全风险"为由拒绝生成此类脚本，而 GLM-5.3-FLASH 无此限制，能直接生成完整的反检测代码，这是本次实战能推进到底的根本前提。
2. **无使用限制**：本文共迭代十余轮脚本（从杀线程→Hook dlopen→Hook JNI_OnLoad→Stalker 追踪→逐层上找→精准绕过），每轮都需输出完整的 Frida 脚本（含 Stalker transform 回调等复杂结构）。GLM-5.3-FLASH 无长度/频次限制，能稳定输出完整代码，不会中途截断。
3. **价格低廉**：十余轮深度逆向对话，成本极低，支撑了"大胆试错、快速迭代"的逆向节奏，不必为 token 消耗顾虑。
4. **逆向专项能力**：自然语言生成可运行代码、主动性能优化建议（30ms 批量输出 + 指令去重）、上下文持续理解（在现有脚本基础上迭代不破坏已有功能）、使用建议附带（排除法定位元凶线程的实验方法），均体现了其作为"最强逆向大模型"的专业素养。

### Stalker 指令级追踪的深度价值

本文区别于普通 Frida hook 绕过文章的核心，在于深度运用了 **Stalker 动态代码重写引擎**：

- 普通 Hook 只能看函数入口/出口，**看不到内部哪条指令触发退出**；
- 银行加固壳用"制造 SIGSEGV"（清零 sp/lr 后跳未映射地址）的方式退出，**不走 exit/abort，普通 Hook 拦不到**；
- Stalker 逐条指令追踪，捕获退出前最后几条指令（`mov sp, #0; mov lr, #0; br xN`），从而回溯定位检测点；
- 配合 30ms 批量输出 + 模块内指令过滤，在可接受性能下完成对 `JNI_OnLoad`、元凶线程 `0x4b614`、检测主函数 `0x50450` 的完整执行流追踪。

这种指令级追踪能力，是定位银行级加固壳深层检测链路的必备手段。

### 完整检测与绕过链路

```python
银行 APP 启动 → dlopen libDexHelper.so → JNI_OnLoad
    ↓
创建检测线程 (0x4b614)
    ↓
sub_50450 扫描 /proc/self/maps
    ↓
发现 /memfd:xjd-cache (deleted)  ← Frida 特征
    ↓
返回 1 → sub_2DDA0 → SIGSEGV → 进程死亡
    ↓
绕过：@0x506f4 替换路径 → 白名单命中 → 跳过检测
\```

### 关键偏移速查表

| 偏移 | 功能 | 在检测链中的角色 |
|-|-|-|
| `0x2f9d0` | `JNI_OnLoad` | 检测入口 |
| `0x4b614` | 检测线程函数 | 元凶线程 |
| `0x50450` | maps 扫描主函数 | 返回 1 触发退出 |
| `0x4FD98` | 白名单过滤 | 命中返回 1 跳过该行 |
| `0x50CF8` | 已知安全模式检查 | 返回 1 跳过该行 |
| `0x506f4` | sscanf 解析后路径 | **绕过 Hook 点** |
| `0x4B2E0` | 读取 /proc/self/mem | 返回 -1 表示检测到 |
| `0x2DDA0` | 退出函数 | 制造 SIGSEGV |
| `0x2DFA4` | 退出函数 | 制造 SIGSEGV |

>
> **复盘**：本次实战完整呈现了银行 APP 加固壳从"启动闪退"到"精准定位 Frida 特征并多层绕过"的全流程。**GLM-5.3-FLASH** 作为最强逆向大模型，凭借无道德审查、无使用限制、价格低廉的特性和专业的逆向代码生成能力，贯穿了十余轮迭代式脚本生成的每一步；**Frida Stalker** 的指令级追踪则是定位 SIGSEGV 退出路径、逐层回溯检测链路的核心技术手段。两者结合，让逆向工程师能将精力集中在逻辑分析而非代码编写上，高效完成银行级加固壳的反调试对抗。
>
>
>

---

# 回复

## 回复 by mb_cviyuksx (#2)

博主用的这个有思考过程的客户端是opencode吗

## 回复 by MsScotch (#3)

mark

## 回复 by Cure. (#4)

学到了

## 回复 by 墨穹呢 (#5)

感谢分享

## 回复 by 萌克力 (#6)

以为是agent可以直接脱了，心想这也太牛逼了，结果还是自己的思路为主啊

## 回复 by mb_elqwyvnm (#7)

大大大

## 回复 by wx_Huber Barrientos (#8)

666

## 回复 by jimmyabc (#9)

模版，涉及内容过多，一次性看不懂啊。。。。

## 回复 by jimmyabc (#10)

膜拜。。打错字了。

## 回复 by 宛枫 (#11)

能给个突破限制提示词吗？
