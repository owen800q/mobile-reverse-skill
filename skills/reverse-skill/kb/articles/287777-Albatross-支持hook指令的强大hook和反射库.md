---
title: '[原创]Albatross 支持hook指令的强大hook和反射库'
url: https://bbs.kanxue.com/thread-287777.htm
tid: 287777
author: WanQing
date: '2025-07-27'
tags: [Android安全, 原创, 基础理论, 逆向分析, 协议分析, 脱壳反混淆, 程序开发, HOOK注入, 系统相关, 源码框架]
crawled_at: '2026-07-31T15:43:36+08:00'
replies: 150
---

# Albatross 指令级 Hook 功能详解

Albatross 是一个功能强大的 Android Hook 框架，不仅支持方法级别的 Hook，现在还支持**指令级别的 Hook**，允许开发者在 Android 7（Nougat）到最新的 Android 16之间，对任意方法中的某条或某段 Dalvik 字节码指令的运行结果进行监控和修改。以下将介绍 Albatross 的指令级 Hook 功能，包括虚拟机模型、寄存器分配机制以及具体 API 的使用方式，并通过一个完整示例进行演示。

## [项目地址](https://github.com/AlbatrossHook/AlbatrossAndroid)

## 一、栈虚拟机 vs 寄存器虚拟机

在深入 Albatross 的指令 Hook 之前，我们先了解 Android ART 虚拟机使用的 **寄存器模型**，以及它与传统的 **栈模型** 的区别。

### 1. 栈虚拟机（Stack-based VM）

- 操作数通过**栈**来传递。
- 每条指令操作的输入和输出都压入/弹出栈。
- 例如：`add` 指令会从栈顶取出两个数相加，结果再压入栈。

优点：结构简单，易于实现。
缺点：频繁的栈操作导致性能较差。

### 2. 寄存器虚拟机（Register-based VM）

- 使用**虚拟寄存器**（v0, v1, v2...）存储操作数。
- 指令直接操作寄存器，无需栈操作。
- Android 的 ART 虚拟机使用的是寄存器模型。

优点：减少内存访问，提升性能。
缺点：指令编码更复杂。

---

## 二、Android ART 虚拟机寄存器分配机制

在 ART 虚拟机中，每个方法都有一个**虚拟寄存器池**，数量由 `.registers` 伪指令指定。这些寄存器用于保存局部变量、参数和中间计算结果。

### 1. 寄存器分配规则

- `v0~vn`：通用寄存器，数量由 `.registers N` 指定。
- 方法参数：
	- 静态方法：参数从 `p0` 开始。
	- 实例方法：`p0` 是 `this`，参数从 `p1` 开始。
- 每个寄存器占 4 字节，对于 64 位类型（如 `long`、`double`），使用两个连续寄存器。

### 2. 示例代码片段

```
.method public getCaller(Landroid/view/View;)V
    .registers 7
    .param p1, "view" # Landroid/view/View;

    .line 180
    invoke-static {}, Lqing/albatross/core/Albatross;->getCallerClass()Ljava/lang/Class;
    move-result-object v0
```

- `.registers 7` 表示方法使用了 7 个虚拟寄存器（v0~v6）。
- `invoke-static` 不需要参数，结果存入 v0。
- `move-result-object v0` 将结果从栈顶移动到寄存器 v0。

---

## 三、Albatross 指令级 Hook API

Albatross 提供了以下核心 API 来进行指令级 Hook：

### 1. Hook 指令 API

| 1 | `public` `static` `InstructionListener hookInstruction(Member member,` `int` `minDexPc,` `int` `maxDexPc, InstructionCallback callback)` |
|-|-|

#### 参数说明：

| 参数 | 类型 | 说明 |
|-|-|-|
| `member` | `Member` | 要 Hook 的方法（Method/Constructor） |
| `minDexPc` | `int` | 起始 Dalvik PC 值（包括） |
| `maxDexPc` | `int` | 结束 Dalvik PC 值（包括） |
| `callback` | `InstructionCallback` | 指令执行时的回调 |

- **返回值**：`InstructionListener`对象，用于后续解除hook（调用`unHook()`方法）。

### 2. 回调接口 `InstructionCallback`

| 123 | `public` `interface` `InstructionCallback {``void` `onEnter(Member method, Object self,` `int` `dexPc, InvocationContext invocationContext);``}` |
|-|-|

#### 参数说明：

| 参数 | 类型 | 说明 |
|-|-|-|
| `method` | `Member` | 当前执行的方法 |
| `self` | `Object` | 方法调用者（`this`,静态方法为null) |
| `dexPc` | `int` | 当前 Dalvik PC 值 (偏移量) |
| `invocationContext` | `InvocationContext` | 当前执行上下文，用于读写寄存器 |

### 3. `InvocationContext` API

该类提供了对当前执行上下文中虚拟寄存器的访问能力：

#### 读取寄存器值：

- `int NumberOfVRegs()`:寄存器的数量，读写寄存器切记不能越界
- `int GetVRegInt(int i)`：读取整型值
- `float GetVRegFloat(int i)`：读取浮点值
- `long GetVRegLong(int i)`：读取长整型值（占用i和i+1）
- `Object GetVRegReference(int i)`：读取对象
- `short GetVRegShort(int i)`:读取short值
- `boolean GetVRegBool(int i)` 读取boolean值

#### 写入寄存器值：

- `int SetVRegInt(int i, int val)`:设置int类型寄存器值
- `void SetVRegReference(int i, Object val)`:写入对象
- `float SetVRegFloat(int i, float val)`:写入浮点数
- `long SetVRegLong(int i, long val)`:设置long类型寄存器值（占用i和i+1）
- `double SetVRegDouble(int i, double val)`:设置double类型寄存器值（占用i和i+1）
- `int SetVRegBoolean(int i, boolean val)`：写入boolean值

#### 获取参数：

- `int GetParamInt(int i)`:获取第i个参数的int值。
- `Object GetParamReference(int i)`:获取第i个参数对象,如果只是数值类型（int,long,float等），读取对象将会导致jvm崩溃
- `float GetParamFloat(int i)`:获取第i个参数的float。
- `long GetParamLong(int i)`:获取第i个参数的long(会读i和i+1两个寄存器的值)。

---

## 四、示例演示

以下是一个完整的指令级 Hook 示例，展示了如何 Hook `getCaller(View)` 方法的指令，修改运行过程中的值。

### 1. 被 Hook 的方法

| 1234 | `public` `void` `getCaller(View view) {``Class<?> caller = Albatross.getCallerClass();``textView.setText(``"caller:"` `+ caller.getName() +` `":"` `+ callerCount++);``}` |
|-|-|

对应的 Dalvik 指令：

```
// 寄存器数量：7个（v0-v6，p0-p1）
.registers 7
// 调用Albatross.getCallerClass()并将结果存入v0

invoke-static {}, Lqing/albatross/core/Albatross;->getCallerClass()Ljava/lang/Class;
move-result-object v0
// 后续逻辑：使用v0的值构建字符串并更新textView
```

Dalvik PC = 4 对应 `move-result-object` 指令执行完。

### 2. Hook 代码

通过hookgetCaller方法中dexPc=0到dexPc=10的指令范围，在dexPc=4（即move-result-object v0指令执行时）修改v0寄存器的值，将调用者类改为当前类。

| 1234567891011121314151617181920212223242526272829303132 | `InstructionListener listener =` `null``;` `public` `void` `instruction(View view)` `throws` `NoSuchMethodException {``if` `(listener ==` `null``) {``Method getCaller = AlbatrossDemoMainActivity.``class``.getDeclaredMethod(``"getCaller"``, View.``class``);``listener = Albatross.hookInstruction(getCaller,` `0``,` `10``, (method, self, dexPc, invocationContext) -> {``assert` `dexPc <=` `10``;``assert` `dexPc >=` `0``;``assert` `method == getCaller;``assert` `self == AlbatrossDemoMainActivity.``this``;``assert` `invocationContext.NumberOfVRegs() ==` `7``;` `Albatross.log(``"onEnter:"` `+ dexPc);` `Object receiver = invocationContext.GetParamReference(``0``);``assert` `receiver == self;` `Object v = invocationContext.GetParamReference(``1``);``assert` `(v` `instanceof` `View);` `if` `(dexPc ==` `4``) {``// Hook Dalvik PC == 4 的指令``// 原始调用：Albatross.getCallerClass()``// 修改为返回当前类 AlbatrossDemoMainActivity.class``invocationContext.SetVRegReference(``0``, AlbatrossDemoMainActivity.``class``);``}``});``}` `else` `{``listener.unHook();``listener =` `null``;``}``}` |
|-|-|

### 3. 效果说明

- 未hook时：`textView`显示实际调用者类名。
- hook生效后：由于v0寄存器被修改为`AlbatrossDemoMainActivity.class`，`textView`将显示当前类名，实现了对方法执行逻辑的精细篡改。
- 我们将 `invoke-static` 返回的 `Class<?>` 值改为 `AlbatrossDemoMainActivity.class`。
- 最终 `textView.setText()` 显示的内容将变为：

| 1 | `caller:qing.albatross.demo.AlbatrossDemoMainActivity:``0` |
|-|-|

---

## 五、应用场景与注意事项

### 应用场景

- **调试**：实时查看方法中某条指令的寄存器状态。
- **注入**：在特定指令插入自定义逻辑（如日志、安全检查）。
- **绕过逻辑**：可针对单个指令Hook，实现更细粒度的逻辑干预。
- **逆向分析**：分析第三方 APK 的执行流程。

### 注意事项

- Dalvik PC 值是相对偏移量，编译器优化可能会导致指令变化，请根据自己编译的代码分析。
- Hook 指令时需确保寄存器索引正确，避免越界。
- Hook 范围应尽量精确，避免影响性能。
- 建议在 Release 版本关闭指令 Hook，尽量使用方法hook。

---

## 六、总结

Albatross 的指令级 Hook 功能为 Android 开发者提供了前所未有的灵活性和控制力。通过理解 ART 虚拟机的寄存器模型和 Dalvik 指令结构，开发者可以在任意方法的任意指令位置插入自定义逻辑，实现高级调试、行为注入、逻辑绕过等功能。

结合 `InstructionCallback` 和 `InvocationContext`，开发者可以实时读写寄存器内容，甚至修改执行流程，这使得 Albatross 成为 Android 动态分析和逆向工程的利器。

**提示**：如需获取 Dalvik PC 值，可使用 `jadx-gui` 或 `smali` 工具查看反编译代码中的 `.line` 和指令偏移。

---

# 回复

## 回复 by 希梦☆奈何 (#2)

*2025-7-27 10:34*

路过看看

## 回复 by 夜惜风雨 (#3)

*2025-7-27 11:06*

66666

## 回复 by anenn (#4)

*2025-7-27 11:14*

学习了~

## 回复 by Cure. (#5)

*2025-7-27 11:31*

6

## 回复 by SomeMx (#6)

*2025-7-27 11:47*

学习一下

## 回复 by mb_ldbucrik (#7)

*2025-7-27 13:36*

感谢分享

## 回复 by poomtoom (#8)

*2025-7-27 16:27*

感谢分享的内容！

## 回复 by 财神爷999 (#9)

*2025-7-28 01:16*

感谢分享

## 回复 by 恋一世的爱 (#10)

*2025-7-28 02:26*

看下。好像so层没开源是吧

## 回复 by 拍拖 (#11)

*2025-7-28 08:45*

学习一下

## 回复 by 西瓜帅 (#12)

*2025-7-28 09:12*

学习学些

## 回复 by WanQing (#13)

*2025-7-28 09:20*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  恋一世的爱](https://bbs.kanxue.com/user-825246.htm)
>
>  看下。好像so层没开源是吧
>
>

是的，等一段时间

## 回复 by chenshipei (#14)

*2025-7-28 10:18*

学习一下

## 回复 by k4y0z (#15)

*2025-7-28 10:49*

666

## 回复 by wx_插曲 (#16)

*2025-7-28 11:37*

学习一下

## 回复 by XCicada (#17)

*2025-7-28 14:49*

学习一下

## 回复 by dfJerry (#18)

*2025-7-28 15:09*

6666

## 回复 by xx_dd_y (#19)

*2025-7-28 15:58*

66666

## 回复 by Superoot (#20)

*2025-7-28 16:12*

66666666666666

## 回复 by 大魔头 (#21)

*2025-7-28 17:20*

666

## 回复 by 我是小奥 (#22)

*2025-7-28 21:55*

学习一下

## 回复 by jdong (#23)

*2025-7-29 09:32*

学习一下

## 回复 by Imxz (#24)

*2025-7-29 09:33*

tql

## 回复 by jilay (#25)

*2025-7-29 10:23*

mark

## 回复 by 繁华皆成空 (#26)

*2025-7-29 10:29*

666

## 回复 by 不知世事 (#27)

*2025-7-29 11:09*

1

## 回复 by wx_喵夫 (#28)

*2025-7-29 11:19*

学习一下

## 回复 by Thehepta (#29)

*2025-7-30 14:31*

mark

## 回复 by artake (#30)

*2025-7-30 16:31*

niu

## 回复 by uni7corn (#31)

*2025-7-30 16:35*

mark

## 回复 by ziyunlll (#32)

*2025-7-30 20:10*

mark

## 回复 by 海带 (#33)

*2025-7-31 09:44*

111

## 回复 by 无视红绿灯 (#34)

*2025-7-31 10:05*

66666

## 回复 by Ankeys (#35)

*2025-7-31 10:08*

gkd

## 回复 by dancheng (#36)

*2025-7-31 10:14*

mark

## 回复 by X14Nuy7 (#37)

*2025-7-31 11:30*

mark

## 回复 by 4Chan (#38)

*2025-7-31 11:40*

makr

## 回复 by 小宇cc (#39)

*2025-7-31 18:35*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_uvyukvot (#40)

*2025-8-1 17:16*

666

## 回复 by mb_4nrpVMxJ (#41)

*2025-8-8 07:06*

康康

## 回复 by wen55444 (#42)

*2025-8-11 11:52*

感谢分享

## 回复 by mb_xjdhrmck (#43)

*2025-8-11 13:57*

6666

## 回复 by 万里星河 (#44)

*2025-8-11 14:30*

学习一下

## 回复 by 胖虎汇邦 (#45)

*2025-8-11 16:01*

111

## 回复 by DirtyAngle (#46)

*2025-8-11 16:17*

0000

## 回复 by xianhuimin (#47)

*2025-8-12 12:56*

tql

## 回复 by 阿杨` (#48)

*2025-8-12 14:01*

学习学习

## 回复 by 3倍アイスクリーム! (#49)

*2025-8-12 14:18*

mark

## 回复 by 万里星河 (#50)

*2025-8-12 15:50*

经测试 指令级Hook用不了 native层并没有注册相关函数 不过so里有注册的相关代码 强制手动注册后不会崩溃了 但没有任何效果 测试系统:安卓10与安卓15

## 回复 by mb_pobqzscg (#51)

*2025-8-12 17:18*

666

## 回复 by WanQing (#52)

*2025-8-12 21:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  经测试&nbsp;指令级Hook用不了&nbsp;native层并没有注册相关函数&nbsp;不过so里有注册的相关代码&nbsp;强制手动注册后不会崩溃了&n ...
>
>

不知道你的测试代码是什么呢，机型是什么，给的demo是默认需要点load初始化才注册的，在android7-16系统上我测试都是没问题的。

## 回复 by 万里星河 (#53)

*2025-8-13 00:34*

try {
        System.loadLibrary("api");
        registerAlbatrossLib(Albatross.class);
        Albatross.init(0);
      } catch (Throwable ignore) {
        Albatross.loadLibrary("albatross_base");
      }
请问demo里的初始化代码是指上上面这个吗？但似乎没有libapi.so这个文件。
于是：
我第一版初始化代码是这样的：
 Albatross.loadLibrary("albatross_base");
 Method onCreate = Activity.class.getDeclaredMethod("onCreate", Bundle.class);
            Albatross.hookInstruction(onCreate, 0, 100, new InstructionCallback()
            {
                @Override
                public void onEnter(Member member, Object self, int dexPc, InvocationContext invocationContext)
                {
                    Log.d("Albatross","dex_Pc:" + dexPc);
                }
            });
报错:No implementation found for int qing.albatross.core.Albatross.getRuntimeISA() (tried Java_qing_albatross_core_Albatross_getRuntimeISA and Java_qing_albatross_core_Albatross_getRuntimeISA__) - is the library loaded, e.g. System.loadLibrary?

于是我改成了这样:
            System.loadLibrary("albatross_base");
            Method onCreate = Activity.class.getDeclaredMethod("onCreate", Bundle.class);
            Albatross.hookInstruction(onCreate, 0, 100, new InstructionCallback()
            {
                @Override
                public void onEnter(Member member, Object self, int dexPc, InvocationContext invocationContext)
                {
                    Log.d("Albatross","dex_Pc:" + dexPc);
                }
            });
报错:
java.lang.UnsatisfiedLinkError: No implementation found for long qing.albatross.core.InstructionListener.hookInstructionNative(java.lang.reflect.Member, int, int, java.lang.Object) (tried Java_qing_albatross_core_InstructionListener_hookInstructionNative and Java_qing_albatross_core_InstructionListener_hookInstructionNative__Ljava_lang_reflect_Member_2IILjava_lang_Object_2) - is the library loaded, e.g. System.loadLibrary?
        at qing.albatross.core.InstructionListener.hookInstructionNative(Native Method)
        at qing.albatross.core.Albatross.hookInstruction(Albatross.java:447)
        at qing.albatross.core.Albatross.hookInstruction(Albatross.java:436)
于是用ida看了下 看到了注册的代码 手动注册 但这个函数似乎需要一个jmethod作为参数 于是随便传了个InstructionListener的onEnter进去:
 typedef void(*Func)(JNIEnv*,jobject);
    void* handle = dlopen("albatross_base",RTLD_LAZY);
    Func entry = (Func)dlsym(handle,"_ZN9albatross23InstrumentationListener23registerInstrumentationEP7_JNIEnvP8_jobject");
    entry(env,obj);
不报错了 注册成功 但没有效果
测试机型：
小米6 lineageos 安卓15
小米8 官方系统 安卓10

## 回复 by 万里星河 (#54)

*2025-8-13 00:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  不知道你的测试代码是什么呢，机型是什么，给的demo是默认需要点load初始化才注册的，在android7-16系统上我测试都是没问题的。
>
>

           最终初始化代码如下:
            System.loadLibrary("albatross_base");
            Method onEnter = InstructionListener.class.getDeclaredMethod("onEnter", Object.class, int.class, long.class);
            registerAlbatrossLib(onEnter);
//            Albatross.init(0); 执行会报错
            Method onClick = b.class.getDeclaredMethod("onClick", DialogInterface.class, int.class);
            Albatross.hookInstruction(onClick, 0, 10, new InstructionCallback()
            {
                @Override
                public void onEnter(Member member, Object self, int dexPc, InvocationContext invocationContext)
                {
                    Log.d("Albatross","dex_Pc:" + dexPc);
                }
            });

## 回复 by WanQing (#55)

*2025-8-13 08:39*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  最终初始化代码如下:
>  System.loadLibrary("albatross_base");
>  Meth ...
>
>

谢谢你的反馈，已经修复了，v1.0.5的版本有问题，你可以试试最新提交的版本，在android10和android15的手机测试都是可以的

## 回复 by mb_uaoofzgb (#56)

*2025-8-13 10:08*

代码开源不？指令Hook是怎么实现的呢？

## 回复 by 万里星河 (#57)

*2025-8-13 11:41*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  谢谢你的反馈，已经修复了，v1.0.5的版本有问题，你可以试试最新提交的版本，在android10和android15的手机测试都是可以的
>
>

好的 我试试

## 回复 by 万里星河 (#58)

*2025-8-13 11:43*

>
> [mb_uaoofzgb](https://bbs.kanxue.com/user-1001998.htm)
>
>  代码开源不？指令Hook是怎么实现的呢？
>
>

盲猜核心是ShadowFrame

## 回复 by 冰眼 (#59)

*2025-8-13 11:53*

ddd

## 回复 by 万里星河 (#60)

*2025-8-13 12:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  谢谢你的反馈，已经修复了，v1.0.5的版本有问题，你可以试试最新提交的版本，在android10和android15的手机测试都是可以的
>
>

测试了以下 没有任何区别 System.loadLibrary后native函数还是没有注册 通过解析符号进行手动注册还是没效果 建议先修复注册问题

## 回复 by zz胡 (#61)

*2025-8-13 13:29*

6666

## 回复 by 智取琪 (#62)

*2025-8-14 10:45*

来了

## 回复 by didiid (#63)

*2025-8-14 16:35*

666

## 回复 by WanQing (#64)

*2025-8-14 20:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  测试了以下 没有任何区别 System.loadLibrary后native函数还是没有注册 通过解析符号进行手动注册还是没效果 建议先修复注册问题
>
>

System.loadLibrary加载是不行的，为了支持混淆，需要将类传递到AlbatrossAndroidInit注册，然后再初始化。最好先跑通demo。

## 回复 by 万里星河 (#65)

*2025-8-14 22:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  System.loadLibrary加载是不行的，为了支持混淆，需要将类传递到AlbatrossAndroidInit注册，然后再初始化。最好先跑通demo。
>
>

可我就是这样做的呀：

```
// 初始化 但hookInstruction还是未注册
AlbatrossAndroidInit(env, cls);
// 尝试手动注册
typedef void(*Func)(JNIEnv*,jobject);
void* handle = dlopen("albatross_base",RTLD_LAZY);
Func entry = (Func)dlsym(handle,"_ZN9albatross23InstrumentationListener23registerInstrumentationEP7_JNIEnvP8_jobject");
entry(env,obj);
return JNI_TRUE;
```

## 回复 by Ascend_202904 (#66)

*2025-8-14 22:26*

6666666666

## 回复 by 万里星河 (#67)

*2025-8-15 03:28*

```
System.loadLibrary("albatross_base");
System.loadLibrary("api");
registerAlbatrossLib(Albatross.class);
Albatross.init(0);
```

```
extern "C"
JNIEXPORT jboolean JNICALL
Java_com_example_aliucord_MainActivity_registerAlbatrossLib(JNIEnv *env, jclass clazz,jclass albatross) {
    int err_code = AlbatrossAndroidInit(env, clazz);
    if (err_code)
        return JNI_FALSE;
    return JNI_TRUE;
}
```

```
cmake_minimum_required(VERSION 3.18.1)
project("api")

add_library(
        api
        SHARED
        native-lib.cpp)

set(JNI_LIBS_DIR ${CMAKE_SOURCE_DIR}/../jniLibs)

target_link_libraries(
        api
        android
        ${JNI_LIBS_DIR}/${ANDROID_ABI}/libalbatross_base.so
        log)
```

```
调用 Albatross.init(0) 会报错:
2025-08-15 03:19:10.772 22173-22173/com.example.aliucord A/libc: Fatal signal 11 (SIGSEGV), code 2 (SEGV_ACCERR), fault addr 0x7c760cf9e7 in tid 22173 (xample.aliucord), pid 22173 (xample.aliucord)
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: Build fingerprint: 'Xiaomi/dipper/dipper:10/QKQ1.190828.002/20.9.4:user/release-keys'
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: Revision: '0'
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: ABI: 'arm64'
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: Timestamp: 2025-08-15 03:19:10+0800
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: pid: 22173, tid: 22173, name: xample.aliucord  >>> com.example.aliucord <<<
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: uid: 10227
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: signal 11 (SIGSEGV), code 2 (SEGV_ACCERR), fault addr 0x7c760cf9e7
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG: Cause: execute-only (no-read) memory access error; likely due to data in .text.
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG:     x0  0000007c5e0aa800  x1  0000000000000000  x2  ffffffffffffffe8  x3  0000007c5e0aa9c0
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG:     x4  0000007c5e0aaa28  x5  0000000000000004  x6  0000007cfc43f660  x7  0000000000000000
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG:     x8  0000000000000000  x9  00000000ffffffff  x10 0000000000000008  x11 00000000ffffffff
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG:     x12 0000007c09e8cc78  x13 ffffffffffffffed  x14 0000007c09f3568d  x15 0000000000000000
2025-08-15 03:19:10.909 22220-22220/? A/DEBUG:     x16 0000007c09f31d90  x17 0000007cfa256220  x18 0000007cfcdb2000  x19 0000007fcee16b84
2025-08-15 03:19:10.910 22220-22220/? A/DEBUG:     x20 0000007fcee16b88  x21 0000007c760cf9e4  x22 0000007c5e632a40  x23 0000000000000001
2025-08-15 03:19:10.910 22220-22220/? A/DEBUG:     x24 0000007c760cf9e4  x25 0000007c09a9db1d  x26 0000007c760cf9e4  x27 0000000000000001
2025-08-15 03:19:10.910 22220-22220/? A/DEBUG:     x28 0000000000000002  x29 0000007fcee168e0
2025-08-15 03:19:10.910 22220-22220/? A/DEBUG:     sp  0000007fcee168d0  lr  0000007c09e857fc  pc  0000007c09e85864
2025-08-15 03:19:11.013 22220-22220/? A/DEBUG: backtrace:
2025-08-15 03:19:11.013 22220-22220/? A/DEBUG:       #00 pc 000000000001b864  /data/app/com.example.aliucord-S9BCUcPIRKMSw8Y8vC42jA==/base.apk
```

## 回复 by WanQing (#68)

*2025-8-15 10:18*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  System.loadLibrary(&quot;albatross_base&quot;);
> System.loadLibrary(&quot;api&quot;) ...
>
>

谢谢你的反馈，我这边写错了，我混淆后才发现传错参数了，是把类albatross传进去
extern "C"
JNIEXPORT  JNICALL jboolean
Java_qing_albatross_demo_AlbatrossDemoMainActivity_registerAlbatrossLib(JNIEnv *env, jclass clazz,
                                                                        jclass albatross) {
    int err_code = AlbatrossAndroidInit(env, albatross);
    if (err_code)
        return JNI_FALSE;
    return JNI_TRUE;
}

## 回复 by WanQing (#69)

*2025-8-15 10:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  System.loadLibrary(&quot;albatross_base&quot;);
> System.loadLibrary(&quot;api&quot;) ...
>
>

看问题可能是修改aot或jit代码是读写属性没有修改成功。可以加个vx方便交流么。

## 回复 by 万里星河 (#70)

*2025-8-15 11:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  谢谢你的反馈，我这边写错了，我混淆后才发现传错参数了，是把类albatross传进去
> extern "C"
> JNIEXPORT JNICALL jboolean
> Java_ ...
>
>

我也在这儿疑惑了好久![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by 山竹笠 (#71)

*2025-8-15 13:19*

mark

## 回复 by 万里星河 (#72)

*2025-8-15 14:13*

```
测试机型:一加五 安卓9
init不报memory access error了 但没有任何效果
```

```
代码：
System.loadLibrary("api");
registerAlbatrossLib(Albatross.class);
Albatross.init(0);
Method onCreate = Activity.class.getDeclaredMethod("onCreate", Bundle.class);
Albatross.hookInstruction(onCreate, 0, 30, new InstructionCallback()
{
    @Override
    public void onEnter(Member member, Object self, int dexPc, InvocationContext invocationContext)
    {
        Log.d("Albatross","dex_Pc:" + dexPc);
    }
});
Log.d("Albatross","hook ok");
```

```
日志：
2025-08-15 14:10:35.077 I/Albatross: Cannot find target constructor for static void qing.albatross.core.ClassLoaderHook.init(java.lang.ClassLoader,java.lang.Void,java.lang.String,java.lang.ClassLoader)
2025-08-15 14:10:35.078 I/Albatross: Cannot find target constructor for static void qing.albatross.core.ClassLoaderHook.initM(java.lang.ClassLoader,java.lang.ClassLoader,boolean)
2025-08-15 14:10:35.078 I/Albatross: Hooked protected java.lang.ClassLoader(java.lang.ClassLoader): hookBackup=private static void qing.albatross.core.ClassLoaderHook.init(java.lang.ClassLoader,java.lang.ClassLoader)
2025-08-15 14:10:35.078 I/Albatross: Hooked private java.lang.ClassLoader(java.lang.Void,java.lang.ClassLoader): hookBackup=static void qing.albatross.core.ClassLoaderHook.init(java.lang.ClassLoader,java.lang.Void,java.lang.ClassLoader)
2025-08-15 14:10:35.263 I/nzack.langeniu: Compiler allocated 7MB to compile int qing.albatross.core.Albatross.hookClassInternal(java.lang.Class, java.lang.ClassLoader, java.lang.Class, java.lang.Object)
2025-08-15 14:10:35.280 D/Albatross: hook ok
```

## 回复 by WanQing (#73)

*2025-8-15 20:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  测试机型:一加五&nbsp;安卓9&nbsp;
> init不报memory&nbsp;access&nbsp;error了&nbsp;但没有任何效果代码：
> S ...
>
>

适配好了，稍后更新，其实最早的版本都是可以的，v1.0.5优化后面尽可能提升运行速度，做了优化，导致会遗漏掉。

## 回复 by xput (#74)

*2025-8-15 22:22*

先生大才啊，特来学习，感谢分享技术

## 回复 by 万里星河 (#75)

*2025-8-15 22:37*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>
>
>
>
>
>
>  万里星河
>
>
>
>  测试机型:一加五&amp;nbsp;安卓9&amp;nbsp;
> init不报memory&amp;nb ...
>
>

嗯嗯 坐等![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by xput (#76)

*2025-8-15 22:52*

我是小白，看着很高端，很想学习食用之，请问怎么使用，我手机下载下来是个zip压缩包，这是要PC编译才能在安卓上执行的吗，我只有手机一部，请问应该从何起手，

## 回复 by WanQing (#77)

*2025-8-16 14:54*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>
>
>
>
>
>
>  WanQing
>
>
>
>
>
>
>
>
>
>  万里星河
>
>
>
>  测试机型:一加五&amp;amp;nbsp ...
>
>

我在coloerOS v6 android9的系统测试没问题,你回头试试

## 回复 by WanQing (#78)

*2025-8-16 14:56*

>
> [xput](https://bbs.kanxue.com/user-498727.htm)
>
>  我是小白，看着很高端，很想学习食用之，请问怎么使用，我手机下载下来是个zip压缩包，这是要PC编译才能在安卓上执行的吗，我只有手机一部，请问应该从何起手，
>
>

这个需要了解android app开发和对smali语法有所了解，需要android studio编译。

## 回复 by 万里星河 (#79)

*2025-8-16 16:44*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  我在coloerOS v6 android9的系统测试没问题,你回头试试
>
>

v.1.0.8的库似乎没有发布 只有v1.0.7

## 回复 by WanQing (#80)

*2025-8-16 19:28*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  v.1.0.8的库似乎没有发布 只有v1.0.7
>
>

拉取最新的代码，之前有bug的几个版本都删除了

## 回复 by 万里星河 (#81)

*2025-8-16 19:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  拉取最新的代码，之前有bug的几个版本都删除了
>
>

一加五 安卓9 初步测试有效果了
小米还是老样子

## 回复 by 万里星河 (#82)

*2025-8-16 20:05*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  一加五 安卓9 初步测试有效果了
> 小米还是老样子
>
>

不知能否说说原理是啥 我在Instrumentation看到如下代码 似乎很有搞头：

```
  // Call-back for when the dex pc moves in a method.
  virtual void DexPcMoved(Thread* thread,
                          Handle this_object,
                          ArtMethod* method,                          uint32_t new_dex_pc)
      REQUIRES_SHARED(Locks::mutator_lock_) = 0;
```

然后就是回调个dex_pc其实不太直观

根据java层的method可获得ArtMethod 然后可以得到codeItem和dex的起始地址 codeItem加上dex_pc能定位到字节码 使用Instruction的导出函数可以直接反编译成smali 因此建议可以把反编译的smali一起回调回来 更直观和实用些

## 回复 by 万里星河 (#83)

*2025-8-16 20:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>
>
>
>
>
>
>  万里星河
>
>
>
>  一加五 安卓9 初步测试有效果了
> 小米还是老样子
>
>  不知能否说说原理是啥 我在Instrumentation看到如下代 ...
>
>

我用frida实现过 但泛化能力不太好 只能在某一部特定的手机用![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by WanQing (#84)

*2025-8-16 21:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  我用frida实现过 但泛化能力不太好 只能在某一部特定的手机用[em_055]
>
>

那种技术方案可以做，不过不应该去hook mterp解释器，而是对其进行动态重编译，发现是目标的跳转到重编译的代码，不然会拖慢执行速度的。

## 回复 by WanQing (#85)

*2025-8-16 21:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>
>
>
>
>
>
>  万里星河
>
>
>
>  一加五 安卓9 初步测试有效果了
> 小米还是老样子
>
>  不知能否说说原理是啥 我在Instrumentation看到如下代 ...
>
>

这个可以做的，适合有壳的情况分析代码。

## 回复 by WanQing (#86)

*2025-8-16 21:30*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  一加五 安卓9 初步测试有效果了
> 小米还是老样子
>
>

你把小米的libart.so 32位和64位的可以都邮箱发给我，我看一下有什么改动

## 回复 by 万里星河 (#87)

*2025-8-16 21:48*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  你把小米的libart.so 32位和64位的可以都邮箱发给我，我看一下有什么改动
>
>

好久没用邮件了 直接附件发你吧

上传的附件：
- libart.so_32bit_xiaomi8_android10

（5.76MB，1次下载）
- libart.so_64bit_xiaomi8_android10

（7.31MB，2次下载）

## 回复 by 飆汗吉米 (#88)

*2025-8-17 03:28*

6666

## 回复 by 万里星河 (#89)

*2025-8-17 17:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  你把小米的libart.so 32位和64位的可以都邮箱发给我，我看一下有什么改动
>
>

修复好了

```
void* hook_getInstruction(void* p1,void* p2,void* p3,void* p4,void* p5,void* p6,void* p7,void* p8)
{
    LOGD("%p %p",p1,p2);
    unsigned long p = ((unsigned long)p2 >> 12) << 12;
    if(mprotect((void*)p,PAGE_SIZE,PROT_READ | PROT_WRITE | PROT_EXEC))
    {
        LOGD("mprotect: %s", strerror(errno));
    }
    return back_getInstruction(p1,p2,p3,p4,p5,p6,p7,p8);
}
```

## 回复 by 万里星河 (#90)

*2025-8-17 22:11*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  修复好了void*&nbsp;hook_getInstruction(void*&nbsp;p1,void*&nbsp;p2,void*&nbsp;p3,void*&a ...
>
>

实现了samli动态反编译

```
public void instruction(View view) throws NoSuchMethodException
{
  initAlbatross();
  if (listener == null)
  {
    Method getCaller = AlbatrossDemoMainActivity.class.getDeclaredMethod("getCaller", View.class);
    listener = Albatross.hookInstruction(getCaller, 0, 10, (method, self, dexPc, invocationContext) ->
    {
        assert dexPc <= 10;
        assert dexPc >= 0;
        assert method == getCaller;
        if (self != AlbatrossDemoMainActivity.this)
        {
            Albatross.log("self:" + self + " this:" + AlbatrossDemoMainActivity.this);
        }
        assert invocationContext.numberOfVRegs() == 7;
        String smali = Albatross.decompile(method,dexPc);
        Log.d("InstructionHooker",method + "[" + dexPc + "]" + "->" + smali);

        Object receiver = invocationContext.getParamObject(0);
        assert receiver == self;
        Object v = invocationContext.getParamObject(1);
        assert (v instanceof View);
        if (dexPc == 4)
        {
          invocationContext.setVRegObject(0, AlbatrossDemoMainActivity.class);
        }
    });
  }
  else
  {
    listener.unHook();
    listener = null;
  }
}
```

```
qing.albatross.demo64 D/InstructionHooker: public void qing.albatross.demo.AlbatrossDemoMainActivity.getCaller(android.view.View)[0]->invoke-static {}, java.lang.Class qing.albatross.core.Albatross.getCallerClass() // method@196
qing.albatross.demo64 D/InstructionHooker: public void qing.albatross.demo.AlbatrossDemoMainActivity.getCaller(android.view.View)[3]->move-result-object v0
qing.albatross.demo64 D/InstructionHooker: public void qing.albatross.demo.AlbatrossDemoMainActivity.getCaller(android.view.View)[4]->iget-object v1, v5, Landroid/widget/TextView; qing.albatross.demo.AlbatrossDemoMainActivity.textView // field@49
qing.albatross.demo64 D/InstructionHooker: public void qing.albatross.demo.AlbatrossDemoMainActivity.getCaller(android.view.View)[6]->new-instance v2, java.lang.StringBuilder // type@TypeIndex[49]
qing.albatross.demo64 D/InstructionHooker: public void qing.albatross.demo.AlbatrossDemoMainActivity.getCaller(android.view.View)[8]->invoke-direct {v2}, void java.lang.StringBuilder.<init>() // method@41
```

## 回复 by WanQing (#91)

*2025-8-17 23:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  实现了samli动态反编译public&nbsp;void&nbsp;instruction(View&nbsp;view)&nbsp;throws&nbsp; ...
>
>

可以，为你点赞

## 回复 by 万里星河 (#92)

*2025-8-17 23:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  可以，为你点赞
>
>

感谢大佬谬赞

## 回复 by 万里星河 (#93)

*2025-8-18 15:31*

不过小米6还是有问题 安卓15 lineageos![image](https://bbs.kanxue.com/view/img/face/006.gif)

## 回复 by WanQing (#94)

*2025-8-18 20:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  不过小米6还是有问题 安卓15 lineageos[em_006]
>
>

方法hook的修复了，我看lineageos 编译出的libart有些方法没有内联，有些内联进去了，指令hook的在修复中。

## 回复 by WanQing (#95)

*2025-8-20 08:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  不过小米6还是有问题 安卓15 lineageos[em_006]
>
>

Android5 lineageOs实测v1.0.9没问题了，你拉取代码试试![image](https://bbs.kanxue.com/view/img/face/020.gif)

## 回复 by 金钱蒲 (#96)

*2025-8-20 09:30*

好好学习天天向上

## 回复 by 万里星河 (#97)

*2025-8-20 10:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  WanQing](https://bbs.kanxue.com/user-875201.htm)
>
>  Android5 lineageOs实测v1.0.9没问题了，你拉取代码试试[em_020]
>
>

大佬太强辣 我抽时间试试![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by ckis (#98)

*2025-8-23 16:35*

学习一下！！！

## 回复 by 万里星河 (#99)

*2025-8-24 12:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  大佬太强辣 我抽时间试试[em_014]
>
>

已测试 小米6 lineageos 安卓15 运行正常

## 回复 by lixianhuei (#100)

*2025-8-24 21:57*

666666

## 回复 by A冷忆 (#101)

*2025-8-27 15:35*

mark

## 回复 by Arsylk (#102)

*2025-8-29 09:32*

6

## 回复 by 万里星河 (#103)

*2025-8-31 20:01*

```
差不多400行代码 我也尝试着实现了一个在arm64架构下的dalvik指令级的art hook框架
```

```
Reflect.monitor(Activity.class.getDeclaredMethod("onCreate", Bundle.class));
Reflect.hook(Activity.class.getDeclaredMethod("onResume"), new HookCallBack() {
    @Override
    public Object callBack(Object obj1, Object obj2, Object obj4, Object obj5, Object obj6, Object obj7) {
        System.out.println("Wonson_Hook:Activity onResume coming");
        try {
            Method onResume = Activity.class.getDeclaredMethod("onResume");
            onResume.setAccessible(true);
            Reflect.disableHook(onResume);
            return onResume.invoke(this);
        } catch (NoSuchMethodException e) {
            e.printStackTrace();
        } catch (InvocationTargetException e) {
            e.printStackTrace();
        } catch (IllegalAccessException e) {
            e.printStackTrace();
        }
        return null;
    }
});
```

```
D/Wonson_Hook: monitor ok!
D/Wonson_Hook: end
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[0]:iget-object v0, v5, Landroid/app/Activity$NonConfigurationInstances; android.app.Activity.mLastNonConfigurationInstances // field@6699
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[2]:if-eqz v0, +9
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[11]:iget-object v0, v5, Landroid/content/pm/ActivityInfo; android.app.Activity.mActivityInfo // field@6662
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[13]:iget-object v0, v0, Ljava/lang/String; android.content.pm.ActivityInfo.parentActivityName // field@18996
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[15]:const/4 v1, #+1
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[16]:if-eqz v0, +12
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[28]:const/4 v0, #+0
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[29]:if-eqz v6, +51
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[80]:iget-object v2, v5, Landroid/app/FragmentController; android.app.Activity.mFragments // field@6690
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[82]:invoke-virtual {v2}, void android.app.FragmentController.dispatchCreate() // method@6202
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[85]:invoke-direct {v5, v6}, void android.app.Activity.dispatchActivityCreated(android.os.Bundle) // method@2539
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[88]:iget-object v2, v5, Landroid/app/VoiceInteractor; android.app.Activity.mVoiceInteractor // field@6723
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[90]:if-eqz v2, +5
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[95]:if-eqz v6, +3
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[98]:iput-boolean v0, v5, Z android.app.Activity.mRestoredFromBundle // field@6706
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[100]:iput-boolean v1, v5, Z android.app.Activity.mCalled // field@6671
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[102]:iget-object v0, v5, Lcom/miui/internal/contentcatcher/IInterceptor; android.app.Activity.mInterceptor // field@6697
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[104]:if-nez v0, +8
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[106]:invoke-static {v5}, miui.contentcatcher.InterceptorProxy miui.contentcatcher.InterceptorProxy.create(android.app.Activity) // method@64010
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[109]:move-result-object v0
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[110]:iput-object v0, v5, Lcom/miui/internal/contentcatcher/IInterceptor; android.app.Activity.mInterceptor // field@6697
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[112]:iget-object v0, v5, Lcom/miui/internal/contentcatcher/IInterceptor; android.app.Activity.mInterceptor // field@6697
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[114]:if-eqz v0, +5
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[116]:invoke-interface {v0}, void com.miui.internal.contentcatcher.IInterceptor.notifyActivityCreate() // method@62747
D/Wonson_Hook: void android.app.Activity.onCreate(android.os.Bundle)[119]:return-void
D/Wonson_Hook: redirect art method!
I/System.out: Wonson_Hook:Activity onResume coming
D/Wonson_Hook: disableHook ok!
D/Wonson_Hook: execute art method!
```

## 回复 by 寻梦之璐 (#104)

*2025-8-31 22:56*

6

## 回复 by git_39084niu516 (#105)

*2025-9-5 13:48*

666

## 回复 by WanQing (#106)

*2025-9-5 21:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  万里星河](https://bbs.kanxue.com/user-892665.htm)
>
>  差不多400行代码&nbsp;我也尝试着实现了一个在arm64架构下的dalvik指令级的art&nbsp;hook框架Reflect.monitor(Activity.class.g ...
>
>

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by wx_听书人 (#107)

*2025-9-5 23:37*

66666

## 回复 by git_56701jackt88 (#108)

*2025-9-8 02:12*

xiexie

## 回复 by wx_aa_775 (#109)

*2025-9-8 20:28*

666666666666666666

## 回复 by younghare (#110)

*2025-9-11 11:39*

了解一下

## 回复 by mb_ozmrnffd (#111)

*2025-9-12 21:12*

![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by wuaiwu (#112)

*2025-9-19 02:41*

6666

## 回复 by 学生的 (#113)

*2025-9-22 04:04*

感谢你的积极参与，期待更多精彩内容！

## 回复 by wx_！_336 (#114)

*2025-9-22 20:35*

111

## 回复 by mb_nhphjyjb (#115)

*2025-10-6 13:38*

感谢分享

## 回复 by qqsunqiang (#116)

*2025-10-6 16:42*

谢谢楼主

## 回复 by mb_gmubqahb (#117)

*2025-10-10 18:04*

mark

## 回复 by xxjj678 (#118)

*2025-10-12 00:36*

666

## 回复 by Gryffindoss (#119)

*2025-10-13 14:11*

666

## 回复 by FindCall (#120)

*2025-10-15 20:53*

mark

## 回复 by tyeying (#121)

*2025-10-20 17:04*

666

## 回复 by 野狼 (#122)

*2025-10-26 06:16*

学习一下

## 回复 by 情迁 (#123)

*2025-10-29 17:20*

kank

## 回复 by mb_pmgifpme (#124)

*2025-11-7 15:04*

1

## 回复 by 暗香沉浮 (#125)

*2025-11-16 10:26*

111

## 回复 by wx_马 (#126)

*2025-11-16 18:49*

mark

## 回复 by 黑屏 (#127)

*2025-11-17 13:02*

666

## 回复 by pynice (#128)

*2025-12-2 15:08*

mark

## 回复 by asm_zhang (#129)

*2025-12-3 15:35*

6

## 回复 by mb_mrgbywba (#130)

*2025-12-6 17:43*

mark

## 回复 by Heiyiren123 (#131)

*2025-12-8 06:19*

感谢分享，很有参考价值！

## 回复 by mb_bdqlgdvm (#132)

*2025-12-19 16:11*

66666666666666666

## 回复 by wx_你浩哥 (#133)

*2025-12-25 22:22*

学习一下

## 回复 by xeiyu (#134)

*2026-1-3 15:49*

6

## 回复 by AMy_德友 (#135)

*2026-1-5 08:07*

Albatross

## 回复 by mb_rewimxhj (#136)

*2026-1-19 07:49*

看看

## 回复 by buluo533 (#137)

*2026-1-19 08:04*

66666

## 回复 by buluo533 (#138)

*2026-1-19 08:04*

66666

## 回复 by mb_aiyhfydo (#139)

*2026-1-22 10:41*

康康

## 回复 by mJqalJqN (#140)

*2026-2-9 17:42*

1

## 回复 by mb_irhdtnzm (#141)

*2026-2-9 18:41*

1

## 回复 by mb_jhohnbzu (#142)

*2026-2-12 11:09*

666

## 回复 by 大萨达 (#143)

*2026-3-20 12:51*

6666

## 回复 by FMNS (#144)

*2026-3-21 07:56*

6666

## 回复 by wx_故事与酒 (#145)

*2026-3-23 21:55*

666666666666666666

## 回复 by 星辰北天 (#146)

*2026-3-29 20:01*

感谢分享

## 回复 by mb_ileraodd (#147)

*2026-4-25 17:14*

566699

## 回复 by l140w4n9 (#148)

*2026-6-5 15:56*

666666

## 回复 by ReverseApp (#149)

*2026-7-13 14:03*

mark

## 回复 by mb_ecoknywz (#150)

*2026-7-13 15:13*

这个学学，看看怎么操作的，感谢大神

## 回复 by wx_coddvccwyh (#151)

6666
