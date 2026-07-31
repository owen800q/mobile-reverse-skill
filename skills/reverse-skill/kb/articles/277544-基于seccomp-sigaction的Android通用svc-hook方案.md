---
title: '[原创]基于seccomp+sigaction的Android通用svc hook方案'
url: https://bbs.kanxue.com/thread-277544.htm
tid: 277544
author: 一只流浪狗
date: '2023-06-09'
tags: [Android安全, 原创, 逆向分析, HOOK注入, 系统相关]
crawled_at: '2026-07-31T14:45:18+08:00'
replies: 39
---

# 前叙

众所周知，目前各大APP的安全模块几乎都会使用自实现的libc函数，如open，read等函数，通过自实现svc方式来实现系统调用。因此我们如果想要hook系统调用，只能通过扫描厂商自实现的代码段，定位svc指令所在地址，再通过inline hook方式来进行hook操作，但是这种方式需要涉及内存修改，很容易被检测到内存篡改行为。

本文将利用seccomp方式来监听系统调用，以达到劫持svc调用的目的。

# 什么是seccomp

Seccomp是一个Linux内核安全模块，它可以使进程限制可以进行的系统调用数量，从而提高进程的安全性和可靠性。Seccomp提供了一种轻量级的进程隔离方式，可以在限制进程的能力的同时，不会影响操作系统的整体功能，是现代容器和虚拟化技术中广泛使用的安全保障机制之一。

Seccomp的主要工作流程是通过在进程中使用`prctl()`系统调用来指定一个过滤规则集，该规则集称为“过滤器”，它定义了该进程允许使用的系统调用类型和参数。当进程调用系统调用时，过滤器会拦截该调用并进行验证，以判断其是否符合规则集中指定的条件。如果系统调用不符合规则，Seccomp将拒绝该操作，并终止进程。

Seccomp的过滤器有两种类型：全局过滤器和线程过滤器。全局过滤器是在`prctl()`系统调用时设置的，它会对整个进程使用的所有线程都生效。而线程过滤器是在线程创建时设置的，只会对该线程生效。通常情况下，Seccomp的使用者只需要使用全局过滤器即可，因为它可以在进程创建时就应用到所有的线程中。

过滤器的具体设置可以使用在C语言中定义的BPF程序宏来完成，也可以使用SECCOMP_MODE_FILTER模式下的`seccomp()`库函数来设置。BPF程序宏和seccomp()函数都需要将过滤器规则集以二进制方式指定，并将其传递给`prctl()`系统调用来启用过滤器。下面是一个简单的示例，演示如何使用BPF程序宏来在全局范围内应用过滤器：

```
#include <stddef.h>
#include <linux/seccomp.h>
#include <sys/prctl.h>

#define FILTER_SYSCALLS \
    BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)), \
    BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_getpid, 0, 1), \
    BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW), \
    BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_TRACE)

int main(int argc, char *argv[]) {
    struct sock_fprog filter = {
        .len = sizeof(FILTER_SYSCALLS) / sizeof(FILTER_SYSCALLS[0]),
        .filter = FILTER_SYSCALLS,
    };
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &filter) < 0) {
        perror("prctl");
        return 1;
    }

    return 0;
}
```

此例中，过滤器仅允许进程调用`getpid()`系统调用。如果进程尝试调用其他系统调用，Seccomp将拒绝该操作并终止进程。这里使用BPF程序宏来定义过滤器，当然也可以使用`seccomp()`库函数来编写等效的过滤器规则，例如通过添加`seccomp_rule_add()`库函数，来定义更复杂的规则集匹配条件等。

# 通用svc hook

当前网上能搜到的基于seccomp实现svc hook的文章大致有两类：

1. [利用fork + ptrace方式](https://bbs.kanxue.com/thread-275511.htm)，来捕获seccomp的`SECCOMP_RET_TRACE`信号，从而达到劫持svc调用的目的。这种方案在可执行文件下，是可行的，能够跑的通。但是在app环境下，ptrace将不再适用，容易触发各种异常信号，并且在ptrace环境下容易被各大厂商app的安全模块检测出来。
2. [利用frida + seccomp方式](https://github.com/Abbbbbi/Frida-Seccomp)，通过`Process.setExceptionHandler`来捕获`SECCOMP_RET_TRAP`信号，并且为了避免hook时死循环递归（hook函数中调用svc又再次被seccomp过滤发出`SECCOMP_RET_TRAP`信号），该项目通过创建新线程的方式来规避，但这种方式在处理多线程或者多进程任务时处理起来很麻烦。

本文的通用hook svc方法与第二种类似，主要是捕获`SECCOMP_RET_TRAP`信号，来实现的hook操作。

## syscall信号拦截

seccomp的filter中发出`SECCOMP_RET_TRAP`信号来触发中断，代码如下。

```
struct sock_filter filter[] = {
    BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)),//读取系统调用号
    BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_openat, 0, 1), //判断是否等于__NR_openat
    BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_TRAP), //若是，则触发SECCOMP_RET_TRAP信号
    BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW), //若否，则通过。
};

struct sock_fprog prog;
prog.filter = filter2;
prog.len = (unsigned short) (sizeof(filter) / sizeof(filter[0]));

if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1) {
    perror("prctl(PR_SET_NO_NEW_PRIVS)");
    return 1;
}
if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) == -1) {
    perror("when setting seccomp filter");
    return 1;
}
```

seccomp_data是一个结构体类型，它在使用Seccomp系统调用过滤机制时作为参数传递给BPF程序来指定系统调用。它的定义包含在linux/seccomp.h头文件中，通常定义如下：

```
struct seccomp_data {
  int nr;
  __u32 arch;
  __u64 instruction_pointer;
  __u64 args[6];
};
```

其中，各字段表示的含义如下：

- nr：系统调用号。当前正在调用的系统调用的编号，一般为0到MAX_SYSCALL之间的值之一。
- arch：处理器架构。指向当前处理器架构类型的指针。
- instruction_pointer：指令指针，指向正在执行的指令的地址。
- args：系统调用参数。系统调用的参数，0到5条参数的值分别储存在这个字段中。

使用Seccomp过滤器功能时，可以使用seccomp_data结构体的这些成员来访问和操作该进程的系统调用，对系统调用进行过滤或修改，来完成对特定系统调用的限制。

## 信号处理

seccomp发出`SECCOMP_RET_TRAP`信号时，会引发程序阻塞机制，此时系统会产生一个`SIGSYS`信号，并使原程序处于临时阻塞状态。因此我们可以使用`sigaction`来注册一个对`SIGSYS`信号进行处理的`handler`，再将处理完的结果返回出去，从而达到hook效果。代码如下：

```
struct sigaction sa;
sigset_t sigset;
sigfillset(&sigset);

sa.sa_sigaction = sig_handler;
sa.sa_mask = sigset;
sa.sa_flags = SA_SIGINFO;

if (sigaction(SIGSYS, &sa, NULL) == -1) {
    LOGE("sigaction init failed.\n");
    return 1;
}
```

```
void sig_handler(int signo, siginfo_t *info, void *data) {
    int my_signo = info->si_signo;
    printf("sig_handler2, signo: %x\n", my_signo);
    unsigned long sysno = ((ucontext_t *) data)->uc_mcontext.arm_r7;
    unsigned long arg0 = ((ucontext_t *) data)->uc_mcontext.arm_r0;
    unsigned long arg1 = ((ucontext_t *) data)->uc_mcontext.arm_r1;
    unsigned long arg2 = ((ucontext_t *) data)->uc_mcontext.arm_r2;
    unsigned long arg3 = ((ucontext_t *) data)->uc_mcontext.arm_r3;
    unsigned long arg4 = ((ucontext_t *) data)->uc_mcontext.arm_r4;
}
```

## 避免死循环

上面例子中我们想要对openat的svc进行hook操作，那么我们就需要再`sig_handler`函数里面对修改过的参数再调用一次openat函数，再将返回值给到主进程，让进程继续执行。

但是这样就会有个问题，就是我们的`sig_handler`里面再调用openat函数会再次经过seccomp的filter，并且会再次触发一次`SECCOMP_RET_TRAP`信号，从而又一次进入`sig_handler`。。。造成死循环问题。

因此我们需要优化`filter`内容，让其能够知道哪些svc调用是从`sig_handler`调用过来，哪些svc调用是主进程自身调用。有多种不同的思路，包括：

1. seccomp_data中的instruction_pointer表示svc调用后的返回地址，我们可以在`sig_handler`中使用我们自实现的svc，`filter`中判断返回地址是否是在我们自实现的svc函数即可。
2. 比较简单的就是我们`sig_handler`进行svc调用时，多传递一个`MAGIC`参数进去，`filter`中判断多余的参数是否等于`MAGIC`，若是则启用`SECCOMP_RET_ALLOW`信号，否则触发`SECCOMP_RET_TRAP`。filter如下：

```
    #define SECMAGIC 0xdeadbeef
    struct sock_filter filter2[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_close, 0, 2),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[2])),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SECMAGIC, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_TRAP)
    };
```

`sig_handle`中处理逻辑如下：

```
#define SECMAGIC 0xdeadbeef

void sig_handler(int signo, siginfo_t *info, void *data) {
    int my_signo = info->si_signo;
    LOGD("sig_handler2, signo: %x\n", my_signo);
    printRegs(data);
    unsigned long sysno = ((ucontext_t *) data)->uc_mcontext.arm_r7;
    unsigned long arg0 = ((ucontext_t *) data)->uc_mcontext.arm_r0;
    unsigned long arg1 = ((ucontext_t *) data)->uc_mcontext.arm_r1;
    unsigned long arg2 = ((ucontext_t *) data)->uc_mcontext.arm_r2;
    unsigned long arg3 = ((ucontext_t *) data)->uc_mcontext.arm_r3;
    unsigned long arg4 = ((ucontext_t *) data)->uc_mcontext.arm_r4;
    switch (sysno) {
        case __NR_close:
            LOGD("[close]fd: %ld\n", arg0);
            int close_fd;
            close_fd = syscall(__NR_close, arg0, 0, SECMAGIC);
            LOGD("[close]close ret: %d\n", close_fd);
            ((ucontext_t *) data)->uc_mcontext.arm_r0 = close_fd;
            break;
        default:
            break;
    }
}
```

有问题欢迎大家私聊或者下方评论。

---

# 回复

## 回复 by 樊辉 (#2)

*2023-6-10 16:15*

有很多不错的svc hook开源项目

## 回复 by 恋一世的爱 (#3)

*2023-6-10 21:29*

能否开源提供完整代码给小白学习下

## 回复 by 秋狝 (#4)

*2023-6-10 22:05*

感谢分享

## 回复 by 你瞒我瞒 (#5)

*2023-6-12 10:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  能否开源提供完整代码给小白学习下
>
>

我也是想问有没有一个完整的demo来跟着复习下![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by 一只流浪狗 (#6)

*2023-6-12 11:47*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  我也是想问有没有一个完整的demo来跟着复习下[em_85]
>
>

等过两天我再整理好发上来。

## 回复 by 妙行 (#7)

*2023-6-12 13:47*

要什么完整demo,论坛里看完相关文章真的写不出来吗.想要源码白嫖还是学习目的

## 回复 by jilay (#8)

*2023-6-13 10:40*

你好，代码用在安卓上switch case命中就卡主了。。是什么情况啊

## 回复 by 一只流浪狗 (#9)

*2023-6-13 10:44*

>
> [jilay](https://bbs.kanxue.com/user-968715.htm)
>
>  你好，代码用在安卓上switch case命中就卡主了。。是什么情况啊
>
>

“BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[1]))”改成“BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[2]))”，试试。

## 回复 by jilay (#10)

*2023-6-13 12:23*

>
> [一只流浪狗](https://bbs.kanxue.com/user-787403.htm)
>
>  “BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[1]))”改成“BPF_STMT(BPF_LD | BPF ...
>
>

可以了。。![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by SharkFall (#11)

*2023-6-25 15:05*

在miui上跑过嘛，大佬。我在demo上跑正常hook，注入以后就出问题了

## 回复 by 恋一世的爱 (#12)

*2023-7-1 01:54*

测试__NR_kill  __NR_openat都正常，__NR_exit会卡死

## 回复 by 恋一世的爱 (#13)

*2023-7-2 13:49*

测试__NR_kill  __NR_openat都正常，__NR_exit会卡死

## 回复 by mb_kgsesxqm (#14)

*2023-7-14 23:59*

大佬，按照你的教程来，写好demo，拦截的是  __NR_openat  注入游戏（游戏没检测）会崩溃，报错：Process 8911 exited due to signal 31 (Bad system call)，可以帮忙看下吗，游戏链接可以在apkpure或者APKCombo搜索Animal Revolt Battle Simulator（版本3.1.1_arm64）https://apkcombo.com/zh/animal-revolt-battle-simulator/com.vdimensionltd.animalrevoltbattlesimulator/download/apk

## 回复 by mb_kgsesxqm (#15)

*2023-7-15 00:01*

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>
>  在miui上跑过嘛，大佬。我在demo上跑正常hook，注入以后就出问题了
>
>

兄弟，你是拦截哪个NR，出现的问题是什么呢

## 回复 by 万里星河 (#16)

*2023-9-5 21:15*

>
> [一只流浪狗](https://bbs.kanxue.com/user-787403.htm)
>
>  等过两天我再整理好发上来。

大佬 64位的信号处理怎么写呀

## 回复 by SharkFall (#17)

*2024-2-8 11:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kgsesxqm](https://bbs.kanxue.com/user-969771.htm)
>
>  兄弟，你是拦截哪个NR，出现的问题是什么呢
>
>

忘了，哈哈哈，不过解决了，现在是32位跑不进hook

## 回复 by 肉蚌葱鸡 (#18)

*2024-2-9 09:56*

请问有尝试hook __NR_clone 的吗 会出现无限重启的情况

## 回复 by mb_gipfprwu (#19)

*2024-2-12 09:14*

尝试hook openat注入后有些为什么跑不进hook

## 回复 by mb_gipfprwu (#20)

*2024-3-1 08:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_gipfprwu](https://bbs.kanxue.com/user-922418.htm)
>
>  尝试hook openat注入后有些为什么跑不进hook
>
>

其他线程的似乎没被应用到

## 回复 by 半只青蛙 (#21)

*2024-4-26 15:57*

请教大神__NR_openat 的实现该怎么写呢，我写的始终不对。

## 回复 by 牧草木 (#22)

*2024-5-30 15:21*

>
> [SharkFall](https://bbs.kanxue.com/user-954363.htm)
>
>  忘了，哈哈哈，不过解决了，现在是32位跑不进hook
>
>

怎么解决的呢  我也出现这个问题了

## 回复 by LKNB888 (#23)

*2024-6-9 15:57*

#define _GNU_SOURCE
#include <jni.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <malloc.h>
#include <unistd.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sys/prctl.h>
#include <signal.h>
#include <string.h>
#include <xhook/xhook.h>
#include <xhook/xh_log.h>
#include <sys/syscall.h>
#include <errno.h>

#define SyscallCode 123456

const char *apkPath__;
const char *repPath__;

static void signal_handler(int signum, siginfo_t *siginfo, void *context);

void registerSignalHandler() {
    // Register signal handler
    struct sigaction sig;
    sigset_t sigset;
    sigfillset(&sigset);
    sig.sa_mask = sigset;
    sig.sa_flags = SA_SIGINFO;
    sig.sa_sigaction = signal_handler;
    if (sigaction(SIGSYS, &sig, NULL) == -1) {
        perror("sigaction");
        //exit(EXIT_FAILURE);
    }

    XH_LOG_ERROR("Finished registering signal handler");
}

void installFilterForE() {
    struct sock_filter filter[] = {
            BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)),
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_openat, 0, 3),
            BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, args[5])),
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, SyscallCode, 1, 0),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_TRAP),
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW),
    };

    struct sock_fprog prog = {
            .len = (unsigned short) (sizeof(filter) / sizeof(filter[0])),
            .filter = filter,
    };

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1) {
        perror("prctl(PR_SET_NO_NEW_PRIVS)");
        //exit(EXIT_FAILURE);
    }

    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) == -1) {
        perror("prctl(PR_SET_SECCOMP)");
        //exit(EXIT_FAILURE);
    }

    XH_LOG_ERROR("Set new filter end");
}

#if defined(__aarch64__)
static void signal_handler(int signum, siginfo_t *siginfo, void *context) {
    ucontext_t *uc = static_cast<ucontext_t *>(context);
    struct sigcontext *sigc = &uc->uc_mcontext;

    int code = sigc->regs[8];

    if (code == __NR_openat) {
        char *fileName = reinterpret_cast<char *>(sigc->regs[1]);

        if (strcmp(fileName, apkPath__) == 0) {
            sigc->regs[0] = AT_FDCWD;  // dirfdNum = AT_FDCWD;
            sigc->regs[1] = reinterpret_cast<long>(repPath__);  // fileName = repPath__
            sigc->regs[2] = O_RDONLY;  // openFlags = O_RDONLY;
            sigc->regs[3] = S_IRUSR;  // permission: read/write/execute

            XH_LOG_ERROR("Redirect apk: %s", repPath__);
        }

         sigc->regs[0] = syscall(code, sigc->regs[0], sigc->regs[1], sigc->regs[2],
                                      sigc->regs[3], sigc->regs[4], SyscallCode);

    }
}
#else
static void signal_handler(int signum, siginfo_t *siginfo, void *context) {
    ucontext_t *uc = static_cast<ucontext_t *>(context);
    struct sigcontext *sigc = &uc->uc_mcontext;

    int code = sigc->arm_r7;

    if (code == __NR_openat) {
        char *fileName = reinterpret_cast<char *>(sigc->arm_r1);

        if (strcmp(fileName, apkPath__) == 0) {
            sigc->arm_r0 = AT_FDCWD;  // dirfdNum = AT_FDCWD;
            sigc->arm_r1 = reinterpret_cast<long>(repPath__);  // fileName = repPath__
            sigc->arm_r2 = O_RDWR | O_CREAT;  // openFlags = O_RDONLY;
            sigc->arm_r3 = S_IRUSR | S_IWUSR | S_IXUSR;  // permission: read/write/execute
        }

        sigc->arm_r0 = syscall(code, sigc->arm_r0, sigc->arm_r1, sigc->arm_r2,
                                      sigc->arm_r3, sigc->arm_r4, SyscallCode);
    }
}
#endif

void startSvcHook() {
    registerSignalHandler();
    installFilterForE();
}

extern "C"
JNIEXPORT void JNICALL
Java_bin_mt_signature_KillerApplication_hookApkPath(JNIEnv *env, __attribute__((unused)) jclass clazz, jstring apkPath, jstring repPath) {
    apkPath__ = env->GetStringUTFChars(apkPath, nullptr);
    repPath__ = env->GetStringUTFChars(repPath, nullptr);
    startSvcHook();
}

有人能帮我修改这个代码吗，因为当我使用这个代码登录游戏时它会崩溃

## 回复 by huangbof (#24)

*2024-6-17 19:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  LKNB888](https://bbs.kanxue.com/user-1000449.htm)
>
>  #define _GNU_SOURCE
> #include
> #include
> #include
> #include
> #include
> #include
> #include
> #i ...
>
>

这段代码好像根本用不起

## 回复 by 樊辉 (#25)

*2024-6-18 21:12*

想要学习seccomp bpf最好去看看proot的源码。非常不错

## 回复 by czins (#26)

*2024-7-7 17:50*

sigsys 不是不可靠信号吗，会不会引起 BAD SYSTEM CALL？

## 回复 by pop_m (#27)

*2025-1-17 19:23*

请教大佬一个问题，我用seccomp对openat进行了hook效果正常，但是同时也连发了好几个问题：
1. 如果被hook进程有使用fork + exec，则会出现sigaction的handler将会找不到（exec会清除当前进程空间，加载另一个可执行程序，但seccomp规则依然保留且无法关闭），最终导致进程异常退出
2. 使用提前创建不受seccomp影响的白名单线程代处理的情况下，那么新进程将沿白名单调用clone处继续往下执行，而不会回到真正想调用clone的线程处开始执行。
请教大佬有没有更好的办法才能让我的seccomp进程支持fork+exec

## 回复 by sinker_ (#28)

*2025-2-14 00:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  pop_m](https://bbs.kanxue.com/user-917202.htm)
>
>  请教大佬一个问题，我用seccomp对openat进行了hook效果正常，但是同时也连发了好几个问题：1.&nbsp;如果被hook进程有使用fork&nbsp;+&nbsp; ...
>
>

我也遇到了这个问题，一直没找到解决方案，请教下大佬现在有合适的方案没

## 回复 by pop_m (#29)

*2025-2-18 19:26*

>
> [sinker_](https://bbs.kanxue.com/user-972452.htm)
>
>  我也遇到了这个问题，一直没找到解决方案，请教下大佬现在有合适的方案没
>
>

算是解决了吧，各种绕弯子，把fork exec的问题解决了，但是发现seccomp+sigaction这个方案整体上好像不是特别稳定，时不时会出现Zygote  : Process 15927 exited due to signal 31 (Bad system call)然后crash掉，目前还在看，等解决了这个不稳定问题我在发一篇文章说一下整体的方案

## 回复 by pop_m (#30)

*2025-2-18 19:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kgsesxqm](https://bbs.kanxue.com/user-969771.htm)
>
>  大佬，按照你的教程来，写好demo，拦截的是 __NR_openat 注入游戏（游戏没检测）会崩溃，报错：Process 8911 exited due to signal 31 (Bad sys ...
>
>

我也遇到了，请问有解决方案吗？感觉问题也不好找

## 回复 by sinker_ (#31)

*2025-2-19 16:05*

好的，期待大佬的方案和文章![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by Golbeze (#32)

*2025-3-20 15:45*

>
> [pop_m](https://bbs.kanxue.com/user-917202.htm)
>
>  算是解决了吧，各种绕弯子，把fork exec的问题解决了，但是发现seccomp+sigaction这个方案整体上好像不是特别稳定，时不时会出现Zygote : Process 15927 exi ...
>
>

大佬现在解决了吗

## 回复 by Golbeze (#33)

*2025-3-20 15:46*

>
> [pop_m](https://bbs.kanxue.com/user-917202.htm)
>
>  请教大佬一个问题，我用seccomp对openat进行了hook效果正常，但是同时也连发了好几个问题：1.&nbsp;如果被hook进程有使用fork&nbsp;+&nbsp; ...
>
>

其实只要clone不指定CLONE_SIGHAND就可能出现这种状况，但是去hook clone也在崩

## 回复 by pop_m (#34)

*2025-5-26 17:35*

>
> [sinker_](https://bbs.kanxue.com/user-972452.htm)
>
>  好的，期待大佬的方案和文章
>
>

文章没写完![image](https://bbs.kanxue.com/view/img/face/055.gif)，说下大概原理吧，主要是修复了上面说的第二点：
hook fork，让其实现为向当前线程发送一个信号（我实现的是sigsys，通过设置x2为特殊值来区分普通kill调用和被hook了的fork），在sigaction里面判断如果为fork调用过来的，就将其上下文保存至全局变量，并发自定义消息送至白名单线程，自己阻塞等待（这里使用了条件变量和互斥锁），白名单线程收到消息后调用原始的fork，调用结束之后将返回值设置全局变量并通知调用线程拿结果，阻塞线程收到消息之后取消阻塞、拿结果、返回白名单线程调用fork的返回值（子进程pid），此时父进程的实现结束。
子进程（由于是白名单线程创建的，所以不会有sccomp约束，但会有刚才存储好的全局上下文）需要通过信号（sigaction）机制恢复上下文：开启一个自定义信号（我用的是siguser），其handler实现有两步：1. 将自定义信号恢复为默认值（也就是该信号只用一次）；2. 将上下文信息（ucontext_t）覆盖为存储好的全局上下文信息，那么该信号函数处理完成之后子进程的执行流会跳到最初调用fork的位置，子进程的实现结束。
稳定性没有专门测，小米手机上完美跑通。流程较为负责，应该是存在稳定性问题，希望大家一起优化。最终文档和demo等我闲了再出![image](https://bbs.kanxue.com/view/img/face/074.gif)

## 回复 by pop_m (#35)

*2025-5-26 17:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Golbeze](https://bbs.kanxue.com/user-843963.htm)
>
>  大佬现在解决了吗
>
>

不完美解决，详情可以看上条评论

## 回复 by pop_m (#36)

*2025-5-26 17:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Golbeze](https://bbs.kanxue.com/user-843963.htm)
>
>  其实只要clone不指定CLONE_SIGHAND就可能出现这种状况，但是去hook clone也在崩
>
>

hook clone崩悄无声息，果断放弃

## 回复 by mb_kgsesxqm (#37)

*2025-6-9 14:08*

>
> [pop_m](https://bbs.kanxue.com/user-917202.htm)
>
>
>
>
>
>
>
>  sinker_
>
>
>
>  好的，期待大佬的方案和文章
>
>  文章没写完，说下大概原理吧，主要是修复了上面说的第二点：hook&nbsp; ...
>
>

大佬，我也遇到fork31问题了，能出个教程修复吗

## 回复 by jilay (#38)

*2025-8-1 15:34*

大佬们，seccomp+sigaction的svc hook方案在mumu等模拟器上有方案吗？尝试使用上面的代码在模拟器上有问题，寄存器数据都是空的，拿不到参数数据![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_rcvipuuv (#39)

*2025-9-9 20:39*

>
> [pop_m](https://bbs.kanxue.com/user-917202.htm)
>
>
>
>
>
>
>
>  sinker_
>
>
>
>  好的，期待大佬的方案和文章
>
>  文章没写完，说下大概原理吧，主要是修复了上面说的第二点：hook&nbsp; ...
>
>

大佬   我按照上面代码集成apk运行后 要么就不停重启 bad systemcall  要么就卡在那  信号处理程序也进不去  代码哪里有问题吗![image](https://bbs.kanxue.com/view/img/face/055.gif)
 struct sock_filter filter[] = {
            BPF_STMT(BPF_LD + BPF_W + BPF_ABS, offsetof(struct seccomp_data, nr)),//读取系统调用号
            BPF_JUMP(BPF_JMP + BPF_JEQ + BPF_K, __NR_openat, 0, 1), //判断是否等于__NR_openat
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_TRAP), //若是，则触发SECCOMP_RET_TRAP信号
            BPF_STMT(BPF_RET + BPF_K, SECCOMP_RET_ALLOW), //若否，则通过。
    };
    struct sock_fprog prog;
    prog.filter = filter;
    prog.len = (unsigned short) (sizeof(filter) / sizeof(filter[0]));

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1) {
        perror("prctl(PR_SET_NO_NEW_PRIVS)");
        return 1;
    }
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) == -1) {
        perror("when setting seccomp filter");
        return 1;

    }

    struct sigaction sa;
    sigset_t sigset;
    sigfillset(&sigset);

    sa.sa_sigaction = sig_handler;
    sa.sa_mask = sigset;
    sa.sa_flags = SA_SIGINFO;

    if (sigaction(SIGSYS, &sa, NULL) == -1) {
        LOGE("sigaction init failed.\n");
        return 1;
    }

## 回复 by 恋一世的爱 (#40)

*2026-2-25 03:05*

bad system call有没有完美解决方案
