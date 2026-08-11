---
title: '[原创]又一款通杀利器来袭，partserver，通杀版frida'
url: https://bbs.kanxue.com/thread-285628.htm
tid: 285628
author: 程序员小潘
date: '2025-02-19'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-08-11T08:39:59+00:00'
replies: 34
---

# 闲聊

24年开始，frida检测越来越强，已经从最初简单hook字符串再到重定向open函数，到后来的patch检测线程，但是到25年的今天，这些通通不管用了。parter在对多家国内国外加固厂商进行逆向研究，收集了一些未被公开的frida检测点，加上自己对源码的研究套出来的部分检测点，集成到partserver。有些厂商的检测思路真的非常刁钻，每一家基本都有自己的特色检测，有些甚至已经到了不改源码基本过不了的地步。跟part脱壳机一样，partserver走的是照样是通杀路线，已对大量国内样本进行测试，截至发帖日，测试的厂商样本包括25最新版爱加密，梆梆，娜迦，腾讯加固，网易易盾，阿里聚安全等等，包含以下app，这些app随便拿一个都能吊打现有的公开frida检测方案:

北京银行_v9.0.3_20250122_com.bankofbeijing.mobilebanking_爱加密企业.apk （通杀）
度小满_v10.2.0_20250121_com.duxiaoman.wallet_梆梆企业.apk（通杀）
个人所得税app_v2.1.6_20250130_cn.gov.tax.its_梆梆企业.apk（通杀）
滴滴出行_v7.0.0_20250119_com.sdu.didi.psnger.apk（通杀）
个人所得税app_v2.1.6_20250130_cn.gov.tax.its_梆梆企业.apk（通杀）
华夏银行20250122_梆梆企业.apk（通杀）
货拉拉司机版_v6.6.17_20250116_com.lalamove.huolala.driver_爱加密企业.apk（通杀）
交管12123_v3.2.0_20250120_com.tmri.app.main_网易易盾.apk（通杀）
交通银行_v9.1.0_20241217_com.bankcomm.Bankcomm_梆梆企业.apk（通杀）
宁波银行_v8.0.3_20250209_com.nbbank_梆梆企业.apk（通杀）
拍拍贷v10.6.7_20241030_com.ppdai.loan_爱加密企业.apk（通杀）
泰隆银行_com.tlbank_梆梆+阿里.apk（通杀）
翼支付_v10.94.10_20250123_com.chinatelecom.bestpayclient_爱加密企业.apk（通杀）
中国工商银行_v10.0.1.2.3_20250108_com.icbc_梆梆企业.apk（通杀）
中国联通_v12.1_20250119_com.sinovatech.unicom.ui_梆梆企业.apk（通杀）
中国农业银行_v10.0.0_20250118_com.android.bankabc_梆梆企业.apk（通杀）
中国平安好车主_v5.54.3_20250209_com.pingan.carowner_娜迦+阿里聚安全.apk（通杀）
com.zhenxi.hunter_v5.8.6_知名检测工具.apk（通杀）

# 部分截图：

北京银行
 ![北京银行](https://bbs.kanxue.com/upload/attach/202502/877942_9ECVGQN7X9S59EV.webp)
货拉拉司机版
 ![货拉拉司机版](https://bbs.kanxue.com/upload/attach/202502/877942_SVK5Z8B2XEQQTBQ.webp)
建设银行
 ![建设银行](https://bbs.kanxue.com/upload/attach/202502/877942_26DQN32648PENX7.webp)
交管12123
 ![交管12123](https://bbs.kanxue.com/upload/attach/202502/877942_CY5QJRS7HVJ25Y8.webp)
中国电信
 ![中国电信](https://bbs.kanxue.com/upload/attach/202502/877942_VNFCHGJTVHEUZ8F.webp)
中国平安好车主
 ![中国平安好车主](https://bbs.kanxue.com/upload/attach/202502/877942_4FDTAAD8F7TCFSB.webp)

# 小结：

后续360通杀版会适配完成，会一并发布。具体检测点以及绕过方式就不公开了，实在需要可以联系我定制。

---

# 回复

## 回复 by mb_ixzqfdot (#2)

*2025-2-19 01:04*

emmmmm

## 回复 by 黑屏 (#3)

*2025-2-19 08:02*

广告

## 回复 by 程序员小潘 (#4)

*2025-2-19 08:46*

>
> [黑屏](https://bbs.kanxue.com/user-589509.htm)
>
>  广告
>
>

我格局小，不想开源

## 回复 by 黑屏 (#5)

*2025-2-19 09:25*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  我格局小，不想开源
>
>

那就别发出来不就行了

## 回复 by 黑屏 (#6)

*2025-2-19 09:26*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  我格局小，不想开源
>
>

自己闷头偷偷用就行了，还用这宣告天下了？？

## 回复 by wangzehua (#7)

*2025-2-19 09:51*

只要你注入了app的进程空间，还是能检测![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 九天666 (#8)

*2025-2-19 10:47*

唯独没见你发360企业版的，你说的这些我也都能过，并且也能过360企业版的，遇到crc检测你就老实了

## 回复 by New对象处 (#9)

*2025-2-19 14:04*

4篇贴，4篇广告

## 回复 by 程序员小潘 (#10)

*2025-2-19 14:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cemqwsbh](https://bbs.kanxue.com/user-947335.htm)
>
>  唯独没见你发360企业版的，你说的这些我也都能过，并且也能过360企业版的，遇到crc检测你就老实了
>
>

360用的是一个开源项目的检测libc的crc方法，这套hunter也在用，有办法绕过的

## 回复 by 程序员小潘 (#11)

*2025-2-19 14:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  New对象处](https://bbs.kanxue.com/user-807696.htm)
>
>  4篇贴，4篇广告
>
>

技术都是需要资本去驱动

## 回复 by 程序员小潘 (#12)

*2025-2-19 14:35*

>
> [wangzehua](https://bbs.kanxue.com/user-377240.htm)
>
>  只要你注入了app的进程空间，还是能检测[em_014]
>
>

有攻就有防嘛

## 回复 by 九天666 (#13)

*2025-2-19 17:36*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  360用的是一个开源项目的检测libc的crc方法，这套hunter也在用，有办法绕过的
>
>

并不是哦，你想想看只要注入了frida为什么后面都打不开360加固的app呢，这个和libc的检测没一点关系。我都说了我魔改的frida，360企业壳的也能过，你得去分析了才知道。

## 回复 by 程序员小潘 (#14)

*2025-2-19 18:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cemqwsbh](https://bbs.kanxue.com/user-947335.htm)
>
>  并不是哦，你想想看只要注入了frida为什么后面都打不开360加固的app呢，这个和libc的检测没一点关系。我都说了我魔改的frida，360企业壳的也能过，你得去分析了才知道。
>
>

就是对可执行段做了checksum

## 回复 by mb_iunhvspv (#15)

*2025-2-20 09:40*

不明觉厉感觉

## 回复 by ldehua (#16)

*2025-2-24 13:25*

4篇贴，4篇广告，建议别再发了

## 回复 by 上官兮唐 (#17)

*2025-2-24 13:38*

这就是韭菜贴，众所周知，这些都已经公开的

## 回复 by 小黄鸭爱学习 (#18)

*2025-2-24 15:12*

纯广告无技术 看雪作为技术论坛也是烂烂的，建议加精所有广告帖子。

## 回复 by 小黄鸭爱学习 (#19)

*2025-2-24 15:12*

@看雪 进来加精帖子

## 回复 by 珍惜Any (#20)

*2025-2-24 15:38*

别拿hunter去做广告，检测代码没超过20行，被你还拿来比较，咋想的....

## 回复 by 程序员小潘 (#21)

*2025-2-24 21:10*

>
> [上官兮唐](https://bbs.kanxue.com/user-953118.htm)
>
>  这就是韭菜贴，众所周知，这些都已经公开的
>
>

这位兄弟~你开个帖子，把我提的厂商的frida检测过了，我立马删帖永不发帖

## 回复 by 笑对VS人生 (#22)

*2025-2-24 21:24*

前排吃瓜看热闹，哈哈

## 回复 by K4NG (#23)

*2025-2-26 17:08*

**不懂就问和开源免费的有啥区别?**

hluda

florida

strongR-frida-android

## 回复 by mb_rewimxhj (#24)

*2025-2-27 12:57*

别丢人现眼了，这些有手就能过

## 回复 by 程序员小潘 (#25)

*2025-2-27 13:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rewimxhj](https://bbs.kanxue.com/user-873375.htm)
>
>  别丢人现眼了，这些有手就能过
>
>

去发个贴，把你的成果秀出来，再来喷吧，不是有张嘴就行

## 回复 by 万里星河 (#26)

*2025-2-27 14:19*

但凡有手写frida的实力 也不至于怕被检测![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by 上官兮唐 (#27)

*2025-3-3 07:57*

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>
>  这位兄弟~你开个帖子，把我提的厂商的frida检测过了，我立马删帖永不发帖
>
>

我不开帖是不想分享方法，你开贴也没发代码，纯秀肌肉炫耀

## 回复 by mb_zipzflmn (#28)

*2025-3-8 20:27*

北京银行9.0.3的版本，注入检测也能绕过么？

## 回复 by Yangser (#29)

*2025-3-11 19:27*

难绷

## 回复 by 人生五碗面 (#30)

*2025-3-16 14:39*

技术变现可以理解，博主请问怎么联系

## 回复 by 程序员小潘 (#31)

*2025-3-17 15:01*

>
> [人生五碗面](https://bbs.kanxue.com/user-760039.htm)
>
>  技术变现可以理解，博主请问怎么联系
>
>

Q328366802

## 回复 by 程序员小潘 (#32)

*2025-3-17 15:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_zipzflmn](https://bbs.kanxue.com/user-1025686.htm)
>
>  北京银行9.0.3的版本，注入检测也能绕过么？
>
>

我这版本秒过

## 回复 by 玺子 (#33)

*2025-5-4 17:54*

什么价格啊

## 回复 by huangbof (#34)

*2025-5-5 03:52*

>
> [玺子](https://bbs.kanxue.com/user-969850.htm)
>
>  什么价格啊
>
>

要钱不是犯法？

## 回复 by 我不是卷王 (#35)

*2025-5-5 13:57*

已举报
