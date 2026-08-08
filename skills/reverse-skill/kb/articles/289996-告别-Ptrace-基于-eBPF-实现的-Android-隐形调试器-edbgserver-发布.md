---
title: '[原创] 告别 Ptrace！基于 eBPF 实现的 Android 隐形调试器 (edbgserver) 发布'
url: https://bbs.kanxue.com/thread-289996.htm
tid: 289996
author: Cyril77
date: '2026-02-09'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-08-08T10:25:57+00:00'
replies: 14
---

## 前言：为什么要造这个轮子？

在 Android 逆向工程中，大家肯定苦 `ptrace` 久矣。 只要用 `ptrace` 去 attach，`TracerPid` 立马变身，各种双进程保护、轮询检测教做人。 虽然 Frida 是神作，但在某些场景下还是有痛点：

1. **动静大**：Frida inject 或 attach 容易被针对性检测（扫 maps、扫线程等）。
2. **数据跟踪弱**：Frida 主要是 Hook 函数，如果我想**对某个内存地址下硬件断点**（Watchpoint）来追踪数据流向，Frida 实现起来比较费劲且性能一般。
3. **调试习惯**：很多人（包括我）还是习惯用 **GDB/Pwndbg** 那种交互式的调试体验，指哪打哪。
4. **太笨重**：IDA 的调试太笨重了，需要配合一系列操作才能精准控制 attach；如果是 frida 的话在验证算法的时候会需要看很多寄存器的值来验证猜想，写脚本太费劲了。

之前的解决方案要么是复杂的预埋 Probe，要么是魔改内核。为了能以**最小侵入特征**、**无视大部分反调试**地愉快使用 `pwndbg`，我基于 **eBPF** 开发了这个调试服务端——**edbgserver**。

**edbgserver** 是一个基于 eBPF 实现的调试器服务端，旨在脱离 `ptrace` 系统调用。 它核心代码运行在内核态，对应用层几乎不可见。目前支持 **Android** (主要目标) 与 **Linux** 下的 Arm64 和 x86_64 架构。

## 支持特性

- **隐形调试**：不使用 `ptrace`，完美绕过 `TracerPid` 检测及基于 ptrace 的反调试。
- **硬件断点支持**：原生支持硬件断点（HwBp）
- **GDB 协议兼容**：完美适配 `pwndbg` `gdb` 前端工具
- **功能全**：
	- 支持软件/硬件断点
	- 单步步入/步过 (Step/Next)
	- 信号发送
	- 内存任意读写、寄存器读取
	- 多线程调试支持
	- 进程库符号信息获取

## 效果演示

**1. 启动服务端（手机端）：** 无需繁琐配置，指定包名和 so 即可。

| 12 | `# 需 Root，内核版本 >= 5.x``.``/edbgserver` `-u -p com.example.target -t libnative-lib.so -b 0x12345` |
|-|-|

**2. GDB 连接（PC 端）：**

| 12 | `pwndbg> target remote :3333``pwndbg> breakrva 0x18A8 libsupervipplayer.so` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202602/1006247_72NW88MRM55S8G8.webp)

## 快速上手

### 环境要求

- Android 设备需 Root
- 内核版本需支持 eBPF（需要 Kernel 5.x 以上，现在的 Pixel、小米等较新机型基本都满足）

### 使用步骤

1. **Push 到手机**： 将编译好的 `edbgserver` 推送到手机 `/data/local/tmp/` 并赋予执行权限。
2. **root 启动 Server**：

| 12 | `# 典型用法：使用 Unix Domain Socket 提高性能，指定包名自动查找进程``.``/edbgserver` `-u -p io.cyril.supervipplayer -t libsupervipplayer.so -b 0x1848` |
|-|-|

- `-p`: 目标包名
- `-t`: 目标 so 名字
- `-b`: 初始断点地址（虚拟地址，IDA 里显示的那个，**不是**文件偏移）
- `-u`: 使用 UDS 通信（性能更好）

1. **端口转发**：

| 1 | `adb forward tcp:3333 localabstract:edbg` |
|-|-|

1. **PC 端连接**： 为了解决 GDB 远程加载 Android 库极其缓慢的问题，我提供了一个 `android_lib_pull.sh` 脚本。 它能一键把目标 App 的 so 和系统库拉到本地，实现**秒加载**。

| 123456 | `# 1. 拉取依赖``.``/android_lib_pull``.sh io.cyril.supervipplayer``# 2. 启动 GDB``pwndbg``pwndbg>` `set` `sysroot android_sysroot/``pwndbg> target remote :3333` |
|-|-|

## 局限性与 TODO

也说说目前的局限性（毕竟 eBPF 在调试领域还是带镣铐跳舞）：

1. **寄存器修改限制**：由于 eBPF 的校验器机制，目前无法直接修改 CPU 寄存器的值。*暂时的替代方案是使用 Patch 指令修改内存。*
2. **Attach 机制**：目前无法像 ptrace 那样随时 attach，必须通过文件断点（uprobe）等待触发来通过信号挂起。
3. **环境隔离**：eBPF 运行在内核态，对 Namespace 感知较弱。建议不要在 WSL2 或 Docker 中运行服务端，可能导致线程信息获取不准。真机和虚拟机（AVD）没问题。
4. **x86_64 支持**：虽然支持，但主要测试集中在 Arm64，x86 下单步可能会有 Bug。

## 项目地址 & 交流

工具是开源的，欢迎大家试用、提 Issue 或 PR。如果你觉得好用，希望能给个 Star ！

希望这个小工具能成为大家调试的又一把瑞士军刀。有问题欢迎在楼下讨论！

项目地址： <https://github.com/Satar07/edbgserver>

---

# 回复

## 回复 by 墨穹呢 (#2)

*2026-2-9 22:21*

感谢分享

## 回复 by KanXue_NG (#3)

*2026-2-9 22:22*

大佬 牛逼 支持一下

## 回复 by 安卓逆向test (#4)

*2026-2-9 23:18*

用uprobe的话，最大的问题应该是uprobe不是实时读取汇编指令的，这就导致hook运行时解密汇编指令的so会崩溃

## 回复 by Cyril77 (#5)

*2026-2-10 00:40*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  用uprobe的话，最大的问题应该是uprobe不是实时读取汇编指令的，这就导致hook运行时解密汇编指令的so会崩溃
>
>

你说的没错，确实这个是比较麻烦的地方。尝试过硬件断点不过感觉想不到什么好的解决方案。。。

## 回复 by wx_Huber Barrientos (#6)

*2026-2-10 03:02*

感谢分享

## 回复 by huangjw (#7)

*2026-2-10 09:06*

总之还太会ebpf，牛逼

## 回复 by gtict (#8)

*2026-2-10 09:10*

我用pwndbg调试，总是很卡，，大佬指导下，到底是啥原因

## 回复 by matrump (#9)

*2026-2-10 09:41*

牛的![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by fei3ei (#10)

*2026-2-10 09:46*

还得是ebpf啊

## 回复 by 夜惜风雨 (#11)

*2026-2-10 16:04*

这个和去年的edbg有什么区别？

## 回复 by 2002ljb (#12)

*2026-2-10 17:26*

感谢分享

## 回复 by Imxz (#13)

*2026-2-11 12:53*

tql

## 回复 by wen55444 (#14)

*2026-2-11 13:48*

termux

## 回复 by sossai (#15)

*2026-2-16 11:43*

这个和之前的edbg区别在哪
