---
title: '[原创] 编译frida-gum c版'
url: https://bbs.kanxue.com/thread-287401.htm
tid: 287401
author: 郑z
date: '2025-06-29'
tags: [Android安全, 原创, HOOK注入, 源码框架, 工具脚本]
crawled_at: '2026-08-09T04:45:13+00:00'
replies: 165
---

搞逆向一直没有一个特别顺手的工具，官方的stalker经常崩溃，qbdi需要主动调用，所以就想要自己编译gum，将报错的地方手动处理掉

刚开始研究编译总会遇到各种各样的问题，被折腾半个月，睡觉做梦都在编译gum![image](https://bbs.kanxue.com/view/img/face/017.gif)

用官方的编译命令`./configure --host=android-arm64 -- -Dfrida-gum:devkits=gum`

我环境编译出来确实跟官方编译好的结构相同，但是某些api会报错，折腾半个月，准备打算放弃，这种突然又觉得不甘心，最终也是解决了，

目前可以稳定完整trace，使用的内存映射，速度也是蛮快，1800w行20s就可以完成，后面看情况开源吧

我使用的是Android studio，因为cmake交叉编译并不熟悉，而且自我感觉Android studio方便一点，可以动态调试，实时处理bug，在使用stalker处理日志时，动态调试倒是帮了大忙

# 准备：

Ubuntu（我的是20.04）

git

ndk（我的是ndk-r25c）

node npm

Android Studio

# 开始：

观看顺序是先文字，下面是配图

将frida 拉到本地

```javascript
git clone https://github.com/frida/frida.git
cd frida
git checkout 16.2.1 // frida-server比较习惯用这个版本，所以也是编译的这个版本
\```

![image](https://bbs.kanxue.com/upload/attach/202506/994069_DYAHQQ8GWPWRXVN.jpg)

![image](https://bbs.kanxue.com/upload/attach/202506/994069_TTXW5NJ96BQAREP.jpg)

之后直接执行 `make`

会罗列出所有可以编译的版本，找到想要编译的版本

![image](https://bbs.kanxue.com/upload/attach/202506/994069_6UG7XZF93MN4VHB.jpg)

再次执行 `make gum-android-arm64`

![image](https://bbs.kanxue.com/upload/attach/202506/994069_DR95CJ5SNQA7GUM.jpg)

然后报错停止了

![image](https://bbs.kanxue.com/upload/attach/202506/994069_268YS3JPPTBY3C4.jpg)

是因为没有找到AndroidNDK，手动配置一下

下载官方ndk [https://developer.android.com/ndk/downloads](https://bbs.kanxue.com/ndk版本)

添加全局变量 ~/bashrc 文件

添加ndk路径

```javascript
export ANDROID_NDK_ROOT=/home/zheng/lib/android-ndk-r25c
export PATH=$ANDROID_NDK_ROOT:$PATH
\```

刷新配置 `source ~/.bashrc`

重新执行编译

![image](https://bbs.kanxue.com/upload/attach/202506/994069_XMJZWAREGDMA5M2.jpg)

再次遇到问题，缺少npm环境

![image](https://bbs.kanxue.com/upload/attach/202506/994069_MFSBT9UYNHAVCK4.jpg)

安装一下 sudo apt install -y nodejs npm

![image](https://bbs.kanxue.com/upload/attach/202506/994069_CMXQGRH8NGTMGN2.jpg)

再次编译 `make gum-android-arm64`

![image](https://bbs.kanxue.com/upload/attach/202506/994069_MRGRQ9FVEMRYMU7.jpg)

这个编译会将gum相关的都编译出来，编译之后的静态链在 `frida/build/frida-android-arm64/lib`中

![image](https://bbs.kanxue.com/upload/attach/202506/994069_SZ6MNDDGDCBCYKG.jpg)

# 引入Android Studio

将这个`libfrida-gum.a`还有`inlude`文件，复制到Android studio中，(这里我方便管理，塞到了自定义的frida文件中，如图三

![image](https://bbs.kanxue.com/upload/attach/202506/994069_KX9UVB36KNBW3A5.jpg)

![image](https://bbs.kanxue.com/upload/attach/202506/994069_3JMBZJQ7N5GB94K.jpg)

![image](https://bbs.kanxue.com/upload/attach/202506/994069_M399EMCJ5RNFBNA.jpg)

![image](https://bbs.kanxue.com/upload/attach/202506/994069_8C263B6B5X7XEHV.jpg)

在`CMakeLIsts.txt`中配置，在实际引用的时候，会有很多报错，我是一个一个补`.h`和`.a`最终编译成功

# CMakeLists 参考

最终我的完整 `CMakeLists.txt`文件

```plain
cmake_minimum_required(VERSION 3.22.1)

project("native-lib")

set(GUM_LIB_PATH ${CMAKE_SOURCE_DIR}/../lib/${ANDROID_ABI})

include_directories( # 添加frida依赖
        ${CMAKE_SOURCE_DIR}/frida
        ${CMAKE_SOURCE_DIR}/frida/capstone
        ${CMAKE_SOURCE_DIR}/frida/glib-2.0
        ${CMAKE_SOURCE_DIR}/frida/glib-2.0/include
        ${CMAKE_SOURCE_DIR}/frida/include
        ${CMAKE_SOURCE_DIR}/frida/lib/glib-2.0/include
)

include_directories( # 添加自定义依赖
        ${CMAKE_SOURCE_DIR}/include
)

include_directories( # 添加本体app依赖
        ${CMAKE_SOURCE_DIR}/libt
)

add_library(${CMAKE_PROJECT_NAME} SHARED
        native-lib.cpp
        libt/md5.cpp
)

target_link_libraries(${CMAKE_PROJECT_NAME}
        android
        log)

add_library(
        trace SHARED
        gum.cpp
        lib/frida_stalker.cpp
        lib/frida_attach.cpp
        lib/raw_logger.cpp
)

target_link_libraries(trace
        ${GUM_LIB_PATH}/libfrida-gum.a
        ${GUM_LIB_PATH}/libcapstone.a
        ${GUM_LIB_PATH}/libglib.a
        ${GUM_LIB_PATH}/libpcre.a
        ${GUM_LIB_PATH}/libgobject.a
        ${GUM_LIB_PATH}/libffi.a
        ${GUM_LIB_PATH}/libiconv.a
        ${GUM_LIB_PATH}/libminizip.a
        ${GUM_LIB_PATH}/libz.a
        android
        log
)
\```

文件树

```plain
 main
├──  cpp
│   ├──  frida
│   │   ├──  capstone
│   │   ├──  glib-2.0
│   │   │   ├──  gio
│   │   │   ├──  glib
│   │   │   │   ├──  deprecated
│   │   │   ├──  gmodule
│   │   │   ├──  gobject
│   │   ├──  gum
│   │   │   ├──  arch-arm
│   │   │   ├──  arch-arm64
│   │   │   ├──  arch-mips
│   │   │   ├──  arch-x86
│   │   │   ├──  heap
│   │   │   ├──  prof
│   │   ├──  gumjs
│   │   ├──  gumpp
│   │   ├──  lib
│   │   │   ├──  glib-2.0
│   │   │   │   ├──  include
│   ├──  include
│   ├──  lib
│   ├──  libt
├──  java
│   ├──  com
├──  lib
│   ├──  arm64-v8a
├──  res
│   ├──  drawable
│   ├──  layout
│   ├──  mipmap-anydpi-v26
│   ├──  mipmap-hdpi
│   ├──  mipmap-mdpi
│   ├──  mipmap-xhdpi
│   ├──  mipmap-xxhdpi
│   ├──  mipmap-xxxhdpi
│   ├──  values
│   ├──  values-night
│   ├──  xml
\```

![image](https://bbs.kanxue.com/upload/attach/202506/994069_CJZJCPQ44AEAAKK.jpg)

---

# 回复

## 回复 by mb_pesxllvn (#2)

*2025-6-29 23:16*

666

## 回复 by SomeMx (#3)

*2025-6-30 05:03*

过来瞧瞧

## 回复 by mb_cfjwplfo (#4)

*2025-6-30 05:50*

1

## 回复 by nevinhappy (#5)

*2025-6-30 07:25*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_插曲 (#6)

*2025-6-30 08:42*

666

## 回复 by ONewTach (#7)

*2025-6-30 08:44*

666

## 回复 by onlythis (#8)

*2025-6-30 09:03*

666

## 回复 by 快乐的小跳蛙 (#9)

*2025-6-30 09:32*

太强了

## 回复 by 我不是卷王 (#10)

*2025-6-30 09:40*

666

## 回复 by 皮皮虾啊 (#11)

*2025-6-30 10:17*

666

## 回复 by 夜惜风雨 (#12)

*2025-6-30 10:18*

666

## 回复 by mb_ldbucrik (#13)

*2025-6-30 10:38*

感谢分享

## 回复 by heckerstone (#14)

*2025-6-30 11:20*

666

## 回复 by sk97 (#15)

*2025-6-30 11:23*

666. 这个很详细啊

## 回复 by Ankeys (#16)

*2025-6-30 11:28*

666

## 回复 by 墨穹呢 (#17)

*2025-6-30 11:29*

感谢分享

## 回复 by 非洲棒棒 (#18)

*2025-6-30 11:41*

666

## 回复 by 4Chan (#19)

*2025-6-30 11:51*

666

## 回复 by 一只笨猫 (#20)

*2025-6-30 12:02*

6

## 回复 by 十年后 (#21)

*2025-6-30 12:09*

666

## 回复 by mb_tvmcbdnl (#22)

*2025-6-30 12:17*

666666666

## 回复 by mb_pmgifpme (#23)

*2025-6-30 13:52*

6

## 回复 by 猫子 (#24)

*2025-6-30 14:15*

学习一下

## 回复 by 万物有属 (#25)

*2025-6-30 15:15*

Learn

## 回复 by 龙飞雪 (#26)

*2025-6-30 17:35*

Learning

## 回复 by 魅叉 (#27)

*2025-6-30 18:14*

看看

## 回复 by Carrty_Cat (#28)

*2025-6-30 18:34*

learn、

## 回复 by ChengQing (#29)

*2025-6-30 18:46*

1

## 回复 by Snark (#30)

*2025-6-30 19:19*

1

## 回复 by zylyy (#31)

*2025-6-30 19:22*

6666

## 回复 by mb_qimctavn (#32)

*2025-6-30 20:33*

666

## 回复 by 边缘 (#33)

*2025-6-30 20:54*

学习一下

## 回复 by A冷忆 (#34)

*2025-6-30 21:26*

学习

## 回复 by mb_ncfbmciq (#35)

*2025-6-30 23:33*

666

## 回复 by mb_cbgtaveo (#36)

*2025-7-1 00:30*

66666

## 回复 by 千屈 (#37)

*2025-7-1 01:37*

666666

## 回复 by huangbof (#38)

*2025-7-1 05:30*

后报错停止了

## 回复 by linix (#39)

*2025-7-1 08:09*

学习一下

## 回复 by ben_ (#40)

*2025-7-1 17:14*

学习学习

## 回复 by mb_ciusvjsi (#41)

*2025-7-1 22:02*

learn

## 回复 by mb_cfzkocqj (#42)

*2025-7-2 10:51*

感谢分享

## 回复 by mb_rgdhfacg (#43)

*2025-7-2 11:25*

看看全文

## 回复 by 丶咖啡猫丶 (#44)

*2025-7-3 09:47*

666

## 回复 by wx_靛芒 (#45)

*2025-7-3 10:50*

为什么不直接用官网编译好的版本呢

## 回复 by uni7corn (#46)

*2025-7-3 11:44*

学习一下。非常感谢分享

## 回复 by 郑z (#47)

*2025-7-3 14:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_靛芒](https://bbs.kanxue.com/user-927376.htm)
>
>  为什么不直接用官网编译好的版本呢
>
>

因为官方版本有bug，会有内存崩溃，或者跳转越界等情况，不能稳定trace

## 回复 by Imxz (#48)

*2025-7-3 16:36*

666

## 回复 by shinratensei (#49)

*2025-7-3 17:25*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_tpdpxzmw (#50)

*2025-7-4 00:51*

tt

## 回复 by wx_宇克鴻 (#51)

*2025-7-4 15:56*

666666

## 回复 by 五BT (#52)

*2025-7-4 22:48*

过来瞧瞧

## 回复 by 秃顶 (#53)

*2025-7-5 14:59*

66

## 回复 by Ann945 (#54)

*2025-7-5 15:04*

1111

## 回复 by hanhaochi (#55)

*2025-7-5 16:53*

谢谢分享

## 回复 by jw8888 (#56)

*2025-7-6 10:59*

66666666666

## 回复 by lxxf (#57)

*2025-7-8 10:32*

66666666

## 回复 by mb_dhaylnrk (#58)

*2025-7-10 14:52*

666

## 回复 by mb_nkjfyhkg (#59)

*2025-7-11 01:41*

mark

## 回复 by mb_tnkubkna (#60)

*2025-7-11 17:06*

666

## 回复 by TkBinary (#61)

*2025-7-11 17:41*

学习下

## 回复 by Tokameine (#62)

*2025-7-11 20:44*

学习一下

## 回复 by wx_故事与酒 (#63)

*2025-7-12 17:00*

66666666666666

## 回复 by Arsylk (#64)

*2025-7-13 08:27*

6

## 回复 by 肥一闪 (#65)

*2025-7-13 21:29*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by 方子敬xiao (#66)

*2025-7-13 23:23*

学习

## 回复 by flice (#67)

*2025-7-22 16:41*

666666666

## 回复 by MaYil (#68)

*2025-7-22 17:34*

感谢分享

## 回复 by mb_irhdtnzm (#69)

*2025-7-23 14:18*

1

## 回复 by Thehepta (#70)

*2025-7-24 14:47*

1

## 回复 by Ram98 (#71)

*2025-7-24 16:57*

666

## 回复 by 夫人十八岁 (#72)

*2025-7-25 16:47*

1111

## 回复 by αβγδεξπ (#73)

*2025-8-6 15:12*

tql

## 回复 by mb_kamhgqsu (#74)

*2025-8-6 15:58*

666

## 回复 by l1nn (#75)

*2025-8-6 17:58*

mark

## 回复 by wx_huhu_859 (#76)

*2025-8-7 00:17*

1

## 回复 by 温泉划水鱼 (#77)

*2025-8-7 15:09*

期待开源

## 回复 by tmi (#78)

*2025-8-7 15:18*

学习一下

## 回复 by g6dtr (#79)

*2025-8-13 02:49*

6

## 回复 by loki_69 (#80)

*2025-8-14 13:56*

666

## 回复 by aq88 (#81)

*2025-8-15 20:22*

学习下

## 回复 by 阿玛农 (#82)

*2025-8-21 15:40*

下载不到源码真是无耻

## 回复 by mr2222 (#83)

*2025-8-21 17:02*

66666

## 回复 by 九黎 (#84)

*2025-8-21 17:08*

Learn

## 回复 by mb_ybvqgbkl (#85)

*2025-9-2 17:45*

666

## 回复 by KanXue_NG (#86)

*2025-9-7 20:02*

学习学习

## 回复 by 祝枝山 (#87)

*2025-9-7 20:58*

666

## 回复 by lidongyooo (#88)

*2025-9-12 12:38*

666

## 回复 by mb_mrjjcxgk (#89)

*2025-9-22 17:39*

6

## 回复 by GeQ1an (#90)

*2025-9-24 14:00*

666

## 回复 by mb_yxcltfyb (#91)

*2025-9-24 22:17*

厉害啊

## 回复 by mb_vymbqugn (#92)

*2025-9-28 14:46*

贴贴

## 回复 by thouger_ (#93)

*2025-9-29 16:54*

牛逼

## 回复 by 雅鸦歌 (#94)

*2025-9-29 19:37*

1

## 回复 by 西瓜帅 (#95)

*2025-10-5 10:00*

我来look look

## 回复 by mb_cvtgkrbe (#96)

*2025-10-9 10:53*

学习一下

## 回复 by mb_cmkfqbwu (#97)

*2025-10-9 17:44*

6666

## 回复 by xifgg (#98)

*2025-10-13 15:02*

66

## 回复 by mb_pivwkzjg (#99)

*2025-10-15 11:42*

666

## 回复 by xianhuimin (#100)

*2025-10-26 16:21*

看看怎么用

## 回复 by 半只青蛙 (#101)

*2025-10-29 14:09*

6666

## 回复 by pigsub (#102)

*2025-10-29 14:32*

6666

## 回复 by chinameme (#103)

*2025-10-30 17:01*

666

## 回复 by Dem0li (#104)

*2025-11-10 17:35*

1

## 回复 by 宛枫 (#105)

*2025-11-10 18:13*

看一下

## 回复 by 兆兆的罩罩 (#106)

*2025-11-24 18:00*

牛

## 回复 by buluo533 (#107)

*2025-11-28 08:43*

6666666666

## 回复 by huangjw (#108)

*2025-11-28 09:24*

好文章，加上编译的目的就更完美了

## 回复 by ovo_帮我不c (#109)

*2025-11-28 15:22*

1

## 回复 by wx_fly_397447 (#110)

*2025-11-28 23:55*

6666666

## 回复 by 再见君不见 (#111)

*2025-12-18 17:42*

学习，源码本身太庞大了

## 回复 by 青椒土豆 (#112)

*2025-12-21 10:20*

学习

## 回复 by dsr000 (#113)

*2025-12-22 21:21*

666

## 回复 by zkbutt (#114)

*2025-12-22 23:41*

学习

## 回复 by wx_霿凇 (#115)

*2025-12-23 15:55*

666

## 回复 by Cure. (#116)

*2026-1-1 11:17*

6

## 回复 by mb_ykavguun (#117)

*2026-1-1 11:35*

666

## 回复 by xeiyu (#118)

*2026-1-3 02:19*

6

## 回复 by Splite_1130 (#119)

*2026-1-4 14:51*

666

## 回复 by cangwuhu (#120)

*2026-1-4 20:15*

666

## 回复 by mb_vvpefhit (#121)

*2026-1-6 01:39*

jhv

## 回复 by 张three (#122)

*2026-1-7 08:36*

666

## 回复 by guijian (#123)

*2026-1-7 09:40*

6

## 回复 by 财神爷999 (#124)

*2026-1-7 10:47*

感谢分享

## 回复 by mb_bhsrdtqf (#125)

*2026-1-12 13:22*

666

## 回复 by GEKEZYX (#126)

*2026-1-16 09:43*

666

## 回复 by satng (#127)

*2026-1-16 12:17*

Learn

## 回复 by 风行九天 (#128)

*2026-1-16 16:18*

学习一下

## 回复 by ivy1 (#129)

*2026-1-16 16:42*

学习一下

## 回复 by sorely (#130)

*2026-1-19 01:25*

来学习下

## 回复 by sorely (#131)

*2026-1-19 01:25*

来学习下

## 回复 by sorely (#132)

*2026-1-19 01:25*

来学习下

## 回复 by 29o (#133)

*2026-1-19 16:02*

学习

## 回复 by mb_evapxmjh (#134)

*2026-1-19 22:34*

666

## 回复 by Va1ue (#135)

*2026-1-20 09:56*

666

## 回复 by wx_简单_549 (#136)

*2026-1-20 17:26*

看看隐藏学习

## 回复 by baogu (#137)

*2026-2-2 17:45*

1111

## 回复 by 寻梦之璐 (#138)

*2026-2-2 22:29*

111

## 回复 by mb_rceuowlf (#139)

*2026-2-9 10:45*

学习

## 回复 by didiid (#140)

*2026-2-9 19:49*

学习一下

## 回复 by straw233 (#141)

*2026-2-9 19:51*

1

## 回复 by 落雪无尘V (#142)

*2026-2-9 19:58*

支持一下啊啊

## 回复 by 末日大哥 (#143)

*2026-2-9 20:24*

666

## 回复 by 无名之辈 (#144)

*2026-2-10 10:35*

谢谢你的细致分析

## 回复 by 独一无二_370133 (#145)

*2026-2-10 10:51*

q

## 回复 by 一只鸭子 (#146)

*2026-2-10 20:36*

郑哥nb

## 回复 by spdfdfer (#147)

*2026-2-11 11:05*

666

## 回复 by mb_ihwsaggc (#148)

*2026-2-12 16:21*

学习

## 回复 by mJqalJqN (#149)

*2026-2-15 16:28*

1

## 回复 by mb_ysikfhxt (#150)

*2026-2-16 19:30*

111

## 回复 by PangBai (#151)

*2026-2-22 12:39*

学习

## 回复 by wx_一颗红心向党旗 (#152)

*2026-2-23 17:02*

6

## 回复 by 曰你 (#153)

*2026-2-28 09:45*

1

## 回复 by mb_ghzqfgyt (#154)

*2026-3-5 05:11*

4144

## 回复 by mb_donutrph (#155)

*2026-3-12 01:04*

666

## 回复 by mb_zdoxkucm (#156)

*2026-3-12 08:12*

看看你长

## 回复 by iBa0 (#157)

*2026-3-26 08:51*

12

## 回复 by mb_tkluuesh (#158)

*2026-3-26 09:10*

111

## 回复 by dob_C (#159)

*2026-3-26 09:47*

感谢分享

## 回复 by mb_rrwegvyc (#160)

*2026-3-30 16:52*

666

## 回复 by 毛毛毛毛虫 (#161)

*2026-3-30 19:29*

看看

## 回复 by zz胡 (#162)

*2026-3-30 20:22*

66

## 回复 by mb_rrwegvyc (#163)

*2026-4-2 19:45*

刚好我想做这个，而且版本还一样，感谢分享！！！！！！！！！！！！！！！

## 回复 by mb_stdlrcgp (#164)

*2026-4-2 21:53*

6666

## 回复 by mb_eumnbkwy (#165)

*2026-5-2 08:40*

看看

## 回复 by 不知世事 (#166)

*2026-6-1 17:02*

1
