---
title: '[原创]某手app libkwsgmain 去花'
url: https://bbs.kanxue.com/thread-278103.htm
tid: 278103
author: amwait
date: '2023-07-20'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆]
crawled_at: '2026-07-31T14:40:57+08:00'
replies: 4
---

该视频app的核心加密算法sig3 在libkwsgmain 中是实现，为了详细研究该算法，首先需要对so去花处理。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/892597_QYM4J5V72PYATMD.png)
以libkwsgmain中JNI_OnLoad 函数为例，该函数首先调用loc_4cda0 函数，在loc_4cda0 函数又立即调用sub_b8778函数，sub_b8778函数是用来计算函数的真实地址的。此外，从0x4cda4开始，实际上是跳转表，但是被ida误以为是指令。

sub_b8778函数汇编指令如下：
![图片描述](https://bbs.kanxue.com/upload/attach/202307/892597_8WRN8UX25A52VFY.png)
在该函数中实际上是修改了PC寄存器的值，从而计算并跳转到JNI_OnLoad 真实函数地址。
实际上该so中有很多出这样的计算跳转地址，因而可以写去花脚本，实现批量去花，就能够快乐的F5了

 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/892597_ANKB4J5ZR8BCMZU.png)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/892597_2UC7DMZ2VQR3P86.png)
写在最后，该app中除了该so文件，还有libcore.so 也使用了该种插花手段，去除方法相同。
此外，该app请求头中的sig字段加密算法在
 ![图片描述](https://bbs.kanxue.com/upload/attach/202307/892597_E6VW557UJP89F7N.png)
其中getClock方法由native实现，具体的加密算法是参数2的byte数组拼接上盐值，最后进行md5得到返回值。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-7-21 10:16*

感谢分享

## 回复 by shinratensei (#3)

*2023-7-21 10:38*

tql

## 回复 by bookool (#4)

*2024-9-7 08:10*

感谢分享

## 回复 by night star (#5)

*2024-9-20 00:32*

大佬请问应该在哪里patch？是在0x4cd92 LDR R0, xx那里跳转到计算好的目标地址么？还是在它上面或者下面那条指令那里跳转
