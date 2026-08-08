---
title: '[原创]尝试构建 LLM + 静态分析审计流水线，60s 自动化定位 Android Native 漏洞'
url: https://bbs.kanxue.com/thread-290561.htm
tid: 290561
author: mb_lwbtipdx
date: '2026-03-29'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析]
crawled_at: '2026-08-08T10:16:16+00:00'
replies: 43
---

**一、 背景**

最近一直在思考如何利用大语言模型的语义理解能力，配合静态分析工具（如反编译、CFG 提取）来加速 Android Native 层（JNI/NDK）的漏洞审计。

目前的痛点在于：JNI 跨语言调用链追踪非常繁琐，且 Native 层的内存操作逻辑在反汇编后阅读压力巨大。我尝试构建了一套自动化流水线，核心思路是：**“自动化提取 JNI 语义 + 跨层数据流摘要 + LLM 逻辑判定”**。

**二、 实测案例：Google CTF 2021 Tridroid**
拿 Google CTF 2021 的经典 Pwn 题 Tridroid 做了个黑盒测试（无符号表、直接跑 Release APK）。

**流水线分析耗时：约 1分钟。**

以下是框架自动生成的分析日志摘要（原始输出，未做人工修改）：

\````
[AI]: 分析发现了一个严重的 **栈缓冲区溢出漏洞**，位于 `modify_element` 函数中。

### 漏洞分析：
1. **触发逻辑**：当调用 `modify` 操作时，程序会执行 `modify_element`。
2. **风险代码段**：
   ```c
   char acStack_38 [32]; // 在栈上分配了一个大小为 32 字节的缓冲区
   // ...
   __src = (void *)_JNIEnv::GetByteArrayElements(param_1,param_2,(uchar *)0x0);
   iVar2 = _JNIEnv::GetArrayLength(param_1,(_jarray *)param_2);
   memcpy(acStack_38,__src,(long)iVar2); // 关键漏洞：没有限制长度，直接将用户可控的长度拷贝进 acStack_38
   strcpy(*(char **)PTR_stack_top_00102ff8, acStack_38); // 拷贝到堆空间，但若 acStack_38 已溢出，控制权可被夺取
   ```
3. **漏洞成因**：
   - `acStack_38` 是一个仅有 32 字节的局部栈变量。
   - `memcpy(acStack_38, __src, (long)iVar2)` 并没有检查传入字节数组的长度 `iVar2`。如果用户提供的字节数组长度超过 32 字节，就会覆盖函数的返回地址或栈帧上的其他数据。
   - 随后的 `strcpy` 操作进一步利用了溢出后的数据，这意味着攻击者可以精确地控制溢出内容，通过构造特定的字节数组，可以实现任意代码执行（RCE）。

### 结论：
该程序存在 **基于栈的缓冲区溢出** 漏洞。攻击者可以通过构造精心设计的 `modify` 操作数据包，利用 `memcpy` 溢出栈空间并覆盖函数返回地址，从而劫持程序控制流。

**下一步建议**：如果需要进一步验证，可以根据 `acStack_38` 的偏移量构造 payload，尝试溢出并触发程序崩溃或控制 PC 指针。是否需要继续探索如何触发该溢出？
\````

**![image](https://bbs.kanxue.com/upload/attach/202603/1010487_W6EHKFUTMBX7AFQ.webp)**

**![image](https://bbs.kanxue.com/upload/attach/202603/1010487_29MXU6ZKBN37MP3.webp)**

**三、 演示视频 (2K高清)**
为了验证分析过程的真实性（非 Hardcode），录制了一段从 APK 下载到产出报告的全流程 Demo。

- **视频链接 (蓝奏云)：** [https://wwbml.lanzoum.com/iPCX13luxxij](https://www.google.com/url?sa=E&q=https%3A%2F%2Fwwbml.lanzoum.com%2FiPCX13luxxij)
- **文件大小：** 11MB

**四、 交流与 Live 测试邀请**
目

**Live Challenge：**前该框架在处理 JNI 边界溢出和简单的 Native 逻辑漏洞上表现尚可，但在重度加固和复杂混淆下的表现还有待测试。
如果有老哥手里有包含 **Native 层逻辑漏洞** 的真实样本（非加固/脱壳后），欢迎发给我交流。我尝试用 AI 跑一下看能不能出报告。

- **我的联系方式 ：2452151196@qq.com**

欢迎各位逆向大佬指点，探讨自动化审计的新姿势。

---

# 回复

## 回复 by mb_4nrpVMxJ (#2)

*2026-3-29 17:03*

看看

## 回复 by iBa0 (#3)

*2026-3-29 18:53*

123

## 回复 by wx_插曲 (#4)

*2026-3-29 19:17*

66

## 回复 by wx_Dispa1r (#5)

*2026-3-29 23:34*

1

## 回复 by ret2c7 (#6)

*2026-3-30 09:34*

1

## 回复 by zouzhiqiang (#7)

*2026-3-30 09:48*

11

## 回复 by 不具名的悲伤 (#8)

*2026-3-30 09:58*

6

## 回复 by Thehepta (#9)

*2026-3-30 10:19*

1

## 回复 by 随风而行aa (#10)

*2026-3-30 11:19*

看看

## 回复 by XCicada (#11)

*2026-3-30 12:01*

看看

## 回复 by mb_asiwnxyv (#12)

*2026-3-30 12:25*

看看

## 回复 by mb_roiscepd (#13)

*2026-3-30 14:53*

666

## 回复 by 4Chan (#14)

*2026-3-30 19:18*

666

## 回复 by cccaaa123 (#15)

*2026-3-31 00:48*

真强

## 回复 by k4y0z (#16)

*2026-3-31 09:52*

666

## 回复 by mb_pesxllvn (#17)

*2026-3-31 09:55*

666

## 回复 by SinkDev (#18)

*2026-3-31 12:27*

看看

## 回复 by 呆萌的小白 (#19)

*2026-4-1 08:36*

收藏一下

## 回复 by mb_ghcouuzx (#20)

*2026-4-1 16:22*

kankan

## 回复 by Kaisar大帝 (#21)

*2026-4-1 17:31*

开源吗?

## 回复 by Newbie_Ninja (#22)

*2026-4-2 13:41*

666

## 回复 by wx_Lyq (#23)

*2026-4-2 15:41*

666

## 回复 by 木木W (#24)

*2026-4-2 15:55*

666

## 回复 by 黑屏 (#25)

*2026-4-2 15:58*

666

## 回复 by mb_fyyqwxca (#26)

*2026-4-3 03:49*

2

## 回复 by darknight007 (#27)

*2026-4-4 14:21*

666

## 回复 by 小迷糊ddd (#28)

*2026-4-5 21:17*

感谢楼主，参考一下。

## 回复 by mb_ysikfhxt (#29)

*2026-4-8 14:52*

666

## 回复 by z_890403 (#30)

*2026-4-8 22:34*

66666

## 回复 by wx_Huber Barrientos (#31)

*2026-4-8 23:24*

为你点赞！

## 回复 by Loopher (#32)

*2026-4-9 11:03*

kankan

## 回复 by mb_uktygsmq (#33)

*2026-4-9 17:03*

666

## 回复 by uni7corn (#34)

*2026-4-27 17:50*

666

## 回复 by ycdear (#35)

*2026-6-1 08:10*

11

## 回复 by huangjw (#36)

*2026-6-1 08:56*

![image](https://bbs.kanxue.com/view/img/face/021.gif)

## 回复 by hyz111 (#37)

*2026-6-1 10:17*

看看

## 回复 by jygzyc (#38)

*2026-6-1 10:54*

666

## 回复 by 温泉划水鱼 (#39)

*2026-6-1 12:33*

看看

## 回复 by mb_xwntdpxy (#40)

*2026-6-1 21:01*

666

## 回复 by simpleness (#41)

*2026-7-15 20:43*

6

## 回复 by Nijika (#42)

*2026-7-16 11:46*

666

## 回复 by wx_辰 (#43)

*2026-7-17 10:27*

先赞后看

## 回复 by liowmark (#44)

*2026-7-17 14:12*

学习学习
