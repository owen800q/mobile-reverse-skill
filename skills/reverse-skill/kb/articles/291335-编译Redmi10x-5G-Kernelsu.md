---
title: '[原创]编译Redmi10x 5G Kernelsu'
url: https://bbs.kanxue.com/thread-291335.htm
tid: 291335
author: Chagrin4_s
date: '2026-05-24'
tags: [Android安全, 原创, 其他]
crawled_at: '2026-10-06T10:24:55+00:00'
replies: 11
---

关于编译链选择 Clang r383902 与 AOSP GCC 4.9

可以配置一个env.sh

\```
export ARCH=arm64
CLANG_BIN="$HOME/toolchains/clang12/bin"
GCC64_BIN="$HOME/toolchains/aarch64-linux-android-4.9/bin/"
GCC32_BIN="$HOME/toolchains/arm-linux-androideabi-4.9/bin/"
export CROSS_COMPILE=aarch64-linux-androidkernel-
export CROSS_COMPILE_ARM32=arm-linux-androideabi-
export PATH="$CLANG_BIN:$GCC64_BIN:$GCC32_BIN:$PATH"
export CLANG_TRIPLE=aarch64-linux-gnu-
\```

然后source env.sh

源码使用Micode <https://github.com/MiCode/Xiaomi_Kernel_OpenSource>

\```
git clone https://github.com/MiCode/Xiaomi_Kernel_OpenSource -b cezanne-r-oss --depth=1 cezanne-r-oss && cd cezanne-r-oss
\```

编译命令采用

\```
make -j$(nproc) ARCH=arm64 SUBARCH=arm64 CC=clang LD=ld.lld  O=out
\```

使用Clang编译需要设置CONFIG_CC_STACKPROTECTOR_STRONG为NONE:

\```
scripts/config --file out/.config --disable CONFIG_CC_STACKPROTECTOR_STRONG
\```

建议同时关闭LTO，除非有需要

\```
scripts/config --file out/.config --disable LTO_CLANG
\```

开始编译，先输入

\```
make -j$(nproc) ARCH=arm64 SUBARCH=arm64 CC=clang LD=ld.lld  O=out atom_user_defconfig
\```

然后

\```
make -j$(nproc) ARCH=arm64 SUBARCH=arm64 CC=clang LD=ld.lld  O=out
\```

![image](https://bbs.kanxue.com/upload/attach/202605/988914_6UEXUXJXBRQAF2U.webp)此报错需要进入最外层的Makefile 注释497行，像这样![image](https://bbs.kanxue.com/upload/attach/202605/988914_SSGVEEFGYH6GP6D.webp)这个报错这样解决:arch/arm64/kernel/vdso/gettimeofday.S 三个都像这样，去掉clock_gettime_return后面的逗号

![image](https://bbs.kanxue.com/upload/attach/202605/988914_TNP9ZEAXFP58677.webp)还会遇到

![image](https://bbs.kanxue.com/upload/attach/202605/988914_D9M63H74WQRTSJT.webp)

需要如下补丁

![image](https://bbs.kanxue.com/upload/attach/202605/988914_RWWFJF6C9EVFB48.webp)

@@ -297,7 +297,7 @@ AES_ENTRY(aes_ctr_encrypt)

 eor v1.16b, v1.16b, v3.16b

 st1 {v0.16b-v1.16b}, [x0], #32

#else

 --ldr q8, =0x30000000200000001 /* addends 1,2,3[,0] */

 ++ldr q8, .Laddends /* addends 1,2,3[,0] */

 dup v7.4s, w8

 mov v0.16b, v4.16b

 add v7.4s, v7.4s, v8.4s

@@ -394,6 +394,11 @@ AES_ENTRY(aes_xts_encrypt)

 ldr q7, .Lxts_mul_x

 b .LxtsencNx

++.Laddends:

++ .word 0x00000001

++ .word 0x00000002

++ .word 0x00000003

++ .word 0x00000000

.LxtsencloopNx:

 ldr q7, .Lxts_mul_x

 next_tweak v4, v4, v7, v8

继续编译会遇到此错误

![image](https://bbs.kanxue.com/upload/attach/202605/988914_G77P8RTKN82P9XN.webp)

![image](https://bbs.kanxue.com/upload/attach/202605/988914_3ZRFSP8NENYERVE.webp)

直接创建空文件替代

\```
mkdir -p drivers/input/touchscreen/focaltech_touch/include/firmware/
mkdir drivers/input/touchscreen/focaltech_touch/include/pramboot/
touch drivers/input/touchscreen/focaltech_touch/include/firmware/fw_ft3518_j7.i
touch drivers/input/touchscreen/focaltech_touch/include/firmware/fw_sample.i
touch drivers/input/touchscreen/focaltech_touch/include/pramboot/FT8719_Pramboot_V0.5_20171221.i
\```

继续编译会遇到如下报错

![image](https://bbs.kanxue.com/upload/attach/202605/988914_ENSCN2PHFZ7RAH9.webp)

需要去drivers/misc/mediatek/scp/mt6873/scp_helper.h 搜索SCP_RECOVERY_SUPPORT

![image](https://bbs.kanxue.com/upload/attach/202605/988914_GURQ9GJ998N3ZH3.webp)

补上 void scp_wdt_reset(int cpu_id);

然后不出意外就可以编译出Image了

但此时并没有wlan和gps bt

现在需要去小米仓库拉取mtk驱动

\```
mkdir -p vendor/mediatek/
git clone https://github.com/MiCode/MTK_kernel_modules.git -b cezanne-r-oss --depth=1 vendor/mediatek/kernel_modules
\```

编辑drivers/misc/mediatek/connectivity/Makefile

## WLAN

搜索CONFIG_WLAN_DRV_BUILD_IN

然后这样改 还需要去除$(srctree)后的../

![image-20260524153245227](https://bbs.kanxue.com/upload/attach/202605/V48MUMPGVK6YNDT.jpg)![image](https://bbs.kanxue.com/upload/attach/202605/988914_JRGM9XKGJMCA65Z.webp)

用$(abspatch)括起来这三个

![image](https://bbs.kanxue.com/upload/attach/202605/988914_7NY5TZW6KD6UH9X.webp)

unlink改为 rm -rf

ln -s改为 ln -snf

编译命令后面加上CONFIG_WLAN_DRV_BUILD_IN=y

也就是

\```
make -j$(nproc) ARCH=arm64 SUBARCH=arm64 CC=clang LD=ld.lld  O=out CONFIG_WLAN_DRV_BUILD_IN=y
\```

然后会遇到这种报错

![image](https://bbs.kanxue.com/upload/attach/202605/988914_VSN4XDANH6GQ22G.webp)

这时候去编辑

vendor/mediatek/kernel_modules/connectivity/wlan/core/gen4m/Makefile

搜索TOP

![image](https://bbs.kanxue.com/upload/attach/202605/988914_K3PSJS3MASKNKXV.webp)

将 TOP := $(srctree)/.. 改为 TOP := $(srctree)/ ，也就是去掉那两个点

vendor/mediatek/kernel_modules/connectivity/wlan/adaptor/Makefile

vendor/mediatek/kernel_modules/connectivity/bt/mt66xx/legacy/Makefile

vendor/mediatek/kernel_modules/connectivity/fmradio/Makefile

vendor/mediatek/kernel_modules/connectivity/gps/Makefile

都需要相同操作

## 蓝牙和GPS:

drivers/misc/mediatek/connectivity/Makefile 搜索For BT built-in mode start

![image](https://bbs.kanxue.com/upload/attach/202605/988914_3QWDWWQRQ79PSPF.webp)去除注释

![image](https://bbs.kanxue.com/upload/attach/202605/988914_QAAT9JE6DXEYZX7.webp)

和刚才一样改unlink ln-snf 以及abspath 需要去除$(srctree)后的../

搜索For GPS built-in mode start找到GPS，一样去除注释修改

![image](https://bbs.kanxue.com/upload/attach/202605/RQSVZE35JF5CDVU.jpg)

改好之后如下图

![image](https://bbs.kanxue.com/upload/attach/202605/988914_AVHW7GNCHSSGPSK.webp)

然后修改vendor/mediatek/kernel_modules/connectivity/gps/Makefile

搜索obj-m += $(MODULE_NAME).o

改为obj-y += $(MODULE_NAME).o

![image](https://bbs.kanxue.com/upload/attach/202605/988914_VURUGUTR8XXNFPJ.webp)

vendor/mediatek/kernel_modules/connectivity/bt/mt66xx/legacy/Makefile同理

![image](https://bbs.kanxue.com/upload/attach/202605/988914_249ZNF9M9353JBM.webp)

还需要修复两个代码

vendor/mediatek/kernel_modules/connectivity/gps/gps_emi.c

搜索gps_emi_mod_exit 去掉__exit

改好如下图

![image](https://bbs.kanxue.com/upload/attach/202605/988914_U9B624KWSV78K53.webp)
找到vendor/mediatek/kernel_modules/connectivity/gps/fw_log_gps.c 搜索 gps_fw_log_exit 和刚才一样

![image](https://bbs.kanxue.com/upload/attach/202605/988914_7E6ADWZ9YXK8RCT.webp)

最后，开启蓝牙

\```
scripts/config --file out/.config --enable CONFIG_MTK_COMBO_BT
\```

编译

![image](https://bbs.kanxue.com/upload/attach/202605/988914_3SPPM535NTMBAKK.webp)

## 集成Resukisu

在内核源码根目录执行 感谢JackA1ltman提供的脚本和patch

\```
curl -LSs "https://raw.githubusercontent.com/ReSukiSU/ReSukiSU/main/kernel/setup.sh" | bash
curl -LSs "https://raw.githubusercontent.com/JackA1ltman/NonGKI_Kernel_Build_2nd/refs/heads/mainline/Patches/susfs_inline_hook_patches.sh" | bash
curl -LSs "https://raw.githubusercontent.com/JackA1ltman/NonGKI_Kernel_Build_2nd/refs/heads/mainline/Patches/Patch/susfs_patch_to_4.14.patch" | patch -p1
\```

编辑fs/proc/task_mmu.c 在最后一个头文件后面添加

\```
#if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)
#include <linux/susfs_def.h>
#endif *// #if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MAP) || defined(CONFIG_KSU_SUSFS_OPEN_REDIRECT)
\```

![image](https://bbs.kanxue.com/upload/attach/202605/988914_WNM7D857XF24AGW.webp)

搜索static int show_smap(struct seq_file m*, void v*)

![image](https://bbs.kanxue.com/upload/attach/202605/988914_5EQSZE8YTAH8V6C.webp)

在图上位置加上

\```
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
 if (vma->vm_file) {
  if (SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))
   return 0;
 }
#endif
\```

最后

\```
scripts/config --file out/.config --enable CONFIG_KSU_SUSFS
\```

编译![image](https://bbs.kanxue.com/upload/attach/202605/988914_G2PBQNHAJ57GHC5.webp)

一路回车

![image](https://bbs.kanxue.com/upload/attach/202605/988914_N8BA4HESVP63Y6U.webp)

刷入方式可以使用magiskboot解包原boot.img后

使用out/arch/arm64/boot/Image替换kernel

使用out/arch/arm64/boot/dts/mediatek/mt6873.dtb替换dtb

重新打包即可

![image](https://bbs.kanxue.com/upload/attach/202605/988914_VAFZHWDK6GHW23M.webp)
By.酷安小白2337557

---

# 回复

## 回复 by xingbing (#2)

*2026-5-25 13:47*

学习了。

## 回复 by Zepp7289 (#3)

*2026-5-25 16:41*

tql

## 回复 by mb_jnmxfjku (#4)

*2026-5-25 17:14*

666

## 回复 by iBa0 (#5)

*2026-7-7 20:53*

1

## 回复 by wx_kx92911 (#6)

*2026-7-9 10:05*

感谢分析

## 回复 by mb_smgcyior (#7)

*2026-8-2 16:30*

NBNB

## 回复 by mb_uepdckud (#8)

*2026-8-8 09:36*

感谢教程，可惜是androidR的，有空试下Q版本的，这些

## 回复 by Chagrin4_s (#9)

*2026-8-18 20:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_uepdckud](https://bbs.kanxue.com/user-887034.htm)
>  感谢教程，可惜是androidR的，有空试下Q版本的，这些
>

手里没有机器

## 回复 by git_99423Can186 (#10)

*2026-8-24 08:06*

666

## 回复 by 在路上911 (#11)

感谢分享，内容很实用，学习了。

## 回复 by mb_xcxzqumw (#12)

感谢分享，内容很实用，学习了。
