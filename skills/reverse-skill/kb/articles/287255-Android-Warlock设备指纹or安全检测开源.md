---
title: '[原创]# Android—Warlock设备指纹or安全检测开源'
url: https://bbs.kanxue.com/thread-287255.htm
tid: 287255
author: xiaoc996
date: '2025-06-15'
tags: [Android安全, 原创, 逆向分析, 程序开发, 系统相关, 工具脚本]
crawled_at: '2026-07-31T14:08:47+08:00'
replies: 12
---

## 一、项目背景

 本项目始于2024年年底创建的GitHub仓库，经过5个月的开发已初步实现核心功能。当前版本的服务端代码完成于2025年5月初，此后项目进入维护阶段。出于代码质量考虑，服务端部分暂未开源，待后续迭代优化后将考虑开放源代码。

 项目初衷源于实际业务中对抗黑灰产的需求。在日常工作中，频繁需要开发新的检测模块来应对各类安全威胁。然而，采用每次新建独立项目或集中堆砌代码的方式都存在明显弊端。为此，我决定开发一个统一的安全检测SDK，以系统化地解决这一问题。

 需要说明的是，当前版本仍存在诸多不足，主要提供了一些基础检测功能。在实际业务场景中，由于合规要求等限制因素，某些定制化检测方案往往难以直接落地。因此，理想的解决方案是针对特定类型的黑灰产工具，开发通用检测机制并结合用户行为分析(UBA)进行精准防御。这也是项目未来的重点发展方向。

## 二、Warlock介绍

 Warlock项目地址：https://github.com/imxiaoc996/DeviceWarLock （release版本在GitHub仓库中）

Warlock设备指纹分为java层和native层指纹，java层共计80+采集信息，native层共计20+采集信息，采集完毕后他们会形成一个json保存在log里，log会被保存到私有目录下的file文件夹当中，java的字段会以a开头，native会以n开头，具体的字段解释我放在了[resource](https://github.com/imxiaoc996/DeviceWarLock/tree/main/resource)。设备环境检测主要有Root、Unlock、云手机、沙箱、注入等检测手段，以下是能力汇总：

### 2.1 设备指纹采集能力

1. **基础硬件与系统信息采集**

- 设备品牌、型号、序列号
- Android系统版本、系统指纹、CPU架构
- 时区、数据目录、内存、存储空间等

1. **设备唯一标识采集**

- Android ID、Google Advertising ID（AAID）
- IMEI、UUID、蓝牙地址、MAC地址等
- DRM ID、Boot ID、ReaperAssignedDeviceId等

1. **WebView与系统环境指纹**

- WebView的UserAgent、分辨率、像素密度、GPU信息、字体列表
- WebView版本、系统语言

1. **系统服务与应用信息**

- 已安装应用列表、系统服务列表
- 系统字体哈希、屏幕亮度、分辨率、超时时间

---

### 2.2 设备环境检测能力

1. **虚拟环境与仿真检测**

- 检测模拟器（如传感器数量、摄像头数量、模拟器特征属性等）
- 检查云手机、沙箱环境

1. **安全风险检测**

- Root检测、Xposed检测、Hook检测、Unlock检测
- 签名校验、系统完整性检测

1. **系统环境异常检测**

- 检查开发者选项、USB调试、VPN连接等
- 检查自定义ROM（如LineageOS）特征

1. **电池与硬件状态检测**

- 电池状态、传感器、摄像头等硬件环境检测

 ![image](https://bbs.kanxue.com/upload/attach/202506/963851_7DHYJ9SM6UAXA7N.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202506/963851_NDV66F82NUUJ5PT.webp)

## 三、写在最后

 本文内容较为精简，主要介绍开源项目 **Warlock**。我们后续计划推进改机相关项目，但当前的重点仍是完善 Warlock 的核心功能。

 尽管 Warlock 在现有安全检测工具中可能功能尚不完善，但作为开源项目，它希望能为对安全检测技术感兴趣的同学提供一些参考和帮助。

 我们承诺至少会维护并迭代该项目一年。如果你有更好的检测方法，项目出现bug，或发现项目中尚未涵盖的技术方案，欢迎一起探讨，共同进步！

---

# 回复

## 回复 by xiaotuo (#2)

*2025-6-16 11:26*

666

## 回复 by dfJerry (#3)

*2025-6-16 11:30*

支持

## 回复 by dfJerry (#4)

*2025-6-16 11:31*

期待分享:改机相关项目

## 回复 by iBa0 (#5)

*2025-6-17 19:12*

感谢

## 回复 by mb_srdgpiky (#6)

*2025-6-17 19:20*

这可以识别重置吗

## 回复 by 珍惜Any (#7)

*2025-6-18 10:05*

点个赞。

## 回复 by SomeMx (#8)

*2025-6-18 11:46*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  点个赞。
>
>

佬 FunJni还更新吗

## 回复 by hacker521 (#9)

*2025-6-18 12:03*

可以识别是否是刚刷机？

## 回复 by Istaroth (#10)

*2025-6-18 15:30*

![image](https://bbs.kanxue.com/view/img/face/078.gif)好文

## 回复 by mb_hhnkcstt (#11)

*2025-6-18 17:06*

还继续更新吗

## 回复 by 珍惜Any (#12)

*2025-6-18 17:14*

>
> [SomeMx](https://bbs.kanxue.com/user-926256.htm)
>
>  佬 FunJni还更新吗
>
>

早不更新了... 我已经抛弃了xposed模块，现在用magisk模块方便点。

## 回复 by mb_lpuubxuh (#13)

*2025-11-29 01:12*

大佬怎么联系呢？有开发需求
