---
title: 逆向小记  bd-ticket-guard-client-cert | bd-ticket-guard-client-data 通过现象看本质
url: https://bbs.kanxue.com/thread-277503.htm
tid: 277503
author: 至尊小仙侠
date: '2023-06-06'
tags: [Android安全, 基础理论, 逆向分析]
crawled_at: '2026-07-31T14:45:27+08:00'
replies: 8
---

# 逆向如逆水行舟,不进则退

## 0.因

最近在群里看到好多人在讨论安卓逆向中某APP的  **bd-ticket-guard-client-cert | bd-ticket-guard-client-data**  于是乎就过去喵了两眼！ 经过一番分析后发现这和我正在学习的 **安全通信行为与方案** 有异曲同工之妙，于是记个小记！

## 1.果

首先证书交换一定要经过服务器，所以我们先抓他个10分钟的包再说。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_AVF5KFHPEX6ASUK.png)
喝口茶的功夫，包抓到了,哦看起来像是个Base64？ 解密下？？？

  ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_BNRQ9K5GMMX9MGP.png)
太标准的证书格式了，拿出我们的openssl解析下

  ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_T9PJ6ZH3QKNFG79.png)

 依然没什么花哨的直接解析出来，既然这是个X509证书，那么要么是服务器下发，要么是自己生成喽，但是如果是本地直接生成，那服务器还校验个鬼哦！

 既然是服务器下发的，那服务器又是怎么校验这个证书是自己下发的呢，这就要讲到CA验证了，首先根据上图我们发现证书的Issuer"（颁发者）是  **ticket_guard_ca_ecdsa_256**  服务器用自己的 **私钥** 签名的值是

  ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_3F6K48FRXM3RRCZ.png)

 当服务器收到这个证书的时候，会做几件事，首先用自己的公钥解开签名获得解密后的证书hash
然后手动计算这个证书的hash值，如果两个hash匹配，那么服务器就确认这个证书是自己所签发下来的了。

## 2.种花得花

那么就ctrl+f搜索是什么包下发的呗！！！

  ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_DT6DWM3F89E3PQF.png)

 霍霍嚯嚯嚯，直接搜到！ 发现如参是个csr证书，okkkkk

---

 CSR是什么

# CSR是Certificate Signing Request的英文缩写，即证书签名请求文件，是证书申请者在申请数字证书时由CSP(加密服务提供者)在生成私钥的同时也生成证书请求文件，证书申请者只要把CSR文件提交给证书颁发机构后，证书颁发机构使用其根证书私钥签名就生成了证书公钥文件，也就是颁发给用户的证书。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_FVGYG8C8U2PPFVG.png)

 解密下这个CSR，okkk 那我们只要模仿下这个CSR就能让服务器给我们颁发个证书喽？
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/873999_ZSQ4RPMP6U62HZV.png)
那好吧随便改改之前的代码签名算法换成SHA256withECDSA CN改下，生产了一个跟他相似的CSR，传过去果然好使！！！

## 3.种豆得豆

那么最后这个 **ticket-guard-client-data** 怎么来的呢，因为涉及到逆向咱就不讲了，其实也是涉及到非对称加密的，就是客户端用私钥去签名数据，服务器用上传过去的证书公钥验签的过程！

## 4.苦海无涯回头是岸

学习太累了，不学又不行，人生太难，生活太苦，放下屠刀，回头是岸！！

---

# 回复

## 回复 by codeoooo (#2)

*2023-6-6 14:46*

666

## 回复 by shinratensei (#3)

*2023-6-9 10:02*

tql

## 回复 by suuuuu (#4)

*2023-6-26 15:22*

难难难    道德玄    不对知音不可谈

## 回复 by 至尊小仙侠 (#5)

*2023-6-26 17:45*

>
> [suuuuu](https://bbs.kanxue.com/user-872695.htm)
>
>  难难难&nbsp;&nbsp;&nbsp;&nbsp;道德玄&nbsp;&nbsp;&nbsp;&nbsp;不对知音不可谈
>
>

对了知音谈几句，不对知音枉费舌尖

## 回复 by 万里星河 (#6)

*2023-6-26 20:44*

逆向论坛发帖:因为涉及到逆向咱就不讲了![image](https://bbs.kanxue.com/view/img/face/36.gif)

## 回复 by 秋狝 (#7)

*2023-6-27 09:02*

66

## 回复 by 至尊小仙侠 (#8)

*2023-6-27 12:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  逆向论坛发帖:因为涉及到逆向咱就不讲了[em_36]
>
>

要是国外的app我就发了 这个怕涉及到风险问题   本来介绍的也是安全通信行为 hhh  哥们心里也苦啊

## 回复 by iBa0 (#9)

*2026-4-16 22:06*

AES GCM？？？
