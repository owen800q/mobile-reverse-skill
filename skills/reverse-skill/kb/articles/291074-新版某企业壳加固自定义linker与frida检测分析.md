---
title: '[原创]新版某企业壳加固自定义linker与frida检测分析'
url: https://bbs.kanxue.com/thread-291074.htm
tid: 291074
author: 乐子人
date: '2026-05-01'
tags: [Android安全, 原创, 逆向分析, NDK分析, 混淆加固, 脱壳反混淆]
crawled_at: '2026-07-31T15:08:26+08:00'
replies: 195
---

## 0.前言

昨天发了某企业壳的逆向分析，评论区有人说不是最新版，于是找了一个最新版的bb加固，样本是moutai。花了3个小时重新分析了一下，总结以下新增的点。

上一篇[某企业壳逆向分析——从过检测到dex代码抽取还原](https://bbs.kanxue.com/thread-291069-1.htm)

## 1.自定义linker

新版加入了自定义linker so壳，相较于旧版本强了一些。

首先通过maps文件定位到内存中的so，然后通过pread读取加密的数据：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_DG495A5F7NMD759.webp)

根据解密出的配置文件，mmap出一段内存，用于复制真实的so的rx和rw段：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_K3QYCBQP9RRUG65.webp)

第一次mmap出的是rx段，对elf头进行rc4解密，然后对剩余部分进行简单的异或解密：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_YUSA9Z73WEVZA92.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_EEJST6ZTFCTR5FW.webp)

然后再次mmap出rw段，用异或解密。

由于这个so壳没有将elfheader和program header，dynamic header拆分，解密完后在内存中就是一个完整的elf，我们直接dump下来即可：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_4TKZ6XDDDDN574W.webp)

剩下的部分就是常规的prelink，重定位，执行init_array等操作，不再赘述。

dump后的so可以直接被ida打开，不需要手动修复：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_C7HXW9MURYF8P6P.webp)

## 2.frida检测加强

简单看了一下具体内容，和之前的版本基本一致，还是走统一的造crash退出函数：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_9N5XZVENVDRS8RN.webp)

并且异常id和之前的一致，比如检测frida依然是256，检测root依然是1：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_RV6TB8WAQM97PKJ.webp)

dex壳部分和之前的版本一致，使用上篇文章的代码可以直接把代码抽取还原：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_SHXWWUHT4JY8J4P.webp)

这里主要看看新增了哪些frida检测

### 2.1 编译特征检测

上个版本检查了java-bridge的三个特征，这个版本检查了更多的编译特征：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_SRU5MJ8JT3CK22W.webp)

- ./lib/android
- art::JavaVMExt::AddGlobalRef
- art::ClassLinker::VisitClassLoaders
- f3 03 02 aa f4 03 01 2a f5 03 00 aa ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?4 ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?4 e0 03 15 aa
- f4 4f 04 a9 fd 7b 05 a9 fd 43 01 91 ff c3 04 d1 ?? ?? ?? ?? ?? ?? ?? ?? f4 03 02 aa
- fd c3 00 91 f3 03 03 aa f4 03 02 aa f5 03 01 aa f6 03 00 aa ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?4 ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?4 e4 23 00 91.
- /subprojects/frida

前三个依然是frida-java-bridge的特征。

中间三个是frida自身用来定位dlopen时的匹配特征码，被当做常量编译进了frida的so里，也成了frida的特征：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_DCN9E2GSGQR96Q3.webp)

具体可以查看gumandorid.c

在ida中，确实可以看到对应的字符串在常量区：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_7CQ9YF4RHJQ2CDA.webp)

最后一个字符串/subprojects/frida应该是编译的项目路径，被打包进so了。

### 2.2 dbus

和之前版本一致：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_23WRP6PGJCMEJY6.webp)

从20000端口检查到30000

### 2.3 检查__dl_rtld_db_dlactivity

这是frida 16.8之后的特征，会模仿调试器的做法，hook linker的__dl_rtld_db_dlactivity。

在调试状态下，该符号的会被写入brk0,用来通知调试器有新的so被加载。

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_P95DGGW4WDKTU4G.webp)

非调试状态下，该符号是nop + ret指令。

frida在gum_hook_rtld_notifier 里也实现了类似的逻辑用来监测新so的加载：

```python
static void
gum_hook_rtld_notifier (const GumRtldNotifierDetails * details, ...) {
    gpointer impl = details->location;  // r_brk 的地址

    // ARM64: 跳过开头的 BRK 指令（如果有的话）
    first_instruction = gum_arm64_reader_disassemble_instruction_at(impl);
    if (first_instruction->id == ARM64_INS_BRK)
        offset = first_instruction->size;

    // 创建 probe listener（不修改函数行为，只是在入口处插桩）
    *handler = gum_make_probe_listener(
        gum_module_registry_on_rtld_notification, NULL, NULL);

    // 用 Interceptor 在 r_brk 地址处 attach
    gum_interceptor_attach(gum_rtld_interceptor,
                           impl + offset,
                           *handler,
                           NULL,
                           GUM_ATTACH_FLAGS_UNIGNORABLE);
}
```

只不过frida使用inline hook把这个地方hook了。

所以具体检测逻辑为：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_W3TVWRWEVZH3SP6.webp)

先在maps里定位该符号所在的段，检查是否有可写权限。如果有，读取第二条指令，检查是否为ret：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_DNPKF2SSW4PMCUG.webp)

0xd65f03c0为ret指令的机器码。

如果不是ret指令，则说明被篡改了，为高版本frida的特征。

### 2.4 检测frida-gadget

frida-gadget一般会有对应的frida-gadget-config.so加载到内存。这个壳子通过检查*config.so来检测frida-gadget:

首先打开maps，对于所有的A.so文件，尝试openat A.config.so:

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_6PTGW5Z5XCB2SXU.webp)

如果访问成功，检查大小是否小于10kb:

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_FANXEYP824R98ZK.webp)

写过frida-gadget的都知道，config.so其实只是一个json配置文件，很小。

然后检查config.so里是否存在interaciton字符串：

 ![image](https://bbs.kanxue.com/upload/attach/202605/872365_FAVEG5BBGJ85UWM.webp)

完全是针对frida-gadget的检测了。

```python
{
 "interaction":{
       "type":"script",
        "path":"/data/local/tmp/hook.js" //frida 脚本
    }
}
```

如果四种检测有一个命中，则认为检测到了frida，走256号异常，造crash退出。

以上就是最新版某帮加固企业版全部的frida检测逻辑了，其实也没有什么神秘的。

## 3. 总结

其他部分该加固和之前一样。最新版只是加了一个非常简单的自定义linker，通常的自定义linker会将elf文件拆开，这个加固在内存中出现了完整的elf文件，是一个硬伤。

检测部分整体框架和以前的一样，只是多了些检测。

frida的检测手段有创新，摒弃了常规的检测。

dex代码抽取没有变化，和之前的逻辑一样，使用之前的代码可以完全还原。

总体来说难度一般，主要是壳子比较弱，脱了后检测点就很容易绕过。

---

# 回复

## 回复 by mb_ysegxpmv (#2)

*2026-5-1 16:44*

牛批啊，学习了

## 回复 by pexillove (#3)

*2026-5-1 16:52*

tql

## 回复 by mb_ldbucrik (#4)

*2026-5-1 17:00*

感谢分享

## 回复 by ClPrada (#5)

*2026-5-1 18:10*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ykavguun (#6)

*2026-5-1 18:24*

tql

## 回复 by alds (#7)

*2026-5-1 19:29*

6

## 回复 by 东方玻璃 (#8)

*2026-5-1 19:45*

强强强![image](https://bbs.kanxue.com/view/img/face/079.gif)佬有空可以逆下ijm企业版,比如电信app和szzc,bb+ijm通杀很多app了![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 乐子人 (#9)

*2026-5-1 19:49*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>  强强强[em_079]佬有空可以逆下ijm企业版,比如电信app和szzc,bb+ijm通杀很多app了[em_065]
>

好

## 回复 by mb_cfjwplfo (#10)

*2026-5-1 19:55*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>  强强强[em_079]佬有空可以逆下ijm企业版,比如电信app和szzc,bb+ijm通杀很多app了[em_065]
>

在3小时内这么快分析并找到检测点，有什么好思路经验吗

## 回复 by 乐子人 (#11)

*2026-5-1 19:57*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  在3小时内这么快分析并找到检测点，有什么好思路经验吗
>

因为和旧版本差不多（）就加了个自定义linker，还是最简单的那种

## 回复 by mb_cfjwplfo (#12)

*2026-5-1 20:14*

>
> [乐子人](https://bbs.kanxue.com/user-872365.htm)
>  因为和旧版本差不多（）就加了个自定义linker，还是最简单的那种
>

大佬收徒吗

## 回复 by mb_wdhsjycl (#13)

*2026-5-1 20:35*

感谢分享

## 回复 by 苦瓜tim (#14)

*2026-5-1 21:04*

大佬牛逼，有空可以看一下易盾的加固，自定义linker，感觉比bb难，app可以是小鹏汽车

## 回复 by 乐子人 (#15)

*2026-5-1 21:11*

>
> [苦瓜tim](https://bbs.kanxue.com/user-826381.htm)
>  大佬牛逼，有空可以看一下易盾的加固，自定义linker，感觉比bb难，app可以是小鹏汽车
>

易盾的三年前看过了，看我的历史文章

## 回复 by Zepp7289 (#16)

*2026-5-1 22:01*

tql

## 回复 by mb_dmryhnwz (#17)

*2026-5-2 00:16*

66

## 回复 by GEKEZYX (#18)

*2026-5-2 01:20*

666

## 回复 by SomeMx (#19)

*2026-5-2 07:28*

学习

## 回复 by mb_ysikfhxt (#20)

*2026-5-2 09:29*

111

## 回复 by koflfy (#21)

*2026-5-2 11:21*

厉害了乐哥。

## 回复 by wx_插曲 (#22)

*2026-5-2 12:03*

厉害了 乐哥

## 回复 by mb_kylehnha (#23)

*2026-5-2 13:05*

很棒，我要学习

## 回复 by medmi (#24)

*2026-5-2 16:40*

牛逼

## 回复 by tonykros (#25)

*2026-5-2 23:19*

牛逼

## 回复 by ulong9527 (#26)

*2026-5-3 01:20*

6

## 回复 by 啥也不会2 (#27)

*2026-5-3 11:13*

牛逼

## 回复 by dsr000 (#28)

*2026-5-3 11:30*

666

## 回复 by 笑对VS人生 (#29)

*2026-5-3 11:38*

hook脚本搞出来通杀

## 回复 by Ankeys (#30)

*2026-5-3 13:15*

牛的

## 回复 by 院士 (#31)

*2026-5-3 16:33*

先收藏学习。

## 回复 by mb_agxdcibq (#32)

*2026-5-3 19:41*

666

## 回复 by 一栋奥特曼 (#33)

*2026-5-3 20:16*

666

## 回复 by ldehua (#34)

*2026-5-4 00:37*

很棒，我要学习

## 回复 by niama (#35)

*2026-5-4 07:32*

666

## 回复 by 伊苏尔德 (#36)

*2026-5-4 09:51*

6

## 回复 by 胡了个三 (#37)

*2026-5-4 11:57*

看不懂看不懂

## 回复 by shuangmou (#38)

*2026-5-4 12:49*

感谢分享

## 回复 by 樊辉 (#39)

*2026-5-4 14:41*

谢谢分享

## 回复 by MaYil (#40)

*2026-5-4 15:08*

感谢分享

## 回复 by 红颜小学生 (#41)

*2026-5-4 20:26*

牛逼

## 回复 by mb_xbgppumd (#42)

*2026-5-5 00:50*

感谢分享

## 回复 by mb_mlyojneh (#43)

*2026-5-5 11:03*

牛逼

## 回复 by lixianhuei (#44)

*2026-5-5 17:11*

666

## 回复 by 抬头望月 (#45)

*2026-5-6 09:19*

1

## 回复 by mb_uzmffdbw (#46)

*2026-5-6 09:39*

666

## 回复 by mb_yjiuccxa (#47)

*2026-5-6 09:50*

感谢分享

## 回复 by Circ1e (#48)

*2026-5-6 10:09*

666

## 回复 by yyyyy——— (#49)

*2026-5-6 10:27*

666

## 回复 by 不具名的悲伤 (#50)

*2026-5-6 10:35*

6

## 回复 by 寻梦之璐 (#51)

*2026-5-6 10:36*

666

## 回复 by bambooeric (#52)

*2026-5-6 11:16*

感谢分享

## 回复 by LuoJunJunJun (#53)

*2026-5-6 11:31*

牛逼

## 回复 by javac_kylin (#54)

*2026-5-6 13:55*

学习 学习

## 回复 by Crack999 (#55)

*2026-5-6 13:58*

厉害了，我需要学习

## 回复 by wx_Dispa1r (#56)

*2026-5-6 14:20*

666

## 回复 by 教教我吧~ (#57)

*2026-5-6 14:38*

>
> [乐子人](https://bbs.kanxue.com/user-872365.htm)
>  易盾的三年前看过了，看我的历史文章
>

佬，你之前的文章没有显示，没有发现有易盾相关的文章。（显示精华4篇，但是只能看到1篇精华）

## 回复 by xianhuimin (#58)

*2026-5-6 14:57*

tql

## 回复 by mb_cbgtaveo (#59)

*2026-5-6 15:20*

666666666

## 回复 by B.M.K (#60)

*2026-5-6 16:05*

1

## 回复 by mb_hzmzywbc (#61)

*2026-5-6 16:08*

tql

## 回复 by wx_weggfkdk (#62)

*2026-5-6 16:16*

看看

## 回复 by xingbing (#63)

*2026-5-6 16:53*

学习

## 回复 by apxar (#64)

*2026-5-6 19:43*

1

## 回复 by 菜鸟9527 (#65)

*2026-5-6 21:25*

牛逼

## 回复 by 晴空万里丶 (#66)

*2026-5-6 21:42*

tql学习下

## 回复 by mb_ugnawvja (#67)

*2026-5-7 08:58*

tql

## 回复 by 我不是卷王 (#68)

*2026-5-7 11:02*

6

## 回复 by mb_pesxllvn (#69)

*2026-5-7 11:08*

666

## 回复 by Gryffindoss (#70)

*2026-5-7 11:15*

6666

## 回复 by 学计算机睡觉 (#71)

*2026-5-7 12:07*

牛逼

## 回复 by 小木马 (#72)

*2026-5-7 15:27*

6666

## 回复 by 莫名其妙abc (#73)

*2026-5-7 17:33*

感谢分享

## 回复 by wx_妳还是不懂 (#74)

*2026-5-7 20:48*

大佬，你有空可以看一下娜迦加固企版，我感觉这个就好强，我研究挺久了

## 回复 by caydemlendi (#75)

*2026-5-7 23:42*

666

## 回复 by console_ (#76)

*2026-5-8 00:00*

1

## 回复 by 桐人dx (#77)

*2026-5-8 02:00*

1111

## 回复 by Migc (#78)

*2026-5-8 09:35*

666

## 回复 by 黑白年代 (#79)

*2026-5-8 09:47*

牛逼

## 回复 by little_r (#80)

*2026-5-8 09:49*

111

## 回复 by Imxz (#81)

*2026-5-8 11:01*

tql

## 回复 by 枯藤舍 (#82)

*2026-5-8 19:49*

666

## 回复 by mb_lzsjiukj (#83)

*2026-5-8 20:45*

学习

## 回复 by mb_kzfiflez (#84)

*2026-5-8 21:06*

强

## 回复 by LL175 (#85)

*2026-5-9 12:28*

很棒，我要学习

## 回复 by uni7corn (#86)

*2026-5-9 13:59*

666

## 回复 by hanjiefang (#87)

*2026-5-9 16:44*

tql

## 回复 by huangjw (#88)

*2026-5-9 18:31*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by mb_lzotvdxv (#89)

*2026-5-9 19:46*

Benen

## 回复 by mb_hcadvceu (#90)

*2026-5-10 01:57*

谢谢分享

## 回复 by mb_ewhhgcuy (#91)

*2026-5-11 06:54*

牛逼

## 回复 by 乐活 (#92)

*2026-5-11 09:30*

1111

## 回复 by mb_zzzqbbim (#93)

*2026-5-11 10:58*

6

## 回复 by 洋少QQ (#94)

*2026-5-11 13:14*

很棒，我要学习

## 回复 by 黄婷婷的男友 (#95)

*2026-5-11 17:16*

666666

## 回复 by 中文fjja (#96)

*2026-5-11 18:21*

学习学习！

## 回复 by 江来一定会有 (#97)

*2026-5-11 19:25*

6

## 回复 by Nanda (#98)

*2026-5-12 17:00*

1

## 回复 by mb_twbjvgyf (#99)

*2026-5-12 22:34*

1

## 回复 by lamorm (#100)

*2026-5-13 09:49*

66666

## 回复 by mb_lfwgtxdb (#101)

*2026-5-13 11:19*

感谢分享

## 回复 by mb_dmjhowok (#102)

*2026-5-13 11:49*

666

## 回复 by mb_shqpjxff (#103)

*2026-5-13 17:12*

1

## 回复 by mb_rxsabupn (#104)

*2026-5-14 05:11*

牛????

## 回复 by ivy1 (#105)

*2026-5-14 17:47*

666666

## 回复 by 木魚· (#106)

*2026-5-14 17:51*

6666666666

## 回复 by mb_odtvpflz (#107)

*2026-5-14 18:01*

很棒，我要学习

## 回复 by qwerdvd (#108)

*2026-5-15 19:08*

6666

## 回复 by AK1988DA (#109)

*2026-5-16 18:45*

444

## 回复 by mb_fdskejlh (#110)

*2026-5-16 20:54*

牛????

## 回复 by 雪国的冬天 (#111)

*2026-5-17 08:20*

感谢大佬分享

## 回复 by mb_zknspvuz (#112)

*2026-5-17 13:16*

1111111111111

## 回复 by mb_kjcdjcoy (#113)

*2026-5-18 02:42*

666

## 回复 by mb_vcadfsvs (#114)

*2026-5-18 08:11*

111

## 回复 by 婲婲丗界 (#115)

*2026-5-18 10:51*

牛皮

## 回复 by mb_kumzialx (#116)

*2026-5-18 16:34*

8888

## 回复 by cpannn (#117)

*2026-5-18 21:24*

zhichi 最新版

## 回复 by wx_coddvccwyh (#118)

*2026-5-18 22:21*

66666

## 回复 by wx_北极星_493 (#119)

*2026-5-19 11:15*

看看

## 回复 by mb_enbuhisq (#120)

*2026-5-19 16:57*

66666666666666666

## 回复 by mb_joablzkk (#121)

*2026-5-20 14:35*

1

## 回复 by mb_ugnawvja (#122)

*2026-5-20 16:35*

tql

## 回复 by mb_msgksrpq (#123)

*2026-5-20 21:00*

666

## 回复 by wx_黑色柳丁 (#124)

*2026-5-21 11:59*

牛逼

## 回复 by uboluo (#125)

*2026-5-21 14:49*

666

## 回复 by Ruinv6 (#126)

*2026-5-21 14:54*

66666666

## 回复 by mb_tewbhakr (#127)

*2026-5-21 17:18*

666666666

## 回复 by haris4687 (#128)

*2026-5-21 20:24*

666

## 回复 by mb_euhyowpw (#129)

*2026-5-22 09:10*

111

## 回复 by mb_uohfzjqw (#130)

*2026-5-22 10:18*

666

## 回复 by 4Chan (#131)

*2026-5-22 11:39*

学习一下

## 回复 by mb_vrkpxsoe (#132)

*2026-5-22 15:32*

666

## 回复 by belikewater (#133)

*2026-5-23 00:04*

1

## 回复 by wx_汪洋大海 (#134)

*2026-5-23 01:26*

666

## 回复 by 简单的简单 (#135)

*2026-5-24 23:50*

666

## 回复 by mb_kjcdjcoy (#136)

*2026-5-25 16:58*

牛逼，哥

## 回复 by mb_osxdmntv (#137)

*2026-5-25 18:28*

666

## 回复 by Tao Holmes (#138)

*2026-5-25 22:31*

tql

## 回复 by zhonghuayi (#139)

*2026-5-26 00:28*

log厉害

## 回复 by mb_ywyqvlni (#140)

*2026-5-26 14:21*

888

## 回复 by 慵懒 (#141)

*2026-5-26 16:39*

666

## 回复 by mb_pdqfznsv (#142)

*2026-5-27 00:49*

666

## 回复 by 云觞 (#143)

*2026-5-27 21:21*

66666

## 回复 by xiaohongmao (#144)

*2026-5-28 10:07*

great

## 回复 by blx2024 (#145)

*2026-5-28 17:24*

学习

## 回复 by yuxuanju (#146)

*2026-5-28 18:51*

光阴似箭啊，一晃二十多年了。

## 回复 by wx_A哦 (#147)

*2026-6-2 11:28*

666

## 回复 by 卡坦精 (#148)

*2026-6-4 09:07*

666

## 回复 by mb_xjdhrmck (#149)

*2026-6-5 00:33*

6666

## 回复 by mb_jhohnbzu (#150)

*2026-6-5 17:47*

666

## 回复 by Mr.ChenX (#151)

*2026-6-6 11:18*

666

## 回复 by 祝今朝 (#152)

*2026-6-7 23:28*

666

## 回复 by mb_sqetvntx (#153)

*2026-6-8 13:33*

学习

## 回复 by YooHaa (#154)

*2026-6-8 16:01*

666

## 回复 by mb_aavcnziz (#155)

*2026-6-9 10:42*

很棒，我要学习

## 回复 by git_74197luban110 (#156)

*2026-6-9 11:16*

666

## 回复 by wx_余生_771 (#157)

*2026-6-15 11:55*

牛逼

## 回复 by sunrise_430526 (#158)

*2026-6-16 10:49*

niubi

## 回复 by 天路 (#159)

*2026-6-16 11:15*

1

## 回复 by Freax (#160)

*2026-6-16 14:35*

6

## 回复 by 斗转南see雪 (#161)

*2026-6-16 14:57*

????

## 回复 by wx_小白_266 (#162)

*2026-6-17 10:37*

看看

## 回复 by wx_GaoH (#163)

*2026-6-19 17:10*

666

## 回复 by zzhone (#164)

*2026-6-20 16:56*

666666666

## 回复 by shuaiaimei (#165)

*2026-6-20 19:43*

大佬牛逼

## 回复 by mb_dcjxxhsk (#166)

*2026-6-21 08:42*

666

## 回复 by X66iaM (#167)

*2026-6-21 19:44*

上个版本检查了java-bridge的三个特征，这个版本检查了更多的编译特征       ----这一部分检测代码是咋定位的  那个dump下来的so里翻半天没见着啊qwq   ![image](https://bbs.kanxue.com/view/img/face/005.gif)![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by mb_paeqogwt (#168)

*2026-6-22 11:40*

test

## 回复 by mb_zuiylqkn (#169)

*2026-6-22 21:38*

感谢分享

## 回复 by 花宝叽果赖 (#170)

*2026-6-23 23:32*

严肃学习

## 回复 by yangshuang (#171)

*2026-6-24 13:34*

牛逼

## 回复 by mb_wvpaswat (#172)

*2026-6-24 15:10*

学习

## 回复 by bygrand (#173)

*2026-6-24 15:31*

强

## 回复 by Evangeliner (#174)

*2026-6-24 16:36*

6666

## 回复 by didiid (#175)

*2026-6-24 19:31*

666

## 回复 by fuqiuluo73 (#176)

*2026-6-24 20:04*

111

## 回复 by mb_rooofjxx (#177)

*2026-6-25 10:40*

牛

## 回复 by myios (#178)

*2026-6-30 06:30*

666

## 回复 by r0reborn (#179)

*2026-6-30 10:05*

666

## 回复 by aistart (#180)

*2026-7-4 12:36*

感谢分享

## 回复 by iBa0 (#181)

*2026-7-9 20:10*

123

## 回复 by wx_西门浪 (#182)

*2026-7-11 19:43*

牛逼

## 回复 by 小cold (#183)

*2026-7-12 11:09*

太强了

## 回复 by mb_iiumogmn (#184)

*2026-7-12 20:58*

感谢分享企业壳新版本frida检测分析

## 回复 by 章康 (#185)

*2026-7-13 15:22*

666

## 回复 by wx_kx92911 (#186)

*2026-7-15 09:55*

感谢分析

## 回复 by doraemonliu (#187)

*2026-7-15 12:41*

66666

## 回复 by mb_degalzhb (#188)

*2026-7-15 14:43*

666

## 回复 by 丶咖啡猫丶 (#189)

*2026-7-16 15:20*

666

## 回复 by scllqk (#190)

*2026-7-18 16:30*

学习

## 回复 by mb_zanihjkx (#191)

*2026-7-22 10:46*

666

## 回复 by wx_茄子豆角伴芹菜 (#192)

*2026-7-22 16:00*

666

## 回复 by mb_eizetlni (#193)

666

## 回复 by k4y0z (#194)

666

## 回复 by BlackMaGou (#195)

感谢分享

## 回复 by mb_syvaqetv (#196)

学习一下
