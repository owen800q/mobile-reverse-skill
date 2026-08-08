---
title: '[原创]IDA Domain: 更Pythonic的 IDA API'
url: https://bbs.kanxue.com/thread-289091.htm
tid: 289091
author: 温泉划水鱼
date: '2025-11-15'
tags: [Android安全, 原创, 漏洞相关, NDK分析, 工具脚本, 其他, 基础理论]
crawled_at: '2026-08-08T10:38:07+00:00'
replies: 24
---

# ida_domain

翻 Hex-Ray 文档时发现了一个好玩的新功能, 差不多8月份发布的，还挺新

ida domain — “一个对初学者友好的开源 Domain API，简化了脚本编写和插件开发，使其以前所未有的方式变得易于上手——以 Pythonic 的方式。”

ida domain 兼容现有的 idc 和 idapython api

macOS环境配置

| 123456789101112131415 | `nano ~``/``.zshrc` `/``/``写入这行 (推荐使用ida9.``2``，可以直接看microCode)``export IDADIR``=``"/Applications/IDA Professional 9.2.app/Contents/MacOS/"` `^X, 然后一直回车` `/``/``验证``echo $IDADIR` `然后pip install ida``-``domain` `/``/``开一个干净的虚拟环境``python` `-``m venv ida``-``env``source ida``-``env``/``bin``/``activate` |
|-|-|

在test.py文件中写入

| 12345678 | `try``:``from` `ida_domain` `import` `Database``print``(``"✓ Installation successful!"``)``except` `ImportError as e:``print``(f``"✗ Installation failed: {e}"``)` `/``/``python test.py``>>> ✓ Installation successful!` |
|-|-|

当然，也可以直接在 IDA 控制台或 IpyDA 里写

IDA Domain API 有以下常用对象实体

- Database - idb数据库操作
- Entries - 入口点管理与分析
- Segments - 内存段操作
- Functions - 函数分析与操作
- Flowchart - 控制流程图和基本模块操作
- Instructions - 指令级分析
- Operands - 操作数分析和操作
- Bytes - 原始字节操作和分析
- Strings - 字符串检测与分析
- Types - 类型信息和管理
- Heads - Address head management （）
- Hooks - 钩子/事件处理
- XRefs - 交叉引用分析
- Names - Symbol name management（符号名称管理）
- Comments - 注释管理
Signature Files - FLIRT 签名文件操作

比老的 idapython api 结构清晰多了，看着就舒服

ida 会把反编译器分析的信息都保存到 idb 中，在 ida_domain 中把 idb 作为入口对象来操作

| 123456 | `import` `ida_domain``db` `=` `ida_domain.Database()``print``(f``'  Entry point: {hex(db.entries[0].address)}'``)``# db.functions.get_all() 通过db绑定的实例访问对象` `>>>  Entry point:` `0x1be23c` |
|-|-|

G 0x1be23c 正是JNI_OnLoad()

 ![image](https://bbs.kanxue.com/upload/attach/202511/991803_EAB4CSCBHC7GJZH.webp)

可以通过一个经典的获取函数对象的方法看到 api 设计思路上的差别

| 12345678910 | `# ida_domain``func` `=` `db.functions.get_at(``0x1DE5C4``)``db.functions.get_disassembly(func)` `# idapython``import` `idautils``func` `=` `idaapi.get_func(``0x1DE5C4``)` `# idapython``dism_addr` `=` `list``(idautils.FuncItems(``0x1DE5C4``))``for` `line` `in` `dism_addr:``print``(``"0x%x %s"` `%` `(line,idc.generate_disasm_line(line,` `0``)))` |
|-|-|

如果使用 idapython 那你必须熟悉 idapython 的结构还有哪些模块里存了哪些函数，想使用什么功能得进源码里一顿找, ida_domain 把相关 api 通过实例对象组装到一起，极大地减小了学习成本。

之前访问 microCode 和 ctree 要通过遍历整个结构树来获取，借助ida_domain轻松获取, 非常nice

| 1234567891011121314 | `func` `=` `db.functions.get_at(``0x1DE5C4``)``db.functions.get_microcode(func)` `# 获取微码``db.functions.get_pseudocode(func)` `# 获取伪c``# 基于idapython的比较长，不写了` `# 获取指定偏移处的微码``mcode` `=` `db.bytes.get_microcode_between(``0x1DE608``,` `0x1DE60C``)` `>>>``[``'1. 0 mov    #0x138.8, t2.8          ; 1DE608 u=           d=t2.8'``,``'1. 1 add    x0.8, t2.8, t2.8        ; 1DE608 u=x0.8,t2.8  d=t2.8'``,``'1. 2 ldx    cs.2, t2.8, t1.8        ; 1DE608 u=t2.8,cs.2,(ALLMEM) d=t1.8'``,``'1. 3 mov    t1.8, x19.8             ; 1DE608 u=t1.8       d=x19.8'``,``'1. 4 goto   @2                      ; 1DE608 u='``]` |
|-|-|

值得一提，在 idapython 中对ui事件，反编译事件等等的hook都分散在不同的模块中，在ida_domain 中聚合了大部分的事件hook

通过反编译钩子 DecompilerHooks 看一下 ida反编译的内部执行流程

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465 | `import` `ida_hexrays,idaapi``from` `ida_domain` `import` `database, hooks``class` `MyDecompilerHooks(hooks.DecompilerHooks):``def` `__init__(``self``):``super``().__init__()` `def` `log(``self``,msg:` `str` `=` `''):``print``(msg)` `def` `glbopt(``self``,mba):``self``.log(``"glbopt"``)``return` `super``().glbopt(mba)` `def` `prealloc(``self``, mba):``self``.log(``"prealloc"``)``return` `super``().prealloc(mba)` `def` `locopt(``self``, mba):``self``.log(``"locopt"``)``return` `super``().locopt(mba)` `def` `preoptimized(``self``,mba):``self``.log(``"preoptimized"``)``return` `super``().preoptimized(mba)` `def` `microcode(``self``, mba_t)` `-``>` `int``:``self``.log(``"microcode"``)``return` `super``().microcode(mba_t)` `def` `prolog(``self``,mba,fc,reachable_blocks,decomp_flags):``self``.log(``"prolog"``)``return` `super``().prolog(mba, fc, reachable_blocks, decomp_flags)` `def` `stkpnts(``self``,mba,``*``sps):``self``.log(``"stkpnts"``)``return` `super``().stkpnts(mba,` `*``sps)` `def` `flowchart(``self``,fc,mba,reachable_blocks,decomp_flags):``self``.log(``"flowchart"``)``return` `super``().flowchart(fc, mba, reachable_blocks, decomp_flags)`  `decomp_hook` `=` `MyDecompilerHooks()``decomp_hook.hook()` `/``/``然后输入这句，强制ida重新分析这个函数``ida_hexrays.mark_cfunc_dirty(``0x1DE5C4``)` `手动f5` `>>> flowchart` `stkpnts 计算sp指针的移动``prolog` `microcode 微码已经生成``preoptimized 下面对应微码的不同成熟度``locopt``prealloc``prealloc``prealloc``prealloc``prealloc``prealloc``glbopt``...``之后生成ctree,伪c代码` |
|-|-|

可惜 ida_domain 暂时还没有能直接操作微码的api，不过可以和 idapython 的 API 结合着用，总之未来可期

[+] ida内部反编译流程，ctree和microcode
https://www.elastic.co/security-labs/introduction-to-hexrays-decompilation-internals

[+] ida_domain Hexray官方教程
https://ida-domain.docs.hex-rays.com/getting_started/#step-3-verify-installation

[+] ida_domain github 源码
https://github.com/HexRaysSA/ida-domain

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2025-11-15 08:00*

感谢分享

## 回复 by KanXue_NG (#3)

*2025-11-15 10:01*

学习学习

## 回复 by 乐活 (#4)

*2025-11-15 15:02*

xxxx

## 回复 by MaYil (#5)

*2025-11-15 15:41*

感谢分享

## 回复 by wx_插曲 (#6)

*2025-11-15 17:59*

大佬牛逼

## 回复 by didiid (#7)

*2025-11-16 00:18*

666

## 回复 by yangshuang (#8)

*2025-11-16 11:35*

111

## 回复 by kingking888 (#9)

*2025-11-16 20:49*

666

## 回复 by 周旋久 (#10)

*2025-11-16 22:18*

mark

## 回复 by adnin (#11)

*2025-11-17 19:07*

mark

## 回复 by wx_Huber Barrientos (#12)

*2025-11-18 03:40*

为你点赞！

## 回复 by huangjw (#13)

*2025-11-19 09:35*

试试先

## 回复 by 龙飞雪 (#14)

*2025-11-19 19:43*

感谢分享

## 回复 by 昭玄大统 (#15)

*2025-11-24 21:35*

666

## 回复 by 带带弟弟吧 (#16)

*2025-12-25 01:10*

1

## 回复 by 蓝色水瓶 (#17)

*2025-12-29 21:39*

666

## 回复 by Eknight (#18)

*2026-1-6 17:35*

666

## 回复 by mb_uzmffdbw (#19)

*2026-1-21 15:11*

6

## 回复 by git_94730eaydwshawke-gif (#20)

*2026-1-24 18:48*

666

## 回复 by caxfan (#21)

*2026-1-30 10:19*

看看

## 回复 by wocaocou (#22)

*2026-2-6 22:19*

点赞

## 回复 by Thehepta (#23)

*2026-3-4 17:36*

1

## 回复 by xxjj678 (#24)

*2026-3-7 22:33*

666

## 回复 by ldz666 (#25)

*2026-7-2 14:39*

666
