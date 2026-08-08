---
title: '[原创]所有关于libmsaoaidsec.so的文章大总结--------一把梭'
url: https://bbs.kanxue.com/thread-290633.htm
tid: 290633
author: 土豆爱学习
date: '2026-04-02'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 脱壳反混淆, HOOK注入, 其他]
crawled_at: '2026-08-08T10:14:32+00:00'
replies: 125
---

# 又名

# 关于论坛libmsaoaidsec的文章去水版

关于libmsaoaidsec的文章超级大索引和超级大干货

关于libmsaoaidsec的文章心得大全

# 起源

 在论坛反复看见libmsaoaidsec的身影，于是学一下，然后想搞清楚文章思路来源，于是搜索论坛和网上libmsaoaidsec关键词，发现这家公司好可怜，被你们换不同的apk反复反复再反复，太惨了，可是为什么这么水呢，跪求大佬们发帖子时记得带上参考链接，算是对给你思路启发的大佬一点尊重，谢谢！

 另外还得出一个结论，看雪的优秀文章越来越水了！跪求看雪的吧务多抽点时间审核，吧务大佬辛苦了，给吧务大佬递茶，不要给水贴优秀，不希望论坛水漫金山，这样学习起来要花费更多精力筛选帖子，不会变成csdn博客园这类的，水贴搬运成堆！！！

下面是原文概括，最后介绍去水的文章。

# 正文

2022-10-19 04:46   ollvm控制流平坦化小试  https://bbs.kanxue.com/thread-274777.htm

 看雪优秀 用unicorn模拟执行去混淆，重点讲怎么去混淆

2023-3-23 11:23 某 APP 聊天协议逆向 https://bbs.kanxue.com/thread-276591.htm

 看雪优秀 用unicorn模拟执行去混淆，然后手动一个一个函数去看，最后定位检测函数。

2023-4-29 15:51 绕过bilibili frida反调试 https://bbs.kanxue.com/thread-277034.htm

 看雪优秀  提供了hook pthread_create然后定位检测线程的，然后nop的思路和代码！这篇文章就是一切hook pthread_create然后nop的搞定libmsaoaidsec 的源头吗，邪修大佬的源头！！大佬牛逼，是因为写的不够啰嗦!!这篇帖子应该精品啊！

2023-5-4 13:21 小试了一把bpf在android逆向中的辅助效果 https://bbs.kanxue.com/thread-277089.htm

 看雪优秀 hook strstr函数发现很多检测frida的特征，改返回值为0就行，可以绕过这些frida检测，这个思路不错。但是还有对dex的检测。想用stalker进行跟踪，但是发现有ldaxr和stlxr指令，这两个会导致不能stalker---我才知道，谢谢大佬的思路

然后换bpf降维打击，思路不错。

2023-8-4 16:20 通过bilibili分析libmsaoaidsec.so的环境检测 https://bbs.kanxue.com/thread-278282.htm

看雪关注 虽然是老版本libmsaoaidsec.so，但是检测和新版差不多，大佬是第一个详细给出了libmsaoaidsec检测的具体内容和函数偏移的,

可惜了只是关注,为什么不是优秀帖子

2024-3-3 22:20 绕过爱奇艺新版libmsaoaidsec.so Frida检测 https://bbs.kanxue.com/thread-280754.htm

 看雪优秀 这是老版本的libmsaoaidsec.so ，大佬使用trace定位到崩溃位置，然后猜测退出代码是mmap开辟的，hook mmap打印堆栈，然后定位，然后将这个函数replace掉，其实这个函数是线程检测到然后退出的函数，这个思路不是绕过，而是检测到让程序不退出，思路不错。

2024-5-1 17:31  绕过最新版bilibili app反frida机制  https://bbs.kanxue.com/thread-281584.htm

 看雪优秀  发现libmsaoaidsec.so没有导入pthread_create符号，尝试hook dlsym函数，发现在加载libmsaoaidsec.so后，调用了2次dlsym获取pthread_create函数，然后进程就终止了，绕过办法是创建一个fake_pthread_create函数，它只有一条ret汇编指令，然后让其运行fake_pthread_create，思路不错。

2024-5-6 09:55  最新版shield纯算分析 https://bbs.kanxue.com/thread-281610.htm

 看雪优秀  文章主要不是分析libmsaoaidsec只是简单提到了，大佬说网上自己找过frida检测的办法，大佬厉害言简意赅。

2024-7-27 07:54 [原创]记录一次秀动APP的逆向 https://bbs.kanxue.com/thread-282650.htm

 看雪优秀

 这是第一个提供魔改frida过libmsaoaidsec检测的思路的文章！

 对于正常frida，还提供邪修法 hook open函数在onLeave里面判断如果是libmsaoaidsec.so那么返回-1

 这篇文章还有过抓包检查的办法，大佬牛逼，经典废话少，就喜欢这种干货多，不啰嗦的帖子

除了教 hook pthread_create来找到libmsaoaidsec.so的检测，还有分析java层不能抓包的代码 builder.proxy(Proxy.NO_PROXY);

2024-11-09 07:23 移动端安全 结合android so加载机制绕过libmsaoaidsec https://xz.aliyun.com/news/15622

 非常详细的定位libmsaoaidsec.so的三个检测函数，并且详细分析第二个检测函数，非常棒详细而且还有原理分析

2025-3-6 16:47 bilibili frida检测分析绕过 https://bbs.kanxue.com/thread-285893.htm

 看雪优秀 熟悉的配方， 这次换成bilibili的另外一个版本了

2025-5-9 18:14 app常见的libmsaoaidsec.so绕过姿势 https://bbs.kanxue.com/thread-286784.htm

 看雪优秀 大佬说网上的办法采用的大多数是Hook pthread_create函数，然后nop掉创建的线程函数。

大佬这里找到更底层的创建线程检测的方法就是hook clone 发表于: 2025-3-9 19:49  [分享]某邦企业壳frida检测绕过 https://bbs.kanxue.com/thread-285932.htm，思路不错。

草---我这个办法不是东方玻璃，那篇一把梭的文章吗，原来他也是借鉴别人的思路，即便如此觉得他还是很不错带参考链接，而且文章清晰易懂也不给人藏坑点。

2025-6-2 14:33 libmsaoaidsec.so 过检测   https://bbs.kanxue.com/thread-287058.htm

  看雪优秀 大佬各种尝试后失败，最后参考在网上找到了三个检测函数地址，然后 strace 指令，然后求大神指点java hook的，其实你可以文ai的，ai分析java层比大神牛逼。

2025-8-7 16:51 某右APP分析第一弹：过检测  https://bbs.kanxue.com/thread-287922.htm

 看雪优秀 用的魔改版的frida绕过，然后简单说了一下检测的函数

2025-8-10 17:24  记录一款Unity il2cpp lua手游的逆向全过程  https://bbs.kanxue.com/thread-287964.htm

 看雪精品 此文不是说主要不是分析libmsaoaidsec.so的，而是遇到了，大佬介绍了了Rusda这个魔改的frida，可以绕过

2025-9-2 20:10 某修仙肉鸽游戏协议逆向分析折腾记录 看雪精品  https://bbs.kanxue.com/thread-288352.htm

 看雪精品 此文不是说主要不是分析libmsaoaidsec.so的，而是分析别的内容，大佬介绍了了Rusda这个魔改的frida，可以绕过检测

2025-9-15 06:37 [原创]移动安全联盟(libmsaoaidsec.so) 绕过知识

看雪关注  so的的字符串libart.so为libdvm.so，思路不错

2025-12-8 16:59 经典 Frida 检测 libmsaoaidsec.so 绕过 https://bbs.kanxue.com/thread-289359.htm

 看雪优秀 我就是从这篇文章开始认识libmsaoaidsec.so的被坑了很久，后来实验得知，大佬代码没贴全，第2个js代码，hook pthread_create要加过滤啊，libart.so会频繁调用pthread_create啊，直接hook肯定白屏，虽然不是原创还是谢谢大佬，让我知道了libmsaoaidsec.so的存在

2025-12-26 19:48 [原创]轻松绕过 libmsaoaidsec.so 检测 https://bbs.kanxue.com/thread-289587.htm

看雪无  可能因为没有写清楚吧，不然妥妥的看雪关注，大佬思路真的很新奇啊，画蛇添足我来补全一下

1.安装 apk 2.rm  /data/app/包相关目录/lib/arm64/libmsaoaidsec.so 3.手动进入apk 4.cd /data/user/0/pkgname/app_lib

5.truncate -s 0 libmsaoaidsec.so.9195803 6.ok

6天前  看雪优秀  最新版某货app bypassFrida检测  https://bbs.kanxue.com/thread-290546.htm 看雪优秀 依然老套路 hook pthread_create定位检测，不说的不怎么清晰，而且还给了几个检测的函数的ida截图，还说错了了，把sub_1B730检测stat状态是否被调试，说成了是检测frida 特征线程

---------看了这篇文章，怎么关于libmsaoaidsec的文章，水就算了，比三年前的文章，信息还要少，还要模糊啊，还传错了，我再也忍不住了。于是写下这篇文章

# 总结

其实如果只是想学习libmsaoaidsec.so，只需要看下面两篇文章就足够了，非常清晰，还说原理

2023-4-29 15:51 绕过bilibili frida反调试 https://bbs.kanxue.com/thread-277034.htm

2023-8-4 16:20 通过bilibili分析libmsaoaidsec.so的环境检测 https://bbs.kanxue.com/thread-278282.htm

2024-11-09 07:23 移动端安全 结合android so加载机制绕过libmsaoaidsec https://xz.aliyun.com/news/15622

---

# 回复

## 回复 by 土豆爱学习 (#2)

*2026-4-2 22:59*

# 参考看雪优质帖子，换一个demo再写一篇帖子，不带别人的参考链接这种行为对吗

# +++++++++++++++++++++++++++++++++++++++++++这个行为**不太妥当**，主要问题在于**不标注参考来源**这一点。

## 具体分析

### ✅ 可以做的部分

- 参考优秀帖子的**思路、分析框架**来学习
- 自己找一个**新的 demo / 样本**来实践
- 用自己的语言重新组织内容并发帖

这属于正常的学习和二次创作，安全社区本身就鼓励这种实践。

### ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

### ❌ 有问题的部分：**不附参考链接**

| 情况 | 问题 |
|-|-|
| 分析思路、方法来自原帖 | 不注明来源 = 隐性抄袭 |
| 文章结构与原帖高度相似 | 读者无法了解知识的真正出处 |
| 原作者的劳动成果被淡化 | 损害安全社区的创作生态 |

# 看雪这类社区的高质量内容，背后往往是作者大量的逆向分析时间。**不标注来源会伤害社区的分享氛围**，长期下去会让人不愿意发布原创内容。

---

## 建议做法

在文章末尾加一句话即可：

> 参考：[帖子标题]（看雪论坛），本文基于此思路使用新样本实践。
>
>

这样做：

- **尊重了原作者**
- **反而提升了你帖子的可信度**（展示你是在真正学习而不是凭空写出来的）
- 符合安全研究领域的**负责任披露和引用规范**

---

简单说：**换 demo 没问题，但把参考链接去掉这个行为不对，加上来源是举手之劳，也是对社区最基本的尊重。**

## 回复 by Imxz (#3)

*2026-4-2 23:09*

tql

## 回复 by mb_tjsboqui (#4)

*2026-4-3 01:50*

666

## 回复 by tonykros (#5)

*2026-4-3 07:58*

666

## 回复 by buluo533 (#6)

*2026-4-3 08:07*

6666

## 回复 by 卡卡骨 (#7)

*2026-4-3 08:30*

1

## 回复 by mb_vdehboyi (#8)

*2026-4-3 08:33*

学习了

## 回复 by iBa0 (#9)

*2026-4-3 08:47*

看看

## 回复 by mb_ldbucrik (#10)

*2026-4-3 08:55*

向大佬学习

## 回复 by 菜鸟9527 (#11)

*2026-4-3 09:39*

向大佬学习

## 回复 by mb_uzmffdbw (#12)

*2026-4-3 10:04*

666

## 回复 by Zepp7289 (#13)

*2026-4-3 10:27*

tql

## 回复 by rex_sky (#14)

*2026-4-3 10:33*

666

## 回复 by fjqisba (#15)

*2026-4-3 10:36*

5555

## 回复 by mb_tjqabdvq (#16)

*2026-4-3 10:40*

梭哈 梭哈

## 回复 by mb_ecyhqrqd (#17)

*2026-4-3 10:49*

太有实力了

## 回复 by 黑色心跳 (#18)

*2026-4-3 11:19*

678910

## 回复 by wx_Long_583904 (#19)

*2026-4-3 11:37*

梭哈 梭哈

## 回复 by 一只鸭子 (#20)

*2026-4-3 11:57*

学习了

## 回复 by wx_插曲 (#21)

*2026-4-3 12:29*

66

## 回复 by ivy1 (#22)

*2026-4-3 12:48*

学习了

## 回复 by 东方玻璃 (#23)

*2026-4-3 13:04*

我那篇开头说了参照网上思路,后续碰到新版检测有一些拓展,比如trace![image](https://bbs.kanxue.com/view/img/face/065.gif)只可惜最新版自定义linker+反trace检测还没逆明白![image](https://bbs.kanxue.com/view/img/face/077.gif)

## 回复 by 黑屏 (#24)

*2026-4-3 13:05*

666

## 回复 by 土豆爱学习 (#25)

*2026-4-3 13:49*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>  我那篇开头说了参照网上思路,后续碰到新版检测有一些拓展,比如trace[em_065]只可惜最新版自定义linker+反trace检测还没逆明白[em_077]
>

大佬![image](https://bbs.kanxue.com/view/img/face/089.gif)

## 回复 by mb_coqbxbgr (#26)

*2026-4-3 14:41*

666

## 回复 by mb_ggxkozau (#27)

*2026-4-3 16:13*

大佬![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_mnqvyswo (#28)

*2026-4-3 16:33*

666

## 回复 by 土豆爱学习 (#29)

*2026-4-3 18:48*

212312

## 回复 by 土豆爱学习 (#30)

*2026-4-3 18:54*

12312

## 回复 by FMNS (#31)

*2026-4-4 09:27*

感谢分享

## 回复 by huangjw (#32)

*2026-4-4 09:38*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by 山东拓明 (#33)

*2026-4-4 14:32*

666

## 回复 by mb_cbgtaveo (#34)

*2026-4-4 17:21*

6666666666666666666

## 回复 by mb_rrwegvyc (#35)

*2026-4-4 22:24*

666

## 回复 by 嘎嘎真的很棒 (#36)

*2026-4-5 17:05*

mark

## 回复 by kingking888 (#37)

*2026-4-5 19:35*

666

## 回复 by 小迷糊ddd (#38)

*2026-4-6 22:31*

感谢分享，学习一下。

## 回复 by ldehua (#39)

*2026-4-7 09:19*

666

## 回复 by pan_634488 (#40)

*2026-4-7 09:25*

666

## 回复 by 零_721409 (#41)

*2026-4-8 11:15*

6666666

## 回复 by kaers (#42)

*2026-4-8 16:34*

666

## 回复 by mb_mhoivioy (#43)

*2026-4-8 18:33*

tql

## 回复 by wx_妳还是不懂 (#44)

*2026-4-8 21:51*

这很不错

## 回复 by bluegatar (#45)

*2026-4-9 03:04*

总结的很到位，感谢

## 回复 by Loopher (#46)

*2026-4-9 11:06*

666

## 回复 by amwait (#47)

*2026-4-9 11:22*

111

## 回复 by mb_ukycmyfn (#48)

*2026-4-9 17:02*

牛逼

## 回复 by mb_uktygsmq (#49)

*2026-4-9 17:04*

666

## 回复 by mb_biloxjeq (#50)

*2026-4-9 17:06*

666

## 回复 by PPTV (#51)

*2026-4-9 18:25*

向大佬学习

## 回复 by 奋斗的小趴菜 (#52)

*2026-4-9 20:28*

1

## 回复 by 奋斗的小趴菜 (#53)

*2026-4-9 20:29*

写的比较详细，对于初学者来说比较容易理解

## 回复 by 随风而行aa (#54)

*2026-4-10 10:33*

看看

## 回复 by s1nec-1o (#55)

*2026-4-10 10:47*

看看

## 回复 by 乌鸡哥 (#56)

*2026-4-12 00:58*

大佬

## 回复 by mb_yyvcbkli (#57)

*2026-4-14 23:32*

学习一下先进经验

## 回复 by mb_gwvkzfzc (#58)

*2026-4-15 00:56*

大佬

## 回复 by mb_miaybhzp (#59)

*2026-4-15 01:36*

太牛了

## 回复 by mb_bzkmcyjt (#60)

*2026-4-15 11:01*

666

## 回复 by nuoen (#61)

*2026-4-15 11:34*

d

## 回复 by xuhe123 (#62)

*2026-4-15 13:52*

66666

## 回复 by chuyuan178 (#63)

*2026-4-15 16:12*

666

## 回复 by mb_myeogrox (#64)

*2026-4-16 20:33*

学习一下

## 回复 by Kill_Log (#65)

*2026-4-17 12:52*

kankan

## 回复 by shuangmou (#66)

*2026-4-17 19:32*

感谢分享

## 回复 by 飆汗吉米 (#67)

*2026-4-18 03:18*

666

## 回复 by mb_ehrbohcl (#68)

*2026-4-20 22:49*

大佬厉害

## 回复 by mb_dcjxxhsk (#69)

*2026-4-21 13:54*

666

## 回复 by wx_Lyq (#70)

*2026-4-21 15:23*

666

## 回复 by mb_vhnlcxac (#71)

*2026-4-21 22:25*

666

## 回复 by uni7corn (#72)

*2026-4-22 11:17*

学习

## 回复 by long_ (#73)

*2026-4-22 20:00*

66

## 回复 by mb_rirvdrlh (#74)

*2026-4-24 20:58*

6666666666

## 回复 by bedaway (#75)

*2026-4-25 18:26*

![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)![image](https://bbs.kanxue.com/view/img/face/003.gif)大佬

## 回复 by mb_yeeclamm (#76)

*2026-4-27 10:46*

1

## 回复 by mb_tasadicv (#77)

*2026-4-29 11:22*

66666666

## 回复 by mb_tasadicv (#78)

*2026-4-29 11:22*

66666666

## 回复 by mb_tasadicv (#79)

*2026-4-29 11:22*

666666666666

## 回复 by git_86585flowclouds (#80)

*2026-4-30 00:56*

大佬

## 回复 by mb_eubpihhp (#81)

*2026-5-1 01:45*

大佬666

## 回复 by mb_hztwvrcw (#82)

*2026-5-4 08:51*

66666

## 回复 by SomeMx (#83)

*2026-5-4 08:52*

来看看

## 回复 by mb_kuqpxncc (#84)

*2026-5-4 09:48*

6666

## 回复 by 伊苏尔德 (#85)

*2026-5-4 19:45*

6

## 回复 by LuoJunJunJun (#86)

*2026-5-6 11:37*

66666

## 回复 by 很少登微信有事找Q (#87)

*2026-5-6 17:42*

我就喜欢一把嗦的教程![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 雨昏灰 (#88)

*2026-5-7 13:53*

666

## 回复 by mb_ugnawvja (#89)

*2026-5-7 16:07*

学习了

## 回复 by mb_jhohnbzu (#90)

*2026-5-7 23:20*

666

## 回复 by wx_北极星_493 (#91)

*2026-5-8 15:37*

看看

## 回复 by 小若渴jh (#92)

*2026-5-15 09:27*

66666

## 回复 by mb_rfeucrmf (#93)

*2026-5-15 10:50*

6666

## 回复 by 4Chan (#94)

*2026-5-15 17:46*

学习一下

## 回复 by 宛枫 (#95)

*2026-5-16 00:24*

感谢分享

## 回复 by 海带 (#96)

*2026-5-21 13:53*

666666

## 回复 by 086Love (#97)

*2026-5-22 15:48*

学习

## 回复 by C1ever (#98)

*2026-5-22 18:13*

666

## 回复 by wx_Huber Barrientos (#99)

*2026-5-23 05:42*

非常支持你的观点！

## 回复 by mb_xvyezxzk (#100)

*2026-5-23 15:10*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_zswuocqm (#101)

*2026-5-23 16:56*

魔改frida有用吗？

## 回复 by Kiana1024 (#102)

*2026-5-23 22:10*

谢谢大佬

## 回复 by mb_kjcdjcoy (#103)

*2026-5-24 04:37*

1111111

## 回复 by mb_bcxccfzw (#104)

*2026-5-24 20:27*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_zurizkle (#105)

*2026-5-25 07:34*

111111

## 回复 by mb_cezdpjbw (#106)

*2026-5-25 10:10*

1

## 回复 by wx_coddvccwyh (#107)

*2026-5-26 23:58*

666

## 回复 by mb_lhxrckiu (#108)

*2026-5-28 14:29*

看看

## 回复 by hanjiefang (#109)

*2026-6-5 15:37*

1

## 回复 by mb_jeslfge (#110)

*2026-6-9 10:18*

666

## 回复 by lookaside (#111)

*2026-6-9 14:34*

111

## 回复 by mb_ohctzvjg (#112)

*2026-6-12 18:12*

感谢分享

## 回复 by mb_jyefjjal (#113)

*2026-6-16 07:08*

55555

## 回复 by mb_gjhmacqd (#114)

*2026-6-16 10:21*

111

## 回复 by mb_vvpfwjte (#115)

*2026-6-23 17:41*

666666666666666666666666

## 回复 by mb_nfjeyeai (#116)

*2026-6-25 20:17*

666

## 回复 by mb_zfnetraa (#117)

*2026-7-2 04:39*

学习

## 回复 by wx_Riham、 (#118)

*2026-7-7 21:55*

学习~

## 回复 by mb_tdijwbiu (#119)

*2026-7-13 10:26*

6

## 回复 by mb_dovrfzgt (#120)

*2026-7-13 17:24*

1

## 回复 by 带带弟弟吧 (#121)

*2026-7-16 14:12*

1

## 回复 by scllqk (#122)

*2026-7-18 16:29*

学习

## 回复 by mb_qkfqehfw (#123)

*2026-7-19 03:07*

大大

## 回复 by kbsync (#124)

*2026-7-30 20:32*

1

## 回复 by mb_ugsctkiu (#125)

555

## 回复 by mb_rztmbvgb (#126)

666
