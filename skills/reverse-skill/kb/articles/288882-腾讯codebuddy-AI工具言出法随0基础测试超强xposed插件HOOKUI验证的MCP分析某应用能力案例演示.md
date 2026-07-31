---
title: 腾讯codebuddy AI工具言出法随0基础测试超强xposed插件HOOKUI验证的MCP分析某应用能力案例演示
url: https://bbs.kanxue.com/thread-288882.htm
tid: 288882
author: 情迁
date: '2025-10-22'
tags: [Android安全, 逆向分析, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T15:28:37+08:00'
replies: 91
---

没有安卓root机的朋友可以直接搞个模拟器 装xposed测试 hookui的能力
我这里是用的网易云模拟器

nodejs +codebuddy + xposed环境的hookui 没有用到其它工具也没进行脱壳。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_HYDQ2DDTWEHPUQB.webp)
mcp添加方法：

这里使用8965端口也就是apkture测试

| 1234567 | `C:\src\hookui>codebuddy mcp add` `-``-``transport sse apkture1 http:``/``/``192.168``.``2.45``:``8965``/``sse``Added sse MCP server apkture1 with URL: http:``/``/``192.168``.``2.45``:``8965``/``sse  to local config``File` `modified: C:\Users\Administrator\.codebuddy.json [project: c:\src\hookui]` `C:\src\hookui>codebuddy mcp` `list``Checking MCP server health...``apkture1: http:``/``/``192.168``.``2.45``:``8965``/``sse (SSE)` `-` `✓ Connected` |
|-|-|

手机端也行 Termux
`pkg install python nodejs clang git vim openssh` 就能装好nodejs了
然后
`npm install -g @tencent-ai/codebuddy-code`装好codebuddy命令

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_8H3XVWU5TATJHAH.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_45B2Q4BCDJHQYVM.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_MRXVH4KTRMHAMMZ.webp)

手机端mcp 调用太费劲了,还是演示电脑的. 所以下面的图片都是电脑端的测试截图哈,
首先我发的是：调用mcp 获取应用列表 其实我想说的是获取当前应用信息
 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_AHQ2KUXK7CQRMAQ.webp)

我后面提问 ：当前应用你无法知道吗？ 可以看到它成功的知道了 当前mcp所挂载在的应用

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_JEQYSRYGRABF9Z7.webp)

我提问：> 当前界面信息

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_E3BC98HQ55FV8KD.webp)

接下来 我提问：让他修改当前界面文字最新发现

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_TXVQJKPCHVQDNTZ.webp)

还能直接弹出原始对话框

| 12345678910111213 | `/``/` `使用HOOKUI的postDelayed在UI线程执行``HOOKUI.postDelayed(function() {``var currentActivity` `=` `HOOKUI.getCurrentActivity();``if` `(currentActivity) {``var dialog` `=` `new android.app.AlertDialog.Builder(currentActivity)``.setTitle(``"看雪论坛"``)``.setMessage(``"HOOKUI MCP 对话框"``)``.setPositiveButton(``"确定"``, null)``.create();` `dialog.show();``}``},` `100``);``", action: "``execute")` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_XXBQC7QZG9HW2EP.webp)

分析当前界面字段等信息 来推测逻辑

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_RXXZ2MB684NTRXZ.webp)
可以看到成功推测出了。

 ![图片描述](upload/tmp/769855_XRUQU ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_865BP7EVAK2R9MC.webp)24QVBXQAXP.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_45HU6R5NFRP2DMV.webp)
全程没有用到分析工具，

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_7N36YVCCYJ28878.webp)

最后关于js的可能比较弱 claude code感觉更强一些，建议把整个文档的内容下载下来让他学习 然后让他通过mcp 直接执行

https://github.com/lozn00/hookui_ability

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_Y34Y7B86C46EZ8K.webp)
我让他分析全局application结果 回答的结果意想不到哈

 ![图片描述](https://bbs.kanxue.com/upload/attach/202510/769855_GYUCHBBGVGNEH8G.webp)

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-10-22 19:48*

yyds,太强了

## 回复 by 黑屏 (#3)

*2025-10-23 08:06*

66

## 回复 by mb_mrjjcxgk (#4)

*2025-10-23 10:03*

66

## 回复 by ldehua (#5)

*2025-10-23 11:45*

66

## 回复 by Imxz (#6)

*2025-10-24 18:00*

sql

## 回复 by git_56402Syy040316 (#7)

*2025-10-24 18:06*

1

## 回复 by Ace_Heng (#8)

*2025-10-24 18:43*

56666

## 回复 by 魔童 (#9)

*2025-10-26 10:32*

66666666

## 回复 by zylyy (#10)

*2025-10-26 11:04*

666666666

## 回复 by wx_快乐一生。 (#11)

*2025-10-26 23:08*

支持一个

## 回复 by mb_qardwonv (#12)

*2025-10-27 08:39*

nb

## 回复 by zouzhiqiang (#13)

*2025-10-27 09:48*

6666

## 回复 by 希梦☆奈何 (#14)

*2025-10-27 11:07*

666

## 回复 by 晨曦遇晓 (#15)

*2025-10-27 14:23*

666

## 回复 by mb_oroygnqo (#16)

*2025-10-27 15:11*

6

## 回复 by Thehepta (#17)

*2025-10-28 14:07*

1

## 回复 by wx_huhu_859 (#18)

*2025-10-28 14:15*

11

## 回复 by MaYil (#19)

*2025-10-28 14:28*

感谢分享

## 回复 by mb_fidppcok (#20)

*2025-10-29 02:30*

感谢分享

## 回复 by mb_tvmcbdnl (#21)

*2025-10-29 10:38*

666666666

## 回复 by Snowman_Liam (#22)

*2025-10-29 12:01*

666666

## 回复 by xinhu (#23)

*2025-10-29 17:16*

666

## 回复 by SInnon (#24)

*2025-10-29 17:30*

666

## 回复 by mb_xflcgdik (#25)

*2025-10-30 15:59*

6

## 回复 by 苏幻墨 (#26)

*2025-10-30 16:27*

666666666

## 回复 by 小青峰 (#27)

*2025-11-4 20:00*

666

## 回复 by TeddyYu (#28)

*2025-11-5 11:10*

现在AI越来越强

## 回复 by 随风而行aa (#29)

*2025-11-5 11:31*

看看

## 回复 by MikotoDev (#30)

*2025-11-7 13:47*

666

## 回复 by baichisi (#31)

*2025-11-7 15:26*

66

## 回复 by 无极彡剑伦 (#32)

*2025-11-11 20:13*

想知道注入so的时机

## 回复 by 筹码 (#33)

*2025-11-14 16:55*

6666

## 回复 by 勒LI (#34)

*2025-11-14 17:07*

6666

## 回复 by mb_dfutauur (#35)

*2025-11-19 10:41*

万物皆可mcp啊，大佬6啊

## 回复 by git_99841xmsnmo444 (#36)

*2025-11-20 11:17*

优秀![image](https://bbs.kanxue.com/view/img/face/060.gif)

## 回复 by kande (#37)

*2025-11-21 04:40*

66666

## 回复 by mb_akowpmjs (#38)

*2025-11-21 15:29*

666

## 回复 by mb_tawwmfks (#39)

*2025-11-27 14:54*

666

## 回复 by 风子 (#40)

*2025-11-29 09:14*

近期都在研究hookui和mcp的用法，经过这几天使用，感觉mcp都在用hookui的功能，mcp相当于一个传令员？是不是我理解错了什么？

## 回复 by mb_jxhmajfh (#41)

*2025-11-29 11:36*

666

## 回复 by 情迁 (#42)

*2025-12-1 08:43*

>
> [风子](https://bbs.kanxue.com/user-132.htm)
>
>  近期都在研究hookui和mcp的用法，经过这几天使用，感觉mcp都在用hookui的功能，mcp相当于一个传令员？是不是我理解错了什么？
>
>

每一个应用都分别有一个对应的mcp服务器,hookui本身也有一个,请问你用的那个服务器是不是hookui本身,如果要研究其它应用自然需要改成其他应用的端口才行的哈

## 回复 by 风子 (#43)

*2025-12-2 20:27*

>
> [情迁](https://bbs.kanxue.com/user-769855.htm)
>
>  每一个应用都分别有一个对应的mcp服务器,hookui本身也有一个,请问你用的那个服务器是不是hookui本身,如果要研究其它应用自然需要改成其他应用的端口才行的哈
>
>

最近都在研究怎么使用，发现可以做的事情非常多，但是codebuddy总问我要授权有点烦

## 回复 by 带篮子 (#44)

*2025-12-4 04:39*

666

## 回复 by 口艾口牙女马口牙 (#45)

*2025-12-4 20:38*

学习一下

## 回复 by 技术总监 (#46)

*2025-12-6 23:09*

厉害????????

## 回复 by wjwujian (#47)

*2025-12-16 01:46*

支持一下

## 回复 by 云觞 (#48)

*2025-12-31 14:30*

66666

## 回复 by sjshb57 (#49)

*2026-1-1 13:37*

点赞

## 回复 by mb_nkgphjuz (#50)

*2026-1-4 11:40*

111

## 回复 by mb_xsozzohb (#51)

*2026-1-5 11:12*

大佬牛逼

## 回复 by mb_qimctavn (#52)

*2026-1-5 12:23*

6

## 回复 by mb_jnmxfjku (#53)

*2026-1-6 15:09*

666

## 回复 by mb_lzybjqdn (#54)

*2026-1-6 21:25*

学习思路

## 回复 by 财神爷999 (#55)

*2026-1-7 10:56*

感谢分享

## 回复 by 4Chan (#56)

*2026-1-12 17:45*

666

## 回复 by dxasqw (#57)

*2026-1-26 16:00*

6

## 回复 by baogu (#58)

*2026-1-30 15:53*

111

## 回复 by shuangmou (#59)

*2026-2-6 17:18*

感谢分享

## 回复 by mb_kfrkwwjb (#60)

*2026-2-15 00:28*

1

## 回复 by AG陆管会梦泪 (#61)

*2026-2-19 16:34*

![image](https://bbs.kanxue.com/view/img/face/010.gif)

## 回复 by kccp (#62)

*2026-2-19 18:57*

666

## 回复 by wx_朝望夕阳丶暮观雪 (#63)

*2026-3-1 07:13*

666

## 回复 by techted89 (#64)

*2026-3-5 13:30*

thx

## 回复 by mb_keidniog (#65)

*2026-3-8 21:44*

6

## 回复 by mb_fyfuomwx (#66)

*2026-3-9 01:28*

6

## 回复 by ATrueMan (#67)

*2026-3-9 09:24*

study

## 回复 by r0reborn (#68)

*2026-3-9 09:45*

6

## 回复 by mb_xnairofv (#69)

*2026-3-9 10:41*

666

## 回复 by pingsky (#70)

*2026-3-19 21:44*

6666

## 回复 by Simon0816 (#71)

*2026-3-20 14:56*

666

## 回复 by krizzy (#72)

*2026-3-22 15:08*

666ik iwthat

## 回复 by 我不是卷王 (#73)

*2026-3-22 16:08*

666

## 回复 by fvduan (#74)

*2026-4-5 15:48*

666

## 回复 by mb_thqoyvtl (#75)

*2026-4-5 18:36*

6666

## 回复 by 小迷糊ddd (#76)

*2026-4-5 21:18*

感谢分享，学习一下。

## 回复 by mb_qlanixyh (#77)

*2026-4-6 17:20*

看看。。

## 回复 by ~时光荏苒 (#78)

*2026-4-27 14:59*

666

## 回复 by davan (#79)

*2026-4-28 16:21*

不错

## 回复 by davan (#80)

*2026-4-28 16:21*

不错666

## 回复 by wx_岁月真好_475628 (#81)

*2026-4-28 17:04*

6666

## 回复 by wx_岁月真好_475628 (#82)

*2026-4-28 17:04*

6666

## 回复 by wx_岁月真好_475628 (#83)

*2026-4-28 17:04*

6666666

## 回复 by 青岛喝墨魔王 (#84)

*2026-5-1 16:05*

666

## 回复 by YOYO2021 (#85)

*2026-5-4 18:12*

谢谢

## 回复 by mb_lzotvdxv (#86)

*2026-5-10 00:29*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by mb_oqmfwxcf (#87)

*2026-5-28 20:02*

这个帖子详细介绍了如何在没有安卓root机的情况下，通过模拟器和Xposed环境进行hookui测试，分享了使用网易云模拟器、nodejs、codebuddy等工具的具体操作步骤，并通过截图展示了测

## 回复 by mb_nhigqljs (#88)

*2026-5-29 09:05*

厉害了，这种方法真的很实用！不用复杂的工具，直接用模拟器就能完成hookui测试，省时省力。作者的分享很详细，从安装到操作都讲得明明白白，特别是用mcp调用获取应用信息和修改界面文字的演示，让人一看

## 回复 by huangjw (#89)

*2026-5-29 09:47*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_nhigqljs (#90)

*2026-5-30 00:41*

厉害了，楼主的方法真的很实用！不用root手机，直接用模拟器就能完成测试，确实方便。特别是用nodejs和codebuddy搭建环境，步骤清晰，对学习hookui技术很有帮助，特别是对像我这样还在学

## 回复 by mb_elqwyvnm (#91)

*2026-5-30 01:04*

无敌pluhs

## 回复 by mb_qdfakwxw (#92)

*2026-6-10 19:51*

这个测试过程非常详细，展示了在模拟器环境下使用Xposed进行hookui的能力。通过Node.js和CodeBuddy的结合，能够高效地进行界面分析和逻辑推测，而且全程没有使用复杂的工具，操作相对
