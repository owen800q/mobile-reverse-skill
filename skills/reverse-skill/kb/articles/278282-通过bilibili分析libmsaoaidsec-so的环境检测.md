---
title: 通过bilibili分析libmsaoaidsec.so的环境检测
url: https://bbs.kanxue.com/thread-278282.htm
tid: 278282
author: 菜鸟泽
date: '2023-08-04'
tags: [Android安全, 逆向分析]
crawled_at: '2026-07-31T14:39:35+08:00'
replies: 7
---

之前在论坛看到这个帖子<https://bbs.kanxue.com/thread-277034.htm>
通过nop的方式过掉了frida检测，一时兴起，想要分析一下具体的检测逻辑

## 样本版本7.26.1，包名tv.danmaku.bili

通过上文楼主给出的方法定位了检测函数的地址，再通过IDA进行调试，且在调试的时候需要先在静态文件中把断点下好，这里就不再赘述调试过程，直接上分析结论

# 一、offset=0x10975处 --检测线程1

存在三个检测方法
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_DCCHGGTANJ5HWX9.png)

## 1.1 通过/proc/%d/status 读取当前进程ptracerPid 穿入第二个方法作为参数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_2NNG2GJ5UME3JP8.png)

## 1.2 查看ptraceId对应的进程信息，读取了/proc/ptracerPid/status 获取PPid，与当前应用进程号做对比，判断是否为应用主进程的子进程进行了ptrace操作

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_53C4HGMGWZX62FN.png)

## 1.3 遍历/proc/self/task/xx/stat文件，读取当前线程状态是否为tracing

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_DHC5ADE4DP8KCB6.png)
实际过程中stat的输出格式是 pid (name) status xxxxxxx
该方法就是判断读取到的status是否为“T”(会通过 |0x20 将其转为“t”,ASCII码为116)

## 1.4 （猜测）检测到异常后的处理方式-等待其他大佬指正~

处理代码未作详细分析，这里只说说我根据一些字符串的猜测：
在上述三个方法检测到异常后，会调用JNI_GetCreatedJavaVMs方法
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_VW59PXGRJMVNRRR.png)
而这个方法是获取已经创建的 Java 虚拟机实例，根据“使用frida-spwan模式hook会导致应用短暂卡顿后，frida进程退出，应用恢复运行”的现象，我猜测是把被hook进程干掉了，以一个新进程运行了上面的Java 虚拟机实例。

# 二、offset=0x11129处 --检测线程2

该方法前半部分是各种字符串的解密，最后的四个方法才是检测
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_XJTPR6MX8EEGXFK.png)

## 2.1 检测 proc/self/task/%s/status 特征字符串 gum-js-loop gmain

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_QWYZ6SKGT2S7U6P.png)

## 2.2 检测/proc/self/fd/%s 特征字符串 injector

 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_9TB8WM3AXDRRMN4.png)

## 2.3 检测/proc/self/maps 特征字符串

检测/data/local/tmp 及对应文件的权限 ‘x’ 'r'
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_S8TCQC2PVQTJR5F.png)
对命中的文件进行解析，检查 _AGENT_1.0 frida-agent特征
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_97NSNXQT2RDPJJC.png)
PS：通过010 editor 打开fridaserver，可发现对应特征

## 2.4 检测 libart.so的inline hook特征

参考了这篇文章<https://bbs.kanxue.com/thread-268586.htm>
解析libart.so 中的_ZN3art9ArtMethod12PrettyMethodEb，是否存在inlinehook特征
读取libart.so-_ZN3art9ArtMethod12PrettyMethodEb
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_86PAA3VS9VG28FN.png)
确定hook特征后 通过执行svc执行进行退出（具体执行会动态解密）
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_CS3G686YJVGW4S6.png)

## 2.5 检测到异常后的退出逻辑

在上述检测逻辑后，部分使用的是直接的函数调用exit(0)，另外一部分是使用svc调用 exit_group，所以仅hook libc的exit函数是无法做到绕过检测的。

# 三、其他

## 3.1 字符串的解密

上述所有方法中的检测字符串都是通过动态解密释放的
以下是我的解密方法
 ![图片描述](https://bbs.kanxue.com/upload/attach/202308/945828_5B7VVXRAWT3XBRP.png)

# 四、总结

1.这个样本的检测方法trace特征检测、frida特征字符串检测、inlinehook特征检测
2.字符串比较方式是直接调用的strstr或strcmp方法
3.检测到异常的退出方法是直接调用exit、执行scv指令调用exit_group

## 小白第一次发帖，可能分析和描述中存在错漏，望大佬指点~

---

# 回复

## 回复 by huangjw (#2)

*2023-8-4 16:40*

沙发，给个优评

## 回复 by mudebug (#3)

*2023-8-5 14:38*

单走一个6

## 回复 by eastpolar (#4)

*2024-2-6 21:44*

牛啊牛啊，学习了

## 回复 by 文心雕龙_968271 (#5)

*2024-8-30 20:21*

谢谢楼主，开卷有益

## 回复 by mb_zfqvurgb (#6)

*2024-10-11 16:42*

很棒，赞赞赞

## 回复 by mb_ytiyqklv (#7)

*2024-12-11 02:18*

请问字符串是怎么还原出来的只是靠猜测吗

## 回复 by 菜鸟泽 (#8)

*2024-12-11 15:17*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ytiyqklv](https://bbs.kanxue.com/user-1005749.htm)
>
>  请问字符串是怎么还原出来的只是靠猜测吗
>
>
>

通过ida断点调试，看内存中变量指向的值
