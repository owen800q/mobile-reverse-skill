---
title: '[原创] primp TLS指纹开源库 编译'
url: https://bbs.kanxue.com/thread-287312.htm
tid: 287312
author: 郑z
date: '2025-06-21'
tags: [Android安全, 原创, 工具脚本]
crawled_at: '2026-07-31T14:08:24+08:00'
replies: 1
---

今天晚上朋友说有个库的tls版本有点跟不上了，想让我看看怎么编译的，然后魔改源码，我第一次在windows上编译东西，我朋友也是从没有编译过东西，所以此篇文章比较细致，也算是一个随笔记

官方地址：`https://github.com/deedy5/primp`

# 准备：

安装`python3.8`以上

编译项目需要虚拟环境，可以使用conda，我这里使用的是venv

# 1、安装编译所需环境

## python 3.8+

python就不贴了吧。。。3.8以上都可以，我编译时使用的是3.10.0

## git安装（一般都有吧）

<https://git-scm.com/downloads/win>

![image](https://bbs.kanxue.com/upload/attach/202506/994069_9QHYZ6PY799H42T.jpg)

## rust安装

安装地址：
<https://www.rust-lang.org/tools/install>

安装参考：

<https://zhuanlan.zhihu.com/p/655386777>

![image](https://bbs.kanxue.com/upload/attach/202506/994069_HDJR9RYG96VW5WZ.jpg)

## perl安装

安装地址：

<https://www.rust-lang.org/tools/install>

![image](https://bbs.kanxue.com/upload/attach/202506/994069_G56C2YY9BKSDJX2.jpg)

![image](https://bbs.kanxue.com/upload/attach/202506/994069_JPBRE6T9UJCK9KB.jpg)

## llvm安装，最好选择exe的

安装地址:

<https://github.com/llvm/llvm-project/releases>

![image](https://bbs.kanxue.com/upload/attach/202506/994069_CRHDDE4MQPPGCA8.jpg)

# 2、检查编译环境：

所需环境：`rustc、cargo、nasm、perl、llvm`

其中llvm需要设置系统变量

LIBCLANG_PATH = D:\tools\LLVM\bin

![image](https://bbs.kanxue.com/upload/attach/202506/994069_T8R9B4ZTPVDJWNJ.jpg)

其他环境检查

```java
(.venv) PS D:\demo\primp-main> rustc --version
rustc 1.87.0 (17067e9ac 2025-05-09)
(.venv) PS D:\demo\primp-main> cargo --version
cargo 1.87.0 (99624be96 2025-05-06)
(.venv) PS D:\demo\primp-main> nasm -v
NASM version 2.16.01 compiled on Jun  1 2023
(.venv) PS D:\demo\primp-main> perl --version
Locale 'Chinese (Simplified)_China.936' is unsupported, and may crash the interpreter.

This is perl 5, version 38, subversion 2 (v5.38.2) built for MSWin32-x64-multi-thread

Copyright 1987-2023, Larry Wall

Perl may be copied only under the terms of either the Artistic License or the
GNU General Public License, which may be found in the Perl 5 source kit.

Complete documentation for Perl, including FAQ lists, should be found on
this system using "man perl" or "perldoc perl".  If you have access to the
Internet, point your browser at https://www.perl.org/, the Perl Home Page.
```

# 3、拉取项目

从官方 clone项目到本地 `git clone https://github.com/deedy5/primp.git`

# 4、创建虚拟环境

在拉取的 primp 项目根目录下，python安装路径

`C:\Users\<用户名>\AppData\Local\Programs\Python\Python310\python.exe -m venv .venv`

python.exe为自己的python路径，需要3.8以上（再次强调）

![image](https://bbs.kanxue.com/upload/attach/202506/994069_2DZM5FFVP4AE6C4.jpg)

# 5、测试激活虚拟环境

`.venv/Scripts/activate`

![image](https://bbs.kanxue.com/upload/attach/202506/994069_KWU42YWVC8STQ76.jpg)

项目路径旁边会有.venv，表示使用虚拟环境，因为教程是后补的

正常终端左边是没有虚拟环境名字的

# 6、安装python所需环境

虚拟环境下：`pip install maturin`

# 7、开始编译

windows找到 `x64 Native Tools Command Prompt for VS 2022` (不在此环境下，边编译会缺少 cl 环境）

![image](https://bbs.kanxue.com/upload/attach/202506/994069_C3MJS58WPETYV74.jpg)

进入到项目：

![image](https://bbs.kanxue.com/upload/attach/202506/994069_T5548FWCCFVK7V4.jpg)

激活虚拟环境：

执行完 `.venv\Scripts\activate`窗口会刷新，左边出现(.venv)，成功激活环境

![image](https://bbs.kanxue.com/upload/attach/202506/994069_7KGAG25P34HTWYF.jpg)

执行编译 `maturin develop`

![image](https://bbs.kanxue.com/upload/attach/202506/994069_WUTSVV9TUGBG74R.webp)

# 8、尝试运行

首次导入模块，会报错

```java
import primp
Traceback (most recent call last):
File "<stdin>", line 1, in <module>
File "D:\demo\primp-main\primp_init_.py", line 9, in <module>
from typing_extensions import Unpack
ModuleNotFoundError: No module named 'typing_extensions'
```

执行 `pip install typing_extensions`

![image](https://bbs.kanxue.com/upload/attach/202506/994069_U6SEKMKBTH5TAF4.jpg)

就正常了

---

# 回复

## 回复 by 郑z (#2)

*2025-6-21 01:29*

魔改的时候发现，primp引用的库，原作者自己实现了py版本的，且更新频繁，非常的肝

[0x676e67/rnet: A blazing-fast Python HTTP Client with TLS fingerprint](https://github.com/0x676e67/rnet)
