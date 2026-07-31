---
title: '[原创]frida版xposed'
url: https://bbs.kanxue.com/thread-286627.htm
tid: 286627
author: KerryS
date: '2025-04-26'
tags: [Android安全, 原创, 工具脚本]
crawled_at: '2026-07-31T14:10:40+08:00'
replies: 13
---

## 背景

主要是因为使用frida server的时候，时间长一点，系统会不稳定，时不时系统就好像重启了一样，虽然没有真的重启，但是qtscrcpy就会断掉，蓝牙也会断掉，frida server也卡死，就又得重新搞，很烦；根本原因就是因为frida的server不仅hook了目标进程，还hook了system server，为了实现spawn以及获取进程信息等等功能，所以server一旦蹦掉，遗害整个系统环境；故而想把frida想xp一样，集成一下，每次应用启动的时候就已经带了，可以直接使用。

## 主要功能

在app启动的时，并且任意app自己的代码执行前，会启动一个服务端，这个服务会接受客户端命令，主要是三个命令，load脚本，update脚本，unload脚本，以实现frida相关功能；并且支持配置，只对目标app才会启动这个服务端。这样一来，使用frida就方便了很多，不需要启动server，检测面少了好多；其次是避免了server的一系列副作用，比如影响系统等；最后是，它的启动早于任何app代码，也就是说第一时间能拿到app的控制权，方便后续做一些检测对抗，接下来说说具体实现，效仿前辈xposed，修改zygote，这里就得提一下zygote相关的必要知识

## zygote启动

zygote的启动

![image](https://bbs.kanxue.com/upload/attach/202504/844633_DFDHK83EYR9CSFY.webp)

对应的文件是

/root/aosp/frameworks/base/cmds/app_process/app_main.cpp的main函数，对应app_process64

/root/aosp/frameworks/base/core/jni/AndroidRuntime.cpp的start函数，对应libandroid_runtime.so

/root/aosp/frameworks/base/core/java/com/android/internal/os/ZygoteInit.java，对应framework.jar

zygote干完他该干的活（启动art，预加载一些常用系统资源，fork系统服务）之后，就启动了一个服务端，进入循环等死状态，等待ams给他发送app fork请求

## app启动

zygote接受到ams的fork请求之后，执行fork，如下

/root/aosp/frameworks/base/core/jni/com_android_internal_os_Zygote.cpp的

com_android_internal_os_Zygote_nativeForkAndSpecialize{

    ForkCommon{

        SpecializeCommon{

            void SetThreadName(const std::string& thread_name)

根据我的观察，SetThreadName函数具有非常良好的性质，

1、首先它是在fork之后的，也就是运行在了app进程空间，此时启动我们的服务，是比较好的，如果在fork前执行的话，fork调用执行的时候，服务会死掉，因为fork是单线程的

2、其次，这时候在app任何代码执行之前，意味着能在最先的时机拿到app控制权，方便做一些检测的对抗

3、再次，这里可以非常方便的拿到app的名字，方便做过滤，只对目标app启动我们的服务

## 静态注入

将我们的逻辑用c++写好之后编译成so，通过lief静态注入到zpp_process64

| 123456789101112131415161718 | `def` `inject_so_tail(src:``str` `\| Path,``new_so:``str``,``dst:``str` `\| Path \|``None` `=` `None``)``-``> Path:``bin_``=` `lief.parse(``str``(src))` `# 1. 记录旧依赖顺序并全部移除``old_needed``=` `[lib``for` `lib``in` `bin_.libraries``if` `lib !``=` `new_so]``for` `lib``in` `list``(bin_.libraries):``bin_.remove_library(lib)` `# 2. 先插入新库，再按「旧依赖逆序」重建``bin_.add_library(new_so)``# 现在它在最前``for` `lib``in` `reversed``(old_needed):``# 逐个插到前面``bin_.add_library(lib)` `out``=` `Path(dst)``if` `dst``else` `Path(``str``(src)``+` `".patched"``)``bin_.write(``str``(out))``return` `out` |
|-|-|

修改好之后，需要借助apatch来实现替换，对于apatch，做了一些了解，它主要是通过向内核注入一段程序，来实现所有功能的，包括kpm,apm,root等。并且他会给用户态暴露系统调用，由这个系统调用统筹管理所有功能，以下这段程序即可使线程获得至高权限，并且pid也不是0，注意，这个线程去执行命令，是没有高权限的，只是他自己有

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `#include <stdio.h>``#include <unistd.h>``#include <sys/syscall.h>``#include <errno.h>``#include <stdlib.h>``#include <fcntl.h>    // 为 O_WRONLY、O_CREAT、O_TRUNC 添加``#include <string.h>   // 为 strerror 添加``#include <sys/stat.h> // 为 stat 结构体和函数添加``#include <sys/types.h> // 添加基本类型定义` `// 大多数Android设备上SuperCall系统调用号``#define __NR_supercall 45` `// 线程级提权命令``#define SUPERCALL_THREAD_SU 0x1011`  `static` `inline` `int` `ver_and_cmd(``const` `char` `*key,``int` `cmd) {``int` `v = 0;``for` `(``int` `i = 0; key[i]; ++i) {``v += key[i];``}``return` `((v & 0xffff) << 16) \| (cmd & 0xffff);``}` `int` `main(``int` `argc,``char` `*argv[]) {` `const` `char` `*key =``"xxxxx"``;``int` `tid = gettid();` `// 执行提权``long` `result = syscall(__NR_supercall, key, ver_and_cmd(key, SUPERCALL_THREAD_SU), tid,``"u:r:magisk:s0"``);``printf``(``"提权调用返回值: %ld\n"``, result);`   `// 只输出一些核心信息以便快速判断``printf``(``"\n--- 权限验证信息 ---\n"``);``system``(``"cat /proc/self/status \| grep -E 'Uid:\|Gid:\|CapEff:'"``);` `return` `0;``}` |
|-|-|

这个系统调用日后应当有大作为，目前暂时不用,目前只是用一下apm模块，apm模块主要做的事情就是完成app_process64的替换，同时往/system/lib64里挂载上我们的主要功能so，功能so主要实现如下，

读取配置文件，hook setthreadname，判断是不是目标进程

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950 | `static` `void` `hook_thread() {``// 1. 初始化 Gum``LOGD(``"[*] hook_thread() called"``);``sleep(2);``gum_init_embedded();``GumAddress base_adress=get_module_base(``"libandroid_runtime.so"``);` `GumAddress SpecializeCommon=base_adress+(GumAddress)0x20AB70;``GumAddress SetThreadName=base_adress+(GumAddress)0x2118A0;``ExtractJString=(ExtractJStringFunc)(base_adress+(GumAddress)0x2115E0);` `auto` `on_enter = [](GumInvocationContext* ic, gpointer) {``gpointer raw = gum_invocation_context_get_nth_argument(ic, 0);``auto` `str =``reinterpret_cast``<``const` `std::string*>(raw);``//        LOGD("[on_enter] SetThreadName %d %s",getpid(),str->c_str());``entry(str->c_str());` `};` `auto` `on_leave = [](GumInvocationContext* ic, gpointer) {` `gpointer raw = gum_invocation_context_get_nth_argument(ic, 0);``auto` `str =``reinterpret_cast``<``const` `std::string*>(raw);``LOGD(``"[on_leave] SetThreadName %d %s"``,getpid(),str->c_str());``};` `gum_hook((GumAddress)SetThreadName,``on_enter,``nullptr,``nullptr);`  `LOGD(``"[*] hook_thread() finished"``);``}`  `__attribute__((constructor))``void` `test_entry(){``//``std::``thread` `t(hook_thread);``t.detach();`        `}` |
|-|-|

如果是目标进程，启动两个线程，其中一个线程负责接收外部指令，也就是load脚本哪些；另一个线程负责具体处理脚本相关的操作，使用frida-gumjs的c api，两个线程内部使用zmq的inproc功能通信，server线程使用zmq的socket通信，zmq是一个轻量级的强大的消息中间件，使用它可以避免原始socket，功能太低级，要处理很多繁琐的细节

| 12345678910111213141516171819202122232425262728293031323334353637 | `//__attribute__((constructor))``void` `entry(``const` `char``* name) {``//    LOGD("entry() called");`  `json j= read_config(``"/system/lib64/dconfig.so"``);``if` `(j.is_null()&&!j.contains(``"process"``) \|\| !j[``"process"``].is_array()) {``LOGD(``"未找到 process 数组或类型错误"``);``return``;``}` `// 3. 遍历 process 数组``for` `(``auto``& item : j[``"process"``]) {``// 用 value(key, 默认值) 既能获取值，又能避免不存在时报异常``std::string pname       = item.value(``"name"``,``""``);``std::string js_content = item.value(``"js_content"``,``""``);``if``(pname.find(name) == std::string::npos) {``continue``;``}``else``{``int` `port = get_free_port();``static` `Server server(port);``if` `(!server.initialize().success) {``LOGD(``"Server 初始化失败，进程: %s"``, name);``return``;``}``LOGD(``"进程名: %s，分配端口: %d"``,name, port);``LOGD(``"进程名: %s，脚本内容: %s"``, pname.c_str(), base64_decode(js_content).c_str());``void``* context = server.getZmqContext();``Agent::instance().startThread(context,js_content);``server.start();``return` `;``}` `}`  `}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839 | `#ifndef AGENT_H``#define AGENT_H` `#include <string>``#include "../include//frida-gumjs.h"``#include "../common/result.h"``#include "../include//zmq.h"``using` `common::Result;` `class` `Agent {``public``:``static` `Agent& instance();` `Result initialize();``Result load();``Result unload();``Result updateScriptContent(``const` `std::string &content);``Result cleanup();` `// 新增方法：处理字符串命令、启动线程监听inproc socket``std::string handleCommand(``const` `std::string& msg);``void` `startThread(``void``* context,``const` `std::string& init_script=``""``);``// 会在内部 initialize 和启动主循环``private``:``Agent();``Agent(``const` `Agent&) =``delete``;``Agent& operator=(``const` `Agent&) =``delete``;` `static` `void` `onMessage(``const` `gchar* message, GBytes* data, gpointer user_data);``void` `loop(``void``* zmqContext);``bool` `isLoaded_;``bool` `isInitialized_;``std::string scriptContent_;``std::string initScriptContent_;``GumScriptBackend* backend_;``GumScript* script_;` `};` `#endif // AGENT_H` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `#pragma once``/*``* Server.h - 网络服务类（简化版）``*``* 设计说明：``*  1. 采用面向对象设计，不使用集中状态块``*  2. 使用 ZeroMQ 实现对外命令的收发（REP 模式）``*  3. 提供初始化、启动、停止和消息处理接口``*  4. 日志使用 LOGD 简单输出``*/` `#include <string>``#include <thread>``#include <atomic>``#include "../common/result.h"  // Result 类（假定已实现）``#include <../include//zmq.h>` `class` `Server {``public``:``// 构造函数：指定监听端口``explicit` `Server(``int` `port);` `// 析构函数：自动停止服务，释放资源``~Server();` `// 初始化服务（创建 ZeroMQ context、socket，并绑定端口）``common::Result initialize();` `// 启动网络服务线程，开始接收客户端命令``common::Result start();` `// 停止服务，等待线程退出并清理资源``common::Result stop();` `// 处理接收到的 JSON 命令，返回 JSON 字符串作为响应（同步调用）``std::string handleMessage(``const` `std::string &msg);` `void``* getZmqContext()``const``;` `private``:``// 监听端口``int` `port_;` `// 标识服务运行状态``std::atomic<``bool``> isRunning_;` `// ZeroMQ context 与 REP socket``void``* zmqContext_;``void``* zmqSocket_;``void``* agentSocket_;``// 用于 inproc://agent``// 网络服务线程``std::``thread``* networkThread_;` `// 网络线程的主循环函数``void` `networkLoop();` `// 日志辅助函数：简单输出日志` `// 禁止拷贝``Server(``const` `Server&) =``delete``;``Server& operator=(``const` `Server&) =``delete``;``};` |
|-|-|

以下是一个简单的客户端，用来发送脚本给app中的服务端执行，他会监控脚本变换，变化了自动更新到服务端

| 123456789101112131415 | `const SERVER_ADDRESS =``'tcp://192.168.1.19:42803'``;``// 主流程：ping -> unload -> update -> load -> 监控脚本变更``executePing(SERVER_ADDRESS)``.then(() => executeUnload(SERVER_ADDRESS))``.then(() => executeUpdate(SERVER_ADDRESS,``'./test2.js'``))``.then(() => executeLoad(SERVER_ADDRESS))``.then(() => {``console.log(``' 初次更新并加载完成，开始监控脚本变化...'``);``monitorScript(SERVER_ADDRESS,``'./test2.js'``);``})``.``catch``(err => {``console.error(``'❌ 出错:'``, err.message);``suggestTroubleshooting();``process.exit(1);``});` |
|-|-|

效果如下

| 12345678910111213141516171819202122232425 | `root@DESKTOP-K3A36QE:``/mnt/c/Users/qqhil/Desktop/remove-cc-plugin/work_code``# node kagent_client.mjs``→ PING tcp:``//192``.168.1.19:55253``↩︎ 服务器原始响应: {``"message"``:``"pong"``,``"success"``:``true``}``✅``ping` `成功``→ UNLOAD SCRIPT``↩︎ 服务器原始响应: {``"message"``:``"Script not loaded"``,``"success"``:``true``}``✅ unload 成功``→ UPDATE test2.js (Base64 编码后 128268 字节)``↩︎ 服务器原始响应: {``"message"``:``"Script content updated"``,``"success"``:``true``}``✅ update 成功``→ LOAD SCRIPT``↩︎ 服务器原始响应: {``"message"``:``"Script loaded successfully"``,``"success"``:``true``}``✅ load 成功``初次更新并加载完成，开始监控脚本变化...``初始脚本哈希: 35c6525790bb9fd3ca008cbe1b9765b60112bdc03f8e85fc8a4eecae93f97b55`   `2025-04-26 21:23:20.594 17259-17259 giao                    pid-17259                            D  进程名: com.tencent.mobileqq，分配端口: 55253``2025-04-26 21:23:20.595 17259-17259 giao                    pid-17259                            D  进程名: com.tencent.mobileqq，脚本内容:``2025-04-26 21:23:36.416 17259-17263 giao                    com.tencent.mobileqq                 D  onMessage:``set` `------------------------------------------------------------------------------``2025-04-26 21:23:36.416 17259-17263 giao                    com.tencent.mobileqq                 D  onMessage:``set` `Process.``id``, 17259,Process.arch, arm64``2025-04-26 21:23:36.417 17259-17263 giao                    com.tencent.mobileqq                 D  onMessage:``set` `1111111``2025-04-26 21:23:36.417 17259-17263 giao                    com.tencent.mobileqq                 D  onMessage:``set` `------------------------------------------------------------------------------` |
|-|-|

附件放在网盘了

链接：https://pan.baidu.com/s/1NQFk1Z-S-jfKkfvksc1xag

提取码：g89w

---

# 回复

## 回复 by 智取琪 (#2)

*2025-4-27 08:50*

666

## 回复 by 院士 (#3)

*2025-4-27 12:55*

先记号，慢慢研究。

## 回复 by Payne-Wu (#4)

*2025-4-29 16:18*

mark

## 回复 by 墨穹呢 (#5)

*2025-4-29 22:16*

感谢分享

## 回复 by mb_elqwyvnm (#6)

*2025-4-30 00:10*

值得学习

## 回复 by 万里星河 (#7)

*2025-5-18 00:05*

lief添加依赖so apatch把依赖so放入系统库路径 gum inlinehook 然后gumjs执行脚本?

## 回复 by KerryS (#8)

*2025-5-18 02:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  lief添加依赖so apatch把依赖so放入系统库路径 gum inlinehook 然后gumjs执行脚本?
>
>

是这样的,只要hook到一个合适的方法就好,这个方法必须在fork之后的进程,并且距离app代码开始执行的地方越近越好

## 回复 by 万里星河 (#9)

*2025-5-20 23:51*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  是这样的,只要hook到一个合适的方法就好,这个方法必须在fork之后的进程,并且距离app代码开始执行的地方越近越好
>
>

感谢您的回复 还有个地方我不太明白 关于APatch文中提到“对于apatch，做了一些了解，它主要是通过向内核注入一段程序，来实现所有功能的，包括kpm,apm,root等。并且他会给用户态暴露系统调用，由这个系统调用统筹管理所有功能” 请问这个信息是从何处得知的 能提供一下这方面的文档链接吗？

## 回复 by KerryS (#10)

*2025-5-21 01:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  感谢您的回复 还有个地方我不太明白 关于APatch文中提到“对于apatch，做了一些了解，它主要是通过向内核注入一段程序，来实现所有功能的，包括kpm,apm,root等。并且他会给用户态暴露系统 ...
>
>

这个就比较综合了,要去了解root的原理,核心是linux的权限系统及其实现,流行的手法是setuid位方式提权和内核中cred相关字段方式,了解这些知识后去看看apatch的源码,再写一些简单的例子尝试,得出的结论

## 回复 by 万里星河 (#11)

*2025-5-23 00:00*

>
> [KerryS](https://bbs.kanxue.com/user-844633.htm)
>
>  这个就比较综合了,要去了解root的原理,核心是linux的权限系统及其实现,流行的手法是setuid位方式提权和内核中cred相关字段方式,了解这些知识后去看看apatch的源码,再写一些简单的例子 ...
>
>

受教了 感谢

## 回复 by mb_jkykcuwo (#12)

*2025-6-10 10:54*

老师！牛马导师！

## 回复 by mb_jkykcuwo (#13)

*2025-7-23 16:15*

老师 我想问一下 这种方法里的js脚本怎么样才能跑 Java.perform呢 试了下 报错了![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by mb_nazusqig (#14)

*2025-9-14 23:11*

666
