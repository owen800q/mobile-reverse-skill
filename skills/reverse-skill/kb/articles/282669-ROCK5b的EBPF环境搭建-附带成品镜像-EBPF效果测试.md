---
title: '[原创]ROCK5b的EBPF环境搭建（附带成品镜像）&EBPF效果测试'
url: https://bbs.kanxue.com/thread-282669.htm
tid: 282669
author: 棕熊
date: '2024-07-28'
tags: [Android安全, 原创, 系统相关]
crawled_at: '2026-07-31T14:22:14+08:00'
replies: 10
---

# ROCK5b的EBPF环境搭建（附带成品镜像）&EBPF效果测试

从虫佬口中得知，20.04无法开启gpu是因为驱动问题，如果要开启必须要**移植驱动给redroid**

我们选择使用开源的gpu驱动，开启gpu支持。

同时编译内核开启相关驱动选项来玩转ebpf

# 参考来源

- **非虫老师的eBPF安全开发与攻防对抗系列课程**
- <https://www.bilibili.com/video/BV1N8411L7Du/?spm_id_from=333.337.search-card.all.click>
- 如果有系统调用等对抗需求可以找非虫老师报名课程，有问必答。

# 移植成品：已经开启gpu与ebpf(仅支持rock5b与orange pi5 plus）：

链接: <https://pan.baidu.com/s/1ujNRZjxRK8I_rLCkL6DVng?pwd=kkja> 提取码: kkja
--来自百度网盘超级会员v7的分享

仅需要简单的刷写镜像即可开启ebpf之旅

sd卡不需要理会spi，如果是nvme启动，请往下参考

## 方案一 驱动移植（实现失败，可以尝试）

查找到方案链接 供有能力的大佬实现（需要从原场安卓镜像移植so）

`https://github.com/remote-android/redroid-doc/issues/228`

之后找到了大佬自己移植docker的成品

git主页

`https://github.com/rk-docker`

docker容器：

| 1234 | `docker run` `-``d` `-``-``privileged` `-``-``name test \``-``p` `5555``:``5555` `\``-``v` `/``dev``/``mali0:``/``dev``/``mali0 \``shangzebei``/``rk3588 androidboot.redroid_gpu_mode``=``mali` |
|-|-|

**测试后发现不行，请大佬自行测试**

## 方案二 使用高版本系统 直接用现成的驱动

1. 安装ppa源里的malig610固件

| 1 | `sudo apt install mali``-``g610``-``firmware` |
|-|-|

	1. 创建容器

| 1234567891011 | `docker run` `-``itd` `-``-``privileged \``-``-``pull always \``-``v` `"$(pwd)"``/``Android:``/``data \``-``v` `/``dev:``/``dev \``-``v` `/``run``/``dbus:``/``run``/``dbus \``-``v` `/``var``/``run``/``dbus:``/``var``/``run``/``dbus \``-``-``mount``=``type``=``bind,source``=``/``dev``/``mali0,destination``=``/``dev``/``mali0 \``-``p` `5555``:``5555` `\``chisbread``/``rk3588``-``gaming:redroid``-``firefly \``androidboot.redroid_fps``=``30` `\``androidboot.redroid_gpu_mode``=``host` |
|-|-|
2. 使用

ppa固件在ubuntu22.04的环境下才有，所以开始安装乌班图22.04 开始编译内核

在[https://wiki.radxa.com/Rock5/downloads下发现第三方乌班图是22.04版本，果断选择](https://wiki.radxa.com/Rock5/downloads%E4%B8%8B%E5%8F%91%E7%8E%B0%E7%AC%AC%E4%B8%89%E6%96%B9%E4%B9%8C%E7%8F%AD%E5%9B%BE%E6%98%AF22.04%E7%89%88%E6%9C%AC%EF%BC%8C%E6%9E%9C%E6%96%AD%E9%80%89%E6%8B%A9)

本以为能顺利的完成，结果踩坑不断

乌班图22.04官方地址：<https://github.com/Joshua-Riek/ubuntu-rockchip>

| 123456 | `docker run` `-``itd` `-``-``privileged \``-``-``pull always \``-``-``mount``=``type``=``bind,source``=``/``dev``/``mali0,destination``=``/``dev``/``mali0 \``-``p` `5555``:``5555` `\``chisbread``/``rk3588``-``gaming:redroid``-``firefly \``androidboot.redroid_gpu_mode``=``host` |
|-|-|

### 坑点一：此乌班图移植的是armbian系列

在多次无法启动后，使用armbian的spi启动成功

### 坑点二： 此版本使用的是5.10.160内核 而非官方的110内核，尝试直接编译后替换后启动失败 开始寻找官方5.10.160内核

寻找过后找到了源码地址

<https://github.com/armbian/linux-rockchip>

Rk-5.10-rkr4分支

官方提供的编译脚本

<https://github.com/armbian/build>

### 坑点三：

python在乌班图高版本只有python2 或者python3 没有python

所以得随编译工具动态的变化软链接

虫佬提供的包，在新版本中名字也有发生变化

修改后的

| 1 | `sudo` `apt-get update &&` `sudo` `apt-get` `install` `-y git curl apt-utils wget device-tree-compiler libncurses5 libncurses5-dev build-essential libssl-dev` `mtools` `bc` `python3 dosfstools bison flex` `rsync` `u-boot-tools` `make` `dwarves libelf-dev ninja-build cmake libglib2.0-dev meson libpixman-1-dev libcapstone-dev libudev-dev libssh-dev libbrlapi-dev libpmem-dev libtasn1-6-dev libdaxctl-dev libbpf-dev libpulse-dev indent libiscsi-dev libnfs-dev libgcrypt20-dev libseccomp-dev libcurl4-openssl-dev libjack-dev libsndio-dev libopengl-dev libusb-dev acpica-tools libxkbcommon-dev libslirp-dev libsdl2-dev librados-dev libglusterfs-dev libepoxy-dev libgmp-dev libgvnc-1.0-dev libgnutls28-dev libfdt-dev` |
|-|-|

进行课程里的修改内核步骤：

| 1 | `scripts``/config` `--``enable` `CONFIG_BPF_LSMscripts``/config` `--``enable` `CONFIG_KGDBscripts``/config` `--``enable` `CONFIG_FUNCTION_PROFILERscripts``/config` `--``enable` `CONFIG_FTRACE_SYSCALLSscripts``/config` `--``enable` `CONFIG_BPF_KPROBE_OVERRIDEscripts``/config` `--``enable` `CONFIG_TRACE_EVENT_INJECTscripts``/config` `--``enable` `CONFIG_HIST_TRIGGERSscripts``/config` `--``enable` `CONFIG_SCHED_TRACERscripts``/config` `--``enable` `CONFIG_IRQSOFF_TRACERscripts``/config` `--``enable` `CONFIG_FUNCTION_TRACERscripts``/config` `--``enable` `CONFIG_STACK_TRACERscripts``/config` `--disable CONFIG_MAGIC_SYSRQscripts``/config` `--``enable` `CONFIG_IKHEADERSscripts``/config` `--``enable` `CONFIG_DEBUG_INFO_BTFscripts``/config` `--``enable` `CONFIG_ASHMEMscripts``/config` `--``enable` `CONFIG_ANDROIDscripts``/config` `--``enable` `CONFIG_ANDROID_BINDER_IPCscripts``/config` `--``enable` `CONFIG_ANDROID_BINDERFSscripts``/config` `--``set``-str CONFIG_ANDROID_BINDER_DEVICES` `""``scripts``/config` `--``enable` `CONFIG_PSI` |
|-|-|

开始编译:

编译安装后，失败了

搜索源码树以后，发现官方并没有提供5.10.160相关的支持

![截屏2023-06-22 10.36.17.png](https://bbs.kanxue.com/upload/attach/202407/967562_8VKET83P5M8YGQV.jpg)

截屏2023-06-22 10.36.17

**这也为后面相同内核的armbian最新版编译后安装失败埋下了伏笔**

## armbian的安装和实现

由于armbian是基于ubuntu的debian实现的，所以我打算拉取最新的armbian源码编译

结果：**和ubuntu22.04一样失败了**

总结： 版本的选择

在此选择下，我们开启第三个版本的测试

插曲 ： 源码选择的简单见解（**官方的源码只能官方镜像用**，升级和降级一定要**注意源码标注的系统版本**）

**sudo apt list |grep linux-source**后

linux-source-5.10.69-legacy-rockchip-rk3588/jammy,jammy 5.10.69-legacy-**rockchip-rk3588**+**22.08**.1 all

第一 源码要与相匹配的设备 rockchip-rk3588

第二 版本必须是22.08 如果不符合 就大概率不启动

所以 我们可以在wiki下从**源码挑镜像**

从这里可以拿到所有armbian的版本

<https://github.com/radxa-build/rock-5b/releases>

**rock@rock-5b:~/rk3588$ sudo apt list |grep linux-source |grep rockchip-rk3588**

![截屏2023-06-22 10.44.56.png](https://bbs.kanxue.com/upload/attach/202407/967562_X33SFMUGY8XRGST.jpg)

截屏2023-06-22 10.44.56

如此过滤 可以确定下可以尝试的版本

# 编译全流程（正文开始）

**我采用的是全程卡刷模式，需要准备一张sd卡** 淘宝上30块 128g

在此注意的是，树莓派指示灯

**蓝色长亮= 砖了**

**绿色长亮 =关机状态**

**绿色长亮，蓝色闪烁 =用户态（系统正常运行）**

刷机参考链接：

<https://wiki.radxa.com/Rock5/install/spi>

<https://wiki.radxa.com/Rock5/install/microSD>

首先：

1. 用读卡器 （有些电脑自带） 把sd卡插到电脑上
2. 使用balenaetcher直接刷入镜像包（任意Linux系统，我刷入的是虫佬课件里带的乌班图）

![image](https://bbs.kanxue.com/upload/attach/202407/967562_5Q4K9PXGZRK46GJ.jpg)

Etcher-rock-5b-1.png

3 .插入sd卡后会直接进入Linux系统 使用ip scanner扫描出ip 账号密码rock

1. 进入Linux系统后下载spi和镜像
2. 刷入spi 如果看不懂就去官方链接：<https://wiki.radxa.com/Rock5/install/spi> 或者选择线刷

| 12345678910111213141516171819202122232425 | `wget https:``/``/``github.com``/``huazi``-``yg``/``rock5b``/``releases``/``download``/``rock5b``/``rkspi_loader.img` `#armbian的spi``wget https:``/``/``dl.radxa.com``/``rock5``/``sw``/``images``/``others``/``zero.img.gz``#清除分区镜像` `gzip` `-``d zero.img.gz``# 解压镜像``ls` `/``dev``/``mtdblock``*``#查看spi分区` `应该显示``/``dev``/``mtdblock0` `将zero.img刷入分区` `sudo dd` `if``=``spi``-``image.img of``=``/``dev``/``mtdblock0``sync` `sudo md5sum` `/``dev``/``mtdblock0 zero.img``#检测是否成功刷入，如果成功了两个md5相同` `sudo dd` `if``=``spi``-``image.img of``=``/``dev``/``mtdblock0``# 刷入spi镜像` `sudo md5sum` `/``dev``/``mtdblock0 spi``-``image.img``#检测是否成功刷入，如果成功了两个md5相同` |
|-|-|

1. 刷入系统

| 123456789 | `# 下载镜像``wget https:``/``/``github.com``/``radxa``-``build``/``rock``-``5b``/``releases``/``download``/``20221108``-``0637``/``Armbian_22.``11.0``-``trunk_Rock``-``5b_bullseye_legacy_5``.``10.72_minimal``.img.xz` `# 刷入镜像``sudo xzcat` `'Armbian_22.11.0-trunk_Rock-5b_bullseye_legacy_5.10.72_minimal.img.xz'` `\| sudo dd of``=``'/dev/nvme0n1'` `bs``=``1M` `status``=``progress` `sudo xzcat` `'ubuntu-22.04-preinstalled-desktop-arm64-rock-5d.img.xz'` `\| sudo dd of``=``'/dev/nvme0n1'` `bs``=``1M` `status``=``progress` `sudo xzcat` `'Armbian_23.05.0-trunk_Rock-5b_jammy_legacy_5.10.110_redroid.img.xz'` `\| sudo dd of``=``'/dev/nvme0n1'` `bs``=``1M` `status``=``progress` |
|-|-|
2. 进入系统 默认账号密码ubuntu

 安装依赖项 **已经修改成新版本可运行的，多跑几遍确认安装成功**

| 1 | `sudo` `apt-get update &&` `sudo` `apt-get` `install` `-y git curl apt-utils wget device-tree-compiler libncurses5 libncurses5-dev build-essential libssl-dev` `mtools` `bc` `python3 dosfstools bison flex` `rsync` `u-boot-tools` `make` `dwarves libelf-dev ninja-build cmake libglib2.0-dev meson libpixman-1-dev libcapstone-dev libudev-dev libssh-dev libbrlapi-dev libpmem-dev libtasn1-6-dev libdaxctl-dev libbpf-dev libpulse-dev indent libiscsi-dev libnfs-dev libgcrypt20-dev libseccomp-dev libcurl4-openssl-dev libjack-dev libsndio-dev libopengl-dev libusb-dev acpica-tools libxkbcommon-dev libslirp-dev libsdl2-dev librados-dev libglusterfs-dev libepoxy-dev libgmp-dev libgvnc-1.0-dev libgnutls28-dev libfdt-dev` |
|-|-|

 下载系统使用内核版本的源码

 `sudo apt install linux-source-5.10.110-legacy-rockchip-rk3588`

 将内核源码解压

 并拷贝原config

| 123456 | `cd ~``mkdir kernel``cd kernel``tar` `-``xf` `/``usr``/``src``/``linux``-``source``-``5.10``.``110``-``rockchip``-``rk3588.tar.xz``tar` `-``xf` `/``usr``/``src``/``linux``-``rockchip``-``rk3588``-``legacy_5.``10.110_22``.``11.4_config``.xz``mv` `-``v linux``-``rockchip``-``rk3588``-``legacy_5.``10.110_22``.``11.4_config` `.config` |
|-|-|

 进行内核设置 不全参考 <https://github.com/iovisor/bcc/blob/master/docs/kernel_config.md> 添加选项

 **如果要开启cutefish 要额外添加，暂时未做**

| 123456 | `scripts``/``config` `-``-``enable CONFIG_ASHMEM``scripts``/``config` `-``-``enable CONFIG_ANDROID``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDER_IPC``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDERFS``scripts``/``config` `-``-``set``-``str` `CONFIG_ANDROID_BINDER_DEVICES ""``scripts``/``config` `-``-``enable CONFIG_PSI` |
|-|-|
3. 编译 安装 make -j8
4. 安装模块 sudo make modules_install
5. 安装内核 **`sudo make install`**
6. 进入boot目录

| 1 | `cd` `/``boot` |
|-|-|

| 1234567891011121314151617181920212223 | `armbianEnv.txt                  initrd.img``-``5.10``.``110``-``99``-``rockchip``-``g``armbian_first_run.txt.template  lost``+``found``boot.bmp                        System.``map``-``5.10``.``110``-``99``-``rockchip``-``g``boot.cmd                        System.``map``-``5.10``.``110``-``rockchip``-``rk3588``boot.scr                        uInitrd``config``-``5.10``.``110``-``99``-``rockchip``-``g   uInitrd``-``5.10``.``110``-``99``-``rockchip``-``g``dtb                             uInitrd``-``5.10``.``110``-``rockchip``-``rk3588``dtb``-``5.10``.``110``-``99``-``rockchip``-``g      vmlinuz``dtb``-``5.10``.``110``-``rockchip``-``rk3588    vmlinuz``-``5.10``.``110``-``99``-``rockchip``-``g``Image                           vmlinuz``-``5.10``.``110``-``rockchip``-``rk3588``initrd.img` `rock@rock``-``5b``:``/``boot$ md5sum vmlinuz``-``5.10``.``110``-``rockchip``-``rk3588``3a04f82b2e6f62680d4f39de49c93940`  `vmlinuz``-``5.10``.``110``-``rockchip``-``rk3588` `rock@rock``-``5b``:``/``boot$ md5sum vmlinuz``-``5.10``.``110``-``99``-``rockchip``-``g``67349202d412eab68167d8282c29bed3`  `vmlinuz``-``5.10``.``110``-``99``-``rockchip``-``g` `rock@rock``-``5b``:``/``boot$ md5sum vmlinuz``3a04f82b2e6f62680d4f39de49c93940`  `vmlinuz` `rock@rock``-``5b``:``/``boot$ md5sum Image``67349202d412eab68167d8282c29bed3`  `Image` |
|-|-|

 由此我们可以看出 Image才是真正的内核引导，而在乌班图22.04中 vmlinuz是真正的内核引导

 **检查一下自己的引导是不是引导到了自己想启动的内核上，用md5sum检测vmlinuz 是否等于vmlinuz-5.10.110-99-rockchip-g的md5**

>
> 补充：救砖方案
>
>
> 如果内核启动不了，插上sd卡，进入Linux系统，将原文件系统进行挂载
>
>
> sudo mkdir /mnt/mydisk1
>
>
> sudo mkdir /mnt/mydisk
>
>
> sudo mount /dev/nvme0n1p1 /mnt/mydisk1
>
>
> sudo mount /dev/nvme0n1p2 /mnt/mydisk
>
>
> cd /mnt/mydisk1 # 进入boot分区
>
>
>
>
> | 1234 | `sudo mv Image Image.old``sudo ln` `-``s vmlinuz``-``5.10``.``110` `Image` `# 将软链接改成之前的镜像，即可启动` |
> |-|-|
>
>
>

**乌班图22.04的启动镜像在firmware（大概是这意思）的文件夹里**

### 编译方式二

使用官方的编译工具安装 参考链接：<https://wiki.radxa.com/Rock5/guide/build-kernel-on-5b>

| 1234 | `$ mkdir ~``/``rk3588``-``sdk && cd ~``/``rk3588``-``sdk``$ 内核源码从``/``usr``/``src 解压出来 命名为kernel``$ git clone` `-``b master https:``/``/``github.com``/``radxa``/``rkbin.git` `# 拉取设备树``$ git clone` `-``b debian https:``/``/``github.com``/``radxa``/``build.git` `# 拉取构建脚本` |
|-|-|

修改内核设置

| 123456789101112131415161718192021222324252627 | `make rockchip_linux_defconfig` `scripts``/``config` `-``-``enable CONFIG_BPF_LSM``scripts``/``config` `-``-``enable CONFIG_KGDB``scripts``/``config` `-``-``enable CONFIG_FUNCTION_PROFILER``scripts``/``config` `-``-``enable CONFIG_FTRACE_SYSCALLS``scripts``/``config` `-``-``enable CONFIG_BPF_KPROBE_OVERRIDE``scripts``/``config` `-``-``enable CONFIG_TRACE_EVENT_INJECT``scripts``/``config` `-``-``enable CONFIG_HIST_TRIGGERS``scripts``/``config` `-``-``enable CONFIG_SCHED_TRACER``scripts``/``config` `-``-``enable CONFIG_IRQSOFF_TRACER``scripts``/``config` `-``-``enable CONFIG_FUNCTION_TRACER``scripts``/``config` `-``-``enable CONFIG_STACK_TRACER``scripts``/``config` `-``-``disable CONFIG_MAGIC_SYSRQ``scripts``/``config` `-``-``enable CONFIG_IKHEADERS``scripts``/``config` `-``-``enable CONFIG_DEBUG_INFO_BTF` `scripts``/``config` `-``-``enable CONFIG_ASHMEM``scripts``/``config` `-``-``enable CONFIG_ANDROID``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDER_IPC``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDERFS``scripts``/``config` `-``-``set``-``str` `CONFIG_ANDROID_BINDER_DEVICES ""``scripts``/``config` `-``-``enable CONFIG_PSI` `make savedefconfig``cp defconfig arch``/``arm64``/``configs``/``rockchip_linux_defconfig``make rockchip_linux_defconfig` |
|-|-|

执行完后使用官方脚本构建

| 123 | `cd ..``.``/``build``/``mk``-``kernel.sh rk3588``-``rock``-``5b``.``/``build``/``pack``-``kernel.sh` `-``d rockchip_linux_defconfig` `-``r` `99` |
|-|-|

| 123456789101112131415 | `tar xf bpftools``-``arm64.tar.gz``12`  `ls``13`  `cd bpftools``14`  `ls``15`  `.``/``python3``16`  `ls``17`  `.``/``python3 share``/``bcc``/``examples``/``hello_world.py``18`  `.``/``python3 share``/``bcc``/``tools``/``19`  `.``/``python3 share``/``bcc``/``tools``/``opensnoop``20`  `cat` `/``proc``/``sys``/``kernel``/``kptr_restrict``21`  `echo` `0` `>` `/``proc``/``sys``/``kernel``/``kptr_restrict``22`  `cat` `/``proc``/``sys``/``kernel``/``kptr_restrict``23`  `.``/``python3 share``/``bcc``/``tools``/``opensnoop``24`  `ls``25`  `.``/``python3 share``/``bcc``/``tools``/``opensnoop` |
|-|-|

# 本人亲测有效方式（一步一步照做 肯定能成）

### **此移植方案一定要有一张sd卡**

我实验了两遍，都成功安装运行，大家跟我一起做即可 这个部分我写的特别详细

使用第**成品包**移植，编译内核开启ebpf

**使用成品包的原因是不确定是不是能够百分百移植显卡驱动，那么选一个有显卡驱动的开启ebpf，那么一定可以成功**

目标移植地址：

<https://forum.radxa.com/t/guide-best-option-for-armbian-afterburner-image-by-monkablyat/14552>

下载地址：

<https://monka.systemonachip.net/rock5b/Armbian_23.05.0-trunk_Rock-5b_jammy_legacy_5.10.110_redroid.img.xz>

在sd卡中随便刷入一个系统（用读卡器） 用写盘工具简单写入即可

在sd卡中下好spi和系统镜像

1. 用读卡器 （有些电脑自带） 把sd卡插到电脑上
2. 使用balenaetcher直接刷入镜像包（任意Linux系统，我刷入的是虫佬课件里带的乌班图）

![image](https://bbs.kanxue.com/upload/attach/202407/967562_5Q4K9PXGZRK46GJ.jpg)

Etcher-rock-5b-1.png

3 .插入sd卡后会直接进入Linux系统 使用ip scanner扫描出ip 账号密码rock

1. 进入Linux系统后下载spi和镜像
2. 刷入spi 如果看不懂就去官方链接：<https://wiki.radxa.com/Rock5/install/spi> 或者选择线刷

| 12345678910111213141516171819202122232425 | `wget https:``/``/``github.com``/``huazi``-``yg``/``rock5b``/``releases``/``download``/``rock5b``/``rkspi_loader.img` `#armbian的spi``wget https:``/``/``dl.radxa.com``/``rock5``/``sw``/``images``/``others``/``zero.img.gz``#清除分区镜像` `gzip` `-``d zero.img.gz``# 解压镜像``ls` `/``dev``/``mtdblock``*``#查看spi分区` `应该显示``/``dev``/``mtdblock0` `将zero.img刷入分区` `sudo dd` `if``=``zero.img of``=``/``dev``/``mtdblock0``sync` `sudo md5sum` `/``dev``/``mtdblock0 zero.img``#检测是否成功刷入，如果成功了两个md5相同` `sudo dd` `if``=``spi``-``image.img of``=``/``dev``/``mtdblock0``# 刷入spi镜像` `sudo md5sum` `/``dev``/``mtdblock0 spi``-``image.img``#检测是否成功刷入，如果成功了两个md5相同` |
|-|-|
3. 刷入系统

| 1234567 | `# 下载镜像``wget https:``/``/``monka.systemonachip.net``/``rock5b``/``Armbian_23.``05.0``-``trunk_Rock``-``5b_jammy_legacy_5``.``10.110_redroid``.img.xz` `# 刷入镜像``sudo xzcat` `'Armbian_23.05.0-trunk_Rock-5b_jammy_legacy_5.10.110_redroid.img.xz'` `\| sudo dd of``=``'/dev/nvme0n1'` `bs``=``1M` `status``=``progress` `sudo xzcat` `'Armbian-unofficial_24.8.0-trunk_Rock-5b_jammy_legacy_5.10.160.img'` `\| sudo dd of``=``'/dev/nvme0n1'` `bs``=``1M` `status``=``progress` |
|-|-|

**刷入后不要重启系统**

由于是第三方打包的，需要手动扩容根分区 （我手动实现了两遍，严格按照指令走即可）

`sudo fdisk -l`

输出

| 123456789101112 | `User``Disk` `/``dev``/``nvme0n1:` `476.94` `GiB,` `512110190592` `bytes,` `1000215216` `sectors``Disk model: CHUXIA` `512GB``Units: sectors of` `1` `*` `512` `=` `512` `bytes``Sector size (logical``/``physical):` `512` `bytes` `/` `512` `bytes``I``/``O size (minimum``/``optimal):` `512` `bytes` `/` `512` `bytes``Disklabel` `type``: gpt``Disk identifier:` `286CDA69``-``C967``-``7D49``-``A6D3``-``5566C9C2E6A1` `Device          Start      End  Sectors  Size` `Type``/``dev``/``nvme0n1p1` `32768`   `557055`   `524288`  `256M` `Linux extended boot``/``dev``/``nvme0n1p2` `557056` `30801920` `30244865` `14.4G` `Linux filesystem` |
|-|-|

查看磁盘名称

我的是 /dev/nvme0n1

| 1 | `sudo fdisk` `/``dev``/``nvme0n1` |
|-|-|

进入交互模式

| 1 | `d` |
|-|-|

先按一个d 按回车后 他会提示你输入数字

输入2 回车

| 1 | `n` |
|-|-|

**按n后**

**输入2**

**之后直接全部回车即可**

**按w后 自动保存退出**

### 原理 删除原来的第二分区 也就是根分区 再重新分区 两次回车是选择启动分区的末尾和硬盘的末尾（也就是最大硬盘）

修复分区

| 1 | `sudo e2fsck` `-``f` `/``dev``/``nvme0n1p2` |
|-|-|

重新读取大小

| 1 | `sudo resize2fs` `/``dev``/``nvme0n1p2` |
|-|-|

接下来拔掉sd卡 进入系统即可

账号 rock 密码armbian +

下载源码

| 1 | `sudo apt install linux``-``source``-``5.10``.``110``-``legacy``-``rockchip``-``rk3588` |
|-|-|

原来的方式无法获取到源码了<https://forum.armbian.com/topic/29087-migration-to-rk35xx-linuxfamily/>

```
sudo sed -i 's/LINUXFAMILY=rockchip-rk3588/LINUXFAMILY=rk35xx/g' /etc/armbian-release
sudo apt update
sudo apt install linux-image-legacy-rk35xx linux-dtb-legacy-rk35xx linux-headers-legacy-rk35xx
sudo apt remove linux-image-legacy-rockchip-rk3588 linux-dtb-legacy-rockchip-rk3588 linux-headers-legacy-rockchip-rk3588
```

即可获取到最新的160源码

解压源码

| 1234 | `/``usr``/``src``├── linux``-``headers``-``5.10``.``110``-``rockchip``-``rk3588``├── linux``-``rockchip``-``rk3588``-``legacy_5.``10.110_22``.``11.4_config``.xz``└── linux``-``source``-``5.10``.``110``-``rockchip``-``rk3588.tar.xz` |
|-|-|

| 123456 | `cd ~``mkdir kernel``cd kernel``tar` `-``xf` `/``usr``/``src``/``linux``-``source``-``5.10``.``110``-``rockchip``-``rk3588.tar.xz``tar` `-``xf` `/``usr``/``src``/``linux``-``rockchip``-``rk3588``-``legacy_5.``10.110_22``.``11.4_config``.xz``mv` `-``v linux``-``rockchip``-``rk3588``-``legacy_5.``10.110_22``.``11.4_config` `.config` |
|-|-|

**如果没有config文件，那么去boot目录下复制即可**

| 1 | `cp` `/``boot``/``config``-``5.10``.``110``-``rockchip``-``rk3588 ~` |
|-|-|

复制完记得移动到kernel目录下，并命名.config

安装编译依赖

| 1 | `sudo apt``-``get update && sudo apt``-``get install` `-``y git curl apt``-``utils wget device``-``tree``-``compiler libncurses5 libncurses5``-``dev build``-``essential libssl``-``dev mtools bc python3 python2 dosfstools bison flex rsync u``-``boot``-``tools make dwarves libelf``-``dev ninja``-``build cmake libglib2.``0``-``dev meson libpixman``-``1``-``dev libcapstone``-``dev libudev``-``dev libssh``-``dev libbrlapi``-``dev libpmem``-``dev libtasn1``-``6``-``dev libdaxctl``-``dev libbpf``-``dev libpulse``-``dev indent libiscsi``-``dev libnfs``-``dev libgcrypt20``-``dev libseccomp``-``dev libcurl4``-``openssl``-``dev libjack``-``dev libsndio``-``dev libopengl``-``dev libusb``-``dev acpica``-``tools libxkbcommon``-``dev libslirp``-``dev libsdl2``-``dev librados``-``dev libglusterfs``-``dev libepoxy``-``dev libgmp``-``dev libgvnc``-``1.0``-``dev libgnutls28``-``dev libfdt``-``dev` |
|-|-|

调整配置 (在内核目录下输入这些命令 分段输入 别一下粘贴)

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273 | `第一段： 开启ebpf` `scripts``/``config` `-``-``enable CONFIG_BPF_LSM``scripts``/``config` `-``-``enable CONFIG_KGDB``scripts``/``config` `-``-``enable CONFIG_FUNCTION_PROFILER``scripts``/``config` `-``-``enable CONFIG_FTRACE_SYSCALLS``scripts``/``config` `-``-``enable CONFIG_BPF_KPROBE_OVERRIDE``scripts``/``config` `-``-``enable CONFIG_TRACE_EVENT_INJECT``scripts``/``config` `-``-``enable CONFIG_HIST_TRIGGERS``scripts``/``config` `-``-``enable CONFIG_SCHED_TRACER``scripts``/``config` `-``-``enable CONFIG_IRQSOFF_TRACER``scripts``/``config` `-``-``enable CONFIG_FUNCTION_TRACER``scripts``/``config` `-``-``enable CONFIG_STACK_TRACER``scripts``/``config` `-``-``disable CONFIG_MAGIC_SYSRQ``scripts``/``config` `-``-``enable CONFIG_IKHEADERS``scripts``/``config` `-``-``enable CONFIG_DEBUG_INFO_BTF` `第二段 开启redroid` `scripts``/``config` `-``-``enable CONFIG_ASHMEM``scripts``/``config` `-``-``enable CONFIG_ANDROID``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDER_IPC``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDERFS``scripts``/``config` `-``-``set``-``str` `CONFIG_ANDROID_BINDER_DEVICES ""``scripts``/``config` `-``-``enable CONFIG_PSI` `第三段 开启cutefish` `scripts``/``config` `-``-``set``-``val CONFIG_VHOST_SCSI m``scripts``/``config` `-``-``set``-``val CONFIG_VHOST_VSOCK m``scripts``/``config` `-``-``set``-``val CONFIG_VHOST_VDPA m``scripts``/``config` `-``-``set``-``val CONFIG_VDPA m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_DRIVERS y``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_TTY m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_HSI m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_VIRTIO m``scripts``/``config` `-``-``set``-``val CONFIG_TARGET_CORE m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_USB m``scripts``/``config` `-``-``set``-``val CONFIG_VSOCKETS m` `scripts``/``config` `-``-``enable CONFIG_BPF_LSM``scripts``/``config` `-``-``enable CONFIG_KGDB``scripts``/``config` `-``-``enable CONFIG_FUNCTION_PROFILER``scripts``/``config` `-``-``enable CONFIG_FTRACE_SYSCALLS``scripts``/``config` `-``-``enable CONFIG_BPF_KPROBE_OVERRIDE``scripts``/``config` `-``-``enable CONFIG_TRACE_EVENT_INJECT``scripts``/``config` `-``-``enable CONFIG_HIST_TRIGGERS``scripts``/``config` `-``-``enable CONFIG_SCHED_TRACER``scripts``/``config` `-``-``enable CONFIG_IRQSOFF_TRACER``scripts``/``config` `-``-``enable CONFIG_FUNCTION_TRACER``scripts``/``config` `-``-``enable CONFIG_STACK_TRACER``scripts``/``config` `-``-``disable CONFIG_MAGIC_SYSRQ``scripts``/``config` `-``-``enable CONFIG_IKHEADERS``scripts``/``config` `-``-``enable CONFIG_DEBUG_INFO_BTF``scripts``/``config` `-``-``enable CONFIG_ASHMEM``scripts``/``config` `-``-``enable CONFIG_ANDROID``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDER_IPC``scripts``/``config` `-``-``enable CONFIG_ANDROID_BINDERFS``scripts``/``config` `-``-``set``-``str` `CONFIG_ANDROID_BINDER_DEVICES ""``scripts``/``config` `-``-``enable CONFIG_PSI``scripts``/``config` `-``-``set``-``val CONFIG_VHOST_SCSI m``scripts``/``config` `-``-``set``-``val CONFIG_VHOST_VSOCK m``scripts``/``config` `-``-``set``-``val CONFIG_VHOST_VDPA m``scripts``/``config` `-``-``set``-``val CONFIG_VDPA m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_DRIVERS y``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_TTY m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_HSI m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_VIRTIO m``scripts``/``config` `-``-``set``-``val CONFIG_TARGET_CORE m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF m``scripts``/``config` `-``-``set``-``val CONFIG_CAIF_USB m``scripts``/``config` `-``-``set``-``val CONFIG_VSOCKETS m` |
|-|-|

开始编译

| 1 | `make` `-``j8` |
|-|-|

编译后可能会出现一些提示 尽量多的选m 以模块运行 可以翻译下 觉得好的功能开开 不影响

| 1 | `Virtual vsock monitoring device (VSOCKMON) [N``/``m``/``?] (NEW)` |
|-|-|

安装模块

| 1 | `sudo make modules_install` |
|-|-|

安装内核

| 1 | `sudo make install` |
|-|-|

进入boot后查看Image软链接位置是否为新编译的内核（不知道可以看时间 ll命令）

| 123456789101112131415161718192021222324 | `-``rw``-``rw``-``r``-``-` `1` `rock rock` `209` `Jun` `22` `11``:``20` `armbianEnv.txt``-``rw``-``rw``-``r``-``-` `1` `root root` `1536` `Mar` `28` `09``:``08` `armbian_first_run.txt.template``-``rw``-``rw``-``r``-``-` `1` `root root` `38518` `Mar` `28` `09``:``08` `boot.bmp``-``rw``-``rw``-``r``-``-` `1` `rock rock` `3404` `Mar` `28` `07``:``48` `boot.cmd``-``rw``-``rw``-``r``-``-` `1` `root root` `3476` `Mar` `28` `09``:``08` `boot.scr``-``rw``-``r``-``-``r``-``-` `1` `root root` `217231` `Jun` `22` `11``:``16` `config``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `216195` `Mar` `28` `08``:``58` `config``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `28` `Mar` `28` `09``:``07` `dtb` `-``> dtb``-``5.10``.``110``-``rockchip``-``rk3588``drwxr``-``xr``-``x` `3` `root root` `4096` `Mar` `28` `09``:``07` `dtb``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `17` `Jun` `22` `11``:``19` `Image` `-``> vmlinuz``-``5.10``.``110``+` `/``/``这里指向了新内核``lrwxrwxrwx` `1` `root root` `20` `Jun` `22` `11``:``17` `initrd.img` `-``> initrd.img``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `15467772` `Jun` `22` `11``:``17` `initrd.img``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `15281181` `Jun` `22` `09``:``40` `initrd.img``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `35` `Jun` `22` `11``:``17` `initrd.img.old` `-``> initrd.img``-``5.10``.``110``-``rockchip``-``rk3588``drwx``-``-``-``-``-``-` `2` `root root` `16384` `Mar` `28` `09``:``08` `lost``+``found``-``rw``-``r``-``-``r``-``-` `1` `root root` `8086342` `Jun` `22` `11``:``16` `System.``map``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `7895037` `Mar` `28` `08``:``58` `System.``map``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `17` `Jun` `22` `11``:``17` `uInitrd` `-``> uInitrd``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `15467836` `Jun` `22` `11``:``17` `uInitrd``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `15281245` `Jun` `22` `09``:``40` `uInitrd``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `17` `Jun` `22` `11``:``17` `vmlinuz` `-``> vmlinuz``-``5.10``.``110``+``-``rw``-``r``-``-``r``-``-` `1` `root root` `38984192` `Jun` `22` `11``:``16` `vmlinuz``-``5.10``.``110``+` `# 这是新内核``-``rw``-``r``-``-``r``-``-` `1` `root root` `34632192` `Mar` `28` `08``:``58` `vmlinuz``-``5.10``.``110``-``rockchip``-``rk3588``lrwxrwxrwx` `1` `root root` `32` `Jun` `22` `11``:``17` `vmlinuz.old` `-``> vmlinuz``-``5.10``.``110``-``rockchip``-``rk3588` |
|-|-|

若没有指向新内核 只需要执行

| 12 | `sudo rm Image``ln` `-``s 新内核名称 Image` |
|-|-|

然后重启即可发现内核替换成功

| 1 | `Linux rock``-``5b` `5.10``.``110``+` `#2 SMP Thu Jun 22 11:02:48 CEST 2023 aarch64 aarch64 aarch64 GNU/Linux` |
|-|-|

cuttefish参考课程，内核已经在编译时候修改过了

这个镜像内置 `https://github.com/ChisBread/malior#malior-redroid`

可以尝试使用

进docker系统以后 记得

sudo mount -t `debugfs debugfs /sys/kernel/debug`

并修改 /proc/sys/kernel/kptr_restrict的的值为0

**参考自ebpf课程内容**

若docker无法启动 则检测模块是否已经安装

交叉编译rock5b内核

| 1 | `git clone -b stable-5.10-rock5 https:``//github``.com``/radxa/kernel``.git --depth=1` |
|-|-|

编译打包headers

```
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- headers_check
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- headers_install INSTALL_HDR_PATH=output_headers
```

# 成品测试

![CleanShot 2024-07-28 at 15.10.16](https://bbs.kanxue.com/upload/attach/202407/967562_XT5JC6NQAB7B4RJ.jpg)

![CleanShot 2024-07-28 at 15.20.28](https://bbs.kanxue.com/upload/attach/202407/967562_DPXX8GD8XZGQNHQ.jpg)

成功启动所有系统调用监控

## 案例1 某MT SVC签名校验

![CleanShot 2024-07-28 at 15.22.31](https://bbs.kanxue.com/upload/attach/202407/967562_UN6BHJE76CG25VS.jpg)

## 案例2 文件io重定向

![CleanShot 2024-07-28 at 15.28.59](https://bbs.kanxue.com/upload/attach/202407/967562_WX2XWYZYP37R3D5.jpg)

首先创建两个file1 内容 file number1

file2 file number2

开启文件重定向

![CleanShot 2024-07-28 at 15.29.58](https://bbs.kanxue.com/upload/attach/202407/967562_AWD9V4G72UCK8BB.jpg)

之后查看文件1

![CleanShot 2024-07-28 at 15.30.34](https://bbs.kanxue.com/upload/attach/202407/967562_U8F6PP7TSTMHHZD.jpg)

发现是文件2的内容

## 案例3 某Frida检测

![CleanShot 2024-07-28 at 15.32.17](https://bbs.kanxue.com/upload/attach/202407/967562_XA6Y2KUNX25ATZT.jpg)

![CleanShot 2024-07-28 at 15.32.27](https://bbs.kanxue.com/upload/attach/202407/967562_5W26B7YE4FQ5WFS.jpg)

发现这个进程在不断访问自己的maps，不知道干啥呢

![image](https://bbs.kanxue.com/upload/attach/202407/967562_BNEDVMR74QW6ZM3.jpg)

访问次数稳定增加，可以判断是线程循环检测，接下来就要做一些东西了

再看看他还访问其他什么了嘛

![CleanShot 2024-07-28 at 15.34.26](https://bbs.kanxue.com/upload/attach/202407/967562_W5QCCP8GPCMF4H4.jpg)

/fd

/maps

/task

都进行了大量循环访问，那么只需要过滤进程名，做io重定向就好了

---

# 回复

## 回复 by 棕熊 (#2)

*2024-7-28 15:43*

需要注意。rock5b版本有5.10.66和6.10两种内核版本供大家选择，orange pi5 plus 只有5.10.160一个内核版本，本文章仅讲如何搭建ebpf环境，ebpf相关知识请去非虫老师的b站进行学习

## 回复 by mb_ldbucrik (#3)

*2024-7-28 23:49*

大佬，太强了，先收藏了，以后参考学习

## 回复 by 我是土匪 (#4)

*2024-7-29 07:05*

orange pi5 plus 比 rock5b 更有性价比。https://github.com/Joshua-Riek/ubuntu-rockchip  这个项目支持5.10和6.10内核的

## 回复 by 棕熊 (#5)

*2024-7-29 08:07*

>
> [我是土匪](https://bbs.kanxue.com/user-155099.htm)
>
>  orange pi5 plus 比 rock5b 更有性价比。https://github.com/Joshua-Riek/ubuntu-rockchip 这个项目支持5.10和6.10内核的
>
>

是这样的，这个项目也是armbian内核，做了局部修改，作者给的build脚本比较简陋 需要修改他的构建文件

## 回复 by 棕熊 (#6)

*2024-7-29 08:08*

>
> [mb_qzwrkwda](https://bbs.kanxue.com/user-967562.htm)
>
>  需要注意。rock5b版本有5.10.66和6.10两种内核版本供大家选择，orange pi5 plus 只有5.10.160一个内核版本，本文章仅讲如何搭建ebpf环境，ebpf相关知识请去非虫老 ...
>
>

orangepi只有一个内核版本是因为我只编译了一个，大家有需要可以去自己编译

## 回复 by Python成长路 (#7)

*2024-7-29 16:06*

我也用的https://github.com/Joshua-Riek/ubuntu-rockchip，编译不需要改build脚本，改个内核配置文件就能编译。可以看：https://mp.weixin.qq.com/s/BlxkDZNR6kyiS2ZjCHGo3g

## 回复 by 棕熊 (#8)

*2024-7-29 19:25*

>
> [Python成长路](https://bbs.kanxue.com/user-779572.htm)
>
>  我也用的https://github.com/Joshua-Riek/ubuntu-rockchip，编译不需要改build脚本，改个内核配置文件就能编译。可以看：https://mp.weixin. ...
>
>

谢谢，今晚学习下，已经关注～

## 回复 by 养只猫不好么 (#9)

*2024-7-31 10:28*

感谢分享

## 回复 by Amun (#10)

*2024-7-31 14:41*

珍惜生命，建议用 飞腾主板 + AMD 显卡。

## 回复 by 黄药师pp (#11)

*2025-7-25 12:01*

大神您好，您分享的移植成品：已经开启gpu与ebpf(仅支持rock5b与orange pi5 plus）：
链接:  提取码: kkja
--来自百度网盘超级会员v7的分享
连接已经失效了，正在学习ebpf，能请求大神再次分享一下吗？万分感谢
