---
title: '[原创]记一次修复IDA 9.0 android_server64的过程'
url: https://bbs.kanxue.com/thread-283135.htm
tid: 283135
author: Damn7Kx
date: '2024-08-28'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-07-31T14:21:09+08:00'
replies: 14
---

# hello

## 前言

使用IDA pro 9.0 android_server64调试程序会报错：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_HKJZUK25AZS3HQT.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_R7F5TWG8V4CQRCF.webp)

## 分析过程

### 字符串

IDA查找对应的字符串"internal error"
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_6HYDPNTCNNT2JW6.webp)
最终找到调用方法`interr`
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_VZ9C68MEYRMVFB3.webp)

### frida分析

启动android_server64和frida
上frida hook interr

| 1234567891011121314 | `function main() {` `var moduleName` `=` `"android_server64"``;``var functionName` `=` `"interr"``;` `Interceptor.attach(Module.findExportByName(moduleName, functionName), {``onEnter: function(args) {``console.log(``"Entering "` `+` `functionName);``showNativeStack(this.context)``},``onLeave: function(retval) {``console.log(``"Leaving "` `+` `functionName);``}``});``}` |
|-|-|

frida启动之后，打开ida去开启调试
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_MMA33UCQ8P6QDGX.webp)
输入手机IP和端口
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_RDX9WSYENDR2WUN.webp)
然后会看到程序直接退出了，观察frida打印
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_SW6A655UMC9RTU9.webp)
IDA跳转到`0x940d0`,确定当前位置就是判断的逻辑，准备nop掉
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_MBCKZQUFXS553H6.webp)

### 修复android_server64

IDA获取该地址的bytes字节，拿到 [ARM COVER](https://armconverter.com)去辅助还原
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_79A9CCHD9M94QZ2.webp)
修改前

| 1 | `1F` `01` `00` `71` `AD` `00` `00` `54` `E0` `03` `13` `AA F3` `7B` `41` `A9` |
|-|-|

修改后

| 1 | `1F` `20` `03` `D5 AD` `00` `00` `54` `E0` `03` `13` `AA F3` `7B` `41` `A9` |
|-|-|

然后保存文件，重新push到手机，随便找个APK验证下。发现可以正常读取进程了。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_P263Q78DBBMF645.webp)
漫长等待之后，也进入了debug界面，module选择想调试的so
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_X4TBD7CWZ8DADQU.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202408/869843_GSP3SDV3SYPDQMB.webp)
至此结束。上传一份修复好的

上传的附件：
- android_server64-fix

（1.24MB，181次下载）

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-8-28 17:41*

请问，ida9.0相对旧版本有哪些提升呢

## 回复 by Damn7Kx (#3)

*2024-8-28 17:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  请问，ida9.0相对旧版本有哪些提升呢
>
>

[官方有写](https://web.archive.org/web/20240808080936/https://out5.hex-rays.com/beta90_6ba923/)

## 回复 by bluegatar (#4)

*2024-8-29 11:33*

很好的分析，就是不知道为啥官方有这个报错

## 回复 by huangjw (#5)

*2024-8-29 16:12*

这个是mac版的吗， 还是通用

## 回复 by Damn7Kx (#6)

*2024-8-29 18:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  huangjw](https://bbs.kanxue.com/user-323039.htm)
>
>  这个是mac版的吗，&nbsp;还是通用
>
>

我这个ida是mac的，不知道winodws的有没有这问题

## 回复 by 小七烤地瓜 (#7)

*2024-8-29 19:54*

ida  mac版本 哪搞的  求一份

## 回复 by Damn7Kx (#8)

*2024-8-30 17:00*

>
> [小七烤地瓜](https://bbs.kanxue.com/user-632038.htm)
>
>  ida mac版本 哪搞的 求一份
>
>

之前不是泄漏了吗，一搜就能搜到

## 回复 by 你瞒我瞒 (#9)

*2024-9-5 09:24*

同样的遇到这个问题，大佬解决了真的太牛了。晚点试试。这个修复的arm版本还是Intel版本的呢？

## 回复 by Damn7Kx (#10)

*2024-9-5 18:03*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  同样的遇到这个问题，大佬解决了真的太牛了。晚点试试。这个修复的arm版本还是Intel版本的呢？
>
>

ida是arm的

## 回复 by tubecityman (#11)

*2024-9-6 13:06*

32位的没问题是吗

## 回复 by 养只猫不好么 (#12)

*2024-9-6 14:01*

感谢分享

## 回复 by ytmrgw (#13)

*2024-11-8 20:27*

有这个IDA的下载地址

## 回复 by yulou1024 (#14)

*2024-12-6 13:03*

我是windows 用了这个android_server64-fix  好像还是获取不到进程

## 回复 by 王麻子本人 (#15)

*2024-12-23 14:11*

你手机是什么型号的啊 ，我win电脑的ida嘎嘎好用 ，换到mac 调试要不设备附加上就卡死，要不恢复运行就发信号
