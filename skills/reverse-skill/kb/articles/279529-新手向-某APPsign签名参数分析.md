---
title: '[原创]新手向-某APPsign签名参数分析'
url: https://bbs.kanxue.com/thread-279529.htm
tid: 279529
author: Aimees
date: '2023-11-13'
tags: [Android安全, 原创, 逆向分析, NDK分析, 协议分析]
crawled_at: '2026-07-31T14:36:43+08:00'
replies: 11
---

分析该APP的包请求，在Fiddler中发现一个请求包：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_PTRBM6MSH5BJTZC.webp)

想把其中的签名弄清楚，然后用python去模拟协议。

原始返回的数据是protobuf的格式，通过修改请求头Accept，可以让服务器返回json的数据格式。

具体操作步骤为：直接将请求头中的Accept: application/x2-protostuff; charset=UTF-8，更改为：Accept: application/json; charset=UTF-8

但是如果直接请求，浏览器会报签名错误：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_3ZT3CFDNGNC9G3M.webp)

注意看请求头中，有两个签名（sign和sg字段），因此这两个签名需要逆向解决，另外还需要知道oak（可能是key）是什么东西。

所以直接将app拖到jeb里面，首先通过查找网址，可以搜索到其构造URL的代码逻辑块，位于：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_QNAUFT2QP5QCEHW.webp)

通过上述定位，可以找到发起请求的入口：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_A7TM5U8CRBRRQ6G.webp)

再往下分析，查看函数makeRequestByPkgName，这个调用就是通过包名获取信息的函数接口：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_FDQ9YT5XMSVQ3BS.webp)

这里new了一个请求ProductDetailRequest，实现了com.nearme.network.request.IRequest接口，进入到请求类中，查看具体的实现：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_3WRUY45XUPZX6WH.webp)

上图中可以发现，请求操作在com.nearme.network.c类中的函数中，查看函数上一跳，发现请求接口：com.nearme.network.extend.d.request

继续分析可以发现该请求接口设置了拦截器并通过initHeader函数初始化了请求头：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_FQ2BHTBWNBFW9GV.webp)

通过分析请求头中的参数来源，将部分重要参数和对应的说明，以及抓包中获取的值列表如下：

| 参数 | 参数说明 | 抓包获取的值 |
|-|-|-|
| otaver | OTA版本，即系统属性”ro.build.version.ota“ | PERM00_11.C.08_1080_202201271341 |
| device_type | 设备类型0：手机 1：折叠设备 2：平板 | 0 |
| User-Agent | 浏览器UA信息（URLEncode） 数据格式是：设备生产商/设备型号/安卓系统版本号/安卓版本/设备ROM版本号/APP_CODE/APP渠道号（默认为0）/应用市场版本号/应用市场版本名 | OPPO%2FPERM00%2F30%2F11%2FV11.1%2F2%2F2101%2F110005%2F11.0.1 |
| t | 当前时间戳 | 1699251997861 |
| id | 代码中的openid 数据格式是：GUID/OUID/DUID/AndroidId | /2bcba0937bc629468b9886c10bf3cbbada3d743768ece4f548a80e41d9360e6a/AA177E8E54FA42CA928C9638A9BDFB8C5bb7929185700b4a882306a43cc6710f/CD623898E41E4FB18BD2ED0842CC0AADEC7D424979CC9C51C70EAC900ECAD017 |
| ocs | 数据格式：设备生产商/设备型号/安卓系统版本号/安卓版本/设备ROM版本号/APP_CODE/ro.build.display.id/应用市场版本号然后经过URLencode处理 | OPPO%2FPERM00%2F30%2F11%2FV11.1%2F2%2FPERM00_11_C.08%2F110005 |
| sign | 签名1 | 47e29daacff4479021520eac9100a1cd |
| sg | 签名2 | 4df40cedbd7d5fec9876600cccb235a9 |
| oak | 签名密钥key | cdb09c43063ea6bb |

通过请求测试，签名sign、sg、oak是服务器作为校验的依据，所以需要对上面三个参数做分析。

**①：**参数”oak“来源的分析

java层获取该参数的代码块是：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_VBD7QH5GCHUQ7DV.webp)

函数跳转到native层，so文件名称：libocstool.so。

上述JNI函数通过静态注册，查看b函数：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_Y2NNT9YT5AY4KA5.webp)

发现key1通过a函数初始化得出，在请求之前进行初始化，并校验APP的签名。

如果APP签名校验不通过，则key得不到初始化，应用内所有的请求都会返回错误。

![image](https://bbs.kanxue.com/upload/attach/202311/978841_5HD7K7RMDKDH9CN.webp)

进入init_key，key1的来源通过包名进行绑定，所以与该应用市场对应的包名的key1为cdb09c43063ea6bb

![image](https://bbs.kanxue.com/upload/attach/202311/978841_HYA2M6JWAKS55T6.webp)

#### **②：参数”sign“来源的分析**

在java层，通过组合特定的参数传入签名函数中：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_6KG7777QZ3K7K9J.webp)

hook一下，可以看到值，通过分析也可以知道传入的参数为：设备生产商/设备型号/安卓系统版本号/安卓版本/设备ROM版本号/APP_CODE/ro.build.display.id/应用市场版本号+当前时间戳/GUID/OUID/DUID/AndroidId/URL_Path+URL_Query

![image](https://bbs.kanxue.com/upload/attach/202311/978841_XCJ9DZ4D7R59H7A.webp)

参数已经分析完毕，接下来来看sign的签名算法：

在上述初始化key1结束后，函数立即初始化了key2：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_THMDBCFJPT4C6W3.webp)

跟踪调用实现，发现key2 通过计算得出：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_SPEX6MQDGXPQX2Q.webp)

简单描述一下生成逻辑：算法：通过去掉v1前两位，然后将v1剩下的部分头尾交换，再拼接上key1，组成一个48位的key2：

| key1 | v1 | key2 |
|-|-|-|
| cdb09c43063ea6bb | 09bdc58acb383220be08f4fe8a43775179 | cdb09c43063ea6bb08f4fe8a43775179bdc58acb383220be |

进入到c函数，可以发现sign的签名是通过MD5计算得出：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_MEFJTVPXSTKSKJC.webp)

算法可以概括为：toHex(MD5(key2 + a1 +（a1的长度+key2的长度）+OBSCURE_CODE))

③：参数”sg“来源的分析

java层中，签名1将作为参数传递给签名2：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_65FJDQ8GGGWM3F4.webp)

然后再组合相应的参数，丢到native层中：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_B5EFFK4AM2XXDDY.webp)

通过分析也可以知道d函数的两个参数是什么，参数a3为Url_path + Url_query+Accept+请求类型字符串（get、post、put、head四选一）+openid+时间戳，参数a4为上面计算的sign。

查看函数d，首先这里将参数a3、key1和a4字符串相合并，然后计算长度，然后再加上计算的长度数字，计算一轮MD5，即MD5(a3+key1+a4+长度数字字符串)：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_858SBGQZVNN7AWE.webp)

然后这里计算出MD5之后，拿着MD5的byte字节数据数组，数组中的每一个数字取绝对值之后，取个位数字（%10）相加再%10：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_YJCRCNXT3JS56KN.webp)

最后得到的v28其实是个数字，取值范围为0-9。然后，对得到的数字再%5，取密钥数组的下标：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_98774ZN7VNRQWNP.webp)

密钥数组sgk和sgsk是一个长度为5的数组：

![image](https://bbs.kanxue.com/upload/attach/202311/978841_YCWJQ3G3A8E9HSS.webp)

通过上面的计算得到目标密钥sgk_sel和sgsk_sel。然后将参数a3与两个目标密钥相加，最后链接上相加后字符串的长度作为待签名数据

对累加后的字符串，根据上面计算的v28数字选择不同的签名算法，最后再转为String，即得到签名sg的值：

- v28大于5，使用SHA1算法签名，即：SHA1(a3+sgk_sel+sgsk_sel+长度)
- v28小于5，使用MD5算法签名，即：MD5(a3+sgk_sel+sgsk_sel+长度）

![image](https://bbs.kanxue.com/upload/attach/202311/978841_H8JM2JX5BPQYAVF.webp)

基于上述分析，就可以编写一个简单的python request请求。通过请求就能获取到正确的返回数据了：

![image](https://bbs.kanxue.com/upload/attach/202312/978841_3M2XNS8P6HFWUSE.webp)

---

# 回复

## 回复 by kreas (#2)

*2024-3-18 16:52*

厉害

## 回复 by zx_994305 (#3)

*2024-3-21 18:21*

学习了

## 回复 by azd放 (#4)

*2024-3-21 21:05*

感谢分享

## 回复 by 夜夜夜夜夜 (#5)

*2024-3-26 13:49*

感谢，有apk链接吗

## 回复 by Aimees (#6)

*2024-3-26 14:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  夜夜夜夜夜](https://bbs.kanxue.com/user-979560.htm)
>
>  感谢，有apk链接吗
>
>

https://www.oppomobile.com/  包名com.heytap.market

## 回复 by 夜夜夜夜夜 (#7)

*2024-3-26 14:57*

>
> [Aimees](https://bbs.kanxue.com/user-978841.htm)
>
>  https://www.oppomobile.com/ 包名com.heytap.market
>
>

感谢大佬

## 回复 by iHTCboy (#8)

*2024-3-28 09:27*

感谢大佬，能私发一份Python吗 ，ihetiancong#gmail.com

## 回复 by ICenE (#9)

*2024-4-18 20:00*

大佬为什么我的ida在分析key2进入c函数的时候没有findclass那样的函数呀，全是偏移量获取地址那种调用

## 回复 by Aimees (#10)

*2024-4-19 09:52*

选中函数的第一个参数，按键盘【y】 ，把第一个参数的类型改成JNIEnv *

## 回复 by iBa0 (#11)

*2025-7-30 23:08*

好羡慕 现在的so都是一坨，没有这么清晰的

## 回复 by xxdppyy (#12)

*2025-8-29 10:39*

感谢大佬，能私发一份Python吗 ，1651379304@qq.com
