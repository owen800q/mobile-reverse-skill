---
title: '[原创]某政务APP登录链路逆向：datagram 参数与 signature 签名分析'
url: https://bbs.kanxue.com/thread-291164.htm
tid: 291164
author: Mengz3
date: '2026-05-09'
tags: [Android安全, 原创, 逆向分析, HOOK注入, 协议分析]
crawled_at: '2026-08-08T10:08:52+00:00'
replies: 36
---

本次分析的APP信息(因保密原因不能完全透露)：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_YMMTCAMGYX5ATX5.webp)

本次分析重点为登录时请求参数分析

```python
{
  "access_token": "",
  "datagram": "Vs0sGlHrcqzFO6umQ2CEUKLhCCUIzMN9n3UZeGY3OHN5iOaVNOg/r1s3dx9fNK1X0Ast0GzfsG4KEFn56kh9bNfE5jph0GMNYxq5G2FEh09a8arW8RkqMRhqg0knoRUW",
  "encryptCode": "2",
  "signature": "wv22glX8Thg6M0Nj8yDSGmPJK+nqnRpcbovdHk11Wbw=",  //抓包每次都会变化
  "signtype": "HMacSM3",
  "timestamp": "20260509195242",
  "zipCode": "1"
}
\```

## datagram参数分析：

 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_WAKEEQ8G7U8ZHCB.webp)
感觉是base64编码后的，通过hook base64调用看下情况：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_VXC9PXZWJVVFK2A.webp)
是base64加密后的，跟踪调用链看下`cn.gov.chinatax.gt4.bundle.tpass.depend.util.SM4Util.encryptData_ECB`，发现函数下面有SM4标准加密
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_PPRMXWAYSB3AG79.webp)
参数都对的上
hook一下这回两个加密函数，看下到底是哪个加密的
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_UGB33SCUSVYP6XE.webp)
发现是参数String那个
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_WQB8C7K59KBDEC3.webp)
将入参明文直接用SM4加密，发现前面全都对得上，只有最后21个字符串对不上，这里怀疑是填充方式有问题
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_89JPZRACG7FD8GG.webp)
把b64-->hex，发现是最后32位对不上，也就是说最后一轮有问题
在刚刚的代码里发现了轮函数线索：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_83EQVSYH27XHSQE.webp)
尝试hook一下，和普通加密最后一轮对比一下
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_92B9ZEG77YMEQAS.webp)
这是标准SM4加密后的最后一轮：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_M7CBQF2Y8SWGZBQ.webp)
对比一下发现最后填充的有问题。
不是“纯标准 SM4 ECB PKCS5”，而是 **先在明文末尾追加一个 0x00，再做剩余长度的 PKCS5/PKCS7 补位**；因此最后一个分组从 ...0808 变成了 ...00070707...，最终导致看到的最后一段密文不同。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_XAJ3Z9V96QBVVVS.webp)
到这datagram参数已经还原到了第一步

### datagram 目前结论

- `RequestUtil.getCompressedDatagram(String)` 的返回值是 `gzip` 后再 `base64` 的字符串
- `SM4Util.encryptData_ECB(String, String)` 是实际命中的加密入口
- 此处不是“纯标准 SM4 ECB PKCS5/PKCS7”
- 实际行为是：**先在明文末尾追加一个 `0x00`，再按剩余长度做 PKCS5/PKCS7 样式补位**

接着我们分析一下sm4加密传入的参数，进一步分析一下直到原始数据
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_NRVRPS4NP7GZF3E.webp)
分析一下这个值怎么来的，参数一眼b64加密后的
追一下b64 hook
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_UVPARDSN92CP2D6.webp)
追一下这个调用链`cn.gov.chinatax.gt4.bundle.tpass.depend.util.RequestUtil.getCompressedDatagram`
发现也是个native函数
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_FT7KESEAJZJS4TG.webp)
hook一下
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_848ZGHXWU3FDXE7.webp)
账号密码明文传入，加密成这个数据
返回值`H4sIAAAAAAAAAKtWKkgsLi7PL0pRslIyNDI2MTUzt1DSUUpMTs4vzSsBCRobmZobmZhZmhoq1QIA7XQPhy8AAAA=`
是base64加密
前四个b64字符为：`H4sI → 1F 8B 08` 这是gzip压缩的头标志（感谢GPT）
尝试一下结果正确
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_5K66Y358KDVQGFC.webp)

### datagram 完整链

梳理一下整个调用链：

#### 业务链

- 账号密码明文 JSON
- `RequestUtil.getCompressedDatagram(String)`
- 返回 `H4sI...` 字符串
- `SM4Util.encryptData_ECB(String, String)`
- 最终生成 `datagram`

#### 数据处理链

- 原始 JSON
- `gzip` 压缩
- `base64` 编码
- 得到 `H4sI...` 字符串
- 明文末尾追加 `0x00`
- 再做剩余长度补位
- `SM4 ECB` 加密
- 最终输出 `datagram`

## signature参数分析

 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_SHGDU2TU6FQUE36.webp)
也是和datagram一样，从b64调用开始追
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_E45V66SHPGXE2DR.webp)
追一下这个调用函数，发现是SM3HashMac，hook一下
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_4ECGDHWRU3YKCF3.webp)
签名每次都在变化，大概率和时间戳有关
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_TH5GKXN4RDWXN9Z.webp)
这里观察到入参明文：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_H2BBJGBMXTXX7XX.webp)
刚好和其他参数相对应
zipCode+encryptCode+datagram+timestamp
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_NCD7PYHF9EJJPZE.webp)
所以每次只有时间戳变化，每一次的结果都不一样
直接就还原出来了，标准的HMacSM3签名
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_NT7N5QHWW4696XJ.webp)

### signature 结论

- `signature` 由 `SM3Util.sm3HashMac(...)` 生成
- 参与签名的明文与：`zipCode + encryptCode + datagram + timestamp` 对应
- 因为 `timestamp` 每次变化，所以 `signature` 每次都会变化

### signature 公式

#### 明文拼接关系

- `zipCode + encryptCode + datagram + timestamp`

#### 算法

- 标准`HMacSM3`

#### 结果特点

- `timestamp` 参与签名
- 所以相同业务数据下，只要时间戳变化，`signature` 就会变化

---

推荐一下比较好用的 Frida 工具：[Frida-Hookers](https://github.com/Mengz3/Frida-Hookers)

---

## 逆向声明

本分析仅面向受控样本、授权测试目标或本地研究环境，目的在于理解应用实现、协议流程、加密逻辑与安全机制，不针对任何未授权真实业务系统实施攻击或滥用。

文中涉及的 Hook、解包、流量分析、协议还原、加密验证等操作，仅用于安全研究与技术验证。所有结论仅作学习记录和研究参考，不作为未授权利用指南。

上传的附件：
- base64.js

（8.17kb，10次下载）
- sm3.js

（2.54kb，10次下载）
- sm4.js

（3.54kb，10次下载）
- sm4.py

（6.03kb，10次下载）
- update_anti.js

（4.62kb，12次下载）
- zip.js

（0.91kb，10次下载）

---

# 回复

## 回复 by 上官兮唐 (#2)

*2026-5-9 22:00*

看看

## 回复 by wx_插曲 (#3)

*2026-5-10 09:39*

看看

## 回复 by 一栋奥特曼 (#4)

*2026-5-10 14:02*

看看

## 回复 by wx_Arron (#5)

*2026-5-10 14:09*

11

## 回复 by nhtr (#6)

*2026-5-10 17:40*

66

## 回复 by mb_ldbucrik (#7)

*2026-5-10 20:29*

感谢分享

## 回复 by mb_fidppcok (#8)

*2026-5-11 10:49*

感谢分享

## 回复 by xianhuimin (#9)

*2026-5-11 13:21*

看看

## 回复 by shuyangzjg (#10)

*2026-5-11 14:03*

学习学习

## 回复 by 乐活 (#11)

*2026-5-11 14:11*

1111111

## 回复 by 086Love (#12)

*2026-5-11 14:13*

学习

## 回复 by mb_fywmigrm (#13)

*2026-5-11 15:01*

1

## 回复 by 4Chan (#14)

*2026-5-11 15:19*

我看刑

## 回复 by mb_uzmffdbw (#15)

*2026-5-11 17:47*

666

## 回复 by Snowman_Liam (#16)

*2026-5-11 17:59*

666

## 回复 by 菜鸟9527 (#17)

*2026-5-12 09:22*

999

## 回复 by 菜鸟9527 (#18)

*2026-5-12 09:30*

登录接口的逆向都不用到so层嘛？

## 回复 by huangjw (#19)

*2026-5-12 09:39*

学习了谢谢

## 回复 by 天涯共何时 (#20)

*2026-5-12 09:54*

111

## 回复 by Gryffindoss (#21)

*2026-5-12 10:12*

66666

## 回复 by Crack999 (#22)

*2026-5-12 14:15*

2522

## 回复 by 末日大哥 (#23)

*2026-5-12 14:26*

666学习一下

## 回复 by 五彩斑斓的黑 (#24)

*2026-5-13 10:31*

666

## 回复 by mb_ykavguun (#25)

*2026-5-15 12:14*

1

## 回复 by mb_elqwyvnm (#26)

*2026-5-16 17:32*

个人所得

## 回复 by mb_rirvdrlh (#27)

*2026-5-16 19:03*

6666666666666

## 回复 by jw8888 (#28)

*2026-5-16 19:45*

11111

## 回复 by mb_jnmxfjku (#29)

*2026-5-19 16:38*

666

## 回复 by 黑色心跳 (#30)

*2026-5-23 11:22*

学习

## 回复 by mb_gjhmacqd (#31)

*2026-6-28 10:46*

666

## 回复 by fannn (#32)

*2026-7-5 12:27*

666

## 回复 by Vqqqqqqqqqq (#33)

*2026-7-7 03:05*

nb

## 回复 by iBa0 (#34)

*2026-7-8 22:05*

1

## 回复 by mb_conrfpbo (#35)

*2026-7-10 11:29*

666

## 回复 by wx_kx92911 (#36)

*2026-7-15 09:46*

感谢分析

## 回复 by Sigil (#37)

*2026-7-31 10:11*

1
