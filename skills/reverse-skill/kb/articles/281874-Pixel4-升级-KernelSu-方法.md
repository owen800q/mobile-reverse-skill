---
title: '[原创] Pixel4 升级 KernelSu 方法'
url: https://bbs.kanxue.com/thread-281874.htm
tid: 281874
author: ShoppingChen
date: '2024-05-23'
tags: [Android安全, 原创, HOOK注入, 其他, 系统相关, 逆向分析]
crawled_at: '2026-07-31T14:27:12+08:00'
replies: 2
---

# 思路：

1.找到开源的 kernelsu pixel4 二进制文件
2.刷入手机中
3.检查 kernelsu 是否更新成功（新功能是否生效）
4.升级 kernelsu apk

## 1.寻找开源的 kernelsu pixel4

非官方支持设备，网上已经有了很多编译好的
<https://kernelsu.org/zh_CN/guide/unofficially-support-devices.html>
<https://github.com/msnx/KernelSU-Pixel4XL>
从readme 中看，需要两步，首先刷入官方的系统镜像，然后刷入本项目的 boot.img
我直接第二步 Download pixel4xl_android13_4.14.276_version.img and flash it in fastboot mode
pixel4xl_android13_4.14.276_version.img
下载位置：<https://github.com/msnx/KernelSU-Pixel4XL/tags>
直接下载 img 注意：记住对应的 kernelsu 版本

## 2.刷入手机

### a.备份

i.adb shell 连接手机
ii.su 获取root
iii.ls -l /dev/block/by-name/ | grep boot

| 1234567 | `flame:``/``system` `# ls -l /dev/block/by-name/ \| grep boot``lrwxrwxrwx` `1` `root root` `15` `1970``-``02``-``25` `14``:``38` `boot_a` `-``>` `/``dev``/``block``/``sda6``lrwxrwxrwx` `1` `root root` `15` `1970``-``02``-``25` `14``:``38` `boot_b` `-``>` `/``dev``/``block``/``sda7``# 备份 boot.img  因为是 ab 分区所以建议都备份``dd` `if``=``/``dev``/``block``/``sda6 of``=``/``sdcard``/``boot_a.img``dd` `if``=``/``dev``/``block``/``sda7 of``=``/``sdcard``/``boot_b.img``# 使用 adb pull 再备份到电脑中` |
|-|-|

b.刷入手机
i.adb reboot bootloader
ii.adb boot 下载的 img 文件
iii.如果上一步能正常启动，则执行下一步
iv.adb flash boot 下载的 img 文件
注意： 从 log 中能看到写到了哪个分区，我这边是写到了 boot_a 分区

| 123456789101112 | `(venv) D:\>adb reboot bootloader` `(venv) D:\>fastboot flash boot C:\Users\User\Desktop\pixel4xl_android13_4.``14.276_v093``.img``Sending` `'boot_a'` `(``38300` `KB)                        OKAY [` `1.247s``]``Writing` `'boot_a'`                                   `OKAY [` `0.285s``]``Finished. Total time:` `1.997s` `(venv) D:\>fastboot reboot``Rebooting                                          OKAY [` `0.043s``]``Finished. Total time:` `0.054s` `(venv) D:\>` |
|-|-|

## 检查内核是否生效

i.检查 备份的 boot.img 和 系统中的 md5 是否一样，如果不一样说明更新成功了
ii.检查 /proc/version 是否和我们需要更新的内核版本一致

## 更新 kernelsu apk

下载位置：<https://github.com/tiann/KernelSU/releases>

本人实际测试的版本：
kernel内核文件： pixel4xl_android13_4.14.276_v093.img
apk 文件： KernelSU_v0.9.2_11682-release.apk

---

# 回复

## 回复 by mb_fidppcok (#2)

*2024-5-24 09:37*

ksu 不是已经有修补模式了吗？

## 回复 by 狄人3 (#3)

*2024-5-25 07:58*

>
> [mb_fidppcok](https://bbs.kanxue.com/user-986312.htm)
>
>  ksu 不是已经有修补模式了吗？
>
>

修补lkm仅支持GKI内核。Pixel 4的内核版本太老了，只能源码编译实现
