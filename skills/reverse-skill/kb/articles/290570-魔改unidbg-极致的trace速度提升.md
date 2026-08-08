---
title: '[原创]魔改unidbg：极致的trace速度提升'
url: https://bbs.kanxue.com/thread-290570.htm
tid: 290570
author: x1a0f3n9
date: '2026-03-30'
tags: [Android安全, 原创, 基础理论, 工具脚本]
crawled_at: '2026-08-08T10:16:05+00:00'
replies: 173
---

`unidbg` 的 `trace` 速度太慢了？别急，我来助你

我们这一篇文章主要是来改进一下 `unidbg` 的自带 `trace` 功能，对于这一功能，我的评价是目前的 `trace` 能用但是并不好用；

# 0. 省流篇：怎么用？

先说一下速度吧，实测比原版unidbg的快几十倍，然后混淆恶心的ollvm+vmp可以达到一百多倍，也就是需要几小时的可以i直接变成几分钟。

找到我的魔改unidbg https://github.com/LunFengChen/unidbg 然后 `git clone`，之后正常使用就行。

然后这里我是提供了类似 `traceCode` 的 API，叫做 `traceCodeText`，因为我后续会支持一波二进制格式的 `trace`，那个速度更快，不过需要和桌面端配合使用；

>
> 注意：我保留了原版的 `traceCode`，这样不影响你项目迁移后的编译问题；
>
>
>

```java
// 原版unidbg，性能地狱；并且写入文件还得自己搞个PrintStream
emulator.traceCode(begin, end);

// 魔改版unidbg： 输出最详细的 trace， 直接传入文件名自动写入
emulator.traceCodeText(module.base, module.base+module.size, "apks/京东/13.1.0/trace_jdgs.log");

// 魔改版unidbg：关闭 SMC 检测 + 关闭 Hexdump + 关闭语义解析
emulator.traceCodeText(module.base, module.base+module.size, "apks/京东/13.1.0/trace_jdgs.log")
  .setDisableSMC(false)
  .setDisableHexdump(true)
  .setDisableFunctionCall(true);
\```

会用了对吧，对优化理论不感兴趣的话，那就可以直接跳到最后了。

# 1. `unidbg` 的 `trace` 实际使用存在的问题

- `trace` 实在太慢了：安全类 SDK 如某美，一亿行日志居然要几小时？能不能做到几分钟？也就是上百倍加速。
- 漏了部分寄存器：如 `q`/`s`/`d`/`h`/`b` 寄存器，其中 `q` 寄存器是最重要的，因为常见的加解密都会用到它。
- `trace` 的格式也不够直观：
	- 最近作者在 [7ebecfe](https://github.com/LunFengChen/unidbg/commit/7ebecfe4fc8a872515e061ff3693ccf730fe9b22) 中加入了 `cpsr` 寄存器更好的打印效果，并且记录了内存读写绝对地址，然后在本人的 [建议](https://github.com/LunFengChen/unidbg/commit/7ebecfe4fc8a872515e061ff3693ccf730fe9b22) 下在 [8063a4f](https://github.com/LunFengChen/unidbg/commit/8063a4f1765fd0abb6163fcd1947b0ddbf691495) 修改成了 `(w 0xe4fff2f0 8) (w 0xe4fff2f8 8)` 更加明显的样子；（也是蹭上了哈哈哈）
	- 不过依旧存在一个问题，就是到底往这个地址写入了什么值？？实际跟踪如果不使用一些高级搜索策略，很容易跟丢；当然这个仁者见仁，智者见智了；

这期文章我们就来解决这个问题，并且试图给大家讲明白我都做了哪些优化；

---

# 2. `unidbg` 的 `trace` 是怎么实现的？`OLLVM`/`VMP` 的 `trace` 有什么特点？

`Unidbg` 的 `Trace` 功能本质是一个 **逐指令回调钩子**（`CodeHook`）：`Unicorn`（或 `Dynarmic`/`Hypervisor`）引擎在执行每一条 ARM/ARM64 指令前，都会回调一次 Java 层的 `hook()` 方法。在这个回调里，原版引擎需要做：

- **反汇编当前指令**（调用 `Capstone`）然后根据 `Capstone` 模块得知哪些寄存器发生了变化，以便于后续读取变化的寄存器打印
	- 这一步是有用的，但是有没有优化空间？
- **查找所属模块**（遍历已加载模块列表）
	- 这一步有意义么？有的，如果走入其他模块，我们其实没必要跟踪
- **格式化输出字符串**（`String.format` + 模块名/地址/指令/寄存器）
	- 用 `String.format` 格式化字符串，效率到底够不够？

对于正常的 SO，一次函数调用可能产生几百到几万条 `Trace`，`unidbg` 原版这套流程完全够用。但 `OLLVM` 和 `VMP` 保护会让函数的**执行路径**急剧膨胀——`OLLVM` 的状态机调度让每个基本块的跳转都要经过 `dispatcher` 中转，`VMP` 更是把每条原始指令翻译成数十条 VM Handler 指令逐条解释执行：

| 保护方案 | 典型特征 | Trace 规模 |
|-|-|-|
| `OLLVM` 控制流平坦化 | 单个函数被拆成数百个 Basic Block，通过 `switch-case` 状态机调度 | 原本 1000 条指令膨胀到 50 万+ |
| `VMP`（虚拟机保护） | 原始指令被翻译为自定义字节码，在 VM Handler 循环中逐条解释执行 | 一个签名函数轻松 几千万条 |
| 两者叠加 | `VMP` 的 Handler 本身又被 `OLLVM` 平坦化 | 数量级爆炸 |

# 3. 性能短板一：`Capstone` 反汇编

## 3.1 问题分析

`unidbg` 做这一步其实是没问题的，主要是为了从机器码到汇编指令，这样可以知道哪些寄存器发生了变化，以便于后续读取变化的寄存器打印。

如 `"stp x29, x30, [sp, #-0x20]!"` 这一条指令就读取了 `sp` 寄存器的值，然后偏移地址，然后读 `x29`、`x30` 的值，然后把值写入到 `sp-0x20` 的地址处；`unidbg` 通过 `Capstone` 可以得知，`read` 的寄存器有 `sp`、`x29`、`x30`，`write` 的寄存器有 `sp`；

但是这一步对于 `OLLVM`/`VMP` 的 `trace` 来说，会有很大的性能浪费，因为 `OLLVM`/`VMP` 的指令膨胀效果，其实存在着大量的重复指令，这些重复指令的机器码都是一样的；此时如果依旧每一条指令都调用一次 `Capstone` 的 `disassemble()`，那么就会非常慢。

如何解决这个问题：很简单，直接上缓存，你 `OLLVM`/`VMP` 再强，能有多少不同的指令？

这里我直接使用了 **L1/L2 两级缓存**，这里为啥不只用一级缓存？比如为什么不直接用一个 `HashMap<地址, 反汇编结果>` 来搞定？

因为：这在 `OLLVM`/`VMP` 场景下效率不是最优的，原因是 `HashMap` 每次查找需要：

1. 把 `long` 地址自动装箱成 `Long` 对象（分配堆内存）
2. 计算哈希值
3. 查找桶 + 遍历链表/红黑树
4. `LRU` 模式下还要维护链表顺序

如果是上亿级别的指令，上亿次 × 这套流程 = 一笔可观的开销。

所以这里我们再搞一级缓存，用**数组**来代替，直接使用地址取模来定位，这样可以省去 `HashMap` 的开销。

```java
// L1: 直接映射数组缓存 —— 8M 槽位，覆盖 32MB 物理寻址
// 地址 → 槽位的映射：(address / 4) & 0x7FFFFF
private final CachedInstruction[] l1Cache = new CachedInstruction[8_388_608];

// L2: LRU 字典兜底 —— 100万 容量
private final Map&lt;Long, CachedInstruction&gt; l2Cache = new LinkedHashMap<>(1_000_000, 0.75f, true) {
    @Override
    protected boolean removeEldestEntry(Map.Entry&lt;Long, CachedInstruction&gt; eldest) {
        return size() > 1_000_000;
    }
};
\```

## 3.2 举例

### L1 做了啥？

ok 接下来拿 `VMP` 举个例子；这里假设 `VMP` 的 VM Handler 循环执行 3 条指令，地址分别是 `0x1000`、`0x1004`、`0x1008`，循环 N 次：

**第 1 轮（全部 cache miss）**

\```
执行 0x1000:
  L1[slot=1024] = 空        ← L1 miss
  L2 也没有                 ← L2 miss
  → 调用 Capstone 反汇编 → 得到 "ldr x8, [x20]"
  → 打包成 CachedInstruction 对象
  → 存入 L1[1024]
执行 0x1004:
  L1[slot=1025] = 空        ← L1 miss
  → 调用 Capstone → "ldr x9, [x8]"
  → 存入 L1[1025]
执行 0x1008:
  L1[slot=1026] = 空        ← L1 miss
  → 调用 Capstone → "br x9"
  → 存入 L1[1026]
这一轮调了 3 次 Capstone。
\```

**第 2 轮（全部命中）**

\```
执行 0x1000:
  L1[1024] = {address=0x1000, mnemonic="ldr", ...}  ← L1 hit!
  → 直接用，不调 Capstone
执行 0x1004:
  L1[1025] = {address=0x1004, mnemonic="ldr", ...}  ← L1 hit!
  → 直接用
执行 0x1008:
  L1[1026] = {address=0x1008, mnemonic="br", ...}   ← L1 hit!
  → 直接用
这一轮 Capstone 调用次数 = 0。
\```

**第 3 轮到 一亿轮：全部 L1 hit，`Capstone` 调用次数 = 0。**

### L2 又做了啥？

举个冲突的例子。假设 `OLLVM` 有两个 Basic Block，地址恰好冲突（算出来的 L1 格子编号一样）：

- `Block_A` 的指令地址: `0x00001000` → `slot = (0x1000 / 4) & 0x7FFFFF = 1024`
- `Block_B` 的指令地址: `0x02001000` → `slot = (0x2001000 / 4) & 0x7FFFFF = 1024` ← 一样！

执行过程：

**第 1 步：执行 `Block_A` 的 `0x00001000`**

\```
L1[1024] = 空 → Cache miss → 调 Capstone 得到 "mov x0, x1"
→ 存入 L1[1024] = {addr=0x00001000, "mov x0, x1"}
\```

**第 2 步：跳到 `Block_B`，执行 `0x02001000`**

\```
L1[1024] = {addr=0x00001000, ...} → 地址不匹配！(0x00001000 ≠ 0x02001000)
→ L1 miss → 查 L2 → L2 也没有 → 调 Capstone 得到 "add x2, x3, #4"
→ 把 L1 里的旧条目（Block_A）降级到 L2：L2[0x00001000] = {addr=0x00001000, "mov x0, x1"}
→ L1[1024] 更新为：{addr=0x02001000, "add x2, x3, #4"}
       此时：L1[1024] = Block_B 的指令
             L2 里有   = Block_A 的指令
\```

**第 3 步：跳回 `Block_A`，又执行 `0x00001000`**

\```
L1[1024] = {addr=0x02001000, ...} → 地址不匹配！
→ L1 miss → 查 L2 → L2[0x00001000] 找到了！ ← L2 hit!
→ 直接使用，不用调 Capstone！
\```

如果没有 L2，第 3 步就要重新调 `Capstone`。`OLLVM` 的 Block 之间来回跳转，没有 L2 的话就会反复 miss 反复调 `Capstone`。**L2 就是干这个的——接住被 L1 挤掉的条目。**

实测上了这个方案，速度大幅提升；

## 3.3 引入的新问题与解决方案：`SMC`（Self-Modifying Code）

如果 SO 运行时，同一个地址的机器码发生变化，缓存的反汇编结果就会失效。解决方案是读取当前机器码并与缓存中的做比较：

```java
// 读取当前内存中的机器码（位运算代替 ByteBuffer）
byte[] bytes = backend.mem_read(address, size);
int machineCode = (bytes[0] & 0xFF) | ((bytes[1] & 0xFF) << 8)
                | ((bytes[2] & 0xFF) << 16) | ((bytes[3] & 0xFF) << 24);

// 与缓存比较
if (!disableSMC && cachedIns != null && cachedIns.machineCode != machineCode) {
    cachedIns = null;  // 代码被动态修改，缓存失效！
}
\```

实测这个方案，只会带来一部分性能损耗，对我个人而言是可以接受的；目前还没想到比较好的方案，主要是不动 `Unicorn` 的话……

其实，对于确认没有 `SMC` 的场景（绝大多数情况），可以通过 `setDisableSMC(true)` 跳过这个检查，这样连 `mem_read` 都省掉。

---

# 4. 性能短板二：Java 层对象分配的 GC 压力

## 4.1 问题分析

在解决了 `Capstone` 重复调用后，性能 Profiling 显示新的热点转移到了 **Java 对象分配**。上亿次回调中，以下操作产生了海量临时对象：

**1. `SMC` 检测中的 `ByteBuffer`**

```java
// 原版：每条指令都分配一个 ByteBuffer 来读取机器码
ByteBuffer buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
int machineCode = buf.getInt();  // 分配 HeapByteBuffer + DirectByteBuffer
\```

上亿次 × `ByteBuffer.allocate()` = 海量堆内存分配 → `Young GC` 频繁触发。

**2. `findModuleByAddress` 模块查表**

```java
// 原版：每条指令都查一次模块归属
Module module = memory.findModuleByAddress(address);
// 内部是 O(N) 遍历已加载模块列表
builder.append(String.format("[%-20s 0x%08x+0x%x]", module.name, module.base, offset));
\```

`String.format` 本身也会创建 `Formatter`、`StringBuilder`、`char` 数组等大量临时对象。

**3. `Hexdump` 格式化**

```java
// 原版
builder.append(String.format(" (%s 0x%x %d)", tag, absAddr, size));
// 每个 byte → String.format("%02x", b) —— 每次分配一个新 String
\```

## 4.2 解决方案

**1. 位运算替代 `ByteBuffer`**

```java
// 优化后：纯位运算，零对象分配
int machineCode = (bytes[0] & 0xFF) | ((bytes[1] & 0xFF) << 8)
                | ((bytes[2] & 0xFF) << 16) | ((bytes[3] & 0xFF) << 24);
\```

**2. 预计算前缀（Precomputed Prefix）**

将 `findModuleByAddress` 和字符串格式化**从热循环移到缓存构建时**。每个 `CachedInstruction` 在首次创建时就固化好完整的前缀文本：

```java
static class CachedInstruction {
    final String precomputedPrefix;  // 一次计算，永久复用

    CachedInstruction(Instruction ins, Emulator<?> emulator, int machineCode, long address) {
        // 仅在缓存 Miss 时执行一次
        StringBuilder pb = new StringBuilder();
        Module module = emulator.getMemory().findModuleByAddress(address);
        if (module != null) {
            pb.append('[').append(module.name).append(" 0x")
              .append(Long.toHexString(module.base)).append("+0x")
              .append(Long.toHexString(address - module.base)).append("] ");
        }
        pb.append("0x").append(Long.toHexString(address)).append(": \"")
          .append(this.mnemonic).append(' ').append(this.opStr).append('"');
        this.precomputedPrefix = pb.toString();
    }
}

// 热循环中：
instructionBuffer.append(cachedIns.precomputedPrefix);  // 直接追加预计算字符串
\```

同样的思路也应用到了寄存器映射：`Capstone` 的 `ins.mapToUnicornReg()` 和 `ins.regName()` 调用都被预计算并存入 `HashMap`，避免在热循环中重复通过 JNI 调用 `Capstone`。

**3. `HEX` 静态速查替代 `String.format`**

```java
private static final char[] HEX_ARRAY = "0123456789abcdef".toCharArray();

// 原版（每个 byte 分配一个 String）：
String.format("%02x", b & 0xFF);

// 优化后（零分配，直接查表追加）：
int v = data[i] & 0xFF;
sb.append(HEX_ARRAY[v >>> 4]).append(HEX_ARRAY[v & 0x0F]);
\```

---

# 5. 性能短板三：同步 I/O 阻塞

## 5.1 问题分析

这个短板不容易被想到，但实际上作用很明显，之所以不在前面讲，是因为这个其实太基础了，本来都不打算提。

经过前两步优化后，瓶颈转移到了 **I/O 写入**。原版的写入方式是：

```java
// 原版：每条指令直接写文件
PrintStream out = redirect != null ? redirect : System.err;
out.println(instructionText);  // 同步写入，带 synchronized 锁
\```

`PrintStream.println()` 内部有 `synchronized` 锁。上亿次同步写入意味着**上亿次锁获取/释放**。而且文件 I/O 本身就有系统调用开销。

## 5.2 解决方案：异步批量写入管线

\```
┌─────────────────────────────────────────────────────────────┐
│  Emulation Thread (热循环)                                   │
│  hook() → 攒入 asyncBlockBuffer (8MB StringBuilder)          │
│  每 50,000 行批量 put 到 logQueue                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ logQueue.put() (一次锁)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  logQueue (LinkedBlockingQueue, 容量 100,000)                │
└───────────────────────────┬─────────────────────────────────┘
                            │ logQueue.take()
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Logger Thread (异步 I/O)                                   │
│  从队列取出大块文本 → 一次性写入 PrintStream/文件              │
└─────────────────────────────────────────────────────────────┘
\```

代码如下：

```java
// 8MB 批处理缓冲区
private final StringBuilder asyncBlockBuffer = new StringBuilder(8_388_608);
private int linesInBlock = 0;

// 攒够 50000 行再 put 一次（将锁获取频率降低 50000 倍）
private void checkFlushAsyncBlockBuffer() {
    if (this.linesInBlock > 50_000) {
        logQueue.put(this.asyncBlockBuffer.toString());
        this.asyncBlockBuffer.setLength(0);
        this.linesInBlock = 0;
    }
}

// 独立的 I/O 线程
this.loggerThread = new Thread(() -> {
    while (true) {
        String msg = logQueue.take();
        if (POISON_PILL.equals(msg)) break;
        out.println(msg);  // 只有这一个线程做文件写入
    }
});
\```

此外，我们还加了函数级别的跟踪，后面会提到；其中，函数调用日志（`Call`/`Ret` 的分隔线）也被重定向到 `asyncBlockBuffer`。原版中 `Call`/`Ret` 的输出是通过独立的 `PrintStream` 直接写的，在多线程批处理模式下，会导致函数调用链与底层汇编指令的**时序错乱**。新版通过 `queueOut`（一个伪 `PrintStream`，实际追加到 `asyncBlockBuffer`）统一了所有输出的序列化：

```java
private final PrintStream queueOut = new PrintStream(...) {
    @Override
    public void println(String s) {
        asyncBlockBuffer.append(s).append('\n');
        linesInBlock++;
        checkFlushAsyncBlockBuffer();
    }
};
\```

---

# 6. `Trace` 格式优化

在性能问题解决后，顺便大幅增强了 `Trace` 的语义可读性吧。加了这些功能实际上会拖慢速度，但是由于我们速度很快了，所以不差这点了，要更多侧重分析方便性了；

### 6.1 常用开发函数自动语义解析

引入了 `TraceCallParser` 接口和四个默认实现，这样大家也可以自己改格式：

| Parser | 覆盖范围 | 示例输出 |
|-|-|-|
| `DefaultJniParser` | 全部 230+ JNI 函数 | `[JNI] JNIEnv->FindClass("com/example/Sign")` |
| `DefaultLibcParser` | 100+ libc 函数 | `libc.so::snprintf(0x7ff00100, 256, "%s-%d", "key", 42)` |
| `DefaultLibcppParser` | C++ `new`/`delete` | `libc++::operator new(1024)` |
| `DefaultSyscallParser` | Linux syscall | `svc openat(-100, "/proc/self/maps", 0, 0)` |

这一点大家仔细 `trace` 体验吧，这东西讲了也没啥价值，就是如何通过 `PLT`/`GOT` 表获取符号的事情，其中 ARM32 和 ARM64 的实现方式还不太一样，本来都打算懒得支持 ARM32 了，但是想了一下既然要开源，就都做好吧；

### 6.2 JNI 上下文自动追踪

\```
=============== -> call: [JNI] JNIEnv->FindClass("com/example/utils/CryptoHelper") =================
  ... 汇编指令 ...
=============== <- [JNI] JNIEnv->FindClass("com/example/utils/CryptoHelper") ret: 0x15 class com/example/utils/CryptoHelper =================
=============== -> call: [JNI] JNIEnv->GetStaticMethodID(0x15 (com/example/utils/CryptoHelper), "sign", "(Ljava/lang/String;)Ljava/lang/String;") =================
\```

返回值中的 `jclass`/`jmethodID` 会被缓存到 `jniIdMap`，后续使用这些 ID 的调用会自动附上对应的类名/方法签名。

### 6.3 `Hexdump` 打印

针对 `ld`/`st` 指令操作的绝对地址，进行内存 `hexdump` 打印，这样分析时可以根据值最早出现去追踪，相当于就是类似龙哥 `DataSearch` 的插件吧，这里除了 `hexdump` 我还贴心的打印了大端序，因为这是个实际使用的小痛点，哈哈哈哈。

### 6.4 Fluent API 配置开关

```java
emulator.traceCodeText(begin, end, outputFile)
    .setDisableSMC(true)         // 无自修改代码时跳过 SMC 检测，省掉 mem_read
    .setDisableHexdump(true)     // 不需要内存 Hexdump 时关闭
    .setDisableFunctionCall(true); // 不需要语义解析时关闭（纯汇编模式）
\```

---

# 7. 当前剩余的改进空间

经过以上优化，**Java 层已经基本不再是瓶颈了**。但仍然存在一些改进空间，这里分析一下：

## 7.1 JNI 边界穿越开销

无论 Java 层多快，**每条指令都要从 C/C++ 引擎穿越到 Java 层**这件事本身就有不可消除的开销：

\```
ARM 指令执行 → Unicorn C 引擎检测到 CodeHook → JNI 回调 → Java hook() → JNI 返回 → 继续执行
\```

每条指令的回调中，还需要读取寄存器的当前值（用于显示变化）。每次 `backend.reg_read()` 也是一次 JNI 调用。一条 `add x0, x1, x2` 就需要读 3 个寄存器，一亿条指令 × 平均 3 次 `reg_read` = **3 亿次 JNI 调用**。

**可能的解决方向：**

- **Native 层批量处理**：将反汇编和格式化逻辑迁移到 C 层，在 Native 侧完成批量格式化后，再通过一次 JNI 调用传回大块文本。彻底消除逐指令的 JNI 穿越。
- **批量寄存器读取 API**：一次 JNI 调用读取所有需要的寄存器值，返回一个 `long[]` 数组，而不是逐个读取。

## 7.2 文件 I/O 吞吐的物理上限

上亿行 `Trace`，由于写入的字节过多，即使用了异步批量写入，磁盘的顺序写入带宽仍然是一个物理上限。

**可能的解决方向：**

- **二进制 `Trace` 格式**：用紧凑的二进制格式记录（只存地址 + 寄存器增量），后处理再还原为可读文本。这个我已经做好了一版，但是我的桌面端做的还不够好，而且现在也有开源的trace-ui了。这里也有点小私心，本身我也不打算开源的，留着自己用就行
- **实时压缩**：对输出流做 `ZSTD` 流式压缩，`Trace` 日志的重复模式极多，压缩比通常 10:1 以上。
- **`Trace` 过滤**：通过 `traceBegin`/`traceEnd` 范围限制 + 函数级白名单机制，只追踪感兴趣的代码区域，从源头减少数据量。这一点一般是用户自己控制的

## 7.3 `Unicorn` 引擎本身的模拟速度

`Unicorn` 是基于 `QEMU` 的翻译执行引擎，每条 ARM 指令需要先翻译成 TCG IR，再翻译成宿主机指令。这个翻译 + 执行的过程本身就比原生执行慢 **10~100 倍**。如果后续能解决这个问题，或者在宿主机上随便跑arm指令，那么我个人觉得速度就不再是问题了；

---

如果看到这里说明你对我的文章也是认可了，可以关注我的同名id b站/公众号/看雪，也可以进入b站主页的qq群。

这里再打个广，挣点米吧，如果还想要深度交流学习的话，可以加入我的[知识星球](https://t.zsxq.com/N8xEH)。

下一期，我会用几个冷门对抗案例，比如：neon指令带来的无限debugger？加壳，抹符号的so加载不了？然后在我的unidbg中解决这几个问题；

---

# 回复

## 回复 by xianhuimin (#2)

*2026-3-30 15:06*

666

## 回复 by fjqisba (#3)

*2026-3-30 15:13*

看看大手子是怎么追踪的

## 回复 by Zepp7289 (#4)

*2026-3-30 15:28*

tql

## 回复 by dxasqw (#5)

*2026-3-30 15:31*

666

## 回复 by XCicada (#6)

*2026-3-30 15:35*

tql

## 回复 by mb_ldbucrik (#7)

*2026-3-30 15:37*

向大佬学习

## 回复 by 五彩斑斓的黑 (#8)

*2026-3-30 16:04*

666

## 回复 by wx_插曲 (#9)

*2026-3-30 16:10*

666

## 回复 by godiand (#10)

*2026-3-30 16:34*

666

## 回复 by xifgg (#11)

*2026-3-30 16:37*

666

## 回复 by mb_asiwnxyv (#12)

*2026-3-30 16:45*

感谢分享

## 回复 by mb_tkijjroi (#13)

*2026-3-30 16:50*

666

## 回复 by JiangNight (#14)

*2026-3-30 16:55*

tql

## 回复 by lackone (#15)

*2026-3-30 17:21*

66666

## 回复 by 拍拖 (#16)

*2026-3-30 17:59*

感谢分享

## 回复 by 飆汗吉米 (#17)

*2026-3-30 18:39*

666

## 回复 by iaoedsz2018 (#18)

*2026-3-30 18:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  fjqisba](https://bbs.kanxue.com/user-729528.htm)
>  看看大手子是怎么追踪的
>

啊？是大手子啊？

## 回复 by 4Chan (#19)

*2026-3-30 19:10*

666

## 回复 by jyotidwi (#20)

*2026-3-30 20:52*

Thanks

## 回复 by 墨穹呢 (#21)

*2026-3-30 20:57*

感谢分享

## 回复 by 啊你好哇123 (#22)

*2026-3-30 23:51*

学习学习

## 回复 by 南行 (#23)

*2026-3-30 23:56*

tql

## 回复 by buluo533 (#24)

*2026-3-31 07:59*

tql

## 回复 by adnin (#25)

*2026-3-31 08:30*

tql

## 回复 by MiTongZhen (#26)

*2026-3-31 08:50*

感谢分享

## 回复 by huangjw (#27)

*2026-3-31 08:50*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by kingking888 (#28)

*2026-3-31 09:06*

666

## 回复 by lixianhuei (#29)

*2026-3-31 09:14*

666

## 回复 by dob_C (#30)

*2026-3-31 09:33*

感谢分享

## 回复 by maxcl (#31)

*2026-3-31 09:40*

666

## 回复 by 军哥i (#32)

*2026-3-31 09:50*

tql

## 回复 by mb_pesxllvn (#33)

*2026-3-31 09:51*

666

## 回复 by tonykros (#34)

*2026-3-31 10:03*

666

## 回复 by mb_euhyowpw (#35)

*2026-3-31 10:22*

666

## 回复 by 零_721409 (#36)

*2026-3-31 10:32*

6666

## 回复 by mb_gcjwsflo (#37)

*2026-3-31 11:30*

tql

## 回复 by mb_pmgifpme (#38)

*2026-3-31 11:45*

1

## 回复 by chengdrgon (#39)

*2026-3-31 11:58*

感谢分享

## 回复 by mb_qimctavn (#40)

*2026-3-31 12:45*

6

## 回复 by fangliangz (#41)

*2026-3-31 14:37*

666

## 回复 by Imxz (#42)

*2026-3-31 14:55*

rbq

## 回复 by mb_ysikfhxt (#43)

*2026-3-31 15:01*

666

## 回复 by puppet_w (#44)

*2026-3-31 15:05*

66

## 回复 by 嘉然Daniel (#45)

*2026-3-31 15:05*

如何跟踪先后加载的多个so模块，需要指定不同的保存文件吗，还是可以输出到同一个文件

## 回复 by Cr_Ring (#46)

*2026-3-31 15:12*

6666666666

## 回复 by shush (#47)

*2026-3-31 15:18*

.

## 回复 by mb_uzmffdbw (#48)

*2026-3-31 16:15*

666

## 回复 by mb_ykavguun (#49)

*2026-3-31 17:09*

tql

## 回复 by wx_L_ (#50)

*2026-3-31 17:21*

tal

## 回复 by supyuan (#51)

*2026-3-31 18:30*

666

## 回复 by FMNS (#52)

*2026-3-31 20:41*

6666

## 回复 by 铭天星 (#53)

*2026-3-31 20:58*

666

## 回复 by xhyeax (#54)

*2026-3-31 22:05*

更换底层引擎为MacOS的Hypervisor，性能提升也很大。

## 回复 by 呆萌的小白 (#55)

*2026-4-1 08:39*

已收藏

## 回复 by 随风而行aa (#56)

*2026-4-1 10:20*

看看

## 回复 by x1a0f3n9 (#57)

*2026-4-1 13:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  嘉然Daniel](https://bbs.kanxue.com/user-982402.htm)
>  如何跟踪先后加载的多个so模块，需要指定不同的保存文件吗，还是可以输出到同一个文件
>

加上了，需要pull最新的commit；使用的话，类似下面这样就行，会自动识别指定so
emulator.traceCodeText(new String[]{ "libdcn_encrypt.so", "libdcn_dynamic.so" }, "apks/xxx/3.69.30.3/trace_multi_modules.txt");

## 回复 by x1a0f3n9 (#58)

*2026-4-1 13:23*

>
> [xhyeax](https://bbs.kanxue.com/user-691226.htm)
>  更换底层引擎为MacOS的Hypervisor，性能提升也很大。
>

是嘛？我这边试了5次，好像没有Unicorn2快，从40s到70-80s，慢了快一倍了； 我是win

## 回复 by MaYil (#59)

*2026-4-1 15:25*

感谢分享

## 回复 by lizhenzhe (#60)

*2026-4-1 16:18*

tql

## 回复 by xhyeax (#61)

*2026-4-1 17:09*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  是嘛？我这边试了5次，好像没有Unicorn2快，从40s到70-80s，慢了快一倍了； 我是win
>

需要使用arm64芯片的MacOS，因为不用做指令集转译。

## 回复 by 永恒梦魇 (#62)

*2026-4-1 17:28*

666

## 回复 by mb_ssjlfpnk (#63)

*2026-4-1 20:14*

学习一下

## 回复 by qiusuper (#64)

*2026-4-1 20:20*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by method (#65)

*2026-4-2 10:10*

1

## 回复 by 寻梦之璐 (#66)

*2026-4-2 10:27*

666

## 回复 by memoriaru (#67)

*2026-4-2 10:28*

学习学习

## 回复 by jdong (#68)

*2026-4-2 10:30*

111

## 回复 by Gryffindoss (#69)

*2026-4-2 10:48*

6666

## 回复 by 九黎 (#70)

*2026-4-2 11:13*

tql

## 回复 by mb_pvkxftjy (#71)

*2026-4-2 13:59*

谢谢谢谢

## 回复 by qqqiu (#72)

*2026-4-2 22:05*

1

## 回复 by JWPL (#73)

*2026-4-2 22:22*

感谢分享

## 回复 by mb_tjqabdvq (#74)

*2026-4-3 10:46*

学习 点赞 ![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by zz胡 (#75)

*2026-4-3 10:47*

66

## 回复 by ID蝴蝶 (#76)

*2026-4-3 11:28*

666

## 回复 by 天地一逆旅 (#77)

*2026-4-3 17:38*

tql

## 回复 by wuchonghua (#78)

*2026-4-4 04:00*

不错，安卓逆向就用这个

## 回复 by mb_tdoadyps (#79)

*2026-4-4 08:58*

tql

## 回复 by mb_ybvqgbkl (#80)

*2026-4-4 10:45*

6666666

## 回复 by fengvmu (#81)

*2026-4-4 19:53*

感谢分享

## 回复 by myios (#82)

*2026-4-4 21:50*

666

## 回复 by mb_rrwegvyc (#83)

*2026-4-4 22:20*

666

## 回复 by 小迷糊ddd (#84)

*2026-4-5 15:11*

感谢分享，认真学习。

## 回复 by jamlops (#85)

*2026-4-5 19:44*

感谢开源

## 回复 by 听我讲故事吗. (#86)

*2026-4-5 21:12*

tql

## 回复 by 我今年6岁 (#87)

*2026-4-5 21:23*

tql

## 回复 by mb_uvyukvot (#88)

*2026-4-9 17:07*

666

## 回复 by hygzs (#89)

*2026-4-13 14:39*

tql

## 回复 by git_14248bibinocode (#90)

*2026-4-13 15:19*

风老牛逼

## 回复 by mb_bbheqnma (#91)

*2026-4-13 15:43*

tql

## 回复 by zxxxxxe (#92)

*2026-4-13 15:45*

tql

## 回复 by spdfdfer (#93)

*2026-4-14 14:28*

tql

## 回复 by whydbg (#94)

*2026-4-15 21:23*

感谢分享

## 回复 by A0tem (#95)

*2026-4-15 21:24*

恩师

## 回复 by tjytjy (#96)

*2026-4-16 10:39*

tql

## 回复 by mb_xflcgdik (#97)

*2026-4-16 11:32*

666

## 回复 by pannifushe (#98)

*2026-4-16 16:35*

1111111111111111111

## 回复 by shuangmou (#99)

*2026-4-17 19:33*

感谢大手子分享

## 回复 by mb_paopxhtx (#100)

*2026-4-19 14:14*

学艺一下

## 回复 by mb_ezphxtar (#101)

*2026-4-20 11:51*

66666666

## 回复 by A0tem (#102)

*2026-4-20 15:37*

再顶一下

## 回复 by xmanYang (#103)

*2026-4-22 22:09*

学习大佬的思路

## 回复 by TkBinary (#104)

*2026-4-22 22:17*

是真的强.开个分支单干吧.

## 回复 by mb_cehqmdor (#105)

*2026-4-23 14:53*

667

## 回复 by mb_rbixrkdo (#106)

*2026-4-25 08:05*

学习

## 回复 by mb_ffsfxcfz (#107)

*2026-4-25 16:41*

adnin
  25 楼
tql

## 回复 by mb_ckwbzclg (#108)

*2026-4-25 19:01*

111

## 回复 by mb_aimnntrv (#109)

*2026-4-28 11:21*

tql

## 回复 by wx_栀_271 (#110)

*2026-4-28 12:00*

谢谢分享

## 回复 by wx_栀_271 (#111)

*2026-4-28 12:00*

谢谢分享

## 回复 by console_ (#112)

*2026-4-29 10:28*

1

## 回复 by console_ (#113)

*2026-4-29 10:28*

1

## 回复 by console_ (#114)

*2026-4-29 10:29*

1

## 回复 by console_ (#115)

*2026-4-29 10:29*

1tql

## 回复 by Thehepta (#116)

*2026-4-29 11:02*

1

## 回复 by tlsn (#117)

*2026-4-29 11:06*

666

## 回复 by ak8888 (#118)

*2026-4-29 21:19*

高手5555555

## 回复 by dsr000 (#119)

*2026-5-3 11:37*

565

## 回复 by mb_ofkncgmb (#120)

*2026-5-4 20:43*

666

## 回复 by wx_小白_266 (#121)

*2026-5-5 01:34*

tql

## 回复 by sorely (#122)

*2026-5-9 00:26*

666

## 回复 by shmilyaxy (#123)

*2026-5-9 11:56*

666

## 回复 by MsScotch (#124)

*2026-5-9 12:13*

tql

## 回复 by Bonquer (#125)

*2026-5-11 15:16*

tql

## 回复 by leijeo (#126)

*2026-5-15 00:38*

666

## 回复 by mb_rtyzyhmr (#127)

*2026-5-15 09:59*

tql

## 回复 by maomaolk (#128)

*2026-5-15 12:21*

tql

## 回复 by 086Love (#129)

*2026-5-15 18:07*

学习

## 回复 by 嘎嘎真的很棒 (#130)

*2026-5-17 20:43*

tql

## 回复 by 嘎嘎真的很棒 (#131)

*2026-5-17 20:43*

tql

## 回复 by 学计算机睡觉 (#132)

*2026-5-22 11:29*

tql

## 回复 by didiid (#133)

*2026-5-22 11:43*

tql

## 回复 by wx_北极星_493 (#134)

*2026-5-24 18:57*

看看

## 回复 by mb_ofgyxagz (#135)

*2026-5-24 20:43*

看看

## 回复 by mb_etrbkelx (#136)

*2026-5-24 22:37*

学习学习

## 回复 by mb_zmtxrnca (#137)

*2026-5-25 12:01*

6

## 回复 by ycdear (#138)

*2026-5-27 12:46*

111

## 回复 by euw (#139)

*2026-5-27 16:21*

qiang

## 回复 by mb_qqihqaoo (#140)

*2026-5-29 13:03*

666666

## 回复 by mb_sezgvuqb (#141)

*2026-5-31 22:11*

111

## 回复 by 小木马 (#142)

*2026-6-2 20:18*

666

## 回复 by merryfish (#143)

*2026-6-2 20:30*

tql

## 回复 by 中文fjja (#144)

*2026-6-2 21:31*

感谢你分享这么好的资源

## 回复 by mb_nggigxxl (#145)

*2026-6-5 02:38*

666666

## 回复 by 呼吸24K纯氧 (#146)

*2026-6-5 09:05*

感谢分享

## 回复 by Mr.ChenX (#147)

*2026-6-6 12:54*

666

## 回复 by 祝今朝 (#148)

*2026-6-7 23:31*

666

## 回复 by mb_agxdcibq (#149)

*2026-6-7 23:40*

111

## 回复 by wx_kx29662 (#150)

*2026-6-8 02:31*

666

## 回复 by Tanuyoki0 (#151)

*2026-6-8 02:43*

666

## 回复 by mb_ugnawvja (#152)

*2026-6-8 15:35*

tql

## 回复 by mb_mtevsvve (#153)

*2026-6-8 17:34*

666

## 回复 by veluboii (#154)

*2026-6-15 22:39*

666

## 回复 by wx_无法回头的伪装 (#155)

*2026-6-16 14:59*

6666

## 回复 by Freax (#156)

*2026-6-16 15:49*

tql

## 回复 by @NoBody (#157)

*2026-6-18 10:32*

你好，我实现了一套新的trace方法可以几乎无损跟踪所有堆数据读写和函数调用，核心在于不要用函数进行保存数据，至于如何区分不同线程的数据只需要几条指令就分开保存，我也尝试了一种新的方法，按照传统的或者开源的算法是没法实现这种级别的跟踪的，速度会非常严重干扰程序运行，现在只需要800元就可以出售我的系统源码，我的tel:nobody_ji

## 回复 by mb_gnsvqbzz (#158)

*2026-6-19 12:30*

tql

## 回复 by 浅笑心柔 (#159)

*2026-6-19 14:42*

你的帖子非常有用，感谢分享！

## 回复 by mb_cbgtaveo (#160)

*2026-6-23 01:48*

6666666666666666666

## 回复 by 宛枫 (#161)

*2026-6-30 02:41*

感谢分享

## 回复 by 西埔 (#162)

*2026-7-20 18:00*

严肃学习

## 回复 by mb_svgkmzvp (#163)

*2026-7-20 21:18*

tql

## 回复 by Midsw (#164)

*2026-7-21 02:51*

mark tql

## 回复 by 木魚· (#165)

*2026-7-21 14:51*

6666666666

## 回复 by MikotoDev (#166)

*2026-7-22 17:23*

tql

## 回复 by ikunnn (#167)

*2026-7-25 20:29*

11111111111

## 回复 by 阳光宝贝 (#168)

*2026-7-27 23:29*

感谢分享

## 回复 by Gypsophilazj (#169)

*2026-7-28 10:05*

tql

## 回复 by BlackMaGou (#170)

*2026-7-31 04:54*

给风佬顶一下

## 回复 by jianxcao (#171)

*2026-7-31 09:54*

666

## 回复 by mb_wzxcpnsa (#172)

666

## 回复 by wx_宇克鴻 (#173)

Thanks

## 回复 by haaYv (#174)

nb
