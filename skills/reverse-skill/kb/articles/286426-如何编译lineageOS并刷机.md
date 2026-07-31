---
title: '[原创]如何编译lineageOS并刷机'
url: https://bbs.kanxue.com/thread-286426.htm
tid: 286426
author: b1n_
date: '2025-04-10'
tags: [Android安全, 原创, 基础理论, 程序开发, 系统相关, 源码框架, 其他]
crawled_at: '2026-07-31T14:12:03+08:00'
replies: 14
---

作者通过自己踩坑发现网上并没有一份很完美的编译lineageOS的教程，作者结合官网和踩坑之后，出一份详细的编译记录，帮助各个苦苦寻找好用的lineage编译文章。遇到问题一定要看清楚文字各位亲们。

# 环境

编译主机 ubuntu 20.04 真的别用其他的版本，坑太多了。如果你的ubuntu是其他版本，建议自己去lineage官网查看安装需要的库。

设备是 flame，编译lineageOS18版本。其他版本也可以参考本文章，反正写的够详细，能踩得坑都记录下来了。

# 步骤

## 安装platform-tools

一定要记住platform-tools的安装目录，作者安装在了 ~/android/platform-tools 目录中

```plain
mkdir -p ~/android/platform-tools

cd ~/android/platform-tools

wget https://dl.google.com/android/repository/platform-tools-latest-linux.zip
```

然后将platform-tools添加到环境变量中，作者喜欢用vim去编辑

```plain
vim ~/.profile
```

然后将下面的内容添加到~/.profile的最下面，这里记得改成你的platform-tools的路径

```plain
# add Android SDK platform tools to path
if [ -d "$HOME/platform-tools" ] ; then
    PATH="$HOME/platform-tools:$PATH"
fi
```

添加成功之后，刷新环境，然后看看adb有没有成功添加到环境变量中，如果没有说明上一步的路径有问题

```plain
source ~/.profile
```

## 安装构建软件包

这里的软件包容易踩坑，官网的给的软件包并不合适，所以作者用的下面的能够成功去编译

```plain
sudo apt-get update

sudo apt-get install bc bison build-essential ccache curl flex g++-multilib gcc-multilib git git-lfs gnupg gperf imagemagick lib32ncurses5-dev lib32readline-dev lib32z1-dev libelf-dev liblz4-tool libncurses5 libncurses5-dev libsdl1.2-dev libssl-dev libxml2 libxml2-utils lzop pngcrush rsync schedtool squashfs-tools xsltproc zip zlib1g-dev m4
```

## JDK&python

18的话用OpenJDK 11，直接安装就好，安装好了之后运行 java --version 检查有没有安装成功

```plain
sudo apt update
sudo apt install openjdk-11-jdk
```

python可以直接将系统的python3软连接成python就可以了

```plain
sudo ln -s /usr/bin/python3 /usr/bin/python
```

## 创建项目目录

创建项目的根目录，准备拉取指定的源码了。~/bin为了放repo，~/android/lineage放安卓源码

```plain
mkdir -p ~/bin
mkdir -p ~/android/lineage
```

### 安装repo并设置环境变量

进入 ~/bin 目录中

```plain
cd ~/bin
curl https://storage.googleapis.com/git-repo-downloads/repo > ~/bin/repo
chmod a+x ~/bin/repo
```

然后将repo目录添加到环境变量中

```plain
vim ~/.profile
```

将下面的内容添加到上面的文件中的最下面，注意要对应自己的repo所在的目录中

```plain
# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi
```

然后运行 source ~/.profile 刷新环境变量

```plain
source ~/.profile
```

## 配置git

随便填

```plain
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

## 开启缓存

开启缓存加快同步代码的速度，如果你的硬盘足够大，超过500G，ccache指定的大小可以是100G，如果没有就指定50G

```plain
export USE_CCACHE=1
export CCACHE_EXEC=/usr/bin/ccache

ccache -M 100G
ccache -o compression=true
```

## 初始化lineageos源存库

```plain
cd ~/android/lineage

repo init -u https://github.com/LineageOS/android.git -b lineage-18.1 --git-lfs --no-clone-bundle
```

执行下面的命令是下载源码，你可以根据当前ubuntu的CPU核心数量去指定线程数量，一般是核心数量的2倍。作者的核心数量是10，所以指定20线程。注意，同步过程中有报错是正常的，因为官方会限制短期的请求数量，不用管继续等就好了。

```plain
repo sync -j 20
```

这条命令执行完毕之后，记得再执行 repo status 查看当前的同步状态，如果出现nothing to commit这种字眼说明同步完成了，可以不用看下面的注意了。同步完成之后，就是源代码拉去完毕了，可以进行下一个步骤了。

注意， 没有出现上面提到的字眼就是失败了，失败的话建议执行 repo sync 命令去补全，注意最好不要指定多线程。

```plain
repo sync
```

## 准备特定于设备的代码

进入到安卓源码项目的根目录，然后运行下面的命令用来下载设备的特定配置和内核。这里的flame是我的设备代号，其他的设备代号需要自己查然后把flame替换成自己的设备代号

```plain
cd ~/android/lineage

source build/envsetup.sh
breakfast flame
```

第一次运行breakfast 命令，会出现下面的错误，我觉得这里是最大的坑

```plain
kerneldev@ubuntu:~/android/lineage$ breakfast flame
In file included from build/make/core/config.mk:291:
In file included from build/make/core/envsetup.mk:266:
device/google/coral/device-lineage.mk:113: error: _nic.PRODUCTS.[[device/google/coral/lineage_flame.mk]]: "vendor/google/flame/flame-vendor.mk" does not exist.
19:31:40 dumpvars failed with: exit status 1
Device flame not found. Attempting to retrieve device repository from LineageOS Github (http://github.com/LineageOS).
Found repository: android_device_google_flame
Default revision: lineage-18.1
Checking branch info
Checking if device/google/flame is fetched from android_device_google_flame
LineageOS/android_device_google_flame already fetched to device/google/flame
Syncing repository to retrieve project.
Fetching: 100% (1/1), done in 0.511s
Checking out: 100% (1/1), done in 0.001s
repo sync has finished successfully.
Repository synced!
Looking for dependencies in device/google/flame
Looking for dependencies in device/google/coral
Looking for dependencies in kernel/google/coral
kernel/google/coral has no additional dependencies.
Looking for dependencies in packages/apps/ElmyraService
packages/apps/ElmyraService has no additional dependencies.
Done
In file included from build/make/core/config.mk:291:
In file included from build/make/core/envsetup.mk:266:
device/google/coral/device-lineage.mk:113: error: _nic.PRODUCTS.[[device/google/coral/lineage_flame.mk]]: "vendor/google/flame/flame-vendor.mk" does not exist.
19:31:43 dumpvars failed with: exit status 1
In file included from build/make/core/config.mk:291:
In file included from build/make/core/envsetup.mk:266:
device/google/coral/device-lineage.mk:113: error: _nic.PRODUCTS.[[device/google/coral/lineage_flame.mk]]: "vendor/google/flame/flame-vendor.mk" does not exist.
19:31:44 dumpvars failed with: exit status 1

** Don't have a product spec for: 'lineage_flame'
** Do you have the right repo manifest?
```

关键的字眼就是 "vendor/google/flame/flame-vendor.mk" does not exist. 这个内容，原因是这个时候设备的特定内容还没有被拉取到当前的项目中，所以构建设备镜像的时候出现这个错误。下面是解决方案

### 解决 breakfast 的错误

官网提供了两种解决方式，但是我觉得官网提供的两种方式都不方便，所以这里用作者自己摸索出来的解决方案，因为操作起来是真的简单

首先创建 ~/android/system_dump/ 目录然后进入

```plain
mkdir ~/android/system_dump/

cd ~/android/system_dump/
```

因为这个问题出现的原因是当前的项目中缺少了指定设备的特定内容，所以不给我们构建，那么我们可以自己去提取现成的特定内容

#### 提取设备特定内容

这个时候需要你进入到 <https://lineage-archive.timschumi.net/> 这个网站中，然后去找到自己对应型号对应版本的包下载下来，注意他一个型号一个版本可能会有多个包，随便下载一个就可以，下载好之后把里面的 payload.bin 文件解压出来。

windows电脑使用 <https://pan.quark.cn/s/bf6a4ce548aa> 工具，首先把payload.bin放进这个工具的目录中然后双击 打开CMD命令行.bat 文件就可以了，然后按 a 全部提取出来。全部提取出来的镜像保存在当前的目录的 img 目录中

linux电脑使用 <https://pan.quark.cn/s/318bd8bf5fe1> 工具，直接 payload-dumper-go payload.bin

 执行就好。

然后把提取出来的镜像全部拷贝到 ~/android/system_dump/ 目录中，对于lineageOS18系统，需要挂载下面这些镜像，其他的可以参考自己解包内容是否含有这些镜像，然后去挂载。高版本会有更多的镜像，作者也没办法去具体判断需要挂在哪些，但是作者能够给到一个技巧，就是如果这里你挂载的不够，那么在 编译 部分会出现文件找不到的问题，如果你确认了报错的文件在项目中没有，那说明这里少挂载了。

```plain
cd ~/android/system_dump/

mkdir system/

sudo mount -o ro system.img system/
sudo mount -o ro vendor.img vendor/
sudo mount -o ro product.img product/
sudo mount -o ro system_ext.img system_ext/
```

下一步是进入到自己的设备的指定目录中，然后执行下面的命令

```plain
cd ~/android/lineage/device/google/flame

./extract-files.sh ~/android/system_dump/
```

运行这个命令的时候也会出现错误，原因是./extract-files.sh脚本中记录的文件路径有问题，需要自己修改，按照错误提示的文件，然后去找到文件的正确路径修改好就可以了，我是用find命令找的错误路径的文件，改好之后运行上面的内容就能够成功提取到了。

## 编译

编译的过程中可能会出现中断的操作，虽然有错误但是大概率是交换分区不够大导致的，建议一开始就修改交换分区，大小就改成内存大小，下面是修改交换分区的命令

```plain
sudo swapoff /swapfile

sudo rm /swapfile

sudo dd if=/dev/zero of=/swapfile bs=1M count=32768 status=progress  # 设置32G大小

sudo chmod 600 /swapfile

sudo mkswap /swapfile

sudo swapon /swapfile
```

为了每次系统重启后自动挂载交换分区，需要执行下面的命令

```plain
sudo vim /etc/fstab
```

# 在最下面一行加上 /swapfile none swap sw 0 0  内容

然后运行 swapon --show 去验证交换分区大小，看到是自己指定的大小就可以了

到这个时间点，设备的特定内容已经提取到当前的项目中了，然后可以去准备编译了，下面是作者自己的编译方式，因为作者需要用到一个OTA的包，并且最推荐使用这种方式。

注意，作者这里编译的是user版本的镜像，如果不考虑什么版本，在运行 source build/envsetup.sh 之后可以直接运行 brunch flame 命令，这样他会自己直接去编译userdebug版本的镜像。

```plain
cd ~/android/lineage

source build/envsetup.sh

lunch lineage_flame-user           # 编译user版本镜像

m																	 # 全速编译
```

全速编译完成之后，再执行 make otapackage 命令生成OTA的包，生成的OTA的包和在前面的网站下载的包的格式一摸一样，这个作为作者的系统刷机包

```plain
make otapackage
```

## 刷机

你可以使用其他的方式去完成刷机，作者比较喜欢下面的方式去完成刷机。

编译完成之后，需要把OTA中的boot.img提取出来，然后boot.img和OTA两个内容作为刷机材料

你的设备在刷机之前需要先刷对应安卓版本的谷歌官方的系统，然后才可以按照下面的步骤去刷

```plain
adb reboot bootloader

fastboot flash boot boot.img
```

按音量下键进入到recovery模式中，在recovery模式中先Factory reset -> Format data/factory reset清掉当前的数据

然后返回，进入到Apply update -> Apply from ADB 中执行下面的命令完成刷机，这个过程比较长，等刷完之后可以重启手机，开机之后就会发现已经来到了lineageOS中了

```plain
adb sideload 编译得到的ota包
```

# 构建开发环境

## 源码导入androidstudio

```plain
cd ~/android/lineage/

source build/envsetup.sh

mmm development/tools/idegen/

development/tools/idegen/idegen.sh
```

执行之后在项目根目录中生成 Android.ipr 文件，这个是用来被导入的文件

## 源码导入clion

```plain
cd ~/android/lineage/

source build/envsetup.sh

export SOONG_GEN_CMAKEFILES=1
export SOONG_GEN_CMAKEFILES_DEBUG=1

lunch lineage_flame-user

m
```

CMakeLists.txt会生成在out/development/ide/clion/art/runtime/libart-arm64-android/CMakeLists.txt

用Clion打开CMakeLists.txt

tools--->cmake-->Change Project Root

选择aosp源码根路径，等解析完

---

# 回复

## 回复 by b1n_ (#2)

*2025-4-10 17:39*

源码导入androidstudio部分有一个错误，在mmm development/tools/idegen/之前需要先执行lunch lineage_flame-user，否则会生成其他的解决方案，并不是你对应的那个

## 回复 by b1n_ (#3)

*2025-4-10 17:44*

然后 development/tools/idegen/idegen.sh 命令需要root权限执行

## 回复 by mb_ldbucrik (#4)

*2025-4-10 19:59*

感谢分享

## 回复 by chengdrgon (#5)

*2025-4-11 10:21*

感谢分享

## 回复 by NT10086 (#6)

*2025-4-11 10:57*

怎么查机子对应的包

## 回复 by b1n_ (#7)

*2025-4-11 14:20*

lineageOS官网能看到具体的安卓版本和lineageOS版本对应关系，https://lineage-archive.timschumi.net/ 里面能找到

## 回复 by geekbyte (#8)

*2025-4-14 10:35*

111

## 回复 by iyue_t (#9)

*2025-4-14 22:09*

>
> [b1n_](https://bbs.kanxue.com/user-981967.htm)
>
>  lineageOS官网能看到具体的安卓版本和lineageOS版本对应关系，https://lineage-archive.timschumi.net/ 里面能找到
>
>
>

帮我大忙了, 找半天没找到历史镜像

## 回复 by OrionisLi (#10)

*2025-4-18 15:44*

跨Android版本的不建议提取，最好是去GitHub搜索对应的内容：
proprietary_vendor <手机厂商> <设备代号>
android_device <手机厂商> <设备代号>
proprietary_vendor <手机厂商> <处理器代号> common
android_device <手机厂商> <处理器代号> common

## 回复 by NT10086 (#11)

*2025-5-15 16:55*

如果能下载的对应型号的文件，为什么要重新编译吗？

## 回复 by b1n_ (#12)

*2025-5-27 15:12*

>
> [NT10086](https://bbs.kanxue.com/user-1000986.htm)
>
>  如果能下载的对应型号的文件，为什么要重新编译吗？
>
>

rom定制需要

## 回复 by mb_xyoslnox (#13)

*2025-10-19 17:56*

感谢分享

## 回复 by lingyi223 (#14)

*2026-5-6 21:28*

为什么我拉百分之1后压根没速度

## 回复 by lingyi223 (#15)

*2026-5-10 19:27*

>
> [b1n_](https://bbs.kanxue.com/user-981967.htm)
>  rom定制需要
>

话说，有编译这个系统内核的教程码，我编译出来一直开不了机
