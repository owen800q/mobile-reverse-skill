---
title: '[原创]从 Frida 到 unidbg：某蜂窝 zzz 参数逆向分析'
url: https://bbs.kanxue.com/thread-291077.htm
tid: 291077
author: Mengz3
date: '2026-05-01'
tags: [Android安全, 原创, 逆向分析, 协议分析, 脱壳反混淆, HOOK注入]
crawled_at: '2026-07-31T13:53:43+08:00'
replies: 6
---

（文章末尾有APK下载地址）

## 1. 前言

这段时间看了篇大佬的文章，有关某蜂窝APP的参数解析，想着自己也做一下是不是这回事。
所以这次只聚焦一件事：把 `zzzghostsigh` 这个参数从 Java 层一路追到 Native，再把算法用 `unidbg + Python` 跑通并复现出来。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_H4AXJ979E7FXEQ9.webp)

---

## 2. 参数调用链

先给结论链路，后面所有分析都围绕它展开：

```
com.mfw.melon.http.c.generateRealUrl()

  -> com.mfw.core.login.util.SecurityTools.appendGhostSighParams(java.util.TreeMap, java.lang.String)

  -> com.mfw.core.login.util.SecurityTools.ghostSigh(java.lang.String)

  -> kh.b.b(android.content.Context, java.lang.String)

  -> com.mfw.tnative.AuthorizeHelper.c(android.content.Context, java.lang.String)

  -> com.mfw.tnative.AuthorizeHelper.xPreAuthencode(android.content.Context, java.lang.String, java.lang.String)

  -> native 层

  -> libmfw.so: 0x396c8

  -> JNI_OnLoad()

  -> loc_3DEC4

  -> sub_3E1D0
```

Java 层中，通过手机验证码登录，追到`com.mfw.melon.http.c.generateRealUrl()`获取到真实上传地址
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_YUEMCCQSTJDHHUV.webp)
这里 参数`zzzghostsigh`主要靠两个点确认：
`SecurityTools.appendGhostSighParams(TreeMap, String)`，以及 `kh.b.b(Context, String) -> AuthorizeHelper.c(...) -> xPreAuthencode(...)`。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_PVYKGD9TAAQY237.webp)
其中 `appendGhostSighParams` 的 Hook 日志已经能证明两件事：
第一，`zzzghostsigh` 是客户端本地追加的；
第二，它的输入不是单字段，而是规范化请求串 `HTTP_METHOD & encoded_url & encoded_sorted_params`。
换句话说，这个参数本质上是对完整请求串做的一层本地摘要。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_4JSHZWQVSNUEMR5.webp)
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_HFBDBD8S5MT4RKN.webp)
也可以通过获取手机抓包流量，也可以确认认证请求中带有`zzzghostsigh`参数

hook `appendGhostSighParams`代码：

```javascript
 var appendGhostSighParams = SecurityTools.appendGhostSighParams.overload('java.util.TreeMap', 'java.lang.String');
    appendGhostSighParams.implementation = function (treeMap, str) {
        var beforeMap = '';
        var afterMap = '';
        var result = '';
        try {
            beforeMap = treeMap ? treeMap.toString() : 'null';
        } catch (e) {
            beforeMap = '<TreeMap toString error: ' + e + '>';
        }
        result = appendGhostSighParams.call(this, treeMap, str);
        try {
            afterMap = treeMap ? treeMap.toString() : 'null';
        } catch (e) {
            afterMap = '<TreeMap toString error: ' + e + '>';
        }

        console.log('\n========== appendGhostSighParams ==========');
        console.log('调用Class   : com.mfw.core.login.util.SecurityTools');
        console.log('原始TreeMap : ' + beforeMap);
        console.log('更新后Map   : ' + afterMap);
        console.log('===========================================\n');
        return result;
```

接着顺着这条链往下追，可以追到：`com.mfw.tnative.AuthorizeHelper.xPreAuthencode(android.content.Context, java.lang.String, java.lang.String)`是生成`zzzghostsigh`参数的Native层入口。
不放心可以尝试hook一下：

```javascript
var xPreAuthencode = AuthorizeHelper.xPreAuthencode.overload('android.content.Context', 'java.lang.String', 'java.lang.String');
    xPreAuthencode.implementation = function (context, str, str2) {
        var pkg = '';
        try {
            pkg = context ? context.getPackageName() : 'null';
        } catch (e) {
            pkg = '<getPackageName error: ' + e + '>';
        }
        var result = xPreAuthencode.call(this, context, str, str2);

        console.log('\n========== AuthorizeHelper.xPreAuthencode ==========');
        console.log('contextPkg  : ' + pkg);
        console.log('arg1(str)   : ' + str);
        console.log('arg2(str2)  : ' + str2);
        console.log('result      : ' + result);
        console.log('===================================================\n');
        return result;
    };
    console.log('[+] Hooked com.mfw.tnative.AuthorizeHelper.xPreAuthencode(Context, String, String)');
```

##  ![image](https://bbs.kanxue.com/upload/attach/202605/962430_UUC7D3EZ837QXM9.webp)

## 3. Native 入口：`xPreAuthencode @ 0x396c8`

这几个 Native 方法不是显式 `Java_*` 导出，而是在 `JNI_OnLoad` 里动态注册。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_VEFDGYTR2257QY4.webp)
确认到的注册表如下：
`xPreAuthencode -> 0x396c8`、`xAuthencode -> 0x3998c`、`signEventData -> 0x39d84`、`signatureChecked -> 0x3a1c8`。
其中和 `zzzghostsigh` 对应的就是：`xPreAuthencode @ 0x396c8`
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_4HXMWZZPUDZRY3G.webp)
这一步把 Java 链真正钉到了 Native 偏移。
进入sub_396C8查看：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_MXKERV3EG6MKQWM.webp)
发现调用了sub_3C9C4。进入查看，发现此函数是判断红框这几个函数是否加载进来了，没加载就会走“Illegal signature”输出
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_H9GVS2FFW92UMJ3.webp)
细看了一会发现没有找到核心加密代码，下一步跑unidbg，跟一下trace，看看有什么发现

---

## 4. 用 unidbg 把 `xPreAuthencode` 跑起来

这一部分是全文最关键的工程步骤，因为一旦能脱离 App 跑起来，后面的 trace、断点和 Python 复现才有意义。
代码：

```java
package com.mfw;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Emulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.HookStatus;
import com.github.unidbg.hook.ReplaceCallback;
import com.github.unidbg.hook.hookzz.Dobby;
import com.github.unidbg.hook.hookzz.IHookZz;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.DalvikModule;
import com.github.unidbg.linux.android.dvm.DvmClass;
import com.github.unidbg.linux.android.dvm.DvmObject;
import com.github.unidbg.linux.android.dvm.StringObject;
import com.github.unidbg.linux.android.dvm.VM;
import com.github.unidbg.linux.android.dvm.jni.ProxyClassFactory;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.arm.backend.Backend;
import com.github.unidbg.arm.context.RegisterContext;
import com.github.unidbg.debugger.BreakPointCallback;
import com.github.unidbg.utils.Inspector;
import unicorn.Arm64Const;

import java.io.FileNotFoundException;
import java.io.PrintStream;
import java.io.File;
import java.io.IOException;

public class zzzghostsigh {

    // 目标 App 包名。xPreAuthencode 的第三个业务参数最终就是这个包名字符串。
    private static final String APK_PACKAGE = "com.mfw.roadbook";

    // IDA 中确认的前置校验函数 sub_3C9C4 偏移。
    // 第一版先直接绕过它，只验证 xPreAuthencode 主链。
    private static final long SUB_3C9C4_OFFSET = 0x3C9C4L;

    // loc_3DEC4 内部进一步调用的压缩核心地址。
    // 第二阶段在这里观察 X0 / X1 的真实入参。
    private static final long SHA1_CORE_OFFSET = 0x3E1D0L;

    // 你已经放到 unidbg 测试资源目录下的 libmfw.so 路径。
    private static final String LIB_PATH =
            "unidbg-android/src/test/resources/example_binaries/arm64-v8a/libmfw.so";

    // AuthorizeHelper 实例 native 方法签名。
    // Java 层声明为：private native String xPreAuthencode(Context context, String str, String str2)
    private static final String X_PRE_AUTH_SIGNATURE =
            "xPreAuthencode(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;";

    private static final String SIMPLE_CANONICAL_STR = "123456";

    private final AndroidEmulator emulator;
    private final VM vm;
    private final Module module;
    private final DvmClass authorizeHelperClass;
    private final DvmClass contextClass;

    public zzzghostsigh() {
        // 按当前 IDA/so 情况固定走 64 位。
        // libmfw.so 当前分析目标是 arm64-v8a 版本。
        // trace 模式不要挂 DynarmicFactory。
        // DynarmicBackend 不支持 traceCode 依赖的 hook_add_new。
        emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName(APK_PACKAGE)
                .build();

        // 设置 Android 系统库解析器，API 23 是 unidbg 常见兼容档位。
        Memory memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));

        // 创建 Dalvik VM，并开启 ProxyClassFactory。
        // 这样后面传 String、Context 这类对象会更顺手。
        vm = emulator.createDalvikVM();
        vm.setDvmClassFactory(new ProxyClassFactory());

        // 设置是否输出详细的JNI调用日志
        vm.setVerbose(true);

        // 只加载目标 so，不自动执行 JNI_OnLoad，保持流程可控。
        DalvikModule dm = vm.loadLibrary(new File(LIB_PATH), false);

        // -----------以上都是比较固定格式--------------

        // 手动执行 JNI_OnLoad，这一步会触发 RegisterNatives，
        // 把 xPreAuthencode / xAuthencode / signEventData / signatureChecked 都注册进 VM。
        dm.callJNI_OnLoad(emulator);
        module = dm.getModule();

        // 解析 Java 层对应的类。
        // 这里我们只用最小链：AuthorizeHelper + Context。
        authorizeHelperClass = vm.resolveClass("com/mfw/tnative/AuthorizeHelper");
        contextClass = vm.resolveClass("android/content/Context");

        // 安装前置校验绕过逻辑。
        installSub3C9C4Bypass();
    }

    // 绕过 sub_3C9C4 判断
    private void installSub3C9C4Bypass() {
        // 让 sub_3C9C4 恒为真。
        IHookZz dobby = Dobby.getInstance(emulator);
        dobby.replace(module.base + SUB_3C9C4_OFFSET, new ReplaceCallback() {
            @Override
            public HookStatus onCall(Emulator<?> emulator, long originFunction) {
                // 如果命中这里，说明 native 的前置签名校验已经被走到了。
                // 直接返回 1，让 xPreAuthencode 继续往 loc_3DEC4 / 0x3E1D0 主摘要链走。
                System.out.printf("[*] bypass sub_3C9C4 at 0x%x%n", module.base + SUB_3C9C4_OFFSET);
                return HookStatus.LR(emulator, 1);
            }
        }, true);
    }

    private void destroy() throws IOException {
        // 关闭 emulator，释放 native/VM 资源。
        emulator.close();
    }

    public static void main(String[] args) throws Exception {
        zzzghostsigh test = new zzzghostsigh();
        try {
            test.runSimpleExample();
            // test.runRealExample();
        } finally {
            test.destroy();
        }
    }
}
```

先绕过 `sub_3C9C4`

```java
    // 绕过 sub_3C9C4 判断
    private void installSub3C9C4Bypass() {
        // 让 sub_3C9C4 恒为真。
        IHookZz dobby = Dobby.getInstance(emulator);
        dobby.replace(module.base + SUB_3C9C4_OFFSET, new ReplaceCallback() {
            @Override
            public HookStatus onCall(Emulator<?> emulator, long originFunction) {
                // 如果命中这里，说明 native 的前置签名校验已经被走到了。
                // 直接返回 1，让 xPreAuthencode 继续往 loc_3DEC4 / 0x3E1D0 主摘要链走。
                System.out.printf("[*] bypass sub_3C9C4 at 0x%x%n", module.base + SUB_3C9C4_OFFSET);
                return HookStatus.LR(emulator, 1);
            }
        }, true);
    }
```

原因很明确：`sub_3C9C4` 是前置签名 / 环境校验门，它不是 `zzzghostsigh` 的主算法本体。

输入先用 `"123456"`
为了先验证链路，没有一上来就喂真实长串，而是直接调用：

```java
xPreAuthencode(context, "123456", "com.mfw.roadbook")
```

得到的结果是：

```
2f45b7dd81d48343c79ddbc14cddb756d7353190
```

跑一下
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_U5EE5SVVEPWAK6W.webp)
成功跑通
接下来trace一下，看经过哪些函数

```java
// 把 native 执行路径完整记录下来
private void enableTrace() {
    try {
        File traceFile = new File("mfw.trace.txt");
        PrintStream printStream = new PrintStream(traceFile);
        emulator.traceCode(module.base, module.base + module.size).setRedirect(printStream);
        System.out.println("[*] trace file: " + traceFile.getAbsolutePath());
    } catch (FileNotFoundException e) {
        throw new RuntimeException(e);
    }
}
```

发现先进入sub_3C9C4
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_3E7GZSTHT6CP2CY.webp)
然后进入了loc_3DEC4
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_GP9G6BAVP8Q8S6X.webp)
最后进入了sub_3E1D0
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_C7JZBVFUZV6FEGE.webp)
含义分别是：`0x396c8` 是 `xPreAuthencode` 主入口，`0x3DEC4` 负责 padding、上下文初始化和调用压缩核心，`0x3E1D0` 才是真正的压缩核心。

查看sub_3E1D0代码发现sha1特征值：

```python
 H0 = 0x67452301
 H1 = 0xEFCDAB89
 H2 = 0x98BADCFE
 H3 = 0x5E4A1F7C  // 与标准sha1不同
 H4 = 0x10325476  // 与标准sha1不同
```

加上代码特征，怀疑是变种sha1

---

## 5. 为什么是魔改 SHA-1

为了确定 `sub_3E1D0` 的性质，在 `0x3E1D0` 下断点，打印了 `X0 / X1`。

```java
private void hookSha1CoreInput() {
    // 这里重点看两个寄存器：
    // X0：更像 state / 5 个魔数所在结构
    // X1：更像输入块或消息调度块
    emulator.attach().addBreakPoint(module.base + SHA1_CORE_OFFSET, new BreakPointCallback() {
        @Override
        public boolean onHit(Emulator<?> emulator, long address) {
            Backend backend = emulator.getBackend();
            RegisterContext context = emulator.getContext();

            long x0 = backend.reg_read(Arm64Const.UC_ARM64_REG_X0).longValue();
            long x1 = backend.reg_read(Arm64Const.UC_ARM64_REG_X1).longValue();

            byte[] x0Bytes = context.getPointerArg(0).getByteArray(0, 0x100);
            byte[] x1Bytes = context.getPointerArg(1).getByteArray(0, 0x100);

            System.out.printf("[*] hit 0x%x, x0=0x%x, x1=0x%x%n", address, x0, x1);
            Inspector.inspect(x0Bytes, "0x3E1D0 X0 state");
            Inspector.inspect(x1Bytes, "0x3E1D0 X1 block");
            return true;
        }
    });
}
```

### 5.1 `X1`：标准哈希块

`X1` 的内容是 `"123456"`、`0x80`、补零以及末尾 bit length = `0x30`，这就是标准哈希 padding 块。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_464Q7WDHEUVB7FW.webp)

### 5.2 `X0`：5 个初始 state

`X0` 前 20 字节是：`0x67452301`、`0xEFCDAB89`、`0x98BADCFE`、`0x5E4A1F7C`、`0x10325476`。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_SU62BNNT93333M3.webp)
它不是可逆加密，而是摘要压缩函数。

### 5.3 和标准 SHA-1 的差异

仔细查看sub_3E1D0代码和trace.txt输出，发现它保留了很多 SHA-1 特征：
512-bit block、80 轮、20-byte digest / 40 hex、`rol5 / rol30`，以及四组常量 `0x5A827999`、`0x6ED9EBA1`、`0x8F1BBCDC`、`0xCA62C1D6`。
但它又不是标准 SHA-1，原因有四点：
1）初始 `state` 不标准；
2）轮分段不标准，实际是 `0..15 -> Ch + K0`、`16..19 -> Xor + K1`、`20..39 -> Maj + K2`、`40..59 -> Ch + K0`、`60..79 -> Xor + K3`；
3）`W[16+]` 扩展不是标准公式；
4）尾部 add-back 也不是标准 `H0..H4 += A..E`。

---

## 7. python逐轮对齐到完全复现

为了验证确实理解了 Native 逻辑，我最后又写了一份 Python 复现脚本。

### 7.1 先用标准思路搭脚手架

第一版做的事情很简单：标准 padding、用 trace 里的 5 个初始 `state`、每轮打印 `temp`。
发现前15轮 temp值全都相同，到了16轮以后全部不同了
仔细查看sub_3E1D0代码：发现从16轮开始K变了
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_XCKRRY23B2BHDXG.webp)

### 7.2 再和 trace 逐轮比

后面的工作基本就是一轮轮对齐。关键分叉点主要有：`round 16`、`round 20`、`round 40` 和最后的 `round 79`。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_A9TR6WYTSS5UU7D.webp)

### 7.3 最后的尾部映射

发现最后79和输出也做了魔改，把尾部回写改成 Native 的映射：

```python
H0 = old_H0 + temp79
H1 = old_H1 + temp78
H2 = old_H2 + rol30(temp76)
H3 = old_H3 + rol30(temp77)
H4 = old_H4 + rol30(temp75)
```

### 7.4 最终结果

现在已经能做到：`round 0..79` 全部与 trace 对齐，关键尾部是 `round 77 = ba4e5f6b`、`round 78 = 9206d7ba`、`round 79 = 2f45b7dd`，最终 digest 为 `2f45b7dd81d48343c79ddbc14cddb756d7353190`。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_JXXUJCUBHBVJJWB.webp)

完整的复现代码
sha1.py:

```python
import struct

def rol32(x, n):
    return ((x << n) | (x >> (32 - n))) & 0xffffffff

def pad_message(data: bytes) -> bytes:
    bit_len = len(data) * 8
    data += b"\x80"
    while (len(data) % 64) != 56:
        data += b"\x00"
    data += struct.pack(">Q", bit_len)
    return data

def sha1_temp_trace(data: bytes, h0, h1, h2, h3, h4):
    data = pad_message(data)

    for block_index in range(0, len(data), 64):
        block = data[block_index:block_index + 64]

        w = list(struct.unpack(">16I", block))
        for t in range(16, 80):
            w.append(rol32(w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16], 1))

        old_h0, old_h1, old_h2, old_h3, old_h4 = h0, h1, h2, h3, h4
        a, b, c, d, e = h0, h1, h2, h3, h4
        temps = []

        print(f"=== Block {block_index // 64} ===")
        print(f"init: A={a:08x} B={b:08x} C={c:08x} D={d:08x} E={e:08x}")

        for t in range(80):
            if 0 <= t <= 15:
                f = (b & c) | ((~b) & d)
                k = 0x5A827999
            elif 16 <= t <= 19:
                f = b ^ c ^ d
                k = 0x6ED9EBA1
            elif 20 <= t <= 39:
                f = (b & c) | (b & d) | (c & d)
                k = 0x8F1BBCDC
            elif 40 <= t <= 59:
                f = (b & c) | ((~b) & d)
                k = 0x5A827999
            else:
                f = b ^ c ^ d
                k = 0xCA62C1D6

            temp = (rol32(a, 5) + f + e + k + w[t]) & 0xffffffff
            temps.append(temp)

            e = d
            d = c
            c = rol32(b, 30)
            b = a
            a = temp

        temp75 = temps[75]
        temp76 = temps[76]
        temp77 = temps[77]
        temp78 = temps[78]
        temp79_delta = temps[79]

        rol30_temp75 = rol32(temp75, 30)
        rol30_temp76 = rol32(temp76, 30)
        rol30_temp77 = rol32(temp77, 30)

        native_h0 = (old_h0 + temp79_delta) & 0xffffffff
        native_h1 = (old_h1 + temp78) & 0xffffffff
        native_h2 = (old_h2 + rol30_temp76) & 0xffffffff
        native_h3 = (old_h3 + rol30_temp77) & 0xffffffff
        native_h4 = (old_h4 + rol30_temp75) & 0xffffffff

        for t, temp in enumerate(temps):
            if t == 79:
                print(f"round {t:02d}: temp={native_h0:08x}")
            else:
                print(f"round {t:02d}: temp={temp:08x}")

        print(f"tail temp75={temp75:08x}")
        print(f"tail temp76={temp76:08x}")
        print(f"tail temp77={temp77:08x}")
        print(f"tail temp78={temp78:08x}")
        print(f"tail rol30(temp75)={rol30_temp75:08x}")
        print(f"tail rol30(temp76)={rol30_temp76:08x}")
        print(f"tail rol30(temp77)={rol30_temp77:08x}")
        print(
            "native-tail "
            f"H0={native_h0:08x} H1={native_h1:08x} "
            f"H2={native_h2:08x} H3={native_h3:08x} H4={native_h4:08x}"
        )

        h0 = native_h0
        h1 = native_h1
        h2 = native_h2
        h3 = native_h3
        h4 = native_h4

    print("digest =", f"{h0:08x}{h1:08x}{h2:08x}{h3:08x}{h4:08x}")

if __name__ == "__main__":
    msg = b"123456"

    H0 = 0x67452301
    H1 = 0xEFCDAB89
    H2 = 0x98BADCFE
    H3 = 0x5E4A1F7C
    H4 = 0x10325476

    sha1_temp_trace(msg, H0, H1, H2, H3, H4)
```

unidbg.java:

```java
package com.mfw;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Emulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.HookStatus;
import com.github.unidbg.hook.ReplaceCallback;
import com.github.unidbg.hook.hookzz.Dobby;
import com.github.unidbg.hook.hookzz.IHookZz;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.DalvikModule;
import com.github.unidbg.linux.android.dvm.DvmClass;
import com.github.unidbg.linux.android.dvm.DvmObject;
import com.github.unidbg.linux.android.dvm.StringObject;
import com.github.unidbg.linux.android.dvm.VM;
import com.github.unidbg.linux.android.dvm.jni.ProxyClassFactory;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.arm.backend.Backend;
import com.github.unidbg.arm.context.RegisterContext;
import com.github.unidbg.debugger.BreakPointCallback;
import com.github.unidbg.utils.Inspector;
import unicorn.Arm64Const;

import java.io.FileNotFoundException;
import java.io.PrintStream;
import java.io.File;
import java.io.IOException;

public class zzzghostsigh {

    // 目标 App 包名。xPreAuthencode 的第三个业务参数最终就是这个包名字符串。
    private static final String APK_PACKAGE = "com.mfw.roadbook";

    // IDA 中确认的前置校验函数 sub_3C9C4 偏移。
    // 第一版先直接绕过它，只验证 xPreAuthencode 主链。
    private static final long SUB_3C9C4_OFFSET = 0x3C9C4L;

    // loc_3DEC4 内部进一步调用的压缩核心地址。
    // 第二阶段在这里观察 X0 / X1 的真实入参。
    private static final long SHA1_CORE_OFFSET = 0x3E1D0L;

    // 你已经放到 unidbg 测试资源目录下的 libmfw.so 路径。
    private static final String LIB_PATH =
            "unidbg-android/src/test/resources/example_binaries/arm64-v8a/libmfw.so";

    // AuthorizeHelper 实例 native 方法签名。
    // Java 层声明为：private native String xPreAuthencode(Context context, String str, String str2)
    private static final String X_PRE_AUTH_SIGNATURE =
            "xPreAuthencode(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;";

    private static final String SIMPLE_CANONICAL_STR = "123456";

    private final AndroidEmulator emulator;
    private final VM vm;
    private final Module module;
    private final DvmClass authorizeHelperClass;
    private final DvmClass contextClass;

    public zzzghostsigh() {
        // 按当前 IDA/so 情况固定走 64 位。
        // libmfw.so 当前分析目标是 arm64-v8a 版本。
        // trace 模式不要挂 DynarmicFactory。
        // DynarmicBackend 不支持 traceCode 依赖的 hook_add_new。
        emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName(APK_PACKAGE)
                .build();

        // 设置 Android 系统库解析器，API 23 是 unidbg 常见兼容档位。
        Memory memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));

        // 创建 Dalvik VM，并开启 ProxyClassFactory。
        // 这样后面传 String、Context 这类对象会更顺手。
        vm = emulator.createDalvikVM();
        vm.setDvmClassFactory(new ProxyClassFactory());

        // 设置是否输出详细的JNI调用日志
        vm.setVerbose(true);

        // 只加载目标 so，不自动执行 JNI_OnLoad，保持流程可控。
        DalvikModule dm = vm.loadLibrary(new File(LIB_PATH), false);

        // -----------以上都是比较固定格式--------------

        // 手动执行 JNI_OnLoad，这一步会触发 RegisterNatives，
        // 把 xPreAuthencode / xAuthencode / signEventData / signatureChecked 都注册进 VM。
        dm.callJNI_OnLoad(emulator);
        module = dm.getModule();

        // 解析 Java 层对应的类。
        // 这里我们只用最小链：AuthorizeHelper + Context。
        authorizeHelperClass = vm.resolveClass("com/mfw/tnative/AuthorizeHelper");
        contextClass = vm.resolveClass("android/content/Context");

        // 安装前置校验绕过逻辑。
        installSub3C9C4Bypass();
        // 把 native 执行路径完整记录下来
        enableTrace();
        // 在 0x3E1D0 下断，观察压缩核心入参。
        hookSha1CoreInput();
    }

    // 绕过 sub_3C9C4 判断
    private void installSub3C9C4Bypass() {
        // 先让 sub_3C9C4 恒为真。
        // 这样做的目的不是“最终绕过方案”，而是为了把 xPreAuthencode 主摘要链先跑通。
        // 这一步完成后，后面再单独补真实 Context / PackageManager / Signature 环境。
        IHookZz dobby = Dobby.getInstance(emulator);
        dobby.replace(module.base + SUB_3C9C4_OFFSET, new ReplaceCallback() {
            @Override
            public HookStatus onCall(Emulator<?> emulator, long originFunction) {
                // 如果命中这里，说明 native 的前置签名校验已经被走到了。
                // 直接返回 1，让 xPreAuthencode 继续往 loc_3DEC4 / 0x3E1D0 主摘要链走。
                System.out.printf("[*] bypass sub_3C9C4 at 0x%x%n", module.base + SUB_3C9C4_OFFSET);
                return HookStatus.LR(emulator, 1);
            }
        }, true);
    }

    // 把 native 执行路径完整记录下来
    private void enableTrace() {
        // traceCode 会把 libmfw.so 实际执行过的指令写到文件。
        try {
            File traceFile = new File("mfw.trace.txt");
            PrintStream printStream = new PrintStream(traceFile);
            emulator.traceCode(module.base, module.base + module.size).setRedirect(printStream);
            System.out.println("[*] trace file: " + traceFile.getAbsolutePath());
        } catch (FileNotFoundException e) {
            throw new RuntimeException(e);
        }
    }

    private void hookSha1CoreInput() {
        // 这里重点看两个寄存器：
        // X0：更像 state / 5 个魔数所在结构
        // X1：更像输入块或消息调度块
        emulator.attach().addBreakPoint(module.base + SHA1_CORE_OFFSET, new BreakPointCallback() {
            @Override
            public boolean onHit(Emulator<?> emulator, long address) {
                Backend backend = emulator.getBackend();
                RegisterContext context = emulator.getContext();

                long x0 = backend.reg_read(Arm64Const.UC_ARM64_REG_X0).longValue();
                long x1 = backend.reg_read(Arm64Const.UC_ARM64_REG_X1).longValue();

                byte[] x0Bytes = context.getPointerArg(0).getByteArray(0, 0x100);
                byte[] x1Bytes = context.getPointerArg(1).getByteArray(0, 0x100);

                System.out.printf("[*] hit 0x%x, x0=0x%x, x1=0x%x%n", address, x0, x1);
                Inspector.inspect(x0Bytes, "0x3E1D0 X0 state");
                Inspector.inspect(x1Bytes, "0x3E1D0 X1 block");
                return true;
            }
        });
    }

    private String callXPreAuthencode(String canonicalStr) {
        // 这里故意不从 Java 包装链 AuthorizeHelper.b(...).c(...) 走，
        // 而是直接调实例 native。
        // 这样更适合第一版教学，因为参数意义最清晰，也最接近 IDA 里的 sub_396C8。

        // 构造一个 AuthorizeHelper Java 对象实例。
        // 这里不依赖它的字段内容，因为我们直接把第三个参数 str2 显式传进 native。
        DvmObject<?> helper = authorizeHelperClass.newObject(null);

        // 第一版只传一个最小 Context 占位对象。
        // 因为 sub_3C9C4 已被绕过，这里不需要真的去实现 getPackageManager 等方法。
        DvmObject<?> context = contextClass.newObject(null);

        // 直接按 Java 层方法签名调用实例 native：
        // xPreAuthencode(Context context, String str, String str2)
        //
        // 参数语义：
        // context      -> 最小 mock Context
        // canonicalStr -> 规范化请求串，也就是你 Frida 里抓到的原始 str
        // APK_PACKAGE  -> 包名字符串，对应 Java 层第三个业务参数 str2
        StringObject result = helper.callJniMethodObject(
                emulator,
                X_PRE_AUTH_SIGNATURE,
                context,
                canonicalStr,
                APK_PACKAGE
        );
        return result.getValue();
    }

    private void runSimpleExample() {
        // 第一档：先看最小输入能不能出结果。
        String result = callXPreAuthencode(SIMPLE_CANONICAL_STR);
        System.out.println("simple input  = " + SIMPLE_CANONICAL_STR);
        System.out.println("simple result = " + result);
    }

    /*
    private void runRealExample() {
        // 第二档：再喂真实 client_auth 规范化串。
        // 这里更接近 zzzghostsigh 的真实生成场景。
        String result = callXPreAuthencode(REAL_CANONICAL_STR);
        System.out.println("real input length = " + REAL_CANONICAL_STR.length());
        System.out.println("real result       = " + result);
    }
    */

    private void destroy() throws IOException {
        // 关闭 emulator，释放 native/VM 资源。
        emulator.close();
    }

    public static void main(String[] args) throws Exception {
        // main 只做三件事：
        // 1. 初始化测试类
        // 2. 先跑简单输入
        // 3. 再跑真实规范化串
        zzzghostsigh test = new zzzghostsigh();
        try {
            test.runSimpleExample();
            // test.runRealExample();
        } finally {
            test.destroy();
        }
    }
}
```

APK文件下载地址：

链接：https://pan.quark.cn/s/7dbceebe781f?pwd=BTau 提取码：BTau

---

推荐一下比较好用的 Frida 工具：[Frida-Hookers](https://github.com/Mengz3/Frida-Hookers)

---

上传的附件：
- libmfw.so

（958.22kb，17次下载）

---

# 回复

## 回复 by MaYil (#2)

*2026-5-2 13:28*

感谢分享

## 回复 by 墨穹呢 (#3)

*2026-5-3 09:43*

感谢分享

## 回复 by PPTV (#4)

*2026-5-3 18:10*

感谢分享

## 回复 by 红皮西瓜 (#5)

*2026-5-6 10:54*

感谢分享

## 回复 by Imxz (#6)

*2026-5-8 11:00*

tql

## 回复 by Ahzn (#7)

*2026-5-11 16:46*

呵呵。。柯里吉娃 哇哇哇带2
