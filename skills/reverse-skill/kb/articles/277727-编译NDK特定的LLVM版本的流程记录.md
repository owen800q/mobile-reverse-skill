---
title: '[原创]编译NDK特定的LLVM版本的流程记录'
url: https://bbs.kanxue.com/thread-277727.htm
tid: 277727
author: blx2024
date: '2023-06-23'
tags: [Android安全, 原创, 基础理论, 混淆加固]
crawled_at: '2026-07-31T14:43:00+08:00'
replies: 1
---

>
> 欢迎关注个人的微信公众号《[Android安全工程](http://baihonghua.cn/Android%E5%AE%89%E5%85%A8%E5%B7%A5%E7%A8%8B)》（可点击进行扫码关注）。个人微信公众号主要围绕 Android 应用的安全防护和逆向分析， 分享各种安全攻防手段、Hook 技术、ARM 汇编等 Android 相关的知识。
>
>
>

## LLVM源码下载

>
> 源码编译环境: ubuntu 22.04.1 LTS
>
>
> 产物使用环境: window10
>
>
> NDK版本： 23.1.7779620
>
>
>

选择的`NDK`版本:

| 1 | `..\Android\Sdk\ndk\``23.1``.``7779620` |
|-|-|

对应的 llvm 版本：

| 1 | `..\Android\Sdk\ndk\``23.1``.``7779620``\toolchains\llvm\prebuilt\windows``-``x86_64\AndroidVersion.txt` |
|-|-|

| 12 | `12.0``.``8``based on r416183c1` |
|-|-|

**源码下载**

采用清华源

| 12345678 | `mkdir ~``/``bin``PATH``=``~``/``bin``:$PATH``curl https:``/``/``mirrors.tuna.tsinghua.edu.cn``/``git``/``git``-``repo > ~``/``bin``/``repo``chmod a``+``x ~``/``bin``/``repo``export REPO_URL``=``'https://mirrors.tuna.tsinghua.edu.cn/git/git-repo'` `mkdir llvm``-``toolchain && cd llvm``-``toolchain``repo init` `-``u https:``/``/``mirrors.tuna.tsinghua.edu.cn``/``git``/``AOSP``/``platform``/``manifest` `-``b llvm``-``toolchain` |
|-|-|

把 NDK 下的 `%ANDROID_SDK_PATH%\ndk\23.1.7779620\toolchains\llvm\prebuilt\windows-x86_64`的 `manifest_7714059.xml` 文件替换掉 `.repo` 下的 `manifest/default.xml` 文件替换（或者直接把内容替换）:

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_23PAR5HPDY8X99A.png)

>
> 这里的 manifest_7714059.xml 文件内的 google 相关的链接需替换成 `https://mirrors.tuna.tsinghua.edu.cn/`
>
>
>

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_GTERTWUHYSC7YK9.png)

需要注意，`.repo`是隐藏文件夹。可能直接在 Window 下复制文件到 Linux 系统出现乱码问题，推荐使用 `FileZilla` 复制文件。

| 12 | `repo init` `-``m default.xml``repo sync` `-``c` |
|-|-|

**编译**

| 1 | `python toolchain``/``llvm_android``/``build.py` `-``-``no``-``build linux` |
|-|-|

`--no-build linux`表示不需要编译 Linux 环境下的 toolchain 。

## 移植LLVM模块

>
> 通过比较 `toolchains\llvm\prebuilt\windows-x86_64/bin` 文件夹下的 `clang.exe` 和 `clang++.exe` 发现，两者的 md5 值是相同的，读者感兴趣可以尝试比较下。故可以通过上述的步骤来解决 ollvm 编译出的 `clang++.exe` 报错问题。
>
>
>  ![image](https://bbs.kanxue.com/upload/attach/202306/928718_YR2G9QQSNUHN2YU.png)
>
>
>

直接把编译好后`out/install/windows-x86/clang-dev/bin`中的 `clang.exe`替换对应的NDK中的`toolchains\llvm\prebuilt\windows-x86_64/bin` 的 `clang.exe` 和 `clang++.exe`（需把编译出的 `clang.exe` 拷贝重命命名替换原NDK中的 `clang++.exe`）

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_B6GYMFEFE8Y2RQ4.png)
 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_AB5HYTT9KY9WY7G.png)

**问题解决**

报错：`ImportError: libffi.so.6: cannot open shared object file: No such file or directory`

解决：

`find /usr/lib -name libffi.so*`

`sudo ln -s /usr/lib/x86_64-linux-gnu/libffi.so.8 /usr/lib/x86_64-linux-gnu/libffi.so.6`

 ![image](https://bbs.kanxue.com/upload/attach/202306/928718_ZBNUXNEUBTEFFM6.png)

## 参考资料

<https://github.com/kk-laoguo/ollvm-13>

<http://strivemario.work/archives/488c6e54.html>

[【清羽】Windows10下编译OLLVM-14.x](https://blog.csdn.net/qq_41923691/article/details/123258565)

<https://android.googlesource.com/toolchain/llvm_android/>

<https://bbs.kanxue.com/thread-271271.htm>

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-23 23:13*

感谢分享
