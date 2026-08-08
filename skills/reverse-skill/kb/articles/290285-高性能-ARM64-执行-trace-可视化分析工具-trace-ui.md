---
title: '[原创]高性能 ARM64 执行 trace 可视化分析工具 —— trace-ui'
url: https://bbs.kanxue.com/thread-290285.htm
tid: 290285
author: j01y
date: '2026-03-12'
tags: [Android安全, 原创, 工具脚本, 协议分析, 逆向分析]
crawled_at: '2026-08-08T10:20:00+00:00'
replies: 124
---

# 写在前面

 上一篇文章《[ARM64 动态指令 trace 离线向后切片分析器 —— trace-slice](https://bbs.kanxue.com/thread-290217.htm)》介绍了三天前开发好的向后切片分析器，现在把今天刚开发完工的trace-ui也开源吧

实在是每次对着010editor分析trace日志看到眼花，待业这么久没上班正好有时间，开发个界面友好的工具给自己用。

从零开发工具不容易，还得自费花钱买AI，熬了几个通宵现在总算完工，其实也有想要掖着藏着不开源，或者想办法换点生活费啥的，但盲猜这种工具几乎没有什么付费意愿，既然没得吃那就掀桌子吧

主要参考了看雪大佬[krash](https://bbs.kanxue.com/thread-273055.htm)和[无名侠](https://mp.weixin.qq.com/s/bGUm_npFVLPA2cvg5FcneA)的文章中实现的工具功能点和ui界面图片，照虎画猫瞎琢磨开发的，市面上这种类型的工具不多，界面美观功能好用的也没人开源。

*ps:开发仓促，完工只是简单测试了下各个功能点，难免有些功能可能会有错误或者bug，理解万岁*

# Trace UI

项目地址：[trace-ui](https://github.com/imj01y/trace-ui)

trace-ui是一款高性能 ARM64 执行 trace 可视化分析工具。基于 Tauri 2 + React 构建的桌面应用，专为安全研究员设计，支持千万行或亿行级大规模 trace 的流畅浏览、函数调用树折叠、反向污点追踪、内存/寄存器实时查看等功能。

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_295PW3UXD7MVW32.webp)

>
> 当前支持 [unidbg](https://github.com/zhkl0228/unidbg) 输出的 ARM64 指令级 trace。
>
>
>

unidbg的日志格式我增加了计算所有内存读取和写入指令的目标绝对地址，所以大家在使用前需要对uinidbg中打印这些信息，否则格式不太一样可能造成bug，修改点位于文件：`src/main/java/com/github/unidbg/AssemblyCodeDumper.java`的`hook`方法中，这样在内存读写的指令时打印的格式是这样的：

- 内存读

```python
[07:23:05 407][libtiny.so 0x6fc114] [295a69b8] 0x406fc114: "ldr w9, [x17, w9, uxtw #2]" ; mem[READ] abs=0x416885f0 x17=0x416885d4 w9=0x7 => w9=0x88bd0
\```

- 内存写

```python
[07:23:05 408][libtiny.so 0x6f87ac] [69692838] 0x406f87ac: "strb w9, [x11, x8]" ; mem[WRITE] abs=0x410c8bd0 w9=0x63 x11=0x41040000 x8=0x88bd0 => w9=0x63
\```

abs是内存的绝对地址

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/905838_JNDDF984C4FTRHA.webp)

AssemblyCodeDumper.java的文件我放到项目里了，大家替换到自己的unidbg中即可

### 调用树折叠

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/905838_D4FHEV79AEZ25Y7.webp)

### 反向污点追踪（Taint Analysis）

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/905838_7DPMYAFZY9TDDXH.webp)

**两种查看模式：**

- **过滤模式（Filter）** — 仅显示与污点相关的行，大幅缩减视图

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/905838_M7Y5ZNK64MDRGWT.webp)

- **高亮模式（Highlight）** — 显示全部行，污点相关行以颜色高亮

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_Y65M5HFNYFE5BHS.webp)

### 寄存器面板

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_GEC7FXR8X4A58A7.webp)

### 内存面板

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_DA3P3JG4DXTNETR.webp)

### 多窗口与浮动面板

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_WWFBE8R22ACDQTA.webp)

### DEF/USE 箭头连线

 ![image](https://bbs.kanxue.com/upload/attach/202603/905838_YWN533G7RJQFF5E.webp)

### 高亮与注释

 ![图片描述](https://bbs.kanxue.com/upload/attach/202603/905838_J6HQSWGSDTN4HJX.webp)

上传的附件：
- trace-ui.exe

（11.28MB，32次下载）
- AssemblyCodeDumper.java

（10.29kb，37次下载）

---

# 回复

## 回复 by Imxz (#2)

*2026-3-12 15:30*

tql

## 回复 by wx_好饿想吃肉 (#3)

*2026-3-12 15:40*

66666

## 回复 by artake (#4)

*2026-3-12 15:42*

888

## 回复 by wx_不愿 (#5)

*2026-3-12 15:44*

sql

## 回复 by artake (#6)

*2026-3-12 15:46*

大佬trace用的是哪个工具

## 回复 by 夜惜风雨 (#7)

*2026-3-12 15:46*

666666

## 回复 by mb_okavlwzx (#8)

*2026-3-12 15:48*

666

## 回复 by mb_mlyojneh (#9)

*2026-3-12 15:50*

感谢分享

## 回复 by mb_ykavguun (#10)

*2026-3-12 15:55*

1

## 回复 by xxjj678 (#11)

*2026-3-12 15:59*

666

## 回复 by wx_插曲 (#12)

*2026-3-12 15:59*

6

## 回复 by Noguess9 (#13)

*2026-3-12 16:05*

11

## 回复 by mb_ldbucrik (#14)

*2026-3-12 16:07*

向大佬学习

## 回复 by 九黎 (#15)

*2026-3-12 16:20*

6666

## 回复 by mJqalJqN (#16)

*2026-3-12 16:28*

1

## 回复 by mb_pesxllvn (#17)

*2026-3-12 16:56*

6

## 回复 by didiid (#18)

*2026-3-12 17:01*

666

## 回复 by mb_tjsboqui (#19)

*2026-3-12 17:03*

666

## 回复 by mb_tjsboqui (#20)

*2026-3-12 17:04*

666

## 回复 by mb_tjsboqui (#21)

*2026-3-12 17:04*

666

## 回复 by Loopher (#22)

*2026-3-12 17:11*

可以可以,很强

## 回复 by long_ (#23)

*2026-3-12 17:18*

666

## 回复 by tjytjy (#24)

*2026-3-12 17:43*

666

## 回复 by jyotidwi (#25)

*2026-3-12 17:54*

666

## 回复 by PangBai (#26)

*2026-3-12 18:10*

999

## 回复 by mb_ybvqgbkl (#27)

*2026-3-12 18:18*

666666

## 回复 by kingking888 (#28)

*2026-3-12 20:44*

666

## 回复 by 温泉划水鱼 (#29)

*2026-3-12 20:45*

强

## 回复 by 温泉划水鱼 (#30)

*2026-3-12 20:46*

开源促进进化，我来给你加点料

## 回复 by guijingwen (#31)

*2026-3-12 21:43*

66

## 回复 by mb_mfjsranl (#32)

*2026-3-12 22:02*

tql

## 回复 by git_75734chatgptbina-crypto (#33)

*2026-3-12 22:16*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by git_59012devamd-coder (#34)

*2026-3-12 22:17*

1111111111

## 回复 by 一拳揍哭你 (#35)

*2026-3-12 23:43*

666

## 回复 by j01y (#36)

*2026-3-12 23:57*

>
> [artake](https://bbs.kanxue.com/user-409365.htm)
>  大佬trace用的是哪个工具
>

现在还在用unidbg，暂时还没有自己的trace工具![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by j01y (#37)

*2026-3-13 00:21*

要不然来一起维护仓库？

## 回复 by XCicada (#38)

*2026-3-13 01:43*

666

## 回复 by 破客 (#39)

*2026-3-13 07:37*

666

## 回复 by mb_npsajqlx (#40)

*2026-3-13 10:00*

666

## 回复 by fjqisba (#41)

*2026-3-13 10:27*

哎，AI写的界面都挺丑的

## 回复 by mb_fidppcok (#42)

*2026-3-13 10:40*

66666

## 回复 by mb_ghcouuzx (#43)

*2026-3-13 10:42*

看看看

## 回复 by mb_pmgifpme (#44)

*2026-3-13 11:16*

1

## 回复 by Mr.He (#45)

*2026-3-13 11:36*

6666

## 回复 by mb_cbgtaveo (#46)

*2026-3-13 14:28*

6666

## 回复 by mb_euhyowpw (#47)

*2026-3-13 16:10*

555

## 回复 by @NoBody (#48)

*2026-3-13 16:31*

楼主做的很好，不过我自己也研究开发了一套非模拟执行的静态jit工具，可以跟踪程序起始到结束几乎所有函数和内存堆读写的数据，而损耗小于50%，如果是模拟执行，速度可能慢100倍，而且只能跟踪单个线程的某个函数。楼主的这套UI非常好，如果用来做后处理效果肯定非常好。

## 回复 by wx_。。。。_455 (#49)

*2026-3-13 16:43*

大佬太强了

## 回复 by 林懋 (#50)

*2026-3-13 19:51*

6

## 回复 by 铭天星 (#51)

*2026-3-13 20:05*

666

## 回复 by mb_ysikfhxt (#52)

*2026-3-13 21:27*

666

## 回复 by wx_huhu_859 (#53)

*2026-3-13 21:42*

11

## 回复 by mb_axzjntyl (#54)

*2026-3-14 09:57*

666

## 回复 by Zepp7289 (#55)

*2026-3-14 12:49*

正需要这种工具，拿文本编辑器看trace真的头秃，感谢大佬

## 回复 by Zepp7289 (#56)

*2026-3-14 12:53*

顺便建议加点mcp接口，让ai来分析trace，hhhh

## 回复 by xianhuimin (#57)

*2026-3-14 13:07*

感谢分享

## 回复 by mb_qimctavn (#58)

*2026-3-14 14:41*

6

## 回复 by maxcl (#59)

*2026-3-14 15:20*

6666

## 回复 by wx_白鸟之诗 (#60)

*2026-3-14 20:42*

6666666666

## 回复 by myios (#61)

*2026-3-14 20:53*

666

## 回复 by wx_A哦 (#62)

*2026-3-14 21:33*

666

## 回复 by pingsky (#63)

*2026-3-15 11:01*

66666

## 回复 by jw8888 (#64)

*2026-3-15 11:12*

1111111111

## 回复 by Vengeance (#65)

*2026-3-15 15:30*

666

## 回复 by jdong (#66)

*2026-3-15 15:49*

666

## 回复 by mr2222 (#67)

*2026-3-15 18:33*

666

## 回复 by Layer1 (#68)

*2026-3-17 08:49*

666

## 回复 by huangjw (#69)

*2026-3-17 09:08*

火钳刘明

## 回复 by dob_C (#70)

*2026-3-17 11:06*

感谢分享

## 回复 by iBa0 (#71)

*2026-3-17 11:22*

1111

## 回复 by AndroidDev (#72)

*2026-3-17 15:32*

学习学习

## 回复 by mb_irhdtnzm (#73)

*2026-3-17 16:58*

e

## 回复 by 枯藤舍 (#74)

*2026-3-18 17:29*

666

## 回复 by mb_shzsxtje (#75)

*2026-3-20 11:10*

666

## 回复 by 不具名的悲伤 (#76)

*2026-3-20 14:06*

6

## 回复 by asuralove (#77)

*2026-3-21 16:34*

666

## 回复 by 拍拖 (#78)

*2026-3-23 16:27*

感谢分享

## 回复 by k4y0z (#79)

*2026-3-23 17:33*

666

## 回复 by 4Chan (#80)

*2026-3-23 17:43*

666

## 回复 by j01y (#81)

*2026-3-23 22:08*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  Zepp7289](https://bbs.kanxue.com/user-993285.htm)
>  顺便建议加点mcp接口，让ai来分析trace，hhhh
>

今天加上mcp咯

## 回复 by mb_stdlrcgp (#82)

*2026-3-29 10:20*

6666

## 回复 by 星辰北天 (#83)

*2026-3-29 17:08*

大佬666

## 回复 by Oo风之恋oO (#84)

*2026-4-10 17:32*

用什么去trace了

## 回复 by fengvmu (#85)

*2026-4-20 20:55*

6

## 回复 by qiusuper (#86)

*2026-4-20 21:07*

11111111

## 回复 by git_66835diako98 (#87)

*2026-4-22 09:36*

6666

## 回复 by git_66835diako98 (#88)

*2026-4-22 09:36*

6666

## 回复 by git_66835diako98 (#89)

*2026-4-22 09:37*

6666

## 回复 by tonykros (#90)

*2026-4-22 09:40*

666

## 回复 by mb_lfwgtxdb (#91)

*2026-4-23 10:59*

感谢大佬的开源

## 回复 by mb_ffsfxcfz (#92)

*2026-4-25 16:49*

大佬trace用的是哪个工具

## 回复 by FMNS (#93)

*2026-4-26 16:14*

6666

## 回复 by mb_bzkmcyjt (#94)

*2026-4-26 20:57*

666

## 回复 by mb_odjbvqwf (#95)

*2026-4-27 19:57*

666

## 回复 by mb_rfeucrmf (#96)

*2026-4-28 12:24*

666

## 回复 by mb_luumktry (#97)

*2026-4-30 17:26*

太牛了

## 回复 by niama (#98)

*2026-5-1 17:26*

666

## 回复 by mb_anbthlub (#99)

*2026-5-3 19:58*

66666

## 回复 by 寻梦之璐 (#100)

*2026-5-5 22:44*

666

## 回复 by 9527vv7 (#101)

*2026-5-6 19:39*

1

## 回复 by mb_eumnbkwy (#102)

*2026-5-8 14:54*

看看

## 回复 by logeye (#103)

*2026-5-8 15:24*

666

## 回复 by mb_etrbkelx (#104)

*2026-5-21 11:07*

666666

## 回复 by mb_gatolgsc (#105)

*2026-5-22 02:54*

666

## 回复 by mb_rndpmawh (#106)

*2026-5-22 09:00*

学习

## 回复 by frankpi (#107)

*2026-5-22 09:26*

666

## 回复 by mb_rirvdrlh (#108)

*2026-5-23 01:11*

6666

## 回复 by maomaolk (#109)

*2026-5-29 11:33*

666

## 回复 by mb_oqmfwxcf (#110)

*2026-6-2 01:42*

trace-ui开源助力ARM64指令分析，为Android????

## 回复 by merryfish (#111)

*2026-6-2 03:04*

thanks very much

## 回复 by 小尘0000 (#112)

*2026-6-3 00:19*

666

## 回复 by mb_paopxhtx (#113)

*2026-6-22 22:31*

我瞧瞧

## 回复 by 中文fjja (#114)

*2026-6-23 10:09*

感谢分享

## 回复 by mb_mkwbfjsm (#115)

*2026-6-24 00:18*

666

## 回复 by Evangeliner (#116)

*2026-6-24 16:33*

666

## 回复 by johnwas (#117)

*2026-6-25 13:16*

666

## 回复 by yuanyouran (#118)

*2026-6-25 14:30*

感谢分享

## 回复 by simpleness (#119)

*2026-7-16 17:23*

6

## 回复 by mb_xultgqpf (#120)

*2026-7-19 16:05*

这位开发者真是太赞了！开源trace-ui这么好的工具，真是造福了整个安全研究社区。看到他为了开发这个工具付出了那么多心血，特别是还参考了看雪大佬的工具功能点和界面，真是让人敬佩。

## 回复 by Midsw (#121)

*2026-7-19 17:06*

666666666

## 回复 by mb_nuomemmo (#122)

*2026-7-24 16:02*

作者开源trace-ui的行为真是值得赞赏！这种分享精神不仅帮助了他人，也促进了技术社区的发展。工具的功能强大，界面友好，解决了实际问题。希望未来能继续看到更多类似的开源项目，共同推动技术进步！

## 回复 by mb_wjytplsl (#123)

*2026-7-25 10:03*

666

## 回复 by mb_oxqwhbqt (#124)

*2026-7-28 16:01*

这个工具看起来功能强大，界面美观，开源精神值得赞赏！虽然开发不易，但分享出来造福更多人，非常值得支持。希望社区能多试用并提出反馈，帮助项目更完善。

## 回复 by 钟白 (#125)

![image](https://bbs.kanxue.com/view/img/face/013.gif)
