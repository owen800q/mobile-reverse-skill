---
title: '[分享]Android  SO文件加载过程探究'
url: https://bbs.kanxue.com/thread-285788.htm
tid: 285788
author: ovo_帮我不c
date: '2025-02-28'
tags: [Android安全, 分享, 基础理论, 逆向分析, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:57:40+08:00'
replies: 76
---

# Android SO文件加载过程探究

在安卓中的app进行so加载过程中，分析一下so的动态静态的so加载过程

在 Android 中，`.so` 文件是 **共享库**文件，`.so` 文件可以分为 **动态链接库**（动态 `.so` 文件）和 **静态链接库**（静态 `.a` 文件），但 Android 中一般更常见的是动态 `.so` 文件，静态链接库通常在编译时被集成到最终的应用中，而不直接加载。所以经常看到的so文件的链接大多是都是以动态链接的

1. 动态链接会利用对应的打包的生成的APK，按照对应的架构（lib/armeabi-v7a/，lib/arm64-v8a/，lib/x86/，lib/x86_64/）去选择对应的**so文件**，然后去实现在 Java 层，通过 **JNI** 来进行。

Java 代码使用 静态`System.loadLibrary("libsofile")` 来加载共享库文件。

| 123 | `static` `{``System.loadLibrary("libsofile);` `// 加载libsofile.so``}` |
|-|-|

或者通过动态加载路径的so文件的过程来实现

| 12 | `String soPath =` `"/data/data/com.example.libsofile/libsofile.so"``;``System.load(soPath);` |
|-|-|
2. 在 Android 中，**静态链接库**（`.a` 文件）是被链接到最终的可执行文件中的，而不是在运行时加载。Android NDK 编译时，静态库会被打包到 APK 中的应用代码部分。

我们要去探究SO文件最真实的加载过程就要从System.load(sopath)这里开始，去剖析安卓源码

[安卓源码](https://cs.android.com/)

## 安卓源码剖析：

System.load(sopath)开始进行解析，查看整个so文件加载过程

### System.load(sopath)

| 1234 | `@CallerSensitive``public` `static` `void` `load(String filename) {``Runtime.getRuntime().load0(Reflection.getCallerClass(), filename);``}` |
|-|-|

先解释一下这里的情况`Reflection.getCallerClass()` 通过反射机制获取调用此方法的类的引用。它返回的是调用 `load0` 方法的 **调用者类**。这里加载到了直接去加载了load0函数。

### load0(Class<?> fromClass, String filename)

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_ST8CRJ25HTES6EG.webp)

| 123456789101112131415161718192021222324 | `//libcore/ojluni/src/main/java/java/lang/Runtime.java``synchronized` `void` `load0(Class<?> fromClass, String filename) {``File file =` `new` `File(filename);``if` `(!(file.isAbsolute())) {``throw` `new` `UnsatisfiedLinkError(``"Expecting an absolute path of the library: "` `+ filename);``}``if` `(filename ==` `null``) {``throw` `new` `NullPointerException(``"filename == null"``);``}``if` `(Flags.readOnlyDynamicCodeLoad()) {``if` `(!file.toPath().getFileSystem().isReadOnly() && file.canWrite()) {``if` `(VMRuntime.getSdkVersion() >= VersionCodes.VANILLA_ICE_CREAM) {``System.logW(``"Attempt to load writable file: "` `+ filename``+` `". This will throw on a future Android version"``);``}``}``}` `String error = nativeLoad(filename, fromClass.getClassLoader(), fromClass);``if` `(error !=` `null``) {``throw` `new` `UnsatisfiedLinkError(error);``}``}` |
|-|-|

在这里去检测了对应加载过程中的sofile。然后就开始往nativeLoad函数走了

### nativeLoad(filename, fromClass.getClassLoader(), fromClass);

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_M85P83X2FXEW4R9.webp)

这里直接是naitve函数了，我们要去看对应的c文件，所以要重新去搜索了，这里的搜索方法就是类名_函数名的形式，转换过程就是**Runtime_nativeLoad**函数

### Runtime_nativeLoad

| 123456 | `JNIEXPORT jstring JNICALL``Runtime_nativeLoad(JNIEnv* env, jclass ignored, jstring javaFilename,``jobject javaLoader, jclass caller)``{``return` `JVM_NativeLoad(env, javaFilename, javaLoader, caller);``}` |
|-|-|

这里是最正常的返回，直接走 JVM_NativeLoad(env, javaFilename, javaLoader, caller)

### JVM_NativeLoad(env, javaFilename, javaLoader, caller)

| 1234567891011121314151617181920212223242526 | `JNIEXPORT jstring JVM_NativeLoad(JNIEnv* env,``jstring javaFilename,``jobject javaLoader,``jclass caller) {``ScopedUtfChars filename(env, javaFilename);``if` `(filename.c_str() == nullptr) {``return` `nullptr;``}` `std::string error_msg;``{``art::JavaVMExt* vm = art::Runtime::Current()->GetJavaVM();``bool` `success = vm->LoadNativeLibrary(env,``filename.c_str(),``javaLoader,``caller,``&error_msg);``if` `(success) {``return` `nullptr;``}``}` `// Don't let a pending exception from JNI_OnLoad cause a CheckJNI issue with NewStringUTF.``env->ExceptionClear();``return` `env->NewStringUTF(error_msg.c_str());``}` |
|-|-|

同样得直接向下去分析就好了 **vm->LoadNativeLibrary**函数

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_BE9AP8TA47G72BW.webp)

### vm->LoadNativeLibrary(env, filename.c_str(),javaLoader,caller,&error_msg);

这里的大多数的函数都是对于so加载中的中途函数，也就是一层一层得调用到关键函数的，所以这里直接往下走就是了

在 JavaVMExt:**:LoadNativeLibrary**这个函数中有需要去注意和理解的地方，同时这里也是在进行调用dlopen来进行真正so文件加载的地方。

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_WBUAHH8ZF9J7HD8.webp)

| 123456789101112 | `ClassLinker* class_linker = Runtime::Current()->GetClassLinker();``if` `(class_linker->IsBootClassLoader(loader)) {``loader = nullptr;``class_loader = nullptr;``}``if` `(caller_class != nullptr) {``ObjPtr<mirror::Class> caller = soa.Decode<mirror::Class>(caller_class);``ObjPtr<mirror::DexCache> dex_cache = caller->GetDexCache();``if` `(dex_cache != nullptr) {``caller_location = dex_cache->GetLocation()->ToModifiedUtf8();``}``}` |
|-|-|

首先是这里的Linker的位置，这里去解码了 ClassLoader 和 Caller Class 信息，同时去判断了加载器是否为 `BootClassLoader`。其实在so加载过程也有借助linker判断so文件结构，链接的位置则是so文件的头部，判断的是so文件结构是否正确。
 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_TYUEZGXFMSDX36C.webp)

这里也去判断了这里加载的so文件是否以及被加载过了，最后开始的对于共享库so的加载（dlopen）
 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_DJQDYUMUTF8SKNW.webp)

| 1234567891011121314151617181920 | `Locks::mutator_lock_->AssertNotHeld(self);``const` `char``* path_str = path.empty() ? nullptr : path.c_str();``bool` `needs_native_bridge =` `false``;``char``* nativeloader_error_msg = nullptr;``void``* handle = android::OpenNativeLibrary(``env,``runtime_->GetTargetSdkVersion(),``path_str,``class_loader,``(caller_location.empty() ? nullptr : caller_location.c_str()),``library_path.get(),``&needs_native_bridge,``&nativeloader_error_msg);``VLOG(jni) <<` `"[Call to dlopen(\""` `<< path <<` `"\", RTLD_NOW) returned "` `<< handle <<` `"]"``;` `if` `(handle == nullptr) {``*error_msg = nativeloader_error_msg;``android::NativeLoaderFreeErrorMessage(nativeloader_error_msg);``VLOG(jni) <<` `"dlopen(\""` `<< path <<` `"\", RTLD_NOW) failed: "` `<< *error_msg;``return` `false``;` |
|-|-|

### OpenNativeLibrary

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_DDBX9AYSE6BK8YC.webp)

在这里开始找到了我们最为熟悉的 **android_dlopen_ext**(path, RTLD_NOW, &dlextinfo);函数，也就是经常进行HOOK的位置了

| 1234567891011121314151617181920212223242526272829303132333435 | `//art/libnativeloader/native_loader.cpp``void``* OpenNativeLibrary(JNIEnv* env,``int32_t target_sdk_version,``const` `char``* path,``jobject class_loader,``const` `char``* caller_location,``jstring library_path_j,``bool``* needs_native_bridge,``char``** error_msg) {``#if defined(ART_TARGET_ANDROID)``if` `(class_loader == nullptr) {``// class_loader is null only for the boot class loader (see``// IsBootClassLoader call in JavaVMExt::LoadNativeLibrary), i.e. the caller``// is in the boot classpath.``*needs_native_bridge =` `false``;``if` `(caller_location != nullptr) {``std::optional<NativeLoaderNamespace> ns = FindApexNamespace(caller_location);``if` `(ns.has_value()) {``const` `android_dlextinfo dlextinfo = {``.flags = ANDROID_DLEXT_USE_NAMESPACE,``.library_namespace = ns.value().ToRawAndroidNamespace(),``};``void``* handle = android_dlopen_ext(path, RTLD_NOW, &dlextinfo);``char``* dlerror_msg = handle == nullptr ? strdup(dlerror()) : nullptr;``ALOGD(``"Load %s using APEX ns %s for caller %s: %s"``,``path,``ns.value().name().c_str(),``caller_location,``dlerror_msg == nullptr ?` `"ok"` `: dlerror_msg);``if` `(dlerror_msg != nullptr) {``*error_msg = dlerror_msg;``}``return` `handle;``}``}` |
|-|-|

在android12中会直接由 android_dlopen_ext直接返回到 **__loader_android_dlopen_ext**函数，而在其他版本可以会到 **mock->mock_dlopen_ext**（这里会走到`mock_dlopen_ext` 会模拟 `dlopen` 的行为，同时通过flag和宏定义走到不同的函数位置）

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_JP7XZJZ4GGZ2TRJ.webp)

这里我们固定在android12的位置去实现。

### __loader_android_dlopen_ext

| 123456 | `void``* __loader_android_dlopen_ext(``const` `char``* filename,``int` `flags,``const` `android_dlextinfo* extinfo,``const` `void``* caller_addr) {``return` `dlopen_ext(filename, flags, extinfo, caller_addr);``}` |
|-|-|

直接的返回进入下一个函数。

### dlopen_ext

| 1234567891011121314 | `//bionic/linker/dlfcn.cpp``static` `void``* dlopen_ext(``const` `char``* filename,``int` `flags,``const` `android_dlextinfo* extinfo,``const` `void``* caller_addr) {``ScopedPthreadMutexLocker locker(&g_dl_mutex);``g_linker_logger.ResetState();``void``* result = do_dlopen(filename, flags, extinfo, caller_addr);``if` `(result == nullptr) {``__bionic_format_dlerror(``"dlopen failed"``, linker_get_error_buffer());``return` `nullptr;``}``return` `result;``}` |
|-|-|

同样进入do_dlopen(filename, flags, extinfo, caller_addr)

### do_dlopen(filename, flags, extinfo, caller_addr)

在这个函数中附加了很多对于do_dlopen函数参数的检测和判断

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_VDXEV7UQRQU77QC.webp)

这种大面积的对于extinfo，对于so文件相关的属性进行的检测。

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_BAXW7CDKFXMDFW9.webp)

通过还对于这里的path进行了对应路径的转换和翻译。

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_9T2DAZFHS26X9BB.webp)

| 123 | `ProtectedDataGuard guard;``soinfo* si = find_library(ns, translated_name, flags, extinfo, caller);``loading_trace.End();` |
|-|-|

这里是对于do_dlopen最为重要的位置，也就是在这里去实现了对于soinfo的初始化，也就是在这开始调用so的.init_proc函数，接着调用.init_array中的函数，最后才是JNI_OnLoad函数。在很多的so文件的检测点判断中很多人也会利用这里的位置对于检测点是在JNI_OnLoad函数之前还是之后的判断依据。

**继续去往find_library(ns, translated_name, flags, extinfo, caller)**

### find_library(ns, translated_name, flags, extinfo, caller)

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_QDS5K896NZQC6TX.webp)

| 12345678910111213141516171819202122232425262728 | `static` `soinfo* find_library(android_namespace_t* ns,``const` `char``* name,` `int` `rtld_flags,``const` `android_dlextinfo* extinfo,``soinfo* needed_by) {``soinfo* si = nullptr;` `if` `(name == nullptr) {``si = solist_get_somain();``}` `else` `if` `(!find_libraries(ns,``needed_by,``&name,``1,``&si,``nullptr,``0,``rtld_flags,``extinfo,``false` `/* add_as_children */``)) {``if` `(si != nullptr) {``soinfo_unload(si);``}``return` `nullptr;``}` `si->increment_ref_count();` `return` `si;``}` |
|-|-|

这里直接往find_libraries里面就可以了

### find_libraries

这个函数就是在so文件加载执行流程的最后了

 ![image](https://bbs.kanxue.com/upload/attach/202502/971248_WGPFMSV5TZNEMS5.webp)

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308 | `bool` `find_libraries(android_namespace_t* ns,``soinfo* start_with,``const` `char``*` `const` `library_names[],``size_t` `library_names_count,``soinfo* soinfos[],``std::vector<soinfo*>* ld_preloads,``size_t` `ld_preloads_count,``int` `rtld_flags,``const` `android_dlextinfo* extinfo,``bool` `add_as_children,``std::vector<android_namespace_t*>* namespaces) {``// Step 0: prepare.``std::unordered_map<``const` `soinfo*, ElfReader> readers_map;``LoadTaskList load_tasks;` `for` `(``size_t` `i = 0; i < library_names_count; ++i) {``const` `char``* name = library_names[i];``load_tasks.push_back(LoadTask::create(name, start_with, ns, &readers_map));``}` `// If soinfos array is null allocate one on stack.``// The array is needed in case of failure; for example``// when library_names[] = {libone.so, libtwo.so} and libone.so``// is loaded correctly but libtwo.so failed for some reason.``// In this case libone.so should be unloaded on return.``// See also implementation of failure_guard below.` `if` `(soinfos == nullptr) {``size_t` `soinfos_size =` `sizeof``(soinfo*)*library_names_count;``soinfos =` `reinterpret_cast``<soinfo**>(alloca(soinfos_size));``memset``(soinfos, 0, soinfos_size);``}` `// list of libraries to link - see step 2.``size_t` `soinfos_count = 0;` `auto` `scope_guard = android::base::make_scope_guard([&]() {``for` `(LoadTask* t : load_tasks) {``LoadTask::deleter(t);``}``});` `ZipArchiveCache zip_archive_cache;``soinfo_list_t new_global_group_members;` `// Step 1: expand the list of load_tasks to include``// all DT_NEEDED libraries (do not load them just yet)``for` `(``size_t` `i = 0; i<load_tasks.size(); ++i) {``LoadTask* task = load_tasks[i];``soinfo* needed_by = task->get_needed_by();` `bool` `is_dt_needed = needed_by != nullptr && (needed_by != start_with \|\| add_as_children);``task->set_extinfo(is_dt_needed ? nullptr : extinfo);``task->set_dt_needed(is_dt_needed);` `// Note: start from the namespace that is stored in the LoadTask. This namespace``// is different from the current namespace when the LoadTask is for a transitive``// dependency and the lib that created the LoadTask is not found in the``// current namespace but in one of the linked namespaces.``android_namespace_t* start_ns =` `const_cast``<android_namespace_t*>(task->get_start_from());` `LD_LOG(kLogDlopen,` `"find_library_internal(ns=%s@%p): task=%s, is_dt_needed=%d"``,``start_ns->get_name(), start_ns, task->get_name(), is_dt_needed);` `if` `(!find_library_internal(start_ns, task, &zip_archive_cache, &load_tasks, rtld_flags)) {``return` `false``;``}` `soinfo* si = task->get_soinfo();` `if` `(is_dt_needed) {``needed_by->add_child(si);``}` `// When ld_preloads is not null, the first``// ld_preloads_count libs are in fact ld_preloads.``bool` `is_ld_preload =` `false``;``if` `(ld_preloads != nullptr && soinfos_count < ld_preloads_count) {``ld_preloads->push_back(si);``is_ld_preload =` `true``;``}` `if` `(soinfos_count < library_names_count) {``soinfos[soinfos_count++] = si;``}` `// Add the new global group members to all initial namespaces. Do this secondary namespace setup``// at the same time that libraries are added to their primary namespace so that the order of``// global group members is the same in the every namespace. Only add a library to a namespace``// once, even if it appears multiple times in the dependency graph.``if` `(is_ld_preload \|\| (si->get_dt_flags_1() & DF_1_GLOBAL) != 0) {``if` `(!si->is_linked() && namespaces != nullptr && !new_global_group_members.contains(si)) {``new_global_group_members.push_back(si);``for` `(``auto` `linked_ns : *namespaces) {``if` `(si->get_primary_namespace() != linked_ns) {``linked_ns->add_soinfo(si);``si->add_secondary_namespace(linked_ns);``}``}``}``}``}` `// Step 2: Load libraries in random order (see b/24047022)``LoadTaskList load_list;``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``auto` `pred = [&](``const` `LoadTask* t) {``return` `t->get_soinfo() == si;``};` `if` `(!si->is_linked() &&``std::find_if(load_list.begin(), load_list.end(), pred) == load_list.end() ) {``load_list.push_back(task);``}``}``bool` `reserved_address_recursive =` `false``;``if` `(extinfo) {``reserved_address_recursive = extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS_RECURSIVE;``}``if` `(!reserved_address_recursive) {``// Shuffle the load order in the normal case, but not if we are loading all``// the libraries to a reserved address range.``shuffle(&load_list);``}` `// Set up address space parameters.``address_space_params extinfo_params, default_params;``size_t` `relro_fd_offset = 0;``if` `(extinfo) {``if` `(extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS) {``extinfo_params.start_addr = extinfo->reserved_addr;``extinfo_params.reserved_size = extinfo->reserved_size;``extinfo_params.must_use_address =` `true``;``}` `else` `if` `(extinfo->flags & ANDROID_DLEXT_RESERVED_ADDRESS_HINT) {``extinfo_params.start_addr = extinfo->reserved_addr;``extinfo_params.reserved_size = extinfo->reserved_size;``}``}` `for` `(``auto``&& task : load_list) {``address_space_params* address_space =``(reserved_address_recursive \|\| !task->is_dt_needed()) ? &extinfo_params : &default_params;``if` `(!task->load(address_space)) {``return` `false``;``}``}` `// The WebView loader uses RELRO sharing in order to promote page sharing of the large RELRO``// segment, as it's full of C++ vtables. Because MTE globals, by default, applies random tags to``// each global variable, the RELRO segment is polluted and unique for each process. In order to``// allow sharing, but still provide some protection, we use deterministic global tagging schemes``// for DSOs that are loaded through android_dlopen_ext, such as those loaded by WebView.``bool` `dlext_use_relro =``extinfo && extinfo->flags & (ANDROID_DLEXT_WRITE_RELRO \| ANDROID_DLEXT_USE_RELRO);` `// Step 3: pre-link all DT_NEEDED libraries in breadth first order.``bool` `any_memtag_stack =` `false``;``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``if` `(!si->is_linked() && !si->prelink_image(dlext_use_relro)) {``return` `false``;``}``// si->memtag_stack() needs to be called after si->prelink_image() which populates``// the dynamic section.``if` `(si->memtag_stack()) {``any_memtag_stack =` `true``;``LD_LOG(kLogDlopen,``"... load_library requesting stack MTE for: realpath=\"%s\", soname=\"%s\""``,``si->get_realpath(), si->get_soname());``}``register_soinfo_tls(si);``}``if` `(any_memtag_stack) {``if` `(``auto``* cb = __libc_shared_globals()->memtag_stack_dlopen_callback) {``cb();``}` `else` `{``// find_library is used by the initial linking step, so we communicate that we``// want memtag_stack enabled to __libc_init_mte.``__libc_shared_globals()->initial_memtag_stack_abi =` `true``;``}``}` `// Step 4: Construct the global group. DF_1_GLOBAL bit is force set for LD_PRELOADed libs because``// they must be added to the global group. Note: The DF_1_GLOBAL bit for a library is normally set``// in step 3.``if` `(ld_preloads != nullptr) {``for` `(``auto``&& si : *ld_preloads) {``si->set_dt_flags_1(si->get_dt_flags_1() \| DF_1_GLOBAL);``}``}` `// Step 5: Collect roots of local_groups.``// Whenever needed_by->si link crosses a namespace boundary it forms its own local_group.``// Here we collect new roots to link them separately later on. Note that we need to avoid``// collecting duplicates. Also the order is important. They need to be linked in the same``// BFS order we link individual libraries.``std::vector<soinfo*> local_group_roots;``if` `(start_with != nullptr && add_as_children) {``local_group_roots.push_back(start_with);``}` `else` `{``CHECK(soinfos_count == 1);``local_group_roots.push_back(soinfos[0]);``}` `for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``soinfo* needed_by = task->get_needed_by();``bool` `is_dt_needed = needed_by != nullptr && (needed_by != start_with \|\| add_as_children);``android_namespace_t* needed_by_ns =``is_dt_needed ? needed_by->get_primary_namespace() : ns;` `if` `(!si->is_linked() && si->get_primary_namespace() != needed_by_ns) {``auto` `it = std::find(local_group_roots.begin(), local_group_roots.end(), si);``LD_LOG(kLogDlopen,``"Crossing namespace boundary (si=%s@%p, si_ns=%s@%p, needed_by=%s@%p, ns=%s@%p, needed_by_ns=%s@%p) adding to local_group_roots: %s"``,``si->get_realpath(),``si,``si->get_primary_namespace()->get_name(),``si->get_primary_namespace(),``needed_by == nullptr ?` `"(nullptr)"` `: needed_by->get_realpath(),``needed_by,``ns->get_name(),``ns,``needed_by_ns->get_name(),``needed_by_ns,``it == local_group_roots.end() ?` `"yes"` `:` `"no"``);` `if` `(it == local_group_roots.end()) {``local_group_roots.push_back(si);``}``}``}` `// Step 6: Link all local groups``for` `(``auto` `root : local_group_roots) {``soinfo_list_t local_group;``android_namespace_t* local_group_ns = root->get_primary_namespace();` `walk_dependencies_tree(root,``[&] (soinfo* si) {``if` `(local_group_ns->is_accessible(si)) {``local_group.push_back(si);``return` `kWalkContinue;``}` `else` `{``return` `kWalkSkip;``}``});` `soinfo_list_t global_group = local_group_ns->get_global_group();``SymbolLookupList lookup_list(global_group, local_group);``soinfo* local_group_root = local_group.front();` `bool` `linked = local_group.visit([&](soinfo* si) {``// Even though local group may contain accessible soinfos from other namespaces``// we should avoid linking them (because if they are not linked -> they``// are in the local_group_roots and will be linked later).``if` `(!si->is_linked() && si->get_primary_namespace() == local_group_ns) {``const` `android_dlextinfo* link_extinfo = nullptr;``if` `(si == soinfos[0] \|\| reserved_address_recursive) {``// Only forward extinfo for the first library unless the recursive``// flag is set.``link_extinfo = extinfo;``}``if` `(__libc_shared_globals()->load_hook) {``__libc_shared_globals()->load_hook(si->load_bias, si->phdr, si->phnum);``}``lookup_list.set_dt_symbolic_lib(si->has_DT_SYMBOLIC ? si : nullptr);``if` `(!si->link_image(lookup_list, local_group_root, link_extinfo, &relro_fd_offset) \|\|``!get_cfi_shadow()->AfterLoad(si, solist_get_head())) {``return` `false``;``}``}` `return` `true``;``});` `if` `(!linked) {``return` `false``;``}``}` `// Step 7: Mark all load_tasks as linked and increment refcounts``// for references between load_groups (at this point it does not matter if``// referenced load_groups were loaded by previous dlopen or as part of this``// one on step 6)``if` `(start_with != nullptr && add_as_children) {``start_with->set_linked();``}` `for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``si->set_linked();``}` `for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``soinfo* needed_by = task->get_needed_by();``if` `(needed_by != nullptr &&``needed_by != start_with &&``needed_by->get_local_group_root() != si->get_local_group_root()) {``si->increment_ref_count();``}``}`  `return` `true``;``}` |
|-|-|

这里很长一部分的代码，在安卓源码中也有对于其进行了批注，一步一步得去加载和解析so文件，去实现so文件的加载

#### Step 0准备加载任务

比如在Step 0 中

| 1234567891011121314151617 | `for` `(``size_t` `i = 0; i < library_names_count; ++i) {``const` `char``* name = library_names[i];``load_tasks.push_back(LoadTask::create(name, start_with, ns, &readers_map));``}` `// If soinfos array is null allocate one on stack.``// The array is needed in case of failure; for example``// when library_names[] = {libone.so, libtwo.so} and libone.so``// is loaded correctly but libtwo.so failed for some reason.``// In this case libone.so should be unloaded on return.``// See also implementation of failure_guard below.` `if` `(soinfos == nullptr) {``size_t` `soinfos_size =` `sizeof``(soinfo*)*library_names_count;``soinfos =` `reinterpret_cast``<soinfo**>(alloca(soinfos_size));``memset``(soinfos, 0, soinfos_size);``}` |
|-|-|

程序去实现了对于这个加载的so文件进行的，存储于数组中，并且去实现了条件判断，假如soinfos为空，还会去实现构造了soinfo* 的结构体指针来申请一段空间来存储

#### Step 1解析依赖

| 1234567891011121314151617181920212223242526 | `for` `(``size_t` `i = 0; i<load_tasks.size(); ++i) {``LoadTask* task = load_tasks[i];``soinfo* needed_by = task->get_needed_by();` `bool` `is_dt_needed = needed_by != nullptr && (needed_by != start_with \|\| add_as_children);``task->set_extinfo(is_dt_needed ? nullptr : extinfo);``task->set_dt_needed(is_dt_needed);` `// Note: start from the namespace that is stored in the LoadTask. This namespace``// is different from the current namespace when the LoadTask is for a transitive``// dependency and the lib that created the LoadTask is not found in the``// current namespace but in one of the linked namespaces.``android_namespace_t* start_ns =` `const_cast``<android_namespace_t*>(task->get_start_from());` `LD_LOG(kLogDlopen,` `"find_library_internal(ns=%s@%p): task=%s, is_dt_needed=%d"``,``start_ns->get_name(), start_ns, task->get_name(), is_dt_needed);` `if` `(!find_library_internal(start_ns, task, &zip_archive_cache, &load_tasks, rtld_flags)) {``return` `false``;``}` `soinfo* si = task->get_soinfo();` `if` `(is_dt_needed) {``needed_by->add_child(si);``}` |
|-|-|

这里 task->get_needed_by() 能够看到其实是在借用上一步得到的so文件的数组去实现检测依赖关系，因为我们知道一个so文件，在ida分析中可以看到的导入表和导出表，全是so与so之间的相互依赖来实现的。通过学习过NDK开发的也知道，在so之间的相互调用中，通过也是通过dlopen来实现。

##### so文件之间的调用：

| 1234567891011121314151617181920212223242526272829303132 | `extern` `"C"` `JNIEXPORT jstring JNICALL``Java_com_chen_javaandso_MainActivity_stringFromJNI(``JNIEnv* env,``jobject` `/* this */``,``jstring path) {``std::string hello =` `"Hello from C++"``;``const` `char``* cpath = env->GetStringUTFChars(path, nullptr);``//这里是java转c++的转char函数``if` `(cpath == nullptr) {``// 处理 JNIEnv::GetStringUTFChars 返回 nullptr 的情况``return` `nullptr;``}``void``* soinfo = dlopen(cpath, RTLD_NOW);``//这里去获取对应路径下的so文件的句柄``if` `(soinfo == nullptr) {``// 处理 dlopen 失败的情况``__android_log_print(ANDROID_LOG_ERROR,` `"JNI"``,` `"Failed to load library: %s"``, dlerror());``env->ReleaseStringUTFChars(path, cpath);``return` `nullptr;``}``//由于我们是通过的对应路径去查找的so文件的函数名，所以这里创建了一个函数指针去得到对应的函数句柄，然后直接调用``void` `(*def)(``char``*) =` `reinterpret_cast``<``void` `(*)(``char``*)>(dlsym(soinfo,` `"_Z7seconedv"``));``//直接去利用句柄去实现查找对应的函数，这里的函数名由于没有加上extern "C"，所以会在执行过程中改变``if` `(def == nullptr) {``// 处理 dlsym 找不到符号的情况``__android_log_print(ANDROID_LOG_ERROR,` `"JNI"``,` `"Failed to find symbol: %s"``, dlerror());``dlclose(soinfo);``env->ReleaseStringUTFChars(path, cpath);``return` `nullptr;``}``def(nullptr);``dlclose(soinfo);` `// 关闭动态库句柄``env->ReleaseStringUTFChars(path, cpath);` `// 释放 JNI 字符串``return` `env->NewStringUTF(hello.c_str());``}` |
|-|-|

#### Step 2 随机顺序

Step2 中，安卓动态链接器采用 **随机顺序** 加载 SO 文件（避免固定顺序带来的漏洞）。如果 `extinfo` 需要 `ANDROID_DLEXT_RESERVED_ADDRESS_RECURSIVE`，则不会进行随机化。设定地址空间参数，比如 `reserved_addr`（预留地址）和 `reserved_size`。

#### Step3 预链接

| 12345678910111213141516 | `bool` `any_memtag_stack =` `false``;``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``if` `(!si->is_linked() && !si->prelink_image(dlext_use_relro)) {``return` `false``;``}``// si->memtag_stack() needs to be called after si->prelink_image() which populates``// the dynamic section.``if` `(si->memtag_stack()) {``any_memtag_stack =` `true``;``LD_LOG(kLogDlopen,``"... load_library requesting stack MTE for: realpath=\"%s\", soname=\"%s\""``,``si->get_realpath(), si->get_soname());``}``register_soinfo_tls(si);``}` |
|-|-|

这里是实现预链接的位置，也是在文章之前提到实现Linker来解析ELF文件结构的地方**si>prelink_image(dlext_use_relro))**

| 1234 | `1.``检查 ELF 头的合法性，确定是有效的 ELF 文件。``2.``读取动态段，提取符号表、字符串表等信息。``3.``初始化 .got.plt 和 .rel.dyn 等重定位表，用于后续符号解析。``4.``解析 DT_NEEDED（依赖的库），准备后续的 link_image() 进行符号解析。` |
|-|-|

这也是对于ELF文件结构处理的细节位置，只有对应的so文件是完整的才能进行加载链接

| 1 | `register_soinfo_tls(si);` |
|-|-|

同时也将soinfo转入到了TLS中去。

#### Step 4 处理全局符号解析

这里去实现把在Step3中解析的符号表等等的信息来进行处理了`DF_1_GLOBAL` 标志的库会被添加到全局符号解析列表。如果是 `LD_PRELOAD` 方式加载的库，强制 `DF_1_GLOBAL` 以确保它能影响所有加载的库。

#### Step5 --- Step7

从Step5到Step7之间的这些处理就很细节了，比如有对于so文件的跨越了匿名空间的特殊处理，以及对于之前的so文件之间的依赖库的递归处理，来实现依赖so之间的函数使用。总的来说全是遍历**load_tasks**，之前准备的so文件，来实现的各种属性和信息的处理。

就此，整个SO文件被全部解析处理。

# 总结

这里我们去重新梳理一下整个so文件加载过程，现在不管是frida检测，还是更多的防护都在so文件里面，这在APP防护和加固很重要，同样破防也是。

我们首先是通过`System.load()`进入

| 1234 | `@CallerSensitive``public` `static` `void` `load(String filename) {``Runtime.getRuntime().load0(Reflection.getCallerClass(), filename);``}` |
|-|-|

此方法最终调用 `Runtime.load0()`，然后进入 `nativeLoad()` 函数。

`Runtime_nativeLoad` → `vm->LoadNativeLibrary`

进入 `JavaVMExt::LoadNativeLibrary` 方法后，最终会调用 `dlopen` 进行真正的 SO 文件加载。

| 1 | `vm->LoadNativeLibrary(env, filename.c_str(), javaLoader, caller, &error_msg);` |
|-|-|

在 Android 12 及以上版本，会调用 `android_dlopen_ext` 返回 `__loader_android_dlopen_ext`。

| 123456 | `void``* __loader_android_dlopen_ext(``const` `char``* filename,``int` `flags,``const` `android_dlextinfo* extinfo,``const` `void``* caller_addr) {``return` `dlopen_ext(filename, flags, extinfo, caller_addr);``}` |
|-|-|

该方法最终调用 `dlopen_ext()`。

| 12345678 | `static` `void``* dlopen_ext(``const` `char``* filename,``int` `flags,``const` `android_dlextinfo* extinfo,``const` `void``* caller_addr) {``ScopedPthreadMutexLocker locker(&g_dl_mutex);``void``* result = do_dlopen(filename, flags, extinfo, caller_addr);``return` `result;``}` |
|-|-|

`do_dlopen(filename, flags, extinfo, caller_addr)`

在 `do_dlopen()` 中，会调用 `find_library()` 进行 SO 文件的真正加载。

| 1 | `soinfo* si = find_library(ns, translated_name, flags, extinfo, caller);` |
|-|-|

这里是对于soinfo的赋值，同时在这里开始调用so的.init_proc函数，接着调用.init_array中的函数，最后才是JNI_OnLoad函数。最后到达**find_libraries** 执行最后的处理。

这里附上评论区中的执行流程图包括了在模拟器下的执行流程。
我在https://bbs.kanxue.com/thread-286377.htm，这里对于模拟器下so文件执行流程做了分析。
 ![image](https://bbs.kanxue.com/upload/attach/202504/971248_UD9D7YQUXUCCFTM.webp)

# 参考文章：

[Android系统加载so的源码分析 — 博客](https://gttiankai.github.io/2018/01/03/android%E7%B3%BB%E7%BB%9F%E5%8A%A0%E8%BD%BDso%E7%9A%84%E6%BA%90%E7%A0%81%E5%88%86%E6%9E%90/)

[安卓so加载流程源码分析 | oacia = oaciaのBbBlog~ = DEVIL or SWEET](https://oacia.dev/android-load-so/)

[Android Linker学习笔记 | WooYun知识库](http://drops.xmd5.com/static/drops/tips-12122.html)

---

# 回复

## 回复 by 逆天而行 (#2)

*2025-3-1 10:52*

蛮不错的 ！

## 回复 by jdong (#3)

*2025-3-3 14:03*

蛮不错的 ！

## 回复 by LQ6H (#4)

*2025-3-3 16:26*

666

## 回复 by iBa0 (#5)

*2025-3-3 17:04*

![image](https://bbs.kanxue.com/view/img/face/057.gif)

## 回复 by Eureka777 (#6)

*2025-3-3 18:39*

6666

## 回复 by diasstudy (#7)

*2025-3-3 22:03*

6666

## 回复 by Ankeys (#8)

*2025-3-4 10:31*

6666

## 回复 by 4Chan (#9)

*2025-3-5 13:57*

666

## 回复 by mb_shzsxtje (#10)

*2025-3-6 10:00*

感谢分享

## 回复 by wx_宇克鴻 (#11)

*2025-3-6 11:17*

666

## 回复 by HappyKL (#12)

*2025-3-7 18:17*

6666

## 回复 by 川美 (#13)

*2025-3-8 16:47*

666

## 回复 by GEKEZYX (#14)

*2025-3-8 19:13*

666

## 回复 by mb_jyabstvr (#15)

*2025-3-9 16:52*

6

## 回复 by hanjiefang (#16)

*2025-3-12 14:47*

好文章

## 回复 by mb_hziqyrum (#17)

*2025-3-13 10:47*

看看再说

## 回复 by dandan11 (#18)

*2025-3-13 11:32*

66

## 回复 by 笑对VS人生 (#19)

*2025-3-13 12:28*

能否动态定义System.loadLibrary("libsofile") 对应默认目录为自定义私有目录

## 回复 by XCCCC (#20)

*2025-3-13 17:15*

6

## 回复 by mb_kgfqphsx (#21)

*2025-3-14 08:56*

666

## 回复 by CIH_D39 (#22)

*2025-3-14 13:40*

66

## 回复 by bonder (#23)

*2025-3-16 15:17*

66

## 回复 by 黑色黎明 (#24)

*2025-3-17 08:34*

不错

## 回复 by mb_ushkloej (#25)

*2025-3-17 11:03*

666

## 回复 by flyingx (#26)

*2025-3-17 19:21*

66

## 回复 by 蜡笔晓辉 (#27)

*2025-3-18 07:41*

888

## 回复 by FIGHTING安 (#28)

*2025-3-18 09:28*

看看

## 回复 by 英俊 (#29)

*2025-3-18 15:39*

study

## 回复 by FindTea (#30)

*2025-3-18 16:28*

666

## 回复 by 爱喝矿泉水 (#31)

*2025-3-18 21:27*

666

## 回复 by lijjianyu (#32)

*2025-3-18 23:45*

666

## 回复 by mb_vcadfsvs (#33)

*2025-3-20 16:41*

666

## 回复 by mb_eaxrskgf (#34)

*2025-3-21 11:22*

6666

## 回复 by POST熟悉中 (#35)

*2025-3-22 02:25*

感谢分享知识![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_jxiwhkvq (#36)

*2025-3-22 10:40*

666

## 回复 by 雪风完美 (#37)

*2025-3-25 10:41*

666666

## 回复 by cced001 (#38)

*2025-4-1 09:36*

了解一下，挺不错的

## 回复 by 睡大街 (#39)

*2025-4-1 11:06*

很有帮助

## 回复 by 边缘 (#40)

*2025-4-30 19:15*

666

## 回复 by 像风一样呢 (#41)

*2025-5-3 17:42*

666666666666

## 回复 by whohh (#42)

*2025-5-31 17:53*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by homea_qwq (#43)

*2025-5-31 21:46*

了解一下

## 回复 by 饺子和皮特 (#44)

*2025-6-5 10:39*

666

## 回复 by mb_cfjwplfo (#45)

*2025-6-6 14:06*

111

## 回复 by 我不是卷王 (#46)

*2025-6-9 10:13*

1

## 回复 by ONewTach (#47)

*2025-6-9 11:10*

666

## 回复 by 夫人十八岁 (#48)

*2025-6-11 10:47*

666

## 回复 by covccc (#49)

*2025-6-11 15:50*

666

## 回复 by mb_mrgbywba (#50)

*2025-6-15 14:04*

66

## 回复 by Resery (#51)

*2025-7-15 18:58*

否动态定义System.loadLibrary("libsofile") 对应默认目录为自定义私有目录

## 回复 by 不知道诶 (#52)

*2025-7-22 23:46*

666

## 回复 by ghostfevil (#53)

*2025-8-2 08:13*

666

## 回复 by G33k3r (#54)

*2025-8-12 23:51*

学习

## 回复 by lixianhuei (#55)

*2025-8-15 12:40*

66666

## 回复 by 飆汗吉米 (#56)

*2025-8-17 03:48*

6666

## 回复 by wx_五十度灰 (#57)

*2025-8-18 08:56*

666

## 回复 by mb_xyoslnox (#58)

*2025-8-19 20:10*

666

## 回复 by mb_dcjxxhsk (#59)

*2025-9-1 22:35*

666

## 回复 by Arsylk (#60)

*2025-9-2 06:53*

66

## 回复 by mb_npylpnpl (#61)

*2025-9-2 09:34*

1

## 回复 by NshIdE (#62)

*2025-9-9 16:08*

666

## 回复 by Xx_gg (#63)

*2025-10-15 08:48*

6666

## 回复 by mb_benfvkcd (#64)

*2025-11-27 14:41*

666

## 回复 by 0x25519 (#65)

*2025-12-29 18:08*

学习学习

## 回复 by mb_ygfwwoty (#66)

*2026-2-3 15:20*

666

## 回复 by mb_uuqjkoab (#67)

*2026-2-18 21:08*

1

## 回复 by mb_etgbvvic (#68)

*2026-2-21 16:17*

666

## 回复 by 儒雅的灯塔 (#69)

*2026-3-1 02:22*

666

## 回复 by jaefern (#70)

*2026-3-3 16:49*

666

## 回复 by Ram98 (#71)

*2026-3-3 17:13*

666

## 回复 by Whoami默 (#72)

*2026-3-5 14:05*

nice

## 回复 by 量凉 (#73)

*2026-5-27 16:07*

666

## 回复 by 简单的简单 (#74)

*2026-5-27 22:41*

666

## 回复 by l1s00t (#75)

*2026-6-19 21:56*

牛的

## 回复 by mb_kgneopde (#76)

*2026-6-24 11:18*

666

## 回复 by mb_degalzhb (#77)

*2026-7-20 10:20*

666
