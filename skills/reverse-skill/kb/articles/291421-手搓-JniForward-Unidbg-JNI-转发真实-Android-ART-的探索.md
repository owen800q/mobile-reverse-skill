---
title: '[原创]手搓 JniForward：Unidbg JNI 转发真实 Android ART 的探索'
url: https://bbs.kanxue.com/thread-291421.htm
tid: 291421
author: r8e8cd8
date: '2026-06-01'
tags: [Android安全, 原创, 程序开发]
crawled_at: '2026-07-31T15:04:30+08:00'
replies: 49
---

## 为啥动手

论坛里偶尔能看到「SO 在 PC 模拟、JNI 丢真机跑」的说法，当时没看太懂中间怎么接。后来手写补环境补烦了，自己撸了一版。

- Unidbg 跑 SO，Native 一般没问题，一回调 JNI 就卡：`TreeMap` 遍历、`String.getBytes`、`getPackageManager` 等，全得 `AbstractJni` 里 switch。
- 换 App 就复制改一轮；Iterator 状态、字符编码差一点点，签名就歪。
- 想搞明白的是：**Native 继续在 Unidbg 里跑，JNI 里哪些该扔真机、怎么传、怎么接回来。**

下面先简单说下整体思路，再写实现细节和踩坑。

---

## 整体思路

**分工：PC 跑 SO，手机跑该真算的那部分 Java**

- SO 的 Native 指令仍在 Unidbg/Unicorn 里执行。
- 遇到 `java/*` 这类 JNI（`TreeMap`、`String.getBytes` 等），PC 不在 `AbstractJni` 里硬编返回值，而是经 adb 发一行 JSON 到手机 Agent，在真机 ART 里调完，再把结果传回。
- PC 和手机之间用 **JSON 一行一问一答**，方便写协议、对 log。

**对象跨进程：只传编号，不传指针**

- Unidbg 里 SO 拿到的 Java 引用，本质是 `**DvmObject`**（模拟器里的「Java 对象壳」）。
- 真机 Agent 里对应的是 `**jobject`** / 普通 Java 对象。
- 这两者都不能塞进 Socket，所以线上只传 `**Handle`（整数编号）**，两边各一张表：`编号 → 真对象`。

举个短例子（SO 遍历 TreeMap）：

1. PC 发 JSON，让手机 `new TreeMap({"width":"1080"})`，手机登记 **1001**，回 `{HANDLE, 1001}`。
2. PC 收到后造一个 `**DvmObject` 壳**，里面不写真 Map，只记「远程编号 = 1001」——SO 以为手里有个 Java 对象，继续跑。
3. SO 调 `entrySet()`，PC 再发 JSON：`对 HANDLE 1001 调 TreeMap->entrySet`；手机查表找到真 TreeMap，调完登记 **1002** 回传。
4. PC 又造一个新 `**DvmObject` 壳**（编号 1002），SO 接着调 `iterator`、`hasNext`、`next`……**Iterator 的状态一直在手机那张表里**，PC 只传递编号。

要点：PC 的 `DvmObject` 多半是「指向手机的遥控器」；手机 Handle 表里才是 `TreeMap`、`Iterator` 本体。同一条链里编号对得上就行，PC 的 1003 和手机的 1003 不要求是同一个内存对象。

**手机算完之后怎么传回来？按返回值类型来**

一次 JNI = 一次 JSON 往返。手机 invoke 完，**按 JNI 返回值是什么类型**，在 JSON 里带不同的 `result`，不是固定只传 Handle：

- **返回 Java 对象**（Map、Iterator、Entry…）→ `HANDLE` 编号，PC 造 `DvmObject` 壳，下次 JNI 再把这个编号发回去。
- **返回 boolean / int 等** → `BOOL`、`I32` 等，把值直接传回来。
- **返回 byte[]** → `BYTES`（Base64），比如 `String.getBytes()`。
- **返回 String** → `STRING`，PC 包成 `StringObject`。
- **void / null** → `NULL` 或空 result。

对象还要链式调用（`next` 再 `getKey`），就靠 Handle 来回指；字符串、字节数组 **把值传回来就行**，SO 在 Native 里直接用，通常不必再登记成 Handle。

**分流：不是全部 JNI 都上网**

- 独立 Agent 是单独安装的 App，没有目标 App 的 Context / ClassLoader。
- `java/`*、`javax/`* → 发手机（JDK 类，ART 算得准）。
- `android/*`、包名签名、`com.xxx` 业务类 → 留 PC 补环境。
- 以后若接 Frida / Xposed 模块（跑在目标进程里），这条边界可以往后挪，协议不用改。

---

## 几种做法（简单对比）

本质都是：**PC 截 JNI → 发请求 → 真机 ART 执行 → 结果回传**。差别在执行端放哪、要少写多少补环境。

- **纯 Unidbg 手写补环境** — 不连手机，全在 `AbstractJni` 里 switch；简单，JNI 多了难维护。
- **Unidbg + 独立 Agent APK + adb（我用的）** — PC 跑 SO，`java/`* 发 JSON 到自写 App；包名、业务类仍 PC 补；不 root、不注入目标 APK。
- **Frida / Xposed 当 Agent** — 跑在目标 App 进程里，**能补的环境更多**（Context、业务类、包名等）；JSON 协议可以共用，但注入/框架 **有可能被检测**，我还没做到这一步。

---

## 整体架构

```python
PC（Unidbg）
  libxxx.so 在 Unicorn 里跑
  SO 调 JNI
    ↓
  【代理层】拦住所有 Jni 回调，统一进 Router
    ↓
  【Router.dispatch】打包成一次 JniCall（方法名 + 参数）
    ↓
  【路由策略】看 signature 前缀
    ├─ java/*、javax/*  ──► 【远程执行器】编 JSON → adb → 手机
    └─ android/*、业务类  ──► 【本地执行器】反射调 AbstractJni 补环境

手机 Agent
  127.0.0.1:8765 收 JSON → 真机 invoke → 回一行 result（HANDLE/BOOL/BYTES…）
```

**Router 在架构里干什么（和上面对应）**

Router 本身**不算 JNI、也不连手机**，只做三件事：

1. **统一入口** — SO 每次 JNI 都先到 `dispatch(方法名, 参数)`，不再散落到各处 switch。
2. **打包** — 压成 `JniCall`，后面无论本地还是远程，格式一致。
3. **分拣** — 查 signature：

- `java/util/Iterator->hasNext()Z` → 远程 → 发手机 → 回来 `BOOL`
- `java/util/Iterator->next()...` → 远程 → 回来 `HANDLE` → PC 造 `DvmObject` 壳
- `android/app/Application->getPackageManager()...` → 本地 → 进本地补环境
- `acceptMethod` → 本地（只问接不接，不是最终执行）

分拣之后是两条执行链，**互斥、只走一条**：

```python
JniCall
  → 路由：isRemote?
       否 → LocalJniExecutor → 反射调 AbstractJni（补环境 switch）
       是 → RemoteJniExecutor → JSON 往返 → JniArgBridge 译回 DvmObject/boolean/bytes
```

所以架构图里「代理 → Router → 分叉」就是：**先进 Router 再决定本地算还是手机算**；控制台 `[local]` / `[remote]` 就是这次走了哪条叉。

Native 指令只在 PC；需要真 JVM 的 JNI 才走右边那条叉。

---

## Router 到底是干什么的、怎么分发

可以把它想成快递分拣中心：SO 每次调 JNI，都先到 Router，Router **不自己算**，只负责「这单该本地送还是发手机」。

### 第一层：统一入口（代理）

Unidbg 原来直接调 `AbstractJni`。我在外面包了一层**动态代理**：任何 `callObjectMethod`、`findClass`……先进代理，代理只做一件事：

```java
return router.dispatch(方法名, 参数数组);
```

这样不用改 Unidbg 源码，用户还是 `vm.setJni(this)`。

### 第二层：打包（JniCall）

Router 收到「方法名 + 参数」，压进一个小结构：

```java
public Object dispatch(String op, Object... args) {
    return executor.execute(new JniCall(op, args));
}
```

`op` 比如 `"callObjectMethodV"`，`args` 里是 `[vm, dvmObject, signature, varArg]`。
**为什么要打包？** 后面发 JSON 时，整包 `JniCall` 转 args 就行，Router 本身不关心本地还是远程。

### 第三层：选执行器（Hybrid）

真正「分发」发生在 `HybridJniExecutor`：

```java
public Object execute(JniCall call) throws Throwable {
    if (!路由策略.isRemote(call)) {
        return 本地执行器.execute(call);   // 还是调 AbstractJni
    }
    try {
        return 远程执行器.execute(call);   // 发 JSON 到手机
    } catch (IOException e) {
        if (允许回退) return 本地执行器.execute(call);
        throw e;
    }
}
```

**路由策略怎么判？** 从参数里找出 JNI 的 signature 字符串（形如 `java/util/Iterator->next()Ljava/lang/Object;`）：

- 以 `java/`、`javax/` 开头 → **发手机**（框架类，真机 ART 算最准）
- 以 `android/`、`com/`、`org/` 开头 → **留 PC**（包名、系统 API、业务类）
- `acceptMethod` / `acceptField` → **永远 PC**（只是 Unidbg 问「该方法是否由补环境接管」，不是真执行）

判完以后，两条路：

**本地路**：`LocalJniExecutor` 用反射找到 `Jni` 接口上对应方法，调原来的实现类——和没加转发前一模一样，补环境 switch 还写在这。

**远程路**：`RemoteJniExecutor` 把 `JniCall` 编成 JSON，Socket 发到 8765，等手机回一行 JSON，再解码塞回 Unidbg。

### 第四层：日志（可选）

外面再包一层「打印执行器」，控制台就会看到：

```python
JNI >> [remote] callObjectMethod java/util/Iterator->next()Ljava/lang/Object;
JNI >> [local]  callObjectMethod android/app/Application->getPackageManager()...
```

`[remote]` / `[local]` 就是 Router 分发结果的直观体现。

**一句话**：Router = 统一进门 → 打包成 JniCall → 按类名前缀分拣 → 本地反射 or 远程 JSON。

---

## 我是怎么一步步做的

**第 1 步：先想直接改 AbstractJni —— 不行**

最开始很直接的想法，把 Unidbg 里每个 JNI override 改成一行转发，例如：

```java
@Override
public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> o,
                                     String signature, VarArg varArg) {
    return (DvmObject<?>) router.dispatch("callObjectMethod", vm, o, signature, varArg);
}
```

`findClass`、`callBooleanMethod` 等几十个方法都要这么改。能跑，但：

- 动的是框架源码，以后升级 Unidbg merge 很痛苦；
- 本地 / 远程写死在改过的类里，不好切换。

后来改成 **不动 AbstractJni**，外面用动态代理包 `Jni` 接口，再只做 Router + 本地反射，跑通 SO 确认和改之前结果一致。

**第 2 步：定 JSON 协议 + PC 端假 Agent**

在 PC 再起一个监听 8765 的小程序，用真 Java 处理 TreeMap/Iterator，跟未来手机 Agent 同一套 JSON。协议定成 **一行 JSON 一问一答**，方便 log 里直接 grep。

**遇到的问题：Unidbg 回调名带 `V`，Agent 只认不带 `V` 的 op**

Unidbg 的 `Jni` 接口里，处理可变参数的方法名末尾会多一个 `**V`**（表示 VarArg），比如 `callObjectMethodV`、`callBooleanMethodV`。我在 PC 侧用动态代理转发时，`method.getName()` 拿到的就是这个带 `V` 的名字，原样写进 JSON 的 `op` 字段。

假 Agent 分发器是按「不带 V 的标准名」写的 switch，两边对不上：

```java
// PC 侧：代理里 method.getName() 拿到的名字
request.setOp("callObjectMethodV");   //  JSON 里 op 带 V 不行

// Agent 侧
switch (req.getOp()) {
    case "callObjectMethod":   // 只注册了这条
        return invokeObjectMethod(req);
    default:
        throw new UnsupportedOperationException("unknown op: " + req.getOp());
}
```

表现就是：Socket 通了、JSON 也 parse 成功，但 Agent 回 `ok:false`，或直接抛 `unknown op: callObjectMethodV`。跟参数翻译无关，纯粹是 **op 名字不一致**。PC 发 JSON 前，把末尾的 `V` 剥掉即可：

```java
private static String normalizeOp(String op) {
    if (op.endsWith("V") && op.length() > 1) {
        return op.substring(0, op.length() - 1);
    }
    return op;
}
// callObjectMethodV  → callObjectMethod
// callBooleanMethodV → callBooleanMethod
```

这样 PC 和 Agent 只维护一套 op 分支，不用为每个 `xxxV` 再复制一份。

**第 3 步：参数翻译（最难，具体代码 AI 帮着改了几轮）**

Unidbg 里 SO 调 JNI 时，参数不是普通 Java 对象，而是一堆框架类型：`DvmObject`、`VarArg`、`VaList`、`StringObject`……PC 要把这些「翻译成 JSON 能发的形式」再发出去，手机算完还要「翻译回来」塞给 Unidbg。我主要理规则（什么发 HANDLE、什么发 MAP），具体反射和编码 AI 帮着改了几轮。

**第 4 步：分流策略 —— 为什么「全扔手机」不行**

跑通 PC 假 Agent 之后，很自然地想：**既然真机 ART 算得准，干脆所有 JNI 都发手机，PC 一个 switch 都不用写。**

试下来不行，原因是：**独立 Agent 是一个自己安装的 APK，不在目标 App 进程里。**

| 期望由手机计算的 | 独立 Agent 里实际会怎样 |
|-|-|
| `Application.getPackageName()` | 返回 Agent 自己的包名（比如 `com.example.jniagent`），不是目标 App |
| `getPackageManager().getPackageInfo(...)` | 查的是 Agent 能看到的包，签名校验、版本号全不对 |
| `com.xxx.business.EncryptUtil` 等业务类 | Agent 的 ClassLoader 根本加载不到目标 APK 里的类 |
| `Context.getAssets()` / `getResources()` | 拿到的是 Agent 的资源，不是目标 App 的 so、配置、证书 |
| 需要目标进程内存里的单例、静态字段 | 完全不在一个进程，查表也查不到 |

所以分流不能是「能发就发」，而是 **按类名前缀划边界**：

- `**java/`*、`javax/*`** → 发手机。JDK 框架类，跟哪个 App 无关，ART 算 TreeMap、String、Iterator 最靠谱。
- `**android/`*、目标包名、`com/` 业务类** → 留 PC 补环境。要么需要 Android 上下文，要么需要目标 App 的 ClassLoader，独立 Agent 给不了。
- **`acceptMethod` / `acceptField`** → 永远 PC。这只是 Unidbg 问「该方法是否由补环境接管」，不是真执行，发手机没意义。
- 这里应该还有更好的优化方法。

**第 5 步：真机 Agent APK**

前面 PC 假 Agent 就是在电脑上开了一个「小型 Java 服务」，监听 8765，收到 JSON 就调 TreeMap、回 JSON。第五步做的事很简单：**把这段逻辑原样搬进手机里。**

可以把它想成在手机上装了一个「专职接电话的 App」：

1. **装 APK** — 就是一个普通 Android 应用，不用 root，不用改目标 App。
2. **开前台 Service** — Android 后台杀进程很凶，Service 不挂前台通知，RPC 跑着跑着就被系统掐了；所以必须常驻通知栏，相当于跟系统说「我在干活，别杀我」。
3. **手机内部监听 8765** — Service 在真机里 bind `127.0.0.1:8765`，等 PC 通过 adb 隧道把请求送过来。
4. **adb 隧道** — PC 和手机是两个设备，不能直接 Socket 连。用 `adb forward tcp:8765 tcp:8765` 的意思是：PC 访问本机 8765 端口，由 adb 把连接转发到手机上的 8765。可以把它想成 **USB 里挖了一条专用管道**。

*第 6 步：删 java/ 补环境*
TreeMap/Iterator 的 override 全删，只留 `vm.setJni(this)` 和 android/* 伪装，签名和纯 PC 跑一致才算通。

---

## 关键代码讲解

### 动态代理：所有 JNI 先进 Router

```java
// 包在 AbstractJni 外面
return (Jni) Proxy.newProxyInstance(
    Jni.class.getClassLoader(),
    new Class<?>[]{ Jni.class },
    (proxy, method, args) -> router.dispatch(method.getName(), args)
);
```

### 本地执行：反射调原来的类

```java
public Object execute(JniCall call) throws Throwable {
    // 方法名 + 参数数量 + 参数类型在 Jni 接口里找 Method
    Method method = resolveMethod(call.getOp(), call.getArgs());
    return method.invoke(delegate, call.getArgs());
}
```

本地处理的是「Router 分拣错了或不该上网的」，最终仍进本地 switch 补环境。

### 远程执行：一整条 JNI 变成一次 Socket 往返

```java
public Object execute(JniCall call) throws Throwable {
    BaseVM vm = 从参数里取出vm;
    RpcValue[] args = 把JniCall参数翻译成JSON可发的形式;
    String op = 归整方法名(call.getOp());  // callObjectMethodV → callObjectMethod
    RpcRequest request = new RpcRequest(请求序号++, op, args);

    try (Socket socket = new Socket(host, port)) {
        写出一条JSON加换行;
        读回一行JSON;
        return 把JSON结果变回Unidbg能用的返回值(vm, response, signature);
    }
}
```

### 参数翻译（核心难点）

```java
// DvmObject 里如果是 远程编号 占位→ 发 HANDLE
if (value instanceof RemoteHandleMarker) {
    return RpcValue.handle(marker.getId());
}
// 如果是 Map 初始数据 → 发 MAP，让手机 new TreeMap
if (value instanceof Map) {
    return RpcValue.map(copy);
}
// VarArg：反射读内部 args 列表，逐个翻译
```

### 结果翻译：HANDLE 变回 DvmObject 占位

```java
public static DvmObject<?> wrapRemoteHandle(BaseVM vm, int handleId, String signature) {
    // 从 signature 看出返回值类型，比如 Iterator.next → Map$Entry
    String className = inferClassName(signature);
    DvmClass type = vm.resolveClass(className);
    // 造一个「壳」，里面只存远程编号，真对象在手机
    return new RemoteHandleDvmObject(type, new RemoteHandleMarker(handleId));
}
```

壳的类型不能设成占位符类本身，必须按 signature 推断真实 Java 类型，否则后面 JNI 类型全乱。

### 手机 Agent：读 JSON、调 Java、写 JSON

```java
// Service 里启动，bind 127.0.0.1:8765
String line = reader.readLine();
RpcRequest req = 解析JSON(line);
RpcResponse resp = dispatcher.dispatch(req);  // 按 op + signature 调真 TreeMap/Iterator
writer.write(编码JSON(resp));
writer.newLine();
writer.flush();
```

手机 Agent 与 PC MockAgent 的 JniOpDispatcher 采用 按 JNI signature 硬编码 的 if/switch：收到 JSON 后根据 op + signature 在真机执行对应 Java 调用。未实现的 signature 会在 logcat 中报 UnsupportedOperationException，再按需增加分支。

**当前仅针对示例 SO 已实现的远程调用**（Map 遍历签名链，非框架全集）：

- `ping`
- `TreeMap.entrySet` / `Set.iterator` / `Iterator.hasNext|next` / `Entry.getKey|getValue`
- `String.getBytes`

**receiver**：参数为 `MAP` 时在手机 `new TreeMap<>(map)` 并登记编号；为 `HANDLE` 时查表取对象。换其他 SO 时，Router/JSON 可复用，Agent 需按实际 `java/*` 调用扩展上述列表。

---

## JSON 协议长什么样

**请求**：`id`、`op`、`args`（数组，每项 `type`+`value`）

**成功**：`id`、`ok:true`、`result`、`resultType`（小写 handle/boolean/bytes/string）

**失败**：`ok:false`、`exception`、`message`

**类型**：NULL、BOOL、I32、STRING、**HANDLE**（大写）、BYTES（Base64）、MAP

**收发**（一行一问一答）：

```java
writer.write(JSON字符串);
writer.newLine();
writer.flush();
String line = reader.readLine();
```

---

## 配置项（启动 Hybrid 时用）

- `jni.forward.mode=local` — 不加转发，原版 Unidbg
- `jni.forward.mode=hybrid` — 强制 java/* 走手机
- `jni.forward.mode=auto` — 启动时 ping 8765，通则 Hybrid（默认）
- `jni.forward.host` / `port` — 默认 127.0.0.1:8765
- `jni.forward.fallback=true` — 手机连不上时回退 PC 本地，开发时用

---

## 用户代码前后

**以前**：几十行补 TreeMap/Iterator。

**现在**：

```java
vm.setJni(this);   // 框架里自动包代理 + Hybrid
// java/* 不用 override 了
// android/* 包名、getPackageManager 仍在 PC 补
```

---

## 手机 Agent 工程（功能说明）

- 独立 Android 工程，Gson 解析 JSON，不依赖 Unidbg。
- 前台 Service 保活，否则后台被杀 RPC 断。
- RpcServer：accept 线程 + 线程池，每个连接处理一条 JSON。
- HandleRegistry：编号从 1000 自增。
- JniOpDispatcher：和 PC 假 Agent 同一套 signature 分支。
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_GUHRBBTA8DZK8TK.webp)
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_EJPGR8236AYHD7V.webp)

---

## 联调顺序

工程脚本与 [快速上手.md](https://github.com/r8e8cd8/jni-forward-unidbg/blob/main/%E5%BF%AB%E9%80%9F%E4%B8%8A%E6%89%8B.md) 一致，在项目根目录分步执行。

### 前置

- 手机安装 **JNI Forward Agent** APK，开启 USB 调试（第 3 步真机用；可先装好）
- 确认 `examples\vipshop\assets\` 下有 `wph.apk`、`libkeyinfo.so`
- 缺 `libz.so` 时从 Android SDK 复制到 `unidbg-android/src/main/resources/android/sdk23/lib64/`

### 第 1 步：框架自测

```cmd
run-jni-remote-verify.cmd
```

成功标志：

```
[PASS] JniForward smoke tests: 4/4
[PASS] JniForward remote tests: 4/4
```

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_33ZWDSYXBVWME9S.webp)

### 第 2 步：MockAgent + 示例

**窗口 A**（保持运行）：

```cmd
run-mock-agent.cmd
```

看到 `listening on 127.0.0.1:8765` 即可。

**窗口 B**（依次两条）：

```cmd
compile-example.cmd
run-hybrid-example.cmd
```

成功标志：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_ESDM3RCV2MC92U9.webp)

```
call native method result: d4887cba12109a9e007e8f1d9628f301f9384676
```

日志里应有 `JNI >> [remote] ...`。

【图3】

### 第 3 步：真机 Hybrid

1. 打开手机上 **JNI Forward Agent**
2. **关掉 PC 上的 MockAgent**（8765 不能冲突）

**窗口 A**：

```cmd
run-phone-setup.cmd
```

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_WVUX22SNAAKF82D.webp)
**窗口 B**：

```cmd
compile-example.cmd
run-hybrid-example.cmd
```

成功标志：`pong` + 签名 `70dc3d08...` + `JNI >> [remote]`（来自手机）。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202606/1012883_JAPFFF2HXK47QK3.webp)

---

## 项目的不足

- **JNI 操作覆盖不全**：目前 mainly 支持对象方法、布尔方法；`NewObject`、`GetByteArrayElements` 等尚未做成 JSON op，不少场景仍须在 PC 侧手写补环境。
- **Agent 按 signature 硬编码**：手机端用 if/switch 逐条对齐 PC 假 Agent，缺一条补一条；未做成「解析 signature → 反射 invoke」，维护成本高，异常与重载也难统一处理。
- **独立 APK 补不全目标 App 上下文**：执行端不在目标进程内，`android/*`、包名、业务类仍依赖 PC 补环境；Frida / Xposed 尚未接入，想进一步减少补环境只能换执行端，协议虽可复用但工程未做。

完整工程见 [jni-forward-unidbg](https://github.com/r8e8cd8/jni-forward-unidbg)（仅供参考：环境、机型、示例 SO 各异，**不一定能直接跑通**，主要提供实现思路与目录结构）。

---

# 回复

## 回复 by 4Chan (#2)

*2026-6-1 13:46*

看了学习一下

## 回复 by 铭天星 (#3)

*2026-6-1 15:52*

666

## 回复 by Imxz (#4)

*2026-6-1 16:30*

tql

## 回复 by 温泉划水鱼 (#5)

*2026-6-1 20:03*

别玩unidbg了，直接真机trace一遍完事了

## 回复 by fjqisba (#6)

*2026-6-1 20:17*

为啥一定要在电脑上跑![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_ldbucrik (#7)

*2026-6-1 20:33*

感谢分享

## 回复 by 寻梦之璐 (#8)

*2026-6-1 22:27*

6666

## 回复 by kingking888 (#9)

*2026-6-1 23:06*

666

## 回复 by mb_elqwyvnm (#10)

*2026-6-1 23:21*

plus

## 回复 by jyotidwi (#11)

*2026-6-2 01:24*

Thanks

## 回复 by dob_C (#12)

*2026-6-2 09:49*

感谢分享

## 回复 by r8e8cd8 (#13)

*2026-6-2 09:57*

>
> [温泉划水鱼](https://bbs.kanxue.com/user-991803.htm)
>  别玩unidbg了，直接真机trace一遍完事了
>

真机 trace 和 Unidbg 不互斥，各有所长

## 回复 by r8e8cd8 (#14)

*2026-6-2 10:03*

不是非得在电脑上跑。这篇主要是看SO在模拟器、JNI在真机怎么接；若Native也全扔真机，就跟普通trace差别不大了。以后或许能延伸成调试工具之类，目前还是先摸原理。谢谢你的问题。

## 回复 by x1a0f3n9 (#15)

*2026-6-2 11:26*

有意义的，感谢分享

## 回复 by didiid (#16)

*2026-6-2 14:56*

666

## 回复 by 橙_ (#17)

*2026-6-2 16:38*

nb

## 回复 by mb_qimctavn (#18)

*2026-6-2 17:44*

6

## 回复 by YANG、 (#19)

*2026-6-2 23:24*

66666

## 回复 by FMNS (#20)

*2026-6-3 09:43*

>
> [温泉划水鱼](https://bbs.kanxue.com/user-991803.htm)
>  别玩unidbg了，直接真机trace一遍完事了
>

感觉麻烦

## 回复 by shuangmou (#21)

*2026-6-3 15:50*

感谢分享

## 回复 by A00乐淘 (#22)

*2026-6-5 13:28*

感谢分享

## 回复 by mb_fdskejlh (#23)

*2026-6-6 10:09*

牛啊牛

## 回复 by mb_nkjfyhkg (#24)

*2026-6-7 03:15*

mark

## 回复 by wx_听书人 (#25)

*2026-6-7 14:43*

6666

## 回复 by mb_jqswpxgb (#26)

*2026-6-8 09:26*

666

## 回复 by mb_ktasfpbp (#27)

*2026-6-15 18:32*

6

## 回复 by wx_无法回头的伪装 (#28)

*2026-6-15 18:43*

66666

## 回复 by wx_插曲 (#29)

*2026-6-15 22:46*

6666

## 回复 by Freax (#30)

*2026-6-16 15:21*

666

## 回复 by git_29853Sandyeeee (#31)

*2026-6-18 03:04*

thx

## 回复 by 呼吸24K纯氧 (#32)

*2026-6-18 09:35*

感谢分享

## 回复 by koflfy (#33)

*2026-6-18 09:42*

6666

## 回复 by mb_cpsiqdds (#34)

*2026-6-20 21:01*

学习

## 回复 by 4ak5ra (#35)

*2026-6-21 15:46*

666

## 回复 by Sigil (#36)

*2026-6-22 10:05*

1

## 回复 by Sigil (#37)

*2026-6-22 10:06*

1

## 回复 by mxystery (#38)

*2026-6-22 19:50*

6666

## 回复 by mb_ajqftfbv (#39)

*2026-6-23 05:03*

66666

## 回复 by buluo533 (#40)

*2026-6-23 08:40*

666666

## 回复 by 一只鸭子 (#41)

*2026-6-23 08:55*

感觉好复杂并且还是要自己手补一些业务环境，感觉现在来说扔给模型去补环境更好

## 回复 by mb_mlyojneh (#42)

*2026-6-23 11:27*

mark

## 回复 by ulong9527 (#43)

*2026-6-26 09:41*

感谢分享，学习一下

## 回复 by mb_uvyukvot (#44)

*2026-6-30 16:21*

666

## 回复 by mb_sajaoega (#45)

*2026-6-30 21:38*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by Da_ (#46)

*2026-7-1 16:07*

666

## 回复 by iBa0 (#47)

*2026-7-6 08:14*

66

## 回复 by nuomida (#48)

*2026-7-8 17:08*

感谢分享

## 回复 by wx_kx92911 (#49)

*2026-7-8 18:22*

感谢分析

## 回复 by amwpecel (#50)

*2026-7-17 08:09*

66666
