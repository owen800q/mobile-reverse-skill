---
title: '[原创]android脱壳:一种使用native进行抽取壳脱壳的方法，native版本的frida-fart'
url: https://bbs.kanxue.com/thread-281005.htm
tid: 281005
author: Thehepta
date: '2024-03-20'
tags: [Android安全, 原创, 脱壳反混淆, 逆向分析, 基础理论]
crawled_at: '2026-07-31T14:29:42+08:00'
replies: 17
---

## 前言

写rxposed的时候，搞了很多模块，其中有一个远程调用脱壳的，但是当时使用的是rmi远程调用，因为一些问题无法使用，可能是对抗问题，也有可能是技术问题，所以我又换了一种远程调用方式。

## 概述

android的dex加固，有整体dex加固，抽取加固，dex vmp,java2c，虽然有这么多，但是其实就脱壳主要是两个方面，第一个是整体dex脱壳，第二个就是在整体dex脱壳的基础上进行dex加密函数还原。抽取加固，dex vmp,java2c这些加固方式都以函数为粒度，进行函数代码的保护。

### 整体加固脱壳

这个比较简单，有一些dex的文件是不进行加固的，直接解压apk就行，有些dex是加固过的，常用的dex不落地的内存加载，对于这种dex的脱壳都有个通用的方案，就是内存dump。dex在运行时总是要加载到内存中的，所以选择合适的时机是可以dump下来完整的dex的。

### 抽取壳脱壳

dexvmp,java2c，dex抽取，这些加固方案，在我看来其实都是函数方法抽取，dex抽取是代码抽取了以后，在运行时还原，dexvmp，java2c这些方案是抽取了以后将抽取的代码转变成了另一种代码，导致了无法自动还原，code_item消失。

### dex抽取还原与防护的问题

##### 如上所属，整体加固的脱壳，在运行时dump下来，而dex抽取，我也说了，在运行时还原，那么可以不可以将dex整体dump和dex抽取还原放到一起那

可以，这种可执行文件加固，本质上就是一种静态加密，动态运行时解密，理论上只要在动态运行解密后dump下来就可以了。

##### 为什么fart和frida-fart都是先脱dex然后在修复code_item的方案

因为直接在内存dump整体dex，然后在获取解密的code_item的修复到dex的方案，对于某些有针对性对抗的安全方案是无效的，对于比较简答的dex抽取确实没有问题

##### 为什么对于某些有针对性对抗的安全方案，内存直接修复dex无效（没有完全分析完成）

因为内存中dump下来的dex在修复code_item的时候，都是将dump下来的code_item，写到dex中code_item被抽取出来的位置，但是内存中dump出来的dex中，可能没有code_item的位置，可能是dex文件进行了重新编译的时候抽出来，也可能是定制了dex重编译，将特定的code_item抽出来，也有可能是修改了偏移位置等等
 ![image](https://bbs.kanxue.com/upload/attach/202403/767217_49UXHRFWJ59754X.webp)

##### fart和frida-fart异同

fart和frida-fart都是基于主动加载脱壳，但是fart是基于函数级别的主动加载，会在dex方法执行前夕进行dump,frida-fart是基于类加载的主动加载，颗粒度没有fart细，但是他们有同属于dex内存加密函数自动还原方式的脱壳，如果frida-fart不行，可能是有一些别的问题，如果fart，那么可能就是真的不行，这种方案就本身不行了。甚至可能不是dex抽取壳。

##### frida-fart 能不能做到和fart一样

理论上可以，hook一些fart中dex函数主动调用需要用到的函数，确实可以，但是目前没有实践

##### 修复问题

fart和frida-fart具体怎么修复的我没有去了解，但是如果内存位置不够的话，先反编译dex，将code_item的字节码反编译然后写入到dex中（可能需要用smail写），然后在回编译，可能就可以了。当然，如果可以做到dex内存重组，也可以。

##### dex抽取壳的强度好像有点低，有没有更高强度的方案

dex抽取相比于dex内存不落地加载，实现的难度高很多，但是在保护方面，强度确实好像并没有很高，有些确实有修复问题，但是实际上内存中都解密了。

##### 更高强度的抽取方案

可以看看这个博客
<https://bbs.kanxue.com/thread-268760.htm#msg_header_h2_6>

<https://bbs.kanxue.com/thread-260052.htm>

网上说fart是主动调用，但是我觉得不太准确，far和frida-fart其实都像是主动加载，博客里说的这些函数需要真正执行一次在dump,更像是主动调用

借鉴一段他的代码

| 123456789101112131415161718192021 | `.method public constructor <init>()V``.registers` `2``goto :goto_c``:goto_1``nop``nop``nop``nop``nop``nop``nop``nop``nop``nop` `return``-``void``:goto_c``const v0,` `0x1669``invoke``-``static {v0}, Ls``/``h``/``e``/``l``/``l``/``H;``-``>i(I)V``goto :goto_1``.end method` |
|-|-|

函数本身就是壳代码，需要先执行一次，对本身进行解密。

还有一些强度更高的，被加密的函数执行以后，会先调用壳代码解密，然后调用执行原函数，然后在加密回去。甚至可以将dex指令揭秘一条，执行一条，循环解密，这些可能会需要一些技巧，但是都是fart或者说自动脱壳所无法做到的。

##### 抽取方案的问题

确实可能存在更高强度的抽取，我在研究的时候也一堆纠结，但是转换思路想写，抽取壳本身的兼容问题，写的强队越高，越复杂，兼容问题越严重，而且还有性能问题，一般越复杂的加密和解密，都意味着性能成倍的损耗。另外方案价值的问题，如果抽壳的方案写的如此复杂，就像我前面说的，解密要好几层，那么为什么不用dex vmp。

##### 学到了点东西

安全对抗中技术确实是一个问题，但是一个安全产品不是技术的高低问题，而是他是否能符合客户要求，在符合用户要求和最大化利益的情况下，提高技术上线。毕竟要吃饭，这也是对抗中防守方的弱势问题。

### native版本的frida-fart

我在上一次写博客推荐我的rxposed的工具的时候，埋了个脱壳的坑，但是有些事没搞完。

讲个笑话：

当时我觉得fart这类工具确实是可以做到内存自动修复的，然后我屁颠屁颠的去找肉丝说我给你修一下，然后肉丝说你去搞搞银行app，然后我去了，我才发现这种code_item偏移位置有问题的dex,理论上确实能做，但是工程里估计很大，只能说，真是尴尬。

#### 上才艺

项目地址：

<https://github.com/Thehepta/androidGRPC>

rxposed项目博客地址：

<https://bbs.kanxue.com/thread-280808-1.htm>

上次博客里我写的使用rmi做的远程调用，然后脱dex,但是rmi在某些银行或者第三方加固公司中不知道为什么用不了，然后我就改成grpc远程调用了，native脱壳的代码完全使用的是frida-fart代码native话，然后我加了一点code_item位置修复，这部分对于我上面说的有防护方案的壳是没啥用。

工程分为两部分，一部分用idea打开，另一部分作为rxposed模块注入到用户进程，lsposed如果要使用，需要只需要加载进去执行入口代码，并且能够执行native函数。只要双方的端口能够通讯连接成功就可以。

grpc 的服务端在android平台上，会一直开启。

grpc 的客户端在pc上，可以随时断开。

部分代码

| 123456789101112 | `String host` `=` `"192.168.31.152"``;``int` `port` `=` `9091``;``ManagedChannel channel` `=` `ManagedChannelBuilder.forAddress(host, port).usePlaintext().build();` `UserServiceGrpc.UserServiceBlockingStub userServiceBlockingStub` `=` `UserServiceGrpc.newBlockingStub(channel);` `Empty empty` `=` `Empty.newBuilder().build();``/``/`        `StringArgument className` `=` `StringArgument.newBuilder().setClassName(``"com.yunmai.valueoflife.MainActivity$a"``).build();``/``/`        `StringArgument className` `=` `StringArgument.newBuilder().setClassName(``"com.ccb.start.MainActivity"``).build();` `userServiceBlockingStub.dumpdex(empty);``/``/`        `userServiceBlockingStub.dumpClass(className);` |
|-|-|

userServiceBlockingStub.dumpdex 会dumpdex到app目录下
userServiceBlockingStub.dumpClass(className) ，这个是远程主动调用类加载函数，来对函数进行解密，然后dump。

#### 测试

用了肉丝测试的几个商业app，都可以脱出来，但是银行类型的app不行，没法自动修复

#### 后续展望

grpc可以进行文件传输，可以直接将dex传输过来dump到pc上，目前还未实现.

如果有机会，可以将dex修复功能和grpc远程调用结合起来使用，可以一次性修复，或者动态dump想要的java函数的code_item。也可以和jadx或者gda

### 总结

- dex抽取壳脱壳，目前大部分使用的可能都是比较简单的抽取壳，我这种native-fart脱壳的方式就能脱下来
- 强度稍微高一点，code_item 修改偏移的抽取壳，这类目前确实市面上有，比如银行，这类fart也是可以脱下来的
- 目前dex抽取主要对抗的问题在于code_item修复问题上，脱壳工具在技术理论上是可以实现一体化修复的
- 更高强队的脱壳，技术上存在，并且有人举了例子，但是本人没有遇到过，不知道到底什么情况

---

# 回复

## 回复 by 陈可牛 (#2)

*2024-3-21 00:39*

dalao方便提供一下样本吗？

我测试这个某银行的某bang只有dexvmp。并没有类抽取~~

![image](https://bbs.kanxue.com/upload/attach/202403/794149_ENX4CMQAJVEUUK7.webp)![image](https://bbs.kanxue.com/upload/attach/202403/794149_EXDUFFN4MAV3XJB.webp)![image](https://bbs.kanxue.com/upload/attach/202403/794149_CPB43KA5MPJNMSY.webp)

## 回复 by huangjw (#3)

*2024-3-21 10:37*

可以哦

## 回复 by Thehepta (#4)

*2024-3-21 11:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  dalao方便提供一下样本吗？我测试这个某银行的某bang只有dexvmp。并没有类抽取~~
>
>

你这一家我搞过了，那个dex内存报错的图，就是他家的。你这个不是方法抽取吗，dexvmp可能需要手工还原的，样本你私我v,或者直接去找找肉丝最新版脱壳的那个app,也行

## 回复 by 陈可牛 (#5)

*2024-3-21 11:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  你这一家我搞过了，那个dex内存报错的图，就是他家的。你这个不是方法抽取吗，dexvmp可能需要手工还原的，样本你私我v,或者直接去找找肉丝最新版脱壳的那个app,也行
>
>

这个不是方法抽取的呢，是vm化，vm化的比较多的。那我私聊一下大佬样本了呢！

## 回复 by Thehepta (#6)

*2024-3-21 11:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  这个不是方法抽取的呢，是vm化，vm化的比较多的。那我私聊一下大佬样本了呢！
>
>

那你是怎么将指令还原的，如果是dex vmp, 所有的指令数据都会与原来不一致，除非你确定指令的位置，然后明白指令的含义，然后搞一个小型的dex 指令转换器

## 回复 by 陈可牛 (#7)

*2024-3-21 12:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  那你是怎么将指令还原的，如果是dex vmp, 所有的指令数据都会与原来不一致，除非你确定指令的位置，然后明白指令的含义，然后搞一个小型的dex 指令转换器
>
>

我也是直接加载，或者暴力点让他加载，然后dump。fart只是虚假调用，我写了白名单进行真实调用。dexvmp的话没啥办法，我目前也是看解释器。例如最近分析的样本：![image](https://bbs.kanxue.com/upload/attach/202403/794149_YDVNT8CB44FPNN8.webp)

## 回复 by tDasm (#8)

*2024-3-21 20:23*

fridα-fart在哪？只看到Rxposed

## 回复 by tDasm (#9)

*2024-3-25 10:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>
>
>
>
>
>
>  Thehepta
>
>
>
>  那你是怎么将指令还原的，如果是dex vmp, 所有的指令数据都会与原来不一致，除非你确定指令的位置，然后明白指令的含义 ...
>
>

FART虚假调用就可以了，只要指令都还原了。你怎么真实调用？不好构造每个方法的入口参数

## 回复 by 陈可牛 (#10)

*2024-3-25 16:59*

反射调用

## 回复 by 陈可牛 (#11)

*2024-3-25 17:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  tDasm](https://bbs.kanxue.com/user-382.htm)
>
>  FART虚假调用就可以了，只要指令都还原了。你怎么真实调用？不好构造每个方法的入口参数
>
>

没有改源码，所以用不了fart。直接反射调用，过滤一些会影响程序退出的类即可。参数对不对无所谓的。目前我测试我的主动调用（真实调用），暂时还没有什么大问题。另外你可以翻一下20到21年这段时间，看雪出了fart课程后，也有一些人用反射去直接调用的。

## 回复 by tDasm (#12)

*2024-3-25 17:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>
>
>
>
>
>
>  tDasm
>
>
>
>  FART虚假调用就可以了，只要指令都还原了。你怎么真实调用？不好构造每个方法的入口参数
>
>  没有改源码，所以用不了far ...
>
>

反射调用是肯定的，但是入口参数不好构造，还是假的，执行会异常。

你把楼主的编译好的程序提供下载？免得每个人再编译一次

## 回复 by 月清晖 (#13)

*2024-3-29 15:26*

不懂就问，数字免费版的native oncreate能脱出来吗？

## 回复 by mb_eiaothcj (#14)

*2024-4-16 14:18*

>
> [月清晖](https://bbs.kanxue.com/user-353710.htm)
>
>  不懂就问，数字免费版的native oncreate能脱出来吗？
>
>

这种一般给钱就能![image](https://bbs.kanxue.com/view/img/face/86.gif)

## 回复 by Thehepta (#15)

*2024-4-16 15:35*

>
> [月清晖](https://bbs.kanxue.com/user-353710.htm)
>
>  不懂就问，数字免费版的native oncreate能脱出来吗？
>
>

老弟你上一次是不是问了，数字的native oncreate,好像是dex vmp，需要手工还原的，等我下一篇dex vmp还原吧

## 回复 by zx_994305 (#16)

*2024-4-16 17:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eiaothcj](https://bbs.kanxue.com/user-977000.htm)
>
>  这种一般给钱就能[em_86]
>
>

只要预算够，没有不能脱的

## 回复 by 养只猫不好么 (#17)

*2024-10-11 15:17*

感谢分享

## 回复 by ikunnn (#18)

*2025-10-12 20:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  老弟你上一次是不是问了，数字的native oncreate,好像是dex vmp，需要手工还原的，等我下一篇dex vmp还原吧
>
>

大佬能不能加你一个联系方式呢，我有一下关于dexvmp的问题，谢谢
