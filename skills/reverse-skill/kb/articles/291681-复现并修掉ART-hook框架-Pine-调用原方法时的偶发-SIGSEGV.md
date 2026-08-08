---
title: '[原创]复现并修掉ART hook框架 Pine 调用原方法时的偶发 SIGSEGV'
url: https://bbs.kanxue.com/thread-291681.htm
tid: 291681
author: 太岁又沐风
date: '2026-06-18'
tags: [Android安全, 原创]
crawled_at: '2026-08-08T10:07:03+00:00'
replies: 22
---

# 复现并修掉ART hook框架 Pine 调用原方法时的偶发 SIGSEGV

Pine（[canyie/pine](https://github.com/canyie/pine)）是目前用得比较多的 ART 方法 hook 框架。它有一个老问题：调用被 hook 方法的**原实现**时，偶发 native `SIGSEGV`，概率性、堆栈不固定、重启可能就好。上游源码在出事的那一行留了 FIXME，但一直没修：

```java
// FIXME: GC happens here (you can add Runtime.getRuntime().gc() to test) will crash backup calling
\```

本文做三件事：把这个崩溃在真机上**确定性复现**、拿到崩溃栈、定位到具体那一次内存读；分析根因，并说明几条看起来能修、其实不行的路；给出修法，换上修复版重新跑、拿到不崩的日志。修复已合入 Pine 的 fork（[taisuii/tine](https://github.com/taisuii/tine)）。

测试环境：Pixel 6 Pro / Android 16（API 36）/ arm64-v8a。Android 13+ 默认 GC 是 userfaultfd 的 CMC（Concurrent Mark Compact），**会搬动对象**，正好命中。开机日志可见 `Using CollectorTypeCMC GC.`。

---

## 一、先理清三个东西

不铺垫原理后面看不懂，但只讲后面要用到的。

**1）backup 方法，以及它为什么“游离”在 GC 视野之外。**
Tine 走方法替换：把目标方法的 `ArtMethod` 入口指向自己的 trampoline，同时**克隆一份原方法**叫 backup，你调原实现时跑的就是它。关键在这份克隆怎么来的（`core/src/main/cpp/art/art_method.h`）：

```cpp
static ArtMethod* New() {
    return static_cast<ArtMethod*>(malloc(size));
}
\```

它是 `malloc` 出来的裸内存，**既不在 ART 托管堆上，也不挂在任何类的方法数组里**。换句话说，运行时根本不知道有这么一个 `ArtMethod` 存在——这一点后面是核心。

**2）`declaring_class` 是一个 32 位压缩 GcRoot。**
`ArtMethod` 里有 `declaring_class`，指向方法所属的 `mirror::Class`。ART 中堆引用普遍用 32 位压缩引用存储，所以它实际是个 `uint32_t`，native 侧就是按 `uint32_t` 读写：

```cpp
uint32_t declaring_class = origin->GetDeclaringClass();
backup->SetDeclaringClass(declaring_class);
\```

GcRoot 的含义是：GC 在回收/压缩时会**遍历所有 root 并就地修正它们**。但前提是这个 root 能被 GC 扫描到。真实方法的 `declaring_class` 能被扫到（下面讲路径），游离的 backup 扫不到。

**3）移动 GC 与安全点。**
“移动式 GC”会在回收时搬动存活对象来压缩内存，对象地址因此改变，所有指向它的引用都要被同步修正。Android 8~12 默认 CC（并发拷贝），13+ 默认 CMC（并发标记-压缩），都会搬；4.4 及以下不会搬。并发 GC 不能在任意指令处搬对象，它要等线程到达**安全点**（方法调用、分配、循环回边、JNI 转换等）才动手。“移动只发生在安全点”这条性质，是后面修复能成立的支点。

---

## 二、复现

逻辑很简单：hook 一个静态方法 `victim`，然后在堆分配压力下反复调它的原实现。每次调用都会走一遍 `callBackupMethod`，也就是崩溃窗口。

```java
public class GcBugReproActivity extends Activity {
    public static int victim(int x) { return (x * 31) ^ (x >>> 3); }  // 被 hook 的方法

    private void run() {
        Method m = GcBugReproActivity.class.getDeclaredMethod("victim", int.class);
        Tine.hook(m, new MethodHook() {
            @Override public void beforeCall(Tine.CallFrame f) { }
            @Override public void afterCall(Tine.CallFrame f) { }
        });
        long sum = 0;
        for (int i = 0; i < 200_000; i++) {
            Object[] garbage = new Object[32];                 // 给压缩器制造可搬运的垃圾
            for (int j = 0; j < 32; j++) garbage[j] = new byte[512];
            sum += victim(i);                                  // -> beforeCall -> callBackupMethod -> afterCall
        }
        Log.i("TineGcRepro", "REPRO_SURVIVED iterations=200000 sum=" + sum);
    }
}
\```

`victim` 是静态方法，它的 declaring class 就是 `GcBugReproActivity`——一个应用类，位于可移动空间，会被 moving GC 搬动。

光靠分配压力撞 GC 是概率性的。为了**每次必中**，复现构建把 `callBackupMethod` 还原成上游 Pine 的原始写法，并按 FIXME 的提示在窗口里强制一次 GC：

```java
// 复现构建：还原上游行为
Class<?> declaring = origin.getDeclaringClass();
syncMethodInfo(origin, backup, hookRecord.skipUpdateDeclaringClass);  // 把当前 declaring_class 抄进 backup
Runtime.getRuntime().gc();                                            // 窗口里强制一次移动 GC
Object result = backup.invoke(thisObject, args);                      // 这里读到的就是被搬走后的野指针
declaring.getClass();                                                 // 上游试图“续命”，注释自己写了 (invalid for now)
return result;
\```

这样每次 backup 调用都精确地“补写最新地址 → 立刻把类搬走 → 再去用它”，命中率 100%。

---

## 三、崩溃日志（真机）

装上复现构建，`am start` 拉起，进程秒崩。logcat（已裁剪）：

```python
I TineGcRepro: REPRO_START device=Pixel 6 Pro Android=16 API=36 abi=arm64-v8a
I TineGcRepro: hook installed; hammering backup calls under GC pressure...
I d.tine.examples: Explicit concurrent mark compact GC freed 2673KB AllocSpace bytes, 92% free, ...
F libc    : Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x10 in tid (tine-gc-repro)
F DEBUG   : signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0000000000000010 (read)
F DEBUG   :     x2 0000000000000010   x3 656800656e696c5f   ...
F DEBUG   : backtrace:
F DEBUG   :   #00 libart.so (art::mirror::Class::GetDescriptor(std::string*)+76)
F DEBUG   :   #01 libart.so (art::mirror::Class::PrettyDescriptor()+44)
F DEBUG   :   #02 libart.so (art::mirror::Class::PrettyClass()+124)
F DEBUG   :   #03 libart.so (art::ClassLinker::InitializeClass(...)+1928)
F DEBUG   :   #04 libart.so (art::ClassLinker::EnsureInitialized(...)+156)
F DEBUG   :   #05 libart.so (art::InvokeMethod<(art::PointerSize)8>(...)+1876)
F DEBUG   :   #06 libart.so (art::Method_invoke(...)+32)
\```

逐帧读：`#06 Method_invoke` → `#05 InvokeMethod` 是 `Method.invoke` 的 native 实现；它在真正执行前要做**类初始化检查** `#04 EnsureInitialized` → `#03 InitializeClass`，期间去取类名 `#02 PrettyClass` → `#01 PrettyDescriptor` → `#00 GetDescriptor`，在这里读了一个坏掉的 `Class*` 而崩。

再看寄存器：`fault addr 0x10`、`x2 = 0x10`，是在一个近乎为空的 `Class*` 上读偏移 `0x10`；`x3 = 0x656800656e696c5f` 按小端解出来是 `_line\0he` 这样的字符串字节——说明这个 `Class*` 指向的内存**已经被搬走/释放、又被填进了别的数据**。野指针读，证据确凿。

崩溃前那行 `Explicit concurrent mark compact GC` 就是我们强制的 `Runtime.getRuntime().gc()` 触发的一次 **CMC 移动压缩**。时间线完全对上。

---

## 四、根因

![图1：移动 GC 如何让 backup 的 declaring_class 变成野指针](https://bbs.kanxue.com/upload/attach/202606/957122_YRGUZP4UHXR2D3D.png)

**为什么真实方法没事、backup 出事？** 因为 GC 修正 `declaring_class` 是靠遍历 root，而 root 只有两类路径能覆盖到一个 `ArtMethod`：一是它所属类的方法数组（GC 扫到类时会顺带访问类里每个方法的 `declaring_class` root），二是活动栈帧（正在执行的帧上的方法会被栈扫描访问到）。真实方法挂在类的方法数组里，所以类一搬动它就被同步修正；而 backup 是 `malloc` 出来、不挂任何类、当时也没在栈上执行——**两条路径都不覆盖它**，于是它的 `declaring_class` 在压缩后变成指向旧地址的野指针。

**窗口在哪？** 上游用一次调用前补写来掩盖：`syncMethodInfo` 把真实方法当前的 `declaring_class` 抄进 backup，然后 `backup.invoke`。问题就在这两步**之间**。`Method.invoke` 的路径很长、安全点密集（参数装箱、数组分配、**类初始化检查**），补写完、还没真正进 backup 栈帧时，任意一个安全点触发移动 GC，类被搬走，紧接着 `EnsureInitialized` 去读 `declaring_class`——就是第三节那条崩溃栈。

**一个关键观察：** backup 一旦真正跑在栈帧上就安全了，因为栈扫描会就地修正帧上方法的 `declaring_class`。所以真正危险的，只有“补写完”到“backup 栈帧对栈扫描可见”这一小段；而移动只发生在安全点。结论：**只要这一小段里类不能移动，竞态就不存在**。

**一条容易踩的错觉：让类“活着”不等于让它“不动”。** 有人会想：那我对 declaring class 加个 JNI 全局引用、或在 Java 里留个强引用把它钉住不就行了？不行。强引用只保证类不被回收，移动 GC 照样会搬它，并且会去更新**那个被跟踪的引用槽**——但 backup 里的 `declaring_class` 是一个独立的裸 `uint32_t`，根本不是被跟踪的槽，它仍然变野。上游那句 `declaring.getClass()` 即便真把 `declaring` 钉在了栈上，被就地更新的也是那个**局部变量的槽**，跟 backup 的字段是两码事——所以它注释里写了 `(invalid for now)`。要么让 backup 成为被跟踪的 root（改动太大，等于重写 Pine 的内存模型），要么在这段窗口里**别让类动**。我们选后者。

---

## 五、修复

![图2：崩溃窗口 vs 修复，一次 backup 调用的时序](https://bbs.kanxue.com/upload/attach/202606/957122_2N92HTXN7DT4BFE.png)

### 5.1 只禁移动，不停世界

第一反应可能是 `ScopedSuspendAll` 把 VM 停掉，或用 `ScopedGCCriticalSection` 把整段调用圈起来禁掉所有 GC。这两种都不能用：backup 会执行**任意用户代码**，里面随时分配对象、触发 allocation GC；一旦把回收能力也卡死，被调用代码里分配触发的 GC 推不动，结果是**死锁或假性 OOM**。

正确粒度是只关**移动**、保留回收。ART 里有现成原语：`art::gc::Heap::IncrementDisableMovingGC` / `DecrementDisableMovingGC`——这正是 `GetPrimitiveArrayCritical` 持有裸堆指针期间用的同一把锁（JNI 给你裸数组指针时，也必须保证这段时间堆不压缩，道理一模一样）。

### 5.2 `IncrementDisableMovingGC` 到底干了什么

它不复杂，但有两个对我们至关重要的语义：一是把 `Heap` 里的 `disable_moving_gc_count_` 计数器加一，计数器 > 0 期间收集器不会选择压缩式回收（非移动回收照常）；二是如果调用时**正好有一次移动 GC 在进行**，它会先 `WaitForGcToComplete` 等它跑完再返回。计数器式意味着它**可重入**——嵌套/递归 backup 安全；“等在途 GC 跑完”这一点，是下面顺序能成立的关键。

### 5.3 Java 侧：先禁 GC、再 sync、后 invoke

```java
long gcGuard = beginCallBackup();   // IncrementDisableMovingGC + 等在途移动 GC 跑完
try {
    syncMethodInfo(origin, backup, hookRecord.skipUpdateDeclaringClass);
    return backup.invoke(thisObject, args);
} finally {
    endCallBackup(gcGuard);         // DecrementDisableMovingGC
}
\```

三步顺序是铁律。`beginCallBackup()` 返回时，移动已被禁、在途的也已结束，类停在它的**最终地址**上；此时 `syncMethodInfo` 抄进 backup 的就是最终地址，并且在 `endCallBackup()` 之前类不可能再动。先前那个窗口被彻底关死。顺序反了就没意义：先 sync 再禁，sync 抄进去的地址仍可能在禁之前被搬走。

### 5.4 native 侧：一对 RAII guard

`begin/end` 对应一个 RAII 对象的生命周期，指针当 cookie 透传回 Java：

```cpp
jlong Tine_beginCallBackup(JNIEnv* env, jclass) {
    return reinterpret_cast<jlong>(new tine::ScopedDisableMovingGc(art::Thread::Current(env)));
}
void Tine_endCallBackup(JNIEnv*, jclass, jlong cookie) {
    delete reinterpret_cast<tine::ScopedDisableMovingGc*>(cookie);
}
\```

`ScopedDisableMovingGc` 仿照项目已有的 `ScopedSuspendVM`，构造 increment、析构 decrement，符号不可用时 `active_=false`、整体退化为 no-op：

```cpp
class ScopedDisableMovingGc {
public:
    explicit ScopedDisableMovingGc(void* self)
            : self_(self), active_(Android::CanDisableMovingGc()) {
        if (LIKELY(active_)) Android::IncrementDisableMovingGc(self_);
    }
    ~ScopedDisableMovingGc() {
        if (LIKELY(active_)) Android::DecrementDisableMovingGc(self_);
    }
private:
    void* self_;
    bool active_;
};
\```

### 5.5 怎么拿到 `art::gc::Heap*`

`IncrementDisableMovingGC` 是 `Heap` 的成员函数，调它得先有 `this`——进程里唯一的 `Heap` 实例。ART 不导出它，从符号里抠。函数符号按 mangled name 解析：

```cpp
increment_disable_moving_gc_ = GetSymbolAddress("_ZN3art2gc4Heap22IncrementDisableMovingGCEPNS_6ThreadE");
decrement_disable_moving_gc_ = GetSymbolAddress("_ZN3art2gc4Heap22DecrementDisableMovingGCEPNS_6ThreadE");
\```

`Heap*` 走 `Runtime::instance_`（全局单例）→ `Runtime::GetHeap()`：

```cpp
void** instance_ptr = GetSymbolAddress("_ZN3art7Runtime9instance_E");
void*  runtime      = instance_ptr ? *instance_ptr : nullptr;
auto   get_heap     = GetSymbolAddress("_ZNK3art7Runtime7GetHeapEv");  // const 版
if (!get_heap) get_heap = GetSymbolAddress("_ZN3art7Runtime7GetHeapEv"); // 兜底
if (get_heap) heap_ = get_heap(runtime);
\```

这里**刻意没有**去猜 `heap_` 在 `Runtime` 结构里的偏移然后硬读。`Runtime` 很大、`heap_` 离任何可校验锚点都远、偏移随版本漂移；猜错的代价不是“拿到 null”，而是把一个**错位指针**喂进 `IncrementDisableMovingGC` 解引用，比正在修的 bug 更致命。所以宁可只走 `GetHeap()`：它若在某些 ROM 上被 inline、未导出，就拿不到，拿不到就退化。按版本标定 offset 可以作为后续，默认不冒险。

### 5.6 降级与零回归

`CanDisableMovingGc()` 要求 `heap_` 和两个函数指针**全部**非空；任一缺失即返回 false，guard 变 no-op，`callBackupMethod` 只剩 `syncMethodInfo` 那行惰性补写——**和改动前完全一致**。即：能生效的设备上关死竞态，不能生效的设备上隐身，不引入任何新失败模式。另外 Android 4.4 及以下没有移动 GC，初始化时直接 return，连符号都不解析。

涉及改动：`android.h`（函数指针 + `CanDisableMovingGc` + `ScopedDisableMovingGc`）、`android.cpp`（`InitDisableMovingGc`）、`tine.cpp`（`begin/endCallBackup` JNI 桥）、`Tine.java`（`callBackupMethod` + native 声明），以及 `AutomatedTest` 里新增的并发 GC 压力步骤。

---

## 六、验证

**换修复版重跑。** 复现 APK 一字不改，只把 core 换成带补丁的版本，同样 20 万次循环 + 同样 GC 压力：

```python
I TineGcRepro: hook installed on victim(int); hammering backup calls under GC pressure...
I Tine    : handleCall for method public static int ...GcBugReproActivity.victim(int)
   ... 20 万次调用全部正常返回 ...
I TineGcRepro: REPRO_SURVIVED iterations=200000 sum=620002257824
\```

同一台机器、同一套压力：复现构建第一批迭代内必崩，修复构建跑满 20 万次正常退出。

**回归压力测试。** `AutomatedTest` 里加了一步：一个线程持续 `Runtime.getRuntime().gc()`，另一个线程疯狂调用被 hook 方法的原实现，长时间不崩。

**线上判断 guard 是否生效（logcat）：**

- `Moving-GC guard for backup calls enabled (heap=0x...)` → guard 已激活；
- `Could not resolve art::gc::Heap*` → 符号缺失，已安全退化；
- 一个间接但有力的信号：`GC moved declaring class ...` 这条日志**降到 0**——因为 backup 调用期间类不再移动，自然没有“搬动后补写”这回事了。

---

## 七、适用范围

修复覆盖 Android L(5.0) 到 V(15)，以及上面实测的 Android 16（CMC）。KitKat 及以下没有移动 GC，不受影响、guard 直接短路。完整 diff 与按版本的兼容说明见仓库 `docs/moving-gc-backup-fix.md`，编好的 AAR 在 Releases。

上游框架：[canyie/pine](https://github.com/canyie/pine)。本文复现工程与修复在其 fork [taisuii/tine](https://github.com/taisuii/tine)。

---

# 回复

## 回复 by mb_jnmxfjku (#2)

*2026-6-18 18:08*

666

## 回复 by 恋一世的爱 (#3)

*2026-6-19 01:06*

6666666

## 回复 by SomeMx (#4)

*2026-6-19 02:09*

过来瞧瞧

## 回复 by mb_tewbhakr (#5)

*2026-6-19 02:50*

看看

## 回复 by wx_Huber Barrientos (#6)

*2026-6-19 12:14*

666

## 回复 by haris4687 (#7)

*2026-6-19 18:09*

66

## 回复 by mb_zoyhhbnr (#8)

*2026-6-19 19:46*

6666

## 回复 by Imxz (#9)

*2026-6-21 09:33*

tql

## 回复 by mb_pesxllvn (#10)

*2026-6-21 11:14*

666

## 回复 by mb_qimctavn (#11)

*2026-6-22 06:15*

6

## 回复 by huangjw (#12)

*2026-6-22 14:32*

看看先

## 回复 by iBa0 (#13)

*2026-6-22 15:11*

111

## 回复 by ~Smile (#14)

*2026-6-22 18:28*

666

## 回复 by wx_北极星_493 (#15)

*2026-6-24 11:06*

看看

## 回复 by huangbof (#16)

*2026-6-24 17:19*

666

## 回复 by mb_alztilld (#17)

*2026-6-30 16:24*

666

## 回复 by cantalou (#18)

*2026-7-7 15:16*

地方

## 回复 by dfJerry (#19)

*2026-7-7 17:11*

55556666

## 回复 by wx_kx92911 (#20)

*2026-7-9 09:53*

感谢分析

## 回复 by kingking888 (#21)

*2026-7-9 10:05*

666

## 回复 by 学编程 (#22)

*2026-7-10 11:07*

666

## 回复 by wx_Kerberos (#23)

*2026-7-28 19:56*

![image](https://bbs.kanxue.com/view/img/face/027.gif)
