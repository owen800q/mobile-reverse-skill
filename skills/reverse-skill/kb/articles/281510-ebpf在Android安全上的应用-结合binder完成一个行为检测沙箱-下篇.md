---
title: '[原创]ebpf在Android安全上的应用：结合binder完成一个行为检测沙箱(下篇)'
url: https://bbs.kanxue.com/thread-281510.htm
tid: 281510
author: windy_ll
date: '2024-04-24'
tags: [Android安全, 原创, 工具脚本]
crawled_at: '2026-07-31T14:28:16+08:00'
replies: 6
---

# ebpf在Android安全上的应用：结合binder完成一个行为检测沙箱(下篇)

## 一、IPC简单介绍

 **IPC是Inter-Process Communication的缩写，含义为进程间通信或者跨进程通信，是指两个进程之间进行数据交换的过程。**

 **Android在什么时候会有跨进程通信的需要？Android在请求系统服务的时候会有跨进程通信的需求，例如访问手机通讯录、获取定位等等行为，本文的目标即是实现一个简易的捕捉这些行为的沙箱**

---

## 二、binder简单介绍

 **Binder是Android中的一种跨进程通信方式，可以理解为是IPC的一种具体实现方式**

---

## 三、ServiceManager简单介绍

 **`ServiceManager`是Android中一个及其重要的系统服务，从它的名称上就可以知道，它是用于管理系统服务的**

 **`ServiceManager`由`init`进程启动**

 **`ServiceManager`负责了以下的一些功能：服务的注册与查找、进程间通信、系统服务的启动与唤醒、提供系统服务的清单实例**

 **`binder`驱动决定了底层的通信详情，那么`ServiceManager`则相当于导航，告诉具体的通信该怎么走，达到那里等**

---

## 四、通信分析

### 4.1 客户端调用JAVA层分析

 **以`WifiManager`类的`getConnectInfo`函数(该函数获取wifi信息)为例进行分析**

 **`ctrl+左键`查看引用，可以发现该函数定义在`android.net.wifi.WifiManager`类中，如下图所示：**

![7.png](https://bbs.kanxue.com/upload/attach/202404/851220_U2W9TG826WQU5MM.png)

![8.png](https://bbs.kanxue.com/upload/attach/202404/851220_YQPNBJEYAE8UQ24.png)

 **从上图可以看到，`getConnectInfo`函数具体代码只有一句`throw new RuntimeException("Stub!");`，这告诉我们这个函数是由rom中相同的类去替代执行，该函数在这被定义是编译所需要(PS:可以参考<https://blog.csdn.net/ttkatrina/article/details/76180641>)，在android源码中的目录`frameworks/base/wifi/java/amdroid/net/wifi`下我们可以找到该类，然后找到该函数的具体实现，如下图所示：**

![9.png](https://bbs.kanxue.com/upload/attach/202404/851220_G8BZS3FCKNYY4FK.png)

 **可以发现该函数调用了`IWifiManager`的`getConnectionInfo`函数，在`frameworks/base/wifi/java/amdroid/net/wifi`目录下可以找到`IWifiManager.aidl`文件，该aidl中定义了`getConnectionInfo`函数，如下图所示：**

![10.png](https://bbs.kanxue.com/upload/attach/202404/851220_2XWJK7SK6CMEWFC.png)

![11.png](https://bbs.kanxue.com/upload/attach/202404/851220_XZ5MSRU27CEZVU5.png)

 **这里需要引入一个概念 --- `AIDL`，`AIDL`是android的一种接口语言，用于公开android服务的接口，以此来实现跨进程的函数调用。`AIDL`在编译时会生成两个类，即`Stub`和`Proxy`两个类，`Stub`类是服务端抽象层的体现，`Proxy`是客户端获取的实例，android通过`proxy-stub`这种设计模式实现了IPC**

 **下面写一个aidl文件然后生成相应的java代码来看看是怎么实现调用的，首先，我们在android studio中随便找一个项目，然后新建一个aidl文件，如下图所示：**

![12.png](https://bbs.kanxue.com/upload/attach/202404/851220_Y9UPKM3CQNENRYK.png)

![13.png](https://bbs.kanxue.com/upload/attach/202404/851220_DAASEJ5KMHU4NY6.png)

 **然后`Build->Make Probject`即可生成，生成的路径位于`build/generated/aidl_source_output_dir/debug/out/包名`，如下图所示：**

![14.png](https://bbs.kanxue.com/upload/attach/202404/851220_2UC5AP7KMYYYJER.png)

 **观察生成后的java文件可发现，`Proxy`类已经生成，在`Proxy`类中我们可以找到我们定义的函数，如下图所示：**

![15.png](https://bbs.kanxue.com/upload/attach/202404/851220_Y45T93WSQCUTVR3.png)

 **具体分析一下该函数，首先通过`obtain`函数生成了一个`Parcel`实例，然后调用`Parcel`的`write`系列函数进行写入，其实就是一个序列化的过程，然后调用了`IBinder`的`transact`函数，跟踪分析一下该函数，在目录`frameworks/base/core/java/android/os`下可以找到该java文件，如下图所示：**

![16.png](https://bbs.kanxue.com/upload/attach/202404/851220_GNFZDQ6FV6SH4DD.png)

![17.png](https://bbs.kanxue.com/upload/attach/202404/851220_9J3GCXZUT6BKFSS.png)

 **可以发现，`IBinder`仅仅是一个接口，其中定义了`transact`方法，该方法有4个参数，第一个参数`code`在我们的远程调用中为函数编号，服务端接受到这个编号后，会去寻找`Stub`类中的静态变量，从而解析出是调用那个函数，第二个和第三个参数`_data`、`_reply`为传入的参数和返回的值，都是经过序列化后的数据，最后一个参数`flags`为指示是否需要阻塞等待结果，0为阻塞等待，1为立即返回。**

 **全局搜索一下，可以发现同目录下的`BinderProxy`类实现了该接口(PS:值得注意的是，同目录下面还存在一个`Binder`类，也实现了该接口，但`Binder`类是服务端的实现，而不是客户端的实现)，如下图所示：**

![18.png](https://bbs.kanxue.com/upload/attach/202404/851220_5BAUN64EAS6NK7F.png)

![19.png](https://bbs.kanxue.com/upload/attach/202404/851220_MAT7S2QFG4N8XWV.png)

 **分析该函数，可以发现最后走向了`transactNative`函数，到此为止，进行IPC通信客户端java层已经分析完毕**

![20.png](https://bbs.kanxue.com/upload/attach/202404/851220_ZUDQGQUNWZD39Q2.png)

### 4.2 客户端调用Native层分析

 **全局搜索一下`transactNative`函数，可以发现该函数在native层中注册信息，如下图所示：**

![21.png](https://bbs.kanxue.com/upload/attach/202404/851220_MQ9X9YDSHGSYQPD.png)

 **跟踪一下`android_os_BinderProxy_transact`函数，可以发现该函数首先通过`getBPNativeData(env, obj)->mObject.get()`获取到了一个`BpBinder`对象，然后调用了`BpBinder`的`transact`函数，如下图所示：**

![22.png](https://bbs.kanxue.com/upload/attach/202404/851220_7NQUQVTGWGMC38D.png)

![23.png](https://bbs.kanxue.com/upload/attach/202404/851220_RBNJ2XPV8TPZRHU.png)

 **继续跟进下去，可以发现进入了`IPCThreadState`的`transact`函数，如下图所示：**

![24.png](https://bbs.kanxue.com/upload/attach/202404/851220_WT3G72CTRKAMS4K.png)

 **接着跟进，可以发现首先调用`writeTransactionData`函数，该函数作用为填充`binder_transaction_data`结构体，为发送到binder驱动做准备，然后调用`waitForResponse`等待返回，如下图所示：**

![25.png](https://bbs.kanxue.com/upload/attach/202404/851220_BF2DF6UEHYAPZKZ.png)

![26.png](https://bbs.kanxue.com/upload/attach/202404/851220_H4FBNPFF4HND4V5.png)

![27.png](https://bbs.kanxue.com/upload/attach/202404/851220_RAR63A9YK726SQV.png)

 **跟进`waitForResponse`函数，可以发现该函数最重要的就是调用`talkWithDriver`函数，分析一下`talkWithDriver`函数，可以发现最终调用了`ioctl`，如下图所示：**

![28.png](https://bbs.kanxue.com/upload/attach/202404/851220_NRCVZDW845N6R6Z.png)

![29.png](https://bbs.kanxue.com/upload/attach/202404/851220_XRU5MYTZHXETFKY.png)

 **到处为止，客户端native层分析完毕**

### 4.3 内核层分析(binder驱动分析)

 **到此处，我们的ebpf程序就可以开始捕捉然后解析数据格式了**

 **当用户层调用`ioctl`时，会进入内核态，进入`binder_ioctl`内核函数(ps:可在内核设备源码中的`binder.c`找到相应的描述符)，分析一下`binder_ioctl`函数，可发现该函数主要作用为在两个进程之间首发数据，我们的通信数据`ioctl`命令是`BINDER_WRITE_READ`，当遇到该命令的时候，会调用`binder_ioctl_write_read`函数，如下图所示：**

![30.png](https://bbs.kanxue.com/upload/attach/202404/851220_6W5JG9A68TU7SDH.png)

![31.png](https://bbs.kanxue.com/upload/attach/202404/851220_PMKF98ZPYEG4QD7.png)

 **跟进`binder_ioctl_write_read`函数，可以发现，该函数首先将`unsigned long`类型的`arg`参数指向的地址的值读取到结构体`binder_write_read`中，说明当`ioctl`命令为`BINDER_WRITE_READ`时，传递进来的参数为指向结构的`binder_write_read`的指针，如下图所示：**

![32.png](https://bbs.kanxue.com/upload/attach/202404/851220_B3CBBEZVVRCHM92.png)

 **到这里其实我们内核态的分析已经可以结束了，我们已经观察到了我们想要的数据了，即`binder_write_read`结构体，可以看一下该结构体的定义，如下所示：**

| 12345678 | `struct` `binder_write_read {``binder_size_t write_size;` `/* 写内容的数据总大小 */``binder_size_t write_consumed;` `/* 记录了从缓冲区读取写内容的大小 */``binder_uintptr_t write_buffer;` `/* 写内容的数据的虚拟地址 */``binder_size_t read_size;` `/* 读内容的数据总大小 */``binder_size_t read_consumed;` `/* 记录了从缓冲区读取读内容的大小 */``binder_uintptr_t read_buffer;` `/* 读内容的数据的虚拟地址 */``};` |
|-|-|

 **这个结构体是用来描述进程间通信过程中所传输的数据，我们读取从客户端发送到服务端的通信包只需要关注`write_size`、`write_consumed`、`write_buffer`，其中，`write_buffer`指向的是一个数组，这个数组中就包含了`binder_transaction_data`结构体，这个结构体在native层`writeTransactionData`函数填充的，我们的目标通信包即是这个结构体，其中，`write_buffer`和`read_buffer`指向的数据结构大致如下：**

![33.png](https://bbs.kanxue.com/upload/attach/202404/851220_KBDYAQC4GWMBSNK.png)

 **一般来说，驱动会一次性传递多条命令和地址的组合，而我们要在其中找到`binder_transaction_data`结构体对应的指令，在`binder.h`头文件中我们可以找到驱动定义的所有指令(<https://android.googlesource.com/kernel/common/+/refs/heads/android-mainline/include/uapi/linux/android/binder.h>)，如下图所示：**

![34.png](https://bbs.kanxue.com/upload/attach/202404/851220_DCAY58VY8TTVFBP.png)

 **可以发现，`BC_TRANSACTION`和`BC_REPLY`指令都对应着`binder_transaction_data`结构体参数，但我们只需要客户端发往驱动的数据包，所以我们只需要`BC_TRANSACTION`指令对应的参数即可**

 **经过上面的分析，我们找到了我们需要的核心数据---`binder_transaction_data`结构体，现在来看一下该结构体的定义，定义如下：**

| 1234567891011121314151617181920 | `struct binder_transaction_data {``union {``__u32 handle;``binder_uintptr_t ptr;``} target;` `/``*` `该事务的目标对象` `*``/``binder_uintptr_t cookie;` `/``*` `只有当事务是由Binder驱动传递给用户空间时，cookie才有意思，它的值是处理该事务的Server位于C``+``+``层的本地Binder对象` `*``/``__u32 code;` `/``*` `方法编号` `*``/``__u32 flags;``pid_t sender_pid;``uid_t sender_euid;``binder_size_t data_size;` `/``*` `数据长度` `*``/``binder_size_t offsets_size;` `/``*` `若包含对象，对象的数据大小` `*``/``union {``struct {``binder_uintptr_t` `buffer``;` `/``*` `参数地址` `*``/``binder_uintptr_t offsets;` `/``*` `参数对象地址` `*``/``} ptr;``__u8 buf[``8``];``} data;` `/``*` `数据` `*``/``};` |
|-|-|

 **有了该数据结构，我们就可以知道客户端调用服务端的函数的函数、参数等数据了**

---

## 五、实现效果

 **PS：整套系统用于商业，就不做开源处理了，这里只给出核心结构体打印的截图，就不再发前端的截图了**

**读取手机通讯录(ps:这里读取出来的数据采用了Toast打印的，所以将捕捉到的Toast相应的通信包也一起打印了出来，下同)：**

![1.png](https://bbs.kanxue.com/upload/attach/202404/851220_SDUT97XWM9SC22B.png)

![2.png](https://bbs.kanxue.com/upload/attach/202404/851220_T2FJTBFMPUDSRNB.png)

**获取地理位置：**

![3.png](https://bbs.kanxue.com/upload/attach/202404/851220_DURZ6499WF6KQJW.png)

![4.png](https://bbs.kanxue.com/upload/attach/202404/851220_JJC66858EVJVY7E.png)

**获取wifi信息：**

![5.png](https://bbs.kanxue.com/upload/attach/202404/851220_PENE7JMZYHUYDYQ.png)

![6.png](https://bbs.kanxue.com/upload/attach/202404/851220_HNKFHDSTU372W4E.png)

---

## 六、其他

 **上面其实我们只分析到了发送部分，反过来，其实我们也可以读取返回包甚至于修改返回包，就可用于对风控的对抗，例如在内核态中修改APP请求的设备标识信息(当然前提是app走系统提供的驱动通信)，亦或者用于逆向的工作，例如过root检测等等。**

 **这部分验证代码就暂不放出来了，感兴趣的可以自己实现一下**

---

# 回复

## 回复 by 秋狝 (#2)

*2024-4-25 09:17*

感谢分享

## 回复 by 雨之后 (#3)

*2024-4-25 14:13*

我选择修改binder驱动

## 回复 by Amun (#4)

*2024-4-25 15:44*

tracepoints 里就一个 `trace_binder_ioctl(cmd, arg)` 适合使用的，应该改 binder 驱动，多加点 trace_binder_xxxx。

## 回复 by 万里星河 (#5)

*2024-4-26 11:13*

"跟进waitForResponse函数，可以发现该函数最重要的就是调用talkWithDriver函数，分析一下talkWithDriver函数，可以发现最终调用了ioctl"
根据原文的这句话 是否可以认为 拦截ioctl系统调用就可以监听所有的binder通信

## 回复 by 天水姜伯约 (#6)

*2025-5-2 13:55*

无敌！！！！！

## 回复 by 万里星河 (#7)

*2025-8-24 16:53*

重温经典
