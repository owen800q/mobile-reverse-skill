---
title: '[原创]经典 Frida 检测 libmsaoaidsec.so 绕过'
url: https://bbs.kanxue.com/thread-289359.htm
tid: 289359
author: xiusi
date: '2025-12-08'
tags: [Android安全, 原创, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T15:23:08+08:00'
replies: 320
---

# 经典 Frida 检测 libmsaoaidsec.so 绕过

案例：某红薯（v9.8.0）

## 1. 定位检测源：追踪 SO 加载流程

在面对 Frida 检测导致的闪退时，首要任务是找到**是哪个 SO 库**触发了检测。
通常，反调试逻辑会在 `JNI_OnLoad` 或 `.init_array` 中执行。如果 App 在加载某个特定的 SO 后立即崩溃，那么该 SO 极大概率就是检测逻辑的所在地。

### 核心思路

通过 Hook 系统底层的动态库加载函数，监控 App 启动过程中加载了哪些 SO 文件。观察 App 崩溃（闪退）前的最后一条加载记录，即可锁定目标。

### Hook 目标：`android_dlopen_ext`

在 Android 7.0 (Nougat) 及更高版本中，系统加载动态库的底层实现主要依赖 `android_dlopen_ext`。相比标准的 `dlopen`，它提供了更丰富的扩展能力（如从文件描述符加载、指定内存空间加载等），是系统加载器的必经之路。

**函数原型**：

| 12345 | `void``* android_dlopen_ext(``const` `char``* filename,` `// args[0]: SO 文件路径``int` `flag,` `// args[1]: 加载标志``const` `android_dlextinfo* extinfo` `// args[2]: 扩展信息结构体``);` |
|-|-|

### 侦测脚本

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344 | `(``function` `() {``// 辅助函数：获取格式化时间``function` `getTime() {``return` `new` `Date().toLocaleTimeString();``}` `// 辅助函数：终端颜色高亮``function` `color(str) {``return` `"\x1b[36m"` `+ str +` `"\x1b[0m"``;``}` `// 1. 查找 android_dlopen_ext 导出地址``// 第一个参数传 null 表示在所有加载的模块中查找``var` `dlopen = Module.findExportByName(``null``,` `"android_dlopen_ext"``);` `if` `(!dlopen) {``console.log(``"[-] android_dlopen_ext not found. Try hooking dlopen instead."``);``return``;``}` `console.log(``"\n[*] Sniffer started on android_dlopen_ext...\n"``);` `Interceptor.attach(dlopen, {``onEnter:` `function` `(args) {``try` `{``// args[0] 是 char* 类型的路径字符串``var` `pathPtr = args[0];``if` `(pathPtr.isNull())` `return``;` `var` `soPath = pathPtr.readCString();``// 过滤无效路径``if` `(!soPath \|\| soPath.trim() ===` `""``)` `return``;` `// 过滤掉系统库，只关注 /data/ 下的应用私有库（可选）``// if (soPath.indexOf("/system/") !== -1) return;` `console.log(`[${getTime()}] Thread:${Process.getCurrentThreadId()} Loading => ${color(soPath)}`);` `}` `catch` `(e) {``console.log(``"[Error] "` `+ e);``}``}``});``})();` |
|-|-|

### 结果分析

使用 `spawn` 模式启动 App 并注入上述脚本：

| 1 | `frida -U -f com.xingin.xhs -l hook.js` |
|-|-|

**现象**：
控制台快速打印出一系列 SO 加载日志，随后 App 突然闪退，Frida 会话断开。

**日志片段**：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_FHKMUJNDUAV3PM8.png)

**结论**：
加载日志停留在 **`libmsaoaidsec.so`**。这说明当系统尝试加载并初始化该库时，触发了其内部的反调试机制，导致进程自杀。

---

## 2. 深入定位：追踪检测线程

确定了 `libmsaoaidsec.so` 是检测元凶后，我们需要找出具体是哪段代码在执行检测。通常，反调试逻辑不会在主线程运行（会卡顿 UI），而是创建一个独立的 **子线程 (pthread)** 进行轮询检测。

因此，我们需要 Hook 系统底层的线程创建函数 `pthread_create`，监控由 `libmsaoaidsec.so` 发起的所有线程创建行为，并获取其执行函数的入口地址。

### 侦测脚本

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566 | `(``function` `() {` `function` `now() {``return` `new` `Date().toLocaleTimeString();``}` `// 格式化输出对齐``function` `align(label, value) {``return` `(label +` `":"``).padEnd(14,` `" "``) + value;``}` `function` `color(str) {``return` `"\x1b[36m"` `+ str +` `"\x1b[0m"``;``}` `var` `targetOnly =` `false``;` `// 若设置为 true，则过滤系统 so，只显示第三方库` `// 1. 获取 pthread_create 函数地址``var` `pthread_create_addr = Module.findExportByName(``null``,` `"pthread_create"``);``if` `(!pthread_create_addr) {``console.log(``"[-] pthread_create not found."``);``return``;``}` `// 2. 定义原函数的 Native 原型，以便后续调用``// int pthread_create(pthread_t *thread, const pthread_attr_t *attr, void *(*start_routine) (void *), void *arg);``var` `pthread_create_native =` `new` `NativeFunction(``pthread_create_addr,` `"int"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``]``);` `console.log(``"\n===== pthread_create monitor started =====\n"``);` `// 3. 使用 Interceptor.replace 替换原函数``Interceptor.replace(pthread_create_addr,` `new` `NativeCallback(``function` `(p0, p1, start_routine, arg) {` `// --- 核心逻辑：反查模块信息 ---``// 通过线程入口地址 (start_routine) 查找它属于哪个 SO 文件``var` `module = Process.findModuleByAddress(start_routine);` `var` `soName = module ? module.name :` `"unknown"``;``// 计算偏移量：函数绝对地址 - 模块基址 = 静态偏移 (IDA 中的地址)``var` `offset = module ?` `"0x"` `+ start_routine.sub(module.base).toString(16) :` `"N/A"``;` `// 过滤逻辑``if` `(targetOnly && soName.indexOf(``"lib"``) === 0 && soName.indexOf(``"libc"``) >= 0) {``return` `pthread_create_native(p0, p1, start_routine, arg);``}` `// 捕获到目标 SO 创建线程时打印``if` `(soName.indexOf(``"msaoaidsec"``) !== -1) {``console.log(``"----------------------------------------"``);``console.log(align(``"Time"``, now()));``console.log(align(``"Thread TID"``, Process.getCurrentThreadId()));` `// 当前发起创建的线程``console.log(align(``"Target SO"``, color(soName)));``console.log(align(``"Entry Addr"``, start_routine));``console.log(align(``"Offset (IDA)"``, color(offset)));` `// 重点关注这个偏移``console.log(align(``"Arg"``, arg));``console.log(``"----------------------------------------"``);``}` `// 4. 必须执行原函数，否则应用会崩溃或线程无法创建``return` `pthread_create_native(p0, p1, start_routine, arg);` `},` `"int"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``]));` `})();` |
|-|-|

### 技术原理解析

#### 1. 目标函数：`pthread_create`

这是 Linux/Android 创建线程的标准 POSIX API。

| 123456 | `int` `pthread_create(``pthread_t *``thread``,` `// arg0: 指向线程标识符的指针``const` `pthread_attr_t *attr,` `// arg1: 线程属性``void` `*(*start_routine) (``void` `*),` `// arg2: 【关键】线程启动后执行的函数指针``void` `*arg` `// arg3: 传递给启动函数的参数``);` |
|-|-|

我们重点关注 **`start_routine`** **(arg2)** ，它直接指向了线程要执行的代码逻辑。

#### 2. 核心 API：`Process.findModuleByAddress(ptr)`

- **作用**：传入一个内存地址，Frida 会自动查询进程的内存映射表（Maps），返回该地址所属的 **Module 对象**（包含模块名 `name`、基址 `base` 等信息）。
- **用途**：用于判断某个函数指针到底是属于系统库（如 `libc.so`），还是属于我们要分析的恶意库（`libmsaoaidsec.so`）。

#### 3. 为什么使用 `Interceptor.replace`？

- 虽然 `Interceptor.attach` 也能监控，但在 Native 层 Hook 这种系统级函数时，`replace`（完全替换实现）提供了更强的控制力。
- 我们可以选择性地**阻止**某些恶意线程的创建（直接不调用 `pthread_create_native` 并返回 0），从而实现“阻断反调试线程”的效果。

### 结果分析

运行脚本后，当控制台输出如下信息时，我们便成功捕获了检测线程：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_23NVXZPNJPTXWGF.png)

通过输出我们可以看到一共捕获到了3条关于 `libmsaoaidsec.so` 创建线程的数据，其函数在so中的偏移量分别是：

| 1 | `0x1c544, 0x1b8d4, 0x26e5c` |
|-|-|

---

## 3. 实施绕过：阻断检测线程

在定位到检测线程的来源后，最简单粗暴且有效的绕过方式是  **“拒绝执行”** 。

由于 `libmsaoaidsec.so` 中的检测逻辑通常在子线程中死循环运行，我们可以 Hook `pthread_create`，当识别到请求来自该 SO 库时，**直接返回 0**（假装创建成功），但不调用原始的 `pthread_create` 函数。这样，反调试线程永远不会被创建，而主程序的逻辑却以为线程已正常启动。

### 绕过脚本

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748 | `(``function` `() {` `// 辅助函数：获取当前时间``function` `now() {``return` `new` `Date().toLocaleTimeString();``}` `// 1. 获取 pthread_create 地址``var` `pthread_create_addr = Module.findExportByName(``null``,` `"pthread_create"``);``if` `(!pthread_create_addr) {``console.log(``"[-] pthread_create not found."``);``return``;``}` `// 2. 定义原函数用于后续调用``var` `pthread_create_native =` `new` `NativeFunction(``pthread_create_addr,` `"int"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``]``);` `console.log(``"\n===== pthread_create killer started =====\n"``);` `// 3. 替换 (Replace) 原函数``Interceptor.replace(pthread_create_addr,` `new` `NativeCallback(``function` `(p0, p1, start_routine, arg) {` `// 反查模块信息``var` `module = Process.findModuleByAddress(start_routine);``var` `soName = module ? module.name :` `"unknown"``;``var` `offset = module ?` `"0x"` `+ start_routine.sub(module.base).toString(16) :` `"N/A"``;` `// --- 核心绕过逻辑 ---``// 检查线程入口函数是否属于 libmsaoaidsec.so``if` `(soName.indexOf(``"libmsaoaidsec.so"``) !== -1) {` `// 打印日志，确认拦截生效``console.log(`[+] \x1b[31mBLOCKED\x1b[0m Detection Thread from: ${soName} \| Offset: ${offset}`);` `// 【关键】直接返回 0``// 在 C 语言标准中，pthread_create 返回 0 代表“成功”``// 我们欺骗 App 说线程创建成功了，但实际上什么都没做``return` `0;``}` `// 对于其他正常的线程请求，放行并执行原函数``return` `pthread_create_native(p0, p1, start_routine, arg);` `},` `"int"``, [``"pointer"``,` `"pointer"``,` `"pointer"``,` `"pointer"``]));` `})();` |
|-|-|

### 原理解析

1. **为什么是** **`return 0`** **？**
 `pthread_create` 的函数原型定义中，返回值 **0** 表示 **Success**（成功），而非 0 的值表示错误码。
 反调试逻辑通常会检查返回值：

| 1234 | `if` `(pthread_create(...) != 0) {``// 创建失败，环境异常，可能被干扰 -> 退出``exit``(0);``}` |
|-|-|

 通过返回 0，我们完美欺骗了上层逻辑，使其认为“监控线程”正在正常运行。
2. **副作用与风险**
 目前的脚本采用的是“核弹级”处理：**禁止该 SO 创建任何线程**。

	- **如果** `libmsaoaidsec.so` 只有反调试线程，那么此法完美。
	- **如果** 该 SO 还需要创建处理业务（如生成 Token）的合法线程，这种“一刀切”的做法可能会导致业务功能失效（例如 App 无法获取 OAID）。
3. **进阶：精确打击 (基于 Offset)**
 如果发现“一刀切”导致 App 功能异常，请使用 **第 2 步** 中获取的 **Offset** 进行精确过滤：

### 结果

成功绕过，程序没用被 **Kill** ，且程序正常运行：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_NB67CBGV9JPGJAN.png)

---

## 4. 其它绕过方法：Hook 初始化函数 (.init_proc)

### SO 库的加载流程详解

Android 系统加载一个 SO 库的顺序如下：

1. **`dlopen`** **/** **`android_dlopen_ext`**：系统调用加载器，将 SO 映射到内存。
2.  **`.init`** **/** **`.init_proc`**：执行初始化段的代码。
3.  **`.init_array`**：执行初始化数组中的函数（C++ 全局构造函数等）。
4. **`JNI_OnLoad`**：最后执行，通常用于注册 JNI 方法。

>
> 很多强壳或检测库（如 `libmsaoaidsec.so`）会将反调试检测放在 **`.init_proc`** 或 **`.init_array`** 中。
> 如果我们在 `android_dlopen_ext` 的 `onLeave`（即加载完成）后再去 Hook `JNI_OnLoad`，此时 `.init` 系列函数早已执行完毕，检测已经触发（App 已闪退），为时晚矣。
>
>
>

### 1. 寻找更早的 Hook 时机

既然 `onLeave` 太晚，我们需要在 `android_dlopen_ext` 的 `onEnter` 之后，但在 `.init` 函数执行期间介入。
最佳策略是：**寻找一个在** **`.init_proc`** **中被调用的外部导入函数（Import）进行 Hook**。

>
> so 未加载完全，无法 Hook 导出函数，也无法通过 so 基址 + 偏移的方式 Hook 函数，所以只能通过 Hook 导入函数进行绕过。
>
>
>

#### 逆向分析 `.init_proc`

通过 IDA 反编译 `libmsaoaidsec.so` 的 `.init_proc` 函数：

| 12345678910111213 | `void` `init_proc()``{``// ...``// 1. 调用系统属性获取函数，获取 SDK 版本``_system_property_get(``"ro.build.version.sdk"``, v1);``// ...``// 2. 各种复杂的初始化和检测逻辑``if` `( (sub_25A48() & 1) == 0 )``{``// ...``sub_1BEC4();` `// 可能包含反调试线程创建``}``}` |
|-|-|

我们发现 `.init_proc` 的入口处调用了  **`__system_property_get`**。这是一个非常好的 Hook 锚点！只要我们 Hook 这个系统函数，当它被调用且参数为 `ro.build.version.sdk` 时，我们就可以断定：**现在正是** **`libmsaoaidsec.so`** **执行初始化的时刻**。

此时 SO 已经在内存中（基址已确定），但后续的检测线程还没来得及创建。

### 2. 编写精确注入脚本

我们的思路如下：

1. Hook `android_dlopen_ext`，监听 `libmsaoaidsec.so` 的加载。
2. 一旦加载，立即 Hook `__system_property_get`。
3. 当捕获到 `ro.build.version.sdk` 属性读取时，说明目标 SO 正在初始化。
4. 此时获取 SO 基址，并直接 **NOP** 掉之前发现的三个检测线程的创建处。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768 | `// NOP 函数：将目标地址指令替换为 RET (直接返回)``function` `nop_64(addr) {``try` `{``// 修改内存权限``Memory.protect(addr, 4,` `'rwx'``);``var` `w =` `new` `Arm64Writer(addr);``// 写入 RET 指令，相当于函数直接结束，不执行任何逻辑``// 也可以使用 w.putNop()，视具体汇编逻辑而定``w.putRet();` `w.flush();``w.dispose();``console.log(`[+] Patched at ${addr}`);``}` `catch` `(e) {``console.error(`[-] Failed to patch at ${addr}: ${e}`);``}``}` `// 核心 Hook 逻辑``function` `locate_init() {``var` `sys_prop_get = Module.findExportByName(``null``,` `"__system_property_get"``);` `Interceptor.attach(sys_prop_get, {``onEnter:` `function` `(args) {``var` `namePtr = args[0];``if` `(namePtr.isNull())` `return``;` `var` `name = namePtr.readCString();` `// 锚点匹配：当读取 SDK 版本时，说明处于 init_proc 早期``if` `(name && name.indexOf(``"ro.build.version.sdk"``) !== -1) {``// 此时 SO 已在内存中，可以获取基址``var` `module = Process.findModuleByName(``"libmsaoaidsec.so"``);` `if` `(module) {``console.log(`[+] Found module base: ${module.base}`);` `// 需要 NOP 的三个检测线程创建点的偏移 (来自前面的 pthread_create 监控)``// 0x1c544, 0x1b8d4, 0x26e5c``var` `offsets = [0x1c544, 0x1b8d4, 0x26e5c];` `offsets.forEach(``function``(offset) {``var` `targetAddr = module.base.add(offset);``console.log(`[*] Patching thread creation at offset 0x${offset.toString(16)}...`);``nop_64(targetAddr);``});` `// Patch 完成后，可以取消 Hook 以免影响性能（可选）``// Interceptor.detachAll();` `}``}``}``});``}` `// 入口：监听 DLOpen``Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``), {``onEnter:` `function` `(args) {``var` `pathPtr = args[0];``if` `(pathPtr.isNull())` `return``;` `var` `path = pathPtr.readCString();``if` `(path.indexOf(``"libmsaoaidsec.so"``) !== -1) {``console.log(`[*] Detected loading of ${path}`);``// 开启第二阶段 Hook``locate_init();``}``}``});` |
|-|-|

### 结果

App 正常启动，日志显示 Patch 成功，且没有再出现闪退。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_N5WSS789Y65AUEV.png)

>
> 面对在 `.init` 段做检测的 SO，**`android_dlopen_ext`** **+** **`__system_property_get`** 是一套非常经典的组合拳。它能帮我们卡住 SO 初始化的咽喉，实现最完美的早期注入。
>
>
>

---

## 参考文章

[https://arch3rn4r.github.io/2025/03/02/frida%E7%BB%95%E8%BF%87%E...](https://arch3rn4r.github.io/2025/03/02/frida%E7%BB%95%E8%BF%87%E6%A3%80%E6%B5%8B%E5%AD%A6%E4%B9%A0/)

‍

---

# 回复

## 回复 by Sharp_Wang (#2)

*2025-12-8 17:53*

666

## 回复 by jyotidwi (#3)

*2025-12-8 18:16*

6666

## 回复 by mb_zqrczqwa (#4)

*2025-12-8 19:37*

66666

## 回复 by cpannn (#5)

*2025-12-8 21:40*

666666

## 回复 by mb_ldbucrik (#6)

*2025-12-8 23:54*

感谢分享

## 回复 by mb_elqwyvnm (#7)

*2025-12-9 00:00*

mb_ldbucrik
  6 楼
感谢分享

## 回复 by wx_范迪塞尔 (#8)

*2025-12-9 09:44*

66666

## 回复 by mb_cbgtaveo (#9)

*2025-12-9 09:59*

6666666666

## 回复 by 七星舞月 (#10)

*2025-12-9 10:35*

感谢分享

## 回复 by 飞机上唱山歌 (#11)

*2025-12-9 10:36*

1

## 回复 by Imxz (#12)

*2025-12-9 10:48*

tql

## 回复 by mb_uvyukvot (#13)

*2025-12-9 11:18*

感谢分享

## 回复 by mb_pesxllvn (#14)

*2025-12-9 11:33*

666

## 回复 by mb_iymaphxh (#15)

*2025-12-9 11:39*

666

## 回复 by wx_Huber Barrientos (#16)

*2025-12-9 12:21*

很给力，感谢分享！

## 回复 by 呼吸24K纯氧 (#17)

*2025-12-9 13:44*

很给力，感谢分享！

## 回复 by mb_roiscepd (#18)

*2025-12-9 16:43*

666

## 回复 by KanXue_NG (#19)

*2025-12-10 09:42*

学习学习

## 回复 by zxhubo (#20)

*2025-12-10 13:54*

非常好

## 回复 by iamshy (#21)

*2025-12-10 14:01*

学习学习

## 回复 by zxhubo (#22)

*2025-12-10 14:18*

最新版YY也是使用的这个版本的libmsaoaidsec.so，因为pthread_create的几个偏移都是一模一样的，但是patch这几个地址以后APP直接白屏卡死，过一会就再次crash了。

## 回复 by git_94730eaydwshawke-gif (#23)

*2025-12-10 15:25*

666

## 回复 by wx_五十度灰 (#24)

*2025-12-10 17:20*

666

## 回复 by mb_pobqzscg (#25)

*2025-12-10 17:32*

666

## 回复 by mb_qimctavn (#26)

*2025-12-10 18:03*

6

## 回复 by mb_hwzomkxk (#27)

*2025-12-10 21:01*

快对app的libmsaoaidsec有点奇怪

## 回复 by zylyy (#28)

*2025-12-10 23:27*

666

## 回复 by 平乱止戈 (#29)

*2025-12-11 11:20*

学习大佬

## 回复 by upcj (#30)

*2025-12-11 13:42*

666

## 回复 by 睡不醒的我 (#31)

*2025-12-11 14:11*

666

## 回复 by mb_uktygsmq (#32)

*2025-12-11 14:45*

666

## 回复 by Snark (#33)

*2025-12-11 17:26*

1

## 回复 by wx_666_974 (#34)

*2025-12-12 11:06*

666

## 回复 by mb_yyvcbkli (#35)

*2025-12-12 11:33*

学习一下先进经验

## 回复 by wx_故事与酒 (#36)

*2025-12-12 14:41*

666666666666666666

## 回复 by GuL1ng (#37)

*2025-12-12 15:31*

66666

## 回复 by 影子记忆 (#38)

*2025-12-12 15:34*

6666

## 回复 by lazybulazy (#39)

*2025-12-12 21:54*

666

## 回复 by mb_igwchhlt (#40)

*2025-12-13 10:07*

看看啊

## 回复 by 小尘0000 (#41)

*2025-12-13 10:53*

666

## 回复 by lazybulazy (#42)

*2025-12-13 17:03*

佬，想请教一下第一种绕过方法找libmsaoaidsec.so 内部偏移函数的时候，运行脚本出现这种情况是怎么回事呀，程序卡在启动界面，so加载情况一直显示的是libart.so

![image](https://bbs.kanxue.com/upload/attach/202512/1000319_DC7GZ23GAT6N3HE.png)

上传的附件：
- 35BBD310748E6CCCD05B3862D97B4A1B.png

（21.64kb，7次下载）

## 回复 by mb_jhohnbzu (#43)

*2025-12-13 17:33*

666

## 回复 by mb_jhohnbzu (#44)

*2025-12-13 17:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zxhubo](https://bbs.kanxue.com/user-835034.htm)
>
>  最新版YY也是使用的这个版本的libmsaoaidsec.so，因为pthread_create的几个偏移都是一模一样的，但是patch这几个地址以后APP直接白屏卡死，过一会就再次crash了。
>
>

解决了吗

## 回复 by yyamcom (#45)

*2025-12-13 17:50*

666

## 回复 by mb_chjjqnap (#46)

*2025-12-14 11:06*

666

## 回复 by xiusi (#47)

*2025-12-14 15:08*

>
> [lazybulazy](https://bbs.kanxue.com/user-1000319.htm)
>
>  佬，想请教一下第一种绕过方法找libmsaoaidsec.so 内部偏移函数的时候，运行脚本出现这种情况是怎么回事呀，程序卡在启动界面，so加载情况一直显示的是libart.so
>
>

我现在也是这样，要hook可以直接用魔改的 frida ，不用去绕

## 回复 by xiusi (#48)

*2025-12-14 15:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zxhubo](https://bbs.kanxue.com/user-835034.htm)
>
>  最新版YY也是使用的这个版本的libmsaoaidsec.so，因为pthread_create的几个偏移都是一模一样的，但是patch这几个地址以后APP直接白屏卡死，过一会就再次crash了。
>
>

我现在也是这种情况，直接用魔改的frida吧，不用去绕

## 回复 by lyuzhao (#49)

*2025-12-14 20:20*

666

## 回复 by mb_srmwcgoy (#50)

*2025-12-14 22:26*

6666666666666

## 回复 by zkbutt (#51)

*2025-12-14 22:57*

很清晰

## 回复 by mb_hyhfavas (#52)

*2025-12-15 13:02*

66666

## 回复 by mb_ajxntfzc (#53)

*2025-12-15 14:04*

6666

## 回复 by ben_ (#54)

*2025-12-15 15:22*

谢谢分享

## 回复 by kingking888 (#55)

*2025-12-16 16:57*

666

## 回复 by mb_aelpsyuc (#56)

*2025-12-16 17:20*

看看内容

## 回复 by chenwitch (#57)

*2025-12-16 17:47*

666

## 回复 by LoeweErr (#58)

*2025-12-16 20:40*

666

## 回复 by mb_wuevwbec (#59)

*2025-12-18 09:58*

666

## 回复 by guijingwen (#60)

*2025-12-18 10:19*

66

## 回复 by 天水姜伯约 (#61)

*2025-12-18 10:44*

hook so入口点可以用一套模板代码

get_so_name = (const char *(*)(void *soinfo))
            (linker64_base +
             get_sym_addr("/apex/com.android.runtime/bin/linker64",
                          "__dl__ZNK6soinfo10get_sonameEv"));
    if (get_so_name == nullptr) {
        LOGE("failed to get get_so_name address");
        return;
    } else {
        LOGD("get_so_name address: %p", (void *) get_so_name);
    }

    static void *call_constructors_addr = (void *)
            (linker64_base +
             get_sym_addr("/apex/com.android.runtime/bin/linker64",
                          "__dl__ZN6soinfo17call_constructorsEv"));
    if (call_constructors_addr == nullptr) {
        LOGE("failed to get call_constructors address");
        return;
    } else {
        LOGD("call_constructors address: %p", call_constructors_addr);
    }

    DobbyInstrument(call_constructors_addr, [](void *address, DobbyRegisterContext *ctx) {
        const char *soname = (const char *) get_so_name((void *) ctx->general.x[0]);
        // hook到了so的加载点, 此时还未调用init_array
        if (soname && strstr(soname, "libmetasec_ml.so")) {

## 回复 by ventest (#62)

*2025-12-18 11:02*

谢谢

## 回复 by 悲守空诺 (#63)

*2025-12-18 13:51*

666

## 回复 by xinhu (#64)

*2025-12-18 14:54*

666666666

## 回复 by mb_clklzhev (#65)

*2025-12-18 15:01*

666

## 回复 by mb_euhyowpw (#66)

*2025-12-18 16:11*

666

## 回复 by wx_郑泽科 (#67)

*2025-12-19 11:21*

666

## 回复 by 4Chan (#68)

*2025-12-19 11:23*

666

## 回复 by mb_jjdbksrs (#69)

*2025-12-19 15:42*

666

## 回复 by 萧别离 (#70)

*2025-12-20 15:43*

学习一下

## 回复 by wx_马 (#71)

*2025-12-21 11:07*

666

## 回复 by 梨树生果 (#72)

*2025-12-21 16:56*

666

## 回复 by mb_dcjxxhsk (#73)

*2025-12-21 22:51*

6666

## 回复 by 司徒废人 (#74)

*2025-12-22 09:55*

666

## 回复 by 魔童 (#75)

*2025-12-22 21:13*

66666666

## 回复 by mb_nxicnwnb (#76)

*2025-12-23 15:01*

666

## 回复 by Ally Switch (#77)

*2025-12-23 18:42*

目标so的导入表里面没有pthread_create的时候，可以尝试去hook一下dlsym

## 回复 by 龙游天下178 (#78)

*2025-12-24 00:01*

6666

## 回复 by mb_txbqztiu (#79)

*2025-12-25 01:48*

666

## 回复 by 零_721409 (#80)

*2025-12-25 14:43*

6666666666

## 回复 by carrys (#81)

*2025-12-25 16:03*

666

## 回复 by woaiziyou (#82)

*2025-12-26 09:55*

学习一下

## 回复 by mb_hfpmtthz (#83)

*2025-12-26 10:12*

6666

## 回复 by mb_acjczpsg (#84)

*2025-12-29 10:24*

666

## 回复 by AYHMO (#85)

*2025-12-29 19:49*

666

## 回复 by git_34874ucupucup8991-lgtm (#86)

*2025-12-30 16:20*

great

## 回复 by l140w4n9 (#87)

*2026-1-1 16:56*

66666

## 回复 by mb_apynwbms (#88)

*2026-1-2 11:40*

666

## 回复 by mb_lwukcnmf (#89)

*2026-1-2 14:43*

1

## 回复 by Kidimos (#90)

*2026-1-2 17:42*

刚好遇到了这个问题，So库用某Guard加固了，还以为也是Guard在检测frida，没想到一看竟然是libmsaoaidsec

## 回复 by Ace_Heng (#91)

*2026-1-2 17:56*

看看

## 回复 by Bileton (#92)

*2026-1-3 00:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zxhubo](https://bbs.kanxue.com/user-835034.htm)
>
>  最新版YY也是使用的这个版本的libmsaoaidsec.so，因为pthread_create的几个偏移都是一模一样的，但是patch这几个地址以后APP直接白屏卡死，过一会就再次crash了。
>
>

yy是哪个

## 回复 by xeiyu (#93)

*2026-1-3 01:48*

666

## 回复 by mb_bhsrdtqf (#94)

*2026-1-4 14:40*

666

## 回复 by mb_qnsuegcb (#95)

*2026-1-5 14:33*

666

## 回复 by Va1ue (#96)

*2026-1-5 16:19*

666

## 回复 by mb_garozvwc (#97)

*2026-1-5 23:06*

566666666666666

## 回复 by MaYil (#98)

*2026-1-5 23:43*

感谢分享

## 回复 by whe (#99)

*2026-1-6 13:54*

666

## 回复 by gannicusliu (#100)

*2026-1-6 13:56*

666

## 回复 by mb_hloacduf (#101)

*2026-1-6 17:46*

666

## 回复 by mb_tyktgjsk (#102)

*2026-1-7 11:13*

666

## 回复 by 1sfans (#103)

*2026-1-7 14:54*

666

## 回复 by superlahm (#104)

*2026-1-7 16:16*

666

## 回复 by CheRevir (#105)

*2026-1-7 17:56*

666

## 回复 by qq戚导 (#106)

*2026-1-7 18:12*

666

## 回复 by Iceshara (#107)

*2026-1-7 19:04*

666

## 回复 by tonykros (#108)

*2026-1-7 20:38*

666

## 回复 by wx_飞_847 (#109)

*2026-1-8 19:54*

66666

## 回复 by tjytjy (#110)

*2026-1-8 20:43*

666

## 回复 by 小路不迷路 (#111)

*2026-1-10 16:28*

6

## 回复 by 超级卡卡罗特 (#112)

*2026-1-11 18:20*

777

## 回复 by 带壳的蜗牛 (#113)

*2026-1-12 15:59*

666666

## 回复 by xianhuimin (#114)

*2026-1-12 21:44*

666

## 回复 by 看那是什么 (#115)

*2026-1-15 10:42*

666

## 回复 by ADR66 (#116)

*2026-1-15 10:50*

66666

## 回复 by mb_evapxmjh (#117)

*2026-1-15 14:36*

666

## 回复 by 漂流的鱼 (#118)

*2026-1-15 22:08*

666

## 回复 by zxhubo (#119)

*2026-1-16 15:22*

>
> [Bileton](https://bbs.kanxue.com/user-993971.htm)
>
>  yy是哪个
>
>
>

就是YY呀，YY 直播

## 回复 by zxhubo (#120)

*2026-1-16 15:24*

>
> [xiusi](https://bbs.kanxue.com/user-1036360.htm)
>
>
>
>
>
>
>
>  zxhubo
>
>
>
>  最新版YY也是使用的这个版本的libmsaoaidsec.so，因为pthread_create的几个偏移都是一模一样的，但 ...
>
>

这还没尝试呢，最近太忙了。等有空了再尝试看行不行

## 回复 by mb_empsallg (#121)

*2026-1-16 15:28*

非常6

## 回复 by 我不是卷王 (#122)

*2026-1-17 21:33*

666

## 回复 by 我不是卷王 (#123)

*2026-1-17 21:33*

6666

## 回复 by mb_oqoqqkxl (#124)

*2026-1-17 23:21*

666

## 回复 by mb_umunpakk (#125)

*2026-1-18 05:41*

666666

## 回复 by mb_zpvlfkkg (#126)

*2026-1-18 06:41*

66666

## 回复 by mb_gshxxejl (#127)

*2026-1-18 15:29*

666

## 回复 by fjqisba (#128)

*2026-1-20 13:36*

必须的

## 回复 by mb_cafsqqjq (#129)

*2026-1-21 04:44*

66666666666

## 回复 by Snowman_Liam (#130)

*2026-1-21 06:23*

666

## 回复 by a7dd (#131)

*2026-1-21 10:00*

tql

## 回复 by 10010 (#132)

*2026-1-21 19:53*

66666666666666

## 回复 by Bileton (#133)

*2026-1-22 07:44*

>
> [天水姜伯约](https://bbs.kanxue.com/user-783210.htm)
>
>  hook so入口点可以用一套模板代码
>
> get_so_name = (const char *(*)(void *soinfo))
>  (linker64_base ...
>
>

大牛，你的代码后面有一部分缺失了

## 回复 by 上官兮唐 (#134)

*2026-1-22 08:53*

看看

## 回复 by huangjw (#135)

*2026-1-22 09:17*

大佬非你莫属

## 回复 by mb_hbosztvl (#136)

*2026-1-22 09:19*

666

## 回复 by 天水姜伯约 (#137)

*2026-1-22 10:29*

>
> [Bileton](https://bbs.kanxue.com/user-993971.htm)
>
>  大牛，你的代码后面有一部分缺失了
>
>

```
function hook_linker_constructors() {
    // 1. 获取 linker64 的基地址或直接查找符号
    // 在 Android 10+ 中，linker 位于 /apex/com.android.runtime/bin/linker64
    const linkerName = "linker64";

    // 2. 查找符号地址 (对应 C++ 代码中的 get_sym_addr)
    // __dl__ZN6soinfo17call_constructorsEv -> soinfo::call_constructors()
    // __dl__ZNK6soinfo10get_sonameEv        -> soinfo::get_soname()
    const call_constructors_addr = Module.findExportByName(linkerName, "__dl__ZN6soinfo17call_constructorsEv");
    const get_soname_addr = Module.findExportByName(linkerName, "__dl__ZNK6soinfo10get_sonameEv");

    if (!call_constructors_addr || !get_soname_addr) {
        console.log("[-] 找不到符号，请确认 Android 版本或符号名是否正确");
        return;
    }

    // 3. 定义 get_soname 函数拨号 (NativeFunction)
    const get_so_name = new NativeFunction(get_soname_addr, 'pointer', ['pointer']);

    console.log("[+] Found call_constructors at: " + call_constructors_addr);
    console.log("[+] Found get_soname at: " + get_soname_addr);

    // 4. 使用 Interceptor.attach 替代 DobbyInstrument
    Interceptor.attach(call_constructors_addr, {
        onEnter: function (args) {
            // 在 C++ 中，成员函数的第一个参数 (x0) 是 'this' 指针，即 soinfo 实例
            const soinfo_ptr = args[0];

            // 调用 get_soname 获取库名
            const soname_ptr = get_so_name(soinfo_ptr);

            if (!soname_ptr.isNull()) {
                const soname = soname_ptr.readCString();

                // 5. 逻辑判断：匹配 libmetasec_ml.so
                if (soname.indexOf("libmetasec_ml.so") !== -1) {
                    console.log("[*] Detected loading: " + soname);

                    // 此时 .init_array 尚未执行，你可以在这里进行进一步的 Hook
                    // 例如：hook 该 so 内部的函数
                }
            }
        }
    });
}

// 执行 Hook
hook_linker_constructors();
```

那个是dobby的代码，用ai翻译成了frida js，可以看一下

## 回复 by mb_rhicgszx (#138)

*2026-1-25 15:54*

666

## 回复 by mb_vymbqugn (#139)

*2026-1-27 01:09*

6666

## 回复 by wingsevil (#140)

*2026-1-27 10:34*

学习学习

## 回复 by 荧光之夏 (#141)

*2026-1-29 11:22*

6666

## 回复 by 逆向小呆呆 (#142)

*2026-1-29 17:29*

6666

## 回复 by mb_zkvoudxe (#143)

*2026-2-1 05:19*

666

## 回复 by 这谁写的代码 (#144)

*2026-2-1 08:06*

666

## 回复 by Circ1e (#145)

*2026-2-2 19:52*

666

## 回复 by mobier (#146)

*2026-2-2 20:25*

![image](https://bbs.kanxue.com/view/img/face/078.gif)学习一下

## 回复 by xuhe123 (#147)

*2026-2-3 23:21*

666666

## 回复 by axpol (#148)

*2026-2-5 14:38*

111

## 回复 by mb_wdyvisdq (#149)

*2026-2-5 21:37*

学习一下

## 回复 by mb_wdyvisdq (#150)

*2026-2-5 21:39*

如果侦测脚本出来的so这是这样的，该怎么找对应位置呢？[09:37:33 PM] Thread:19209 Loading => libSignatureKiller.so  没有绝对路径

## 回复 by 小白鱼来了 (#151)

*2026-2-6 13:41*

966666666

## 回复 by yinsel (#152)

*2026-2-6 14:14*

感谢分享！！！

## 回复 by GEKEZYX (#153)

*2026-2-6 15:00*

666

## 回复 by mb_akyvqgsf (#154)

*2026-2-8 21:47*

666

## 回复 by mb_nidmxriy (#155)

*2026-2-10 13:27*

666

## 回复 by 萌新三连 (#156)

*2026-2-10 15:15*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by pphappy (#157)

*2026-2-11 04:27*

666

## 回复 by odysseus (#158)

*2026-2-11 06:19*

666

## 回复 by kccp (#159)

*2026-2-11 10:55*

1

## 回复 by mb_nlkswyor (#160)

*2026-2-11 14:34*

666

## 回复 by mb_kfdusnod (#161)

*2026-2-14 09:28*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by puppet_w (#162)

*2026-2-14 15:41*

6

## 回复 by mb_euphpkii (#163)

*2026-2-16 11:48*

666

## 回复 by mb_blhyvqfj (#164)

*2026-2-17 21:08*

这必须狠狠的学习呀，谢谢大佬![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_vyiuuicw (#165)

*2026-2-19 11:09*

tql

## 回复 by mb_cxpzdwfe (#166)

*2026-2-19 19:41*

6666

## 回复 by 饮岁 (#167)

*2026-2-24 10:06*

666

## 回复 by mb_ilyviizj (#168)

*2026-2-25 04:56*

111

## 回复 by mb_czqyztmr (#169)

*2026-2-25 14:13*

1

## 回复 by ivy1 (#170)

*2026-2-25 14:37*

666

## 回复 by Layer1 (#171)

*2026-2-25 15:08*

666

## 回复 by qingyebai (#172)

*2026-2-25 22:24*

666

## 回复 by 驼子 (#173)

*2026-2-25 22:43*

学习

## 回复 by 禾夕夕 (#174)

*2026-2-26 01:56*

666

## 回复 by mb_advzsyem (#175)

*2026-2-26 09:23*

学习一下

## 回复 by mb_rxlldkxh (#176)

*2026-2-28 11:17*

楼主，我根据你的贴子，尝试hook伊对app的libmsaoaidsec.so，没hook成功，一直没打印出pthread_create地址
└─# frida -U -f me.yidui -l hook_pthread_create.js --no-pause
     ____
    / _  |   Frida 14.2.18 - A world-class dynamic instrumentation toolkit
   | (_| |
    > _  |   Commands:
   /_/ |_|       help      -> Displays the help system
   . . . .       object?   -> Display information about 'object'
   . . . .       exit/quit -> Exit
   . . . .
   . . . .   More info at https://frida.re/docs/home/
Spawning `me.yidui`...

===== pthread_create monitor started =====

Spawned `me.yidui`. Resuming main thread!
[AOSP on msm8996::me.yidui]->

## 回复 by mb_hfpmtthz (#177)

*2026-2-28 14:44*

666

## 回复 by mb_oaufhyol (#178)

*2026-3-1 21:58*

666

## 回复 by mb_dwxaumtm (#179)

*2026-3-3 16:44*

666

## 回复 by jaefern (#180)

*2026-3-3 16:47*

666

## 回复 by Ram98 (#181)

*2026-3-3 17:17*

666

## 回复 by mb_gqzoivfx (#182)

*2026-3-3 19:13*

666

## 回复 by 带带弟弟吧 (#183)

*2026-3-3 20:37*

1

## 回复 by mb_gqzoivfx (#184)

*2026-3-4 11:36*

>
> [mb_rxlldkxh](https://bbs.kanxue.com/user-909786.htm)
>
>  楼主，我根据你的贴子，尝试hook伊对app的libmsaoaidsec.so，没hook成功，一直没打印出pthread_create地址
> └─# frida -U -f me.yidui -l ...
>
>

同上，解决了么

## 回复 by 土豆爱学习 (#185)

*2026-3-5 13:47*

12312312

## 回复 by mb_iyeoluxk (#186)

*2026-3-5 14:24*

66666

## 回复 by mb_stdlrcgp (#187)

*2026-3-5 23:03*

6666666

## 回复 by Noguess9 (#188)

*2026-3-6 10:16*

11

## 回复 by qig (#189)

*2026-3-7 12:08*

666

## 回复 by mb_sqetvntx (#190)

*2026-3-8 14:26*

xx

## 回复 by 土豆爱学习 (#191)

*2026-3-11 13:40*

666

## 回复 by devil_1 (#192)

*2026-3-11 14:30*

666

## 回复 by kalux (#193)

*2026-3-11 14:56*

666

## 回复 by qqqiu (#194)

*2026-3-15 21:54*

6

## 回复 by mb_awbfnjrt (#195)

*2026-3-16 10:10*

666

## 回复 by 小辣鸡的id (#196)

*2026-3-16 16:37*

1

## 回复 by parkerpan (#197)

*2026-3-17 10:42*

666

## 回复 by Crack999 (#198)

*2026-3-17 11:44*

学习学习

## 回复 by wx_？_992 (#199)

*2026-3-18 15:56*

666

## 回复 by 偏爱你妹 (#200)

*2026-3-18 18:10*

思路非常清晰

## 回复 by mb_prxebxbs (#201)

*2026-3-19 00:54*

666

## 回复 by 山东拓明 (#202)

*2026-3-20 10:57*

666

## 回复 by wx_佳仔 (#203)

*2026-3-20 16:44*

666

## 回复 by mb_abajbief (#204)

*2026-3-21 10:17*

7

## 回复 by mb_criqjxad (#205)

*2026-3-21 22:28*

666

## 回复 by 飆汗吉米 (#206)

*2026-3-21 23:04*

666

## 回复 by Leaveret (#207)

*2026-3-23 01:02*

111

## 回复 by 水瓶 (#208)

*2026-3-23 15:58*

666666

## 回复 by Atop0s. (#209)

*2026-3-23 16:02*

mark

## 回复 by 木槿any (#210)

*2026-3-23 17:50*

666

## 回复 by MikotoDev (#211)

*2026-3-26 03:07*

666

## 回复 by Sigil (#212)

*2026-3-26 11:57*

1

## 回复 by 土豆爱学习 (#213)

*2026-4-2 10:06*

>
> [lazybulazy](https://bbs.kanxue.com/user-1000319.htm)
>  佬，想请教一下第一种绕过方法找libmsaoaidsec.so 内部偏移函数的时候，运行脚本出现这种情况是怎么回事呀，程序卡在启动界面，so加载情况一直显示的是libart.so
>

hook pthread_create要加过滤啊，libart.so会频繁调用pthread_create啊，直接hook肯定白屏啊。去看文章 https://xz.aliyun.com/news/15622更加详细。

## 回复 by 土豆爱学习 (#214)

*2026-4-2 10:08*

>
> [mb_rxlldkxh](https://bbs.kanxue.com/user-909786.htm)
>  楼主，我根据你的贴子，尝试hook伊对app的libmsaoaidsec.so，没hook成功，一直没打印出pthread_create地址
> └─# frida -U -f me.yidui -l ...
>

hook pthread_create要加过滤啊，libart.so会频繁调用pthread_create啊，直接hook肯定白屏啊。去看文章 https://xz.aliyun.com/news/15622更加详细。

## 回复 by 土豆爱学习 (#215)

*2026-4-2 10:22*

我发现一个问题，作者A写一篇文章，然后作者B拿着他的文章换一个demo就是一篇新文章，然后作者C参考作者B，依此类推。并且也不带上参考文章地址，并且关键思路和信息还越写越少。

论坛关于hook pthread_create定位被检测位置和libmsaoaidsec.so的原始思路来自于两年前，
地址如下，有兴趣的可以看看,原始思路和更加清晰的过程，

ps都2年了libmsaoaidsec.so的三个检测函数的偏移地址没变，他们的安全人员躺平了不更新了？

https://xz.aliyun.com/news/15622
http://www.yxfzedu.com/article/8993
https://bbs.kanxue.com/thread-277034-1.htm

估计上面这些文章也是参考的某个文章的，为什么难以找到文章的源头，
难道宇宙的尽头就是搬运(((φ(◎ロ◎;)φ)))。

## 回复 by 尹少欣 (#216)

*2026-4-6 06:33*

666

## 回复 by 小迷糊ddd (#217)

*2026-4-7 09:16*

感谢分享，学习一下。

## 回复 by 外交 (#218)

*2026-4-11 15:19*

666

## 回复 by dark_stars (#219)

*2026-4-11 20:13*

666

## 回复 by wx_Deity (#220)

*2026-4-11 21:01*

666

## 回复 by 乌鸡哥 (#221)

*2026-4-12 00:44*

666

## 回复 by mb_yyvcbkli (#222)

*2026-4-14 19:46*

学习一下先进经验

## 回复 by mb_jszirmbz (#223)

*2026-4-15 00:23*

666

## 回复 by mb_kuqpxncc (#224)

*2026-4-16 14:29*

666

## 回复 by mb_xpplzptm (#225)

*2026-4-17 12:55*

66666

## 回复 by 我就夸你 (#226)

*2026-4-17 14:46*

666

## 回复 by wx_窒息 (#227)

*2026-4-17 17:51*

666

## 回复 by mb_dcyjtaqk (#228)

*2026-4-18 21:03*

感谢分享!!!

## 回复 by mb_tasadicv (#229)

*2026-4-21 10:54*

666

## 回复 by mb_vhnlcxac (#230)

*2026-4-21 22:28*

666

## 回复 by ldehua (#231)

*2026-4-23 11:46*

666

## 回复 by mb_yeeclamm (#232)

*2026-4-28 15:28*

1

## 回复 by mb_yeeclamm (#233)

*2026-4-28 15:28*

1

## 回复 by mb_dsvrufqa (#234)

*2026-4-28 16:37*

6666666

## 回复 by mb_dsvrufqa (#235)

*2026-4-28 16:37*

6666666

## 回复 by mb_ugnawvja (#236)

*2026-4-29 10:28*

感谢分享！

## 回复 by mb_ugnawvja (#237)

*2026-4-29 10:28*

感谢！

## 回复 by git_86585flowclouds (#238)

*2026-4-30 01:12*

真的很好

## 回复 by mb_klyhhlcc (#239)

*2026-5-1 07:38*

66

## 回复 by mb_kylehnha (#240)

*2026-5-3 21:04*

好东西

## 回复 by fancy繁星 (#241)

*2026-5-8 16:10*

666

## 回复 by mb_pmgifpme (#242)

*2026-5-10 13:07*

1

## 回复 by 真挖不出来洞 (#243)

*2026-5-11 14:15*

牛逼

## 回复 by ilanlanya (#244)

*2026-5-11 14:52*

666

## 回复 by 小若渴jh (#245)

*2026-5-15 03:02*

66666

## 回复 by mb_kuhxsjlt (#246)

*2026-5-15 16:44*

6

## 回复 by cpluse (#247)

*2026-5-16 20:38*

感谢分享

## 回复 by mb_gtzlnffr (#248)

*2026-5-19 10:37*

666

## 回复 by 段誉 (#249)

*2026-5-19 16:26*

666

## 回复 by wx_！_336 (#250)

*2026-5-19 21:28*

666

## 回复 by 海带 (#251)

*2026-5-21 14:41*

666

## 回复 by wx_完美 (#252)

*2026-5-22 19:02*

谢谢分享

## 回复 by mb_vrrlkian (#253)

*2026-5-26 23:21*

6666

## 回复 by 大笨钟 (#254)

*2026-5-27 14:07*

666

## 回复 by chqi (#255)

*2026-5-27 18:25*

666

## 回复 by haris4687 (#256)

*2026-5-27 21:33*

66

## 回复 by 简单的简单 (#257)

*2026-5-27 22:40*

666

## 回复 by LuisY (#258)

*2026-5-28 10:15*

6

## 回复 by mb_eybtgvvs (#259)

*2026-5-28 10:20*

666

## 回复 by mb_ugnawvja (#260)

*2026-5-28 10:22*

666

## 回复 by mb_lhxrckiu (#261)

*2026-5-28 14:34*

看看

## 回复 by mb_ybflwzfa (#262)

*2026-5-28 15:48*

666

## 回复 by mb_ugnzmwel (#263)

*2026-5-28 16:14*

666

## 回复 by wx_技术Liu (#264)

*2026-5-29 22:44*

6666

## 回复 by 新手入门% (#265)

*2026-5-30 10:37*

1

## 回复 by 番茄丶 (#266)

*2026-5-30 12:57*

66666

## 回复 by yaoqianshuj (#267)

*2026-5-30 15:10*

666

## 回复 by GoKu123 (#268)

*2026-5-31 15:12*

666

## 回复 by Tanuyoki0 (#269)

*2026-5-31 20:21*

66666666666

## 回复 by git_74197luban110 (#270)

*2026-6-1 16:52*

666

## 回复 by tigericon (#271)

*2026-6-2 14:07*

66

## 回复 by 一栋奥特曼 (#272)

*2026-6-2 17:11*

666

## 回复 by Mirikkas (#273)

*2026-6-3 01:17*

66666

## 回复 by snowflake911 (#274)

*2026-6-3 15:38*

666

## 回复 by mb_uuqpavws (#275)

*2026-6-4 13:15*

6666

## 回复 by mb_elytixax (#276)

*2026-6-4 14:02*

感谢分享

## 回复 by mb_pqvukyfl (#277)

*2026-6-5 10:02*

666

## 回复 by Arcue1d (#278)

*2026-6-7 11:16*

666

## 回复 by git_87237minhdanhsc (#279)

*2026-6-8 00:03*

1

## 回复 by yangshuang (#280)

*2026-6-8 10:49*

666

## 回复 by mb_wgjydnix (#281)

*2026-6-8 11:42*

666

## 回复 by mb_kbagkani (#282)

*2026-6-8 15:08*

666

## 回复 by mb_awqgymxv (#283)

*2026-6-10 19:21*

666

## 回复 by mb_awqgymxv (#284)

*2026-6-10 19:21*

侦测脚本

## 回复 by mb_awqgymxv (#285)

*2026-6-10 19:23*

注入侦测脚本  frida -U -f  报名 -l detect.js 提示  TypeError: not a function
    at <anonymous> (G:\xxx\scripts\detect.js:14)
    at <eval> (G:\xxxx\scripts\detect.js:44)

## 回复 by 五彩斑斓的黑 (#286)

*2026-6-10 23:18*

666

## 回复 by mb_lrzszndq (#287)

*2026-6-14 20:41*

666

## 回复 by 鱼鱼鱼鱼鱼 (#288)

*2026-6-16 10:49*

大佬6666

## 回复 by mb_xjdhrmck (#289)

*2026-6-16 11:11*

66666

## 回复 by mb_cewrbxyv (#290)

*2026-6-19 04:26*

热舞太过温柔头发

## 回复 by 4ak5ra (#291)

*2026-6-21 15:43*

666

## 回复 by mb_rooofjxx (#292)

*2026-6-22 10:24*

666

## 回复 by 小李08 (#293)

*2026-6-23 11:31*

666

## 回复 by wx_coddvccwyh (#294)

*2026-6-24 00:30*

6666

## 回复 by Gypsophilazj (#295)

*2026-6-26 16:43*

666

## 回复 by 量凉 (#296)

*2026-6-28 08:28*

666

## 回复 by 逆向小龙 (#297)

*2026-6-30 16:19*

111

## 回复 by mb_zfnetraa (#298)

*2026-7-2 02:04*

666

## 回复 by mb_fuiuugpi (#299)

*2026-7-3 01:23*

666

## 回复 by mb_kgneopde (#300)

*2026-7-6 15:21*

666

## 回复 by mb_zurizkle (#301)

*2026-7-7 18:18*

不不不

## 回复 by mb_dmkmqsyg (#302)

*2026-7-7 20:57*

1

## 回复 by wx_Riham、 (#303)

*2026-7-10 12:59*

666

## 回复 by wx_寻_333 (#304)

*2026-7-14 23:04*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_cezdpjbw (#305)

*2026-7-16 11:37*

666

## 回复 by wx_杨杰_424 (#306)

*2026-7-17 08:10*

tql

## 回复 by mb_nuomemmo (#307)

*2026-7-18 16:00*

这篇技术分析非常详细，展示了Frida在反调试检测中的强大应用。通过HOOK系统函数和分析SO库加载过程，成功定位并绕过了反调试机制，这种思路值得学习。结合Sophos的研究，AI在恶意软件开发中的

## 回复 by mb_qkfqehfw (#308)

*2026-7-19 03:04*

666

## 回复 by 祝今朝 (#309)

*2026-7-19 19:53*

666

## 回复 by mb_odnnlwif (#310)

*2026-7-20 22:03*

666

## 回复 by mb_rxgpbdxs (#311)

*2026-7-22 15:36*

1

## 回复 by mb_bnjbcdzy (#312)

*2026-7-22 16:02*

这条技术分析非常深入，点赞！通过Hook系统函数巧妙绕过检测，体现了开发者对底层机制的深刻理解。同时，文中提到的框架进化方向也很有启发，未来的技术选型或许将更多由工具而非人工决定。继续探索AI与开发

## 回复 by mb_oxqwhbqt (#313)

这篇文章详细地分析了如何利用Frida检测和绕过反调试机制，内容非常实用。通过HOOK系统函数和监控SO库的加载过程，作者成功定位了反调试的源头，并提出了具体的绕过方法。这种技术不仅展示了Frida

## 回复 by mb_vcuiorbn (#314)

666

## 回复 by GeQ1an (#315)

666

## 回复 by 酱爆 (#316)

666

## 回复 by mb_cylxfmot (#317)

666

## 回复 by mb_cylxfmot (#318)

666

## 回复 by mb_gjhmacqd (#319)

666

## 回复 by mb_akzdpbgl (#320)

感谢分享

## 回复 by mb_ysikfhxt (#321)

123
