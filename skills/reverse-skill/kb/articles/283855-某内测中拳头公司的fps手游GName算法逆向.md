---
title: '[原创]某内测中拳头公司的fps手游GName算法逆向'
url: https://bbs.kanxue.com/thread-283855.htm
tid: 283855
author: blackr0ck
date: '2024-10-10'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:19:17+08:00'
replies: 4
---

# 0x0 序言

前段时间研究了一下某游戏的GName算法，水一篇文章记录一下，以下简称该游戏为C手游。

# 0x1 静态分析

首先先dump并修复libUE4.so，拖进IDA看一下。ida解析完成后，搜ByteProperty，找到引用的函数 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_BA9QH4Q67XQB6QC.webp)
正常来说找函数调用，这个函数的参数就是全局变量FNamePool的指针，也就是GName，但是C手游的查引用后发现，只有一个函数sub_562B820调用过这个sub_5627A0C
 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_QSTEA8BUFK9UUHM.webp)
其中这个v1就是本该是一个GName的值，再对sub_562B820查一次调用，随便进去一个函数，发现sub_562B820这个函数的返回值貌似返回的就是fnamePool的地址

| 12 | `/``/``sub_562B20的返回算法``return` `*``(_QWORD` `*``)(byte_9B0A620[(unsigned` `int``)off_9B0A6A0] \| (unsigned __int64)(unsigned __int16)(byte_9B0A620[dword_9B0A6A4] <<` `8``) \| ((unsigned __int64)byte_9B0A620[dword_9B0A6A8] <<` `16``) &` `0xFFFF000000FFFFFFLL` `\| (byte_9B0A620[(unsigned` `int``)off_9B0A6AC] <<` `24``) \| ((unsigned __int64)byte_9B0A620[dword_9B0A6B0] <<` `32``) &` `0xFFFF00FFFFFFFFFFLL` `\| ((unsigned __int64)byte_9B0A620[dword_9B0A6B4] <<` `40``) \| ((unsigned __int64)byte_9B0A620[dword_9B0A6B8] <<` `48``) \| ((unsigned __int64)byte_9B0A620[(unsigned` `int``)off_9B0A6BC] <<` `56``));` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_54RDNGJ7XMH9TNJ.webp)
猜测他是通过byte_9B0A620这个数组，以一定的算法去动态生成FNamePool的地址，不像其他UE4游戏，内存中没有指向他的全局变量。

# 0x2 动态分析

那既然静态分析完了，那就实际来验证一下这个想法对不对吧。
首先先搜一下ByteProperty
 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_P5GATK6V2VPRQVY.webp)
找到FNamePool，然后搜索一下0x7325610000引用，果然没有全局变量指向这个地址。对这个地址下个断点，查一下调用栈

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849 | `[``13432``\|``13587``] event_addr:``0x7325610000` `hit_count:``320``, Backtrace:` `#00 pc 000000000562aeb4  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#01 pc 000000000562cf34  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#02 pc 00000000059db020  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#03 pc 0000000003dac2dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#04 pc 00000000059e29c0  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#05 pc 0000000006cb6fe0  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#06 pc 00000000058dc80c  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#07 pc 00000000057b92dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#08 pc 00000000057b9410  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#09 pc 0000000005876ecc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#10 pc 00000000057ae080  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#11 pc 00000000058de858  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#12 pc 00000000058de1ac  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#13 pc 00000000058dde28  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#14 pc 00000000058dc814  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#15 pc 00000000057b92dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#16 pc 00000000057b9410  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#17 pc 0000000005876ecc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#18 pc 00000000058681b0  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#19 pc 00000000057ae080  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#20 pc 00000000058de858  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#21 pc 00000000058de1ac  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#22 pc 00000000058dde28  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#23 pc 00000000058dc814  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#24 pc 00000000057b92dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#25 pc 00000000057b9410  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#26 pc 0000000005876ecc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#27 pc 00000000057ae080  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#28 pc 00000000058de858  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#29 pc 00000000058de1ac  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#30 pc 00000000058dde28  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#31 pc 00000000058dc814  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#32 pc 00000000057b92dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#33 pc 00000000057b9410  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#34 pc 0000000005876ecc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#35 pc 00000000058681b0  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#36 pc 00000000057ae080  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#37 pc 00000000058de858  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#38 pc 00000000058de1ac  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#39 pc 00000000058dde28  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#40 pc 00000000058dc814  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#41 pc 00000000057b92dc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#42 pc 00000000057b9410  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#43 pc 0000000005876ecc  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#44 pc 00000000057ae080  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#45 pc 00000000058de858  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#46 pc 00000000058de1ac  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#47 pc 00000000058dde28  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so``#48 pc 00000000058dc814  /data/app/~~xxx_xxxxxxxxxxx==/com.xxxxxxx.xxxx.xxxxx-xxxxxxxxxxxxxxx==/lib/arm64/libUE4.so` |
|-|-|

进562cf34这个地方看一下
 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_2FJA4EK7QCHR7ET.webp)
果然跟之前猜测的差不多，写个frida脚本试试能不能生成类名

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `function getName(index){``var f_addr` `=` `moduleBase.add(``0x562b820``);``/``/` `将目标函数地址转换为JavaScript函数``var getGnameFunc` `=` `new NativeFunction(f_addr,` `'uint64'``, []);` `/``/` `调用目标函数并传递内存地址作为参数``try``{``var gname` `=` `getGnameFunc();``console.log(`GName: ${gname}`);``/``/` `dumpVector(buf);``/``/``info(ptr(actor_addr).add(``0x130``).readPointer().add(``0x14c``).readU8()&``32` `!``=` `0``);``}``catch (e){``console.log(e)``}``var offset_FNameEntry_Info` `=` `0``;` `var Block` `=` `index >>` `16``;``var Offset` `=` `index &` `65535``;` `var FNamePool` `=`  `gname;``/``/` `console.log(`FNamePool: ${FNamePool}`);``console.log(`Block: ${Block}`);``var NamePoolChunk` `=` `ptr(FNamePool).add(``0x40``).add (Block``*``8``).readPointer();``console.log(`NamePoolChunk: ${NamePoolChunk}`);``var FNameEntry` `=` `NamePoolChunk.add((``0x2` `*` `index)&``0x1FFFE``);``console.log(`FNameEntry: ${FNameEntry}`);``try` `{``if` `(offset_FNameEntry_Info !``=``=` `0``) {``var FNameEntryHeader` `=` `FNameEntry.readU16();``}` `else` `{``var FNameEntryHeader` `=` `FNameEntry.readU16();``}``} catch (e) {``/``/` `console.log(e);``return` `"";``}``console.log(`FNameEntryHeader: ${FNameEntryHeader}`);``var str_addr` `=` `FNameEntry.add(``0x2``);``console.log(`str_addr: ${str_addr}`);``var str_length` `=` `FNameEntryHeader >>` `6``;``var wide` `=` `FNameEntryHeader &` `1``;``console.log(str_length)``if` `(str_length >` `0` `&& str_length <` `250``) {` `var` `str` `=` `str_addr.readUtf8String(str_length);``console.log(``str``)``}` `}` |
|-|-|

在登陆界面获取看看world的类名
 ![image](https://bbs.kanxue.com/upload/attach/202410/980456_REHS3DAYY7K48RY.webp) ![image](https://bbs.kanxue.com/upload/attach/202410/980456_CAUP95Y9AWCMMZ6.webp) ![image](https://bbs.kanxue.com/upload/attach/202410/980456_VVZ28PZJZJ8HZ8Z.webp)
也是验证成功了。

# 0x3 小结

这次最开始还是花了点时间，看懂了之后就感觉这个方法还挺简单的，也算是见识了一种修改GName的方式。

---

# 回复

## 回复 by KXXTEST (#2)

*2024-10-10 14:31*

mark![image](https://bbs.kanxue.com/view/img/face/71.gif)

## 回复 by AunCss (#3)

*2024-10-10 15:42*

瓦的手游？大佬用什么在内存下断点的，怎么调用栈能这么深

## 回复 by 墨穹呢 (#4)

*2024-10-10 15:58*

感谢分享

## 回复 by gannicusliu (#5)

*2025-5-23 17:38*

不明觉厉
