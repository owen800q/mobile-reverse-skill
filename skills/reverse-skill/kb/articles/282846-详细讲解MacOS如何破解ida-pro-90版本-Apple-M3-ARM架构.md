---
title: '[原创]详细讲解MacOS如何破解ida-pro-90版本（Apple M3 ARM架构）'
url: https://bbs.kanxue.com/thread-282846.htm
tid: 282846
author: 小黑学逆向
date: '2024-08-10'
tags: [Android安全, 原创, 基础理论, 工具脚本, 其他]
crawled_at: '2026-08-11T08:44:48+00:00'
replies: 13
---

## MacOS中如何破解ida-pro-90版本（Apple M3）

>
> 说明一下，写这篇文章纯属是正打算学安卓逆向，朋友给我发了个文件说是好东西，然后让我自己看着破解。破解出来后朋友说网上教程比较少，让我写篇文章出来（也不知道大家会不会，我自己百度的时候是没看到几篇文章）。PS：本来就是一个小白，文章中写得不对的地方还请大佬指点
>
>
>

ps：这里提醒一下，我本来试过每次安装都要重新生成patched文件

## 1. 环境\文件准备

### 1.1. ida90文件

| 12 | `1. idapro_90_armmac.app.zip   安装包``2. crack_ida90_beta.py        生成密钥、破解文件的脚本` |
|-|-|

### 1.2. python环境

在安装ida90的时候，提示需要python3.4或者更高的版本，如果你的电脑没有的话就自己安装升级一下吧，这里不放升级\安装python的教程（因为我也不会）

### 1.3. 关闭sip

在你的终端中输入`csrutil status`。显示：`System Integrity Protection status: disabled.`。那么你可以直接忽略这一步进入到下面的安装环节了
 ![sip状态](https://bbs.kanxue.com/upload/attach/202408/1002807_2GBV7HYXECP2EWW.webp)

#### 1.3.1如何关闭SIP

1. Apple Silicon Mac 在关机时按住电源按钮（大约10 秒）。
2. 然后转到“选项”。您可能需要管理员密码。
3. 输入解锁密码后，在左上角点击实用工具并点击终端
4. 终端内输入命令：`csrutil disable`，然后回车执行输入电脑密码。
5. 提示输入y/n，输入y。回车后输入电脑密码
6. 等待一段时间，大概几秒左右。提示完成后重启电脑就好了

>
> 如果关闭sip有问题的话可以百度一下，其实教程很多也很详细。这里写一下只是为了让这篇文章看起来字多一些。
>
>
>

## 2. 进入到安装ida-pro90的步骤了

### 2.1. 第一步，解压`idapro_90_armmac.app.zip`得到`idapro_90_armmac`文件

 ![文件解压](https://bbs.kanxue.com/upload/attach/202408/1002807_NTAP8UV8496C74A.webp)

#### 2.2 双击打开`idapro_90_armmac`进入到安装界面

>
> 这里可能会有一个小插曲，就是不让你打开这个文件。提示：apple无法检查其是否包含恶意软件（图片网上找的，我自己的没截图）
> ![无法安装idapro—90](https://bbs.kanxue.com/upload/attach/202408/1002807_CS7Y8FH95HZXAGM.webp)
> 解决方法：打开设置->隐私与安全性->安全性->允许打开这个文件。然后再打开这个文件就行了
>
>
>

### 2.3 一直点Next，直到出现这个界面

>
> ps: 这个时候不要着急打开软件嗷。还要进行一些文件的替换以及删除
>  ![安装完成了](https://bbs.kanxue.com/upload/attach/202408/1002807_W8BKGRSHT7W6P69.webp)
>
>
>

## 3. 开始patch

这个时候`crack_ida90_beta.py`文件就派上用上咯。需要将默认的`libida.dylib`、`libida.dylib`文件替换

### 3.1 生成.patched文件

1. 拿到ida安装目录下的`libida.dylib`、`libida.dylib`文件。与`crack_ida90_beta.py` 文件放在同一个目录下。ida默认安装目录是：/Applications/IDA Professional 9.0.app/Contents/MacOS/
 ![准备生成patched文件](https://bbs.kanxue.com/upload/attach/202408/1002807_U6G9XST4PE483UD.webp)
2. 使用python3命令执行`crack_ida90_beta.py`脚本
 ![执行py脚本](https://bbs.kanxue.com/upload/attach/202408/1002807_BF5SB637FSNFUE5.webp)
这里就提示.patched文件生成完成了。上面的dll、so文件没有生成不需要关心，那个是linux和win系统需要使用的
3. 执行后会生成`idalic.hexlic`、`libida.dylib.patched`、`libida64.dylib.patched`三个文件
 ![执行py脚本后的文件列表](https://bbs.kanxue.com/upload/attach/202408/1002807_6ZFGXPSA9TUCZCW.webp)
4. 将`idalic.hexlic`许可证文件复制到`$home/.idapro`目录下。如果不知道`$home`目录在哪里可以使用`echo $home`打印出来。这是讲ida.hexlic复制到`$home/.idapro`目录下的结果
 ![执行py脚本后的文件列表](https://bbs.kanxue.com/upload/attach/202408/1002807_XBW62NF2VCGW2ZV.webp)
5. 将libida.dylib.patched、libida64.dylib.patched替换掉安装目录下默认的libida.dylib、libida64.dylib文件。这里就不放图了，应该都能完成吧

到这里你的ida就破解完成了。
 ![安装成功界面图](https://bbs.kanxue.com/upload/attach/202408/1002807_3SMXAJPKPEYF3H4.webp)
 ![安装成功界面图](https://bbs.kanxue.com/upload/attach/202408/1002807_QG2YAY3RZGJRNZ7.webp)

ps ：许可证文件路径是可以修改的。默认是在`$home/.idapro`目录
 ![可以选择ida.hexlic文件](https://bbs.kanxue.com/upload/attach/202408/1002807_RXCFQHR6DJNK5UV.webp)

## 4. 打开安装好的IDA，发现还是有问题

### 问题1：软件崩溃了。

>
> 提示：System Integrity Protection Enable。这个问题就是没有将SIP机制关闭，回到上面的教程把SIP关闭就行了
>
>
>

### 问题2：Oops! internal error 30016 occurred

>
> 这个问题不知道是不是只有我才出现了。太恶心了这个问题
> 解决方法就是将`/Applications/IDA Professional 9.0.app/Contents/MacOS/plugins/arm_mac_user64.dylib`文件去除就行了。
> 这里我没有删除，而是将`arm_mac_user64.dylib`文件名称修改为：`arm_mac_user64.dylib.bak`防止后面需要使用到
>
>
>

后续各位大佬碰到其他问题的话也可以补充的

上传的附件：
- crack_ida90_beta.py

（6.45kb，551次下载）

---

# 回复

## 回复 by kkHAIKE (#2)

*2024-8-12 10:23*

这个版本是不是还没有任何插件泄漏

## 回复 by 小黑学逆向 (#3)

*2024-8-12 11:39*

>
> [kkHAIKE](https://bbs.kanxue.com/user-148805.htm)
>
>  这个版本是不是还没有任何插件泄漏
>
>

应该是吧，还没有了解过。目前还没有学到使用这个工具的阶段

## 回复 by zulkar_Lab (#4)

*2024-11-13 10:58*

Python SDK配置
1.the `idalib/python` folder run: pip install .
2.python py-activate-idalib.py
后可以在外部python解释器上调用idaapi
但是在IDA内部就无法使用idaapi了
具体报错如下：
Python>import ida
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/xxx/Library/Python/3.9/lib/python/site-packages/ida/__init__.py", line 60, in <module>
    raise IdalException("Cannot run IDALIB in interactive mode.")
ida.IdalException: Cannot run IDALIB in interactive mode.
大佬们这个问题该怎么解决

## 回复 by bluegatar (#5)

*2024-11-13 13:54*

不错的初学项教程

## 回复 by Payne-Wu (#6)

*2024-11-13 15:30*

rm

## 回复 by yaoqianshuj (#7)

*2025-3-13 17:48*

求教一下，有windows下的教程么

## 回复 by mb_lcxkqdzz (#8)

*2025-3-17 10:14*

大佬，LIcense manager的时候报错识别不出license怎么办，有没有人遇到过T_T![image](https://bbs.kanxue.com/view/img/face/006.gif)
Could not load licenses: Signature decryption failed with code: -2

## 回复 by 小黑学逆向 (#9)

*2025-4-1 10:10*

不关闭spi就把需要删除的内容重新签名

## 回复 by 0x7 (#10)

*2025-6-19 16:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_lcxkqdzz](https://bbs.kanxue.com/user-1027191.htm)
>
>  大佬，LIcense manager的时候报错识别不出license怎么办，有没有人遇到过T_T[em_006]
> Could not load licenses: Signature decrypt ...
>
>

遇到了，解决了吗？

## 回复 by 咕嘎咕嘎 (#11)

*2026-2-6 00:10*

Termination Reason:    Namespace CODESIGNING, Code 2 Invalid Page

VM Region Info: 0x1055c44b0 is in 0x1051bc000-0x105690000;  bytes after start: 4228272  bytes before end: 834383
      REGION TYPE                    START - END         [ VSIZE] PRT/MAX SHRMOD  REGION DETAIL
      __LINKEDIT                  104e58000-1051bc000    [ 3472K] r--/rwx SM=COW  /Applications/IDA Professional 9.0.app/Contents/Frameworks/QtGui.framework/Versions/5/QtGui
--->  __TEXT                      1051bc000-105690000    [ 4944K] r-x/rwx SM=COW  /Applications/IDA Professional 9.0.app/Contents/MacOS/libida64.dylib
      __DATA_CONST                105690000-1056ac000    [  112K] r--/rw- SM=COW  /Applications/IDA Professional 9.0.app/Contents/MacOS/libida64.dylib
我的崩溃了

## 回复 by 咕嘎咕嘎 (#12)

*2026-2-25 19:16*

debug 一直
./android_server64
IDA Android 64-bit remote debug server(ST) v9.0.30. Hex-Rays (c) 2004-2024
2026-02-25 19:09:05 Listening on 0.0.0.0:23946...

Error: Oops! internal error 30016 occurred.
有大佬帮忙解决嘛。。。。。

## 回复 by en0th (#13)

*2026-4-21 16:31*

>
> [mb_xaxehsrw](https://bbs.kanxue.com/user-1058587.htm)
>  debug 一直
> ./android_server64
> IDA Android 64-bit remote debug server ...
>

我也遇到了这个问题，请问解决了吗？

## 回复 by en0th (#14)

*2026-4-21 16:34*

在上文找到解决方案了
