---
title: '[分享]qtrace ttttrace'
url: https://bbs.kanxue.com/thread-289683.htm
tid: 289683
author: Yangser
date: '2026-01-05'
tags: [Android安全, 分享, 程序开发]
crawled_at: '2026-08-08T10:30:45+00:00'
replies: 189
---

# qtrace

## 地址

[qtrace](https://github.com/SoyBeanMilkx/qtrace)
 ![image](https://bbs.kanxue.com/upload/attach/202601/947037_JYAQQR5YRTWJ223.webp)

## 速度

2GB+/min

 ![image](https://bbs.kanxue.com/upload/attach/202601/947037_YZS68P6XXE9XPSC.webp)

## 格式

| 1 | `libName!{symbolInfo}!{traceType}` |
|-|-|

其中：

1. **symbolInfo**可以是符号名(并不保证百分百能解析出偏移)、偏移地址、IDA反汇编风格函数名(sub_xxxx)
2. **traceType**定义
	1. *func_code*：常规汇编流
	2. *func_call*：函数调用关系
	3. *mem_rw*：内存读写情况

## 日志格式

### func_code

 ![image](https://bbs.kanxue.com/upload/attach/202601/947037_SC34KAPHX9VK4DG.webp)

### func_call

 ![image](https://bbs.kanxue.com/upload/attach/202601/947037_XYNCGS7BAPJA6PM.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202601/947037_NX763JTDGRRB85B.webp)

## == END ==

今天第一天上班，有人懂上班吗饿啊饿啊

本来想完善一下再发的，，，现在就当攒bug了，到时候一块修

不开源。因为部分代码参考了**追佬的vm-trace** 欢迎大家使用vm-trace

不好用别骂我，我还是个孩子

上传的附件：
- func_call.log

（11.00kb，50次下载）
- func_call2.log

（11.93kb，26次下载）
- func_code.log

（1.37MB，30次下载）
- qtrace.apk

（7.31MB，157次下载）

---

# 回复

## 回复 by wx_huhu_859 (#2)

*2026-1-6 00:42*

11

## 回复 by Bonnie-Ran (#3)

*2026-1-6 00:50*

mark一下，有函数调用关系

## 回复 by mb_vvpefhit (#4)

*2026-1-6 01:15*

gccv

## 回复 by mb_ldbucrik (#5)

*2026-1-6 01:20*

感谢分享

## 回复 by mb_nkjfyhkg (#6)

*2026-1-6 02:18*

mark

## 回复 by huluxia (#7)

*2026-1-6 03:52*

大佬牛逼

## 回复 by SomeMx (#8)

*2026-1-6 04:17*

看看实力

## 回复 by 风_158566 (#9)

*2026-1-6 07:36*

谢谢分享

## 回复 by 黑屏 (#10)

*2026-1-6 07:54*

mark

## 回复 by Yangser (#11)

*2026-1-6 08:48*

>
> [SomeMx](https://bbs.kanxue.com/user-926256.htm)
>
>  看看实力
>
>

没实力，菜哭了

## 回复 by mb_asiwnxyv (#12)

*2026-1-6 09:08*

感谢分享

## 回复 by huangjw (#13)

*2026-1-6 09:13*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_插曲 (#14)

*2026-1-6 09:19*

66

## 回复 by rex_sky (#15)

*2026-1-6 09:22*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_roiscepd (#16)

*2026-1-6 09:59*

66

## 回复 by wx_。。。。_455 (#17)

*2026-1-6 10:30*

66

## 回复 by guijian (#18)

*2026-1-6 10:50*

66

## 回复 by mb_ysegxpmv (#19)

*2026-1-6 11:04*

大佬牛皮

## 回复 by mb_qimctavn (#20)

*2026-1-6 13:29*

6

## 回复 by Imxz (#21)

*2026-1-6 14:18*

tql

## 回复 by ldehua (#22)

*2026-1-6 14:30*

大佬牛皮

## 回复 by 奋斗小菜鸟 (#23)

*2026-1-6 15:03*

牛鼻

## 回复 by mb_cbgtaveo (#24)

*2026-1-6 15:05*

6666666666

## 回复 by uniking (#25)

*2026-1-6 15:39*

666

## 回复 by 带带弟弟吧 (#26)

*2026-1-6 16:39*

11111

## 回复 by wx_ㅤ_683 (#27)

*2026-1-6 17:18*

安装包损坏

## 回复 by Yangser (#28)

*2026-1-6 17:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  安装包损坏
>
>

安卓版本上限14，cpu架构arm64

## 回复 by GEKEZYX (#29)

*2026-1-6 17:45*

666

## 回复 by mb_lizfxfno (#30)

*2026-1-6 20:36*

感谢分享

## 回复 by mb_yxcltfyb (#31)

*2026-1-6 20:45*

牛牛牛

## 回复 by xianhuimin (#32)

*2026-1-6 21:36*

666

## 回复 by wen55444 (#33)

*2026-1-7 02:28*

6666

## 回复 by Kill_Log (#34)

*2026-1-7 07:58*

666

## 回复 by buluo533 (#35)

*2026-1-7 07:59*

66666

## 回复 by 像风一样呢 (#36)

*2026-1-7 08:30*

666

## 回复 by amwpecel (#37)

*2026-1-7 08:55*

666

## 回复 by mb_euhyowpw (#38)

*2026-1-7 09:25*

666

## 回复 by dob_C (#39)

*2026-1-7 09:48*

感谢分享

## 回复 by wx_不愿 (#40)

*2026-1-7 10:10*

666

## 回复 by mb_pesxllvn (#41)

*2026-1-7 10:26*

666

## 回复 by pexillove (#42)

*2026-1-7 11:31*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  安卓版本上限14，cpu架构arm64
>
>

pxiel6安卓13下载后安装包是灰色的也提示无法安装

## 回复 by mb_ykavguun (#43)

*2026-1-7 12:32*

6666

## 回复 by 淡定小胖子 (#44)

*2026-1-7 13:47*

66

## 回复 by 1sfans (#45)

*2026-1-7 14:14*

666

## 回复 by 夜惜风雨 (#46)

*2026-1-7 14:32*

66666666666

## 回复 by wx_piracy (#47)

*2026-1-7 14:38*

666

## 回复 by wx_ㅤ_683 (#48)

*2026-1-7 15:01*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  安卓版本上限14，cpu架构arm64
>
>

小米10，安卓12

## 回复 by Yangser (#49)

*2026-1-7 15:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  小米10，安卓12
>
>

我搞错了，minSDK和targetSdk都设置成34了，你自己重打包一下吧。没做任何校验

## 回复 by mb_4nrpVMxJ (#50)

*2026-1-7 16:11*

666

## 回复 by 丶咖啡猫丶 (#51)

*2026-1-7 18:44*

666

## 回复 by wx_Huber Barrientos (#52)

*2026-1-8 00:19*

感谢分享

## 回复 by 月清晖 (#53)

*2026-1-8 09:09*

越看不懂的越高端

## 回复 by 抬头望月 (#54)

*2026-1-8 09:18*

666

## 回复 by 肉蚌葱鸡 (#55)

*2026-1-8 09:52*

牛鼻

## 回复 by Yangser (#56)

*2026-1-8 10:21*

>
> [月清晖](https://bbs.kanxue.com/user-353710.htm)
>
>  越看不懂的越高端
>
>

啊，我就是为了让大家都看得懂用的明白才写的ui

## 回复 by mb_mlyojneh (#57)

*2026-1-8 10:56*

666

## 回复 by wx_kx26825 (#58)

*2026-1-8 11:37*

6666666666

## 回复 by 壹久玖 (#59)

*2026-1-8 11:39*

666

## 回复 by baitongling (#60)

*2026-1-8 14:43*

666

## 回复 by wujimaa (#61)

*2026-1-8 14:50*

999

## 回复 by 九月心情 (#62)

*2026-1-8 15:23*

66666

## 回复 by wx_ㅤ_683 (#63)

*2026-1-8 15:34*

显示，Module not found:，找不到库是什么原因

## 回复 by 飞机上唱山歌 (#64)

*2026-1-8 15:47*

1

## 回复 by wx_范迪塞尔 (#65)

*2026-1-8 16:47*

看看可能过检测

## 回复 by 29o (#66)

*2026-1-8 17:09*

666

## 回复 by CheRevir (#67)

*2026-1-8 17:11*

666

## 回复 by Yangser (#68)

*2026-1-8 17:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  显示，Module not found:，找不到库是什么原因
>
>

哪个日志

## 回复 by mb_ysegxpmv (#69)

*2026-1-8 21:48*

libmsaoaidsec.so!JNI_OnLoad!func_call我输入这个后点那个输入框后面的按钮，下面会提示symbol not found:JNI_OnLoad，但是JNI_OnLoad再idapro中打开的libmsaoaidsec.so是导出的

## 回复 by kingking888 (#70)

*2026-1-8 21:53*

666

## 回复 by qwerdvd (#71)

*2026-1-9 02:14*

6

## 回复 by 秋落 (#72)

*2026-1-9 07:36*

666

## 回复 by Helenccz (#73)

*2026-1-9 09:59*

6666

## 回复 by iBa0 (#74)

*2026-1-9 11:12*

看看老铁

## 回复 by keulraesik (#75)

*2026-1-9 14:14*

谢谢分享

## 回复 by tank小王子 (#76)

*2026-1-9 14:14*

牛逼。。。

## 回复 by Yangser (#77)

*2026-1-9 14:19*

>
> [mb_ysegxpmv](https://bbs.kanxue.com/user-1014708.htm)
>
>  libmsaoaidsec.so!JNI_OnLoad!func_call我输入这个后点那个输入框后面的按钮，下面会提示symbol not found:JNI_OnLoad，但是JNI_OnLoad ...
>
>

那你传偏移就行了

## 回复 by aerfaxing (#78)

*2026-1-9 15:10*

牛批

## 回复 by wx_weggfkdk (#79)

*2026-1-9 15:10*

看下

## 回复 by wx_ㅤ_683 (#80)

*2026-1-9 15:40*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  哪个日志
>
>

call,其它类型也不行

## 回复 by Yangser (#81)

*2026-1-9 16:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  call,其它类型也不行
>
>

你要trace的app里有那个so吗，只支持arm64

## 回复 by wx_ㅤ_683 (#82)

*2026-1-9 17:20*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  你要trace的app里有那个so吗，只支持arm64
>
>

有so,是arm64

## 回复 by Yangser (#83)

*2026-1-9 17:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  有so,是arm64
>
>

你截图发我邮件吧，shuangxve@gmail.com

## 回复 by baogu (#84)

*2026-1-9 19:06*

8

## 回复 by mb_ysegxpmv (#85)

*2026-1-9 20:09*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  那你传偏移就行了
>
>

试了下还是不行，用ida里面的地址减去模块地址了都不行

## 回复 by Yangser (#86)

*2026-1-9 20:28*

>
> [mb_ysegxpmv](https://bbs.kanxue.com/user-1014708.htm)
>
>  试了下还是不行，用ida里面的地址减去模块地址了都不行
>
>

也没报错吗

## 回复 by wx_听书人 (#87)

*2026-1-9 20:49*

66666

## 回复 by mb_ysegxpmv (#88)

*2026-1-9 22:02*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  也没报错吗
>
>

换了一个软件，试了其他的so可以了，先通过frida查看加载了那些so，再去做trace就可以了

## 回复 by 温泉划水鱼 (#89)

*2026-1-10 01:33*

康康

## 回复 by mb_zpvlfkkg (#90)

*2026-1-11 03:52*

666

## 回复 by wx_lll_652 (#91)

*2026-1-11 06:43*

555566

## 回复 by 温泉划水鱼 (#92)

*2026-1-11 10:15*

能trace多线程吗

## 回复 by Viseris (#93)

*2026-1-11 12:26*

谢谢分享

## 回复 by mb_bhsrdtqf (#94)

*2026-1-11 17:43*

666

## 回复 by pigsub (#95)

*2026-1-11 18:01*

666666666

## 回复 by wx_逸_143 (#96)

*2026-1-11 18:17*

66666

## 回复 by apxar (#97)

*2026-1-11 22:46*

1

## 回复 by mb_lpcoesnt (#98)

*2026-1-11 23:57*

这个太强了

## 回复 by zylyy (#99)

*2026-1-12 00:23*

666

## 回复 by mb_lakweznz (#100)

*2026-1-12 00:32*

瞅瞅

## 回复 by mb_tcheuwvg (#101)

*2026-1-12 10:49*

666

## 回复 by bygrand (#102)

*2026-1-12 13:28*

111

## 回复 by nevinhappy (#103)

*2026-1-12 14:35*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by chionyuna (#104)

*2026-1-12 14:47*

666

## 回复 by 网络侦探 (#105)

*2026-1-12 17:48*

围观看下

## 回复 by jdong (#106)

*2026-1-13 09:39*

6666666666

## 回复 by asuralove (#107)

*2026-1-13 10:07*

666

## 回复 by 飆汗吉米 (#108)

*2026-1-14 11:48*

666

## 回复 by mb_jhohnbzu (#109)

*2026-1-16 18:03*

666

## 回复 by AYHMO (#110)

*2026-1-17 11:14*

6666

## 回复 by wx_小友 (#111)

*2026-1-17 12:48*

0.0

## 回复 by fei3ei (#112)

*2026-1-19 09:46*

有实力的

## 回复 by mb_auylfslb (#113)

*2026-1-19 09:50*

666

## 回复 by mb_auylfslb (#114)

*2026-1-19 09:50*

666

## 回复 by mb_maiyudos (#115)

*2026-1-19 14:27*

66

## 回复 by mb_evapxmjh (#116)

*2026-1-20 11:53*

666

## 回复 by 九黎 (#117)

*2026-1-20 14:26*

tql

## 回复 by wx_西门浪 (#118)

*2026-1-20 20:13*

666

## 回复 by SInnon (#119)

*2026-1-23 18:10*

6666666

## 回复 by Zepp7289 (#120)

*2026-1-23 19:23*

牛逼

## 回复 by ghostrong (#121)

*2026-1-24 14:52*

1111

## 回复 by git_94730eaydwshawke-gif (#122)

*2026-1-24 18:42*

1

## 回复 by fei3ei (#123)

*2026-1-26 10:09*

牛

## 回复 by BestToYou (#124)

*2026-1-26 10:34*

6666

## 回复 by 小尘0000 (#125)

*2026-1-28 10:28*

666

## 回复 by chenwitch (#126)

*2026-1-28 19:48*

666

## 回复 by 简单的简单 (#127)

*2026-1-28 20:44*

666

## 回复 by fengvmu (#128)

*2026-1-29 09:53*

666

## 回复 by xiaoc996 (#129)

*2026-1-29 09:55*

666

## 回复 by mb_lgbrcvmf (#130)

*2026-1-30 11:16*

666

## 回复 by mb_ysikfhxt (#131)

*2026-1-30 16:02*

1

## 回复 by 木头子 (#132)

*2026-2-1 17:38*

niupi

## 回复 by 墨点 (#133)

*2026-2-4 04:18*

666

## 回复 by 烬奇小云 (#134)

*2026-2-4 09:40*

666

## 回复 by mb_xxezghuh (#135)

*2026-2-4 12:09*

666

## 回复 by mb_rbaigqfb (#136)

*2026-2-5 09:03*

学习下

## 回复 by baichisi (#137)

*2026-2-5 09:15*

666

## 回复 by wx_白鸟之诗 (#138)

*2026-2-5 09:21*

666

## 回复 by 盖伦爸爸 (#139)

*2026-2-6 09:54*

666666

## 回复 by tDasm (#140)

*2026-2-6 12:54*

学习

## 回复 by 小今朝 (#141)

*2026-2-6 13:49*

666

## 回复 by mb_zkxhnhda (#142)

*2026-2-8 11:27*

66

## 回复 by mb_nbhpszaj (#143)

*2026-2-8 17:17*

123

## 回复 by mb_irhdtnzm (#144)

*2026-2-9 18:44*

1

## 回复 by XJ。 (#145)

*2026-2-9 19:16*

6

## 回复 by @NoBody (#146)

*2026-3-1 08:48*

你好，我自己做了一个二进制静态动态结合的创新的方案(我研究过学术界关于二进制跟踪的很多论文)，可以记录ios程序起始到结束堆内存读写和函数调用(普通的类似stalker的方法太慢了是无法实现的)，速度只减少50%。不过最近不做逆向了，有需要的朋友我可以出这套系统找10个人每个人500块。WX:jiqizaisikao

## 回复 by myios (#147)

*2026-3-1 09:48*

666

## 回复 by PangBai (#148)

*2026-3-2 00:05*

999

## 回复 by 西瓜帅 (#149)

*2026-3-2 09:11*

66

## 回复 by 我不是卷王 (#150)

*2026-3-2 09:57*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 听我讲故事吗. (#151)

*2026-3-2 20:08*

666

## 回复 by mb_donutrph (#152)

*2026-3-5 14:57*

66

## 回复 by mb_stdlrcgp (#153)

*2026-3-5 23:00*

6666666

## 回复 by mb_jzyasacd (#154)

*2026-3-5 23:16*

666

## 回复 by 云觞 (#155)

*2026-3-6 14:39*

感谢分享

## 回复 by Mr.He (#156)

*2026-3-6 15:30*

66666

## 回复 by bolice (#157)

*2026-3-6 16:24*

看看什么trace

## 回复 by mb_hvhepvsl (#158)

*2026-3-6 16:34*

666

## 回复 by pingsky (#159)

*2026-3-6 22:27*

有点意思哦

## 回复 by qig (#160)

*2026-3-9 09:40*

感谢分享

## 回复 by 林懋 (#161)

*2026-3-13 17:36*

6

## 回复 by mb_xyoslnox (#162)

*2026-3-20 23:24*

支持

## 回复 by Xx_gg (#163)

*2026-4-8 09:47*

66666

## 回复 by tjytjy (#164)

*2026-4-8 10:55*

666

## 回复 by 我就是小熊猫 (#165)

*2026-4-8 14:13*

666

## 回复 by mb_ugnawvja (#166)

*2026-4-23 17:07*

感谢分享

## 回复 by long_ (#167)

*2026-4-24 16:01*

666

## 回复 by mb_gluymaeh (#168)

*2026-4-25 09:30*

666

## 回复 by frozenrain (#169)

*2026-4-25 09:48*

是否支持iOS下的trace

## 回复 by Yangser (#170)

*2026-4-27 09:30*

>
> [frozenrain](https://bbs.kanxue.com/user-144246.htm)
>  是否支持iOS下的trace
>

最近有要做的打算

## 回复 by Freax (#171)

*2026-4-27 11:37*

6

## 回复 by Gryffindoss (#172)

*2026-5-13 14:20*

666

## 回复 by XCicada (#173)

*2026-5-13 14:52*

66

## 回复 by mb_uzmffdbw (#174)

*2026-5-15 17:46*

666

## 回复 by 鼻屎怪 (#175)

*2026-5-16 22:28*

6666

## 回复 by x1a0f3n9 (#176)

*2026-5-19 12:48*

大佬我爱你

## 回复 by Yangser (#177)

*2026-5-19 13:09*

>
> [x1a0f3n9](https://bbs.kanxue.com/user-1036990.htm)
>  大佬我爱你
>

大佬我更爱你

## 回复 by mb_rztmbvgb (#178)

*2026-5-19 13:18*

666

## 回复 by zxqi (#179)

*2026-5-23 23:57*

1

## 回复 by shuangmou (#180)

*2026-5-24 00:26*

感谢分享

## 回复 by 中文fjja (#181)

*2026-5-27 22:06*

感谢分享

## 回复 by didiid (#182)

*2026-6-25 13:59*

666

## 回复 by maomaolk (#183)

*2026-6-28 11:36*

666

## 回复 by s1nec-1o (#184)

*2026-6-28 13:20*

1

## 回复 by 上官兮唐 (#185)

*2026-6-28 14:15*

看看，感谢大佬

## 回复 by 钟白 (#186)

*2026-7-19 02:45*

666

## 回复 by MikotoDev (#187)

*2026-7-23 02:53*

66

## 回复 by TeamAR (#188)

*2026-7-23 09:06*

666

## 回复 by mb_mihutdve (#189)

*2026-7-27 15:10*

666

## 回复 by fenfei331 (#190)

666
