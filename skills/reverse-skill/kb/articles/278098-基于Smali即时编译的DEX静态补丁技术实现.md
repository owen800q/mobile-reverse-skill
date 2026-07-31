---
title: '[原创]基于Smali即时编译的DEX静态补丁技术实现'
url: https://bbs.kanxue.com/thread-278098.htm
tid: 278098
author: gjden
date: '2023-07-20'
tags: [Android安全, 原创, 基础理论, 逆向分析, 其他]
crawled_at: '2026-07-31T14:41:08+08:00'
replies: 41
---

时常有人建议实现一个能对APK进行修改和重打包的功能，其实可以实现重打包的工具不少，想来也是多此一举，因此长时间没有搭理。直到前一段时间，有小伙伴反馈重打包某APP，始终失败，几乎放弃，原因是DEX中出现了很多非法花指令，他解包时所有的DEX都需要反编译，由于非法指令太多，回编译后的APK始终无法正常使用。随着字节码指令级的对抗升级，这种问题或许会越来越普遍。针对这种问题，最终极的解决方法就是不反编译，直接给DEX文件中的指令打补丁，但其中牵扯到指令格式、局部寄存器、各种索引问题需要解决，并非易事。因此为了实现这种解决方法，便有了本文，这种技术我称为“smali即时编译静态补丁技术”：无需采用传统反编译手段对整个APK进行反编译后做代码修改工作，仅仅针对某一条或多条smali指令进行修改并将修改指令直接patch到DEX文件中，也不需要对所有代码做二次编译。

**Contribution:**

- **实现全新轻量级smali编译器LiteSmali**
- **指令语法****提示器**
- **花指令清除器**
- **广谱匹配的花指令全局识别器**

**下载地址：**

[github.com](https://github.com/charles2gan/GDA-android-reversing-Tool)

[GDA主页-亚洲首款现代交互式Android反编译器](http://www.gda.wiki:9090/)

演示：

1、修改DEX文件中的字符串

 ![image](https://bbs.kanxue.com/upload/attach/202307/302697_7UHMURM3ZNRZHGN.gif)

2、 修改跳转指令吐出Flag：

![image](https://bbs.kanxue.com/upload/attach/202307/302697_YHZC4H2XCKSTGZM.gif)

## 一、简述

为了实现APK的插桩和修改，通常做法是使用backsmali工具将目标DEX/APK反汇编成为smali代码文件，然后搜索要修改的文件并对感兴趣的smali代码进行修改，完成代码修改后再通过smali工具将其编译回去（其他集成这些核心工具的软件底层原理也类似）。我们知道一款商业化的APP，其内部可能包含着上万个类以及上千万级的字节码指令，这里面存在着各种对抗的可能性，这些对抗手段极容易导致类似于apktool/backsmali/smali工具在工作过程中出现错误。尤其在处理一些被加固保护过的APP，或者被混淆或者采用了各种对抗手段的APP时，错误率会显著提高，哪怕只要有一个小段代码处理不当，或者某一个需要反编译的文件（DEX文件/XML文件/资源文件）无法正常反编译，就会导致整个插桩或patch过程失败。

因此，实现一种直接对DEX文件打补丁的技术能够很好简化整个过程，避免这类情况的出现。直接补丁技术可以完全脱离一系列工具链的依赖，同时也不需要反编译和编译整个APK文件及其内部文件（包括XML文件、资源文件、DEX文件等等），节省了系统开销、简化了patch过程、避免了不可期的错误。

本文旨在介绍新版GDA反编译器中引入的一种可以直接对DEX文件进行smali代码级patch的技术，并通过一些简单的例子来分享其使用方法。即使你不熟悉smali也能够方便的自定义自己的代码，并通过简单的操作就能够将所有修改内容方便地回写到APK文件中，并自动实现APK的签名和安装。你可以一边修改代码，一边查看执行结果。

注意： 由于修改后APK需要签名，因此我不得不引入apksinger.jar，所以需要你系统中有java环境，如果GDA自带的签名工具签名失败，你可以用自己的签名工具对未签名成功的APK进行签名。

![image](https://bbs.kanxue.com/upload/attach/202307/V8AE9QY6Z7JMVMT.jpg)

## 二、实现原理

         我们这里谈及的DEX Patch实际上指的是对类的方法代码进行修改，直接对字节码做修改并不是我们期望的目标，因此这里实现的要求是对任意位置的二进制数据实现smali输入、smali编译和字节码生成，最后将生成的字节码回写到dex文件中。

                                                                                                    ![image](https://bbs.kanxue.com/upload/attach/202307/302697_BZVA4HHF6P2ZRCH.jpg)

原理其实很简单，这整个过程最核心最难的部分就是smali编译器，常规smali编译器其实并不满足我的需求：一则类似于smali这样开源编译器（准确说叫汇编器）大而复杂；我这里是需要严重依赖DEX文件来生成字节码，其中class descriptor, method index, field index, string index这些都需要从DEX文件中去提取；三则是smali编译器很难去完成独立于上下文的单个smali编译的工作。因此再造轮子长远来看更划算，而且通过c++实现能够能够更好的和GDA的GUI交互，效率更高也更容易维护。于是，一个可逐条编译且上下文无关的smali编译器诞生了，这是一个非常轻量级的smali编译器，没有庞大的词法/语法器。我将其命名为LiteSmali。

当然，有了LiteSmali还远远不够，要做好与GDA反编译器之间的交互以及与Android设备交互，还需要做大量的工作比如smali指令实时提示、批量编译、DEX回写、校验签名以及APK安装。为了延续GDA原有的代码编辑，单个指令编辑依然放到smali文本框中实现，当然也提供批量smali代码的输入，并且实现从指令修改到APK安装的一站式操作，简化了代码patch到代码执行的过程。整个patch和运行的过程不需要任何第三方工具介入。GDA的liteSmali支持的交互操作如下：

1)       Smali指令自动提示：支持所有smali指令的实时格式提示（包括指令、操作码、寄存器）

2)       对象自动提示：根据你的输入，程序从当前dex空间中搜索可用的对象给你使用，其中包括string, class/type, method,field.

3)       一键patch: 通过回车键实时将smali代码patch回代码中

4)       字符串patch:可以对dex中的字符串进行修改

5)       DEX自动校验：修改完后，自动更新DEX文件的signature和checksum。

6)       回写DEX到APK并自动签名：一键实现将已修改的DEX文件回写到APK文件中，通过GDA自带的证书文件或自定义的证书对APK文件进行签名。

##

## 三、使用方法

这里我以一个crackme为例介绍该功能如何使用，该crackme是一个以输入密码释放正确来弹出flag的程序。该APK来自github，我把这个crackme放在本文的附件中。这是一个非常简单的crackme，本文主要用来演示如何编辑指令。

### 1、  破解crackme演示

![image](https://bbs.kanxue.com/upload/attach/202307/302697_GKTZ5TWCJB5EGGT.gif)

在上述动画里，鼠标单击你所需要编辑的指令，按M键，该指令的smali代码便会显示在右上角smali编辑框中，编辑好后按下回车键生效，GDA会patch内存中DEX文件，同时会自动获取下一条指令等待你的编辑，如果不需要忽略即可。最后，你可以按下R键将修改后的DEX文件保存到磁盘中同时更新checksum和signature，然后回写到原APK文件中，最后签名APK并安装到Android设备中。

### 2、  编辑以及恢复任意smali

如果想返回编辑前的文件，你可以通过CTRL+Z恢复上一次编辑的指令。下图中，首先连续编辑几条指令后，通过快捷键逐条恢复指令。

     ![image](https://bbs.kanxue.com/upload/attach/202307/302697_8HNB27A92PZ4EWP.gif)

###     3、批量编译smali

如果你想将多条smali代码一次性的写入DEX文件中，你可以首先将代码写如文件中，然后右键菜单->Multi-Dex Edit，导入你的文件，进行编辑，注意：smali代码支持的格式包含如下三种情况：

1）  纯smali代码

2）  带偏移的smali代码

3）  带字节码的smali代码

对于跳转指令，你需要在GDA中修正跳转偏移地址

 ![image](https://bbs.kanxue.com/upload/attach/202307/302697_7EK7Y63N2J4GJJ9.gif)

### 4、函数调用注意事项

在函数调用时应该注意，你要调用的方法是否是私有方法，虽然GDA能够编译通过，但是你无法启动APP。

 ![image](https://bbs.kanxue.com/upload/attach/202307/Z64Z4BP3MDUCP6F.jpg)

### 5、关于构造smali shellcode

虽然直接编辑DEX文件无法引入新的字符串和API，但如果我们选取一个空间足够的方法来引入，也是可行的。具体做法也很简单，我们通过建立一个数组，将字符串逐个填充即可，如果是API也可以先填充APK字符串，然后通过反射调用来实现。最后提取出shellcode字节码即可，以下是我构造的一段shellcode代码。

   [![image](https://bbs.kanxue.com/upload/attach/202307/6YC5M2SBMXFCD72.jpg)](https://github.com/charles2gan/GDA-android-reversing-Tool)

### 6、关于花指令清除与恢复

GDA的花指令清楚有两种方式，一种是直接对选择的指令行进行nop，可以通过CTR+Z恢复，一种是通过广谱匹配的方式实现进行指令清除，可以在右键菜单中恢复。

                                ![image](https://bbs.kanxue.com/upload/attach/202307/302697_NGJPHXA7VT4QC39.gif)              上面动画演示直接NOP掉你所识别出来的花指令，花指令清楚后，反编译代码恢复正常。

  通过广谱匹配清除所有花指令，需要编辑匹配规则，注意确认生效后，当前页面需要刷新以后才能看到。

![image](https://bbs.kanxue.com/upload/attach/202307/VQJ8BHGRYC966R5.jpg)

其中规则中两个问号代表一个任意字节匹配，通过大括号来指定任意值的长度，规则非常简单易用。如 1a05??{2}6e101b??{3} 可以匹配如下指令：

![image](https://bbs.kanxue.com/upload/attach/202307/PTYJEGBPH6BA5NU.jpg)

每个匹配都会保存在Junk Manager中，你可以点击每个规则以恢复被该规则清除的指令，如图。

![image](https://bbs.kanxue.com/upload/attach/202307/QKUK2VD5PMCA8PX.jpg)

7、恢复所有被编辑过的DEX到原始DEX

如果需要将所有修改一次性恢复到原始状态，可以通过点击菜单栏中的如下菜单实现。

![image](https://bbs.kanxue.com/upload/attach/202307/PTQJS6FCGX9HN4U.jpg)

## 四、总结

  当然，基于DEX文件的代码编辑，并不是那么完美，依然有很多限制，比如难以引入新的字符串和API，许多资源受限于DEX本身，不管如何这也是一项值得尝试的技术，比如构造shellcode等等，正是得益于GDA反编译器保留指令级别的特性，使得该技术得以实现和应用，使用如有问题，可以到GDA的github主页去留言反馈问题，同时希望小伙伴们start我的GDA反编译器项目。

   欢迎star: [GDA github](https://github.com/charles2gan/GDA-android-reversing-Tool)

上传的附件：
- app.apk

（1.21MB，34次下载）

---

# 回复

## 回复 by hackings (#2)

*2023-7-20 16:27*

G神太牛逼了！！！！！！

## 回复 by SomeMx (#3)

*2023-7-20 16:36*

牛的![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by method (#4)

*2023-7-20 16:37*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by gjden (#5)

*2023-7-20 17:14*

**今年是我写GDA反编译器的第10个年头，纪念以下，同时感谢看雪的小伙伴们，我与你们同在，哈哈。**

![image](https://bbs.kanxue.com/upload/attach/202307/S8M42PJ5BPAZAAZ.jpg)

一直都有人问我写这个赚不赚钱，说实话没钱挣，但是传播广了说不定会遇到有这样的运气，同时感谢西班牙土豪的捐赠。此前截图放错成了一张订单截图。

![image](https://bbs.kanxue.com/upload/attach/202307/302697_AYUAXFCNBEVH9KR.jpg)

## 回复 by kanxue666 (#6)

*2023-7-20 17:16*

>
> [gjden](https://bbs.kanxue.com/user-302697.htm)
>
>  今年是我写GDA反编译器的第10个年头，纪念以下，同时感谢看雪的小伙伴们，我与你们同在，哈哈。一直都有人问我写这个赚不赚钱，说实话没钱挣，但是传播广了说不定会遇到有这样的运气，同时感谢西班牙土豪的捐赠 ...
>
>

牛牛牛，这是15万刀，值了。

## 回复 by TrumpWY (#7)

*2023-7-20 19:11*

>
> [kanxue666](https://bbs.kanxue.com/user-859631.htm)
>
>  牛牛牛，这是15万刀，值了。
>
>

明明是150w刀

## 回复 by kanxue666 (#8)

*2023-7-20 19:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  TrumpWY](https://bbs.kanxue.com/user-957821.htm)
>
>  明明是150w刀
>
>

哥们儿，仔细看看，是不是多看了几个0![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by fjqisba (#9)

*2023-7-20 21:19*

6666，我顶我顶

## 回复 by kanxue (#10)

*2023-7-20 22:00*

这个工具太强大了！

## 回复 by gjden (#11)

*2023-7-20 22:10*

>
> [kanxue](https://bbs.kanxue.com/user-93.htm)
>
>  这个工具太强大了！
>
>

![image](https://bbs.kanxue.com/view/img/face/67.gif)![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by hackevil (#12)

*2023-7-20 22:19*

G神太强了！

## 回复 by hackevil (#13)

*2023-7-20 22:25*

>
> [kanxue666](https://bbs.kanxue.com/user-859631.htm)
>
>  牛牛牛，这是15万刀，值了。
>
>

G神的10年，值个毛线，至少加两个0，才符合G神的身份![image](https://bbs.kanxue.com/view/img/face/19.gif)

## 回复 by 秋狝 (#14)

*2023-7-21 10:14*

tql

## 回复 by kanxue666 (#15)

*2023-7-21 11:13*

>
> [hackevil](https://bbs.kanxue.com/user-816665.htm)
>
>  G神的10年，值个毛线，至少加两个0，才符合G神的身份[em_19]
>
>

这也要杠一下![image](https://bbs.kanxue.com/view/img/face/80.gif)

## 回复 by LowRebSwrd (#16)

*2023-7-21 19:21*

tql

## 回复 by huangjw (#17)

*2023-7-21 21:35*

gda作者，6666

## 回复 by 小菜鸟一 (#18)

*2023-7-22 07:46*

tql

## 回复 by 金坷垃彩虹 (#19)

*2023-7-22 09:58*

确实牛

## 回复 by MsScotch (#20)

*2023-7-22 10:52*

tql

## 回复 by saloyun (#21)

*2023-7-22 11:29*

tql

## 回复 by billery (#22)

*2023-7-22 20:29*

tql

## 回复 by 万里星河 (#23)

*2023-7-22 23:47*

支持大佬

## 回复 by _air (#24)

*2023-7-23 13:53*

感谢分享

## 回复 by 新气象 (#25)

*2023-7-23 15:14*

作者牛逼，支持下

## 回复 by XCicada (#26)

*2023-7-24 09:34*

![image](https://bbs.kanxue.com/upload/attach/202307/927003_P9QSNNCBWY2FAQK.jpg)这里反编译出错了
Android_8.9.70.11635_64.apk

```
com.tencent.mobileqq.setting.main.MainSettingConfigProvider
```

## 回复 by StriveMario (#27)

*2023-7-24 10:17*

膜一下

## 回复 by hpphpp (#28)

*2023-7-24 11:20*

专程登陆来致敬一下

## 回复 by gjden (#29)

*2023-7-24 15:20*

>
> [hackevil](https://bbs.kanxue.com/user-816665.htm)
>
>  G神的10年，值个毛线，至少加两个0，才符合G神的身份[em_19]
>
>

价值也不只是金钱来衡量，自己开心就好

## 回复 by gjden (#30)

*2023-7-24 15:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  hpphpp](https://bbs.kanxue.com/user-226208.htm)
>
>  专程登陆来致敬一下
>
>

感谢

## 回复 by gjden (#31)

*2023-7-24 15:20*

>
> [a'ゞCicada](https://bbs.kanxue.com/user-927003.htm)
>
>  这里反编译出错了Android_8.9.70.11635_64.apkcom.tencent.mobileqq.setting.main.MainSettingConfigProvider
>
>

提供下APK文件

## 回复 by Cherryl (#32)

*2023-7-24 17:18*

感谢分享。

## 回复 by ssuperrice (#33)

*2023-7-25 08:56*

tql

## 回复 by XCicada (#34)

*2023-7-25 15:16*

>
> [gjden](https://bbs.kanxue.com/user-302697.htm)
>
>  提供下APK文件
>
>

https://downv6.qq.com/qqweb/QQ_1/android_apk/Android_8.9.70.11635_64.apk

## 回复 by daxia200N (#35)

*2023-7-26 18:09*

支持下，居然有破解版了

## 回复 by gjden (#36)

*2023-7-27 11:54*

>
> [daxia200N](https://bbs.kanxue.com/user-1491.htm)
>
>  支持下，居然有破解版了
>
>

exetool跟得挺快，这么快就出来了。

## 回复 by lqfcugo (#37)

*2023-7-27 14:03*

牛逼Puls~~

## 回复 by alds (#40)

*2023-8-3 11:31*

大佬，你这个支持去平坦流混淆吗？

## 回复 by hackings (#41)

*2023-8-4 17:56*

>
> [daxia200N](https://bbs.kanxue.com/user-1491.htm)
>
>  支持下，居然有破解版了
>
>

别用那个破解版，没破解完全，假死难受，还是用free版吧

## 回复 by 陈可牛 (#42)

*2023-12-14 19:05*

挺好用的，特别是对于大app上！

不过有三项的免费版也加上去的话，那就太好了！

1、类似于抖音这种大app中反编译一直弹那个提示框，一直谈没办法反编译！很难受！最好可以直接忽略不要强制提醒；

2、注解丢失；

3、行信息丢失，java调用栈回溯的时候没法根据行号进行确定是那个重载！！！

最好感谢版主的无私奉献，又让我们有了一款非常好用的工具！

## 回复 by 万里星河 (#43)

*2025-8-9 19:03*

重温经典

## 回复 by 山竹笠 (#44)

*2025-8-15 15:29*

tql
