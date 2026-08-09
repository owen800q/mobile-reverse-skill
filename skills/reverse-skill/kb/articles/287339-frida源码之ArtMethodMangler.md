---
title: '[原创]frida源码之ArtMethodMangler'
url: https://bbs.kanxue.com/thread-287339.htm
tid: 287339
author: 我不是卷王
date: '2025-06-24'
tags: [Android安全, 原创, 基础理论, HOOK注入, 源码框架, 逆向分析]
crawled_at: '2026-08-09T04:48:49+00:00'
replies: 82
---

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122 | `class ArtMethodMangler {``//构造一个方法 hook 的控制对象``constructor (opaqueMethodId) {``//将 opaqueMethodId 转换为 Frida 内部可直接操作的“原始方法 ID”格式``const methodId = unwrapMethodId(opaqueMethodId);``//将解包后的 methodId 保存在当前对象中，表示“目标 Java 方法”的实际 ID``this``.methodId = methodId;``//初始化 originalMethod 为 null``this``.originalMethod =``null``;``//当前正在生效的“方法实现”。初始时还没有被 hook，因此是原始的 methodId。hook 之后它可能会指向 trampoline 或 replacement``this``.hookedMethodId = methodId;``//存储替代方法（replacement）的 ID``this``.replacementMethodId =``null``;``//存放 Frida 提供的 Interceptor 对象，用于 attach 到目标函数上，实现拦截逻辑``this``.interceptor =``null``;``}` `replace (impl, isInstanceMethod, argTypes, vm, api) {``const { kAccCompileDontBother, artNterpEntryPoint } = api;``//java方法hook前 备份原始值``this``.originalMethod = fetchArtMethod(``this``.methodId, vm);``//保存原生方法的访问标志``const originalFlags =``this``.originalMethod.accessFlags;``//绕过 Xposed Hook 的方法劫持，恢复 Java 方法的真实原始实现` `if` `((originalFlags & kAccXposedHookedMethod) !== 0 && xposedIsSupported()) {``//originalFlags 是 ArtMethod->accessFlags``//kAccXposedHookedMethod 是一个特殊标志位，用于表示该方法已经被 Xposed 框架 hook``//xposedIsSupported() 检查当前运行环境是否启用了对 Xposed 框架的识别与兼容``//这不是正常 native 方法的地址，而是 Xposed Hook 结构体的指针（Xposed修改了jniCode字段，注入其自己的 hook 信息结构体）` `const hookInfo =``this``.originalMethod.jniCode;``//从 hookInfo 中提取真实方法指针``this``.hookedMethodId = hookInfo.add(2 * pointerSize).readPointer();``//使用 fetchArtMethod() 方法，从真实的 ArtMethod 指针创建一个有效的 Java 方法对象。``//之后 Frida 将 hook 的目标重定向到该真实方法，而不是被 Xposed 替换过的版本` `this``.originalMethod = fetchArtMethod(``this``.hookedMethodId, vm);``}` `const { hookedMethodId } =``this``;``//将原生方法复制了一份``const replacementMethodId = cloneArtMethod(hookedMethodId, vm);``this``.replacementMethodId = replacementMethodId;``//patchArtMethod 修改artMethod结构的函数``//replacementMethodId 被替换的新方法的artmethod指针`  `patchArtMethod(replacementMethodId, {``jniCode: impl,``//替换后的jni实现函数指针``// art method的访问标志``//移除掉一些原有的标志 kAccCriticalNative 极限优化的native方法``// kAccFastNative 快速native方法``// kAccNterpEntryPointFastPathFlag  Nterp快捷径``// kAccNative native方法``// kAccCompileDontBother 不对该方法进行AOT或JIT编译``accessFlags: ((originalFlags & ~(kAccCriticalNative \| kAccFastNative \| kAccNterpEntryPointFastPathFlag)) \| kAccNative \| kAccCompileDontBother) >>> 0,` `//设置该方法的Quick entry point``// 指向一个通用的jni桥接函数 artclasslinker提供``//用于让方法执行时 正确通过jni调用你替换进去的native函数``quickCode: api.artClassLinker.quickGenericJniTrampoline,``//设置art中的解释器入口地址``//及时方法没被jit编译 也能在解释执行时调用替换的native方法``interpreterCode: api.artInterpreterToCompiledCodeBridge``}, vm);` `// Remove kAccFastInterpreterToInterpreterInvoke and kAccSkipAccessChecks to disable use_fast_path``// in interpreter_common.h``let hookedMethodRemovedFlags = kAccFastInterpreterToInterpreterInvoke \| kAccSingleImplementation \| kAccNterpEntryPointFastPathFlag;``if` `((originalFlags & kAccNative) === 0) {``hookedMethodRemovedFlags \|= kAccSkipAccessChecks;``}` `patchArtMethod(hookedMethodId, {``accessFlags: ((originalFlags & ~(hookedMethodRemovedFlags)) \| kAccCompileDontBother) >>> 0``}, vm);` `const quickCode =``this``.originalMethod.quickCode;` `// Replace Nterp quick entrypoints with art_quick_to_interpreter_bridge to force stepping out``// of ART's next-generation interpreter and use the quick stub instead.``if` `(artNterpEntryPoint !==``null` `&& quickCode.equals(artNterpEntryPoint)) {``patchArtMethod(hookedMethodId, {``quickCode: api.artQuickToInterpreterBridge``}, vm);``}` `if` `(!isArtQuickEntrypoint(quickCode)) {``const interceptor =``new` `ArtQuickCodeInterceptor(quickCode);``interceptor.activate(vm);` `this``.interceptor = interceptor;``}` `artController.replacedMethods.set(hookedMethodId, replacementMethodId);` `notifyArtMethodHooked(hookedMethodId, vm);``}``//将已 Hook 的 ArtMethod 恢复为原始状态``revert (vm) {``//解构出当前 Hook 的方法 ID 和拦截器``const { hookedMethodId, interceptor } =``this``;``//把 originalMethod 的内容写回 hookedMethodId 对应内存` `patchArtMethod(hookedMethodId,``this``.originalMethod, vm);``//从全局中移除hookedMethodId 防止重复hook` `artController.replacedMethods.``delete``(hookedMethodId);` `if` `(interceptor !==``null``) {``interceptor.deactivate();``//清空 interceptor 引用` `this``.interceptor =``null``;``}``}` `resolveTarget (wrapper, isInstanceMethod, env, api) {``return` `this``.hookedMethodId;``}``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202506/1030887_6WA3MKGG7QCZ2TR.webp)

---

# 回复

## 回复 by 寻梦之璐 (#2)

*2025-6-28 22:49*

1

## 回复 by 破绽百出 (#3)

*2025-6-29 11:52*

>
> [寻梦之璐](https://bbs.kanxue.com/user-917635.htm)
>
>  1
>
>

哥学会这个可以去美团嘛

## 回复 by mb_mxrlvbns (#4)

*2025-6-29 13:51*

可以

## 回复 by 夜惜风雨 (#5)

*2025-6-30 16:26*

6666

## 回复 by 寻梦之璐 (#6)

*2025-6-30 22:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  破绽百出](https://bbs.kanxue.com/user-873266.htm)
>
>  哥学会这个可以去美团嘛
>
>

可以的，黄袍加身

## 回复 by 酒仙桥之虎 (#7)

*2025-6-30 22:21*

666

## 回复 by 日暮归途 (#8)

*2025-7-1 06:52*

学习学习

## 回复 by Ankeys (#9)

*2025-7-1 09:52*

666

## 回复 by git_56701jackt88 (#10)

*2025-7-1 09:54*

666666

## 回复 by LeoW丨 (#11)

*2025-7-1 15:44*

666666

## 回复 by zhangminnn (#12)

*2025-7-2 22:46*

666666

## 回复 by Cyb3r9 (#13)

*2025-7-3 14:32*

666666

## 回复 by y小白001 (#14)

*2025-7-3 18:04*

6666

## 回复 by awayawell (#15)

*2025-7-8 14:59*

666666666

## 回复 by xinghun90 (#16)

*2025-7-9 08:46*

6666666

## 回复 by GEKEZYX (#17)

*2025-7-9 09:33*

666

## 回复 by git_16837m45aka (#18)

*2025-7-9 09:40*

666

## 回复 by 丶咖啡猫丶 (#19)

*2025-7-9 10:05*

666

## 回复 by mb_aoooaosd (#20)

*2025-7-9 10:12*

牛逼

## 回复 by 带带弟弟吧 (#21)

*2025-7-9 13:26*

111

## 回复 by JWPL (#22)

*2025-7-9 13:48*

学习学习

## 回复 by jw8888 (#23)

*2025-7-9 13:50*

66666666666

## 回复 by 西埔 (#24)

*2025-7-9 17:10*

666

## 回复 by 斗转南see雪 (#25)

*2025-7-9 17:38*

666

## 回复 by SGSGsama (#26)

*2025-7-10 11:42*

666

## 回复 by hekes (#27)

*2025-7-10 11:48*

看看

## 回复 by 宛枫 (#28)

*2025-7-10 12:06*

感谢分享，学习一下

## 回复 by lbunknow (#29)

*2025-7-10 13:45*

666

## 回复 by jia jia (#30)

*2025-7-11 16:28*

1

## 回复 by 李啊啊 (#31)

*2025-7-11 17:45*

666

## 回复 by mb_tnkubkna (#32)

*2025-7-11 18:15*

111

## 回复 by mb_cbgtaveo (#33)

*2025-7-14 16:50*

6666666666666

## 回复 by mb_irhdtnzm (#34)

*2025-7-15 15:38*

p

## 回复 by Xx_gg (#35)

*2025-7-15 18:40*

666

## 回复 by lookaside (#36)

*2025-7-16 10:05*

66

## 回复 by wen55444 (#37)

*2025-7-17 01:39*

666

## 回复 by fujing (#38)

*2025-7-17 06:10*

你的帖子非常有用，感谢分享！

## 回复 by it爱好者_625041 (#39)

*2025-7-17 06:14*

666

## 回复 by mb_qqihqaoo (#40)

*2025-7-21 13:05*

66666

## 回复 by mb_iyfuxmht (#41)

*2025-7-25 00:13*

666

## 回复 by wx_插曲 (#42)

*2025-7-28 11:21*

666

## 回复 by baitongling (#43)

*2025-7-29 18:08*

666

## 回复 by frankpi (#44)

*2025-7-30 11:44*

636

## 回复 by early bird (#45)

*2025-7-31 00:33*

666

## 回复 by mb_nkjfyhkg (#46)

*2025-7-31 01:48*

Mark

## 回复 by dfJerry (#47)

*2025-8-4 11:09*

6

## 回复 by XCicada (#48)

*2025-8-4 11:15*

学习学习

## 回复 by mb_kamhgqsu (#49)

*2025-8-4 11:16*

666

## 回复 by sunburn_6 (#50)

*2025-8-6 22:33*

感谢分享

## 回复 by wx_huhu_859 (#51)

*2025-8-7 00:51*

1

## 回复 by nsec (#52)

*2025-8-7 10:21*

6666

## 回复 by GuL1ng (#53)

*2025-8-7 14:21*

6666

## 回复 by 神奇的人鱼 (#54)

*2025-8-7 14:25*

666

## 回复 by 秃顶 (#55)

*2025-8-7 14:54*

666

## 回复 by Old_Yuan (#56)

*2025-8-8 10:31*

666

## 回复 by 南飞雁 (#57)

*2025-8-8 16:10*

666

## 回复 by jw8888 (#58)

*2025-8-19 13:29*

6666666666666

## 回复 by mb_afnbxjqv (#59)

*2025-8-19 13:40*

6666

## 回复 by d43hyuh (#60)

*2025-8-19 14:19*

66

## 回复 by mb_ekhqutmo (#61)

*2025-9-15 12:03*

666

## 回复 by qqxiaobai (#62)

*2025-11-16 18:27*

666

## 回复 by mb_pesxllvn (#63)

*2025-11-16 20:04*

666

## 回复 by mb_atdqqbte (#64)

*2025-11-16 22:58*

强

## 回复 by git_21915secu05-jpg (#65)

*2025-11-17 00:21*

777

## 回复 by mb_fywsujzf (#66)

*2025-11-17 01:33*

11441

## 回复 by quanIngo (#67)

*2025-11-25 12:06*

看看什么内容

## 回复 by mb_qimctavn (#68)

*2025-11-25 13:35*

6

## 回复 by mb_benfvkcd (#69)

*2025-11-27 14:39*

666

## 回复 by mb_advzsyem (#70)

*2025-12-17 17:13*

6666

## 回复 by Va1ue (#71)

*2026-1-8 15:08*

6666

## 回复 by AYHMO (#72)

*2026-1-8 15:50*

6666

## 回复 by mb_zpkhskyr (#73)

*2026-1-8 18:34*

666

## 回复 by SomeMx (#74)

*2026-1-9 05:07*

过来瞧瞧

## 回复 by iBa0 (#75)

*2026-3-27 08:43*

111

## 回复 by huangjw (#76)

*2026-3-27 09:32*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by Sigil (#77)

*2026-3-28 11:15*

1

## 回复 by davan (#78)

*2026-3-28 16:52*

666

## 回复 by mb_yxcltfyb (#79)

*2026-3-29 03:22*

太强啦

## 回复 by 星辰北天 (#80)

*2026-3-29 19:24*

感谢分享

## 回复 by buluo533 (#81)

*2026-4-21 09:49*

6666666

## 回复 by riderjoker (#82)

*2026-4-21 14:50*

1

## 回复 by long_ (#83)

*2026-5-26 15:44*

666
