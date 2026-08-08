---
title: '[原创]复习arm64指令架构上通过ptrace安装硬件断点的源码流程'
url: https://bbs.kanxue.com/thread-287975.htm
tid: 287975
author: dadadasda
date: '2025-08-11'
tags: [Android安全, 原创, 基础理论, 逆向分析, 系统相关, 源码框架]
crawled_at: '2026-08-08T10:50:36+00:00'
replies: 50
---

前些天有些讨论提到了安装硬件断点的相关操作，会出现用户进程出错退出的情况，所以这里从源码里复习一下怎么在arm64机器上注册硬件断点。

用户态空间安装硬件断点最常使用的是PTRACE_SETREGSET,指定寄存器集合为NT_ARM_HW_BREAK的一系列读写，从源码kernel/ptrace.c中可以观察到，实际PTRACE_SETREGSET时候只是调用到了跨平台写法
`ptrace_regset`

| 12 | `const struct user_regset_view` `*``view` `=` `task_user_regset_view(task);``const struct user_regset` `*``regset` `=` `find_regset(view,` `type``);` |
|-|-|

其中task_user_regset_view会返回架构相关信息。这里内部使用的是`arch/arm64/ptrace.c`中定义的`user_aarch64_view`，内含`aarch64_regsets`

其中对dbg系列寄存器定义了`hw_break_get`/`hw_break_set`来注册断点回调，核心调用流程为

1. `ptrace_hbp_set_addr`

	- `ptrace_hbp_get_initialised_bp`
		- `ptrace_hbp_create`
			- `ptrace_breakpoint_init`新建断点结构体
			- `register_user_hw_breakpoint` hw_breadkpoint.h 注册断点事件，包含**回调**为`ptrace_hbptriggered`
			- `ptrace_hbp_set_event`写入线程的调试寄存器
				- `tsk->thread.debug.hbp_break[idx] = bp;`
				- `tsk->thread.debug.hbp_watch[idx] = bp;`
	- `modify_user_hw_breakpoint` in hw_breadkpoint.h控制修改断点信息
2. `ptrace_hbp_set_ctrl`

	- 写入dbg控制寄存器

那么这样一个硬件断点在ptrace的流程中就安装完成了，实际用户进程触发时便会自动调用`ptrace_hbptriggered`处理信号，接下来看这个回调怎么触发

## 源码追溯回调的处理

`ptrace_hbptriggered`回调的起始与完结点：

- 由执行指令（breakpoint）或访问内存(watchpoint)踩到硬件断点异常入口点位于中断处理入口entry.S `el0_dbg`位置，也即用户态调试异常，调用流程为
	- `do_debug_exception`,
		- 关键1.fault信息的获取位置`const struct fault_info *inf = debug_fault_info + DBG_ESR_EVT(esr);`
		- 关键2.fault回调函数的入口`if (!inf->fn(addr_if_watchpoint, esr, regs))` 这个在arch/arm64/hw_breakpoint.c中被`hook_debug_fault_code(DBG_ESR_EVT_HWBP, breakpoint_handler, SIGTRAP,TRAP_HWBKPT, "hw-breakpoint handler");`设置为了使用`breakpoint_handler`处理
			- `perf_bp_event(bp, regs)`为调用回调的perf事件入口点
				- 兜兜转转会到达`__perf_event_overflow(event, throttle, data, regs))`核心调用
					- `READ_ONCE(event->overflow_handler)(event, data, regs);`=(等效于)=>此处调用到了`event->overflow_handler`即注册的`ptrace_hbptriggered`函数，其中唯一的关键是：
						- 为用户态进程安装一个trap信号，以供tracer捕获信息 `force_sig_info(SIGTRAP, &info, current);` info包含了断点踩踏的地址`(void __user *)(bkpt->trigger),`作为触发参数。

可以看到ptrace这套接口其实很方便地把指令集中的同步异常转化为了被trace进程中的信号，被tracer异步唤醒处理。挺优雅的，具备很强的跨平台通用性，就是整体效率上不算很高。如果直接在处理同步异常时刻不挂起信号，而是直接进入到同线程用户态或内核态的handler处理动作，可以有更好的效率。

目前为了解决这个handler的灵活度可以用内核lua接口绑定常用的寄存器读取与内核读取的c接口来实现，感兴趣的朋友可以关注更新。

---

# 回复

## 回复 by wx_插曲 (#2)

*2025-8-11 14:29*

牛逼

## 回复 by mb_ldbucrik (#3)

*2025-8-11 22:01*

感谢分享

## 回复 by SomeMx (#4)

*2025-8-12 01:21*

过来瞧瞧

## 回复 by onlythis (#5)

*2025-8-12 08:41*

感谢分享

## 回复 by zhuzhu_biu (#6)

*2025-8-12 12:00*

分享一张很久之前记录硬断调用的流程图

![image](https://bbs.kanxue.com/upload/attach/202508/878476_FQDPC7UDP6DK7CT.webp)

## 回复 by sk97 (#7)

*2025-8-12 12:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  分享一张很久之前记录硬断调用的流程图
>
>

图好糊。有无高清大图？

## 回复 by dadadasda (#8)

*2025-8-12 13:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>  分享一张很久之前记录硬断调用的流程图
>
>

你这个也太糊了![image](https://bbs.kanxue.com/view/img/face/055.gif)不过看几个关键节点应该总结蛮好的

## 回复 by zhuzhu_biu (#9)

*2025-8-13 12:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  sk97](https://bbs.kanxue.com/user-897408.htm)
>
>  图好糊。有无高清大图？
>
>

看雪压缩了,我没注意

![image](https://bbs.kanxue.com/upload/attach/202508/878476_T3ZG8AJF5RRCPJT.png)

上传的附件：
- 硬件断点指令流程.drawio.png

（1.82MB，66次下载）

## 回复 by dadadasda (#10)

*2025-8-13 14:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  zhuzhu_biu](https://bbs.kanxue.com/user-878476.htm)
>
>
>
>
>
>
>
>  sk97
>
>
>
>  图好糊。有无高清大图？
>
>  看雪压缩了,我没注意
>
>

赞，挺全面了

## 回复 by bullyxy (#11)

*2025-8-14 10:13*

学习学习

## 回复 by mb_irhdtnzm (#12)

*2025-8-16 20:07*

1

## 回复 by mb_xjdhrmck (#13)

*2025-8-16 21:39*

6666

## 回复 by 飆汗吉米 (#14)

*2025-8-17 03:53*

6666

## 回复 by 暴强 (#15)

*2025-8-17 08:55*

66666666666

## 回复 by fangliangz (#16)

*2025-8-18 09:26*

666

## 回复 by mb_4nrpVMxJ (#17)

*2025-8-18 10:33*

看看

## 回复 by mb_undccabr (#18)

*2025-8-18 14:54*

6666666666666666666

## 回复 by mb_dcjxxhsk (#19)

*2025-8-19 17:37*

666

## 回复 by 寻梦之璐 (#20)

*2025-8-19 22:16*

1

## 回复 by mb_nkjfyhkg (#21)

*2025-8-20 01:57*

1

## 回复 by git_27405Danya22891 (#22)

*2025-8-20 19:01*

круто

## 回复 by XCicada (#23)

*2025-9-11 10:49*

感谢

## 回复 by belikewater (#24)

*2025-9-15 15:11*

6

## 回复 by mb_pnyyaazf (#25)

*2025-9-18 12:42*

6

## 回复 by jasonxgw (#26)

*2025-9-24 17:21*

tql

## 回复 by 大萨达 (#27)

*2025-11-1 09:59*

666

## 回复 by MsScotch (#28)

*2025-11-1 11:10*

mark

## 回复 by 3cly (#29)

*2025-11-3 19:16*

123

## 回复 by 大萨达 (#30)

*2025-11-9 11:39*

666

## 回复 by 大萨达 (#31)

*2025-11-9 18:17*

888

## 回复 by mb_irhdtnzm (#32)

*2025-11-9 23:38*

1

## 回复 by 倾心Deep (#33)

*2025-11-10 22:55*

6

## 回复 by Ms135 (#34)

*2025-11-13 15:20*

666

## 回复 by git_63314bikhx (#35)

*2025-12-7 01:49*

666

## 回复 by mb_vxjviech (#36)

*2025-12-28 18:38*

666

## 回复 by mb_qqlojqnm (#37)

*2026-1-26 05:20*

666

## 回复 by pingsky (#38)

*2026-2-22 09:24*

感谢分享

## 回复 by mb_eywdngzs (#39)

*2026-2-25 23:17*

666

## 回复 by huangjw (#40)

*2026-3-28 08:54*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 星辰北天 (#41)

*2026-3-29 19:49*

感谢分享

## 回复 by mb_eumnbkwy (#42)

*2026-4-25 19:02*

666

## 回复 by mb_jwevvolh (#43)

*2026-5-6 13:30*

6666

## 回复 by mb_fqndstzl (#44)

*2026-5-6 15:39*

666666

## 回复 by logeye (#45)

*2026-5-6 17:31*

111

## 回复 by hooych (#46)

*2026-5-7 21:22*

学习了，感谢分享

## 回复 by mb_rrwegvyc (#47)

*2026-5-19 19:31*

6666666666666

## 回复 by GeQ1an (#48)

*2026-6-1 17:01*

6

## 回复 by 砂砾 (#49)

*2026-6-1 17:36*

谢谢分享!

## 回复 by mb_ycyasroo (#50)

*2026-7-14 18:35*

666

## 回复 by Yuuuual (#51)

*2026-7-23 13:43*

学习记录，感谢分享
