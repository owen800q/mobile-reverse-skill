---
title: '[原创]Android主流Root方案Magisk和KernelSU的对比和详解'
url: https://bbs.kanxue.com/thread-283505.htm
tid: 283505
author: 恋空
date: '2024-09-18'
tags: [Android安全, 原创, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-08-11T08:44:41+00:00'
replies: 15
---

刚好最近在研究内核级Root，感觉这玩意还挺复杂的，研究了挺久。为了让大家少踩坑，特意写一遍文章解答一下这些Root方式的原理和细节。

# 一、Magisk框架

![image](https://bbs.kanxue.com/upload/attach/202409/3WVV7DZZR96Y6CN.jpg)

Magisk是一款用于Android设备的开源ROOT框架，它通过独特的原理实现了对系统的深度定制和优化。

### 1. Systemless Root技术

Magisk的核心原理在于采用了一种名为“Systemless Root”的技术。与传统的root方法不同，Systemless Root技术允许用户在不修改系统分区（/system）的情况下获得root权限。这意味着，Magisk在修改系统时不会破坏系统分区的完整性和稳定性，从而避免了因root而导致的问题，如OTA升级困难和系统无法启动等。

### 2. Boot分区修改

Magisk通过在boot分区中创建一个Magisk镜像（通常是/data/magisk.img），并将需要修改的文件和目录挂载到这个镜像中，实现对系统的修改。这样，所有的修改都发生在boot分区内，而不会影响到系统分区。在Android设备的启动过程中，Magisk通过修改boot分区中的init文件，实现在系统启动时挂载Magisk镜像，从而实现对系统的隐藏和修改。

![image](https://bbs.kanxue.com/upload/attach/202409/862224_BCR7V49JWHEVFQW.webp)

**Magisk框架通过向boot.img的ramdisk进行解析，并通过cpio工具将magiskinit替换掉/init文件。这样系统在启动时就会首先执行magiskinit，magiskinit会首先以init进程的身份完成systemless加载，然后再调用原来的init文件完成系统的启动。**

### 3. Hook和Bind Mount机制

Magisk使用了一种Hook和Bind Mount的机制来构建出一个在system基础上能够自定义替换、增加以及删除的文件系统 (/sbin)。具体来说，Magisk在启动时会在boot中创建钩子，然后将/data/magisk.img挂载到/magisk，从而构建出一个可以自定义的文件系统。这个文件系统与系统的原始文件系统并行存在，但Magisk能够控制哪些文件或目录被替换、增加或删除。

**具体流程如下：**

- magiskinit会在Pre-Init（预启动）阶段首先挂载magisk.img文件到/sbin当中去，然后通过对init.rc的挂载实现修改并注入/sbin/magiskd服务。这样/sbin中就会有su文件，su文件通过与magiskd通信实现获取Root。
- 在post-fs-data触发后， /data 被解密并挂载时。守护进程 Magiskd 将启动，执行 post-fs-data 脚本，并调用已经安装模块中对应的流程文件(shell)。例如posf-fs-data.sh之类的。
- **在启动过程中magiskd会修改sepolicy规则，并增加`magisk`命名空间规则，为后面ROOT和模块提供更高的权限。**
- 通过执行resetprop程序实现将各个模块的system.prop信息强制覆盖到系统的property里面。

### 4. 模块化和功能丰富

除了上述的核心原理外，Magisk还提供了丰富的模块和功能。用户可以通过Magisk Manager（Magisk的管理程序）来安装、升级和管理这些模块。这些模块可以实现各种功能和特性的增加和定制，如Xposed模块用于进一步修改和优化系统、Magisk Hide用于隐藏Magisk和其他应用程序的存在以绕过一些应用的检测、MagiskSU作为root权限的管理工具等。

![image](https://bbs.kanxue.com/upload/attach/202409/862224_4GWRMNQ3KR7SVCC.webp)

通过module_install.sh和util_function.sh实现对Magisk模块的安装，将插件文件解压到/data/adb/module下。

### 5. 方案优势和劣势

由于Magisk采用的Systemless Root技术，并且所有的修改都发生在boot分区内，因此它能够保持非常良好的兼容性，无视原来系统和内核被定制过的情况，不会影响系统的稳定性和安全性。这使得用户可以在不牺牲系统稳定性和安全性的前提下，享受root带来的各种便利和功能。

劣势是magisk虽然成功获取了root权限和模块加载，但是在加载过程中留下很多特征（例如，环境变量，/sbin目录，特征文件）。所以就需要shamiko这类插件来实现隐藏。

# 二、KernelSU

KernelSU是weishu编写的一个内核级ROOT框架。与Magisk不同的是，KernelSU不通过替换init文件，而是通过修改或者注入内核来实现root。

### 1、注入方式

KernelSU通过了两种方式，一种是通过直接刷入已经带KernelSU的GKI内核来获取权限，另一种则是KernelSU最近发布的通过对boot.img进行patch来实现安装的方式。

**值得注意的是，KernelSU虽然也提供patch模式，但是与Magisk不同的是，KernelSU仅采用注入LKM模块+kprobe来实现将内核模块注入系统内核，通过kprobe来hook给用户提供ROOT。不会对用户空间造成太大的污染。**

### **2.ROOT获取原理**

- 首先KernelSU通过修改内核的faccessat、stat调用入口，让需要root的应用进程能够感知到su文件。![image](https://bbs.kanxue.com/upload/attach/202409/862224_KB4RDDZHQ7RJNSG.webp)
- 然后在程序通过execve执行/system/bin/su时，KernelSU通过在execve插桩，判断是否是被运行获取root的应用。如果是，则通过**修改uid为0，SELinux context为u:r:su:s0**，然后重定向到/system/bin/sh的方式为需要的应用提供Root权限。          ![image](https://bbs.kanxue.com/upload/attach/202409/862224_754U7HN4X2AADDS.webp)

### 3.模块化原理

- ksud.c: 通过修改open和read调用，实现将ksud服务注入到uevent.rc中，然后通过ksud调用模块内的脚本文件，来实现对Magisk模块的兼容。![image](https://bbs.kanxue.com/upload/attach/202409/862224_S5Q4W7H7Y7B954B.webp)
- 其他的，KernelSU也是一样通过resetprop实现对property和修改，和修改sepolicy实现更高的权限获取。但是KernelSU更为高明的是，KernelSU通过在内核中对security模块的struct policydb修改来实现在内核空间对sepolicy的修改，无需通过用户空间来修改。
- KernelSU使用OverlayFS这一项Linux内核新特性来实现和Magisk一样的systemless，并且更为高效，不需要在系统启动时进行bindmount。

参考：

Root注入：<https://github.com/tiann/KernelSU/blob/main/kernel/sucompat.c>

服务注入：<https://github.com/tiann/KernelSU/blob/main/kernel/ksud.c>

sepolicy修改： <https://github.com/tiann/KernelSU/blob/main/kernel/selinux/sepolicy.c>

# 三、附言

本篇文章版权属于恋空（https://bbs.kanxue.com/homepage-862224.htm），QQ：2928455383。转载请声明出处，之前看到很多人将我的文章转载到cs某n，某乎，并且不声明来源。请大家尊重原创！

---

# 回复

## 回复 by 恋空 (#2)

*2024-9-18 20:03*

APatch还没怎么了解，等了解后再补齐。

## 回复 by Thehepta (#3)

*2024-9-18 20:05*

kernelsu 也提供了和magisk一样的模块功能，这个的原理是什么

## 回复 by 恋空 (#4)

*2024-9-18 20:08*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  kernelsu 也提供了和magisk一样的模块功能，这个的原理是什么
>
>

magisk的模块本来就是一个zip包，里面有各种脚本文件来启动。KernelSU也通过root在系统启动的时候执行这些文件，提供一个差不多的执行环境，就可以兼容大部分的magisk插件了

## 回复 by 珍惜Any (#5)

*2024-9-18 20:28*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 你瞒我瞒 (#6)

*2024-9-19 09:13*

下一篇ap

## 回复 by mb_fidppcok (#7)

*2024-9-19 09:45*

感觉在写kernelSU 时，内容没有magisk  一样丰富

## 回复 by Lnju (#8)

*2024-9-19 11:46*

赞

## 回复 by 院士 (#9)

*2024-9-19 12:52*

期待楼主补充apatch。![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 恋空 (#10)

*2024-9-19 15:25*

>
> [院士](https://bbs.kanxue.com/user-682431.htm)
>
>  期待楼主补充apatch。[em_13]
>
>

对APatch至今都不太明白，只知道是直接对内核二进制进行解析，从符号表中找出关键函数进行插桩。其他的就还没明白，所以不敢写。

## 回复 by 恋空 (#11)

*2024-9-26 16:10*

>
> [mb_fidppcok](https://bbs.kanxue.com/user-986312.htm)
>
>  感觉在写kernelSU 时，内容没有magisk 一样丰富
>
>

ksu更底层也更干净，magisk需要更强的兼容性和通用性，而且Magisk经过这么多年的改进确实已经很完善了，肯定是更复杂一些。

## 回复 by 恋空 (#12)

*2024-9-30 16:04*

新群交流进![image](https://bbs.kanxue.com/upload/attach/202409/862224_4HFXUZXAUVCDSQ3.webp)

## 回复 by artake (#13)

*2024-9-30 17:42*

好像都已经过时了，现在是APatch了

## 回复 by 恋空 (#14)

*2024-10-3 15:41*

>
> [artake](https://bbs.kanxue.com/user-409365.htm)
>
>  好像都已经过时了，现在是APatch了
>
>

APatch都还不成熟，在你这就把Magisk和KernelSU淘汰了![image](https://bbs.kanxue.com/view/img/face/19.gif)

## 回复 by mb_ldbucrik (#15)

*2024-12-6 13:00*

apatch写一个内核模块hook全部系统调用好实现吗

## 回复 by wx_范迪塞尔 (#16)

*2025-3-28 11:12*

APatch 最新的不支持了
