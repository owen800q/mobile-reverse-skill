---
title: '[原创]QTrace：基于QBDI的高稳定，高定制的trace工具'
url: https://bbs.kanxue.com/thread-290574.htm
tid: 290574
author: 乐子人
date: '2026-03-31'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析, 协议分析, 混淆加固, 程序开发, HOOK注入, 源码框架]
crawled_at: '2026-08-08T10:15:34+00:00'
replies: 210
---

# QTrace：基于QBDI的高稳定，高定制的trace工具

现在的混淆越来越恶心了，平坦化+间接跳转已经是标配。传统的单步调试早已难以招架，去混淆在面对多层间接跳转+编译优化时也显得力不从心。于是逆向分析中很多时候需要借助trace工具来辅助。

目前主流的trace工具有三种：

- Unidbg：使用范围广，上手简单。问题是需要补环境，有时候需要补充大量环境才能勉强跑通。就算跑通了，也因为是模拟执行，存在大量数据与真机数据不一致的问题。
- stalker：frida配套的trace工具，稳定性较差，经常各种崩溃。不过最近有大佬开源了[GumTrace](https://bbs.kanxue.com/thread-290400.htm)，在稳定性上提升了许多。
- qbdi：qbdi是基于动态重编译技术的插桩工具。具体原理可参考：[QBDI原理详解](https://bbs.kanxue.com/thread-289884.htm)

qbdi的优点是稳定+真机trace。缺点是上手复杂，需要自己引入编译qbdi相关的库。

QTrace封装了qbdi库，并修复了虚拟栈崩溃bug，优化了日志系统，引入了灵活的自定义监控框架等，可以方便逆向工作者更好的定制自己的trace工具。

QTrace为android studio项目，主要开发语言为C/C++。逆向工作者需要在使用中根据自己的实际需要来修改c++代码。

最终会编译生成libnativelib.so，注入这个so到目标进程将会自动实现hook和trace功能。

## QTrace

项目地址：<https://github.com/zgy0x01/QTrace>

### 主要功能

- 安卓arm64真机指令trace，内存读写监控
- 自定义函数插桩监控
- 自定义libc，jni函数插桩监控
- 使用轻量级hook框架[shadowhook](https://github.com/bytedance/android-inline-hook)实现hook功能

### 项目结构

```python
-hook/
-include/
-other/
-qbdi-arm64/
-shadowhook/
-third/
CMakeLists.txt
jnitrace.cpp
libctrace.cpp
logger.cpp
native_main.cpp
qbdihook.cpp
vm.cpp
\```

### 工作原理

- 将libnativelib.so注入目标进程后，他会自动根据config中的libname，去/data/local/tmp目录下寻找对应的so，然后遍历进程的maps文件，在内存中进行比对，找到要trace的目标so。
- 通过shadowhook，hook目标函数。当程序执行到目标函数时，可以选择将控制流转移给qbdi进行trace，也可以只过滤特定的参数进行trace，而对其他的参数则执行原函数。这对trace高并发，或vmp函数入口很有帮助。

```python
_g_trace_data->hooktask = shadowhook_hook_func_addr((void*)(_g_trace_data->start + _g_trace_data->target),
                                                            (void*)(hook_and_trace_arg4),
                                                            (void**)&ori_arg4);
\```

例如，只有当X2为0x975dbf9a时，我们才进行trace，其他情况直接返回执行。

```python
size_t hook_and_trace_arg4(size_t x0,size_t x1,size_t x2,size_t x3)
{
    if(x2 != 0x975dbf9a)
    {
        return ori_arg4(x0,x1,x2,x3);
    }
    size_t regs[31] = {0};
    save_regs(regs);
    regs[0] = x0;
    regs[1] = x1;
    regs[2] = x2;
    regs[3] = x3;
    size_t result = trace(regs);//执行trace
    _g_trace_data->hooktask = shadowhook_hook_func_addr((void*)(_g_trace_data->start + _g_trace_data->target),
                                                        (void*)(hook_and_trace_arg4),
                                                        (void**)&ori_arg4);
    return result;
}
\```

- trace的过程中，会自动解析br，blr指令。如果目标地址命中自定义的libc函数，jni函数，或so本身的其他函数，则会根据你的定制规则进行解析。‘

内置了以下函数的监控：

```python
//libc函数
addLibctrace(handle,libc_access,"access");
addLibctrace(handle,libc_system_property_get,"__system_property_get");
addLibctrace(handle,libc_memcpy,"memcpy");
addLibctrace(handle,libc_pthread_create,"pthread_create");
addLibctrace(handle,libc_fopen,"fopen");
addLibctrace(handle,libc_lstat,"lstat");
addLibctrace(handle,libc_stat,"stat");
addLibctrace(handle,libc_fstatat,"fstatat");
addLibctrace(handle,libc_execve,"execve");
addLibctrace(handle,libc_clock_gettime,"clock_gettime");
addLibctrace(handle,libc_strlen,"strlen");
addLibctrace(handle,libc_memmove,"memmove");
addLibctrace(handle,libc_memset,"memset");
addLibctrace(handle,libc_kill,"kill");
addLibctrace(handle,libc_abort,"abort");
addLibctrace(handle,libc_exit,"exit");
\```

```python
//jni函数
addJNITrace((void*)pJFunc->NewStringUTF,"NewStringUTF",trace_NewStringUTF);
addJNITrace((void*)pJFunc->GetStringUTFChars,"GetStringUTFChars",trace_GetStringUTFChars);
addJNITrace((void*)pJFunc->NewString,"NewString",trace_NewString);
addJNITrace((void*)pJFunc->FindClass,"FindClass",trace_FindClass);
addJNITrace((void*)pJFunc->GetFieldID,"GetFieldID",trace_GetFieldID);
addJNITrace((void*)pJFunc->GetMethodID,"GetMethodID",trace_GetMethodID);
addJNITrace((void*)pJFunc->RegisterNatives,"RegisterNatives",trace_RegisterNatives);
addJNITrace((void*)pJFunc->GetLongField,"GetLongField",trace_GetLongField);
addJNITrace((void*)pJFunc->GetStaticMethodID,"GetStaticMethodID",trace_GetStaticMethodID);
addJNITrace((void*)pJFunc->CallStaticObjectMethodV,"CallStaticObjectMethodV",trace_CallStaticObjectMethodV);
addJNITrace((void*)pJFunc->GetStaticFieldID,"GetStaticFieldID",trace_GetStaticFieldID);
addJNITrace((void*)pJFunc->GetIntField,"GetIntField",trace_GetIntField);
addJNITrace((void*)pJFunc->GetByteArrayRegion,"GetByteArrayRegion",trace_GetByteArrayRegion);
addJNITrace((void*)pJFunc->GetArrayLength,"GetArrayLength",trace_GetArrayLength);
addJNITrace((void*)pJFunc->GetByteArrayElements,"GetByteArrayElements",trace_GetByteArrayElements);
\```

你也可以根据自己的逆向需求，增添更多的函数监控。

所有的监控函数都符合以下格式：

```python
typedef void (*TraceCallBack)(QBDI::VM *vm, QBDI::GPRState *gprState);
\```

例如libc_access:

```python
void libc_access(QBDI::VM *vm, QBDI::GPRState *gprState)
{
    if(_logger == nullptr)
    {
        LOGE("libc trace:logger not init!");
        return;
    }
    uint64_t x0 = QBDI_GPR_GET(gprState, 0);
    if(debug)
    {
        LOGE("libc access:%s",(char*)x0);
    }
    appendlogendl();
    appendlog("[log] libc access:");
    appendlog((char*)x0);
    appendlogendl();
}
\```

 会通过QBDI宏获取x0参数，然后在logcat中打印日志，同时写入log文件。

## 用法示例

以小某书的libtiny.so为例，讲述QTrace的基本用法：

首先需要将libtiny.so push到/data/local/tmp目录。

### trace jni_onload函数

然后修改native_main.cpp中的void config() 函数。指定目标so名称和trace的函数。我们先trace jni_onload函数

```python
void config()
{
    //目标so
    libname = "libtiny.so";
    ...

    //待trace函数，此处为jni_onload函数
    trace_func = 0x1991B4;
    ...
}
\```

由于jni_onload函数有2个参数，所以我们选择hook_and_trace_arg2，修改void trace()函数：

```python
void trace()
{
   ...
        _g_trace_data->hooktask = shadowhook_hook_func_addr((void*)(_g_trace_data->start + _g_trace_data->target),
                                                            (void*)(hook_and_trace_arg2),
                                                            (void**)&ori_arg2);
    ...
}
\```

执行android studio的make project，将生成的目标so，push到/data/local/tmp

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_SFBN6FAS852MVY4.webp)使用项目自带的inject.js注入so，在logcat中过滤QTrace，可以看到实时的trace日志：

![image](https://bbs.kanxue.com/upload/attach/202603/872365_YGWVBM3RTM6H34P.webp)

由于内置了RegisterNatives的解析，所以jni函数的注册自动打印了出来。函数名a，偏移0x173148

将trace文件pull到本地，用010editor查看：

有完整的指令trace和内存读写监控：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_UN7DYX8P3X7U3GK.webp)

同时日志里搜索[log]，也能看到jni注册信息：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_NARHXB2U3BHWX8R.webp)

a函数即其native入口函数：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_8MC6SFBH3H2SAJW.webp)

这个函数有很多调用，会根据第一个参数的不同，执行不同的任务：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_BQ9GEM2NW6V6X78.webp)

我们只关心其签名是如何生成的。

### trace native入口方法

重新修改void config()函数,我们trace a函数：

```python
void config()
{
    libname = "libtiny.so";
    ...
    //native入口函数
    trace_func = 0x173148;
    ...
}
\```

由于这个函数在native有4个入参，我们需要修改trace函数，使用hook_and_trace_arg4

```python
void trace()
{
   ...
        _g_trace_data->hooktask = shadowhook_hook_func_addr((void*)(_g_trace_data->start + _g_trace_data->target),
                                                            (void*)(hook_and_trace_arg4),
                                                            (void**)&ori_arg4);
    ...
}
\```

同时我们只关心签名，所以在hook_and_trace_arg4函数中，对X2进行过滤：

```python
size_t hook_and_trace_arg4(size_t x0,size_t x1,size_t x2,size_t x3)
{
    //不是签名，直接返回执行原来的函数。
    if(x2 != 0x975dbf9a)
    {
        return ori_arg4(x0,x1,x2,x3);
    }
    //是签名，进入trace
    size_t regs[31] = {0};
    save_regs(regs);
    regs[0] = x0;
    regs[1] = x1;
    regs[2] = x2;
    regs[3] = x3;
    size_t result = trace(regs);
    _g_trace_data->hooktask = shadowhook_hook_func_addr((void*)(_g_trace_data->start + _g_trace_data->target),
                                                        (void*)(hook_and_trace_arg4),
                                                        (void**)&ori_arg4);
    return result;
}
\```

查看日志。可以看到核心的签名都已经出现：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_UA4Q83DYVJ88RWP.webp)

将trace文件pull到本地，可以看到完整的指令，内存变化。并且所有日志也在trace文件中：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_PNBWZEHE39YV9KR.webp)

### 添加自定义函数监控

在逆向中我们会分析出一些功能函数，比如base64，加密解密函数等等。我们也可以将这些函数添加到trace中，连同日志一起打印出来，更好的辅助我们逆向分析：

例如我们发现0x71DD54函数是一个base64编码函数，我们可以在trace中增加相关的监控：

在 native_main.cpp 的addhooks()函数添加如下：

```python
static void addHooks()
{
    addHook(0x71DD54,hook_0x71DD54);
}
\```

在qbdihook.h添加对应的函数原型：

```python
void hook_0x71DD54(QBDI::VM *vm, QBDI::GPRState *gprState);
\```

在qbdihook.cpp中添加实现：

```python
void hook_0x71DD54(QBDI::VM *vm, QBDI::GPRState *gprState)
{
    //获取输入
    size_t input = QBDI_GPR_GET(gprState,3);
    //获取长度
    size_t len = QBDI_GPR_GET(gprState,4);
    //将输入以16进制字符串打印
    char* hex = bytes_to_hex_string((char*)input,len);
    char* base64 = (char*) malloc(2 * len);
    memset(base64,0,2*len);
    base64_encode(base64,(uint8_t*)input,len);
    //在logcat里打印base64的输入和结果
    LOGE("base64:src:%p,raw:%s,res:%s",input,hex,base64);

    //在trace文件里写入同样的结果
    appendlogendl();
    appendformat("base64:src:%p,raw:%s,res:%s",input,hex,base64);
    appendlogendl();
    free(hex);
    free(base64);
}
\```

重新编译生成libnativelib.so，push到/data/local/tmp目录，注入：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_CYRMFVNRP3MGTG4.webp)

可以看到，当trace经过base64函数时，会自动打印出相关信息。

你可以根据自己的逆向结果，添加更多的自定义监控，然后trace。这样出来的trace文件会极大的提升逆向效率。

libc函数和jni函数的监控用法相同，分别在void addLibctrace() 和void addJNItrace()中添加即可。

## 总结

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_VS96S8MA7EV6K7B.webp)

在trace面前，所有的ollvm混淆，间接跳转，vmp都像纸糊的一样。当然，有了完整的trace指令，内存读写和日志，接下来如何分析trace，是各位自己的事情了。

如果您在使用QTrace的过程中遇到任何问题，欢迎进群交流讨论：

 ![image](https://bbs.kanxue.com/upload/attach/202603/872365_AH6R5Y7JDFQDVRC.webp)

---

# 回复

## 回复 by wx_插曲 (#2)

*2026-3-31 08:06*

6

## 回复 by huangjw (#3)

*2026-3-31 08:55*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_jhohnbzu (#4)

*2026-3-31 09:43*

66

## 回复 by k4y0z (#5)

*2026-3-31 09:49*

666

## 回复 by mb_pesxllvn (#6)

*2026-3-31 09:53*

666

## 回复 by mb_iesvmzqc (#7)

*2026-3-31 10:02*

666

## 回复 by mb_mlyojneh (#8)

*2026-3-31 10:03*

感谢分享

## 回复 by 呆萌的小白 (#9)

*2026-3-31 10:04*

已收藏

## 回复 by XCicada (#10)

*2026-3-31 10:16*

66

## 回复 by mb_ysegxpmv (#11)

*2026-3-31 10:30*

牛逼，大佬

## 回复 by 西瓜帅 (#12)

*2026-3-31 10:33*

llok look

## 回复 by mb_asiwnxyv (#13)

*2026-3-31 10:33*

感谢分享

## 回复 by Zepp7289 (#14)

*2026-3-31 10:42*

tql

## 回复 by 墨穹呢 (#15)

*2026-3-31 11:17*

感谢分享

## 回复 by mb_pmgifpme (#16)

*2026-3-31 11:22*

1

## 回复 by jyotidwi (#17)

*2026-3-31 11:36*

Tql

## 回复 by mb_qimctavn (#18)

*2026-3-31 12:34*

6

## 回复 by 飆汗吉米 (#19)

*2026-3-31 12:38*

666

## 回复 by mb_yzaaoeic (#20)

*2026-3-31 12:41*

66666

## 回复 by 温泉划水鱼 (#21)

*2026-3-31 12:46*

看看

## 回复 by mb_ldbucrik (#22)

*2026-3-31 13:34*

太强了,感谢大佬

## 回复 by 丶咖啡猫丶 (#23)

*2026-3-31 13:40*

666

## 回复 by B.M.K (#24)

*2026-3-31 13:56*

666

## 回复 by lixianhuei (#25)

*2026-3-31 14:09*

6666

## 回复 by Sigil (#26)

*2026-3-31 14:14*

1

## 回复 by yezheyu (#27)

*2026-3-31 14:29*

666

## 回复 by Imxz (#28)

*2026-3-31 15:13*

rbq

## 回复 by cydian (#29)

*2026-3-31 16:20*

666

## 回复 by git_82017s1e34ou (#30)

*2026-3-31 16:41*

666

## 回复 by MaYil (#31)

*2026-3-31 16:56*

感谢分享

## 回复 by mb_cbgtaveo (#32)

*2026-3-31 18:05*

666

## 回复 by wx_huhu_859 (#33)

*2026-3-31 18:13*

11

## 回复 by iBa0 (#34)

*2026-3-31 18:29*

123

## 回复 by 29o (#35)

*2026-3-31 20:37*

感谢

## 回复 by ulong9527 (#36)

*2026-3-31 23:39*

666

## 回复 by mb_mfjsranl (#37)

*2026-4-1 09:08*

666

## 回复 by GEKEZYX (#38)

*2026-4-1 09:49*

666

## 回复 by 机车王子 (#39)

*2026-4-1 10:02*

感谢你分享这么好的资源！

## 回复 by kingking888 (#40)

*2026-4-1 10:08*

666

## 回复 by git_26578slotmagia (#41)

*2026-4-1 11:35*

1111

## 回复 by baichisi (#42)

*2026-4-1 17:06*

6666

## 回复 by lookzo (#43)

*2026-4-1 22:18*

666

## 回复 by ldehua (#44)

*2026-4-1 22:30*

6666

## 回复 by 九黎 (#45)

*2026-4-2 09:27*

tql

## 回复 by 寻梦之璐 (#46)

*2026-4-2 10:23*

666

## 回复 by 一栋奥特曼 (#47)

*2026-4-2 10:31*

66666

## 回复 by xifgg (#48)

*2026-4-2 14:07*

66

## 回复 by xianhuimin (#49)

*2026-4-2 14:39*

感谢分享

## 回复 by Gryffindoss (#50)

*2026-4-2 14:40*

6666

## 回复 by 始識 (#51)

*2026-4-2 17:14*

6666

## 回复 by 4Chan (#52)

*2026-4-2 17:33*

666

## 回复 by amwpecel (#53)

*2026-4-3 10:40*

6666

## 回复 by mb_rbaigqfb (#54)

*2026-4-3 12:56*

太强了,感谢大佬

## 回复 by zsf2019 (#55)

*2026-4-3 14:21*

666

## 回复 by mb_mnqvyswo (#56)

*2026-4-3 16:56*

qbdi 我记得有缺点来着

## 回复 by 天地一逆旅 (#57)

*2026-4-3 17:29*

牛牛牛

## 回复 by wx_妳还是不懂 (#58)

*2026-4-3 19:42*

非常感谢

## 回复 by wx_西门浪 (#59)

*2026-4-3 21:43*

6666666666

## 回复 by FMNS (#60)

*2026-4-4 09:10*

666

## 回复 by mb_ybvqgbkl (#61)

*2026-4-4 10:42*

666666

## 回复 by fengvmu (#62)

*2026-4-4 19:53*

感谢分享

## 回复 by 熊猫吃鱼 (#63)

*2026-4-4 20:18*

666

## 回复 by 龙飞雪 (#64)

*2026-4-5 14:58*

感謝分享，學習了。

## 回复 by 小迷糊ddd (#65)

*2026-4-5 15:11*

感谢分享，学习一下。

## 回复 by 我今年6岁 (#66)

*2026-4-5 21:20*

66

## 回复 by angelbox (#67)

*2026-4-6 09:17*

6666

## 回复 by mb_irhdtnzm (#68)

*2026-4-7 08:15*

1

## 回复 by Elenia (#69)

*2026-4-7 16:23*

谢谢分享

## 回复 by xxjj678 (#70)

*2026-4-7 18:39*

666

## 回复 by didiid (#71)

*2026-4-8 00:04*

6667

## 回复 by Xx_gg (#72)

*2026-4-8 08:44*

6666

## 回复 by 我就是小熊猫 (#73)

*2026-4-8 09:57*

666

## 回复 by jasonxgw (#74)

*2026-4-8 16:10*

tql

## 回复 by mb_lfwgtxdb (#75)

*2026-4-8 16:10*

感谢分享

## 回复 by mb_bckuidjl (#76)

*2026-4-8 16:41*

6666

## 回复 by koflfy (#77)

*2026-4-9 10:42*

mark

## 回复 by mb_uktygsmq (#78)

*2026-4-9 17:04*

6666

## 回复 by mb_ykavguun (#79)

*2026-4-9 23:43*

1

## 回复 by Oo风之恋oO (#80)

*2026-4-10 13:56*

这是什么看不懂啊

## 回复 by wx_L_ (#81)

*2026-4-10 17:32*

666

## 回复 by cx52038 (#82)

*2026-4-11 01:21*

666

## 回复 by mb_mrobgkew (#83)

*2026-4-12 17:10*

656666

## 回复 by mb_ysikfhxt (#84)

*2026-4-12 19:08*

666

## 回复 by wx_fly_397447 (#85)

*2026-4-12 23:03*

6666666666666666

## 回复 by mb_gatolgsc (#86)

*2026-4-13 08:58*

66666

## 回复 by 带壳的蜗牛 (#87)

*2026-4-13 14:03*

6666666666

## 回复 by git_14248bibinocode (#88)

*2026-4-13 23:32*

66666666666666666

## 回复 by yltfy (#89)

*2026-4-14 01:43*

666

## 回复 by mb_koixqizd (#90)

*2026-4-14 13:36*

学习

## 回复 by Freax (#91)

*2026-4-15 18:15*

666

## 回复 by xerik (#92)

*2026-4-15 18:32*

6666

## 回复 by xerik (#93)

*2026-4-15 18:32*

6666

## 回复 by cpannn (#94)

*2026-4-17 20:13*

研究中

## 回复 by 嘎嘎真的很棒 (#95)

*2026-4-18 11:30*

tql

## 回复 by mb_hdgliaem (#96)

*2026-4-20 14:56*

666

## 回复 by try_catch (#97)

*2026-4-20 15:04*

666

## 回复 by mb_tvuiswau (#98)

*2026-4-20 18:52*

发萨达附属

## 回复 by jw8888 (#99)

*2026-4-20 20:00*

666666666666

## 回复 by 金白水清 (#100)

*2026-4-21 00:01*

感谢大佬分享好工具

## 回复 by Ankeys (#101)

*2026-4-21 11:27*

感谢分享

## 回复 by mb_gluymaeh (#102)

*2026-4-24 14:56*

6666

## 回复 by mb_donutrph (#103)

*2026-4-24 15:42*

666

## 回复 by namename123 (#104)

*2026-4-27 15:40*

666

## 回复 by uni7corn (#105)

*2026-4-27 17:52*

666

## 回复 by ivy1 (#106)

*2026-4-27 18:48*

6666

## 回复 by wx_A哦 (#107)

*2026-4-29 16:26*

6666

## 回复 by wx_A哦 (#108)

*2026-4-29 16:26*

6666

## 回复 by PangBai (#109)

*2026-5-1 13:41*

999

## 回复 by mb_whftmjdy (#110)

*2026-5-2 07:40*

6666666666666

## 回复 by 伊苏尔德 (#111)

*2026-5-3 23:02*

6

## 回复 by wx_Huber Barrientos (#112)

*2026-5-5 02:03*

666

## 回复 by niama (#113)

*2026-5-5 06:55*

666

## 回复 by mb_uzmffdbw (#114)

*2026-5-6 09:58*

666

## 回复 by wx_Dispa1r (#115)

*2026-5-6 15:00*

1

## 回复 by logeye (#116)

*2026-5-6 19:42*

6666

## 回复 by mb_ssjlfpnk (#117)

*2026-5-6 20:14*

![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by Wolfxyb (#118)

*2026-5-7 10:52*

6666666666

## 回复 by mb_xwntdpxy (#119)

*2026-5-8 16:04*

666

## 回复 by Crack999 (#120)

*2026-5-8 16:15*

66666666

## 回复 by WX_WQj (#121)

*2026-5-9 10:48*

6666

## 回复 by rico_wu (#122)

*2026-5-9 14:19*

666666

## 回复 by mb_osxdmntv (#123)

*2026-5-10 00:28*

666

## 回复 by mb_utmyqsij (#124)

*2026-5-10 11:26*

777

## 回复 by mb_rirvdrlh (#125)

*2026-5-10 13:00*

666666

## 回复 by nuomida (#126)

*2026-5-11 14:37*

这个和gumTrace相比有啥区别呢

## 回复 by mb_npsajqlx (#127)

*2026-5-11 14:54*

666

## 回复 by Circ1e (#128)

*2026-5-11 15:15*

666

## 回复 by mb_rdailgiw (#129)

*2026-5-11 16:58*

666

## 回复 by wx_ㅤ_683 (#130)

*2026-5-11 21:18*

支持32位的so吗

## 回复 by 乐子人 (#131)

*2026-5-11 22:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>  支持32位的so吗
>

只支持64的

## 回复 by 鼻屎怪 (#132)

*2026-5-12 16:53*

tql

## 回复 by njxxdx (#133)

*2026-5-12 21:23*

太强了,感谢大佬

## 回复 by shuangmou (#134)

*2026-5-13 20:58*

感谢分享

## 回复 by 努力的菜鸡 (#135)

*2026-5-14 13:08*

666

## 回复 by 雪国的冬天 (#136)

*2026-5-17 08:32*

感谢大佬分享

## 回复 by mb_kumzialx (#137)

*2026-5-18 16:09*

8888

## 回复 by ben_ (#138)

*2026-5-18 16:17*

66666

## 回复 by 木志本柯 (#139)

*2026-5-18 16:41*

QBDI动态二进制插桩会被crc检测不？

## 回复 by 五彩斑斓的黑 (#140)

*2026-5-18 18:45*

666

## 回复 by merryfish (#141)

*2026-5-18 21:33*

very good

## 回复 by 乐子人 (#142)

*2026-5-19 14:04*

>
> [木志本柯](https://bbs.kanxue.com/user-749995.htm)
>  QBDI动态二进制插桩会被crc检测不？
>

不会

## 回复 by 木志本柯 (#143)

*2026-5-19 17:11*

>
> [乐子人](https://bbs.kanxue.com/user-872365.htm)
>  不会
>

会被检测到返回地址不，比如call的返回地址？

## 回复 by mb_uokrnlrg (#144)

*2026-5-21 08:37*

666

## 回复 by x1a0f3n9 (#145)

*2026-5-22 01:39*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_euhyowpw (#146)

*2026-5-22 09:09*

666

## 回复 by mb_uohfzjqw (#147)

*2026-5-22 10:13*

6666

## 回复 by olibaby (#148)

*2026-5-22 22:41*

6666

## 回复 by git_45464ntt3005 (#149)

*2026-5-22 23:23*

6666

## 回复 by zxqi (#150)

*2026-5-24 00:54*

1

## 回复 by np010 (#151)

*2026-5-24 17:52*

nice tool

## 回复 by 桐人dx (#152)

*2026-5-25 21:18*

6666

## 回复 by mb_farzbkyi (#153)

*2026-5-26 17:17*

666

## 回复 by ovo_帮我不c (#154)

*2026-5-26 17:25*

111

## 回复 by ycdear (#155)

*2026-5-26 23:09*

111

## 回复 by REHEroadchik (#156)

*2026-5-27 11:40*

666

## 回复 by xifgg (#157)

*2026-5-27 14:08*

666

## 回复 by dob_C (#158)

*2026-5-27 16:11*

感谢分享

## 回复 by 中文fjja (#159)

*2026-5-27 22:53*

感谢分享

## 回复 by maomaolk (#160)

*2026-5-28 16:32*

6666

## 回复 by 发烧小孩 (#161)

*2026-5-28 17:11*

666

## 回复 by Migc (#162)

*2026-5-29 16:35*

6666

## 回复 by ak8888 (#163)

*2026-5-31 19:57*

hello

## 回复 by 枯藤舍 (#164)

*2026-5-31 20:05*

666

## 回复 by wx_Kerberos (#165)

*2026-6-1 00:27*

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by 小木马 (#166)

*2026-6-2 16:40*

666

## 回复 by mb_dcjxxhsk (#167)

*2026-6-4 16:59*

666

## 回复 by mb_tewbhakr (#168)

*2026-6-5 22:40*

看看

## 回复 by Mr.ChenX (#169)

*2026-6-6 11:16*

666

## 回复 by mb_mwfzoyhc (#170)

*2026-6-8 05:37*

谢谢分享

## 回复 by git_74197luban110 (#171)

*2026-6-8 08:39*

666

## 回复 by Tao Holmes (#172)

*2026-6-11 16:37*

6666

## 回复 by bygrand (#173)

*2026-6-11 22:37*

666

## 回复 by mb_etrbkelx (#174)

*2026-6-15 14:29*

666

## 回复 by Sungt. (#175)

*2026-6-15 15:23*

1

## 回复 by mb_ktasfpbp (#176)

*2026-6-15 18:00*

6

## 回复 by tubecityman (#177)

*2026-6-15 18:41*

IOS有吗

## 回复 by mb_bysnyvmg (#178)

*2026-6-18 12:01*

6666

## 回复 by mb_yalauklc (#179)

*2026-6-18 17:17*

666

## 回复 by 何森 (#180)

*2026-6-20 15:48*

奖励楼主一个胸大臀肥的TS

## 回复 by mb_paeqogwt (#181)

*2026-6-22 15:42*

学习

## 回复 by mb_paopxhtx (#182)

*2026-6-22 22:30*

666666

## 回复 by SInnon (#183)

*2026-6-24 03:07*

66666666666666666666666

## 回复 by lbunknow (#184)

*2026-6-24 10:10*

666

## 回复 by dsr000 (#185)

*2026-6-24 14:12*

666

## 回复 by Splite_1130 (#186)

*2026-6-26 20:05*

6666

## 回复 by myios (#187)

*2026-6-30 06:24*

666

## 回复 by 天涯共何时 (#188)

*2026-7-3 18:43*

666

## 回复 by mb_tfqctboq (#189)

*2026-7-5 11:47*

666

## 回复 by 梦笔随花 (#190)

*2026-7-6 17:23*

6

## 回复 by mb_gcjwsflo (#191)

*2026-7-6 17:27*

666

## 回复 by wx_coddvccwyh (#192)

*2026-7-6 19:54*

6666

## 回复 by 林懋 (#193)

*2026-7-6 23:37*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by a5right (#194)

*2026-7-7 10:42*

6666

## 回复 by spdfdfer (#195)

*2026-7-10 00:44*

6666

## 回复 by lotus* (#196)

*2026-7-10 14:13*

66666

## 回复 by alds (#197)

*2026-7-10 17:24*

66

## 回复 by mb_iiumogmn (#198)

*2026-7-12 23:00*

感谢分享

## 回复 by 西埔 (#199)

*2026-7-16 14:03*

8888

## 回复 by wx_至尊宝_395664 (#200)

*2026-7-16 15:38*

6

## 回复 by ID蝴蝶 (#201)

*2026-7-16 16:00*

666

## 回复 by simpleness (#202)

*2026-7-16 17:20*

6

## 回复 by Yy798e (#203)

*2026-7-17 17:08*

66666

## 回复 by mb_sqetvntx (#204)

*2026-7-17 17:30*

学习

## 回复 by mb_twbjvgyf (#205)

*2026-7-21 06:34*

1

## 回复 by mb_wjytplsl (#206)

*2026-7-25 10:15*

666

## 回复 by MikotoDev (#207)

*2026-7-27 10:51*

666

## 回复 by 钟白 (#208)

*2026-7-27 11:38*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by J1rrY (#209)

*2026-7-27 11:45*

6666666

## 回复 by git_56402Syy040316 (#210)

*2026-7-29 11:39*

1

## 回复 by v5w7crq3 (#211)

666
