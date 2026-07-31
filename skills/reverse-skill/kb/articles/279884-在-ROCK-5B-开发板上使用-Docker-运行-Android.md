---
title: '[原创] 在 ROCK 5B 开发板上使用 Docker 运行 Android'
url: https://bbs.kanxue.com/thread-279884.htm
tid: 279884
author: Amun
date: '2023-12-14'
tags: [Android安全, 原创, 系统相关, 工具脚本]
crawled_at: '2026-07-31T14:35:47+08:00'
replies: 9
---

# 在 ROCK 5B 开发板上使用 Docker 运行 Android

年初时购入了一个 ROCK 5B，折腾 Android 逆向分析，有了一些成果后，自己 DIY 了更好的逆向分析平台(ROCK 5B 已经卖掉了)。

整理文档时，翻出来当时的记录文档，论坛里也没有看到有相关的帖子，现在发出来希望对大家有帮助。

目录- 在 ROCK 5B 开发板上使用 Docker 运行 Android
- 在 ROCK 5B 构建适用 Android 的 Linux 内核
- 安装内核
- 安装内核 deb 包
- 激活新内核
- 启动 Android 镜像
- 安装 docker
- 启动 Android 容器
- 连接 Android
- 其他
环境：官方 Ubuntu 20.04 镜像

## 在 ROCK 5B 构建适用 Android 的 Linux 内核

>
> 懒得弄得话，可以直接用我以前构建的
> <https://bbs.kanxue.com/thread-277387.htm>
>
>
>

参照 <https://wiki.radxa.com/Rock5/guide/build-kernel-on-5b>
完成：

- [Install essential pacakges](https://wiki.radxa.com/Rock5/guide/build-kernel-on-5b#Install%20essential%20pacakges)
>
>
>
> | 12 | `$` `sudo` `apt-get update``$` `sudo` `apt-get` `install` `-y git  device-tree-compiler libncurses5 libncurses5-dev build-essential libssl-dev` `mtools` `bc` `python dosfstools bison flex` `rsync` `u-boot-tools` `make` |
> |-|-|
>
>
>
- [Get the source code](https://wiki.radxa.com/Rock5/guide/build-kernel-on-5b#Get%20the%20source%20code)
>
>
>
> | 1234 | `$` `mkdir` `~``/rk3588-sdk` `&&` `cd` `~``/rk3588-sdk``$ git clone -b linux-5.10-gen-rkr3.4 https:``//github``.com``/radxa/kernel``.git``$ git clone -b master https:``//github``.com``/radxa/rkbin``.git``$ git clone -b debian https:``//github``.com``/radxa/build``.git` |
> |-|-|
>
>
>

检出 rock5b 的内核配置

| 123 | `cd` `~``/rk3588-sdk``cd` `kernel``make` `rockchip_linux_defconfig` |
|-|-|

进入配置 GUI

| 1 | `make` `menuconfig` |
|-|-|

检查以下配置选项，没有勾选的就勾上。配置 menuconfig 中，按 '/' 键可以搜索。

| 123456789101112131415161718192021 | `CONFIG_DMABUF_HEAPS=y``CONFIG_DMABUF_HEAPS_SYSTEM=y` `CONFIG_STAGING=y``CONFIG_ASHMEM=y` `CONFIG_ANDROID=y``CONFIG_ANDROID_BINDER_IPC=y``CONFIG_ANDROID_BINDERFS=y``CONFIG_ANDROID_BINDER_DEVICES=``"binder,hwbinder,vndbinder"` `CONFIG_PSI=y` `CONFIG_FUSE_FS=y` `CONFIG_ROCKCHIP_EFUSE=y` `CONFIG_COMPAT=y``CONFIG_COMPAT_32BIT_TIME=y` `CONFIG_ARM64_4K_PAGES=y` |
|-|-|

懒得搞的话，可以打开 kernel 目录中的 `.config` 文件，将上面的配置粘贴进去。

保存配置退出配置界面后，设置为默认编译配置。

| 12 | `make` `savedefconfig``cp` `defconfig arch``/arm64/configs/rockchip_linux_defconfig` |
|-|-|

开始编译

| 12 | `cd` `~``/rk3588-sdk``.``/build/pack-kernel``.sh -d rockchip_linux_defconfig -r 99` |
|-|-|

构建完成后(rock5b 上约 20分钟)，在 目录 `~/rk3588-sdk/out/packages` 中会存在 内核 deb 包。

如果在构建过程自动重启，一般是电源功率过低，换个 45W 以上电源就好。

## 安装内核

### 安装内核 deb 包

安装在上一步中生成的 deb 包

| 12 | `sudo` `dpkg -i out``/packages/linux-headers-5``.10.110-99-rockchip-g9fd61a9a9912_5.10.110-99-rockchip_arm64.deb``sudo` `dpkg -i out``/packages/linux-image-5``.10.110-99-rockchip-g9fd61a9a9912_5.10.110-99-rockchip_arm64.deb` |
|-|-|

### 激活新内核

编辑文件 `/boot/extlinux/extlinux.conf`

设置默认启动内核

| 12345678910111213 | `timeout 10``menu title` `select` `kernel` `# 添加和设置默认启动内核``default kernel-5.10.110-99-rockchip-g9fd61a9a9912` `# 这个是新安装的内核``label kernel-5.10.110-99-rockchip-g9fd61a9a9912``# ...` `# 旧内核``label kernel-5.10.110-34-rockchip-gca15bbe36e6c``# ...` |
|-|-|

重启系统

## 启动 Android 镜像

### 安装 docker

| 1 | `sudo` `apt` `install` `docker.io` |
|-|-|

### 启动 Android 容器

三种镜像

- firefly
 需要单独导入，略麻烦，文档 [容器虚拟安卓](https://wiki.t-firefly.com/zh_CN/EC-R3588SPC/linux_technical_cases.html#rong-qi-xu-ni-an-zhuo)
- redroid
 没驱动，还需要折腾
- myt
 开箱即用

用 myt 的镜像进行测试

| 123456789 | `sudo` `docker run -itd --``rm` `--privileged \``--pull always \``-``v` `~``/android_data``:``/data` `\``-``v` `/dev/net/tun``:``/dev/tun` `\``-``v` `/dev/mali0``:``/dev/mali0` `\``-p 5501:5555 \``--name dobox \``registry.cn-hangzhou.aliyuncs.com``/whsyf/dobox``:rk3588-202303011` |
|-|-|

其中 `~/android_data` 目录如果不存在的话，需要自己手动创建，或者换到一个已存在的目录
`-p 5501:5555` 是在主机上映射 5501 为容器的 ADB 端口

## 连接 Android

Windows 可以使用 QtScrcpy 进行连接
<https://github.com/barry-ran/QtScrcpy>

假设 ROCK 5B 的局域网地址是 192.168.1.13，ADB 命令窗口输入 `connect 192.168.1.13:5501`，执行。再双击连接即可。

# 其他

理论上 RK3588 和 RK3588S 都适用，自己搞定内核就行。

由于容器是使用 privileged 特权模式启动的，就不要手贱在 adb shell 里面输入 reboot ，这会让主机也重启。

如果有坛友知道如何在非特权模式下启动，麻烦告知，谢谢。

---

# 回复

## 回复 by wx_Deity (#2)

*2023-12-14 17:56*

感谢分享

## 回复 by 陈可牛 (#3)

*2023-12-14 18:59*

正准备捣鼓，感谢分享

## 回复 by `铭浅. (#4)

*2023-12-28 19:23*

大佬，我创建了redroid虚拟机，然后adb连接一直offline是怎么回事，设置虚拟机的哪个可以不用adb tcpip 5555呢。感谢回答

## 回复 by Amun (#5)

*2023-12-31 13:48*

>
> [`铭浅.](https://bbs.kanxue.com/user-902773.htm)
>
>  大佬，我创建了redroid虚拟机，然后adb连接一直offline是怎么回事，设置虚拟机的哪个可以不用adb tcpip 5555呢。感谢回答
>
>

1. 可以检查一下是哪个端口映射到了 5555 端口
2. 用 docker exec 进入容器里，检查是否已经正常启动

## 回复 by `铭浅. (#6)

*2024-1-2 10:08*

谢谢，找到原因了，是因为没有执行modprobe ashmem_linux，导致的问题

## 回复 by woaiziyou (#7)

*2024-1-2 10:31*

这板子可以开多少台安卓环境

## 回复 by IamHuskar (#8)

*2024-1-2 10:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  woaiziyou](https://bbs.kanxue.com/user-638740.htm)
>
>  这板子可以开多少台安卓环境
>
>
>

同问。16G内存可以开多少个android。

## 回复 by Amun (#9)

*2024-1-3 15:33*

>
> [IamHuskar](https://bbs.kanxue.com/user-528829.htm)
>
>  同问。16G内存可以开多少个android。
>
>

空载 500~700 MB 一个 Android 系统，具体看业务负载了。如果是运行游戏，CPU 才是瓶颈。

## 回复 by IamHuskar (#10)

*2024-1-3 16:20*

>
> [Amun](https://bbs.kanxue.com/user-850401.htm)
>
>  空载 500~700 MB 一个 Android 系统，具体看业务负载了。如果是运行游戏，CPU 才是瓶颈。
>
>

游戏如果走mali gpu 可能还好。cpu确实稍微差点。不过已经是不错的旗舰款芯片了
