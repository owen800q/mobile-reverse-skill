---
title: '[原创]将rwProcMem33编译进安卓内核'
url: https://bbs.kanxue.com/thread-278647.htm
tid: 278647
author: oacia
date: '2023-08-31'
tags: [Android安全, 原创, 系统相关, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:38:51+08:00'
replies: 68
---

>
> 为了做出腾讯游戏安全竞赛初赛的这道安卓题,开始学习`rwProcMem33` 的使用来打硬件断点了
>
>
> 在[juice4fun](https://bbs.kanxue.com/user-home-831526.htm)师傅做腾讯游戏安全竞赛初赛的安卓题的[writeup](https://bbs.kanxue.com/thread-276896.htm#msg_header_h2_2)时,使用了[rwProcMem33](https://github.com/abcz316/rwProcMem33)来对安卓手机打下硬件断点分析反调试,我也对在安卓手机中打硬件断点的工具很感兴趣,所以就学习一下编译和使用的方法啦
>
>
> 要想使用rwProcMem33,编译环境(即AOSP安卓内核源码环境)的搭建过程是必不可少的,因为最终内核模块是运行在安卓手机的linux内核中,而非虚拟机的linux内核中,所以内核源码是有必要下载的
>
>
> 所以这篇文章不仅是硬件断点工具的编译和使用笔记,也是安卓内核的编译笔记,用来记录我在编译内核的过程中遇到的困难,以及如何克服的
>
>
> 为了更快的下载速度,可以选择配置代理,也可以手动切换下载源,只要不出现网络问题导致下载失败就行
>
>
> docker的使用完全是因为我的虚拟机shell环境崩溃,从而导致无法编译,如果对自己虚拟机的shell环境足够自信,不使用docker也是可以的
>
>
>

# 编译环境搭建

## 虚拟机配置

我使用的虚拟机为`Ubuntu22.04`,虚拟机的参考配置如下

![image-20230811162236189](https://bbs.kanxue.com/upload/attach/202308/963320_PETCHPHSF5TSJTH.png)

## 为虚拟机配置代理

### 查看虚拟机代理地址

打开`clash for windows`,并打开`Allow LAN`的开关,随后点击`network interfaces`

![image-20230811175325211](https://bbs.kanxue.com/upload/attach/202308/963320_USNYY8N3ZYGGU87.png)

请注意我的虚拟机使用的网络连接方式为NAT模式,所以需要关注`VMnet8`的地址,所以对于该虚拟机,代理地址为`192.168.27.1`,端口就是`clash`中`Port`选项所显示的端口

![image-20230811175516413](https://bbs.kanxue.com/upload/attach/202308/963320_F5Y9EE4YGGJ2PP7.png)

### 启用虚拟机代理

依次点击如下选项进入代理配置

![image-20230811180538737](https://bbs.kanxue.com/upload/attach/202308/963320_MSKAYGFMEHH78HB.png)

输入代理地址保存即可

![image-20230811180608202](https://bbs.kanxue.com/upload/attach/202308/963320_2UY6VUJFA74ZMGP.png)

## 配置docker ubuntu镜像

>
> 本人因为不小心运行了一个命令`source _setup_env.sh`,导致虚拟机的shell环境整个崩掉了,`build.sh`也屡屡运行失败,看了眼`_setup_env.sh`我真是只能苦涩的笑...
>
>
> ![image-20230816224032513](https://bbs.kanxue.com/upload/attach/202308/963320_UNSWBP4C8JHX4QW.png)
>
>
> 所以不得不用docker了,不过用下来发现竟然意外的好用
>
>
>

### 安装docker

| 1 | `sudo` `apt` `install` `docker.io` |
|-|-|

### docker pull代理配置

| 12 | `sudo` `mkdir` `-p` `/etc/systemd/system/docker``.service.d``sudo` `gedit` `/etc/systemd/system/docker``.service.d``/proxy``.conf` |
|-|-|

输入以下代理服务器内容

| 1234 | `[Service]``Environment=``"HTTP_PROXY=http://192.168.27.1:7890/"``Environment=``"HTTPS_PROXY=http://192.168.27.1:7890/"``Environment=``"NO_PROXY=localhost,127.0.0.1"` |
|-|-|

### 刷新配置并重启 docker 服务

| 12 | `sudo` `systemctl daemon-reload``sudo` `systemctl restart docker` |
|-|-|

### docker镜像代理配置

| 12 | `sudo` `mkdir` `-p ~/.docker/``sudo` `gedit ~/.docker``/config``.json` |
|-|-|

输入以下内容

| 1234567891011 | `{``"proxies"``:``{``"default"``:``{``"httpProxy"``:` `"http://192.168.27.1:7890/"``,``"httpsProxy"``:` `"http://192.168.27.1:7890/"``,``"noProxy"``:` `"localhost,127.0.0.1"``}``}``}` |
|-|-|

### 下载Ubuntu镜像

| 1 | `docker pull ubuntu` |
|-|-|

### 运行Ubuntu镜像

| 1 | `docker run -it --net host --name Akernel ubuntu` `/bin/bash` |
|-|-|

## 安装sudo,vim

| 123 | `apt-get update``apt-get` `install` `vim``apt-get` `install` `sudo` |
|-|-|

## 修改apt-get的软件源为阿里源

| 12 | `sudo` `cp` `/etc/apt/sources``.list` `/etc/apt/sources``.list_backup``sudo` `vim` `/etc/apt/sources``.list` |
|-|-|

替换为如下内容

| 1234567891011121314 | `deb http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse``deb-src http://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse` `deb http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse``deb-src http://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse` `deb http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse``deb-src http://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse` `# deb http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse``# deb-src http://mirrors.aliyun.com/ubuntu/ jammy-proposed main restricted universe multiverse` `deb http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse``deb-src http://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse` |
|-|-|

随后将`apt-get`更新至最新版本

| 123 | `sudo` `apt-get update``sudo` `apt-get upgrade``sudo` `apt-get` `install` `build-essential` |
|-|-|

## 安装必要的库

| 1 | `sudo` `apt-get` `install` `git-core gnupg flex bison build-essential zip curl zlib1g-dev gcc-multilib g++-multilib libc6-dev-i386 libncurses5 lib32ncurses5-dev x11proto-core-dev libx11-dev lib32z1-dev libgl1-mesa-dev libxml2-utils xsltproc unzip fontconfig libssl-dev` `bc` `kmod cpio git curl` |
|-|-|

## 为git配置基本信息

| 123 | `git config --global user.email` `"xxx@gmail.com"``git config --global user.name` `"xxx"``git config --global http.proxy 192.168.27.1:7890` |
|-|-|

## 安装repo

| 123 | `mkdir` `~``/bin``curl https:``//storage``.googleapis.com``/git-repo-downloads/repo` `> ~``/bin/repo``chmod` `a+x ~``/bin/repo` |
|-|-|

## 修改repo的下载源为清华源,并添加repo至全局变量

### 打开全局变量配置文件

| 1 | `sudo` `vim ~/.bashrc` |
|-|-|

### 添加全局变量

在末尾添加这三行并保存

| 123 | `# repo``export` `REPO_URL=``'https://mirrors.tuna.tsinghua.edu.cn/git/git-repo/'``export` `PATH=``"~/bin:$PATH"` |
|-|-|

### 使配置文件生效

| 1 | `source` `~/.bashrc` |
|-|-|

## 安装python

如果使用`python --version`有打印python版本的话,那么这一步就不需要了,如果docker中没有安装`python`,在docker内使用如下命令安装

| 1234 | `sudo` `apt-get` `install` `software-properties-common``add-apt-repository ppa:deadsnakes``/ppa``sudo` `apt` `install` `python3.9``sudo` `ln` `-s` `/usr/bin/python3` `/usr/bin/python` |
|-|-|

## 修改交换区大小

为了防止编译源码的过程中由于交换区不足而失败,所以我们需要去修改**虚拟机**的交换区的大小

| 12345678 | `sudo` `swapoff` `/swapfile``sudo` `rm` `/swapfile` `# 设置了32g交换区, 防止编译失败，执行下列命令需要花费一段时间，如果执行命令后没有输出，请耐心等待命令执行完毕``sudo` `dd` `if``=``/dev/zero` `of=``/swapfile` `bs=1GB count=32``sudo` `chmod` `600` `/swapfile``sudo` `mkswap -f` `/swapfile``sudo` `swapon` `/swapfile` |
|-|-|

# 下载内核源码

## 查看内核版本号

这里我的`pixel3`的内核版本为`Linux version 4.9.270-g862f51bac900-ab7613625`

| 12 | `adb shell` `cat` `/proc/version``Linux version 4.9.270-g862f51bac900-ab7613625 (android-build@abfarm-east4-101) (Android (7284624, based on r416183b) clang version 12.0.5 (https:``//android``.googlesource.com``/toolchain/llvm-project` `c935d99d7cf2016289302412d708641d52d2f7ee))` `#0 SMP PREEMPT Thu Aug 5 07:04:42 UTC 2021` |
|-|-|

## 查看内核源码分支

进入[building-kernels](https://source.android.com/setup/build/building-kernels)中查看自己的源码分支,如图我的手机型号为`pixel3`,并且内核版本为4.9,于是就知道内核源码的代号是`android-msm-crosshatch-4.9`

![image-20230811172340268](https://bbs.kanxue.com/upload/attach/202308/963320_8HQ82VK39A9MFGD.png)

之后进入[安卓内核源码列表](https://android.googlesource.com/kernel/manifest/+refs)中,搜索内核源码代号`android-msm-crosshatch-4.9`

![image-20230811232551456](https://bbs.kanxue.com/upload/attach/202308/963320_A5EU9GBYQE628Y3.png)

我的手机是安卓12,所以我下载的内核版本为`android-msm-crosshatch-4.9-android12`

这里的`qpr1`和`qpr2`,我们先看一下`QPR`的定义,简单来说就是`QPR`后面跟的数字越高,内核版本就越新

>
> QPR, of course, is short for the **Quarterly Platform Release**, which Google first introduced with Android 12. These are not full system updates, but they bring a few select changes to the Pixels and other great high-end phones that opt to receive them.
>
>
>

注意一点就是例如你想要下载[android-msm-crosshatch-4.9-android10](https://android.googlesource.com/kernel/manifest/+/refs/heads/android-msm-crosshatch-4.9-android10),请先进入你想要下载的AOSP的地址,看看仓库中的`default.xml`文件,重点关注`<project path="build" name="kernel/build"` ,如果`revision`的值为`main`,请千万不要下载,否则你就会发现下载下来之后根本无法build!!,**这是由于build仓库和内核源码仓库不同步导致的**

![image-20230812144108245](https://bbs.kanxue.com/upload/attach/202308/963320_KN6A4YGXMDX846X.png)

当然你也可以选择进入[kernel/build](https://android.googlesource.com/kernel/build/+refs)中找到适合你的`build file`,不过我还是建议能一键编译就一键编译,比如我下载的`android-msm-crosshatch-4.9-android12`,`build`和`kernel source code`就是同步的(惨痛的教训,头铁想要用安卓9的内核源码编译,结果根本无法build...最后还是妥协把手机刷成安卓12了)

## 下载内核源码

| 123 | `mkdir` `android-kernel &&` `cd` `android-kernel``repo init -u https:``//android``.googlesource.com``/kernel/manifest` `-b android-msm-crosshatch-4.9-android12``repo` `sync` `-j4` |
|-|-|

## 切换git分支

我的手机的Linux内核版本为`Linux version 4.9.270-g862f51bac900-ab7613625`,`g`后面跟的是git分支,所以切换的分支为`862f51bac900`

| 12 | `cd` `private``/msm-google``git checkout 862f51bac900` |
|-|-|

# 编译内核源码

## 解包boot.img

首先下载[android-image-kitchen](https://forum.xda-developers.com/attachments/android-image-kitchen-v3-8-win32-zip.5300919/)

然后将`boot.img`放在工具的根目录下,这里的`boot.img`就是网上下载的刷机包解压之后其中的`boot.img`

![image-20230811184714849](https://bbs.kanxue.com/upload/attach/202308/963320_B6JZYZ8DF4YC7MU.png)

然后运行`unpackimg.bat`,运行之后的窗口请不要关闭,因为输出中有需要后续使用到的参数,当然也可以将输出的内容复制下来到txt中

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `Android Image Kitchen - UnpackImg Script``by osm0sis @ xda-developers` `Supplied image: boot.img` `Removing old work folders and files . . .` `Setting up work folders . . .` `Image` `type``: AOSP` `Signature with` `"AVBv2"` `type` `detected.` `Splitting image to` `"split_img/"` `. . .` `ANDROID! magic found at: 0``BOARD_KERNEL_CMDLINE console=ttyMSM0,115200n8 androidboot.console=ttyMSM0 printk.devkmsg=on msm_rtb.filter=0x237 ehci-hcd.park=3 service_locator.``enable``=1 cgroup.memory=nokmem lpm_levels.sleep_disabled=1 usbcore.autosuspend=7 loop.max_part=7 androidboot.boot_devices=soc``/1d84000``.ufshc androidboot.super_partition=system buildvariant=user``BOARD_KERNEL_BASE 0x00000000``BOARD_NAME``BOARD_PAGE_SIZE 4096``BOARD_HASH_TYPE sha1``BOARD_KERNEL_OFFSET 0x00008000``BOARD_RAMDISK_OFFSET 0x01000000``BOARD_SECOND_OFFSET 0x00000000``BOARD_TAGS_OFFSET 0x00000100``BOARD_OS_VERSION 12.0.0``BOARD_OS_PATCH_LEVEL 2021-10``BOARD_HEADER_VERSION 2``BOARD_HEADER_SIZE 1660``BOARD_DTB_SIZE 863100``BOARD_DTB_OFFSET 0x01f00000` `Unpacking ramdisk to` `"ramdisk/"` `. . .` `Compression used:` `gzip``56773 blocks` `Done!` `请按任意键继续. . .` |
|-|-|

当`unpackimg.bat`运行完毕后,我们进入`split_img/`,然后解压其中的`boot.img-ramdisk.cpio.gz`,并将解压后的`boot.img-ramdisk.cpio`文件复制到内核源码根目录中

| 1 | `root@oacia-virtual-machine:``/home/oacia/Desktop/``# docker cp boot.img-ramdisk.cpio Akernel:/android-kernel/` |
|-|-|

## 下载mkbootimg.py

我们还需要下载[mkbootimg.py](http://aospxref.com/android-11.0.0_r21/xref/system/tools/mkbootimg/mkbootimg.py),并将其复制到放到内核源码根目录

| 1 | `docker` `cp` `mkbootimg.py Akernel:``/android-kernel/` |
|-|-|

## 修改build.sh

在内核源码根目录,进入`build/build.sh`,找到下方代码的位置

| 12 | `echo` `"========================================================"``echo` `" Files copied to ${DIST_DIR}"` |
|-|-|

并在这两行代码之前加上下列命令

| 123 | `if` `[ -f` `"${VENDOR_RAMDISK_BINARY}"` `];` `then``cp` `${VENDOR_RAMDISK_BINARY} ${DIST_DIR}``fi` |
|-|-|

![image-20230811192125650](https://bbs.kanxue.com/upload/attach/202308/963320_H5J3UM8FPRGRKUB.png)

## 下载rwProcMem33

下载地址

| 1 | `https:``//github``.com``/abcz316/rwProcMem33` |
|-|-|

然后将解压后的文件夹复制到docker中内核源码目录下的`private/msm-google/drivers/`中

| 1 | `docker` `cp` `rwProcMem33 Akernel:``/android-kernel/private/msm-google/drivers/` |
|-|-|

## 修改rwProcMem33

### ver_control.h

将`MY_LINUX_VERSION_CODE`切换到对应的安卓内核版本,我们在下载内核源码阶段已经通过`cat /proc/version`知道了内核的版本号为`Linux version 4.9.270-g862f51bac900-ab7613625`,所以在`private/msm-google/drivers/rwProcMem33/ver_control.h`和`private/msm-google/drivers/rwProcMem33/hwBreakpointProcModule/hwBreakpointProc/ver_control.h`中我们也将内核切换到对应的`4.9`版本,选择`MY_LINUX_VERSION_CODE`的原则选这里出现的版本号中越接近自己手机内核版本的版本号

![image-20230813120617329](https://bbs.kanxue.com/upload/attach/202308/963320_F4BYD36TCJJJ275.png)

---

在`Linux 4.11`前,Linux内核把页表分为4级

- 页全局目录(Page Global Directory，PGD)
- 页上层目录(Page Upper Directory，PUD)
- 页中间目录(Page Middle Directory，PMD)
- 直接页表(Page Table，PT)

所以对于`Linux version 4.11`以下的内核版本,并不支持五级页表,选择`启用读取pagemap文件来计算物理内存的地址`,同时注释掉`启用页表计算物理内存的地址`如图所示
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/963320_2YU5QSXTCBYTQCY.png)
`Linux version 4.11`版本把页表扩展到五级,在页全局目录和页上层目录之间增加了页四级目录(Page 4th Directory，P4D)

所以对于`Linux version 4.11`及以上的内核版本,选择`启用页表计算物理内存的地址`,同时注释掉`启用读取pagemap文件来计算物理内存的地址`如图所示
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/963320_VH2VXYJDMBQ2J8E.png)

### linux_kernel_api文件夹

在`rwProcMem33/linux_kernel_api`文件夹中新建一个头文件`linux_kernel_api.h`
 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/963320_BB9RDKSREXH9NQS.png)
并写入如下内容

| 1234567891011121314151617181920212223 | `#ifndef LINUX_KERNEL_API_H_``#define LINUX_KERNEL_API_H_``#include "../ver_control.h"``#if MY_LINUX_VERSION_CODE < KERNEL_VERSION(5,8,0)` `long` `probe_kernel_read(``void``* dst,` `const` `void``* src,` `size_t` `size);` `MY_STATIC` `long` `x_probe_kernel_read(``void``* bounce,` `const` `char``* ptr,` `size_t` `sz) {``return` `probe_kernel_read(bounce, ptr, sz);``}` `#endif` `#if MY_LINUX_VERSION_CODE >= KERNEL_VERSION(5,8,0)` `long` `copy_from_kernel_nofault(``void``* dst,` `const` `void``* src,` `size_t` `size);` `MY_STATIC` `long` `x_probe_kernel_read(``void``* bounce,` `const` `char``* ptr,` `size_t` `sz) {``return` `copy_from_kernel_nofault(bounce, ptr, sz);``}` `#endif``#endif /* LINUX_KERNEL_API_H_ */` |
|-|-|

### api_proxy.h

为了包含`linux_kernel_api.h`头文件,我们在`api_proxy.h`的前几行中加入`#include "linux_kernel_api/linux_kernel_api.h"`如图

 ![图片描述](https://bbs.kanxue.com/upload/attach/202309/963320_7XG54SXK88DA3NQ.png)

## 修改drivers的Makefile

在`private/msm-google/drivers/Makefile`的开头加入下列命令

| 12 | `obj-y += rwProcMem33``/hwBreakpointProcModule/hwBreakpointProc/``obj-y += rwProcMem33/` |
|-|-|

## 修改msm-google的Makefile

在编译`rwProcMem33`内核模块时,由于内核编译时会将警告视为错误导致编译内核停止,所以我们要修改Makefile来忽视warning

在`private/msm-google/Makefile`找到如下位置,在`-Wno-format-security`后加上一个`-w`参数

![image-20230816235239736](https://bbs.kanxue.com/upload/attach/202308/963320_MFFQ6TSK7H673BG.png)

## 开始编译

在安卓内核源码的根目录打开终端使用如下命令开始编译

>
>  命令的参数为使用`android-image-kitchen`解包`boot.img`之后,控制台所打印的参数请务必替换为相对应的参数!!!
>
>
>

参数对应关系为

| `android-image-kitchen`解包参数名称 | 值 | 编译命令参数名称 |
|-|-|-|
| BOARD_KERNEL_CMDLINE | console=ttyMSM0,115200n8 androidboot.console=ttyMSM0 printk.devkmsg=on msm_rtb.filter=0x237 ehci-hcd.park=3 service_locator.enable=1 cgroup.memory=nokmem lpm_levels.sleep_disabled=1 usbcore.autosuspend=7 loop.max_part=7 androidboot.boot_devices=soc/1d84000.ufshc androidboot.super_partition=system buildvariant=user | KERNEL_CMDLINE |
| BOARD_KERNEL_BASE | 0x00000000 | BASE_ADDRESS |
| BOARD_PAGE_SIZE | 4096 | PAGE_SIZE |
| BOARD_HEADER_VERSION | 2 | BOOT_IMAGE_HEADER_VERSION |

编译命令中的`BUILD_CONFIG`为AOSP源码根目录的`build.config`的软连接所指向的配置文件

![image-20230812145430979](https://bbs.kanxue.com/upload/attach/202308/963320_SCTQ3S5JTATEDRE.png)

所以最终的编译命令为

| 1 | `BUILD_CONFIG=private``/msm-google/build``.config.bluecross BUILD_BOOT_IMG=1 MKBOOTIMG_PATH=mkbootimg.py VENDOR_RAMDISK_BINARY=boot.img-ramdisk.cpio KERNEL_BINARY=Image.lz4 BOOT_IMAGE_HEADER_VERSION=2 KERNEL_CMDLINE=``"console=ttyMSM0,115200n8 androidboot.console=ttyMSM0 printk.devkmsg=on msm_rtb.filter=0x237 ehci-hcd.park=3 service_locator.enable=1 cgroup.memory=nokmem lpm_levels.sleep_disabled=1 usbcore.autosuspend=7 loop.max_part=7 androidboot.boot_devices=soc/1d84000.ufshc androidboot.super_partition=system buildvariant=user"` `BASE_ADDRESS=0x00000000 PAGE_SIZE=4096 build``/build``.sh` |
|-|-|

经过一段时间的等待,编译成功!

![image-20230813121805073](https://bbs.kanxue.com/upload/attach/202308/963320_SC42B8MGHAF7JG5.png)

生成的`boot.img`的路径为`/android-kernel/out/android-msm-pixel-4.9/dist/boot.img`

# 使用Magisk修补boot.img实现root

安装Magisk [下载地址](https://github.com/topjohnwu/Magisk/releases)

| 1 | `adb` `install` `"D:\TOOLS\pixel3\Magisk-v26.1.apk"` |
|-|-|

将由内核源码编译出来的`boot.img`上传到手机上

| 1 | `adb push boot.img` `/sdcard/` |
|-|-|

然后在手机上打开`Magisk`,依次点击`安装->选择并修补一个文件->/sdcard/boot.img->开始`

待修补完成后,将修补后的`boot.img`传到电脑上

| 1 | `adb pull` `/storage/emulated/0/Download/magisk_patched-xxxxx_xxxxx``.img` |
|-|-|

# 刷入内核

| 123 | `adb reboot bootloader``fastboot flash magisk_patched-xxxxx_xxxxx.img``fastboot reboot` |
|-|-|

# 编译HwBpClient客户端

进入`rwProcMem33\hwBreakpointProcModule\testHwBpClient`文件夹,双击`testHwBpClient.vcxproj`在`visual studio`中打开

编译的程序位数应为**64位**

对于**Windows平台**编译的`HwBpClient`,并且需要在`testHwBpClientDlg.cpp`的这个位置进行修改,将这个位置的`llX`改为`I64X`,`%zu`改成`I64d`,否则将无法正确输入内容

 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/963320_FFJTQZMHD5VYCF8.webp)

原因在于C/C++输出64位数在window下和linux下是不一样的

linux

| 123 | `printf``(``"%lld/n"``,a);``printf``(``"%llu/n"``,a);``printf``(``"%llx/n"``,a);` |
|-|-|

windows

| 123 | `printf``(``"%I64d/n"``,a);``printf``(``"%I64u/n"``,a);``printf``(``"%I64x/n"``,a);` |
|-|-|

修改完成后如图所示

 ![图片描述](https://bbs.kanxue.com/upload/attach/202403/963320_W3WFU5UNN4BSN9Z.webp)

接下来按下ctrl+B生成即可

![image-20230816194207598](https://bbs.kanxue.com/upload/attach/202308/963320_KHJ9X4BKEV3M6Z9.png)

# 编译HwBpServer服务端

编译HwBpServer服务端需要NDK,并将NDK引入环境变量中

NDK可以在`android studio`中进行安装,依次点击`File->Project Structure->SDK Location`,找到`Android NDK location`,点击`Download`即可开始安装,我这里使用的ndk的版本为`ndk25.2.9519653`

如果没有安装`Android studio`,NDK的安装方法可以在谷歌上找到

NDK安装完成后,进入到`rwProcMem33\hwBreakpointProcModule\testHwBpServer\jni`,打开cmd运行命令

| 1 | `ndk-build` |
|-|-|

即可完成编译,编译后的文件在`rwProcMem33\hwBreakpointProcModule\testHwBpServer\libs`中,选择对应手机架构的ELF,`push`到手机中运行即可

# 获取手机的IPv4地址

将电脑和我们的测试手机连接**同一个手机热点**,然后在测试手机中打开`设置->WLAN`点击我们连接的热点的高级选项,来查看手机的IP地址

# 运行HwBpServer服务端

将编译出来的程序复制到手机中并运行

| 123456 | `adb push rwProcMem33\hwBreakpointProcModule\testHwBpServer\libs\arm64-v8a\testHwBpServer.out` `/data/local/tmp``adb shell``su``cd` `/data/local/tmp``chmod` `777 testHwBpServer.out``.``/testHwBpServer``.out` |
|-|-|

查看打印出来的端口号`3170`

![image-20230816221255328](https://bbs.kanxue.com/upload/attach/202308/963320_ASHSYVFXXSPRC3P.png)

# 运行HwBpClient客户端

在电脑中运行编译完成的HwBpClient客户端,填入手机的IP地址以及由`testHwBpServer.out`打印出来的端口号

![image-20230816221420002](https://bbs.kanxue.com/upload/attach/202308/963320_CUZGWHFHDT9Q8Y7.png)

点击连接即可开始打硬件断点

![image-20230816221529230](https://bbs.kanxue.com/upload/attach/202308/963320_62SPJPAK3XF96Q6.png)

# 查询进程PID

| 1 | `ps` `-A` |
|-|-|

# 查询目标so的基址

可以使用命令来查询

| 1 | `cat` `/proc/``[app的PID]``/maps` |
|-|-|

也可以使用下面的frida脚本查询so的基址

| 12345678910111213141516 | `function` `dump_so(so_name) {``Java.perform(``function` `() {``var` `currentApplication = Java.use(``"android.app.ActivityThread"``).currentApplication();``var` `dir = currentApplication.getApplicationContext().getFilesDir().getPath();``var` `libso = Process.getModuleByName(so_name);``console.log(``"[name]:"``, libso.name);``console.log(``"[base]:"``, libso.base);``console.log(``"[size]:"``, ptr(libso.size));``console.log(``"[path]:"``, libso.path);``}``});``}` `rpc.exports = {``dump_so: dump_so``};` |
|-|-|

接下来就可以愉快的打硬件断点啦~

# 参考资料

- [[原创]开源一个Linux内核里进程内存管理模块源码](https://bbs.kanxue.com/thread-259317.htm)
- [万字长文教你使用安卓内核驱动进行内存读写](https://blog.csdn.net/qq_46832407/article/details/129971512)
- [安卓内核驱动编译](https://www.bilibili.com/video/BV1hR4y1k795)
- [AOSP Android 10内核编译刷入Pixel3](https://www.sunofbeach.net/a/1624287020915548162)
- [kernel编译的哪些坑](https://zhuanlan.zhihu.com/p/582258078)
- [eBPF on Android之打补丁和编译内核修正版](https://blog.seeflower.dev/archives/174/)
- [Android10 内核编译笔记](https://bbs.kanxue.com/thread-277224.htm#msg_header_h2_4)

---

# 回复

## 回复 by 万里星河 (#2)

*2023-8-31 19:46*

当初要有这篇雄文 也不至于摸索一周才编译出来![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by mb_kbkqyusp (#3)

*2023-8-31 19:59*

又涨见识了，太吊了这个
![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by mb_mndqtppt (#4)

*2023-8-31 21:13*

QQ附近人大佬有把

## 回复 by 值得怀疑 (#5)

*2023-8-31 22:03*

你好，我大概看了下是要在docker下编译吗，还是不在docker 下也可以，你虚拟机下装docker 这性能可以吗？

## 回复 by oacia (#6)

*2023-8-31 22:37*

>
> [值得怀疑](https://bbs.kanxue.com/user-396746.htm)
>
>  你好，我大概看了下是要在docker下编译吗，还是不在docker 下也可以，你虚拟机下装docker 这性能可以吗？
>
>

不在docker下编译也是可以的;
docker的性能由虚拟机的配置决定,docker 仅仅虚拟了用户空间,和虚拟机共用的是同一个内核,所以我文中提到的<修改交换区大小>修改的也是虚拟机的交换区大小

## 回复 by 秋狝 (#7)

*2023-9-1 09:09*

感谢分享

## 回复 by mudebug (#8)

*2023-9-1 10:01*

感谢分享

## 回复 by kkte (#9)

*2023-9-1 11:46*

这个思路很好啊，

## 回复 by Archar (#10)

*2023-9-1 17:20*

感谢分享

## 回复 by 白菜大哥 (#11)

*2023-9-1 21:54*

啥型号的手机，方便分享个ROM吗？

## 回复 by oacia (#12)

*2023-9-1 22:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  白菜大哥](https://bbs.kanxue.com/user-649095.htm)
>
>  啥型号的手机，方便分享个ROM吗？
>
>

我的手机是pixel3,pixel或者nexus系列手机的刷机包可以直接在https://developers.google.com/android/images?hl=zh-cn下载,其他型号的手机去网上找找有没有相关的刷机包吧,想起来之前有刷过一次三星手机SM-P200,当时那个刷机包还是我在网上买来的![image](https://bbs.kanxue.com/view/img/face/78.gif)

## 回复 by 龙飞雪 (#13)

*2023-9-1 22:50*

不错，感谢分享

## 回复 by 霸气压萝莉 (#14)

*2023-9-1 22:55*

学到了

## 回复 by 白菜大哥 (#15)

*2023-9-2 18:23*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  我的手机是pixel3,pixel或者nexus系列手机的刷机包可以直接在https://developers.google.com/android/images?hl=zh-cn下载,其他型号的手机 ...
>
>

感谢，我看看有没有便宜的，我是想直接白嫖一下你改好的ROM![image](https://bbs.kanxue.com/view/img/face/6.gif)

## 回复 by NPC2000 (#16)

*2023-9-3 20:24*

![image](https://bbs.kanxue.com/upload/attach/202309/962943_7RB9UGCH8A568ZT.jpg)大佬，加-w会还是显示这种报错，pixel3 android12 内核

## 回复 by oacia (#17)

*2023-9-3 20:56*

>
> [NPC2000](https://bbs.kanxue.com/user-962943.htm)
>
>  大佬，加-w会还是显示这种报错，pixel3 android12 内核

看了下这个报错是没声明p4d,我记得在linux4.11才能用五级页表来着,看来文章还是有写的不太严谨的地方![image](https://bbs.kanxue.com/view/img/face/85.gif),我刚刚改了一下文章中修改ver_control.h这儿的内容,你可以重新编译试试看

## 回复 by NPC2000 (#18)

*2023-9-4 12:10*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>
>
>
>
>
>
>  NPC2000
>
>  大佬，加-w会还是显示这种报错，pixel3 android12 内核 看了下这个报错是没声明p4d,我记得在linux4.11 ...
>
>

感谢大佬，这次成功了

## 回复 by shinratensei (#19)

*2023-9-4 13:39*

tql

## 回复 by cmputer (#20)

*2023-9-4 15:27*

感谢分享

## 回复 by 你瞒我瞒 (#21)

*2023-9-5 09:28*

在刷入内核的步骤遇到问题了：然后再手机上打开Magisk,依次点击安装->选择并修补一个文件->/sdcard/boot.img->开始

待修补完成后,将修补后的boot.img传到电脑上adb pull /storage/emulated/0/Download/magisk_patched-xxxxx_xxxxx.img，这里是拿到了修补的boot，这个boot，我记得是需要刷到设备上面才能实现root。下面刷入的boot是在内核编译完成的？那么上面面具修补的boot好像没用到？

## 回复 by oacia (#22)

*2023-9-5 11:33*

哦哦抱歉![image](https://bbs.kanxue.com/view/img/face/85.gif)关于修补boot.img实现root这一部分的内容,我是直接从以前我做的笔记这里复制过来的,这里相关的内容还没有进行修改,所以造成了误导
这里使用Magisk修补的boot.img,应该是由内核源码编译出来的boot.img,而不是从刷机包中解包出来的boot.img,文章内的相关内容已经进行修正,感谢指出![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by Yuusha (#23)

*2023-9-5 11:37*

'

## 回复 by oacia (#24)

*2023-9-5 11:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Yuusha](https://bbs.kanxue.com/user-951896.htm)
>
>  刷了后卡android&nbsp;log,但adb能用,猜测是模块加载验证之类的问题,根据这篇文章关闭验证后https://bbs.kanxue.com/thread-264295.htm,启 ...
>
>

因为不是使用insmod的方式安装内核模块而是直接把内核模块编译进内核,这应该是不需要模块验证的,你用lsmod看看有没有硬件断点相关的内核模块

## 回复 by Yuusha (#25)

*2023-9-5 15:49*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  因为不是使用insmod的方式安装内核模块而是直接把内核模块编译进内核,这应该是不需要模块验证的,你用lsmod看看有没有硬件断点相关的内核模块

'

## 回复 by oacia (#26)

*2023-9-5 16:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Yuusha](https://bbs.kanxue.com/user-951896.htm)
>
>  刷好后一直卡安卓log,卡了几分钟后可以进系统但没触屏了,用adb lsmod命令也没看见rwProcMem33相关的,不知道为什么,还有就是把module.c的check_verion函数返回值改为 ...
>
>

如果仅仅编译内核模块的话是不需要修改其他任何的内核源码的,触屏或者其他系统相关的功能失效,有可能是刷进去的内核型号和原本的内核型号不匹配导致的,另外手机的内核源码如果没有被官方公开的话,用谷歌官网的通用内核源码编译之后刷到手机里面,也有可能导致功能异常

## 回复 by 你瞒我瞒 (#27)

*2023-9-6 14:41*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  哦哦抱歉[em_85]关于修补boot.img实现root这一部分的内容,我是直接从以前我做的笔记这里复制过来的,这里相关的内容还没有进行修改,所以造成了误导
> 这里使用Magisk修补的boot.i ...
>
>

现在虽然编译成功了，但是不知道这个东西有啥用途，和使用的案例，GitHub只有代码，没有文档怎么用![image](https://bbs.kanxue.com/view/img/face/85.gif)

## 回复 by oacia (#28)

*2023-9-6 17:38*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  现在虽然编译成功了，但是不知道这个东西有啥用途，和使用的案例，GitHub只有代码，没有文档怎么用[em_85]
>
>

我在我发的另一篇文章https://bbs.kanxue.com/thread-278648.htm中用到了这个工具,在那篇文章中我利用这个工具找到了crc的检测点,当然这个工具能做的不仅仅是打硬件断点,自行调用驱动的接口可以实现更多的功能

## 回复 by abcz316 (#29)

*2023-9-7 00:08*

tql，x_probe_kernel_read这个地方还是不建议去修改，面具源码里面也是全部API都加上x_，以代表一个api proxy的概念

## 回复 by 淡然他徒弟 (#30)

*2023-9-7 12:27*

mark

## 回复 by chaodchen (#31)

*2023-9-7 13:42*

大佬帮我看看这个问题咋回事 pixel4 4.14的内核 android12系统

![image](https://bbs.kanxue.com/upload/attach/202309/953173_5H7V2N7BBYZFKK6.jpg)

## 回复 by oacia (#32)

*2023-9-7 15:04*

>
> [abcz316](https://bbs.kanxue.com/user-892833.htm)
>
>  tql，x_probe_kernel_read这个地方还是不建议去修改，面具源码里面也是全部API都加上x_，以代表一个api proxy的概念
>
>

大佬您的代码真的学习到了![image](https://bbs.kanxue.com/view/img/face/67.gif)原来用api proxy的方式就可以通过不修改核心的代码,而是修改配置选项头文件的方法就可以达到预期的效果,我直接修改核心代码的方法应该是仅仅解了燃眉之急![image](https://bbs.kanxue.com/view/img/face/85.gif)
另外我发现在linux_kernel_api的文件夹中,只有当MY_LINUX_VERSION_CODE为一个确切的版本时,才会对x_probe_kernel_read做出定义,要是没有匹配上MY_LINUX_VERSION_CODE版本,那x_probe_kernel_read函数可能会出现未定义的情况
我通过查阅资料https://elixir.bootlin.com/linux/v5.8/source/mm/maccess.c发现内核内存拷贝函数是在Linux5.8由probe_kernel_read更换为copy_from_kernel_nofault的,我感觉要是以Linux版本的范围来对x_probe_kernel_read做定义,应该会有助于减少不同版本的内核编译过程中的报错现象

## 回复 by chaodchen (#33)

*2023-9-7 15:05*

>
> [chaodchen](https://bbs.kanxue.com/user-953173.htm)
>
>  大佬帮我看看这个问题咋回事 pixel4 4.14的内核 android12系统
>
>

找到问题了testMemSearch 在连接驱动的时候没有传文件描述符

## 回复 by mb_sdxbepyu (#34)

*2023-9-8 03:26*

意思是Linux version 4.11以下的内核版本只能用pagemap获取物理地址吗

## 回复 by 你瞒我瞒 (#35)

*2023-9-8 09:16*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  我在我发的另一篇文章https://bbs.kanxue.com/thread-278648.htm中用到了这个工具,在那篇文章中我利用这个工具找到了crc的检测点,当然这个工具能做的不仅仅是打硬件断 ...
>
>

看了这个文章，整个流程很小详细，但是小白的我跟着操作不来，特别是so部分，现在发现stalker跟踪so函数调用，我先学习这个，感谢感谢。

## 回复 by 轻快笑着行 (#36)

*2023-9-8 16:06*

先赞再看，谢谢分享

## 回复 by Yuusha (#37)

*2023-9-8 17:41*

直接buld/build.sh在编译成boot.img,这样就会有问题,照着楼主的解包方式弄就可以,不知道为什么求指教

## 回复 by 东方玻璃 (#38)

*2023-9-12 23:26*

请问大佬编译内核时报错如下怎么解决
/home/glass/android-kernel/Pixel3XL/android12/private/msm-google/Makefile:1126: recipe for target 'drivers' failed
make[2]: *** [drivers] Error 2
Makefile:152: recipe for target 'sub-make' failed
make[1]: *** [sub-make] Error 2
Makefile:24: recipe for target '__sub-make' failed
make: *** [__sub-make] Error 2

## 回复 by 东方玻璃 (#39)

*2023-9-13 13:42*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  请问大佬编译内核时报错如下怎么解决
> /home/glass/android-kernel/Pixel3XL/android12/private/msm-google/Makefile:1126: r ...
>
>

之前用的ubuntu18.04,今天换了20.04编译成功

## 回复 by oacia (#40)

*2023-9-13 17:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_sdxbepyu](https://bbs.kanxue.com/user-951016.htm)
>
>  意思是Linux version 4.11以下的内核版本只能用pagemap获取物理地址吗
>
>

是的,因为linux4.11以下没有五级页表

## 回复 by oacia (#41)

*2023-9-13 17:23*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>
>  之前用的ubuntu18.04,今天换了20.04编译成功
>
>

![image](https://bbs.kanxue.com/view/img/face/78.gif)看来是环境问题,其实可以试试docker的,这样编译环境就不会有偏差了

## 回复 by pexillove (#42)

*2023-9-15 18:35*

大佬你用的vs是哪个版本,我用vs2022报错

## 回复 by oacia (#43)

*2023-9-15 19:37*

>
> [pexillove](https://bbs.kanxue.com/user-956077.htm)
>
>  大佬你用的vs是哪个版本,我用vs2022报错
>
>

我用的是vs2022,可以顺利编译的

## 回复 by pexillove (#44)

*2023-9-15 19:47*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  我用的是vs2022,可以顺利编译的
>
>

![image](https://bbs.kanxue.com/upload/attach/202309/956077_YSBAHSMU63YZPDP.jpg)

## 回复 by pexillove (#45)

*2023-9-15 19:48*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  我用的是vs2022,可以顺利编译的
>
>

就像图中那样

## 回复 by oacia (#46)

*2023-9-15 22:38*

>
> [pexillove](https://bbs.kanxue.com/user-956077.htm)
>

可能是你的visual studio没有装MFC组件,去visual studio installer里面安装一下就可以了

## 回复 by pexillove (#47)

*2023-9-16 11:42*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  可能是你的visual studio没有装MFC组件,去visual studio installer里面安装一下就可以了
>
>

昨天看了一下报错日志,解决了,谢谢

## 回复 by cming0420 (#48)

*2023-10-7 22:28*

太赞了，这就去尝试一下![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 牛马丶出生 (#49)

*2023-10-11 06:55*

大佬  请问内核的签名校验怎么过?

## 回复 by oacia (#50)

*2023-10-11 16:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rgvaqlss](https://bbs.kanxue.com/user-963177.htm)
>
>  大佬 请问内核的签名校验怎么过?
>
>

将内核模块直接编译到内核中是没有签名校验的,将boot.img刷入手机之后会发现模块直接就装上去了

## 回复 by 江来一定会有 (#51)

*2023-10-19 15:10*

感谢分享，文档前面一些改注释部分的解释确实省了不少时间，但是如果想用好这个功能，还是得自己熟悉源码。
我是直接obj-m 编译成ko加载使用的。总的来说，这个hw_breakpoint是在内核模块进行register bp并完成回调并记录，在用户态通过ioctl与内核模块通信拿到记录信息的模式，这个其实不太灵活，如果有办法能把回调直接暴露给用户态使用就更好了。

## 回复 by 凉皮不要蒜 (#52)

*2023-10-28 16:02*

好奇怪。我用的android-msm-coral-4.14-android13 ，然后切换的自己分支是安卓12的：git checkout 82a738b32e3f
结果编译后 没有boot.img文件。。

我是4.14.257  安卓12的。

> BUILD_CONFIG=private/msm-google/build.config.floral
>
> BUILD_BOOT_IMG=1
>
> MKBOOTIMG_PATH=mkbootimg.py
>
> VENDOR_RAMDISK_BINARY=boot.img-ramdisk.cpio
>
> KERNEL_BINARY=Image.lz4
>
> BOOT_IMAGE_HEADER_VERSION=2
>
> KERNEL_CMDLINE="console=ttyMSM0,115200n8
>
> androidboot.console=ttyMSM0 printk.devkmsg=on msm_rtb.filter=0x237
>
> ehci-hcd.park=3 service_locator.enable=1 androidboot.memcg=1
>
> cgroup.memory=nokmem usbcore.autosuspend=7
>
> androidboot.usbcontroller=a600000.dwc3 swiotlb=2048
>
> androidboot.boot_devices=soc/1d84000.ufshc loop.max_part=7
>
> buildvariant=user"
>
> BASE_ADDRESS=0x00000000
>
> PAGE_SIZE=4096
>
> build/build.sh
>
>
>
>
>

## 回复 by mb_ckpefbiq (#53)

*2023-12-19 15:25*

有邮箱吗，咨询下 kernel 6.1.25 android 14 ，编译的问题

## 回复 by sanqiu (#54)

*2023-12-25 20:35*

怎么判断模块是否被成功编译到内核了

## 回复 by oacia (#55)

*2023-12-25 22:08*

>
> [sanqiu](https://bbs.kanxue.com/user-932657.htm)
>
>  怎么判断模块是否被成功编译到内核了
>
>

在adb shell输入命令ls sys/module/ ,如果编译的模块名称出现在这里面就说明模块被成功编译到内核了

## 回复 by sanqiu (#56)

*2023-12-26 15:37*

>
> [oacia](https://bbs.kanxue.com/user-963320.htm)
>
>  在adb shell输入命令ls sys/module/ ,如果编译的模块名称出现在这里面就说明模块被成功编译到内核了
>
>

真奇怪 ，我是用-y编译进内核了，用dmesg也查看到了log打印了，sys/module/没有显示模块，这算是编译成功了吗？

## 回复 by 你瞒我瞒 (#57)

*2024-1-2 14:52*

>
> [chaodchen](https://bbs.kanxue.com/user-953173.htm)
>
>  找到问题了testMemSearch 在连接驱动的时候没有传文件描述符
>
>

传递文件描述符是什么意思，可以给出一个详细的例子嘛

## 回复 by Amun (#58)

*2024-1-2 16:19*

涉及内核的功能，可以用 waydroid 和 redroid，省时省力，珍惜生命![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 珍惜Any (#59)

*2024-1-3 16:28*

inlinehook用的啥，你用的啥和应用层通讯的。

## 回复 by neilwu (#60)

*2024-1-18 17:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  当初要有这篇雄文 也不至于摸索一周才编译出来[em_5]
>
>

请问 大佬是用 pixel sailfish 的内核 android-msm-marlin-3.18-pie-qpr2 编译出来的吗？

## 回复 by misskings (#61)

*2024-1-26 18:28*

我看着好像hwBreakpointProc模块好像并没有依赖上层的rwProcMem33模块，貌似rwProcMem33这个模块是testKo这里用的。testKo这个感觉是个测试内核模块的代码，猜测是不是只需要hwBreakpointProc就行了。毕竟服务端里面访问的驱动设备是hwBreakpointProc的

## 回复 by misskings (#62)

*2024-2-6 13:58*

4.14编译报错

/home/king/android_src/pixelExper_thirteen/kernel/google/msm-4.14/drivers/rwProcMem33/phy_mem.h:176:93: error: member reference type 'pgd_t *' is a pointer
; did you mean to use '->'?
        printk_debug("init_mm pgd val:0x%lx,pgd addr:0x%lx\n", (unsigned long)pgd_val(*(mm->pgd)), pgd_val((mm->pgd)));
                                                                                                   ^~~~~~~~~~~~~~~~~~
/home/king/android_src/pixelExper_thirteen/kernel/google/msm-4.14/arch/arm64/include/asm/pgtable-types.h:50:24: note: expanded from macro 'pgd_val'
#define pgd_val(x)      ((x).pgd)

## 回复 by misskings (#63)

*2024-2-7 01:07*

而且就算编译成功了。但是也看不到/sys/module/rwProcMem37，奇怪了。我在aosp的内核分支上测试还是正常的。换了个rom的内核就不行了

## 回复 by misskings (#64)

*2024-2-7 01:17*

哦。原来我编译的是在/vendor/lib/modules这个目录下。

## 回复 by goldenegg (#65)

*2024-2-15 21:28*

比较好奇你的VS版本，你说需要把lld改成I64d这些，但是VS早就支持lld/llx这些格式了啊

## 回复 by dadadasda (#66)

*2025-4-9 12:54*

额，kernel有内置的access_remote_vm或者access_process_vm接口，注意好权限检查和锁就行，再搞一个页表查询有必要吗。

## 回复 by JSnow (#67)

*2025-10-23 14:39*

android9内核编译了2天编译不出来才看到这篇帖子(

## 回复 by 龙飞雪 (#68)

*2025-11-6 15:42*

学习了，感谢分享。

## 回复 by yaoqianshuj (#69)

*2026-2-26 18:22*

大佬请教一下，按你的步骤编译刷机之后，在logo页面和pause界面卡住循环了，有遇到过吗
