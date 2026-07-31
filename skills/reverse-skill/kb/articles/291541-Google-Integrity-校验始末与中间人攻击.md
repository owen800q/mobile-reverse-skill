---
title: '[原创]Google Integrity 校验始末与中间人攻击'
url: https://bbs.kanxue.com/thread-291541.htm
tid: 291541
author: lidongyooo
date: '2026-06-10'
tags: [Android安全, 原创, 逆向分析, 漏洞相关]
crawled_at: '2026-07-31T15:03:42+08:00'
replies: 140
---

Google Integrity 一直以绝对可信闻名，基于此大量的银行、金融类APP都高度依赖 Integrity 服务来验证客户端的请求是否可信。但它真的完全可靠吗？怀揣着这个疑问，我深度分析了 Integrity Token 的生成过程与 Key Attestation 的原理。得出的结论是不可靠。

### Integrity Token 的生成

在官方的文档中，想要获取一个 Token 有两种请求方式。分别为传统与标准请求。

传统请求的示例代码为：

```java
import com.google.android.gms.tasks.Task; ...

// Receive the nonce from the secure server.
String nonce = ...

// Create an instance of a manager.
IntegrityManager integrityManager =
    IntegrityManagerFactory.create(getApplicationContext());

// Request the integrity token by providing a nonce.
Task<IntegrityTokenResponse> integrityTokenResponse =
    integrityManager
        .requestIntegrityToken(
            IntegrityTokenRequest.builder().setNonce(nonce).build());
```

标准请求的示例代码为：

```python
import com.google.android.gms.tasks.Task;

// Create an instance of a manager.
StandardIntegrityManager standardIntegrityManager =
    IntegrityManagerFactory.createStandard(applicationContext);

StandardIntegrityTokenProvider integrityTokenProvider;
long cloudProjectNumber = ...;

// Prepare integrity token. Can be called once in a while to keep internal
// state fresh.
standardIntegrityManager.prepareIntegrityToken(
    PrepareIntegrityTokenRequest.builder()
        .setCloudProjectNumber(cloudProjectNumber)
        .build())
    .addOnSuccessListener(tokenProvider -> {
        integrityTokenProvider = tokenProvider;
    })
    .addOnFailureListener(exception -> handleError(exception));
```

这两种请求方式的区别仅仅是标准请求使用了缓存，高频调用的响应速度更快。从业务安全的角度来说是完全一致的。因此，我们以传统请求 API 为例，来

分析完整的生成过程。

#### 客户端分析

首先我们通过 Maven 拿到 Integrity 的 jar 包。然后使用 Jadx 打开定位到 requestIntegrityToken 函数：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_B69EBUDPH8GVH9R.webp)

发起请求时携带了一个 IntegrityTokenRequest 参数，里面主要包含了获取 Token 的必要参数：nonce、cloudProjectNumber。

进入到 this.a.c 函数：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_XPMUKK4DZ42ZGF5.webp)

- 将 nonce 解码为 byte[]
- 初始化 TaskCompletionSource 回调类
- 初始化 an 执行类（继承自 Runnable ）
- this.a.u 启动 an 线程

组装 Binder 跨进程调用参数：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_RGE2S4SU6J8ZJT3.webp)

发起调用：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_57UKUNM9PZFE6C5.webp)

最终由 IIntegrityService 做为服务端处理来自客户端的请求，至此我们正式进入 Google Play 源码分析。

#### 服务端分析

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_MNC7B9NWM5SB3C9.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_BXV7RZBKDNNVJMY.webp)

- 经由 dispatchTransaction 转发到 c 函数
- 由 c 函数具体处理客户端的请求

由于篇幅的关系，我这里不展开 c 以及一系列子函数的调用。我只大概讲一下它的流程：

- 接收客户端参数
- 验证客户端的身份（通过 Binder.getCallingUid() 验证 Uid 是否与包名相等）
- 收集设备信息（ro.build.product、ro.product.brand、ro.vendor.build.fingerprint）
- 收集登录账号信息（用于验证是否具有指定 APP 的安装权限）
- 收集包名信息（通过 PMS 获取版本号、签名 Signature[] apkContentsSigners = signingInfo.hasMultipleSigners() ? signingInfo.getApkContentsSigners() : signingInfo.getSigningCertificateHistory(); 、安装来源标识等……）
- 将包名等信息转发给 GMS DroidGuard 签名
- 发起 Key Attestation 挑战拿到 Tee 证书链（验证设备是否已解锁）
- 将所有信息组装为 Protobuf 数据包发给后端验证
- 后端返回 Integrity Token 回调客户端

```json
Request Body：
{
  "type": "IntegrityRequestParameters",
  "deviceIntegritySignals": {
    "type": "DeviceIntegritySignals",
    "droidguardTokenByteString": {
      "type": "ByteString",
      "size": 39032,
      "sha256": "bd5a30d9d722df7e36397b918861aa9084ef9eb54ae31255926e7552e84e4104",
      "asciiPreview": "..'..i........O.].....[.....s.......D.Q..M.w+.t..o...@..{HD..~-..U'....V.Y..z......._.}......DL.",
      "hexPreview": "0a06270ae369a80012c1b0020a064c06f22f2f1e1e68ae3126dba9ac7ae367a7488b1cc40d81ff230e19a6c55d75537e7d3",
      "base64Preview": "CgYnCuNpqAASwbACCgZPrF2VyZrSEFsAAOOyvHOlh8C+TYZbQWkeIyFfTKs5JIvjXQqUIFrFi1qWSY0nXJZIXfHo0tpmUUwpdGWPHySiA"
    },
    "flowName": "pia_attest_e1",
    "keyAttestationMetadata": {
      "type": "bmyq",
      "raw": "# bmyq@5eb8d24",
      "field_b": "2",
      "field_d": "null",
      "field_e": "# bmyn@7c344",
      "field_f": "null",
      "certificateChain": [
        {
          "type": "ByteString",
          "size": 678,
          "sha256": "984470b2b5ceafcdcd705c1a6285bc93ffe420fea2d25d373dcdc3949ac85fda",
          "asciiPreview": "0...0..H........0...*.H.=...091.0...U....TEE1)0'..U... 22317fdd8510cac935893090d9b6e2a00...70010",
          "hexPreview": "308202a230820248a003020102020101300a060828648ce3d020106082a8648ce3d0301070342000413a0b0fdc54e9e1861e41bdc30",
          "base64Preview": "MIICojCCAkigAwIBAgIBATAKBggqhkjOPQQDAjA5MQwwC30Oo4IBWTCCAVUwDgYDVR0PAQH/BAQDAgeAMIIBQQYKKwYBBAHWeQIBEQSCATEw"
        },
        {
          "type": "ByteString",
          "size": 503,
          "sha256": "5e6af0046b0b9faf744df21648abe4e049c1c7e5c0de06b830e6b784187d7e8d",
          "asciiPreview": "0...0..y........&..Y...O.B....M0...*.H.=...091.0...U....TEE1)0'..U... d492ff615155c8a4a60926ded6",
          "hexPreview": "308201f330820179a00302010202101c26a48a5902c1a64f97429fadfbe538393330393064396236653261",
          "base64Preview": "MIIB8zCCAXmgAwIBAgIQHCakilkCwaZPl0KfrfvhTTAKBggqhkjOCWgwDTmGjYzBh"
        },
        {
          "type": "ByteString",
          "size": 920,
          "sha256": "2812ef63dd35e8d8c7cbc6453dbd7961ec5f1e3645d4eae0584dbd383f0ae7ec",
          "asciiPreview": "0...0..|...................G..w.0...*.H........0.1.0...U....f92009e853b6b0450...240202225757Z..3",
          "hexPreview": "308203943082017ca003020102021100941cbcc1e8a41de02e17e847c3b877db300d06092a052b810400220362000408",
          "base64Preview": "MIIDlDCCAXygAwIBAgIRAJQcvMHopB3gLhfoR8O4d9swDQYJKoZIhvcNAQELBQAwGzEZMBcGABGuj"
        },
        {
          "type": "ByteString",
          "size": 1312,
          "sha256": "cedb1cb6dc896ae5ec797348bce9286753c2b38ee71ce0fbe34a9a1248800dfc",
          "asciiPreview": "0...0.............r.....0...*.H........0.1.0...U....f92009e853b6b0450...220320180748Z..420315180",
          "hexPreview": "3082051c30820304a0030201041663abef982f32c77f7531030c9752",
          "base64Preview": "MIIFHDCCAwSgAwIBAgIJAPHBcqaZ6vUdM+T+W8a9nsNL/ggj"
        }
      ],
      "certificateChainCount": 4
    },
    "buildFingerprintMetadata": {
      "type": "bmyh",
      "fingerprint": "Lenovo/TB320FC_PRC/TB320FC:15/AQ3A.240812.002/ZUXOS_1.1.350_250418_PRC:user/release-keys",
      "raw": "# bmyh@8f6a54a8"
    }
  },
  "packageName": "gr.nikolasspyr.integritycheck",
  "versionCode": 22,
  "nonce": "4X4a4MUeHGybbu9GQF9vYBbqYTg==",
  "certificateSha256Digests": [
    "F5UrXPhnBbreh3Q_WjMe_kyYK_tNoNL9XXC_wjXPeeM"
  ],
  "timestampAtRequest": "2026-04-18T13:45:51.190Z",
  "cloudProjectNumber": null,
  "playCoreVersion": {
    "type": "bmyu",
    "major": 1,
    "minor": 4,
    "patch": 0,
    "versionString": "1.4.0"
  },
  "playProtectDetails": {
    "type": "bmyv",
    "raw": "# bmyv@7bcd9",
    "fields": {
      "b": "1",
      "c": "2"
    }
  },
  "appAccessRiskDetailsResponse": {
    "type": "abfk",
    "raw": "AppAccessRiskDetailsResponse{installedAppsSignalData={2=[com.motorola.mobiledesktop, com.zui.pp, com.zui.wifip2p, com.lenovo.penservice, com.lenovo.ue.device, com.lenovo.levoice.trigger, com.zui.safecenter, com.qualcomm.qti.services.systemhelper, com.zui.cores, com.dolby.dolbyvisionservice, vendor.qti.qesdk.sysservice, com.qualcomm.qti.uceShimService, com.qualcomm.qti.dynamicddsservice, com.qti.dpmserviceapp, com.motorola.android.providers.settings], 6=[bin.mt.plus]}, accessibilityAbuseSignalData={}, displayListenerMetadata=DisplayListenerMetadata{isActiveDisplayPresent=false, displayListenerInitialisationTimeDelta=Optional.empty, lastDisplayAddedTimeDelta=Optional[PT-0.001S], displayListenerUsed=2}, signalGenerationLatency=PT0.002342813S, signalGenerationBreakdownTelemetry=SignalGenerationBreakdownTelemetry{requestParametersLatency=RequestParametersLatencyBreakdown{installedPackages=PT0.040158698S, runningAppProcesses=PT0.002319791S, runningServices=PT0.001184271S, activeDisplays=PT0.001730833S, enabledAccessibilityServices=PT0.004136928S, mediaProjectionDebugDump=PT0.001912032S, runningApps=PT0.000196459S, installedPackagesIsRecognized=PT0.000449375S, appOpsToOpEntry=PT0.00093677S, manifestPermissionToPackages=PT0.067272969S, activeDisplayInfo=PT0.000058125S, accessibilityServiceData=PT0.000021302S, runningMediaProjectionTypeServicePackages=PT0.000812031S}, installedAppsSignalLatency=PT0.000189688S, screenCaptureSignalLatency=PT0.00091099S, accessibilityAbuseSignalLatency=PT0.000031927S, screenOverlaySignalLatency=PT0.000257761S, displayListenerMetadataLatency=PT0.001320938S}}"
  },
 "installSourceMetadata": {
        "type": "bmyk",
        "formatted": "1:1,2:1,3:0,4:1,5:[],6:0",
        "raw": {
          "c": "31",
          "d": "1",
          "e": "1",
          "f": "0",
          "g": "1",
          "i": "0"
        }
      },
      "locationTrustMetadata": null,
      "deviceIdentifier": {
        "type": "ByteString",
        "size": 64,
        "sha256": "e47aa4c751f9079c06367ff3814e9bb441c754242e2154929de5067a680a3b4e",
        "ascii": "894ce4844f1b477fa99a4f515de4acaa80121998b19efe3e7faffae6497be163",
        "hex": "383934636534383434663162343737669376265313633",
        "base64": "ODk0Y2U0ODQ0ZjFiNDc3ZmE5="
      }
    }
}

Response Body:
{
  "token": "eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.ullChctbyhVID6nmtbgtcMqN3fxb2tsNIeLD9baKL6YnkFjbfjGcWSyADMZLeaK1XbmSYMO3OegfoX0CwEQkSDSa3bfwfM9Bo_NTD3b8i_hXCkpdAuPpahcLy_VLh5tvcqwSx7KAFEyg5IxkPPGeIIVehPwi22xBPcq3V5Pe7NOF705Av4nXv1-GgP9t5IPnf3moFbo4lqMJBANi8.35KbgY4kp8sL9jJyRNjE5w",
  "statusCode": "0",
  "extra": "null",
}
```

在收集的所有信息中，最为人津津乐道的便是 Tee 签名的证书链。这是由绝对安全的硬件空间生成的设备描述信息，按理说是绝对可信的。因为，一旦你更改了返回的证书链，你没办法重签。不重签后端就不认这个证书链，直接判定为伪造。你想要重签，就必须拿到私钥，可是私钥放到 Tee 中，不可导出不可读取。因此，形成了完美闭环。

这套完美的防御体系，看似无懈可击。但是当 Tee 私钥泄漏了之后呢？这条防御链条中最重要的一环，将土崩瓦解。

### Key Attestation 的原理

Google Play 发起 Key Attestation 的代码为：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_WBTFJKPHVGKMBZA.webp)

- 首先指定别名、密钥生成算法、挑战值（防重放）等信息构建一个 KeyGenParameterSpec
- 通过 KeyPairGenerator 指定 AndroidKeyStore 为具体的处理服务
- generateKeyPair 生成派生密钥对
- getCertificateChain 拿到最终的认证证书链
- 发送给服务端验证

这些调用的背后实际上发生了什么呢？generateKeyPair 具体的流程如下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_ZWWSTGFQ78B3C84.webp)
这一步调用完以后 ，Tee 返回一个 X.509 证书链。这个证书链就是 Key Attestation 验证的核心。一般情况下至少包含三个证书：

- Root Certificate（厂商根证书（预存在 Tee），必须交由 Google 备案。否则不能通过验证。）
- Attestation Certificate（中间证书（预存在 Tee），当前设备的证书。必须经过 Root Private Key 签名。）
- Leaf Certificate（叶子证书（Tee 动态生成的证书），必须经过 Attestation Private Key 签名。附带大量的设备描述与辅助验证信息）

根据官方文档描述，Leaf Certificat 附带的信息至少包含如下两项：

1. RootOfTrust（用于校验设备是否已解锁）
2. AttestationApplicationId（用于校验发起密钥认证的 APP 签名）

拿到证书链之后，便组包发给了 Google 后端进行校验。那么在后端是如何校验的呢？依赖的便是在上文中指定的签名算法：EC（secp256r1），实际上使用的算法是：ECDSA（椭圆曲线数字签名算法）secp256r1为指定的椭圆曲线参数。算法具体的签名与验证过程：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_NGR5R9W7ZMGM38F.webp)

根据图中的验证过程可知：私钥只签名不参与验证，公钥只验证不参与签名。签名值与公钥分别附加在证书的 Certificate.signatureValue Certificate.TBSCertificate.subjectPublicKeyInfo 中。因为每张证书都由上张证书签名，所以 Google 拿到三张证书依次进行校验：

- r, s = decode_ecdsa_signature(Leaf.signatureValue); ecdsa_verify(Leaf.TBSCertificate, r, s, Attestation Public Key)
- r, s = decode_ecdsa_signature(AttestationsignatureValue); ecdsa_verify(Attestation.TBSCertificate, r, s, Root Public Key)

```python
def ecdsa_verify(message, r, s, Q):
    # 1. 检查签名范围
    if r <= 0 or r >= n:
        return False

    if s <= 0 or s >= n:
        return False

    # 2. 计算消息哈希
    e = sha256(message)

    # 3. 求 s 的模逆
    w = inverse_mod(s, n)

    # 4. 计算两个系数
    u1 = (e * w) % n
    u2 = (r * w) % n

    # 5. 椭圆曲线点运算
    P = point_add(
            scalar_mult(u1, G),
            scalar_mult(u2, Q)
        )

    if P is INF:
        return False

    # 6. 验证
    x = P.x % n

    return x == r
```

当校验到 Root Certificate 时，由于没有上级证书。这时拿 Root Certificate 去数据库匹配，如果这张 Root Certificate 是由厂商提交过备案的，则证明整条链条可信。接下来再继续校验 AttestationApplicationId、RootOfTrust 等信息。其中 RootOfTrust 是获得 MEETS_DEVICE_INTEGRITY 也就是二绿的关键。这里面携带了设备是否解锁的标识：deviceLocked。并且整个 RootOfTrust 状态是由 Tee 维护的，因此不具备伪造性。

但是当我们拥有一台有 Root 权限并且没有解锁 Bootloader 设备的时候呢？那么这台设备就具备就具备以下两个发起中间人攻击的条件：

- 能通过 Google Integrity 验证（因为 BootLoader 未解锁）
- 能将 Key Attestation 的证书链导出（因为拥有 Root 权限）

### 中间人攻击实验

设备A：Y700 - 拥有 Root 权限 - 三绿

设备B：Pixel6 - 拥有 Root 权限 - 一绿

Google Play 版本均保持一致（过 AttestationApplicationId 签名校验）

| 设备 | 是否具有Root 权限 | 是否通过 Google Integrity 验证 |
|-|-|-|
| Y700 | 是 | 是 |
| Pixel 6 | 是 | 否 |

我们使用如下 Frida 脚本启动 Pixel 的 Google Play：

```js
// 伪代码：
let cache_certificate_chain = []

function sendToY700(challenge) {
    // connect server
    // send challenge
    return certificate_chain
}

function hook() {
    Java.perform(function () {
        const KeyPairGeneratorSpec = Java.use('android.security.keystore.KeyGenParameterSpec$Builder');
        KeyPairGeneratorSpec.setAttestationChallenge.overload('[B').implementation = function (challenge) {
            cache_certificate_chain = sendToY700(challenge)
            return this.setAttestationChallenge(challenge);
        };

        const SecLevel = Java.use('android.security.keystore2.IKeystoreSecurityLevel$Stub$Proxy');
        SecLevel.getCertificateChain.implementation = function () {
            return cache_certificate_chain
        };

    });
}

setImmediate(hook)
```

如下脚本启动 Y700 的 Google Play：

```js
// 伪代码：
function receiveFormPixel6(challenge) {
    let KeyGenParameterSpec keyGenParameterSpecBuild = new KeyGenParameterSpec.Builder("integrity.api.key.alias", 4).setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1")).setDigests("SHA-512").setAttestationChallenge(challenge).setDevicePropertiesAttestationIncluded(false).build();
    let KeyPairGenerator keyPairGenerator = KeyPairGenerator.getInstance("EC", "AndroidKeyStore");
    keyPairGenerator.initialize(keyGenParameterSpecBuild);
    if (keyPairGenerator.generateKeyPair() == null) {
        throw new IllegalStateException("Failed to create the key pair.");
    }
    let String keystoreAlias = keyGenParameterSpecBuild.getKeystoreAlias();
    return keyStore.getCertificateChain(keystoreAlias);
}
```

然后惊奇的发现：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012164_EJPZ3ZWNH4SQQQU.webp)

---

# 回复

## 回复 by SomeMx (#2)

*2026-6-10 09:55*

学习一下

## 回复 by wx_唔. (#3)

*2026-6-10 10:17*

6666

## 回复 by brookwang (#4)

*2026-6-10 10:37*

学习一下

## 回复 by 酷伯 (#5)

*2026-6-10 10:42*

学习一下

## 回复 by pareto (#6)

*2026-6-10 10:59*

1

## 回复 by pareto (#7)

*2026-6-10 11:04*

google play  认证 有效果吗

## 回复 by 4Chan (#8)

*2026-6-10 11:20*

学习一下

## 回复 by apxar (#9)

*2026-6-10 11:34*

1

## 回复 by New对象处 (#10)

*2026-6-10 11:43*

一大早起来，看到别的群发无root做rpc转发，卷起来了

## 回复 by git_73061mrtdev4 (#11)

*2026-6-10 12:14*

good

## 回复 by wlmf (#12)

*2026-6-10 14:10*

mark,话说无root有方案吗？还是说无解

## 回复 by 温泉划水鱼 (#13)

*2026-6-10 15:03*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_elqwyvnm (#14)

*2026-6-10 15:18*

学到就是赚到

## 回复 by ivy1 (#15)

*2026-6-10 17:11*

学到就是赚到

## 回复 by cobe (#16)

*2026-6-10 17:49*

666

## 回复 by zxc (#17)

*2026-6-10 17:59*

1

## 回复 by MsScotch (#18)

*2026-6-10 18:34*

划重点：拥有一台有 Root 权限并且没有解锁 Bootloader 设备

## 回复 by wx_666_974 (#19)

*2026-6-10 18:45*

学习

## 回复 by YAR (#20)

*2026-6-10 19:53*

666

## 回复 by mb_bvvcoitr (#21)

*2026-6-10 20:58*

本质上还是play integrity检测太松。否则 deviceIdAttestion 就够喝一壶的

## 回复 by mb_enbuhisq (#22)

*2026-6-10 21:03*

66666666

## 回复 by kingking888 (#23)

*2026-6-10 22:21*

666

## 回复 by Ascend_202904 (#24)

*2026-6-10 22:43*

66666666666

## 回复 by wx_Huber Barrientos (#25)

*2026-6-10 22:55*

666

## 回复 by mb_qimctavn (#26)

*2026-6-11 08:53*

6

## 回复 by baichisi (#27)

*2026-6-11 09:37*

666

## 回复 by xwtwho (#28)

*2026-6-11 09:48*

1

## 回复 by dreameriii (#29)

*2026-6-11 10:06*

我能想到有2个防御点，一起讨论看看：1、 challenge 用时间戳，中间人转发 KA 请求，到 root 未解锁设备生成KA结果，再转发回来，这里耗时估计会比较高，后端服务器计算KA结果到服务器的时间，减去 challenge的时间，对比同型号其他设备的平时间差；
2、攻击者需要以我们app的身份在root未解锁的设备发起KA请求，那肯定要注入代码，这里就需要做好app被注入攻击的检测（lsposed、frida等等）。

## 回复 by method (#30)

*2026-6-11 11:09*

1

## 回复 by shuangmou (#31)

*2026-6-11 11:26*

感谢分享

## 回复 by mb_bvvcoitr (#32)

*2026-6-11 17:31*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>  我能想到有2个防御点，一起讨论看看：1、&nbsp;challenge&nbsp;用时间戳，中间人转发&nbsp;KA&nbsp;请求，到&nbsp;root& ...
>

1.抛去网络延时，我知道有实现已经可以在10ms内完成双向传输，而且计算ka到服务器的时间受网络环境影响太大了；
2.可以注入keystore2 binder服务而不是app

我觉得本质上这个是没办法防御的，除非将密钥认证证书与设备硬件信息进行绑定，并且传送给谷歌，类比腾讯soter的实现。

## 回复 by mb_bvvcoitr (#33)

*2026-6-11 17:32*

此外就是做好安全补丁版本验证，对安全补丁斑斑太低的设备提高不信任值。

## 回复 by koflfy (#34)

*2026-6-11 18:04*

mark

## 回复 by dreameriii (#35)

*2026-6-11 19:12*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif) 确实，注入 keystore2 那就没办法了。

## 回复 by mb_dmkmqsyg (#36)

*2026-6-11 20:45*

666

## 回复 by zeroghost (#37)

*2026-6-11 22:49*

666

## 回复 by mb_xjdhrmck (#38)

*2026-6-12 10:21*

6666

## 回复 by Imxz (#39)

*2026-6-12 17:52*

tql

## 回复 by zxxxxxe (#40)

*2026-6-13 20:00*

666

## 回复 by git_29853Sandyeeee (#41)

*2026-6-13 20:25*

love

## 回复 by 文西哥 (#42)

*2026-6-14 07:20*

66666

## 回复 by buluo533 (#43)

*2026-6-14 09:09*

学习一下

## 回复 by mb_goqnmbff (#44)

*2026-6-14 13:40*

学习一下

## 回复 by sunnoc (#45)

*2026-6-14 22:46*

666

## 回复 by zylyy (#46)

*2026-6-14 23:37*

666

## 回复 by mb_dcjxxhsk (#47)

*2026-6-15 00:27*

666

## 回复 by guardia (#48)

*2026-6-15 02:31*

see

## 回复 by 冷瞳 (#49)

*2026-6-15 09:42*

555

## 回复 by memoriaru (#50)

*2026-6-15 09:52*

学习

## 回复 by mb_cbgtaveo (#51)

*2026-6-15 10:10*

6666666666

## 回复 by mb_hdmrryzf (#52)

*2026-6-15 11:52*

6

## 回复 by qqqiu (#53)

*2026-6-15 12:04*

6

## 回复 by swkl (#54)

*2026-6-15 15:30*

66666666666

## 回复 by mb_jnmxfjku (#55)

*2026-6-15 19:05*

666

## 回复 by mb_rewimxhj (#56)

*2026-6-16 02:26*

看看吧

## 回复 by tjytjy (#57)

*2026-6-16 15:46*

666

## 回复 by haris4687 (#58)

*2026-6-16 16:45*

666

## 回复 by mb_suajmqsa (#59)

*2026-6-17 06:09*

>
> [MsScotch](https://bbs.kanxue.com/user-718886.htm)
>  划重点：拥有一台有 Root 权限并且没有解锁 Bootloader 设备
>

8gen5和8至尊gen5

## 回复 by mb_yalauklc (#60)

*2026-6-17 10:38*

666

## 回复 by mb_depeeceu (#61)

*2026-6-17 11:28*

666

## 回复 by veluboii (#62)

*2026-6-17 17:51*

666

## 回复 by chionyuna (#63)

*2026-6-17 17:55*

666

## 回复 by 呼吸24K纯氧 (#64)

*2026-6-17 19:24*

看看

## 回复 by pigsub (#65)

*2026-6-17 20:02*

6666

## 回复 by wx_huhu_859 (#66)

*2026-6-17 20:42*

11

## 回复 by mb_ndbtkggd (#67)

*2026-6-18 11:43*

234

## 回复 by 飆汗吉米 (#68)

*2026-6-18 19:53*

666

## 回复 by 4seaynl (#69)

*2026-6-20 02:53*

支持一下

## 回复 by Popluna (#70)

*2026-6-20 07:03*

学习中间人攻击实现思路

## 回复 by Kk一刀 (#71)

*2026-6-23 13:27*

1

## 回复 by hyz111 (#72)

*2026-6-23 14:00*

666

## 回复 by wx_Dispa1r (#73)

*2026-6-23 14:16*

1

## 回复 by 乔治_331129 (#74)

*2026-6-24 11:28*

goat

## 回复 by mb_xwntdpxy (#75)

*2026-6-24 19:43*

666

## 回复 by zpazz (#76)

*2026-6-25 15:15*

？

## 回复 by iceway (#77)

*2026-6-25 15:17*

666666

## 回复 by ulong9527 (#78)

*2026-6-26 09:03*

感谢分享，学习一下

## 回复 by ulong9527 (#79)

*2026-6-26 09:03*

测试回复-爬虫验证

## 回复 by mb_tfqctboq (#80)

*2026-6-26 15:57*

666

## 回复 by chago (#81)

*2026-6-26 17:09*

有点东西

## 回复 by Circ1e (#82)

*2026-6-26 17:35*

666

## 回复 by Viseris (#83)

*2026-6-26 17:44*

6666

## 回复 by mb_dlljjfcf (#84)

*2026-6-26 21:14*

66666多谢

## 回复 by liowmark (#85)

*2026-6-30 09:33*

学习

## 回复 by mb_uvyukvot (#86)

*2026-6-30 16:14*

666

## 回复 by mb_qbqklzyt (#87)

*2026-7-1 12:06*

666

## 回复 by git_58319TheShuiLan (#88)

*2026-7-1 15:36*

6666666666666666

## 回复 by wx_Ruin (#89)

*2026-7-2 03:12*

\````````

## 回复 by herbo (#90)

*2026-7-2 12:02*

666

## 回复 by mb_xpgokwnb (#91)

*2026-7-2 14:20*

?

## 回复 by roysue (#92)

*2026-7-2 15:02*

666

## 回复 by cnhuaWu (#93)

*2026-7-2 15:34*

666

## 回复 by Big权 (#94)

*2026-7-2 15:50*

学习

## 回复 by mb_qdutazbj (#95)

*2026-7-2 18:22*

666

## 回复 by Nuyoah、 (#96)

*2026-7-6 10:44*

6666

## 回复 by Thehepta (#97)

*2026-7-6 11:01*

1

## 回复 by Gfyg (#98)

*2026-7-6 11:55*

6666

## 回复 by mb_donutrph (#99)

*2026-7-6 16:40*

666

## 回复 by iBa0 (#100)

*2026-7-6 20:30*

123

## 回复 by 寒号鸟二代 (#101)

*2026-7-6 22:12*

6666

## 回复 by mb_kvudlizw (#102)

*2026-7-7 01:23*

666666

## 回复 by Ro0kie (#103)

*2026-7-7 10:29*

6666

## 回复 by wx_kx92911 (#104)

*2026-7-9 09:54*

感谢分析

## 回复 by Crack999 (#105)

*2026-7-9 15:17*

2311

## 回复 by dig_grave (#106)

*2026-7-9 17:26*

1

## 回复 by 小黄鸭爱学习 (#107)

*2026-7-9 17:27*

111

## 回复 by ClPrada (#108)

*2026-7-9 18:01*

666666

## 回复 by Zepp7289 (#109)

*2026-7-9 19:14*

tql

## 回复 by AK1988DA (#110)

*2026-7-13 16:49*

0009

## 回复 by st6666 (#111)

*2026-7-14 11:54*

66666666666

## 回复 by mb_auiexznm (#112)

*2026-7-14 16:55*

66666666666666666666

## 回复 by mb_bvwbboty (#113)

*2026-7-14 17:13*

666

## 回复 by mb_degalzhb (#114)

*2026-7-15 14:32*

666

## 回复 by 肆意残沙 (#115)

*2026-7-15 14:35*

学习

## 回复 by mb_kbkqyusp (#116)

*2026-7-15 14:39*

666666

## 回复 by 星落黎明 (#117)

*2026-7-15 15:11*

感谢分享

## 回复 by Ruinv6 (#118)

*2026-7-16 15:35*

11111111111

## 回复 by simpleness (#119)

*2026-7-16 21:02*

6

## 回复 by git_87569irmch (#120)

*2026-7-17 03:01*

666

## 回复 by TeamAR (#121)

*2026-7-17 07:31*

666

## 回复 by mb_rvbdmznk (#122)

*2026-7-17 15:31*

666

## 回复 by Vengeance (#123)

*2026-7-20 10:24*

666

## 回复 by sleep4r (#124)

*2026-7-20 17:55*

666

## 回复 by mb_sihvtppm (#125)

*2026-7-22 15:18*

1

## 回复 by mosida (#126)

*2026-7-22 15:38*

666

## 回复 by Cure. (#127)

*2026-7-22 16:16*

integrity_token，safetynet_token能通过代码生成吗

## 回复 by dob_C (#128)

*2026-7-23 16:20*

感谢分享

## 回复 by 悠久之翼灬 (#129)

*2026-7-23 16:22*

6

## 回复 by Sam--小小龙 (#130)

666

## 回复 by mb_xpgokwnb (#131)

66666

## 回复 by Ben曹 (#132)

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by Migc (#133)

666

## 回复 by 淡定小胖子 (#134)

6666

## 回复 by git_30584zhutou9527 (#135)

666

## 回复 by huaerxiela (#136)

666

## 回复 by huaerxiela (#137)

666

## 回复 by mb_qlanixyh (#138)

6666

## 回复 by git_86585flowclouds (#139)

好文章，学习一下

## 回复 by git_86585flowclouds (#140)

>
> [Cure.](https://bbs.kanxue.com/user-1022596.htm)
>  integrity_token，safetynet_token能通过代码生成吗
>

目测是不能的，

## 回复 by nqminhquan (#141)

666666666
