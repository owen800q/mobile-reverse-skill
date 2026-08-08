---
title: '[原创]利用Frida，对新版Instagram注册流程抓包'
url: https://bbs.kanxue.com/thread-287984.htm
tid: 287984
author: lvcoffee
date: '2025-08-11'
tags: [Android安全, 原创, 基础理论, 逆向分析, HOOK注入, 工具脚本]
crawled_at: '2026-08-08T10:50:21+00:00'
replies: 18
---

追随大神的脚步（<https://bbs.kanxue.com/thread-267215.htm>），新版（391.0.0.42.82）发生了变化，没找到对应的类，只能另想他法。
1）根据前辈分析的结果，搜索“X-IG-App-ID”，在X.5ks中找到了“c5nq.A02("X-IG-App-ID", "567067343352427");”，看来这个是写死的固定值。

 函数是public final C6aU startRequest(C5nq c5nq, C5ns c5ns, C5rd c5rd) ；

2）然后发现这个startRequest一层一层的调用，用frida一层一层的跟踪下去，我是用的打印实现类的笨办法。

| 12345678910111213141516 | `function printStacks(){``var throwable` `=` `Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$new());``console.log(throwable);``}` `function getObjClassName(obj) {``const objClass` `=` `Java.use(``"java.lang.Object"``).getClass.``apply``(obj);``return` `Java.use(``"java.lang.Class"``).getName.``apply``(objClass);``}``var clazz` `=` `Java.use(``'X.5jm'``);` `clazz.startRequest.implementation` `=` `function() {` `console.log(``"\nX.5jm arguments[0] = "` `+``arguments[``0``] );` `console.log(``"X.5jm A01 is "` `+` `getObjClassName(this.A01.value) );` `printStacks();``return` `this.startRequest.``apply``(this,arguments);` `}` |
|-|-|

最后追踪到堆栈，这是嵌套了18层地狱吧

| 123456789101112131415161718192021222324252627282930313233343536 | `X.``5jm` `arguments[``0``]` `=` `{Uri: https:``/``/``graph.instagram.com``/``logging_client_events. RequestId:` `153045711``}``X.``5jm` `A01` `is` `com.instagram.api.tigon.TigonServiceLayer``java.lang.Throwable``at X.``5jm``.startRequest(Native Method)``at X.``5jn``.startRequest(:``22``)``at X.``5jq``.startRequest(:``52``)``at X.``5kA``.startRequest(:``351``)``at X.``5ka``.startRequest(:``23``)``at X.``5kb``.startRequest(:``207``)``at X.``5kk``.startRequest(:``95``)``at X.``5kl``.startRequest(:``59``)``at X.``5pb``.startRequest(:``280``)``at X.``5kn``.startRequest(:``36``)``at X.``5kq``.startRequest(:``86``)``at X.``5ks``.startRequest(:``110``)``at X.``5oj``.startRequest(:``31``)``at X.``5ok``.startRequest(:``21``)``at X.``5ol``.startRequest(:``92``)``at X.``5om``.startRequest(:``19``)``at X.``5pc``.startRequest(:``129``)``at X.``5pn``.startRequest(:``17``)``at X.``5pq``.startRequest(:``344``)``at X.``5pv``.startRequest(:``19``)``at X.``5qz``.startRequest(:``53``)``at X.``4tq``.startRequest(:``14``)``at X.``4tq``.A00(:``17``)``at X.``4sq``.A00(:``41``)``at X.``4sq``.A02(:``5``)``at com.instagram.analytics.analytics2.IGAnalytics2SimpleUploader.GET(:``71``)``at com.facebook.analytics2.logger.legacy.uploader.PrivacyControlledUploader.GET(:``2``)``at X.PRi.A00(:``34``)``at X.DF8.handleMessage(:``95``)``at android.os.Handler.dispatchMessage(Handler.java:``106``)``at android.os.Looper.loopOnce(Looper.java:``210``)``at android.os.Looper.loop(Looper.java:``299``)``at android.os.HandlerThread.run(HandlerThread.java:``67``)` |
|-|-|

“com.instagram.api.tigon.TigonServiceLayer”，这个类，看起来是把请求加到Executor去发送，位置应该是对了。

3）打印com.instagram.api.tigon.TigonServiceLayer.startRequest函数的参数

| 123456789101112131415161718192021222324 | `function printFields(obj) {` `console.log(``">>>printFields "` `+` `getObjClassName(obj) );``var fields` `=` `Java.use(``"java.lang.Object"``).getClass.``apply``(obj).getDeclaredFields();``fields.forEach(function (field) {``field.setAccessible(true);``try` `{``console.log(``"- "` `+` `field.getName()` `+` `" = "` `+` `field.get(obj));``} catch (e) {``console.log(``"- "` `+` `field.getName()` `+` `" = <无法读取>"``);``}``});``}` `var tigonServer` `=` `Java.use(``'com.instagram.api.tigon.TigonServiceLayer'``);``tigonServer.startRequest.implementation` `=` `function() {` `console.log(``"\n###tigonServer."`  `);``for` `(let index` `=` `0``; index < arguments.length; index``+``+``) {``const arg` `=` `arguments[index];``console.log(``"\narg["``+``index``+` `"] is "``+``getObjClassName(arg));` `printFields(arg);` `}``console.log(``"\n***tigonServer."`  `);` `return` `this.startRequest.``apply``(this,arguments);` `}` |
|-|-|

发现内容基本在第一个参数X.5nq里面

| 12345678910111213141516 | `arg[``0``]` `is` `X.``5nq``-` `printFields X.``5nq` `class` `X.``5nq``-` `A00` `=` `3``-` `A01` `=` `false``-` `A02` `=` `false``-` `A03` `=` `683607820``-` `A04` `=` `X.``5cr``@``5f615e1``-` `A05` `=` `X.``5kz``@``1780f06``-` `A06` `=` `1``-` `A07` `=` `https:``/``/``i.instagram.com``/``api``/``v1``/``bloks``/``async_action``/``com.bloks.http://www.bloks.caa.reg.confirmation.medium_selection.async``/``-` `A08` `=` `https:``/``/``i.instagram.com``/``api``/``v1``/``bloks``/``async_action``/``com.bloks.http://www.bloks.caa.reg.confirmation.medium_selection.async``/``-` `A09` `=` `[X``-``IG``-``App``-``Locale: zh_CN, X``-``IG``-``Device``-``Locale: zh_CN, X``-``IG``-``Mapped``-``Locale: zh_CN, X``-``Pigeon``-``Session``-``Id``: UFS``-``6314b0fe``-``36ba``-``43db``-``a0cf``-``2ba6c63f1be9``-``0``, X``-``Pigeon``-``Rawclienttime:` `1754642242.610``, X``-``IG``-``Bandwidth``-``Speed``-``KBPS:` `1902.000``, X``-``IG``-``Bandwidth``-``TotalBytes``-``B:` `0``, X``-``IG``-``Bandwidth``-``TotalTime``-``MS:` `0``, X``-``Bloks``-``Version``-``Id``: fb1049782079182ce7240ad652c0cdd80f0c2ffdca5ce115931bf8dd16c52c6f, X``-``IG``-``WWW``-``Claim:` `0``, X``-``Bloks``-``Prism``-``Button``-``Version: CONTROL, X``-``Bloks``-``Prism``-``Indigo``-``Link``-``Version:` `0``, X``-``Bloks``-``Prism``-``Colors``-``Enabled: false, X``-``Bloks``-``Prism``-``Font``-``Enabled: false, X``-``Bloks``-``Is``-``Layout``-``RTL: false, X``-``IG``-``Device``-``ID``: ee217655``-``e663``-``47cb``-``9c19``-``167198cc9066``, X``-``IG``-``Family``-``Device``-``ID``: e39f3ddd``-``179f``-``4be3``-``9bea``-``8840233ca3d8``, X``-``IG``-``Android``-``ID``: android``-``f4d4cc0c1de7fb83, X``-``IG``-``Timezone``-``Offset:` `28800``, X``-``IG``-``Nav``-``Chain: com.bloks.http://www.caa.login.login_homepage:com.bloks.www.caa.login.login_homepage:``1``:button:``1754642010.457``::,IgCdsScreenNavigationLoggerModule:com.bloks.http://www.bloks.caa.reg.contactpoint_phone:``2``:button:``1754642025.719``::, X``-``IG``-``CLIENT``-``ENDPOINT: com.bloks.http://www.bloks.caa.reg.contactpoint_phone, X``-``FB``-``Connection``-``Type``: WIFI, X``-``IG``-``Connection``-``Type``: WIFI, X``-``IG``-``Capabilities:` `3brTv10``=``, X``-``IG``-``App``-``ID``:` `567067343352427``]``-` `A0A` `=` `{enqueue_time``=``308069416``}``-` `A0B` `=` `false``-` `A0C` `=` `true``-` `A0D` `=` `26` |
|-|-|

A08和A09很明显，一个是请求的URL，一个是请求头。请求内容盲猜在A04和A05里面。JADX打开X.5cr的类，里面也是一些像头一样的类，感觉不是内容。打开X.5kz类，里面就2个属性值A00和A01。

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `public final` `class` `C5kz implements C5lA {``public final C4ym A00;``public final byte[] A01;` `@Override` `/``/` `X.C5lA``public final C4ym BDk() {``return` `null;``}` `@Override` `/``/` `X.C5lA``public final C4ym BE1() {``return` `this.A00;``}` `@Override` `/``/` `X.C5lA``public final InputStream F1R() {``return` `new ByteArrayInputStream(this.A01);``}` `@Override` `/``/` `X.C5lA``public final` `long` `getContentLength() {``return` `this.A01.length;``}` `public C5kz(``List` `list``, boolean z) {``String` `str``;``String A00` `=` `C5la.A00(``list``);``Charset forName` `=` `Charset.forName(``"UTF-8"``);``C0Ce.A08(forName);``byte[] bytes` `=` `A00.getBytes(forName);``C0Ce.A08(bytes);``this.A01` `=` `bytes;``if` `(z) {``str` `=` `"application/x-www-form-urlencoded; charset=UTF-8"``;``}` `else` `{``str` `=` `"application/x-www-form-urlencoded"``;``}``this.A00` `=` `new C4ym(``"Content-Type"``,` `str``);``}``}` |
|-|-|

Hook构造函数，A01里保存的确实就是发送的内容。

| 123456789101112 | `var C5kz` `=` `Java.use(``'X.5kz'``);``C5kz.$init.implementation` `=` `function() {` `var ret``=` `this.$init.``apply``(this,arguments);` `console.log(``"\n###X.5kz"`  `);` `var` `len``=``this.A01.value.length;``console.log(``"byte[] A01 len:"``+``len``);` `if``(``len``>``0``){``console.log(``"X.5kz.A01:"` `+` `jString.$new(this.A01.value));``}``console.log(``"\n***X.5kz"`  `);` `return` `ret;``}` |
|-|-|

返回的值，是URL编码的

| 123 | `###X.5kz``byte[] A01` `len``:``9730``X.``5kz``.A01:params``=``%``7B``%``22client_input_params``%``22``%``3A``%``7B``%``22flash_call_permissions_status``%``22``%``3A``%``7B``%``22READ_PHONE_STATE``%``22``%``3A``%``22DENIED``%``22``%``2C``%``22READ_CALL_LOG``%``22``%``3A``%``22DENIED``%``22``%``2C``%``22ANSWER_PHONE_CALLS``%``22``%``3A``%``22DENIED``%``22``%``7D``%``2C``%``22device_id``%``22``%``3A``%``22android``-``f4d4cc0c1de7fb83``%``22``%``2C``%``22was_headers_prefill_available``%``22``%``3A0``%``2C``%``22login_upsell_phone_list``%``22``%``3A``%``5B``%``5D``%``2C``%``22whatsapp_installed_on_client``%``22``%``3A1``%``2C``%``22msg_previous_cp``%``22``%``3A``%``22``%``22``%``2C``%``22switch_cp_first_time_loading``%``22``%``3A1``%``2C``%``22accounts_list``%``22``%``3A``%``5B``%``5D``%``2C``%``22confirmed_cp_and_code``%``22``%``3A``%``7B``%``7D``%``2C``%``22country_code``%``22``%``3A``%``22``%``22``%``2C``%``22family_device_id``%``22``%``3A``%``22e39f3ddd``-``179f``-``4be3``-``9bea``-``8840233ca3d8``%``22``%``2C``%``22block_store_machine_id``%``22``%``3A``%``22``%``22``%``2C``%``22fb_ig_device_id``%``22``%``3A``%``5B``%``5D``%``2C``%``22phone``%``22``%``3A``%``22855385468758``%``22``%``2C``%``22lois_settings``%``22``%``3A``%``7B``%``22lois_token``%``22``%``3A``%``22``%``22``%``7D``%``2C``%``22cloud_trust_token``%``22``%``3Anull``%``2C``%``22` |
|-|-|

URL解码，然后再格式化JSON，就看到请求的参数了

| 123456789101112131415161718 | `{``"client_input_params"``: {``"flash_call_permissions_status"``: {``"READ_PHONE_STATE"``:` `"DENIED"``,``"READ_CALL_LOG"``:` `"DENIED"``,``"ANSWER_PHONE_CALLS"``:` `"DENIED"``},``"device_id"``:` `"android-f4d4cc0c1de7fb83"``,``"was_headers_prefill_available"``:` `0``,``"login_upsell_phone_list"``: [],``"whatsapp_installed_on_client"``:` `1``,``"msg_previous_cp"``: "",``"switch_cp_first_time_loading"``:` `1``,``"accounts_list"``: [],``"confirmed_cp_and_code"``: {},``"country_code"``: "",``"family_device_id"``:` `"e39f3ddd-179f-4be3-9bea-8840233ca3d8"``,``"block_store_machine_id"``: "",` |
|-|-|

后面就是通过native函数，发送出去

| 1234567 | `public` `class` `TigonXplatService extends TigonServiceHolder {``public static final` `int` `DEFAULT_BUFFER_SIZE` `=` `1024``;``public final C1z9 mTigonRequestCounter;` `private native TigonXplatRequestToken sendRequestBodyBufferIntegerBuffer(TigonRequest tigonRequest, byte[] bArr,` `int` `i, TigonBodyProvider tigonBodyProvider, byte[] bArr2,` `int` `i2, TigonCallbacks tigonCallbacks, Executor executor);` `private native TigonXplatRequestToken sendRequestIntegerBuffer(TigonRequest tigonRequest, byte[] bArr,` `int` `i, ByteBuffer[] byteBufferArr,` `int` `i2, TigonCallbacks tigonCallbacks, Executor executor);` |
|-|-|

到这里，路还长着，发送的实际内存，是加密的，这个后面要具体分析。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202508/911417_GKBJDQUPJ6D4EAX.webp)

---

# 回复

## 回复 by wx_春风十里 (#2)

*2025-8-12 00:44*

reg_context应该是服务器返回的数据

## 回复 by @=llfly (#3)

*2025-8-12 09:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)  frida 用的溜

## 回复 by lvcoffee (#4)

*2025-8-12 09:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_春风十里](https://bbs.kanxue.com/user-767092.htm)
>
>  reg_context应该是服务器返回的数据
>
>

这是请求包里的，不过叫“server_params”确实没理解意思

## 回复 by mb_jlxjrnqk (#5)

*2025-8-12 20:56*

私个联系方式，有偿求后续

## 回复 by mb_jlxjrnqk (#6)

*2025-8-12 21:04*

>
> [lvcoffee](https://bbs.kanxue.com/user-911417.htm)
>
>  这是请求包里的，不过叫“server_params”确实没理解意思
>
>

有偿求后续

## 回复 by wx_春风十里 (#7)

*2025-8-13 03:31*

>
> [lvcoffee](https://bbs.kanxue.com/user-911417.htm)
>
>  这是请求包里的，不过叫“server_params”确实没理解意思
>
>

reg_context是上一个请求返回的，你过掉sslpinning抓包看就知道了,带regm的就是![image](https://bbs.kanxue.com/upload/attach/202508/767092_HHXT3JA8A3RTP3C.webp)

## 回复 by lvcoffee (#8)

*2025-8-14 09:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_春风十里](https://bbs.kanxue.com/user-767092.htm)
>
>
>
>
>
>
>
>  lvcoffee
>
>
>
>  这是请求包里的，不过叫“server_params”确实没理解意思
>
>  reg_context是上一个请求返回的， ...
>
>

感谢解答，我继续努力搞明白

## 回复 by tylrr (#9)

*2025-8-25 23:10*

私个联系方式，有偿求爬ins数据方法

## 回复 by kkkk1344 (#10)

*2025-8-31 13:19*

求 ins rcs方面技术大牛 付费请教

## 回复 by wx_心在何方 (#11)

*2025-9-10 15:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_春风十里](https://bbs.kanxue.com/user-767092.htm)
>
>
>
>
>
>
>
>  lvcoffee
>
>
>
>  这是请求包里的，不过叫“server_params”确实没理解意思
>
>  reg_context是上一个请求返回的， ...
>
>

有没有大佬，逆向出来了解析这种结构数据的app代码，求一份

## 回复 by mb_ynmeghig (#12)

*2025-10-10 14:10*

大量出Ins账号以及ins全协议各种数据接口以及私信协议

## 回复 by Eclora (#13)

*2025-11-1 16:35*

他的注册流程基本上是 初始化Graphql>获取Lisp脚本执行信息。并且将用到的值和方法都放到了返回信息里面>选择对应的操作流程>通过LISP脚本执行获取返回值提交>基本上是一层套一层,实现整体注册链路。

## 回复 by Eclora (#14)

*2025-11-1 16:37*

注册的话设备风控解决不解决问题不大,主要是后续养号操作流程。

## 回复 by Sungt. (#15)

*2025-11-21 14:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ynmeghig](https://bbs.kanxue.com/user-1053137.htm)
>
>  大量出Ins账号以及ins全协议各种数据接口以及私信协议
>
>

fb 的协议是否有，有偿

## 回复 by cx_yiran (#16)

*2026-2-3 14:49*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Eclora](https://bbs.kanxue.com/user-1049893.htm)
>
>  他的注册流程基本上是 初始化Graphql>获取Lisp脚本执行信息。并且将用到的值和方法都放到了返回信息里面>选择对应的操作流程>通过LISP脚本执行获取返回值提交>基本上是 ...
>
>

我现在就很疑惑啊，我找到了lisp脚本位置了，也看到明文的json了，但是吧，我改了没用，设备风控该有还是有，主要是关联设备风控

## 回复 by Eclora (#17)

*2026-2-9 16:30*

>
> [cx_yiran](https://bbs.kanxue.com/user-949825.htm)
>
>  我现在就很疑惑啊，我找到了lisp脚本位置了，也看到明文的json了，但是吧，我改了没用，设备风控该有还是有，主要是关联设备风控
>
>

因为他这部分并不涉及设备信息的上传,设备信息的上传主要在日志部分。 https://m.facebook.com/a/bz?fb_dtsg=* 这个请求 负责当前会话的日志请求 包含设备、操作动作、加载时间、操作变化等

## 回复 by cx_yiran (#18)

*2026-2-24 22:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Eclora](https://bbs.kanxue.com/user-1049893.htm)
>
>  因为他这部分并不涉及设备信息的上传,设备信息的上传主要在日志部分。 https://m.facebook.com/a/bz?fb_dtsg=* 这个请求 负责当前会话的日志请求 包含设备、操作动作、加 ...
>
>

我好像看到了这个地址的，但我没跟，因为我抓到了device_info的相关函数，是一个地方吗？

## 回复 by Eclora (#19)

>
> [cx_yiran](https://bbs.kanxue.com/user-949825.htm)
>  我好像看到了这个地址的，但我没跟，因为我抓到了device_info的相关函数，是一个地方吗？
>

本质上他的日志遥测所上报的数据就是他后面审核这个账号是否正常注册存活判断的关键.device_info有用.但并不止
