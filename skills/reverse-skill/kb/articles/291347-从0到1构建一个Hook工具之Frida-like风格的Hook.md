---
title: '[原创]从0到1构建一个Hook工具之Frida-like风格的Hook'
url: https://bbs.kanxue.com/thread-291347.htm
tid: 291347
author: n_1ng
date: '2026-05-25'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T15:05:41+08:00'
replies: 34
---

## 前言

一开始的 `Nook`，本质上是一个 Android Hook 框架。它已经具备了几类底层能力：注入、Java Hook、Native Hook。但这距离Frida-like的Hook风格还有很大的差距，**一个 Hook 框架，不等于一个可用的动态分析工具**。框架解决的是“你注入进去之后能做什么”，工具解决的是“你如何把能力稳定、可重复、低摩擦地用起来”。

项目仓库在：

[Nook仓库地址](https://github.com/x1aon1ng/Nook)

大佬们可以尝试着用一下看，release里下一个server，然后

```python
python -m pip install --upgrade nook-cli
```

脚本语法基本和Frida一致，希望大家点点star哈哈，有问题可以提提issue或者直接在评论里提，后面有时间会持续维护和更新。

## 目标

接下来要做的是把它推进成一个更接近 Frida 使用体验的东西：

- 可以 `spawn` / `attach`
- 可以加载脚本
- 可以在脚本里做 Java / Native Hook
- 可以像 Frida 一样在宿主侧用 CLI 驱动整个流程

因为这里的代码实现比较冗长，所以这篇文章和前面几篇的风格会有所不同：通过案例来介绍Nook以及简单介绍Frida背后是怎么做的。

这里案例使用的是https://github.com/DERE-ad2001/Frida-Labs

## 从整体来看Nook增加了哪些模块

在此之前，作为一个Hook框架，Nook实现一次hook的基本语义是这样的：

```c
  static int (*orig_Add)(int a, int b) = nullptr;

  int Hook_Add(int a, int b) {
      int ret = orig_Add(a, b);
      return ret + 100;
  }

  void InstallHook() {
      NookInlineHookAddress(
          (void*)Add,
          (void*)Hook_Add,
          (void**)&orig_Add
      );
  }
```

并且我们需要手动的编译成so，通过Ninjector这样的注入工具注入到目标app中。

而我们的目标是像Frida那样，在设备上启动一个server，我们在host端只需要写好js脚本，通过一行命令就能完成hook，在已经有一个Hook框架的基础上，我们还需要什么呢？

首先我们把Nook定为三层结构：

- Host
	- CLI / Python SDK / REPL
- Device Server
	- `nook-server`
- Target Agent
	- 注入到目标进程里的运行时

另外我们还需要通信和协议层来进行远程的操控：

- transport
	- TCP / Unix socket / ADB forward 这类传输
- protocol
	- frame / tlv / message types
- session
	- 会话管理、请求响应关联、消息分发
- server handlers
	- 处理 host 发来的脚本、RPC、resume、detach 等请求

最后还需要一个脚本运行时，将工作模型从`写c+编译+注入`变为`写js+动态加载`，通过一个JS Bridge，把底层的Hook能力变成我们熟悉的脚本API

### 从一个最小例子来理解完整的一次Hook过程

先从一个脚本开始：

```js
Java.perform(function () {
  var MainActivity = Java.use("com.ad2001.frida0x1.MainActivity");
  MainActivity.get_random.implementation = function () {
    return 1;
  };
});
```

一次Hook的本质是：

```python
- 主机端把脚本送进目标进程
- 目标进程里的 QuickJS 执行脚本
- `Java.perform(...)` 把执行切进 Java VM
- `Java.use(...)` 找到目标类并构造方法 wrapper
- `.implementation = fn` 把 JS 函数登记成 Java hook 回调
- 底层安装真正的 Java hook
- 当目标方法被调用时，再从 Java/Native 层回调回 JS
```

#### Host侧发起操作

用户做的事情通常是：

```python
nook-cli -U com.ad2001.frida0x1 -l .\tests\Test_Lab\nook-frida-labs\frida-0x1\script.js
```

这里 Host 侧承担的职责是：

```python
1. 解析命令行参数
2. 连接设备上的 `nook-server`
3. 选择 attach 或 spawn 工作流
4. 建立一个面向目标进程的 session
5. 把 `script.js` 内容作为脚本加载请求发给 server
```

#### Server 负责把 agent 放进目标进程，并建立控制连接

`nook-server` 接到 Host 请求后，不是自己去执行 Hook。它真正负责的是：

```python
- 找到目标进程
- 或拉起目标进程
- 注入 `libnook-agent.so`
- 等 agent 在目标进程内初始化完成
- 建立 Host ↔ Server ↔ Agent 的控制通道
```

#### Agent 启动 QuickJS 运行时，并接收脚本

agent 进入目标进程后，会初始化自己的运行时环境：

```python
- QuickJS runtime
- script registry
- native / java / rpc / message bridge
```

接着 server 把 `SCRIPT_LOAD` 这类请求转发给 agent，agent 再把脚本内容交给 `JsRuntime::Evaluate(...)` 一类入口去执行。

#### JS 运行时先执行 `Java.perform(...)`

脚本一加载，首先跑到的是：

```js
Java.perform(function () { ... });
```

这一步表面语义很简单：在 Java 可用的时候执行回调”，对 Nook 来说，它实际做了两件事：

1. 确保当前执行上下文能安全进入 Java VM
2. 在 Java ready / class loader ready 的语义下安排这个回调

#### Java.use(...)构造 wrapper

接下来脚本会执行：

```js
var MainActivity = Java.use("com.ad2001.frida0x1.MainActivity");
```

- 构造了一个 JS 层的 class wrapper / proxy

这个 wrapper 里会延迟解析：

```python
- 方法
- 字段
- 重载信息
- static / instance 元数据
```

#### implementation = fn 真正的“安装 Hook 请求”

```python
MainActivity.get_random.implementation = function () {
  return 1;
};
```

此时把脚本层意图翻译成底层 Hook 引擎能够理解的安装请求。当 `implementation = fn` 落到 native bridge 后， Nook 会继续把请求传给 Java hook 子系统。安装成功后，当 app 运行到`MainActivity.get_random()`时，底层 Java hook 会先截获这次调用，然后再把控制流送回 Nook runtime 持有的 JS callback，也就是：

```python
function () {
  return 1;
}
```

于是完整链路变成：

```python
1. Java 方法被调用
2. 底层 Java hook 命中
3. 回到 Nook 的 callback receiver
4. 再桥接回 JS runtime
5. 执行用户脚本里的实现函数
6. 把 JS 返回值再转回 Java / JNI 可接受的值
7. 最终把这个值作为真实方法返回值送回上层
```

#### 简单的一个流程图

```python
Host CLI
  -> Server
    -> inject agent
      -> QuickJS runtime 初始化
        -> load script.js
          -> Java.perform(...)
            -> Java.use(...)
              -> method wrapper
                -> implementation = fn
                  -> Java hook install
                    -> 目标方法后续真正执行
                      -> hook 命中
                        -> 回调回 JS
                          -> return 1
                            -> 写回真实返回值
```

## 通过不同的案例来理解细节

### Frida 0x1：Hook Java 方法

第一个例子是最典型的 Frida Java Hook 入门题。

目标app关键方法如下：

 ![test1](https://bbs.kanxue.com/upload/attach/202605/985628_TPDUWMQG2VZFM47.webp)

在 `frida-0x1` 里，目标是 Hook `MainActivity.get_random()`，把返回值强制改成 `5`，然后再观察后续 `check(int, int)` 的参数。

这个例子很适合作为起点，因为它对应的是 Frida 最基础、也最高频的能力：**通过脚本替换 Java 方法实现**。我们很容易就可以写出对应的hook代码：

```c
Java.perform(function () {
  var MainActivity = Java.use("com.ad2001.frida0x1.MainActivity");
  var getRandom = MainActivity.get_random.overload();
  var check = MainActivity.check.overload("int", "int");

  getRandom.implementation = function () {
    console.log("lab:frida-0x1:hit:get_random");
    console.log("lab:frida-0x1:result:forced-random=5:expected-input=14");
    return 5;
  };

  check.implementation = function (left, right) {
    console.log("lab:frida-0x1:hit:check:left=" + left + ":right=" + right);
    return this.check.callOriginal(left, right);
  };

  console.log("lab:frida-0x1:installed");
});
```

Hook效果如下，输入14后就可以在app页面看到flag：“FRIDA{BABY_HOOK_0x1}”：

```python
(nook) C:\Users\n1ng>nook-cli -U -f com.ad2001.frida0x1 -l E:\Learn\my_program\all_my_hook\kanxue\Nook\tests\Test_Lab\nook-frida-labs\frida-0x1\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.0

 Dynamic instrumentation toolkit for Android

[*] Spawning 'com.ad2001.frida0x1'...
[*] Waiting for agent runtime ready...
[+] Spawned (pid: 32326)
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[*] Resuming pid 32326...
[+] Process resumed
lab:frida-0x1:installed
lab:frida-0x1:hit:get_random
lab:frida-0x1:result:forced-random=5:expected-input=14
lab:frida-0x1:hit:get_random
lab:frida-0x1:result:forced-random=5:expected-input=14
lab:frida-0x1:hit:check:left=5:right=14
```

我们第一步就从这个脚本出发：

#### Java.perform(function())

首先是第一句代码`Java.perform(function())`，这句代码意味着什么？

可以简单将其理解为：“等 Java 运行环境准备好之后，再执行这段回调。”它的目的不是单纯“执行一个函数”，而是保证下面这些 Java 相关操作发生在一个安全时机：已经拿到JNIEnv*，Java VM已经可用，目标app的ClassLoader/生命周期已经可以做到Java.use(...) 的阶段。不然你太早去 Java.use("com.ad2001.frida0x1.MainActivity")，很容易因为类还没准备好、ClassLoader 还没就绪而失败。

在Nook中，我是这么去处理的：

```c
  Java.perform = function (fn) {
    if (Java._isClassLoaderReady()) {
      return Java.vm.perform(fn);
    }
    return Java.ready(function () {
      return Java.vm.perform(fn);
    });
  };
```

意思很容易理解：

- 如果 ClassLoader 已经 ready，立刻执行
- 如果还没 ready，就先挂到 Java.ready(...) 队列里，等 ready 再执行

在agent_rumtime里面，Nook 维护了一个readyCallbacks 队列。它会检查两类条件：Java._isClassLoaderReady()和Java._isLifecycleReady()。

如果还没 ready，就把当前脚本的回调缓存起来；等到 Java.__nookDispatchReady() 被触发时，再把这些回调取出来执行。

简单总结Java.perform(fn) 本质上做的是：

```python
    1. 看 Java/ClassLoader 是否 ready
    2. 如果没 ready，把 fn 存起来
    3. ready 之后再调用 Java.vm.perform(fn)
```

真正执行回调的是 Java.vm.perform(...)：

```python
  - 调 QueryCurrentJavaEnvPointer(true, ...) 获取当前可用的 JNIEnv*
  - Android 下如果需要，会先 EnsureJavaHookReadyForJs(...)
  - 用一个 scoped override 把这次拿到的 JNIEnv* 绑定到当前 JS 执行上下文
  - 然后再真正调用你传进来的 JS 回调
```

也就是：带着一个有效的 Java 环境去执行你的回调。

Frida是怎么做的呢？其实做的事情是类似的，判断当前是不是app process，classFactory.loader是否已经准备好，ready了就this.vm.perform(fn)，还没ready就把回调塞进 _pendingVmOps，然后启动 _performPendingVmOpsWhenReady()。

Frida 的 Java.perform 负责等待 Java / loader 可用，并把回调排队到 VM-ready 路径，也就是说，Frida 的 Java.perform 自己就带了一套 “等 app class loader ready 并把它接起来” 的逻辑。

Nook 这边则是

```python
  - C++/bridge 层提供 _isClassLoaderReady()、_isLifecycleReady()
  - JS 层 Java.perform(...) 只负责：
      - 查 ready
      - 排队
      - ready 后执行
```

以及Frida 的vm.perform() 自己 attach/detach 线程，而Nook的Java.vm.perform() 先解析/确保可用 env，再在当前 JS 执行上下文里带着它跑。

简单总结就是Frida的Java.perform自己处理 pending + bootstrap，Nook 的 Java.perform的处理更简单，一个“基于 ready 条件和脚本桥接机制的等待执行器”，更复杂的时机控制被放到了后面的 spawn gate /script runtime bridge 里。

#### Java.use(class)

然后是

```js
var MainActivity = Java.use("com.ad2001.frida0x1.MainActivity");
```

Java.use(...) 在 Nook 里做了什么？其实只是：

```python
  - 把类名取出来
  - 调 CreateJavaUseWrapper(ctx, class_name)
```

Java.use("com.ad2001.frida0x1.MainActivity") 本质不是“立刻找类并返回 JNI 对象”，也不会“立刻把这个类执行起来”，而是“构造一个能代表这个 Java 类的 JS wrapper”。

后面的比如

```python
  - Foo.bar()
  - Foo.someField.value
  - Foo.$new()
  - Foo.baz.overload(...)
```

都是在这个`wrapper`之上继续展开的。

这个 wrapper 的生成逻辑在 `CreateJavaUseWrapper()`，`CreateJavaUseWrapper()` 里面内嵌了一大段 JS factory 代码，用来构造一个 Frida 风格的 Java 类包装对象。这个 wrapper 至少包含几层东西：

```python
  - $className
  - __nookJavaReceiverHandle
  - __nookJavaLoaderHandle
  - 方法缓存 __nookMethodCache
  - 字段缓存 __nookFieldCache
```

另外，它会动态构造出一个 `makeMethod(...)`，这个 `makeMethod(...)` 生成的方法对象会带这些元数据：

```python
  - method.$className
  - method.$methodName
  - method.$signature
  - method.$isStatic
  - method.__nookJavaReceiverHandle
  - method.__nookJavaLoaderHandle
```

所以再下一句Hook代码中的 `var getRandom = MainActivity.get_random.overload()`不是普通 JS function，它其实是一个带 Java 方法元数据的 JS 方法 wrapper。

并且`Java.use(...)` 不一定立刻 resolve 全部方法， 当执行Java.use的时候Nook 并不会在这一刻就把 MainActivity 的所有成员都反射出来只是先返回一个代理对象，真正去处理成员访问，是在后面你写，比如`MainActivity.get_random`，即

```python
  - 先返回一个类 wrapper
  - 方法访问时再按需生成 method wrapper
  - overload 信息需要时再补解析
```

简单总结就是`Java.use(...)` 的核心产物不是 `JNI class handle`，而是“后续可继续演化的 `JS wrapper`”。

Nook在这点的处理和Frida是类似的，都不是直接返回裸jclass，而是一个面向脚本层的类代理对象，不过Frida的`ClassFactory`比Nook成熟的多，Java.use(...) 只是默认 class factory 的入口，真正负责类包装、loader 关联、wrapper 缓存、对象 cast/use 的，是 `ClassFactory`。而且 Frida 的 runtime 里，classFactory.loader 是一个很关键的状态。

#### overlaod()

在Nook中，overload(...) 可以理解成：Java.use 拿到的是“方法组”，overload(...) 才是把这个方法组收窄成“某一个确定签名的方法”。

比如`var getRandom = MainActivity.get_random.overload()`，这里不是在调用 get_random，而是在做“选重载”。后面你给 getRandom.implementation、check.implementation 赋值时，挂钩目标就已经不是一个模糊的方法名了，而是一个唯一的方法签名。

Nook 在js_runtime里调用makeMethod(...) 给每个方法包装器都挂了一个 method.overload = function () { ... }，它会：

```python
  - 取出你传的类型名列表
  - 先查 __nookOverloadCache
  - 没命中就调用 __nookJavaResolveOverloadSignature(className, methodName, typeNames, loaderHandle)
  - 拿到唯一签名后，再重新生成一个绑定了 $signature、$overloadTypeNames、$isStatic 的新 method wrapper
```

所以 overload(...) 返回的其实是一个新的、更具体的方法包装器。 原生侧入口是 JsJavaResolveOverloadSignature，它再去调 ResolveJavaMethodSignature(...)。这层不是简单字符串匹配，而是会：

```python
  - 先找实例方法，找不到再找静态方法
  - 反射收集同名候选
  - 按你传入的参数类型做匹配
  - 如果命中多个，再用 ResolveMostSpecificJavaOverload(...) 选“最具体”的那个
  - 最终返回唯一的 JNI signature 和 isStatic
```

Frida的语义和Nook基本是一样的，Java.use(...).method 先是一个 dispatcher，.overload(...) 之后才变成具体 overload wrapper。

#### implementation

implementation翻译成中文的意思就是：将计划、决策或系统付诸实施的过程。当我们在脚本写下：

```js
check.implementation = function (left, right) {
  console.log("lab:frida-0x1:hit:check:left=" + left + ":right=" + right);
  return this.check.callOriginal(left, right);
};
```

不是一个单纯的赋值过程，而是就在实施Hook：

```python
- 把这个 JS 函数登记成某个 Java 方法的替换实现
- 触发底层 Java Hook 安装
- 让后续目标方法命中时，控制流先进入脚本回调
```

在之前提到的 method wrapper 里，`makeMethod(...)` 给每个方法包装器都定义了：

```c
Object.defineProperty(method, 'implementation', {
  get() {
    return this.__nookImplementation;
  },
  set(fn) {
    if (typeof fn !== 'function') {
      throw new TypeError(...);
    }
    this.__nookJavaHookId = __nookJavaInstallImplementation(this, fn);
    this.__nookImplementation = fn;
  }
});
```

所以，执行这行代码的时候发生的是：

```python
1. 校验右边必须是函数
2. 调 `__nookJavaInstallImplementation(this, fn)`
3. 返回一个 `hookId`
4. 把这个 `hookId` 挂到当前 method wrapper 的 `__nookJavaHookId`
5. 再把 JS 函数本身保存到 `__nookImplementation`
```

这意味着 method wrapper 从这一刻开始，不只是“描述某个 Java 方法”，而是已经和一个真实安装好的 Hook 绑定起来了。

`__nookJavaInstallImplementation(...)` 背后做了什么呢？它会先从 method wrapper 上把安装 Hook 所需的元数据取出来，包括：

```python
- $className
- $methodName
- $signature
- $isStatic
- __nookJavaLoaderHandle
```

然后拼出一个`JavaJsHookRequest`：

```python
- class_name
- method_name
- signature
- loader_handle
- is_static
- deferred = true
```

其中deferred表示这次安装走的是 deferred hook 流程，也就是允许目标方法还没完全 ready 时先注册，后面再由底层时机成熟后完成接管。

随后 `JsJavaInstallImplementation` 会调用

```c
InstallJavaJsHook(request, state.java_hook_installer_dependencies, &record, &error_message)
```

如果安装成功，它还会把这个 JS 回调函数保存到当前脚本的运行时回调表里：

```c
state.java_hook_callbacks[state.current_script_id][record.hook_id] = fn
```

所以这一层做了两件事：

```python
- 把 Hook 安装到 Java Hook 子系统
- 把 JS 回调和 `hookId` 关联起来，供后续命中时回调
```

那Nook 底层 Java Hook 是怎么真正装上的呢？它的大体流程是：

1. 校验请求是否合法
2. 生成新的 `hook_id`
3. 规范化一些特殊方法名，比如把 `$init` 转成 `<init>`
4. 调具体安装逻辑
5. 把 `JavaJsHookRecord` 存进全局注册表

也就是说，`implementation = fn` 赋值最终会走到 Nook 底层已有的 Java Hook 能力，把某个类、某个方法、某个签名真正挂上。安装成功后，Nook 会得到：

```python
- installed_hook_id
- callback_slot
- hook_id
```

这些信息会一起保存在 `JavaJsHookRecord` 里，后面调用原方法、卸载 Hook、转发回调时都要用到。

那么当目标方法命中后怎么回到这段 JS呢？目标 Java 方法被调用时，底层 Java Hook 不会直接执行你写的 JS 函数。中间还会经过一层“hook id -> script callback”的分发。大体链路是：

```python
- 底层 Java Hook 命中
- 通过 callback slot 找到对应 `hook_id`
- 进入 `DispatchJavaHookInvocationToRuntime(...)`
- 在运行时里找到 `state.java_hook_callbacks[script_id][hook_id]`
- 再把参数封装成 JS 值，真正调用你写的 `implementation`
```

所以 `implementation = fn` 的本质，不只是“替换方法逻辑”，而是把：

```python
- 底层 Java Hook
- 运行时回调分发表
- 当前 method wrapper
```

这三者给串成了一条完整的调用链。

Frida这边的语义也是类似的，给某个具体overload wrapper赋implementation，本质就是在告诉`frida-java-bridge`：

```python
- 这个方法以后不要直接走原始实现
- 命中时先桥接到 JS/NativeCallback
- 在桥里再由用户脚本决定是否调用原方法
```

#### callOriginal(...)

当我们在脚本里写：

```python
return this.check.callOriginal(left, right);
```

这句的含义不是“再通过普通 Java 调用走一遍 `check`”，而是：

```python
- 在当前 Hook 回调上下文里
- 直接调用这个被 Hook 方法对应的原始实现
- 并且绕过当前这层 JS 替换逻辑，避免再次进入同一个 `implementation`
```

所以 `callOriginal(...)` 的本质不是普通方法调用，而是“从当前 Hook 上下文回到原始实现”的专用入口。Nook 是在每次 Java Hook 命中、准备进入 JS 回调时，动态构造一个当前回调专用的 receiver：

```python
1. 先为当前 `thiz` 构造一个新的 Java wrapper
2. 取出当前被 Hook 的方法对象
3. 用当前 `hook_id` 生成一个 `callOriginal` 函数
4. 把这个函数挂到方法对象上
```

`callOriginal(...)` 对应的原生入口是`JsJavaCallOriginal`，它会先从 `func_data` 里取出当前绑定的 `hook_id`，然后把 JS 参数逐个转成 `JavaJsValue`，最后调用`CallOriginalJavaJsHook(hook_id, args, arg_count, ...)`

并且`callOriginal(...)` 只能在当前Hook回调里使用，因为Nook 默认实现里，`callOriginal` 依赖的是“当前线程正在处理哪一次 Java Hook 调用”这个活动上下文。

`CallOriginalJavaJsHook(...)` 会先通过 `hook_id` 找到对应的 `JavaJsHookRecord`，然后走默认实现`DefaultCallOriginalJavaJsHook(...)`，这层会做几件关键的事：

1. 读取当前线程上的 `ActiveJavaJsInvocation`
2. 拿到当前 `installed_hook_id`
3. 确认参数个数和当前签名匹配
4. 把 JS 参数按当前 Java 签名转换成 `NookJavaHookValue`
5. 调底层：
	- `nook::java_hook_internal::CallOriginalNow(...)`
6. 把原始返回值再转回 `JavaJsValue`
7. 最后回到 JS

也就是说，真正执行原方法的是`CallOriginalNow(...)`，而不是再去走一次普通 `Java.use(...).method(...)` 调用流程，这是为了避免递归重入。

### Frida 0x2：调用静态方法

第二个例子是 frida-0x2，他的关键点是调用一个静态 Java 方法。

 ![test2](https://bbs.kanxue.com/upload/attach/202605/985628_H5HNC37FSPM2279.webp)

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0x2 -l .\tests\Test_Lab\nook-frida-labs\frida-0x2\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.frida0x2] lab:frida-0x2:match:com.ad2001.frida0x2.MainActivity
[USB Device::com.ad2001.frida0x2] lab:frida-0x2:result:invoked:get_flag(4919)
[USB Device::com.ad2001.frida0x2] lab:frida-0x2:complete
[USB Device::com.ad2001.frida0x2]->
```

首先我们简单介绍一下静态方法，以及与之相对的另一个概念实例方法在Hook中有什么不同。对 Hook 框架来说，静态方法和普通实例方法必须额外区分，根本原因在于

```python
  - 实例方法一定依赖一个对象实例，也就是 this / receiver
  - 静态方法不依赖对象，只依赖类本身
```

这会直接影响三件事：

```python
  - 定位目标方法时，不能只看方法名，因为同名方法里可能既有静态也有实例版本
  - 调用时参数组织不一样，实例方法要带 receiver，静态方法不要
  - 最终 JNI 调用入口不一样，实例方法走 Call<Type>MethodA，静态方法走 CallStatic<Type>MethodA
```

Nook做了两种判断的方案：一种情况是显式解析时，比如 .overload(...) 或列举 declared methods，这时候它会直接走 Java 反射，取 Method 的modifiers，再用 Modifier.isStatic(...) 判断，这个是最直接的静态判定。

另一种情况是像 MainActivity.get_flag(4919) 这种直接调用，没有先显式 .overload(...)。这时候 Nook 会在调用阶段综合判断：

```python
  - 当前 wrapper 有没有 receiver，也就是 receiver_handle 是否为 0
  - 按实例方法去解析签名能不能成功
```

它的策略基本是：

```python
  - 先按实例方法试
  - 如果失败，而且当前没有 receiver
  - 就再按静态方法试一次
  - 如果这次成功，就把这次调用正式认定为静态方法
```

这个题表面上不复杂，核心是找到目标类，然后直接调用静态方法 `MainActivity.get_flag(4919)`。

Hook代码也很短：

```js
Java.perform(function(){
    var MainActivity = Java.use("com.ad2001.frida0x2.MainActivity");
    MainActivity.get_flag(4919);
});
```

但它验证的是另一个很关键的能力：**脚本运行时是不是一个可操作的 Java 对象环境**。

如果 Nook 只是 Hook 框架，那它擅长的是“拦截某个现有执行路径”；但 Frida-like 工具还得支持另一种分析方式：**不等程序自己走到那里，而是脚本主动去调用。**

所以这个例子验证的重点，不只是“Java.use 能不能找到类”，而是：

- 找到类之后能不能像 Frida 一样直接调静态方法
- attach 到一个已经启动的进程之后，脚本能不能马上介入

在上一个例子中我们已经知道了Java.use会返回一个Js Wrapper，而`MainActivity.get_flag(4919)`实际调的是 method wrapper,这个 wrapper 是makeMethod(...) 生成的，函数体最终会走到： `__nookJavaInvoke(...)`。

 JsJavaInvoke 主要做这几件事：

```python
  - 从 method wrapper 上取出方法元数据
  - 把 4919 这样的 JS 参数转成 JavaJsValue
  - 如果当前方法还没明确签名，就自动做一次重载解析
  - 最后调用 InvokeJavaMethod(...)
```

而类包装器wrapper上的方法其实并不是一开始就是静态的，Nook是在真正调用的那一刻才动态的把它收敛为静态调用，最后JNI层再明确分到 `CallStatic*MethodA` 这条路径。

在这个例子中，Java.use("com.ad2001.frida0x2.MainActivity") 返回的是类 wrapper。这个 wrapper 的receiverHandle 本身就是 0x0，因为它不是某个实例对象。随后你第一次访问：MainActivity.get_flag，js_runtime默认会生成makeMethod(canonicalMethodName, undefined, undefined, false)，false意思就是这个 method wrapper 一开始默认并没有被认定为静态方法，真正关键发生在你执行MainActivity.get_flag(4919) 的时候。此时会进入 JsJavaInvoke。它先从 method wrapper 里解析出：

```python
  - class_name = MainActivity
  - method_name = get_flag
  - signature = ""
  - is_static = false
  - receiver_handle = 0
```

它表面还像个“未定的实例方法包装器”，但又没有 receiver，因为是在类 wrapper 上调的，于是 JsJavaInvoke 会先按当前记录去做一次重载解析。如果失败，并且发现：

```python
  - receiver_handle == 0
  - record.is_static == false
```

它就会走一个静态回退分支，大意就是：

```python
  static_record.is_static = true;
  再按静态方法解析一次
```

如果这次成功，就把当前 record 正式翻成静态方法。也就是说，Nook 的策略不是“类 wrapper 上的所有方法先天就标成静态”，而是：

```python
  - 先给你统一的方法访问体验
  - 再在调用阶段根据上下文自动判断这是实例调用还是静态调用
```

然后尝试签名解析，直到收敛到目标方法，比如这里的 get_flag(int)，等这些都定下来之后，才会进DefaultInvokeJavaMethod(...)。这里才是真正的JNI 分叉点：

```python
  - 如果 record.is_static == true，走 CallStaticIntMethodA / CallStaticObjectMethodA / CallStaticVoidMethodA
  - 如果不是静态，走 CallIntMethodA / CallObjectMethodA / CallVoidMethodA
```

### Frida 0x3：修改静态字段

第三个例子是 `frida-0x3`，这里要做的事情很简单：修改静态字段 `Checker.code`，让后续逻辑进入正确分支。

 ![test3](https://bbs.kanxue.com/upload/attach/202605/985628_AW8JDQGU2BRGY4X.webp)

这个案例对应的是 Frida Java API 里非常常见的一类操作：**字段读写**。

方法 Hook 和字段修改其实是两种不同的能力边界：

- 方法 Hook 更偏“替换行为”
- 字段修改更偏“篡改状态”

Hook效果如下：

```python
(nook) C:\Users\n1ng>nook-cli -U -f com.ad2001.frida0x3 -l E:\Learn\my_program\all_my_hook\kanxue\Nook\tests\Test_Lab\nook-frida-labs\frida-0x3\script.js
27042

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[*] Resuming pid 17848...
[+] Process resumed
lab:frida-0x3:result:code-before=0:code-after=512
[USB Device::com.ad2001.frida0x3] [script.js]-> lab:frida-0x3:installed
```

Hook代码也很简单：

```python
Java.perform(function () {
  var Checker = Java.use("com.ad2001.frida0x3.Checker");
  var before = Checker.code.value;
  Checker.code.value = 512;
  console.log("lab:frida-0x3:result:code-before=" + before + ":code-after=" + Checker.code.value);
  console.log("lab:frida-0x3:installed");
});
```

在Nook中，Java字段也是通过暴露成一个字段包装器，然后通过`.value`去读写真实字段值，`Checker.code.value`背后的含义是：Checker.code先得到也给JavaField Wrapper，再通过这个wrapper的`getvalue()/set value(...)`去触发真实的字段读写，那字段又是怎么被包装出来的呢？在`CreateJavaUseWrapper`生成的Proxy里，当脚本访问`Checker.code`时，Nook会先走`__nookJavaResolveField(className, fieldName, isStaticGuess, loaderHandle)`，如果字段存在，就调用`makeField(fieldName, signature, isStatic)`生成一个字段包装器：

```python
{
  $className,
  $fieldName,
  $signature,
  $isStatic,
  __nookJavaReceiverHandle,
  __nookJavaLoaderHandle,
  get value() { return __nookJavaReadField(this); },
  set value(nextValue) { __nookJavaWriteField(this, nextValue); }
}
```

判断`code`是否为静态字段的方法是：Nook 在字段解析时会先看当前 wrapper 有没有 receiver。类 wrapper 的 receiverHandle 是0x0，所以访问 Checker.code 时，会先按“静态字段”去解析，底层再通过反射和 Modifier.isStatic(...) 确认它确实是静态字段。最后这个字段会被收敛成：

```python
  - 类 com.ad2001.frida0x3.Checker
  - 字段 code
  - 签名 I
  - isStatic = true
```

读字段时，`Checker.code.value` 会进 `__nookJavaReadField(...)`，原生入口是 `JsJavaReadField`，最终在`DefaultReadJavaField(...)` 里，如果是静态 int，就走 JNI 的`GetStaticIntField(...)`。

写字段时，`Checker.code.value = 512` 会进 `__nookJavaWriteField(...)`，原生入口是 `JsJavaWriteField`，最后在`DefaultWriteJavaField(...)` 里按字段类型和静态属性分叉。这里因为它是 static int，最终走的是`SetStaticIntField(...)`。

Frida的做法则不是等到真正调用或访问时才去猜“这个成员是不是静态”，，而是在建模阶段就已经把“字段/方法”和“静态/实例”分开编码了：

```python
  - 方法成员会被编码成 m:<type>0x...
  - 字段成员会被编码成 f:<type>0x...
```

当在Frida中写`Check.code`时：

```python
  - 先走 Proxy 的 get
  - 再通过 $find(property) 去成员模型里找
  - 找到后再把它 unwrap 成脚本侧成员对象
```

### Frida 0x4：构造对象并调用实例方法

第四个例子是 `frida-0x4`，他的核心是创建一个java对象实例，然后调用这个对象的实例方法。

这个例子验证的是 Frida 风格 Java 对象编程里更进一步的一层：**脚本能不能像操作普通对象一样去操作目标 App 的 Java 实例。**

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0x4 -l .\tests\Test_Lab\nook-frida-labs\frida-0x4\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.frida0x4] lab:frida-0x4:instance:com.ad2001.frida0x4.Check
[USB Device::com.ad2001.frida0x4]->
[USB Device::com.ad2001.frida0x4] lab:frida-0x4:result:FRIDA{XORED_INSTANCE}
```

Hook代码：

```python
Java.perform(function () {
  var Check = Java.use("com.ad2001.frida0x4.Check");
  var instance = Check.$new();
  var flag = instance.get_flag(1337);
  console.log("lab:frida-0x4:instance:" + instance.$className);
  console.log("lab:frida-0x4:result:" + String(flag));
});
```

核心分两步走，首先是`Check.$new`创建Java对象的实例，Nook在是怎么做的呢？

```python
$new: function () {
  const args = Array.prototype.slice.call(arguments);
  const constructorTarget = {
    $className: className,
    $methodName: '<init>',
    $signature: ...,
    $isStatic: false,
    __jptr: '0x0',
    __nookJavaReceiverHandle: '0x0',
    __nookJavaLoaderHandle: loaderHandle
  };
  return __nookJavaInvoke.apply(null, [constructorTarget].concat(args));
}
```

`$new`在Nook中还是被统一在了Java 调用桥中，在js_runtime里类wrapper自带一个`$new`，他会先构造一个假的method target：

```python
  - $methodName = "<init>"
  - $isStatic = false
  - __nookJavaReceiverHandle = "0x0"
```

然后直接丢给 `__nookJavaInvoke(...)`。也就是说，Nook 把“构造对象”也当成一种特殊的 Java 方法调用来处理，目标就是构造函数`<init>`。后面到了 `DefaultInvokeJavaMethod(...)`，它会先判断当前方法是不是构造函数，如果是，就走构造分支：

```python
  - ResolveJavaClass(...)
  - GetMethodID(clazz, "<init>", signature)
  - 把 JS 参数转成 JNI 参数
  - 调 env->NewObjectA(...)
  - 再 NewGlobalRef(instance) 持有对象
```

所以 $new() 最后真的是走 JNI NewObjectA(...) 把 Java 对象构造出来，并且返回给脚本的不是裸 jobject，而是一个新的对象 wrapper。JsJavaInvoke 看到返回值是 Java object 后，会再调用`CreateJavaUseWrapper(...)`，但这次传进去的 receiverHandle 不再是 0x0，而是刚创建好的那个对象句柄。于是：

```python
  - 类 wrapper 变成了对象 wrapper
  - 后面 instance.get_flag 再解析时，会自动带上真实 receiver
  - 这时调用链天然就是实例方法语义，不需要再像静态方法那样靠 receiver == 0 去猜
```

当脚本继续执行：

```python
var flag = instance.get_flag(1337);
```

此时 `instance` 已经不是类 wrapper，而是对象 wrapper。所以后面 Proxy 再创建 `get_flag` 这个 method wrapper 时，会把真实对象句柄带进去，这时 `JsJavaInvoke` 再去调用这个方法，就天然会按实例方法那条路径走。

### Frida 0x5：找到现有实例再调用方法

第五个例子是 `frida-0x5`。

这个题的重点不是自己 new 一个对象，而是找到当前进程里已经存在的 `MainActivity` 实例，然后在这个 live instance 上调用 方法

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0x5 -l .\tests\Test_Lab\nook-frida-labs\frida-0x5\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.frida0x5] lab:frida-0x5:match:com.ad2001.frida0x5.MainActivity
[USB Device::com.ad2001.frida0x5]->
[USB Device::com.ad2001.frida0x5] lab:frida-0x5:result:invoked:flag(1337)
[USB Device::com.ad2001.frida0x5] lab:frida-0x5:complete
```

Hook代码：

```js
Java.performNow(function () {
  var fired = false;

  Java.choose("com.ad2001.frida0x5.MainActivity", {
    onMatch: function (instance) {
      if (fired) {
        return;
      }
      fired = true;
      console.log("lab:frida-0x5:match:" + instance.$className);
      instance.flag(1337);
      console.log("lab:frida-0x5:result:invoked:flag(1337)");
    },
    onComplete: function () {
      console.log("lab:frida-0x5:complete");
    }
  });
});
```

这里有两点和之前不同，一个是Java.performNow(function(...))，一个是Java.choose(...)\

#### Java.performNow(...)

为什么这里需要用`Java.performNow(...)`？其实是在表达一种不同的时机语义。Nook的Js runtime里面他们是这样被定义的：

```js
Java.performNow = function (fn) {
  return Java.vm.perform(fn);
};

Java.perform = function (fn) {
  if (Java._isClassLoaderReady()) {
    return Java.vm.perform(fn);
  }
  return Java.ready(function () {
    return Java.vm.perform(fn);
  });
};
```

也就是说`Java.performNow(fn)`只保证当前前程进入`Java.vm.perform(fn)`，不会额外等待ClassLoader ready，不会走ready callback队列。

#### Java.choose(...)

和上一个例子中自己构造一个Java对象然后调用实例方法不同，这里是直接去VM中找系统已经创建好的一个`MainActivity`，因为Activity这种Android组件不是普通类，不能简单的$new就指望它处于一个有效状态里，它依赖生命周期、上下文、主线程、系统管理等，所以这里需要用Java.choose(...)去找现成的实例，而不是自己new。

Nook 里 Java.choose(...)会做三件事：

```python
  - 读类名和 onMatch/onComplete
  - 调 EnumerateJavaObjects(...)
  - 把每个命中的对象包装成脚本实例，逐个回调 onMatch
```

默认实现最终落到DefaultEnumerateJavaObjects(...)。这里不是自己维护对象表，而是直接用`dalvik.system.VMDebug.getInstancesOfClasses(...)`，然后把这些对象转成全局引用，再包装成对象 wrapper 交给脚本。大致流程是：

```python
1. `FindClass` 找到目标类
2. 找到 `dalvik.system.VMDebug`
3. 拿到：
   - `getInstancesOfClasses([Ljava/lang/Class;Z)[[Ljava/lang/Object;`
4. 构造只包含目标类的 `Class[]`
5. 调 `VMDebug.getInstancesOfClasses(...)`
6. 遍历返回的对象数组
7. 把每个命中的实例都转成全局引用
8. 再描述其 className，封装成 `JavaJsValue`
```

所以 onMatch(instance) 里的 instance 不是一个简单句柄，而是一个真正的对象 wrapper。它带着真实 receiverHandle，因此后面可以直接`instance.flag(1337)`

### Frida 0x6：构造对象参数并传入

第六个例子是 `frida-0x6`，这个案例的核心是`给Java方法传入一个对象参数`。

Hook效果：

Hook代码：

```js
Java.performNow(function () {
  var Checker = Java.use("com.ad2001.frida0x6.Checker");
  var fired = false;

  Java.choose("com.ad2001.frida0x6.MainActivity", {
    onMatch: function (instance) {
      if (fired) {
        return;
      }
      fired = true;
      var checker = Checker.$new();
      checker.num1.value = 1234;
      checker.num2.value = 4321;
      console.log("lab:frida-0x6:match:" + instance.$className);
      console.log("lab:frida-0x6:checker:num1=" + checker.num1.value + ":num2=" + checker.num2.value);
      instance.get_flag(checker);
      console.log("lab:frida-0x6:result:invoked:get_flag(checker)");
    },
    onComplete: function () {
      console.log("lab:frida-0x6:complete");
    }
  });
});
```

它比前一个例子再进一层。这里不仅要找到现有实例，还要：

```python
- 构造 `Checker` 对象
- 给它填入需要的字段值
- 再把它作为参数传给 `MainActivity.get_flag(checker)`
```

核心代码是：

```python
var checker = Checker.$new();
instance.get_flag(checker);
```

首先是`$new`，这个在上面的例子中做过了介绍，会返回一个`Java Checker对象Wrapper`，然后当我们将其作为参数传递给`instance.get_flag(checker)`时，Nook需要回答两个问题：1.这个JS值是不是一个Java 对象；2.如果是，它内部对应的`jobject/handle`是什么。

这一步首先发生在`ParseJavaJsValue(...)`，当它看到传进来的 JS 值是一个对象时，会检查这个对象上有没有`__nookJavaReceiverHandle`，如果没有，再看`__jptr`，只要能从这两个属性里取到有效句柄，就会把它解析成`JavaJsValueKind::kObject`，并记录`object_handle`，`object_class_name`，所以它内部是真实包含着Java对象句柄的。

当 `instance.get_flag(checker)` 进入 `JsJavaInvoke` 之后，参数会先都被解析成 `JavaJsValue`。此时 `checker` 这个参数已经是`kind = kObject`，`object_handle = <Checker 实例句柄>`。

随后在真正发起 Java 调用前，Nook 会根据目标方法签名，对每个参数执行`ConvertJavaJsValueToNookJavaHookValue(...)`

对于对象参数，这层会把`value.object_handle`直接转换成`jobject`也就是`out_value->l = reinterpret_cast<jobject>(value.object_handle);`

这一步意味着脚本侧传进去的不是“某种序列化后的对象描述”，而是直接把对应 Java 对象实例本身传回给了目标方法。

把整题串起来，其实就是下面这条链：

```python
1. `Java.choose(...)` 找到活着的 `MainActivity`
2. `Checker.$new()` 构造一个新的 `Checker`
3. `checker.num1.value = 1234`
4. `checker.num2.value = 4321`
5. `instance.get_flag(checker)` 进入实例方法调用
6. `checker` 被 `ParseJavaJsValue(...)` 识别成 Java 对象参数
7. `ConvertJavaJsValueToNookJavaHookValue(...)` 把它转成 JNI `jobject`
8. `MainActivity.get_flag(Checker)` 真正收到这个对象实例
9. Java 侧检查：
   - `A.num1 == 1234`
   - `A.num2 == 4321`
10. 条件成立，继续执行 flag 逻辑
```

### Frida 0x7：Hook 构造函数

第七个例子是 `frida-0x7`，这里的重点是构造函数路径，也就是在对象创建时就把逻辑改掉，让后续条件天然成立。

构造函数 Hook 一直都是 Frida Java 能力里很有代表性的一类场景。因为它意味着你不只是“在对象已经存在后动手”，而是可以在对象诞生那一刻就介入。

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U -f com.ad2001.frida0x7 -l .\tests\Test_Lab\nook-frida-labs\frida-0x7\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[*] Resuming pid 29265...
[+] Process resumed
[USB Device::com.ad2001.frida0x7]->
[USB Device::com.ad2001.frida0x7] lab:frida-0x7:ctor-hit:123:321
[USB Device::com.ad2001.frida0x7] lab:frida-0x7:ctor-rewrite:num1=600:num2=600
```

Hook代码：

```js
Java.perform(function () {
  var Checker = Java.use("com.ad2001.frida0x7.Checker");
  var init = Checker.$init.overload("int", "int");

  init.implementation = function (num1, num2) {
    console.log("lab:frida-0x7:ctor-hit:" + String(num1) + ":" + String(num2));
    console.log("lab:frida-0x7:ctor-rewrite:num1=600:num2=600");
    return init.call(this, 600, 600);
  };
});
```

代码的核心就是`Checker.$init.implementation和this.$init(600, 600);`，它的语义就是：在当前hook回调上下文中调用原始构造函数实现并修改参数。

Nook中发挥了作用的是`callOriginal`，构造函数命中时，Nook 会给当前回调 receiver 上挂一个专用的 `callOriginal` 入口，对构造函数来说，`$init(...)` 在脚本层就是这个原始构造逻辑的入口映射。所以 Nook 里 `Checker.$init.implementation` 这条链本质上还是走前面同一套 Java Hook 安装流程，只不过目标方法变成了 `<init>`。

### Frida 0x8：Native Hook 入门

前面几个例子基本都在 Java 层，到了 `frida-0x8`，重点开始转向 Native。

这个题的核心是 Hook Native 比较逻辑，把参与比较的 secret 内容观察出来。

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0x8 -l .\tests\Test_Lab\nook-frida-labs\frida-0x8\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.frida0x8] lab:frida-0x8:installed:target=0x797fd683c0
[USB Device::com.ad2001.frida0x8]->
[USB Device::com.ad2001.frida0x8] lab:frida-0x8:hit:input=Hello:secret=FRIDA{NATIVE_LAND}
```

Hook代码：

```js
(function () {
  var strcmpAdr = Module.getExportByName("libc.so", "strcmp");
  console.log("lab:frida-0x8:installed:target=" + String(strcmpAdr));

  Interceptor.attach(strcmpAdr, {
    onEnter: function (args) {
      try {
        if (args[0].isNull() || args[1].isNull()) {
          return;
        }

        var left = args[0].readCString();
        var right = args[1].readCString();
        if (left.indexOf("Hello") !== -1) {
          console.log("lab:frida-0x8:hit:input=" + left + ":secret=" + right);
        }
      } catch (error) {
        console.log("lab:frida-0x8:error:" + String(error));
      }
    }
  });
})();
```

这里的Hook对象选择的是libc中的`strcmp`函数，代码核心首先是`Module.getExportByName("libc.so", "strcmp")`，这句代码的含义是去`libc.so`的导出表里找`strcmp`，直接拿到它的运行地址，Frida中常见的几种拿地址的方式有：

```python
- `Module.enumerateExports()`
- `Module.getExportByName()`
- `Module.findExportByName()`
- `Module.getBaseAddress() + offset`
- `Module.enumerateImports()`
```

Nook对`Module.getExportByName(...)`背后的实现其实很简单：

```python
1. 解析 JS 传进来的：
   - `module_name`
   - `symbol_name`
2. 调：
   - `FindNativeJsExportByName(module_name, symbol_name, &target_address, ...)`
3. 如果成功，就用：
   - `MakeNativePointer(ctx, target_address)`
     返回给脚本
```

Frida的做法也是类似的，不过他是由gumjs暴露Module API，底层由gum去做模块/符号解析。

然后是`Interceptor.attach(strcmpAdr,...)`，这句代码的含义是在目标函数地址入口打上Hook，函数每次被调用的时候先进入`onEnter`从而执行我们的逻辑。

大致流程是：

```python
- `JsInterceptorAttach`
1. 读取 callbacks 对象里的：
   - `onEnter`
   - `onLeave`
2. 解析 hook target
   可以是：
   - 直接传进来的 pointer
   - 或者模块名 + 符号名这种目标描述
3. 组装一个 `NativeJsHookRequest`
4. 调：
   - `InstallNativeHookForCurrentScript(...)`
5. 再进一步落到：
   - `InstallNativeJsHook(...)`
```

所以Nook的`Interceptor.attach(...)`本质就是在安装一个inline hook，安装成功后把

```python
- `hook_id`
- `target_address`
- `module_name`
- `symbol_name`
- `snapshots`
- `hook_handle`
```

这些信息记进 native hook 注册表。 后面函数命中时，再根据 `hook_id` 回调到当前脚本注册的 `onEnter/onLeave`。

#### 对strcmp这种基础高频函数的处理

这里还有一个问题就是对于`strcmp`这类高频的基础函数，一旦Hook引擎热路径中有多余的开销，它会被`strcmp`这种函数成百上千的放大，一开始Nook的做法就是简单的：

```python
1. 命中 trampoline
2. 进 `DispatchInlineHookSlot(...)`
3. 取 slot / hook 信息
4. 构造 `HookEvent`
5. 同步进入 QuickJS 执行 `onEnter`
6. 调原函数
7. 再同步进入 QuickJS 执行 `onLeave`
```

对于 `strcmp` 这种高频函数：

```python
- 每一次 `strcmp`
- 都会完整走一遍 Hook 分发
- 而 JS callback 内部、日志、字符串处理、运行时辅助逻辑，又很可能继续触发新的 `strcmp`
```

于是很容易出现两类放大：

```python
1. 高频同步跨语言调用放大
   一次普通 `strcmp`，被放大成：
   - native hook 分发
   - JS runtime 进入
   - callback 执行
   - 再回 native
   - leave 阶段再来一次

2. 重入递归放大
   如果 JS callback 或 runtime 内部又间接调用到 `strcmp`，
   那么原本只是“正在处理 `strcmp` Hook”，会再次命中同一个 Hook。
```

这时用户看到的外部现象就是：

```python
- 明显卡顿
- UI 发僵
- 某些场景下甚至像“白屏”或“冻住几秒”
```

Nook的做法主要有三点：

首先是当前线程递归保护，直接 bypass 到 original，在 `DispatchInlineHookSlot(...)` 开头先判断：

```python
if (GetNativeJsInlineHookThreadState().dispatch_depth > 0u ||
    IsNativeJsInlineHookIgnoredOnCurrentThread()) {
    if (slot.original_function != nullptr) {
        return original(...);
    }
    return 0;
}
```

- 如果当前线程已经在执行 hook 分发
- 或者当前线程被显式标记为忽略 hook
- 那么这次命中不再进 JS
- 直接跳 original

这样就挡住 JS callback 内部再次触发 `strcmp` 的重入，也能挡住 runtime/日志/字符串辅助逻辑造成的二次命中。

第二就是进入 JS callback 前，临时把当前线程标记为 ignore。现在代码里有：

```python
- `PushNativeJsInlineHookIgnore()`
- `PopNativeJsInlineHookIgnore()`
- `ScopedNativeJsInlineHookIgnore`
```

并且在真正同步调用 JS callback 之前，会这样包一层：

```cpp
ScopedNativeJsInlineHookIgnore ignore_scope;
JsRuntime::InvokeNativeHookCallbackSync(...)
```

enter 和 leave 两边都这样做了。

这意味着：

```python
- 一旦开始执行当前 Hook 的 JS callback
- 当前线程的 `ignore_level` 就会先加 1
- callback 期间如果又撞到 `strcmp`
- 直接走 bypass，不再继续进 JS
```

第三点是把热路径上的 slot 读取改成 runtime snapshot，早期每次触发都去锁表、读 slot、拼装状态，现在 Nook在 `ActivateInlineHookSlot(...)` 里，安装 hook 成功后会把热路径需要的最小信息整理到：

```python
- `slot_runtime_snapshots`
- `slot_runtime_in_use`

std::array<std::atomic<bool>, kMaxNativeJsInlineHookSlots> slot_runtime_in_use = {};
std::array<NativeJsInlineHookRuntimeSnapshot, kMaxNativeJsInlineHookSlots> slot_runtime_snapshots = {};
```

而 `DispatchInlineHookSlot(...)` 走的是：`GetInlineHookRuntimeSnapshot(...)`，这条路径只用原子位判断 slot 是否可用，再读预先整理好的 runtime snapshot。

Frida 在这件事上更成熟，在 `frida-gum/gum/guminterceptor.c` 里，`_gum_function_context_begin_invocation(...)` 一进来就先做：

1. `gum_interceptor_guard_key` 检查
2. `ignore_level` 检查
3. 决定这次是否真的要 `invoke_listeners`
4. 如果不需要，直接 `goto bypass`

然后 Frida 还有明确的每线程忽略计数：

```c
gum_interceptor_ignore_current_thread(...)
gum_interceptor_unignore_current_thread(...)
```

后面Nook会慢慢补充优化上来。

### Frida 0x9：修改 Native 返回值

第九个例子frida-0x9，和上一个例子相比，这里不只是观察，而是直接修改 Native 函数返回值，让 `check_flag()` 强制返回正确结果。

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.a0x9 -l .\tests\Test_Lab\nook-frida-labs\frida-0x9\script3.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script3.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.a0x9] lab:frida-0x9:installed:target=0x78ede2c614
[USB Device::com.ad2001.a0x9]->
[USB Device::com.ad2001.a0x9] lab:frida-0x9:hit:original-ret=0x1
[USB Device::com.ad2001.a0x9] lab:frida-0x9:result:forced-ret=1337
```

Hook代码：

```python
(function () {
  var target = Module.getExportByName(
    "liba0x9.so",
    "Java_com_ad2001_a0x9_MainActivity_check_1flag"
  );

  console.log("lab:frida-0x9:installed:target=" + String(target));

  Interceptor.attach(target, {
    onLeave: function (retval) {
      console.log("lab:frida-0x9:hit:original-ret=" + String(retval));
      retval.replace(1337);
      console.log("lab:frida-0x9:result:forced-ret=1337");
    }
  });
})();
```

这个脚本的完整含义是：

```python
- 找到 JNI 导出符号 Java_com_ad2001_a0x9_MainActivity_check_1flag
- 用 Interceptor.attach(...) 挂上去
- 在 onLeave 里调用 retval.replace(1337)
```

和上一个例子不同，这里需要hook的不是通用的libc函数，而是JNI导出的真正目标函数，这里的关键代码是`retval.replace(1337);`，`retval`并不只是一个普通的JS number，在Nook中，leave回调收到的是一个返回值包装对象wrapper，在js_runtime里面Nook会专门构造这个返回值对象：

```python
- 先把当前原始返回值包装成一个 NativePointer 风格对象
- 再在这个对象上挂一个：
  - `replace(...)`
```

也就是说`retval`既能被打印、读取值，也能通过`replace()`把底层返回值标记为"需要覆盖"。

Nook这部分的实现可以分为两层：

```python
1. JS runtime 层
   为 `onLeave` 构造一个带 `replace()` 的返回值 wrapper
2. Native dispatch 层
   在 leave callback 返回后，检查脚本有没有提交“返回值覆盖”
```

leave回调结束后，修改后的返回值又是怎么生效的呢？Nook 的 inline hook dispatch 流程大致是：

```python
1. 进入 hook
2. 先跑 `onEnter`
3. 调原始函数，拿到 `return_value`
4. 构造 leave 事件
5. 跑 `onLeave`
6. 如果脚本在 `onLeave` 里提交了返回值覆盖
7. 就把 `return_value` 改成覆盖后的值
8. 最后把这个新值返回给原始调用方
```

```python
if (leave_result.has_return_value_override) {
    return_value = leave_result.return_value;
}
```

### Frida 0xA：主动调用 Native 函数

第十个例子`frida-0xA`这次的重点不是拦截，而是主动调用一个 Native 函数，也就是脚本层的 `NativeFunction` 能力。

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0xa -l .\tests\Test_Lab\nook-frida-labs\frida-0xA\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 2)
[USB Device::com.ad2001.frida0xa] libfrida0xa.so found at: 0x78edd2d000
[USB Device::com.ad2001.frida0xa]->
[USB Device::com.ad2001.frida0xa] Success! Function address: 0x78edd4ad60
[USB Device::com.ad2001.frida0xa] Done. Check Logcat for the 'Decrypted Flag' message.
```

Hook代码：

```js
(function () {
  var seen = false;

  function invoke(base) {
    if (seen) {
      return;
    }
    seen = true;
    console.log("libfrida0xa.so found at: " + base);
    try {
      var adr = base.add(0x1DD60);
      console.log("Success! Function address: " + adr);
      var get_flag = new NativeFunction(adr, "void", ["int", "int"]);
      get_flag(1, 2);
      console.log("Done. Check Logcat for the 'Decrypted Flag' message.");
    } catch (error) {
      seen = false;
      console.log("Invocation failed: " + String(error));
    }
  }

  var existing = Process.findModuleByName("libfrida0xa.so");
  if (existing !== null) {
    invoke(existing.base);
    return;
  }

  Process.attachModuleObserver({
    onAdded: function (module) {
      if (module.name === "libfrida0xa.so") {
        invoke(module.base);
      }
    }
  });
})();
```

hook代码的含义是：

```python
找到 libfrida0xa.so 的基址
计算出 get_flag 偏移
构造 NativePointer
构造 NativeFunction
调用 get_flag(1, 2)
```

核心代码就是首先是`*var* get_flag = new NativeFunction(getFlagAddr, "void", ["int", "int"])`，把一个Native地址包装成了JS里可以调用的函数对象，Nook 会做这几件事：

```python
1. 解析第一个参数 `addr`
   - 必须是一个非 0 指针
2. 解析第二个参数 `returnType`
   - 这里是 `"void"`
3. 解析第三个参数 `argTypes`
   - 这里是 `["int", "int"]`
4. 调 `CreateNativeFunctionValue(...)`
   - 生成一个“看起来像 JS 函数，但内部带着 Native 调用元数据”的对象
```

所以 `NativeFunction` 的本质不是“立刻调用一次”，而是：

```python
- 创建一个 callable JS object
- 并把目标地址、返回类型、参数类型挂在这个对象身上
```

那它又是怎么变成一个可调用函数对象的呢？核心在`CreateNativeFunctionValue(...)`

它做了两层事：

```python
1. 用 `JS_NewCFunctionData(...)` 创建一个 JS 可调用对象
   - 真正被调用时会落到 `JsNativeFunctionInvoke(...)`
2. 把元数据挂到这个函数对象上
   - target address
   - return type
   - arg types
```

也就是说，脚本里拿到的 `get_flag` 虽然看起来像普通 JS 函数：

```js
get_flag(1, 2)
```

但实际上它背后是一个“带闭包数据的宿主函数”：

```python
- 代码入口固定是 `JsNativeFunctionInvoke(...)`
- 真正调用谁，由构造时保存下来的地址元数据决定
```

这点和 Java 侧的 method wrapper 思路很像。

然后当真正调用`get_flag(1,2)`时，会进入`JsNativeFunctionInvoke(...)`，它的执行流程可以概括成：

```python
1. 先从函数对象的闭包数据里取出：
   - `target_address`
   - `return_type`
   - `expected_argc`
   - `arg_types`
2. 检查传入参数个数是否匹配
3. 逐个参数调用 `ParseJsNativeCallValue(...)`
   - 把 JS 值转成 Native 可调用的内部表示 `NativeCallValue`
4. 如果目标地址其实对应的是 Nook 注册过的 `NativeCallback` 或 replace hook
   - 先走回调/替换逻辑
5. 否则走真正的原生函数调度：
   - `DispatchTypedNativeFunction(...)`
6. 把返回值再转回 JS：
   - `NativeCallValueToJs(...)`
```

`DispatchTypedNativeFunction(...)`负责的是Nook底层如何真正去call这个native函数，`DispatchTypedNativeFunction(...)` 会先判断：

```python
- 返回值是否用了浮点 ABI
- 参数里是否有 `float` / `double`
```

如果没有浮点类型，它会走比较直接的 raw 调用路径：

```python
- `CallNativeFunctionRawVoid(...)`
- `CallNativeFunctionRawU64(...)`
```

本质上就是把目标地址强转成函数指针，然后调用。

但如果涉及浮点参数或浮点返回值，由于

```python
- 浮点参数和整数参数在 ABI 层可能走不同寄存器
- 返回值位置也可能不同
```

所以 Nook 又提供了另一层 typed dispatch：

```python
- `DispatchTypedNativeFunctionWithAbi(...)`
- `InvokeTypedNativeFunction0/1/2(...)`
- `DispatchTypedNativeFunction1(...)`
- `DispatchTypedNativeFunction2(...)`
```

它会根据参数类型组合，挑出合适的函数签名去调。

然后`Process.attachModuleObserver(...)`监听模块加载时机，确保地址可用后再主动call。

Nook 里 `Process.findModuleByName(...)` 是怎么做的呢？

```python
- `JsProcessFindModuleByName(...)`

它的流程很直接：

1. 从 JS 拿到模块名字符串
2. 调 `CollectLoadedNativeModules(...)` 枚举当前进程已加载模块
3. 用 `FindLoadedModuleByName(...)` 按名字匹配
4. 找到就 `MakeModuleObject(...)` 包成 JS `module` 对象返回
5. 找不到就返回 `null`
```

`Process.attachModuleObserver(...)` 呢？

```python
- `JsProcessAttachModuleObserver(...)`

它做的事情可以理解成“给当前脚本注册一组模块事件回调”。

主要流程是：

1. 校验参数必须是对象
2. 取出其中的 `onAdded` / `onRemoved`
3. 要求至少有一个是函数
4. 以 `current_script_id` 为 key，存入 `state.module_observers`
```

注册完成后，如果提供了 `onAdded`，它会立刻：

```python
1. 再次 `CollectLoadedNativeModules(...)`
2. 枚举当前已经加载的所有模块
3. 对每个模块都主动调用一次 `onAdded(module)`
```

Native侧模块加载后，Nook这边最终会走`NotifyModuleObserverModuleLoaded(const char* module_path, ...)`

它做的事情是：

```python
1. 取出当前所有 `module_observers`
2. 再次枚举已加载模块
3. 根据 `module_path` 找到对应的 `NativeModuleRecord`
4. 调 `EnqueueModuleEventLocked(...)`
```

并且这里并不是在任意Native线程里直接硬调JS回调，而是先把模块事件排入运行时列表，再由JS runtime在安全上下文里分发给脚本。

### Frida 0xB：指令 Patch

最后一个例子是 `frida-0xB`，这个案例的核心不再是去Hook某个函数或者主动调用函数，而是直接把目标 so 里的某条机器指令改掉，从而修改控制流。

Hook效果：

```python
E:\Learn\my_program\all_my_hook\kanxue\Nook>nook-cli -U com.ad2001.frida0xb -l .\tests\Test_Lab\nook-frida-labs\frida-0xB\script.js

    _   __            __
   / | / /___  ____  / /__
  /  |/ / __ \/ __ \/ //_/
 / /|  / /_/ / /_/ / ,<
/_/ |_/\____/\____/_/|_|  v0.1.1

 Dynamic instrumentation toolkit for Android

[*] Waiting for agent runtime ready...
[*] Loading 'script.js'...
[+] Script loaded (id: 1)
[USB Device::com.ad2001.frida0xb] lab:frida-0xB:note:arm64-memory-patch-path
[USB Device::com.ad2001.frida0xb]->
[USB Device::com.ad2001.frida0xb] lab:frida-0xB:result:patched=0x78ede57248:size=4
```

Hook代码：

```js
(function () {
  var patched = false;

  function patchModule(module) {
    if (patched) {
      return;
    }
    patched = true;

    var branch = module.base.add(0x15248);
    console.log("lab:frida-0xB:note:arm64-memory-patch-path");

    Memory.patchCode(branch, 4, function (code, size) {
      code.writeByteArray([0x1f, 0x20, 0x03, 0xd5]);
      console.log("lab:frida-0xB:result:patched=" + String(branch) + ":size=" + size);
    });
  }

  var existing = Process.findModuleByName("libfrida0xb.so");
  if (existing !== null) {
    patchModule(existing);
    return;
  }

  Process.attachModuleObserver({
    onAdded: function (module) {
      if (module.name === "libfrida0xb.so") {
        patchModule(module);
      }
    },
    onRemoved: function (_module) {}
  });

  console.log("lab:frida-0xB:waiting:module-not-ready");
})();
```

这里代码看着长，其实核心就这一小段：

```js
Memory.patchCode(branch, 4, function (code, size) {
      code.writeByteArray([0x1f, 0x20, 0x03, 0xd5]);
      console.log("lab:frida-0xB:result:patched=" + String(branch) + ":size=" + size);
    });
  }
```

这里写进去的 `1f 20 03 d5`，在 ARM64 上就是一条`NOP`，也就是说，这题的本质是把 `b.ne` 那条条件跳转指令覆盖掉，让他执行后续的解码逻辑。

Nook 对这个 API 的实现入口是`JsMemoryPatchCode(...)`

这个函数的语义其实很清楚：

```python
1. 你给它一个目标地址
2. 给它一个 patch 大小
3. 再给它一个 `apply(code, size)` 回调
4. Nook 先准备一块可写的临时缓冲区
5. 让你在回调里修改这块缓冲区
6. 然后它再把修改后的字节安全地拷回真实代码页
```

所以 `Memory.patchCode(...)` 不是“你直接拿目标 `.text` 去写”，而是：

```python
- 先改临时副本
- 再统一提交到真实目标地址
```

`JsMemoryPatchCode(...)` 主要做这几步：

````python
1. 校验参数
   - 地址必须是非 0 指针
   - size 必须大于 0
   - apply 必须是函数

2. 检查目标内存是否可读
   - `IsReadableMemoryRange(...)`

3. 分配一块 `scratch` 临时缓冲区
   - `malloc(size)`

4. 先把目标地址当前那段字节拷进 `scratch`
   - `memcpy(scratch, target, size)`

5. 把 `scratch` 指针包装成 JS 可操作的指针值
   - 作为 `apply(code, size)` 里的 `code`

6. 调 JS 回调
   - 让脚本在这块临时副本上执行：

```js
code.writeByteArray([0x1f, 0x20, 0x03, 0xd5]);
```

7. 读取目标原始页权限
   - `TryGetUniformProtectionForRange(...)`

8. 推导出可写权限版本
   - `TryMakeWritableProtectionString(...)`

9. 对目标页做页对齐
   - `ComputePageAlignedProtectionRange(...)`

10. 临时改页权限

   - Android/Linux 下最终走 `mprotect(...)`

11. 把 `scratch` 内容拷回真实目标地址

   - `memcpy(target, scratch, size)`

12. 刷指令缓存

   - `FlushInstructionCacheForRange(...)`

13. 恢复原始页权限

14. 释放 `scratch`
````

这里的`Memory.patchCode(...)` 回调里给你的 `code`，本质上是一块临时内存的指针。Nook 在运行时里已经给指针对象挂了写内存能力，所以脚本可以直接：

```python
code.writeByteArray([...])
```

也就是说：

```python
- 写的不是原始 `.text`
- 而是 `scratch`
- Nook 在回调结束后再把 `scratch` 提交到真实代码地址
```

Frida 写法里会用 `X86Writer`、`Arm64Writer` 这类接口直接写指令。
而在 Nook 当前实现里，我暂时没有去完整复刻这套 writer API，而是先用 `Memory.patchCode(...)` 去完成等效 patch。

## 结语

如果只按这些例子顺序往下看，会发现一条很清晰的演进线：

- `frida-0x1` 到 `frida-0x7`，Nook 逐步把 Java 侧常见 Frida 工作流补齐
- `frida-0x8` 到 `frida-0xA`，Nook 开始具备 Native 侧常见观察、改写、主动调用能力
- `frida-0xB`，Nook 开始尝试用自己的方式去覆盖更底层的 patch 场景

这条路线对我来说很重要，因为它让我确认了一件事：

Nook 的价值已经不再只是“底层有 Java Hook、PLT Hook、Inline Hook”，而是它开始形成了一种更接近 Frida 的使用方式。

也就是说，Nook已经不只是一个会 Hook 的框架，而是在把它一点点推成一个真正可用的 Frida-like Hook 工具。不过总体而言，Nook还处于一个相对幼稚的阶段，希望后面可以慢慢一点点完善!

---

# 回复

## 回复 by mb_zoyhhbnr (#2)

*2026-5-26 09:42*

太强了![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ldbucrik (#3)

*2026-5-26 09:59*

感谢分享

## 回复 by jyotidwi (#4)

*2026-5-26 10:46*

tql

## 回复 by mb_xjdhrmck (#5)

*2026-5-26 10:58*

666

## 回复 by didiid (#6)

*2026-5-26 14:09*

666

## 回复 by tonykros (#7)

*2026-5-26 14:21*

666

## 回复 by xingbing (#8)

*2026-5-26 15:15*

强![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by 墨穹呢 (#9)

*2026-5-26 15:16*

感谢分享

## 回复 by mb_pesxllvn (#10)

*2026-5-26 17:32*

666

## 回复 by 院士 (#11)

*2026-5-26 19:51*

先收藏，慢慢学习。

## 回复 by XCicada (#12)

*2026-5-26 19:54*

666

## 回复 by PPTV (#13)

*2026-5-26 19:59*

666

## 回复 by AGSFGBKILO (#14)

*2026-5-26 21:46*

大佬厉害呀

## 回复 by wx_Huber Barrientos (#15)

*2026-5-27 11:49*

666

## 回复 by git_94327axixa518 (#16)

*2026-5-28 19:15*

66666

## 回复 by guardia (#17)

*2026-5-28 20:33*

666

## 回复 by 简单的简单 (#18)

*2026-5-28 23:20*

666

## 回复 by x1a0f3n9 (#19)

*2026-5-29 12:42*

666太强了

## 回复 by mb_msgksrpq (#20)

*2026-6-1 14:58*

没办法指定端口么

## 回复 by n_1ng (#21)

*2026-6-1 18:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_msgksrpq](https://bbs.kanxue.com/user-992126.htm)
>  没办法指定端口么
>
>

目前还没写，过两天会和gadget一起加一下

## 回复 by 辉煌科技 (#22)

*2026-6-2 03:52*

谢谢

## 回复 by mb_qimctavn (#23)

*2026-6-2 09:19*

6

## 回复 by n00bzx (#24)

*2026-6-3 19:24*

莫得kx额度了,就不给了

## 回复 by 叶晓枫A (#25)

*2026-6-4 03:37*

可以像frida那样手动注入fridagatget实现免root hook吗

## 回复 by n_1ng (#26)

*2026-6-4 11:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  叶晓枫A](https://bbs.kanxue.com/user-797221.htm)
>  可以像frida那样手动注入fridagatget实现免root hook吗
>

github上刚更新了，文章还没写，可以试试看哈哈

## 回复 by 八嘎boy (#27)

*2026-6-4 19:41*

666

## 回复 by AK1988DA (#28)

*2026-6-6 17:16*

888

## 回复 by mb_gywomfeb (#29)

*2026-6-10 21:25*

看看学习一下

## 回复 by Midsw (#30)

*2026-6-11 21:50*

6666 厉害

## 回复 by mb_kgneopde (#31)

*2026-6-12 17:24*

666

## 回复 by ulong9527 (#32)

*2026-6-26 09:43*

感谢分享，学习一下

## 回复 by iBa0 (#33)

*2026-7-7 21:06*

123

## 回复 by wx_kx92911 (#34)

*2026-7-9 10:05*

感谢分析

## 回复 by mb_degalzhb (#35)

*2026-7-15 14:35*

nb
