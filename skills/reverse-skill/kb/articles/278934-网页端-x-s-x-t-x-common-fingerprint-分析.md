---
title: '[原创] 网页端 x-s，x-t，x-common，fingerprint 分析'
url: https://bbs.kanxue.com/thread-278934.htm
tid: 278934
author: wbwnnx
date: '2023-09-19'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:38:00+08:00'
replies: 3
---

其实最早改版的时候我就还原出来了，至于为啥没发，毕竟人家刚改版。
以下只是思路，没有算法也不要问我要算法，我不做那个，只是研究学习。

# 进入正题：

三个参数X-S，X-S-Common，X-T, 先说下我的思路，我是找到了一个/webprofile的接口，这个有的人应该比我懂，data里面长这样
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_N5FHXCW62WN3QY7.png)

## 1、fingerprint

这个profiledata就是浏览器一堆环境，我最开始破解的版本是3.3.3，看来这已经升级了，但估计大体没变化。咱们直接搜索profiledata。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_J9RSB6RNZ3N9DCF.png)
我们先下断o.getv18, reportBroswerInfo_awaiter和reportBroswerInfo_generator
vmp文件就在window.xhsFingerprintV3.getV18里面，点进去看看大体框架，我只能说跟某程的加固框架是同一个，特征很明显。等过一会再写一个testab的文章哈哈哈

咱们随机先下一个断点log，随便输出什么都可以，然后步过执行发现reportBroswerInfo_awaiter和reportBroswerInfo_generator都没有日志输出，而且等reportBroswerInfo_generator之后 n 就已经出来了，说明getv18里面就是一个整体流程。

然后就开始下日志断点，搜索apply一些关键点来下，观察一下作用域里的值，那些是用来存储数据的哪些是用来存储指令集的，第一次多下一点一点一点缩小范围减少日志输出。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_29GPZ374KXE2PAJ.png)
比如这都调用charcodeat了，那说明就开始算法的加密了，直接设置条件断点设置字符串等于charcodeat中断

断下之后打开闭包数据找一找，发现了这么一堆，看到ey开头赶紧拿去base64解码，这个搞多了都懂。
![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_D7Y2V8Y4EZF54QC.png)
出来是这么个东西
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_FUWCWJ5C4VPBY2S.png)
这就是初始化的浏览器环境，这省事了，直接下这个变量的日志断点就可以了，然后观察值的变化，发现v18结束，这个值确实出来了。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_43UX2HF6YB42AJQ.png)
这一看就是16进制的数据，直接复制出来看最后两位F3十进制是243，直接控制台往上翻，确实对应上了，82的十进制也是130
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_Q48KXT9CB8XKPDW.png)
看下这个数组长度是8，那说明这个是个分组加密，上面的日志还有很多，这里就不说了，说到这基本算法都能猜出来了，就差还原了，也是继续下log，这次log就下在微运算上，把微算法分析在拼接。
幸亏是对称加密，结果不变，不然都不好断。
所以初始位置暂定为 192, 88 来断点这是加密结果开头的两个十六进制。
断下之后我们一步一步往下走，就开始发现每8个字节进行加密了，后续把这个charcodeat的日志打全或者单步就发现这些字节就是上面base64的指纹。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_9K7387A55U7QFQ9.png)
后面的流程上面也说过了，就开始拼接微运算的算法，结果大致如下。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_62JZMBYH76UGBU7.png)
发现运算的时候还会去取一些固定的数组的值，就是最开始截图的数据存储的地方
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_EHJ5N6QSFJDWS96.png)
等还原结束我才发现了这个算法其实调用库会非常简单，key在我还原的时候已经发现了，但是不能说哈哈哈，最后就是8个一组的数据，转16进制。至此这个指纹就到这了，具体收集什么就不讲了，得挨个去分析。

## 2、x-s, x-t

然后我们继续往下走的时候发现开始开始获取x-s,x-t了，就是一个三元表达式，这个对象没有就走老的sign，有的话就走新的。
进去也是vmp，但是不是同一个vmp文件
![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_363FZ9WPKKSRZ86.png)
老办法还是上断点，先断apply一些重要的，最后的base64也是标准的，直接把这个x-s先解码
![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_TDFZG5WKMQ5ZNCE.png)
这个playload跟那个data不能说完全一样那也大差不大了，我当时感觉就是用的同一个算法，后面看了一眼还真是，就是key不一样 ，算法怎么追data已经讲过了，直接找原文就行了。
![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_NHYTBQPSYP5MHQC.png)
同上像上面一样断65，ce的10进制是最简单的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_7BJVKDNAPDM5S4Y.png)
然后发现一段字符串，x1是url的md5，我校验过没有魔改，x2是浏览器环境，x3是local_id，这个local_id就是随机的字符串和时间戳还有platform和校验码组成的，x4就是x-t。
'x1=6667296f17398985a2a087300d1474e4;x2=0|0|0|1|0|0|1|0|0|0|1|0|0|0|0;x3=1899576b2c4e9kacvosh7lks0930l0gtkf07f0qjv30000393857;x4=1695126119863;'
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_JVHKVSFQV7XQ9HQ.webp)
然后发现也是8个一组在运算，只是key不同，到这x-s就完事了.

## 3、x-common

重点说一下这个common，听别人说获取游客id必须要，之前还不是那么重要。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_NBGNA9JKS64XN9R.png)
这里面的算法就有说法了，重点是这个玩意，他是在localStorage存储直接hook一下set看看堆栈，发现他是初始化的时候在fingerprint之前就存储了，跟fingerprint同一个vmp
![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_3KRYC2RSBAEY7MV.png)
然后就是trace微运算还原之后，其实就是fingerprint里面个别的字段，看着就是一堆环境，进行了rc4和魔改base64，里面还有字符串的运算。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_Q2TVGBERDQG3N7J.png)
像这些混淆直接ast还原在还原成python就行了，很简单
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_NWG5J7ED8NYYR3X.png)

到这common就结束了，后面写着写着想水文章了，发现我的字数一段比一段少

验证: 先获取游客id，然后就可以请求通了，但是大部分还是要登录的

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/921346_5EBKNHAWR5M6HQ7.webp)

---

# 回复

## 回复 by 秋狝 (#2)

*2023-9-20 10:36*

感谢分享

## 回复 by mb_xubwvtdx (#3)

*2023-9-20 11:13*

这很屌啊 感谢分享

## 回复 by dontaskme (#4)

*2023-10-13 23:14*

大佬私信联系方式
