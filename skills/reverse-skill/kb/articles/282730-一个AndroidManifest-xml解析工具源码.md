---
title: '[原创]一个AndroidManifest.xml解析工具源码'
url: https://bbs.kanxue.com/thread-282730.htm
tid: 282730
author: Jobcrazy
date: '2024-08-01'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 程序开发, 源码框架, 工具脚本]
crawled_at: '2026-08-11T08:44:53+00:00'
replies: 14
---

起因是在论坛看到了[AndroidManifest 二进制解析笔记](https://bbs.kanxue.com/thread-280251.htm)这篇文章，原贴是C++写的，而且没有完整的源码。网上找到的其他文章都是拿Java写的，太笨重了。于是我动手用Go写了这么一个工具，可以在附件里下载到。

除了解析成结构体之外，这个工具还能把解析完成的结构体写回到文件里。

如何阅读：直接拉到main函数，就可以看到解析和写入的两个函数的调用。源码很简单，总共就400行，照着下面这个图，读一下代码就可以了。

![image](https://bbs.kanxue.com/upload/attach/202408/79798_6PPAB4N6TG78WE2.webp)

上传的附件：
- main.go

（10.53kb，96次下载）

---

# 回复

## 回复 by koflfy (#2)

*2024-8-1 10:26*

mark，顶A导。

## 回复 by 快乐的小跳蛙 (#3)

*2024-8-1 14:17*

A导 yyds

## 回复 by 曰曰 (#4)

*2024-8-1 14:39*

214行报错 unexpected EOF

上传的附件：
- AndroidManifest.xml

（49.18kb，4次下载）

## 回复 by Jobcrazy (#5)

*2024-8-2 05:44*

>
> [曰曰](https://bbs.kanxue.com/user-417510.htm)
>
>  214行报错&nbsp;unexpected EOF
>
>

可以自行按需修改一下，我代码里没有判断文件是否已经到末尾，只是按图里的结构进行了遍历。文件头里有写文件应该是多大：

type HEADER struct {
        ResType    uint16
        HeaderSize uint16
        Filesize   uint32  <-- 这一行
}

也可以对照010Editor+AndroidManifest.bt的插件解析的结果

## 回复 by 简单的简单 (#6)

*2024-8-5 09:25*

嘿嘿，其实已经贴出大部分代码了

## 回复 by Jobcrazy (#7)

*2024-8-6 11:40*

>
> [简单的简单](https://bbs.kanxue.com/user-950902.htm)
>
>  嘿嘿，其实已经贴出大部分代码了
>
>

嘿嘿，感谢原作者

## 回复 by 养只猫不好么 (#8)

*2024-8-7 13:55*

感谢分享

## 回复 by Jobcrazy (#9)

*2024-8-11 12:04*

>
> [曰曰](https://bbs.kanxue.com/user-417510.htm)
>
>  214行报错&nbsp;unexpected EOF
>
>

我对着010Editor检查了一下，发现Chunk之间不一定是紧密相连的，可能有被0填充的空隙。而我的代码是连续读取的，所以导致了这个错误。可以自行把代码改一下，因为每个Chunk的size在Chunk的头里面都有，读完了之后根据这个size跳转到下一个Chunk再读，就没问题了。

## 回复 by 曰曰 (#10)

*2024-8-11 12:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Jobcrazy](https://bbs.kanxue.com/user-79798.htm)
>
>
>
>
>
>
>
>  曰曰
>
>
>
>  214行报错&amp;nbsp;unexpected EOF
>
>  我对着010Editor检查了一下，发现Chunk之 ...
>
>

好的，感谢

## 回复 by 弄好了 (#11)

*2024-9-4 12:10*

goggoog

## 回复 by bluegatar (#12)

*2024-9-5 22:41*

有代码就是好

## 回复 by tmi (#13)

*2024-9-25 15:41*

亲自运行了一下，发现了一个问题，但是我也没有找到问题原因，怀疑跟编译的版本或者xxx设置相关。

 binary.Read(file, binary.LittleEndian, &data.ResChunk.ResType) 这里的ResType会读取出来两种值，对比发现是因为xml文件有两个字节没对上

解决办法就是read两次（ResType正好两个字节，可以读取多于的两个字节）

![image](https://bbs.kanxue.com/upload/attach/202409/939264_X3YEMZPC53XCDVM.webp)![image](https://bbs.kanxue.com/upload/attach/202409/939264_3EHBVBH5JU3KZWP.webp)

## 回复 by Jobcrazy (#14)

*2024-10-24 08:50*

>
> [tmi](https://bbs.kanxue.com/user-939264.htm)
>
>  亲自运行了一下，发现了一个问题，但是我也没有找到问题原因，怀疑跟编译的版本或者xxx设置相关。&nbsp;binary.Read(file, binary.LittleEndian, & ...
>
>

你可能遇到了我在9楼说的情况？可以按我说的用之前读到的Chunk Size来判断是否到了结尾

## 回复 by C878 (#15)

*2025-7-22 10:16*

因工作需要，有幸读到师兄的文章，CR49
