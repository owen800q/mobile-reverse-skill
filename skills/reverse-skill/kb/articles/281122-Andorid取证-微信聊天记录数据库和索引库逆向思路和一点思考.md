---
title: '[原创]【Andorid取证】微信聊天记录数据库和索引库逆向思路和一点思考'
url: https://bbs.kanxue.com/thread-281122.htm
tid: 281122
author: PengLaiDoll
date: '2024-03-28'
tags: [Android安全, 原创, 逆向分析, 其他]
crawled_at: '2026-08-12T04:01:52+00:00'
replies: 10
---

看到 @行简 大佬采用Hook的方法对微信数据库解密，深受启发。前段时间正好在做微信相关的项目，这里分享一下我自己逆向的思路，如有谬误，还请大佬批评指正
注：本文所提供方法仅供逆向学习参考，请勿用于违法犯罪，所产生的的一切后果由用户自行承担责任

# 前期调研

随着微信多次更新，微信数据加密的方式多次更改，应该是从微信的某个大版本开始引入聊天记录数据库SQLCipher加密，密钥为md5（IMEI+UIN）.substring(0,7)，到了微信8.0版本，更改了加密方式，猜测是因为Android10原有的API无法再提供手机的IMEI码，便更改了加密方式。聊天记录索引库在微信早期版本命名为“IndexMicroMsg.db”；6.6版本后更新命名为““FTS5IndexMicroMsg.db”，新增全文检索功能；微信7.0版本将命名改为“FTS5IndexMicroMsg_encrypt.db”，将索引文件也进行了加密，二者密钥并不相同

# 工具和环境

微信 8.0.19
Jeb
DB Browser

# 逆向思路

因为是纯分析代码，可能会有些繁琐，估将一些步骤省略，只贴一些关键函数

## 文件搜集

用户UIN位置：/data/data/com.tencent.mm/shared_prefs/auth_info_key_prefs.xml
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_43GNNFZ9MUCK552.webp)
聊天记录数据库文件：'/data/data/com.tencent.mm/MicroMsg/[用户IDmd5]'
索引文件：'/data/data/com.tencent.mm/MicroMsg/[用户IDmd5]/FTS5IndexMicroMsg_encrypt.db'

## 逆向思路

### 数据库文件解密

因为与数据库相关，所以可以直接定位包名为com.tencent.mm和com.tencent.wcdb
明文搜索“EnMicroMsg.db”定位到可疑函数（因为也有个数据库初始化的过程，其中也会有这个明文，注意分析）
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_9EMUFZHB5BE9HY6.webp)
这里还可以看到数据库备份文件相关代码，我们先不管着重分析一下下面的加密代码
明文变量key直接给出，getmessageDeigest跟踪进去是md5
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_7HVWPPCMGYGMEN2.webp)
下面我们需要知道的就是其中的两个变量q.eD(true)和arg12
先看q.eD(true)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_737MBTCKJ4KUTWK.webp)
其实从传入参数看就已经知道该函数返回值为"1234567890ABCDEF"
后面看了一下上面的函数，发现一步一步往里面跟踪可以找到获取用户IMEI的函数，应该是被弃用了。
再看arg12，改了一下名为j2，交叉引用查看，定位到唯一用例,
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_QA8ZT6JWAFKSVJ5.webp)
b函数也传入了j2，这里的j2是由a函数传入的，为第四个参数
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_HGCKBTRDHTPS4A3.webp)
查看函数a的交叉引用，也是唯一的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_4C2RVFHVF2H8529.webp)
由另一个函数b传入，继续交叉引用，找到调用
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_AU8M2PEYUQM2DTF.webp)
可以由名字推知arg12也就是j2就是用户UIN
由此可以得出聊天记录数据库文件加密方式：md5("1234567890ABCDEF"+[UIN]).substring(0,7)

### 索引库文件解密

因为索引库肯定是在数据库文件初始化之后才生成，且使用FTS，可以直接顺着逻辑在com.tencent.mm.plugin.fts包中往下找
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_TDEUJMC92QUDX35.webp)
还是三个字符串拼接，第一个最后返回值还是UIN，第二个是“1234567890ABCDEF”,第三个我们跟踪一下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_H7UWBGA93W9HVUD.webp)
这里注意一下log，先把代码放在这里

### 数据库查看

先将上面的密钥试着解一下数据库，当然是可以解开的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_PP87GFHHEWQWHY6.webp)
这里注意，我们看到了userinfo的表，结合上面索引库的Log，便有了一些想法，先看一下这个表
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_RR44HSJGDUDXTXB.webp)
里面有userid这个东西，推测一下，第三个字段可能就是用户id
这样索引文件的密钥就是md5([UIN]+"1234567890ABCDEF"+[USERID]).substring(0,7)

# 后期补充和一些思考

抱着试一试的想法去更改了一下数据库内容，试一下能不能实现聊天记录的篡改，结果成了。。。。具体操作过程就不再提供了（虽然试了一晚上只成功了一次）
 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/927366_B5P6UF5FXT9MS36.webp)
对数据库记录进行更改，然后使用adb pull指令将原有文件进行替换，重新登陆微信，微信会自动检测到索引文件与聊天记录数据库不符，是否进行修复。如果不进行修复，那么索引文件就不会重新索引，索引文件中的原有记录不会改变；如果修复，则会重新启动微信，根据数据库文件进行重新索引
虽然目前还没有见到改微信聊天记录的，但确实能通过修改数据库并替换的方式实现聊天记录的篡改，现在微信聊天记录也具有法律效益了，我觉得以目前的取证工作来说，聊天记录的法律上的有效性检测仍需进一步努力
另外提供一个可以检测篡改的思路，不知可行性怎么样
微信在更新版本时会生成上文中提到了一个数据库文件的备份，那个的加密方式好像和聊天记录数据库大致但又不完全相同，是用来微信版本更新恢复聊天记录的，可以作为判断聊天记录是否篡改的依据

---

# 回复

## 回复 by mb_fidppcok (#2)

*2024-3-28 14:25*

向大佬学习下

## 回复 by 秋狝 (#3)

*2024-3-29 14:02*

感谢分享

## 回复 by zylrocket (#4)

*2024-3-30 03:11*

玩的很专业呀

## 回复 by gamehack (#5)

*2024-3-30 08:08*

666,学习一下!

## 回复 by mb_mjzezdid (#6)

*2024-9-28 17:36*

大佬，FTS5IndexMicroMsg.db库中的data表怎么解密

## 回复 by alds (#7)

*2024-11-2 16:42*

篡改他的数据库应该简单点，有root权限的话直接加载他的apk，反射获取数据库操作类，之后就能随便操作他的数据了

## 回复 by mb_yxljnnks (#8)

*2024-12-12 15:32*

求助大神帮忙查看删除的微信好友的聊天记录，有偿

## 回复 by mb_yxljnnks (#9)

*2024-12-13 22:35*

我老婆出轨了 现在还在和那个人联系 我想看下他们的聊天记录   我想挽救家庭    孩子才2岁半 求大神帮帮忙

## 回复 by illusion0088 (#10)

*2025-5-28 18:40*

大佬为什么我按照你的解密方法实现不了

## 回复 by 达沙迪奥 (#11)

*2026-2-11 11:41*

大佬，用户UIN是负数咋办
