---
title: '[原创]FRIDA源码编译(win，ubuntu20.4)和frida-tools安装以及编译遇到问题'
url: https://bbs.kanxue.com/thread-277588.htm
tid: 277588
author: 快乐的小跳蛙
date: '2023-06-12'
tags: [Android安全, 原创, HOOK注入, 源码框架]
crawled_at: '2026-07-31T14:45:00+08:00'
replies: 7
---

## 一.前言

        frida是一个款优秀的hook框架。本篇文章是对自己根据frida编译手册在编译frida源码过程中的回顾总结以及遇到的问题如何解决的，分享给在编译frida源码过程遇到问题的坛友。

        下面我们就根据[frida编译手册](https://frida.re/docs/building/)来进行编译

## 二.win编译

        [frida在windows编译手册](https://frida.re/docs/building/#windows)

2.1.编译环境

        首先要确认编译前的环境：

               1，VS2022

               2，Git

               3，python

               4，NodeJs

        关于python环境和Nodejs要注意的是：python环境必须安装在这个目录下**C:\Program Files\Python310\**，否则会无法编译。

### 2.2.自定义python路径

由于python的默认安装路径在appdata路径下，也可以修改**releng/frida.props**文件中的<PythonLoacation>标签来修改python的加载路径。

| 123 | `<``PythonLocation` `Condition``=``"'$(PythonLocation)'=='' AND '$(Platform)'=='x64'"``>你的python路径</``PythonLocation``>` `<``PythonLocation` `Condition``=``"'$(PythonLocation)'=='' AND '$(Platform)'=='Win32'"``>你的python路径</``PythonLocation``>` |
|-|-|

### 2.3.nodej版本的选择

编译手册并未对nodejs的版本要求有说明，并不是你可以使用任意你喜欢的nodejs版本进行编译。这里我们参考[作者编译完成的模块](https://github.com/frida/frida/releases)来选择nodejs的版本。

其中V83，V93就是nodejs的版本。

![image](https://bbs.kanxue.com/upload/attach/202306/871252_BQQ2P4F5BTV4HPP.jpg)

我们可以对比nodejs的版本号来选择安装nodejs的版本，我这里选择的是V93。[nodejs版本对照及下载](https://nodejs.org/en/download/releases)

![image](https://bbs.kanxue.com/upload/attach/202306/871252_EPAD5TKW26MB33V.jpg)

至此我们需要的环境就已经准备好了，下面开始clone源码。命令：git clone --recurse-submodules https://github.com/frida/frida

### 2.4.编译windows Toolchain and SDK

执行releng/build-deps-windows.py全自动编译。脚本执行成功后你可以下楼去打篮球，跑步，玩累了回来你会发现已经编译好了。这个过程是非常耗时的，因为会编译各种版本的SDK，我的自己12核3.7G频率的CPU编译了约70分钟左右。生成目录在build/

### 2.5.开始编译

如果已经进行到了这一步，所有的准备工作我们已经完成了。用VS2022打开frida目录下的frida.sln。选择你喜欢的版本，win32/x64/Debug/Release。右键frida-core这个工程，选择生成。如果不出意外的话，要出意外了。在下方的输出目录会输出许多警告日志信息，它会遮挡出现的错误日志，我们可在工程属性编辑禁用特定警告。

全角中文引号导致的错误

![image](https://bbs.kanxue.com/upload/attach/202306/871252_FTVPED8MKH4V49G.jpg)

解决办法就是在VS中剔除掉所有报错使用全角中文字符的位置。接下来frida-core应该不会遇到什么问题了。

接下来编译全部工程生成frida.dll，只要是frida.dll编译出来后，再出现error一律无视。

![image](https://bbs.kanxue.com/upload/attach/202306/871252_SURVAJJTENZBXW6.jpg)

生成目录在build/frida-windows/版本/bin。再window上编译frida除了再编译toolchain比较耗时外，其他还是很快的。编译出来的dll我们也只能再windows上使用，如果需要在android平台使用，我们需要在ubuntu下编译。

## 三.ubuntu20.4编译

        关于ubuntu如何安装在本小节中不在赘述，我们除了可以在vmware通过安装ubuntu来进行源码编译这种方式之外，还可以通过wsl安装ubuntu来进行编译。[使用WSL在windows上安装linux](https://learn.microsoft.com/zh-cn/windows/wsl/install)。使用WSL进行编译产生的错误请自行解决，不在本章讨论范围内。

### 3.1.编译环境

        编译前确认的环境

        1，ndkr25-linux版本

        2，nodejs

        3，python3.8

先执行编译手册提供给我们的安装环境命令：**sudo apt-get install build-essential curl git lib32stdc++-9-dev \
    libc6-dev-i386 nodejs npm python3-dev python3-pip**

然后clone frida源码:**git clone --recurse-submodules https://github.com/frida/frida.git**

### 3.2.开始编译

通过make命令来获取可编译版本的参数

例如，如果要编译在64位android平台下运行：**make frida-android-arm64**

ubuntu下编译frida不用预先编译toolchain和SDK。因为make执行的脚本会从网络上下载已经编译好的的toolchain和SDK。

我在ubuntu下只遇到这个错误，**Cannot load plugin "typescript": Not supported**

解决办法是更换nodejs版本(和win一致)来解决，也许是通过apt-get安装的nodejs版本较低的原因。

生成目录：frida/build/frida-android-arm64/bin

## 四.frida-tools安装

    frida-tools是安装frida在windows上执行的pyhon环境。如果你已经完成第二节**win编译，**那么你需要在frida-tools/agents/fs目录下执行npm install 和    npm run build两条命令，然后再frida-tools目录下执行python setup.py  install。通过pip list命令检查是否安装成功。

---

# 回复

## 回复 by 简单的简单 (#2)

*2023-6-12 21:52*

大佬搞个手工 patch 教程呗 ![image](https://bbs.kanxue.com/view/img/face/88.gif)

## 回复 by 秋狝 (#3)

*2023-6-13 09:52*

感谢分享

## 回复 by 快乐的小跳蛙 (#4)

*2023-6-13 09:55*

>
> [简单的简单](https://bbs.kanxue.com/user-950902.htm)
>
>  大佬搞个手工 patch 教程呗 [em_88]
>
>

还没看怎么用，刚搞明白编译

## 回复 by TUGOhost (#5)

*2023-7-2 19:12*

大佬，nodejs那块就直接下下来就行了？我本地是Ubuntu20编译frida16的版本，之前也编译过但是没遇到需要安装nodejs

## 回复 by TUGOhost (#6)

*2023-7-2 19:30*

没事了，我看了这个issue：https://github.com/frida/frida/issues/2325，解决了，更换nodejs版本即可，还有就是可能需要挂个代理，我在make core-android-arm 出现问题，挂了代理解决了，编译成功

## 回复 by TUGOhost (#7)

*2023-7-3 16:02*

大佬想请问下，在Windows下编译frida，如果安装的是社区版的Visual Studio是不是无法编译成功？我这边python .\releng\build-deps-windows.py 回显“ERROR: Visual Studio 2022 is not installed”，我看了下代码会执行build目录下的一个子目录底下的.\vswhere.exe -version 17.0 -format json -property installationPath ，我实际运行了下全是空的哪怕是.\vswhere.exe -all -format json也是空的

## 回复 by 快乐的小跳蛙 (#8)

*2023-7-4 10:32*

>
> [TUGOhost](https://bbs.kanxue.com/user-754019.htm)
>
>  大佬想请问下，在Windows下编译frida，如果安装的是社区版的Visual&nbsp;Studio是不是无法编译成功？我这边python&nbsp;.\releng\build- ...
>
>

我用的就是社区版本的vs2022，可以编译成功。如果你确认你的自定义python环境是正确的，你可以尝试使用开始界面中vs2022提供的交叉编译的命令行来执行build-deps-windows.py。
