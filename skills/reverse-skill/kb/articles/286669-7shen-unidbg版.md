---
title: '[原创]7shen unidbg版'
url: https://bbs.kanxue.com/thread-286669.htm
tid: 286669
author: 小羽~
date: '2025-04-29'
tags: [Android安全, 原创, HOOK注入, 协议分析, NDK分析, 逆向分析, 基础理论]
crawled_at: '2026-08-10T03:07:32+00:00'
replies: 13
---

## 1. 概述

2025年最新版某视频，重点分析其7神参数生成算法。相比其他平台（如某书），xx的难度较低（无需大量环境补全代码），但需解决版本抓包与QUIC协议限制问题。‌本方案仅用于技术研究，请勿用于非法用途。

## 2.前言

### 2.1 准备工具

| 工具 | 版本/要求 | 建议说明 |
|-|-|-|
| xx App | ‌**34.1**‌（需特定脱壳工具处理加固） | 强调脱壳必要性，提供脱壳工具链接（如 [Frida-DexDump](https://github.com/hluwa/FRIDA-DEXDump)） |
| Frida | ‌**16.1.11+**‌（兼容 Android 12+） | 使用新版 Frida 避免 Hook 失效，提供降级方案 |
| Jadx | ‌**1.2.0+**‌（支持 DEX 转 Java 优化） | 建议开启反混淆插件（如 JEB） |
| Charles | ‌**4.6+**‌（需安装 BoringSSL 证书） | QUIC降级抓包 |
| unidbg | ‌**0.9.8**‌（需自行编译 JNI 库） | 附编译指南及依赖项（如 Android NDK r25b） |
| Root 设备（演示的是模拟器） | Android 9-13（推荐 Pixel 系列，避免厂商定制 ROM） | 推荐使用 Magisk Delta + Shamiko 隐藏 Root |

### 2.2 演示

直接运行，打印参数
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_NPS2UG4GWRNYS4H.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_2XC7J6AJNTZ2JQ6.webp)

## 3.大概流程

>
> 1. 抓包APP
> 2. hookAPP定位到算法位置
> 3. 找到具体的so文件
> 4. unidbg模拟执行
>
>
>

### 3.1 抓包

1.抓包 发现有ssl校验，接口请求失败
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_BENEHQTMUC7A2T4.webp)
2. 使用frida hook 走quic降级的方式，可以抓到包，但是这个方法只对33.1以下版本的app生效，抓包后发现请求头里面有7神参数
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_R2UGYP3CVYJWUF6.webp)

### 3.2 算法位置

1. 定位7神的位置，frida hook拦截器，这个比较简单就不演示
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_PYHH6AF2TUR7HK6.webp)
2. 发现拦截器里面是在tryAdd....方法生成的7神，点进去看看
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_NAFYPAQ5KA89D4W.webp)
3. 发现里面又调了别的方法，继续点进去，注意这是个接口 点进去得找到具体的实现类
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_7VZ7HZSVTNNV26D.webp)
4. 只看关键代码，里面又调了其他的方法，这个方法是native方法 c写的，开始找so文件
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_P6GQNHJMYSCRWNZ.webp)

### 3.3 找到具体的so文件

- 通过 Hook libart.so 的 RegisterNatives 函数，捕获动态注册的 JNI 方法表
- 找到具体的so文件，so文件就是libmetasec_ml.so
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_TDMHEE4CDM54377.webp)

### 3.4 unidbg模拟执行

unidbg调用a方法，补完环境这些流程整理到一起就是之前演示的效果了。
 ![image](https://bbs.kanxue.com/upload/attach/202504/1014160_ZY44NX75NBN5TJ3.webp)

---

# 回复

## 回复 by q525318656 (#2)

*2025-4-29 22:11*

???????????? 大神 怎么联系你

## 回复 by 黑屏 (#3)

*2025-4-30 07:58*

又一个广告贴

## 回复 by 小羽~ (#4)

*2025-4-30 10:11*

>
> [黑屏](https://bbs.kanxue.com/user-589509.htm)
>
>  又一个广告贴
>
>

怎么就广告了，之前某书发了个被删了

## 回复 by hacker521 (#5)

*2025-5-1 10:29*

建议发下unidbg补好的文件~

## 回复 by huluxia (#6)

*2025-5-3 11:57*

现在怎么抓包？xp代码不能用了

## 回复 by 安卓逆向test (#7)

*2025-5-3 22:57*

最新版本加密方法好像不是那个动态注册的函数了

## 回复 by 小太子奶 (#8)

*2025-5-5 16:06*

我跟到的函数怎么不一样，有联系方式交流吗

## 回复 by 小羽~ (#9)

*2025-5-6 09:10*

d3jvvJp3eHc5OTEyMDM=

## 回复 by 快乐的小跳蛙 (#10)

*2025-5-6 09:19*

unidbg jni编译指南在哪里呀

## 回复 by mb_ocigfxyo (#11)

*2025-5-7 10:48*

大神，怎么练习你

## 回复 by 小羽~ (#12)

*2025-6-17 10:45*

>
> [安卓逆向test](https://bbs.kanxue.com/user-973348.htm)
>
>  最新版本加密方法好像不是那个动态注册的函数了
>
>

是不是okttp还是混淆的哪个，好像的确不是了 不过最近没时间研究了

## 回复 by wx_插曲 (#13)

*2025-7-26 14:52*

不要v

## 回复 by thouger_ (#14)

*2025-10-31 09:37*

广告贴，，还是说更多的发不出来？
