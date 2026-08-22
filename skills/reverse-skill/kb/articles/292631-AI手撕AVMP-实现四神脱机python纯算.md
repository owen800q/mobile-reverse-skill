---
title: '[原创]AI手撕AVMP，实现四神脱机python纯算'
url: https://bbs.kanxue.com/thread-292631.htm
tid: 292631
author: 程序员小潘
date: '2026-08-20'
tags: [Android安全, 原创, 逆向分析, 协议分析]
crawled_at: '2026-08-22T04:03:25+00:00'
replies: 12
---

版本：v10.65.0（2026-08-07）

这篇不是教程，是一份复盘。先看一波成果：

![image](https://bbs.kanxue.com/upload/attach/202608/877942_MT7HFTMQ2HSQTY2.webp)

没有用到任何unidbg等模拟执行框架，纯手撕代码还原avmp逻辑，生成的签名服务器直接通过。没有报FAIL_SYS_ILEGEL_SIGN/FAIL_SYS_REQUEST_EXPIRED

这7个签名都什么含义？a1=doCommandNative(70102, args) 里 args[1]

| 头 | 含义 | 怎么来的 / 算法 |
|-|-|-|
| x-t | 时间戳(秒) | 直接取当前时间。和 a1 里的 t 字段是同一个值 |
| x-utdid | 设备号(24字符 base64) | 设备唯一标识。也嵌在 a1 里,头和 a1 必须一致 |
| x-devid | deviceToken | mtop.sys.newdeviceid 注册返回的设备凭证。也嵌在 a1 里 |
| x-umt | base64(umid) | umid 是 24 字节设备 token |
| x-sgext | 设备指纹 A | SG native 采集→组装成 _N_ 字段表→2字节XOR编码→base64。字段=设备id/分辨率/传感器/时间戳/加密nonce |
| x-mini-wua | 设备指纹 B | SG native 生成的另一种 wua blob,高熵 crypto |
| x-sign | 主签名 | 见下,核心 |

前 4 个是"设备身份 + 时间",直接填就行。后面 x-sgext / x-mini-wua 是两个设备指纹。真正的密码学在 x-sign。

  a1 = utdid &&& appkey & md5(body) & t & api & v && ttid & token &&& openappkey=... & features & ...

                                ↑绑请求      ↑绑时间           ↑设备凭证

  APPENDED = '&' + x-mini-wua + '&&' + x-sgext          ← 两个指纹头拼进来

  c434   = md5( a1  ‖  APPENDED )                        ← 标准 md5,输出 16 字节

  x-sign = 固定前缀 azYBCM007xAA + base64( 白盒变换(c434) )  ← 填进一个 102 字符的模板

  所以一条 x-sign 里其实"锁"进了:请求 body(md5)、时间(t)、设备号(utdid)、设备凭证(token)、两个设备指纹(经

  APPENDED)。改任何一个,c434 就变,x-sign 就变。服务端拿收到的这些原料重算一遍对比——这就是为什么 4

  个头必须同一次签名、共享 nonce,单独换一个就 ILLEGAL_SIGN。

TaobaoSigner.PROG 是什么

这是整个东西的核心资产。PROG = 我从白盒虚拟机里逆出来的 c434 → x-sign 那段变换,以"直线程序"的形式存下来。

这是一套 threaded-code 风格的 VM：253 个 handler，18000 多个唯一节点（还带循环），线程码存的是数据指针不是 handler 指针。每个 handler 干净得像 RISC 指令——一条 VM 指令 + 统一的 dispatch 尾巴

\```
ldrh w4, [x21, #0x10]!      ; 取下一个 opcode
ldr  x3, [x23, x4, lsl#3]   ; 查 handler 表
br   x3                     ; 跳过去
\```

白盒加密全塞在里面。标准的 md5/sha1/sha256 常量表（那 64 个 md5 K 值、各种 IV）我全在内存快照里翻到了——都是 app 启动时解密到堆上的，不是网络下发（有人问过我"这 VM 哪来的"，就是这么来的，本地解密，非动态）。

这里我要吐槽一句：avmp 这套东西最恶心的不是它多难，是它把一个本来几十行的 md5 摊成了几十万条 VM 指令，白盒混淆再糊一层，你想直接抠密钥是抠不出来的——消息、IV、状态全在 VM 寄存器里扩散。黑盒到头了，唯一的路是完整 devirt，把 VM 提升回可读的算法。

  背景:c434 → x-sign 这一段在 SG 里是跑在 avmp 白盒 VM 里的,几十万条混淆指令。我用符号执行,把 c434 的 16

  字节设成符号,跑一遍下游,把所有 a1 无关的具体值折叠掉,只保留对 c434 的依赖,最后压成 5533

  步、无循环无分支的一串运算。这一串就是 PROG。

  结构上,PROG 是一个列表,每一项是 (op, args):

  - op 是运算类型:in / memld / extract / add / sub / and / orr / eor / lsl / lsr / ror / mul / mvn / sxtb ...(基本是 ARM

  ALU 那套)。

  - args 里的每个参数,要么是立即数,要么是 [节点下标]——引用前面某一步算出来的结果。等于一张 SSA 式的数据流图。

  _transform(c434) 就是这张图的解释器,顺序求值 val[i] = op(参数):

  - in → 读 c434 的某个字节(算法的唯一输入);

  - memld → 从内嵌的常量表 TBL 里查值(那 22 处 base64 编码查的就是标准 base64 字母表,其余是白盒常量);TBL_BASE

  是这张表的基址,用来把地址换成表内偏移;

  - 其余 add/eor/lsl/... → 白盒的位运算;

  - 最后 OUT 把某些节点的值映射到 x-sign 的具体字符位;

  - XTMPL 是 x-sign 的固定模板(前缀那些恒定字符),_transform 只往里填会变的中间那几十位。

  一句话:PROG 就是把"跑一遍白盒虚拟机"替换成了"顺序算 5533 步纯运算"。没有 VM、没有循环、零第三方依赖,所以能纯 Python

  1ms 出签名。配套的 TBL(常量表)、OUT(节点→输出位映射)、XTMPL(模板)、APPENDED(指纹常量)都是同一次 trace 一起抠出来的。

  顺带对照下另外几个类属性,一起就懂了:

  - PROG = c434→x-sign 的直线程序(算法本体)

  - TBL / TBL_BASE = 它读的白盒常量表(含 base64 表)

  - OUT = 哪个节点的第几字节 → x-sign 的哪一位

  - XTMPL = x-sign 固定模板

  - APPENDED = 塞进 md5 的两个指纹头(设备相关)

  所以严格说,x-sign 的算法 = md5 (标准) + PROG 这段逆出来的白盒直线变换。前者是通用的,后者是这个 app 版本 / 这次 trace

  专属的——换版本(libsgmainso 变)就得重抠一份 PROG。

    回头看，难点到底在哪

1. 混淆的心智负担。avmp 把简单算法摊成几十万条 VM 指令，你面对的不是"这个 md5 怎么算"，而是"这几十万条指令里哪一段是 md5、我的重执行器有没有哪个 handler 语义写错了"。100% 字节对拍是唯一能让你安心往下走的东西——差一个字节，整条链后面全崩。
2. 提取代码的 bug 会伪装成算法的难题。那个多读 2 字符的 off-by-one，让我围着不存在的"尾部 MAC"逆了好几天。教训是：结果不对时，先怀疑自己 dump / 截断 / 对齐的代码，别一上来就假设是算法没逆干净。
3. 动态输出把静态分析的直觉全打乱。时间、nonce、轮换的 umid，任何一个对不上都是 ILLEGAL_SIGN，而报错信息只有一个，你分不清是哪一环。靠的是在真机上做控制变量的对照实验，一次只动一个量，把服务端每一条校验规则单独钉死。

---

# 回复

## 回复 by wx_插曲 (#2)

66

## 回复 by ATrueMan (#3)

study

## 回复 by ATrueMan (#4)

看不到图呢

## 回复 by Steesha (#5)

楼主的图炸了，重新上传一下吧～
所以只是静态重放了x-sign吗，x-mini-wua的算法有没有解出来呢？
还有个小问题，就是算法是模拟执行了VM的字节码吗～我看第一张图下面有一堆VM字节码？楼主是否把VM整个还原到了单个函数呢![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by mb_ldztajei (#6)

去弄一下eeid的生成 那个有意思

## 回复 by xtyuns (#7)

666

## 回复 by mb_hwzomkxk (#8)

内容的图没了

## 回复 by 九黎 (#9)

tql

## 回复 by 程序员小潘 (#10)

>
> [Steesha](https://bbs.kanxue.com/user-901773.htm)
>  楼主的图炸了，重新上传一下吧～
> 所以只是静态重放了x-sign吗，x-mini-wua的算法有没有解出来呢？
> 还有个小问题，就是算法是模拟执行了VM的字节码吗～我看第一张图下面有一堆VM字节码？楼 ...
>

不是重放，重放会EXPIRED/ILLEGAL_SIGN，你仔细看x-sign中间部分是有变化的。现在的vm相当于是把253个handle提升成ir来跑，不跑.so不用unicorn

## 回复 by 程序员小潘 (#11)

>
> [ATrueMan](https://bbs.kanxue.com/user-968999.htm)
>  看不到图呢
>

这排版。。。我有空再重新整理下吧~

## 回复 by Steesha (#12)

>
> [程序员小潘](https://bbs.kanxue.com/user-877942.htm)
>  不是重放，重放会EXPIRED/ILLEGAL_SIGN，你仔细看x-sign中间部分是有变化的。现在的vm相当于是把253个handle提升成ir来跑，不跑.so不用unicorn
>

楼主方便提供一下 .so 的版本和位置吗，本人很有兴趣研究一下，并复现你的这个文章

## 回复 by livy (#13)

楼主真强
