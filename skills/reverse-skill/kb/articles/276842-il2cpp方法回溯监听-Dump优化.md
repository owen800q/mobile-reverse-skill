---
title: il2cpp方法回溯监听&Dump优化
url: https://bbs.kanxue.com/thread-276842.htm
tid: 276842
author: 珍惜Any
date: '2023-04-13'
tags: [Android安全, 基础理论, 逆向分析, NDK分析, 协议分析, 混淆加固, 脱壳反混淆, HOOK注入, 系统相关]
crawled_at: '2026-08-11T08:48:15+00:00'
replies: 22
---

# il2cpp方法回溯监听&Dump优化

## 前言：

最近在看一个单机游戏，il2cpp做的，以前没研究过游戏，顺便花一点时间看看 。现在市面上主要分为两种游戏 。

 Lua和U3d ，Lua现在大部分都被淘汰，貌似代码框架很多年没有人维护了，想要Hook和和源码替换的话也很简单，直接Hook buff_load即可 。还有的是各种变种,Luajit,Luaq 之类的，这种需要去找对应的opencode ，解密以后在进行替换。这里不是我们的重点不多说 。

 重点介绍一下u3d的对抗，最早的U3D都是dll文件，直接打包出来的，这种作弊也很简单，直接反编译dll。修改函数即可 。

 而现在核心的u3d游戏都是il2cpp的 ，在C#写的代码转换成C++代码，从而直接在各种平台上运行。在安卓上也是如此 。

 官方的一张原理图：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202304/819934_8RBFA3U3ZC2ATPB.png)

 我们在分析分析il2cpp游戏，最常用的库就是Perfare大佬的Il2CppDumper和Zygisk-Il2CppDumper ， 项目地址如下：

 https://github.com/Perfare/Il2CppDumper

 https://github.com/Perfare/Zygisk-Il2CppDumper

 分别介绍一下1&2 。

 很多游戏如果在没有进行保护的情况，可以直接使用Il2CppDumper

 只需要提供，global-metadata.bat 和原生的libil2cpp.so

 在对游戏的资源文件直接进行解密，就可以快速的得到的游戏的资源文件还有地址。编译过程解释如下：

  ![图片描述](https://bbs.kanxue.com/upload/attach/202304/819934_6Z8FSKPQA65FRY6.png)

 但是大部分的游戏或者说源码，都进行了保护 ，想要直接进行提取 很难 ，我测试了很多个apk都不太行 。

 所以这个时候就用到https://github.com/Perfare/Zygisk-Il2CppDumper

 他是基于Magisk模块对So文件进行注入 ，然后dump 游戏的方法地址和资源信息 。直接改一下包名，即可对游戏进行Dump 。

 但是这个时候我在使用的时候发现，一直找不到il2cpp.so在maps里面 。研究了好久才发现，Apk将So进行了隐藏 。

 主要原理后来深度分析一下 才知道 。**他会先把自己so，也就是il2cpp.so 的内存复制一份 ,然后 unmap 掉，然后在原来的位置mmap同样大的匿名内存，最后复制回去 。这样内存里面就多了一块匿名内存 。**这也是riru里面Hide的办法 。在Zygisk-Il2CppDumper 他的源码如下。他相当于是每次暂停一秒。如果发现了libil2cpp.so以加载，就开始初始化的过程 。就是因为这一秒钟，可能导致So被隐藏 。

| 1234567891011121314151617 | `void hack_start(const char` `*``game_data_dir) {``bool` `load` `=` `false;``for` `(``int` `i` `=` `0``; i <` `10``; i``+``+``) {``void` `*``handle` `=` `xdl_open(``"libil2cpp.so"``,` `0``);``if` `(handle) {``load` `=` `true;``il2cpp_api_init(handle);``il2cpp_dump(game_data_dir);``break``;``}` `else` `{``sleep(``1``);``}``}``if` `(!load) {``LOGI(``"libil2cpp.so not found in thread %d"``, gettid());``}``}` |
|-|-|

这个时候我就想着如果可以在libil2cpp.so刚刚加载到内存里以后直接进行Dump 和初始化 即可 。魔改开始 。

## 实现原理：

项目代码95%以上都来自https://github.com/Perfare/Zygisk-Il2CppDumper ，尊重原创 ！

 Zygisk-Il2CppDumper 里面用的是Magisk进行的注入，之前没开发过复杂的Magisk模块 ，所以我这里注入采用的是Xposed。将我们的SO注入即可 。

 直接在我们so的on_load函数对Linker进行hook，得到加载的回调。代码如下：

| 12345678910111213141516171819202122 | `#define MATCH_ELF "libil2cpp.so"` `class` `FunJniLinkerCallBack : public LinkerLoadCallBack {``public:``void loadBefore(const char` `*``path) const override {` `}` `void loadAfter(const char` `*``path, const char` `*``redirect_path, void` `*``ret) const override {``if` `(path` `=``=` `nullptr) {``return``;``}``if` `(StringUtils::endsWith(path, MATCH_ELF)) {``LOGE(``">>>>>>>>>>>> find libil2cpp.so is load [%s] %s"``,saveFilePath, path)``hack_prepare(path, saveFilePath);``}``}``};``void linkerCallBack::hookLinkerCallBack() {``ZhenxiRunTime::linkerHandler::init();``ZhenxiRunTime::linkerHandler::addLinkerCallBack(new FunJniLinkerCallBack());``}` |
|-|-|

 ZhenxiRunTime::linkerHandler::init();

 是我之前写的hook linker的封装，主要就是hook linker的一些常用dlopen方法。主要参考的开源版本的VA 。

 在上述添加监听的Callback以后在对libil2cpp.so进行监听即可 。这样完美解决So加载回调问题 。在So 刚刚加载到内存里面。

 还没有进行加密的时候，我们快速的对文件进行Dump 。拿到开始地址 。

 剩下的代码和https://github.com/Perfare/Zygisk-Il2CppDumper原始的内容一样 。

| 123456789101112131415161718192021222324252627282930 | `auto assemblies` `=` `il2cpp_domain_get_assemblies(domain, &size);``std::stringstream imageOutput;``for` `(``int` `i` `=` `0``; i < size;` `+``+``i) {``auto image` `=` `il2cpp_assembly_get_image(assemblies[i]);``imageOutput <<` `"// Image "` `<< i <<` `": "` `<< il2cpp_image_get_name(image) <<` `"\n"``;``}``std::vector<std::string> outPuts;``if` `(il2cpp_image_get_class) {``LOGI(``"Version greater than 2018.3"``);``/``/``使用il2cpp_image_get_class``for` `(``int` `i` `=` `0``; i < size;` `+``+``i) {``auto image` `=` `il2cpp_assembly_get_image(assemblies[i]);``std::stringstream imageStr;``imageStr <<` `"\n// Dll : "` `<< il2cpp_image_get_name(image);``auto classCount` `=` `il2cpp_image_get_class_count(image);``for` `(``int` `j` `=` `0``; j < classCount;` `+``+``j) {``auto klass` `=` `il2cpp_image_get_class(image, j);``auto` `type` `=` `il2cpp_class_get_type(const_cast<Il2CppClass` `*``>(klass));``/``/``LOGD(``"type name : %s"``, il2cpp_type_get_name(``type``));``auto outPut` `=` `imageStr.``str``()` `+` `dump_type(``type``);``outPuts.push_back(outPut);``}``}``}` `else` `{``LOGI(``"Version less than 2018.3"``);``/``/``使用反射``auto corlib` `=` `il2cpp_get_corlib();``auto assemblyClass` `=` `il2cpp_class_from_name(corlib,` `"System.Reflection"``,` `"Assembly"``);``auto assemblyLoad` `=` `il2cpp_class_get_method_from_name(assemblyClass,` `"Load"``,` `1``);``....` |
|-|-|

初始化一些常用的il2cpp函数，这些函数都是il2cpp在编译阶段打入到so内部的，好像代码是没有开源的 。

 不过还好，根据方法名都可以知道具体的函数的含义 。部分函数如下 ：

| 1234567891011 | `DO_API(const MethodInfo``*``, il2cpp_class_get_methods, (Il2CppClass` `*` `klass, void``*` `*``iter``));``DO_API(const MethodInfo``*``, il2cpp_class_get_method_from_name, (Il2CppClass` `*` `klass, const char``*` `name,` `int` `argsCount));``DO_API(const char``*``, il2cpp_class_get_name, (Il2CppClass` `*` `klass));``DO_API(void, il2cpp_type_get_name_chunked, (const Il2CppType` `*` `type``, void(``*``chunkReportFunc)(void``*` `data, void``*` `userData), void``*` `userData));``DO_API(const char``*``, il2cpp_class_get_namespace, (Il2CppClass` `*` `klass));``DO_API(Il2CppClass``*``, il2cpp_class_get_parent, (Il2CppClass` `*` `klass));``DO_API(Il2CppClass``*``, il2cpp_class_get_declaring_type, (Il2CppClass` `*` `klass));``DO_API(int32_t, il2cpp_class_instance_size, (Il2CppClass` `*` `klass));``DO_API(size_t, il2cpp_class_num_fields, (const Il2CppClass` `*` `enumKlass));``DO_API(``bool``, il2cpp_class_is_valuetype, (const Il2CppClass` `*` `klass));``...` |
|-|-|

主要实现原理 ，就是先获取当前进程的domain，然后获取domain里面全部的DLL在进行解析 。

 每个DLL里面有很多个Class ,每个Class 里面又存在很多个Method 。依次遍历循环即可 。打印效果如下：

 实现细节不多介绍，详细代码参考

 https://github.com/Perfare/Zygisk-Il2CppDumper

| 123456789101112131415161718192021222324252627282930313233343536373839 | `/``/` `Namespace: System``[Serializable]``public enum GCNotificationStatus``{``/``/` `Fields``public Int32 value__;` `/``/` `0x10``public const GCNotificationStatus Succeeded` `=` `0``;` `/``/` `0x0``public const GCNotificationStatus Failed` `=` `1``;` `/``/` `0x0``public const GCNotificationStatus Canceled` `=` `2``;` `/``/` `0x0``public const GCNotificationStatus Timeout` `=` `3``;` `/``/` `0x0``public const GCNotificationStatus NotApplicable` `=` `4``;` `/``/` `0x0` `/``/` `Properties` `/``/` `Methods``}` `/``/` `Dll : xxx.dll``/``/` `Namespace: System``public static` `class` `GC``{``/``/` `Fields``internal static readonly` `Object` `EPHEMERON_TOMBSTONE;` `/``/` `0x0` `/``/` `Properties``public static Int32 MaxGeneration { get; }` `/``/` `Methods``/``/` `RVA:` `0x2d3c5e4` `VA:` `0x733ad445e4``private static Int32 GetCollectionCount(Int32 generation) { }``/``/` `RVA:` `0x2d3c5e8` `VA:` `0x733ad445e8``private static Int32 GetMaxGeneration() { }``/``/` `RVA:` `0x2d3c5ec` `VA:` `0x733ad445ec``private static Void InternalCollect(Int32 generation) { }``/``/` `RVA:` `0x2d3c5f0` `VA:` `0x733ad445f0``private static Void RecordPressure(Int64 bytesAllocated) { }``/``/` `RVA:` `0x2d3c5f4` `VA:` `0x733ad445f4``internal static Void register_ephemeron_array(Ephemeron[] array) { }``....` |
|-|-|

## IL2CppTracer:

dump下来文件以后 , 我们现在需要做的是去hook对应的逻辑 ，但是Hook完以后才发现 ，有一些函数根本没走 。

 Hook也没效果 ，我们想知道指定时间内 他都调用了哪些函数，比如战斗开始，他都调用了哪些函数 。对局中调用哪些函数 。

 我们现在可以拿到这些方法的的全部地址， 为什么我们不讲将il2cpp全部函数都进行Hook ？直接在hook的callback里面进行栈回溯，获取返回的地址，然后在打印这个返回地址的信息 ，将信息保存到文件里面，就可以得到全部的method 回溯 。

 具体代码如下：先获取全部DLL，在获取Class，最后对每个Method进行Hook 。

 ***<u>经过测试发现并不可行 。</u>***

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115 | `HOOK_DEF(void``*``, HookCallBackNoArgs) {``if` `(!isFinish) {``return` `orig_HookCallBackNoArgs();``}``if` `(ALL_METHOD_LIST` `=``=` `nullptr) {``return` `orig_HookCallBackNoArgs();``}` `void` `*``method_ptr` `=` `(void` `*``) __builtin_return_address(``0``);``for` `(const auto &method:` `*``ALL_METHOD_LIST) {``if` `(method``-``>methodPointer && method_ptr) {``if` `(method``-``>methodPointer` `=``=` `method_ptr) {``const string &methodInfo` `=` `getMethodInfo(method);``if` `(mOs` `=``=` `nullptr) {``mOs` `=` `new std::ofstream(saveDir);``}``LOGE(``"tracer method info %s il2cpp base ->  %p"``, methodInfo.c_str(),``(void` `*``) il2cpp_base)``*``mOs << methodInfo;``return` `orig_HookCallBackNoArgs();``}``}``}``return` `orig_HookCallBackNoArgs();``}` `HOOK_DEF(void``*``, HookCallBack, va_list args) {``if` `(!isFinish) {``return` `orig_HookCallBack(args);``}``if` `(ALL_METHOD_LIST` `=``=` `nullptr) {``return` `orig_HookCallBack(args);``}``void` `*``method_ptr` `=` `(void` `*``) __builtin_return_address(``0``);``for` `(const auto &method:` `*``ALL_METHOD_LIST) {``if` `(method``-``>methodPointer && method_ptr) {``if` `(method``-``>methodPointer` `=``=` `method_ptr) {``const string &methodInfo` `=` `getMethodInfo(method);``if` `(mOs` `=``=` `nullptr) {``mOs` `=` `new std::ofstream(saveDir);``}``LOGE(``"tracer method info %s il2cpp base ->  %p"``, methodInfo.c_str(),``(void` `*``) il2cpp_base)``*``mOs << methodInfo;``return` `orig_HookCallBack(args);``}``}``}``return` `orig_HookCallBack(args);``}` `void il2cpp_tracer(const char` `*``outDir) {``saveDir` `=` `std::string(outDir).append(``"FunIl2cpp_tracer.txt"``);``LOGI(``"il2cpp_tracer tracer... %s"``, saveDir.c_str())``if` `(ALL_METHOD_LIST` `=``=` `nullptr) {``ALL_METHOD_LIST` `=` `new` `list``<const MethodInfo` `*``>;``}``size_t size;``auto domain` `=` `il2cpp_domain_get();``LOGI(``"il2cpp_tracer init domain finish "``)``auto assemblies` `=` `il2cpp_domain_get_assemblies(domain, &size);``LOGI(``"il2cpp_tracer init assemblies finish "``)``if` `(il2cpp_image_get_class) {``LOGI(``"Version greater than 2018.3"``);``for` `(``int` `i` `=` `0``; i < size;` `+``+``i) {``auto image` `=` `il2cpp_assembly_get_image(assemblies[i]);``auto imageName` `=` `il2cpp_image_get_name(image);``auto classCount` `=` `il2cpp_image_get_class_count(image);``for` `(``int` `j` `=` `0``; j < classCount;` `+``+``j) {``auto tempKlass` `=` `il2cpp_image_get_class(image, j);``if` `(tempKlass` `=``=` `nullptr) {``continue``;``}``auto` `type` `=` `il2cpp_class_get_type(const_cast<Il2CppClass` `*``>(tempKlass));``if` `(``type` `=``=` `nullptr) {``continue``;``}``auto` `*``klass` `=` `il2cpp_class_from_type(``type``);``if` `(klass` `=``=` `nullptr) {``continue``;``}``void` `*``iter` `=` `nullptr;``while` `(auto method` `=` `il2cpp_class_get_methods(klass, &``iter``)) {``auto pointer` `=` `method``-``>methodPointer;``if` `(pointer) {``const string &methodInfo` `=` `getMethodInfo(method);``/``/``hook` `all` `method``auto param_count` `=` `il2cpp_method_get_param_count(method);``if` `(param_count >` `0``) {``HookUtils::Hooker((void` `*``) pointer,``(void` `*``) new_HookCallBack,``(void` `*``*``) &orig_HookCallBack``);``}` `else` `{``HookUtils::Hooker((void` `*``) pointer,``(void` `*``) new_HookCallBackNoArgs,``(void` `*``*``) &orig_HookCallBackNoArgs``);``}``ALL_METHOD_LIST``-``>push_back(method);``LOGI(``"hook method success %lu %s "``, ALL_METHOD_LIST``-``>size(),``methodInfo.c_str());` `}``if` `(``iter` `=``=` `nullptr) {``break``;``}``}` `}``}``isFinish` `=` `true;``LOGE(``"lister il2cpp finish method size  %lu  "``, ALL_METHOD_LIST``-``>size())``}``}` |
|-|-|

因为这个一般游戏的方法基本都是几万个或者几十万个，如果进行大量Hook，很容易造成大量崩溃 。

 我这里测试了inline和异常Hook都是在Hook 2W个函数左右，程序闪退，没有具体错误日志 。报错的原因也都是Hook框架分配的匿名内存导致的 。后来放弃这种方案 。

 我继续去他So的符号表去查找，看看是否存在可疑函数。直到发现了一个叫 il2cpp_runtime_invoke 。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202304/819934_2MQGMBBQTKMF6TN.png)

 这个函数当时以为只是invoke才会进行调用，类似Java的invoke 。我Hook了测试一下。发现基本执行都会走这个函数 。回调代码如下：

 获取被调用这个method，获取它的class和dll信息，还有方法信息，都进行保存 。

| 123456789101112131415161718192021222324 | `HOOK_DEF(Il2CppObject``*``, il2cpp_runtime_invoke,``const MethodInfo` `*``method, void` `*``obj,``[[maybe_unused]] void` `*``*``params, Il2CppException` `*``*``exc) {``std::stringstream imageOutput;``auto` `*``clazz` `=` `il2cpp_method_get_class(method);``if` `(clazz !``=` `nullptr) {``auto` `*``image` `=` `il2cpp_class_get_image(clazz);``if` `(image !``=` `nullptr) {``imageOutput <<` `"["` `<< il2cpp_image_get_name(image) <<` `"] "``;``}``imageOutput<<``"["` `<< il2cpp_class_get_name(clazz) <<` `"] "``;``}``const string &methodInfo` `=` `getMethodInfo(method);``imageOutput << methodInfo;``auto pointer` `=` `method``-``>methodPointer;``if` `(pointer) {``imageOutput <<` `" 0x"` `<< ((uint64_t) pointer` `-` `il2cpp_base);``}``imageOutput <<` `"\n"``;``LOGE(``"%s"``, imageOutput.``str``().c_str())``/``/``save` `file``*``mOs << imageOutput.``str``();``return` `orig_il2cpp_runtime_invoke(method, obj, params, exc);``}` |
|-|-|

打印效果如下，大量方法都会进行回溯 ，在游戏里的对局也会有函数调用 ：

| 12345678910111213 | `2023``-``04``-``13` `13``:``49``:``58.773` `3635``-``4153``/``? E``/``Zhenxi: [xxx.dll] [DOTweenComponent] private Void LateUpdate() { }``0x25020200``2023``-``04``-``13` `13``:``49``:``58.773` `3635``-``4153``/``? E``/``Zhenxi: [UnityEngine.InputModule.dll] [NativeInputSystem] internal static Void ShouldRunUpdate(NativeInputUpdateType updateType, out Boolean retval) { }``0x26522584``2023``-``04``-``13` `13``:``49``:``58.773` `3635``-``4153``/``? E``/``Zhenxi: [UnityEngine.InputModule.dll] [NativeInputSystem] internal static Void NotifyBeforeUpdate(NativeInputUpdateType updateType) { }``0x26521468``2023``-``04``-``13` `13``:``49``:``58.773` `3635``-``4153``/``? E``/``Zhenxi: [UnityEngine.InputModule.dll] [NativeInputSystem] internal static Void NotifyUpdate(NativeInputUpdateType updateType, IntPtr eventBuffer) { }``0x26521608``2023``-``04``-``13` `13``:``49``:``58.773` `3635``-``4153``/``? E``/``Zhenxi: [UnityEngine.CoreModule.dll] [Application] internal static Void InvokeOnBeforeRender() { }``0x49698664``2023``-``04``-``13` `13``:``49``:``58.774` `3635``-``4153``/``? E``/``Zhenxi: [UnityEngine.UIModule.dll] [Canvas] private static Void SendPreWillRenderCanvases() { }``0x26404800``...` |
|-|-|

## 2023年4月17日19:26:13

在测试的时候发现il2cpp_runtime_invoke 都是系统api的调用，并不符合预期。后来代码经过修改，采用插装的方式进行Hook ，主要用的是dobby的DobbyInstrument 方法 。核心方法如下 。代码开源。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384 | `std::``list``<std::shared_ptr<ClosureUserData>> &getMethodInfoList() {``static std::``list``<std::shared_ptr<ClosureUserData>> methodInfoList;``return` `methodInfoList;``}``void instrument_callback(void` `*``address, DobbyRegisterContext` `*``reg_ctx) {``for` `(const auto &info: getMethodInfoList()) {``if` `(info``-``>orig_function_pointer` `=``=` `address) {``LOGI(``"Method is called %s"``, getMethodInfo(info``-``>method).c_str())``return``;``}``}``LOGI(``"not find callback method info %p"``, address)``}``bool` `hook_il2cpp_method(const MethodInfo` `*``method) {``void` `*``method_address` `=` `(void` `*``) method``-``>methodPointer;``if` `(method_address` `=``=` `nullptr) {``LOGE(``"Method address is NULL"``);``return` `false;``}` `auto pData` `=` `std::make_shared<ClosureUserData>();``pData``-``>method` `=` `method;``pData``-``>orig_function_pointer` `=` `method_address;` `if` `(HookUtils::addTrampoline(method_address, instrument_callback)) {``getMethodInfoList().push_back(pData);``return` `true;``}` `else` `{``return` `false;``}``}``bool` `ishook(const string& msg){``if``(isTraceALL){``return` `true;``}``return` `std::any_of(filter_list.begin(),``filter_list.end(),``[&msg](const string&` `str``) {``return` `StringUtils::containsInsensitive(msg,` `str``);``});``}``void il2cpp_tracer(const char` `*``outDir) {``HookUtils::startBranchTrampoline();``saveDir` `=` `std::string(outDir).append(``"FunIl2cpp_tracer.txt"``);``LOGI(``"il2cpp_tracer tracer... %s"``, saveDir.c_str())``size_t size;``auto domain` `=` `il2cpp_domain_get();``auto assemblies` `=` `il2cpp_domain_get_assemblies(domain, &size);``if` `(il2cpp_image_get_class) {``hookSize` `=` `0``;``for` `(``int` `i` `=` `0``; i < size;` `+``+``i) {``auto image` `=` `il2cpp_assembly_get_image(assemblies[i]);``auto imageName` `=` `il2cpp_image_get_name(image);``auto classCount` `=` `il2cpp_image_get_class_count(image);``for` `(``int` `j` `=` `0``; j < classCount;` `+``+``j) {``auto tempKlass` `=` `il2cpp_image_get_class(image, j);``auto` `type` `=` `il2cpp_class_get_type(const_cast<Il2CppClass` `*``>(tempKlass));``auto` `*``klass` `=` `il2cpp_class_from_type(``type``);``void` `*``iter` `=` `nullptr;``while` `(auto method` `=` `il2cpp_class_get_methods(klass, &``iter``)) {``auto pointer` `=` `method``-``>methodPointer;``if` `(pointer) {``const string &methodInfo` `=` `getMethodInfo(method);``const char` `*``clazzName` `=` `il2cpp_class_get_name(klass);``auto methodInfoStr` `=` `string(clazzName)` `+` `" "` `+` `methodInfo;``if``(ishook(methodInfoStr)){``if` `(hook_il2cpp_method(method)) {``hookSize``+``+``;``LOGI(``"hook method info success  %s  size-> %zu  %p"``,``methodInfoStr.c_str(), hookSize, ((char` `*``) pointer` `-` `il2cpp_base))``}` `else` `{``LOGE(``"Failed to hook method: %s"``, methodInfoStr.c_str());``}``}``}``if` `(``iter` `=``=` `nullptr) {``break``;``}``}``}``}``LOGE(``"hook finish %zu "``, hookSize)``}``}` |
|-|-|

项目地址：

 https://github.com/w296488320/XposedJniTrace

 和我之前的jnitrace用的同一套代码基，都是xposed注入native ，并且公用一套nativelib 所以都放到一起了 。

 **在此强调 :**

 **项目代码95%以上都来自https://github.com/Perfare/Zygisk-Il2CppDumper ，尊重原创 ！**

上传的附件：
- FunIl2cpp_v1.0.0_2023-04-17_release.apk

（3.40MB，242次下载）

---

# 回复

## 回复 by 0xEA (#2)

*2023-4-13 15:02*

nb

## 回复 by ogli324 (#3)

*2023-4-13 15:03*

点赞

## 回复 by exit\(0\) (#4)

*2023-4-13 15:06*

看不懂 但我大受震撼

## 回复 by 沧澜～ (#5)

*2023-4-13 15:07*

看不懂 但我大受震撼

## 回复 by Papaya. (#6)

*2023-4-13 15:10*

看不懂 但我大受震撼

## 回复 by mudebug (#7)

*2023-4-13 22:53*

大佬666

## 回复 by 秋狝 (#8)

*2023-4-14 09:11*

感谢分享

## 回复 by Lupinus (#9)

*2023-4-14 10:48*

hook so加载相关函数可能会被游戏保护的sdk检测，不hook的话不能第一时间获取到libil2cpp.so的加载；我觉得更好的做法可能还是改rom或者扫游戏的可执行内存获取il2cpp的特征去实现对抗

## 回复 by 阿碧 (#10)

*2023-4-14 11:32*

6666

## 回复 by wx_水山 (#11)

*2023-4-14 12:25*

动手实验了下，业务逻辑的函数不知道为啥，基本都没有打印。

## 回复 by 珍惜Any (#12)

*2023-4-14 13:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_水山](https://bbs.kanxue.com/user-912816.htm)
>
>  动手实验了下，业务逻辑的函数不知道为啥，基本都没有打印。
>
>

可能存在问题，我最近再改改，那个api调用的都是系统的api调用 。等我改完，有好的思路也可以pull

## 回复 by 珍惜Any (#13)

*2023-4-14 13:57*

>
> [Lupinus](https://bbs.kanxue.com/user-754335.htm)
>
>  hook so加载相关函数可能会被游戏保护的sdk检测，不hook的话不能第一时间获取到libil2cpp.so的加载；我觉得更好的做法可能还是改rom或者扫游戏的可执行内存获取il2cpp的特征去实 ...
>
>

这个我测试过的，基本都需要加载到内存里才会进行保护 。我直接hook linker最理想方案，刚刚加载完毕立刻就进行dump

## 回复 by Amun (#14)

*2023-4-14 22:50*

来一个游戏样本？

## 回复 by 冷瞳 (#15)

*2023-4-17 19:35*

666

## 回复 by Papaya. (#16)

*2023-4-18 13:57*

>
> [Amun](https://bbs.kanxue.com/user-850401.htm)
>
>  来一个游戏样本？
>
>

你小子是钓鱼的吧![image](https://bbs.kanxue.com/view/img/face/38.gif)

## 回复 by 万里星河 (#17)

*2023-4-19 17:32*

支持一下

## 回复 by aqingadmin (#18)

*2023-4-30 16:29*

有个游戏用了Zygisk-Il2CppDumper  直接闪退 用了这个apk lsp 找不到这游戏 打勾不了 ![image](https://bbs.kanxue.com/view/img/face/16.gif)

## 回复 by 梦霓裳 (#19)

*2023-4-30 20:32*

大佬 github上的项目不见了 啥情况

## 回复 by 珍惜Any (#20)

*2023-5-4 09:34*

>
> [梦霓裳](https://bbs.kanxue.com/user-971532.htm)
>
>  大佬 github上的项目不见了 啥情况
>
>

造谣的人太多了

## 回复 by 梦霓裳 (#21)

*2023-5-6 01:35*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  造谣的人太多了
>
>

唉，都不给人好好研究吗。大佬还会分享吗？

## 回复 by 744722817 (#22)

*2023-6-7 21:03*

>
> [Amun](https://bbs.kanxue.com/user-850401.htm)
>
>  来一个游戏样本？
>
>

星穹铁道![image](https://bbs.kanxue.com/view/img/face/41.gif)

## 回复 by 744722817 (#23)

*2023-6-7 21:04*

>
> [珍惜Any](https://bbs.kanxue.com/user-819934.htm)
>
>  造谣的人太多了
>
>

啥情况
