---
title: '[原创]Reqable =  charles + Brida'
url: https://bbs.kanxue.com/thread-277303.htm
tid: 277303
author: zapata_ok
date: '2023-05-21'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-08-12T04:02:26+00:00'
replies: 10
---

先上一张图，UI 效果相当炸裂，这是用 flutter 进行开发， 无论是性能上还是 UI 上体验感上都非常好.目前还在内测阶段。地址 ： <https://reqable.com/download/> 。小 Tip ：小黄鸟也是这个作者写的哦 ！！！
 ![image](https://bbs.kanxue.com/upload/attach/202305/944052_TPY54HSE7P4JZ5Z.png)
这个是最新的抓包工具， 目前支持抓 Web 、IOS、Android 三段抓包，平台也是全适配，Android 和 IOS 正在开发阶段，预计年底上线。
 ![image](https://bbs.kanxue.com/upload/attach/202305/944052_U8DZKRSK63K3PGF.png)
为什么要介绍这款工具呢？笔者主要是做移动端逆向，平常的抓包工具组合一般是 charles + VPN 。但是苦于不能写脚本头疼了好久，前面还用了 BurpSutie 的 Brida ，但是难用程度简直是地狱级，笔者配置花了一个晚上也没有配置好，最后只剩下放弃了。
见到这款抓包工具的时候，看到它可以写脚本，马上就行了实践，因为 reqable 的作者做 web 的测试比较多，对移动端甚少，所以算是第一个吃螃蟹的吧。
以前抓了一个包，无论是 Request 和 Response 都对 body 进行了加密，想结合着看收发包的情况，真的是抓耳挠腮。
 ![image](https://bbs.kanxue.com/upload/attach/202305/944052_RT767VR6V3YN4JS.png)
上图便是使用 reqable 进行的 APP 抓包，前提需要把它的证书放到系统目录下。我们同样可以用 VPN 的方式进行抓包，代理端口是 9000 , VPN 和 HTTP 都可以用这个端口，后台会根据协议的类型自动进行识别并捕获流量。
接下来就是写脚本动态的进行数据解密，我们参照 Brida ，用 RPC 的方式进行解密，目标 APP 是一个颜色 APP ，内容太炸裂，这里就不放了。
定位到解密的地方，是一个静态方法，APP 的解密代码
 ![image](https://bbs.kanxue.com/upload/attach/202305/944052_A96DT294GT37B7E.png)
先 Hook 拿到 Key 和 测试的数据，对 RPC 代码测试 ，成品代码：

 js 的脚本 ：

| 1234567891011121314 | `function decrypt(hexdata){``return` `new Promise(resolve` `=``> {``Java.perform(function main(){``let C1567` `=` `Java.use(``"android.support.v4.\u1079"``);``var key` `=` `"132f1537f85scxpcm59f7e318b9epa51"``var value` `=` `C1567[``"\u1546"``](key,hexdata)``resolve(value)``})``})``}` `rpc.exports` `=` `{``decrypt: decrypt``}` |
|-|-|

reqable 的脚本

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647 | `from` `reqable` `import` `*``import` `frida``import` `json` `script` `=` `None` `def` `on_message(message,data):``print``(message)` `def` `decryptData(script, data):``return` `script.exports.decrypt(data)` `def` `load():``devices` `=` `frida.get_usb_device()``session` `=` `devices.attach(``"cn.nvlee.cmpguw"``)` `filepath` `=` `r``"C:\Users\Administrator\Desktop\scripts\script.js"``with` `open``(filepath) as f:``jscode` `=` `f.read()` `script` `=` `session.create_script(jscode)``script.on(``"message"``,on_message)``script.load()``return` `script` `# 请求``def` `onRequest(context, request):``script` `=` `load()` `data` `=` `json.loads(``str``(request.body))[``"data"``]``result` `=` `decryptData(script, data)``print``(``"request result => "``, result)` `# Done``return` `request` `# 响应``def` `onResponse(context, response):` `script` `=` `load()` `data` `=` `json.loads(``str``(response.body))[``"data"``]``result` `=` `decryptData(script, data)``print``(``"response result => "``, result)` `# Done``return` `response` |
|-|-|

一起来看看解密的效果吧：
 ![image](https://bbs.kanxue.com/upload/attach/202305/944052_5TEC8BD7B8EEX7M.png)

 下个月这款软件就上线了，敬请期待吧

---

# 回复

## 回复 by 秋狝 (#2)

*2023-5-22 09:03*

6

## 回复 by seeeseee (#3)

*2023-5-22 09:12*

frida attach还是怪耗时的，要追求速度的话，安卓端开个http服务做联动感觉更快![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by nevinhappy (#4)

*2023-5-22 09:19*

Fiddler不挺好用的。。。

## 回复 by gamehack (#5)

*2023-5-22 09:48*

看上去还是挺不错的,记下了,感谢分享!

## 回复 by REerr (#6)

*2023-5-22 10:13*

mitmproxy不好用嘛

## 回复 by 新机穿越 (#7)

*2023-5-22 12:12*

能否用脚本调用抓包结果？

## 回复 by mb_bppcorlj (#8)

*2023-5-24 00:15*

可以抓tcp udp吗

## 回复 by RiDiN (#9)

*2023-5-25 16:57*

那你可能还没用过这个 <https://github.com/rev1si0n/lamda>

## 回复 by 小黄鸭爱学习 (#10)

*2023-6-26 17:04*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  frida attach还是怪耗时的，要追求速度的话，安卓端开个http服务做联动感觉更快[em_63]
>
>

要依赖frida的hook调用解密，光http服务还是不行。

## 回复 by 小黄鸭爱学习 (#11)

*2023-6-26 17:06*

fiddler调用App方法解析这方面还是不行，不过可以搭建hook rpc服务配合fiddler脚本，这个算是整合在一起了。
