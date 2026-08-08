---
title: '[原创] 半年时间，我终于用懂了 eDBG —— eBPF 轻量级 trace   tenet 回放伪动调的调试器'
url: https://bbs.kanxue.com/thread-291272.htm
tid: 291272
author: vior
date: '2026-05-19'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:08:27+00:00'
replies: 16
---

>
> 项目地址：https://github.com/chenxvb/eDBG
>
>
>

搞 Android 逆向的都知道，ptrace 调试器（frida、IDA remote dbsrv）一上来就容易被检测，各种反调试手段层出不穷。花了大半年时间断断续续踩坑，我终于把 eDBG 这套基于 eBPF 的调试 + trace 回放工作流跑通了，感觉确实好用，写篇文章记录一下。

## eDBG 是什么

eDBG 是一款基于 eBPF 的轻量级 CLI 调试器，专门针对 Android ARM64 平台。它不使用 ptrace 来附加进程，而是通过内核态的 eBPF uprobe 机制来实现断点和调试，因此能够几乎完全无视用户态的反调试检测。

这个魔改 fork 版 Unicorn Trace 功能 —— 在断点处 dump 上下文，用 Unicorn 引擎做指令级模拟执行，生成 Tenet 兼容的 trace 日志。这意味着你可以在 IDA 里像动态调试一样前进后退地回放执行过程。

## 为什么用它

相比传统方案（frida stalker、IDA trace、qiling），eDBG 版本的 tracer 有以下好处：

- **基于 eBPF，基本完全无视反调试** —— uprobe 工作在内核态，用户态的 ptrace 检测、`/proc/self/status` TracerPid 检查等手段全部失效
- **下断运行更轻量，崩溃少，内嵌 dump 更快** —— 不需要注入 so，不需要 attach 进程，断点触发后直接在内核态采集寄存器和内存
- **可以 Unicorn 回放，直接丢给 AI 看 trace** —— dump 出来的 `regs.json` + 内存 bin 可以直接给 LLM 分析执行流（eDBG 本身也支持 MCP 模式直接对接 AI agent）
- **支持 Tenet 回放调试，相当于 IDA 里伪动调，但更舒服** —— 在 IDA 里可以前进/后退逐条指令查看，还支持内存断点，比真动调更自由

## 效果展示

### Unicorn Trace Dump 全流程

参考仓库图片

### Tenet 回放调试

 ![image](https://bbs.kanxue.com/upload/attach/202605/930478_XH37EXNZPFENUW9.webp)

### Tenet 内存断点

这是 eDBG + Tenet 最惊艳的能力之一：你可以在 Tenet 的回放中对任意内存地址下断点，当该地址被读写时自动定位到对应的指令。这对于分析加密算法中的 buffer 变化、追踪关键数据流向非常高效。

 ![image](https://bbs.kanxue.com/upload/attach/202605/930478_FEGU2YJXC2TNZZN.webp)

## 工作流

一个典型的 eDBG trace 分析流程如下：

```python
┌─────────────────────────────────────────────────────────┐
│  1. IDA 静态分析，确定目标函数入口和出口偏移               │
│     找到 libxxx.so 中目标函数: 入口 0x1234, 出口 0x5678    │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  2. 手机端启动 eDBG，设置断点                             │
│     ./eDBG -p com.target.app -l libxxx.so -b 0x1234      │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  3. 启动/操作目标 APP，触发断点                           │
│     程序命中 0x1234，eDBG 暂停                            │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  4. 执行 trace，dump + Unicorn 模拟执行                   │
│     (eDBG) trace libxxx.so+0x5678 ./trace_out --tenet     │
│                                                           │
│     eDBG 自动：                                            │
│       ① dump 当前寄存器 + 内存段                          │
│       ② Unicorn 模拟执行每条指令                          │
│       ③ 遇到外部调用 → 切回真实调试器执行 → 重新 dump     │
│       ④ 生成 uc.log（反汇编日志）+ tenet.log（回放日志）  │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│  5. 将 trace 产物 pull 到 PC                              │
│     adb pull /data/local/tmp/trace_out ./                 │
└───────────────────────────┬─────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
┌──────────────────────┐  ┌──────────────────────────────┐
│  6a. IDA + Tenet      │  │  6b. 直接看 uc.log /          │
│  加载 tenet.log       │  │      丢给 AI 分析 trace       │
│  前进后退回放         │  │      或用 local_emu.py 回放   │
│  内存断点追踪数据流   │  │                                │
└──────────────────────┘  └──────────────────────────────┘
\```

### 命令速查

```bash
# 基本调试
./eDBG -p com.target.app -l libxxx.so -b 0x1234
(eDBG) c                                          # 继续运行到断点
(eDBG) s / n                                       # 单步步入 / 步过
(eDBG) info r                                      # 查看寄存器
(eDBG) x SP 128                                    # 查看栈内存

# Trace（核心用法）
(eDBG) trace libxxx.so+0x5678 ./trace_out --tenet  # trace 到目标地址，输出 tenet 日志
(eDBG) trace x30 ./trace_out --tenet               # trace 到 LR（整个函数）

# 内存操作
(eDBG) dump 0x7abc0000 0x4000 mem.bin              # dump 内存到文件
(eDBG) write 0x7abc0000 deadbeef                   # 写内存（patch）
\```

## 原理简介

### eBPF 断点机制

传统调试器（GDB/LLDB/IDA dbsrv）通过 `ptrace(PTRACE_ATTACH, pid)` 附加到目标进程，这个动作会被用户态的反调试手段轻松检测到（读 TracerPid、检测 SIGTRAP handler 等）。

eDBG 走了完全不同的路线：

```python
  传统方案                          eDBG 方案
  ────────                          ─────────
  用户态 ptrace attach              内核态 eBPF uprobe
       ↓                                ↓
  /proc/pid/status 可见             内核态操作，用户态不可见
  SIGTRAP 信号可检测               无信号，uprobe callback
  进程会被 stop                     uprobe handler 中暂停线程
\```

eBPF uprobe 的原理是在内核中对目标文件的指定偏移注册探针。当任何进程执行到该偏移对应的指令时，内核会触发 uprobe handler，在 handler 中可以读取寄存器、暂停执行等。因为整个过程发生在内核态，用户态程序几乎没有感知。

eDBG 使用 **文件+偏移** 的断点注册方式，不需要知道目标进程的 PID 或内存布局，可以在目标 APP 启动之前就准备好断点。

### Unicorn Trace 的多轮同步机制

单纯的 Unicorn 模拟有个致命问题：遇到外部函数调用（比如 `strlen`、`malloc`）就会因为缺少实现而失败。eDBG 的解法非常优雅：

```python
Unicorn 模拟执行
    │
    ├── 指令在 bound 范围内 → 继续模拟，记录 trace
    │
    └── PC 跳出 bound（外部调用）→ 暂停模拟
            │
            ├── 在 LR 处设置临时断点
            ├── 用真实调试器 continue，让程序真实执行外部函数
            ├── 断点命中后重新 dump 寄存器 + 内存
            └── 开始新一轮 Unicorn 模拟（Round N+1）
\```

每一轮的 dump 和 trace 日志都会保存，最终合并成完整的 `uc_combine.log` 和 `tenet_combine.log`。这个设计让 Unicorn Trace 可以处理几乎所有包含外部调用的真实代码。

### Tenet 内存断点

Tenet 是 IDA 的一个时间旅行调试插件。加载 eDBG 生成的 `tenet.log` 后，你可以：

- 前进/后退逐条指令回放
- 查看每条指令执行前后的寄存器和内存变化
- **对任意内存地址设置读/写断点** —— 当回放到该地址被访问时自动停下

这个内存断点能力是分析加密/混淆代码的利器。比如你知道明文在地址 A，密文在地址 B，对这两个地址下内存断点，就能快速定位到加密函数的关键操作。

推荐使用特化版 Tenet：https://github.com/chenxvb/Tenet-IDA9.0 ，支持 dump 内存加载，在 IDA 中还原完整动调体验。

## 小技巧

### 1. 先断后调，永远记住 -b

eDBG 不支持随时暂停，**必须** 通过 `-b` 或运行时 `b` 命令在目标位置先下断点。养成习惯：在 IDA 里确定好偏移再启动。

### 2. trace 整个函数用 x30

```bash
(eDBG) trace x30 ./trace_out --tenet
\```

`x30` 就是 LR（链接寄存器），trace 到 LR 相当于 trace 整个当前函数。这是最常用的 trace 方式。

### 3. 手动指定 bound 避免不必要的外部调用同步

如果目标代码跨多个段，自动 bound 可能不准，导致频繁触发外部调用同步（每次同步都会慢一些）。手动指定 `--bound` 可以减少中断：

```bash
(eDBG) trace 0x5678 ./out --tenet --bound 0x1000 0x9000
\```

### 4. dump 产物可以离线回放

trace 产出的 `dump_*/regs.json` + 内存 bin 文件可以用 [Unicorn-Trace](https://github.com/chenxvb/Unicorn-Trace) 的 `local_emu.py` 离线回放，不需要手机，不需要再跑一次。适合反复调试同一段代码：

```python
from local_emu import run_all_continuous
run_all_continuous(dump_path="./trace_out/dump_xxx", debug_switch=True)
\```

### 5. 调试会跳过系统库

对 `libc.so`、`libart.so` 这类被大量进程加载的库会自动跳过，但会局限在本库中，可以过滤很多无用逻辑且提高效率

## 缺点与局限

说优点也要说缺点，eDBG 并不完美：

- **异常类反调试会有问题** —— eDBG 无视的是常规的 ptrace/signal 检测，但如果目标使用了基于异常处理流程的反调试（比如故意触发 SIGSEGV 走 signal handler 来执行关键逻辑），eDBG 的 uprobe 机制可能会干扰异常传递链路，导致行为异常
- **过多的外部调用会很慢** —— 每次 Unicorn 遇到外部调用都需要切回真实调试器执行、重新 dump 内存、重启模拟，如果目标函数密集调用外部函数（比如大量 `strlen`/`memcpy`/JNI 调用），trace 速度会急剧下降
- **在外部调用少的 VM trace 场景很有优势** —— 反过来说，对于自定义 VM、纯计算类混淆（ollvm handler、白盒加密循环等）这种外部调用很少的代码，eDBG 的 trace 效率非常高，这是它的最佳使用场景
- **仅支持 Android ARM64** —— 需要 root + 内核 5.10+，覆盖面有限

## 相关工具与参考

| 工具 | 说明 |
|-|-|
| [eDBG](https://github.com/chenxvb/eDBG) | 本文主角，eBPF 调试器 |
| [eDBG](https://github.com/ShinoLeah/eDBG) | fork 原仓库 eBPF 调试器 |
| [Unicorn-Trace](https://github.com/chenxvb/Unicorn-Trace) | 源项目，IDA 插件版本 + 离线回放工具链 |
| [Tenet-IDA9.0](https://github.com/chenxvb/Tenet-IDA9.0) | 特化版 Tenet，支持 dump 内存加载 |
| [Tenet (原版)](https://github.com/gaasedelen/tenet) | IDA 时间旅行调试插件 |
| [stackplz](https://github.com/SeeFlowerX/stackplz) | eDBG 的参考项目，eBPF trace 工具 |
| [pwndbg](https://github.com/pwndbg/pwndbg) | eDBG CLI 界面的灵感来源 |
| [Unicorn Engine](https://github.com/unicorn-engine/unicorn) | CPU 模拟引擎 |
| [KernelSU](https://github.com/tiann/KernelSU) | 推荐的 root 方案 |

**延伸阅读：**

- [eDBG 使用进阶：避免 uprobes 产生可被察觉的特征](https://www.sh1no.icu/posts/28348c4/)
- [看雪相关讨论](https://bbs.kanxue.com/thread-289135.htm)

---

*如果觉得有用，去 GitHub 给 eDBG 点个 Star 吧。*

---

# 回复

## 回复 by Zepp7289 (#2)

*2026-5-19 21:21*

test大佬我记得之前说过uprobe处理混淆的so不太好

## 回复 by vior (#3)

*2026-5-20 10:39*

动调混淆会有啥问题吗，目前我用还没遇到什么问题。如果有问题也可以用 ida 版本的插件 dump

## 回复 by Imxz (#4)

*2026-5-20 15:30*

tql

## 回复 by userapp (#5)

*2026-5-21 17:43*

魔改kernel+硬断点替代uprobes岂不是没内存特征了？

## 回复 by 墨穹呢 (#6)

*2026-5-21 21:55*

感谢分享

## 回复 by 啊你好哇123 (#7)

*2026-5-23 13:19*

这个在框架里面可以用吗？手机没root

## 回复 by mb_ykavguun (#8)

*2026-5-24 01:07*

1

## 回复 by n_1ng (#9)

*2026-5-24 14:47*

666

## 回复 by fengyunabc (#10)

*2026-5-25 11:27*

感谢分享。

## 回复 by internnal_q (#11)

*2026-5-25 14:37*

谢谢群主分享。

## 回复 by vior (#12)

*2026-5-26 15:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  userapp](https://bbs.kanxue.com/user-752991.htm)
>  魔改kernel+硬断点替代uprobes岂不是没内存特征了？
>

是的，毕竟读取内存寄存器都是外部完成的，没有内存注入特征

## 回复 by vior (#13)

*2026-5-26 15:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  啊你好哇123](https://bbs.kanxue.com/user-847178.htm)
>  这个在框架里面可以用吗？手机没root
>

没有 root 应该是无法用的

## 回复 by 海带 (#14)

*2026-5-28 16:18*

6666

## 回复 by x1a0f3n9 (#15)

*2026-6-2 11:53*

这项目有点意思，感谢分享

## 回复 by vior (#16)

*2026-6-2 15:00*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  这项目有点意思，感谢分享
>

感谢支持，有兴趣也可以看看我的原 ida 插件版本 https://github.com/chenxvb/Unicorn-Trace

## 回复 by x1a0f3n9 (#17)

*2026-6-2 15:03*

>
> [vior](https://bbs.kanxue.com/user-930478.htm)
>  感谢支持，有兴趣也可以看看我的原 ida 插件版本 https://github.com/chenxvb/Unicorn-Trace
>

谢谢分享，前去拜读一下![image](https://bbs.kanxue.com/view/img/face/003.gif)
