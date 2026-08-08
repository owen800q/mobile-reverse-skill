---
title: '[原创]某手游逆向分析libtprt'
url: https://bbs.kanxue.com/thread-290312.htm
tid: 290312
author: lihaiyanz
date: '2026-03-14'
tags: [Android安全, 原创, 逆向分析, 协议分析, 脱壳反混淆, HOOK注入]
crawled_at: '2026-08-08T10:19:22+00:00'
replies: 133
---

![image](https://bbs.kanxue.com/upload/attach/202603/540232_SHGNEZAY7RPUFX5.webp)

打开安装包看到是il2cpp的框架使用Il2CppDumper.GUI 看看
![image](https://bbs.kanxue.com/upload/attach/202603/540232_7UGFMBRKVQ3USYX.webp)

报错 使用010看看是so文件和.dat文件是不是加固了

![image](https://bbs.kanxue.com/upload/attach/202603/540232_6QHQCQA53XENS9Z.webp)

so文件IDA加载后看也有问题  回到lib文件下面看到这个 libtprt.so 这个是某讯的加固

使用frida 把libil2cpp.so DUMP下来 网上很多脚本

使用IDA 搜索字符串global-metadata.dat 定位到
通过一通分析就发现他使用的libtprt.so进行解密的

分析了几个使用libtprt.so加固的手游 发现都是固定位置解密的global-metadata.dat 和libil2cpp.so的

这里就说下libtprt.so怎么进行解密global-metadata.dat 和libil2cpp.so的
![image](https://bbs.kanxue.com/upload/attach/202603/540232_C5CDBK34KNJJMHP.webp)

![image](https://bbs.kanxue.com/upload/attach/202603/540232_H7GBH7PE8UNB43U.webp)

![image](https://bbs.kanxue.com/upload/attach/202603/540232_RYB54PD2AS8REJC.webp)

先看解密global-metadata.dat
![image](https://bbs.kanxue.com/upload/attach/202603/540232_8QK9VUQ94N8TQJJ.webp)

309478292十六进制就是94 43 72 12 正好对应着我们global-metadata.dat的头四字节

![image](https://bbs.kanxue.com/upload/attach/202603/540232_YTDJ37UE2B6G2AQ.webp)

133938就是解密算法 算法是AES这个自己可以下载被libtprt加固的游戏看
3647341504LL是密钥 剩下的就是使用编程实现下解密就好了

![image](https://bbs.kanxue.com/upload/attach/202603/540232_VXQKYWQ4BXBSSG4.webp)
这里是进行二次解密前几字节的
这里重点说下 密钥是每个游戏用的不一样 需要拿到libtprtSO定位到拿到密钥
下面是就是运行的结果
![image](https://bbs.kanxue.com/upload/attach/202603/540232_V5AER5TP8V7NC24.webp)
我们看下直接使用fridaDUMP的SO进行Il2CppDumper
![image](https://bbs.kanxue.com/upload/attach/202603/540232_VYUHZCXJT3PSPGA.webp)

虽然报错了但是可以看到 dll和dump.cs文件已经拿到了 这说明SO还有被处理
下面就是使用fridaHOOK 32AE0DUMP 出来 libil2cpp.so就不会报错了 这里就不再演示了 有兴趣的可以去实践下

---

# 回复

## 回复 by mb_hcqpswwu (#2)

*2026-3-14 02:29*

看看思路

## 回复 by wx_Huber Barrientos (#3)

*2026-3-14 03:50*

非常感谢！

## 回复 by wx_code_258 (#4)

*2026-3-14 04:25*

6

## 回复 by cpannn (#5)

*2026-3-14 06:14*

好????????

## 回复 by mb_dmryhnwz (#6)

*2026-3-14 07:29*

6

## 回复 by jw8888 (#7)

*2026-3-14 07:59*

6666666666

## 回复 by 外交 (#8)

*2026-3-14 09:26*

66666

## 回复 by 破客 (#9)

*2026-3-14 09:33*

看看思路

## 回复 by Imxz (#10)

*2026-3-14 09:48*

rql

## 回复 by huangjw (#11)

*2026-3-14 09:58*

可以的，好东东。谢谢分享

## 回复 by jyotidwi (#12)

*2026-3-14 10:13*

777

## 回复 by 毛毛毛毛虫 (#13)

*2026-3-14 11:38*

看看

## 回复 by mb_ldbucrik (#14)

*2026-3-14 12:54*

感谢分享

## 回复 by 土豆爱学习 (#15)

*2026-3-14 18:06*

成功dump so和bat文件得到dump.cs只是第一步，后面还有麻烦的检测和封号逻辑等着你

## 回复 by mb_tdoadyps (#16)

*2026-3-15 00:05*

11

## 回复 by mb_ejwssbrk (#17)

*2026-3-15 00:47*

看看思路

## 回复 by mb_ghzqfgyt (#18)

*2026-3-16 02:19*

1343434

## 回复 by SomeMx (#19)

*2026-3-16 03:43*

过来瞧瞧

## 回复 by Zepp7289 (#20)

*2026-3-16 09:23*

tql

## 回复 by wx_weggfkdk (#21)

*2026-3-16 09:39*

看看

## 回复 by wlmf (#22)

*2026-3-16 09:52*

mark

## 回复 by Gryffindoss (#23)

*2026-3-16 10:23*

66666

## 回复 by 4Chan (#24)

*2026-3-16 10:55*

666

## 回复 by fjqisba (#25)

*2026-3-16 11:06*

为啥不用AI分析

## 回复 by gloomyle (#26)

*2026-3-16 17:14*

66666

## 回复 by CheRevir (#27)

*2026-3-16 17:39*

666

## 回复 by xxRea (#28)

*2026-3-16 17:58*

看看思路

## 回复 by puppet_w (#29)

*2026-3-16 18:00*

66

## 回复 by mb_atzlqltk (#30)

*2026-3-17 00:29*

66

## 回复 by mb_yalauklc (#31)

*2026-3-17 08:40*

看看内容

## 回复 by chenwitch (#32)

*2026-3-17 10:38*

666

## 回复 by mb_knjxjdkf (#33)

*2026-3-17 17:57*

有实力

## 回复 by TeamAR (#34)

*2026-3-17 19:15*

666

## 回复 by git_83176ivica-111 (#35)

*2026-3-17 20:52*

Thanks

## 回复 by mb_cozyptsk (#36)

*2026-3-17 22:15*

看看

## 回复 by MaYil (#37)

*2026-3-17 23:23*

感谢分享

## 回复 by mb_douhzfuu (#38)

*2026-3-18 09:31*

*

## 回复 by xifgg (#39)

*2026-3-18 09:59*

666

## 回复 by XCicada (#40)

*2026-3-18 10:21*

66666

## 回复 by XCicada (#41)

*2026-3-18 10:23*

怎么不露文件大小

## 回复 by andy张刘 (#42)

*2026-3-18 13:30*

看看思路

## 回复 by 丶咖啡猫丶 (#43)

*2026-3-19 09:11*

666

## 回复 by 天地一逆旅 (#44)

*2026-3-19 10:17*

学习一下

## 回复 by mb_sibpnhef (#45)

*2026-3-19 11:24*

ai分析

## 回复 by mb_ouklyzqs (#46)

*2026-3-19 21:20*

6666

## 回复 by cpannn (#47)

*2026-3-19 22:16*

学习了。

## 回复 by iBa0 (#48)

*2026-3-22 00:49*

123

## 回复 by Cyb3r9 (#49)

*2026-3-22 04:08*

Sure, that's great stuff. Thanks for sharing.

## 回复 by GEKEZYX (#50)

*2026-3-22 10:52*

666

## 回复 by 暴强 (#51)

*2026-3-22 11:43*

不错啊！！！

## 回复 by mb_ysikfhxt (#52)

*2026-3-22 14:52*

11

## 回复 by Circ1e (#53)

*2026-3-23 10:18*

666

## 回复 by TinM! (#54)

*2026-3-23 10:19*

1

## 回复 by mb_jwcpnqgs (#55)

*2026-3-24 14:26*

好

## 回复 by 零_721409 (#56)

*2026-3-24 20:46*

666

## 回复 by mb_mtzutctp (#57)

*2026-3-26 11:49*

666

## 回复 by wx_宇克鴻 (#58)

*2026-3-26 16:43*

6666

## 回复 by mb_sqymxjmv (#59)

*2026-3-27 23:08*

6666

## 回复 by lackone (#60)

*2026-3-28 11:26*

666

## 回复 by hygzs (#61)

*2026-3-28 15:51*

感谢分享看看啥东西

## 回复 by 袁伟业 (#62)

*2026-3-28 19:41*

666

## 回复 by 我是小奥 (#63)

*2026-3-29 01:18*

感谢分享

## 回复 by mb_izusevbx (#64)

*2026-3-31 13:15*

1

## 回复 by lvchalove (#65)

*2026-3-31 15:47*

666666

## 回复 by mb_abajbief (#66)

*2026-3-31 16:06*

1

## 回复 by 小迷糊ddd (#67)

*2026-4-6 22:31*

感谢楼主，参考一下。

## 回复 by 我今年6岁 (#68)

*2026-4-6 22:39*

tql

## 回复 by JiangNight (#69)

*2026-4-7 11:47*

学习下

## 回复 by win柠初 (#70)

*2026-4-7 15:21*

看看

## 回复 by mb_uktygsmq (#71)

*2026-4-9 17:37*

66666

## 回复 by mb_jnmxfjku (#72)

*2026-4-17 11:26*

666

## 回复 by FMNS (#73)

*2026-4-20 13:41*

111111111

## 回复 by mb_hfjfruhl (#74)

*2026-4-20 14:42*

1

## 回复 by wx_赛特 (#75)

*2026-4-20 23:27*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by nqminhquan (#76)

*2026-4-21 00:50*

66666666

## 回复 by 曾经的四 (#77)

*2026-4-21 11:16*

66666666666

## 回复 by ILA1992 (#78)

*2026-5-7 13:04*

这期什么

## 回复 by WX_WQj (#79)

*2026-5-7 16:08*

666

## 回复 by mb_eywdngzs (#80)

*2026-5-9 16:33*

66666

## 回复 by wx_D_755717 (#81)

*2026-5-9 18:59*

6666

## 回复 by woodward (#82)

*2026-5-9 19:20*

66666

## 回复 by mb_lzotvdxv (#83)

*2026-5-9 19:26*

请通过 Telegram 联系我，这很重要。Telegram：@dlopenext

## 回复 by mb_hnwotbvj (#84)

*2026-5-12 21:43*

6666

## 回复 by mb_cjjbbtgt (#85)

*2026-5-13 02:58*

467755

## 回复 by mb_vgbsclvi (#86)

*2026-5-24 00:29*

111

## 回复 by mb_owfvtagq (#87)

*2026-5-25 01:38*

66666

## 回复 by mb_zurizkle (#88)

*2026-5-25 07:04*

6666

## 回复 by zhonghuayi (#89)

*2026-5-26 11:25*

6666

## 回复 by 086Love (#90)

*2026-5-26 11:28*

学习

## 回复 by 酱油啊啊啊啊 (#91)

*2026-5-26 11:38*

6666666

## 回复 by icey233 (#92)

*2026-5-30 16:17*

看看思路

## 回复 by wx_故事与酒 (#93)

*2026-5-30 17:41*

66666666666666666666

## 回复 by mb_devnoxep (#94)

*2026-6-6 12:54*

太牛了，我也研究看看

## 回复 by mb_fogbfnnb (#95)

*2026-6-6 14:45*

6

## 回复 by mb_jegknedl (#96)

*2026-6-9 05:15*

学习学习

## 回复 by mb_zxamxsfc (#97)

*2026-6-11 08:57*

1111

## 回复 by mb_hkcftrec (#98)

*2026-6-11 10:29*

666

## 回复 by mb_rbixrkdo (#99)

*2026-6-11 10:45*

66666666666666

## 回复 by baichisi (#100)

*2026-6-11 10:58*

66

## 回复 by git_64225chenzhenghao806-cmyk (#101)

*2026-6-11 13:11*

55

## 回复 by mb_stmixwya (#102)

*2026-6-11 16:48*

666

## 回复 by mb_wiezfmox (#103)

*2026-6-25 17:09*

666

## 回复 by mb_nwhhyhde (#104)

*2026-6-26 11:20*

6666

## 回复 by 歪嘉尔 (#105)

*2026-6-26 12:38*

可以

## 回复 by 歪嘉尔 (#106)

*2026-6-26 12:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  fjqisba](https://bbs.kanxue.com/user-729528.htm)
>  为啥不用AI分析
>

有啥教程不

## 回复 by mb_gjhmacqd (#107)

*2026-6-26 14:03*

666

## 回复 by mb_pvtzrssj (#108)

*2026-7-1 10:57*

看看

## 回复 by xautzbl (#109)

*2026-7-1 14:43*

666

## 回复 by mb_usbxikyh (#110)

*2026-7-1 21:08*

see

## 回复 by mb_zdainsyf (#111)

*2026-7-5 12:58*

1

## 回复 by fuqiuluo73 (#112)

*2026-7-6 16:16*

11111

## 回复 by Ruinv6 (#113)

*2026-7-7 15:36*

11111111111

## 回复 by git_74909tuanha1305 (#114)

*2026-7-9 14:59*

666

## 回复 by git_74909tuanha1305 (#115)

*2026-7-9 14:59*

666

## 回复 by YooHaa (#116)

*2026-7-10 16:44*

666

## 回复 by mb_elpcuukh (#117)

*2026-7-13 17:57*

成功dump so和bat文件得到dump.cs只是第一步，后面还有麻烦的检测和封号逻辑等着你

## 回复 by wx_寻_333 (#118)

*2026-7-13 20:25*

![image](https://bbs.kanxue.com/view/img/face/059.gif)

## 回复 by mb_zmitfows (#119)

*2026-7-14 16:07*

666

## 回复 by mb_pnsgktdz (#120)

*2026-7-16 04:39*

嘟嘟叔叔

## 回复 by mb_hfayfkpi (#121)

*2026-7-16 13:03*

谢谢分享

## 回复 by 3cly (#122)

*2026-7-16 16:18*

1

## 回复 by mb_isdejwcu (#123)

*2026-7-18 11:54*

666

## 回复 by mb_qimctavn (#124)

*2026-7-18 12:33*

6

## 回复 by Snark (#125)

*2026-7-18 13:15*

111

## 回复 by 星辰1190 (#126)

*2026-7-20 14:27*

2131231231

## 回复 by 龙雨 (#127)

*2026-7-20 18:13*

66666666

## 回复 by mb_nwflotoa (#128)

*2026-7-22 08:31*

谢谢分享

## 回复 by kris_574089 (#129)

*2026-7-23 17:20*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by permanent011 (#130)

*2026-7-24 17:24*

666

## 回复 by mb_yscnhzom (#131)

*2026-7-24 17:57*

学习下看看，感谢楼主分享

## 回复 by mb_uimsagvt (#132)

*2026-7-29 15:10*

看看

## 回复 by mb_jnvmrmrw (#133)

*2026-8-1 17:06*

+666

## 回复 by mb_rztmbvgb (#134)

*2026-8-1 17:26*

666
