---
title: '[原创]Android TEE 密钥认证证书数据结构学习笔记'
url: https://bbs.kanxue.com/thread-289742.htm
tid: 289742
author: 简单的简单
date: '2026-01-13'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T13:57:44+08:00'
replies: 8
---

## 前言

## 项目链接

https://github.com/lxz-jiandan/AndroidTeeCertParse (C++解析 + 010Editor模板)

## 概述

### 什么是 TEE 密钥认证证书？

TEE（Trusted Execution Environment，可信执行环境）密钥认证证书是 Android 设备用于证明密钥安全性的数字证书。它基于 X.509 标准，但包含了 Android Keymaster 特有的扩展信息，用于验证：

- 密钥的生成环境（软件/TEE/StrongBox）
- 设备的启动验证状态
- 系统版本和安全补丁级别
- 密钥的使用限制和属性
- 设备的硬件安全特性

### 证书的作用

1. **密钥来源验证**：证明密钥是在安全环境中生成的
2. **设备完整性验证**：验证设备启动状态和系统版本
3. **安全策略执行**：确保密钥使用符合安全要求
4. **防篡改保护**：通过数字签名确保证书内容不可伪造

---

## 整体架构

### 层次结构

| 12345678910111213141516171819202122232425262728293031 | `X.``509` `Certificate (根证书)``├── TBSCertificate (待签名证书)``│   ├── Version (证书版本)``│   ├── Serial Number (序列号)``│   ├── Signature Algorithm (签名算法)``│   ├── Issuer (颁发者)``│   ├── Validity (有效期)``│   ├── Subject (主题)``│   ├── Subject Public Key Info (公钥信息)``│   └── Extensions [``3``] (扩展)``│       └── TEE Attestation Extension (TEE认证扩展)``│           ├── OID:` `1.3``.``6.1``.``4.1``.``11129.2``.``1.17``│           └── Attestation Record (认证记录)``│               ├── Attestation Version (认证版本)``│               ├── Security Level (安全级别)``│               ├── Keymaster Version (Keymaster版本)``│               ├── Keymaster Security Level (Keymaster安全级别)``│               ├── Attestation Challenge (认证挑战)``│               ├── Unique` `ID` `(可选，设备唯一``ID``)``│               ├── Software Enforced (软件强制属性)``│               └── TEE Enforced (TEE强制属性)``│                   └── Authorization` `List` `(授权列表)``│                       ├── Context[``701``]: Creation DateTime (创建时间)``│                       ├── Context[``704``]: Root of Trust (信任根)``│                       ├── Context[``705``]: OS Version (系统版本)``│                       ├── Context[``706``]: OS Patch Level (系统补丁级别)``│                       ├── Context[``718``]: Vendor Patch Level (厂商补丁级别)``│                       ├── Context[``719``]: Boot Patch Level (启动补丁级别)``│                       └── Context[``709``]: Attestation Application` `ID` `(认证应用``ID``)``├── Signature Algorithm (签名算法)``└── Signature Value (签名值)` |
|-|-|

### 数据流向

1. **证书生成**：TEE 环境根据密钥属性和设备状态生成认证记录
2. **扩展嵌入**：将认证记录作为 X.509 扩展嵌入证书
3. **签名**：使用设备私钥对证书进行签名
4. **验证**：客户端验证证书签名和扩展内容

---

## X.509 证书基础结构

### TBSCertificate（待签名证书）

TBSCertificate 是证书的核心部分，包含所有需要签名的信息：

#### 1. Version（版本）

- **位置**：Context[0]，可选字段
- **值**：0=v1, 1=v2, 2=v3
- **说明**：TEE 证书通常为 v3，支持扩展

#### 2. Serial Number（序列号）

- **类型**：INTEGER
- **说明**：证书颁发者分配的唯一序列号，用于标识证书

#### 3. Signature Algorithm（签名算法）

- **类型**：SEQUENCE
- **内容**：算法 OID + 参数
- **常见算法**：SHA256withRSA, SHA512withRSA, ECDSA

#### 4. Issuer（颁发者）

- **类型**：SEQUENCE of RelativeDistinguishedName
- **说明**：证书颁发者的可分辨名称（DN）
- **示例**：CN=Android, O=Android, C=US

#### 5. Validity（有效期）

- **类型**：SEQUENCE
- **内容**：
	- notBefore：证书生效时间（UTC 或 GeneralizedTime）
	- notAfter：证书过期时间

#### 6. Subject（主题）

- **类型**：SEQUENCE of RelativeDistinguishedName
- **说明**：证书持有者的可分辨名称
- **注意**：TEE 证书中，Subject 通常与 Issuer 相同（自签名）

#### 7. Subject Public Key Info（公钥信息）

- **类型**：SEQUENCE
- **内容**：
	- Algorithm：公钥算法标识符（RSA/EC）
	- SubjectPublicKey：公钥值（BIT STRING）

#### 8. Extensions（扩展）

- **位置**：Context[3]（标签 0xA3）
- **类型**：SEQUENCE of Extension
- **说明**：包含 TEE 认证扩展和其他标准扩展

---

## TEE 扩展结构

### Extension 结构

每个扩展包含三个部分：

| 12345 | `Extension ::``=` `SEQUENCE {``extnID` `OBJECT` `IDENTIFIER,` `-``-` `扩展OID``critical    BOOLEAN DEFAULT FALSE,` `-``-` `关键标志（可选）``extnValue    OCTET STRING` `-``-` `扩展值``}` |
|-|-|

### TEE Attestation Extension

- **OID**：`1.3.6.1.4.1.11129.2.1.17`
- **编码**：`2B 06 01 04 01 D6 79 02 01 11`
- **Critical**：通常为 TRUE（0xFF）
- **extnValue**：包含完整的 Attestation Record（OCTET STRING 包装）

### 扩展值解析流程

1. 读取扩展 SEQUENCE
2. 查找 TEE OID（通过字节匹配）
3. 定位到扩展值 OCTET STRING
4. 解析内部的 Attestation Record

---

## 认证记录结构

### Attestation Record 字段

认证记录是 TEE 证书的核心数据，采用 SEQUENCE 结构：

#### 1. Attestation Version（认证版本）

- **类型**：INTEGER
- **值**：
	- 100：Keymaster v1
	- 200：Keymaster v2
	- 300：Keymaster v3
	- 400：Keymaster v4

#### 2. Attestation Security Level（认证安全级别）

- **类型**：ENUMERATED
- **值**：
	- 0：Software（软件级别）
	- 1：TEE（可信执行环境）
	- 2：StrongBox（独立硬件安全模块）

#### 3. Keymaster Version（Keymaster 版本）

- **类型**：INTEGER
- **说明**：Keymaster HAL 版本号（如 4 表示 Keymaster 4.0）

#### 4. Keymaster Security Level（Keymaster 安全级别）

- **类型**：ENUMERATED
- **说明**：与 Attestation Security Level 相同，表示 Keymaster 实现的安全级别

#### 5. Attestation Challenge（认证挑战）

- **类型**：OCTET STRING
- **说明**：客户端提供的随机数（nonce），用于防止重放攻击
- **长度**：通常 16-32 字节

#### 6. Unique ID（设备唯一ID，可选）

- **类型**：OCTET STRING
- **说明**：设备的唯一标识符，用于设备识别

#### 7. Software Enforced（软件强制属性）

- **类型**：AUTHORIZATION_LIST（SEQUENCE）
- **说明**：由 Android 系统强制执行的密钥属性
- **内容**：各种 Keymaster 标签，如密钥用途、算法等

#### 8. TEE Enforced（TEE 强制属性）

- **类型**：AUTHORIZATION_LIST（SEQUENCE）
- **说明**：由 TEE 环境强制执行的密钥属性，包含设备安全状态信息
- **关键内容**：
	- Root of Trust（信任根）
	- OS Version（系统版本）
	- Patch Levels（补丁级别）
	- Creation DateTime（创建时间）
	- Attestation Application ID（认证应用ID）

---

## 授权列表结构

### Authorization List 概述

授权列表是一个 SEQUENCE，包含多个 Keymaster 标签。每个标签使用 Context 标签号标识，格式为：

| 123 | `[CONTEXT tag_number] CONSTRUCTED {``-``-` `标签内容``}` |
|-|-|

### 标签编码规则

- **标签号 < 31**：单字节编码，格式为 `0xA0 | tag_number`
- **标签号 >= 31**：多字节编码（扩展标签号）
	- 第一个字节：`0xBF`（Context 类别，扩展标志）
	- 后续字节：标签号的高 7 位编码（BER 编码）

### 扩展标签号示例

- **701**：`BF 85 3D`（创建时间）
- **704**：`BF 85 40`（信任根）
- **705**：`BF 85 41`（系统版本）
- **706**：`BF 85 42`（系统补丁级别）
- **718**：`BF 85 66`（厂商补丁级别）
- **719**：`BF 85 67`（启动补丁级别）
- **709**：`BF 85 45`（认证应用ID）

---

## 关键数据结构详解

### 1. Root of Trust（信任根）

信任根是设备安全的基础，包含：

| 123456 | `RootOfTrust ::``=` `SEQUENCE {``verifiedBootKey    OCTET STRING,` `-``-` `已验证启动密钥（SHA``-``256``）``deviceLocked       BOOLEAN,` `-``-` `设备锁定状态（``0xFF``=``锁定）``verifiedBootState  ENUMERATED,` `-``-` `启动验证状态``verifiedBootHash   OCTET STRING OPTIONAL` `-``-` `启动镜像哈希（可选）``}` |
|-|-|

#### 字段说明

- **verifiedBootKey**：启动验证密钥的 SHA-256 哈希值，用于验证启动镜像完整性
- **deviceLocked**：
	- `0xFF`：设备已锁定（安全状态）
	- `0x00`：设备未锁定（可能不安全）
- **verifiedBootState**：
	- `0`：Verified（已验证）
	- `1`：Self-Signed（自签名）
	- `2`：Unverified（未验证）
	- `3`：Failed（验证失败）

### 2. OS Version（系统版本）

- **标签**：Context[705]
- **类型**：INTEGER
- **编码规则**：`OS_VERSION = (major * 10000) + (minor * 100) + patch`
- **示例**：
	- `130000` → Android 13.0.0
	- `120000` → Android 12.0.0

### 3. OS Patch Level（系统补丁级别）

- **标签**：Context[706]
- **类型**：INTEGER
- **格式**：YYYYMM（6 位数字）
- **示例**：`202305` → 2023年5月

### 4. Vendor Patch Level（厂商补丁级别）

- **标签**：Context[718]
- **类型**：INTEGER
- **格式**：YYYYMMDD（8 位数字）
- **示例**：`20230515` → 2023年5月15日

### 5. Boot Patch Level（启动补丁级别）

- **标签**：Context[719]
- **类型**：INTEGER
- **格式**：YYYYMMDD（8 位数字）
- **说明**：启动镜像的安全补丁级别

### 6. Creation DateTime（创建时间）

- **标签**：Context[701]
- **类型**：INTEGER
- **格式**：毫秒级 Unix 时间戳
- **说明**：密钥创建时间，可用于推断设备重置时间
- **示例**：`0x019B8C644101` → 2023-05-15 10:30:00.001 UTC

### 7. Attestation Application ID（认证应用ID）

- **标签**：Context[709] 或 Application[99]
- **类型**：SEQUENCE
- **结构**：

| 123456789 | `AttestationApplicationId ::``=` `SEQUENCE {``packageInfos` `SET` `OF AttestationPackageInfo,``signatureDigests` `SET` `OF OCTET STRING``}` `AttestationPackageInfo ::``=` `SEQUENCE {``packageName  OCTET STRING,` `-``-` `应用包名（UTF``-``8``）``version      INTEGER` `-``-` `版本号（versionCode）``}` |
|-|-|

#### 字段说明

- **packageInfos**：应用包信息集合
	- packageName：应用包名（如 `com.example.app`）
	- version：应用版本代码（versionCode）
- **signatureDigests**：APK 签名证书的 SHA-256 摘要集合
	- 用于验证应用身份和完整性
	- TEE 侧不可伪造

#### 解析注意事项

1. **SET OF 顺序**：SET 是无序集合，packageInfos 和 signatureDigests 的顺序不保证
2. **外层包装**：可能被 OCTET STRING 包装
3. **标签形式**：
	- Application[99] PRIMITIVE：直接包含编码数据
	- Context[709] CONSTRUCTED：包含 OCTET STRING，其内容为 AttestationApplicationId

---

## ASN.1 编码规则

### 基本概念

ASN.1（Abstract Syntax Notation One）是一种数据编码标准，用于定义和编码数据结构。

### 标签结构

每个 ASN.1 标签包含：

| 1 | `标签字节` `=` `[类别(``2``位)][构造标志(``1``位)][标签号(``5``位)]` |
|-|-|

- **类别**（高 2 位）：

	- `00`：Universal（通用）
	- `01`：Application（应用）
	- `10`：Context（上下文）
	- `11`：Private（私有）
- **构造标志**（第 6 位）：

	- `0`：Primitive（基本类型）
	- `1`：Constructed（构造类型）
- **标签号**（低 5 位）：

	- 0-30：单字节编码
	- 31+：多字节扩展编码

### 长度编码

ASN.1 长度有两种格式：

#### 短格式（长度 < 128）

| 1 | `长度字节` `=` `0xxxxxxx``（直接编码长度值）` |
|-|-|

#### 长格式（长度 >= 128）

| 12 | `第一个字节` `=` `1xxxxxxx``（低``7``位表示后续长度字节数）``后续字节` `=` `实际长度值（大端序）` |
|-|-|

**示例**：

- 长度 5：`05`
- 长度 200：`81 C8`（1 字节长度，值为 200）
- 长度 1000：`82 03 E8`（2 字节长度，值为 1000）

### 常用标签

| 标签值 | 类型 | 说明 |
|-|-|-|
| 0x01 | BOOLEAN | 布尔值 |
| 0x02 | INTEGER | 整数 |
| 0x03 | BIT STRING | 位串 |
| 0x04 | OCTET STRING | 字节串 |
| 0x05 | NULL | 空值 |
| 0x06 | OBJECT IDENTIFIER | 对象标识符 |
| 0x0A | ENUMERATED | 枚举值 |
| 0x0C | UTF8String | UTF-8 字符串 |
| 0x13 | PrintableString | 可打印字符串 |
| 0x16 | IA5String | IA5 字符串 |
| 0x17 | UTCTime | UTC 时间 |
| 0x18 | GeneralizedTime | 通用时间 |
| 0x30 | SEQUENCE | 有序序列 |
| 0x31 | SET | 无序集合 |
| 0xA0-0xBF | Context[0-31] | 上下文标签 |

### 扩展标签号编码

当标签号 >= 31 时，使用多字节编码：

1. 第一个字节：`0x1F`（表示扩展标签号）
2. 后续字节：标签号的 BER 编码
	- 每个字节的最高位：`1` 表示还有后续字节，`0` 表示最后一个字节
	- 低 7 位：标签号的一部分

**示例**：标签号 701

- 701 = 0x02BD = `0000 0010 1011 1101`
- 编码：`BF 85 3D`
	- `BF` = `1011 1111`（Context 类别，扩展标志）
	- `85` = `1000 0101`（还有后续字节，值为 5）
	- `3D` = `0011 1101`（最后一个字节，值为 61）
	- 计算：5 << 7 | 61 = 640 + 61 = 701

---

## Keymaster 标签系统

### 标签分类

Keymaster 标签用于标识密钥属性和认证信息，分为以下几类：

#### 1. 密钥属性标签（1-100）

- **KM_TAG_PURPOSE (1)**：密钥用途（加密/签名/验证等）
- **KM_TAG_ALGORITHM (2)**：加密算法（RSA/EC/AES等）
- **KM_TAG_KEY_SIZE (3)**：密钥大小（位数）
- **KM_TAG_DIGEST (5)**：摘要算法（SHA256/SHA512等）
- **KM_TAG_PADDING (6)**：填充模式（PKCS7/OAEP/PSS等）
- **KM_TAG_EC_CURVE (10)**：椭圆曲线类型（P-256/P-384等）

#### 2. 设备信息标签（700-724）

- **KM_TAG_ORIGIN (702)**：密钥来源（生成/导入/派生）
- **KM_TAG_ROOT_OF_TRUST (704)**：信任根
- **KM_TAG_OS_VERSION (705)**：操作系统版本号
- **KM_TAG_OS_PATCHLEVEL (706)**：系统安全补丁级别
- **KM_TAG_VENDOR_PATCHLEVEL (718)**：厂商补丁级别
- **KM_TAG_BOOT_PATCHLEVEL (719)**：启动镜像补丁级别

#### 3. 设备标识标签（710-717）

- **KM_TAG_ATTESTATION_ID_BRAND (710)**：设备品牌
- **KM_TAG_ATTESTATION_ID_DEVICE (711)**：设备型号代码
- **KM_TAG_ATTESTATION_ID_PRODUCT (712)**：产品名称
- **KM_TAG_ATTESTATION_ID_SERIAL (713)**：设备序列号
- **KM_TAG_ATTESTATION_ID_IMEI (714)**：IMEI号
- **KM_TAG_ATTESTATION_ID_MANUFACTURER (716)**：制造商名称
- **KM_TAG_ATTESTATION_ID_MODEL (717)**：设备型号名称

#### 4. 应用认证标签（709）

- **KM_TAG_ATTESTATION_APPLICATION_ID (709)**：认证应用ID

### 标签编码方式

Keymaster 标签在 ASN.1 中使用 Context 标签编码：

- **标签号 < 31**：`0xA0 | tag_number`
- **标签号 >= 31**：扩展标签号编码（如上述 701、705 等）

---

## 安全机制与应用场景

### 安全机制

#### 1. 数字签名

- 证书使用设备私钥签名，确保内容不可篡改
- 客户端使用设备公钥验证签名

#### 2. 信任根验证

- 验证启动密钥确保启动镜像完整性
- 设备锁定状态确保密钥安全存储

#### 3. 版本控制

- 系统版本和补丁级别用于评估设备安全性
- 防止使用过时或不安全的系统版本

#### 4. 应用身份验证

- Attestation Application ID 确保密钥只能被指定应用使用
- 签名摘要防止应用被篡改

### 应用场景

#### 1. 密钥认证

- 应用请求密钥认证，获取包含设备安全状态的证书
- 服务器验证证书，评估设备安全性

#### 2. 设备完整性验证

- 通过 Root of Trust 验证设备启动状态
- 通过补丁级别验证系统安全性

#### 3. 密钥绑定

- 通过 Attestation Application ID 将密钥绑定到特定应用
- 防止密钥被其他应用滥用

#### 4. 安全策略执行

- 根据设备安全状态决定是否允许操作
- 根据系统版本和补丁级别评估风险

### 验证流程

1. **证书解析**：解析 X.509 证书结构
2. **扩展提取**：提取 TEE 认证扩展
3. **记录解析**：解析认证记录内容
4. **签名验证**：验证证书数字签名
5. **内容验证**：
	- 验证 Challenge 匹配
	- 验证应用 ID 匹配
	- 验证设备安全状态
	- 验证系统版本和补丁级别
6. **决策**：根据验证结果决定是否允许操作

---

## 总结

### 关键要点

1. **层次结构**：TEE 证书是标准的 X.509 证书，包含 TEE 特有的扩展
2. **编码格式**：使用 ASN.1 DER 编码，需要理解标签和长度编码规则
3. **标签系统**：Keymaster 标签使用 Context 标签编码，标签号 >= 31 需要扩展编码
4. **安全信息**：信任根、系统版本、补丁级别等关键信息在 TEE Enforced 授权列表中
5. **应用绑定**：Attestation Application ID 将密钥绑定到特定应用

### 学习建议

1. **理解 ASN.1**：掌握 ASN.1 编码规则是解析证书的基础
2. **实践解析**：使用 010 Editor 或类似工具实际解析证书文件
3. **对比分析**：对比不同设备的证书，理解字段差异
4. **安全评估**：理解各字段的安全含义，能够评估设备安全性

### 参考资料

- [Android Key Attestation](https://developer.android.com/training/articles/security-key-attestation)
- [Android Keystore System](https://source.android.com/docs/security/features/keystore)
- [X.509 Certificate Structure](https://tools.ietf.org/html/rfc5280)
- [ASN.1 Encoding Rules](https://www.itu.int/rec/T-REC-X.690/)

---

# 回复

## 回复 by huangjw (#2)

*2026-1-13 13:27*

可以的

## 回复 by Hawcett (#3)

*2026-1-13 14:02*

大牛也得自己找工作？？？

## 回复 by 简单的简单 (#4)

*2026-1-13 14:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Hawcett](https://bbs.kanxue.com/user-916899.htm)
>
>  大牛也得自己找工作？？？
>
>

![image](https://bbs.kanxue.com/view/img/face/032.gif)

## 回复 by 轻装前行 (#5)

*2026-1-19 18:02*

一加能不能root后使用原生微信指纹支付![image](https://bbs.kanxue.com/view/img/face/004.gif)第三方模块不放心

## 回复 by 土豆爱学习 (#6)

*2026-3-14 18:01*

666

## 回复 by mb_zcfhleoj (#7)

*2026-4-22 16:38*

感谢分享

## 回复 by mb_lzotvdxv (#8)

*2026-5-9 20:18*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by mb_vwdfywtj (#9)

*2026-6-6 07:21*

1
