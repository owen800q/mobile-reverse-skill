---
title: '[分享][下载]Game修改器2.7优化界面，Frida支持双模式运行自定义指令'
url: https://bbs.kanxue.com/thread-276619.htm
tid: 276619
author: 冷冻猫咪
date: '2023-03-25'
tags: [Android安全, 分享, 逆向分析, NDK分析, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-08-11T08:48:23+00:00'
replies: 21
---

[点这里下载](https://www.123pan.com/s/VDcDVv-n1rfA.html)

![image](https://bbs.kanxue.com/upload/attach/202303/915097_UHDZNBG4U8RAXD4.jpg)

![image](https://bbs.kanxue.com/upload/attach/202303/915097_5TUWDNYS2PDJGQQ.jpg)

请手动打开通知权限，toast提示需要

请手动打开 后台弹出界面 权限

经测试个别系统可能没有弹出权限会崩溃

这个权限无法动态申请。。。

![image](https://bbs.kanxue.com/upload/attach/202303/915097_3JN3RNBXZF2ZZMB.jpg)

Frida脚本指令使用注意

[pack]代码包名输入框内的文本

[pid]代码通过包名输入框内文本获取指定程序pid

[path]代表选择脚本按钮所选择的脚本路径

指令使用方式一

-e -f [pack] -s [path]

指令使用方式二

-n com.myapp -s /sdcard/hook.js

注意每中间必须用空格隔开，与电脑端命令行Frida指令一样

脚本执行记录会在/sdcard/Hook/log.txt生成脚本执行结果日志

暂时没测试出其他问题，发个新帖说明下更新Frida脚本使用方式

---

# 回复

## 回复 by 冷冻猫咪 (#2)

*2023-3-25 14:12*

如果使用输入框内包名直接用[pack]代替，脚本执行指令为-s [path]跟电脑端不同注意，支持Attach模式-n -p执行脚本，支持Spawn -f模式执行脚本根据需求自行选择。

## 回复 by 白帽子黑客 (#3)

*2023-3-25 15:09*

这软件能脱壳不，能脱的话，咋操作

## 回复 by 白帽子黑客 (#4)

*2023-3-25 16:07*

脱不了壳，文件没东西

## 回复 by 白帽子黑客 (#5)

*2023-3-25 16:08*

![image](https://bbs.kanxue.com/upload/attach/202303/975299_KS33MHKVVJYJR5X.jpg)![image](https://bbs.kanxue.com/upload/attach/202303/975299_72XVAAHUVPDHFRW.jpg)

## 回复 by 冷冻猫咪 (#6)

*2023-3-25 16:17*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  脱不了壳，文件没东西
>
>

用脚本可以脱，不知道你的脚本怎么写的，所以可能是脱壳失败！

## 回复 by 白帽子黑客 (#7)

*2023-3-25 16:37*

你的脱壳脚本上传下呗，用你之前的hook.js脚本，没反应

## 回复 by 冷冻猫咪 (#8)

*2023-3-25 17:07*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  你的脱壳脚本上传下呗，用你之前的hook.js脚本，没反应
>
>

https://bbs.kanxue.com/thread-275967.htm

## 回复 by 白帽子黑客 (#9)

*2023-3-25 17:54*

我是下载了这个脚本，脱壳也dump没啥反应![image](https://bbs.kanxue.com/view/img/face/9.gif)

## 回复 by 白帽子黑客 (#10)

*2023-3-25 17:59*

**究竟哪出问题了，dump没反应![image](https://bbs.kanxue.com/upload/attach/202303/975299_UMGSK8WMRCVN9RF.jpg)**

## 回复 by 冷冻猫咪 (#11)

*2023-3-25 19:19*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  我是下载了这个脚本，脱壳也dump没啥反应[em_9]
>
>

可能这个壳有检测，或者别的原因。。。

## 回复 by 白帽子黑客 (#12)

*2023-3-27 15:40*

注入脚本，脚本执行，运行了，为舍dump出啥东西，哪环节出了问题

## 回复 by 冷冻猫咪 (#13)

*2023-3-27 17:28*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  注入脚本，脚本执行，运行了，为舍dump出啥东西，哪环节出了问题
>
>

不知道你脱的什么壳，可能是脚本问题或者被加固检测到。
脚本不是万能的不是说所有壳都能脱

## 回复 by 万里星河 (#14)

*2023-3-27 17:44*

支持一下 不过我觉得game修改器可以再添加一个功能 论坛大佬曾写过一个通过frida像GG那样搜索游戏内存数据的框架 可是试试整合进来 搞个frida版的GG修改器

## 回复 by 白帽子黑客 (#15)

*2023-3-27 22:02*

能搞成DITOR郊果样，能脱壳就给力了

## 回复 by 白帽子黑客 (#16)

*2023-3-27 22:03*

试了好几次，都脱不了

## 回复 by 白帽子黑客 (#17)

*2023-3-27 22:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  支持一下 不过我觉得game修改器可以再添加一个功能 论坛大佬曾写过一个通过frida像GG那样搜索游戏内存数据的框架 可是试试整合进来 搞个frida版的GG修改器
>
>

你DITOR脱壳脚本写的相当给力

## 回复 by 冷冻猫咪 (#18)

*2023-3-28 15:45*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  试了好几次，都脱不了
>
>

有可能是手机系统不兼容，frida服务没法启动只测试了光速10可用

## 回复 by 白帽子黑客 (#19)

*2023-3-28 17:11*

>
> [冷冻猫咪](https://bbs.kanxue.com/user-915097.htm)
>
>  有可能是手机系统不兼容，frida服务没法启动只测试了光速10可用
>
>

我说呢，安卓6系统没反应![image](https://bbs.kanxue.com/view/img/face/1.gif)  后期能升级兼容吗

## 回复 by 冷冻猫咪 (#20)

*2023-3-28 20:23*

>
> [白帽子黑客](https://bbs.kanxue.com/user-975299.htm)
>
>  我说呢，安卓6系统没反应[em_1] 后期能升级兼容吗
>
>

没有6系统的手机估计没戏了，vmos安卓7试了崩溃听说是虚拟机不支持，这个so不是我写的只是做了些优化更方便使用！！！

## 回复 by 暖心系 (#21)

*2023-4-1 22:20*

大佬接开发吗？可否留个联系方式

## 回复 by 冷冻猫咪 (#22)

*2023-4-2 13:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  暖心系](https://bbs.kanxue.com/user-821131.htm)
>
>  大佬接开发吗？可否留个联系方式

我没事自己玩玩，没做过项目简单的功能可以做做！！！
