---
title: '[原创]freeRASP签名检测和其他设备环境的绕过方案'
url: https://bbs.kanxue.com/thread-289794.htm
tid: 289794
author: wohowo
date: '2026-01-18'
tags: [Android安全, 原创, 逆向分析, 混淆加固, 脱壳反混淆, HOOK注入]
crawled_at: '2026-08-08T10:29:54+00:00'
replies: 147
---

针对国外Talsec freeRASP付费定制化加固的通杀绕过方案

本方案不hook一切应用代码，全部使用绕过系统底层来实现通杀效果，避免触碰应用代码这种不能复用的方式

本项目实现了针对 Talsec freeRASP 安全检测框架的完整绕过方案，采用四层防护体系，从内核层到应用层全面拦截检测

一、 Native 层 BPF 系统调用拦截
======================================================

核心原理：
使用 Linux BPF 机制在内核层拦截系统调用，在 SIGSYS 信号处理器中伪造返回值。这是最底层的拦截方式，应用无法绕过

绕过方案：

1. APK 签名伪造
    拦截 openat、read、fstat 系统调用并伪造
    当应用读取 apk 时，重定向到预存的 原包.apk（包含原始签名）

PS：其实freeRASP并没有直接去读取apk来验证签名，这里只是说一下svc的签名绕过方案，其他加固会直接读取apk来验证签名，包括谷歌的检测，应该写到自己的绕过框架里面，一股脑无脑绕过

2. /proc/self/maps 隐藏
    拦截 read 系统调用读取 maps 文件
    过滤所有一切敏感行

3. /proc/self/status 伪造
    将 Seccomp: 2 改为 Seccomp: 0
    隐藏 seccomp 过滤器的存在，这个隐藏方案其实不完整，加固厂商如果采取更严格的手段还是能检测到的，但是其实Zygote自己本身也会安装bpf，所以如果自己不安装的话，这个还是会检测到2，其实并不通过这个来检测

4. /proc/self/mounts 过滤
    过滤包含 magisk、zygisk、core/mirror 的挂载点
    隐藏 Magisk 相关挂载

5. Ftrace 检测绕过
    伪造 /proc/sys/kernel/ftrace_enabled
    伪造 /sys/kernel/debug/tracing/current_tracer

二、设备安全状态伪造
=============================================

核心原理：
Hook Java 层系统 API，伪造设备安全状态，绕过各类环境检测

绕过方案：

1. Root 检测绕过
   File.exists()                    > false     隐藏 /system/bin/su 等 70+ 个 root 路径，这个是从某个加密数组里解密出来的
   Runtime.exec()                   > 拦截      阻止执行 su、which su 等命令
   PackageManager.getPackageInfo()  > 抛异常    隐藏 Magisk、KernelSU 等 50+ 个 root 包名，这个也是从某个加密数组里解密出来的
   System.getenv("PATH")            > 过滤      移除 PATH 中的 /sbin 等路径，这个也是从某个加密数组里解密出来的

    这些路径全是从freeRASP的某个加密数组里解密出来的，不管自己有没有，反正一股脑全部隐藏就完了

   File.canWrite()                  > false     隐藏 /system、/data 可写状态

2. 开发者选项检测绕过
   Settings.Global.getInt("development_settings_enabled") > 0
   Settings.Global.getInt("adb_enabled")                  > 0

3. 设备锁屏检测绕过
   KeyguardManager.isDeviceSecure()     > true
   KeyguardManager.isKeyguardSecure()   > true
   BiometricManager.canAuthenticate()   > BIOMETRIC_SUCCESS

4. 网络/VPN 检测绕过
   NetworkCapabilities.hasTransport(TRANSPORT_VPN) > false
   NetworkInfo.getType()                           > TYPE_MOBILE
   NetworkInterface.getName()                      > 隐藏 VPN 接口

5. 调试检测绕过
   Debug.isDebuggerConnected() > false
   Debug.waitingForDebugger()  > false

6. SIM 卡检测绕过
   TelephonyManager.getSimState()                       > 5 (SIM_STATE_READY)
   TelephonyManager.getSimOperator()                    > "40445" (Airtel India)
   TelephonyManager.getSimOperatorName()                > "Airtel"
   TelephonyManager.hasIccCard()                        > true
   SubscriptionManager.getActiveSubscriptionInfoCount() > 1

7. Google Play License (pairip) 绕过
    拦截 bindService() 对 com.android.vending 的绑定请求
    返回伪造的 FakeLicensingBinder

    国内设备没有谷歌环境，可以通过这个方案来绕过

三、 硬件密钥库与签名哈希伪造
===============================================

核心原理：
伪造硬件安全状态和 Key Attestation 中的签名哈希。

绕过方案：

1. 硬件密钥库检测绕过
   KeyStore.isHardwareBackedKeyStore()
   KeyInfo.isInsideSecureHardware()
   .........

2. Key Attestation 签名哈希替换
   (1) 启动时从 原始apk 提取原始签名
   (2) 找到 OCTET STRING 后的 32 字节签名哈希
   (3) 替换为原始签名的 SHA256 哈希
   ......

在这个Key Attestation里面其实还有更隐蔽更难以发现的检测签名的手段

四、  签名验证代理
==========================================

核心原理：
使用 Java 动态代理替换系统 PackageManager，拦截所有签名查询并返回原始签名。

绕过方案：

1. PackageManager 代理注入
   (1) 在 Zygote 阶段（可以更迟在application阶段）通过反射获取 ActivityThread.sPackageManager
   (2) 创建 Proxy.newProxyInstance() 包装原始 PM
   (3) 替换 ActivityThread 和 ApplicationPackageManager 中的 PM 引用

2. getPackageInfo 签名替换
    替换 PackageInfo.signatures 字段为原始签名
    替换 PackageInfo.signingInfo 中的证书链

3. 原始签名加载
    直接解析 原始.apk 的 APK Signing Block
    提取签名块中的 DER 编码证书
    转换为 android.content.pm.Signature 对象

4. checkSignatures 绕过
    Hook checkSignatures() 方法

5. 安装来源伪造（防止检测 APK 非谷歌商店安装）
   getInstallerPackageName(packageName)  >   伪装为 Google Play 安装
   ......

总结：四层防护体系，当然了，这个freeRASP并没有更严格的hook检测，如果使用更复杂的检测，哪就需要更多的手段来绕过，还有更多更复杂的检测方案和绕过方案和防止hook的方案这里就不细讲了

上述绕过方案适用于大多数加固，有些加固使用了上述方案没有的方案，哪就需要更多的手段来绕过

转发请著名来源，谢谢

---

# 回复

## 回复 by wx_插曲 (#2)

*2026-1-18 10:35*

6

## 回复 by mb_asiwnxyv (#3)

*2026-1-18 10:53*

感谢分享

## 回复 by 小尘0000 (#4)

*2026-1-18 11:43*

666

## 回复 by SomeMx (#5)

*2026-1-18 12:02*

过来瞧瞧

## 回复 by mb_4nrpVMxJ (#6)

*2026-1-18 12:41*

666

## 回复 by mb_qimctavn (#7)

*2026-1-18 13:22*

6

## 回复 by mb_irhdtnzm (#8)

*2026-1-18 13:25*

1

## 回复 by 随风而行aa (#9)

*2026-1-18 13:28*

看看

## 回复 by 恋一世的爱 (#10)

*2026-1-18 13:41*

看看

## 回复 by Imxz (#11)

*2026-1-18 13:50*

666

## 回复 by wx_李威威 (#12)

*2026-1-18 15:30*

66

## 回复 by apxar (#13)

*2026-1-18 15:41*

1

## 回复 by mb_jofnsvty (#14)

*2026-1-18 23:41*

6666

## 回复 by mb_jofnsvty (#15)

*2026-1-18 23:41*

6666

## 回复 by mb_rewimxhj (#16)

*2026-1-19 07:24*

看看

## 回复 by mb_roiscepd (#17)

*2026-1-19 09:12*

666

## 回复 by jdong (#18)

*2026-1-19 09:35*

666

## 回复 by Ascend_202904 (#19)

*2026-1-19 09:43*

6666666666

## 回复 by dob_C (#20)

*2026-1-19 11:21*

感谢分享

## 回复 by Viseris (#21)

*2026-1-19 12:06*

感谢分享

## 回复 by woaiziyou (#22)

*2026-1-19 13:10*

学习

## 回复 by 4Chan (#23)

*2026-1-19 13:41*

学习一下

## 回复 by 不具名的悲伤 (#24)

*2026-1-19 15:07*

6

## 回复 by 29o (#25)

*2026-1-19 16:09*

看看

## 回复 by mb_auylfslb (#26)

*2026-1-19 16:38*

1

## 回复 by Kill_Log (#27)

*2026-1-19 18:14*

666

## 回复 by 毛毛毛毛虫 (#28)

*2026-1-19 19:55*

看看

## 回复 by wx_huhu_859 (#29)

*2026-1-19 21:37*

11

## 回复 by buluo533 (#30)

*2026-1-20 08:03*

666

## 回复 by 黑屏 (#31)

*2026-1-20 08:08*

666

## 回复 by ldehua (#32)

*2026-1-20 09:20*

看看

## 回复 by 夜惜风雨 (#33)

*2026-1-20 10:25*

66666666666666666666666666666666666

## 回复 by AMy_德友 (#34)

*2026-1-20 10:35*

![image](https://bbs.kanxue.com/view/img/face/004.gif)根本不可能 sigprocmask的信号检测 阁下如何应对

## 回复 by 逆向漏洞大神 (#35)

*2026-1-20 11:06*

想看

## 回复 by Superoot (#36)

*2026-1-20 11:11*

感谢分享，学习一下

## 回复 by fangliangz (#37)

*2026-1-20 13:06*

666

## 回复 by mb_armzgbpd (#38)

*2026-1-20 14:09*

666

## 回复 by 拍拖 (#39)

*2026-1-20 16:14*

感谢分享

## 回复 by 9527vv7 (#40)

*2026-1-20 20:10*

6

## 回复 by 机车王子 (#41)

*2026-1-20 20:38*

感谢你的积极参与，期待更多精彩内容！

## 回复 by 上官兮唐 (#42)

*2026-1-20 21:36*

看看

## 回复 by timeromantic (#43)

*2026-1-20 21:56*

感谢分享，我想学习

## 回复 by xianhuimin (#44)

*2026-1-21 00:35*

看看

## 回复 by 无名侠 (#45)

*2026-1-21 01:19*

学习

## 回复 by k4y0z (#46)

*2026-1-21 10:33*

666

## 回复 by mb_euhyowpw (#47)

*2026-1-21 11:48*

66

## 回复 by seandong (#48)

*2026-1-21 13:07*

1

## 回复 by fjqisba (#49)

*2026-1-21 13:37*

666,bixu dei学习了

## 回复 by mb_ysegxpmv (#50)

*2026-1-21 16:28*

特来学习

## 回复 by csyjyy (#51)

*2026-1-22 15:55*

6

## 回复 by 大魔头 (#52)

*2026-1-22 18:13*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by Arsylk (#53)

*2026-1-23 08:09*

n

## 回复 by git_95208Kevynskdo (#54)

*2026-1-23 09:36*

lendo

## 回复 by wx_weggfkdk (#55)

*2026-1-23 14:42*

看看

## 回复 by bisoso (#56)

*2026-1-24 10:15*

感谢分享！

## 回复 by huangjw (#57)

*2026-1-24 10:20*

火钳刘明

## 回复 by git_91090armpro666-tech (#58)

*2026-1-24 11:45*

看起来很猛

## 回复 by 搬砖最积极 (#59)

*2026-1-24 12:13*

过来瞧瞧

## 回复 by 秃顶 (#60)

*2026-1-24 15:28*

66

## 回复 by FMNS (#61)

*2026-1-27 07:55*

看看

## 回复 by zjphoenix (#62)

*2026-1-27 08:14*

学习

## 回复 by mb_ehujhmht (#63)

*2026-1-27 10:02*

6

## 回复 by 我心向山 (#64)

*2026-1-27 15:34*

看看

## 回复 by comingundone (#65)

*2026-1-27 17:30*

1

## 回复 by 风间仁 (#66)

*2026-1-27 20:19*

1

## 回复 by 笑对VS人生 (#67)

*2026-1-27 21:12*

支持一个

## 回复 by dhruwen (#68)

*2026-1-28 21:07*

Great analysis, very helpful for learning bro.

## 回复 by mb_hbosztvl (#69)

*2026-1-29 00:19*

酷酷酷

## 回复 by Crack999 (#70)

*2026-1-29 09:29*

感谢分享

## 回复 by 呱呱呱000 (#71)

*2026-1-29 21:24*

牛啊

## 回复 by Zepp7289 (#72)

*2026-1-29 22:33*

感谢分享

## 回复 by chenwitch (#73)

*2026-1-30 13:38*

666

## 回复 by zkbutt (#74)

*2026-1-31 22:45*

学习

## 回复 by mb_vxguvtyr (#75)

*2026-2-1 03:30*

感谢分享

## 回复 by mb_tofujngy (#76)

*2026-2-1 08:22*

ωX-22APyHrvyYv18dω

## 回复 by wen55444 (#77)

*2026-2-2 21:00*

感谢分享

## 回复 by 飆汗吉米 (#78)

*2026-2-3 14:39*

先拜讀

## 回复 by wx_星儿 (#79)

*2026-2-3 22:49*

看看

## 回复 by caydemlendi (#80)

*2026-2-7 05:56*

6

## 回复 by 非洲男 (#81)

*2026-2-7 10:47*

感谢分享，学习下

## 回复 by git_22352GameBusuk (#82)

*2026-2-7 23:50*

666

## 回复 by mb_mykwpyev (#83)

*2026-2-8 02:45*

看看

## 回复 by mb_xgoaxxei (#84)

*2026-2-8 14:53*

66666666666

## 回复 by 黑色心跳 (#85)

*2026-2-8 17:23*

看看

## 回复 by mb_cbgtaveo (#86)

*2026-2-8 21:22*

666666666

## 回复 by hanjiefang (#87)

*2026-2-9 16:39*

![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by mb_rdqxdjmw (#88)

*2026-2-10 13:48*

学习一下

## 回复 by mb_wuevwbec (#89)

*2026-2-10 13:54*

mark

## 回复 by mb_ozmrnffd (#90)

*2026-2-10 15:24*

![image](https://bbs.kanxue.com/view/img/face/015.gif)

## 回复 by mb_xjdhrmck (#91)

*2026-2-10 15:54*

666

## 回复 by uni7corn (#92)

*2026-2-11 15:33*

感谢分享

## 回复 by pingsky (#93)

*2026-2-16 12:18*

太强了

## 回复 by jyotidwi (#94)

*2026-2-16 12:46*

66

## 回复 by 非凡人平常心 (#95)

*2026-2-16 13:03*

感谢分享

## 回复 by 熊猫吃鱼 (#96)

*2026-2-16 13:33*

66666

## 回复 by 张恒_884729 (#97)

*2026-2-17 13:23*

学习一下

## 回复 by mb_mpffrkcr (#98)

*2026-2-22 11:44*

666

## 回复 by 毕索 (#99)

*2026-2-22 16:08*

6

## 回复 by 我是小奥 (#100)

*2026-2-23 20:46*

学习一下

## 回复 by mb_duoplyas (#101)

*2026-2-23 21:34*

学习学习

## 回复 by git_30232mirra87654321 (#102)

*2026-2-24 21:45*

1

## 回复 by git_69939seeknoobwisdom (#103)

*2026-2-25 03:01*

666

## 回复 by mb_dtyaunuj (#104)

*2026-2-25 14:54*

KANKN

## 回复 by xiaoc996 (#105)

*2026-2-25 15:11*

6666

## 回复 by tmi (#106)

*2026-2-25 15:57*

![image](https://bbs.kanxue.com/view/img/face/035.gif)

## 回复 by git_43131MobileResearcher (#107)

*2026-3-2 08:00*

Thanks!

## 回复 by git_43131MobileResearcher (#108)

*2026-3-2 08:00*

Thanks!

## 回复 by qig (#109)

*2026-3-2 08:12*

感谢分享

## 回复 by linix (#110)

*2026-3-2 08:38*

666

## 回复 by mb_gkazhfpu (#111)

*2026-3-2 10:51*

1

## 回复 by 嘎嘎真的很棒 (#112)

*2026-3-2 11:01*

1

## 回复 by mb_zdoxkucm (#113)

*2026-3-5 02:02*

看看隐藏

## 回复 by irrisolto (#114)

*2026-3-8 00:54*

fff

## 回复 by mb_ghcouuzx (#115)

*2026-3-8 17:40*

看看

## 回复 by mb_deisgjrb (#116)

*2026-3-9 12:19*

11

## 回复 by git_44857niuniu524 (#117)

*2026-3-11 15:41*

666

## 回复 by mb_pmqkxpag (#118)

*2026-3-19 17:26*

look

## 回复 by wx_故事与酒 (#119)

*2026-3-23 01:19*

看看

## 回复 by Zkeleven (#120)

*2026-3-23 10:05*

666666

## 回复 by CuteHacker (#121)

*2026-3-23 10:52*

1

## 回复 by iBa0 (#122)

*2026-3-23 14:13*

111

## 回复 by mb_rndpmawh (#123)

*2026-3-23 14:26*

看看

## 回复 by 中文fjja (#124)

*2026-3-23 14:31*

感谢分享

## 回复 by creek_ (#125)

*2026-3-23 14:56*

6

## 回复 by qqqiu (#126)

*2026-3-23 18:47*

1

## 回复 by xeiyu (#127)

*2026-3-24 04:56*

666

## 回复 by wx_666_974 (#128)

*2026-3-24 11:27*

感谢分享

## 回复 by huangbof (#129)

*2026-3-26 16:07*

感谢分享

## 回复 by git_20703QinJun-1998 (#130)

*2026-4-17 14:14*

666

## 回复 by mb_hcadvceu (#131)

*2026-4-22 20:44*

看看

## 回复 by wfjun (#132)

*2026-5-2 23:26*

6666666666666

## 回复 by ClPrada (#133)

*2026-5-3 20:46*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by tubecityman (#134)

*2026-5-3 21:47*

不错

## 回复 by _109563 (#135)

*2026-5-6 15:03*

ok

## 回复 by darknight007 (#136)

*2026-5-7 11:41*

666

## 回复 by mb_girssugh (#137)

*2026-5-8 05:32*

666

## 回复 by wx_北极星_493 (#138)

*2026-5-20 22:40*

看看

## 回复 by mb_bfpcpmjo (#139)

*2026-5-21 09:36*

6

## 回复 by TeamAR (#140)

*2026-5-21 11:17*

666

## 回复 by mb_tewbhakr (#141)

*2026-5-22 08:21*

看看

## 回复 by GuMian (#142)

*2026-5-27 09:31*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by mJqalJqN (#143)

*2026-5-27 11:40*

1

## 回复 by mb_bcxccfzw (#144)

*2026-5-28 14:16*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by gfxvggbwic (#145)

*2026-6-3 17:23*

666

## 回复 by 努力8点 (#146)

*2026-6-4 11:36*

学习

## 回复 by mb_qeymwqsa (#147)

*2026-7-2 19:54*

666

## 回复 by mb_gipyuybr (#148)

*2026-7-24 00:13*

学习学习
