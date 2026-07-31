---
title: '[原创]AI逆向某视频签名算法X-Medusa全过程'
url: https://bbs.kanxue.com/thread-291105.htm
tid: 291105
author: scxc
date: '2026-05-05'
tags: [Android安全, 原创, 逆向分析, 协议分析, 混淆加固, 脱壳反混淆]
crawled_at: '2026-07-31T13:53:25+08:00'
replies: 23
---

# AI逆向某视频签名算法X-Medusa全过程

>
> 本文仅记录一次针对移动端 native 签名逻辑的逆向分析过程，用于安全研究、算法学习和逆向工程方法论交流。文中涉及的脚本、地址和结论均来自本地样本与模拟环境验证，不讨论任何绕过风控、批量请求或业务滥用场景。
>
>
>

## 前言

这次分析的目标是某视频 App 29.3 版本中的一个 native 签名头：`X-Medusa`。

样本位于 Android native so：

```
libmetasec_ml.fully_deobf.so
```

外层调用函数是：

```
sub_D4F3C(url, headers_blob)
```

这个函数会一次性生成多个签名头：

```
X-Argus
X-Gorgon
X-Helios
X-Khronos
X-Ladon
X-Medusa
```

本文重点只讲 `X-Medusa`。

我最终将 `X-Medusa` 主路径还原成了纯 Python，可以在不启动 native VM 的情况下，只输入同一次运行的动态值，生成和 native 一致的 `X-Medusa`。

整个过程并不是一开始就直接进入算法还原。前半段我先用 Cursor 的 Opus 模型搭建和调通ExAndroidNativeEmu 调用环境，它帮我把 `sub_D4F3C` 的 native 签名调用跑起来，也就是能从本地 emu里拿到各个签名头。到这一步后，继续深入 `X-Medusa` 内部时，分析基本卡在 SM3 和周边混淆逻辑，无法继续稳定拆出后续 VM 路径。

后半段切到 Codex 后，分析方式变成了“动态 trace + 局部 Python lift + native 对照验证”。也就是本文后面记录的过程：不再只看静态伪代码，而是对每个 VM 片段抓输入、输出和实际内存读写变化，再把能证明的局部逻辑写成 Python，最后组合成完整 pipeline。

最终验证结果：

```
[rebuild] src_a_match=True x_medusa_match=True
```

也就是说，Python 重建出的明文 `src_a` 和最终 `X-Medusa` 都与 native 同一次运行完全一致。

## 分析环境

本次使用的是一个基于 ExAndroidNativeEmu 的本地模拟环境。目录中已有调用示例：

```
dy_sign_send.py
```

它负责：

```
1. 初始化 Android native emu
2. 加载 libmetasec_ml.fully_deobf.so
3. 调 JNI_OnLoad
4. 调用 sub_D4F3C
5. 解析返回的签名 header
```

分析过程中还遇到一个环境问题：系统里存在不匹配的 Unicorn dylib，会影响 emu 运行。后面所有 native 对照命令都统一这样跑：

```bash
env -u DYLD_LIBRARY_PATH python3 ...
```

避免 Python 加载错误的 Unicorn 动态库。

## 第一步：先定位 X-Medusa 在 sub_D4F3C 中的位置

一开始没有直接钻 VM，而是先观察 `sub_D4F3C` 的输出 map/string 插入位置。

最终确认各 header 的插入点：

```
0xca684 -> X-Gorgon
0xcaa5c -> X-Khronos
0xcb09c -> X-Argus
0xcb4dc -> X-Ladon
0xcba30 -> X-Medusa
0xcbe64 -> X-Helios
0x46a70 -> X-Neptune
```

其中 `X-Medusa` 的关键路径是：

```
sub_D4F3C
  -> native wrapper
  -> VM entry lib+0x445b8
  -> Medusa VM bytecode call lib+0xd8978
  -> bytecode entry base+0x18bdd0
  -> X-Medusa 插入点 lib+0xcba30
```

这里最重要的是确定 VM 执行边界：

```
VM interpreter entry: lib+0x445b8
Medusa bytecode call: lib+0xd8978
VM bytecode entry:    base+0x18bdd0
```

有了这个边界，后续 hook 只在 Medusa VM 活跃期间记录，避免被 JNI 初始化、其它 header 或环境探测逻辑干扰。

## 第二步：确认 VM 解释器形态

最开始静态看 `0x445b8` 这个 VM 入口，会发现它很像 MIPS 风格解释器：

```
32 个虚拟寄存器
load/store
branch
R/I/J 类似的指令形态
```

但不能直接把它当标准 MIPS。

我写了一个 Python VM 模型和 native 状态对比脚本，核心思路是：

```
1. 在 native VM 初始化后抓 VM state
2. 在 VM fetch/decode 点抓每一步 PC 和寄存器
3. Python 模型模拟一条
4. 和 native 下一步状态对比
```

VM fetch/decode 点：

```
lib+0x4466c
```

对比后得到一个重要结论：

```
这个 VM 是 MIPS-like，但不是标准 MIPS。
r0 也不是硬编码 zero。
```

也就是说，不能做这样的假设：

```
r0 永远等于 0
```

部分 R-type 指令的目标寄存器编码也和标准 MIPS 有差异。所以后续还原关键逻辑时，我没有完全依赖静态反汇编，而是优先使用动态 trace 的输入、输出和实际内存读写变化。

## 第三步：从最终 X-Medusa 反推 packet 结构

接下来先看最终 `X-Medusa` 是什么。

通过跟踪 base64 调用链：

```
0xdc608 -> 0xee588 -> 0x10dd84
```

确认 `X-Medusa` 是标准 base64，使用普通字母表：

```
ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
```

base64 解码后得到一个 raw packet。继续跟踪最终 packet 的 copy 序列，得到结构：

```
packet = fixed20 || var2 || 00 || 01 || body_first || body

fixed20     = c312f41237faabe817c5282916383c6297dd950a
var2        = 2 字节变量，后来确认等于 d71bc_seed32_le[:2]
00 01       = 固定 flags
body_first  = AES-like 输出的第 32 字节
body        = patch 后的 second_buffer
```

VM copy 点如下：

```
vm+0x191234: copy dst+0x00 len=20
vm+0x191264: copy dst+0x14 len=2
vm+0x1912a4: copy dst+0x16 len=1
vm+0x1912dc: copy dst+0x17 len=1
vm+0x191320: copy dst+0x18 len=1
vm+0x191360: copy dst+0x19 len=N
```

这个阶段先写出最外层 Python：

```python
packet = fixed20 + var2 + b"\x00\x01" + bytes([body_first]) + body
X_Medusa = base64.b64encode(packet)
```

## 第四步：倒推 body 的来源

继续追 packet body，发现最终 body 来自一个中间 buffer，但不是直接复制出来的。

它的生成分成两步：

```
1. 先拼 second_buffer
2. 再 patch second_buffer 前 31 个 64-bit word 的稀疏 bit 位
```

second_buffer 布局：

```
second_buffer =
  byte[0]      = 0xa6
  byte[1:9]   = seed8
  byte[9:...] = first_intermediate
  tail         = tail2
```

其中：

```
seed8 = uint32_le(rand@vm+0x18ec30) || 013a0b00
tail2 = uint32_le(rand@vm+0x18e408)[:2]
```

关键 VM 写点：

```
vm+0x18eda4  写 first byte
vm+0x18edcc  copy 8-byte seed
vm+0x18edf4  copy first_intermediate
vm+0x18ee24  copy tail2
vm+0x1910b8  31 次 sparse word patch
```

这一步对应的 Python lift：

```python
def medusa_second_buffer_layout(first_byte, seed8, first_intermediate, tail2):
    return bytearray(bytes([first_byte]) + seed8 + first_intermediate + tail2)
```

验证方式是同一次 native run 中抓取 copy 的 source/destination/len，然后和 Python 拼出来的 buffer 做 byte-for-byte 比较。

## 第五步：还原 reverse-xor

`first_intermediate` 继续往前追，来到 VM 片段：

```
vm+0x18eb4c..0x18eb98
```

静态看这里时很容易把 source 和 destination 看反。所以我对这个范围做了窄范围动态 trace，记录每一轮：

```
source pointer
destination pointer
source byte
key byte
written byte
loop index
```

最终确认真实逻辑：

```c
for (i = 0; i < n; i++)
    dst[i] = src[n - 1 - i] ^ key4[i & 3];
```

也就是：

```
反向读取 source
正向写入 destination
使用 4 字节循环 xor key
```

key 的来源在前面：

```
vm+0x18eacc..0x18eb00
```

它调用一个短 VM helper，对 `tail2` 做 hash，取低 16 位组成 4 字节 key：

```python
ret = block_189850_tail2_hash(tail2)
k = ret & 0xffff
key4 = bytes([k >> 8, k & 0xff, k >> 8, k & 0xff])
```

验证样例：

```
fe1e -> ret=fff80f18 -> key4=0f180f18
a057 -> ret=fffaff0d -> key4=ff0dff0d
c2c0 -> ret=fff9effb -> key4=effbeffb
```

## 第六步：找到 reverse-xor 的上游 d71bc

reverse-xor 的输入不是原始明文，而是：

```
reverse_source = 8 zero bytes || d71bc_output
```

继续追上游，发现：

```
vm+0x1897d0..0x1897f0  memset(dst, 0x20, len)
vm+0x1897f4..0x18982c  native helper call
native helper          lib+0xd71bc
```

进入 `lib+0xd71bc` 时参数：

```
x0 = dst
x1 = src_a
x2 = len(src_a)
x3 = key32
x4 = 0x20
```

这里一开始也容易误判为某种标准加密算法，但动态 trace 后发现它不是 AES/SM4 这种标准 block cipher，而是一个混淆过的字节状态机。

整体结构：

```
pass 1:
  正向读 src
  反向写 dst
  每个字节混入 key[(i*4)%32] 和 key[((i*4)|1)%32]

pass 2:
  使用 dst[i-1], dst[i-2], i 做前向反馈

tail:
  dst[n-1] ^= dst[n-2]
  dst[0] = (dst[0] ^ dst[1]) + sum(dst[1:])
```

把它 lift 成 Python：

```python
block_d71bc_encode(src, key)
```

然后用 native dump 的 `src_a/key/dst` 验证：

```
block_d71bc_encode(src_a, key) == native dst
```

## 第七步：还原 d71bc 的 key

`d71bc` 的 key32 不是固定表，而是 SM3 结果。

调用链：

```
vm+0x18b6c0 -> wrapper lib+0xdc6bc -> native lib+0xd9bc0
```

对 `b"abc"` 做验证后确认 `lib+0xd9bc0` 是标准 SM3：

```
SM3("abc") =
66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0
```

key material 的构造：

```
sign_key_b64 = rBrarpWnr5SlEUqzs6l92ABQqgo5MUxAUoyuyVJWwow=
sign_key     = base64_decode(sign_key_b64)
seed32_le    = uint32_le(rand@vm+0x18e408)

material68 = sign_key || seed32_le || sign_key
key32      = SM3(material68)
```

所以：

```python
d71bc_key = SM3(sign_key || uint32_le(d71bc_rand) || sign_key)
```

这也解释了前面 `tail2`：

```
tail2 = uint32_le(d71bc_rand)[:2]
```

同一个 rand 同时参与：

```
1. d71bc key
2. reverse-xor key 派生
3. packet var2/tail2
```

## 第八步：确认三个 rand 的作用

只在 Medusa VM 活跃期间 trace rand wrapper，确认共有三次：

```
vm+0x18c788 -> top.f3
vm+0x18e408 -> d71bc seed / tail2 / reverse_key4
vm+0x18ec30 -> second_buffer seed8
```

分别对应：

```
top_rand:
  top.f3 = zigzag32(top_rand)

d71bc_rand:
  seed32_le = uint32_le(d71bc_rand)
  tail2 = seed32_le[:2]
  d71bc_key = SM3(sign_key || seed32_le || sign_key)

seed8_rand:
  seed8 = uint32_le(seed8_rand) || 013a0b00
```

这里有一个坑：`--lock-time` 并不会固定这三个 rand。模拟器里的 rand hook 来自 Python `random.randint(0, 0xffffffff)`，所以想复现同一次签名，必须捕获这三个 rand，或者额外固定随机源。

## 第九步：还原 src_a 明文 protobuf

`d71bc` 的输入 `src_a` 是一个 protobuf-like 明文消息。

入口参数里可以直接拿到：

```
lib+0xd71bc:
  x1 = src_a
  x2 = len(src_a)
```

解析后字段如下：

```
top.f1   bytes   f7e85ffad7d7dc3bd62ac87057cf6118
top.f2   varint  6
top.f3   varint  zigzag32(rand@0x18c788)
top.f4   string  "3019"
top.f6   string  "1611921764"
top.f7   string  "29.3.0"
top.f8   string  "v04.05.05-ml-android"
top.f9   varint  0x80a0a00
top.f10  bytes   8 zero bytes
top.f12  varint  0xd3e825e8
top.f13  bytes   ea24463898fd615efc1982685c362167a1a349ba
top.f14  bytes   SM3(URL query)[0:6]
top.f15  message small tuple
top.f20  string  "none"
top.f21  varint  738
top.f23  message device/time env
top.f24  string  JSON env
```

native 辅助函数也能印证这一点：

```
0x10d580..0x10d718  varint / zigzag encoder
0x10c1ec..0x10c32c  protobuf field writer
```

所以这一段不应该按加密算法理解，而应该按 protobuf builder 还原。

对应 Python 中实现了：

```
proto_varint()
proto_key()
proto_field_varint()
proto_field_bytes()
proto_field_fixed32()
medusa_src_a_rebuild()
medusa_src_a_from_runtime_values()
```

验证方式：

```
native src_a == Python rebuilt src_a
```

## 第十步：top.f14 是 URL query 的 SM3 前 6 字节

对 SM3 helper 的 IO 做 trace 后确认：

```
top.f14 = SM3(URL query bytes)[0:6]
```

注意这里是 query，不包含 path，也不包含问号前面的部分。

样例：

```
SM3(query) =
6cc3b8b4c20643691762996898e9a999546377e6713affda2d66b09c19020aca

top.f14 =
6cc3b8b4c206
```

## 第十一步：f23 里的 pid 和时间

`src_a.f23` 是一段嵌套环境 message，其中几个字段是动态值。

最终确认：

```
f23.f7       = zigzag32(getpid())
f23.12.f28  = zigzag64(X-Khronos_seconds * 1000)
f23.12.f40  = zigzag64(current_epoch_milliseconds)
```

对应 native 证据：

```
lib+0xdc8e4  调 getpid
lib+0x101c64 gettimeofday -> sec * 1000 + usec / 1000
lib+0x101c9c gettimeofday_ms / 1000
```

这里要区分：

```
f23.12.f28 跟 X-Khronos 秒相关
f23.12.f40 跟当前 epoch ms 相关
```

即使锁定 URL 里的 `ts` 或 emu 的 `--lock-time`，`f40` 仍可能变化。要复现同一次签名，就必须使用 native run 里抓到的当前毫秒值。

## 第十二步：f24 是 UUID、MD5、CRC32 组合

`src_a.f24` 是 JSON 字符串，形态如下：

```json
{"cmr":16777216,"cmr2":16777216,"un_h":0,"vpn":0,"kd":694367,"fkd":...,"pd":...,"dyn":"","do":0,"tk":true}
```

先从最终 JSON 里的 `fkd/pd` 回溯 source string：

```
vm+0x18db5c  CRC32(fkd_source)
vm+0x18dd2c  CRC32(pd_source)
```

确认：

```
pd  = signed_crc32(uuid_source)
fkd = unsigned_crc32(md5(uuid_source || "694367").hexdigest())
```

继续追 `uuid_source`，发现它不是直接把 `/dev/urandom` 的 16 字节格式化成 UUID，而是：

```
/dev/urandom first16
  -> 作为 xorshift128+ seed
  -> PRNG 调用两次
  -> raw16 = le64(out0) || le64(out1)
  -> 按 native nibble 顺序填 UUID 模板
```

PRNG 逻辑：

```python
x = s0
y = s1
x ^= (x << 23) & 0xffffffffffffffff
new_s1 = x ^ y ^ (y >> 5) ^ (x >> 18)
out = (new_s1 + y) & 0xffffffffffffffff
new_s0 = y
```

UUID 模板：

```
xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
```

填充规则：

```
每个 byte 先用低 nibble，再用高 nibble
x -> alphabet[nibble]
y -> alphabet[(nibble & 3) | 8]
固定的版本位 4 不消耗随机 nibble
```

用固定 `/dev/urandom` 输入 `--urandom-int 1` 验证：

```
seed16 = 01000000000000000000000000000000
out0   = 0x0000000000800021
out1   = 0x0000000001040041
uuid   = 12000800-0000-4000-8140-040100000000
md5(uuid || "694367").hexdigest()
       = 4a5edaf53834ae3aef2e1fcc298394c4
fkd    = 922802938
pd     = 508833512
```

## 第十三步：bit-slice 提取和 patch

最终 packet 的 body 还会经过一层 bit-slice 处理。

流程：

```
1. 从 second_buffer 前 31 个 64-bit word 中提取 31 字节
2. 这 31 字节拼一个 32-byte block，最后补 00
3. 送入 AES-like transform
4. transform 输出 aes32
5. aes32[:31] patch 回 second_buffer 的前 31 个 64-bit word
6. aes32[31] 放到 packet 的 body_first
```

提取位置：

```
vm+0x18ee54..0x18f024
```

patch 位置：

```
vm+0x190f4c..0x1910b8
```

稀疏 bit lanes：

```
bit positions: 5, 14, 18, 28, 35, 41, 48, 63
```

byte bit permutation：

```
in bit 0 -> out bit 2
in bit 1 -> out bit 0
in bit 2 -> out bit 4
in bit 3 -> out bit 7
in bit 4 -> out bit 5
in bit 5 -> out bit 6
in bit 6 -> out bit 1
in bit 7 -> out bit 3
```

这一步看起来很绕，但动态验证很直接：

```
记录每个 old_word、input_byte、new_word
Python 按相同 bit permutation 和 sparse mask 计算
逐项对比 new_word
```

## 第十四步：AES-like transform

在 `vm+0x193800` 附近能看到明显的 AES GF(2^8) 乘法痕迹：

```
andi ..., 0x80
xori ..., 0x1b
```

但它不是标准 AES。

继续 trace S-box、state permutation、key schedule 和 round-key 顺序后，最终确认它是一个自定义 AES-like 变换：

```
1. 使用 AES MixColumns arithmetic
2. 使用自定义 substitution table
3. 使用自定义 state permutation
4. 使用自定义 round-key byte order
5. 对两个 16-byte block 做 CBC-like chaining
```

固定材料：

```
material16 = d31e3718288a1027baab59f146a09a9c
iv16       = ea180a0336ed352fcd24e4d50018ae54
```

输入：

```
aes_input = extract31 || 00
```

输出：

```
aes32 = medusa_aes_like_transform32(aes_input, material16)
```

其中：

```
aes32[:31] -> patch second_buffer
aes32[31]  -> packet body_first
```

这一阶段逐轮验证了：

```
sub bytes
shift rows
mix columns
round key xor
key schedule
完整 transform32
```

## 第十五步：组合成完整 pipeline

到这里，所有局部块都已经能和 native 对上。

最终 Python pipeline：

```python
d71bc_seed32_le = uint32_le(d71bc_rand)
tail2 = d71bc_seed32_le[:2]
d71bc_key = SM3(sign_key || d71bc_seed32_le || sign_key)
reverse_key4 = hash_tail2_to_key4(tail2)
seed8 = uint32_le(seed8_rand) + bytes.fromhex("013a0b00")

src_a = build_src_a(...)
d71bc_output = block_d71bc_encode(src_a, d71bc_key)
reverse_source = b"\x00" * 8 + d71bc_output
first_intermediate = reverse_xor(reverse_source, reverse_key4)
second_buffer = layout(0xa6, seed8, first_intermediate, tail2)
aes32 = custom_aes_like(extract31(second_buffer), material16)
packet = assemble_packet(tail2, aes32, second_buffer)
X_Medusa = base64(packet)
```

最终封装成：

```python
medusa_x_medusa_from_full_runtime_values(...)
```

以及纯 Python 命令行：

```bash
python3 medusa_pure_x_medusa.py \
  --top-rand 0xef26a2e7 \
  --d71bc-rand 0x2d39c8b6 \
  --seed8-rand 0x93bbc24b \
  --pid 92685 \
  --khronos-sec 1777603264 \
  --current-epoch-ms 1777965666036 \
  --f24-seed16 0x1
```

## 最终验证

端到端验证脚本会在同一次 native run 中抓取：

```
src_a
三个 rand
pid
current_epoch_ms
f24 source
native X-Medusa
```

然后 Python 用这些值重新生成：

```
src_a
packet
X-Medusa
```

验证结果：

```
[rebuild] src_a_match=True x_medusa_match=True
```

这说明：

```
1. src_a 明文结构已还原
2. d71bc helper 已还原
3. reverse-xor 已还原
4. second_buffer layout 已还原
5. bit-slice extract/patch 已还原
6. AES-like transform 已还原
7. packet assembly 和 base64 已还原
```

## 复现同一次签名需要哪些输入

如果要让纯 Python 和某一次 native 运行输出完全一致，至少要提供：

```
URL/query
rand@vm+0x18c788
rand@vm+0x18e408
rand@vm+0x18ec30
pid
X-Khronos seconds
current epoch milliseconds
f24 UUID seed16，或直接给 device_uuid/device_hash_hex/f24_fkd/f24_pd
```

其中最容易忽略的是：

```
1. 三个 rand 不会被 --lock-time 固定
2. f23.12.f40 是当前 epoch ms
3. f24 UUID 不是直接 urandom 格式化，而是 xorshift128+ 后再按 nibble 填模板
```

## AI 在这次逆向中的作用

这篇文章标题里有 “AI逆向”，但它不是指把 so 丢给 AI 然后自动出结果。

这次更接近一种分阶段的人机协作式逆向。

第一阶段用的是 Cursor 的 Opus 模型，重点解决工程入口问题：

```
1. 搭建 ExAndroidNativeEmu 调用环境
2. 加载 so、跑 JNI_OnLoad
3. 调通 sub_D4F3C(url, headers_blob)
4. 拿到 X-Argus / X-Gorgon / X-Helios / X-Khronos / X-Ladon / X-Medusa
```

这个阶段的价值很大，因为没有稳定 emu 调用，就谈不上后续动态验证。但它继续深入时基本只能推到 SM3 和一些外层 helper，面对 VM 内部的数据流、buffer 来源、bit-slice patch、AES-like transform 时，很难继续拆下去。

第二阶段切到 Codex，重点从“能调用”转向“能解释和复现”：

```
1. 围绕 Medusa VM 调用边界写 targeted trace
2. 每次只回答一个小问题，例如某个 buffer 从哪来、某个字段怎么生成
3. 根据同一次 native run 的 IO 写 Python lift
4. 让 Python lift 和 native buffer 做 byte-for-byte 对比
5. 最后把所有局部 lift 合成完整 X-Medusa pipeline
```

这也是后半段能继续推进的关键：不是让模型直接“猜算法”，而是让它不断写脚本、跑验证、缩小未知范围。

整体分工更像这样：

```
人负责：
  - 判断分析方向
  - 选择 hook 点
  - 判断哪些 trace 有价值
  - 识别哪些结论可能是误判

AI 负责：
  - 快速写 trace 脚本
  - 根据动态 IO 归纳局部算法
  - 把局部算法整理成 Python lift
  - 反复跑 native 对照和 self-test
  - 维护 notes、脚本、验证命令
```

这类 VM 保护样本如果只靠静态反编译，很容易被以下问题拖住：

```
1. VM 指令格式和标准 MIPS 不完全一致
2. 静态伪代码容易看反 src/dst
3. VM 栈 slot 在嵌套 helper 中会复用
4. native helper、对象字符串和 VM 寄存器混在一起
5. 同一个字段可能来自 rand/time/pid/urandom 多个动态源
```

AI 的优势在于可以很快写出大量“小而准”的 trace：

```
trace packet
trace memcpy
trace heap writes
trace helper IO
trace rand
trace protobuf source
trace AES-like round
trace f24 source generation
trace full rebuild
```

每个 trace 都只回答一个问题。只要问题拆得足够小，AI 生成代码和整理结论的效率很高。

## 方法论总结

这次逆向最重要的不是某一个算法，而是验证方式：

```
1. 先确定最终输出位置
2. 从最终 packet 往前倒推
3. 每一段只关心输入、输出和实际内存读写变化
4. 写最小 Python lift
5. 和同一次 native run 做 byte-for-byte 对比
6. 再把小块组合成完整 pipeline
```

在 VM 保护场景里，不要迷信静态反编译。

更稳的方式是：

```
用静态分析找大致范围
用动态 trace 确认真实数据流
用 Python lift 固化结论
用 native 对照防止自嗨
```

最终产物不是一份“看起来像”的伪代码，而是可以跑出同样结果的实现。

## 当前边界

这次完整还原的是 `X-Medusa` 主路径，不等于整个 so 或所有 header 都已经完全还原。

当前边界：

```
1. X-Medusa 主路径可以纯 Python 复现
2. X-Argus / X-Ladon / X-Gorgon 等其它头不在本文范围内
3. VM 解释器本身没有完整转成 C
4. 三个 rand、pid、时间、f24 seed 仍属于运行时输入
5. 要跨运行输出完全一致，必须固定或捕获这些动态值
```

如果后续继续做，可以有两个方向：

```
1. 把 VM interpreter 的所有 handler 系统性转成 C/Python
2. 继续还原其它 header 的完整算法链
```

对 `X-Medusa` 来说，目前更直接有效的方式是：不追求完整解释器，而是 lift 实际执行路径和关键 native helper。

## 结语

这次 `X-Medusa` 的逆向过程，从最初只知道 VM 入口 `0x445b8`，到最终得到纯 Python 复现，大致经历了：

```
定位 header 插入点
确定 VM 执行边界
分析 packet 外层结构
倒推 second_buffer
还原 reverse-xor
还原 d71bc byte-state-machine
确认 SM3 key material
解析 src_a protobuf
还原 f23/f24 动态字段
还原 bit-slice patch
还原 AES-like transform
组合端到端 pipeline
native 对照验证
```

最终结果：

```
src_a_match=True
x_medusa_match=True
```

这也是本文最核心的判断标准：不是“猜到了算法像什么”，而是“同一次 native 输入下，Python 输出完全一致”。

上传的附件：
- libmetasec_ml.fully_deobf.so

（2.32MB，170次下载）
- dy_sign_send.py

（24.44kb，189次下载）
- medusa_lift_blocks.py

（63.96kb，179次下载）
- medusa_pure_x_medusa.py

（4.64kb，186次下载）
- medusa_reverse_walkthrough.md

（20.00kb，169次下载）
- medusa_re_notes.md

（35.12kb，178次下载）
- 中间生成文件.zip

（133.92kb，174次下载）

---

# 回复

## 回复 by Umiade (#2)

*2026-5-5 16:23*

给大哥点赞！

------------

过去，逆向所谓的工作量，一方面在于定位算法，需要尽可能准确地找到最小单元的指令流和控制流，另一个方面在于从上一步获取的数据中依靠经验还原出算法。

而现在借助给大模型搭好完善的脚手架，后一步的工作量可以大幅度降低，但这个过程中，专家经验的输入仍然必不可少。

未来在更多领域，会有越来越多的“一人成军”，领域专家的知识我觉得不但不会被淘汰，反而会愈发重要。

## 回复 by 爱吃菠菜 (#3)

*2026-5-5 16:28*

![image](https://bbs.kanxue.com/view/img/face/089.gif)

## 回复 by LowRebSwrd (#4)

*2026-5-5 16:36*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 墨穹呢 (#5)

*2026-5-6 00:19*

感谢分享

## 回复 by mb_rrvlrvbk (#6)

*2026-5-7 10:40*

![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by Imxz (#7)

*2026-5-8 11:08*

tql

## 回复 by Light紫星 (#8)

*2026-5-8 11:41*

大佬太强了

## 回复 by 3倍アイスクリーム! (#9)

*2026-5-8 11:43*

太强了这个得好好学习下

## 回复 by uni7corn (#10)

*2026-5-8 11:53*

感谢大佬的深度分析；学习了

## 回复 by Migc (#11)

*2026-5-8 11:55*

太强了

## 回复 by 龙幽 (#12)

*2026-5-8 13:54*

版本太老了，一个简单的mips 虚拟机，试下最新的版本

## 回复 by yezheyu (#13)

*2026-5-8 14:02*

666

## 回复 by mb_muaytokh (#14)

*2026-5-9 15:31*

>
> [龙幽](https://bbs.kanxue.com/user-570137.htm)
>  版本太老了，一个简单的mips 虚拟机，试下最新的版本
>

新版本那个太绕了，我用ai跟了下，烧了8亿token，根本搞不出来

## 回复 by maxcl (#15)

*2026-5-10 14:31*

也 尝试 分析过 不错

## 回复 by runjin (#16)

*2026-5-11 14:31*

请问get和post请求有没有什么区别? 它只用到url吗?

## 回复 by PPTV (#17)

*2026-5-12 19:41*

必须要好好跟着来一遍

## 回复 by mb_nzmpaifg (#18)

*2026-5-12 20:46*

学习学习

## 回复 by 手把手教我吗 (#19)

*2026-5-20 22:01*

有联系方式没，大佬发一个交流一下

## 回复 by 手把手教我吗 (#20)

*2026-5-25 05:58*

很好奇，sign_key_b64固定值是从哪拿到的

## 回复 by scxc (#21)

*2026-5-25 12:43*

medusa_re_notes.md 里面有写 从vm里取的

## 回复 by 龙哥在不在 (#22)

*2026-5-30 08:40*

>
> [手把手教我吗](https://bbs.kanxue.com/user-888537.htm)
>  很好奇，sign_key_b64固定值是从哪拿到的
>

每个app固定的，运行时会进行rc4等一系列解密获得一个protobuf,就有signkey和commonkey。没有初始化的话sdk默认内置一个3019的appid在里面

## 回复 by git_24708cy3ber (#23)

*2026-6-2 04:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  龙哥在不在](https://bbs.kanxue.com/user-1011535.htm)
>  每个app固定的，运行时会进行rc4等一系列解密获得一个protobuf,就有signkey和commonkey。没有初始化的话sdk默认内置一个3019的appid在里面
>

大佬 有联系方式嘛

## 回复 by 盖伦爸爸 (#24)

*2026-6-22 13:55*

top.f13的算法也很复杂，我用AI跟了好长时间没有搞出来
