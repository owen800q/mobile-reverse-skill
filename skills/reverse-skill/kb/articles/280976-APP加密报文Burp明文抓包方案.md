---
title: '[原创]APP加密报文Burp明文抓包方案'
url: https://bbs.kanxue.com/thread-280976.htm
tid: 280976
author: owlTest
date: '2024-03-20'
tags: [Android安全, 原创, HOOK注入, 协议分析, 逆向分析, 基础理论]
crawled_at: '2026-07-31T14:29:51+08:00'
replies: 10
---

目录- 前言
- 目标APP介绍
- 请求报文格式
- 响应报文格式
- 请求报文与响应报文加解密流程
- 请求报文加密流程
- 响应报文解密流程
- Hook抓包的缺陷
- 传统Hook抓包方式
- 传统Hook抓包方式存在的缺陷
- 报文以RSA加密情况下明文请求包思路
- 使用通用加解密算法
- 使用自写加解密算法
- 实现过程
- 通用加密算法实现过程
- 自写加密算法实现过程
- 最终效果
- 总结
# 前言

随着安全等级的提高目前金融、证券、保险类APP经常使用加密的请求和响应报文在公网传输数据，使用传统的frida转发到Burp的方式测试起来非常恼火，而且对于重放类问题基本上很难挖掘，本篇文章使用frida、frida RPC和burp插件联动的方式对加密报文进行明文抓包以解决不能重放的问题，希望能够解决各位在测试过程中遇到的APP加密报文明文抓包和重放的问题。

# 目标APP介绍

## 请求报文格式

1.抓取APP登录请求报文可知APP以POST方式传输json格式的请求报文数据，JSON格式字段data为加密数据，digest字段为签名。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_8U8K3DKP8JGB4JQ.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_FCXSSEWPEGJA49J.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_XPD5ZWYEKBQCCTZ.webp)

2.请求报文中data字段以RSA APP本地私钥的方式加密传输。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_C9A2N4CKPMJG4CY.webp)

3.请求报文中digest字段以SHA256withRSA本地私钥，对请求报文明文数据Base64编码字符进行加签。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_KUUACEKDB6E2W5V.webp)

## 响应报文格式

1.APP本地拦截器XXXXXXXXInterceptor#intercept方法对响应参数data进行解密和digest参数验签。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_N6GVYBSZ2ZKPBJW.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_22FEXQ888S24W6H.webp)

## 请求报文与响应报文加解密流程

### 请求报文加密流程

1.客服端发起请求加密流程如下图所示:
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_2V9DDK3N6RJG2SN.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_BYZCWMMFB42U9YX.webp)

### 响应报文解密流程

1.客服端接收响应加解密流程如下图所示:

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_F9SQ68FYWAN96MQ.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_U9QEFNRK5X38A5M.webp)

# Hook抓包的缺陷

## 传统Hook抓包方式

1.通过Hook加密函数修改明文和Hook解密函数修改解密的方式修改请求和响应报文。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_R3JA495XSB9S48E.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_Q3WMD5B8WQVWMVJ.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_XDMZNPN6TEJ9XEE.webp)

2.Hook转发Burp显示的请求报文。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_7NWVPCNZP74R8VF.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_DGFAN7T263WG79K.webp)

3.Hook转发Burp显示的响应报文。

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_PR5FPQMYT5G843D.webp)

## 传统Hook抓包方式存在的缺陷

1.抓取到的请求和响应报文不直观，大多数情况下只知道参数不知道参数对应的请求URL。

2.无法对请求报文进行重放。

# 报文以RSA加密情况下明文请求包思路

## 使用通用加解密算法

1.加密流程如下：

①通过frida hook让加密函数不进行加密直接返回明文数据；

②通过Burp抓取请求报文抓取到的就是明文数据；

③通过Burp插件按照加密加强算法流程对明文数据加密加签然后将报文发送给服务器；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_NZ4C2WPA628Q39B.webp)

2.解密流程如下：

①Burp收到服务器返回的加密加签数据，Burp插件进行解密得到明文数据；

②frida hook让解密函数直接接返回Burp插件解密后的数据；

③Burp返回明文数据APP显示；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_V592VE6EV2GDXMV.webp)

## 使用自写加解密算法

1.加密流程如下：

①通过frida hook让加密函数不进行加密直接返回明文数据；

②通过Burp抓取请求报文抓取到的就是明文数据；

③Burp插件调用frida RPC请求APP加密函数对明文数据进行加密，得到加密加签后的请求密文数据；

④Burp插件RPC调用完成得到密文数据发送给服务器；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_FA2CQ6BNYA73N6E.webp)

2.解密流程如下：

①Burp收到服务器返回的加密加签的密文数据；

②Burp插件调用frida RPC请求APP解密函数对密文数据进行解密得到解密后的明文数据；

③frida hook让解密函数直接接返回Burp插件调用RPC解密后的数据；

④通过frida hook让解密函数不进行解密直接返回明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_RR9AVSJ6R6EY83T.webp)

# 实现过程

## 通用加密算法实现过程

1.加密流程实现过程如下：

①通过frida hook让加密函数不进行加密直接返回明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_AFP8BW5JBBGEV8A.webp)

②通过Burp抓取请求报文抓取到的就是明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_PB2ZF698XHEMWKE.webp)

③通过Burp插件按照加密加强算法流程对明文数据加密加签然后将报文发送给服务器；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_U2YVH8CPWY7245W.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_PBD8K9NAU7UMXP4.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_635MGBWA8JB9K6W.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_H4NPNSWHXCW6CNQ.webp)

查看burp日志发送是已经是加密报文了

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_HUP2QMZJ7D76T3R.webp)

2.解密流程实现如下：

①Burp收到服务器返回的加密加签数据，Burp插件进行解密得到明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_4CE4ZDRUKERBNUM.webp)

②frida hook让解密函数直接接返回Burp插件解密后的数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_FWVZ65ZRX36V23C.webp)

③Burp返回明文数据APP显示；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_M6M5A3QG6JYJ9KF.webp)

## 自写加密算法实现过程

1.加密流程如下：

①通过frida hook让加密函数不进行加密直接返回明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_HXD7NEGFEV862W7.webp)

②通过Burp抓取请求报文抓取到的就是明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_AEQNSZ2E945MW95.webp)

③Burp插件调用frida RPC请求APP加密函数对明文数据进行加密，得到加密加签后的请求密文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_8BKSWTP5T6GDD5A.webp)

④Burp插件RPC调用完成得到密文数据发送给服务器；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_8ZHEUCFF7XJK49H.webp)

2.解密流程如下：

①Burp收到服务器返回的加密加签的密文数据；

②Burp插件调用frida RPC请求APP解密函数对密文数据进行解密得到解密后的明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_AQ5XSN38KEWEH4G.webp)

③frida hook让解密函数直接接返回Burp插件调用RPC解密后的数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_KRVM44T4T6Y274B.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_9HMFC4Y5F3TUD4U.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_JAEPEGFBP45A9GY.webp)

④通过frida hook让解密函数不进行解密直接返回明文数据；

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_TMEV4C9GU8CE6RS.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_U4P6GDU93673RUN.webp)

# 最终效果

报文历史记录、重放、爆破模块都可以正常使用，我们就能在明文下愉快地进行测试啦！！！！

 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_RADSFCWJ38EE2ZU.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_RHHEGSKGD925PCY.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_N3A82UAYY8TW9RU.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_9E458S6T5XHE8XP.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202403/996427_JD9QV4Q7KNMD4NV.webp)

# 总结

如上方法对于其他加密方式同样适用，而且不光是APP端Web端同样适用，希望各位能够举一反三。

下次分享不借助Burp插件只使用Frida+Frida RPC方式自行重放的方法敬请期待。

---

# 回复

## 回复 by mb_fidppcok (#2)

*2024-3-20 15:01*

好像很不错的样子

## 回复 by 非白即黑 (#3)

*2024-3-21 21:06*

太牛了

## 回复 by yccccc (#4)

*2024-3-26 16:16*

有一些工具，比如xserver是否也能实现你这个？

## 回复 by PeterJoin (#5)

*2024-4-17 19:18*

给力，这是哪个APP呢？

## 回复 by KevindHY (#6)

*2025-1-7 17:10*

大佬这个插件有开源的打算吗

## 回复 by 软件君子 (#7)

*2025-1-8 15:59*

好思路 很新颖

## 回复 by owlTest (#8)

*2025-2-26 11:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  KevindHY](https://bbs.kanxue.com/user-751139.htm)
>
>  大佬这个插件有开源的打算吗
>
>

这个就是的burp插件开发，有需要我可以放到github上面。

## 回复 by owlTest (#9)

*2025-2-26 11:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  yccccc](https://bbs.kanxue.com/user-931215.htm)
>
>  有一些工具，比如xserver是否也能实现你这个？
>
>

xserver这个没有搞过。。可以细说吗？

## 回复 by inono (#10)

*2025-2-26 23:32*

师傅github地址可以给一个吗

## 回复 by 飞猫的世界 (#11)

*2025-5-26 11:30*

学习了
