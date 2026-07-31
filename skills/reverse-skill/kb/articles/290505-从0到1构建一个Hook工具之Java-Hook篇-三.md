---
title: '[原创]从0到1构建一个Hook工具之Java Hook篇（三）'
url: https://bbs.kanxue.com/thread-290505.htm
tid: 290505
author: n_1ng
date: '2026-03-25'
tags: [Android安全, 原创, HOOK注入]
crawled_at: '2026-07-31T15:12:16+08:00'
replies: 24
---

## 前言

在前两篇文章中，我们已经做到了attach和spawn两种模式的注入，你是否还记得，我们在做传统spawn注入的时候用到了一个叫做dobby的框架，当时并没有深入介绍，从这一篇文章开始，我们就将进入真正的Hook部分，这里先从Java世界开始。有描述不对的或者值得改进的欢迎在评论区提出！

项目地址：https://github.com/x1aon1ng/Nook

## 目标

暂时我们只关心Java Hook的核心部分实现，因此这里的成品只是一个粗糙的hook框架，其他的后面会慢慢再补充上来。在读完这篇文章后，相信你可以问答下面这些问题：

1. Android上的Java方法最终是如何被执行的
2. Java Hook到底hook的是什么
3. Java Hook的核心原理是什么
4. 一个最小可用的Java Hook框架至少需要哪些部件
5. Hook框架和注入器分别解决的是什么问题

## 具体原理和实现

### 知道这些基础你会更好的理解下文

1. JNI：即Java Native Interface，Java和native代码交互的标准接口，定义了Java怎么调用C/C++，以及C/C++怎么访问Java对象、类、方法
2. JNIEnv：是JNI提供给native线程的接口表句柄，其实就是“当前线程操作JVM/Java对象的入口”，所有的JNI调用基本都要通过它，比如FindClass、GetMethodID
3. Application：在Android中一个app启动后，系统会在他的进程中创建一个Application对象，这个Application是这个app在当前进程的全局入口对象
4. ClassLoader：Java中的类不是天然就在内存中的，是需要时由类加载器加载进来的，这个类的装载器即ClassLoader，不同的ClassLoader决定了类是否能被找到、属于哪个类空间
5. ArtMethod：ART运行时中“一个Java方法”的底层描述结构，不是Java层的Method对象，而是ART内部真正决定方法如何执行的native结构，里面会保存方法标志入口地址等关键信息
6. access_flags：方法或类的访问标志位，描述这个方法有哪些属性比如public、static、native，在Hook中我们往往会修改这个字段来改变方法执行语义
7. JIT/AOT：JIT即Just-In-Time，运行时即时编译，方法执行时热点代码会在运行过程中被编译为机器码；AOT即Ahead-Of-Time，提前编译，安装或构建阶段就将代码编译为机器码；对Hook来说JIT/AOT会影响方法最后走解释器、quick code还是桥接入口
8. entry_point_from_jni：ArtMethod里记录JNI/Native路径入口的字段，可以理解为：如果这个方法按JNI/Native语义执行，最后该跳到的native地址
9. entry_point_from_compiled_code：ArtMethod里记录编译后代码/quick路径入口的字段，可以理解为：方法正常执行时ART从那段compiled/quick代码开始进入
10. ABI：这里指Application Binary Interface，二进制调用约定
11. trampoline：跳板代码，一小段中转代码，通常不负责业务逻辑，在Hook中它是原始执行路径和框架处理逻辑之间的桥梁

### 原理和方案实现

### 原理介绍

我们从一个非常简单的Java方法来理解Java Hook

```java
package cn.n1ng.javatest;

public class JavaHookTest {
    public int get_num_from_java_method() {
        return 111;
    }
}
```

如果我们想要把他的返回值从111改为999，表面上看起来非常简单，但从运行视角来看，它背后发生了这些事情：

1. 找到JavaHookTest.get_num_from_java_method()这一个方法
2. 找到它在ART里的ArtMethod
3. 保留原始实现，做好备份
4. 改写方法入口让他先进入我们自己的trampoline
5. 在trampoline里把调用现场给接住
6. 解析参数和返回值类型
7. 进入我们的hook回调
8. 在回调里修改返回值

在这个过程中需要解决的是两个核心问题：

首先是**方法接管**

即解决怎么让目标方法执行时先到我这里来的问题

然后是**调用还原**

即解决“来到我这里”之后，我怎么知道原方法的参数、返回值怎么处理、原方法还能不能继续调用的问题

所以在框架外看起来可能只是一个简单的数字替换，在内部实现往往会牵扯到ArtMethod、trampoline、ABI、参数解析、backup、调用桥接等问题，解决这些问题是实现Java Hook的最低门槛。

### 具体实现

上文我们已经知道了实现一次hook需要经历哪些流程，由此我们可以总结出一个最小可用的Java Hook框架至少需要下面这些部件。

**方法定位**

第一步首先是需要先找到目标方法，他需要解决的问题是如何从类名、方法名、签名定位到Java方法，又如何从Java方法进一步拿到ART内部的方法。即：

1. FindClass
2. GetMethodID
3. jmethodID -> ArtMethod

用户需要给出class_name, method_name, signature, is_static；首先需要JNIEnv，因为后面无论是FindClass还是GetMethodID都依赖于JNIEnv*，

然后是FindClass，思路是先直接通过env->FindClass，失败后通过ActivityThread.currentApplication()拿到当前应用(这里选择android.app.ActivityThread，因为他是系统类，能拿到当前进程里的Application对象)，找到currentApplication方法，调用它拿到当前Application，此时我们拿到了当前目标进程里的Application实例，他是App运行时环境的核心对象之一，通过它可以继续拿到真正属于这个App的ClassLoader，最后调用ClassLoader.loadClass()方法真正加载目标类。

```cpp
    // 1) Try normal FindClass
    std::string slashName;
    for (const char* p = className; *p; ++p) {
        slashName += (*p == '.') ? '/' : *p;
    }

    jclass clazz = env->FindClass(slashName.c_str());
    if (clazz) return clazz;
    if (env->ExceptionCheck()) env->ExceptionClear();

    // 2) Injection context: use Application ClassLoader
    jclass activityThreadClass = env->FindClass("android/app/ActivityThread");
    if (!activityThreadClass) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jmethodID currentAppMethod = env->GetStaticMethodID(
        activityThreadClass, "currentApplication", "()Landroid/app/Application;");
    if (!currentAppMethod) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jobject application = env->CallStaticObjectMethod(activityThreadClass, currentAppMethod);
    if (!application || env->ExceptionCheck()) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jclass applicationClass = env->GetObjectClass(application);
    jmethodID getClassLoaderMethod = env->GetMethodID(
        applicationClass, "getClassLoader", "()Ljava/lang/ClassLoader;");
    env->DeleteLocalRef(applicationClass);
    if (!getClassLoaderMethod) {
        env->DeleteLocalRef(application);
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jobject classLoader = env->CallObjectMethod(application, getClassLoaderMethod);
    env->DeleteLocalRef(application);
    if (!classLoader || env->ExceptionCheck()) {
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jclass classLoaderClass = env->FindClass("java/lang/ClassLoader");
    if (!classLoaderClass) {
        env->DeleteLocalRef(classLoader);
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    jmethodID loadClassMethod = env->GetMethodID(
        classLoaderClass, "loadClass", "(Ljava/lang/String;)Ljava/lang/Class;");
    if (!loadClassMethod) {
        env->DeleteLocalRef(classLoader);
        env->DeleteLocalRef(classLoaderClass);
        if (env->ExceptionCheck()) env->ExceptionClear();
        return nullptr;
    }

    std::string dotName;
    for (const char* p = className; *p; ++p) {
        dotName += (*p == '/') ? '.' : *p;
    }

    jstring classNameStr = env->NewStringUTF(dotName.c_str());
    jclass loadedClass = (jclass)env->CallObjectMethod(classLoader, loadClassMethod, classNameStr);
    env->DeleteLocalRef(classNameStr);
    env->DeleteLocalRef(classLoader);
    env->DeleteLocalRef(classLoaderClass);

    if (loadedClass && !env->ExceptionCheck()) {
        LOGI("FindClass via ActivityThread success: %s", className);
        return loadedClass;
    }
```

再接着是FindMethod，其实就是获取methodID，我们此时已经拿到了jclass，并且知道了方法名、方法签名，直接通过env->GetMethodID获取即可，顺便把签名转化为一种更简单的格式，后面记作shorty。

```cpp
    std::string methodSignature = shorty ? shorty : "";
    std::string detectedShorty;

    if (!signature_to_shorty(methodSignature.c_str(), &detectedShorty)) {
        LOGE("Invalid method signature for shorty conversion: %s", methodSignature.c_str());
        return {nullptr, ""};
    }

    jmethodID methodID = isStatic ?
        env->GetStaticMethodID(clazz, methodName, methodSignature.c_str()) :
        env->GetMethodID(clazz, methodName, methodSignature.c_str());
```

在ART中，jmethodID只是一个中间桥梁，真正需要改写的目标是ArtMethod。

```cpp
jclass clazz = FindClass(env, className);
auto [methodID, detectedShorty] = FindMethod(env, clazz, methodName, shorty, isStatic);
void* artMethod = ArtInternals::DecodeFunc(ArtInternals::jniIDManager, methodID);

if (!artMethod) {
    LOGE("Failed to decode method ID");
    return -1;
}
```

**运行时结构识别**

我们最终要改的不是Java对象，而是ART内部结构和入口字段，因此需要识别出ArtMethod大小、access_flags偏移、entry_point_from_compiled_code偏移等关键信息

这个运行时结构信息我们一部分通过解析libart符号获取，一部分通过运行时探测结构偏移获取，最后把这些结构统一存储到ArtInternals中供后续Hook使用

我们可以设计几个结构体来存储相关运行时布局信息

```cpp
  typedef struct {
      intptr_t heap;
      intptr_t threadList;
      intptr_t internTable;
      intptr_t classLinker;
      intptr_t jniIdManager;
  } ArtRuntimeSpecOffsets;

  typedef struct {
      intptr_t quickResolutionTrampoline;
      intptr_t quickImtConflictTrampoline;
      intptr_t quickGenericJniTrampoline;
      intptr_t quickToInterpreterBridgeTrampoline;
  } ClassLinkerSpecOffsets;

  struct ArtMethodSpec {
      size_t offset_access_flags;
      size_t offset_entry_jni;
      size_t offset_entry_quick;
      size_t art_method_size;
      size_t interpreterCode;
  };
```

其中ArtRuntimeSpecOffsets描述的是Runtime里几个关键成员的偏移，比如heap、threadList、classLinker等；ClassLinkerSpecOffsets描述的是ClassLinker里几个关键trampoline的偏移，ArtMethodSpec描述的是ArtMethod里真正要改写的字段偏移：access_flags，entry_jni，entry_quick，ArtMethod大小。

ArtInternals的命名空间记录了结果的存储

```cpp
  DecodeMethodIdFn DecodeFunc = nullptr;
  ArtMethodInvoke Invoke = nullptr;
  CurrentFromGDB GetCurrentThread = nullptr;
  DecodeJObjectFn DecodeJObject = nullptr;
  ScopedGCSection SGCFn = nullptr;
  destroyScopedGCSection DestroyGCFn = nullptr;
  ScopedSuspendAll ScopedSuspendAllFn = nullptr;
  destroyScopedSuspendAll destroyScopedSuspendAllFn = nullptr;
  newlocalref newlocalrefFn = nullptr;

  uintptr_t RuntimeInstance = 0;
  void* jniIDManager = nullptr;
  ArtMethodSpec ArtMethodLayout = {0};
  ArtRuntimeSpecOffsets RunTimeSpec = {0};
  ClassLinkerSpecOffsets ClassLinkerSpec = {0};
```

大致是靠这几种方法找到的：

1. 符号解析：从libart.so直接拿函数/全局符号，比如Runtime::instance_，DecodeMethodId，ArtMethod::Invoke
2. 锚点扫描：用已知对象值作为锚点反推结构偏移，比如JavaVM*是外部已知值，如果Runtime某一段内存里有个成员正好等于它，那这个点就能作为结构定位锚点反推Runtime
3. 样本方法特征识别：用一个已知方法的flags/JNI入口特征取探测ArtMethod布局

```cpp
        void *art_method = ArtInternals::DecodeFunc(ArtInternals::jniIDManager, mid);
        if (!art_method) {
            LOGE("Failed to decode art_method");
            return false;
        }

        uintptr_t base = reinterpret_cast<uintptr_t>(art_method);
        uintptr_t entry_jni_offset = 0;
        uintptr_t access_flags_offset = 0;
        size_t found = 0;

        const uint32_t expected_flags =
                kAccPublic | kAccStatic | kAccFinal | kAccNative;
        const uint32_t flags_mask = 0x0000FFFF;

        for (size_t offset = 0; offset < 64; offset += 4) {
            uintptr_t addr = base + offset;

            // 1. check if it's a pointer into libandroid_runtime.so
            void *maybe_ptr = *reinterpret_cast&lt;void **&gt;(addr);
            if (tool::is_in_module(maybe_ptr, "libandroid_runtime.so")) {
                entry_jni_offset = offset;
                found++;
                LOGI("Found: entry_jni_offset = 0x%lx", offset);
            }

            // 2. check if it looks like access_flags
            uint32_t maybe_flags = *reinterpret_cast<uint32_t *>(addr);
            if ((maybe_flags & flags_mask) == expected_flags) {
                access_flags_offset = offset;
                found++;
                LOGI("Found: access_flags_offset = 0x%lx (flags = 0x%x)", offset, maybe_flags);
            }

            if (found == 2) break;
        }

        if (found != 2) {
            LOGE("Failed to detect ArtMethod field layout");
            return false;
        }

        // 3. quick_code entry offset is next pointer
        uintptr_t entry_quick_offset = entry_jni_offset + pointer_size;

        output->offset_entry_jni = entry_jni_offset;
        output->offset_access_flags = access_flags_offset;
        output->offset_entry_quick = entry_quick_offset;
        output->art_method_size = entry_quick_offset + pointer_size;
        output->interpreterCode = output->offset_entry_jni - pointer_size;
```

**原方法备份**

如果我们没有做原方法的备份，仅仅只是做了修改目标方法入口，当后面再想调用原方法的时候，可能就无从找起了，因此需要提前做好backup。

先读原始字段

```cpp
  uint64_t* quickCode = (uint64_t*)((char*)artMethod +
  ArtInternals::ArtMethodLayout.offset_entry_quick);
  uint32_t orgFlag = *(uint32_t*)((char*)artMethod +
  ArtInternals::ArtMethodLayout.offset_access_flags);
  uint64_t* jni = (uint64_t*)((char*)artMethod + ArtInternals::ArtMethodLayout.offset_entry_jni);
```

然后放入HookInfo中

```cpp
  HookInfo info = {
      className,
      methodName,
      detectedShorty,
      isStatic,
      artMethod,
      nullptr,
      trampoline,
      *quickCode,
      *jni,
      orgFlag,
      0,
      0,
      0,
      false,
      ArtInternals::ArtMethodLayout,
      methodID,
      callback,
      true
  };
```

然后按探测到的ArtMethod大小分配一块新内存，把当前目标ArtMethod整块复制过去

```cpp
static void* allocate_backup_artmethod(const HookInfo& hookInfo) {
    auto backup = new uint8_t[hookInfo.layout.art_method_size];
    if (!backup) {
        LOGE("Failed to allocate backup ArtMethod");
        return nullptr;
    }

    memcpy(backup, hookInfo.artMethod, hookInfo.layout.art_method_size);
    return backup;
}

static void sync_backup_artmethod(HookInfo& hookInfo) {
    if (!hookInfo.backupValid || !hookInfo.backupArtMethod) {
        return;
    }

    auto currentFlag = *reinterpret_cast<uint32_t*>((char*)hookInfo.artMethod + hookInfo.layout.offset_access_flags);
    auto currentQuick = *reinterpret_cast<uint64_t*>((char*)hookInfo.artMethod + hookInfo.layout.offset_entry_quick);
    auto currentJni = *reinterpret_cast<uint64_t*>((char*)hookInfo.artMethod + hookInfo.layout.offset_entry_jni);

    if (currentQuick != 0 && currentQuick != hookInfo.hookedEntryPoint) {
        hookInfo.orgEntryPoint = currentQuick;
    }
    if (currentJni != 0 && currentJni != hookInfo.hookedJNIEntry) {
        hookInfo.orgJNIEntry = currentJni;
    }
    if (currentFlag != hookInfo.hookedFlag) {
        hookInfo.orgFlag = currentFlag;
    }

    recover_artmethod(hookInfo.backupArtMethod, hookInfo, true);
}
```

但我们最终想要的backup不是目标方法某一时刻的机械拷贝，而是一份可以代表原方法执行路径、并且可以被Invoke稳定调用的ArtMethod，所以需要调用recover_artmethod方法，恢复原始access_flags、entry_quick、entry_jni，并且还加上了一个kAccCompileDontBother标志，可以让其更稳定，减少运行时/JIT对他做额外处理

```cpp
  static void recover_artmethod(void* ArtmethodToRecover, HookInfo& hookInfo, bool tempRecover =
  false) {
      if (tempRecover) {
          *reinterpret_cast<uint32_t*>((char*)ArtmethodToRecover +
  hookInfo.layout.offset_access_flags)
              = hookInfo.orgFlag | kAccCompileDontBother;
      } else {
          *reinterpret_cast<uint32_t*>((char*)ArtmethodToRecover +
  hookInfo.layout.offset_access_flags)
              = hookInfo.orgFlag;
      }
      *reinterpret_cast<uint64_t*>((char*)ArtmethodToRecover + hookInfo.layout.offset_entry_quick)
          = hookInfo.orgEntryPoint;
      *reinterpret_cast<uint64_t*>((char*)ArtmethodToRecover + hookInfo.layout.offset_entry_jni)
          = hookInfo.orgJNIEntry;
  }
```

**入口改写**

这里是真正让hook生效的一步，Java Hook的本质就是接管执行入口，这一步通常有两种方案，一个是replacement，即直接修改ArtMethod里的入口字段，一个是inline hook式的，直接patch编译代码入口处的机器码。我们这里先尝试replacement方案，读出原始access_flags/entry_jni/entry_quick，然后构造HookInfo，最后把目标ArtMethod改写掉。

这里改的核心就三点：flag + entry_jni + entry_quick。用access_flags把方法伪装成native，用entry_jni塞进自己的trampoline，用entry_quick接到ART的quick JNI bridge，这样形成一个完整路径

```cpp
  目标方法调用
      ->
  entry_quick
      ->
  quickGenericJniTrampoline
      ->
  entry_jni
      ->
  Nook trampoline
      ->
  hook_handler
```

```cpp
uint64_t* quickCode = (uint64_t*)((char*)artMethod + ArtInternals::ArtMethodLayout.offset_entry_quick);
uint32_t orgFlag = *(uint32_t*)((char*)artMethod + ArtInternals::ArtMethodLayout.offset_access_flags);
uint64_t* jni = (uint64_t*)((char*)artMethod + ArtInternals::ArtMethodLayout.offset_entry_jni);

info.hookedFlag = getModifiedFlag(orgFlag);
info.hookedJNIEntry = (uint64_t)trampoline;
info.hookedEntryPoint = (uint64_t)quickEntry;

write_hooked_artmethod(info.artMethod,
                       info,
                       info.hookedFlag,
                       info.hookedJNIEntry,
                       info.hookedEntryPoint);
```

```cpp
  static void write_hooked_artmethod(void* artMethod,
                                     const HookInfo& hookInfo,
                                     uint32_t hookedFlag,
                                     uint64_t hookedJniEntry,
                                     uint64_t hookedQuickEntry) {
      *reinterpret_cast<uint32_t*>((char*)artMethod + hookInfo.layout.offset_access_flags) =
  hookedFlag;
      *reinterpret_cast<uint64_t*>((char*)artMethod + hookInfo.layout.offset_entry_jni) =
  hookedJniEntry;
      *reinterpret_cast<uint64_t*>((char*)artMethod + hookInfo.layout.offset_entry_quick) =
  hookedQuickEntry;
  }
```

**trampoline**

即中间跳板，框架不会直接把目标方法的入口改成某个高层回调函数，而是通常会先进入一小段我们自己控制的机器码，这段机器码做的是“现场接管”的工作：保存关键寄存器，带上当前Hook标识、跳到统一的native handler。他是链接ART调用现场和Hook逻辑的桥梁

```cpp
static uint8_t* GenerateTrampoline(uint64_t hook_id, void* handler_addr) {
    uint8_t* code = (uint8_t*)tool::allocate_exec_mem(TRAMPOLINE_SIZE);
    if (!code) {
        LOGE("Failed to allocate trampoline memory");
        return nullptr;
    }

    uint32_t* inst = (uint32_t*)code;
    int i = 0;

    // stp x0, x1, [sp, #-16]!  - 保存参数
    inst[i++] = 0xA9BF07E0;
    // movz x0, #hook_id
    inst[i++] = 0xD2800000 | ((hook_id & 0xFFFF) << 5);
    // ldr x1, #8
    inst[i++] = 0x58000041;
    // br x1
    inst[i++] = 0xD61F0020;
    // handler_addr 字面量
    void** addr_ptr = (void**)&inst[i++];
    *addr_ptr = handler_addr;

    return code;
}

__attribute__((naked))
void hook_trampoline_ex() {
    asm volatile(
        "mov x15, x0\n"
        "ldp x0, x1, [sp], #16\n"
        "b hook_handler\n"
    );
}
```

**ABI参数解析**

一个Hook回调想要好用，最终回是这样的一个类似效果

```cpp
callback(env, thiz, args, arg_count, result)
```

但是ART在调用方法时，并不会主动帮我们把参数打包成args[]，他只会按照ABI规则把参数放进x0-x7、v0-v7、栈空间当中，因此框架必须自己完成一次还原，先知道目标方法参数类型，再按ABI规则从寄存器/栈中读回来，最后整理成统一的回调参数表示。

比如一个方法

```java
void loadAd(String type, String position)
```

他在解析时候就需要知道：参数个数为2，两个参数都是对象，对象参数在ART调用现场要按对象引用规则处理。

先看签名转换

```cpp
static bool signature_to_shorty(const char* signature, std::string* outShorty) {
    size_t index = 1;
    while (index < length && signature[index] != ')') {
        if (!append_shorty_type(signature, length, &index, outShorty)) {
            return false;
        }
        index++;
    }

    std::string returnShorty;
    if (!append_shorty_type(signature, length, &index, &returnShorty) || returnShorty.empty()) {
        return false;
    }
    outShorty->insert(outShorty->begin(), returnShorty[0]);
    return true;
}
```

然后是参数还原，其实就是从寄存器取，超过8个就从栈里读。比较特殊的就对象参数和this，从寄存器或栈里拿出来的不能直接作为jobject，需要转换成JNI本地引用/jobject

```cpp
    // 解析参数
    size_t paramCount = hookInfo.shorty.size() - 1; // shorty[0] 是返回值
    HookValue* args = new HookValue[paramCount];
    jobject* ownedLocalRefs = new jobject[paramCount];
    memset(ownedLocalRefs, 0, sizeof(jobject) * paramCount);

    int x_reg_count = 2;  // x0(env), x1(thiz) 已用
    int v_reg_count = 0;
    int stack_reg_count = 0;

    for (size_t i = 0; i < paramCount; i++) {
        char type = hookInfo.shorty[i + 1];

        switch (type) {
            case 'F':  // float
                if (v_reg_count < 8) {
                    double* vregs[] = {&v0, &v1, &v2, &v3, &v4, &v5, &v6, &v7};
                    args[i].f = *(float*)vregs[v_reg_count];
                } else {
                    args[i].f = *(float*)((uint64_t)args_in + stack_reg_count * 8);
                    stack_reg_count++;
                }
                v_reg_count++;
                break;

            case 'D':  // double
                if (v_reg_count < 8) {
                    double* vregs[] = {&v0, &v1, &v2, &v3, &v4, &v5, &v6, &v7};
                    args[i].d = *vregs[v_reg_count];
                } else {
                    args[i].d = *(double*)((uint64_t)args_in + stack_reg_count * 8);
                    stack_reg_count++;
                }
                v_reg_count++;
                break;

            case 'L':  // 对象引用
                {
                    uint64_t obj_ptr;
                    if (x_reg_count <= 7) {
                        uint64_t* xregs[] = {&x2, &x3, &x4, &x5, &x6, &x7};
                        obj_ptr = *xregs[x_reg_count - 2];
                    } else {
                        obj_ptr = *(uint64_t*)((uint64_t)args_in + stack_reg_count * 8);
                        stack_reg_count++;
                    }
                    ownedLocalRefs[i] = create_local_ref_from_stack_ref(env, obj_ptr);
                    args[i].l = ownedLocalRefs[i];
                    x_reg_count++;
                }
                break;

            default:  // 其他整数和指针类型
                if (x_reg_count <= 7) {
                    uint64_t* xregs[] = {&x2, &x3, &x4, &x5, &x6, &x7};
                    args[i].u = *xregs[x_reg_count - 2];
                } else {
                    args[i].u = *(uint64_t*)((uint64_t)args_in + stack_reg_count * 8);
                    stack_reg_count++;
                }
                x_reg_count++;
        }
    }
```

**Hook回调分发**

当trampoline把执行流交给统一handler之后框架还要回答一个问题：当前这次的调用属于哪一个Hook？因为一个进程中可能同时安装了多个Hook。所以框架通常需要维护一张运行时记录表，把每个目标方法和它对应的Hook记录关联起来，这里记录表应该有以下内容：目标方法信息，callback指针、原始入口/原始flags、backup method、参数签名信息。当handler收到一次调用之后，就根据hook id或者当前分发地址查到这条记录，然后决定后续怎么走，是修改返回值还是调用原方法。

先查表找到HookInfo(通过之前生成trampoline时存的hookid)

```cpp
uint64_t tmpHookid;
asm volatile("mov %0, x15" : "=r"(tmpHookid));
uint32_t hookID = (uint32_t)tmpHookid;

HookInfo hookInfo = HookStore&lt;HookInfo&gt;::Instance().CopyByIndex(hookID);
if (!hookInfo.valid) {
    LOGE("Hook %d is invalid", hookID);
    return 0;
}
```

然后调用用户注册的callback

```cpp
HookValue directRet = {0};
bool callOriginal = hookInfo.callback(env, callbackThis, args, paramCount, &directRet);
```

简单总结一下这里的Hook回调分发机制：安装Hook时为每一个Hook分配唯一hook_id，并把包含callback的HookInfo存入HookStore，运行时由trampoline把hook_id带入统一hook_handler，再由hook_handler按hook_id查出对应的HookInfo，最终指向这条Hook绑定的callback。

**原方法调用**

这一步和上面的原方法备份是强相关的，它是backup的“使用方式”。

有了backup之后，框架还需要解决：参数如何编码成ART能接受的形式，如何调用原始ArtMethod，返回值如何转回Hook层可以接受的形式。这里可以借ART自己的Invoke能力，这样可以尽量复用已有的调用机制。

首先需要获取GetCurrentThread()(这个在初始化阶段已经解析出来了)，后续ArtMethod::Invoke调用需要当前Art Thread指针(这里原方法调用的方案不是重新回到Java层反射调用，而是直接在ART内部按运行时调用约定指向backup ArtMethod)，然后将参数编码为ART Invoke能接受的格式，其实就是和上面参数解析执行相反的操作流程，上一步时从ART对象引用变为JNI本地引用，这里是JNI本地引用转换为ART对象引用。最后调用Invoke方法即可。

```cpp
void* thread = ArtInternals::GetCurrentThread();
auto argsArray = new uint32_t[(paramCount + 2) * 8];
uint32_t argsize = 0;

if (!hookInfo.isStatic) {
    uint32_t compressed_this = 0;
    encode_jobject_to_invoke_ref(thread, callbackThis, &compressed_this);
    argsArray[0] = compressed_this;
    argsize += 4;
}

ArtInternals::Invoke(invokeArtMethod, thread, argsArray, argsize, &result, hookInfo.shorty.c_str());
```

这里至少有着三层转换：callback拿到的是jobject，Invoke需要的是运行时对象和按shorty排布的参数块，调完之后还要把jvalue result转换为Hook层返回值

**小结**

到这里我们已经完成了一个虽然非常粗糙但已经初具雏形的Hook框架了，接下来回答刚开始的几个问题：

1. Android上的Java方法最终是如何被执行的：最终是靠ART运行时中的方法描述结构来执行的，这个核心结构就是ArtMethod，比如当Java层发起一次方法调用时，ART会先拿到这个方法对应的ArtMethod，再根据其中保存的运行时信息去决定执行路径
2. Java Hook到底hook的是什么：是ART运行时里对这个方法的执行入口
3. Java Hook的核心原理是什么：接管目标方法在ART中的执行入口，并在必要时保留一条可以回到原始实现的路径
4. 一个最小可用的Java Hook框架至少需要哪些部件：方法定位、运行时结构识别、原方法备份、入口改写、trampoline、参数解析、Hook回调、原方法调用
5. Hook框架和注入器分别解决的是什么问题：注入器解决的时怎么把so放进目标进程并执行的问题，Hook框架解决的是进入目标进程之后怎么接管Java方法执行的问题。

## TODO

1. inline式的方案
2. 更完善的backup
3. 更简便的脚本化使用模块

---

# 回复

## 回复 by mb_jnmxfjku (#2)

*2026-3-25 16:11*

666

## 回复 by mb_ldbucrik (#3)

*2026-3-25 17:02*

感谢分享

## 回复 by mb_qimctavn (#4)

*2026-3-26 10:53*

6

## 回复 by 星辰北天 (#5)

*2026-3-29 20:19*

感谢分享

## 回复 by mb_ecyhqrqd (#6)

*2026-3-30 02:57*

感谢分享

## 回复 by dob_C (#7)

*2026-3-30 10:04*

感谢分享

## 回复 by mb_nkjfyhkg (#8)

*2026-3-31 03:42*

mark

## 回复 by ulong9527 (#9)

*2026-3-31 23:41*

66

## 回复 by Kill_Log (#10)

*2026-4-2 14:52*

666

## 回复 by mb_tjsboqui (#11)

*2026-4-7 21:21*

666

## 回复 by tjytjy (#12)

*2026-4-10 16:01*

66

## 回复 by mb_cbgtaveo (#13)

*2026-4-10 16:11*

66666666666666

## 回复 by wx_coddvccwyh (#14)

*2026-4-12 13:58*

666666

## 回复 by iBa0 (#15)

*2026-4-13 14:34*

123

## 回复 by xianhuimin (#16)

*2026-4-24 23:27*

看看

## 回复 by uni7corn (#17)

*2026-4-27 14:52*

感谢分享

## 回复 by GEKEZYX (#18)

*2026-4-30 01:28*

666

## 回复 by Xx_gg (#19)

*2026-4-30 16:22*

66666

## 回复 by merryfish (#20)

*2026-5-19 02:31*

666666

## 回复 by Imxz (#21)

*2026-5-26 14:10*

tql

## 回复 by git_94327axixa518 (#22)

*2026-5-28 19:11*

3q

## 回复 by mb_kgneopde (#23)

*2026-6-12 17:22*

666

## 回复 by simpleness (#24)

*2026-7-16 19:15*

6

## 回复 by mb_degalzhb (#25)

*2026-7-20 10:55*

感谢分享《[原创]从0到1构建一个Hook工具之Java Hook篇（三）》。文中的分析过程和关键思路很有参考价值，我会结合实际环境进一步验证和学习。
