---
title: '[原创]unidbg中看似随机但固定的arc4random源码分析'
url: https://bbs.kanxue.com/thread-290331.htm
tid: 290331
author: x1a0f3n9
date: '2026-03-15'
tags: [Android安全, 原创, 逆向分析, 系统相关, 其他]
crawled_at: '2026-08-15T11:21:25+00:00'
replies: 10
---

hello大家好，我是x1a0f3n9，大家可以叫我小风，第一次在看雪发帖，发点理论分析贴看看效果。

起因是 因为感觉纯靠 实战逆向案例 学c的使用，理解倒是完全没问题，但是对于为什么要这么开发还是不够清楚，所以我打算把常见的库函数原理都大概弄明白一下，在这个过程中发现某些随机数生成器（arc4random）比较奇怪，然后联想到我之前的一个案例中有个地方没有完全弄明白，所以这篇文章就详细分析一下

这个arc4random 随机函数 在很多案例中都会使用。但是我们在前面的案例中发现unidbg中这个我们不需要固定，但是真机却需要，这是为什么呢？

先说说，为什么有的时候不用rand那种依靠种子的随机数生成器，而是要用arc4random？

因为其是安全等级最高的伪随机数生成器，而且不需要像 `rand` 那样提前输入种子`seed` ；如果需要种子的话，逆向过程中就很好处理了，直接hook固定种子就完事了。而 **`arc4random()`** 是**不需要你喂种子** 的，因为它内部**直接向操作系统内核要高强度随机性字节** ，且其内部自带极其复杂的密码学流密码（早年是 RC4，现在是 **ChaCha20** ）。它能保证：即使在多线程高并发下，吐出的每个字节都绝对猜测不到规律！ 接下来我们追一下源码，这里我们要去拿真机中的代码

\```
adb -d shell "su -c cp /system/lib64/libc.so /data/local/tmp/
adb -d pull /data/local/tmp/libc.so
\```

然后用Binary Ninja打开 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_RQQ52MW2KM839MH.webp)找到这个导出函数，这里三个名字都一样，我们追下去就能找到具体实现 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_FCFDSX8WSWNG69E.webp) ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_G7YYRDMD7C9W2HE.webp)

就是这里了，这里分栏一下，然后把汇编打开，追一下return

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_KSJW33HCZA9AK2Y.webp)

这里追一下rsx，实际上返回值就是从rsx搅拌池里读的；同样我们得先理解他之前的x8_2，而x8__2和全局变量rs有关系，所以我们需要先理解这个函数大概做了啥

1. 拿底层 TLS 寄存器检查安全状态。
2. 如果发现rsx池子里水不够（*rs <= 3），喊小弟 `_rs_stir_if_needed(4)` 或者 `_rs_rekey` 去倒水。

>
> 看交叉引用，这里用rsx的很多
>
>
>
3. 最后从 rsx 池子里舀走 4 个字节，抹除痕迹，返回给你。

接下来追一下`_rs_stir_if_needed`函数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_9GH7V3T6JGVVPR4.webp) ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_97WFSSYWCGJHXAJ.webp)在此之前他会判断rs全局变量是不是空，如果是就init初始化，这里init的时候他把var60传进去用于生成大水池

而var_60 在前面声明之后，然后memset置空，然后经过getentropy 函数赋值

接下来追这个函数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_A2EWK65RACCRJVK.webp)点进去之后追arg1就行，这里主要是经过很多分支，第一个分支是getrandom，之后是读 /dev/urandom 文件获取

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_FY6JX4WUGWJYWU2.webp)这个getrandom函数追进去很容易理解，是通过内核的系统调用获取的，调用号0x116； 像这种函数一般都是不会出故障的，所以基本上就是这个了； 接下来追一下unidbg的这个arc4random； 这里要去找到unidbg用的libc哦，在 `unidbg-android/src/main/resources/android/sdk23/lib64/libc.so`

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_CN2FEZ6C5NCEJ3X.webp)同样地，也是走了 getentropy 函数  ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_HY87A62QGVQHJ2B.webp)结果发现，他是直接打开了 /dev/urandom；然后判断x0_1正不正常，如果正常就继续走

这里是正常的，因为unidbg是对这个文件进行了处理的

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_Z566TZGTUGWZKGY.webp)点过去 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_T7SA6F22YJPGBD8.webp)

发现他生成了 RandomFileIO 对象

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_XA6SHD6822HBNYZ.webp)

这个对象，主要实现了read函数，我们可以在这里 进行日志插桩；然后我的实战案例中 发现他没走这里

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_PC8DNTJ9HQV6GHU.webp)

我这里是给他固定化了， ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_CWEG8JTUGZPEXM2.webp)可以看到他这里没有走进 RandomFileIO.read；

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_URVVY85H5DX6QJF.webp)

也就是说他走到了前面两个分支中，然后直接close了

这里我们要知道 fstat和ioctl是啥。让ai总结一下 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_3XWRWEQKR4NFDH7.webp)这里大家随便看看就行，我们直接日志插桩看他走了哪个

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_UEF8PM96SC45RWC.webp)

这里面没有这两函数，我们找extends的DriverFileIO

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_NBDK7EUB9VBN2UZ.webp)点过去发现这里面有，我们日志插桩，看看走没走

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_XV5K3DXG3FGMA8Z.webp)结果轻松发现他是走了fstat然后废掉的

! ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_P8QMCSKW5NH8TTY.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_5KNSGAEV9DPA9Z8.webp)问了下ai说是这里返回0是正确的

那么就是触发了另一个条件了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_62NEPCQC5MWSFCB.webp)也就是这里的 `(var_70 & 0xf000) != 0x2000)`

这里var_70没有被改，那就是0，0&0xf000=0，然后0！=0x2000所以true，就直接close了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_D7GQQEQNBG2DVKA.webp)然后这里close完了之后直接break推出外层循环了，然后x0就被设置成5了

并且返回值是0xffffffff  ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_QW54B54YBJUGMKC.webp)然后退到外层，直接报错了，然后直接调用9杀掉进程 （也就是向内核发信号 9，**SIGKILL：无条件强制击杀** ）那为啥unidbg还继续走下去了？

这里追一下raise实际做了啥？

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_UN3T298NSA6HVZ9.webp) ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_DU2EDURWPBSU7P2.webp)走到了这里面，然后调用了tgkill的系统调用

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_FMVPEZC3H2NYJDT.webp)这里会被我们的unidbg拦截的，找一下有没有实现这个函数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_MWDERPQR997P2HV.webp)然后日志插桩一下，很快就拦截到了，这里我们追一下return

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_SMRQSMUCY39MAQE.webp)结果发现，他基本上都是返回0，除非你的sig信号不满足条件，当然这种基本上不会出现这种问题

而linux的系统调用返回0基本上都是代表成功，所以这里其实啥也没干就代表成功了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_DP7HK9QD6AK9SKW.webp)结果他就继续走下去了

然后我们hook这个函数会发现他都是固定的

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_N5MW2N3RGFFPWKK.webp)那么为什么固定？

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_H9YUKBHFAZHYXMV.webp)是因为这里主要是走了个chacha20算法，然后输入被固定了；

因为标准的chacha20是void chacha_encrypt_bytes(chacha_ctx *ctx, const uint8_t *m, uint8_t *c)，上下文，明文，密文

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_6R4HJ5XX2DPQY5J.webp)他这里是原地加密的，然后输入的密文在前面被memset了，所以全是0，然后呢

然后直接hook这个chacha就发现了我们关注的密文了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_FYA4Z6THT39MFTG.webp)然后在这里对这个进行hook很容易就发现了 接下来也可以把她的key/iv那些hook出来

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_BUQFX3HW62SXH6D.webp)然后拿去cyberchef看看

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_AHN76DDVWGJ38EX.webp)当然这里其实都不用验证，因为libc里不可能还搞个魔改chacha吧。。。不过这里就当是练习一下了 高版本的libc走的是getrandom函数，走的是系统调用0x116也就是227的getrandom，这个系统调用的代码可以去对应内核版本的linux源码中查看

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_WQMNMXUJTAZVGF9.webp)

很明显流程：收集噪声 -> 注入熵池 -> 触发 ChaCha20 -> 擦除内存痕迹 -> 对外输出；

问了下ai是随机数来源是

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/1036990_PTBUEWFAFPUPNUM.webp)感兴趣的可以去github的linux源码中查看

总结一下：arc4random

- 在低版本安卓是走的/dev/urandom，但是unidbg对于这个文件漏了文件描述的封装，导致被检测出来环境异常了，然后raise(9）线程崩溃，走到tgkill，但是unidbg的系统调用拦截了，然后无事发生，结果就正常标准chacha20加密，然后从偏移0x28每次取出4个值；

- 在高版本走的是getrandom函数，这个走的是系统调用0x116也就是227的getrandom

---

# 回复

## 回复 by wx_。。。。_455 (#2)

*2026-3-16 09:01*

666

## 回复 by iBa0 (#3)

*2026-3-22 01:12*

确认过眼神，是bin玩家！

## 回复 by mb_nuomemmo (#4)

*2026-7-22 16:03*

这篇文章详细分析了arc4random随机数生成器的工作原理，特别是其在Android系统中的实现细节和Unidbg中的表现。通过逆向工程和调试，作者揭示了arc4random的安全性和高效性，同时

## 回复 by mb_nuomemmo (#5)

*2026-8-7 16:01*

这位小风同学的分析真是深入透彻，arc4random的机制被你解得如此清晰，佩服！这种对底层机制的探究精神值得学习，对于我们理解系统安全和随机数生成原理帮助很大。期待你更多类似的分享，继续加油！

## 回复 by mb_bnjbcdzy (#6)

*2026-8-8 16:01*

小风的分析非常深入，对arc4random的实现原理和实际应用进行了细致的逆向研究，特别是对比了真机和unidbg环境下的行为差异，对理解随机数生成器的安全性和实现细节非常有帮助。这种技术深度的分享

## 回复 by mb_hjnyfmfs (#7)

这位博主的技术分析非常深入，尤其是对arc4random的实现细节的解读令人敬佩。作为一名开发者，我深感技术探索的魅力，尤其是在逆向工程中，这种对底层机制的理解和掌控能力令人折服。同时。

## 回复 by mb_vrcwxcxq (#8)

小风的分享非常详细，从arc4random的实现原理到实际逆向分析的过程都讲解得非常透彻，技术分析功底深厚，值得学习！这种深入的技术探讨对开发者理解底层机制大有裨益，点赞支持！

## 回复 by x1a0f3n9 (#9)

你们是机器人么![image](https://bbs.kanxue.com/view/img/face/022.gif)

## 回复 by mb_kvvvwhmo (#10)

这篇技术分析非常深入，对arc4random的实现细节和实际应用的探讨让我受益匪浅。作为一名开发者，能够看到如此详细的逆向分析过程，不仅帮助我更好地理解了随机数生成器的工作原理，也让我意识到在编程和

## 回复 by mb_mwogblyz (#11)

这篇技术分析讲得太详细了！通过深入解析arc4random的实现机制，揭示了随机数生成器在不同系统版本中的差异，技术分析非常深入，对开发者理解底层实现有很大帮助！
