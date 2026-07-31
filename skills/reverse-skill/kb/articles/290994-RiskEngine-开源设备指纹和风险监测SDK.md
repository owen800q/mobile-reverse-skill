---
title: '[原创]RiskEngine 开源设备指纹和风险监测SDK'
url: https://bbs.kanxue.com/thread-290994.htm
tid: 290994
author: WsttXm
date: '2026-04-26'
tags: [Android安全, 原创, HOOK注入, 源码框架]
crawled_at: '2026-07-31T15:09:57+08:00'
replies: 157
---

# RiskEngine 开源设备指纹和风险监测SDK

`RiskEngine` 是我开源在 GitHub 上的一个 Android 端设备指纹采集 + 风险检测 SDK。Java + C++17 双层结构，纯离线，进 App 之后调一次 `RiskEngine.collect()` 拿一份 `RiskReport`。

整篇按"招式"排，一招一招拆。Frida 检测占一半多的篇幅，是整个 SDK 最重的部分，按"对抗演化"的层次从入门级一路讲到内存级。

---

## 项目大致长什么样

代码组织上分两层：

- Java 层放 `riskengine-sdk/src/main/java/com/wsttxm/riskenginesdk/`，对外 API、各类业务级检测、调度编排
- Native 层 C++17 写在 `riskengine-sdk/src/main/cpp/` 下，做接触 `/proc`、解析 ELF、走系统调用这些"敏感动作"

入口长这样：

```java
RiskEngineConfig config = new RiskEngineConfig.Builder()
        .debugLog(true)
        .collectTimeout(15000)
        .build();
RiskEngine.init(context, config);

RiskEngine.collect(new RiskEngineCallback() {
    @Override public void onSuccess(RiskReport report) {
        Log.d("RiskEngine", "Risk: " + report.getOverallRiskLevel());
        Log.d("RiskEngine", "Score: " + report.getRiskScore());
    }
    @Override public void onError(Throwable error) {}
});
```

接的人不用关心内部细节，等回调就行。但要看安全设计，得看回调背后的逻辑。

代码盘点：12 个 Detector（root、hook、模拟器、调试、mount、ADB、进程扫描、沙箱、云手机、自定义 ROM、方法完整性等），十多个 Collector（android_id、build props、telephony、wifi、bluetooth、签名、屏幕、容器信号等）。Native 那边还有 5 个原生检测器和若干原生采集器。

---

## 招式一：Android ID 读了 4 遍

采集层定下的第一条原则：**单源采集顶多算"原始数据"，做不了"指纹"**。

Android ID 这种东西，绝大多数人一行就完事：

```java
String id = Settings.Secure.getString(
        context.getContentResolver(), Settings.Secure.ANDROID_ID);
```

放在风控里这就是个一行就能 hook 掉的"假指纹"——一段 Frida 脚本：

```js
Java.use("android.provider.Settings$Secure")
    .getString.overload(...).implementation = function() {
        return "0123456789abcdef";
    }
```

设备指纹工作直接归零。

`collector/java_layer/AndroidIdCollector.java` 里同一个 Android ID 从 4 个独立路径各读一遍：

```java
@Override
protected void collect(CollectorResult result) {
    collectViaSettingsApi(result);
    collectViaNameValueCache(result);
    collectViaContentResolver(result);
    collectViaContentQuery(result);
}
```

四条路：

1. `Settings.Secure.getString` 标准 API，最常见的一条
2. 反射 `sNameValueCache.mValues`，直接掏 Settings 的内部缓存。这条要绕 hidden API，加了 `HiddenApiBypass.addHiddenApiExemptions("")`
3. `ContentResolver.call("GET_secure", "android_id")`，走 ContentProvider 的 call 通道
4. `content query` 命令行，直接 fork 一个 `content query --uri content://settings/secure ...` 子进程读 stdout

四路读到的值丢同一个 `CollectorResult`，由 `core/DataAggregator.java` 比对一致性。`DataAggregator` 第 27 行起：

```java
if (fingerprint.hasInconsistency()) {
    List&lt;String&gt; inconsistent = fingerprint.getInconsistentFields();
    List&lt;String&gt; details = List.of("inconsistent_fields:" + ...);
    allDetections.add(new DetectionResult(
            "multi_source_validation",
            RiskLevel.HIGH,
            DetectionStatus.DANGER,
            6, 10, false, details, evidence
    ));
}
```

任意两路不一致直接合成一个 `multi_source_validation` 的 HIGH 级检测项。

这个设计的关键不在每条单路读到了什么，而在让攻击方同时维护四条路径的一致性。hook 一个静态 Java 方法，一行 Frida 就够。要让四条路全部返回"一致的伪造值"，要做的事是：

- hook `Settings.Secure.getString`
- hook 反射读 `mValues` 的路径，要么 hook `Field.get`，要么 hook 整个 ArrayMap 的 `get`
- hook `ContentResolver.call`
- 拦截 `content query` 子进程的 stdout——这条最难，子进程不在 inject 的进程里

第四条命令行通道，要拦只能 root 之后 hook 整个 system_server 改 settings provider，或者拦 shell 调用本身，工作量级跳一档。加这一路就是冲着"hook 不到的同进程外路径"来的。

---

## 招式二：把检测下沉到 syscall

讲完 Java 层多源，再看 native 层。

Frida 在 Android 上的入侵姿势，一大半都是 hook libc 的几个常用函数：`open` `openat` `read` `fopen` `fgets` `pread`。原因很简单——绝大部分检测代码（不管是 Java 的 `FileReader` 还是 C 的 `fopen`）底层都会落到 libc，hook 一个就能拦一片。

`cpp/util/syscall_wrapper.cpp` 里直接走 raw syscall：

```cpp
// Use raw syscall to avoid libc hooks
long my_openat(int dirfd, const char *path, int flags, mode_t mode) {
    return syscall(__NR_openat, dirfd, path, flags, mode);
}
long my_read(int fd, void *buf, size_t count) {
    return syscall(__NR_read, fd, buf, count);
}
long my_close(int fd) {
    return syscall(__NR_close, fd);
}
```

`syscall(__NR_openat, ...)` 不走 libc 的 `openat` 包装函数，直接通过 `syscall` 这个汇编入口（ARM64 上是 `svc #0` 指令）陷入内核。Frida 默认 hook 的是 libc 的 `openat` 符号，syscall 路径完全绕开它。

如果攻击方只是 `Interceptor.attach(Module.findExportByName("libc.so", "openat"), ...)` 这种常规姿势，对 native 检测路径完全失效。要绕开这条得搞内核态 hook（kprobe / sys_call_table 改写），需要 root + 内核级访问；或者扫指令找到所有 `svc #0` 全部插桩，技术上能做，Frida 默认不干。工作量级再跳一档。

`syscall_wrapper.cpp` 底下还封装了一个 `read_file_content`，把 openat + read + close 包成一个函数，几乎所有 native 检测器读 proc 文件都走它。

---

## 重头戏：Frida 检测的六层楼

这部分是 RiskEngine 最重的一块，单独放出来讲。

这一块设计的时候有个明确的层次：从最入门的字符串扫描到最高级的内存检测，每一层都是独立的检测维度，单独看都可能被绕掉，但堆在一起就强迫攻击方在所有维度同时绕过。每层按"常规做法 + 容易被绕的姿势 + RiskEngine 怎么做"展开。

### 第 0 层：先把 Frida 怎么进来的捋清楚

讲检测前先讲对手怎么动手。Frida 在 Android 上有两种主要落地方式：

**`frida-server` 模式**：电脑 PC 通过 USB / TCP 连一个跑在手机上的 `frida-server`，server 默认 27042 listen，跟客户端用 D-Bus over TCP 通信。需要 root，server 要 ptrace 目标进程。

**`frida-gadget` 模式**：把 `libfrida-gadget.so` 重打包进目标 APK，进程一启动 `System.loadLibrary` 把 gadget 装载进自己进程，gadget 自己跑一个 listener 等远程脚本连过来。不需要 root。

不管哪种，落到目标进程内一定会留下三类痕迹：

1. **被注入的代码**——要么是 gadget 的 .so，要么是 server 端 ptrace 进来注入的代码段
2. **新增的线程**——Frida runtime 起来要起 GLib 主循环、JS 引擎线程
3. **被改过的内存或指令**——这是 hook 的本质，要让原方法跳到 hook 实现，就得改原方法的入口

下面六层检测顺着这三个维度排，越往上越靠近"物理痕迹"那一边。

### 第 1 层：常规 Frida 检测

入门三招：扫字符串、扫线程名、扫端口。这三招实现简单、成本极低、单独看都能被绕掉。先把这三招过一遍，再讲为什么留着。

**扫字符串**。开 `/proc/self/maps`，看里面有没有 frida 相关字串。`HookFrameworkDetector.java` 第 96 行起：

```java
try (BufferedReader br = new BufferedReader(new FileReader("/proc/self/maps"))) {
    String line;
    while ((line = br.readLine()) != null) {
        String lower = line.toLowerCase();
        if (lower.contains("frida") || lower.contains("gadget")) {
            addStrong(details, score, "frida_maps:" + line.trim());
            break;
        }
    }
} catch (Exception ignored) {}
```

maps 一行行读，全转小写，看里面有没有 `frida` 或 `gadget`。绕这层有两种姿势：把 `libfrida-gadget.so` 改名成 `libutils_v2.so` 重打包进 APK，maps 里再没 frida 字样了；或者 hook `open`/`openat`，让读 `/proc/self/maps` 时返回伪造内容。第二条 Java 路径走 `FileReader` 最终落到 libc 不抗 hook，但 native 路径走 raw syscall 不在此列。

**扫线程名**。Frida runtime 起来后会在进程里创建带特征名的线程：`gum-js-loop`、`gmain`、`pool-frida`、`gdbus`。这些是 GLib 和 GUM 库内部线程，启动时就 setname 了。`HookFrameworkDetector.java` 第 116 行起：

```java
java.io.File taskDir = new java.io.File("/proc/self/task");
java.io.File[] tasks = taskDir.listFiles();
if (tasks != null) {
    for (java.io.File task : tasks) {
        java.io.File comm = new java.io.File(task, "comm");
        if (comm.exists()) {
            try (BufferedReader br = new BufferedReader(new FileReader(comm))) {
                String threadName = br.readLine();
                if (threadName != null && (threadName.contains("gum-js-loop")
                        || threadName.contains("gmain")
                        || threadName.contains("frida"))) {
                    addMedium(details, score, "frida_thread:" + threadName);
                }
            }
        }
    }
}
```

遍历 `/proc/self/task/`，每个子目录是一个线程的目录，里面 `comm` 文件存线程名。

`/proc/[pid]/comm` 和 `/proc/[pid]/task/[tid]/comm` 不是同一个东西。前者是进程主线程的名字，后者是某个具体线程的名字。Frida 是开新线程，主线程名字它没改，所以必须遍历 task 子目录。

绕这一层的姿势：在 Frida 启动时 hook `prctl(PR_SET_NAME)` 把线程名替换；或者拿 Frida 源码改名重新编译，把 `gum-js-loop` 改成 `worker-x`；又或者拦截 `/proc/self/task` 的目录读取（hook `getdents64`），过滤掉 frida 的 tid——native 走 raw `getdents64` 把这条打回去了。

**扫端口**。`frida-server` 默认 27042 listen，最直接的检测就是 connect 这个端口：

```java
try {
    Socket socket = new Socket();
    socket.connect(new InetSocketAddress("127.0.0.1", 27042), 120);
    socket.close();
    addMedium(details, score, "frida_port_open:27042");
} catch (Exception ignored) {}
```

`HookFrameworkDetector.java` 第 108 行那段。短小精悍，攻击方一行 `frida-server -l 0.0.0.0:9999` 换端口就破。

升级版在 `util/ProcfsUtils.java` 第 91 行：

```java
public static Set&lt;Integer&gt; findLoopbackListeningPorts() {
    LinkedHashSet&lt;Integer&gt; ports = new LinkedHashSet<>();
    collectLoopbackPorts("/proc/net/tcp", ports);
    collectLoopbackPorts("/proc/net/tcp6", ports);
    return ports;
}
```

不再固定端口，直接读 `/proc/net/tcp` 和 `/proc/net/tcp6`，把所有 LISTEN 状态、绑在回环地址（127.0.0.1、::1、0.0.0.0、::）的端口列出来。

`/proc/net/tcp` 的格式可以照抄写 parser，不用查文档：

```python
  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid ...
   0: 0100007F:69A2 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000 ...
```

每行一个连接。第二列 `local_address` 是 16 进制的 `IP:PORT`，前 8 位是 IP（小端），后 4 位是端口。第四列 `st` 是状态，`0A` 就是 LISTEN。

`ProcfsUtils.readTcpTable` 干的就是把这玩意儿解析出来，`isListening()` 比对状态、`isLoopback()` 判断是不是回环，组合后拿一份"本机所有 LISTEN 端口"。绕这层还能让 server 不 listen，切到 gadget 模式——gadget 默认是进程内通信，可以不开端口。这就把战场推到内存检测那一档去。

---

那这三招既然都能被绕，为什么还要留？

留着抓蠢的。现实里相当一部分外挂作者、爬虫开发者、刚学 Frida 的萌新，就是装上 frida-server 直接连过来跑脚本，不做任何隐藏。这三条规则一秒能把这一拨人全部拦掉。**底层用便宜的规则筛掉量级最大的那批低质攻击，把昂贵的检测预算留给真正有威胁的少数对手**——这是任何风控系统都该有的一层。

下一档开始进入"扫到了之后还要确认它真是 frida"这一阶段。

### 第 2 层：D-Bus 协议探针

第 1 层有个隐患：扫到一个 LISTEN 端口，但怎么确认它就是 frida-server？万一是别的合法服务呢？

这里换协议指纹。Frida 内部通信走 D-Bus over TCP。D-Bus 协议有个特点：客户端连上来要先发一个 NUL 字节加 AUTH 命令开始握手，服务端拒绝（认证失败、协议不对）会回一个以 `REJECTED` 开头的响应。

`util/ProcfsUtils.java` 第 212 行：

```java
public static String probeDbus(int port, int timeoutMs) {
    try (Socket socket = new Socket()) {
        socket.connect(new java.net.InetSocketAddress("127.0.0.1", port), timeoutMs);
        socket.setSoTimeout(timeoutMs);
        socket.getOutputStream().write("\0AUTH\r\n".getBytes(StandardCharsets.US_ASCII));
        socket.getOutputStream().flush();
        byte[] buffer = new byte[96];
        int read = socket.getInputStream().read(buffer);
        if (read <= 0) return "";
        return new String(buffer, 0, read, StandardCharsets.US_ASCII).trim();
    } catch (Exception ignored) {
        return "";
    }
}
```

发出去的 payload 就一个 NUL + `AUTH\r\n`，故意不带任何认证内容。frida-server 这种走 D-Bus 的会回 `REJECTED EXTERNAL` 或类似字串。普通 HTTP 服务器、其他 RPC 服务都不会有这种回包。

误报率几乎为零。这一招的价值在于把"扫端口"升级成"协议握手"，准确率拉满。

回到 `HookFrameworkDetector.java` 第 137 行，把第 1 层和第 2 层串起来：

```java
Set&lt;Integer&gt; loopbackPorts = ProcfsUtils.findLoopbackListeningPorts();
for (Integer port : loopbackPorts) {
    if (port == null || port <= 0) continue;
    String response = ProcfsUtils.probeDbus(port, PROBE_TIMEOUT_MS);
    if (response.toUpperCase().startsWith("REJECT")) {
        addStrong(details, score, "dbus_reject:" + port);
    }
}
```

把第 1 层拿到的所有 LISTEN 端口逐个发 D-Bus 探针。

举一反三：很多敏感工具都可以用类似思路做协议指纹。`adbd` 在 5555 上跑，连过去发 `host:version` 回包带版本号；`gdbserver` 连过去发 `+`，回包是 `$qSupported#73` 这种 GDB Remote Serial Protocol 报文；`debugserver`（lldb 那边）也有自己的 banner。只要愿意花时间读协议规范，"高准确率指纹"全都能写出来。

绕这一层只能把 frida-server 的通信协议从 D-Bus 换成自定义二进制协议。技术上能做，等于自己 fork 一个 frida-tools 维护，几乎没人愿意。

### 第 3 层：把进程和端口绑起来

到第 2 层，已经能很精准地判断"本机有 D-Bus 服务在监听"。但还有一个细节：怎么证明这个服务**就是 Frida**而不是别的什么 D-Bus 应用？

`HookFrameworkDetector.java` 第 151 行又加了一道门：

```java
List&lt;Integer&gt; pids = ProcfsUtils.findPidsByNameFragments(
        "frida-server", "frida_helper");
for (Integer pid : pids) {
    addStrong(details, score, "frida_pid:" + pid);
    for (Integer port : ProcfsUtils.findPidLoopbackListeningPorts(pid)) {
        addStrong(details, score, "frida_pid_port:" + port);
    }
}
```

逻辑分两步：

第一步，扫遍 `/proc/[pid]/`，从 `comm` 和 `cmdline` 里找名字带 `frida-server` 或 `frida_helper` 的进程，捞出所有候选 PID。`findPidsByNameFragments` 干这事。

第二步，针对每个候选 PID，读 `/proc/[pid]/net/tcp` 和 `/proc/[pid]/net/tcp6`——这个文件存的是这个进程能看到的 socket 表（在 net namespace 下），一样能找出它在 listen 哪些回环端口。

进程身份和端口监听绑死：哪怕攻击者改了端口、又装作其他服务，只要"某个进程同时具备 frida 进程特征 + 在 listen 一个回环端口"，就 strong 信号直接打。

测过的对手里有把 frida-server 改名叫 `media.codec_v2`、端口换成 31337、还专门起了个伪装 ContentProvider 抢答其他检测的。这套规则（进程名特征 + 进程独立持有的端口表）是当时唯一稳稳钉死它的检测项。

多源关联是反作弊一切方法的灵魂。单维度检测一打就穿，两个维度对上了可信度翻倍，三个维度对上了攻击者几乎赖不掉。

但到这里所有检测都还在"看名字、看协议、看端口"——只要攻击者把 Frida 改造得彻底匿名（gadget 模式、不开端口、不用 D-Bus），上面这三层都会失效。

下面进入项目最硬的一层。

### 第 4 层：内存层——看物理痕迹

前面讲过 hook 的本质：**要让原方法跳到 hook 实现，就得改原方法的入口**。这是绕不过去的事实。代码可以重命名，端口可以换，协议可以改，要 hook 一个函数那个函数的内存就一定会变。最高级的检测都在内存层。

`cpp/detector/native_hook_detector.cpp` 里干了三件事，盯三种"内存痕迹"。

**痕迹一：anon_exec 匿名可执行内存段**

正常 APK 里的 .so 文件加载进来，maps 里那一行一定有 `pathname` 字段对应文件路径。frida-gadget 通过 `mmap(MAP_ANONYMOUS | PROT_READ | PROT_EXEC, ...)` 注入的代码段，路径列是空的。

`native_hook_detector.cpp` 第 128 行：

```cpp
bool is_suspicious_executable_region(const MapEntry &entry) {
    if (entry.end <= entry.start || entry.perms.size() < 3) return false;
    if (entry.perms[0] != 'r' || entry.perms[2] != 'x') return false;

    std::string lower = to_lower(entry.raw);
    if (contains_any(lower, {
            "dalvik-jit", "jit-cache", "zygote", "scudo", "linker_alloc",
            "memfd:jit", "vdex", "boot-framework", "[vectors]"
    })) {
        return false;
    }
    return entry.path.empty();
}
```

判定：可读 + 可执行（`r-xp`）、路径空、不在白名单里。后面这个白名单是关键——Android 自己的 ART 就有一堆合法的匿名可执行段（JIT 编译出来的代码、dalvik-jit、memfd:jit），不排掉它们误报满天飞。误报治理的代码占整个检测器近一半篇幅，但生产环境必须有。

maps 的格式：

```python
addr_start-addr_end perms offset dev inode pathname
7f4a000000-7f4a020000 r-xp 00000000 fd:00 12345 /system/lib64/libc.so
```

每行一个内存段，pathname 缺失就是匿名映射。

绕这一层的姿势：在 mmap 之后改 `/proc/self/maps` 的内容——不行，maps 是内核生成的虚拟文件，应用层改不了。只能 hook 读路径。但 native 走的是 raw syscall + 自己 parse，hook libc 没用。

更高级的姿势：把代码段提前 mmap 到一个有合法路径的文件后面，伪造成系统库延伸。这要么对应文件不存在（fstat 一查就露），要么得真的预先放一个伪造文件落盘——工作量级再跳一档。

**痕迹二：ARM64 inline hook 的 trampoline 指令模式**

inline hook 的本质：把目标函数开头几条指令替换成跳转指令，让程序跳到 hook 实现，hook 实现执行完再跳回原指令的下一条。

ARM64 上一种最常见的跳板写法：

```python
LDR  X16, =target_addr   ; 把目标地址加载到 X16
BR   X16                 ; 无条件跳转到 X16
```

这两条指令在机器码里有非常稳定的模式。`native_hook_detector.cpp` 第 94 行起：

```cpp
bool is_arm64_ldr_literal(uint32_t instruction) {
    return (instruction & 0x3B000000u) == 0x18000000u;
}
bool is_arm64_br(uint32_t instruction) {
    return (instruction & 0xFFFFFC1Fu) == 0xD61F0000u;
}
```

ARM64 指令编码：每条 ARM64 指令固定 4 字节。`LDR (literal)` 的高位 opcode 模式是 `0x18000000` 加各种修饰位。`BR` 指令是 `0xD61F0000` 加寄存器编号（占低 5 位）。两个 mask 把变化位过滤掉，比较固定位就能识别指令类型。

扫每个可执行段开头：

```cpp
size_t scan_trampoline_hits(const MapEntry &entry) {
#if defined(__aarch64__)
    if (entry.end <= entry.start || entry.perms[0] != 'r' || entry.perms[2] != 'x') return 0;
    size_t length = std::min<uintptr_t>(entry.end - entry.start, 4096);
    if (length < sizeof(uint32_t) * 2) return 0;
    auto *cursor = reinterpret_cast&lt;const uint32_t *&gt;(entry.start);
    size_t count = length / sizeof(uint32_t);
    size_t hits = 0;
    for (size_t i = 0; i + 1 < count; ++i) {
        if (is_arm64_ldr_literal(cursor[i]) && is_arm64_br(cursor[i + 1])) {
            ++hits;
        }
    }
    return hits;
#else
    return 0;
#endif
}
```

只扫前 4096 字节是个性能权衡。inline hook 的跳板永远在函数开头，深扫整个段就是浪费 CPU。

绕这层换其他跳板模式。比如 `MOVZ + MOVK + MOVK + MOVK + BR` 用四条 `MOVZ/MOVK` 拼出 64 位地址再跳。能用，但加一条规则的成本比攻击方换实现的成本低一个数量级——主动权在防守方。

**痕迹三：SIGTRAP handler 探针**

这条最有意思。`native_hook_detector.cpp` 第 196 行：

```cpp
bool run_sigtrap_probe() {
    struct sigaction action{};
    struct sigaction old_action{};
    action.sa_sigaction = sigtrap_handler;
    action.sa_flags = SA_SIGINFO;
    sigemptyset(&action.sa_mask);
    if (sigaction(SIGTRAP, &action, &old_action) != 0) return true;

    g_sigtrap_seen = 0;
    pid_t pid = getpid();
    pid_t tid = static_cast<pid_t>(syscall(__NR_gettid));
    syscall(__NR_tgkill, pid, tid, SIGTRAP);
    sigaction(SIGTRAP, &old_action, nullptr);
    return g_sigtrap_seen == 1;
}
```

代码自己注册一个 SIGTRAP handler，然后用 `tgkill` 给当前线程发一个 SIGTRAP，看 handler 收没收到（`g_sigtrap_seen` 标志位）。如果 handler 没收到，说明信号路径被劫持了——通常是某个调试器或 hook 框架在接管 SIGTRAP。

原理：ptrace + 调试断点是用 SIGTRAP 实现的。调试器给目标进程下断点 = 把目标指令换成 BRK，被 ptrace 跟踪的进程触发 BRK 时内核会把 SIGTRAP 投递给 tracer 而不是 tracee，tracee 自己注册的 handler 就吃不到这个信号。

这是个"反推存在"：没法直接判断有没有被 ptrace，那就发个 SIGTRAP 给自己看自己接不接得到。接不到就有人在动信号路径。

### 第 5 层：自检——别去找 frida 在哪，看 frida 有没有动我

到第 4 层，前面所有招数都在主动找 Frida 在进程里的痕迹。还有一个完全不同的视角没用：**别去找 frida 在哪，去看自己的关键方法有没有被 frida 动过**。

`detector/MethodIntegrityDetector.java`：

```java
@Override
protected DetectionResult detect() {
    List&lt;String&gt; suspicious = new ArrayList<>();
    inspect(suspicious, RiskEngine.class, "collectSync");
    inspect(suspicious, RiskEngine.class, "getReportJson");
    inspect(suspicious, HookFrameworkDetector.class, "detect");
    inspect(suspicious, DebugDetector.class, "detect");
    inspect(suspicious, EmulatorDetector.class, "detect");
    inspect(suspicious, AndroidIdCollector.class, "collectViaSettingsApi", ...);
    inspect(suspicious, Debug.class, "isDebuggerConnected");
    inspect(suspicious, Settings.Secure.class, "getString",
            android.content.ContentResolver.class, String.class);
    if (!suspicious.isEmpty()) {
        return result(RiskLevel.HIGH, DetectionStatus.DANGER, 10, 10, false, ...);
    }
    return safe();
}
```

挑出来盯的方法分四类：

- SDK 自己的关键方法：`collectSync`、`getReportJson`，对应"采集入口"
- 其他检测器的入口：`HookFrameworkDetector.detect`、`DebugDetector.detect`、`EmulatorDetector.detect`，对应"兄弟检测器有没有被绑架"
- 数据采集入口：`AndroidIdCollector.collectViaSettingsApi`
- 系统级敏感方法：`Debug.isDebuggerConnected`、`Settings.Secure.getString`

挑这几个不是随便挑的，都是攻击者要"消灭风控"几乎必 hook 的目标。`HookFrameworkDetector.detect` 自己就是 hook 检测的入口，攻击者要让 hook 检测不报，第一选择就是 hook 这个方法让它直接 return safe。把它做成"必经之路"，反过来 hook 它就一定会留下痕迹。

每个方法走一次 `inspect`：

```java
private void inspect(List&lt;String&gt; suspicious, Class<?> owner, String name, Class<?>... parameterTypes) {
    String methodLabel = owner.getName() + "#" + name;
    try {
        Executable executable = owner.getDeclaredMethod(name, parameterTypes);
        String result = NativeCollectorBridge.nativeInspectMethodEntryPoint(executable);
        if (result == null || result.isEmpty()) return;
        if (result.startsWith("suspicious:")) {
            suspicious.add(methodLabel + ":" + result.substring("suspicious:".length()));
        }
    } catch (...) {}
}
```

把 Java `Executable` 对象（其实是 ART 内部 ArtMethod 的封装）传给 native，native 端通过 ART 的 ArtMethod 内存布局找到这个方法的"快速编译入口指针"（`entry_point_from_quick_compiled_code`），看这个指针指向的内存段是合法系统区域还是被劫持过的可疑区域。

`native_hook_detector.cpp` 第 290 行 `native_inspect_method_entry_point`：

```cpp
constexpr size_t kProbeBytes = 64;
constexpr size_t kWordSize = sizeof(uintptr_t);
size_t readable_bytes = ...;
size_t probe_bytes = std::min(kProbeBytes, readable_bytes);
for (size_t offset = 0; offset + kWordSize <= probe_bytes; offset += kWordSize) {
    auto *slot = reinterpret_cast&lt;const uintptr_t *&gt;(art_method + offset);
    uintptr_t candidate_address = *slot;
    if (candidate_address < 4096) continue;
    const MapEntry *region = find_region(regions, candidate_address);
    if (region == nullptr || !is_executable_region(*region)) continue;
    // ... 收集候选
}
```

这块的实现思路很务实：ArtMethod 在不同 Android 版本上字段偏移会变（11、12、13、14 都不一样），与其精确匹配某个版本，不如把 ArtMethod 头部 64 字节都扫一遍，挑里面**指向可执行内存段的指针**作为候选，取偏移最大的那个（一般是入口指针的位置）。然后看这个指针落在哪个内存段：

```cpp
if (is_suspicious_method_region(chosen->region) || !is_allowed_method_region(chosen->region)) {
    return "suspicious:" + summary.str();
}
return "ok:" + summary.str();
```

落在 `frida/gadget/xposed/substrate` 之类的段、或者落在不被允许的段（合法 ART 区是 `libart`、`/apex/`、`/system/`、`.oat`、`.odex`、`memfd:jit`、`/data/app/` 等），都算 suspicious。

这一招的核心威慑力：**哪怕攻击者把 Frida 包装得连匿名内存都没了、连协议都改了、连进程名都伪装得和系统进程一样，只要它真的劫持了关键方法，那个方法的入口指针一定指向 Frida 的内存段**。

绕这一层有两个思路，但都自相矛盾：

- 不去 hook 这几个方法——但 Frida 的目的就是为了 hook，关键方法本身就是 hook 检测的入口（`HookFrameworkDetector.detect`），不 hook 它就拿不到任何成果
- hook 完之后还把读字节的接口也 hook 掉让它返回原始字节——但这又落入"多源验证"陷阱：JNI 路径、syscall 路径、ArtMethod 内存指针，全都得同步劫持

到这一层，攻防进入"你绕一招我加一招"的纯阵地战。

最后还有 `RiskReport.java` 第 100 行的兜底逻辑：

```java
private boolean hasHardTrigger() {
    for (DetectionResult detection : detections) {
        if (detection.getRiskLevel().getValue() < RiskLevel.HIGH.getValue()) continue;
        String name = detection.getDetectorName();
        List&lt;String&gt; details = detection.getDetails();
        if ("hook_framework".equals(name) && containsAny(details,
                "dbus_reject", "frida_pid_port", "anon_exec", "trampoline", "sigtrap")) {
            return true;
        }
        if ("method_integrity".equals(name)) {
            return true;
        }
    }
    return false;
}
```

`method_integrity` 命中任何一项 → 直接 DEADLY，不管别的检测打了多少分。这是把"自检"放到 SDK 决策的至高位。

### 第 6 层：信号分级 + 多招组合

到这里所有招式都讲完了，最后讲怎么把它们组合起来出一个判定。

回到 `HookFrameworkDetector.java`：

```java
private static final class SignalScore {
    private int strong;
    private int medium;
    private int weak;
}
```

每条规则按强弱给信号打标，加到 `SignalScore`：

- strong：内存层痕迹（`anon_exec`、`trampoline`、`sigtrap`）、协议握手（`dbus_reject`）、进程关联（`frida_pid_port`）、Xposed 实际激活的 hook 数量
- medium：线程名、Xposed 类被加载、栈痕迹、默认端口连得上
- weak：其他弱信号（一般是 native 层那些不太确定的字符串）

最后按累加值判级：

```java
if (score.strong >= 2 || (score.strong >= 1 && score.medium >= 2)) {
    return result(RiskLevel.DEADLY, ..., 10, 10, ...);
}
if (score.strong >= 1 || score.medium >= 2) {
    return result(RiskLevel.HIGH, ..., 8, 10, ...);
}
return result(RiskLevel.MEDIUM, ..., 4, 10, ...);
```

之所以这么搞，是因为每一档单独看都可以被绕。线程名能改、端口能换、字符串能 mv、连 anon_exec 都有偏门姿势能伪装。但要强迫攻击者**同时**在所有维度全部绕过——改名 + 改端口 + 改协议 + 不留匿名内存 + 不动方法入口 + 不被 SIGTRAP 探针发现 + 4 路 Android ID 数据始终一致——这个工程量已经超过"重新写一个 Frida"。

写一条 99% 准确的规则比写十条 90% 准确的规则更难。十条 90% 的规则做投票反而稳。这是做风控这些年最朴素的一条经验。

---

## 顺便聊聊其他几个检测器

Frida 那块是最重的，剩下几个检测器思路一样，简单扫过。

`detector/RootDetector.java` 用 `su` 二进制路径列表 + Magisk 路径 + `getenforce` 看 SELinux 是不是 Permissive + native 端的 root 检测组合。重点是把 `/data/adb/magisk` 这类**模块化 root** 的特征单独检测了，老的 root 脚本通常只盯 `/system/bin/su`，会漏。

`detector/EmulatorDetector.java` 是个证据累积型设计：传感器数量太少、传感器厂商写着 AOSP、热区为空、缺蓝牙摄像头闪光特性、网卡 IP 是 `10.0.2.15`（QEMU 默认网关）等十几条特征，**累积到 3 条以上才升级风险等级**。"3 条以上"这个阈值是控误报的关键——单个特征都有概率出现在物理设备上，比如低端机传感器确实少。

`detector/DebugDetector.java` 主要靠 `TracerPid` 字段（在 `/proc/self/status` 里），同时用 native 的 ptrace 探测、ADB 端口探测、IDA 默认调试端口 23946、maps 里的 `gdbserver`/`lldb`/`android_server` 等做交叉验证。

`detector/MountAnalysisDetector.java` 直接读 `/proc/mounts` 和 `/proc/self/mountinfo`，找 `magisk` 字串和 `tmpfs /system` 这种"内存覆盖系统分区"的痕迹。Magisk 类的模块化 root 必须用 tmpfs 挂载覆盖系统分区，这个行为在挂载表里改不掉——内核生成的视图。这是非常稳的一条规则。

每个检测器拉出来都是同一套思路：**多个独立特征、信号分级、组合判定、native 层兜底**。

---

## 工程实践中的细节

**注册表插件化**。`detector/DetectorRegistry.java` 和 `collector/CollectorRegistry.java` 都是简单的构造函数里 `add(new XxxDetector(context))`。要扩展新检测，新建一个类继承 `BaseDetector`，在 Registry 里加一行就行，主流程一行不用改。

**任务并发与超时**。`core/TaskScheduler.java` 用 `ExecutorService + Future` 把所有 collector 和 detector 并行跑，统一超时（默认 15 秒）。任意单个任务挂了不影响其他任务的结果。脚本思维容易写出"按顺序执行 N 个检测、第 5 个卡住整个进程都回不来"这种代码，并发 + 超时是 SDK 化的硬门槛。

**Native 边界**。`detector/DebugDetector.java` 第 60 行起，先调 `NativeCollectorBridge.nativeGetTracerPid()`，失败才 fallback 到 Java 读 `/proc/self/status`。这个"native 优先、Java 兜底"模式贯穿所有检测器：能下沉的尽量下沉到 C++，因为 native 层加上前面说的 raw syscall，攻击表面要小一档。

---

## 写在最后

代码仓库地址：https://github.com/WsttXm/RiskEngine。Releases中有编译好的APK和aar，欢迎体验、欢迎提Issue 和 PR。

**致谢**

- https://github.com/taisuii/sentry
- https://github.com/taisuii/rusda
- https://github.com/1193776794/launch

---

# 回复

## 回复 by 温泉划水鱼 (#2)

*2026-4-26 17:32*

秒吃，我来试试

## 回复 by huangjw (#3)

*2026-4-26 17:33*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_ldbucrik (#4)

*2026-4-26 17:59*

感谢分享

## 回复 by 拍拖 (#5)

*2026-4-26 18:00*

感谢分享

## 回复 by qqqiu (#6)

*2026-4-26 18:28*

2

## 回复 by qqqiu (#7)

*2026-4-26 18:30*

这种叫检测 离真正的风控还有距离

## 回复 by WsttXm (#8)

*2026-4-26 18:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  qqqiu](https://bbs.kanxue.com/user-1053738.htm)
>  这种叫检测 离真正的风控还有距离
>

写着写着就主要偏向于检测了，本来还有风控的服务端我删掉了，感兴趣可以翻翻GitHub仓库的历史提交

## 回复 by apxar (#9)

*2026-4-26 19:43*

1

## 回复 by mb_asiwnxyv (#10)

*2026-4-26 20:31*

感谢分享

## 回复 by mb_bzkmcyjt (#11)

*2026-4-26 20:56*

666

## 回复 by wx_huhu_859 (#12)

*2026-4-26 22:32*

11

## 回复 by Zepp7289 (#13)

*2026-4-27 00:53*

tql

## 回复 by WsttXm (#14)

*2026-4-27 10:28*

>
> [温泉划水鱼](https://bbs.kanxue.com/user-991803.htm)
>  秒吃，我来试试
>

感谢支持

## 回复 by 发烧小孩 (#15)

*2026-4-27 10:33*

看看

## 回复 by method (#16)

*2026-4-27 10:37*

1

## 回复 by 寻梦之璐 (#17)

*2026-4-27 10:39*

666

## 回复 by 寻梦之璐 (#18)

*2026-4-27 10:45*

/proc/[pid]/net/tcp 和 /proc/[pid]/net/tcp6 这两个目录用户app没有权限，哥，![image](https://bbs.kanxue.com/view/img/face/011.gif)

## 回复 by mb_jhohnbzu (#19)

*2026-4-27 10:50*

666

## 回复 by iBa0 (#20)

*2026-4-27 11:07*

123

## 回复 by 夜惜风雨 (#21)

*2026-4-27 14:20*

66666666

## 回复 by xianhuimin (#22)

*2026-4-27 14:56*

感谢分享

## 回复 by xingbing (#23)

*2026-4-27 15:05*

感谢分享

## 回复 by pan_634488 (#24)

*2026-4-27 15:08*

感谢分享

## 回复 by starrysky (#25)

*2026-4-27 15:41*

1

## 回复 by 小尘0000 (#26)

*2026-4-27 16:27*

666

## 回复 by 随风而行aa (#27)

*2026-4-27 16:46*

看看

## 回复 by tcc0lin (#28)

*2026-4-27 17:42*

1

## 回复 by wx_岁月真好_475628 (#29)

*2026-4-27 18:14*

666666

## 回复 by 一栋奥特曼 (#30)

*2026-4-27 19:49*

666

## 回复 by Aar0n (#31)

*2026-4-27 21:57*

111

## 回复 by wx_寒号鸟二代 (#32)

*2026-4-27 22:11*

66666

## 回复 by mb_nkjfyhkg (#33)

*2026-4-28 00:58*

mark

## 回复 by 木志本柯 (#34)

*2026-4-28 01:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  qqqiu](https://bbs.kanxue.com/user-1053738.htm)
>  这种叫检测 离真正的风控还有距离
>

风控就是一条条检查慢慢堆起来的。工程问题罢了

## 回复 by jdong (#35)

*2026-4-28 09:35*

6666

## 回复 by 小菜sky (#36)

*2026-4-28 09:52*

mark

## 回复 by 熊猫吃鱼 (#37)

*2026-4-28 10:37*

6666

## 回复 by guijingwen (#38)

*2026-4-28 10:39*

66

## 回复 by 大魔头 (#39)

*2026-4-28 12:00*

jixu

## 回复 by 大魔头 (#40)

*2026-4-28 12:00*

jixu

## 回复 by 大魔头 (#41)

*2026-4-28 12:00*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by Imxz (#42)

*2026-4-28 12:16*

tql

## 回复 by mb_ghcouuzx (#43)

*2026-4-28 13:00*

看啊看看

## 回复 by mb_ghcouuzx (#44)

*2026-4-28 13:00*

看看看

## 回复 by mb_ghcouuzx (#45)

*2026-4-28 13:00*

看看

## 回复 by mb_cbgtaveo (#46)

*2026-4-28 14:20*

6666666666

## 回复 by mb_cbgtaveo (#47)

*2026-4-28 14:20*

6666666666

## 回复 by mb_cbgtaveo (#48)

*2026-4-28 14:20*

66666666

## 回复 by mJqalJqN (#49)

*2026-4-28 15:07*

1

## 回复 by mJqalJqN (#50)

*2026-4-28 15:07*

1

## 回复 by 简单的简单 (#51)

*2026-4-28 15:56*

抱走开抄

## 回复 by 简单的简单 (#52)

*2026-4-28 15:56*

抱走开抄

## 回复 by 简单的简单 (#53)

*2026-4-28 15:56*

抱走开抄

## 回复 by XCicada (#54)

*2026-4-28 17:39*

感谢

## 回复 by k4y0z (#55)

*2026-4-28 17:45*

666

## 回复 by k4y0z (#56)

*2026-4-28 17:45*

666

## 回复 by k4y0z (#57)

*2026-4-28 17:45*

666

## 回复 by wx_weggfkdk (#58)

*2026-4-28 18:08*

看看

## 回复 by wx_weggfkdk (#59)

*2026-4-28 18:08*

看看

## 回复 by wx_weggfkdk (#60)

*2026-4-28 18:08*

看看![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by veluboii (#61)

*2026-4-28 21:27*

7666

## 回复 by veluboii (#62)

*2026-4-28 21:28*

666

## 回复 by veluboii (#63)

*2026-4-28 21:28*

666

## 回复 by Thehepta (#64)

*2026-4-29 11:03*

1

## 回复 by dob_C (#65)

*2026-4-29 11:44*

感谢分享

## 回复 by dob_C (#66)

*2026-4-29 11:44*

感谢分享

## 回复 by dob_C (#67)

*2026-4-29 11:44*

感谢分享

## 回复 by mb_zanihjkx (#68)

*2026-4-29 14:07*

666

## 回复 by mb_fsotigwk (#69)

*2026-4-29 15:54*

1

## 回复 by 易始 (#70)

*2026-4-29 19:35*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 易始 (#71)

*2026-4-29 19:36*

感谢分享

## 回复 by 易始 (#72)

*2026-4-29 19:36*

感谢分享

## 回复 by 易始 (#73)

*2026-4-29 19:36*

感谢分享

## 回复 by logeye (#74)

*2026-4-29 22:07*

6666

## 回复 by 特洛伊Troye (#75)

*2026-4-30 15:04*

看看

## 回复 by 4Chan (#76)

*2026-4-30 16:41*

学习一下

## 回复 by mb_koixqizd (#77)

*2026-4-30 17:31*

学习

## 回复 by mb_ckanaznr (#78)

*2026-5-1 03:54*

感谢分享

## 回复 by oscar99999 (#79)

*2026-5-1 21:10*

666666

## 回复 by uni7corn (#80)

*2026-5-2 14:58*

感谢分享

## 回复 by uni7corn (#81)

*2026-5-2 15:25*

感谢分享，学习了

## 回复 by mb_lvesdvhu (#82)

*2026-5-3 15:54*

6666

## 回复 by 伊苏尔德 (#83)

*2026-5-4 09:55*

6

## 回复 by flyingx (#84)

*2026-5-4 10:02*

感谢分享

## 回复 by Snowman_Liam (#85)

*2026-5-4 11:08*

666

## 回复 by mb_pivwkzjg (#86)

*2026-5-6 11:23*

感谢分享

## 回复 by fangliangz (#87)

*2026-5-6 13:06*

666

## 回复 by mb_donutrph (#88)

*2026-5-6 14:30*

666

## 回复 by 小木马 (#89)

*2026-5-7 14:38*

666

## 回复 by xiaoc996 (#90)

*2026-5-7 16:20*

66

## 回复 by mb_ugnawvja (#91)

*2026-5-9 09:02*

感谢分享

## 回复 by Migc (#92)

*2026-5-9 09:47*

6

## 回复 by 看雪高研 (#93)

*2026-5-9 09:50*

666

## 回复 by mb_yaewlqnp (#94)

*2026-5-9 10:17*

6666666

## 回复 by Corner_610006 (#95)

*2026-5-9 10:44*

感谢分享

## 回复 by kingking888 (#96)

*2026-5-9 11:02*

666

## 回复 by orange_777 (#97)

*2026-5-9 11:17*

1

## 回复 by 29o (#98)

*2026-5-9 11:33*

感谢分享

## 回复 by mb_qimctavn (#99)

*2026-5-9 12:13*

6

## 回复 by mb_saeucvtv (#100)

*2026-5-9 13:12*

666

## 回复 by 木槿any (#101)

*2026-5-9 13:21*

666

## 回复 by mb_hkxztpyq (#102)

*2026-5-9 14:33*

感谢分享，细细看看都有哪些检测能力吧

## 回复 by permanent011 (#103)

*2026-5-9 17:00*

1

## 回复 by mb_osxdmntv (#104)

*2026-5-10 00:20*

666

## 回复 by ivy1 (#105)

*2026-5-11 13:39*

感谢分享

## 回复 by tigericon (#106)

*2026-5-11 13:52*

66

## 回复 by mb_ndotvqat (#107)

*2026-5-11 14:04*

1

## 回复 by ltaiyang (#108)

*2026-5-11 16:34*

感谢分享

## 回复 by ivy1 (#109)

*2026-5-11 16:43*

感谢分享

## 回复 by TinM! (#110)

*2026-5-12 11:40*

1

## 回复 by 勒LI (#111)

*2026-5-12 15:05*

666

## 回复 by 末日大哥 (#112)

*2026-5-12 15:21*

666学习一下

## 回复 by virjar (#113)

*2026-5-12 15:51*

感谢分享

## 回复 by 飆汗吉米 (#114)

*2026-5-13 14:33*

666

## 回复 by lamboo (#115)

*2026-5-13 14:57*

66666666

## 回复 by mb_gypkxvgh (#116)

*2026-5-14 14:14*

123

## 回复 by hbslover (#117)

*2026-5-14 22:05*

1

## 回复 by 街道办事处 (#118)

*2026-5-15 09:50*

111

## 回复 by mb_ynwjzbro (#119)

*2026-5-18 11:18*

6

## 回复 by tobecome (#120)

*2026-5-20 14:36*

11

## 回复 by mb_zvqaijnr (#121)

*2026-5-20 22:06*

999

## 回复 by 三点水的湫 (#122)

*2026-5-20 22:42*

里边检测sandbox有问题的

## 回复 by wx_北极星_493 (#123)

*2026-5-20 22:46*

看看

## 回复 by fengyunabc (#124)

*2026-5-20 23:19*

感谢分享。

## 回复 by mb_zwojibcx (#125)

*2026-5-22 18:56*

7

## 回复 by 章康 (#126)

*2026-5-23 22:24*

感谢分享

## 回复 by mb_gatolgsc (#127)

*2026-5-25 12:05*

感谢分享

## 回复 by yangshuang (#128)

*2026-5-25 21:43*

感谢分享

## 回复 by FMNS (#129)

*2026-5-25 21:59*

.....

## 回复 by wx_张健_921 (#130)

*2026-5-26 10:32*

666

## 回复 by 曹无咎 (#131)

*2026-5-26 16:12*

1

## 回复 by git_71735namngsec-netizen (#132)

*2026-5-26 16:56*

666

## 回复 by mb_jnmxfjku (#133)

*2026-5-26 17:21*

666

## 回复 by hanjiefang (#134)

*2026-5-26 17:41*

感谢分享

## 回复 by artake (#135)

*2026-5-26 17:55*

666

## 回复 by wx_星儿 (#136)

*2026-5-26 18:39*

22

## 回复 by 蒙面功夫熊猫 (#137)

*2026-5-28 14:27*

1

## 回复 by maomaolk (#138)

*2026-5-28 15:10*

感谢分享

## 回复 by mb_czqyztmr (#139)

*2026-6-10 20:17*

1

## 回复 by mb_enbuhisq (#140)

*2026-6-10 21:11*

66666

## 回复 by mb_xiycqmtm (#141)

*2026-6-15 17:28*

感谢分享

## 回复 by ulong9527 (#142)

*2026-6-26 09:51*

感谢分享，学习一下

## 回复 by mb_dlljjfcf (#143)

*2026-6-27 08:50*

666666

## 回复 by mb_ajqftfbv (#144)

*2026-6-30 22:52*

感谢分享

## 回复 by 咸鱼…… (#145)

*2026-6-30 23:20*

666

## 回复 by 咸鱼…… (#146)

*2026-6-30 23:20*

666

## 回复 by mb_equmgdsm (#147)

*2026-7-1 10:48*

学习

## 回复 by 逆向小龙 (#148)

*2026-7-1 11:24*

1

## 回复 by git_75734chatgptbina-crypto (#149)

*2026-7-5 03:55*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by mb_ttaweivy (#150)

*2026-7-7 03:22*

66

## 回复 by A0x01 (#151)

*2026-7-7 07:45*

666

## 回复 by buluo533 (#152)

*2026-7-7 09:53*

学习一下

## 回复 by 空谈误国 (#153)

*2026-7-7 09:57*

感谢分享

## 回复 by 我不是卷王 (#154)

*2026-7-7 10:52*

1

## 回复 by wx_小喇叭 (#155)

*2026-7-7 15:24*

1

## 回复 by 白毅 (#156)

*2026-7-9 01:17*

学习

## 回复 by r0-涛 (#157)

*2026-7-13 13:44*

1

## 回复 by mb_degalzhb (#158)

*2026-7-15 14:47*

666
