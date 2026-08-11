---
title: '[求助]大佬们有办法hook il2cpp全部的函数吗，并打印原返回值'
url: https://bbs.kanxue.com/thread-279216.htm
tid: 279216
author: mb_othrajzu
date: '2023-10-13'
tags: [Android安全, 求助, HOOK注入]
crawled_at: '2026-08-11T08:46:44+00:00'
replies: 18
---

目前只会一个个hook而不会批量hook全部的函数，求大佬们指点

---

# 回复

## 回复 by mb_vgyntjdw (#2)

*2023-10-14 14:31*

可以不过大概率会闪崩

## 回复 by mb_othrajzu (#3)

*2023-10-14 19:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_vgyntjdw](https://bbs.kanxue.com/user-979641.htm)
>
>  可以不过大概率会闪崩
>
>

那除了frida的话，dobby这一类hook框架可以实现吗，求大佬指条路

## 回复 by 无名侠 (#4)

*2023-10-14 20:39*

可以看看这个插件
https://github.com/P4nda0s/IDAFrida
一键生成IDA 里面选定函数的 hook 脚本

## 回复 by mb_othrajzu (#5)

*2023-10-14 22:18*

>
> [无名侠](https://bbs.kanxue.com/user-617255.htm)
>
>  可以看看这个插件
> https://github.com/P4nda0s/IDAFrida
> 一键生成IDA 里面选定函数的 hook 脚本
>
>

好的谢谢

## 回复 by 简单的简单 (#6)

*2023-10-14 22:26*

dump.cs 里的地址根据函数名过滤一下，然后大力出奇迹

## 回复 by mb_othrajzu (#7)

*2023-10-15 09:32*

>
> [简单的简单](https://bbs.kanxue.com/user-950902.htm)
>
>  dump.cs 里的地址根据函数名过滤一下，然后大力出奇迹
>
>

我就是因为游戏没法得到dump.cs了，然后通过hook全部的函数再看返回值确定我要hook的那个函数地址，以此来越过厚厚的加密喔

## 回复 by oacia (#8)

*2023-10-15 10:43*

前两个月用过 https://github.com/IIIImmmyyy/frida-il2cppDumper 可以打印出il2cpp所有调用的函数 但是现在看作者似乎把项目隐藏了 可惜呐![image](https://bbs.kanxue.com/view/img/face/82.gif)

## 回复 by mb_othrajzu (#9)

*2023-10-16 16:56*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  前两个月用过 https://github.com/IIIImmmyyy/frida-il2cppDumper 可以打印出il2cpp所有调用的函数 但是现在看作者似乎把项目隐藏了 可惜呐[em_82 ...
>
>

这个对隐藏api的没有作用貌似，这个项目我保存了一份的

## 回复 by wx_嗨 (#10)

*2023-10-16 17:38*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  前两个月用过 https://github.com/IIIImmmyyy/frida-il2cppDumper 可以打印出il2cpp所有调用的函数 但是现在看作者似乎把项目隐藏了 可惜呐[em_82 ...
>
>

好像就是直接hook全部函数的，github上看提交历史可以看到![image](https://bbs.kanxue.com/view/img/face/27.gif)

## 回复 by mb_othrajzu (#11)

*2023-10-16 20:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_嗨](https://bbs.kanxue.com/user-953698.htm)
>
>  好像就是直接hook全部函数的，github上看提交历史可以看到[em_27]
>
>

这个是出dump.cs的吧

## 回复 by 唱过阡陌 (#12)

*2023-10-17 10:18*

https://github.com/axhlzy/Il2CppHookScripts

## 回复 by 你瞒我瞒 (#13)

*2023-10-18 09:13*

>
> [唱过阡陌](https://bbs.kanxue.com/user-868525.htm)
>
>  https://github.com/axhlzy/Il2CppHookScripts
>
>

感谢

## 回复 by 珍惜Any (#14)

*2023-10-24 16:20*

lsp商店搜索 ，funil2cpp，根据你需要的函数关键字添加就行了 ，我之前写过 。用的插装 。

## 回复 by mb_othrajzu (#15)

*2023-10-25 09:34*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  lsp商店搜索 ，funil2cpp，根据你需要的函数关键字添加就行了 ，我之前写过 。用的插装 。
>
>

好的，谢谢大佬

## 回复 by wx_范迪塞尔 (#16)

*2023-10-30 11:56*

我测了一下，用的ALL，lsp选系统和游戏，进游戏操作，只有一个函数注入，其他的都没反应啊，大佬

## 回复 by EX呵呵 (#17)

*2023-10-30 12:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_othrajzu](https://bbs.kanxue.com/user-950805.htm)
>
>  这个对隐藏api的没有作用貌似，这个项目我保存了一份的
>
>

隐藏api？ 某hoyo家的游戏 il2cpp_get_api_table？

## 回复 by mb_munjswmb (#18)

*2023-10-30 15:49*

如果只是为了获取函数名称，倒是可以在内存中搜索xxxx.dll文本名称，然后扫一次指针看看有哪些值指向这些名称，然后再扫一遍，根据对应il2cppClass结构体的那个位置就能够获取到类名，再通过类名就能获取方法名了，方法那个我记得是MethodInfo结构体

## 回复 by mb_othrajzu (#19)

*2023-10-30 23:10*

>
> [EX呵呵](https://bbs.kanxue.com/user-828999.htm)
>
>  隐藏api？ 某hoyo家的游戏 il2cpp_get_api_table？
>
>

对，不过通过特征码解决了需求
