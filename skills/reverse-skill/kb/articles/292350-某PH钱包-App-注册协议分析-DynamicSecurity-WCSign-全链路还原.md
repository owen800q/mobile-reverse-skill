---
title: 某PH钱包 App 注册协议分析：DynamicSecurity「WCSign」全链路还原
url: https://bbs.kanxue.com/thread-292350.htm
tid: 292350
author: 星野安全
date: '2026-08-08'
tags: [Android安全]
crawled_at: '2026-08-14T05:10:19+00:00'
replies: 10
---

>
> **目标 App**：`com.globe.gcash.android`（GCash）6.00.2 build 1213
> **对象层**：自研 DynamicSecurity（`RequestEncryption` / `GAESCipher` / `GRSACipher`），
> **本文结构**：按分析顺序记录「假设 → 实验 → 否证/坐实 → 数据」；密钥/私钥只露前缀
>
>
>

---

## 0. 分析目标与判据

需要回答三个问题：

1. 注册发码 / 验码走哪条网络路径（host、path、body 形态）？
2. 加密与签名的原语是什么、字段谁加密谁明文、如何做到本地组包字节级等价于真机？
3. 设备身份（apdid / udid / utdid / 机型）绑在哪一层、哪些能纯离设备造、哪些是硬缺口？

起点条件：App 有反系统代理、同进程多套 Alipay 系 RPC、native 存在 APSE 白盒、进入注册页易崩溃。下面按分析顺序记录，包含走过的弯路。

先确立判据：能否用纯 Python 组包、打到真网关，使服务器验签通过、发出真 OTP，并跑完 generate → verify → isGcashRegistered → register 全链路。该判据区分「组包看似正确」与「服务器实际接受」两种情况，下文多数篇幅用于排除前者。

---

## 1. 复现环境

| 层 | 本次复现 | 产出 |
|-|-|-|
| 静态 | jadx-headless 加载 `gcash_1213_base.apk`，`class_count=82230`，`load≈58s` | 关键类 smali（Java 反编译被 anti-decompile 干扰，smali 可读） |
| 密码 oracle | 本地临时 RSA 对 + 组包 + 服务器视角解封 | 24 项离线单测 PASS |
| 握手 | 直连 `api.mynt.xyz` key-agreement（v1 GET+POST） | 真实 `flowId` + 服务器 X509 公钥 |
| 铸 apdid | `iclientgw-sea.alipay.com/imgw.htm` | `{apdid,token}` 形态与真机一致 |
| 历史实网 | lab 会话 `F6C07A5E`（2026-07-20） | generate/verify/isreg 明文响应 |
| 真机动态 | 进程内 sergei `GCashHook` 冷启动（6.01.0） | 指纹 RPC 明文 + DynSec 钩子就绪（见 §3.2 / §12） |
| 全链路闭合 | 纯离设备 register（虚拟号 + 铸 apdid） | KYC level 1 `APPROVED / FOR CREATION`（见 §11） |

>
> Java 层关键方法普遍插了 `goto` 噪声（`if-eqz v0, :cond_1` 自环），jadx 报 `Method not decompiled`。分析时直接读 smali 调用序，不依赖 Java 源。
>
>
>

---

## 2. 抓包入口：系统代理探测

### 2.1 现象

开系统 HTTP 代理，注册步弹：

\```
This feature does not support Android ver4.4 and lower
\```

关掉代理后流程恢复，接码可收到 6 位 OTP。SSL unpin（`TrustManagerImpl.verifyChain` 放行）在同环境是生效的。

### 2.2 判断

拦截的不是 TLS pin 证书，而是「系统代理设置被探测」。在 Windows + 系统代理 + mitmproxy 上直接抓注册 RPC，入口不可用；后续需透明路由，或在进程内、加密前抠明文。

此步无「解密失败的密文」可分析——请求未按预期路径发出。由此确定方向：该协议的明文只存在于进程内、`RequestEncryption` 组包之前，线路上只有一段 `sign`。

---

## 3. RPC hook：设备指纹旁路，非注册 OTP

### 3.1 假设

注册走 Alipay mobilegateway / mPaaS RPC，hook `com.alipay.mobile.common.rpc.*` 或动态 `Proxy` 即可。

### 3.2 实验

进程内 hook `Proxy.newProxyInstance`，对带 `@OperationType` 的 InvocationHandler 挂 `invoke`。同进程实际两套：

| 框架 | Handler | 注册期实际用途 |
|-|-|-|
| IAP AC | `com.iap.ac.android.rpc.RpcInvocationHandler` | 配置 / 设备指纹上报 |
| Quake | `com.alipay.imobile.network.quake.rpc.RpcInvocationHandler` | 改 MPIN 等 |

抓到的明文指纹 RPC（真机冷启动，本次复测 logcat），`JsonSerializer` / RPC hook 同时打出（URL 仍是 imgw）：

\```
operationType = alipay.security.deviceFingerPrint.staticData.report.v2
url = https://iclientgw-sea.alipay.com/imgw.htm
requestData = [{
  "apdid": "eYOIklFxBezvpB4O2bCc1f4M…",
  "bizData": {"reqType":"1"},
  "dataMap": {
    "AA1": "com.globe.gcash.android",
    "AA2": "6.01.0",
    "AA3": "APPSecuritySDK-OVERSEA",
    "AA4": "P9.0.2.20250905",
    "AE1": "android",
    "AE10": "M2007J3SG",
    "AE12": "12",
    "AE13": "36"
  },
  "os": "android"
}]
\```

同次启动 `TokenResult` 缓存：

\```
apdid      = eYOIklFxBezvpB4O2bCc1f4M…
apdidToken = …nwEAAA==
umidToken  = null
\```

另有配置类 RPC（冷启动）：`ap.mobileamcs.cloud.fetch.config` / `ap.mobileprod.amcs.config.local.fetch`，明文里同样带 spoof 后的 `mobileModel` / `osVersion` / `clientVersion`。

据此确认：

1. 进程内 hook 能绕过反 MITM 拿明文；
2. 改机字段（机型 `AE10`、系统 `AE12`/`AE13`）进了指纹上报；
3. 铸造端点形态与 §10 离设备 mint 一致（`os:"android"` + imgw），token 尾缀同为 `nwEAAA==`；
4. `umidToken=null`：GCash 的指纹 SDK 未启用 umid（§9.3 坐实 `needUmid=false`），排除了「必须复现 umid」这一方向。

### 3.3 否证

注册页按 Next，没有发码 operation-type。名字带 Otp 的 `OtpVerificationFacade`（Quake）在注册路径上也不触发——静态确认它挂在 reset_mpin，不是注册。

结论：RPC 线是旁路证据，不是注册 OTP 主路径。需从 UI 往下静态追。

---

## 4. 从 Activity 到 Retrofit 注解

### 4.1 调用链（smali 级）

`OtpRepositoryImpl.generateOtpCodeWc` 核心逻辑（去噪后语义）：

\```
body = LinkedHashMap{ msisdn ← params, udid ← params }   // scenarioID 不进 body
header = GKApiServiceDynamicSecurity.Companion
           .getEncHeaders( mapOf("scenarioID" → scenarioID) )
wcSign = RequestEncryption().generateSignedBody(
           header, body, listOf("msisdn"), "POST")
→ safeCall { service.generateOtpCodeNew(wcSign) }
\```

接口注解（jadx smali，本次复现）：

```smali
# GKApiServiceDynamicSecurity.generateOtpCodeNew
.annotation runtime Lretrofit2/http/POST;
    value = "c4/v2.3/otp/generate_code"
.end annotation
# @Body WCSign

# GKApiServiceDynamicSecurity.verifyOtpCode
.annotation runtime Lretrofit2/http/POST;
    value = "/c4/v2.3/otp/verify_code"
.end annotation
\```

Host 不在注解里，实测基址 `https://api.mynt.xyz`（与旧 `c4/v1/otp/*` Map body 路径并存；注册新路径走 v2.3 + WCSign）。

### 4.2 三种「在线 hook」落空的原因

| 打点 | 为何空 |
|-|-|
| 标准 mPaaS RPC | 不是那条线 |
| Quake OtpVerificationFacade | 改 MPIN，不是注册 |
| 明文 okhttp body | `@Body` 已是 `WCSign`，字段已 AES |

正确 choke point：`RequestEncryption.generateSignedBody`（dex 层，免壳，是整个协议里唯一能一次获取「明文 body + 明文 header + 本地 aesKey/iv + 最终 sign」的点）。

---

## 5. `generateSignedBody` 结构（smali 调用图）

类：`gcash.common.android.util.encryption.RequestEncryption`
模型：`WCSign{ sign, aesKey, iv }`（字段 jadx 坐实）

### 5.1 顶层五步（`generateSignedBody` smali）

\```
p1 = EncryptedHeader headers
p2 = body Object
p3 = List encParams
p4 = method String

WCEncrypt  = b(headers, body, encParams, method)   // 组 request + sec
payload    = n(WCEncrypt)                          // gson → m() Base64
sig        = l(payload)                            // GRSACipher.sign(priv)
sign       = sig + "." + payload
return new WCSign(sign, this.d /*aesKey*/, this.c /*iv*/)
\```

`b()` 再拆：

\```
EncryptedRequest  = h(headers, body, encParams, method)  // 内含 d() 头加密 + c() body 加密
EncryptedSecurity = i(headers, encParams)                // RSA 封 key/iv + enc 路径清单
return new WCEncrypt(request, security)
\```

`n()`：

\```
gson.toJson(obj) → m(json)   // m = Base64 NO_WRAP
\```

`l()`：

\```
GRSACipher.sign(payload, GHashConfigPrefService.getPrivateKey())
\```

线路模型：`sign = base64(RSA_sign(payload)) + "." + base64(gson(WCEncrypt))`。`@Body(WCSign)` 只 `@Expose` 了 `sign` 一个字段；`aesKey`/`iv` 本地留存（用于解响应、解字段），服务器侧的密钥在 `sec.key`/`sec.initializer` 中被 RSA 封装。

### 5.2 头加密 `d()`：谁走 AES、谁走 Base64

smali 明确分支：

| 字段 | 处理函数 |
|-|-|
| Authorization / X-Package-Id / channel / channelSecret / X-Reg-Channel | `e()` = AES 字段加密（非空才加密） |
| X-Env-Info | `m()` = Base64 only，不是 AES |
| 其它（X-UDID、X-FlowId、Time…） | 透传明文 |

组包时此处易错：把 `X-Env-Info` 也做 AES 会与真机不一致。「非空才加密」是一个隐含条件——`Authorization` 在注册期是空串，`d()` 判空后置 null，gson 省略 null 键，因此最终 payload 中没有 Authorization 键，`sec.enc` 清单里也不出现它。这条「空 → 缺席」连锁在复现时容易被忽略。

### 5.3 body 加密 `c()`：只动 `encParams` 点名路径

语义：`gson → JsonObject → 按 path 遍历 → 叶子 e() AES → 回写`。注册 generate 的 path 列表为 `["msisdn"]`，故 udid 明文留在 body。原实现支持 `a.b[0].c` 嵌套路径遍历，但注册/登录/建号全程只用扁平字段名，无需实现嵌套。

### 5.4 `i()`：EncryptedSecurity

\```
initializer = GRSACipher.encrypt(serverPub, iv)      // 字段 this.c
key         = GRSACipher.encrypt(serverPub, aesKey)  // 字段 this.d
enc         = j(headers路径) + k(body encParams路径)
// EncryptedSecurity 构造顺序在模型里对应 enc / initializer / key
\```

`GRSACipher.encrypt` 的原语（§6.2 展开）：服务器公钥为 X509/SubjectPublicKeyInfo，填充是 `RSA/ECB/PKCS1Padding`（PKCS#1 v1.5），输出 Base64 NO_WRAP。封装对象是本请求随机生成的 `aesKey`（32 字符）与 `iv`（16 字符）；服务器用自身私钥解出这一对，即可解 `sec.enc` 清单点名的密文。

oracle 解出的 `sec.enc` 真值（本次复现 generate）：

```json
[
  "request.header.X-Package-Id",
  "request.header.X-Reg-Channel",
  "request.body.msisdn"
]
\```

verify 会多一条 `"request.body.code"`。`sec.enc` 是「本次哪些叶子被 AES」的路径索引，须与 `d()`/`c()` 实际加密的字段逐一对齐，多一条少一条服务器解密都会错位。

### 5.5 `RequestEncryption` 私有方法全景（smali 单字母混淆 → 语义）

该类各 helper 方法如下。方法名在 dex 里被混淆成单字母，调用图仍清晰：

| 混淆名 | 签名（语义） | 干什么 | 关键点 |
|-|-|-|-|
| `generateSignedBody` | (header, body, encParams, method) → WCSign | 顶层编排 | 见 §5.1 五步 |
| `b` | (…) → WCEncrypt | 组 `{request, sec}` | = `h()` + `i()` |
| `h` | (…) → EncryptedRequest | 组 `{body, header, method}` | body 走 `c()`、header 走 `d()`；method=POST→null |
| `d` | (EncryptedHeader) → Map | 头字段级处理 | 命中 `ENCRYPTED_HEADERS` 且非空 → `e()`；`X-Env-Info` → `m()`；余透传 |
| `c` | (body, encParams) → JsonObject | body 字段级 AES | 按 path 遍历叶子 → `e()` 回写；`encParams` 外字段不动 |
| `e` | (String) → String | AES 字段加密 | `GAESCipher.encrypt`（AES/CBC/PKCS5，key/iv=this.d/this.c） |
| `i` | (header, encParams) → EncryptedSecurity | 组 `{enc, initializer, key}` | 见下 `j`/`k` |
| `j` | (header) → List | header 加密路径 | 对每个在场且被加密的头 → `"request.header.<k>"` |
| `k` | (encParams) → List | body 加密路径 | 对每个 encParam → `"request.body.<p>"` |
| `n` | (WCEncrypt) → String | 序列化 payload | `m( gson.toJson(WCEncrypt) )` |
| `m` | (bytes/String) → String | Base64 NO_WRAP | flag=2；同时是 `X-Env-Info` 的编码器 |
| `l` | (payload) → String | RSA 签名 | `GRSACipher.sign(payload, getPrivateKey())` |

调用树：

\```
generateSignedBody
├─ b → WCEncrypt
│   ├─ h → EncryptedRequest{ body:c(body,encParams), header:d(header), method }
│   │        c(叶子)→e()=AES        d(命中头)→e()=AES / X-Env-Info→m()=Base64
│   └─ i → EncryptedSecurity{ enc:j(header)+k(encParams),
│                             initializer:RSA(iv), key:RSA(aesKey) }
├─ n → payload = m( gson(WCEncrypt) )           // Base64(gson)
├─ l → sig     = RSA_sign(payload)              // SHA256withRSA
└─ WCSign( sig + "." + payload, aesKey, iv )
\```

需区分 `e()`（AES）与 `m()`（Base64）：头里只有 `X-Env-Info` 走 `m()`，其余敏感头与 body 点名字段走 `e()`。`sec.enc`（=`j()`+`k()`）是「本次哪些叶子走了 `e()`」的路径清单，服务器据此反查解密。

---

## 6. 密码学原语与字节等价约束

原语为 AES-CBC + SHA256withRSA。复现的关键在于序列化字节需与真机完全一致，否则签名无法通过；本文的多数细节集中于此。

### 6.1 AES — `GAESCipher.encrypt`

\```
Cipher.getInstance("AES/CBC/PKCS5Padding")
SecretKeySpec( secretKey.getBytes(UTF_8), "AES" )
IvParameterSpec( iv.getBytes(UTF_8) )
Base64.encodeToString(doFinal(...), flag=2)   // 2 = NO_WRAP
\```

关键细节：key/iv 是「可打印字符串」，直接取 UTF-8 字节作密钥，不是 raw bytes。

- `getSecretKey(n)` = `NanoIdHelper.generate(n)`，注册用 `n=32` → 32 个可打印字符 → 32 字节 → AES-256；iv = `NanoId(16)` → 16 字节。
- NanoId 字母表：aesKey/iv 用 URL-safe 64 表 `_-0-9A-Za-z`（密钥每字节落在这 64 个可见 ASCII 内，密钥空间为 `64^32` 而非 `256^32`，熵略低；对复现无影响，dump 出来为可读字符串）。

固定材料自检（任何语言可对拍）：

\```
key = "k"*32, iv = "i"*16
AES("639277040774") = 3K3bz/aoHS3Hj8sN5ie/bw==
\```

### 6.2 RSA — 一类三用（sign / seal / verify）

`GRSACipher` 承担三类操作，填充与密钥格式不同：

| 用途 | smali | 密钥 | 算法 | 干什么 |
|-|-|-|-|-|
| 签 payload | `sign → e()` | 客户端私钥 PKCS8 | `SHA256withRSA` | 签 `payload`，得 `sig` |
| 封 aesKey/iv | `encrypt` | 服务器公钥 X509 | `RSA/ECB/PKCS1Padding`(v1.5) | 进 `sec.key`/`sec.initializer` |
| 验签（服务器侧镜像） | `verify` | 客户端公钥 X509 | `SHA256withRSA` | oracle 自检用 |

\```
# sign
PKCS8EncodedKeySpec( Base64.decode(priv, 2) )
Signature.getInstance("SHA256withRSA")
initSign → update(message UTF-8) → sign
Base64.encodeToString(..., 2)
\```

私钥空时 `sign` 会 `blockingGet` 触发握手再签——对应「第一次请求前必握手」（§8）。

### 6.3 gson 字节等价约束（四条件）

签名字节来自 `new Gson()` 的默认序列化，本地需逐字节复刻。四条约束：

**① HTML 转义**。`new Gson()` 默认把 `= < > & '` 转成 `\u00XX` 形式。AES 密文 Base64 常带 `==` padding，进 gson 后 padding 变成 `\u003d\u003d`。

oracle 真实 payload 片段（本次复现，注意 `=` 已被转义成 `\u003d`）：

\```
...BvaAQU0caw\u003d\u003d","udid":"ANDoiGQf...
\```

固定 key 演示（左侧是 AES 原始密文里的 `==`，右侧是它进 gson 后变成的样子）：

\```
gson_dumps({"msisdn":"3K3bz/aoHS3Hj8sN5ie/bw==", "udid":"AND..."})
→ {"msisdn":"3K3bz/aoHS3Hj8sN5ie/bw\u003d\u003d","udid":"AND..."}
\```

缺此步则本地 payload 字节与 App 不一致（每个 `=` 变 6 字符 `\u003d`），`SHA256withRSA` 无法通过。

**② 紧凑分隔符**：`,` 与 `:`，无空格。

**③ 省略 null 键**：值为 null 的键 gson 默认不输出（前面 Authorization 空 → 缺席、method=POST → null → 省略，都依赖此）。

**④ 字段顺序 = ART 字段名字母序**。此条容易被忽略：gson 按 Java 反射得到的字段顺序序列化，ART 上该顺序为字段名字母序。本地组包时 dict 的键须按此序构造，否则 payload 字节改变、签名不通过。三个容器实测顺序：

| 容器 | 字段字母序 |
|-|-|
| `WCEncrypt` | `request`, `sec` |
| `EncryptedRequest` | `body`, `header`, `method`（method=POST 时 null → 省略） |
| `EncryptedSecurity` | `enc`, `initializer`, `key` |

`EncryptedHeader` 同理，其 JSON key 输出顺序（省略 null 后）实测为：

\```
Authorization, channel, channelSecret, Content-Type, Correlator-ID, Time,
X-AccountId, X-Correlator-Id, X-DBID, X-Env-Info, X-EventLinkId, X-FlowId,
X-LinkRequestId, X-Package-Id, X-Reg-Channel, X-Security-Id, X-Service-Prefix,
X-Tracker, X-UDID, X-UserId
\```

OTP 路径只设了其中 `Time / X-Correlator-Id / X-Env-Info / X-FlowId / X-Package-Id / X-Reg-Channel / X-Tracker / X-UDID`（与实测 `header_keys` 一致），其余键在场为 null → 省略。

四条中缺任一条：本地 payload 字节即与 App 不一致，`SHA256withRSA` 无法通过服务端验签。其表现为验签失败而非解密失败——服务端多回 `422 Invalid Signature` 或网关拒绝，易被误判为加密实现错误（§11 的 register 段即出现过一次 `code:400 Failed verification at prehandling`）。

---

## 7. 离线 oracle：服务器视角往返验证

思路：先不打真网关，用自造服务器密钥对验证「组包结构可解回」。该步骤将「密码学是否正确」与「服务器业务/风控是否接受」解耦；§10 的 `key:null` 判定依赖它排除签名错误的可能。

### 7.1 步骤

1. `simulate_handshake()` → 客户端对 + 假服务器对；
2. 铸一枚真实 apdidToken（可选，填 env）；
3. `build_generate_request(msisdn)`；
4. 拆 `sign = sig + "." + payload`；
5. 客户端公钥验 `sig`（`GRSACipher.verify` 镜像）；
6. 服务器私钥 RSA 解 `sec.key` / `sec.initializer` → 拿回 aesKey/iv；
7. 按 `sec.enc` AES 解密，与 cleartext 比对。

七步全部通过即证明：签名字节等价（步 5）、密钥封装正确（步 6）、字段级加密与 `sec.enc` 索引一致（步 7）。

### 7.2 本次复现输出（2026-07-30）

\```
=== APDID MINT ===
apdid_prefix  eYOIkj0lHUX4/PatvP6VEP2y...
token_suffix  ...uxyznwEAAA==

=== GENERATE CLEARTEXT ===
url             https://api.mynt.xyz/c4/v2.3/otp/generate_code
cleartext_body  { msisdn: 639277040774, udid: ANDoiGQfhW4E7HFonHP1ZsFgMcRFtdoy }
enc_params      [msisdn]
scenario_id     first_time_otp
aesKey_len      32   iv_len 16   iv = p9JG_LpYItCkktgJ

=== WIRE ===
sign 总长 ~3733   sig_b64 ~344   payload_b64 ~3388
sec.enc = [request.header.X-Package-Id, request.header.X-Reg-Channel, request.body.msisdn]
body.msisdn 密文前缀 OM8Bq6ZJ/LFlBvaAQU0caw==...
body.udid   明文     ANDoiGQfhW4E7HFonHP1ZsFgMcRFtdoy
request 无 method 字段（POST → null → gson 省略）

=== X-Env-Info 解码摘录 ===
terminalType APP
appVersion   6.00.2:1213
osType       Android   channel GCASH_APP
scenario_id  first_time_otp
extendInfo.phoneModel SM-A125F
extendInfo.lbsErrorCode 1000
tokenId / dfpToken 尾缀 ...nwEAAA==

=== SERVER RECOVER ===
unsealed aesKey/iv 与本地一致
decrypted msisdn        = 639277040774
decrypted X-Package-Id  = com.globe.gcash.android
decrypted X-Reg-Channel = 16

=== VERIFY ===
sec.enc 含 request.body.msisdn + request.body.code
code 解回 423323，udid 仍明文
\```

离线单测 24 PASS / 0 FAIL。

### 7.3 从真值反推的结构图

```mermaid
flowchart TB
    subgraph clear [加密前]
      B["body {msisdn, udid}"]
      H["EncryptedHeader + Env JSON"]
      K["aesKey 32 / iv 16"]
    end
    subgraph wire [线路]
      S["sec.enc 路径清单"]
      R["RSA 封 key+iv"]
      P["gson+Base64 payload"]
      G["SHA256withRSA → sig.payload"]
      W["HTTP {sign}"]
    end
    B --> S
    H --> S
    K --> R
    B --> P
    H --> P
    R --> P
    S --> P
    P --> G --> W
\```

---

## 8. 密钥握手（联网复现）

密钥非硬编码：每台设备装机时本地生成一对 RSA-2048，再与服务器交换公钥。握手基址来自 `Configuration.getDomainV5("tc_login_key_agreement_endpoint")`，实测落在 `api.mynt.xyz`。

现网存在两个版本，`AgreementAPICallImpl` 里都有：

\```
# v1（本文实测走这条）
GET  https://api.mynt.xyz/c4/v1/key-agreement/handshake?v=2&du=<udid>
     → { pub: <服务器 RSA-2048 X509 公钥, 392 字符 b64>, flowId: <UUID>, traceId, version }
POST https://api.mynt.xyz/c4/v1/key-agreement/handshake
     body = { pub: [客户端公钥切 100 字符块, 逐块 RSA/ECB/PKCS1(serverPub)], du, flowId }
     → { code:"0", message:"Successfully saved!" }   ← 服务器保存我方客户端公钥

# v3（存在，另一形态）
POST https://api.mynt.xyz/c4/v3/key-agreement/handshake
     → ResponseAgreement{ pub, flowId, traceId }
\```

POST 中客户端公钥切成 100 字符一块、逐块用服务器公钥 RSA 封装后上传（单次 RSA/ECB/PKCS1 明文长度受限，公钥 b64 共 392 字符，需分块）。服务器保存客户端公钥后，即可验证客户端私钥签名的 WCSign，因此握手是首个业务请求的前置。

本次实测：

\```
udid        = ANDOHVotHEZBSfI1sDVfmZK7ZcmwqRHb
HANDSHAKE_OK
flowId      = 2ad9a51e-bf9e-43ac-901e-6424f4a69e47
server_pub  = MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKC...  (X509 b64, len=392)
client_pub  len=392
client_priv len=1624（不贴全文）
\```

本地 prefs 语义（`GHashConfigPrefService`）：

| prefs key | 语义 | 用在 |
|-|-|-|
| `agreement_private_key` | 客户端私钥 PKCS8 | 签 payload（`sig`） |
| `agreement_public_key` | 客户端公钥 X509 | 握手 POST 上传给服务器 |
| `agreement_api_public_key` | 服务器公钥 | 封 aesKey/iv（`sec.key`/`initializer`） |
| `agreement_api_flow_id` | 服务器下发 flowId | 头 `X-FlowId` |

触发时机：`GRSACipher.sign` 发现 `agreement_private_key` 为空时，`blockingGet` 阻塞执行握手，握手完成后再签。因此「首个请求前必有一次握手」由 lazy-init 决定，非显式编排。

---

## 9. X-Env-Info 与设备标识

注册 body 几乎只有号与 udid。设备画像在 `X-Env-Info` JSON 中（再 Base64 进 WCSign header，`X-Env-Info` 走 `m()` 即纯 Base64，不 AES——见 §5.2）。

### 9.1 完整字段（对齐 `GNetworkUtil.getMobileEnvInfo` + `d()` + `getEnvInfo(scenario)`）

`getMobileEnvInfo()` 产出的顶层 + `extendInfo`：

\```
terminalType="APP"  orderTerminalType="APP"  channel="GCASH_APP"
tokenId = apdidToken            deviceId = UTDevice.getUtdid()   ← utdid，有值就写
appVersion = "6.00.2:1213"      osType="Android"  osVersion=RELEASE
extendInfo{
  userAgent="GCash App Android"（固定注入，非 WebView UA）
  dfpToken = apdidToken
  appVersion, phoneBrand, phoneManufacturer, phoneModel,
  phoneOsVersion = "release,sdk"（如 "11,30"）,
  udid, currencyCode="PHP", referenceId=NanoId32
}
定位成功 → 顶层 latitude/longitude + extendInfo{LBSType="gps", acc, LBSUpdateTime}
定位失败 → extendInfo.lbsErrorCode = 1000（lab 抓包常见此值）
\```

然后 `d()` 会把 `MobileEnvInfo` 转成 Map，再往同一个 JSON 里塞一批镜像键——这些键塞进 `X-Env-Info` 这个 JSON 对象里，不是 HTTP 头：

\```
User-Agent, X-DFP-TOKEN(=apdidToken), X-APP-VERSION,
X-PHONE-BRAND, X-PHONE-MANUFACTURER, X-PHONE-MODEL, X-PHONE-OS-VERSION
\```

最后 `getEnvInfo(scenario)` 再补 `scenario_id`。真机样本（token 脱敏）：

```json
{
  "terminalType": "APP", "tokenId": "eTPYTWV6...REDACTED",
  "appVersion": "6.00.2:1213", "osType": "Android", "osVersion": "11",
  "orderTerminalType": "APP", "channel": "GCASH_APP",
  "extendInfo": { "phoneModel": "SM-A125F", "udid": "ANDoiGQf...",
                  "currencyCode": "PHP", "lbsErrorCode": "1000", ... },
  "deviceId": "amtK7+u7WlUDAGJU3vpuQ3gI",
  "X-DFP-TOKEN": "eTPYTWV6...oWjDuxyznwEAAA==",
  "X-PHONE-MODEL": "SM-A125F", "scenario_id": "first_time_otp"
}
\```

`deviceId: "amtK7+u7WlUDAGJU3vpuQ3gI"` 即 utdid（24 字符 Base64）——§9.3 展开其生成算法。

### 9.2 硬字段与 A/B

对齐后，OTP generate 路径的硬要求：

| 键 | 实测/要求 |
|-|-|
| `scenario_id` | `first_time_otp`（缺 → generate 系统性 `code:1`） |
| `appVersion` | `6.00.2:1213` 形态（必须带 build 号，纯 `6.00.2` 会失败） |
| `tokenId` / `extendInfo.dfpToken` | apdidToken |
| `deviceId` | utdid（smali 恒 `deviceId=getUtdid`；A/B 显示有无都能 generate `code:0`） |
| `extendInfo.udid` | 与 body/X-UDID 一致 |
| LBS | 失败路径常见 `lbsErrorCode=1000` |

A/B 思路（只改 env 一个维度，看 generate 的 `code`）已坐实：

- `scenario_id` / `appVersion` build 号是硬校验（缺则 `code:1`）；
- `deviceId` 不是「去掉就过 / 加上就失败」的开关——`deviceId=on` 与 `off` 两种变体 generate 都 `code:0`。早前「删掉 deviceId 就好」的判断有误，smali 里 `deviceId` 恒等于 utdid；
- 同一 session 第 3 次 generate → `code:2 "Retries exceeded"`（OT201421）——限流按 `udid/apdid` 身份计，不是字段问题；`pm clear` 可清本地侧计数。

### 9.3 设备身份三件套：哪些能纯离设备造

X-Env-Info 里三个 native 相关标识，逆向后可复现性差别较大，决定整条离设备链的可行性。

| 标识 | 在 env 里 | 谁生成 | 纯离设备可造？ |
|-|-|-|-|
| apdidToken | `tokenId` / `dfpToken` | libAPSE native 采集 → imgw 服务器铸 | 见 §10.1（可绕过铸） |
| umidToken | （不出现） | 客户端本地 = utdid | 可复现，但 GCash `needUmid=false` 不使用（伪线索） |
| utdid | `deviceId` | `com.ta.utdid2` 客户端算法 | 算法已知，可铸合法值 |

**umid（伪线索）**：`modules.x.o.a(ctx)` 解析链最终 fallback 到 `UTDevice.getUtdid`（即 utdid），铸造 RPC 下行无 umid 字段，且 GCash 配置 `needUmid=false` → `createStaticRequest` 里 `umidToken=""`，X-Env-Info 实测无此键。Alibaba SecurityGuard 的 `IUMIDComponent.getSecurityToken`（libsgmain）在 GCash 里 0 xref，存在但未接线。无需复现 umid。

**utdid**（`com.ta.utdid2` / `UTUtdid.a()`，18 字节 → Base64 NO_WRAP = 24 字符）：

| 字节 | 内容 |
|-|-|
| 0–3 | `currentTimeMillis()/1000`（int 大端，秒级时间戳） |
| 4–7 | `Random().nextInt()` |
| 8 | `0x03`（版本 tag） |
| 9 | `0x00` |
| 10–13 | `hashCode(IMEI)`（现代机 `getDeviceId()=null` → 退化成随机数的 hashCode） |
| 14–17 | `hashCode( Base64_NOWRAP( HmacSHA1(前 14 字节) ) )` 完整性 tag |

- HmacSHA1 固定 key（硬编码在 `com.ta.utdid2.device.c`）：`d6fc3a4a06adbde89223bvefedc24fecde188aaa9161`
- `hashCode` = Java `String.hashCode`（`h = 31h + c`，32 位溢出）
- 校验器 `c.b(String)`：长度 == 24 且字符集 `[0-9a-zA-Z=/+]`

utdid 半可复现：无法从设备确定性反推（含时间戳 + 随机），但算法已知，可铸一个结构合法、HMAC 自洽的新值（`gen_utdid()`）。持久化较顽固（跨 app、跨卸载）：`Settings.System["mqBRboGZkQPcAkyk"]`（明文）/`["dxCRMxhQkdGePGnp"]`（加密），SP `Alvin2/UTDID2`，外置 `/sdcard/.UTSystemConfig/Global/Alvin2`、`/sdcard/.DataStorage/ContextData`——任一命中就回填其余。更换 utdid 需清除上述全部位置，否则仅清 app 数据无效。

小结：三者中 umid 无关、utdid 可铸，唯一硬缺口为 apdidToken，下一节展开。

---

## 10. 两个误导性信号：apdid 白盒与 key:null

### 10.1 apdid 是否必须复现 getColorInfo 白盒

早期 unidbg 路线卡在 `PARAM_ERROR`，形态上类似未跑通 16 字节 getColorInfo VM 白盒信封。要判断它是否为硬门槛，先逆清 App 原本铸 apdid 的整条 native 链（jadx 看 `com.alipay.alipaysecuritysdk.*`、ghidra/strings 看 `libAPSE_9.0.2.so`），再与「离设备直铸」对照。

#### 10.1.1 APSE 采集层结构（对照）

**入口与配置**（`com.gcash.iap.apsecurity.AntApSecurityServiceImpl`，Kotlin，基本没混淆）：

```java
APP_NAME  = "GCash"
BIZ_TOKEN = "XNRt6WZc/5sZ038Ox3Q2fyX/"            // APSE appKey
Configuration{ gateway = "https://iclientgw-sea.alipay.com/imgw.htm",
               envMode  = 0 (ONLINE),
               needUmid = false,                  // ← GCash 不取 umid（§9.3）
               secret   = "1" (wbType) }
inputParams = { tid: DeviceUtils.getDeviceId(ctx), utdid: UTDevice.getUtdid(ctx) }
APSecuritySdk.init(ctx, "GCash", BIZ_TOKEN); APDID.initToken("GCash", inputParams, cb)
getToken() = APDID.getTokenResult("GCash").apdidToken     // ← 注册 X-Env-Info 用的就是它
\```

**铸造流水线**（`ApdidManager`）：

\```
baseInitToken → doFirst → createStaticRequest → RPCService.updateStaticData → doResponse → saveToStorage
     env 变清缓存        组上行(采集+双封装)         mgw 铸造 RPC              回填服务器铸的 apdid/token
\```

**`dataMap` 字段族**（`createStaticRequest` 组包，采集面主体；离设备直铸时将其替换为一个随机 `default`）：

| 组 | 内容（节选） |
|-|-|
| AD（硬件指纹） | `AD211` = native 采集加密 blob `ed`，`AD212` = `{ck, vk:ek}`；`AD1..AD34` 由 native `h.b(ctx)` 填 |
| AE（Build/环境） | AE1=android, AE2=root/模拟器 flag, AE4=BOARD, AE5=BRAND, AE6=DEVICE, AE8=INCREMENTAL, AE9=MANUFACTURER, AE10=MODEL, AE11=PRODUCT, AE12=VERSION.RELEASE, AE13=VERSION.SDK, AE15=`ro.kernel.qemu`, AE20=native prop, AE21=/proc/cpuinfo 首行 |
| AC（身份） | AC1=tid, AC2=utdid, AC5=userId, AC10=sessionId, AC14=encodeUmid |
| AA（App/SDK） | AA1=包名, AA3=APPSecuritySDK-OVERSEA, AA4=P9.0.2.20250905 |

**谁在 Java、谁在 native**（区分「改机盖得到」与「盖不到」）：

- Java 侧实读：`TelephonyManager.getDeviceId()`(IMEI)、`Settings.Secure.android_id`、`WifiManager.getBSSID()`、`getInstalledPackages(64)`（装机列表）；
- Java 不读、若采则在 native：IMSI、SIM serial、`getMacAddress`、BOOTLOADER——这些在 `libAPSE` 里采，Java hook 看不到；
- `Configuration.secret != null` 时整张 `dataMap` 再过 `JNIBridge.aesEncrypt` native 加密 → `{default:<enc>, wbType:secret}`。这即离设备直铸中 `default` 字段的来历。

**native JNI 面**（`libAPSE_9.0.2.so`，`ApdidJNIBridge`）：

\```
initCollect / getCollectInfo / getCrashInfo / isCrashBefore / decryptConfig /
getDynData / getAA13 / getAD102 / getAD104 / getAD108 / getAE20 / getNativeProp
\```

硬件指纹计算、`ed/ek` 加密、`dataMap` 的 AES 封装均在此，Java 层不可见——这是「必须复现白盒」这一判断的来源。

**落库**：`saveToStorage` 把服务器铸的 token 写进 SharedPreferences 文件 `openapi_file_pri` / key `openApiGCash`（加密）；相关 `vkeyid_profiles_v4`（dynamic_key）、`last_apdid_env`、native crash-guard `filesDir/sc_edge`。之后 `getToken()` 都从这里取缓存，不重算。

该链完整时，「apdid 不可离设备铸造」看似成立：native 采集 + 双重加密 + mgw 签名 RPC + 服务器铸，共四道门。但下述删减实验将其推翻。

#### 10.1.2 铸造端点不校验白盒

对铸造端点做输入删减：

\```
POST https://iclientgw-sea.alipay.com/imgw.htm
operationType=alipay.security.deviceFingerPrint.staticData.report.v2
requestData=[{ "apdid":"", "os":"android", "dataMap":{"wbType":"1","default":<任意 base64>} }]
\```

- `requestData` 带上 `os:"android"` 即 `resultCode=SUCCESS`；`bizData` 垃圾/缺省/截断都行，`default` 填随机 600 字节也行。
- `PARAM_ERROR` 根因是缺 `os` 字段，而非白盒未复现。该 2940 字节 VM 字节码 / 16 字节 getColorInfo 信封与铸造成败无关（伪线索）。
- 铸出的两个值来源不同：`apdid` = 确定性 `f(dataMap.default)`（改 `default` → 换新 apdid，用于 OTP 限流时轮换设备身份），`token` = 服务器每次现发。

本次 mint 形态：`apdid` 头 `eYOIk…`，`token` 尾 `nwEAAA==`（与真机 harvest 一致）。一次 HTTP POST 铸一份，约几百毫秒，替代了在真机上 hook `getToken` 收割的方式。

>
> 方法：对一个看似必须逆向的 native 白盒，通过在铸造端点做输入删减 A/B（逐字段删除、观察服务器响应）即可判定其是否被校验，无需逆向 VM 字节码。
>
>
>

### 10.2 verify 回包 `key:null`

历史实网会话 `F6C07A5E`（profile vivo 1806 / Android 10）：

| 步 | HTTP | 响应体（业务字段） |
|-|-|-|
| generate | 201 | `{"code":0,"success":true}` |
| verify | 201 | `{"code":0,"key":null,"message":"Something went wrong."}` |
| isGcashRegistered | 200 | `code=13301, exist=false, status=0, statusStr=Not Registered` |

`key:null` + `"Something went wrong."` 形态上类似被风控拦截。以下对照数据逐一排除该假设：

**① 同形态在相反状态下逐字段一致** → 不携带状态信息：

| 号码 | verify 回包 | 紧接 isGcashRegistered |
|-|-|-|
| 全新号 status:0 | `code:0, key:null, "Something went wrong."` | `200 {code:"13301", exist:false, "Not Registered"}` |
| 已注册号 status:3 | `code:0, key:null, "Something went wrong."` | `200 {code:"13300", exist:true, "Active"}` |

`key:null` 在未注册与已注册下出现且完全一致 → 不可能是「拦截/放行」信号。

**② 错码对照**证明真 OTP 路径已过 OTP 比对：

| verify 输入 | 回包 |
|-|-|
| 错 OTP `000000`/`123456` | `422 code:1011 "Your OTP is invalid." / "Invalid authentication code."` |
| 真 OTP | `201 code:0 key:null` |

若为签名/加密错误，错码与真码应同样在验签前失败；实际错码走到了业务层的 OTP 比对（1011），真码过了比对（code:0），说明加密签名层正确。

**③ 反证「拦截说」**：`key:null` 的 verify 之后，`isGcashRegistered` 立刻回 `200` + 可导航业务体。若 verify 被风控拦，下一跳应是 `403 {code:143}`（该形态确实复现过——即「没有前置 verify 就裸调 isGcashRegistered」，补上 verify 即 200），而非业务体。

**④ 换真机铸造 token 仍 key:null**：A/B 过「离设备空壳 mint 的 apdid」与「Pixel6 真机跑完整 getColorInfo 白盒铸的 token」，两者 verify 都是 key:null，排除「token 太水被拦」。

**⑤ jadx 坐实**：`SuccessVerifyBody` 只有 `key` 一个字段；新注册 UI 的成功 handler（`g1`）不读 key。`"Something went wrong."` 同时是客户端本地 `OtpCodeUtilImp.GENERIC_HEADER` 文案，服务端也回了同句——文案表示失败，字段表示成功。

| 假说 | 证据 | 结论 |
|-|-|-|
| 签名/加密错 | generate 发真 OTP；错码 1011 走到业务层 | 否 |
| key:null = 业务拒会话 | 下一跳 isreg 仍 200 业务体 | 否 |
| key:null = 未注册特有 | 已注册号同样 key:null | 否 |
| apdid 太水被拦 | 真机白盒 token 同样 key:null | 否 |
| 成功判据 | `code:0`；新注册 UI 不读 `key`（jadx） | 是 |

结论：验码成功判据为 `code:0`（`OtpAccepted`），`key:null` 是与成功并存的噪声。「号源信誉 / 设备图谱 / KYC 挂起」等假设不成立：虚拟号 + 离设备铸 apdid 即可完整通过 `generate → verify(code:0) → isGcashRegistered(200 可导航体)`。

---

## 11. register 终段：组包正确性与 RTS 风控

OTP 闭环之后，注册协议还有最后一跳 `register`（将 PII + MPIN + apdidToken 打包建号）。该步骤用于验证组包字节级正确性：服务器需完成解密、执行 register 业务逻辑并返回结构化 KYC 信封，方可确认整套 WCSign（header / body / sec.enc）正确。

端点 `c4/v3.4/gcash/register`（`GcashRegistrationApiService.register`，`@Body WCSign`），header 走 `RegistrationDataSourceImpl.getHeader()`（只有 `Content-Type / X-UDID / X-FlowId / X-Env-Info / X-Reg-Channel`，无 Package/Time/Tracker），env 走 `getEnvInfo()`（不带 scenario_id，但 Map 里补一个 `X-UDID` 键）。body 19 个加密字段：

\```
encParams(19) = [msisdn, firstName, lastName, email, dateOfBirth, address, tokenId, mpin,
                 caCountry, caProvince, caTown, caZipcode, paCountry, paStreet, paProvince,
                 paTown, paZipcode, nationality, mainSourceOfFunds]
\```

明文 body 里还有 `referralCode`、`version="1213"`、`rdsData`、`termsAndConditions="true"`（后两者明文，不进加密集），`udid` 键置 null（gson 省略，服务器读 `X-UDID` 头）。`caZipcode/paZipcode` 是小写 c——这类「1213 版精确键名」错一个字母服务器就当缺字段。

### 11.1 `rdsData`：一个易错点

明文 body 里的 `rds_data` 易被想当然填成非空。但 jadx 确认：注册期 `PinEnhancePresenter.h()` 将 `rdsData` 硬编码为空串，注册链路不执行 `RDSClient/zipAndEncryptData`（`setRdsData` 0 xref）。影响：

- `rdsData` 明文进 RSA 签名 payload。填非空 → 本地 payload 字节与真机不一致 → `422 code:400 "Invalid Signature Key: Failed verification at prehandling"`（验签在 prehandling 阶段失败）；
- 填空串才是真机字节，过 crypto prehandling → 进业务层。

这印证 §6.3：此处的错误是多填 `rdsData` 导致签名字节不等价，而非少填。

### 11.2 RTS 风控与「组包已对」的判据

过了 prehandling 之后是业务风控：

| register 回包 | 含义 |
|-|-|
| `422 code:400 Failed verification at prehandling` | 签名字节不等价（组包错，回 §6 查） |
| `422 code:13300`（对已注册号强发） | 正常业务信封——服务端解析并跑了 register，只因该号已有账号而拒 → 证明组包正确 |
| `13449` | RTS 风控 risk-decline（与真机低信任设备同 class），组包对、身份可疑 |
| `200 code:0 "User Successfully Registered"` | 建号成功，返回 KYC 信封 |

13449 按设备指纹速度累计（`deviceThreshold / maxDevicePreCom`）：复用同一枚陈旧 apdid 或同一份 PII 会累计风险值。对应处理是每个身份现铸 fresh apdid（§10.1，清 device velocity）+ fresh 合成菲律宾 PII（避免 PII velocity）。成功样本：

```json
"register": { "http": 200, "body": {
  "KYCDetails": { "applicationStage":"FOR CREATION", "applicationStatus":"APPROVED",
                  "firstName":"PEDRO", "lastName":"GAMBOA", "nationality":"FILIPINO",
                  "registrationChannel":"APP_REGISTRATION", ... },
  "KYCLevel":"1", "code":0, "message":"User Successfully Registered",
  "transactionID":"5f561d74698dc62e9adcef77174da47f" } }
\```

至此判据满足：纯离设备（无真机、无 frida）跑通 `handshake → generate → verify(code:0) → isGcashRegistered → register(code:0 KYC APPROVED)`，整套 WCSign 组包字节级正确，服务器全程接受。register 段在此仅用作协议正确性证据，不展开为建号工具。

---

## 12. 进程内明文抓取点

### 12.1 打点

```java
// 伪代码
hookAllMethods(RequestEncryption, "generateSignedBody", before → {
    // ⚠️ 必须 before：方法内 d() 会就地 AES/Base64 改写 header
    // args[0] EncryptedHeader 明文（含 X-Env-Info 原文）
    // args[1] body 明文 {msisdn,udid[,code]}
    // args[2] encParams
}, after → {
    // result  WCSign(sign, aesKey, iv)
});
hookAllMethods(RequestEncryption, "decryptRequest", after → log(result));
// 密钥：GHashConfigPrefService.getApiPublicKey / getPrivateKey / getApiFlowId
// 辅助：GRSACipher.sign/encrypt、AntApSecurityServiceImpl.getToken、UTDevice.getUtdid
\```

真机冷启动 log（钩子就绪，尚未进 OTP UI）：

\```
[GCash-rpc]  proxy-discovery armed
[GCash-http] hooked okhttp3…RealCall.getResponseWithInterceptorChain
[GCash-dynsec] hooked generateSignedBody
[GCash-dynsec] hooked GRSACipher sign/encrypt
[GCash-dynsec] hooked getToken
installed … rpc=true
\```

`generateSignedBody` 的 BODY/HEADER 日志要等注册发码/验码真正组包才出现；冷启动只先打指纹 RPC（§3.2）和配置 RPC。一处 `generateSignedBody` 即注册协议明文全集。真机实抓到的 generate BODY（6.01.0）：`{"msisdn":"0955…","udid":"ANDxdAv…"}`，`scenario_id=first_time_otp`，`appVersion=6.01.0:1216`，`X-FlowId=95a81226-…`，与离线 oracle 组的包结构逐字段吻合。

### 12.2 为什么选 dex 层打点

GCash 存在 native 完整性自校，通用 Dobby/inline hook 会触发崩溃：

- 现象：点输入 / Next 后约 2–4s 死，`main gone status=11`；
- 根因：`libgcash_sc.so` 在线程 `gcash-sc-load` 的 `phdr_cb` 触发 SIGSEGV——它遍历自己的 program header 做 `.so` CRC 自校，Dobby 改了目标 `.text` 即被检出；
- 另一处：早期 seccomp 用 `SECCOMP_RET_ERRNO|EPERM` 拦 `exit/exit_group`，触发 `ApplicationExitInfo SIGILL status=4`。

处理（保活栈，非本文重点，简述）：删除 `code_cache` 与 `/data/local/tmp` 下的坏 `libgcash_sc.so`，seccomp 改 `RET_TRACE`（plain `exit(93)` 放行），配 `ptrace guard` 持续 `FREEZE exit_group`，`vmtrace` 关闭（Dobby 挂 libAPSE 会触发 CRC）。处理后 OtpMsisdnActivity 存活 ≥25–35s，主 pid 稳定。

`generateSignedBody` 位于 dex/ART 层，不落入被 CRC 自校的 native `.text`，因此 Java 层 hook 既可获取完整明文，又不触发 libgcash_sc / libAPSE 的完整性检查。

---

## 13. 最终效果

完成了脱机注册协议的复现：无真机、无 Frida，纯 Python 跑通握手 → 发码 → 验码 → 查号 → 建号，实网建号成功。

---

## 14. 附录：关键类（6.00.2）

\```
# 注册协议主链
gcash.common_data.source.otp.OtpRepositoryImpl
gcash.common.android.network.api.service.GKApiServiceDynamicSecurity
gcash.common.android.util.encryption.RequestEncryption
gcash.common.android.util.agreement.GAESCipher
gcash.common.android.util.agreement.GRSACipher
gcash.common.android.util.agreement.AgreementAPICallImpl
gcash.common.android.model.encryption.WCSign / WCEncrypt / EncryptedHeader / EncryptedSecurity
gcash.common.android.util.GNetworkUtil                       # getMobileEnvInfo / d / getEnvInfo
gcash.common.android.pref.GHashConfigPrefService             # 握手密钥 prefs

# 建号 / 查号
（Gcash）RegistrationDataSourceImpl / GcashRegistrationApiService   # c4/v3.4/gcash/register
（Gcash）IsGcashRegisteredUseCase                                   # isGcashRegistered 查号
gcash.common.android.util.OtpCodeUtilImp                           # GENERIC_HEADER

# native 标识
com.gcash.iap.apsecurity.AntApSecurityServiceImpl                 # getToken()=apdidToken
com.alipay.alipaysecuritysdk.apdid.manager.ApdidManager           # 铸造/缓存
ApdidJNIBridge（libAPSE_9.0.2.so）                                 # initCollect/getCollectInfo
com.ta.utdid2 / com.ut.device.UTDevice（UTUtdid.a）                # utdid 生成
\```

---

# 回复

## 回复 by mb_jnmxfjku (#2)

666

## 回复 by mb_ldbucrik (#3)

感谢分享

## 回复 by AK1988DA (#4)

444

## 回复 by Imxz (#5)

kkb

## 回复 by manyuegong33 (#6)

11

## 回复 by k4y0z (#7)

666

## 回复 by mb_gjhmacqd (#8)

666

## 回复 by mb_goqnmbff (#9)

666

## 回复 by 葱葱油油 (#10)

666

## 回复 by Kazusa (#11)

66
