---
title: '[求助]如何hook cocosjs'
url: https://bbs.kanxue.com/thread-285475.htm
tid: 285475
author: mb_doaynyyh
date: '2025-02-09'
tags: [Android安全, 求助, 逆向分析, HOOK注入]
crawled_at: '2026-08-11T08:40:13+00:00'
replies: 20
---

目前在网上看到的都是说什么xxtea解密，
的确，我要逆向的手游存在jsc文件，但也不是非要进行解密。因为我并没有在libcocos.so中找到关于xxtea的函数，猜测是三方加密
目前的情况是：
找到了send发包函数，是在java层
通过frIDA回溯不了send的调用栈(无论是so还是java均未找到调用或引用，多线程也没有相关逻辑)
也没有找到so调用java层send函数的代码
猜测是使用js调用的java的send函数。
就是看看有没有大神指教一下怎么做，用什么工具能hook到安卓的js层代码，或者具体思路是怎样的，关于加密解密其实都还好，我自己能进行回溯，主要就是js的hook，感觉真是空白领域。不同于浏览器，安卓手游的确不知道该怎么办
附：想做款手游的自动化脚本，不是很想用封包发送实现，想通过功能函数调用实现
菜鸡一枚，勿调侃

---

# 回复

## 回复 by 答案在风中飘 (#2)

*2025-2-10 09:26*

游戏名和下载url私信发我

## 回复 by 陈可牛 (#3)

*2025-2-10 10:15*

同上

## 回复 by mb_doaynyyh (#4)

*2025-2-10 11:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  同上
>
>

已发

## 回复 by mb_doaynyyh (#5)

*2025-2-10 11:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  答案在风中飘](https://bbs.kanxue.com/user-968180.htm)
>
>  游戏名和下载url私信发我
>
>

已发

## 回复 by Aimees (#6)

*2025-2-10 13:39*

同上

## 回复 by mb_doaynyyh (#7)

*2025-2-10 15:24*

>
> [Aimees](https://bbs.kanxue.com/user-978841.htm)
>
>  同上
>
>

已发

## 回复 by 陈可牛 (#8)

*2025-2-10 19:20*

key:

\```
8cACzItxxxxpK3gk
\```

https://www.bilibili.com/video/BV1VKNZeXEiy/

## 回复 by mb_doaynyyh (#9)

*2025-2-10 19:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  key:8cACzItxxxxpK3gkhttps://www.bilibili.com/video/BV1VKNZeXEiy/
>
>

可以麻烦给个思路吗？

## 回复 by 陈可牛 (#10)

*2025-2-10 19:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_doaynyyh](https://bbs.kanxue.com/user-987006.htm)
>
>  可以麻烦给个思路吗？
>
>

就干他呀![image](https://bbs.kanxue.com/view/img/face/055.gif)。与jsc无关，跟cocos creator正常编译的修改一样。

直接hook来看调用栈了。这里就是StartGame的入口了

![image](https://bbs.kanxue.com/upload/attach/202502/794149_KMFZGAKP6UARBH3.webp)

## 回复 by mb_doaynyyh (#11)

*2025-2-10 19:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  就干他呀。与jsc无关，跟cocos creator正常编译的修改一样。直接hook来看调用栈了。这里就是StartGame的入口了
>
>

还是有点懵，能给个联系方式，详细教学一下吗？

## 回复 by mb_doaynyyh (#12)

*2025-2-10 19:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  就干他呀。与jsc无关，跟cocos creator正常编译的修改一样。直接hook来看调用栈了。这里就是StartGame的入口了
>
>

就是如何hook到js的执行流程的，可以传授一下吗？

## 回复 by Aimees (#13)

*2025-2-11 10:19*

64位的so，sub_303C44就是解密的地方，v20就是解密密钥；

![image](https://bbs.kanxue.com/upload/attach/202502/978841_AVFVCR8YGW6MWBW.webp)

紧接着317E58判断解密后的内容是不是1F 8B开头（gzip压缩）

![image](https://bbs.kanxue.com/upload/attach/202502/978841_WC2J9FZ6RBPRE9Z.webp)
搜索key：
![image](https://bbs.kanxue.com/upload/attach/202502/978841_GM2VH36AADV5YXP.webp)

![image](https://bbs.kanxue.com/upload/attach/202502/978841_2DXEBFUY5BG9QR8.webp)

然后写个脚本解密，游戏源代码就出来了

![image](https://bbs.kanxue.com/upload/attach/202502/978841_4QN6Y66E4WJX588.webp)

## 回复 by mb_tcrggrah (#14)

*2025-2-11 15:56*

有没有手机网络安全技术专家，在线求

## 回复 by Lunction (#15)

*2025-2-11 19:35*

什么游戏

## 回复 by mb_doaynyyh (#16)

*2025-2-11 21:07*

可以加我q吗，805266421

## 回复 by mb_doaynyyh (#17)

*2025-2-11 21:31*

>
> [Lunction](https://bbs.kanxue.com/user-681174.htm)
>
>  什么游戏
>
>
>

16楼

## 回复 by 啊你好哇123 (#18)

*2025-2-15 13:06*

>
> [Aimees](https://bbs.kanxue.com/user-978841.htm)
>
>  64位的so，sub_303C44就是解密的地方，v20就是解密密钥；紧接着317E58判断解密后的内容是不是1F 8B开头（gzip压缩）搜索key：然后写个脚本解密，游戏源代码就出来了
>
>

大佬问下可以做到动态hook这个js逻辑吗？就是类似于inline hook 一个汇编代码那种

## 回复 by mb_doaynyyh (#19)

*2025-2-18 12:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  yazigegeda](https://bbs.kanxue.com/user-847178.htm)
>
>  大佬问下可以做到动态hook这个js逻辑吗？就是类似于inline hook 一个汇编代码那种
>
>

我也想问这个问题，java层，so层都能hook到，js层不知道怎么去搞，感觉得研究cocos creator的低层实现，

## 回复 by mb_covdmskb (#20)

*2025-2-19 10:03*

>
> [Aimees](https://bbs.kanxue.com/user-978841.htm)
>
>  64位的so，sub_303C44就是解密的地方，v20就是解密密钥；紧接着317E58判断解密后的内容是不是1F 8B开头（gzip压缩）搜索key：然后写个脚本解密，游戏源代码就出来了
>
>

请问是怎么跳转到key那个函数的呢，上下看了下好像没有关联？

## 回复 by 复读基 (#21)

*2025-2-20 10:13*

根据cocos文档来看 是有原生调试这个东西的你试试使用同版本的ccc编译一个调试版本的so替换原版 看看能不能用开启调试功能![image](https://bbs.kanxue.com/view/img/face/051.gif)，只能祈祷没改过ccc源码了
