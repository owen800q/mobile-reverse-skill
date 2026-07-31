---
title: '[原创] Pixel 8a（akita:6.1-android16内核支持ebpf）AOSP / GKI 内核源码获取、编译与刷机实战指南'
url: https://bbs.kanxue.com/thread-290205.htm
tid: 290205
author: nuoen
date: '2026-03-06'
tags: [Android安全, 原创, 系统相关, 基础理论]
crawled_at: '2026-07-31T13:57:05+08:00'
replies: 8
---

# Pixel 8a（akita:6.1-android16内核支持ebpf）AOSP / GKI 内核源码获取、编译与刷机实战指南

>
> 这篇文章围绕 **Pixel 8a（akita）**，系统梳理 AOSP / GKI 内核源码的获取方式、编译方法、镜像含义、刷机步骤，以及后续源码阅读与调试的常见工作流。
> 在付出一台Pixel 8a刷成砖的代价下，成功刷入了可以使用ebpf的内核。这篇博客原先只是我零散的笔记，今天让AI帮忙整理下，给有需要的人提供参考。
>
>
>

---

## 这篇文章适合谁

如果你符合下面任意一种情况，这篇文章会比较适合你：

- 想拉取 **AOSP 源码** 和 **Pixel GKI 内核源码**
- 想自己编译 **Pixel 8a 内核**
- 想搞清楚 **Android 12 之后 GKI 的交付形态**
- 想在 **Android Studio / VS Code** 中阅读 AOSP 或内核源码
- 想弄明白 Pixel 上各类镜像分区到底分别负责什么

---

## 阅读前先建立整体认知

在开始之前，先记住一句最重要的话：

>
> **AOSP 负责系统源码，GKI 负责通用内核基线，vendor 模块和设备树负责设备差异化。**
>
>
>

如果你把这句话理解透了，后面的下载、编译、刷机、调试，基本都会顺很多。

---

## 1. 先搞清楚：AOSP、GKI、设备内核分别是什么

很多“编不过”“刷不开机”“不知道该拉哪个仓”的问题，本质上都不是命令问题，而是概念没对齐。

### 1.1 AOSP 是什么

AOSP（Android Open Source Project）是 Android 系统源码本身，主要包括：

- framework
- system
- packages
- libcore
- build system
- 一部分通用工具链与平台代码

你如果想看 **SystemServer、AMS、PackageManager、Binder Framework、Java Framework** 这些内容，主要是在 AOSP 里。

### 1.2 GKI 是什么

GKI（Generic Kernel Image）可以理解为 Google 主导维护的 **Android 通用内核基线**。

它的目标是：

- 把 Android 内核的公共部分收敛到 Google 统一维护
- 保持 ABI / KMI 稳定
- 让厂商尽量把差异化逻辑放到 vendor 模块里，而不是持续维护一棵完整私有内核

### 1.3 设备内核又是什么

设备最终运行的并不只是“通用 GKI 内核”这一层，还包括：

- 具体设备相关配置
- 厂商设备树
- vendor kernel modules
- 某些 SoC / 机型相关的 boot 镜像拆分方式

所以，真正落到设备侧，看到的是一套 **GKI + vendor 模块 + dtbo + 多种 boot 分区** 的组合，而不是传统时代那种“一个厂商大内核打包进 boot.img”这么简单。

---

## 2. AOSP 仓库结构与 manifest 是怎么组织的

如果你是第一次接触 repo 管理的大仓，这一部分建议先看清楚。

### 2.1 AOSP 仓库结构

```
AOSP 根目录
├─ .repo/                         # repo 工具本地管理目录
│  └─ manifests/                  # manifest 仓库同步到本地后的内容
│     └─ default.xml              # repo 实际使用的清单
└─ 其他项目仓库...
```

### 2.2 `default.xml` 在哪里

`default.xml` 来自 `platform/manifest` 仓库。执行 `repo init -u ...` 之后，会同步到本地：

```
.repo/manifests/default.xml
```

这也是 repo 实际展开整棵源码树时所依赖的核心清单文件。

### 2.3 `kernel/superproject` 是什么

`kernel/superproject` 不是某一棵具体内核源码树，它更像一个 **聚合型 superproject**，用于做多内核仓库的统一组织、索引和版本管理。

可以把它理解成“内核仓库世界里的总入口”，但不是你真正写代码、改配置、编译内核的那棵源代码目录。

### 2.4 内核分支名怎么看

例如下面这个分支名：

```
common-android14-6.1-2025-09
```

可以拆成四部分理解：

- `common`：Android 通用内核线（ACK）
- `android14`：目标 Android 版本
- `6.1`：基于 Linux 6.1 LTS
- `2025-09`：该时间窗口对应的发布线或维护线

### 2.5 常用 manifest 仓库

平台源码 manifest：

```
https://android.googlesource.com/platform/manifest
```

内核源码 manifest：

```
https://android.googlesource.com/kernel/manifest/
```

---

## 3. Android 内核交付方式：Android 12 前后到底变了什么

### 3.1 一句话理解

Android 12 之前，很多设备更接近“**厂商自己维护整棵设备内核**”的模式；Android 12 之后，Google 通过 **GKI（Generic Kernel Image）** 把通用内核基线收拢起来，厂商则更多把差异化能力放到 **vendor 模块** 和 **设备树** 里。

### 3.2 整体分层

```
Upstream Linux LTS
        │
        ▼
Android Common Kernel（kernel/common）
        │
        ▼
GKI Kernel Image + vendor modules + dtbo
        │
        ▼
具体设备运行镜像
```

### 3.3 Android 12 前后最核心的区别

| 维度 | Android 12 以下 | Android 12 及以上 |
|-|-|-|
| 内核维护方式 | 厂商 / 机型维护定制内核 | Google 维护 GKI 通用内核基线 |
| 厂商差异化位置 | 大量直接放在设备内核里 | 更多放到 vendor 模块和设备树 |
| `boot.img` 职责 | 常常承载更多厂商定制内容 | 更偏向承载通用内核镜像 |
| 更新模式 | 更依赖整机型内核更新 | 更适合 GKI + vendor 模块分离更新 |

## 4. 下载源码前，先明确你要拉的是哪一类代码

这一步非常关键。

实际工作里，很多人会把下面三类内容混为一谈：

1. **AOSP 平台源码**：主要看 framework / system / app / build system
2. **Pixel GKI 内核源码**：主要看 Pixel 对应分支的 kernel 编译链路
3. **驱动或设备相关发布包**：用于补充设备端闭源或发布产物

所以，先按目标拆开处理。

---

## 5. 获取 Pixel 8a OTA、AOSP 和 GKI 源码

### 5.1 下载全量 OTA 包

Pixel 8a OTA 页面：

```
https://developers.google.com/android/ota?#akita
```

例如：
这里选择和你手机系统相同版本的ota全量包
我的手机设置里的build版本是 BP4A.260105.004.E1,这里就选择相应的包
 ![OTA下载](https://bbs.kanxue.com/upload/attach/202603/856625_S8C2XECSJGRDABT.webp)

>
> 提示：如果下载页面打开出现风控，就去找一个有 Google 人机验证的网站，先完成验证再返回下载页面即可。
>
>
>

### 5.2 OTA 解包

```bash
unzip akita-ota-bp4a.260105.004.e1-aa134978.zip
payload-dumper-go payload.bin
```

解包后你通常会拿到：

- `boot.img`
- `init_boot.img`
- `vendor_boot.img`
- `vendor_kernel_boot.img`
- `dtbo.img`
- `vbmeta*.img`
- `system_dlkm.img`
- `vendor_dlkm.img`

这些镜像后面刷机会直接用到。

![解压产物](https://bbs.kanxue.com/upload/attach/202603/856625_G8Y7D8BTGJQVS5K.webp)

### 5.3 拉取 AOSP 平台源码

示例版本信息：
网址

```python
https://source.android.com/docs/setup//build-numbers#source-code-tags-and-builds
```

| Build ID | Tag | Version | Supported devices | Security patch level |
|-|-|-|-|-|
| BP3A.250905.014 | android-16.0.0_r3 | Android 16 | Android 16 | 2025-09-05 |

拉取命令：

```bash
repo init --partial-clone --no-use-superproject \
  -b android-16.0.0_r3 \
  -u https://android.googlesource.com/platform/manifest
repo sync -c -j8
```

### 5.4 拉取 Pixel GKI 内核源码

参考：

```
https://source.android.com/docs/setup/build/building-pixel-kernels#pixel-gki-kernel-branches
https://android.googlesource.com/kernel/manifest/+/refs/heads/android-gs-akita-6.1-android16
```

拉取命令：

```bash
repo init -u https://android.googlesource.com/kernel/manifest \
  -b android-gs-akita-6.1-android16-beta
repo sync
```

### 5.5 驱动下载页面

>
> 由于我们有全量OTA包，驱动可以不下载，这里仅记录
>
>
>

```
https://developers.google.com/android/drivers?hl=zh-cn
```

---

## 6. 开始编译：Pixel 8a GKI 内核怎么编

这一部分只聚焦内核本身。aosp的编译网上教程很多，这里就不再赘述了

### 6.1 新增自定义配置 fragment

我是为了使内核支持ebpf,所以增加了一些全局配置
新建以下文件:
//private/devices/google/akita/akita_gki.fragment

```
CONFIG_FTRACE_SYSCALLS=y
CONFIG_FUNCTION_TRACER=y
CONFIG_FUNCTION_GRAPH_TRACER=y
CONFIG_STACK_TRACER=y
CONFIG_DYNAMIC_FTRACE=y
# Disable Clang CFI
# CONFIG_CFI_CLANG is not set
```

在private/devices/google/akita/BUILD.bazel中新增

```
load("//build/bazel_common_rules/dist:dist.bzl", "copy_to_dist_dir")
load(
    "//build/kernel/kleaf:kernel.bzl",
    "kernel_abi",
    "kernel_build",
    "kernel_build_config",
    "kernel_dtstree",
    "kernel_images",
    "kernel_module_group",
    "kernel_modules_install",
    "kernel_unstripped_modules_archive",
    "merged_kernel_uapi_headers",
    "kernel_compile_commands" //新增
)
load("//private/devices/google/common/kleaf:create_file.bzl", "create_file")
load("//private/devices/google/zuma:constants.bzl", "ZUMA_DTBS", "ZUMA_MODULE_OUTS")
load(":constants.bzl", "AKITA_DTBOS")
exports_files(["akita_gki.fragment"])//新增
package(
    default_visibility = ["//visibility:public"],
)//新增
...
# 末尾新增
# 生成compile_commands.json
# cd $KERNEL_REPO_ROOT
# tools/bazel run \
#   --config=akita \
#   --config=use_source_tree_aosp \
#   //private/devices/google/akita:akita_compile_commands -- \
#   $(pwd)/compile_commands.json
kernel_compile_commands(
    name = "akita_compile_commands",
    kernel_build = ":kernel",
    visibility = ["//visibility:public"],
)
```

### 6.2 编译命令

关于bazel的使用方法，大家可以问AI，这里直接给出可以完全编译出内核的命令

```bash
tools/bazel run \
  --config=akita \
  --config=use_source_tree_aosp \
  //private/devices/google/akita:zuma_akita_dist \
  --gki_build_config_fragment=//private/devices/google/akita:akita_gki.fragment \
  --defconfig_fragment=//private/devices/google/akita:akita_gki.fragment \
  -s --debug_print_scripts --debug_make_verbosity=V
```

### 6.3 编译后如何验证结果

例如，确认 `CONFIG_FTRACE_SYSCALLS` 是否开启：

```bash
./aosp/scripts/extract-ikconfig ./out/akita/dist/Image | grep -E "CONFIG_FTRACE_SYSCALLS"
```

如果能查到对应配置，说明最终生成的内核镜像里已经包含该配置。

---

## 7. 刷机前必须先知道的风险点

这部分务必认真看。

### 7.1 先准备好编译产物

编译出的内核产物在此目录下：

```python
/path/akita-kernel/out/akita/dist/*.img
```

另外一部分是我们从ota中解出的产物，原则是运行刷机流程时，如果遇到了没有编译出的镜像，就用oat解出的产物

### 7.2 刷机前的核心原则

>
> **强烈建议先刷对应版本的厂包或全量 OTA，确保 A/B 分区上的 bootloader 版本一致。**
>
>
>

需要特别注意的是：

- 你要刷入的厂包 / OTA 版本，必须 **大于等于** 当前手机版本
- 否则可能触发反回滚保护
- 严重时会导致设备无法恢复
- 一旦遇到刷入后重新启动的情况，请立即停止任何动作，使用8.1的步骤重新刷入ota包

这一步不是“保险起见”，而是 Pixel 实机刷机时非常关键的前置条件和保险措施。

---

## 8. Pixel 8a 内核镜像刷入流程

### 8.1 先进入 recovery 并 sideload 匹配版本 OTA

```bash
fastboot reboot recovery
```

进入 recovery 后：

1. 选择 **ADB sideload** 模式
2. 如果屏幕显示机器人和 `No command`：
	- 按住电源键
	- 再按一次音量加键
	- 进入 Recovery 菜单

执行：

```bash
adb sideload /Users/nuoen/Downloads/akita-ota-bp4a.260105.004.e1-aa134978.zip
```

### 8.2 刷入内核相关镜像

```bash
adb reboot bootloader
fastboot -w
fastboot oem pkvm disable
fastboot flash boot boot.img
fastboot flash dtbo dtbo.img
fastboot flash vendor_kernel_boot vendor_kernel_boot.img
```

### 8.3 进入 fastbootd，刷入 dlkm 镜像

```bash
fastboot reboot fastboot
fastboot getvar is-userspace
fastboot flash system_dlkm system_dlkm.img
fastboot flash vendor_dlkm vendor_dlkm.img
```

### 8.4 回到 bootloader，刷入 vbmeta

```bash
fastboot flash --disable-verity --disable-verification vbmeta vbmeta.img
fastboot flash --disable-verity --disable-verification vbmeta_system vbmeta_system.img
fastboot flash --disable-verity --disable-verification vbmeta_vendor vbmeta_vendor.img
```

完成后再重启设备，验证是否成功进入系统。

---

## 9. 编译内核模块（`.ko`）

如果你不是只改内核配置，而是要自己编译一个可加载模块，可以参考下面的方式。

### 9.1 编译命令

```bash
tools/bazel run \
  --config=akita \
  --config=use_source_tree_aosp \
  --config=no_download_gki_fips140 \
  //modules/hello:hello_dist
```

### 9.2 `hello` 模块示例 `BUILD.bazel`

```python
load("@//build/kernel/kleaf:kernel.bzl", "kernel_module", "kernel_modules_install")
load("//build/bazel_common_rules/dist:dist.bzl", "copy_to_dist_dir")

package(
    default_visibility = ["//visibility:public"],
)

filegroup(
    name = "lkm_sources",
    srcs = glob(
        [
            "**/*.c",
            "**/*.h",
            "Kbuild",
        ],
        exclude = [
            "BUILD.bazel*",
            "**/*.bzl",
            ".gid/**",
        ],
    ),
)

kernel_module(
    name = "hello",
    srcs = [":lkm_sources"],
    outs = ["hello.ko"],
    kernel_build = "//private/devices/google/akita:kernel",
)

copy_to_dist_dir(
    name = "hello_dist",
    data = [":hello"],
    dist_dir = "out/hello",
    flat = True,
    log = "info",
)

kernel_modules_install(
    name = "hello_install",
    kernel_build = "//private/devices/google/akita:kernel",
    kernel_modules = [
        ":hello",
    ],
)
```

---

具体模块代码可以在我的仓库中找到
https://github.com/nuoen/kernel_modules

到此基本上内核就刷入完成了，如果需要root可以用Magisk等工具来替换ota包中的镜像
pixel 8a 替换的是 init_boot.img

## 以下就是一些其他的资料和笔记

## 10. GKI 编译产物里，这些镜像分别是什么

这一部分建议结合刷机一起理解。

### 10.1 `init_boot.img`

从 Android 13 开始，Pixel 系列把原来放在 `boot.img` 里的通用 ramdisk 拆分到了 `init_boot.img`。

### 10.2 `boot.img`

`boot.img` 现在主要承载的是 **GKI 通用内核镜像**，可以理解为：

- 包含 kernel Image
- 不再负责完整厂商差异化逻辑
- 厂商扩展更多通过 vendor 模块完成

### 10.3 `vendor_boot.img`

这是厂商专用 ramdisk，通常包含：

- 设备专属驱动加载脚本
- SoC 早期初始化内容
- vendor 相关服务
- 某些依赖的 init 配置

### 10.4 `vendor_kernel_boot.img`

这是 GKI 架构下非常关键的一个分区，常见承载内容包括：

- vendor kernel modules 的 early 部分
- 厂商补充的内核能力
- GKI 与 vendor 之间的接口衔接层

>
> **这个分区不要随意替换。**
>
>
> 刷写错误可能导致：
>
>
> - kernel panic
> - 直接进入 fastboot
> - 无法正常启动系统
>
>
>

### 10.5 ramdisk 到底是什么

ramdisk 是内核启动早期挂载的根文件系统的一部分，常见内容包括：

- `/init`
- early init scripts
- `sepolicy`
- `ueventd.rc`
- `fstab`
- 一些早期启动所需的配置或注入内容

在 Tensor SoC（Pixel 6 / 7 / 8）体系上，一般可以这样理解：

- 通用 ramdisk 在 `init_boot.img`
- vendor ramdisk 在 `vendor_boot.img`

---

## 11. GKI / KMI 符号表在哪里看

如果你在分析 ABI、检查可导出符号、验证某个接口是否仍在 KMI 集合内，这一部分会用得上。

### 11.1 常见位置

```
aosp/android/
```

### 11.2 主文件 `abi_gki_aarch64.stg`

```
aosp/android/abi_gki_aarch64.stg
```

特点：

- 体积较大
- 是 GKI ABI 的主定义文件
- 包含类型信息、函数签名、结构体布局、符号定义等

### 11.3 基础符号列表 `abi_gki_aarch64`

```
aosp/android/abi_gki_aarch64
```

通常用于列出一些基础公共符号，例如：

- `module_layout`
- `__put_task_struct`

### 11.4 厂商相关符号列表

例如：

- `abi_gki_aarch64_qcom`
- `abi_gki_aarch64_pixel`
- `abi_gki_aarch64_mtk`
- `abi_gki_aarch64_exynos`

### 11.5 查询示例

```bash
grep -i "register_kprobe" aosp/android/abi_gki_aarch64.stg
```

---

## 12. 如何阅读 AOSP 源码

如果你的重点是 framework / system 层，建议先把阅读环境搭起来。

### 12.1 Android Studio 导入 AOSP

#### 第一步：编译 idegen

```bash
source build/envsetup.sh
lunch <target>-userdebug
mmm development/tools/idegen/
sh ./development/tools/idegen/idegen.sh
```

生成产物：

- `android.ipr`
- `android.iml`

#### 第二步：打开项目之前先做裁剪

可按需调整权限：

```bash
chmod 777 android.ipr android.iml
```

这两个文件的作用分别是：

- `android.ipr`：Android Studio 打开项目时选择的入口文件
- `android.iml`：模块描述文件，可以裁剪无关目录，减少索引压力

通常如果你只看 framework，可以优先保留：

- `frameworks`
- `packages`
- `libcore`
- `system`

#### 第三步：配置 SDK

在 Android Studio 中打开 **Project Structure**，配置：

- Java SDK
- 对应版本的 Android API

必要时删除多余的 class path / source path，减少误跳转。

#### 第四步：删除不必要依赖

一般保留下面两类就够了：

- `<Module source>`
- `Android API Platform`

#### 第五步：调整源码优先级

如果手动加入 `frameworks/base` 等目录依赖，建议把它放在 `Module Source` 之上，否则代码跳转时可能优先跳到生成目录而不是源码目录。

#### 第六步：显示被排除文件

在 Project 视图设置里取消勾选：

```
Show Excluded Files
```

#### 第七步：清理版本控制目录

在：

```
File → Settings → Version Control
```

删除不必要的目录管理，只保留你真正需要操作的源码路径。

### 12.2 额外优化建议

#### 提高 inotify 限制

编辑 `/etc/sysctl.conf`，加入：

```conf
fs.inotify.max_user_watches=524288
```

然后执行：

```bash
sudo sysctl -p
cat /proc/sys/fs/inotify/max_user_watches
```

#### 调大 Android Studio 堆内存

在 Android Studio 中进入：

```
File → Settings → Appearance & Behavior → System Settings → Memory Settings
```

适当把 heap size 调大，否则索引大仓时很容易卡顿甚至 OOM。

### 12.3 Android Studio 调试 AOSP

调试流程通常是：

1. 连接设备并开启 USB 调试
2. 在源码处打断点
3. 点击 **Attach Debugger to Android Process**
4. 勾选 **Show all processes**
5. 选择目标进程，例如 `system_process`

如果按钮点击没有反应：

- 点击 **Add Configuration...**
- 左上角点 `+`
- 选择 **Android App**
- 保存后重新尝试

---

## 13. 如何用 VS Code + clangd 阅读 AOSP / GKI

如果你更偏爱轻量工作流，可以直接走 VS Code。

### 13.1 AOSP：生成 `compile_commands.json`

```bash
cd /path/to/aosp-root

source build/envsetup.sh
lunch aosp_arm64-userdebug

export SOONG_GEN_COMPDB=1
export SOONG_GEN_COMPDB_DEBUG=1
export SOONG_LINK_COMPDB_TO="$PWD"

m
```

检查输出：

```bash
ls compile_commands.json
ls out/soong/development/ide/compdb/compile_commands.json
```

VS Code 的 `.vscode/settings.json` 可以这样配置：

```json
{
  "clangd.arguments": [
    "--compile-commands-dir=.",
    "--background-index",
    "--all-scopes-completion"
  ]
}
```

如果还要阅读 Java 代码，可以补充：

```json
{
  "java.project.sourcePaths": [
    "frameworks/base/core/java",
    "frameworks/base/services/core/java",
    "frameworks/base/packages",
    "libcore",
    "system"
  ]
}
```

### 13.2 GKI：通过 bazel 生成 `compile_commands.json`

```bash
tools/bazel run \
  --config=akita \
  --config=use_source_tree_aosp \
  //private/devices/google/akita:akita_compile_commands -- \
  $(pwd)/compile_commands.json
```

VS Code 配置：

```json
{
  "clangd.arguments": [
    "--compile-commands-dir=${workspaceFolder}"
  ]
}
```

---

## 14. 常见调试方式示例

这部分不是本文重点，但作为后续工作流的衔接，保留几个常用模板。

### 14.1 使用 LLDB 调试 `servicemanager`

设备端：

```bash
adb push lldb-server /data/local/tmp/
adb shell
cd /data/local/tmp
chmod 755 lldb-server
./lldb-server p --server --listen unix-abstract:///data/local/tmp/debug.sock
```

主机端：

```sh
(lldb) platform select remote-android
(lldb) platform connect unix-abstract-connect:///data/local/tmp/debug.sock
(lldb) file out/target/product/marlin/symbols/system/bin/servicemanager
(lldb) target modules search-paths add /system /home/nuoen/aosp/out/target/product/marlin/symbols/system
(lldb) process attach --pid 477
```

启动：

```sh
(lldb) process launch --stdin /dev/stdin --working-dir /data/local/tmp
```

### 14.2 使用 LLDB 调试 `/data/local/tmp/main`

适用场景：已经把可执行文件 `main` push 到设备，希望在主机端远程调试。

设备端：

```bash
adb push ./main /data/local/tmp/main
adb shell chmod 755 /data/local/tmp/main

adb push /path/to/lldb-server /data/local/tmp/lldb-server
adb shell chmod 755 /data/local/tmp/lldb-server

adb shell "/data/local/tmp/lldb-server platform --server --listen unix-abstract:///data/local/tmp/debug-main.sock"
```

主机端：

```bash
lldb
```

```ssh
(lldb) platform select remote-android
(lldb) platform connect unix-abstract-connect:///data/local/tmp/debug-main.sock
(lldb) target create ./main
(lldb) b main
(lldb) process launch --working-dir /data/local/tmp -- arg1 arg2
```

如果程序已经运行，也可以 attach：

```bash
adb shell pidof main
```

```sh
(lldb) process attach --pid <pid>
```

注意：

- 建议使用 `-g -O0` 编译，便于断点和变量显示
- 如果依赖自定义 `.so`，启动前设置 `LD_LIBRARY_PATH=/data/local/tmp`
- `lldb` 与 `lldb-server` 最好版本匹配

### 14.3 使用 GDB 远程调试 Android 64 位程序

#### 前提要求

- Android 设备已 root
- 目标程序已推送到 `/data/local/tmp/`
- ELF 为 `aarch64`
- 主机安装 `gdb-multiarch`，或使用 NDK 提供的 GDB
- 主机与设备可通过 adb 通信

#### 步骤 1：推送程序

```bash
adb push ~/linux-6.7.12/LinuxLearn/exp/uaf/pwn_uaf1 /data/local/tmp/
adb shell chmod +x /data/local/tmp/pwn_uaf1
```

#### 步骤 2：设备端启动 `gdbserver64`

```bash
adb shell
cd /data/local/tmp
./gdbserver64 :1234 ./pwn_uaf1 1 test_input.txt
```

预期输出：

```
Process ./pwn_uaf1 created; pid = xxxx
Listening on port 1234
```

#### 步骤 3：主机端做端口转发

```bash
adb forward tcp:1234 tcp:1234
```

#### 步骤 4：主机端启动 GDB

方式 A：

```bash
gdb-multiarch ~/linux-6.7.12/LinuxLearn/exp/uaf/pwn_uaf1
```

方式 B：

```bash
cd $NDK/toolchains/llvm/prebuilt/linux-x86_64/aarch64-linux-android/debugger-bin
./aarch64-linux-android-gdb ~/linux-6.7.12/LinuxLearn/exp/uaf/pwn_uaf1
```

#### 步骤 5：连接目标并调试

```gdb
target remote :1234
file ~/linux-6.7.12/LinuxLearn/exp/uaf/pwn_uaf1
break main
continue
```

调试时常用命令：

- `next` / `step`
- `print var`
- `info registers`

#### 常见问题

| 问题 | 原因 |
|-|-|
| 连接后立刻断开 | 架构不匹配，确认目标是 `aarch64` |
| `Reply contains invalid hex digit` | GDB / gdbserver 版本不兼容 |
| 传参不生效 | 参数要在设备端启动 `gdbserver` 时传入 |
| 无法交互输入 | attach 模式下 stdin 可能不可用 |

#### 一键脚本模板

```bash
#!/bin/bash
adb push pwn_uaf1 /data/local/tmp/
adb shell chmod +x /data/local/tmp/pwn_uaf1
adb forward tcp:1234 tcp:1234
adb shell "cd /data/local/tmp && ./gdbserver64 :1234 ./pwn_uaf1 arg1 arg2" &
sleep 2
gdb-multiarch pwn_uaf1 -ex "target remote :1234"
```

---

## 15. 总结

如果你读到这里，建议把整件事重新串成下面这条主线：

1. **先区分 AOSP 与 GKI**：一个是系统源码，一个是内核基线
2. **再确认设备对应分支**：尤其是 Pixel 机型与 Android 版本要匹配
3. **拉源码**：平台源码和内核源码分别拉
4. **编译 GKI 内核**：必要时加自定义 fragment
5. **理解镜像职责**：特别是 `boot`、`init_boot`、`vendor_boot`、`vendor_kernel_boot`、`vendor_dlkm`
6. **按正确顺序刷机**：先保证版本对齐，再刷相关镜像
7. **最后建立阅读和调试环境**：Android Studio 或 VS Code，各取所需

---

## 参考资料

- `https://android.googlesource.com/platform/manifest`
- `https://android.googlesource.com/kernel/manifest/`
- `https://source.android.com/docs/setup/build/building-pixel-kernels#pixel-gki-kernel-branches`
- `https://developers.google.com/android/ota?#akita`
- `https://developers.google.com/android/drivers?hl=zh-cn`
- `https://gityuan.com/2018/06/02/android-bp/`
- `https://www.cnblogs.com/yongfengnice/p/18246075`
- `https://juejin.cn/post/7139773823116640263`

---

# 回复

## 回复 by Zepp7289 (#2)

*2026-3-7 00:30*

太强了

## 回复 by Imxz (#3)

*2026-3-7 21:45*

tql

## 回复 by git_66480p0-tato (#4)

*2026-3-13 15:13*

666

## 回复 by huangjw (#5)

*2026-3-15 15:04*

王炸

## 回复 by ID蝴蝶 (#6)

*2026-3-17 23:06*

不错

## 回复 by ID蝴蝶 (#7)

*2026-4-3 23:40*

大佬，你的pixel 8a刷的是编译aosp16吗

## 回复 by nuoen (#8)

*2026-4-15 01:59*

>
> [ID蝴蝶](https://bbs.kanxue.com/user-611407.htm)
>  大佬，你的pixel 8a刷的是编译aosp16吗
>

没有刷aosp, 只替换了内核，最新的aosp代码还没有释放出来

## 回复 by mb_zcfhleoj (#9)

*2026-4-22 16:37*

感谢分享
