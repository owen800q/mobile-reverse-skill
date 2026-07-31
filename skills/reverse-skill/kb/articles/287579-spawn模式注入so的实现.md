---
title: '[原创] spawn模式注入so的实现'
url: https://bbs.kanxue.com/thread-287579.htm
tid: 287579
author: Yangser
date: '2025-07-11'
tags: [Android安全, 原创, 基础理论, HOOK注入, 源码框架]
crawled_at: '2026-07-31T15:46:52+08:00'
replies: 83
---

# 注入篇二 spawn模式的实现

前言：在[上一篇文章](https://yuuki.cool/2025/07/12/InjectSo/)中大概解释了attach模式注入so的实现思路，但是实战中spawn模式注入也是很常用的

## 0x01 什么是spawn注入模式

我的理解是 在目标进程**启动时**对其进行注入。这可以帮助我们绕过部分反调试，同时可以监听一些初始化函数

## 0x02 大致的实现思路

spawn翻译过来是`产卵`的意思，刚接触frida的时候我不理解spawn这个单词和注入这个操作之间的联系，后来才知道这个操作是需要注入zygote的，而zygote翻译过来刚好是`受精卵`的意思，现在感觉还挺有意思的，spawn这个名字确实很恰当

我们想要在进程启动时就注入，那么时机很重要，这个时机当然越早越好...吗？我们知道app进程都是由zygote进程fork而来的，fork之后才会有app进程，这里差不多就是app进程刚出生的时候了，我们在这时，把自己的so注入就可以实现上述的效果了

## 0x03 开始实现

由于我们要hook zygote进程里的一些函数，所以首先要把hook模块注入进zygote进程，关于如何通过ptrace注入目标进程，[上一篇文章](https://yuuki.cool/2025/07/12/InjectSo/)已经讲的比较清晰了，这里就不过多赘述了，这里先来讲讲hook模块应该实现哪些功能吧。这里的hook框架依旧是使用dobby

**首先要明确hook点**

上面说了，我们是hook fork函数，所以目标so是`/system/lib64/libc.so`，查找函数地址可以先dlopen libc.so，然后再dlsym fork函数，这里dlopen是为了拿到对应so的handle，正常进程里libc.so 99%是已经被加载过的，你再打开一次也无所谓，因为linker会直接返回solist里的handle给你，不会浪费很多时间。当然也可以使用elf_utils解析磁盘上的libc.so拿到偏移，然后查找基地址两个相加得到真实的地址

**其次编写hook函数**

| 123456789101112131415161718192021222324252627282930313233 | `static` `std::string getCurrentProcessName() {``char` `process_name[64] = {0};``int` `fd = open(``"/proc/self/cmdline"``, O_RDONLY);``if` `(fd != -1) {``ssize_t len = read(fd, process_name,` `sizeof``(process_name) - 1);``if` `(len > 0) {``process_name[len] =` `'\0'``;``}``close(fd);``}``return` `std::string(process_name);``}` `static` `pid_t hooked_fork() {``if` `(in_hook_fork) {``return` `orig_fork();``}` `LOGD(``"enter fork func!"``);` `pid_t result = orig_fork();` `if` `(result == 0) {``LOGD(``"enter child process"``);``std::string current_process = getCurrentProcessName();``if` `(!current_process.empty()) {``LOGD(``"Child process started: %s"``, current_process.c_str());``//todo 然后判断进程名是否为目标进程，后续再dlopen自己的so``}``}` `return` `result;``}` |
|-|-|

我刚开始是这么写的，我觉得没啥毛病，但是一运行就有问题了，各位可以先思考一下为什么这样不行哈哈哈哈

运行时输出了如下日志：

| 12 | `07-09 10:52:08.046 19197 19197 I [Zygote_Hook]: enter child process``07-09 10:52:08.047 19197 19197 I [Zygote_Hook]: Child process started: zygote64` |
|-|-|

子进程的进程名依然是`zygote64`，为什么会这样呢？？？其实是因为获取进程名的时机太早了，这时子进程还没初始化完全，所以获取到的名字还是父进程的

为了解决这个问题，我们就得先研究一下android中app进程的进程名是如何被设置的，查阅了一番资料后得知`android.os.Process.setArgv0`函数负责设置进程名，它是一个native函数，长这样

| 12345678910111213141516171819 | `void` `android_os_Process_setArgV0(JNIEnv* env, jobject clazz, jstring name)``{``if` `(name == NULL) {``jniThrowNullPointerException(env, NULL);``return``;``}` `const` `jchar* str = env->GetStringCritical(name, 0);``String8 name8;``if` `(str) {``name8 = String8(``reinterpret_cast``<``const` `char16_t*>(str),``env->GetStringLength(name));``env->ReleaseStringCritical(name, str);``}` `if` `(!name8.empty()) {``AndroidRuntime::getRuntime()->setArgv0(name8.c_str(),` `true` `/* setProcName */``);``}``}` |
|-|-|

它的第三个参数就是我们需要的进程名，所以我们可以在子进程中hook这个函数，当函数执行时取出参数，与我们的目标进程名作比较，如果一致，则加载我们自己的so。加载so使用dlopen就行了，但是dlopen只能从那几个路径加载，虽然本文不涉及注入痕迹的隐藏，但简单的能直接避免还是就避免一下吧。如果从app私有目录加载，那么app自己是有权限检查该路径下的文件的，不是很安全。如果从/system/lib下加载，那每次注入不同的so都需要重启手机重新挂载文件，这太麻烦了。所以还是从/data/local/tmp下加载吧，当然这个路径也不安全，但相对好一点。但如果选择这个路径，就会有新的问题。普通app进程是没办法访问这个目录的，所以dlopen肯定会失败。解决方案也比较简单，把selinux设置为宽容模式即可。那么新的问题又来了，hook代码是运行在app进程的，app进程没有权限设置selinux，这里只有Injector进程有这个权限，所以需要设计跨进程通信模块，用于在dlopen前后通知Injector模块修改selinux模式

**设计通信模块**

为了方便，本来想直接用信号的，因为这个通信场景本身也不复杂，但是后面写完才发现权限不够，于是又重写，这里直接用UDS。为了后续开发方便，就把模块单拎出来写了，另外两个模块共享通信模块

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189 | `#include "socket_comm.h"``#include <sys/socket.h>``#include <sys/un.h>``#include <unistd.h>``#include <thread>``#include <android/log.h>``#include <sys/stat.h>``#include <errno.h>` `#define LOG_TAG "[Socket_Comm]"``#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)``#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)` `namespace` `comm {` `SocketServer::SocketServer() : server_fd_(-1), running_(``false``), background_thread_(nullptr) {``}` `SocketServer::~SocketServer() {``Stop();``}` `bool` `SocketServer::Start() {``if` `(server_fd_ != -1) {``LOGE(``"Server already started"``);``return` `false``;``}` `unlink(COMM_SOCKET_PATH);` `// 创建Unix Domain Socket``server_fd_ = socket(AF_UNIX, SOCK_STREAM, 0);``if` `(server_fd_ < 0) {``LOGE(``"Failed to create socket: %s"``,` `strerror``(``errno``));``return` `false``;``}` `struct` `sockaddr_un server_addr;``memset``(&server_addr, 0,` `sizeof``(server_addr));``server_addr.sun_family = AF_UNIX;``strncpy``(server_addr.sun_path, COMM_SOCKET_PATH,` `sizeof``(server_addr.sun_path) - 1);` `if` `(bind(server_fd_, (``struct` `sockaddr*)&server_addr,` `sizeof``(server_addr)) < 0) {``LOGE(``"Failed to bind socket: %s"``,` `strerror``(``errno``));``close(server_fd_);``server_fd_ = -1;``return` `false``;``}` `// 设置socket文件权限，允许所有用户访问``chmod(COMM_SOCKET_PATH, 0666);` `if` `(listen(server_fd_, 1) < 0) {``LOGE(``"Failed to listen on socket: %s"``,` `strerror``(``errno``));``close(server_fd_);``server_fd_ = -1;``unlink(COMM_SOCKET_PATH);``return` `false``;``}` `running_ =` `true``;``LOGI(``"Unix Domain Socket server started at %s"``, COMM_SOCKET_PATH);``return` `true``;``}` `void` `SocketServer::Stop() {``running_ =` `false``;` `if` `(server_fd_ != -1) {``shutdown(server_fd_, SHUT_RDWR);``close(server_fd_);``server_fd_ = -1;``}` `unlink(COMM_SOCKET_PATH);` `if` `(background_thread_) {``if` `(background_thread_->joinable()) {``background_thread_->join();``}``delete` `background_thread_;``background_thread_ = nullptr;``}` `LOGI(``"Socket server stopped"``);``}` `std::string SocketServer::WaitForMessage(``int` `timeout_ms) {``if` `(server_fd_ == -1) {``LOGE(``"Server not started"``);``return` `""``;``}` `fd_set readfds;``FD_ZERO(&readfds);``FD_SET(server_fd_, &readfds);` `struct` `timeval* tv_ptr = nullptr;``struct` `timeval tv;``if` `(timeout_ms >= 0) {``tv.tv_sec = timeout_ms / 1000;``tv.tv_usec = (timeout_ms % 1000) * 1000;``tv_ptr = &tv;``}` `int` `ret = select(server_fd_ + 1, &readfds, nullptr, nullptr, tv_ptr);``if` `(ret <= 0) {``if` `(ret < 0 &&` `errno` `!= EINTR) {``LOGE(``"select error: %s"``,` `strerror``(``errno``));``}``return` `""``;``}` `struct` `sockaddr_un client_addr;``socklen_t client_len =` `sizeof``(client_addr);``int` `client_fd = accept(server_fd_, (``struct` `sockaddr*)&client_addr, &client_len);``if` `(client_fd < 0) {``if` `(``errno` `!= EINTR &&` `errno` `!= EAGAIN) {``LOGE(``"Failed to accept connection: %s"``,` `strerror``(``errno``));``}``return` `""``;``}` `char` `buffer[256] = {0};``ssize_t bytes_read = recv(client_fd, buffer,` `sizeof``(buffer) - 1, 0);``close(client_fd);` `if` `(bytes_read > 0) {``buffer[bytes_read] =` `'\0'``;``LOGI(``"Received message: %s"``, buffer);``return` `std::string(buffer);``}` `return` `""``;``}` `void` `SocketServer::RunInBackground(std::function<``void``(``const` `std::string&)> callback) {``if` `(background_thread_) {``LOGE(``"Background thread already running"``);``return``;``}` `background_thread_ =` `new` `std::``thread``(&SocketServer::AcceptLoop,` `this``, callback);``}` `void` `SocketServer::AcceptLoop(std::function<``void``(``const` `std::string&)> callback) {``LOGI(``"Background accept loop started"``);` `while` `(running_) {``std::string msg = WaitForMessage(1000);``if` `(!msg.empty() && callback) {``callback(msg);``}``}` `LOGI(``"Background accept loop ended"``);``}` `bool` `SocketClient::SendMessage(``const` `std::string& message) {``int` `client_fd = socket(AF_UNIX, SOCK_STREAM, 0);``if` `(client_fd < 0) {``LOGE(``"Failed to create client socket: %s"``,` `strerror``(``errno``));``return` `false``;``}` `struct` `sockaddr_un server_addr;``memset``(&server_addr, 0,` `sizeof``(server_addr));``server_addr.sun_family = AF_UNIX;``strncpy``(server_addr.sun_path, COMM_SOCKET_PATH,` `sizeof``(server_addr.sun_path) - 1);` `if` `(connect(client_fd, (``struct` `sockaddr*)&server_addr,` `sizeof``(server_addr)) < 0) {``LOGE(``"Failed to connect to server: %s (path: %s)"``,` `strerror``(``errno``), COMM_SOCKET_PATH);``close(client_fd);``return` `false``;``}` `ssize_t bytes_sent = send(client_fd, message.c_str(), message.length(), 0);``close(client_fd);` `if` `(bytes_sent < 0) {``LOGE(``"Failed to send message: %s"``,` `strerror``(``errno``));``return` `false``;``}` `LOGI(``"Message sent: %s"``, message.c_str());``return` `true``;``}` `}` |
|-|-|

这样就解决权限的问题了:) 是不是就可以加载so了呢，直接dlopen(SO_PATH, FLAG)，那么`SO_PATH`从哪来？当然完善上面的跨进程通信模块，也能把path传过来，但是有点麻烦了，这里我的解决方案是在hook模块里导出一个函数用于被Injector模块远程调用，参数里传递一些必要的信息，比如`SO_PATH`

| 12345678910 | `// 全局变量存储目标信息``static` `char` `g_target_process_name[256] = {0};``static` `char` `g_target_library_path[512] = {0};` `extern` `"C"` `void` `setTargetInfo(``char``* target_process_name,` `char``* target_library_path) {``strcpy``(g_target_process_name, target_process_name);``strcpy``(g_target_library_path, target_library_path);``LOGI(``"Target process name: %s"``, g_target_process_name);``LOGI(``"Target library path: %s"``, g_target_library_path);``}` |
|-|-|

**总的代码就是这样子的**

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217 | `#include <sys/mman.h>``#include <dlfcn.h>``#include <sys/types.h>``#include <string>``#include <jni.h>``#include "utils.h"``#include "../ipc/socket_comm.h"` `#define LIBC "/system/lib64/libc.so"``#define LIBANDROID_RUNTIME "/system/lib64/libandroid_runtime.so"` `// 全局变量存储目标信息``static` `char` `g_target_process_name[256] = {0};``static` `char` `g_target_library_path[512] = {0};` `typedef` `pid_t (*Fork_t)();``static` `Fork_t orig_fork = nullptr;``void``* fork_addr = nullptr;` `typedef` `void` `(*SetArgV0_t)(JNIEnv*, jobject, jstring);``static` `SetArgV0_t orig_setArgV0 = nullptr;``void``* setArgV0_addr = nullptr;` `static` `volatile` `int``* inject_flag = nullptr;``static` `pid_t g_zygote_pid = 0;` `static` `bool` `g_injection_done =` `false``;` `void` `unhook() {``if``(fork_addr)` `DobbyDestroy(fork_addr);` `if``(setArgV0_addr)` `DobbyDestroy(setArgV0_addr);` `LOGI(``"All hooks removed"``);``}` `extern` `"C"` `void` `cleanup_hooks() {``unhook();` `if` `(inject_flag && inject_flag != MAP_FAILED) {``LOGI(``"Cleaning up shared memory"``);``munmap((``void``*)inject_flag,` `sizeof``(``int``));``inject_flag = nullptr;``}` `memset``(g_target_process_name, 0,` `sizeof``(g_target_process_name));``memset``(g_target_library_path, 0,` `sizeof``(g_target_library_path));``g_injection_done =` `false``;` `LOGI(``"cleanup_hooks completed"``);``}` `static` `void` `hook_setArgV0(JNIEnv* env, jobject clazz, jstring name) {``std::string process_name;``if` `(name && env) {``const` `char``* name_utf = env->GetStringUTFChars(name, nullptr);``if` `(name_utf) {``process_name = name_utf;``env->ReleaseStringUTFChars(name, name_utf);``LOGD(``"Process name: %s"``, process_name.c_str());``}``}` `if` `(!process_name.empty() && process_name == g_target_process_name && !g_injection_done) {``// 标记已完成，避免重复注入``g_injection_done =` `true``;` `// 在子进程中 unhook``if``(setArgV0_addr) {``DobbyDestroy(setArgV0_addr);``setArgV0_addr = nullptr;``}` `LOGI(``"Target process detected: %s, injecting library: %s"``,``process_name.c_str(), g_target_library_path);` `void``* handle = dlopen(g_target_library_path, RTLD_NOW \| RTLD_NODELETE \| RTLD_GLOBAL);` `bool` `inject_success = (handle != nullptr);``if` `(inject_success) {``LOGI(``"Successfully loaded library: %s"``, g_target_library_path);``comm::SocketClient::NotifySuccess();``}` `else` `{``LOGE(``"Failed to load library: %s, error: %s"``,``g_target_library_path, dlerror());``comm::SocketClient::NotifyFailed();``}` `if` `(inject_flag && inject_flag != MAP_FAILED) {``*inject_flag = 1;``LOGI(``"Set inject_flag to 1 in shared memory"``);``}``}` `if` `(orig_setArgV0) {``orig_setArgV0(env, clazz, name);``}``}` `static` `void` `setup_setArgV0_hook() {``void``* handle = dlopen(LIBANDROID_RUNTIME, RTLD_NOW);``if` `(!handle) {``LOGE(``"Failed to open libandroid_runtime.so: %s"``, dlerror());``return``;``}` `const` `char``* symbol =` `"_Z27android_os_Process_setArgV0P7_JNIEnvP8_jobjectP8_jstring"``;``setArgV0_addr = dlsym(handle, symbol);``if` `(!setArgV0_addr) {``LOGE(``"Failed to find %s: %s"``, symbol, dlerror());``return``;``}` `LOGI(``"Found %s at %p"``, symbol, setArgV0_addr);` `orig_setArgV0 = (SetArgV0_t)InlineHook(setArgV0_addr, (``void``*)hook_setArgV0);``if` `(orig_setArgV0) {``LOGI(``"Successfully hooked %s"``, symbol);``}` `else` `{``LOGE(``"Failed to hook %s"``, symbol);``}``}` `static` `pid_t hook_fork() {``LOGD(``"enter fork func!"``);` `pid_t result = orig_fork();` `if` `(result == 0) {``LOGD(``"enter child process"``);``setup_setArgV0_hook();``}` `else` `if` `(result > 0) {``if` `(getpid() == g_zygote_pid && inject_flag && inject_flag != MAP_FAILED && *inject_flag == 1) {``LOGI(``"Injection completed in child process, unhooking fork in parent"``);``if` `(fork_addr) {``DobbyDestroy(fork_addr);``fork_addr = nullptr;``}` `munmap((``void``*)inject_flag,` `sizeof``(``int``));``inject_flag = nullptr;``}``}` `return` `result;``}` `void` `setup_fork_hook() {``void``* handle = dlopen(LIBC, RTLD_NOW);``if` `(!handle) {``LOGE(``"Failed to open libc.so"``);``return``;``}` `const` `char``* fork_symbol =` `"fork"``;``fork_addr = dlsym(handle, fork_symbol);``if` `(!fork_addr) {``LOGE(``"Failed to find fork"``);``return``;``}` `LOGI(``"Found fork at %p"``, fork_addr);` `orig_fork = (Fork_t)InlineHook(fork_addr, (``void``*)hook_fork);``if` `(orig_fork) {``LOGI(``"Successfully hooked fork"``);``}` `else` `{``LOGE(``"Failed to hook fork"``);``}``}` `extern` `"C"` `void` `setTargetInfo(``char``* target_process_name,` `char``* target_library_path) {``strcpy``(g_target_process_name, target_process_name);``strcpy``(g_target_library_path, target_library_path);``LOGI(``"Target process name: %s"``, g_target_process_name);``LOGI(``"Target library path: %s"``, g_target_library_path);` `g_injection_done =` `false``;` `if` `(inject_flag && inject_flag != MAP_FAILED) {``*inject_flag = 0;``LOGI(``"Reset inject_flag to 0"``);``}` `if` `(fork_addr == nullptr && orig_fork == nullptr) {``LOGI(``"Re-hooking fork for new injection"``);``setup_fork_hook();``}``}` `__attribute__((constructor))``void` `initialize_hook() {``LOGI(``"Zygote hook module loaded"``);` `g_zygote_pid = getpid();` `inject_flag = (``volatile` `int``*)mmap(NULL,` `sizeof``(``int``),``PROT_READ \| PROT_WRITE,``MAP_SHARED \| MAP_ANONYMOUS, -1, 0);``if` `(inject_flag != MAP_FAILED) {``*inject_flag = 0;``LOGI(``"Created shared memory for inject_flag"``);``}` `else` `{``LOGE(``"Failed to create shared memory"``);``inject_flag = nullptr;``}` `setup_fork_hook();``}` `__attribute__((destructor))``void` `cleanup_hook() {``LOGD(``"Cleaning up hooks in destructor"``);``cleanup_hooks();``}` |
|-|-|

自己写时记得及时unhook，不然有的软件会进不去

## 0x04 小结

在学校时，用完frida之后去食堂吃饭，付钱的软件老是打不开，当时不明白为什么我明明调试的是别的app，这个app凭什么打不开，其实是用完之后zygote进程里的一些函数没有被unhook，app启动会fork zygote进程，所以就被检测到了:(

再来聊聊检测和过检测吧，就说我写的这个工具吧，如果不开源，可能就是maps里有可疑路径的so，soinfo list里也会有，`/proc/self/fd/` 中的文件描述符，还有就是通信时的痕迹，别的地方感觉也没啥了(注入留下的痕迹，hook的不归我管)。前面两个，目前用户层有的解决方案就是：

- 遍历 `/proc/<pid>/maps`，找到目标库的所有内存段
- 对每个段，远程分配匿名内存、远程 memcpy 覆盖内容、调用 `mremap` 将匿名内存映射到原来的地址
- 最后还原原有的内存保护权限

但这样还是解决不了问题的，因为正常app基本没用可执行的匿名内存段，但是一些加固之后的似乎有，我之前看36O是有的

solist里的痕迹就是通过找到[solist_remove_soinfo](https://cs.android.com/android/platform/superproject/main/+/main:bionic/linker/linker_main.cpp;l=99?q=solist_remove_soinfo)函数的地址，然后调用它，移除目标so的soinfo，当然这里还涉及获取目标so的soinfo，遍历solist等操作，不赘述了

使用[自定义linker](https://github.com/SoyBeanMilkx/soLoader)的方案可以在so的路径上多一些选择，而且不会在solist留下痕迹，但也并非一点痕迹没有的:( 所以还是配合[内核模块](https://github.com/SoyBeanMilkx/feature)一起用吧

---

# 回复

## 回复 by mb_cfjwplfo (#2)

*2025-7-11 17:29*

先创建通信模块注入so然后在这个so文件里面新注入核心代码so是吗![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by Yangser (#3)

*2025-7-11 19:01*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>
>  先创建通信模块注入so然后在这个so文件里面新注入核心代码so是吗[em_004]
>
>

是这样的，因为要监控进程创建

## 回复 by mb_ldbucrik (#4)

*2025-7-11 19:18*

感谢分享

## 回复 by mb_dybhojzi (#5)

*2025-7-13 17:06*

6666

## 回复 by cpannn (#6)

*2025-7-13 20:56*

新东西

## 回复 by mb_nkjfyhkg (#7)

*2025-7-14 01:15*

mark

## 回复 by ONewTach (#8)

*2025-7-14 09:05*

666

## 回复 by TkBinary (#9)

*2025-7-14 09:51*

一件收藏![image](https://bbs.kanxue.com/view/img/face/007.gif)

## 回复 by cydian (#10)

*2025-7-14 13:48*

666

## 回复 by Yangser (#11)

*2025-7-14 14:50*

嘻嘻

## 回复 by CCTV9 (#12)

*2025-7-14 15:35*

6666

## 回复 by mb_mumzrqcs (#13)

*2025-7-15 02:38*

6666666

## 回复 by mb_irhdtnzm (#14)

*2025-7-15 07:40*

z

## 回复 by ben_ (#15)

*2025-7-15 10:48*

学习

## 回复 by 纷纷扰扰 (#16)

*2025-7-15 15:23*

mark

## 回复 by 我是小奥 (#17)

*2025-7-15 17:08*

学习

## 回复 by mb_4nrpVMxJ (#18)

*2025-7-15 17:19*

看看

## 回复 by etsun (#19)

*2025-7-17 11:29*

感谢分享

## 回复 by baichisi (#20)

*2025-7-18 11:31*

66666

## 回复 by Ms135 (#21)

*2025-7-19 09:17*

666

## 回复 by mb_yqsvfqmf (#22)

*2025-7-20 15:50*

能私聊吗

## 回复 by mb_yqsvfqmf (#23)

*2025-7-20 15:51*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  是这样的，因为要监控进程创建
>
>

能私聊吗

## 回复 by Yangser (#24)

*2025-7-21 09:19*

>
> [mb_yqsvfqmf](https://bbs.kanxue.com/user-1043871.htm)
>
>  能私聊吗
>
>

可以的，ShuangXve@gmail

## 回复 by 猫子 (#25)

*2025-7-21 10:55*

学习一下

## 回复 by SInnon (#26)

*2025-7-22 03:26*

666

## 回复 by mb_yqsvfqmf (#27)

*2025-7-22 10:15*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  可以的，ShuangXve@gmail
>
>

你v？

## 回复 by Yangser (#28)

*2025-7-23 14:39*

>
> [mb_yqsvfqmf](https://bbs.kanxue.com/user-1043871.htm)
>
>  你v？
>
>

那是邮箱，这个平台让留v吗，你可以给我发邮件

## 回复 by mb_umadhuev (#29)

*2025-7-23 16:11*

牛逼

## 回复 by mb_yqsvfqmf (#30)

*2025-7-24 21:46*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  那是邮箱，这个平台让留v吗，你可以给我发邮件
>
>

可以发出来的

## 回复 by gaorqing (#31)

*2025-7-24 23:30*

6666

## 回复 by 龙飞雪 (#32)

*2025-7-25 15:19*

学习了

## 回复 by Yangser (#33)

*2025-7-26 18:42*

>
> [mb_yqsvfqmf](https://bbs.kanxue.com/user-1043871.htm)
>
>  可以发出来的
>
>

lIIIIlIllIlIllIIIllI

## 回复 by mb_yqsvfqmf (#34)

*2025-7-29 07:38*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  lIIIIlIllIlIllIIIllI
>
>

？

## 回复 by mb_yfmtnfii (#35)

*2025-7-29 11:05*

1

## 回复 by Vengeance (#36)

*2025-7-29 14:15*

Learn

## 回复 by mb_hkqnanbs (#37)

*2025-7-29 16:39*

看看

## 回复 by wx_huhu_859 (#38)

*2025-7-29 19:46*

1

## 回复 by mb_yqsvfqmf (#39)

*2025-7-29 23:47*

>
> [Yangser](https://bbs.kanxue.com/user-947037.htm)
>
>  lIIIIlIllIlIllIIIllI
>
>

接私不？

## 回复 by Arsylk (#40)

*2025-7-30 06:05*

66

## 回复 by uni7corn (#41)

*2025-7-31 02:05*

学习一下

## 回复 by 肖安111 (#42)

*2025-8-1 16:22*

66

## 回复 by mb_tmbvnlxt (#43)

*2025-8-6 16:45*

666

## 回复 by wx_插曲 (#44)

*2025-8-6 17:16*

牛逼

## 回复 by Old_Yuan (#45)

*2025-8-14 10:11*

666

## 回复 by snowflake911 (#46)

*2025-8-14 13:55*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_ezmrnfsu (#47)

*2025-8-14 15:47*

学习下

## 回复 by 飆汗吉米 (#48)

*2025-8-17 03:37*

6666

## 回复 by huangjw (#49)

*2025-8-18 15:45*

巩固学习

## 回复 by mb_gmubqahb (#50)

*2025-9-17 14:19*

牛

## 回复 by wx_steve (#51)

*2025-9-18 11:21*

666

## 回复 by 安小卓 (#52)

*2025-9-18 12:27*

学习

## 回复 by mb_qqlojqnm (#53)

*2025-9-20 14:49*

1111

## 回复 by anlanemo (#54)

*2025-9-22 14:29*

学习一下

## 回复 by 雅鸦歌 (#55)

*2025-9-25 10:03*

1

## 回复 by XCicada (#56)

*2025-9-25 10:14*

学习

## 回复 by 洛水y (#57)

*2025-9-28 17:12*

感谢分享

## 回复 by mb_dmryhnwz (#58)

*2025-10-2 08:33*

666

## 回复 by Viseris (#59)

*2025-10-10 13:27*

6666

## 回复 by WanQing (#60)

*2025-10-10 14:20*

666

## 回复 by mb_ykavguun (#61)

*2025-10-12 22:34*

1111

## 回复 by mb_iwftxini (#62)

*2025-10-12 23:36*

666

## 回复 by 威兹曼 (#63)

*2025-10-13 08:41*

666

## 回复 by mb_zvxyxkeh (#64)

*2025-10-22 12:44*

看看

## 回复 by mb_qimctavn (#65)

*2025-10-22 13:10*

6

## 回复 by mb_jqqxasya (#66)

*2025-11-3 21:11*

666

## 回复 by 夜惜风雨 (#67)

*2025-11-9 02:10*

6666

## 回复 by mb_yjiuccxa (#68)

*2025-11-10 13:24*

向大佬学习

## 回复 by GEKEZYX (#69)

*2025-11-21 14:08*

666

## 回复 by mb_bhsrdtqf (#70)

*2025-12-14 19:20*

666

## 回复 by xianhuimin (#71)

*2026-1-7 15:10*

感谢分享

## 回复 by wx_Huber Barrientos (#72)

*2026-1-8 00:22*

感谢分享

## 回复 by mb_fucrihek (#73)

*2026-1-8 21:48*

学习

## 回复 by mb_ysegxpmv (#74)

*2026-1-8 21:49*

牛皮，大佬

## 回复 by GeQ1an (#75)

*2026-1-10 17:50*

66666

## 回复 by 天路 (#76)

*2026-1-26 13:57*

666

## 回复 by 墨点 (#77)

*2026-1-31 12:00*

666

## 回复 by wfassg (#78)

*2026-3-5 16:04*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by jaefern (#79)

*2026-3-6 17:21*

666

## 回复 by 我不是卷王 (#80)

*2026-3-8 07:32*

6

## 回复 by iBa0 (#81)

*2026-3-26 17:31*

123

## 回复 by hanjiefang (#82)

*2026-5-27 10:08*

学习

## 回复 by emgelu48 (#83)

*2026-6-17 09:09*

nice

## 回复 by MilesKing (#84)

*2026-7-9 02:56*

先收藏了
