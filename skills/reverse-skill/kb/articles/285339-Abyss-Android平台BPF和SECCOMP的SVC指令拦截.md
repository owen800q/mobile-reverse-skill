---
title: '[原创]【Abyss】Android平台BPF和SECCOMP的SVC指令拦截'
url: https://bbs.kanxue.com/thread-285339.htm
tid: 285339
author: Tiony.bo
date: '2025-01-23'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:14:31+08:00'
replies: 25
---

>
> `Android`平台从上到下，无需ROOT/解锁/刷机，应用级拦截框架的最后一环 —— `SVC`系统调用拦截。
>
>
>

[☞ Github: https://www.github.com/iofomo/abyss ☜](https://www.github.com/iofomo/abyss)　

 ![image](https://bbs.kanxue.com/upload/attach/202501/909890_ZBDG9ARW9R5BS42.webp)

由于我们虚拟化产品的需求，需要支持在普通的`Android`手机运行。我们需要搭建覆盖应用从上到下各层的应用级拦截框架，而`Abyss`作为系统`SVC`指令的调用拦截，是我们最底层的终极方案。

源码位置：https://github.com/iofomo/abyss/tree/main/svcer

## 01. 说明

**Seccomp（Secure Computing Mode）：**

`Seccomp` 是 `Linux` 内核的一个安全特性，用于限制进程可以执行的系统调用。它通过过滤系统调用，防止恶意程序执行危险操作。`Seccomp` 通常与 `BPF` 结合使用，以实现更灵活的过滤规则。

**BPF（Berkeley Packet Filter）：**

`BPF` 是一种内核技术，最初用于网络数据包过滤，但后来被扩展用于更广泛的用途，包括系统调用过滤。`BPF` 程序可以在内核中运行，用于检查和过滤系统调用。

## 02. 主要流程

首先，配置 `BPF` 规则，如下我们配置了目标系统调用号的拦截规则，不在这个名单内的就放过，这样可以实现仅拦截我们关心的系统调用（即函数），提升拦截效率和稳定性。

| 12345678910111213 | `static` `void` `doInitSyscallNumberFilter(``struct` `sock_filter* filter, unsigned` `short``& i) {``// Load syscall number into accumulator``filter[i++] = BPF_STMT(BPF_LD \| BPF_W \| BPF_ABS, (offsetof(``struct` `seccomp_data, nr)));``// config target syscall``// add more syscall here ...``//    filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, __NR_openat, 5, 0);``//    filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, __NR_getcwd, 4, 0);``//    filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, __NR_chdir, 3, 0);``//    filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, __NR_execve, 2, 0);``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, __NR_openat, 1, 0);` `filter[i++] = BPF_STMT(BPF_RET \| BPF_K, SECCOMP_RET_ALLOW);``}` |
|-|-|

然后，我们需要过滤掉一些系统库和自身库，防止写入死循环。

- 自身实现库的过滤【必须】
- `vdso` 的过滤【必须】
- `linker` 的过滤【可选，提效】
- `libc` 的过滤【可选，提效】

通过解析进程 `maps` 中对应库地址区间，配置跳过此区间的系统调用规则。

| 12345678910111213141516 | `static` `void` `doInitSyscallLibFilterByAddr(``struct` `sock_filter* filter, unsigned` `short``& i,` `const` `uintptr_t``& start,` `const` `uintptr_t``& end) {``// Load syscall lib into accumulator``#if defined(__arm__)``filter[i++] = BPF_STMT(BPF_LD \| BPF_W \| BPF_ABS, offsetof(``struct` `seccomp_data, instruction_pointer));``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JGE \| BPF_K, start, 0, 2);``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JGE \| BPF_K, end, 1, 0);``filter[i++] = BPF_STMT(BPF_RET \| BPF_K, SECCOMP_RET_ALLOW);``#else // __aarch64__``filter[i++] = BPF_STMT(BPF_LD \| BPF_W \| BPF_ABS, (offsetof(``struct` `seccomp_data, instruction_pointer) + 4));``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JEQ \| BPF_K, (uint32_t)(start >> 32), 0, 4);``filter[i++] = BPF_STMT(BPF_LD \| BPF_W \| BPF_ABS, (offsetof(``struct` `seccomp_data, instruction_pointer)));``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JGE \| BPF_K, (uint32_t)start, 0, 2);``filter[i++] = BPF_JUMP(BPF_JMP \| BPF_JGE \| BPF_K, (uint32_t)end, 1, 0);``filter[i++] = BPF_STMT(BPF_RET \| BPF_K, SECCOMP_RET_ALLOW);``#endif``}` |
|-|-|

其次，应用以上配置。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546 | `struct` `sigaction act = { 0 };``act.sa_flags = SA_SIGINFO \| SA_NODEFER;``act.sa_sigaction = handleSignalAction;``struct` `sigaction old_sa = {};` `ret = sigaction(SIGSYS, &act, &old_sa);``if` `(0 != ret) {``LOGSVCE(``"sigaction: %d, %d, %s"``, ret,` `errno``,` `strerror``(``errno``))``::``free``(filter);``__ASSERT(0)``return` `-11;``}` `// Unmask SIGSYS``sigset_t mask;``if` `(sigemptyset(&mask) \|\| sigaddset(&mask, SIGSYS) \|\|``sigprocmask(SIG_UNBLOCK, &mask, nullptr)``) {``LOGSVCE(``"sigprocmask: %d, %d, %s"``, ret,` `errno``,` `strerror``(``errno``))``::``free``(filter);``__ASSERT(0)``return` `-12;``}` `struct` `sock_fprog prog = {``.len = filterCount,``.filter = filter,``};` `// set to self process``ret = prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0);``if` `(0 != ret) {``LOGSVCE(``"PR_SET_NO_NEW_PRIVS: %d, %d, %s"``, ret,` `errno``,` `strerror``(``errno``))``::``free``(filter);``__ASSERT(0)``return` `-13;``}` `// set seccomp to kernel``ret = prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog);``if` `(0 != ret) {``LOGSVCE(``"PR_SET_SECCOMP: %d, %d, %s"``, ret,` `errno``,` `strerror``(``errno``))``::``free``(filter);``__ASSERT(0)``return` `-14;``}` |
|-|-|

最后，实现拦截后的处理。

| 123456789101112131415161718192021 | `static` `void` `handleSignalAction(``int` `signo, siginfo_t* info,` `void``* context) {``if` `(!info \|\| !context \|\| signo != SIGSYS \|\| info->si_code != SYS_SECCOMP) {``LOGSVCW(``"signal: signo=%d, code=%d, errno=%d, call_addr=%p, arch=0x%x, syscall=0x%x,%s"``,``info->si_signo, info->si_code, info->si_errno, info->si_call_addr, info->si_arch,``info->si_syscall, SvcerDumper::index2name(info->si_syscall)``)``return``;``}` `ucontext_t *uc =` `reinterpret_cast``<ucontext_t *>(context);` `intptr_t` `rc = SvcerSyscall::Call(SECCOMP_SYSCALL(uc),``SECCOMP_PARM1(uc),``SECCOMP_PARM2(uc),``SECCOMP_PARM3(uc),``SECCOMP_PARM4(uc),``SECCOMP_PARM5(uc),``SECCOMP_PARM6(uc)``);``SvcerSyscall::PutValueInUcontext(rc, uc);``}` |
|-|-|

## 03. 封装

为了使用方便，封装了一些基础系统调用的日志打印接口。

1）添加要拦截的系统调用号。（日常日志打印）

| 1234567 | `SvcerDumper::addDump(SVCER_SYSCALL_execve);``SvcerDumper::addDump(SVCER_SYSCALL_execveat);``SvcerDumper::addDump(SVCER_SYSCALL_open);``SvcerDumper::addDump(SVCER_SYSCALL_openat);``SvcerDumper::addAll();` `SvcerHooker::init(ESvcerHookerMode_IgnoreAll,` `"libifmamts.so"``);` |
|-|-|

2）注册要拦截的系统调用回调。

| 12345678910111213141516171819202122232425262728 | `// 这里注册``for` `(``int` `i=SVCER_SYSCALL_None; i<SVCER_SYSCALL_Max; ++i) {``SvcerHooker::registerCallback((TSVCER_SYSCALL_Type)i, handleSvcerHookerCallback);``}` `// 这里实现` `static` `void` `handleKonkerSvcerHookerCallback(``int` `sn, SvcerHookerArgument* arg``/*Not NULL*/``) {``switch` `(sn) {``case` `__NR_statfs:``// int statfs(const char* path, struct statfs* result);``case` `__NR_truncate:``// typedef int truncate(const char *filename, off_t len);``case` `__NR_chdir:``// int chdir(const char *path);``{``const` `char``* pathname = (``const` `char``*)arg->getArgument1();``char` `memString[512];``if` `(memString == KonkerFixer::fixDataPath(pathname, memString)) {``LOGSVCI(``"fixer, %s: %s"``, SvcerDumper::index2name(sn), __PRINTSTR(pathname))``arg->setArgument1((``intptr_t``)memString);``}``arg->doSyscall();``return``;``}``default``:``LOGSVCI(``"ignore, %s"``, SvcerDumper::index2name(sn))``break``;``}``arg->doSyscall();``}` |
|-|-|

3）初始化

| 12 | `// 设置要过滤的库和当前自身库名称``SvcerHooker::init(ESvcerHookerMode_IgnoreVdso\|ESvcerHookerMode_IgnoreLibc\|ESvcerHookerMode_IgnoreLinker,` `"libdemo.so"``);` |
|-|-|

## 04. 附

**额外模块：**

本框架实现了最基本的检测仿真，如通过 `__NR_rt_sigaction` 和 `__NR_prctl` 获取配置时，会对返回值进行还原。

**参考项目：**

<https://github.com/proot-me/proot>

<https://github.com/termux/proot>

---

# 回复

## 回复 by Imxz (#2)

*2025-1-24 12:05*

66666666666

## 回复 by 逆天而行 (#3)

*2025-2-5 19:03*

这个项目如何 导入自己的项目中进行测试  ？ 大佬 有 api使用的说明不？  （未看真切 答案在 开头    把源码 直接复制到自己的项目中就行了 文章 中也说明的很清楚  我看的是大佬之前的 文章  没发现 这个篇是新的 ）

## 回复 by 逆天而行 (#4)

*2025-2-5 20:19*

大佬 为什么 你给的demo 有日志显示  而我导入的源码 进的项目 却提示 内核不支持
![image](https://bbs.kanxue.com/view/img/face/010.gif)

## 回复 by Tiony.bo (#5)

*2025-2-5 20:23*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  这个项目如何&nbsp;导入自己的项目中进行测试&nbsp;&nbsp;？&nbsp;大佬&nbsp;有&nbsp;api使用的说明不？&nbs ...
>
>

你可以直接将svcer模块源码导入到你工程就可以

## 回复 by Tiony.bo (#6)

*2025-2-5 20:24*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  大佬 为什么 你给的demo 有日志显示 而我导入的源码 进的项目 却提示 内核不支持
> [em_010]
>
>

你的内核版本多少？这个是有版本要求的，你可以看初始化函数有内核版本检测，基本上最近几年的系统都应该支持的

## 回复 by 逆天而行 (#7)

*2025-2-6 13:01*

>
> [Tiony.bo](https://bbs.kanxue.com/user-909890.htm)
>
>  你的内核版本多少？这个是有版本要求的，你可以看初始化函数有内核版本检测，基本上最近几年的系统都应该支持的
>
>

我使用的piexl 5  内核版本 是 4.19 观察 大佬的源码 发现最低 需要 5.9    我观察源码，发现原理 与这篇文章 相似 [基于seccomp+sigaction的Android通用svc hook方案 - 软件逆向板块 - 逆想技术论坛 - Powered by Discuz!](https://nixiang.tech/forum.php?mod=viewthread&tid=336) 我尝试编写类似的代码 结合大佬项目  发现大佬对 多架构做了 支持 我拿来直接用   没做什么 线程判断   做的app内 全局 hook   就能够实现 我的需求 对文件进行 io重定向

## 回复 by 逆天而行 (#8)

*2025-2-6 13:06*

还有一点点 的疑惑  大佬 对  __NR_rt_sigaction 和 __NR_prctl   的仿真 我确实 看的不大懂   大佬有相关的文章 吗  ？  我确实 没找到 相关资料

## 回复 by Tiony.bo (#9)

*2025-2-13 09:42*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>
>
>
>
>
>
>  Tiony.bo
>
>
>
>  你的内核版本多少？这个是有版本要求的，你可以看初始化函数有内核版本检测，基本上最近几年的系统都应该支持的
>
>  我使 ...
>
>

这个要做好检测和考虑处理好进程fork的问题

## 回复 by Tiony.bo (#10)

*2025-2-13 09:43*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  还有一点点 的疑惑 大佬 对 __NR_rt_sigaction 和 __NR_prctl 的仿真 我确实 看的不大懂 大佬有相关的文章 吗 ？ 我确实 没找到 相关资料
>
>

这个是为了解决应用的普通检测逻辑不出错，挺简单的实现，实际上各大加固和安全模块检测更为深度，这里只是给出实现思路，所谓商业化还需要花精力实现这部分

## 回复 by 啊你好哇123 (#11)

*2025-2-15 13:52*

小白问下这个东西需要手机root吗

## 回复 by Tiony.bo (#12)

*2025-2-16 10:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  yazigegeda](https://bbs.kanxue.com/user-847178.htm)
>
>  小白问下这个东西需要手机root吗
>
>

不需要，应用级的

## 回复 by dreameriii (#13)

*2025-2-16 15:12*

这个其实会遇到点问题，就是有的App也会注册 SIGSYS的信号监听，不知道 up 有没有遇到过相似的~

## 回复 by mb_rewimxhj (#14)

*2025-2-17 03:17*

>
> [Tiony.bo](https://bbs.kanxue.com/user-909890.htm)
>
>  这个是为了解决应用的普通检测逻辑不出错，挺简单的实现，实际上各大加固和安全模块检测更为深度，这里只是给出实现思路，所谓商业化还需要花精力实现这部分
>
>

安卓低版本和高版本都不太兼容

## 回复 by Tiony.bo (#15)

*2025-2-17 11:34*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  这个其实会遇到点问题，就是有的App也会注册 SIGSYS的信号监听，不知道 up 有没有遇到过相似的~
>
>

所以源码里面做了简单的仿真，不干扰APP的正常使用，大家可以继续按照需要完善

## 回复 by Tiony.bo (#16)

*2025-2-17 11:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rewimxhj](https://bbs.kanxue.com/user-873375.htm)
>
>  安卓低版本和高版本都不太兼容
>
>

低版本是不支持，高版本肯定没问题的

## 回复 by xdcs100 (#17)

*2025-2-18 19:04*

6666666

## 回复 by 逆天而行 (#18)

*2025-2-23 10:54*

佬 我看你这个项目里面的app 使用的proot 的源码  我觉得这样的方式很牛 为啥 svcer不使用这样的方式呢？

## 回复 by Tiony.bo (#19)

*2025-3-7 11:09*

>
> [逆天而行](https://bbs.kanxue.com/user-957038.htm)
>
>  佬 我看你这个项目里面的app 使用的proot 的源码 我觉得这样的方式很牛 为啥 svcer不使用这样的方式呢？
>
>
>

项目中包含两种方案，一种是proot，另一种就是现在的svcer

## 回复 by 逆天而行 (#20)

*2025-3-7 13:47*

>
> [Tiony.bo](https://bbs.kanxue.com/user-909890.htm)
>
>  项目中包含两种方案，一种是proot，另一种就是现在的svcer
>
>

多谢解惑

## 回复 by wx_嗨 (#21)

*2025-3-13 18:47*

佬，我用你的项目测试，如果不填ESvcerHookerMode_IgnoreLibc，拦截openat, app必崩，但是我自己尝试用SECCOMP实现，是能正常拦截的，这是有什么bug么，我测试了好几次都这样，忽略libc就正常

## 回复 by Tiony.bo (#22)

*2025-5-7 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_嗨](https://bbs.kanxue.com/user-953698.htm)
>
>  佬，我用你的项目测试，如果不填ESvcerHookerMode_IgnoreLibc，拦截openat, app必崩，但是我自己尝试用SECCOMP实现，是能正常拦截的，这是有什么bug么，我测试了好 ...
>
>

这是你自己的拦截实现调用的是libc的库函数来完成的吧？导致陷入死循环了，这个主要是自己的实现代码导致的。通常在具体操作时需要注意的

## 回复 by 恋一世的爱 (#23)

*2025-6-28 05:57*

测试无限 Process 17872 exited due to signal 31 (Bad system call)

## 回复 by 恋一世的爱 (#24)

*2025-6-28 06:02*

是的，不过滤libc就会 Process 17872 exited due to signal 31 (Bad system call)，过滤就失去hook意义了

## 回复 by 逆天而行 (#25)

*2025-6-28 19:10*

>
> [Tiony.bo](https://bbs.kanxue.com/user-909890.htm)
>
>  这是你自己的拦截实现调用的是libc的库函数来完成的吧？导致陷入死循环了，这个主要是自己的实现代码导致的。通常在具体操作时需要注意的
>
>

这个 问题 我研究过  与 内核版本 有很大的关系  主要是 bpf 里面拦截了 sigation 和 prctl 这俩个函数    去掉，就能运行了

## 回复 by jilay (#26)

*2025-8-1 15:26*

大佬们，seccomp+sigaction的svc hook方案在mumu等模拟器上有方案吗？尝试使用上面的在代码模拟器上有问题，寄存器数据都是空的，拿不到参数数据![image](https://bbs.kanxue.com/view/img/face/006.gif)
