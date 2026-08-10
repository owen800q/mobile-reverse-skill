---
title: '[原创]关于NativeDetector中的检测到Umount'
url: https://bbs.kanxue.com/thread-286664.htm
tid: 286664
author: 无味
date: '2025-04-28'
tags: [Android安全, 原创, 漏洞相关, 其他, 工具脚本]
crawled_at: '2026-08-10T03:07:39+00:00'
replies: 18
---

## 检测

`Native Detector`中能检测到:'/debug_rakdisk/.magisk/modules/xx/riru/lib64'
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_44PZJG2AG8A5B8P.webp)

## 猜测

还是直接上ce搜索:
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_2Y465VU8DCWA5FV.webp)
对一下区块, 最可疑的就是`[anon:stack_and_tls:main]`

| 1234567891011121314151617 | `redmi:/` `# cat /proc/1097/maps \| grep 7a077``7a076a0000-7a07768000 r--p 00000000 00:00 0                              [anon:linker_alloc]``7a07768000-7a07788000 r--s 00000000 00:11 13760` `/dev/__properties__/u``:object_r:vndk_prop:s0``7a07788000-7a0778b000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_small_objects]``7a0778b000-7a0778d000 r--p 00041000 07:78 53` `/apex/com``.android.art``/javalib/arm64/boot-core-icu4j``.art``7a0778d000-7a07791000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_small_objects]``7a07791000-7a07792000 r--p 0001d000 07:78 56` `/apex/com``.android.art``/javalib/arm64/boot-core-libart``.art``7a07792000-7a07794000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_small_objects]``7a07794000-7a07795000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_lob]``7a07795000-7a0779a000 rw-p 00000000 00:00 0                              [anon:System property context nodes]``7a0779a000-7a0779b000 ---p 00000000 00:00 0` `7a0779b000-7a0779f000 rw-p 00000000 00:00 0                              [anon:stack_and_tls:main]``7a0779f000-7a077a0000 ---p 00000000 00:00 0` `7a077a0000-7a077a4000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_small_objects]``7a077a4000-7a077a5000 rw-p 00000000 00:00 0                              [anon:ReadFileToBuffer]``7a077a5000-7a077ab000 rw-p 00000000 00:00 0                              [anon:bionic_alloc_small_objects]``7a077ab000-7a0780f000 r--p 00000000 00:00 0                              [anon:linker_alloc]` |
|-|-|

找到内存区块后, 难道是通过哪个指针泄露的?
随便改点字符就没有了, 再下面随便复制一下是相同的字符串, 又能搜索到了, 证明只是通过`[anon:stack_and_tls:main]`的字符串`/debug_ramdisk/.magisk/`搜索

 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_US7P9UAMYD9EQW6.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_D59MWPX673DSXZU.webp)

## 探索

>
> 这个指针是从哪来的呢?
>
>
>

| 12345678910111213141516 | `if` `(android_prop::GetApiLevel() >= __ANDROID_API_O__) {``auto` `*dir = dirname(path);``auto` `*ns = &__loader_android_create_namespace == nullptr ? nullptr :``__loader_android_create_namespace(path, dir, nullptr,``2``/*ANDROID_NAMESPACE_TYPE_SHARED*/``,``nullptr, nullptr,``reinterpret_cast``<``void` `*>(&DlopenExt));``if` `(ns) {``info.flags = ANDROID_DLEXT_USE_NAMESPACE;``info.library_namespace = ns;` `LOGD(``"open %s with namespace %p, dir: %p"``, path, ns, dir);``}` `else` `{``LOGD(``"cannot create namespace for %s"``, path);``}``}` |
|-|-|

就是`android`的`DlopenExt`方法里的, 当要`__loader_android_create_namespace`时会有一个`dirname`查询目录.

## 结论

可以在每次`open`之后直接清除这个字符串

| 12 | `// 直接清除``memset``(dir, 0,` `strlen``(dir));` |
|-|-|

也可以随便改一下关键字, 或者自己也搜索内存改下算了.

---

# 回复

## 回复 by hacker521 (#2)

*2025-4-28 22:52*

能否分析下 检测到风险应用：他这个包名检测现在是怎么检测的呢？为什么 隐藏应用列表隐藏仍然无效？

## 回复 by 无味 (#3)

*2025-4-28 22:59*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  能否分析下 检测到风险应用：他这个包名检测现在是怎么检测的呢？为什么&nbsp;隐藏应用列表隐藏仍然无效？
>
>

包名检测无意义，开源的直接改名，不开源的在android进程中hook packageManager

## 回复 by hacker521 (#4)

*2025-4-28 23:02*

就是单纯想了解下这个检测包名的原理~ 很好奇 如果不改包名 单纯的 隐藏应用列表怎么才能隐藏？

## 回复 by 无味 (#5)

*2025-4-28 23:07*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  就是单纯想了解下这个检测包名的原理~ 很好奇 如果不改包名 单纯的 隐藏应用列表怎么才能隐藏？
>
>

android应用是通过Binder（aidl）向android（system_server）进程获取包名的，直接在内存中操作应该是没有办法的。

## 回复 by hacker521 (#6)

*2025-4-28 23:13*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  android应用是通过Binder（aidl）向android（system_server）进程获取包名的，直接在内存中操作应该是没有办法的。
>
>

我怎么感觉这个是通过命令 检测data目录下包名是否存在是返回文件不存在还是permission denied？

## 回复 by 无味 (#7)

*2025-4-29 00:04*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  我怎么感觉这个是通过命令 检测data目录下包名是否存在是返回文件不存在还是permission denied？
>
>

/data/data并不能判断，/data/app无法判断

## 回复 by 你瞒我瞒 (#8)

*2025-4-29 09:33*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  我怎么感觉这个是通过命令 检测data目录下包名是否存在是返回文件不存在还是permission denied？
>
>

以前可以隐藏，自己看了一些帖子，有人在隐藏应用列表中打开数据隔离可以

## 回复 by 无味 (#9)

*2025-4-29 09:56*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  以前可以隐藏，自己看了一些帖子，有人在隐藏应用列表中打开数据隔离可以
>
>

和安卓版本有很大关系, 再者包名的风险等级也算最低, 所以我认为检测包名无意义

## 回复 by huangjw (#10)

*2025-4-29 10:20*

可以的

## 回复 by 你瞒我瞒 (#11)

*2025-4-29 14:15*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>
>
>
>
>
>
>  你瞒我瞒
>
>
>
>  以前可以隐藏，自己看了一些帖子，有人在隐藏应用列表中打开数据隔离可以
>
>  和安卓版本有很大关系, 再者包名的风险等级也算最 ...
>
>

现在有部分软件已经把mt列为风险app，检查针对用户安装了什么app，然后认为用户有可疑，这个还是有在商业app上面这么搞。存在这么搞肯定有对抗的需求了。![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by hacker521 (#12)

*2025-4-29 16:31*

![image](https://bbs.kanxue.com/upload/attach/202504/983172_GGG44Z926YPZFG3.webp)![image](https://bbs.kanxue.com/upload/attach/202504/983172_W8Y4JBVK398UJUJ.webp)

它怎么检测的？

## 回复 by 无味 (#13)

*2025-4-29 19:45*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  它怎么检测的？
>
>

检测确实很厉害, 我对包名隐藏了解不多, 无能为力了![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by hacker521 (#14)

*2025-4-29 21:18*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  检测确实很厉害, 我对包名隐藏了解不多, 无能为力了[em_055]
>
>

你分析下 他so层的逻辑呀~

## 回复 by 无味 (#15)

*2025-4-29 22:55*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  你分析下 他so层的逻辑呀~
>
>

Ruru也能检测出来： https://github.com/byxiaorun/Ruru/tree/master/library/src/main/java/icu/nullptr/applistdetector

## 回复 by hacker521 (#16)

*2025-4-30 10:12*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  Ruru也能检测出来： https://github.com/byxiaorun/Ruru/tree/master/library/src/main/java/icu/nullptr/applistd ...
>
>

Ruru没法检测隐藏应用列表 开启隐藏以后得，但是NativeDetector 会，你看我截图，懂？

## 回复 by 无味 (#17)

*2025-4-30 10:40*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  Ruru没法检测隐藏应用列表 开启隐藏以后得，但是NativeDetector 会，你看我截图，懂？
>
>

你自己研究研究吧, 我对隐藏应用没兴趣

## 回复 by mb_dovsgrdo (#18)

*2026-2-13 22:07*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  Ruru没法检测隐藏应用列表 开启隐藏以后得，但是NativeDetector 会，你看我截图，懂？
>
>

就是属性检测????，没你想象的那么高级

## 回复 by hacker521 (#19)

*2026-2-13 23:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_dovsgrdo](https://bbs.kanxue.com/user-1034435.htm)
>
>  就是属性检测????，没你想象的那么高级
>
>

最新版的HMA已经可以隐藏了
