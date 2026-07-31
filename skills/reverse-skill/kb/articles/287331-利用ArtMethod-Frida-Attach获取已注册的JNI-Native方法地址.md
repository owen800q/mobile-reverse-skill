---
title: '[原创]利用ArtMethod，Frida Attach获取已注册的JNI Native方法地址'
url: https://bbs.kanxue.com/thread-287331.htm
tid: 287331
author: lihe07
date: '2025-06-23'
tags: [Android安全, 原创, 基础理论, 逆向分析, NDK分析, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T14:08:17+08:00'
replies: 3
---

## **问题背景**

在实际脱壳中，经常遇到应用程序无法Frida Spawn，只能Frida Attach进行分析的情况。大部分的安卓壳都会在App启动阶段加入Hook检测和反调试，而在App启动后Attach可以很好地避免被检测到。

但跳过App启动阶段，导致我们无法采用常见的Hook ArtMethod::RegisterNative方法来获得动态绑定的Native方法地址。本文以360加固为例，讨论一种获取正在运行中的App的Native方法地址的方法。

## 环境

1. 360加固的APP（包含Native方法 + exports隐藏 + JNI_OnLoad动态绑定）
2. Android 9 Pie
3. Frida v16

## 动态绑定流程

关于Native方法的动态绑定，论坛上已经有很多文章了，不过为了方便参考，此处便再次进行赘述。

当App调用 System.loadLibrary 加载 包含 JNI 的 .so 时，首先会像加载一个常规 .so 一样，调用 dlopen。这之后，如果发现该 .so 包含 JNI_OnLoad 方法，则会立即调用。大部分的动态绑定就是在这一阶段进行的（也有可能在之后进行，JNI允许更换绑定）。

动态绑定需要调用这样的方法：

```
static JNINativeMethod gMethods[] = {
    {"my_method", "()Ljava/lang/String;", (void*)my_method }};

(*env)->RegisterNatives(env, clazz, gMethods, sizeof(gMethods) / sizeof(gMethods[0]));
```

在Android平台上，JNI的RegisterNatives方法由Dalvik (Android 5之前) 或者 ART (Android 5或者更新) 实现。此处我们以Android 9为例，找到ART这部分的源代码

runtime/jni_internal.cc:

```
static jint RegisterNatives(JNIEnv* env,
                              jclass java_class,
                              const JNINativeMethod* methods,
                              jint method_count) {
    // 省略各种检查...
    for (jint i = 0; i < method_count; ++i) {
        // ...
        ArtMethod* m = FindMethod<true>(current_class.Ptr(), name, sig); // 获取到对应的ArtMethod
        // ...
        const void* final_function_ptr = m->RegisterNative(fnPtr); // ArtMethod上的注册方法
        // ...
    }
}
```

继续查看 ArtMethod::RegisterNative 的实现

runtime/art_method.cc:

```
const void* ArtMethod::RegisterNative(const void* native_method) {
    CHECK(IsNative()) << PrettyMethod();
    CHECK(native_method != nullptr) << PrettyMethod();
    void* new_native_method = nullptr;
    Runtime::Current()->GetRuntimeCallbacks()->RegisterNativeMethod(this,
                                                                  native_method,
                                                                  /*out*/&new_native_method);
    SetEntryPointFromJni(new_native_method);
    return new_native_method;
}
```

不难发现，如果我们能获得一个Native方法对应的ArtMethod对象，并读取它的 EntryPoint field，便可获得内存中已经解密后的Native方法位置，辅助我们进行dump分析。

## Frida实现

借助Frida-Java-Bridge，可以很轻松地实现这个操作。参考 [Frida-Java-Bridge 源代码](http://github.com/frida/frida-java-bridge/blob/main/lib/android.js) ， android.js 中已经提供了一些ArtMethod的封装方法（但没有导出）。

将其复制出，并根据 libart.so 中获取的 ArtMethod 字段的偏移量，我们可以写出如下封装：

```
function getApi(): any {
  return (Java as any).api
}

class StdString {
  handle: NativePointer;

  constructor() {
    this.handle = Memory.alloc(3 * Process.pointerSize);
  }

  dispose() {
    const [data, isTiny] = this._getData();
    if (!isTiny) {
      getApi().$delete(data);
    }
  }

  disposeToString() {
    const result = this.toString();
    this.dispose();
    return result;
  }

  toString() {
    const str = this.handle;
    const isTiny = (str.readU8() & 1) === 0;
    const data = isTiny ? str.add(1) : str.add(2 * Process.pointerSize).readPointer();
    return data.readUtf8String();
  }

  _getData() {
    const str = this.handle;
    const isTiny = (str.readU8() & 1) === 0;
    const data = isTiny ? str.add(1) : str.add(2 * Process.pointerSize).readPointer();
    return [data, isTiny];
  }
}

class ArtMethod {
  handle: NativePointer;

  constructor(handle: NativePointer) {
    this.handle = handle;
  }

  prettyMethod(withSignature = true) {
    const result = new StdString();
    getApi()['art::ArtMethod::PrettyMethod'](result, this.handle, withSignature ? 1 : 0);
    return result.disposeToString();
  }

  toString() {
    return `ArtMethod(handle=${this.handle})`;
  }

  methodIdx() {
    return this.handle.add(12).readU32();
  }

  isNative() {
    return (this.handle.add(4).readU32() & 0x100) != 0;
  }

  getJniEntry() {
    return this.handle.add(0x18).readPointer()
  }
}
```

封装的使用方法也十分简单：

```
const MyJni = Java.use("com.xxxx.app.MyJni");

const MyArtMethod = new ArtMethod(MyJni.myMethod.handle);

console.log(MyArtMethod.prettyMethod(true))
console.log("isNative:", MyArtMethod.isNative())
console.log("jniEntry:", MyArtMethod.getJniEntry())
```

---

# 回复

## 回复 by mb_cfjwplfo (#2)

*2025-6-23 21:56*

大佬您好，我想问一下frida hook这个prettymetod有什么用处，看它hook的时候也没用到啊

## 回复 by 清风QingFeng (#3)

*2025-6-24 00:57*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>
>  大佬您好，我想问一下frida hook这个prettymetod有什么用处，看它hook的时候也没用到啊
>
>

这个函数好像是可以打印出  class+方法签名，方便查看是哪个类的哪个方法正在注册

## 回复 by lihe07 (#4)

*2025-6-24 12:27*

>
> [清风QingFeng](https://bbs.kanxue.com/user-1038905.htm)
>
>  这个函数好像是可以打印出 class+方法签名，方便查看是哪个类的哪个方法正在注册
>
>

嗯，对的。ArtMethod::PrettyMethod当传入True的时候，返回带函数签名的方法名，类似这样：

```
"java.lang.String com.demo.MyClass.myMethod(java.lang.Object, java.lang.String)"
```

传入False的时候，就只返回方法名：

```
"com.demo.MyClass.myMethod"
```
