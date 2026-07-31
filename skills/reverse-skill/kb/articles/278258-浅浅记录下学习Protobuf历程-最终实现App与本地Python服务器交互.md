---
title: '[原创] 浅浅记录下学习Protobuf历程，最终实现App与本地Python服务器交互'
url: https://bbs.kanxue.com/thread-278258.htm
tid: 278258
author: 哇哈哈919
date: '2023-08-02'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:39:40+08:00'
replies: 3
---

第一次写文章,难免会有差错,文章若有不妥之处,还请大家不吝赐教~

>
> 希望这篇文章对你有帮助,可以减轻入门protobuf的一些负担~
>
>
>

>
> 目标:
>
>
> 1. 搭建window & Nexus6P(Kali NetHunter) 运行gRPC环境 ps:Nexus6P环境的搭建可有可无~
> 2. 使用Python gRPC 实现: 客户端<-->服务端的protobuf的通信
> 3. PC上 client.py 移植到Nexus6P (Kali NetHunter) 上 实现 android 与服务端(PC)交互 (ps:啥Android啊 那就是Linux.... 可有可无)
> 4. ~~r0env2022 搭建 Android app 运行服务端环境 & 编译apk....~~ 案例Dem0可直接在r0env2022下编译运行,只需要提取出.proto文件 生成服务端代码就可直接使用~真的是太爽了,节省了时间
> 5. 拦截AndroidDem0 <--> PC 上 Python实现的服务端的通信 ~~&反序列化~~
>
>
>

### 与宿主机隔离开发环境

1. 使用 virtualenv 创建一个船新的Python310 的环境 ~~`virtualenv Python310_LearningProtobuf`~~
	- 先执行`pip3 install virtualenv -i https://pypi.douban.com/simple` 再执行 `pip3 install virtualenvwrapper-win -i https://pypi.douban.com/simple`
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_JNV72SSX5NMBD5Y.png)
	- 创建Python虚拟环境存放目录, `D:\Interpreter installation Directory\virtualenv` 并加入系统环境PATH中
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_CTSASPUTC77FBVN.png)
	- 创建虚拟环境 `mkvirtualenv Py310protobuf` 并进入虚拟环境中...
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_U463SXM9PQF83XV.png)
2. 虚拟环境安装 **protobuf** **grpcio grpcio-tools ** `pip3 install protobuf grpcio grpcio-tools -i https://pypi.douban.com/simple `
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_TQD7C3E746N4J37.png)
	- 查看虚拟环境中第三方库及版本
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_P474KSC2HAWRDAH.png)

### 什么是grpc & Protobuf？

- gRPC是一种高性能、开源的远程过程调用（Remote Procedure Call，简称RPC）框架。它由Google开发并开源，旨在解决分布式系统中不同服务之间的通信问题。gRPC基于HTTP/2协议进行通信，并使用Protocol Buffers（简称Protobuf）作为默认的数据序列化和传输格式。
- Protocol Buffers（protobuf）是一种轻量级、高效的数据序列化机制，也是Google开源的项目。它能够将结构化的数据序列化为二进制格式，以便在不同的系统之间进行数据交换。相比于JSON或XML等常见的文本格式，Protobuf产生的数据体积更小，序列化和反序列化速度更快。
- gRPC使用Protobuf作为默认的消息传递格式，通过定义接口和消息类型来描述服务和数据格式，然后自动生成客户端和服务器端的代码。这样可以方便地进行跨语言的服务通信，提供了强大的代码生成能力和易于扩展的特性。gRPC支持多种编程语言，包括C++、Java、Python、Go、Ruby等。
- 总而言之，gRPC是一个基于HTTP/2和Protobuf的高性能RPC框架，它提供了简单、可靠的通信方式，使得分布式系统中的不同服务之间能够高效地进行数据交互。
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_EUVAEB8GX8FH7VJ.png)
- [Protobuf Github](https://github.com/protocolbuffers/protobuf/tree/main/python)
- [Protobuf Python 文档](https://protobuf.dev/getting-started/pythontutorial/)

### Python gRPC Protobuf正向开发 实现PC Client <-->Server 交互

1. 创建 example.proto 文件 来编写对应规则,创建了一个服务 以及两个数据格式

| 1234567891011121314151617 | `syntax` `=` `"proto3"``;` `package test;` `service HelloDemo {``rpc Hello(HelloReq) returns(HelloReply){}``}` `message HelloReq{``string name` `=` `1``;``int32 age` `=` `2``;``string sendtime` `=` `3``;``}` `message HelloReply{``string result` `=` `1``;``}` |
|-|-|
2. 利用 example.proto 通过 grpcio_tools protoc 来生成Python 客户端和服务端(grpc-server)文件 为踩坑记录

	- `python -m grpcio_tools -I. --python_out=. --grpc_python_out=. example.proto` 失败 ,原因-> 猜测应该使用./ 来 表示当前目录~
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_4VEMYJU7K485JY4.png)
	- 换一种方式,使用文档中提供的方式  [protoc github download](https://github.com/protocolbuffers/protobuf/releases/tag/v23.4) 下载之后加入到PATH中
	- `protoc -I=. --python_out=. --grpc_python_out=. example.proto` 对example进行编译 并生成 python客户端和服务端grpc代码
	- but 又又又又报错了 原因不可知也
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_XY29HXDTYHHHSKN.png)
	- 最后,执行 `python -m grpc_tools.protoc -I./ --python_out=./ --grpc_python_out=./ example.proto` 生成了两份代码
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_UJGZ87JDW4BWTWN.png)
3. 根据生成的example_pb2_grpc.py编写 service.py

| 12345678910111213141516171819202122232425262728293031 | `# coding:utf-8` `import` `grpc``import` `example_pb2 as pb2``import` `example_pb2_grpc as pb2_grpc``from` `concurrent` `import` `futures` `# 目的为了给服务器增加线程` `# HelloDemo 为 .proto 文件中 service` `class` `HelloDemo(pb2_grpc.HelloDemoServicer):``# Hello 为  .proto 文件中 service 包含 rpc 方法名` `def` `Hello(``self``, request, context):``name, age, sendtime` `=` `request.name, request.age, sendtime``result` `=` `f``"My Name is {name},age is {age} years old!\n now time is {sendtime}"``# 返回数据类型为.proto 文件中 message   HelloReply` `return` `pb2.HelloReply(result``=``result)`  `def` `run():``grpc_server` `=` `grpc.server(``futures.ThreadPoolExecutor(max_workers``=``4``),``)``pb2_grpc.add_HelloDemoServicer_to_server(HelloDemo(),grpc_server)``# PC 上 监听 127.0.0.1 局域网连接 监听 0.0.0.0``ip_port` `=` `"127.0.0.1:5505"``grpc_server.add_insecure_port(ip_port)``grpc_server.start()``print``(f``"service start at {ip_port}"``)``grpc_server.wait_for_termination()` `if` `__name__` `=``=` `"__main__"``:``run()` |
|-|-|
4. 根据生成的example_pb2.py 编写client.py

| 12345678910111213141516171819202122232425 | `# coding:utf-8` `import` `grpc``import` `example_pb2 as pb2``import` `example_pb2_grpc as pb2_grpc``from` `concurrent` `import` `futures` `def` `run():``# 构建通道与服务器连接``conn` `=` `grpc.insecure_channel(``"127.0.0.1:5505"``)``# HelloDemoStub表示客户端  ,HelloDemoStub是 protoc 自动生成的``client` `=` `pb2_grpc.HelloDemoStub(channel``=``conn)``name, age, sendtime` `=` `"xiaozhu0513"``,` `18``, datetime.now().strftime(``'%Y-%m-%d-%H:%M:%S'``)``# 相当于先生成一个 HelloReq 类型的数据  为 本地发送到客户端的数据, 然后传输  实例化客户端的``response` `=` `client.Hello(pb2.HelloReq(``name` `=` `name,``age` `=` `age,``sendtime` `=` `f``"{sendtime}"``))``print``(f``"客户端发送 {name} {age} {sendtime} -> 服务器"``)``print``(``"客户端接收到服务器返回信息 "``,response.result)`  `if` `__name__` `=``=` `"__main__"``:``run()` |
|-|-|
5. 先运行service.py 再运行 client.py 效果图如下

	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_BXP387P3VG8EJ2A.png)
6. 至此,完成了第一个小任务,最后查阅资料时,发现官方提供了Demo 以及教程....

	- [官方demo](https://grpc.io/docs/languages/python/quickstart/)
	- [client.py](https://github.com/grpc/grpc/blob/master/examples/python/helloworld/greeter_client.py)
	- [service.py](https://github.com/grpc/grpc/blob/master/examples/python/helloworld/greeter_server.py)

### 常用的protobuf数据类型&特殊字符&pb文件&

>
> [官方语法介绍](https://protobuf.dev/programming-guides/proto3/)
>
>
>

#### 常用的protobuf数据类型

1. string -> 字符串类型，要求utf-8或7-bit 与 ascii编码的字符串
2. bytes -> 比特类型
3. bool -> 布尔类型
4. int32 ->32位整形 对应Py是int
5. int64 ->64位整形 对应Py是int
6. float -> 浮点类型
7. repeated -> 数组 (list) 如 repeated string data = 1; 表示 一个 string 的list
8. map -> 字典类型(Python) 如map <string , string> data = 1; 前者为key的string类型 后者为string类型的value

#### 常用的protobuf特殊字符

1. package -> 包名
2. syntax -> Protobuf语法版本
3. service -> 定义一个服务
4. rpc -> 定义服务中的方法
5. stream -> 定义方法的传输为流传输
6. message -> 定义消息体 message User{}
7. extend -> 扩展消息体 extend User{}
8. import -> 导入一些插件
9. // -> 注释~

### 在Nexus6P KaliNetHunter 上 配置环境并启动客户端与PC上server进行通信 (可有可无....)

>
> 目标：
>
>
> 1. 在6P手机上配置好Python环境,grpc环境
> 2. 运行client.py 与 PC上server.py进行交互
> 3. ~~(未复现出)抓包拦截请求数据,尝试分析.... ~~ 当初以为只要运行在手机上就算是android了,,,后来才反应过来,,,,我是运行在linux上py程序不是android
>
>
> 	- client.py 和 android app 走的系统底库不同(后续实现了App抓socket却可以抓到而client.py却不能抓到),
>
>
>

#### Nexus6P手机上配置grpc环境~

1. Python3.10 环境下 直接安装 三件套 `pip3 install protobuf grpcio grpcio-tools -i https://pypi.douban.com/simple`
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_XXKBABBXV2SC6N4.png)
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_8Y8Q869G3JZYU3N.png)
	- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_EQMMCU7V4QYHE2K.png)
2. 下载linux对应的 protoc 工具 push到手机内. 先不下载试试win生成的两份_pb2文件能否共用 ? 是的,可直接可用
3. 将client.py 修改访问地址为局域网内PC的ip 并push到 /sdcard/protobuf 目录下

#### Nexus6P 与PC 通信

将服务端的监听端口由127.0.0.1 修改为 0.0.0.0,之后先启动server 再在6P手机上启动client.Py 实现交互

- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_BMPSVREJ7BGC673.png)
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_XZ7ZRYSSVD3NF9R.png)
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_X6JJ8V7GZVFR6HY.png)
可以发现同一局域网时可以进行通信的

#### 此处采用中间人抓包会报错

客户端启动失败！ charles 抓的包为 Unknow 整体运行逻辑如下~

- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_SDZ9V8VUJDYA5VS.jpg)
- 不知为何原因~

### Android grpc-protobuf Dem0

>
> [demo下载地址](https://github.com/xuexiangjys/Protobuf-gRPC-Android)
>
>
> 目标：
>
>
> 1. 实现Android App 与 PC上建立的Python服务端进行通信
> 2. 弄清楚普通i请求grpc 的执行流程 以及生成对应的Python服务器版本代码
> 3. 最终实现效果可以使得二者可以正常通信，为抓包hook以及分析打下基础
>
>
>

#### 搞清楚 android-java .proto 的运行原理

1. [Java客户端 + Python后端 实现 通信](https://blog.51cto.com/u_15895329/5894299)
2. [官方Java教程](https://protobuf.dev/getting-started/javatutorial/) [官方Python教程](https://protobuf.dev/getting-started/pythontutorial/)

#### 利用Demo 实现与Python 通信

>
> 只分析其中一个界面
>  ![image](https://bbs.kanxue.com/upload/attach/202308/900788_UVZGM72U4JQ7FAM.png)
>
>
>

##### 找到demo中helloworle.proto文件 pull到PC上 并生成Python _pb2_grpc.py 代码

- 进入对应解释器环境下 执行 `python -m grpc_tools.protoc -I./ --python_out=./ --grpc_python_out=./ helloworld.proto`
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_Q75Y4SS86B6XYJ9.png)
- 照猫画虎 写出对应的service.py

| 12345678910111213141516171819202122232425262728293031 | `from` `datetime` `import` `datetime` `import` `grpc``import` `helloworld_pb2 as pb2``import` `helloworld_pb2_grpc as pb2_grpc``from` `concurrent` `import` `futures` `class` `Greeter(pb2_grpc.GreeterServicer):``def` `SayHello(``self``, request, context):``name` `=` `request.name``sendtime` `=` `datetime.now().strftime(``'%Y-%m-%d-%H:%M:%S'``)``result` `=` `f``"My Name is {name}!!! send time is {sendtime} "``print``(f``"服务器接收到客户端参数 -> name = {name}"``)``print``(f``"服务器响应时间: {sendtime}"``)``return` `pb2.HelloReply(message` `=` `result)`  `def` `run():``grpc_server` `=` `grpc.server(``futures.ThreadPoolExecutor(max_workers``=``4``),``)``pb2_grpc.add_GreeterServicer_to_server(Greeter(),grpc_server)``# ip_port = "127.0.0.1:50051"``ip_port` `=` `"0.0.0.0:50051"``grpc_server.add_insecure_port(ip_port)``grpc_server.start()``print``(f``"service start at {ip_port}"``)``grpc_server.wait_for_termination()` `if` `__name__` `=``=` `"__main__"``:``run()` |
|-|-|
- 验证启动apk 能否正常通信
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_BH5D2XN49HJBCHA.png)
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_UAMJXADGQD8J35E.png)

所有所有前期准备已经ok 准备使用hook抓包看能否抓到包~

### objection动态分析 & Hook socket抓包

1. objection 动态分析, 搜索 类 android hooking search classes protobuf

- 复制系统库保存为txt文件 执行脚本加上hook

| 1234567891011121314 | `# 读取文件并处理``with` `open``(``'my_protobuf.txt'``,` `'r'``,encoding``=``'utf-8'``) as` `file``:``lines` `=` `file``.readlines()``processed_lines` `=` `[]``for` `line` `in` `lines:``# 进行处理操作``processed_line` `=` `"android hooking watch class "` `+` `line``# 将处理后的行插入到原来的列表中``processed_lines.append(processed_line)` `# 将处理后的内容按行插入到原文件中``with` `open``(``'my_protobuf_new.txt'``,` `'w'``,encoding``=``'utf-8'``) as` `file``:``for` `processed_line` `in` `processed_lines:``file``.write(processed_line)` |
|-|-|
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_HDRJ6JVWKDSHYMR.png)

2. 所有的输出信息如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687 | `com.xuexiang.protobufdemo on (google:` `8.1``.``0``) [usb]` `# (agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.toBuilder()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke)` `(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke)` `(agent) [``33h1vvf01vb``] Called com.google.protobuf.UnknownFieldSetLite.getDefaultInstance()``(agent) [r44a6fapyp] Called com.google.protobuf.GeneratedMessageLite$Builder.mergeFrom(com.google.protobuf.GeneratedMessageLite)` `(agent) [r44a6fapyp] Called com.google.protobuf.GeneratedMessageLite$Builder.copyOnWrite()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.visit(com.google.protobuf.GeneratedMessageLite$Visitor, com.google.protobuf.GeneratedMessageLite)` `(agent) [flxqngw0jns] Called com.google.protobuf.GeneratedMessageLite$MergeFromVisitor.visitString(boolean, java.lang.String, boolean, java.lang.String)` `(agent) [flxqngw0jns] Called com.google.protobuf.GeneratedMessageLite$MergeFromVisitor.visitUnknownFields(com.google.protobuf.UnknownFieldSetLite, com.google.protobuf.UnknownFieldSetLite)` `(agent) [``33h1vvf01vb``] Called com.google.protobuf.UnknownFieldSetLite.getDefaultInstance()``(agent) [r44a6fapyp] Called com.google.protobuf.GeneratedMessageLite$Builder.copyOnWrite()``(agent) [r44a6fapyp] Called com.google.protobuf.GeneratedMessageLite$Builder.build()``(agent) [r44a6fapyp] Called com.google.protobuf.GeneratedMessageLite$Builder.buildPartial()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.makeImmutable()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke)` `(agent) [``33h1vvf01vb``] Called com.google.protobuf.UnknownFieldSetLite.makeImmutable()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.isInitialized()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke, java.lang.``Object``)` `(agent) [``4fnnhkno676``] Called io.grpc.protobuf.lite.ProtoLiteUtils$MessageMarshaller.stream(java.lang.``Object``)``(agent) [``4fnnhkno676``] Called io.grpc.protobuf.lite.ProtoLiteUtils$MessageMarshaller.stream(com.google.protobuf.MessageLite)` `(agent) [t74uyknf3ri] Called io.grpc.protobuf.lite.ProtoInputStream.available()``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeStringSize(``int``, java.lang.String)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeTagSize(``int``)``(agent) [``75uwxvix9zw``] 【【【Called com.google.protobuf.WireFormat.makeTag(``int``,` `int``)】】】``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeUInt32SizeNoTag(``int``)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeStringSizeNoTag(java.lang.String)``(agent) [``78m3ko66u48``] Called com.google.protobuf.Utf8.encodedLength(java.lang.CharSequence)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeLengthDelimitedFieldSize(``int``)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeUInt32SizeNoTag(``int``)``(agent) [t74uyknf3ri] Called io.grpc.protobuf.lite.ProtoInputStream.drainTo(java.io.OutputStream)``(agent) [pi8dc23shb] 【【【Called com.google.protobuf.AbstractMessageLite.writeTo(java.io.OutputStream)】】】``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computePreferredBufferSize(``int``)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.newInstance(java.io.OutputStream,` `int``)``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeString(``int``, java.lang.String)` `(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeTag(``int``,` `int``)``(agent) [``75uwxvix9zw``] 【【【Called com.google.protobuf.WireFormat.makeTag(``int``,` `int``)】】】``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeUInt32NoTag(``int``)``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.flushIfNotAvailable(``int``)``(agent) [``032rofd4w0eb``] Called com.google.protobuf.CodedOutputStream$AbstractBufferedEncoder.bufferUInt32NoTag(``int``)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.access$``100``()``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeStringNoTag(java.lang.String)` `(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.computeUInt32SizeNoTag(``int``)``(agent) [``78m3ko66u48``] 【【【Called com.google.protobuf.Utf8.encode(java.lang.CharSequence, [B,` `int``,` `int``)】】】``(agent) [yozcy0715w] Called com.google.protobuf.Utf8$SafeProcessor.encodeUtf8(java.lang.CharSequence, [B,` `int``,` `int``)``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeUInt32NoTag(``int``)``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.flushIfNotAvailable(``int``)``(agent) [``032rofd4w0eb``] Called com.google.protobuf.CodedOutputStream$AbstractBufferedEncoder.bufferUInt32NoTag(``int``)``(agent) [``4gz3lfvhznc``] Called com.google.protobuf.CodedOutputStream.access$``100``()``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.writeLazy([B,` `int``,` `int``)``(agent) [``2ira22725rq``] 【【【Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.write([B,` `int``,` `int``)】】】``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.flush()``(agent) [``2ira22725rq``] Called com.google.protobuf.CodedOutputStream$OutputStreamEncoder.doFlush()``(agent) [``4fnnhkno676``] Called io.grpc.protobuf.lite.ProtoLiteUtils$MessageMarshaller.parse(java.io.InputStream)``(agent) [``4fnnhkno676``] Called io.grpc.protobuf.lite.ProtoLiteUtils$MessageMarshaller.parse(java.io.InputStream)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.newInstance([B,` `int``,` `int``)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.newInstance([B,` `int``,` `int``, boolean)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.pushLimit(``int``)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.recomputeBufferSizeAfterLimit()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.setSizeLimit(``int``)``(agent) [``4fnnhkno676``] Called io.grpc.protobuf.lite.ProtoLiteUtils$MessageMarshaller.parseFrom(com.google.protobuf.CodedInputStream)` `(agent) [``6thpuwhq0js``] Called com.google.protobuf.AbstractParser.parseFrom(com.google.protobuf.CodedInputStream, com.google.protobuf.ExtensionRegistryLite)` `(agent) [``6thpuwhq0js``] Called com.google.protobuf.AbstractParser.parseFrom(com.google.protobuf.CodedInputStream, com.google.protobuf.ExtensionRegistryLite)` `(agent) [b7ksjxdkr9] Called com.google.protobuf.GeneratedMessageLite$DefaultInstanceBasedParser.parsePartialFrom(com.google.protobuf.CodedInputStream, com.google.protobuf.ExtensionRegistryLite)` `(agent) [b7ksjxdkr9] Called com.google.protobuf.GeneratedMessageLite$DefaultInstanceBasedParser.parsePartialFrom(com.google.protobuf.CodedInputStream, com.google.protobuf.ExtensionRegistryLite)` `(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.parsePartialFrom(com.google.protobuf.GeneratedMessageLite, com.google.protobuf.CodedInputStream, com.google.protobuf.ExtensionRegistryLite)` `(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke)` `(agent) [``33h1vvf01vb``] Called com.google.protobuf.UnknownFieldSetLite.getDefaultInstance()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.readTag()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.isAtEnd()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.readRawVarint32()``(agent) [``75uwxvix9zw``] Called com.google.protobuf.WireFormat.getTagFieldNumber(``int``)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.readStringRequireUtf8()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.readRawVarint32()``(agent) [``78m3ko66u48``] Called com.google.protobuf.Utf8.isValidUtf8([B,` `int``,` `int``)``(agent) [sa0emcwxaha] Called com.google.protobuf.Utf8$Processor.isValidUtf8([B,` `int``,` `int``)``(agent) [yozcy0715w] Called com.google.protobuf.Utf8$SafeProcessor.partialIsValidUtf8(``int``, [B,` `int``,` `int``)``(agent) [yozcy0715w] Called com.google.protobuf.Utf8$SafeProcessor.partialIsValidUtf8([B,` `int``,` `int``)``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.readTag()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.isAtEnd()``(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.tryRefillBuffer(``int``)``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.makeImmutable()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke)` `(agent) [``33h1vvf01vb``] Called com.google.protobuf.UnknownFieldSetLite.makeImmutable()``(agent) [``6thpuwhq0js``] Called com.google.protobuf.AbstractParser.checkMessageInitialized(com.google.protobuf.MessageLite)` `(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.isInitialized()``(agent) [e48kca70yae] Called com.google.protobuf.GeneratedMessageLite.dynamicMethod(com.google.protobuf.GeneratedMessageLite$MethodToInvoke, java.lang.``Object``)` `(agent) [``34xbsz3uxgl``] Called com.google.protobuf.CodedInputStream.checkLastTagWas(``int``)` |
|-|-|
3. hook `com.google.protobuf.Utf8.encode(java.lang.CharSequence, [B, int, int)`

- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_NP88DC7QGZDZ224.png)

4. 使用frida hook socket 结果如下

- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_3ZSFTM5NWSBSMUC.png)
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_JRMTEJ7V3GC9V2X.png)
- ![image](https://bbs.kanxue.com/upload/attach/202308/900788_PQ2KWRHDPWTQQP6.png)

>
> 至此全部完结~
> 以上就是最近几天学习内容,接下来研究研究Java具体如何实现的，争取学会还原tag来实现无proto文件反解析出数据.
>
>
>

上传的附件：
- LearningProtobufDem0.7z

（5.49kb，26次下载）

---

# 回复

## 回复 by 哇哈哈919 (#3)

*2023-8-3 14:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  铭濠笙科技](https://bbs.kanxue.com/user-983177.htm)
>
>  能给我解密一下吗？协议protobuf
>
>

是违法app的话我可以试着学习一下如何解密,若是正规app就算了。
目的是学习~![image](https://bbs.kanxue.com/view/img/face/87.gif)

## 回复 by 小海CC (#5)

*2023-8-30 09:42*

标题protobuf拼错了

## 回复 by 哇哈哈919 (#6)

*2023-8-30 16:39*

>
> [小海CC](https://bbs.kanxue.com/user-878857.htm)
>
>  标题protobuf拼错了
>
>

谢谢老哥提醒！
