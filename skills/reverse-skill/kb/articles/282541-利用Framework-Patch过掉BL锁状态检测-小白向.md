---
title: '[原创]利用Framework Patch过掉BL锁状态检测（小白向）'
url: https://bbs.kanxue.com/thread-282541.htm
tid: 282541
author: sffool
date: '2024-07-17'
tags: [Android安全, 原创, 系统相关]
crawled_at: '2026-07-31T14:23:22+08:00'
replies: 23
---

# 介绍

该项目源自Github外国大佬
![image.png](https://bbs.kanxue.com/upload/attach/202407/988654_B5RKGB5M3USUBHB.jpg)
**项目链接：**
[GitHub - chiteroman/FrameworkPatch: Modify framework.jar to build on system level a valid certificate chain](https://github.com/chiteroman/FrameworkPatch)
在此声明，本教程也依托于Github项目上的教程和其他人发的教程，但后者这篇教程好像被原作者删除了。我也找不到了，无法提供相关信息，若原作者看到，请联系我补充。
PS：
原项目自带教程，但是只有英文版教程，并且教程详尽程度对我这样的小白不是很友好
所以写了这篇小白向的教程
大佬or有安卓开发经验的师傅可以直接看Github原项目

## 作用

对于已解锁BL的手机，这个项目通过对手机根目录下`/system/framework/framework.jar`这个文件进行修改来过掉BL锁状态检测
如果仅利用项目自带的keybox，可以过掉非硬件检测or密钥检测的BL锁状态验证，对付大部分软件，是没有问题的，而且目前有BL锁检测的软件其实很少。
如果你有谷歌下发的keybox，那么利用该项目，你可以近乎完美的过掉BL锁状态检测。
注意，对`TEE损坏`的手机没有效果！！！例如OPPO/一加等品牌手机，解锁BL就会使TEE假死。
本教程只有前者，就是教如何使用该项目。
我也不知道如何向谷歌申请下发keybox（我还是一个无安卓开发经验的小白）

## 存在的问题

- 目前检测BL的软件还是较少
- 完美隐藏BL状态需要谷歌下发的密钥
- 与`Kitsune Magisk`的`Su List`有冲突
- 和`Shamiko`模块有冲突
- 影响性能？
- 未知的问题

## 研究价值

目前，有些安卓游戏是存在检测BL状态的
以此为依据在设备上使用不同严格程度的检测方案
之后，或许会有更多的软件对BL锁状态进行检测
故，还是有一些研究价值

# 教程

**所需设备和工具：**

- 1台已Root的安卓手机（装有Magisk/Apatch等）
- Termux 或者 ZeroTermux
- MT管理器和密钥认证APP
- `Framework Patch` [Github链接](https://github.com/chiteroman/FrameworkPatch)及 `Framework Patcher Go`[GitHub链接](https://github.com/changhuapeng/FrameworkPatcherGO)
- Magisk模块模板`framework-modify`
- 科学上网

部分所需工具：
[百度网盘](https://pan.baidu.com/s/1LtwGXQn5NOYGoPuGIyq3fA?pwd=ew6v)
有FrameworkPatcherGO，模块模板，密钥认证APP
其他工具请自行准备

该教程内容不需要电脑就可以实现
Magisk模块模板我会提供附件（非本人制作）
**该项目有风险，请做好救砖的准备！！！**
**该项目有风险，请做好救砖的准备！！！**
**该项目有风险，请做好救砖的准备！！！**

## 内容预览

1. 配置Termux编译环境
2. 使用Termux编译所需`dex`
3. 利用`Framework Patcher Go`模块自动修改`framework.jar`中的`dex`（部分手机到此就已结束）
4. 手动修改`framework.jar`中的`dex`（部分手机的framework.jar无法使用`FrameworkPatcherGo`模块自动修改并安装）并制作模块

## 效果预览

![Screenshot_20240716-210903.png](https://bbs.kanxue.com/upload/attach/202407/988654_RVD2VZWBRRFV3RJ.jpg)![Screenshot_20240717-182045.png](https://bbs.kanxue.com/upload/attach/202407/988654_UKQFGTQJ3VEWTT6.jpg)
第一张图为安装前，第二张图为安装后（使用项目自带证书，故会显示来自AOSP的根证书，非完美隐藏）

## 配置Termux编译环境

### 换国内源

使用Termux执行

| 1234 | `sed` `-i` `'s@^\(deb.*stable main\)$@#\1\ndeb https://mirrors.tuna.tsinghua.edu.cn/termux/termux-packages-24 stable main@'` `$PREFIX``/etc/apt/sources``.list``sed` `-i` `'s@^\(deb.*games stable\)$@#\1\ndeb https://mirrors.tuna.tsinghua.edu.cn/termux/game-packages-24 games stable@'` `$PREFIX``/etc/apt/sources``.list.d``/game``.list``sed` `-i` `'s@^\(deb.*science stable\)$@#\1\ndeb https://mirrors.tuna.tsinghua.edu.cn/termux/science-packages-24 science stable@'` `$PREFIX``/etc/apt/sources``.list.d``/science``.list``pkg update` |
|-|-|

### 安装Java和配置Android编译环境

大量参考该文章[CSDN链接](https://blog.csdn.net/Mingyueyixi/article/details/136014207)（嘿，就是Copy）
如果之后想在手机上利用Termux编译APK项目的，推荐观看下

| 123456 | `#安装git``pkg` `install` `git -y``#安装openssh``pkg` `install` `openssh -y``#安装Java—sdk—17``pkg` `install` `openjdk-17 -y` |
|-|-|

请科学上网

| 123456789 | `curl -O https:``//googledownloads``.cn``/android/repository/commandlinetools-linux-11076708_latest``.zip` `ANDROID_HOME=~``/android/sdk``mkdir` `-p $ANDROID_HOME``/latest``unzip ```ls` `\|``grep` `"commandlinetools-linux.*_latest.zip"``` -d $ANDROID_HOME``# cmdline-tools 的产物需要移动到cmdline-tools/latest目录中，这是android sdk固定的路径组织形式``# 压缩包没有包含在latest文件夹中，自己移动一下``mv` `$ANDROID_HOME``/cmdline-tools/``* $ANDROID_HOME``/latest``mv` `$ANDROID_HOME``/latest` `$ANDROID_HOME``/cmdline-tools` |
|-|-|

MT管理器打开`/data/user/0/com.termux/files/home/`
创建文件，名字是`.bashrc`
填入以下内容

| 123456789101112 | `echo` `"用户："``$(``whoami``)` `if` `pgrep -x` `"sshd"` `>``/dev/null``then``echo``#echo "sshd运行中..."``else``sshd``echo` `"自动启动sshd"``fi``export` `ANDROID_HOME=~``/android/sdk``export` `PATH=$ANDROID_HOME``/cmdline-tools/latest/bin``:$PATH` |
|-|-|

Termux执行如下命令

| 12 | `cd` `~``source` `.bashrc` |
|-|-|

然后彻底关闭Termux，重新打开。
继续
由于我们只需要编译，故执行第三条命令即可

| 123456 | `#查看sdk列表``#sdkmanager --list``#安装安卓14平台开发工具``#sdkmanager --install "platforms;android-34"``#安装支持安卓14的构建工具``sdkmanager --``install` `"build-tools;34.0.0"` |
|-|-|

接下来，我们下载arm版本的sdk工具（google编译的安卓sdk没有arm版本 ）

| 1234567891011 | `cd` `~``curl -LJO https:``//github``.com``/lzhiyong/android-sdk-tools/releases/download/34``.0.3``/android-sdk-tools-static-aarch64``.zip` `#根据构架选择，一般用上面那个就行了，如果更改了，需要把解压命令也更改下``#curl -LJO https://github.com/lzhiyong/android-sdk-tools/releases/download/34.0.3/android-sdk-tools-static-arm.zip` `unzip android-sdk-tools-static-aarch64.zip -d .``/armtools``# 下载的是34版本的，所以，覆盖到34版本的目录``mkdir` `-p ~``/android/sdk/platform-tools``cp` `-p .``/armtools/build-tools/``*  ~``/android/sdk/build-tools/34``.0.0``cp` `-p .``/armtools/platform-tools/``*  ~``/android/sdk/platform-tools` |
|-|-|

git项目
注意科学上网

| 12 | `cd` `~``git clone https:``//github``.com``/chiteroman/FrameworkPatch``.git` |
|-|-|

## 编译dex

这里需要科学上网
并且，执行所需时间较长，耐心等待
最后，这里执行完了，还不算完
会有报错，请勿担心

| 1234 | `cd` `.``/FrameworkPatch``echo` `"sdk.dir=$ANDROID_HOME"` `>` `local``.properties``chmod` `+x .``/gradlew``.``/gradlew` `build` |
|-|-|

执行后，你会看到如下报错
![Screenshot_20240717-154206.png](https://bbs.kanxue.com/upload/attach/202407/988654_T2Z5T4223H32QUR.jpg)
不急，执行以下命令替换aapt2

| 1234 | `TARGET=``"/data/user/0/com.termux/files/home/.gradle/caches/transforms-4"``find` `"$TARGET"` `-``type` `f -name` `"aapt2"` `\|` `while` `read` `-r aapt2_file;` `do``cp` `-f ~``/android/sdk/build-tools/34``.0.0``/aapt2` `"$aapt2_file"``done` |
|-|-|

接下里继续编译

| 12 | `.``/gradlew` `assembleRelease``cp` `-f app``/build/intermediates/dex/release/minifyReleaseWithR8/classes``.dex ~` |
|-|-|

我们打开`/data/user/0/com.termux/files/home/`
就可以看到有一个dex文件，留着备用

## `Framework Patcher Go`模块自动修改

从`Framework Patcher Go`[GitHub链接](https://github.com/changhuapeng/FrameworkPatcherGO)上下载模块
MT管理器打开zip
将`classes.dex`添加到zip中的
`/META-INF/com/google/android/magisk/dex/`
文件夹下
然后Magisk刷入模块
它会自动修改系统自带的`framework.jar`中的`dex`
然后以面具模块的形式替换系统原来的`framework.jar`
PS：过程中需要按音量上下键的
![Screenshot_20240717-194948.png](https://bbs.kanxue.com/upload/attach/202407/988654_ZX68NVC7379PNUF.jpg)
**注意，注意，注意**
前面都是按音量上键
但到了最后
你看到

| 12 | `This step` `is` `not` `required unless your device crashes after installing this module.``Do you want to` `apply` `this step?` |
|-|-|

这两行英语后，请按音量下键
等待刷完
请提前做好救砖准备
如TWRP，音量键救砖模块等等

如果最后按音量下键后
是会卡开机页面的
则救砖

然后继续刷入模块
但在最后选择按音量上键

如果正常开机
那么到这里就结束了

但如果还是无法开机
那就只能手动修改`framework.jar`中的`dex`
请看接下来的教程

## 手动修改`framework.jar`

文件路径：`/system/framework/framework.jar`
复制文件到某个路径下
不要直接修改系统路径下的jar

MT管理器打开jar
`查看`——`Dex编辑器++`——`全选`
接下来

### **搜索方法名**：`engineGetCertificateChain`

在方法的末尾附近应该有如下几行代码：

| 123 | `const``/``4` `v4,` `0x0``aput``-``object` `v2, v3, v4``return``-``object` `v3` |
|-|-|

类似结构，但寄存器的值可能是不一样的
如图
![Screenshot_20240717-191030.png](https://bbs.kanxue.com/upload/attach/202407/988654_8DDKM5BA67PB93M.jpg)
我们在`return-object XX`前加入

| 12 | `invoke``-``static {XX}, Lcom``/``android``/``internal``/``util``/``framework``/``Android;``-``>engineGetCertificateChain([Ljava``/``security``/``cert``/``Certificate;)[Ljava``/``security``/``cert``/``Certificate;``move``-``result``-``object` `XX` |
|-|-|

将 `XX` 替换为对应的值
如图
![Screenshot_20240717-191603.png](https://bbs.kanxue.com/upload/attach/202407/988654_RD35AWVC7JVGXQU.jpg)
保存返回

### **搜索方法名：**`newApplication`

可以看到有两个结果
我们先点开第一个
如图
![Screenshot_20240717-192134.png](https://bbs.kanxue.com/upload/attach/202407/988654_4JDNE7XZBCPFB22.jpg)
存在类似代码

| 1 | `.param XX，``"context"` `#Landroid/content/Context;` |
|-|-|

在方法末尾`return` 之前添加以下代码：

| 1 | `invoke``-``static {XX}, Lcom``/``android``/``internal``/``util``/``framework``/``Android;``-``>newApplication(Landroid``/``content``/``Context;)V` |
|-|-|

将 `XX` 替换为寄存器。
如图
![Screenshot_20240717-192220.png](https://bbs.kanxue.com/upload/attach/202407/988654_VKVU7F533FQDCQP.jpg)
保存，看第二个搜索结果
如图
![Screenshot_20240717-192532.png](https://bbs.kanxue.com/upload/attach/202407/988654_PHP4G3KS8D6H32Y.jpg)
看到和刚刚不同
有p1，p2，p3
我们还是和第一个一样
选择绿色高亮文本为`context`的那一行对应的寄存器
在方法末尾`return` 之前添加以下代码：

| 1 | `invoke``-``static {XX}, Lcom``/``android``/``internal``/``util``/``framework``/``Android;``-``>newApplication(Landroid``/``content``/``Context;)V` |
|-|-|

将 `XX` 替换为寄存器
如图
![Screenshot_20240717-194350.png](https://bbs.kanxue.com/upload/attach/202407/988654_8RQ7F9D9AVVZQAM.jpg)
保存返回

### **搜索方法名：**`hasSystemFeature`

结果有很多
我们只看`ApplicationPackageManager`类下的第一个
如图
![Screenshot_20240717-195633.png](https://bbs.kanxue.com/upload/attach/202407/988654_ZTEZNP44Z7YEPYE.jpg)
在方法末尾`return` 之前添加以下代码：

| 12 | `invoke``-``static {v0, p1}, Lcom``/``android``/``internal``/``util``/``framework``/``Android;``-``>hasSystemFeature(ZLjava``/``lang``/``String;)Z``move``-``result v0` |
|-|-|

如寄存器有不同，请自行更改，和之前一样就行
如图
![Screenshot_20240717-200049.png](https://bbs.kanxue.com/upload/attach/202407/988654_3AUQCAWCFF2WQUG.jpg)
保存返回
保存并退出
在压缩文件中更新

### 利用模板制作模块

找到我们之前编译的dex
如图
![Screenshot_20240717-200316.png](https://bbs.kanxue.com/upload/attach/202407/988654_2TRBR9HMKB9SM7X.jpg)
根据`framework.jar`中dex的数量`n`个
重命名编译好的dex为classes[n+1].dex
然后添加到`jar`内
如图
![Screenshot_20240717-200609.png](https://bbs.kanxue.com/upload/attach/202407/988654_7DR598CXCXAHTDW.jpg)
保存返回

找到Magisk模块模板`Frist-framework-modify`
注意最开始，选择带`Frist`的
将修改后的`framework.jar`添加到压缩包`/system/framework/`下
然后利用面具刷入，重启

能开机，结束
不能开机
选择不带`Frist`的`framework-modify`模板
将修改后的`framework.jar`添加到压缩包`/system/framework/`下
然后利用面具刷入，重启

>
> 带Frist和不带的区别：
> 其实就和Framework Patch Go模块一样
> 带Frist的模块和Go模块最后按音量下键的不会执行下列代码
> 而不带Frist和Go模块最后按音量上键的会执行
>
>
>

| 1234567891011 | `if` `[` `"$BOOTMODE"` `] && { [` `"$KSU"` `] \|\| [` `"$APATCH"` `]; }; then``find` `"/system/framework"` `-``type` `f` `-``name` `'boot-framework.*'` `-``print0 \|``while` `IFS``=` `read` `-``r` `-``d '' line; do``mkdir` `-``p` `"$(dirname "``$MODPATH$line``")"` `&& mknod` `"$MODPATH$line"` `c` `0` `0``done``elif` `[` `"$BOOTMODE"` `] && [` `"$MAGISK_VER_CODE"` `]; then``find` `"/system/framework"` `-``type` `f` `-``name` `'boot-framework.*'` `-``print0 \|``while` `IFS``=` `read` `-``r` `-``d '' line; do``mkdir` `-``p` `"$(dirname "``$MODPATH$line``")"` `&& touch` `"$MODPATH$line"``done``fi` |
|-|-|

如果刷入后还是无法正常开机
只能先救砖
再向项目作者提交issue了

# 结语

本篇文章基本上是对原项目作者的教程进行翻译，简单化，和补充
希望未来可以写出更高质量的文章

在看雪的第一篇文章Over
未来待续

---

# 回复

## 回复 by 珍惜Any (#2)

*2024-7-18 10:38*

真麻烦，你直接说hook system_server哪个方法就行了。framework.jar就是系统服务用的。

## 回复 by sffool (#3)

*2024-7-18 10:47*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  真麻烦，你直接说hook system_server哪个方法就行了。framework.jar就是系统服务用的。
>
>

大牛，我不会![image](https://bbs.kanxue.com/view/img/face/47.gif)

## 回复 by 珍惜Any (#4)

*2024-7-18 10:51*

>
> [sffool](https://bbs.kanxue.com/user-988654.htm)
>
>  大牛，我不会[em_47]
>
>

哈哈哈哈 我看你那个github了 ，这个老外和之前挺火那个BootloaderSpoofer作者是同一个 。我今天看看这块，如果能搞成xp模块，直接在系统服务hook就好了。

## 回复 by sffool (#5)

*2024-7-18 10:58*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  哈哈哈哈 我看你那个github了 ，这个老外和之前挺火那个BootloaderSpoofer作者是同一个 。我今天看看这块，如果能搞成xp模块，直接在系统服务hook就好了。
>
>

好的，大牛
关注你了，期待![image](https://bbs.kanxue.com/view/img/face/3.gif)

## 回复 by 你瞒我瞒 (#6)

*2024-7-18 15:11*

感谢，很详细

## 回复 by Aimees (#7)

*2024-7-18 15:24*

费老大劲看了半天，这个手机的截图也太大了，建议这块简明扼要一些，直接找到哪个类 哪个函数，修改或者patch哪些点就行了，也可以转换成frida代码

## 回复 by New对象处 (#8)

*2024-7-18 15:24*

“在 Android Studio 中打开此项目并更改 EC 和 RSA 密钥，您必须提供密钥箱私钥。编译为 release 并复制 classes.dex 文件。”这句话很关键，之前有个卖秘钥提供xposed插件做验证，代码跟这个差不多，秘钥哪搞是个问题

## 回复 by New对象处 (#9)

*2024-7-18 15:26*

具体为什么开不了机，可以尝试下删除framework.jar 生成的一些odex 文件，现在的设备都有签名校验了

## 回复 by sffool (#10)

*2024-7-18 16:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  “在 Android Studio 中打开此项目并更改 EC 和 RSA 密钥，您必须提供密钥箱私钥。编译为 release 并复制 classes.dex 文件。”这句话很关键，之前有个卖秘钥提供x ...
>
>

关键就是keybox密钥，需要谷歌下发。这方面我还不是很了解

## 回复 by sffool (#11)

*2024-7-18 16:09*

我在语雀上是可以缩小图片的
但导出MD格式，然后再导入到看雪里面调整不了大小
或者是我操作姿势有问题

## 回复 by sffool (#12)

*2024-7-18 16:34*

>
> [Aimees](https://bbs.kanxue.com/user-978841.htm)
>
>  费老大劲看了半天，这个手机的截图也太大了，建议这块简明扼要一些，直接找到哪个类 哪个函数，修改或者patch哪些点就行了，也可以转换成frida代码
>
>

小白向，故还是配上了图

## 回复 by 菱志漪 (#13)

*2024-7-19 10:11*

希望国内也能早日大规模实现后台类似谷歌play integrity的保护

## 回复 by mb_fidppcok (#14)

*2024-7-22 09:49*

这个重新编译的jar 只能给AOSP系统 ？像国内的ROM 也能是一样的方法？

## 回复 by sffool (#15)

*2024-7-23 09:12*

>
> [mb_fidppcok](https://bbs.kanxue.com/user-986312.htm)
>
>  这个重新编译的jar 只能给AOSP系统 ？像国内的ROM 也能是一样的方法？
>
>

不是
是里面的keybox密钥盒是aosp的
只要你有谷歌下发的密钥盒就能过掉这个
但目前，一般人很难获取到密钥盒

## 回复 by Thehepta (#16)

*2024-7-25 13:40*

就你这个图片，加手机编辑，是个狠人

## 回复 by StarsunYzL (#17)

*2024-7-25 20:16*

太麻烦了，这玩意感觉主要是为了过Google Play Integrity检测，单独检测BL锁的似乎不多，但有Google Play Integrity检测的App就多了去了，但还是太麻烦了，直接BootloaderSpoofer能用就用，不能用就Shift+Del![image](https://bbs.kanxue.com/view/img/face/28.gif)

## 回复 by 养只猫不好么 (#18)

*2024-8-6 11:59*

感谢分享

## 回复 by crosscc (#19)

*2024-9-27 18:43*

感谢分享

## 回复 by 陈某人 (#20)

*2024-11-10 21:59*

感谢分享

## 回复 by 鸿蒙时空 (#21)

*2025-3-4 10:07*

keybox秘钥盒我有啊

上传的附件：
- 还没有吊销的key，小石付费购买给大家免费使用，.zip

（7.87kb，111次下载）

## 回复 by mb_cplwkbmk (#22)

*2025-8-18 18:38*

为啥我安装编译工具的时候会报错
sdkmanager command not found

## 回复 by 恋一世的爱 (#23)

*2025-8-19 19:36*

改完后，微信可以指纹付款吗

## 回复 by mb_wobirpwx (#24)

*2025-8-29 08:09*

cd ~
git clone https://github.com/chiteroman/FrameworkPatch.git
这个里的链接挂掉了 导致一直弄不好 希望作者快更新一下
