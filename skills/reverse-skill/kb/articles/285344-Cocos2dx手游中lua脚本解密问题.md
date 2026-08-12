---
title: '[求助]Cocos2dx手游中lua脚本解密问题'
url: https://bbs.kanxue.com/thread-285344.htm
tid: 285344
author: mb_pwffqryw
date: '2025-01-23'
tags: [Android安全, 求助, 基础理论, 逆向分析]
crawled_at: '2026-08-12T04:01:21+00:00'
replies: 10
---

最近遇到个Cocos2d-x加lua开发的手游，我用frIDA hook了luaL_loadbuffer和更底层的lua_loadx，都没得到明文，图1是cocos2d::LuaStack::luaLoadBuffer，前面是if分支，我动态调试确定是走的最后分支，图3是其中一个加密脚本，虽然导出函数中有个xxtea_decrypt，但hook之后发现根本没有调用过，所以我就蒙了，不知道解密过程到底在哪，只能请教大神给点思路。谢谢 ![image](https://bbs.kanxue.com/upload/attach/202501/1006985_CX9DZ8YXHGRTX63.webp) ![image](https://bbs.kanxue.com/upload/attach/202501/1006985_H3QMW3JHEACTAW3.webp) ![3](https://bbs.kanxue.com/upload/attach/202501/1006985_337TGS5AUHCFJBJ.webp)

---

# 回复

## 回复 by 陈可牛 (#2)

*2025-1-26 17:49*

方便留一下样本？

## 回复 by 微启宇 (#3)

*2025-1-26 20:35*

没有进行xxtea加密，所以不会调用xxtea解密。不要被网上的文章和教程误导，xxtea加密教程文章多了开发的也会避免使用xxtea加密。你这lua脚本是在luac前面加了个文件头而已（大致分析的结果）你可以尝试把LJ这一行前面的都删掉然后尝试解密看看。

## 回复 by wx_kx34217 (#4)

*2025-1-29 07:45*

你提供的第一段，不就是解密的么，一眼就能看出来

## 回复 by mb_pwffqryw (#5)

*2025-1-30 13:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  方便留一下样本？
>
>

我不知道怎么发给你，邮箱?

## 回复 by mb_pwffqryw (#6)

*2025-1-30 14:19*

>
> [微启宇](https://bbs.kanxue.com/user-436472.htm)
>
>  没有进行xxtea加密，所以不会调用xxtea解密。不要被网上的文章和教程误导，xxtea加密教程文章多了开发的也会避免使用xxtea加密。你这lua脚本是在luac前面加了个文件头而已（大致分析的结 ...
>
>

是的，文件前4行是厂商硬加的文件头，因为我在luaL_loadbuffer中得到的密文是从LJ这一行开始的，但如果要把他当luac来反编译，应该也不行吧，不符合luac的文件格式，最起码表面看起来不像单纯的luac

## 回复 by 微启宇 (#7)

*2025-1-30 18:15*

>
> [mb_pwffqryw](https://bbs.kanxue.com/user-1006985.htm)
>
>  是的，文件前4行是厂商硬加的文件头，因为我在luaL_loadbuffer中得到的密文是从LJ这一行开始的，但如果要把他当luac来反编译，应该也不行吧，不符合luac的文件格式，最起码表面看起来不像 ...
>
>

你既然已经能从luaL_loadbuffer获取文件内容那就把它们dump下来

## 回复 by 微启宇 (#8)

*2025-1-30 18:15*

>
> [微启宇](https://bbs.kanxue.com/user-436472.htm)
>
>  你既然已经能从luaL_loadbuffer获取文件内容那就把它们dump下来
>
>

然后再反编译一下。

## 回复 by mb_pwffqryw (#9)

*2025-1-31 18:15*

>
> [微启宇](https://bbs.kanxue.com/user-436472.htm)
>
>  你既然已经能从luaL_loadbuffer获取文件内容那就把它们dump下来
>
>

我倒是试过，dump得到的就是从LJ这一行开始之后的内容，不过也有极个别的字节被改变了，而且反编译不通过

## 回复 by tianxiao41 (#10)

*2025-4-27 17:30*

lua——loadbuffer dump出lua明文后 ，如何再动态加载进内存中,以实现功能呢。

## 回复 by 果冻大砍刀 (#11)

*2025-4-28 13:44*

luajit也不会经过xxtea
