---
title: 攻防世界-mobile-easy-app详解
url: https://bbs.kanxue.com/thread-281603.htm
tid: 281603
author: KerryS
date: '2024-05-05'
tags: [Android安全, 工具脚本, 逆向分析]
crawled_at: '2026-07-31T14:27:54+08:00'
replies: 3
---

#### 序言

这道题网上很多分析，但是分析的都是arm版本的，我选了arm64的来分析，arm64相比arm难度高一些，因为arm64编译器搞了inline优化，看起来略抽象

#### 分析

这道题逻辑很简单，输入flag然后一个check函数验证，check函数是c层的，但是arm32和arm64差别很大，给大家瞄一眼，先32后64
 ![image](https://bbs.kanxue.com/upload/attach/202405/844633_YHJ9Y3Q6V69GZNF.webp)
可以看到，32位的逻辑非常清晰，拿到char*之后，弄成std::string,之后sub_9670函数对比是否是flag{开头，往后CheckM函数把flag{xxx}中的xxx的左16和右16组合在一起，形成一个32字节的字符串，之后check1进行一些简单的逻辑运算，再往后的encry是一个tea，之后是一个魔改的base64,就完事，逻辑很简单，但是到了arm64，就很难看了
 ![image](https://bbs.kanxue.com/upload/attach/202405/844633_92QWKAW4DZNE5CW.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202405/844633_346MWHV9UU8YZWB.webp)
说说主要的区别吧，首先是内联了很多函数，可以看到sub_9670已经没了，encry函数也没了，代码的复杂度提高了很多，还有就是，函数的返回值不按套路出牌，不放在x0寄存器中，不知道放在哪里，得去动态看才知道，比如check1之后的返回值，arm32中一看就知道是指针接受了返回值，但在arm64中莫名其妙放在了一个其他地方。

##### string内存结构问题问题

接下来说说，是怎么分析解决arm64的，首先，经过看这个so的代码以及一些搜索，发现string的内存结构为，string的大小为3个dq（8个字节），24字节，如果字符串小于0x17，那么首字节存放字符串长度乘以2，第二个字节开始放字符串内容；如果是长字符串，那么第一个dq放的是容量，并且这个容量会是奇数，也就是&&1会=1；编译器也是通过这个标志位判断是长字符串还是短字符串，第二个dq放的是字符串的真实长度，第三个dq放的是一个char*，指向真实的字符串；另外一个关于string的问题是，string的很多内部细节也被inline出来了，比如动态扩容，这部分的特征是，会出现一个grow_by_函数，这个函数执行扩容的细节，细节不说了，紧跟这个grow_by_函数后，会看到设置字符串长度的代码，根据这两个特征就能知道实在动态扩容了；

##### 参数乱放问题

函数返回值不是放在x0，会放在莫名奇妙的地方，栈上的某个地方，这一块我采用的解决办法是用frida的stalker trace来分析，非常爽，文末会附上trace脚本

##### 题目其他的一些细节

tea的秘钥是so中的init_array的一个函数设置的，base64的表是在jni_onload中设置的
其余并没有什么特别之处了，这里着重想推荐两个好用的技巧

#### 两个技巧

##### stalker trace

根据yang神首创，经过奋飞小改，之后我在改一点，已经能用了，脚本主要功能是从给定的地址开始trace，trace从这个地址开始后的size长度的代码，会把执行完每一条汇编之后的影响打印出来，寄存器变化，内存的变化，以及内存中的字符串或者u64打印出来，文末也会附上trace check函数后的效果，大体是这样
 ![image](https://bbs.kanxue.com/upload/attach/202405/844633_YHU4RDTD78T4R7R.webp)

##### z3

z3是一个强大的约束求解器，一些琐碎的逻辑用z3比较好求出来，不然的话得人工取反推实现，这里用来解决check1中的逻辑，我们只需要按照正向逻辑按照z3的api写出约束条件，在调用求解器求解，即可得出输入
 ![image](https://bbs.kanxue.com/upload/attach/202405/844633_AGPYY3JCR9MJZQS.webp)

上传的附件：
- easy-app.zip

（2.37MB，44次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2024-5-6 10:42*

感谢分享

## 回复 by mb_dejwmbmm (#3)

*2024-5-7 00:03*

感谢分享

## 回复 by mb_zgwftbre (#4)

*2024-5-7 18:26*

感谢分享
