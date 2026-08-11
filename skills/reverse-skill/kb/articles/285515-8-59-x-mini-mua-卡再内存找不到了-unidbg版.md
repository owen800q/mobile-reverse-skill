---
title: '[求助]8.59 x-mini-mua  卡再内存找不到了  unidbg版'
url: https://bbs.kanxue.com/thread-285515.htm
tid: 285515
author: 小羽~
date: '2025-02-11'
tags: [Android安全, 求助, 逆向分析]
crawled_at: '2026-08-11T08:40:08+00:00'
replies: 26
---

如果注释掉这行代码memory.addHookListener(systemPropertyHook);
不hook系统属性是可以出结果但是结果会少很多。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202502/1014160_H2TN8WBW923K4Z9.webp)

如果补系统文件，就会报内存找不到，看日志是获取ro.product.brand后就找不到了

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `[``17``:``18``:``06` `562``] DEBUG [com.github.unidbg.pointer.UnidbgPointer] (UnidbgPointer:``348``) - getString pointer=RW``@0x40757860``, size=``16``, encoding=UTF-``8``, ret=ro.product.brand``[``17``:``18``:``06` `562``] DEBUG [com.github.unidbg.linux.android.SystemPropertyHook] (SystemPropertyHook$``5``:``96``) - __system_property_find key=ro.product.brand, LR=RX``@0x4028ea4c``[libtiny.so]``0x28ea4c``地址=fffe18a4长度``8``返回=[``1``,` `0``,` `0``, -``44``]String  �``地址=406c25b4长度``8``返回=[``103``,` `111``,` `111``,` `103``,` `108``,` `101``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``,` `0``]Stringgoogle` `[``17``:``18``:``06` `563``] DEBUG [com.github.unidbg.pointer.UnidbgPointer] (UnidbgPointer:``348``) - getString pointer=R``@0x406c25b4``, size=``6``, encoding=UTF-``8``, ret=google``[``17``:``18``:``06` `563``] DEBUG [com.github.unidbg.linux.android.SystemPropertyHook] (SystemPropertyHook$``5``:``109``) - __system_property_find key=ro.product.brand, pi=R``@0x406c25b0``, value=google``地址=405cbf1c长度``8``返回=[``1``,` `0``,` `0``, -``44``]String  �``地址=404f6cc0长度``8``返回=[``4``,` `0``,` `0``,` `0``]String` `[``17``:``18``:``06` `564``] DEBUG [com.github.unidbg.linux.AndroidSyscallHandler] (AndroidSyscallHandler:``308``) - futex uaddr=RW``@0x404f6cc0``[libtiny.so]``0x4f6cc0``, isPrivate=``true``, cmd=``1``, val=``0x7fffffff``, old=``0x4``, LR=RX``@0x40617934``[libc.so]``0x67934``[``17``:``18``:``06` `564``] DEBUG [com.github.unidbg.linux.AndroidSyscallHandler] (AndroidSyscallHandler:``340``) - futex FUTEX_WAKE val=``0x7fffffff``, old=``4``, task=Runnable\|Function64 address=``0x401ab2d0``, arguments=[wxw``@0xfffe1640``[libandroid.so]``0x640``,` `621541985``,` `828356434``,` `110771485``]``[``17``:``18``:``06` `564``]  WARN [com.github.unidbg.arm.AbstractARM64Emulator] (AbstractARM64Emulator$``1``:``66``) - Fetch memory failed: address=``0x165ff2dc8``, size=``1``, value=``0x0``debugger` `break` `at:` `0x165ff2dc8` `@ Runnable\|Function64 address=``0x401ab2d0``, arguments=[wxw``@0xfffe1640``[libandroid.so]``0x640``,` `621541985``,` `828356434``,` `110771485``]``>>> x0=``0x406c25b0` `x1=``0x0` `x2=``0xbffffffffffde98` `x3=``0x0` `x4=``0x0` `x5=``0x1` `x6=``0x0` `x7=``0x81` `x8=``0x165ff2dc8` `x9=``0x1f6fbb6c` `x10=``0xc` `x11=``0x80` `x12=``0x40656a80` `x13=``0xc` `x14=``0xd``>>> x15=``0x6` `x16=``0x404ed708` `x17=``0x0` `x18=``0x40742020` `x19=``0xbffffffffffe060` `x20=``0x406c25b0` `x21=``0xbfffffffffff718` `x22=``0x404ac000` `x23=``0x66011558` `x24=``0x1f6fbad4` `x25=``0x3ee8cc60` `x26=``0x3ee8cc68` `x27=``0xbffffffffffec78` `x28=``0xbfffffffffff718` `fp=``0xbffffffffffdf00``>>> q0=``0x3f800000``(``1.0``) q1=``0x3f800000``(``1.0``) q2=``0x0``(``0.0``) q3=``0x0``(``0.0``) q4=``0x80200802802008028020080280200802``(-``4``.458850023827439E-``308``, -``4``.458850023827439E-``308``) q5=``0x1000000000000000100000``(``5``.180654E-``318``,` `5``.180654E-``318``) q6=``0x0``(``0.0``) q7=``0x80200802802008028020080280200802``(-``4``.458850023827439E-``308``, -``4``.458850023827439E-``308``) q8=``0x0``(``0.0``) q9=``0x0``(``0.0``) q10=``0x0``(``0.0``) q11=``0x0``(``0.0``) q12=``0x0``(``0.0``) q13=``0x0``(``0.0``) q14=``0x0``(``0.0``) q15=``0x0``(``0.0``)``>>> q16=``0x40100401401004014010040140100401``(``4.003911019303815``,` `4.003911019303815``) q17=``0xa00aa00aa00aa00aaaaaaaaa00100010``(-``3``.7206606621968206E-``103``, -``2``.4822441395927015E-``154``) q18=``0x80200802802008028020080280200802``(-``4``.458850023827439E-``308``, -``4``.458850023827439E-``308``) q19=``0x0``(``0.0``) q20=``0x0``(``0.0``) q21=``0x0``(``0.0``) q22=``0x0``(``0.0``) q23=``0x0``(``0.0``) q24=``0x0``(``0.0``) q25=``0x0``(``0.0``) q26=``0x0``(``0.0``) q27=``0x0``(``0.0``) q28=``0x0``(``0.0``) q29=``0x0``(``0.0``) q30=``0x0``(``0.0``) q31=``0x0``(``0.0``)``LR=RX``@0x40258018``[libtiny.so]``0x258018``SP=``0xbffffffffffde70``PC=wxw``@0x165ff2dc8``nzcv: N=``0``, Z=``1``, C=``1``, V=``0``, EL0, use SP_EL0``地址=165ff2dc4长度``9``地址=165ff2dc8长度``9``地址=165ff2dc4长度``9``com.github.unidbg.arm.backend.BackendException: mem_read address=``0x165ff2dc4``, size=``60``at com.github.unidbg.arm.backend.Unicorn2Backend.mem_read(Unicorn2Backend.java:``127``)``at com.github.unidbg.arm.AbstractARM64Emulator.disassemble(AbstractARM64Emulator.java:``221``)``at com.github.unidbg.arm.AbstractARMDebugger.disassemble(AbstractARMDebugger.java:``963``)``at com.github.unidbg.arm.SimpleARM64Debugger.loop(SimpleARM64Debugger.java:``52``)``at com.github.unidbg.arm.AbstractARMDebugger.debug(AbstractARMDebugger.java:``279``)``at com.github.unidbg.arm.AbstractARM64Emulator$``1``.hook(AbstractARM64Emulator.java:``68``)``at com.github.unidbg.arm.backend.Unicorn2Backend$``9``.hook(Unicorn2Backend.java:``324``)``at com.github.unidbg.arm.backend.unicorn.Unicorn$NewHook.onMemEvent(Unicorn.java:``117``)``at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Native Method)``at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Unicorn.java:``312``)``at com.github.unidbg.arm.backend.Unicorn2Backend.emu_start(Unicorn2Backend.java:``397``)``at com.github.unidbg.AbstractEmulator.emulate(AbstractEmulator.java:``378``)``at com.github.unidbg.thread.Function64.run(Function64.java:``39``)``at com.github.unidbg.thread.MainTask.dispatch(MainTask.java:``19``)``at com.github.unidbg.thread.UniThreadDispatcher.run(UniThreadDispatcher.java:``175``)``at com.github.unidbg.thread.UniThreadDispatcher.runMainForResult(UniThreadDispatcher.java:``99``)``at com.github.unidbg.AbstractEmulator.runMainForResult(AbstractEmulator.java:``341``)``at com.github.unidbg.arm.AbstractARM64Emulator.eFunc(AbstractARM64Emulator.java:``262``)``at com.github.unidbg.Module.emulateFunction(Module.java:``163``)``at com.github.unidbg.linux.android.dvm.DvmObject.callJniMethod(DvmObject.java:``135``)``at com.github.unidbg.linux.android.dvm.DvmClass.callStaticJniMethodObject(DvmClass.java:``317``)``at com.anjuke.mobile.sign.xhs.XHSMiniMua.a(XHSMiniMua.java:``185``)``at com.anjuke.mobile.sign.xhs.XHSMiniMua.init(XHSMiniMua.java:``126``)``at com.anjuke.mobile.sign.xhs.XHSMiniMua.main(XHSMiniMua.java:``1040``)``Caused by: unicorn.UnicornException: Invalid memory read (UC_ERR_READ_UNMAPPED)` `有没有大佬一起交流` |
|-|-|

---

# 回复

## 回复 by wx_白熊 (#2)

*2025-2-12 11:11*

可以交流一下

## 回复 by 小羽~ (#3)

*2025-2-12 14:17*

>
> [wx_白熊](https://bbs.kanxue.com/user-945136.htm)
>
>  可以交流一下
>
>

你到哪一步了

## 回复 by mb_sjlmuxry (#4)

*2025-3-17 21:09*

我没注释 memory.addHookListener(systemPropertyHook); 也没看到 mini，直接结束了

## 回复 by mb_sjlmuxry (#5)

*2025-3-17 21:10*

>
> [wx_白熊](https://bbs.kanxue.com/user-945136.htm)
>
>  可以交流一下
>
>

怎么加你，交流下

## 回复 by maxcl (#6)

*2025-3-20 10:31*

public static native Object a(int i10, Object... objArr);  这个咋还原

## 回复 by 杨如画 (#7)

*2025-3-20 11:35*

少就是指纹不全,对比真机就好了,不影响其他的

## 回复 by 小羽~ (#8)

*2025-3-24 17:51*

>
> [杨如画](https://bbs.kanxue.com/user-983110.htm)
>
>  少就是指纹不全,对比真机就好了,不影响其他的
>
>

可以的大佬 已经解决了 注册设备的接口也模拟出来了，现在就差学ida来弄纯算了![image](https://bbs.kanxue.com/view/img/face/071.gif)

## 回复 by rico_wu (#9)

*2025-4-29 10:28*

佬我也在做这个，可以交流一下么，私信我wx?

## 回复 by mb_prcsxqmw (#10)

*2025-5-30 22:06*

![image](https://bbs.kanxue.com/view/img/face/006.gif)求助！！

## 回复 by wx_+5_377 (#11)

*2025-8-8 11:49*

想问下，我还原后的shield都是最后的32个16进制数和真机下抓包出来的不一样，看着像是使用某个变量给MD5哈希成32位数据后，又重编码了一下，但一直没整出来，大概是啥原因啊

-- 更新，大概猜测是对时间戳的处理，可能是用了initializeNative时的时间戳作为参数了，我再试下

## 回复 by mb_doidlnho (#12)

*2025-8-21 15:48*

大佬，我补x-mini-mua时结果直接返回null，提示缺少依赖一些系统的so文件，加进去后又报缺少一些系统函数的符号symbal的提示，这个怎么解决呀，跪求大佬指导

## 回复 by mb_wiuhlhwy (#13)

*2025-8-22 15:22*

前排学些，牛

## 回复 by mb_xgbachmn (#14)

*2025-10-14 03:05*

我也是在学习逆向，弄这个，call static jni返回的结果是空，有些迷茫，下一步该如何走了

## 回复 by mb_xgbachmn (#15)

*2025-10-14 03:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_+5_377](https://bbs.kanxue.com/user-914300.htm)
>
>  想问下，我还原后的shield都是最后的32个16进制数和真机下抓包出来的不一样，看着像是使用某个变量给MD5哈希成32位数据后，又重编码了一下，但一直没整出来，大概是啥原因啊-- 更新，大概猜测是对 ...
>
>

shiled那个我搞定了，不同时间去算，值都是一样的，如果你搞定了x-mini的，求指点

## 回复 by mark chen (#16)

*2025-11-12 21:51*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xgbachmn](https://bbs.kanxue.com/user-1032881.htm)
>
>  我也是在学习逆向，弄这个，call static jni返回的结果是空，有些迷茫，下一步该如何走了
>
>

你的解决了吗？我也遇到相同问题。也没报错，不知道该怎么处理了，刚学unidbg

## 回复 by wx_浓情淡如你 (#17)

*2025-11-28 09:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mark chen](https://bbs.kanxue.com/user-1036092.htm)
>
>  你的解决了吗？我也遇到相同问题。也没报错，不知道该怎么处理了，刚学unidbg
>
>
>

我也刚学, 能交流下吗

## 回复 by mark chen (#18)

*2025-12-15 21:01*

>
> [wx_浓情淡如你](https://bbs.kanxue.com/user-894999.htm)
>
>  我也刚学, 能交流下吗
>
>

已经弄出来了

## 回复 by mb_igwchhlt (#19)

*2025-12-21 09:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mark chen](https://bbs.kanxue.com/user-1036092.htm)
>
>  你的解决了吗？我也遇到相同问题。也没报错，不知道该怎么处理了，刚学unidbg
>
>
>

我也是 一直是null

## 回复 by mark chen (#20)

*2025-12-21 16:49*

没有初始化

## 回复 by mark chen (#21)

*2025-12-21 16:50*

没有初始化

## 回复 by mb_aiyhfydo (#22)

*2026-1-16 16:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_+5_377](https://bbs.kanxue.com/user-914300.htm)
>
>  想问下，我还原后的shield都是最后的32个16进制数和真机下抓包出来的不一样，看着像是使用某个变量给MD5哈希成32位数据后，又重编码了一下，但一直没整出来，大概是啥原因啊-- 更新，大概猜测是对 ...
>
>

我也遇到这个问题，我把抓包的所有http请求参数放到unidbg模拟生成shield，deviceId和main_hmac也加到unidbg，但是unidbg生成的shield和抓包的不一样，调xiaohongshu接口是失败的

## 回复 by mb_aiyhfydo (#23)

*2026-1-19 00:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_aiyhfydo](https://bbs.kanxue.com/user-977458.htm)
>
>  我也遇到这个问题，我把抓包的所有http请求参数放到unidbg模拟生成shield，deviceId和main_hmac也加到unidbg，但是unidbg生成的shield和抓包的不一样，调xia ...
>
>

解决了，在构造request对象时不能手动传入"xy-platform-info"请求头

Request request = new Request.Builder()

    .url("https://edith.xiaohongshu.com/api/sns/v2/user/phone/zones")

    .addHeader("host", "edith.xiaohongshu.com")

    .addHeader("xy-direction", "99")

    .................

    .addHeader("xy-common-params", "fid=&gid=xxxxxxxxx10805&holder_ctry=CN&did=70101c7ea5ea6832de8596564a775823")

    .addHeader("user-agent", "Dalvik/2.1.0 (Linux; U; Android 9; SM-S9210 Build/PQ3A.190605.10141057) Resolution/1080*1920 Version/9.11.0 Build/9110805 Device/(Samsung;SM-S9210) discover/9.11.0 NetType/Unknown")

    .addHeader("referer", "https://app.xhs.cn/")

//    .addHeader("xy-platform-info", "platform=android&build=9110805&deviceId=41b41111-2b7f-3adf-9c22-b00524b59591") // so会自动生成"xy-platform-info"，不能外部传入

    .addHeader("accept-encoding", "gzip")

    .build();

## 回复 by mb_nmyiwtzp (#24)

*2026-2-28 16:30*

有一起弄 xhs 的吗? 交流一下, 风控又严了

## 回复 by lazybulazy (#25)

*2026-3-4 16:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_aiyhfydo](https://bbs.kanxue.com/user-977458.htm)
>
>
>
>
>
>
>
>  mb_aiyhfydo
>
>
>
>  我也遇到这个问题，我把抓包的所有http请求参数放到unidbg模拟生成shield，deviceId和main_ ...
>
>

我也是这个问题，最初还以为我补环境代码的问题，试了两遍后发现应该是更新了，感谢大佬思路

## 回复 by mb_pveclrmt (#26)

*2026-4-23 19:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mark chen](https://bbs.kanxue.com/user-1036092.htm)
>  没有初始化
>

请教下怎么初始化呢

## 回复 by mb_pveclrmt (#27)

*2026-4-27 18:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_nmyiwtzp](https://bbs.kanxue.com/user-872347.htm)
>  有一起弄 xhs 的吗? 交流一下, 风控又严了
>

有群吗？我也在搞这个app,加vx: keepmoving198778
