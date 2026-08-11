---
title: '[求助][求助]apktools逆向app失败'
url: https://bbs.kanxue.com/thread-283653.htm
tid: 283653
author: wx_ZXC_301
date: '2024-09-26'
tags: [Android安全, 求助, 逆向分析, 混淆加固, 脱壳反混淆]
crawled_at: '2026-08-11T08:44:37+00:00'
replies: 11
---

通过Android killer调用apktools解压某app，结果中间报错了，导致失败，app的名字是特殊符号，不知道和这个是否有关系，已经升级了apktools为最新版本，但是依旧报错。尝试下载其他app，可以正常解压。

怀疑此app加了壳，但是apkscan扫不出来，本人小白，请大神能指点一二，不胜感激。

以下是报错信息：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677 | `当前 Apktool 使用版本：new_apktools``正在反编译 APK，请稍等...``>I: Using Apktool` `2.10``.``0` `on js62tccl.apk with` `32` `thread(s).``>I: Baksmaling classes.dex...``>I: Baksmaling classes17.dex...``>I: Baksmaling classes13.dex...``>I: Baksmaling classes40.dex...``>I: Baksmaling classes35.dex...``>I: Baksmaling classes25.dex...``>I: Baksmaling classes8.dex...``>I: Baksmaling classes34.dex...``>I: Baksmaling classes26.dex...``>I: Baksmaling classes6.dex...``>I: Baksmaling classes37.dex...``>I: Baksmaling classes39.dex...``>I: Baksmaling classes38.dex...``>I: Baksmaling classes21.dex...``>I: Baksmaling classes7.dex...``>I: Baksmaling classes29.dex...``>I: Baksmaling classes31.dex...``>I: Baksmaling classes16.dex...``>I: Baksmaling classes33.dex...``>I: Baksmaling classes12.dex...``>I: Baksmaling classes11.dex...``>I: Baksmaling classes3.dex...``>I: Baksmaling classes22.dex...``>I: Baksmaling classes24.dex...``>I: Baksmaling classes28.dex...``>I: Baksmaling classes4.dex...``>I: Baksmaling classes2.dex...``>I: Baksmaling classes27.dex...``>I: Baksmaling classes19.dex...``>I: Baksmaling classes30.dex...``>I: Baksmaling classes15.dex...``>I: Baksmaling classes32.dex...``>I: Loading resource table...``>W: Bad string block: string entry` `is` `at` `204960``, past end at` `204960``>W: Skipping unknown chunk data of size` `0``>W: Skipping unknown chunk data of size` `0``>W: Skipping unknown chunk data of size` `0``>W: Skipping unknown chunk data of size` `0``>W: Skipping unknown chunk data of size` `0``>W: Skipping unknown chunk data of size` `0``>S: Unknown chunk` `type``:` `013c``>I: Decoding` `file``-``resources...``>I: Decoding values` `*``/``*` `XMLs...``>I: Decoding AndroidManifest.xml with resources...``>W: Bad string block: string entry` `is` `at` `1496``, past end at` `1496``>I: Loading resource table` `from` `file``: C:\Users\zxc\AppData\Local\apktool\framework\``1.apk``>I: Baksmaling classes36.dex...``>W: Could` `not` `decode attr value, using undecoded value instead: ns``=``, name``=``theme, value``=``0x00000036``>W: Could` `not` `decode attr value, using undecoded value instead: ns``=``, name``=``, value``=``0x10000008``>W: Unknown chunk` `type` `at: (``0x00006840``) skipping...``>W: Unknown chunk` `type` `at: (``0x00012220``) skipping...``>W: AXML hit unexpected end of` `file` `at byte:` `0x12220``>I: Regular manifest package...``>[Fatal Error] :``2``:``178``: 已经为元素` `"manifest"` `指定属性` `"android:"``。``>I: Copying assets` `and` `libs...``>◇c?⒓▅.wav (Invalid argument)``>◇c?⒓▅.wav (Invalid argument)``>?∷?``9``?╬??l﹕c⑷Z.d (Invalid argument)``>W: Skipping` `file` `cfg``/``a``/``mode_1``/``?``34``?x◎?Q???``65``【``7H``?卍?``4U``ⅶ┍E?﹛???????♀︶??z???＂?A??t?←???a5?g????N??Ⅵ?t??￣┤tq?x?R?E?□╔?????mⅸ??yU?j??g┒﹎``7``?``*``l?L????卍□①?⊙?⑤▊??????b▂H≡??ⅱ???∠p???④c????◢⑺Bⅴ?Ⅱ?Ⅳ?∷?``9``?╬??l﹕c⑷Z.d (Invalid argument)``>W: Skipping` `file` `cfg``/``a``/``mode_1``/``?``34``?x◎?Q???``65``【``7H``?卍?``4U``ⅶ┍E?﹛???????♀︶??z???＂?A??t?←???a5?g????N??Ⅵ?t??￣┤tq?x?R?E?□╔?????mⅸ??yU?j??g┒﹎``7``?``*``l?L????卍□①?⊙?⑤▊??????b▂H≡??ⅱ???∠p???④c????◢⑺Bⅴ?Ⅱ?Ⅳ???⑧?┬?▂↙??A▔????``9``?``9``??×K⒊v??┋??X????⒕???╣``5``???s?@.rar (Invalid argument)``>Exception` `in` `thread` `"main"` `java.nio.``file``.InvalidPathException: Illegal char <<> at index` `137``: D:\aosp\android``-``killer``-``main\projects\js62tccl\Project\assets\cfg\a\mode_1\G??M?``3``?S┷??Y?vD?▲ew??○???【▄aのq⊙p?????X??``6``◇??▅⑤?``4``?I??o?→?┸?????⒙<√?♀???C┧???``9``???⑷??⒏?j??????x?≠?⊿``2``⑤????⊿?↘???????①x??㊣?■??♀?☆???≧?``0Y``?﹫?E?╣???C??``3``??〗〔????∥⒌???&zⅳ???f╓¤???IV????j◎??N?﹊?Yl????◎????↙????∷.ppt``>    at sun.nio.fs.WindowsPathParser.normalize(Unknown Source)``>    at sun.nio.fs.WindowsPathParser.parse(Unknown Source)``>    at sun.nio.fs.WindowsPathParser.parse(Unknown Source)``>    at sun.nio.fs.WindowsPath.parse(Unknown Source)``>    at sun.nio.fs.WindowsFileSystem.getPath(Unknown Source)``>    at java.io.``File``.toPath(Unknown Source)``>    at brut.directory.DirUtil.copyToDir(SourceFile:``0``)``>    at brut.directory.AbstractDirectory.copyToDir(SourceFile:``0``)``>    at brut.directory.DirUtil.copyToDir(SourceFile:``0``)``>    at brut.androlib.ApkDecoder.copyRawFiles(SourceFile:``0``)``>    at brut.androlib.ApkDecoder.decode(SourceFile:``0``)``>    at brut.apktool.Main.main(SourceFile:``0``)``APK 反编译失败，无法继续下一步源码反编译!` |
|-|-|

---

# 回复

## 回复 by NT10086 (#2)

*2024-9-26 16:36*

KILLER 很旧的工具了
建议用其它工具了

## 回复 by mb_fefksfsl (#3)

*2024-9-26 19:52*

试试 jadx

## 回复 by erichyx (#4)

*2024-9-26 23:04*

很可能是某些文件名乱码的原因

## 回复 by mb_zilcedlt (#5)

*2024-9-27 13:25*

是的大佬，请问这种乱码的文件名怎么才能识别出来正常解压呢

## 回复 by 一颗小草 (#6)

*2024-9-27 13:39*

可以发个样本出来看看

## 回复 by wx_ZXC_301 (#7)

*2024-9-27 15:03*

>
> [mb_fefksfsl](https://bbs.kanxue.com/user-979936.htm)
>
>  试试 jadx
>
>

试过了，![image](https://bbs.kanxue.com/upload/attach/202409/925298_APWAZRNSFJZ5XEN.webp)

## 回复 by wx_ZXC_301 (#8)

*2024-9-27 15:07*

>
> [erichyx](https://bbs.kanxue.com/user-371779.htm)
>
>  很可能是某些文件名乱码的原因
>
>

老哥你说的是对的，我也认为是文件名字问题，app名字也很奇怪是特殊符号。

## 回复 by wx_ZXC_301 (#9)

*2024-9-27 15:08*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  一颗小草](https://bbs.kanxue.com/user-973070.htm)
>
>  可以发个样本出来看看
>
>

通过百度网盘分享的文件：crackapp.apk
链接：https://pan.baidu.com/s/19_x4uxsmQUSJES3vK8Kqug
提取码：y3k9
--来自百度网盘超级会员V5的分享
文件80多M，网盘分享吧

## 回复 by mb_cxfdglzv (#10)

*2024-9-27 15:56*

AndroidManifest.xml用apktool和jadx反编译失败可能是这个文件做了反编译相关的对抗，可以参考下这篇文章
https://xz.aliyun.com/t/12938?time__1311=GqGxuD9Qi%3DeiqGN4eeqBKGQF59BCqQDgWoD

## 回复 by wx_ZXC_301 (#11)

*2024-9-28 22:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  NT10086](https://bbs.kanxue.com/user-1000986.htm)
>
>  KILLER 很旧的工具了
> 建议用其它工具了
>
>

有哪些推荐吗？jeb么

## 回复 by wx_ZXC_301 (#12)

*2024-9-28 22:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cxfdglzv](https://bbs.kanxue.com/user-938844.htm)
>
>  AndroidManifest.xml用apktool和jadx反编译失败可能是这个文件做了反编译相关的对抗，可以参考下这篇文章
> https://xz.aliyun.com/t/12938?time ...
>
>

看起来是这样的，研究一下
