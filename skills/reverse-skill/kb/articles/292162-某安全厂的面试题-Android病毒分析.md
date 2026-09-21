---
title: '[原创] 某安全厂的面试题 Android病毒分析'
url: https://bbs.kanxue.com/thread-292162.htm
tid: 292162
author: BitWarden
date: '2026-07-25'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-09-21T09:04:01+00:00'
replies: 10
---

# 前言

去年这个时候笔者面试一家安全厂的面试题目（两个字的hh），过了一年了翻出来了拿出来分享一下。技术面是通过了，最后可能是没有缘分吧。比较可惜。希望文章能给正在找工作的一点帮助。(分析报告纯古法0 ai辅助)

# 分析报告

分析人员： **

分析日期： 2025年6月23日

样本来源： **

# 1. 分析环境

分析工具：GDA,IDA PRO, Jeb Pro

分析设备：谷歌Pixel1

系统版本：Android 8.1

# 2. 威胁概述

## 2.1. 样本基本信息

样本类型：Android恶意应用程序

主要组成：包含两个DEX文件的复合型恶意软件

威胁等级：高危

# 3. 核心恶意功能

## 3.1. 屏幕解锁攻击模块

利用无障碍服务监听和记录用户输入的密码、图案

实施PIN码暴力破解攻击

密码信息存储在特定路径（/Config/sys/apps/loge/）

## 3.2. 虚拟货币钓鱼攻击

针对Trust Wallet等数字钱包应用

创建虚假交易界面进行钓鱼

监控BTC、ETH、USDT等主流虚拟货币余额

专门攻击Binance应用，通过恶意覆盖界面窃取用户资产

## 3.3. 远程访问木马（RAT）功能

连接远程控制服务器（103.118.247.217:7781）

具备屏幕截图、设备信息收集能力

支持远程控制和应用卸载操作

## 3.4. 权限绕过与持久化

针对小米、华为、OPPO等主流厂商进行权限绕过

自动获取无障碍权限和设备管理器权限

实施电池优化绕过，确保后台运行

## 3.5. 反检测与对抗分析

具备反虚拟机/模拟器检测能力

通过窗口拦截阻止用户卸载应用

保护关键服务和权限设置不被用户修改

## 3.6. 通信机制

使用TCP协议进行原始socket通信

采用Base64编码传输敏感信息

建立持久化的C&C通信连接

## 3.7. 总结

这是一个功能完整的高级持续性威胁（APT）样本，集成了密码窃取、虚拟货币盗取、远程控制等多种攻击手段，对用户财产安全和隐私构成严重威胁。

# 4. 动态行为分析

## 4.1. 静态配置分析

使用GDA工具查看AndroidManifest.xml文件，发现Apk疑似获取如下权限。

|  |  |
|-|-|
| android.permission.MODIFY_AUDIO_SETTINGS | 修改音频设置 |
| android.permission.SEND_SMS | 发送短信 |
| android.permission.SET_WALLPAPER | 设置壁纸 |
| android.permission.READ_SMS | 读取短信内容 |
| android.permission.READ_CALL_LOG | 读取通话记录 |
| android.permission.READ_CONTACTS | 读取联系人信息 |
| android.permission.GET_ACCOUNTS | 获取系统账户信息 |
| android.permission.CAMERA | 访问摄像头 |
| android.permission.RECORD_AUDIO | 录制音频 |
| android.permission.ACCESS_COARSE_LOCATION | 获取大概位置信息 |
| android.permission.ACCESS_FINE_LOCATION | 获取精确GPS位置 |
| android.permission.CALL_PHONE | 直接拨打电话 |
| android.permission.DISABLE_KEYGUARD | 禁用锁屏 |
| android.permission.FOREGROUND_SERVICE | 运行前台服务 |
| android.permission.READ_EXTERNAL_STORAGE | 读取外部存储 |
| android.permission.RECEIVE_BOOT_COMPLETED | 开机自启动 |
| android.permission.WRITE_EXTERNAL_STORAGE | 写入外部存储 |
| oppo.permission.OPPO_COMPONENT_SAFE OPPO | 厂商安全组件权限 |
| oplus.permission.OPLUS_COMPONENT_SAFE OPLUS | 厂商安全组件权限 |
| com.huawei.permission.external_app_settings.USE_COMPONENT | 华为外部应用设置组件权限 |
| android.permission.INTERNET | 网络访问权限 |

## 4.2. 执行分析

使用正常软件进行执行分析。

一共启动了两个活动窗口。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_XZQBNFPXYMAQ7QX.webp)

引导用户启动无障碍，疑似模拟触摸影响用户输入。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_BPDXXN496HNE22E.webp)
启动后会阻止用户关闭无障碍。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_TDB89JDZ4MBCU8J.webp)

# 5. 样本壳分析

## 5.1. Java层分析

### 5.1.1. 加密字符串算法分析

样本使用了字符串加密，来进行其特征，我们需要进行解密。

主要解密函数如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_Z9A82N965KHP9SF.webp)

可以看到是一个base64加密，并且进行字符串分割，分割元素是”ǘūď”。函数解密流程图。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_JTXFHY672T7X4WF.webp)

使用frida进行hook，获取所有字符串解密后结果。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_DPNV9TG8A32JSDB.webp)

部分hook代码：

```python
function hook_m_io(){
Java.perform(()=>{
var cls_j_m = Java.use("j.m");
if(cls_j_m == null){
return;
}
cls_j_m.io.overload("java.lang.String").implementation= function(str:string){
var ret_vaule = this.io(str)
console.log(str,"decode: ",ret_vaule);
return ret_vaule;
}
});
}
\```

### 5.1.2. 主活动分析

使用GDA查看AndroidManifest.xml，查看主活动。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_85NCK9WYGSW83HW.webp)

在软件中并没有发现n0fon.izxjm.v84jv.MainActivity的主活动类。通过分析m类可以发现：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_8MUK3ABJVS77GS4.webp)

样本重写了attachBaseContext方法，在执行MainActivity之前运行了部分逻辑

### 5.1.3. attachBaseContext函数分析

Dex自解压行为

样本首先打开文件

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_YYHZWERDY2GSA5P.webp)

文件名为：

“ZmLEj8eYxavEj3Rrd2pkLmRleMeYxavEj8eWx5bEjw==”:tkwjd.dex

“ZmLEj8eYxavEj3Rrd2pkLmRleMeYxavEj8eWx5bEjw==”:tkwjdd.dex

路径为：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EFBTPSA8BN9HVBP.webp)

/data/data/n0fon.izxjm.v84jv/files/

并且判断文件是否存在

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_SYB83BDP8Z7QZ65.webp)

样本最后执行解压自己的APK

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_XZUBKGMHQFNCUAS.webp)
并且匹配.tkwjd关键字写入到缓冲区中，并且写入到文件缓冲器。我在apk文件中找到f.tkwjd文件

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_RSMV2CY5W6MYPP8.webp)

解压完成后就会对文件进行解密

解密算法如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EY9ZUKU8W7KNVZT.webp)

解密完后就会执行label_30:分支中可以看到样本通过DexClassLoader加载了一个dex，并且加载了里面的类并且调用了方法。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_FBBN6Y4JZRW5WYN.webp)

最后他会加载dex，执行attachBaseContextEx和setLoadFlag方法。

c.g.attachBaseContextEx分析

根据不同的指令集加载不同的so。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_2FVA7K4GUJTR8ZS.webp)

修改文件名

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_RK3R8YX588QA85W.webp)

解密so

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_9QPUTHFFJ5X74RG.webp)

从文件中解压并且解密

解密函数

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_C5Z7WFFHHGGETRX.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_V88YXSCJX7J9U2G.webp)

可以发现so被ase进行加密了。

使用python模拟解密算法对本地加密过的so进行解密实际上他是一个zip文件。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_GXKWT9TUBRWDU75.webp)

解压出来就是样本本身的so了。

### 5.1.4. J.onCreate函数分析

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_K7KG74AAPYF962Q.webp)

主要是使用反射调用了m.a.onCreateEx，这里写了一个去字符串混淆脚本还原了真实代码。

Context劫持

将Context的外部引用指向恶意Application

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_R8KT4CU6HFP8VNS.webp)

篡改ActivityThread

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_TDN7UMRYJREZ7UX.webp)

获取ActivityThread实例（Android应用的主线程管理器），将mInitialApplication字段替换为恶意Application。

Application列表操作

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_FG9G5MH8SRPB7GK.webp)

修改系统维护的所有Application列表,这确保系统认为恶意Application是合法的。

LoadedApk包含应用的包信息，将其中的Application引用替换为恶意版本。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_BS5MQX2JQFQAVTZ.webp)

ApplicationInfo伪装

修改ApplicationInfo中的className，使系统认为恶意Application是应用的正式Application类。

生命周期接管

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_YXSUMSWD5TUKWEH.webp)

调用恶意Application的onCreate

### 5.1.5. g.1内部类分析

这里主要做了一个重打包检测。

拿到ApplicationInfo

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EMX45HR3KGEMETB.webp)

通过apk拿到mf文件

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_JAUUC5YWBMSYHNV.webp)

获取MANIFEST.MF文件的时间戳

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_6PX9DMPZ9NU6MU3.webp)

与原本的硬编码时间戳进行比较，如果不一样就是被篡改过。

### 5.1.6. Java层启动流程

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_H4MXSMMRAH8ZSFW.webp)

整个apk在java中启动流程就如上图。

## 5.2. Jni层分析

### 5.2.1. native_attach分析

从java层中可以知道java层调用了m.attach函数。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_2ZE62JHRBTCHMQE.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_R9YVA5CCVGGK334.webp)

从ida中可以看到上面m.attach函数。

### 5.2.2. sub_15F6C函数分析

创建一个dex准备进行自解密。

Dex加密数据回填

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EXUDZQSQDJHJ3UH.webp)

### 5.2.3. sub_17194分析

定位apk的位置

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EEA2Z4MD9FHEYPA.webp)

### 5.2.4. sub_17264分析

进行解密

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_KE4KK2E9K8PQ33G.webp)

通过反射Inmemorydexclassloader加载dex

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_KQDXT7GJM7KE2ST.webp)

遍历dexfile，并且存储里面的元素。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_NRPP5YYR94AZKSQ.webp)

最后做了替换，在sub_19064函数中。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_4C3PZWFV7E9C38K.webp)

最后返回

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_WXASCS6MVSJJTYN.webp)

## 5.3. 脱壳思路

由于主要使用的是Inmemorydexclassloader加载的dex，所以我们可以在BaseDexClassLoader获取到classload和文件缓冲区。如下图类之间关系。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_263ZBK2HMGSSMZ5.webp)

这里采用的是定制Aosp进行修改。主要使用Aosp8.1系统，在BaseDexClassLoader构造进行插桩Dump所有dex文件。部分代码：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_DXA3PQ73C5KPV7V.webp)

一共Dump如下文件（前缀dump_是脱壳机添加，后面为源文件名）。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_9XR9B5HZFM8CYDE.webp)

# 6. 静态行为分析

## 6.1. 主文件分析

由于有多个Dex文件这里使用Python脚本对文件进行甄别。通过Hash比较，文件大小以及文件格式。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_23TUXU5KQVPRKDY.webp)

发现有两个dex：

b409bdef6a255e52d6aa27ad68c938e7c886d1ea35b4cda27d9f8c42c418fe4d

49049c73c3aa8722d569a90e4be5742b15c68d526a99b984826a37eee1265a12。通过jeb pro观察。

## 6.2. MainActivity类行为分析

反虚拟机/模拟器检测

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_VC8S9Q6MX9CJPZR.webp)

恶意WebView配置，恶意网站http://dou.gamesrwf.com

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_CRBAZPREPF8YQVT.webp)

恶意隐藏进程 Activity被销毁时启动后台Activity保持存在

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_NTSZ2WR5TR6B5MV.webp)

## 6.3. ClickUnlock屏幕密码解锁破解模块分析

利用无障碍监听输入密码

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_NUUM29PWYXJ8JQG.webp)
记录图案

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_95JKPAPNJWYGSCX.webp)

检测消息完成后保存图案

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_SRKAQNCCYU5S2CF.webp)

保存密码到这个路径下"/Config/sys/apps/loge/pwdss.text"

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_54QA4QCAGZU79HR.webp)

利用无障碍模拟破解用户密码

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_UBS92ZXECCPGVPY.webp)

PIN密码暴力破解

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_QJ8HF4BCZPW3KPW.webp)

屏幕唤醒和解锁启动

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_DNPW6ZT9BABW7WD.webp)

## 6.4. 虚拟币钓鱼模块Trust

虚假交易界面，部分代码

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_97X595WGBWPSSQ7.webp)

钱包名窃取

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_H29R9VTZC85UQCB.webp)

监控BTC余额

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_N4F36ZTCP78N2RG.webp)

监控etc余额

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EP3D2MZCYSD42T8.webp)

监控USDT余额

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_7HEKFN7JU6ACQGR.webp)

## 6.5. Binance应用程序转账攻击模块

检测Binance应用攻击触发

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_QJC3W8AAC3U8DPF.webp)

恶意覆盖界面

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_7FWPNR2MHNGFSJA.webp)

最后把数据存放到变量中

## 6.6. 远程访问木马模块

建立与远程控制服务器的连接

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_QHWTTF24BC4YGW5.webp)

应用卸载操作

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_3Q872DD6EVWS7EG.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_XPHH67MPEG5KEJ5.webp)

设备信息收集

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_9UWDMPR27EP2X22.webp)

屏幕截图控制

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_PQJD8TFG3UMJ8K9.webp)

## 6.7. 远程控制溯源分析

在n0fon.izxjm.v84jv.servziz.initializeService 类中查找到了攻击方的IP地址

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_8S8FYGRYJ7GWXWK.webp)

使用base64进行解密，可以获得以下信息。

服务器IP地址： 103.118.247.217
服务器端口： 7781

连接的一些信息

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_ZVC3WN973GE6EC2.webp)

## 6.8. 后台工作服务

主要是位置前台的服务连接

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_CM3A6UHN7SGSQDW.webp)

## 6.9. 无障碍服务模块以及远控具体实现

服务器地址以及端口

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_PNJBR7R5BM64MZS.webp)

通过解码IP地址如下:

103.118.247.217:7781

截图底层实现

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_GPRMKC7W4Q86HM9.webp)

屏幕内容扫描底层实现

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_M6YZ7SMYZJR5KH2.webp)

PIN码监控部分代码

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_23U6J8T5WU3HSCH.webp)

密码保存

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_MWVQFH7J72WZWVS.webp)

密码存储位置 ：/sdcard/Config/sys/apps/loge/

存储结构：

pwdss.txt # 成功验证的解锁密码

pwdsz.txt # 当前输入的密码

pwd.txt # 备用密码文件

pwdtype.txt # 密码类型标识

log-YYYY-MM-DD.txt # 按日期的活动日志

应用活动监控

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_S84Y4NWF5N6T3GV.webp)

Trust Wallet攻击实现

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_KFPP2TS5RUF3W4T.webp)

## 6.10. 权限绕过

电池管理系统

小米绕过

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_SAPEFYSGKHR23VK.webp)

华为绕过：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_ZZZKTZE9KMMF8HD.webp)

OPPO绕过：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_RTWEPDDDN8RKVQU.webp)

无障碍权限自动获取:

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_SQ3VME2DFRT3334.webp)

系统静音功能

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_UG22NBWRHDAED7Z.webp)

## 6.11. 窗口拦截 NewUnInstall

阻止用户卸载

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_CJ4TARE57FSXB3A.webp)

通过关键词检测

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_VB433RFF443F2MY.webp)

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_V7PKA72TEJX8G88.webp)

解码后主要是：自启动管理、权限管理、应用权限、后台活动、电池优化、无障碍服务、设备管理器、系统权限。阻止用户进行设置。

特定权限设置拦截

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_YH7DWRAU5BHX39Q.webp)

无障碍服务保护

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_7SGBX8YF277QV5T.webp)

## 6.12. 网络协议分析

主要使用的是原始socket进行通信的，使用的是TCP协议。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_EQUNFWRW84U6F8V.webp)

数据包格式

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_K4Z6T42MRRAPZP6.webp)

录制发送

 ![图片描述](https://bbs.kanxue.com/upload/attach/202607/992284_E3Q69CUJ8KC4ASV.webp)

# 总结

希望对你有帮助。如果有啥疑问也可以直接在评论区提出来。文章不限制，觉得还可以的话请帮我点个赞吧。

---

# 回复

## 回复 by dayDReam_10 (#2)

*2026-8-7 09:38*

大佬有样本嘛，想学习一下

## 回复 by BitWarden (#3)

*2026-8-7 17:56*

>
> [dayDReam_10](https://bbs.kanxue.com/user-1073886.htm)
>  大佬有样本嘛，想学习一下
>

有的

## 回复 by BitWarden (#4)

*2026-8-7 17:56*

回去我发到附件里面 不过现在来看 ai秒了也没啥太大意义了

## 回复 by dayDReam_10 (#5)

*2026-8-9 19:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  BitWarden](https://bbs.kanxue.com/user-992284.htm)
>  回去我发到附件里面 不过现在来看 ai秒了也没啥太大意义了
>

感谢大佬

## 回复 by BitWarden (#6)

*2026-8-10 12:08*

>
> [dayDReam_10](https://bbs.kanxue.com/user-1073886.htm)
>  感谢大佬
>
>

上传不了，百度云链接发你吧：通过网盘分享的文件：doubao.apk
链接: https://pan.baidu.com/s/1rJCh3MtU969JmV7fStEbsA 提取码: bz3t
--来自百度网盘超级会员v6的分享

## 回复 by dayDReam_10 (#7)

*2026-8-10 22:14*

感谢大佬
![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by mb_vfkgwxph (#8)

*2026-8-17 08:22*

能接单吗大佬

## 回复 by BitWarden (#9)

*2026-8-17 14:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_vfkgwxph](https://bbs.kanxue.com/user-1088990.htm)
>  能接单吗大佬
>

灰黑不接

## 回复 by mb_vfkgwxph (#10)

*2026-8-19 13:47*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  BitWarden](https://bbs.kanxue.com/user-992284.htm)
>  灰黑不接
>

是我手机有顽固性病毒需要证据可以提供吗一般杀毒软件查杀不出

## 回复 by aจุ๊บ (#11)

失效了  求补链接
