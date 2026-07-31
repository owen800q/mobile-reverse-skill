---
title: '[原创] 从 r0capture 到 eCapture：Hermes Agent 自动抓包在真实任务里的价值'
url: https://bbs.kanxue.com/thread-291916.htm
tid: 291916
author: xxxmm
date: '2026-07-08'
tags: [Android安全, 原创, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-07-31T13:50:16+08:00'
replies: 7
---

>
> 本文记录一次使用 Hermes Agent 辅助完成某APP抓包、踩坑、复盘与业务接口分析的过程。重点不是单独介绍某一个抓包工具，而是复盘一条真实移动端 HTTPS 流量分析链路：先尝试 r0capture/Frida，发现对当前目标效果不好；再用 tcpdump 兜底确认网络侧事实；最后切换到 eCapture，通过 Android BoringSSL 明文 TLS hook 拿到更有价值的接口内容。
>
>
> 本文保留接口路径用于技术复盘，但所有 Cookie、token、uid、设备标识、账号凭据、手机号、验证码、发帖 token 等敏感字段均做脱敏处理，统一以 `[REDACTED]` 或概括形式呈现。
>
>
>

## 目录

- 1. 为什么用AI自动抓包
- 2. 业务场景：酷安 APP 抓包到底要看什么
- 3. 工具选型：r0capture、tcpdump 与 eCapture 的分工
- 4. Hermes Agent 后台评审机制：为什么它适合长链路任务
- 5. 实验环境与任务目标
- 6. 第一阶段：r0capture抓包，结果不理想
- 7. 第二阶段：tcpdump 兜底，只能回答网络侧问题
- 8. 第三阶段：eCapture 初次踩坑，KernelSU root 不等于 CAP_BPF
- 9. 第四阶段：eCapture text 模式拿到酷安核心 API
- 10. pcapng 与 text log：两类产物分别能说明什么
- 11. 关键接口与业务语义分析
- 12. 登录、验证码与敏感字段观察
- 13. 第三方 SDK 与非核心业务流量
- 14. AI Agent 在这类任务里的实际价值
- 15. 复盘：抓包的目标不是看到包，而是理解包
- 16. 参考资料

## 1. 为什么用AI自动抓包

传统移动端抓包并不缺工具。Charles、Burp Suite、mitmproxy、Wireshark、tcpdump、Frida、r0capture、eCapture 都可以在不同层面解决问题。但真正做一次 App 流量分析时，最耗时间的往往不是“装一个工具”，而是下面这些连续判断：

- 目标 App 是否走系统代理；
- HTTPS 是否有证书锁定或自定义网络栈；
- Java 层 Hook 是否能覆盖真实请求；
- native 层 TLS 明文能否被捕获；
- pcap 文件里哪些是核心业务，哪些只是广告、埋点或图片资源；
- 抓到的接口内容能否和用户操作对应起来；
- 最终材料能否被整理成可复盘、可复测、可脱敏的报告。

这些步骤单看都不难，但组合起来很容易变成“经验工程”。测试人员需要在命令行、手机、代理工具、PCAP 文件和业务文档之间反复切换。尤其是分析 PCAP 时，问题并不是 Wireshark 不强，而是 Wireshark 只告诉你包长什么样，不直接告诉你这些包在业务里意味着什么。

这正是 AI Agent 可以切入的地方。

本文的核心观点是：**AI 自动抓包的价值不只是帮人敲命令，而是把抓包过程从工具操作升级为可追踪、可复盘、可迁移的业务分析链路。**

这次目标是酷安 App，包名为：

```
com.coolapk.market
```

测试动作包括：

1. 登录入口与登录后同步；
2. 主页信息流加载；
3. 发帖提交。

从结果看，这次任务最有价值的地方不在于“某个工具一次成功”，而在于工具链路经历了多次切换：

```
r0capture/Frida 尝试
  -> 输出为空或进程终止
  -> tcpdump 兜底确认域名/SNI/连接
  -> eCapture 初次遇到 CAP_BPF 权限问题
  -> KernelSU debug su -g 方式运行 eCapture
  -> text 模式拿到酷安 /v6/... 明文接口
  -> pcapng 辅助验证网络侧事实
  -> 生成脱敏分析报告
```

这条链路比单独展示一条命令更接近真实安全测试现场。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_4T4AVVD395HYS9R.png)

 AI抓包路线图

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_CH7G5995XUSP86E.png)

 酷安 App 首页

## 2. 业务场景：酷安 APP 抓包到底要看什么

本次任务目标可以拆成三层：

| 层次 | 目标 | 期望结果 |
|-|-|-|
| 工具层 | 下载并部署 r0capture、tcpdump、eCapture，验证设备上能运行 | 抓包工具顺利运行 |
| 抓包层 | 抓取酷安登录、主页、发帖相关流量 | 产出 text log 与 pcapng |
| 分析层 | 分析请求路径、Header、Body、第三方 SDK、敏感字段 | 形成分析报告 |

为了避免文章停留在“工具能跑”的层面，本次实验选择了一个最容易理解、也最适合作为入门案例的业务对象：酷安APP。

酷安APP 看起来简单，但它具备典型移动应用的网络行为：

- 启动时拉取首页推荐、账号状态、配置下发、通知未读数等基础数据；
- 进入首页或下拉刷新时请求信息流列表、热门内容、频道页数据和广告资源；
- 进入帖子详情页时请求帖子正文、评论列表、点赞/收藏/转发状态等数据；
- 登录、发帖、评论、点赞等操作可能携带 Cookie、X-App-Token、X-App-Device、uid、feed_id、提交 token 等鉴权或行为字段；
- APP 内还会混入广告 SDK、风控 SDK、HTTPDNS、日志埋点、图片 CDN 等非核心业务流量。

从业务分析角度看，我们真正关心的不是“抓到了多少包”，而是：

- 哪些请求对应酷安核心业务，例如首页信息流、帖子详情、评论列表、通知列表、发帖接口；
- 哪些请求只是广告、风控、HTTPDNS、日志上报或图片资源；
- Cookie、X-App-Token、X-App-Device、uid、feed_id、_v2_post_token 等敏感字段是否出现在请求中；
- 请求参数和响应字段如何映射到 APP 页面展示，例如首页卡片、帖子内容、评论区、通知列表和个人动态；
- 发帖、评论、点赞等写接口是否存在重放、参数篡改、越权调用或 token 泄露风险；
- 这些结论能否被整理成可脱敏、可复测、可沉淀的接口分析报告，而不是停留在几张抓包截图里。

这就是酷安这类社区型 APP 的流量分析痛点：数据包只是网络层事实，真正有价值的是把接口路径、Header、Body、用户操作和页面展示对应起来。
而大模型擅长的正是把半结构化请求、响应字段、上下文线索和人工测试目标组织成可读结论。因此，本实验把“分析抓包结果”放在和“成功抓到包”同等重要的位置。

## 3. 工具选型：Hermes Agent、r0capture、tcpdump 与 eCapture 的分工

本文涉及四个核心组件，但它们的角色不同。

### 3.1 Hermes Agent：自动化调度层

`Hermes Agent` 在本文中不是被分析的唯一主角，而是自动化执行引擎。它负责：

- 理解自然语言任务；
- 拆解抓包步骤；
- 调用命令行工具；
- 根据错误输出调整执行路径；
- 记录中间结论；
- 在后续任务中复用已经沉淀的 Skill 和 Memory。

换句话说，Hermes Agent 的位置更像一个懂安全测试流程的执行助理。它不替代 r0capture，也不替代 Wireshark，而是把这些工具组织成流程。

### 3.2 r0capture：Frida Hook 路线

`r0capture` 是一款基于 Frida 的 Android 抓包工具，由r0ysue大佬在GitHub上开源，适合处理普通代理难以覆盖的加密流量场景。它通过 Hook Java 层、网络库和 SSL/TLS 相关接口，在数据进入加密层前或解密后捕获明文内容，直接通杀TCP/IP四层模型中的应用层中的全部协议,能够有效地捕获和分析移动应用的网络请求。

**r0capture的核心功能包括：**

1. 通杀应用层全部协议的抓包: 充分利用Frida动态插桩技术，直接通杀TCP/IP四层模型中的应用层中的全部协议，在移动设备上捕获应用的明文请求和响应，包括Http、WebSocket、Ftp、Xmpp、Imap、Smtp、Protobuf等等、以及它们的SSL版本的请求和响应数据。通杀了所有应用层框架，包括HttpUrlConnection、Okhttp1/3/4、Retrofit/Volley等等。
具体Hook的接口包括但不限于

- `com.android.org.conscrypt.OpenSSLSocketImpl$SSLOutputStream.write`
- `com.android.org.conscrypt.OpenSSLSocketImpl$SSLOutputStream.read`
- `com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLOutputStream.write`
- `com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLInputStream.read`

1. dump客户端证书: 在Frida的Spawn模式下，可以在服务器校验客户端的情形下，通过hook java.security.KeyStore接口帮助dump客户端证书，并保存到本地，方便用户将证书导入到Charles等抓包工具中进行抓包。具体的接口包括但不限于java.security.KeyStore的PrivateKeyEntry内部类的getPrivateKey和getCertificateChain等接口；
2. 抓包结果可以以pcap文件的形式保存，用户可以使用Wireshark等工具进行分析；

**r0capture的使用流程如下：**

1. 在移动设备上安装frida-server，并确保设备与电脑连接正常；
2. 使用r0capture的命令行工具，指定要抓取的应用包名和输出的pcap文件名；
3. r0capture捕获指定应用的网络请求和响应，并将其保存为pcap文件；
4. 使用Wireshark等工具分析生成的pcap文件，提取出其中的HTTP请求和响应，并分析其内容；
5. 通过r0capture提供的接口，dump客户端证书，帮助用户在服务器校验客户端的情形下进行抓包。

**r0capture的核心代码实现如下：**

```javascript
//在服务器校验客户端的情形下，帮助dump客户端证书，并保存为p12的格式，证书密码为r0ysue
    Java.use("java.security.KeyStore$PrivateKeyEntry").getPrivateKey.implementation = function () {
      var result = this.getPrivateKey()
      var packageName = Java.use("android.app.ActivityThread").currentApplication().getApplicationContext().getPackageName();
      storeP12(this.getPrivateKey(), this.getCertificate(), '/sdcard/Download/' + packageName + uuid(10, 16) + '.p12', 'r0ysue');
      var message = {};
      message["function"] = "dumpClinetCertificate=>" + '/sdcard/Download/' + packageName + uuid(10, 16) + '.p12' + '   pwd: r0ysue';
      message["stack"] = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Throwable").$new());
      var data = Memory.alloc(1);
      send(message, Memory.readByteArray(data, 1))
      return result;
    }
    Java.use("java.security.KeyStore$PrivateKeyEntry").getCertificateChain.implementation = function () {
      var result = this.getCertificateChain()
      var packageName = Java.use("android.app.ActivityThread").currentApplication().getApplicationContext().getPackageName();
      storeP12(this.getPrivateKey(), this.getCertificate(), '/sdcard/Download/' + packageName + uuid(10, 16) + '.p12', 'r0ysue');
      var message = {};
      message["function"] = "dumpClinetCertificate=>" + '/sdcard/Download/' + packageName + uuid(10, 16) + '.p12' + '   pwd: r0ysue';
      message["stack"] = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Throwable").$new());
      var data = Memory.alloc(1);
      send(message, Memory.readByteArray(data, 1))
      return result;
    }

    // 直接在Socket层hook住输入输出流的read和write接口，获取明文的请求和响应数据
     if (parseFloat(Java.androidVersion)  > 8) {
      Java.use("com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLOutputStream").write.overload('[B', 'int', 'int').implementation = function (bytearry, int1, int2) {
        var result = this.write(bytearry, int1, int2);
        SSLstackwrite = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Throwable").$new()).toString();
        return result;
      }
      Java.use("com.android.org.conscrypt.ConscryptFileDescriptorSocket$SSLInputStream").read.overload('[B', 'int', 'int').implementation = function (bytearry, int1, int2) {
        var result = this.read(bytearry, int1, int2);
        SSLstackread = Java.use("android.util.Log").getStackTraceString(Java.use("java.lang.Throwable").$new()).toString();
        return result;
      }
    }

```

这类方案的优势是直接贴近 APP 运行时，不依赖系统代理是否生效。对于有证书校验、代理检测或复杂网络框架的 APP，它比传统中间人代理更容易拿到明文。

但 Frida 路线也有天然限制：

- 需要 frida-server 版本、设备架构、Python frida 库匹配；
- App 如果使用 Cronet、QUIC、自定义 native 网络栈，Java 层 Hook 可能覆盖不到；
- 目标进程可能在 spawn/attach 后崩溃或主动退出；
- Hook 类加载时机不对时，可能出现类找不到、没有输出、pcap 空文件等情况。

这次酷安目标上，r0capture/Frida 就遇到了这些问题。

### 3.3 tcpdump：网络侧事实兜底

`tcpdump` 是 Linux/Unix 平台最常用的网络抓包工具，其核心原理是通过操作系统提供的数据链路层抓包机制，对经过网络接口的数据包进行实时捕获、过滤和解析。tcpdump 本身并不直接操作网卡硬件，而是依赖底层抓包库 libpcap（Windows 平台对应 WinPcap/Npcap）完成数据包的获取，因此其工作流程可以概括为“网卡接收数据 → 内核捕获 → BPF过滤 → libpcap读取 → tcpdump解析显示”。

首先，当数据包经过网卡时，无论是接收（RX）还是发送（TX），都会进入 Linux 内核网络协议栈。在正常情况下，数据包会依次经过数据链路层、网络层、传输层，最终交给相应的应用程序。而当 tcpdump 启动后，libpcap 会向内核注册一个 PF_PACKET（Packet Socket） 或早期 BSD 系统中的 BPF（Berkeley Packet Filter）设备，使内核能够在协议栈处理数据之前，将经过指定网卡的数据复制一份交给抓包程序。由于抓包只是复制数据，不会影响原始数据包的正常传输，因此 tcpdump 本身属于一种被动监听工具。

为了提高抓包效率，tcpdump 并不会把所有数据包都复制到用户态，而是利用 Berkeley Packet Filter（BPF） 机制完成内核级过滤。用户输入的过滤条件（如 tcp port 80、host 192.168.1.1 等）首先会被编译成 BPF 字节码，再加载到内核中执行。只有满足过滤规则的数据包才会被复制到用户空间，其余数据包直接在内核中丢弃。这种设计避免了大量无关数据在内核态和用户态之间频繁拷贝，大大降低了 CPU 和内存开销，也是 tcpdump 能够在高速网络环境下保持较高性能的重要原因。

过滤后的数据包由 libpcap 从内核缓冲区读取到用户空间。libpcap 为 tcpdump 提供了统一的接口，负责网卡打开、缓冲区管理、数据包读取以及超时处理等底层工作。tcpdump 获取到原始数据包后，会按照网络协议格式逐层解析。例如，首先解析 以太网帧头（Ethernet Header），获取源 MAC 地址、目的 MAC 地址以及上层协议类型；随后解析 IP 头，得到源 IP、目的 IP、TTL、协议号等信息；如果是 TCP 或 UDP 数据包，则继续解析传输层头部，获取端口号、序列号、确认号等内容，并最终以文本形式输出给用户。

此外，tcpdump 支持将捕获的数据保存为 pcap 格式文件。pcap 文件保存的是完整的二进制数据包，可被 Wireshark、tshark 等分析工具再次打开进行深入分析。因此，在实际安全测试、网络故障排查以及协议分析过程中，通常采用 tcpdump 负责服务器端抓包，Wireshark 负责离线分析 的方式，提高分析效率。

需要注意的是，由于 tcpdump 工作在网络接口层，因此它能够捕获的数据是明文协议头和原始网络数据。对于 HTTPS、TLS 等加密通信，tcpdump 只能看到加密后的密文负载，而无法直接获取应用层明文内容。如果需要分析 HTTPS 的明文数据，则需要结合 TLS 密钥日志（SSLKEYLOGFILE）、MITM 代理或 eCapture 等基于 eBPF、uprobes 的工具对加密过程进行旁路解密。

tcpdump不是明文 HTTPS 抓包工具。它的价值是记录网络层事实：

- 目标 IP、端口、连接数量；
- TLS SNI；
- DNS/HTTPDNS；
- 明文 HTTP 图片资源或 SDK 上报；
- 流量大小、方向、时序。

但它不能直接告诉我们 HTTPS 里的 path、Header、Body。也就是说，tcpdump 可以回答“连到了哪里、什么时候连、流量有多大”，但不能直接回答“提交了什么接口参数”。

### 3.4 eCapture：eBPF / TLS 明文捕获路线

eCapture（Extensible Capture）是一款基于 eBPF（extended Berkeley Packet Filter） 技术实现的开源网络数据捕获工具。与传统抓包工具（如 Wireshark、tcpdump）依赖网卡数据包不同，eCapture 采用了一种全新的思路：不去分析已经加密后的网络数据，而是在应用程序完成 TLS 加密之前或解密之后直接获取明文数据。因此，它无需安装 CA 证书、无需配置代理，也无需对目标应用进行重打包，即可实现 HTTPS/TLS 明文流量的捕获，特别适用于服务器环境、Android Root 环境以及各类网络安全分析场景。

从源码结构来看，eCapture 整体采用 Go + eBPF 的架构实现，源码主要包括 CLI（命令行）、Manager（管理模块）、Probe（探针模块）、eBPF Program（内核程序）以及 Event Processor（事件处理模块） 五部分。CLI 层负责解析用户输入的参数，例如 ecapture tls、ecapture bash 等命令；Manager 模块根据用户配置初始化对应的 Probe；Probe 模块负责加载不同类型的 eBPF 程序，并将其挂载到指定的用户态或内核态函数；eBPF Program 则运行于 Linux 内核中，负责真正的数据捕获；最后由 Event Processor 将内核采集到的数据解析并格式化输出为文本、PCAPNG 或 SSL Key Log 等形式。

eCapture 最核心的技术是 Uprobe（User Probe）。Uprobe 是 Linux eBPF 提供的用户态动态探针机制，可以在用户空间 ELF 程序的指定函数入口或出口插入 Hook，而无需修改程序代码。eCapture 正是利用这一机制，对 OpenSSL、BoringSSL、GnuTLS、NSS、GoTLS 等主流 TLS 加密库中的关键函数进行动态挂载。例如，在 OpenSSL 中，Probe 模块会定位 SSL_write() 和 SSL_read() 等函数，通过 link.OpenExecutable().Uprobe() 将 eBPF 程序附加到这些函数上。当应用调用 SSL_write() 发送数据时，此时 HTTP 请求仍然是明文，尚未经过 TLS 加密；而在 SSL_read() 返回时，接收到的 TLS 数据已经完成了解密。因此，eBPF 程序只需读取这两个函数参数中的缓冲区地址，即可直接获得完整的 HTTP 请求和响应内容，而完全绕过传统 HTTPS 中间人代理（MITM）方式。

从源码流程来看，整个 TLS 抓包过程如下所示：

```python
用户执行 ecapture tls
          │
          ▼
    Cobra CLI 解析参数
          │
          ▼
    Manager 初始化 Probe
          │
          ▼
加载 OpenSSL/BoringSSL Probe
          │
          ▼
Attach Uprobe 到 SSL_write/SSL_read
          │
          ▼
目标程序调用 SSL_write()
          │
          ▼
eBPF 读取 buf 参数中的明文数据
          │
          ▼
Perf Event / RingBuffer
          │
          ▼
Go Event Processor
          │
          ▼
HTTP 重组并输出文本或 PCAP
```

在 eBPF 程序内部，真正的数据读取主要依赖 bpf_probe_read_user() 等辅助函数。例如，在 SSL_write() 的 Uprobe 中，第二个参数通常为用户缓冲区 char *buf，第三个参数表示数据长度。eBPF 程序读取该缓冲区后，将 HTTP 明文、PID、时间戳等信息封装为事件结构体，再通过 bpf_perf_event_output() 或新版内核提供的 Ring Buffer 接口发送到用户空间。

除了 Uprobe，eCapture 还使用了 Kprobe（Kernel Probe） 和 TC（Traffic Control） 等内核探针技术。Kprobe 主要用于 Hook Linux 内核函数，例如数据库查询函数、Shell 命令读取函数等，实现 MySQL、PostgreSQL、Bash 等应用的行为审计；TC 则通过在 Linux Traffic Control 子系统挂载 eBPF 程序，对网络流量进行过滤和统计，实现更底层的数据采集。因此，eCapture 实际形成了 "用户态 Uprobe + 内核态 Kprobe/TC" 的双探针架构，使其既能够获取 TLS 明文，又能够监控底层网络行为。

由于 eBPF 程序运行在内核中，无法直接执行文件写入、网络发送等复杂操作，因此 eCapture 利用了 BPF Map 和 Perf Event（或 Ring Buffer） 实现内核态与用户态之间的数据通信。BPF Map 是内核中的高性能键值存储结构，用于保存当前捕获的数据；Perf Event 则是一种高效的事件通知机制，当 eBPF 程序捕获到新的 TLS 明文后，会调用 perf_event_output 将事件异步推送至用户空间。Go 编写的 Event Processor 持续监听 Perf Buffer，一旦收到事件，便根据 PID、线程 ID、SSL 对象地址等信息进行连接关联和 HTTP 数据重组，最终输出完整的 HTTP 请求、响应内容或导出为 PCAPNG 文件，供 Wireshark 等工具进一步分析。

值得注意的是，eCapture 的工作原理与传统抓包工具存在本质区别。tcpdump、Wireshark 等工具工作于网络接口层，只能捕获已经完成 TLS 加密后的密文数据，因此需要依赖 CA 证书、中间人代理或 SSL Key Log 才能实现 HTTPS 解密。而 eCapture 的 Hook 点位于 TLS 库内部，在 SSL_write() 加密之前和 SSL_read() 解密之后获取数据，因此采集到的是应用程序真正处理的明文内容，并不涉及 TLS 算法破解，也不会影响正常通信过程。这种方式不仅避免了证书安装、代理配置等复杂操作，同时也降低了对目标程序的侵入性。

在 Android 平台上，系统默认采用 BoringSSL 或 Conscrypt 作为 TLS 实现，因此 eCapture 通常针对这些动态库进行 Uprobe 挂载。本次实验中，eCapture 运行于具有 Root 权限的 Android Shell 环境，通过 Hook BoringSSL 相关加解密函数，成功捕获了酷安应用的 HTTPS 明文请求，并以 Text 模式实时输出 HTTP 内容。相比基于 Frida 的 r0capture，eCapture 更接近 Native TLS 层，不依赖 Java Hook，也无需向目标进程注入 JavaScript，因此稳定性更高，对部分 Frida 检测较严格的应用也具有更好的兼容性。

## 4. Hermes Agent 后台评审机制：为什么它适合长链路任务

自动抓包不是一次命令能完成的短任务，而是一个长链路任务。它通常包含环境确认、依赖安装、设备连接、抓包执行、结果导出、数据分析和报告生成。任何一步失败，后续都需要调整。

Hermes Agent 的后台评审机制正适合这种场景。它会在任务执行过程中检查 Memory 和 Skill 是否需要审查，并在后台触发能力更新。核心逻辑来自 `run_agent.py`：

```python
_should_review_memory = False
if (self._memory_nudge_interval > 0
        and "memory" in self.valid_tool_names
        and self._memory_store):
    self._turns_since_memory += 1
    if self._turns_since_memory >= self._memory_nudge_interval:
        _should_review_memory = True
        self._turns_since_memory = 0

_should_review_skills = False
if (self._skill_nudge_interval > 0
        and self._iters_since_skill >= self._skill_nudge_interval
        and "skill_manage" in self.valid_tool_names):
    _should_review_skills = True
    self._iters_since_skill = 0

if final_response and not interrupted and (_should_review_memory or _should_review_skills):
    try:
        self._spawn_background_review(
            messages_snapshot=list(messages),
            review_memory=_should_review_memory,
            review_skills=_should_review_skills,
        )
    except Exception:
        pass
```

相关配置如下：

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: ''
  nudge_interval: 10
  flush_min_turns: 6

skills:
  external_dirs: []
  template_vars: true
  inline_shell: false
  inline_shell_timeout: 10
  guard_agent_created: false
  creation_nudge_interval: 15
```

对于自动抓包任务，这套机制的意义在于：

- 第一次任务中遇到的 Frida 版本、设备架构、依赖安装问题可以被记录；
- 抓包命令、输出路径、常用 tshark 过滤表达式可以沉淀成 Skill；
- 后续换一个 APP 时，Agent 不必重新从零摸索；
- 多轮交互后，Agent 对“用户真正想要的是业务分析，不只是抓包截图”的理解会更稳定。

这也是本文标题强调“AI 自动抓包”的原因。Hermes 的价值不是单独展示某段后台评审代码，而是让抓包流程具备长期复用能力。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_MACR2AY7NBHZ6N9.png)

 Hermes Agent 后台评审机制图示

## 5. 实验环境与任务目标

本次实验环境如下：

| 项目 | 内容 |
|-|-|
| 目标 App | 酷安 |
| 包名 | `com.coolapk.market` |
| Android 设备 | Android 14，arm64-v8a，KernelSU root |
| App 版本 | `CoolMarket 16.2.1` |
| 主要工具 | r0capture、Frida、tcpdump、eCapture、tshark/Wireshark |
| 主要成功方案 | eCapture `tls -m text` + BoringSSL hook |

给 Hermes Agent 的原始任务如下：

```
帮我将 r0capture（地址为https://github.com/r0ysue/r0capture）和eCapture 下载下来（地址为https://github.com/gojue/ecapture），抓取手机上的酷安APP的包，具体包名是 com.coolapk.market，抓取网络请求包（登录 、主页 和 发帖），分析里面的包的内容。
```

这个任务不是单纯运行 r0capture、eCapture，而是要求 Agent 完成三件事：

1. 自动搭建抓包环境；
2. 抓取目标 APP 的网络流量；
3. 分析 数据包文件中的业务内容。

其中第三点最关键。只做到第二点，只能证明工具能用；做到第三点，才说明 AI Agent 对安全测试、逆向分析测试工作流产生了实际价值。

## 6. 第一阶段：r0capture抓包，结果不理想

一开始的思路是沿用常见 Android 明文抓包流程：启动 frida-server，使用 r0capture attach/spawn 目标进程，对酷安的登录、主页、发帖阶段分别抓包。

但结果并不好。两个 r0capture 相关 pcap 文件大小都是 24 bytes：

这类文件基本只能说明 pcap 文件头存在，不能说明抓到了有效业务流量。

登录阶段日志也非常短：

```
attach
Press Ctrl+C to stop logging.
You have stoped logging.
```

这意味着 r0capture 没有输出可用于分析的明文 HTTPS 内容。

继续尝试 Frida attach 时，日志显示 attach 超时：

```
Failed to attach: unexpectedly timed out while waiting for stop from process with PID [REDACTED]
```

尝试 spawn 并 Hook HTTP/OkHttp 时，又遇到了类加载问题：

```
OkHttp hook failed: java.lang.ClassNotFoundException: Didn't find class "okio.Buffer"
java.net.URL hooked
WebView hooked
Process terminated
```

因此，这次实测表明r0capture 在当前酷安版本、当前设备和当前 Hook 点组合下效果不好。它不是完全不能用于所有酷安场景，但在这次实测中没有拿到登录、主页、发帖的核心 HTTPS API 明文。

这也提醒我们，工具启动了，不代表抓到了有分析价值的包；pcap 文件存在，也不代表里面有业务内容。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_P39Y9UJ97BCEEUQ.png)

 r0capture 失败证据

## 7. 第二阶段：tcpdump 兜底，只能回答网络侧问题

r0capture 输出不理想后，切换到 tcpdump 兜底。tcpdump 的价值是帮助确认 App 确实有网络活动，并保留登录、主页、发帖阶段的网络侧证据。

这些 pcap 可以用 Wireshark/tshark 看连接、SNI、域名、图片资源和 SDK 上报，但不能直接还原酷安核心 HTTPS 请求正文。比如：

- 可以看到 `api.coolapk.com`、`api2.coolapk.com`、`account.coolapk.com` 等域名相关连接；
- 可以看到部分明文 HTTP 资源或第三方 SDK 上报；
- 可以观察某个用户操作后是否出现上行 TLS Application Data；
- 但看不到 `/v6/feed/createFeed` 的 form body，也看不到 Cookie、X-App-Token 等 HTTPS 内部 Header。

所以 tcpdump能证明"有流量"，但不能完成"接口语义分析"。这也是后面继续切换到 eCapture 的原因。

>
> 如果想展示“tcpdump 只能看到网络侧事实”的过程，可以打开早期 tcpdump 文件并截图，例如：
>
>
> `/root/coolapk_capture_20260525_192003/2_home_tcpdump.pcap`
>
>
> 建议截图 Wireshark 的 Conversations、Endpoints 或 TLS SNI 过滤结果。注意不要展示任何可能关联个人设备或账号的明文内容。 -->
>
>
>

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_76NTUG42GCT2FFV.png)

 tcpdump 只能看到网络侧事实

## 8. 第三阶段：eCapture 初次踩坑，KernelSU root 不等于 CAP_BPF

改用 eCapture 后也不是一次成功。第一次遇到的核心问题是：设备虽然有 KernelSU root，但普通 `su` shell 并没有 eCapture 加载 eBPF 程序所需的 capability。

当时观察到 `/proc/self/status` 中 `CapEff=0`，eCapture 报错类似：

```
the current user does not have CAP_BPF to load bpf programs
```

这说明“uid=0”不等于“具备 CAP_BPF/CAP_SYS_ADMIN”。对 eBPF 类工具来说，root shell 是否拥有有效 capabilities 非常关键。

后续使用 KernelSU 的 debug root shell，并通过全局 mount namespace 方式执行脚本：

```bash
adb shell "/system/bin/su -c '/data/adb/ksud debug su -g < /data/local/tmp/script.sh'"
```

这个方式让 eCapture 能够在设备上正常加载并运行。到这里，工具链才真正进入可用状态。

这个坑对后续复用价值很高：如果只看到 eCapture 报 CAP_BPF 错误，继续换参数通常没有意义，应该先检查 root shell 的 capability 和 mount namespace。

>
> 如果你本地还保留终端历史或运行日志，可以在这里插入一张 eCapture 报 `CAP_BPF` 权限问题，或后来通过 `ksud debug su -g` 成功运行的终端截图。截图时避免展示设备序列号、真实路径中的个人信息或任何 token。 -->
>
>
>

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_5MTG4P526MU7WV4.png)

 eCapture 报 `CAP_BPF` 权限问题, 通过 `ksud debug su -g` 成功运行

## 9. 第四阶段：eCapture text 模式拿到酷安核心 API

最终有效的方案是使用 eCapture 的 `tls` 模式，并以 text/stdout 日志作为核心分析材料。pcapng 同时保留，用于 Wireshark/tshark 侧的流量统计和网络侧验证。

从 text/stdout 日志中可以看到酷安核心 API 路径，例如：

```
POST api.coolapk.com /v6/service/sync2?exp=0&t=[REDACTED]
GET  api2.coolapk.com /v6/main/indexV8?page=1&firstLaunch=0&installTime=[REDACTED]&ids=[REDACTED]
GET  api.coolapk.com /v6/page/dataList?url=[REDACTED]&title=[REDACTED]&page=1
GET  api.coolapk.com /v6/notification/list?page=1
GET  api.coolapk.com /v6/account/loadConfig?key=my_page_card_config&refresh=0
POST api.coolapk.com /v6/feed/createFeed
GET  api.coolapk.com /v6/user/feedList?uid=...&page=1&showAnonymous=0&isIncludeTop=1
```

这一步是整次任务的分水岭：从“只能看到网络连接”进入到了“可以分析业务接口”的阶段。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_537RHP4R6GNVX7G.png)

 eCapture 抓到的酷安核心 API 摘要

## 10. pcapng 与 text/stdout log：两类产物分别能说明什么

这次最终同时保留了 pcapng 和 text/stdout log。两者不是替代关系，而是互补关系。

| 对比项 | pcapng 文件 | text/stdout log |
|-|-|-|
| 代表文件 | `ecap_home_pcap.pcapng`、`ecap_login_nav.pcapng` | `ecap_home_stdout.log`、`ecap_post_text_2_stdout.log` 等 |
| 适合工具 | Wireshark、tshark | grep、脚本、文本分析、大模型归纳 |
| 主要内容 | 包级别流量、TCP/TLS、SNI、HTTP 明文资源、连接时序 | eCapture 捕获到的 TLS 明文 HTTP 请求内容 |
| 能否直接看酷安 `/v6/...` path | 本次 pcapng 中基本不能直接解析核心 `/v6/...` body/path | 可以看到多个核心 `/v6/...` 接口 |
| 能否看 Header/Body | 对 HTTPS 核心接口不理想 | 可以看到 Header、form body、部分响应片段 |
| 适合结论 | “连到了哪里、流量多大、有哪些域名和 SDK” | “具体请求了哪个接口、带了哪些参数、对应什么业务” |

pcapng 的重要结论包括：

- `ecap_home_pcap.pcapng` 约 16 MB，14255 frames，抓包约 54 秒；
- `ecap_login_nav.pcapng` 约 8.3 MB，8478 frames，抓包约 69 秒；
- 首页侧能看到 `api2.coolapk.com` SNI、HTTPDNS、图片资源和广告 SDK；
- 登录导航侧能看到 `account.coolapk.com`、`static.coolapk.com`、网易易盾、快手、百度等域名；
- pcapng 不是本次分析酷安核心 `/v6/...` API body 的主证据。

text/stdout log 的价值则更直接：它能把酷安的核心业务请求从 TLS 里还原出来，因此成为本次接口分析的主证据。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_Q5WASKYBGEES53F.png)

 eCapture text log

## 11. 关键接口与业务语义分析

### 11.1 登录入口与登录后同步

登录入口阶段没有完整抓到“提交验证码/登录表单”的瞬间，但抓到了登录入口、风控、同步和登录后请求。

代表接口：

```
POST api.coolapk.com /v6/service/sync2?exp=0&t=[REDACTED]
GET  api.coolapk.com /v6/notification/list?page=1
GET  api.coolapk.com /v6/account/loadConfig?key=my_page_card_config&refresh=0
```

`/v6/service/sync2` 的请求体中可以看到类似阅读进度/行为同步字段，例如：

```
reportProgress=[{"feed_id":"[REDACTED]","uid":"[REDACTED]","feed_type":"12","feed_uid":"[REDACTED]","read_progress":37,"article_time":14,"all_time":14,"dateline":"[REDACTED]"}]
```

这类接口的业务含义不是登录本身，而是登录态下的客户端行为同步。它说明 App 会把用户阅读进度、内容 ID、时间等行为信息发送到服务端。

登录后还会出现通知列表和账号配置请求：

```
GET /v6/notification/list?page=1
GET /v6/account/loadConfig?key=my_page_card_config&refresh=0
```

这些接口通常依赖 Cookie、X-App-Token、X-App-Device 等 Header。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_QEKYBYZQAQ35UJS.png)

 酷安 App 登录入口

### 11.2 主页信息流

主页信息流的核心接口是：

```
GET api2.coolapk.com /v6/main/indexV8?page=1&firstLaunch=0&installTime=[REDACTED]&ids=
GET api2.coolapk.com /v6/main/indexV8?page=2&firstLaunch=0&installTime=[REDACTED]&lastItem=[REDACTED]&ids=
```

从参数看，`indexV8` 至少包含以下语义：

| 参数 | 观察到的作用 |
|-|-|
| `page` | 分页页码 |
| `firstLaunch` | 是否首次启动或首次加载状态 |
| `installTime` | 安装时间或客户端侧时间标识，脱敏处理 |
| `firstItem` / `lastItem` | 信息流游标或去重边界 |
| `ids` | 已加载内容 ID 列表或去重参数 |

另一个主页/频道相关接口是：

```
GET api.coolapk.com /v6/page/dataList?url=%2Fpage%3Furl%3DV15_ZHUANTI_SHENGHUO&title=%E7%94%9F%E6%B4%BB&subTitle=&page=1
GET api.coolapk.com /v6/page/dataList?url=%23%2Ffeed%2FdigestList%3ForTagKeywords%3D%E7%94%9F%E6%B4%BB%E7%83%AD%E8%AE%AE%26orderBy%3Dlastupdate%26message_status%3Dall%26filterId%3D82&title=%E7%83%AD%E8%AE%AE&page=1
```

`/v6/page/dataList` 的特点是 `url` 参数内嵌页面路由或专题路由，`title` 与 `page` 控制具体栏目和分页。因此它更像是频道页、专题页或标签页的数据列表接口。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_CH7G5995XUSP86E.png)

 酷安 App 首页

### 11.3 发帖提交

发帖阶段最关键的接口是：

```
POST api.coolapk.com /v6/feed/createFeed
```

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_25UKWKERBM8Y9DU.png)

 发帖请求包

脱敏后的请求体结构如下：

```
id=
message=[REDACTED]
type=feed
pic=
status=1
publish_status=0
location=
long_location=
latitude=0.0
longitude=0.0
media_url=
media_type=0
media_pic=
message_title=
message_brief=
extra_title=
extra_url=
extra_key=
extra_pic=
extra_info=
message_cover=
disallow_repost=0
is_editInDyh=0
forwardid=
fid=
dyhId=
targetType=
productId=
province=
city_code=
location_city=
location_country=
disallow_reply=0
vote_score=0
replyWithForward=0
media_info=
insert_product_media=0
is_ks_doc=0
goods_list_id=
is_html_article=2
_v2_post_token=[REDACTED]
```

这个接口的分析价值很高，因为它直接对应用户的“发布动态”动作。从字段上看，它不仅包含正文，还包含发布状态、媒体、位置、转发/评论控制、商品/文档扩展、提交 token 等信息。

安全上需要注意：

- `Cookie`、`X-App-Token`、`X-App-Device`、`_v2_post_token` 任意泄露，都可能造成账号或发帖相关风险；
- 请求体里有 `latitude`、`longitude`、`location` 等位置字段，本次是空值或 `0.0`，但如果用户开启位置，可能带来隐私风险；
- 写接口不应该用于未授权复现或批量调用，分析时应避免误发真实内容。

发帖后还观察到个人动态刷新：

```
GET api.coolapk.com /v6/user/feedList?uid=[REDACTED]&page=1&showAnonymous=0&isIncludeTop=1
```

这说明发布后 App 会回到用户 feed 列表或个人页进行刷新确认。

![image](https://bbs.kanxue.com/upload/attach/202607/1019522_S9SNDKXHGRKPWTT.png)

 酷安 App 发帖页

>
> 建议在这里放一张发帖页截图，正文使用测试内容即可。请不要展示真实账号、真实私密内容、定位、草稿箱、手机号或验证码。如果截图发布后页面，也要打码头像、昵称和用户 ID。 -->
>
>
>

## 12. 登录、验证码与敏感字段观察

手动登录“提交瞬间”没有被有效抓到，因此不能断言完整登录协议是什么样。

但基于现有抓包，可以得出两个有限结论：

1. 现有登录相关抓包文件中，没有发现明文短信验证码/登录验证码字段；
2. 登录后请求中能看到会话相关 Header/Token 会随业务请求发送。

已检查过的关键词包括：

```
验证码、短信、sms、captcha、verify、verification、smsCode、verifyCode、code=、phone、mobile、quickpass、login、password
```

日志中出现的 `code=` 主要来自：

- SDK 的 `version_code`；
- 发帖参数中的 `city_code`；
- `_v2_post_token` 等提交校验字段。

这些不是短信验证码。

因此，准确结论应该写成：

```
在现有抓包样本中没有看到明文验证码字段；但由于登录提交瞬间没有被可靠覆盖，这不能证明酷安登录接口一定不会上传验证码明文。如果重新在 eCapture 正常运行状态下抓完整短信登录流程，仍需要再次确认。
```

敏感字段方面，本次酷安业务请求普遍涉及：

| 字段 | 风险 |
|-|-|
| `Cookie` | 登录态/会话凭据，泄露后可能导致账号被冒用 |
| `X-App-Token` | 客户端签名或鉴权相关 Header |
| `X-App-Device` | 设备指纹/设备标识相关 Header |
| `_v2_post_token` | 发帖提交校验 token |
| `uid` | 账号身份或行为关联字段 |
| `feed_id`、阅读进度 | 可关联用户浏览行为 |
| 第三方 SDK body | 可能包含设备、网络、屏幕、广告位、风控特征 |

## 13. 第三方 SDK 与非核心业务流量

酷安主页和登录/发帖过程中混入了不少第三方 SDK 流量。按本次 eCapture的text log与 pcapng 观察，主要包括：

| 类型 | 代表域名/路径 | 可能用途 |
|-|-|-|
| 腾讯广告/GDT | `v2mi.gdt.qq.com /gdt_mview.fcg`、`sdk.e.qq.com /event`、`win.gdt.qq.com /win_notice.fcg` | 广告展示、曝光、点击、素材统计 |
| 腾讯 HTTPDNS | `119.29.29.87 /d?dn=api.coolapk.com...` | HTTPDNS 解析 |
| 字节/穿山甲 | `toblog.ctobsnssdk.com /service/2/app_log/` | 日志、广告或埋点 |
| 网易易盾 | `da.dun.163.com /sn.gif`、`ir-sdk.dun.163.com /v4/a/up` | 风控、登录/环境检测 |
| 快手广告 | `open.e.kuaishou.com /rest/e/v3/open/logBatch` | 广告/反作弊/日志批量上报 |
| 百度/运营商等 | `mime.baidu.com`、`auni.telecome.cn` 等 | SDK、认证、资源或环境检测 |

这些请求不一定都是酷安核心业务，但它们对隐私和合规分析很重要。移动 App 真实流量往往不是“一个 App 对一个服务端”，而是一组业务接口、广告 SDK、风控 SDK、HTTPDNS、图片 CDN、日志上报共同构成的网络生态。

## 14. AI Agent 在这类任务里的实际价值

这次任务中，AI Agent 的价值不是简单替人敲命令，而是把多阶段过程串起来：

1. 根据自然语言目标拆解任务；
2. 下载和部署工具；
3. 判断 r0capture 产物是否为空；
4. 识别 Frida attach/spawn、OkHttp hook 失败；
5. 切换到 tcpdump 保留网络侧证据；
6. 发现 eCapture 的 CAP_BPF/capability 问题；
7. 记住 KernelSU debug shell 的可用执行方式；
8. 把 text log、pcapng 形成分析报告；

这条链路体现了 Agent 更适合做“长链路安全测试辅助”，而不是只完成一次命令执行。

如果把传统抓包看作“看见流量”，那么 AI Agent 参与后的目标应该是“理解流量并沉淀流程”。

## 15. 复盘：AI 自动抓包的价值不只是少敲命令

这次酷安抓包复盘可以总结为三点。

第一，工具失败本身也是有效结论。r0capture/Frida 阶段虽然没有拿到可用明文，但它明确告诉我们：当前 Hook 方式对这个目标不可靠，继续围绕空 pcap 做分析没有意义。

第二，pcapng 和 text log 要分工使用。pcapng 适合看网络连接、域名、SNI、HTTP 明文资源和第三方 SDK；text/stdout log 才是这次分析酷安 `/v6/...` API path、Header、Body 的主证据。

第三，eCapture 在 Android 上很好用，但前提是 root shell 真的具备加载 eBPF 所需的能力。KernelSU 普通 su shell 中 `CapEff=0` 时，eCapture 会失败；这次通过 `/data/adb/ksud debug su -g` 解决，是一个值得记录的关键经验。

最终，本次抓包确认了酷安 App 在登录后同步、主页信息流和发帖操作中的多条核心接口：

```
/v6/service/sync2
/v6/main/indexV8
/v6/page/dataList
/v6/notification/list
/v6/account/loadConfig
/v6/feed/createFeed
/v6/user/feedList
```

其中 `/v6/feed/createFeed` 是最典型的写接口，body 中包含正文、发布状态、媒体、位置、回复/转发控制和 `_v2_post_token`。

本次实验还观察到一个有价值的现象：当 Hermes Agent 完成酷安 APP 抓包后，再处理另一个游戏中心 APP 时，可以复用此前沉淀的 Skill 和 Memory，将任务完成时间缩短到约原来的 1/3。这个结果说明 Agent 的价值不是单次执行，而是持续积累。

这就是 AI Agent 自动抓包在真实任务里的价值：不是保证某个工具一次成功，而是在工具失效、权限受限、数据混杂时，仍然能把链路跑通，把失败原因、有效证据和业务结论整理出来。

所以，AI 自动抓包的最终价值不是“少敲几行命令”，而是：

- 让逆向工程师从重复环境问题中解放出来；
- 让流量分析从截图展示走向业务解释；
- 让一次经验沉淀为可复用流程；
- 让安全测试报告更快从数据包抵达结论。

如果说传统抓包解决的是“看见流量”，那么 AI Agent 自动抓包要解决的是“理解流量”。这才是它值得继续深入的地方。

## 16. 参考资料

1. [Hermes Agent 中文文档](https://hermesagent.org.cn/docs)
2. [Frida 官方文档](https://frida.re/docs/)
3. [r0capture GitHub 仓库](https://github.com/r0ysue/r0capture)
4. [用实测说话！Hermes Agent真的比OpenClaw更好吗？实战/原理/如何安装详解](https://www.bilibili.com/video/BV1zRdaBcE9x/?share_source=copy_web&amp;vd_source=a06553ded9844b5ef06db446deeb5e88)
5. [我们发现了 Hermes Agent 的第一个远程代码执行漏洞，但这已经不重要了](https://mp.weixin.qq.com/s/R8r4WSi1eEh0r0Uwxo_5dA)
6. [eCapture GitHub 仓库](https://github.com/gojue/ecapture)
7. [eCapture旁观者：Android HTTPS明文抓包](https://www.bilibili.com/video/BV1xP4y1Z7HB/?share_source=copy_web&amp;vd_source=a06553ded9844b5ef06db446deeb5e88)
8. [Loop Engineering 入门:从 Prompt 到 Loop 的范式跃迁](https://mp.weixin.qq.com/s/QwPdOXl9PT8f7Gz8vaDzHg?scene=1&amp;click_id=28)
9. [Loop Engineering](https://addyosmani.com/blog/loop-engineering/)

————————————————————————————————————————————————
个人介绍

1. 网安老兵，擅长Web渗透测试、JS逆向、IOT安全测试；
2. 开发过多个安全、逆向工具、POC、Burp插件等，在github上已发布；
3. github主页：https://github.com/xm1nutes

---

# 回复

## 回复 by xxxmm (#2)

*2026-7-8 15:55*

欢迎感兴趣的师傅提问，一起成长。文章得到了r0ysue佬的指点，在此表示感谢。

## 回复 by xxxmm (#3)

*2026-7-8 23:10*

个人介绍
1. 网安老兵，擅长Web渗透测试、JS逆向、IOT安全测试；
2. 开发过多个安全、逆向工具、POC、Burp插件等，在github上已发布；
3. github主页：https://github.com/xm1nutes

## 回复 by Imxz (#4)

*2026-7-10 14:06*

tql

## 回复 by clz3216 (#5)

*2026-7-13 23:04*

很有参考性

## 回复 by xxxmm (#6)

*2026-7-17 16:55*

>
> [clz3216](https://bbs.kanxue.com/user-963838.htm)
>  很有参考性
>

多谢支持，欢迎一起交流

## 回复 by xxxmm (#7)

*2026-7-17 16:55*

>
> [Imxz](https://bbs.kanxue.com/user-656334.htm)
>  tql
>

多谢支持，欢迎一起交流

## 回复 by 老衲很年轻 (#8)

*2026-7-21 22:08*

登录型app还是危险，检测root环境就封了
