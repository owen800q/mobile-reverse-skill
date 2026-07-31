---
title: '[原创]Frida源码分析之Java Hook原理篇'
url: https://bbs.kanxue.com/thread-291155.htm
tid: 291155
author: gal2xy
date: '2026-05-09'
tags: [Android安全, 原创, 源码框架]
crawled_at: '2026-07-31T13:53:07+08:00'
replies: 1
---

根据[官方文档](https://frida.re/docs/bridges/?utm_source=chatgpt.com)，Frida 17之后的版本中， GumJs 运行时不再捆绑 bridges（例如 frida-java-bridge、frida-objc-bridge, frida-swift-bridge）。因此这篇Java Hook原理分析参考的项目源码在[frida-java-bridge](https://github.com/frida/frida-java-bridge)中。

以如下例子进行原理分析

```js
var Adapter = Java.use(targetClass);
Adapter["doAdapter"].implementation = function (i) {
    console.log(">>> doAdapter is called: i=" + i);
    var result = this.doAdapter(i);
    console.log("<<< doAdapter result=" + result);
    return result;
}
```

Adapter["doAdapter"]获取到的是methodPrototype对象，然后将自定义的hook函数赋值给implementation字段，使用到的是implementation的`set()`方法来安装Hook（对应android.js 1697行处）。

## implementation.set

```js
implementation: {
    enumerable: true,
    get () {
      const replacement = this._r;
      return (replacement !== undefined) ? replacement : null;
    },
    set (fn) {
      const params = this._p;
      const holder = params[1]; // classWrapper
      const type = params[2]; // 方法类型：实例/静态/构造
      // 构造方法通过$init进行hook
      if (type === CONSTRUCTOR_METHOD) {
        throw new Error('Reimplementing $new is not possible; replace implementation of $init instead');
      }
      // 卸载已存在的hook逻辑
      const existingReplacement = this._r;
      if (existingReplacement !== undefined) {
        // holder.$f._patchedMethods 是 classFactory 维护的“当前已打补丁的方法集合”，用于后续统一清理
        holder.$f._patchedMethods.delete(this);

        const mangler = existingReplacement._m;
        mangler.revert(vm);// 删除hook逻辑，恢复成原函数

        this._r = undefined;
      }

      if (fn !== null) {
        const [methodName, classWrapper, type, methodId, retType, argTypes] = params;
        // 将用户定义的JS hook函数封装成native函数
        const replacement = implement(methodName, classWrapper, type, retType, argTypes, fn, this);
        const mangler = makeMethodMangler(methodId);
        replacement._m = mangler;
        this._r = replacement;
        // 对原方法进行hook
        mangler.replace(replacement, type === INSTANCE_METHOD, argTypes, vm, api);
        // 添加到补丁集合中
        holder.$f._patchedMethods.add(this);
      }
    }
}
```

`set()` 首先校验目标方法是否是构造方法，此方法不通过当前路径实现。然后检查目标方法是否已经被hook，如果被hook过了，则撤销之前的hook逻辑。最后，如果存在新的hook逻辑，则调用`implement()`方法将用户定义的js hook逻辑封装成native函数，并调用`mangler.replace()`方法对目标方法进行hook。

## implement

```js
function implement (methodName, classWrapper, type, retType, argTypes, handler, fallback = null) {
  const pendingCalls = new Set();
  // 返回一个函数，内部调用了用户的hook代码，并且对入参类型进行了转换(jni to js)，对返回值类型进行了转换(js to jni)
  const f = makeMethodImplementation([methodName, classWrapper, type, retType, argTypes, handler, fallback, pendingCalls]);
  // 将做了参数类型适配的hook代码封装成native函数
  const impl = new NativeCallback(f, retType.type, ['pointer', 'pointer'].concat(argTypes.map(t => t.type)));
  impl._c = pendingCalls;

  return impl;
}

function makeMethodImplementation (params) {
  return function () {
    return handleMethodInvocation(arguments, params);
  };
}
```

该函数主要是对用户定义的hook逻辑封装成native函数。其中`makeMethodImplementation()` 的作用是把一堆上下文参数封进闭包，生成一个符合 `NativeCallback` 签名的入口函数，其内部调用了`handleMethodInvocation()`方法。

### handleMethodInvocation

```js
function handleMethodInvocation (jniArgs, params) {
  // 将JNIEnv封装成js层的JNIEnv
  const env = new Env(jniArgs[0], vm);

  const [methodName, classWrapper, type, retType, argTypes, handler, fallback, pendingCalls] = params;

  const ownedObjects = [];
  // 实例方法创建类实例对象，静态方法直接使用classWrapper
  let self;
  if (type === INSTANCE_METHOD) {
    const C = classWrapper.$C;
    self = new C(jniArgs[1], STRATEGY_VIRTUAL, env, false);
  } else {
    self = classWrapper;
  }

  const tid = getCurrentThreadId();
  //创建局部帧，管理本地引用
  env.pushLocalFrame(3);
  let haveFrame = true;
  // 当前线程与env进行关联
  vm.link(tid, env);

  try {
    pendingCalls.add(tid);//线程id加入到集合中
    // fallback为null, fn赋值为用户定义的hook代码
    let fn;
    if (fallback === null || !ignoredThreads.has(tid)) {
      fn = handler;
    } else {
      fn = fallback;
    }
    // 将jni参数转成js参数
    const args = [];
    const numArgs = jniArgs.length - 2;
    for (let i = 0; i !== numArgs; i++) {
      const t = argTypes[i];

      const value = t.fromJni(jniArgs[2 + i], env, false);// 跳过前两个JNI参数（JNIEnv*, jobject/jclass）
      args.push(value);
      // js参数保存到ownedObjects中
      ownedObjects.push(value);
    }
    // 用户定义的hook方法执行
    const retval = fn.apply(self, args);

    if (!retType.isCompatible(retval)) {
      throw new Error(`Implementation for ${methodName} expected return value compatible with ${retType.className}`);
    }
    // 返回值从js转成jni
    let jniRetval = retType.toJni(retval, env);
    // 如果返回的是对象引用（pointer），需要把该引用“带出”当前local frame，否则frame弹出后引用失效
    // 同时保存到ownedObjects中
    if (retType.type === 'pointer') {
      jniRetval = env.popLocalFrame(jniRetval);
      haveFrame = false;

      ownedObjects.push(retval);
    }

    return jniRetval;
  }
  ...
}
```

当 Java 调用某个被 Hook 的方法时，负责将 JNI 的数据结构转换成 js 对象，执行用户定义的 js hook 代码，然后再将结果转换成回 JNI 的变量类型。

## makeMethodMangler

这里分析andriod平台下的java hook，因此我们分析`lib\android.js`下的`ArtMethodMangler`，该类的初始化函数如下：

```js
class ArtMethodMangler {
  constructor (opaqueMethodId) {
    const methodId = unwrapMethodId(opaqueMethodId);

    this.methodId = methodId;
    this.originalMethod = null;
    this.hookedMethodId = methodId;
    this.replacementMethodId = null;

    this.interceptor = null;
  }
  ...
}
```

## ArtMethodMangler.replace

对应`ArtMethodMangler.replace()`方法，位置在`lib\android.js`3707行处。接下来进行拆解分析。

```js
replace (impl, isInstanceMethod, argTypes, vm, api) {
    const { kAccCompileDontBother, artNterpEntryPoint } = api;
    // 获取原函数ArtMethod字段快照
    this.originalMethod = fetchArtMethod(this.methodId, vm);
```

这里主要是获取原函数的ArtMethod结构体中部分字段的值，具体为`jniCode`（）、`accessFlags`（）、`quickCode`（）、`interpreterCode`（方法解释执行入口），对于f`etchArtMethod`方法的详细分析见fetchArtMethod。

```js
const originalFlags = this.originalMethod.accessFlags;
// 判断当前函数是否被xposed hook过了
if ((originalFlags & kAccXposedHookedMethod) !== 0 && xposedIsSupported()) {
    // 该函数已被xposed hook过了
    // 此时jniCode是xposed的hookInfo指针
    const hookInfo = this.originalMethod.jniCode;
    // 获取真正的ArtMethod指针
    this.hookedMethodId = hookInfo.add(2 * pointerSize).readPointer();
    // 获取原函数ArtMethod字段快照
    this.originalMethod = fetchArtMethod(this.hookedMethodId, vm);
}
```

这部分主要检测是否进行了xposed hook，如果进行了，则借助xposed hook的信息获取原方法的ArtMethod指针，并重新调用`fetchArtMethod`获取原函数的ArtMethod结构体中部分字段的值。

```js
const { hookedMethodId } = this; // hookedMethodId为ArtMethod指针

const replacementMethodId = cloneArtMethod(hookedMethodId, vm);// 复制原函数的ArtMethod，用于后续修改
this.replacementMethodId = replacementMethodId;
// 把克隆出来的 ArtMethod 改造成一个 native 方法
patchArtMethod(replacementMethodId, {
    jniCode: impl, // 用户定义的hook代码逻辑
    accessFlags: ((originalFlags & ~(kAccCriticalNative | kAccFastNative | kAccNterpEntryPointFastPathFlag)) | kAccNative | kAccCompileDontBother) >>> 0,
    quickCode: api.artClassLinker.quickGenericJniTrampoline,
    interpreterCode: api.artInterpreterToCompiledCodeBridge
}, vm);
```

调用`cloneArtMethod()`复制原函数的ArtMethod，后续的修改都在这个副本上进行的。之后调用`patchArtMethod()`方法对复制出来的ArtMethod中的`jniCode`、`accessFlags`、`quickCode`、`interpreterCode`进行修复，具体见patchArtMethod。这里分析一下入参：

- accessFlags：

	- 清掉 `kAccCriticalNative`，避免走 critical native 调用路径。
	- 清掉 `kAccFastNative`，避免走 fast native 调用路径。
	- 清掉 `kAccNterpEntryPointFastPathFlag`，避免 nterp（ART使用的新一代解释器，逐步取代了早期的Mterp）快路径绕过 Frida 预期的调用路径。
	- 加上 `kAccNative`，告诉 ART 这个method 是 native 方法。
	- 加上 `kAccCompileDontBother`，告诉 ART 编译器不要尝试编译这个方法，因为 native 方法已经是机器码，不需要 ART JIT/AOT 编译。**总结一下就是 把方法标记为普通的 native 方法，同时禁用 ART 的特殊快速路径优化。**
- quickCode

原本是quick模式入口，现修改成`api.artClassLinker.quickGenericJniTrampoline`，代表的是`ClassLinker`的`quick_generic_jni_trampoline_`字段。也就是说，从 quick 路径进入这个方法时，不直接执行原来的 quick compiled code，而是进入 ART 的通用 JNI 调用桥，再由 JNI 桥读取 `jniCode` 并调用native化的hook代码。
- interpreterCode

原本是解释器模式入口，现修改成`api.artInterpreterToCompiledCodeBridge`，是从解释器模式转成机器码模式的入口。这样解释器执行该方法时，会桥接到 compiled/JNI 路径，最终进入 generic JNI trampoline 和 native化的hook代码。

```js
// Remove kAccFastInterpreterToInterpreterInvoke and kAccSkipAccessChecks to disable use_fast_path
// in interpreter_common.h
// 修改被 hook 的原始 ArtMethod 的 access_flags，目的不是把原方法直接改成 replacement，而是让 ART 后续调用原方法时不要走某些 fast path，从而确保 Frida 的 replacement 映射逻辑有机会介入。
let hookedMethodRemovedFlags = kAccFastInterpreterToInterpreterInvoke | kAccSingleImplementation | kAccNterpEntryPointFastPathFlag;
if ((originalFlags & kAccNative) === 0) {
    hookedMethodRemovedFlags |= kAccSkipAccessChecks;
}
// 修复原方法的ArtMethod
patchArtMethod(hookedMethodId, {
    accessFlags: ((originalFlags & ~(hookedMethodRemovedFlags)) | kAccCompileDontBother) >>> 0
}, vm);
```

这里对原方法的`accessFlags`进行了处理，禁用了快速调用路径标志，如果原方法不是 native，还需要移除访问检查跳过标志，最后加上`kAccCompileDontBother`，告诉 ART 不要尝试 JIT/AOT 编译这个方法。

```js
const quickCode = this.originalMethod.quickCode;

// Replace Nterp quick entrypoints with art_quick_to_interpreter_bridge to force stepping out
// of ART's next-generation interpreter and use the quick stub instead.
if (artNterpEntryPoint !== null && quickCode.equals(artNterpEntryPoint)) {
    patchArtMethod(hookedMethodId, {
        quickCode: api.artQuickToInterpreterBridge
    }, vm);
}
```

如果原方法是解释执行，且使用了Nterp，那么`quickCode`就会替换成`art_quick_to_interpreter_bridge`，强制跳出解释器模式，并改用机器码模式。

```js
if (!isArtQuickEntrypoint(quickCode)) {
    const interceptor = new ArtQuickCodeInterceptor(quickCode);
    // 开始patch
    interceptor.activate(vm);

    this.interceptor = interceptor;
}
```

如果原方法的quickCode是 ART Quick 编译路径的入口，也就是说原方法已经是机器码模式了，那么就需要通过`ArtQuickCodeInterceptor`对机器码进行patch，这部分见ArtQuickCodeInterceptor.activate。

最后是收尾工作

```js
// 使用hash表记录已经替换的方法，方便后续恢复
artController.replacedMethods.set(hookedMethodId, replacementMethodId);
notifyArtMethodHooked(hookedMethodId, vm);
```

### fetchArtMethod

```js
function fetchArtMethod (methodId, vm) {
  const artMethodSpec = getArtMethodSpec(vm);
  const artMethodOffset = artMethodSpec.offset;
  return (['jniCode', 'accessFlags', 'quickCode', 'interpreterCode']
    .reduce((original, name) => {
      const offset = artMethodOffset[name];
      if (offset === undefined) {
        return original;
      }
      const address = methodId.add(offset);
      const read = (name === 'accessFlags') ? readU32 : readPointer;
      original[name] = read.call(address);
      return original;
    }, {}));
}
```

`getArtMethodSpec`返回的是`ArtMethod`结构体布局描述，返回的结构是

```json
{
  size: <ArtMethod结构体大小>,
  offset: {
    jniCode: <偏移，对应字段为JNI函数指针(native方法入口)>,
    quickCode: <偏移，对应字段为指向JIT/AOT编译后的机器码的入口>,
    accessFlags: <偏移，对应字段为方法的修饰信息>,
    interpreterCode: <偏移，对应字段为方法解释执行的入口>
  }
}
```

由于Android版本的差异，有些字段就不存在（例如interpreterCode），于是借助`reduce`过滤出存在的字段并获取对应字段的值。

### patchArtMethod

```js
function patchArtMethod (methodId, patches, vm) {
  const artMethodSpec = getArtMethodSpec(vm);// 获取ArtMethod中字段偏移
  const artMethodOffset = artMethodSpec.offset;
  Object.keys(patches).forEach(name => {
    const offset = artMethodOffset[name];
    if (offset === undefined) {
      return;
    }
    const address = methodId.add(offset);
    const write = (name === 'accessFlags') ? writeU32 : writePointer;
    write.call(address, patches[name]);// 修改字段的值
  });
}
```

获取`jniCode`、`accessFlags`、`quickCode`、`interpreterCode`字段，并进行修正，设置为相应的入参值。

## ArtQuickCodeInterceptor.activate

```js
activate (vm) {
    const constraints = this._allocateTrampoline();

    const { trampoline, quickCode, redirectSize } = this;
    // Arm64下对应writeArtQuickCodeReplacementTrampolineArm64函数
    const writeTrampoline = artQuickCodeReplacementTrampolineWriters[Process.arch];
    const prologueLength = writeTrampoline(trampoline, quickCode, redirectSize, constraints, vm);
    this.overwrittenPrologueLength = prologueLength;

    this.overwrittenPrologue = Memory.dup(this.quickCodeAddress, prologueLength);
    // Arm64下对应writeArtQuickCodePrologueArm64函数
    const writePrologue = artQuickCodePrologueWriters[Process.arch];
    writePrologue(quickCode, trampoline, redirectSize);
}
```

该函数首先调用`_allocateTrampoline()`方法分片trampoline的内存空间、确定用于重定向的字节大小，以及获取空闲寄存器。以Arm64为例，接下来调用`writeArtQuickCodeReplacementTrampolineArm64()`函数编写trampoline，返回用于重定向的字节大小，然后保存原函数quickCode入口处相应字节大小的指令，用于后续恢复。最后调用`writeArtQuickCodePrologueArm64()`函数修改quickCode入口使其跳转到编写好的trampoline处。

### writeArtQuickCodeReplacementTrampolineArm64

```js
function writeArtQuickCodeReplacementTrampolineArm64 (trampoline, target, redirectSize, { availableScratchRegs }, vm) {
  const artMethodOffsets = getArtMethodSpec(vm).offset;

  let offset;
  Memory.patchCode(trampoline, 256, code => {
    const writer = new Arm64Writer(code, { pc: trampoline });
    const relocator = new Arm64Relocator(target, writer);
    // 保存CPU上下文
    // Save FPRs.
    writer.putPushRegReg('d0', 'd1');
    writer.putPushRegReg('d2', 'd3');
    writer.putPushRegReg('d4', 'd5');
    writer.putPushRegReg('d6', 'd7');

    // Save core args, callee-saves & LR.
    writer.putPushRegReg('x1', 'x2');
    writer.putPushRegReg('x3', 'x4');
    writer.putPushRegReg('x5', 'x6');
    writer.putPushRegReg('x7', 'x20');
    writer.putPushRegReg('x21', 'x22');
    writer.putPushRegReg('x23', 'x24');
    writer.putPushRegReg('x25', 'x26');
    writer.putPushRegReg('x27', 'x28');
    writer.putPushRegReg('x29', 'lr');

    // Save ArtMethod* + alignment padding.
    writer.putSubRegRegImm('sp', 'sp', 16); // sub sp, sp, 16
    writer.putStrRegRegOffset('x0', 'sp', 0);// str x0, [sp, #0]
    // 插入调用findReplacementFromQuickCode的指令,查找是否存在replacement method，如果没有返回NULL
    writer.putCallAddressWithArguments(artController.replacedMethods.findReplacementFromQuickCode, ['x0', 'x19']);

    writer.putCmpRegReg('x0', 'xzr');// cmp x0, xzr
    writer.putBCondLabel('eq', 'restore_registers');// b.eq restore_registers

    // Set value of x0 in the current frame.
    writer.putStrRegRegOffset('x0', 'sp', 0);// str x0, [sp, #0]
    // 恢复CPU上下文
    writer.putLabel('restore_registers');

    // Restore ArtMethod*
    writer.putLdrRegRegOffset('x0', 'sp', 0);
    writer.putAddRegRegImm('sp', 'sp', 16);

    // Restore core args, callee-saves & LR.
    writer.putPopRegReg('x29', 'lr');
    writer.putPopRegReg('x27', 'x28');
    writer.putPopRegReg('x25', 'x26');
    writer.putPopRegReg('x23', 'x24');
    writer.putPopRegReg('x21', 'x22');
    writer.putPopRegReg('x7', 'x20');
    writer.putPopRegReg('x5', 'x6');
    writer.putPopRegReg('x3', 'x4');
    writer.putPopRegReg('x1', 'x2');

    // Restore FPRs.
    writer.putPopRegReg('d6', 'd7');
    writer.putPopRegReg('d4', 'd5');
    writer.putPopRegReg('d2', 'd3');
    writer.putPopRegReg('d0', 'd1');

    writer.putBCondLabel('ne', 'invoke_replacement');//b.ne invoke_replacement
    // 没有replacement
    do {
      offset = relocator.readOne();
    } while (offset < redirectSize && !relocator.eoi);
    // 将原函数开头前redirectSize字节写入trampoline
    relocator.writeAll();
    // 原函数字节数 > redirectSize, 跳转到剩余部分继续执行
    if (!relocator.eoi) {
      const scratchReg = Array.from(availableScratchRegs)[0];
      writer.putLdrRegAddress(scratchReg, target.add(offset));// ldr x16/x17, qucikcode + redirectSize
      writer.putBrReg(scratchReg);// br x16/x7
    }
    // 有replacement
    writer.putLabel('invoke_replacement');

    writer.putLdrRegRegOffset('x16', 'x0', artMethodOffsets.quickCode);// ldr x16, [x0, #quickCode]
    writer.putBrReg('x16');// br x16;

    writer.flush();
  });

  return offset;
}
```

首先保存部分寄存器，然后调用`findReplacementFromQuickCode`方法查找是否存在replacement实现，如果有，则返回相应地址，否则为NULL（0），这里分情况进行讨论分析：

- 没有replacement实现，即 `x0 == 0`，跳到 `restore_registers`标签，从栈中恢复部分寄存器，此时`x0`还是原函数的methodId，接着将原始指令重写到 trampoline 中，执行完这些指令后，最后跳转到原 quick code 剩下的部分继续执行。
- 有replacement实现，即 `x0 != 0`，把返回的 replacement methodId 写回栈顶，然后恢复部分寄存器，此时`x0`就是 replacement methodId。接着跳转到`invoke_replacement`标签处，跳转到replacement method的quickCode入口进行执行。

#### findReplacementFromQuickCode

位置在`lib\android.js` 1925行处。

```c
gpointer
find_replacement_method_from_quick_code (gpointer method, gpointer thread)
{
  gpointer replacement_method;
  gpointer managed_stack;
  gpointer top_quick_frame;
  gpointer link_managed_stack;
  gpointer * link_top_quick_frame;

  replacement_method = get_replacement_method (method);
  if (replacement_method == NULL)
    return NULL;

  /*
   * Stack check.
   *
   * Return NULL to indicate that the original method should be invoked, otherwise
   * return a pointer to the replacement ArtMethod.
   *
   * If the caller is our own JNI replacement stub, then a stack transition must
   * have been pushed onto the current thread's linked list.
   *
   * Therefore, we invoke the original method if the following conditions are met:
   *   1- The current managed stack is empty.
   *   2- The ArtMethod * inside the linked managed stack's top quick frame is the
   *      same as our replacement.
   */
  managed_stack = thread + ${threadOffsets.managedStack};
  top_quick_frame = *((gpointer *) (managed_stack + ${managedStackOffsets.topQuickFrame}));
  if (top_quick_frame != NULL)
    return replacement_method;

  link_managed_stack = *((gpointer *) (managed_stack + ${managedStackOffsets.link}));
  if (link_managed_stack == NULL)
    return replacement_method;

  link_top_quick_frame = GSIZE_TO_POINTER (*((gsize *) (link_managed_stack + ${managedStackOffsets.topQuickFrame})) & ~((gsize) 1));
  if (link_top_quick_frame == NULL || *link_top_quick_frame != replacement_method)
    return replacement_method;

  return NULL;
}

gpointer
get_replacement_method (gpointer original_method)
{
  gpointer replacement_method;

  g_mutex_lock (&lock);

  replacement_method = g_hash_table_lookup (methods, original_method);

  g_mutex_unlock (&lock);

  return replacement_method;
}
```

主要是根据传入的原函数methodId 查找对应的replacement methodId，返回 NULL 表示应调用原始方法，否则返回指向replacement ArtMethod 的指针。

这里做了栈检查，这样来自hook逻辑中的原函数调用就不会是无限递归，而是返回NULL，执行原函数逻辑。这就是我们在hook A函数，并能够在hook逻辑内部调用原始A函数的原因。

### writeArtQuickCodePrologueArm64

```js
function writeArtQuickCodePrologueArm64 (target, trampoline, redirectSize) {
  Memory.patchCode(target, 16, code => {
    const writer = new Arm64Writer(code, { pc: target });

    if (redirectSize === 16) {
      writer.putLdrRegAddress('x16', trampoline);// ldr x16, trampoline
    } else {
      writer.putAdrpRegAddress('x16', trampoline);// adrp x16, trampoline
    }

    writer.putBrReg('x16');// br x16

    writer.flush();
  });
}
```

这里则是根据可用重定位空间为8字节或16字节，设置不同的跳转指令。

# 总结

Frida 在进行 Java Hook时，首先会将用户编写的 JS 函数包装成 `NativeCallback`，使其具备 JNI native 函数的调用形式。之后的hook工作都围绕 `ArtMethod` 做修改。它会读取目标方法的 `jniCode`、`accessFlags`、`quickCode`、`interpreterCode` 字段，复制出一个 `ArtMethod`副本，用于replacement method，并**把这个副本改造成 native 方法**：`jniCode` 指向前面生成的 `NativeCallback`，`quickCode` 指向 ART 的通用 JNI trampoline，`interpreterCode` 指向解释器到编译代码的桥接入口。这样无论方法从解释器路径还是 quick compiled code 路径进入，最终都能转到 Frida 的 replacement 实现。需要额外注意的是，**对于已经编译成机器码的方法，Frida 还会 patch 原始机器码入口**，即修改原始机器码前 8/16 字节为跳转到 trampoline 的指令，trampoline 中再通过 `findReplacementFromQuickCode()` 查询当前方法是否存在 replacement。如果存在，就跳转到 replacement method 入口；如果不存在，或者当前调用来自 Hook 逻辑内部对原函数的调用，则恢复执行原方法。

---

参考：

https://deepwiki.com/frida/frida-java-bridge/4.1-method-hooking-basics

[[原创]源码简析之ArtMethod结构与涉及技术介绍-Android安全-看雪安全社区｜专业技术交流与安全研究论坛](https://bbs.kanxue.com/thread-248898-1.htm)

[Frida Internal - Part 3: Java Bridge 与 ART hook - 有价值炮灰](https://evilpan.com/2022/04/17/frida-java/)

---

# 回复

## 回复 by Imxz (#2)

*2026-5-11 15:22*

tql
