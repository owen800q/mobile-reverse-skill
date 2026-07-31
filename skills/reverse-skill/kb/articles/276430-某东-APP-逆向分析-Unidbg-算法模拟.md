---
title: '[原创]某东 APP 逆向分析+ Unidbg 算法模拟'
url: https://bbs.kanxue.com/thread-276430.htm
tid: 276430
author: KKKKKKKEM
date: '2023-03-11'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:52:02+08:00'
replies: 17
---

>
> 最近正好在学习逆向与unidbg，旨在记录一下学习过程(纯小白文，一步步分析)
>
>
>

# 环境准备

| 1 | `com.jingdong.app.mall``=``=``11.6``.``4` |
|-|-|

# 入口定位

逆向分析，发现 `params` 里面有一个 `sign` 以及请求头里面有一个 `jdgs`

 首先我们发现京东的 `sign` 是 `32` 位的，猜测其可能是 `md5` 之类的 `hash` 算法，既然是 `hash` 算法，那么就大概率会用到 `getBytes` 方法，我们首先 `hook` 一下 `java.lang.String` 的 `getBytes` 方法，代码如下：

| 123456789101112131415161718192021 | `/``/` `获取 Java 的字符串``const` `str` `=` `Java.use(``'java.lang.String'``);` `/``/` `重载  getBytes 方法 (因为常用的` `Hash` `算法一般都会调用字符串的 getBytes 方法)``str``.getBytes.overload().implementation` `=` `function () {`  `var response` `=` `this.getBytes()``var str1` `=` `this.toString();` `/``/` `如果 string 里面包含了 functionId （其他关键字也可以，需要自己尝试）``if` `(str1.indexOf(``"functionId"``) >``=` `0``) {``/``/` `输出找到了字符串``console.log(``"find string:"``, str1);` `/``/` `打印一下堆栈``console.log(Java.use(``"android.util.Log"``).getStackTraceString(Java.use(``"java.lang.Throwable"``).$new()));``}` `return` `response;``}` |
|-|-|

使用 `firda` 加载脚本后进入详情页就发现出现了以下堆栈

| 1234567891011121314 | `java.lang.Throwable``at java.lang.String.getBytes(Native Method)``at com.jd.security.jdguard.a.e.o(SourceFile:``15``)``at com.jd.security.jdguard.a.e.i(SourceFile:``3``)``at com.jd.security.jdguard.a.c.a(SourceFile:``10``)``at com.jd.security.jdguard.a.c.b(SourceFile:``4``)``at com.jingdong.common.guard.JDGuardHelper$``1.genSign``(SourceFile:``1``)``at com.jingdong.jdsdk.network.toolbox.HttpSettingTool.doSignUsingJdGuard(SourceFile:``10``)``at com.jingdong.jdsdk.network.toolbox.ParamBuilderForJDMall.setupParams(SourceFile:``23``)``at com.jingdong.jdsdk.network.toolbox.HttpSettingTool.setupParams(SourceFile:``2``)``at com.jingdong.jdsdk.network.toolbox.HttpGroupAdapter$RequestTask.run(SourceFile:``14``)``at java.util.concurrent.ThreadPoolExecutor.runWorker(ThreadPoolExecutor.java:``1167``)``at java.util.concurrent.ThreadPoolExecutor$Worker.run(ThreadPoolExecutor.java:``641``)``at java.lang.Thread.run(Thread.java:``919``)` |
|-|-|

通过以上堆栈我们发现了疑似入口为：`com.jingdong.common.guard.JDGuardHelper$1.genSign`， `jadx` 源码如下：

| 123 | `public` `Map``<String, String> genSign(URI uri, byte[] bArr, String` `str``, String str2, boolean z) {``return` `c.b(uri, bArr,` `str``, str2, z);``}` |
|-|-|

因此我们再次 `hook` 验证，代码如下：

| 12345678910111213141516171819 | `const jString` `=` `Java.use(``"java.lang.String"``);` `let IJDGuardPlugin` `=` `Java.use(``"com.jingdong.common.guard.JDGuardHelper$1"``);``IJDGuardPlugin[``"genSign"``].implementation` `=` `function (uri, bArr,` `str``, str2, z) {` `let result` `=` `this[``"genSign"``](uri, bArr,` `str``, str2, z);` `let mapStr` `=` `JSONObject.$new(result).toString()` `console.log(``"======== IJDGuardPlugin.genSign is called =========="``)``console.log(`uri` `=` `${uri}`)``console.log(`bArr string` `=` `${jString.$new(bArr)}`)``console.log(```str`  `=` `${``str``}`)``console.log(`str2` `=` `${str2}`)``console.log(`z` `=` `${z}`)``console.log(`mapStr` `=` `${mapStr}\n\n`)` `return` `result;``};` |
|-|-|

| 1234567891011121314 | `uri` `=` `https:``/``/``api.m.jd.com``/``client.action?functionId``=``getLegoWareDetailComment&lmt``=``0``&clientVersion``=``11.6``.``4``&build``=``98704``&client``=``android&partner``=``tencent&oaid``=``1B4220DEA49487D7AF8DE6AF4C0F1F60F05819E2ADCC3CD2ACDF3C07D81BEDC6``&eid``=``eidAf5088122acsfbxEYf1ulTs2pUn38cGRLh28RGgYgyPwz80gu9s7yfbXAvbZ1R70WQm1PENZaDGd6EF``/``munBEHRDWPW5sYgYPelPhS``+``vYueanoeJv&sdkVersion``=``29``&lang``=``zh_CN&harmonyOs``=``0``&networkType``=``wifi&uemps``=``2``-``2``-``2``&ext``=``%``7B``%``22prstate``%``22``%``3A``%``220``%``22``%``2C``%``22pvcStu``%``22``%``3A``%``221``%``22``%``2C``%``22cfgExt``%``22``%``3A``%``22``%``7B``%``5C``%``22privacyOffline``%``5C``%``22``%``3A``%``5C``%``220``%``5C``%``22``%``7D``%``22``%``7D``&ef``=``1``&ep``=``%``7B``%``22hdid``%``22``%``3A``%``22JM9F1ywUPwflvMIpYPok0tt5k9kW4ArJEU3lfLhxBqw``%``3D``%``22``%``2C``%``22ts``%``22``%``3A1678345151525``%``2C``%``22ridx``%``22``%``3A``-``1``%``2C``%``22cipher``%``22``%``3A``%``7B``%``22area``%``22``%``3A``%``22CV83Cv8yDzu5XzK``%``3D``%``22``%``2C``%``22d_model``%``22``%``3A``%``22J05PUOnVU0O2CNKm``%``22``%``2C``%``22wifiBssid``%``22``%``3A``%``22dW5hbw93bq``%``3D``%``3D``%``22``%``2C``%``22osVersion``%``22``%``3A``%``22CJK``%``3D``%``22``%``2C``%``22d_brand``%``22``%``3A``%``22J25vUQn1cm``%``3D``%``3D``%``22``%``2C``%``22screen``%``22``%``3A``%``22CtO1EIenCNqm``%``22``%``2C``%``22uuid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``2C``%``22aid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``2C``%``22openudid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``7D``%``2C``%``22ciphertype``%``22``%``3A5``%``2C``%``22version``%``22``%``3A``%``221.2``.``0``%``22``%``2C``%``22appname``%``22``%``3A``%``22com``.jingdong.app.mall``%``22``%``7D``&st``=``1678346289851``&sign``=``4bcf4d55a72e4023eebcf2d80c0bac2c``&sv``=``111`  `bArr string` `=` `{``"category"``:``"12218;12221;13554"``,``"commentNum"``:``3``,``"isNew"``:``"0"``,``"newTitle"``:null,``"shadowMainSku"``:``"0"``,``"shieldCurrentComment"``:``"1"``,``"shopId"``:null,``"shopType"``:``"0"``,``"sku"``:``"10064651465940"``,``"venderId"``:``"12715063"``,``"wareType"``:``"0"``}`  `str`  `=` `application``/``x``-``www``-``form``-``urlencoded; charset``=``UTF``-``8`  `str2` `=` `Post` `z` `=` `true` `mapStr` `=` `{``"jdgs"``:``"{\"b1\":\"a4574221-958f-4752-ba5b-40e53bed1c17\",\"b2\":\"3.1.4-grey_0\",\"b3\":\"2.0\",\"b4\":\"eDIaHBTaPBKuc86zzA+aq9kltjVpsfYK9uL9uBZTn64tmAtrIPjdnnSaRU5oYnqGZrpwAfVY8PxsVG6T0BM07qPisYg5ffIXkrDYnM9W1bnZyY9uOnXSCSgwMt369HcipuC56Bh3OoP2\/8dGTfb1IJTRCj8s5o12Js+W4id6RKGen4q52iF74F+bl3fA5Zsl2Z3fg96JTVf7nAAIDvXiJBacMEMzWVBblzJMwjNENwZs2SvOB\/b6XSr5lrdlAtHgSytyL7ME5ftn+flvL2nJwH3CQ7AanNGaKFCaZPzjV0sU3+Q29NONh1SBjFDMGX\/PgA9QZmrQj14raPf7w7t\/QsdjjBPix+jbGr5KuPGOVaVBWSKhzh0s3Wkqhe5PqkjkYOUM3DAFGb7d1fNTXlZJUsI8Dsqin8a\/iXLb4RU=\",\"b5\":\"a49356adf69f2937aa764b661c2982d202ec6003\",\"b7\":\"1678346289856\",\"b6\":\"3e5485b2ee5c1e3a55e6ab35606728264d787a0f\"}"``}` |
|-|-|

使用 `firda` 重新加载 `js` 脚本后发现其返回值居然是请求头里面的 `jdgs`，并不是我们需要的 `sign`，并且里面的参数，也就是 `uri` 里面包含了我们需要的 `sign` 参数，所以 `sign` 应该是在获取 `jdgs` 之前就生成了！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_2UBUBFJRBRQSPHR.png)

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_PQ2D2DM4JNXFJB2.png)

 那么我们尝试定位上一级堆栈，也就是 `com.jingdong.jdsdk.network.toolbox.HttpSettingTool.doSignUsingJdGuard` ，源码如下：

| 12345678910111213141516171819202122232425262728 | `public static void doSignUsingJdGuard(HttpSetting httpSetting, String` `str``) {``URI uri;``if` `(TextUtils.isEmpty(httpSetting.getFunctionId()) \|\| JDHttpTookit.getEngine().getJdGuardPlugin()` `=``=` `null \|\| !JDHttpTookit.getEngine().getJdGuardPlugin().isEnable() \|\| !JDHttpTookit.getEngine().getJdGuardPlugin().isInWhiteList(httpSetting.getFunctionId())) {``return``;``}``String str2` `=` `httpSetting.isPost() ? UrlRequest.HTTP_METHOD_POST : UrlRequest.HTTP_METHOD_GET;``boolean isPost` `=` `httpSetting.isPost();``Map``<String, String>` `map` `=` `null;``String str3` `=` `isPost ? ParamEncodeUtil.DEFAULT_CONTENT_TYPE : null;``try` `{``uri` `=` `new URI(httpSetting.getUrl());``} catch (URISyntaxException unused) {``uri` `=` `null;``}``try` `{``map` `=` `JDHttpTookit.getEngine().getJdGuardPlugin().genSign(uri, !TextUtils.isEmpty(``str``) ?` `str``.getBytes() : null, str3, str2, isPost);``} catch (Throwable unused2) {``}``if` `(``map` `=``=` `null \|\|` `map``.isEmpty()) {``return``;``}``Map``<String, String> headerMap` `=` `httpSetting.getHeaderMap();``if` `(headerMap` `=``=` `null \|\| headerMap.isEmpty()) {``headerMap` `=` `new HashMap<>();``}``headerMap.putAll(``map``);``httpSetting.setHeaderMap(headerMap);``}` |
|-|-|

我们可以发现此时的 `uri` 里面就有的 `sign` ，因此我们继续定位上层 `com.jingdong.jdsdk.network.toolbox.ParamBuilderForJDMall.setupParams` ，源码如下：

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `public static void setupParams(HttpRequest httpRequest) {``String` `str``;``HttpSetting httpSetting` `=` `HttpSettingTool.setupBaseParams(httpRequest);``HttpSettingTool.addGuardVerifyLmtCode(httpSetting);``if` `(httpSetting.getCustomMapParam()` `=``=` `null \|\| !httpSetting.getCustomMapParam().containsKey(``"uuid"``)) {``str` `=` `"";``}` `else` `{``str` `=` `httpSetting.getCustomMapParam().get(``"uuid"``);``httpSetting.getCustomMapParam().remove(``"uuid"``);``}``if` `(TextUtils.isEmpty(``str``) && httpSetting.getCustomEncryptMapParam() !``=` `null && httpSetting.getCustomEncryptMapParam().containsKey(``"uuid"``)) {``str` `=` `httpSetting.getCustomEncryptMapParam().get(``"uuid"``);``httpSetting.getCustomEncryptMapParam().remove(``"uuid"``);``}``if` `(TextUtils.isEmpty(``str``)) {``str` `=` `JDHttpTookit.getEngine().getStatInfoConfigImpl().getDeviceUUID(httpSetting.getFunctionId(), httpSetting.isEnableEncryptTransmission());``}``if` `(TextUtils.isEmpty(``str``)) {``str` `=` `"unknow"``;``}``if` `(OKLog.D) {``String str2` `=` `TAG;``OKLog.d(str2,` `"id:"` `+` `httpSetting.getId()` `+` `"- uuid -->> "` `+` `str``);``}``String bodyParam` `=` `HttpSettingTool.getBodyParam(httpSetting);``if` `(httpSetting.getType()` `=``=` `6000``) {``if` `(RuntimeConfigHelper.advertiseStatDataEnable()) {``HttpSettingTool.addStatQueryParam(httpSetting, bodyParam,` `str``);``}``}` `else` `{``HttpSettingTool.addStatQueryParam(httpSetting, bodyParam,` `str``);``}``HttpSettingTool.addCustomQueryParam(httpSetting);``if` `(JDHttpTookit.getEngine().isNeedVerifySignature()) {``JDHttpTookit.getEngine().getSignatureHandlerImpl().networkSettingsPreSignature();``signature(httpSetting, bodyParam,` `str``);``}``HttpSettingTool.doSignUsingJdGuard(httpSetting, bodyParam);``JDHttpTookit.getEngine().getExternalDebugConfigImpl().addMockerIdName(httpSetting);``}` |
|-|-|

发现这个函数是设置 `httpSetting` 的 参数的，貌似就是我们需要的！我们看一下有没有关键的代码！发现了这么一行代码：`signature(httpSetting, bodyParam, str);` ，很可疑，我们先来尝试 `hook` 验证加密入口是否正确，先尝试 `hook` 一下 `com.jingdong.jdsdk.network.toolbox.ParamBuilderForJDMall.signature` 这个函数吧，因为这个函数是没有返回值的，所以我们尝试输出一下调用前与调用后的 `httpSetting` 的 `url` 不就知道他有没有给 `url` 加上 `sign` 了吗？代码如下：

| 1234567891011121314151617 | `Java.perform(()` `=``> {``let ParamBuilderForJDMall` `=` `Java.use(``"com.jingdong.jdsdk.network.toolbox.ParamBuilderForJDMall"``);``ParamBuilderForJDMall[``"signature"``].implementation` `=` `function (httpSetting,` `str``, str2) {``console.log(``"========= ParamBuilderForJDMall.signature ========="``)``console.log(`before httpSetting``=``${httpSetting}`)``console.log(`before httpSetting uri``=``${httpSetting.getUrl()}`)``console.log(```str``=``${``str``}`)``console.log(`str2``=``${str2}`)` `this[``"signature"``](httpSetting,` `str``, str2);` `console.log(`after httpSetting``=``${httpSetting}`)``console.log(`after httpSetting uri``=``${httpSetting.getUrl()`)``};`  `})` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_8CSCG47CN65D4BX.png)

 果然发现这就是关键入口，因为之前的 `uri` 里面是没有 `sign` 这个参数的，但是后面却有了，因此我们就追进去看看，发现了这么一行代码：`String signature = JDHttpTookit.getEngine().getSignatureHandlerImpl().signature(JDHttpTookit.getEngine().getApplicationContext(), functionId, str, str2, property, versionName);` ，继续跟进到 `signature` 里面去发现他只是一个接口，所以肯定有实现或者重载的地方！（这种情况，我们一般 `hook` 不到，因为位置不正确，实际调用的是其实现类的那个函数，不信你可以试试！）

 那么我们应该如何找这个接口的实现呢？这边提供一个思路，因为实现的话肯定要使用同样的函数名，返回值以及参数，所以可以尝试直接搜索，例如当前函数定义为 `String signature(Context context, String str, String str2, String str3, String str4, String str5);`，那么我们就直接将这个作为关键字进行搜索（当然你也可以尝试查找用例，不过应该找不到）

 通过搜索我们找到了如下结果：

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_TETTE95GEG5R2W2.png)

 一个个去找就能发现真正的加密入口了：

| 1234 | `@Override` `/``/` `com.jingdong.jdsdk.network.dependency.ISignatureHandler``public String signature(Context context, String` `str``, String str2, String str3, String str4, String str5) {``return` `BitmapkitUtils.getSignFromJni(context,` `str``, str2, str3, str4, str5);``}` |
|-|-|

再继续跟进去就能发现这个是一个 `native` 函数 （其实从名字就能看出来），所以 `sign` 的 `jni` 入口为：`com.jingdong.common.utils.BitmapkitUtils.getSignFromJni`

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_YP82HS55FY7FMK8.png)

 我们回到 `jdgs` 加密入口处，继续跟进代码就能发现其实际也是一个 `native` 函数，简单讲一下步骤

| 123456 | `1.` `首先定位的入口为：com.jingdong.common.guard.JDGuardHelper$``1.genSign``2.` `进入 c.b，关键代码为 eVar.i();``3.` `进入 eVar.i，发现 jdgs 就是 而 o 是 o(h())``4.` `进入 o 函数，发现了 com.jd.security.jdguard.b.d().A(bArr);``5.` `进入 com.jd.security.jdguard.b.d().A 发现了 Bridge.main(``101``, new` `Object``[]{bArr, u(), s(), w(), q()});``6.` `进入 main 发现 public static native` `Object``[] main(``int` `i2,` `Object``[] objArr); 也就是入口了` |
|-|-|

# 接口分析

## sign

入口为：`com.jingdong.common.utils.BitmapkitUtils.getSignFromJni`

 使用通用的办法找到 `so` 文件和函数签名：`so` 文件 `libjdbitmapkit.so`, 函数签名：`getSignFromJni(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;` ， `hook` 一下分析一下参数吧！

| 12345678910111213141516171819202122 | `Java.perform(()` `=``> {` `let BitmapkitUtils` `=` `Java.use(``"com.jingdong.common.utils.BitmapkitUtils"``);``BitmapkitUtils[``"getSignFromJni"``].implementation` `=` `function (context,` `str``, str2, str3, str4, str5) {` `console.log(``"========= getSignFromJni ========="``)``console.log(` context``=``${context}`)``console.log(`` `str``=``${``str``}`)``console.log(` str2``=``${str2}`)``console.log(` str3``=``${str3}`)``console.log(` str4``=``${str4}`)``console.log(` str5``=``${str5}`)` `let result` `=` `this[``"getSignFromJni"``](context,` `str``, str2, str3, str4, str5);` `console.log(` result``=``${result}`)``return` `result;``};`   `})` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_HF67EFBMBV69247.png)

- `context`：就是 `android.context.Context`
- `str`：也就是 `functionId`
- `str2`：是 `body` 字符串
- `str3`：一直是 `f9f40175bf4c6710`， 猜测可能是设备码或者 `secretKey` 之类的东西吧（搜索抓包发现其为一个 `uuid`， 那就是设备码之类的 ）
- `str4`：设备类型，我的是 `android`
- `str5`：看起来是版本号
- `result`：就是加密好的 `sign` 和时间戳以及一个 `sv`， 所以猜测加密用上了这些

## jdgs

入口为：`com.jd.security.jdguard.core.Bridge.main`

 使用通用的办法找到 `so` 文件和函数签名：`so` 文件 `libjdg.so`, 函数签名：`main(I[Ljava/lang/Object;)[Ljava/lang/Object;` ， `hook` 一下分析一下参数吧！

| 12345678910111213141516 | `Java.perform(()` `=``> {` `let Bridge` `=` `Java.use(``"com.jd.security.jdguard.core.Bridge"``);``Bridge[``"main"``].implementation` `=` `function (i2, objArr) {``console.log(``"======== Bridge.main ========"``)``console.log(`i2``=``${i2}`)``console.log(`objArr``=``${objArr}`)` `let result` `=` `this[``"main"``](i2, objArr);` `console.log(`result``=``${result}`)` `return` `result;``};` `})` |
|-|-|

- `i2`：`101`， 固定的数字
- `objArr`
	- `objArr[0]`：`uri` 转为 `byte` 数组
	- `objArr[1]`：一串和设备相关的字符串
	- `objArr[2]`：`eid` 还是什么东西
	- `objArr[3]`：1.0
	- `objArr[4]`：83
- `result`：请求头里面的 `jdgs`

这个参数暂时先不分析了，我们本文主要分析 `sign` ，如果有需要后续再补充分布步骤，先记录一下参数示例

| 123456789101112131415 | `i2:` `101` `objArr[``0``]: POST` `/``client.action bef``=``1``&bfa06501b64b4672e3b8645fd0ad54401e4786bd9efebc784fa483cf99bec2fd``=``&build``=``98704``&client``=``android&clientVersion``=``11.6``.``4``&ef``=``1``&eid``=``eidAf5088122acsfbxEYf1ulTs2pUn38cGRLh28RGgYgyPwz80gu9s7yfbXAvbZ1R70WQm1PENZaDGd6EF``%``2FmunBEHRDWPW5sYgYPelPhS``+``vYueanoeJv&ep``=``%``7B``%``22hdid``%``22``%``3A``%``22JM9F1ywUPwflvMIpYPok0tt5k9kW4ArJEU3lfLhxBqw``%``3D``%``22``%``2C``%``22ts``%``22``%``3A1678345151525``%``2C``%``22ridx``%``22``%``3A``-``1``%``2C``%``22cipher``%``22``%``3A``%``7B``%``22area``%``22``%``3A``%``22CV83Cv8yDzu5XzK``%``3D``%``22``%``2C``%``22d_model``%``22``%``3A``%``22J05PUOnVU0O2CNKm``%``22``%``2C``%``22wifiBssid``%``22``%``3A``%``22dW5hbw93bq``%``3D``%``3D``%``22``%``2C``%``22osVersion``%``22``%``3A``%``22CJK``%``3D``%``22``%``2C``%``22d_brand``%``22``%``3A``%``22J25vUQn1cm``%``3D``%``3D``%``22``%``2C``%``22screen``%``22``%``3A``%``22CtO1EIenCNqm``%``22``%``2C``%``22uuid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``2C``%``22aid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``2C``%``22openudid``%``22``%``3A``%``22ZtvwDNKnDzVsZtHtDtcnCK``%``3D``%``3D``%``22``%``7D``%``2C``%``22ciphertype``%``22``%``3A5``%``2C``%``22version``%``22``%``3A``%``221.2``.``0``%``22``%``2C``%``22appname``%``22``%``3A``%``22com``.jingdong.app.mall``%``22``%``7D``&ext``=``%``7B``%``22prstate``%``22``%``3A``%``220``%``22``%``2C``%``22pvcStu``%``22``%``3A``%``221``%``22``%``2C``%``22cfgExt``%``22``%``3A``%``22``%``7B``%``5C``%``22privacyOffline``%``5C``%``22``%``3A``%``5C``%``220``%``5C``%``22``%``7D``%``22``%``7D``&functionId``=``wareBusiness&harmonyOs``=``0``&lang``=``zh_CN&lmt``=``0``&networkType``=``wifi&oaid``=``1B4220DEA49487D7AF8DE6AF4C0F1F60F05819E2ADCC3CD2ACDF3C07D81BEDC6``&partner``=``tencent&scval``=``10062561918391``&sdkVersion``=``29``&sign``=``68049b09fa2cb6111f9ab0209ea9412e``&st``=``1678348533650``&sv``=``100``&uemps``=``2``-``2``-``2` `转为 byte 数组` `objArr[``1``]: sdm845\|``-``\|OnePlus6\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``§§``0``\|``1``§§``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``§§``-``\|``115717931008``§§``-``\|``-``\|``1.0``\|``-``§§``0``\|``1``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-``§§OnePlus``/``OnePlus6``/``OnePlus6:``10``/``QKQ1.``190716.003``/``2107162030``:user``/``release``-``keys``/``\|``-``\|``-``\|``1678344292938``\|``-``§§``-``\|``-``\|``-``\|``-``\|``-``\|``-``\|``-`  `objArr[``2``]: eidAf5088122acsfbxEYf1ulTs2pUn38cGRLh28RGgYgyPwz80gu9s7yfbXAvbZ1R70WQm1PENZaDGd6EF``/``munBEHRDWPW5sYgYPelPhS``+``vYueanoeJv` `objArr[``3``]:` `1.0` `objArr[``4``]:` `83`  `返回值：{``"b1"``:``"a4574221-958f-4752-ba5b-40e53bed1c17"``,``"b2"``:``"3.1.4-grey_0"``,``"b3"``:``"2.0"``,``"b4"``:``"poW6/4yQ4JTEcYoerj5XATijmNYCBHcNjt++g5Q4O+l6+FjqoOp+0969nSqdVuQ6OYidCZIgcjC5HDYYgMu7jfPc+9qv092hwdGQxZK4GlClVizD6jznVAOvOvMYNkLQ3FjogO+BAMTJQvk8EPD7vWXJm8uvve8RVv1HkFs5RZ3zXSBNp3M2OyVX1hIZ9/CRBsu49MSJLIjUmz1fWvi47BZ+IlWC78KJMHb33i9I9YwzGtGnZCtIA3Sj+SzBiIIAS7B9dNfqYkjHf3FzDMcx3F0QznG+VyIw/qw727A7tulxd+5kky8tIG73Yb59KDmoEXrMlzDFEh9YGutpUKhBz3bTFp/uMp9MM1I5oKMoURMMAf7BK4ZWocY/wEWwq6Chh+rrlbZYpwJ/zCg3nxk/xmdIgvJ85+Ses0BYy+49"``,``"b5"``:``"231497376118012d822698e78658dc91d6fa9a63"``,``"b7"``:``"1678348533659"``,``"b6"``:``"eeb029f8f6aadee6c235acd9eaf8447e6825f478"``}` |
|-|-|

# Unidbg

这边提供一个通用的模板，可以自己填充

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `package 这个写当前包名;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.AbstractJni;``import` `com.github.unidbg.linux.android.dvm.DalvikModule;``import` `com.github.unidbg.linux.android.dvm.DvmClass;``import` `com.github.unidbg.linux.android.dvm.VM;``import` `com.github.unidbg.memory.Memory;` `import` `java.io.``File``;` `public` `class` `className extends AbstractJni {``private final AndroidEmulator emulator;``private final VM vm;` `/``/` `包名``private final String packageName` `=` `"包名"``;``/``/` `apk 地址``private final String packagePath` `=` `"apk 地址"``;``/``/` `so 名称, 要去掉 lib 和  .so``private final String libraryName` `=` `"so 名称, 要去掉 lib 和  .so"``;``/``/` `jni 类名``private final String jniClassName` `=` `"jni 类名"``;``/``/` `调试信息``private final Boolean verbose` `=` `true;``/``/` `jni 模块``private final DvmClass Module;`  `public className() {` `/``/` `实例化一个模拟器` `emulator` `=` `AndroidEmulatorBuilder``.for32Bit()``.addBackendFactory(new Unicorn2Factory(true))``.setProcessName(packageName)``.build();`  `Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));``vm` `=` `emulator.createDalvikVM(new` `File``(packagePath));``vm.setJni(this);``vm.setVerbose(verbose);``DalvikModule dm` `=` `vm.loadLibrary(libraryName, true);``Module` `=` `vm.resolveClass(jniClassName);``dm.callJNI_OnLoad(emulator);``}` `public static void main(String[] args) {``className ins` `=` `new className();``}`  `}` |
|-|-|

## sign

先套用一下模板，然后运行看看

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `package com.jingdong.app.mall;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.AbstractJni;``import` `com.github.unidbg.linux.android.dvm.DalvikModule;``import` `com.github.unidbg.linux.android.dvm.DvmClass;``import` `com.github.unidbg.linux.android.dvm.VM;``import` `com.github.unidbg.memory.Memory;` `import` `java.io.``File``;` `public` `class` `signUtils extends AbstractJni {``private final AndroidEmulator emulator;``private final VM vm;` `/``/` `包名``private final String packageName` `=` `"com.com.jingdong.app.mall"``;``/``/` `apk 地址``private final String packagePath` `=` `"unidbg-android/src/test/resources/jd.apk"``;``/``/` `so 名称, 要去掉 lib 和  .so``private final String libraryName` `=` `"jdbitmapkit"``;``/``/` `jni 类名``private final String jniClassName` `=` `"com.jingdong.common.utils.BitmapkitUtils"``;``/``/` `调试信息``private final Boolean verbose` `=` `true;``/``/` `jni 模块``private final DvmClass Module;`  `public signUtils() {` `/``/` `实例化一个模拟器` `emulator` `=` `AndroidEmulatorBuilder``.for32Bit()``.addBackendFactory(new Unicorn2Factory(true))``.setProcessName(packageName)``.build();`  `Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));``vm` `=` `emulator.createDalvikVM(new` `File``(packagePath));``vm.setJni(this);``vm.setVerbose(verbose);``DalvikModule dm` `=` `vm.loadLibrary(libraryName, true);``Module` `=` `vm.resolveClass(jniClassName);``dm.callJNI_OnLoad(emulator);``}` `public static void main(String[] args) {``signUtils ins` `=` `new signUtils();``}`  `}` |
|-|-|

- `com/jingdong/common/utils/BitmapkitUtils->a:Landroid/app/Application;`

| 12 | `java.lang.UnsupportedOperationException: com``/``jingdong``/``common``/``utils``/``BitmapkitUtils``-``>a:Landroid``/``app``/``Application;``at com.github.unidbg.linux.android.dvm.AbstractJni.getStaticObjectField(AbstractJni.java:``103``)` |
|-|-|

发现报错了，是因为缺少环境问题，可以看到最底层的报错堆栈在 `com.github.unidbg.linux.android.dvm.AbstractJni.getStaticObjectField`，大概意思就是要找`com/jingdong/common/utils/BitmapkitUtils`这个类的 `a` 字段，但是找不到，所以报了上述的错误，那么我们就需要重写 `getStaticObjectField` 这个方法，将环境补充完毕，步骤如下：

 首先我们先点进源码里面看看作者自己的实现

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `@Override``public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature) {``case` `"android/content/Context->TELEPHONY_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.TELEPHONY_SERVICE);``case` `"android/content/Context->WIFI_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.WIFI_SERVICE);``case` `"android/content/Context->CONNECTIVITY_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.CONNECTIVITY_SERVICE);``case` `"android/content/Context->ACCESSIBILITY_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.ACCESSIBILITY_SERVICE);``case` `"android/content/Context->KEYGUARD_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.KEYGUARD_SERVICE);``case` `"android/content/Context->ACTIVITY_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.ACTIVITY_SERVICE);``case` `"android/content/Context->LOCATION_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.LOCATION_SERVICE);``case` `"android/content/Context->WINDOW_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.WINDOW_SERVICE);``case` `"android/content/Context->SENSOR_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.SENSOR_SERVICE);``case` `"android/content/Context->UI_MODE_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.UI_MODE_SERVICE);``case` `"android/content/Context->DISPLAY_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.DISPLAY_SERVICE);``case` `"android/content/Context->AUDIO_SERVICE:Ljava/lang/String;"``:``return` `new StringObject(vm, SystemService.AUDIO_SERVICE);``case` `"java/lang/Void->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Void"``);``case` `"java/lang/Boolean->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Boolean"``);``case` `"java/lang/Byte->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Byte"``);``case` `"java/lang/Character->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Character"``);``case` `"java/lang/Short->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Short"``);``case` `"java/lang/Integer->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Integer"``);``case` `"java/lang/Long->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Long"``);``case` `"java/lang/Float->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Float"``);``case` `"java/lang/Double->TYPE:Ljava/lang/Class;"``:``return` `vm.resolveClass(``"java/lang/Double"``);``}` `throw new UnsupportedOperationException(signature);``}` |
|-|-|

重写这个方法，补充实现，我们查看 `jadx` 发现 `a` 这个字段是一个 `android.app.Application` （你也可以通过签名看出来），所以我们需要在 `unidbg` 里面构造出来。

 在 `unidbg` 里面，`resolveClass`是一个可变参数方法，它的第二个参数是可变参数，用于进一步描述我们所构造的这个`DvmClass`的父类和接口。

 拿目前需要补充的 `android.app.Application` 为例，通过搜索资料可知，`Application` 继承与 `ContextWrapper`， 而 `ContextWrapper` 又继承与 `Context`，所以在 `unidbg` 里面需要实现一个 `Application`，那么可以使用以下嵌套代码：

| 123 | `DvmClass Context` `=` `vm.resolveClass(``"android/content/Context"``);``DvmClass ContextWrapper` `=` `vm.resolveClass(``"android/content/ContextWrapper"``, Context);``DvmClass Application` `=` `vm.resolveClass(``"android/app/Application"``, ContextWrapper);` |
|-|-|

补环境代码如下：

| 1234567891011121314151617 | `@Override``public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature) {``case` `"com/jingdong/common/utils/BitmapkitUtils->a:Landroid/app/Application;"``: {``DvmClass Context` `=` `vm.resolveClass(``"android/content/Context"``);``DvmClass ContextWrapper` `=` `vm.resolveClass(``"android/content/ContextWrapper"``, Context);``/``/` `使用 android``/``app``/``Application 发现会报错: com.github.unidbg.arm.backend.BackendException``/``/` `百度了一下发现这个错误是找不到 methodID``/``/` `因此可以使用 android``/``app``/``Activity 代替, 因为它也可以获取 Application 对象``DvmClass Application` `=` `vm.resolveClass(``"android/app/Activity"``, ContextWrapper);` `return` `Application.newObject(signature);``}``}` `return` `super``.getStaticObjectField(vm, dvmClass, signature);``}` |
|-|-|

- `android/content/pm/ApplicationInfo->sourceDir:Ljava/lang/String;`

| 12 | `java.lang.UnsupportedOperationException: android``/``content``/``pm``/``ApplicationInfo``-``>sourceDir:Ljava``/``lang``/``String;``at com.github.unidbg.linux.android.dvm.AbstractJni.getObjectField(AbstractJni.java:``171``)` |
|-|-|

取 `ApplicationInfo` 也就是 `apk` 的存放位置 可以使用 `adb` 进手机查看一下

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_X2G724KA3R2EC96.png)

 所以 `app` 在这里： `/data/app/com.jingdong.app.mall-Icn20e0xHLzrVHPBwOirRA==/bask.apk`

| 123456789 | `@Override``public DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch (signature) {``case` `"android/content/pm/ApplicationInfo->sourceDir:Ljava/lang/String;"``: {``return` `new StringObject(vm,` `"/data/app/com.jingdong.app.mall-Icn20e0xHLzrVHPBwOirRA==/bask.apk"``);``}``}``return` `super``.getObjectField(vm, dvmObject, signature);``}` |
|-|-|

- `com/jingdong/common/utils/BitmapkitZip->unZip(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)[B`

| 12 | `java.lang.UnsupportedOperationException: com``/``jingdong``/``common``/``utils``/``BitmapkitZip``-``>unZip(Ljava``/``lang``/``String;Ljava``/``lang``/``String;Ljava``/``lang``/``String;)[B``at com.github.unidbg.linux.android.dvm.AbstractJni.callStaticObjectMethod(AbstractJni.java:``432``)` |
|-|-|

这个补的时候有一个参数，可以先输出一下参数，看看都是什么

| 123 | `arg0``-``-`  `/``data``/``app``/``com.jingdong.app.mall``-``Icn20e0xHLzrVHPBwOirRA``=``=``/``bask.apk``arg1``-``-`  `META``-``INF``/``arg2``-``-`  `.RSA` |
|-|-|

所以他找的好像是 `apk` 里面 `META-INF` 文件夹里面的 `xxx.RSA` ， 我们只要使用压缩文件打开 `apk` 就可以看到一个叫做 `JINGDONG.RSA` 的文件，补全一下即可！

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_Z795XH96JASBJ9R.png)

| 1234567891011121314151617181920212223242526 | `@Override``public DvmObject<?> callStaticObjectMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {` `switch (signature) {``case` `"com/jingdong/common/utils/BitmapkitZip->unZip(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)[B"``: {``StringObject apkPath` `=` `varArg.getObjectArg(``0``);``StringObject directory` `=` `varArg.getObjectArg(``1``);``StringObject filename` `=` `varArg.getObjectArg(``2``);` `if` `(``"/data/app/com.jingdong.app.mall-Icn20e0xHLzrVHPBwOirRA==/bask.apk"``.equals(apkPath.getValue())``&&` `"META-INF/"``.equals(directory.getValue())``&&` `".RSA"``.equals(filename.getValue())``) {``byte[] data` `=` `vm.unzip(``"META-INF/JINGDONG.RSA"``);``return` `new ByteArray(vm, data);``}`  `}` `}`  `return` `super``.callStaticObjectMethod(vm, dvmClass, signature, varArg);``}` |
|-|-|

- `sun/security/pkcs/PKCS7-><init>([B)V`

| 12 | `java.lang.UnsupportedOperationException: sun``/``security``/``pkcs``/``PKCS7``-``><init>([B)V``at com.github.unidbg.linux.android.dvm.AbstractJni.newObject(AbstractJni.java:``741``)` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_SZ28SZQH74Z8JUK.png)

 写完之后提示要捕捉异常，因此就捕捉一下，虽然我也不懂为什么

| 1234567891011121314151617181920212223 | `@Override``public DvmObject<?> newObject(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {``switch (signature) {``case` `"sun/security/pkcs/PKCS7-><init>([B)V"``: {``PKCS7 pkcs7` `=` `null;` `try` `{``byte[] bArray` `=` `(byte[]) varArg.getObjectArg(``0``).getValue();``pkcs7` `=` `new PKCS7(bArray);` `} catch (ParsingException e) {``e.printStackTrace();` `}``DvmClass pkcs7Class` `=` `vm.resolveClass(``"sun/security/pkcs/PKCS7"``);``return` `pkcs7Class.newObject(pkcs7);` `}``}` `return` `super``.newObject(vm, dvmClass, signature, varArg);` `}` |
|-|-|

- `sun/security/pkcs/PKCS7->getCertificates()[Ljava/security/cert/X509Certificate;`

| 12 | `java.lang.UnsupportedOperationException: sun``/``security``/``pkcs``/``PKCS7``-``>getCertificates()[Ljava``/``security``/``cert``/``X509Certificate;``at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethod(AbstractJni.java:``921``)` |
|-|-|

| 123456789101112 | `@Override``public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {``switch (signature) {``case` `"sun/security/pkcs/PKCS7->getCertificates()[Ljava/security/cert/X509Certificate;"``: {``PKCS7 pkcs7` `=` `(PKCS7) dvmObject.getValue();``X509Certificate[] x509Certificates` `=` `pkcs7.getCertificates();``return` `ProxyDvmObject.createObject(vm, x509Certificates);` `}``}``return` `super``.callObjectMethod(vm, dvmObject, signature, varArg);``}` |
|-|-|

- `com/jingdong/common/utils/BitmapkitZip->objectToBytes(Ljava/lang/Object;)[B`

| 12 | `java.lang.UnsupportedOperationException: com``/``jingdong``/``common``/``utils``/``BitmapkitZip``-``>objectToBytes(Ljava``/``lang``/``Object``;)[B``at com.github.unidbg.linux.android.dvm.AbstractJni.callStaticObjectMethod(AbstractJni.java:``432``)` |
|-|-|

发现他找的是一个 `objectToBytes` 方法，但是找不到，所以我们直接去 `jadx` 里面搜索一下，便得到了结果

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_XTRUMX2XUCF25RY.png)

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_W7E6G7X4TDUSG94.png)

 可以直接复制出来使用，去除报错，导入一些包就可以了！

| 1234567891011121314 | `public static byte[] objectToBytes(``Object` `obj) {``try` `{``ByteArrayOutputStream byteArrayOutputStream` `=` `new ByteArrayOutputStream();``ObjectOutputStream objectOutputStream` `=` `new ObjectOutputStream(byteArrayOutputStream);``objectOutputStream.writeObject(obj);``objectOutputStream.flush();``byte[] byteArray` `=` `byteArrayOutputStream.toByteArray();``objectOutputStream.close();``byteArrayOutputStream.close();``return` `byteArray;``} catch (IOException e2) {``return` `null;``}``}` |
|-|-|

然后再继续补环境

| 123 | `case` `"com/jingdong/common/utils/BitmapkitZip->objectToBytes(Ljava/lang/Object;)[B"``: {``return` `new ByteArray(vm, objectToBytes(varArg.getObjectArg(``0``).getValue()));``}` |
|-|-|

接着运行发现居然不报错了，因此我们就写一个获取 `sign` 的函数尝试调用一下！

| 1234567891011121314151617 | `public void getSign() {``DvmObject<?> context` `=` `vm.resolveClass(``"android/content/Context"``).newObject(null);``String arg1` `=` `"getLegoWareDetailComment"``;``String arg2` `=` `"{\"category\":\"12473;12480;12515\",\"commentNum\":3,\"isNew\":\"0\",\"newTitle\":null,\"shadowMainSku\":\"0\",\"shieldCurrentComment\":\"1\",\"shopId\":null,\"shopType\":\"0\",\"sku\":\"11653586880\",\"venderId\":\"644185\",\"wareType\":\"0\"}"``;``String arg3` `=` `"f9f40175bf4c6710"``;``String arg4` `=` `"android"``;``String arg5` `=` `"11.6.4"``;`  `DvmObject<?> ret` `=` `module.callStaticJniMethodObject(emulator,` `"getSignFromJni(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"``, vm.addLocalObject(context), arg1, arg2, arg3, arg4, arg5` `);``System.out.println(``"================================================"``);``System.out.println(ret.getValue());``System.out.println(``"================================================"``);` `}` |
|-|-|

 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_5MWPTAJQ6FV44R6.png)

 好的，又开始报错了，咱继续补环境

- `java/lang/StringBuffer-><init>()V`

| 12 | `java.lang.UnsupportedOperationException: java``/``lang``/``StringBuffer``-``><init>()V``at com.github.unidbg.linux.android.dvm.AbstractJni.newObjectV(AbstractJni.java:``791``)` |
|-|-|

| 123456789101112 | `@Override``public DvmObject<?> newObjectV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch (signature) {``case` `"java/lang/StringBuffer-><init>()V"``: {``StringBuffer stringBuffer` `=` `new StringBuffer();``return` `vm.resolveClass(``"java/lang/StringBuffer"``).newObject(stringBuffer);` `}``}``return` `super``.newObjectV(vm, dvmClass, signature, vaList);` `}` |
|-|-|

- `java/lang/StringBuffer->append(Ljava/lang/String;)Ljava/lang/StringBuffer;`

| 12 | `java.lang.UnsupportedOperationException: java``/``lang``/``StringBuffer``-``>append(Ljava``/``lang``/``String;)Ljava``/``lang``/``StringBuffer;``at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethodV(AbstractJni.java:``416``)` |
|-|-|

| 12345678910111213 | `@Override``public DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch (signature) {``case` `"java/lang/StringBuffer->append(Ljava/lang/String;)Ljava/lang/StringBuffer;"``: {``StringBuffer stringBuffer` `=` `(java.lang.StringBuffer) dvmObject.getValue();``stringBuffer.append(vaList.getObjectArg(``0``).getValue());``DvmClass StringBuffer` `=` `vm.resolveClass(``"java/lang/StringBuffer"``);``return` `StringBuffer.newObject(stringBuffer);` `}``}``return` `super``.callObjectMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

- `java/lang/Integer->toString()Ljava/lang/String;`

| 12 | `java.lang.UnsupportedOperationException: java``/``lang``/``Integer``-``>toString()Ljava``/``lang``/``String;``at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethodV(AbstractJni.java:``416``)` |
|-|-|

| 123456 | `case` `"java/lang/Integer->toString()Ljava/lang/String;"``: {``Integer value` `=` `(Integer) dvmObject.getValue();` `return` `vm.resolveClass(``"java/lang/String"``).newObject(value.toString());` `}` |
|-|-|

- `java/lang/StringBuffer->toString()Ljava/lang/String;`

| 12 | `java.lang.UnsupportedOperationException: java``/``lang``/``StringBuffer``-``>toString()Ljava``/``lang``/``String;``at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethodV(AbstractJni.java:``416``)` |
|-|-|

| 12345 | `case` `"java/lang/StringBuffer->toString()Ljava/lang/String;"``: {``StringBuffer value` `=` `(StringBuffer) dvmObject.getValue();``return` `vm.resolveClass(``"java/lang/String"``).newObject(value.toString());` `}` |
|-|-|

最后发现环境补完了，可以直接得到 `sign` 了！

  ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_7VKVUXTJQBNXUWF.png)

## jdgs

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465666768697071727374 | `package com.jingdong.app.mall;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.arm.backend.Unicorn2Factory;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.``*``;``import` `com.github.unidbg.linux.android.dvm.jni.ProxyDvmObject;``import` `com.github.unidbg.memory.Memory;` `import` `java.io.``File``;` `public` `class` `jdgs extends AbstractJni {``private final AndroidEmulator emulator;``private final VM vm;` `/``/` `包名``private final String packageName` `=` `"com.com.jingdong.app.mall"``;``/``/` `apk 地址``private final String packagePath` `=` `"unidbg-android/src/test/resources/jd.apk"``;``/``/` `so 名称, 要去掉 lib 和  .so``private final String libraryName` `=` `"jdg"``;``/``/` `jni 类名``private final String jniClassName` `=` `"com.jd.security.jdguard.core.Bridge"``;``/``/` `调试信息``private final Boolean verbose` `=` `true;``/``/` `jni 模块``private final DvmClass module;` `public jdgs() {``/``/` `实例化一个模拟器` `emulator` `=` `AndroidEmulatorBuilder``.for32Bit()``.addBackendFactory(new Unicorn2Factory(true))``.setProcessName(packageName)``.build();`  `Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));``vm` `=` `emulator.createDalvikVM(new` `File``(packagePath));``vm.setJni(this);``vm.setVerbose(verbose);``DalvikModule dm` `=` `vm.loadLibrary(libraryName, true);``module` `=` `vm.resolveClass(jniClassName);``dm.callJNI_OnLoad(emulator);``}` `public static void main(String[] args) {``jdgs ins` `=` `new jdgs();``ins.getJdgs();``}` `public void getJdgs() {``Integer i2` `=` `101``;``String arr1` `=` `"/client.action bef=1&bfa06501b64b4672e3b8645fd0ad54401e4786bd9efebc784fa483cf99bec2fd=&build=98704&client=android&clientVersion=11.6.4&ef=1&eid=eidAf5088122acsfbxEYf1ulTs2pUn38cGRLh28RGgYgyPwz80gu9s7yfbXAvbZ1R70WQm1PENZaDGd6EF%2FmunBEHRDWPW5sYgYPelPhS+vYueanoeJv&ep=%7B%22hdid%22%3A%22JM9F1ywUPwflvMIpYPok0tt5k9kW4ArJEU3lfLhxBqw%3D%22%2C%22ts%22%3A1678345151525%2C%22ridx%22%3A-1%2C%22cipher%22%3A%7B%22area%22%3A%22CV83Cv8yDzu5XzK%3D%22%2C%22d_model%22%3A%22J05PUOnVU0O2CNKm%22%2C%22wifiBssid%22%3A%22dW5hbw93bq%3D%3D%22%2C%22osVersion%22%3A%22CJK%3D%22%2C%22d_brand%22%3A%22J25vUQn1cm%3D%3D%22%2C%22screen%22%3A%22CtO1EIenCNqm%22%2C%22uuid%22%3A%22ZtvwDNKnDzVsZtHtDtcnCK%3D%3D%22%2C%22aid%22%3A%22ZtvwDNKnDzVsZtHtDtcnCK%3D%3D%22%2C%22openudid%22%3A%22ZtvwDNKnDzVsZtHtDtcnCK%3D%3D%22%7D%2C%22ciphertype%22%3A5%2C%22version%22%3A%221.2.0%22%2C%22appname%22%3A%22com.jingdong.app.mall%22%7D&ext=%7B%22prstate%22%3A%220%22%2C%22pvcStu%22%3A%221%22%2C%22cfgExt%22%3A%22%7B%5C%22privacyOffline%5C%22%3A%5C%220%5C%22%7D%22%7D&functionId=wareBusiness&harmonyOs=0&lang=zh_CN&lmt=0&networkType=wifi&oaid=1B4220DEA49487D7AF8DE6AF4C0F1F60F05819E2ADCC3CD2ACDF3C07D81BEDC6&partner=tencent&scval=10062561918391&sdkVersion=29&sign=68049b09fa2cb6111f9ab0209ea9412e&st=1678348533650&sv=100&uemps=2-2-2"``;``String arr2` `=` `"sdm845\|-\|OnePlus6\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-§§0\|1§§-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-\|-§§-\|115717931008§§-\|-\|1.0\|-§§0\|1\|-\|-\|-\|-\|-\|-\|-\|-\|-§§OnePlus/OnePlus6/OnePlus6:10/QKQ1.190716.003/2107162030:user/release-keys/\|-\|-\|1678344292938\|-§§-\|-\|-\|-\|-\|-\|-"``;``String arr3` `=` `"eidAf5088122acsfbxEYf1ulTs2pUn38cGRLh28RGgYgyPwz80gu9s7yfbXAvbZ1R70WQm1PENZaDGd6EF/munBEHRDWPW5sYgYPelPhS+vYueanoeJv"``;``String arr4` `=` `"1.0"``;``String arr5` `=` `"83"``;` `Object``[] arr` `=` `new` `Object``[]{arr1.getBytes(), arr2, arr3, arr4, arr5};` `DvmObject<?> ret` `=` `module.callStaticJniMethodObject(emulator,` `"main(I[Ljava/lang/Object;)[Ljava/lang/Object;"``, i2, ProxyDvmObject.createObject(vm, arr));``System.out.println(``"================================================"``);`  `System.out.println(ret.getValue());``System.out.println(``"================================================"``);` `}` `}` |
|-|-|

模拟 `jdgs` 的时候不知道为什么会报这样一个错误，并且也没有堆栈，因为还是小白，暂时不知道如何解决
目前会导致获取到的结果拿不到，以后有思路了再来完善这一块！希望有大佬能指导一下，万分感谢！！
 ![图片描述](https://bbs.kanxue.com/upload/attach/202303/899374_DR263T8A2DTTZWJ.png)

---

# 回复

## 回复 by 黑屏 (#2)

*2023-3-13 13:40*

初始化函数的问题

## 回复 by 白龙lilac (#4)

*2023-3-14 15:28*

看起来是没有在 Unidbg 里执行它所需的初始化函数或初始化过程

## 回复 by System's (#5)

*2023-3-14 19:59*

这个可以琢磨琢磨，

## 回复 by mb_skfgafxa (#7)

*2023-4-17 10:55*

楼主，请教一下，libjdg里面main函数在哪边哈？我用IDA在libjdg里没有找到main函数，这个函数有做加密吗。。。您用的app是哪个版本

## 回复 by 我是新手qaq (#8)

*2023-4-20 12:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_skfgafxa](https://bbs.kanxue.com/user-937968.htm)
>
>  楼主，请教一下，libjdg里面main函数在哪边哈？我用IDA在libjdg里没有找到main函数，这个函数有做加密吗。。。您用的app是哪个版本
>
>

是aes算法

## 回复 by 秋狝 (#9)

*2023-4-20 13:46*

感谢分享

## 回复 by wx_倾尽天下 (#10)

*2023-4-30 19:42*

感谢分享~![image](https://bbs.kanxue.com/view/img/face/28.gif)

## 回复 by mb_yivjyszq (#12)

*2023-5-21 15:58*

期待楼主后续分享

## 回复 by 常胜cs (#13)

*2023-5-22 15:43*

我需要JDGS sign 我有算法 现成的 有算法的 可以加我 有偿 也可以互换算法 V: wmt52188

## 回复 by mb_vtdbbwio (#14)

*2023-6-17 20:28*

[main]E/JDG: [make_header:480] [-] Error pp not init  这个该如何解决？

## 回复 by mb_ytoplrsb (#15)

*2023-8-21 13:17*

感谢分享，非常好

## 回复 by 安卓逆向test (#16)

*2023-8-30 10:28*

那个sign值我大体照你的方法来补，但是在调用callStaticJniMethodObject方法的时候出现了java.lang.ClassCastException: com.github.unidbg.linux.android.dvm.DvmObject cannot be cast to com.github.unidbg.linux.android.dvm.StringObject的错误，不知道是怎么回事

## 回复 by 西北吹风 (#17)

*2023-9-5 14:40*

看了一下jdgs在初始化得时候，做了很多环境判断，初始化代码没写，导致报 Error pp not ini错误

## 回复 by mb_yojqgpjh (#18)

*2023-10-11 09:14*

大佬，有空的时候分析下jdgs吧，感谢！！！

## 回复 by 北辰清影 (#19)

*2024-1-26 11:00*

请问jdgs中的objArr[0]如何转换打印出来呀![image](https://bbs.kanxue.com/view/img/face/15.gif)

## 回复 by 小 鲨 鱼 (#20)

*2024-9-6 19:58*

同求大佬出一篇分析下jdgs处理的问题：[main]E/JDG: [make_header:530] [-] Error pp not init

## 回复 by 若水天涯 (#21)

*2024-9-17 09:18*

期待楼主后续分享
