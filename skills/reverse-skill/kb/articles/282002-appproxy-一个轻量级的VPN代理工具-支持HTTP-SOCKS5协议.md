---
title: '[原创]appproxy 一个轻量级的VPN代理工具，支持HTTP, SOCKS5协议'
url: https://bbs.kanxue.com/thread-282002.htm
tid: 282002
author: iyue_t
date: '2024-06-02'
tags: [Android安全, 原创, 工具脚本, 协议分析, 逆向分析]
crawled_at: '2026-07-31T14:26:20+08:00'
replies: 44
---

# [appproxy](https://github.com/ys1231/appproxy)

## 项目背景

- 在分析app的时候,偶尔需要抓包,尝试了目前比较常见的代理工具
- `Drony` `Postern` `ProxyDroid` 发现都有一个相同的问题,对于较新的Android系统不太友好,要么app列表显示不正常,或者界面过于复杂,往往设置之后经常会失效,偶然在play上发现一个比较新的代理工具,界面很不错清晰不过对国内用户不友好有些功能需要会员,即使花钱由于不维护或者网络原因,完整的功能无法使用于是在业余时间开发了这个.

## 项目简介

1. 基于flutter和[tun2socks](https://github.com/xjasonlyu/tun2socks)开发.
2. [appproxy](https://github.com/ys1231/appproxy) 是一个轻量级的VPN代理工具，支持HTTP, SOCKS5协议
3. 功能单只做代理,可分app代理, 双击修改配置逻辑比较简单, 主打一个能用就行.
4. 出于学习flutter的目的去做的,分享给大家,顺便帮我测试一下.
5. 加上[MoveCertificate](https://github.com/ys1231/MoveCertificate) 上下游都有了哈哈.
<https://ys1231.lanzouw.com/b00taws06h> 密码: 65eg

## 附上截图

![Screenshot_20240604-205220](https://bbs.kanxue.com/upload/attach/202406/853140_QGTG4HW6WTFZ3AU.png)

![Screenshot_20240604-205910](https://bbs.kanxue.com/upload/attach/202406/853140_FX8YSENDRVD6M3V.png)

![Screenshot_20240604-205229](https://bbs.kanxue.com/upload/attach/202406/853140_WVCND84ET4A52ZY.png)

![Screenshot_20240604-205148](https://bbs.kanxue.com/upload/attach/202406/853140_4G668AUC5AQ9JFW.png)

![Screenshot_20240604-205158](https://bbs.kanxue.com/upload/attach/202406/853140_CXYX7CZPKJZ8CBA.png)

---

# 回复

## 回复 by huangjw (#2)

*2024-6-3 00:35*

牛啊，附上图就更棒了

## 回复 by mb_fidppcok (#3)

*2024-6-3 14:35*

https是不是不行了？

## 回复 by caolinkai (#4)

*2024-6-3 16:38*

感谢分享

## 回复 by iyue_t (#5)

*2024-6-4 21:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  huangjw](https://bbs.kanxue.com/user-323039.htm)
>
>  牛啊，附上图就更棒了
>
>

听了你的建议,觉得有道理,附上了.

## 回复 by 云觞 (#6)

*2024-6-5 10:15*

之前也想过做一个新的代理工具，但是想想太浪费时间了，来体验体验大佬的新工具

## 回复 by iyue_t (#7)

*2024-6-6 10:21*

>
> [云觞](https://bbs.kanxue.com/user-921611.htm)
>
>  之前也想过做一个新的代理工具，但是想想太浪费时间了，来体验体验大佬的新工具
>
>

我也等了一段时间,没发现新的才自己写了.

## 回复 by 云觞 (#8)

*2024-6-6 15:41*

>
> [iyue_t](https://bbs.kanxue.com/user-853140.htm)
>
>  我也等了一段时间,没发现新的才自己写了.
>
>

给大佬点个赞，用了一下，非常不错，提个小需求，创建好的代理能否加个编辑功能，不然每次都得删除再添加再重新命名

## 回复 by 文西哥 (#9)

*2024-6-6 16:43*

大佬可以参考一下 Kitsunebi  挺不错

## 回复 by 文西哥 (#10)

*2024-6-6 16:46*

可否设置 单个app对应单独的代理地址？ 这样更棒了

## 回复 by iyue_t (#11)

*2024-6-7 09:55*

>
> [文西哥](https://bbs.kanxue.com/user-931323.htm)
>
>  可否设置 单个app对应单独的代理地址？ 这样更棒了
>
>

有时间弄，这个可以有。![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by iyue_t (#12)

*2024-6-7 09:57*

>
> [云觞](https://bbs.kanxue.com/user-921611.htm)
>
>  给大佬点个赞，用了一下，非常不错，提个小需求，创建好的代理能否加个编辑功能，不然每次都得删除再添加再重新命名
>
>

一看就是没认真看文档的![image](https://bbs.kanxue.com/view/img/face/36.gif)，双击就能编辑，这个功能做的时间比较靠后，就略显简陋。

## 回复 by iyue_t (#13)

*2024-6-7 10:00*

>
> [云觞](https://bbs.kanxue.com/user-921611.htm)
>
>  给大佬点个赞，用了一下，非常不错，提个小需求，创建好的代理能否加个编辑功能，不然每次都得删除再添加再重新命名
>
>

有什么我没注意到的需求，可以去github提，慢慢改，顺便给个star就很开心![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by tmi (#14)

*2024-6-7 10:10*

看了下，套壳了tun2sock，有办法处理socket的数据包吗？只能自己编译tun2sock成aar？

## 回复 by mb_kywyiskf (#15)

*2024-7-1 00:30*

可以选择过滤IP吗，比如本地IP过滤不走代理

## 回复 by mb_onetrtkl (#16)

*2024-7-1 14:16*

支持安卓几的啊

## 回复 by iyue_t (#17)

*2024-7-8 17:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_onetrtkl](https://bbs.kanxue.com/user-987891.htm)
>
>  支持安卓几的啊
>
>

理论上支持到最新，实际没测过。

## 回复 by lz_0618 (#18)

*2024-7-10 21:33*

我试了半天，好像不行啊，我在雷电模拟器9下安装的，也不知道应该装哪个版本，三个都试了下，运行时都没有报错，app-arm64-v8a-release版本小钥匙都没有，可能不行。app-armeabi-v7a-release小钥匙出来了，但我的mitmproxy没有看到连接信息，用Postern的时侯，能看到client connect提示信息，这个啥也没有，另外那个没有注意什么现象。这个代理，不支持虚拟机？

## 回复 by iyue_t (#19)

*2024-7-14 15:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  lz_0618](https://bbs.kanxue.com/user-966905.htm)
>
>  我试了半天，好像不行啊，我在雷电模拟器9下安装的，也不知道应该装哪个版本，三个都试了下，运行时都没有报错，app-arm64-v8a-release版本小钥匙都没有，可能不行。app-armeabi- ...
>
>

你需要下载对应cpu架构的包app-x86_64-release.apk

## 回复 by 亲近自然 (#20)

*2024-8-15 13:42*

>
> [iyue_t](https://bbs.kanxue.com/user-853140.htm)
>
>  有时间弄，这个可以有。[em_13]
>
>

电脑上有些软件没有设置socks代理的地方，有没有啥工具可以单独设置某个应用走代理的呀？

## 回复 by uvbs (#21)

*2024-8-15 16:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  亲近自然](https://bbs.kanxue.com/user-1003720.htm)
>
>  电脑上有些软件没有设置socks代理的地方，有没有啥工具可以单独设置某个应用走代理的呀？
>
>

proxyfier sockcap 都可以

## 回复 by iyue_t (#22)

*2024-8-15 16:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  亲近自然](https://bbs.kanxue.com/user-1003720.htm)
>
>  电脑上有些软件没有设置socks代理的地方，有没有啥工具可以单独设置某个应用走代理的呀？
>
>

目前无非两种 http 和socks5  这两种都可以兼容,应该是够用了的.

## 回复 by 非白即黑 (#23)

*2024-8-15 17:05*

挺好的，我之前用的就是你说的那个付费的软件，虽然能用，但是你这个更香，点赞支持

## 回复 by 非白即黑 (#24)

*2024-8-15 17:13*

>
> [非白即黑](https://bbs.kanxue.com/user-892704.htm)
>
>  挺好的，我之前用的就是你说的那个付费的软件，虽然能用，但是你这个更香，点赞支持
>
>

装上了，效果不错，不过他不能编辑，希望加个编辑

## 回复 by iyue_t (#25)

*2024-8-15 23:35*

>
> [非白即黑](https://bbs.kanxue.com/user-892704.htm)
>
>  装上了，效果不错，不过他不能编辑，希望加个编辑
>
>

双击就可以修改和编辑，我也是写了一半才想起来，就用了个最简单的触发事件。

## 回复 by mb_elqwyvnm (#26)

*2024-8-16 00:09*

真不错

## 回复 by 亲近自然 (#27)

*2024-8-16 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  uvbs](https://bbs.kanxue.com/user-100039.htm)
>
>  proxyfier sockcap 都可以
>
>

试过sockscap,单独的软件添加进去后无法代理。

实际想达到的目的是Socks代理后，等同于进入对方的局域网，海康的摄像头扫描工具可以直接扫描到对方内网的摄像头信息，想实现远程管理摄像头。

![image](https://bbs.kanxue.com/upload/attach/202408/1003720_CGXEJFKCW3WMUUS.webp)

## 回复 by mb_pnlabahd (#28)

*2024-8-18 07:16*

为什么我装上没有效果

## 回复 by iyue_t (#29)

*2024-8-20 16:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_pnlabahd](https://bbs.kanxue.com/user-975939.htm)
>
>  为什么我装上没有效果
>
>

不知道，你可以去提isuse

## 回复 by jfztaq (#30)

*2024-8-28 09:02*

试试看看能不能用

## 回复 by jfztaq (#31)

*2024-10-3 07:33*

支持socket了吗？试试看看

## 回复 by jfztaq (#32)

*2024-10-3 07:51*

真好用，就是如果换个app抓包的话，要先把代理关闭，然后重新开才生效

## 回复 by mb_ltnaxjfa (#33)

*2024-10-20 22:49*

兄弟有联系方式吗

## 回复 by 看场雪小弟子 (#34)

*2024-12-12 14:19*

Hi，我在蓝叠模拟器上安装appproxy，配置好socks代理，想切换其他应用进行使用时，发现appproxy代理开关会自动关闭，即掉后台现象，有时候重启模拟器该问题会消失，有时候重启仍会出现掉后台现象，请问可能是由于啥原因导致的呢

## 回复 by iyue_t (#35)

*2024-12-12 21:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  看场雪小弟子](https://bbs.kanxue.com/user-896438.htm)
>
>  Hi，我在蓝叠模拟器上安装appproxy，配置好socks代理，想切换其他应用进行使用时，发现appproxy代理开关会自动关闭，即掉后台现象，有时候重启模拟器该问题会消失，有时候重启仍会出现掉后台 ...
>
>

收集一下日志 github 提交 issue .

## 回复 by 千屈 (#36)

*2024-12-20 21:55*

搜索中文包名没效果,关闭代理的时候 状态栏的vpn标志 有时候还是有 希望能完美下

## 回复 by iyue_t (#37)

*2024-12-20 22:00*

>
> [mb_gobsmfsi](https://bbs.kanxue.com/user-928200.htm)
>
>  搜索中文包名没效果,关闭代理的时候 状态栏的vpn标志 有时候还是有 希望能完美下
>
>

搜索逻辑是： 1. 包名； 2. 中文名首字母不需要直接搜中文，打字没有字母快；
它只是慢并不是不会消失，可以做但是目前很忙，最近忙着带娃。

## 回复 by 千屈 (#38)

*2025-1-6 13:14*

下次更新 加个开关vpn状态栏实时反馈 现在有时候关了 状态栏还有 强迫症福音

## 回复 by iyue_t (#39)

*2025-1-8 10:47*

>
> [mb_gobsmfsi](https://bbs.kanxue.com/user-928200.htm)
>
>  下次更新 加个开关vpn状态栏实时反馈 现在有时候关了 状态栏还有 强迫症福音
>
>

快过年了，比较忙，年前看有没有时间搞。

## 回复 by 千屈 (#40)

*2025-3-24 00:27*

关掉代理的时候 状态栏的vpn的图标有时候还在 上次反馈过了还没修复

## 回复 by iyue_t (#41)

*2025-3-24 09:40*

>
> [千屈](https://bbs.kanxue.com/user-928200.htm)
>
>  关掉代理的时候 状态栏的vpn的图标有时候还在 上次反馈过了还没修复
>
>

最近出车祸了，没时间搞。

## 回复 by iyue_t (#42)

*2025-3-31 14:14*

>
> [iyue_t](https://bbs.kanxue.com/user-853140.htm)
>
>  最近出车祸了，没时间搞。
>
>

我试了一下最新版，不管是手动结束还是，被别的vpn中断都能立即消失，我的手机版本比较新15

## 回复 by 千屈 (#43)

*2025-4-5 20:45*

我是安卓10和12

## 回复 by 千屈 (#44)

*2025-4-8 00:31*

雷电9也是 关掉状态栏VPN图标也不消失

## 回复 by iyue_t (#45)

*2025-4-8 19:00*

>
> [千屈](https://bbs.kanxue.com/user-928200.htm)
>
>  雷电9也是 关掉状态栏VPN图标也不消失
>
>

能用就行
