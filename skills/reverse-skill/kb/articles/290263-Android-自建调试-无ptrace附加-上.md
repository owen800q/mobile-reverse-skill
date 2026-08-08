---
title: '[原创]Android 自建调试  无ptrace附加 (上)'
url: https://bbs.kanxue.com/thread-290263.htm
tid: 290263
author: 只会逆一点点
date: '2026-03-11'
tags: [Android安全, 原创, 程序开发, 系统相关]
crawled_at: '2026-08-08T10:20:04+00:00'
replies: 12
---

# 演示

## 引言

作为一个刚接触安卓的小白，我发现虽然安卓平台的工具琳琅满目——Frida、Unidbg、Xposed、Zygote注入，还有GG和AGG修改器等，但实际操作起来总觉得不够顺手。手机屏幕太小，各种操作都显得局促，最终还是得连接到电脑上。更让我困扰的是，安卓上缺少像Windows平台那么好用的调试器，目前大多只能靠Hook来进行调试分析。

基于这些痛点，萌生了一个想法：能不能打造一个专门为安卓设计的调试器，对标Windows上的x64dbg和Cheat Engine，而且不依赖ptrace机制？经过初步研究，我发现可以借鉴Windows自建调试器的思路。但安卓有一个独特优势：没有PG(保护机制)的限制，Hook非常自由，甚至系统本身就提供了完善的Hook支持。更重要的是，我们可以自行编译源码，定制一个完全符合需求的系统。

1.无附加调试器，不依赖ptrace

2.异常过滤，无视干扰

3.内核重构，自建调试体系，理论上能调试任何程序

4.无痕断点无视crc校验

5.扫描ip端口自动连接，读写，遍历进程，遍历模块，解析符号，反汇编，查看内存，设置断点，单步，步过，寄存器显示，堆栈回溯(已经实现)

6.后续将继续完善，dump so自动拉取到电脑，内存扫描(特征码，字符串等)，实现无限断点，实现系统调用监控moniter syscall，实现无痕hook 读执行分离。

## 扫描ip端口自动连接

![image](https://bbs.kanxue.com/upload/attach/202603/67QZGAEYN527SFP.jpg)

## 遍历进程

![image](https://bbs.kanxue.com/upload/attach/202603/YUCWHPK4BZ76VPE.jpg)

## 遍历模块

![image](https://bbs.kanxue.com/upload/attach/202603/GAYVXXNXFYWQJPX.jpg)

## 解析符号

![image](https://bbs.kanxue.com/upload/attach/202603/ZKAMV8XVMRNG3E9.jpg)

## 设置断点，单步，步过

![image](https://bbs.kanxue.com/upload/attach/202603/DRERF2S7CTWGXQQ.jpg)

## 反汇编，查看内存

![image](https://bbs.kanxue.com/upload/attach/202603/DPG53S2A6P3AV4Q.jpg)

## 寄存器显示，堆栈回溯

![image](https://bbs.kanxue.com/upload/attach/202603/VJBJK9YZVMUG28V.jpg)

# 原理讲解

## 选材

虽然安卓可以编译源码定制系统，但是太过复杂，且兼容性较差，我们可以选择通过加载内核模块来获取同等内核权限，与windows一样。

在安卓系统开发中，KO文件是一个经常会遇到的概念。简单来说，.ko文件是Linux内核模块（Kernel Module）的文件格式，全称为"Kernel Object"内核模块是Linux内核支持的一种动态加载机制，它允许在内核运行时动态地添加或移除功能，而不需要重新编译整个内核或重启系统

KPM:APatch框架下的内核补丁模块，文件后缀为`.kpm`，但它本质上就是KO模块 在标准KO模块的基础上，赋予了更强大的动态修补能力，隐藏性更好，并且不用再拉取每个版本内核源码，一次编译4.9-6.x通用(只是能加载上，版本间的差异还是需要自己弥补)

## 隐蔽通信

不使用常见ioctl

密钥作为节点名

Hook `proc_root_readdir` 隐藏目录

通过 `proc_read` 实现双向通信

或者hook任意系统调用

# 内核态数据结构

内核没stl自己实现数据结构吧

```plain
cvector cvector_create(const size_t size)
{
	cvector cv = (cvector)x_kmalloc(sizeof (struct _cvector), GFP_KERNEL);

	if (!cv) return NULL;

	cv->cv_pdata = vmalloc(MIN_LEN * size);

	if (!cv->cv_pdata)
	{
		kfree(cv);
		return NULL;
	}

	cv->cv_size = size;
	cv->cv_tot_len = MIN_LEN;
	cv->cv_len = 0;

	return cv;
}
\```

#

#

上传的附件：
- 压缩画质_演示.mp4

（7.37MB，77次下载）
- 压缩画质_演示2.mp4

（7.50MB，25次下载）

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-3-11 16:01*

感谢分享

## 回复 by dob_C (#3)

*2026-3-11 16:49*

感谢分享

## 回复 by Imxz (#4)

*2026-3-11 17:20*

tql

## 回复 by Hawcett (#5)

*2026-3-11 17:41*

图挂了，键盘也包浆了，该换换了

## 回复 by iBa0 (#6)

*2026-3-12 09:53*

123

## 回复 by mb_oholboab (#7)

*2026-3-12 10:42*

这个问题困扰我好久了，奈何开发实力欠缺，楼主666

## 回复 by mJqalJqN (#8)

*2026-3-12 16:31*

1

## 回复 by 我不是卷王 (#9)

*2026-3-12 16:35*

666

## 回复 by 梅雨个个 (#10)

*2026-3-30 16:11*

666 什么时候发布呢？

## 回复 by git_14248bibinocode (#11)

*2026-4-12 15:23*

6666666666666

## 回复 by git_14248bibinocode (#12)

*2026-4-12 15:35*

有没有发布，怎么购买

## 回复 by 夕阳s (#13)

*2026-4-15 11:05*

只会逆一点点![image](https://bbs.kanxue.com/view/img/face/001.gif)
