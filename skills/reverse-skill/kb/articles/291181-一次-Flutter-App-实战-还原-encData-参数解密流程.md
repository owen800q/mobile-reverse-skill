---
title: '[原创]一次 Flutter App 实战：还原 encData 参数解密流程'
url: https://bbs.kanxue.com/thread-291181.htm
tid: 291181
author: Mengz3
date: '2026-05-11'
tags: [Android安全, 原创, 逆向分析, 协议分析, HOOK注入]
crawled_at: '2026-07-31T13:52:52+08:00'
replies: 12
---

注：app放在文章末尾，需要自取

## 一、目标

- 分析响应中的 encData 参数
- 判断编码/加密方式
- 还原客户端解密链

## 二、APP初始分析

APP扫描：

```python
[TOOL] APK 扫描输出：
[TOOL] APK检测工具 - 扫描配置:
[TOOL] - 文件路径: xxx
[TOOL] - 检测类型: ROOT(true) 模拟器(true) 反调试(true) 代理(true) SDK(true) 硬编码(false) 证书(true)
[TOOL] - 最大文件大小: 500 MB
[TOOL] - 递归扫描: true
[TOOL] ---------------------------------------------------
[TOOL] 正在扫描APK文件: xxx
[TOOL]
[TOOL]   - 加固特征扫描结果
[TOOL]     - 未发现加固特征
[TOOL]
[TOOL]   - 安全检测特征扫描结果
[TOOL]     - 模拟器检测特征
[TOOL]       - classes.dex -> emulator (模拟器标识)
[TOOL]       - classes.dex -> goldfish (Android模拟器内核标识)
[TOOL]     - 代理检测特征
[TOOL]       - classes.dex -> Ljavax/net/ssl/X509TrustManager; (自定义证书信任管理器)
[TOOL]       - classes.dex -> Ljavax/net/ssl/X509TrustManager; (自定义证书信任管理器)
[TOOL]
[TOOL]   - 第三方SDK特征扫描结果
[TOOL]     - Google
[TOOL]       - Flutter -> lib/arm64-v8a/libapp.so
[TOOL]       - Flutter -> lib/arm64-v8a/libflutter.so
[TOOL]       - Flutter -> lib/armeabi-v7a/libapp.so
[TOOL]       - Flutter -> lib/armeabi-v7a/libflutter.so
[TOOL]       - Flutter -> lib/x86_64/libapp.so
[TOOL]       - Flutter -> lib/x86_64/libflutter.so
[TOOL]     - Huawei
[TOOL]       - HMS Scan Kit -> lib/arm64-v8a/libscannative.so
[TOOL]       - HMS Scan Kit -> lib/armeabi-v7a/libscannative.so
[TOOL]     - Mpv
[TOOL]       - LibMpv -> lib/arm64-v8a/libmpv.so
[TOOL]       - LibMpv -> lib/armeabi-v7a/libmpv.so
[TOOL]       - LibMpv -> lib/x86/libmpv.so
[TOOL]       - LibMpv -> lib/x86_64/libmpv.so
[TOOL]   - 证书扫描结果
[TOOL]     - 未发现证书文件
```

扫描发现flutter框架
搜索界面抓包分析一下
请求包：

```txt
GET /api/search/keyWord?pageSize=20&searchType=1&searchWord=搜索关键字&page=1 HTTP/1.1
user-agent: realme/RE546F/RMX3366/RMX3366_14.0.0.2100(CN01)/android_version=34/chigua_app/ver=2.0.1
deviceid: 3ba82b6df20ef02829ddd378720d220fc1ba74c3
accept: application/json;charset=UTF-8
accept-encoding: gzip
aut: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0NTE5MTc2IiwiaXNzIjoia2RtaDE0IiwiaWF0IjoxNzc4MzQxOTMxLCJuYmYiOjE3Nzg0Nzc0NzcsImV4cCI6MTkzNjE1NzQ3N30.hAoY_3MeAkUDeR5TK5zZSuY4MQMaoSD082z4XtwQrWs
s: 6abe2dc524aa837f52f47e46e9a1e795
host: ojqpi.qbyjhuwtlh.work
content-type: application/json;charset=UTF-8
t: 1778478120170
```

请求包中似乎没有什么重点
看看响应包：

```txt
HTTP/1.1 200
Content-Type: application/json;charset=UTF-8
Transfer-Encoding: chunked
Connection: keep-alive
Server: nginx/1.22.1
Date: Mon, 11 May 2026 05:42:01 GMT
X-XSS-Protection: 1; mode=block
Content-Encoding: gzip
Vary: Accept-Encoding
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-Cache: Miss from cloudfront
Via: 1.1 ce03dab0723e1a81658675d5bdaf168c.cloudfront.net (CloudFront)
X-Amz-Cf-Pop: LAX50-P5
X-Amz-Cf-Id: FtoVgMKtfgc5SOUwWt0ULaV_A3sUDf-g-5YcmF-y_DMZaxxIoeEehw==
Vary: Origin

{"code":200,"msg":"success","encData":"0b/3mMo5VcwmmB+kBXR6tCZ24QWmendkcH8m0YIHs480sWU0QW2EBNyQjOLCup7ieZXHBzDYy+EyFCQ1TfJudJuEkfsYDSAtFYL8RxOhbARbs/58xaOJXUGljd+QtGainfvrw+QX5gOBUNcjzlZJh/kfz9/AycfjzW3NbegRa+BjGNRuL9Wvog2uzh/CIL8u2c4m20RtzMClzzWdQBLO7BKJ3deYUQ7vJFHx0uUkT789LBFqimIv7G1vnFpImiMf9bRuDXDhoQ1NctHy4k6DCpExydq1+DSI0eF6NHxMTXa/wYq7w5iuHLEpEABNBQ82P+ixE/o/FljzIGQkf8+lHpRQrwNp4jxVGnx0wX9czoKc76yoC0wqlFEoBQgZ8nkwDO2dLRUzV2gOciM4lcUqI9fNXv2nPPI2urKJgXs1s0ybBmtGE39/KlywyfdnJvc8advnWpaWsXcm7P0uUXCrkATMX9IFpLqNC9e8XCQVHy/RcqVL6u87pHpiPka4Tlq+zLHBmjIU3GylecFO0azigKH/XGdKJxPUqhoXEOoHvuQojM5Y1PSpxrGegJH4HaFotcS/hnvq6g9xcHjVvk/cZ1oko+XIvsR5Ys46l5ojm31bmZSIGfseJqGGBpBxwZRdv2SItIoLQJiBWIlqJiHVUjQHzcqk2uKl/bykj8nIcYgT8FNDug1V2BH6ykW7ff7Nj+QzQtERrAtCamLOX......这里太长了省略......TkI6sKEkH+K2cbei3SKChigC/UpNwbf0sYVplshbvMkfP2E="}
```

返回了`encData`参数，base64加密后的
b64解不出来，乱码，大概率是经过其他加密的。
结合 Base64 解码失败后的非明文表现，初步怀疑后续仍存在对称解密层（`AES/DES/SM4`），并且数据很长。
使用jadx搜不到`encData`参数，转战so文件
在Flutter架构中：
`libflutter.so` 负责“怎么运行 Flutter”
`libapp.so` 负责“这个 App 具体运行什么逻辑”

## 三、Flutter 场景处理

打开libapp.so之前，先用Blutter还原一下。
Blutter 是 Flutter Android Release App 的 Dart AOT 分析工具，核心价值是帮你从 `libapp.so` 里提取 Object Pool、字符串、符号、汇编和 Frida 模板([worawit/blutter: Flutter Mobile Application Reverse Engineering Tool](https://github.com/worawit/blutter))。具体的使用教程可以问AI或者上网搜索，这里就跳过了

还原后能看一些函数的具体名字，不至于盲目分析。如果直接使用ida 打开libapp.so，所有函数都是sub_开头，几乎无法分析

## 四、响应参数encData分析

在IDA中搜索`encData`
只搜索到一个，发现也没有交叉引用
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_S4PU4PXK4UBQTQY.webp)

这里尝试去hook 调用该地址也没hook到
hook代码：

```JavaScript
const base = Module.findBaseAddress("libapp.so");
const target = base.add(0x91071);
const page = ptr(target).and(ptr(-Process.pageSize));

MemoryAccessMonitor.enable([{ base: page, size: Process.pageSize }], {
    onAccess(details) {
        if (!ptr(details.address).equals(target)) return;

        const from = details.from;
        const m = Process.findModuleByAddress(from);
        if (!m || m.name !== "libapp.so") return;

        console.log("[*] encData hit -> " + from.sub(m.base));
    }
});
```

之前已经知道，参数最后编码成base64，这里搜索一下base64
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_Q46TCKZUQ7T7XVQ.webp)
这里有不少base64相关函数，全部hook一遍，看看谁被调用了，hook的时候打印参数和返回值内存，看看能不能找到`encData`一样的数据。
hook代码：

```JavaScript
// 目标 so 基址
const soName = "libapp.so";
const base = Module.findBaseAddress(soName);

// 安全 dump 内存；失败时返回错误信息，避免脚本中断
function dumpMem(p, size = 0x40) {
    try {
        return hexdump(ptr(p), {
            offset: 0,
            length: size,
            header: true,
            ansi: false
        });
    } catch (e) {
        return "[dump failed] " + e;
    }
}

// 通用 hook：打印参数、参数内存，以及返回值和返回值内存
function hookFunc(off, name) {
    const addr = base.add(off);

    Interceptor.attach(addr, {
        onEnter(args) {
            this.name = name;
            this.off = off;

            console.log("\n[*] " + name + " hit @0x" + off.toString(16));

            for (let i = 0; i < 6; i++) {
                try {
                    console.log("arg" + i + " = " + args[i]);
                } catch (e) {
                    console.log("arg" + i + " = <err>");
                }
            }

            for (let i = 0; i < 6; i++) {
                console.log("\n[arg" + i + " mem]");
                try {
                    console.log(dumpMem(args[i]));
                } catch (e) {
                    console.log("[dump failed] " + e);
                }
            }
        },

        onLeave(retval) {
            try {
                console.log("\n[retval] " + retval);
            } catch (e) {
                console.log("\n[retval] <err>");
            }

            console.log("[retval mem]");
            try {
                console.log(dumpMem(retval));
            } catch (e) {
                console.log("[dump failed] " + e);
            }
        }
    });
}

// Base64 相关关键函数：
// - 编码入口 / 分块编码 / 收尾
// - 解码入口 / 分块解码 / padding 检查
// - 编解码过程中的 stub/辅助函数
const targets = [
    [0x470920, "dart_convert_::base64Encode_470920"],
    [0x3C2470, "dart_convert_Base64Codec::normalize_3c2470"],
    [0x3C2B5C, "dart_convert_Base64Codec::_checkPadding_3c2b5c"],
    [0x3C2CB0, "dart_convert__Base64Decoder::_inverseAlphabet_3c2cb0"],
    [0x4845E0, "dart_convert_Base64Codec::decode_4845e0"],
    [0x88C5E0, "dart_convert_Base64Codec::get_decoder_88c5e0"],
    [0x890988, "dart_convert_Base64Encoder::convert_890988"],
    [0x890A14, "dart_convert__Base64Encoder::encode_890a14"],
    [0x890B14, "dart_convert__Base64Encoder::encodeChunk_890b14"],
    [0x890E7C, "dart_convert__Base64Encoder::writeFinalChunk_890e7c"],
    [0x891040, "Allocate_Base64EncoderStub_891040"],
    [0x89104C, "dart_convert_Base64Decoder::convert_89104c"],
    [0x891130, "dart_convert__Base64Decoder::close_891130"],
    [0x8911E0, "dart_convert__Base64Decoder::decode_8911e0"],
    [0x8912AC, "dart_convert__Base64Decoder::decodeChunk_8912ac"],
    [0x8917BC, "dart_convert__Base64Decoder::_allocateBuffer_8917bc"],
    [0x8918A8, "dart_convert__Base64Decoder::_trimPaddingChars_8918a8"],
    [0x891A08, "dart_convert__Base64Decoder::_checkPadding_891a08"],
    [0x891C60, "Allocate_Base64DecoderStub_891c60"],
];

// 批量安装 hook，失败也继续处理下一个
targets.forEach(([off, name]) => {
    try {
        hookFunc(off, name);
        console.log("[+] hook ok: " + name + " @0x" + off.toString(16));
    } catch (e) {
        console.log("[-] hook fail: " + name + " @0x" + off.toString(16) + " err=" + e);
    }
});
```

结果：
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_XAY7HT4RASVJ862.webp)
Hook的结果发现不少函数参数或者返回值是`encData`
根据 hook 命中结果筛选调用链，观察函数名字，只有`dart_convert_Base64Codec::decode_4845e0`最符合，其他大概率都是此函数下游调用链

```python
- dart_convert_Base64Codec::decode_4845e0
    - arg2 = 0x7201f00069

- dart_convert_Base64Decoder::convert_89104c
    - arg2 = 0x7201f00069

- dart_convert__Base64Decoder::decode_8911e0
    - arg2 = 0x7201f00069

- dart_convert__Base64Decoder::_allocateBuffer_8917bc
    - arg1 = 0x7201f00069
    - arg4 = 0x7201f00069

- dart_convert__Base64Decoder::_trimPaddingChars_8918a8
    - arg1 = 0x7201f00069
    - arg4 = 0x7201f00069

- dart_convert__Base64Decoder::decodeChunk_8912ac
    - arg1 = 0x7201f00069

- dart_convert__Base64Decoder::_checkPadding_891a08
    - arg1 = 0x7201f00069

- dart_convert__Base64Decoder::close_891130
    - arg2 = 0x7201f00069
    - arg4 = 0x7201f00069
```

IDA中搜索看一下`dart_convert_Base64Codec::decode_4845e0`此函数
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_5ZB5R7GEB2XQWJG.webp)
很正常的base64函数，往下追可以追到其他base64函数调用链。
直接X看下此函数的被谁调用，追到了`encrypt_encrypt_Encrypter::decrypt64_484308`
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_74HUER4UYSEFY4R.webp)
这里将base64解密的值大概率传给了最后的return加密函数
hook一下最后return的`encrypt_encrypt_Encrypter::decrypt_48436c()`看下参数和返回值
hook代码：

```JavaScript
const soName = "libapp.so";
const base = Module.findBaseAddress(soName);

function dumpMem(p, size = 0x80) {
    try {
        return hexdump(ptr(p), {
            offset: 0,
            length: size,
            header: true,
            ansi: false
        });
    } catch (e) {
        return "[dump failed] " + e;
    }
}

Interceptor.attach(base.add(0x48436C), {
    onEnter(args) {
        this.hit = true;

        console.log("\n[*] encrypt_encrypt_Encrypter::decrypt_48436c hit @0x48436c");

        for (let i = 0; i < 6; i++) {
            console.log("arg" + i + " = " + args[i]);
        }

        for (let i = 0; i < 6; i++) {
            console.log("\n[arg" + i + " mem]");
            console.log(dumpMem(args[i]));
        }
    },
    onLeave(retval) {
        if (!this.hit) return;

        console.log("\n[retval] " + retval);
        console.log("[retval mem]");
        console.log(dumpMem(retval));
    }
});
```

输出：

```
[*] encrypt_encrypt_Encrypter::decrypt_48436c hit @0x48436c
[JS] arg0 = 0x7200e40529
[JS] arg1 = 0x7200e40509
[JS] arg2 = 0x7200e448e9
[JS] arg3 = 0x7200e40139
[JS] arg4 = 0x7200e44900
[JS] arg5 = 0x7200e7ffe8
[JS]
[arg0 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e40529  40 07 00 00 00 00 00 40 05 e4 00 72 00 00 00 00  @......@...r....
7200e40539  00 00 00 40 87 00 00 d1 bf f7 98 ca 39 55 cc 26  ...@........9U.&
7200e40549  98 1f a4 05 74 7a b4 a3 a2 c2 9d 53 8c 87 68 a4  ....tz.....S..h.
7200e40559  2c 63 52 78 f5 e8 1f 1a 07 a1 73 df 98 7d 85 23  ,cRx......s..}.#
7200e40569  43 77 90 79 65 61 c2 ff 89 cc ed ee 80 ce 13 67  Cw.yea.........g
7200e40579  5a 56 8f e4 7d 30 4a ba 84 d9 6f 4a 59 fb fd 11  ZV..}0J...oJY...
7200e40589  ee e0 62 8a ea ed 76 ec 1d 40 24 38 3d 88 f6 f8  ..b...v..@$8=...
7200e40599  38 77 6c 3c e7 98 d4 3b 0d bc 0d 68 37 d7 f9 91  8wl<...;...h7...
[JS]
[arg1 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e40509  91 ed 00 00 00 00 00 19 02 e4 00 81 80 00 00 1c  ................
7200e40519  f1 28 01 00 00 00 00 ff ff ff ff ff ff ff ff 1c  .(..............
7200e40529  40 07 00 00 00 00 00 40 05 e4 00 72 00 00 00 00  @......@...r....
7200e40539  00 00 00 40 87 00 00 d1 bf f7 98 ca 39 55 cc 26  ...@........9U.&
7200e40549  98 1f a4 05 74 7a b4 a3 a2 c2 9d 53 8c 87 68 a4  ....tz.....S..h.
7200e40559  2c 63 52 78 f5 e8 1f 1a 07 a1 73 df 98 7d 85 23  ,cRx......s..}.#
7200e40569  43 77 90 79 65 61 c2 ff 89 cc ed ee 80 ce 13 67  Cw.yea.........g
7200e40579  5a 56 8f e4 7d 30 4a ba 84 d9 6f 4a 59 fb fd 11  ZV..}0J...oJY...
[JS]
[arg2 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e448e9  a1 ed 00 00 00 00 00 29 05 e4 00 81 80 00 00 81  .......)........
7200e448f9  80 00 00 81 80 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44909  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44919  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44929  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44939  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44949  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44959  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
[JS]
[arg3 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e40139  c1 ed 00 00 00 00 00 e9 01 e4 00 81 80 00 00 1c  ................
7200e40149  c2 27 01 00 00 00 00 10 00 00 00 00 00 00 00 69  .'.............i
7200e40159  01 e4 00 81 80 00 00 81 80 00 00 81 80 00 00 1c  ................
7200e40169  45 07 00 00 00 00 00 80 01 e4 00 72 00 00 00 00  E..........r....
7200e40179  00 00 00 60 00 00 00 4a 68 62 47 63 69 4f 69 4a  ...`...JhbGciOiJ
7200e40189  49 55 7a 49 31 4e 69 00 00 00 00 00 00 00 00 00  IUzI1Ni.........
7200e40199  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e401a9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1c  ................
[JS]
[arg4 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e44900  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44910  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44920  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44930  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44940  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44950  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44960  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e44970  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
[JS]
[arg5 mem]
[JS] [dump failed] Error: access violation accessing 0x7200e80000
[JS]
[retval] 0x7200ed50a9
[JS] [retval mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200ed50a9  f0 05 00 00 00 00 00 48 7c 00 00 00 00 00 00 7b  .......H|......{
7200ed50b9  00 22 00 76 00 69 00 64 00 65 00 6f 00 4c 00 69  .".v.i.d.e.o.L.i
7200ed50c9  00 73 00 74 00 22 00 3a 00 5b 00 7b 00 22 00 76  .s.t.".:.[.{.".v
7200ed50d9  00 69 00 64 00 65 00 6f 00 49 00 64 00 22 00 3a  .i.d.e.o.I.d.".:
7200ed50e9  00 32 00 32 00 30 00 39 00 38 00 38 00 2c 00 22  .2.2.0.9.8.8.,."
7200ed50f9  00 74 00 69 00 74 00 6c 00 65 00 22 00 3a 00 22  .t.i.t.l.e.".:."
7200ed5109  00 20 00 f0 6c fd 56 76 98 a7 7e 63 00 6f 00 73  . ..l.Vv..~c.o.s
7200ed5119  00 65 00 72 00 20 00 48 00 69 00 67 00 68 00 73  .e.r. .H.i.g.h.s
```

可以看到返回值已经将`encData`解密出来了，参数中arg3也有值得关注的，`JhbGciOiJIUzI1Ni`一个16位字符串，这里留意一下可能包含着密钥或者IV信息

### 4.1 加密算法分析：

接下来继续，看能不能找到加密方式/密码/IV之类的信息
往下继续追一下`encrypt_encrypt_Encrypter::decrypt_48436c()`，直接进入函数
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_YW4WN79JKA49QY6.webp)
里面套了一个加密函数`4843b4()`，传入的参数继承自`48436c()`没有变化，接着进入`encrypt_encrypt_Encrypter::decryptBytes_4843b4`去查看
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_H2YMWVFTGYS56QJ.webp)
追到这里就恍然大悟了，AES加密，并且传入的参数也变化了
hook一下`encrypt_encrypt_Encrypter::decryptBytes_48441c()`看看能不能找到一些信息

hook代码(和上一个hook代码一样，只需修改 `0x48436C` --> `0x48441c` 即可)

```javascript
const soName = "libapp.so";
const base = Module.findBaseAddress(soName);

function dumpMem(p, size = 0x80) {
    try {
        return hexdump(ptr(p), {
            offset: 0,
            length: size,
            header: true,
            ansi: false
        });
    } catch (e) {
        return "[dump failed] " + e;
    }
}

Interceptor.attach(base.add(0x48441c), {
    onEnter(args) {
        this.hit = true;

        console.log("\n[*] encrypt_encrypt_Encrypter::decrypt_48441c hit @0x48441c");

        for (let i = 0; i < 6; i++) {
            console.log("arg" + i + " = " + args[i]);
        }

        for (let i = 0; i < 6; i++) {
            console.log("\n[arg" + i + " mem]");
            console.log(dumpMem(args[i]));
        }
    },
    onLeave(retval) {
        if (!this.hit) return;

        console.log("\n[retval] " + retval);
        console.log("[retval mem]");
        console.log(dumpMem(retval));
    }
});
```

输出：

```
[*] encrypt_encrypt_Encrypter::decrypt_48441c hit @0x48441c
[JS] arg0 = 0x7200c8d989
[JS] arg1 = 0x7200c8d989
[JS] arg2 = 0x7200c92059
[JS] arg3 = 0x7200008081
[JS] arg4 = 0x7200c92070
[JS] arg5 = 0x7200c8d8a9
[JS]
[arg0 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200c8d989  d2 ed 00 00 00 00 00 c9 d7 c8 00 11 74 95 00 41  ............t..A
7200c8d999  bb 2d 00 59 dc c8 00 81 80 00 00 81 80 00 00 1c  .-.Y............
7200c8d9a9  a2 05 00 00 00 00 00 81 80 00 00 08 00 00 00 71  ...............q
7200c8d9b9  52 28 00 c1 0e 2f 00 c1 e4 00 00 41 bb 2d 00 5c  R(.../.....A.-.\
7200c8d9c9  e2 05 00 00 00 00 00 1a 00 00 00 00 00 00 00 41  ...............A
7200c8d9d9  45 53 2f 43 42 43 2f 50 4b 43 53 37 00 00 00 1c  ES/CBC/PKCS7....
7200c8d9e9  a2 05 00 00 00 00 00 81 80 00 00 06 00 00 00 01  ................
7200c8d9f9  d2 2d 00 91 13 01 00 c9 d9 c8 00 81 80 00 00 5c  .-.............\
[JS]
[arg1 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200c8d989  d2 ed 00 00 00 00 00 c9 d7 c8 00 11 74 95 00 41  ............t..A
7200c8d999  bb 2d 00 59 dc c8 00 81 80 00 00 81 80 00 00 1c  .-.Y............
7200c8d9a9  a2 05 00 00 00 00 00 81 80 00 00 08 00 00 00 71  ...............q
7200c8d9b9  52 28 00 c1 0e 2f 00 c1 e4 00 00 41 bb 2d 00 5c  R(.../.....A.-.\
7200c8d9c9  e2 05 00 00 00 00 00 1a 00 00 00 00 00 00 00 41  ...............A
7200c8d9d9  45 53 2f 43 42 43 2f 50 4b 43 53 37 00 00 00 1c  ES/CBC/PKCS7....
7200c8d9e9  a2 05 00 00 00 00 00 81 80 00 00 06 00 00 00 01  ................
7200c8d9f9  d2 2d 00 91 13 01 00 c9 d9 c8 00 81 80 00 00 5c  .-.............\
[JS]
[arg2 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200c92059  a1 ed 00 00 00 00 00 99 dc c8 00 81 80 00 00 81  ................
7200c92069  80 00 00 81 80 00 00 00 00 00 00 00 00 00 00 00  ................
7200c92079  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c92089  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c92099  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920a9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920b9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920c9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
[JS]
[arg3 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200008081  b1 0a 00 db 07 00 00 00 00 00 00 00 00 00 00 70  ...............p
7200008091  f1 03 00 14 0d 00 00 00 00 00 00 00 00 00 00 72  ...............r
72000080a1  f1 03 00 cf 04 00 00 01 00 00 00 00 00 00 00 72  ...............r
72000080b1  f1 03 00 d5 04 00 00 00 00 00 00 00 00 00 00 30  ...............0
72000080c1  56 00 00 ef 14 00 00 11 f2 00 00 81 80 00 00 81  V...............
72000080d1  80 00 00 81 80 00 00 81 80 00 00 81 80 00 00 81  ................
72000080e1  80 00 00 81 80 00 00 81 80 00 00 81 80 00 00 81  ................
72000080f1  80 00 00 81 80 00 00 81 80 00 00 81 80 00 00 05  ................
[JS]
[arg4 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200c92070  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c92080  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c92090  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920a0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920b0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920c0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920d0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c920e0  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
[JS]
[arg5 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200c8d8a9  c1 ed 00 00 00 00 00 59 d9 c8 00 81 80 00 00 1c  .......Y........
7200c8d8b9  c2 27 01 00 00 00 00 10 00 00 00 00 00 00 00 d9  .'..............
7200c8d8c9  d8 c8 00 81 80 00 00 81 80 00 00 81 80 00 00 1c  ................
7200c8d8d9  45 07 00 00 00 00 00 f0 d8 c8 00 72 00 00 00 00  E..........r....
7200c8d8e9  00 00 00 60 00 00 00 4a 68 62 47 63 69 4f 69 4a  ...`...JhbGciOiJ
7200c8d8f9  49 55 7a 49 31 4e 69 00 00 00 00 00 00 00 00 00  IUzI1Ni.........
7200c8d909  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200c8d919  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1c  ................
[JS]
[retval] 0x7200d091b9
[JS] [retval mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200d091b9  40 07 00 00 00 00 00 d0 91 d0 00 72 00 00 00 00  @..........r....
7200d091c9  00 00 00 28 87 00 00 7b 22 76 69 64 65 6f 4c 69  ...(...{"videoLi
7200d091d9  73 74 22 3a 5b 7b 22 76 69 64 65 6f 49 64 22 3a  st":[{"videoId":
7200d091e9  32 32 30 39 38 38 2c 22 74 69 74 6c 65 22 3a 22  220988,"title":"
7200d091f9  20 e6 b3 b0 e5 9b bd e9 a1 b6 e7 ba a7 63 6f 73   ............cos
7200d09209  65 72 20 48 69 67 68 73 73 74 6e 20 e9 ab 98 e9  er Highsstn ....
7200d09219  a2 9c e5 80 bc e5 a4 a7 e5 a5 b6 e5 b0 a4 e7 89  ................
7200d09229  a9 20 e5 92 8c e7 98 a6 e7 8c b4 e7 94 b7 e5 8f  . ..............
```

在 `encrypt_encrypt_AES::decrypt_48441c` 的参数 dump 中，可以明确观察到 `AES/CBC/PKCS7` 字样，说明该响应字段的核心解密算法可定位为 `AES-CBC-PKCS7`。
同时，在参数内存中还出现了 `JhbGciOiJIUzI1Ni` 这一字符串片段，其与请求头 aut 中 JWT 头部内容一致，说明认证材料可能参与了解密流程或参数构造，这里猜测为密钥或者IV；返回值也是解密的正常可见字符串结果。
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_BQKUWUTAC6SKJ7P.webp)

### 4.2 密钥和IV

接下来目标是确定密钥和IV的具体值
经过长时间的分析，我们返回到`encrypt_encrypt_Encrypter::decrypt64_484308()`来分析
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_S2JZB8GZFCXUQKF.webp)
刚才在分析的时候，我们hook了`48436c()`，hook结果中已经发现了`JhbGciOiJIUzI1Ni`字符串：

```
[arg3 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
7200e40139  c1 ed 00 00 00 00 00 e9 01 e4 00 81 80 00 00 1c  ................
7200e40149  c2 27 01 00 00 00 00 10 00 00 00 00 00 00 00 69  .'.............i
7200e40159  01 e4 00 81 80 00 00 81 80 00 00 81 80 00 00 1c  ................
7200e40169  45 07 00 00 00 00 00 80 01 e4 00 72 00 00 00 00  E..........r....
7200e40179  00 00 00 60 00 00 00 4a 68 62 47 63 69 4f 69 4a  ...`...JhbGciOiJ
7200e40189  49 55 7a 49 31 4e 69 00 00 00 00 00 00 00 00 00  IUzI1Ni.........
7200e40199  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
7200e401a9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1c  ................
```

因为猜测这里大概率是密钥或者IV，但是在调用此函数时已经生成了这个字符串了，是`48436c()`的参数，说明密钥/IV的生成函数还在前面
X追一下`encrypt_encrypt_Encrypter::decrypt64_484308()`的调用链
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_5VYJ9BJGNTXHNRK.webp)
这里直接发现了Key和IV

第一个红框中的每一行代码的解释：
 1.分配一个 **Key 对象**。
 2.把前面 substring() 的结果取出来，放到 v18。
 3.把这个 Key 对象保存到局部变量里，后面还要继续用。
 4.Key.fromUtf8(sub)

第二个红框中的每一行代码的解释：
 1.分配一个 **IV 对象**。
 2.把前面 substring() 的结果取出来，放到 v20。
 3.把这个 IV 对象保存到局部变量里，后面还要继续用。
 4.IV.fromUtf8(sub)

再往上看代码，无论是v18还是v20都是从一个变量里被赋值的，这样就能解释了`Key`和`IV`的值一样

```c
//伪代码：
String s = StorageService.read(...);
String sub = s.substring(2, 36);

Key key = Key.fromUtf8(sub);
IV iv   = IV.fromUtf8(sub);

AES aes = new AES(key);
Encrypter encrypter = new Encrypter(aes);

String plain = encrypter.decrypt64(encData, iv);
return jsonDecode(plain);
```

- StorageService::_read_456074：读取本地存储值
- substring_3afbf8：固定切片
- AllocateKeyStub + ctor_fromUtf8：构造 key
- AllocateIVStub + ctor_fromUtf8：构造 iv
- decrypt64：对 encData 做 base64 + AES 解密

实在不放心的话，可以hook一下`encrypt_encrypt_Encrypted::ctor_fromUtf8_4ac39c()`，用之前hook的代码，改个地址就可以
输出截取关键部分：

```
第一次hook到4ac39c():
[arg2 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
720129c5b9  e2 05 00 00 00 00 00 20 00 00 00 00 00 00 00 4a  ....... .......J
720129c5c9  68 62 47 63 69 4f 69 4a 49 55 7a 49 31 4e 69 1c  hbGciOiJIUzI1Ni.
720129c5d9  b1 ed 00 00 00 00 00 81 80 00 00 81 80 00 00 81  ................
720129c5e9  80 00 00 81 80 00 00 00 00 00 00 00 00 00 00 00  ................
720129c5f9  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
720129c609  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
720129c619  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
720129c629  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................

第二次hook到4ac39c():
[arg2 mem]
[JS]              0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
720129c5b9  e2 05 00 00 00 00 00 20 00 00 00 00 00 00 00 4a  ....... .......J
720129c5c9  68 62 47 63 69 4f 69 4a 49 55 7a 49 31 4e 69 1c  hbGciOiJIUzI1Ni.
720129c5d9  b1 ed 00 00 00 00 00 89 c6 29 01 81 80 00 00 1c  .........)......
720129c5e9  c2 27 01 00 00 00 00 10 00 00 00 00 00 00 00 09  .'..............
720129c5f9  c6 29 01 81 80 00 00 81 80 00 00 81 80 00 00 1c  .)..............
720129c609  45 07 00 00 00 00 00 20 c6 29 01 72 00 00 00 00  E...... .).r....
720129c619  00 00 00 60 00 00 00 4a 68 62 47 63 69 4f 69 4a  ...`...JhbGciOiJ
720129c629  49 55 7a 49 31 4e 69 00 00 00 00 00 00 00 00 00  IUzI1Ni.........
```

这里完全可以证明key和iv是一个值，都是`JhbGciOiJIUzI1Ni`

最后解密验证一下
 ![image](https://bbs.kanxue.com/upload/attach/202605/962430_38BRK9V4HBSMC8Q.webp)
解密一下，结果出来了。

## 五、结论

- encData 处理链为：

	- Base64 decode
	- AES/CBC/PKCS7 decrypt
	- UTF8 decode / jsonDecode
- key / iv 来源于本地存储固定切片
- key 与 iv 在当前函数中来源相同

---

懂的都懂：WVVoU01HTklUVFpNZVRrelpESkdNV1ZwTlhOWlZ6VTJZak5XTTB4dFRuWmlVemx3Vmtob2JsbDZUbmRaZW14dFRXMW5TelZoSzBjMU5rTkNUMnBLZGsxVVRUMD0=

---

推荐一下比较好用的 Frida 工具：[Frida-Hookers](https://github.com/Mengz3/Frida-Hookers)

---

# 回复

## 回复 by wx_老夫_473 (#2)

*2026-5-11 22:25*

楼主有没有遇到过hook flutter应用，用blutter还原后，里面所有的.build方法的地址都hook不到，只有main.dart里面的方法能hook到

## 回复 by Mengz3 (#3)

*2026-5-12 00:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_老夫_473](https://bbs.kanxue.com/user-954714.htm)
>  楼主有没有遇到过hook flutter应用，用blutter还原后，里面所有的.build方法的地址都hook不到，只有main.dart里面的方法能hook到
>

抱歉，目前没有遇到过，可能还没接触到吧

## 回复 by 天涯共何时 (#4)

*2026-5-13 09:39*

666666

## 回复 by 天涯共何时 (#5)

*2026-5-13 09:43*

失效了呢 楼主 找不到在哪

## 回复 by Mengz3 (#6)

*2026-5-13 10:25*

>
> [天涯共何时](https://bbs.kanxue.com/user-986202.htm)
>  失效了呢 楼主 找不到在哪
>

已更新

## 回复 by 黑色心跳 (#7)

*2026-5-22 15:56*

请问楼主的apk扫描工具用的是什么啊，感觉挺不错的![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by Mengz3 (#8)

*2026-5-23 00:48*

>
> [黑色心跳](https://bbs.kanxue.com/user-1057014.htm)
>  请问楼主的apk扫描工具用的是什么啊，感觉挺不错的[em_003]
>

https://github.com/moyuwa/ApkCheckPack

## 回复 by 超爱大户爱 (#9)

*2026-5-23 16:25*

blutter生成的ida脚本，在ida9.x上执行会报错吧，因为他用的是7.x的api，楼主是怎么解决这个问题的？

## 回复 by Savoor (#10)

*2026-5-31 19:58*

很有用，感谢分享

## 回复 by Cure. (#11)

*2026-6-1 00:08*

>
> [超爱大户爱](https://bbs.kanxue.com/user-927014.htm)
>  blutter生成的ida脚本，在ida9.x上执行会报错吧，因为他用的是7.x的api，楼主是怎么解决这个问题的？
>
>

让ai改就行

## 回复 by 揰掵佲 (#12)

*2026-6-29 03:17*

感谢分享

## 回复 by mb_yyvcbkli (#13)

*2026-7-2 06:35*

学习先进经验
