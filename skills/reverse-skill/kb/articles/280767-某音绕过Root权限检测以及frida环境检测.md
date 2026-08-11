---
title: '[原创]某音绕过Root权限检测以及frida环境检测'
url: https://bbs.kanxue.com/thread-280767.htm
tid: 280767
author: Zedbully
date: '2024-03-05'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-11T08:45:59+00:00'
replies: 15
---

# D音绕过逆向环境检测

## 1上期回顾

1:上一片帖子已经可以抓到抖音的包了，这只是第一步 离目标还比较遥远
2:这一期在用开发手机进直播间的时候 发现直播人数没有加1

## 2:怀疑三个方面的问题

2.1:root
2.2:frida
2.3 天意

## 解决思路

3.1:找了一台没有root的手机 发现一切正常，下载了某银行app，进去后提示操作环境异常，随即闪退
3.2 用面具隐藏掉root权限以后，打开某银行操作正常，打开D音直播间，人数成功+1（没有开启frida）
3.3 开启frida以后，打开抖音进入直播间 人数还是没+1，于是停掉frida以后，再次进入直播间发现人数正常+1
3.4 但是frida必须打开，不然无法逆向，于是我更改了frida-server的name，并且更改了启动端口，运行魔改版的frdia，修改了特征以后，启动frida，进入直播间，看到了直播间人数+1，ok！完美！

---

# 回复

## 回复 by 一群人游走 (#2)

*2024-3-5 10:20*

重点: 魔改后的frida

## 回复 by 雨之后 (#3)

*2024-3-5 11:21*

重点: 3年

## 回复 by neo10 (#4)

*2024-3-5 14:02*

天意也是被怀疑对象![image](https://bbs.kanxue.com/view/img/face/78.gif)

## 回复 by Zedbully (#5)

*2024-3-5 14:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  一群人游走](https://bbs.kanxue.com/user-633773.htm)
>
>  重点: 魔改后的frida
>
>

肉丝老师有讲过 git上开源的

## 回复 by Zedbully (#6)

*2024-3-5 14:40*

>
> [雨之后](https://bbs.kanxue.com/user-582985.htm)
>
>  重点: 3年
>
>

自己学习

## 回复 by Zedbully (#7)

*2024-3-5 14:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  neo10](https://bbs.kanxue.com/user-995063.htm)
>
>  天意也是被怀疑对象[em_78]
>
>

弄不出来就是天意

## 回复 by Python成长路 (#8)

*2024-3-6 09:15*

>
> [Zedbully](https://bbs.kanxue.com/user-995236.htm)
>
>  肉丝老师有讲过 git上开源的
>
>

链接发一下，谢谢

## 回复 by axyzyz (#9)

*2024-3-6 22:39*

66666

## 回复 by dreameriii (#10)

*2024-3-7 09:56*

楼主metasec 模块的 hook 检测能过吗

## 回复 by mb_qccpktjm (#11)

*2024-3-8 19:35*

小白问下大佬，这里“面具隐藏root”的面具 是什么工具啊？名字叫啥？

## 回复 by mb_plkucays (#12)

*2024-3-16 04:12*

大神能帮忙解决风控的问题吗

## 回复 by xwtwho (#13)

*2024-3-16 17:37*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  楼主metasec 模块的 hook 检测能过吗
>
>

要不要过tiktok这个模块的各个检测，包括frida hook崩，so修改的检测也过，可以查report数据验证的

## 回复 by huangjw (#14)

*2024-3-16 20:53*

收藏先，用到在翻出来看

## 回复 by wx_倾尽天下 (#15)

*2024-4-17 19:47*

Magisk

## 回复 by charleskui (#16)

*2025-6-13 14:43*

某音防范做的比银行类App还严格
