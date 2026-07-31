---
title: '[原创]app加固分析狗尾续貂之dex vmp还原'
url: https://bbs.kanxue.com/thread-285212.htm
tid: 285212
author: night star
date: '2025-01-12'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆]
crawled_at: '2026-07-31T14:14:55+08:00'
replies: 15
---

# 前言

oacia大佬的[APP加固dex解密流程分析](https://bbs.kanxue.com/thread-280609.htm)，已经基本把它翻个底朝天了，但众所周知要彻底攻破该加固，仍有dex vmp这最后一道堡垒横在面前。在此之前拜读过爱吃菠菜大佬的[某DEX_VMP安全分析与还原](https://bbs.kanxue.com/thread-270799.htm)以及Thehepta大佬的[vmp入门(一)：android dex vmp还原和安全性论述](https://bbs.kanxue.com/thread-281427.htm)，了解到dex vmp的原理是对dalvik指令进行了加密和置换，这里参照大佬们的方法对oacia大佬的样本复现了一遍，记录一下历程。

# 获取trace

既然是vmp，按照vmp常规的分析流程，必然要先拿到trace，以这次的经历来看，拿到trace就已经成功了一半了。参考了很多大佬的文章，大致有以下几种方法：ida trace、unidbg/AndroidNativeEmu、frida stalker、frida qbdi、Dobby Instrument、unicorn 虚拟CPU。

## ida trace

开始打算用maiyao的[ida trace脚本](https://github.com/maiyao1988/IDAScripts/blob/master/ida_trace.py)，但遇到以下问题：
1.ida附加上后每次执行到linker加载壳so加载到一半就退出了，单步发现是跑到rtld_db_dlactivity里的BRK指令会直接退出，但加载其他so时并没有这个问题（why?)。这里手动把它跳过了。
2.trace了一下JNI_Onload，结果发现每当进入mutex_lock就会卡死在那无限循环……这个没能解决，只好弃用。

## unidbg/AndroidNativeEmu

补java环境有点累，尤其是补到后面发现可能会有很多代理类，没坚持补下去……

## frida stalker

从oacia那篇文章来的肯定少不了尝试一下stalker，结果发现和ida相似的问题——每当进入mutex_lock就会卡死在那无限循环。

## frida qbdi

尝试用yang的[frida-qbdi-tracer](https://github.com/lasting-yang/frida-qbdi-tracer)，但每当trace到一些跳转的时候就会崩溃，查阅资料发现qbdi好像确实存在这样的bug。

## Dobby Instrument（未尝试）

这个我是后面才看到的，感觉将来可以尝试一下，详见KerryS的[指令级工具Dobby源码阅读](https://bbs.kanxue.com/thread-273487.htm)。

## unicorn 虚拟CPU（未尝试）

爱吃菠菜那篇文章的中的方法，没完全搞明白，感觉大意应该是把unicorn作为一个so文件注入到app中，用frida hook住目标函数，当发生调用时把环境补给unicorn来trace。

## 小结

经过不断尝试，最终还是使用frida stalker，通过hook mutex_lock函数，在OnEnter中跳过stalker，再在OnLeave中恢复stalker的方法，在经过无数次崩溃之后，终于拿到了dex vmp的trace……

# 指令流分析

拿到trace指令流后，就可以着手分析了。可以看到，onCreate函数被注册到的地方，使用DebugSymbol.fromAddress没有打印出任何符号，应该是一块动态申请的内存区域：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_QQQHT9PW9JKK59R.webp)
函数并不大，里面也基本全是位置无关代码，应该只是一个跳板，很快，便来到了主elf中的函数sub_137978。

## 跳转表修复（未完成）

sub_137978这个函数就大了，该函数内的指令流数量占了全部的99%，然而在ida F5中却不那么好分析，因为它全程用跳转表实现：
 ![ida F5](https://bbs.kanxue.com/upload/attach/202501/941380_2C2HKKWEU7RMDSB.webp)
 ![汇编](https://bbs.kanxue.com/upload/attach/202501/941380_779YJPD2X296D68.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_V5PQSRZ3XJ24VTW.webp)
 ![跳转表](https://bbs.kanxue.com/upload/attach/202501/941380_PAVVGDNQD63PVXH.webp)
ida倒是具备跳转表修复的功能，在Edit->other->specify switch idiom中，可以参考<https://github.com/ChinaNuke/ChinaNuke.github.io/blob/main/2021/08/Specify-switch-statement-in-IDA-Pro/index.html> （原博文已挂，这里的备份需要下载下来看）
我按照它的讲解修复了一下，不过效果也不是太好，估计是没搞清start of switch idiom和input register。
也尝试过用数据流分析来回溯跳转表，然后转化为bcond addr1、b addr2来修复，不过因为可能会涉及指令重排的问题，而且有的块的前驱没有分析出来会导致数据流中断，懒得再用迭代了……这里直接从trace中找到这些BR X8的后继，然后在ida中用idc.add_cref(ea, next_ea, idc.fl_JF)添加上引用，姑且在汇编分析了。

## 函数调用分析

不过，这么多指令应该从哪入手呢？先跟一下它的函数调用吧。在trace中搜索BL，先是几个比较短的函数，然后进入到一个有意思的函数sub_13B1D8：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_76264BTDA6BANEY.webp)
看到这么大这么整齐的一个结构体，而之前又没有看到什么对a2的初始化，难道？我尝试将a2改为JNIEnv*，竟然整齐地对上了！再退回到result初始化的地方，看到result结构体的大小为0x728，和JNIEnv的大小0x748如此接近，那么很有可能是一个打乱顺序的JNIEnv。既然这么巧，先把这个结构体创建出来：
![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_QY8MK6UP52KRDMJ.webp)
继续向下分析函数调用，在经过一系列短函数后，来到了函数sub_144EF0。
这个函数指令流数量占了90%以上，而其中再没有占比特别高的函数了，大概它就是虚拟机入口了，给它命名为vm_entry_sub_144EF0，接下来主要研究它。

## 虚拟机分析

和sub_137978一样，vm_entry_sub_144EF0同样是全程跳转表，怎么办呢？
根据上文提到的爱吃菠菜以及Thehepta的文章,可知dex vmp中会大量调用JNI函数，所以从它们入手是一个不错的选择。

### 从JNI调用入手

先看这条：
FindClass(androidx/appcompat/app/AppCompatActivity)libjiagu_64.so!0x19e654
我们来到0x19e654这个地址，将参数设为重排的JNIEnv，果然，这里确实是调用FindClass，这也印证了前面对JNI的猜测。查看其调用链为vm_entry_sub_144EF0->sub_160D7C->sub_19E508。
先看一下sub_160D7C：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_2BSQ4X2P5XP5HQ9.webp)
有很多不同类型的CallXXMethod，这些显然是在解释函数调用指令，将该函数命名为call_method_sub_160D7C。
从call_method_sub_160D7C调用处向上回溯，我发现它经历了一系列的cmp w0, xx的比较和跳转，很像是在根据操作码来选择handler的流程。搜索一下
w0的来源，发现是来自sub_15FC34的返回值，其输入一部分是来自同一基本块内的sub_16CE0C，这两个函数都总共被执行了17次，均匀地分布在整个vm_entry_sub_144EF0的指令流中。
继续向上回溯，来到loc_153FC8，查看其引用，发现有多达254处，而联想到dalvik opcode为1字节，256种，因此这里多半就是虚拟机的dispatcher了。
再看一下oacia的未加固样本的OnCreate函数指令：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_QHAK2KSM4F3A7CA.webp)
数一下，也是刚好17条。因此，sub_15FC34和sub_16CE0C应该就是解析字节码的函数了。

### 解密字节码

sub_16CE0C中多次用到异或运算，像是在解密字节码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_CSP39CUTP3ZNSX8.webp)
而sub_15FC34，如前所述其返回值是handler所对应的w0，不过没仔细研究其生成过程，像是从文件读取的：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_YUZSSHYR4CNGKX7.webp)
回到call_method_sub_160D7C继续分析，又发现了两个和sub_16CE0C极其相似的函数，不过分别是从offset=2和4处开始解密，查看其返回值，分别为0x154b(5451)和0x21，根据dalvik的函数调用指令invoke的格式，其offset=2处的对应的是函数index，我们拿010editor来看一下method 5451：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202501/941380_Z6WSDQPW7D2EEMJ.webp)
恰好就是其实际调用的函数！
我们把这几个解密字节码的函数的所有返回值按序排列一下，和原字节码进行对比：
 ![image](https://bbs.kanxue.com/upload/attach/202501/941380_UWGYXBUFH46EGHD.webp)
可以看到，除了作为操作码的首字节及部分操作数外，其余均相同。而这些操作数不同的地方，其实也仅仅是因为dex内容发生改变而导致的index的不同，实际指向仍然是相同的。

### 还原操作码

那么接下来就是还原操作码苦力活了，不过也有迹可循，至少根据jni调用可以把method、field相关的指令还原，在资源中搜索操作数可以看看是不是对资源的引用，也可以像破解凯撒密码那样利用不同指令的统计特征及上下文相关性来推断。也有一些取巧的方法，比如自己构造一个容纳了尽量多类型指令的onCreate函数进行加固作为对照，即使它指令对照表发生改变，也可以根据其对应handler相似性来推断。

# 总结

综上所述，onCreate函数的关键流程包括：重排JNI、解密操作码、选择handler、解密操作数，其中操作码由于进行了置换，还需要通过各种方法进一步还原成dalvik操作码。

# 后记

整个数字加固研究下来，涉及到的大致包括ffi调用、frida反调试、elf动态解密加载、自实现linker解析与重定位、dex动态解密加载、dex vmp。但说实话，我花的时间最多的，虽然是dex vmp部分，但确是在如何获取完整的trace上，之后的分析反而没有花太多时间，可能因为像解密字节码关键函数没有用跳转表混淆掉吧，仍然可以用ida f5分析，而且操作数没有做其他的变换，另外就是有大佬们经典文章的加持。
不过仍有一些问题悬而未决，比如字节码的来源，又是如何被加载到内存中的？interpreter_wrap_int64_t、interpreter_wrap_float等这几个函数是什么原理？ida调试为什么单单壳so在运行到rtld_db_dlactivity里BRK时会退出而其他so不会？以后有机会再回过头来研究吧（逃）

# 参考文献

[APP加固dex解密流程分析](https://bbs.kanxue.com/thread-280609.htm)，oacia
[ida trace脚本](https://github.com/maiyao1988/IDAScripts/blob/master/ida_trace.py)，my1988
[frida-qbdi-tracer](https://github.com/lasting-yang/frida-qbdi-tracer)，Imyang
[某DEX_VMP安全分析与还原](https://bbs.kanxue.com/thread-270799.htm)，爱吃菠菜
[vmp入门(一)：android dex vmp还原和安全性论述](https://bbs.kanxue.com/thread-281427.htm)，Thehepta
[Dalvik解释器源码到VMP分析](https://bbs.kanxue.com/thread-226214.htm)，glider
[从0开发你自己的Trace后端分析工具: (1) 概述](https://bbs.kanxue.com/thread-281555.htm)，FANGG3
[指令级工具Dobby源码阅读](https://bbs.kanxue.com/thread-273487.htm)，KerryS

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-1-12 17:47*

感谢分享

## 回复 by 软件君子 (#3)

*2025-1-12 19:35*

好帖 不知道能扛多久 看来还原vmp还是 容纳了尽量多类型指令的onCreate函数进行加固作为对照 这个方案比较靠谱 另外大佬对过签有研究吗

## 回复 by night star (#4)

*2025-1-12 20:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  软件君子](https://bbs.kanxue.com/user-992177.htm)
>
>  好帖 不知道能扛多久 看来还原vmp还是 容纳了尽量多类型指令的onCreate函数进行加固作为对照 这个方案比较靠谱 另外大佬对过签有研究吗
>
>

用seccomp重定向？我记得珍惜any大佬有个帖子讲这个

## 回复 by 软件君子 (#5)

*2025-1-12 20:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  night star](https://bbs.kanxue.com/user-941380.htm)
>
>  用seccomp重定向？我记得珍惜any大佬有个帖子讲这个
>
>

好的佬 那篇帖子我看过 我去试试能不能过掉

## 回复 by 龙飞雪 (#6)

*2025-1-13 11:18*

学习了。

## 回复 by 万里星河 (#7)

*2025-1-14 00:05*

大佬谦虚了 这哪里是狗尾续貂 明明就是画龙点睛 锦上添花。基于类似破解凯撒密码的统计学特征进行opcode还原的思路很有启发性。对于字节码解密函数的定位 其实还可以用frida监控内存读写的方式得到。另外hook所有的jni函数 监控其字段读写 函数调用 解析参数返回值 在指定vmp函数进入时记录这些信息 指定vmp函数离开时输出这些信息 可以快捷精准地分析指定的vmp函数![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 墨穹呢 (#8)

*2025-1-14 11:37*

感谢分享

## 回复 by 万里星河 (#9)

*2025-1-14 17:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  软件君子](https://bbs.kanxue.com/user-992177.htm)
>
>  好的佬 那篇帖子我看过 我去试试能不能过掉
>
>

活捉一个B站up

## 回复 by night star (#10)

*2025-1-14 20:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  大佬谦虚了 这哪里是狗尾续貂 明明就是画龙点睛 锦上添花。基于类似破解凯撒密码的统计学特征进行opcode还原的思路很有启发性。对于字节码解密函数的定位 其实还可以用frida监控内存读写的方式得到。 ...
>
>

是你呀，指出sofixer符号解析问题的大佬![image](https://bbs.kanxue.com/view/img/face/065.gif) 话说“frida监控内存读写”，应该是先定位到字节码区域，对它进行监控吧？我是先找的解密函数![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by 万里星河 (#11)

*2025-1-15 10:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  night star](https://bbs.kanxue.com/user-941380.htm)
>
>  是你呀，指出sofixer符号解析问题的大佬[em_065] 话说“frida监控内存读写”，应该是先定位到字节码区域，对它进行监控吧？我是先找的解密函数[em_055]
>
>

是的 需要先定位到字节码区域

## 回复 by 海带 (#12)

*2025-3-1 13:36*

赞

## 回复 by 海带 (#13)

*2025-3-11 15:24*

111

## 回复 by 好好好好尼玛 (#14)

*2025-7-30 09:57*

interpreter_wrap_int64_t、interpreter_wrap_float 是 混淆过的，开始是一个解密，然后进入一个简单的 VMP 实现，根据解密的字节码通过ffi调用目标函数。 ![image](https://bbs.kanxue.com/view/img/face/007.gif)

## 回复 by 好好好好尼玛 (#15)

*2025-7-30 09:59*

把整个指令流trace的结果发出来一份 观摩观摩？？

## 回复 by ikunnn (#16)

*2025-11-16 23:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  好好好好尼玛](https://bbs.kanxue.com/user-794617.htm)
>
>  把整个指令流trace的结果发出来一份 观摩观摩？？
>
>

有个好问题怎么得到指令映射表，看jni调用真的可以吗
