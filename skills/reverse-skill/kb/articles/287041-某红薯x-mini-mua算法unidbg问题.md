---
title: '[求助]某红薯x-mini-mua算法unidbg问题'
url: https://bbs.kanxue.com/thread-287041.htm
tid: 287041
author: mb_prcsxqmw
date: '2025-05-30'
tags: [Android安全, 求助, 逆向分析, 协议分析, HOOK注入, 源码框架]
crawled_at: '2026-08-09T04:50:04+00:00'
replies: 126
---

已解决。

![image](https://bbs.kanxue.com/upload/attach/202509/1006229_ZR8GU8ZMRDDKPJB.webp)

---

# 回复

## 回复 by bluegatar (#2)

*2025-5-31 23:07*

贴个完整代码

## 回复 by hacker521 (#3)

*2025-6-1 02:08*

贴个完整代码

## 回复 by 思卓 (#4)

*2025-6-1 23:02*

要初始化

## 回复 by mb_sgrrhluj (#5)

*2025-6-3 17:15*

![image](https://bbs.kanxue.com/upload/attach/202506/1039076_RXCKTX9HRTABWRW.webp)

的确要初始化。。。初始化后提示
java.lang.NullPointerException: Cannot invoke "com.github.unidbg.pointer.UnidbgPointer.toIntPeer()" because "jmethodID" is null

当我Patch掉这个函数的时候 又会蹦出新的错误。。

![image](https://bbs.kanxue.com/upload/attach/202506/1039076_KZHUPES2TJWT39W.webp)

报错的地址  在so文件中对应的代码如下：

![image](https://bbs.kanxue.com/upload/attach/202506/1039076_GUF8R24PKHFC9XG.webp)

文本：

__int64 sub_18D8E4()

{

  __int64 v0; // x19

  unsigned __int64 v1; // x11

  bool v2; // cc

  __int64 v3; // x8

  __int64 v4; // x8

  unsigned int v5; // w9

  *(_QWORD *)(v0 + 3032) = *(_QWORD *)(v0 + 440);

  **(_QWORD **)(v0 + 3032) = *(_QWORD *)(v0 + 3024);

  v1 = 0x37AC138u;

  *(_QWORD *)(v0 + 3040) = *(_QWORD *)(v0 + 448);

  v2 = *(_DWORD *)(v0 + 2700) <= 6;

  v3 = 512;

  **(_QWORD **)(v0 + 808) = *(_QWORD *)(v0 + 3040);

  **(_QWORD **)(v0 + 816) = *(_QWORD *)(v0 + 3032);

  **(_QWORD **)(v0 + 824) = *(_QWORD *)(v0 + 2872);

  **(_QWORD **)(v0 + 832) = *(_QWORD *)(v0 + 2864);

  **(_QWORD **)(v0 + 840) = *(_QWORD *)(v0 + 2768);

  **(_QWORD **)(v0 + 848) = *(_QWORD *)(v0 + 2760);

  **(_QWORD **)(v0 + 856) = *(_QWORD *)(v0 + 2728);

  **(_QWORD **)(v0 + 864) = *(_QWORD *)(v0 + 2736);

  **(_QWORD **)(v0 + 872) = *(_QWORD *)(v0 + 2832);

  **(_QWORD **)(v0 + 880) = *(_QWORD *)(v0 + 2840);

  **(_QWORD **)(v0 + 888) = *(_QWORD *)(v0 + 2928);

  **(_QWORD **)(v0 + 896) = *(_QWORD *)(v0 + 2936);

  if ( v2 )

    v3 = 1296;

  if ( !v2 )

    v1 = 0x37B9D74u;

  v4 = *(__int64 *)((char *)&off_627930 + v3);

  v5 = (unsigned int)sub_17FE10 + 3488972;

  if ( v2 )

    v5 = (unsigned int)sub_187CF0 - 8572456;

  return ((__int64 (*)(void))(v4 + (int)(v5 - v1)))();

}

## 回复 by mb_sgrrhluj (#6)

*2025-6-3 17:19*

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>
>  贴个完整代码
>
>

![image](https://bbs.kanxue.com/view/img/face/006.gif)已贴

## 回复 by mb_sgrrhluj (#7)

*2025-6-3 17:19*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  贴个完整代码
>
>
>

已贴

## 回复 by mb_sgrrhluj (#8)

*2025-6-3 17:21*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  贴个完整代码
>
>
>

.

## 回复 by mb_sgrrhluj (#9)

*2025-6-3 17:37*

.

## 回复 by mb_sgrrhluj (#10)

*2025-6-3 17:38*

QQ 1969422834    V：longtime410528   欢迎大佬加我。。。。

## 回复 by 小 鲨 鱼 (#11)

*2025-6-23 16:40*

大佬解决了吗？同样的问题![image](https://bbs.kanxue.com/view/img/face/073.gif)

## 回复 by mb_sgrrhluj (#12)

*2025-6-26 12:40*

![image](https://bbs.kanxue.com/view/img/face/064.gif)感谢各位大佬指导。已经弄出来了

## 回复 by 广东小飞 (#13)

*2025-7-21 09:26*

兄弟，完整的弄出来了吗？

## 回复 by mb_prcsxqmw (#14)

*2025-9-17 21:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  广东小飞](https://bbs.kanxue.com/user-1044276.htm)
>
>  兄弟，完整的弄出来了吗？
>
>

![image](https://bbs.kanxue.com/view/img/face/001.gif)已经解决。

## 回复 by mb_pnyyaazf (#15)

*2025-9-18 01:04*

666

## 回复 by mb_uikdudgo (#16)

*2025-9-20 19:13*

同样的问题

## 回复 by wx_飞_847 (#17)

*2025-9-22 10:48*

666

## 回复 by Majh (#18)

*2025-9-22 12:37*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_xjdhrmck (#19)

*2025-9-22 14:17*

0.0

## 回复 by hale jstin (#20)

*2025-9-22 17:35*

666

## 回复 by mb_kgiaivmg (#21)

*2025-9-26 13:30*

666

## 回复 by mb_qgszoowq (#22)

*2025-9-27 19:09*

111

## 回复 by 空空的爸爸 (#23)

*2025-9-28 22:25*

11111

## 回复 by xeiyu (#24)

*2025-9-29 07:58*

666

## 回复 by logeye (#25)

*2025-9-29 17:49*

666

## 回复 by KanXue_NG (#26)

*2025-10-6 11:54*

666

## 回复 by mb_xflcgdik (#27)

*2025-10-7 09:15*

1

## 回复 by 乐枫大大 (#28)

*2025-10-15 00:05*

666

## 回复 by tubecityman (#29)

*2025-10-15 05:01*

学习下

## 回复 by @NoBody (#30)

*2025-10-15 10:48*

第三方东方时尚

## 回复 by 梨树生果 (#31)

*2025-10-17 10:52*

666

## 回复 by 赵小只 (#32)

*2025-10-22 14:35*

求一下完整代码![image](https://bbs.kanxue.com/view/img/face/088.gif)

## 回复 by mb_qqihqaoo (#33)

*2025-10-27 13:09*

63333333

## 回复 by jasonxgw (#34)

*2025-10-27 16:16*

666

## 回复 by 寻梦之璐 (#35)

*2025-10-29 22:25*

666

## 回复 by mb_ykavguun (#36)

*2025-10-29 22:45*

666

## 回复 by mb_ssnabqqf (#37)

*2025-10-30 14:14*

33

## 回复 by mark chen (#38)

*2025-10-31 09:26*

666

## 回复 by 枯藤舍 (#39)

*2025-10-31 14:28*

666

## 回复 by mb_farzbkyi (#40)

*2025-11-4 20:09*

666

## 回复 by mb_asiwnxyv (#41)

*2025-11-4 20:14*

666

## 回复 by tanqi (#42)

*2025-11-5 13:55*

66666666666![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by wx_好饿想吃肉 (#43)

*2025-11-5 14:41*

1

## 回复 by wx_key_678 (#44)

*2025-11-5 16:03*

666

## 回复 by 豆浆与油条 (#45)

*2025-11-11 09:26*

66666

## 回复 by 贪欲. (#46)

*2025-11-11 10:27*

666

## 回复 by mb_cqcrdwgm (#47)

*2025-11-11 10:35*

666

## 回复 by 喜欢就去抢啊 (#48)

*2025-11-11 13:10*

感谢分享

## 回复 by mb_sldlxhzw (#49)

*2025-11-11 13:23*

666

## 回复 by mark chen (#50)

*2025-11-12 22:21*

你好，大佬，我使用unidbg模拟调用libtiny.so,在补完所有so之后，尝试调用方法，直接返回了null,刚学习unidbg不知道后续该怎么处理了，麻烦指教一下，谢谢。

## 回复 by git_56402Syy040316 (#51)

*2025-11-19 17:30*

1

## 回复 by 不再后悔 (#52)

*2025-11-20 13:12*

666

## 回复 by mb_apynwbms (#53)

*2025-11-28 11:01*

666

## 回复 by junday (#54)

*2025-12-1 02:08*

666

## 回复 by 列子御风 (#55)

*2025-12-1 15:29*

666

## 回复 by wen55444 (#56)

*2025-12-5 20:23*

666

## 回复 by smart_ql (#57)

*2025-12-10 19:02*

来看看

## 回复 by wx_一叶舟 (#58)

*2025-12-16 19:38*

666

## 回复 by mb_uikdudgo (#59)

*2025-12-19 12:45*

1111

## 回复 by mb_aiyhfydo (#60)

*2025-12-27 18:17*

666

## 回复 by APT_华生 (#61)

*2026-1-6 11:42*

66

## 回复 by mb_zqebrrja (#62)

*2026-1-15 16:26*

666

## 回复 by wx_意境_248 (#63)

*2026-1-15 16:32*

111

## 回复 by Migc (#64)

*2026-1-16 11:18*

666

## 回复 by mb_npsajqlx (#65)

*2026-1-19 14:37*

6

## 回复 by mb_uzmffdbw (#66)

*2026-1-23 13:35*

666

## 回复 by mb_idiqaklm (#67)

*2026-1-25 23:18*

学习

## 回复 by mb_qgeepiru (#68)

*2026-1-26 14:15*

666

## 回复 by johnwas (#69)

*2026-2-2 18:14*

666

## 回复 by mb_cafsqqjq (#70)

*2026-2-5 00:31*

66666

## 回复 by wx_白鸟之诗 (#71)

*2026-2-5 09:30*

6666

## 回复 by zhanbinbin (#72)

*2026-2-5 17:22*

学习学习

## 回复 by 王三石 (#73)

*2026-2-5 22:16*

厉害

## 回复 by mb_fglogyec (#74)

*2026-2-9 14:22*

7777

## 回复 by mb_euphpkii (#75)

*2026-2-16 20:07*

666

## 回复 by mb_ilyviizj (#76)

*2026-2-26 09:25*

111

## 回复 by 小明的爱 (#77)

*2026-2-26 12:06*

看一下

## 回复 by mb_cbgtaveo (#78)

*2026-2-26 13:53*

66666

## 回复 by mb_hfbquwgl (#79)

*2026-2-26 21:09*

666666

## 回复 by mb_onyauvcf (#80)

*2026-3-3 16:14*

支持一下

## 回复 by ID蝴蝶 (#81)

*2026-3-3 16:28*

6666

## 回复 by myios (#82)

*2026-3-3 20:09*

666

## 回复 by 开胃小菜Wx (#83)

*2026-3-4 15:47*

666

## 回复 by mb_ugryjzdr (#84)

*2026-3-5 12:00*

66

## 回复 by mb_uikdudgo (#85)

*2026-3-5 14:12*

111

## 回复 by jaefern (#86)

*2026-3-5 15:54*

666

## 回复 by mb_ncfbmciq (#87)

*2026-3-6 00:12*

666

## 回复 by sunburn_6 (#88)

*2026-3-6 06:26*

什么情况

## 回复 by mb_gqzoivfx (#89)

*2026-3-6 19:54*

666

## 回复 by 兰小娟 (#90)

*2026-3-9 09:21*

666666666

## 回复 by mb_kmapyxje (#91)

*2026-3-9 21:03*

666

## 回复 by 外交 (#92)

*2026-3-9 21:08*

666

## 回复 by mb_ybvqgbkl (#93)

*2026-3-10 15:55*

5666

## 回复 by mb_nmyiwtzp (#94)

*2026-3-10 15:57*

1

## 回复 by 无情铁手 (#95)

*2026-3-11 15:45*

666

## 回复 by git_73766huu899283-beep (#96)

*2026-3-17 15:27*

123

## 回复 by mb_qyqxxuee (#97)

*2026-3-25 21:35*

3

## 回复 by mb_nydrrooh (#98)

*2026-3-27 17:05*

666

## 回复 by CheRevir (#99)

*2026-3-27 17:41*

666

## 回复 by mb_euhyowpw (#100)

*2026-3-27 17:42*

666

## 回复 by mb_pzprixmz (#101)

*2026-3-31 23:37*

666

## 回复 by mb_wzynadof (#102)

*2026-4-20 10:32*

ss

## 回复 by mb_ehrbohcl (#103)

*2026-4-21 16:20*

666

## 回复 by mb_pjqwrjje (#104)

*2026-4-22 09:48*

333

## 回复 by mb_pveclrmt (#105)

*2026-4-24 14:02*

666

## 回复 by 西瓜帅 (#106)

*2026-4-25 21:22*

11

## 回复 by Xnxin (#107)

*2026-4-26 06:09*

666

## 回复 by mb_pveclrmt (#108)

*2026-4-28 00:17*

大佬门，我也碰到这个情况了，有谁能解惑一下吗？谢谢
false, java.lang.Float@662b4c69, false], 6) => java.lang.Float@662b4c69 was called from RX@0x400ebbf0[libtiny.so]0xebbf0
[00:12:07 240]  WARN [com.github.unidbg.linux.ARM64SyscallHandler] (ARM64SyscallHandler:412) - handleInterrupt intno=2, NR=-130096, svcNumber=0x134, PC=unidbg@0xfffe03d4, LR=RX@0x40258784[libtiny.so]0x258784, syscall=null
java.lang.NullPointerException
        at com.github.unidbg.linux.android.dvm.DalvikVM64$53.handle(DalvikVM64.java:945)
        at com.github.unidbg.linux.ARM64SyscallHandler.hook(ARM64SyscallHandler.java:121)
        at com.github.unidbg.arm.backend.UnicornBackend$11.hook(UnicornBackend.java:345)
        at unicorn.Unicorn$NewHook.onInterrupt(Unicorn.java:128)
        at unicorn.Unicorn.emu_start(Native Method)
        at com.github.unidbg.arm.backend.UnicornBackend.emu_start(UnicornBackend.java:376)
        at com.github.unidbg.AbstractEmulator.emulate(AbstractEmulator.java:378)

## 回复 by mb_ysikfhxt (#109)

*2026-4-28 08:46*

111

## 回复 by Evan_422 (#110)

*2026-5-9 14:10*

666

## 回复 by mb_dsiazahl (#111)

*2026-5-27 08:04*

6666

## 回复 by 086Love (#112)

*2026-5-27 09:14*

看看

## 回复 by mb_lfwgtxdb (#113)

*2026-5-29 17:04*

666

## 回复 by Freax (#114)

*2026-5-29 17:50*

1

## 回复 by likely (#115)

*2026-6-4 19:23*

666

## 回复 by 小子xz (#116)

*2026-6-16 13:23*

666

## 回复 by mb_vxufgfcw (#117)

*2026-6-22 10:50*

666666

## 回复 by AyonA333 (#118)

*2026-6-25 13:44*

666

## 回复 by ldz666 (#119)

*2026-7-1 10:17*

666

## 回复 by xautzbl (#120)

*2026-7-1 15:27*

666

## 回复 by wx_L_ (#121)

*2026-7-7 15:57*

1

## 回复 by 白毅 (#122)

*2026-7-8 03:28*

厉害

## 回复 by jayce.1 (#123)

*2026-7-10 10:17*

1

## 回复 by mb_izvatudf (#124)

*2026-7-10 23:15*

6666

## 回复 by sunburn_6 (#125)

*2026-7-13 08:59*

666

## 回复 by git_54107yeweilin666 (#126)

*2026-7-29 16:10*

666

## 回复 by wx_Endy Zhang (#127)

*2026-7-30 01:11*

1
