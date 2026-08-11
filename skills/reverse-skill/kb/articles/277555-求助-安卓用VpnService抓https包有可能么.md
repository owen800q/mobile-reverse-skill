---
title: '[求助][求助]安卓用VpnService抓https包有可能么？'
url: https://bbs.kanxue.com/thread-277555.htm
tid: 277555
author: wx_思文
date: '2023-06-10'
tags: [Android安全, 求助, 协议分析, 系统相关]
crawled_at: '2026-08-11T08:47:29+00:00'
replies: 16
---

想问一下有大佬能做到用安卓的vpnservice抓https包的query不？

 我尝试了下https实在抓不到，又或者：VpnService把请求拦截，然后在推给远程服务器能把协议改成Http有这种可能吗？ 有没有有相关经验的大佬给解惑一下，这方面的文档少的不得了

---

# 回复

## 回复 by 铭天星 (#2)

*2023-6-10 21:39*

https://github.com/zhkl0228/AndroidVPN

## 回复 by RiDiN (#3)

*2023-6-11 17:46*

<https://github.com/rev1si0n/lamda>

抓包不该是问题，会写代码那不仅能抓，还能实时修改。UI工具永远没有命令行和代码来的方便。

我觉得这个年代不应该还有人困在这个问题上面，看样子还是普及度不高，虽然它也不是全能的。

## 回复 by wx_思文 (#4)

*2023-6-13 23:55*

兄弟们，还有别的方案吗？这都需要中间人证书。唉，哥们就是碰到一个包，无root抓到了一个https的url，而且没用到中间人证书。。。哥们百思不得其解啊。。。 那个https的链接换成http其实也可以访问，我就想他的实现方式是不是把https链接拦截了，换成个http的。。。当然这都是我的推测。

## 回复 by wx_思文 (#5)

*2023-6-13 23:56*

不需要抓包体，只要能抓到url的query部分就可以了。。。百思不得其解。有大佬能推测出安卓无root抓https的query部分的思路吗？

## 回复 by RiDiN (#6)

*2023-6-14 16:36*

~

## 回复 by 小黄鸭爱学习 (#7)

*2023-6-15 14:52*

>
> [铭天星](https://bbs.kanxue.com/user-687583.htm)
>
>  https://github.com/zhkl0228/AndroidVPN
>
>

这个为什么输入不了也启动不了

## 回复 by 铭天星 (#8)

*2023-6-15 23:08*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  这个为什么输入不了也启动不了
>
>

下载libnetguard，跟手机网络同局域网，启动测试程序Main会自动发现ip跟端口

## 回复 by mb_xxtxvmxu (#9)

*2023-6-16 11:11*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>
>  https://github.com/rev1si0n/lamda抓包不该是问题，会写代码那不仅能抓，还能实时修改。UI工具永远没有命令行和代码来的方便。我觉得这个年代不应该还有人困在这个问题上面，看 ...
>
>

前提是不root不安装证书

## 回复 by mb_xxtxvmxu (#10)

*2023-6-16 11:28*

>
> [铭天星](https://bbs.kanxue.com/user-687583.htm)
>
>  下载libnetguard，跟手机网络同局域网，启动测试程序Main会自动发现ip跟端口

[报错找不到kraken-http-decoder这个包](https://github.com/zhkl0228/libnetguard/issues/1)

## 回复 by 铭天星 (#11)

*2023-6-16 15:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxtxvmxu](https://bbs.kanxue.com/user-980967.htm)
>
>
>
>
>
>
>
>  铭天星
>
>  下载libnetguard，跟手机网络同局域网，启动测试程序Main会自动发现ip跟端口 报错找不到kraken-http-decode ...
>
>

kraken也要下载并mvn install

## 回复 by RiDiN (#12)

*2023-6-16 17:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxtxvmxu](https://bbs.kanxue.com/user-980967.htm)
>
>  前提是不root不安装证书
>
>

不root不安装证书光流量那你用手抓呗

## 回复 by mb_xxtxvmxu (#13)

*2023-6-18 15:24*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>
>  不root不安装证书光流量那你用手抓呗
>
>

用过一个小软件专门抓游戏里webview地址的确实有手就行

## 回复 by RiDiN (#14)

*2023-6-19 17:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxtxvmxu](https://bbs.kanxue.com/user-980967.htm)
>
>  用过一个小软件专门抓游戏里webview地址的确实有手就行
>
>

emm，出个教程叭我给你投50币，注意上下文，https 哦

## 回复 by RiDiN (#15)

*2023-6-19 17:36*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxtxvmxu](https://bbs.kanxue.com/user-980967.htm)
>
>  用过一个小软件专门抓游戏里webview地址的确实有手就行
>
>

还有在那叭叭叭的，你怎么知道你那个小软件没安装证书（低版本的用户证书）

## 回复 by RiDiN (#16)

*2023-6-19 17:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxtxvmxu](https://bbs.kanxue.com/user-980967.htm)
>
>  用过一个小软件专门抓游戏里webview地址的确实有手就行
>
>

来个手动流程我就信了，并且我还给你发红包，并且，至少要有百分之三十的通用性，并且，不能直接或间接root，装证书，使用bpf，使用任何泄漏的CA根证书，并且给你任意一部安卓8-安卓10的手机都能抓到https内容，求求你了哥们，这种破解https的技巧分享出来那真是，太酷啦

## 回复 by daxia200N (#17)

*2023-6-21 18:03*

大黄鸟是可以抓的，没有root的话可以用lspatch进行patch后使用xposed相关模块应该就可以了，52和mt上有相关的文章。
