---
title: '[原创]自动化采集Android系统级设备指纹对抗&如何四两拨千斤?'
url: https://bbs.kanxue.com/thread-281889.htm
tid: 281889
author: 珍惜Any
date: '2024-05-25'
tags: [Android安全, 原创, 协议分析, 逆向分析, 基础理论]
crawled_at: '2026-07-31T14:27:08+08:00'
replies: 102
---

# 自动化采集Android系统级设备指纹对抗&如何四两拨千斤？

# 背景：

这篇文章主要是针对设备指纹层面的一个整体的对抗思路 ，可能网上会有相似的文章，但是都不适用于现在的环境 ，想着简单梳理一下，之前是二次打包，只能在客户端去修改，所以需要去hook binder的这些方法，实现hook的拦截 ，但是留的痕迹也很多，很难做到不修改客户端，但是现在我们是在Root的环境下 ，很多东西玩法就变了  。最早是Magisk可以在系统层做一些文件替换，现在的Apatch出来以后，很多对抗都放在了内核里面，直接从应用层修改直接跳转到内核 （说好的不进入内核呢？），最早之前很多可能还是通过编译自定义ROM或者自定义内核之类的去实现对抗 ，现在看起来有点鸡肋 。

下面的内容也只是我个人所感所想，如果有更好的思路，或者文中有什么地方没有讲述清除，讲述错误的地方也可以随时回复。

基础知识：

[风控对抗基础随笔](https://bbs.kanxue.com/thread-273838.htm)

设备指纹第一篇：

[聊聊大厂设备指纹获取和对抗&设备指纹看着一篇就够了!](https://bbs.kanxue.com/thread-273759.htm)

设备指纹第二篇：

[聊聊大厂设备指纹其二&Hunter环境检测思路详解!](https://bbs.kanxue.com/thread-277402.htm)

设备指纹第三篇：

[聊聊大厂设备指纹其三&如何在风控对抗这场“猫鼠游戏”中转换角色!](https://bbs.kanxue.com/thread-277637.htm)

这篇文章是第四篇 ，主要是针对架构的事情进行演练和梳理，通过“推演”的方式去模拟一场战斗。而我们

站在“玩家”视角去推断这场战斗胜负。

其实在第三篇文章里面结论：

**我们只需要让客户端安全SDK检测“失效”即可做到黑产的自动化爬取 。**

这个失效并不是说让他不上报，而是检测不到 ，但是在客户端还要实现那么多对抗 ，比如一键新机，包括各种复杂的环境检测都需要绕过 ，也不是一件简单的事情 。

我之前写过一个软件叫Hunter，它主要就是检测客户端的风险项，在不断和黑产对抗测试的过程中发现，很多攻击者的攻击方式很有趣，有硬件断点逃逸内存CRC检测，有内核注入的，有直接在服务端修改直接修改客户端返回值的。发现绕过的办法千奇百怪 ，但是他们核心的思路就是 。

**客户端不注入不修改一丁点代码，但是可以实现一键新机 。**

下来我们就聊一下，客户端应该怎么做才能实现这个功能的 ？中间有哪些坑？为什么要这么做？

原理&细节这几个角度去综合分析一下。

# 模拟战争环境：

## 对手模拟：

假设我们的对手是目前国内Apk风控的天花板 ，每个策略都是熟练掌握客户端对抗的人 。

客户端也是顶级检测团队 ，如果发现客户端一丁点风险可以写策略对其打击  ，比如下面的一些常见操作。

- 行为识别&Socket埋点上报（检测用户是否是正常用户，判断指定场景埋点等信息是否正常）
- 查杀分离（当发现客户端存在问题的时候，不会立刻去封你的号，防止客户端测试找到封号点 ）
- 点击路径矩阵（记录当前对当前页面的点击操作坐标）
- 多层策略嵌套（服务端有历史各种策略，如果某一个点没有改机改全，即可封号，被降权）

> 比如在A地方获取设备信息B ，在C地方获取的也是设备信息B 。如果A和C获取结果不一样，则认为设备异常，这种多级校准策略
>
>
- 安全SDK检测能力天花板：

（安全SDK检测能力也是国内的天花板，Hook,沙箱，重打包，Hook框架等检测也是最强，**我们暴露给的只有手机解锁**）
- AI用户行为&策略学习

（不断地自动化推导当前用户是否是一个正常设备）
- 实时监控与响应：

（实时监控客户端行为，及时发现异常并采取相应的应对措施。）
- IP聚集性检测等
- 抓取频次策略

（比如一分钟/一小时/24小时，抓取多少）

**在上述情况同时存在的情况下 ，我们应该如何绕过，实现抓取量化呢？**

## 对抗模拟：

第一步：

5台手机，20个账号 。 一个账号假设阈值为1000数据量/一天。超过数据量即封号。先把第一步跑通以后，后面逐步增加设备和账号。

![image-20240524185544391](https://bbs.kanxue.com/upload/attach/202405/DN3YE7NMDAM222P.jpg)![image](https://bbs.kanxue.com/upload/attach/202405/819934_24U4RV5F65C38SG.webp)

这些是一个简单的架构图，客户端里面的【设备指纹】和【环境信息对抗】是这部分最核心的 。全文30%架构设计，70%跟设备对抗相关 。

手机系统有要求：

**需要Android 11以上，13以上最好，刷入了Apatch 。**

这块有个细节点，为什么需要Android11以上的手机呢？

> 这个其实是因为Android的一个严重漏洞导致的，就是Android11以下，哪怕没有权限也可以通过netlinker直接获取到你得网卡信息 ，
>
> 详细代码实现可以参考我之前写的文章：这个代码在github有开源 <https://bbs.kanxue.com/thread-271698.htm> 。
>
> （不过我只有10以下的手机的话，可以直接往内核打补丁，然后重新编译内核刷入，也是可以的，不过麻烦点，不推荐）
>
> 不需要任何授权，而且还可以读一些net文件直接通过cat的方式获取 ，而且11以下，还有可以使用老的SD卡读写权限，直接往SD卡写入。
>
> 新版本只允许你往/sdcard/Android/data/包名里面去写入SD卡相关数据，这样在Apk卸载的时候直接就会一起删除。有很多大厂的指纹非常恶心。
>
> 会往SD卡里面写入一些文件种子，如果不进行隔离，很难改的全。
>
>

后面我会详细慢慢说，为什么需要使用Apatch ，包括为什么不用Magisk。

## 客户端架构：

客户端想要实现的功能就两部分【设备指纹对抗】&【环境信息对抗】 ，我修改指纹之前，需要先需要知道设备指纹是怎么产生的，比如一些有用的设备指纹比如最基本的一个AndroidId这种，他的产生就在服务端 。

**我们为了尽可能让客户端设备指纹对抗做的隐藏，因为我们不能修改目标Apk任何代码，所以就需要在他生产的地方进行修改。**

下面简单将设备指纹梳理一下 。

### 设备指纹分类：

#### 系统服务相关设备指纹相关

| 设备指纹分类 | 产生位置 | 描述 |
|-|-|-|
| Android Id | system_server |  |
| 各种Id IMEI这些 | system_server |  |
| Apk包相关 | system_server |  |
| 蓝牙相关 | system_server |  |
| wifi信息相关 | system_server |  |

#### 其他ApkSettingsProvider提供相关

| 设备指纹分类 | 产生位置 | 描述 |
|-|-|-|
| SettingsProvider | 安全中心 | 比如oaid，这种获取方式就是通过内容提供者的方式，通过某个Apk提供的,比如小米的就是小米的安全中心提供的,可以直接在小米安全中心进程去做Hook 。 |

#### 内核ID相关

| 设备指纹分类（内核相关） | 产生位置 | 描述 |
|-|-|-|
| /proc/sys/kernel/random/boot_id | 内核 | 保存内核相关,修改11以上可能导致RES资源文件出现问题,需要用mknod去进行修改。 |
| /sys/block/mmcblk0/device/cid | 内核 |  |
| /sys/block/mmcblk0/device/serial | 内核 |  |
| /sys/devices/soc0/serial_number | 内核 | cpu协议, 有的cpu不支持 |

#### Init进程设备指纹相关

这个进程比较特殊，init进程，init进程是最早的进程。内核启动的第一条进程 ，

目前发现DRM产生位置是在init进程产生的 。底层通过native binder进行的通讯 。

比如DRM如果想修改，可以在客户端获取的时候去修改，Java和C 都需要进行Hook 。比如常见的Java和C获取 。

Java获取如下：

```
import android.media.MediaDrm;
import java.util.UUID;
try {
UUID wideVineUuid = new UUID(-0x121074568629b532L, -0x5c37d8232ae2de13L);
MediaDrm wvDrm = new MediaDrm(wideVineUuid);
byte[] wideVineId =
wvDrm.getPropertyByteArray(MediaDrm.PROPERTY_DEVICE_UNIQUE_ID);
Log.i("DRM ID", bytesToHex(wideVineId));
wvDrm.release();
} catch (UnsupportedSchemeException e) {
e.printStackTrace();
}
```

c获取如下：

```
#include <media/NdkMediaDrm.h>
const uint8_t uuid[] =
{0xed,0xef,0x8b,0xa9,0x79,0xd6,0x4a,0xce,0xa3,0xc8,0x27,0xdc,0xd5,0x1d,0x21,0xed
};
AMediaDrm *mediaDrm = AMediaDrm_createByUUID(uuid);
AMediaDrmByteArray aMediaDrmByteArray;
AMediaDrm_getPropertyByteArray(mediaDrm, PROPERTY_DEVICE_UNIQUE_ID,
&aMediaDrmByteArray);
AMediaDrm_release(mediaDrm);
```

这个C和Java的最终流程都是调用init进程的IPC进行获取的 。

最终进程位置在 ，android.hardware.drm这个里面 。

```
C:\Users\ASUS>adb shell
cmi:/ $ su
cmi:/ # ps -ef | grep -service.widevine | grep android.hardware.drm
media         1069     1 0 19:31:15 ?     00:00:00 android.hardware.drm@1.3-service.widevine
```

#### Apk环境相关

环境相关指的是getprop的方式去获取的，一些环境相关的设备指纹。

## 设备指纹对抗：

经过上面的梳理 ，我们发现设备指纹主要的产生位置分为五大类，这五大类，可以包含安卓目前全部的设备指纹产生方式 。

下来我们需要对这些进程进行Hook和修改 ，因为我们不能再客户端进程去修改，所以需要在这五大设备指纹产生类型的地方进行修改。

## 前置准备 ：

我们需要用Magisk模块去实现一个Xposed ，为什么要自己去实现一个呢？

> 因为在可以用Magisk模块在指定进程注入lsplant，实现Java Hook， 比如修改system_server里面的去hook一些Java方法
>
> 很方便，自己实现的话逻辑也可控 ，方便Hook除了目标Apk以外的其他进程。
>
>

这块实现也很简单，lsposed是开源的 。这块还是建议从头写一遍，加深印象，如果有什么不明白的 再去lsposed里面翻源码 。

这块简单说一下具体的实现思路  。

### Magisk模块基础：

Magisk模块提供了 Zygisk进行注入 ， 其实是提供了五个方法，分别是 。

- onLoad
- preAppSpecialize
- postAppSpecialize
- preServerSpecialize
- postServerSpecialize

这五个方法也是zygisk对应的接口，相当于Xposed的Loadpackage 。

其实我们会发现 有一个pre和一个post ，

pre方法是指，当前没有被设置沙箱化 ，比如我们的Apk在zygote里面孵化出来的时候，就是一条普通的进程，

为什么只允许读取/data/data/包名下的内容 ，而不能读取别的apk里面的内容 ，是因为被专业化的操作了 。

Magisk模块里面叫specialization  。下面是magisk模块头文件里面的原话，翻译是gpt翻译的。

```
On Android, all app processes are forked from a special daemon called "Zygote".
For each new app process, zygote will fork a new process and perform "specialization".
This specialization operation enforces the Android security sandbox on the newly forked
process to make sure that 3rd party application code is only loaded after it is being
restricted within a sandbox.
在 Android 上，所有的应用进程都是从一个特殊的守护进程 "Zygote" 分叉(fork)出来的。
对于每一个新的应用进程，Zygote 会分叉一个新进程并进行 "(specialization)" 操作。
这个专门化操作强制实施 Android 安全沙盒，确保第三方应用代码只有在被限制在沙盒中之后才加载。

On Android, there is also this special process called "system_server". This single
process hosts a significant portion of system services, which controls how the
Android operating system and apps interact with each other.
在 Android 上，还有一个特殊的进程叫做 "system_server"。
这个单一进程承载了大部分的系统服务，控制着 Android 操作系统和应用程序之间的互动方式。

The Zygisk framework provides a way to allow developers to build modules and run custom
code before and after system_server and any app processes' specialization.
This enable developers to inject code and alter the behavior of system_server and app processes.
Zygisk 框架提供了一种方法，允许开发者构建模块并在 system_server
和任何应用进程的specialization之前和之后运行自定义代码。
这使开发者能够注入代码并改变 system_server 和应用进程的行为。

Please note that modules will only be loaded after zygote has forked the child process.
THIS MEANS ALL OF YOUR CODE RUNS IN THE APP/SYSTEM_SERVER PROCESS, NOT THE ZYGOTE DAEMON!
请注意，模块只会在 Zygote fork 子进程之后加载。
这意味着你的所有代码都是在应用/系统服务器进程中运行，而不是在 Zygote 守护进程中运行！
```

所以我们可以在某个Apk 没有被设置selinux规则和沙箱话之前进行一些操作 。比如chroot这种都可以进行，比如shamiko好像就是执行chroot，这时候各种权限都没有，让我们的目标App单独隔离到一个新的根目录下，实现的过掉root检测 。

post是被设置专业化完毕以后的回调，pre是设置专业化之前 。

五个方法其中两个是系统服务的，pre和post，另外的是当某个App加载的pre和post 。

为了方便学习，我让gtp把这个zygisk.hpp翻译了一下 ，可以参考中文去学习magisk模块的基本Api操作 。

```
/* Copyright 2022-2023 John "topjohnwu" Wu
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
 * REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
 * AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
 * INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
 * LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
 * OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
 * PERFORMANCE OF THIS SOFTWARE.
 */

// This is the public API for Zygisk modules.
// DO NOT MODIFY ANY CODE IN THIS HEADER.

#pragma once

#include <jni.h>
#include <ostream>
#include <sstream>
#include <string>

#define ZYGISK_API_VERSION 4

/*

***************
* Introduction
***************

On Android, all app processes are forked from a special daemon called "Zygote".
For each new app process, zygote will fork a new process and perform "specialization".
This specialization operation enforces the Android security sandbox on the newly forked
process to make sure that 3rd party application code is only loaded after it is being
restricted within a sandbox.
在 Android 上，所有的应用进程都是从一个特殊的守护进程 "Zygote" 分叉(fork)出来的。
对于每一个新的应用进程，Zygote 会分叉一个新进程并进行 "(specialization)" 操作。
这个专门化操作强制实施 Android 安全沙盒，确保第三方应用代码只有在被限制在沙盒中之后才加载。

On Android, there is also this special process called "system_server". This single
process hosts a significant portion of system services, which controls how the
Android operating system and apps interact with each other.
在 Android 上，还有一个特殊的进程叫做 "system_server"。
这个单一进程承载了大部分的系统服务，控制着 Android 操作系统和应用程序之间的互动方式。

The Zygisk framework provides a way to allow developers to build modules and run custom
code before and after system_server and any app processes' specialization.
This enable developers to inject code and alter the behavior of system_server and app processes.
Zygisk 框架提供了一种方法，允许开发者构建模块并在 system_server
和任何应用进程的specialization之前和之后运行自定义代码。
这使开发者能够注入代码并改变 system_server 和应用进程的行为。

Please note that modules will only be loaded after zygote has forked the child process.
THIS MEANS ALL OF YOUR CODE RUNS IN THE APP/SYSTEM_SERVER PROCESS, NOT THE ZYGOTE DAEMON!
请注意，模块只会在 Zygote fork 子进程之后加载。
这意味着你的所有代码都是在应用/系统服务器进程中运行，而不是在 Zygote 守护进程中运行！

*********************
* Development Guide
*********************

Define a class and inherit zygisk::ModuleBase to implement the functionality of your module.
Use the macro REGISTER_ZYGISK_MODULE(className) to register that class to Zygisk.

Example code:

static jint (*orig_logger_entry_max)(JNIEnv *env);
static jint my_logger_entry_max(JNIEnv *env) {
 return orig_logger_entry_max(env);
}

class ExampleModule : public zygisk::ModuleBase {
public:
    void onLoad(zygisk::Api *api, JNIEnv *env) override {
        this->api = api;
        this->env = env;
    }
    void preAppSpecialize(zygisk::AppSpecializeArgs *args) override {
        JNINativeMethod methods[] = {
            { "logger_entry_max_payload_native", "()I", (void*) my_logger_entry_max },
        };
        api->hookJniNativeMethods(env, "android/util/Log", methods, 1);
        *(void **) &orig_logger_entry_max = methods[0].fnPtr;
    }
private:
    zygisk::Api *api;
    JNIEnv *env;
};

REGISTER_ZYGISK_MODULE(ExampleModule)

-----------------------------------------------------------------------------------------

or runs in the sandbox of the target process in post[XXX]Specialize, the code in your class
never runs in a true superuser environment.
由于你的模块类的代码在 pre[XXX]Specialize 中以 Zygote 的特权运行，
或者在 post[XXX]Specialize 中在目标进程的沙盒中运行，你的类中的代码从不在一个真正的超级用户环境中运行。

If your module require access to superuser permissions, you can create and register
a root companion handler function. This function runs in a separate root companion
daemon process, and an Unix domain socket is provided to allow you to perform IPC between
your target process and the root companion process.
如果你的模块需要访问超级用户权限，你可以创建并注册一个根伴随处理函数(root companion handler function)。
这个函数在一个单独的根伴随守护进程中运行，并提供了一个 Unix socket，允许你在目标进程和根伴随进程之间进行
IPC（进程间通信）。

Example code:

static void example_handler(int socket) { ... }

REGISTER_ZYGISK_COMPANION(example_handler)

*/

namespace zygisk {

    struct Api;
    struct AppSpecializeArgs;
    struct ServerSpecializeArgs;

    class ModuleBase {
    public:

        // This method is called as soon as the module is loaded into the target process. A Zygisk API handle will be passed as an argument.
        // 一旦模块被加载到目标进程中，就会调用此方法。一个 Zygisk API 句柄会作为参数传递。
        virtual void onLoad([[maybe_unused]] Api *api, [[maybe_unused]] JNIEnv *env) {}

        // This method is called before the app process is specialized.
        // At this point, the process just got forked from zygote, but no app specific specialization
        // is applied. This means that the process does not have any sandbox restrictions and
        // still runs with the same privilege of zygote.
        // 在应用进程专业化之前调用，此时进程刚从 zygote 分叉出来，但还未应用任何特定于应用的专业化设置。
        // 这意味着进程还没有任何沙箱限制，并且仍然以 zygote 相同的权限运行。
        virtual void preAppSpecialize([[maybe_unused]] AppSpecializeArgs *args) {}

        // This method is called after the app process is specialized.
        // At this point, the process has all sandbox restrictions enabled for this application.
        // This means that this method runs with the same privilege of the app's own code.
        // 在应用进程专业化之后调用，此时进程已经为该应用启用了所有沙盒限制。
        // 这意味着这个方法与应用自己的代码以相同的权限运行。
        virtual void postAppSpecialize([[maybe_unused]] const AppSpecializeArgs *args) {}

        // This method is called before the system server process is specialized.
        // 在系统服务器进程专业化之前调用此方法。
        // See preAppSpecialize(args) for more info.
        // 有关更多信息，请参考 preAppSpecialize(args)。
        virtual void preServerSpecialize([[maybe_unused]] ServerSpecializeArgs *args) {}

        // This method is called after the system server process is specialized.
        // At this point, the process runs with the privilege of system_server.
        // 在系统服务器进程专业化之后调用。
        // 此时，进程以 system_server 的权限运行。
        virtual void postServerSpecialize([[maybe_unused]] const ServerSpecializeArgs *args) {}
    };

    struct AppSpecializeArgs {
        // Required arguments.
        // These arguments are guaranteed to exist on all Android versions.
        jint &uid;
        jint &gid;
        jintArray &gids;
        jint &runtime_flags;
        jobjectArray &rlimits;
        jint &mount_external;
        jstring &se_info;
        jstring &nice_name;
        jstring &instruction_set;
        jstring &app_data_dir;

        // Optional arguments. Please check whether the pointer is null before de-referencing
        jintArray *const fds_to_ignore;
        jboolean *const is_child_zygote;
        jboolean *const is_top_app;
        jobjectArray *const pkg_data_info_list;
        jobjectArray *const whitelisted_data_info_list;
        jboolean *const mount_data_dirs;
        jboolean *const mount_storage_dirs;

        AppSpecializeArgs() = delete;

        std::string toString(JNIEnv *env) const {
            std::ostringstream stream;
            printJString(env, stream, "nice_name", nice_name);

            printJString(env, stream, "app_data_dir", app_data_dir);

            printJString(env, stream, "se_info", se_info);
            printJString(env, stream, "instruction_set", instruction_set);
            stream << "uid: " << uid << " gid: " << gid << " runtime_flags: " << runtime_flags
                   << " mount_external: " << mount_external;

            printJIntArray(env, stream, "gids", gids);

            printJBoolean(env, stream, "is_child_zygote", is_child_zygote);
            printJBoolean(env, stream, "is_top_app", is_top_app);
            printJBoolean(env, stream, "mount_data_dirs", mount_data_dirs);
            printJBoolean(env, stream, "mount_storage_dirs", mount_storage_dirs);

            printJObjectArrayPointer(env, stream, "pkg_data_info_list", pkg_data_info_list);
            printJObjectArrayPointer(env, stream, "whitelisted_data_info_list",
                                     whitelisted_data_info_list);

            return stream.str();
        }

    private:
        [[maybe_unused]]
        void printJString(JNIEnv *env, std::ostringstream &stream, const std::string &name,
                          jstring value) const {
            if (value != nullptr) {
                const char *chars = env->GetStringUTFChars(value, nullptr);
                stream << " " << name << ": " << chars << "\n";
                env->ReleaseStringUTFChars(value, chars);
            } else {
                stream << " " << name << ": null" << "\n";
            }
        }

        [[maybe_unused]]
        void printJIntArray(JNIEnv *env, std::ostringstream &stream, const std::string &name,
                            jintArray value) const {
            if (value != nullptr) {
                jsize length = env->GetArrayLength(value);
                jint *elements = env->GetIntArrayElements(value, nullptr);
                stream << " " << name << ": [";
                for (jsize i = 0; i < length; ++i) {
                    stream << elements[i];
                    if (i < length - 1) {
                        stream << ", ";
                    }
                }
                stream << "]" << "\n";
                env->ReleaseIntArrayElements(value, elements, JNI_ABORT);
            } else {
                stream << " " << name << ": null" << "\n";
            }
        }

        [[maybe_unused]]
        void printJBoolean(JNIEnv *env, std::ostringstream &stream,
                           const std::string &name, jboolean *value) const {
            if (value != nullptr) {
                stream << " " << name << ": " << ((*value) == JNI_TRUE ? "true" : "flase") << "\n";
            } else {
                stream << " " << name << ": null" << "\n";
            }
        }

        [[maybe_unused]]
        void
        printJObjectArrayPointer(JNIEnv *env, std::ostringstream &stream, const std::string &name,
                                 jobjectArray *arrayPtr) const {
            if (arrayPtr && *arrayPtr) {
                jobjectArray array = *arrayPtr;
                jsize length = env->GetArrayLength(array);
                stream << " " << name << ": [";
                for (jsize i = 0; i < length; ++i) {
                    jstring str = (jstring) env->GetObjectArrayElement(array, i);
                    const char *chars = env->GetStringUTFChars(str, nullptr);
                    stream << chars;
                    env->ReleaseStringUTFChars(str, chars);
                    if (i < length - 1) {
                        stream << ", ";
                    }
                }
                stream << "]" << "\n";
            } else {
                stream << " " << name << ": null" << "\n";
            }
        }

    };

    struct ServerSpecializeArgs {
        jint &uid;
        jint &gid;
        jintArray &gids;
        jint &runtime_flags;
        jlong &permitted_capabilities;
        jlong &effective_capabilities;

        ServerSpecializeArgs() = delete;
    };

    namespace internal {
        struct api_table;

        template<class T>
        void entry_impl(api_table *, JNIEnv *);
    }
    // These values are used in Api::setOption(Option)
    // 这些值被用在 Api::setOption(Option) 方法中
    enum Option : int {
        // Force Magisk's denylist unmount routines to run on this process.
        // 强制在此进程上运行 Magisk 的拒绝列表unmount routines。
        //
        // Setting this option only makes sense in preAppSpecialize.
        // 只有在 preAppSpecialize 中设置此选项才有意义。
        // The actual unmounting happens during app process specialization.
        // 实际的卸载过程发生在应用进程specialization期间。
        //
        // Set this option to force all Magisk and modules' files to be unmounted from the
        // mount namespace of the process, regardless of the denylist enforcement status.
        // 设置此选项以强制从进程的挂载命名空间中卸载所有 Magisk 和模块的文件，无论拒绝列表的执行状态如何。
        // 这个主要是卸载magisk整个系统文件
        FORCE_DENYLIST_UNMOUNT = 0,

        // When this option is set, your module's library will be dlclose-ed after post[XXX]Specialize.
        // 设置此选项时，你的模块库将在 post[XXX]Specialize 之后被 dlclose。
        // Be aware that after dlclose-ing your module, all of your code will be unmapped from memory.
        // 注意，dlclose 你的模块后，你所有的代码都将从内存中取消映射。
        // YOU MUST NOT ENABLE THIS OPTION AFTER HOOKING ANY FUNCTIONS IN THE PROCESS.
        // 在进程中挂钩任何函数后，你必须不启用此选项。
        // 这个是卸载so文件
        DLCLOSE_MODULE_LIBRARY = 1,
    };

    // Bit masks of the return value of Api::getFlags()
    // Api::getFlags() 返回值的位掩码
    enum StateFlag : uint32_t {
        // The user has granted root access to the current process
        // 用户已授予当前进程根访问权限
        PROCESS_GRANTED_ROOT = (1u << 0),

        // The current process was added on the denylist
        // 当前进程被添加到拒绝列表中
        PROCESS_ON_DENYLIST = (1u << 1),
    };

    // All API methods will stop working after post[XXX]Specialize as Zygisk will be unloaded
    // from the specialized process afterwards.
    // 所有API方法post[XXX]Specialize后停止工作，因为Zygisk将在之后从专业化过程中卸载。
    struct Api {

        // Connect to a root companion process and get a Unix domain socket for IPC.
        // 获取和root守护进程通讯的句柄,可以直接通过这个句柄进行ipc通讯 。
        // 连接到root companion进程并获取 Unix socket进行 IPC。
        //
        // This API only works in the pre[XXX]Specialize methods due to SELinux restrictions.
        // 由于 SELinux 限制，此 API 仅在 pre[XXX]Specialize 方法中有效。
        //
        // The pre[XXX]Specialize methods run with the same privilege of zygote.
        // pre[XXX]Specialize 方法以与 zygote 相同的权限运行。
        // If you would like to do some operations with superuser permissions, register a handler
        // function that would be called in the root process with REGISTER_ZYGISK_COMPANION(func).
        // 如果你想以超级用户权限执行一些操作，请注册一个处理函数，
        // 在根进程中以 REGISTER_ZYGISK_COMPANION(func) 调用。

        // Another good use case for a companion process is that if you want to share some resources
        // across multiple processes, hold the resources in the companion process and pass it over.
        // companion进程的另一个好用途是，如果你想在多个进程间共享一些资源，
        // 可以在companion进程中保持这些资源并传递过去。
        //
        // The root companion process is ABI aware; that is, when calling this method from a 32-bit
        // process, you will be connected to a 32-bit companion process, and vice versa for 64-bit.
        // root伴随进程是 ABI 意识到的；
        // 也就是说，当从 32 位进程调用此方法时，你将连接到一个 32 位的伴随进程，对于 64 位也是如此。
        //
        // Returns a file descriptor to a socket that is connected to the socket passed to your
        // module's companion request handler. Returns -1 if the connection attempt failed.
        // 返回一个文件描述符到一个套接字，该套接字连接到传递给模块的伴随请求处理器的套接字。
        // 如果连接尝试失败，则返回 -1。
        int connectCompanion();

        // Get the file descriptor of the root folder of the current module.
        // 获取当前模块的根文件夹的文件描述符。
        //
        // This API only works in the pre[XXX]Specialize methods.
        // 此 API 仅在 pre[XXX]Specialize 方法中工作。
        // Accessing the directory returned is only possible in the pre[XXX]Specialize methods
        // or in the root companion process (assuming that you sent the fd over the socket).
        // 只有在 pre[XXX]Specialize 方法或根伴随进程中（假设你通过套接字发送了 fd）才能访问返回的目录。
        // Both restrictions are due to SELinux and UID.
        // 这两个限制都是由于 SELinux 和 UID。
        //
        // Returns -1 if errors occurred.
        // 如果发生错误，则返回 -1。
        int getModuleDir();

        // Set various options for your module.
        // 为你的模块设置各种选项。
        // Please note that this method accepts one single option at a time.
        // 请注意，此方法一次只接受一个选项。
        // Check zygisk::Option for the full list of options available.
        // 查看 zygisk::Option 以获取可用选项的完整列表。
        void setOption(Option opt);

        // Get information about the current process.
        // 获取有关当前进程的信息。
        // Returns bitwise-or'd zygisk::StateFlag values.
        // 返回按位或的 zygisk::StateFlag 值。
        uint32_t getFlags();

        // Exempt the provided file descriptor from being automatically closed.
        // 免除提供的文件描述符被自动关闭。
        //
        // This API only make sense in preAppSpecialize; calling this method in any other situation
        // is either a no-op (returns true) or an error (returns false).
        // 此 API 仅在 preAppSpecialize 中有意义；
        // 在任何其他情况下调用此方法要么是无操作（返回 true），要么是错误（返回 false）。
        //
        // When false is returned, the provided file descriptor will eventually be closed by zygote.
        // 当返回 false 时，提供的文件描述符最终将被 zygote 关闭。
        bool exemptFd(int fd);

        // Hook JNI native methods for a class
        // 为一个类挂钩 JNI 原生方法
        //
        // Lookup all registered JNI native methods and replace it with your own methods.
        // 查找所有注册的 JNI 原生方法并用你自己的方法替换它。
        // The original function pointer will be saved in each JNINativeMethod's fnPtr.
        // 原始函数指针将被保存在每个 JNINativeMethod 的 fnPtr 中。
        // If no matching class, method name, or signature is found, that specific JNINativeMethod.fnPtr
        // will be set to nullptr.
        // 如果没有找到匹配的类、方法名或签名，那么特定的 JNINativeMethod.fnPtr 将被设置为 nullptr。
        void hookJniNativeMethods(JNIEnv *env, const char *className, JNINativeMethod *methods,
                                  int numMethods);

        // Hook functions in the PLT (Procedure Linkage Table) of ELFs loaded in memory.
        // hook在内存中加载的 ELF 文件的 PLT（程序链接表）中得函数。
        //
        // Parsing /proc/[PID]/maps will give you the memory map of a process. As an example:
        // 解析 /proc/[PID]/maps 将给你一个进程的内存映射。例如：
        //
        //       <address>       <perms>  <offset>   <dev>  <inode>           <pathname>
        //       地址             权限    偏移量     设备    节点               路径名
        // 56b4346000-56b4347000  r-xp    00002000   fe:00    235       /system/bin/app_process64
        // (More details: https://man7.org/linux/man-pages/man5/proc.5.html)
        // （更多详情请访问：https://man7.org/linux/man-pages/man5/proc.5.html）
        //
        // The `dev` and `inode` pair uniquely identifies a file being mapped into memory.
        // `dev` 和 `inode` 对唯一标识了被映射到内存中的文件。
        // For matching ELFs loaded in memory, replace function `symbol` with `newFunc`.
        // 对于匹配的在内存中加载的 ELF 文件，将函数 `symbol` 替换为 `newFunc`。
        // If `oldFunc` is not nullptr, the original function pointer will be saved to `oldFunc`.
        // 如果 `oldFunc` 不是 nullptr，原始的函数指针将被保存到 `oldFunc`。
        void
        pltHookRegister(dev_t dev, ino_t inode, const char *symbol, void *newFunc, void **oldFunc);

        // Commit all the hooks that was previously registered.
        // 提交之前注册的所有钩子。
        // Returns false if an error occurred.
        // 如果发生错误，返回 false。
        bool pltHookCommit();

    private:
        internal::api_table *tbl;

        template<class T>
        friend void internal::entry_impl(internal::api_table *, JNIEnv *);
    };

// Register a class as a Zygisk module

#define REGISTER_ZYGISK_MODULE(clazz) \
void zygisk_module_entry(zygisk::internal::api_table *table, JNIEnv *env) { \
    zygisk::internal::entry_impl<clazz>(table, env);                        \
}

// Register a root companion request handler function for your module
// 为模块注册root伴随请求处理程序函数

// The function runs in a superuser daemon process and handles a root companion request from
// your module running in a target process.
// 该函数在超级用户守护进程中运行，并处理来自目标进程中运行的模块的根伴随请求。
// The function has to accept an integer value,
// which is a Unix domain socket that is connected to the target process.
// 函数必须接受一个整数值，该整数值是连接到目标进程的Unix socket。

// See Api::connectCompanion() for more info.
//
// NOTE:
// the function can run concurrently on multiple threads.
// Be aware of race conditions if you have globally shared resources.
// 该函数可以在多个线程上同时运行。如果您拥有全球共享的资源，请注意种族状况。

#define REGISTER_ZYGISK_COMPANION(func) \
void zygisk_companion_entry(int client) { func(client); }

/*********************************************************
 * The following is internal ABI implementation detail.
 * You do not have to understand what it is doing.
 *********************************************************/

    namespace internal {

        struct module_abi {
            long api_version;
            ModuleBase *impl;

            void (*preAppSpecialize)(ModuleBase *, AppSpecializeArgs *);

            void (*postAppSpecialize)(ModuleBase *, const AppSpecializeArgs *);

            void (*preServerSpecialize)(ModuleBase *, ServerSpecializeArgs *);

            void (*postServerSpecialize)(ModuleBase *, const ServerSpecializeArgs *);

            module_abi(ModuleBase *

            module) : api_version(ZYGISK_API_VERSION), impl(module) {
                preAppSpecialize = [](auto m, auto args) { m->preAppSpecialize(args); };
                postAppSpecialize = [](auto m, auto args) { m->postAppSpecialize(args); };
                preServerSpecialize = [](auto m, auto args) { m->preServerSpecialize(args); };
                postServerSpecialize = [](auto m, auto args) { m->postServerSpecialize(args); };
            }
        };

        struct api_table {
            // Base
            void *impl;

            bool (*registerModule)(api_table *, module_abi *);

            void (*hookJniNativeMethods)(JNIEnv *, const char *, JNINativeMethod *, int);

            void (*pltHookRegister)(dev_t, ino_t, const char *, void *, void **);

            bool (*exemptFd)(int);

            bool (*pltHookCommit)();

            int (*connectCompanion)(void * /* impl */);

            void (*setOption)(void * /* impl */, Option);

            int (*getModuleDir)(void * /* impl */);

            uint32_t (*getFlags)(void * /* impl */);
        };

        template<class T>
        void entry_impl(api_table *table, JNIEnv *env) {
            static Api api;
            api.tbl = table;
            static T module;
            ModuleBase *m = &module;
            static module_abi abi(m);
            if (!table->registerModule(table, &abi)) return;
            m->onLoad(&api, env);
        }

    } // namespace internal

    inline int Api::connectCompanion() {
        return tbl->connectCompanion ? tbl->connectCompanion(tbl->impl) : -1;
    }

    inline int Api::getModuleDir() {
        return tbl->getModuleDir ? tbl->getModuleDir(tbl->impl) : -1;
    }

    inline void Api::setOption(Option opt) {
        if (tbl->setOption) tbl->setOption(tbl->impl, opt);
    }

    inline uint32_t Api::getFlags() {
        return tbl->getFlags ? tbl->getFlags(tbl->impl) : 0;
    }

    inline bool Api::exemptFd(int fd) {
        return tbl->exemptFd != nullptr && tbl->exemptFd(fd);
    }

    inline void
    Api::hookJniNativeMethods(JNIEnv *env, const char *className, JNINativeMethod *methods,
                              int numMethods) {
        if (tbl->hookJniNativeMethods)
            tbl->hookJniNativeMethods(env, className, methods, numMethods);
    }

    inline void Api::pltHookRegister(dev_t dev, ino_t inode, const char *symbol, void *newFunc,
                                     void **oldFunc) {
        if (tbl->pltHookRegister) tbl->pltHookRegister(dev, inode, symbol, newFunc, oldFunc);
    }

    inline bool Api::pltHookCommit() {
        return tbl->pltHookCommit != nullptr && tbl->pltHookCommit();
    }

} // namespace zygisk

extern "C" {

[[gnu::visibility("default"), maybe_unused]]
void zygisk_module_entry(zygisk::internal::api_table *, JNIEnv *);

[[gnu::visibility("default"), maybe_unused]]
void zygisk_companion_entry(int);

} // extern "C"
```

更多Api操作，包括系统文件替换，修改selinux权限等操作 ，这里不过多介绍 ，详细的话可以参考官网 。

传送门：<https://topjohnwu.github.io/Magisk/guides.html>

### Magisk模块如何实现一个Xposed ?

掌握了magisk模块基础以后可以尝试，可以尝试自己实现一个lsposed，lsposed开源版本正好也不支持android 15 ，实现了只要Lsplant支持到15

即可在android 15上去使用 。这里再次感谢lsplant的开发者 ~

我们需要先把编译的java代码在magisk模块里面执行 ，让他在系统服务（system_server）里面去执行java代码 。然后在执行后续的操作 。

下面是具体的实现流程：

#### 1、Magisk模块加载java代码

我们可以先把我们自己编译的Java代码，丢到magisk模块的system/framework文件夹下 ，让系统服务在启动的时候加载我们的jar包 。

在系统服务回调里面直接用PathClassloader去加载jar包即可 ，然后反射调用里面的静态方法 。第一步实现从Magisk模块转到java调用 。

因为jar包放的是system/framework ，这个文件里面只有system_server有权限去读 ，其他的Apk是没有权限去读取的，所以不需要担心别的Apk读取到你自己的特征 。

#### 2、系统服务初始化

通过上面的设置，已经可以实现了调用java方法 ，我们下来再java方法里面对系统服务进行替换和mock , 然后再系统服务里面挂载我们的服务 可以在添加服务的时候替换成你自己的 。

如何hook添加函数呢？

可以动态代理即可 。当系统开始addService时候，添加服务是指定服务的时候 你可以把对应的服务替换成你得，你得服务里面包含【原始服务】和 【你自己的服务】

这样在别人请求的时候你可以用你的服务去做一些事情 。

```
  Object origServiceManager = ServiceManager.getIServiceManager.callStatic();
        //在SystemServer还没有添加系统服务的时候进行动态代理
        ServiceManager.sServiceManager.setStaticValue(Reflection.on("android.os.IServiceManager")
                .proxy((proxy, method, args) -> {
                    if ("addService".equals(method.getName())) {
                        String serviceName = (String) args[0];
                        IBinder binder = (IBinder) args[1];
                        //CLog.w("[" + serviceName + "] -> [" + binder + "]");
                        if (ServerConfig.TARGET_BINDER_SERVICE_NAME.equals(serviceName)) {
                            // Replace the clipboard service so apps can acquire binder
                            args[1] = new BinderServiceProxy((Binder) args[1],
                                    ServerConfig.TARGET_BINDER_SERVICE_DESCRIPTOR, rms);
                            clipboardServiceReplaced = true;
                        }  else if (Context.ACTIVITY_SERVICE.equals(serviceName)) {
                            RuntimeManagerService.initContext();
                        }
                        if (clipboardServiceReplaced)
                            //set orig ServiceManager
                            ServiceManager.sServiceManager.setStaticValue(origServiceManager);
                        }

                    try {
                        return method.invoke(origServiceManager, args);
                    } catch (InvocationTargetException e) {
                        throw e.getTargetException();
                    }
                }));
```

直接动态代理 ServiceManager ，这样在系统服务添加各种各样的Manager的时候，如果发现是指定的系统服务，替换成你自己的即可 。你得这个系统服务需要实现Binder ，添加完毕以后 我们在发服务端暴露一个接口 ，做共享内存 。

#### 3、共享内存的实现

首先说一下这块为什么要用共享内存去实现 ，之前edxp这种他是在你需要hook进程里面去注入dex，这样的话dex已经被注入了 ，特征太多 。

> 检测也很好检测，直接用内存漫游去内存里面扣DexFile File 的个数，很容易检测到内存加载了多少个Dex
>
>

我们可以在服务端(system_service)搞个接口 ，等待客户端过来请求 ，然后用共享内存的方式把dex分配到指定客户端 。

比如我希望Hook Hunter, 我可以在Hunter启动里面 去请求服务端这个分配共享内存的接口 。服务端返回一个fd句柄 ，hunter直接用这个句柄mmap到内存里 ，然后用InMemoryDexClassLoader 去加载这个mmap到内存里的值 。得到classloader以后再去classloader里面findclass，去调用里面的方法即可 。

我们希望的是全局用一份dex即可，而不是每个进程都加载一份dex ，这样效率也不高  。下面这段代码就是当服务端收到客户端的请求，准备开始分配dex的代码 。

```
  else if (code == ServerConfig.DEX_TRANSACTION_CODE) {
            //CLog.i("RuntimeManagerService receive DEX_TRANSACTION_CODE "+.getCallAppName());
            try {
                //unzip jar
                unzip(RuntimeManagerService.RUNTIME_JAR_PATH,
                        RuntimeManagerService.RUNTIME_TEMP_DEX_PATH);
                //get dex
                File[] files = new File(RuntimeManagerService.RUNTIME_TEMP_DEX_PATH).listFiles();
                if (files == null || files.length == 0) {
                    CLog.i("DEX_TRANSACTION_CODE files size == 0 ");
                    return false;
                }
                @SuppressWarnings("all")
                List<File> dexFiles = Stream.of(files).
                        filter(file -> file.getName().endsWith(".dex")).collect(Collectors.toList());

                if (dexFiles.isEmpty()) {
                    CLog.i("DEX_TRANSACTION_CODE dexFiles.size()==0 ");
                    return false;
                }
                for(File file:dexFiles){
                    if(!file.exists()){
                        CLog.d("DEX_TRANSACTION_CODE dex file not find  "+file);
                        return false;
                    }
                }
                //CLog.i("DEX_TRANSACTION_CODE dex info " + dexFiles);
                ArrayList<SharedMemory> shm = RuntimeManagerService.getPreloadDex(dexFiles);
                if (shm == null || shm.isEmpty()) return false;
                reply.writeNoException();
                //dex size
                reply.writeInt(shm.size());
                for (int i = 0; i < shm.size(); i++) {
                    // assume that write only a fd
                    SharedMemory sharedMemory = shm.get(i);
                    sharedMemory.writeToParcel(reply, 0);
                    reply.writeLong(sharedMemory.getSize());
                }
                //clean temp dir
                try {
                    FileUtils.deleteDirectory(
                            new File(RuntimeManagerService.RUNTIME_TEMP_DEX_PATH)
                    );
                }catch (Throwable e) {
                    MagiskEngine.popen("rm -rf "+RuntimeManagerService.RUNTIME_TEMP_DEX_PATH);
                }
            } catch (Throwable e) {
                CLog.e("DEX_TRANSACTION_CODE handler error  " + e, e);
            }
            //CLog.i("RuntimeManagerService receive DEX_TRANSACTION_CODE return");
            return true;
        }
```

服务端直接打开/system/framework/myjar.jar , myjar里面装的是Dex

打开这个jar包以后，把这个jar包用SharedMemory加载到内存里 ，加载没问题以后直接往客户端写入 对应的SharedMemory句柄，这块支持多个dex写入，

写入方式如下 ：

```
SharedMemory sharedMemory = shm.get(i);
sharedMemory.writeToParcel(reply, 0);
```

我写入的格式是先写入具体加载fd的个数 ，然后对应的文件句柄 fd和fd的size  。

客户端从包裹里面读取服务端写入的值，按照顺序，先读取具体加载的fd句柄个数  ，然后for循环去读取fd和fd大小，加载fd即可 ,mmap加载到内存以后使用InMemoryDexClassLoader去加载 。

```
jobject DexLoader::FromDexFd(JNIEnv *env,
                             const std::vector<std::tuple<int, size_t>> fd_list,const std::string& process_name ) {
    if (fd_list.size() == 0) {
        LOGE("DexLoader::FromDexFd fd size<=0")
        return nullptr;
    }
    LOGI("DexLoader::FromDexFd start load dex %s ", process_name.c_str())

    jobjectArray byteBuffArray =
            env->NewObjectArray(fd_list.size(),env->FindClass("java/nio/ByteBuffer"), NULL);

    for(int i=0;i<fd_list.size();i++){
        std::tuple<int, size_t> fd_info =  fd_list.at(i);
        auto fd = std::get<0>(fd_info);
        auto size = std::get<1>(fd_info);
        auto *addr = mmap(nullptr, size, PROT_READ, MAP_SHARED, fd, 0);
        LOGI("DexLoader::FromDexFd mmap start -> %p  [%s] ",addr, printMappedRegion(addr).c_str())
        //auto *addr = mmap(nullptr, size, PROT_READ, MAP_ANONYMOUS | MAP_SHARED, fd, 0);
        if (addr == MAP_FAILED) {
            LOGE("DexLoader::FromDexFd mmap error %s ", strerror(errno))
            return nullptr;
        }
        //get byte buff
        ScopedLocalRef<jobject> buffer(env,env->NewDirectByteBuffer(addr, (long) size));
        env->SetObjectArrayElement(byteBuffArray,i,buffer.get());
        //LOGI("DexLoader::FromDexFd mmap success %lu %p - %p package name -> [%s] ", size,addr,(void*)((char*)addr+size),process_name.c_str())
    }
    if(InMemoryDexClassLoader == nullptr){
        InMemoryDexClassLoader = WellKnownClasses::CacheClass(env,
              "dalvik/system/InMemoryDexClassLoader");
    }
    if(InMemoryDexClassLoader_init == nullptr){
        //more dex
        InMemoryDexClassLoader_init = WellKnownClasses::CacheMethod(env,
              InMemoryDexClassLoader,"<init>","([Ljava/nio/ByteBuffer;Ljava/lang/ClassLoader;)V",false);
    }
    WellKnownClasses::Init(env);
    ScopedLocalRef<jobject> system_class_loader(env, env->CallStaticObjectMethod(
            WellKnownClasses::java_lang_ClassLoader,
            WellKnownClasses::java_lang_ClassLoader_getSystemClassLoader));
    jobject loader = env->NewObject(InMemoryDexClassLoader, InMemoryDexClassLoader_init,
                                    byteBuffArray, system_class_loader.get());
    if (JNIHelper::ExceptionCheck(env)) {
        return nullptr;
    }
    return loader;
}
```

这块在指定客户端加载的时候，你只需要初始化一下lsplant，即可实现对任意进程的java hook

#### 4、客户端如何规避Class检测？

如果我们注入了一条进程，但是目标进程通过内存漫游拿到的全部的classloader，然后去对每个classloader去loadclass ，

直接load比如某一个特征class，这样会导致这个class被暴露 ，导致我们代码泄漏 ，所以这块可以用一个内存混淆 ，主要用的是lsposed里面的obfuscation.cpp

他这个原理是对内存dex进行混淆 ，比如正常的路径是com/zhenxi/hack ，他可以混淆成A/B/C这种随机字符串包名 ，这块添加点在系统服务打开dex的时候，得到了这个SharedMemory以后，对里面的内容进行混淆 。

```
    private static SharedMemory readDex(InputStream in) throws IOException, ErrnoException {
        var memory = SharedMemory.create(null, in.available());
        var byteBuffer = memory.mapReadWrite();
        Channels.newChannel(in).read(byteBuffer);
        SharedMemory.unmap(byteBuffer);
        if (BuildConfig.isObfuscationDex) {
            //obfuscate dex
            SharedMemory newMemory = ObfuscationManager.obfuscateDex(memory);
            if (BuildConfig.isSavefuscationDex) {
                saveObfuscationDex(newMemory);
            }
            if (memory != newMemory) {
                memory.close();
                memory = newMemory;
            }
        }
        memory.setProtect(OsConstants.PROT_READ);
        return memory;
    }

    public synchronized static ArrayList<SharedMemory> getPreloadDex(List<File> dexFiles) {
        if (preloadDex == null) {
            preloadDex = new ArrayList<>();
            for (File dex_file : dexFiles) {
                if (!dex_file.exists()) {
                    CLog.e("RuntimeManagerService getPreloadDex file not find " + dex_file);
                    continue;
                }
                try (var is = new FileInputStream(dex_file)) {
                    preloadDex.add(readDex(is));
                } catch (Throwable e) {
                    CLog.e("RuntimeManagerService preload dex", e);
                    return null;
                }
            }
        }
        return preloadDex;
    }
```

因为你混淆了，还需要在服务端暴露一个查询接口 ，比如客户端得到的A/B/C的原始路径是com/zhenxi/hack，防止反射失败 。

可以站在obfuscation.cpp里面配置好自己需要混淆的路径即可。具体源码可以参考Lsposed 。

# 设备指纹对抗：

## 设备指纹相关的对抗（system_service）

系统服务的都很简单，直接在system_service初始化lsplant以后 ，直接用Xposedapi去hook即可 。

举个例子，修改整个android系统的android id 。直接hook SettingsProvider 里面的call方法即可对全部的android id进行修改 。

```
        Class<?> SettingsProviderClazz = RuntimeManagerService.findclass(
                    "com.android.providers.settings.SettingsProvider");
            if (SettingsProviderClazz == null) {
                CLog.e("ServiceBaseInfoProcessor mockAndroidId ContentProviderProxyClazz == null");
                return;
            }
            //public Bundle call(String method, String name, Bundle args) {
            hook_set.add(RposedHelpers.findAndHookMethod(SettingsProviderClazz,
                    "call", String.class, String.class, Bundle.class, new RC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                            super.beforeHookedMethod(param);
                            //GET_secure/android_id/Bundle[mParcelledData.dataSize=48]
                            var thisOjb = (ContentProvider) param.thisObject;
                            if (thisOjb == null) return;
                            //if(!FPServiceProcessManager.isMatchCallPackageInfo(thisOjb.getCallingPackage())) return;

                            String key = (String) param.args[1];
                            if (StringUtils.isEmpty(key)) {
                                return;
                            }
                            //args bundle
                            //Bundle bundle = (Bundle) param.args[2];
                            //result
                            Bundle result = (Bundle) param.getResult();
                            if (result != null) {
                                String orig_value = result.getString("value");
                                String mock_value = getMockValueDistribution(orig_value, key,thisOjb.getCallingPackage());

                                if (mock_value != null && !mock_value.equals(orig_value)) {
                                    Bundle temp_result = new Bundle();
                                    temp_result.putString("value", mock_value);
                                    param.setResult(temp_result);
                                    CLog.i("[" + key + "] system_service orig value [" + orig_value + "] mock value -> ["
                                            + mock_value + "] call package -> " + thisOjb.getCallingPackage());
                                }
//                                CLog.i("[" + key + "] system_service orig value [" + orig_value + "] mock value -> ["
//                                        + mock_value + "] call package -> " + thisOjb.getCallingPackage());
                            }
                        }
                    }));

        } catch (Throwable e) {
            CLog.e("ServiceBaseInfoProcessor mockAndroidId error " + e, e);
        }
```

因为系统服务是系统全局的，所以任何Apk读取到的都是你mock过的 ，如果想实现包名隐藏，或针对某个Apk读取，让他读取不到指定包的存在。

直接在系统服务里面去hook packageManager相关即可 。代码如下 。hook完毕以后任何Apk都读取不到你hook的包 ，可以在isHandler里面整体做分发处理 。

**获取当前调用的uid ，在获取包名 ，判断是谁获取的 获取的包名是什么 ，都一清二楚 。**

```
private void HookgetPackageInfo(IPackageManager server_package) {

//        Method[] declaredMethods = server_package.getClass().getDeclaredMethods();
//        for(var method: declaredMethods){
//            CLog.e("IPackageManager method info "+method);
//        }

        RC_MethodHook handler_list = new RC_MethodHook() {
            @Override
            protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                super.afterHookedMethod(param);
                try {
                    Object result = param.getResult();
                    if (result == null) return;
                    if (result instanceof List<?> list) {
                        list.removeIf(item -> isHandler(param,item));
                    } else if (result instanceof ParceledListSlice<?> list) {
                        list.getList().removeIf(item -> isHandler(param,item));
                    }
                } catch (Throwable e) {
                    CLog.e("ServicePackageProcessor handler_list error ",e);
                }
            }
        };

        RC_MethodHook handler_single = new RC_MethodHook() {
            @Override
            protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                super.afterHookedMethod(param);
                try {
                    Object result = param.getResult();
                    if (result == null) return;
                    if (isHandler(param,result)) {
                        param.setResult(null);
                    }
                } catch (Exception e) {
                    CLog.e("ServicePackageProcessor handler_single error ",e);
                }
            }
        };

        //java.util.List com.android.server.pm.PackageManagerService.getAllPackages()
        try {
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getAllPackages", handler_list));
        } catch (Exception ignored) {

        }
        try {
            //android.content.pm.ParceledListSlice com.android.server.pm.PackageManagerService.getInstalledPackages(int,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getInstalledPackages", handler_list));
        } catch (Exception ignored) {

        }
        try {
            //android.content.pm.ParceledListSlice
            //com.android.server.pm.PackageManagerService.getInstalledApplications(int,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getInstalledApplications", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //public final ParceledListSlice<PackageInfo> getPackagesHoldingPermissions()
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getPackagesHoldingPermissions", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //List<InstrumentationInfo> queryInstrumentationInternal(String targetPackage,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryInstrumentationInternal", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //public abstract List<ResolveInfo> queryIntentActivities(@NonNull Intent intent, int flags);
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryIntentActivities", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //public abstract List<ResolveInfo> queryIntentActivityOptions(@Nullable ComponentName caller,
            //              @Nullable Intent[] specifics, @NonNull Intent intent, int flags);
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryIntentActivityOptions", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //public List<ResolveInfo> queryIntentServices(Intent intent, ResolveInfoFlags flags)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryIntentServices", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //public List<ResolveInfo> queryIntentContentProviders(Intent intent, ResolveInfoFlags flags)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryIntentContentProviders", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            // ParceledListSlice<ResolveInfo> parceledList = mPM.queryIntentReceivers(
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "queryIntentReceivers", handler_list
            ));
        } catch (Exception ignored) {

        }
        try {
            //PackageInfo com.android.server.pm.PackageManagerService.getPackageInfo(java.lang.String,int,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getPackageInfo", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //int[] com.android.server.pm.PackageManagerService.getPackageGids(java.lang.String,int,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getPackageGids", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //ApplicationInfo com.android.server.pm.PackageManagerService.getApplicationInfo(java.lang.String,int,int)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getApplicationInfo", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //InstallSourceInfo
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getInstallSourceInfo", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public abstract @Nullable Intent getLaunchIntentForPackage(@NonNull String packageName);
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getLaunchIntentForPackage", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public abstract @Nullable Intent getLeanbackLaunchIntentForPackage(@NonNull String packageName);
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getLeanbackLaunchIntentForPackage", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public ActivityInfo getActivityInfo(ComponentName className, int flags)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getActivityInfo", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public ResolveInfo resolveActivity(Intent intent, ResolveInfoFlags flags)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "resolveActivity", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public ResolveInfo resolveActivityAsUser(Intent intent, ResolveInfoFlags flags, int userId)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "resolveActivityAsUser", handler_single));
        } catch (Exception ignored) {

        }
        try {
            //public int getPackageUid(String packageName, int flags)
            hook_set.addAll(RposedBridge.hookAllMethods(
                    server_package.getClass(), "getPackageUid", new RC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                            super.afterHookedMethod(param);
                            Object result = param.getResult();
                            if (result == null) return;
                            if (result instanceof Integer) {
                                if (param.args[0] instanceof String package_name) {
                                    if (isBlackApp(param,package_name)) {
                                        param.setResult(-1);
                                    }
                                }
                            }
                        }
                    }));
        } catch (Exception ignored) {

        }
    }
```

系统服务的hook比较简单 ，只需要基本的Xposed hook即可 。还有其他IMEI，，ICCID ,网卡，蓝牙都可以在系统服务进行处理 。

直接Hook对应的Api 即可， 这块可以直接吧system/framework里面frameword.jar 解压成class，导入AndroidStudio ，方便类的操作 。

不然每次hook还需要去findclass ，不方便 ，gradle编译设置成只编译即可 。

## 其他Apk相关Hook :

目前只发现oaid,vaid,aaid 这三个基础的是在小米安全中心产生的，他提供一个内容提供者，这块处理也很简单。

直接在Magisk模块发现加载是小米安全中心的时候，注入lsplant，请求服务端，拿到java代码句柄，实现和上面类似的逻辑 。

直接hook对应的代码即可 。可以根据你自己的逻辑去修改对应的hook逻辑 。

```
public static void mockOaid(IRuntimeService service, Context context) {
        if(isInited) return;
        //小米安全中心里面的类
        Class<?> IdProviderClazz = RposedHelpers.findClass(
                "com.miui.idprovider.IdProvider", context.getClassLoader());
        if (IdProviderClazz == null) {
            CLog.e("ServiceProcessOthersApks mockOaid  IdProvider clazz == null");
            return;
        }
        //CLog.e("ServiceProcessOthersApks mockOaid  get class success !");
        //public Cursor query(Uri uri, String[] strArr, String str, String[] strArr2, String str2) {
        RposedHelpers.findAndHookMethod(IdProviderClazz, "query",
                Uri.class,
                String[].class, String.class,
                String[].class, String.class, new RC_MethodHook() {
                    @Override
                    protected void afterHookedMethod(MethodHookParam param) throws Throwable {
                        super.afterHookedMethod(param);
                        Object arg = param.args[0];
                        if (arg == null) {
                            return;
                        }
                        Object result = param.getResult();
                        if (result == null) return;
                        Cursor ret = (Cursor) result;
                        if (param.thisObject instanceof ContentProvider object) {
                            Uri uri = (Uri) arg;
                            if (object.getCallingPackage() == null) {
                                return;
                            }
                            String callingPackage = object.getCallingPackage();
                            //CLog.i("ServiceProcessOthersApks callingPackage "+callingPackage);
                            //只处理目标Apk,减少请求服务端逻辑
                            if (callingPackage.equals(BuildConfig.tagPackageName)) {
                                if (uri.toString().equals(AUTHORITY + PATH_OAID)) {
                                    handlerId(param, service, ret, PATH_OAID);
                                } else if (uri.toString().equals(AUTHORITY + PATH_AAID)) {
                                    handlerId(param, service, ret, PATH_AAID);
                                } else if (uri.toString().equals(AUTHORITY + PATH_VAID)) {
                                    handlerId(param, service, ret, PATH_VAID);
                                } else {
                                    CLog.i("not match uri " + uri + " " + AUTHORITY + PATH_OAID);
                                }
                            }
                        }
                    }
                });
        isInited = true;
    }
```

## 内核ID相关Hook：

| 常用内核ID |  |  |
|-|-|-|
| /sys/block/mmcblk0/device/cid |  |  |
| /sys/block/mmcblk0/device/serial |  |  |
| /sys/devices/soc0/serial_number |  |  |
| /proc/sys/kernel/random/boot_id |  |  |
| netlink网卡 |  |  |
| 内核配置文件相关 |  |  |

这块其实一直我一个很蛋疼的点 ，因为在这个值的产生是在内核里面，不属于任何Apk 范畴，但是又可以当设备指纹 ，

比如最基本的一个boot id ，虽然这玩意重启以后会发生变化 。

他获取方式就可能三种多 ；

1、比如svc去open这个文件读取内容 。

2、popen cat这个文件内容，

3、在搞版本里面 也可以直接进入到当前进程的fd句柄下 ，直接ls - l 也能查到对应的boot_id

```
houji:/ # ls -l /proc/19178/fd
total 0
lrwx------ 1 root root 64 2024-05-24 22:46 0 -> /dev/null
lrwx------ 1 root root 64 2024-05-24 22:46 1 -> /dev/null

lrwx------ 1 root root 64 2024-05-24 22:46 79 -> /dev/ashmem5bc1633e-ea26-444e-b8a6-d7f607b9dd37

lr-x------ 1 root root 64 2024-05-24 22:46 8 -> /apex/com.android.art/javalib/core-oj.jar
lrwx------ 1 root root 64 2024-05-24 22:46 80 -> socket:[605258]
```

比如上面的第三行, /dev/ashmem  后面这一串就是对应的boot_id ，5bc1633e-ea26-444e-b8a6-d7f607b9dd37

因为我们当前手机可能有10个账号同时在，所以我们希望每个账号单独一份boot_id ，比如当A账号启动的时候切换到A账号的Boot_id 。

这样。

我之前的修改方案是直接编译小米内核，发现坑居多 ，小米内核很多驱动不开源，比如什么屏幕下指纹解锁等都是不开源的 。

**低版本android编译还好，还顺利，但是高版本编译的话各种坑 ，环境也是不全的 。最后发现单独编译内核在内核里面修改是【一条死路】 。**

这块划重点 ，当时研究编译高版本小米内核研究了一个多月，也没搞定 。

> 这块还有一个坑，就是你为什么不用自定义ROM去做？
>
> 因为国内环境对原生ROM检测能力较强，意义不大，改动成本也太大，不适合做插件化，随开随关。
>
>

正当我一筹莫展时候，发现Apatch 支持了Hook内核的能力 ，只要你的手机刷了Apatch ，即可使用KPM模块，去开发自己内核hook工具 。

Apatch 不仅仅可以运行Magisk模块，还可以支持内核模块Hook 。

举个例子 ：

如果想修改Boot_id，我们先看内核他是怎么获取的 。

他是通过sysctl函数在内核里面暴露给外读取的一个函数 对应的。源码位置如下 。初始化如下  Kernel\drivers\char\random.c

```
    {
        .procname = "boot_id",
        .data = &sysctl_bootid,
        .maxlen = 16,
        .mode = 0444,
        .proc_handler = proc_do_uuid,
    },
```

可以看到data 指向真是数据在 sysctl_bootid

其实就是一个16字节的数组 static char sysctl_bootid[16]; 在c文件的最上面 。

我们直接使用KPM模块直接hook即可 ,把原始的值地址保存起来，然后自定义一个syscall，往内核里面写入一个Mock 的boot_id即可 。

```
char *sysctl_bootid = 0;
void initHackBootId(){
    sysctl_bootid = (char *)kallsyms_lookup_name("sysctl_bootid");
    //save orig boot_id
    memset(ori_sysctl_bootid, 0, 0x10);
    memcpy(ori_sysctl_bootid, sysctl_bootid, 0x10);
    snprintf(ori_ashmem_path, ASHMEM_FULL_NAME_LEN, "%s%pU", ASHMEM_NAME_PREFIX, ori_sysctl_bootid);
    if(sysctl_bootid == NULL){
        pr_info("get sysctl_bootid sym sysctl_bootid == NULL \n");
    }
    pr_info("runtime_kpm: kernel sysctl_bootid addr:\n %llx %s",sysctl_bootid, sysctl_bootid);
}
```

直接调用这个自定义的Syscall直接往原始boot_id写入即可 。已经通过kallsyms_lookup_name 获取到了原始的字节数组指针 。

> 这个Boot_id修改以后还有个坑 ，修改以后任何APk 都打不开了 ，原因是因为服务端因为已经加载了 ，保存的是原始的boot_id 。
>
> 然后我们往服务端发送具体的改机指令，服务端开始通过Syscall往内核写入mock boot_id ，因为我们需要在客户端启动之前完成mock指纹的工作
>
> 客户端刚刚启动 ，这时候客户端读取服务端资源的时候，是通过共享内存的方式去写入的 ，客户端拿到的也是一个fd文件句柄 ，客户端尝试去打开这个文件句柄的时候，发现找不到这个boot_id导致任何Apk都打不开，这块解决办法也很简单 ，可以使用mknod进行backup即可解决。
>
>

其他的字段修改也很简单，在内核里面没那么多事，直接hook对应的函数，实现修改即可 。

搞一个mock value，搞一个自定义syscall 给mockvalue赋值 。如果mockvalue不等于null ，hook内核函数优先读取mockvalue即可 。

> 最早的时候我实现内核对抗的时候采用也是自定义内核和编译内核模块的方式，但是高版本刷入不进去，刷完手机就死机。
>
> 之前用的版本一直都是Android 10 ，就拿Boot_Id来说 ，这块其实他就是一个sysctl函数 ，这个函数是方便内核和应用层交互的 。
>
> 改内核也很简单 ，可以直接在内核里面添加一个sysctl函数，直接对应用层暴露一个命令，直接写入即可 。
>
>
>
> ```
> static int hack_bootid(struct ctl_table *table, int write,
>                   void __user *buffer, size_t *lenp, loff_t *ppos) {
> size_t len;
> long ret;
> if (!write) {
>    pr_err("hack_bootid: Attempt to read-only");
>    return -EFAULT;
> }
> if (write) {
>    len = min_t(size_t, *lenp, sizeof(sysctl_bootid));
>    pr_info("hack_bootid: Attempt to write. Requested len=%zu", len);
>    if (len) {
>        memset(sysctl_bootid, 0, sizeof(sysctl_bootid));
>        ret = copy_from_user(sysctl_bootid, buffer, len); // 直接从用户空间拷贝数据
>        if (ret) {
>            pr_err("hack_bootid: Failed to copy data from user space");
>            return -EFAULT;
>        }
>        pr_info("hack_bootid: Successfully updated sysctl_bootid ret = %d ",ret);
>    }
> }
> pr_info("hack_bootid: Current bootid -> [%.*s]", (int)sizeof(sysctl_bootid), sysctl_bootid);
> return 0;
> }
> ```
>
> 内核里面注册对应的sysctl表, 应用层可以直接
>
>
>
> ```
> {
>    .procname = "hack_boot_id",
>    .data = &sysctl_bootid,
>    .maxlen = 16,
>    .mode = 0666,
>    .proc_handler = hack_bootid,
> },
> ```
>
> 修改的话直接一条命令行 ，也可以实现。
>
>
>
> ```
> sysctl -w kernel.random.hack_boot_id="1234567890123456"
> ```
>
> 不过现在有了Apatch以后就抛弃了。
>
>

## Init进程设备指纹相关：

这个是最特殊的一个设备指纹，比如刚开头的时候说过 ，DRMID这种 产生就在Init 进程产生的。init作为一切进程的始祖，它里面包含的东西太多了 。

正是因为时间太早。所以想要hook这个进程成本很高 ，需要注入进去 ，我之前找空大师（zygisk_next作者 ，lsposed作者之一）聊过，想着在zygisk_next添加init进程的回调，但是也不知道现在开发进度如何了 。不知道等到猴年马月 ，但是这种init进程想要注入只有一个办法了 ，直接用ptrace打进去 ，但是这块还有个坑爹的地方 ，如果用ptrace注入进去以后，怎么把mock值传过去呢？ 传到目标进程里面 。

上面的指纹整体 都是通过系统服务去保存的，想着通过env去调用binder 拿到class 去和服务端通讯 ，但是init进程里面不允许这样 ，因为init进程里面 他创建时间太早了，连JavaVM都没有创建，所以没办法拿到env 。

而且init进程，它属于vendor分区的东西 ，不属于system分区 。

> 在Android8以上，安卓出了个分区隔离 ，system分区里面的不允许读取vendor里面的内容 ，vendor也不允许读取system里面 ，这样各种应用层在Hal层进行修改 。所以就没办法注入目标进程以后通过/system/lib64/libandroid_runtime.so调用_ZN7android14AndroidRuntime7mJavaVME虚拟机的创建 。
>
>

后来想了很久，直接通过ptrace 往目标进程写入一个字符串是最好的办法 。

我们还是讲drm的进程修改，这玩意其实核心产生位置是在/vendor/lib64/libwvhidl.so  下面这个符号里面去产生的。

```
_ZN5wvdrm8hardware3drm4V1_28widevine11WVDrmPlugin20CdmIdentifierBuilder17getDeviceUniqueIdEPNSt3__112basic_stringIcNS6_11char_traitsIcEENS6_9allocatorIcEEEE
```

目标有了，现在用ptrace去实现以下 。我们首先需要先修改system_server允许执行root权限 ，然后用ptrace去写个注入程序 。

```
const char* _libinject_log_tag = "Zhenxi";
int _libinject_log = 1;

void libinject_log(const char* log_tag) {
    _libinject_log_tag = log_tag;
    _libinject_log = log_tag == NULL ? 0 : 1;
}

pid_t _pid;
void *_dlopen;
void *_dlerror;
void *_calloc;
void *_free;

typedef void (*remote_stop_t)();
remote_stop_t remote_stop_ptr = NULL;

// ptrace wrapper with some error checking.
static long trace(const char* debug, int request, void *addr = NULL, size_t data = 0) {
    errno = 0;
    long ret = 0;
    for (int i = 0; i < 10; i++) {
        ret = ptrace(request, _pid, (caddr_t) addr, (void *) data);
        if (ret == -1 && (errno == EBUSY || errno == EFAULT || errno == ESRCH)) {
            char eb[16];
            char rb[16];

            const char* e = NULL;
            const char* r = NULL;

            switch (errno) {
            case ESRCH: e = "ESRCH"; break;
            default: snprintf(eb, sizeof(eb), "%d", errno); e = eb;
            }

            switch (request) {
            case PTRACE_PEEKTEXT: r = "PTRACE_PEEKTEXT"; break;
            case PTRACE_PEEKDATA: r = "PTRACE_PEEKDATA"; break;
            case PTRACE_POKETEXT: r = "PTRACE_POKETEXT"; break;
            case PTRACE_POKEDATA: r = "PTRACE_POKEDATA"; break;
            case PTRACE_CONT: r = "PTRACE_CONT"; break;
            case PTRACE_KILL: r = "PTRACE_KILL"; break;
            case PTRACE_SINGLESTEP: r = "PTRACE_SINGLESTEP"; break;
#if defined(PTRACE_GETREGS)
            case PTRACE_GETREGS: r = "PTRACE_GETREGS"; break;
#endif
#if defined(PTRACE_SETREGS)
            case PTRACE_SETREGS: r = "PTRACE_SETREGS"; break;
#endif
#if defined(PTRACE_GETFPREGS)
            case PTRACE_GETFPREGS: r = "PTRACE_GETFPREGS"; break;
#endif
#if defined(PTRACE_SETFPREGS)
            case PTRACE_SETFPREGS: r = "PTRACE_SETFPREGS"; break;
#endif
            case PTRACE_ATTACH: r = "PTRACE_ATTACH"; break;
            case PTRACE_DETACH: r = "PTRACE_DETACH"; break;
            case PTRACE_SYSCALL: r = "PTRACE_SYSCALL"; break;
            case PTRACE_SETOPTIONS: r = "PTRACE_SETOPTIONS"; break;
            case PTRACE_GETEVENTMSG: r = "PTRACE_GETEVENTMSG"; break;
            case PTRACE_GETSIGINFO: r = "PTRACE_GETSIGINFO"; break;
            case PTRACE_SETSIGINFO: r = "PTRACE_SETSIGINFO"; break;
#if defined(PTRACE_GETREGSET)
            case PTRACE_GETREGSET: r = "PTRACE_GETREGSET"; break;
#endif
#if defined(PTRACE_SETREGSET)
            case PTRACE_SETREGSET: r = "PTRACE_SETREGSET"; break;
#endif
            default: snprintf(rb, sizeof(rb), "%d", request); r = rb;
            }

            INJECTLOG("ptrace [%s] error [%s] on request [%s]", debug, e, r);
        }
        if (ret == -1 && (errno == ESRCH)) {
            INJECTLOG("ptrace remote_stop/retry");
            if (remote_stop_ptr != NULL) {
                remote_stop_ptr();
            }
        } else {
            break;
        }
    }
    return ret;
}

/*
 * This method will open /proc/<pid>/maps and search for the specified
 * library base address.
 */
static uintptr_t findLibrary(const char *library, pid_t pid) {
    char filename[0xFF] = { 0 }, buffer[1024] = { 0 };
    FILE *fp = NULL;
    uintptr_t address = 0;
    bool isFind = false;
    sprintf(filename, "/proc/%d/maps", pid == -1 ? _pid : pid);

    fp = fopen(filename, "rt");
    if (fp == NULL) {
        INJECTLOGE("findLibrary fopen error %s %s ",library,filename);
        goto done;
    }

    while (fgets(buffer, sizeof(buffer), fp)) {
        if (strstr(buffer, library)) {
            address = (uintptr_t) strtoul(buffer, NULL, 16);
            isFind = true;
            goto done;
        } else{
            //INJECTLOG("printf map item %s ",buffer);
        }
    }

    done:
//    if(!isFind){
//        INJECTLOG("findLibrary not find [%s] in %s ",library,filename);
//    }
    if (fp) {
        fclose(fp);
    }
//    if(address == 0){
//        INJECTLOG("findLibrary [%s] return 0 ,not find addr ",library);
//    }
    return address;
}

/*
 * Compute the delta of the local and the remote modules and apply it to the local address of the symbol ...
 * 计算本地和远程模块的增量，并将其应用于符号的本地地址。。。
 * BOOM, remote symbol address!
 * BOOM，远程符号地址！
 */
static void* remote_findFunction(const char* library, void* local_addr) {
    if(local_addr == nullptr){
        INJECTLOGE("remote_findFunction %s location base %p",library,(void*)local_addr);
        return nullptr;
    }
    uintptr_t remote_handle = findLibrary( library, -1 );
    if(remote_handle == 0){
        INJECTLOGE("remote_findFunction %s remote base == 0 ",library);
        return nullptr;
    }
    uintptr_t local_handle = findLibrary( library, getpid() );
    if(local_handle == 0){
        //INJECTLOG("remote_findFunction local_handle == 0 %s loc  %p  %d %s ",library,local_addr,getpid(),getprogname());
        Dl_info info;
        if(dladdr(local_addr,&info)){
            local_handle = (uintptr_t)info.dli_fbase;
        } else{
            INJECTLOGE("remote_findFunction local_handle backup == 0  ");
            return nullptr;
        }
    }
    uintptr_t offset = (uintptr_t) local_addr - local_handle;
    uintptr_t remote_addr = remote_handle + offset;
    return (void*)remote_addr;
}

static uint64_t ms() {
    struct timespec spec;
    clock_gettime(CLOCK_MONOTONIC, &spec);
    return (spec.tv_sec * 1000) + (spec.tv_nsec / 1.0e6);
}

/*
 * Make sure the remote process is stopped, or we get ESRCH errors
 */
static void remote_stop() {
//    INJECTLOG( "remote_stop" );
    kill( _pid, SIGSTOP );

    int status;
    int ret;
    uint64_t start = ms();
    while ( (ret = waitpid( _pid, &status, WUNTRACED || WNOHANG )) != -1 ) {
        if (ret == _pid) {
            if (WIFSIGNALED(status)) {
                trace ( "remote_stop", PTRACE_CONT, NULL, WTERMSIG(status));
            } else if (WIFSTOPPED(status)) {
                break;
            } else if (WIFEXITED(status)) {
                break;
            }
        } else if (ms() - start > 128) {
            // assume stopped before remote_stop() was called, 128ms is long
            break;
        }
        usleep(1);
    }
//    INJECTLOG( "/remote_stop" );
}

/*
* Read 'blen' bytes from the remote process at 'addr' address.
*/
static bool remote_read(const char* debug, size_t addr, unsigned char *buf, size_t blen){
    remote_stop();

    size_t i = 0;
    long ret = 0;

    for( i = 0; i < blen; i += sizeof(size_t) ){
       ret = trace( debug, PTRACE_PEEKTEXT, (void *)(addr + i) );
       if( ret == -1 ) {
           return false;
       }

       memcpy( &buf[i], &ret, sizeof(ret) );
    }

    return true;
}

/*
 * Write 'blen' bytes to the remote process at 'addr' address.
 */
static bool remote_write(const char* debug, size_t addr, unsigned char *buf, size_t blen) {
    remote_stop();

    size_t i = 0;
    long ret;

    // make sure the buffer is word aligned
    char *ptr = (char *) malloc(blen + blen % sizeof(size_t));
    memcpy(ptr, buf, blen);

    for (i = 0; i < blen; i += sizeof(size_t)) {
        ret = trace( debug, PTRACE_POKETEXT, (void *) (addr + i), *(size_t *) &ptr[i] );
        if (ret == -1) {
            free(ptr);
            return false;
        }
    }

    free(ptr);

    return true;
}

// Get remote registers
static void trace_getregs(const char* debug, struct pt_regs * regs) {
#if defined (__aarch64__) || defined(__x86_64__)
    uintptr_t regset = NT_PRSTATUS;
    struct iovec ioVec;

    ioVec.iov_base = regs;
    ioVec.iov_len = sizeof(*regs);
    trace( debug, PTRACE_GETREGSET, (void*)regset, (size_t)&ioVec );
#else
    trace( debug, PTRACE_GETREGS, 0, (size_t)regs );
#endif
}

// Set remote registers
static void trace_setregs(const char* debug, struct pt_regs * regs) {
#if defined (__aarch64__) || defined(__x86_64__)
    uintptr_t regset = NT_PRSTATUS;
    struct iovec ioVec;

    ioVec.iov_base = regs;
    ioVec.iov_len = sizeof(*regs);
    trace( debug, PTRACE_SETREGSET, (void*)regset, (size_t)&ioVec );
#else
    trace( debug, PTRACE_SETREGS, 0, (size_t)regs );
#endif
}

/*
 * Remotely call the remote function given its address, the number of
 * arguments and the arguments themselves.
 * 给定远程函数的地址、参数数量和参数本身，远程调用该函数。
 */
static uintptr_t remote_call(void *function, int nargs, ...) {
#if defined(__arm__) || defined(__aarch64__) || defined(__i386__) || defined(__x86_64__)
    //暂停目标进程
    remote_stop();

    struct pt_regs regs, rbackup;

    // get registers and backup them
    trace_getregs( "backup", &regs );
    // 备份原始寄存器
    memcpy( &rbackup, &regs, sizeof(struct pt_regs) );

    // start copying parameters
    va_list vl;
    va_start(vl,nargs);

    // push parameters into registers and stacks, setup registers to perform the call

#if defined(__arm__) || defined(__aarch64__)
    // fill R0-Rx with the first 4 (32-bit) or 8 (64-bit) parameters
    // 用前4个（32位）或8个（64位）参数填充R0 Rx
    // arm里面寄存器是R0开始
    for ( int i = 0; ( i < nargs ) && ( i < PARAMS_IN_REGS ); ++i ) {
        regs.uregs[i] = va_arg( vl, uintptr_t );
    }

    // push remaining parameters onto stack
    if (nargs > PARAMS_IN_REGS) {
        regs.ARM_sp -= sizeof(uintptr_t) * (nargs - PARAMS_IN_REGS);
        uintptr_t stack = regs.ARM_sp;
        for ( int i = PARAMS_IN_REGS; i < nargs; ++i ) {
            uintptr_t arg = va_arg( vl, uintptr_t );
            remote_write( "params", (size_t)stack, (uint8_t *)&arg, sizeof(uintptr_t) );
            stack += sizeof(uintptr_t);
        }
    }

    // return address to catch
    regs.ARM_lr = 0;

    // function address to call
    regs.ARM_pc = (uintptr_t)function;

    // setup the current processor status register
    // 设置当前处理器状态寄存器
    if ( regs.ARM_pc & 1 ) {
        // thumb
        regs.ARM_pc &= (~1u);
        regs.ARM_cpsr |= CPSR_T_MASK;
    } else {
        // arm
        regs.ARM_cpsr &= ~CPSR_T_MASK;
    }
#elif defined(__i386__)
    // push all params onto stack
    regs.esp -= sizeof(uintptr_t) * nargs;
    uintptr_t stack = regs.esp;
    for( int i = 0; i < nargs; ++i ) {
        uintptr_t arg = va_arg( vl, uintptr_t );
        remote_write( "params", (size_t)stack, (uint8_t *)&arg, sizeof(uintptr_t) );
        stack += sizeof(uintptr_t);
    }

    // return address to catch
    uintptr_t tmp_addr = 0;
    regs.esp -= sizeof(uintptr_t);
    remote_write( "return", (size_t)regs.esp, (uint8_t *)&tmp_addr, sizeof(uintptr_t) );

    // function address to call
    regs.eip = (uintptr_t)function;
#elif defined(__x86_64__)
    // align, rsp - 8 must be a multiple of 16 at function entry point
    {
        uintptr_t space = sizeof(uintptr_t);
        if (nargs > 6) space += sizeof(uintptr_t) * (nargs - 6);
        while (((regs.rsp - space - 8) & 0xF) != 0) regs.rsp--;
    }

    // fill [RDI, RSI, RDX, RCX, R8, R9] with the first 6 parameters
    for ( int i = 0; ( i < nargs ) && ( i < 6 ); ++i ) {
        uintptr_t arg = va_arg( vl, uintptr_t );
        switch (i) {
        case 0: regs.rdi = arg; break;
        case 1: regs.rsi = arg; break;
        case 2: regs.rdx = arg; break;
        case 3: regs.rcx = arg; break;
        case 4: regs.r8 = arg; break;
        case 5: regs.r9 = arg; break;
        }
    }

    // push remaining parameters onto stack
    if (nargs > 6) {
        regs.rsp -= sizeof(uintptr_t) * (nargs - 6);
        uintptr_t stack = regs.rsp;
        for( int i = 6; i < nargs; ++i ) {
            uintptr_t arg = va_arg( vl, uintptr_t );
            remote_write( "params", (size_t)stack, (uint8_t *)&arg, sizeof(uintptr_t) );
            stack += sizeof(uintptr_t);
        }
    }

    // return address to catch
    uintptr_t tmp_addr = 0;
    regs.rsp -= sizeof(uintptr_t);
    remote_write( "return", (size_t)regs.rsp, (uint8_t *)&tmp_addr, sizeof(uintptr_t) );

    // function address to call
    regs.rip = (uintptr_t)function;

    // may be needed
    regs.rax = 0;
    regs.orig_rax = 0;
#endif

    // end of parameters
    va_end(vl);

    // do the call
    trace_setregs( "call", &regs );
    trace( "call", PTRACE_CONT );

    // catch the SIGSEGV caused by the 0 return address
    // 捕获由0返回地址引起的SIGSEGV
    int status;
    while ( waitpid( _pid, &status, WUNTRACED ) == _pid ) {
        if ( WIFSTOPPED(status) && (WSTOPSIG(status) == SIGSEGV) ) {
            break;
        }
        trace( "waitpid", PTRACE_CONT );
    }

    // get registers again for return value
    // 再次获取返回值的寄存器
    trace_getregs( "return", &regs );

    // restore original registers state
    // 恢复原始寄存器状态
    trace_setregs( "restore", &rbackup );

    // continue execution
    // 继续执行
    trace( "continue", PTRACE_CONT );

#if defined(__arm__) || defined(__aarch64__)
    return regs.ARM_r0;
#elif defined(__i386__)
    return regs.eax;
#elif defined(__x86_64__)
    return regs.rax;
#endif
    return 0;
#else
#error ARCHITECTURE NOT SUPPORTED
#endif
}

// Allocate memory in remote process
static uintptr_t remote_calloc(size_t nmemb, size_t size) {
    return remote_call(_calloc, 2, nmemb, size);
}

// Free remotely allocated memory.
static void remote_free(uintptr_t p) {
    remote_call(_free, 1, p);
}

// Copy a given string into the remote process memory.
static uintptr_t remote_string(const char *s) {
    uintptr_t mem = remote_calloc(strlen(s) + 1, 1);

    remote_write( "string", mem, (unsigned char *) s, strlen(s) + 1);

    return mem;
}

// Remotely force the target process to dlopen a library.
static uintptr_t remote_dlopen(const char *libname) {
    uintptr_t pmem = remote_string(libname);
    uintptr_t plib = remote_call(_dlopen, 2, pmem, 2);
    remote_free(pmem);
    return plib;
}

// Get remote dlerror
static void remote_dlerror(char* error, int size) {
    uintptr_t e = remote_call(_dlerror, 0);
    remote_read("dlerror", e, (unsigned char*)error, size - 1);
}

// Find pid for process
pid_t find_pid_of(const char* process) {
    int id;
    pid_t pid = -1;
    DIR* dir;
    FILE *fp;
    char filename[32];
    char cmdline[256];

    struct dirent * entry;

    if (process == NULL)
        return -1;

    dir = opendir("/proc");
    if (dir == NULL)
        return -1;

    while ((entry = readdir(dir)) != NULL) {
        id = atoi(entry->d_name);
        if (id != 0) {
            sprintf(filename, "/proc/%d/cmdline", id);
            fp = fopen(filename, "r");
            if (fp) {
                fgets(cmdline, sizeof(cmdline), fp);
                fclose(fp);

                if (strcmp(process, cmdline) == 0) {
                    /* process found */
                    //if(id > pid){
                    ////相同进程名时, 使用进程ID最大的进程(最近启动的进程), 避免在VMOS里查找到主机的进程
                    //  pid = id;
                    //}
                    pid = id;
                    break;
                }
            }
        }
    }

    closedir(dir);
    return pid;
}

//作用为解除zygote进程的阻塞状态
void * connect_to_zygote(void *arg) {
    int s, len;
    struct sockaddr_un remote;

    INJECTLOG("[+] wait 2s...");
    sleep(2);

    /***
    * zygote进程启动后会进入一个死循环, 用来接收AMS的请求连接,
    * 当没有应用启动时, zygote进程一直处于阻塞状态。
    * 为防止wait无法返回，因此主动发起一个zygote的连接，解除zygote阻塞状态。
    */
    if ((s = socket(AF_UNIX, SOCK_STREAM, 0)) != -1) {
        remote.sun_family = AF_UNIX;
#if defined(__arm__)
        strcpy(remote.sun_path, "/dev/socket/zygote");
#elif defined(__aarch64__)
        strcpy(remote.sun_path, "/dev/socket/zygote64");
#endif
        len = strlen(remote.sun_path) + sizeof(remote.sun_family);
        INJECTLOG("[+] start to connect zygote socket");
        connect(s, (struct sockaddr *) &remote, len);
        INJECTLOG("[+] close socket");
        close(s);
    }

    return NULL;
}

// Load library in process pid, resolves JavaVM and passes it and param to loaded library, returns 0 on success
// 在进程pid中加载库，解析JavaVM并将其和param传递给加载的库，成功时返回0
int injectvm(pid_t pid, char* library, const char* type,const char* param) {
    remote_stop_ptr = remote_stop;

    int ret = 1;
    _pid = pid;

    // attach to target process
    if ( trace( "attach", PTRACE_ATTACH ) != -1) {
        // stop entire process, including non-main threads
        kill( _pid, SIGSTOP);

        // wait until we're stopped
        remote_stop();

        /* First thing first, we need to search these functions into the target
         * process address space.
         */

        /* We can resolve the references to LIBC easily, but dl* is tricky. On older Android
         * versions, libdl.so is commonly not loaded by the linker, and our dl* functions
         * come directly from the linker.
         *
         * On newer Android versions, libdl.so is directly loaded and dl* come from there.
         *
         * On even newer Android versions, the linker/libc/libdl have moved from /system to /bionic
         */
        //判断VMOS环境 isVMOS!=0 表示为VMOS环境
        int isVMOS = findLibrary(PATH_LIBC_VMOS, _pid);
        int isVMOSPRO = findLibrary(PATH_LIBC_VMOS_PRO, _pid);
        int isVMOSPRO2 = findLibrary(PATH_LIBC_VMOS_PRO_2, _pid);
        int isTWOYI = findLibrary(PATH_LIBC_TWOYI, _pid);
        int isVPHONE = findLibrary(PATH_LIBC_VPHONE, _pid);

        const char* libc = isVMOS!=0 ? PATH_LIBC_VMOS : (isVMOSPRO!=0 ? PATH_LIBC_VMOS_PRO :(isVMOSPRO2!=0 ? PATH_LIBC_VMOS_PRO_2 : ( isTWOYI!=0 ? PATH_LIBC_TWOYI : ( isVPHONE!=0 ? PATH_LIBC_VPHONE : (access( PATH_LIBC_BIONIC, R_OK ) == 0 ? PATH_LIBC_BIONIC : PATH_LIBC)))));
        const char* libdl = isVMOS!=0 ? PATH_LIBDL_VMOS : (isVMOSPRO!=0 ? PATH_LIBDL_VMOS_PRO :(isVMOSPRO2!=0 ? PATH_LIBDL_VMOS_PRO_2 : ( isTWOYI!=0 ? PATH_LIBDL_TWOYI :( isVPHONE!=0 ? PATH_LIBDL_VPHONE :(access( PATH_LIBDL_BIONIC, R_OK ) == 0 ? PATH_LIBDL_BIONIC : PATH_LIBDL)))));
        const char* linker = isVMOS!=0 ? PATH_LINKER_VMOS :(isVMOSPRO!=0 ? PATH_LINKER_VMOS_PRO :(isVMOSPRO2!=0 ? PATH_LINKER_VMOS_PRO_2 : ( isTWOYI!=0 ? PATH_LINKER_TWOYI :( isVPHONE!=0 ? PATH_LINKER_VPHONE :(access( PATH_LINKER_BIONIC, R_OK ) == 0 ? PATH_LINKER_BIONIC : PATH_LINKER)))));
        //INJECTLOG( "libc:%s", libc );
        //INJECTLOG( "libdl:%s", libdl );
        //INJECTLOG( "linker:%s", linker );
        //获取远端dlopen的地址
        _calloc = remote_findFunction( libc, (void *) calloc );
        _free = remote_findFunction( libc, (void *) free );
        if ((findLibrary( libdl, -1 ) != 0) && (findLibrary( libdl, _pid ) != 0)) {
           //ret = 100+isVPHONE;
            void* handle = dlopen( libdl, RTLD_LAZY );
            _dlopen = remote_findFunction( libdl, dlsym( handle, "dlopen" ) );
            _dlerror = remote_findFunction( libdl, dlsym( handle, "dlerror" ) );
            dlclose( handle );
        } else {
            //ret = 200+isVPHONE;
            _dlopen = remote_findFunction( linker, (void *) dlopen );
            _dlerror = remote_findFunction( linker, (void *) dlerror );
        }

        // Resolve android::AndroidRuntime::mJavaVM,
        // this is tricky from the payload because
        // of linker namespaces (you can't load the lib, dlsym doesn't work right, and the location
        // of the variable in memory is different between Android versions), but no such issue
        // exists from this injector.

        //获取java vm,如果是vendor下面的拿runtime可能失败
        //因为runtime是在system分区下面
        void* runtime = dlopen( PATH_LIBANDROID_RUNTIME, RTLD_NOW  );
        void* javavm = dlsym( runtime, "_ZN7android14AndroidRuntime7mJavaVME" );
        void* _javavm = remote_findFunction( PATH_LIBANDROID_RUNTIME, javavm );
        dlclose(runtime);

        INJECTLOG( "calloc:%p free:%p dlopen:%p dlerror:%p javavm:%p", _calloc, _free, _dlopen, _dlerror, _javavm );
        INJECTLOG( "inject elf path %s ", library );

        // once we have the addresses, we can proceed to inject
        if ( remote_dlopen(library) != 0 ) {
            INJECTLOG( "remote dlopen [%s] success ! ",library);
            void* payload = dlopen( library, RTLD_LAZY );
            if(payload == nullptr){
                INJECTLOG( "remote dlopen error %s ", library);
            }
            void* LocDoRunSym = dlsym(payload, "doRun" );
            if(LocDoRunSym == nullptr){
                INJECTLOG( "not find doRun sym " );
            }
            Dl_info info;
            dladdr(LocDoRunSym,&info);
            INJECTLOG("loc doRun info [%s] fbase -> %p  offset %p ",
                      info.dli_fname,info.dli_fbase,(void*)((size_t)LocDoRunSym-(size_t)info.dli_fbase)
            );
            void* remoteDoRunSym = remote_findFunction(library, LocDoRunSym);
            if (LocDoRunSym != NULL && remoteDoRunSym != NULL) {
                //INJECTLOG("start call doRun -> %p -> [%s]", remoteDoRunSym, param);
                uintptr_t pdata = remote_string(param);
                uintptr_t ptype = remote_string(type);
                //remote_call(remoteDoRunSym, 2, _javavm, pmem);
                //return 0 is success ~!
                auto call_dorun_ret = remote_call(remoteDoRunSym, 2,ptype, pdata);
                //auto call_dorun_ret = remote_call(remoteDoRunSym, 0);
                remote_free(pdata);
                remote_free(ptype);
                //INJECTLOG("doRun call finish %lu %p",call_dorun_ret,(void*)call_dorun_ret);
                ret = call_dorun_ret;
            }
        } else {
            char error[1024] = { 0 };
            remote_dlerror(error, 1024);
            INJECTLOG( "remote_dlopen failed: %s", error );
        }

        // detach from target process
        remote_stop();
        trace( "detach", PTRACE_DETACH );
        // let all threads in the target process continue
        kill( _pid, SIGCONT );
        INJECTLOG( "<<<<<<<< ptrace finish >>>>>>>> ");
    } else {
        INJECTLOG( "Failed to attach to process %d", _pid);
    }

    return ret;
}
```

这段代码编译成一个注入器 ，输入路径就是对应的pid和你要注入的so文件 。

**整体思路就是ptrace attach到目标进程 。然后让目标进程调用dlopen去打开指定的so文件 ，实现我们自己的逻辑的初始化。**

>
>
> ---
>
> ***下面说的远端函数指的是被注入的进程的函数地址。***
>
>

### 1、所以我们需要得到目标进程dlopen，malloc （用于分配字符串）的地址 。

先算出来dlopen相对libc的偏移 ，我们先在可执行程序里面打开libc，计算出来dlopen的偏移 。

然后注入进程以后，在目标进程打开libc ，在目标进程地址libc+ 获取到的偏移 ，就是目标进程的dlopen地址 。

同样的方式去获取dlopen ，dlerror ，malloc ，free 等地址 。

```
/*
 * Compute the delta of the local and the remote modules and apply it to the local address of the symbol ...
 * 计算本地和远程模块的增量，并将其应用于符号的本地地址。。。
 * BOOM, remote symbol address!
 * BOOM，远程符号地址！
 */
static void* remote_findFunction(const char* library, void* local_addr) {
    if(local_addr == nullptr){
        INJECTLOGE("remote_findFunction %s location base %p",library,(void*)local_addr);
        return nullptr;
    }
    uintptr_t remote_handle = findLibrary( library, -1 );
    if(remote_handle == 0){
        INJECTLOGE("remote_findFunction %s remote base == 0 ",library);
        return nullptr;
    }
    uintptr_t local_handle = findLibrary( library, getpid() );
    if(local_handle == 0){
        //INJECTLOG("remote_findFunction local_handle == 0 %s loc  %p  %d %s ",library,local_addr,getpid(),getprogname());
        Dl_info info;
        if(dladdr(local_addr,&info)){
            local_handle = (uintptr_t)info.dli_fbase;
        } else{
            INJECTLOGE("remote_findFunction local_handle backup == 0  ");
            return nullptr;
        }
    }
    uintptr_t offset = (uintptr_t) local_addr - local_handle;
    uintptr_t remote_addr = remote_handle + offset;
    return (void*)remote_addr;
}
```

上面这段代码就是做我说的这件事 ，参数1先传入对应的so路径 ，参数2需要获取的函数比如dlopen地址（这个地址是我们本地进程的dlopen地址）  。

返回值是远端的dlopen地址 。实现方式主要如下 ：

我们可以先通过findLibrary 遍历自己的进程的比如libc.so文件开始地址 ，比如是0xABC 。

在获取目标进程libc的开始地址 。可以通过dladdr 函数里面的dli_fbase得到开始地址 比如是0x456

这时候我们用本地进程的dlopen绝对地址， 减去我们自己的libc.so 开始地址0xABC ，得到dlopen的相对偏移 。

再用这个dlopen的相对偏移去加上0x456 ，就是目标进程的dlopen的绝对地址。

### 2、远端进程打开我们自己的SO文件

直接在远端进程调用dlopen函数指针 ，打开我们要注入的so文件 ，拿到so文件的句柄以后，在通过dlsym拿到我们导出的函数  。

然后再调用远端进程 malloc 去分配一个字符串 ，分配完毕以后用作参数传到我们导出的函数 。实现初始化 。

详细代码可以参考 injectvm 函数 ，里面有详细的注入流程  。

### 3、Hack DRM

这时候已经注入到目标进程，可以直接用inlinehook去hook 即可 。因为注入的分区主要在vendor下面 ，所以不能直接用system/lib下的so文件 。

```
extern "C" {
__attribute__ ((visibility ("default")))
int
doRun(char *type, char *data) {
    LOG(ERROR) << "start doRun  !!! data ->" << data;
    if (strcpy(type, "hack_drm")) {
#define SYM_THE_PATH "/vendor/lib64/libwvhidl.so"
        LOG(ERROR) << "rep mock drm  [" << fake_wvdrm_hash << "] orig [" << data << "]";
        fake_wvdrm_hash = data;
        if (!DrmIsHooked) {
            //1.2&1.3&1.4
            auto sym = getSymCompat(SYM_THE_PATH,
                                    "_ZN5wvdrm8hardware3drm4V1_28widevine11WVDrmPlugin20CdmIdentifierBuilder17getDeviceUniqueIdEPNSt3__112basic_stringIcNS6_11char_traitsIcEENS6_9allocatorIcEEEE");
            if (sym == nullptr) {
                sym = getSymCompat(SYM_THE_PATH,
                                   "_ZN5wvdrm8hardware3drm4V1_38widevine11WVDrmPlugin20CdmIdentifierBuilder17getDeviceUniqueIdEPNSt3__112basic_stringIcNS6_11char_traitsIcEENS6_9allocatorIcEEEE");
            }
            if (sym == nullptr) {
                sym = getSymCompat(SYM_THE_PATH,
                                   "_ZN5wvdrm8hardware3drm4V1_48widevine11WVDrmPlugin20CdmIdentifierBuilder17getDeviceUniqueIdEPNSt3__112basic_stringIcNS6_11char_traitsIcEENS6_9allocatorIcEEEE");
            }
            if (sym == nullptr) {
                LOG(ERROR) << "!!!!!!!!!! mock drm error ,not find sym  !!!!!!!! ";
                return 1;
            }
            auto ret = HookUtils::Hooker(sym, (void *) new_getDeviceUniqueId,
                                         (void **) &orig_getDeviceUniqueId);

            if (ret) {
                DrmIsHooked = true;
                LOG(ERROR) << "hack drm is success ! " << ret;
            } else {
                LOG(ERROR) << "hack drm is error ! ";
            }
        } else {
            LOG(INFO) << "realy is hack drm " << fake_wvdrm_hash;
        }
    }
    return 0;
}
}
```

## Getprop指纹修改：

再讲这块之前，我们需要先科普一下一个基础知识，就是selinux关闭了会发生什么 ，这块还有一个很有意思的趣闻 。客户端如何反向投毒&蜜罐服务端 ？

```
zeus:/ $ id
uid=2000(shell) gid=2000(shell) groups=2000(shell),1004(input),1007(log),1011(adb),1015(sdcard_rw),1028(sdcard_r),1078(ext_data_rw),1079(ext_obb_rw),3001(net_bt_admin),3002(net_bt),3003(inet),3006(net_bw_stats),3009(readproc),3011(uhid),3012(readtracefs) context=u:r:shell:s0
zeus:/ $ getprop | grep oem
[ro.fota.oem]: [Xiaomi]
[ro.ril.oem.imei]: [864489057004666]
[ro.ril.oem.imei1]: [864489057004666]
[ro.ril.oem.imei2]: [864489057004666]
[ro.ril.oem.meid]: [99001831350666]
[ro.ril.oem.psno]: [37331/21ZW02666]
[ro.ril.oem.sno]: [789752F14564695]
[sys.oem_unlock_allowed]: [0]
```

getprop 里面保存了一些变量，这些变量的Selinux权限很高 ，需要系统级别的group或者root级别的selinux全选组才可以拿到 。

但是如果你手机关闭了Selinux ,这些变量都可以随便拿 。这里面不仅仅有oem分区的值，还有一些历史开机时间 。这些都是比较隐蔽的设备指纹。

```
[persist.sys.boot.reason.history]: [reboot,userrequested,1716561955]
```

他可以直接通过getprop直接就把你手机全部信息都读走 ，我们其实是不希望这样的，**所以selinux无论如何也要开启 ，否则你得手机就是在裸奔。**

对与修改这些环境变量方法更多了，直接用magisk自带的magisk resetprop 命令直接修改即可。比如下面的修改debug环境，一行命令行就是全局修改了。

```
magisk resetprop ro.debuggable 1
```

用起来也很方便  。

这块就说上面的那个趣闻了 ，很多大厂他在采集数据的时候，**根本没办法保证自己采集的数据是准确的**，特别是这种oem分区的，在他觉得我能采到这个值就可以上报到服务端 。那好我们来个反向投毒 。

> 我们直接把一台正常的手机，伪装成关闭selinux权限的 ，然后去故意暴露一个我修改过的ro.ril.oem.imei等，让目标App去读取 。
>
> 用这种方式差不点没给我笑死，竟然真的把一台已经封掉的手机给复活了。基本可以断定，很多大厂客户端采集的数据也没有确认 ，特别是 这种隐藏数据 。
>
> 他也是尝试去拿，而我们也尝试去给你伪造的 。这种imei这种数据在大厂的风控设备指纹里面比重很大，完全不经过确认是真是假，就被列入了指纹。
>
>

其实在大厂里面很多策略根本不懂技术 ，他们遇到了问题，只会想着问安全SDK的客户端，去帮忙查case，当查不到有任何问题的时候

头疼的就是他们了。

# 设备指纹采集反思&总结：

前段时间在写hunter代码的时候 ，我忽然想到一个问题 。

**我们在做安全SDK客户端的数据采集的时候，应该如何确保我们拿到的字段是真实和安全的？**

## 1、我们可以自己去NDK里面把libc.so的动态库编译到我们自己的so里面 。而不走系统的libc 。

为什么不推荐使用系统的libc呢 ？其实这块有一个so文件字符串通杀的办法 。就是直接hook strlen这个函数 。

如果发现上级调用栈使我们自己的就直接返回 ，如果是目标So文件的我们就可以在这里进行替换和拦截。基本可以通杀市面上任何大厂 。

之前和牛头人做对抗的时候发现牛头人就是没有走标准的libc.so文件 ，一个libc.so函数没有被调用 。

## 2、我们应该尽可能的不要使用c++ 里面的string

网上有很多字符串的开源库，如果使用了c++ 里面的string 就很难逃逸strlen的hook，因为string的构造里面无论如何也需要使用strlen 。

如果对方直接hook了你string的append函数 ，你也是没办法逃逸的。

## 3、单字段多形式获取

比如上面说的boot_id这种，我们应该尝试使用多种方式去获取，比如abc三种方式获取的值都是一样的，客户端在进行上报 。

## 4、基础环境检测

设备指纹分为两部分，采集设备指纹相关字段，风险检测相关字段 。个人觉得 1/9比例是最好的 ，踩一个字段的前提下，应该把可能被修改的点

都想到，而不是只采集有效的字段 ，更多应该关注环境信息 ，比如在一些重点场景下可以采集一些用户的logcat日志上报。

方便做攻击分析，很多黑产或者搞攻击的会忽略这块，其实检测就是细节上的对抗 ，logcat日志直接给你上报过去，发现指定日志直接封你号就行了。

> 但是这块也有弊端，logcat这种属于大数据 ，通过什么地方上报是个问题，如果是同步上报过去，肯定会很耗时 ，所以这块
>
> 可能还需要去设计，在制定场景下去通过socket这种发包的方式取上报拦截。
>
>

# 一机多号实现：

上面说了这么多，还有一个地方没有说 ，就是如何实现IO重定向呢？我们知道一个App可以写入的位置只有两个地方 。

一个是/sdcard 和 /data/data/包名 。我们只需要把这些进行保存的位置进行IO重定向。

> SD卡里面还有/sdcard/Android/data/包名这些都是隶属于/sdcard下面的，但是他们两个的挂载位置是完全不一样的，所属的selinux权限也不一样 。
>
> /sdcard 这种属于 Fuse（文件系统用户空间），但是/sdcard/Android/data/是属于F2FS（闪存友好文件系统）的 。
>
>

这块有两种比较好的实现方式

- 内核模块去实现系统级别IO重定向。
- 直接使用Mount命令

现在你已经有Root环境 ，如果在开发syscall hook实现成本也挺大的 ，可以推荐用方案1 ，通过Apatch模块在内核里面直接进行全局的IO重定向即可 。

但是需要测试 。我这边使用的是Mount命令，更轻量化 。

他这个命令的主要是

```
 mount --bind 源文件目录 目标文件目录
```

比如我希望对/data/data/包名、这个目录 进行IO重定向 mount --bind  【/abc/AAA用户/data目录】 ，【 /data/data/包名】

这样执行的话当目标App往  /data/data/包名目录写入东西的时候，也会同步到/abc/AAA用户/data目录 这个目录 。

当我们umount取消挂载的时候 /abc/AAA用户/data目录文件内容还是会存在 。即可实现全局的IO重定向。具体实现如下 。包名以脱敏。记得修改文件权限，小心selinux规则限制哦 ，**不过限制了也无所谓，Magisk模块支持修改自定义selinux规则。**

![image](https://bbs.kanxue.com/upload/attach/202405/819934_RE32GQR6X2GU87W.webp)

每个用户下面保存着

- 当前用户的设备指纹相关数据
- SD卡相关数据 （重定向目录）
- /data/data/包名相关数据（重定向目录）

三个目录即可 ，如果切换到指定用户，只需要把当前用户的设备指纹相关数据进行读取，把mock的保存到内存里即可。在设置mock的设备指纹读取这个内存中的值即可 。

# 对抗总结：

通过上面连续操作我们即可实现在客户端不注入一行代码的情况下，实现设备指纹的全量修改。虽然我们对目标进程进行对抗 ，但是我们一行代码也没有修改 。

我们改的也都是系统本身的值 。但是客户端获取的都是被修改过的 。

### 问题1：

因为你使用了mount命令 ，我可以直接检测你挂载文件 ，如果有人遍历了你mount挂载文件检测你怎么办呢？

> 这块其实很简单，直接不让他读或者在内核写个模块把这个文件特征抹掉就好了，内核你都能随便修改了，整个手机规则的缔造者。
>
> 啥文件还不能修改呢。
>
>

### 问题2：

magisk模块本身也不是会注入到目标进程么？难道就一点痕迹没有么？

> 这个问题其实很简单，注入归注入，修改归修改，注入了什么也没修改 内存是无痕迹的 。
>
> 我们只需要在magisk模块加载完毕以后调用
>
> api_->setOption(zygisk::Option::DLCLOSE_MODULE_LIBRARY);
>
> 把magisk模块so移除掉即可 。可能移除掉以后目标的Application还没开始执行调用就已经关闭了。
>
>
> > **我们在目标进程没有修改任何代码，所以不存在函数跳转地址 ，我也没有inlinehook当前进程的任何so文件 。**
> >
> > **内存里面也就不会再内存里面存在任何执行的段 ，并且任何SO文件的CRC也不发生变化。**
> >
> >
>
>

### 问题3：

你手机既然root了，我检测你解锁或者root不行么？

> 其实这块有一个很恶心的事情，就是shamiko+magisk修改包名 ，可以过掉国内99.999%的App root检测 。
>
> shamiko会用chroot给你一个新的环境 ，是任何root痕迹都没有的 ，root检测其实很难的 ，解锁的手机也没办法直接封号 。
>
> （之前老版本的shamiko可能有一些漏洞可以钻，但是新版本里面我找了很久也没找到好的洞 。）
>
> 因为现在市面上解锁的手机占比还是很大的 。解锁了也不一定代表作弊了。
>
>

### 问题4：

你客户端不注入一行代码，如何拿到Apk里面的数据呢？

> 办法有很多 ，可以直接用自动点击的软件配合OCR文字识别即可 。看什么样的数据，如果是大文本数据可以直接通过抓包或者路由代理等直接解密即可 。
>
> 最次办法直接客户端注入lsplant直接hook对应函数，拿到数据  。
>
> 这块lsplant hook crc也不一定发生变化的，因为我之前把他inlinehook那块注释掉，发现hook还是生效的，他那个inlinehook主要是为了解决
>
> 一些被oat了短指令的函数 。
>
> 这块还有一个新的技术点可以用内核里面的硬件断点去实现inlinehook 。也是无痕的hook方式一种，不过好像hook的方法数量有限。
>
> 这里感谢B哥提供的硬段思路，B哥太强了！
>
>

### 问题5：

你那么多台手机都聚集在一起不怕被封么？

> 可以把手机放在全国各地，连接上USB能实现自动点击即可  , 流量使用物联卡的流量即可。
>
> 解决聚集性策略。这块需要逐步发展，手机数量是在之前满足的情况下，在进行扩增。
>
>

# 结尾：

感谢读到这里 ，各位读到这里也是有e点收获的 。最起码方向有了 ，如果本文里面，有哪些错误地方或者不认同有更好的方案也可以随时在下面回复即可。

有时间的情况下，我每一条都会看的。

再次感谢lsplant的开源项目和Apatch的项目开源 。

<https://github.com/LSPosed/LSPlant>

<https://github.com/bmax121/APatch>

                                                                                                                                                                                                                ---- 2024/5/25日阴。

---

# 回复

## 回复 by KerryS (#2)

*2024-5-25 17:07*

我怎么感觉直接去逆向分析风控sdk，看它上传了什么信息，更加简洁一点

## 回复 by hacker521 (#3)

*2024-5-25 18:55*

珍惜大佬出品，必属精品![image](https://bbs.kanxue.com/view/img/face/3.gif)

## 回复 by mb_fssslkzs (#4)

*2024-5-26 22:57*

tql，好喜欢这种硬核的知识帖子了，不仅学了知识，又了解安卓的前世今生

## 回复 by tmi (#5)

*2024-5-27 09:53*

厉害

## 回复 by 王小翊i (#6)

*2024-5-27 09:54*

珍惜出品，必属精品

## 回复 by 0xEA (#7)

*2024-5-27 09:54*

tql

## 回复 by hzzheyang (#8)

*2024-5-27 09:56*

珍惜大佬太强了

## 回复 by mb_zfqvurgb (#9)

*2024-5-27 09:56*

牛逼

## 回复 by alienhe (#10)

*2024-5-27 10:14*

太顶了

## 回复 by 小黄鸭爱学习 (#11)

*2024-5-27 10:39*

1

## 回复 by 小黄鸭爱学习 (#12)

*2024-5-27 10:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  我怎么感觉直接去逆向分析风控sdk，看它上传了什么信息，更加简洁一点
>
>

理论上是 但是不通用 假设sdk不断更新或者你要面对数个app采集的时候。
时间就是金钱，这属于用设备成本换开发时间了。
假设团队只用3个人去对抗300个人的安全团队做采集，我举得时间还是挺宝贵的。

## 回复 by 珍惜Any (#13)

*2024-5-27 15:30*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  理论上是 但是不通用 假设sdk不断更新或者你要面对数个app采集的时候。
> 时间就是金钱，这属于用设备成本换开发时间了。
> 假设团队只用3个人去对抗300个人的安全团队做采集，我举得时间还是挺宝贵的 ...
>
>

有明白人，通用最好。

## 回复 by 小黄鸭爱学习 (#14)

*2024-5-27 16:48*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  有明白人，通用最好。
>
>

问题5：
你那么多台手机都聚集在一起不怕被封么？

这里能做的事情还是很多的，包括模拟日常使用。手机的高度陀螺仪检测，日常的使用电量模拟都能作为风控的指标。

自动化的触摸行为方式也要谨慎处理。

我的建议是做成一个手机仿真日常大模型去对抗大厂的风控大模型。
用大数据对抗大数据，用大模型对抗大模型，用AI对抗AI。

## 回复 by 珍惜Any (#15)

*2024-5-27 17:10*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  问题5：
> 你那么多台手机都聚集在一起不怕被封么？
>
> 这里能做的事情还是很多的，包括模拟日常使用。手机的高度陀螺仪检测，日常的使用电量模拟都能作为风控的指标。
>
> 自动化的触摸行为方式也要谨慎处 ...
>
>

嗯嗯 感谢提醒 ，陀螺仪一般没权限去读的 。电量hook了都是随机的。还有一些基础的也都模拟了。

## 回复 by KerryS (#16)

*2024-5-27 17:59*

>
> [小黄鸭爱学习](https://bbs.kanxue.com/user-832784.htm)
>
>  理论上是 但是不通用 假设sdk不断更新或者你要面对数个app采集的时候。
> 时间就是金钱，这属于用设备成本换开发时间了。
> 假设团队只用3个人去对抗300个人的安全团队做采集，我举得时间还是挺宝贵的 ...
>
>

悟了，难怪标题说是四两拨千斤

## 回复 by Gordonhat (#17)

*2024-5-29 10:06*

请教下，magisk+lsposed 去hook server进程有什么风险吗，还是说为了适配高版本的android，才自己实现一个lsposed

## 回复 by 珍惜Any (#18)

*2024-5-29 10:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Gordonhat](https://bbs.kanxue.com/user-690300.htm)
>
>  请教下，magisk+lsposed 去hook server进程有什么风险吗，还是说为了适配高版本的android，才自己实现一个lsposed
>
>

没任何风险，hook server 不会涉及目标Apk进程hook所以没任何风险 。为啥自己实现一个Lsposed，是为了定制化，根据自己逻辑去完善。

## 回复 by hacker521 (#19)

*2024-5-29 15:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Gordonhat](https://bbs.kanxue.com/user-690300.htm)
>
>  请教下，magisk+lsposed 去hook server进程有什么风险吗，还是说为了适配高版本的android，才自己实现一个lsposed
>
>

lsposed 国外大神接手的开源版本已经兼容到Android 15了

## 回复 by 珍惜Any (#20)

*2024-5-29 16:34*

>
> [hacker521](https://bbs.kanxue.com/user-983172.htm)
>
>  lsposed 国外大神接手的开源版本已经兼容到Android 15了
>
>

可以尝试自己搞搞，没几行代码，lsplant支持15的。

## 回复 by 初恒 (#21)

*2024-5-31 18:50*

珍惜大佬, app厂商上 tee怎么破。![image](https://bbs.kanxue.com/view/img/face/40.gif)

## 回复 by 珍惜Any (#22)

*2024-5-31 21:57*

>
> [初恒](https://bbs.kanxue.com/user-788622.htm)
>
>  珍惜大佬, app厂商上 tee怎么破。[em_40]
>
>

很好的问题，目前就tee解锁验证,github有一个项目，是hook密钥的方式去绕过的，还有一种办法是直接在内核tee这块进行处理 。

## 回复 by 霸业 (#23)

*2024-6-1 13:55*

难搞:)

## 回复 by 珍惜Any (#24)

*2024-6-1 16:28*

>
> [霸业](https://bbs.kanxue.com/user-796003.htm)
>
>  佬，drm指纹，tee应该是keystone，这些 binder通信服务， 您是怎么知道哪个进程响应客户端的请求呢。
> 我之前想在kernel里面拦截binder流量做所有，mock，难搞:)
>
>

不要想了，死路一条。drm直接ptrace，他是走的native的binder

## 回复 by 霸业 (#25)

*2024-6-1 17:12*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  不要想了，死路一条。drm直接ptrace，他是走的native的binder
>
>

## 回复 by zkywalker (#26)

*2024-8-5 11:09*

大佬牛逼，思路和大佬类似，已经完成了步骤5，有多个各地的非wifi状态的机器机房可以自动化采集数据，但是改机部分有思路没技术实现，还得是大佬![image](https://bbs.kanxue.com/view/img/face/35.gif)

## 回复 by 珍惜Any (#27)

*2024-8-5 11:35*

>
> [zkywalker](https://bbs.kanxue.com/user-674746.htm)
>
>  大佬牛逼，思路和大佬类似，已经完成了步骤5，有多个各地的非wifi状态的机器机房可以自动化采集数据，但是改机部分有思路没技术实现，还得是大佬[em_35]
>
>

嘿嘿嘿 ，我这边代码跑了1年了，目前还没有发现改不掉的，有啥问题都可以随时帖子里面问。

## 回复 by zkywalker (#28)

*2024-8-5 16:40*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  嘿嘿嘿 ，我这边代码跑了1年了，目前还没有发现改不掉的，有啥问题都可以随时帖子里面问。
>
>

还得是大佬，我这的RPA自动采集也跑了快一年了，在一定量的范围内还是比较安全的，但是已经开始遇到设备指纹维度的风控了，不过我的root后的风控对抗经验太拉胯，还不敢把设备都root了，不过大佬的文章也算给了以及强心针，至少表示这个路子可行，跟大佬多学习了![image](https://bbs.kanxue.com/view/img/face/29.gif)

## 回复 by 珍惜Any (#29)

*2024-8-7 16:43*

>
> [zkywalker](https://bbs.kanxue.com/user-674746.htm)
>
>  还得是大佬，我这的RPA自动采集也跑了快一年了，在一定量的范围内还是比较安全的，但是已经开始遇到设备指纹维度的风控了，不过我的root后的风控对抗经验太拉胯，还不敢把设备都root了，不过大佬的文章也 ...
>
>

![image](https://bbs.kanxue.com/view/img/face/69.gif)

## 回复 by gunkkk (#30)

*2024-8-8 14:50*

感谢大佬 请教一下这里apatch相比GKI的优势除了通用性外还有什么其他的点吗 比如有没有针对GKI内核的检测？![image](https://bbs.kanxue.com/view/img/face/4.gif)

## 回复 by gunkkk (#31)

*2024-8-8 14:56*

而且只保留bootid不保留boottime信息么

## 回复 by 养只猫不好么 (#32)

*2024-8-8 18:32*

感谢分享

## 回复 by 李啊啊 (#33)

*2024-8-9 17:16*

佬，某团的风控，能这么玩嘛？

## 回复 by 珍惜Any (#34)

*2024-8-9 19:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  李啊啊](https://bbs.kanxue.com/user-736307.htm)
>
>  佬，某团的风控，能这么玩嘛？
>
>

肯定可以，这套方案是通用的

## 回复 by 珍惜Any (#35)

*2024-8-9 20:01*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gunkkk](https://bbs.kanxue.com/user-915131.htm)
>
>  而且只保留bootid不保留boottime信息么
>
>

好问题，这块也需要在内核里面处理一下stat和stat -f的信息，boot_id的信息 要和开机时间一样

## 回复 by 珍惜Any (#36)

*2024-8-12 15:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gunkkk](https://bbs.kanxue.com/user-915131.htm)
>
>  感谢大佬 请教一下这里apatch相比GKI的优势除了通用性外还有什么其他的点吗 比如有没有针对GKI内核的检测？[em_4]
>
>

侧信道

## 回复 by 李啊啊 (#37)

*2024-8-13 11:48*

佬，这套系统能采购吗？或者有类似的平台可以介绍下吗

## 回复 by gunkkk (#38)

*2024-8-13 14:29*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  好问题，这块也需要在内核里面处理一下stat和stat -f的信息，boot_id的信息 要和开机时间一样
>
>

直接getclock拿的呢？ 另外大佬方不方便透露下GKI的侧信道检测指的是kernelsu之前那个root入口的吗 还是说有什么不可避免的侧信道痕迹咧

## 回复 by gunkkk (#39)

*2024-8-13 14:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gunkkk](https://bbs.kanxue.com/user-915131.htm)
>
>  直接getclock拿的呢？ 另外大佬方不方便透露下GKI的侧信道检测指的是kernelsu之前那个root入口的吗 还是说有什么不可避免的侧信道痕迹咧
>
>

说错了不是getclock 是拿boottime的syscall

## 回复 by 珍惜Any (#40)

*2024-9-4 10:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  李啊啊](https://bbs.kanxue.com/user-736307.htm)
>
>  佬，这套系统能采购吗？或者有类似的平台可以介绍下吗
>
>

课程会讲

## 回复 by 珍惜Any (#41)

*2024-9-4 10:15*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  gunkkk](https://bbs.kanxue.com/user-915131.htm)
>
>  直接getclock拿的呢？ 另外大佬方不方便透露下GKI的侧信道检测指的是kernelsu之前那个root入口的吗 还是说有什么不可避免的侧信道痕迹咧
>
>

这种不太好搞得，内核缺陷。大厂一般也就是频繁调用然后，计算平均值，上报到服务端去分析，判断是否是自定义内核系列。

## 回复 by angeliswx (#42)

*2024-9-7 02:48*

大佬 能通过这个方式做到自动化采集pdd吗

## 回复 by 珍惜Any (#43)

*2024-9-9 14:53*

>
> [angeliswx](https://bbs.kanxue.com/user-979063.htm)
>
>  大佬 能通过这个方式做到自动化采集pdd吗
>
>

你猜... 线上代码跑了不知道多久了。

## 回复 by angeliswx (#44)

*2024-9-9 16:48*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  你猜... 线上代码跑了不知道多久了。
>
>

就是能自动化采集解析pdd的商品数据是吧 谢谢大佬了 能不能+一下联系方式呀

## 回复 by 珍惜Any (#45)

*2024-9-11 17:17*

>
> [angeliswx](https://bbs.kanxue.com/user-979063.htm)
>
>  就是能自动化采集解析pdd的商品数据是吧 谢谢大佬了 能不能+一下联系方式呀
>
>

不搞黑产哈

## 回复 by 珍惜Any (#46)

*2024-9-22 14:13*

1

## 回复 by mb_ndaywdez (#47)

*2024-10-17 10:04*

牛逼，学习了。如果能给个代码让我白嫖就好了。

## 回复 by mb_cxmjsgrw (#48)

*2024-10-18 10:07*

请问大佬讲这个的课程在哪里？

## 回复 by 珍惜Any (#49)

*2024-10-18 14:34*

>
> [mb_cxmjsgrw](https://bbs.kanxue.com/user-866431.htm)
>
>  请问大佬讲这个的课程在哪里？
>
>

mt里面可以看看目录。

## 回复 by mb_ndaywdez (#50)

*2024-10-21 09:58*

牛逼，看到了。

## 回复 by mb_ndaywdez (#51)

*2024-10-23 15:39*

惜佬，有啥别的地方发博客么？ 总感觉看完缺少点什么。

## 回复 by 珍惜Any (#52)

*2024-10-30 16:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ndaywdez](https://bbs.kanxue.com/user-964958.htm)
>
>  惜佬，有啥别的地方发博客么？ 总感觉看完缺少点什么。
>
>

暂无

## 回复 by 珍惜Any (#53)

*2024-11-4 14:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ndaywdez](https://bbs.kanxue.com/user-964958.htm)
>
>  牛逼，学习了。如果能给个代码让我白嫖就好了。
>
>

没

## 回复 by KerryS (#54)

*2024-11-12 10:43*

佬，高版本是不是拿不到蓝牙的mac地址了，imei也是

## 回复 by 珍惜Any (#55)

*2024-11-12 11:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  佬，高版本是不是拿不到蓝牙的mac地址了，imei也是
>
>

关闭蓝牙即可，不要打开，NFC关闭，蓝牙关闭，手机静音，位置信息关闭，前置条件。

## 回复 by KerryS (#56)

*2024-11-13 11:54*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  关闭蓝牙即可，不要打开，NFC关闭，蓝牙关闭，手机静音，位置信息关闭，前置条件。
>
>

但是我开启蓝牙之后，获取到的蓝牙mac也是一串固定的02 00 ...，

## 回复 by 珍惜Any (#57)

*2024-11-13 18:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  但是我开启蓝牙之后，获取到的蓝牙mac也是一串固定的02 00 ...，
>
>

安卓版本问题，低版本，很多可以通过系统漏洞去获取蓝牙地址 。所以建议关闭。

## 回复 by magicjava (#58)

*2024-11-20 14:50*

珍惜老哥真牛呀！膜拜了

## 回复 by 珍惜Any (#59)

*2024-11-20 15:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  magicjava](https://bbs.kanxue.com/user-659541.htm)
>
>  珍惜老哥真牛呀！膜拜了
>
>

带带弟弟

## 回复 by Crack999 (#60)

*2024-11-22 14:49*

膜拜我的珍惜大哥---by发财

## 回复 by 天水姜伯约 (#61)

*2024-12-11 23:25*

无敌！！

## 回复 by wx_梦里不知身是客 (#62)

*2025-2-19 11:40*

大佬，这部分sysctl_bootid = (char *)kallsyms_lookup_name("sysctl_bootid");获取sysctl_bootid的地址的时候返回的是空，是对内核版本有什么要求吗

## 回复 by 珍惜Any (#63)

*2025-2-20 20:32*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_梦里不知身是客](https://bbs.kanxue.com/user-941716.htm)
>
>  大佬，这部分sysctl_bootid = (char *)kallsyms_lookup_name("sysctl_bootid");获取sysctl_bootid的地址的时候返 ...
>
>

你去搜一下看看呗 ，内核里面基本都会有的

## 回复 by dadadasda (#66)

*2025-3-17 14:26*

lsplant这套还是挺依赖跳板代码的，有跳板他的头指令就有比较明显的痕迹，最好是不要在用户进程里使用。某种程度上，最老版本的art-xposed 其实提供了不错的思路，也能移植到15上。

## 回复 by mb_bzferabr (#67)

*2025-4-16 11:24*

resetprop --delete指令在alp面具模块中，执行删除某条系统属性后，列如(persist.sys.vold_app_data_isolation_enabled)，会被30版本的牛头人检测到Property Modified (10)，但正常手机中本不应该存在这个属性吧，求各位大佬讲解一下牛头的检测到这条属性的原理是什么

## 回复 by 珍惜Any (#68)

*2025-4-16 13:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_bzferabr](https://bbs.kanxue.com/user-1031288.htm)
>
>  resetprop --delete指令在alp面具模块中，执行删除某条系统属性后，列如(persist.sys.vold_app_data_isolation_enabled)，会被30版本的牛头人 ...
>
>

用最新版本，最新magisk 28已经修复了这个问题了。也不算Bug，就是把原始属性置为null，牛头人会去读取原始熟悉判断是否null，以此实现检测的。

## 回复 by 珍惜Any (#69)

*2025-4-16 14:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_bzferabr](https://bbs.kanxue.com/user-1031288.htm)
>
>  resetprop --delete指令在alp面具模块中，执行删除某条系统属性后，列如(persist.sys.vold_app_data_isolation_enabled)，会被30版本的牛头人 ...
>
>

直接用system_porperties去解析就行了。

## 回复 by mb_bzferabr (#70)

*2025-4-16 16:37*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  用最新版本，最新magisk 28已经修复了这个问题了。也不算Bug，就是把原始属性置为null，牛头人会去读取原始熟悉判断是否null，以此实现检测的。
>
>

感谢大佬解答，我刚刚升级alp面具为28103，shamiko1.2.3，zygisknext1.2.8，模块里面使用用resetprop --delete命令，牛头还是会报Property Modified (10)，还有一点疑惑是system_porperties解析是指这种吗？
import android.os.SystemProperties;

public class SystemPropertyDemo {
    public static void main(String[] args) {
        // 读取 Android 版本
        String sdkVersion = SystemProperties.get("ro.build.version.sdk");
        System.out.println("Android SDK Version: " + sdkVersion);

        // 读取设备型号
        String deviceModel = SystemProperties.get("ro.product.model", "Unknown");
        System.out.println("Device Model: " + deviceModel);
    }
}

## 回复 by 残月_374878 (#71)

*2025-4-16 19:45*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  我怎么感觉直接去逆向分析风控sdk，看它上传了什么信息，更加简洁一点
>
>

确实是这样的，看他取哪些值，然后针对性的修改。但是作者可能想实现的是那种通杀情况

## 回复 by 珍惜Any (#72)

*2025-4-17 11:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_bzferabr](https://bbs.kanxue.com/user-1031288.htm)
>
>  感谢大佬解答，我刚刚升级alp面具为28103，shamiko1.2.3，zygisknext1.2.8，模块里面使用用resetprop --delete命令，牛头还是会报Property Modi ...
>
>

https://blog.canyie.top/2022/04/09/property-implementation-and-isolation/ 从头看一下

## 回复 by mb_lfvhycml (#73)

*2025-4-21 20:18*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  很好的问题，目前就tee解锁验证,github有一个项目，是hook密钥的方式去绕过的，还有一种办法是直接在内核tee这块进行处理 。
>
>

佬，内核tee处理有开源的github项目吗，我没搜到

## 回复 by 珍惜Any (#74)

*2025-4-22 00:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_lfvhycml](https://bbs.kanxue.com/user-1010376.htm)
>
>  佬，内核tee处理有开源的github项目吗，我没搜到
>
>

服务端mock一下设置成不支持tee然后在设置密钥，没必要搞这个，你root和解锁特征根本整不完，你试试hunter我写的，在小米设备根本不会误判

## 回复 by 福家舱 (#75)

*2025-5-16 09:12*

怎么联系，解决一个perimeterx   按压 获取了设备的那些指纹

## 回复 by 珍惜Any (#76)

*2025-6-3 19:10*

>
> [福家舱](https://bbs.kanxue.com/user-1013162.htm)
>
>  怎么联系，解决一个perimeterx 按压 获取了设备的那些指纹
>
>

自己hook一下就行了，tracer一份。

## 回复 by dreameriii (#77)

*2025-6-23 13:53*

> 这时候已经注入到目标进程，可以直接用inlinehook去hook 即可 。因为注入的分区主要在vendor下面 ，所以不能直接用system/lib下的so文件 。
>
>

请教下 惜佬 ，widevine 进程无法加载 非vendor 分区下的so，那该如何解决呢？ 我想参照 frida 通过匿名文件加载 agent.so的方式，发现还要修改selinux策略，挺麻烦的。 不知道大佬有没有什么高招可以赐教下~

## 回复 by 珍惜Any (#78)

*2025-6-23 15:56*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  这时候已经注入到目标进程，可以直接用inlinehook去hook 即可 。因为注入的分区主要在vendor下面 ，所以不能直接用system/lib下的so文件 。请教下 惜佬 ，widevine ...
>
>

恩挺恶心的，这块，我是直接把我的注入的A so挂载到vendor下，然后别的再搞个注入B so当注入器，吧A so启动。这个A so里面只依赖libc。其他任何数据都是通过ptrace启动时候函数调用传递过来。

## 回复 by 珍惜Any (#79)

*2025-6-23 15:57*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  这时候已经注入到目标进程，可以直接用inlinehook去hook 即可 。因为注入的分区主要在vendor下面 ，所以不能直接用system/lib下的so文件 。请教下 惜佬 ，widevine ...
>
>

我用的是magisk模块，所以比较方便，直接挂载就行了，frida我觉得问题太多，不方便定制化。

## 回复 by dreameriii (#80)

*2025-6-24 14:03*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我用的是magisk模块，所以比较方便，直接挂载就行了，frida我觉得问题太多，不方便定制化。
>
>

明白了，感谢大佬~ 我也是正好参照了 https://github.com/reveny/Android-GUI-Injector 这个项目，它包含了一个注入方法和frida 的注入很相似，利用匿名内存文件 + dlopen 就可以。 一开始看frida源码，想着要修改 selinux 策略好复杂，后来看到它的项目，直接在注入前先执行命令关闭 selinux ，注入完成后再开启…… 确实很方便，而且也注入成功了。![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 珍惜Any (#81)

*2025-6-24 16:27*

>
> [dreameriii](https://bbs.kanxue.com/user-719252.htm)
>
>  明白了，感谢大佬~ 我也是正好参照了 https://github.com/reveny/Android-GUI-Injector 这个项目，它包含了一个注入方法和frida 的注入很相似，利用匿名内 ...
>
>

嗯呢![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by mb_cawopqfr (#82)

*2025-8-8 17:45*

请问下大佬怎么去hook system_server呢? 在preServerSpecialize做hook默认是全局hook是吗

## 回复 by night star (#83)

*2025-8-9 15:11*

“如果是大文本数据可以直接通过抓包或者路由代理等直接解密即可”，想请问一下，这里的意思相当于还是要把它客户端的加解密逻辑还原出来是吗？

## 回复 by 珍惜Any (#84)

*2025-8-10 22:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  night star](https://bbs.kanxue.com/user-941380.htm)
>
>  “如果是大文本数据可以直接通过抓包或者路由代理等直接解密即可”，想请问一下，这里的意思相当于还是要把它客户端的加解密逻辑还原出来是吗？
>
>

最早我是这样搞得，后来我发现更简单的办法，系统服务里面可以获取到应用层的top view信息，直接解析这个就好了。

## 回复 by night star (#85)

*2025-8-16 21:33*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  最早我是这样搞得，后来我发现更简单的办法，系统服务里面可以获取到应用层的top view信息，直接解析这个就好了。
>
>

嗯，这样应该提取到的是它展示出来的数据吧

## 回复 by 珍惜Any (#86)

*2025-8-17 12:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  night star](https://bbs.kanxue.com/user-941380.htm)
>
>  嗯，这样应该提取到的是它展示出来的数据吧
>
>

对的，不展示的数据也不关注。

## 回复 by STCEN (#87)

*2025-9-1 17:25*

请教一下大佬，netlink获取网卡mac的方法是不是在安卓12和以上版本就不能再实现呢？我只能获取到ipv6地址

## 回复 by cs_jackw (#88)

*2025-9-1 18:23*

这一块楼主已经做得很稳定了吗？

## 回复 by 珍惜Any (#89)

*2025-9-2 10:04*

>
> [STCEN](https://bbs.kanxue.com/user-866679.htm)
>
>  请教一下大佬，netlink获取网卡mac的方法是不是在安卓12和以上版本就不能再实现呢？我只能获取到ipv6地址
>
>

对的，有的手机装了老版本的magisk，magisk本身有个漏洞也可以实现这个功能。

## 回复 by STCEN (#90)

*2025-9-2 10:12*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  对的，有的手机装了老版本的magisk，magisk本身有个漏洞也可以实现这个功能。
>
>

谢谢大佬解答！

## 回复 by zkbutt (#91)

*2025-10-21 20:36*

我这边花了半个月把以上的全实现了，最后还是过不了同盾的设备唯一性检测，崩溃中~

## 回复 by 珍惜Any (#92)

*2025-10-22 10:19*

>
> [zkbutt](https://bbs.kanxue.com/user-999559.htm)
>
>  我这边花了半个月把以上的全实现了，最后还是过不了同盾的设备唯一性检测，崩溃中~
>
>

你改的不够全，你去改hunter，里面有几个Native 设备指纹，还有一个java的，这些都需要改掉，才行。

## 回复 by zkbutt (#93)

*2025-11-13 18:27*

大佬这块有没有清单，或教程呢！求指导

## 回复 by 珍惜Any (#94)

*2025-11-26 10:07*

>
> [zkbutt](https://bbs.kanxue.com/user-999559.htm)
>
>  大佬这块有没有清单，或教程呢！求指导
>
>

没有，课程讲了一点。

## 回复 by mb_cdlztwsb (#95)

*2026-1-16 12:49*

hunter检测全部改掉就差不多了把![image](https://bbs.kanxue.com/view/img/face/029.gif)

## 回复 by 珍惜Any (#96)

*2026-1-21 11:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_cdlztwsb](https://bbs.kanxue.com/user-1064393.htm)
>
>  hunter检测全部改掉就差不多了把[em_029]
>
>

是指纹

## 回复 by 珍惜Any (#97)

*2026-3-2 14:18*

1

## 回复 by JanusXiao (#98)

*2026-3-5 17:09*

惜佬，请教下；ptrace attach到目标进程 。然后让目标进程调用dlopen去打开指定的so文件 ，读取寄存器这里I/O error；好像是 CFI保护：控制流完整性阻止读取关键寄存器，android 13；有没有破局的方案![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by JanusXiao (#99)

*2026-3-6 16:49*

有没有大佬遇到libwvaidl.so中hook  行为导致 Widevine CDM 初始化失败，降级到 L3 模式，并且 deviceUniqueId 被清空；求赐教

## 回复 by 珍惜Any (#100)

*2026-3-10 17:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  JanusXiao](https://bbs.kanxue.com/user-1043226.htm)
>
>  有没有大佬遇到libwvaidl.so中hook 行为导致 Widevine CDM 初始化失败，降级到 L3 模式，并且 deviceUniqueId 被清空；求赐教
>
>

一加手机吧 ，解锁了TEE被破坏了。 DRM这玩意我记得是运行在TEE里面 。

## 回复 by 珍惜Any (#101)

*2026-3-10 17:14*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  JanusXiao](https://bbs.kanxue.com/user-1043226.htm)
>
>  惜佬，请教下；ptrace&nbsp;attach到目标进程&nbsp;。然后让目标进程调用dlopen去打开指定的so文件&nbsp;，读取寄存器这里I/O&nbsp ...
>
>

我记得 drm在vendor分区，这块需要注意分区问题，你需要把你得so挂载到vendor分区，

## 回复 by JanusXiao (#102)

*2026-3-10 17:44*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  一加手机吧 ，解锁了TEE被破坏了。 DRM这玩意我记得是运行在TEE里面 。
>
>

pixel 6 pro android13，不是因为libwvaidl.so这里有防御机制么？我找了keybox能过三绿；so也挂载到vendor分区，hook代码都是正常执行的，只是getDeviceUniqueId返回值为空了，如果不执行hook getDeviceUniqueId逻辑，能正常获取到系统的drmid，执行了hook获取到的就是空值

## 回复 by 珍惜Any (#103)

*2026-3-11 10:40*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  JanusXiao](https://bbs.kanxue.com/user-1043226.htm)
>
>
>
>
>
>
>
>  珍惜Any
>
>
>
>  一加手机吧 ，解锁了TEE被破坏了。 DRM这玩意我记得是运行在TEE里面 。
>
>  pixel&nbsp;6&a ...
>
>

我基本用的小米设备，我是不信任pixel设备的，国内用pixel基本都是高风险，国外还好。

## 回复 by JanusXiao (#104)

*2026-3-11 10:51*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  我基本用的小米设备，我是不信任pixel设备的，国内用pixel基本都是高风险，国外还好。
>
>

好的，感谢惜佬

## 回复 by mb_stdlrcgp (#105)

*2026-3-18 20:41*

66666
