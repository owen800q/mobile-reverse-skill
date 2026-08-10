---
title: '[原创] 关于牛头人(nativeTest)的Found Injection(4)的检测'
url: https://bbs.kanxue.com/thread-286580.htm
tid: 286580
author: 无味
date: '2025-04-23'
tags: [Android安全, 原创, 逆向分析, 其他]
crawled_at: '2026-08-10T03:07:47+00:00'
replies: 14
---

## 原由

上一篇 [关于NativeBridge注入的检测和隐藏](https://bbs.kanxue.com/thread-286536.htm) NativeBridge注入后， 牛头人还是会显示"**Found Injection(4)**"
这不得行， 先测试：

1. 禁用`riru`和`LSPosed`, 正常
2. 随意`resetprop ro.dalvik.vm.native.bridge xx`后am restart, `Found Injection(4)`
3. `resetprop`为0后 正常
得出，检测逻辑应该和上一篇文章一样，只是内存中还有一个特征驻留了。

## 解决

从头阅读源码，果然找到一个点。[AndroidRuntime::addOption](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/base/core/jni/AndroidRuntime.cpp;drc=82ada6503a81af7eeed2924a2d2d942375f6c8c2;l=501?hl=zh-cn)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_7JNCC3BEJVDYRHH.webp)
[Vector<JavaVMOption> mOptions;](https://cs.android.com/android/platform/superproject/main/+/main:frameworks/base/core/jni/include/android_runtime/AndroidRuntime.h;drc=cda041235680be1f09e13570b928d6c552af240d;l=134?hl=zh-cn)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_EUE9PY2EKZB9N4P.webp)
看一下属性的内存位置：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_JHUYB2WTJS2VK5V.webp)
在AndroidRumtime的指针+8(point length)的位置
AndroidRuntime的指针可以通过`AndroidRuntime::getRuntime`获取
写个小`jni`测试一下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_MV9HB9TBP8FYWCW.webp)
logcat
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_TDUEYASHV5GAH8J.webp)
可以看出， `Vecrot`的结构还在，但值的指针大部分都是野指针，牛头人应该是通过`size`判断，因为如果加了`NativeBridge`后会多一个参数。
指针知道了，那这次直接上CE， 上传好·ceserver·后， 执行`su -c ceserver_arm64`, 电脑连接上
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_UKGC24UF7ABKDU9.webp)
不管了，清零：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_8489JSXUDKVZSS9.webp)
启动后奔溃，应该是`mOptions->array()`不能为nullprt, 指向一个空白区域，正好下面有一块：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_XCKVBYBE5ZQQHB9.webp)
再次测试
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_G9CFSQECAJVY8K4.webp)
难道不是？？
其实不然，牛头人应该是同时检测了`webview_zygote`
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_KFWPH9EFQ3Y7YEX.webp)
用同样方式改一下：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202504/98159_HDE7BGD46CAM3P5.webp)
好了再改一上篇说的`NativeBridgeError`， `found Injection(4)`没了

### 结语

牛头人不愧是native的测试，都是内存检测, `Futile Hide(8)`是我用的一个调试模块导致，正式应该环境不会出现， 但`Abnomal Environment`应该解决一下，而且安装`LSPlosed`还是会出现`Found Inject`，等有空搞。睡......

---

# 回复

## 回复 by 无味 (#2)

*2025-4-23 01:32*

我与牛头人不共戴天![image](https://bbs.kanxue.com/view/img/face/065.gif)， 点赞评论多的话， 我一个一个解决它(![image](https://bbs.kanxue.com/view/img/face/065.gif)当然是解决我能解决的![image](https://bbs.kanxue.com/view/img/face/065.gif))，并写出过过程。

## 回复 by 珍惜Any (#3)

*2025-4-23 10:28*

hunter 615版本可以看看

## 回复 by 无味 (#4)

*2025-4-23 11:24*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  hunter&nbsp;615版本可以看看
>
>

![image](https://bbs.kanxue.com/upload/attach/202504/98159_YN2BKPBJWFJDUXM.webp)

6.1.5升级就闪退, 但6.1.1没问题, 只是bl锁我暂时没管, LSPosed注入了

## 回复 by 珍惜Any (#5)

*2025-4-23 16:07*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  6.1.5升级就闪退, 但6.1.1没问题, 只是bl锁我暂时没管, LSPosed注入了
>
>

github有下载地址。https://github.com/w296488320/HunterUpdate

## 回复 by 无味 (#6)

*2025-4-23 16:32*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  github有下载地址。https://github.com/w296488320/HunterUpdate
>
>

加了一个odex校验, 应该和`native detector`不一样的方式, 有空研究下![image](https://bbs.kanxue.com/view/img/face/001.gif)

![image](https://bbs.kanxue.com/upload/attach/202504/98159_R884SMM2N3U2JRF.webp)

## 回复 by 珍惜Any (#7)

*2025-4-23 16:36*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  加了一个odex校验, 应该和`native detector`不一样的方式, 有空研究下
>
>

这个是两个文件的inode不一样，跟奇怪 。如果没hook理论上不可能存在这个问题的。

## 回复 by 无味 (#8)

*2025-4-23 16:41*

hook了呀, lsposed直接注入了的, 不过我多打开几次又没了, 好奇怪.

## 回复 by mb_kgsesxqm (#9)

*2025-4-23 18:37*

>
> [无味](https://bbs.kanxue.com/user-98159.htm)
>
>  我与牛头人不共戴天[em_065]， 点赞评论多的话， 我一个一个解决它([em_065]当然是解决我能解决的[em_065])，并写出过过程。
>
>

小哥哥，看好你哦

## 回复 by 无味 (#10)

*2025-4-24 01:29*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  这个是两个文件的inode不一样，跟奇怪 。如果没hook理论上不可能存在这个问题的。
>
>

破案了，是我改odex引起的： https://bbs.kanxue.com/thread-286498.htm

## 回复 by 你瞒我瞒 (#11)

*2025-4-24 09:40*

Abnomal Environment这个是什么异常，好模糊

## 回复 by 无味 (#12)

*2025-4-24 10:32*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  Abnomal Environment这个是什么异常，好模糊
>
>

应该是和magisk(apatch/ksu之类的)有关, 刚刷上机就报.

## 回复 by lookaside (#13)

*2025-5-26 17:34*

牛头人怎么知道原始size的大小？

## 回复 by 程序猿007 (#14)

*2025-8-28 10:07*

我挺好奇，你是怎么定位到的？

## 回复 by 小七烤地瓜 (#15)

*2025-8-28 10:32*

.

![image](https://bbs.kanxue.com/upload/attach/202508/632038_TS7SXSU3YYBSBNQ.png)

上传的附件：
- QQ20250828-103127.png

（85.76kb，8次下载）
