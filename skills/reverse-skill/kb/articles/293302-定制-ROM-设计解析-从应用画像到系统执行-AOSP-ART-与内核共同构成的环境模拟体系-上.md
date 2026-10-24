---
title: '[分享]定制 ROM 设计解析 从应用画像到系统执行：AOSP、ART 与内核共同构成的环境模拟体系。【上】'
url: https://bbs.kanxue.com/thread-293302.htm
tid: 293302
author: 乐子
date: '2026-10-23'
tags: [Android安全, 分享]
crawled_at: '2026-10-24T08:16:37+00:00'
replies: 16
---

大家好，新手逆向，改机小白说说最近研究的定制 ROM 设计，也是借鉴了很多大佬的项目和源码！！！

此 ROM 以应用和分身为配置单位，将设备属性、文件视图、资源统计、定位及电话信息组织为独立环境。
Agent 提供操作入口，设备中间件 组织参数，底层执行点分布于 Android Framework、运行时、系统运行
库和 Linux 内核。
自写“ROM 示例应用”实机画面。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_R4SJFT5NVTA44VK.webp)

## 本文的重点

结合自写应用的配置前后对照，解释功能如何进入系统，以及身份、路径、缓存、ABI 和编译优化为何成为
底层实现的难点。所有应用截图均为自写示例，不展示业务应用、账号、设备序列号或服务端地址。

## **1.让相同代码读到不同环境**

![image](https://bbs.kanxue.com/upload/attach/202610/990589_TW8H3ZGVTC49D67.webp)

这个对照体现了环境模拟的基本思路：配置改变系统的返回路径，应用保留原有调用方式。8 GiB 是接口呈
现值，不会增加真实物理内存；文件替换的作用范围也由实际打开路径决定。

## **2.五层协作，分工明确**

不同层处理不同类型的信息，共同遵循应用身份和配置空间的选择结果

01 Agent：入口与任务编排
选择应用和分身，设置参数，启动、脚本、代理、远程任务等。

02 设备中间件：参数生成与服务
将设备画像转换为属性快照、结构化参数及各类底层配置文件。

03 AOSP / Framework：系统语义
在预埋调用点处理参数、系统对象与回调，承接定位、电话和应用生命周期。

04 ART / 系统运行库：进程内执行
方法入口替换、原方法回调、属性读取与 Native 接口适配。

05 Linux 内核：路径与查询基础
按配置身份参与文件打开、元数据、文件系统统计、网络信息和 proc 输出

## **3.一份环境，需要多条读取链共同表达**

Java 接口、Native 包装层和直接系统调用的覆盖范围各不相同。定位“在哪一层改写”，才能决定需要修
改哪些入口、什么时候加载参数，以及如何核对最终结果。

## **4.预埋钩子把功能接进系统**

在系统既定调用位置保留扩展入口，再由功能分发器执行参数代理和结果替换

**![image](https://bbs.kanxue.com/upload/attach/202610/990589_AQ963K3WD3FQM7C.webp)**

**5.钩子的价值：进入对象真正产生的位置**

电话订阅、定位回调、应用启动和内存对象具有不同生命周期。将钩子放进 AOSP 调用链，可以在对象创建、
参数分发或结果返回时接入，使功能实现与对应系统服务保持明确关系。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_H337BPQAZ29QX6Y.webp)

预埋钩子适合稳定的系统接入点；ART 方法替换服务于运行时扩展。二者分别处理调用位置与方法入口，需要协
同初始化。

按身份选择一套环境
内核以真实运行 UID 为起点，经过映射找到对应参数空间。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_MQNEHWK2Z4U2HAP.webp)

映射把“哪个进程正在运行”与“这次使用哪套参数”联系起来。它选择环境数据，本身不会把进程的
Linux 凭据改成配置身份。分身启动链还会组织包管理身份、数据目录与进程启动，这些是相互配合的独立
动作

## **底层难点：不能只处理“启动成功”**

配置关联需跨越启动、退出、隔离子进程和分身切换。UID 复用、卸载和目录删除都可能改变状态，因此身份映射、参数缓存和磁盘文件需要分别维护。控制接口还应限定调用主体与目标范围，保证配置能力只作用
于预期应用。

## **6.文件内容可以在打开时替换**

**![image](https://bbs.kanxue.com/upload/attach/202610/990589_5ZQQY88A7VUWED2.webp)**

**原路径 → 覆盖候选 → 实际文件对象**

底层将原始绝对路径拼接到当前配置空间的覆盖根目录。候选文件存在时，新打开的描述符指向覆盖文件；
没有覆盖时继续原路径。示例中内容由 BASELINE_CONTENT 变为 DEMO_OVERLAY_CONTENT。

## **7.stat 与 statfs 补齐文件画像**

内容、文件属性和文件系统容量形成关联，需要在对应查询入口分别表达。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_X3TTP9FJUGVFAXJ.webp)

![image](https://bbs.kanxue.com/upload/attach/202610/990589_2QES9GKJQWJBQPQ.webp)

难点一：匹配范围

stat 使用的路径字符串、fstat 还原出的 FD 路径，以及 /data/data 与 /data/user/0 等别名可能不同。
statfs 还包含按原始总块数回退的匹配逻辑，作用范围可能覆盖同一文件系统的其他路径。

难点二：结构与长度边

内核需要正确填写 32 位和 64 位 ABI 的结构；大容量字段尤其要避免截断。已测 statfs64 可保留超过 2³²
的块数，但 FD 路径缓冲长度会影响匹配。缓存命中、路径长度和错误返回都应进入兼容性检查。

## **8.同一个 RAM 参数，多个接入点**

Java 对象、libc 包装和内核 proc 输出分别参与内存信息呈现。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_D5KSWE3Z88X5AC8.webp)

三个 8 GiB 来自不同执行层

ActivityManager 的 MemoryInfo 由 Framework 钩子改写；libc sysinfo 在包装层使用内存参数；
/proc/meminfo 由内核按页换算后输出。示例保留原始 sysinfo 系统调用作为对照，因此同时显示真实总
量 3.57 GiB。

## **9.网络画像与数据路径分别控制**

网卡枚举、本地地址查询、DNS 参数和代理转发承担不同职责。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_MCNFBMR4F3C87C4.webp)

此 ROM 在部分网络查询路径中按配置返回地址信息。网卡枚举与 socket 查询需要分别适配，尤其是 IPv4、
IPv6、前缀长度以及地址结构大小。相同网络画像必须在各入口中转换为正确结构。

## **10.proc 输出与运行时状态协作**

**![image](https://bbs.kanxue.com/upload/attach/202610/990589_UQUCMP23PSMD78K.webp)**

ART 方法替换需要跳转包装等可执行代码区域。映射本身、映射权限和诊断接口展示属于不同环节。

## **11.方法入口替换与原方法回调**

ART 承接动态方法替换，使模块可以在原有调用路径上加入自己的逻辑。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_ZA56XJ8X2JEFDT3.webp)

## **12.一套应用，多套保存环境**

**![image](https://bbs.kanxue.com/upload/attach/202610/990589_N7A8NGFEP47QTMU.webp)**

## **13.坐标、Provider 与回调共同构成位置**

![image](https://bbs.kanxue.com/upload/attach/202610/990589_Z9YDNMJ9X7MEX8C.webp)

系统钩子组织位置对象，并对 network、passive、gps 等路径分别处理。

## **14.围绕应用可见的电话对象模拟**

运营商、订阅、卡状态、信号和基站信息构成互相关联的电话环境。

![image](https://bbs.kanxue.com/upload/attach/202610/990589_Z3GND5YM7AM7ZYY.webp)

实现思路：让字段进入对应对象与事件。通过电话与订阅相关钩子处理对象和返回值，并结合位置及运营商信息组织部分小区参数。对象型
接口与简单字符串接口需要分别适配，监听回调还涉及系统注册过程和不同事件掩码。

---

# 回复

## 回复 by Ascend_202904 (#2)

666666666

## 回复 by CheRevir (#3)

666

## 回复 by method (#4)

1

## 回复 by mb_ldbucrik (#5)

向大佬学习

## 回复 by mb_xjdhrmck (#6)

6666

## 回复 by mb_jnmxfjku (#7)

666

## 回复 by xianhuimin (#8)

看看

## 回复 by 呼吸24K纯氧 (#9)

看看隐藏

## 回复 by 小黄鸭爱学习 (#10)

1111

## 回复 by 小黄鸭爱学习 (#11)

这点字段还不够，大厂设备注册指纹几百个。还有传感器相关的HAL层定制

## 回复 by 乐子 (#12)

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>  这点字段还不够，大厂设备注册指纹几百个。还有传感器相关的HAL层定制
>

这部分会在下补上，我自己采集训练了这部分，这篇内容起个开头![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by 我不是卷王 (#13)

666

## 回复 by 温泉划水鱼 (#14)

看看

## 回复 by 熊猫吃鱼 (#15)

666

## 回复 by Bonquer (#16)

666

## 回复 by 念折纸 (#17)

6
