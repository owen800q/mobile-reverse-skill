---
title: frida分析支付某扫码转账生成URI流程
url: https://bbs.kanxue.com/thread-284764.htm
tid: 284764
author: kzzll
date: '2024-12-12'
tags: [Android安全, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:17:03+08:00'
replies: 7
---

## 介绍

需要分析支付某打开扫一扫，扫到目标二维码后是如何跳转到转账页面的。

## 定位

发现扫码从数据包无从下手定位，尝试关键字：QRScan，QRCode，Translate等都找不到对应的函数，所以最终通过View的点击事件。

| 123456789 | `var Button` `=` `Java.use(``"android.widget.Button"``);``Button.setOnClickListener.overload(``"android.view.View$OnClickListener"``).implementation` `=` `function (listener) {``console.log(``"Button clicked"``);``/``/``listener.onClick(this);` `/``/` `调用原来的点击事件``printStack();``this.setOnClickListener(listener);``console.log(``"Button clicked end"``);``return``;``};` |
|-|-|

打印了堆栈，从堆栈结果里面找到了一个疑似创建扫码相机的View：

**com.alipay.mobile.scan.ui2.NScanTopView**

因为这个类代码量巨大，5000多行，而且都是混淆过的名称，我直接发给ai进行分析，得出了大概扫描后的回调结果是在a方法：

| 1234 | `@Override` `/``/` `com.alipay.mobile.scan.ui.BaseScanTopView``public final void a(com.alipay.mobile.bqcscanservice.BQCScanResult r25) {``/``/` `... existing code ...``}` |
|-|-|

但是代码的过程看不到，只能看Smail指令，并且对应参数r25里面的BQCScanResult也是啥都没有，只能通过方法的执行过程分析（还是给AI分析）随后得出hook代码：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `let NScanTopView` `=` `Java.use(``"com.alipay.mobile.scan.ui2.NScanTopView"``);``NScanTopView[``"a"``].overload(``'com.alipay.mobile.bqcscanservice.BQCScanResult'``).implementation` `=` `function (result) {``console.log(``"NScanTopView.a is called"``);` `if``(result !``=` `null) {``/``/` `1.` `先确认是否是 MultiMaScanResult``if``(result.$className` `=``=``=` `"com.alipay.mobile.mascanengine.MultiMaScanResult"``) {``let multiResult` `=` `Java.cast(result, Java.use(``"com.alipay.mobile.mascanengine.MultiMaScanResult"``));` `/``/` `2.` `获取 maScanResults 数组``let scanResults` `=` `multiResult.maScanResults.value;``if``(scanResults && scanResults.length >` `0``) {``/``/` `3.` `获取第一个结果``let firstResult` `=` `scanResults[``0``];` `/``/` `4.` `打印扫描文本``console.log(``"Scan Text:"``, firstResult.text.value);` `/``/` `5.` `打印更多信息(如果需要)``if``(firstResult.rect) {``console.log(``"Scan Rect:"``, JSON.stringify({``left: firstResult.rect.value.left,``top: firstResult.rect.value.top,``right: firstResult.rect.value.right,``bottom: firstResult.rect.value.bottom``}));``}` `if``(firstResult.``type``) {``console.log(``"Scan Type:"``, firstResult.``type``.value);``}``}``}` `/``/` `备用方案：通过反射获取所有可能的属性``try` `{``let fields` `=` `result.getClass().getDeclaredFields();``for``(let i` `=` `0``; i < fields.length; i``+``+``) {``let field` `=` `fields[i];``field.setAccessible(true);``console.log(`Field ${field.getName()}: ${field.get(result)}`);``}``} catch(e) {``console.log(``"Error getting fields:"``, e);``}``}` `/``/` `调用原始方法``return` `this[``"a"``](result);``};` |
|-|-|

输出结果：

| 12345678910111213141516 | `Scan Text: https:``/``/``qr.alipay.com``/``fkx17137rejqeh4j3v4cib0?t``=``1733923946234``Scan Rect: {``"left"``:{``"_p"``:[``"<instance: android.graphics.Rect>"``,``2``,{``"className"``:``"int"``,``"name"``:``"I"``,``"type"``:``"int32"``,``"size"``:``1``,``"byteSize"``:``4``,``"defaultValue"``:``0``},``"0x7048f4b8"``,``"0x7ae97bd488"``,``"0x7ae97c07a0"``]},``"top"``:{``"_p"``:[``"<instance: android.graphics.Rect>"``,``2``,{``"className"``:``"int"``,``"name"``:``"I"``,``"type"``:``"int32"``,``"size"``:``1``,``"byteSize"``:``4``,``"defaultValue"``:``0``},``"0x7048f4d8"``,``"0x7ae97bd488"``,``"0x7ae97c07a0"``]},``"right"``:{``"_p"``:[``"<instance: android.graphics.Rect>"``,``2``,{``"className"``:``"int"``,``"name"``:``"I"``,``"type"``:``"int32"``,``"size"``:``1``,``"byteSize"``:``4``,``"defaultValue"``:``0``},``"0x7048f4c8"``,``"0x7ae97bd488"``,``"0x7ae97c07a0"``]},``"bottom"``:{``"_p"``:[``"<instance: android.graphics.Rect>"``,``2``,{``"className"``:``"int"``,``"name"``:``"I"``,``"type"``:``"int32"``,``"size"``:``1``,``"byteSize"``:``4``,``"defaultValue"``:``0``},``"0x7048f4a8"``,``"0x7ae97bd488"``,``"0x7ae97c07a0"``]}}``Scan` `Type``: QR``Field candidate: false``Field classicFrameCount:` `44``Field frameCount:` `44``Field frameType:` `0``Field maScanResults: [Lcom.alipay.mobile.mascanengine.MaScanResult;@``178c311``Field readerParams: null``Field recognizedPerformance:` `type``=``Normal^scanType``=``3``^unrecognizedFrame``=``42``^sumDurationOfUnrecognized``=``1694``^durationOfRecognized``=``51``^durationOfBlur``=``0``^durationOfBlurSVM``=``0``^detectFrameCountBlurSVM``=``0``^detectAvgDurationBlurSVM``=``0.0``^durationOfNoNeedCheckBlurSVM``=``0``^whetherGetTheSameLaplaceValue``=``false^sameLaplaceValueCount``=``0``^``Field rsBinarized: false``Field rsBinarizedCount:` `0``Field rsInitTime:` `0``Field totalEngineCpuTime: null``Field totalEngineTime:` `2811662``Field totalScanTime:` `48566` |
|-|-|

这样就拿到了扫码结果，但是我需要接着跟踪它将扫码结果进行转账通讯的部分，经过分析，最终处理扫描二维码的逻辑是在

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374757677787980818283848586878889909192 | `/``/` `1.` `Hook BaseScanTopView 的所有方法，找到使用 c 的地方``let BaseScanTopView` `=` `Java.use(``"com.alipay.mobile.scan.ui.BaseScanTopView"``);``let NScanTopView` `=` `Java.use(``"com.alipay.mobile.scan.ui2.NScanTopView"``);``/``/` `Hook 所有方法``let methods` `=` `BaseScanTopView.``class``.getDeclaredMethods();``methods.forEach(method` `=``> {``let methodName` `=` `method.getName();``if``(BaseScanTopView[methodName]) {``try` `{``BaseScanTopView[methodName].implementation` `=` `function() {``console.log(`\n[``*``] BaseScanTopView.${methodName} 被调用`);` `/``/` `尝试通过反射获取 c 字段的值``try` `{``let field` `=` `this.getClass().getSuperclass().getDeclaredField(``"c"``);``field.setAccessible(true);``let cValue` `=` `field.get(this);``if``(cValue) {``console.log(``"[*] c 字段值类型:"``, cValue.$className);` `/``/` `如果是 by 接口的实现，hook 它的方法``if``(Java.use(``"com.alipay.mobile.scan.ui.by"``).``class``.isAssignableFrom(cValue.getClass())) {``console.log(``"[*] 找到 by 接口实现类:"``, cValue.$className);` `/``/` `Hook 这个实现类的方法``let implClass` `=` `Java.use(cValue.$className);``if``(implClass.a) {``implClass.a.overload(``'com.alipay.mobile.mascanengine.MaScanResult'``,` `'com.alipay.mobile.scan.util.DataTransChannel'``)``.implementation` `=` `function(maScanResult, dataTransChannel) {``console.log(``"\n[*] by 实现类的 a 方法被调用"``);``if``(maScanResult !``=` `null) {``console.log(``"[*] 扫描结果:"``, maScanResult.text.value);``}``return` `this.a(maScanResult, dataTransChannel);``};``}``}``}``} catch(e) {``/``/``console.log(``"[!] 获取 c 字段失败:"``, e);``}` `/``/` `调用原方法``return` `this[methodName].``apply``(this, arguments);``};``} catch(e) {``/``/``console.log(`[!] Hook ${methodName} 失败:`, e);``}``}``});` `/``/` `2.` `Hook NScanTopView 的 b 方法``NScanTopView[``"b"``].overload(``'com.alipay.mobile.bqcscanservice.BQCScanResult'``).implementation` `=` `function (bQCScanResult) {``console.log(``"\n[*] NScanTopView.b 被调用"``);` `/``/` `在调用前尝试获取 c 字段``try` `{``let field` `=` `this.getClass().getSuperclass().getDeclaredField(``"c"``);``field.setAccessible(true);``let cValue` `=` `field.get(this);``if``(cValue) {``console.log(``"[*] c 字段实现类:"``, cValue.$className);``}``} catch(e) {``console.log(``"[!] 获取 c 字段失败:"``, e);``}` `let result` `=` `this[``"b"``](bQCScanResult);``return` `result;``};` `/``/` `3.` `动态查找并 hook by 接口的实现类``Java.choose(``"com.alipay.mobile.scan.ui.by"``, {``onMatch: function(instance) {``console.log(``"[*] 找到 by 接口实例:"``, instance.$className);``/``/` `Hook 这个实例的方法``let implClass` `=` `Java.use(instance.$className);``if``(implClass.a) {``implClass.a.overload(``'com.alipay.mobile.mascanengine.MaScanResult'``,` `'com.alipay.mobile.scan.util.DataTransChannel'``)``.implementation` `=` `function(maScanResult, dataTransChannel) {``console.log(``"\n[*] by 实现类的 a 方法被调用"``);``if``(maScanResult !``=` `null) {``console.log(``"[*] 扫描结果:"``, maScanResult.text.value);``}``return` `this.a(maScanResult, dataTransChannel);``};``}``},``onComplete: function() {}``});` |
|-|-|

输出结果：

| 123456789101112 | `[``*``] NScanTopView.b 被调用``[``*``] c 字段实现类: com.alipay.mobile.scan.as.main.MainCaptureActivity``MainCaptureActivity.a` `is` `called: maScanResult``=``com.alipay.mobile.mascanengine.MaScanResult@``80f5308``, dataTransChannel``=``DataTransChannel{isFromAlbum``=``false, albumImagePath``=``'null'``, scanCode``=``'null'``, payLinkToken``=``'null'``, controlType``=``'camera'``, isFromRoute``=``false, isCache``=``false, bizType``=``'null'``, custProgressDialog``=``com.alipay.mobile.scan.ui2.NBluePointView{a02faa1 I.E...... ......I.` `0``,``0``-``1080``,``2028``}}``MainCaptureActivity.a result``=``true` `[``*``] BaseScanTopView.p 被调用``[``*``] c 字段值类型: com.alipay.mobile.scan.as.main.MainCaptureActivity``[``*``] 找到 by 接口实现类: com.alipay.mobile.scan.as.main.MainCaptureActivity` `[``*``] BaseScanTopView.q 被调用``[``*``] c 字段值类型: com.alipay.mobile.scan.as.main.MainCaptureActivity``[``*``] 找到 by 接口实现类: com.alipay.mobile.scan.as.main.MainCaptureActivity` |
|-|-|

然后去查看了 com.alipay.mobile.scan.as.main.MainCaptureActivity 这个类的 a 方法实现过程：

| 123456789101112 | `public final boolean a(com.alipay.mobile.mascanengine.MaScanResult r17, com.alipay.mobile.scan.util.DataTransChannel r18) {``/``*` `r16` `=` `this;``r1` `=` `r16``…………………………``…………………………``…………………………``boolean r0` `=` `r2.a(r3, r4, r5, r6, r7, r8)` `*``/``}` |
|-|-|

因为无法正常编译成java代码，并且很长，一如既往的让AI帮我分析，AI得出结果这个方法是一个判断扫描结果类型，进行路由分发的

| 123456789101112131415161718192021222324 | `/``/` `判断不同的扫码类型``com.alipay.mobile.mascanengine.MaScanType r3` `=` `com.alipay.mobile.mascanengine.MaScanType.PRODUCT``com.alipay.mobile.mascanengine.MaScanType r11` `=` `r2.``type` `if` `(r3` `=``=` `r11) goto Ldb` `/``/` `商品条码``/``/` `... 其他类型判断``com.alipay.mobile.mascanengine.MaScanType r3` `=` `com.alipay.mobile.mascanengine.MaScanType.QR` `/``/` `二维码` `/``/` `二维码处理``if` `(r3` `=``=` `r11) goto Lc3` `/``/` `QR类型``r10.put(r9, r3)` `/``/` `存储扫描文本``/``/` `处理隐藏数据``if` `(!TextUtils.isEmpty(r2.hiddenData)) {``r10.put(``"hiddenData"``, r2.hiddenData)``}` `/``/` `收集扫描性能数据``r0.put(``"totalTime"``, r8)` `r0.put(``"scanTime"``, r8)``r0.put(``"realTime"``, r8)` `com.alipay.phone.scancode.y.a r0` `=` `r1.d``/``/` `... 参数准备``boolean r0` `=` `r2.a(r3, r4, r5, r6, r7, r8)` `/``/` `调用实际的业务处理方法` |
|-|-|

然后在这个混淆的方法里面，找到了关键类
**com.alipay.phone.scancode.y.a**

| 1234567891011121314151617181920 | `let ScanCodeHandler` `=` `Java.use(``"com.alipay.phone.scancode.y.a"``);` `ScanCodeHandler.a.overload(``'java.lang.String'``,` `'java.util.Map'``,` `'java.lang.String'``,` `'java.lang.String'``,` `'com.alipay.mobile.scan.util.DataTransChannel'``,` `'java.lang.String'``).implementation` `=` `function(str1,` `map``, str2, str3, channel, str4) {``console.log(``"\n[*] 扫码业务处理被调用"``);``console.log(``"[*] 扫描类型:"``, str1);``console.log(``"[*] 扫描内容:"``, str3);` `let result` `=` `this.a(str1,` `map``, str2, str3, channel, str4);``console.log(``"[*] 处理结果:"``, result);``return` `result;``};`  `[``*``] 扫码业务处理被调用``[``*``] 扫描类型: qrCode``[``*``] 扫描内容: https:``/``/``qr.alipay.com``/``fkx17``*``*``*``*``*``*``0``?t``=``1733900000000``[``*``] 处理结果: true``MainCaptureActivity.a result``=``true` |
|-|-|

最后跟踪进 a 方法里面的实现过程（发现也是无法正常编译的java代码）
这个函数的过程作用大致如下：
1、初始化参数处理
2、检查是否由路由传过来的参数
3、检查是否支持离线支付
4、处理路由
5、缓存处理
6、记录支付行为
最后，hook了这个方法里面的相关涉及的类，得出hook代码以及输出结果

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182838485868788 | `/``/` `1.` `Hook 主要的路由处理方法``let CodeRouter` `=` `Java.use(``"com.alipay.phone.scancode.y.a"``);``CodeRouter.a.overload(``'java.lang.String'``,` `'java.util.Map'``,` `'java.lang.String'``,` `'java.lang.String'``,` `'int'``,` `'java.lang.String'``)``.implementation` `=` `function(``type``,` `map``, sourceId, content, flag, token) {``console.log(``"\n[*] 扫码支付路由被调用"``);``console.log(``"[*] 类型:"``,` `type``);``console.log(``"[*] 内容:"``, content);``console.log(``"[*] 来源ID:"``, sourceId);``console.log(``"[*] Token:"``, token);` `/``/` `打印``Map``参数`  `/``/` `2.` `Hook DataTransChannel``try` `{``let channel` `=` `this.D.value;``if``(channel !``=` `null) {``console.log(``"[*] DataTransChannel 信息:"``);``console.log(``"  是否来自相册:"``, channel.f115683a.value);``console.log(``"  图片路径:"``, channel.b.value);``console.log(``"  扫描内容:"``, channel.c.value);``console.log(``"  Channel类型:"``, channel.e.value);` `/``/` `打印额外参数``if``(channel.m !``=` `null) {``let extraParams` `=` `channel.m.value;``console.log(``"[*] 额外参数:"``);``let extraIterator` `=` `extraParams.entrySet().iterator();``while``(extraIterator.hasNext()) {``let entry` `=` `extraIterator.``next``();``console.log(``"  "``, entry.getKey()` `+` `" = "` `+` `entry.getValue());``}``}``}``} catch(e) {``console.log(``"[!] 获取Channel信息失败:"``, e);``}` `/``/` `3.` `Hook 离线支付检查``try` `{``if``(this.I !``=` `null) {``let offlineHandler` `=` `this.I.value;``let offlineResult` `=` `offlineHandler.a(content);``if``(offlineResult !``=` `null) {``console.log(``"[*] 离线支付信息:"``);``console.log(``"  URI:"``, offlineResult.f);``console.log(``"  Method:"``, offlineResult.g);``console.log(``"  Type:"``, offlineResult.d);``}``}``} catch(e) {``console.log(``"[!] 获取离线支付信息失败:"``, e);``}` `/``/` `4.` `Hook RouteInfo 创建``try` `{``let RouteInfo` `=` `Java.use(``"com.alipay.mobile.scan.biz.RouteInfo"``);``RouteInfo.$init.implementation` `=` `function() {``console.log(``"[*] 创建新的RouteInfo"``);``return` `this.$init();``};` `RouteInfo.setUri.implementation` `=` `function(uri) {``console.log(``"[*] 设置RouteInfo URI:"``, uri);``return` `this.setUri(uri);``};` `RouteInfo.setMethod.implementation` `=` `function(method) {``console.log(``"[*] 设置RouteInfo Method:"``, method);``return` `this.setMethod(method);``};``} catch(e) {``console.log(``"[!] Hook RouteInfo失败:"``, e);``}` `/``/` `打印调用栈``console.log(``"[*] 调用栈:"``);``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Exception"``).$new()));` `let result` `=` `this.a(``type``,` `map``, sourceId, content, flag, token);``console.log(``"[*] 路由处理结果:"``, result);``return` `result;``};` `[``*``] 设置RouteInfo Method: native``[``*``] 创建新的RouteInfo``[``*``] 设置RouteInfo Method: native``[``*``] 设置RouteInfo URI: alipays:``/``/``platformapi``/``startapp?appId``=``20001001``&bizType``=``UTP_QR_CODE&pageData``=``%``7B``%``22tpl``%``22``%``*``*``*``*``*``*``*` |
|-|-|

通过输出结果，发现最后会生成出路由URI，用于唤起支付界面的，尝试通过adb直接打开这个URI看看是否能直接跳转到转账界面。

adb shell am start -a android.intent.action.VIEW -d "alipays://platformapi/startapp?appId=20001001&bizType=UTP_QR_CODE&pageData=省略参数"

最后成功直接打开转账界面，由此分析出了整个扫码转账的执行环节。。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-12-12 10:08*

感谢分享

## 回复 by 你瞒我瞒 (#3)

*2024-12-13 09:15*

大佬能否提供一个apk样本

## 回复 by koflfy (#4)

*2024-12-13 15:13*

能否提供一个apk样本

## 回复 by KingSelyF (#6)

*2024-12-20 17:15*

好一个面向AI编程

## 回复 by kzzll (#7)

*2024-12-22 20:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  koflfy](https://bbs.kanxue.com/user-111569.htm)
>
>  能否提供一个apk样本
>
>

10.5.28.8100

## 回复 by wx_范迪塞尔 (#8)

*2025-3-28 11:10*

你好 又样本么

## 回复 by wx_沉默的逗比 (#9)

*2025-4-2 15:29*

为什么分析唤起支付页面的功能？
