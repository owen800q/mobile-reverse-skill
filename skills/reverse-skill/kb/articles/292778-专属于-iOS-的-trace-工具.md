---
title: '[原创] 专属于 iOS 的 trace 工具'
url: https://bbs.kanxue.com/thread-292778.htm
tid: 292778
author: αβγδεξπ
date: ''
tags: [Android安全, 原创]
crawled_at: '2026-08-26T01:57:39+00:00'
replies: 7
attachments:
- {filename: com.snk.qbditracer_iphoneos-arm.deb, aid: '404036', path: ../attachments/292778/com.snk.qbditracer_iphoneos-arm.deb, url: 'https://bbs.kanxue.com/attach-download-404036-311c6b7f471816b26ac6874010783545@DeI+ulbEqQlqgbGdw0KVZQ==.htm', size: 1.32MB，6次下载, downloaded: false}
---

目录- 前言
- QBDI 是什么
- 为什么还要配合 Dobby
- trace 输出格式
- 向量寄存器
- 基础使用
- 添加 trace 规则
- 添加监视
- 日志输出位置
# 前言

众所周知，trace 在算法分析中的地位举足轻重。但在 iOS 上，用 Frida Stalker 不够稳定、也容易被检测到；用 unidbg 或 chomper 又得补一大堆环境。所以今天，Ta来了！Ta 来了！Ta带着 QBDI 和 Dobby 走来了，不仅有着简单的界面，还有着实实在在的功能。

这是本人在二进制分析过程中结合大模型开发的一个工具，欢迎大家交流学习，后续会考虑公布源码。

想快速常常工具的咸淡，请戳这里 [com.snk.qbditracer_iphoneos-arm.deb](https://bbs.kanxue.com/upload/attach/202608/982645_QVK87TFZ578ZBMG._deb) 。

## QBDI 是什么

QBDI（QuarkslaB Dynamic binaryInstrumentation）是一款动态二进制插桩框架。简单说，它能把一段代码"托管"到自己的虚拟环境里执行，每执行一条指令都回调一次——于是你就能逐条指令地观察目标代码怎么跑、寄存器和内存怎么变，而不用改动原始二进制。

早期 QBDI 在 iOS 中支持有限，但官网最新版已经正式支持 **iOS ARM64**。这也是本项目选择它的直接原因：能在越狱 iPhone 上稳定地做指令级 trace。

## 为什么还要配合 Dobby

QBDI 只解决"逐条指令记录"这件事，但它本身**不负责把自己挂到目标代码上**——你得先有办法在某个地址"插一脚"，把控制权交给 QBDI。

这一步就交给 [Dobby](https://github.com/jmpews/Dobby)。Dobby 是一个 inline hook 库，负责在指定地址下钩子。二者分工很清晰：

- **Dobby**：在 `模块基址 + 起始地址` 处 hook 住，作为进入点。
- **QBDI**：命中后接管执行，从起始地址逐条 trace 到结束地址。

一个管"从哪进"，一个管"怎么记"，配合起来才能实现"在函数中间任意一段，逐指令 trace"的效果。

# trace 输出格式

每 trace 到一条指令，日志里会输出一行，格式如下：

```python
0x<动态地址> (<模块名>!0x<静态地址>): <汇编指令>   {变化的寄存器: 值, ...}
\```

- **动态地址**：这条指令运行时的实际地址（已含 ASLR slide）。
- **模块名!静态地址**：换算回相对模块基址的偏移，方便直接对照 IDA/Ghidra 里看到的地址。
- **汇编指令**：这条指令的反汇编。
- **末尾大括号**：寄存器的值。

为了让日志不至于爆炸，寄存器采用**增量输出**：

- **第一条指令**会完整打印全部 32 个通用寄存器（`x0`–`x28`、`fp`、`lr`、`sp`）的初始值。
- **之后每一条**只打印相比上一条**发生了变化的寄存器**——一眼就能看出这条指令改动了什么。若某条指令没有改动任何寄存器，则大括号省略。

寄存器值统一以 16 位十六进制显示（如 `0x000000016fdff8a0`）。

# 向量寄存器

在规则的「记录内容(logMask)」里勾选 **向量寄存器(VREG)**，就会额外记录向量寄存器 `v0`–`v31`。它们和通用寄存器一样采用增量输出，但单独占一行、以 `V{...}` 开头：

```python
0x<动态地址> (<模块名>!0x<静态地址>): <汇编指令>   {变化的通用寄存器: 值}
   V{变化的向量寄存器: 值, ...}
\```

每个向量寄存器是 128 位，以 32 位十六进制显示（高 64 位在前、低 64 位在后）。

>
> 向量寄存器数据量大，默认不开。调试 NEON、加解密等涉及向量运算的代码时再勾选。
>
>
>

# 基础使用

插件顶部有一个总开关，它是所有规则的总闸。关闭时，即使 trace 条目已经配好，规则也不会生效。所以开始 trace 前，先确认总开关是打开的。

![image-20260825115637579](https://bbs.kanxue.com/upload/attach/202608/982645_RVAYCYPEER3KY3N.png)

在某条 trace 条目上**右滑**，可以停用这条规则——规则还在，只是暂时不跑，方便随时切换。

![image-20260825150759196](https://bbs.kanxue.com/upload/attach/202608/982645_WRN26JZ5SZWUTPA.png)

在某条 trace 条目上**左滑**，则可以导出、复制或删除这条规则。

![image-20260825150823832](https://bbs.kanxue.com/upload/attach/202608/982645_8EEE3JK3UH4T9EG.png)

# 添加 trace 规则

如果之前创建并导出过规则，直接选 **【导入 Tracer】** 就能复用，省去重新配置。下面介绍从零创建一条新规则。

![image-20260825150605609](https://bbs.kanxue.com/upload/attach/202608/982645_MV288CAZKX6M5TR.png)

进入后，先选定要 trace 的目标 App，再填入目标模块名，以及 trace 的起始地址和结束地址。

其中「延迟」是指等程序启动、加载完相关库之后再开始 trace，留几秒缓冲能避免模块还没就位就 hook 失败。「trace 次数」通常设为 1 就够了。

![image-20260825151102404](https://bbs.kanxue.com/upload/attach/202608/982645_9JKBBZM9J2KT83D.png)

## 添加监视

监视的作用，是当 trace 到某个地址时，把指定寄存器的值输出出来。输出形式可以按需选择，比如按字符串读取，或者以 dump 形式呈现。

![image-20260825151314144](https://bbs.kanxue.com/upload/attach/202608/982645_337FXPP27YP4NSJ.png)

![image-20260825151430351](https://bbs.kanxue.com/upload/attach/202608/982645_DVF8P5FVYYHHENV.png)

添加完成后，效果如下：

![image-20260825151510723](https://bbs.kanxue.com/upload/attach/202608/982645_9WBY3ZFY3KVJSF8.png)

举个例子，配好下面这几条监视后，trace 日志里就会输出对应的数据：

![image-20260825151608044](https://bbs.kanxue.com/upload/attach/202608/982645_6SP4PWU2HF8H723.png)

若某个地址配置了监视点，会在该指令后紧跟一行 `[watch ...]` 输出对应寄存器解引用的内容（见上文ß「添加监视」）。

![image-20260825151733627](https://bbs.kanxue.com/upload/attach/202608/982645_UUQR87A8VDMRAY8.png)

上面是输入，下面是签名结果，输入和输出一目了然，排查和追溯都很方便。

![image-20260825151805202](https://bbs.kanxue.com/upload/attach/202608/982645_3X7N68VXF3T28B7.png)

# 日志输出位置

trace 日志会写到手机的 `/tmp/` 目录下。具体的文件命名规则，点击左上角的问号即可查看。

![image-20260825153554440](https://bbs.kanxue.com/upload/attach/202608/982645_HA3M9KBCT356F73.png)

## 附件

- [com.snk.qbditracer_iphoneos-arm.deb](../attachments/292778/com.snk.qbditracer_iphoneos-arm.deb) — 1.32MB，6次下载

---

# 回复

## 回复 by mb_ldbucrik (#2)

感谢分享

## 回复 by 墨穹呢 (#3)

感谢分享

## 回复 by 墨穹呢 (#4)

墨穹呢  0秒前
  引用  编辑  举报 3 楼  0
感谢分享

## 回复 by tonykros (#5)

666

## 回复 by kingking888 (#6)

666

## 回复 by MaYil (#7)

感谢分享

## 回复 by Imxz (#8)

tql
