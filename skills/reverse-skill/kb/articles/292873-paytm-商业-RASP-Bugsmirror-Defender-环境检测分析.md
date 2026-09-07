---
title: '[原创]paytm  商业 RASP Bugsmirror Defender 环境检测分析'
url: https://bbs.kanxue.com/thread-292873.htm
tid: 292873
author: 小七烤地瓜
date: '2026-09-07'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆, 漏洞相关, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-09-07T08:25:39+00:00'
replies: 19
---

# Bugsmirror Defender (libcachehandler.so) 检测分析与绕过

>
> 目标库：`libcachehandler.so`（商业 RASP **Bugsmirror Defender**，特征串 `BugsmirrorDefenderValidation` / `com.bugsmirror.samplekeyattestation`）
> 分析环境：AArch64，IDA + Frida Gadget
> 关键函数（设备版 `libcachehandler.so_fixed` 偏移）：
>
>
> - `sub_14D5E0` — 上报汇聚点 `handle_security_violation(ctx, code, sev, a3, a4, ist)`
> - `sub_DF838(id)` — 结果读取器，读全局结果位表（`sub_EA95C` 为解密重建版对应函数）
> - `sub_143BB4` / `sub_11DEE8` — keystore attestation 校验（IST31 所在）
> - `check_android_keystore_integrity_trap`（重建版 `sub_11D478`）— **echo-trap 回声陷阱本体（IST34）**
> - `check_su_in_system_image`（重建版 `sub_11B9B8`）— IST34 上报判定点，调用上面的 echo-trap
> - `sub_14BDA8` — 运行期字符串解码器
>
>
> 说明：以下 IST34 小节的偏移取自**解密重建版 `libcachehandler_decrypted_rebuild.so`**（结果读取器为 `sub_EA95C`），已用 IDA 逐条验证。
>
>
>

---

## 一、检测码总览

| code | arg5 / 含义 | 检测的东西 | 应对 |
|-|-|-|-|
| **61007** | `61007-IST1` … `IST34` | **AndroidKeyStore 密钥认证链真伪**（核心，见下） | 关掉 StrongBox 特性 |
| **61009** | `61009-IST1/2-<包名>` | 已装应用黑名单（77 项，如 `bin.mt.plus` MT管理器） | 卸载/改包名 或 Frida 藏包名 |
| **10002** | `CA compromised by proxy tool:` | 抓包/中间人代理 CA（Charles/Fiddler/HttpCanary…） | 卸抓包工具/删其 CA |
| **10004** | `90040-IST5` | popen shell 命令环境探测 | 视命令而定 |
| **00000** | `Device environment is not correct.` | **兜底异常**：某检查抛异常没走完（本例是 StrongBox 请求失败引发） | 消除引发异常的根因 |

>
> 注：`61007` 的 `IST1…IST34` 在**上报层**都汇聚到 category 1004（`if (sub_EA95C(1004)) 上报`），根因归一；但**检测层 IST31 与 IST34 是两套不同原理**：`IST31`（`sub_11DEE8`）是硬件认证链**验签 + pin 比对**，`IST34`（`check_android_keystore_integrity_trap`）是**「echo-trap」回声陷阱**——两者互补，详见第二节。
>
>
>

---

## 二、61007 (IST31/IST34…) 检测原理 —— Key Attestation 链真伪校验

### 结构

- 所有 `61007-ISTx` 上报都是 `if (sub_DF838(1004)) 上报`——**只读 category 1004 的结果位**。
- category 1004 由 keystore attestation 校验置位。

### 校验流程（`sub_11DEE8` / `sub_143BB4`）

1. `hasSystemFeature("android.hardware.strongbox_keystore")` —— 设备有 StrongBox 则 `setIsStrongBoxBacked(true)`。
2. `KeyPairGenerator` 现场生成一个带 attestation 的 key（EC secp256r1 / RSA，固定证书 notBefore/notAfter）。
3. `getCertificateChain` 取回证书链。
4. **逐级 `cert.verify(上一级公钥)`** —— 密码学验签，确认每张证书由上一级真实签发。
5. **`checkValidity()`** —— 证书未过期。
6. **比对链上证书的公钥 / 序列号 / IssuerDN 与内嵌 pin 值**（内嵌了正版 Google/TEE 认证链的参考值，`sub_122BD4`/`sub_122EE8`）。
7. 验签失败 / pin 对不上 → 置 category 1004 → 报 61007。

### 关键点

- **它验的是「链是不是 Google 真私钥签的」，不是「内容填得对不对」，也不查解锁状态（无 `getExtensionValue`、无 RootOfTrust、无 verifiedBoot/locked 解析）。**
- 内嵌 pin 里有一张真实 Google/TEE 中间证（CRL 序列号 `10997554208317698753`）及其 EC 公钥 `MFkw…`，是它的参照锚点。

### 为什么伪造（TrickyStore / TEESimulator）过不了

- 这类模块把真链 leaf 以上整段换成自己 keybox 的中间证/根证（`newChain = leaf + keybox.certificates`）。
- 换出来的链**没有 Google 真私钥的签名**，验签/pin 对不上 → 必中。
- **数学上无解**：要伪造一条能通过 Google 签名验证的链，需要 Google 的私钥，你没有。换正版三绿 keybox 也不行（pin 的是它自带的特定链，不是你 keybox 的链）。

---

## 二·补、61007-IST34「echo-trap」检测原理 —— 回声陷阱（IDA 已验证）

IST34 与 IST31 上报层同归 category 1004，但**检测原理完全不同**：IST31 打「你伪造的链没有 Google 真签名」，IST34 打「你的 hook 太贪，连我自己塞进 KeyStore 的已知证书都乱改」。一个从密码学正确性下手，一个从「keystore hook 的副作用」下手，互为补充；凡是粗暴全局替换 `getCertificateChain` 返回值的伪造模块，两条都躲不掉。

### 上报判定（`check_su_in_system_image` @ 0x11B9B8）

```c
v2 = sub_EA95C(1004);                        // 先读 1004 当前结果位
if (__system_property_get("ro.build.version.sdk", nptr) <= 0) return;
v3 = (v2 & 1) != 0 ? 29 : 33;                // SDK 阈值:1004 已置位→29,否则→33
v4 = atoi(nptr);
if (v4 < 1 || v4 < v3 || (byte_15FCDB & 1)) return;   // SDK 太低 / 已跑过一次 → 跳过

if ((sub_EA95C(1004) & 1) != 0 && check_android_keystore_integrity_trap(a1))
    handle_security_violation(a1, "61007", 0, 0, 0, "61007-IST34");
\```

三个门槛：

1. **`byte_15FCDB` 单次守卫** —— 全程只跑一次（函数末尾置 1）。
2. **SDK 门槛** —— Android 8/8.1 以下不跑。
3. **`sub_EA95C(1004) & 1` 必须已为真** —— 即 **IST34 是 IST31 的「二次确认」**：只有当链校验已把 1004 置位、判定环境可疑，才拉起 echo-trap 再确认一遍，成立就补报 `IST34`。

### 检测本体（`check_android_keystore_integrity_trap` @ 0x11D478）

内嵌两块 base64（重建版直接写入）：

| 变量 | 内容 |
|-|-|
| 私钥 | 一段 **PKCS#8 EC 私钥**（secp256r1） |
| 证书 | 对应的一张**自签证书**，CN = `EchoTrapStatic`，notBefore `2026-05-07` / notAfter `2126-04-13` |

流程：

1. `sub_147EF0`（WolfSSL）把两段 base64 解成 DER，记下**证书 DER 及其长度**作为参照锚点；解码失败抛 `WolfSSL failed to decode Private Key / Certificate`。
2. 私钥经 `PKCS8EncodedKeySpec` + `KeyFactory("EC").generatePrivate` 还原；证书经 `CertificateFactory("X.509").generateCertificate` 还原。
3. **`keyStore.setKeyEntry("echo_trap_key", privKey, pwd, [cert])`** —— 把这张**内容完全已知**的 leaf 证书塞进 AndroidKeyStore。
>
> 前面还用 `KeyPairGenerator` + `setAttestationChallenge("trap_bait")` 生成过一个真 attestation key，那是**诱饵**，让 hook 以为这是常规 attestation 调用。
>
>
>
4. **`chain = keyStore.getCertificateChain("echo_trap_key")`** —— 原样读回。
5. **`keyStore.deleteEntry("echo_trap_key")`** —— 用完删除，不留痕。
6. **逐字节比对（核心判定）**：

```c
if ( !GetArrayLength(chain)                          // 链为空
  || chain[0].getEncoded().length != 内嵌证书长度 )   // 长度对不上
{
    return true;                                     // 判定被篡改
}
return memcmp(内嵌证书DER, chain[0].getEncoded(), 长度) != 0;  // 一个字节不同 → 篡改
\```

### 为什么能逮住 TrickyStore / TEESimulator

- 正常设备：塞进去什么读回来就是什么，`memcmp == 0`，返回 false，不报。
- 装了 keystore 伪造模块：这类模块为骗过 attestation 会**无差别拦截 `getCertificateChain`**，把返回链整段换成自己 keybox 的伪造链。于是连跟 attestation 毫无关系的 `echo_trap_key` 也被替换 —— 读回的 leaf 不再是那张 `EchoTrapStatic` 自签证书，长度/字节对不上 → **IST34 命中**。

### IST34 的绕过

- IST34 挂在 `sub_EA95C(1004)` 已置位的前置下 —— **只要让 1004 不置位（方法 A 关 StrongBox 让 IST31 整条不跑），echo-trap 根本不会被调**，IST34 一并消失。
- 运行期 hook（方法 C）：`sub_EA95C` 对 `id==1004` 返回 0，同时压掉 IST31 与本条前置。
- 若单独针对 echo-trap：让你的 keystore hook **对 alias `echo_trap_key` 放行（不替换其返回链）** —— 成熟伪造模块应做的「白名单」逻辑，粗暴全局替换的会死在这里。

---

## 三、关键突破 —— StrongBox 特性是「强完整性检查」的开关

第 1 步是核心：**App 只在「设备报告有 StrongBox」时才跑这套强完整性检查（IST31）。**

- `hasSystemFeature(strongbox) = true`（真 Pixel 6 等）→ 走 StrongBox 路径 → 跑链校验 → 伪造链被逮 → **61007**；若让 StrongBox 请求失败 → 抛 `StrongBoxUnavailableException` → **00000「环境不对」**。
- `hasSystemFeature(strongbox) = false` → **App 不请求 StrongBox → 整条强完整性检查跳过 → 没有 61007，也没有 00000。**

**所以：把设备的 StrongBox 特性关掉，IST31 直接不跑。** 这是最干净的绕过。

---

## 四、应对方法（已验证有效）

Hook 改机 魔改ts 最近新出的漏洞机免解锁root提权三绿转发 均可实现绕过 感兴趣的可以自己测试一下 这个检测思路还是比较有意思的

## 五、其它检测码与应对

| code | 检测 | 应对 |
|-|-|-|
| **61009** | `getInstalledPackages` 拿已装应用，逐个与 77 项编码黑名单 `strcmp`（`sub_14BDA8` 解码后比），命中报 `61009-IST2-<包名>` | 卸载/改包名命中项；或 Frida hook 解码器 `sub_14BDA8`，解出黑名单包名时原地改首字节使其匹配不上 |
| **10002** | 扫已装 CA 证书，发现抓包/代理工具 CA（拼串 `CA compromised by proxy tool:` ） | 卸抓包工具，删其用户 CA |
| **10004 / 90040-IST5** | `sub_14BDA8` 解出一条 shell 命令 → `popen(cmd,"r")` 读输出判断环境 | 看具体命令（hook `sub_14BDA8` 打印）；隐藏对应痕迹 |
| **00000** | 兜底：检查抛异常没走完 → `Device environment is not correct.` | 消除引发异常的根因（本例＝StrongBox 请求失败，用方法 A 关特性即可根除） |

---

## 六、本项目最终采用的方案

第四步应对方法均已实现

## 七、水贴一篇 不喜勿喷

---

# 回复

## 回复 by 我不是卷王 (#2)

七爹牛逼

## 回复 by mb_powwxesw (#3)

666

## 回复 by Light紫星 (#4)

支持大佬

## 回复 by hacker521 (#5)

支持大佬

## 回复 by mb_jmkqiocd (#6)

看看7佬的nb技术

## 回复 by Migc (#7)

七哥牛逼

## 回复 by 啊你好哇123 (#8)

学习学习

## 回复 by 铭信 (#9)

![image](https://bbs.kanxue.com/view/img/face/092.gif)![image](https://bbs.kanxue.com/view/img/face/092.gif)![image](https://bbs.kanxue.com/view/img/face/092.gif)![image](https://bbs.kanxue.com/view/img/face/092.gif)

## 回复 by mb_ldbucrik (#10)

向大佬学习

## 回复 by 熊猫吃鱼 (#11)

8888

## 回复 by iBa0 (#12)

666

## 回复 by tonykros (#13)

666

## 回复 by wx_Huber Barrientos (#14)

666

## 回复 by 拍拖 (#15)

感谢你分享

## 回复 by mb_xjdhrmck (#16)

12312

## 回复 by k4y0z (#17)

666

## 回复 by Dem0li (#18)

111

## 回复 by manyuegong33 (#19)

123

## 回复 by 不营业红茶冻 (#20)

文中：内嵌 pin 里有一张真实 Google/TEE 中间证（CRL 序列号 10997554208317698753）及其 EC 公钥 MFkw…，是它的参照锚点
安卓各家厂家的 CA 差异非常大有这么多，他是如何收集的？
如果用户用的是小众机型，该软件如何放行策略？
