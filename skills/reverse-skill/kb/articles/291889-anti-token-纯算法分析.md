---
title: '[原创]anti-token 纯算法分析'
url: https://bbs.kanxue.com/thread-291889.htm
tid: 291889
author: Red
date: '2026-07-06'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:01:54+08:00'
replies: 75
---

# anti-token 纯算法分析

本文基于AI分析 anti-token，不得不感慨AI确实强大。

测试环境

- APP：pdd
- 版本号：8.13.0
- Pixel6

它对应 Java Native 方法：

```
com.xunmeng.pinduoduo.secure.DeviceNative.info2(Context context, long timestamp_ms)
signature: (Landroid/content/Context;J)Ljava/lang/String;
```

```
0x1CFAC 负责生成 info2 长 anti-token。

最终返回值 =
"2af" + Base64(AES-128-CBC-PKCS7(GZIP(raw_packet)))
```

其中：

```
AES key = "pdd_aes_180121_1"
AES IV  = 16 字节全 0
前缀    = "2af"
```

---

## 1. jni动态注册函数追踪

com.xunmeng.pinduoduo.secure.DeviceNative.info2是一个动态注册的jni方法，通过Hook RegisterNatives，得到函数偏移0x1cfac，以及库名为 libpdd_secure.so

```python
hook_dynamic_register_func()

function hook_dynamic_register_func() {
    // 获取 RegisterNatives 函数的内存地址，并赋值给addrRegisterNatives。
    var addrRegisterNatives = null;
    var symbols = Module.enumerateSymbolsSync("libart.so");
    for (var i = 0; i < symbols.length; i++) {
        var symbol = symbols[i];
        if (symbol.name.indexOf("art") >= 0 &&
            symbol.name.indexOf("JNI") >= 0 &&
            symbol.name.indexOf("RegisterNatives") >= 0 &&
            symbol.name.indexOf("CheckJNI") < 0) {
            addrRegisterNatives = symbol.address;
            console.log("RegisterNatives is at ", symbol.address, symbol.name);
            break
        }
    }
    if (addrRegisterNatives) {
        Interceptor.attach(addrRegisterNatives, {
            onEnter: function (args) {
                var env = args[0];        // jni对象
                var java_class = args[1]; // 类
                var class_name = Java.vm.tryGetEnv().getClassName(java_class);
                var taget_class = "com.xunmeng.pinduoduo.secure.DeviceNative";
                if (class_name === taget_class) {
                    console.log("\n[RegisterNatives] method_count:", args[3]);
                    var methods_ptr = ptr(args[2]);
                    var method_count = parseInt(args[3]);
                    for (var i = 0; i < method_count; i++) {
                        // Java中函数名字的
                        var name_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3));
                        // 参数和返回值类型
                        var sig_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize));
                        // C中的函数内存地址
                        var fnPtr_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize * 2));
                        var name = Memory.readCString(name_ptr);
                        var sig = Memory.readCString(sig_ptr);
                        var find_module = Process.findModuleByAddress(fnPtr_ptr);
                        // 地址、偏移量、基地址
                        var offset = ptr(fnPtr_ptr).sub(find_module.base);
                        console.log('class_name:', class_name, "name:", name, "sig:", sig, 'module_name:', find_module.name, "offset:", offset);
                    }
                }
            }
        });
    }

}
```

![image-20260706103328915](https://bbs.kanxue.com/upload/attach/202607/910288_R4G6RDDH9UPAFY4.png)

`0x1CFAC` 就是一个 native 方法入口。它接收 Java 传入的 `Context` 和一个 `long` 值，然后返回一个 Java `String`。

IDA 反编译出来的原型是：

```c
__int64 __fastcall sub_1CFAC(__int64 a1, __int64 a2, __int64 a3, __int64 a4)
```

把 JNI 语义补上后更容易理解：

```c
jstring DeviceNative_info2_main(JNIEnv *env, jclass clazz, Context context, jlong timestamp_ms)
```

参数含义：

| 反编译参数 | JNI 含义 | 说明 |
|-|-|-|
| `a1` | `JNIEnv *env` | native 调 Java 的入口表 |
| `a2` | `jclass clazz` | 静态 native 方法的 class 参数，本函数基本不用 |
| `a3` | `Context context` | Android 上下文，用来取系统、Telephony、反射等信息 |
| `a4` | `jlong timestamp_ms` | Java 层传入的毫秒级时间戳。IDA 原始参数名是 `a4`，本文统一叫 `timestamp_ms`。最终写入 `tag32` |

---

## 2. 函数控制流扁平化了解

这个函数做了控制流扁平化。

![image-20260703094956937](https://bbs.kanxue.com/upload/attach/202607/910288_SFNDG4XEVUM7RQ8.png)

正常代码可能长这样：

```c
step1();
step2();
if (condition) {
  step3();
}
return result;
```

但反编译中会看到大量类似代码：

```c
for (i = 1039507498; ; i = -1088307489) {
  if (i >= xxx) {
    ...
    i = 755121284;
  } else {
    ...
    i = -507031606;
  }
}
```

这里的 `i` 是状态机变量。大量随机整数只是混淆后的状态编号，不是业务数据。分析时不要跟着这些数字走，而要抓住真正的调用和数据流：

```
采集 tag -> 拼 raw_packet -> gzip -> AES -> Base64 -> NewStringUTF
```

混淆后大概798行

![image-20260706095121854](https://bbs.kanxue.com/upload/attach/202607/910288_TUJXF46QUMQNE6K.png)

让AI帮我们分析规则，并编写去控制流平坦化脚本,去除后逻辑就比较清晰了。

![image-20260706100510564](https://bbs.kanxue.com/upload/attach/202607/910288_ENB357QRPYTVB3N.png)

IDA底部python 执行命令

```python
PATCH_MODE = "apply"

exec(open(r"D:\Workspace\app\android_pdd\soTest\ida_deflatten_1cfac_patch_idb.py", encoding="utf-8").read())

exec(open(r"D:\Workspace\app\android_pdd\soTest\ida_deflatten_1cfac_patch_csel_idb.py", encoding="utf-8").read())

exec(open(r"D:\Workspace\app\android_pdd\soTest\ida_deflatten_1cfac_patch_trampoline_idb.py", encoding="utf-8").read())
```

## 3. 关键函数分析

本节把主流程涉及的关键子函数一并列出，保留能证明执行逻辑的核心语句，并把 IDA 临时变量名改成更容易理解的名字。

### 3.1 主函数 0x1CFAC 的执行骨架

![image-20260706135538737](https://bbs.kanxue.com/upload/attach/202607/910288_PAK2CWBJ3M8YZM2.png)

关键调用顺序可以还原为：

```c
jstring DeviceNative_info2_main(JNIEnv *env, jclass clazz, jobject context, jlong timestamp_ms) {
    // tv 保存当前秒和微秒，后续 tag33 会用到这两个值。
    struct timeval tv;
    gettimeofday(&tv, 0);

    /*
     * 静态/半静态 tag 缓存：
     * tag1..tag31 大多来自 system property、Build、Telephony、环境检测。
     */
    if (need_refresh_cache(tv.tv_sec)) {
        // 写缓存前先加写锁，避免多线程同时刷新全局 tag 数组。
        pthread_rwlock_wrlock(&global_lock);

        // record_count 表示当前已经写入多少个 record slot。
        record_count = 0;
        record_count += collect_build_tags(env, context, global_slots, record_count);       // sub_16C2F4  采集 tag1..tag11
        record_count += collect_build_prop_stat(global_slots[record_count]);                // sub_16C648  采集 tag12
        record_count += collect_telephony_tags(env, context, global_slots, record_count);   // sub_16C6C4  采集 tag13..tag28
        record_count += collect_optional_proc_version(global_slots[record_count]);          // sub_16CD40  采集tag29
        record_count += collect_env_risk_flags(env, context, global_slots[record_count]);   // sub_16F1D4  采集 tag31 环境风险 flags

        // 记录本次刷新时间，用于判断 86400 秒过期逻辑。
        last_refresh_sec = tv.tv_sec;
        pthread_rwlock_unlock(&global_lock);
    }

    // 读全局缓存前加读锁，把缓存里的 record slot 复制到本次调用的局部缓冲区。
    pthread_rwlock_rdlock(&global_lock);
    copy_cached_slots_to_local_buffer();
    pthread_rwlock_unlock(&global_lock);

    /*
     * 每次调用都变化的 tag。
     */
    write_int_record(local_tag32_slot, 32, timestamp_ms, 8);                // sub_169840
    write_int_record(local_tag33_slot, 33, make_tag33(tv), 8);              // sub_169840
    write_string_record(local_tag34_slot, 34, make_uuid_without_dash(), 32); // sub_172124 + record slot

    // 把局部 slot 数组压成连续 TLV raw_packet。
    raw_packet = build_raw_packet(all_slots);
    // raw_packet 进入 gzip 阶段，返回 Java byte[]。
    gzip_array = info2_gzip_raw_packet_to_jbytearray(env, raw_packet, raw_len);

    // 从 Java byte[] 取出 gzip 后的字节，准备进入 AES/Base64 封装。
    gzip_len = env->GetArrayLength(gzip_array);
    gzip_bytes = malloc(gzip_len);
    env->GetByteArrayRegion(gzip_array, 0, gzip_len, gzip_bytes);

    // prefix 动态解出，当前值已验证为 "2af"。
    prefix = decode_prefix(); // "2af"
    return info2_aes_base64_prefix_wrap(env, gzip_bytes, gzip_len, prefix);
}
```

对应主函数中的关键证据：

```c
gettimeofday(&tv, 0); // 取当前时间，tv_sec/tv_usec 后面用于 tag33。

sub_16C2F4(a1, a3, dword_1CFAE4, dword_1D3CE4);          // 采集 tag1..tag11。
sub_16C648(&dword_1CFAE4[132 * dword_1D3CE4]);           // 采集 tag12。
sub_16C6C4(a1, a3, dword_1CFAE4);                        // 采集 tag13..tag28。
sub_16CD40(&dword_1CFAE4[132 * dword_1D3CE4]);           // 尝试采集可选 tag29。
sub_16F1D4(a1, a3, &dword_1CFAE4[132 * v41]);            // 采集 tag31 环境风险 flags。

sub_169840(&s, 32, a4, 8);                               // 写 tag32：Java 传入的 timestamp_ms；a4 是 IDA 原始参数名。
srand48(tv_sec);                                         // 用秒数作为随机种子。
lrand48();                                               // 得到 tag33 高 32 位。
srand48(tv_usec);                                        // 用微秒作为随机种子。
lrand48();                                               // 得到 tag33 低 32 位。
sub_169840(v49, 33, tag33, 8);                           // 写 tag33：8 字节大端整数。

info2_gzip_raw_packet_to_jbytearray(a1, raw_packet, raw_len); // raw_packet 进入 gzip。
info2_aes_base64_prefix_wrap(a1, gzip_bytes, gzip_len, prefix); // gzip 结果进入 AES/Base64/前缀封装。
```

Hook 验证：

```
[Java] com.xunmeng.pinduoduo.secure.DeviceNative.info2 ENTER
  timestamp_ms : 1782971586354
  context : android.app.ContextImpl@3f3473

============================================================
[libpdd_secure.so + 0x1CFAC] DeviceNative_info2_main ENTER
============================================================
input:
  env           : 0xb4000078beaa6610
  clazz_or_obj  : 0x9f22c4c0
  context       : 0x764b8887b8
  timestamp     : 1782971586354
  timestamp_hex : 0x0000019f21635732
============================================================
[libpdd_secure.so + 0x1CFAC] DeviceNative_info2_main LEAVE
============================================================
output:
  retval      : 0x79d6ee1c01
  jstring_len : 431
  jstring     : 2af5lghy4KzO2lc*****************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************************HAeXhfW04hjK60=
```

整体逻辑：

- 收集34个tag，按tag类型调用write_string_record 或者 write_int_record 函数转换为自定义格式。
- 对收集的34个tag进行压缩重排，顺序按照tag值排序。
- 再进行gzip压缩、ase加密、base64编码、加前缀特征头 2af。

### 3.2 `sub_1697AC`： write_string_record

此函数用于 C 字节指针/字符串 -> slot

```python
char *__fastcall sub_1697AC(char *result, char a2, void *src, int a4)
{
  char v4; // w9

  _ReadStatusReg(TPIDR_EL0);
  result[516] = byte_1CF0C3;
  result[517] = byte_1CF052;
  result[518] = byte_1CF052;
  v4 = byte_1CF052;
  *((_DWORD *)result + 130) = a4;
  *((_DWORD *)result + 131) = a4 + 3;
  result[519] = v4;
  *result = a2;
  if ( a4 >= 1 )
    return (char *)memcpy(result + 1, src, a4);
  return result;
}
```

该函数证明了 record slot 的内部布局：`slot[0]` 是 tag，`slot+1` 是 payload，`slot+520` 是 payload 长度，`slot+524` 是 record 长度。

伪代码：

```c
void write_bytes_record(char *slot, uint8_t tag, void *src, int len) {
    // slot 尾部 0x204 位置写 type 标记，当前有效 type 为 0x01。
    slot[516] = 0x01;
    slot[517] = 0x00;
    slot[518] = 0x00;
    slot[519] = 0x00;

    *(uint32_t *)(slot + 520) = len;       // payload 长度。
    *(uint32_t *)(slot + 524) = len + 3;   // record body 长度：type + tag + payload_len + payload。

    slot[0] = tag;                         // slot 开头保存 tag 编号。

    if (len >= 1) {
        // payload 从 slot+1 开始保存。
        memcpy(slot + 1, src, len);
    }
}
```

如调用write_bytes_record(slot, 2, "google", 6) 会构造成这样的slot

```python
slot+0x000 : tag = 02 // slot 开头保存 tag 编号。
slot+0x001 : payload = 676f6f676c65  // payload 从 slot+1 开始保存。
slot+0x204 : type = 01   // slot 尾部 0x204 位置写 type 标记，当前有效 type 为 0x01。
slot+0x208 : payload_len = 6  // payload 长度。
slot+0x20c : record_len = 9 // record body 长度：type + tag + payload_len + payload。
```

### 3.3 `sub_169840`：write_int_record

该函数先把整数转成指定长度的大端字节，再复用 record slot 格式。

整数 value -> 大端 bytes -> slot

伪代码：

```c
void write_int_record(char *slot, uint8_t tag, uint64_t value, int len) {
    // tmp 保存整数的大端字节表示。
    uint8_t tmp[len];

    int_to_big_endian(value, tmp, len); // sub_17FC74：把整数转成 len 字节大端序。

    // 下面的 slot 尾部字段与 write_bytes_record 完全一致。
    slot[516] = 0x01;
    slot[517] = 0x00;
    slot[518] = 0x00;
    slot[519] = 0x00;

    *(uint32_t *)(slot + 520) = len;     // payload_len。
    *(uint32_t *)(slot + 524) = len + 3; // record_len。

    slot[0] = tag;                       // 保存 tag 编号。
    memcpy(slot + 1, tmp, len);          // 保存整数 payload。
}
```

它调用的 `sub_17FC74` 可以简化为：

```c
void int_to_big_endian(uint64_t value, void *out, int len) {
    /*
     * 按 4 字节一组 bswap32，然后取最后 len 字节。
     * 最终效果就是把 value 写成 big-endian。
     */
    out = value.to_bytes(len, "big"); // 伪代码写法：最终输出 len 字节大端整数。
}
```

 slot 布局和上面是一样的：

```python
  slot+0x000 : tag
  slot+0x001 : payload，也就是整数的大端字节
  slot+0x204 : type = 1
  slot+0x208 : payload_len = value_len
  slot+0x20c : record_len = value_len + 3
```

如sdk版本，我的是34，这个是整数型。

```python
slot+0x000 : tag = 0a // slot 开头保存 tag 编号。
slot+0x001 : payload = 22  // payload 从 slot+1 开始保存。34 = 0x22
slot+0x204 : type = 01   // slot 尾部 0x204 位置写 type 标记，当前有效 type 为 0x01。
slot+0x208 : payload_len = 1  // payload 长度。
slot+0x20c : record_len = 4 // record body 长度：type + tag + payload_len + payload。
```

### 3.4 `sub_1699B8`：从 Java String 写 record

这个函数用于把 Java 字符串写入 slot，或者把字符串转整数后写入固定长度 payload。

 Java jstring -> 根据 mode 决定按字符串写，还是按整数写 -> slot

```c
void write_jstring_record(JNIEnv *env, char *slot, uint8_t tag, jstring str, int mode) {
    if (str == NULL) {
        // Java 字符串为空时，写一个空 payload record。
        write_empty_record(slot, tag);
        return;
    }

    // 从 Java String 取 UTF-8 长度和 UTF-8 字节指针。
    int strlen = env->GetStringUTFLength(str);
    const char *chars = env->GetStringUTFChars(str, 0);

    if (strlen == 0) {
        // 空字符串同样写成空 payload。
        write_empty_record(slot, tag);
        release_and_delete_local_ref();
        return;
    }

    if (mode == 0) {
        // mode=0：按原始字符串字节写入。
        write_bytes_record(slot, tag, chars, strlen);
    } else if (mode > 0) {
        // mode>0：字符串转整数，再按 mode 指定的字节数写入。
        uint64_t value = atoll(chars);
        write_int_record(slot, tag, value, mode);
    } else {
        /*
         * mode < 0 时，写固定长度数值。
         * 例如 tag30 使用 -8，最终写入 8 字节。
         */
        int out_len = -mode;
        // mode<0：按固定长度写数值，解析失败时使用 -1 兜底。
        uint64_t value = parse_number_or_minus_one(chars);
        write_int_record(slot, tag, value, out_len);
    }

    // 释放 JNI 字符串资源和局部引用，避免泄露。
    env->ReleaseStringUTFChars(str, chars);
    env->DeleteLocalRef(str);
}
```

### 3.5 tag32/tag33 的直接证据

tag32：

```c
sub_169840(&s, 32, a4, 8); // tag32：把 Java 传入的 timestamp_ms 按 8 字节大端写入；a4 是 IDA 原始参数名。
```

可还原为：

```c
write_int_record(slot, 32, timestamp_ms, 8); // 等价含义：tag=32，payload=timestamp_ms 的 8 字节大端表示。
```

tag33：

```c
srand48(tv_sec);  // 用当前秒数播种。
hi = lrand48();   // 第一次 lrand48 作为 tag33 高 32 位。

srand48(tv_usec); // 用当前微秒数播种。
lo = lrand48();   // 第一次 lrand48 作为 tag33 低 32 位。

tag33 = lo + (hi << 32);        // 合成 64 位 tag33。
sub_169840(slot, 33, tag33, 8); // 按 8 字节大端写入 tag33 record。
```

可还原为：

```python
def make_tag33(tv_sec: int, tv_usec: int) -> int:
    # 高 32 位来自 tv_sec 的 srand48/lrand48。
    hi = lrand48_first(tv_sec)
    # 低 32 位来自 tv_usec 的 srand48/lrand48。
    lo = lrand48_first(tv_usec)
    # 拼成 64 位整数，后续按 8 字节大端写入 payload。
    return (hi << 32) | lo
```

### 3.6 `sub_16C2F4`：采集 system property / Build 字段

该函数负责 tag1 到 tag11 的主要系统属性。

伪代码：

```c
int collect_build_tags(JNIEnv *env, jobject context, char *slots, int start_index) {
    // prop 用来接收 __system_property_get 读取出的系统属性字符串。
    char prop[PROP_VALUE_MAX];
    // 每条 record slot 大小是 0x210，从 start_index 对应位置开始写。
    char *slot = slots + start_index * 0x210;

    // tag1：设备序列号或 fallback 值 unknown。
    write_jstring_record(env, slot + 0x210 * 0, 1, get_serial_or_unknown(), 0);

    // tag2：品牌 ro.product.brand。
    __system_property_get("ro.product.brand", prop);
    write_bytes_record(slot + 0x210 * 1, 2, prop, strlen(prop));

    // tag3：设备代号 ro.product.device。
    __system_property_get("ro.product.device", prop);
    write_bytes_record(slot + 0x210 * 2, 3, prop, strlen(prop));

    // tag4：机型 ro.product.model。
    __system_property_get("ro.product.model", prop);
    write_bytes_record(slot + 0x210 * 3, 4, prop, strlen(prop));

    // tag5：厂商 ro.product.manufacturer。
    __system_property_get("ro.product.manufacturer", prop);
    write_bytes_record(slot + 0x210 * 4, 5, prop, strlen(prop));

    // tag6：主板 ro.product.board。
    __system_property_get("ro.product.board", prop);
    write_bytes_record(slot + 0x210 * 5, 6, prop, strlen(prop));

    // tag7：构建显示 ID ro.build.display.id。
    __system_property_get("ro.build.display.id", prop);
    write_bytes_record(slot + 0x210 * 6, 7, prop, strlen(prop));

    build_tag8_string(prop); // tag8：id + "/" + incremental + ":" + type + "/" + tags。
    write_bytes_record(slot + 0x210 * 7, 8, prop, strlen(prop));

    // tag9：Android release 版本，例如 "14"。
    __system_property_get("ro.build.version.release", prop);
    write_bytes_record(slot + 0x210 * 8, 9, prop, strlen(prop));

    // tag10：SDK_INT，字符串转整数后写 1 字节。
    __system_property_get("ro.build.version.sdk", prop);
    write_int_record(slot + 0x210 * 9, 10, atoll(prop), 1);

    // tag11：构建时间戳 ro.build.date.utc，写 4 字节。
    __system_property_get("ro.build.date.utc", prop);
    write_int_record(slot + 0x210 * 10, 11, atoll(prop), 4);

    // 本函数固定写入 11 条 record。
    return 11;
}
```

对应反编译能看到连续的：

```c
__system_property_get(..., nptr);      // 读取系统属性到 nptr。
sub_1697AC(v9 + 528, 2, nptr);        // 写 tag2。
sub_1697AC(v9 + 1056, 3, nptr);       // 写 tag3。
sub_1697AC(v9 + 1584, 4, nptr);       // 写 tag4。
...
sub_169840(v27, 10, sdk_int, 1);      // 写 tag10：1 字节 SDK_INT。
sub_169840(v30, 11, build_date_utc, 4); // 写 tag11：4 字节 build date。
return 11;                            // 返回写入的 record 数量。
```

Hook 验证，1697AC和169840，slot结构体为：

- 0x208->payloadLen
- 0x20c->recordLen
- 0x204->typeWord
- 0x0->tag
- [0x1，payloadLen] ->payload

![image-20260703164712740](https://bbs.kanxue.com/upload/attach/202607/910288_SB5NJ49N3GA7EJQ.png)

### 3.7 `sub_16C648`：tag12

该函数读取 `/system/build.prop` 的文件状态，取其中一个时间字段写成 4 字节整数。

伪代码：

```c
int collect_build_prop_stat(char *slot) {
    // stat 结构保存文件元信息。
    struct stat st;

    if (stat("/system/build.prop", &st) != 0) {
        // 读取失败时写 0。
        write_int_record(slot, 12, 0, 4);
    } else {
        // 读取成功时写 stat 中的时间字段，长度 4 字节。
        write_int_record(slot, 12, st.some_time_field, 4);
    }

    // 本函数只写 tag12 一条 record。
    return 1;
}
```

对应反编译核心：

```c
v2 = sub_16FE00(19, 19, 18); // 解出路径字符串，动态验证中应看到 /system/build.prop。
if (stat(v2, &st))           // stat 失败。
    value = 0;               // 失败时 tag12 写 0。
else
    value = v6;              // 成功时取 stat 结构里的一个时间字段。
sub_169840(a1, 12, value, 4); // tag12 写 4 字节整数。
return 1;                    // 返回写入数量。
```

Hook 验证：1230768000时间戳转换后是2009-01-01 08:00

![image-20260703170141067](https://bbs.kanxue.com/upload/attach/202607/910288_NWC8EWEKJFAZ3VW.png)

![image-20260703170235796](https://bbs.kanxue.com/upload/attach/202607/910288_2W43XRDZXS5J5ZU.png)

![image-20260703170542992](https://bbs.kanxue.com/upload/attach/202607/910288_WJA3BFR7Z5ATHAM.png)

### 3.8 `sub_16C6C4`：Telephony/network 字段

该函数负责 tag13 到 tag28，多数来自 `TelephonyManager`。

伪代码：

```c
int collect_telephony_tags(JNIEnv *env, jobject context, char *slots, int start_index) {
    // 通过 Context.getSystemService("phone") 获取 TelephonyManager。
    TelephonyManager tm = context.getSystemService("phone");
    // 从当前起始 slot 开始连续写 tag13..tag28。
    char *slot = slots + start_index * 0x210;

    // tag13..tag17：当前样本中多为空或固定字段。
    write_int_record_or_empty(slot + 0x210 * 0, 13, NULL, 8);
    write_empty_record(slot + 0x210 * 1, 14);
    write_empty_record(slot + 0x210 * 2, 15);
    write_empty_record(slot + 0x210 * 3, 16);
    write_empty_record(slot + 0x210 * 4, 17);

    // tag18：SIM 状态，写 1 字节。
    write_int_record(slot + 0x210 * 5, 18, tm.getSimState(), 1);
    // tag19：SIM 运营商名称。
    write_string_record(slot + 0x210 * 6, 19, tm.getSimOperatorName());
    // tag20：SIM 国家 ISO。
    write_string_record(slot + 0x210 * 7, 20, tm.getSimCountryIso());
    // tag21：固定空字段。
    write_empty_record(slot + 0x210 * 8, 21);

    // tag22：网络类型编号映射成字符串，例如 UNKNOWN/LTE。
    int network_type = get_network_type_if_allowed(tm);
    write_string_record(slot + 0x210 * 9, 22, NETWORK_TYPE_NAMES[network_type]);

    // tag23/tag24：NetworkOperator 拆成 MCC 和 MNC。
    char *operator = tm.getNetworkOperator();
    write_string_record(slot + 0x210 * 10, 23, first_3_chars(operator));
    write_string_record(slot + 0x210 * 11, 24, chars_after_3(operator));

    // tag25：网络运营商名称。
    write_string_record(slot + 0x210 * 12, 25, tm.getNetworkOperatorName());
    // tag26：网络国家 ISO。
    write_string_record(slot + 0x210 * 13, 26, tm.getNetworkCountryIso());
    // tag27/tag28：数据连接状态和数据活动状态，均写 1 字节。
    write_int_record(slot + 0x210 * 14, 27, tm.getDataState(), 1);
    write_int_record(slot + 0x210 * 15, 28, tm.getDataActivity(), 1);

    // 本函数固定写 tag13..tag28，共 16 条。
    return 16;
}
```

对应反编译核心包括：

```c
sub_1699B8(..., 13, ..., 8);          // 写 tag13，按 8 字节整数模式处理。
sub_1697AC(..., 14, 0);               // 写 tag14 空 payload。
sub_1697AC(..., 15, 0);               // 写 tag15 空 payload。
sub_1697AC(..., 16, 0);               // 写 tag16 空 payload。
sub_1697AC(..., 17, 0);               // 写 tag17 空 payload。

sub_169840(..., 18, getSimState(), 1);          // 写 tag18：SIM 状态。
sub_1699B8(..., 19, getSimOperatorName(), 0);   // 写 tag19：SIM 运营商名称。
sub_1699B8(..., 20, getSimCountryIso(), 0);     // 写 tag20：SIM 国家。
sub_1697AC(..., 21, 0);                         // 写 tag21 空 payload。
sub_1697AC(..., 22, network_type_name);         // 写 tag22 网络类型名称。
...
sub_169840(..., 27, getDataState(), 1);         // 写 tag27：数据状态。
sub_169840(..., 28, getDataActivity(), 1);      // 写 tag28：数据活动状态。
return 16;                                      // 返回写入 record 数量。
```

Hook 验证tag 18、21、22 、23：

![image-20260703170934497](https://bbs.kanxue.com/upload/attach/202607/910288_QE8ZPTDWQ37PWZT.png)

### 3.9 `sub_16F1D4`：tag31 环境风险 flags

该函数把三路检测结果 OR 到一起，然后写 tag31。

伪代码：

```c
int collect_env_risk_flags(JNIEnv *env, jobject context, char *slot) {
    // flags 是多个检测结果的按位或。
    int flags = 0;

    flags |= check_debugger_connected();  // sub_16DC4C：检测 Debug.isDebuggerConnected。
    flags |= check_proc_status();         // sub_16E0D4：检测 /proc/<pid>/status。
    flags |= check_java_stack_trace(env); // sub_16E384：检测 Java 调用栈。

    // tag31 写 1 字节 flags。
    write_int_record(slot, 31, flags, 1);
    return 1;
}
```

对应反编译核心：

```c
v5 = sub_16DC4C();                 // 检测 debugger。
v6 = sub_16E0D4();                 // 检测 proc status。
v7 = sub_16E384(a1);               // 检测 Java stack trace。
sub_169840(a3, 31, v6 | v5 | v7, 1); // 三路结果 OR 后写 tag31。
return 1;                          // 返回写入数量。
```

Hook 验证为0，这里也能看出来,假如用unidbug调的话，java stack trace可能会为1，导致风控的存在。

![image-20260703171012827](https://bbs.kanxue.com/upload/attach/202607/910288_77DT33TPHHBDFMY.png)

### 3.10 `sub_172124`：tag34 UUID

该函数通过 JNI 调 Java 侧 UUID 逻辑，最后把 Java 字符串拷贝到 native 缓冲区。

主函数上是直接保存的，没有调用1697ac或者169840创建slot。

![image-20260703171325740](https://bbs.kanxue.com/upload/attach/202607/910288_BJYBDHT4AKX92NT.png)

伪代码：

```c
void make_uuid_without_dash(JNIEnv *env, char *out) {
    // Java: UUID.randomUUID()
    uuid_obj = UUID.randomUUID();
    // Java: uuid.toString()
    uuid_str = uuid_obj.toString();
    // Java: uuid_str.replaceAll("-", "")
    clean_str = uuid_str.replaceAll("-", "");

    // 取出 Java 字符串 UTF-8 内容，复制到 native 输出缓冲区。
    const char *chars = env->GetStringUTFChars(clean_str, 0);
    memcpy(out, chars, strlen(chars) + 1);
    env->ReleaseStringUTFChars(clean_str, chars);
}
```

主函数随后把它作为 tag34 record 使用：

```
tag = 34 = 0x22
payload_len = 32 = 0x20
record_len = 32 + 3 = 35 = 0x23
```

这与主函数里写全局 tag34 slot 的逻辑一致：

```c
qword_1D3CD8 = 0x2000000001LL; // 组合写入 payload_len=0x20 和 type=0x01。
LOBYTE(dword_1D3CE0) = 0x23;  // record_len = 0x20 + 3。
byte_1D3AD4 = 0x22;           // tag = 0x22，也就是十进制 34。
```

### 3.11 raw_packet 拼接逻辑

主函数里先统计所有 record 的 `record_len`，再 `malloc(raw_len)`，最后把 slot 转成连续 TLV。

![image-20260703171636580](https://bbs.kanxue.com/upload/attach/202607/910288_KXYFXJYVWEFX8TQ.png)

上面的逻辑执行完成后，他还会补上tag 32、33、34到raw packet。32和33的获取方式后面会提到。

![image-20260703172611774](https://bbs.kanxue.com/upload/attach/202607/910288_U7SS5C6G5CVTRPV.png)

伪代码：

```c
uint8_t *build_raw_packet(slot_t *slots, int count, int *out_len) {
    // body_len 是所有 record 的总长度，不包含 6 字节 packet 头。
    int body_len = 0;

    for (int i = 0; i < count; i++) {
        body_len += slots[i].record_len + 2; // 每条 record 前还有 2 字节 record_len 前缀。
    }

    // raw_len = 4 字节 version + 2 字节 body_len + body。
    int raw_len = body_len + 6;
    uint8_t *raw = malloc(raw_len);
    memset(raw, 0, raw_len);

    // 前 4 字节是 uint32 小端 version=1。
    raw[0] = 0x01;
    raw[1] = 0x00;
    raw[2] = 0x00;
    raw[3] = 0x00;
    // 接着 2 字节是 uint16 大端 body_len。
    raw[4] = body_len >> 8;
    raw[5] = body_len;

    // p 指向第一个 record 的写入位置。
    uint8_t *p = raw + 6;

    for (int i = 0; i < count; i++) {
        uint16_t record_len = slots[i].record_len;

        // 每条 record 先写 2 字节大端 record_len。
        p[0] = record_len >> 8;
        p[1] = record_len;
        p[2] = 0x01;                   // type 固定为 0x01。
        p[3] = slots[i].tag;           // tag 编号。
        p[4] = slots[i].payload_len;   // payload 长度。
        memcpy(p + 5, slots[i].payload, slots[i].payload_len);

        // 跳到下一条 record 的写入位置。
        p += 2 + record_len;
    }

    // 返回 raw_packet 长度和缓冲区指针。
    *out_len = raw_len;
    return raw;
}
```

对应主函数证据：

```c
v63 = malloc(v61);                  // 分配 raw_packet 缓冲区。
memset(v63, 0, v62);                // 清零 raw_packet。
*(_BYTE *)v63 = byte_1CC133;        // 写 version 低字节 0x01，即 uint32_le version=1。
v63[2] = bswap32(body_len) >> 16;   // 写 uint16_be body_len。

*v125 = bswap32(record_len) >> 16;  // 写每条 record 的 uint16_be record_len。
*((_BYTE *)v133 + 2) = type;        // 写 type，当前为 0x01。
*((_BYTE *)v133 + 3) = tag;         // 写 tag 编号。
*v75 = payload_len;                 // 写 payload_len。
memcpy(v75 + 1, payload, payload_len); // 拷贝 payload 数据。
```

下面补充本次 hook 样例值和 raw_packet 写入形态。

raw_packet 中每个 record 的写法固定为：

```
record = record_len_be(2B) + type(1B) + tag(1B) + payload_len(1B) + payload
record_len = 1(type) + 1(tag) + 1(payload_len) + payload_len
```

例如 tag2 的 payload 是字符串 `google`：

```
payload_text = google
payload_hex  = 676f6f676c65
record       = 0009 01 02 06 676f6f676c65
               ^^^^ ^^ ^^ ^^ payload
               len  type tag payload_len
```

依次对所有record转换，再按照tag大小，进行排序拼接。

组装后会传入 0x181980进行压缩，对此函数入参和出参分别打印一下 (UUID和设备信息 敏感信息打码了)

![image-20260706092653189](https://bbs.kanxue.com/upload/attach/202607/910288_CXYDJ4E9G4AJZY3.png)

raw_packet包的数据

![image-20260706092118237](https://bbs.kanxue.com/upload/attach/202607/910288_39R46HRE9N7C6TY.png)

### 3.12 `sub_181980 info2_gzip_raw_packet_to_jbytearray`：raw_packet 进入 gzip

这个函数的作用是把 native 的 `raw_packet` 复制到 Java byte[]，再调用压缩逻辑，返回 gzip 后的 byte[]。

伪代码：

```c
jbyteArray info2_gzip_raw_packet_to_jbytearray(JNIEnv *env, uint8_t *raw_packet, int raw_len) {
    // 先解析/查找 gzip helper 类和方法，真实代码里通过混淆字符串和 JNI 反射完成。
    jclass gzip_helper_class = find_class_or_reflect(...);
    jmethodID gzip_method = get_method_id(...);

    // 创建 Java byte[]，长度等于 raw_packet 长度。
    jbyteArray input = env->NewByteArray(raw_len);
    // 把 native 明文 raw_packet 拷贝到 Java byte[]。
    env->SetByteArrayRegion(input, 0, raw_len, raw_packet);

    // 调用压缩方法，返回 gzip 后的 byte[]。
    jbyteArray gzip_result = env->CallStaticObjectMethod(gzip_helper_class, gzip_method, input);

    // 删除临时局部引用。
    env->DeleteLocalRef(input);
    return gzip_result;
}
```

对应反编译核心：

```c
v40 = env->NewByteArray(a3);                 // 创建长度为 raw_len 的 Java byte[]。
env->SetByteArrayRegion(v40, 0, a3, a2);     // 把 a2 指向的 raw_packet 写入 byte[]。
env->CallVoidMethod(..., v40);               // 调用压缩相关方法，把 byte[] 作为输入。
v38 = env->CallObjectMethod(...);            // 获取压缩后的 byte[]。
return v38;                                  // 返回 gzip 结果。
```

注意：主函数传入该函数的是压缩前明文：

```c
info2_gzip_raw_packet_to_jbytearray(a1, v63, (unsigned int)v61); // v63 是 raw_packet 指针，v61 是 raw_packet 长度。
```

所以 hook 这个函数入口可以直接拿到完整 `raw_packet`。

结合AI分析

![image-20260706092537186](https://bbs.kanxue.com/upload/attach/202607/910288_3F9FKMCGN8AW4K8.png)

gzip压缩实际上是ByteArrayOutputStream + GZIPOutputStream

### 3.13 `sub_1E5F4 info2_aes_base64_prefix_wrap`：最终返回字符串

![image-20260706092926511](https://bbs.kanxue.com/upload/attach/202607/910288_3QU23YQ3VFEMZKR.png)

该函数完成最终封装。

伪代码：

```c
jstring info2_aes_base64_prefix_wrap(JNIEnv *env, uint8_t *gzip_bytes, int gzip_len, char *prefix) {
    // 先计算 PKCS7 padding 后的 AES 密文长度。
    int cipher_len = pkcs7_cipher_len(gzip_len, 16);
    // 分配密文输出缓冲区。
    uint8_t *cipher = malloc(cipher_len);

    // AES key 已动态验证为固定字符串 "pdd_aes_180121_1"。
    uint8_t key[16] = "pdd_aes_180121_1";
    // AES-CBC 的 IV 是 16 字节全 0。
    uint8_t iv[16] = {0};

    // 对 gzip 后的数据执行 AES-128-CBC/PKCS7 加密。
    aes_cbc_encrypt_pkcs7(key, iv, gzip_bytes, gzip_len, cipher);

    // 输出字符串缓冲区，先放 prefix，再放 Base64。
    char *out = malloc(cipher_len * 2);
    strcpy(out, prefix);               // prefix 当前为 "2af"。
    // Base64 从 out+3 开始写，正好接在 "2af" 后面。
    base64_encode(cipher, cipher_len, out + 3);

    // 转成 Java String 返回给 Java 层。
    jstring result = env->NewStringUTF(out);

    // 释放 native 临时缓冲区。
    free(gzip_bytes);
    free(cipher);
    free(out);
    return result;
}
```

对应反编译核心：

```c
v8 = sub_165424(a3);                         // 根据 gzip_len 计算 PKCS7 后密文长度。
v9 = malloc(v8);                             // 分配 AES 密文缓冲区。
v15 = *(_OWORD *)sub_2E034(17, 17, 16);      // 解出 16 字节 AES key。
info2_aes_cbc_encrypt_zero_iv(&v15, a2, a3, v9); // 使用 zero IV 做 AES-CBC 加密。

v11 = malloc(2 * v8);                        // 分配最终字符串缓冲区。
memcpy(v11, a4, strlen(a4) + 1);             // 先写入 prefix，当前 prefix 为 "2af"。
info2_base64_encode(v9, v8, v11 + 3);        // Base64 写到 prefix 后面。
result = env->NewStringUTF(v11);             // 转成 Java String 返回。
```

`info2_aes_cbc_encrypt_zero_iv` 又能证明 IV 为 0：

```c
v5[0] = 0;                                   // IV 前 8 字节为 0。
v5[1] = 0;                                   // IV 后 8 字节为 0。
return aes_cbc_impl(key, v5, plain, plain_len, out); // 使用 zero IV 进入底层 AES-CBC。
```

aes函数 入参和出参

![image-20260706093537784](https://bbs.kanxue.com/upload/attach/202607/910288_8AAPTNKUFTNHAA8.png)

Base64 函数 `info2_base64_encode` 使用标准字母表，并在剩余 1 或 2 字节时写 `=` padding。

Hook 验证：

![image-20260706094815896](https://bbs.kanxue.com/upload/attach/202607/910288_ZYWSCPGE23DAYKG.png)

## 4. 核心数据结构：TLV record

这个函数生成的原始数据叫 `raw_packet`。它由很多条小记录组成，每条记录就是一个 `tag`。

可以把它理解成一个表：

```
tag 1  = 设备序列号 / fallback
tag 2  = brand
tag 3  = device
...
tag 32 = Java 传入的 timestamp_ms
tag 33 = 时间派生随机数
tag 34 = UUID
```

### 4.1 record 的最终编码格式

每条 record 写进 `raw_packet` 时，格式是：

```
uint16_be record_len
uint8     type
uint8     tag
uint8     payload_len
bytes     payload
```

说明：

| 字段 | 大小 | 含义 |
|-|-|-|
| `record_len` | 2 字节 | 后面 `type + tag + payload_len + payload` 的长度，大端序 |
| `type` | 1 字节 | 当前固定为 `0x01` |
| `tag` | 1 字节 | 字段编号，例如 `0x20` 是 tag32 |
| `payload_len` | 1 字节 | payload 长度 |
| `payload` | 变长 | 具体字段值 |

例如 payload 为 8 字节的 `tag32`，record 长度就是：

```
type 1 字节 + tag 1 字节 + payload_len 1 字节 + payload 8 字节 = 11
record_len = 0x000b
```

### 4.2 native 内部的 record slot

在拼包前，native 先把每条 record 放进固定大小的临时槽位。

槽位大小是：

```
0x210 = 528 字节
```

布局可以还原为：

```
offset 0x000: tag，1 字节
offset 0x001: payload 缓冲区
offset 0x204: type/标记，通常是 0x01 00 00 00
offset 0x208: payload_len，4 字节
offset 0x20c: record_len，4 字节，值为 payload_len + 3
```

相关 helper：

```
sub_1697AC(slot, tag, ptr, len)
  写 bytes/string payload

sub_169840(slot, tag, value, len)
  把整数按 big-endian 写入 payload

sub_1699B8(env, slot, tag, jstring, mode)
  从 Java String 写 payload
```

---

## 5. raw_packet 格式

所有 record 拼好后，会形成 `raw_packet`：

```
uint32_le version
uint16_be body_len
record[]
```

当前版本号固定为：

```
version = 1
```

所以包头的前 4 字节是小端序：

```
01 00 00 00
```

`body_len` 是后面所有 record 的总长度，不包含前 6 字节 packet header。

伪代码：

```python
body = b"".join(record.encode() for record in records)
raw_packet = struct.pack("<I", 1) + struct.pack(">H", len(body)) + body
```

---

## 6. 0x1CFAC 的整体流程

把混淆状态机去掉后，函数可以简化成下面这个流程：

```c
jstring info2(JNIEnv *env, jclass clazz, Context context, jlong timestamp_ms) {
    timeval tv = gettimeofday();

    refresh_cached_tags_if_needed(env, context, tv.tv_sec);

    records = cached_device_records;
    records += tag32_from_timestamp(timestamp_ms);
    records += tag33_from_time(tv.tv_sec, tv.tv_usec);
    records += tag34_from_uuid();

    raw_packet = build_raw_packet(records);
    gzip_bytes = gzip(raw_packet);

    result = "2af" + base64(aes_cbc_pkcs7_encrypt(gzip_bytes));
    return NewStringUTF(result);
}
```

真实 native 里分成几个阶段：

| 阶段 | 关键位置/调用 | 作用 |
|-|-|-|
| 取时间 | `gettimeofday(&tv, 0)` | 用于 tag33，也用于判断缓存是否过期 |
| 刷新缓存 | `pthread_rwlock_wrlock/rdlock` | 保护全局 tag 缓存 |
| 采集静态字段 | `sub_16C2F4/sub_16C648/sub_16C6C4/sub_16CD40/sub_16F1D4` | 写 tag1 到 tag31，tag29 可选 |
| 写动态字段 | `sub_169840(&s, 32, a4, 8)` | 写 tag32，即 Java 传入的 `timestamp_ms`。这里的 `a4` 是 IDA 原始参数名 |
| 写随机字段 | `srand48/lrand48` + `sub_169840(..., 33, ..., 8)` | 写 tag33 |
| 写 UUID | `sub_172124(a1, &unk_1D3AD5)` | 写 tag34 的 32 位 hex 字符串 |
| 拼 raw_packet | `malloc(v61)` + `memset(v63, 0, v62)` | 生成 packet header 和连续 record |
| gzip | `info2_gzip_raw_packet_to_jbytearray` | 把 raw_packet 压缩成 Java byte[] |
| AES/Base64/前缀 | `info2_aes_base64_prefix_wrap` | 最终生成 Java String |

---

## 7. 全局缓存机制

函数里有几组重要全局变量：

| 地址/名字 | 作用 |
|-|-|
| `dword_1CFAE4` | 全局 record slot 数组，每个 slot `0x210` 字节 |
| `dword_1D3CE4` | 当前已缓存 record 数量 |
| `dword_1D3CE8` | 调用/刷新计数 |
| `qword_1D3CF0` | 上次刷新时的 `tv_sec` |
| `stru_1D8E00` | `pthread_rwlock_t`，读写锁 |
| `byte_1D3AD4` 到 `dword_1D3CE0` | 一个独立的全局 record slot，对应 tag34 |

缓存存在的原因：

```
tag1..tag31 大部分是设备、系统、Telephony、环境检测信息。
这些字段不需要每次调用都重新采集，所以 native 会缓存。
```

刷新条件大致是：

```
1. 计数达到特定周期，例如 10000 次边界；
2. 距离上次刷新超过 86400 秒；
3. 缓存尚未初始化。
```

如果不需要刷新，本次调用只补充动态字段：

```
tag32 = timestamp_ms
tag33 = 当前时间派生值
tag34 = UUID 字符串
```

---

## 8. tag32：Java 传入的 timestamp_ms

反编译关键点：

```c
sub_169840(&s, 32, a4, 8); // a4 是 IDA 原始参数名，对应 Java 传入的 timestamp_ms。
```

含义：

```
tag = 32
value = timestamp_ms。反编译里这个参数原始显示为 a4
长度 = 8 字节
字节序 = big-endian
```

如果 `timestamp_ms = 0x0000019f1cb27649`，payload 就是：

```
00 00 01 9f 1c b2 76 49
```

---

## 9. tag33：由 gettimeofday 派生

反编译关键点：

```c
gettimeofday(&tv, 0);
srand48(tv_sec);
hi = lrand48();
srand48(tv_usec);
lo = lrand48();
tag33 = lo + (hi << 32);
sub_169840(record, 33, tag33, 8);
```

也就是：

```
tag33 高 32 位 = srand48(tv_sec) 后第一次 lrand48()
tag33 低 32 位 = srand48(tv_usec) 后第一次 lrand48()
```

Python 复现：

```python
def lrand48_first(seed: int) -> int:
    state = (((seed & 0xffffffff) << 16) + 0x330e) & ((1 << 48) - 1)
    state = (0x5DEECE66D * state + 0xB) & ((1 << 48) - 1)
    return (state >> 17) & 0x7fffffff

tag33 = (lrand48_first(tv_sec) << 32) | lrand48_first(tv_usec)
```

---

## 10. tag34：UUID

反编译关键点：

```c
sub_172124(a1, &unk_1D3AD5);
qword_1D3CD8 = 0x2000000001LL;
byte_1D3AD4 = 0x22;
dword_1D3CE0 = 0x23;
```

这里的 `0x22` 是十进制 `34`，也就是 tag34。

`sub_172124` 通过 JNI/反射调用 Java 侧 UUID 相关逻辑，最终把类似下面的字符串写入 payload：

```
UUID.randomUUID().toString().replaceAll("-", "")
```

结果是 32 字节 ASCII hex，例如：

```
27d4713b922140f4b1a45ae47be7cc08
```

所以 tag34 的 payload 长度是 `0x20`，record_len 是：

```
0x20 + 3 = 0x23
```

---

## 11. tag 来源总表

原始 tag 来源总表如下：

| tag | 来源/含义 | 写入方式 |
|-|-|-|
| 1 | `ro.serialno`，为空时 fallback 为 `unknown` | string |
| 2 | `ro.product.brand` | string |
| 3 | `ro.product.device` | string |
| 4 | `ro.product.model` | string |
| 5 | `ro.product.manufacturer` | string |
| 6 | `ro.product.board` | string |
| 7 | `ro.build.display.id` | string |
| 8 | build id / incremental / type / tags 拼接 | string |
| 9 | `ro.build.version.release` | string |
| 10 | `ro.build.version.sdk` | 1 字节整数 |
| 11 | `ro.build.date.utc` | 4 字节整数 |
| 12 | `stat("/system/build.prop")` 时间字段 | 4 字节整数 |
| 13 | 空字段 | empty |
| 14 | 空字段 | empty |
| 15 | 空字段 | empty |
| 16 | 空字段 | empty |
| 17 | 空字段 | empty |
| 18 | `TelephonyManager.getSimState()` | 1 字节整数 |
| 19 | `TelephonyManager.getSimOperatorName()` | string |
| 20 | `TelephonyManager.getSimCountryIso()` | string |
| 21 | 空字段 | empty |
| 22 | 网络类型名，例如 `UNKNOWN/LTE/...` | string |
| 23 | `TelephonyManager.getNetworkOperator()` 前 3 位 MCC | string |
| 24 | `TelephonyManager.getNetworkOperator()` 后续 MNC | string |
| 25 | `TelephonyManager.getNetworkOperatorName()` | string |
| 26 | `TelephonyManager.getNetworkCountryIso()` | string |
| 27 | `TelephonyManager.getDataState()` | 1 字节整数 |
| 28 | `TelephonyManager.getDataActivity()` | 1 字节整数 |
| 29 | `/proc/version` 检测，当前环境通常缺失 | optional |
| 30 | `com.xunmeng.pinduoduo.secure.EU.gad()` | 8 字节整数 |
| 31 | 环境风险 flags | 1 字节整数 |
| 32 | Java 传入的 `timestamp_ms` | 8 字节整数 |
| 33 | `gettimeofday` 派生随机值 | 8 字节整数 |
| 34 | UUID 去横线后的 32 位 hex | string |

本次 hook 样本中的 tag 来源和值如下：

| tag | 来源/含义 | 本次样例值 | payload_hex | raw_packet record |
|-|-|-|-|-|
| 1 | `ro.serialno`，为空时 fallback 为 `unknown` | `unknown` | `756e6b6e6f776e` | `000a010107756e6b6e6f776e` |
| 2 | `ro.product.brand` | `google` | `676f6f676c65` | `0009010206676f6f676c65` |
| 3 | `ro.product.device` | `oriole` | `6f72696f6c65` | `00090103066f72696f6c65` |
| 4 | `ro.product.model` | `Pixel 6` | `506978656c2036` | `000a010407506978656c2036` |
| 5 | `ro.product.manufacturer` | `Google` | `476f6f676c65` | `0009010506476f6f676c65` |
| 6 | `ro.product.board` | `oriole` | `6f72696f6c65` | `00090106066f72696f6c65` |
| 7 | `ro.build.display.id` | `UP1A.AAAA.BBB` | `hook获取` | `hook获取` |
| 8 | build id / incremental / type / tags 拼接 | `UP1A.AAAA.BBB/CCCCCCCC:user/release-keys` | `hook获取` |  |
| 9 | `ro.build.version.release` | `14` | `3134` | `00050109023134` |
| 10 | `ro.build.version.sdk` | `34` / `0x22` | `22` | `0004010a0122` |
| 11 | `ro.build.date.utc` | `1693627309` / `0x64f2b3ad` | `64f2b3ad` | `0007010b0464f2b3ad` |
| 12 | `stat("/system/build.prop")` 时间字段 | `2009-01-01 08:00` / `0x495c0780` | `495c0780` | `0007010c04495c0780` |
| 13 | 空字段 | 空 | `空` | `0003010d00` |
| 14 | 空字段 | 空 | `空` | `0003010e00` |
| 15 | 空字段 | 空 | `空` | `0003010f00` |
| 16 | 空字段 | 空 | `空` | `0003011000` |
| 17 | 空字段 | 空 | `空` | `0003011100` |
| 18 | `TelephonyManager.getSimState()` | `1` / `0x01` | `01` | `000401120101` |
| 19 | `TelephonyManager.getSimOperatorName()` | 空字符串 | `空` | `0003011300` |
| 20 | `TelephonyManager.getSimCountryIso()` | 空字符串 | `空` | `0003011400` |
| 21 | 空字段 | 空 | `空` | `0003011500` |
| 22 | 网络类型名，例如 `UNKNOWN/LTE/...` | `UNKNOWN` | `554e4b4e4f574e` | `000a011607554e4b4e4f574e` |
| 23 | `TelephonyManager.getNetworkOperator()` 前 3 位 MCC | 空字符串 | `空` | `0003011700` |
| 24 | `TelephonyManager.getNetworkOperator()` 后续 MNC | 空字符串 | `空` | `0003011800` |
| 25 | `TelephonyManager.getNetworkOperatorName()` | 空字符串 | `空` | `0003011900` |
| 26 | `TelephonyManager.getNetworkCountryIso()` | `cn` | `636e` | `0005011a02636e` |
| 27 | `TelephonyManager.getDataState()` | `0` / `0x00` | `00` | `0004011b0100` |
| 28 | `TelephonyManager.getDataActivity()` | `0` / `0x00` | `00` | `0004011c0100` |
| 29 | `/proc/version` 检测，可选字段 | 本次未写入 | 无 | 无 record |
| 30 | `com.xunmeng.pinduoduo.secure.EU.gad() 从 Java 层 EU.gad() 拿到的一个安装/设备相关 ID` | `hook获取` | `hook获取` | `hook获取` |
| 31 | 环境风险 flags | `0` / `0x00` | `00` | `0004011f0100` |
| 32 | Java 传入的 `timestamp_ms` | `0x0000019f20e3cb58` | `0000019f20e3cb58` | `000b0120080000019f20e3cb58` |
| 33 | `gettimeofday` 派生随机值 | `0x410f2e2d77e8ce53` | `410f2e2d77e8ce53` | `000b012108410f2e2d77e8ce53` |
| 34 | UUID 去横线后的 32 位 hex | `14485da47cae4a908c0761dbd42ba9e6` | `3134343835646134376361653461393038633037363164626434326261396536` | `00230122203134343835646134376361653461393038633037363164626434326261396536` |

---

## 12. gzip 阶段

主函数调用：

```c
info2_gzip_raw_packet_to_jbytearray(env, raw_packet, raw_len)
```

这个函数做的事情：

```
1. 创建 Java byte[]
2. 把 native raw_packet 拷贝到 Java byte[]
3. 通过 Java/Native 压缩流程得到 gzip 结果
4. 返回 gzip 后的 jbyteArray
```

从最终复现看，gzip 格式为：

```
gzip header = 1f 8b 08 00 00 00 00 00 00 00
body        = raw deflate stream
trailer     = crc32(raw_packet) + isize，小端序
```

Python 复现核心：

```python
compressor = zlib.compressobj(6, zlib.DEFLATED, -15)
deflated = compressor.compress(raw_packet) + compressor.flush()
gzip_bytes = header + deflated + trailer
```

---

## 13. AES/Base64/前缀阶段

主函数最后调用：

```c
info2_aes_base64_prefix_wrap(env, gzip_bytes, gzip_len, prefix)
```

该函数内部逻辑：

```
1. 根据 gzip_len 计算 PKCS7 padding 后的 AES 密文长度
2. 解出 AES key："pdd_aes_180121_1"
3. 使用 AES-128-CBC 加密
4. IV 为 16 字节 0
5. 对密文做 Base64
6. 在 Base64 前面加 "2af"
7. 调用 NewStringUTF 返回 Java String
```

最终形式：

```
2af + base64(ciphertext)
```

---

## 14. 关键调用证据

IDA 中 `0x1CFAC` 的关键调用点：

| 地址 | 调用 | 说明 |
|-|-|-|
| `0x1D228` | `gettimeofday` | 获取 `tv_sec/tv_usec` |
| `0x1D528` | `pthread_rwlock_wrlock` | 写锁刷新缓存 |
| `0x1DE74` | `pthread_rwlock_rdlock` | 读锁读取缓存 |
| `0x1DF8C` | `sub_16C2F4` | 采集 Build/system property tag |
| `0x1DFA4` | `sub_16C648` | 采集 `/system/build.prop` stat 信息 |
| `0x1DFC0` | `sub_16C6C4` | 采集 Telephony/network tag |
| `0x1DFE4` | `sub_16CD40` | 可选 tag29 |
| `0x1D8DC` | `sub_16F1D4` | 写 tag31 环境风险 flags |
| `0x1DC9C` | `sub_169840` | 写 tag32 |
| `0x1E1A4` | `srand48` | tag33 低位随机源 |
| `0x1E1A8` | `lrand48` | tag33 低位随机源 |
| `0x1E538` | `info2_gzip_raw_packet_to_jbytearray` | gzip 阶段 |
| `0x1D368` | `info2_aes_base64_prefix_wrap` | AES/Base64/前缀阶段 |

---

## 15.发送请求测试

![image-20260702184240675](https://bbs.kanxue.com/upload/attach/202607/910288_HQMQAUKYZ6ZDRWB.png)

相关的去混淆脚本和Hook脚本会打包到附件中

上传的附件：
- 相关附件.zip

（10.33MB，94次下载）

---

# 回复

## 回复 by xingbing (#2)

*2026-7-6 15:33*

学习。

## 回复 by 随风而行aa (#3)

*2026-7-6 15:42*

看看

## 回复 by mb_jnmxfjku (#4)

*2026-7-6 16:06*

666

## 回复 by MaYil (#5)

*2026-7-6 16:10*

感谢分享

## 回复 by 大众 (#6)

*2026-7-6 16:12*

感谢分享

## 回复 by mb_ykavguun (#7)

*2026-7-6 16:58*

6

## 回复 by mb_ykavguun (#8)

*2026-7-6 16:58*

6

## 回复 by mb_ykavguun (#9)

*2026-7-6 17:01*

6

## 回复 by 乐子人 (#10)

*2026-7-6 18:59*

6

## 回复 by wx_阿白_534 (#11)

*2026-7-6 19:49*

6

## 回复 by 温泉划水鱼 (#12)

*2026-7-6 20:13*

6

## 回复 by wx_北极星_493 (#13)

*2026-7-7 03:08*

66

## 回复 by mb_ldbucrik (#14)

*2026-7-7 08:50*

感谢分享

## 回复 by mb_vrkpxsoe (#15)

*2026-7-7 09:40*

华

## 回复 by 空谈误国 (#16)

*2026-7-7 09:49*

感谢分享

## 回复 by 错过 (#17)

*2026-7-7 10:49*

666

## 回复 by 我就是小熊猫 (#18)

*2026-7-7 11:13*

6666

## 回复 by 我不是卷王 (#19)

*2026-7-7 11:15*

6

## 回复 by myios (#20)

*2026-7-7 13:31*

6

## 回复 by 茅山小僧 (#21)

*2026-7-7 13:44*

学习一下

## 回复 by xianhuimin (#22)

*2026-7-7 13:59*

666

## 回复 by mb_cbgtaveo (#23)

*2026-7-7 14:42*

66666666666

## 回复 by kingking888 (#24)

*2026-7-7 15:11*

6666

## 回复 by jmpews (#25)

*2026-7-7 15:42*

感谢分享

## 回复 by mb_ugsctkiu (#26)

*2026-7-7 15:45*

666666666

## 回复 by 用户名null (#27)

*2026-7-7 15:45*

1

## 回复 by mb_yftogafn (#28)

*2026-7-7 15:46*

666666

## 回复 by wx_雷火丰 (#29)

*2026-7-7 15:47*

666

## 回复 by 小黄鸭爱学习 (#30)

*2026-7-7 15:47*

1111

## 回复 by 丶咖啡猫丶 (#31)

*2026-7-7 15:50*

666

## 回复 by Botton (#32)

*2026-7-7 15:50*

666

## 回复 by wx_喵不吃 (#33)

*2026-7-7 15:52*

1

## 回复 by yangshuang (#34)

*2026-7-7 15:53*

感谢分享

## 回复 by Imxz (#35)

*2026-7-7 16:02*

TQL

## 回复 by 女少 (#36)

*2026-7-7 19:07*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by YANG、 (#37)

*2026-7-7 22:47*

感谢分享

## 回复 by mb_qimctavn (#38)

*2026-7-8 08:29*

6

## 回复 by mb_zsmeyemp (#39)

*2026-7-8 10:31*

66666

## 回复 by Thehepta (#40)

*2026-7-8 11:04*

1

## 回复 by mb_qztkkwxt (#41)

*2026-7-8 13:38*

666

## 回复 by mb_uvyukvot (#42)

*2026-7-8 16:02*

666

## 回复 by FMNS (#43)

*2026-7-8 20:58*

666

## 回复 by bisoso (#44)

*2026-7-9 01:39*

感谢分享

## 回复 by wx_kx92911 (#45)

*2026-7-9 09:51*

感谢分析

## 回复 by mb_ahyhoece (#46)

*2026-7-9 15:19*

123132

## 回复 by linglonger (#47)

*2026-7-9 20:53*

66666666666

## 回复 by wx_Dispa1r (#48)

*2026-7-10 10:47*

1

## 回复 by ulong9527 (#49)

*2026-7-11 01:01*

6666

## 回复 by 上官兮唐 (#50)

*2026-7-11 01:05*

感谢分享

## 回复 by manyuegong33 (#51)

*2026-7-11 17:04*

666

## 回复 by iBa0 (#52)

*2026-7-11 17:18*

1

## 回复 by mb_vjpiriil (#53)

*2026-7-11 22:51*

666

## 回复 by Zepp7289 (#54)

*2026-7-12 00:40*

6

## 回复 by mb_iiumogmn (#55)

*2026-7-12 22:59*

感谢分享

## 回复 by mb_ajxntfzc (#56)

*2026-7-13 09:44*

666

## 回复 by 机车王子 (#57)

*2026-7-13 10:50*

你的分享对大家帮助很大，非常感谢！

## 回复 by 伊苏尔德 (#58)

*2026-7-13 15:04*

1

## 回复 by AK1988DA (#59)

*2026-7-13 16:06*

000

## 回复 by mb_cezdpjbw (#60)

*2026-7-14 14:11*

1

## 回复 by mb_pmgifpme (#61)

*2026-7-14 14:41*

1

## 回复 by kzx0808 (#62)

*2026-7-14 15:29*

6

## 回复 by mb_degalzhb (#63)

*2026-7-15 14:31*

666

## 回复 by ID蝴蝶 (#64)

*2026-7-16 15:37*

感谢分享

## 回复 by 3cly (#65)

*2026-7-16 16:16*

1

## 回复 by miyuecao (#66)

*2026-7-16 16:59*

666

## 回复 by wx_huhu_859 (#67)

*2026-7-16 21:35*

11

## 回复 by mb_brwwdknt (#68)

*2026-7-20 20:55*

感谢分享

## 回复 by 简单的简单 (#69)

*2026-7-21 00:24*

666

## 回复 by mb_gjhmacqd (#70)

*2026-7-21 09:41*

666

## 回复 by mb_ifjlatem (#71)

*2026-7-21 10:10*

666

## 回复 by Harden13 (#72)

*2026-7-21 14:35*

666

## 回复 by wx_插曲 (#73)

*2026-7-23 12:34*

6

## 回复 by 学习的小秦 (#74)

66666

## 回复 by mb_jjhjwyge (#75)

666666

## 回复 by beierer (#76)

感谢分享
