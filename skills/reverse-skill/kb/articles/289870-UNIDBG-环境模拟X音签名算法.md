---
title: '[原创]UNIDBG 环境模拟X音签名算法'
url: https://bbs.kanxue.com/thread-289870.htm
tid: 289870
author: 易之生生
date: '2026-01-26'
tags: [Android安全, 原创, 逆向分析, 工具脚本]
crawled_at: '2026-08-08T10:28:13+00:00'
replies: 235
---

X音版本: 370401

# JNI_OnLoad

X音的校验参数是在 libmetasec_ml.so 中，静态导出函数只有一个 JNI_OnLoad, 其它导出函数是通过 JNIEnv->RegisterNatives 动态注册。

init_array 段如下:

```c
.init_array:0000000000374BC0 ; Segment type: Pure data
.init_array:0000000000374BC0                 AREA .init_array, DATA, ALIGN=3
.init_array:0000000000374BC0                 ; ORG 0x374BC0
.init_array:0000000000374BC0                 DCQ sub_173268
.init_array:0000000000374BC8                 DCQ sub_180D6C
.init_array:0000000000374BD0                 DCQ sub_268454
.init_array:0000000000374BD8                 DCQ sub_2723C8
.init_array:0000000000374BE0                 DCQ sub_283BA0
.init_array:0000000000374BE8                 DCQ sub_29AE6C
.init_array:0000000000374BF0                 DCQ sub_29D1A4
.init_array:0000000000374BF8                 DCQ sub_2A0B1C
.init_array:0000000000374C00                 DCQ sub_2A3288
.init_array:0000000000374C08                 DCQ sub_2A3CA8
.init_array:0000000000374C10                 DCQ sub_343964
.init_array:0000000000374C10 ; .init_array   ends
\```

首先运行 UNIDBG 最基础的代码来测试 init_array :

```java
package com.ss.android.ugc.aweme;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.memory.Memory;

import java.io.File;

public class Sign6_370401 extends AbstractJni {

    private final AndroidEmulator emulator;
    private final VM vm;
    private final Module module;
    private final Memory memory;

    private Sign6_370401() {
        emulator = AndroidEmulatorBuilder
                .for64Bit()
                .setProcessName("com.ss.android.ugc.aweme")
                .addBackendFactory(new Unicorn2Factory(true))
                .build();
        emulator.getBackend().registerEmuCountHook(100000);
        emulator.getSyscallHandler().setVerbose(true);
        emulator.getSyscallHandler().setEnableThreadDispatcher(true);

        memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));
        memory.setCallInitFunction(true);

        vm = emulator.createDalvikVM(new File("unidbg-android/src/test/resources/bytedance/aweme_douyinweb2_370401.apk"));
        vm.setJni(this);
        vm.setVerbose(true);
        DalvikModule dm = vm.loadLibrary(new File("unidbg-android/src/test/resources/bytedance/libmetasec_ml.370401.so"), true);
        module = dm.getModule();
    }

    public static void main(String[] args) {
        Sign6_370401 sign6 = new Sign6_370401();
    }
}
\```

正常情况下，输出日志如下:

```python
File opened 'stdin' with oflags=0x0 from null
File opened 'stdout' with oflags=0x1 from null
File opened 'stderr' with oflags=0x1 from null
[17:25:31 888] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64:3927) - _JavaVM=unidbg@0xfffe0080, _JNIInvokeInterface=unidbg@0xfffe16a0, _JNIEnv=unidbg@0xfffe1640
[17:25:32 070]  INFO [com.github.unidbg.linux.AndroidElfLoader] (AndroidElfLoader:487) - libmetasec_ml.so load dependency libandroid.so failed
File opened '/dev/__properties__' with oflags=0x88000 from RX@0x12552854[libc.so]0x22854
File closed '/dev/__properties__' from RX@0x1254ece4[libc.so]0x1ece4
File opened '/proc/stat' with oflags=0x80000 from RX@0x12552854[libc.so]0x22854
dlopen:libnetd_client.so
AndroidElfLoader dlopen libnetd_client.so
AndroidElfLoader LinuxModule null
AndroidElfLoader MemRegion name /system/lib64/libdl.so
AndroidElfLoader MemRegion name /system/lib64/libdl.so
AndroidElfLoader MemRegion name /system/lib64/libc.so
AndroidElfLoader MemRegion name /system/lib64/libc.so
AndroidElfLoader MemRegion name /system/lib64/libm.so
AndroidElfLoader MemRegion name /system/lib64/libm.so
AndroidElfLoader MemRegion name /system/lib64/libc++.so
AndroidElfLoader MemRegion name /system/lib64/libc++.so
AndroidElfLoader MemRegion name /system/lib64/liblog.so
AndroidElfLoader MemRegion name /system/lib64/liblog.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader LibraryFile null
Read 1884 bytes from '/proc/stat'
Read 0 bytes from '/proc/stat'
File closed '/proc/stat' from RX@0x1254ece4[libc.so]0x1ece4
\```

运行 dm.callJNI_OnLoad(emulator); 调用 JNI_OnLoad 后报错 :

```python
[17:29:47 233] DEBUG [com.github.unidbg.linux.android.dvm.DalvikModule] (DalvikModule:31) - Call [libmetasec_ml.so]JNI_OnLoad: 0x1227bfb0
[17:29:47 237] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$234:3901) - GetEnv vm=unidbg@0xfffe0080, env=null, version=0x10006
JNIEnv->FindClass(com/bytedance/mobsec/metasec/ml/MS) was called from RX@0x1226ee80[libmetasec_ml.so]0x26ee80
[17:29:47 238] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[17:29:47 240] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x36f48686, global=true
[17:29:47 240] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$3:87) - FindClass env=unidbg@0xfffe1640, className=com/bytedance/mobsec/metasec/ml/MS, hash=0x36f48686
JNIEnv->GetSuperClass(class com/bytedance/mobsec/metasec/ml/MS) was called from RX@0x1226ee9c[libmetasec_ml.so]0x26ee9c
[17:29:47 240] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$7:153) - JNIEnv->GetSuperClass was called, class = com/bytedance/mobsec/metasec/ml/MS, superClass get failed.
[17:29:47 241]  WARN [com.github.unidbg.linux.ARM64SyscallHandler] (ARM64SyscallHandler:410) - handleInterrupt intno=2, NR=-130832, svcNumber=0x106, PC=unidbg@0xfffe00f4, LR=RX@0x1226ee9c[libmetasec_ml.so]0x26ee9c, syscall=null
com.github.unidbg.arm.backend.BackendException
    at com.github.unidbg.linux.android.dvm.DalvikVM64$7.handle(DalvikVM64.java:155)
    at com.github.unidbg.linux.ARM64SyscallHandler.hook(ARM64SyscallHandler.java:119)
    at com.github.unidbg.arm.backend.Unicorn2Backend$11.hook(Unicorn2Backend.java:352)
    at com.github.unidbg.arm.backend.unicorn.Unicorn$NewHook.onInterrupt(Unicorn.java:109)
    at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Native Method)
    at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Unicorn.java:312)
    at com.github.unidbg.arm.backend.Unicorn2Backend.emu_start(Unicorn2Backend.java:389)
    at com.github.unidbg.AbstractEmulator.emulate(AbstractEmulator.java:378)
    at com.github.unidbg.thread.Function64.run(Function64.java:39)
    at com.github.unidbg.thread.MainTask.dispatch(MainTask.java:19)
    at com.github.unidbg.thread.UniThreadDispatcher.run(UniThreadDispatcher.java:165)
    at com.github.unidbg.thread.UniThreadDispatcher.runMainForResult(UniThreadDispatcher.java:97)
    at com.github.unidbg.AbstractEmulator.runMainForResult(AbstractEmulator.java:341)
    at com.github.unidbg.arm.AbstractARM64Emulator.eFunc(AbstractARM64Emulator.java:262)
    at com.github.unidbg.Module.emulateFunction(Module.java:163)
    at com.github.unidbg.linux.LinuxModule.callFunction(LinuxModule.java:256)
    at com.github.unidbg.linux.LinuxSymbol.call(LinuxSymbol.java:27)
    at com.github.unidbg.linux.android.dvm.DalvikModule.callJNI_OnLoad(DalvikModule.java:33)
    at com.ss.android.ugc.aweme.Sign6_370401.&lt;init&gt;(Sign6_370401.java:40)
    at com.ss.android.ugc.aweme.Sign6_370401.main(Sign6_370401.java:45)
[17:29:47 243]  WARN [com.github.unidbg.AbstractEmulator] (AbstractEmulator:417) - emulate RX@0x1227bfb0[libmetasec_ml.so]0x27bfb0 exception sp=unidbg@0xe4fff460, msg=com.github.unidbg.arm.backend.BackendException, offset=8ms @ Runnable|Function64 address=0x1227bfb0, arguments=[unidbg@0xfffe0080, null]
[17:29:47 243] DEBUG [com.github.unidbg.linux.android.dvm.DalvikModule] (DalvikModule:36) - Call [libmetasec_ml.so]JNI_OnLoad finished: version=0xffffffff, offset=10ms
Exception in thread "main" java.lang.IllegalStateException: Illegal JNI version: 0xffffffff
    at com.github.unidbg.linux.android.dvm.BaseVM.checkVersion(BaseVM.java:228)
    at com.github.unidbg.linux.android.dvm.DalvikModule.callJNI_OnLoad(DalvikModule.java:39)
    at com.ss.android.ugc.aweme.Sign6_370401.&lt;init&gt;(Sign6_370401.java:40)
    at com.ss.android.ugc.aweme.Sign6_370401.main(Sign6_370401.java:45)
\```

错误的原因如下 :

```c
JNIEnv->GetSuperClass was called, class = com/bytedance/mobsec/metasec/ml/MS, superClass get failed.
\```

根据 APK 的 JAVA 代码 :

```java
package com.bytedance.mobsec.metasec.ml;

import ms.bd.c.i2;

/* loaded from: classes56.dex */
public final class MS extends i2 {
}
\```

```java
package ms.bd.c;

/* loaded from: classes56.dex */
public abstract class i2 extends y2 {
    public static final void Louis() {
    }

    public static final void Zeoy() {
    }

    public void Francies() {
    }
}
\```

```java
package ms.bd.c;

/* loaded from: classes56.dex */
public abstract class y2 {
    public static native Object a(int i, int i2, long j, String str, Object obj);

    public static Object b(int i, int i2, long j, String str, Object obj) {
        try {
            return u2.a(i, i2, j, str, obj);
        } catch (Throwable th) {
            throw new RuntimeException(th);
        }
    }
}
\```

补充以下代码 :

```java
DvmClass a = vm.resolveClass("ms/bd/c/y2");
DvmClass b = vm.resolveClass("ms/bd/c/i2", a);
DvmClass c = vm.resolveClass("com/bytedance/mobsec/metasec/ml/MS", b);
\```

继续运行报错 :

```python
java.lang.UnsupportedOperationException: com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;
    at com.github.unidbg.linux.android.dvm.AbstractJni.callStaticObjectMethodV(AbstractJni.java:504)
    at com.github.unidbg.linux.android.dvm.AbstractJni.callStaticObjectMethodV(AbstractJni.java:438)
    at com.github.unidbg.linux.android.dvm.DvmMethod.callStaticObjectMethodV(DvmMethod.java:59)
    at com.github.unidbg.linux.android.dvm.DalvikVM64$112.handle(DalvikVM64.java:1836)
    at com.github.unidbg.linux.ARM64SyscallHandler.hook(ARM64SyscallHandler.java:119)
    at com.github.unidbg.arm.backend.Unicorn2Backend$11.hook(Unicorn2Backend.java:352)
    at com.github.unidbg.arm.backend.unicorn.Unicorn$NewHook.onInterrupt(Unicorn.java:109)
    at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Native Method)
    at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Unicorn.java:312)
    at com.github.unidbg.arm.backend.Unicorn2Backend.emu_start(Unicorn2Backend.java:389)
    at com.github.unidbg.AbstractEmulator.emulate(AbstractEmulator.java:378)
    at com.github.unidbg.thread.Function64.run(Function64.java:39)
    at com.github.unidbg.thread.MainTask.dispatch(MainTask.java:19)
    at com.github.unidbg.thread.UniThreadDispatcher.run(UniThreadDispatcher.java:165)
    at com.github.unidbg.thread.UniThreadDispatcher.runMainForResult(UniThreadDispatcher.java:97)
    at com.github.unidbg.AbstractEmulator.runMainForResult(AbstractEmulator.java:341)
    at com.github.unidbg.arm.AbstractARM64Emulator.eFunc(AbstractARM64Emulator.java:262)
    at com.github.unidbg.Module.emulateFunction(Module.java:163)
    at com.github.unidbg.linux.LinuxModule.callFunction(LinuxModule.java:256)
    at com.github.unidbg.linux.LinuxSymbol.call(LinuxSymbol.java:27)
    at com.github.unidbg.linux.android.dvm.DalvikModule.callJNI_OnLoad(DalvikModule.java:33)
    at com.ss.android.ugc.aweme.Sign6_370401.&lt;init&gt;(Sign6_370401.java:45)
    at com.ss.android.ugc.aweme.Sign6_370401.main(Sign6_370401.java:50)
\```

修补环境, 打印出第一个参数是 268435470

```c
callStaticObjectMethodV com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;
----------------------------
268435470
----------------------------
\```

继续分析以上 com/bytedance/mobsec/metasec/ml/MS 类的调用, 最终的调用函数 u2.a(i, i2, j, str, obj) 代码如下 :

```java
case 268435470:
    return Long.valueOf(C2450509eM.LIZ);
\```

```java
public final class C2450509eM {
    public static volatile long LIZ = 2;
    public static volatile long LIZIZ;
}
\```

结果为返回 2

修补代码如下 :

```java
@Override
public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {
    System.out.println("callStaticObjectMethodV "+ signature);
    switch (signature) {
        case "com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;": {
            int a = vaList.getIntArg(0);
            System.out.println("----------------------------");
            System.out.println(a);
            System.out.println("----------------------------");
            if (a == 268435470) {
                return DvmLong.valueOf(vm,2);
            }
        }
    }
    return super.callStaticObjectMethodV(vm, dvmClass, signature, vaList);
}

@Override
public long callLongMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {
    switch (signature) {
        case "java/lang/Long->longValue()J": {
            java.lang.Long result = (java.lang.Long)dvmObject.getValue();
            return result;
        }
    }
    return super.callLongMethodV(vm, dvmObject, signature, vaList);
}
\```

最终调用 JNI_OnLoad 的完整代码如下 :

```java
package com.ss.android.ugc.aweme;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.wrapper.DvmLong;
import com.github.unidbg.memory.Memory;

import java.io.File;

public class Sign6_370401 extends AbstractJni {

    private final AndroidEmulator emulator;
    private final VM vm;
    private final Module module;
    private final Memory memory;

    private Sign6_370401() {
        emulator = AndroidEmulatorBuilder
                .for64Bit()
                .setProcessName("com.ss.android.ugc.aweme")
                .addBackendFactory(new Unicorn2Factory(true))
                .build();
        emulator.getBackend().registerEmuCountHook(100000);
        emulator.getSyscallHandler().setVerbose(true);
        emulator.getSyscallHandler().setEnableThreadDispatcher(true);

        memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));
        memory.setCallInitFunction(true);

        vm = emulator.createDalvikVM(new File("unidbg-android/src/test/resources/bytedance/aweme_douyinweb2_370401.apk"));
        vm.setJni(this);
        vm.setVerbose(true);

        DvmClass a = vm.resolveClass("ms/bd/c/y2");
        DvmClass b = vm.resolveClass("ms/bd/c/i2", a);
        DvmClass c = vm.resolveClass("com/bytedance/mobsec/metasec/ml/MS", b);

        DalvikModule dm = vm.loadLibrary(new File("unidbg-android/src/test/resources/bytedance/libmetasec_ml.370401.so"), true);
        module = dm.getModule();
        dm.callJNI_OnLoad(emulator);
    }

    @Override
    public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {
        System.out.println("callStaticObjectMethodV "+ signature);
        switch (signature) {
            case "com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;": {
                int a = vaList.getIntArg(0);
                System.out.println("----------------------------");
                System.out.println(a);
                System.out.println("----------------------------");
                if (a == 268435470) {
                    return DvmLong.valueOf(vm,2);
                }
            }
        }
        return super.callStaticObjectMethodV(vm, dvmClass, signature, vaList);
    }

    @Override
    public long callLongMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {
        switch (signature) {
            case "java/lang/Long->longValue()J": {
                java.lang.Long result = (java.lang.Long)dvmObject.getValue();
                return result;
            }
        }
        return super.callLongMethodV(vm, dvmObject, signature, vaList);
    }

    public static void main(String[] args) {
        Sign6_370401 sign6 = new Sign6_370401();
    }
}
\```

输出日志如下:

```python
File opened 'stdin' with oflags=0x0 from null
File opened 'stdout' with oflags=0x1 from null
File opened 'stderr' with oflags=0x1 from null
[18:38:47 675] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64:3927) - _JavaVM=unidbg@0xfffe0080, _JNIInvokeInterface=unidbg@0xfffe16a0, _JNIEnv=unidbg@0xfffe1640
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff9de5a268, global=true
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff9de5a078, global=true
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[18:38:47 677] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x36f48686, global=true
[18:38:47 861]  INFO [com.github.unidbg.linux.AndroidElfLoader] (AndroidElfLoader:487) - libmetasec_ml.so load dependency libandroid.so failed
File opened '/dev/__properties__' with oflags=0x88000 from RX@0x12552854[libc.so]0x22854
File closed '/dev/__properties__' from RX@0x1254ece4[libc.so]0x1ece4
dlopen:libnetd_client.so
AndroidElfLoader dlopen libnetd_client.so
AndroidElfLoader LinuxModule null
AndroidElfLoader MemRegion name /system/lib64/libdl.so
AndroidElfLoader MemRegion name /system/lib64/libdl.so
AndroidElfLoader MemRegion name /system/lib64/libc.so
AndroidElfLoader MemRegion name /system/lib64/libc.so
AndroidElfLoader MemRegion name /system/lib64/libm.so
AndroidElfLoader MemRegion name /system/lib64/libm.so
AndroidElfLoader MemRegion name /system/lib64/libc++.so
AndroidElfLoader MemRegion name /system/lib64/libc++.so
AndroidElfLoader MemRegion name /system/lib64/liblog.so
AndroidElfLoader MemRegion name /system/lib64/liblog.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader MemRegion name /system/lib64/libmetasec_ml.370401.so
AndroidElfLoader LibraryFile null
File opened '/proc/stat' with oflags=0x80000 from RX@0x12552854[libc.so]0x22854
Read 1884 bytes from '/proc/stat'
Read 0 bytes from '/proc/stat'
File closed '/proc/stat' from RX@0x1254ece4[libc.so]0x1ece4
[18:38:47 957] DEBUG [com.github.unidbg.linux.android.dvm.DalvikModule] (DalvikModule:31) - Call [libmetasec_ml.so]JNI_OnLoad: 0x1227bfb0
[18:38:47 961] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$234:3901) - GetEnv vm=unidbg@0xfffe0080, env=null, version=0x10006
JNIEnv->FindClass(com/bytedance/mobsec/metasec/ml/MS) was called from RX@0x1226ee80[libmetasec_ml.so]0x26ee80
[18:38:47 962] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x36f48686, global=true
[18:38:47 962] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$3:87) - FindClass env=unidbg@0xfffe1640, className=com/bytedance/mobsec/metasec/ml/MS, hash=0x36f48686
JNIEnv->GetSuperClass(class com/bytedance/mobsec/metasec/ml/MS) was called from RX@0x1226ee9c[libmetasec_ml.so]0x26ee9c
[18:38:47 962] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$7:158) - JNIEnv->GetSuperClass was called, class = com/bytedance/mobsec/metasec/ml/MS, superClass = ms/bd/c/i2
JNIEnv->GetSuperClass(class ms/bd/c/i2) was called from RX@0x1226eec0[libmetasec_ml.so]0x26eec0
[18:38:47 963] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$7:158) - JNIEnv->GetSuperClass was called, class = ms/bd/c/i2, superClass = ms/bd/c/y2
[18:38:47 963] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$212:3366) - RegisterNatives dvmClass=class ms/bd/c/y2, methods=unidbg@0xe4fff460, nMethods=1
JNIEnv->RegisterNatives(ms/bd/c/y2, unidbg@0xe4fff460, 1) was called from RX@0x1226ef88[libmetasec_ml.so]0x26ef88
[18:38:47 963] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$212:3379) - RegisterNatives dvmClass=class ms/bd/c/y2, name=a, signature=(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, fnPtr=RX@0x1226f0f8[libmetasec_ml.so]0x26f0f8
RegisterNative(ms/bd/c/y2, a(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, RX@0x1226f0f8[libmetasec_ml.so]0x26f0f8)
[18:38:47 964] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$20:309) - DeleteLocalRef object=unidbg@0xffffffff9de5a268
[18:38:47 964] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$110:1781) - GetStaticMethodID class=unidbg@0x36f48686, methodName=b, args=(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, LR=RX@0x1226f044[libmetasec_ml.so]0x26f044
[18:38:47 964] DEBUG [com.github.unidbg.linux.android.dvm.DvmClass] (DvmClass:99) - getStaticMethodID signature=com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, hash=0x2f94ee13
JNIEnv->GetStaticMethodID(com/bytedance/mobsec/metasec/ml/MS.b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;) => 0x2f94ee13 was called from RX@0x1226f044[libmetasec_ml.so]0x26f044
[18:38:47 965] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$229:3607) - GetObjectRefType object=unidbg@0x36f48686, dvmGlobalObject=class com/bytedance/mobsec/metasec/ml/MS, dvmLocalObject=null
[18:38:47 967] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$234:3901) - GetEnv vm=unidbg@0xfffe0080, env=null, version=0x10006
[18:38:47 968] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$234:3901) - GetEnv vm=unidbg@0xfffe0080, env=null, version=0x10006
[18:38:47 969] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$234:3901) - GetEnv vm=unidbg@0xfffe0080, env=null, version=0x10006
[18:38:47 969] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$112:1828) - CallStaticObjectMethodV clazz=unidbg@0x36f48686, jmethodID=unidbg@0x2f94ee13, va_list=unidbg@0xe4fff300
[18:38:47 970] DEBUG [com.github.unidbg.linux.android.dvm.VaList64] (VaList64:131) - VaList64 base_p=0xe4fff370, base_integer=0xe4fff300, base_float=0xe4fff2d0, mask_integer=0x0, mask_float=0xffffff80, args=(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, shorty=[I, I, J, Ljava/lang/String;, Ljava/lang/Object;]
callStaticObjectMethodV com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;
----------------------------
268435470
----------------------------
[18:38:47 970] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[18:38:47 970] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xc1caa8f, global=true
JNIEnv->CallStaticObjectMethodV(class com/bytedance/mobsec/metasec/ml/MS, b(0x1000000e, 0x0, 0x0L, null, null) => java.lang.Long@17ed40e0) was called from RX@0x1226f430[libmetasec_ml.so]0x26f430
[18:38:47 971] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x17ed40e0, global=false
JNIEnv->FindClass(java/lang/Long) was called from RX@0x12271414[libmetasec_ml.so]0x271414
[18:38:47 972] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xc1caa8f, global=true
[18:38:47 972] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$3:87) - FindClass env=unidbg@0xfffe1640, className=java/lang/Long, hash=0xc1caa8f
[18:38:47 972] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$229:3607) - GetObjectRefType object=unidbg@0xc1caa8f, dvmGlobalObject=class java/lang/Long, dvmLocalObject=null
[18:38:47 972] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$30:502) - GetMethodID class=unidbg@0xc1caa8f, methodName=longValue, args=()J, LR=RX@0x12271450[libmetasec_ml.so]0x271450
[18:38:47 972] DEBUG [com.github.unidbg.linux.android.dvm.DvmClass] (DvmClass:133) - getMethodID signature=java/lang/Long->longValue()J, hash=0x44606195
JNIEnv->GetMethodID(java/lang/Long.longValue()J) => 0x44606195 was called from RX@0x12271450[libmetasec_ml.so]0x271450
[18:38:47 973] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$50:882) - CallLongMethodV object=unidbg@0x17ed40e0, jmethodID=unidbg@0x44606195, va_list=unidbg@0xe4fff300
[18:38:47 973] DEBUG [com.github.unidbg.linux.android.dvm.VaList64] (VaList64:131) - VaList64 base_p=0xe4fff370, base_integer=0xe4fff300, base_float=0xe4fff2d0, mask_integer=0xffffffd8, mask_float=0xffffff80, args=()J, shorty=[]
JNIEnv->CallLongMethodV(java.lang.Long@17ed40e0, longValue() => 0x2L) was called from RX@0x12225ab4[libmetasec_ml.so]0x225ab4
[18:38:47 973] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$20:309) - DeleteLocalRef object=unidbg@0x17ed40e0
bionic_clone fn=RX@0x12597c70[libc.so]0x67c70, LR=RX@0x1254ec80[libc.so]0x1ec80
bionic_clone fn=RX@0x12597c70[libc.so]0x67c70, LR=RX@0x1254ec80[libc.so]0x1ec80
bionic_clone fn=RX@0x12597c70[libc.so]0x67c70, LR=RX@0x1254ec80[libc.so]0x1ec80
File opened '/proc/self/exe' with oflags=0x0 from RX@0x12275638[libmetasec_ml.so]0x275638
Read 64 bytes from '/proc/self/exe'
File closed '/proc/self/exe' from RX@0x12274c94[libmetasec_ml.so]0x274c94
[18:38:48 032] DEBUG [com.github.unidbg.linux.android.dvm.DalvikModule] (DalvikModule:36) - Call [libmetasec_ml.so]JNI_OnLoad finished: version=0x10006, offset=75ms
\```

# Decrypt

根据 JNI_OnLoad 的日志，可以看到其调用了 RegisterNative 注册了 ms/bd/c/y2 类的 a 函数 ， 对应的 libmetasec_ml.so 函数的地址为 0x26f0f8

```python
[18:38:47 963] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$212:3366) - RegisterNatives dvmClass=class ms/bd/c/y2, methods=unidbg@0xe4fff460, nMethods=1
JNIEnv->RegisterNatives(ms/bd/c/y2, unidbg@0xe4fff460, 1) was called from RX@0x1226ef88[libmetasec_ml.so]0x26ef88
[18:38:47 963] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$212:3379) - RegisterNatives dvmClass=class ms/bd/c/y2, name=a, signature=(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, fnPtr=RX@0x1226f0f8[libmetasec_ml.so]0x26f0f8
RegisterNative(ms/bd/c/y2, a(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;, RX@0x1226f0f8[libmetasec_ml.so]0x26f0f8)
\```

对应的反汇编代码如下:

```c
sub_26F0F8

var_50= -0x50
var_48= -0x48
var_40= -0x40
var_38= -0x38
var_30= -0x30
var_28= -0x28
var_20= -0x20
var_18= -0x18
var_10= -0x10
var_8= -8

MOV             X1, X0
MOV             W0, W2
MOV             W2, W3
MOV             X3, X4
MOV             X4, X5
MOV             X5, X6
SUB             SP, SP, #0x50
STP             X29, X30, [SP,#0x50+var_10]
STP             X0, X1, [SP,#0x50+var_50]
STP             X2, X3, [SP,#0x50+var_40]
STP             X4, X5, [SP,#0x50+var_30]
STP             X6, X7, [SP,#0x50+var_20]
BL              sub_26F138
MOV             X1, X0
ADD             X1, X1, #0x38 ; '8'
BR              X1
; End of function sub_26F0F8
\```

对 ms/bd/c/y2 类的 a 函数进行 HOOK, 和 com.bytedance.mobsec.metasec.ml.MS 的 a 是同一个函数, HOOK 代码如下:

```js
function hookJava(){

    Java.perform(function(){
        // let MS = Java.use("com.bytedance.mobsec.metasec.ml.MS");
        let MS = Java.use("ms.bd.c.y2");
        MS["a"].implementation = function (i, i2, j, str, obj) {
            console.log(`MS is called: i=${i}, i2=${i2}, j=${j}, str=${str}, obj=${obj}`);
            if(obj != null ){
                var jsArray = Java.array('byte', obj);
                var buffer = new Uint8Array(jsArray).buffer;
                console.log(hexdump(buffer, {
                    offset: 0,
                    length: buffer.length,
                    header: true,
                    ansi: true
                }));
            }
            let result = this["a"](i, i2, j, str, obj);
            console.log(`MS result=${result}`);
            return result;
        };
    });

}
\```

发现有调用号为 0x1000001 的解密调用:

```python
MS is called: i=16777217, i2=0, j=0, str=eecc17, obj=[B@e111eaf
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  75 69 14 05 01 29 62 0a 33 23 64 29 31 14 1a 29  ui...)b.3#d)1..)
00000010  70 4d 26 2a 40 6f 02 12 0f 24                    pM&*@o...$
MS result=android.app.ActivityThread
MS is called: i=16777217, i2=0, j=0, str=fe9aef, obj=[B@efd92bc
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  74 72 58 07 5f 7f 71 65 6b 25 7e 71 43 01 43 45  trX._.qek%~qC.CE
00000010  6d 56 6d 30 73                                   mVm0s
MS result=currentActivityThread
MS is called: i=16777217, i2=0, j=0, str=2c96ae, obj=[B@e14f245
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  2e 40 49 56 57 64 38 56 61 63 30                 .@IVWd8Vac0
MS result=mActivities
MS is called: i=16777217, i2=0, j=0, str=00a510, obj=[B@71a5d9a
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  32 26 1d 51 1e 22 37                             2&.Q."7
MS result=stopped
MS is called: i=16777217, i2=0, j=0, str=146b73, obj=[B@d976dc1
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  21 35 51 1f 1e 2d 26 0c                          !5Q..-&.
MS result=activity
MS is called: i=16777217, i2=0, j=0, str=38186e, obj=[B@b27c117
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  23 34 46 5e 06 7b 34 57 69 66 36 3f 4c 58 47 73  #4F^.{4Wif6?LXGs
00000010  33 0d 69 67 2c 74 60 6d 3d 46 15 2b 59 57 01 12  3.ig,t`m=F.+YW..
00000020  63 62 2e 57 14                                   cb.W.
MS result=android.intent.action.BATTERY_CHANGED
MS is called: i=16777217, i2=0, j=0, str=3849df, obj=[B@b8c6904
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  32 36 52 4a 5c 74 34                             26RJ\t4
MS result=plugged
MS is called: i=16777217, i2=0, j=0, str=fd01c9, obj=[B@fe01eed
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  76 68 47 57 53 27 61 0b 68 6f 63 63 4d 51 12 2f  vhGWS'a.hoccMQ./
00000010  66 51 68 6e 79 28 61 64 68 1a 40 77 58 5e 54 4e  fQhny(adh.@wX^TN
00000020  62 6b 7b 0b 41                                   bk{.A
MS result=android.intent.action.BATTERY_CHANGED
MS is called: i=16777217, i2=0, j=0, str=0cb0c5, obj=[B@55d57b3
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  2d 64 07 41 50                                   -d.AP
MS result=level
MS is called: i=16777217, i2=0, j=0, str=d91fba, obj=[B@32cbce9
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  66 38 43 1e 58                                   f8C.X
MS result=scale
\```

在 UNIDBG 中对解密函数进行调用:

```java
public void decrypt(){
    int i = 0x1000001;
    int i2 = 0;
    long j = 0;
    String str = "d91fba";
    byte[] obj = new byte[]{0x66, 0x38, 0x43, 0x1e, 0x58};
    Object result = y2.callStaticJniMethodObject(emulator, "a(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;", i, i2, j, str, obj);
    System.out.println("result:"+result);
}
\```

成功输出了 scale 的解密结果:

```python
Find native function Java_ms_bd_c_y2_a => RX@0x1226f0f8[libmetasec_ml.so]0x26f0f8
[13:46:03 690] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff9de5a268, global=false
[13:46:03 691] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[13:46:03 691] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff83d61724, global=true
[13:46:03 691] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x3ac42916, global=false
[13:46:03 691] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x76f84423, global=true
[13:46:03 692] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xb66, global=true
[13:46:03 692] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x47d384ee, global=false
[13:46:03 698] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$184:3023) - NewStringUTF bytes=RW@0x123def9c[libmetasec_ml.so]0x3def9c, string=utf-8
JNIEnv->NewStringUTF("utf-8") was called from RX@0x122709c8[libmetasec_ml.so]0x2709c8
[13:46:03 699] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff83d61724, global=true
[13:46:03 699] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x2d6a9952, global=false
[13:46:03 699] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$23:353) - EnsureLocalCapacity capacity=3
[13:46:03 699] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$28:461) - GetObjectClass object=unidbg@0x3ac42916, dvmObject="d91fba"
[13:46:03 700] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$30:502) - GetMethodID class=unidbg@0xffffffff83d61724, methodName=getBytes, args=(Ljava/lang/String;)[B, LR=RX@0x122702dc[libmetasec_ml.so]0x2702dc
[13:46:03 700] DEBUG [com.github.unidbg.linux.android.dvm.DvmClass] (DvmClass:133) - getMethodID signature=java/lang/String->getBytes(Ljava/lang/String;)[B, hash=0x318b4ca9
JNIEnv->GetMethodID(java/lang/String.getBytes(Ljava/lang/String;)[B) => 0x318b4ca9 was called from RX@0x122702dc[libmetasec_ml.so]0x2702dc
[13:46:03 700] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$32:550) - CallObjectMethodV object=unidbg@0x3ac42916, jmethodID=unidbg@0x318b4ca9, va_list=unidbg@0xe4fff0a0, lr=RX@0x122703e4[libmetasec_ml.so]0x2703e4
[13:46:03 700] DEBUG [com.github.unidbg.linux.android.dvm.VaList64] (VaList64:131) - VaList64 base_p=0xe4fff240, base_integer=0xe4fff1d0, base_float=0xe4fff1b0, mask_integer=0xfffffff0, mask_float=0xffffff80, args=(Ljava/lang/String;)[B, shorty=[Ljava/lang/String;]
[13:46:03 700] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xb66, global=true
JNIEnv->CallObjectMethodV("d91fba", getBytes("utf-8") => [B@0x643931666261) was called from RX@0x122703e4[libmetasec_ml.so]0x2703e4
[13:46:03 703] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x73035e27, global=false
[13:46:03 703] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$20:309) - DeleteLocalRef object=unidbg@0xffffffff83d61724
[13:46:03 704] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$161:2650) - GetArrayLength array=[B@0x643931666261
JNIEnv->GetArrayLength([B@0x643931666261 => 6) was called from RX@0x12270b68[libmetasec_ml.so]0x270b68
JNIEnv->GetByteArrayRegion([B@0x643931666261, 0, 6, RW@0x12717080) was called from RX@0x12270ba8[libmetasec_ml.so]0x270ba8

>-----------------------------------------------------------------------------<
[13:46:03 706]GetByteArrayRegion array=[B@0x643931666261, start=0, length=6, buf=RW@0x12717080, md5=13aca1d9716999983a627cd4f156a96e, hex=643931666261
size: 6
0000: 64 39 31 66 62 61                                  d91fba
^-----------------------------------------------------------------------------^
[13:46:03 709] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$20:309) - DeleteLocalRef object=unidbg@0x73035e27
[13:46:03 713] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$20:309) - DeleteLocalRef object=unidbg@0x2d6a9952
[13:46:03 713] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$161:2650) - GetArrayLength array=[B@0x6638431e58
JNIEnv->GetArrayLength([B@0x6638431e58 => 5) was called from RX@0x12270b68[libmetasec_ml.so]0x270b68
JNIEnv->GetByteArrayRegion([B@0x6638431e58, 0, 5, RW@0x12717078) was called from RX@0x12270ba8[libmetasec_ml.so]0x270ba8

>-----------------------------------------------------------------------------<
[13:46:03 714]GetByteArrayRegion array=[B@0x6638431e58, start=0, length=5, buf=RW@0x12717078, md5=2fb0b32f68a25b037a7773fd6b70362c, hex=6638431e58
size: 5
0000: 66 38 43 1E 58                                     f8C.X
^-----------------------------------------------------------------------------^
[13:46:03 714] DEBUG [com.github.unidbg.linux.android.dvm.DalvikVM64] (DalvikVM64$184:3023) - NewStringUTF bytes=unidbg@0xe4fff291, string=scale
JNIEnv->NewStringUTF("scale") was called from RX@0x12270c54[libmetasec_ml.so]0x270c54
[13:46:03 716] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0xffffffff83d61724, global=true
[13:46:03 716] DEBUG [com.github.unidbg.linux.android.dvm.BaseVM] (BaseVM:146) - addObject hash=0x483bf400, global=false
result:"scale"
\```

但是没有 HOOK 到调用号为 0x3000001 对签名参数的调用,手动构造 0x3000001 的参数,使用 FRIDA 主动调用的代码如下：

```js
function callJava(){
    Java.perform(function() {
        let s1 = "https://ichannel.snssdk.com/service/2/app_alert_check/?ac=wifi&channel=shenmasem_ls_dy_210&aid=1128&app_name=aweme&version_code=230300&version_name=23.3.0&device_platform=android&os=android&ssmix=a&device_type=Pixel&device_brand=google&language=zh&os_api=27&os_version=8.1.0&openudid=b104cd40fd2b3224&manifest_version_code=230301&resolution=1080*1794&dpi=420&update_version_code=23309900&_rticket=1670126182805&package=com.ss.android.ugc.aweme&cpu_support64=true&host_abi=armeabi-v7a&is_guest_mode=0&app_type=normal&minor_status=0&appTheme=light&need_personal_recommend=1&is_android_pad=0&ts=1670126133&cdid=26ed513b-3f69-440f-ba7d-4b53f333e88c&md=0&iid=4072246474186391&device_id=3122268427780248&uuid=352531081299354";
        let s2 = "x-ss-req-ticket\r\n"+
                "1646193928088\r\n"+
                "personal-recommend-status\r\n"+
                "1\r\n"+
                "x-vc-bdturing-sdk-version\r\n"+
                "2.2.1.cn\r\n"+
                "passport-sdk-version\r\n"+
                "30626\r\n"+
                "sdk-version\r\n"+
                "2\r\n"+
                "x-tt-trace-id\r\n"+
                "00-48cde91e0100ba02e9a49302ff57211e-48cde91e0100ba02-01\r\n"+
                "user-agent\r\n"+
                "com.ss.android.ugc.aweme/230300 (Linux; U; Android 8.1.0; zh_CN; Pixel; Build/OPM1.171019.014;tt-ok/3.12.13.1)\r\n"+
                "accept-encoding\r\n"+
                "gzip, deflate";
        // let MS = Java.use("com.bytedance.mobsec.metasec.ml.MS");
        let MS = Java.use("ms.bd.c.y2");
        let method = MS.a.overload('int', 'int', 'long', 'java.lang.String', 'java.lang.Object');
        let args3 = Java.use("java.lang.String").$new(s1);
        let args4 = Java.use("java.lang.String").$new(s2).getBytes('UTF_8');
        let result = method.call(MS, 0x3000001, 0, 0n, args3, args4);
        console.log("result:", result);
    });
}
\```

返回结果为 NULL :

```python
[Pixel 6::com.ss.android.ugc.aweme ]-> callJava()
MS is called: i=50331649, i2=0, j=0, str=https://ichannel.snssdk.com/service/2/app_alert_check/?ac=wifi&channel=shenmasem_ls_dy_210&aid=1128&app_name=aweme&version_code=230300&version_name=23.3.0&device_platform=android&os=android&ssmix=a&device_type=Pixel&device_brand=google&language=zh&os_api=27&os_version=8.1.0&openudid=b104cd40fd2b3224&manifest_version_code=230301&resolution=1080*1794&dpi=420&update_version_code=23309900&_rticket=1670126182805&package=com.ss.android.ugc.aweme&cpu_support64=true&host_abi=armeabi-v7a&is_guest_mode=0&app_type=normal&minor_status=0&appTheme=light&need_personal_recommend=1&is_android_pad=0&ts=1670126133&cdid=26ed513b-3f69-440f-ba7d-4b53f333e88c&md=0&iid=4072246474186391&device_id=3122268427780248&uuid=352531081299354, obj=[B@78c0adc
           0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0123456789ABCDEF
00000000  78 2d 73 73 2d 72 65 71 2d 74 69 63 6b 65 74 0d  x-ss-req-ticket.
00000010  0a 31 36 34 36 31 39 33 39 32 38 30 38 38 0d 0a  .1646193928088..
00000020  70 65 72 73 6f 6e 61 6c 2d 72 65 63 6f 6d 6d 65  personal-recomme
00000030  6e 64 2d 73 74 61 74 75 73 0d 0a 31 0d 0a 78 2d  nd-status..1..x-
00000040  76 63 2d 62 64 74 75 72 69 6e 67 2d 73 64 6b 2d  vc-bdturing-sdk-
00000050  76 65 72 73 69 6f 6e 0d 0a 32 2e 32 2e 31 2e 63  version..2.2.1.c
00000060  6e 0d 0a 70 61 73 73 70 6f 72 74 2d 73 64 6b 2d  n..passport-sdk-
00000070  76 65 72 73 69 6f 6e 0d 0a 33 30 36 32 36 0d 0a  version..30626..
00000080  73 64 6b 2d 76 65 72 73 69 6f 6e 0d 0a 32 0d 0a  sdk-version..2..
00000090  78 2d 74 74 2d 74 72 61 63 65 2d 69 64 0d 0a 30  x-tt-trace-id..0
000000a0  30 2d 34 38 63 64 65 39 31 65 30 31 30 30 62 61  0-48cde91e0100ba
000000b0  30 32 65 39 61 34 39 33 30 32 66 66 35 37 32 31  02e9a49302ff5721
000000c0  31 65 2d 34 38 63 64 65 39 31 65 30 31 30 30 62  1e-48cde91e0100b
000000d0  61 30 32 2d 30 31 0d 0a 75 73 65 72 2d 61 67 65  a02-01..user-age
000000e0  6e 74 0d 0a 63 6f 6d 2e 73 73 2e 61 6e 64 72 6f  nt..com.ss.andro
000000f0  69 64 2e 75 67 63 2e 61 77 65 6d 65 2f 32 33 30  id.ugc.aweme/230
00000100  33 30 30 20 28 4c 69 6e 75 78 3b 20 55 3b 20 41  300 (Linux; U; A
00000110  6e 64 72 6f 69 64 20 38 2e 31 2e 30 3b 20 7a 68  ndroid 8.1.0; zh
00000120  5f 43 4e 3b 20 50 69 78 65 6c 3b 20 42 75 69 6c  _CN; Pixel; Buil
00000130  64 2f 4f 50 4d 31 2e 31 37 31 30 31 39 2e 30 31  d/OPM1.171019.01
00000140  34 3b 74 74 2d 6f 6b 2f 33 2e 31 32 2e 31 33 2e  4;tt-ok/3.12.13.
00000150  31 29 0d 0a 61 63 63 65 70 74 2d 65 6e 63 6f 64  1)..accept-encod
00000160  69 6e 67 0d 0a 67 7a 69 70 2c 20 64 65 66 6c 61  ing..gzip, defla
00000170  74 65                                            te
MS result=null
result: null
\```

# Sign

字节使用的网络底层库是 Cronet‌, 签名参数是在 libsscronet.so 中添加的，根据字符串 x-ttnet-origin-url 定位到目标函数地址是 0x47A31C,

```c
__int64 __fastcall std::__Cr::DoIOSInit::DoIOSInit(__int64 a1, __int64 a2, __int64 **a3, __int64 *a4)
{
    ...
    if ( !v14
    || (sub_1F70D0((void **)&dest, "x-ttnet-origin-url"),
        v15 = sub_2E8058(a2 + 4048, (const void **)&dest),
        v16 = sub_204CC0((__int64)&dest),
        a2 + 4056 != v15) )
    {
        ...
        if ( !*(_BYTE *)(v29 + 4377) )
        {
          v89 = (__int64 (__fastcall *)(_QWORD *, __int128 *))atomic_load(&qword_5FFE80);
          if ( v89 )
          {
            if ( !*v17 )
            {
              v90 = (v151 & 0x80u) == 0 ? &v149 : v149;
              v91 = v145 >= 0 ? &src : (__int128 *)src;
              *(_QWORD *)(a2 + 4432) = base::subtle::TimeTicksNowIgnoringOverride(v37);
              s = (char *)v89(v90, v91);
              *(_QWORD *)(a2 + 4440) = base::subtle::TimeTicksNowIgnoringOverride(s);
            }
          }
        }
        ...
    }
    ...
}
\```

调用 libmetasec_ml.so 签名函数的伪代码和汇编代码如下:

```c
s = (char *)v89(v90, v91);
\```

```c
.text:000000000047AAE4                 MOV             X0, X21
.text:000000000047AAE8                 MOV             X1, X22
.text:000000000047AAEC                 BLR             X23
\```

使用 FRIDA HOOK 0x47AAEC 地址, 获取到 X23 的地址是 libmetasec_ml.so 的 0x2A45F0 偏移:

```js
function hook_cronet(){
    Java.perform(function() {
        const lib = Process.findModuleByName("libsscronet.so");
        if (!lib) {
            console.error("libsscronet.so not found");
            return;
        }
        Interceptor.attach(lib.base.add(0x47AAEC), {
            onEnter: function(args) {
                console.log(`[libsscronet] args_0="${args[0]}"`);
                console.log(`[libsscronet] args_1="${args[1]}"`);
                console.log("libsscronet args_0: ", args[0].readCString());
                console.log("libsscronet args_1: ", args[1].readCString());
                console.log("libsscronet x23: ", this.context.x23);
            },

            onLeave: function(retval) {
                console.log("libsscronet retval: ", retval.readCString());
            }
        });
    });
}
\```

对 libmetasec_ml.so 的 0x2A45F0 地址进行 HOOK ,获取到了签名参数:

```js
function hook_metasec_ml(){
    Java.perform(function() {
        const lib = Process.findModuleByName("libmetasec_ml.so");
        if (!lib) {
            console.error("libmetasec_ml.so not found");
            return;
        }
        Interceptor.attach(lib.base.add(0x2A45F0), {
            onEnter: function(args) {
                console.log(`[libmetasec_ml] args_0="${args[0]}"`);
                console.log(`[libmetasec_ml] args_1="${args[1]}"`);
                console.log("libmetasec_ml args_0: ", args[0].readCString());
                console.log("libmetasec_ml args_1: ", args[1].readCString());
            },

            onLeave: function(retval) {
                console.log("libmetasec_ml retval: ", retval.readCString());
            }
        });
    });
}
\```

```python
[libmetasec_ml] args_0="0x74b1840890"
[libmetasec_ml] args_1="0x745183a950"
libmetasec_ml args_0:  https://api5-normal-m-hj.amemv.com/privacy/setting/change?iid=3247301440846819&device_id=397365608203400&ac=wifi&channel=douyinweb2_64_android&aid=1128&app_name=aweme&version_code=370400&version_name=37.4.0&device_platform=android&os=android&ssmix=a&device_type=Pixel+6&device_brand=google&language=zh&os_api=36&os_version=16&manifest_version_code=370401&resolution=1080*2146&dpi=420&update_version_code=37409900&_rticket=1769247175853&package=com.ss.android.ugc.aweme&first_launch_timestamp=1769245978&last_deeplink_update_version_code=0&cpu_support64=true&host_abi=arm64-v8a&is_guest_mode=0&app_type=normal&minor_status=0&appTheme=light&is_preinstall=0&need_personal_recommend=1&is_android_pad=0&is_android_fold=0&ts=1769247174&cdid=1a506faa-3555-49d0-9f25-44f7968645c1
libmetasec_ml args_1:  cookie
passport_csrf_token=d0e6583384688b26714cd372e22d6c5e; passport_csrf_token_default=d0e6583384688b26714cd372e22d6c5e; store-region=cn-he; store-region-src=did; install_id=3247301440846819; ttreq=1$836482d2656977ff15663f05c6cb24bf4e14fdb6; odin_tt=2cc07cb8a8111f7a6c3ad1b3395693943d7b5dd0d19ca04d8a06c7cebe40c4ab989dbd6585e6c23dbf7d3be58cff359e6c5befc19dca7f8ef7882f8dee277a7b34061a8ae9120d15f53e8ee248f56cd3
x-tt-request-tag
t=0;n=0;s=0;p=0
x-tt-dt
AAAS5FGCSMPV2LPST6QFRAVVEHRHPJG6PHIDX7DAZ47VYPUE35FFRQDQEZWFURXE3LO4MANJ5SB6HM2W3BIZQKO7O3U3XLLI4MWUEFPC4HQC2EIXDI2G3ZY2TTEGO
activity_now_client
1769247174480
x-ss-req-ticket
1769247175855
sdk-version
2
passport-sdk-version
601486
x-vc-bdturing-sdk-version
4.1.1.cn
content-type
application/x-www-form-urlencoded; charset=UTF-8
x-ss-stub
FDF60E82C1607606E7386BA88D06B4CA
content-length
33
x-tt-store-region
cn-he
x-tt-store-region-src
did
x-ss-dp
1128
x-tt-trace-id
01-ef5976540d16966e3ec4488aaa3b0468-ef5976540d16966e-00
user-agent
com.ss.android.ugc.aweme/370401 (Linux; U; Android 16; zh_CN_#Hans; Pixel 6; Build/BP2A.250805.005; Cronet/TTNetVersion:6f1e308d 2025-12-08 QuicVersion:21ac1950 2025-11-18)
accept-encoding
gzip, deflate, br

Backtracer FUZZY:
  0: 0x71ecdabaf0 libsscronet.so!0x47aaf0
  1: 0x763810fa18 libc.so!scudo_malloc+0x28
  2: 0x71eccafe64 libsscronet.so!0x37ee64
  3: 0x763810f854 libc.so!_ZN5scudo9AllocatorINS_19AndroidNormalConfigEXadL_Z21scudo_malloc_postinitEEE10deallocateEPvNS_5Chunk6OriginEmm+0xc4
  4: 0x763810fa18 libc.so!scudo_malloc+0x28
  5: 0x71ecc721e0 libsscronet.so!0x3411e0
  6: 0x71ecd42f88 libsscronet.so!0x411f88
  7: 0x71ecd42c90 libsscronet.so!0x411c90
  8: 0x71ecb32928 libsscronet.so!0x201928
  9: 0x71ecb2b57c libsscronet.so!0x1fa57c
  10: 0x71ecb6f8a0 libsscronet.so!0x23e8a0
  11: 0x71ecb6f8b0 libsscronet.so!0x23e8b0
  12: 0x71ecc68e04 libsscronet.so!0x337e04
  13: 0x71ecd426ac libsscronet.so!0x4116ac
  14: 0x763810fa18 libc.so!scudo_malloc+0x28
  15: 0x71ecd3c8b4 libsscronet.so!0x40b8b4

libmetasec_ml retval:  X-Perseus
LpLLLkINqlYjZyIsWZa+PU9jOYyDslGf2lRehrGQbUO0/h0EPMZgZFKzH5DBopCBLLoj6mKd30ZCwahDKCC6eCZERH+YBwq5Gf7IlyqIzUj/L1cBUw8xLVulsZsIPDA6PzLtD4FRBxdwy+L9TtXyl/HN6GViQ/yZVkXY9gOfQ364JQZnV12EKHIDjITvXwlVbEpLDJSTFZtN3FDlIahMviWtGKz8ycKl0sM91+d9a8z0yC0gCoaE5N3pfeteDCogsgEB/wESTL9Y9Ngi0P+E5pSgMZQPND2R5rlqzGU6fbHSu4m+YjWUnj58YQooHXtzadNyZGFVOvqEUKio8T+/h/WNd0wGcONJzvotj7niEnfjmdN7fhRbGSwwkAKQQjUi/W1F+Dk29TOwYoGmMXnsxr4hVu4eLvoaYvsTO4GigWvHD+UqTsqpCdIG4+q8TcnwmdH0Ix23/qhiu4DL/S7/HdfySo1ANz4+CBkbv46Vpi9g7E0An/dqMgd67uSfHaSedN92Qb1WTC5vyZtyn6vcuB7jyTPReO5mcptKGyTEEKOL61HEg+bxdsyVkE+DBMNSafDAvWpcnu457GZTWBmwKaiVAtwYYSyOH5fWm3EYi7BzovovBslpeTm1CZfZCWfi1KRnChGn3vAdlKI/cMoeD1/2Lud4es7kHrLN6MRUMxUaciQE77YEe9bxUKX11b8xIKHuV5qmONo0dRQw7MZ39t+jZmtwKn5Y76DJDqCBNN7lncgTKt2WoCiWRZgQFggG9yosOus/fLJkKMiyxsF5f8dHM48tyyGV6offhDF5WzU2xIuAOy64XWnbxG1K7KtVEPhaG/5VR3IQCiqGIeqg87kug+Qo+V3c/YvItuF7KPr5IS9xuhWvNSBn5TPN6e85QKFLsvU=
X-Medusa
zpF0aaILX0OLCtv4SFt2Awun0JeOlQANU2SDMrzGgWCoGNMP7DWtW6dxAXwXGBpFit+g477gUnZjGjTwy3s9MLloDSGyCLNW5m1tXi77OntAogTIJThzK3vEs8qghmBBSKwZDjLQTtgxe3GtKa63JxC0BF12P1ssEL5y+xXvqMrt3AfQrSpU/qnsHqY/vVxj7vj7u6ONzSeuyBLPg5PU5Eaqd9LZM1o7es+KfHoW0tH6ecGTEO9QSQkyd76n9EXjjGm5DbwHs5UBaAy/LbFRfnmUegWYtE3VJDV79xbpkyUHDJdYJTI10NyrY0ISRTAEc04T6nJixIVFFy7SjJpfUjax+exdfP/7l3z//5eNCg==
X-Argus
yZF0aQ==
X-Helios
q1N8CDT3R5nrbHX9j2QpNt6E4n7l/aAEyPWVMMZLNLpssoO5
X-Ladon
9pAogw==
X-Khronos
1769247177
X-Gorgon
8404b0080004c5f77c0804902af3caf9896f10c344e3ed941fbc
\```

UNIDBG 调用签名函数代码如下:

```java
public void metasec(){
    String s1 = "https://api5-normal-m-hj.amemv.com/privacy/setting/change?iid=3247301440846819&device_id=397365608203400&ac=wifi&channel=douyinweb2_64_android&aid=1128&app_name=aweme&version_code=370400&version_name=37.4.0&device_platform=android&os=android&ssmix=a&device_type=Pixel+6&device_brand=google&language=zh&os_api=36&os_version=16&manifest_version_code=370401&resolution=1080*2146&dpi=420&update_version_code=37409900&_rticket=1769247175853&package=com.ss.android.ugc.aweme&first_launch_timestamp=1769245978&last_deeplink_update_version_code=0&cpu_support64=true&host_abi=arm64-v8a&is_guest_mode=0&app_type=normal&minor_status=0&appTheme=light&is_preinstall=0&need_personal_recommend=1&is_android_pad=0&is_android_fold=0&ts=1769247174&cdid=1a506faa-3555-49d0-9f25-44f7968645c1";
    String s2 = "cookie\r\n" +
            "passport_csrf_token=d0e6583384688b26714cd372e22d6c5e; passport_csrf_token_default=d0e6583384688b26714cd372e22d6c5e; store-region=cn-he; store-region-src=did; install_id=3247301440846819; ttreq=1$836482d2656977ff15663f05c6cb24bf4e14fdb6; odin_tt=2cc07cb8a8111f7a6c3ad1b3395693943d7b5dd0d19ca04d8a06c7cebe40c4ab989dbd6585e6c23dbf7d3be58cff359e6c5befc19dca7f8ef7882f8dee277a7b34061a8ae9120d15f53e8ee248f56cd3\r\n" +
            "x-tt-request-tag\r\n" +
            "t=0;n=0;s=0;p=0\r\n" +
            "x-tt-dt\r\n" +
            "AAAS5FGCSMPV2LPST6QFRAVVEHRHPJG6PHIDX7DAZ47VYPUE35FFRQDQEZWFURXE3LO4MANJ5SB6HM2W3BIZQKO7O3U3XLLI4MWUEFPC4HQC2EIXDI2G3ZY2TTEGO\r\n" +
            "activity_now_client\r\n" +
            "1769247174480\r\n" +
            "x-ss-req-ticket\r\n" +
            "1769247175855\r\n" +
            "sdk-version\r\n" +
            "2\r\n" +
            "passport-sdk-version\r\n" +
            "601486\r\n" +
            "x-vc-bdturing-sdk-version\r\n" +
            "4.1.1.cn\r\n" +
            "content-type\r\n" +
            "application/x-www-form-urlencoded; charset=UTF-8\r\n" +
            "x-ss-stub\r\n" +
            "FDF60E82C1607606E7386BA88D06B4CA\r\n" +
            "content-length\r\n" +
            "33\r\n" +
            "x-tt-store-region\r\n" +
            "cn-he\r\n" +
            "x-tt-store-region-src\r\n" +
            "did\r\n" +
            "x-ss-dp\r\n" +
            "1128\r\n" +
            "x-tt-trace-id\r\n" +
            "01-ef5976540d16966e3ec4488aaa3b0468-ef5976540d16966e-00\r\n" +
            "user-agent\r\n" +
            "com.ss.android.ugc.aweme/370401 (Linux; U; Android 16; zh_CN_#Hans; Pixel 6; Build/BP2A.250805.005; Cronet/TTNetVersion:6f1e308d 2025-12-08 QuicVersion:21ac1950 2025-11-18)\r\n" +
            "accept-encoding\r\n" +
            "gzip, deflate, br";

    Number number = module.callFunction(emulator,
            0x2A45F0, s1, s2
    );
    System.out.printf("0X%X\n", number.intValue());
    int hash = number.intValue();
    UnidbgPointer p = memory.pointer(hash & 0xffffffffL);
    System.out.println(p.getString(0));
}
\```

修补完环境后的完整代码如下:

```java
package com.ss.android.ugc.aweme;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.api.AssetManager;
import com.github.unidbg.linux.android.dvm.api.Binder;
import com.github.unidbg.linux.android.dvm.array.ArrayObject;
import com.github.unidbg.linux.android.dvm.array.ByteArray;
import com.github.unidbg.linux.android.dvm.wrapper.DvmInteger;
import com.github.unidbg.linux.android.dvm.wrapper.DvmLong;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.pointer.UnidbgPointer;

import java.io.File;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

public class Sign6_370401 extends AbstractJni {

    private final AndroidEmulator emulator;
    private final VM vm;
    private final Module module;
    private final Memory memory;
    private final DvmClass y2;
    private final DvmClass i2;
    private final DvmClass MS;

    private Sign6_370401() {
        emulator = AndroidEmulatorBuilder
                .for64Bit()
                .setProcessName("com.ss.android.ugc.aweme")
                .addBackendFactory(new Unicorn2Factory(true))
                .build();
        emulator.getBackend().registerEmuCountHook(100000);
        emulator.getSyscallHandler().setVerbose(true);
        emulator.getSyscallHandler().setEnableThreadDispatcher(true);

        memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));
        memory.setCallInitFunction(true);

        vm = emulator.createDalvikVM(new File("unidbg-android/src/test/resources/bytedance/aweme_douyinweb2_370401.apk"));
        vm.setJni(this);
        vm.setVerbose(true);

        y2 = vm.resolveClass("ms/bd/c/y2");
        i2 = vm.resolveClass("ms/bd/c/i2", y2);
        MS = vm.resolveClass("com/bytedance/mobsec/metasec/ml/MS", i2);

        DalvikModule dm = vm.loadLibrary(new File("unidbg-android/src/test/resources/bytedance/libmetasec_ml.370401.so"), true);
        module = dm.getModule();
        dm.callJNI_OnLoad(emulator);
    }

    @Override
    public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {
        System.out.println("callStaticObjectMethodV "+ signature);
        switch (signature) {
            case "com/bytedance/mobsec/metasec/ml/MS->b(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;": {
                int a = vaList.getIntArg(0);
                System.out.println("----------------------------");
                System.out.println(a);
                System.out.println("----------------------------");
                if (a == 268435470) {
                    return DvmLong.valueOf(vm,2);
                }
                if (a == 65539){
                    File file = new File("test_path");
                    return new StringObject(vm, file.getAbsolutePath());
                }
                if (a == 33554433){
                    return new StringObject(vm, "");
                }
                if (a == 33554434){
                    return new StringObject(vm, "");
                }
            }
            case "java/lang/Integer->valueOf(I)Ljava/lang/Integer;":
                int arg_0 = vaList.getIntArg(0);
                return DvmInteger.valueOf(vm, arg_0);
            case "java/lang/Thread->currentThread()Ljava/lang/Thread;": {
                return vm.resolveClass("java/lang/Thread").newObject(Thread.currentThread());
            }
        }
        return super.callStaticObjectMethodV(vm, dvmClass, signature, vaList);
    }

    @Override
    public long callLongMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {
        switch (signature) {
            case "java/lang/Long->longValue()J": {
                java.lang.Long result = (java.lang.Long)dvmObject.getValue();
                return result;
            }
        }
        return super.callLongMethodV(vm, dvmObject, signature, vaList);
    }

    @Override
    public DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {
        switch (signature) {
            case "java/lang/Integer->getBytes(Ljava/lang/String;)[B":
                System.err.println(vaList.getIntArg(0));
                String arg_0 = String.valueOf(vaList.getIntArg(0));
                ByteArray result = new ByteArray(vm,arg_0.getBytes(StandardCharsets.UTF_8));
                return result;
            case "java/lang/Thread->getStackTrace()[Ljava/lang/StackTraceElement;": {
                DvmObject<?>[] a = {
                        vm.resolveClass("java/lang/StackTraceElement").newObject("dalvik.system.VMStack"),
                        vm.resolveClass("java/lang/StackTraceElement").newObject("java.lang.Thread")
                };
                return new ArrayObject(a);
            }
        }
        return super.callObjectMethodV(vm, dvmObject, signature, vaList);
    }

    public void decrypt(){
//        int i = 0x1000001;
//        int i2 = 0;
//        long j = 0;
//        String str = "0cb0c5";
//        byte[] obj = new byte[]{0x2d, 0x64, 0x07, 0x41, 0x50};
//        Object result = y2.callStaticJniMethodObject(emulator, "a(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;", i, i2, j, str, obj);
//        System.out.println("result:"+result);

        int i = 0x1000001;
        int i2 = 0;
        long j = 0;
        String str = "d91fba";
        byte[] obj = new byte[]{0x66, 0x38, 0x43, 0x1e, 0x58};
        Object result = y2.callStaticJniMethodObject(emulator, "a(IIJLjava/lang/String;Ljava/lang/Object;)Ljava/lang/Object;", i, i2, j, str, obj);
        System.out.println("result:"+result);
    }

    public void metasec(){
        String s1 = "https://api5-normal-m-hj.amemv.com/privacy/setting/change?iid=3247301440846819&device_id=397365608203400&ac=wifi&channel=douyinweb2_64_android&aid=1128&app_name=aweme&version_code=370400&version_name=37.4.0&device_platform=android&os=android&ssmix=a&device_type=Pixel+6&device_brand=google&language=zh&os_api=36&os_version=16&manifest_version_code=370401&resolution=1080*2146&dpi=420&update_version_code=37409900&_rticket=1769247175853&package=com.ss.android.ugc.aweme&first_launch_timestamp=1769245978&last_deeplink_update_version_code=0&cpu_support64=true&host_abi=arm64-v8a&is_guest_mode=0&app_type=normal&minor_status=0&appTheme=light&is_preinstall=0&need_personal_recommend=1&is_android_pad=0&is_android_fold=0&ts=1769247174&cdid=1a506faa-3555-49d0-9f25-44f7968645c1";
        String s2 = "cookie\r\n" +
                "passport_csrf_token=d0e6583384688b26714cd372e22d6c5e; passport_csrf_token_default=d0e6583384688b26714cd372e22d6c5e; store-region=cn-he; store-region-src=did; install_id=3247301440846819; ttreq=1$836482d2656977ff15663f05c6cb24bf4e14fdb6; odin_tt=2cc07cb8a8111f7a6c3ad1b3395693943d7b5dd0d19ca04d8a06c7cebe40c4ab989dbd6585e6c23dbf7d3be58cff359e6c5befc19dca7f8ef7882f8dee277a7b34061a8ae9120d15f53e8ee248f56cd3\r\n" +
                "x-tt-request-tag\r\n" +
                "t=0;n=0;s=0;p=0\r\n" +
                "x-tt-dt\r\n" +
                "AAAS5FGCSMPV2LPST6QFRAVVEHRHPJG6PHIDX7DAZ47VYPUE35FFRQDQEZWFURXE3LO4MANJ5SB6HM2W3BIZQKO7O3U3XLLI4MWUEFPC4HQC2EIXDI2G3ZY2TTEGO\r\n" +
                "activity_now_client\r\n" +
                "1769247174480\r\n" +
                "x-ss-req-ticket\r\n" +
                "1769247175855\r\n" +
                "sdk-version\r\n" +
                "2\r\n" +
                "passport-sdk-version\r\n" +
                "601486\r\n" +
                "x-vc-bdturing-sdk-version\r\n" +
                "4.1.1.cn\r\n" +
                "content-type\r\n" +
                "application/x-www-form-urlencoded; charset=UTF-8\r\n" +
                "x-ss-stub\r\n" +
                "FDF60E82C1607606E7386BA88D06B4CA\r\n" +
                "content-length\r\n" +
                "33\r\n" +
                "x-tt-store-region\r\n" +
                "cn-he\r\n" +
                "x-tt-store-region-src\r\n" +
                "did\r\n" +
                "x-ss-dp\r\n" +
                "1128\r\n" +
                "x-tt-trace-id\r\n" +
                "01-ef5976540d16966e3ec4488aaa3b0468-ef5976540d16966e-00\r\n" +
                "user-agent\r\n" +
                "com.ss.android.ugc.aweme/370401 (Linux; U; Android 16; zh_CN_#Hans; Pixel 6; Build/BP2A.250805.005; Cronet/TTNetVersion:6f1e308d 2025-12-08 QuicVersion:21ac1950 2025-11-18)\r\n" +
                "accept-encoding\r\n" +
                "gzip, deflate, br";

        Number number = module.callFunction(emulator,
                0x2A45F0, s1, s2
        );
        System.out.printf("0X%X\n", number.intValue());
        int hash = number.intValue();
        UnidbgPointer p = memory.pointer(hash & 0xffffffffL);
        System.out.println(p.getString(0));
    }

    public static void main(String[] args) {
        Sign6_370401 sign6 = new Sign6_370401();
        sign6.decrypt();
        sign6.metasec();
    }
}
\```

生成的结果如下:

```python
X-Perseus
RCRRRmNvH9uMYAw7bT0l+wSqcf6LGWY+iT4EIXkqmEO8gowS48PyPyL+wGwn3b8aknVFBSvilhZPgwDvSyUU48ahQu2Q4M5bCLyMLq0OgxNzuIYRdxKJ8xjNVuRkj4xOCZ9fNLjhIaXccD3qXRFfNkxyF0y4o7x+4NGgmpQc9hsFk4+3HlClNRZ7NhPRwZiBbnTlDYg04PMnzydEcGFQHwzNQFPMWPmQQLjcqy2rT3nzkgGShAAkIlhWnMACMnuLyx1fMIeaEDiTDYqR9z5adS5GUaGNUBPSxRAUJ1iQc1CMKFTLFDgGLrtmHYyeJCGishslzu4Mp10IjSAIQ/5nebhQKKb3SxIHfqaEaYJXo66rjUx9Tf7wZx4tqVRLA5fFmBR0dp/JADT5v+FHjj0DeenfJNso17IsUjgGr4UKpk+LHwmOcxRHrdvYafk7q6z/T/gZBmNRs7HhttDJC3unZPZ6JlRgW9U//Yxpo1Y8i02Q1o84pqtkBLFMlQ/hDNCMj1IhFLcPqJq6PR44KLyofgpxnjSyo8c5bJfby9Egjk67ChTsXXp8n23d1WDIhQAuSJRUpUGc+chcSRYBpdN2+5BoTD02wd3Xtv1TFJCkflTDlH18fmtEjfjSavhyOOVtxoG80+7c89d0NRitK2oDaN7aB12ev7zoGPipuTnBFyy3ckTn9LEMSNb3Hpy301ishcW/WWiwc7iF674CVK+MznbvOBwQj4g+etvebqjVRCWvoJBZvqFcFFvWcSBhx/lKyn41sAP4PfdQ
X-Medusa
L8h0aUNSX0NqU9v4qQJ2A+r+0Jcw3gANcmg5+Dzk+jbSfA2PPaYrdcoXAWIHmHkx09gApJOOlgv/nMqCQCo5GAql3bzX5XE7B1cttHty2SnaKaIVdfGfDarETUcoKRtp8t5FBH5SzMFRd+2mgdcqu5Yx28g0VoUuzwZdEQGG/7IXZW2ia/XGBU8ynZDjuvt7fYgtvRMaIMFlJep2yEUZhVevL2eU3KjxU41sDPI6XT7uh3X18Ia3tl967L5zeaV+WyyrUt3Jr5GyNNtDTk/xvyW8ZRZmAZURn4n//p+J//4sWw==
X-Argus
KMh0aQ==
X-Helios
4pAeH1ccsEKzASoWOYQJUwwwYAE2sU5zRqUwgEvB9F6+P6mX
X-Ladon
j6cNmg==
X-Khronos
1769261096
X-Gorgon
8404404900001acec54f66aea755c441911e7bf0d6a65bfde62f
\```

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-1-26 12:19*

感谢分享

## 回复 by kingking888 (#3)

*2026-1-26 13:52*

666

## 回复 by curtainzzzz (#4)

*2026-1-26 14:23*

66666666

## 回复 by uni7corn (#5)

*2026-1-26 14:49*

感谢分享。

## 回复 by 黑屏 (#6)

*2026-1-26 14:55*

66

## 回复 by Imxz (#7)

*2026-1-26 16:03*

tql

## 回复 by mb_pesxllvn (#8)

*2026-1-26 16:13*

666

## 回复 by 黑屏 (#9)

*2026-1-26 16:43*

77777

## 回复 by mb_nbhpszaj (#10)

*2026-1-26 16:44*

123

## 回复 by mb_mlyojneh (#11)

*2026-1-26 17:14*

https://bbs.kanxue.com/thread-289870.htm

## 回复 by 嘎嘎真的很棒 (#12)

*2026-1-26 19:02*

666

## 回复 by Superoot (#13)

*2026-1-26 19:19*

66666666

## 回复 by 寻梦之璐 (#14)

*2026-1-26 22:23*

111

## 回复 by tubecityman (#15)

*2026-1-27 05:09*

66666

## 回复 by linix (#16)

*2026-1-27 10:05*

666

## 回复 by hacker521 (#17)

*2026-1-27 10:15*

666

## 回复 by MaYil (#18)

*2026-1-27 10:23*

感谢分享

## 回复 by 丶咖啡猫丶 (#19)

*2026-1-27 10:49*

666

## 回复 by imcczy (#20)

*2026-1-27 11:06*

666

## 回复 by mb_ykavguun (#21)

*2026-1-27 12:13*

1

## 回复 by lmh2020 (#22)

*2026-1-27 12:16*

666

## 回复 by mb_qimctavn (#23)

*2026-1-27 13:09*

6

## 回复 by 机车王子 (#24)

*2026-1-27 16:11*

感谢你的积极参与，期待更多精彩内容！

## 回复 by mb_gqjaobpz (#25)

*2026-1-27 20:54*

牛逼

## 回复 by Corner_610006 (#26)

*2026-1-27 20:54*

666

## 回复 by daliands (#27)

*2026-1-27 20:54*

666

## 回复 by 梦笔随花 (#28)

*2026-1-27 20:54*

666

## 回复 by 蜡笔晓辉 (#29)

*2026-1-27 20:54*

fffffff

## 回复 by letme98 (#30)

*2026-1-27 20:55*

牛逼

## 回复 by mb_vmirashm (#31)

*2026-1-27 20:55*

6666

## 回复 by mb_cbgtaveo (#32)

*2026-1-27 23:16*

66666666

## 回复 by mb_qtjqaquw (#33)

*2026-1-28 05:20*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Rocky虞 (#34)

*2026-1-28 11:38*

666

## 回复 by 铭天星 (#35)

*2026-1-28 13:49*

666

## 回复 by mb_wunjysbn (#36)

*2026-1-28 14:08*

牛逼

## 回复 by 随风而行aa (#37)

*2026-1-28 14:19*

看看

## 回复 by git_94730eaydwshawke-gif (#38)

*2026-1-28 14:23*

666

## 回复 by mb_fywmigrm (#39)

*2026-1-28 16:22*

111

## 回复 by 温泉划水鱼 (#40)

*2026-1-28 17:28*

强

## 回复 by LQ6H (#41)

*2026-1-28 22:26*

666

## 回复 by fengvmu (#42)

*2026-1-29 09:49*

6

## 回复 by huangjw (#43)

*2026-1-29 10:21*

可以，还想问下这个是几神啊，7神吗

## 回复 by mb_xjdhrmck (#44)

*2026-1-29 14:38*

6666

## 回复 by 4Chan (#45)

*2026-1-29 15:38*

牛逼

## 回复 by huluxia (#46)

*2026-1-29 16:01*

66666666

## 回复 by mb_tjsboqui (#47)

*2026-1-29 16:29*

666

## 回复 by mb_empsallg (#48)

*2026-1-29 16:40*

大佬牛逼 分析到位

## 回复 by mb_bhsrdtqf (#49)

*2026-1-29 20:29*

6666

## 回复 by wx_Huber Barrientos (#50)

*2026-1-30 04:55*

666

## 回复 by 这谁写的代码 (#51)

*2026-1-30 07:41*

感谢

## 回复 by 九黎 (#52)

*2026-1-30 08:51*

学习学习

## 回复 by BestToYou (#53)

*2026-1-30 11:10*

666

## 回复 by 1sfans (#54)

*2026-1-30 11:46*

666

## 回复 by 小明的爱 (#55)

*2026-1-30 15:04*

感谢分享

## 回复 by mb_trortpvy (#56)

*2026-1-30 15:17*

666

## 回复 by mb_qfjnvedi (#57)

*2026-1-30 17:43*

牛儿逼之！！

## 回复 by vox (#58)

*2026-1-30 20:05*

nibu

## 回复 by wx_starfall (#59)

*2026-1-31 11:38*

66666666

## 回复 by mb_fywwfzew (#60)

*2026-1-31 22:57*

牛逼

## 回复 by maxcl (#61)

*2026-1-31 23:36*

看下  谢谢分享

## 回复 by mb_nntqdxvc (#62)

*2026-2-2 00:15*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by wc有蚊子 (#63)

*2026-2-2 16:52*

niubi

## 回复 by 下雨天sana (#64)

*2026-2-2 18:08*

666

## 回复 by mb_gqzoivfx (#65)

*2026-2-2 19:45*

牛逼

## 回复 by 王叔叔 (#66)

*2026-2-2 19:57*

666

## 回复 by 做好事不留名 (#67)

*2026-2-2 20:02*

1

## 回复 by method (#68)

*2026-2-3 11:25*

1

## 回复 by tjytjy (#69)

*2026-2-3 11:28*

666

## 回复 by wonhurry (#70)

*2026-2-3 15:27*

补补unidbg知识![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by mb_ssnabqqf (#71)

*2026-2-3 15:44*

1111

## 回复 by wx_小螃蟹 (#72)

*2026-2-3 16:45*

厉害

## 回复 by visionvv (#73)

*2026-2-3 17:13*

牛逼

## 回复 by wx_7788 (#74)

*2026-2-3 20:30*

7777

## 回复 by slbwgslz (#75)

*2026-2-3 20:33*

6666

## 回复 by 不具名的悲伤 (#76)

*2026-2-5 15:25*

6

## 回复 by 小今朝 (#77)

*2026-2-6 11:28*

666

## 回复 by jamlops (#78)

*2026-2-8 21:02*

看看

## 回复 by mb_fidppcok (#79)

*2026-2-9 10:34*

牛。很了不起的技术。

## 回复 by thouger_ (#80)

*2026-2-9 14:12*

牛逼

## 回复 by mb_ijumdife (#81)

*2026-2-10 09:06*

66666666

## 回复 by dob_C (#82)

*2026-2-10 09:46*

感谢分享

## 回复 by mb_wuevwbec (#83)

*2026-2-10 14:00*

牛逼

## 回复 by 司徒废人 (#84)

*2026-2-10 18:40*

感谢分享

## 回复 by git_41224nguyentruong190 (#85)

*2026-2-11 00:24*

6666666666

## 回复 by mb_pmgifpme (#86)

*2026-2-11 11:10*

1

## 回复 by mb_npsajqlx (#87)

*2026-2-11 11:17*

6

## 回复 by M.C (#88)

*2026-2-12 10:21*

NB

## 回复 by Mr.He (#89)

*2026-2-12 10:56*

6666

## 回复 by passself (#90)

*2026-2-13 16:52*

666

## 回复 by 星落黎明 (#91)

*2026-2-19 00:34*

感谢分享

## 回复 by albao (#92)

*2026-2-21 20:45*

感谢分享

## 回复 by myios (#93)

*2026-2-21 21:49*

666

## 回复 by Zireael (#94)

*2026-2-22 15:23*

牛逼

## 回复 by 勒LI (#95)

*2026-2-22 15:48*

666

## 回复 by mb_nswsoaro (#96)

*2026-2-22 18:57*

6

## 回复 by wuchonghua (#97)

*2026-2-23 19:30*

X-Medusa，我都还不会

## 回复 by mb_yaeaedrh (#98)

*2026-2-24 00:47*

6666

## 回复 by mb_ilyviizj (#99)

*2026-2-24 07:02*

111

## 回复 by A00乐淘 (#100)

*2026-2-24 09:30*

感谢分享 支持

## 回复 by kccp (#101)

*2026-2-24 09:34*

666

## 回复 by mb_hfbquwgl (#102)

*2026-2-24 10:41*

大佬威武

## 回复 by mb_roiscepd (#103)

*2026-2-24 11:31*

666

## 回复 by 窜天猴 (#104)

*2026-2-24 13:58*

666

## 回复 by baozidth (#105)

*2026-2-24 15:46*

666

## 回复 by mb_lizfxfno (#106)

*2026-2-24 20:23*

666

## 回复 by wx_插曲 (#107)

*2026-2-24 20:38*

66

## 回复 by lotus* (#108)

*2026-2-25 10:33*

6666

## 回复 by mb_rjyuyjmm (#109)

*2026-2-25 17:56*

666666

## 回复 by mb_ykkavacg (#110)

*2026-2-25 23:30*

6666

## 回复 by git_34020Charlotte-z (#111)

*2026-2-26 02:24*

6666

## 回复 by mb_wxvjqniz (#112)

*2026-2-26 02:59*

666

## 回复 by mb_wxvjqniz (#113)

*2026-2-26 03:20*

666

## 回复 by wx_-_127 (#114)

*2026-2-26 05:07*

接接接

## 回复 by linix (#115)

*2026-2-26 07:34*

666

## 回复 by dogfood (#116)

*2026-2-27 12:19*

6666666

## 回复 by mb_ffsfxcfz (#117)

*2026-3-1 18:37*

666

## 回复 by 独一无二_370133 (#118)

*2026-3-2 10:39*

1

## 回复 by melissa1210 (#119)

*2026-3-2 18:10*

thanks

## 回复 by mb_lnfgvyyu (#120)

*2026-3-6 15:58*

6666

## 回复 by pingsky (#121)

*2026-3-6 16:03*

感谢分享

## 回复 by xeiyu (#122)

*2026-3-6 23:54*

666

## 回复 by qig (#123)

*2026-3-8 17:55*

感谢分享

## 回复 by mb_ybvqgbkl (#124)

*2026-3-10 16:00*

66666

## 回复 by wx_nowind (#125)

*2026-3-10 19:13*

niuba

## 回复 by long_ (#126)

*2026-3-11 08:38*

11

## 回复 by mb_uokrnlrg (#127)

*2026-3-11 13:06*

666

## 回复 by 红皮西瓜 (#128)

*2026-3-11 14:54*

6

## 回复 by mb_xlviyutx (#129)

*2026-3-12 19:01*

666

## 回复 by jyotidwi (#130)

*2026-3-13 00:05*

66666

## 回复 by mb_fglogyec (#131)

*2026-3-13 06:34*

6666

## 回复 by uniking (#132)

*2026-3-16 11:23*

6

## 回复 by wx_fly_397447 (#133)

*2026-3-17 23:27*

6666

## 回复 by ak8888 (#134)

*2026-3-18 16:18*

厉害

## 回复 by wx_Yu_799 (#135)

*2026-3-20 10:01*

666

## 回复 by 0x530c (#136)

*2026-3-23 15:27*

666

## 回复 by 菜鸟9527 (#137)

*2026-3-23 15:46*

牛逼了

## 回复 by iBa0 (#138)

*2026-3-23 15:52*

123

## 回复 by XJ。 (#139)

*2026-3-23 19:35*

6

## 回复 by git_39829Makseeee (#140)

*2026-3-24 18:31*

666

## 回复 by xuhe123 (#141)

*2026-3-24 19:10*

666

## 回复 by mb_mgmaxnuw (#142)

*2026-3-25 00:27*

66666

## 回复 by fancy繁星 (#143)

*2026-3-25 19:17*

666

## 回复 by 我就是小熊猫 (#144)

*2026-3-27 15:39*

6666

## 回复 by PangBai (#145)

*2026-3-29 17:48*

1

## 回复 by mb_hebmqpll (#146)

*2026-4-2 14:14*

666

## 回复 by mb_mhcaipna (#147)

*2026-4-3 16:25*

牛逼牛逼

## 回复 by 爬虫不看学历 (#148)

*2026-4-3 17:08*

学习

## 回复 by mb_uzmffdbw (#149)

*2026-4-3 17:19*

666

## 回复 by XCicada (#150)

*2026-4-3 18:07*

感谢

## 回复 by lizhenzhe (#151)

*2026-4-4 20:18*

666

## 回复 by YANG、 (#152)

*2026-4-5 21:20*

666

## 回复 by 特洛伊Troye (#153)

*2026-4-5 21:47*

牛的

## 回复 by mb_nonzieas (#154)

*2026-4-7 16:04*

赞

## 回复 by Kk一刀 (#155)

*2026-4-7 16:25*

1111

## 回复 by PPTV (#156)

*2026-4-7 17:01*

期待更多精彩内容！

## 回复 by mb_rzyawund (#157)

*2026-4-7 17:42*

666

## 回复 by 学计算机睡觉 (#158)

*2026-4-8 23:39*

6666

## 回复 by linclsky (#159)

*2026-4-13 22:33*

666666

## 回复 by mb_tqdvviuj (#160)

*2026-4-16 00:30*

可以

## 回复 by sakmacc (#161)

*2026-4-16 10:40*

牛逼

## 回复 by mb_agxdcibq (#162)

*2026-4-17 11:16*

好文 ![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by xwtwho (#163)

*2026-4-17 11:21*

1

## 回复 by sir678 (#164)

*2026-4-17 13:44*

![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by mb_fjycmhem (#165)

*2026-4-17 14:53*

6

## 回复 by mb_paopxhtx (#166)

*2026-4-17 15:50*

666

## 回复 by git_23977jackmama12138 (#167)

*2026-4-17 21:09*

6666666666

## 回复 by 红叶疯了 (#168)

*2026-4-17 21:26*

感谢分享

## 回复 by mb_ermtvtqr (#169)

*2026-4-20 17:38*

666

## 回复 by 炫天使 (#170)

*2026-4-22 19:36*

感谢分享

## 回复 by samosxin (#171)

*2026-4-25 15:52*

111

## 回复 by Ankeys (#172)

*2026-4-26 11:44*

看看

## 回复 by oscar99999 (#173)

*2026-4-26 17:33*

666666

## 回复 by 街道办事处 (#174)

*2026-4-27 10:11*

111

## 回复 by 手把手教我吗 (#175)

*2026-4-27 12:08*

666

## 回复 by 呼吸24K纯氧 (#176)

*2026-4-27 20:18*

666

## 回复 by mb_fynvoaid (#177)

*2026-4-28 17:41*

wo cao niu bi

## 回复 by mb_fynvoaid (#178)

*2026-4-28 17:41*

wo cao niu bi 学习了

## 回复 by mb_fynvoaid (#179)

*2026-4-28 17:41*

wo cao niu bi 学习了

## 回复 by mb_fynvoaid (#180)

*2026-4-28 17:41*

牛逼啊，

## 回复 by mb_iiulbilc (#181)

*2026-4-30 09:16*

6666666

## 回复 by mb_rmhqkzps (#182)

*2026-5-7 16:02*

666

## 回复 by Big权 (#183)

*2026-5-9 10:40*

6666

## 回复 by mb_pveclrmt (#184)

*2026-5-9 10:45*

牛逼

## 回复 by mb_gpxzdoej (#185)

*2026-5-10 15:02*

感谢你的积极参与，期待更多精彩内容！

## 回复 by mb_ysikfhxt (#186)

*2026-5-10 23:02*

111

## 回复 by Splite_1130 (#187)

*2026-5-12 14:10*

666666

## 回复 by r8e8cd8 (#188)

*2026-5-13 19:21*

666

## 回复 by jw8888 (#189)

*2026-5-13 20:38*

6666666

## 回复 by mb_donutrph (#190)

*2026-5-14 00:14*

6

## 回复 by ponywin (#191)

*2026-5-17 11:15*

感谢分享

## 回复 by 信心风暴 (#192)

*2026-5-17 13:14*

888 厉害

## 回复 by KingSelyF (#193)

*2026-5-18 13:47*

牛逼

## 回复 by CheRevir (#194)

*2026-5-18 13:53*

666

## 回复 by memoriaru (#195)

*2026-5-18 14:36*

感谢分享

## 回复 by git_66341tikapiscom (#196)

*2026-5-18 20:17*

good!

## 回复 by 大笨钟 (#197)

*2026-5-21 18:02*

nb

## 回复 by 壹久玖 (#198)

*2026-5-21 20:44*

![image](https://bbs.kanxue.com/view/img/face/026.gif)

## 回复 by NSpron (#199)

*2026-5-23 05:15*

看看大佬

## 回复 by ovo_帮我不c (#200)

*2026-5-25 12:19*

11

## 回复 by 荷蒉丈人 (#201)

*2026-5-26 17:15*

666

## 回复 by runjin (#202)

*2026-5-26 20:26*

good

## 回复 by JX小丶 (#203)

*2026-5-26 20:41*

来看看

## 回复 by ycdear (#204)

*2026-5-26 22:11*

2

## 回复 by mb_sezgvuqb (#205)

*2026-5-26 23:04*

1

## 回复 by mb_qcshhquy (#206)

*2026-5-28 15:37*

nb

## 回复 by hanjiefang (#207)

*2026-6-5 15:45*

1

## 回复 by Tanuyoki0 (#208)

*2026-6-6 22:48*

学习一下

## 回复 by wx_Single (#209)

*2026-6-13 20:24*

牛逼,6666

## 回复 by mb_jegknedl (#210)

*2026-6-15 04:11*

学习

## 回复 by mb_kzjnlbla (#211)

*2026-6-16 13:37*

666学习下大佬的思路

## 回复 by Freax (#212)

*2026-6-16 15:54*

6

## 回复 by mb_xzwzvabc (#213)

*2026-6-17 12:20*

6666

## 回复 by mb_gnsvqbzz (#214)

*2026-6-19 00:27*

感谢分享

## 回复 by mb_osxdmntv (#215)

*2026-6-19 18:18*

666

## 回复 by git_98579rabbits0209 (#216)

*2026-6-20 14:30*

牛逼

## 回复 by mb_leghawkh (#217)

*2026-6-20 23:23*

nb

## 回复 by SilentXC (#218)

*2026-6-21 21:47*

66666666

## 回复 by 晴空万里丶 (#219)

*2026-6-22 00:38*

666

## 回复 by mb_ajxntfzc (#220)

*2026-6-22 02:39*

6666

## 回复 by hb6106 (#221)

*2026-6-22 08:55*

666

## 回复 by Timele (#222)

*2026-6-23 16:36*

666

## 回复 by APT_华生 (#223)

*2026-6-24 14:24*

牛逼

## 回复 by johnwas (#224)

*2026-6-26 16:53*

666

## 回复 by 3倍アイスクリーム! (#225)

*2026-7-3 14:50*

学习一下

## 回复 by 这样的我 (#226)

*2026-7-9 11:47*

1

## 回复 by mb_etqosgsk (#227)

*2026-7-22 07:26*

牛逼牛逼

## 回复 by mb_pjvujuri (#228)

*2026-7-23 00:26*

okok

## 回复 by mb_wcezgawj (#229)

*2026-7-23 02:27*

学习一下

## 回复 by jianxcao (#230)

*2026-7-23 11:16*

牛逼

## 回复 by mb_zmtxrnca (#231)

*2026-7-29 17:08*

4

## 回复 by 天道happy (#232)

*2026-7-29 17:15*

学习一下

## 回复 by 大萨达 (#233)

666

## 回复 by xiaoez (#234)

666

## 回复 by mb_ezrknqqn (#235)

666

## 回复 by mb_guzdnhio (#236)

666
