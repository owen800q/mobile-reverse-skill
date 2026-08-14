---
title: '[原创]某视频APP七神签名之X-Gorgon生成逻辑逆向分析——古法逆向与AI辅助结合'
url: https://bbs.kanxue.com/thread-291170.htm
tid: 291170
author: console_
date: '2026-05-10'
tags: [Android安全, 原创, 逆向分析]
crawled_at: '2026-08-14T05:10:28+00:00'
replies: 13
---

**本文章中所有内容仅供学习交流使用，不用于其他任何目的，严禁用于商业用途和非法用途，否则由此产生的一切后果均与作者无关！若有侵权，请联系删除。本文仅记录一次针对移动端 native 签名逻辑的逆向分析过程，用于安全研究、算法学习和逆向工程方法论交流。文中涉及的脚本、地址和结论均来自本地样本与模拟环境验证，不讨论任何绕过风控、批量请求或业务滥用场景。**

在这篇文章中你能看到古法逆向和AI逆向的结合，确保token充足，避免天才程序员陨落
需要用到的工具有ida pro 9.2，jadx，frida(我的是魔改版)，一台root的真机，unidbg，版本是34.1，codex5.4高推理,
首先检测idapromcp和jadxmcp配置是否完好，codex能否正常调用mcp接口进行分析，没问题的话开始分析

# 第一章定位七神生成函数

使用hookssl证书校验过掉校验，成功抓包,这部分教程很多，不再赘述
来到libsscronet.so中，即七个参数x-argus、x-gorgon、x-helios 、 x-khronos 、 x-ladon 、 x-medusa 、 x-soter，
我们发现这些字符串都被同一个地址调用，地址为0x3FDECC
然后这个函数内部这些字符串又作为参数传递给sub_1ECA2C
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_KJE8NM8NB55W9WR.webp)
交叉引用太多，所以我们直接使用frida，hook，0x1ECA2C这个函数，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_AAYTJEEFCS4DKNG.webp)

```python
/**
 *  Hook libsscronet.so 中偏移 0x1ECA2C 的函数，打印其入参
 *  使用 waitForModule 确保目标模块加载后执行 hook
 */

const SO_NAME = "libsscronet.so";
const OFFSET  = 0x1ECA2C;

// 等待 SO 加载并执行回调
function waitForModule(soName, callback) {
    const module = Process.findModuleByName(soName);
    if (module) {
        console.log(`[+] ${soName} 已加载，基址: ${module.base}`);
        callback(module);
        return;
    }

    console.log(`[*] 等待 ${soName} 加载...`);
    const dlopen = Module.findExportByName(null, "android_dlopen_ext")
                || Module.findExportByName(null, "dlopen");

    Interceptor.attach(dlopen, {
        onEnter(args) {
            const path = args[0].readCString();
            if (path && path.indexOf(soName) >= 0) {
                this.isTarget = true;
            }
        },
        onLeave(retval) {
            if (this.isTarget) {
                let mod = Process.findModuleByName(soName);
                // 备选：枚举模块查找
                if (!mod) {
                    Process.enumerateModules().forEach(m => {
                        if (m.name.indexOf("sscronet") >= 0) mod = m;
                    });
                }
                if (mod) {
                    console.log(`[+] ${soName} 已加载，基址: ${mod.base}`);
                    callback(mod);
                }
                this.isTarget = false;
            }
        }
    });
}

// 具体 hook 实现：打印入参
function hookTarget(module) {
    const targetAddr = module.base.add(OFFSET);
    console.log(`[*] 正在 hook 地址: ${targetAddr}`);

    Interceptor.attach(targetAddr, {
        onEnter(args) {
            console.log("---------- 入参信息 ----------");
            console.log("args[0]:", args[0]);
            console.log("args[1] (CString):", args[1].readCString());

            // 可选：打印调用堆栈，便于定位调用来源
            // console.log("调用堆栈:\n" +
            //     Thread.backtrace(this.context, Backtracer.FUZZY)
            //         .map(DebugSymbol.fromAddress)
            //         .join("\n")
            // );
            console.log("------------------------------");
        },
        onLeave(retval) {
            // 如需查看返回值可在此处理
        }
    });
}

// 入口
function main() {
    waitForModule(SO_NAME, hookTarget);
}

main();
\```

成功命中七神的出口，但输出太多，所以我们优化hook代码
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_TSYA7FVAXYZTMA4.webp)

## 美化后的输出为，可以看到调用堆栈

#  ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9A5D5C3XTNYD3DD.webp)调用堆栈:0x7710c82b90 libsscronet.so!0x45cb900x7710b92300 libsscronet.so!0x36c3000x786a4c4350 libc.so!malloc+0x280x7710b55934 libsscronet.so!0x32f9340x7710c236ac libsscronet.so!0x3fd6ac0x7710c233c8 libsscronet.so!0x3fd3c80x778e169d8c先从最顶层的0x7710c82b90 libsscronet.so!0x45cb90入手跳转点进去查看其伪c代码，就是下面这行代码。f5转伪c然后扔给AI分析，发现请求头原始数据（v137, v132） │ ▼ v73(v74, v75) ← 真正的签名生成算法 │ ▼ 返回 s（完整签名字符串） │sub_1ECA2C(0x1ECA2C) ← 你的 Hook 点，负责设置到网络请求 下面hook，v73这个函数，并打印参数v74和v75即地址0x456B6C ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_W7N2DQ7T6Y3PCUD.webp) hook结果日志为参数一是url，参数二是hearders的信息========== v73 被调用 ==========[v74] args[0]: 0x76ebd98e00[v74] 字符串内容:这里是url信息，接口已脱敏[v75] args[1]: 0x77167cd600[v75] 字符串内容:下面是请求头信息x-tt-request-tagt=0;n=0;s=0;p=0x-tt-dtAAAWXKIIYPPF7GQF5UICSORC22CKTAZNDR5FHOUZ2WJP4APR6KKBNQT2MSLIBKPAJ3S57LYWRF7FJUCBUALGGNKGTWXBNSGBETHW7K5XUHL5SSF7Y6RUQ3M227UNCDNRMZTP5GZL337BK7MIFNYI72I后面还有很多，

 看这个函数被调用之后，在arm64指令集的调用约定中，寄存器x0通常用来存储函数调用的返回值，这里将x0传递给了x21
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_2ZD2J3MP8XFYRK5.webp)
 我们接下来hook，45CB70这个地址，读取x0获取最原始的返回值

```python
/**
 * Hook 0x45CB70 (v73 返回后的第一条指令)
 * 用于捕获七神签名最终字符串，并验证其所在模块，wechat，hook111999
 */
function hookReturnValue(module) {
    const targetAddr = module.base.add(HOOK_OFFSET);
    console.log(`[*] 即将 Hook 地址: ${targetAddr}`);

    // 查看该地址所在的模块（可能是 libsscronet.so 或其他 so）
    const modInfo = Process.findModuleByAddress(targetAddr);
    if (modInfo) {
        console.log(`[+] 地址所在模块: ${modInfo.name}`);
        console.log(`[+] 模块基址: ${modInfo.base}`);
        console.log(`[+] 模块内偏移: ${targetAddr.sub(modInfo.base)}`);
    } else {
        console.log("[!] 无法确定地址所属模块");
    }
    Interceptor.attach(targetAddr, {
        onEnter(args) {
            // 此时 x0 仍是 v73 的返回值（七神签名完整字符串指针）
            const retPtr = this.context.x0;
            console.log("\n========== v73 返回值 (x0) ==========");
            console.log("指针: " + retPtr);
            try {
                const retStr = retPtr.readCString();
                if (retStr) {
                    console.log("内容:\n" + retStr);
                } else {
                    console.log("(空字符串)");
                }
            } catch (e) {
                console.log("无法读取为 CString，打印 hexdump (前256字节):");
                console.log(hexdump(retPtr, { length: 256 }));
            }
            console.log("======================================\n");
        }
    });
}
function main() {
    waitForModule(SO_NAME, hookReturnValue);
}
main();
\```

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_7BNK7NNETSBB8BT.webp)

## 看到v73返回的就是七神的数值，我们下面定位v73这个函数的具体位置

```python
const SO_NAME = "libsscronet.so";
const V73_CALL_OFFSET = 0x45CB6C; // BLR X23
const V73_RET_OFFSET  = 0x45CB70; // MOV X21, X0
function hookV73(module) {
    // ------------------ Hook BLR X23 (0x45CB6C) ------------------
    const addrCall = module.base.add(V73_CALL_OFFSET);
    console.log(`[*] Hook v73 调用指令: ${addrCall}`);
    Interceptor.attach(addrCall, {
        onEnter(args) {
            // 此时 X23 保存着 v73 的真正地址
            const targetFuncAddr = this.context.x23;
            console.log("\n========== v73 目标函数信息 ==========");
            console.log("函数地址: " + targetFuncAddr);
            const targetMod = Process.findModuleByAddress(targetFuncAddr);
            if (targetMod) {
                console.log("所在模块: " + targetMod.name);
                console.log("模块基址: " + targetMod.base);
                console.log("模块内偏移: " + targetFuncAddr.sub(targetMod.base));
            } else {
                console.log("[!] 无法确定目标模块（可能是动态生成的代码）");
            }
            console.log("========================================\n");
        }
    });
\```

## 日志如下

日志如下，也就是BLR会跳转到一个其他so的函数，这个函数在 libmetasec_ml.so ，并且计算偏移 0x14DBF4 处，也就是里面的 sub_14DBF4 函数，我们下面转到libmetasec_ml.so
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_GEGKQFYMSQ2ARF9.webp)
**小结**
**v73这个函数会接收url和请求头信息两个参数，返回七神，我们要分析v73这个函数的实现，即它是怎么处理url和请求头参数生成七神的，我们通过hook定位到v73这个函数在libmetasec_ml.so 的sub_14DBF4中，下面我们转成libmetasec_ml.so，然后分析sub_14DBF4这个函数**

# unidbg固定输出并分析libmetasec_ml.so定位x-gorgon算法实现位置

**关于unidbg补环境**，**这部分可以单开一篇文章了。大家可以先看论坛里的有一篇补环境的文章，这篇文章重点在分析算法，避免篇幅过长，先不说明补环境的流程，补完环境正常输出固定七神之后(除了美杜莎其他全固定)，其中X-Gorgon的固定参数为
840440ca0000900e2e6316640c563d305547aba28ae11cf6f18e**
840440ca0000900e2e6316640c563d305547aba28ae11cf6f18e记住26个字节数据，后面分析的时候很重要
另外还有花指令，你可以让AI识别自动处理花指令，非常有效哦，这个可以后面写个文章
我们回到libmetasec_ml.so中，分析整个加密函数sub_14DBF4，分析调用链
让AI分析参数最终落地的地方
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_KGMVY3UDXSBWHF3.webp)
**g跳转到sub_14F394,注意到memcpy函数**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_DG99GETN8RBFVSV.webp)
我们下面使用 unidbg hook 这个函数，因为，它们是“数据真正写进缓冲区”的落地点，最适合看最终明文、字段写入顺序和实际字节内容。我们hook它得到str2即src，即数据的源地址，然后再使用unidbg对这个地址做：
emulator.traceWrite();来反推生成过程
hook代码为

```python
static void hook14F394Memcpy() {
    Debugger attach = emulator.attach();
    IHookZz hookZz = HookZz.getInstance(emulator);
    hookZz.wrap(module.findSymbolByName("memcpy"), new WrapCallback<RegisterContext>() {
        @Override
        public void preCall(Emulator<?> emulator, RegisterContext ctx, HookEntryInfo info) {
            UnidbgPointer lr = ctx.getLRPointer();
            // 只关心 sub_14F394 里的最终 memcpy
            long wantLr = module.base + 0x14F4EC;
            if (lr == null || lr.peer != wantLr) {
                return;
            }
            Pointer dest = ctx.getPointerArg(0);
            Pointer src = ctx.getPointerArg(1);
            int length = ctx.getIntArg(2);
            System.out.println("======== sub_14F394 memcpy ========");
            System.out.println("LR   : " + lr);
            System.out.println("dest : " + dest);
            System.out.println("src  : " + src);
            System.out.println("len  : " + length);
            if (src != null && length > 0) {
                byte[] data = src.getByteArray(0, length);
                Inspector.inspect(data, "sub_14F394 memcpy src");
                try {
                    System.out.println("src str: " + new String(data));
                } catch (Exception ignored) {
                }
            }
        }
    });
}
\```

**把hook之后的日志丢给codex，让它分析**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_ZTUZAH9J7Y23T7E.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_APDPVMZX35C4J7F.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9YQF85HT4WXVMQ3.webp)
得到这个地址之后，下面我们对这个地址0x126af280进行emulator.traceWrite，
emulator.traceWrite(begin,end)：顾名思义追踪写入，监控指定内存地址范围内的所有写入操作，记录"谁在什么时候往什么地址写了什么数据。
再直白一点就是我们要看是哪些地址把这52字节塞满了，且塞的hex是，这也是我们固定入参和输出的原因
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_8HSXFAUBKM8YUEZ.webp)
下面是监控这 52 字节，追溯是谁生成了这52字节的数据
unidbg trace代码为emulator.traceWrite(0x126af280, 0x126af280 + 0x34)，
有1w多行日志，我们全丢给codex让它帮我们分析，ai能大大减少我们的出错率，提高我们的工作效率
（这里记得创建个log.txt文件，**直接粘贴百分之一伯卡死的**）
codex分析日志的结果为
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_7EPK2QKSKHXERQF.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_46SQ38SNRRNFR88.webp)
**我们回到unidbg搜索日志中的地址0x10A010验证看是否是这样**
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_VXPYU2PB5ZVQTPH.webp)
完美对上，0x38，0x00，0x34，0x00，0x30等等都是匹配的。首位两条指令等会看汇编的时候再分析
最终我们定位到了，数据是指令0x10a010写入的，地址为0x109ff4，这两个地址都位于libmetasec_ml.so,中
我们打开ida跳转到地址0x10a010，f5转伪代码分析，我们可以得到这个不是最终的加函数，
这里的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FDQQTGNPEE5RY25.webp)
直接启动我们的IDA pro mcp，让其分析函数sub_109FB8，找到我们的X-Gongo是哪里生成的
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_YU972XRCQTCK4AN.webp)
AI分析结果：首先函数sub_109FB8不是核心加密函数，而是最终hex构造层；和我们的判断一致，这里也解决了为什么上面写入字节时，为什么写入一次就要写一次0。如下图所示
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_J5DYEAT57M8H2KE.webp)
我们继续向上溯源。即找到是谁把a1给函数sub_109FB8的，任务直接交给codex
codex定位到函数sub_77C90，这个函数也不是生成算法的地方，作用是把一段原始 byte 数组编码成 hex 字符
串，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_KD3CA3C98BCB2KJ.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_U56GY7X5ZCMASEE.webp)
接下来我们使用unidbg hook 函数sub_77C90，获取到原始的byte数组
使用unidbg hook函数sub_77C90，目的是找到byte数组的数据和地址是什么，
hook代码如下，在我们hook时会大量命中这个函数，和我们的固定参数是一样的
840440ca0000900e2e6316640c563d305547aba28ae11cf6f18e
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_N4WY2FUC4KNZVRX.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_XANXPU5HEB4EF26.webp)
我们将日志扔给codex，发现第12次命中了x-g参数下面tracewire得到的结构体地址和x-g，看是谁写入了它们
emulator.traceWrite(0x1265c540, 0x1265c540 + 26);
运行之后把日志丢给codex，让它分析X-Gorgon各字节的命中。分别在哪些函数里写入的，是一个函数一次性写入，还是不同的函数各写入一些字节最后拼接成X-Gorgon，日志不大直接丢给AI，让它分析，它会结合IDA pro mcp分析，能快速定位参数的命中位置，还会发现一些深层的细节，输出过长，只截取关键部分。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_8QKQ94ZNKUKGNN5.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_VA2FWZ5UHFFSC2A.webp)
26 字节不是一次性写入，而是由不同函数写入拼接而成”
现在我们已经完成“结果定位”，现在进入“逐字节生成路径解释”阶段；接下来就是用 IDA + unidbg动态trace，把 26 字节原始 Gorgon 的生成过程彻底拆开并复现。

# 逐个字节分析X-Gorgon的构成

sub_16CEA0 就是现在该主攻的 X-Gorgon 核心生成函数；直接让ai读伪代码即可，。最终结果如下
负责把模板变成最终后 20 字节。这里AI识别到sub_16CEA0是一个魔改的RC4算法，标准的RC4算法输入明文之后输出明文，但这里对加密后的字节进行了字节变换，导致我们使用标准RC4解密是解不出来的，必须复现第二轮字节变换的流程，做字节反变换才能得到加密后的密文，进而使用密钥解密密文得到明文，这就是我们的思路。
**下一步我们就要找到RC4算法输入的20字节明文找到RC4的密钥，测试算法看和我们的固定结果是否一致，即验证我们的思路是否正确**
直接让AI写出unidbg hook 函数sub_16CEA0的代码，运行hook代码之后密钥明文密文全部命中。日志如下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_2VAEAGM3VTDGUH8.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_C2PV53S4DUZYBC8.webp)
而且我们还知道了第一次和第二次轮的中间字节，更方便我们验证思路是否正确，写出nodejs复现程序，运行日志如下所示
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_X89VUXKR734FXFK.webp)
**最终结果是能和我们的固定结果能对上的840440ca0000900e2e6316640c563d305547aba28ae11cf6f18e**
下面开始分析20字节输入和密钥的来源，依旧emluator.tracewrite();找到是哪个函数写入的
结合上面的日志直接让写出trace代码，emulator.traceWrite(0x1271ca00, 0x1271ca00 + 20);
我们人工看日志很慢所以直接丢给ai，让它定位这20字节输入的来源
[17:46:09 075] Memory WRITE at 0x1271ca00, data size = 8, data value = 0x2aa3d28e69b52697, PC=RX@0x1242c1b4[libc.so]0x1c1b4, LR=RX@0x12109b90[libmetasec_ml.so]0x109b90，这里的八个字节 0x2aa3d28e69b52697就是我们20字节的前八个字节，其他的分析算法也一样
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_J9CVTW2JZYJDPVU.webp)
最后定位到这20字节不是一次性写入的，是8+12的方式，分别被指令0x109b90，0x109e6c，0x109e6c
写入，接下来启动IDA，分析这俩指令0x109b90和0x109e6c所在的函数，指令0x109b90定位到函数sub_109AD4，指令0x109e6c定位到函数sub_109D84，下面分析这俩函数，发现这俩函数并不是8字节和12字节生成的地方，只是一个拼接的出口
**97 26 B5 69 8E D2 A3 2A 00 00 00 00 00 05 09 04 68 21 94 F2**
即现在20字节拆开是分别写入的，所以下一步我们进一步启动tracewrite(),看是谁写了前8和后12字节，我们先分析前八个字节，即0x109b90，可以发现这是一个memcpy函数，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FUPKKT3H76DAGB3.webp)
我们写出hook函数打印输出参数，找到是谁生成了八个字节97 26 B5 69 8E D2 A3 2A
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_PFU8AHNB9NJ3K5J.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9YZ776AKQ5CRB6K.webp)
运行之后查看日志发现前四个字节来自0x125c9cc0，后四个字节来自0x125db4e0，
有了地址之后我们开始tracewrite看是谁写入了这些字节，
emulator.traceWrite(0x125c9cc0,0x125c9cc0+4);
emulator.traceWrite(0x125db4e0,0x125db4e0+12);
先分析前四个字节，运行之后日志如下，前四个字节写入在0x109e6c
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9JGGMYH4M3KU68K.webp)
我们跳转到0x109e6c，这里是memmove，不是生成的地方，我们继续hook定位
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_4EJNMFGXK779N9P.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_YK2798UFYK7VXTF.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_HYRCKDAUBTUJSZ4.webp)
wow，我们继续hook，找上层调用，有种套娃的感觉
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_3QCB54FGW427UYE.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FDJ223GWE522N7K.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9S7AE3WNGJUJHY2.webp)
套娃流程如下
10B74C>>1271c9a0>>0x10b4ec>>10B4E8>>0xe4ffebe8>>0x1072fc
套娃这一部分是手工活，下面跟完套娃，最后定位到地址为0x1072fc，跳转到地址0x1072fc
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_PWGH58N8NJYASWH.webp)
这是一个md5算法，且src是明文，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_VCPMDH3J7VBTTUX.webp)
分析这个函数的调用链，找到最外层的md5调用函数，hook到明文和密文。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_6WBWBS58RK95UXS.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_U2CDHNHHTJCKJBA.webp)
hook地址10747C，日志如下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_HMC4UTGS9GTMMJY.webp)
拿参数验证一哈看是不是标准md5，最后结果是9726B569B8C2B2BB49FA27EC3A20D996
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FT8WGZCBRQYX7ZS.webp)
和输出能对上，url做md5取前四字节这里前四个字节已经搞定了，下面我们分析后四个字节8E D2 A3 2A
回到上面的emulator.traceWrite(0x125db4e0,0x125db4e0+12);，跳转到0x109e6c
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_H3MEJHQECBGUZ8F.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9XE7N9JVKPWU4TU.webp)
继续hook mmove，溯源0x125c9cc8
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_4RQ992QRWDTDTPS.webp)
继续trace，0x125c9cc8
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_5ECH2BJPXQ8KKMC.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_A9VFZK7VPFDJ8EZ.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_HPNCFPJUCP52GHX.webp)
找到0x1271c8c0，继续trace
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_R6JE6CEGCKCYFAH.webp)
跳过去。0x836e4，这下进到真正的函数逻辑了
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_PVYUD67K4HK47SQ.webp)
ok啊hook入参，
这里打印出来就可以了，这个就是我们请求头里的x-ss-stub的前四个字节
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_3GAHJNHPG9XYW5K.webp)
现在20字节的前八个字节已经分析完毕了。下面我们分析后12个字节。
00 00 00 00 00 05 09 04 68 21 94 F2
结合前面的trace日志我们定位到sub_109D84
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_K2P4RXGQ7T4D4HQ.webp)
开始hook，12的前四个字节00 00 00 00，0x125c9cc8
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_MW3A96HHWHXVP6V.webp)
中间四个字节00 05 09 04，0x125c9cc8
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_TMUECD5U5BZFT9V.webp)
最后四个字节，0x125c9cc8，68 21 94 F2
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_Q6U9MN7FW2DVGFX.webp)
都在0x125c9cc8，我们trace看一下在哪里写入的
前四个。在0x10b750，中间四个和最后四个在0x10b4ec
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_74UD723U7YY22YN.webp)
先分析前四个，我们先跳到0x10b750，是mmcpy，我们继续hook mmcy，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_YMTKTQSTAN43FWD.webp)
继续trace分析，0x1271c9e0，定位到，跳转到10b574
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_T4JVDWWVGRGTHBE.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_8SA58G4X6FUCAUH.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_98X67CZ25FYMYVE.webp)
，结果固定为0，前四个字节分析完毕。固定为0，
下面分析剩下的八个字节，上面的trace代码表明地址在0x10b4ec
跳过去！！！，继续hook，00 05 09 04 68 21 94 F2
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_QSMKGQ3FFG9MUKX.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_VTHTZJ5AQ89FMF5.webp)
trace，0xe4ffec74和0xe4ffec70；
emulator.traceWrite(0xe4ffec74L,0xe4ffec74L+4);.在0x16d2d4，00 05 09 04
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_6YSKP46TW6K8XPN.webp)
emulator.traceWrite(0xe4ffec70L,0xe4ffec70L+4);在0x16d2e0，68 21 94 F2
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_ZYCGYQJVQ5FPHX3.webp)
ok啊，最后俩函数都落在了sub_16D204中，先看0x16d2d4
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_GSSGZERZWNT93ZU.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FPXH5U9MF89KN5R.webp)
进去细看，这个函数没有参数，我们hook它的输出看看是不是00 05 09 04，
我们hook x0寄存器来获取它的返回值，这里在它的调用的下一行汇编打断点查看x0寄存器的值
这里我们得到了寄存器信息x0=0x4090500，即函数的返回值。发现输出一样，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_RPRU84K99MD4BGD.webp)
那么这个时候这个函数没有输入，我们怀疑是初始化信息，我们打开全量trace日志搜索这个数据4090500，看它第一次出现在哪里，定位到地址0x0591f8，跳过去
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_AGQHD44BDW669M3.webp)
定位到函数sub_590D4()
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9BMGD862Q878HKZ.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_9P7SYRNFEE37SRX.webp)
hook函数strdup()，读它的地址就是原始字符串即ptr的值；读取到这个地址之后发现是04.09.05，即是初始化时写入的版本号，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_KVTNC5YUKJ9NRWJ.webp)
至此中间四个字节分析完毕，下面分析最后的四个字节,
emulator.traceWrite(0xe4ffec70L,0xe4ffec70L+4);在0x16d2e0，68 21 94 F2
跳到0x16d2e0，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_89ABJ4J456PYX98.webp)
v5就是函数的输入0x16D204，交叉引用比较少。我们直接找它的调用就可以啦
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_XZNXT8EXUT838GB.webp)
跳进去
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_DBFAMUR5PVC9MDH.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FFXN5HD79GGK8XG.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_JBH2FS7MCVUTPE3.webp)
跳到sub_12D504里看看
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_FUHHMRXNB7PZU5H.webp)
再跳sub_12D488
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_VWM2NYV7JZZMYJX.webp)
跟进去看看，一直跟到底，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_HUQEMXPQW7CBQFG.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_EGMY94FYRPDDNAD.webp)

发现是一个返回时间戳的函数，还是个秒级时间戳
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_NN66J97SRYFXE5P.webp)
我们看我们固定的时间戳1747031282，转成hex看一哈，68 21 94 F2完美对上，
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_RQN28BPMZWX4GQG.webp)
后二十个字节至此分析完毕，下面分析前六个字节，回到那张图
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_4QE6CHNPDZRHBZA.webp)
先分析0x84，它来自0x16d1fc，跳过去十进制数124的16进制就是0x84，这里固定
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_GWBWMHUJ5YM4VGM.webp)
再分析0x04它来自0x16d1a0，跳过去看看，发现落在了函数sub_16CEA0内，前面我们分析过，sub_16CEA0是rc4加密所在函数，这里等价于*(_BYTE )((_QWORD *)(*a1 + 16) + 1LL) = 4;，即将缓冲区的第二个字节固定为4
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_U7XF4VZZF9EFT5A.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_MMR2V8TV5FZ49GH.webp)
在分析0x40，跳到0x16d160，这里是将v6的地址的低字节写入第三个字节。
第三字节 0x40 = LOBYTE(v6)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_URY8CW2F59Z3NNE.webp)
第四个字节0xCA，直接跳到0x16d018，分析发现这里是将v6地址的低高字节写入第四个字节
第四字节 0xCA = BYTE1(v6)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_2PAQFRBX8Y7MD95.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_TGQDDRA8WHUAV6U.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_F6ZN26CEZ4WP6DA.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_QXYFAZVVXXXGQ48.webp)
那么这个地址怎么来的呢，我们分析这个函数，根据上面的分析，且buf[2] 写到 0x1271CA42 = v6 + 2
buf[3] 写到 0x1271CA43 = v6 + 3，说明v6就是26字节缓冲区的首地址
回到我们的emulator.traceWrite(0x1271ca40, 0x1271ca40 + 26);，验证0x1271CA40
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/989038_SN3CWNWRDMWDHSA.webp)
剩下最后两个字节0x00和0x00，请求不变，固定，RC4密钥的这篇文章不再分析。
验证完毕，分析结束by console；
至此全文分析完毕，感谢各位大佬写的文章作为参考，这篇文章总耗时15天+，在大四的毕业前完成，就当为自己的青春画个句号吧。

关于作者
26应届本科毕业生，日常研究web逆向，Android 逆向、协议分析、SO加固对抗等。

常用工具链：IDA Pro + Frida + unidbg + AI辅助分析

目前在看机会，逆向/爬虫/移动安全方向均可，欢迎交流：

- 看雪站内私信
- 邮箱：860600441@qq.com

大家如果有问题可以下面留言即可，文章中的错误大家在评论区留言即可，新手小白第一次写文章有错误在所难免

---

# 回复

## 回复 by bluegatar (#2)

*2026-5-10 22:57*

现在用ai是大趋势的

## 回复 by Imxz (#3)

*2026-5-11 15:26*

tql

## 回复 by flyocean (#4)

*2026-5-13 00:25*

![image](https://bbs.kanxue.com/view/img/face/079.gif)![image](https://bbs.kanxue.com/view/img/face/061.gif)![image](https://bbs.kanxue.com/view/img/face/078.gif) 学习了

## 回复 by git_14248bibinocode (#5)

*2026-5-13 10:38*

666

## 回复 by bygrand (#6)

*2026-5-25 11:33*

师傅请教一下这个是哪个版本啊

## 回复 by git_40631tt123-web (#7)

*2026-8-7 11:17*

师傅请教一下这个是哪个版本啊

## 回复 by 随风烟火 (#8)

333

## 回复 by mb_vhrfkkrn (#9)

666

## 回复 by wx_　　　　　　　　_126478 (#10)

666

## 回复 by 小明的爱 (#11)

666

## 回复 by mb_cbgtaveo (#12)

666666

## 回复 by 星落黎明 (#13)

感谢分享

## 回复 by olixina (#14)

感谢分享
