---
title: '[原创] microdbg - 纯 go 实现 android 模拟框架'
url: https://bbs.kanxue.com/thread-285377.htm
tid: 285377
author: 为你芯冻
date: '2025-01-26'
tags: [Android安全, 原创, 逆向分析, 源码框架]
crawled_at: '2026-08-11T08:41:28+00:00'
replies: 22
---

unidbg 很香, 但又苦于 java 用的不太习惯, 于是开发了这款纯基于 go 实现的模拟框架 microdbg

[microdbg](https://github.com/wnxd/microdbg) 定义了模拟器, 调试器, 模块, 任务, 文件系统等一些基础接口
[microdbg-loader](https://github.com/wnxd/microdbg-loader) 可执行文件格式转换成模块加载
[microdbg-unicorn](https://github.com/wnxd/microdbg-unicorn) 基于 unicorn 引擎封装的模拟器后端
[microdbg-linux](https://github.com/wnxd/microdbg-linux) linux 内核调用的模拟实现代码
[microdbg-java](https://github.com/wnxd/microdbg-java) 定义了 JNI 相关的接口, 与 java 基础类型的反射实现框架
[microdbg-android](https://github.com/wnxd/microdbg-android) 安卓运行时的实现
 ![image](https://bbs.kanxue.com/upload/attach/202501/634873_RJKS98UMNP5MKRM.webp)
上述研究案例放在[microdbg-example](https://github.com/wnxd/microdbg-example)

以上代码仅供研究学习。
欢迎大家提供改进建议或者参与一起开发

接下来的开发计划
[microdbg] 增加对 x86, x86_64 的支持
[microdbg-loader] 增加对 pe, mach-o 的支持
[microdbg-linux] 完善系统调用

以下是未来可能新增支持的开发计划
[microdbg-dynarmic] 新增 dynarmic 引擎模拟器后端
[microdbg-darwin] 新增 darwin 内核的实现
[microdbg-ios] 新增 ios 运行时的实现

---

补充一下测试需要的 so 文件, 忘记 git 规则把 so 排除了

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-1-26 14:42*

感谢分享

## 回复 by mb_rjdrqvpa (#3)

*2025-1-26 18:47*

相比unidbg的优缺点是什么？

## 回复 by 为你芯冻 (#4)

*2025-1-26 18:51*

模拟调用封装成任务形式，解决了 unidbg 无法嵌套调用的问题，然后每次模拟不会重启模拟器，提升继续模拟执行的性能

## 回复 by mb_ldbucrik (#5)

*2025-1-26 21:42*

>
> [为你芯冻](https://bbs.kanxue.com/user-634873.htm)
>
>  模拟调用封装成任务形式，解决了 unidbg 无法嵌套调用的问题，然后每次模拟不会重启模拟器，提升继续模拟执行的性能
>
>

因为AndroidNativeEmu也是类似unidbg的框架，但是对Unidbg 作为 Java 实现的工具，通过更完善的 JNI 和系统调用模拟，你这个有解决这些问题吗

## 回复 by 暗月隐落 (#6)

*2025-1-26 22:56*

加油大佬,期待更多大佬的视频教程

## 回复 by 为你芯冻 (#7)

*2025-1-26 23:35*

AndroidNativeEmu 属于 python 框架，和我赛道不一样，熟悉 go 开发的人更愿意尝试 microdbg

## 回复 by mb_asiwnxyv (#8)

*2025-1-31 13:08*

=== RUN   TestSm4EncryptBox
    ijm_test.go:94: zip: not a valid zip file
--- FAIL: TestSm4EncryptBox (0.01s)

这种错误代表着什么 跑的测试案例  git clone下来没改任何东西。

## 回复 by 为你芯冻 (#9)

*2025-1-31 17:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_asiwnxyv](https://bbs.kanxue.com/user-963863.htm)
>
>  === RUN TestSm4EncryptBox
>  ijm_test.go:94: zip: not a valid zip file
> --- FAIL: TestSm4Encrypt ...
>
>

只有 TestSm4EncryptBox 出现报错吗, 示例只有 2.apk 和 runtime/10.zip 涉及到 zip

## 回复 by 为你芯冻 (#10)

*2025-1-31 17:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_asiwnxyv](https://bbs.kanxue.com/user-963863.htm)
>
>  === RUN TestSm4EncryptBox
>  ijm_test.go:94: zip: not a valid zip file
> --- FAIL: TestSm4Encrypt ...
>
>

看下是不是没安装 git lfs 导致 apk 文件没有 clone 下来

## 回复 by mb_asiwnxyv (#11)

*2025-1-31 17:39*

>
> [为你芯冻](https://bbs.kanxue.com/user-634873.htm)
>
>
>
>
>
>
>
>  mb_asiwnxyv
>
>
>
>  === RUN TestSm4EncryptBox
>  ijm_test.go:94: zip: not ...
>
>

测试案例都报错 都是这个错误 平台是macos15.3  go1.23.5 依赖也都下载了

## 回复 by mb_asiwnxyv (#12)

*2025-1-31 17:39*

>
> [为你芯冻](https://bbs.kanxue.com/user-634873.htm)
>
>  看下是不是没安装 git lfs 导致 apk 文件没有 clone 下来
>
>

是的 你说的对 我查看了大小是只有134字节 已经本地下载了

## 回复 by 为你芯冻 (#13)

*2025-1-31 17:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_asiwnxyv](https://bbs.kanxue.com/user-963863.htm)
>
>  测试案例都报错 都是这个错误 平台是macos15.3 go1.23.5 依赖也都下载了
>
>

m系芯片的 macos 增加了 pthread_jit_write_protect_np 导致 写和执行不能同时出现在内存属性上, 可能导致有一些奇怪的 bug

## 回复 by 又见飞刀z (#14)

*2025-2-7 14:39*

NB,我本来也想写个的，名字都想好了：unidbgo，我用go主要是为了业务代码安全，java代码太容易反编译了，但感觉工作量有点大，就暂时搁置了，换成了另一种快照模拟的方案：直接把unidbg模拟运行好的快照放到unicron-go里执行，省去补环境了，并且更安全了（只有一个快照文件，没有任何业务代码）

## 回复 by 为你芯冻 (#15)

*2025-2-7 15:47*

>
> [又见飞刀z](https://bbs.kanxue.com/user-673625.htm)
>
>  NB,我本来也想写个的，名字都想好了：unidbgo，我用go主要是为了业务代码安全，java代码太容易反编译了，但感觉工作量有点大，就暂时搁置了，换成了另一种快照模拟的方案：直接把unidbg模拟运 ...
>
>

请教一下快照模拟怎么实现的, java环境和syscall都不用补吗
是把每一步的运算结果都储存了, 运行时候按顺序还原吗

## 回复 by 又见飞刀z (#16)

*2025-2-7 16:48*

>
> [为你芯冻](https://bbs.kanxue.com/user-634873.htm)
>
>  请教一下快照模拟怎么实现的, java环境和syscall都不用补吗
> 是把每一步的运算结果都储存了, 运行时候按顺序还原吗
>
>

大部分的Java环境和syscall都发生在核心算法执行前，这些unidbg都帮忙处理完了，当然有些是避免不了的，比如各种内存操作，这些处理完基本上没啥问题了

## 回复 by 为你芯冻 (#17)

*2025-2-7 17:57*

>
> [又见飞刀z](https://bbs.kanxue.com/user-673625.htm)
>
>  大部分的Java环境和syscall都发生在核心算法执行前，这些unidbg都帮忙处理完了，当然有些是避免不了的，比如各种内存操作，这些处理完基本上没啥问题了
>
>

我知道了. 3q

## 回复 by 啊你好哇123 (#18)

*2025-2-15 13:42*

>
> [又见飞刀z](https://bbs.kanxue.com/user-673625.htm)
>
>  NB,我本来也想写个的，名字都想好了：unidbgo，我用go主要是为了业务代码安全，java代码太容易反编译了，但感觉工作量有点大，就暂时搁置了，换成了另一种快照模拟的方案：直接把unidbg模拟运 ...
>
>

大佬问下这种模拟器啥的是咋开发的有没有书籍教程啥的网上找不到

## 回复 by hhhaiai (#19)

*2025-2-16 20:14*

太厉害了。

## 回复 by 夜惜风雨 (#20)

*2025-3-28 21:46*

第三方hook框架 HookZz 类似的go版本，好像没有

## 回复 by 夜惜风雨 (#21)

*2025-3-29 03:01*

还有就是Dynarmic 引擎比Unicorn快非常多，大佬考虑集成么

## 回复 by mb_rlmghtdv (#22)

*2025-5-20 17:48*

大佬 补文件 有问题 我用了art.LinkFS 却没有成功补上

## 回复 by mb_xyntbivj (#23)

*2026-2-7 09:44*

这个如何直接调用so的方法，类似unidbg中的module.callFunction
