---
title: '[原创] Android 内核无痕 Hook 框架设计思路和避坑指北'
url: https://bbs.kanxue.com/thread-292066.htm
tid: 292066
author: SharkFall
date: '2026-07-18'
tags: [Android安全, 原创, 基础理论, 逆向分析, 程序开发, 源码框架, 工具脚本, 其他]
crawled_at: '2026-07-31T14:59:55+08:00'
replies: 197
---

## 写在前面

拜读完珍惜佬写的 [Android内核无痕Hook理解和感悟](https://bbs.kanxue.com/thread-290718.htm) 文章以后, 受益匪浅 !!!

非常感谢珍惜佬的文章, 解释的非常清楚, 并且给出了很多实现细节, 非常值得学习和借鉴 !!!

经段一段时间的摸索, 终于完整实现了珍惜佬文章中的无痕 Hook 框架, 这篇文章记录一下整体的设计思路和技术方向，顺便聊点踩坑经历。

整个框架的所有无痕能力都是基于 APatch 模块提供的内核 Hook 能力实现, 感谢 [APatch](https://github.com/bmax121/APatch) !!!

还要感谢 GitRoy 大佬提供的技术支持 !!!

传统 Hook 能力的弊端这里就不提及了, 珍惜佬已经讲的很清楚了, 在现在的高强度对抗中, 传统 Hook 能力已经有些不足了, 所以我们需要一种新的 Hook 能力来对抗现在的各种高强度检测手段.

所以 **无痕 Hook** 诞生了 !!!

## 框架能力 & 架构

### Hook & Trace & MemRW & ?

既然从头造轮子, 那就一次搞定目前的需求吧, 所以框架覆盖了以下方向, 下面会附上原理和一些方案

- 模块化注入库
- Zygote 注入 (用于在 App 启动后分发 Hook)
- Inline Hook (基于 Shadow Page 方案)
- 基于指令插桩的寄存器快照记录 (基于 Shadow Page 方案)
- 指令插桩支持 Before & After 回调 (基于 Shadow Page 方案)
- HWBP 断点 (基于直接操作 ARM64 调试寄存器, 绕过 perf_event 子系统)
- VMA Less 内存分配 (Maps 不可见)
- Art Hook (基于 Shadow Data Page 方案)
- VMA Dump (内核直接遍历目标进程 VMA 链表, 不经 `/proc/maps`, 无痕读取)
- 内存读写 (内核侧走目标页表, 不经 ptrace/procfs, 支持跨进程)
- 内核态 Trace (基于 CPU 硬件单步 `MDSCR_EL1.SS` + `SPSR.SS`, 每条指令触发 SS 异常采集全量寄存器)
- 用户态指令模拟 Trace (基于 dbi 引擎全部走幽灵内存隐藏)
- 符号解析 (直接解析ELF 符号表, 不经 `dl_iterate_phdr`, 用于 Trace 反查符号 / Hook 定位)
- 反调试对抗 (内核层拦截 `ptrace`, 硬件调试寄存器假账本欺骗)
- PC 管控台 (ghost-console + agent 翻译适配层, 设备侧事件 push + 控制 RPC 多路复用)
- DEX 动态加载 (内存字节注入 Java 类, 不落盘)
- Binder / Linker 拦截 (Shadow Hook 拦截 Binder 事务与 dlopen, 零 ArtMethod 改动)
- SO 早期生命周期 & JNI Trace (解决 SO 构造函数早于模块 hook 的时序矛盾)
- 花指令对抗 (仿真跟随间接分支, trace 日志还原真实执行路径)
- Daemon 热重载 (不重启 Zygote 热替换 Daemon)
- 跨 Fork 子进程继承 (VMA-less PTE 不被 fork 复制, 需手动克隆)
- 模块版本兼容 (编译期声明 API 版本约束)
- Dex Dump (感谢 FART 的脱壳思路)
- and more ...

### GhostHook 架构全景

先上一张整体架构图，感受一下模块关系:

```python
┌─────────────────────────────────────────────────┐
│              Manager App (EL0)                   │
│   KPM 加载 / 模块管理 / 注入配置 / 事件日志       │
└──────────────────────┬──────────────────────────┘
                       │ syscall (注入配置同步 / 事件轮询)
═══════════════════════╪═══════════════════════════ EL0/EL1
                       ▼
┌─────────────────────────────────────────────────┐
│            KPM 内核模块 (EL1)                     │
│  ┌─────────┬────────┬────────┬──────────────┐  │
│  │  HWBP   │ Shadow │ Ghost  │ Anti-Debug   │  │
│  │ Manager │  Page  │ Memory │ (假账本)      │  │
│  └─────────┴────────┴────────┴──────────────┘  │
│  ┌──────────┬──────────┬───────────────────┐    │
│  │ Mem R/W  │VMA Dump  │  CPU Trace (SS)   │    │
│  │(页表遍历) │(VMA链表) │  (MDSCR.SS+ring)  │    │
│  └──────────┴──────────┴───────────────────┘    │
└──────────────────────┬──────────────────────────┘
                       ▲ syscall（SDK 命令）
═══════════════════════╪═══════════════════════════ EL0/EL1
                       ▼ 返回值 / 事件（daemon 代理）
┌─────────────────────────────────────────────────┐
│              目标进程 (EL0)                       │
│                                                   │
│  Daemon SO (先加载, 幽灵内存中, 全局单例)          │
│  ┌─────────────────────────────────────────┐     │
│  │  GhostApi 函数表实现                     │     │
│  │  syscall 桥接 / 符号解析 / 用户 SO 加载   │     │
│  │  mako (ART Hook) / gtrace (仿真 Trace)   │     │
│  │  dex loader / binder & linker 拦截器     │     │
│  └──────────────────┬──────────────────────┘     │
│                     │ 传入 GhostApi*              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ 用户 SO A│ │ 用户 SO B│ │ 用户 SO C│ ← 幽灵内存│
│  │ghostEntry│ │ghostEntry│ │ghostEntry│          │
│  └──────────┘ └──────────┘ └──────────┘         │
└─────────────────────────────────────────────────┘
```

几个关键设计决策:

**Daemon 代理模式**：KPM 先往 Zygote 注入一个 Daemon SO，由它实现所有 SDK 逻辑并通过 syscall 与内核通信。用户模块只需要 include 一个纯声明头文件，通过 Daemon 传入的函数指针表调用能力。这样用户模块极轻量，多模块零代码重复，符号解析和 Hook 句柄管理都集中在 Daemon 一处。

**Zygote 注入**：Daemon SO 先注入到 Zygote 常驻，子进程 fork 后再按包名按需加载用户模块。常规 Zygote 状态随 fork 延续；VMA-less 映射及其运行状态由 fork 路径显式恢复，确保子进程得到独立、完整的运行环境。

**鉴权**：KPM 启动时生成 32 字节随机 session key，所有命令必须携带。Manager 端通过签名锚定自动获取 key——KPM 编译期内置 Manager 签名证书摘要，鉴权请求到达时在内核态校验调用者 APK 签名是否匹配，命中则缓存 uid 走 fast-path，整个过程无需提权。非 Manager 链路（agent / PC 调试）走人工配对码 fallback：一次性短码，限时消费，防止被测信道检测

## 核心技术方向

### 模块化注入 & Zygote 注入

整个注入链路完全在内核态完成：KPM 读取 Daemon SO 的 ELF 文件、解析重定位、通过页表操作映射幽灵内存、生成 bootstrap 跳板劫持 Zygote 执行流。Daemon 驻留 Zygote 后，fork 出的子进程按包名匹配配置，按需加载用户模块。

注入编排流程大致是：发现 Zygote PID → 读取 ELF → 内核态 ELF 链接器解析 PT_LOAD 段 → 幽灵内存映射到 Zygote 用户态地址空间 → 注册 NEEDED 库到符号解析器 → 重定位（IFUNC 自修复）→ 生成 ARM64 bootstrap 跳板 → `task_work_add` 劫持执行流。

用户模块（`.ghm` 文件）由 Manager App 管理，Daemon 通过自带的 ELF 链接器在幽灵内存中加载，调用 `ghostEntry(GhostApi*)` 入口。模块开发者只需 include 一个纯声明头文件，不链接任何 SDK 库。

Daemon 热重载的设计思路是"清场再进场"：先清除 Zygote 上所有已注册的 hook 状态、拆除旧 daemon 幽灵内存映射（含用户态残留 PTE 清理），再重新注入新版本。整个过程不重启 Zygote，开发期迭代效率高。

内核 linker 有个很坑的点, 是 ifunc 的处理, 要么daemon全自实现函数, 要么就模块入口做一下ifunc的修复, 再进行其它操作

### Shadow Hook (影子页)

这里要感谢 WX 大佬提出的 [Shadow Page 方案](https://bbs.kanxue.com/thread-290304.htm)。下面 Art Hook 使用的 Shadow Data Page 也是由这一思路延伸而来。

这是框架 **Inline Hook** 和 **指令插桩** 的核心方案。它为同一 VA 维护两份内容视图：original PFN 保存原始字节，shadow PFN 保存 hook 或插桩后的指令。执行与读取通过页权限和异常路由选择各自的视图：

- 执行态映射到 shadow PFN，权限为 `--x`（执行不可读）
- 普通数据读取触发 DABT 后，PTE 临时指向 original PFN，权限为 `r--`
- 读取完成后的下一次执行触发 IABT，PTE 恢复指向 shadow PFN

这种双视图设计将原始代码内容、实际执行内容和读取结果分开管理。常规代码读取路径基于 original PFN 计算校验值，执行路径则进入 shadow PFN；完整性观察的结果由观察路径及其可见范围共同决定。

页表切换以 `mm_struct` 为作用域。Shadow Page 管理器为同一地址空间内的线程和 CPU 统一维护 PTE 状态、TLB/cache 同步及异常上下文，使执行视图和读取视图在并发访问下保持一致。

关键前提是目标运行内核已启用并支持 FEAT_EPAN（PAN3），从而允许 EL0 使用 execute-only 映射（执行不可读的 PTE 权限组合）。设备能力由 KPM 在内核侧统一探测；用户态 feature ID 寄存器的可见字段随内核 ABI、版本和配置变化。

没有 EPAN 的设备使用单页 `---` 仿真路径：原页完全阻断，KPM 在 fault handler 中软件仿真执行指令。仿真器按层级覆盖：PC-relative 指令使用原始 PC 计算，普通 ALU 和访存指令由软件执行，SIMD/FP 等低频指令通过 backup 页单步兜底。

>
> [!WARNING]
>
>
> - EPAN 设备可使用执行/读取双视图；非 EPAN 设备需要评估内核侧指令仿真的覆盖范围和性能成本。
> - 能力探测、PTE 属性组合及异常处理路径均以目标内核的实际实现为准。
>
>
>

除了 Inline REPLACE，Shadow Page 还支持三种指令插桩模式：

- **LISTEN**：命中时发 PRE 事件（寄存器快照），单步原指令，SS 后发 POST 事件。纯监听，不阻断用户回调
- **INTERCEPT**：原指令执行后进入用户态 callback，回调通过调用线程栈帧中的寄存器上下文修改寄存器和续算 PC；回调上下文按线程保存，页表视图仍由 mm 级 Shadow Page 管理器协调
- **BEFORE_AFTER**：before callback 在原指令前执行，after callback 在原指令后执行，中间靠特定的内核通知机制协调原指令单步

插桩命中靠特定的未定义指令编码触发异常，handler 内根据 PC 偏移查表判断归属，不需要读取目标 VA 字节。

### 幽灵内存 (Ghost Mem)

这是整个框架隐身能力的根基。

常规 `mmap` 会在进程地址空间中创建 VMA 元数据，`/proc/self/maps` 按这些元数据枚举映射。仅过滤 `show_map_vma` 仍会留下可由 `mincore` 等路径观察到的映射行为。

幽灵内存的思路是绕过操作系统管理层，直接操作底层页表:

```python
function allocGhostMemory(pid, size):
    kernelPage = kernelVmalloc(size)          // 内核态分配物理页
    userVA = findUnusedVASpace(pid)           // 在用户态找一个 VMA 空洞
    // 直接修改目标进程页表，把 kernelPage 的 PFN 挂到 userVA
    // 手工拼装 PTE 属性位
    injectPte(pid->mm, userVA, kernelPage.pfn)
    flushTLB()                                 // 强制 CPU 认下这张"伪造地契"
    return userVA  // CPU 硬件认可，但 OS 管理层查无此 VMA
```

Ghost Mem 将映射信息分为硬件页表和 VMA 元数据两层：CPU 的 MMU 依据 PTE 完成访问，常规 VMA 链表枚举则不会返回这段地址。它的设计目标是收敛常规 VMA 枚举面；页表检查、映射一致性检查和内核态观察属于另一条可见性边界，需要在威胁模型中单独评估。

VMA-less PTE 还需要地址空间保护。`get_unmapped_area`/`mmap_region` 的选址依据 VMA，后续普通 mmap 可能选中已由 ghost PTE 占用的 VA。框架在 `mmap_region` 路径检查重叠，命中时返回 `-ENOMEM`（fail-closed）；其余会改变地址空间布局的路径也纳入目标内核的兼容性清单。

### HWBP 硬件断点

ARM64 CPU 内置了调试寄存器，你把目标地址写进去，CPU 每次执行时硬件比较器自动比对，命中就触发异常。整个过程不改一个字节的内存。

GhostHook 的 HWBP **不经过 perf_event 子系统**，而是在内核态直接操作 ARM64 调试寄存器并接管 debug 异常处理路径。这样做的好处是绕过了 perf_event 路径的检测面

**HWBP注册**。Linux 内核里进程和线程都是 `task_struct`，HWBP 绑定的是 TID 而非 TGID。只给主线程下断点，子线程走到目标地址根本不会报警。

**数量限制是个硬约束**：HWBP Manager 在初始化阶段读取目标 CPU 的调试能力，并结合内核已占用的槽位计算可分配断点数。执行断点数量随设备和运行环境变化，适合承载数量有限、需要低侵入监听的热点规则；大规模 Hook 由 Shadow Page 等页级机制承担。单条 HWBP 规则可用于追踪入参与返回值：

```python
// 概念：按 TID 维护的断点状态
function hwbpHandler(regs):
    state = stateFor(currentTid)
    if state.mode == ENTRY:
        captureArgs(regs)                 // 抓入参
        state.returnStack.push(returnAddr)
        moveBreakpoint(state.returnStack.top())
        state.mode = RETURN
    elif state.mode == RETURN:
        captureReturnValue(regs)          // 抓返回值
        state.returnStack.pop()
        moveBreakpoint(origAddr)
        state.mode = ENTRY
```

HWBP 状态和返回地址栈按 TID 隔离。递归与重入场景通过可用断点槽位或辅助机制维护嵌套层次；函数体中的普通指令保持原生执行，入口、返回及状态转换点由异常处理接管。

如果需要替换执行流（不只是监听），就得引入用户态跳板。跳板里有一个"关闸→调原函数→开闸"的流程，避免调原函数时重复触发断点死循环。LR 寄存器的保护是个极易踩坑的点——`BLR` 指令会覆盖 X30，得找个 callee-saved 寄存器（比如 X20）当"安全屋"暂存原始 LR。

### 指令重定位 (DBI)

有了 DBI 引擎以后就可以模拟执行指令实现 trace 了, 这里参考了 Frida Gum 的实现, 重构了一下, 感谢 Firda, 感谢开源 !!!

DBI 主要用于hook跳板的指令重定位和用户态指令模拟, DBI + PTE hook实现起来发现有很多坑, 我就改用shadow page 实现 hook了

把指令搬到新内存（shadow 页 / 跳板）后，所有 PC 相对寻址指令会算错地址。ARM64 指令 32 位塞不下完整 64 位地址，编译器大量使用相对寻址（`B`/`BL`/`CBZ`/`ADRP`/`LDR literal`）。搬到新地址后"向前跳 50 步"会跳到完全错误的地方。

重定位引擎需要逐条扫描，分类处理:

| 指令类型 | 处理方式 |
|-|-|
| `B`/`BL` (无条件跳转) | 超出射程时展开为间接跳转序列，64 位绝对地址硬编码在指令后 |
| `B.cond`/`CBZ`/`TBZ` (条件跳转) | 射程短必越界，需反转条件 + 远跳序列 |
| `ADRP`+`ADD` (PC 相对数据寻址) | 算出原始绝对地址，改写为 PC-relative 字面量加载 |
| `BLR` 系列 (带 PAC 的分支) | ARMv8.3 PAC 指令需特殊处理，避免污染 LR |
| 普通算术/访存 | 安全，原样拷贝 |

```python
// 概念：远跳展开
// 原始: B target  (4 字节, 射程有限)
// 展开为间接跳转序列:
//   保存暂存寄存器
//   从字面量池加载 64 位绝对地址
//   绝对跳转
//   .quad target    // 地址数据贴在后面
// 4 字节 → 多个指令槽，需要提前预算膨胀空间
```

指令膨胀后需要提前计算 `offset_map`（原始指令索引 → 克隆页偏移），这也是缺页异常路由时"传送地图"的数据来源。

### ART Java 方法 Hook

ART 虚拟机里每个 Java 方法对应一个 `ArtMethod` 结构体，其中 `entry_point` 指针指向编译后的机器码入口。传统 LSPlant 方案是替换这个指针指向自定义跳板，但反作弊会扫描所有 `ArtMethod` 的 `entry_point`，检查指针是否指向合法的 `boot.art` 或 OAT 文件区域。

GhostHook 的 ART 路径采用 **Shadow Data Page** 管理 `entry_point`。原始 ArtMethod 数据页保留原始字段，shadow 副本保存 hook 后的入口；DABT 发生后，访问来源决定本次访问看到的页视图，ART 运行时代码读取 shadow 页，其余读取路径读取原始页。

同页多条 ArtMethod 共享一张 shadow 页，并由增量 patch 管理。页内写入通过差分同步合并：hook 字段保持目标入口，其他字段跟随原始页更新。Shadow Data Page 复用 mm 级页表协调、并发访问和 TLB 一致性机制。

ART hook 引擎（mako）是独立 SHARED lib，不静态链入 Daemon SO。Manager 开关启用时把路径推到 KPM 缓存，Daemon 首次调用 `artHook` 时 lazy load 进幽灵内存。mako 的跳板池也走幽灵内存（经适配层注入 `ghostMalloc(RWX)`），不引入常规 maps 区段。shorty 取值用反射 `Method.getReturnType` + `getParameterTypes` 自拼，不依赖 libart 内部符号。ArtMethod 字段布局、偏移和可用入口由 Android/ART 版本适配层管理，未匹配版本走失败降级。

定位 Java 方法有两条路径：按 className + methodName + sig 走标准反射，或直接拿反射 `Method` 对象——后者跳过符号解析，适合 hook 隐藏 API 等不可经标准路径定位的方法。两条路径殊途同归，最终都落到 mako 的 ArtMethod 入口替换上。

反射类加载的设计思路是预解析：在 daemon 初始化时把反射链句柄全部解析为全局缓存，fork 继承，后续调用时不再触发 JNI 查找，把开销压到最小。

这里 mako hook 是我之前写的 art hook 框架, 选择用外挂加载的方式主要是考虑到两个原因:

- 1.内核态 linker 实现限制较多, 还有奇奇怪怪的问题, 所以换到 daemon 动态加载
- 2.按需加载, 节省内存, 提高效率, 不需要 hook 就可以不加载, 用户态 trace 加载模式也是这样设计的

### 无痕内存读写

跨进程内存读写支持无痕模式。内核侧直接走目标进程页表遍历，不经 `ptrace`、不经 `/proc/pid/mem`、不设 `TracerPid`。

```python
// 概念：跨进程内存读写
function readMem(pid, addr, buf, len):
    mm = getTaskMm(pid)        // 拿目标进程 mm
    walkPageTable(mm, addr)    // 遍历页表取物理页
    copyPageToBuf(buf, ...)   // 读页内容
    mmput(mm)                  // 释放 mm 引用（必须配对！）
    return 0
```

这条路径也用于 Shadow Page 的跨进程读取：读事务在页表锁、mm 级同步和多 CPU 可见性协议保护下，临时将 PTE 指向 original PFN，完成 GUP 取页后恢复执行视图。TLB 刷新与保留策略由后端按目标内核、CPU 拓扑和访问时序实现。

### VMA Dump

思路是让内核直接遍历目标进程的 VMA 链表，把结果写到调用方 buffer。整个过程不经 `/proc/maps`、不设 `TracerPid`、不创建文件。agent 用它构建 per-pid VMA 缓存，配合 ELF 符号表缓存做地址→符号的反查。

### 内核态 Trace (CPU 单步)

这是 Trace 的记录模式：在 debug 异常处理的 Software Step 分支中加入 trace 步进处理，对目标线程设置单步标志进入连续单步。每条用户态指令触发一次 SS 异常，handler 在异常上下文里采集 PC + 全量 GPR + SP + PSTATE + 时间戳，写入专用 trace ring buffer（覆盖最旧 + 丢弃计数），消费者分批取走。

```python
// 概念：CPU 单步 trace
function traceHandleStep(regs, session):
    if not inRange(regs.pc, session):
        return                  // 不在目标范围，跳过
    entry = { pc, x0..x30, sp, pstate, timestamp }
    ringWrite(session.ring, entry)
    if session.steps >= session.maxSteps:
        traceStop(session)      // 达到上限，停止
    else:
        rearmSingleStep()      // 重新 arm 单步
```

关键约束：`MDSCR_EL1.SS` 是 per-CPU 寄存器，目标线程被调度到其他 CPU 时 SS 会丢失。trace 期间必须把目标线程钉在单个 CPU 上（`set_cpus_allowed_ptr`），trace 结束后恢复原亲和性。

trace 的连续单步与框架其他单步消费者（HWBP 恢复单步、shadow BRK 单步、shadow read 单步、simulate backup 单步）共享同一个 `MDSCR.SS` 位。trace 在 SS 分发链中具有最高优先级，但不破坏其他机制的 one-shot 单步恢复。

### 符号解析

Daemon 内置符号解析器，读 ELF `.dynsym` 解析符号地址。不走 `dl_iterate_phdr`——幽灵内存中的 SO 不在动态链接器维护的 `link_map` 中，常规枚举不会包含它；因此需要自行维护加载模块与符号表信息。

符号解析用于两条路径：Hook 定位（按 SO 名 + 符号名找地址）和 Trace 符号化（批量解析 PC 对应的 `{soName, sym, offset}` 映射表，随 trace 帧推送到 PC）。

VMA 缓存经内核无痕读取，ELF 符号表缓存从磁盘文件解析一次后复用（优先全量符号表），排序后二分查找。

### 反调试对抗

反作弊检测 HWBP 的手段已经非常成熟，主要通过 `ptrace` 和 `perf_event_open` 施展"连环五步杀"：读寄存器查空位、满载占坑测试、读写一致性校验、越界诱导陷阱（故意设 7 个断点看是否返回 `-ENOSPC`）、主动触发测试。

应对思路是在内核层实现硬件调试寄存器的"假账本"：拦截 `ptrace` 对调试寄存器的读写请求，反作弊全程跟假账本交互，真实 CPU 物理寄存器不受干扰。假账本需要精确模拟内核行为——包括越界报错、读写一致性等，细节不到位反而暴露。

### 跨 Fork 子进程继承

Zygote 注入的 Daemon、跳板和 Shadow Page 使用 VMA-less PTE。Fork 处理器将它们视为显式继承对象：在目标内核验证过的 fork 窗口内，为子进程恢复所需映射、运行状态和元数据。

```python
kernel_clone
  └─ copy_process        ← 子进程 mm/页表已构造（VMA 复制完，但 VMA-less PTE 丢失）
     └─ wake_up_new_task(child)  ← KP hook 在此窗口安装子进程的 ghost PTE
```

四类对象的继承策略各不相同：

- **Ghost Mem**：给子进程分配独立物理页 + 私有拷贝 + 逐页独立 PTE。必须私有——直接共享父进程物理页会导致子进程写 daemon 静态数据污染父进程。
- **Shadow Page**：标记了 fork 传播的 hook 页克隆继承 shadow PTE；未标记的需暂停。
- **HWBP 规则**：按子进程的线程生命周期注册断点，并为每个 TID 维护独立状态和返回地址栈。
- **Instrument / Hook 元数据**：拷贝页内 hook/instrument 元数据（受 fork 传播标志门控）。

线程 clone（共享 mm）不需要克隆——只有新进程才需要安装 ghost 内存。

### DEX 动态加载

有时模块需要在目标进程注入自定义 Java 类——比如运行时生成的代理类或 Hook 回调类。设计上走内存 DEX 加载路线：dex 字节不落盘，直接在幽灵内存中包装为 ByteBuffer，反射构造 ClassLoader。

```python
// 概念：DEX 内存加载
function loadDex(dexBytes, size, useAppParent):
    ghostBuf = ghostMalloc(size, RW)     // 拷贝到独立幽灵内存
    byteBuffer = newDirectByteBuffer(ghostBuf, size)
    parent = useAppParent ? appClassLoader : null
    classLoader = new InMemoryDexClassLoader(byteBuffer, parent)
    return handle  // 后续 findClassFromDex / unloadDex
```

关键设计点：dex 字节先拷贝到独立的幽灵内存分配，使数据生命周期与用户 SO 的 ELF 映射解耦——直接包装指针会让 buffer 生命周期耦合 SO 映射，拷贝后 dex loader 自主管理，卸载时确定释放。

parent ClassLoader 的选择影响可见范围：挂载 App ClassLoader 可经委托解析 App/framework 类；隔离加载则只有 bootstrap 类 + 自身 dex 类可见。这条路径完全在 daemon 侧实现，与 ART hook 引擎是否启用无关。

### Binder / Linker 拦截器

这两类拦截器都基于 Shadow Hook 实现，不引入 GOT trampoline。Binder 路径直接拦截 `transactNative` 的 native 入口；Linker 路径通过 Bionic 版本适配层解析可用 dlopen 入口。两者的映射可见性以常规 VMA 枚举为边界，页表及内核态观察路径纳入独立的安全评估。

**Binder Transact 拦截**：shadow hook `transactNative` 的 native 函数地址，在 transact 前后按 interface token 分发 before/after 回调。ART 适配层负责按版本定位 ArtMethod 与 native 入口，不将任何字段偏移视为稳定 ABI。读取 interface token 依赖 libbinder.so / libutils.so 的 native 函数，因此由一层 Parcel 工具桥接。

```python
// 概念：Binder 事务拦截
function fakeTransactNative(data, reply, flags):
    token = readInterfaceToken(data)    // 经 Parcel 工具读取
    dispatchBefore(token, data, reply)  // 按 token 匹配 before 回调
    result = origTransact(data, reply, flags)
    result = dispatchAfter(token, result, data, reply)  // 可覆盖返回值
    return result
```

Binder 拦截当前覆盖 client 侧。服务端采用 C++ 虚函数分派，扩展服务端覆盖时需要解析具体实现目标或设置独立拦截点。binder call log 作为可选开关，默认关闭，避免热路径开销。

**Linker dlopen 拦截**：shadow hook linker 的可用 dlopen 入口，在 SO 加载前后按 lib name 子串匹配分发回调。内部符号名和调用链由 Bionic 版本适配层维护，未命中入口时该能力保持关闭。

两项能力均懒加载：首次调用才触发 init，per-process 独立，fork 后由映射继承处理器恢复。

### SO 早期生命周期 & JNI Trace

用户模块的 `ghostEntry` 在进程启动早期执行，目标 SO 则可能在后续才加载。SO 生命周期分为两段：ELF 的 `.init`/`.init_array` 由 linker 构造函数路径执行，`JNI_OnLoad` 由 ART 在 `dlopen` 返回后查找并调用。两段都位于 `System.loadLibrary` 的返回之前，框架为它们分别设置拦截点。

```python
进程启动
  -> daemon 加载用户 SO -> ghostEntry(api)     ← simTraceStart 只能在这里或之后
  -> App 代码执行
    -> System.loadLibrary("libfoo.so")
      -> dlopen -> link -> relocate
      -> call_constructors                       ← .init / .init_array 在此执行
      -> dlopen 返回
      -> ART 查找并调用 JNI_OnLoad
    -> App 后续调用 libfoo.so 的函数             ← simTraceStart 在这里才能 findSymbol
```

Linker 构造函数路径和 ART 的 `JNI_OnLoad` 路径各自建立拦截点。linker/ART 内部符号及调用链由版本特征识别；幽灵内存中的 SO 不在 `dl_iterate_phdr` 的常规枚举范围内，符号解析器据此维护独立的模块记录，并在需要时回退到完整 ELF 符号表。

JNI 动态注册的 trace 同理：JNIEnv 函数表中的 native 方法注册入口按固定偏移就能取到，无需解析 ART 内部符号，在注册时拦截匹配的方法即可 trace 其函数指针。

### 花指令对抗

目标 SO 使用花指令混淆控制流：在真实指令间插入 junk bytes，通过 `br x_reg`（间接分支寄存器）跳转到 SO 内部的真实代码地址。静态反汇编器看到 `br` 时无法解析目标地址，从 junk bytes 起点反汇编会产生错误指令序列。

GTrace 采用动态仿真执行的方案，天然跟随 `br` 跳转——trace 日志中的指令序列已经是去花后的真实执行路径。trace 日志通过标注内部分支目标和 PC 间断区间，使自动化分析工具可直接提取去花后的真实执行路径，无需从 PC 非连续推断。

### 多 Trace 并发

同一 SO 中不同函数的 trace 场景：先 `traceStart(funcA)` 再 `traceStart(funcB)`，之后 A 和 B 可能在不同时刻被调用。如果 per-trace 配置（writer、traceMode、memReadMode 等）存在全局变量中，第二次调用会覆盖前者的配置，导致 trace 数据写错文件。

解法是将 code handler 的 per-trace 配置从全局变量重构为 per-handle 上下文，通过仿真引擎的 userData 传递给所有 hook 回调，实现多 handle 独立运行。由于仿真执行是同步阻塞的，两个 trace 不可能真正并发，但 shadow hook 是异步触发的——per-handle 化后各自独立，互不干扰。

## 踩坑杂谈

这部分聊几个让人头疼的细节，给各位大佬省点时间。

**多页 `vmap` 的页数组构造**

多页幽灵内存使用 `alloc_pages` + `vmap` 时，页数组必须包含每一页对应的 `struct page`。`vmap` 按数组逐页建立内核虚拟映射；连续页分配需要正确展开每个 page 并逐页校验 PFN。一次 ELF 加载出现的 PFN 重复和 `missing DT_GNU_HASH`，最终定位为页数组/PFN 展开环节错误。当前实现使用 `vmalloc` 简化多页分配，并继续以 `vmalloc_to_pfn` 逐页校验映射结果。

**跳板池化后的 cache 维护范围**

早期每条跳板独占一整页 ghost 映射，浪费 87.5%~94% 物理页。改成每页 256B 切 16 槽的跳板池后，跳板 VA 不再页对齐。原有"整页 DC CIVAC + IC IVAU"如果以槽基为起点会越界刷到相邻映射。解法是所有 cache flush 范围改为按页对齐（刷整张池页，over-flush 相邻槽，注册非高频路径可接受）。

**异常上下文中的锁**

Hook 回调运行在异常上下文中，不能用 `spin_lock_irqsave`——它会操作 DAIF 寄存器，破坏 KP 跳板状态。必须用自定义的 LDAXR/STXR 原子锁来保护共享数据。

**`mm_users` 引用泄漏**

临时持有目标进程 `mm`（通过 `get_task_mm` 或等价内核符号）的代码，所有返回路径都必须 `mmput`。泄漏一个 `mm_users` 引用会阻止进程进入 `exit_mmap`，导致 ghost 映射无法清理，Android framework 在 SIGKILL 后仍认为旧 ProcessRecord 未死亡，后续启动被拒绝或卡 splash。这个排查起来非常非常非常非常非常非常非常痛苦...

**Fork 克隆必须私有拷贝**

子进程 fork 时，ghost 映射使用独立的 `vmalloc` + `memcpy` + 逐页 PTE，避免 daemon 静态数据跨进程共享。资源生命周期同时覆盖 fork、退出和 execve 的旧 mm 回收路径，并按目标 Android/Linux 内核调用链注册清理处理。

## 与传统方案的对比

下表比较三类方案的实现路径与工程约束。可见性、完整性和并发性均由具体观察路径、目标内核及运行时版本共同决定。

| 维度 | 传统 Inline Hook | 纯 HWBP | GhostHook 架构 |
|-|-|-|-|
| 代码页处理 | 原始 `.text` 直接改写 | 保留原始代码页 | original 页保留，shadow 页承载替换内容 |
| 完整性视图 | 读取和执行均为改写结果 | 读取和执行均为原始结果 | 读取视图为 original，执行视图为 shadow |
| Hook 数量 | 通常不受硬件槽位限制 | 由可用断点槽位决定 | 由页与元数据管理能力决定 |
| 映射元数据 | 跳板映射可见 | 通常无额外映射 | 常规 VMA 枚举不包含 ghost 映射 |
| 并发模型 | 修改窗口同步 | TID 状态隔离 | mm 级 PTE、TLB/cache 与异常状态协调 |
| 工程门槛 | 低 | 中 | 高（内核 + ARM64 指令集功底） |
| 调试寄存器 | 不依赖 | 受调试设施与检测面影响 | 按目标内核维护调试寄存器状态 |
| ART Hook 入口 | 改 `entry_point` 指针 | 可用性取决于实现 | Shadow Data Page 提供受控的入口视图 |
| Trace 能力 | 无 | 有限的断点事件 | CPU 单步 + 仿真双模式 |
| 跨进程读写 | 常见实现使用 ptrace | 无 | 内核页表遍历，不经 ptrace |
| DEX 动态加载 | 取决于实现 | 取决于实现 | 内存字节加载 DEX，不落盘 |
| Binder 拦截 | 常见实现使用 GOT hook | 不适用 | Shadow Hook `transactNative`，版本适配 |
| Linker 拦截 | 常见实现使用 PLT hook | 不适用 | Shadow Hook dlopen 入口，版本适配 |
| SO 早期 Trace | 取决于注入时机 | 不适用 | 分别覆盖构造函数与 `JNI_OnLoad` 路径 |
| 花指令对抗 | 不支持 | 不支持 | 仿真跟随 `br` 跳转 + junk bytes 标注 |
| Fork 继承 | 手动处理 | 不自动继承规则状态 | fork 路径恢复映射和状态 |
| Daemon 热重载 | 需重启 | 需重启 | 清 hook → 卸载 → 重新注入，不重启 Zygote |
| 性能 | 极快 | 快 | 异常与同步路径有额外开销，后续取决于实现 |

## 模块开发体验

对于写 Hook 模块的人来说，设计目标只有一个：极简。模块开发者只需 include 一个纯声明头文件，不链接任何 SDK 库，拿到一个函数指针表就能用全部能力。

```cpp
// 概念：用户模块入口
#include "ghosthook_sdk.h"

void ghostEntry(const GhostApi *api) {
    // Shadow Hook
    api->shadowHook("libc.so", "open", myOpen, &origOpen);

    // ART Hook / DEX 加载 / Binder 拦截 / trace ...
    // —— 全部通过同一个 api 指针表调用
}
```

所有 DBI/跳板/内存隐藏等底层细节全部由 Daemon + KPM 透明处理。模块编译为独立 `.ghm` 文件，由 Manager App 管理和分发。

## 写在最后

这个项目从设计到实现断断续续搞了挺久，踩的坑远比上面写的多。

内核态开发最大的痛苦不是逻辑复杂，而是调试成本——一个 PTE 属性位拼错了，手机直接黑屏重启，有时候 dmesg 提供的崩溃日志甚至无法定位

这套架构的价值在于把原始页、shadow 页和访问路径分层管理。传统 Inline Hook 直接改写目标代码；Shadow Page 则以双页视图承载执行和读取。围绕页表同步、运行时版本适配与资源生命周期建立完整约束后，这种分层能够为 Hook、插桩和 Trace 提供统一的内核侧基础设施。

项目还在持续迭代，后面有机会再聊聊更多细节。文中如果有描述不准确的地方，欢迎交流指正。

最后配几张图, 祝各位大佬实现顺利 !!!

![GhostHook Manager App](https://bbs.kanxue.com/ghost-hook-design/ghost-hook-manager-app.png)

![image](https://bbs.kanxue.com/ghost-hook-design/ghost-hook-module-demo.png)

![模块加载与 ART Hook 注册日志](https://bbs.kanxue.com/ghost-hook-design/ghost-hook-module-init.png)

![Ghost Trace 指令流跟踪日志](https://bbs.kanxue.com/ghost-hook-design/ghost-hook-trace-log.png)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/954363_ZPQ8BXY46QUD2ZM.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/954363_C6N788GHXBS3Q7C.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/954363_RCUSGHW7MWSSJPH.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/954363_ZQ7CY9DZK387BUN.webp)

---

# 回复

## 回复 by 珍惜Any (#2)

*2026-7-19 00:10*

火钳刘明

## 回复 by SharkFall (#3)

*2026-7-19 00:18*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>  火钳刘明
>

欢迎珍惜佬！

## 回复 by fuqiuluo73 (#4)

*2026-7-19 00:26*

火钳刘明

## 回复 by 钟白 (#5)

*2026-7-19 00:39*

牛牛牛牛，学习了！！

## 回复 by merryfish (#6)

*2026-7-19 00:44*

cool

## 回复 by xianhuimin (#7)

*2026-7-19 00:45*

666

## 回复 by mb_nkjfyhkg (#8)

*2026-7-19 01:51*

mark

## 回复 by SomeMx (#9)

*2026-7-19 01:53*

过来学习一下

## 回复 by PPKun (#10)

*2026-7-19 02:29*

大佬想问一下，你的实现支持art热页hook吗

## 回复 by FMNS (#11)

*2026-7-19 05:38*

666

## 回复 by mb_ldbucrik (#12)

*2026-7-19 06:46*

感谢分享

## 回复 by KerryS (#13)

*2026-7-19 07:11*

真狠啊

## 回复 by mb_qimctavn (#14)

*2026-7-19 07:38*

6

## 回复 by mb_cfjwplfo (#15)

*2026-7-19 08:36*

111

## 回复 by mb_cfjwplfo (#16)

*2026-7-19 08:37*

>
> [PPKun](https://bbs.kanxue.com/user-970983.htm)
>  大佬想问一下，你的实现支持art热页hook吗
>

应该不可以，大佬可以加个好友交流一下，我也是卡在了libart上，感觉不能dbi只能通过pte页表rw/x切换实现

## 回复 by SharkFall (#17)

*2026-7-19 09:18*

>
> [PPKun](https://bbs.kanxue.com/user-970983.htm)
>  大佬想问一下，你的实现支持art热页hook吗
>

用shadow page实现的hook，目前测试起来没什么问题

## 回复 by SharkFall (#18)

*2026-7-19 09:19*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  应该不可以，大佬可以加个好友交流一下，我也是卡在了libart上，感觉不能dbi只能通过pte页表rw/x切换实现
>

dbi hook实现起来坑太多了![image](https://bbs.kanxue.com/view/img/face/055.gif)，我放弃了，改用shadow hook实现的

## 回复 by mb_cfjwplfo (#19)

*2026-7-19 10:40*

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>  dbi hook实现起来坑太多了[em_055]，我放弃了，改用shadow hook实现的
>

理想化情况下dbi很牛比，但现实很骨感

## 回复 by mb_kjzusjxu (#20)

*2026-7-19 10:55*

666666666666666

## 回复 by SharkFall (#21)

*2026-7-19 10:58*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  理想化情况下dbi很牛比，但现实很骨感
>

![image](https://bbs.kanxue.com/view/img/face/055.gif)![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by mb_yvuzbfvo (#22)

*2026-7-19 11:11*

666

## 回复 by mb_pesxllvn (#23)

*2026-7-19 13:36*

666

## 回复 by 尤瑟努 (#24)

*2026-7-19 13:46*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_插曲 (#25)

*2026-7-19 16:17*

66

## 回复 by 墨穹呢 (#26)

*2026-7-19 16:40*

火钳刘明

## 回复 by Gryffindoss (#27)

*2026-7-19 18:48*

12312

## 回复 by 温泉划水鱼 (#28)

*2026-7-19 23:01*

66

## 回复 by mb_tewbhakr (#29)

*2026-7-20 01:00*

看看

## 回复 by Imxz (#30)

*2026-7-20 09:12*

tql

## 回复 by Zepp7289 (#31)

*2026-7-20 09:23*

tql

## 回复 by wx_范迪塞尔 (#32)

*2026-7-20 09:31*

666

## 回复 by 学计算机睡觉 (#33)

*2026-7-20 09:38*

666

## 回复 by 淡定小胖子 (#34)

*2026-7-20 11:13*

感谢分享，学习一下

## 回复 by git_71735namngsec-netizen (#35)

*2026-7-20 11:37*

666

## 回复 by lixianhuei (#36)

*2026-7-20 13:41*

666

## 回复 by mb_ysikfhxt (#37)

*2026-7-20 13:53*

111

## 回复 by GitRoy (#38)

*2026-7-20 14:08*

好强

## 回复 by SharkFall (#39)

*2026-7-20 14:50*

>
> [GitRoy](https://bbs.kanxue.com/user-762912.htm)
>  好强
>

![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)Roy佬

## 回复 by 辉煌科技 (#40)

*2026-7-20 14:57*

666

## 回复 by wx_Dispa1r (#41)

*2026-7-20 14:59*

1

## 回复 by amwpecel (#42)

*2026-7-20 15:22*

66666

## 回复 by 错过 (#43)

*2026-7-20 15:26*

cool

## 回复 by chaego (#44)

*2026-7-20 15:41*

瞅瞅

## 回复 by mb_yesvqzcy (#45)

*2026-7-20 15:47*

666

## 回复 by 逆天而行 (#46)

*2026-7-20 15:59*

一路走来 都是老师

## 回复 by mb_egojlewe (#47)

*2026-7-20 16:29*

牛

## 回复 by didiid (#48)

*2026-7-20 16:41*

666

## 回复 by Midsw (#49)

*2026-7-20 17:12*

Mark

## 回复 by anywhere杨 (#50)

*2026-7-20 17:22*

777

## 回复 by linkin5epk (#51)

*2026-7-20 17:29*

111

## 回复 by mb_ggnpkuap (#52)

*2026-7-20 18:45*

66

## 回复 by Aar0n (#53)

*2026-7-20 19:57*

希望后续开源

## 回复 by git_58319TheShuiLan (#54)

*2026-7-20 20:18*

666666666666666666666666

## 回复 by aii9917 (#55)

*2026-7-20 20:27*

666

## 回复 by iBa0 (#56)

*2026-7-20 21:15*

366

## 回复 by Botton (#57)

*2026-7-20 21:33*

学习

## 回复 by mb_tjqabdvq (#58)

*2026-7-20 21:49*

干货满满 学习点赞

## 回复 by drf520 (#59)

*2026-7-20 21:52*

66666666666666

## 回复 by DawnDotVip (#60)

*2026-7-20 23:00*

66

## 回复 by uni7corn (#61)

*2026-7-20 23:25*

感谢分享

## 回复 by mb_fnnjknab (#62)

*2026-7-21 00:49*

感谢

## 回复 by mb_kggsatxn (#63)

*2026-7-21 01:51*

学习一下

## 回复 by guardia (#64)

*2026-7-21 04:17*

666

## 回复 by huangjw (#65)

*2026-7-21 08:53*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 苏幻墨 (#66)

*2026-7-21 09:22*

学习一下...分析![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ifjlatem (#67)

*2026-7-21 09:52*

666

## 回复 by Nijika (#68)

*2026-7-21 10:15*

666

## 回复 by mb_zsmeyemp (#69)

*2026-7-21 10:19*

666

## 回复 by mb_xqpwqark (#70)

*2026-7-21 10:23*

666

## 回复 by wx_虚度守护 (#71)

*2026-7-21 10:34*

瑞思拜

## 回复 by fengyunabc (#72)

*2026-7-21 10:43*

感谢分享。

## 回复 by console_ (#73)

*2026-7-21 11:46*

66

## 回复 by ssafosl (#74)

*2026-7-21 15:46*

6

## 回复 by mb_cbgtaveo (#75)

*2026-7-21 16:17*

666

## 回复 by scllqk (#76)

*2026-7-21 16:37*

学习

## 回复 by ID蝴蝶 (#77)

*2026-7-21 16:41*

学习

## 回复 by 黑屏 (#78)

*2026-7-21 16:56*

66

## 回复 by mb_audxeeaj (#79)

*2026-7-21 16:58*

学习一下

## 回复 by YooHaa (#80)

*2026-7-21 16:58*

66

## 回复 by Vengeance (#81)

*2026-7-21 17:14*

666

## 回复 by mb_ggnpkuap (#82)

*2026-7-21 19:05*

请问会开源吗？

## 回复 by wx_三生三世 (#83)

*2026-7-21 19:15*

学习

## 回复 by 祝今朝 (#84)

*2026-7-21 19:22*

1

## 回复 by mb_hcadvceu (#85)

*2026-7-21 19:57*

谢谢分享

## 回复 by 幻生 (#86)

*2026-7-21 21:10*

????????

## 回复 by Snark (#87)

*2026-7-21 21:31*

11

## 回复 by mb_oqoqqkxl (#88)

*2026-7-21 21:36*

yiedy

## 回复 by kingking888 (#89)

*2026-7-22 00:49*

666

## 回复 by git_65827AvailablFrom (#90)

*2026-7-22 00:56*

666

## 回复 by 无视红绿灯 (#91)

*2026-7-22 09:00*

aaa

## 回复 by ulong9527 (#92)

*2026-7-22 09:24*

6

## 回复 by mb_nkgphjuz (#93)

*2026-7-22 09:55*

牛皮

## 回复 by 清风QingFeng (#94)

*2026-7-22 12:12*

66

## 回复 by mb_lfvhycml (#95)

*2026-7-22 13:43*

666

## 回复 by Friday_risa (#96)

*2026-7-22 14:24*

6666666

## 回复 by mb_sihvtppm (#97)

*2026-7-22 15:02*

6

## 回复 by mb_mildqryr (#98)

*2026-7-22 15:07*

666

## 回复 by mb_qztkkwxt (#99)

*2026-7-22 17:35*

学习

## 回复 by mb_qwgxafvv (#100)

*2026-7-22 21:15*

1

## 回复 by 过眼浮云 (#101)

*2026-7-23 00:03*

666

## 回复 by 狐狸黑斯 (#102)

*2026-7-23 00:41*

111

## 回复 by mb_zatexoyx (#103)

*2026-7-23 01:25*

666

## 回复 by 一只鸭子 (#104)

*2026-7-23 10:02*

有一个问题，检测不能直接去检测页权限吗？安卓默认代码段页内存也不会只读吧，这会不会是一个小漏点

## 回复 by SharkFall (#105)

*2026-7-23 11:10*

>
> [一只鸭子](https://bbs.kanxue.com/user-1003853.htm)
>  有一个问题，检测不能直接去检测页权限吗？安卓默认代码段页内存也不会只读吧，这会不会是一个小漏点
>

改的不是maps显示的页权限

## 回复 by mb_uvyukvot (#106)

*2026-7-23 11:20*

666

## 回复 by Yuuuual (#107)

*2026-7-23 13:29*

666

## 回复 by Yuuuual (#108)

*2026-7-23 13:29*

666

## 回复 by kudos5566 (#109)

*2026-7-23 14:26*

6

## 回复 by xtyuns (#110)

*2026-7-23 14:58*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 万神fake (#111)

*2026-7-23 15:03*

谢谢楼主分享

## 回复 by 一栋奥特曼 (#112)

*2026-7-23 15:36*

6666

## 回复 by 悠久之翼灬 (#113)

*2026-7-23 16:12*

66

## 回复 by 孤梦拾遗 (#114)

*2026-7-23 16:31*

666

## 回复 by 一只鸭子 (#115)

*2026-7-23 16:40*

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>  改的不是maps显示的页权限
>

牛皮，是我狭隘了

## 回复 by mb_kfexwtvm (#116)

*2026-7-23 16:52*

66

## 回复 by mb_kfexwtvm (#117)

*2026-7-23 16:53*

代码呢？你搞什么鬼

## 回复 by l140w4n9 (#118)

*2026-7-23 17:43*

6666

## 回复 by LeronMe (#119)

*2026-7-23 17:53*

666

## 回复 by mb_euhyowpw (#120)

*2026-7-23 19:06*

666

## 回复 by 小黄鸭爱学习 (#121)

*2026-7-23 22:13*

测试一下

## 回复 by 弄好了 (#122)

*2026-7-23 23:26*

apatch

## 回复 by Ayuer (#123)

*2026-7-23 23:37*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by G33k3r (#124)

*2026-7-23 23:41*

66

## 回复 by hansxia (#125)

*2026-7-24 07:34*

就想对抗检测

## 回复 by buluo533 (#126)

*2026-7-24 09:51*

学习了

## 回复 by mb_ejimlmwd (#127)

*2026-7-24 09:58*

666

## 回复 by 九黎 (#128)

*2026-7-24 10:00*

tql

## 回复 by git_17554snsj369 (#129)

*2026-7-24 10:35*

66

## 回复 by 特洛伊Troye (#130)

*2026-7-24 10:43*

厉害

## 回复 by Am1re (#131)

666

## 回复 by 龙飞雪 (#132)

666

## 回复 by v5w7crq3 (#133)

666

## 回复 by mb_jzfhycpd (#134)

6666

## 回复 by mb_hfayfkpi (#135)

学习了

## 回复 by k26 (#136)

1

## 回复 by mb_siajdeqa (#137)

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_Kerberos (#138)

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by python_joker (#139)

66666

## 回复 by mb_glqxwdfe (#140)

96

## 回复 by git_30584zhutou9527 (#141)

6666

## 回复 by mb_mwfzoyhc (#142)

谢谢分享

## 回复 by Annilans (#143)

666

## 回复 by Kill_Log (#144)

强的一批

## 回复 by ILA1992 (#145)

1111111111

## 回复 by mb_lyooxmza (#146)

终于可以反微信检测hook了吗

## 回复 by wx_Jesus、 (#147)

666

## 回复 by wx_coddvccwyh (#148)

6666

## 回复 by zhnnmsl (#149)

66

## 回复 by mb_iiulbilc (#150)

高频调用Shadow Page难道不会被perf性能侧信道检测到？

## 回复 by mb_iiulbilc (#151)

1.每一次对Hook函数地址的读/写/执行都会触发一次内核陷入，TLB刷新，CPU周期耗时远大于正常代码页
2.在 wake_up_new_task 手动克隆幽灵内存、Shadow配置短时间连续fork产生大量子进程，子进程缺页异常时延同样异常
3.高频函数被HWBP断点命中时，极端场景会漏泄SIGTRAP信号

## 回复 by mb_iiulbilc (#152)

更致命的硬伤是架构级的缺陷：你用vmalloc分配内存，然后手动填充PTE，但刻意不挂入VMA为了过maps扫描，但内核硬性规则：mincore、process_vm_readv、mprotect等系统调用强制依赖find_vma()来校验地址合法性，难以修复的物理矛盾在于你既然没有VMA，这些系统调用必然返回-EFAULT，但你为了让Hook生效，又必须让PTE拥有READ和EXEC权限，两者在逻辑上是互斥的，系统调用说查无此页，CPU却说这页能执行，无痕Hook言过其实

## 回复 by enze (#153)

mark

## 回复 by mb_pbsputfb (#154)

厉害

## 回复 by 补丁布丁 (#155)

支持 支持

## 回复 by 猜我是谁_610897 (#156)

6666666666666

## 回复 by git_51684xuexijiaoben (#157)

学习一下哇

## 回复 by jaefern (#158)

666

## 回复 by 好听的网名 (#159)

66666

## 回复 by jw8888 (#160)

6666

## 回复 by SharkFall (#161)

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_iiulbilc](https://bbs.kanxue.com/user-864142.htm)
>  1.每一次对Hook函数地址的读/写/执行都会触发一次内核陷入，TLB刷新，CPU周期耗时远大于正常代码页2.在&nbsp;wake_up_new_task&nbsp;手动克隆幽灵内存 ...
>

是的，还是有待优化

## 回复 by SharkFall (#162)

哈哈, ai味浓浓的哈, “架构级的缺陷”, 感谢指点. 根据我浅薄的理解, cpu取指令不查vma, mmu会根据pte把va转换为pfn+offset也就是pa, 然后cpu根据pa读/写/取指, 所以mincore/mprotect/preadv走find_vma探测不到vma和cpu能不能取指&执行疑似没有关系![image](https://bbs.kanxue.com/view/img/face/029.gif)![image](https://bbs.kanxue.com/view/img/face/047.gif)

## 回复 by mb_stuvicca (#163)

66

## 回复 by 西埔 (#164)

严肃学习

## 回复 by Chagrin4_s (#165)

学习学习

## 回复 by mb_rmwvchlr (#166)

66666666

## 回复 by mb_iiulbilc (#167)

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>  哈哈, ai味浓浓的哈, “架构级的缺陷”, 感谢指点. 根据我浅薄的理解, cpu取指令不查vma, mmu会根据pte把va转换为pfn+offset也就是pa, 然后cpu根据pa读/写/取指, ...
>

CPU 取指确实只走 MMU 查 PTE，跟 VMA 没有关系。我的观点不是没有 VMACPU 就不能执行，而是 CPU 不查询 VMA刚好让这种映射产生了两个不一致的地址空间视图，你隐藏 maps 的代价是破坏 VMA 与 PTE 的一致性，它确实能执行但能执行却不存在才是这套架构的硬伤。如果指出问题需要被打上ai标签会让你好受些那你就认为我是ai就行，但我是不是Ai都不影响问题的真假![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_iiulbilc (#168)

你在内存上花费的精力和时间值得赞叹，但别忘记了有些必须保持一致的地方，有些指纹检测是硬件层面的逻辑必然

## 回复 by mb_ccijmwun (#169)

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_nrcvdeps (#170)

nb

## 回复 by niama (#171)

666

## 回复 by SharkFall (#172)

好的 谢谢哈, 讲话非常正式的感觉, 我以为是ai

## 回复 by wx_wyx (#173)

6666

## 回复 by 不知道诶 (#174)

66

## 回复 by mb_mihutdve (#175)

66

## 回复 by wx_kx60819 (#176)

大赞

## 回复 by mb_lojlzfoa (#177)

666

## 回复 by mb_jnmxfjku (#178)

666

## 回复 by GeQ1an (#179)

666

## 回复 by mb_kgneopde (#180)

66666

## 回复 by uboluo (#181)

666

## 回复 by mb_lgqdgzwm (#182)

666

## 回复 by anenn (#183)

666

## 回复 by mb_lmaxftld (#184)

11

## 回复 by 无限进步 (#185)

看看

## 回复 by 道友请留步 (#186)

11111111111

## 回复 by wgetlaidu (#187)

666

## 回复 by zkbutt (#188)

听不懂学学

## 回复 by SInnon (#189)

33333333333

## 回复 by Sofia4041 (#190)

看看

## 回复 by mb_irhdtnzm (#191)

66

## 回复 by Bean3ai (#192)

大佬这个项目有github地址吗？

## 回复 by X14Nuy7 (#193)

nb

## 回复 by 一乐 (#194)

666

## 回复 by 菜鸟逆向 (#195)

![image](https://bbs.kanxue.com/view/img/face/001.gif)666

## 回复 by PPKun (#196)

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>  用shadow page实现的hook，目前测试起来没什么问题
>

我自己实现的挂在热页上会导致libart崩溃![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by mb_ujrqdalt (#197)

牛的

## 回复 by mb_vkxrpcms (#198)

4
