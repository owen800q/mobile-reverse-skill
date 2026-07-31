---
title: '[原创]btrace：binder_transaction+eBPF+Golang实现通用的Android APP动态行为追踪工具'
url: https://bbs.kanxue.com/thread-281895.htm
tid: 281895
author: nullnu
date: '2024-05-26'
tags: [Android安全, 原创, 源码框架, 系统相关, HOOK注入, 逆向分析]
crawled_at: '2026-07-31T14:26:45+08:00'
replies: 10
---

# btrace：binder_transaction+eBPF+Golang实现通用的Android APP动态行为追踪工具

## 一、简介：

    在进行Android恶意APP检测时，需要进行自动化的行为分析，一般至少包括行为采集和行为分析两个模块。其中，行为分析有基于规则、基于机器学习、基于深度学习甚至基于大模型的方案，各有各的优缺点，不是本文关注的重点，本文主要关注Android APP的动态行为采集。在做Android APP逆向分析时经常需要通过hook系统调用观察APP的行为，也需要一个动态行为追踪工具。

    btrace（<https://github.com/null-luo/btrace>）就是一个开源的针对Android APP的动态行为采集/追踪工具。目标是**通用**、**可靠**、**简单**。如果类比到Linux tracing systems的话，我们的工具也可以分成三部分：data sources我们的方案是kprobe/binder_transaction；way to extract data我们采用eBPF；frontends我们使用Golang。

![image](https://bbs.kanxue.com/upload/attach/202405/607459_9SPASYDH9VUAMNJ.webp)

    接下来分别介绍这三个部分的方案。

## 二、data sources：kprobe/binder_transaction

    binder是Android IPC的核心机制，Android APP在访问系统服务的时候，实际上就是在进行跨进程通信，因此，监控binder就可以获取到APP调用系统服务的行为。

    之前已有帖子介绍了在kernel层进行监控和拦截的优势：[https://bbs.kanxue.com/thread-279725.htm](https://bbs.kanxue.com/thread-279725.htm，这)，这里就不再重复说明了，我们重点看一下在kernel层的哪个函数做监控比较好。我们的目标是要获取：APP的包名、调用服务名、调用函数名、调用参数。![image](https://bbs.kanxue.com/upload/attach/202405/607459_2YA5UJJA7XBQHU7.webp)

    首先想到的是内核已经定义的tracepoint：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_AKHC6JE59EY4BEC.webp)

    可惜大部分tracepoint都没有带上binder核心数据的指针，也就是没有办法获取到目标服务名和函数参数：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_9XYQFTYR3ESBUJY.webp)

    只有binder_ioctl这个tracepoint里面的arg指向的是struct binder_write_read：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_HAD45K8QTA6EVYB.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_PW4WUBR24QZUYUT.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_SEREA2BZAHAJA4E.webp)

    但问题是struct binder_write_read相当的原始，解析起来比较复杂：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_WSM8EBGSCSBDJDY.webp)

    这是因为binder_ioctl是链路上kernel层的第一个函数，传进来的数据还没有经过处理。那么，我们能不能找一找binder_ioctl后面的函数，尽可能让系统对数据进行解析和处理之后我们直接拿到想要的字段呢？

    我们把binder_ioctl->binder_ioctl_write_read->binder_thread_write->binder_transaction这条调用链分析了一下，发现binder_transaction是一个比较合适的点，在它之前的函数已经对用户层传入的数据进行了很多解析和过滤，这里拿到的数据是struct binder_transaction_data，相对比较简单了：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_TAN7BW7M3XTG49B.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_DC6HACUUTH5F5B2.webp)

    其实，仔细看binder_transaction函数的代码可以发现，本来通过binder_debug和trace_binder_transaction这两个地方直接拿到数据是最方便的，可惜的是binder_debug没有输出code（调用函数的编号），trace_binder_transaction又没有输出调用服务名和参数的数据指针。导致没有办法直接使用这两个点。

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_TXVGB7CHC6REEE7.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_T5TENWRKXBKW57E.webp)

    尤其是trace_binder_transaction，如果往后一点放到内存拷贝（user->kernel）完成之后，再将数据指针输出的话就非常完美了。

所以，最后我们还是回到对binder_transaction这个内核函数进行监控，解析参数struct binder_transaction_data来拿到数据的方案。

## 三、way to extract data：eBPF

    eBPF是一个运行在Linux内核里面的虚拟机组件，它可以在无需改变内核代码或者加载内核模块的情况下，安全而又高效地拓展内核的功能。是一种非侵入性的内核函数hook方法。

    并且，Google 为了解决 Android 碎片化提出了GKI（通用内核镜像），要求Android 12以上版本的设备出厂必须使用GKI内核，而且GKI内核的编译选项把eBPF相关的功能都是打开的。

    所以eBPF特别适合用于对Android设备中Linux内核函数的监控。

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_ETM3SBHWWWZG7UQ.webp)

    binder_transaction函数总共5个参数，我们可以根据第4个参数来过滤掉回应的transaction，只关注请求的transaction：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_DV93NR6HAVEYSPF.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_P7HFDPSR43P9X9G.webp)

    我们的目标是要获取：APP的包名、调用服务名、调用函数名、调用参数这几个字段：

- APP的包名可以通过当前UID来获取（因为binder_transaction函数是在client的进程内）；
- 调用函数名可以通过binder_transaction_data->code来获取；
- 调用服务名和调用参数可以通过binder_transaction_data->data.ptr.buffer来获取；

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_D9QSHSC5NWDN9QH.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_RF6V9DVRE7A7E3J.webp)

    其中要注意的是，binder_transaction_data->data.ptr.buffer指向的数据目前还在用户空间，还没有完成向内核空间的拷贝，所以需要使用bpf_probe_read_user函数。（这就是我上节说的如果把trace_binder_transaction往后移到内存拷贝之后，并且把内核空间的数据地址输出，那就完美了，可惜！）：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_6Q77AH6FB6DN2AD.webp)

## 四、frontend：Golang

    eBPF的核心程序一般是使用C语言编写，clang进行编译后，需要将其加载到内核中。目前有多个项目对eBPF的编写调试运行的流程进行了封装和优化，比如bcc、libbpf等，我们选择的是cilium/ebpf。

    它封装了BPF系统调用，与内核提供的libbpf类似，区别在于这个库是Go语言的，更加方便进行用户态程序的开发，而且外部依赖少，与此同时其还提供了bpf2go工具，可用来将eBPF程序编译成Go语言中的一部分，使得交付更加方便。也就是说很容易将项目编译为一个独立可运行的ELF文件。

    我们的开发环境是Ubuntu arm64的虚拟机（主机是Mac）：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_8FFZUFHFRMEY3YB.webp)

    cilium/ebpf使用起来非常方便，整个框架分为三个部分：

- 运行在内核态用C写eBPF代码，llvm编译为eBPF字节码；
- 用户态使用Golang编写，cilium/ebpf纯go类库，做eBPF字节码的内核加载，kprobe HOOK对应函数；
- 用户态使用Golang做事件读取、解码、处理。

    我们在内核态程序里将需要的数据放到ringbuf里传递给用户态：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_X6BAKWV55VMPS88.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/JZS8GJMBTHQF5S8.jpg)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_N59RAZRKV3KXJHT.webp)

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_CAJ96X3NNN2MRZS.webp)

    用户态程序收到数据后做处理：

    1、APP的包名

    知道UID后执行命令"pm list packages -U"去查一下就能知道：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_U3TSSBPH862WYWE.webp)

    2、调用函数名、调用服务名、调用参数

    Android进程间通信基于Proxy与Stub的设计模式，AIDL是Android接口定义语言，在写完AIDL文件后，编译器自动生成一个同名的.java文件，里面包含Stub和Proxy两个类，Stub类是服务端抽象层的体现。Proxy的接口供客户端程序调用，然后它内部会把信息包装好，通过binder传递给Stub，而后者通过对应的接口作用于服务端系统，从而完成了“远程调用”。

    先来看看Proxy的代码，红色对应的就是要调用函数的编号，也就是binder_transaction_data->code。蓝色就是要调用的服务的接口名，绿色部分则是要调用函数的参数，可以看出来这两部分被打包到一个Parcel里面去，对应的就是binder_transaction_data->data.ptr。最后通过transact函数将以上三部分内容往binder传递。

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_CWGQ9HP6FDUAC9A.webp)

    writeInterfaceToken函数在写入接口名之前，还写了12字节（4+4+4）的其他数据：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_XKHEHEFDG67UT3H.webp)

    我们在解析的时候先跳过头部12字节，接下来的4字节代表接口名字符串的长度，接着的数据即是接口名字符串：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_RSFKWDUJ2RCSNQ2.webp)

    最后，看一下binder_transaction_data->code如何转换成函数名，仔细分析了binder流程代码，函数名在编译.aidl文件的时候就已经转换成code了，之后一直传递的都是code，直到服务端的onTransact函数里才根据code去选择函数：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_R4DDKWNZSK52XGP.webp)

    所以在整个binder数据传输的过程中都找不到合适的hook点，后来偶然发现.aidl文件自动生成的Stub类里面有getTransactionName、getDefaultTransactionName这么两个函数可以根据函数编码获取到函数名，那么我们就可以使用反射来获取函数名：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_EGHPV9YX54569JA.webp)

    顺手在Android代码里搜索了一下这两个函数，发现有一个类已经将对getDefaultTransactionName的调用包装好了：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_5HGX9KXBGC5F786.webp)

    但是在golang里面不太好调用Android的API，所以换了一个思路，写了一个Android APP，利用反射把系统服务下所有的transactionCode和methodName的映射关系记录下来，输出给btrace在运行时候查询：

    ![image](https://bbs.kanxue.com/upload/attach/202405/607459_TU8F2NRWYDZGWR9.webp)

    有几个注意点：

- 系统所有的服务名可以通过service list获取：

        ![image](https://bbs.kanxue.com/upload/attach/202405/607459_93AKMCJK9SHQDW2.webp)

- 需要打开策略开关才能访问hide的API：adb shell settings put global hidden_api_policy 1。
- 每一个服务内transaction函数一般是从1开始逐个编号的，而且每个函数对应一个field，所以我们获取服务类的field数目就知道此类最多有多少个transaction函数需要我们尝试去获取名字：

![image](https://bbs.kanxue.com/upload/attach/202405/607459_AHNWV8GAY6NTQ2A.webp)

        ![image](https://bbs.kanxue.com/upload/attach/202405/607459_FRCKXUFQWSCBCQF.webp)

    最后效果（参数的解析暂不支持）：

![image](https://bbs.kanxue.com/upload/attach/202405/607459_BNKTVJSHF34Q76F.webp)

## 五、总结：

    我们使用binder_transaction+eBPF+Golang来实现一个针对Android APP的动态行为追踪工具，目标是**通用**、**可靠**、**简单**。

- 通用：基于binder底层内核函数，可以监控到所有API调用，覆盖系统版本广泛；
- 可靠：基于eBPF，对内核无侵入，并且有验证器的验证，安全可靠；
- 简单：基于Golang作为frontend，灵活高效，逻辑简单清晰，外部依赖少，单一ELF可独立运行。

btrace项目地址：<https://github.com/null-luo/btrace>

---

# 回复

## 回复 by huangjw (#2)

*2024-5-26 14:20*

赞， 有golang，也要python

## 回复 by mb_rjdrqvpa (#3)

*2024-5-26 17:28*

佬，这个工具怎么编译使用？方便发布一个可执行文件吗？

## 回复 by 你瞒我瞒 (#4)

*2024-5-27 09:37*

巨佬这个工具如何编译，可以分享下在那些环境下需要什么环境的lib的支持和编译开发流程不

## 回复 by artake (#5)

*2024-6-3 16:08*

太牛逼了

## 回复 by 天堂猪0ink (#6)

*2024-6-3 18:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  佬，这个工具怎么编译使用？方便发布一个可执行文件吗？
>
>

需要配ebpf相关环境，用golang编译的，详情可以查看cilium/ebpf项目相关文档

## 回复 by mb_dejwmbmm (#7)

*2024-6-3 21:49*

????

## 回复 by nullnu (#8)

*2024-6-9 13:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rjdrqvpa](https://bbs.kanxue.com/user-932635.htm)
>
>  佬，这个工具怎么编译使用？方便发布一个可执行文件吗？
>
>

已发布到github上

## 回复 by nullnu (#9)

*2024-6-9 13:02*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  巨佬这个工具如何编译，可以分享下在那些环境下需要什么环境的lib的支持和编译开发流程不
>
>

已更新到github上

## 回复 by 你瞒我瞒 (#10)

*2024-6-11 09:34*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  nullnu](https://bbs.kanxue.com/user-607459.htm)
>
>  已更新到github上
>
>

感谢感谢

## 回复 by mb_xeayhfep (#11)

*2024-8-15 15:38*

在反射时有些service会报classnotfound的错误该怎么解决呢？后面的参数解析思路应该是怎么样的
