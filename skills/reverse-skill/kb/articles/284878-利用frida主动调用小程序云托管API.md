---
title: 利用frida主动调用小程序云托管API
url: https://bbs.kanxue.com/thread-284878.htm
tid: 284878
author: kzzll
date: '2024-12-19'
tags: [Android安全, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:16:50+08:00'
replies: 7
---

## 简介

好久没有碰Android逆向了，有1年多了，基本都生疏了，前来复习一下；
本着研究学习的方向，探索Wx小程序云托管的调用机制；

## 抓包

Charles发现云托管的API没办法直接抓包，似乎用的是内部的通道进行通信的，所以只能尝试往小程序jsapi方向下手。

## 提取

在开始之前，需要先把小程序代码脱出来。
<https://github.com/wux1an/wxapkg>
在GitHub上无意中找到的。该项目由go编写的，非常方便，直接扫描电脑上缓存的小程序并且还有解压
 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_CQSNEGM8FG2MDBH.webp)
在图上发现该小程序是调用 **t.cloud.init** 进行初始化云托管，随后通过**t.cloud.callContainer**来实现调用接口。

## 分析

把wechat.apk拖入到jadx-gui进行分析，并尝试检索关键词，callContainer 关键字。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_7W4QPHRK8P63WH4.webp)
但是很遗憾，没有搜索到任何结果，并且抓不到数据包，简单的方式基本上找不到任何有用的结果。

>
> *尝试转变思路，需要尝试搜索一些关键词不是很常见但可能小程序会调用到的，因为如果搜索常见关键字，可能会导致非常多的结果，也同样无从下手。*
>
>
>

最后我选择搜索了wx小程序的一些常用的函数名称，如：getStorageSync

 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_GMFMNJSPRVNURZ8.webp)

接着直接复制frida的hook代码片段，直接hook查看
 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_VGHZ6RDA8ZK3V7E.webp)
然后去小程序一顿乱操作，可以看到已经hook到了。

随之我们打印堆栈，往上翻，看看能不能找到wx和小程序的交互处。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_UT5VZ93PEGBJV22.webp)
打印堆栈后，发现 **com.tencent.mm.plugin.appbrand.jsapi.p.proceed** 比较不顺眼，可以进它进行hook尝试

 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_7GT3VNN7QE2CTWS.webp)

刚才的调用堆栈是

| 1234 | `com.tencent.mm.plugin.appbrand.jsapi.storage.v.t(Native Method)``com.tencent.mm.plugin.appbrand.jsapi.r.P(Unknown Source:``24``)``com.tencent.mm.plugin.appbrand.service.u.P(Unknown Source:``91``)``com.tencent.mm.plugin.appbrand.jsapi.p.proceed(Unknown Source:``138``)` |
|-|-|

也就是我查看的proceed，接下来应该会往 u.P 走
所以简单阅读下代码，发现下面这行代码进行了一个json的返回

| 1 | `JSONObject D` `=` `r.D(this.f58622h, this.f58616b);` |
|-|-|

由于proceed没有提供传入参数，所以直接hook r.D 这个方法里面，看看他的参数是什么？

 ![图片描述](https://bbs.kanxue.com/upload/attach/202412/885524_GJ8KPW4GBUD9UCF.webp)

上面图上的打印就是 r.D 的参数和返回值，我在进行hook的时候，随意滑动了一下小程序和触发一些接口。

| 1 | `r.D` `is` `called: rVar``=``com.tencent.mm.plugin.appbrand.service.u@``5cfb43f``,` `str``=``{``"keepAlive"``:true,``"data"``:{``"api_name"``:``"qbase_commapi"``,``"data"``:{``"qbase_api_name"``:``"tcbapi_call_container"``,``"qbase_req"``:``"{\"method\":\"post\",\"headers\":[{\"k\":\"TOKEN\",\"v\":\"eyJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJlMjMwOWUwZC0xODAwLTQwZTYtOWIwYi1mNzU4YWRmN2NkODIiLCJpYXQiOjE3MzQ1ODk4MTcsImlzcyI6ImRlbW8iLCJzdWIiOiJ7XCJjZWxscGhvbmVcIjpcIjEzMTE3NzE3NTM4XCIsXCJlbWFpbFwiOlwiXCIsXCJmbGFnXCI6XCJZXCIsXCJsYXN0SXBcIjpcIjIyMi4yMTYuMTYzLjI0MFwiLFwibmlja05hbWVcIjpcIuW-ruS_oeeUqOaItzUxNTZcIixcIm9wZW5pZFwiOlwib3ZVNFo0eFpXTWxhNi1jOTdGTTZqd0FxOXFOMFwiLFwicmlza1JhbmtGbGFnXCI6XCIxXCIsXCJ1bmlvbklkXCI6XCJvay0xZzVoMlItSkdybnZ3dm5oZjJROXNNZ2tnXCIsXCJ1c2VySWRcIjo3MDAwMDAwNzUwMTg2OSxcInVzZXJOYW1lXCI6XCJcIixcInVzZXJQaG90b1VSTFwiOlwiaHR0cHM6Ly9tYWxsaW50ZXIubHRnLmNuOjI4ODY2L2dyb3VwMS9NMDAvM0UvOEUvckJEVXNtUmk2aG1BTUV5NEFBQU9feFlQYWxnMzgwLmpwZ1wiLFwidXNlclR5cGVcIjpcIjNcIn0ifQ.4bnMdASe_0nXsImdm4Zhv3-igN8bVanuChtG4PJj6_o\"},{\"k\":\"content-type\",\"v\":\"application/json\"},{\"k\":\"sign\",\"v\":\"\"},{\"k\":\"X-WX-EXCLUDE-CREDENTIALS\",\"v\":\"unionid, cloudbase-access-token\"},{\"k\":\"X-WX-GATEWAY-ID\",\"v\":\"ylxs-7g9pu9tk6f466517\"},{\"k\":\"HOST\",\"v\":\"mallwx.ltg.cn\"},{\"k\":\"User-Agent\",\"v\":\"Mozilla/5.0 (Linux; Android 10; Pixel 3 Build/QP1A.191005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.6723.103 Mobile Safari/537.36 XWEB/1300199 MMWEBSDK/20240301 MMWEBID/2603 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android\"},{\"k\":\"referer\",\"v\":\"https://servicewechat.com/wx2fd91fc20b4d1376/193/page-frame.html\"},{\"k\":\"X-WX-ENV\",\"v\":\"ylxs-4gg26312c79395ce\"},{\"k\":\"X-WX-CONTAINER-PATH\",\"v\":\"/promoterAction/queryPromoter\"}],\"data\":\"{}\",\"data_type\":0,\"action\":1,\"retryType\":0,\"call_id\":\"1734593087863-0.30876127625770944\"}"``,``"qbase_options"``:{``"env"``:``"ylxs-4gg26312c79395ce"``,``"rand"``:``"0.6732074762652199"``},``"qbase_meta"``:{``"session_id"``:``"1734590464124"``,``"sdk_version"``:``"wx-miniprogram-sdk/3.3.5 (1720506833000 platform/android})"``,``"filter_user_info"``:false},``"cli_req_id"``:``"1734593087868_0.0936678805604707"``},``"operate_directly"``:false},``"timeout"``:``180000``,``"requestInQueue"``:false,``"isImportant"``:false}` |
|-|-|

其中这一串我发现似乎就是小程序云托管调用的API

## 总结

1、通过搜索wx常见的函数，如getStorageSync以快速hook到小程序内部机制
2、通过调用堆栈往上跟随找到小程序和微信的交互点

没错，本章已经结束了，抛砖引玉，记录思路。

---

# 回复

## 回复 by mb_tlhbjuoh (#2)

*2024-12-20 07:42*

大佬，Frida主动调用云函数没问题 但是你这个小程序似乎是走的网关，网关的加解密在js里 不在微信里 是AES加解密， hook 云函数相关的点能拿到key，最后用网关的key去直接解密请求抓包，主动发包也可以用这个token和key去组包直接发https请求

## 回复 by mb_tlhbjuoh (#3)

*2024-12-20 07:43*

有没有点能直接hook 然后给小程序注入js呢？

## 回复 by mb_fidppcok (#4)

*2024-12-23 10:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_tlhbjuoh](https://bbs.kanxue.com/user-904629.htm)
>
>  大佬，Frida主动调用云函数没问题 但是你这个小程序似乎是走的网关，网关的加解密在js里 不在微信里 是AES加解密， hook 云函数相关的点能拿到key，最后用网关的key去直接解密请求抓包，主 ...
>
>

这个大佬能否再说详细点

## 回复 by kzzll (#5)

*2024-12-23 14:37*

>
> [mb_fidppcok](https://bbs.kanxue.com/user-986312.htm)
>
>  这个大佬能否再说详细点
>
>

具体构造的实现是在 libwxa-runtime-binding.so 实现的，函数名：nativeInvokeCallbackHandler

## 回复 by mb_snfxvlmb (#6)

*2025-3-4 15:54*

frida能不能主动调用微信小程序中的wx.getUserCryptoManager().getLatestUserKey()函数？

## 回复 by mb_snfxvlmb (#7)

*2025-3-4 15:55*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_tlhbjuoh](https://bbs.kanxue.com/user-904629.htm)
>
>  大佬，Frida主动调用云函数没问题 但是你这个小程序似乎是走的网关，网关的加解密在js里 不在微信里 是AES加解密， hook 云函数相关的点能拿到key，最后用网关的key去直接解密请求抓包，主 ...
>
>

frida能不能主动调用微信小程序中的wx.getUserCryptoManager().getLatestUserKey()函数？

## 回复 by U_M_R (#8)

*2025-5-8 16:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_tlhbjuoh](https://bbs.kanxue.com/user-904629.htm)
>
>  大佬，Frida主动调用云函数没问题 但是你这个小程序似乎是走的网关，网关的加解密在js里 不在微信里 是AES加解密， hook 云函数相关的点能拿到key，最后用网关的key去直接解密请求抓包，主 ...
>
>

你确定是这套流程吗？  老哥搞定了么？
