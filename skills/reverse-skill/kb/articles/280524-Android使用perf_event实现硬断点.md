---
title: Android使用perf_event实现硬断点
url: https://bbs.kanxue.com/thread-280524.htm
tid: 280524
author: ri_Char
date: '2024-02-15'
tags: [Android安全, 工具脚本, 逆向分析]
crawled_at: '2026-07-31T14:32:24+08:00'
replies: 13
---

# 背景

在Android中，目前有一下几种方式实现硬件断点。

1. GDB Server
2. rwProcMem33等此类内核模块

但是这些方式都有一些问题，比如GDB Server需要使用`ptrace`附加在目标进程，容易被检测。rwProcMem33等内核模块需要内核头文件，不开源内核难以使用，此外触发一次断点后会导致整个线程卡死，直到断点删除。

使用linux `perf_event`机制实现硬件断点可以在不附加在目标进程、不安装内核模块的情况下下断，同时也无法被目标进程检测。
该方法支持读、写、执行断点，可以读写断点设置1、4、8字节长度。断点后可以输出此时的寄存器信息。

**项目地址：** [ri-char/pwatch](https://github.com/ri-char/pwatch)

# 原理

使用`perf_event_open`系统调用，设置断点类型为`PERF_TYPE_BREAKPOINT`。`sample_type`为`PERF_SAMPLE_REGS_USER`，可以采样寄存器信息。
将断点信息填入结构体后使用`perf_event_open`创建`perf_event`，返回一个`fd`。使用`mmap`打开该fd可以得到断点出发后的信息。

| 1234567891011121314151617181920 | `let mut attrs = sys::bindings::perf_event_attr::``default``();` `attrs.size = std::mem::size_of::<sys::bindings::perf_event_attr>() as u32;``attrs.type_ = sys::bindings::PERF_TYPE_BREAKPOINT;``attrs.__bindgen_anon_1.sample_period = 1;``attrs.__bindgen_anon_2.wakeup_events = 1;``attrs.bp_type = r#type;``attrs.__bindgen_anon_3.bp_addr = addr;``attrs.__bindgen_anon_4.bp_len = len as u64;``attrs.set_precise_ip(2);``attrs.sample_type = sys::bindings::PERF_SAMPLE_REGS_USER \| sys::bindings::PERF_SAMPLE_TID;``attrs.sample_regs_user = arch::SAMPLE_REGS_USER;` `sys::perf_event_open(``&mut attrs,``pid,``-1,``-1,``(sys::bindings::PERF_FLAG_FD_CLOEXEC) as u64,``)` |
|-|-|

`sample_type`还可以加上`PERF_SAMPLE_STACK_USER`，获取用户调用栈信息。

---

# 回复

## 回复 by mb_qnxaollu (#2)

*2024-2-20 15:40*

第一种怎么实现呢。

## 回复 by wx_晚风_407 (#3)

*2024-2-20 17:23*

..

## 回复 by Amun (#4)

*2024-2-20 18:57*

![image](https://bbs.kanxue.com/view/img/face/63.gif) 牛批

## 回复 by ri_Char (#5)

*2024-2-20 20:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_qnxaollu](https://bbs.kanxue.com/user-931275.htm)
>
>  第一种怎么实现呢。
>
>

使用ptrace的PTRACE_GETREGSET和PTRACE_SETREGSET修改REGSET_HW_BREAK和REGSET_HW_WATCH,内核中这两个regset的定义在这里
https://elixir.bootlin.com/linux/v5.15.148/source/arch/arm64/kernel/ptrace.c#L1470

## 回复 by dreameriii (#6)

*2024-3-2 21:10*

大佬太强了，正好需要这个功能，感谢无私分享！ ![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by mb_qnxaollu (#7)

*2024-6-4 08:36*

有成品不。

## 回复 by mb_slvxaotq (#8)

*2024-7-11 04:14*

No space left on device怎么解决？

## 回复 by mb_oholboab (#9)

*2024-8-26 10:10*

能被检测到

## 回复 by mb_xqptnehm (#10)

*2024-12-2 19:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ri_Char](https://bbs.kanxue.com/user-941299.htm)
>
>  使用ptrace的PTRACE_GETREGSET和PTRACE_SETREGSET修改REGSET_HW_BREAK和REGSET_HW_WATCH,内核中这两个regset的定义在这里
> http ...
>
>

## 回复 by 神雕大侠X (#11)

*2025-5-8 15:01*

进程自己通过ptrace REGGET_HW_BREAK，能读取到硬件断点寄存器吗？如果能那是不是可以检测？

## 回复 by dadadasda (#12)

*2025-8-16 09:19*

这种读取的情况相当于抢占ptrace，进程组内能抢到子线程的话gdb也附加不上去了。

## 回复 by 万里星河 (#13)

*2025-8-18 02:05*

666

## 回复 by mb_eiphaxvi (#14)

*2026-7-2 01:14*

这种断点能做成.exe来调试安卓设备吗
