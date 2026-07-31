---
title: flutter抓包绕过
url: https://bbs.kanxue.com/thread-280261.htm
tid: 280261
author: puppet_w
date: '2024-01-19'
tags: [Android安全, 逆向分析]
crawled_at: '2026-07-31T14:33:15+08:00'
replies: 14
---

# flutter的证书校验

## 起因：

最近工作上让做个app的复测，把apk发我后，开始尝试挂代理抓包，结果发现抓不到
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_TSGQEJM832T2GA5.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_XG46U2PTF65FVHF.webp)
以为是证书没弄好，想着前几天不是刚导入了吗（雾）。又重新导入了下还是不行。然后各种lsp模块，objection都不行，r0capture也没数据。
然后jadx看了下，全是flutter字样，才想起来和flutter有关。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_ZTRC35SRJJWA7SV.webp)

## 开始百度（：

然后就开始各种找。<https://bbs.kanxue.com/thread-261941.htm>
根据上面文章找到关键函数[handshake.cc](https://github.com/google/boringssl/blob/master/ssl/handshake.cc)386行
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_9XV6PNCPGF5BT7N.webp)
session_verify_cert_chain函数在第356行的[ssl_x509.cc](https://github.com/google/boringssl/blob/master/ssl/ssl_x509.cc)中被定义
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_ESQRB8WCACSE87F.webp)
然后根据<https://bbs.kanxue.com/thread-261941.htm> 这篇文章特征找，但是这个是32位的，所以在app安装的时候指定32位安装

| 1 | `adb install` `-``-``abi armeabi``-``v7a <path to apk>` |
|-|-|

接下来就是找
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_UD2GWE34RX7MRFZ.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_QJ98WF3PZ5Z2NB5.webp)
往上翻找
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_3S6SFETA8NUZNMB.webp)

# 写脚本绕过

## 32位

| 1234567891011121314151617181920212223242526272829 | `function hook_ssl_verify_result(address) {``Interceptor.attach(address, {``onEnter: function(args) {``console.log(``"Disabling SSL validation"``)``},``onLeave: function(retval) {``console.log(``"Retval: "` `+` `retval);``retval.replace(``0x1``);``}``});` `}``function hookFlutter() {``var m` `=` `Process.findModuleByName(``"libflutter.so"``);``var pattern` `=` `"2D E9 F0 4F 85 B0 06 46 50 20 10 70"``;``var res` `=` `Memory.scan(m.base, m.size, pattern, {``onMatch: function(address, size){``console.log(``'[+] ssl_verify_result found at: '` `+` `address.toString());``/``/` `Add` `0x01` `because it's a THUMB function``/``/` `Otherwise, we would get` `'Error: unable to intercept function at 0x9906f8ac; please file a bug'``hook_ssl_verify_result(address.add(``0x01``));` `},``onError: function(reason){``console.log(``'[!] There was an error scanning memory'``);``},``onComplete: function() {``console.log(``"All done"``)``}``});``}` |
|-|-|

然后启动就可以抓包了
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_TQN6MDMT2UK54QD.webp)

## 64位

搜索ssl_client
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_WEWW2HWDVQQWQAP.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_2CA6YZ39K287ZNC.webp)
照例往上找
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_SPZB6G8SCCXUJDE.webp)
然后就找到了这些

| 123456789 | `.text:``0000000000596870` `FF C3` `01` `D1                 SUB             SP, SP,` `#0x70``.text:``0000000000596874` `FD` `7B` `01` `A9                 STP             X29, X30, [SP,``#0x70+var_60]``.text:``0000000000596878` `FC` `6F` `02` `A9                 STP             X28, X27, [SP,``#0x70+var_50]``.text:``000000000059687C` `FA` `67` `03` `A9                 STP             X26, X25, [SP,``#0x70+var_40]``.text:``0000000000596880` `F8` `5F` `04` `A9                 STP             X24, X23, [SP,``#0x70+var_30]``.text:``0000000000596884` `F6` `57` `05` `A9                 STP             X22, X21, [SP,``#0x70+var_20]``.text:``0000000000596888` `F4` `4F` `06` `A9                 STP             X20, X19, [SP,``#0x70+var_10]``.text:``000000000059688C` `08` `0A` `80` `52`                 `MOV             W8,` `#0x50``.text:``0000000000596890` `48` `00` `00` `39`                 `STRB            W8, [X2]` |
|-|-|

然后写脚本

| 1234567891011121314151617181920212223242526272829 | `function hook_ssl_verify_result(address) {``Interceptor.attach(address, {``onEnter: function(args) {``console.log(``"Disabling SSL validation"``)``},``onLeave: function(retval) {``console.log(``"Retval: "` `+` `retval);``retval.replace(``0x1``);``}``});` `}``function hookFlutter() {``var m` `=` `Process.findModuleByName(``"libflutter.so"``);``var pattern` `=` `"FF C3 01 D1 FD 7B 01 A9 FC 6F 02 A9FA 67 03 A9 F8 5F 04 A9 F6 57 05 A9 F4 4F 06 A9 08 0A 80 52 48 00 00 39"``;``var res` `=` `Memory.scan(m.base, m.size, pattern, {``onMatch: function(address, size){``console.log(``'[+] ssl_verify_result found at: '` `+` `address.toString());``/``/` `Add` `0x01` `because it's a THUMB function``/``/` `Otherwise, we would get` `'Error: unable to intercept function at 0x9906f8ac; please file a bug'``hook_ssl_verify_result(address.add(``0x01``));` `},``onError: function(reason){``console.log(``'[!] There was an error scanning memory'``);``},``onComplete: function() {``console.log(``"All done"``)``}``});``}` |
|-|-|

然后发现报错了
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_5DS32UZ3R35GP5D.webp)
把hook_ssl_verify_result(address.add(0x01))改为hook_ssl_verify_result(address)就可以正常使用了
 ![图片描述](https://bbs.kanxue.com/upload/attach/202401/929264_PBVYKHQ59MR3MX6.webp)

# 参考：

<https://www.jianshu.com/p/ada10d2976f2>
<https://mp.weixin.qq.com/s/pXpfXK-Ez0n70f3bqFuuFg>
<https://bbs.kanxue.com/thread-261941.htm>
<https://blog.nviso.eu/2019/08/13/intercepting-traffic-from-android-flutter-applications/>
以上四篇文章均是和flutter证书校验相关

---

# 回复

## 回复 by shuyangzjg (#2)

*2024-1-19 16:59*

向大佬学习

## 回复 by erichyx (#3)

*2024-1-19 21:57*

直接用VPN抓包不就行了

## 回复 by 秋狝 (#4)

*2024-1-20 21:43*

感谢分享

## 回复 by puppet_w (#5)

*2024-1-22 08:36*

-

## 回复 by puppet_w (#6)

*2024-1-22 08:36*

>
> [erichyx](https://bbs.kanxue.com/user-371779.htm)
>
>  直接用VPN抓包不就行了
>
>

VPN不行的

## 回复 by mb_ezphxtar (#7)

*2024-1-22 11:53*

求个样本

## 回复 by puppet_w (#8)

*2024-1-22 16:45*

>
> [mb_ezphxtar](https://bbs.kanxue.com/user-909258.htm)
>
>  求个样本
>
>

样本哇，好像是工作项目中的，不太能分享，不好意思哈

## 回复 by mb_ezphxtar (#9)

*2024-1-22 22:22*

>
> [puppet_w](https://bbs.kanxue.com/user-929264.htm)
>
>  样本哇，好像是工作项目中的，不太能分享，不好意思哈
>
>

好的感谢~

## 回复 by mb_ekitlujo (#10)

*2024-1-25 10:11*

大佬666

## 回复 by shinratensei (#11)

*2024-1-25 13:11*

tql

## 回复 by 司徒废人 (#12)

*2024-1-29 10:02*

sockets转发+external proxy也可以抓包的

## 回复 by axyzyz (#13)

*2024-3-6 22:47*

一开代理系统就提示退出

## 回复 by mb_plkucays (#14)

*2024-3-16 04:12*

大神能帮忙解决风控的问题吗

## 回复 by 暮至夜寒 (#15)

*2025-4-7 16:48*

大佬，遇到了Memory.scan报错Error: access violation accessing 0x7374889000，这是什么问题呀
