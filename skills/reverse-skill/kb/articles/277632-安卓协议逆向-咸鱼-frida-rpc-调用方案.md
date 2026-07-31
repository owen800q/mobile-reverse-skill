---
title: '[原创]安卓协议逆向 咸鱼 frida rpc 调用方案'
url: https://bbs.kanxue.com/thread-277632.htm
tid: 277632
author: 行简
date: '2023-06-15'
tags: [Android安全, 原创, 逆向分析, 协议分析, HOOK注入]
crawled_at: '2026-07-31T14:44:50+08:00'
replies: 6
---

# 0x01 需求

通过frida rpc调用真机获取指定关键字的搜索结果数据。
本文仅供大家学习及研究使用、切勿用于各种非法用途。

# 0x02 rpc 简介

frida 提供了一种跨平台的 rpc （远程过程调用）机制，通过 frida rpc 可以在主机和目标设备之间进行通信，并在目标设备上执行代码，可实现功能如下：
*1、动态地修改函数和方法的参数和返回值。
2、监视和拦截特定函数和方法的调用。
3、修改内存中的数据和指令。
4、与目标设备上的应用程序进行交互，发送和接收数据。
5、在运行时加载自己的 JavaScript 脚本，从而实现自定义的行为修改。*

# 0x03 软硬件工具

app 版本：7.4.70
设备：K40 刷 piexl 11 rom
抓包工具：Charles
反汇编工具：JEB、JADX、IDA
inject：frida

# 0x04 抓包

>
> POST /gw/mtop.taobao.idle.search.glue/8.0/ HTTP/1.1
> x-sgext: JAfKISv0W5XonL3HUeX4UiH7EfgS%2BwL4F%2FIX8wL7F%2FoC%2BQ3%2FDfoN%2Bw37DfsN%2Bw37DfsN%2Bw35E%2BYQ5hL4DfkT5hHmEeYR5hHmEeYR5hHmEeYR5hHmEOYX%2Bg38EeYT%2Bg36DfoN%2BBnpEPwW%2BBH%2FF%2FoQ%2FQL6E6lA%2BhH6EPlH%2FRWoFvMT6RD%2FGekY6RL%2BAvoR%2BhbpEukQ6RDpEOkQ6RDpE%2BkQ6RP6AvkC%2FwKpAvoC%2BgL6AvoC%2BgLpROlHrwL6AqxEr0T6FukR%2BhH6EQ%3D%3D
> umid: Y6mM0d1XDnwDAAZc4d8Tk60B
> x-sign: azU7Bc002xAAJzB6M9wiB4WMskX6dzB3PW%2F64QfVy78rMahh4hODtL0DoF9kmgIWRqfEkGhlFlqjHfQDYE50A5EzkuewtzB3MLcwdz
> x-nettype: WIFI
> x-pv: 6.3
> x-nq: WIFI
> EagleEye-UserData: spm-cnt=a2170.8011571.0.0&spm-url=a2170.unknown.0.0
> first_open: 1
> x-features: 27
> x-app-conf-v: 0
> x-mini-wua: HHnB_QQx7EhGYzt0aRv0%2BjcjSfSTdMh9NXopIhtlxCcIGWkyEPONy4fMU296Q4NG4PEFmdynoG21RVXefkf%2Ff8G%2Fqlkl8cahX%2BEk3JT5GB2Uh4TNEqzzblgemWV%2Bitf42AKL%2FrWZLKkzalExnviNeICDt5A%3D%3D
> content-type: application/x-www-form-urlencoded;charset=UTF-8
> Content-Length: 630
> x-t: 1672056548
> Content-Type: application/x-www-form-urlencoded;charset=UTF-8
> x-bx-version: 6.5.56
> f-refer: mtop
> x-extdata: openappkey%3DDEFAULT_AUTH
> x-ttid: 231200%40fleamarket_android_7.4.70
> x-app-ver: 7.4.70
> x-c-traceid: Y6mM0d1XDnwDAAZc4d8Tk60B16720565484910160126869
> x-location: 0%2C0
> x-umt: 2QMB7AlLPMcI7wKFTpWcJNO9Tq3ykFES
> a-orange-q: appKey=21407387&appVersion=7.4.70&clientAppIndexVersion=1120221225203700833&clientVersionIndexVersion=0
> x-utdid: Y6mM0d1XDnwDAAZc4d8Tk60B
> x-appkey: 21407387
> x-devid: AnlVbDHuTb2u0LWMPSEZxO4CdI4PNLcEAjN85BBOipB9
> user-agent: MTOPSDK%2F3.1.1.7+%28Android%3B11%3BXiaomi%3BM2012K11AC%29
> Host: g-acs.m.goofish.com
> Accept-Encoding: gzip
> Connection: Keep-Alive
> data=%7B%22activeSearch%22%3Afalse%2C%22bizFrom%22%3A%22home%22%2C%22disableHierarchicalSort%22%3A0%2C%22forceUseInputKeyword%22%3Afalse%2C%22forceUseTppRepair%22%3Afalse%2C%22fromFilter%22%3Afalse%2C%22fromKits%22%3Afalse%2C%22fromLeaf%22%3Afalse%2C%22fromShade%22%3Afalse%2C%22fromSuggest%22%3Afalse%2C%22keyword%22%3A%22%E4%B8%9D%E8%A2%9C%22%2C%22pageNumber%22%3A1%2C%22resultListLastIndex%22%3A0%2C%22rowsPerPage%22%3A10%2C%22searchReqFromActivatePagePart%22%3A%22historyItem%22%2C%22searchReqFromPage%22%3A%22xyHome%22%2C%22searchTabType%22%3A%22SEARCH_TAB_MAIN%22%2C%22shadeBucketNum%22%3A-1%2C%22suggestBucketNum%22%3A27%7D
>
>
>

 多次抓包，发现变化的字段有：

>
> x-sgext、x-sign、x-mini-wua、x-c-traceid、x-t、Content-Length
>
>
>

# 0x04 参数分析

先从 x-sign 值入手， apk 包拖入 jadx 搜索，得到以下结果：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_KECFSEJVJQFPNVR.png)

 一个个点进去查看，发现并没有有价值的东西，仅仅只是构建字段名等操作，并且我尝试 hook 这些点，并没有得到有用的信息，换 JEB 看看，反复搜索观察，最终定位到 getUnifiedSign 这个函数：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_WTHEKW7CPR9JSVH.png)

 跟进查看它有三处调用点：

| 12345 | `Lmtopsdk``/``security``/``ISign;``-``>getUnifiedSign(Ljava``/``util``/``HashMap;Ljava``/``util``/``HashMap;Ljava``/``lang``/``String;Ljava``/``lang``/``String;ZLjava``/``lang``/``String;)Ljava``/``util``/``HashMap;,,` `Lmtopsdk``/``security``/``AbstractSignImpl;``-``>getUnifiedSign(Ljava``/``util``/``HashMap;Ljava``/``util``/``HashMap;Ljava``/``lang``/``String;Ljava``/``lang``/``String;ZLjava``/``lang``/``String;)Ljava``/``util``/``HashMap;,,` `Lmtopsdk``/``security``/``InnerSignImpl;``-``>getUnifiedSign(Ljava``/``util``/``HashMap;Ljava``/``util``/``HashMap;Ljava``/``lang``/``String;Ljava``/``lang``/``String;ZLjava``/``lang``/``String;)Ljava``/``util``/``HashMap;,,` |
|-|-|

解析：
第 1 处定义了 ISign 的接口，并写了 getUnifiedSign 方法，代码有删减：

| 123 | `public interface ISign {``HashMap getUnifiedSign(HashMap arg1, HashMap arg2, String arg3, String arg4, boolean arg5, String arg6);``}` |
|-|-|

第 2 处定义了一个抽象类 AbstractSignImpl 实现了 ISign 接口中的 getUnifiedSign 方法，当类实现接口的时候，类要实现接口中所有的方法。否则，类必须声明为抽象的类。该处声明的为抽象类，并不需要实现接口，代码有删减：

| 123456 | `public abstract` `class` `AbstractSignImpl implements ISign {``@Override`  `/``/` `mtopsdk.security.ISign``public HashMap getUnifiedSign(HashMap arg2, HashMap arg3, String appKey, String authCode, boolean useWua, String requestId) {``return` `null;``}``}` |
|-|-|

第 3 处定义了 InnerSignImpl 类继承 AbstractSignImpl，java中规定抽象类的子类必须给出抽象类中的抽象方法的具体实现，除非该子类也是抽象类。InnerSignImpl 并不是抽象类，也可以看出它实现了 getUnifiedSign 方法，代码有删减：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `public` `class` `InnerSignImpl extends AbstractSignImpl {``@Override`  `/``/` `mtopsdk.security.AbstractSignImpl``public HashMap getUnifiedSign(HashMap arg17, HashMap arg18, String appKey, String authCode, boolean useWua, String requestId) {``String instanceId` `=` `this.c();``if``(appKey` `=``=` `null) {``arg17.put(``"SG_ERROR_CODE"``,` `"AppKey is null"``);``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, instanceId` `+` `" [getUnifiedSign] AppKey is null."``);``return` `null;``}` `if``(arg17` `=``=` `null) {``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, instanceId` `+` `" [getUnifiedSign] params is null.appKey="` `+` `appKey);``return` `null;``}` `if``(this.f` `=``=` `null) {``arg17.put(``"SG_ERROR_CODE"``,` `"unified is null"``);``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, instanceId` `+` `" [getUnifiedSign]sg unified sign is null, please call ISign init()"``);``return` `null;``}` `try` `{``HashMap` `input` `=` `new HashMap();``String data` `=` `(String)this.a(arg17, appKey, true).get(``"INPUT"``);``boolean v10` `=` `StringUtils.isBlank(data);``if``(v10) {``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, this.c()` `+` `" [getUnifiedSign]get sign failed with sign data empty "``,` `"appKeyIndex="` `+` `this.a.k` `+` `",authCode="` `+` `this.a.i);``return` `null;``}` `input``.put(``"appkey"``, appKey);``input``.put(``"data"``, data);``input``.put(``"useWua"``, Boolean.valueOf(useWua));``input``.put(``"env"``, Integer.valueOf(this.d()));``input``.put(``"authCode"``, authCode);``input``.put(``"extendParas"``, arg18);``input``.put(``"requestId"``, requestId);``input``.put(``"api"``, arg17.get(``"api"``));``HashMap output` `=` `this.f.getSecurityFactors(``input``);``if``(output !``=` `null && !output.isEmpty()) {``return` `output;``}` `TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, this.c()` `+` `" [getUnifiedSign]get sign failed with no output "``,` `"appKeyIndex="` `+` `this.a.k` `+` `",authCode="` `+` `this.a.i);``}``catch(SecException v0_1) {``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, this.c()` `+` `" [getUnifiedSign]get sign failed and SecException errorCode "` `+` `v0_1.getErrorCode()` `+` `",appKeyIndex="` `+` `this.a.k` `+` `",authCode="` `+` `this.a.i, v0_1);``}``catch(Throwable v0) {``TBSdkLog.e(``"mtopsdk.InnerSignImpl"``, this.c()` `+` `" [getUnifiedSign]get sign failed exception ,appKeyIndex="` `+` `this.a.k` `+` `",authCode="` `+` `this.a.i, v0);``}` `return` `null;``}``}` |
|-|-|

从该函数中不难发现里面包含了许多抓包中的参数信息，有理由怀疑程序就是在此处进行组包并请求信息的！

# 0x05 hook getUnifiedSign

分析到这了，先 hook 看看 getUnifiedSign 函数请求和返回都是些啥，hook 代码：

| 123456789101112 | `function main() {``Java.perform(function () {``var InnerSignImpl` `=` `Java.use(``"mtopsdk.security.InnerSignImpl"``);``InnerSignImpl[``"getUnifiedSign"``].implementation` `=` `function (params, ext, appKey, authCode, useWua, requestId) {``console.log(``'\ngetUnifiedSign is called'` `+` `', '` `+` `'\nparams: \n'` `+` `params` `+` `'\n'` `+` `'ext: \n'` `+` `ext` `+` `'\n'` `+` `'appKey: \n'` `+` `appKey` `+` `'\n'` `+` `'authCode: \n'` `+` `authCode` `+` `'\n'` `+` `'useWua: \n'` `+` `useWua` `+` `'\n'` `+` `'requestId: \n'` `+` `requestId);``var ret` `=` `this.getUnifiedSign(params, ext, appKey, authCode, useWua, requestId);``console.log(``'getUnifiedSign ret value is '` `+` `ret);``return` `ret;``};``});``}``setImmediate(main)` |
|-|-|

搜索关键字：黑丝。
结果：

>
> getUnifiedSign is called,
> params:
> {data={"activeSearch":false,"bizFrom":"home","disableHierarchicalSort":0,"forceUseInputKeyword":false,"forceUseTppRepair":false,"fromFilter":false,"fromKits":false,"fromLeaf":false,"fromShade":false,"fromSuggest":false,"keyword":"黑丝","pageNumber":1,"resultListLastIndex":0,"rowsPerPage":10,"searchReqFromActivatePagePart":"searchButton","searchReqFromPage":"xyHome","searchTabType":"SEARCH_TAB_MAIN","shadeBucketNum":-1,"suggestBucketNum":27}, deviceId=AnlVbDHuTb2u0LWMPSEZxO4CdI4PNLcEAjN85BBOipB9, sid=null, uid=null, x-features=27, appKey=21407387, api=mtop.taobao.idle.search.glue, lat=0, lng=0, utdid=Y6mM0d1XDnwDAAZc4d8Tk60B, extdata=openappkey=DEFAULT_AUTH, ttid=231200@fleamarket_android_7.4.70, t=1672065081, v=8.0}
> ext:
> {pageId=, pageName=}
> appKey:
> 21407387
> authCode:
> null
> useWua:
> false
> requestId:
> r_342
> getUnifiedSign ret value is
> {x-sgext=JAc6QkgEOGWLbN43MhWbokILcghxC2EIdAJ0A2EJdghhCW4PbgpuC24LbgtuC24LbgtuC24MdRZzFnQNbgx1FnIWchZyFnIWchZyFnIWchZyFnIWcxZzDncWcw53FnEWchZyFnACYQt0DXAKdwxyC3UZcgghW3IKcgtxXHUOIA17CGEJdgphA2EJdhlyCnINYQlhC2ELYQthC2ELYQhhC2EOcRlxGXUZcw5hCmEKYQphCmEKYRknGSRfYQphXCdfJwInGXIKcgpy, x-umt=2QMB7AlLPMcI7wKFTpWcJNO9Tq3ykFES, x-mini-wua=HHnB_LsOm2MbDDQX8pocsAv844s/AJ3eeRpQBvQ0ruCym5E4E9z73i+wqyWX+kYoOCLjd0M+Af0hvQxs8NJyeS1/+qAd+g60eGM0Y7snvKtTeCvVhBnNESbEFrPu+orzouidZjoRxOAXN2Cpe1icpSFPKMA==, x-sign=azU7Bc002xAAJAe6xWI/sfnl+vxS1Be0CqzNIjAW/Hwc8p+i1dC0d4rAl5xTWTXVcWTzU1+mIZmU3sPAV41DwKbwpS1llAe0BZQHtA}
>
>
>

 参数都在这了，这就好办了，rpc 调用就能解决，注意这边的 data 数据是进行了 url 编码的，需进行进一步转化。
rpc 调用代码可参考我写的：[原创] 安卓协议逆向 cxdx 分析与实现](https://bbs.kanxue.com/thread-275790.htm) 一文。

---

# 回复

## 回复 by codeoooo (#2)

*2023-6-26 17:03*

沙发

## 回复 by suuuuu (#3)

*2023-7-3 17:28*

搜索白丝儿

## 回复 by 秋狝 (#4)

*2023-7-3 21:11*

感谢分享

## 回复 by kkte (#5)

*2024-1-9 20:21*

试了一下，似乎走到这里了，TBSdkLog.e("mtopsdk.InnerSignImpl", instanceId + " [getUnifiedSign]sg unified sign is null, please call ISign init()");

## 回复 by kkte (#6)

*2024-1-9 20:21*

看起来rpc还是要补上下文环境呐

## 回复 by Payne-Wu (#7)

*2024-5-29 17:19*

似乎有有检测params里面的data，然后导致参数生成正常但无法使用
