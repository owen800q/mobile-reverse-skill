---
title: '[原创] Frida 脚本无 Root 一键持久化方案：将 Frida 脚本打包至 Xposed 模块、直接注入APP、生成 .so, .dll'
url: https://bbs.kanxue.com/thread-289075.htm
tid: 289075
author: _MicroBlock
date: '2025-11-12'
tags: [Android安全, 原创, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:01:48+08:00'
replies: 8
---

**# 缘起**

最近在开发某款 APP 的功能扩展时，我使用 Frida 编写了大量逻辑，但不想再逐行翻译成 Xposed 代码。于是决定将 Frida 直接固化到 APP 中。

最初尝试使用 frida-gadget，但在 Android 16 上遇到问题：脚本完全不执行，也没有任何错误提示，只好放弃。

在网上搜索后，没有找到便捷的持久化方案，于是决定自己动手实现。
我的目标是：只需运行一行命令，就能自动打包出 Xposed 模块、已固化 Frida 脚本的 APP 包，以及可注入运行 Frida 脚本的 .so 和 .dll 文件。

最终，这个目标顺利实现了。**如果你只是想打包 Frida 脚本，而不关心具体原理，可以直接使用以下工具**：
<https://github.com/std-microblock/fripack/>

---

**# 自编译 Frida**

既然要自己动手，自然要做得尽善尽美。一方面需要掩盖 Frida 的某些特征，另一方面也要尽量减小体积。此外，我还希望将脚本直接嵌入二进制文件中，而不是作为独立文件存在。于是，我开始研究如何自行编译 Frida，类似于实现一个自定义的 frida-gadget。

首先，我们来看一下 Frida 的代码架构：
![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_CE9QSKMAFNJ2D88.webp)
（注：此为简化示意图。实际上，frida-inject 和 frida-server 注入的是 frida-agent，但整体结构类似。）

可以看到，Frida Gadget 实际上是通过调用 Frida-GumJS 来执行我们的脚本。因此，我们也可以编写一个程序，调用 Frida-GumJS 来执行脚本。为了实现这一点，首先需要编译出 Frida-GumJS 库。

Frida-GumJS 通常包含两个引擎：V8 和 QuickJS。V8 执行效率高，但体积较大；QuickJS 体积较小。为了减小最终生成的二进制文件体积，我关闭了 V8 和内置的 Database，并参考 Florida 的 CI 流程，编写了一个 GitHub CI 来编译 Frida-GumJS：
<https://github.com/FriRebuild/fripack-inject>

接着，我创建了一个 xmake 项目，首先实现调用 GumJS 执行脚本的功能：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_Q5KPYMNZSP4UDAR.webp)

为了便于后续嵌入 JS 脚本，我设计了一个带有特定 Magic 标记的结构体：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_9ASQY9MVV92RTDY.webp)

这样，在生成 .so 文件时，就可以通过扫描 Magic 标记找到这个配置结构，然后通过设置 `data_size` 和 `data_offset` 来指定脚本数据在二进制文件中的存储位置。

接下来，我们需要编写一个 CLI 工具，将脚本数据嵌入到二进制文件中。这里我选择了使用 Rust 来实现。

---

**# 将数据嵌入二进制文件**

**## ELF 文件编辑**

ELF 文件的主要结构包括 Section 和 Segment，其中数据通过 Segment 映射到内存中。我们只需新建一个 Segment，将脚本数据放入其中，并确保其加载到内存中。然后，计算出该数据映射的虚拟地址与 `g_embedded_config` 虚拟地址之间的偏移量，这样我们自制的 frida-gadget 就能正确加载数据了。

听起来很简单，我们来实现一下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_4SAX95NB8PWSM5F.webp)

需要特别注意：对于需要加载到内存中的 Segment（PT_LOAD），其 `vaddr` 必须按 4K 或 16K 对齐，否则 `dl` 可能不会正确映射，且不会报错。

同时，由于新增了 Segment 和 Section，我们还需要扩展 ELF 文件头的大小：
![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_E3GVJ5BS945JXC8.webp)

运行后却发现报错：`.note sh_offset at 0x270, must be larger than 0x28a`。这是怎么回事？原来是因为新增的 Segment 和 Section 导致 ELF 头变大，与原有的部分 Section 发生了重叠。我们需要将这些重叠的 Section 在文件中的数据及其 `p_offset` 移动到文件末尾：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_YA7A828ESY7DBES.webp)

再次运行，这次没有报错了。但将文件放到手机中加载时，又出现了新错误：`PT_PHDR segment is not covered by a PT_LOAD segment`。这个问题比较奇怪，网上资料也很少。我猜测 PT_PHDR Segment 本身不会被映射到内存中，它需要一个 PT_LOAD Segment 来帮助加载。于是，我们找到覆盖 PT_PHDR Segment 的那个 Segment，并将其扩展的大小同步到 PT_PHDR Segment：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_GVQZ53H4WVAXA2N.webp)

接着，我们找到 Magic 标记在二进制文件中的位置，定位其所在的 Segment，并获取其 `vaddr`：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_P4ZNEJKSMESGQS7.webp)

计算出偏移量后，将其填入二进制文件中：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_NSRW2WK96HB62C7.webp)

**## PE 文件编辑**

PE 文件的处理逻辑类似。虽然编辑 ELF 花了大半天时间，踩了不少坑，但编写 PE 编辑代码只用了十分钟。不得不说，PE 的设计比 ELF 更优秀（除了那个强制要求 ordinal 的 EAT），而且几乎没有遇到什么坑。以下是相关代码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_AADUNMVKUVEYXTB.webp)

至此，我们得到了一个**无需任何外部文件依赖、加载即自动执行脚本**的二进制文件。

---

**# 加载二进制文件到目标进程**

接下来，只需要想办法将这个二进制文件加载到目标进程中。实现方式有很多，例如：

- 重新打包 APK，对 APP 自带的 .so 文件使用 patchelf，将我们的 .so 加入其依赖项。
- 重新打包 APK，在某个初始化类中添加静态初始化代码，调用 `System.loadLibrary` 加载我们的 .so。
- 编写 Xposed 模块，利用其在目标进程中执行代码的特性来加载 .so。
- 对于 Windows，使用多种 DLL 注入手段加载我们的 DLL。
- 对于 Linux，使用 `LD_PRELOAD` 或其他映射方法加载我们的 .so。
- 编写 Zygisk 模块，直接对特定 APP 加载我们的 .so。

目前，我已实现了前五种加载方式。受篇幅所限，这里仅介绍 Xposed 的实现方式。

---

**# 生成 Xposed 模块来加载 .so**

Xposed 模块会在目标进程中执行代码，因此我们只需在 `xposed_init` 类的 `initZygote` 方法中获取模块的 APK 路径，然后使用 `System.load` 加载其中的 .so 文件即可。

但问题在于，我们需要生成的是一个 APK 文件。我不想依赖过于笨重的 gradlew，也不想手动处理安卓特有的压缩格式、aapt2 编码、zipalign 等步骤。因此，我选择直接生成 apktool 工程，然后使用 apktool 构建 Xposed 模块的 APK。这样只需安装 apktool，即可方便地完成生成。

Xposed 模块的主要特征包括：AndroidManifest 中的几个特殊 metadata，以及 `/assets/` 文件夹中的 `xposed_init` 和 `native_init` 文件。我们直接手动构建 apktool 的文件结构，并编写一段 Smali 代码，继承 `IXposedHookZygoteInit` 和 `IXposedHookLoadPackage`，以实现加载 .so 的逻辑：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202511/1052870_KNH4V2VTTR2QQ8C.webp)

最后使用 `apktool b` 命令，即可构建出 Xposed 模块。

---

至此，我们已经实现了从 Frida 脚本一键打包生成 Xposed 模块的大部分逻辑。

---

# 回复

## 回复 by 呼吸24K纯氧 (#2)

*2025-11-12 16:09*

期待更多优质内容的分享，论坛有你更精彩！

## 回复 by mb_elqwyvnm (#3)

*2025-11-13 00:01*

nice

## 回复 by 笑对VS人生 (#4)

*2025-11-13 20:53*

可以试试非root环境下Frida完全内置apk打包https://bbs.kanxue.com/thread-284482.htm

## 回复 by _MicroBlock (#5)

*2025-11-13 23:54*

>
> [笑对VS人生](https://bbs.kanxue.com/user-687336.htm)
>
>  可以试试非root环境下Frida完全内置apk打包https://bbs.kanxue.com/thread-284482.htm
>
>
>

这个也支持了的，"type": "inject-apk"，也是一键生成

## 回复 by mb_atdqqbte (#6)

*2025-11-16 22:47*

fridagumjs库不是有导出脚本执行函数吗

## 回复 by Matriy (#7)

*2025-11-24 23:47*

想问下，我现在frida测试用的别的端口绕过，如果用这个项目，能解决端口检测的问题吗?

## 回复 by mb_sdvjpqrb (#8)

*2026-1-20 17:52*

大佬写的有点高级，小白表示看不懂最好出个简单例子教程

## 回复 by shuangmou (#9)

*2026-2-6 17:15*

感谢分享
