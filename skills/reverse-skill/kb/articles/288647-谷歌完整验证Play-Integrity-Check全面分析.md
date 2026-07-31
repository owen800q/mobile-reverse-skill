---
title: '[原创]谷歌完整验证Play Integrity Check全面分析'
url: https://bbs.kanxue.com/thread-288647.htm
tid: 288647
author: 恋空
date: '2025-09-30'
tags: [Android安全, 原创, 基础理论, 逆向分析, 系统相关]
crawled_at: '2026-07-31T14:03:42+08:00'
replies: 31
---

引言

在海外安卓APP市场，Google Play Integrity API是风控策略的最重要一环。大部分APP风控系统均依赖于这个体系，Play Integrity Check不是一个简单的设备检查，而是一套精密的远程安全证明（Remote Key Attestation） 系统

##### 一、核心架构：分层判决与信任链传递

Play Integrity API 的响应结构（Integrity Verdict）本身就是其技术理念的体现——分层判决。它不是给出一个单一结论，而是提供一组信号，由开发者服务器基于自身风险模型进行最终决策。

技术原理： 其核心依赖于一个由Google硬件根密钥签名的认证链。整个过程可分解为：

###### 1.触发与挑战（Challenge）：

应用向设备上的Play服务发起请求，附带一个由服务器生成的、一次性的随机数（"nonce"）或哈希（"requestHash"）。此步骤用于防止重放攻击。

###### 2.数据收集与签名（Data Collection & Signing）：

 Play服务作为可信执行环境（TEE）或StrongBox的调用代理，收集设备硬件、系统状态、应用身份等多种信号。这些信号与"nonce"一起，由一个受硬件保护的密钥进行签名，生成一个完整性令牌（Integrity Token）。

###### 3. 令牌验证（Token Verification）：

###### 应用将令牌发送至开发者服务器。服务器必须执行最关键的一步：离线验证令牌的签名链，一直追溯到Google的根证书。绝不能在客户端验证，否则被篡改的系统可能提供虚假的“成功”响应。

###### 4. 解码与判决（Decoding & Adjudication）：

验证通过后，服务器解码令牌中的JSON载荷，并根据其中各个字段的信号进行综合风控判决。

##### 二、深度解码：几大判决字段的技术内涵

> {
>
>
>   "requestDetails": { ... },
>
>   "appIntegrity": { ... },
>
>   "deviceIntegrity": { ... },
>
>   "accountDetails": { ... },
>
>   "environmentDetails": { ... }
>
> }
>
>

###### 1. 请求详情 ("requestDetails") - 防重放机制

> "requestDetails": {
>
>
>   // 代码包名
>
>   "requestPackageName": "com.package.name",
>
>   // 请求哈希
>
>   "requestHash": "aGVsbG8gd29scmQgdGhlcmU",
>
>   // 时间戳
>
>   "timestampMillis": "1675655009345"
>
> }
>
>

技术原理： 这是所有验证的第一道关卡。服务器必须严格比对

"requestPackageName"和

"requestHash"/

"nonce"是否与原始请求一致。

风控意义： 确保返回的判决结果确实是对本次特定请求的响应，有效抵御攻击者截获并重复使用旧令牌的重放攻击（Replay Attack）。

###### 2. 应用完整性 ("appIntegrity") - 代码身份认证

* 技术原理： 此字段直接验证应用本身的二进制身份。

"appRecognitionVerdict"的取值源于与Google Play服务器上的官方记录进行比对。

  "PLAY_RECOGNIZED"：应用的证书SHA256摘要、包名和版本号与Play商店中最新或允许的版本完全匹配。这证明了应用未被篡改、重打包或替换签名。

   "UNRECOGNIZED_VERSION"：证书或包名可能有效，但版本不符（如安装的是非官方渠道的修改版）。

风控意义： 这是对抗重打包应用（Repackaged App） 和木马植入的第一道防线。对于金融、支付等核心场景，应强制要求"PLAY_RECOGNIZED"。

###### 3. 设备完整性 ("deviceIntegrity") - 设备健康状态检测

> "deviceIntegrity": {
>
>
>   // "MEETS_DEVICE_INTEGRITY" is one of several possible values.
>
>   "deviceRecognitionVerdict":   ["MEETS_DEVICE_INTEGRITY"]
>
> }
>
>

这是最复杂且最核心的部分，采用了一种标签化（Label-based） 的信任模型。

技术原理： 系统通过多个维度评估设备环境：

硬件支持验证： 检查是否具备硬件支持的密钥认证（如TEE），"verifiedBootState"是否为"Verified"，"deviceLocked"是否为

"true"。这是"MEETS_DEVICE_INTEGRITY"的基础。

模拟器检测： 纯软件模拟器通常无法通过硬件验证，因此无法获得"MEETS_DEVICE_INTEGRITY"标签。"MEETS_VIRTUAL_INTEGRITY"则为Google认可的安全模拟器提供了出路。

标签体系解析：

"MEETS_BASIC_INTEGRITY"：最低限度信任。 设备可能已解锁Bootloader或系统未认证，但系统内核未被严重破坏（无Root）。可用于过滤掉最粗糙的篡改。

重点参考：KeyAttestion验证是否为合法谷歌颁发证书，且未吊销。非模拟器设备，ROM为经过谷歌GMS认证的设备系统。（主要通过Build信息和系统签名来判断）

参考意义：依据谷歌的说法，如果获得此项检测，则至少说明设备应该获取到GMS验证

"MEETS_DEVICE_INTEGRITY"：核心信任等级。 意味着设备是正版硬件，引导加载程序已锁定，运行的是经过认证的系统映像。这是绝大多数安全操作的必要条件。

重点参考：证书的rootOfTrust结构，确保该设备BL未被解锁

"MEETS_STRONG_INTEGRITY"：最高信任等级。 在"MEETS_DEVICE_INTEGRITY"基础上，还要求系统在过去一年内接收过安全更新。这旨在排除那些长期不更新、存在已知漏洞的设备。

重点参考：Build.SECURITY_PATCH，证书里面的补丁版本信息

风控意义： 允许开发者实施分级风控策略。例如，对低价值操作，允许

"MEETS_BASIC_INTEGRITY"；对高价值操作，要求

"MEETS_STRONG_INTEGRITY"；对作弊零容忍的游戏，则拒绝所有无

"MEETS_DEVICE_INTEGRITY"标签的设备。

###### 4. 账户详情 ("accountDetails") - 授权验证

* 技术原理： 检查当前登录的Google账号是否拥有该应用在Google Play上的授权（许可）。

"appLicensingVerdict: LICENSED"意味着应用是从Play商店安装的。

* 风控意义： 有效识别并阻止从第三方商店旁加载（Sideload） 的应用，这些应用是盗版和篡改的重灾区。

5. 环境详情 (

"environmentDetails") - 运行时动态风险

这是API的进阶能力，从静态验证延伸到动态环境监控。

应用访问风险 ("appAccessRiskVerdict")：

技术原理： 动态扫描当前运行的应用，检测哪些应用拥有无障碍服务（Accessibility Service）、 overlay 或屏幕截图权限。关键在于，它并非简单阻止所有此类应用，而是将其分为

"KNOWN_"（来自Play商店或系统预装）和

"UNKNOWN_"（来自其他来源）两类。

   * 风控意义： 精准对抗自动化脚本（Bots） 和屏幕窃取。开发者可以制定策略：例如，允许知名的屏幕录制工具（

"KNOWN_CAPTURING"），但阻止一切未知来源的控制应用（

"UNKNOWN_CONTROLLING"）。

 Play保护机制 ("playProtectVerdict")：

   * 技术原理： 集成Google Play Protect的扫描结果，告知设备上是否安装了已知的恶意软件。

   * 风控意义： 提供了设备整体健康度的另一个维度。即使用户通过了设备完整性检查，但如果设备上存在银行木马，其风险依然极高。此信号可用于触发额外的身份验证或直接拒绝交易。

##### 三、攻击难点

1. 服务端决策原则： 所有信任判决必须在开发者自己的服务器上完成。客户端仅负责收集和传递令牌。

2. 信号融合，非绝对信任： Play Integrity提供的是信号（Signals），而非绝对的“安全/不安全”结论。开发者应将这些信号与自身业务数据（如用户行为分析、交易历史）相结合，构建自适应的风控模型。

3. 纵深防御（Defense in Depth）： 不要依赖单一信号。一个作弊应用可能通过了应用完整性检查（重打包技术高超），但设备完整性必定失败。一个正版应用可能在已被Root的设备上运行，此时设备完整性信号就会失效。多重信号交叉验证才能构建坚固的防线。

#### 四、切入正题

###### 绕过难点在哪里：

绕过难点在于谷歌证书信任链，是由谷歌根证书颁发给通过了GMS验证的设备厂商。

###### 为啥证书的可信链无法攻击：

设备的证书存储在基于ARM Trustazone的TEE环境或者基于单独硬件的Strongbox中，很难通过外部攻击。请看下面信息传递机制

###### 信息传递的精妙机制：

> ###### BOOTROM --> ABL ---> 传递信息给TZ ---> Linux内核
>
>

开机时，设备bootrom（写死在固件）预先验证abl分区（Android Bootloader）程序是否符合预期签名才能启动（而无论设备bl是否解锁）

abl分区会在安全空间（Secure area）加载一部分信息给Tee或者strongbox，来确定bl程序是否被解锁了

如果未解锁，则通过AVB机制验证系统的完整性（根据vbmeta分区的签名校验分区），才完成启动，将控制权交给boot分区的内核

如果已经解锁，则跳过验证。但是会把已经解锁的信息传给安全空间，这样后续开机后获取到的证书信息rootOfTrust就会显示已经解锁

###### 系统启动后：

keystore2进程会接收来自APP的Key Attention请求（通过binder），然后调用到keymint HAL进入安全空间生成证书

###### 部分绕过方法：

BootloaderSpoof

通过在APP进程端hook AndroidKeyStore的请求完成证书替换。

Trickystore

通过注入到keystore进程，拦截binder请求的ioctl调用，完成证书替换。

但是需要有效的keybox才能完成替换，获得三绿。

密钥证明是基于谷歌根证书的下级证书，在运行时生成的临时证书，来证明请求来自真实设备。keybox，就可以理解为包含了下级证书和私钥都文件。而playintgrity的验证重点就是密钥证明。

参考文档：

https://developer.android.com/google/play/integrity/verdicts?hl=zh-cn

---

# 回复

## 回复 by baitongling (#2)

*2025-9-30 17:26*

第一

## 回复 by matrump (#3)

*2025-9-30 17:31*

tql

## 回复 by mb_ldbucrik (#4)

*2025-9-30 18:38*

感谢分享

## 回复 by New对象处 (#5)

*2025-9-30 18:43*

keybox是个问题

## 回复 by QQ765746002 (#6)

*2025-10-1 10:58*

大佬，我有个问题，我想做一个pdd的环境包，请问谷歌3的话这种对应表应该怎么弄呢，有偿有偿师傅。

## 回复 by lidongyooo (#7)

*2025-10-2 13:50*

666

## 回复 by KerryS (#8)

*2025-10-5 04:43*

有没有可能,A设备是风险的,B设备是正常的,把验证的工作转移给B去做

## 回复 by 恋空 (#9)

*2025-10-7 15:58*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  有没有可能,A设备是风险的,B设备是正常的,把验证的工作转移给B去做
>
>

理论上是不行的。因为，KeyAttestion每次生成出来的验证证书，包含了调用者的包名和签名SHA256（且这个过程执行在系统keystore2进程内）。在正常未解锁设备下，你既无法伪造出应用签名，也无法hook或者篡改系统代码。所以，你还是无法绕过。
详细字段参考：https://developer.android.com/privacy-and-security/security-key-attestation?hl=zh-cn
字段名称：AttestationApplicationId

例外：

除非你有办法在未解锁bl的情况下，攻击系统拿到权限，或者hook系统代码。

并且，证书内包含了系统补丁日期，谷歌对这种有漏洞的设备版本比较敏感。（懂得都懂

## 回复 by Zkeleven (#10)

*2025-10-7 16:45*

666

## 回复 by KerryS (#11)

*2025-10-8 04:55*

>
> [恋空](https://bbs.kanxue.com/user-862224.htm)
>
>
>
>
>
>
>
>  KerryS
>
>
>
>  有没有可能,A设备是风险的,B设备是正常的,把验证的工作转移给B去做
>
>  理论上是不行的。因为，KeyAttestio ...
>
>

AB两个设备都安装同一个app,同一版本,这样的话,调用者的包名和签名,岂不是都是一样的了吗

## 回复 by 久处不厌557 (#12)

*2025-10-9 16:46*

tql

## 回复 by 恋空 (#13)

*2025-10-9 17:53*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  AB两个设备都安装同一个app,同一版本,这样的话,调用者的包名和签名,岂不是都是一样的了吗
>
>

你教教我怎么在未解锁未root的情况下，拿到别的应用的证书数据？你是神偷吗？

## 回复 by 不具名的悲伤 (#14)

*2025-10-10 14:14*

6

## 回复 by lookzo (#15)

*2025-10-12 09:50*

666

## 回复 by mb_qsiyccce (#16)

*2025-10-13 10:21*

感谢分享1

## 回复 by mb_qsiyccce (#17)

*2025-10-13 10:21*

感谢分享2

## 回复 by gtict (#18)

*2025-10-13 10:58*

这种证书链，，咋分析。。在bootloader上的

## 回复 by mb_dqziiprm (#19)

*2025-10-13 13:42*

6666661

## 回复 by mb_qsiyccce (#20)

*2025-10-13 14:15*

6666664

## 回复 by mb_qsiyccce (#21)

*2025-10-13 15:42*

感谢博主分享，受益颇丰

## 回复 by mb_hadiqbct (#22)

*2025-10-16 10:45*

好文章，打开新思路

## 回复 by dreameriii (#23)

*2025-10-16 16:07*

大佬有研究过 TrickyStore的检测不？

## 回复 by mb_rqezybkt (#24)

*2025-10-22 05:30*

>
> [恋空](https://bbs.kanxue.com/user-862224.htm)
>
>  你教教我怎么在未解锁未root的情况下，拿到别的应用的证书数据？你是神偷吗？
>
>

那么问题来了，你怎么知道他不是神偷！！！

## 回复 by mb_rqezybkt (#25)

*2025-10-24 15:15*

大佬，能加个好友吗，私信下我，我账号没权限私信

## 回复 by mb_qsiyccce (#26)

*2025-10-27 17:46*

大佬

## 回复 by mb_joqmgxbb (#27)

*2025-10-28 18:23*

重点未吊销keybox

## 回复 by mb_qsiyccce (#28)

*2025-11-4 10:38*

大佬，能加个好友吗

## 回复 by 阿钟wilsion (#29)

*2026-3-16 14:28*

keybox.xml是怎么提取出来的呢

## 回复 by mb_dcjxxhsk (#30)

*2026-4-22 11:06*

关键是哪里来的keybox，hook点很多

## 回复 by mb_lzotvdxv (#31)

*2026-5-9 20:24*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by mb_lzotvdxv (#32)

*2026-5-10 12:32*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext
