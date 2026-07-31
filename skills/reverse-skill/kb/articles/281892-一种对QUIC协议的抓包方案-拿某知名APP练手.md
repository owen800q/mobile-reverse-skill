---
title: 一种对QUIC协议的抓包方案（拿某知名APP练手）
url: https://bbs.kanxue.com/thread-281892.htm
tid: 281892
author: 执着的追求
date: '2024-05-25'
tags: [Android安全, 协议分析]
crawled_at: '2026-07-31T14:26:51+08:00'
replies: 17
---

# 前言

   自从转到了安全岗后，Android这一块的东西也很少碰了，最近感觉工作挺无聊的，想重新涉足这一领域，看看能不能跳个槽什么的！刚好前段时间有个朋友提到某音现在抓包很难，说是因为采用了什么 QUIC 协议，想让我帮忙看看有没有解决方法。所以借此契机就打算拿这个来重新入门了。

    有太长时间没关注过Android这块的对抗技术了，某音在这方面一定也是在持续迭代，为了保险起见不被各种对抗技术劝退，所以选了一个它的同门APP某茄小说，根据以往的经验，它们两个所用的网络框架和底层网络支持库都是一样的，所以从理论上来讲搞定了某茄小说就等于搞定了某音。

    根据从网上查到的一些公开怎么应对GQUIC协议抓包的方法，大多都是在想办法去绕过这个协议。如，修改路由规则来阻止UDP上443端口的流量使其被动地降级到HTTPS，或者逆向分析调整QUIC配置使其直接降级到HTTPS。还有一些其他方法，如Dump SSL中的KeyLog，然后再使用Wireshark解密。这个方法用来抓取HTTPS特别好用，对于QUIC来说则只支持IETF标准下的QUIC，本例中的APP使用的是早期的GQUIC，它有着一套自己的加密方式QUIC Crypto，所以并不适用。

    总的来说这些方法都更注重于实用性偏向于技巧性，虽对于学习来说也不无裨益，但我更倾向于去理解协议，从协议层去解决这个问题。

---

# 1. 先来一个简单的协议介绍

      QUIC，音同 'quick'，最初由 Google 提出，是一种将 HTTP/2的多路复用与头部压缩机制封装到数据包中，通过 UDP 进行传输的协议，仅应用于 HTTP 之上。后续随着 HTTP/2 的逐步完善，QUIC 逐步演变为独立协议，并被 IETF 规范化。IETF 提出了两个概念，即 HTTP Over QUIC 和 QUIC 传输层协议，使得 QUIC 可以被用于其他应用层协议之上。自此，QUIC 就分为了 Google 版本和 IETF 版本，前者被称之为 GQUIC，后者被称之为 IQUIC。现在所常说的 QUIC 一般都指后者，HTTP/3 协议也是基于 IQUIC 的。

    在安全性方面，GQUIC与IQUIC采用了两个完全不同的方式，前者使用了自己的一套加密方式QUIC Crypto，后者还是延续使用了TLS1.3.

从这张图中可以看到他们之间的区别
![image](https://bbs.kanxue.com/upload/attach/202405/848410_P8VZTH2JFSHQVUC.webp)
    本文中所提到的APP使用的是GQUIC Q043协议，所以下文也只会针对这个版本进行分析。

# 2. 怎么在移动设备上抓取GQUIC的流量

   QUIC在网络流量中表现形式为UDP流量，因此传统的HTTP抓包工具无法捕获它，所以需要使用能够直接抓取网卡流量的工具，如tcpdump和Wireshark。要在Android设备上捕获网卡流量,有两种主要方式:

1. 在本地搭建一个类似于软路由的服务,通过VPN连接后,即可从软路由上进行抓包。
2. 在Android设备上安装tcpdump,从而直接进行抓包。可以通过[Termux](https://github.com/termux/termux-app)来安装。

我所使用的是waydroid，它用了容器技术使得可以在Linux系统上直接运行原生的Android环境，因此Linux宿主机也可以随意的访问和操作Android环境的资源。

---

    在这里帮张银奎老师的幽兰打一个广告，幽兰是一款ARM64的笔记本，其中内置了waydroid，JTAG调试接口和EBPF等。在里面可以自定义ARM的Android镜像，用gdb调试Android中的进程，访问Android文件系统，直接与ARM处理器通信等，总之让你体验站在上帝的视角看Android，嘎嘎好用！

    感兴趣的朋友可以了解一下[Nano Code](https://www.nanocode.cn/#/yl/)。

---

 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_RYQUX2P6GU2DD5R.webp)

    流量已经能抓到了，下面来看看流量中是个什么东西。

# 3. GQUIC的数据包结构

## 3.1. 整体结构

      GQUIC中的数据包分为常规数据包和特殊数据包，特殊数据包用于版本协商和连接重置，常规数据包则用于正常的数据传输，因此本文主要分析常规数据包。一个完整的GQUIC常规数据包由一个可变长度的数据包头部和一个或多个可变长度的数据帧构成,头部携带控制信息,帧负责承载应用数据，整体分层结构如下图所示。

 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_BD774EE97UX2SMQ.webp)

                                                            （抽象图）

    在常规数据包中，除用于建立初始连接的握手包(Client Hello和Server REJ)外,所有数据包自第一帧起均均会被加密，对握手包则是进行HASH认证。

 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_4YG7KZDGUS2G5MA.webp)

                                                         （未被加密的CHLO包）

 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_85SV6XRRKQV9EB9.webp)

                                                         （加密后的常规数据包）

## 3.2. 数据包剖析

### 3.2.1. 包头部分

    GQUIC数据包头部包含了几个控制字段，其长度在1-51字节之间，具体格式为：

| 123456789101112131415161718192021222324252627282930313233 | `0        1        2        3        4            8``+--------+--------+--------+--------+--------+---    ---+``\| Public \|    Connection ID (64)    ...                 \| ->``\|Flags(8)\|      (optional)                              \|``+--------+--------+--------+--------+--------+---    ---+``9       10       11        12` `+--------+--------+--------+--------+``\|      QUIC Version (32)            \| ->``\|         (optional)                \|` `+--------+--------+--------+--------+` `13       14       15        16      17       18       ...      44``+--------+--------+--------+--------+--------+--------+--------+--------+``\|                        Diversification Nonce                          \| ->``\|                              (optional)                               \|``+--------+--------+--------+--------+--------+--------+--------+--------+``45      46       47        48       49       50``+--------+--------+--------+--------+--------+--------+``\|           Packet Number (8, 16, 32, or 48)          \|``\|                  (variable length)                  \|``+--------+--------+--------+--------+--------+--------+` `51       ...``+--------+--------+--------+--------+--------+--------+``\|                     XXX Frame                       \|``\|                  (variable length)                  \|``+--------+--------+--------+--------+--------+--------+` `51 + prev frame len``+--------+--------+--------+--------+--------+--------+``\|                     XXX Frame                       \|``\|                 optional (variable length)          \|``+--------+--------+--------+--------+--------+--------+` |
|-|-|

    Public Flags字段是一组控制标识，共8个字节，具体含义如下：

        0x1：如果该数据包是由客户端发起的，则表示包头中包含了一个4字节长度的版本号信息。如果该数据包是由服务端发起的，则表示这是一个特殊的版本协商包。

        0x2：表示这是一个特殊的连接重置包。

        0x4：表示包头中包含了一个32字节长度的随机数Diversification Nonce，这个标志只在由服务端发起的数据包中有效。

        0x8：表示数据包中包含了一个8字节长度的Connetion ID， 由客户端发起的数据包中会携带。

        0x30：表示包头中包含了一个6字节长度的包编号。

        0x20： 表示包头中包含了一个4字节长度的包编号。

        0x10：表示包头中包含了一个2字节长度的包编号。

        0x00：表示包头中包含了一个1字节长度的包编号。

        0x40：保留。

        0x80：保留。必须为0。

    Diversification Nonce字段是一个随机数，用于密钥的计算，通常出现在server hello数据包中。Packet Number字段表示数据包的序号，从1开始依次递增，主要用于ACK机制，但不能保证应用数据的流式顺序。其他字段的含义可以通过其名称直接理解，因此不再赘述。

### 3.2.2. 帧部分

     GQUIC包含了多种类型的数据帧。例如，Stream Frame用于承载客户端和服务器之间的应用数据；ACK Frame和Stop Waiting Frame用于数据包的可靠传输；Padding Frame用于满足协议的对齐要求等。但这里的重点是怎么获取客户端与服务端之间传输的应用数据，因此也只会对Stream Frame进行分析。若有兴趣了解更多，可参考Google放出的官方文档[QUIC Wire Layout Specification - Google 文档](https://docs.google.com/document/d/1WJvyZflAO2pq77yOLbp9NsGjC1CHetAXV8I0fQe-B_U/edit#heading=h.o9jvitkc5d2g)。

    Stream Frame，指的就是数据流。它是一个独立的数据传输通道，每个流都有一个唯一的Stream ID。多条流可以同时进行数据传输而互不干扰，因此一个连接中可以存在多个流，也就是多个数据通道，这正是GQUIC多路复用机制的实现。其格式如下：

| 12345678910111213141516171819202122232425 | `SLEN用于表示Stream ID字段的长度，OLEN用于表示offset字段的长度，``DLEN用于表示Data Length字段的长度。``0           1       …                SLEN``+--------+--------+--------+--------+--------+``\|Type (8)\| Stream ID (8, 16, 24, or 32 bits) \|``\|        \|    (Variable length SLEN bytes)   \|``+--------+--------+--------+--------+--------+` `SLEN+1  SLEN+2     …                                         SLEN+OLEN` `+--------+--------+--------+--------+--------+--------+--------+--------+``\|   Offset (0, 16, 24, 32, 40, 48, 56, or 64 bits) (variable length)    \|``\|                    (Variable length: OLEN  bytes)                     \|``+--------+--------+--------+--------+--------+--------+--------+--------+` `SLEN+OLEN+1   SLEN+OLEN+2``+-------------+-------------+``\| Data length (0 or 16 bits)\|``\|  Optional(maybe 0 bytes)  \|``+------------+--------------+` `SLEN+OLEN+1+DLEND``+-------------------+-------------+``\|          Data Block             \|``\|      (Variable length)          \|``+-------------------+-------------+` |
|-|-|

    Type字段是一个长度为1字节的值，包含各种标志，为方便描述所以这里表示为“1fdooossB”。其中最高位必须为1，f位表示FIN位，意味着发送结束；d位表示是否存在Data Length字段。接下来的三个ooo位表示Offset字段的长度，最后两个ss位表示Stream ID字段的长度。

    Offset字段是一个可变长度的值，它用于表示这个帧中所携带的数据块在整个数据流中的偏移量。因为基于UDP的协议都会存在乱序这个现象，所以GQUIC使用了Stream ID + Offset的机制来确认一个流中每个数据块的顺序，接收方再根据这个顺序来重新组装数据。

    Data Lenght字段是一个可选字段，若存在该字段，则表示该帧中所携带的数据块的长度。若不存在该字段，则表示这是最后一个帧，且该数据包中后续所有的内容都是这个帧所携带的数据块。

    Data Block就是帧所携带的数据，主要分为三种类型：HandShakeMessage、HTTP/2 Frame和HttpBody。HandShakeMessage用于传递双方的握手消息，HTTP/2 Frame用于传递双方的HTTP头部数据，HttpBody则用于传递双方的HTTP主体数据，以下是详细的介绍。

### 3.2.3. HandShakeMessage

   HandshakeMessage用于客户端和服务器在握手阶段的通信，共有四种类型：由客户端发起的InChoate CHLO和Complete CHLO，以及由服务器发起的Rejection和SHLO。它们通过一个tag字段进行区分，如下：

  ![image](https://bbs.kanxue.com/upload/attach/202405/848410_N2HGGYWKQZJRHHS.webp)

    InChoate CHLO表示这是一个不完整的CHLO包，它的目的是希望服务器能够提供自身的配置信息，它可包含以下字段：

- **SNI**（可选）：用于解析DNS的域名。
- **STK**（可选）：服务器先前提供的令牌。
- **PDMD**：客户端所接受的证书验证算法。
- **CCS**（可选）：本地通用证书的Hash值。
- **CCRT**（可选）：缓存的服务器证书的Hash值。
- **VER**：所使用的协议版本。
- **XLCT**：客户端期望服务器使用的叶证书的哈希值。

    Rejection 是服务器在收到客户端发起的 InChoate CHLO 后作出的响应消息，其中包含了服务器自身的配置信息。这些配置信息将用于后续的密钥协商，它可包含以下字段：

- **SCFG**（可选）：服务器的配置信息，它包含了一个或多个配置项，每个配置项都包含以下内容：

	- AEAD： 服务器所支持的数据加密算法。
	- SCID：该配置的 ID。
	- PUBS：服务器的公钥。
	- KEXS：服务器所支持的密钥交换算法。
	- Orbit：历史遗留。
	- EXPY：该配置项的过期时间。
	- VER：该配置项所支持的版本。
- **STK**（可选）：一个不透明的字节串，客户端需要在下一个CHLO包中携带这个值。
- **SNO**（可选）：服务端生成的随机数，客户端需要在下一个CHLO包中携带这个值。
- **STTL**（可选）：服务器配置的有效时长（以秒为单位）。
- **CRT**（可选）：服务器其的证书链。
- **PROF**（可选）：用于对服务器证书的验证。

   Complete CHLO 表示客户端和服务器已经完成了所有通信细节的协商，并开始进行密钥交换，它相较于InChoate CHLO包新增了以下字段：

- **SCID**：客户端所使用的服务器配置项ID。
- **AEAD**：客户端所选择的数据加密算法。
- **KEXS**：客户端所选择的密钥交换算法。
- **NONC**：客户端生成的随机数。
- **SNO**（可选）：服务端生成的随机数。
- **PUBS**：客户端的公钥。

    SHLO 包是一个加密消息，表示服务器和客户端已经成功了完成初始密钥的协商，并成功建立了连接。相比于 Rejection 包，SHLO 包新增了一个 PUBS 字段，该字段是一个临时公钥。通过这个临时公钥，双方可以在已协商的初始密钥基础上计算出会话密钥，至此整个握手过程完毕。

### 3.2.4. HTTP/2 Frame

    在GQUIC协议中，HTTP头部数据会被压缩传输，这一部分用的是HTTP/2中的机制，所以称为HTTP2/Frame。（有些资料说它使用的不是HTTP/2，而是HTTP/2的前身SPDY，但Google在它自己的官方文档中都是用HTTP/2描述的）

    由于GQUIC把HTTP/2和QUiC传输层揉到了一起，这使得HTTP2中绝大部分对数据流的管理工作都被GQUIC传输层接管了。因此在该协议中，它只使用了HTTP/2中的HEAD_STREAM类型来处理HTTP头部的压缩数据，所以这里只会涉及到HEAD_STREAM。

HEAD_STREAM的结构可表示如下：

| 123456789 | `+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``\|                 Length (``24``)                   \|``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``\|` `Type` `(``8``)    \|   Flags (``8``)   \|``+``-``+``-``-``-``-``-``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+``\|R\|                 Stream Identifier (``31``)                      \|``+``=``+``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``+``\|                   Frame Payload (``0.``..)                      ...``+``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``-``+` |
|-|-|

- **Length** : 帧主体长度。
- **Type** ： 类型。
- **Flags** ： 特定的Type，有一组特定的flag，以便对type做更多约定。
- **R** : 保留(1bit)。语义未设置并且必须在发送的时候设置为 0 。
- **Stream Identifier** : 流标识符。

### 3.2.5. HttpBody

    HttpBody指的是原始的HTTP主体内容数据，没有特定格式。这部分数据可能会被压缩，具体取决于HTTP头部中的Content-Encoding字段。

### 3.2.6. GQUIC数据包概括

    至此，有关GQUIC中数据包相关的内容大概已经讲完了，相信大家在脑子中都有了一个初步的概念，现在就用一张图来总结一下GUIC的数据包格式，如下：

 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_NUWP63GXR3XDJJ3.webp)

# 4. GQUIC的通信过程

   如果把通信过程划分为三个生命周期阶段，可以将其概括为建立连接阶段、数据传输阶段和连接终止阶段。在建立连接阶段，双方通过握手交换信息来初始化连接；数据传输阶段主要涉及通过一个或多个数据流传递应用数据。最后，在连接终止阶段，双方协商关闭连接并释放所有相关资源。

## 4.1. 建立连接阶段

    在 GQUIC 中该阶段服务器和客户端会使用固定的 Stream ID为1的数据流来交换握手消息（HandShakeMessage），当流建立后，客户端先检查是否存在已缓存的服务器配置信息，如果有则直接进入0-RTT阶段，否则进入1-RTT阶段，流程大概如下：
 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_JFGZWZ9YWAK5CQH.webp)
    详细过程如下：

1. 客户端首先发送一个不完整的CHLO包，请求服务器提供加密通信所需的配置信息。
2. 服务器核查当前使用的协议版本。如果该版本不被支持，便进入版本协商过程；如果支持，则发送一个包含加密配置信息的REJ包。
3. 客户端接收REJ消息后，根据提供的加密配置选取合适的密钥交换算法，并利用服务器的公钥计算出初始密钥。随后，客户端再发送一个完整的CHLO包，其中包含客户端所选用的密钥交换算法，数据加密算法和客户端公钥等。
4. 客户端用初始密钥加密并发送Request包。
5. 服务器使用客户端的公钥计算出初始密钥，再以初始密钥为基础计算出一个临时的公私钥对，服务器使用这个私钥计算出最终的会话密钥。然后，服务器使用初始密钥对Request解密，如果能解开则发送一个用初始密钥加密的SHLO包，SHLO包中包含了用于生成会话密钥的公钥。 最后服务器再响应一个用会话密钥加密的Response。
6. 客户端收到SHLO包后，使用初始密钥解密以提取临时公钥，并使用该公钥生成会话密钥，再使用会话密钥解密Response。
7. 双方均切换至会话密钥，握手阶段结束，后续开始应用数据的传输。

## 4.2. 数据传输阶段

   数据传输阶段顾名思义就是双方进行应用数据传输，在GQUIC中 它使用了不同的双向流分别传递 HTTP 头部数据和 HTTP 主体数据，其中用于传递 HTTP 头部数据的流 ID 固定为 3，而用于传递 HTTP 主体数据的流 ID 则来自于HTTP/2 Frame中的流 ID。在同一个连接上，头部数据和主体数据的传递是同时进行的，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202405/848410_BPY4936AHJ7AAA6.webp)

    从图上来看，其实GQUIC中的多路复用机制并不完全，因为它使用了一个固定的流来传递头部数据，所以少在头部数据的传输过程中还是会存在队头阻塞的问题。

### 4.3. 连接终止阶段

    对本文来说不重要，略。

对于GQUIC协议的分析就到先到此为止了，是时候该考虑怎么对数据包进行解密，以及怎么从数据包中提取HTTP报文的问题了。

# 5. 怎么解密GQUIC数据包

     GQUIC Crypto 使用了前向安全机制，即双方先计算出一个临时的初始密钥，用于对握手阶段的信息进行加密。后续再基于这个初始密钥，进一步计算出会话密钥，用于加密后续的通信数据。这样做的优点就在于，即使服务器的私钥后续被泄露，也无法解密之前已经完成的通信记录。所以想要解密GQUIC数据包，则必须也按照这个步骤先计算出初始密钥，再计算出会话密钥。至于初始密钥和会话密钥的计算过程，Google在其官方文档中已经罗列出了很详细的步骤，所以这里我直接将它抄录如下：

    Key material is generated by an HMAC-based key derivation function (HKDF) with hash function  SHA-256.  HKDF (specified in [RFC 5869](https://tools.ietf.org/html/rfc5869)) uses the approved two-step key derivation procedure specified in [NIST SP 800-56C](http://csrc.nist.gov/publications/nistpubs/800-56C/SP-800-56C.pdf).

Step 1: HKDF-Extract

The output of the key agreement (32 bytes in the case of Curve25519 and P-256) is the premaster secret, which is the input keying material (IKM) for the HKDF-Extract function. The salt input is the client nonce followed by the server nonce (if any).  HKDF-Extract outputs a pseudorandom key (PRK), which is the master secret. The master secret is 32 bytes long if SHA-256 is used.

Step 2: HKDF-Expand

The PRK input is the master secret. The info input (context and application specific information) is the concatenation of the following data:

1. The label “QUIC key expansion”
2. An 0x00 byte
3. The GUID of the connection from the packet layer.
4. The client hello message
5. The server config message
6. The DER encoded contents of the leaf certificate

Key material is assigned in this order:

1. Client write key.
2. Server write key.
3. Client write IV.
4. Server write IV.

If any primitive requires less than a whole number of bytes of key material, then the remainder of the last byte is discarded.

When the forward-secret keys are derived, the same inputs are used except that info uses the label “QUIC forward secure key expansion”.

When the server’s initial keys are derived, they must be diversified to ensure that the server is able to provide entropy into the HKDF.

Step 1: HKDF-Extract

The concatenation of the server write key plus the server write IV from the found round is the input keying material (IKM) for the HKDF-Extract function. The salt input is the diversification nonce.  HKDF-Extract outputs a pseudorandom key (PRK), which is the diversification secret. The diversification secret is 32 bytes long if SHA-256 is used.

Step 2: HKDF-Expand

The PRK input is the diversification secret. The info input (context and application specific information) is the label "QUIC key diversification".

Key material is assigned in this order:

1. Server write key.
2. Server write IV.

   反推上述步骤可见，想要解密GQUIC数据包至少需要四个材料：预主密钥（premaster secret）、CHLO握手数据包，REJ握手数据包，和随机数(Diversification Nonce)。其中后三者都可以通过抓包工具直接获得，但是，预主密钥的生成依赖于各自的私钥和对方的公钥，公钥信息可以从握手数据包中提取，私钥信息则是保密的。因此，解密GQUIC数据包的关键实际上就是怎么去获取私钥。当然，获取服务器的私钥不太现实，但是获取客户端的私钥还是有一定操作空间的。

    目前商用的QUIC协议大多都是基于已开源的项目，因此在分析采用QUIC协议的客户端时，可以先确定其使用的是哪个开源项目后再去分析该项目的开源代码，根据从代码中提取到的特征去逆向分析客户端，使其能直接定位到生成私钥的地方，然后再通过Hook获取。至于怎么通过特征去逆向分析，那办法就多了，最简单的莫过于通过字符串去定位，总之对于有经验的人来说就是小case。

    以某茄APP为例，它使用了Google的cronet库[GitHub - google/quiche](https://github.com/google/quiche)， 所以通过分析cronet的开源代码后通过从代码中提取到的字符串”Key exchange failure“特征，成功地定位到了生成私钥的地方。
 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_Y5MNC62RY3B2U4V.webp)

    然后再使用Frida hook，代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `function` `OnCreatePrivateKey(imgBase)``{``var` `cornetBase = Module.findBaseAddress(imgBase);``if` `(cornetBase ==` `null``)``{``console.log(``"can't found the cornet\n"``);``return``;``}``var` `onCreatePrivateKeyFun =  cornetBase.add(0x1E524C);``if` `(onCreatePrivateKeyFun ==` `null``)``{``console.log(``"bad onCreatePrivateKeyFun"``);``return``;``}``if` `(onCreatePrivateKeyFun.readU64().toString(16) !=` `"97fff8b8910163e8"``)``{``console.log(`bad feature${ onCreatePrivateKeyFun.readU64().toString(16)}`);``return``;``}` `Interceptor.attach(onCreatePrivateKeyFun, {``onEnter:` `function``(args)``{``var` `private_key_ptr =` `new` `NativePointer(``this``.context.x0);``var` `len =` `this``.context.x1.toUInt32();``if` `(len != 32)``{``console.log(``"bad private key"``);``}``else``{``var` `private_key = private_key_ptr.readByteArray(32);``var` `private_key_hex = Array.prototype.map.call(``new` `Uint8Array(private_key), x => ('00``' +` `x.toString(16)).slice(-2)).join('``');` `console.log(`hit OnCreatePrivateKey and the key is ${private_key_hex} the len is ${len}`)``}` `}``})``console.log(``"success found onCreatePrivateKeyFun"``)``}` |
|-|-|

    现在已经能获取到私钥了，然后再根据上述的步骤去生成密钥就可以对数据包解密了，不会也没关系，后面有开源代码。

# 6. 怎么解密使用了0-RTT握手的数据包

    在上一节中提到想要解密数据包，则需要预主密钥（premaster secret）、CHLO握手数据包，REJ握手数据包和多样随机数的参与。但若客户端采用了0-RTT握手方式的话，服务端是不会返回REJ数据包的。那么，该如何解决这个问题呢？很简单，在CHLO包中有一个名为SNI的字段，该字段是服务器的域名，所以当使用一个支持GQUIC的客户端，并通过相同版本的协议访问该域名时，服务器就会返回一个REJ包。由于REJ包中的配置信息是固定的，故可以直接拿来使用。

    还有一个问题就是，SNI其实是一个可选的字段，也就是说可能会出现没有这个字段的场景。如果真出现这种情况的话，也不用慌，可以先试一下通过IP能不能访问到服务器，如果可以的话用IP代替域名也能达到同样的效果，但有的服务器禁止直接通过IP访问，所以对于这种情况就只能逆向分析了。通常来说，SNI这个字段都是有的，因为它会涉及CDN加速的问题，而且稍微大一点的APP都会配置CDN加速。

# 7. 实战

    上面讲了很多东西， 现在要做的就是怎么将这些东西全部给用起来，我在Google开源库[GitHub - google/quiche](https://github.com/google/quiche)的基础上实现了这些功能，并成功地应用到了某茄APP上，效果如下：
 ![image](https://bbs.kanxue.com/upload/attach/202405/848410_H6KBSWXU5AV8Y9R.webp)

    至于某音的话朋友说和这个一样，不过我没尝试，不想去折腾它的反调试了。

    至于具体的实现，这里就不讲了，不然篇幅实在太大，我会把代码上传到Github上，感兴趣的自己去研究吧。

# 8. The End

     源码地址在[这里](https://github.com/aazhuliang/GQUIC_043_decrypt)（只是一个Demo），目前只能应用在GQUIC协议的Q043版本上，如果大家想基于这个源码去扩展的话，则强烈推荐看完[Google的官方文档]([QUIC, a multiplexed transport over UDP](https://www.chromium.org/quic/))，然后再根据文档去读活代码。

    最后，这里只讲了怎么解密GQUIC的流量，如果是IQUIC的话则有更简单的方式，就是文中一开始提到的Dump SSL库中的KeyLog，然后直接使用Wireshark解密。这个方法用来解密HTTPS也百试不爽，下次在再专门写一篇文章来说吧。

    注意：文中所开源的代码只用作学习与交流，切勿用作其它非法用途。

    码字不易，转载请注明出处。

---

# 回复

## 回复 by xwtwho (#2)

*2024-5-26 08:37*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by mb_ldbucrik (#3)

*2024-5-26 09:20*

大佬yyds

## 回复 by linglonger (#4)

*2024-5-26 11:41*

好文好看爱看

## 回复 by 大枫叶 (#5)

*2024-5-27 15:36*

orz

## 回复 by TrumpWY (#6)

*2024-5-28 11:17*

很强!

## 回复 by wulicc (#7)

*2024-5-30 16:45*

大佬 私聊

## 回复 by Limp瘸子 (#8)

*2024-5-30 18:11*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by gtict (#9)

*2024-5-30 23:40*

那个工程都不会弄解密~~

## 回复 by mb_qpswjpde (#10)

*2024-6-3 18:26*

![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by 养只猫不好么 (#11)

*2024-7-30 17:20*

感谢分享

## 回复 by mb_nszigedb (#12)

*2024-9-26 18:37*

大佬，请教下，这个q043目前是没办法在wireshark上解密是吗？我想看它的收发包过程

## 回复 by 执着的追求 (#13)

*2024-9-27 16:56*

wireshark只支持标准QUIC协议，早期的GQUIC不支持。

## 回复 by mb_nszigedb (#14)

*2024-9-29 10:02*

多谢大佬，我看wireshark说可以解码gquic，但是不支持解密，那我还得看看怎么pcap解密了喂给wireshark...想看看gquic收发包情况好艰难

## 回复 by JNI_OnLoad (#15)

*2024-9-29 11:48*

Very good![image](https://bbs.kanxue.com/view/img/face/1.gif)

## 回复 by 利叶增辉 (#16)

*2025-4-23 13:46*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 七浪 (#17)

*2026-4-7 19:55*

QUIC 协议的抓包方案非常及时！越来越多 APP 开始用 QUIC/HTTP3，传统的 MITM 代理已经抓不到。实际中发现可以通过 hook SSL_read/SSL_write 拦截解密后的明文数据，或者用 Frida 劫持 SSLKEYLOGFILE 配合 Wireshark 解密。感谢这个新思路！

## 回复 by jerryxlee (#18)

*2026-6-8 09:34*

主流APP很多都使用这个协议了，26年小白来学习！
