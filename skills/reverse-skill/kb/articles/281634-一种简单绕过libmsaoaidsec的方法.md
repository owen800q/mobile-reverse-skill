---
title: '[原创]一种简单绕过libmsaoaidsec的方法'
url: https://bbs.kanxue.com/thread-281634.htm
tid: 281634
author: lanoche
date: '2024-05-07'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-11T08:45:30+00:00'
replies: 12
---

不知从什么时候开始，携带libmsaoaidsec的应用越来越多，关键这东西还不让用frida。

给出一个简单绕过的方法

| 123456789101112131415 | `function hook_dlopen(soName` `=` `'') {``Interceptor.attach(Module.findExportByName(null,` `"android_dlopen_ext"``), {``onEnter: function (args) {``var pathptr` `=` `args[``0``];``if` `(pathptr !``=``=` `undefined && pathptr !``=` `null) {``var path` `=` `ptr(pathptr).readCString();``if``(path.indexOf(``'libmsaoaidsec.so'``) >``=` `0``){``ptr(pathptr).writeUtf8String("");``}``console.log(``'path: '``,path)``}``}``});``}``hook_dlopen()` |
|-|-|

---

# 回复

## 回复 by LLeaves (#2)

*2024-5-7 19:06*

好简单粗暴

## 回复 by Imxz (#3)

*2024-5-8 16:50*

亲测无用

## 回复 by lanoche (#4)

*2024-5-9 08:40*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>
>  亲测无用
>
>

只测试了自己使用的几个应用，不保证通用。并且反frida的地方很多....

## 回复 by xixiha5230 (#5)

*2024-5-13 14:42*

有用![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 拾海 (#6)

*2024-5-21 09:55*

高端的食材往往只需要最朴素的烹饪方式![image](https://bbs.kanxue.com/view/img/face/23.gif)

## 回复 by mb_ocjajutu (#7)

*2024-5-29 02:39*

牛逼老哥

## 回复 by Yangser (#8)

*2024-6-10 19:22*

这是啥原理啊

## 回复 by mb_sjxphvyl (#9)

*2024-6-13 06:11*

强![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 陈可牛 (#10)

*2024-6-13 10:42*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  这是啥原理啊
>
>

你把so删除效果一样的，这个是一个著名的某id用bangbang保护之后的sdk依赖库。

## 回复 by 陈可牛 (#11)

*2024-6-13 10:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  你把so删除效果一样的，这个是一个著名的某id用bangbang保护之后的sdk依赖库。
>
>

删除之后某id就为空了

## 回复 by Yangser (#12)

*2024-6-13 21:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  删除之后某id就为空了
>
>

吆西，谢谢佬

## 回复 by 吴俊 (#13)

*2024-7-18 14:52*

律师函警告
