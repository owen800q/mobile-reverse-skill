---
title: '[原创] JDex：基于Xposed / Lsposed的主动调用抽取壳脱壳工具'
url: https://bbs.kanxue.com/thread-290669.htm
tid: 290669
author: JSnow
date: '2026-04-06'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆, 程序开发, HOOK注入, 工具脚本]
crawled_at: '2026-08-08T10:12:21+00:00'
replies: 205
---

**本工具仅用于安全研究和学习目的，请勿用于非法用途**

# JDex2

得益于Frida优秀的Java以及Native层Hook功能，现在基于Frida的脱壳脚本层出不穷，但是对Frida的检测也日益加强，现在都不必说企业壳，免费壳都配备了不少Frida检测。而Fart类基于修改Android源码进行主动调用脱壳的方案虽然非常完美，但是编译，刷机等操作却会对于刷机小白来说门槛较高，而且对源码的修改考虑不周就可能造成无法预知的错误，而且比较难Debug（而且因为需要Linux进行编译，对电脑配置不高使用虚拟机的人来说也会不大友好）

这时Lsposed相对隐蔽的Hook手段和较低的开发成本就会让**脱壳**这门技术和**过检测**被划分开来，入门和实操难度也会低很多（但是也有部分厂商是上了比较强的针对lsposed的检测手段的，所以只能应对大多数企业抽取壳情况，而不是全部）

Github仓库地址写在帖子末尾，本项目依赖于Xposed/Lsposed主动调用构造方法进行抽取壳的脱壳，但是并不是非常完善，很多功能还有待完善和优化。如果你对本项目感兴趣，非常欢迎参与讨论、魔改、二次开发、提交 Issue 或分享你的思路

**本项目的应用场景：**

应对多数未对Lsposed进行有效检测的企业抽取壳和免费壳的Dex加固

工作流程：

```python
Xposed注入 → 获取真实ClassLoader → 遍历DexFile → 主动调用构造方法触发回填 → Native层Dump
\```

## 反射脱壳部分

首先在Android上，Dex的动态加载大部分都是依赖于ClassLoader的，最常见的是通过`DexClassLoader`，`PathClassLoader`和`InMemoryClassLoader`进行加载。大多数的壳无非就是将Dex进行不同粒度的加密，但是实际交给`ART`虚拟机解释执行的时候都要进行动态解密。这就是我们脱壳的核心原理，在Dex解密的时候将其从内存中Dump下来。

>
> 以下所有源码部分演示均以android-9.0.0_r61作为演示
>
>
>

### 寻找真正的ClassLoader

对于每一个App，都有一个非常核心的类：**LoadedApk**

它被用于描述该应用在当前进程中的所有运行时信息，其中就有我们非常感兴趣的APP的真实ClassLoader，并且还为我们提供了`getClassLoader`方法，返回当前`LoadedApk`中的`mClassLoader`字段

```java
807      public ClassLoader getClassLoader() {
808          synchronized (this) {
809              if (mClassLoader == null) {
810                  createOrUpdateClassLoaderLocked(null /*addedPaths*/);
811              }
812              return mClassLoader;
813          }
814      }
\```

至于为什么大多数APP`LoadedApk`中的ClassLoader就是真实的ClassLoader：

系统在启动 Activity 时，**不会使用你自定义的 ClassLoader**，而是使用 `LoadedApk` 中的 `mClassLoader`。你的 `DexClassLoader` 加载的类对系统框架层来说是"不可见"的，当App启动自定义的Activity，Service时就会找不到这些类。所以常见的壳会选择将解密后dex的`ClassLoader`插入到`LoadedApk`的`mClassLoader`中，或者在双亲委派链中加入自定义的ClassLoader。**而大部分主流加固方案都采用替换 `mClassLoader` 的方式**

因为壳需要**解密 DEX 并创建全新的 ClassLoader**，这与"替换"方案天然契合。而"插入委派链"方案无法解决"原始 ClassLoader 不认识解密后 DEX"这一根本问题，且控制力，兼容性和安全性都不如直接替换

获取`LoadedApk`的方案有很多种，我们这里选择这条反射链获取ClassLoader，因为偶然间在`Android`源码中看到了这种获取LoadedApk的方式，所以可能会更稳定一些

```java
181        ReflectionHelpers.setField(activityThread, "mBoundApplication", data);
182
183        LoadedApk loadedApk = activityThread.getPackageInfo(applicationInfo, null, Context.CONTEXT_INCLUDE_CODE);
\```

```python
ActivityThread.currentActivityThread()
    → mBoundApplication (AppBindData)
        → info (LoadedApk)
            → getClassLoader()
\```

因为Xposed对于反射获取字段的封装非常友好，所以我们不需要自己写大量反射，只需要借助Xposed的API：

```java
    private ClassLoader getRealClassLoader(XC_LoadPackage.LoadPackageParam lpparam) {
        try {
            Class<?> atClass = Class.forName("android.app.ActivityThread");
            Object at = atClass.getMethod("currentActivityThread").invoke(null);
            if (at == null)
                throw new RuntimeException("ActivityThread is null");

            Object boundApp = XposedHelpers.getObjectField(at, "mBoundApplication");
            if (boundApp == null)
                throw new RuntimeException("mBoundApplication is null");

            Object loadedApk = XposedHelpers.getObjectField(boundApp, "info");
            if (loadedApk == null)
                throw new RuntimeException("LoadedApk is null");

            ClassLoader cl = (ClassLoader) XposedHelpers.callMethod(loadedApk, "getClassLoader");
            if (cl != null) {
                Log.e(TAG, "Got real ClassLoader: " + cl);
                Log.e(TAG, "ClassLoader type: " + cl.getClass().getName());
                return cl;
            }
        } catch (Throwable t) {
            Log.e(ErrTAG, "getRealClassLoader failed", t);
        }
        Log.w(TAG, "Fallback to lpparam.classLoader");
        return lpparam.classLoader;
    }
\```

当然其实`loadPackageParam.classLoader`也是从`LoadedApk`中拿ClassLoader，虽然通过两种方式都可以获取，但是这里为了考虑到`LoadedApk`的ClassLoader可能被替换，而xposed获取的时机不一定是我们想要的时机，所以反射调用获取会更保险

最初想过做一个Frida那样可以枚举ClassLoader的功能：

从当前虚拟机的 Runtime 中获取唯一的 `ClassLinker*`，在一个 ART 线程中、并在线程被 JVM 暂停的状态下主动调用 `ClassLinker::VisitClassLoaders`，传入一个始终返回 `true` 的 visitor 回调。 该 visitor 是 Frida 构造的 **native 回调函数指针**，其签名为 `bool visitor(mirror::ClassLoader* loader)`，（不包含 this 指针）。 ART 在遍历每一个已注册的 `mirror::ClassLoader*` 时，主动调用该 visitor，并将当前遍历到的 ClassLoader 作为参数传入。 Frida 在回调中将这些 loader 提升为 JNI 全局引用并保存，遍历结束后在 Java 世界中将它们包装为 `java.lang.ClassLoader` 对象数组返回

但是Xposed实现该功能时间成本较高，而且很多壳并不需要这种方式去脱壳，`LoadedApk`已经够用，所以这里就暂时不做实现了

### 从ClassLoader -> Art::DexFile

首先众所周知的三大ClassLoader就是

- DexClassLoader
- PathClassLoader
- InMemoryClassLoader

而它们都继承自`BaseDexClassLoader`，没有使用更上层的ClassLoader是因为在`BaseDexClassLoader`有很方便的`DexPathList`用于获取DexFile

```java
46      private final DexPathList pathList;
\```

其中的`dexElements`属于`Element`这个内部类，其中我们就可以遍历所有`dexElements`的拿到该ClassLoader对应的所有`DexFile`

```java
64      private Element[] dexElements;

//
static class Element {
607          /**
608           * A file denoting a zip file (in case of a resource jar or a dex jar), or a directory
609           * (only when dexFile is null).
610           */
611          private final File path;
612
613          private final DexFile dexFile;
614
615          private ClassPathURLStreamHandler urlHandler;
616          private boolean initialized;
......
\```

可是我们都知道ART虚拟机中的DexFile和我们真正需要的Dex相差甚远，而从Android8系列开始Android源码中去除了`DexFile`类中的`getBytes`方法，想拿到我们需要的Dex最好的方法就是拿到Native层的`Art::DexFile`。而恰好`DexFile`中有两个比较有趣的字段，是`mCookie`和`mInternalCookie`，这两个字段虽然是Object类型，但是其实是`long[]`，内部存储的数据就是指向`Art::DexFile`绝对地址的指针，所以我们就可以通过将其强转为`long[]`之后传到Native层去进行读写来Dump（强转之前先做验证）

```java
41  public final class DexFile {
42    /**
43     * If close is called, mCookie becomes null but the internal cookie is preserved if the close
44     * failed so that we can free resources in the finalizer.
45     */
46      @ReachabilitySensitive
47      private Object mCookie;
48
49      private Object mInternalCookie;
\```

我们就可以封装这样两个函数来从`BaseDexClassLoader`中Dump我们需要的Dex文件

```java
    /**
     * 遍历 ClassLoader 的所有 dexElements 并全部 dump
     */
    private List&lt;DexFile&gt; getAllDexFiles(ClassLoader loader) {
        List&lt;DexFile&gt; dexFiles = new ArrayList<>();
        try {
            if (!(loader instanceof BaseDexClassLoader)) {
                Log.e(TAG, "Not BaseDexClassLoader: " + loader.getClass().getName());
                return dexFiles;
            }
            Object pathList = XposedHelpers.getObjectField(loader, "pathList");
            Object[] dexElements = (Object[]) XposedHelpers
                    .getObjectField(pathList, "dexElements");
            Log.e(TAG, "dexElements count: " + dexElements.length);

            for (Object element : dexElements) {
                // 某些 element 本身也可能是 null
                if (element == null)
                    continue;
                Object dexFileObj = XposedHelpers.getObjectField(element, "dexFile");
                if (dexFileObj instanceof DexFile) {
                    dexFiles.add((DexFile) dexFileObj);
                }
            }
            Log.e(TAG, "Valid DexFile count: " + dexFiles.size());

        } catch (Throwable t) {
            Log.e(ErrTAG, "getAllDexFiles failed", t);
        }
        return dexFiles;
    }

    private void dumpDex(DexFile dexFile, String outDir) {
        // 防止重复dump，减少性能开销
        synchronized (dumpedDexFiles) {
            if (dumpedDexFiles.contains(dexFile))
                return;
            dumpedDexFiles.add(dexFile);
        }
        try {
            // 通过mCookie去拿到指针进行Dump
            Object cookie = XposedHelpers.getObjectField(dexFile, "mCookie");
            if (cookie instanceof long[]) {
                long[] c = (long[]) cookie;
                dumpDexByCookie(c, outDir);
            }
        } catch (Throwable t) {
            Log.e(ErrTAG, "dumpDex failed", t);
        }
    }
\```

64位下`Art::DexFile`的内存结构大致如下，我们可以使用偏移直接读，但是这里我选择使用`dex\n`头进行判断，避免Dump下来一大堆无效数据，当然有需求的话可以修改代码重新编译即可，直接通过对应偏移读取

```cpp
Offset  |  Size  |  成员
----------------------------------------------
0x00     	8      vptr (隐式, 指向 vtable)
0x08     	8      begin_ (const uint8_t* const)
0x10     	8      unused_size_ (size_t)
\```

因为我们Native层的读取方式相对Android对开发者的期望来说，可以说是另辟蹊径，所以自然会导致很多问题，其中最重要的问题就是读取到不可读的地址，因为有些地址可能已经被释放了，但是还是被`mCookie`持有，因为Android本来就没指望有人这样去读取，所以在对一些APP的测试中直接读取就会导致崩溃

所以我们需要在读取前借助`pipe`进行内核层读写，如果地址不可读，内核会返回 `-EFAULT`，不会让我们想要脱壳的进程崩溃

```cpp
#include &lt;jni.h&gt;
#include &lt;cstdio&gt;
#include &lt;cstring&gt;
#include &lt;cstdint&gt;
#include &lt;sys/stat.h&gt;
#include &lt;unistd.h&gt;
#include &lt;signal.h&gt;
#include &lt;setjmp.h&gt;
#include &lt;android/log.h&gt;
#include &lt;vector&gt;

#define TAG "JDex2 Native"
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

/**
 * 通过 write + pipe 检测地址是否可读，如果直接读取到不可读的内存APP会崩溃
 */
static bool isAddressReadable(const void* addr, size_t len) {
    if (addr == nullptr) return false;
    if ((uintptr_t)addr < 0x10000) return false;

    // 限制单次检查大小，pipe 缓冲区有限
    if (len > 4096) len = 4096;

    int fd[2];
    // fd[0]为读句柄，fd[1]为写句柄
    if (pipe(fd) != 0) return false;

    ssize_t ret = write(fd[1], addr, len);

    close(fd[0]);
    close(fd[1]);

    return ret == (ssize_t)len;
}
static bool isDexRegionReadable(const uint8_t* begin, uint32_t fileSize) {
    // 整个检测会爆缓冲区，只抽样检查
    if (!isAddressReadable(begin, 0x70)) return false;
    if (fileSize > 4) {
        if (!isAddressReadable(begin + fileSize - 4, 4)) return false;
    }
    if (fileSize > 0x1000) {
        if (!isAddressReadable(begin + fileSize / 2, 4)) return false;
    }

    return true;
}
static bool isDexMagic(const uint8_t* data) {
    // 只脱dex，抽取壳不会优化成cdex的
    return (data[0] == 'd' && data[1] == 'e' && data[2] == 'x' && data[3] == '\n');
}

static uint32_t getDexFileSize(const uint8_t* begin) {
    return *reinterpret_cast&lt;const uint32_t*&gt;(begin + 0x20);
}

static const uint8_t* findBegin(jlong dexFilePtr) {

    // 不一定获取到的所有指针都是可读的，读之前都要先做验证

    if (!isAddressReadable((const void*)dexFilePtr, 64)) {
        LOGE("dexFilePtr 0x%llx is not readable", (unsigned long long)dexFilePtr);
        return nullptr;
    }

    for (int offset = 0; offset < 64; offset += sizeof(void*)) {
        const uint8_t* candidate = *((const uint8_t**)((uint8_t*)dexFilePtr + offset));

        if (candidate == nullptr) continue;

        if ((uintptr_t)candidate < 0x10000) {
            LOGE("offset %d: candidate 0x%llx too small, skip",
                 offset, (unsigned long long)candidate);
            continue;
        }

        if (!isAddressReadable(candidate, 0x70)) {
            LOGE("offset %d: candidate 0x%llx not readable, skip",
                 offset, (unsigned long long)candidate);
            continue;
        }

        if (isDexMagic(candidate)) {
            LOGE("Found begin_ at offset %d, addr=0x%llx",
                 offset, (unsigned long long)candidate);
            return candidate;
        }
    }
    return nullptr;
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_jsnow_jdex2_MainActivity_stringFromJNI(JNIEnv *env, jobject thiz) {
    return env->NewStringUTF("Hello from JDex!");
}
extern "C"
JNIEXPORT void JNICALL
Java_com_jsnow_jdex2_JSHook_dumpDexByCookie(JNIEnv *env, jclass clazz, jlongArray cookie,
                                            jstring outDir) {

    if (cookie == nullptr) return;

    const char* outDirStr = env->GetStringUTFChars(outDir, nullptr);
    jsize cookieLen = env->GetArrayLength(cookie);
    jlong* cookieElements = env->GetLongArrayElements(cookie, nullptr);

    mkdir(outDirStr, 0755);

    LOGE("cookie length = %d", cookieLen);

    // 遍历DexFile去Dump Dex
    // 头部第一个pointer其实一个隐藏的 vptr 指针，为求保险也可以读一下
    for (int i = 0; i < cookieLen; i++) {
        jlong dexFilePtr = cookieElements[i];
        if (dexFilePtr == 0) continue;

        LOGE("Processing cookie[%d] = 0x%llx", i, (unsigned long long)dexFilePtr);
        // 通过dex头判断会更保险一点，避免dump下来一大堆乱七八糟的东西，而且测试了一下大部分的壳都没有抹去dex头
        const uint8_t* begin = findBegin(dexFilePtr);
        if (begin == nullptr) {
            LOGE("cookie[%d]: cannot find valid dex data, skip", i);
            continue;
        }

        uint32_t fileSize = getDexFileSize(begin);
        LOGE("cookie[%d]: file_size = %u", i, fileSize);
        if (fileSize < 0x70 || fileSize > 100 * 1024 * 1024) {
            LOGE("cookie[%d]: unreasonable file_size=%u, skip", i, fileSize);
            continue;
        }

        if (!isDexRegionReadable(begin, fileSize)) {
            LOGE("cookie[%d]: dex region not readable, skip", i);
            continue;
        }

        uint32_t checksum = *reinterpret_cast&lt;const uint32_t*&gt;(begin + 0x08);
        char outPath[100];
        snprintf(outPath, sizeof(outPath), "%s%u.dex",
                 outDirStr, fileSize);

        FILE* check = fopen(outPath, "r");
        if (check != nullptr) {
            fclose(check);
            LOGE("Already dumped: %s, skip", outPath);
            continue;
        }

        FILE* fp = fopen(outPath, "wb");
        if (fp) {
            // 将Dump下来的Dex写入对应目录
            size_t written = 0;
            size_t chunkSize = 4096;
            while (written < fileSize) {
                size_t toWrite = fileSize - written;
                if (toWrite > chunkSize) toWrite = chunkSize;
                size_t ret = fwrite(begin + written, 1, toWrite, fp);
                if (ret != toWrite) {
                    LOGE("cookie[%d]: fwrite error at offset %zu", i, written);
                    break;
                }
                written += ret;
            }
            fclose(fp);
            LOGE("Dumped: %s (size=%u, written=%zu)", outPath, fileSize, written);
        } else {
            LOGE("Failed to write: %s", outPath);
        }
    }
    env->ReleaseLongArrayElements(cookie, cookieElements, 0);
    env->ReleaseStringUTFChars(outDir, outDirStr);

}
\```

此时在Xposed成功注入到对应APP进程后新建一个Thread，sleep一会之后进行Dump就是最初的`JDex1`了，这也是为什么本项目叫`JDex2`的原因，因为之前的一版脱壳功能实在不尽人意，对于不少大家可能感兴趣的APP来说，只能脱下来已经触发逻辑的那一些类。我一般分析还是比较喜欢从字符串入手的，这样的话对和我一样的字符串党非常不友好。所以就需要上**主动调用**之路了

### 主动调用

#### 最初的一些设想

>
> 此小节为未实现的探索方案，仅供参考
>
>
>

其实最初的设计是借助一些inlineHook框架对`ArtMethod::Invoke`解释执行链路上的`EnterInterpreterFromEntryPoint`函数进行Hook，通过第三个参数`ShadowFrame`去获取`ArtMethod`和`dex_pc_ptr_`，然后`return 0`中断执行流。

该函数在Native层的实现如下

```cpp
585  JValue EnterInterpreterFromEntryPoint(Thread* self, const CodeItemDataAccessor& accessor,
586                                        ShadowFrame* shadow_frame) {
587    DCHECK_EQ(self, Thread::Current());
588    bool implicit_check = !Runtime::Current()->ExplicitStackOverflowChecks();
589    if (UNLIKELY(__builtin_frame_address(0) < self->GetStackEndForInterpreter(implicit_check))) {
590      ThrowStackOverflowError(self);
591      return JValue();
592    }
593
594    jit::Jit* jit = Runtime::Current()->GetJit();
595    if (jit != nullptr) {
596      jit->NotifyCompiledCodeToInterpreterTransition(self, shadow_frame->GetMethod());
597    }
598    return Execute(self, accessor, *shadow_frame, JValue());
599  }
\```

ShadowFrame的内存结构如下

```cpp
class ShadowFrame {
    // ShadowFrame 类没有任何虚函数，因此没有 vptr
    [0x00] ShadowFrame* link_;                 // 上一个 ShadowFrame（调用栈）
    [0x08] ArtMethod* method_;                 // 当前执行的方法
    [0x10] JValue* result_register_;           // 返回值寄存器

    [0x18] const uint16_t* dex_pc_ptr_;         // Dex 指令指针
    [0x20] const uint16_t* dex_instructions_;   // Dex 指令起始地址
\```

如果需要dump，就需要在之前通过`mCookie`去DumpDex的时候将所有Dump下来的Dex的begin和size都存起来，在这里通过`dex_pc_ptr_`指向的地址范围来快速判断方法位于哪个Dex。

这样或许可以避免像`frida-fart`那样借助自实现的`GetObsoleteDexCache`去确认方法属于哪个`DexFile`，同时也能通过`dex_pc_ptr_ - begin`快速定位offset回填。但是实测了一些inline hook框架，即使hook后不进行任何操作直接调用原函数，也不进行主动调用，也会在Hook之后一段时间之后崩溃，可能是调用约定或是其它原因，所以最后没有实现

此设想因为本项目最终并没有实现，所以也就不做赘述了，大家感兴趣的话可以详细了解该部分Android源码

#### 实现主动调用

在`DexFile.java`中有这样一个函数，可以帮我们通过`cookie`获取该`DexFile`的所有类，从而让我们可以快速得到一个`String[]`，进而进行构造方法的批量调用。这个cookie参数或许也可以引发大家的思考，进而发现`cookie`和真实`Art::DexFile`的关系

```java
395      private static native String[] getClassNameList(Object cookie);
\```

因为我们在实现Native层的Hook的时候遇到了比较难解决的问题，所以我们主动调用所有方法并且进行方法粒度dump的想法就化为了泡影 QwQ ，那我们只能在Java层通过对原App尽量少的操作进行脱壳。前面提到很多抽取壳都是基于**类**级别进行抽取的，只要触发类中的任意一个方法就可以了

对原App破坏最小的方法调用就是**构造方法**了，因为静态方法并不是每个类都有，使用静态方法进行脱壳的话就会很被动，而且调用静态方法由于不可预知的效果，对类的影响扩散可能会直接导致App崩溃，并且仅通过`loadClass`是无法让大部分抽取壳回填的（父类方法是肯定不行的，不然调用一个Object的方法所有类都解密了还加什么壳）

最初尝试单纯调用构造方法new实例，但是错误的参数可能会导致大量的异常甚至崩溃，并且Activity等系统类实例化是需要Looper和各种各样符合要求的参数的，而我们批量主动调用要获取这些乱七八糟的参数是非常费力的。所以我们可以添加一个Hook，来让方法不实际执行，避免导致的各种不可控的崩溃。

然后在实测中被某些壳检测到了，导致app崩溃了......

但是之前对该壳的免费版有一些了解，该壳会通过检测方法是否被非法转为Native方法从而判断是否被Hook，所以我们需要在`newInstance`之后解除Hook，以规避这种检测

##### 构造参数

在我们反射获取的构造方法中，Android为我们提供了一个非隐藏的方法`getParameterTypes`供我们调用

```java
136      public Class<?>[] getParameterTypes() {
137          // Android-changed: getParameterTypes() partly implemented using Executable.
138          Class<?>[] paramTypes = super.getParameterTypesInternal();
139          if (paramTypes == null) {
140              return EmptyArray.CLASS;
141          }
142
143          return paramTypes;
144      }
\```

所以我们可以将它的返回值传递进来进行参数的构造，尽量减少错误的发生（避免在Hook执行执行前遇到的参数检查导致直接异常）

```java
    private Object[] makeDefaultArgs(Class<?>[] paramTypes) {
        Object[] args = new Object[paramTypes.length];
        for (int i = 0; i < paramTypes.length; i++) {
            Class<?> t = paramTypes[i];
            // 对于引用类型，传入null是合法的（没必要再去构造对应类型参数）
            if (t == boolean.class)
                args[i] = false;
            else if (t == byte.class)
                args[i] = (byte) 0;
            else if (t == char.class)
                args[i] = (char) 0;
            else if (t == short.class)
                args[i] = (short) 0;
            else if (t == int.class)
                args[i] = 0;
            else if (t == long.class)
                args[i] = 0L;
            else if (t == float.class)
                args[i] = 0.0f;
            else if (t == double.class)
                args[i] = 0.0;
            else
                args[i] = null;
        }
        return args;
    }
\```

##### 主动调用

而在主动调用的时候我们要注意接口，注解类，抽象类，枚举类是没有构造函数的，并且本来也没有CodeItem，所以我们直接跳过这些方法避免崩溃

```java
    // 在类级别定义一个共享实例，避免每次循环都创建新对象
    private static final XC_MethodHook BLOCK_CONSTRUCTOR = new XC_MethodHook() {
        @Override
        protected void beforeHookedMethod(MethodHookParam param) {
            param.setResult(null); // 构造方法返回 void，用 null
        }
    };

private void invokeAllConstructors(String[] names, BaseDexClassLoader loader, List&lt;String&gt; blackList) {
        for (String name : names) {
            try {
                // 将黑名单进行剔除，因为在某些APP的某些类中，可能会继承一些当前Android版本不存在的类
                // 这时候尝试new实例会直接导致APP崩溃
                if (matchPrefix(blackList, name)) continue;
                Class<?> clazz = XposedHelpers.findClass(name, loader);
                int mod = clazz.getModifiers();
                if (clazz.isInterface() || clazz.isAnnotation()
                        || clazz.isEnum() || Modifier.isAbstract(mod))
                    continue;

                Constructor<?>[] constructors = clazz.getDeclaredConstructors();
                if (constructors.length == 0) continue;

                // 选择任意一个构造方法即可
                Constructor<?> target = constructors[0];
                target.setAccessible(true);

                Set<XC_MethodHook.Unhook> unhooks = XposedBridge.hookAllConstructors(clazz, BLOCK_CONSTRUCTOR);
                try {
                    // 获取参数列表，通过正确的参数类型调用可以避免在调用中途遇到无法预期的拦截
                    Object[] args = makeDefaultArgs(target.getParameterTypes());
                    if (invokeDebugger) Log.e(DebugTag, "Invoke Class: " + clazz);
                    // 调用构造方法，触发代码的回填
                    target.newInstance(args);
                } catch (Throwable ignored) {
                } finally {
                    // 为了防止某些加固通过检测方法是否被转为Native方法来检测Hook，无论构造是否成功都要解除Hook
                    for (XC_MethodHook.Unhook unhook : unhooks) {
                        unhook.unhook();
                    }
                }
            } catch (Throwable e) {
                Log.e(ErrTAG, "Failed: " + name, e);
            }
        }
    }
\```

到这里基本上反射脱壳的方案就结束了，只需要对其主动调用后触发回填，然后DumpDex即可了

```java
try {
                        // sleep 10秒，等待壳加载结束
                        Thread.sleep(10000);
                        ensureNativeLoaded();
                        if (!nativeLoaded) {
                            Log.e(TAG, "Native library not loaded, abort!");
                            return;
                        }
                        // 通过LoadedApk获取APP的真实ClassLoader
                        ClassLoader realLoader = getRealClassLoader(loadPackageParam);
                        if (!(realLoader instanceof BaseDexClassLoader)) {
                            Log.e(TAG, "realLoader is not BaseDexClassLoader, skip invokeAllMethod");
                            return;
                        }
                        // 通过DexFile的Cookie将所有Dex文件Dump下来
                        List&lt;DexFile&gt; allDexFile = getAllDexFiles(realLoader);
                        // 调用DexFile内部的getClassNameList方法获取所有的Class名称，然后去进行主动调用
                        for (DexFile dexFile : allDexFile) {
                            if (dexFile != null) {
                                // 获取每一个DexFile的方法之后主动调用
                                String[] names = getAllClassName(dexFile, whiteList, blackList);
                                invokeAllConstructors(names, (BaseDexClassLoader) realLoader,blackList);
//                                invokeTest(realLoader, "");
                                // 将Dex文件dump到输出目录
                                dumpDex(dexFile, outDir);
                            }
                        }
                        Log.e(TAG, "All Dex dumps completed!");
                    } catch (Throwable e) {
                        Log.e(ErrTAG, "Reflect dump failed", e);
                    }
\```

## Hook脱壳部分

为什么还要设置这样一个分支呢，因为之前在一些App中碰到了自身一些在Java或Native层进行动态加载的情况，因为并不像整体加壳那样想要加载Activity，Service等组件，所以不会在`LoadedApk`字段中。我们就需要通过Hook去获取ClassLoader

该方法的弊端也很明显，因为xposed/lsposed系列实现 Java Hook 的原理就是将方法转为Native方法后指向自己的处理函数去处理，所以Hook了不解除就很容易被检测出来，所以该分支一般情况下不推荐使用

这里我们选择Hook的是`BaseDexClassLoader`的构造方法和这些方法

```java
            String[] methodNames = {
                    "makeDexElements",        // DexClassLoader
                    "makePathElements",       // PathClassLoader
                    "makeInMemoryDexElements" // InMemoryDexClassLoader
            };
\```

因为很多壳为了防止Hook ClassLoader导致壳被直接脱下来，以及兼容性问题，所以会选择使用这些方法向DexPathList 中的 dexElements 数组中直接插入DexFile，这样就会避免调用三大ClassLoader的构造方法。

这两个方法在Android源码中的定义如下

```java
319      private static Element[] makeDexElements(List&lt;File&gt; files, File optimizedDirectory,
320              List&lt;IOException&gt; suppressedExceptions, ClassLoader loader) {
321          return makeDexElements(files, optimizedDirectory, suppressedExceptions, loader, false);
322      }
323
324
325      private static Element[] makeDexElements(List&lt;File&gt; files, File optimizedDirectory,
326              List&lt;IOException&gt; suppressedExceptions, ClassLoader loader, boolean isTrusted) {
327        Element[] elements = new Element[files.size()];
328        int elementsPos = 0;
......
\```

此时的`thisObject`是 `DexPathList`实例，通过 `definingContext`字段拿到对应的 ClassLoader，然后仿照之前的反射获取dex即可，这里就不做赘述了

这种情况下为了脱壳完整性也加了反射dumpdex

## 项目地址 & 使用方法简介

由于配置文件存在本地，需要读写存储权限

`MainActivity`中有如下配置，会根据输入将配置写到`/sdcard/config.properties`路径下，也可以手动编辑，除了目标包名，其它配置多个路径可以通过`,`间隔

白名单和黑名单只是不做主动调用，但是仍然会进行dump

 ![图片描述](https://bbs.kanxue.com/upload/attach/202604/1033854_G4J8BPWYNQAGNZR.webp)

- 需要将与目标App对应架构的so放到`/data/local/tmp/`目录下
	- 仅测试了在arm64下的稳定性尚佳
- targetApp：目标APP包名
- targetClass：指定要脱的壳的包路径`com.xxx`（不设置可能会导致 JNI 引用过多，通常建议以App的包名前两层作为筛选）
- blackListClass：填写某些导致App崩溃的类，如果崩溃则需要通过`JDex2 Debugger`的日志对某些类或者包进行筛选（由于写到本地性能开销过大所以没有写）
- Debugger：输出完成主动调用的类列表（`tag~=JDex2 Debugger`）
	- 当对某些APP脱壳过程中出现崩溃的情况，需要参考主动调用的类列表进行分析，可能是因为某些Android的系统类在低版本下不存在，而APP的业务逻辑中做了定义但不会在低版本Android调用
	- 比如某APP的`com.xxx.xxx.conferencesw`包下的类
- Hook：使用Hook方式脱壳（不推荐使用）
- innerClassesFilter：由于可能导致 JNI 引用数量过多，可以尝试关闭对内部类的主动调用，但是对某些壳，脱出来的匿名类依旧是空的，按需开启，建议使用黑名单过滤而不是本配置

如果使用的是Lsposed，**记得在Lsposed中勾选对应APP**

脱壳效果展示： ![图片描述](https://bbs.kanxue.com/upload/attach/202604/1033854_2N3EYJ434BPC38S.webp)

## 本工具的局限性

- 只能对抗类级别的方法抽取，而基于方法粒度的抽取则会无法进行，并且无法应对方法执行结束后重新抽取的情况，还有真正开始执行字节码才动态解密的情况
- 各个方面的便捷性不足，一些崩溃问题可能需要参考崩溃日志进行分析，而且不算很完善
- 基于Android9.0+开发，未适配Android7系列及以下，Android8稳定性未知
- JNI全局引用数量超过最大上限 51200 个导致崩溃

	- 如果类的数量过于庞大，由于每次主动调用每个类都创建一个新的匿名 `XC_MethodHook` 实例，即使使用了`XC_MethodHook`共享实例，但是只是减少了 callback 对象的创建，每次 `hookAllConstructors` 底层仍然会创建全局引用。所以这种情况下要么选择过滤内部类，要么**使用黑名单去跳过之前dump过的包**（个人推荐），或者使用白名单每次只dump几个包下的类
- 高度依赖于Lsposed的隐蔽性，如果Lsposed被检测则会直接闪退无法进行脱壳
- 对于一些该系统下不存在的类的主动调用实例化可能导致崩溃，需要通过观察`invokeDebugger`的结束类去将其加入黑名单
- UI写的有点草率

## 更新

更新会直接更新在Github中

## 项目地址

⭐ 如果本项目对您有帮助，请点个 Star，感谢您的支持！

- [Github: JDex2 Release](https://github.com/J5now/JDex2)

---

# 回复

## 回复 by SomeMx (#2)

*2026-4-6 21:25*

学习一下

## 回复 by tonykros (#3)

*2026-4-6 21:42*

666

## 回复 by jyotidwi (#4)

*2026-4-6 21:51*

tql

## 回复 by mb_asiwnxyv (#5)

*2026-4-6 22:32*

学习一下

## 回复 by 小迷糊ddd (#6)

*2026-4-6 22:47*

感谢分享，学习一下。

## 回复 by wx_妳还是不懂 (#7)

*2026-4-6 23:02*

非常感谢

## 回复 by FMNS (#8)

*2026-4-7 07:51*

非常感谢

## 回复 by 九黎 (#9)

*2026-4-7 08:27*

tql

## 回复 by mb_ldbucrik (#10)

*2026-4-7 10:46*

感谢分享

## 回复 by XCicada (#11)

*2026-4-7 11:08*

感谢

## 回复 by virjar (#12)

*2026-4-7 11:29*

666

## 回复 by mb_roiscepd (#13)

*2026-4-7 11:55*

666

## 回复 by 墨穹呢 (#14)

*2026-4-7 13:25*

感谢分享

## 回复 by mb_pesxllvn (#15)

*2026-4-7 13:42*

666

## 回复 by mmm_6 (#16)

*2026-4-7 13:56*

大佬太强了

## 回复 by puppet_w (#17)

*2026-4-7 13:57*

66

## 回复 by jdong (#18)

*2026-4-7 14:09*

666

## 回复 by iBa0 (#19)

*2026-4-7 14:51*

666

## 回复 by xianhuimin (#20)

*2026-4-7 14:56*

看看

## 回复 by Am1re (#21)

*2026-4-7 15:01*

666

## 回复 by mb_4nrpVMxJ (#22)

*2026-4-7 15:13*

666

## 回复 by xingbing (#23)

*2026-4-7 15:27*

学习一下 ！！！

## 回复 by jack_432875 (#24)

*2026-4-7 15:35*

感谢分享  !!

## 回复 by xiaotuo (#25)

*2026-4-7 15:58*

感谢分享

## 回复 by quanCode (#26)

*2026-4-7 16:08*

点赞分享

## 回复 by LQ6H (#27)

*2026-4-7 16:33*

666

## 回复 by 学着学逆向 (#28)

*2026-4-7 16:57*

感谢分享

## 回复 by YANG、 (#29)

*2026-4-7 17:28*

感谢分享  !!

## 回复 by Kill_Log (#30)

*2026-4-7 19:48*

666

## 回复 by mb_mlyojneh (#31)

*2026-4-7 20:57*

感谢分享

## 回复 by wx_插曲 (#32)

*2026-4-7 22:37*

666

## 回复 by 希梦☆奈何 (#33)

*2026-4-7 23:27*

路过学习

## 回复 by mb_elqwyvnm (#34)

*2026-4-8 05:42*

xiaotuo
  25 楼
感谢分享

## 回复 by huangjw (#35)

*2026-4-8 08:24*

![image](https://bbs.kanxue.com/view/img/face/078.gif)

## 回复 by amwpecel (#36)

*2026-4-8 09:36*

感谢分享

## 回复 by mb_cbgtaveo (#37)

*2026-4-8 09:36*

6666666666666666

## 回复 by han_shuang (#38)

*2026-4-8 09:47*

666

## 回复 by mb_fidppcok (#39)

*2026-4-8 09:49*

大佬太强了

## 回复 by 猫子 (#40)

*2026-4-8 10:01*

学习一下

## 回复 by 随风而行aa (#41)

*2026-4-8 10:33*

看看

## 回复 by YoungBai (#42)

*2026-4-8 10:37*

666

## 回复 by Snowman_Liam (#43)

*2026-4-8 10:47*

666

## 回复 by 慵懒 (#44)

*2026-4-8 10:51*

感谢分享

## 回复 by woaiziyou (#45)

*2026-4-8 11:17*

非常感谢

## 回复 by 卡坦精 (#46)

*2026-4-8 11:35*

666

## 回复 by Imxz (#47)

*2026-4-8 11:36*

rbq

## 回复 by AyonA333 (#48)

*2026-4-8 18:26*

学习

## 回复 by mb_gluymaeh (#49)

*2026-4-8 18:37*

你的分享对大家帮助很大，非常感谢！

## 回复 by koflfy (#50)

*2026-4-8 18:58*

mark

## 回复 by mb_qimctavn (#51)

*2026-4-8 19:11*

6

## 回复 by 黑嘿黑 (#52)

*2026-4-9 09:10*

mark

## 回复 by mb_hcadvceu (#53)

*2026-4-9 13:12*

感谢分享

## 回复 by mb_uvyukvot (#54)

*2026-4-9 16:51*

666

## 回复 by ldehua (#55)

*2026-4-9 23:44*

感谢分享

## 回复 by ldehua (#56)

*2026-4-9 23:53*

感谢分享

## 回复 by 大众 (#57)

*2026-4-10 00:10*

学习以下

## 回复 by 52bug (#58)

*2026-4-10 05:50*

666

## 回复 by 晴空万里丶 (#59)

*2026-4-10 06:04*

感谢分享

## 回复 by 喜欢就去抢啊 (#60)

*2026-4-10 09:07*

感谢分享

## 回复 by 苏幻墨 (#61)

*2026-4-10 09:49*

学习一下

## 回复 by 小木马 (#62)

*2026-4-10 11:26*

看看

## 回复 by mb_rztmbvgb (#63)

*2026-4-10 13:47*

66

## 回复 by mb_amtwjywa (#64)

*2026-4-10 14:13*

厉害了

## 回复 by kingking888 (#65)

*2026-4-10 22:24*

666

## 回复 by Zepp7289 (#66)

*2026-4-12 00:37*

tql

## 回复 by Kaedehara (#67)

*2026-4-12 00:50*

感谢分享

## 回复 by mb_yaeaedrh (#68)

*2026-4-12 01:17*

6

## 回复 by mb_ezphxtar (#69)

*2026-4-12 16:26*

一666666666

## 回复 by lixianhuei (#70)

*2026-4-13 08:49*

6666

## 回复 by buluo533 (#71)

*2026-4-13 09:12*

学习一下

## 回复 by 是小源啦 (#72)

*2026-4-13 09:19*

感谢分享

## 回复 by keulraesik (#73)

*2026-4-13 11:25*

学习一下 ,谢谢

## 回复 by pieces (#74)

*2026-4-13 12:14*

tql

## 回复 by uni7corn (#75)

*2026-4-13 13:55*

感谢分享

## 回复 by 云觞 (#76)

*2026-4-13 15:40*

666

## 回复 by Mirikkas (#77)

*2026-4-14 05:49*

666

## 回复 by mb_clyjjfyk (#78)

*2026-4-14 09:05*

111

## 回复 by 七星舞月 (#79)

*2026-4-14 09:48*

感谢分享

## 回复 by 高粱红 (#80)

*2026-4-14 12:31*

感谢分享

## 回复 by huangbof (#81)

*2026-4-14 13:47*

，也可以手动编辑，除了目标包名

## 回复 by mb_ghcouuzx (#82)

*2026-4-14 18:13*

看看卡

## 回复 by 曰你 (#83)

*2026-4-15 22:29*

1

## 回复 by mb_xflcgdik (#84)

*2026-4-16 11:33*

666

## 回复 by mb_exxfhcyj (#85)

*2026-4-17 09:18*

6

## 回复 by mb_jnmxfjku (#86)

*2026-4-17 15:28*

666

## 回复 by pangzibupang (#87)

*2026-4-18 03:15*

感谢分享

## 回复 by yercn (#88)

*2026-4-18 09:30*

感谢你的贡献，论坛因你而更加精彩！

## 回复 by UncleChen (#89)

*2026-4-19 01:15*

感谢分享

## 回复 by mb_oxzwfgim (#90)

*2026-4-19 02:42*

学习学习

## 回复 by git_14248bibinocode (#91)

*2026-4-20 11:07*

6666666666666666666

## 回复 by k4y0z (#92)

*2026-4-20 11:21*

666

## 回复 by mb_jjsshyyy (#93)

*2026-4-20 17:43*

学习

## 回复 by cradsl (#94)

*2026-4-20 19:28*

感谢分享··

## 回复 by 文西哥 (#95)

*2026-4-20 21:20*

感谢分享，学习一下。

## 回复 by Ankeys (#96)

*2026-4-21 09:23*

666

## 回复 by mb_hhkzpddm (#97)

*2026-4-21 17:17*

不错不错论坛因你而精彩

## 回复 by 彭彭丁满 (#98)

*2026-4-21 18:00*

感谢分享

## 回复 by 胖子不胖 (#99)

*2026-4-21 18:19*

感谢分享

## 回复 by mb_hjvqlubz (#100)

*2026-4-21 21:20*

666

## 回复 by 末日大哥 (#101)

*2026-4-21 21:48*

666

## 回复 by 然而没有梦 (#102)

*2026-4-22 03:30*

感谢分享![image](https://bbs.kanxue.com/view/img/face/038.gif)

## 回复 by wfjun (#103)

*2026-4-22 09:47*

牛鼻

## 回复 by mb_chjjqnap (#104)

*2026-4-22 11:09*

66

## 回复 by 西瓜很大 (#105)

*2026-4-22 14:18*

感谢分享！

## 回复 by 抬头望月 (#106)

*2026-4-22 14:36*

感谢分享

## 回复 by Viseris (#107)

*2026-4-22 15:44*

66666

## 回复 by 雪国的冬天 (#108)

*2026-4-22 16:11*

感谢大佬分享

## 回复 by HL_Mcgrady (#109)

*2026-4-22 17:07*

学习学习

## 回复 by guijingwen (#110)

*2026-4-22 17:19*

66

## 回复 by 需要渗透高手 (#111)

*2026-4-22 17:23*

学习一下

## 回复 by 0x25519 (#112)

*2026-4-22 17:30*

学习学习

## 回复 by CheRevir (#113)

*2026-4-22 17:36*

666

## 回复 by Thehepta (#114)

*2026-4-22 17:52*

1

## 回复 by nqminhquan (#115)

*2026-4-22 19:14*

6666666

## 回复 by mb_girssugh (#116)

*2026-4-23 04:35*

111

## 回复 by alds (#117)

*2026-4-24 09:12*

66

## 回复 by mb_tkluuesh (#118)

*2026-4-24 11:22*

111

## 回复 by 呼吸24K纯氧 (#119)

*2026-4-24 11:40*

感觉分享，看看隐藏

## 回复 by 淡定小胖子 (#120)

*2026-4-24 14:15*

6666

## 回复 by mb_ehrbohcl (#121)

*2026-4-24 14:56*

666

## 回复 by haofree_591134 (#122)

*2026-4-25 19:07*

感谢分享

## 回复 by wx_coddvccwyh (#123)

*2026-4-25 22:06*

66666

## 回复 by mb_rbvykvqm (#124)

*2026-4-26 17:14*

感谢老铁

## 回复 by wx_听书人 (#125)

*2026-4-27 18:37*

666

## 回复 by mb_gtqzxabf (#126)

*2026-4-28 01:26*

感谢分享

## 回复 by ClPrada (#127)

*2026-5-1 03:03*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_weufbroc (#128)

*2026-5-1 06:36*

看看能不能脱

## 回复 by shuangmou (#129)

*2026-5-1 12:54*

感谢分享

## 回复 by 宛枫 (#130)

*2026-5-2 08:36*

感谢分享

## 回复 by mb_ysikfhxt (#131)

*2026-5-2 09:26*

123

## 回复 by 孤江雪 (#132)

*2026-5-3 14:51*

感谢分享

## 回复 by 笑对VS人生 (#133)

*2026-5-4 08:14*

支持下

## 回复 by Cure. (#134)

*2026-5-4 15:53*

666

## 回复 by mb_joablzkk (#135)

*2026-5-6 09:22*

1

## 回复 by mb_yjiuccxa (#136)

*2026-5-6 09:42*

感谢分享

## 回复 by mb_yyvcbkli (#137)

*2026-5-6 09:52*

学习一下先进经验

## 回复 by mJqalJqN (#138)

*2026-5-6 11:09*

1

## 回复 by mb_lzsjiukj (#139)

*2026-5-8 20:57*

感谢分享

## 回复 by Migc (#140)

*2026-5-9 10:43*

tql

## 回复 by wx_快乐一生。 (#141)

*2026-5-10 10:56*

支持一个

## 回复 by amwpecel (#142)

*2026-5-10 15:03*

666

## 回复 by mb_rirvdrlh (#143)

*2026-5-10 22:12*

66666666666666666666

## 回复 by 初音未来 ㅤ (#144)

*2026-5-11 09:28*

学习了感谢分享

## 回复 by 酒仙桥之虎 (#145)

*2026-5-11 11:06*

111

## 回复 by cs_jackw (#146)

*2026-5-11 12:08*

感谢分享

## 回复 by 铁头葫芦娃 (#147)

*2026-5-12 18:23*

66666

## 回复 by 街道办事处 (#148)

*2026-5-13 08:02*

111

## 回复 by wx_　　　　_151 (#149)

*2026-5-13 09:13*

学习一下

## 回复 by mb_rbxtpjku (#150)

*2026-5-13 20:45*

666

## 回复 by ranks (#151)

*2026-5-13 23:30*

感谢分享

## 回复 by mb_qnkjfgfq (#152)

*2026-5-14 00:19*

sdadsadadsadasdadsadadsa

## 回复 by 落雪无尘V (#153)

*2026-5-14 01:30*

支持一下啊

## 回复 by mb_rxsabupn (#154)

*2026-5-14 05:05*

感谢分享

## 回复 by mb_ziwxnuti (#155)

*2026-5-14 07:27*

感谢分享

## 回复 by iamshy (#156)

*2026-5-14 10:20*

感谢分享

## 回复 by desedese (#157)

*2026-5-14 14:58*

感谢分享

## 回复 by 舞梦月影 (#158)

*2026-5-14 16:43*

感谢分享

## 回复 by bY4 (#159)

*2026-5-15 13:10*

感谢分享

## 回复 by ReverseApp (#160)

*2026-5-15 14:28*

感谢分享  !!

## 回复 by 月清晖 (#161)

*2026-5-15 15:42*

很强！  感谢楼主分享！

## 回复 by 紫川 (#162)

*2026-5-16 18:17*

666

## 回复 by huluxia (#163)

*2026-5-16 22:50*

牛逼。。。

## 回复 by mb_lhxrckiu (#164)

*2026-5-16 23:52*

学习

## 回复 by mb_zatbyyvv (#165)

*2026-5-18 14:43*

xiaotuo
  25 楼
感谢分享

## 回复 by 五彩斑斓的黑 (#166)

*2026-5-18 18:02*

666

## 回复 by 老小白 (#167)

*2026-5-22 20:36*

666

## 回复 by XiangXtreme (#168)

*2026-5-23 00:48*

感谢分享

## 回复 by mb_hvzfxnxe (#169)

*2026-5-24 14:36*

感谢分享

## 回复 by mb_tkluuesh (#170)

*2026-5-29 17:06*

111

## 回复 by mb_csnwuokx (#171)

*2026-5-29 17:14*

tql

## 回复 by mb_rooofjxx (#172)

*2026-5-29 17:59*

666

## 回复 by GeeKc (#173)

*2026-5-30 15:42*

6666

## 回复 by niama (#174)

*2026-5-31 02:44*

666

## 回复 by mb_gthrlmtf (#175)

*2026-5-31 21:16*

6666

## 回复 by mb_gkbxtfri (#176)

*2026-6-3 11:25*

![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by wx_恶龙咆哮嗷呜 (#177)

*2026-6-3 17:34*

tql

## 回复 by 千谦 (#178)

*2026-6-4 02:15*

666

## 回复 by johnchowzzy (#179)

*2026-6-4 05:59*

感谢分享

## 回复 by 寻梦之璐 (#180)

*2026-6-4 14:32*

6666

## 回复 by wx_Mr.Wr (#181)

*2026-6-6 10:27*

666

## 回复 by 财神爷999 (#182)

*2026-6-6 20:09*

感谢分享

## 回复 by mb_etobpsbv (#183)

*2026-6-9 10:34*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_oqwzheps (#184)

*2026-6-9 14:25*

感谢分享！

## 回复 by qaz1168 (#185)

*2026-6-12 16:06*

感谢分享

## 回复 by mb_pfgnxxyq (#186)

*2026-6-12 17:15*

666

## 回复 by mb_sqdwqxce (#187)

*2026-6-15 14:58*

看看

## 回复 by RedSand07 (#188)

*2026-6-15 16:03*

学习一下

## 回复 by nuomida (#189)

*2026-6-16 09:24*

怎么感觉有些东西缺失了

## 回复 by Freax (#190)

*2026-6-16 16:33*

感谢分享

## 回复 by mb_kgneopde (#191)

*2026-6-16 16:45*

666

## 回复 by wx_小白_266 (#192)

*2026-6-17 10:42*

看看

## 回复 by mb_vlfbadbl (#193)

*2026-6-23 11:17*

感谢分享

## 回复 by mb_trytevep (#194)

*2026-6-23 11:24*

感谢分享

## 回复 by YooHaa (#195)

*2026-6-23 14:25*

666

## 回复 by wx_xiao强 (#196)

*2026-6-23 14:56*

写的好详细

## 回复 by mb_wvpaswat (#197)

*2026-7-7 09:01*

学习

## 回复 by mb_zamcrfks (#198)

*2026-7-8 14:30*

666

## 回复 by wx_kx92911 (#199)

*2026-7-8 17:40*

感谢分享

## 回复 by waddle (#200)

*2026-7-13 08:31*

tql

## 回复 by zckeyer (#201)

*2026-7-26 19:45*

感谢分享

## 回复 by J1rrY (#202)

*2026-7-27 11:15*

支持![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 木魚· (#203)

*2026-7-27 11:53*

牛逼

## 回复 by didiid (#204)

*2026-7-27 14:02*

666

## 回复 by mb_tawwmfks (#205)

感谢分享

## 回复 by mb_gzmttlte (#206)

666
