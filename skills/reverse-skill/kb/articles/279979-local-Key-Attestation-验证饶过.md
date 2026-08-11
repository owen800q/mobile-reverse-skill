---
title: '[分享]local Key Attestation 验证饶过'
url: https://bbs.kanxue.com/thread-279979.htm
tid: 279979
author: pareto
date: '2023-12-24'
tags: [Android安全, 分享, 基础理论, 系统相关, 源码框架]
crawled_at: '2026-08-11T08:46:25+00:00'
replies: 19
---

书接上文 <https://bbs.kanxue.com/thread-279799.htm>

自己做了一个本地绕过的脚本效果不是很理想，又去研究大佬的脚本，这个大佬的每次commit 基本我都看了，被大佬的底蕴折服，也印证了一句话，知识面越广，攻击面越广。

<https://github.com/chiteroman/BootloaderSpoofer>

## 思路1

评论里hook verify的思路，逻辑如图：

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556 | `public` `class` `Xposed implements IXposedHookLoadPackage {``private static` `int` `indexOf(byte[] array) {``final byte[] PATTERN` `=` `{``48``,` `74``,` `4``,` `32``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `1``,` `1``,` `0``,` `10``,` `1``,` `2``};``outer:``for` `(``int` `i` `=` `0``; i < array.length` `-` `PATTERN.length` `+` `1``; i``+``+``) {``for` `(``int` `j` `=` `0``; j < PATTERN.length; j``+``+``) {``if` `(array[i` `+` `j] !``=` `PATTERN[j]) {``continue` `outer;``}``}``return` `i;``}``return` `-``1``;``}` `@Override``public void handleLoadPackage(XC_LoadPackage.LoadPackageParam lpparam) {``try` `{``KeyStore keyStore` `=` `KeyStore.getInstance(``"AndroidKeyStore"``);``KeyStoreSpi keyStoreSpi` `=` `(KeyStoreSpi) XposedHelpers.getObjectField(keyStore,` `"keyStoreSpi"``);``XposedHelpers.findAndHookMethod(keyStoreSpi.getClass(),` `"engineGetCertificateChain"``, String.``class``, new XC_MethodHook() {``@Override``protected void afterHookedMethod(MethodHookParam param) throws Throwable {``Certificate[] certificates` `=` `(Certificate[]) param.getResultOrThrowable();``if` `(certificates[``0``] instanceof X509Certificate cert) {` `for` `(Method method : cert.getClass().getMethods()) {``if` `(method.getName().toLowerCase(Locale.ROOT).contains(``"verify"``)) {``/``/` `verify 不抛出异常表示验证通过``XposedBridge.hookMethod(method, XC_MethodReplacement.DO_NOTHING);``}``}` `/``/``获取证书编码,修改部分偏移的数据``/``/``修改Device locked:true``/``/``修改Verified boot state: Verified``byte[] bytes` `=` `cert.getEncoded();``if` `(bytes` `=``=` `null \|\| bytes.length` `=``=` `0``)` `return``;``int` `index` `=` `indexOf(bytes);``/``/``这个索引？``if` `(index` `=``=` `-``1``)` `return``;``bytes[index` `+` `38``]` `=` `1``;``bytes[index` `+` `41``]` `=` `0``;` `/``/``替换证书``CertificateFactory certFactory` `=` `CertificateFactory.getInstance(``"X.509"``);``X509Certificate modCert` `=` `(X509Certificate) certFactory.generateCertificate(new ByteArrayInputStream(bytes));``certificates[``0``]` `=` `modCert;``param.setResult(certificates);``}``}``});``} catch (Throwable t) {``XposedBridge.log(t);``}``}``}` |
|-|-|

这一版问题很明显，challenge 没有饶过，被修改的证书内容，实际无法通过公钥验证

## new

又更新了一个版本，卧槽 被大佬深厚的底蕴震撼 v3.5 , 这个版本的思路， 弥补之前的短板：

1. challenge 没有修复
2. 证书被修改后，实际没法通过公钥验证

那chiteroman怎么做的呢？

1. hook generateKeyPair ，返回插件预置的公私钥
2. hook setAttestationChallenge ，实时获取challenge
3. 替代 engineGetCertificateChain 函数，伪造整条证书链、并写入challenge

是吧 这个思路看起来很nice ，不过也存在问题 , 始终使用的内置的公私钥。换句话说，无论生成几次公私钥，始终是同一个公私钥,这一点问题。

正常产生的公钥
 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_WF7T555MNJVRQXB.webp)
有问题
 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_S4MVCK97QMD477X.webp)

怎么解决呢？

1. 内置多个证书
2. 中间人实时生产证书

我正在开发的脚本，思路就是直接走一个中间人发证书。

因为个人兴趣原因，后续可能也会做很多设备异常判定的研究，有相同志向的小伙伴 不做黑产！！纯研究，可以私信我。我看人多的话，就拉个群大家一起交流。

>
> <https://github.com/chiteroman/BootloaderSpoofer>
> <https://github.com/doom-man/bypasskeyattestation/blob/main/docs/other.md>
>
>
>

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-24 16:39*

感谢分享

## 回复 by 你瞒我瞒 (#3)

*2023-12-25 09:52*

感谢分享，已经发了私信，看到拉我一下![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by iceway (#4)

*2023-12-28 11:46*

这个内容干货很多，已经发了私信，能拉一下一起研究吗？

## 回复 by yyb (#5)

*2023-12-28 19:01*

咦，这个是52早还是看雪早，两边同时有这个贴？

## 回复 by 空空的爸爸 (#6)

*2023-12-30 12:55*

拉我一下。一起研究

## 回复 by ADR66 (#7)

*2023-12-31 08:29*

这个内容干货很多，已经发了私信，能拉一下一起研究吗？

## 回复 by sogohere (#8)

*2024-1-1 10:26*

谢谢大神分享！

## 回复 by 蓝色格调 (#9)

*2024-1-16 19:00*

“伪造整条证书链、并写入challenge”，证书链可以怎么获取呢？

## 回复 by pedies (#10)

*2024-1-20 18:44*

大佬 拉我入群

## 回复 by 空空的爸爸 (#11)

*2024-2-1 08:55*

实际上上使用中间人产生多个证书不可行。因为中间人证书也是在手机安全环境中生成。除非用最后生成的用户证书继续派生下一级用户证书，这样会存在两个证书都包含extensionOID 。这个问题需要特殊处理一下

## 回复 by 空空的爸爸 (#12)

*2024-2-1 09:00*

大家有兴趣的。我拉个群一起探讨？企鹅 383156428

## 回复 by pareto (#13)

*2024-2-19 15:27*

>
> [空空的爸爸](https://bbs.kanxue.com/user-887079.htm)
>
>  实际上上使用中间人产生多个证书不可行。因为中间人证书也是在手机安全环境中生成。除非用最后生成的用户证书继续派生下一级用户证书，这样会存在两个证书都包含extensionOID 。这个问题需要特殊处理一 ...
>
>

中间人 生成完整的证书链， extensionOID有什么问题吗

## 回复 by pareto (#14)

*2024-2-19 15:36*

相关研究方向的 可以进电报 https://t.me/+V4B4K7LtH4U0NTU1 ，最近研究方向偏移，近期可能不会更新，更新了，会发的

## 回复 by 空空的爸爸 (#15)

*2024-3-4 13:23*

>
> [pareto](https://bbs.kanxue.com/user-790193.htm)
>
>  中间人 生成完整的证书链， extensionOID有什么问题吗
>
>
>

中间人怎么生成完整的证书链？从手机里面拿到的只能是用户证书、

## 回复 by gunkkk (#16)

*2024-6-21 16:52*

官网明确只有根证书可信，这样也改不了根证书吧？ 另外为什么需要hook 生成密钥对的地方，返回内置密钥？很奇怪的操作

## 回复 by hacker521 (#17)

*2024-6-24 11:43*

还是过不了keyattention的检测啊？

## 回复 by pareto (#18)

*2024-6-24 12:49*

理论上没有泄露的私钥搞不了

## 回复 by 珍惜Any (#19)

*2024-6-24 14:09*

文章不错，这块分享一下一个通用的思路 。
1、服务端先hook 告诉客户端不支持tee和沙箱 ，这样客户端只能在证书初始化的时候设置第一种最弱的内存模式 。
2、客户端直接参考BootloaderSpoofer 配合无痕hook去掉。
（如果服务端有能直接bypass的更好）

## 回复 by guijian (#20)

*2026-5-6 11:18*

学习了
