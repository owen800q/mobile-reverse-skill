---
title: '[原创]D3CTF 2026 d3llvm.apk 反调试定位与加密 SO的Dump'
url: https://bbs.kanxue.com/thread-292355.htm
tid: 292355
author: '0xCCCC'
date: '2026-08-08'
tags: [Android安全, 原创]
crawled_at: '2026-08-12T04:03:06+00:00'
replies: 10
---

**这篇文章记录 D3CTF 2026 `d3llvm` 在启动阶段的分析过程，重点不在最终输入算法，而在下面这条链路：**

  -> logcat 定位 JNI_OnLoad

  -> 逐层 trace 外层 libd3llvm.so

  -> 放行环境检查

  -> 发现加密的 libd3llvm_payload.so

  -> 通过 dlsym 捕获 Payload_OnLoad

  -> 从内存恢复可被 IDA 正确识别的 payload ELF

  -> 分析 payload 内层状态机

  -> 定位并验证第二层检查

**测试环境**

设备：Pixel 5，arm64-v8a，已解锁并具有 root

系统：Android

动态分析：Frida 17.15.3

静态分析：JADX、IDA Pro

辅助工具：adb、logcat、apktool

包名：com.example.d3llvm

**1. 从启动崩溃开始**

安装 APK 后直接点击图标，直接闪退。看起来是环境检测到异常，抓日志看看清理日志、启动 Activity，再导出本次崩溃信息：

```cmd

adb shell am force-stop com.example.d3llvm

adb logcat -c

adb shell am start -n com.example.d3llvm/.MainActivity

adb logcat -d > "D:\anzhuonixiang\d3llvm_log.txt"

\```

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_5THT4TRTRE9C8BX.webp)

可以看出，Android 明确指出 `libd3llvm.so` 的 `JNI_OnLoad` 返回了错误值。

所以目前线索指向分析libd3llvm.so，进去看看到底怎么检测的，先用apktool解包一下apk。

**2. 静态查看外层 JNI_OnLoad**

**![image](https://bbs.kanxue.com/upload/attach/202608/1065284_5GDAXF7Y4R9J7DD.webp)![image](https://bbs.kanxue.com/upload/attach/202608/1065284_7ZZV6JGM4KAA97V.webp)**

看起来有点吓人，检测点挺多而且嵌套了几层，大致找几个看一下

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_57YD92WVKAMEPXW.webp)

TracePid检测有没有正在被调试

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_ZPXS3E7KPJB7R6Y.webp)

检测Bootloader锁是否打开，也就是说root过的手机环境会被检测

**3. 先 trace 返回值判断哪些检测点需要绕开**

由于apk一打开直接闪退，应使用启动模式而不是附加模式

frida -U -f com.example.d3llvm -l .\d3llvm_trace_step.js

\```
const module = Process.findModuleByName('libd3llvm.so');
function traceReturn(module, offset, name) {
    Interceptor.attach(module.base.add(offset), {
        onLeave(retval) {
            console.log(`[RET] ${name} => ${retval.toInt32()}`);
        }
    });
}
traceReturn(module, 0x103bc, 'sub_103bc');
traceReturn(module, 0x104b8, 'sub_104b8');
traceReturn(module, 0x10c28, 'sub_10c28');
traceReturn(module, 0x10c50, 'sub_10c50');
traceReturn(module, 0x10d00, 'sub_10d00');
traceReturn(module, 0x10ec4, 'sub_10ec4');
traceReturn(module, 0x1137c, 'sub_1137c');
traceReturn(module, 0x11674, 'sub_11674');
traceReturn(module, 0x11828, 'sub_11828');
\```

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_ZJ6ASWAAGXMM5UE.webp)

第一次运行时，外层流程停在 `sub_103BC`。修改返回值继续

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_ZAY28PDZ5PGMHSV.webp)

哦豁，都验证通过，但依然没有启动成功。怀疑是下图中的Payload_Onload函数校验没通过。

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_BR74WVXV8JCTBAJ.webp)

改一下脚本，抓一下v3 v5的值。v3是Payload_Onload函数的函数地址，且位于另一个.so文件（libd3llvm_payload.so）

\```
//检查payload_onload地址是否查询成功
Interceptor.attach(module.base.add(0xfe34), {
    onEnter() {
        const x8 = this.context.x8;
        let payloadModule = Process.findModuleByName('libd3llvm_payload.so');
        console.log(`[FE34] X8=${x8}`);
        console.log(`Address=${payloadModule.base}`);
    }
});

//检查payload_onload函数返回值
Interceptor.attach(module.base.add(0xfe58), {
    onEnter() {
        const raw = this.context.x0.toUInt32();
        const signed = raw > 0x7fffffff
        ? raw - 0x100000000
        : raw;

        console.log(`[FE58] W0=${signed}`);
    },
    onLeave(ret) {
    console.log('[+] Payload_OnLoad original result: ' +
        ret.toInt32());
                }
});
\```

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_3NK98KQ6C8PSVR5.webp)

找到了，v5为-1，也就是说Payload_Onload函数大概率也是个校验函数，执行结果不满足要求。

这里如果直接修改Payload_Onload函数返回值，有可能会导致其中一些初始化操作不执行，保险起见去对应函数部分看一下。

**4. 动态dump出libd3llvm_payload.so**

ida打开libd3llvm_payload.so文件发现本身是加密过的，需要用frida来hook出解密的文件。

这里选择dlsym函数执行时的时间点来dump，因为如果Payload_Onload开始执行时dump，有可能文件结构会被frida破坏。

\```
//dump解密后的so函数

function dumpPayload(module) {
    if (module === null) {
        throw new Error('payload module is null');
    }

    const outputPath =
        '/data/user/0/com.example.d3llvm/files/' +
        'libd3llvm_payload.decrypted.so';

    // 读取磁盘上的原始ELF，保留正常文件布局。
    const source = new File(module.path, 'rb');
    const chunks = [];
    let total = 0;

    while (true) {
        const chunk = source.readBytes(0x10000);
        if (chunk.byteLength === 0) {
            break;
        }

        const bytes = new Uint8Array(chunk);
        chunks.push(bytes);
        total += bytes.length;
    }

    source.close();

    const image = new Uint8Array(total);
    let position = 0;

    chunks.forEach((chunk) => {
        image.set(chunk, position);
        position += chunk.length;
    });

    if (
        image.length < 0x40 ||
        image[0] !== 0x7f ||
        image[1] !== 0x45 ||
        image[2] !== 0x4c ||
        image[3] !== 0x46 ||
        image[4] !== 2 ||
        image[5] !== 1
    ) {
        throw new Error('source is not ELF64 little-endian');
    }

    const view = new DataView(image.buffer);

    const readU16 = (offset) =>
        view.getUint16(offset, true);

    const readU32 = (offset) =>
        view.getUint32(offset, true);

    const readU64 = (offset) =>
        readU32(offset) +
        readU32(offset + 4) * 0x100000000;

    const programHeaderOffset = readU64(0x20);
    const programHeaderSize = readU16(0x36);
    const programHeaderCount = readU16(0x38);

    let patchedSegments = 0;
    let patchedBytes = 0;

    for (let i = 0; i < programHeaderCount; i++) {
        const header =
            programHeaderOffset + i * programHeaderSize;

        const type = readU32(header);
        const flags = readU32(header + 4);
        const fileOffset = readU64(header + 8);
        const virtualAddress = readU64(header + 16);
        const fileSize = readU64(header + 32);

        const isLoadSegment = type === 1;       // PT_LOAD
        const isExecutable = (flags & 1) !== 0; // PF_X

        if (!isLoadSegment || !isExecutable || fileSize === 0) {
            continue;
        }

        const available = Math.min(
            fileSize,
            image.length - fileOffset
        );

        if (available <= 0) {
            continue;
        }

        const memoryAddress =
            module.base.add(virtualAddress);

        const decrypted =
            memoryAddress.readByteArray(available);

        image.set(
            new Uint8Array(decrypted),
            fileOffset
        );

        patchedSegments++;
        patchedBytes += available;

        console.log(
            '[dump] patched executable PT_LOAD' +
            ' memory=' + memoryAddress +
            ' fileOffset=0x' + fileOffset.toString(16) +
            ' size=0x' + available.toString(16)
        );
    }

    if (patchedSegments === 0) {
        throw new Error('no executable PT_LOAD segment found');
    }

    const output = new File(outputPath, 'wb');
    output.write(image.buffer);
    output.flush();
    output.close();

    console.log(
        '[+] valid ELF dumped: ' + outputPath +
        ' size=' + image.length +
        ' patched=0x' + patchedBytes.toString(16)
    );
}
let payloadOnLoadDumped = false;

function dumpso() {
    const address = findGlobalExport('dlsym');
    if (address === null) {
        return;
    }

    Interceptor.attach(address, {
        onEnter(args) {
            this.symbol = null;
            try {
                if (!args[1].isNull()) {
                    this.symbol = args[1].readCString();
                }
            } catch (error) {
                this.symbol = null;
            }
        },
        onLeave(retval) {
            if (
                this.symbol === 'Payload_OnLoad' &&
                !retval.isNull() &&
                !payloadOnLoadDumped
            ) {
                let payloadModule = Process.findModuleByName('libd3llvm_payload.so');
                if (payloadModule === null) {
                    //根据地址反查函数属于哪个模块，得到libd3llvm_payload.so模块地址
                    payloadModule = Process.findModuleByAddress(target);
                }
                try {
                    dumpPayload(payloadModule);
                    console.log('[+] payload dump completed');
                } catch (error) {
                    payloadOnLoadDumped = false;
                    console.log(
                        '[-] payload dump failed: ' + error.stack
                    );
                }
            }
        }
    });

    console.log('[+] watching dlsym at ' + address);
}
\```

成功dump出且可以分析

**5. Payload_OnLoad函数分析**

**![image](https://bbs.kanxue.com/upload/attach/202608/1065284_PCMS8BBTGQGRCBX.webp)**

**![image](https://bbs.kanxue.com/upload/attach/202608/1065284_Y87886R82JYAM7M.webp)**

有一个魔改过的ollvm混淆，D810无法直接处理。观察后发现状态位为v22，每次跳转都会改变v22，且有大量类似*(v20 + (a3[*v20 + 17] ^ a3[*v20 + 18]))的混淆。a3是一张固定混淆表，这部分混淆本质是每次进行查表,ollvm本身state也并不多，可以直接手动整理所有状态来观察跳转。

整理后的伪代码：

\```
case 0:
    break;
case 1:
    *(v20 + 0xc8) = (*(qword_43148 + 1448))(*qword_43148,*(v20 + 0xc0),v20 + 0x30,4LL);  /* a3 XOR(case=1, 37, 38); idx 38,39 | a3 XOR(case=1, 35, 36); idx 36,37 | a3 XOR(case=1, 31, 32); idx 32,33 */
    (*(qword_43148 + 248))(*qword_43148, *(v20 + 0xc0));  /* a3 XOR(case=1, 35, 36); idx 36,37 */
    v13 = *(qword_43148 + 488);
    v14 = *qword_43148;
    v4 = (off_40BA0[0x1])(&unk_423BD);  /* a3 XOR(case=1, 15, 16); idx 16,17 */
    *(v20 + 0xc0) = v13(v14, v4);  /* a3 XOR(case=1, 35, 36); idx 36,37 */
    if ( *(v20 + 0xc0) )  /* a3 XOR(case=1, 35, 36); idx 36,37 */
        v5 = 7;
    else
        v5 = 2;
    *v20 += v5;
case 2:
    *(v20 + 0x4) = -1;  /* a3 XOR(case=2, 18, 19); idx 20,21 */
    *v20 -= 2;
case 3:
    *(v20 + 0x4) = 0;  /* a3 XOR(case=3, 17, 18); idx 20,21 */
    *v20 -= 3;
case 4:
    if ( *(v20 + 0x18) )  /* a3 XOR(case=4, 22, 23); idx 26,27 */
        v10 = 2;
    else
        v10 = -2;
    *v20 += v10;
case 5:
    if ( v21 )
        v6 = -3;
    else
        v6 = -1;
    *v20 += v6;
case 6:
    if ( (sub_3689C(*(v20 + 0x18), &bridge) & 1) != 0 )  /* a3 XOR(case=6, 20, 21); idx 26,27 */
        v7 = 5;
    else
        v7 = 1;
    *v20 += v7;
case 7:
    *(v20 + 0x4) = -1;  /* a3 XOR(case=7, 13, 14); idx 20,21 */
    *v20 -= 7;
case 8:
    *(v20 + 0xc8) = (*(qword_43148 + 1448))(*qword_43148,*(v20 + 0xc0),v20 + 0x90,2LL);  /* a3 XOR(case=8, 30, 31); idx 38,39 | a3 XOR(case=8, 28, 29); idx 36,37 | a3 XOR(case=8, 26, 27); idx 34,35 */
    (*(qword_43148 + 248))(*qword_43148, *(v20 + 0xc0));  /* a3 XOR(case=8, 28, 29); idx 36,37 */
    *(v20 + 0x4) = 65542;  /* a3 XOR(case=8, 12, 13); idx 20,21 */
    *v20 -= 8;
case 9:
    *(v20 + 0x4) = 0;  /* a3 XOR(case=9, 11, 12); idx 20,21 */
    *v20 -= 9;
case 10:
    qword_43148 = v24;
    memcpy(v20 + 0x30, off_408C8, 0x60uLL);  /* a3 XOR(case=10, 22, 23); idx 32,33 */
    memcpy(v20 + 0x90, off_40928, 0x30uLL);  /* a3 XOR(case=10, 24, 25); idx 34,35 */
    v11 = *(qword_43148 + 488);
    v12 = *qword_43148;
    v8 = (off_40BA0[0x2])(&unk_42397);  /* a3 XOR(case=10, 4, 5); idx 14,15 */
    *(v20 + 0xc0) = v11(v12, v8);  /* a3 XOR(case=10, 26, 27); idx 36,37 */
    if ( *(v20 + 0xc0) )  /* a3 XOR(case=10, 26, 27); idx 36,37 */
        v9 = -9;
    else
        v9 = -1;
    *v20 += v9;
case 11:
    v24 = operator new(0x738uLL);
    sub_12590(v24, *(v20 + 0x18));  /* a3 XOR(case=11, 15, 16); idx 26,27 */
    --*v20;
\```

完整成功路径：5 -> 4 -> 6 -> 11 -> 10 -> 1 -> 8 -> 0

继续定位，定位到sub_3689c函数校验没通过

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_KBHQ6464NG2B3S7.webp)

是一个程序的完整性校验，直接hook

\```
let payloadOnLoadHooked=false;
function watchDlsym() {
    const address = findGlobalExport('dlsym');
    if (address === null) {
        return;
    }

    Interceptor.attach(address, {
        onEnter(args) {
            this.symbol = null;
            try {
                if (!args[1].isNull()) {
                    this.symbol = args[1].readCString();
                }
            } catch (error) {
                this.symbol = null;
            }
        },
        onLeave(retval) {
            if (
                this.symbol === 'Payload_OnLoad' &&
                !retval.isNull() &&
                !payloadOnLoadHooked
            ) {
                payloadOnLoadHooked = true;
                //保存入口地址
                const target = ptr(retval);
                console.log('[+] dlsym Payload_OnLoad => ' + target);
                let payloadModule = Process.findModuleByName('libd3llvm_payload.so');
                if (payloadModule === null) {
                    //根据地址反查函数属于哪个模块，得到libd3llvm_payload.so模块地址
                    payloadModule = Process.findModuleByAddress(target);
                }
                if (payloadModule !== null) {
                    /*
                     * Payload_OnLoad performs an internal predicate at +0x3689c.
                     * On this unlocked/rooted device it returns false, so the
                     * flattened dispatcher stores -1 before RegisterNatives.
                     * Force this predicate to true so normal registration runs.
                     */
                    Interceptor.attach(payloadModule.base.add(0x3689c), {
                        onLeave(r) {
                            console.log('[+] payload predicate original result: ' +
                                r.toInt32());
                            r.replace(1);
                        }
                    });
                    console.log('[+] hook installed: payload predicate at ' +
                        payloadModule.base.add(0x3689c));
                } else {
                    console.log('[!] cannot locate payload module for predicate hook');
                }

                Interceptor.attach(target, {
                    onEnter(args) {
                        console.log('[+] entered Payload_OnLoad');
                    },
                    onLeave(ret) {
                        console.log('[+] Payload_OnLoad original result: ' +
                            ret.toInt32());
                    }
                });
                console.log('[+] hook installed: Payload_OnLoad');
            }
        }
    });

    console.log('[+] watching dlsym at ' + address);
}
\```

frida启动，程序成功运行

![image](https://bbs.kanxue.com/upload/attach/202608/1065284_BX2WV84G7BUHAG3.webp)

**6. 总结**

这部分分析最终形成了两层定位：

\```

外层 libd3llvm.so

  -> JNI_OnLoad

  -> sub_103BC 环境门

  -> dlopen(libd3llvm_payload.so)

  -> dlsym(Payload_OnLoad)

内层 libd3llvm_payload.so

  -> Payload_OnLoad

  -> GetEnv

  -> sub_3689C bridge/摘要/认证检查

  -> FindClass

  -> RegisterNatives

  -> 返回 JNI_VERSION_1_6

\```

对我来说，这个apk最有价值的地方不是后续算法部分，而是面对类似反调试手段时建立了一套可重复的方法：

\```

先从系统日志确定失败边界

-> 静态查看条件关系

-> 动态记录原始返回值

-> 每次只放行当前阻塞点

-> 在运行时边界捕获下一层模块

-> 正确恢复 ELF 后继续静态分析

-> 最后收敛成最小 Hook 集

\```

本文重点在反调试部分，暂不展开后续解密算法。

---

# 回复

## 回复 by SomeMx (#2)

过来瞧瞧

## 回复 by mb_vwdfywtj (#3)

``

## 回复 by wx_插曲 (#4)

6

## 回复 by Zepp7289 (#5)

tql

## 回复 by mb_ldbucrik (#6)

感谢分享

## 回复 by cpannn (#7)

感谢分享

## 回复 by iBa0 (#8)

123

## 回复 by mb_jhohnbzu (#9)

666

## 回复 by 带带弟弟吧 (#10)

1

## 回复 by tonykros (#11)

666
