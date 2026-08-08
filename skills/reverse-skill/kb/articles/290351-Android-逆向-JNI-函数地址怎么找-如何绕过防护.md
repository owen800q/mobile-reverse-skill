---
title: '[原创]Android 逆向：JNI 函数地址怎么找？如何绕过防护？'
url: https://bbs.kanxue.com/thread-290351.htm
tid: 290351
author: 0xCodeMaster
date: '2026-03-16'
tags: [Android安全, 原创, 逆向分析, NDK分析]
crawled_at: '2026-08-08T10:18:50+00:00'
replies: 68
---

# Native函数动态注册与寻址基础

JNI 函数有两种注册方式，也是所有攻防技术的基础：

- 静态注册：通过 `Java_包名_类名_方法名` 函数名规则自动匹配
- 动态注册：通过 `RegisterNatives()` 手动注册 `JNINativeMethod` 结构体

静态注册通过IDA总结观察其方法名称即可找到，而动态注册一般情况下需要通过HOOK RegisterNatives即可抓取函数地址。

# **隐藏Native动态注册痕迹：不直接调用 RegisterNatives 的 Native 注册技术**

我们不再乖乖地调用官方 JNI 接口，而是先让系统已经帮我们填好的那部分当“样本”，量一量结构体的布局，然后照着写，后续所有 Java → native 的绑定，全靠手动写指针完成。

想靠写内存实现“注册”，你必须知道写哪儿。
换句话说：在当前 Android 版本里，`ArtMethod` 结构体里，那个存 native 函数入口地址的字段，到底偏移多少？

于是就有了这套“样本探测”思路：

1. 找一个你已经 明确知道注册关系 的 Java 方法 ↔ C 函数。
2. 在运行时，拿到这个 Java 方法对应的 `ArtMethod*`。
3. 再拿到对应的 C 函数地址（就是你自己的 `native` 函数指针）。
4. 在 `ArtMethod` 这块内存中，用“扫描指针值”的方式找到哪一个字段正好等于这个 C 函数地址。
5. 那个字段所在的位置，就是当前系统真实的 `entry_point_from_quick_compiled_code_` 偏移。
6. 一旦这个偏移算出来，以后就不用再 `RegisterNatives` 了，所有注册统统变成：`entry_ptr = my_func_addr`。

刚好存在一个函数GetMethodID这个函数的返回值就是ArtMethod *

## 具体实现

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137 | `// ========================================================``// ArtMethod 结构体参考（Android 8/9/10 大致布局）``//``// 这里列出来是为了说明：``//   jmethodID 本质上就是 ArtMethod* 指针``//   其中 data_ 字段存放的就是 JNI native 函数的地址``//   entry_point_from_quick_compiled_code_ 是执行入口``//``// 但不同 Android 版本中各字段的偏移不同！``// 所以这段代码没有硬编码偏移，而是用"动态探测"的方式找到偏移``// ========================================================``/*``struct ArtMethod {``uint32_t declaring_class_;``std::atomic<std::uint32_t> access_flags_;``uint32_t dex_code_item_offset_;``uint32_t dex_method_index_;``uint16_t method_index_;``uint16_t hotness_count_;``void *dex_cache_resolved_methods_;``void *data_;                                  // ← native 函数指针存在这里``void *entry_point_from_quick_compiled_code_;``};``*/`  `// -------------------- 两个 native 函数实现 --------------------` `/**``* 真正要隐蔽注册的 native 函数``* 对应 Java 层: public native String stringFromJNI();``*``* 关键：这个函数不会通过 RegisterNatives 注册``*       而是通过直接写 ArtMethod 内存来注册``*       所以 Hook RegisterNatives 的工具（如 Frida）捕获不到它``*/``jstring stringFromJNI(``JNIEnv *env,``jobject``/* this */``) {``std::string hello =``"Anti Trace JNI"``;``return` `env->NewStringUTF(hello.c_str());``}` `/**``* "探针"函数 / "牺牲品"函数``* 对应 Java 层: public native int getoffset();``*``* 这个函数会通过正常的 RegisterNatives 注册``* 目的不是为了业务，而是为了：``*   注册后，ArtMethod 中 data_ 字段会被写入 getoffset 的地址``*   通过遍历 ArtMethod 内存，找到 getoffset 地址出现的位置``*   从而确定 data_ 字段在 ArtMethod 结构体中的偏移（index）``*/``jint getoffset(``JNIEnv *env,``jobject``/* this */``) {``return` `100;``}`  `// -------------------- JNI_OnLoad: 核心逻辑 --------------------` `JNIEXPORT jint JNICALL JNI_OnLoad(JavaVM *vm,``void` `*reserved) {` `// ---- 第 1 步：获取 JNIEnv ----``JNIEnv *env = nullptr;``if` `(vm->GetEnv((``void` `**) &env, JNI_VERSION_1_6) != JNI_OK) {``return` `JNI_ERR;``}` `// ---- 第 2 步：找到 Java 类和方法 ID ----``// jmethodID 本质上就是 ArtMethod* 指针``jclass MainActivity_jclass = env->FindClass(``"com/cr/algorithmproject/MainActivity"``);` `// ================================================================``//  ---- 第 3 步：用"探针"函数 getoffset 动态探测偏移 ----``// ================================================================` `// 3.1 通过正常的 RegisterNatives 注册 getoffset``//     注册后，ART 会把 getoffset 函数指针写入``//     getoffset_jmethodID 对应的 ArtMethod 的 data_ 字段``//``//     这一步会被 Frida 的 RegisterNatives Hook 捕获``//     但这只是"探针"，真正要保护的 stringFromJNI 不走这条路``JNINativeMethod methods[] = {``{``"getoffset"``,``"()I"``, (``void` `*) getoffset},``};``env->RegisterNatives(MainActivity_jclass, methods, 1);` `// 3.2 获取 getoffset 的 jmethodID（即 ArtMethod*）``jmethodID getoffset_jmethodID = env->GetMethodID(``MainActivity_jclass,``"getoffset"``,``"()I"``);` `// 3.3 把 getoffset 的 ArtMethod* 当作 void* 数组来遍历``//     在内存中逐个 pointer 搜索，找到值 == getoffset 函数地址的那个位置``//     那个位置的 index 就是 data_ 字段在 ArtMethod 中的偏移（以 pointer 为单位）``//``//     原理：``//       ArtMethod 内存布局（以 void* 数组视角看）：``//       array[0] = declaring_class_ + access_flags_（可能合并）``//       array[1] = dex_code_item_offset_ + dex_method_index_``//       ...``//       array[N] = data_ = (void*)getoffset  ← 找的就是这个 N``//       ...``//``void` `**array = (``void` `**) getoffset_jmethodID;``int` `index = 0;``while` `(array[index] != (``void` `*) getoffset) {``index++;``}``// 此时 index 就是 data_（native 函数指针）在 ArtMethod 中的偏移``// 这个偏移在当前 Android 版本 + 当前设备上是准确的``// 不需要硬编码任何结构体偏移！`  `// ================================================================``//  ---- 第 4 步：直接写内存，完成 stringFromJNI 的"隐蔽注册" ----``// ================================================================` `// 把 stringFromJNI 的 ArtMethod* 也当作 void* 数组``// 用刚才探测到的 index，直接把 stringFromJNI 函数指针写进去``//``// 等价于: artMethod->data_ = (void*)stringFromJNI;``// 但不调用任何 JNI API，直接操作内存``//``// 这一步：``//   ✗ 不走 RegisterNatives       → Frida Hook RegisterNatives 抓不到``//   ✗ 不走 ArtMethod::RegisterNative → Frida Hook RegisterNative 也抓不到``//   ✗ 不走 SetEntryPointFromJni  → Hook 这个也抓不到``//   ✓ 纯内存写入                  → 只有监控 mprotect/内存写入才可能发现``array = (``void` `**) stringFromJNI_jmethodID;``array[index] = (``void` `*) stringFromJNI;` `return` `JNI_VERSION_1_6;``}` |
|-|-|

通过上面这种不直接调用 RegisterNatives 的注册方式，可以很好地隐藏 JNI 函数。攻击者根本无法通过传统 Hook RegisterNatives 的方式，拿到 Java  native 函数在 so 里的真实偏移与地址。

难道遇到这种防护，我们就束手无策了吗？

当然不是。这里给大家分享一个通杀思路：不去管它怎么注册、怎么隐藏，我们直接去遍历目标类的 ArtMethod，把里面的关键字段打印出来，就能直接拿到 Java 方法与 Native 函数的对应关系，从虚拟机层面绕过所有注册层防护

# 高级绕过：遍历指定类的ArtMethod

**原理：Java 函数最终指向 Native 层的 `ArtMethod`**

**思路如下：**

**1、用 Runnable 当“探针”自动探测 methods_ 偏移**

- 通过 env.findClass("java/lang/Runnable") 拿到系统接口 Runnable，再用 getMethodId("run", "()V") 获取它唯一的那个方法的 methodId。
- 因为 Runnable 只有一个 run()，所以这个 methodId 就是 ArtMethod[0] 的地址，直接减去 LengthPrefixedArray 头部大小（32 位减 4，64 位减 8）就能反推出整块 LengthPrefixedArray<ArtMethod> 的首地址。
- 把这个地址转成 uint64，在 Runnable 对应的 mirror::Class 内存里，从偏移 0 开始每 4 个字节读一次 U64，找到那个等于我们刚才算出的值的位置，这个 offset 就是当前系统上 mirror::Class::methods_ 字段的真实偏移，这样可以解决不同系统版本中methods_ 字段偏移可能不同的情况。

**2、通过枚举 ClassLoader 找到任意 Java 类的 jclass**

- 因为目标类不一定能直接用 env.findClass 找到，所以用 Java.enumerateClassLoaders 把所有 ClassLoader 走一遍。
- 对每个 loader 调用 Class.forName(targetClassName, false, loader)（这里传全限定名 "com.cr.Lsposed_ShadowHook.MainActivity"），哪一个不抛异常且返回非空，就是正确的 Class。

**3、借助 DecodeJObject 将jclass转换为 C++ 的 mirror::Class***

- 调用 DecodeJObject(thread_self, jclass_ptr) 把 Java 的 Class 解到 ART 里的 mirror::Class*，这是 C++ 层真正的类对象。
- 用第一步算出来的 methods_offset，在 mirror::Class* 内存上 add(methods_offset).readPointer()，就得到了 LengthPrefixedArray<ArtMethod>*。
- LengthPrefixedArray<ArtMethod>内存结构就是ArtMethod数量+ArtMethod数组

**4、按你逆出来的ArtMethod偏移拆解 ArtMethod 内容**

- 以 64 位为例，针对你那版结构体：
- +0x04 读取 access_flags_ 看方法修饰符。
- +0x08 / +0x0c / +0x10 / +0x12 分别读 dex_code_item_offset_、dex_method_index_、method_index_、hotness_count_。
- +0x18 / +0x20 / +0x28 分别读取 dex_cache_resolved_methods_、data_、entry_point_from_quick_compiled_code_，其中 entry_point 就是 native/quick 入口地址。

- 遍历 methods_count 次，每次用 method_array_data.add(i * art_method_size) 定位到当前 ArtMethod 指针，然后按这些偏移把信息全部打印出来。

**5、通过 PrettyMethod 把 ArtMethod 转成人类可读的方法名**

- 在 libart.so 里遍历导出符号，模糊匹配名字里同时包含 "art", "ArtMethod", "PrettyMethod" 的符号，拿到它的地址。
- 结合不同 Android 版本的实现，封装出适配当前 ABI 的 NativeFunction，再在 JS 里准备好 std::string 的临时缓冲区，调用后用你写的 readStdString 从返回的 std::string 结构里把真正的 UTF‑8 字符串读出来。
- 在遍历 ArtMethod 时，对每一个 currentMethodPtr 调一次 callprettymethod(currentMethodPtr)，日志里就能看到“类名.方法名(签名)”和对应的 entry_point，方便后续做 inline hook 或直接改入口指针。

**Frida脚本的具体实现如下：**

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274 | `function` `pointerToUInt64(ptr) {``return` `uint64(ptr.toString());``}` `/**``* 核心工具函数：动态探测并获取 mirror::Class 中 methods_ 字段的偏移量``* 原理：借助系统类 java.lang.Runnable 和其已知方法 run()，反推 methods_ 在内存中的位置``*/``function` `getArtMethodArrayOffset(env, thread_self, DecodeJObject) {``var` `pointerSize = Process.pointerSize;` `// LengthPrefixedArray 的头部大小 (32位系统为4字节，64位系统为了8字节对齐会补4字节空位，共8字节)``var` `array_header_size = (pointerSize === 8) ? 8 : 4;``// 1. 获取系统绝对存在的、只有一个方法的接口：Runnable``var` `runnableClass = env.findClass(``"java/lang/Runnable"``);``var` `runnableMirrorClass = DecodeJObject(thread_self, runnableClass);` `// 2. 获取唯一的 run() 方法的 methodId``var` `runMethodId = env.getMethodId(runnableClass,``"run"``,``"()V"``);` `if``(IsErrorLog)``console.log(``"array_header_size:  "``+ array_header_size +``"  runnableMirrorClass:   "``+runnableMirrorClass  +``"  runMethodId:  "``+runMethodId   );`  `// =====================================================================``// 因为 Runnable 只有 run() 这一个方法，所以 run() 的 index 绝对是 0。``// methodId 就是 ArtMethod[0] 的地址。``// 直接减去 header 即可得到数组对象指针！``// =====================================================================``var` `lengthPrefixedArrayPtr = runMethodId.sub(array_header_size);``// 转换为 uint64_t 用于内存严谨比对``var` `expectedMethodsValue64 = pointerToUInt64(lengthPrefixedArrayPtr);` `// console.log("[*] Expected Runnable methods_ uint64_t: " + expectedMethodsValue64.toString(16));``// 3. 在 Runnable 的 mirror::Class 内存中暴力搜索这个 uint64_t``for` `(``var` `offset = 0x0; offset < 0x150; offset += 4) {``var` `val64 = runnableMirrorClass.add(offset).readU64();` `if` `(val64.equals(expectedMethodsValue64)) {``env.deleteLocalRef(runnableClass);``return` `offset;``}``}` `env.deleteLocalRef(runnableClass);``return` `-1;``}` `/**``* 辅助函数：获取 DecodeJObject 函数指针``*/``function` `getDecodeJObjectFunc() {``var` `libart = Process.getModuleByName(``"libart.so"``);``var` `symbols = libart.enumerateSymbols();``for` `(``var` `i = 0; i < symbols.length; i++) {``var` `sym = symbols[i];` `if` `(sym.name.indexOf(``"DecodeJObject"``) !== -1 && sym.name.indexOf(``"Thread"``) !== -1) {``return` `new` `NativeFunction(sym.address,``'pointer'``, [``'pointer'``,``'pointer'``]);``}``}``return` `null``;``}` `/*``辅助函数：输出 std::string 字符串``*/``function` `readStdString(str) {``const isTiny = (str.readU8() & 1) == 0;``if` `(isTiny) {``return` `str.add(1).readUtf8String();``}``return` `str.add(2 * Process.pointerSize).readPointer().readUtf8String();``}` `/*``辅助函数：通过ArtMethod指针调用PrettyMethod获取方法名称``*/` `function` `callprettymethod(ArtMethodptr) {``var` `libartmodule = Process.getModuleByName(``"libart.so"``);``var` `PrettyMethodaddr =``null``;``libartmodule.enumerateExports().forEach(``function` `(symbol) {``//android 7``//_ZN3art12PrettyMethodEPNS_9ArtMethodEb``//_ZN3art12PrettyMethodEPNS_9ArtMethodEb``// if (symbol.name == "_ZN3art12PrettyMethodEPNS_9ArtMethodEb") {``//     Log("find PrettyMethod:" + JSON.stringify(symbol));``//     PrettyMethodaddr = symbol.address;``// }``//_ZN3art9ArtMethod12PrettyMethodEb``//Android 8``// if (symbol.name == "_ZN3art9ArtMethod12PrettyMethodEb") {``//     Log("find PrettyMethod:" + JSON.stringify(symbol));``//     PrettyMethodaddr = symbol.address;``// }``if` `(symbol.name.indexOf(``"PrettyMethod"``) != -1 && symbol.name.indexOf(``"ArtMethod"``) != -1 && symbol.name.indexOf(``"art"``) != -1) {``//Log("find PrettyMethod:" + JSON.stringify(symbol));``PrettyMethodaddr = symbol.address;``}``});``var` `PrettyMethodfunc =``new` `NativeFunction(PrettyMethodaddr, [``"pointer"``,``"pointer"``,``"pointer"``], [``"pointer"``,``"int"``]);``var` `result = PrettyMethodfunc(ArtMethodptr, 1);``var` `stdstring = Memory.alloc(3 * Process.pointerSize);``ptr(stdstring).writePointer(result[0]);``ptr(stdstring).add(1 * Process.pointerSize).writePointer(result[1]);``ptr(stdstring).add(2 * Process.pointerSize).writePointer(result[2]);``var` `funcnamestring = readStdString(stdstring);``return` `funcnamestring;``}``var` `env;``var` `pointerSize;``var` `thread_self;``var` `DecodeJObject;``var` `methods_offset;``var` `IsErrorLog;``function` `Init_()``{``env = Java.vm.getEnv();``pointerSize = Process.pointerSize;` `// 1. 获取 Thread* self``thread_self = env.handle.add(pointerSize).readPointer();` `// 2. 获取 DecodeJObject 函数``DecodeJObject = getDecodeJObjectFunc();``//var PrettyMethod = getPrettyMethodFunc();``if` `(!DecodeJObject) {``if``(IsErrorLog)``console.log(``"[-] Could not find DecodeJObject or ArtMethod::PrettyMethod in libart.so"``);``return``;``}`  `// ==========================================``// 第一阶段：通过系统类探测 methods_ 偏移量 (探测一次，终身受用)``// ==========================================``methods_offset = getArtMethodArrayOffset(env, thread_self, DecodeJObject);``if` `(methods_offset === -1) {``if``(IsErrorLog)``console.log(``"[-] Failed to find methods_ array offset via system class."``);``return``;``}``if``(IsErrorLog)``console.log(``"[+] Successfully detected 'methods_' offset: 0x"` `+ methods_offset.toString(16));``return``;``}`  `/**``* 主逻辑：解析目标类的 ArtMethod 数组``*/``function` `exploreArtMethod(targetClassName) {` `// ==========================================``// 枚举所有类加载器通过 Class.forName 查找目标类``// ==========================================``var` `jclass_ptr =``null``;``var` `ClassDef = Java.use(``"java.lang.Class"``);``// 拿到 java.lang.Class 的反射类``Java.enumerateClassLoaders({``onMatch:``function``(loader) {``try` `{``// [核心操作]：调用 Class.forName("xxx", false, loader)``// 这会返回一个真实的 java.lang.Class 实例对象``var` `javaClassObj = ClassDef.forName(targetClassName,``false``, loader);``if``(IsErrorLog)``console.log(``"    -> javaClassObj: "` `+ javaClassObj);``if` `(javaClassObj !=``null``) {``// 【绝杀】：提取这个 Class 实例的底层 JNI 句柄``// 兼容所有 Frida 版本：依次尝试 $h, $handle, handle``var` `rawHandle = javaClassObj.$h \|\| javaClassObj.$handle \|\| javaClassObj.handle;` `// 明确转换为 NativePointer，彻底杜绝 expected a pointer 报错！``jclass_ptr = ptr(rawHandle.toString());``if``(IsErrorLog)``{``console.log(``"[+] Found class via Class.forName!"``);``console.log(``"    -> ClassLoader: "` `+ loader);``console.log(``"    -> jclass pointer: "` `+ jclass_ptr);``}`  `return` `'stop'``;``// 找到了，停止遍历``}``}``catch``(e) {``// 当前 loader 没找到，会抛出 ClassNotFoundException，直接忽略继续找下一个``if``(IsErrorLog)``console.log(``"[-] 没找到 "` `);``}``},``onComplete:``function``() {}``});``// 校验是否真正拿到了 jclass 指针``if` `(jclass_ptr ===``null` `\|\| jclass_ptr.isNull()) {``if``(IsErrorLog)``console.log(``"[-] Target class not found in any ClassLoader: "` `+ targetClassName);``return``;``}`  `// ==========================================``// 通过 DecodeJObject 将jclass转换为 mirror::Class*``// ==========================================``var` `mirror_class = DecodeJObject(thread_self, jclass_ptr);``if``(IsErrorLog)``console.log(``"[*] Target mirror::Class* : "` `+ mirror_class);` `// ==========================================``// 通过 之前拿到的偏移加上类指针，就可以拿到 methods_ 指针``// ==========================================``var` `methods_ptr = mirror_class.add(methods_offset).readPointer();``if` `(methods_ptr.isNull()) {``if``(IsErrorLog)``console.log(``"[-] Target class has no methods (methods_ ptr is NULL)."``);``return``;``}` `//var ptr_sized_offset = (pointerSize === 8) ? 0x18 : 0x14;``var` `art_method_size = (pointerSize === 8) ? 48 : 32;``var` `array_header_size = (pointerSize === 8) ? 8 : 4;`  `// ==========================================``// 解析 LengthPrefixedArray``// 内存布局：``// 4字节长度 + 数组数据``// ==========================================``var` `methods_count = methods_ptr.readU32();``var` `method_array_data = methods_ptr.add(array_header_size);``if``(IsErrorLog)``console.log(``"\n[*] Found "` `+ methods_count +``" methods in "` `+ targetClassName);`    `console.log(``"--- Traversing ArtMethod Array ---"``);` `// ==========================================``// 遍历 ArtMethod 数组``// 每个 ArtMethod 结构体大小为 art_method_size 字节``// ==========================================``for` `(``var` `i = 0; i < methods_count; i++) {``var` `currentMethodPtr = method_array_data.add(i * art_method_size);` `// 读取你定义的结构体字段``var` `class_ = currentMethodPtr.add(0x00).readPointer();``var` `access_flags = currentMethodPtr.add(0x04).readU32();``var` `dex_code_item_offset = currentMethodPtr.add(0x08).readU32();``var` `dex_method_index_ = currentMethodPtr.add(0x0c).readU32();``var` `method_index = currentMethodPtr.add(0x10).readU16();``var` `hotness_count_ = currentMethodPtr.add(0x12).readU16();``var` `dex_cache_resolved_methods_ = currentMethodPtr.add(0x18).readPointer();``var` `data_ = currentMethodPtr.add(0x20).readPointer();``var` `entry_point = currentMethodPtr.add(0x28).readPointer();` `console.log(``"==============================================================="``);``console.log(``"[Method "` `+ i +``"] "` `+``"\nArtMethodAddr: "` `+ currentMethodPtr +``"\nname: "``, callprettymethod(currentMethodPtr, 1)+``"\nEntryPoint: "` `+ entry_point+``"\ndata_: "` `+ data_ +``"\n"``);`  `}` `}`  `Java.perform(``function` `() {``//是否启动错误日志``IsErrorLog = 0;``Init_();``exploreArtMethod(``"com.cr.Lsposed_ShadowHook.MainActivity"``);` `});` |
|-|-|

---

# 回复

## 回复 by mb_ysikfhxt (#2)

*2026-3-16 21:28*

1

## 回复 by wx_插曲 (#3)

*2026-3-17 06:59*

1

## 回复 by Imxz (#4)

*2026-3-17 09:13*

rbq

## 回复 by wlmf (#5)

*2026-3-17 11:02*

mark

## 回复 by mb_roiscepd (#6)

*2026-3-17 11:27*

666

## 回复 by mb_qimctavn (#7)

*2026-3-17 11:36*

6

## 回复 by mb_lsbvvhcp (#8)

*2026-3-17 16:00*

666

## 回复 by Gryffindoss (#9)

*2026-3-18 10:28*

666

## 回复 by pingsky (#10)

*2026-3-18 11:48*

TQL

## 回复 by guijingwen (#11)

*2026-3-18 16:50*

66

## 回复 by 北袅 (#12)

*2026-3-19 08:10*

1

## 回复 by ab19950220 (#13)

*2026-3-19 08:52*

666

## 回复 by huangjw (#14)

*2026-3-19 09:26*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_njmrwrqv (#15)

*2026-3-19 11:57*

ab19950220
  13 楼
666

## 回复 by mb_rztmbvgb (#16)

*2026-3-19 18:45*

666

## 回复 by SomeMx (#17)

*2026-3-19 18:51*

过来瞧瞧

## 回复 by xuhe123 (#18)

*2026-3-20 11:44*

666666

## 回复 by 4Chan (#19)

*2026-3-20 17:27*

666

## 回复 by xeiyu (#20)

*2026-3-20 17:57*

666

## 回复 by wuchonghua (#21)

*2026-3-21 02:38*

cmd怎么找呢

## 回复 by 明未央 (#22)

*2026-3-21 18:52*

6666666666666

## 回复 by mb_hziqyrum (#23)

*2026-3-21 21:12*

666

## 回复 by guardia (#24)

*2026-3-21 21:28*

666

## 回复 by 墨穹呢 (#25)

*2026-3-21 21:55*

感谢分享

## 回复 by iBa0 (#26)

*2026-3-21 23:04*

123

## 回复 by vicora (#27)

*2026-3-23 15:22*

666

## 回复 by mb_ghcouuzx (#28)

*2026-3-23 15:31*

感谢分享

## 回复 by reserve_zhou (#29)

*2026-3-24 12:23*

感谢分享

## 回复 by 心有万象 (#30)

*2026-3-25 10:05*

666

## 回复 by Am1re (#31)

*2026-3-25 11:37*

666

## 回复 by 黑嘿黑 (#32)

*2026-3-26 14:05*

mark

## 回复 by tonykros (#33)

*2026-3-27 21:52*

666

## 回复 by lackone (#34)

*2026-3-28 11:19*

6666

## 回复 by mb_twbjvgyf (#35)

*2026-3-29 08:30*

1

## 回复 by 呆萌的小白 (#36)

*2026-3-29 08:33*

必须看一下,学一下,虽然不会,但是看完就忘不了了

## 回复 by mb_stdlrcgp (#37)

*2026-3-29 13:55*

66666

## 回复 by mb_gqtfyqhu (#38)

*2026-3-29 15:16*

666

## 回复 by 星辰北天 (#39)

*2026-3-29 17:03*

感谢分享

## 回复 by mb_glkitklk (#40)

*2026-3-29 21:47*

很精彩的文章

## 回复 by 小黄鸭爱学习 (#41)

*2026-3-30 17:04*

66666

## 回复 by huangbof (#42)

*2026-3-30 19:17*

感谢分享

## 回复 by mb_oqssebnp (#43)

*2026-3-30 20:27*

感谢分享

## 回复 by A0x01 (#44)

*2026-3-30 20:45*

666

## 回复 by mb_dmjhowok (#45)

*2026-3-31 10:08*

66666

## 回复 by L11 (#46)

*2026-4-1 07:54*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 夜惜风雨 (#47)

*2026-4-2 11:03*

666666

## 回复 by 随风而行aa (#48)

*2026-4-2 11:12*

看看

## 回复 by mb_ttjjlead (#49)

*2026-4-2 11:28*

666

## 回复 by 小Tzzz (#50)

*2026-4-2 12:14*

666

## 回复 by mb_goqnmbff (#51)

*2026-4-5 13:33*

cmd怎么找呢

## 回复 by wx_妳还是不懂 (#52)

*2026-4-6 20:20*

非常感谢

## 回复 by 小迷糊ddd (#53)

*2026-4-6 22:49*

感谢分享，认真学习。

## 回复 by mb_ootypyxb (#54)

*2026-4-9 18:59*

感谢

## 回复 by mb_wwvrilgs (#55)

*2026-4-21 11:26*

666

## 回复 by mb_rirvdrlh (#56)

*2026-4-21 23:43*

666666

## 回复 by zhao3261 (#57)

*2026-4-25 11:17*

感谢分享

## 回复 by uni7corn (#58)

*2026-4-27 14:25*

感谢分享

## 回复 by mb_rbvykvqm (#59)

*2026-5-2 21:19*

感谢老铁

## 回复 by 末日大哥 (#60)

*2026-5-2 21:52*

666

## 回复 by wx_OME (#61)

*2026-5-5 19:35*

感谢分享

## 回复 by wx_北极星_493 (#62)

*2026-5-7 12:36*

看看

## 回复 by mb_cviyuksx (#63)

*2026-5-8 11:34*

666

## 回复 by Nu1lN0ne (#64)

*2026-5-8 17:26*

学习

## 回复 by mb_lzotvdxv (#65)

*2026-5-9 19:59*

请在 Telegram 上联系我，有个重要的 2000 美元任务。 Telegram：@dlopenext

## 回复 by wx_逝水无痕 (#66)

*2026-6-3 11:51*

666

## 回复 by XCicada (#67)

*2026-6-3 12:19*

666

## 回复 by wanderdeng (#68)

*2026-7-1 18:47*

很好的啊

## 回复 by Vengeance (#69)

*2026-7-22 11:31*

666
