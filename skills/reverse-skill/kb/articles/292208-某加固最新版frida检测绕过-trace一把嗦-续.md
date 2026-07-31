---
title: '[原创]某加固最新版frida检测绕过-trace一把嗦(续)'
url: https://bbs.kanxue.com/thread-292208.htm
tid: 292208
author: 东方玻璃
date: '2026-07-29'
tags: [Android安全, 原创, 逆向分析, NDK分析, 混淆加固, 脱壳反混淆, HOOK注入, 工具脚本]
crawled_at: '2026-07-31T13:30:39+08:00'
replies: 46
---

目录- 前言
- V3-zgcbank
- dump so failed
- dump anonymous so
- unpack so
- 绕过线程检测函数
- trace + 二分法定位检测点
- V4-fengshou
- 绕过线程检测函数
- trace 定位检测点
- 总结
- References
# 前言

最近把收藏的百来篇网页技术文章保存到本地, 构建知识库供 AI 调用, 希望以此自动化 ai 一把嗦

实际使用下来确实有部分成果, 但依赖文章本身的准确性和完整性, AI 复现起来还是很快的

但没有对应资料时, 自动化嗦就有一些问题了:

- 如何省去人工打开 IDA 分析 so 的操作, 让 ai 自动调用 IDA 分析?

关于这个问题, 无名侠的 [IDA-NO-MCP](https://github.com/P4nda0s/IDA-NO-MCP) 足够用, 但是还不够自动化

于是搜索是否有 cli 版本, 正好有, 顺手让 ai 改了一份自用
- IDA 会导出海量反编译文件, 包括大量函数
- AI 的 Context 有限, 容易走进死胡同转圈, 反复踩坑
- 上来 hook exit, kill 等各种系统api, 力大砖飞
- AI 谎报军情, 说脚本通过了, 实际是卡死了 APP 造成存活假象

看到 AI 谎报军情还产出了一坨屎山, 选择回归手工, 途中 AI 的帮助主要是: 改 trace 脚本, 分析函数功能等

手工跑通一遍之后, 可以总结经验, 提取特征码, 让 AI 自动分析其他样本实现通杀, 没必要每个样本都手工

总而言之, 希望本文能给师傅们带来一些帮助和启发

环境:

- Macmini M4 Macos 15.7.7
- IDA Pro 9.4
- Pixel 6A Android 14

工具:

- Codex 梭哈
- [yynxxxxx/Codex-X](https://github.com/yynxxxxx/Codex-X) 指令提示词破限
- [Rusda](https://github.com/taisuii/rusda) 16.2.1 (Frida-tools 12.3.0)
- [ida-export-cli](https://github.com/OrientalGlass/ida-export-cli) 以 cli 的方式调用 ida 反编译,方便 AI 快速分析
- [glass-stalker-trace](https://github.com/OrientalGlass/glass-stalker-trace) Trace 函数调用链以及指定函数汇编细节

某加固最近的 4 个版本 (近2年):

| Version | libDexHelper.so | Bypass |
|-|-|-|
| V1 | 壳 so 解密释放真 so, 替换 soinfo 后运行 | Hook 线程检测函数即可 |
| V2 | 同 V1 | hook 线程检测函数 绕过非法内存访问崩溃点 绕过 crc 校验函数 |
| V3 | 壳 so 内置自定义 linker 加载真 so 到匿名内存 | 扫描定位真 so 基址 hook 线程检测函数 绕过新检测函数 |
| V4 | 同 V3 | V3 的基础上额外增加了检测函数 |

针对 V1-V2版本, dump so , trace 和 bypass 较为简单, 前文 [某加固新版frida检测绕过-trace一把嗦](https://bbs.kanxue.com/thread-289545.htm) 已有详细介绍

针对 V3-V4版本, 后续则使用二分法和 Trace 定位辅助分析, 在此感谢迷人哥的思路

**声明:**

1. **本文所述内容仅为技术研究与学习交流之目的, 所分析的 App 版权归其所属公司所有**
2. **作者未对任何 App 进行非法篡改, 破解, 数据窃取或商业利用, 亦不鼓励或支持任何违反法律法规的行为**
3. **读者不得将本文内容用于任何非法用途, 由此产生的一切法律责任由使用者自行承担**
4. **请遵守《中华人民共和国网络安全法》及相关法律法规**

# V3-zgcbank

## dump so failed

老式欧美打法, 起 frida-server, hook dlopen 并 dump so

```js
function dump_so(so_name, package_name) {
    var libso = Process.getModuleByName(so_name);
    console.log("[name]:", libso.name);
    console.log("[base]:", libso.base);
    console.log("[size]:", ptr(libso.size));
    console.log("[path]:", libso.path);

    var file_path = "/data/data/" + package_name + "/" + libso.name + "_" + libso.base + "_" + ptr(libso.size) + ".so";
    var file_handle = new File(file_path, "wb");
    if (file_handle && file_handle != null) {
        Memory.protect(ptr(libso.base), libso.size, 'rwx');
        var libso_buffer = ptr(libso.base).readByteArray(libso.size);
        file_handle.write(libso_buffer);
        file_handle.flush();
        file_handle.close();
        console.log("[dump]:", file_path);
    }
}

function hook_dlopen_dump_so(soName, package_name) {
    var once_flag = true;
    Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"),
        {
            onEnter: function (args) {
                var pathptr = args[0];
                if (pathptr !== undefined && pathptr != null) {
                    var path = ptr(pathptr).readCString();
                    if (path.indexOf(soName) >= 0) {
                        this.is_can_hook = true;
                    }
                }
            },
            onLeave: function (retval) {
                if (this.is_can_hook && once_flag) {
                    dump_so(soName, package_name);
                    once_flag = false;
                }
            }
        }
    );
}
function main(){
    hook_dlopen_dump_so("libDexHelper.so","com.mobile.zgcbank");
}
setImmediate(main);
```

会发现输出了目标 so 的基本信息,但是 dump 失败

![image](https://bbs.kanxue.com/upload/attach/202607/968342_6K5M8JWW929V3DT.png)

如果查看maps, 利用maps dump出的so则没有有效信息, 说明真实目标 so不在系统 linker 的soinfo list中

## dump anonymous so

推测存在自定义linker, 关于这方面知识点可参考前一篇文章 [Android从ELF-Loader到自定义Linker的实现及原理](https://bbs.kanxue.com/thread-290643.htm)

```js
function saveToFile(path, data) {
    const file = new File(path, "wb");
    file.write(data);
    file.flush();
    file.close();
}
function getElfFullSize(base) {
    try {
        const is64Bit = base.add(4).readU8() === 2;
        const e_phoff = is64Bit ? base.add(32).readS64() : base.add(28).readS32();
        const e_phnum = is64Bit ? base.add(56).readU16() : base.add(44).readU16();
        const p_size = is64Bit ? 56 : 32;

        let maxAddr = 0;
        for (let i = 0; i < e_phnum; i++) {
            const phdrAddr = base.add(e_phoff).add(i * p_size);
            const p_type = phdrAddr.readU32();

            if (p_type === 1) { // PT_LOAD
                const p_vaddr = is64Bit ? phdrAddr.add(16).readS64() : phdrAddr.add(8).readS32();
                const p_memsz = is64Bit ? phdrAddr.add(40).readS64() : phdrAddr.add(20).readS32();
                const end = p_vaddr + p_memsz;
                if (end > maxAddr) maxAddr = end;
            }
        }
        // 向上对齐到页 (4096)
        return (maxAddr + 0xFFF) & ~0xFFF;
    } catch (e) {
        console.log("    [!] 无法解析 Phdr 计算大小，跳过。");
        return 0;
    }
}
function dump_module(base, soName, saveDir) {
    console.log(`[+] Dump 模块: ${soName} at ${base}, save to ${saveDir}`);
    // 2. 计算整个 SO 的内存大小 (解析 PT_LOAD)
    const fullSize = getElfFullSize(base);
    if (fullSize === 0) return;

    // 3. 执行 Dump
    const fileName = `${soName}_${base}_${fullSize}.so`;
    const filePath = saveDir + fileName;

    const dumpData = base.readByteArray(fullSize);
    saveToFile(filePath, dumpData);

    console.log(`[+] Dump 成功: ${filePath}`);
    console.log(`    Size: ${(fullSize / 1024 / 1024).toFixed(2)} MB (${fullSize} Bytes)`);
}

function scanHiddenModules(soName, pkgName) {
    const saveDir = `/data/data/${pkgName}/`;
    console.log(`[*] 开始扫描内存，Dump 文件将保存至: ${saveDir}`);

    // 0.获取所有已知模块基地址, 设置白名单
    const knownModules = Process.enumerateModules().map(m => m.base.toString());

    // 遍历app进程内存范围
    Process.enumerateRanges({
        protection: 'r-x',
        coalesce: true
    }).forEach(function (range) {
        try {
            // 1. 验证 ELF 魔数
            const buf = range.base.readByteArray(4);
            if (!buf) return;
            const bytes = new Uint8Array(buf);
            if (bytes[0] === 0x7f && bytes[1] === 0x45 && bytes[2] === 0x4c && bytes[3] === 0x46) {
                // 2. 获取内存范围所属基地址, 验证是否为已知模块
                const base = range.base;
                if (knownModules.indexOf(base.toString()) !== -1) return;
                console.log(`[!] 发现隐藏模块: ${base}`);
                 // 3. 发现匿名模块, dump
                dump_module(base, soName, saveDir);

            }
        } catch (e) { }
    });
}

function main() {
    var soName = "libDexHelper.so";
    var package_name = "com.mobile.zgcbank";
    scanHiddenModules(soName, package_name);
}
setImmediate(main);
```

在内存中搜索匿名可执行模块成功dump目标 so

![image](https://bbs.kanxue.com/upload/attach/202607/968342_77FCZHSN422YDZP.png)

提取到 PC 并使用 [SoFixer](https://github.com/LunFengChen/SoFixer) 修复:

![image](https://bbs.kanxue.com/upload/attach/202607/968342_EKS47TC7K528M4S.png)

修复后的 dump 版so 如下,无 JNI_OnLoad 符号,需要人工判定

tip: 也可以使用 bindiff 和旧版 libDexHelper 对比, 恢复部分符号

![image](https://bbs.kanxue.com/upload/attach/202607/968342_YVZNX6NWAK2EH2T.png)

## unpack so

除了 dump 之外, 还可以使用脚本静态解密 apk的壳 so 以得到目标 so, 此处不做展开(后续水一篇一键脱壳).

unpack 版相比 dump 版, 保留了更多符号信息:

unpack 版,有 JNI_OnLoad 符号,可以看到地址为 0x13A8C

![image](https://bbs.kanxue.com/upload/attach/202607/968342_KTX6CGXQGKU2UWS.png)

后续分析基于 unpack 版, 但两版地址相同, 脚本通用

## 绕过线程检测函数

前文 dump 得到了被自定义 linker 加载的 so, 那么问题来了:

通过 maps 和 soinfo 只能定位壳 so, 无法定位真实 so, 所以 frida 的部分 API (如 Module.findModuleByAddress) 无法正常使用

解决方法: scanHiddenModule 扫描到目标 so 后, 可获取对应的base和range, 后续hook 需要基于 base+offset 的方式进行

hook clone 定位目标 so 创建的线程检测函数, 可注释非目标 so的 log 防止干扰

```js
var libName = "libDexHelper.so"
var appName = "com.mobile.zgcbank"

function hook_clone(base) {
    var clone = Module.findExportByName('libc.so', 'clone');
    Interceptor.attach(clone, {
        onEnter: function (args) {
            //只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了
            if (args[3] != 0) {
                var thread_func_addr = args[3].add(96).readPointer()        // 真正的用户线程函数地址
                var module = Process.findModuleByAddress(thread_func_addr); // 根据线程函数地址 addr，找它属于哪个模块
                if (module) {
                    var offset = (thread_func_addr - module.base);              // 获取相对于 base 的偏移
                    //console.log(`[+] clone thread func: ${module.name}+0x${offset.toString(16)}`); // 注释以关闭非目标 so 的 log
                } else {
                    var offset = thread_func_addr.sub(base);
                    console.log(`[+] clone thread func: ${libName}+0x${offset.toString(16)}`);
                }
            }
        }
    });
}

function hook_functions(base, range) {
    hook_clone(base);
}
function scanHiddenModules() {
    const knownModules = Process.enumerateModules().map(m => m.base.toString());
    var target_range;
    Process.enumerateRanges({
        protection: 'r-x',
        coalesce: true
    }).forEach(function (range) {
        try {
            const buf = range.base.readByteArray(4);
            if (!buf) return;
            const bytes = new Uint8Array(buf);
            // 验证 ELF 魔数
            if (bytes[0] === 0x7f && bytes[1] === 0x45 && bytes[2] === 0x4c && bytes[3] === 0x46) {
                const base = range.base;
                if (knownModules.indexOf(base.toString()) !== -1) return;
                console.log(`\n[!] Found Hidden Module: ${base}`);
                target_range = range;
            }
        } catch (e) {
            console.error(`Error while scanning range ${range.base}: ${e}`);
        }
    });
    return target_range;
}

function hook_dlopen(soName) {
    var once_flag = true;
    Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"),
        {
            onEnter: function (args) {
                var pathptr = args[0];
                if (pathptr !== undefined && pathptr != null) {
                    var path = ptr(pathptr).readCString();
                    //console.log("[+]dlopen: " + path);
                    if (path.indexOf(soName) >= 0) {
                        this.is_can_hook = true;
                    }
                }
            },
            onLeave: function (retval) {
                if (this.is_can_hook && once_flag) {
                    const range = scanHiddenModules();
                    hook_functions(range.base, range);
                    once_flag = false;
                }
            }
        }
    );
}
function main() {
    hook_dlopen(libName);
}
setImmediate(main);
```

结果如下, 输出了多个目标 so 创建的线程函数

![image](https://bbs.kanxue.com/upload/attach/202607/968342_XYKUVKE5XZHXD9H.png)

直接 patch 这些函数开头为 ret 指令

```js
//......
function patchThreadFunc(addr) {
    Memory.protect(addr, 4, 'rwx');  // 修改该地址的权限为可读可写
    var writer = new Arm64Writer(addr);
    writer.putRet();   // 直接将函数首条指令设置为ret指令
    writer.flush();    // 写入操作刷新到目标内存，使得写入的指令生效
    Memory.protect(addr, 4, 'r-x');  // 恢复该地址的权限为只读可执行
    writer.dispose();  // 释放 Arm64Writer 使用的资源
    console.log("[+] nop " + addr + " success");
}

function bypass_detect_funcs(base) {
    patchThreadFunc(base.add(0x2cb28));
    patchThreadFunc(base.add(0x43ed8));
    patchThreadFunc(base.add(0x3e018));
    patchThreadFunc(base.add(0x4bd70));
    patchThreadFunc(base.add(0x4c608));
    patchThreadFunc(base.add(0x574d8));
    patchThreadFunc(base.add(0x48088));
    patchThreadFunc(base.add(0x4aed8));
}

function hook_functions(base, range) {
    hook_clone(base);
    bypass_detect_funcs(base);
}
//......
```

patch成功, 但无法 bypass, 说明还有其他检测函数

![image](https://bbs.kanxue.com/upload/attach/202607/968342_FU69NM4FX5DZJ59.png)

## trace + 二分法定位检测点

(注意: 复现时使用 插件V1.2版本, log可能有所差别)

接下来可以使用 [glass-stalker-trace](https://github.com/OrientalGlass/glass-stalker-trace) trace 生成函数调用树以辅助分析

使用方法很简单, 将 `glass_stalker_trace_ida.py` 放入 ida的 plugins/目录下

依次点击 Edit > Plugins > Glass Stalker Trace: Export JS 即可导出 trace 脚本

![image](https://bbs.kanxue.com/upload/attach/202607/968342_DN8RYYR5YBDF5P3.png)

使用前需要调用 configureTrace 进行基本配置, 之后传入 base 和 range 调用 trace_start 即可开始 trace, 建议输出 log 到文件中方便查看

```sh
frida -Uf com.mobile.zgcbank -l bypass-zgcbank.js > log.txt
```

```js
//......
function hook_functions(base, range) {
    //hook_clone(base);
    bypass_detect_funcs(base);

    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x13A8C
        }
    });
    trace_start(base, range);
}
//......
```

trace log 如下, 再此简单介绍 trace 格式:

以节点 `[tree] |-- sub_29D78 (0x29d78) [from=0x2832c, bl, depth=2]` 为例:

- `[tree]` 函数调用树标签, 用于打印函数节点, 还有其他各类标签, 方便分类 log
- `sub_29D78` 函数名称, 若函数有符号或手动命名则有效, 否则默认 sub_xxx, 以 IDA 导出结果为准
- `(0x29d78)` 函数相对模块的偏移地址
- `[from=0x2832c, bl, depth=2]`

该节点 在 `base+0x2832c` 处被调用, 跳转指令为 `bl`, 节点深度为 2

![image](https://bbs.kanxue.com/upload/attach/202607/968342_B3BH4QUVP9P5D83.png)

trace 结果有 300+ 行, trace 目标函数退出前的 log 如下:

```python
[tree] |-- sub_A4868 (0xa4868) [from=0x15a40, bl, depth=1]
[tree]     |-- sub_A3C9C (0xa3c9c) [from=0xa48bc, b, tail, depth=1]
[tree]         |-- sub_A4484 (0xa4484) [from=0xa3d68, bl, depth=2]
[tree]         |-- sub_A4484 (0xa4484) [from=0xa3d70, bl, depth=2]
[tree]         |-- sub_A4484 (0xa4484) [from=0xa3d78, bl, depth=2]
[tree]         |-- sub_A4484 (0xa4484) [from=0xa3d80, bl, depth=2]
[tree]         |-- sub_C5D08 (0xc5d08) [from=0xa43f4, bl, depth=2]
[tree]         |-- sub_C5D08 (0xc5d08) [from=0xa444c, bl, depth=2]
[trace] root returned; ending owner session returnTarget=libart.so+0x4f6ed8 callerCallsite=libart.so+0x4f6ed4
```

直接跟进 0x15a40, 发现位于 JNI_OnLoad 尾部, 确实调用了 sub_A4868, 但该函数并非检测函数

![image](https://bbs.kanxue.com/upload/attach/202607/968342_TG5XJX7UZMPW9ZF.png)

所以当前的情况是: patch绕过了线程检测函数, trace 可以完整跑完 JNI_OnLoad, 但 app 仍然会检测到 frida 从而崩溃, 且 trace 不能直接定位到具体崩溃点位, 即没有明确的崩溃函数/指令.

那么我们可以猜测: trace 的函数调用链中, 有某个/某些函数检测到 frida, 但没有直接 kill 进程, 而是交由其他函数/子线程/子进程执行, 从而避免位于主线程的调用链导致被 trace.

定位这个检测点可以使用 **二分法** (设左右边界节点分别为 [left,right]):

- 根据 trace 结果, 选取合适的中间节点mid, hook 该节点并 sleep 一定时间
- 如果 sleep 没有完成便崩溃, 说明 [left,mid] 即中间节点前方有检测函数
- 如果 sleep 完成后才崩溃, 说明 [mid,right] 即中间节点后方有检测函数

如何选取合适节点? 目标节点尽量满足居中, 唯一, 防止同地址函数在不同节点的调用干扰分析.

另外每次二分 trace 时, 需要保留对应节点的 trace 结果, 和原始 trace 结果对比

以 174 行的节点 64ED8 为例 (该节点选取并不理想, 仅模拟直接分析踩坑情况, 前方 69 行也有该函数调用节点)

![image](https://bbs.kanxue.com/upload/attach/202607/968342_UFKP6S6NYKYF96T.png)

代码如下, 注意 sleep 时间不能太久, 防止系统 kill app, 5-10s 比较合适

```js
function sleep_test(base, offset) {
    Interceptor.attach(base.add(offset), {
        onEnter: function (args) {
            this.lr = this.context.lr;
        },
        onLeave: function (retval) {
            console.log(`[+] ${libName}+0x${offset.toString(16)} retval: ${retval} lr: ${this.lr.sub(base)}`);
            const startedAt = Date.now();
            console.log(`[sleep] begin tid=${Process.getCurrentThreadId()}`);
            Thread.sleep(10);
            console.log(`[sleep] end elapsed=${Date.now() - startedAt}ms`);
        }
    })
}
function hook_functions(base, range) {
    sleep_test(base, 0x67ED8)
    //hook_clone(base);
    bypass_detect_funcs(base);

    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x13A8C
        }
    });
    trace_start(base, range);
}
```

Trace 结果如下, 可以看到在 69 行的 67ED8 函数命中了 hook, 并且完成了一次完整 sleep

后续又命中一次, 且启动 sleep 便崩溃, 说明检测点位于 69 行之后

![image](https://bbs.kanxue.com/upload/attach/202607/968342_434AV5PUA2UANUZ.png)

下一个节点选取194 行的 17534, 该节点只有一次调用, 且内部调用函数较多, 比较可疑

![image](https://bbs.kanxue.com/upload/attach/202607/968342_RP5HPTSZKMVVTR4.png)

注意此时应该注释前一个节点的 sleep

```js
function hook_functions(base, range) {
    //sleep_test(base, 0x67ED8)
    sleep_test(base,0x17534)
      //......
}
```

trace 结果如下, 完整sleep 一次, 说明检测点在 sub_17534 之后

同时可以发现 sleep end 后有一次 fork 调用, 可以猜测是 fork 的子进程进行了检测, 并 kill 了父进程

![image](https://bbs.kanxue.com/upload/attach/202607/968342_M77C2TGKNHP36F7.png)

下一个节点选取 229行的 1AB90

![image](https://bbs.kanxue.com/upload/attach/202607/968342_G5XPXQ9F9QFFHGV.png)

此次有变化,多输出了几次 1AB90 调用, 但实际触发 hook 和 sleep 的位于末尾

说明检测点位于sub_17534~sub_1AB90

并且可以发现在 fork 调用后, 创建了几个线程, 之后命中 hook, app 崩溃

![image](https://bbs.kanxue.com/upload/attach/202607/968342_5VFCVU2WCGJVYE8.png)

之后的二分 trace 是重复试验过程, 不再赘述, 明确指出检测点为 sub_2813C, 且不是 JNI_OnLoad 开头调用的那一个, 而是在 418 行, if 内 fork 的分支.

![image](https://bbs.kanxue.com/upload/attach/202607/968342_C84W8PTDYMV873K.png)

目测该函数的功能为扫描 cmdline 判断当前是否处于被调试状态
hook 该函数, 观察返回值可以发现:

- return 0 必定触发 if 分支内的 fork
- return 1 app 崩溃
- return 2 app 可运行
- return 3 其他点位调用该函数的正常返回值

所以 hook 后 replace retval = 3 即可绕过

```js
function bypass_detect_funcs(base) {
    Interceptor.attach(base.add(0x2813C), {
        onEnter(args){
            console.log("[patch] sub_2813C called")
        },
        onLeave(retval) {
            console.log(`[patch] sub_2813C retval ${retval} -> 3`);
            retval.replace(3);
        }
    });
    patchThreadFunc(base.add(0x2cb28));
    patchThreadFunc(base.add(0x43ed8));
    patchThreadFunc(base.add(0x3e018));
    patchThreadFunc(base.add(0x4bd70));
    patchThreadFunc(base.add(0x4c608));
    patchThreadFunc(base.add(0x574d8));
    patchThreadFunc(base.add(0x48088));
    patchThreadFunc(base.add(0x4aed8));
}
```

成功绕过, 并且 trace 的目标函数JNI_OnLoad 完整结束

![image](https://bbs.kanxue.com/upload/attach/202607/968342_DT4SBDRZJUBBAW6.png)

值得一提的是 trace 末尾的 2813C 并非检测点, 该函数共有 3 次调用, 其中第二次为检测点

![image](https://bbs.kanxue.com/upload/attach/202607/968342_ZY4CA2EYYQ6BRSK.png)

对应的点位, 紧跟 sub_17534, 返回值为 0 时触发 fork 子进程并创建检测线程

bypass 后, if 分支外主进程继续执行其他函数, 所以 bypass 前后对应的 trace 结果会有不同

![image](https://bbs.kanxue.com/upload/attach/202607/968342_9QR5828CH3Z5EUY.png)

# V4-fengshou

同上类似, 可以 hook dlopen, 扫描匿名可执行模块 dump 目标 so, 也可以静态脚本脱壳

## 绕过线程检测函数

hook clone定位检测线程函数

```js
var libName = "libDexHelper.so"
var appName = "com.yitong.zjrc.mfs.android"

function hook_clone(base) {
    var clone = Module.findExportByName('libc.so', 'clone');
    Interceptor.attach(clone, {
        onEnter: function (args) {
            //只有当 args[3] 不为 NULL 时，才说明上层确实把 “线程控制块指针” 传进来了
            if (args[3] != 0) {
                var thread_func_addr = args[3].add(96).readPointer()        // 真正的用户线程函数地址
                var module = Process.findModuleByAddress(thread_func_addr); // 根据线程函数地址 addr，找它属于哪个模块
                if (module) {
                    var offset = (thread_func_addr - module.base);              // 获取相对于 base 的偏移
                    //console.log(`[+] clone thread func: ${module.name}+0x${offset.toString(16)}`); // 注释以关闭非目标 so 的 log
                } else {
                    var offset = thread_func_addr.sub(base);
                    console.log(`[+] clone thread func: ${libName}+0x${offset.toString(16)}`);
                }
            }
        }
    });
}

function hook_functions(base, range) {
    hook_clone(base);
}
function scanHiddenModules() {
    const knownModules = Process.enumerateModules().map(m => m.base.toString());
    var target_range;
    Process.enumerateRanges({
        protection: 'r-x',
        coalesce: true
    }).forEach(function (range) {
        try {
            const buf = range.base.readByteArray(4);
            if (!buf) return;
            const bytes = new Uint8Array(buf);
            // 验证 ELF 魔数
            if (bytes[0] === 0x7f && bytes[1] === 0x45 && bytes[2] === 0x4c && bytes[3] === 0x46) {
                const base = range.base;
                if (knownModules.indexOf(base.toString()) !== -1) return;
                console.log(`\n[!] Found Hidden Module: ${base}`);
                target_range = range;
            }
        } catch (e) {
            console.error(`Error while scanning range ${range.base}: ${e}`);
        }
    });
    return target_range;
}

function hook_dlopen(soName) {
    var once_flag = true;
    Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"),
        {
            onEnter: function (args) {
                var pathptr = args[0];
                if (pathptr !== undefined && pathptr != null) {
                    var path = ptr(pathptr).readCString();
                    //console.log("[+]dlopen: " + path);
                    if (path.indexOf(soName) >= 0) {
                        this.is_can_hook = true;
                    }
                }
            },
            onLeave: function (retval) {
                if (this.is_can_hook && once_flag) {
                    const range = scanHiddenModules();
                    hook_functions(range.base, range);
                    once_flag = false;
                }
            }
        }
    );
}
function main() {
    hook_dlopen(libName);
}
setImmediate(main);
```

结果如下

![image](https://bbs.kanxue.com/upload/attach/202607/968342_6WGQ6VGQSSJ8X5F.png)

patch这 7 个线程函数后再次启动, 会出现第 8 个

![image](https://bbs.kanxue.com/upload/attach/202607/968342_JWF5R3JC8YPHMWW.png)

所以共有 8 个检测函数

```js
function bypass_detect_funcs(base) {
    patchThreadFunc(base.add(0x302b0));
    patchThreadFunc(base.add(0x348a4));
    patchThreadFunc(base.add(0x5171c));
    patchThreadFunc(base.add(0x4741c));
    patchThreadFunc(base.add(0x5e588));
    patchThreadFunc(base.add(0x60a88));
    patchThreadFunc(base.add(0x61b3c));
    patchThreadFunc(base.add(0x6dc04));
}
function hook_functions(base, range) {
    hook_clone(base);
    bypass_detect_funcs(base);
}
```

## trace 定位检测点

同V3类似, 此处不再赘述重复 trace + 二分法定位, 实际上有了 V3 版本的结论, 可以通过特征码直接定位

对于该样本, 对应的目标函数为 sub_2DF48

```js
function bypass_detect_funcs(base) {
    Interceptor.attach(base.add(0x2DF48), {
        onLeave: function (retval) {
            console.log(`[+] sub_2DF48 called! original: ${retval}, returning 3`);
            retval.replace(3);
        }
    });

    patchThreadFunc(base.add(0x302b0));
    patchThreadFunc(base.add(0x348a4));
    patchThreadFunc(base.add(0x5171c));
    patchThreadFunc(base.add(0x4741c));
    patchThreadFunc(base.add(0x5e588));
    patchThreadFunc(base.add(0x60a88));
    patchThreadFunc(base.add(0x61b3c));
    patchThreadFunc(base.add(0x6dc04));
}
function hook_functions(base, range) {
    hook_clone(base);
    bypass_detect_funcs(base);
}
```

结果如下: 成功 bypass sub_2DF48, 创建的线程函数有变化, 但app仍然崩溃, 说明有其他检测点

![image](https://bbs.kanxue.com/upload/attach/202607/968342_NZETED3JZN7BABV.png)

使用前文提到的 trace 插件, 启动 ida 导出脚本, 配置基本信息后开始 trace

```js
function hook_functions(base, range) {
    //hook_clone(base);
    bypass_detect_funcs(base);
    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x14884
        }

    })
    trace_start(base, range);
}
```

结果如下, trace 结果提示由于持续时间限制(10s) 导致 root leave, 即 trace 终止

![image](https://bbs.kanxue.com/upload/attach/202607/968342_GSKYUPDZDMZJC76.png)

说明默认的 10s 不够用,可以适当增大

```js
function hook_functions(base, range) {
    hook_clone(base);
    bypass_detect_funcs(base);
    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x14884
        },
        options: {
            maxDurationMs:30000,
        }
    })
    trace_start(base, range);
}
```

此次 trace 出现 Process terminated, 没有 root leave, 说明被检测函数检测提前终止

且由于热点函数, 以 sub_80100和 sub_7C4F0为主, 命中次数太多, 引发trace 引擎性能限制

虽然工具自动进行部分限制, 但仍然不足

![image](https://bbs.kanxue.com/upload/attach/202607/968342_XMQ4W9XU64G3DNR.png)

为热路径限制手动指定函数

```js
function hook_functions(base, range) {
    hook_clone(base);
    bypass_detect_funcs(base);
    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x14884
        },
        options: {
            maxDurationMs:30000,
            hotPathSuppress: {
                functions: [0x80100,0x7C4F0]
            }
        }
    })
    trace_start(base, range);
}
```

trace 得到的最后一个 depth=1的节点是 sub_1E33C, 该函数非常庞大

![image](https://bbs.kanxue.com/upload/attach/202607/968342_9Z3B94Y5QQH4Z2A.png)

比较有意思的是 sub_6A5A8, 调用树非常大, 实际上该函数就是目标检测函数

![image](https://bbs.kanxue.com/upload/attach/202607/968342_S36TQ5SA2SAG8GB.png)

trace 末尾显示触发非法内存地址访问而崩溃, 说明成功 trace 到崩溃前的函数调用关系树

![image](https://bbs.kanxue.com/upload/attach/202607/968342_GXJA4JT365GTJKS.png)

可以选取 trace 崩溃前的一个函数,开启指令级 trace:

```js
function hook_functions(base, range) {
    //hook_clone(base);
    //sleep_test(base,0x47798);
    //sleep_test(base, 0x6B374);
    bypass_detect_funcs(base);
    configureTrace({
        moduleName: libName,
        root: {
            name: 'JNI_OnLoad',
            offset: 0x14884
        },
        options: {
            maxDurationMs: 30000,
            hotPathSuppress: {
                functions: [0x80100, 0x7C4F0]
            }
            ,
            detailTrace: {
                enabled: true,
                startOffset: 0x10380,
                packageName:appName,
                untilProcessExit:true
            }
        }
    })
    trace_start(base, range);
}
```

log 位于`/data/data/<package-name>/files/`内, 对应 trace 结果如下

tail 命令查看最后一段指令, 最后 blr x20 , 调用点为 0x10674

![image](https://bbs.kanxue.com/upload/attach/202607/968342_78FBQRB32WD2777.png)

ida 分析可以发现, 该函数为

```python
_ZN3art13DexFileLoader10OpenCommonEPKhmS2_mRKNSt3__112basic_stringIcNS3_11char_traitsIcEENS3_9allocatorIcEEEEjPKNS_10OatDexFileEbbPS9_NS3_10unique_ptrINS_16DexFileContainerENS3_14default_deleteISH_EEEEPNS0_12VerifyResultE
```

实际上是 `art::DexFileLoader::OpenCommon`的一个重载, 这是壳在解密释放真实 DEX

![image](https://bbs.kanxue.com/upload/attach/202607/968342_Y9RKGZUCX5C7V4C.png)

所以可以推断: 最新的检测点并非检测到frida后主动杀掉进程, 而是检测到后故意不解密 DEX, 或者埋坑

当触发原有的正常逻辑时, 系统相关 API 正常调用发现缺失关键数据, 从而触发异常/非法内存访问等引发崩溃

分析到此处有一些运气成分: 该插件的 V1.0版本会折叠节点, 导致误打误撞快速定位到了 sub_6A5A8

![image](https://bbs.kanxue.com/upload/attach/202607/968342_VYNKCR8D2QUFME4.png)

位于 1E33C 的 3150 行

- 检测结果为 0 时, 进入 if 分支,创建检测线程 6AB94, 进行 DEX解密释放
- 检测结果为 1 时, 不进入 if, 导致 DEX 无法正常解密释放
- 最后无论是否进入 if, 都会进入装载和调用 DEX 的代码逻辑, 若DEX 状态不正常则触发崩溃

![image](https://bbs.kanxue.com/upload/attach/202607/968342_UT9TS5KDYADTXF7.png)

其创建检测线程代码如下, 循环调用 6A5A8 检测, 如果返回值==0 则正常,继续循环; 否则退出循环触发 jumpout

![image](https://bbs.kanxue.com/upload/attach/202607/968342_TKWY7AXHAYZ59QY.png)

所以绕过该函数需要做两件事:

1. hook 6A5A8 返回值为 0, 强制进入 if 分支, 保证 DEX 可以正常释放
2. patch 6AB94, 防止检测线程工作

```js
function bypass_detect_funcs(base) {
    Interceptor.attach(base.add(0x2DF48), {
        onLeave: function (retval) {
            console.log(`[+] sub_2DF48 called! original: ${retval}, returning 3`);
            retval.replace(3);
        }
    });

    Interceptor.attach(base.add(0x6A5A8), {
        onLeave: function (retval) {
            retval.replace(0); //replace 0 for bypass
        }
    });
    patchThreadFunc(base.add(0x302b0));
    patchThreadFunc(base.add(0x348a4));
    patchThreadFunc(base.add(0x5171c));
    patchThreadFunc(base.add(0x4741c));
    patchThreadFunc(base.add(0x5e588));
    patchThreadFunc(base.add(0x60a88));
    patchThreadFunc(base.add(0x61b3c));
    patchThreadFunc(base.add(0x6dc04));
    patchThreadFunc(base.add(0x6ab94));
}
```

效果如下, 成功 bypass (可能会弹窗提示存在 ROOT 风险, 确认即可, 不会 kill app)

![image](https://bbs.kanxue.com/upload/attach/202607/968342_5V25GTK72N6G7QR.png)

# 总结

近期摆烂了一段时间, 本篇文章作为复健, 原本想放到星球, 想想还是算了, 个人感觉干货不多, 过检测也没什么好藏着的, 需要持续攻防对抗, 就当做一份小礼物吧

最后, 欢迎师傅们进群交流:

![image](https://bbs.kanxue.com/upload/attach/202607/968342_YMYFK8D78WCX7N8.png)
如果觉得文章有帮助也欢迎师傅们提前入股星球, 后续发一些学习总结和实战案例:

![37-zsxq](https://bbs.kanxue.com/upload/attach/202607/968342_MD2ZUF2Z7Y6QQ4H.png)
# References

[新版梆企检测绕过](https://bbs.kanxue.com/thread-290874.htm#msg_header_h3_2)

[新版某企业壳加固自定义linker与frida检测分析](https://bbs.kanxue.com/thread-291074.htm)

[某企业壳逆向分析——从过检测到dex代码抽取还原](https://bbs.kanxue.com/thread-291069.htm)

[stalker_trace_so](https://github.com/oacia/stalker_trace_so)

[stalkercpp_xiaojia](https://github.com/yizhiyonggangdexiaojia/stalkercpp_xiaojia)

---

# 回复

## 回复 by x1a0f3n9 (#2)

认真学习![image](https://bbs.kanxue.com/view/img/face/005.gif)

## 回复 by Zepp7289 (#3)

tql

## 回复 by console_ (#4)

严肃学习

## 回复 by Cure. (#5)

狠狠地学习![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by MsScotch (#6)

支持学习

## 回复 by aut0run (#7)

认真学习

## 回复 by mb_ldbucrik (#8)

感谢分享

## 回复 by mb_nkjfyhkg (#9)

mark

## 回复 by ldehua (#10)

有点意思

## 回复 by 花宝叽果赖 (#11)

666

## 回复 by wx_coddvccwyh (#12)

6666

## 回复 by 啊你好哇123 (#13)

学习

## 回复 by mb_ysegxpmv (#14)

tql

## 回复 by mb_cbgtaveo (#15)

666666

## 回复 by wx_Huber Barrientos (#16)

666

## 回复 by BlackMaGou (#17)

认真学习

## 回复 by iBa0 (#18)

66

## 回复 by xwtwho (#19)

66

## 回复 by 摸鱼学安卓 (#20)

严肃学习

## 回复 by MaYil (#21)

感谢分享

## 回复 by 寻梦之璐 (#22)

666

## 回复 by mb_jhohnbzu (#23)

666

## 回复 by cpannn (#24)

牛牛

## 回复 by mb_xnfozane (#25)

666

## 回复 by upcj (#26)

666

## 回复 by 逆向小龙 (#27)

学习

## 回复 by lizhenzhe (#28)

666

## 回复 by mb_akzdpbgl (#29)

感谢分享

## 回复 by mb_llrpqrtc (#30)

感谢分享

## 回复 by 中文fjja (#31)

感谢分享

## 回复 by 巡夜人 (#32)

感谢分享

## 回复 by kudos5566 (#33)

6

## 回复 by mb_ykavguun (#34)

666

## 回复 by mb_eizetlni (#35)

666

## 回复 by xtyuns (#36)

学习一下

## 回复 by mb_rztmbvgb (#37)

666

## 回复 by didiid (#38)

666

## 回复 by v5w7crq3 (#39)

666

## 回复 by lrhtony (#40)

66

## 回复 by 带壳的蜗牛 (#41)

6666

## 回复 by 我不是QI (#42)

777

## 回复 by mb_euhyowpw (#43)

666

## 回复 by mb_xaxjwwvm (#44)

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by kingking888 (#45)

666

## 回复 by scllqk (#46)

学习

## 回复 by mb_syvaqetv (#47)

学习了
