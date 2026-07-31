---
title: '[原创] Bypass 某 x 书 frida 检测'
url: https://bbs.kanxue.com/thread-282628.htm
tid: 282628
author: 行简
date: '2024-07-25'
tags: [Android安全, 原创, 基础理论, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:22:37+08:00'
replies: 8
---

## 0x01、环境

app 版本：8.46.0 酷安下载
设备：Pixel 2XL Android 8.1
hook：frida 12.8.0、frida-tools 5.3.0

## 0x02、Bypass_frida

hook libc.so 模块中 strstr 与 strcmp，一把绕过。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152 | `function Bypass_frida() {``var pt_strstr` `=` `Module.findExportByName(``"libc.so"``,` `'strstr'``);``Interceptor.attach(pt_strstr, {``onEnter: function (args) {``var args1` `=` `args[``0``].readCString();``var args2` `=` `args[``1``].readCString();``if` `(``args2.indexOf(``"gum-js-loop"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"pool-frida"``) !``=``=` `-``1``\|\|``args2.indexOf(``"linjector"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"REJECT"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"frida"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"gmain"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"gdbus"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"tmp"``) !``=``=` `-``1``) {``console.log(``"strstr-->"``, args1, args2);``this.hook_str` `=` `true;``}``}, onLeave: function (retval) {``if` `(this.hook_str) {``retval.replace(``0``);``}``}``});` `var pt_strcmp` `=` `Module.findExportByName(``"libc.so"``,` `'strcmp'``);``Interceptor.attach(pt_strcmp, {``onEnter: function (args) {``var args1` `=` `args[``0``].readCString();``var args2` `=` `args[``1``].readCString();``if` `(``args2.indexOf(``"gum-js-loop"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"pool-frida"``) !``=``=` `-``1``\|\|``args2.indexOf(``"linjector"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"REJECT"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"frida"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"gmain"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"gdbus"``) !``=``=` `-``1` `\|\|``args2.indexOf(``"tmp"``) !``=``=` `-``1``) {``console.log(``"strcmp-->"``, args1, args2);``this.hook_cmp` `=` `true;``}``}, onLeave: function (retval) {``if` `(this.hook_cmp) {``retval.replace(``0``);``}``}``})``}``Bypass_frida();` |
|-|-|

## 0x03、效果

 ![图片描述](https://bbs.kanxue.com/upload/attach/202407/945390_UPGWQUE44PESS9A.webp)

---

# 回复

## 回复 by 你瞒我瞒 (#2)

*2024-7-26 09:36*

x是什么，小白猜不到。

## 回复 by 行简 (#3)

*2024-7-26 10:03*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  x是什么，小白猜不到。
>
>

是 x 啊![image](https://bbs.kanxue.com/view/img/face/76.gif)

## 回复 by hacker521 (#4)

*2024-7-28 00:16*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  x是什么，小白猜不到。
>
>

小红薯

## 回复 by 你瞒我瞒 (#5)

*2024-7-29 09:38*

>
> [行简](https://bbs.kanxue.com/user-945390.htm)
>
>  是 x 啊[em_76]
>
>

之前的蓝尿?

## 回复 by mb_rugymctl (#6)

*2024-7-29 19:20*

大佬，能帮忙app去壳吗？https://f.ws28.cn/f/epnkmz8iilm

## 回复 by 行简 (#7)

*2024-7-30 10:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rugymctl](https://bbs.kanxue.com/user-1002747.htm)
>
>  大佬，能帮忙app去壳吗？https://f.ws28.cn/f/epnkmz8iilm
>
>

可 私我

## 回复 by mb_rugymctl (#8)

*2024-7-30 17:37*

>
> [行简](https://bbs.kanxue.com/user-945390.htm)
>
>  可 私我
>
>

呃。。。账号没权限私信![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by mb_jeslfge (#9)

*2024-11-9 10:58*

看样子像脸书
