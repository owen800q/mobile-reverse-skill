---
title: '[原创]Native层binder与syscall代理技术'
url: https://bbs.kanxue.com/thread-290553.htm
tid: 290553
author: 孤木落
date: '2026-03-28'
tags: [Android安全, 原创, 基础理论, 逆向分析, 程序开发, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-08-08T10:16:21+00:00'
replies: 9
---

# Native层binder与syscall代理技术

灵感来源：[【Android】深入Binder底层拦截](https://www.52pojie.cn/forum.php?mod=viewthread&amp;tid=1866468)

开源地址：[AndProxy - Github](https://github.com/ggggmllll/AndProxyDemo)

由于本人是个菜鸟（自学android野路子这一块），并不是很了解binder通信的实际原理与调用链，所以AndProxy其实还是有很多问题。而且学业繁忙，检查问题与修复bug能力有限，期待更多大佬贡献代码。

## 代理技术原理

- Syscall代理：源于我对老文章[某去签工具分析](https://ggggmllll.github.io/2025/12/20/%E6%9F%90%E5%8E%BB%E7%AD%BE%E5%B7%A5%E5%85%B7%E5%88%86%E6%9E%90/)（这里有一个兼容性问题，`seccomp_notify`机制需要内核版本大于5.10，所以一般要出场Android 12以上的机型才可用）
- ioctl hook：就是简单的GotHook。但是有两个比较重要的细节（坑） 1. 由于Android的命名空间机制，`dl_iterate_phdr`无法找到libbinder.so，只能手动扫描/proc/self/maps 2. Got项没有写权限，必须先`mprotect`赋予`w`可写再修改，最后把权限改回去
- binder数据解析与修改：参考[【Android】深入Binder底层拦截](https://www.52pojie.cn/forum.php?mod=viewthread&amp;tid=1866468)

## Syscall 代理技术的一些细节

其实这个框架最早是作为我写的一个拦截皇室战争的`exit_group`等退出函数的frida模块被开发出的。为什么不使用已经成熟的seccomp+sigaction机制？因为皇室战争的加固提供方Promon已经对此通过主动注册信号处理函数作了防范，但是seccomp_notify处于兼容性原因，暂时没有进行防范。

在拦截退出时，我们有一个基本需求：打印推出前的函数调用栈，快速判断触发闪退位置。

但是，`seccomp_notify`机制本身不支持获取syscall被调用时的寄存器上下文，所以我们必须利用额外的机制，自然联想到信号量。基本流程是，若要获取寄存器，则在supervisor_loop启动前注册一个信号处理函数，syscall被调用时会触发supervisior，此时supervisor会接收到当前寄存器，再通过shared memory传回supervisior。优点是可以利用SIG_USER2这种很少被注册处理函数，但是可以触发处理函数的信号，这样防御成本就大大增加了。

然后就是第一个坑，通过查阅文档，syscall调用后，进程处于阻塞状态，此时如果发送了信号，就会打断阻塞，syscall也不会被调用。为此，我们必须将sig的flag加上restart，这样就可以再次调用syscall进入supervisor。我们将在第一次进入supervisor进入时获取寄存器上下文，在第二次进入时调用回调函数进行真正的处理。

第二个坑是，supervisor和主进程不是同一个进程，所以注册callback时可能会有bug。我主要利用的是fork不会改变模块布局，所以如果模块在supervisor启动前就已经被加载，那么他的函数指针在supervisor和被监控进程中是等价的，直接传递即可。

最后是如何在被监控进程调用可能被seccomp限制的回调？这个利用了seccomp的限制以线程为单位的特性，执行java callback的线程先于seccomp的bpf规则注册就不会被限制，所以会在JNI_OnLoad中先启动线程，init函数在此之后调用。（从这个角度看SvcInterceptor的addFile方法其实没有什么用，可能会在后续版本移除）

>
> 具体实现参考：seccomp_hook.cpp, SvcInterceptor.cpp
>
>
>

## binder代理的一些细节

感谢 @iofomo（数字锋芒）大佬的的无私分享，主要技术细节都在他的blog中，这里只分享几个小问题的解决方案。

首先是服务名解析（Stub中的DESCRIPTOR字段），按照大佬分享的方法没有解析出来。但是注意到[strlen][utf16_str]的固定结构，采用了模糊搜索方法，成功解析服务名（缺点是很容易误匹配，所以我加了很多限制）。

然后是为什么选择Got Hook？因为我不想在代码段留脏页（bushi）。其实是因为Got Hook比较简单，而且binder通信位置相对集中在libbinder.so，所以选择对libbinder.so进行Got Hook。

最后是解包Parcel对象，这个放在java层做比较简单，具体示例在`app`模块中有演示，注意一定要清除缓存

## 技术展望

我开发AndProxy的最初目的是做android运行时监控，但是AndProxy还可以用于做隔离沙盒，PMS Hook，IO重定向等等。目前我计划将其用于开发APP多开和监控沙盒，但是苦于不会Framework，而且学业繁忙，希望有大佬可以加入开发。

---

# 回复

## 回复 by iBa0 (#2)

*2026-3-29 11:15*

牛逼

## 回复 by 墨穹呢 (#3)

*2026-3-29 11:59*

感谢分享

## 回复 by Imxz (#4)

*2026-3-30 09:28*

tql

## 回复 by mb_mrgbywba (#5)

*2026-4-3 01:18*

强强

## 回复 by 温泉划水鱼 (#6)

*2026-4-4 17:56*

仙品

## 回复 by uni7corn (#7)

*2026-4-27 17:50*

是否有技术交流群，可参与Android多开开发。

## 回复 by 孤木落 (#11)

*2026-4-28 21:52*

因为一直没人联系，所以还没建群。不过您可以用github的readme中的QQ邮箱对应的qq号直接联系我，十分感谢

## 回复 by 孤木落 (#12)

*2026-4-28 21:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  uni7corn](https://bbs.kanxue.com/user-909566.htm)
>  是否有技术交流群，可参与Android多开开发。
>

## 回复 by wx_北极星_493 (#13)

*2026-5-19 11:22*

看看
