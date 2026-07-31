---
title: 针对魔改unity引擎的il2cpp dump方案il2cpp_class_dumper
url: https://bbs.kanxue.com/thread-282653.htm
tid: 282653
author: 安卓逆向test
date: '2024-07-27'
tags: [Android安全, 逆向分析, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:22:19+08:00'
replies: 13
---

# 前言

unity游戏的攻防自其诞生之初就已经开始了，现如今已经到了白热化的阶段，[il2cpp_class_dumper](https://github.com/AndroidReverser-Test/il2cpp_class_dumper)就是为此而生，但在介绍它之前，让我们先以攻击者的视角来回顾这场攻防对抗。

# 静态dump，基于Il2CppDumper

## 传统的静态dump

在很久以前的时候，游戏厂商还没开始重视游戏安全，这时候存储unity app程序集关键符号信息的global-metadata.dat甚至没有任何经过加密就直接放入包体中，这时攻击者只需将包体中的global-metadata.dat和libil2cpp.so提取出来，再使用[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)这个项目即可得到unity app程序集的关键符号信息。

但随着游戏厂商开始注重对global-metadata.dat的静态加密，这种方法越来越不适用。

## 动静结合的静态dump

既然直接从包体中提取global-metadata.dat不行，但若是直接在游戏运行时从内存中搜索global-metadata.dat再将其dump下来不就行了吗，以上方法在global-metadata.dat整体加密整体解密的情况下其实是适用的，在这种情况下dump下内存中已经解密的global-metadata.dat再使用[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)即可顺利完成符号dump。

但是如果内存中始终没有完整的global-metadata.dat呢，它可能是分块解密再分块加载呢，这种情况实际上是非常常见的，这样的话，单纯的内存dump已经不能够解决问题了，在这种情况下可以直接分析libil2cpp.so中加载global-metadata.dat的逻辑来对原包体中的加密过的global-metadata.dat进行解密还原，但这种方法过于复杂而且因为不同游戏的加密方法不一致很难做到通用，所以攻击者往往都会选择第二种方法动态dump。

# 传统的动态dump，基于Zygisk-Il2CppDumper

正如前面所说，静态dump已经变得十分复杂且不通用了，动态dump便应运而生，即便到了现在这种无视静态加密的动态dump方法也还能dump绝大多数Unity游戏，就这么一种通用且使用方便的dump方法，它的原理其实十分简单，概括起来就是利用libil2cpp.so中的il2cpp框架的关键系统api的导出函数的主动调用来获取unity app的程序集的符号信息。默认情况下很多il2cpp的系统api是直接暴露在libil2cpp.so的导出表当中的，这也是使用[Zygisk-Il2CppDumper](https://github.com/Perfare/Zygisk-Il2CppDumper)的前提条件。

但是如果游戏刻意隐藏了il2cpp框架的关键系统api的导出呢，只需隐藏一两个dump工具需要用到的il2cpp api就能阻碍动态dump工具的运行，实际上现在很多游戏都是这样做的。

这种情况下可以选择给dump工具打补丁，如果只隐藏了一两个il2cpp api那攻击者可以自己找到相应的il2cpp api的地址再修改dump工具的相应位置的源码不就顺利解决这个问题了吗。但如果隐藏的不是一个两个而是所有的il2cpp框架的关键系统api的导出呢，这种情况下再自己手动的一个一个找，不说耗费的时间要多少，能不能做到都是个问题。

## 自动化地寻找il2cpp api

对于没有魔改unity引擎的游戏来说，自动化地寻找il2cpp api是可行的，可以使用[frida-find-il2cpp-api](https://github.com/AndroidReverser-Test/frida-find-il2cpp-api)这个项目中的find_il2cpp_api.js来自动导出il2cpp api来供动态dump工具使用。
但是这种方法仅限于在没有魔改unity引擎的情况下使用。

# 以退为进，针对魔改unity引擎的dump

正如前面所说，在魔改unity引擎这种情况下，想要得到全部的il2cpp框架的关键系统api已是困难重重了，但我们不妨想想我们真的需要这么多il2cpp api吗，如果我们将需要的il2cpp api削减至个位数，在这种情况下就算一个一个api手动查找需要的时间也不会很多，虽然这样得到的符号信息也会比传统的动态dump少很多，但必要的取舍还是需要做出。

## 妥协的动态dump方法il2cpp_class_dumper

与其说[il2cpp_class_dumper](https://github.com/AndroidReverser-Test/il2cpp_class_dumper)是动态dump，它更像是一种动静结合的dump方法。
该方法的核心思想是在il2cpp框架的SetupMethodsLocked放置hook，这样可以拦截到加载的所有klass并将其保存，待游戏加载完成所需要的klass后再通过主动调用极少部分的il2cpp api来动态dump klass的符号信息并保存至本地。
正是因为需要的il2cpp api非常少，目前该方法只能dump游戏程序集中的方法信息。

# 总结

通过上述回顾，可以明显看出现在关于unity游戏程序集符号信息的获取是愈发艰难了，[il2cpp_class_dumper](https://github.com/AndroidReverser-Test/il2cpp_class_dumper)算是我个人想到的一个权宜之计。路漫漫其修远兮，吾将上下而求索。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-7-27 11:49*

test大佬支持一下

## 回复 by Lnju (#3)

*2024-7-29 12:01*

思路不错 支持一下

## 回复 by gtict (#4)

*2024-7-29 15:45*

目前该方法只能dump游戏程序集中的方法信息:是系统方法还是游戏写的那些方法

## 回复 by 安卓逆向test (#5)

*2024-7-29 18:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gtict](https://bbs.kanxue.com/user-346783.htm)
>
>  目前该方法只能dump游戏程序集中的方法信息:是系统方法还是游戏写的那些方法
>
>

所有已经初始化过的类的方法信息都能dump,跟系统方法和自定义方法无关

## 回复 by fu11p7r (#6)

*2024-7-30 00:07*

遇到打乱了结构的就不太行了，像某二游那样每个版本都把il2cpp结构打乱一遍，有什么好的办法呢

## 回复 by 安卓逆向test (#7)

*2024-7-30 09:29*

>
> [TubituX](https://bbs.kanxue.com/user-958990.htm)
>
>  遇到打乱了结构的就不太行了，像某二游那样每个版本都把il2cpp结构打乱一遍，有什么好的办法呢
>
>

其实运行时dump几乎不需要结构体信息，像我这个和Zygisk-Il2CppDumper一样都是只需要methodinfo的方法指针偏移没有改动就行了，这个地方其实连米X游的魔改引擎都没有改动，其他符号信息的dump都是通过il2cpp api的主动调用来获得的，就无视结构体改变了

## 回复 by fu11p7r (#8)

*2024-7-30 10:36*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  其实运行时dump几乎不需要结构体信息，像我这个和Zygisk-Il2CppDumper一样都是只需要methodinfo的方法指针偏移没有改动就行了，这个地方其实连米X游的魔改引擎都没有改动，其他符 ...
>
>

MethodInfo我记得也是有打乱的，不过这个修起来也容易

## 回复 by 养只猫不好么 (#9)

*2024-7-30 16:51*

感谢分享

## 回复 by wx_aa_775 (#10)

*2024-8-6 18:15*

分析zzz的时候发现只能dump每个类的ctor方法，楼主有解决方法吗？

## 回复 by 安卓逆向test (#11)

*2024-8-8 23:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_aa_775](https://bbs.kanxue.com/user-917033.htm)
>
>  分析zzz的时候发现只能dump每个类的ctor方法，楼主有解决方法吗？
>
>

这个其实应该是il2cpp_class_get_methods这个api的位置没对，因为zzz的那个so其实是有特殊的处理，ida识别有问题

## 回复 by Himeko (#12)

*2024-8-17 16:18*

早起用的框架就是大概几个接口, 然而抓的函数少太多了, 没调用就抓不到, 分析不太方便

## 回复 by zouzhiqiang (#13)

*2024-8-19 15:14*

顶一下

## 回复 by 软件君子 (#14)

*2025-4-9 17:47*

好分析的很好 点赞
