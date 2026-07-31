---
title: '[原创]FridaLocalManager 本地持久化群控管理工具'
url: https://bbs.kanxue.com/thread-278564.htm
tid: 278564
author: 复活甲
date: '2023-08-24'
tags: [Android安全, 原创, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:39:06+08:00'
replies: 6
---

![图片描述](https://bbs.kanxue.com/upload/attach/202308/961239_4EJA8NNBES78XYP.png)

## 0x01 前言

FridaLocalManager是我开发的一个本地持久化、可以动态扩展的框架。在实际的开发过程，经常会遇到frida-server中断，RPC调用时间久了APP又出现闪退、卡顿等异常问题，需要人为的手动干预，非常影响业务的发展。如果半夜出现了问题，即使加入了监控报警，我们也不能起来跑到公司去弄吧。当然frida持久化的工具很多，寒冰大佬的FridaManager也是一个很好的解决方案。

## 0x02 优点

1.支持frida-server开机、宕机自动启动
2.支持APP中断、卡顿、退出自动重启
3.支持手机群控管理，管理100+台手机轻轻松松

## 0x03 FridaLocalManager使用流程

### 1.配置frida-server监控脚本

将monitor_frida_server.sh移动到手机/data/local/tmp/目录下。代码比较简洁，短小而精悍，里面的frida 启动方式、端口、命名都可以自由发挥，考虑到每个人的习惯都不一样，就不制作成magisk的模块，一旦定型后面改起来也是很麻烦的，完全的可扩展，自由发挥。

| 1234567891011121314 | `#!/system/bin/sh` `echo` `"frida-server 监控脚本"` `while` `[` `1` `-``gt` `0` `]; do``port``=``$(netstat` `-``nlt \| grep` `6666` `\| wc` `-``l)``if` `[ $port` `-``ne` `1` `]; then``echo` `"frida-server 断开连接，正常在启动中...."``$(cd` `/``data``/``local``/``tmp && .``/``fs1280` `-``l` `0.0``.``0.0``:``6666``)``else``echo` `"frida-server 正在运行...."``fi``sleep` `1s``done` |
|-|-|

### 2.设置frida-server开机启动。

将magisk.sh移动到移动到 /data/adb/post-fs-data.d 重启手机后，可完成对frida server 监控 可以用 netstat -nlp | grep 6666 来检查启动状态。

### 3.配置设备

device_list 在代码中我是固定的，这里看每个人的需求，自由扩展。比如我又100台设备，可以写在redis里面，从redis里面获取，也可以单独建立一个文件读取。剩下的都是不影响的，主打的就是可扩展。

| 123456789101112131415161718192021222324252627 | `while` `True``:``print``(``"开始执行..........................................................."``)``# 设备列表 此处可以设置成动态获取，无线扩展``device_list` `=` `[``"0000"``,` `"192.168.137.63:6666;5000"``]``i` `=` `1``thread_pool` `=` `[]``for` `item` `in` `device_list:``# 创建新线程``thread_i` `=` `myThread(``"Thread-"` `+` `str``(i), i, item)` `thread_pool.append(thread_i)``i` `=` `i` `+` `1``# 开启新线程``try``:``print``(``"thread_pool 长度："``,` `len``(thread_pool))``for` `th` `in` `thread_pool:``th.start()``tid` `=` `1``print``(``"当前线程ID"``, tid, th)``for` `th` `in` `thread_pool:``th.join()``print``(``"退出主线程"``)``except` `Exception as e:``logging.exception(e)``print``(``'请求异常'``)``break``print``(``"结束执行....................................................."``)` |
|-|-|

### 监控每个程序的运行状态

| 12345678910111213141516171819202122232425262728293031323334353637 | `def` `monitor_thread(``self``):``while` `True``:``thread_list` `=` `[]``time.sleep(``30``)``for` `thread` `in` `threading.``enumerate``():``thread_list.append(thread.getName())``# print(thread.getName(), thread.ident)``thread_error_status` `=` `self``.redis_client.hget(``"frida_app_error"``, thread.getName())``if` `thread_error_status:``thread_error_status` `=` `thread_error_status.decode()``else``:``time.sleep(``3``)``continue``time.sleep(``2``)` `if` `thread_error_status` `=``=` `'1'``:``# 通过调用stop()方法关闭线程``exctype` `=` `SystemExit``tid` `=` `ctypes.c_long(thread.ident)``if` `not` `inspect.isclass(exctype):``exctype` `=` `type``(exctype)``res` `=` `ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))``if` `res` `=``=` `0``:``raise` `ValueError(``"invalid thread id"``)``elif` `res !``=` `1``:``# """if it returns a number greater than one, you're in trouble,``# and you should call it again with exc=NULL to revert the effect"""``ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,` `None``)``raise` `SystemError(``"PyThreadState_SetAsyncExc failed"``)``pass``# 终止完线程之后，重新打开此线程``time.sleep(``5``)``run_device` `=` `self``.redis_client.hget(``"frida_device_name_ip_hash"``, thread.getName()).decode()``thread_i` `=` `myThread(thread.getName(), thread.ident, run_device)``thread_i.start()``thread_i.join()``time.sleep(``5``)` |
|-|-|

## 0x04 运行效果

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/961239_PQ4YCD4GDD5HDR6.png)

好了，就到这里吧，想要体验的可以gitub中下载，后面会开发出有界面版本，直接在页面上点点就可以操作，还可以监控到每台设备当前的运行状态、请求次数等
后续更新会放在github:
[FridaLocalManager](https://github.com/jiadajun/FridaLocalManager)

---

# 回复

## 回复 by 智取棋 (#2)

*2023-8-24 11:36*

打卡

## 回复 by 秋狝 (#3)

*2023-8-24 14:14*

感谢分享

## 回复 by mb_fssslkzs (#4)

*2023-8-24 17:43*

yyds 6666

## 回复 by 阿里看看 (#5)

*2023-11-6 11:17*

大佬，看到你都做frida的群控工具了，想请教你一个问题。

请问有没有遇到接入手机多了以后，Frida就识别不到手机的问题，这个数量应该是10台以上。
比如我接入9台手机的时候，使用frida-ls-devices时，能正常获取到所有手机。

Id        Type    Name             OS
--------  ------  ---------------  ------------------
local     local   XTZJ-20211020RE  Windows 10.0.19041
ccebc4b0  usb     MI 6X            Android 9
20b758f6  usb     MI 6X            Android 9
437924e2  usb     MI 6X            Android 9
1e6b3cfe  usb     MI 6X            Android 9
557c4c0   usb     MI 6X            Android 9
b792138   usb     MI 6X            Android 9
1e86001f  usb     MI 6X            Android 9
19b3c646  usb     MI 6X            Android 9
2de6ead7  usb     MI 8 Lite        Android 9
barebone  remote  GDB Remote Stub
socket    remote  Local Socket

但再多接一台时，数据就变成
Id        Type    Name             OS
--------  ------  ---------------  ------------------
local     local   XTZJ-20211020RE  Windows 10.0.19041
barebone  remote  GDB Remote Stub
socket    remote  Local Socket

但是使用adb devices时是能够正常显示的。

## 回复 by 阿里看看 (#6)

*2023-11-6 11:19*

目前我在win10和centos 7上测都是一样，python3.11，frida 16.1.3

## 回复 by mobing (#7)

*2024-10-19 21:17*

![image](https://bbs.kanxue.com/view/img/face/63.gif)
