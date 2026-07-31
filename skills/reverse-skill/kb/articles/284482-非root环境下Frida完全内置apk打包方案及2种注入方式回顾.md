---
title: '[原创]非root环境下Frida完全内置apk打包方案及2种注入方式回顾'
url: https://bbs.kanxue.com/thread-284482.htm
tid: 284482
author: 笑对VS人生
date: '2024-11-18'
tags: [Android安全, 原创, HOOK注入]
crawled_at: '2026-07-31T16:05:57+08:00'
replies: 270
---

今天简单分享之前验证的一个免ROOT权限Frida完全内置APK方案！让Frida得到更广泛的使用！

 关于frida-gadget使用官方及各论坛都有许多讲解及说明，但似乎都停留在把hook脚本代码存放本地SD目录或者/data/local/tmp。

 对于分析来说完全够用了，但是对于想把实现hook的整体效果直接分享出来就存在局部限制，那么能不能实现LSPatch类似效果？答案是完全没问题！
 运行效果如下：
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_FDQ9C76P94HKD8X.webp)

首选我们回顾下frida-gadget注入两种方式，顺便补充完善部分细节，具体如下：

1.基于so层通过添加依赖库方式调用Frida库 （实现原理参考：Android平台感染ELF文件实现模块注入）

简单来说就是找个软件启动时候最开始调用so文件，t通过对其注入添加依赖库方式启用frida-gadget

*如果apk本身没有so这种方式是否可以？
也没问题，直接通过dex2c方案把部分java方法转换为so调用，再注入就好了！
比如 开源的 <https://github.com/codehasan/dex2c> 或者某些一键工具*

为了让操作简单化，这里我把注入工具重新py写了下，为了普遍可以用特意找win7环境打包独立exe
Windows环境下so注入工具下载见：<https://gitee.com/xdvsrs/so-injection-tool-exe>
（论坛附件上传运行空间有限，只能借助gitee）
注入操作方式如下图：
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_VGM9UQWZY74DMEM.webp)

2.基于JAVA层Smali代码调用Frida库 （System.loadLibrary("frida");）
这是比较常用的方案，通过首启activity或application在方法<init>()或<clinit>()或onCreate植入如下代码
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_6NUDKGH8JSCMQX6.webp)
代码如下

| 12 | `const``-``string p0,` `"frida-gadget"`    `invoke``-``static {p0}, Ljava``/``lang``/``System;``-``>loadLibrary(Ljava``/``lang``/``String;)V` |
|-|-|

## 接下来就是今天重点，如何把脚本也一并内置apk里面，直接安装打开就自动调用

 关于打包进apk后执行js官方文档及之前部分博主、网友是这样讲的 !
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_S8568MYETMF8PX6.webp) ![image](https://bbs.kanxue.com/upload/attach/202411/687336_PM86DWWYRMR8YK9.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_FW88BWF6HC57E7M.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_WUPPPDVCD4GNE32.webp)

 这样并不能实现脚本内置，这样还得借助ADB或者本地文件夹读取权限才能完成加载hook的js代码，分享使用存在局限性！

## 重点！重点！

## 通过如下方式实现js跟随依赖库，配置文件处于同一路径，就可以直接加载，

 原理：安装后的 so 文件通常会被存储在以下路径：/data/app/<package-name>/lib/<abi>/
 （本身没有so的APK就手动创建文件夹或者D2C抽取产生）
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_PMGUBK5X294QQUA.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202411/687336_FAC4JADU9RPQ277.webp)
 libjs.so：hook的js代码文件（案例内容）

| 123456789101112131415161718192021222324252627 | `if` `(Java.available) {``Java.perform(function () {``console.log(``"Hooking any Activity..."``);` `/``/` `动态获取所有的 Activity 类，并 Hook 其 onCreate 方法``var Activity` `=` `Java.use(``"android.app.Activity"``);` `Activity.onCreate.overload(``"android.os.Bundle"``).implementation` `=` `function (bundle) {``var activityClassName` `=` `this.getClass().getName();` `/``/` `获取当前 Activity 类名``console.log(activityClassName` `+` `" onCreate hooked!"``);` `/``/` `调用原始的 onCreate 方法``this.onCreate(bundle);` `/``/` `获取上下文并在主线程显示 Toast，提示当前 Activity 名称``var context` `=` `Java.use(``'android.app.ActivityThread'``).currentApplication().getApplicationContext();` `Java.scheduleOnMainThread(function() {``var toast` `=` `Java.use(``"android.widget.Toast"``);``var message` `=` `"Frida Hook成功! 通过java层调用 \n当前Activity: "` `+` `activityClassName;``toast.makeText(context, Java.use(``"java.lang.String"``).$new(message),` `1``).show();``});``};``});``}` `else` `{``console.log(``"Java environment not available!"``);``}` |
|-|-|

 libfrida-gadget.config.so： 调用配置内容改如下

| 123456 | `{` `"interaction"``:{``"type"``:``"script"``,``"path"``:``"libjs.so"``}``}` |
|-|-|

 libfrida-gadget.config.so：Frida依赖库文件（可根据需要自行去下载<https://github.com/frida/frida/releases> ）

 为了进一步方便大家参考比较，以上2种方式分别做了Demo，可自行下载对比原版改动地方！

 完成以上打包，接下来就是自由发挥的时候了！*hook!hook!*

## 测试demo及工具打包下载：(论坛或gitee注意是分割文件)

  [apk demo下载 （gitee分享）](https://gitee.com/xdvsrs/so-injection-tool-exe/tree/master/apkdemo)

 第三方网盘下载：<https://share.feijipan.com/s/waD7AO5K>

 有待改善优化空间：比如做手机端或者PC端一键注入打包，做魔改，自己二次编译libfrida-gadget定制个人需求功能

 补充：市场上部分应用目前都带加固或者防Frida，如何过检测等等.....就靠大家自己探索了！

 文献主要参考：<https://frida.re/docs/gadget/> 以及部分前辈、博主文档

上传的附件：
- frida免root内置打包样本及工具.zip.001

（7.00MB，151次下载）
- frida免root内置打包样本及工具.zip.002

（7.00MB，116次下载）
- frida免root内置打包样本及工具.zip.003

（7.00MB，96次下载）
- frida免root内置打包样本及工具.zip.004

（6.58MB，116次下载）

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-11-18 23:24*

感谢分享，向楼主学习

## 回复 by mb_elqwyvnm (#3)

*2024-11-19 02:58*

理论学习

## 回复 by azd放 (#4)

*2024-11-19 08:58*

感谢分享，向楼主学习

## 回复 by hacker521 (#5)

*2024-11-19 10:40*

感谢分享，向楼主学习

## 回复 by wx_byte (#6)

*2024-11-19 10:46*

666

## 回复 by mb_Xr1IQxQa (#7)

*2024-11-19 10:53*

6666666

## 回复 by 墨穹呢 (#8)

*2024-11-19 11:42*

感谢分享

## 回复 by KingSelyF (#9)

*2024-11-19 14:57*

可以跨进程搞？

## 回复 by Imxz (#10)

*2024-11-19 15:29*

66666666

## 回复 by anenn (#11)

*2024-11-19 16:38*

学习了

## 回复 by 阳光宝贝 (#12)

*2024-11-19 18:25*

学习了，感谢

## 回复 by kingking888 (#13)

*2024-11-19 20:10*

感谢分享

## 回复 by 5m10v3 (#14)

*2024-11-20 10:39*

感谢分享

## 回复 by pexillove (#15)

*2024-11-20 10:53*

看看看看·

## 回复 by 养只猫不好么 (#16)

*2024-11-20 11:05*

感谢分享

## 回复 by mb_tewbhakr (#17)

*2024-11-20 11:19*

看看隐藏

## 回复 by mb_sslwzxww (#18)

*2024-11-20 16:06*

感谢分享

## 回复 by 软件君子 (#19)

*2024-11-20 16:25*

看看技术贴

## 回复 by mb_tvmcbdnl (#20)

*2024-11-21 01:18*

看看技术贴

## 回复 by wogao (#21)

*2024-11-21 09:31*

学习技术贴

## 回复 by 万物有属 (#22)

*2024-11-21 10:13*

学习技术贴

## 回复 by mb_lzrunsng (#23)

*2024-11-21 11:47*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_luijbmka (#24)

*2024-11-21 15:36*

牛皮牛皮

## 回复 by AunCss (#25)

*2024-11-22 11:07*

牛的。又是一种新方式

## 回复 by Necopy (#26)

*2024-11-22 15:16*

学习学习

## 回复 by yinjianann (#27)

*2024-11-22 15:36*

牛的

## 回复 by 呼吸24K纯氧 (#28)

*2024-11-22 17:26*

感谢分享，向楼主学习

## 回复 by Thehepta (#29)

*2024-11-22 17:37*

我看看

## 回复 by 程序员小潘 (#30)

*2024-11-22 18:56*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Hidd3n_c0d3r (#31)

*2024-11-22 19:19*

学习了，感谢

## 回复 by mb_dhqqovwu (#32)

*2024-11-23 02:42*

学习一下方法

## 回复 by Fantiane (#33)

*2024-11-24 01:18*

666

## 回复 by 微微T52G25 (#34)

*2024-11-25 07:47*

大佬专业啊

## 回复 by 从未沦陷 (#35)

*2024-11-25 08:01*

太强了,学习一下

## 回复 by wx_蚊子_415 (#36)

*2024-11-25 17:08*

真的牛 关注了

## 回复 by mb_paeqogwt (#37)

*2024-11-26 19:46*

很好

## 回复 by AYHMO (#38)

*2024-11-27 10:55*

感谢分享

## 回复 by wx_IT_717 (#39)

*2024-11-27 12:08*

感谢楼主的分享，非root环境的需求越来越大

## 回复 by 人海呀茫茫啊 (#40)

*2024-11-27 13:03*

牛皮

## 回复 by wx_0.0_522 (#41)

*2024-11-27 13:54*

nb

## 回复 by ldljlzw (#42)

*2024-11-27 15:49*

我的回复怎么不见呢？谢谢楼主！![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by sogohere (#43)

*2024-11-27 16:52*

值得学习！

## 回复 by jjcat (#44)

*2024-11-27 16:58*

????????

## 回复 by mb_ipugnluu (#45)

*2024-11-28 07:38*

感谢分享，向楼主学习

## 回复 by saloyun (#46)

*2024-11-28 08:35*

牛的哟,还是思路打开了

## 回复 by Gryffindoss (#47)

*2024-11-28 09:34*

6666666

## 回复 by 不再后悔 (#48)

*2024-11-28 10:26*

牛牛牛牛

## 回复 by mb_rllvittu (#49)

*2024-11-29 02:08*

1111

## 回复 by 默写lose挚爱 (#50)

*2024-11-30 10:24*

学习了

## 回复 by liuxingbusi (#51)

*2024-12-1 12:06*

学习

## 回复 by 7_up (#52)

*2024-12-1 13:18*

感谢分享

## 回复 by 财神爷999 (#53)

*2024-12-2 20:57*

很好，看看

## 回复 by 李生abcd (#54)

*2024-12-3 10:36*

牛牛

## 回复 by 不具名的悲伤 (#55)

*2024-12-3 11:10*

6

## 回复 by 初恒 (#56)

*2024-12-3 15:05*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_jrutkmfr (#57)

*2024-12-3 20:46*

牛皮牛皮

## 回复 by 狂小咪 (#58)

*2024-12-4 03:07*

牛皮牛皮

## 回复 by 眠眠 (#59)

*2024-12-5 08:07*

感谢分享

## 回复 by 黑屏 (#60)

*2024-12-6 08:29*

学习技术贴

## 回复 by qqsunqiang (#61)

*2024-12-9 14:17*

谢谢楼主分享

## 回复 by mb_jgdenpbg (#62)

*2024-12-10 00:46*

sd

## 回复 by zouzhiqiang (#63)

*2024-12-10 09:56*

666

## 回复 by mb_anbthlub (#64)

*2024-12-10 10:09*

1

## 回复 by mb_selzmlge (#65)

*2024-12-10 22:25*

这个的有弊端，就是在加固情况下或者有签名验证下不适用，比如180x2

## 回复 by mb_aiwbqwce (#66)

*2024-12-12 20:46*

大佬牛逼

## 回复 by wx_Wyndem (#67)

*2024-12-13 10:22*

牛皮牛皮

## 回复 by MaYil (#68)

*2024-12-14 17:36*

感谢分享

## 回复 by mb_loylxxdo (#69)

*2024-12-15 13:29*

学习到了

## 回复 by 从未沦陷 (#70)

*2024-12-16 08:44*

最关键的还是解决二次打包校验啊

## 回复 by woaiziyou (#71)

*2024-12-16 11:25*

为你点赞！

## 回复 by mb_sjnafgkp (#72)

*2024-12-17 11:52*

有没有手机版的

## 回复 by anywhere杨 (#73)

*2024-12-17 20:00*

厉害

## 回复 by 彦沄学长 (#74)

*2024-12-17 20:23*

感谢分享~

## 回复 by 像风一样呢 (#75)

*2024-12-17 20:33*

学习一下

## 回复 by mb_cabwymdh (#76)

*2024-12-17 21:26*

????

## 回复 by mb_gwvkzfzc (#77)

*2024-12-18 11:36*

牛的

## 回复 by x_power (#78)

*2024-12-23 08:16*

牛牛牛

## 回复 by mb_rykfhozr (#79)

*2024-12-27 13:50*

牛的。又是一种新方式

## 回复 by r0reborn (#80)

*2024-12-27 15:22*

111

## 回复 by mb_vgsbqhdw (#81)

*2024-12-28 19:06*

学习一下

## 回复 by 丁真 (#82)

*2024-12-28 23:20*

长见识了![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_itzrixny (#83)

*2025-1-2 02:11*

看看技术贴

## 回复 by ONewTach (#84)

*2025-1-2 08:15*

看一看瞧一瞧

## 回复 by 果冻大砍刀 (#85)

*2025-1-2 12:28*

学习技术贴

## 回复 by Jeanmm (#86)

*2025-1-2 13:50*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 哆啦噩梦 (#87)

*2025-1-2 14:40*

牛皮牛皮

## 回复 by wx_逝水流年 (#88)

*2025-1-2 15:15*

牛皮

## 回复 by 钱钱钱￥ (#89)

*2025-1-2 15:39*

学习技术贴

## 回复 by it爱好者_625041 (#90)

*2025-1-2 21:54*

good

## 回复 by mb_xyoslnox (#91)

*2025-1-3 00:12*

niua

## 回复 by hy6ran (#92)

*2025-1-3 09:46*

学习学习

## 回复 by mb_xyoslnox (#93)

*2025-1-4 23:01*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by zhczf (#94)

*2025-1-5 02:30*

通过dex2c方案把部分java方法转换为so调用

## 回复 by hekes (#95)

*2025-1-5 15:36*

学习学习

## 回复 by ty1937 (#96)

*2025-1-6 09:53*

看看隐藏

## 回复 by 口艾口牙女马口牙 (#97)

*2025-1-6 10:22*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_xplmklfg (#98)

*2025-1-9 14:26*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 八重嘤 (#99)

*2025-1-10 14:22*

![image](https://bbs.kanxue.com/view/img/face/063.gif)

## 回复 by mb_xfxbxijx (#100)

*2025-1-15 09:34*

1111111

## 回复 by wx_插曲 (#101)

*2025-1-15 09:46*

1

## 回复 by Crack999 (#102)

*2025-1-15 13:37*

感谢分享

## 回复 by mb_fwbyoqyp (#103)

*2025-1-17 00:43*

牛皮

## 回复 by mb_cmkfqbwu (#104)

*2025-1-22 16:55*

几

## 回复 by mb_zsizdcrb (#105)

*2025-1-24 13:09*

6666

## 回复 by wx_平头哥 (#106)

*2025-1-24 14:14*

学习学习

## 回复 by mb_kszojzkj (#107)

*2025-1-24 15:28*

感谢分享

## 回复 by mb_yfbuhojr (#108)

*2025-1-26 07:05*

感谢分享，下载学习

## 回复 by tfll (#109)

*2025-1-26 15:38*

学习一下新的hook方式

## 回复 by kylinokok (#110)

*2025-1-27 05:08*

又是一种新方式

## 回复 by huangbof (#111)

*2025-1-28 12:14*

感谢分享，向楼主学习

## 回复 by mb_cjxvunvr (#112)

*2025-1-29 16:11*

好![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by undefined_621929 (#113)

*2025-1-31 10:23*

牛皮牛皮

## 回复 by mb_dqfyawrq (#114)

*2025-1-31 22:10*

![image](https://bbs.kanxue.com/view/img/face/001.gif)太强了

## 回复 by 情迁 (#115)

*2025-2-1 17:43*

没太懂，和我hookui里面内置frida有啥区别呢 我回复下看看

## 回复 by 笑熬浆糊 (#116)

*2025-2-1 17:59*

一种新方式

## 回复 by xiaoc996 (#117)

*2025-2-5 10:38*

666666

## 回复 by 小黑瞳 (#118)

*2025-2-11 12:16*

感谢分享，向楼主学习

## 回复 by jikjgygjhg (#119)

*2025-2-11 12:35*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by nqminhquan (#120)

*2025-2-11 15:53*

thank you for share

## 回复 by Da_ (#121)

*2025-2-12 11:51*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 大山雀小猫咪 (#122)

*2025-2-13 09:33*

学习技术贴

## 回复 by wx_归期_856 (#123)

*2025-2-13 10:25*

感谢分享

## 回复 by wfvw126 (#124)

*2025-2-18 15:56*

看看怎么样

## 回复 by 墨儒蛮君 (#125)

*2025-2-20 03:05*

牛

## 回复 by bluegatar (#126)

*2025-2-20 12:01*

有签名验证怎么搞？？？

## 回复 by mb_wuevwbec (#127)

*2025-2-24 13:50*

牛皮

## 回复 by cpannn (#128)

*2025-2-26 20:51*

技术贴

## 回复 by alimke (#129)

*2025-2-27 08:43*

真的不错

## 回复 by fangliangz (#130)

*2025-2-27 09:22*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 挥一挥衣袖 (#131)

*2025-2-27 09:38*

6的

## 回复 by 叮叮当_468844 (#132)

*2025-2-27 11:32*

牛皮牛皮

## 回复 by DstoneCool (#133)

*2025-2-27 13:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by passself (#134)

*2025-2-28 10:56*

666

## 回复 by 孤独的街 (#135)

*2025-2-28 11:55*

学习技术贴

## 回复 by NSpron (#136)

*2025-3-3 14:38*

看看内容

## 回复 by suexian (#137)

*2025-3-4 11:12*

666

## 回复 by andy张刘 (#138)

*2025-3-5 22:04*

牛的。又是一种新方式

## 回复 by 智取琪 (#139)

*2025-3-5 23:19*

牛逼

## 回复 by cjja爱之恋 (#140)

*2025-3-7 00:54*

支持，，，，，

## 回复 by shsgl (#141)

*2025-3-7 01:47*

跟大牛学学

## 回复 by stuhkg (#142)

*2025-3-7 11:34*

牛皮牛皮

## 回复 by 逆向小玖 (#143)

*2025-3-7 16:51*

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>
>  有签名验证怎么搞？？？
>
>

过掉签名验证

## 回复 by mb_tbvvbfot (#144)

*2025-3-7 23:45*

前来学习！

## 回复 by zkbutt (#145)

*2025-3-8 03:13*

能不能动态指定目录呢

## 回复 by mb_wnwwmdty (#146)

*2025-3-11 16:28*

1

## 回复 by mb_kxvziwtt (#147)

*2025-3-12 08:44*

感谢分享

## 回复 by mb_mmodulik (#148)

*2025-3-13 18:11*

看看大佬文章

## 回复 by 大舊饭 (#149)

*2025-3-14 18:05*

6

## 回复 by mb_izcdoqeh (#150)

*2025-3-19 03:28*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by ugvnui (#151)

*2025-3-19 09:03*

不错，挺好的

## 回复 by wx_小小MAN (#152)

*2025-3-19 17:02*

感谢分享，向楼主学习

## 回复 by 偶尔.c (#153)

*2025-3-20 15:12*

看看隐藏，感谢分享

## 回复 by zkbutt (#154)

*2025-3-20 15:28*

不知道怎么回事，so层的hook用不起

## 回复 by qiusuper (#155)

*2025-3-20 15:30*

谢谢谢谢

## 回复 by 39周 (#156)

*2025-3-21 15:56*

1

## 回复 by mb_dgsueauw (#157)

*2025-3-21 16:33*

感谢分享

## 回复 by yyyad (#158)

*2025-3-21 22:35*

你好，问一下怎么把js脚本放在lib里面

## 回复 by hbslover (#159)

*2025-3-25 00:00*

1111

## 回复 by 花情 (#160)

*2025-4-1 09:31*

看看

## 回复 by mb_yubqcabm (#161)

*2025-4-6 21:56*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_fqzjlpub (#162)

*2025-4-15 13:43*

666

## 回复 by mb_vxsnzesk (#163)

*2025-4-15 13:56*

支持一个

## 回复 by 笑对VS人生 (#164)

*2025-4-16 06:44*

>
> [yyyad](https://bbs.kanxue.com/user-1029297.htm)
>
>  你好，问一下怎么把js脚本放在lib里面
>
>
>

直接js文件重命名后缀放lib相应架构文件夹里面，看样本吧，还不会那就放弃吧

## 回复 by mb_vpaqlckp (#165)

*2025-4-21 15:31*

666666

## 回复 by mb_cbgtaveo (#166)

*2025-4-21 15:56*

66666

## 回复 by 迷途小猪 (#167)

*2025-4-21 23:58*

看看学习

## 回复 by Vengeance (#168)

*2025-4-24 00:16*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by winte (#169)

*2025-5-1 18:03*

能做成简单工具就好了

## 回复 by mb_hwxdqfhi (#170)

*2025-5-2 17:31*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Viseris (#171)

*2025-5-5 19:05*

11

## 回复 by Assclyon (#172)

*2025-5-6 09:58*

感谢大佬分享新的思路![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_ekitlujo (#173)

*2025-5-6 11:13*

66

## 回复 by 林蓝 (#174)

*2025-5-6 12:16*

666  支持

## 回复 by 天街 (#175)

*2025-5-16 10:41*

l厉害

## 回复 by 咸鱼…… (#176)

*2025-5-16 18:07*

感谢分享

## 回复 by kxblah (#177)

*2025-5-20 16:05*

hao

## 回复 by frankpi (#178)

*2025-5-20 19:18*

636

## 回复 by npc0vo (#179)

*2025-6-1 19:43*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_szxvbgvd (#180)

*2025-6-2 15:22*

????????

## 回复 by fzyspark (#181)

*2025-6-3 11:37*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Tanuyoki0 (#182)

*2025-6-7 00:59*

感谢分享

## 回复 by Ms135 (#183)

*2025-6-16 20:20*

666

## 回复 by mb_xflcgdik (#184)

*2025-6-24 09:20*

6

## 回复 by mb_qgybgrma (#185)

*2025-6-26 21:49*

牛的。又是一种新方式

## 回复 by mb_ebiwunmj (#186)

*2025-6-26 22:39*

牛皮

## 回复 by mb_vwuaejat (#187)

*2025-6-30 11:36*

0111

## 回复 by omuitk (#188)

*2025-7-3 17:57*

牛的。又是一种新方式

## 回复 by Ann945 (#189)

*2025-7-5 02:31*

nb

## 回复 by mb_rzbczrdy (#190)

*2025-7-7 19:46*

回复看看，学习

## 回复 by 飆汗吉米 (#191)

*2025-7-7 23:11*

学习技术贴

## 回复 by 一拳揍哭你 (#192)

*2025-7-9 15:58*

学习学习

## 回复 by fgfyo (#193)

*2025-7-10 09:13*

学习学习！！！

## 回复 by 智取棋 (#194)

*2025-7-15 08:55*

牛逼的

## 回复 by Jiryu (#195)

*2025-7-15 15:43*

11

## 回复 by mb_pivwkzjg (#196)

*2025-7-28 14:57*

666

## 回复 by early bird (#197)

*2025-7-31 00:29*

感谢分享

## 回复 by mb_btxmxtmb (#198)

*2025-8-3 10:57*

刚好想了解这部分内容，太牛了

## 回复 by 舞梦月影 (#199)

*2025-8-3 15:08*

感谢分享

## 回复 by mb_aoaayslv (#200)

*2025-8-6 10:28*

学习一下

## 回复 by mb_birmgglx (#201)

*2025-9-18 12:49*

学习学习

## 回复 by wx_！_336 (#202)

*2025-9-20 10:05*

111

## 回复 by xinhu (#203)

*2025-10-13 17:30*

123123

## 回复 by mb_irhdtnzm (#204)

*2025-10-14 22:12*

1

## 回复 by mb_spjzwhqd (#205)

*2025-10-17 00:32*

厉害

## 回复 by mb_cbhhrcqt (#206)

*2025-10-17 06:28*

11111111111111111

## 回复 by 非洲男 (#207)

*2025-10-26 10:50*

感谢分享，学习一下

## 回复 by tdhao (#208)

*2025-11-11 19:41*

看看有没有好办法

## 回复 by zylyy (#209)

*2025-11-11 21:17*

666666

## 回复 by Evangeliner (#210)

*2025-11-16 14:23*

看看看看

## 回复 by mb_basgiwmq (#211)

*2025-11-18 08:27*

666666666666666

## 回复 by 梦_魇 (#212)

*2025-11-18 10:14*

666

## 回复 by mb_qimctavn (#213)

*2025-11-18 10:53*

6

## 回复 by mb_umfqcneh (#214)

*2025-11-24 13:39*

666

## 回复 by mb_ztqcemce (#215)

*2025-11-28 09:10*

看看教程

## 回复 by Heiyiren123 (#216)

*2025-12-9 04:46*

支持楼主，感谢分享！

## 回复 by lov520ing (#217)

*2025-12-14 12:41*

6666

## 回复 by 上官兮唐 (#218)

*2025-12-14 14:21*

看看

## 回复 by mb_rbaigqfb (#219)

*2025-12-16 17:12*

感谢师傅分享

## 回复 by tigericon (#220)

*2025-12-17 20:34*

666

## 回复 by tigericon (#221)

*2025-12-17 20:34*

666

## 回复 by tigericon (#222)

*2025-12-17 20:34*

666

## 回复 by tigericon (#223)

*2025-12-17 20:34*

666

## 回复 by mb_yhlgzisk (#224)

*2025-12-19 11:33*

牛的牛的

## 回复 by wx_Huber Barrientos (#225)

*2025-12-20 13:00*

66666

## 回复 by mb_iqfpzyti (#226)

*2025-12-25 18:16*

~

## 回复 by 哈希豪 (#227)

*2025-12-26 16:28*

666666666666666666666

## 回复 by mb_rdqxdjmw (#228)

*2026-1-13 16:47*

学习学习

## 回复 by 宛枫 (#229)

*2026-1-15 01:13*

感谢分享，感谢分享

## 回复 by mb_fhpfcoqp (#230)

*2026-1-15 10:01*

感谢分享，向楼主学习

## 回复 by 周小韬 (#231)

*2026-1-15 10:14*

cool

## 回复 by mb_auylfslb (#232)

*2026-1-15 10:48*

666

## 回复 by dob_C (#233)

*2026-1-15 11:20*

感谢分享

## 回复 by 信安匠人 (#234)

*2026-1-16 16:32*

666

## 回复 by 逆向小呆呆 (#235)

*2026-1-18 19:19*

太强大了

## 回复 by wx_小白_266 (#236)

*2026-1-24 00:59*

可以可以牛逼

## 回复 by dxasqw (#237)

*2026-1-28 01:04*

6666

## 回复 by qqxiaobai (#238)

*2026-1-28 18:00*

这种方式如果和PC连接，互传js脚本和hook信息，那可真是方便至极、可以为所欲为啊![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_xcxzqumw (#239)

*2026-1-29 16:16*

牛的。又是一种新方式

## 回复 by mb_oltoyiex (#240)

*2026-2-4 16:03*

666

## 回复 by mb_uzcsurra (#241)

*2026-2-4 18:36*

6

## 回复 by mb_oltoyiex (#242)

*2026-2-4 20:39*

出现没有Java is undefined 大佬这怎么解决

## 回复 by B.M.K (#243)

*2026-2-4 22:14*

666

## 回复 by mb_cuovdytq (#244)

*2026-2-18 14:13*

4 楼
感谢分享，向楼主学习

## 回复 by mb_vvpefhit (#245)

*2026-2-28 18:47*

111

## 回复 by lufeey (#246)

*2026-3-3 15:05*

感谢分享

## 回复 by NIXEVOL (#247)

*2026-3-12 22:08*

牛皮啊，厉害

## 回复 by mb_hcqpswwu (#248)

*2026-3-14 02:42*

看看

## 回复 by iBa0 (#249)

*2026-4-5 09:30*

123

## 回复 by 啊你好哇123 (#250)

*2026-4-9 12:11*

学习学习

## 回复 by xx_dd_y (#251)

*2026-4-9 17:13*

666

## 回复 by git_74197luban110 (#252)

*2026-4-10 09:57*

666

## 回复 by mb_jbwxhnml (#253)

*2026-4-12 18:01*

11

## 回复 by git_24708cy3ber (#254)

*2026-4-13 09:17*

666

## 回复 by shuangmou (#255)

*2026-4-14 16:54*

感谢大佬分享

## 回复 by wx_窒息 (#256)

*2026-4-17 21:09*

666

## 回复 by babalove (#257)

*2026-4-18 20:57*

感谢分享

## 回复 by 星落噜啦啦 (#258)

*2026-4-19 09:33*

牛

## 回复 by mb_wignxlei (#259)

*2026-4-19 13:53*

666

## 回复 by mb_rrwegvyc (#260)

*2026-4-21 11:25*

666666666

## 回复 by mb_jtoofixf (#261)

*2026-5-6 22:31*

牛

## 回复 by 菜鸟9527 (#262)

*2026-5-7 13:22*

学习一下大佬的经验

## 回复 by 街道办事处 (#263)

*2026-5-21 10:52*

111

## 回复 by mb_irrqcmsq (#264)

*2026-5-28 10:26*

谢谢，太厉害了

## 回复 by mb_xjdhrmck (#265)

*2026-6-6 19:26*

666

## 回复 by mb_rooofjxx (#266)

*2026-6-25 11:11*

牛

## 回复 by mb_kjujrhnv (#267)

*2026-6-25 11:22*

111

## 回复 by mb_wtskxwnr (#268)

*2026-6-25 12:18*

看看

## 回复 by guijingwen (#269)

*2026-6-28 17:27*

66

## 回复 by 皮皮卡卡丘 (#270)

*2026-7-12 00:21*

·

## 回复 by mb_degalzhb (#271)

*2026-7-20 10:14*

666
