---
title: '[原创]libmsaoaidsec.so Frida检测、反调与绕过实战'
url: https://bbs.kanxue.com/thread-290658.htm
tid: 290658
author: x0rrrrr
date: '2026-04-05'
tags: [Android安全, 原创, 基础理论, 逆向分析, 脱壳反混淆, HOOK注入, 源码框架]
crawled_at: '2026-08-08T10:12:42+00:00'
replies: 120
---

# 一、前言

学习了frida检测原理后，打算找个样本练手。起初是仿照着东方玻璃师傅的文章复现，但是在找最后一个检测点遇到了一些阻碍，导致最后一个执行流没找出来所以暂且先放放。后来在误打误撞下发现了一个新的样本，该样本有不少检测，故借此样本分析一下。最终完成检测的绕过，以及其中各类检测方法实现的分析还原。

## 声明

1. 本文所述内容仅为技术研究与学习交流之目的, 所分析的 App 版权归其所属公司所有
2. 作者未对任何 App 进行非法篡改, 破解, 数据窃取或商业利用, 亦不鼓励或支持任何违反法律法规的行为
3. 读者不得将本文内容用于任何非法用途, 由此产生的一切法律责任由使用者自行承担
4. 请遵守《中华人民共和国网络安全法》及相关法律法规

## 文章知识点

阅读这篇文章，可能能让你掌握这些知识点：

- 检测点的定位思路
- `pthread_create`函数调用链
- 一些反调试、反frida的手段

# 二、检测点定位

首先就是检测点定位，这里直接使用两种方式进行`frida`注入的测试。这里直接使用frida的纯交互模式进行测试：

```bash
frida -U -f com.douban.frodo
\```

进入frida之后，发现frida马上就退出了，而程序正常运行： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_3NT6BRCYFF8J354.webp)

说明可能在某些so，或者子线程当中会有检测，接下来在app成功运行的情况下，使用`attach`进行附加，发现等待几秒钟后app直接退出， 退出之后app又重新启动了： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_BH9RKCYPA4HDE89.webp)

那么已经可以推测出来，这个app在子线程当中一定有对frida的检测。接下来需要定位一下这个这个检测点到底在哪里，这里对`dlopen`进行hook，脚本如下：

```js
function frida_check(){
    function hook_dlopen(addr){
        Interceptor.attach(addr,{
            onEnter: function(args){
                this.path = "";
                this.soPath = args[0];
                if(this.soPath !== null && this.soPath !== undefined){
                    this.path = this.soPath.readCString();
                    console.log("\x1b[96m[dlopen onEnter]\x1b[0m " + this.path);
                }
            }, onLeave:function(retval){
                if(this.path !== null && this.path !== undefined){
                    console.log("\x1b[92m[dlopen onLeave]\x1b[0m " + this.path);
                }
            }
        });
    }

    console.log("[+] 开始定位 frida 检测位置");
    var android_dlopen_ext = Module.findExportByName("libdl.so","android_dlopen_ext");
    hook_dlopen(android_dlopen_ext);
}
frida_check();
\```

在`onEnter`和 `onLeave`的位置输出一下提示，由于这个frida检测是通过退出自己的进程来打断frida注入的话，那么这个过程中检测的so可能会有下面的**行为特征：**

- 只有`onEnter`的输出，没有`onLeave`的输出，说明可能在这个so加载的过程中就检测到然后退出了。
- 有这两个位置都有输出，但是没有了其他so加载的输出提示，进程也退出了。

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_9Z7EQRNVVP7BJBX.webp)经过hook发现，进行检测的地方在这个`libmsaoaidsec.so`的so当中。而且可以看到的是在`dlopen onLeave`之前，这个进程就已经退出了，可以初步判断这个检测的位置大致是在`init_proc`，`init_array`执行过程当中，**因为`JNI_Onload`的调用时机是在`dlopen`之后**，所以需要对这个so当中的`init_proc`和`init_array`进行主要分析

# 三、so分析

确定了目标，就可以开始着手分析了。这里将so从apk当中取出来后，丢到IDA，接着想要通过段来找到`init_array`，这个结构，但是这个so有点不同，只有这三个段 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_WGH859KU8MZ3YSZ.webp)这里直接在IDA View窗口搜索：能够搜到 `DT_INIT`，`DT_INIT_ARRAY`，对应的就是`.init_proc`，`.init_array`了。

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_R9F8ZVNRCVHT9PS.webp)

这里为了快速定位到究竟是`.init_proc`还是`.init_array`当中的某个函数检测并退出进程的，就直接对`call_function`进行hook，将对应的函数偏移答应出来，如果遇到**只进不出的**就说明是在这个函数当中进行了检测行为了。对应的hook代码如下：

```js
function frida_check(){
    function hook_call_function(){
        if(isHook) return;
        isHook = true;
        var symbols = Process.getModuleByName("linker64").enumerateSymbols();
        var call_function = null;
        for(let i = 0; i < symbols.length; i++ )
        {
            var symbol = symbols[i];            if(symbol.name.indexOf("__dl__ZL13call_functionPKcPFviPPcS2_ES0_.__uniq.331521225453620004837736674378903349473") != -1)    // call_function
            {
                call_function = symbol.address;
                break;
            }
        }
        console.log("call function: ",call_function);
        Interceptor.attach(call_function,{
            onEnter: function(args){
                this.realpath = args[2].readCString();
                if(this.realpath.indexOf("libmsaoaidsec.so") !== -1){
                    this.base = Process.getModuleByName("libmsaoaidsec.so").base;
                    this.addr = args[1];
                    console.log("\x1b[96m[call Function onEnter]\x1b[0m " + ptr(this.addr).sub(this.base));
                }
            },onLeave: function(retval){
                if(this.realpath.indexOf("libmsaoaidsec.so") !== -1){
                    console.log("\x1b[92m[call Function onEnter]\x1b[0m " + ptr(this.addr).sub(this.base));
                }
            }
        });
    }
    function hook_dlopen(addr, soName){
        Interceptor.attach(addr,{
            onEnter: function(args){
                this.path = "";
                this.soPath = args[0];
                if(this.soPath !== null && this.soPath !== undefined){
                    this.path = this.soPath.readCString();
                    if(this.path.indexOf(soName) !== -1) hook_call_function();
                    console.log("\x1b[96m[dlopen onEnter]\x1b[0m " + this.path);
                }
            }, onLeave:function(retval){
                if(this.path !== null && this.path !== undefined){
                    console.log("\x1b[92m[dlopen onLeave]\x1b[0m " + this.path);
                }
            }
        });
    }
    console.log("[+] 开始定位 frida 检测位置");
    var android_dlopen_ext = Module.findExportByName("libdl.so","android_dlopen_ext");
    hook_dlopen(android_dlopen_ext,"libmsaoaidsec.so");
    var isHook = false;
}

frida_check();
\```

运行之后，发现是在这个`0x14400`函数退出进程的，因为并没有从这个函数`onLeave`，也就是检测在这个`.init_proc`函数当中。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_G455XM2GSMWBUYN.webp)

如果后续想要更进一步的了解这个so的检测的话就需要这个`.init_proc`进行深度分析了。这里先不深入进行分析，上面定位检测点的时候猜测是有通过**子线程进行检测的**，这里可以先尝试对`pthread_create`，进行hook，然后替换掉线程函数，看看能否绕过再说。

# 四、子线程绕过

结合上述的分析结果可以判断，也是有子线程检测的。还有一种可能是，在`.init_proc`当中启动的子线程检测。这里就先尝试一下，通过替换子线程的线程函数来看看能否绕过检测。而想要对子线程的线程函数进行替换，就需要先找到到底是使用了哪一个函数，而想要做到这一步，就需要对`pthread_create`这个函数进行hook。既然提及到了这个`pthread_create`，那么顺带的也来整理一下这个函数的调用链，以及是怎么调用线程函数的。

## pthread_create调用链分析

Android分析有一点好处就是可以直接对照着源码，再和IDA的反编译进行比对分析。那么首先就先进行源码的分析。（源码可以使用在线网站，这里使用的是[XRefAndroid - Support Android 16.0 & OpenHarmony 6.0 (AndroidXRef/AospXRef)](https://xrefandroid.com/)）

### 函数声明

```cpp
int pthread_create(
    pthread_t* thread_out,           // 输出参数，返回新线程的线程句柄
    pthread_attr_t const* attr,      // 线程属性，传 NULL 表示默认属性
    void* (*start_routine)(void*),   // 线程函数
    void* arg                        // 线程函数参数
);
\```

### 相关结构体

- **`pthread_attr_t`**

```c
typedef struct {
  uint32_t flags;			// 标志位
  void* stack_base;			// 栈基址
  size_t stack_size;		// 栈大小
  size_t guard_size;		// 保护页大小
  int32_t sched_policy;		// 调度策略
  int32_t sched_priority;	// 调度优先级

#ifdef __LP64__
  char __reserved[16];		// 64位下的保留字段，用于对齐
#endif
} pthread_attr_t;
\```

**`pthread_internal_t`**

```cpp
class pthread_internal_t {
 public:
  class pthread_internal_t* next;			// 指向上一个线程环境块
  class pthread_internal_t* prev;			// 指向下一个线程环境块

  pid_t tid;			// 线程ID

 private:
  uint32_t cached_pid_ : 31;			// 高31位缓存PID
  uint32_t vforked_ : 1;				// 最后1位标记这个线程是否通过vfork()创建的

 public:
  bool is_vforked() { return vforked_; }

  // ==========================================================
  // 3. PID/TID 缓存管理方法
  // ==========================================================
  pid_t invalidate_cached_pid() {
    pid_t old_value;
    get_cached_pid(&old_value);
    set_cached_pid(0);
    return old_value;
  }

  void set_cached_pid(pid_t value) {
    cached_pid_ = value;
  }

  bool get_cached_pid(pid_t* cached_pid) {
    *cached_pid = cached_pid_;
    return (*cached_pid != 0);
  }

  // ==========================================================
  // 4. 线程基本属性与状态
  // ==========================================================
  pthread_attr_t attr;						// 线程基本属性

  _Atomic(ThreadJoinState) join_state;

  __pthread_cleanup_t* cleanup_stack;

  void* (*start_routine)(void*);			// 函数指针，这个线程的执行函数
  void* start_routine_arg;					// 函数参数指针
  void* return_value;						// 线程函数返回值
  sigset64_t start_mask;

  void* alternate_signal_stack;

  // ==========================================================
  // 5. 安全防护机制 (Shadow Call Stack - 针对 ARM64)
  // ==========================================================
  void* shadow_call_stack_guard_region;

  uintptr_t stack_top;

  _Atomic(bool) terminating;

  // ==========================================================
  // 6. 同步与内存管理
  // ==========================================================
  Lock startup_handshake_lock;

  void* mmap_base;
  size_t mmap_size;

  void* mmap_base_unguarded;
  size_t mmap_size_unguarded;
  char vma_name_buffer[32];

  // ==========================================================
  // 7. 线程局部存储 (TLS) 与错误处理
  // ==========================================================
  thread_local_dtor* thread_local_dtors;

  char* current_dlerror;
#define __BIONIC_DLERROR_BUFFER_SIZE 512
  char dlerror_buffer[__BIONIC_DLERROR_BUFFER_SIZE];

  bionic_tls* bionic_tls;

  int errno_value;
};
\```

在这个`pthread_internal_t`当中，对于找线程函数来说比较重要的就是这几个成员，他们的名称以及结构体偏移大致如下：

- `start_routine`：线程函数地址，偏移为0x60
- `start_routine_arg`：线程函数的参数，偏移为0x68
- `return_value`：线程函数的返回值，偏移为0x70

### 调用链分析

有了上面的了解之后就能够来分析`pthread_create`的调用链了。这个函数可以在源码当中的`/bionic/libc/bionic/pthread_create.cpp`当中找到： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_47S76S48MWPUU57.webp)

`pthread_create`首先会调用`__allocate_thread`将新线程所需要的内存空间申请好，并且划分不同的功能区。然后返回`tcb`指针，后续会通过tcb来获取`pthread_internal_t*`指针。接着就是对`thread`进行初始化，包括线程回调函数，以及函数参数的初始化。

完成上述准备之后，就进入到了最关键的一步，调用`clone`：以当前进程为模板，克隆出来一个新的执行流。这里需要注意的这几个参数：参数一(`__pthread_start`)，参数四(`thread`)。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_5AYSX2T4AVTU49H.webp)

跟进函数，继续分析： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_3RF25T3XGR8JX88.webp)

可以看到函数声明：`fn`就是`__pthread_start`，`arg`就是`thread`，接着往下分析：下面会判断`fn`是否为空，如果有值则调用`__bionic_clone`，来进行系统调用进行创建线程。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_3SXBKNH45NSQPXP.webp)

到这里会发现无法跟进`__bionic_clone`，这里需要配合ida来分析`libc.so`代码。首先在`libc.so`的`clone`当中找到调用`__bionic_clone`的位置，标记一下参数传递所使用的寄存器。这里标记了几个比较重要的参数： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_FMJ44FY6BMJDFZ2.webp)

这里是对照着源码的参数进行标记的。完成后进入`__bionic_clone`进行分析，汇编代码分析如下 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_ZV67APR3W6M7E3F.webp)这里系统调用之后如果返回的是子线程的空间的话，sp已经变成了子线程的栈帧。然后回进入`__start_thread`这个函数当中。此时`x0`是`pthread_start`的函数地址，`x1`是结构体地址。

接着继续看看`__start_thread`这个函数作用是什么。在这个函数当中，我们主要关注的是`thread`和`phread_start`相关的寄存器即可。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_7H6FDAGKZTASBYK.webp)

最后会调用`pthread_start`这个函数。这个函数可以在源码当中看到是什么情况： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_AZNXQ2JR2TZG9R6.webp)

可以看到传入的`arg`参数就是`thread`，接着会在后面调用`thread`当中的回调函数，也就是`pthread_create`传入的回调函数地址。综上所述，`pthread_create`的调用链大致如下（在其他不同版本的设备中可能会不太一样）：

```bash
pthread_create --> clone --> __bionic_clone  --> __start_thread ---> pthread_start
\```

而且在这个分析过程中可以发现，有非常多的点可以通过`pthread_internal_t`结构体拿到对应的线程函数，例如`clone`，`__bionic_clone`，`__start_thread`等函数当中。有了上面的知识就可以来试试找出**通过创建线程来检测frida的函数**在哪里了。

## 获取线程函数及绕过

有了上面的知识就可以通过frida来写脚本，获取线程函数地址了：

```js
var pthread_hooked = false;
function hook_pthread_create(soName){
    if(pthread_hooked) return;
    pthread_hooked = true;
    var pthread_create = Module.findExportByName("libc.so","pthread_create");
    console.log("pthread_create addr : ",pthread_create);
    var observer = Interceptor.attach(pthread_create,{
        onEnter: function(args){
            this.thread_func_addr = args[2];
            if(this.thread_func_addr !== null && this.thread_func_addr !== undefined){
                var module = Process.findModuleByAddress(this.thread_func_addr);
                if(module.name.indexOf(soName) !== -1){
                    console.log(`pthread_create thread func : ${module.name} +\x1b[38;5;208m0x${(this.thread_func_addr - module.base).toString(16)}\x1b[0m`);
                }
            }
        }, onLeave:function(retval){}
    });
}
hook_pthread_create("libmsaoaidsec.so");
\```

以**Spawn**方式注入，输出如下，可以发现能够找到对应so当中相关的线程函数了。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_KHFMGVARTRP96XA.webp)

接着就来试一下将这三个函数给替换掉

```js
var pthread_hooked = false;
function hook_pthread_create(soName){
    if(pthread_hooked) return;
    pthread_hooked = true;
    var pthread_create = Module.findExportByName("libc.so","pthread_create");
    console.log("[*] pthread_create addr : ",pthread_create);
    Interceptor.attach(pthread_create,{
        onEnter: function(args){
                this.thread_func_addr = args[2];
                if(this.thread_func_addr !== null && this.thread_func_addr !== undefined){
                    var module = Process.findModuleByAddress(this.thread_func_addr);
                    if(module.name.indexOf(soName) !== -1){
                        let offset = this.thread_func_addr - module.base;
                       if (offset == 0x26E5C) {
                            args[2] = fake_thread_26E5C;
                            console.log("[replace] sub_26E5C -> fake_thread_26E5C");
                        } else if (offset == 0x1B8D4) {
                            args[2] = fake_thread_1B8D4;
                            console.log("[replace] sub_1B8D4 -> fake_thread_1B8D4");
                        } else if (offset == 0x1C544) {
                            args[2] = fake_thread_1C544;
                            console.log("[replace] sub_1C544 -> fake_thread_1C544");
                        }
                    }
                }
        }, onLeave:function(retval){}
    });
}

var fake_thread_26E5C = new NativeCallback(function (arg) {
    console.log("[fake_thread_26E5C] called, arg =", arg);
    return ptr(0);
}, 'pointer', ['pointer']);

var fake_thread_1B8D4 = new NativeCallback(function (arg) {
    console.log("[fake_thread_1B8D4] called, arg =", arg);
    return ptr(0);
}, 'pointer', ['pointer']);

var fake_thread_1C544 = new NativeCallback(function (arg) {
    console.log("[fake_thread_1C544] called, arg =", arg);
    return ptr(0);
}, 'pointer', ['pointer']);
\```

只不过替换线程函数之后就进程就直接崩溃了，命令行当中也打印了**崩溃转储信息**（这个可能需要多重复操作几次才会打印）： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_VHB9XCZAHT6F3XF.webp)

通过转储信息可以看到一个是`fault addr = 0x000b0202000015b2`，另一个是`backtrace`，当中的调用堆栈。现在就需要去IDA当中通过调用堆栈回溯一下发生这种问题的点可能在哪里。

## 解决崩溃问题

在IDA当中直接跳转到`0x20d10`的位置： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_9TZQ2JPXW3J8P6E.webp)

可以看到这里是将`W8`，这个寄存器当中的值存放到`x20+0x188`的位置，通过转储信息可以看到此时的 `x20 = 000b02020000142a`而加上`0x188`之后就是这个`fault addr`了，那么此时需要找到这个`x20`，到底是从哪里来的。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_Y42J6FATXQTW3T9.webp)

这里将x20高亮一下，然后再函数开头发现是从这个 **`[X8,#off_4B728@PAGEOFF]`** 中取出来的，接着找这个标签： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_GJG5445SWGCNZGF.webp)

最后发现是调用了`sub_2082C`这个函数的返回值。现在得分析一下这个`sub_2082C`这个函数到底是做什么的： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_TP5BYZWKE7J42X9.webp)

进来看到好几个带有`linker64`的字符串，接着就是 `.symtab`，`.strtab`，`solist` ![image](https://bbs.kanxue.com/upload/attach/202604/999665_2JW7JEMP3PV3V8D.webp) ![image](https://bbs.kanxue.com/upload/attach/202604/999665_VD7VTDDNMSZEUFT.webp)

根据这些特征猜测这个函数是解析elf，根据`solist`这个符号获取solist的结构，用ai分析了一下确实是：**通过解析 linker64 的 ELF 符号表，定位 Android linker 内部的 solist 全局变量，从而拿到当前进程加载模块链表的头指针。**

那么接下来hook一下这个函数，看看返回值是什么：

```js
function hook_sub_2082C(target, offset){
    if(!target) return;
    console.log(`[hooked] sub_2082C is hooked`);
    Interceptor.attach(target, {
        onEnter: function(args){
            console.log(`\x1b[38;5;208m[sub_2082C onEnter]\x1b[0m`);
        }, onLeave:function(retval){
            console.log(`\x1b[93m[sub_${offset.toString(16)} onLeave]\x1b[0m retval --> ${retval.toString(16)}`);
        }
    })
}
\```

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_MK9GXCNJH3R8M4Q.webp)

通过对代码流程分析可以得出：如果这个函数返回值为0的话，就不会执行到`0x20D10`的位置，这里将返回值改为 0，验证 `solist/soinfo` 路径是否参与检测，顺便hook一下调用`sub_2082C`的函数，有没有正常退出(`onLeave`)。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_853PMMCENWY6DSG.webp)

这个`sub_20bdc`就是上层的函数，可以看到能够正常退出了，而且很惊喜的发现这个`dlopen`也成功的退出了，则就说明剩下的`init_array`没有检测函数了。可惜这里的进程还是退出了，这里hook了一下`JNI_OnLoad`，发现`JNI_Onload`能够正常退出，但是进程仍然退出，并且也没有新的so加载，那么可能就是在java层调用了检测函数了： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_VB483USH7C4VMSC.webp)

到这里就不再细究java层了。经过资料查找发现，有不少app都有使用了这个so来进行检测，这里找到最新版的某艺进行测试，依旧是使用一模一样的frida脚本，然后进行hook，发现是可以完成Frida的注入的： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_6B9NZV9XMXSW4BT.webp)

可以发现是能够注入了。

# 五、思路总结

在以前旧版本的检测当中，只需要将启动线程的函数`replace`即可，但是在新版当中由于线程相关逻辑缺失，导致某个后续流程使用了未初始化/无效状态。在进行了nop这个线程函数，或者是替换线程函数的情况下，需要再另外对目标函数进行处理。满足以上两点才能够进行frida的检测绕过

# 六、混淆手段

这个so当中主要的混淆手段就是ollvm，还有就是字符串的加密，以及`ShellCode`的加密及使用。ollvm就不需要说了，这里就来讲讲后面两种：

## 字符串加密

这里找到一段反编译后的代码看看： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_QYV5ECF5UFH52R6.webp)

大致的特征就是这种：先计算长度，然后异或解密这种。这种特征貌似不只是在这个so当中出现过，之前分析壳的时候好像也见过类似的。**解决办法：** 目前针对这种解密字符串没想到有什么比较好的方法，只能一个个写脚本解密。有比较好的想法的师傅可以指点一下

## ShellCode使用

可能会有的师傅会想通过hook `exit`这类函数来定位一下进程是在哪里退出的。恐怕这个想法实现不了（可以试一下，主包这里没试过）。这里拿一个检测函数当中调用的退出函数看看：

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_87VURU582N9PCEU.webp)

这里会先对数据进行异或解密，解密手法就是之前字符串的解密方法，然后通过mmap将解密出来的机器码拷贝到这个 **`RWX`** 的匿名内存当中，然后通过函数指针调用这个`ShellCode`，而这段`ShellCode`解密脚本以及反汇编之后的效果如下：

```python
enc = [ 0x91, 0xA7, 0x29, 0x4B, 0xA6, 0xA9, 0x99, 0x73, 0x69, 0x9A,
  0xF8, 0x7F, 0x86, 0x87, 0xAA, 0x4C, 0xB8, 0x89, 0x9A, 0x72,
  0xB6, 0xB9, 0xA4, 0x7C, 0x86, 0x87, 0xAA, 0x4C]
code = []
key = [0x99,0xa7,0xa9]

for i in range(len(enc)):
    code.append(enc[i] ^ key[i % 3])

code_1 = code[0] | (code[1] << 8) | (code[2] << 16) | (code[3] << 24)
code_1 += 3008
code[0] = code_1 & 0xFF
code[1] = (code_1 >> 8) & 0xFF
code[2] = (code_1 >> 16) & 0xFF
code[3] = (code_1 >> 24) & 0xFF

from capstone import*
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
for insn in md.disasm(bytes(code),0x1000):
    print(f"0x{insn.address:x}:\t{insn.mnemonic}\t{insn.op_str}")
\```

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_7747BAYXHEG5BFN.webp)

可以看到这个ShellCode直接通过系统调用，结束整个进程。所以hook exit这类函数的方法可能行不通

# 七、检测思路

那么既然已经绕过了Frida的检测，现在可以来好好看看这个`so`当中使用到的检测手法了。这里拿了几个出来分析，如果有兴趣的话可以自己分析一下其他的。

## 线程函数

那么首当其冲的肯定就是通过创建线程来进行检测的函数了。分别有以下三个：

```bash
0x1C544
0x1B8D4
0x26E5C
\```

这里我对`0x1b8d4`做了一个比较详细的分析，`0x26e5c`，`0x1c544`大致粗略看了一下。

### sub_1b8d4

这个函数进入之后看起来还是很清爽的，代码如下（这里是已经分析过，然后修复了不少函数名，变量名的结果）： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_HXCUBWACFEMN9P9.webp)

大致就是通过`get_tracePID`来获取`TracerPid`，来检测是否处于调试状态。另外一个就是通过`check_stat()`来判断线程状态是否是`T (stopping)`，挂起状态。如果是的话就会退出循环，然后进程退出。来看看这个`tracePid`的获取方法： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_NDBV5PK8JPTVNJY.webp) ![image](https://bbs.kanxue.com/upload/attach/202604/999665_8GZ8YMDPGF4JVTX.webp)

就是通过打开`proc/self/status`这个文件，然后取出`TracePid`，这个字段的值。这里的字符串通过反编译能看到都不是硬编码，基本上都是加密的。这个问题后面再说。`check_stat`这个函数原理大致也差不多，这里就不展开了。所以这个线程函数其实是**通过TracePid和stat**，来反调试。

### sub_26E5C

接下来就是26E5C这个函数了。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_TWANMFDDEDTXUUK.webp)

进来首先是一个小型的ollvm，重点只有这个部分，如果`sub_1678c`返回值最低位为0的话，就会走到这个`exit_0`当中，接着看看这个`sub_1678c` ![image](https://bbs.kanxue.com/upload/attach/202604/999665_WST4GU72P3ZSXTQ.webp)

发现是打开了`/proc/self/maps`这个文件，然后就是获取maps当中的`start_addr`等信息进行检测，这里不再赘述。分析方法就是先按照上面混淆手段提及到的字符串解密，将字符串解密之后就会比较容易分析了。

### sub_1C544

进入后发现很多字符串解密的位置，解密了头几个后发现这些特征：`gum-js-loop`，`gmain`，`linjector`....这种很明显就是frida特征了，猜测这个线程函数主要就是进行的frida检测。 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_MHMWFBJ6EU6HJ5P.webp) ![image](https://bbs.kanxue.com/upload/attach/202604/999665_TXRQBS7PWU54S9M.webp) ![image](https://bbs.kanxue.com/upload/attach/202604/999665_WD38BPKZ4Q7EC5M.webp)

## 其他检测函数

### sub_23AD4

这个函数是在init_proc当中的，功能就是用来检测模拟器： ![image](https://bbs.kanxue.com/upload/attach/202604/999665_7MG5YQKZVVR327B.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202604/999665_X6X4VSSS5Z9XGZP.webp)通过`maps`，查看是否有`x86`这种路径的模块，这种模块路径一般是在模拟器当中

## 检测总结

这个so当中检测的手法远不止于此，还有类似adb检测，crc完成性检测等等，但是对这些函数进行hook之后发现并没有调用，也就没有写出来了。感兴趣的可以去看看

# 参考

- [[原创]某加固新版frida检测绕过-trace一把嗦-Android安全-看雪安全社区｜专业技术交流与安全研究论坛](https://bbs.kanxue.com/thread-289545.htm)
- [frida检测对抗————libmsaoaidsec.so绕过 - 吾爱破解 - 52pojie.cn](https://www.52pojie.cn/thread-2079166-1-1.html)
- [【某瓣app逆向】第一期：【frida反调试检测】 针对性绕过的分析&实现_哔哩哔哩_bilibili](https://www.bilibili.com/video/BV1gd7GzLEEM/?spm_id_from=333.788.videopod.sections&amp;vd_source=41dcc8f32a8b1a7d0d3bf0169a2dadaf)

---

# 回复

## 回复 by FMNS (#2)

*2026-4-5 18:30*

6666

## 回复 by tonykros (#3)

*2026-4-5 20:38*

666

## 回复 by mb_ldbucrik (#4)

*2026-4-5 20:39*

感谢分享

## 回复 by 我今年6岁 (#5)

*2026-4-5 21:17*

感谢分享

## 回复 by Imxz (#6)

*2026-4-6 08:56*

rbq

## 回复 by wx_妳还是不懂 (#7)

*2026-4-6 20:24*

非常感谢

## 回复 by 小迷糊ddd (#8)

*2026-4-6 22:47*

感谢分享，认真学习。

## 回复 by mb_uktygsmq (#9)

*2026-4-6 23:44*

666

## 回复 by 七浪 (#10)

*2026-4-7 10:22*

从 SO 里定位检测逻辑再到 Frida 绕过的过程写得很清楚，这类实战拆解比只看结论更有参考价值，感谢分享。

## 回复 by pingsky (#11)

*2026-4-7 10:57*

666

## 回复 by 中文fjja (#12)

*2026-4-7 12:37*

谢谢分享

## 回复 by iBa0 (#13)

*2026-4-7 15:04*

123

## 回复 by mb_cezterwx (#14)

*2026-4-7 16:10*

666666

## 回复 by LQ6H (#15)

*2026-4-7 17:12*

666

## 回复 by wx_Huber Barrientos (#16)

*2026-4-8 13:05*

谢谢分享

## 回复 by bluegatar (#17)

*2026-4-8 23:58*

这个so被干透了

## 回复 by x0rrrrr (#18)

*2026-4-9 10:54*

>
> [bluegatar](https://bbs.kanxue.com/user-352825.htm)
>  这个so被干透了
>

是的![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by wx_星儿 (#19)

*2026-4-9 12:21*

非常感谢

## 回复 by 红皮西瓜 (#20)

*2026-4-9 13:47*

1111

## 回复 by win柠初 (#21)

*2026-4-10 11:44*

好东西 来看看

## 回复 by lackone (#22)

*2026-4-11 11:55*

66666

## 回复 by mb_iyozxdcx (#23)

*2026-4-12 02:06*

感谢分享

## 回复 by 毛毛毛毛虫 (#24)

*2026-4-12 11:38*

学习一下

## 回复 by devil_1 (#25)

*2026-4-12 15:35*

666

## 回复 by 上官兮唐 (#26)

*2026-4-12 15:53*

看看

## 回复 by 菜鸟逆向 (#27)

*2026-4-13 07:25*

![image](https://bbs.kanxue.com/view/img/face/001.gif)看看

## 回复 by wx_Lyq (#28)

*2026-4-13 10:08*

666

## 回复 by 外交 (#29)

*2026-4-13 19:08*

666666666

## 回复 by 溜溜菜 (#30)

*2026-4-14 17:14*

666

## 回复 by git_86302JokerXsh (#31)

*2026-4-15 10:18*

666666

## 回复 by xuhe123 (#32)

*2026-4-15 13:05*

6666

## 回复 by GEKEZYX (#33)

*2026-4-15 13:50*

666

## 回复 by huangjw (#34)

*2026-4-15 14:01*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by r0k (#35)

*2026-4-15 14:22*

谢谢分享

## 回复 by cx52038 (#36)

*2026-4-15 21:13*

666

## 回复 by mb_jhohnbzu (#37)

*2026-4-16 11:24*

666

## 回复 by mb_vgzccfwq (#38)

*2026-4-16 14:06*

6666

## 回复 by mb_kuqpxncc (#39)

*2026-4-16 15:57*

666

## 回复 by cpannn (#40)

*2026-4-17 20:54*

xuexi le

## 回复 by mb_fsoesckx (#41)

*2026-4-18 02:10*

感谢分享

## 回复 by 飆汗吉米 (#42)

*2026-4-18 02:53*

666

## 回复 by mb_agxdcibq (#43)

*2026-4-18 12:26*

666

## 回复 by kingking888 (#44)

*2026-4-18 14:59*

666

## 回复 by 东方玻璃 (#45)

*2026-4-18 21:40*

好文,今天逆这个so用到了师傅的思路![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by x0rrrrr (#46)

*2026-4-18 23:27*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>  好文,今天逆这个so用到了师傅的思路[em_056]
>

感谢东方师傅的认可![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 小尘0000 (#47)

*2026-4-22 16:11*

666

## 回复 by ldehua (#48)

*2026-4-23 11:41*

感谢分享

## 回复 by mb_uohfzjqw (#49)

*2026-4-23 13:01*

666

## 回复 by TeamAR (#50)

*2026-4-24 10:33*

666

## 回复 by wx_刘建辉 (#51)

*2026-4-24 14:56*

我想看看后面怎么解决的

## 回复 by mb_yeeclamm (#52)

*2026-4-24 15:19*

1

## 回复 by wfjun (#53)

*2026-4-24 19:38*

,666

## 回复 by mb_rirvdrlh (#54)

*2026-4-24 20:49*

66666666666666

## 回复 by x0rrrrr (#55)

*2026-4-25 17:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_刘建辉](https://bbs.kanxue.com/user-898874.htm)
>  我想看看后面怎么解决的
>

什么后面怎么解决的

## 回复 by 牛爷爷啊 (#56)

*2026-4-25 22:08*

厉害，学习下！

## 回复 by scllqk (#57)

*2026-4-26 10:16*

学习

## 回复 by AK1988DA (#58)

*2026-4-26 10:37*

7

## 回复 by LuisY (#59)

*2026-4-28 11:56*

66

## 回复 by LuisY (#60)

*2026-4-28 11:56*

66

## 回复 by Snowman_Liam (#61)

*2026-4-28 12:08*

666

## 回复 by Snowman_Liam (#62)

*2026-4-28 12:08*

6666

## 回复 by LuisY (#63)

*2026-4-28 12:22*

我走到了leave JNI_OnLoad 阶段之后 还是会Process terminated ， 这个应该是Java层做了检测 ， 但是Java层的检测需要怎么绕过，有相关教程不

## 回复 by x0rrrrr (#64)

*2026-4-28 12:26*

>
> [LuisY](https://bbs.kanxue.com/user-1000037.htm)
>  我走到了leave JNI_OnLoad 阶段之后 还是会Process terminated ， 这个应该是Java层做了检测 ， 但是Java层的检测需要怎么绕过，有相关教程不
>

我这一部分没有进行后续研究了。不过感觉可以从java加载这个so的位置入手往下分析看看java层的代码。

## 回复 by 4Chan (#65)

*2026-4-28 15:28*

学习一下

## 回复 by huangbof (#66)

*2026-4-28 23:20*

数来定位一下进程是在哪里退出

## 回复 by huangbof (#67)

*2026-4-28 23:20*

数来定位一下进程是在哪里退出

## 回复 by huangbof (#68)

*2026-4-28 23:20*

数来定位一下进程是在哪里退出

## 回复 by oscar99999 (#69)

*2026-4-29 08:19*

666666

## 回复 by oscar99999 (#70)

*2026-4-29 08:20*

666666![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by oscar99999 (#71)

*2026-4-29 08:21*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by mb_ugnawvja (#72)

*2026-4-29 09:35*

感谢分享

## 回复 by mb_ugnawvja (#73)

*2026-4-29 09:35*

感谢分享

## 回复 by mb_ugnawvja (#74)

*2026-4-29 09:36*

感谢分享

## 回复 by mb_ugnawvja (#75)

*2026-4-29 09:36*

感谢分享

## 回复 by 伊苏尔德 (#76)

*2026-4-29 16:44*

123

## 回复 by 伊苏尔德 (#77)

*2026-4-29 16:44*

123213

## 回复 by 伊苏尔德 (#78)

*2026-4-29 16:44*

666

## 回复 by 伊苏尔德 (#79)

*2026-4-29 16:44*

555

## 回复 by git_86585flowclouds (#80)

*2026-4-30 00:53*

学习一下

## 回复 by mb_cviyuksx (#81)

*2026-4-30 14:04*

666

## 回复 by mb_hztwvrcw (#82)

*2026-5-4 08:49*

学习一下

## 回复 by 总有些想学 (#83)

*2026-5-8 09:48*

感谢分享

## 回复 by fancy繁星 (#84)

*2026-5-8 16:30*

666

## 回复 by mb_lzsjiukj (#85)

*2026-5-8 20:32*

感谢分享

## 回复 by 秃顶 (#86)

*2026-5-9 00:20*

666

## 回复 by yuniao (#87)

*2026-5-12 11:10*

666

## 回复 by Zepp7289 (#88)

*2026-5-12 11:23*

tql

## 回复 by mb_dmjhowok (#89)

*2026-5-13 11:39*

666

## 回复 by Andy_877594 (#90)

*2026-5-14 15:54*

看看

## 回复 by 小若渴jh (#91)

*2026-5-15 03:13*

66666

## 回复 by mb_stdlrcgp (#92)

*2026-5-15 14:25*

666

## 回复 by magicianlz (#93)

*2026-5-15 17:33*

你的分享对大家帮助很大，非常感谢！

## 回复 by 宛枫 (#94)

*2026-5-16 00:37*

感谢分享

## 回复 by 086Love (#95)

*2026-5-18 11:39*

学习

## 回复 by wx_kaka_141 (#96)

*2026-5-18 17:25*

1

## 回复 by wx_哈哈哒 (#97)

*2026-5-20 14:26*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by A0tem (#98)

*2026-5-20 16:57*

![image](https://bbs.kanxue.com/view/img/face/076.gif)

## 回复 by 海带 (#99)

*2026-5-21 14:32*

66666

## 回复 by DevilHunter (#100)

*2026-5-23 00:15*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_lhxrckiu (#101)

*2026-5-28 14:21*

看看

## 回复 by git_74197luban110 (#102)

*2026-6-1 16:49*

666

## 回复 by mb_czqyztmr (#103)

*2026-6-10 14:22*

666

## 回复 by mb_otoynfkv (#104)

*2026-6-10 14:36*

>
> [devil_1](https://bbs.kanxue.com/user-969875.htm)
>  666
>

nice

## 回复 by yangshuang (#105)

*2026-6-18 10:11*

666

## 回复 by mb_kgneopde (#106)

*2026-6-24 11:21*

666

## 回复 by Da_ (#107)

*2026-6-25 09:54*

tql

## 回复 by wx_余生_771 (#108)

*2026-6-25 16:54*

学习一下

## 回复 by mb_ajxntfzc (#109)

*2026-6-28 03:09*

666

## 回复 by mb_cbgtaveo (#110)

*2026-7-7 14:51*

66666

## 回复 by mb_qkfqehfw (#111)

*2026-7-19 03:03*

666

## 回复 by Vengeance (#112)

*2026-7-22 18:49*

6666

## 回复 by mb_gjhmacqd (#113)

*2026-7-23 00:05*

666

## 回复 by mb_pmnukjhq (#114)

*2026-7-23 00:38*

666

## 回复 by Yuuuual (#115)

*2026-7-23 13:32*

学习记录，感谢分享

## 回复 by Elliot_Lin (#116)

*2026-7-23 17:11*

感谢分享

## 回复 by ShriyGo (#117)

*2026-7-24 10:40*

111

## 回复 by 阿文hx (#118)

*2026-7-25 02:27*

666

## 回复 by wx_steve (#119)

*2026-7-25 10:29*

1

## 回复 by mb_uulqeyon (#120)

*2026-7-25 14:14*

1

## 回复 by 亦心柚 (#121)

大佬好强
