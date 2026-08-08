---
title: '[原创]安卓逆向 某头部银行app 过frida检测 脱壳 定位登录接口加解密函数全过程'
url: https://bbs.kanxue.com/thread-290187.htm
tid: 290187
author: reserve_zhou
date: '2026-03-05'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆, HOOK注入, 系统相关, 工具脚本]
crawled_at: '2026-08-08T10:20:39+00:00'
replies: 120
---

首先，我是新手，希望大佬勿喷，只是分享我的学习流程 本贴没出现任何关于真正业务相关的代码，只有学习流程，对包名进行打码 ，违规必删

注：本贴有很多不完善之处！！clone的原理 ，脱壳的具体方法 ，过ssl检测的具体方法 。回头看，真的有很多不完善的地方！如果是要追寻细节解决方法的朋友可以退出了

过一阵会总结一个新手入门四大关，也是以本帖App为案例，旨在为入门frida-hook的朋友提供一些线性思路  描述各个环节详细的方法，以及如何解决各种类型的问题 。

首先frida -f 模式注入app

app启动后有强制退出弹框 可以看到有可能存在反root ， 反调试 。 但是奇怪的是，frida连接并没有死，app也并没闪退 ， 只是app出现弹框强制退出，意识到这比其他so层反注入可能要好很多，因为这代表so层没有进行强制终止app进程 ，尝试用frida动态找类以及查询进程信息进行基本连接测试发现完全可以操控app进程，那么就好办了，不过以防万一，还是先dlopen看看加载的so文件里有没有可以的风控so

![image](https://bbs.kanxue.com/upload/attach/202603/FSCA3NZ4DVRGCJ3.jpg)![image](https://bbs.kanxue.com/upload/attach/202603/6YAP957MGVQRJC6.jpg)

dlopen脚本

| Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"), { onEnter: function (args) { console.log("加载SO：" + args[0].readCString() ); } }); console.log("监控启动！操作APP看SO加载路径～"); |
|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_YPZHKGCQEBTCKCU.webp)

hook clone函数，暗杀子线程

`clone`是 Android/Linux 创建线程的核心系统调用，所有子线程创建必走此函数；

`PROT_NONE`为内存权限标识，设为该权限后，对应地址无法读 / 写 / 执行，线程执行即崩溃；

            Hook clone 捕获壳的防护子线程地址，打`PROT_NONE`直接废线程。

           hook clone函数 实战代码

| function hook_cer_test_and_offset() { const TARGET_SO = [ ]; var clone = Module.findExportByName('libc.so', 'clone'); if (!clone) { console.log("[-] 未找到clone函数"); return; } Interceptor.attach(clone, { onEnter: function (args) { if (args[3].isNull() \|\| args[3] == 0) return; try { var addr = args[3].add(96).readPointer(); if (addr.isNull() \|\| addr == 0) return; var mod = Process.findModuleByAddress(addr); if (mod && TARGET_SO.includes(mod.name)) { var so_base = mod.base; var offset = addr - so_base; console.log("【检测线程定位】"); console.log("SO名：", mod.name); console.log("入口地址：", addr); console.log("十进制偏移：", offset); console.log("十六进制偏移：", "0x" + offset.toString(16).toUpperCase()); console.log("====================================="); } } catch (e) { } }, onLeave: function (retval) { } }); console.log("[+] clone函数Hook完成，仅监控目标防护SO（含最新新增3个可疑SO + 日志所有出现SO）"); } setImmediate(() => { hook_cer_test_and_offset(); }); |
|-|

可以看到，只有自研究的so文件 ，里面有一个so文件很可疑，这里用红圈标记，尝试hook clone函数，看看是否会出现clone线程的情况，有的话直接暗杀 。 这是clone函数的脚本，大家可以用这个来进行定位可疑so文件的子线程，因为就我目前对银行app过检测的经验来看，大部分是通过clone子线程来进行检测的，甚至有多个子线程互相检测的情况 ，我查过梆梆反调试的原理，也是通过clone线程来进行检测frida痕迹，不论行不行大家都可以先试试，就我个人来言，能过百分之60的银行类检测，但是本项目恰好是另外百分之40，哈哈，但是也有办法！接下来会演示

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_473G94AHD4UQBU7.webp)

![image](https://bbs.kanxue.com/upload/attach/202603/3VUG7M73XVPMQ3G.jpg)

把挖到的地址patch   暗杀后，发现app还是有强制弹框，此时我又锁定了另外一个so，发现同样clone了子线程 ，同样的操作，发现app直接打不开了，app无响应，我此时有一个大胆的想法，这个可能是解密壳的so文件，先过完检测再来确定

那么暗杀方法不行，那么就抓住一切可以利用的痕迹，没用通杀的方法，只有灵活的人类 ，之前有提到，这里frida注入app后并没有死，可以操控frida hook进程，那么还说什么，抓住破绽弹框，直接hook弹框类 ， 抓住调用栈，拦截调用 ， 发现果然孵化再打开的时候就不再弹框了，

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_QUKYUTUGZHBNFGQ.webp)![image](https://bbs.kanxue.com/upload/attach/202603/1068038_NK7VNTK4F69PEGV.webp)

注意，这里我要分享一个细节 大家注意，可以通过hook 弹框类的java创造方法来检测弹窗，但是更好的是通过调用堆栈找到真正的方法调用类方法，可以更精准，更安全

接下来检测就这样过掉了，接下来就是本篇最过瘾的一集，脱壳

一开始，我用mt管理器查看加固信息，惊呆了，头部银行居然没有加固么？？包结构如此清晰，没有出现加固的特征

  ![image](https://bbs.kanxue.com/upload/attach/202603/R8E7MWX32J4A4G4.jpg)![image](https://bbs.kanxue.com/upload/attach/202603/3CT6KSM59XWJGBG.jpg)

打开业务包名，哈哈哈还是被加固了的，AndroidManifate.xml 也有加固特征

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_P8UWQPDATZC2JHG.webp)

   接下来我尝试使用opencommon脱壳，结果是脱到了的

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_VJHQHB99TYAEDN7.webp)

   也可以看清楚完整的包结构  但是做了函数抽取，也就是把class文件里面的函数指令直接打上nop导致只能看见空 ，这就是典型的特征 ，java层的反馈就是包的结构虽然一清二楚 但是函数全部都是return null

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_D626QTX2U9MT5EX.webp)

这里我做了一点分析，就是说，我们使用opencommonhook的时候 ，此时拿到的是被nop化的dex文件 ，很头疼怎么办呢， 我们等待回填又不能触发opencoomon ，所以此时我们可以考虑使用frida-dexdump ，在回填后深度扫描内存，也是一种好方法  注意，这里必须触发模块，或者主动调用函数来让app强制回填，不然同样抓不到

经过反复测试，找到加载点，因为这里是函数抽取，包的结构是完全明了的，完全可以进行主动调用函数来看看dex回填的时机，这里比较私密，不懂私信我，所以经过一番测试，找到了位置，于是，可以考虑使用frida-dexdump深度脱壳来dump maps里面的文件

值得注意的是，如果连frida-dexdump被检测的很严重，就是对内存分区做了强检测，导致应用闪退的话，这时候就真的只能采用so文件主动解密的方法了，分析壳的解密函数，手动解密，难度很高，但是这里很幸运，脱到了

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_M4DHJWRF8AJ93KW.webp)

此时就是真正的代码，脱壳成功

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_G7RK69TAT5CGV84.webp)

接下来就可以来分析登录接口的加密了，首先第一步，先抓包 ，小黄鸟安装证书后，连接电脑协同，必须安装证书，否则可能导致抓不到包

但是我们开启小黄鸟之后，可以发现，开启了ssl检测

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_7KM9ZVQSZFFJGXM.webp)

我们需要hookTrustManagerImpl ，过掉检测

成功抓到包，我们筛选登录接口，触发登录模块，定位登录包 ，最终找到了登录包

![image](https://bbs.kanxue.com/upload/attach/202603/78FSWENY4G767WY.jpg)

根据参数静态搜索定位 ，打开jadx，搜索名称

![image](https://bbs.kanxue.com/upload/attach/202603/1068038_DXYFRNTV9DXZMAG.webp)

此时通过frida动态分析 ，hook java的aes方法 和 crypti方法 找到加解密和密钥  也可以通过静态分析， 但是这里我推荐先动态hook ，定位到具体位置，再进行动态调试，主动调用函数，看函数用途

这一步份涉及实现细节，本文不展开，需要的话可以私信我

至此登录接口破解成功

因为是作者第一次发帖，本贴我不知道什么能写上去什么不能，所以后面会比较模糊，但是可以参考思路，谢谢大家，如果有帮助，麻烦关注一下，我们可以一起进步

---

# 回复

## 回复 by win柠初 (#2)

*2026-3-6 11:38*

有些图片看不到是怎么回事

## 回复 by user_adb (#3)

*2026-3-6 11:53*

难受啊，还有些图片看不了，楼主图片是不是没传好

## 回复 by reserve_zhou (#4)

*2026-3-6 12:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_magic_rookie](https://bbs.kanxue.com/user-939450.htm)
>
>  难受啊，还有些图片看不了，楼主图片是不是没传好
>
>

关注我，晚点有空我更新一下帖子，不好意思，有问题可以私信我

## 回复 by reserve_zhou (#5)

*2026-3-6 16:38*

大家有问题的都可以留言，可能图片因为限制原因被平台禁了？？

## 回复 by 七浪 (#6)

*2026-3-6 17:41*

感谢分享，学习了

## 回复 by reserve_zhou (#7)

*2026-3-6 18:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  七浪](https://bbs.kanxue.com/user-993780.htm)
>
>  感谢分享，学习了
>
>

客气了，后面还会分享更多，如native层混淆突破 ，js逆向， h5逆向等

## 回复 by mb_srmwcgoy (#8)

*2026-3-7 15:34*

66666666

## 回复 by YoungBai (#9)

*2026-3-11 17:56*

好强啊.银行类root检测太让人头疼了.感谢分享.

## 回复 by reserve_zhou (#10)

*2026-3-11 22:40*

>
> [YoungBai](https://bbs.kanxue.com/user-674789.htm)
>
>  好强啊.银行类root检测太让人头疼了.感谢分享.
>
>

现在来看这个帖子还是有很多细节可以优化的，之前关于clone函数的patch也只是知其然而不知其所以然，后面还会更新更好的对抗so文件检测的帖子

## 回复 by mb_ysegxpmv (#11)

*2026-3-11 22:44*

牛逼

## 回复 by mb_oaufhyol (#12)

*2026-3-12 17:20*

666

## 回复 by 外交 (#13)

*2026-3-12 17:46*

666

## 回复 by mb_vywouypi (#14)

*2026-3-12 18:41*

66666666

## 回复 by mb_luvldgil (#15)

*2026-3-12 22:08*

1

## 回复 by zephyyyr (#16)

*2026-3-12 22:18*

111111

## 回复 by mb_kfrkwwjb (#17)

*2026-3-12 23:24*

666

## 回复 by xxjj678 (#18)

*2026-3-13 00:05*

666

## 回复 by mb_adlxcbkt (#19)

*2026-3-13 10:25*

66

## 回复 by mb_xflcgdik (#20)

*2026-3-13 11:50*

66

## 回复 by scllqk (#21)

*2026-3-13 12:39*

牛

## 回复 by kingking888 (#22)

*2026-3-13 12:58*

????

## 回复 by 0xCodeMaster (#23)

*2026-3-13 13:02*

6666

## 回复 by 土豆爱学习 (#24)

*2026-3-13 13:24*

111

## 回复 by daiviswang (#25)

*2026-3-13 13:31*

1111111

## 回复 by maxcl (#26)

*2026-3-13 13:56*

66666

## 回复 by long_ (#27)

*2026-3-13 13:59*

666

## 回复 by mb_cbgtaveo (#28)

*2026-3-13 14:22*

666666666

## 回复 by mb_fywmigrm (#29)

*2026-3-13 18:00*

1

## 回复 by yyyad (#30)

*2026-3-13 18:24*

666

## 回复 by 菜鸟逆向 (#31)

*2026-3-13 21:32*

![image](https://bbs.kanxue.com/view/img/face/001.gif)学习一下

## 回复 by 乌鸡哥 (#32)

*2026-3-13 21:45*

1111111

## 回复 by wx_huhu_859 (#33)

*2026-3-13 23:59*

21

## 回复 by mb_jnkpzfyq (#34)

*2026-3-14 01:28*

支持大佬

## 回复 by reserve_zhou (#35)

*2026-3-14 01:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_jnkpzfyq](https://bbs.kanxue.com/user-1039567.htm)
>  支持大佬
>

不敢当，不敢当

## 回复 by mb_mlyojneh (#36)

*2026-3-14 01:43*

感谢分享

## 回复 by 曰你 (#37)

*2026-3-14 01:51*

1

## 回复 by wx_Huber Barrientos (#38)

*2026-3-14 03:47*

6666

## 回复 by Vengeance (#39)

*2026-3-14 05:34*

666

## 回复 by amwait (#40)

*2026-3-14 10:30*

111

## 回复 by mb_qucmgawb (#41)

*2026-3-14 10:32*

11111

## 回复 by mb_nydrrooh (#42)

*2026-3-14 14:08*

666

## 回复 by mb_ttdxmirg (#43)

*2026-3-14 22:46*

6666

## 回复 by qqqiu (#44)

*2026-3-14 23:05*

66

## 回复 by mb_tkluuesh (#45)

*2026-3-14 23:29*

1

## 回复 by 小猪达 (#46)

*2026-3-15 00:17*

看看

## 回复 by qig (#47)

*2026-3-15 07:18*

6666

## 回复 by mb_weufbroc (#48)

*2026-3-15 18:47*

看看 真是好东西

## 回复 by cafeMusic (#49)

*2026-3-16 08:56*

强

## 回复 by huangjw (#50)

*2026-3-16 09:20*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_gdsjpsvo (#51)

*2026-3-16 14:26*

11111

## 回复 by git_107370xcmore (#52)

*2026-3-16 21:04*

666

## 回复 by mb_ysikfhxt (#53)

*2026-3-16 21:29*

1

## 回复 by 一栋奥特曼 (#54)

*2026-3-17 00:59*

1111

## 回复 by 卡坦精 (#55)

*2026-3-17 08:28*

666

## 回复 by dsr000 (#56)

*2026-3-17 09:15*

666

## 回复 by mb_ugnawvja (#57)

*2026-3-17 13:51*

为你点赞！

## 回复 by zero_coder (#58)

*2026-3-17 14:23*

大家好，如果有安卓逆向经验丰富的人才，看到消息可以的话联系我，我们在寻找逆向大神

## 回复 by zero_coder (#59)

*2026-3-17 14:29*

6666~ 作者你好，看到消息的话可以联系我，期待你的信息~

## 回复 by Atop0s. (#60)

*2026-3-17 16:25*

mark

## 回复 by xifgg (#61)

*2026-3-17 16:44*

111

## 回复 by Mr.He (#62)

*2026-3-17 16:50*

6666

## 回复 by The0dore (#63)

*2026-3-17 17:46*

66666

## 回复 by 中文fjja (#64)

*2026-3-17 19:35*

谢谢分享

## 回复 by 小黄鸭爱学习 (#65)

*2026-3-17 19:36*

学习

## 回复 by pingsky (#66)

*2026-3-17 20:01*

666666666

## 回复 by mb_urvhdxxp (#67)

*2026-3-18 02:25*

看看隐藏

## 回复 by 陳學城 (#68)

*2026-3-18 10:00*

111

## 回复 by Gryffindoss (#69)

*2026-3-18 10:25*

666

## 回复 by mb_edxuqbkt (#70)

*2026-3-18 11:01*

1111

## 回复 by 飆汗吉米 (#71)

*2026-3-18 15:04*

6666

## 回复 by mb_iyeoluxk (#72)

*2026-3-18 15:43*

感谢分享，学习了

## 回复 by 乐观的李阔 (#73)

*2026-3-18 16:13*

111

## 回复 by ab19950220 (#74)

*2026-3-18 16:54*

3333

## 回复 by xianhuimin (#75)

*2026-3-19 02:31*

看看

## 回复 by mb_hznwzoin (#76)

*2026-3-19 21:58*

1

## 回复 by linclsky (#77)

*2026-3-19 22:08*

6666

## 回复 by Simon0816 (#78)

*2026-3-20 11:27*

666

## 回复 by 木槿any (#79)

*2026-3-20 11:52*

666

## 回复 by chengdrgon (#80)

*2026-3-20 12:03*

感谢分享

## 回复 by xuhe123 (#81)

*2026-3-20 12:17*

6666666

## 回复 by 抬头望月 (#82)

*2026-3-20 12:19*

666

## 回复 by XCicada (#83)

*2026-3-20 12:23*

学习了

## 回复 by mb_qimctavn (#84)

*2026-3-20 12:46*

6

## 回复 by 菜鸟9527 (#85)

*2026-3-20 13:38*

点赞

## 回复 by i意写书 (#86)

*2026-3-20 17:22*

得

## 回复 by xeiyu (#87)

*2026-3-20 17:58*

666

## 回复 by wx_坚持才有好结果 (#88)

*2026-3-20 18:01*

11

## 回复 by 学计算机睡觉 (#89)

*2026-3-20 18:09*

66666

## 回复 by 阳光宝贝 (#90)

*2026-3-20 21:03*

感谢分享

## 回复 by git_55111Empycity (#91)

*2026-3-21 00:23*

6

## 回复 by nuoen (#92)

*2026-3-21 03:05*

666

## 回复 by tonykros (#93)

*2026-3-21 21:11*

6666

## 回复 by 张three (#94)

*2026-3-22 10:01*

999999999999999

## 回复 by puppet_w (#95)

*2026-3-22 15:19*

111

## 回复 by iBa0 (#96)

*2026-3-22 19:48*

11

## 回复 by mb_uzmffdbw (#97)

*2026-3-23 09:33*

666

## 回复 by wx_k74001 (#98)

*2026-3-23 10:50*

学习下厉害啦

## 回复 by mb_xgoaxxei (#99)

*2026-3-23 11:32*

![image](https://bbs.kanxue.com/view/img/face/066.gif)

## 回复 by mb_atwurgje (#100)

*2026-3-23 12:39*

6

## 回复 by 山东拓明 (#101)

*2026-3-23 16:05*

666

## 回复 by mb_ekhqutmo (#102)

*2026-3-23 16:32*

11111

## 回复 by hacker521 (#103)

*2026-3-23 16:50*

666

## 回复 by guijingwen (#104)

*2026-3-23 16:58*

66

## 回复 by Eastbo (#105)

*2026-3-23 16:58*

学习了

## 回复 by git_82017s1e34ou (#106)

*2026-3-24 14:43*

666

## 回复 by mb_xbqfqsnf (#107)

*2026-3-25 01:25*

6666

## 回复 by mb_fglogyec (#108)

*2026-3-25 08:35*

66666666

## 回复 by GEKEZYX (#109)

*2026-3-25 10:01*

666

## 回复 by mb_jerxzakl (#110)

*2026-3-25 10:30*

6666

## 回复 by mb_fhnslbti (#111)

*2026-3-25 10:43*

大佬能分享一下app吗

## 回复 by git_83176ivica-111 (#112)

*2026-3-25 12:38*

Cool

## 回复 by wx_插曲 (#113)

*2026-3-26 09:40*

666

## 回复 by Cure. (#114)

*2026-3-26 11:06*

1

## 回复 by mb_pivwkzjg (#115)

*2026-3-26 11:54*

6666

## 回复 by Splite_1130 (#116)

*2026-3-26 15:54*

666666

## 回复 by mb_nxfmrrll (#117)

*2026-3-26 23:54*

学习

## 回复 by superoldman (#118)

*2026-3-27 11:43*

牛逼

## 回复 by wx_窒息 (#119)

*2026-3-27 18:45*

666

## 回复 by mb_lzotvdxv (#120)

*2026-5-9 20:32*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by reserve_zhou (#121)

*2026-5-11 22:12*

>
> [mb_lzotvdxv](https://bbs.kanxue.com/user-1042730.htm)
>  请在 Telegram 上联系我，有个重要的 2000 美元任务。
>  Telegram：@dlopenext
>

你看看
