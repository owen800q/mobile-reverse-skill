---
title: '[原创]深入浅出 Android Hook 技术：Frida 框架入门系列'
url: https://bbs.kanxue.com/thread-289346.htm
tid: 289346
author: xiusi
date: '2025-12-06'
tags: [Android安全, 原创, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T15:23:27+08:00'
replies: 84
---

# 深入浅出 Android Hook 技术：Frida 框架入门系列

## 一、Hook 框架概述

**Hook** 是一种在程序运行时动态修改或拦截函数调用、参数或返回值的技术。在 Android 安全研究、逆向分析以及自动化测试中，Hook 技术扮演着至关重要的角色。

### 核心应用场景

- **拦截应用逻辑**：获取或修改关键数据（如加密密钥、用户输入）。
- **监控函数调用流程**：分析 App 的运行轨迹和内部逻辑。
- **动态修改程序行为**：实现功能调试、绕过安全限制（如 Root 检测、SSL Pinning）。

### 主流框架对比

目前 Android 生态中主要有两种主流的 Hook 框架：

| 框架名称 | 特点 | 适用场景 |
|-|-|-|
| **Xposed** | 需要刷机或安装虚拟机，修改系统层级，Hook 修改重启后依然生效。 | 适用于开发模块、系统定制、用户级持久化功能增强。 |
| **Frida** | 基于 Python + JavaScript，跨平台，支持动态注入，无需重启设备。 | **首选工具**。适用于逆向分析、安全测试、算法还原、快速验证逻辑。 |

本篇文章将重点介绍在安卓逆向中最常用的 **Frida 框架**，带你完成从环境搭建到基本命令的使用。

---

## 二、Frida 框架的安装

Frida 的工作模式是 **C/S 架构**（客户端/服务端），因此安装过程分为两部分：

1. **PC 客户端**：`frida` (Python 库) —— 负责编写脚本、发送指令并接收 Hook 结果。
2. **Android 服务端**：`frida-server` —— 运行在手机端，负责接收 PC 端指令并执行 Hook 注入。

### 1. PC 端安装 Frida

确保电脑已安装 Python 环境，直接使用 `pip` 命令安装：

| 12345 | `# 安装 frida 核心库``pip` `install` `frida` `# 安装 frida 命令行工具 (提供了 frida-ps, frida-ls-devices 等命令)``pip` `install` `frida-tools` |
|-|-|

**指定版本安装（推荐）：**
为了保证稳定性，建议 PC 端和手机端保持版本一致。如果需要安装特定版本（例如 16.7.14）：

| 12 | `pip` `install` `frida==16.7.14``pip` `install` `frida-tools==12.3.0` |
|-|-|

*注：**`frida-tools`* *的版本通常会自动匹配，如非必要可不指定。*

---

### 2. Android 端安装 frida-server

#### 第一步：确定设备架构

在下载服务端之前，必须知道你的 Android 设备 CPU 架构。连接手机（确保已开启 USB 调试），输入以下命令：

| 1 | `adb shell getprop ro.product.cpu.abi` |
|-|-|

- 输出 `arm64-v8a`：请下载 **arm64** 版本（目前主流真机）。
- 输出 `armeabi-v7a`：请下载 **arm** 版本（旧手机）。
- 输出 `x86` 或 `x86_64`：请下载对应版本（常见于模拟器）。

#### 第二步：下载对应版本的 frida-server

前往官方 GitHub 发布页：[Frida Releases](https://www.google.com/url?q=https%3A%2F%2Fgithub.com%2Ffrida%2Ffrida%2Freleases)

**下载原则**：

1. **版本一致**：必须与电脑端 `frida --version` 显示的版本一致。
2. **架构匹配**：根据上一步查询的 ABI 选择。

>
> **示例场景**：
>
>
> - PC 环境：Python 3.9.13
> - Frida 版本：16.7.14
> - 设备：真机 (arm64)
>
>
> **下载文件**：`frida-server-16.7.14-android-arm64.xz`
>
>
> ![image](https://bbs.kanxue.com/upload/attach/202512/1036360_6TD549STJP6GJ5T.png)
>
>
>

#### 第三步：安装与运行

下载完成后解压得到 `frida-server-16.7.14-android-arm64` 文件，按照以下步骤操作：

**1. 推送到手机临时目录**
`/data/local/tmp/` 是安卓系统中用于存放临时文件的标准目录，且允许执行二进制文件。

| 1 | `adb push frida-server-16.7.14-android-arm64` `/data/local/tmp/` |
|-|-|

**2. 进入手机 Shell 并提权**
Frida 服务端必须以 Root 权限运行。

| 12 | `adb shell``su` |
|-|-|

**3. 赋予执行权限并运行**
建议在命令末尾添加 `&` 符号，使其在后台运行，防止关闭终端窗口后服务停止。

| 12345 | `cd` `/data/local/tmp``chmod` `+x frida-server-16.7.14-android-arm64` `# 启动服务（& 表示后台挂起）``.``/frida-server-16``.7.14-android-arm64 &` |
|-|-|

>
> **提示**：如果此时终端没有报错且光标闪烁或返回新的一行，说明启动成功。
>
>
>

---

#### 第四步：设置端口转发（Port Forwarding）

为了让电脑端的 Frida 客户端（Python/CLI）能通过 USB 与手机端的 frida-server 通信，需要建立端口映射。

**方式一：使用默认端口（推荐）**
Frida 默认使用 `27042` 端口进行通信。如果是标准启动（即上一步中直接运行），只需执行：

| 123 | `# 将电脑的 27042 端口转发到手机的 27042 端口``adb forward tcp:27042 tcp:27042``adb forward tcp:27043 tcp:27043` |
|-|-|

**方式二：使用自定义端口（非标端口）**
如果默认端口被占用，或者为了规避针对默认端口的检测，可以指定非标准端口（例如 `8888`）。

1. **手机端启动时指定端口**：
 在**第三步**运行 frida-server 时，需要修改启动命令，监听指定地址和端口：

| 12 | `# 格式：./frida-server -l 监听地址:端口``.``/frida-server-16``.7.14-android-arm64 -l 0.0.0.0:8888 &` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202512/1036360_QWNHY9BVTG2U9P8.png)
2. **电脑端设置端口转发**：

| 12 | `# 将电脑的 8888 端口转发到手机的 8888 端口``adb forward tcp:8888 tcp:8888` |
|-|-|
3. **客户端连接指定**：
 后续使用 frida 命令时，需要通过 `-H` 参数指定地址（或者通过 `-D` 指定设备），若仅通过 USB 转发，通常客户端会自动识别，或需指定 host：

| 1234 | `# 示例：连接到本地转发的端口``frida -H 127.0.0.1:8888 -l hook.js -f com.example.target``或``frida -H 127.0.0.1:8888 -l hook.js` `"Target App Name"` |
|-|-|

#### 进阶技巧：规避简单检测

为了方便输入命令，同时规避部分 App 针对 "frida-server" 文件名的简单字符串检测，建议重命名：

| 12 | `# 重命名为 fs``mv` `frida-server-16.7.14-android-arm64 fs` |
|-|-|

---

## 三、Frida 常用命令速查

环境搭建完成后，可以使用以下命令来测试连接状态或执行 Hook 任务。

### 1. 设备连接与进程查看

| 命令 | 说明 |
|-|-|
| `frida-ls-devices` | 列出电脑连接的所有设备（检查 USB 连接是否正常）。 |
| `frida-ps -U` | USB 模式。列出当前连接的 Android 设备上正在运行的进程。 |
| `frida-ps -Uai` | 列出设备上所有**已安装**的应用（包括未运行的），显示包名和应用名。 |
| `frida-ps -D <device_id>` | 连接指定 ID 的设备（当多设备连接时使用）。 |

### 2. Hook 脚本注入模式

Frida 主要有两种注入模式：**Spawn（重启/冷启动）** 和 **Attach（附加/热注入）** 。

#### 1. Spawn 模式 (冷启动)

**适用场景**：App 启动阶段就有检测（如 Root 检测、模拟器检测），或者需要 Hook 启动时才执行的逻辑（如 `Application.onCreate()`、早期 Native 初始化）。
**原理**：Frida 会自动启动（重启）App，并在 App 真正启动前将脚本注入。

- **关键参数**：`-f <Package Name>`
- **标识符**：必须使用 **包名**

| 12 | `# 格式：frida -U -l 脚本路径 -f 包名``frida -U -l script.js -f com.example.target` |
|-|-|

#### 2. Attach 模式 (热注入)

**适用场景**：App 已经在运行中，需要中途介入分析逻辑，或者为了规避针对启动注入的检测。
**原理**：Frida 附加到当前正在运行的进程上，不会重启 App。

- **关键参数**：无 `-f` 参数
- **标识符**：可以使用 **进程名** (App Name) 或 **PID**

| 123 | `# 格式：frida -U -l 脚本路径 <进程名/PID>``# 注意：这里通常填写 App 的名称（Process Name），而非包名``frida -U -l script.js` `"Target App Name"` |
|-|-|

---

#### 如何获取 包名、进程名 或 PID？

在执行注入前，我们需要准确找到目标的标识符。可以使用 `frida-ps` 配合过滤命令查找。

**1. 查找包名 (Package Name) - 用于 Spawn 模式**
列出设备上安装的所有应用：

| 12 | `# -ai 表示列出已安装(installed)的应用详情``frida-``ps` `-Uai` |
|-|-|

**2. 查找进程名 (Name) 或 PID - 用于 Attach 模式**
列出当前正在运行的进程，并进行关键词过滤：

- **Linux / macOS 用户** (使用 `grep`)：

| 1 | `frida-``ps` `-U \|` `grep` `"com.example.target"` |
|-|-|
- **Windows 用户** (使用 `findstr`)：

| 1 | `frida-``ps` `-U \| findstr` `"com.example.target"` |
|-|-|

### 3. 远程连接

如果使用 WiFi 调试或远程调试（需在手机端启动 frida-server 时指定监听端口）：

| 1234 | `# 连接到指定 IP 和端口``frida -H 192.168.1.100:8888 -l script.js -f com.example.target``或``frida -H 192.168.1.100:8888 -l script.js` `"Target App Name"` |
|-|-|

---

## 四、Java 层 Hook

### 1. 基本框架

在 Frida 中，所有的 Java 层 Hook 操作都必须被包裹在 `Java.perform` 中执行。这是因为 Frida 的 JavaScript 脚本运行在独立的线程中，若要访问 Android 应用的 Java 虚拟机（VM）环境，必须显式地将当前线程附加到 VM 上。

#### 基本模板

| 12345678910111213141516171819202122232425 | `Java.perform(``function` `() {``// 1. 获取目标类 (Java.use 对应 Java 的 Class.forName)``var` `TargetClass = Java.use(``"com.example.demo.MainActivity"``);` `// 2. 覆写目标方法 (implementation)``TargetClass.targetMethod.implementation =` `function` `(arg1, arg2) {` `// [可选] 打印参数``console.log(``"[*] Hook targetMethod, args: "` `+ arg1 +` `", "` `+ arg2);` `// [可选] 修改参数``var` `newArg1 =` `"Hacked"``;` `// 3. 调用原方法 (非常重要，否则原逻辑会被截断)``// 使用 this.targetMethod 调用原逻辑``var` `result =` `this``.targetMethod(newArg1, arg2);` `// [可选] 修改返回值``console.log(``"[*] Original result: "` `+ result);``return` `result;``};` `// 3. 修改目标字段 (field)``TargetClass.field.value = new_field;``});` |
|-|-|

#### 核心 API 详解

- **`Java.perform(fn)`** ：
Frida 的入口函数。它确保当前线程已附加到 Android 的 Java VM，只有在这里面才能调用 `Java.use` 等 API。

>
> **注意**：所有的 Hook 逻辑都应包含在回调函数 `fn` 中。
>
>
>
- **`Java.use(className)`** ：
动态获取一个 Java 类的引用（类似反射中的获取 Class 对象）。

	- **参数**：完整的类名（包名 + 类名），例如 `"android.util.Log"`。
	- **返回**：一个 JavaScript 包装对象，通过它可以访问该类的静态变量、方法，或实例化对象。
- **`implementation`**：
这是实现 Hook 的关键属性。通过给某个方法的 `implementation` 赋值一个 JavaScript 函数，从而**替换**掉原有的 Java 方法逻辑。

	- **参数**：函数的参数应与原 Java 方法参数一一对应。
	- **`this`** **上下文**：在函数内部，`this` 指向当前的类实例（Instance）。若 Hook 的是静态方法，`this` 指向类对象。

#### 执行时机与防报错处理

在某些特殊场景下（如脚本注入过早、类尚未加载），直接运行可能会报错。我们可以使用定时器来延迟执行。

**1. 使用** **`setImmediate`** **(推荐)**
用于确保在当前 JS 事件循环结束后立即执行，常用于防止阻塞主线程或处理某些特定的栈问题。

| 1234567 | `// 立即执行``setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Script Loaded immediately."``);``// Hook 逻辑...``});``});` |
|-|-|

>
> 不要让 setImmediate 位于代码的第一行，可能会被 Frida 的 REPL 误解析成命令而报以下错误：
>
>
>
>
> | 12 | `Error: could not parse` `'E:\Work_Space\hook.js'` `line 1: expecting field name``at <anonymous> (``/frida/repl-2``.js:1)` |
> |-|-|
>
>
>

**2. 使用** **`setTimeout`** **(延时执行)**
适用于应用启动初期类还未加载（ClassNotFoundException）的情况，或者为了避开某些早期的检测逻辑。

| 1234567 | `// 延迟 500 毫秒执行``setTimeout(``function``() {``Java.perform(``function``() {``console.log(``"[*] Script Loaded after 500ms."``);``// Hook 逻辑...``});``}, 500);` |
|-|-|

### 2. Hook 普通方法

普通方法通常指的是类中的**实例方法**（非静态方法）。在 Hook 这类方法时，我们需要注意保留或者合理利用 `this` 指针，因为它代表了当前对象的实例。

我们以 **Frida-Labs 0x1** 为例进行演示。

靶场地址：[github.com/DERE-ad2001/Frida-Labs](https://github.com/DERE-ad2001/Frida-Labs)

#### 目标分析

查看反编译后的 Java 源代码，我们发现关键逻辑位于 `MainActivity` 的 `check` 方法中：

| 12345678910 | `// 目标类：com.ad2001.frida0x1.MainActivity``void` `check(``int` `i,` `int` `i2) {``// 关键判断逻辑：如果 (i * 2) + 4 等于 i2，则猜测正确``if` `((i *` `2``) +` `4` `== i2) {``Toast.makeText(getApplicationContext(),` `"Yey you guessed it right"``,` `1``).show();``// ... 获取 Flag 的后续逻辑``}` `else` `{``Toast.makeText(getApplicationContext(),` `"Try again"``,` `1``).show();``}``}` |
|-|-|

**分析**：想要触发 "Yey you guessed it right" 的分支，传入的参数必须满足 `(i * 2) + 4 == i2`。虽然我们可以通过计算输入正确的值（例如输入 0 和 4），但在逆向中，更直接的方法是 **Hook 该方法并篡改参数**，无论用户在 UI 输入什么，强制让传入逻辑的参数满足等式。

#### Hook 脚本编写

我们的策略是：拦截 `check` 方法，将参数强制修改为一组满足条件的固定值（例如 `i=0, i2=4`），然后将修改后的参数传递给原方法执行。

| 1234567891011121314151617181920212223242526 | `setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Hook Script..."``);` `// 1. 获取目标类的引用``let MainActivity = Java.use(``"com.ad2001.frida0x1.MainActivity"``);` `// 2. 覆写 check 方法``// 注意：普通方法的 implementation 函数，第一个参数不用写 this，this 依然指向当前实例``MainActivity[``"check"``].implementation =` `function` `(i, i2) {``console.log(`[*] Original args: i=${i}, i2=${i2}`);` `// 3. 篡改参数``// 我们构造一组满足 (i * 2) + 4 == i2 的值``// 0 * 2 + 4 = 4``i = 0;``i2 = 4;``console.log(`[*] Tampered args: i=${i}, i2=${i2}`);` `// 4. 调用原方法``// 使用 this["methodName"](args) 调用原始实现``// 这样应用原本的判断逻辑会使用我们要修改后的参数运行``this``[``"check"``](i, i2);``};``});``});` |
|-|-|

#### 运行结果

运行脚本后，在 App 输入框中随意输入任意数字，点击提交按钮，成功通过校验，获取到 Flag。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_DYHGNHEC35QXDUH.png)

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_PV67268N7YCR664.png)

>
> 在 JavaScript 中调用原方法时，既可以使用 `this.check(i, i2)` 也可以使用 `this["check"](i, i2)`。
> 推荐使用 **方括号** **`[]`**  **写法**，因为当混淆后的方法名包含特殊字符（如 `$`, `-`）或关键字时，点号写法可能会报错。
>
>
>

### 3. Hook 静态方法

静态方法（`static`）与普通实例方法的区别在于：**静态方法属于类本身，而不属于类的某个具体实例**。这意味着在 Frida 中，我们无需获取类的实例对象（即不需要 `this`），直接通过 `Java.use` 获取的类引用即可进行 Hook 或调用。

我们以 **Frida-Labs 0x2** 为例，展示如何**主动调用**一个静态方法。

#### 目标分析

分析反编译后的 Java 代码：

| 123456789101112131415161718 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``static` `TextView f103t1;` `public` `void` `onCreate(Bundle savedInstanceState) {``super``.onCreate(savedInstanceState);``setContentView(C0569R.layout.activity_main);``// 初始化 UI，但并没有调用 get_flag``f103t1 = (TextView) findViewById(C0569R.C0572id.textview);``}` `// 关键的静态方法，包含获取 Flag 的逻辑``public` `static` `void` `get_flag(``int` `a) {``if` `(a ==` `4919``) {``// ... 解密并显示 Flag``f103t1.setText(``"FLAG is here..."``);` `}``}``}` |
|-|-|

**分析**：

1. 目标方法 `get_flag` 是 `static` 的。
2. **关键问题**：在 `onCreate` 生命周期中，App 并没有主动调用 `get_flag`。
3. **策略**：如果我们仅仅写一个 `implementation` 去拦截它，由于 App 自身不执行该方法，Hook 永远不会被触发。因此，我们需要利用 Frida 的能力，**主动调用 (Invoke)** 该静态方法，并传入正确的参数 `4919`。

#### Hook 脚本编写

对于静态方法，`Java.use` 返回的对象可以直接点出方法名进行调用。

| 1234567891011121314 | `setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Active Call Script..."``);` `// 1. 获取类引用``let MainActivity = Java.use(``"com.ad2001.frida0x2.MainActivity"``);` `// 2. 主动调用静态方法``// 静态方法不需要实例，直接通过类包装器调用``// 传入代码中要求的参数 4919``console.log(``"[*] Calling MainActivity.get_flag(4919)..."``);``MainActivity[``"get_flag"``](4919);``});``});` |
|-|-|

#### 运行结果

脚本运行后，无需任何用户交互，Frida 会立即执行该函数，App 界面上的 TextView 随即更新显示 Flag。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_GAGKT2BTBAGZFXX.png)

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_QERYF7PY3T8FA6H.png)

>
> **核心总结**
>
>
> - **修改逻辑**：如果要拦截已有调用并修改参数/返回值，使用 `Class.method.implementation = function(...) { ... }`。
> - **主动触发**：如果方法未被调用，直接使用 `Class.method(...)` 进行执行。静态方法可直接调用，普通方法则需先获取实例（`Java.choose`）。
>
>
>

### 4. Hook 静态字段

在 Frida 中，对字段（Field）的操作与方法（Method）不同。我们不能像拦截方法那样去 "Hook" 一个字段的读取或写入动作（虽然通过 Setter/Getter 可以间接实现），通常的操作是**直接获取或修改字段的值**。

我们以 **Frida-Labs 0x3** 为例。

#### 目标分析

反编译应用，找到校验逻辑所在的 `MainActivity` 和数据类 `Checker`：

| 1234567891011121314151617 | `// 1. 校验逻辑 (MainActivity.java)``public` `void` `onClick(View v) {``// 关键判断：检查 Checker 类的静态变量 code 是否等于 512``if` `(Checker.code ==` `512``) {``Toast.makeText(MainActivity.``this``.getApplicationContext(),` `"YOU WON!!!"``,` `1``).show();``// ... 获取 Flag``}` `else` `{``Toast.makeText(MainActivity.``this``.getApplicationContext(),` `"TRY AGAIN"``,` `1``).show();``}``}` `// 2. 数据定义 (Checker.java)``public` `class` `Checker {``// 默认值为 0``static` `int` `code =` `0``;` `// ...``}` |
|-|-|

**分析**：
`Checker.code` 默认初始化为 0。点击按钮时，逻辑直接判断它是否为 512。我们无需拦截 `onClick`，只需要在点击之前，将 `Checker.code` 的内存值修改为 `512` 即可。

#### Hook 脚本编写

在 Frida 中，通过 `Java.use` 获取到的类对象，可以直接访问其静态字段。
**注意**：访问字段值时，必须使用 `.value` 属性。如果直接打印 `Checker.code`，得到的是一个 Frida 的字段包装对象（Field Object），而不是具体的值。

| 12345678910111213141516 | `setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Field Modification Script..."``);` `// 1. 获取类引用``let Checker = Java.use(``"com.ad2001.frida0x3.Checker"``);` `// 2. 修改静态字段的值``// 语法：Class.fieldName.value = newValue``console.log(``"[*] Original code value: "` `+ Checker.code.value);` `Checker.code.value = 512;` `console.log(``"[*] Modified code value: "` `+ Checker.code.value);``});``});` |
|-|-|

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_XBANV6QJMPJ996P.png)

### 5. Hook 无实例非静态方法

在之前的案例中，我们处理的要么是**静态方法**（直接通过类调用），要么是**已运行的实例方法**（通过拦截获取 `this`）。但有时我们会遇到一种特殊情况：
目标方法是**非静态**的（Instance Method），且 App 当前的运行流程中**并没有创建该类的实例**。此时，为了执行该方法，我们需要在 Frida 脚本中手动创建一个该类的实例对象。

我们以 **Frida-Labs 0x4** 为例。

#### 目标分析

| 123456789101112131415161718 | `// 1. 主界面 (MainActivity.java)``public` `void` `onCreate(Bundle savedInstanceState) {``// 仅初始化了 UI，并没有引用或实例化 Check 类``super``.onCreate(savedInstanceState);``// ...``}` `// 2. 目标类 (Check.java)``public` `class` `Check {``// 这是一个普通的实例方法（非 static）``public` `String get_flag(``int` `a) {``if` `(a ==` `1337``) {``// ... 返回 Flag 字符串``return` `"FLAG{...}"``;` `}``return` `""``;``}``}` |
|-|-|

**分析**：

1. `get_flag` 是普通方法，必须通过 `new Check()` 创建的对象来调用。
2. `MainActivity` 中没有实例化 `Check` 类，意味着我们在内存中找不到现成的对象（无法使用 `Java.choose`）。
3. **策略**：使用 Frida 的 `$new()` 方法手动调用 `Check` 类的构造函数，创建一个新对象，然后调用该对象的方法。

#### Hook 脚本编写

| 12345678910111213141516171819202122 | `setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Instance Creation Script..."``);` `// 1. 获取类引用``let CheckClass = Java.use(``"com.ad2001.frida0x4.Check"``);` `// 2. 实例化对象 (相当于 Java 中的 new Check())``// $new() 是 Frida 提供的特殊方法，用于调用类的构造函数``let checkInstance = CheckClass.$``new``();``console.log(``"[*] Check instance created: "` `+ checkInstance);` `// 3. 主动调用实例方法``// 传入要求的参数 1337``let flag = checkInstance.get_flag(1337);` `// 4. 输出结果``console.log(`[*] Check.get_flag result: ${flag}`);` `// [可选] 将结果显示在控制台或回写到 App UI（如果有对应 Hook 点）``});``});` |
|-|-|

#### 运行结果

脚本执行后，Frida 在目标进程的内存中成功创建了一个 `Check` 对象，并调用了其 `get_flag` 方法。由于参数正确（1337），方法返回了 Flag 字符串并在控制台打印出来。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_2PT5JXGJT69SJ8Q.png)

### 6. Hook 实例

在前面的案例中，我们通过 `$new()` 创建了一个全新的对象。但在 Android 开发中，很多类（如 `Activity`, `Service`）是由系统管理的，如果我们自己 `new` 一个 Activity，它不仅无法控制当前的 UI，还可能导致应用崩溃。

**场景**：我们需要调用当前**正在运行的**某个页面（Activity）中的方法，或者获取当前内存中某个单例对象的状态。
**方法**：使用 `Java.choose` 在内存堆（Heap）中扫描并获取已存在的对象实例。

我们以 **Frida-Labs 0x5** 为例。

#### 目标分析

| 12345678910111213141516 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``TextView f103t1;` `// 标准的 Activity 生命周期``public` `void` `onCreate(Bundle savedInstanceState) {``super``.onCreate(savedInstanceState);``// ...``}` `// 目标方法：是一个实例方法``public` `void` `flag(``int` `code) {``if` `(code ==` `1337``) {``// ... 更新 UI 显示 Flag``}``}``}` |
|-|-|

**分析**：

1. `flag` 是实例方法，需要对象调用。
2. `MainActivity` 是一个 Activity，当前正在手机屏幕上显示。
3. **策略**：不能 `new MainActivity()`。我们需要深入内存，找到当前那个“活着的” `MainActivity` 实例，然后控制它去执行 `flag(1337)`。

#### Hook 脚本编写

使用 `Java.choose` API 进行内存搜索。

 **注意时机**：
这里建议使用 `setTimeout` 而非 `setImmediate`。
因为在 Spawn（冷启动）模式下，Frida 脚本注入极快，此时 `MainActivity` 可能还没来得及完成初始化（即还未进入堆内存）。延迟 500ms~1000ms 可以确保 Activity 已经创建完毕，从而避免搜索落空。

| 123456789101112131415161718192021222324252627 | `setTimeout(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Memory Scan..."``);` `// 动态在堆内存中搜索指定类的实例``Java.choose(``"com.ad2001.frida0x5.MainActivity"``, {` `// 【回调1】每找到一个实例，就会调用一次 onMatch``// instance 参数即为找到的 Java 对象（类似于 this）``onMatch:` `function` `(instance) {``console.log(``"[*] Found instance: "` `+ instance);` `// 主动调用实例方法``instance.flag(1337);` `// 优化：如果只想找一个实例（通常 Activity 只有一个），``// 可以返回 "stop" 停止后续搜索，减少开销``// return "stop";` `},` `// 【回调2】搜索全部完成后调用``onComplete:` `function` `() {``console.log(``"[*] Memory Scan Complete."``);``}``});``});``}, 1000);` `// 延迟 1 秒等待 UI 加载` |
|-|-|

#### API 详解：Java.choose(className, callbacks)

- **`className`**：需要搜索的类名（字符串）。
- **`callbacks`**：一个包含两个回调函数的对象：

	- **`onMatch(instance)`** ：

		- 核心函数。Frida 会遍历堆，每发现一个该类的实例，就执行一次此函数。
		- `instance`：捕获到的对象句柄，可直接调用其方法或访问字段。
		- 返回值：如果在函数末尾 `return "stop"`，Frida 会立即停止搜索（适用于单例或只关心第一个结果的场景）。
	- **`onComplete()`** ：

		- 当内存扫描彻底结束时调用。无论是否找到实例，最后都会执行，常用于清理工作或打印结束日志。

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_E8DYFMEMJMVVFDM.png)

### 7. Hook 含有对象参数的方法

在实际逆向中，目标方法的参数往往不是简单的 `int` 或 `String`，而是自定义的类对象（Object）。为了调用这类方法，我们需要在脚本中**手动构造一个符合要求的对象实例**作为参数传入。

这是一个综合性的案例，结合了 **Section 5 (对象实例化)** 和 **Section 6 (内存实例查找)** 的技巧。我们以 **Frida-Labs 0x6** 为例。

#### 目标分析

| 1234567891011121314151617181920 | `// 1. 主 Activity (MainActivity.java)``public` `class` `MainActivity` `extends` `AppCompatActivity {``// ...` `// 目标方法：``// 1. 是实例方法（需要找到 MainActivity 实例）``// 2. 参数是 Checker 类型的对象 A（需要构造 Checker 实例）``public` `void` `get_flag(Checker A) {``// 校验逻辑：检查传入对象的两个成员变量``if` `(``1234` `== A.num1 &&` `4321` `== A.num2) {``// ... 成功获取 Flag``}``}``}` `// 2. 参数类 (Checker.java)``public` `class` `Checker {``int` `num1;``int` `num2;``}` |
|-|-|

**分析**：

1. **调用者**：`get_flag` 存在于 `MainActivity` 中，且正在运行，因此需要用 `Java.choose` 获取 `MainActivity` 的实例。
2. **参数**：方法签名要求传入一个 `Checker` 对象。我们需要使用 `$new()` 创建这个对象。
3. **数据构造**：创建 `Checker` 对象后，必须将其成员变量 `num1` 和 `num2` 分别赋值为 `1234` 和 `4321`，才能通过校验。

#### Hook 脚本编写

脚本逻辑流程：等待 App 加载 -> 搜索 `MainActivity` 实例 -> 创建并配置 `Checker` 参数对象 -> 主动调用。

| 1234567891011121314151617181920212223242526272829303132 | `setTimeout(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Starting Complex Call Script..."``);` `// 1. 搜索宿主实例 (MainActivity)``Java.choose(``"com.ad2001.frida0x6.MainActivity"``, {``onMatch:` `function` `(instance) {``console.log(``"[*] Found Host instance: "` `+ instance);` `// 2. 准备参数类 (Checker)``let CheckerClass = Java.use(``"com.ad2001.frida0x6.Checker"``);` `// 3. 实例化参数对象``let checkerObj = CheckerClass.$``new``();` `// 4. 配置参数对象的字段值``// 注意：访问字段必须用 .value``console.log(``"[*] Configuring Checker object..."``);``checkerObj.num1.value = 1234;``checkerObj.num2.value = 4321;` `// 5. 主动调用目标方法，传入构造好的对象``console.log(``"[*] Invoking get_flag..."``);``instance[``"get_flag"``](checkerObj);``},` `onComplete:` `function` `() {``console.log(``"[*] Memory Scan Complete."``);``}``});``});``}, 1000);` `// 延迟 1 秒确保 Activity 已加载` |
|-|-|

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_DUBTCNE6GBT6AG2.png)

### 8. Hook 构造方法

构造方法（Constructor）在 Android 逆向中是一个非常重要的 Hook 点。在 Frida 中，构造方法在 JavaScript 层面被映射为  **`$init`**。

我们以 **Frida-Labs 0x7** 为例。

#### 目标分析

| 1234567891011121314151617181920212223242526272829 | `// 1. 调用处 (MainActivity.java)``public` `void` `onCreate(Bundle savedInstanceState) {``// ...``// 创建 Checker 实例，传入初始值 (123, 321)``Checker ch =` `new` `Checker(``123``,` `321``);` `try` `{``// 将实例传入 flag 方法进行校验``flag(ch);` `}` `catch` `(Exception e) { ... }``}` `// 2. 校验处 (MainActivity.java)``public` `void` `flag(Checker A) {``// 校验逻辑：两个成员变量都必须大于 512``if` `(A.num1 >` `512` `&&` `512` `< A.num2) {``// ... 获取 Flag``}``}` `// 3. 数据类 (Checker.java)``public` `class` `Checker {``int` `num1;``int` `num2;``// 构造方法``public` `Checker(``int` `a,` `int` `b) {``this``.num1 = a;``this``.num2 = b;``}``}` |
|-|-|

**分析**：
`Checker` 被初始化为 (123, 321)，不满足 `> 512` 的条件。想要通过校验，我们有两种截然不同的思路：

1. **拦截校验点 (****`flag`** **)** ：在检查前，把参数对象替换成一个合格的新对象。
2. **拦截生成源 (****`Checker`** **构造器)** ：在对象创建时，直接篡改传入的初始参数。

---

#### 思路一：Hook 校验方法 (替换参数对象)

这种方法比较“暴力”，直接在 `flag` 方法执行前，创建一个满足条件的新 `Checker` 对象，并替换掉原本的参数 `A`。

- **优点**：只会影响 `flag` 方法的执行，不会污染整个 App 中其他创建 `Checker` 的地方（作用域小，风险低）。
- **缺点**：需要手动构造对象，代码稍繁琐。

| 1234567891011121314151617 | `setImmediate(``function` `() {``Java.perform(``function` `() {``let MainActivity = Java.use(``"com.ad2001.frida0x7.MainActivity"``);` `MainActivity[``"flag"``].implementation =` `function` `(A) {``console.log(`[*] Hooked flag method. Original args: ${A}`);` `// 1. 创建一个新的“合格”对象``let Checker = Java.use(``"com.ad2001.frida0x7.Checker"``);``let newChecker = Checker.$``new``(999, 999);` `// 传入 > 512 的值` `// 2. 偷梁换柱：将参数 A 替换为 newChecker``// 3. 调用原方法，此时传入的是我们伪造的对象``this``[``"flag"``](newChecker);``};``});``});` |
|-|-|

---

#### 思路二：Hook 构造方法 (推荐 - 修改初始化参数)

这是本节的重点。我们直接 Hook `Checker` 类的构造方法（`$init`）。当 App 尝试用 (123, 321) 去 new 对象时，我们强制将其修改为 (999, 999)。

- **优点**：代码简洁，直击源头。
- **缺点**：如果 App 中很多地方都用到了这个类，所有的实例都会被修改（全局影响）。

**关键点**：Frida 中 hook 构造方法必须使用 `$init` 关键字。

| 12345678910111213141516171819 | `setImmediate(``function` `() {``Java.perform(``function` `() {``let Checker = Java.use(``"com.ad2001.frida0x7.Checker"``);` `// Hook 构造方法使用 $init``Checker[``"$init"``].implementation =` `function` `(a, b) {``console.log(`[*] Checker.$init called` `with``: a=${a}, b=${b}`);` `// 1. 篡改参数``a = 999;``b = 999;``console.log(`[*] Tampered arguments to: a=${a}, b=${b}`);` `// 2. 调用原始构造方法进行初始化``// 这里的 this 指向正在被创建的对象实例``this``[``"$init"``](a, b);``};``});``});` |
|-|-|

#### 运行结果

脚本运行后，App 在初始化 `Checker` 时参数被修改，随后 `flag` 方法校验通过，Flag 显示。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_BF5T8UPQPNR7Q5B.png)

>
> **进阶提示：处理重载**
> 如果构造方法有多个（例如 `Checker()` 和 `Checker(int a)`），Frida 可能会提示模糊匹配错误。此时需要使用 `overload` 指明参数签名：
>
>
>
>
> | 1 | `Checker[``"$init"``].overload(``'int'``,` `'int'``).implementation =` `function``(a, b) { ... }` |
> |-|-|
>
>
>

### 9. Hook 重载方法

在 Java 中，允许存在多个同名方法，只要它们的参数列表（参数个数或类型）不同，这就是 **方法重载 (Overloading)** 。

当我们要 Hook 一个存在重载的方法时，如果直接使用 `implementation`，Frida 无法确定你到底想 Hook 哪一个版本，从而抛出 "ambiguous"（歧义）错误。此时，必须使用 **`.overload()`** 明确指定参数签名。

#### 目标分析

我们编写一个简单的 Demo `Challenge4Activity`，其中包含两个名为 `check` 的方法：

| 12345678910111213 | `public` `class` `Challenge4Activity` `extends` `AppCompatActivity {``// ... UI 绑定逻辑 ...` `// 重载版本 1：接收 String 类型``private` `void` `check(String str) {``Toast.makeText(``this``,` `"String版: "` `+ str,` `0``).show();``}` `// 重载版本 2：接收 int 类型``private` `void` `check(``int` `i) {``Toast.makeText(``this``,` `"Int版: "` `+ i,` `0``).show();``}``}` |
|-|-|

**分析**：
虽然方法名都是 `check`，但在 Smali/Bytecode 层面它们的签名是完全不同的。

- `check(String)` -> 参数类型为 `java.lang.String`
- `check(int)` -> 参数类型为 `int`

#### Hook 脚本编写

使用 `.overload('Type1', 'Type2', ...)` 来指定目标方法的参数类型。

**签名书写规则**：

1. **基本数据类型**：直接写名称（如 `'int'`, `'boolean'`, `'float'`）。
2. **引用类型 (对象)** ：必须写**完整的类名路径**（如 `'java.lang.String'`, `'android.os.Bundle'`）。
3. **数组**：遵循 JNI 签名格式或使用 `[类型`（如 `'[B'` 代表字节数组，或者 `'[Ljava.lang.String;'`）。

| 1234567891011121314151617181920 | `setImmediate(``function` `() {``Java.perform(``function` `() {``let Challenge4Activity = Java.use(``"com.xiusi.fridastudy.Challenge4Activity"``);` `// 1. Hook 接收 String 参数的 check 方法``// 注意：String 是类，必须写全称 java.lang.String``Challenge4Activity[``"check"``].overload(``'java.lang.String'``).implementation =` `function` `(str) {``console.log(`[*] Hooked check(String), value=${str}`);``// 修改参数并调用原方法``this``[``"check"``](``"Hacked String"``);``};` `// 2. Hook 接收 int 参数的 check 方法``// 注意：int 是基本类型，直接写 'int'``Challenge4Activity[``"check"``].overload(``'int'``).implementation =` `function` `(i) {``console.log(`[*] Hooked check(int), value=${i}`);``this``[``"check"``](99999);``};``});``});` |
|-|-|

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_DBWTP5N54DR72GZ.png)

>
>  **实用技巧：不知道签名怎么办？**
> 如果你不确定重载的签名该怎么写（比如是一个复杂的自定义类数组），可以故意不写 `.overload()` 或者乱写一个 `.overload()`。
> 运行脚本时，**Frida 会报错，并在错误信息中列出该方法所有可用的 overload 签名**。直接把报错信息里正确的签名复制出来即可！
>
>
> *报错示例：*
>
>
> ![image](https://bbs.kanxue.com/upload/attach/202512/1036360_KGQ5JKP4PV2ZJEJ.png)
>
>
>

---

## 五、Native 层 Hook

Native 层 Hook 主要针对 Android 中的 **C/C++ 代码**（通常编译为 `.so` 动态链接库）。与 Java 层不同，这里操作的是内存地址、寄存器和汇编指令。Frida 提供了强大的 `Interceptor` API 来实现这一层面的拦截。

### 1. 基本框架

Native Hook 的核心是通过 `Module` 找到函数的内存地址，然后利用 `Interceptor.attach` 挂钩该地址。

由于 Native 库（.so 文件）通常是在 App 运行时动态加载的，建议使用 `setTimeout` 延迟执行，或拦截 `System.loadLibrary` 来确保目标 so 已加载。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `function` `hookNative() {``// 1. 获取目标函数的内存地址``// 参数1: so名称 (如 "libc.so"), 参数2: 导出函数名 (如 "strcmp")``// 如果不知道 so 名称，参数1 可传 null，但这会全盘扫描，效率较低``var` `funcPtr = Module.findExportByName(``"libc.so"``,` `"strcmp"``);` `console.log(``"[*] Target function address: "` `+ funcPtr);` `if` `(funcPtr) {``// 2. 附加拦截器``Interceptor.attach(funcPtr, {` `// 【进入函数前调用】``// args: 参数数组，args[0] 代表第1个参数，args[1] 代表第2个参数...``// 注意：args 中的元素都是 NativePointer 对象（指针）``onEnter:` `function` `(args) {``console.log(``"[*] onEnter strcmp"``);` `// 读取参数内容``// 假设 strcmp(const char *s1, const char *s2)``// 使用 Memory.readUtf8String 读取指针指向的字符串``var` `str1 = Memory.readUtf8String(args[0]);``var` `str2 = Memory.readUtf8String(args[1]);` `console.log(`    s1: ${str1}, s2: ${str2}`);` `// [可选] 修改参数``// 这种修改仅在本次调用生效``// this.context.x0 = ... (ARM64 寄存器操作)``},` `// 【函数返回后调用】``// retval: 返回值指针 (NativePointer)``onLeave:` `function` `(retval) {``console.log(``"[*] onLeave, retval: "` `+ retval);` `// [可选] 修改返回值``// 将返回值修改为 0 (表示两字符串相等)``// retval.replace(0);` `}``});``}` `else` `{``console.log(``"[-] Function not found!"``);``}``}` `setImmediate(``function` `() {``// Java.perform 在这里主要用于将当前线程附加到 VM，防止某些 JNI 操作崩溃``// 如果是纯 Native Hook，不涉及 JNI 调用，也可以不写 Java.perform``Java.perform(``function` `() {``var` `Runtime = Java.use(``"java.lang.Runtime"``);``Runtime.loadLibrary0.overload(``'java.lang.Class'``,` `'java.lang.String'``).implementation =` `function` `(loader, libname) {``console.log(``"[*] Loading:"``, libname);``var` `ret =` `this``.loadLibrary0(loader, libname);``if` `(libname.includes(``"libc.so"``)) {``console.log(``"[*] 目标库已加载！"``, libname);``hookNative();``}``return` `ret;``};``});``});` |
|-|-|

#### 核心 API 详解

**Interceptor.attach(target, callbacks**)

这是 Native Hook 的核心函数。

- **`target`**：要 Hook 的函数在内存中的绝对地址（`NativePointer`）。
- **`callbacks`**：包含 `onEnter` 和 `onLeave` 两个回调函数的对象。

**回调函数详解：**

- **`onEnter: function (args)`**

	- 函数执行**前**被调用。
	- **`args`**：一个数组，包含传递给函数的参数。

		- `args[0]`, `args[1]`... 分别对应 C 函数的第 1、2... 个参数。
		- **注意**：它们都是指针（Pointer）。如果是整数，需用 `.toInt32()` 转换；如果是字符串指针，需用 `Memory.readUtf8String(args[x])` 读取。
	- **`this.context`**：访问 CPU 寄存器上下文（如 `this.context.x0` 在 ARM64 中通常存放第一个参数或返回值）。
- **`onLeave: function (retval)`**

	- 函数执行**后**被调用。
	- **`retval`**：包含函数的返回值（NativePointer）。
	- **`retval.replace(val)`** ：用于篡改返回值。例如 `retval.replace(1)` 强制返回 1。

---

#### Module 类常用 API

`Module` 类主要用于操作加载到进程中的动态链接库（SO 文件），是定位 Hook 地址的第一步。

| API 方法 | 说明 | 适用场景 |
|-|-|-|
| **`Module.findExportByName(name, exp)`** | 查找导出函数的绝对地址。找不到返回`null`。 | **最常用**。Hook 系统函数（如`libc.so`的`open`）或 App 明确导出的 JNI 函数。 |
| **`Module.getExportByName(name, exp)`** | 查找导出函数的绝对地址。找不到**抛出异常**。 | 确定函数一定存在时使用，用于脚本的强依赖检查。 |
| **`Module.getBaseAddress(name)`** | 获取指定 SO 在内存中的**基址**。 | **关键**。Hook**未导出函数**（Sub_xxx）。公式：`绝对地址 = 基址 + 偏移(IDA)` |
| **`Module.enumerateExports(name, cb)`** | 枚举指定 SO 的所有**导出**符号。 | 寻找目标函数名，或模糊搜索特定的导出函数。 |
| **`Module.enumerateImports(name, cb)`** | 枚举指定 SO 的所有**导入**符号。 | 分析该 SO 调用了哪些外部函数（如`fopen`,`ssl_write`）。 |

---

#### (内存读写)常用 API

在 Native Hook 中，`args[n]` 得到的仅仅是 `内存地址（指针）` 。要获取指针指向的实际数据（如字符串内容、整数值、结构体数据），必须使用 `Memory` 类的方法进行读取；若要修改数据，则使用对应的 `write` 方法。

| API 方法 | 说明 | 典型示例 |
|-|-|-|
| `Memory.readUtf8String(ptr)` | 读取指针处的 UTF-8 字符串。常用于读取 `char*` 类型参数。 | `var str = Memory.readUtf8String(args[0]);` |
| `Memory.writeUtf8String(ptr, str)` | 将字符串写入指定地址。**⚠️ 慎用**：必须确保目标缓冲区有足够的空间，否则会造成内存溢出崩溃。 | `Memory.writeUtf8String(args[0], "hack");` |
| `Memory.readInt(ptr)` | 读取地址处的 4 字节整数 (int)。 | `var val = Memory.readInt(args[1]);` |
| `Memory.writeInt(ptr, value)` | 将整数写入指定地址。常用于修改标志位或计数器。 | `Memory.writeInt(args[1], 1337);` |
| `Memory.readByteArray(ptr, len)` | 读取指定长度的字节数组。常用于查看结构体、加密后的二进制流。 | `var buf = Memory.readByteArray(args[2], 16);` |
| `hexdump(ptr, options)` | 调试神器。以十六进制 + ASCII 形式打印内存块，便于观察未知数据结构。 | `console.log(hexdump(args[0], { length: 64 }));` |

**示例：综合使用内存读写**

| 12345678910111213141516171819202122 | `Interceptor.attach(targetAddr, {``onEnter:` `function` `(args) {``// 1. 读取字符串参数``var` `strArg = Memory.readUtf8String(args[0]);` `// 2. 读取整数指针参数 (int *count)``var` `count = Memory.readInt(args[1]);` `console.log(`[*] args[0]=${strArg}, *args[1]=${count}`);` `// 3. 修改内存中的整数值``Memory.writeInt(args[1], 9999);` `// 4. 打印内存 Dump 查看更多细节``console.log(hexdump(args[0], {``offset: 0,``length: 32,``header:` `true``,``ansi:` `true``}));``}``});` |
|-|-|

| 参数 | 含义 |
|-|-|
| **offset** | dump 时相对基地址的偏移（字节） |
| **length** | dump 的字节数 |
| **header** | 是否显示地址头部信息 |
| **ansi** | 是否使用彩色输出（ANSI Color） |

---

#### 常用 Native 辅助脚本

在逆向初期，我们往往不知道具体的函数名或 SO 加载情况，以下脚本非常实用。

##### 脚本 A：枚举所有已加载的 SO 库

用于查看目标 SO 是否已加载，以及获取其基址。

| 1234567891011121314151617181920212223242526272829 | `setImmediate(``function` `() {``console.log(``"[*] Enumerating modules..."``);` `// 打印表头``console.log(``"Module Name"``.padEnd(40) +``"Base Address"``.padEnd(20) +``"Size"``);``console.log(``"-"``.repeat(90));` `Process.enumerateModules({``onMatch:` `function` `(module) {``let name = (module.name \|\|` `""``).toString();``let base = module.base ? module.base.toString() :` `"N/A"``;``let size = module.size ? module.size.toString() :` `"N/A"``;` `console.log(``name.padEnd(40) +``base.padEnd(20) +``size``);``},``onComplete:` `function` `() {``console.log(``"-"``.repeat(90));``console.log(``"[*] Module enumeration complete"``);``}``});``});` |
|-|-|

##### 脚本 B：枚举指定 SO 的所有导出函数

用于查找目标函数在内存中的偏移或确切名称（特别是在存在混淆或 C++ Name Mangling 时）。

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `setImmediate(``function` `() {``var` `targetSo =` `"libfrida0xa.so"``;``console.log(``"[*] Enumerating exports of "` `+ targetSo +` `"..."``);` `var` `module = Process.findModuleByName(targetSo);` `if` `(module) {` `// 打印表头``console.log(``"Name"``.padEnd(40) +``"Address"``.padEnd(20) +``"Type"``);``console.log(``"-"``.repeat(80));` `Module.enumerateExports(targetSo, {``onMatch:` `function` `(exp) {``let name = (exp.name \|\|` `""``).toString();``let addr = exp.address ? exp.address.toString() :` `"N/A"``;``let type = (exp.type \|\|` `""``).toString();` `// 对打印进行过滤（可选）``if` `(name.includes(``""``)) {``console.log(``name.padEnd(40) +``addr.padEnd(20) +``type``);``}``},``onComplete:` `function` `() {``console.log(``"-"``.repeat(80));``console.log(``"[*] Export enumeration complete"``);``}``});` `}` `else` `{``console.log(``"[-] Module "` `+ targetSo +` `" not found!"``);``}``});` |
|-|-|

##### 脚本 C：枚举指定 SO 的所有导入函数

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `setImmediate(``function` `() {``var` `targetSo =` `"libfrida0xa.so"``;``console.log(``"[*] Enumerating imports of "` `+ targetSo +` `"..."``);` `var` `module = Process.findModuleByName(targetSo);` `if` `(module) {``// 打印表头``console.log(``"Name"``.padEnd(40) +``"Address"``.padEnd(20) +``"Type"``.padEnd(12) +``"From Module"``);``console.log(``"-"``.repeat(90));` `Module.enumerateImports(targetSo, {``onMatch:` `function` `(imp) {``// 处理可能为 undefined 的字段``let name = (imp.name \|\|` `""``).toString();``let addr = imp.address ? imp.address.toString() :` `"N/A"``;``let type = (imp.type \|\|` `""``).toString();``let from = (imp.module \|\|` `""``).toString();` `if` `(name.includes(``""``)) {``console.log(``name.padEnd(40) +``addr.padEnd(20) +``type.padEnd(12) +``from``);``}``},``onComplete:` `function` `() {``console.log(``"-"``.repeat(90));``console.log(``"[*] Import enumeration complete"``);``}``});` `}` `else` `{``console.log(``"[-] Module "` `+ targetSo +` `" not found!"``);``}``});` |
|-|-|

### 2. Hook 有符号函数

所谓“有符号函数”，指的是在动态链接库的导出表（Export Table）中能找到名字的函数。这通常包括：

1. **系统库函数**：如 `libc.so` 中的 `open`, `read`, `strcmp`。
2. **JNI 导出函数**：Java Native Interface 的标准命名函数，格式通常为 `Java_包名_类名_方法名`。

我们以 **Frida-Labs 0x8** 为例。

#### 目标分析

| 1234567891011121314151617 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``// 声明 Native 方法``public` `native` `int` `cmpstr(String str);` `// 加载 so 库``static` `{``System.loadLibrary(``"frida0x8"``);``}` `public` `void` `onClick(View v) {``// 调用 native 方法进行校验``int` `res = MainActivity.``this``.cmpstr(ip);``if` `(res ==` `1``) {``// ... 成功``}``}``}` |
|-|-|

**分析**：

1. 关键逻辑位于 Native 层。将 `libfrida0x8.so` 拖入 IDA 分析，发现 `cmpstr` 对应的 Native 实现是 `Java_com_ad2001_frida0x8_MainActivity_cmpstr`。
2. **核心逻辑**：

| 123456 | `// 伪代码``// 生成比较字符串 s2``for` `(i = 0; i < len; ++i) s2[i] = encrypted[i] - 1;``// 使用 strcmp 比较用户输入 (input) 和 flag (s2)``v4 =` `strcmp``(input, s2);``return` `v4 == 0;` |
|-|-|
3. **策略**：由于最终校验调用了标准的 C 库函数 `strcmp`，我们可以直接 Hook `libc.so` 中的 `strcmp`。当我们的输入字符串与 Flag 进行比较时，Flag 必然会作为 `strcmp` 的另一个参数出现。

#### Hook 脚本编写

**关键点：处理 SO 加载时机**
由于我们 Hook 的是 `libc.so` 的函数（它是系统库，启动即加载），理论上可以直接 Hook。
但为了演示更通用的 Native Hook 流程（针对 App 自带的 so），我们采用 **“监听加载”** 的策略：Hook `java.lang.Runtime.loadLibrary0`，监控目标 SO 何时被加载。一旦检测到目标 SO 加载完毕，立即执行 Native Hook 逻辑。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `// 定义核心 Hook 逻辑``function` `hookNative() {``// 1. 获取 strcmp 函数地址``// libc.so 是系统库，通常始终存在``var` `strcmp_ptr = Module.findExportByName(``"libc.so"``,` `"strcmp"``);``console.log(``"[*] strcmp address: "` `+ strcmp_ptr);` `// 2. 附加拦截器``Interceptor.attach(strcmp_ptr, {``onEnter:` `function` `(args) {``// args[0] = s1 (用户输入), args[1] = s2 (Flag)` `// 读取参数字符串``var` `str1 = Memory.readUtf8String(args[0]);``var` `str2 = Memory.readUtf8String(args[1]);` `// 3. 过滤噪声``// 系统中调用 strcmp 的地方非常多，不加过滤会刷屏卡死``// 我们约定：在 App 输入框中输入特定的特征词 "666"，只拦截包含该特征词的调用``if` `(str1 && str1.includes(``"666"``)) {``console.log(``"\n[+] Detected strcmp call!"``);``console.log(``"    Input: "` `+ str1);``console.log(``"    Flag candidate: "` `+ str2);``}``},``onLeave:` `function` `(retval) {}``});``}` `setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Hooking System.loadLibrary..."``);` `// Hook Runtime.loadLibrary0 以监听 SO 加载``var` `Runtime = Java.use(``"java.lang.Runtime"``);``Runtime.loadLibrary0.overload(``'java.lang.Class'``,` `'java.lang.String'``).implementation =` `function` `(loader, libname) {` `// 调用原始方法加载库``var` `ret =` `this``.loadLibrary0(loader, libname);` `// 检查是否是我们关注的库``if` `(libname.includes(``"frida0x8"``)) {``console.log(`[*] Target library loaded: ${libname}`);``// 目标库加载后，执行 Native Hook``hookNative();``}``return` `ret;``};``});``});` |
|-|-|

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_9WMB34MJYF5YSPD.png)

>
> - **为什么过滤？** `strcmp` 是极其常用的底层函数，每秒可能被调用成百上千次。如果不加 `if (input.includes(...))` 过滤，日志瞬间就会被淹没，甚至导致 App 卡顿崩溃。
> - **为什么 Hook loadLibrary0？** 虽然本例直接 Hook `libc` 也可以，但养成“先监听加载，再 Hook”的习惯对于处理 App 自有的 so（非系统库）至关重要，因为在 so 未加载前，你是找不到其内部函数地址的。
>
>
>

### 3. Hook 函数返回值

在 Native 层 Hook 中，除了查看参数，最常见的需求就是**修改函数的返回值**。比如绕过某些布尔类型的校验函数（返回 `true`/`false`），或者修改计算结果。这需要在 `onLeave` 回调中进行操作。

我们以 **Frida-Labs 0x9** 为例。

#### 目标分析

**Java 层代码**：

| 123456789101112131415161718 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``// 定义 Native 方法``public` `native` `int` `check_flag();` `// 加载 so``static` `{``System.loadLibrary(``"a0x9"``);``}` `public` `void` `onClick(View v) {``// 校验逻辑：如果 native 方法返回 1337，则通过``if` `(MainActivity.``this``.check_flag() ==` `1337``) {``Toast.makeText(...,` `"Correct"``, ...).show();``}` `else` `{``Toast.makeText(...,` `"Try again"``, ...).show();``}``}``}` |
|-|-|

**Native 层代码 (伪代码)** ：
使用 IDA 打开 `liba0x9.so`，查看导出函数 `Java_com_ad2001_a0x9_MainActivity_check_1flag`：

| 12345 | `// 真正的逻辑非常简单，直接返回 1``__int64` `Java_com_ad2001_a0x9_MainActivity_check_1flag()``{``return` `1LL;``}` |
|-|-|

**分析**：
Native 函数固定返回 `1`，但 Java 层要求返回 `1337` 才能成功。
显然，我们无法通过修改输入参数来改变结果（因为它没有参数）。我们必须拦截该函数执行完毕后的**返回动作**，强行将返回值从 `1` 修改为 `1337`。

#### Hook 脚本编写

使用 `Interceptor.attach` 的 **`onLeave`** 回调。

- **`retval`**：代表函数的返回值对象（NativePointer）。
- **`retval.replace(value)`** ：将返回值替换为指定的值（可以是整数，也可以是新的指针地址）。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `// 核心 Hook 逻辑``function` `hookNative() {``// 1. 查找导出函数地址``// 注意：JNI 函数名中的特殊字符会被转义，例如 "_" 变为 "_1"``var` `funcName =` `"Java_com_ad2001_a0x9_MainActivity_check_1flag"``;``var` `check_ptr = Module.findExportByName(``"liba0x9.so"``, funcName);` `console.log(``"[*] Target function address: "` `+ check_ptr);` `if` `(check_ptr) {``Interceptor.attach(check_ptr, {``// 函数进入时，无需操作``onEnter:` `function` `(args) {},` `// 函数即将返回时调用``onLeave:` `function` `(retval) {``// 2. 打印原始返回值``console.log(``"[*] Original return value: "` `+ retval.toInt32());` `// 3. 篡改返回值``// 将返回值强制修改为 1337``retval.replace(1337);` `console.log(``"[+] Modified return value to: 1337"``);``}``});``}` `else` `{``console.log(``"[-] Function not found. Check the export name."``);``}``}` `// 监听 SO 加载逻辑 (标准模版)``setImmediate(``function` `() {``Java.perform(``function` `() {``console.log(``"[*] Hooking System.loadLibrary..."``);``var` `Runtime = Java.use(``"java.lang.Runtime"``);` `Runtime.loadLibrary0.overload(``'java.lang.Class'``,` `'java.lang.String'``).implementation =` `function` `(loader, libname) {``var` `ret =` `this``.loadLibrary0(loader, libname);` `// 确保是目标 so 加载后再 hook``if` `(libname.includes(``"a0x9"``)) {``console.log(`[*] Target library loaded: ${libname}`);``hookNative();``}``return` `ret;``};``});``});` |
|-|-|

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_DSZ742F5N8MHXQ7.png)

>
> ** 技巧提示**
>
>
> - **replace 指针**：如果返回值是一个指针（例如 `char*` 或 `struct*`），也可以使用 `ptr("0x12345678")` 来构造一个新的地址并传给 `retval.replace()`。
> - **JNI 命名陷阱**：在 `Module.findExportByName` 时，务必注意 JNI 的名字修饰规则。如果找不到函数，建议先用 `Module.enumerateExports` 打印出来看看真正的名字是什么。
>
>
>

### 4. Hook 调用有符号函数

在逆向分析中，我们经常会发现一些**隐藏的函数**。它们存在于 SO 库中，包含了关键逻辑（如解密 Flag、生成 Token），但在 App 的正常运行流程中从未被调用，或者触发条件极难满足。

此时，我们需要利用 Frida 的 `NativeFunction` API，将这些内存地址“包装”成 JavaScript 函数，从而实现**主动调用**。

我们以 **Frida-Labs 0xA** 为例。

#### 目标分析

**1. Java 层分析**

| 1234567891011121314 | `public` `final` `class` `MainActivity` `extends` `AppCompatActivity {``// 加载 library``static` `{``System.loadLibrary(``"frida0xa"``);``}` `// 定义了一个 native 方法``public` `final` `native` `String stringFromJNI();` `public` `void` `onCreate(Bundle savedInstanceState) {``// 调用 stringFromJNI 并显示``activityMainBinding.sampleText.setText(stringFromJNI());``}``}` |
|-|-|

**2. Native 层分析**
通过 IDA 分析 `stringFromJNI`，发现它只是返回了一个普通的字符串，并没有 Flag。
但在导出表中，我们发现了一个可疑的函数 **`get_flag`**，虽然它在 Java 层没有被声明，也没有被调用。

| 12345678910111213 | `// get_flag 伪代码``// 接收两个参数：result, a2``__int64` `__fastcall get_flag(``int` `result,` `int` `a2)``{``// 关键判断：如果两个参数之和等于 3``if` `( result + a2 == 3 )``{``// ... 解密逻辑 ...``// 将 Flag 打印到 Logcat 中 (tag: FLAG)``result = __android_log_print(3,` `"FLAG"``,` `"Decrypted Flag: %s"``, decrypted_flag);``}``return` `result;``}` |
|-|-|

**分析**：

- 目标函数：`get_flag`。
- 触发条件：传入两个整数，使其和为 3（例如 `1 + 2`）。
- 输出方式：Flag 不会通过返回值返回，而是打印在系统日志中。

#### 获取函数符号 (Name Mangling)

由于该函数是 C 编写的，编译器会对函数名进行**修饰 (Name Mangling)** 以支持重载等特性。直接搜 `get_flag` 可能找不到，我们需要找到它在导出表中的“真实名字”。

使用 `Module.enumerateExports` 脚本查看：

| 12345 | `[*] Enumerating exports of libfrida0xa.so...``Name            Address             Type``----------------------------------------``_Z8get_flagii   0x732cc66d60        function``...` |
|-|-|

 **`_Z8get_flagii`** 就是我们要找的真实符号名（`_Z` 开头，`8` 是长度，`ii` 代表两个 `int` 参数）。

当然也可以直接在 IDA 中的反汇编界面进行查看：

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_Y2C82RZMCB2XN94.png)

#### Hook 脚本编写

使用 `NativeFunction` 将地址转换为函数并调用。

| 12345678910111213141516171819202122232425262728 | `function` `invokeNative() {``// 1. 获取目标函数的内存地址``// 使用修饰后的完整符号名``var` `funcPtr = Module.findExportByName(``"libfrida0xa.so"``,` `"_Z8get_flagii"``);` `if` `(!funcPtr) {``console.log(``"[-] Function not found!"``);``return``;``}``console.log(``"[*] get_flag address: "` `+ funcPtr);` `// 2. 定义 Native 函数原型 (关键步骤)``// 格式: new NativeFunction(address, returnType, argTypes[])``// get_flag 返回值是 long (__int64), 参数是两个 int``var` `get_flag =` `new` `NativeFunction(funcPtr,` `'long'``, [``'int'``,` `'int'``]);` `// 3. 主动调用``// 传入参数 1 和 2，满足 1+2=3 的条件``console.log(``"[*] Invoking get_flag(1, 2)..."``);``get_flag(1, 2);``}` `// 延迟执行，确保 SO 已加载``setTimeout(``function` `() {``Java.perform(``function` `() {``invokeNative();``});``}, 1000);` |
|-|-|

#### API 详解：NativeFunction

`new NativeFunction(address, returnType, argTypes[, abi])`

- **`address`**：函数的内存地址 (NativePointer)。

>
> `address` 参数是 `pointer` 类型（`Module.findExportByName()` 的返回值就是 `pointer` 类型），如果这里传的是 `number` 类型，需要如下转换：
>
>
>
>
> | 123 | `address =` `new` `NativePointer(address);``// 或者``address = ptr(address);` |
> |-|-|
>
>
>
- **`returnType`**：返回值的类型（字符串）。
- **`argTypes`**：参数类型列表（字符串数组）。
- **支持类型**：

	- `void`
	- `pointer` (对应 C 指针)
	- `int`, `uint`, `long`, `ulong`
	- `char`, `uchar`
	- `float`, `double`

#### 运行结果

脚本运行后，Frida 主动执行了该函数。由于函数内部调用了 `__android_log_print`，我们需要去 **Logcat** 查看结果，这里使用的是 `Android Studio` 的日志查看功能。

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_AR85TE6WG5NFSN2.png)

### 5. Hook 无符号函数

在生产环境中，为了防止逆向分析，开发者通常会去除 SO 库中的符号表（Strip）。此时，函数名会变成类似 `sub_151C0` 这样的无意义名称，我们无法通过 `findExportByName` 直接找到它。

在这种情况下，我们需要采用 **“基址 + 偏移”** 的策略进行定位。
**公式**：`目标函数绝对地址 = SO 库在内存中的基址 + 函数在文件中的偏移量`

我们继续以 **Frida-Labs 0xA** 为例，假设 `get_flag` 函数的符号已被去除。

#### 偏移获取

使用 IDA Pro 或 Ghidra 打开 `libfrida0xa.so`，跳转到目标函数。

```
.text:000000000001DD60 ; __int64 __fastcall get_flag(...)
.text:000000000001DD60 EXPORT _Z8get_flagii
.text:000000000001DD60 _Z8get_flagii
```

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_UZHFYTX69S375A5.png)

观察左侧地址栏，可以看到该函数相对于文件头的偏移量为 **`0x1DD60`**。

#### Hook 脚本编写

在编写脚本时，我们需要先获取 SO 的基址，然后加上偏移。

**关键点：Thumb 模式 (+1 问题)**
在 **32位 ARM** 架构下，指令集分为 ARM（4字节对齐）和 Thumb（2字节对齐）。如果目标函数是 Thumb 指令集，其地址的最低位（LSB）必须为 1。

- **64位 (ARM64)** ：不需要处理，直接相加。
- **32位 (ARM)** ：如果 IDA 中显示的偏移是偶数，但函数实际上是 Thumb 指令（大部分 Android 32位 SO 都是 Thumb），需要在偏移地址上  **+1**。

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `function` `hookNative() {``// 1. 获取 SO 库的内存基址``var` `moduleName =` `"libfrida0xa.so"``;``var` `baseAddr = Module.findBaseAddress(moduleName);` `if` `(!baseAddr) {``console.log(``"[-] Module not found: "` `+ moduleName);``return``;``}``console.log(``"[*] Module Base Address: "` `+ baseAddr);` `// 2. 计算目标函数绝对地址``var` `offset = 0x1dd60;` `// IDA 中看到的偏移` `// 处理 Thumb 模式 (仅针对 32 位 ARM)``// 这里的逻辑是：如果是 32 位 ARM 架构，我们通常默认尝试 +1 (Thumb模式)``// 或者可以通过 Process.arch === 'arm' 来判断``var` `targetAddr = baseAddr.add(offset);` `/*` `// 如果是在 32 位 ARM 设备上，且函数是 Thumb 指令集：``if (Process.arch === 'arm') {``targetAddr = targetAddr.add(1);``}``*/` `console.log(``"[*] Calculated Function Address: "` `+ targetAddr);` `// 3. 将地址转换为 NativeFunction 进行调用``// 定义原型：返回值 long, 参数 (int, int)``var` `get_flag =` `new` `NativeFunction(targetAddr,` `'long'``, [``'int'``,` `'int'``]);` `console.log(``"[*] Invoking sub_1DD60(1, 2)..."``);``get_flag(1, 2);``}` `setTimeout(``function` `() {``Java.perform(``function` `() {``hookNative();``});``}, 1000);` |
|-|-|

#### API 详解

- **`Module.findBaseAddress(name)`**

	- 获取指定加载模块（SO 库）在内存中的起始地址。
	- 返回：`NativePointer` 对象；如果未找到模块，则返回 `null`。
- **`NativePointer.add(offset)`**

	- 指针运算。返回一个新的指针对象，其地址为原地址加上偏移量。
	- 注意：支持十六进制字符串（如 `.add("0x10")`）或整数。

#### 运行结果

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_AR85TE6WG5NFSN2.png)

### 6. 修改汇编指令 (Code Patching)

在某些场景下，单纯的 Hook（拦截）已经无法满足需求。例如：

1. 函数内部有死循环或反调试检测。
2. 关键判断逻辑位于函数中间，而非返回值。
3. 需要强行跳过某段汇编指令（如 `B.NE`, `CBZ`）。

此时，我们需要使用 `X86Writer` 或 `Arm64Writer` 直接修改内存中的机器码。

#### 基本脚本框架

由于代码段（.text）通常是 **只读（RX）** 的，直接写入会报错。因此，必须先使用 `Memory.protect` 将目标内存页修改为 **可读可写可执行（RWX）** 。

| 123456789101112131415161718192021 | `// 1. 确定目标地址``var` `targetAddr = ...;` `// 2. 修改内存权限 (必须页对齐)``// Process.pageSize 通常是 4096 (0x1000)``var` `pageSize = Process.pageSize;``var` `pageStart = targetAddr.and(ptr(pageSize - 1).not());` `// 向下取整到页边界``Memory.protect(pageStart, pageSize,` `"rwx"``);` `// 3. 编写汇编指令``var` `writer =` `new` `Arm64Writer(targetAddr);` `// Android 主流是 ARM64``try` `{``// 写入 NOP 指令 (No Operation)``writer.putNop();`  `// 必须 flush 才能将缓冲区写入内存``writer.flush();``} finally {``// 释放资源``writer.dispose();``}` |
|-|-|

#### 核心 API 详解

| API | 说明 |
|-|-|
| **`Arm64Writer`**/**`X86Writer`** | Frida 提供的汇编编写器，用于将高级指令自动转换为对应的机器码并写入内存。 |
| **`Memory.protect(ptr, size, prot)`** | 修改内存保护属性。`prot`参数如`"rwx"`,`"rw-"`,`"r-x"`。**注意**：`ptr`必须是页对齐的地址。 |
| **`writer.putNop()`** | 写入 NOP 指令（空指令）。常用于擦除跳转指令或检测代码。 |
| **`writer.putBImm(addr)`** | 写入跳转指令（Branch）。 |
| **`writer.flush()`** | **关键**。将缓冲区中的机器码真正写入到内存中，并刷新指令缓存（Instruction Cache）。 |
| **`writer.dispose()`** | 销毁 Writer 对象，释放相关资源。 |

>
> 更多 API 请查阅官方文档：
>
>
> - [Arm64Writer](https://www.google.com/url?q=https%3A%2F%2Ffrida.re%2Fdocs%2Fjavascript-api%2F%23arm64writer)
> - [X86Writer](https://www.google.com/url?q=https%3A%2F%2Ffrida.re%2Fdocs%2Fjavascript-api%2F%23x86writer)
>
>
>

---

#### 实战案例：Frida-Labs 0xB

我们以 **Frida-Labs 0xB** 为例，演示如何通过修改汇编指令绕过逻辑判断。

**1. 分析 Java 层**

| 12345678 | `public` `final` `class` `MainActivity` `extends` `AppCompatActivity {``// 加载 so 库``static` `{ System.loadLibrary(``"frida0xb"``); }` `public` `final` `native` `void` `getFlag();` `// ... 点击按钮调用 getFlag()``}` |
|-|-|

**2. 分析 Native 层 (IDA)**
Java 层直接调用了 `getFlag()`，但反编译该函数看似为空（Empty Body）。这通常是因为 IDA 识别错误或代码被混淆。我们直接查看汇编代码：

```
.text:0000000000015234 MOV   W8, #0xDEADBEEF       ; W8 = 3735928559
.text:000000000001523C STUR  W8, [X29,#var_24]
.text:0000000000015240 LDUR  W8, [X29,#var_24]
.text:0000000000015244 SUBS  W8, W8, #0x539        ; W8 = W8 - 1337
.text:0000000000015248 B.NE  loc_1532C             ; 关键跳转！如果结果不为0，跳转走
```

**逻辑解读**：

- 代码将 `0xDEADBEEF` 减去 `0x539` (1337)。
- 结果显然不为 0。
- `B.NE` (Branch if Not Equal) 指令成立，程序跳转到 `loc_1532C`（直接结束或错误分支），跳过了中间真正生成 Flag 的代码。

**3. Patch 策略**
我们需要阻止这个跳转，让代码“顺流而下”执行到生成 Flag 的区域。
最简单的方法是将 `B.NE` 指令（偏移 `0x15248`）替换为 **`NOP`**（什么都不做）。

**4. 编写脚本**

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `function` `patchCode() {``var` `moduleName =` `"libfrida0xb.so"``;``var` `baseAddr = Module.findBaseAddress(moduleName);` `if` `(!baseAddr) {``console.log(``"[-] Module not found"``);``return``;``}``console.log(``"[*] Base address: "` `+ baseAddr);` `// 计算目标指令地址 (基址 + 偏移)``var` `offset = 0x15248;` `var` `targetAddr = baseAddr.add(offset);``console.log(``"[*] Target address: "` `+ targetAddr);` `// --- 内存权限修改 (关键步骤) ---``// 计算页对齐地址``var` `pageSize = Process.pageSize;``var` `pageStart = targetAddr.and(ptr(pageSize - 1).not());` `console.log(``"[*] Changing memory protection..."``);``// 将该页修改为可读可写可执行 (RWX)``Memory.protect(pageStart, pageSize,` `"rwx"``);` `// --- 指令修改 ---``var` `writer =` `new` `Arm64Writer(targetAddr);``try` `{``console.log(``"[*] Patching instruction to NOP..."``);``writer.putNop();` `// 写入 NOP``writer.flush();` `// 立即生效``console.log(``"[+] Patch success!"``);``}` `catch` `(e) {``console.error(``"[-] Patch failed: "` `+ e);``} finally {``writer.dispose();``}``}` `setImmediate(``function` `() {``// 延迟执行，确保 SO 已加载``setTimeout(``function``() {``Java.perform(``function` `() {``patchCode();``});``}, 1000);``});` |
|-|-|

**5. 运行结果**

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_2B38XDQ6WNCYSA7.png)

![image](https://bbs.kanxue.com/upload/attach/202512/1036360_PUA4K2GR8QV332P.png)

---

‍

---

# 回复

## 回复 by Heiyiren123 (#2)

*2025-12-8 02:47*

很给力，感谢分享！

## 回复 by 破客 (#3)

*2025-12-8 06:01*

感谢分享

## 回复 by bbpk (#4)

*2025-12-8 08:22*

感谢分享

## 回复 by KanXue_NG (#5)

*2025-12-8 16:21*

感谢分享

## 回复 by mb_cbgtaveo (#6)

*2025-12-9 10:01*

66666666

## 回复 by 七星舞月 (#7)

*2025-12-9 10:06*

感谢分享

## 回复 by Ace_Heng (#8)

*2025-12-9 10:20*

看看

## 回复 by Imxz (#9)

*2025-12-9 10:49*

tql

## 回复 by mb_uvyukvot (#10)

*2025-12-9 11:26*

tql

## 回复 by mb_pesxllvn (#11)

*2025-12-9 11:35*

666

## 回复 by wx_Huber Barrientos (#12)

*2025-12-9 12:20*

很给力，感谢分享！

## 回复 by git_86302JokerXsh (#13)

*2025-12-9 16:53*

太厉害了

## 回复 by xianhuimin (#14)

*2025-12-10 01:30*

高产

## 回复 by huangjw (#15)

*2025-12-11 09:21*

火钳刘明

## 回复 by 夜惜风雨 (#16)

*2025-12-11 09:48*

66666666

## 回复 by upcj (#17)

*2025-12-11 13:52*

6

## 回复 by mb_pnrjfxiv (#18)

*2025-12-13 18:16*

666

## 回复 by AK1988DA (#19)

*2025-12-14 20:51*

2

## 回复 by mb_ldtlgfnz (#20)

*2025-12-15 11:57*

火钳刘明

## 回复 by ulong9527 (#21)

*2025-12-15 15:33*

6

## 回复 by lance_357335 (#22)

*2025-12-15 17:51*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_fhpfcoqp (#23)

*2025-12-16 08:30*

6

## 回复 by peterchen (#24)

*2025-12-16 17:57*

多谢分享！

## 回复 by yu@n (#25)

*2025-12-17 21:10*

谢谢

## 回复 by YZJClear (#26)

*2025-12-18 20:06*

怎么root呢![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by xiusi (#27)

*2025-12-19 17:24*

>
> [YZJClear](https://bbs.kanxue.com/user-777812.htm)
>
>  怎么root呢[em_002]
>
>

刚入门可以用模拟器啊

## 回复 by 儒雅的灯塔 (#28)

*2025-12-21 01:06*

888

## 回复 by mb_uqfngcin (#29)

*2025-12-29 16:21*

666

## 回复 by mb_xqitfkbz (#30)

*2025-12-30 20:17*

1

## 回复 by zhao3261 (#31)

*2026-1-1 10:13*

谢谢

## 回复 by tjytjy (#32)

*2026-1-8 20:38*

谢谢

## 回复 by 飆汗吉米 (#33)

*2026-1-10 08:05*

6666

## 回复 by mb_uxxdrffh (#34)

*2026-1-13 10:37*

多谢分享！

## 回复 by wx_weggfkdk (#35)

*2026-1-13 11:00*

666

## 回复 by Bileton (#36)

*2026-1-13 12:59*

6

## 回复 by Snowman_Liam (#37)

*2026-1-21 06:24*

6

## 回复 by xuhe123 (#38)

*2026-1-22 12:41*

66

## 回复 by mb_gilgovuj (#39)

*2026-1-23 16:43*

666

## 回复 by keulraesik (#40)

*2026-1-23 17:11*

谢谢

## 回复 by wingsevil (#41)

*2026-1-23 19:25*

666

## 回复 by mb_wckjnnha (#42)

*2026-1-30 15:18*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by starscc (#43)

*2026-2-2 19:40*

感谢分享！

## 回复 by mb_zsizdcrb (#44)

*2026-2-2 20:56*

666

## 回复 by 寻梦之璐 (#45)

*2026-2-2 22:26*

11

## 回复 by wx_ _299 (#46)

*2026-2-4 09:38*

谢谢分享

## 回复 by taoying (#47)

*2026-2-4 09:39*

1

## 回复 by netprodiag (#48)

*2026-2-4 16:13*

讲得非常详细，学到了，谢谢分享！

## 回复 by mb_deisgjrb (#49)

*2026-2-9 03:29*

66

## 回复 by qig (#50)

*2026-2-10 19:19*

66666666

## 回复 by spdfdfer (#51)

*2026-2-11 11:13*

666

## 回复 by mb_lzybjqdn (#52)

*2026-2-14 23:56*

感谢分享

## 回复 by Tommy_t (#53)

*2026-2-28 10:48*

多谢分享

## 回复 by mb_irhdtnzm (#54)

*2026-3-2 13:24*

1

## 回复 by mb_srmwcgoy (#55)

*2026-3-4 15:34*

tql

## 回复 by mb_iywmjqjc (#56)

*2026-3-5 22:59*

666

## 回复 by mb_wyewaetf (#57)

*2026-3-8 11:53*

6666

## 回复 by mb_oaufhyol (#58)

*2026-3-9 11:40*

6666

## 回复 by wx_郑泽科 (#59)

*2026-3-10 09:19*

6666

## 回复 by 小辣鸡的id (#60)

*2026-3-10 09:57*

111

## 回复 by wx_故事与酒 (#61)

*2026-3-11 12:23*

6666666666666666666

## 回复 by mb_otoynfkv (#62)

*2026-3-11 22:02*

nice

## 回复 by 残枫 (#63)

*2026-3-13 09:13*

学习

## 回复 by huangbof (#64)

*2026-3-14 17:02*

多谢分享！

## 回复 by mb_criqjxad (#65)

*2026-3-21 22:29*

666

## 回复 by javac_kylin (#66)

*2026-3-31 15:10*

厉害了 我的哥

## 回复 by 小迷糊ddd (#67)

*2026-4-7 09:16*

感谢分享，学习一下。

## 回复 by jack_432875 (#68)

*2026-4-7 17:21*

感谢分享

## 回复 by pan_634488 (#69)

*2026-4-8 14:17*

666

## 回复 by n1ght (#70)

*2026-4-8 16:29*

感谢分享

## 回复 by git_49999huanptd2011 (#71)

*2026-4-20 17:06*

666

## 回复 by mb_dcjxxhsk (#72)

*2026-4-23 20:02*

6666

## 回复 by mb_eckbhhvy (#73)

*2026-4-28 20:44*

1

## 回复 by mb_eckbhhvy (#74)

*2026-4-28 20:44*

1

## 回复 by ADR66 (#75)

*2026-4-30 10:08*

666

## 回复 by Samepursuit (#76)

*2026-5-15 01:38*

谢谢

## 回复 by mb_lfqytcls (#77)

*2026-5-22 04:31*

1

## 回复 by এ卿欢颜้ꦿ (#78)

*2026-6-2 22:25*

tql

## 回复 by mb_awqgymxv (#79)

*2026-6-9 19:07*

感谢分享

## 回复 by DevilHunter (#80)

*2026-6-12 20:28*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_xjdhrmck (#81)

*2026-6-16 11:09*

666

## 回复 by zzhone (#82)

*2026-6-21 20:37*

666

## 回复 by mb_aplbnlua (#83)

*2026-7-8 14:55*

6

## 回复 by iBa0 (#84)

*2026-7-13 22:07*

1

## 回复 by mb_ndmoqzht (#85)

1
