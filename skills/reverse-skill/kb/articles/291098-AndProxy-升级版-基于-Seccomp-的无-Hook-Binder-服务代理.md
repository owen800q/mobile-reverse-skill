---
title: '[原创]AndProxy 升级版：基于 Seccomp 的无 Hook Binder 服务代理'
url: https://bbs.kanxue.com/thread-291098.htm
tid: 291098
author: 孤木落
date: '2026-05-04'
tags: [Android安全, 原创, 基础理论, 程序开发, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:07:32+08:00'
replies: 80
---

# AndProxy 升级版：基于 Seccomp 的无 Hook Binder 服务代理

本文是 **AndProxy——Syscall 及 Binder 运行时代理库** 的升级版方案介绍。

原方案通过 GotHook 拦截 Binder `ioctl` 实现服务代理；升级版完全抛弃 Hook，仅使用 `seccomp-notify` 机制，直接修改 Binder 事务中的目标 `handle`，利用 Binder 驱动自身的路由机制实现透明转发。

关于 Binder 通信的基础概念，例如：

- `BINDER_WRITE_READ`
- `BC_TRANSACTION`
- `binder_transaction_data`

可参考前置文章。

---

## 一、背景

在 Android 系统上，对系统服务调用进行拦截和代理，是虚拟机、应用分身、隐私保护等场景中的基础能力。

传统代理方案大致分为两类。

---

### 1. Java 层动态代理

通过反射替换 `ServiceManager` 中的 `IBinder` 缓存。

这种方式的问题是：

- 时机敏感
- 覆盖不全
- 容易被检测
- 对不同 Android 版本兼容性较差

---

### 2. Native 层 GotHook / Inline Hook

通过 Hook `libbinder.so` 中的 `ioctl` 函数实现 Binder 调用拦截。

原版 AndProxy 采用的就是这种方案，但它存在几个固有问题：

- 需要手动扫描 `/proc/self/maps` 定位库加载地址
- GOT 表项没有写权限，需要先 `mprotect` 再修改
- 修改后的内存权限变化是明显特征
- Hook 点容易受系统版本、编译选项和加固策略影响

---

### 升级版思路

既然所有 Binder 调用最终都会经过：

```c
ioctl(fd, BINDER_WRITE_READ, &bwr)
```

那么问题就变成：

>
> 能不能直接在系统调用层面拦截并修改 Binder 数据，而不修改任何代码？
>
>
>

答案是：

```
seccomp-notify
```

升级版 AndProxy 的核心思路是：

1. 拦截 `ioctl` 系统调用。
2. 判断是否为 `BINDER_WRITE_READ`。
3. 解析 `binder_transaction_data`。
4. 找到其中的 `target.handle`。
5. 将原始服务 handle 替换为代理服务 handle。
6. 让原始系统调用继续执行。
7. Binder 驱动根据新的 handle 自动将事务路由到代理服务。

整个过程不修改：

- 代码段
- GOT 表
- PLT 表
- `libbinder.so`
- Java 层缓存

只修改 Binder 事务中的一个字段：

```c
binder_transaction_data.target.handle
```

---

## 二、核心概念

在展开方案之前，需要先理清几个关键概念。

---

### 2.1 系统服务名 ≠ 系统服务类名

这是最常见的误区，也是方案设计的关键前提。

Android 系统服务的注册名和类名并不相同：

| 服务类名 | ServiceManager 注册名 |
|-|-|
| `com.android.server.am.ActivityManagerService` | `"activity"` |
| `com.android.server.pm.PackageManagerService` | `"package"` |
| `com.android.server.wm.WindowManagerService` | `"window"` |

客户端通常通过服务名调用：

```kotlin
ServiceManager.getService("package")
```

获取对应的 Binder handle。

只知道服务类名，无法直接推导出服务名。

因此，在代理系统中必须同时区分：

- **serviceClass**：用于反射获取 AIDL 方法编号
- **serviceName**：用于获取 Binder 服务 handle

---

### 2.2 Handle：Binder 驱动的路由标识

在 Binder 通信中，`handle` 是 Binder 驱动用来路由 IPC 数据的整数标识符。

客户端发起 `BC_TRANSACTION` 时，会在：

```c
binder_transaction_data.target.handle
```

中指定目标服务的 handle。

Binder 驱动根据这个值，将数据投递到对应的服务端进程。

因此，只要能修改这个字段，就可以改变 Binder 事务的路由目标。

也就是说：

>
> 修改 `target.handle`，就等价于修改 Binder 请求的目的地。
>
>
>

---

### 2.3 关键数据结构

一次完整的 Binder 调用会被封装在：

```c
binder_transaction_data
```

中。

其中两个字段是本方案最关注的核心：

| 字段 | 作用 |
|-|-|
| `target.handle` | 目标服务 handle，决定 Binder 请求被路由到哪里 |
| `code` | 方法编号，对应 AIDL 接口中的某个方法 |

方案的核心操作就是：

>
> 在 `BC_TRANSACTION` 被提交到内核之前，将 `target.handle` 替换为代理服务的 handle。
>
>
>

---

## 三、方案整体架构

升级版 AndProxy 由三个子系统构成，均在用户态运行。

```
┌──────────────────────────────────────┐
│         编译期：KSP 注解处理           │
│                                      │
│   @ProxyMethod(                     │
│       serviceClass,                 │
│       serviceName,                  │
│       methodName                    │
│   )                                 │
│                                      │
│   自动生成代理路由表和代理服务类       │
└──────────────┬───────────────────────┘
               │
               │ 生成代理路由表
               ▼
┌──────────────────────────────────────┐
│        运行时：Seccomp 拦截层          │
│                                      │
│   Seccomp-BPF 过滤 ioctl             │
│   解析 txn                           │
│   匹配路由表                          │
│   替换 target.handle                 │
└──────────────┬───────────────────────┘
               │
               │ 修改后的 Binder txn
               ▼
┌──────────────────────────────────────┐
│          辅助系统：初始化层            │
│                                      │
│   服务名 → handle 映射                │
│   code → 方法名映射                   │
│   BWR / Txn 解析函数                  │
│   代理服务启动与注册                  │
└──────────────────────────────────────┘
```

---

### 无 Hook 运行方式

整个方案通过注入 APK 的方式进入目标进程，在目标进程的用户态空间中运行。

核心机制包括：

- 进程自行安装 seccomp 过滤器
- supervisor 通过 seccomp-notify 接收系统调用通知
- 通过 `process_vm_readv()` 读取目标进程内存
- 通过 `process_vm_writev()` 写回修改后的 Binder 事务数据

整个过程不需要：

- Hook
- `mprotect`
- 修改 GOT
- 修改代码段
- `ptrace`

---

## 四、第一部分：基于 KSP 的注解系统

## 4.1 注解设计

升级版方案使用单个 `@ProxyMethod` 注解，直接声明代理一个目标方法所需的全部信息。

示例：

```kotlin
@ProxyMethod(
    serviceClass = "android.content.pm.IPackageManager",
    serviceName = "package",
    methodName = "getInstalledPackages"
)
fun proxyGetInstalledPackages(flags: Int, userId: Int): Any? {
    // 代理逻辑
}
```

三个参数分别承担不同功能，缺一不可。

| 参数 | 用途 | 为什么必须手动指定 |
|-|-|-|
| `serviceClass` | 反射获取 `Stub.TRANSACTION_*`，得到方法 `code` | `code` 值定义在 AIDL 生成的 Stub 类中，必须知道完整接口名 |
| `serviceName` | 调用 `ServiceManager.getService(name)` 获取目标服务 handle | 服务名是向 ServiceManager 注册的字符串，无法从类名稳定推导 |
| `methodName` | 反射获取对应 `TRANSACTION_*` 常量 | 同一个接口有多个方法，必须指定代理哪一个 |

---

### 为什么不自动维护“服务类名 → 服务名”映射？

Android 系统服务数量很多，而且服务类名与注册名之间没有统一规律。

例如：

| 服务类名 | 服务名 |
|-|-|
| `ActivityManagerService` | `"activity"` |
| `PackageManagerService` | `"package"` |
| `WindowManagerService` | `"window"` |

手动维护一套完整映射表的成本很高，并且容易出错。

更重要的是：

>
> `serviceName` 本身就是运行时获取 handle 的必要信息，并不是冗余字段。
>
>
>

因此，让开发者在注解中同时声明 `serviceClass` 和 `serviceName`，是更务实的工程选择。

这样既避免维护大型映射表，也让代理关系更加显式。

---

## 4.2 编译期处理流程

KSP 处理器在编译期完成以下工作。

---

### 第一步：收集所有 `@ProxyMethod`

遍历所有被 `@ProxyMethod` 标记的函数，提取三元组：

```
(serviceClass, serviceName, methodName)
```

例如：

```
android.content.pm.IPackageManager
package
getInstalledPackages
```

---

### 第二步：按 `serviceName` 分组

同一个 `serviceName` 下的代理方法会被归入同一个代理服务类。

例如：

```
serviceName = "package"
  ├── getInstalledPackages
  ├── getPackageInfo
  └── queryIntentActivities

serviceName = "activity"
  ├── startActivity
  └── getRunningAppProcesses
```

每个代理服务对应一个 Binder 服务实例，运行时只注册一次。

---

### 第三步：生成代理路由表

为每个被代理的方法生成一条路由记录。

每条记录包含：

| 字段 | 含义 |
|-|-|
| `serviceClass` | Binder 接口描述符，用于从事务数据中匹配接口 |
| `serviceName` | 系统服务注册名，用于获取原始服务和代理服务 handle |
| `code` | AIDL 方法编号，运行时通过反射填充 |
| `handler` | 对应的代理函数引用 |

最终生成的结构可以理解为：

```
serviceClass
  → serviceName
    → code
      → handler
```

例如：

```
android.content.pm.IPackageManager
  → package
    → 3
      → proxyGetInstalledPackages
```

---

## 五、第二部分：基于 Seccomp 的 Binder 拦截层

这是整个方案的核心。

它利用 Linux `seccomp-notify` 机制，在系统调用层面截获 Binder `ioctl`，并修改事务数据。

---

## 5.1 为什么使用 Seccomp-notify

`seccomp-notify` 对应的返回值是：

```c
SECCOMP_RET_USER_NOTIF
```

它允许用户态 supervisor 接管被过滤器命中的系统调用。

大致流程是：

1. 目标线程发起系统调用。
2. Seccomp-BPF 判断该系统调用需要通知用户态。
3. 系统调用暂停。
4. supervisor 读取通知。
5. supervisor 检查或修改参数。
6. supervisor 通知内核继续执行。
7. 内核恢复原始系统调用。

相比 Hook 方案，`seccomp-notify` 的优势是：

- 不修改代码
- 不修改 GOT
- 不依赖 `ptrace`
- 不占用信号处理函数
- 纯文件描述符 IO 模型，便于接入事件循环
- 可以获取完整的系统调用参数和寄存器上下文
- 更接近系统调用级别的透明代理

`SECCOMP_RET_USER_NOTIF` 需要内核支持，典型环境要求：

```
Linux kernel >= 5.10
Android 12+
```

---

## 5.2 BPF 过滤规则

Seccomp-BPF 过滤器在内核态做快速判断。

过滤逻辑如下：

```
1. 检查系统调用号
   - 如果不是 __NR_ioctl，直接放行

2. 检查 ioctl cmd 参数
   - 如果不是 BINDER_WRITE_READ，直接放行

3. 命中 ioctl + BINDER_WRITE_READ
   - 返回 SECCOMP_RET_USER_NOTIF
   - 通知 supervisor

4. 其他情况
   - 返回 SECCOMP_RET_ALLOW
```

BPF 层只负责粗过滤。

更精确的匹配逻辑，例如：

- 是否为 Binder fd
- 是否包含 `BC_TRANSACTION`
- 是否命中代理服务
- `code` 是否在路由表中

都交给用户态 supervisor 处理。

---

## 5.3 Supervisor 处理流程

当 BPF 过滤器返回 `SECCOMP_RET_USER_NOTIF` 后，supervisor 接管处理。

完整流程如下：

```
1. 通过 SECCOMP_IOCTL_NOTIF_RECV 获取通知

2. 从通知中提取系统调用参数：
   - fd
   - cmd
   - arg

3. 通过 process_vm_readv() 读取目标进程中的 binder_write_read

4. 遍历 BWR 写缓冲区，解析 Binder 命令

5. 遇到 BC_TRANSACTION 时：
   - 解析 binder_transaction_data
   - 读取 target.handle
   - 读取 code
   - 从数据缓冲区中提取接口描述符 serviceClass
   - 根据 serviceClass 找到 serviceName
   - 根据 serviceName 和 code 匹配代理路由表

6. 如果命中代理规则：
   - 将 target.handle 替换为代理服务 handle

7. 通过 process_vm_writev() 写回修改后的数据

8. 通过 SECCOMP_IOCTL_NOTIF_SEND 通知内核继续执行

9. 内核恢复原始 ioctl

10. Binder 驱动读取到已经被修改的 handle，
    将事务路由到代理服务
```

---

### 匹配逻辑

Binder 事务的数据缓冲区中通常包含接口描述符，例如：

```
android.content.pm.IPackageManager
```

这个字符串正好对应注解中的：

```kotlin
serviceClass = "android.content.pm.IPackageManager"
```

由于注解中同时声明了：

```kotlin
serviceClass = "android.content.pm.IPackageManager"
serviceName = "package"
```

KSP 可以在编译期生成查找链：

```
serviceClass → serviceName → code → handler
```

Supervisor 解析出 `serviceClass` 后，就可以直接定位到对应路由表。

然后根据 `binder_transaction_data.code` 判断是否命中某个代理方法。

---

## 5.4 Handle 替换原理

整个替换过程完全发生在用户态内存中。

`ioctl` 的第三个参数是一个指向用户空间结构体的指针：

```c
struct binder_write_read *bwr;
```

而 `binder_transaction_data` 又嵌套在 BWR 的写缓冲区中。

当 seccomp-notify 暂停系统调用后：

1. supervisor 读取这片用户态内存。
2. 找到其中的 `binder_transaction_data`。
3. 修改 `target.handle`。
4. 写回原地址。
5. 通知内核继续执行原始 `ioctl`。

此时 Binder 驱动继续处理 `ioctl` 时，从用户态缓冲区读到的已经是修改后的数据：

```
原始 handle → 代理服务 handle
```

因此驱动会自然地将事务路由到代理服务。

这个过程只修改一个字段：

```c
binder_transaction_data.target.handle
```

却把 Binder 路由交还给了 Binder 驱动本身完成。

这也是该方案最简洁的地方：

>
> 不重新实现 Binder 协议栈，只改变 Binder 驱动的路由目标。
>
>
>

---

## 六、第三部分：辅助系统

辅助系统维护各类映射关系，并为 supervisor 提供基础能力。

---

## 6.1 `code` → 方法名映射

辅助系统通过注解中声明的 `serviceClass`，在运行时反射对应 AIDL Stub 类中的 `TRANSACTION_*` 常量。

例如：

```
Stub.TRANSACTION_getInstalledPackages = 3
Stub.TRANSACTION_queryIntentActivities = 8
```

注解中的：

```kotlin
methodName = "getInstalledPackages"
```

会与：

```
TRANSACTION_getInstalledPackages
```

建立对应关系。

最终生成：

```
code → handler
```

例如：

```
3 → proxyGetInstalledPackages
```

---

## 6.2 服务名 → Handle 获取

辅助系统在代理服务启动时完成以下工作：

1. 通过 `ServiceManager.getService(serviceName)` 获取原始服务的 `IBinder`。
2. 从 `BpBinder` 中提取底层 handle 值。
3. 创建代理服务实例。
4. 将代理服务注册到 `ServiceManager`。
5. 获取代理服务自身的 handle，供 supervisor 替换时使用。

整体映射可以理解为：

```
serviceName
  → originalHandle
  → proxyHandle
```

例如：

```
package
  → 原始 PackageManager handle
  → 代理 PackageManager handle
```

---

## 6.3 BWR / Txn 解析函数

辅助系统提供 Binder 协议解析函数，用于 supervisor 中精确解析被拦截的 `ioctl` 数据。

主要包括：

- 解析 `binder_write_read`
- 遍历 write buffer
- 识别 `BC_TRANSACTION`
- 解析 `binder_transaction_data`
- 提取 `target.handle`
- 提取 `code`
- 读取接口描述符 `serviceClass`

这些函数是 supervisor 判断是否需要代理的基础。

---

## 6.4 代理服务生命周期管理

辅助系统还负责代理服务的启动和生命周期管理。

具体包括：

1. 根据 KSP 生成的路由表创建代理 Binder 对象。
2. 将代理服务注册到 `ServiceManager`。
3. 接收被转发过来的 Binder 调用。
4. 根据 `code` 查找对应代理函数。
5. 执行代理逻辑。
6. 将返回结果通过 Binder 返回给原始调用方。

代理服务本身不需要知道请求是如何被路由过来的。

从它的视角看，它只是一个普通 Binder 服务。

---

## 七、完整执行流程

下面以目标应用调用：

```kotlin
PackageManager.getInstalledPackages()
```

为例，展示一次完整代理过程。

---

## 7.1 编译期

开发者编写代理方法：

```kotlin
@ProxyMethod(
    serviceClass = "android.content.pm.IPackageManager",
    serviceName = "package",
    methodName = "getInstalledPackages"
)
fun proxyGetInstalledPackages(flags: Int, userId: Int): Any? {
    // 代理逻辑
}
```

KSP 处理器生成代理路由表：

```
serviceClass = android.content.pm.IPackageManager
serviceName  = package
code         = 3
handler      = proxyGetInstalledPackages
```

并生成对应代理服务类。

---

## 7.2 运行时初始化

初始化阶段完成：

1. 通过反射 `IPackageManager.Stub` 获取：

```
TRANSACTION_getInstalledPackages = 3
```
2. 将 `code = 3` 填入路由表。
3. 通过：

```kotlin
ServiceManager.getService("package")
```

获取原始服务 handle。
4. 创建代理服务实例。
5. 注册代理服务并获取代理服务 handle。
6. 安装 seccomp 过滤器。
7. 启动 supervisor。

---

## 7.3 运行时拦截

目标应用调用：

```kotlin
pm.getInstalledPackages()
```

此时流程如下：

```
1. libbinder 构造 binder_transaction_data

   target.handle = 原始 package 服务 handle
   code          = 3

2. libbinder 调用：

   ioctl(fd, BINDER_WRITE_READ, &bwr)

3. Seccomp-BPF 检测到：

   ioctl + BINDER_WRITE_READ

   返回 SECCOMP_RET_USER_NOTIF

4. Supervisor 读取 BWR

5. Supervisor 解析 BC_TRANSACTION

6. Supervisor 提取：
   - serviceClass = android.content.pm.IPackageManager
   - code = 3
   - target.handle = 原始 package handle

7. Supervisor 查询路由表：

   android.content.pm.IPackageManager
     → package
       → 3
         → proxyGetInstalledPackages

8. 命中代理规则

9. Supervisor 将：

   target.handle = 原始 package handle

   替换为：

   target.handle = 代理 package handle

10. Supervisor 写回 BWR

11. Supervisor 通知内核继续执行 ioctl

12. Binder 驱动读取修改后的 target.handle

13. Binder 驱动将事务投递到代理服务

14. 代理服务根据 code = 3 调用：

    proxyGetInstalledPackages()

15. 代理服务返回结果

16. 目标应用收到代理后的返回值
```

---

## 八、方案优势

## 8.1 零 Hook

该方案不修改：

- GOT 表
- PLT 表
- 代码段
- `libbinder.so`
- Java 层 Binder 缓存

也不需要：

- `mprotect`
- `ptrace`
- Inline Hook
- GotHook

所有操作都发生在系统调用通知和用户态内存数据修改层面。

---

## 8.2 利用 Binder 原生路由机制

方案只修改：

```c
binder_transaction_data.target.handle
```

之后的路由过程完全交给 Binder 驱动完成。

因此不需要重新实现：

- Binder 协议栈
- Parcel 编解码框架
- Binder 对象生命周期管理
- Binder 驱动调度逻辑

本质上，这是在利用 Binder 已有能力做转发。

---

## 8.3 编译期路由生成

通过 KSP 注解处理器，代理声明在编译期被收集和整理。

运行时只需要填充：

- 方法 code
- 原始服务 handle
- 代理服务 handle

代理路由结构在编译期就已经确定，运行时逻辑更简单。

---

## 8.4 性能路径清晰

Seccomp-BPF 过滤器在内核态执行粗过滤。

只有命中的：

```
ioctl + BINDER_WRITE_READ
```

才会进入 supervisor。

Supervisor 只需要做：

- BWR 解析
- 接口描述符匹配
- code 查表
- handle 替换

整体路径清晰，额外逻辑集中在 Binder 事务发起前。

---

## 8.5 低侵入性

相比传统 Hook 方案，该方案不会产生典型的 Hook 修改痕迹，例如：

- GOT 表被改写
- 代码段被 patch
- 内存页权限被临时改成可写可执行
- `libbinder.so` 函数入口被改写
- Java 层 Binder 缓存被替换

它更接近一种系统调用层面的代理调度机制。

---

## 九、与内核技术结合的扩展价值

升级版 AndProxy 最大的扩展价值，不只是“无 Hook”，而是它天然站在 **系统调用边界** 上。

传统 Binder 代理方案通常深植于：

- Java Framework 层
- `libbinder.so`
- 进程内 Hook 框架
- ServiceManager 缓存替换逻辑

这些方案很难和内核侧能力形成稳定协同。

而基于 `seccomp-notify` 的方案不同。

它的拦截点位于：

```
用户态 Binder 调用
  → ioctl 系统调用边界
    → Binder 驱动
```

这个位置天然适合与内核技术组合。

---

### 9.1 与 eBPF 结合

可以在内核侧通过 eBPF 观察或统计 Binder 相关行为，例如：

- 哪些进程发起了 Binder 调用
- 哪些服务被频繁访问
- 某些 code 的调用频率
- Binder 调用延迟
- 代理前后的行为差异

用户态 AndProxy 负责：

```
路由替换
```

内核侧 eBPF 负责：

```
观测、统计、审计、策略辅助
```

两者可以形成清晰分工。

---

### 9.2 与内核 Hook / Trace 机制结合

如果系统环境允许，还可以在内核侧通过 tracepoint、kprobe 或受控 inline patch 观察 Binder 驱动路径。

例如关注：

- `binder_ioctl`
- `binder_transaction`
- Binder 线程调度
- 目标服务进程唤醒
- Binder reply 返回路径

这样可以构建一套从用户态到内核态的完整 Binder 代理观测链路：

```
用户态：
  seccomp-notify 修改 handle

内核态：
  追踪 Binder 驱动如何路由事务

代理服务：
  执行业务代理逻辑
```

---

### 9.3 系统级透明代理能力

由于方案的核心动作发生在系统调用边界，因此它更容易扩展成系统级透明代理能力。

典型组合方式是：

```
用户态 AndProxy
  → 修改目标 Binder handle

内核态观测/策略模块
  → 记录、过滤、审计或辅助决策

代理 Binder 服务
  → 执行实际代理逻辑
```

这样，代理系统不再局限于某一个 Java API 或某一个 Hook 点，而是可以围绕 Binder 调用链构建更完整的策略层。

---

### 9.4 分层架构优势

这种架构的最大好处是分层明确：

| 层级 | 职责 |
|-|-|
| KSP 编译期 | 生成代理声明和路由表 |
| 用户态 seccomp 层 | 拦截 Binder ioctl，修改 handle |
| Binder 驱动 | 按 handle 完成原生路由 |
| 代理服务 | 执行业务逻辑 |
| 内核观测层 | 统计、审计、追踪和辅助策略 |

因此，它不只是一个 Binder 代理技巧，而是一个可以和内核观测、内核策略、系统级监控结合的代理框架基础。

---

## 十、局限

## 10.1 Android 版本限制

`seccomp-notify` 需要较新的内核支持。

典型目标环境为：

```
Android 12+
Linux kernel 5.10+
```

在更老的 Android 版本上，内核可能不支持 `SECCOMP_RET_USER_NOTIF`。

---

## 10.2 Binder fd 隔离

Android 存在多个 Binder 域：

- `/dev/binder`
- `/dev/vndbinder`
- `/dev/hwbinder`

不同 Binder 域服务不同的系统组件。

Supervisor 需要区分不同 Binder fd，避免错误代理。

---

## 10.3 并发处理复杂

Binder 调用高度并发。

目标进程可能有多个线程同时发起：

```c
ioctl(fd, BINDER_WRITE_READ, &bwr)
```

因此 supervisor 需要处理：

- 多线程通知
- 通知队列
- 请求超时
- 事务上下文隔离
- 并发写回安全

---

## 10.4 二次 IPC 开销

代理调用通常会变成：

```
原始调用方
  → 代理服务
    → 原始系统服务
      → 代理服务
        → 原始调用方
```

相比直接访问系统服务，多了一层 Binder 转发。

因此需要关注：

- 延迟增加
- 高频接口性能
- 大 Parcel 数据传输成本
- 代理服务线程池压力

---

## 10.5 接口描述符解析依赖 Binder 数据布局

Supervisor 需要从 Binder transaction 的数据缓冲区中解析接口描述符。

不同 Android 版本、不同 AIDL 生成模式、不同调用路径下，Parcel 数据布局可能存在差异。

因此解析逻辑需要做充分兼容。

---

## 结语

AndProxy 升级版的核心思想可以概括为一句话：

>
> 不 Hook `ioctl`，而是在 `ioctl` 真正进入 Binder 驱动前，修改它即将提交给驱动的 Binder transaction 数据。
>
>
>

它真正修改的只有一个字段：

```c
binder_transaction_data.target.handle
```

但这个字段正是 Binder 驱动进行路由的关键。

因此，该方案不需要重新实现 Binder 协议，也不需要侵入 `libbinder.so`，而是把 Binder 原生路由机制变成了代理能力的一部分。

从工程架构上看，它由三部分组成：

```
KSP 编译期生成路由
  → seccomp-notify 拦截 ioctl
    → Binder 驱动按替换后的 handle 路由
```

这种设计的价值不只是减少 Hook 痕迹，更重要的是把 Binder 代理能力放到了系统调用边界上。

这使它天然可以与 eBPF、内核 trace、内核策略模块等技术组合，形成从用户态代理到内核态观测的完整系统。

对于虚拟化、应用分身、隐私保护、行为审计等场景，这是一种比传统 Java 代理或 Native Hook 更干净、更分层、更容易扩展的 Binder 代理架构。

---

# 回复

## 回复 by jyotidwi (#2)

*2026-5-4 15:56*

谢谢分享

## 回复 by 孤木落 (#3)

*2026-5-4 15:57*

基于这个思路，实现了一个类似于CorePatch的内核模块，通过内核转发和注册系统服务，直接干掉签名校验

## 回复 by FMNS (#4)

*2026-5-4 16:16*

谢谢分享

## 回复 by 温泉划水鱼 (#5)

*2026-5-4 16:44*

看看

## 回复 by ClPrada (#6)

*2026-5-4 16:56*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_ldbucrik (#7)

*2026-5-4 17:06*

向大佬学习

## 回复 by mb_lpcoesnt (#8)

*2026-5-4 21:12*

厉害了

## 回复 by Viseris (#9)

*2026-5-4 22:54*

谢谢分享

## 回复 by 夜惜风雨 (#10)

*2026-5-5 10:31*

666666666666

## 回复 by Zepp7289 (#11)

*2026-5-5 11:02*

tql

## 回复 by SomeMx (#12)

*2026-5-5 12:23*

学习一下

## 回复 by 末日大哥 (#13)

*2026-5-5 13:38*

666

## 回复 by mb_4nrpVMxJ (#14)

*2026-5-5 14:18*

666

## 回复 by 恋一世的爱 (#15)

*2026-5-5 14:27*

看看老哥

## 回复 by 啊你好哇123 (#16)

*2026-5-5 14:28*

学习学习

## 回复 by 啊你好哇123 (#17)

*2026-5-5 14:28*

>
> [孤木落](https://bbs.kanxue.com/user-1044055.htm)
>  基于这个思路，实现了一个类似于CorePatch的内核模块，通过内核转发和注册系统服务，直接干掉签名校验
>

可以在应用层实现吗

## 回复 by 苏幻墨 (#18)

*2026-5-5 15:57*

谢谢分享

## 回复 by 孤木落 (#19)

*2026-5-5 18:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  啊你好哇123](https://bbs.kanxue.com/user-847178.htm)
>  可以在应用层实现吗
>

我在文章中探讨的seccomp就是在用户态实现的方法
ebpf方案我暂时没有分享

## 回复 by iBa0 (#20)

*2026-5-6 10:33*

123

## 回复 by Thehepta (#21)

*2026-5-6 10:34*

1

## 回复 by mJqalJqN (#22)

*2026-5-6 11:08*

1

## 回复 by mb_qimctavn (#23)

*2026-5-6 11:31*

6

## 回复 by amwpecel (#24)

*2026-5-6 11:36*

666

## 回复 by x_power (#25)

*2026-5-6 11:50*

666

## 回复 by wx_Dispa1r (#26)

*2026-5-6 15:22*

1

## 回复 by xingbing (#27)

*2026-5-6 16:49*

谢谢分享

## 回复 by PPTV (#28)

*2026-5-6 17:14*

666

## 回复 by 4Chan (#29)

*2026-5-6 19:26*

学习一下

## 回复 by mb_pesxllvn (#30)

*2026-5-7 11:10*

666

## 回复 by Gryffindoss (#31)

*2026-5-7 11:16*

6666

## 回复 by uniking (#32)

*2026-5-7 14:20*

谢谢分享

## 回复 by mb_elqwyvnm (#33)

*2026-5-7 14:23*

学习新思路

## 回复 by Imxz (#34)

*2026-5-8 10:53*

TQL

## 回复 by kingking888 (#35)

*2026-5-9 11:07*

666

## 回复 by huangbof (#36)

*2026-5-9 12:12*

通知内核继续执行

## 回复 by Ankeys (#37)

*2026-5-11 14:14*

666

## 回复 by 无视红绿灯 (#38)

*2026-5-12 09:39*

6666

## 回复 by Crack999 (#39)

*2026-5-12 14:12*

感谢分享

## 回复 by guardia (#40)

*2026-5-13 04:21*

learn

## 回复 by git_14248bibinocode (#41)

*2026-5-13 10:34*

谢谢分享

## 回复 by mb_ghcouuzx (#42)

*2026-5-14 14:50*

相关代码能分享下么？

## 回复 by 月落之汀 (#43)

*2026-5-15 17:03*

有几个实现细节想跟楼主交流确认一下，主要是“透明”和“转发”这块。

1. 文章里说的是透明代理，但我理解这里可能有两种完全不同的透明：
第一种是“对调用方App透明”。比如只针对某个App的某个Binder code，把 target.handle改到自己的代理服务，然后代理服务直接mock一个返回值，比如你说的签名校验直接返回通过。
这个场景我理解是成立的，因为App侧只看到这次 Binder调用返回了它期望的Parcel，确实没有标准办法知道到底是谁处理了这个transaction。

第二种是“对原始系统服务也透明”，链路就变成：
调用方 -> 代理服务 -> 原始系统服务 -> 代理服务 -> 调用方

这里我有个疑问：原始系统服务看到的caller不就变成代理服务了吗？比如getCallingUid/getCallingPid，应该都会变。如果没做处理，我理解就不能叫完整透明，只能说对调用方透明。

这里就明显跟你说的“不重新实现Binder协议栈，也不重新实现Parcel编解码”不一致了，如果代理服务要做转发、修改请求或修改返回，业务层还是要正确处理这些东西的，这个边界文章里感觉没说清楚。

2.基于上面这个问题，关于你的实现中，如果目标是system_server / PackageManagerService / 厂商自己的服务发起Binder请求，如果内部会检查 getCallingUid，这种怎么处理？
还是说这个方案的主要目标其实是App侧特定code的结果替换，比如签名校验、包信息查询这类，并不打算做通用透明转发？

PS：另外handle这块我理解应该是在目标进程内初始化时分别拿originalHandle和proxyHandle，因为Binder handle是进程独立的，如果不是目标进程内拿handle，就需要内核直接操作binder_ref，难度会高很多

## 回复 by 孤木落 (#44)

*2026-5-15 17:48*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>  有几个实现细节想跟楼主交流确认一下，主要是“透明”和“转发”这块。1.&nbsp;文章里说的是透明代理，但我理解这里可能有两种完全不同的透明：第一种是“对调用方App透明”。比如只针对某个Ap ...
>

请问你问的是ebpf方案还是seccomp方案?

## 回复 by 月落之汀 (#45)

*2026-5-15 18:01*

>
> [孤木落](https://bbs.kanxue.com/user-1044055.htm)
>  请问你问的是ebpf方案还是seccomp方案?
>

我理解我应该问的是ebpf的方案，如果方便交流的话，还请解惑，谢谢

## 回复 by 孤木落 (#46)

*2026-5-15 18:20*

>
> [月落之汀](https://bbs.kanxue.com/user-706309.htm)
>  我理解我应该问的是ebpf的方案，如果方便交流的话，还请解惑，谢谢
>

对不起，对于ebpf方案，我目前只是根据seccomp发散了一个思路，完善的代理技术还没有研究，也没有没有充分测试过，只跑过一个修改包信息查询的demo（gpt写的）。seccomp方案中这两个问题比较容易解决，也是我当前研究多开框架时主要使用的，暂时没有精力完善ebpf方案。

## 回复 by mb_ghcouuzx (#47)

*2026-5-16 22:40*

用这个实现  定位修改可以么？

## 回复 by wx_北极星_493 (#48)

*2026-5-19 13:11*

看看

## 回复 by 荧光之夏 (#49)

*2026-5-19 15:42*

666

## 回复 by huluxia (#50)

*2026-5-19 16:24*

牛逼6666

## 回复 by wlmf (#51)

*2026-5-20 09:17*

mark

## 回复 by mb_ahyhoece (#52)

*2026-5-20 17:14*

666

## 回复 by 三点水的湫 (#53)

*2026-5-20 22:45*

1

## 回复 by TeamAR (#54)

*2026-5-20 23:57*

666

## 回复 by mb_koixqizd (#55)

*2026-5-21 10:11*

学习

## 回复 by 受人以渔 (#56)

*2026-5-24 10:23*

12

## 回复 by 简单的简单 (#57)

*2026-5-24 23:42*

666

## 回复 by mb_mihutdve (#58)

*2026-5-26 10:42*

6666

## 回复 by ycdear (#59)

*2026-5-27 08:08*

111

## 回复 by GeQ1an (#60)

*2026-5-27 17:37*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_qzxqnktk (#61)

*2026-6-1 10:28*

666

## 回复 by dob_C (#62)

*2026-6-2 15:53*

感谢分享

## 回复 by wx_故事与酒 (#63)

*2026-6-2 16:16*

666666666666666666666666

## 回复 by 寻梦之璐 (#64)

*2026-6-3 23:28*

6666

## 回复 by 叶晓枫A (#65)

*2026-6-4 03:04*

学不完，根本学不完

## 回复 by mb_iuashfyi (#66)

*2026-6-7 20:09*

5

## 回复 by SInnon (#67)

*2026-6-8 16:24*

66666666

## 回复 by XCicada (#68)

*2026-6-8 16:53*

厉害

## 回复 by mb_ezmrnfsu (#69)

*2026-6-9 22:47*

666

## 回复 by SomeMx (#70)

*2026-6-14 08:35*

项目咋没了 佬

## 回复 by Superoot (#71)

*2026-6-18 14:32*

6666

## 回复 by mb_tewbhakr (#73)

*2026-6-19 21:42*

看看

## 回复 by mb_jegknedl (#74)

*2026-6-22 10:49*

学习

## 回复 by Snowman_Liam (#75)

*2026-6-22 11:28*

6666

## 回复 by mb_ebaajipv (#76)

*2026-6-22 18:16*

666

## 回复 by zhangminnn (#77)

*2026-6-23 20:56*

66666

## 回复 by ulong9527 (#78)

*2026-6-26 09:48*

感谢分享，学习一下

## 回复 by 白毅 (#79)

*2026-6-27 20:20*

tql

## 回复 by wx_kx92911 (#80)

*2026-7-15 09:48*

感谢分析

## 回复 by mb_degalzhb (#81)

*2026-7-15 14:40*

666

## 回复 by wx_Kerberos (#82)

![image](https://bbs.kanxue.com/view/img/face/001.gif)
