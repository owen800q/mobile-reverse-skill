---
title: '[原创]某开源通讯软件view once图片的调用逻辑分析'
url: https://bbs.kanxue.com/thread-291248.htm
tid: 291248
author: mb_hfjfruhl
date: '2026-05-17'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T13:52:24+08:00'
replies: 0
---

# 某开源通讯软件view once图片的调用逻辑分析

## 1. 传输协议

一开始直接用了burpsuit抓包，但是什么东西都没抓到，于是用netstat看了一下，再结合资料，发现用的是私有协议mtproto，所以burp抓不到东西。

直接用frida开始hook，虽然不太清楚具体的结构，但是可以先hook一些比较底层的函数，然后分析数据再把hook点一步步的网上移，最后挂到反序列化、解密操作之后的地方。

### 1. 从网络层开始

用脚本先Hook native里的以下函数:

```js
connect
close
getpeername
getsockname
send
sendto
write
recv
recvfrom
read
```

这一步可以拿到fd, peer, ip:port, 收发方向, 包大小。

然后分析包的前十几个bytes，发现了疑似mtproto transport的类型。

例如:

```python
0xef -> mtproto-abridged-init
0xeeeeeeee -> mtproto-intermediate-init
0xdddddddd -> mtproto-padded-intermediate-init
```

这里看到的只是原始数据，是看不到明文的。

### 2. hook java层的ConnectionsManager.sendRequest

可以hook

```python
org.telegram.tgnet.ConnectionsManager.sendRequest
```

在这里直接遍历

```js
const ConnectionsManager = Java.use('org.telegram.tgnet.ConnectionsManager');
const overloads = ConnectionsManager.sendRequest.overloads;
```

然后打印第一参数，也就是tl的请求对象:

```js
const req = arguments[0];
reqName = req ? req.$className : '<null>';
fields = summarizeTlObject(req);
```

在日志里就能够看到:

```
TL_messages_getHistory
TL_messages_readHistory
TL_messages_sendMessage
TL_messages_getMessagesReactions
```

### 3. hook入站

真正获取到明文消息的内容的位置是在

```java
org.telegram.messenger.MessagesController.processUpdates
```

在这里只选择第一参数是:

```js
org.telegram.messenger.MessagesController.processUpdates
```

的overload。
可以做个简单的逻辑判断：

```js
if (firstArg !== 'org.telegram.tgnet.TLRPC$Updates') {
    return;
}
```

然后调用

```js
logIncomingUpdates('MessagesController.processUpdates', updates, fromQueue);
```

这里已经是 Telegram 客户端处理服务端更新的业务层了。也就是说：

```
MTProto 网络包
 -> native/tgnet 解密
 -> TL 反序列化
 -> 得到 TLRPC$Updates
 -> 进入 MessagesController.processUpdates
```

在这里抓到的就不是密文了，而是java对象。

接下来需要做的是对updates.updates里的东西进行筛选:

```
TL_updateNewMessage
TL_updateNewChannelMessage
TL_updateShortMessage
TL_updateShortChatMessage
```

如果发现有message字段，就进一步去尝试获取:

```js
message.id
date
out
message
from_id
peer_id
media
```

### 4. 聊天框中的消息对象MessageObject

找到的最贴近聊天窗口的地方是在:

```js
org.telegram.messenger.MessageObject
```

hook一下MessageObject的构造函数：

```js
MessageObject.$init.overloads.forEach(function (overload) {
    overload.implementation = function () {
        const ret = overload.apply(this, arguments);
        logMessageObject(this, 'MessageObject.<init>');
        return ret;
    };
});
```

这个MessageObject是一个用的很多的消息包装对象，文本、图片、媒体状态都会被包成这个对象然后交给ui。

logMessageObject()主要功能是：

```js
const owner = readField(obj, 'messageOwner');
const summary = owner ? summarizeMessage(owner) : {};
const messageText = readField(obj, 'messageText');
```

其中：
messageOwner 是原始 TLRPC$Message
messageText 是 UI 层处理后的文本
summarizeMessage(owner) 会继续解析消息、发送方、会话、媒体

所以这一步拿到的其实就是已经解密、反序列化之后的马上要给ui去用的明文消息。

大概的格式是这样的：

```js
{
  "api": "MessageObject.<init>",
  "message_object": {
    "class": "org.telegram.tgnet.TLRPC$TL_message",
    "id": "20",
    "out": "false",
    "message": "",
    "media_unread": "true",
    "media": {
      "class": "org.telegram.tgnet.TLRPC$TL_messageMediaPhoto",
      "ttl_seconds": "2147483647",
      "photo": {
        "class": "org.telegram.tgnet.TLRPC$TL_photo",
        "id": "...",
        "dc_id": "5"
      }
    },
    "messageText": "阅后即焚图片"
  }
}
```

这里的ttl_seconds应该是这张图片过期的时间，2147483647是最大的int值。在app里处理的时候也有判断ttl_seconds == Interger.Max的，如果是那就说明这是一张view once图片；如果ttl_seconds > 0说明不是一张普通的图片；如果0 < ttl_seconds < Interger.Max那就计算其过期时间，时间到了就调用相应的销毁逻辑。

## 2. 图片处理逻辑分析

### 1. hook getPathToAttach

在找到以上信息之后，为了找到对应的图片处理逻辑，直接尝试hook了getPathToAttach这个函数。

每当从对话列表点到对话框里的时候，就会调用这个函数去加载照片。

对于普通的图片和阅后即焚的图片保存路径是不一样的，阅后即焚的照片保存路径在

```
/storage/emulated/0/Android/data/org.telegram.messenger.web/cache
```

并且不是以明文的形式保存的。通过对这个目录下的一些文件进行分析，发现文件名有点意思，可以看看：

```
-6070991742858629533_120.jpg.enc
-6070991742858629543_121.jpg.enc
-6070991742858629543_121.jpg.enc.key
-6070991742858629543_121.temp.enc
```

除了开头的那个-之外，60709917428586295这一段相同，后面的结尾有点不同。

所以有理由相信，这些就是同一组照片在cache中的不同的派生文件，简单来说就是这是一起的。

所以接下来需要找的就是谁加载了这些文件，然后加载之后去了哪里，在哪里解密的？

### 2. .enc文件调用链

为了找到是谁打开了这个.enc，在native层我hook了：

```
open
open64
openat
openat64
read
close
```

在java层hook了：

```java
org.telegram.messenger.secretmedia.EncryptedFileInputStream
```

中的

```java
read(byte[], int, int)
skip(long)
decryptBytesWithKeyFile(byte[], int, int, java.io.File)
decryptBytesWithKeyFile(byte[], int, int, org.telegram.messenger.SecureDocumentKey)
```

还有

```java
org.telegram.messenger.secretmedia.EncryptedFileDataSource
```

中的

```java
open(com.google.android.exoplayer2.upstream.DataSpec)
read(byte[], int, int)
```

最终确定了调用链:

```
/data/user/0/org.telegram.messenger.web/cache/-6070991742858629543_121.jpg.enc.key
  -> 读取 32 bytes key
  -> 读取 16 bytes iv

/storage/emulated/0/Android/data/org.telegram.messenger.web/cache/-6070991742858629543_121.jpg.enc
  -> EncryptedFileInputStream.read(...)
  -> Utilities.aesCtrDecryptionByteArray(...)
```

总结就是：
.enc图片的实际路径是:cache/-6070991742858629543_121.jpg.enc
对应的key是：

```
/data/user/0/org.telegram.messenger.web/cache/-6070991742858629543_121.jpg.enc.key
```

其中.key文件的结构是前32字节的aes key, 后16字节的iv。
调用的解密函数是:

```java
org.telegram.messenger.Utilities.aesCtrDecryptionByteArray([B, [B, [B, int, long, int)
```

caller是:

```java
org.telegram.messenger.secretmedia.EncryptedFileInputStream.read([B, int, int)
```

使用的模式是mode=0, 对应的是ctr模式。

完整的链路如下：

```java
ImageLoader / CacheOutTask
  -> EncryptedFileInputStream
  -> 读取 .jpg.enc.key: key(32) + iv(16)
  -> read .jpg.enc chunk
  -> Utilities.aesCtrDecryptionByteArray(buffer, key, iv, offset, length, fileOffset)
  -> 得到解密后的图片字节流
```

## 3. 图片重建

第二点里已经讲到了加密文件的存储路径以及对应的解密函数了，这里简单讲一下解密之后怎么去重建一个图片。

### 1. Hook aes解密的函数

hook这个可以打印一些信息，但是hook这个最主要的方法是，确定app真的调用了这个函数解密。

### 2. hook EncryptedFileInputStream.read(byte[], int, int)

这个是核心，同时这个也是解密函数的caller。hook这个可以直接拿到明文。

### 3. 重建图片

接下来就比较简单，把拿到的明文拼接一下，判断一下数据的开头和结尾，命中了之后直接保存就完事，扩展名是.jpg，然后直接保存完事。

## 4. 关于ai

以上的分析深度的结合了ai，现在的ai能够干大量人不好干的工作，比如看汇编, smali代码, frida脚本跑出来的大量的未经处理的日志等等这种对人来说晦涩难懂的东西。ai看这些东西看的又快又准，还能帮着写hook脚本，又快又好。但是整体过程中还是有很多地方需要人去把控，纯让ai做容易跑偏。
还有就是一个ai的正义感问题，涉及到隐私功能的分析ai直接不干了，还得让人去拆解成一个个的小目标然后一点点的摸索。
总的来说ai在数据分析方面优势很明显，可以信任但是不能100%信任，每个流程还需要自己把控一下。
如果还需要学习技术，一定要在ai做完了之后多复盘，把技术细节和有疑问的地方搞清楚。
