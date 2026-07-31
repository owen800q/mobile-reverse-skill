---
title: 使用JADX-MCP高效反混淆
url: https://bbs.kanxue.com/thread-289776.htm
tid: 289776
author: _0xA1pha
date: '2026-01-16'
tags: [Android安全, 混淆加固]
crawled_at: '2026-07-31T15:15:41+08:00'
replies: 238
---

## 概述

通过优化提示词，规范化agent的行为，从而得到一套高效率的java层反名称混淆方法

## 痛点

在安卓逆向过程中，我们常遇到这样的混淆

![去混淆前](https://bbs.kanxue.com/upload/attach/202602/1059242_3Q8BRB8Q4N44CR3.png)

总结起来可以分几类：

1、unicode小语种类，比如阿拉伯语，类名竟然能竖起来。（可以用插件转变为类似第三种）

2、O0o、1lI、ILZ类

3、短字符类，比如f0、a、ab

对于只有名称混淆的，我们可以使用jadx-mcp配合ai根据语义快速且高效地批量进行恢复，从而把逆向工程周期极大地缩短。

## 思路

实测JEB-MCP占资源太大，而且过于卡，反编译一个类可能需要几分钟，对于我这种计算资源比较少的小牛马显然JEB还是过于笨重了。不过之前的提示词还是有效的，可以考虑把提示词迁移至jadx-mcp。于是找到了https://github.com/zinja-coder/jadx-ai-mcp这个项目。

### jadx-mcp部署和连接

jadx-mcp实际上是两部分，分别是`JADX-AI-MCP`和`JADX-MCP-SERVER`，前者是一个jar，是jadx插件，后者是标准的mcp服务器。

我的IDE是google的antigravity，官方没有提供安装方法，不过这个IDE一看就是vscode改过来的，所以可以参考roocode、cline这种进行配置。此处有一个坑点：我为antigravity配置了socks5代理，导致`JADX-MCP-SERVER`网络连通性测试出现异常。解决方案是下面配置中的env字段。注意timeout设大一点。

修改`~\.gemini\antigravity\mcp_config.json`，添加

```
{
    "mcpServers": {
        "jadx-mcp-server": {
            "command": "uv",
            "args": [
                "--directory",
                "d:/xxxxx/jadxmcp",
                "run",
                "jadx_mcp_server.py"
            ],
            "env": {
                "HTTP_PROXY": "",
                "HTTPS_PROXY": "",
                "ALL_PROXY": "",
                "NO_PROXY": "*"
            },
            "timeout": 1800
        }
    }
}
```

连接好之后，在`manage mcp servers`界面，应该能出来可用的mcp函数列表，整理如下

```
# 核心代码获取与导航
fetch_current_class 获取 JADX-GUI 插件中当前选中的类及其代码。
get_selected_text 返回反编译代码视图中当前选中的文本。
get_method_by_name 根据名称获取特定类中方法的源代码。
get_all_classes 返回项目中的所有类列表（支持分页）。
get_class_source 获取特定类的 Java 源代码。
search_method_by_name 在所有类中搜索特定的方法名。
get_methods_of_class 列出一个类中的所有方法名称。
search_classes_by_keyword 搜索源代码中包含特定关键字的类。
get_fields_of_class 列出一个类中的所有字段名称。
get_smali_of_class 获取一个类的 Smali 代码表示。

# 资源与清单文件
get_android_manifest 获取并返回 AndroidManifest.xml 的内容。
get_strings 获取 strings.xml 文件的内容。
get_all_resource_file_names 获取所有资源文件的名称。
get_resource_file 获取特定资源文件的内容。
get_main_application_classes_names 从 Manifest 包配置中获取主应用程序（Application）类的名称。
get_main_application_classes_code 获取主应用程序（Application）类的代码（支持分页）。
get_main_activity_class 从 AndroidManifest.xml 中获取主 Activity 类。

# 重构与重命名
rename_class 重命名特定的类。
rename_method 重命名特定的方法。
rename_field 重命名特定的字段。
rename_package 重命名一个包及其包含的所有类。

# 调试 (Debug)
debug_get_stack_frames 获取当前的栈帧（调用栈）。
debug_get_threads 获取被调试进程中的所有线程。
debug_get_variables 在进程挂起（暂停）时获取当前变量。

# 交叉引用 (Xrefs)
get_xrefs_to_class 查找对某个类的所有引用。
get_xrefs_to_method 查找对某个方法的所有引用。
get_xrefs_to_field 查找对某个字段的所有引用。
```

### 提示词设计和优化

之前flanker发布的JEB-MCP中的提示词如下：

| 12345 | `1.` `连接MCP jadx``-``mcp``-``server``2.` `分析D:\xxx.apk应用的com.xxx.MainActivity类的功能``3.` `根据功能重命名所有方法名小于``3``个字符的名称``4.` `如果调用了其他类的方法，分析相应的类功能，并重命名方法名小于``3``个字符的名称``5.` `输出分析过程。` |
|-|-|

经过测试我的智障AI+MCP无法达到演示的效果。此种情况，可以将大的长期目标（完成反混淆）拆分成多个小的短期目标（获取类的代码，分析功能，重命名包、类、字段、方法的名称等等）。我们将需求告诉贵的、聪明的AI，让AI来拆分任务、形成一个初步提示词。然后我们把需要改善的地方告诉他，让他来优化。最后我们拿这个优化好的提示词去让便宜的、笨的AI去大量地做，以节省token和提高速度。

优化后的提示词如下。

```
# Role Definition

You are an advanced Android Reverse Engineering Expert Agent driven by JADX MCP. You excel at static code analysis in highly adversarial, heavily obfuscated environments. Your core principle is "evidence-based reasoning"—never guess.

# Task Context

* **Target APK Path:** `xxx.apk`
* **Target Scope:**
* *Mode A (Entry Class):* `com.xxxxx.XXX`
* *Mode B (Package Scan):* `[User provided package name]`

* **Output File:** `rename.txt`
* **Format Standard:** Defined in file `rename_templete.txt`

# Execution Workflow

## Phase 1: Scope Definition

1. Connect to JADX MCP.
2. Check user input:
* If **Package Name**: Call `search_classes_by_keyword` to get the class list, and output "Scanning package [Package Name], found [N] classes".
* If **Class Name**: Lock onto that class directly.

## Phase 2: Deep Analysis & Adversarial Detection

Iterate through every class in the target list (CurrentClass) and execute the following strict steps:

1. **Source Retrieval:** Get source code.
2. **Adversarial Environment Check (Critical):**
Before starting logic analysis, scan for situations JADX cannot handle and **record alerts immediately**:
* **Native Methods:** Are there methods modified by the `native` keyword? (C++ implementation cannot be analyzed)
* **Phantom Calls:** Are there calls to non-existent classes or methods? (Likely dynamic loading or class stripping)
* **Empty Methods:** Is the body of a called method empty? (Likely removed by obfuscator or instrumentation trap)
* *Action:* If found, explicitly mark in the analysis brief as "Unable to analyze: [Reason]".

3. **Deobfuscation Logic:**
For identifiers matching obfuscation characteristics (length < 3, meaningless characters), search for "Semantic Anchors" (strings, APIs, return values).

* **Strict Rule:** If no concrete evidence is found (such as explicit strings or API calls), or the logic is too obscure, you **must** rename it to `Unknown` or `Unknown_Method_[Hash]`. **Absolutely do not force meaning.**

## Phase 3: Recursive Dependency Analysis (Strict Control)

To understand the full context of the current class, check its external dependencies, but you must adhere to the following **circuit breaker mechanism**:

1. **Dependency Scan:** Scan all external classes/methods called by the current class.
2. **Filter Condition (Recursion Admission):** Initiate recursive analysis on an external class only if **all** the following conditions are met:
* The external class **is also obfuscated** (matches Phase 2 obfuscation characteristics).
* The external class has **not** been analyzed yet (Idempotency Check).
* **Recursion Depth:** Current recursion depth < **5 levels** (Depth < 5).

3. **Stop Check:** Once the depth limit is reached, stop tracing and mark it as `External_Obfuscated_Ref` at the current level to prevent Context Explosion.

## Phase 4: Progress Reporting

**Upon completing the analysis of a class (and its recursive dependencies), you must output a short report to the user:**

> "Analyzed Class: [ClassName] (Recursion Depth: [N]). Found [N] obfuscation points, Renamed [M], Unknown [X]. Adversarial Warning: [None/Native/Phantom]"

## Phase 5: Final Output Generation

Read and compile all renaming records, strictly following the format in `rename_templete.txt` to output to the file `rename.txt`.
```

rename_templete.txt内容如下

| 1234567891011121314151617181920212223242526272829 | `# rename.txt 规范说明``# =====================``# 格式: [类型]\|[包名/类名]\|[原名]\|[新名]\|[功能说明]``# 类型: C=类, M=方法, F=字段``# 每行一条记录，便于追加和快速解析``# 新会话时只需读取最后N行即可恢复上下文``#``# 示例:``# C\|com.xxxxx\|O000O0O00OOO0OOO0O0\|HijackDetectionManager\|劫持检测管理器``# M\|com.xxxxx.HijackDetectionManager\|O000O0O00OO0O0OOO0O\|handleActivityPaused\|Activity暂停处理``# F\|com.xxxxx.HijackDetectionManager\|O000O0O00OO0O0OOO0O\|sMainHandler\|主线程Handler` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``XXX 包反混淆记录``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=` `# 类重命名``C\|com.xxxxx\|O000O0O00OO0O0OOO0O\|SamplingMonitorRunnable\|原生采样监控Runnable``C\|com.xxxxx\|O000O0O00OO0O0OOOO0\|HijackActivityLifecycleCallback\|劫持检测Activity生命周期回调` `# 方法重命名``M\|com.xxxxx.unexp.AttackResponseHandler\|O000O0O00OO0O0OOO0O\|handleAttackDetected\|处理检测到的攻击``M\|com.xxxxx.xxxxxx\|O000O0O00OO0O0OOO0O\|onHomeKeyPressed\|Home键按下回调``M\|com.xxxxx.xxxxxx\|O000O0O00OO0O0OOOO0\|getContext\|获取Context` `# 字段重命名``F\|com.xxxxx.xxxxxx\|O000O0O00OO0O0OOO0O\|sContext\|上下文``F\|com.xxxxx.HijackDetectionManager\|O000O0O00OO0O0OOO0O\|sMainHandler\|主线程Handler``F\|com.xxxxx.HijackDetectionManager\|f11565O000O0O00OO0O0OOOO0\|sCurrentComponent\|当前组件` |
|-|-|

### 核心思想

1、强调“递归”，这样我们能让AI从我们更感兴趣的点或面入手，扩散至与他们相关的部分。这样能避免大量分析一些标准的、框架性质的、不是很感兴趣的功能。

2、为什么不用mcp的get_all_classes这个功能？因为这个返回的是整个apk的class，支持分页是每页显示多少条那种，而不是显示某个包下的所有class，测试app有200000个类，每次100条，就需要调2000次，这样上下文会很容易撑爆，触发上下文压缩，这样AI就有可能忘掉前面的但是重要的东西。但是可以用search_classes_by_keyword这个功能，搜索结果会比较精准。

>
>  也许可以先全量跑一次生成一棵树，然后根据节点序号去查找？后续可能考虑从这里下手优化。
>
>
>

3、为什么要设计一个rename_templete.txt？输出类的命令，如果是简单的说“完成后将xxx输出”，AI会每次设计一个新的格式输出，这样太乱，也不方便后续可能的其他自动化操作。另外，上述格式可以让AI每次都追加，而不是全量读取或输出一遍。以后遇到诸如内存爆了、jadx白屏了这种问题，在重启后可以直接让mcp“重新执行最后x条重命名操作”，快速恢复进度。

## 效果

上面图片中的混淆示例，经过反混淆实际可以达到如下效果。

![去混淆后](https://bbs.kanxue.com/upload/attach/202602/1059242_4ZYNSH5B8497J2A.png)

虽然还有一些错，但是基本上能看了。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-1-16 13:45*

感谢分享

## 回复 by mb_asiwnxyv (#3)

*2026-1-16 13:52*

感谢分享

## 回复 by 带带弟弟吧 (#4)

*2026-1-16 14:00*

11

## 回复 by bisoso (#5)

*2026-1-16 14:11*

感谢分享！

## 回复 by hellopen (#6)

*2026-1-16 14:52*

支持

## 回复 by huangjw (#7)

*2026-1-16 15:47*

真的那么好用吗

## 回复 by Mr.He (#8)

*2026-1-16 16:31*

666

## 回复 by wx_霿凇 (#9)

*2026-1-16 16:32*

666

## 回复 by 4Chan (#10)

*2026-1-16 16:59*

看看

## 回复 by mb_ysegxpmv (#11)

*2026-1-16 23:58*

牛逼，大佬

## 回复 by 黑屏 (#12)

*2026-1-17 08:25*

666

## 回复 by GEKEZYX (#13)

*2026-1-17 11:36*

666

## 回复 by mb_qimctavn (#14)

*2026-1-17 12:15*

6

## 回复 by lookzo (#15)

*2026-1-17 15:16*

6666

## 回复 by mb_cbgtaveo (#16)

*2026-1-17 15:39*

666666

## 回复 by 上官兮唐 (#17)

*2026-1-17 15:50*

看看

## 回复 by 希梦☆奈何 (#18)

*2026-1-17 16:16*

学习

## 回复 by 安小卓 (#19)

*2026-1-17 17:38*

学习

## 回复 by 熊猫吃鱼 (#20)

*2026-1-17 17:40*

6666666

## 回复 by mb_rwpvhfvs (#21)

*2026-1-17 19:07*

6666

## 回复 by zylyy (#22)

*2026-1-17 19:43*

666

## 回复 by mb_xhkcfjao (#23)

*2026-1-17 20:13*

感谢分享

## 回复 by Kill_Log (#24)

*2026-1-17 20:41*

666

## 回复 by Kill_Log (#25)

*2026-1-17 20:41*

666

## 回复 by Kill_Log (#26)

*2026-1-17 20:41*

666

## 回复 by 蓝色水瓶 (#27)

*2026-1-17 21:55*

666

## 回复 by git_97580helord (#28)

*2026-1-17 21:59*

cool

## 回复 by bbpk (#29)

*2026-1-17 22:21*

jeb里的mcp也挺好用

## 回复 by 快乐的小跳蛙 (#30)

*2026-1-17 22:37*

看看

## 回复 by 快乐的小跳蛙 (#31)

*2026-1-17 22:37*

看看

## 回复 by 我不在冷 (#32)

*2026-1-18 05:57*

MARK

## 回复 by ZACSN12 (#33)

*2026-1-18 09:30*

111

## 回复 by ZACSN12 (#34)

*2026-1-18 09:30*

111

## 回复 by guijingwen (#35)

*2026-1-18 11:11*

66

## 回复 by 淡然他徒弟 (#36)

*2026-1-18 11:23*

mark

## 回复 by 漂流的鱼 (#37)

*2026-1-18 11:25*

666

## 回复 by ldljlzw (#38)

*2026-1-18 13:01*

谢谢

## 回复 by 开胃小菜Wx (#39)

*2026-1-18 14:45*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by mb_zcudycuk (#40)

*2026-1-18 17:41*

6666

## 回复 by xingbing (#41)

*2026-1-18 21:00*

感谢分享 ！

## 回复 by kienmanowa (#42)

*2026-1-18 23:04*

感谢分享

## 回复 by fangliangz (#43)

*2026-1-19 09:10*

666

## 回复 by linix (#44)

*2026-1-19 09:36*

666

## 回复 by mb_auylfslb (#45)

*2026-1-19 09:55*

666

## 回复 by woaiziyou (#46)

*2026-1-19 09:56*

学习一下

## 回复 by woaiziyou (#47)

*2026-1-19 09:56*

学习一下

## 回复 by mb_auylfslb (#48)

*2026-1-19 09:56*

666

## 回复 by mb_lxotxkix (#49)

*2026-1-19 10:39*

666666666666

## 回复 by bambooeric (#50)

*2026-1-19 11:02*

666

## 回复 by 不知世事 (#51)

*2026-1-19 11:09*

学习

## 回复 by 不知世事 (#52)

*2026-1-19 11:09*

学习

## 回复 by git_56402Syy040316 (#53)

*2026-1-19 11:38*

666

## 回复 by iBa0 (#54)

*2026-1-19 11:41*

123

## 回复 by 铭天星 (#55)

*2026-1-19 11:49*

666

## 回复 by mb_xjdhrmck (#56)

*2026-1-19 13:45*

666

## 回复 by mb_xjdhrmck (#57)

*2026-1-19 13:45*

666

## 回复 by 正己 (#58)

*2026-1-19 13:56*

表哥牛逼

## 回复 by 正己 (#59)

*2026-1-19 13:56*

表哥牛逼

## 回复 by mb_zzzklvpa (#60)

*2026-1-19 14:16*

666666

## 回复 by mb_egsjciof (#61)

*2026-1-19 15:18*

感谢分享

## 回复 by wx_Yu_799 (#62)

*2026-1-19 15:32*

感谢分享

## 回复 by wx_Yu_799 (#63)

*2026-1-19 15:32*

感谢分享

## 回复 by 木槿any (#64)

*2026-1-19 16:02*

666

## 回复 by 乐活 (#65)

*2026-1-19 16:10*

666

## 回复 by wx_Dispa1r (#66)

*2026-1-19 22:17*

1

## 回复 by chenxinxia (#67)

*2026-1-20 10:34*

感谢分享

## 回复 by 烬奇小云 (#68)

*2026-1-20 14:22*

666

## 回复 by mb_wtskxwnr (#69)

*2026-1-20 15:32*

666

## 回复 by tjytjy (#70)

*2026-1-20 16:55*

666

## 回复 by LoeweErr (#71)

*2026-1-20 17:45*

666

## 回复 by ldehua (#72)

*2026-1-21 09:49*

感谢分享

## 回复 by ID蝴蝶 (#73)

*2026-1-21 14:35*

666

## 回复 by ouduomi (#74)

*2026-1-21 14:55*

感谢分享

## 回复 by Buu (#75)

*2026-1-21 16:03*

6666

## 回复 by mb_qqihqaoo (#76)

*2026-1-21 22:05*

666666

## 回复 by BRUCEVIP (#77)

*2026-1-22 00:18*

66666666

## 回复 by mb_elqwyvnm (#78)

*2026-1-22 00:31*

学习下

## 回复 by AndroidDev (#79)

*2026-1-22 10:51*

6666

## 回复 by 错了而已~ (#80)

*2026-1-22 15:29*

666

## 回复 by 寞叶_ (#81)

*2026-1-22 16:00*

学习一下

## 回复 by 壹久玖 (#82)

*2026-1-22 16:39*

111

## 回复 by zxqi (#83)

*2026-1-22 17:43*

666

## 回复 by iamshy (#84)

*2026-1-22 18:49*

感谢分享

## 回复 by xle (#85)

*2026-1-22 20:40*

666

## 回复 by mb_qblzkzce (#86)

*2026-1-22 21:03*

感谢分享

## 回复 by wx_逸_143 (#87)

*2026-1-23 01:18*

6666

## 回复 by xinhu (#88)

*2026-1-23 10:57*

111

## 回复 by FacelessC (#89)

*2026-1-23 11:39*

666

## 回复 by kingking888 (#90)

*2026-1-23 11:50*

666

## 回复 by 杨大王 (#91)

*2026-1-23 13:33*

666

## 回复 by mb_gqjpkkaz (#92)

*2026-1-23 14:41*

111

## 回复 by mb_uvyukvot (#93)

*2026-1-23 15:14*

666

## 回复 by mb_ejsmaepg (#94)

*2026-1-23 15:44*

6666

## 回复 by 哈猪 (#95)

*2026-1-23 16:35*

混淆过的apk怎么反编译呢，反编译后的包再次打包后就运行异常，这个怎么破，没有开发包

## 回复 by mb_ejwssbrk (#96)

*2026-1-23 16:58*

666

## 回复 by mb_emwvcbiq (#97)

*2026-1-23 20:05*

66666

## 回复 by Mirikkas (#98)

*2026-1-25 19:12*

感谢分享

## 回复 by onwyc123 (#99)

*2026-1-25 22:45*

666

## 回复 by erichyx (#100)

*2026-1-25 23:56*

666

## 回复 by 周小韬 (#101)

*2026-1-26 10:04*

666

## 回复 by shuangmou (#102)

*2026-1-26 10:33*

感谢分享

## 回复 by K.K (#103)

*2026-1-26 16:53*

666

## 回复 by mb_xreqcaxm (#104)

*2026-1-26 17:18*

好思路牛啊

## 回复 by chuj- (#105)

*2026-1-26 17:32*

看看。

## 回复 by wx_ln (#106)

*2026-1-26 19:03*

6666

## 回复 by mb_gwhsbnpt (#107)

*2026-1-27 10:54*

6

## 回复 by Da_ (#108)

*2026-1-27 10:56*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by memoriaru (#109)

*2026-1-27 15:00*

感谢分享

## 回复 by 小童net (#110)

*2026-1-28 00:37*

![image](https://bbs.kanxue.com/view/img/face/050.gif)

## 回复 by lqfcugo (#111)

*2026-1-29 11:05*

看看

## 回复 by daiviswang (#112)

*2026-1-29 11:25*

111111111

## 回复 by mb_gndxmsix (#113)

*2026-1-30 10:36*

666

## 回复 by XCicada (#114)

*2026-1-30 17:45*

666

## 回复 by wx_king of the world (#115)

*2026-1-30 19:26*

666

## 回复 by mb_myeogrox (#116)

*2026-1-30 21:03*

666

## 回复 by mb_cjxvunvr (#117)

*2026-1-31 10:30*

666

## 回复 by mb_eahujfpt (#118)

*2026-1-31 10:45*

谢谢分享

## 回复 by mb_rkuanlbh (#119)

*2026-1-31 10:53*

感谢分享

## 回复 by 宛枫 (#120)

*2026-1-31 22:43*

感谢分享

## 回复 by mb_ggnlrzcs (#121)

*2026-1-31 23:46*

666

## 回复 by 财神爷999 (#122)

*2026-2-1 17:37*

66666

## 回复 by best9 (#123)

*2026-2-2 15:30*

谢谢！很有收获。

## 回复 by mb_tnjdswra (#124)

*2026-2-2 17:26*

感谢分享，是个好思路哇

## 回复 by mb_hfpmtthz (#125)

*2026-2-3 08:48*

666

## 回复 by jongan (#126)

*2026-2-3 09:13*

感谢分享

## 回复 by 小叶叶_let (#127)

*2026-2-3 09:38*

666

## 回复 by mb_vfvkjkuk (#128)

*2026-2-3 11:45*

666

## 回复 by xautzbl (#129)

*2026-2-3 14:31*

666

## 回复 by mb_mdbezdns (#130)

*2026-2-4 10:17*

6666

## 回复 by mb_dwksysag (#131)

*2026-2-5 16:49*

6

## 回复 by 做好事不留名 (#132)

*2026-2-5 16:58*

1

## 回复 by S_602205 (#133)

*2026-2-5 17:06*

666

## 回复 by AK1988DA (#134)

*2026-2-5 19:55*

3

## 回复 by Kcarry (#135)

*2026-2-7 18:14*

66666

## 回复 by apxar (#136)

*2026-2-8 15:46*

1

## 回复 by sonyps (#137)

*2026-2-9 00:28*

可是jadx经常反编译失败呀

## 回复 by mb_ijumdife (#138)

*2026-2-10 10:45*

66666666

## 回复 by 逍遥无极天 (#139)

*2026-2-10 15:19*

666

## 回复 by God_li (#140)

*2026-2-10 16:24*

666

## 回复 by spdfdfer (#141)

*2026-2-11 11:15*

666

## 回复 by xxxxxxx_798269 (#142)

*2026-2-12 12:32*

1

## 回复 by libc (#143)

*2026-2-14 03:29*

666

## 回复 by hacker521 (#144)

*2026-2-14 04:51*

真的那么好用吗

## 回复 by mb_lzybjqdn (#145)

*2026-2-14 23:07*

感谢分享

## 回复 by mJqalJqN (#146)

*2026-2-15 09:49*

1

## 回复 by Ace_Heng (#147)

*2026-2-15 19:14*

看看看

## 回复 by tubecityman (#148)

*2026-2-15 23:23*

9999

## 回复 by 高级菜鸟 (#149)

*2026-2-16 10:55*

感谢分享！

## 回复 by dhruwen (#150)

*2026-2-16 13:44*

good

## 回复 by 非凡人平常心 (#151)

*2026-2-16 13:58*

感谢分享

## 回复 by wx_1_816 (#152)

*2026-2-18 15:36*

感谢分享

## 回复 by 闪光45 (#153)

*2026-2-20 16:05*

感谢分享

## 回复 by banana_02 (#154)

*2026-2-20 20:32*

666

## 回复 by mb_urzqsoer (#155)

*2026-2-20 23:11*

65654598459165

## 回复 by mb_mxsesokv (#156)

*2026-2-22 00:23*

666

## 回复 by mb_uggsnfmv (#157)

*2026-2-22 11:45*

666666

## 回复 by wx_include_376 (#158)

*2026-2-22 11:49*

6666

## 回复 by XCicada (#159)

*2026-2-22 13:24*

感谢分享

## 回复 by 毕索 (#160)

*2026-2-22 15:56*

666

## 回复 by mb_dainmpqw (#161)

*2026-2-25 00:00*

666

## 回复 by baichisi (#162)

*2026-2-25 17:06*

ttt

## 回复 by wc有蚊子 (#163)

*2026-2-25 17:23*

666

## 回复 by Gryffindoss (#164)

*2026-2-27 14:04*

6666

## 回复 by 逆向小呆呆 (#165)

*2026-2-27 14:17*

6666

## 回复 by xxjj678 (#166)

*2026-2-27 18:23*

666

## 回复 by 爱不惜 (#167)

*2026-2-27 21:52*

看看

## 回复 by xdnice (#168)

*2026-2-27 22:41*

谢谢楼主的分享。

## 回复 by wx_筟鈈疋 (#169)

*2026-2-28 09:44*

1111

## 回复 by 再遇雌鹿 (#170)

*2026-2-28 10:45*

感谢分享

## 回复 by 不想起名字a (#171)

*2026-2-28 16:48*

感谢分享![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by longforus (#172)

*2026-2-28 17:18*

666

## 回复 by xiaocaiji123 (#173)

*2026-3-2 10:00*

66666

## 回复 by alds (#174)

*2026-3-3 10:17*

感谢

## 回复 by 零_721409 (#175)

*2026-3-3 10:59*

666666666

## 回复 by 孤梦拾遗 (#176)

*2026-3-3 11:20*

666

## 回复 by 梨树生果 (#177)

*2026-3-5 19:19*

666

## 回复 by mb_zhbemswn (#178)

*2026-3-5 23:02*

666

## 回复 by mb_vwuaejat (#179)

*2026-3-7 09:59*

666

## 回复 by Li1nkl3e (#180)

*2026-3-8 09:40*

感谢分享

## 回复 by mb_ybvqgbkl (#181)

*2026-3-8 16:25*

66666

## 回复 by qig (#182)

*2026-3-8 16:55*

感谢分享

## 回复 by strin (#183)

*2026-3-9 16:32*

感谢分享

## 回复 by git_29583Bumchou (#184)

*2026-3-11 12:46*

SSSS

## 回复 by 红皮西瓜 (#185)

*2026-3-12 10:35*

6

## 回复 by mb_tjqabdvq (#186)

*2026-3-12 12:34*

期待更多精彩内容

## 回复 by 小迷糊ddd (#187)

*2026-3-17 12:08*

666

## 回复 by adnin (#188)

*2026-3-17 12:21*

666

## 回复 by xianhuimin (#189)

*2026-3-19 02:08*

感谢分享

## 回复 by wx_7788 (#190)

*2026-3-19 16:22*

6666

## 回复 by 寻梦之璐 (#191)

*2026-3-19 16:29*

666

## 回复 by mb_rztmbvgb (#192)

*2026-3-19 18:48*

666

## 回复 by mb_criqjxad (#193)

*2026-3-21 22:18*

666

## 回复 by cangwuhu (#194)

*2026-3-23 11:11*

666

## 回复 by qqqiu (#195)

*2026-3-23 12:29*

1

## 回复 by mb_jnmxfjku (#196)

*2026-3-23 13:44*

666

## 回复 by dsr000 (#197)

*2026-3-23 16:13*

666

## 回复 by mb_luvldgil (#198)

*2026-3-23 18:35*

1

## 回复 by 离人怎挽 (#199)

*2026-3-25 09:02*

666

## 回复 by 智童 (#200)

*2026-4-2 22:20*

厉害????

## 回复 by mb_kujsrqqv (#201)

*2026-4-8 01:27*

不错不错

## 回复 by mb_uktygsmq (#202)

*2026-4-8 02:53*

56666

## 回复 by 飆汗吉米 (#203)

*2026-4-10 22:18*

666

## 回复 by wugenb (#204)

*2026-4-10 22:43*

6666

## 回复 by wuxiping (#205)

*2026-4-11 20:01*

66666

## 回复 by 风里有民谣 (#206)

*2026-4-14 00:16*

666

## 回复 by 冷瞳 (#207)

*2026-4-18 18:58*

111]

## 回复 by mb_zcfhleoj (#208)

*2026-4-22 16:38*

感谢分享

## 回复 by Wblank (#209)

*2026-4-25 03:08*

666

## 回复 by mb_bxuawtsu (#210)

*2026-4-25 11:00*

111

## 回复 by 淡月疏桐影 (#211)

*2026-5-8 13:04*

666

## 回复 by mb_lzsjiukj (#212)

*2026-5-8 20:42*

感谢分享

## 回复 by wx_wyx (#213)

*2026-5-8 22:22*

66

## 回复 by method (#214)

*2026-5-19 17:38*

1

## 回复 by wumh (#215)

*2026-5-19 21:23*

感谢分享

## 回复 by mb_qupzepyf (#216)

*2026-5-20 11:06*

666

## 回复 by 温泉划水鱼 (#217)

*2026-5-23 16:28*

看看

## 回复 by C1ever (#218)

*2026-5-23 21:34*

666

## 回复 by ClPrada (#219)

*2026-5-28 16:10*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_xwntdpxy (#220)

*2026-6-1 21:13*

666

## 回复 by SInnon (#221)

*2026-6-7 17:27*

666

## 回复 by Bonquer (#222)

*2026-6-8 10:19*

66

## 回复 by 海sf (#223)

*2026-6-9 14:17*

看看

## 回复 by wx_coddvccwyh (#224)

*2026-6-12 15:30*

6666

## 回复 by 量凉 (#225)

*2026-6-19 01:23*

666

## 回复 by wx_WantC (#226)

*2026-6-19 05:09*

不错

## 回复 by Proto (#227)

*2026-7-3 11:01*

666

## 回复 by Iceshara (#228)

*2026-7-7 22:25*

666

## 回复 by Circ1e (#229)

*2026-7-9 17:11*

666

## 回复 by mb_iiumogmn (#230)

*2026-7-12 22:58*

感谢分享，深入学习

## 回复 by 伊苏尔德 (#231)

*2026-7-13 18:37*

1

## 回复 by mb_4nrpVMxJ (#232)

*2026-7-13 19:11*

666

## 回复 by 二木先生 (#233)

*2026-7-13 19:37*

学习

## 回复 by lamboo (#234)

*2026-7-13 20:15*

66666

## 回复 by mb_degalzhb (#235)

*2026-7-20 10:58*

感谢分享《使用JADX-MCP高效反混淆》。文中的分析过程和关键思路很有参考价值，我会结合实际环境进一步验证和学习。

## 回复 by 幻生 (#236)

*2026-7-21 21:29*

6666

## 回复 by mb_eospsxcx (#237)

*2026-7-24 09:55*

666

## 回复 by 阿三 (#238)

*2026-7-24 10:02*

666

## 回复 by mb_fkmhhynr (#239)

感谢分享
