---
title: '[原创] sukinject：跨进程 arm64 DBI hook / 注入框架'
url: https://bbs.kanxue.com/thread-291947.htm
tid: 291947
author: PPKun
date: '2026-07-10'
tags: [Android安全, 原创, HOOK注入, 源码框架]
crawled_at: '2026-08-08T10:03:22+00:00'
replies: 58
---

看了网上很多关于 arm64 无痕 hook 的方法，然后自己理解下加上 ai 帮忙

 整理并开源了一个自己在用的 Linux / Android arm64 跨进程 hook 框架：sukinject

 ### 它是什么

 sukinject 做的是跨进程、内核辅助的 hook，不是同进程 inline hook。

 公开语义很简单：

 ```text

   target -> replacement -> origin

 ```

 - target：目标进程里的函数地址

 - replacement：也在目标进程地址空间里的代码（内核生成的 ABI wrapper / 已有 VA / agent 装进去的代码）

 - origin：目标进程里可回调原函数的 trampoline（ghost 页入口）

 调用方进程里的普通 C 函数指针，不能直接当 replacement——地址空间隔离决定了这一点。

 和 Dobby 那类同进程 inline hook 是不同模型，不追求 Dobby 兼容。需要同进程改字节插跳的，继续用 Dobby 即可。

 ### 技术路线（简要）

 依赖 root + 匹配内核的 kmod（/proc/sukinject）。

 大致思路：

 1. 目标代码页通过 PTE 翻转 UXN，执行会 instruction fault

 2. kprobe 挂在 fault 路径上，把 PC 重定向到 ghost / 重编译页

 3. 原始页字节尽量不改；执行走 shadow，读路径仍可对准原页（隐蔽性谱系更接近 wxshadow / 整页 DBI 那条线，而不是改 .text 插 B）

 能力边界也说清楚：

 - 主线 AArch64；compat32 会 fail closed

 - 需要自己能加载 suk_step4.ko（内核版本/树要对上）

 - 不是完整动态链接器，也不是「任意 C++ / TLS / 完整 so 语义」运行时

 - agent 路径支持受限 ELF / package 装进目标再绑入口，不是 ptrace+dlopen 主线

 ### 2. 四条 hook 路径

 ┌───┬────────────────────────────┬───────────┬──────────────────────────────────────────────────────┬────────────────────────────────┐

 │ # │ 路径                       │ kmod 命令 │ 核心做法                                             │ 代价/限制                      │

 ├───┼────────────────────────────┼───────────┼──────────────────────────────────────────────────────┼────────────────────────────────┤

 │ 1 │ DBI 整页重编译（默认主线） │ dbi-hook  │ UXN + fault 改 PC → ghost 重编译页；原页字节尽量不动 │ 复杂页/热页可能踩坑；有 origin │

 ├───┼────────────────────────────┼───────────┼──────────────────────────────────────────────────────┼────────────────────────────────┤

 │ 2 │ 指针换槽                   │ ptr-hook  │ 只改 8B 槽，不改 .text                               │ 只覆盖「过指针」调用           │

 ├───┼────────────────────────────┼───────────┼──────────────────────────────────────────────────────┼────────────────────────────────┤

 │ 3 │ HW-BP persistent           │ bp-hook   │ 硬件执行断点，命中改 pc；可 origin island            │ 每 hit 进内核；槽位少          │

 ├───┼────────────────────────────┼───────────┼──────────────────────────────────────────────────────┼────────────────────────────────┤

 │ 4 │ PFN-swap                   │ pfn-hook  │ 页帧/执行视图交换（实验）                            │ 非默认；隐蔽模型与 DBI 不同    │

 └───┴────────────────────────────┴───────────┴──────────────────────────────────────────────────────┴────────────────────────────────┘

 安装窗口还有 break-arm（oneshot 断点汇合）、task-hold、fork-watch 等，用来卡安装时机，本身不是第 3 条长期 hook。

 主路径：业务上优先 DBI +（可选）agent 装载；能指针化的用 ptr；低频零改字节再考虑 bp-hook；pfn 当实验后端。

 ### 你能直接用的东西

 ┌──────────────────────────────────────┬───────────────────────────────────────────────┐

 │ 组件                                 │ 用途                                          │

 ├──────────────────────────────────────┼───────────────────────────────────────────────┤

 │ include/sukinject.h + libsukinject.a │ C API：SukInjectHook / Unhook 等              │

 ├──────────────────────────────────────┼───────────────────────────────────────────────┤

 │ sukctl                               │ resolve、dbi-hook、status、hold/break/fork 等 │

 ├──────────────────────────────────────┼───────────────────────────────────────────────┤

 │ sukagentctl                          │ hook-elf：装 agent + 入口替换（可带 origin）  │

 ├──────────────────────────────────────┼───────────────────────────────────────────────┤

 │ 文档                                 │ docs/public-interfaces.md 起总览              │

 └──────────────────────────────────────┴───────────────────────────────────────────────┘

 最小库用法示意：

 ```c

   SukInjectOptions opt = SukInjectOptionsDefault();

   opt.abi = "int-origin-add:7";

   SukInjectRequest req = {0};

   void *origin = NULL;

   req.pid = pid;

   req.target = target_va_in_remote;  /* 目标进程 VA */

   req.origin = &origin;

   req.options = opt;

   SukInjectInstallResult result;

   char reason[256];

   SukInjectHook(&req, &result, reason, sizeof(reason));

   /* origin 是目标进程内 VA，本进程不能当函数指针调用 */

 ```

 CLI 示例：

 ```sh

   # 解析符号

   sukctl --allow -p $PID --module libfoo.so --symbol bar resolve

   # 生成式 wrapper：调 origin 后整数返回值 +7

   sukctl --allow -p $PID --module libfoo.so --symbol bar --origin-add 7 dbi-hook

   # agent 入口替换

   sukagentctl hook-elf -p $PID \

     --module token_cli --target-symbol validate_token \

     --elf ./token_agent.so --agent-symbol force_pass_token \

     --preflight --stop --resume

 ```

 更完整的说明见仓库文档：

 - 接口总览：docs/public-interfaces.md

 - 库：docs/library-guide.md

 - Agent：docs/agent-guide.md

 - CLI / proc：docs/cli-reference.md、docs/proc-interface.md

仓库：https://github.com/PPKunOfficial/sukinject

另外提一嘴测试环境，高通8+处理器，linux版本5.10

---

# 回复

## 回复 by Imxz (#2)

*2026-7-10 11:49*

tql

## 回复 by wx_插曲 (#3)

*2026-7-10 12:09*

tql

## 回复 by mb_cfjwplfo (#4)

*2026-7-10 12:24*

把 PC 重定向到 ghost，这条路对于libart不行，直接崩溃

## 回复 by x1a0f3n9 (#5)

*2026-7-10 13:04*

看样子得高内核手机才行对吧，试用一下

## 回复 by 祝今朝 (#6)

*2026-7-10 13:29*

666

## 回复 by 温泉划水鱼 (#7)

*2026-7-10 14:16*

大内核hook时代

## 回复 by YooHaa (#8)

*2026-7-10 14:59*

666

## 回复 by wx_听书人 (#9)

*2026-7-10 15:06*

6666

## 回复 by 小黄鸭爱学习 (#10)

*2026-7-10 15:13*

测试 依旧无痕hook大时代

## 回复 by mb_jnmxfjku (#11)

*2026-7-10 15:15*

666

## 回复 by xingbing (#12)

*2026-7-10 15:36*

666

## 回复 by Sigil (#13)

*2026-7-10 15:55*

1

## 回复 by 拍拖 (#14)

*2026-7-10 16:39*

感谢分享！

## 回复 by PPKun (#15)

*2026-7-10 17:27*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  把 PC 重定向到 ghost，这条路对于libart不行，直接崩溃
>

我readme里已经说了不行了，会卡死的

## 回复 by PPKun (#16)

*2026-7-10 17:28*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  看样子得高内核手机才行对吧，试用一下
>

不知道低版本行不行，我没低版本的手机了![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by mb_jhohnbzu (#17)

*2026-7-10 18:11*

1

## 回复 by FMNS (#18)

*2026-7-10 20:32*

666

## 回复 by mb_ldbucrik (#19)

*2026-7-10 20:44*

太强了，向大佬学习

## 回复 by mb_cfjwplfo (#20)

*2026-7-11 12:16*

>
> [PPKun](https://bbs.kanxue.com/user-970983.htm)
>  我readme里已经说了不行了，会卡死的
>

为什么不行啊大佬，我也好奇这个

## 回复 by PPKun (#21)

*2026-7-11 14:21*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  为什么不行啊大佬，我也好奇这个
>

ART很多地方会自改，ghost不会自动同步，要手动重编，没同步就会看起来是新代码，但是跑的是旧代码
然后很多涉及跳转的地方，也不好处理

## 回复 by git_25016MaYumioko (#22)

*2026-7-11 17:00*

牛逼

## 回复 by guardia (#23)

*2026-7-12 02:44*

666

## 回复 by 夜惜风雨 (#24)

*2026-7-12 11:00*

66666666

## 回复 by mb_qimctavn (#25)

*2026-7-13 07:53*

6

## 回复 by wx_范迪塞尔 (#26)

*2026-7-13 10:02*

66666

## 回复 by Gryffindoss (#27)

*2026-7-13 10:02*

/6666

## 回复 by 学计算机睡觉 (#28)

*2026-7-13 10:52*

1

## 回复 by git_71735namngsec-netizen (#29)

*2026-7-13 16:10*

666

## 回复 by git_71735namngsec-netizen (#30)

*2026-7-13 16:10*

666

## 回复 by iBa0 (#31)

*2026-7-13 16:44*

1

## 回复 by mb_bdctiije (#32)

*2026-7-14 02:56*

学习

## 回复 by mb_heldrckv (#33)

*2026-7-14 10:28*

666

## 回复 by guijingwen (#34)

*2026-7-14 10:33*

66

## 回复 by didiid (#35)

*2026-7-14 11:39*

666

## 回复 by puppet_w (#36)

*2026-7-14 13:56*

学习大佬知识

## 回复 by wx_晚风_407 (#37)

*2026-7-14 16:31*

666

## 回复 by mb_oqoqqkxl (#38)

*2026-7-15 02:12*

学习

## 回复 by Ankeys (#39)

*2026-7-15 10:25*

看看

## 回复 by 珍惜Any (#40)

*2026-7-15 11:35*

>
> [PPKun](https://bbs.kanxue.com/user-970983.htm)
>  我readme里已经说了不行了，会卡死的
>

这个问题前段时间我刚刚兼容，因为libart.so是2m内存页，需要拆成512个4k，然后这块DBI编译这块还有一堆坑。特别是libart.so里面jit编译那块，对DBI要求非常高。都需要让AI去处理，你可以把DBI之前原始指令，编译后的指令都保存成文件，然后交给AI让AI慢慢优化。

## 回复 by 博士9999 (#41)

*2026-7-15 15:36*

6

## 回复 by 桐人dx (#42)

*2026-7-15 16:02*

666

## 回复 by drf520 (#43)

*2026-7-15 17:12*

666666666666

## 回复 by Arsylk (#44)

*2026-7-16 01:04*

66

## 回复 by tonykros (#45)

*2026-7-16 08:15*

666

## 回复 by mb_xqptnehm (#47)

*2026-7-18 17:19*

6

## 回复 by Chxe (#48)

*2026-7-18 17:39*

1

## 回复 by mb_dswynejo (#49)

*2026-7-19 01:44*

6

## 回复 by 钟白 (#50)

*2026-7-19 02:14*

牛

## 回复 by mb_uepdckud (#51)

*2026-7-19 15:14*

牛的，看看隐藏

## 回复 by Vengeance (#52)

*2026-7-20 11:52*

66

## 回复 by mb_fnnjknab (#53)

*2026-7-21 04:10*

66

## 回复 by ulong9527 (#54)

*2026-7-22 09:30*

6

## 回复 by Yuuuual (#55)

*2026-7-23 13:32*

学习记录，感谢分享

## 回复 by huangbof (#56)

*2026-7-23 18:52*

还有 break-arm

## 回复 by wx_Kerberos (#57)

*2026-7-24 21:15*

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by mb_tewbhakr (#58)

*2026-7-26 01:34*

看看

## 回复 by mb_pesxllvn (#59)

*2026-7-28 09:53*

666

## 回复 by mb_yvuzbfvo (#60)

看看
