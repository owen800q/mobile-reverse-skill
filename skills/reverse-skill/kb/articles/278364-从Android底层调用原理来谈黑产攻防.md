---
title: '[原创]从Android底层调用原理来谈黑产攻防'
url: https://bbs.kanxue.com/thread-278364.htm
tid: 278364
author: 恋空
date: '2023-08-10'
tags: [Android安全, 原创, 基础理论, 逆向分析, 混淆加固, 程序开发, 系统相关]
crawled_at: '2026-07-31T14:39:25+08:00'
replies: 19
---

最近忙于公司事务，今天刚好抽出时间对最近的研究成果来说道说道，受到珍惜Any大神的文章启发，特地研究了一下Binder驱动的原理，分享出来给大家。
参考：
<https://bbs.kanxue.com/thread-277637.htm>
<http://aospxref.com/android-13.0.0_r3/>
<https://github.com/torvalds/linux/blob/master/drivers/android/binder.c#L5610>

#### 1.序言

众所周知，安卓AOSP是开放源代码，那么能否从安卓系统源代码中获得在黑产攻防中的优势呢？

#### 2.一切的根源 -- Binder

 ![Linux Binder驱动](https://bbs.kanxue.com/upload/attach/202308/862224_FZE9FYXDF477WYY.png)
梦开始的地方，Google为Linux写的Binder驱动

##### 那么Binder的工作原理是什么呢？

>
> 在安卓中涉及很多功能的调用，而像socket pipe这样的通道虽然方便用于传递数据，但是不方便用于应用级之间的调用，因为Android中system_server也是运行在用户级的（而非内核级）。如果使用socket、pipe的话，则无法通过内核的特权级接口获取到调用者的身份。
>
>
>

##### Binder调用为什么就安全呢？

| 1 | `调用者` `-``-``-``> 接受者信息``+``数据` `-``-``-``> Linux Binder驱动` `-``-``-``> 发送者信息``+``数据` `-``-``-``>  被调用者` |
|-|-|

所以，被调用者能相对安全的获取到调用者的身份（Java层的Binder.getCallingUid()和Binder.getCallingPid()），然后被调用者就可以通过Binder驱动返回的可信信息里的uid知道是哪个App在进行调用。

##### Android Framework是怎么完成接口调用的？

| 1 | `Framework` `-``-``-``> AIDL` `-``-``-``> Binder` `-``-``-``> SystemServer` |
|-|-|

假如你调用的是WifiManager.getWifiInfo()，那么路径如下：

| 1 | `WifiManager.java` `-``-``-``> IWifiManager.aidl` `-``-``-``> Binder.translate` `-``-``-``> Binder驱动` |
|-|-|

然后来到SystemServer这边：

| 1 | `Binder驱动` `-``-``-``>  Binder.execTranslate` `-``-``-``>  IWifiManager.onTranslate` `-``-``-``> WifiManagerService.getWifiInfo()` |
|-|-|

##### 3.接口调用的最后一道门Binder.java和BinderProxy.java

BinderProxy.java
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/862224_N37HWS6R4BQB5QY.png)

>
> 所有AIDL的调用最后都会经过到这里来，然后转发到C++的Binder接口，发送给Linux内核里的Binder驱动
>
>
>

Binder.java
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/862224_P47HGMWWCG35YND.png)

>
> 所有通过AIDL对SystemServer或者其他服务进行的调用，都会被另一端的C++ Binder接口转发到Binder.execTranslate方法，然后分发到相应的服务去
>
>
>

#### 4.怎么攻？怎么防？

###### ========= 攻 ===========

有很多办法。
例如，直接Hook BinderProxy.translate，亦或者更底层的方法，直接在SystemServer拦截execTranslate方法
.

###### ======== 防 ========

1.对部分重要的方法采用Binder.translate的直接调用，绕过对framework的调用，防止定制ROM对framework修改的攻击

**难点：兼容性不太好，需要花大量时间去兼容**
.
2.基于第一点，采取更底层的方法使用C++层的接口直接和Binder驱动通信
**难点：兼容性更不友好，Binder驱动更新频繁，而且每个版本的数据格式也在变化。**

---

# 回复

## 回复 by 秋狝 (#2)

*2023-8-11 09:37*

mark

## 回复 by Amun (#3)

*2023-8-11 14:24*

只需要适配4个版本的 binder 就行，也还好

## 回复 by 恋空 (#4)

*2023-8-11 16:15*

>
> [Amun](https://bbs.kanxue.com/user-850401.htm)
>
>  只需要适配4个版本的 binder 就行，也还好
>
>

假如黑产在SystemServer那端拦截修改数据，就好像无解了。暂时没想出什么解决办法，有的话请赐教。

## 回复 by 珍惜Any (#5)

*2023-8-12 22:56*

我不叫Andy ，可以叫我珍惜Any 哈哈哈哈~

## 回复 by SomeMx (#6)

*2023-8-12 23:07*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我不叫Andy ，可以叫我珍惜Any 哈哈哈哈~

新版本的Hunter强度确实不错

## 回复 by 秋狝 (#7)

*2023-8-12 23:12*

感谢分享

## 回复 by 珍惜Any (#8)

*2023-8-13 11:46*

>
> [SomeMx](https://bbs.kanxue.com/user-926256.htm)
>
>
>
>
>
>
>
>  珍惜Any
>
>  我不叫Andy ，可以叫我珍惜Any 哈哈哈哈~ 新版本的Hunter强度确实不错
>
>

感谢认可

## 回复 by 恋空 (#9)

*2023-8-14 17:59*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我不叫Andy ，可以叫我珍惜Any 哈哈哈哈~
>
>

我的锅，我把你的和那个Andy大佬看错成同一个人了![image](https://bbs.kanxue.com/view/img/face/2.gif)

## 回复 by 珍惜Any (#10)

*2023-8-15 19:11*

>
> [恋空](https://bbs.kanxue.com/user-862224.htm)
>
>  我的锅，我把你的和那个Andy大佬看错成同一个人了[em_2]
>
>

binder本质上还是一个驱动，我见过某个apk 直接实现binder，反正binder驱动是开源的。然后往服务端去发送，就连Binder.translate，都不会走，直接走自己的binder，非常恶心 ，但是这种需要对不同apk版本适配，也麻烦的很 。

## 回复 by 恋空 (#11)

*2023-8-15 20:53*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  binder本质上还是一个驱动，我见过某个apk 直接实现binder，反正binder驱动是开源的。然后往服务端去发送，就连Binder.translate，都不会走，直接走自己的binder，非常 ...
>
>

黑产：我在System Server端拦截所有请求
大厂卒。

## 回复 by 珍惜Any (#12)

*2023-8-16 09:56*

>
> [恋空](https://bbs.kanxue.com/user-862224.htm)
>
>  黑产：我在System Server端拦截所有请求
> 大厂卒。
>
>

一般黑产都是二次打包，很难做到服务端拦截。

## 回复 by Himeko (#13)

*2023-11-14 16:01*

看到binder, 想起来跟lsp代码的痛苦时刻

## 回复 by 万里星河 (#14)

*2023-11-17 16:43*

| 12 | `有很多办法。``例如，直接Hook BinderProxy.translate` |
|-|-|

对于这个 我有个不成熟的疑问 如果直接拦截translate的话 那么要如何确定code和远端哪个服务的哪个函数相对应呢？

## 回复 by 恋空 (#15)

*2023-11-20 15:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  有很多办法。
> 例如，直接Hook&nbsp;BinderProxy.translate对于这个 我有个不成熟的疑问 如果直接拦截translate的话 那么要如何确定code和远端哪个服务的 ...
>
>

几个经验总结：
translate方法的第一个参数是int code，这个代表了来源的函数
第二个参数Parcel data，反射Parcel里面有一个变量String mInterfaceName这个是标注来自的接口aidl类
实在不行，可以通过hread.currentThread().getStackTrace()获取本地函数的调用来源

## 回复 by wx_围城 (#16)

*2023-11-21 09:47*

mark

## 回复 by breakM (#17)

*2025-5-15 00:18*

mark

## 回复 by zxqi (#18)

*2025-5-19 17:08*

111111111

## 回复 by x_leevin (#19)

*2025-6-24 16:20*

这里的拦截是可以拦截到其他应用对系统服务的调用么？

## 回复 by wx_白鸟之诗 (#20)

*2025-7-30 19:46*

mark
