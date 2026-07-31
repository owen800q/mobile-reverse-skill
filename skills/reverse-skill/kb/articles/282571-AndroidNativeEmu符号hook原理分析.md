---
title: '[原创]AndroidNativeEmu符号hook原理分析'
url: https://bbs.kanxue.com/thread-282571.htm
tid: 282571
author: mb_ztaoodiz
date: '2024-07-19'
tags: [Android安全, 原创, 基础理论, 程序开发, HOOK注入, 源码框架, 工具脚本]
crawled_at: '2026-07-31T14:22:56+08:00'
replies: 3
---

# AndroidNativeEmu符号hook原理分析

AndroidNativeEmu支持某个函数符号进行hook，代码实例如下：

| 12345 | `@native_method``def` `sprintf(mu, buffer_addr, format_addr, arg1, arg2):``print``(``"sprintf(%x,%x,%x,%x)"` `%` `(buffer_addr, format_addr, arg1, arg2))` `emulator.modules.add_symbol_hook(``"sprintf"``, emulator.hooker.write_function(sprintf)` `+` `1``)` |
|-|-|

他是怎么实现的呢？我们从其源代码来分析。

考虑如下问题：

1. 如何实现的函数符号的hook？

初步的猜想是将符号表的对应地址值填为指定函数的地址，后续解析符号的时候，就将该符号的地址填充过去。但是这样存在问题，因为我们的函数是python函数，没有地址，所以无法直接跳转到我们的python函数。
2. 根据问题1，是如何将hook的地址和python函数关联的？

unicorn本身的hook是只支持对某个地址区域进行hook的，只要执行到这个区域的代码，就会调用对应的python函数。但是这里是符号hook，而不是地址区域hook。

#### emulator.hooker.write_function(sprintf)分析

首先从`emulator.hooker.write_function(sprintf)`开始分析，进去看看他干了什么。

###### hooker

先看看emulator内部的hooker对象是啥，进入到emulator的构造函数中：

| 1234 | `HOOK_MEMORY_BASE` `=` `0x20000000``HOOK_MEMORY_SIZE` `=` `0x00200000``# HOOK_MEMORY_BASE和HOOK_MEMORY_SIZE好像是模拟器专门定义的一个用来hook的内存区域，这个区域执行的代码都会调用unicorn的原生hook``self``.hooker` `=` `Hooker(``self``, HOOK_MEMORY_BASE, HOOK_MEMORY_SIZE)` |
|-|-|

可以看到他是Hooker的实例，再进入Hooker类，其构造函数部分的代码如下：

| 12345678910111213141516171819202122 | `from` `keystone` `import` `Ks, KS_ARCH_ARM, KS_MODE_THUMB``from` `unicorn` `import` `*``from` `unicorn.arm_const` `import` `*` `STACK_OFFSET` `=` `8`  `# Utility class to create a bridge between ARM and Python.``class` `Hooker:` `def` `__init__(``self``, emu, base_addr, size):``self``._emu` `=` `emu``self``._keystone` `=` `Ks(KS_ARCH_ARM, KS_MODE_THUMB)``self``._size` `=` `size``self``._current_id` `=` `0xFF00``self``._hooks` `=` `dict``()``self``._hook_magic` `=` `base_addr``self``._hook_start` `=` `base_addr` `+` `4``# _hook_current的地址是从HOOK_MEMORY_BASE开始的``self``._hook_current` `=` `self``._hook_start``# 在unicorn中设置了hook，对应的回调函数为_hook``self``._emu.uc.hook_add(UC_HOOK_CODE,` `self``._hook,` `None``,` `self``._hook_start,` `self``._hook_start` `+` `size)` |
|-|-|

到这里，hooker对象就创建完成了。还是比较简单，就是抽象了一个专门的地址区域用于hook，同时在unicorn中给这段地址区域设置了UC_HOOK_CODE。

###### write_function

接下来是`hook.write_function`：

| 1234567891011121314151617181920212223242526 | `def` `write_function(``self``, func):``# Get the hook id.``# 生成了一个hook_id和当前的hook区域的地址``hook_id` `=` `self``._get_next_id()``hook_addr` `=` `self``._hook_current` `# 创建了一段汇编代码，其中包含了hook的id``asm` `=` `"PUSH {R4,LR}\n"` `\``"MOV R4, #"` `+` `hex``(hook_id)` `+` `"\n"` `\``"MOV R4, R4\n"` `\``"POP {R4,PC}"` `asm_bytes_list, asm_count` `=` `self``._keystone.asm(bytes(asm, encoding``=``'ascii'``))` `if` `asm_count !``=` `4``:``raise` `ValueError(``"Expected asm_count to be 4 instead of %u."` `%` `asm_count)` `# 将代码写入特定的hook区域``self``._emu.uc.mem_write(hook_addr, bytes(asm_bytes_list))` `# 地址和id向后移动。``self``._hook_current` `+``=` `len``(asm_bytes_list)``# 将python的函数和id关联``self``._hooks[hook_id]` `=` `func``# 这个代码区域的地址``return` `hook_addr` |
|-|-|

简单来说，就是创建了一段特殊的代码区域，返回了这个区域的地址。这个代码区域有特定的id标识`（为了区分不同的函数hook）`，且这段内存区域在unicorn中被设置了回调函数`（hooker的构造函数中）`。

#### emulator.modules.add_symbol_hook("sprintf", emulator.hooker.write_function(sprintf) + 1)

这个函数实现非常简单：

| 12 | `def` `add_symbol_hook(``self``, symbol_name, addr):``self``.symbol_hooks[symbol_name]` `=` `addr` |
|-|-|

就是将`write_function`返回的地址写入到符号表中，后续其他依赖这个函数的库会解析为对应的地址。也就是说，后续执行这个符号对应的函数的时候，就会跳转到`write_function`中生成的代码区域。同时要注意，这个区域是被hook了的。所以，我们要去看看Hooker类中的`_hook`方法是如何实现的，看看他做了什么处理

#### _hook方法

| 123456789101112131415161718 | `def` `_hook(``self``, uc, address, size, user_data):``# 这里是在检查这段代码的特征，看看是否是write_function函数生成的代码``# Check if instruction is "MOV R4, R4"``if` `size !``=` `2` `or` `self``._emu.uc.mem_read(address, size) !``=` `b``"\x24\x46"``:``return``# 如果是，说明这个区域是被hook的，从这个区域中读取到hook_id``# Find hook.``hook_id` `=` `self``._emu.uc.reg_read(UC_ARM_REG_R4)``hook_func` `=` `self``._hooks[hook_id]` `# Call hook.``try``:``# 调用对应的方法``hook_func(``self``._emu)``except``:``# Make sure we catch exceptions inside hooks and stop emulation.``uc.emu_stop()``raise` |
|-|-|

#### 总结

回答之前我们的提问：

1. 如何实现的符号hook？

对于符号的hook确实是依赖于对符号表的hook实现的，但是其地址不能是python函数的地址。框架的作者专门为每个被hook的函数开辟了一块内存空间，放入一些特殊的汇编代码和一个函数的id，通过这个id能找到对应的python函数。同时这个内存区域是被unicorn的原生hook hook了的，会调用框架内部的处理函数。在该处理函数中，会从这个内存区域中去找到函数id，从而得到该符号对应的python函数进行调用。

# @native_method装饰器分析

通过前面的分析，我们已经知道了如何将符号和我们对应的python函数关联上。但是还存在一个问题，就是函数参数的问题，如何将函数参数传递给对应的python参数？这就要用到框架提供的`@native_method`装饰器

### 什么是装饰器？

装饰器本质上是一个可调用对象，它接收一个函数作为参数，并返回一个新函数或可调用对象。装饰器通常用于横切关注点（cross-cutting concerns），如日志记录、权限检查、缓存等。

实例：

| 12345678910111213 | `def` `my_decorator(func):``def` `wrapper(``*``args,` `*``*``kwargs):``print``(``"Something is happening before the function is called."``)``result` `=` `func(``*``args,` `*``*``kwargs)``print``(``"Something is happening after the function is called."``)``return` `result``return` `wrapper` `@my_decorator``def` `say_hello(name):``print``(f``"Hello, {name}!"``)` `say_hello(``"Alice"``)` |
|-|-|

在这个示例中，`@my_decorator` 应用于 `say_hello` 函数，等价于 `say_hello = my_decorator(say_hello)`。当你调用 `say_hello("Alice")` 时，实际执行的是 `wrapper` 函数。

### native_method源代码分析

源代码如下：

| 123456789101112131415161718192021222324252627282930 | `def` `native_method(func):``def` `native_method_wrapper(``*``argv):``"""``:type self``:type emu androidemu.emulator.Emulator``:type uc Uc``"""` `emu` `=` `argv[``1``]` `if` `len``(argv)` `=``=` `2` `else` `argv[``0``]``uc` `=` `emu.uc` `args` `=` `inspect.getfullargspec(func).args``args_count` `=` `len``(args)` `-` `(``2` `if` `'self'` `in` `args` `else` `1``)` `if` `args_count <` `0``:``raise` `RuntimeError(``"NativeMethod accept at least (self, uc) or (uc)."``)` `native_args` `=` `native_read_args(uc, args_count)` `if` `len``(argv)` `=``=` `1``:``result` `=` `func(uc,` `*``native_args)``else``:``result` `=` `func(argv[``0``], uc,` `*``native_args)` `if` `result` `is` `not` `None``:``native_write_arg_register(emu, UC_ARM_REG_R0, result)``else``:``uc.reg_write(UC_ARM_REG_R0, JNI_ERR)` `return` `native_method_wrapper` |
|-|-|

所以，在我们的代码中：

| 123456 | `@native_method``def` `sprintf(mu, buffer_addr, format_addr, arg1, arg2):``print``(``"sprintf(%x,%x,%x,%x)"` `%` `(buffer_addr, format_addr, arg1, arg2))``format` `=` `memory_helpers.read_utf8(mu, format_addr)``result` `=` `format` `%` `(memory_helpers.read_utf8(mu, arg1), arg2)``mu.mem_write(buffer_addr, result.encode()` `+` `b``'\x00'``)` |
|-|-|

调用sprintf之前，实际上调用的是native_method方法，该方法对sprintf进行了装饰。

而其native_method_wrapper装饰的实现就是在获取函数参数的个数，然后从寄存器中获取对应的参数，传递给python。

##### 扩展思考

这个框架中的@native_method装饰器的作用是解析函数参数，从寄存器或者内存中读取参数再传递给python，但是他的实现是比较简陋的。本质上是利用inspect获取python的函数原型再决定读取几个参数。

比如，如果我们要完整的实现sprintf的hook就不太行，因为sprintf的参数是不定的，函数原型中不能知道具体有几个参数。只能解析spriintf的format来确定参数数量，再读取参数。当然实现起来有点麻烦，后续尝试写一下。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2024-7-20 00:15*

支持一下，不过不是有很多成熟的框架吗，比如unidbg，qiling

## 回复 by mb_ztaoodiz (#3)

*2024-7-20 08:27*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ldbucrik](https://bbs.kanxue.com/user-985313.htm)
>
>  支持一下，不过不是有很多成熟的框架吗，比如unidbg，qiling
>
>

各种框架都有自己的缺点，了解原理才能更好使用嘛。AndroidNativeEmu更加轻量一点，更容易学习

## 回复 by mb_ldbucrik (#4)

*2024-7-20 11:04*

有道理
