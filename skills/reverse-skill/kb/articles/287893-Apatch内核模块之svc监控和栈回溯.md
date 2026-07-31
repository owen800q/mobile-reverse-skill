---
title: '[原创]Apatch内核模块之svc监控和栈回溯'
url: https://bbs.kanxue.com/thread-287893.htm
tid: 287893
author: 孤恒
date: '2025-08-05'
tags: [Android安全, 原创, 基础理论, 逆向分析, 系统相关]
crawled_at: '2026-07-31T15:42:14+08:00'
replies: 157
---

# 前言

现代 app 的壳中有大量的 syscall 的直接调用，想要知道其中的调用参数以及结果有以下方法：
1、使用 frida 进行内存搜索 svc 0 指令的机器码（01 00 00 D4)，然后自己想办法干掉
2、使用 seccomp 进行拦截，使用 seccomp 的过程中可能会遇到一些奇奇怪怪的问题
3、使用内核模块在内核态进行拦截
在 Apatch 之前编写的内核模块需要针对单独的内核进行编译，并且编译环境还需要完整内核的依赖文件，这种方法还需要修改内核设置并将内核放入到系统映像中重新刷机。非常复杂，使用 Apatch 编译的内核模块加载方便且具有一定的通用性。

# 配置编译环境

下载官方的 github
<https://github.com/bmax121/KernelPatch/tree/dev>
下载 gun 编译工具链
<https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads>
添加环境

| 1 | `export PATH``=``$PATH:``/``opt``/``arm``-``gnu``-``toolchain``/``bin``/``aarch64``-``none``-``elf``-` |
|-|-|

打开官方目录中的 kpms/demo-hello，使用 make 编译

| 1 | `make` |
|-|-|

会在本目录下生成 hello.kpm 文件，把该文件 push 到手机里，然后在 Apatch 内核模块页面加载
加载成功后可以在 adb shell（root 权限）下使用 dmesg 指令输出内核日志

# svc 监控

在官方目录中 kpms/demo-syscall 下有关于 openat 的 hook
我们注意到在 init 中有两种 apatch 提供的 hook 方式，一种是fp_hook_syscalln，一种是inline_hook_syscalln。
笔者的需求是监控 readlinkat 的入参和栈回溯，那么可以使用inline_hook_syscalln 实现
这里复制一下一整个目录，修改一下目录名
将 syscall.c 中无关的内容去除，新增一个before_readlinkat 函数，根据参数表
编写 log 输出

| 12345678910111213141516 | `void before_readlinkat(hook_fargs4_t` `*``args, void` `*``udata){``const char __user` `*``filename` `=` `(typeof(filename))syscall_argn(args,` `1``);``char buf[``1024``];``compat_strncpy_from_user(buf, filename, sizeof(buf));``struct task_struct` `*``task` `=` `current;``pid_t pid` `=` `-``1``, tgid` `=` `-``1``;``if` `(__task_pid_nr_ns) {``pid` `=` `__task_pid_nr_ns(task, PIDTYPE_PID,` `0``);``tgid` `=` `__task_pid_nr_ns(task, PIDTYPE_TGID,` `0``);``}``char comm[``1024``];``get_task_comm_func(comm, sizeof(comm), task);``pr_info(``"readlinkat pid: %d, filename: %s, process: %s"``, pid, buf, comm);``struct pt_regs` `*``regs` `=` `_task_pt_reg(task);``unwind_user_stack(task, pid);``}` |
|-|-|

这里说明一下get_task_comm_func 函数，这个是内核导出函数get_task_comm
需要在前面定义函数类型，然后通过kallsyms_lookup_name 函数获取函数指针调用（相当于 dlsym 获取函数指针）

| 123 | `typedef struct mm_struct` `*``(``*``get_task_mm)(struct task_struct` `*``task);``get_task_mm get_task_mm_func;``get_task_comm_func` `=` `(typeof(__get_task_comm))kallsyms_lookup_name(``"__get_task_comm"``);` |
|-|-|

内核导出函数列表可以查看/proc/kallsyms 文件

| 1 | `cat` `/``proc``/``kallsyms` |
|-|-|

# 栈回溯实现

我们想要定位哪里调用的 svc 就需要用到栈回溯，由于内核中没有直接可以进行栈回溯的函数，这个需要我们自己实现，arm64 下的栈回溯实现主要是靠 fp 寄存器。
首先知道，arm64 寄存器中 x29 是 fp 寄存器，x30 是 lr 寄存器，其中 lr 寄存器存储了函数的返回地址，如果是调用多层函数的话那么会把 lr 寄存器和 fp 寄存器中的值存储到栈中并将地址存储到 fp 寄存器中，具体如下图
 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/979192_BQ4S6VKZ6Y7XRSY.webp)
那么我们只需要反复读取 fp 寄存器中的值就可以拿到以往 lr 寄存器中的值。
栈回溯代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `typedef` `int` `(``*``access_process_vm) (struct task_struct` `*``tsk, unsigned` `long` `addr, void` `*``buf,` `int` `len``,` `int` `write);``access_process_vm access_process_vm_func;``typedef struct mm_struct` `*``(``*``get_task_mm)(struct task_struct` `*``task);``get_task_mm get_task_mm_func;``typedef void (``*``mmput) (struct mm_struct` `*``mm);``mmput mmput_func;` `struct user_frame {``unsigned` `long` `fp;``unsigned` `long` `lr;``};` `bool` `unwind_user_stack(struct task_struct` `*``task, pid_t pid){``struct user_frame frame;``int` `i;` `struct pt_regs` `*``regs` `=` `_task_pt_reg(task);``frame.fp` `=` `regs``-``>regs[``29``];``frame.lr` `=` `regs``-``>regs[``30``];``unsigned` `long` `pc` `=` `regs``-``>pc;` `struct mm_struct``*` `mm` `=` `get_task_mm_func(task);``if``(!mm)``return` `false;` `for``(i` `=` `0``; i <` `16``; i``+``+``){` `if``(i` `=``=` `0``){``pr_info(``"pid: %d, frame[%d]: lr: %llx, fp: %llx pc: %llx\n"``, pid, i, frame.lr, frame.fp, pc);``}``else``{``pr_info(``"pid: %d, frame[%d]: lr: %llx, fp: %llx\n"``, pid, i, frame.lr, frame.fp);``}` `if``(!frame.fp \|\| !frame.lr){``break``;``}``if``(access_process_vm_func(task, frame.fp, &frame, sizeof(struct user_frame),` `0``) !``=` `sizeof(frame)){``break``;``}``}``mmput_func(mm);``}` `/``/` `init``access_process_vm_func` `=` `(typeof(access_process_vm))kallsyms_lookup_name(``"access_process_vm"``);``get_task_mm_func` `=` `(typeof(get_task_mm))kallsyms_lookup_name(``"get_task_mm"``);``mmput_func` `=` `(typeof(mmput))kallsyms_lookup_name(``"mmput"``);` |
|-|-|

此处解释一下几个函数
1、get_task_mm 获取进程 mm_struct（用户态虚拟内存） 防止被销毁
2、access_process_vm 读写用户态中的内存空间，第一个参数是 task 也就进程状态，第二个参数是目标地址，第三个参数是为读写数据分配的缓冲区地址 ，第四个参数是读写数据的长度，第五个参数是 0（读）1（写）
3、 mmput 只用于释放 get_task_mm() 获取的对象 。
实现效果如图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/979192_25A7XVJUEAV7MQ2.webp)

---

# 回复

## 回复 by mb_dybhojzi (#2)

*2025-8-5 17:36*

6666

## 回复 by 墨穹呢 (#3)

*2025-8-5 20:59*

感谢分享

## 回复 by virjar (#4)

*2025-8-5 22:00*

666

## 回复 by wx_huhu_859 (#5)

*2025-8-6 00:40*

1

## 回复 by Imxz (#6)

*2025-8-6 09:24*

太牛了!

## 回复 by method (#7)

*2025-8-6 09:48*

1

## 回复 by 西瓜帅 (#8)

*2025-8-6 10:34*

可以的这帖子

## 回复 by Ankeys (#9)

*2025-8-6 10:49*

6

## 回复 by K4NG (#10)

*2025-8-6 10:49*

tql

## 回复 by 涿州飞神 (#11)

*2025-8-6 10:49*

66666

## 回复 by mb_hiqkelrh (#12)

*2025-8-6 10:49*

666

## 回复 by tuosen (#13)

*2025-8-6 12:07*

文章写的挺好的, 简单易理解
1.使用inline_hook_syscalln hook  readlinkat
2.获取当前进程的task_struct结构
3.获取当前task的寄存器信息, 帧指针fp, lr返回地址, pc当前执行地址
4.循环打印帧信息, 通过access_process_vm 获取下一帧数据

## 回复 by mb_uvyukvot (#14)

*2025-8-6 14:36*

666

## 回复 by mb_tmbvnlxt (#15)

*2025-8-6 15:49*

666

## 回复 by mb_jnmxfjku (#16)

*2025-8-6 17:45*

666

## 回复 by 4Chan (#17)

*2025-8-6 17:53*

666

## 回复 by wx_插曲 (#18)

*2025-8-6 18:25*

666

## 回复 by mb_pobqzscg (#19)

*2025-8-6 18:27*

666

## 回复 by 秃顶 (#20)

*2025-8-6 18:29*

666

## 回复 by mb_cbgtaveo (#21)

*2025-8-6 20:31*

66666

## 回复 by 雅鸦歌 (#22)

*2025-8-6 20:44*

666

## 回复 by 上官兮唐 (#23)

*2025-8-6 22:06*

666

## 回复 by kingking888 (#24)

*2025-8-6 22:58*

666

## 回复 by XCicada (#25)

*2025-8-7 10:13*

感谢分享

## 回复 by Yang1k (#26)

*2025-8-7 10:16*

6

## 回复 by git_27068Lych1e1 (#27)

*2025-8-7 15:29*

感谢分享

## 回复 by iBa0 (#28)

*2025-8-7 16:12*

666

## 回复 by TeamAR (#29)

*2025-8-7 16:14*

learning

## 回复 by mJqalJqN (#30)

*2025-8-7 19:06*

1

## 回复 by didiid (#31)

*2025-8-7 19:18*

666

## 回复 by koflfy (#32)

*2025-8-8 11:18*

mark

## 回复 by mb_lfvhycml (#33)

*2025-8-8 14:14*

66666

## 回复 by mb_qqlojqnm (#34)

*2025-8-8 14:45*

感谢分享

## 回复 by mb_donutrph (#35)

*2025-8-8 16:14*

666

## 回复 by kinglyu (#36)

*2025-8-9 00:08*

感谢分享！

## 回复 by YiGod (#37)

*2025-8-9 11:24*

gxfx

## 回复 by huangjw (#38)

*2025-8-9 14:34*

牛逼

## 回复 by mb_rbfpkjqw (#39)

*2025-8-9 18:17*

666

## 回复 by ldehua (#40)

*2025-8-9 19:03*

感谢分享

## 回复 by 完顔修正 (#41)

*2025-8-9 20:42*

感谢分享

## 回复 by wushuang双 (#42)

*2025-8-10 15:12*

感谢分享

## 回复 by Zepp7289 (#43)

*2025-8-10 22:50*

save_stack_trace_user内核符号可以打印回溯

## 回复 by 寒号鸟二代 (#44)

*2025-8-11 09:39*

666

## 回复 by xiaoc996 (#45)

*2025-8-11 09:46*

666

## 回复 by guijingwen (#46)

*2025-8-11 10:07*

66

## 回复 by mb_xjdhrmck (#47)

*2025-8-11 10:37*

666

## 回复 by artake (#48)

*2025-8-11 12:14*

666

## 回复 by wuxin159 (#49)

*2025-8-11 15:34*

感谢分享

## 回复 by bullyxy (#50)

*2025-8-11 19:47*

感谢分享

## 回复 by 飆汗吉米 (#51)

*2025-8-11 21:45*

感谢分享

## 回复 by mb_pesxllvn (#52)

*2025-8-12 17:40*

666

## 回复 by 无视红绿灯 (#53)

*2025-8-12 19:51*

6666

## 回复 by 废人one (#54)

*2025-8-12 20:24*

111111111111111

## 回复 by 大嘴巴巴 (#55)

*2025-8-14 16:39*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by dreameriii (#56)

*2025-8-14 19:55*

thanks for sharing !

## 回复 by jamlops (#57)

*2025-8-14 20:09*

感谢分享

## 回复 by 三一米田 (#58)

*2025-8-15 09:45*

..

## 回复 by 山竹笠 (#59)

*2025-8-15 11:29*

感谢分享

## 回复 by 无所从来 (#60)

*2025-8-15 17:26*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 万里星河 (#61)

*2025-8-16 10:58*

本人小白 读取用户空间数据为何不用copy_from_user 如果是arm32 又该如何栈回溯

## 回复 by 孤恒 (#62)

*2025-8-18 11:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Zepp7289](https://bbs.kanxue.com/user-993285.htm)
>
>  save_stack_trace_user内核符号可以打印回溯
>
>

我这里内核导出函数只有save_stack_trace

## 回复 by 孤恒 (#63)

*2025-8-18 11:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  本人小白 读取用户空间数据为何不用copy_from_user 如果是arm32 又该如何栈回溯
>
>

access_process_vm不受进程限制，copy_from_user在低版本内核里可以使用，高版本的没有试过。
arm32的堆栈里fp和lr与arm64堆栈位置相反，也就是说把结构体里的fp和lr的定义反过来写，然后fp寄存器在arm32中是r11，lr寄存器是r14

## 回复 by 万里星河 (#64)

*2025-8-18 12:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  孤恒](https://bbs.kanxue.com/user-979192.htm)
>
>  access_process_vm不受进程限制，copy_from_user在低版本内核里可以使用，高版本的没有试过。
> arm32的堆栈里fp和lr与arm64堆栈位置相反，也就是说把结构体里的fp ...
>
>

谢谢

## 回复 by fkueihcy (#65)

*2025-8-18 16:39*

感谢分享

## 回复 by goldening (#66)

*2025-8-18 16:41*

谢谢分享

## 回复 by 寻梦之璐 (#67)

*2025-8-18 22:47*

1

## 回复 by 夜惜风雨 (#68)

*2025-8-21 23:56*

666

## 回复 by ADR66 (#69)

*2025-8-22 06:58*

66666666666666666

## 回复 by mb_eqttlgdj (#70)

*2025-8-22 16:29*

6666

## 回复 by 小尘0000 (#71)

*2025-8-23 14:51*

666

## 回复 by lixianhuei (#72)

*2025-8-25 14:10*

66666

## 回复 by mb_pklvtpgn (#73)

*2025-8-25 14:57*

1

## 回复 by 酒仙桥之虎 (#74)

*2025-8-27 10:40*

666

## 回复 by apxar (#75)

*2025-8-28 20:06*

6

## 回复 by AK1988DA (#76)

*2025-8-29 16:41*

2

## 回复 by flysea (#77)

*2025-8-29 17:30*

感谢分享如此详细的内容

## 回复 by mb_irhdtnzm (#78)

*2025-9-1 09:02*

1

## 回复 by mb_vxufgfcw (#79)

*2025-9-2 15:19*

孤恒666

## 回复 by 逆道而行 (#80)

*2025-9-3 17:26*

6666

## 回复 by `姚大齐丶Nayo (#81)

*2025-9-4 15:26*

66666

## 回复 by mb_loezwfrh (#82)

*2025-9-11 15:56*

66666

## 回复 by wx_Yo__Booo_0 (#83)

*2025-9-12 11:14*

感谢分享

## 回复 by FMNS (#84)

*2025-9-14 06:04*

感谢分享

## 回复 by 随风而行aa (#85)

*2025-9-21 23:15*

看看

## 回复 by mb_pnyyaazf (#86)

*2025-9-22 17:56*

感谢分享

## 回复 by mb_anbthlub (#87)

*2025-9-22 20:44*

66

## 回复 by Ms135 (#88)

*2025-9-23 16:10*

666

## 回复 by mb_jwevvolh (#89)

*2025-10-4 21:29*

666

## 回复 by Arsylk (#90)

*2025-10-5 07:48*

66

## 回复 by mb_alztilld (#91)

*2025-10-8 10:00*

666

## 回复 by Mr.He (#92)

*2025-10-9 11:39*

666

## 回复 by git_52399CodeExia54 (#93)

*2025-10-10 02:27*

Good content

## 回复 by doraemonliu (#94)

*2025-10-10 10:43*

6666

## 回复 by xxjj678 (#95)

*2025-10-12 00:33*

666

## 回复 by 黑洞yyh (#96)

*2025-10-12 11:44*

666

## 回复 by dsr000 (#97)

*2025-10-14 14:33*

666

## 回复 by xianhuimin (#98)

*2025-10-14 14:39*

感谢分享

## 回复 by 魔童 (#99)

*2025-10-21 10:20*

66666666

## 回复 by azd放 (#100)

*2025-10-21 11:17*

感谢分享

## 回复 by mb_sjxphvyl (#101)

*2025-10-21 14:37*

666

## 回复 by thouger_ (#102)

*2025-10-23 17:25*

感谢分享

## 回复 by 六尘之幻 (#103)

*2025-10-28 16:47*

666学习一下

## 回复 by 0526 (#104)

*2025-10-29 07:47*

感谢分享

## 回复 by 卡坦精 (#105)

*2025-10-29 08:47*

666

## 回复 by axpol (#106)

*2025-10-29 13:55*

666

## 回复 by pigsub (#107)

*2025-10-29 14:36*

66666

## 回复 by Sharp_Wang (#108)

*2025-10-30 10:32*

666

## 回复 by Xx_gg (#109)

*2025-11-4 08:48*

6666

## 回复 by mb_krbimell (#110)

*2025-11-4 09:37*

6666

## 回复 by 曰你 (#111)

*2025-11-4 10:01*

1

## 回复 by mb_dcjxxhsk (#112)

*2025-11-4 10:12*

666

## 回复 by mickelfeng (#113)

*2025-11-5 11:42*

https://github.com/bmax121/KernelPatch/tree/dev 下载dev是因为可以打印日志吗

## 回复 by wx_晚风_407 (#114)

*2025-11-5 17:12*

666666666

## 回复 by mb_cizqyhuh (#115)

*2025-11-6 17:30*

感谢分享！用内核模块监控svc调用确实比传统方案更实用，特别是arm64栈回溯通过fp寄存器解析调用链的思路很巧妙。完整技术脉络已整理成[思维导图](https://www.anygraphanywhere.com/automap/mindmap.html?link=1750930532811-1762421844722)，对系统安全分析很有参考价值。

![image](https://bbs.kanxue.com/upload/attach/202511/1040915_42XHCMBHVFCN2H2.webp)

## 回复 by YooHaa (#116)

*2025-11-7 15:14*

666

## 回复 by 大萨达 (#117)

*2025-11-9 11:35*

666

## 回复 by mb_basgiwmq (#118)

*2025-11-15 02:22*

6666666666666666666666

## 回复 by 带带弟弟吧 (#119)

*2025-11-16 02:14*

1

## 回复 by mb_qimctavn (#120)

*2025-11-16 14:12*

6

## 回复 by 西北吹风 (#121)

*2025-11-17 15:06*

感谢分享

## 回复 by GEKEZYX (#122)

*2025-11-21 13:52*

666

## 回复 by Heiyiren123 (#123)

*2025-11-21 16:25*

学习学习

## 回复 by mb_mmlkqxal (#124)

*2025-11-26 15:03*

11

## 回复 by wx_八 (#125)

*2025-12-9 19:53*

tql

## 回复 by mb_vyiuuicw (#126)

*2025-12-12 11:34*

666

## 回复 by TinM! (#127)

*2025-12-18 18:13*

666

## 回复 by lqfcugo (#128)

*2025-12-29 18:37*

学习下。

## 回复 by mb_ylhhknsp (#129)

*2026-1-5 17:56*

????

## 回复 by mb_ysikfhxt (#130)

*2026-1-6 17:41*

1

## 回复 by AMy_德友 (#131)

*2026-1-7 14:51*

555

## 回复 by Ddddz (#132)

*2026-1-7 16:23*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_spjzwhqd (#133)

*2026-1-26 03:48*

感谢感谢

## 回复 by bygrand (#134)

*2026-1-27 21:48*

123

## 回复 by nixiadexue (#135)

*2026-1-31 14:50*

感谢分享

## 回复 by 安小卓 (#136)

*2026-2-6 14:13*

666

## 回复 by fjqisba (#137)

*2026-2-11 18:43*

监控太重要了，必须得学习

## 回复 by mb_ajghhdbh (#138)

*2026-3-4 15:56*

1

## 回复 by Layer1 (#139)

*2026-3-9 09:50*

666

## 回复 by mb_ugnawvja (#140)

*2026-3-17 17:30*

感谢分享

## 回复 by mb_ykavguun (#141)

*2026-3-17 18:02*

1

## 回复 by jack.Chen (#142)

*2026-3-25 19:33*

感谢分享

## 回复 by 温泉划水鱼 (#143)

*2026-3-29 19:41*

学习

## 回复 by mb_ghzqfgyt (#144)

*2026-3-31 14:07*

感谢感谢

## 回复 by mb_mhoivioy (#145)

*2026-4-5 00:01*

刚好在研究这个东西，感谢分享

## 回复 by mb_uktygsmq (#146)

*2026-4-10 17:46*

666

## 回复 by AyonA333 (#147)

*2026-4-27 18:51*

666

## 回复 by wgetlaidu (#148)

*2026-4-29 18:13*

666

## 回复 by wgetlaidu (#149)

*2026-4-29 18:13*

666

## 回复 by uboluo (#150)

*2026-5-19 10:04*

666

## 回复 by mb_mihutdve (#151)

*2026-5-19 21:39*

6

## 回复 by 钱钱钱￥ (#152)

*2026-6-25 17:29*

来学习了

## 回复 by mb_jegknedl (#153)

*2026-6-28 05:25*

学习

## 回复 by wx_coddvccwyh (#154)

*2026-7-11 04:23*

666666

## 回复 by lazybulazy (#155)

*2026-7-13 23:42*

666

## 回复 by mb_bdctiije (#156)

*2026-7-16 06:43*

学习

## 回复 by git_73275XuanLong18 (#157)

*2026-7-21 00:26*

666

## 回复 by wx_白鸟之诗 (#158)

111
