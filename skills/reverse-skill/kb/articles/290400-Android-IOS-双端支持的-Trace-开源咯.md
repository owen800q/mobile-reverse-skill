---
title: '[原创]Android IOS 双端支持的 Trace 开源咯'
url: https://bbs.kanxue.com/thread-290400.htm
tid: 290400
author: lidongyooo
date: '2026-03-19'
tags: [Android安全, 原创, 逆向分析, 程序开发, 源码框架, 工具脚本]
crawled_at: '2026-08-08T10:17:36+00:00'
replies: 122
---

# 真机 GumTrace，每 3 秒 1G

Github: <https://github.com/lidongyooo/GumTrace>

基于 Frida Gum (Stalker) 引擎的 ARM64 真机动态指令追踪工具，支持 Android 和 iOS 平台。

## 致谢

- [Trace UI](https://github.com/imj01y/trace-ui) - 本项目官方指定的 trace 分析工具。高性能 ARM64 执行 trace 可视化分析工具。基于 Tauri 2 + React 构建的桌面应用，专为安全研究员设计，支持千万行或亿行级大规模 trace 的流畅浏览、函数调用树折叠、反向污点追踪、内存/寄存器实时查看等功能。Trace Ul 与 GumTrace 深度适配，是在分析 trace 日志时的得力助手。感谢 [@imj01y](https://github.com/imj01y) 的开源贡献!

## 功能概述

GumTrace 以共享库的形式注入目标进程，对指定模块进行指令级别的动态追踪，并将完整的执行轨迹写入日志文件。

### 核心功能

- **指令级追踪** — 逐条记录 ARM64 指令的执行，包括模块名、绝对地址、相对偏移、助记符和操作数
- **寄存器快照** — 记录每条指令执行时的寄存器读写值（通用寄存器 x0-x28、SIMD 寄存器 q/d/s/h/b、SP、FP、LR、NZCV）
- **内存访问追踪** — 记录内存读写的目标地址（mem_r / mem_w），支持基址 + 索引 + 偏移的复合寻址计算
- **函数调用拦截** — 自动识别 BL/BLR/BR/B 指令的跳转目标，匹配已知符号后打印函数参数和返回值
- **系统调用追踪** — 拦截 SVC 指令，根据系统调用号解析函数名（覆盖 Linux aarch64 全部系统调用）
- **Android JNI 追踪** — 自动识别 JNI 函数调用，解析 jclass、jmethodID、jstring 等 JNI 对象
- **iOS ObjC 追踪** — 拦截 objc_msgSend，解析类名、selector，打印 NSDictionary/NSArray/NSString/NSData/NSNumber 等 ObjC 对象

### 污点分析工具

项目附带一个独立的离线污点分析工具（`src/taint/`），可对 GumTrace 生成的日志进行正向/反向数据流追踪：

- **正向追踪** — 从指定寄存器或内存地址出发，追踪数据如何被传播
- **反向追踪** — 从指定寄存器或内存地址出发，反向追溯数据来源
- 支持寄存器间传播、寄存器与内存间的 load/store 传播、NZCV 标志位传播
- 输出匹配的指令及每步的污点快照

## 日志格式

每行指令记录的格式如下：

```python
[模块名] 0x绝对地址!0x相对偏移 助记符 操作数; 寄存器名=值 mem_r=地址 mem_w=地址
\```

示例：

```python
[libtarget.so] 0x7a3c001890!0x1890 ldr x0, [x1, #0x10]; x1=0x7a3c050000 mem_r=0x7a3c050010
-> x0=0x12345678
call func: strcmp(0x7a3c050010, 0x7a3c060000)
args0: hello
args1: world
ret: 0xffffffffffffffff
\```

## 构建

### 环境要求

- CMake >= 3.10
- Android: NDK r29+（arm64-v8a）
- iOS: Xcode + iphoneos SDK（arm64，最低 iOS 12.0）
- Frida Gum 静态库（已包含在 `libs/` 目录）

### 构建 Android

```bash
# 编辑 build_android.sh 中的 ANDROID_NDK_HOME 路径
./build_android.sh
# 产物: build_android/libGumTrace.so
\```

### 构建 iOS

```bash
./build_ios.sh
# 产物: build_ios/libGumTrace.dylib
\```

### 构建污点分析工具

```bash
cd src/taint
mkdir -p build && cd build
cmake ..
cmake --build .
# 产物: taint_tracker
\```

## API

GumTrace 编译为共享库，导出以下 C 接口：

### `init(module_names, trace_file_path, thread_id, options)`

初始化追踪器。

| 参数 | 类型 | 说明 |
|-|-|-|
| `module_names` | `const char*` | 要追踪的模块名，多个用逗号分隔（如 `"libtarget.so,libutils.so"`） |
| `trace_file_path` | `char*` | 日志输出文件路径 |
| `thread_id` | `int` | 要追踪的线程 ID（0 表示追踪当前线程） |
| `options` | `GUM_OPTIONS` | 选项位掩码，`1` 启用 DEBUG 模式（高频刷写日志） |

### `run()`

启动追踪。会创建一个后台线程定期刷写日志文件。

### `unrun()`

停止追踪，刷写并关闭日志文件。

## 使用示例（Frida）

通过 Frida 脚本加载 GumTrace 共享库并调用其导出接口，即可对目标进程进行指令追踪。完整示例见 [example.js](https://bbs.kanxue.com/example.js)。

### 1. 推送 GumTrace 到设备

```bash
adb push build_android/libGumTrace.so /data/local/tmp/
\```

>
> **注意：** 如果 SO 加载失败（dlopen 返回 NULL），通常是 SELinux 阻止了从 `/data/local/tmp/` 加载共享库。需要先关闭 SELinux：
>
>
>
>
> ```bash
> adb shell setenforce 0
> ```
>
>
>

### 2. 编写 Frida 脚本

```javascript
let traceSoName = 'libGumTrace.so'
let targetSo = 'libtarget.so'

let gumtrace_init = null
let gumtrace_run = null
let gumtrace_unrun = null

// 加载 GumTrace 共享库并获取函数指针
function loadGumTrace() {
    let dlopen = new NativeFunction(Module.findGlobalExportByName('dlopen'), 'pointer', ['pointer', 'int'])
    let dlsym = new NativeFunction(Module.findGlobalExportByName('dlsym'), 'pointer', ['pointer', 'pointer'])

    let soHandle = dlopen(Memory.allocUtf8String('/data/local/tmp/' + traceSoName), 2)

    gumtrace_init = new NativeFunction(
        dlsym(soHandle, Memory.allocUtf8String('init')),
        'void', ['pointer', 'pointer', 'int', 'int'])
    gumtrace_run = new NativeFunction(
        dlsym(soHandle, Memory.allocUtf8String('run')),
        'void', [])
    gumtrace_unrun = new NativeFunction(
        dlsym(soHandle, Memory.allocUtf8String('unrun')),
        'void', [])
}

// 初始化并启动追踪
function startTrace() {
    loadGumTrace()
    let moduleNames = Memory.allocUtf8String(targetSo)
    let outputPath = Memory.allocUtf8String('/data/data/com.example.app/trace.log')
    let threadId = 0   // 0 = 当前线程
    let options = 0    // 1 = DEBUG 模式
    gumtrace_init(moduleNames, outputPath, threadId, options)
    gumtrace_run()
}

// 停止追踪
function stopTrace() {
    gumtrace_unrun()
}

// hook 目标函数，在其执行期间进行追踪
let targetModule = Process.findModuleByName(targetSo)
Interceptor.attach(targetModule.base.add(0x1234), {
    onEnter() {
        startTrace()
        this.tracing = true
    },
    onLeave() {
        if (this.tracing) stopTrace()
    }
})
\```

### 3. 运行

```bash
frida -U -f com.example.app -l hook.js
\```

### 4. 拉取日志

```bash
adb pull /data/data/com.example.app/trace.log .
\```

## 污点分析工具使用

### 命令行

```bash
# 正向追踪：从第 100 行的 x0 寄存器开始追踪数据流向
./taint_tracker -i trace.log -o result.log -f x0 -l 100

# 反向追踪：从第 500 行的 x0 寄存器反向追溯数据来源
./taint_tracker -i trace.log -o result.log -b x0 -l 500

# 追踪内存地址
./taint_tracker -i trace.log -o result.log -f mem:0x1000 -l 100

# 按相对地址定位起始位置
./taint_tracker -i trace.log -o result.log -f x0 -a 0x1890

# 按字节偏移定位起始位置
./taint_tracker -i trace.log -o result.log -b x0 -p 1048576
\```

### 010 Editor 插件

项目提供了 010 Editor 脚本 [TaintTracker.1sc](https://bbs.kanxue.com/src/taint/TaintTracker.1sc)，可以在 010 Editor 中直接对 trace 日志进行交互式污点分析。

**安装：**

1. 编辑 `TaintTracker.1sc`，将 `TAINT_TRACKER_PATH` 和 `OUTPUT_DIR` 修改为你本地的路径
2. 在 010 Editor 中通过 **Scripts > Run Script** 加载该脚本，或将其添加到脚本目录中

**使用：**

1. 在 010 Editor 中打开 GumTrace 生成的 trace 日志文件
2. 将光标移到要分析的指令行（以 `[` 开头的行）
3. 运行 `TaintTracker.1sc` 脚本
4. 在弹出的对话框中选择追踪方向（正向/反向）
5. 输入追踪目标（寄存器名如 `x0`，或内存地址如 `mem:0x1000`），脚本会自动提取光标所在行的第一个寄存器作为默认值
6. 脚本自动调用 `taint_tracker` 并在 010 Editor 中打开结果文件

## 项目结构

```python
GumTrace/
├── CMakeLists.txt              # 主构建脚本
├── build_android.sh            # Android 构建脚本
├── build_ios.sh                # iOS 构建脚本
├── example.js                  # Frida 使用示例脚本
├── libs/                       # Frida Gum 静态库和头文件
│   ├── FridaGum-Android-17.6.2.h
│   └── FridaGum-IOS-17.6.2.h
└── src/
    ├── main.cpp                # 入口，导出 init/run/unrun 接口
    ├── GumTrace.h/cpp          # 核心追踪引擎（Stalker 回调、指令解析、日志写入）
    ├── CallbackContext.h/cpp   # 指令上下文对象池
    ├── FuncPrinter.h/cpp       # 函数调用参数/返回值打印（含 JNI 和 ObjC）
    ├── Utils.h/cpp             # 工具函数（寄存器值读取、hexdump、字符串格式化）
    ├── platform.h              # 平台检测宏
    └── taint/                  # 离线污点分析工具
        ├── CMakeLists.txt
        ├── main.cpp            # 命令行入口
        ├── TraceParser.h/cpp   # 日志解析器（零分配设计）
        ├── TaintEngine.h/cpp   # 污点传播引擎（正向/反向）
        └── TaintTracker.1sc    # 010 Editor 污点分析脚本
\```

## 内置函数识别

GumTrace 内置了对常见库函数参数的自动解析：

| 类别 | 函数 |
|-|-|
| 字符串操作 | `strlen`, `strcmp`, `strncmp`, `strcpy`, `strcat`, `strstr`, `strdup` 等 |
| 内存操作 | `memcpy`, `memmove`, `memset`, `memcmp`, `memmem` 等 |
| 文件操作 | `open`, `openat`, `read`, `write`, `fopen`, `close` 等 |
| 内存分配 | `malloc`, `calloc`, `realloc`, `free` |
| 内存映射 | `mmap`, `mprotect` |
| 动态链接 | `dlopen`, `dlsym`, `dlclose` |
| 格式化 | `sprintf`, `snprintf`, `sscanf` |
| 系统 | `syscall`, `__system_property_get`, `sysconf` |
| JNI (Android) | `FindClass`, `GetMethodID`, `CallObjectMethod`, `GetStringUTFChars` 等全部 JNI 函数 |
| ObjC (iOS) | `objc_msgSend`, `objc_retain`, `objc_release`, `NSClassFromString` 等 |

## 技术细节

- 基于 Frida Gum Stalker 进行代码插桩，使用 `gum_stalker_iterator_put_callout` 在每条指令前插入回调
- 使用 Capstone 反汇编引擎解析 ARM64 指令的操作数和访问类型
- 自动排除系统模块（`/system/`、`/apex/`、`/vendor/` 等路径），仅追踪用户指定的目标模块
- 跳过原子指令（LSE、独占加载/存储）以避免 Stalker 插桩导致的死锁
- 使用 10MB 内存缓冲区减少文件 I/O 次数，提升追踪性能
- 污点分析工具采用零分配解析设计，可高效处理 GB 级日志文件

---

# 回复

## 回复 by mb_asiwnxyv (#2)

*2026-3-19 13:29*

感谢分享

## 回复 by mb_rztmbvgb (#3)

*2026-3-19 13:32*

666

## 回复 by bluegatar (#4)

*2026-3-19 14:39*

感谢大佬，trace的格式和unidbgyi一样吗？

## 回复 by iBa0 (#5)

*2026-3-19 15:46*

老铁666

## 回复 by 残枫 (#6)

*2026-3-19 15:55*

学习学习

## 回复 by xianhuimin (#7)

*2026-3-19 16:53*

666

## 回复 by k4y0z (#8)

*2026-3-19 16:55*

666

## 回复 by 墨穹呢 (#9)

*2026-3-19 17:06*

感谢分享

## 回复 by mb_ghcouuzx (#10)

*2026-3-19 17:11*

看看看看

## 回复 by 随风而行aa (#11)

*2026-3-19 17:39*

看看

## 回复 by bluegatar (#12)

*2026-3-19 20:44*

有点问题啊，trace后的log用trace ui打开提示：文件格式不正确，未检测到有效的arm64 trace指令行

## 回复 by 熊猫吃鱼 (#13)

*2026-3-19 21:28*

6666

## 回复 by Zepp7289 (#14)

*2026-3-19 21:42*

tql

## 回复 by xxjj678 (#15)

*2026-3-19 21:54*

666

## 回复 by mb_ysikfhxt (#16)

*2026-3-19 22:04*

111

## 回复 by 西瓜帅 (#17)

*2026-3-20 09:27*

666

## 回复 by Imxz (#18)

*2026-3-20 09:27*

tql

## 回复 by xuhe123 (#19)

*2026-3-20 11:41*

666666

## 回复 by 川美 (#20)

*2026-3-20 11:53*

老铁666

## 回复 by wx_。。。。_455 (#21)

*2026-3-20 14:16*

666

## 回复 by amwpecel (#22)

*2026-3-20 14:26*

老铁666

## 回复 by mb_cbgtaveo (#23)

*2026-3-20 15:57*

6666666666

## 回复 by dob_C (#24)

*2026-3-20 16:02*

感谢分享

## 回复 by mb_pmgifpme (#25)

*2026-3-20 18:02*

1

## 回复 by ldehua (#26)

*2026-3-20 19:15*

666

## 回复 by ulong9527 (#27)

*2026-3-21 01:05*

666

## 回复 by huangjw (#28)

*2026-3-21 09:54*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_qimctavn (#29)

*2026-3-22 14:39*

6

## 回复 by 一栋奥特曼 (#30)

*2026-3-23 10:24*

666

## 回复 by dsr000 (#31)

*2026-3-23 15:57*

6

## 回复 by maxcl (#32)

*2026-3-25 10:12*

666

## 回复 by kingking888 (#33)

*2026-3-25 11:00*

666

## 回复 by puppet_w (#34)

*2026-3-25 11:10*

66

## 回复 by XCicada (#35)

*2026-3-25 11:35*

感谢分享

## 回复 by 日本小丸子 (#36)

*2026-3-25 15:02*

1

## 回复 by 寒君愁 (#37)

*2026-3-27 18:14*

1

## 回复 by lackone (#38)

*2026-3-28 11:16*

6666

## 回复 by mb_gqtfyqhu (#39)

*2026-3-28 23:11*

666666666666666

## 回复 by 海带 (#40)

*2026-3-29 00:34*

6666

## 回复 by mb_stdlrcgp (#41)

*2026-3-29 13:54*

666666

## 回复 by logeye (#42)

*2026-3-29 17:08*

666

## 回复 by FMNS (#43)

*2026-3-30 06:04*

6666

## 回复 by tonykros (#44)

*2026-3-31 08:20*

666

## 回复 by MaYil (#45)

*2026-3-31 16:59*

感谢分享

## 回复 by 逆道而行 (#46)

*2026-3-31 17:20*

1

## 回复 by pannifushe (#47)

*2026-4-2 09:09*

666666

## 回复 by git_26578slotmagia (#48)

*2026-4-2 13:34*

111

## 回复 by mb_rbaigqfb (#49)

*2026-4-3 13:02*

感谢分享

## 回复 by fengvmu (#50)

*2026-4-4 20:08*

666

## 回复 by 小迷糊ddd (#51)

*2026-4-6 22:49*

感谢分享，受教了。

## 回复 by wx_好饿想吃肉 (#52)

*2026-4-7 10:02*

6666

## 回复 by lmh2020 (#53)

*2026-4-10 07:47*

666

## 回复 by Oo风之恋oO (#54)

*2026-4-10 13:55*

这是什么东西

## 回复 by win柠初 (#55)

*2026-4-10 13:55*

感谢分享

## 回复 by mb_lfwgtxdb (#56)

*2026-4-10 15:02*

感谢分享

## 回复 by laolichaobao (#57)

*2026-4-10 16:04*

666

## 回复 by wx_L_ (#58)

*2026-4-10 17:43*

666

## 回复 by 一丢丢 (#59)

*2026-4-10 17:48*

666

## 回复 by shutu (#60)

*2026-4-12 04:07*

666666666666

## 回复 by vdaoren (#61)

*2026-4-12 11:02*

![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by nuomida (#62)

*2026-4-13 10:42*

学习学习

## 回复 by mb_yaeaedrh (#63)

*2026-4-14 17:56*

1

## 回复 by 小尘0000 (#64)

*2026-4-14 17:58*

1

## 回复 by mb_4nrpVMxJ (#65)

*2026-4-16 06:52*

1

## 回复 by tjytjy (#66)

*2026-4-16 17:08*

666

## 回复 by 龙飞雪 (#67)

*2026-4-16 17:44*

1

## 回复 by TeamAR (#68)

*2026-4-16 18:02*

666

## 回复 by cpannn (#69)

*2026-4-17 20:34*

厉害

## 回复 by git_14248bibinocode (#70)

*2026-4-20 11:22*

66666666666666666

## 回复 by mb_rfulxvjw (#71)

*2026-4-20 11:55*

1

## 回复 by git_49999huanptd2011 (#72)

*2026-4-20 12:29*

1

## 回复 by 3uiad (#73)

*2026-4-20 14:08*

666

## 回复 by 兰小娟 (#74)

*2026-4-20 15:34*

66666666

## 回复 by sorely (#75)

*2026-4-21 13:14*

666

## 回复 by 流浪的孩纸 (#76)

*2026-4-21 18:00*

感谢分享

## 回复 by mb_pvtzrssj (#77)

*2026-4-22 16:25*

看看

## 回复 by mb_gluymaeh (#78)

*2026-4-24 14:38*

感谢分享

## 回复 by xifgg (#79)

*2026-5-9 17:05*

666

## 回复 by guijingwen (#80)

*2026-5-9 17:40*

66

## 回复 by CuteHacker (#81)

*2026-5-11 10:49*

1

## 回复 by niama (#82)

*2026-5-15 04:15*

666

## 回复 by 鼻屎怪 (#83)

*2026-5-15 14:12*

666

## 回复 by mb_ykavguun (#84)

*2026-5-17 21:30*

1

## 回复 by myios (#85)

*2026-5-17 22:46*

666

## 回复 by np010 (#86)

*2026-5-24 20:54*

nice share

## 回复 by B.M.K (#87)

*2026-5-24 21:21*

66

## 回复 by mb_vjpiriil (#88)

*2026-5-26 11:01*

666

## 回复 by g-yan (#89)

*2026-5-27 10:02*

1

## 回复 by 发烧小孩 (#90)

*2026-5-28 17:20*

666

## 回复 by baichisi (#91)

*2026-5-29 18:25*

666

## 回复 by 寻梦之璐 (#92)

*2026-5-30 17:56*

66

## 回复 by ycdear (#93)

*2026-5-30 19:43*

111

## 回复 by @@@ (#94)

*2026-5-31 17:23*

感谢分享

## 回复 by shmilyaxy (#95)

*2026-6-1 17:16*

666

## 回复 by CheRevir (#96)

*2026-6-1 17:41*

66666

## 回复 by 丶咖啡猫丶 (#97)

*2026-6-2 15:04*

666

## 回复 by mb_mwfzoyhc (#98)

*2026-6-8 05:12*

谢谢分享

## 回复 by git_74197luban110 (#99)

*2026-6-8 08:31*

666

## 回复 by mb_aszywhsj (#100)

*2026-6-10 10:40*

6666

## 回复 by wx_Huber Barrientos (#101)

*2026-6-11 01:11*

666

## 回复 by mb_jegknedl (#102)

*2026-6-11 05:11*

继续学习

## 回复 by bygrand (#103)

*2026-6-11 23:33*

强强

## 回复 by mb_hfpmtthz (#104)

*2026-6-13 11:39*

6666

## 回复 by 木志本柯 (#105)

*2026-6-13 13:34*

有将它应用实战过游戏的反作弊吗？效果怎么样，会不会被检测？

## 回复 by Sungt. (#106)

*2026-6-15 15:14*

1

## 回复 by mb_etrbkelx (#107)

*2026-6-17 01:23*

666

## 回复 by wx_leo_346548 (#108)

*2026-6-18 10:27*

感谢分享

## 回复 by mb_mkwbfjsm (#109)

*2026-6-21 00:21*

老铁666

## 回复 by mb_paopxhtx (#110)

*2026-6-22 22:31*

我看看怎么样

## 回复 by wx_Dispa1r (#111)

*2026-6-23 15:11*

1

## 回复 by 勒LI (#112)

*2026-6-23 16:31*

666

## 回复 by lbunknow (#113)

*2026-6-24 10:08*

666

## 回复 by mb_nfjeyeai (#114)

*2026-6-25 14:43*

6

## 回复 by zkbutt (#115)

*2026-6-25 23:34*

学习

## 回复 by wx_coddvccwyh (#116)

*2026-7-6 19:55*

6666

## 回复 by TheLuckyOne (#117)

*2026-7-6 21:32*

nb

## 回复 by wx_至尊宝_395664 (#118)

*2026-7-16 10:30*

1

## 回复 by Yy798e (#119)

*2026-7-17 17:13*

666

## 回复 by v5w7crq3 (#120)

*2026-7-23 18:46*

666

## 回复 by 伊苏尔德 (#121)

1

## 回复 by mb_fnfsthcc (#122)

111

## 回复 by mb_gkbxtfri (#123)

666
