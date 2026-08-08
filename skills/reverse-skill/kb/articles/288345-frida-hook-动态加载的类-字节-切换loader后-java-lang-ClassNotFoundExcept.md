---
title: '[原创]frida hook 动态加载的类（字节），切换loader后，java.lang.ClassNotFoundException的问题'
url: https://bbs.kanxue.com/thread-288345.htm
tid: 288345
author: Bondzhen
date: '2025-09-02'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-08T10:48:04+00:00'
replies: 46
---

// ===== 配置区 =====
 const TARGET_CLASS = "com.bytedance.sdk.component.r.mn.o"; // 匿名内部类
 const TARGET_METHOD = "cx"; // 目标回调
// const TARGET_CLASS = "com.bytedance.sdk.component.on.mn.t$1"; // 匿名内部类
//// const TARGET_METHOD = "onFailure"; // 目标回调
// const TARGET_METHOD = "onResponse"; // 目标回调
 const PASSTHROUGH = true; // true=调用原方法更稳；false=不调原方法（仅观测）

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879808182838485868788899091929394959697 | `Java.perform(function () {``var pinnedLoader` `=` `null;` `/``/` `1``) 精准锁定能加载目标类的 ClassLoader（找到就停止）``Java.enumerateClassLoaders({``onMatch: function (loader) {``try` `{``if` `(loader.findClass(TARGET_CLASS)) {``pinnedLoader` `=` `loader;``return` `'stop'``;` `/``/` `立刻停止，避免后续被别的 loader 覆盖``}``} catch (e) {}``},``onComplete: function () {}``});` `if` `(!pinnedLoader) {``console.log(``"[!] Target class not found in any loader:"``, TARGET_CLASS);``return``;``}``console.log(``"[*] Pinned loader ="``, pinnedLoader);` `/``/` `2``) 切到该 loader 后再 use``Java.classFactory.loader` `=` `pinnedLoader;``var Target` `=` `Java.use(TARGET_CLASS);` `/``/` `为防止 ContextClassLoader 被第三方（如 GDT）换走，这里准备线程类``var Thread` `=` `Java.use(``"java.lang.Thread"``);` `/``/` `3``) 安全 Hook：不去 toString 参数、不访问 getClass，避免触发类加载``Target[TARGET_METHOD].overloads.forEach(function (ov) {``const sig` `=` `ov.argumentTypes.``map``(t` `=``> t.className).join(``", "``);``console.log(``"[*] Hooking"``, TARGET_CLASS` `+` `"."` `+` `TARGET_METHOD` `+` `"("` `+` `sig` `+` `")"``);` `ov.implementation` `=` `function () {``/``/` `3.1` `线程上下文 ClassLoader 保护``var t` `=` `Thread.currentThread();``var old` `=` `t.getContextClassLoader();``var needRestore` `=` `false;``try` `{``/``/` `只有在不同的时候才设置，避免无谓扰动``if` `(old !``=``=` `pinnedLoader) {``t.setContextClassLoader(pinnedLoader);``needRestore` `=` `true;``}``} catch (e) {``/``/` `忽略：某些 ROM 可能限制``}``/``/` `3.2` `观测：仅打印一次固定文案，不触碰任何参数，避免触发类加载``console.log(``"[+] onFailure() invoked"``);``try` `{``if` `(PASSTHROUGH) {``console.log(``"[+] onFailure() invoked2222"``);``/``/` `打印所有参数``console.log(``"\n====== Hooked onResponse ======"``);``try` `{``for` `(let i` `=` `0``; i < arguments.length; i``+``+``) {``let arg` `=` `arguments[i];``try` `{``console.log(``"  arg["` `+` `i` `+` `"]: "` `+` `arg);``} catch (ee) {``console.log(``"  arg["` `+` `i` `+` `"]: <error printing> "` `+` `ee);``}``}``} catch (e) {``console.log(``"!! error printing arguments:"``, e);``}``console.log(``"[+] onFailure() invoked3333"``);``/``/` `调用原方法通常更稳（SDK 上层可能依赖该回调触发后续清理）``let ret;``try` `{``if` `(PASSTHROUGH) {``ret` `=` `ov.``apply``(this, arguments);``console.log(``">>> [Return Value]:"``, ret);``return` `ret;``}` `else` `{``console.log(``">>> NOOP (skip original)"``);``return``;` `/``/` `void``}``} catch (e) {``console.log(``"!!! Exception in hook:"``, e);``}``}` `else` `{``/``/` `NOOP：不调用原方法，只做观测``return``;``}``}` `finally` `{``/``/` `3.3` `恢复 ContextClassLoader``if` `(needRestore) {``try` `{ t.setContextClassLoader(old); } catch (e) {}``}``}``};``});` `console.log(``"[*] Hook installed:"``, TARGET_CLASS` `+` `"."` `+` `TARGET_METHOD);``});` |
|-|-|

---

# 回复

## 回复 by zz胡 (#2)

*2025-9-2 10:46*

看看

## 回复 by SomeMx (#3)

*2025-9-2 11:07*

过来瞧瞧

## 回复 by mb_qimctavn (#4)

*2025-9-2 11:47*

6

## 回复 by 飆汗吉米 (#5)

*2025-9-2 12:40*

666

## 回复 by tonykros (#6)

*2025-9-2 15:55*

666

## 回复 by wx_插曲 (#7)

*2025-9-2 16:17*

666

## 回复 by uni7corn (#8)

*2025-9-3 10:48*

6666

## 回复 by didiid (#9)

*2025-9-3 14:34*

666

## 回复 by iBa0 (#10)

*2025-9-4 17:45*

2

## 回复 by 寻梦之璐 (#11)

*2025-9-4 19:22*

1

## 回复 by Arsylk (#12)

*2025-9-5 07:08*

1

## 回复 by 带带弟弟吧 (#13)

*2025-9-5 10:52*

11

## 回复 by mb_npylpnpl (#14)

*2025-9-5 15:22*

1

## 回复 by baitongling (#15)

*2025-9-5 15:58*

1

## 回复 by mb_ykavguun (#16)

*2025-9-5 20:41*

1

## 回复 by MaYil (#17)

*2025-9-5 21:45*

感谢分享

## 回复 by mb_mdbezdns (#18)

*2025-9-6 01:29*

66666666

## 回复 by 筹码 (#19)

*2025-9-6 10:09*

66666

## 回复 by mb_dqwgdsem (#20)

*2025-9-6 23:06*

666666666666666

## 回复 by 威兹曼 (#21)

*2025-9-7 10:00*

感谢分享

## 回复 by mb_ghebfkzn (#22)

*2025-9-7 15:48*

1

## 回复 by 希梦☆奈何 (#23)

*2025-9-7 16:25*

看看

## 回复 by XCicada (#24)

*2025-9-8 10:33*

看看

## 回复 by shuangmou (#25)

*2025-9-9 00:21*

感谢分享

## 回复 by `姚大齐丶Nayo (#26)

*2025-9-9 09:27*

感谢分享

## 回复 by SandKing (#27)

*2025-9-11 14:01*

看看

## 回复 by 智取琪 (#28)

*2025-9-15 11:33*

6

## 回复 by mb_auylfslb (#29)

*2025-9-15 14:13*

1

## 回复 by wx_郑泽科 (#30)

*2025-9-18 16:28*

感谢分享

## 回复 by KanXue_NG (#31)

*2025-10-4 15:15*

学习学习

## 回复 by 1iuyan (#32)

*2025-10-16 20:02*

orz

## 回复 by xx_dd_y (#33)

*2025-10-23 14:50*

666

## 回复 by method (#34)

*2025-10-28 17:07*

1

## 回复 by mb_hcttxirp (#35)

*2025-11-20 14:47*

感谢分享

## 回复 by mb_bhsrdtqf (#36)

*2025-12-4 12:42*

大佬

## 回复 by zylyy (#37)

*2025-12-4 13:08*

6666

## 回复 by FMNS (#38)

*2025-12-5 08:36*

感谢分享

## 回复 by huangjw (#39)

*2025-12-5 09:18*

its goods

## 回复 by mb_ngwaisbz (#40)

*2025-12-14 00:55*

6666

## 回复 by 我心向山 (#41)

*2025-12-22 18:30*

感谢分享

## 回复 by tigericon (#42)

*2025-12-22 18:41*

66

## 回复 by mb_cbgtaveo (#43)

*2026-2-5 13:50*

66666666666666

## 回复 by 抬头望月 (#44)

*2026-2-5 14:23*

看看

## 回复 by Tanuyoki0 (#45)

*2026-3-9 18:20*

看看思路

## 回复 by wohowo (#46)

*2026-3-9 18:42*

1

## 回复 by 小李08 (#47)

*2026-3-18 15:23*

666
