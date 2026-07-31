---
title: '[原创] 更高更妙的抓包——从Chrome源码学习使用Cronet 通讯组件的app的通用抓包方法'
url: https://bbs.kanxue.com/thread-277996.htm
tid: 277996
author: 乐子人
date: '2023-07-13'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析, 协议分析, 系统相关, 源码框架]
crawled_at: '2026-07-31T14:41:48+08:00'
replies: 41
---

#### 0.前言

最近看论坛里关于抓包的问题聊的火热，小弟我也借此机会献丑来分享一下我的抓包的研究成果。

毫无疑问，app逆向的第一步是抓包。通过抓包可以获取很多有用的线索，比如url，参数名等。再根据url，参数名等，可以逐步抽丝剥茧找到app收发数据的地方，然后就能找到最关键的签名所在的位置。研究清楚签名，接下来就可以做一些不可告人之事了~

安卓app常用的网络框架是okhttp，对于okhttp的抓包研究已经非常成熟了，无非是certificate pin或者hostname verify那一套。但是最近几年，出现了一些基于Google Cronet通讯框架的app，比如某音，某小破站等等。Cronet是从Chrome中抽出的给移动端使用的网络组件，目前针对Cronet抓包，证书校验的研究比较少，大多是奇技淫巧，没能从根本上挖掘。本文从Chrome源码出发，结合实例某音，研究一下使用Cronet安卓程序的正确抓包姿势。

#### 1.从报错入手

打开手机代理，将https证书塞入手机的根目录，启动目标应用，结果：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_DXMVY6Q7DW42U7B.png)

请求全部失败，app界面也显示无网络，无所谓，我们打开日志先看看：
 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_WURDN6BJE74QUQG.png)

看到了：ERR_CERT_AUTHORITY_INVALID

很明显是检测到了证书 无效。

经常使用Chrome浏览器的朋友应该对这种ERR_开头的错误有印象：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_3GJZSXVQ35RY49F.png)

没错，这正是Chrome的报错通用的格式。

那么我们就可以从报错入手，去Chrome源码里看看这个错误的来源，以此为根据寻求bypass的方式。

#### 2.撸源码

打开Chrome Code Search（在线的Chrome源码浏览网页，提供了强大的交叉引用和全文搜索功能）

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_EYPD4R9RHHM64H3.png)

全局搜索ERR_CERT_AUTHORITY_INVALID

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_H6QWKMAPQCQ8EWG.png)

出现了很多结果，观察后发现 net/cert/cert_status_flags.cc这个文件比较可疑，点进去看看：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_3D873YSTDHD2B28.png)

发现 一个叫做MapCertStatusToNetError 的函数里，返回了这个ERR_CERT_AUTHORITY_INVALID。

（MapCertStatusToNetError ）映射证书状态至网络错误类型，查看这个函数的被谁引用：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_4HZ33U6R67B64PM.png)

在一个cert_verify_proc_android.cc的文件里被引用。这个文件名已经暗示了在检查/校验证书，我们点进去看看：
 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_NAAKTKP3RZBQJPB.png)

在VerifyInternal这个函数里，先用TrustManager校验了一番，如果发现校验结果verify_result的cert_status出现了error，则直接将错误映射后返回。如果没有错误则检查了证书的发布者是否为known_root，然后返回OK。

我们再往上回溯VerifyInternal这个函数：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_PDRG2P6ERBD7HTY.png)

看到一个更抽象的名字：cert_verify_proc.cc(证书校验程序)，点进去看看：
 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_G4PFDJR2AK6S3KW.png)

在这个函数中，rv保存了VerifyInternal的结果，如果结果是OK,则再继续进行了更多的检查：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_6SBGHHBVDEZU23K.png)

比如证书是否使用了较弱的hash算法，是否过期，是否有效期过长（ssl证书有效期通常为1年）等等。
 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_WV8QTFQ5B7VPV3G.png)

最后将rv返回。

我们看到无论是哪一步返回，rv的值都是MapCertStatusToNetError 这个函数赋予的。所以如果我们直接将这个的返回值改为OK，那么无论怎么校验，最终Verify的结果都是通过。换句话说，就是证书校验的过程被bypass了。所以我们考虑在app的so中找到这个函数的位置，然后修改即可。

#### 3.实战

我们观察MapCertStatusToNetError这个函数的特征：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_QKKHS6S2D44MQB4.png)

很明显的，每次通过一个flag与cert_status作与运算，如果通过则返回。

我们打开某音的lib目录，找到目标so：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_HZZ6K46532ASQ7Y.png)

打开之后发现并不好定位MapCertStatusToNetError函数的位置，因为函数名被抹去了。

我们考虑从其他的地方入手，尤其是一些有字符串常量，或者打log的地方入手。

我们看到Verify函数调用了很多次MapCertStatusToNetError函数，但是Verify函数里并没有可提供搜索的字符串信息。

结合编译原理的知识，我们知道源码中相邻的函数通常在编译结果中也是相邻的。

我们到Verify函数下面的一个函数里有一个字符串信息：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_TR2WQRV3ZEPTCCR.png)

我们全局搜索这个字符串，果然有:

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_23DNPZF45G7QZJF.png)

通过交叉引用定位到引用这个字符串的函数，查看与他相邻的上一个函数：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_QT3YC4PP73CVNWB.png)

发现了与Verify函数相似的结构：判断rv是否ok，ok则进一步检查，并通过MapCertStatusToNetError函数给赋值。

我们点进去这个sub_31ff58函数：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_G7R42EF6MYAPC3J.png)

看到了与MapCertStatusToNetError函数一样的结构：通过flag与判断，然后返回。

所以我们找到了MapCertStatusToNetError函数，通过修改汇编指令，直接让他在入口处直接返回OK(0)：

修改前：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_2TQMJ9XVXYD29QJ.png)

修改后：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_W75J89QFE95ETSR.png)

修改完后把so扔回手机替换app包里的so，再次打开app，发现已经可以成功抓包了：
 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_MSS5BJZM5SGWH99.png)

随便打开一个视频的评论看看抓包是否正确：

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_NVKXGCGB585JGUC.png)

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_TWR8XY3GQPYXMBB.png)

 ![image](https://bbs.kanxue.com/upload/attach/202307/872365_MWC5GPGQW6FCVYS.jpg)

嗯，对的，收工！

#### 4.后记

其实小破站用的也是cronet，之前也有类似的证书校验，用同样的方法也能抓包。但是今天试了一下发现小破站把证书校验取消了，可能是觉得这些校验容易被绕过所以直接放弃治疗了吧哈哈。

总结起来，本文基于chrome源码，提出了一种更为通用的cronet组件证书校验的抓包方式，也更加直击cronet组件证书校验的核心。cronet的证书校验绕过可能比okhttp的还要简单，只要改8个字节就行，或者用frida hook MapCertStatusToNetError这个函数让他返回0就行。难点在于MapCertStatusToNetError函数的定位，这个可以通过各种方式去定位，小弟我采用的是字符串+编译相邻性原理定位的。

希望本文能对大家在https抓包的研究上提供一种新的思路。

————————————————————————————————————————————————
2023.8.3 更新
在实际中发现，有时候Verify函数里并没有调用MapCertStatusToNetError函数就直接返回了，观察源码后看到是：
 ![image](https://bbs.kanxue.com/upload/attach/202308/872365_9C493H8Z3HWDWXM.png)
直接调用了VerifyInternal这个虚函数，返回RV后有可能是非0值，同时verify->result并不符合后面的每一种条件，这样就会不经过MapCertStatusToNetError函数而直接返回。所以也可以定位到Verify函数之后，直接Hook Verify函数让他返回0（OK），这样更保险一点

---

# 回复

## 回复 by youxiaxy (#2)

*2023-7-13 07:45*

学习了。感谢分享

## 回复 by laodazhou (#3)

*2023-7-13 09:59*

![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 秋狝 (#4)

*2023-7-13 10:48*

哇哦![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by .KK (#5)

*2023-7-13 11:00*

很强~

## 回复 by exit\(0\) (#6)

*2023-7-13 11:05*

高人~阔以

## 回复 by 快乐的小跳蛙 (#7)

*2023-7-13 11:44*

大佬666

## 回复 by chengdrgon (#8)

*2023-7-13 12:53*

感谢分享，思路值得借鉴

## 回复 by huluxia (#9)

*2023-7-13 12:57*

大佬厉害！

## 回复 by hhhaiai (#10)

*2023-7-13 14:25*

牛p

## 回复 by 执法长老R0 (#11)

*2023-7-13 15:17*

不知道有没有侵权，路过的时候看到的。

支持正版，打击盗版。从我做起，从小事做起。从看雪做起。

![image](https://bbs.kanxue.com/upload/attach/202307/980197_3ME5457WUKFCPEK.jpeg)

## 回复 by 乐子人 (#12)

*2023-7-13 16:08*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。
>
>

咦？

## 回复 by mb_gtnrqjce (#13)

*2023-7-13 17:29*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。
>
>

人家又不是没贴原链接，加上自己的总结了而已。。。现在对侵权的定义已经这样了嘛？？？

## 回复 by codeoooo (#14)

*2023-7-13 19:45*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。
>
>

转载 贴个转载原链接 宣传一波 这也不行了？

## 回复 by SharsDela (#15)

*2023-7-14 11:09*

看过一本《更高更妙的物理》物理竞赛的书![image](https://bbs.kanxue.com/view/img/face/51.gif)

## 回复 by 一颗小草 (#16)

*2023-7-14 11:30*

分析的挺好的，我试验机android11，push到data/data/packname/lib下面替换发现没用，应该是系统有so缓存机制，不知道缓存在哪了，将apk解包替换重新打包安装即可。

## 回复 by 屠龙勇士潘森 (#17)

*2023-7-14 11:52*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。
>
>

卧槽 otto

## 回复 by 乐子人 (#18)

*2023-7-14 12:51*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  SharsDela](https://bbs.kanxue.com/user-772149.htm)
>
>  看过一本《更高更妙的物理》物理竞赛的书[em_51]
>
>

名称来源于此

## 回复 by 乐子人 (#19)

*2023-7-14 12:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  一颗小草](https://bbs.kanxue.com/user-973070.htm)
>
>  分析的挺好的，我试验机android11，push到data/data/packname/lib下面替换发现没用，应该是系统有so缓存机制，不知道缓存在哪了，将apk解包替换重新打包安装即可。
>
>

应该push到data/app/package/lib/arm64下吧

## 回复 by 执法长老R0 (#20)

*2023-7-14 14:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_gtnrqjce](https://bbs.kanxue.com/user-873264.htm)
>
>  人家又不是没贴原链接，加上自己的总结了而已。。。现在对侵权的定义已经这样了嘛？？？
>
>

转贴之前还是希望征求原作者同意，而不是直接转载。楼主发文章出来供大家学习参考学习，这是希望我们可以相互学习共同进步。

没有被原作者知晓、同意的情况下，做出的"转载"，而且还是收费的，我个人更愿意视其为"窃"。

个人这里觉得不太合适，君子爱财取之有道。而不是取之有"盗"。

以上均是本人的一些看法，如果与看官的看法冲突，请多多海涵，本人无意冒犯。

推荐几个别人想要转载之前的操作。

![image](https://bbs.kanxue.com/upload/attach/202307/980197_Z575M579M69P59R.jpg)![image](https://bbs.kanxue.com/upload/attach/202307/980197_RP9NQTBW784KH9E.jpg)

看雪的高级回复不能设置回复具体的人物对象。咱这里回复的是 13楼临时成员mb_gtnrqjce、14楼 codeoooo。

## 回复 by 大魔法狮子 (#21)

*2023-7-14 15:18*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。

6

## 回复 by 一颗小草 (#22)

*2023-7-14 15:20*

>
> [乐子人](https://bbs.kanxue.com/user-872365.htm)
>
>  应该push到data/app/package/lib/arm64下吧
>
>

我下载的最新版dy，只有v7库，push位置应该没错不知道为啥没反应，重打包没问题，还是感谢楼主分析

## 回复 by vay (#23)

*2023-7-15 11:44*

太强了

## 回复 by MsScotch (#24)

*2023-7-15 11:47*

>
> [执法长老R0](https://bbs.kanxue.com/user-980197.htm)
>
>  不知道有没有侵权，路过的时候看到的。支持正版，打击盗版。从我做起，从小事做起。从看雪做起。
>
>

啊，这拿来主义用的妙啊
一方面，“小弟都会”，另一方面，“菜菜们，买的不亏八”

## 回复 by Kare-chen (#25)

*2023-7-15 13:07*

好大哥，这个是啥版本，我看最新的版本好像有点不一样

## 回复 by 乐子人 (#26)

*2023-7-15 13:16*

>
> [Kare-chen](https://bbs.kanxue.com/user-933783.htm)
>
>  好大哥，这个是啥版本，我看最新的版本好像有点不一样
>
>
>

最新版本，前两天刚从应用商店下的

## 回复 by 乐子人 (#27)

*2023-7-15 13:18*

>
> [Kare-chen](https://bbs.kanxue.com/user-933783.htm)
>
>  好大哥，这个是啥版本，我看最新的版本好像有点不一样
>
>
>

看了一下，文章里用的版本是26.1

## 回复 by mb_vawulafi (#28)

*2023-7-17 12:29*

两个小白问题：
1. 通过交叉引用定位到引用这个字符串的函数，查看与他相邻的上一个函数  ==> 这一步能不能具体一点啊，总是找不到
2. 通过修改汇编指令，直接让他在入口处直接返回OK(0)：==> IDA怎么修改这个函数的汇编内容啊，不会影响其他地址吗

## 回复 by mb_uimobzwn (#29)

*2023-7-20 00:21*

太强了

## 回复 by KayaK-Z (#30)

*2023-7-25 20:01*

.rodata:000000000005BFCE        0000002F        C        Net.CertVerifier.NameNormalizationPrivateRoots

![image](https://bbs.kanxue.com/upload/attach/202307/949222_Z7YB2V4JKN8FR4J.jpg)

卡到这一步了，怎么找sub_2D013C的上一个函数呢。。

## 回复 by 乐子人 (#31)

*2023-7-27 23:11*

>
> [KayaK-Z](https://bbs.kanxue.com/user-949222.htm)
>
>  .rodata:000000000005BFCE &nbsp; &nbsp; &nbsp; &nbsp;0000002F &nbsp; &nbsp; & ...
>
>

转到text模式浏览汇编，找到上一个函数

## 回复 by 秋狝 (#32)

*2023-7-28 09:20*

下个版本更新，会把相关字符串加密吧

## 回复 by roysue (#33)

*2023-8-2 20:25*

兴致冲冲按照文章来跟 结果跟到ollvm里了 附上so

PS：这不是抖音的 这是幸福里app 一个找房的

![image](https://bbs.kanxue.com/upload/attach/202308/581423_WKY56FZ594SUBAH.jpg)![image](https://bbs.kanxue.com/upload/attach/202308/581423_FYH7JHYJZ3RR4EP.jpg)

上传的附件：
- libsscronet.so

（2.62MB，23次下载）

## 回复 by 乐子人 (#34)

*2023-8-2 22:38*

>
> [roysue](https://bbs.kanxue.com/user-581423.htm)
>
>  兴致冲冲按照文章来跟 结果跟到ollvm里了 附上so&nbsp;PS：这不是抖音的 这是幸福里app 一个找房的
>
>

Map函数应该是sub_19B3F8这个

## 回复 by 乐子人 (#35)

*2023-8-2 22:40*

>
> [roysue](https://bbs.kanxue.com/user-581423.htm)
>
>  兴致冲冲按照文章来跟 结果跟到ollvm里了 附上so&nbsp;PS：这不是抖音的 这是幸福里app 一个找房的
>
>

先找到Net.CertVerifier.NameNormalizationPrivateRoots字符串的引用，然后他物理上相邻的上一个函数里就是Verify函数了，里面能找到Map函数。

## 回复 by dfJerry (#37)

*2023-12-6 17:37*

cornet上层，应该有对应的Java接口可以调用把。它设置证书绑定，应该也是有java层的API？所以可以从Java层过掉证书校验吗？大佬有研究过吗

## 回复 by 橘子皮儿 (#38)

*2024-10-17 17:17*

现在的跟这个版本不太一样了，找不到map那个函数

## 回复 by 养只猫不好么 (#39)

*2024-10-29 16:01*

感谢分享

## 回复 by 4Chan (#40)

*2024-11-4 14:39*

取这个名字，高中物理竞赛至少三等奖

## 回复 by mb_tfdidxxx (#41)

*2025-6-11 18:41*

我发现我找到了对应的函数后，发现连libsscronet.so都没有加载呢，有没有大佬解惑一下

## 回复 by bluegatar (#42)

*2025-6-11 23:35*

非常棒啊，这个抓包方案

## 回复 by mb_pnlabahd (#43)

*2025-6-12 01:37*

Verify函数一定能通过字符串定位到吗
