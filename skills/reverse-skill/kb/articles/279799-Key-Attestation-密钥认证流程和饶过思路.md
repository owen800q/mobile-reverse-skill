---
title: '[原创]Key Attestation 密钥认证流程和饶过思路'
url: https://bbs.kanxue.com/thread-279799.htm
tid: 279799
author: pareto
date: '2023-12-07'
tags: [Android安全, 原创, 基础理论, 系统相关]
crawled_at: '2026-07-31T14:36:08+08:00'
replies: 17
---

# bypassKeyAttestation

目录- bypassKeyAttestation
- Key Attestation 密钥认证
- 获取证书链
- 解析证书链
- 对证书链进行校验
- 解析extension，获取设备的状态
- 饶过手段
- 准备证书
- 注入目标进程
- 替换证书链
- 结语
## Key Attestation 密钥认证

官方文档介绍： [https://source.android.com/docs/security/features/keystore/attestation，](https://source.android.com/docs/security/features/keystore/attestation%EF%BC%8C)

个人理解，硬件提供加密功能，同时该硬件模块也会反映设备的软硬件的安全环境。

不想自己实现一套代码的，可以直接用开源的:

 <https://github.com/vvb2060/KeyAttestation>

功能入口 <https://github.com/vvb2060/KeyAttestation/blob/master/app/src/main/java/io/github/vvb2060/keyattestation/home/HomeViewModel.kt> doAttestation方法：

### 获取证书链

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_FQ774XP79ET27ZN.webp)

### 解析证书链

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_W3DK2RUP7TU9AYV.webp)

### 对证书链进行校验

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_YT66MV3B5URBJXW.webp)

### 解析extension，获取设备的状态

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_WCJGYKE5G6SHNQ6.webp)

格式规范文档： <https://source.android.com/docs/security/features/keystore/attestation#attestation-extension>

简单看下解析extension的内容
 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_GTS9FCJAVMKC82C.webp)

解析后部分数据

```
Attest version: Keymaster version 4.1
Attest security: StrongBox
Verified boot Key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= (base64)
Device locked: false
Verified boot state: Unverified

//Hash for boot
//Hashtree metadata for system
//Hashtree metadata for vendor
Verified boot hash: nDqAWissOCsw+aWEm7cEcAkCvQngEE+ypQ75UWakxt4= (base64)
```

## 饶过手段

思路比较简单，替换到整条证书链为一个正常设备的证书链即可：

1. 可以通过hook java层代码
2. 写一个magisk插件 <https://github.com/doom-man/bypasskeyattestation>

hook java层已经比较熟练了，由于后续期望强化对异常设备的检测，大多对抗检测的工具又是走magisk插件实现的，打算用magisk插件实现一遍。

参考 <https://github.com/chiteroman/PlayIntegrityFix> 大佬写的插件进行学习，对大佬拙劣的模仿。

### 准备证书

将证书文件移动/data/local/tmp 下，并提供读权限；
 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_EPB42WX6BR5J439.webp)

### 注入目标进程

代码入口在cpp/main.cpp

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_MHDSDN8BFB8C2DQ.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_ZF3B37YXJG8BAAK.webp)

### 替换证书链

 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_DT54ADWWRPJ6M4Z.webp)

CustomKeyStoreSpi.java
 ![image](https://bbs.kanxue.com/upload/attach/202312/790193_UMXS3Y4BQ4MYPU5.webp)

替换后效果

## 结语

我认为设备异常判定，即使各大厂商去自研解决方案，也应该去学习了解系统层面提供的安全检测手段 和 官方在用的判定方案。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-12-8 10:26*

感谢分享

## 回复 by 月落之汀 (#3)

*2023-12-11 10:15*

RootOfTrust这部分信息在bootloader的启动过程中就被设置进TEE了，用TEE的证书签发时，就包含了这部分信息，且存放在证书的extension中，这里面包含了设备BL状态和启动状态等信息，因为校验的是链上的所有证书（通常3个），这部分信息是无法篡改的，因此这部分，针对本地的证书链校验，hook掉证书的verify就可以了，没必要替换证书，因为人家真的把证书传上服务器（目前是有的）去校验是不是谷歌的证书的话，即便通过，也存在相应的检测点

## 回复 by pedies (#4)

*2023-12-11 10:17*

试了一下，没有生效呢， 设备还是unlock

## 回复 by pedies (#5)

*2023-12-11 10:28*

思路比较简单，替换到整条证书链为一个正常设备的证书链？   正常的证书怎么获取到呢？

## 回复 by pareto (#6)

*2023-12-11 10:49*

跟大师傅沟通下 ，目前unlock 只是针对key attesation ，还有challenge 码的问题需要解决，还会做进一步研究强化功能

## 回复 by pareto (#7)

*2023-12-11 10:50*

私聊 我看看问题呢

## 回复 by pareto (#8)

*2023-12-11 10:51*

>
> [pedies](https://bbs.kanxue.com/user-655107.htm)
>
>  试了一下，没有生效呢， 设备还是unlock
>
>

私信下 看看问题

## 回复 by pareto (#9)

*2023-12-11 10:53*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>
>  RootOfTrust这部分信息在bootloader的启动过程中就被设置进TEE了，用TEE的证书签发时，就包含了这部分信息，且存放在证书的extension中，这里面包含了设备BL状态和启动状态等 ...

是的 也可以

## 回复 by pareto (#10)

*2023-12-11 11:08*

>
> [pedies](https://bbs.kanxue.com/user-655107.htm)
>
>  试了一下，没有生效呢， 设备还是unlock
>
>

或者直接提issue

## 回复 by zpazz (#11)

*2023-12-13 00:01*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>
>  RootOfTrust这部分信息在bootloader的启动过程中就被设置进TEE了，用TEE的证书签发时，就包含了这部分信息，且存放在证书的extension中，这里面包含了设备BL状态和启动状态等 ...
>
>

师傅，如果上传。有思路解决么![image](https://bbs.kanxue.com/view/img/face/35.gif)

## 回复 by pareto (#12)

*2023-12-13 10:15*

>
> [zpazz](https://bbs.kanxue.com/user-822224.htm)
>
>  师傅，如果上传。有思路解决么[em_35]
>
>

利用一个安全的中间人提供证书，

## 回复 by 月落之汀 (#13)

*2023-12-13 11:38*

>
> [zpazz](https://bbs.kanxue.com/user-822224.htm)
>
>  师傅，如果上传。有思路解决么[em_35]
>
>

理论上你能搞到TEE的私钥（RSA和ECC两组）才行，这个是生产的时候就已经被厂家写进去的，而且大概是10k设备用一组（谷歌是这么说的，实际不清楚），没那么简单就可以读出来，不过有些设备TEE本身就有问题，就是取不到的，还有个办法就是楼主说的中间人了，给另外一台环境一致的设备代签就可以了

## 回复 by 空空的爸爸 (#14)

*2023-12-30 17:38*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>
>  RootOfTrust这部分信息在bootloader的启动过程中就被设置进TEE了，用TEE的证书签发时，就包含了这部分信息，且存放在证书的extension中，这里面包含了设备BL状态和启动状态等 ...
>
>

可以通过自定义rom 解决把。直接修改bl状态为lock可以么

## 回复 by 寻梦之璐 (#15)

*2024-11-21 16:23*

>
> [pedies](https://bbs.kanxue.com/user-655107.htm)
>
>  思路比较简单，替换到整条证书链为一个正常设备的证书链？ 正常的证书怎么获取到呢？
>
>

有思路了嘛，大佬

## 回复 by mb_dmfadzfi (#16)

*2024-12-11 10:40*

看起来没问题，实则还是没办法绕过去：

1，hook掉证书的verify就可以了，没必要替换证书，因为人家真的把证书传上服务器（目前是有的）去校验是不是谷歌的证书的话，即便通过，也存在相应的检测点 --------------------------》 都是在服务器验证，谁还在本地校验，服务器校验完成后结果就保存在服务器端。本地hook了没啥用，就如hook微信修改余额，只能骗骗人而已，真正的钱还是那么多。

2， 用中间代理人，看起来可以，但还是不行， 在证书链返回的数据中，Software Enforced Authorization List: 中Attestation Application ID: 里面有Package Infos和Signature Digests 这个是调用app的签名，也就是作为中间人在正常手机中获取证书链的app的签名要与google的app一样，又只能hook Google app或正常手机中hook包签名信息，这样又要破坏正常手机，就成了死循环。

目前也在寻找其它合适解决办法，还没有其它思路讨论呢

## 回复 by pareto (#17)

*2024-12-12 18:08*

兄弟们 G

## 回复 by mb_nrdkziep (#18)

*2025-3-6 23:17*

>
> [pareto](https://bbs.kanxue.com/user-790193.htm)
>
>  兄弟们 G
>
>

咋样，搞定了吗
