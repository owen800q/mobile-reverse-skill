---
title: 绕过最新版bilibili app反frida机制
url: https://bbs.kanxue.com/thread-281584.htm
tid: 281584
author: 天水姜伯约
date: '2024-05-01'
tags: [Android安全, 逆向分析]
crawled_at: '2026-07-31T14:28:01+08:00'
replies: 29
---

>
> 安卓的最新版B站APP（7.76.0）有反FRIDA机制，本文介绍一下如何绕过它
>
>
>

## 问题说明

截止到2024年5月1日，B站最新版的安卓APP（7.76.0）有反Frida机制，不管是spawn还是attach，都无法注入frida，如下图所示。本文介绍一下如何绕过它

![image](https://bbs.kanxue.com/upload/attach/202405/783210_REY93YQ8TF8Y234.webp)

## 方法

### 定位检测点

检测Frida的机制一般在Native层实现，通常会创建几个线程轮询检测。首先要知道检测机制是由哪个so实现的，通过hook android_dlopen_ext函数，观察加载到哪个so的时候，触发反调试进程终止即可。Frida脚本代码与输出如下，最终可以定位到检测点在libmsaoaidsec.so中。

| 1234567891011 | `var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``console.log(``"[LOAD]"``, path)``}``},``}``)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202405/783210_WTUGR6U7UJRAPDU.webp)

### 绕过检测点

#### 对抗

使用IDA载入libmsaoaidsec.so，发现没有导入pthread_create符号

 ![image](https://bbs.kanxue.com/upload/attach/202405/783210_Q9B5UQVT7S5G6XX.webp)

使用Frida脚本尝试HOOK pthread_create 函数，也没有找到来自libmsaoaidsec.so的调用

| 12345678910111213 | `var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"pthread_create"``),``{``onEnter:` `function` `(args) {``var` `module = Process.findModuleByAddress(ptr(``this``.returnAddress))``if` `(module !=` `null``) {``console.log(``"[pthread_create] called from"``, module.name)``}``else` `{``console.log(``"[pthread_create] called from"``, ptr(``this``.returnAddress))``}``},``}``)` |
|-|-|

 ![image](https://bbs.kanxue.com/upload/attach/202405/783210_72Z8UZTE2PGXY6T.webp)

#### 分析

尽管表现有点奇怪，但它一定会调用pthread_create创建检测线程。所以尝试hook dlsym函数，在加载libmsaoaidsec.so之前挂钩dlsym函数，代码如下

| 12345678910111213141516171819202122232425262728293031323334353637 | `function` `hook_dlsym() {``var` `count = 0``console.log(``"=== HOOKING dlsym ==="``)``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"dlsym"``),``{``onEnter:` `function` `(args) {``const name = ptr(args[1]).readCString()``// const module = Process.findModuleByAddress(ptr(this.returnAddress))``console.log(``"[dlsym]"``, name)``if` `(name ==` `"pthread_create"``) {``count++``}``}``}``)``return` `Interceptor``}` `function` `hook_dlopen() {``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``console.log(``"[LOAD]"``, path)``if` `(path.indexOf(``"libmsaoaidsec.so"``) > -1) {``hook_dlsym()``}``}``},``}``)``return` `interceptor``}` `var` `dlopen_interceptor = hook_dlopen()` |
|-|-|

输出如下，在加载libmsaoaidsec.so后，调用了2次dlsym获取pthread_create函数，然后进程就终止了。证明它确实会调用pthread_create，只是调用方式不是直接调用，可能采取了一些对抗手段。

 ![image](https://bbs.kanxue.com/upload/attach/202405/783210_KS8SGSMC6C6A6U3.webp)

#### 绕过

它应该是使用了一些反hook的手段，没有必要和它正面对抗。简单描述一下我的绕过策略，创建一个fake_pthread_create函数，它只有一条ret汇编指令，然后hook来自libmsaoaidsec.so的前2次对dlsym的调用，返回fake_pthread_create函数的地址，这样就达成了欺骗它调用fake_pthread_create函数的目的。最终代码如下

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758 | `function` `create_fake_pthread_create() {``const fake_pthread_create = Memory.alloc(4096)``Memory.protect(fake_pthread_create, 4096,` `"rwx"``)``Memory.patchCode(fake_pthread_create, 4096, code => {``const cw =` `new` `Arm64Writer(code, { pc: ptr(fake_pthread_create) })``cw.putRet()``})``return` `fake_pthread_create``}` `function` `hook_dlsym() {``var` `count = 0``console.log(``"=== HOOKING dlsym ==="``)``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"dlsym"``),``{``onEnter:` `function` `(args) {``const name = ptr(args[1]).readCString()``console.log(``"[dlsym]"``, name)``if` `(name ==` `"pthread_create"``) {``count++``}``},``onLeave:` `function``(retval) {``if` `(count == 1) {``retval.replace(fake_pthread_create)``}``else` `if` `(count == 2) {``retval.replace(fake_pthread_create)``// 完成2次替换, 停止hook dlsym``interceptor.detach()``}``}``}``)``return` `Interceptor``}` `function` `hook_dlopen() {``var` `interceptor = Interceptor.attach(Module.findExportByName(``null``,` `"android_dlopen_ext"``),``{``onEnter:` `function` `(args) {``var` `pathptr = args[0];``if` `(pathptr !== undefined && pathptr !=` `null``) {``var` `path = ptr(pathptr).readCString();``console.log(``"[LOAD]"``, path)``if` `(path.indexOf(``"libmsaoaidsec.so"``) > -1) {``hook_dlsym()``}``}``}``}``)``return` `interceptor``}` `// 创建虚假pthread_create``var` `fake_pthread_create = create_fake_pthread_create()``var` `dlopen_interceptor = hook_dlopen()` |
|-|-|

执行`frida -U -f tv.danmaku.bili -l bypass.js`后即可绕过反frida机制，如下图所示

 ![image](https://bbs.kanxue.com/upload/attach/202405/783210_6Y4D53MN2WAU9U6.webp)

代码也可从github下载，见引用[1]。

## 引用

[1] <https://github.com/ddddhm1234/bypass_bilibili/>

---

# 回复

## 回复 by mudebug (#2)

*2024-5-1 21:31*

![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 秋狝 (#3)

*2024-5-1 22:08*

感谢分享

## 回复 by 院士 (#4)

*2024-5-2 12:42*

厉害了。![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by xinsui (#5)

*2024-5-2 13:12*

![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by mb_fidppcok (#6)

*2024-5-3 10:25*

牛逼了大佬

## 回复 by 安卓逆向test (#7)

*2024-5-3 15:25*

奇怪了，我看了下这个版本的app，我在它那个so init函数的入口处hook pthread_create是可以看到有检测线程的,应该是你下hook的时机没对

## 回复 by 天水姜伯约 (#8)

*2024-5-3 16:04*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  奇怪了，我看了下这个版本的app，我在它那个so init函数的入口处hook pthread_create是可以看到有检测线程的,应该是你下hook的时机没对
>
>

我发现了，Process.findModuleByAddress(ptr(this.returnAddress))，我在hook pthread_create时尝试获取了返回地址所属的so文件，frida脚本卡在这行代码没动了，我以为没有hook到

## 回复 by 文西哥 (#9)

*2024-5-4 12:11*

牛逼了大佬

## 回复 by AunCss (#10)

*2024-5-11 11:54*

姜师？

## 回复 by 道破红尘 (#11)

*2024-5-21 15:58*

厉害了

## 回复 by liukuo362573 (#12)

*2024-5-23 14:24*

学习到了，感谢楼主分享。

## 回复 by liukuo362573 (#13)

*2024-5-23 16:20*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  奇怪了，我看了下这个版本的app，我在它那个so init函数的入口处hook pthread_create是可以看到有检测线程的,应该是你下hook的时机没对
>
>

大佬你在那个 so init 函数入口处 hook 的脚本，能发一下吗？

## 回复 by ngiokweng (#14)

*2024-5-24 11:41*

學習了![image](https://bbs.kanxue.com/view/img/face/63.gif) 分享一下另外的解決思路, 一種是IO重定向maps(配合魔改的frida), 另一種是直接不加載libmsaoaidsec.so

## 回复 by Karwin (#15)

*2024-5-24 20:58*

大哥，我有个问题：我从豌豆荚下载的7.76.0版本的app，我hook了看到只开了一个线程，而且换了线程过不去检测。
之前我也遇到过类似的情况：跟着一个文章操作，app的版本一样，但是结果也是不一样。
您知道这是什么原因吗

## 回复 by ariesGinn (#16)

*2024-5-27 16:59*

当在Java.perform()中hook java层代码的时候无法绕过反frida机制

## 回复 by 梦_魇 (#17)

*2024-6-4 11:13*

在启动时候 hook  art中的regitsternative方法好像还是会被检测，我看了一下这个函数调用的返回地址没在本模块内，不知道怎么定位检测了， 楼主有遇到吗？

## 回复 by 未露姓名陈某 (#18)

*2024-6-5 17:22*

你不会就是那个传说中的孔明关门弟子吧

## 回复 by mb_rugymctl (#19)

*2024-7-25 17:02*

老哥，私一个APP逆向，有偿

## 回复 by 养只猫不好么 (#20)

*2024-7-25 18:28*

感谢分享

## 回复 by mb_rugymctl (#21)

*2024-7-25 21:21*

老哥，私一个APP逆向，有偿

## 回复 by MANKVIS (#22)

*2024-8-5 18:23*

>
> [ariesGinn](https://bbs.kanxue.com/user-942183.htm)
>
>  当在Java.perform()中hook java层代码的时候无法绕过反frida机制
>
>

请问解决了吗

## 回复 by 北袅 (#23)

*2024-10-26 15:53*

>
> [MANKVIS](https://bbs.kanxue.com/user-919319.htm)
>
>  请问解决了吗
>
>

同问

## 回复 by mb_kthocqep (#24)

*2024-12-13 16:58*

其实替换一次就行了，打印下retval两次地址你就会发现都是相同的，因为替换的是函数定义，而且不是调用地～～

## 回复 by shley2333 (#25)

*2025-1-2 17:34*

设置延时注入就可以
setTimeout(function() {
    Java.perform(function () {
        console.log("hello bilibili");
    })
}, 1000); // 1000 毫秒等于 1 秒

## 回复 by yggcwhat (#26)

*2025-1-5 15:12*

>
> [北袅](https://bbs.kanxue.com/user-951483.htm)
>
>  同问
>
>
>

+1

## 回复 by 荧光之夏 (#27)

*2025-1-6 12:07*

tql

## 回复 by Janeho117 (#28)

*2025-2-17 23:31*

tql

## 回复 by iBa0 (#29)

*2025-3-23 17:11*

现在对抗已经升级了c，libmsaoaidsec已经被摩擦的不成样子，app开发商自己搞svc检测

## 回复 by mb_gwugqjlw (#30)

*2025-12-23 11:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Karwin](https://bbs.kanxue.com/user-999871.htm)
>
>  大哥，我有个问题：我从豌豆荚下载的7.76.0版本的app，我hook了看到只开了一个线程，而且换了线程过不去检测。
> 之前我也遇到过类似的情况：跟着一个文章操作，app的版本一样，但是结果也是不一样 ...
>
>

遇到了相同的问题。请问你解决了嘛
