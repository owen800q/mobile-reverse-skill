---
title: '[原创]某手游逆向全流程复盘：从 IL2CPP Dump 到 TCP 握手协议还原'
url: https://bbs.kanxue.com/thread-290459.htm
tid: 290459
author: 梧桐生
date: '2026-03-22'
tags: [Android安全, 原创, 协议分析]
crawled_at: '2026-07-31T15:12:48+08:00'
replies: 154
---

# 某手游逆向全流程复盘：从 IL2CPP Dump 到 TCP 握手协议还原

## 0x00 前言

本文记录了对某款基于 Unity 引擎（IL2CPP 编译）手游的完整逆向分析过程，涵盖运行时 Dump、网络协议识别、加密逻辑还原、握手流程分析，以及隐藏在脚本引擎中的业务逻辑挖掘。

文章以过程复盘为主，保留了实际分析中的弯路与回溯，力求真实还原研究思路。目标游戏已脱敏处理。

**分析环境：**

- 设备：Android 物理机
- 抓包：SunnyNet抓包工具
- 主要工具：frida-il2cpp-bridge、CyberChef、Python（pycryptodome）

---

## 0x01 初步抓包与流量特征识别

启动游戏后第一步是被动观察流量，用 SunnyNet 抓取全量网络数据，确认游戏是否走 TCP。启动后很快能看到若干条 TCP 长连接建立，选取其中持续有数据交互的连接，结合游戏内操作（日常任务或者日常关卡等）观察流量是否随操作变化——数据量明显跟随操作波动，确认这条 TCP 连接就是游戏主逻辑信道。

看原始字节流，能很快发现一个规律：每个数据包前固定以 `45 67` 开头，结尾固定是 `89 AB`，中间内容随操作变化且不可读。Magic 头尾明确，说明是自定义二进制协议，中间部分大概率经过加密或压缩处理。把这两个特征记下来，后续在代码里定位包结构时会直接用到。 ![image](https://bbs.kanxue.com/upload/attach/202603/922433_ACYZESVWM5ZQSMF.webp)

---

## 0x02 APK 检查与 Dump 方案选择

把 APK 解包后，第一步检查 `global-metadata.dat` 的文件头。标准未加固的 IL2CPP metadata 文件头是固定的 magic（`AF 1B B1 FA`），但这里头部字节不符，判断 metadata 要么被加密，要么做了自定义结构处理。走常规 Il2CppDumper 静态分析这条路行不通。 ![image](https://bbs.kanxue.com/upload/attach/202603/922433_FJ7E2MKVSUFBDXG.webp)

转换思路，改用运行时 dump。注入 frida-il2cpp-bridge，等 IL2CPP runtime 在内存中完成自解密并初始化后，由脚本直接从内存里 dump 出 `dump.cs`。注入时机很关键，太早 runtime 还没完成初始化，太晚可能触发反调试，需要根据游戏启动流程适当调整 attach 时机。最终成功拿到 cs 文件。

---

## 0x03 从 dump.cs 定位数据包结构

拿到 `dump.cs` 之后，回过头来用抓包看到的特征做索引。直接搜 `4567` 和 `89AB` 没有结果——想到这类常量在 C# 里可能以十进制保存，换算后搜对应十进制值，找到了：

```csharp
// MoleMole.PacketDefine
const int HEAD_MAGIC = 17767;  // 0x4567
const int TAIL_MAGIC = 35243;  // 0x89AB
```

定位到 `MoleMole` 命名空间下，顺藤摸瓜翻相关类，重点关注两个工具类：`MoleMole.AesUtils` 和 `MoleMole.Crc32Utils`。

---

## 0x04 动态验证加密位置

写 Frida 脚本分别 hook 两个工具类的方法，打印调用日志，结合抓包时间线对比：

- `Crc32Utils` 相关方法始终没有调用记录，排除 CRC 完整性校验的可能。
- `AesUtils` 的加密/解密方法有稳定调用，且调用时机与抓包数据发出时间吻合。

交叉比对 hook 日志里的明文输入和抓包的密文输出，确认数据包中间的不可读部分确实是 AES 加密的结果。

```python
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {

  const Assembly = Il2Cpp.domain.assembly("Assembly-CSharp");

  const AESUtils = Assembly.image.class('MoleMole.AESUtils');
  const Encrpt = AESUtils.method('Encrpt');
  const Decrpt = AESUtils.method('Decrpt');
  // static System.Byte[] Decrpt(System.Byte[] encrypted, System.Byte[] key);
  Decrpt.implementation = function (encrypted, key) {

    console.log("=== AESUtils.Decrpt Hooked ===");

    // 打印参数
    const encBytes = arrayToBytes(encrypted);
    const keyBytes = arrayToBytes(key);
    console.log("Decrypting:", bytesToHex(encBytes));
    console.log("Key:", bytesToHex(keyBytes));

    // 调用原始函数
    const result = Decrpt.invoke(encrypted, key);

    // 打印结果
    console.log("Decrypted:", bytesToHex(arrayToBytes(result)));
    console.log("==============================");
    return result
  };

  Encrpt.implementation = function (encrypted, key) {

    console.log("=== AESUtils.Encrpt Hooked ===");

    // 打印参数
    const encBytes = arrayToBytes(encrypted);
    const keyBytes = arrayToBytes(key);
    console.log("Encrypting:", bytesToHex(encBytes));
    console.log("Key:", bytesToHex(keyBytes));

    // 调用原始函数
    const result = Encrpt.invoke(encrypted, key);

    // 打印结果
    console.log("Encrypted:", bytesToHex(arrayToBytes(result)));
    console.log("==============================");
    return result
  };
});
```

---

## 0x05 IV 与 Key 分析

### IV

重启游戏，多次打印 `AesUtils` 加密调用时类内的 IV 字段——每次启动值相同，确认 IV 是静态固定的。这里有两种验证手段：一是直接 hook `AesUtils` 的方法打印类字段，二是下沉到 native 层 hook AES 初始化点（如 `AES_init_ctx_iv` 或 mbedtls 对应接口），两种方式拿到的值一致。

### Key

重启游戏后发现 key 每次不同，且没有明显规律，不像是简单的时间戳或随机种子生成。打印调用栈，发现收包和发包走的 key 不同，最终在 `MoleMole.TcpAsyncClient` 里找到两个字段：

```csharp
MoleMole.TcpAsyncClient
    System.Byte[] session_read_key_;   // offset 0xa8
    System.Byte[] session_write_key_;  // offset 0xb0
```

读写 key 分离，说明是握手后协商的 session key。key 的来源悬而未决，需要从握手流程里继续找。

```ts
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
  const AesTransform = Il2Cpp.domain.assembly("System.Core").image.class("System.Security.Cryptography.AesTransform");
    // Hook the constructor to capture key and IV
  const ctor = AesTransform.method(".ctor");
  ctor.implementation = function (algo, encryption, key, iv) {
    console.log("==============================");
    console.log("[AesTransform Constructor]");
    console.log("Encryption mode: " + encryption);
    // Key and IV are Il2Cpp.Array<byte>
    if (key) {
      const keyBytes = new Uint8Array(key.handle.readByteArray(key.length));
      console.log("Key (hex): " + bytesToHex(arrayToBytes(key)));
      console.log("Key length: " + key.length);
    }
    if (iv) {
      const ivBytes = new Uint8Array(iv.handle.readByteArray(iv.length));
      console.log("IV (hex): " + bytesToHex(arrayToBytes(iv)));
      console.log("IV length: " + iv.length);
    }
    console.log("==============================");
    return this.method('.ctor').invoke(algo, encryption, key, iv);
  };
});
```

---

## 0x06 组包结构还原

从调用栈继续往上追，`AesUtils.Encrypt` 的调用方是 `MoleMole.NetPacket.SerializeSec`。这个函数内部大量通过 `System.IO.MemoryStream` 做字节拼接，但调用都是通过计算偏移间接发起的（IL2CPP 的 vtable 调用方式），没有直接可读的符号。
通过hook跳转点并减去libil2cpp地址可以得到函数地址来确定具体调用的函数。
整体逻辑是生成4567，然后拿到调用`MoleMole.NetPacket`的`k__BackingField`字段做cmdid，接下来调用`MoleMole.NetPacket`的`Head`的`CalculateSize`函数确定part1的长度并转成字节，然后通过调用`MoleMole.NetPacket`的`Body`的`get_Length`函数确定part2的长度并转成字节，接着拼接`Head`和`Body`后调用`MoleMole.AESUtils`的`Encrpt`加密，再生成89ab后将前面所有的内容都用`System.IO.MemoryStream`的`Write`拼接到一起

```csharp
// Assembly-CSharp
class MoleMole.NetPacket : System.Object, System.IDisposable
{
    System.UInt16 <cmdId>k__BackingField; // 0x10
    Baseproto.PacketHead Head; // 0x18
    System.IO.MemoryStream Body; // 0x20
```

```c
__int64 __fastcall sub_2CDB4C0(__int64 a1, __int64 *a2, __int64 *a3)
{
  __int64 v6; // x0
  __int64 result; // x0
  __int64 v8; // x22
  __int64 v9; // x23
  unsigned int v10; // w24
  __int64 v11; // x22
  __int64 v12; // x23
  unsigned int v13; // w24
  unsigned int v14; // w0
  __int64 v15; // x22
  unsigned int v16; // w24
  __int64 v17; // x23
  unsigned int v18; // w24
  __int64 v19; // x22
  unsigned int v20; // w0
  __int64 v21; // x22
  unsigned int v22; // w24
  __int64 v23; // x23
  unsigned int v24; // w24
  __int64 v25; // x22
  __int64 v26; // x21
  __int64 v27; // x0
  __int64 v28; // x20
  __int64 v29; // x21
  __int64 v30; // x0
  __int64 v31; // x21
  __int64 v32; // x19
  __int64 v33; // x20
  unsigned int v34; // w21

  if ( (byte_A5674D1 & 1) == 0 )
  {
    sub_292804C(69884);
    byte_A5674D1 = 1;
  }
  if ( (IsPatched_3702264(2967, 0) & 1) != 0 )
  {
    v6 = sub_37021C4(2967, 0);
    if ( !v6 )
      sub_2954148();
    return sub_2A1F5DC(v6, a1, a2, a3, 0);
  }
  else
  {
    result = *a2;
    if ( *a2 )
    {
      if ( *(a1 + 0x20) )
      {
        (*(*result + 760LL))(result, 0, *(*result + 768LL));
        if ( !*a2 )
          sub_2954148();
        (*(**a2 + 504LL))(*a2, 0, *(**a2 + 512LL));
        v8 = *a2;
        if ( (*(qword_A43BEB8 + 295) & 2) != 0 && !*(qword_A43BEB8 + 216) )
          il2cpp_runtime_class_init_0(qword_A43BEB8);
        v9 = GetBytesNetworkdThread(0x4567u);
        if ( (*(qword_A426770 + 295) & 2) != 0 && !*(qword_A426770 + 216) )
          il2cpp_runtime_class_init_0(qword_A426770);
        v10 = sub_45C78DC(0x4567, System_Int32);
        if ( !v8 )
          sub_2954148();
        (*(*v8 + 808LL))(v8, v9, 0, v10, *(*v8 + 816LL));
        v11 = *a2;
        v12 = GetBytesNetworkdThread(*(a1 + 0x10));
        v13 = sub_45C78DC(*(a1 + 0x10), System_Int32);
        if ( !v11 )
          sub_2954148();
        (*(*v11 + 808LL))(v11, v12, 0, v13, *(*v11 + 816LL));
        if ( !*(a1 + 0x18) )
          sub_2954148();
        v14 = CalculateSize(*(a1 + 0x18));
        v15 = *a2;
        v16 = v14;
        v17 = GetBytesNetworkdThread(v14);
        v18 = sub_45C78DC(v16, System_Int32);
        if ( !v15 )
          sub_2954148();
        (*(*v15 + 808LL))(v15, v17, 0, v18, *(*v15 + 816LL));
        v19 = *(a1 + 0x20);
        if ( !v19 )
          sub_2954148();
        v20 = (*(*v19 + 0x1D8LL))(*(a1 + 0x20), *(*v19 + 0x1E0LL));
        v21 = *a2;
        v22 = v20;
        v23 = GetBytesNetworkdThread_0(v20);
        v24 = sub_45C79C0(v22, qword_A4A6F50);
        if ( !v21 )
          sub_2954148();
        (*(*v21 + 808LL))(v21, v23, 0, v24, *(*v21 + 816LL));
        v25 = sub_2962ABC(System_IO_MemoryStream);
        System_IO_MemoryStream_ctor(v25);
        Google_Protobuf_MessageExtensions_WriteTo(*(a1 + 0x18), v25);
        v26 = *(a1 + 0x20);
        if ( !v26 )
          sub_2954148();
        (*(*v26 + 0x388LL))(v26, v25, *(*v26 + 912LL));
        if ( !v25 )
          sub_2954148();
        v27 = (*(*v25 + 888LL))(v25, *(*v25 + 896LL));
        v28 = *a3;
        v29 = v27;
        if ( (*(qword_A43BD60 + 295) & 2) != 0 && !*(qword_A43BD60 + 216) )
          il2cpp_runtime_class_init_0(qword_A43BD60);
        v30 = MoleMole_AESUtils_Encrpt(v29, v28);
        v31 = *a2;
        if ( !v30 )
          sub_2954148();
        if ( !v31 )
          sub_2954148();
        (*(*v31 + 808LL))(*a2, v30, 0, *(v30 + 24), *(*v31 + 816LL));
        v32 = *a2;
        v33 = GetBytesNetworkdThread(0x89ABu);
        v34 = sub_45C78DC(0x89AB, System_Int32);
        if ( !v32 )
          sub_2954148();
        (*(*v32 + 808LL))(v32, v33, 0, v34, *(*v32 + 816LL));
        return 1;
      }
      else
      {
        return 0;
      }
    }
  }
  return result;
}
```

```ts
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
  // 找到 System.IO.MemoryStream 类
  const mscorlibAssembly = Il2Cpp.domain.tryAssembly("mscorlib") || Il2Cpp.domain.tryAssembly("System");
  if (!mscorlibAssembly) {
    console.error("mscorlib or System assembly not found!");
    return;
  }

  const MemoryStreamClass = mscorlibAssembly.image.tryClass("System.IO.MemoryStream");
  if (!MemoryStreamClass) {
    console.error("MemoryStream class not found!");
    return;
  }

  // Hook Write(byte[] buffer, int offset, int count)
  const WriteMethod = MemoryStreamClass.tryMethod("Write", 3);
  if (WriteMethod) {
    WriteMethod.implementation = function (buffer, offset, count) {
      const hexString = bytesToHex(arrayToBytes_len(buffer, offset + count));

      // 判断以 "4567" 开头 且 长度 > 12
      if (hexString.startsWith("4567") && hexString.length > 12) {
        console.log("[HOOK] MemoryStream.Write called");
        console.log(`Buffer length: ${buffer.length}, Offset: ${offset}, Count: ${count}`);
        console.log(`Write data (hex): ${hexString}`);
      }

      return this.method("Write", 3).invoke(buffer, offset, count);
    };
    console.log("MemoryStream.Write hooked successfully!");
  } else {
    console.error("Write method not found!");
  }

  const GetBuffer = MemoryStreamClass.tryMethod("GetBuffer", 0);
  if (GetBuffer) {
    GetBuffer.implementation = function (stream: Il2Cpp.Object) {
      const length = this.method("get_Length").invoke();
      const ret = this.method("GetBuffer").invoke();

      const hexString = bytesToHex(arrayToBytes_len(ret, length));

      // 判断 hexString 是否以4567开头 且长度 > 12
      if (hexString.startsWith("4567") && hexString.length > 12) {
        console.log("[HOOK] MemoryStream.GetBuffer called");
        console.log(`Length: ${length}`);
        console.log(`GetBuffer data (hex): ${hexString}`);
      }

      return ret;
    };

    console.log("MemoryStream.GetBuffer hooked successfully!");
  } else {
    console.error("WriteTo method not found!");
  }
});
```

处理方式：hook 各处 `MemoryStream.Write` 调用点，打印调用地址，减去对应模块基址，再拿偏移去 `dump.cs` 里查对应方法名，逐步还原出拼接顺序。结合 `CalculateSize`（protobuf 标准方法）的调用位置，最终确认数据包结构如下：

```python
┌─────────────┬───────────┬─────────────┬─────────────┬────────────────────┬──────────────┐
│  45 67      │  cmd_id   │ len(part1)  │ len(part2)  │  encrypted_body    │  89 AB       │
│  HEAD_MAGIC │  (2B)     │  (2B)       │  (4B)       │  AES 加密 pb       │  TAIL_MAGIC  │
└─────────────┴───────────┴─────────────┴─────────────┴────────────────────┴──────────────┘
```

body 在加密前分为 part1 和 part2 两段：part1 是连接级别的元数据，与整条 TCP 连接的生命周期绑定；part2 是业务逻辑 payload，随 cmdid 变化而变化。

---

## 0x07 握手流程与 Session Key 协商

### 发现未加密的握手包

在组包结构确认之后，重新审视 TCP 连接建立初期的数据包。观察到连接建立后最初的 4 个数据包 body 部分是明文——没有走 `SerializeSec` 的加密流程。用 CyberChef 对 body 做 protobuf raw decode，能正常解析出标准 pb 结构，字段清晰可读，确认握手阶段数据是明文 pb 传输。

### cmdid=0x0066：密钥交换包

把 cmdid 对应到 `dump.cs` 里的 proto message 类逐包分析。在 `cmdid=0x0066` 的 part1 中，发现两段长度均为 256 字节的 bytestring。256 字节即 2048 bit，结合字段的上下文语义，合理推测这里使用了 RSA-2048 进行密钥交换。

```python
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
  const PacketHead = Assembly.image.class('Baseproto.PacketHead');
  const Session1 = PacketHead.method("set_SessionValue1");
  console.log("找到方法: set_SessionValue1 ->", Session1);

  Session1.implementation = function (value: Il2Cpp.Object) {
    console.log("=== Hook set_SessionValue1 ===");

    // 获取 ByteString 对象
    const bsObj = value as Il2Cpp.Object;

    // 尝试调用 ToByteArray() 获取原始 bytes
    let bytes = null;
    if (bsObj.class.method("ToByteArray")) {
      try {
        bytes = bsObj.method("ToByteArray").invoke(); // 返回 byte[] 类型
        console.log("ByteString 长度:", bytes.length);
        // 可以进一步将 bytes 转为 hex 或 base64 打印
        console.log("Bytes (hex):", bytesToHex(arrayToBytes(bytes)));
      } catch (e) {
        console.warn("调用 ToByteArray 失败:", e);
      }
    }

    // 调用原始 setter 函数
    const ret = this.method("set_SessionValue1").invoke(value);

    console.log("=== End Hook ===");
    return ret;
  };

  const Session2 = PacketHead.method("set_SessionValue2");
  console.log("找到方法: set_SessionValue2 ->", Session2);

  Session2.implementation = function (value: Il2Cpp.Object) {
    console.log("=== Hook set_SessionValue2 ===");

    // 获取 ByteString 对象
    const bsObj = value as Il2Cpp.Object;

    // 尝试调用 ToByteArray() 获取原始 bytes
    let bytes = null;
    if (bsObj.class.method("ToByteArray")) {
      try {
        bytes = bsObj.method("ToByteArray").invoke(); // 返回 byte[] 类型
        console.log("ByteString 长度:", bytes.length);
        // 可以进一步将 bytes 转为 hex 或 base64 打印
        console.log("Bytes (hex):", bytesToHex(arrayToBytes(bytes)));
      } catch (e) {
        console.warn("调用 ToByteArray 失败:", e);
      }
    }

    // 调用原始 setter 函数
    const ret = this.method("set_SessionValue2").invoke(value);

    console.log("=== End Hook ===");
    return ret;
  };
});
```

hook `System.Security.Cryptography` 的底层 RSA 实现，打印 `RSAParameters` 结构体内容，可以直接拿到完整的公私钥参数：

```csharp
// mscorlib
struct System.Security.Cryptography.RSAParameters : System.ValueType
{
    System.Byte[] Exponent; // 0x10    // 公钥参数
    System.Byte[] Modulus; // 0x18
    System.Byte[] P; // 0x20    // 私钥参数
    System.Byte[] Q; // 0x28
    System.Byte[] DP; // 0x30
    System.Byte[] DQ; // 0x38
    System.Byte[] InverseQ; // 0x40
    System.Byte[] D; // 0x48

}
```

用 Python 从这些参数还原密钥：

```python
from Crypto.PublicKey import RSA

key = RSA.construct((
    int.from_bytes(modulus, 'big'),
    int.from_bytes(exponent, 'big'),
    int.from_bytes(d, 'big'),
    int.from_bytes(p, 'big'),
    int.from_bytes(q, 'big'),
))
```

用私钥解密两段 256 字节的 bytestring，分别得到两串 16/32 字节的数据——正是后续通信使用的 `session_read_key_` 和 `session_write_key_`。至此 key 的来源完全清晰。

### cmdid=0x0067：客户端身份确认包

`cmdid=0x0067` 是客户端的回包，part1 中包含用本地私钥加密的数据，发送至服务端做身份验证。本地私钥是设备级别唯一的，推测是首次运行时生成并持久化存储的密钥对，公钥在注册/登录阶段已上传服务端。这一步完成后，双方持有相同的 session key，后续所有数据包切换为 AES 加密传输。

### 握手时序

```python
Client                               Server
  │                                    │
  │──[0x0066] 明文 pb ──────────────>  │  发送： token和设备ID
  │                                    │
  │  <──────────── 明文 pb [0x0066]──  │  回应RSA 加密的key（read + write）
  │                                    │
  │──[0x0067] 明文 pb ──────────────>  │  发送：本地私钥加密的身份数据
  │                                    │
  │  <──────────── 明文 pb [0x0067]──  │  服务端确认，握手完成
  │                                    │
  │══════════ 后续全部 AES 加密 ═══════│
```

```ts
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
  const Assembly = Il2Cpp.domain.assembly("Assembly-CSharp");
  const TcpAsyncClient = Assembly.image.class('MoleMole.TcpAsyncClient');
  const send = TcpAsyncClient.method('send');
  send.implementation = function (packet) {
    const cmdId   = packet.method('get_cmdId').invoke();
    const ret = this.method("send").invoke(packet);
    const bodyArr = packet.method('getBody').invoke().method("ToArray").invoke();
    const hexBody = bytesToHex(arrayToBytes_len(bodyArr, bodyArr.length));

    console.log(
      "=== Hook send ===\n" +
      "cmdId = " + cmdId + "\n" +
      "send ==> " + hexBody
    );

    return ret;
  };
});

  function arrayToBytes(arr: Il2Cpp.Array<Il2Cpp.Byte>): number[] {
    const result: number[] = [];
    for (let i = 0; i < arr.length; i++) {
      result.push(arr.get(i));
    }
    return result;
  }

  function arrayToBytes_len(arr,length): number[] {
    const result: number[] = [];
    for (let i = 0; i < length; i++) {
      result.push(arr.get(i));
    }
    return result;
  }
```

---

## 0x08 业务逻辑层：发现 Puerts JS 脚本引擎

### cmdid 对不上的异常

在分析具体业务包时，发现部分 cmdid 在 `dump.cs` 里完全查不到对应的 protobuf 类定义——既没有 message 类，也没有相关的 encode/decode 调用。排查方向首先是 xlua：hook xlua 相关入口没有命中，排除。

继续翻 `dump.cs`，在命名空间里发现了 `Puerts` 相关的类。Puerts 是腾讯开源的在 Unity 里嵌入 JavaScript/TypeScript 运行时的框架，这意味着游戏把部分业务逻辑（包括这些 cmdid 对应的 pb 处理）下沉到了 JS 层，绕过了 IL2CPP 的静态编译，所以 `dump.cs` 里看不到。

### 定位脚本加载入口

Puerts 加载脚本走的是 `ILoader` 接口，游戏实现了一个自定义 loader：

```csharp
// Assembly-CSharp
class CustomTsScriptLoader : System.Object, Puerts.ILoader
{
    System.String PathToUse(System.String filepath);       // 0x05c73d00
    System.Boolean FileExists(System.String filepath);     // 0x05c73e40
    System.String ReadFile(System.String filepath, System.String& debugpath);  // 0x05c74078
    System.String CheckAndFixPath(System.String filepath); // 0x05c73f9c
    System.Void .ctor();                                   // 0x05c743a4
}
```

关键方法是 `ReadFile`——Puerts 每次加载一个脚本模块都会调用它，返回值就是脚本的完整字符串内容。

### Hook ReadFile 拿到完整脚本

直接 hook `ReadFile`，打印返回值和 `filepath` 参数，游戏运行过程中所有被动态加载的脚本内容都会从这里流出。脚本以明文 JS 文件形式加载，没有字节码编译或混淆处理，可以直接阅读。

```ts
import "frida-il2cpp-bridge";

Il2Cpp.perform(() => {
    const asm = Il2Cpp.domain.assembly("Assembly-CSharp");
    const loaderClass = asm.image.class("CustomTsScriptLoader");

    if (!loaderClass) {
        console.log("[!] 没找到 CustomTsScriptLoader");
        return;
    }

    const readFile = loaderClass.method("ReadFile");
    if (!readFile) {
        console.log("[!] 没找到 ReadFile 方法");
        return;
    }

    console.log("[*] Hooking CustomTsScriptLoader.ReadFile");

    const savedFiles = new Set<string>();

    readFile.implementation = function (filepath, debugPath) {
        const result = this.method("ReadFile").invoke(filepath, debugPath);

        try {
            const code = result?.toString().replace(/^"|"$/g, "") ?? "";
            const fp = filepath?.toString().replace(/"/g, "") ?? "unknown";

            // 避免重复保存同一个文件
            if (!savedFiles.has(fp)) {
                savedFiles.add(fp);

                // 取文件名部分作为保存名

                const fileName = fp
                    .replace(/^[/\\]+/, "")   // 去掉开头的斜杠
                    .replace(/[/\\]/g, "_")   // 中间斜杠换成下划线
                    .replace(/[/\\]$/, "");   // 去掉结尾的斜杠

                const savePath = `/sdcard/ts_dump/${fileName}`;

                const f = new File(savePath, "w");
                f.write(code);
                f.flush();
                f.close();

                console.log(`[+] 已保存: ${fp} → ${savePath} (${code.length} chars)`);
            }
        } catch (e) {
            console.log("[!] Error:", e);
        }

        return result;
    };
});
```

加载的模块涵盖：

- 各 cmdid 对应的 protobuf message 定义（以 JS 对象形式内联定义）
- 收发包的序列化/反序列化逻辑
- 部分游戏业务逻辑（战斗、任务等）

之前查不到的 cmdid，在这些 JS 模块里全部能找到对应的结构定义，协议层至此完整还原。

---

## 0x09 总结与踩坑复盘

### 整体分析流程

```python
抓包识别 Magic 特征（45 67 / 89 AB）
    ↓
APK 检查 → metadata 头部异常 → 转用 frida-il2cpp-bridge 运行时 dump
    ↓
dump.cs 搜索魔数 → 十进制转换 → 定位 PacketDefine / AesUtils
    ↓
动态 hook → 确认 AES 加密 → 固定 IV
    ↓
调用栈追溯 → SerializeSec → 还原组包结构
    ↓
握手包识别（明文 pb）→ RSA 参数提取 → 解密 session key
    ↓
发现 Puerts → hook ReadFile → 拿到完整 JS 脚本 → 补全 pb 定义
```

**附件内有完整的分析脚本可以直接使用**

### 最深的弯路：AES key 的来源

整个过程里卡得最久的是 AES key 的来源问题。确认 IV 是静态固定的之后，key 每次重启都不同，也没有明显的生成规律。当时的思路是在"加密函数周围"找 key——尝试过对所有网络收包回调打印内容来碰运气，始终定位不到。

真正的突破口是调用栈：从 `AesUtils.Encrypt` 往上追调用链，找到 `SerializeSec`，再结合 TCP 握手初期有明文包这个观察，才把视角转移到握手流程上。最后通过 hook RSA 底层参数，才把 `session_read_key_` / `session_write_key_` 的来源完整串联起来。

回头看，这个弯路的根本原因是先入为主地在加密函数附近找 key，而没有从"key 是什么时候被写入 `TcpAsyncClient` 字段的"这个角度出发。如果一开始就 hook 字段写入时机，可能会更快定位到握手环节。

### 可复用的方法论

- **常量搜索注意进制**：十六进制 magic 在 C# 代码里经常以十进制存储，搜索时记得换算
- **metadata 异常直接上运行时 dump**：头部不对就放弃静态分析，frida-il2cpp-bridge 省时间
- **调用栈是定位 key 来源最有效的手段**：比在函数周围盲打 hook 效率高得多
- **IL2CPP dump 不完整时优先排查脚本层**：Puerts / xlua 的存在会导致部分逻辑在 dump.cs 里看不到，遇到 cmdid 对不上时第一时间检查是否有脚本引擎介入

上传的附件：
- index.ts

（8.82kb，65次下载）

---

# 回复

## 回复 by Imxz (#2)

*2026-3-22 18:02*

tql

## 回复 by PPTV (#3)

*2026-3-22 18:33*

感谢分享

## 回复 by tonykros (#4)

*2026-3-22 20:45*

Thanks for sharing

## 回复 by mb_abajbief (#5)

*2026-3-22 21:18*

厉害啊大佬

## 回复 by Zepp7289 (#6)

*2026-3-22 21:48*

tql

## 回复 by mb_asiwnxyv (#7)

*2026-3-22 21:53*

感谢分享

## 回复 by Aar0n (#8)

*2026-3-23 02:28*

1

## 回复 by huangjw (#9)

*2026-3-23 09:02*

看看先

## 回复 by mb_ldbucrik (#10)

*2026-3-23 09:31*

感谢分享

## 回复 by Snark (#11)

*2026-3-23 10:01*

1

## 回复 by supyuan (#12)

*2026-3-23 10:20*

666

## 回复 by 错过 (#13)

*2026-3-23 10:37*

666

## 回复 by mb_gacxucdh (#14)

*2026-3-23 11:06*

lihai

## 回复 by Elv1s (#15)

*2026-3-23 11:23*

666

## 回复 by wx_无法回头的伪装 (#16)

*2026-3-23 11:30*

6666

## 回复 by fjqisba (#17)

*2026-3-23 11:30*

看看怎么写挂的

## 回复 by XCicada (#18)

*2026-3-23 14:35*

tql

## 回复 by Gryffindoss (#19)

*2026-3-23 14:45*

6666

## 回复 by GEKEZYX (#20)

*2026-3-23 14:46*

666

## 回复 by lixianhuei (#21)

*2026-3-23 15:44*

6666

## 回复 by 枯藤舍 (#22)

*2026-3-23 15:46*

666

## 回复 by andy张刘 (#23)

*2026-3-23 16:21*

lixianhuei
  22 楼
6666

## 回复 by xingbing (#24)

*2026-3-23 16:25*

感谢分享!!!

## 回复 by git_29894Cui-xf (#25)

*2026-3-23 17:46*

1111

## 回复 by method (#26)

*2026-3-23 17:55*

1

## 回复 by xifgg (#27)

*2026-3-23 18:06*

11

## 回复 by asdasafwe (#28)

*2026-3-23 18:55*

感谢分享

## 回复 by tjxiaowu (#29)

*2026-3-23 19:58*

感谢分享

## 回复 by mb_wdhsjycl (#30)

*2026-3-23 19:59*

1

## 回复 by 墨穹呢 (#31)

*2026-3-23 21:16*

感谢分享

## 回复 by mb_abynwzbl (#32)

*2026-3-23 21:25*

111

## 回复 by mb_huezdnet (#33)

*2026-3-23 22:00*

感谢分享

## 回复 by 嘎嘎真的很棒 (#34)

*2026-3-23 22:04*

mark

## 回复 by 青庭 (#35)

*2026-3-23 22:27*

66

## 回复 by 陌沫 (#36)

*2026-3-23 22:54*

666

## 回复 by Atnil (#37)

*2026-3-24 10:03*

我倒要看看![image](https://bbs.kanxue.com/view/img/face/0103.gif)![image](https://bbs.kanxue.com/view/img/face/0103.gif)

## 回复 by MaYil (#38)

*2026-3-24 11:20*

感谢分享

## 回复 by mb_ayexlfko (#39)

*2026-3-24 12:27*

666

## 回复 by wx_Y_786749 (#40)

*2026-3-24 14:07*

安全

## 回复 by mb_ysegxpmv (#41)

*2026-3-24 14:29*

666

## 回复 by 小李08 (#42)

*2026-3-24 15:41*

6666

## 回复 by pan_634488 (#43)

*2026-3-24 16:17*

666

## 回复 by 毛毛毛毛虫 (#44)

*2026-3-24 18:28*

学习一下

## 回复 by cpannn (#45)

*2026-3-24 20:05*

学习！

## 回复 by loveaixing (#46)

*2026-3-24 21:06*

感谢分享!!!

## 回复 by Matchman33 (#47)

*2026-3-25 08:55*

太牛了

## 回复 by wx_Huber Barrientos (#48)

*2026-3-25 09:54*

为你点赞！

## 回复 by 非凡人平常心 (#49)

*2026-3-25 16:03*

6

## 回复 by Roger (#50)

*2026-3-25 19:24*

mark

## 回复 by B.M.K (#51)

*2026-3-26 09:00*

666

## 回复 by LoginUser (#52)

*2026-3-26 09:12*

感谢分享!

## 回复 by 外交 (#53)

*2026-3-26 10:03*

6666

## 回复 by 不具名的悲伤 (#54)

*2026-3-26 13:43*

6

## 回复 by Crack999 (#55)

*2026-3-26 13:49*

感谢分享

## 回复 by mb_euhyowpw (#56)

*2026-3-26 15:04*

66

## 回复 by wx_宇克鴻 (#57)

*2026-3-26 16:24*

6666

## 回复 by mb_tvmcbdnl (#58)

*2026-3-27 02:04*

感谢分享!!!

## 回复 by 勒LI (#59)

*2026-3-27 10:13*

666

## 回复 by tigericon (#60)

*2026-3-27 10:32*

66

## 回复 by Steesha (#61)

*2026-3-27 12:33*

666

## 回复 by qwerdvd (#62)

*2026-3-27 15:57*

感谢分享!!!

## 回复 by KXLCN (#63)

*2026-3-27 18:33*

好

## 回复 by mb_pbwrxajf (#64)

*2026-3-27 18:52*

感谢分享!!!

## 回复 by 诶一 (#65)

*2026-3-27 19:01*

666666

## 回复 by 蓝冰love (#66)

*2026-3-28 00:20*

感谢分享

## 回复 by wx_code_258 (#67)

*2026-3-28 04:20*

学习

## 回复 by lackone (#68)

*2026-3-28 10:51*

6666666

## 回复 by 呆萌的小白 (#69)

*2026-3-29 08:09*

原来教程也可以这么详细,我也吃到细糠了

## 回复 by wx_故事与酒 (#70)

*2026-3-29 09:05*

666666666666666666666666

## 回复 by zylyy (#71)

*2026-3-29 19:25*

666

## 回复 by mb_izusevbx (#72)

*2026-3-30 23:17*

感谢分享

## 回复 by hahao (#73)

*2026-3-31 00:47*

感谢分享

## 回复 by mb_uzmffdbw (#74)

*2026-3-31 16:32*

666

## 回复 by 冷风Feng (#75)

*2026-4-4 15:26*

感谢分享!!!

## 回复 by mb_hugdbdew (#76)

*2026-4-5 00:49*

感谢分享

## 回复 by 小迷糊ddd (#77)

*2026-4-6 22:31*

感谢分享，认真学习。

## 回复 by win柠初 (#78)

*2026-4-7 14:46*

好东西，来看看

## 回复 by 5h3r10(l{ (#79)

*2026-4-7 19:51*

看到Sunny我都已经知道是什么游戏了，哈哈，上小学就用过你的辅助

## 回复 by mb_gpkeephm (#80)

*2026-4-8 15:16*

6666666

## 回复 by 星雨心愿 (#81)

*2026-4-8 15:40*

66666

## 回复 by mb_tvuiswau (#82)

*2026-4-9 01:31*

感谢分享!!!

## 回复 by AK1988DA (#83)

*2026-4-9 17:01*

444

## 回复 by mb_owfvtagq (#84)

*2026-4-10 19:39*

感谢你分享这么好的资源！

## 回复 by mb_sbshxkcs (#85)

*2026-4-10 21:02*

学到了

## 回复 by mb_jzyasacd (#86)

*2026-4-11 04:43*

666

## 回复 by longerp (#87)

*2026-4-11 06:00*

感谢分享!!!

## 回复 by mb_dagesnbs (#88)

*2026-4-11 19:05*

tql

## 回复 by mb_mxsesokv (#89)

*2026-4-12 04:22*

感谢分享!!!

## 回复 by mb_ujlbfnqz (#90)

*2026-4-12 15:28*

6666G感谢分享

## 回复 by mb_ujlbfnqz (#91)

*2026-4-12 15:31*

6666 感谢

## 回复 by 沐仁浴义 (#92)

*2026-4-13 05:32*

66666

## 回复 by wx_随波逐流、 (#93)

*2026-4-13 19:08*

感谢分享!!!

## 回复 by r0reborn (#94)

*2026-4-14 09:39*

66666

## 回复 by hygzs (#95)

*2026-4-14 10:37*

66666666

## 回复 by shuangmou (#96)

*2026-4-14 11:54*

感谢大佬分享

## 回复 by xxRea (#97)

*2026-4-15 09:05*

感谢分享
![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by r0k (#98)

*2026-4-15 14:27*

谢谢分享

## 回复 by FMNS (#99)

*2026-4-20 09:06*

感谢分享!!!

## 回复 by mb_zzzklvpa (#100)

*2026-4-20 09:36*

66666666

## 回复 by git_49999huanptd2011 (#101)

*2026-4-20 13:04*

1

## 回复 by git_442072863931186 (#102)

*2026-4-20 22:34*

6666

## 回复 by mb_zcfhleoj (#103)

*2026-4-22 16:31*

感谢分享

## 回复 by bllk (#104)

*2026-4-23 03:01*

感谢分享!

## 回复 by uni7corn (#105)

*2026-4-27 14:40*

感谢分享

## 回复 by mb_udytusff (#106)

*2026-4-27 15:12*

fdgdhfdjhfjxjf

## 回复 by 大白_460230 (#107)

*2026-5-1 19:01*

感谢分享!!!

## 回复 by mb_tofujngy (#108)

*2026-5-1 21:38*

感谢分享

## 回复 by nqminhquan (#109)

*2026-5-2 16:45*

666666

## 回复 by 星落噜啦啦 (#110)

*2026-5-3 14:03*

6666

## 回复 by superhuap (#111)

*2026-5-3 22:21*

感谢分享!!!

## 回复 by mb_vkwujxpi (#112)

*2026-5-8 11:30*

666

## 回复 by mb_otltlegp (#113)

*2026-5-10 21:16*

66

## 回复 by git_42339srkdragon (#114)

*2026-5-10 21:58*

666

## 回复 by admin5 (#115)

*2026-5-10 22:17*

看看

## 回复 by nhtr (#116)

*2026-5-12 09:53*

666

## 回复 by mb_hnwotbvj (#117)

*2026-5-12 21:38*

66

## 回复 by mb_cjjbbtgt (#118)

*2026-5-13 02:24*

看看

## 回复 by git_14248bibinocode (#119)

*2026-5-13 10:39*

6666666666666

## 回复 by 086Love (#120)

*2026-5-18 14:15*

学习

## 回复 by mb_vhwdzyqo (#121)

*2026-5-19 10:40*

啥游戏 有大佬透露下吗

## 回复 by mb_ymtvhvgj (#122)

*2026-5-27 00:09*

666

## 回复 by mb_elytxfur (#123)

*2026-5-28 13:58*

，kk

## 回复 by mb_lgtsulbs (#124)

*2026-5-31 19:45*

6

## 回复 by BOSC叛忍 (#125)

*2026-5-31 20:16*

厉害

## 回复 by mb_tecrmqmn (#126)

*2026-5-31 20:21*

666

## 回复 by mb_etgbvvic (#127)

*2026-5-31 21:13*

666

## 回复 by mb_jyijaqac (#128)

*2026-5-31 22:25*

感谢分享

## 回复 by 末日大哥 (#129)

*2026-5-31 22:32*

666

## 回复 by 天涯共何时 (#130)

*2026-5-31 22:54*

666

## 回复 by mb_devnoxep (#131)

*2026-6-6 12:48*

牛逼啊大哥

## 回复 by mb_fogbfnnb (#132)

*2026-6-6 14:54*

333

## 回复 by mb_aqizvenj (#133)

*2026-6-8 14:32*

！

## 回复 by mb_jegknedl (#134)

*2026-6-9 05:13*

学习学习

## 回复 by mb_zxamxsfc (#135)

*2026-6-10 17:02*

1111

## 回复 by mb_etobpsbv (#136)

*2026-6-14 22:05*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by wx_断浪天涯 (#137)

*2026-6-15 14:17*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by Circ1e (#138)

*2026-6-15 14:32*

666

## 回复 by mb_uekrtlsh (#139)

*2026-6-20 17:47*

666

## 回复 by Snowman_Liam (#140)

*2026-6-20 18:04*

666

## 回复 by 闲闲 (#141)

*2026-6-21 11:46*

谢分享谢分享

## 回复 by mb_zjtkhkzx (#142)

*2026-6-29 22:57*

看看啥样的

## 回复 by useryq (#143)

*2026-7-6 15:11*

1

## 回复 by console_ (#144)

*2026-7-6 15:20*

study

## 回复 by mb_elpcuukh (#145)

*2026-7-13 17:52*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by 小尘0000 (#146)

*2026-7-13 18:09*

6666

## 回复 by wx_Dispa1r (#147)

*2026-7-14 17:08*

1

## 回复 by mb_qdutazbj (#148)

*2026-7-15 04:07*

666

## 回复 by mb_degalzhb (#149)

*2026-7-15 14:50*

666

## 回复 by git_52487AlianBlank (#150)

*2026-7-16 14:54*

666

## 回复 by 3cly (#151)

*2026-7-16 16:18*

1

## 回复 by Kazusa (#152)

*2026-7-17 15:39*

6666666

## 回复 by mb_qztkkwxt (#153)

*2026-7-17 17:46*

666

## 回复 by 魔童 (#154)

*2026-7-17 21:19*

666

## 回复 by mb_efxrdkzw (#155)

*2026-7-18 13:58*

66666666
