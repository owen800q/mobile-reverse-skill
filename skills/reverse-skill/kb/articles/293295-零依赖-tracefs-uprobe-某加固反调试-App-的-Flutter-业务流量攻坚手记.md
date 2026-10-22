---
title: '[原创]零依赖 tracefs uprobe：某加固反调试 App 的 Flutter 业务流量攻坚手记'
url: https://bbs.kanxue.com/thread-293295.htm
tid: 293295
author: 择势
date: ''
tags: [Android安全, 原创]
crawled_at: '2026-10-22T09:18:08+00:00'
replies: 0
---

## 0. 声明

本文所有分析均在作者**自有的测试设备**上进行，目标为学习研究与防护技术探讨。文中涉及的应用、接口、数据均已脱敏，不提供任何针对特定平台的攻击方法、密钥或数据。请读者在授权范围内合规使用相关技术。

## 1. 背景：一块"代理全灭"的硬骨头

目标是某 C2C 交易平台 App（Android，易盾级加固）。需求很简单：摸清行情类接口的协议。上手之后发现常规武器全部失效：

- **代理抓包**（mitmproxy / Charles / HttpCanary）：核心业务请求一个都看不见，或握手即断；
- **Frida hook**：attach 上去几秒后目标进程被 SIGKILL，典型的主动反调试；
- **静态补丁**：给 libflutter.so / 相关 SSL 库打补丁绕过证书校验，App 完整性校验咬回来，真实校验点藏得比预想深，弃疗；
- **r0capture 类现成方案**：它们 hook 的是系统 conscrypt 的 SSL 库——而目标的核心流量根本不走系统库。

第一阶段的结论（后来被实测修正过一次，过程略）：App 里存在**两条完全独立的网络通道**——

| 通道 | 业务 | 网络栈 | 协议 |
|-|-|-|-|
| A | 首页/登录/广告 | OkHttp → 系统 conscrypt | HTTP/2 |
| B | 搜索/详情/行情（核心） | Dart `HttpClient` → libflutter.so 内嵌**静态 BoringSSL** | HTTP/1.1 |

代理全灭的根因就是通道 B：**Dart 运行时使用自己内置的 CA 列表，不读系统证书库，也不理系统代理设置**。中间人攻击的两个前提（流量经过你、信任你的证书）同时不成立。

顺带排掉的两个嫌疑：抓包初期怀疑过 QUIC 和字节的 TTNet（App 里确实带了相关 so），实测发现核心业务进程中这些库压根没加载——**不要对着 strings 猜通道，要看进程实际加载了什么**。

## 2. 为什么内核探针是唯一活路

盘点一下手里剩下的牌：

- 代理系：两票否决，出局；
- Frida 系：进程级反调试，脚本没挂上进程先死，出局；
- 改库重打包：壳的完整性校验等着你，出局；
- eCapture/eBPF 类：方向对，但需要往设备塞一堆工具链，且对无符号的静态 BoringSSL 一样要解决偏移问题。

最后赢的是一个"系统原生自带、零依赖"的方案：**tracefs uprobe**。

uprobe 是 Linux 内核官方功能（2012 年进主线），本来是给线上服务做无侵入性能分析的（perf/ftrace/eBPF 都建立在它之上）。原理一句话：**让内核在目标进程执行到某条指令时接管一瞬，把寄存器/内存抄一份给你**。它免疫反调试的原因：

1. **不改目标进程一个字节**——探针的指令替换是内核在页表层做的，对进程透明；
2. **不注入任何代码、不开任何端口**——frida 的那些特征（内存映射、命名管道、线程）一个都不存在；
3. **App 想检测它，得先自己能读 `/sys/kernel/tracing/`**——可 App 没有 root，单向降维。

对"见 frida 即自杀"的目标，这是射击死角。

## 3. 在无符号 libflutter.so 里定位 SSL_write / SSL_read

uprobe 要挂在函数地址上，但 libflutter.so 是 stripped 的，静态 BoringSSL 没有任何符号。这里沉淀了一套可复用的两步定位法（换版本可半自动重做）：

### 第一步：从 Dart VM 的 native 注册表摸到 BoringSSL

Dart VM 会把 `SecureSocket_Handshake` 这类 native 方法名注册进一张表。思路：

1. 在 rodata 里找到注册表字符串（如 `SecureSocket_Handshake`）；
2. 顺 `.rela.dyn` 找到指向这些字符串的指针表，定位 VM 层的 native 实现函数；
3. 沿 VM 函数的 BL 调用链往下走，就进入静态链接的 BoringSSL 区域，圈定 `SSL_write`/`SSL_read`/`SSL_do_handshake` 的候选。

### 第二步：用 BoringSSL 行号立即数确认身份

BoringSSL 的 `OPENSSL_PUT_ERROR(ssl_lib.cc:行号)` 会把**源码行号编译成立即数**。而 Dart SDK 的 DEPS 文件把 BoringSSL 钉死在某个 commit——也就是说，**哪个函数里出现哪个行号立即数，是唯一确定的**。拿候选函数里的行号立即数（例如 w3=937/958/963 等）和对应版本 `ssl_lib.cc` 逐行比对，全部吻合即确认：

```python
SSL_read         0x73d7bc
SSL_write        0x73dfc4
SSL_do_handshake 0x73d3c4
SSL_get_error    0x73e0ac
\```

（以上偏移仅对文中所述版本有效，目标升级即作废；这里 `.text` 段 file offset == vaddr，省去了换算。）

参数约定：x0=ssl，x1=buf，w2=num。**SSL_write 的 x1 入口即明文**（加密前的 HTTP 请求）。SSL_read 麻烦一点：明文不在入口，要在函数尾部——它把解密好的应用数据 `memcpy(out, pending, ret)` 拷给调用方，那处 `bl memcpy`（本例 0x73de98）的 **x1=src 就是明文，x24=len**。

## 4. 挂探针：几行 echo，以及一地的坑

不需要装任何软件，直接写 tracefs：

```bash
T=/sys/kernel/tracing
P=/data/app/~~xxxx==/com.example.target-yyyy==/lib/arm64/libflutter.so

# 写方向：入口取 buf，分 8 段，每段 64 字节，共 512B
echo "p:xjb_sslw $P:0x73dfc4 n=%x2 b0=+0(%x1):x8[64] b1=+64(%x1):x8[64] ...(共8段)" >> $T/uprobe_events
# 读方向：在函数尾部 memcpy 调用处取 src 和 len
echo "p:xjb_sslr $P:0x73de98 len=%x24 b0=+0(%x1):x8[64] ...(共8段)" >> $T/uprobe_events

echo 1 > $T/events/uprobes/xjb_sslw/enable
echo 1 > $T/events/uprobes/xjb_sslr/enable
echo 1 > $T/tracing_on
cat $T/trace_pipe   # 明文哗啦啦
\```

**踩坑清单（全是拿时间换的，文档里不会告诉你）：**

1. **`uprobe_events` 用 `>` 打开会清空全部已定义事件**——追加必须用 `>>`。第一次用时把定义好的探针清了个精光，还以为是地址错了。
2. **单段 fetch 上限 `x8[64]`（64 字节）**，想要 512 字节就写 8 段。
3. **fetch 别贪大**：试过 16 段抓 1KB，结果 buf 跨页时内核取数缺页，**整条事件被静默丢弃**——表现为"探针哑火"，无任何报错。8 段 512B 是稳定点。代价是大响应抓不全（"只剩半个"），需要应用层重组或接受截断。
4. **fetchargs 里寄存器用 `%x0..%x30`**，不支持 `$argN` 写法。
5. 探针定义写进 `uprobe_events` 后是**持久**的（重启 tracing 子系统前都在），用完 `echo 0 > .../enable` 停用即可，随时两行 echo 复活。

## 5. 从字节流到协议：重组与解码

内核给的是原始字节，还要自己做"翻译"：

- **按 (DartWorker 线程, 时间序) 重组**请求/响应；
- 通道 B 的服务端是 Envoy，响应是 `Transfer-Encoding: chunked` 的明文 JSON（不 gzip），去 chunk 头即是完整 JSON；
- 通道 A（首页/广告）是 HTTP/2，如果也要分析，得自己实现 **HPACK 解码**（作者另写了两个 Python 脚本分别处理读写方向）；
- **自动化操作**：uiautomator 对 Flutter 页面只能 dump 出 5 个节点（Flutter 自绘 UI 没有原生控件树），只能走 screencap 截图 + `input tap` 按坐标点的笨办法——笨，但稳。

至此，行情类接口的协议格式全部摸清（接口路径此处化名）：价格曲线 `POST /v1/common/get-xxx-line`、成交均价 `get-xxx-summary-by-time`、成交列表 `get-xxx-history-list`，请求体携带商品 ID，响应为明文的字段数组。示例（数据为编造）：

```json
{"code":"0","data":{"prices":[{"bucketStr":"2026-09-24","price":100,"tradingVolume":2}]}}
\```

## 6. 番外：那个唬人的 `{"cypher":2}` 根本不是目标平台自研的

分析过程中抓到一类加密载荷：`{"cypher":2,"message":"2..."}`。直觉是"平台还有一套应用层加密"，结果逆完发现是**内嵌广告聚合 SDK（穿山甲 GroMore 系）的标准协议**，只是平台把 SDK 的上报地址指到了自家网关，所以混在业务域名里。

机制（cypher 字段是协议版本号）：

```python
message = "2" + K + Base64( AES-128/ECB/PKCS5(明文JSON, key) )
K       = 16 字符随机小写 hex
key     = K[8:16] + K[0:8] 的 ASCII 字节
\```

**每条消息自带密钥**——把 message 第 2~17 字符（K）的后半截接到前半截前面，就是 AES key。解密核心 10 行 Python：

```python
k   = msg[1:17]
key = (k + k)[8:24].encode()
pt  = AES.new(key, AES.MODE_ECB).decrypt(base64.b64decode(msg[17:]))
pt  = pt[:-pt[-1]]  # 去 PKCS5 padding
\```

40 条现网样本 100% 解出（解出来全是广告 SDK 的设备指纹上报，与业务数据无关）。老版本 cypher=1 用固定 key（属于该公开 SDK，此处打码为 `b045********49b8`）。

**教训：看到加密先定性再动手。** 一度以为要硬刚平台自研密码学，甚至把嫌疑锁到了一个 `lib***Cipher.so` 上（逆完发现它只吐一个 7 字节常量，与 cypher 无关，纯烟雾弹）。真正的业务数据通道，自始至终是明文。

## 7. 方法论沉淀（比单个 case 值钱的部分）

1. **新 App 第一条军规：先找历史版本，从最软的捏起。** 目标的演进是教科书：老版本（原生 Java）装 CA 即抓、签名私钥在 jadx 里白给；新版本（Flutter + 双层私信任）正面刚不动。**但服务端向后兼容**——老版签名对新版服务端照样 200。客户端装甲升级 ≠ 服务端验签升级。老版本研究产出的是不可再生资本。
2. **正面强攻和侧翼验证随时切换。** 抓不到包不等于拿不到数据：协议摸清了、签名配方有了，自己写客户端直连也是一种"抓包"。
3. **对着 strings 猜通道会死，看进程实际加载了什么。** QUIC/TTNet 两个嫌疑都是这么浪费掉时间的。
4. **防检测的天花板在内核态。** 应用层修再多墙，也挡不住房东开天窗。uprobe 这套东西不新鲜（运维圈天天用），新鲜的是它对移动端反调试是降维打击——而且零依赖，手机上不留任何软件痕迹。
5. **踩坑清单是最值得记笔记的部分。** 偏移换版本可以重找，`>` 清空事件、512B 哑火这种坑，踩过一次记一辈子。

## 8. 工具链清单

| 用途 | 工具 |
|-|-|
| 探针 | 内核原生 tracefs uprobe（零安装） |
| 偏移定位 | llvm-objdump / IDA + BoringSSL 对应版本源码比对 |
| 协议解析 | 自研 Python 脚本（uprobe 明文重组、HPACK 解码、chunked 重组） |
| 设备自动化 | screencap + input tap（Flutter 页面的无奈之选） |
| Root 环境 | APatch |

## 9. 结语

这块骨头的硬，不在任何单一技术点，而在"加固 + 反调试 + 自带网络栈 + 私信任"四层装甲的叠加。但四层装甲有一个共同的射击死角：它们防的都是"进我家里动手"的人，防不了根本不进家门的人。tracefs uprobe 这类内核原生能力，值得每个做移动端安全研究的同行放进工具箱——它不占地方，不需要装，而且对手大概率看不见它。

（全文完。文中涉及的目标应用、接口、数据均已脱敏；具体偏移仅对所述旧版本有效。）
