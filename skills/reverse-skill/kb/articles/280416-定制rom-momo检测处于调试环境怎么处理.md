---
title: 定制rom，momo检测处于调试环境怎么处理
url: https://bbs.kanxue.com/thread-280416.htm
tid: 280416
author: 搬砖最积极
date: '2024-01-31'
tags: [Android安全, 基础理论]
crawled_at: '2026-08-11T08:46:09+00:00'
replies: 12
---

如图所示，处于调试环境。开发者选择和adb都没开启的，不知道哪个prop属性或proc文件异常了，有遇到过的吗。
 ![image](https://bbs.kanxue.com/upload/attach/202401/993791_5DKHBJ2PBKWCE3W.webp)

---

# 回复

## 回复 by 狄人3 (#2)

*2024-1-31 22:04*

这个好像就是检测debuggable属性的吧，看看ro.debuggable是不是1？

## 回复 by 搬砖最积极 (#3)

*2024-1-31 23:02*

>
> [狄人3](https://bbs.kanxue.com/user-936025.htm)
>
>  这个好像就是检测debuggable属性的吧，看看ro.debuggable是不是1？
>
>

试了修改不是检测这个属性

## 回复 by mb_qimctavn (#4)

*2024-2-1 12:45*

ro.adb.secure=1

## 回复 by 搬砖最积极 (#5)

*2024-2-1 13:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_qimctavn](https://bbs.kanxue.com/user-967474.htm)
>
>  ro.adb.secure=1
>
>

看了安全的prop都是1，不是这个引起
getprop|grep sec
[aaudio.hw_burst_min_usec]: [2000]
[dalvik.vm.dexopt.secondary]: [true]
[init.svc.zygote_secondary]: [running]
[init.svc_debug_pid.zygote_secondary]: [993]
[pm.dexopt.install-bulk-secondary]: [verify]
[pm.dexopt.install-bulk-secondary-downgraded]: [extract]
[ro.adb.secure]: [1]
[ro.boottime.zygote_secondary]: [5901644805]
[ro.build.version.security_patch]: [2024-01-05]
[ro.secure]: [1]
[ro.vendor.build.security_patch]: [2020-10-05]
[security.perf_harden]: [1]

## 回复 by DiamondH (#6)

*2024-2-1 13:43*

userdebug包引起的吧

## 回复 by 寻梦之璐 (#7)

*2024-2-1 14:42*

你编译user包

## 回复 by 金坷垃彩虹 (#8)

*2024-2-1 17:46*

su文件？su文件没改，被直接命令行su了吧，返回没有权限就可以确定是调试环境

## 回复 by 搬砖最积极 (#9)

*2024-2-1 21:38*

>
> [DiamondH](https://bbs.kanxue.com/user-720798.htm)
>
>  userdebug包引起的吧
>
>

6,7楼正解了![image](https://bbs.kanxue.com/view/img/face/13.gif)，我是userdebug魔改user包，各种操作都改了，还是不行，应该多编译打包了一些debug服务，目前还没排查出来。

## 回复 by 思睿 (#10)

*2024-2-6 16:34*

init.svc.adbd应该是这个属性 编译的是eng

## 回复 by wx_Goodwell (#11)

*2024-2-6 20:35*

手机也是定制的吗

## 回复 by luole (#12)

*2024-2-6 22:03*

“处于调试环境(26)” 检测有三：1.prctl(PR_GET_DUMPABLE)  2.ro.debuggable 3.ro.secure

## 回复 by 找工具的菜鸡 (#13)

*2026-4-28 21:48*

大佬，怎么联系呢
