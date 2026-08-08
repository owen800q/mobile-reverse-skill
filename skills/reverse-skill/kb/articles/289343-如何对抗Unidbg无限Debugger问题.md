---
title: '[原创]如何对抗Unidbg无限Debugger问题'
url: https://bbs.kanxue.com/thread-289343.htm
tid: 289343
author: KanXue_NG
date: '2025-12-06'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:37:00+00:00'
replies: 27
---

# 如何对抗Unidbg无限Debugger问题

0x1-前言:

本篇文章,笔者想谈谈Unidbg无限debugger这个问题,毕竟这种样本确实存在,却没有看到过有师傅发文章进行讲解,那就由我起个头吧.本篇的样本单纯讲无限debugger这个问题,算法分析先搁置.

本篇来自我的公众号发布后复制粘贴,代码块和图片可能丢失,请转移至我的原文:

> aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvZnp0aTB4MUNaaGp0aUVVak9NaXFfQQ==
>
>

0x2-样本信息:

直达:

\```
aHR0cHM6Ly93d3cuZG93bnphLmNuL3NvZnQvMTA0MzAzODMuaHRtbA==
\```

version:

\```
4.7.1
\```

此篇研究的对象是libsignature.so这个so文件.

0x3-由因而起:

首先搭好unidbg的架子

\```
import com.github.unidbg.AndroidEmulator;
\```

运行看看,发现自动断在了这个地方0x400f9230:

\```
debugger break at: 0x400f9230 @ Runnable|Function64 address=0x400970fc, arguments=[]>>> x0=0x0 x1=0xfffffffffffffb27 x2=0xbffff678 x3=0x8 x4=0xfffffffffffffb27 x5=0x400f9320 x6=0x0 x7=0x0 x8=0x87 x9=0x0 x10=0xbffff690 x11=0x401fd0e6 x12=0x4e x13=0x4f x14=0x0>>> x15=0x401fd0d9 x16=0x4025a5f8 x17=0x400f9230 x18=0x17 x19=0x402614b0 x20=0x1 x21=0x402615c0 x22=0xbffff6f0 x23=0x0 x24=0x0 x25=0x0 x26=0x0 x27=0x0 x28=0x0 fp=0xbffff690>>> q0=0x0(0.0) q1=0x0(0.0) q2=0x0(0.0) q3=0x0(0.0) q4=0x0(0.0) q5=0x40100401401004014010040140100401(4.003911019303815, 4.003911019303815) q6=0x0(0.0) q7=0x1f100000000000001f1(2.456E-321, 2.456E-321) q8=0x0(0.0) q9=0x0(0.0) q10=0x0(0.0) q11=0x0(0.0) q12=0x0(0.0) q13=0x0(0.0) q14=0x0(0.0) q15=0x0(0.0)>>> q16=0x51f100000000000041f1(8.3403E-320, 1.0364E-319) q17=0x0(0.0) q18=0x51f100000000000041f1(8.3403E-320, 1.0364E-319) q19=0x0(0.0) q20=0x0(0.0) q21=0x0(0.0) q22=0x0(0.0) q23=0x0(0.0) q24=0x0(0.0) q25=0x0(0.0) q26=0x0(0.0) q27=0x0(0.0) q28=0x0(0.0) q29=0x0(0.0) q30=0x0(0.0) q31=0x0(0.0)LR=RX@0x400972d8[libsignature.so]0x972d8SP=0xbffff690PC=RX@0x400f9230[libsignature.so]0xf9230nzcv: N=0, Z=0, C=0, V=0, EL0, use SP_EL0_armv8_sha512_probe + 0x0    [libsignature.so 0x0f922c] [c0035fd6] 0x400f922c: "ret"
\```

![图片](https://bbs.kanxue.com/upload/attach/202512/8GUEFZ46JFKRW6H.jpg)

笔者并没有人为的去下断点,这是样本本身所引发的问题.

按下c,继续执行

![图片错误](https://bbs.kanxue.com/src)

无论怎么按,都会断在这个位置.

我们可以用stop命令停止

\```
stop: stop emulation
\```

![图片错误](https://bbs.kanxue.com/src)

这样看似解决了问题,但是如果想额外人为的下断点去看函数入参,寄存器状态,内存状态,就会被样本本身引发的断点干扰.

以上现象,笔者将其定义为无限debugger,无限debugger干扰了我们人为的下断分析,故我们需要做手动patch.

0x4-透过现象看本质:

首先,我们需要知道Unidbg(Unicorn Debugger)本质上是一个基于 Unicorn引擎的模拟执行框架,它并不是一个传统意义上的调试器,但提供了调试功能.

通过断点位置的调试输出信息定位原因:

\```
debugger break at: 0x400f9230 @ Runnable|Function64 address=0x400970fc, arguments=[]>>> x0=0x0 x1=0xfffffffffffffb27 x2=0xbffff678 x3=0x8 x4=0xfffffffffffffb27 x5=0x400f9320 x6=0x0 x7=0x0 x8=0x87 x9=0x0 x10=0xbffff690 x11=0x401fd0e6 x12=0x4e x13=0x4f x14=0x0>>> x15=0x401fd0d9 x16=0x4025a5f8 x17=0x400f9230 x18=0x17 x19=0x402614b0 x20=0x1 x21=0x402615c0 x22=0xbffff6f0 x23=0x0 x24=0x0 x25=0x0 x26=0x0 x27=0x0 x28=0x0 fp=0xbffff690>>> q0=0x0(0.0) q1=0x0(0.0) q2=0x0(0.0) q3=0x0(0.0) q4=0x0(0.0) q5=0x40100401401004014010040140100401(4.003911019303815, 4.003911019303815) q6=0x0(0.0) q7=0x1f100000000000001f1(2.456E-321, 2.456E-321) q8=0x0(0.0) q9=0x0(0.0) q10=0x0(0.0) q11=0x0(0.0) q12=0x0(0.0) q13=0x0(0.0) q14=0x0(0.0) q15=0x0(0.0)>>> q16=0x51f100000000000041f1(8.3403E-320, 1.0364E-319) q17=0x0(0.0) q18=0x51f100000000000041f1(8.3403E-320, 1.0364E-319) q19=0x0(0.0) q20=0x0(0.0) q21=0x0(0.0) q22=0x0(0.0) q23=0x0(0.0) q24=0x0(0.0) q25=0x0(0.0) q26=0x0(0.0) q27=0x0(0.0) q28=0x0(0.0) q29=0x0(0.0) q30=0x0(0.0) q31=0x0(0.0)LR=RX@0x400972d8[libsignature.so]0x972d8SP=0xbffff690PC=RX@0x400f9230[libsignature.so]0xf9230nzcv: N=0, Z=0, C=0, V=0, EL0, use SP_EL0_armv8_sha512_probe + 0x0    [libsignature.so 0x0f922c] [c0035fd6] 0x400f922c: "ret"
\```

pc寄存器是存当前的指令的地址,而lr寄存器是存函数执行完毕后应该返回的地址.

将so文件拖入ida中进行反汇编,跳转到当前指令的地址(0xf9230).

![图片错误](https://bbs.kanxue.com/src)

\```
.text:00000000000F9230                 EXPORT _armv8_sha512_probe.text:00000000000F9230 _armv8_sha512_probe DCQ 0xD65F03C0CEC08000, 0xD503201FD503201F.text:00000000000F9230                                         ; CODE XREF: ._armv8_sha512_probe+C↑j.text:00000000000F9230                                         ; DATA XREF: LOAD:0000000000026FF0↑o ...
\```

这几条汇编意思是,导出了一个名为_armv8_sha512_probe的函数,可以供其他的so文件导入使用,可是具体逻辑为什么是一堆数字呢,看不到具体的反汇编指令,这个与ida的识别有关系,ida错误的把它识别成了数据段,按下键盘的c也没有办法转成代码段,我们就人为手动的来转换一下.

\```
DCQ 0xD65F03C0CEC08000, 0xD503201FD503201F
\```

这里IDA使用DCQ(Define Quadword)定义了两个四字(每个四字8字节).

将这两组数据拆分成4段每段4字节,然后转换一下字节序

\```
CEC08000 ===>00 80 c0 ceD65F03C0 ===>c0 03 5f d6D503201F ===>1f 20 03 d5D503201F ===>1f 20 03 d5
\```

使用以下在线网站进行反汇编

\```
aHR0cHM6Ly9hcm1jb252ZXJ0ZXIuY29tLw==
\```

反汇编结果

\```
sha512su0 v0.2d, v0.2dret nop nop
\```

![图片错误](https://bbs.kanxue.com/src)

重点关注前两条指令,后两条是nop无意义.

sha512su0指令介绍:

\```
指令全称：SHA512 Schedule Update 0（SHA-512消息扩展第0步）功能：执行SHA-512算法中消息扩展的初始步骤操作数：两个128位的向量寄存器（.2d表示每个寄存器包含两个64位双字）
\```

sha512su0是ARMv8.4-A的加密扩展指令,而Unidbg作为一款模拟执行框架,只模拟了部分指令,并不能涵盖所有,当执行到此条指令时,unidbg没有实现该指令的模拟导致产生异常中断,ret指令的返回地址错误的指向了代码开头,这便形成了无限循环,也就是我们所见到的无限debugger.

0x5-解决方案:

解决的思路是,打破这个循环,将pc寄存器的值改成lr寄存器的值,从而实现跳过整个函数.

\```
void PatchDebug(){    emulator.attach().addBreakPoint(0x400f9230L, new BreakPointCallback() {        @Override        public boolean onHit(Emulator<?> emulator, long address) {            System.out.println("Skip Func");            emulator.getBackend().reg_write(Arm64Const.UC_ARM64_REG_PC,                    emulator.getBackend().reg_read(Arm64Const.UC_ARM64_REG_LR));            return true;        }    });}
\```

在样本的干扰断点位置0x400f9230设置一个断点,设置一个断点回调,修改寄存器的的值,返回true是不断在此处,false是断在此处.

要注意放的位置也就是时机.

![图片错误](https://bbs.kanxue.com/src)

经过我的测试,在Jni_OnLoad这个时机太晚了,需要在So文件加载初始化之前.

![图片错误](https://bbs.kanxue.com/src)

完整unidbg代码

\```
import com.github.unidbg.AndroidEmulator;
\```

当然也有第二种方法就是将此指令进行nop掉

\```
sha512su0 v0.2d, v0.2d
\```

具体代码:

\```
void PatchDebug(){    emulator.attach().addBreakPoint(0x400f9230L, new BreakPointCallback() {        @Override        public boolean onHit(Emulator<?> emulator, long address) {            System.out.println("Nop Func");            byte[] nop = {(byte)0x1F, (byte)0x20, (byte)0x03, (byte)0xD5};            emulator.getMemory().pointer(0x400f9230L).write(nop);            return true;        }    });}
\```

第二种方法笔者不是很推荐,仅供思路扩展,nop掉后,如果有别的函数调用到此函数,那么将会引发雪崩式的问题.解决了这个问题引发了第二个问题,处理起来就变得麻烦了很多.

0x6-结语:

此篇所涉及到的无限debugger问题,就比较偏unidbg检测与反检测这个主题了.反检测的思路是patch掉检测点.

---

# 回复

## 回复 by 啊你好哇123 (#2)

*2025-12-6 15:57*

图片错误咋回事

## 回复 by KanXue_NG (#3)

*2025-12-6 19:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  啊你好哇123](https://bbs.kanxue.com/user-847178.htm)
>
>  图片错误咋回事
>
>

公众号发布转过来的 图片和代码块会丢失 看我公众号的原文
aHR0cHM6Ly9tcC53ZWl4aW4ucXEuY29tL3MvZnp0aTB4MUNaaGp0aUVVak9NaXFfQQ==

## 回复 by wx_插曲 (#4)

*2025-12-6 22:06*

66666

## 回复 by xingbing (#5)

*2025-12-9 15:03*

学习！！！

## 回复 by mb_xkzgakjm (#6)

*2025-12-15 14:43*

666

## 回复 by 大魔头 (#7)

*2025-12-15 14:50*

学习

## 回复 by 程IT龙 (#8)

*2025-12-19 18:21*

学习学习

## 回复 by mb_qimctavn (#9)

*2025-12-19 18:39*

6

## 回复 by git_52399CodeExia54 (#10)

*2026-1-27 20:54*

Opsy daisy

## 回复 by guijingwen (#11)

*2026-2-6 10:40*

66

## 回复 by qig (#12)

*2026-2-16 22:18*

学习学习

## 回复 by wx_Huber Barrientos (#13)

*2026-2-16 23:57*

为你点赞！

## 回复 by mb_ghebfkzn (#14)

*2026-2-18 14:08*

。

## 回复 by Zireael (#15)

*2026-2-22 18:11*

学习

## 回复 by mb_ncfbmciq (#16)

*2026-3-6 18:31*

666

## 回复 by xeiyu (#17)

*2026-3-13 10:15*

666

## 回复 by mb_stdlrcgp (#18)

*2026-3-29 01:32*

66666

## 回复 by wx_故事与酒 (#19)

*2026-3-29 08:03*

6666666666666666666666666666

## 回复 by 呆萌的小白 (#20)

*2026-3-29 08:31*

貌似很需要,先收藏吃灰吧

## 回复 by 爬虫不看学历 (#21)

*2026-4-3 16:56*

厉害

## 回复 by XCicada (#22)

*2026-4-3 18:10*

学习

## 回复 by mb_cbgtaveo (#23)

*2026-4-4 18:22*

666666666

## 回复 by fengvmu (#24)

*2026-4-4 19:50*

学习

## 回复 by wx_小白_266 (#25)

*2026-5-8 21:42*

tql

## 回复 by r8e8cd8 (#26)

*2026-5-13 20:54*

有用

## 回复 by mb_agaijsul (#27)

*2026-7-21 16:59*

666

## 回复 by mb_guzdnhio (#28)

999
