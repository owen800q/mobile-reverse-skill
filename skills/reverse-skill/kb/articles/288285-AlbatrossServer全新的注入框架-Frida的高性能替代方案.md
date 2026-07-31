---
title: '[原创]AlbatrossServer全新的注入框架，Frida的高性能替代方案'
url: https://bbs.kanxue.com/thread-288285.htm
tid: 288285
author: WanQing
date: '2025-08-29'
tags: [Android安全, 原创, 基础理论, 逆向分析, 漏洞相关, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T15:36:22+08:00'
replies: 157
---

## **开发背景**

Frida难以应对发杂的代码逻辑，容易对抗，运行效率低。spawn模式有缺陷，多进程app会有问题，特征改来改去，索性自己开发一套。

## **项目简介**

**AlbatrossServer** 是一款专为 **Android 安全研究、逆向分析、动态监控** 设计的工具，支持在设备上实时注入 **AlbatrossAndroid Hook 代码**，实现对目标进程的 **动态插桩、代码修改、方法拦截、日志监控** 等功能。

**核心特点**：
✅ **PC 端远程控制**（Python API）
✅ **支持 Launch（启动注入）和 Attach（运行时注入）**
✅ **可 Hook 系统应用 & 普通 App**
✅ **支持 x86、x86_64、ARM、ARM64 架构**
✅ **提供 Java 层插件开发框架**
✅ **对抗少，Frida无法运行可以尝试它**

**⚠️ 重要声明**：

- **仅供安全研究、逆向学习、漏洞挖掘使用**
- **禁止用于非法破解、恶意攻击、商业盗版等行为**
- **需 Root 权限**（依赖 SELinux 宽松模式）

---

## **项目结构**

| 模块 | 说明 |
|-|-|
| **albatross-python** | PC 端控制工具，用于设备管理、App 启动/注入、RPC 调用 |
| **albatross-java** | 设备端核心代码，运行在 `system_server` 或目标 App 进程 |
| **resource** | 存储注入所需的 `agent.so`、`albatross_server`、Demo 插件 |

---

## **核心功能**

### **1. 动态注入（Launch & Attach）**

- **Launch 模式**（类似 Frida `spawn`）：

	- 在 App 启动前注入，可拦截 `Application.onCreate()` 之前的逻辑
	- 适用于需要 **早期 Hook** 的场景（如修改 `ClassLoader`、拦截 `ActivityThread`）
- **Attach 模式**（类似 Frida `attach`）：

	- 附加到已运行的进程，适用于 **运行时调试**

### **2. 插件开发（Java 层 Hook）**

- 插件需继承 `AlbatrossInjector`，并实现关键生命周期方法：

| 1234567891011121314151617181920212223 | `public` `class` `DemoInjector` `extends` `AlbatrossInjector {``public` `DemoInjector(String libName, String argString,` `int` `flags) {``super``(libName, argString, flags);``}` `@Override``public` `void` `beforeMakeApplication() {``// App 未初始化时调用（仅 Launch 模式生效）``Albatross.log(``"Before Application.makeApplication()"``);``}` `@Override``public` `void` `beforeApplicationCreate(Application application) {``// Application.onCreate() 之前调用``Albatross.hookClass(ActivityH.``class``);` `// Hook 目标类``}` `@Override``public` `void` `afterApplicationCreate(Application application) {``// Application.onCreate() 之后调用``Albatross.log(``"After Application.onCreate()"``);``}``}` |
|-|-|

### **3. Python API 示例**

| 123456789101112131415161718192021222324 | `import` `albatross``import` `time` `device` `=` `albatross.get_device(``"your_device_id"``)` `# 获取设备``assert` `device.is_root` `# 检查 Root 权限` `# 获取已安装的 App 列表``user_pkgs` `=` `device.get_user_packages()` `# 注入 Demo 插件``inject_dex` `=` `"plugins/injector_demo.apk"`  `# 插件路径``inject_class` `=` `"qing.albatross.app.agent.DemoInjector"`  `# 插件全限定名` `for` `pkg` `in` `user_pkgs:``if` `"albatross"` `in` `pkg:` `# 仅测试目标 App``print``(f``"Testing {pkg}..."``)``device.stop_app(pkg)` `# 停止 App``device.start_app(pkg)` `# 重新启动（Launch 模式）``time.sleep(``3``)``device.attach(pkg, inject_dex,` `None``, inject_class)` `# 注入插件``device.home()` `# 返回桌面``time.sleep(``2``)` `print``(``"Test completed!"``)` |
|-|-|

---

## **适用场景**

 **Android 安全研究**（动态分析恶意软件、Hook 敏感 API）
 **逆向工程**（修改 App 行为、绕过签名校验）
 **漏洞挖掘**（监控 JNI 调用、拦截系统服务）
 **学习 Android 内部机制**（如 `ActivityThread`、`Binder` 通信）

---

## **下载 & 使用**

 **GitHub 地址**：<https://github.com/AlbatrossHook/AlbatrossServer>

---

设备数量有限，仅在少量的设备上测试，出现bug在论坛上反馈太麻烦了，所以特定创建QQ群，便于交流反馈。

QQ群：478564202 （安卓移动安全逆向隐私合规分析）

**欢迎安全研究者、逆向工程师交流讨论！** ????

---

# 回复

## 回复 by tonykros (#2)

*2025-8-29 08:26*

Thank you very much

## 回复 by SomeMx (#3)

*2025-8-29 08:42*

过来瞧瞧

## 回复 by visow (#4)

*2025-8-29 09:07*

学习学习

## 回复 by mb_ldbucrik (#5)

*2025-8-29 09:09*

向大佬学习

## 回复 by jdong (#6)

*2025-8-29 09:28*

向大佬学习

## 回复 by luckbbs (#7)

*2025-8-29 09:40*

向大佬学习

## 回复 by matrump (#8)

*2025-8-29 09:55*

666

## 回复 by mb_fidppcok (#9)

*2025-8-29 10:01*

过来瞧瞧

## 回复 by KanXue_NG (#10)

*2025-8-29 10:17*

向佬学习学习

## 回复 by 黑屏 (#11)

*2025-8-29 10:32*

666

## 回复 by A冷忆 (#12)

*2025-8-29 10:42*

666

## 回复 by mb_asiwnxyv (#13)

*2025-8-29 10:56*

向大佬学习

## 回复 by huangjw (#14)

*2025-8-29 11:00*

![image](https://bbs.kanxue.com/view/img/face/079.gif) 牛啊

## 回复 by jw8888 (#15)

*2025-8-29 12:34*

666666666

## 回复 by wx_Ruin (#16)

*2025-8-29 12:36*

66666666

## 回复 by xianhuimin (#17)

*2025-8-29 15:29*

tql 666

## 回复 by TreeHole (#18)

*2025-8-29 16:38*

666 tql

## 回复 by 夜惜风雨 (#19)

*2025-8-29 17:40*

666 tql

## 回复 by wx_插曲 (#20)

*2025-8-29 18:07*

666 tql

## 回复 by mb_irhdtnzm (#21)

*2025-8-29 19:34*

666

## 回复 by 灌者为王 (#22)

*2025-8-30 14:23*

向大佬学习

## 回复 by mb_elqwyvnm (#23)

*2025-8-30 14:27*

可以学习

## 回复 by mb_ebiwunmj (#24)

*2025-8-31 00:44*

牛皮啊

## 回复 by mudebug (#25)

*2025-8-31 00:46*

666

## 回复 by didiid (#26)

*2025-8-31 15:24*

666

## 回复 by 奋斗小菜鸟 (#27)

*2025-8-31 17:30*

看看

## 回复 by 希梦☆奈何 (#28)

*2025-8-31 17:49*

路过学习

## 回复 by Imxz (#29)

*2025-8-31 20:47*

tql

## 回复 by 筹码 (#30)

*2025-9-1 01:17*

66666

## 回复 by 带带弟弟吧 (#31)

*2025-9-1 09:03*

111

## 回复 by fangliangz (#32)

*2025-9-1 09:33*

666

## 回复 by 晨曦遇晓 (#33)

*2025-9-1 10:53*

66666

## 回复 by wushuang双 (#34)

*2025-9-1 12:13*

牛皮啊

## 回复 by mb_qqihqaoo (#35)

*2025-9-1 12:51*

66666

## 回复 by upcj (#36)

*2025-9-1 15:09*

666

## 回复 by 万里星河 (#37)

*2025-9-1 15:24*

666

## 回复 by cmputer (#38)

*2025-9-1 15:28*

学习

## 回复 by 丁海洋 (#39)

*2025-9-1 16:03*

6666

## 回复 by shuangmou (#40)

*2025-9-2 00:50*

学习学习

## 回复 by 飆汗吉米 (#41)

*2025-9-2 03:28*

666

## 回复 by pigsub (#42)

*2025-9-2 04:40*

6666

## 回复 by mb_uwlfzzlj (#43)

*2025-9-2 10:40*

感谢大佬

## 回复 by 云觞 (#44)

*2025-9-2 11:42*

向佬学习

## 回复 by hekes (#45)

*2025-9-2 19:29*

看看

## 回复 by wx_huhu_859 (#46)

*2025-9-2 22:53*

去

## 回复 by MsScotch (#47)

*2025-9-2 23:03*

有真实的例子 可以学习么

## 回复 by fvduan (#48)

*2025-9-2 23:23*

很好

## 回复 by 温泉划水鱼 (#49)

*2025-9-3 00:08*

谢谢

## 回复 by mb_cbgtaveo (#50)

*2025-9-3 01:40*

6666666

## 回复 by Mrzh (#51)

*2025-9-3 07:59*

666

## 回复 by uni7corn (#52)

*2025-9-3 10:54*

6666

## 回复 by 魏朝阳 (#53)

*2025-9-3 12:01*

强

## 回复 by xiaoc996 (#54)

*2025-9-3 16:00*

66666

## 回复 by mb_ivdgiaqo (#55)

*2025-9-3 16:16*

iiii

## 回复 by 九黎 (#56)

*2025-9-4 08:30*

牛逼

## 回复 by mb_hfpmtthz (#57)

*2025-9-4 09:28*

6666

## 回复 by wx_小友 (#58)

*2025-9-5 14:52*

066

## 回复 by git_17554snsj369 (#59)

*2025-9-5 15:35*

tql

## 回复 by Sigil (#60)

*2025-9-6 20:37*

1

## 回复 by mb_ghebfkzn (#61)

*2025-9-7 17:05*

1

## 回复 by 口艾口牙女马口牙 (#62)

*2025-9-7 22:25*

666

## 回复 by xeiyu (#63)

*2025-9-8 00:25*

666

## 回复 by xx_dd_y (#64)

*2025-9-8 09:46*

66666666

## 回复 by XCicada (#65)

*2025-9-8 10:45*

学习

## 回复 by 机车王子 (#66)

*2025-9-8 11:05*

感谢你的积极参与，期待更多精彩内容！

## 回复 by ivy1 (#67)

*2025-9-8 15:41*

这应该只有他的特定设备能跑

## 回复 by wx_aa_775 (#68)

*2025-9-8 20:39*

666666

## 回复 by WanQing (#69)

*2025-9-8 23:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  ivy1](https://bbs.kanxue.com/user-972238.htm)
>
>  这应该只有他的特定设备能跑
>
>

真机虚拟机arm,arm64,x86,x64能运行AlbatrossAndroid都可以的,selinux规则修改可能不全，注入失败可以关闭

## 回复 by wx_五十度灰 (#70)

*2025-9-17 13:33*

666

## 回复 by wx_霿凇 (#71)

*2025-9-17 15:43*

666

## 回复 by ben_ (#72)

*2025-9-18 18:22*

学习

## 回复 by lbunknow (#73)

*2025-9-19 13:54*

5555

## 回复 by wx_！_336 (#74)

*2025-9-22 20:22*

111

## 回复 by mb_anbthlub (#75)

*2025-9-22 20:28*

66666666666

## 回复 by Pe1Chen (#76)

*2025-9-23 14:29*

666

## 回复 by birdcard (#77)

*2025-9-23 15:41*

666666666

## 回复 by ab19950220 (#78)

*2025-9-23 17:24*

学习一下

## 回复 by mb_yjiuccxa (#79)

*2025-9-23 17:32*

666

## 回复 by mb_wujvwaae (#80)

*2025-9-23 17:40*

大佬，学习让我进步

## 回复 by 八嘎boy (#81)

*2025-9-23 20:17*

6666

## 回复 by huangbof (#82)

*2025-9-25 19:59*

666

## 回复 by dawnsky1111 (#83)

*2025-9-25 22:21*

66

## 回复 by Valerian7 (#84)

*2025-9-26 10:52*

6666

## 回复 by mb_nhphjyjb (#85)

*2025-10-6 13:23*

感谢分享

## 回复 by mb_gmubqahb (#86)

*2025-10-10 15:07*

6666

## 回复 by mb_ykavguun (#87)

*2025-10-12 22:35*

55555

## 回复 by mb_gqjpkkaz (#88)

*2025-10-13 11:19*

学习

## 回复 by 大魔头 (#89)

*2025-10-13 11:40*

666

## 回复 by mb_bezctjbs (#90)

*2025-10-13 13:21*

学习学习

## 回复 by mb_cizqyhuh (#91)

*2025-10-13 14:01*

这框架确实比Frida好用多了，多进程和性能问题都解决了，Java插件设计也很人性化，配合[思维导图](https://www.anygraphanywhere.com/module/mind_map.html)会更直观，期待更多实际使用案例分享！

![image](https://bbs.kanxue.com/upload/attach/202510/1040915_BWUTY2UKVT46FYB.webp)

## 回复 by Gryffindoss (#92)

*2025-10-13 14:03*

666

## 回复 by mb_ugxtlzlx (#93)

*2025-10-18 15:26*

6666

## 回复 by mb_dmryhnwz (#94)

*2025-10-18 15:53*

666

## 回复 by 情迁 (#95)

*2025-10-29 17:15*

kank

## 回复 by 随风而行aa (#96)

*2025-11-8 20:54*

看卡

## 回复 by kishou_yusa (#97)

*2025-11-8 21:09*

66

## 回复 by mb_qimctavn (#98)

*2025-11-16 13:04*

6

## 回复 by wx_马 (#99)

*2025-11-17 12:08*

666

## 回复 by mb_lakweznz (#100)

*2025-11-17 12:27*

1

## 回复 by YoungBai (#101)

*2025-11-18 18:22*

666

## 回复 by mb_pfmgmdso (#102)

*2025-11-20 16:11*

666

## 回复 by mJqalJqN (#103)

*2025-11-20 17:28*

1

## 回复 by 黑色心跳 (#104)

*2025-11-21 20:58*

厉害

## 回复 by zylyy (#105)

*2025-11-21 22:27*

66666

## 回复 by 野狼 (#106)

*2025-11-23 14:27*

学习学习

## 回复 by mb_fhpfcoqp (#107)

*2025-11-25 17:57*

666

## 回复 by mb_ztqcemce (#108)

*2025-11-28 09:03*

看看教程

## 回复 by godiand (#109)

*2025-11-28 13:48*

又有新轮子了

## 回复 by asm_zhang (#110)

*2025-12-3 15:42*

6

## 回复 by mb_awbfnjrt (#111)

*2025-12-3 15:46*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by git_56701jackt88 (#112)

*2025-12-7 10:47*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_pmwkabcl (#113)

*2025-12-8 06:48*

6

## 回复 by mb_jqqxasya (#114)

*2025-12-9 21:56*

666

## 回复 by mb_pobqzscg (#115)

*2025-12-10 18:06*

666

## 回复 by git_94730eaydwshawke-gif (#116)

*2025-12-10 22:57*

666

## 回复 by mb_jvgnqejw (#117)

*2025-12-11 22:39*

777

## 回复 by lidongyooo (#118)

*2025-12-25 10:48*

666

## 回复 by 莱茵 (#119)

*2025-12-25 15:12*

666

## 回复 by wen55444 (#120)

*2026-1-22 05:41*

666

## 回复 by mb_aiyhfydo (#121)

*2026-1-22 10:33*

可以

## 回复 by popo223 (#122)

*2026-1-24 23:03*

666

## 回复 by SInnon (#123)

*2026-1-25 04:19*

6666666

## 回复 by mb_4nrpVMxJ (#124)

*2026-1-25 07:07*

666

## 回复 by mb_lnesxqxz (#125)

*2026-1-25 09:42*

6666

## 回复 by ouduomi (#126)

*2026-1-25 13:30*

学习学习

## 回复 by mb_tcandlos (#127)

*2026-1-25 22:03*

1

## 回复 by cecini (#128)

*2026-1-27 12:25*

注入框架AlbatrossServer 与hook框架 Albatross Android什么区别？
注入框架与hook框架什么区别

## 回复 by mb_axzjntyl (#129)

*2026-2-6 08:49*

666

## 回复 by mb_uodtmdzg (#130)

*2026-2-6 08:58*

6666

## 回复 by mb_xflcgdik (#131)

*2026-2-6 09:38*

666

## 回复 by mb_jhohnbzu (#132)

*2026-2-12 10:05*

666

## 回复 by mb_oddjuffq (#133)

*2026-2-12 12:27*

6666

## 回复 by mb_tkluuesh (#134)

*2026-2-14 09:53*

666

## 回复 by mb_iywmjqjc (#135)

*2026-3-3 14:49*

666

## 回复 by mb_tcheuwvg (#136)

*2026-3-19 13:35*

1111

## 回复 by iBa0 (#137)

*2026-3-25 22:10*

111

## 回复 by mb_ghcouuzx (#138)

*2026-3-25 22:28*

看看看

## 回复 by mb_rrwegvyc (#139)

*2026-3-30 10:58*

666

## 回复 by tjytjy (#140)

*2026-4-10 15:33*

666

## 回复 by YOYO2021 (#141)

*2026-5-4 18:16*

666

## 回复 by mb_lzotvdxv (#142)

*2026-5-10 00:34*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by mb_ezmrnfsu (#143)

*2026-5-15 23:08*

666

## 回复 by 086Love (#144)

*2026-5-16 09:43*

学习

## 回复 by จุ๊บ习惯性的回下头 (#145)

*2026-5-22 18:31*

学习学习试试  frida被检测的太厉害

## 回复 by mb_uohfzjqw (#146)

*2026-5-22 19:14*

666

## 回复 by mb_njmrwrqv (#147)

*2026-5-23 09:37*

666

## 回复 by g-yan (#148)

*2026-5-26 22:34*

666

## 回复 by Popluna (#149)

*2026-6-20 06:53*

是否可以直接替换呢

## 回复 by git_98579rabbits0209 (#150)

*2026-6-20 14:44*

牛逼

## 回复 by nuomida (#151)

*2026-6-30 13:12*

学习学习

## 回复 by mb_dswynejo (#152)

*2026-7-1 20:21*

666

## 回复 by mb_awqgymxv (#153)

*2026-7-7 10:15*

学习了

## 回复 by git_74909tuanha1305 (#154)

*2026-7-7 11:40*

牛皮啊

## 回复 by mb_ghcouuzx (#155)

*2026-7-7 12:04*

进不去，框架中文名是什么？

## 回复 by 八岁鱼 (#156)

*2026-7-20 04:34*

向大佬学习

## 回复 by Vengeance (#157)

*2026-7-22 18:45*

666

## 回复 by git_13573jjchoNC (#158)

xie xie
