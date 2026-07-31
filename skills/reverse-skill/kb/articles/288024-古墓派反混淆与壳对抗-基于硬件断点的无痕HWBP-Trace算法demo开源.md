---
title: '[原创]古墓派反混淆与壳对抗：基于硬件断点的无痕HWBP-Trace算法demo开源'
url: https://bbs.kanxue.com/thread-288024.htm
tid: 288024
author: dadadasda
date: '2025-08-14'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析, 脱壳反混淆, HOOK注入, 源码框架]
crawled_at: '2026-07-31T15:38:53+08:00'
replies: 55
---

之前在帖子《[古墓派反native混淆方案：实机调试](https://bbs.kanxue.com/thread-286210.htm)》里提到的一套用于trace代码调用流程的一套算法，基于ptrace接口。

曾在各种BR跳转混淆库，以及臭名昭著某n_o_r_msg上跑出完整调用流程，在此开源下部分demo代码。

#### 整体线程架构包括

- 主线程：负责监听陷入trace_me的线程，获取当前tracee的信息（起始地址，tid，trace类型）fork生成专用执行trace的进程
- 专用线程：负责作为tracee的parent，接受事件信号，主要流程是读取pc前后指令，安装断点，执行单步

#### 核心函数包括

- 内核接口函数集(这个你们自己写)，负责调度与唤醒tracee/tracer，同时额外完成ptrace调用中不存在的额外task链接
- `do_find_next_jump`获取下一个跳转类的指令(这个你们自己用ptrace+指令解析库写)
- `ptrace_install_single_hwbp_at{nth}`为第\text{n}^{\text{th}}nth个slot安装硬件断点 (这个你们自己用ptrace_setregset写)
- `do_cont`/`do_cont_signal`/`do_single_step`使线程继续执行，带信号继续执行，单步执行 (这个你们自己用ptrace写)
- `doLogPc`/`doLogPcDeep`/`doLogPcOut` 记录执行相对pc值，过深调用的相对pc值，在本so库范围外调用的pc值 (这个你们自己写特定格式的文件行输出)

#### 开源动机？

- 目前本套trace算法已移入内核侧以解释器处理同步异常，用户层侧trace功能处于废弃状态，故而部分开源此版本的用户侧逻辑
- 每个人自己的想法覆盖范围其实是有限的，有人一起参与阅读思考可以集思广益
- 多写作表述有助于复习理清自己的开发思路，不然过些时间就忘了为啥当年那么写了
- 本套代码其实也可以用于执行无痕native-hook,分享给有开发能力的同志应该能够搞些更优雅的框架出来造福大众（本人自己不怎么喜欢各种现成框架，更爱现写现用，本体既轻量也不容易被针对反制）

#### demo代码细节

以下c代码组合一把梭哈编译成可执行文件便可实现一个HWBP-trace-server

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `/``/` `-``-``-``-``-``-``-``-``-``-` `↓↓↓↓ 需要自己去实现的逻辑，暂不开源 ↓↓↓↓``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``/``/``内核接口：标志当前线程为server线程``void xxxx_setselfengine(void);` `/``/``内核接口：获取当前标记uid的、调用完ptrace_me陷入睡眠的线程``void xxxx_fetchOne(struct trace_info``*` `&info);` `/``/``内核接口：声明当前线程为 线程[pid] 的专属tracer线程``void xxxx_markSelfTracer(``int` `pid);` `/``/` `解析当前进程pc 地址后` `2048``长度内的指令（``512``条指令），获取下一条 跳转类 指令``void do_find_next_jump(unsigned` `long``*` `next_pc);` `/``/` `-``-``-``-``-``-``-``-``-``-` `↑↑↑↑ 需要自己去实现的逻辑，暂不开源 ↑↑↑↑` `-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-`     `/``/` `进程静态变量` `#define enable_trace true` `/``/`  `是否是 bl blr类link跳转``static` `bool` `wrap_call``=``false;` `/``/`  `是否是ret类型的跳转``static` `bool` `ret_call``=``false;`  `/``/` `上一个安装的断点地址``static unsigned` `long` `last_hw_bp``=``0``;`  `/``/` `上一个安装 ret的断点地址``static unsigned` `long` `last_hw_bp_ret``=``0``;` `/``/` `调试线程号``static` `int` `traced_tid;`  `/``/` `trace最大深度``#define MAX_TRACE_DEPTH 2`  `/``/` `link调用深度``static` `int` `call_depth` `=` `-``MAX_TRACE_DEPTH;` `/``/` `入口点处的初始调用深度记录值，不变``static` `int` `orig_depth` `=` `-``MAX_TRACE_DEPTH;` |
|-|-|

核心trace逻辑代码：后面看情况补充注释更新一下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239 | `/``/` `-``-``-``-``-``-``-``-``-``-` `↓↓↓↓ 待补充和整理注释，这会有点写不动了 ↓↓↓↓``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``int` `call_flow_analyze_do(``bool` `norange){` `unsigned` `long` `pc``=``0``;` `/``/``获取目标线程当前pc后第一个跳转类指令的地址``unsigned` `long` `next_j_addr` `=` `do_find_next_jump(&pc);`  `/``/` `why do we stop` `in` `last phase?``/``/` `/``/``reasons:``if``(pc``=``=``last_hw_bp){`  `/``/` `reason` `1``: hit at setted jump bp``if``(PRINT_CMDLINE)printf(``"\t\t------hbp stop: 0x%lx\n"``,pc);` `ptrace_remove_single_hwbp_at(traced_tid,pc);`  `/``/``未设置返回暂停，返回了``if``(ret_call&&last_hw_bp_ret``=``=``0``){``printf(``"\t\t------no hbp ret: 0x%lx\n"``,pc);``printf(``"dep-1\n"``);``call_depth``-``=``1``;` `}` `if``(wrap_call){``call_depth``+``=``1``;``printf(``"dep+1\n"``);``}` `/``/``单步执行``goto singlestep;`  `}``else` `if``(pc``=``=``last_hw_bp_ret&&last_hw_bp_ret!``=``0``){` `/``/` `reason` `2``: hit at a ret bp``printf(``"\t\t------hbp ret: 0x%lx\n"``,pc);``ptrace_remove_single_hwbp_at2(traced_tid,pc);``last_hw_bp_ret``=``0``;`  `printf(``"dep-1\n"``);``call_depth``-``=``1``;`  `if``(pc``=``=``next_j_addr){` `if``(wrap_call){``printf(``"dep+1\n"``);``call_depth``+``=``1``;``}`  `if``(ret_call){``/``/``next``printf(``"dep-1\n"``);``call_depth``-``=``1``;` `}` `goto singlestep;``}` `goto docont_wbp;`  `}``else``{``/``/` `reason` `3``: single stepped` `if``(PRINT_CMDLINE)printf(``"\t\t------not a hbp, maybe step\n"``);`  `/``/` `now we check deep call after singlestep``if``(call_depth >``=``0` `&& last_hw_bp_ret>``0``){``/``/``too deep``doLogPcDeep(pc` `-` `so_range_start );``/``/``just log offset` `if``(!do_cont(traced_tid)){``printf(``"ptrace_cont fail\n"``);``}` `printf(``"\t\t---wait from sea---\n\n"``);``return` `0``;``}`    `/``/` `check``/``/` `we are out of` `range` `and` `we can trace link back` `if``(last_hw_bp_ret>``0``&&(pc>so_range_end\|\|pc<so_range_start)){\` `doLogPcOut(pc);` `/``/``just` `continue` `it``if``(!do_cont(traced_tid))``if``(PRINT_CMDLINE)printf(``"ptrace_cont fail\n"``);``printf(``"\t\t---wait for comingback---\n\n"``);``return` `0``;``}``else` `if``((pc>so_range_end\|\|pc<so_range_start) && last_hw_bp_ret``=``=``0``){` `if``(!do_cont(traced_tid))``if``(PRINT_CMDLINE)printf(``"ptrace_cont fail\n"``);` `printf(``"\t\t---trace must be ended---\n\n"``);` `return` `1``;``}`  `/``/` `we steped on a call`  `if``(pc``=``=``next_j_addr){` `if``(wrap_call){``printf(``"dep+1\n"``);``call_depth``+``=``1``;` `}` `if``(ret_call&&last_hw_bp_ret``=``=``0``){``/``/``next``printf(``"dep-1\n"``);``call_depth``-``=``1``;` `}` `goto singlestep;``}`  `goto docont_wbp;` `}`   `/``/` `next` `phase``singlestep:` `if``(call_depth<``=``orig_depth){``/``/``we are out of trace reange` `doLogPc(pc` `-` `so_range_start );` `printf(``"\t\t---out of functions---\n\n"``);` `return` `1``;` `}`  `if``(pc>so_range_start&&pc<so_range_end&&!norange)``doLogPc(pc` `-` `so_range_start );` `if``(norange)``doLogPc(pc);`  `if``(PRINT_CMDLINE)printf(``"\t\tdocont------wrap:%d ret:%d \n"``,wrap_call?``1``:``0``,ret_call?``1``:``0``);`  `if``(wrap_call){``/``/` `just` `set` `return` `bp``if``(ptrace_install_single_hwbp_at3(traced_tid,next_j_addr)){``last_hw_bp_ret``=``next_j_addr``+``4``;``/``/` `update``if``(PRINT_CMDLINE)printf(``"\t\t------set hbp ret before: 0x%lx\n"``,last_hw_bp_ret);` `}``else``printf(``"hbp set fail!!!\n"``);``}`  `/``/` `at branch point``printf(``"\t\t------single-step\n"``);` `/``/` `do single step``if``(!do_single_step(traced_tid))``printf(``"ptrace_single fail\n"``);` `return` `0``;` `/``/` `do` `continue` `with bp` `docont_wbp:` `/``/` `logpc``if``(pc>so_range_start&&pc<so_range_end&&!norange)``doLogPc(pc` `-` `so_range_start );` `if``(norange)``doLogPc(pc);`  `if``(PRINT_CMDLINE)printf(``"\t\tdocont------wrap:%d ret:%d \n"``,wrap_call?``1``:``0``,ret_call?``1``:``0``);`   `if``(wrap_call){` `if``(ptrace_install_single_hwbp_at2(traced_tid,next_j_addr)){``last_hw_bp``=``next_j_addr;` `last_hw_bp_ret``=``next_j_addr``+``4``;``/``/` `update` `if``(PRINT_CMDLINE)printf(``"\t\t------set hbp ret before: 0x%lx\n"``,last_hw_bp_ret);``}``else``printf(``"hbp set fail!!!\n"``);`  `}``else``{` `if``(PRINT_CMDLINE)printf(``"\t\t------set hbp before: 0x%lx\n"``,next_j_addr);` `if``(ptrace_install_single_hwbp_at(traced_tid,next_j_addr))``last_hw_bp``=``next_j_addr;``/``/` `update``else``printf(``"hbp set fail!!!\n"``);` `}` `if``(!do_cont(traced_tid))``printf(``"ptrace_cont fail\n"``);` `printf(``"\t\t------cont\n"``);` `return` `0``;` `}` `/``/` `-``-``-``-``-``-``-``-``-``-` `↑↑↑↑ 待补充和整理注释，这会有点写不动了 ↑↑↑↑` `-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-` |
|-|-|

以下为包含主次进程生命流程代码，较为简单

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100 | `/``/` `trace专用线程流程` `void call_thread_do(``int` `pid,unsigned` `long` `addr,``int` `type` `/``*``trace类型，内核中声明，可做hook也可做trace``-``flow``*``/``){` `int` `wait_status``=``-``1``;``bool` `norange``=``false;`  `/``/``tell tracee we are ready, could sleep here``xxxx_markSelfTracer(pid);` `/``/` `此时tracee已经将此线程ptrace_link` `printf(``"now thread tracer running for pid: %d\n"``,pid);` `/``/` `now the tracee` `is` `stopped` `and` `traced``/``/` `内核接口在目标线程第一次调用trace_me时候额外挂了sigtrap，用于同步线程状态``waitpid(pid,&wait_status,``0``);` `unsigned` `long` `start_addr``=``0``;` `if``(``type``=``=``TYPE_PTHREAD_CREATED){``printf(``"thread func start at: %lx running for pid: %d\n"``,addr,pid);``}` `/``/``根据内核传来的地址判断当前trace范围``start_addr``=``get_start_addr_fortype(addr,``type``);` `while``(WIFSTOPPED(wait_status)){` `int` `signal` `=` `WSTOPSIG(wait_status);` `if``(signal!``=``5``){``/``/``not` `triggered by trap``printf(``"tracee process %d unexpected stopped by signal %d at pc: 0x%lx\n"``, pid,signal,getpc(pid)``-``start_addr);``do_cont_signal(pid,signal);``waitpid(pid, &wait_status,` `0``);``continue``;``}` `if``(``type``=``=``TYPE_TRACE_CALLFLOW && enable_trace){``/``/``处理每一段trace``if``(call_flow_analyze_do(norange)){``/``/` `一般为线程执行结束``/``/` `或者是踩踏到出口点``printf(``"-----detach!! tid: %d\n"``,pid);``ptrace(PTRACE_DETACH,traced_tid,``0``,``0``);` `wait_status``=``0``;``return``;``}``}` `waitpid(pid,&wait_status,``0``);``continue``;``}``}` `int` `engine_server(){` `struct trace_info info;` `/``/` `we do` `not` `collect thread info``signal(SIGCHLD,SIG_IGN);`  `/``/` `mark` `self` `as engine``xxxx_setselfengine();` `/``/` `主循环` `do{` `/``/``get tracee info` `or` `sleep``xxxx_fetchOne(&info);` `int` `tid``=``info.pid;``/``/` `no use``unsigned` `long` `addr``=``info.addr_s;` `/``/``used as` `type` `in` `server mode``int` `type``=``(``int``)info.addr_e;` `printf(``"get tracee tid:%d type: %d\n"``,tid,``type``);` `/``/` `now we have tracee info``/``/` `子进程任务``if``(fork()``=``=``0``){` `/``/``不使用clone类的pthread_create以免污染局部变量``call_thread_do(tid,addr,``type``);``return` `0``;``}` `/``/``go on` `and` `fetch` `next` `}``while``(``1``);` `}`  `int` `main(``int` `argc, char``*``*` `argv){``engine_server();``}` |
|-|-|

#### trace 文件输出

最后写文件生成的trace文件示例，用以结合ida静态分析原始so库与内存dump文件

 ![image](https://bbs.kanxue.com/upload/attach/202508/1006186_9FNCD5VJKEF7FC9.webp)

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-8-14 09:55*

大佬，yyds

## 回复 by wx_插曲 (#3)

*2025-8-14 09:59*

大佬，yyds

## 回复 by bullyxy (#4)

*2025-8-14 10:10*

学习学习

## 回复 by artake (#5)

*2025-8-14 10:10*

666

## 回复 by misskings (#6)

*2025-8-14 10:19*

学习学习

## 回复 by seeeseee (#7)

*2025-8-14 10:20*

学习

## 回复 by dfJerry (#8)

*2025-8-14 10:22*

66

## 回复 by 丶咖啡猫丶 (#9)

*2025-8-14 10:34*

666

## 回复 by mb_donutrph (#10)

*2025-8-14 10:46*

666

## 回复 by xxjj678 (#11)

*2025-8-14 10:49*

666

## 回复 by uni7corn (#12)

*2025-8-14 11:01*

6666，学习一下。

## 回复 by Imxz (#13)

*2025-8-14 11:02*

tql

## 回复 by mb_tmbvnlxt (#14)

*2025-8-14 12:54*

666

## 回复 by ssafosl (#15)

*2025-8-14 13:36*

666

## 回复 by 魅叉 (#16)

*2025-8-14 13:39*

666

## 回复 by mb_wwhqckrx (#17)

*2025-8-14 13:40*

你的帖子非常有用，感谢分享！

## 回复 by mb_vanjeoof (#18)

*2025-8-14 13:56*

666

## 回复 by zZhouQing (#19)

*2025-8-14 14:24*

当年，全真教创始祖师王重阳举义反抗金兵，建造了一座大型仓库存放军粮物资，为了掩人耳目而设计成古墓形状。古墓其中机关众多。抗金义军失败后，王重阳愤而隐居古墓，自称将其称作“活死人墓”，意思是虽生犹死，与金人不共戴天。当世女侠林朝英对他一往情深，叹惜他一副大好身手埋没在一座坟墓之中，便使激将法将他骗出石墓，盼与王重阳携手同闯江湖。但王重阳于邦国之仇难以忘怀，时刻记着收复山河的家国大事，对林朝英的深情厚意虽然深知，但是只好装痴乔呆。林朝英还以为王重阳瞧她不起，终于在终南山与他比武决胜，以巧计赢得石墓赌注。从此她住在墓中，终身未曾复出，开创了古墓派。

## 回复 by linkin5epk (#20)

*2025-8-14 14:26*

666

## 回复 by wx_huhu_859 (#21)

*2025-8-14 16:17*

1

## 回复 by 小尘0000 (#22)

*2025-8-14 16:55*

666

## 回复 by mb_uciwwrxu (#23)

*2025-8-14 19:05*

慕名学习

## 回复 by wx_霿凇 (#24)

*2025-8-15 15:14*

666

## 回复 by 暴强 (#25)

*2025-8-17 08:54*

66666666666

## 回复 by fangliangz (#26)

*2025-8-18 09:26*

666

## 回复 by mb_undccabr (#27)

*2025-8-18 13:05*

6666666666666666

## 回复 by wx_荣仔 (#28)

*2025-8-18 15:12*

666666加油高手。等你补充

## 回复 by mb_rjoxthlj (#29)

*2025-8-18 19:01*

666

## 回复 by 寻梦之璐 (#30)

*2025-8-18 22:23*

1

## 回复 by mb_dcjxxhsk (#31)

*2025-8-19 17:33*

666

## 回复 by 夜惜风雨 (#32)

*2025-8-20 00:29*

6666

## 回复 by wen55444 (#33)

*2025-8-20 18:55*

感谢分享

## 回复 by mb_kbkqyusp (#34)

*2025-8-23 11:10*

66666666

## 回复 by mb_dmryhnwz (#35)

*2025-8-23 12:56*

66

## 回复 by TeamAR (#36)

*2025-8-23 13:36*

66666666666

## 回复 by 祝枝山 (#37)

*2025-8-23 16:31*

111

## 回复 by wx_Kerberos (#38)

*2025-8-26 00:29*

![image](https://bbs.kanxue.com/view/img/face/012.gif)

## 回复 by baichisi (#39)

*2025-8-26 10:56*

6

## 回复 by XCicada (#40)

*2025-8-28 16:41*

66666666666

## 回复 by mb_mrjjcxgk (#41)

*2025-8-29 15:59*

666

## 回复 by mb_akowpmjs (#42)

*2025-9-10 19:52*

666

## 回复 by jasonxgw (#43)

*2025-9-24 17:13*

tql

## 回复 by asuralove (#44)

*2025-10-10 10:02*

666

## 回复 by mb_irhdtnzm (#45)

*2025-10-14 15:20*

1

## 回复 by Mr.He (#46)

*2025-10-30 14:35*

666

## 回复 by 大萨达 (#47)

*2025-11-9 12:42*

6666

## 回复 by 暗香沉浮 (#48)

*2025-11-16 09:12*

11

## 回复 by 嘎嘎真的很棒 (#49)

*2025-11-21 18:29*

学习

## 回复 by Ankeys (#50)

*2025-12-26 13:20*

66666

## 回复 by Zepp7289 (#51)

*2026-2-9 15:53*

tql

## 回复 by wx_白鸟之诗 (#52)

*2026-3-1 13:48*

6666

## 回复 by wx_dangerous (#53)

*2026-4-1 19:53*

6

## 回复 by GeQ1an (#54)

*2026-6-1 16:57*

666

## 回复 by mb_fzwldzav (#55)

*2026-6-15 12:42*

mask

## 回复 by Yuuuual (#56)

*2026-7-23 13:38*

学习记录，感谢分享
