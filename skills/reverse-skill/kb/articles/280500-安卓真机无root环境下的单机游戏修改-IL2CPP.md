---
title: '[原创]安卓真机无root环境下的单机游戏修改-IL2CPP'
url: https://bbs.kanxue.com/thread-280500.htm
tid: 280500
author: fu11p7r
date: '2024-02-11'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:32:43+08:00'
replies: 16
---

目录- 前言
- 准备工作
- 开始操作
- 注入 frida-gadget
- 介绍
- 安装 objection
- 全局安装
- 虚拟环境安装
- patch apk
- 安装测试
- frida-il2cpp-bridge
- 安装测试
- 开始修改
- 完结撒花
# 前言

之前在研究手游的il2cpp修改，选取了 `Mine Survival` 作为研究对象，由于手上没有root的机子，于是安装在了MuMu模拟器上

但是很快发现了问题，游戏只有arm的lib，由于一系列原因，导致我无法获取到 `libil2cpp.so` 的基址
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_2HAHEC8J25Y6S6B.webp)
在尝试了很多方法后都无法完美的解决这个问题，最终只能考虑安装在真机上了

但是目前并没有对机子root的打算，于是选取了注入 `frida-gadget` 的方案，这样没有root也可以对游戏进行修改了hhh

# 准备工作

基础工作不做过多介绍，学这个的应该都懂一点

我的设备

- 安卓真机 - Redmi Note 8
- 电脑 - Win10 专业版 22H2

推荐使用 [scrcpy](https://github.com/Genymobile/scrcpy) ，可以将手机画面投屏到电脑，延迟低

# 开始操作

## 注入 frida-gadget

### 介绍

可以手动操作去理解原理，参考这篇文章 [Using Frida on Android without root](https://koz.io/using-frida-on-android-without-root/)

当然我这种懒汉肯定是选用自动化方案啦，使用 [objection](https://github.com/sensepost/objection) 来自动化patch apk

### 安装 objection

- python版本 3.4+
- pip3版本 9.0+
- (可选)virtualenv版本 15+

#### 全局安装

| 1 | `$ pip3` `install` `-U objection` |
|-|-|

#### 虚拟环境安装

为了防止冲突，推荐安装在虚拟环境里

| 123456 | `# 创建虚拟环境``$ virtualenv myenv``# 激活虚拟环境``$ .\myenv\Scripts\activate``# 安装objection``$ pip3` `install` `-U objection` |
|-|-|

### patch apk

确定以下命令安装并且可用，将其添加到环境变量中

- aapt - <http://elinux.org/Android_aapt>
- adb - <https://developer.android.com/studio/command-line/adb.html>
- jarsigner - <http://docs.oracle.com/javase/7/docs/technotes/tools/windows/jarsigner.html>
- apktool - <https://ibotpeaches.github.io/Apktool/>

adb连接上安卓设备，执行下面的命令，就可以自动化的帮你patch好apk了

| 1 | `$ objection patchapk --``source` `'.\Mine Survival_v2.5.3.apk'` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_NWA4GRZYGK58HEU.webp)

### 安装测试

将`Mine Survival_v2.5.3.objection.apk`安装到手机

| 1 | `$ adb` `install` `'.\Mine Survival_v2.5.3.objection.apk'` |
|-|-|

然后执行一下 `frida-ps -U` ，有如下回显就是成功了

| 1234 | `$ frida-``ps` `-U``PID  Name``-----  ------``21709  Gadget` |
|-|-|

测试一下，写个获取 `libil2cpp.so` 基址的脚本

| 1234 | `Java.perform(``function``() {``var` `module = Process.getModuleByName(``"libil2cpp.so"``);``console.log(module.base);``})` |
|-|-|

注入js

| 1 | `$ frida -U Gadget -l .\hook.js` |
|-|-|

可以看到成功获取到了`libil2cpp.so`的基址
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_AHVJQNM7H5495JA.webp)

## frida-il2cpp-bridge

很好用，不多解释了

### 安装测试

执行下面的命令来安装 frida-il2cpp-bridge

| 1 | `$ npm` `install` `--save-dev frida-il2cpp-bridge` |
|-|-|

修改 `package.json`

| 12345678910 | `{``"main"``:` `"index.ts"``,``"scripts"``: {``"prepare"``:` `"npm run build"``,``"watch"``:` `"frida-compile index.ts -w -o hook.js"``},``"dependencies"``: {``"frida-il2cpp-bridge"``:` `"^0.9.0"``}``}` |
|-|-|

新建一个 `index.ts`，测试一下输出unity版本

| 12345 | `import` `"frida-il2cpp-bridge"``;` `Il2Cpp.perform(() => {``console.log(``"Unity version: "` `+ Il2Cpp.unityVersion);``});` |
|-|-|

执行 `npm run watch` 编译一下，然后再开个console执行 `frida -U Gadget -l .\hook.js`

可以看到成功输出了unity的版本
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_P5CYKZYMS8FU65E.webp)

### 开始修改

通过分析 `il2cppdumper` dump后得到的 `Assembly-CSharp.dll`，发现了 `Inventory` 这个类，可以看到他有一个 `AddItems` 的方法，那我们就可以想办法调用他来添加物品
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_KBTYTEUBWX4ZMBQ.webp)

现在来跟踪一下这个类

| 1234567891011 | `import` `"frida-il2cpp-bridge"``;` `Il2Cpp.perform(() => {``console.log(``"Unity version: "` `+ Il2Cpp.unityVersion);` `const AssemblyCSharp = Il2Cpp.domain.assembly(``"Assembly-CSharp"``).image``const Inventory = AssemblyCSharp.class(``"Inventory"``);` `Il2Cpp.trace(``true``).classes(Inventory).and().attach();` `});` |
|-|-|

拾取一个物品，可以看到他调用了 `Inventory::AddDropItem` 这个方法
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_BZENX44AHR936PN.webp)

那么就可以hook他来调用 `Inventory::AddItems`

| 12345678910111213141516171819 | `import` `"frida-il2cpp-bridge"``;` `Il2Cpp.perform(() => {``console.log(``"Unity version: "` `+ Il2Cpp.unityVersion);` `const AssemblyCSharp = Il2Cpp.domain.assembly(``"Assembly-CSharp"``).image``const Inventory = AssemblyCSharp.class(``"Inventory"``);``const AddDropItem = Inventory.method(``"AddDropItem"``);` `// Il2Cpp.trace(true).classes(Inventory).and().attach();` `AddDropItem.implementation =` `function` `(item): boolean {``// bool AddItems(int id, int amount)``this``.method(``"AddItems"``).invoke(115, 999);` `const result =` `this``.method<boolean>(``"AddDropItem"``).invoke(item);``return` `result;` `};``});` |
|-|-|

拾取物品，可以看到我们拥有了许多核导弹(喜)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202402/958990_EA8GUJF7Q7W85PC.webp)

# 完结撒花

感谢开源项目的维护者们

`frida-il2cpp-bridge` 还是很强大的，可以去学习一下

写的可能有点乱，有问题还请指出hh

---

# 回复

## 回复 by 秋狝 (#2)

*2024-2-11 21:30*

感谢分享

## 回复 by mb_ldbucrik (#3)

*2024-2-12 17:53*

谢谢分享

## 回复 by 你瞒我瞒 (#4)

*2024-2-19 16:52*

不错，但是图片很模糊

## 回复 by fu11p7r (#5)

*2024-2-20 16:34*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  不错，但是图片很模糊
>
>

下次注意![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by 路西菲尔lxfe (#6)

*2024-2-22 01:25*

感谢分享

## 回复 by 万里星河 (#7)

*2024-2-27 22:19*

mark

## 回复 by 司徒废人 (#8)

*2024-2-29 09:42*

大佬，能不能讲讲定位additems的过程![image](https://bbs.kanxue.com/view/img/face/27.gif)

## 回复 by fu11p7r (#9)

*2024-2-29 20:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  司徒废人](https://bbs.kanxue.com/user-641235.htm)
>
>  大佬，能不能讲讲定位additems的过程[em_27]
>
>

dump 后分析 Assembly-CSharp.dll，我是慢慢看过去的，看到Inventory类下的AddItems很容易想到这个就是添加物品到背包的方法了，调用验证一下就好啦

## 回复 by caolinkai (#10)

*2024-3-9 12:30*

感谢 分享

## 回复 by mb_pweuvgeh (#11)

*2024-3-19 10:53*

大佬，frida-il2cpp-bridge中如何打印变量是 System.Collections.Generic.List<实体类> list 的值呢？

## 回复 by IamHuskar (#12)

*2024-3-19 10:56*

有这么好的不用root的工具不早说。

## 回复 by fu11p7r (#13)

*2024-3-20 20:58*

>
> [mb_pweuvgeh](https://bbs.kanxue.com/user-990416.htm)
>
>  大佬，frida-il2cpp-bridge中如何打印变量是 System.Collections.Generic.List list 的值呢？
>
>

可以看一下wiki，或许对你有帮助
https://github.com/vfsfitvnm/frida-il2cpp-bridge/wiki

## 回复 by wx_kx64744 (#14)

*2024-4-13 16:41*

大佬，我附加脚本为什么Failed to attach: unable to connect to remote frida-server: closed，frida-ps -U也有回显，机型问题吗？

## 回复 by wx_范迪塞尔 (#15)

*2024-4-15 09:17*

有些游戏没法重新打包，会闪退或者重新打包失败

## 回复 by wx_kx64744 (#16)

*2024-4-16 20:02*

函数原型：public static string xxxxx (string input) {}
我的函数：xxxx可以获取到，但是hook时不执行；
xxxxx .implementation = function (str): Il2Cpp.String {}

## 回复 by l6031l (#17)

*2024-9-10 10:24*

遇到个问题, 在这里贴一个解决方案
如果在执行objection patchapk --source .\xxx.apk的时候遇到报错`UnicodeDecodeError: 'gbk' codec can't decode byte...`, 可以设置PYTHONUTF8=1后再运行
(注意powershell用的是$Env:  cmd用的是set)
