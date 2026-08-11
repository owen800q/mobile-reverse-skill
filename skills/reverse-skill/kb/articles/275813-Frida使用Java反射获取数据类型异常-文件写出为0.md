---
title: '[求助]Frida使用Java反射获取数据类型异常，文件写出为0'
url: https://bbs.kanxue.com/thread-275813.htm
tid: 275813
author: 冷冻猫咪
date: '2023-01-14'
tags: [Android安全, 求助, 基础理论, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-08-11T08:49:23+00:00'
replies: 18
---

通过Java反射获取的数据类型异常，无法被识别为数组length获取不了长度，[0]取不了元素。

调用Java类Arry.get可以取出数组长度跟元素，但是写出的文件大小为0，

如果通过Java.use获取到类去调用Java方法，可以正常写出文件大小length取长度[0]取元素都可以使用。

var method = dex.getClass().getDeclaredMethod("getBytes", null);

method.setAccessible(true);

var dexBytes =method.invoke(dex, []);

var path = mFile.$new("/sdcard/gg.dex");

var rand = RandomAccessFile.$new(path, "rw");

var mBytes=Java.use("[B");

rand.write(Java.cast(dexBtes,mBytes));

rand.close();

dexBytes无法用js函数取长度，类型强转也无效。

所有代码已经上传附件，欢迎测试！把xp模块转换成js代码，

不想用Java.use方式获取函数跟变量.

因为不止这一个模块转换成脚本还有java数据类型问题，

有能写出文件的麻烦说下怎么处理谢谢！

上传的附件：
- hook.js

（4.24kb，7次下载）

---

# 回复

## 回复 by 冷冻猫咪 (#2)

*2023-1-14 19:33*

尴尬浏览两百多次没一个说话的！

## 回复 by userapp (#3)

*2023-1-14 20:44*

java.lang.reflect.Array.getLength

## 回复 by 冷冻猫咪 (#4)

*2023-1-14 20:53*

哎呀！之前搜索Api没看到这个。。。大意了！！！

## 回复 by 靴子 (#5)

*2023-1-15 00:25*

安装Frida-server到目标设备上
在开发机上使用frida-ps -U查找要Hook的进程
使用frida -U <pid> -l script.js attach连接到目标进程
在脚本中使用Interceptor.attach()来挂载Hook函数
使用Interceptor.replace()来替换目标函数

## 回复 by 不吃早饭 (#6)

*2023-1-15 02:00*

Application.attach通常会被内联，不进行处理的话会导致hook无效

## 回复 by 你瞒我瞒 (#7)

*2023-1-16 09:33*

因为文字都懂，就是不知道在描述什么

## 回复 by 冷冻猫咪 (#8)

*2023-1-16 11:45*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  因为文字都懂，就是不知道在描述什么

无法获取java反射返回的数组长度跟元素

## 回复 by 冷冻猫咪 (#9)

*2023-1-16 14:37*

![image](https://bbs.kanxue.com/upload/attach/202301/915097_JA4JKPEDTYNXPDV.jpg)上面是txt输出的文本，下面是代码写出byte[]为空。![image](https://bbs.kanxue.com/upload/attach/202301/915097_67MW4MT4EEAKSZ5.jpg)

## 回复 by seeeseee (#10)

*2023-1-16 14:45*

这路径不存在吧... /sdcardHook

## 回复 by 冷冻猫咪 (#11)

*2023-1-16 15:24*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  这路径不存在吧... /sdcardHook
>
>

路径是截图的时候删代码误删了/

## 回复 by 冷冻猫咪 (#12)

*2023-1-16 15:26*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  这路径不存在吧... /sdcardHook
>
>

写出的dex为0字节![image](https://bbs.kanxue.com/upload/attach/202301/915097_MSSNVJ24NQNREZ4.jpg)

## 回复 by seeeseee (#13)

*2023-1-16 16:41*

因为你的arr是空的，你需要给定一个有长度的数组，比如这样

Java.array('byte', new Uint8Array(1024));

## 回复 by 冷冻猫咪 (#14)

*2023-1-16 17:31*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  因为你的arr是空的，你需要给定一个有长度的数组，比如这样
>
> Java.array('byte', new Uint8Array(1024));
>
>

for是后来加的把java反射取出来的byte数组存到js数组里，因为js里取不了java反射取的数组长度跟元素。

## 回复 by 冷冻猫咪 (#15)

*2023-1-16 17:38*

>
> [seeeseee](https://bbs.kanxue.com/user-941366.htm)
>
>  因为你的arr是空的，你需要给定一个有长度的数组，比如这样
>
> Java.array('byte', new Uint8Array(1024));
>
>

测试了下加new Uint8Array(1024)创建数组，代码异常不执行app崩溃

## 回复 by userapp (#16)

*2023-1-17 10:39*

把dexBytes直接给rand.write

## 回复 by 冷冻猫咪 (#17)

*2023-1-17 11:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  userapp](https://bbs.kanxue.com/user-752991.htm)
>
>  把dexBytes直接给rand.write
>
>

一样写出0，for转换byte数组是后面写的转换类型。

## 回复 by userapp (#18)

*2023-1-18 16:25*

>
> [冷冻猫咪](https://bbs.kanxue.com/user-915097.htm)
>
>  一样写出0，for转换byte数组是后面写的转换类型。
>
>

既然在for中能遍历到值，试试用rand.write(arr[n])

## 回复 by 冷冻猫咪 (#19)

*2023-1-18 17:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  userapp](https://bbs.kanxue.com/user-752991.htm)
>
>  既然在for中能遍历到值，试试用rand.write(arr[n])
>
>

写出不了，arr也不能用js里的length取长度奇怪。用java反射类可以取出来。
