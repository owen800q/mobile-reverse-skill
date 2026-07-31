---
title: '[原创]Apatch KPM内核模块从编译入门到环境对抗跑路(1)-入门知识'
url: https://bbs.kanxue.com/thread-291052.htm
tid: 291052
author: 小黄鸭爱学习
date: '2026-04-29'
tags: [Android安全, 原创, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T13:53:59+08:00'
replies: 2
---

## 编译你的第一个KPM

### > 重要提示，在做真机KPM模块开发测试之前请先备份你的boot.img用于救砖。

### 环境准备

- ubuntu24.02
- 下载编译工具
- 然后是在这下载GNU tools ，建议使用aarch64-none-elf，我之前使用linux自带的aarch64-linux-gnu编译出来无法正常使用。`https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads/11-2-2022-02`
- 实测这个地址下载的非常慢，建议直接复制链接用迅雷

```
# 1. 下载工具链
wget wget https://developer.arm.com/-/media/Files/downloads/gnu/11.2-2022.02/binrel/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz

# 2. 解压（直接解压 .tar.xz 文件）
tar -xvf gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf.tar.xz

# 3. 移动到常用目录（可选，建议移动到 /usr/local/ 或 /opt/）
sudo mv gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf /opt/

# 4. 将 bin 目录添加到 PATH（临时生效）
export PATH=$PATH:/opt/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf/bin

# 5. 验证是否安装成功
aarch64-none-elf-gcc --version
```

![image](https://bbs.kanxue.com/upload/attach/202604/832784_GZSG6AB2ZG32Q5V.webp)下载示例编译

下载工程，切换到示例hello工程

```
# 下载KernelPatch源码
git clone https://github.com/bmax121/KernelPatch
cd KernelPatch/kpms/demo-hello

# 设置临时环境变量
export PATH=/opt/gcc-arm-11.2-2022.02-x86_64-aarch64-none-elf/bin:$PATH
export TARGET_COMPILE=aarch64-none-elf-
```

- make 进行编译 输出文件 hello.kpm 和 hello.o

![image](https://bbs.kanxue.com/upload/attach/202604/832784_34Y9CWWDQ4MKRFZ.webp)安装hello.kpm

- 将文件推送到手机

`adb push hello.kpm /storage/emulated/0/Download`

- 打开管理器选择文件安装

- ![image](https://bbs.kanxue.com/upload/attach/202604/832784_DU4RXTD65BMGT2J.webp)adb 验证模块加载成功信息

```
# 查看内核日志
adb shell
su
dmesg | grep -i kp
```

![image](https://bbs.kanxue.com/upload/attach/202604/832784_5V2U3NWRKRBHPWK.webp)理解KPM模块的基本信息

hello模块作为最简单的KPM示例，其中包含了KPM模块的基本框架内容。

### hello.c

- 演示kpm模块的整个运行周期，并写下日志。

#### 1.KPM标识部分

该内容会显示在安装界面上

```
/* KPM 元信息 —— 用于标识模块身份 */
KPM_NAME("kpm-hello-demo");       /* 模块名称，必须唯一 */
KPM_VERSION("1.0.0");             /* 模块版本 */
KPM_LICENSE("GPL v2");            /* 许可证 */
KPM_AUTHOR("bmax121");            /* 作者 */
KPM_DESCRIPTION("KernelPatch Module Example"); /* 模块描述 */
```

#### 2.生命周期函数

- init 加载触发

![image](https://bbs.kanxue.com/upload/attach/202604/832784_GD4GJWAHCVUGATX.webp)

- exit 卸载触发

![image](https://bbs.kanxue.com/upload/attach/202604/832784_43EDMWWNG9SJWNH.webp)

- control0 在界面上输入参数时候触发

![image](https://bbs.kanxue.com/upload/attach/202604/832784_DDJEHVTCZ358XSK.webp)

![image](https://bbs.kanxue.com/upload/attach/202604/832784_6RRJRDKUBGURU2Z.webp)

![image](https://bbs.kanxue.com/upload/attach/202604/832784_AQ9CJXKBDN2W95T.webp)

获取了输入参数，并且调用`compat_copy_to_user`显示到用户

- control1 用户态通过 kpctl 发送原始数据时调用触发。在界面上我没触发出来，应该是嵌入模块预设参数的时候触发(不太关注这个)

#### 3.注册函数生效

```
/* 注册 KPM 生命周期回调函数 */

KPM_INIT(hello_init);      /* 注册初始化函数 */
KPM_CTL0(hello_control0);  /* 注册控制命令 0 */
KPM_CTL1(hello_control1);  /* 注册控制命令 1 */
KPM_EXIT(hello_exit);      /* 注册退出函数 */
```

### makeflie文件

- 模块的编译配置
- 编译工程依赖于 `KernelPatch` 项目，必须指定KernelPatch目录。

## 基于kpm的inlineHook和SyscallHook

关于这两部分，原文档说的特别清楚。我直接放给AI总结一下

<https://github.com/bmax121/KernelPatch/blob/main/doc/zh-CN/inline-hook.md>
<https://github.com/bmax121/KernelPatch/blob/main/doc/zh-CN/syscall-hook.md>

### 核心概念对比

| 特性 | **Syscall Hook** | **Inline Hook** |
|-|-|-|
| **目标** | 拦截系统调用（如 `openat`、`read`） | 拦截任意内核函数 |
| **底层实现** | 基于 Inline Hook 框架，并自动处理内核差异（如有无 syscall wrapper） | 直接修改 ARM64 内核函数入口代码，实现跳转 |
| **主要API** | `hook_syscalln()`（自动选择策略） `inline_hook_syscalln()` `fp_hook_syscalln()` | `hook_wrapN()`（推荐，支持链） `hook()`（简单替换） |
| **参数访问** | **必须**使用专用宏：`syscall_argn(args, n)` | 直接通过 `hook_fargsN_t` 结构体的 `argN` 成员访问 |
| **回调类型** | 基于统一的 `hook_fargsN_t` | 根据参数个数使用 `hook_fargsN_t` |
| **跳过原函数** | 设置 `args->skip_origin = 1` 并提供返回值 | 设置 `args->skip_origin = 1` 并提供返回值 |
| **传递私有数据** | 通过 `udata` 参数（用户数据指针） | 通过 `udata` 参数 或 `fargs->local` （在 before/after 间共享） |
|  |  |  |

- inlineHook可在运行时拦截并修改任意内核函数的行为。只能hook内核层无法针对App函数进行hook。
- SyscallHook是基于inlineHook的针对系统调用的封装处理，底层依然是inlineHook。

## 实战你的第一个kpm模块

在反调试检测和环境伪装这一块，kpm能做到更底层的对抗。

> 抛砖引玉，我这里实战对抗一下`libmsaoaidsec.so`这个模块的frida检测。不用frida脚本的反检测代码而是通过kpm模块隐藏frida信息。
>
>
>
>
> 代码整理中，先发试试能不能通过检测
>
>

## 参考文档

[APatch部署及KPM实现InlineHook及SyscallHook技术](https://it.idocdown.com/app/articles/blogs/detail/18028)
[APatch部署及KPM实现InlineHook及SyscallHook技术-先知社区](https://xz.aliyun.com/news/91659)

官方教程
[KernelPatch Modules(KPM) 使用指南 | APatch Docs](https://apatch.dev/zh_CN/kpm-usage-guide.html)
[KernelPatch/doc/zh-CN at main · bmax121/KernelPatch](https://github.com/bmax121/KernelPatch/tree/main/doc/zh-CN)

---

# 回复

## 回复 by Imxz (#2)

*2026-5-1 14:44*

tql

## 回复 by 心在o (#3)

*2026-5-25 00:49*

支持一下，什么时候更新下一版那
