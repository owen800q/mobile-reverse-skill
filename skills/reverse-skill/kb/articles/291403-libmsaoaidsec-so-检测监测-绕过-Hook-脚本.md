---
title: '[原创]libmsaoaidsec.so 检测监测 绕过 Hook 脚本'
url: https://bbs.kanxue.com/thread-291403.htm
tid: 291403
author: xiusi
date: '2026-05-30'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:04:53+08:00'
replies: 140
---

# libmsaoaidsec.so 检测监测+绕过 Hook 脚本

前文：[[原创]libmsaoaidsec.so 检测体系分析](https://bbs.kanxue.com/thread-291377.htm)
[[原创]经典 Frida 检测 libmsaoaidsec.so 绕过](https://bbs.kanxue.com/thread-289359.htm)

---

## 一、问题背景

在 Android Native 安全分析中，很多安全组件并不会等到 `JNI_OnLoad` 后才启动检测，而是会将部分关键逻辑放在 **`.init`** **、** **`.init_proc`** **或** **`.init_array`** **等更早的初始化阶段**。

`libmsaoaidsec.so` 的检测逻辑就存在这类特征：如果在 `android_dlopen_ext` 的 `onLeave` 阶段再安装 Hook，库的初始化逻辑通常已经执行完毕，部分反调试、注入检测或完整性校验可能已经触发，最终表现为 App 闪退、退出或关键流程异常。

---

## 二、Android SO 加载流程与 Hook 时机

Android 加载 Native SO 时，通常会经过以下流程：

| 阶段 | 关键函数或段 | 说明 |
|-|-|-|
| 1 | `dlopen` / `android_dlopen_ext` | 系统加载器将目标 SO 映射到进程内存 |
| 2 | `.init` / `.init_proc` | 执行 SO 的早期初始化代码 |
| 3 | `.init_array` | 执行初始化数组中的函数，例如 C++ 全局构造函数 |
| 4 | `JNI_OnLoad` | 注册 JNI 方法并完成 Java 与 Native 层绑定 |

需要注意的是，**`android_dlopen_ext`** **的** **`onLeave`** **并不等价于“SO 刚刚映射完成”** 。当 `onLeave` 被触发时，加载器通常已经执行完 `.init` 和 `.init_array` 中的初始化函数。如果目标库把检测逻辑放在这些早期阶段，那么在 `onLeave` 再安装 Hook 往往已经太晚。

更合适的思路是：**在** **`android_dlopen_ext`** **的** **`onEnter`** **中识别目标 SO 加载事件，然后寻找** **`.init_proc`** **内部调用的外部导入函数作为二级锚点**。这样既可以保证目标 SO 已经进入加载流程，又能在其初始化逻辑执行过程中插入 Hook。

---

## 三、早期 Hook 锚点定位

对 `libmsaoaidsec.so` 的 `init_proc` 进行分析，可以看到其早期逻辑中调用了 `sub_123F0`：

```c
__int64 __fastcall init_proc(__int64 a1)
{
    ...

    StatusReg = _ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2));
    v15 = *(StatusReg + 40);
    s_1 = &StatusReg - 250;
    *off_47FB8 = sub_123F0(a1);
    ...
}
```

继续查看 `sub_123F0`，可以发现其调用了 `__system_property_get` 读取系统属性：

```c
__int64 sub_123F0()
{
    _QWORD nptr[2];

    nptr[1] = *(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);
    nptr[0] = 0LL;
    __system_property_get("ro.build.version.sdk", nptr);
    return atoi(nptr);
}
```

对应导入表中也可以看到 `__system_property_get`：

```
extern:00000000000A76D8 IMPORT __imp___system_property_get
extern:00000000000A76D8 ; CODE XREF: __system_property_get+C
extern:00000000000A76D8 ; DATA XREF: LOAD:__system_property_get_0
```

![导入函数定位](https://bbs.kanxue.com/upload/attach/202605/1036360_TEDTS7WJ5XETXCD.png)

由此可以确定一个较理想的早期 Hook 链路：

1. Hook `android_dlopen_ext`。
2. 在 `onEnter` 中判断当前加载路径是否包含 `libmsaoaidsec.so`。
3. 命中目标库后，立即 Hook `__system_property_get`。
4. 当 `__system_property_get("ro.build.version.sdk", ...)` 被调用时，说明执行已经进入目标库初始化流程。
5. 此时通过 `Process.findModuleByName("libmsaoaidsec.so")` 获取模块基址。
6. 基于 **模块基址 + 函数偏移** 安装检测监测 Hook 和绕过 Patch。

这个锚点的优势在于： **`__system_property_get`** **是** **`.init_proc`** **早期调用的外部导入函数，触发时机早于大多数检测逻辑，且比盲目轮询模块加载更稳定**。

---

## 四、检测点与绕过策略总览

脚本中主要通过函数返回值判断不同检测逻辑是否启用，并对部分关键分支进行返回值替换或直接写入 `RET` 指令。

### 4.1 函数偏移与检测含义

| 函数 | 偏移 | 判断条件 | 检测含义 |
|-|-|-|-|
| `sub_CA28` | `0xCA28` | 返回值是否为 `167` | ADB / USB 调试环境检测 |
| `sub_CAA8` | `0xCAA8` | 返回值是否为 `248` | Frida / 注入痕迹检测的条件之一 |
| `sub_CAE8` | `0xCAE8` | 返回值是否为 `249` | 反调试、`TracerPid`、线程状态检测 |
| `sub_CC64` | `0xCC64` | 返回值是否为 `218` | Magisk / root 检测 |
| `sub_CEE4` | `0xCEE4` | 返回值是否为 `203` | 目标区域 CRC32 校验 |
| `sub_C830` | `0xC830` | 返回值是否为 `1` | 轮询代码 CRC 校验条件之一 |
| `sub_95C8` | `0x95C8` | 返回值是否为真 | 轮询代码 CRC 校验条件之一 |
| `sub_12D9C` | `0x12D9C` | 返回值是否为真 | Frida / 注入痕迹检测的条件之一 |
| `sub_25A48` | `0x25A48` | `(retval & 1) == 0` | Native 环境检测、代码 CRC / APK v1 签名校验 |
| `sub_CEA4` | `0xCEA4` | 返回值替换为 `666` | 通过返回值修改绕过特定检测分支 |
| `sub_16720` | `0x16720` | 返回值替换为 `666` | 通过返回值修改绕过校验结果 |

### 4.2 复合判断条件

部分检测逻辑不是由单个函数返回值决定，而是由多个函数组合判断。

Frida / 注入痕迹检测：

```javascript
const shouldCheck = lastSubCAA8Ret === 248 && !lastSub12D9CRet;
```

含义如下：

- `sub_CAA8()` 返回 `248`
- `sub_12D9C()` 返回假值
- 两个条件同时满足时，进入 **Frida / 注入痕迹检测**

轮询代码 CRC 校验：

```javascript
const shouldCheck = lastSubC830Ret !== 1 || !!lastSub95C8Ret;
```

含义如下：

- `sub_C830()` 不等于 `1`，或者
- `sub_95C8()` 返回真值
- 任一条件满足时，进入 **轮询代码 CRC 校验**

这类复合条件非常适合通过日志进行动态观察，因为它不仅能显示某个函数是否被调用，还能帮助判断当前运行环境下到底触发了哪一类检测。

---

## 五、核心 Frida Hook 设计

整体脚本可以拆分为四个部分：

1. **目标库加载监控**：Hook `android_dlopen_ext`，捕获 `libmsaoaidsec.so` 加载事件。
2. **早期初始化锚点**：Hook `__system_property_get`，等待 `ro.build.version.sdk` 被读取。
3. **检测函数监测**：基于 `base + offset` Hook 关键函数，记录返回值并输出检测状态。
4. **绕过逻辑安装**：通过返回值替换和写入 `RET` 指令跳过特定检测函数。

### 5.1 监控目标 SO 加载

```javascript
function hookAndroidDlopenExt() {
    const androidDlopenExt = Module.findExportByName(null, 'android_dlopen_ext');
    if (androidDlopenExt === null) {
        logError('android_dlopen_ext not found');
        return;
    }

    Interceptor.attach(androidDlopenExt, {
        onEnter(args) {
            const pathPtr = args[0];
            if (pathPtr.isNull()) {
                return;
            }

            let path = null;
            try {
                path = pathPtr.readCString();
            } catch (e) {
                return;
            }

            if (path.indexOf(TARGET_SO) === -1) {
                return;
            }

            logInfo('detected loading of ' + path);
            locateInitAnchor();
        }
    });

    logInfo('hooked android_dlopen_ext at ' + androidDlopenExt);
}
```

这里选择 `onEnter` 而不是 `onLeave`，关键原因在于：**目标库的初始化函数会在** **`android_dlopen_ext`** **返回前执行**。如果等待 `onLeave`，很多早期检测已经错过。

### 5.2 借助 `__system_property_get` 捕获初始化阶段

```javascript
function locateInitAnchor() {
    if (propHooked) {
        return;
    }

    const sysPropGet = Module.findExportByName(null, '__system_property_get');
    if (sysPropGet === null) {
        logError('__system_property_get not found');
        return;
    }

    Interceptor.attach(sysPropGet, {
        onEnter(args) {
            const namePtr = args[0];
            if (namePtr.isNull()) {
                return;
            }

            let name = null;
            try {
                name = namePtr.readCString();
            } catch (e) {
                return;
            }

            if (name === null || name.indexOf(INIT_ANCHOR_PROPERTY) === -1) {
                return;
            }

            if (retPatched) {
                return;
            }

            logInfo('__system_property_get("' + name + '", ' + args[1] + ') hit');

            const module = Process.findModuleByName(TARGET_SO);
            if (module === null) {
                logError(TARGET_SO + ' not found by Frida module query');
                return;
            }

            logInfo('found ' + TARGET_SO + ' base = ' + module.base + ', size = 0x' + module.size.toString(16));
            installTargetHooks(module.base);
        }
    });

    propHooked = true;
    logInfo('hooked __system_property_get at ' + sysPropGet);
}
```

这段逻辑的核心是过滤属性名：

```javascript
const INIT_ANCHOR_PROPERTY = 'ro.build.version.sdk';
```

只有当目标库读取该属性时，才认为命中了早期初始化锚点。随后再获取 `libmsaoaidsec.so` 的基址并安装 Hook，避免对其他模块调用 `__system_property_get` 的行为造成干扰。

### 5.3 基于返回值判断检测是否启用

以 `sub_CC64` 为例，该函数返回 `218` 时，可以判断 Magisk / root 检测相关逻辑被启用：

```javascript
function hookSubCC64(base) {
    if (subCC64Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CC64_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CC64 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                log('sub_CC64 retval int = ' + ret + ', equals 218 => ' + (ret === 218 ? 'YES' : 'NO'));
                logDecision(ret === 218, ret === 218 ? MSG_MAGISK_ROOT_CHECK : MSG_NO_MAGISK_ROOT_CHECK);
            }
        });

        subCC64Hooked = true;
        logInfo('hooked sub_CC64 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CC64_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CC64 at ' + subAddr + ': ' + e);
    }
}
```

这种写法适合做动态观测：每个检测函数在进入和返回时都会打印日志，最终通过 `[DETECT]` 或 `[SKIP]` 输出当前检测分支是否激活。

### 5.4 通过返回值替换绕过检测

对于部分校验函数，脚本直接在 `onLeave` 阶段替换返回值。例如 `sub_16720`：

![image](https://bbs.kanxue.com/upload/attach/202605/1036360_4HHDYNTHQXT59B6.png)

```javascript
function hookSub16720Return666(base) {
    if (sub16720Hooked) {
        return;
    }

    const subAddr = base.add(SUB_16720_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                this.checkOff = args[0];
                this.checkLen = args[1].toInt32();
                log('sub_16720 entered at ' + subAddr + ', check_off = ' + this.checkOff + ', check_len = ' + this.checkLen);
            },
            onLeave(retval) {
                const original = retval.toInt32();
                retval.replace(ptr(666));
                log('sub_16720 retval original = ' + original + ', hook result = 666, check_off = ' + this.checkOff + ', check_len = ' + this.checkLen);
            }
        });

        sub16720Hooked = true;
        logInfo('hooked sub_16720 return patch at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_16720_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_16720 at ' + subAddr + ': ' + e);
    }
}
```

这里的重点不是固定值 `666` 本身，而是 **通过修改返回值改变上层分支判断结果**。

### 5.5 对线程创建或轮询检测入口写入 `RET`

脚本还对若干偏移直接写入 ARM64 `RET` 指令，使相关函数立即返回：

```javascript
const RET_PATCH_OFFSETS = [
    0x8CAC,
    0x19E0C,
    0x1C544,
    0x1B8D4,
    0x26E5C
];
```

对应 Patch 实现如下：

```javascript
function ret_64(addr) {
    try {
        Memory.protect(addr, 4, 'rwx');

        const writer = new Arm64Writer(addr);
        writer.putRet();
        writer.flush();
        writer.dispose();

        logPatch('patched RET at ' + addr);
        return true;
    } catch (e) {
        logError('failed to patch RET at ' + addr + ': ' + e);
        return false;
    }
}

function patchRetChecks(base) {
    if (retPatched) {
        return;
    }

    logPatch('patching RET offsets, base = ' + base);

    for (let i = 0; i < RET_PATCH_OFFSETS.length; i++) {
        const offset = RET_PATCH_OFFSETS[i];
        const addr = base.add(offset);

        logPatch('patching RET at offset 0x' + offset.toString(16) + ', addr = ' + addr);
        ret_64(addr);
    }

    retPatched = true;
}
```

这种方式适用于已经确认目标函数主要用于检测、线程创建或轮询校验的场景。

---

## 六、完整 Hook 脚本

下面是整理后的完整 Frida 脚本。脚本目标为 ARM64 环境下的 `libmsaoaidsec.so`，通过早期锚点安装 Hook，并输出各类检测分支状态。

```javascript
'use strict';

const TARGET_SO = 'libmsaoaidsec.so';
const INIT_ANCHOR_PROPERTY = 'ro.build.version.sdk';

const SUB_C830_OFFSET = 0xC830;
const SUB_95C8_OFFSET = 0x95C8;
const SUB_CA28_OFFSET = 0xCA28;
const SUB_CAA8_OFFSET = 0xCAA8;
const SUB_CAE8_OFFSET = 0xCAE8;
const SUB_CC64_OFFSET = 0xCC64;
const SUB_CEA4_OFFSET = 0xCEA4;
const SUB_CEE4_OFFSET = 0xCEE4;
const SUB_12D9C_OFFSET = 0x12D9C;
const SUB_16720_OFFSET = 0x16720;
const SUB_25A48_OFFSET = 0x25A48;

const MSG_FRIDA_CHECK = '进行 Frida / 注入痕迹检测';
const MSG_NO_FRIDA_CHECK = '不进行 Frida / 注入痕迹检测';
const MSG_ANTI_DEBUG_CHECK = '进行反调试、TracerPid、线程状态检测';
const MSG_NO_ANTI_DEBUG_CHECK = '不进行反调试、TracerPid、线程状态检测';
const MSG_ADB_CHECK = '进行 ADB / USB 调试环境检测';
const MSG_NO_ADB_CHECK = '不进行 ADB / USB 调试环境检测';
const MSG_CRC32_CHECK = '进行目标区域 CRC32 计算，并与预期 CRC32 值对比';
const MSG_NO_CRC32_CHECK = '不进行目标区域 CRC32 计算';
const MSG_POLLING_CRC_CHECK = '进行轮询代码 CRC 校验';
const MSG_NO_POLLING_CRC_CHECK = '不进行轮询代码 CRC 校验';
const MSG_MAGISK_ROOT_CHECK = '进行 Magisk / root 检测';
const MSG_NO_MAGISK_ROOT_CHECK = '不进行 Magisk / root 检测';
const MSG_NATIVE_ENV_CHECK = '进行 Native 层环境检测';
const MSG_NO_NATIVE_ENV_CHECK = '不进行 Native 层环境检测';
const MSG_CODE_CRC_APK_V1_CHECK = '进行代码 CRC / APK v1 签名校验';

const RET_PATCH_OFFSETS = [
    0x8CAC,
    0x19E0C,
    0x1C544,
    0x1B8D4,
    0x26E5C
];

let propHooked = false;
let retPatched = false;
let subC830Hooked = false;
let sub95C8Hooked = false;
let subCA28Hooked = false;
let subCAA8Hooked = false;
let subCAE8Hooked = false;
let subCC64Hooked = false;
let subCEA4Hooked = false;
let subCEE4Hooked = false;
let sub12D9CHooked = false;
let sub16720Hooked = false;
let sub25A48Hooked = false;

let lastSubCAA8Ret = null;
let lastSub12D9CRet = null;
let lastSubC830Ret = null;
let lastSub95C8Ret = null;

const COLOR = {
    reset: '\x1b[0m',
    dim: '\x1b[2m',
    red: '\x1b[31m',
    green: '\x1b[32m',
    yellow: '\x1b[33m',
    cyan: '\x1b[36m',
    bold: '\x1b[1m'
};

function colorize(color, message) {
    return color + message + COLOR.reset;
}

function log(message) {
    console.log('[hook] ' + message);
}

function logInfo(message) {
    console.log(colorize(COLOR.cyan, '[hook] ' + message));
}

function logDecision(active, message) {
    const color = active ? COLOR.bold + COLOR.yellow : COLOR.dim;
    const prefix = active ? '[DETECT] ' : '[SKIP] ';
    console.log(colorize(color, prefix + message));
}

function logPatch(message) {
    console.log(colorize(COLOR.green, '[patch] ' + message));
}

function logError(message) {
    console.error(colorize(COLOR.red, '[error] ' + message));
}

function ret_64(addr) {
    try {
        Memory.protect(addr, 4, 'rwx');

        const writer = new Arm64Writer(addr);
        writer.putRet();
        writer.flush();
        writer.dispose();

        logPatch('patched RET at ' + addr);
        return true;
    } catch (e) {
        logError('failed to patch RET at ' + addr + ': ' + e);
        return false;
    }
}

function patchRetChecks(base) {
    if (retPatched) {
        return;
    }

    logPatch('patching RET offsets, base = ' + base);

    for (let i = 0; i < RET_PATCH_OFFSETS.length; i++) {
        const offset = RET_PATCH_OFFSETS[i];
        const addr = base.add(offset);

        logPatch('patching RET at offset 0x' + offset.toString(16) + ', addr = ' + addr);
        ret_64(addr);
    }

    retPatched = true;
}

function logFridaTraceDecision(tag) {
    if (lastSubCAA8Ret === null || lastSub12D9CRet === null) {
        return;
    }

    const shouldCheck = lastSubCAA8Ret === 248 && !lastSub12D9CRet;
    log(tag + ': sub_CAA8() = ' + lastSubCAA8Ret + ', sub_12D9C() = ' + lastSub12D9CRet + ', condition (sub_CAA8() == 248 && !sub_12D9C()) => ' + shouldCheck);
    logDecision(shouldCheck, shouldCheck ? MSG_FRIDA_CHECK : MSG_NO_FRIDA_CHECK);
}

function logPollingCrcDecision(tag) {
    if (lastSubC830Ret === null || lastSub95C8Ret === null) {
        return;
    }

    const shouldCheck = lastSubC830Ret !== 1 || !!lastSub95C8Ret;
    log(tag + ': sub_C830() = ' + lastSubC830Ret + ', sub_95C8() = ' + lastSub95C8Ret + ', condition (sub_C830()!=1 || sub_95C8()) => ' + shouldCheck);
    logDecision(shouldCheck, shouldCheck ? MSG_POLLING_CRC_CHECK : MSG_NO_POLLING_CRC_CHECK);
}

function hookSubC830(base) {
    if (subC830Hooked) {
        return;
    }

    const subAddr = base.add(SUB_C830_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_C830 entered at ' + subAddr);
            },
            onLeave(retval) {
                lastSubC830Ret = retval.toInt32();
                log('sub_C830 retval int = ' + lastSubC830Ret + ', equals 1 => ' + (lastSubC830Ret === 1 ? 'YES' : 'NO'));
                logPollingCrcDecision('sub_C830.onLeave');
            }
        });

        subC830Hooked = true;
        logInfo('hooked sub_C830 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_C830_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_C830 at ' + subAddr + ': ' + e);
    }
}

function hookSub95C8(base) {
    if (sub95C8Hooked) {
        return;
    }

    const subAddr = base.add(SUB_95C8_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_95C8 entered at ' + subAddr);
            },
            onLeave(retval) {
                lastSub95C8Ret = retval.toInt32();
                log('sub_95C8 retval int = ' + lastSub95C8Ret + ', bool = ' + (!!lastSub95C8Ret));
                logPollingCrcDecision('sub_95C8.onLeave');
            }
        });

        sub95C8Hooked = true;
        logInfo('hooked sub_95C8 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_95C8_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_95C8 at ' + subAddr + ': ' + e);
    }
}

function hookSubCA28(base) {
    if (subCA28Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CA28_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CA28 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                log('sub_CA28 retval int = ' + ret + ', equals 167 => ' + (ret === 167 ? 'YES' : 'NO'));
                logDecision(ret === 167, ret === 167 ? MSG_ADB_CHECK : MSG_NO_ADB_CHECK);
            }
        });

        subCA28Hooked = true;
        logInfo('hooked sub_CA28 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CA28_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CA28 at ' + subAddr + ': ' + e);
    }
}

function hookSubCAA8(base) {
    if (subCAA8Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CAA8_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CAA8 entered at ' + subAddr);
            },
            onLeave(retval) {
                lastSubCAA8Ret = retval.toInt32();
                log('sub_CAA8 retval int = ' + lastSubCAA8Ret + ', equals 248 => ' + (lastSubCAA8Ret === 248 ? 'YES' : 'NO'));
                logFridaTraceDecision('sub_CAA8.onLeave');
            }
        });

        subCAA8Hooked = true;
        logInfo('hooked sub_CAA8 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CAA8_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CAA8 at ' + subAddr + ': ' + e);
    }
}

function hookSubCAE8(base) {
    if (subCAE8Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CAE8_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CAE8 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                log('sub_CAE8 retval int = ' + ret + ', equals 249 => ' + (ret === 249 ? 'YES' : 'NO'));
                logDecision(ret === 249, ret === 249 ? MSG_ANTI_DEBUG_CHECK : MSG_NO_ANTI_DEBUG_CHECK);
            }
        });

        subCAE8Hooked = true;
        logInfo('hooked sub_CAE8 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CAE8_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CAE8 at ' + subAddr + ': ' + e);
    }
}

function hookSubCC64(base) {
    if (subCC64Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CC64_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CC64 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                log('sub_CC64 retval int = ' + ret + ', equals 218 => ' + (ret === 218 ? 'YES' : 'NO'));
                logDecision(ret === 218, ret === 218 ? MSG_MAGISK_ROOT_CHECK : MSG_NO_MAGISK_ROOT_CHECK);
            }
        });

        subCC64Hooked = true;
        logInfo('hooked sub_CC64 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CC64_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CC64 at ' + subAddr + ': ' + e);
    }
}

function hookSubCEA4Return666(base) {
    if (subCEA4Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CEA4_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CEA4 entered at ' + subAddr);
            },
            onLeave(retval) {
                const original = retval.toInt32();
                retval.replace(ptr(666));
                log('sub_CEA4 retval original = ' + original + ', hook result = 666');
            }
        });

        subCEA4Hooked = true;
        logInfo('hooked sub_CEA4 return patch at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CEA4_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CEA4 at ' + subAddr + ': ' + e);
    }
}

function hookSubCEE4(base) {
    if (subCEE4Hooked) {
        return;
    }

    const subAddr = base.add(SUB_CEE4_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_CEE4 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                log('sub_CEE4 retval int = ' + ret + ', equals 203 => ' + (ret === 203 ? 'YES' : 'NO'));
                logDecision(ret === 203, ret === 203 ? MSG_CRC32_CHECK : MSG_NO_CRC32_CHECK);
            }
        });

        subCEE4Hooked = true;
        logInfo('hooked sub_CEE4 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_CEE4_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_CEE4 at ' + subAddr + ': ' + e);
    }
}

function hookSub12D9C(base) {
    if (sub12D9CHooked) {
        return;
    }

    const subAddr = base.add(SUB_12D9C_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_12D9C entered at ' + subAddr);
            },
            onLeave(retval) {
                const raw = retval.toInt32();
                lastSub12D9CRet = raw !== 0;
                log('sub_12D9C retval bool = ' + lastSub12D9CRet + ', raw int = ' + raw);
                logFridaTraceDecision('sub_12D9C.onLeave');
            }
        });

        sub12D9CHooked = true;
        logInfo('hooked sub_12D9C at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_12D9C_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_12D9C at ' + subAddr + ': ' + e);
    }
}

function hookSub25A48(base) {
    if (sub25A48Hooked) {
        return;
    }

    const subAddr = base.add(SUB_25A48_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                log('sub_25A48 entered at ' + subAddr);
            },
            onLeave(retval) {
                const ret = retval.toInt32();
                const shouldCheck = (ret & 1) === 0;

                log('sub_25A48 retval int = ' + ret + ', (retval & 1) == 0 => ' + shouldCheck);
                if (shouldCheck) {
                    logDecision(true, MSG_NATIVE_ENV_CHECK);
                    logDecision(true, MSG_CODE_CRC_APK_V1_CHECK);
                } else {
                    logDecision(false, MSG_NO_NATIVE_ENV_CHECK);
                }
            }
        });

        sub25A48Hooked = true;
        logInfo('hooked sub_25A48 at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_25A48_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_25A48 at ' + subAddr + ': ' + e);
    }
}

function hookSub16720Return666(base) {
    if (sub16720Hooked) {
        return;
    }

    const subAddr = base.add(SUB_16720_OFFSET);

    try {
        Interceptor.attach(subAddr, {
            onEnter(args) {
                this.checkOff = args[0];
                this.checkLen = args[1].toInt32();
                log('sub_16720 entered at ' + subAddr + ', check_off = ' + this.checkOff + ', check_len = ' + this.checkLen);
            },
            onLeave(retval) {
                const original = retval.toInt32();
                retval.replace(ptr(666));
                log('sub_16720 retval original = ' + original + ', hook result = 666, check_off = ' + this.checkOff + ', check_len = ' + this.checkLen);
            }
        });

        sub16720Hooked = true;
        logInfo('hooked sub_16720 return patch at ' + subAddr + ' (base ' + base + ' + 0x' + SUB_16720_OFFSET.toString(16) + ')');
    } catch (e) {
        logError('failed to hook sub_16720 at ' + subAddr + ': ' + e);
    }
}

function installTargetHooks(base) {
    hookSubC830(base);
    hookSub95C8(base);
    hookSubCA28(base);
    hookSubCAA8(base);
    hookSubCAE8(base);
    hookSubCC64(base);
    hookSubCEA4Return666(base);
    hookSubCEE4(base);
    hookSub12D9C(base);
    hookSub16720Return666(base);
    hookSub25A48(base);
    patchRetChecks(base);
}

function locateInitAnchor() {
    if (propHooked) {
        return;
    }

    const sysPropGet = Module.findExportByName(null, '__system_property_get');
    if (sysPropGet === null) {
        logError('__system_property_get not found');
        return;
    }

    Interceptor.attach(sysPropGet, {
        onEnter(args) {
            const namePtr = args[0];
            if (namePtr.isNull()) {
                return;
            }

            let name = null;
            try {
                name = namePtr.readCString();
            } catch (e) {
                return;
            }

            if (name === null || name.indexOf(INIT_ANCHOR_PROPERTY) === -1) {
                return;
            }

            if (retPatched) {
                return;
            }

            logInfo('__system_property_get("' + name + '", ' + args[1] + ') hit');

            const module = Process.findModuleByName(TARGET_SO);
            if (module === null) {
                logError(TARGET_SO + ' not found by Frida module query');
                return;
            }

            logInfo('found ' + TARGET_SO + ' base = ' + module.base + ', size = 0x' + module.size.toString(16));
            installTargetHooks(module.base);
        }
    });

    propHooked = true;
    logInfo('hooked __system_property_get at ' + sysPropGet);
}

function hookAndroidDlopenExt() {
    const androidDlopenExt = Module.findExportByName(null, 'android_dlopen_ext');
    if (androidDlopenExt === null) {
        logError('android_dlopen_ext not found');
        return;
    }

    Interceptor.attach(androidDlopenExt, {
        onEnter(args) {
            const pathPtr = args[0];
            if (pathPtr.isNull()) {
                return;
            }

            let path = null;
            try {
                path = pathPtr.readCString();
            } catch (e) {
                return;
            }

            if (path.indexOf(TARGET_SO) === -1) {
                return;
            }

            logInfo('detected loading of ' + path);
            locateInitAnchor();
        }
    });

    logInfo('hooked android_dlopen_ext at ' + androidDlopenExt);
}

setImmediate(function () {
    logInfo('script loaded');
    hookAndroidDlopenExt();
});
```

---

## 七、运行方式与效果验证

使用 Frida spawn 模式启动目标 App，并加载 Hook 脚本：

```
frida -U -f com.xingin.xhs -l hook.js
```

示例输出如下：

```
Spawning `com.xingin.xhs`...
[hook] script loaded
[hook] hooked android_dlopen_ext at 0x7459d37100
Spawned `com.xingin.xhs`. Resuming main thread!
[hook] detected loading of /data/app/.../lib/arm64/libmsaoaidsec.so
[hook] hooked __system_property_get at 0x744f7475f0
[hook] __system_property_get("ro.build.version.sdk", 0x7309710790) hit
[hook] found libmsaoaidsec.so base = 0x72cd001000, size = 0xaa000
[hook] hooked sub_C830 at 0x72cd00d830 (base 0x72cd001000 + 0xc830)
[hook] hooked sub_95C8 at 0x72cd00a5c8 (base 0x72cd001000 + 0x95c8)
[hook] hooked sub_CA28 at 0x72cd00da28 (base 0x72cd001000 + 0xca28)
[hook] hooked sub_CAA8 at 0x72cd00daa8 (base 0x72cd001000 + 0xcaa8)
[hook] hooked sub_CAE8 at 0x72cd00dae8 (base 0x72cd001000 + 0xcae8)
[hook] hooked sub_CC64 at 0x72cd00dc64 (base 0x72cd001000 + 0xcc64)
[hook] hooked sub_CEA4 return patch at 0x72cd00dea4 (base 0x72cd001000 + 0xcea4)
[hook] hooked sub_CEE4 at 0x72cd00dee4 (base 0x72cd001000 + 0xcee4)
[hook] hooked sub_12D9C at 0x72cd013d9c (base 0x72cd001000 + 0x12d9c)
[hook] hooked sub_16720 return patch at 0x72cd017720 (base 0x72cd001000 + 0x16720)
[hook] hooked sub_25A48 at 0x72cd026a48 (base 0x72cd001000 + 0x25a48)
```

继续观察 Patch 结果：

```
[patch] patching RET offsets, base = 0x72cd001000
[patch] patching RET at offset 0x8cac, addr = 0x72cd009cac
[patch] patched RET at 0x72cd009cac
[patch] patching RET at offset 0x19e0c, addr = 0x72cd01ae0c
[patch] patched RET at 0x72cd01ae0c
[patch] patching RET at offset 0x1c544, addr = 0x72cd01d544
[patch] patched RET at 0x72cd01d544
[patch] patching RET at offset 0x1b8d4, addr = 0x72cd01c8d4
[patch] patched RET at 0x72cd01c8d4
[patch] patching RET at offset 0x26e5c, addr = 0x72cd027e5c
[patch] patched RET at 0x72cd027e5c
```

检测分支输出示例：

```
[hook] sub_CAE8 retval int = 249, equals 249 => YES
[DETECT] 进行反调试、TracerPid、线程状态检测

[hook] sub_CA28 retval int = 0, equals 167 => NO
[SKIP] 不进行 ADB / USB 调试环境检测

[hook] sub_CEE4 retval int = 0, equals 203 => NO
[SKIP] 不进行目标区域 CRC32 计算

[hook] sub_95C8.onLeave: sub_C830() = 1, sub_95C8() = 0, condition (sub_C830()!=1 || sub_95C8()) => false
[SKIP] 不进行轮询代码 CRC 校验
```

![运行效果示例](https://bbs.kanxue.com/upload/attach/202605/1036360_DR2CY55VR6B2RGX.png)

从输出可以确认：

- `libmsaoaidsec.so` 的加载事件被成功捕获。
- `__system_property_get("ro.build.version.sdk", ...)` 早期锚点命中。
- 目标 SO 基址被正确获取。
- 多个 `base + offset` Hook 成功安装。
- 线程或轮询相关入口已经被写入 `RET`。
- 日志能够清晰区分 `[DETECT]` 与 `[SKIP]` 分支，便于后续分析。

---

## 八、总结

本文围绕 `libmsaoaidsec.so` 的早期初始化检测，整理了一套可复用的 Frida 分析思路：

1. **Hook** **`android_dlopen_ext.onEnter`** **捕获目标 SO 加载事件**。
2. **利用** **`.init_proc`** **中的外部导入函数** **`__system_property_get`** **作为早期锚点**。
3. **在读取** **`ro.build.version.sdk`** **时获取目标 SO 基址**。
4. **基于** **`base + offset`** **监测关键检测函数返回值**。
5. **结合返回值替换与 ARM64** **`RET`** **Patch 绕过特定检测入口**。

这类分析的关键不在于某一个固定偏移，而在于方法论：**先解决 Hook 时机，再定位初始化锚点，最后围绕检测函数建立可观测、可验证、可迁移的动态分析链路**。

‍

---

# 回复

## 回复 by 宛枫 (#2)

*2026-5-30 21:40*

感谢分享

## 回复 by tonykros (#3)

*2026-5-30 22:00*

666

## 回复 by xianhuimin (#4)

*2026-5-31 00:19*

感谢分享

## 回复 by wx_Huber Barrientos (#5)

*2026-5-31 02:30*

666

## 回复 by mb_depeeceu (#6)

*2026-5-31 06:50*

不错的

## 回复 by mb_zoyhhbnr (#7)

*2026-5-31 07:57*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_北极星_493 (#8)

*2026-5-31 08:12*

看看

## 回复 by mb_gxnzvoal (#9)

*2026-5-31 11:20*

感谢分享

## 回复 by 天路 (#10)

*2026-5-31 18:41*

111111

## 回复 by cpannn (#11)

*2026-5-31 23:52*

学习

## 回复 by mb_jhohnbzu (#12)

*2026-6-1 09:48*

666

## 回复 by 4Chan (#13)

*2026-6-1 13:50*

学习一下

## 回复 by git_14248bibinocode (#14)

*2026-6-1 14:02*

学习一下

## 回复 by gannicusliu (#15)

*2026-6-1 14:50*

学习一下

## 回复 by iBa0 (#16)

*2026-6-1 16:41*

123

## 回复 by git_74197luban110 (#17)

*2026-6-1 16:50*

666

## 回复 by MaYil (#18)

*2026-6-1 16:57*

感谢分享

## 回复 by 海山 (#19)

*2026-6-2 09:04*

学习

## 回复 by tigericon (#20)

*2026-6-2 14:17*

66

## 回复 by SomeMx (#21)

*2026-6-2 17:08*

学习一下

## 回复 by 086Love (#22)

*2026-6-2 17:25*

学习

## 回复 by Imxz (#23)

*2026-6-2 22:29*

kkb

## 回复 by shuangmou (#24)

*2026-6-3 15:55*

感谢分享

## 回复 by mb_elytixax (#25)

*2026-6-4 14:02*

感谢分享

## 回复 by snowflake911 (#26)

*2026-6-4 15:27*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by ROSE0 (#27)

*2026-6-4 15:59*

学习

## 回复 by mb_czqyztmr (#28)

*2026-6-5 10:35*

1

## 回复 by mb_elqwyvnm (#29)

*2026-6-5 14:08*

学习一下

## 回复 by mb_xpkadaio (#30)

*2026-6-5 14:11*

111

## 回复 by 黄石 (#31)

*2026-6-5 17:25*

666

## 回复 by git_89049pencilbsp (#32)

*2026-6-5 19:09*

感谢分享

## 回复 by bedaway (#33)

*2026-6-6 00:37*

666

## 回复 by Mr.ChenX (#34)

*2026-6-6 11:07*

666

## 回复 by issio (#35)

*2026-6-6 19:59*

感谢分析

## 回复 by Little_Z (#36)

*2026-6-6 23:33*

感谢分享

## 回复 by Arcue1d (#37)

*2026-6-7 10:52*

感谢分享

## 回复 by ldehua (#38)

*2026-6-7 19:05*

感谢分享

## 回复 by mb_dcjxxhsk (#39)

*2026-6-7 22:09*

666

## 回复 by git_87237minhdanhsc (#40)

*2026-6-7 23:59*

1

## 回复 by gzzchh (#41)

*2026-6-8 02:45*

非常支持你的观点！

## 回复 by mb_xihakijc (#42)

*2026-6-8 03:18*

感谢分享

## 回复 by yangshuang (#43)

*2026-6-8 14:52*

感谢分享

## 回复 by lookaside (#44)

*2026-6-9 14:10*

111

## 回复 by mb_rxgpbdxs (#45)

*2026-6-9 22:24*

感谢分享

## 回复 by 五彩斑斓的黑 (#46)

*2026-6-10 23:08*

666

## 回复 by mb_lhxrckiu (#47)

*2026-6-11 15:26*

11111

## 回复 by 钱钱钱￥ (#48)

*2026-6-12 09:41*

感谢分享

## 回复 by DevilHunter (#49)

*2026-6-12 17:53*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ohctzvjg (#50)

*2026-6-12 18:11*

感谢分享

## 回复 by mb_yfxezfnn (#51)

*2026-6-14 06:49*

666

## 回复 by zzhone (#52)

*2026-6-14 20:27*

感谢分享

## 回复 by HangNam (#53)

*2026-6-15 01:43*

Good Work

## 回复 by mb_jegknedl (#54)

*2026-6-15 03:16*

看看学习

## 回复 by mb_gjhmacqd (#55)

*2026-6-15 14:54*

666

## 回复 by bhhqxhq (#56)

*2026-6-16 09:40*

学习

## 回复 by 鱼鱼鱼鱼鱼 (#57)

*2026-6-16 10:36*

感谢分享

## 回复 by mb_xjdhrmck (#58)

*2026-6-16 11:07*

6666

## 回复 by Kevin_ZZZ (#59)

*2026-6-16 11:17*

学习一下

## 回复 by mb_tfqctboq (#60)

*2026-6-16 18:21*

感谢分享

## 回复 by 中文fjja (#61)

*2026-6-17 11:10*

感谢分享

## 回复 by mb_audxeeaj (#62)

*2026-6-17 11:38*

感谢分享

## 回复 by veluboii (#63)

*2026-6-17 23:08*

666

## 回复 by Zireael (#64)

*2026-6-18 02:24*

感谢分享

## 回复 by 孤江雪 (#65)

*2026-6-19 15:23*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_GaoH (#66)

*2026-6-19 16:57*

和那帮

## 回复 by mb_cpsiqdds (#68)

*2026-6-20 21:03*

学

## 回复 by GEKEZYX (#69)

*2026-6-21 00:58*

666

## 回复 by 4ak5ra (#70)

*2026-6-21 15:40*

感谢分享

## 回复 by mb_awqgymxv (#71)

*2026-6-22 19:27*

感谢

## 回复 by mb_awqgymxv (#72)

*2026-6-22 20:03*

一执行脚本APP就自动退出了

## 回复 by mb_cedxuhcp (#73)

*2026-6-22 22:41*

感谢分享

## 回复 by 张恒_884729 (#74)

*2026-6-26 03:35*

666666

## 回复 by ulong9527 (#75)

*2026-6-26 09:42*

感谢分享，学习一下

## 回复 by 十年一梦. (#76)

*2026-6-26 15:08*

学习到了

## 回复 by wx_DWJ (#77)

*2026-6-26 16:29*

666

## 回复 by Gypsophilazj (#78)

*2026-6-26 17:09*

学习

## 回复 by wx_wyx (#79)

*2026-6-26 18:23*

感谢分享

## 回复 by bygrand (#80)

*2026-6-26 20:43*

强强

## 回复 by mb_dlljjfcf (#81)

*2026-6-26 20:57*

历害大神

## 回复 by 故人叹 (#82)

*2026-6-26 21:33*

感谢感谢

## 回复 by 信心风暴 (#83)

*2026-6-27 06:59*

Mark

## 回复 by mb_qimctavn (#84)

*2026-6-27 07:06*

6

## 回复 by mb_ajxntfzc (#85)

*2026-6-28 03:01*

6666

## 回复 by huangbof (#86)

*2026-6-28 04:08*

感谢分享

## 回复 by mb_nwbitjng (#87)

*2026-6-28 11:54*

66

## 回复 by 逆向小龙 (#88)

*2026-6-30 16:04*

111

## 回复 by mb_uvyukvot (#89)

*2026-6-30 16:23*

666

## 回复 by mb_zfnetraa (#90)

*2026-6-30 19:49*

感谢分享

## 回复 by guardia (#91)

*2026-7-1 00:42*

666

## 回复 by ALick43 (#92)

*2026-7-1 18:42*

感谢分享！

## 回复 by mb_dswynejo (#93)

*2026-7-1 20:11*

感谢分享

## 回复 by guigu001 (#94)

*2026-7-1 22:23*

tql

## 回复 by 晨曦遇晓 (#95)

*2026-7-2 10:22*

666

## 回复 by xiaoxuya (#96)

*2026-7-3 04:36*

感谢分享 学习一下

## 回复 by wx_coddvccwyh (#97)

*2026-7-4 00:43*

6666

## 回复 by git_42339srkdragon (#98)

*2026-7-4 17:36*

6666

## 回复 by wx_飞_847 (#99)

*2026-7-4 18:17*

感谢分享

## 回复 by AAA撒拉嘿 (#100)

*2026-7-4 18:45*

感谢分享

## 回复 by mb_kgneopde (#101)

*2026-7-6 15:20*

556

## 回复 by wx_断浪天涯 (#102)

*2026-7-6 17:15*

感谢分享

## 回复 by xiaohuayin (#103)

*2026-7-6 17:19*

感谢分享

## 回复 by mb_ulozvsrv (#104)

*2026-7-6 17:43*

666，学习学习

## 回复 by sffool (#105)

*2026-7-7 11:01*

感谢分享

## 回复 by mb_ysikfhxt (#106)

*2026-7-7 11:14*

111

## 回复 by mb_cbgtaveo (#107)

*2026-7-7 14:47*

666666666

## 回复 by wx_Riham、 (#108)

*2026-7-9 09:49*

666

## 回复 by wx_kx92911 (#109)

*2026-7-9 10:04*

感谢分析

## 回复 by mb_ugnawvja (#110)

*2026-7-9 12:32*

学习一下

## 回复 by 小尘0000 (#111)

*2026-7-9 15:06*

66

## 回复 by wx_窒息 (#112)

*2026-7-10 00:42*

666

## 回复 by ldz666 (#113)

*2026-7-13 15:51*

666

## 回复 by mb_degalzhb (#114)

*2026-7-15 14:34*

666

## 回复 by simpleness (#115)

*2026-7-16 17:33*

6

## 回复 by mb_twbjvgyf (#116)

*2026-7-16 20:50*

1

## 回复 by wx_杨杰_424 (#117)

*2026-7-17 08:14*

tql

## 回复 by mb_qztkkwxt (#118)

*2026-7-17 10:01*

666

## 回复 by mb_qkfqehfw (#119)

*2026-7-19 03:01*

学习

## 回复 by _雨化田 (#120)

*2026-7-19 08:45*

感谢分享

## 回复 by 豆腐君 (#121)

*2026-7-19 14:07*

666

## 回复 by 祝今朝 (#122)

*2026-7-19 20:03*

111

## 回复 by mb_nkjfyhkg (#123)

*2026-7-20 03:06*

mark

## 回复 by mb_ghhwqgrd (#124)

*2026-7-20 22:26*

厉害！！！

## 回复 by git_20668ternary88 (#125)

*2026-7-21 10:41*

1

## 回复 by mb_rxgpbdxs (#126)

*2026-7-21 16:15*

1

## 回复 by 尘埃. (#127)

*2026-7-21 16:30*

6

## 回复 by 学计算机睡觉 (#128)

*2026-7-21 16:38*

666

## 回复 by 黑屏 (#129)

*2026-7-21 16:59*

66

## 回复 by 一栋奥特曼 (#130)

*2026-7-22 17:29*

6666

## 回复 by mb_dmkmqsyg (#131)

*2026-7-23 15:45*

1

## 回复 by 珍惜Any (#132)

*2026-7-23 21:01*

111

## 回复 by ShriyGo (#133)

*2026-7-23 21:22*

666

## 回复 by mb_qltrlkcu (#134)

*2026-7-23 22:48*

666

## 回复 by 猜我是谁_610897 (#135)

感谢分享

## 回复 by mb_vcuiorbn (#136)

学习一下

## 回复 by mb_akzdpbgl (#137)

感谢分享

## 回复 by scllqk (#138)

学习

## 回复 by mb_irhdtnzm (#139)

1

## 回复 by v5w7crq3 (#140)

666

## 回复 by kingking888 (#141)

666

## 回复 by mb_opdtzncs (#142)

感谢分享
