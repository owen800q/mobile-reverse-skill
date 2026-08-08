---
title: '[原创]Frida企业级加固对抗实战: 通过 mmap/mprotect 钓出壳隐藏的真实 SO'
url: https://bbs.kanxue.com/thread-290647.htm
tid: 290647
author: reserve_zhou
date: '2026-04-04'
tags: [Android安全, 原创, 逆向分析, 混淆加固, HOOK注入]
crawled_at: '2026-08-08T10:13:56+00:00'
replies: 149
---

# 前言

今天在对某企业级 Android 加固方案进行逆向分析时，我通过 Frida 注入开展动态调试，过程中发现了一个明显违背 ELF 标准的反常现象：通过 dlopen 遍历已加载 SO 时，打印某 SO 的基地址与 JNI_OnLoad 函数地址后，我发现该 JNI_OnLoad 地址完全不属于该 SO 的内存区间，甚至出现了函数地址 < 模块基址的反常现象，严重违背 ELF/Linker 标准的内存布局规则。

深入排查后最终定位到根因：该加固壳劫持了系统 linker64 链接器、Hook 了 dlopen 系列函数，通过伪造虚假的 SO 信息（向 Frida 等调试工具暴露一个看似正常的 “壳 SO”），将真正的业务 SO 隐藏在内存中、绕开系统 linker 私自加载，以此实现反调试、反逆向的防护效果。

本文将详细拆解这类企业级加固的对抗思路，从底层原理、脚本编写、动态调试到脱壳还原，手把手教大家如何通过 Frida 从内存中精准 “钓” 出被壳隐藏的真实业务 SO，完成脱壳还原。全程实操为主、原理为辅，文中所有脚本均已脱敏处理，可直接复用。

水平有限，文中若有疏漏或错误，恳请各位大佬斧正。

本文用到的工具和前置知识：

1.mmap的分配原理和mmproct函数的权限修正:     东方玻璃大佬的底层知识讲解一直十分之详细，大家可以参考[[原创]Android从ELF-Loader到自定义Linker的实现及原理-Android安全-看雪安全社区｜专业技术交流与安全研究论坛](https://bbs.kanxue.com/thread-290643.htm)

2.Frida stalker ：Frida 是本次动态调试、Hook 系统函数的核心工具，需要大家熟悉 Frida 的基本注入命令、Interceptor 钩子用法、Module 相关 API；Frida Stalker 是 Frida 内置的高性能指令级追踪引擎，也是本次验证脱壳正确性的关键工具，需要了解其基本的追踪配置、指令捕获逻辑。

3.ELF 文件结构基础：需要了解 SO 文件的基本结构，包括导出表、代码段（text）、数据段（data）、soinfo 结构体的基本作用，明白符号表查询的基本流程，这样才能理解“导出表异常“地址倒挂”等反常现象的本质。

哈哈   发现本文用到的知识点上面东方玻璃的大佬刚刚发的的帖子都有讲到，大家可以看看

# 案例演示

## 正常注入

获取一款企业级加固安卓 APP 后，我通过 Frida 对进程进行注入，Hook 系统`dlopen`函数枚举加载的 SO 模块，成功定位到目标加固 SO。该 SO 采用典型的企业级加固方案，也是很经典的，加载完一个so就被杀进程了

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_GVQUKRVUGCMX8RN.webp)

进程崩溃后，首要任务是定位崩溃的核心位置。熟悉 Android SO 加载流程的朋友都知道，JNI_OnLoad 是 Android SO 库被系统加载时自动执行的第一个核心入口函数，也是企业级加固放置反调试、完整性校验、进程强杀等防护逻辑的关键位置，属于逆向分析中必查的核心节点。

因此，我优先针对 JNI_OnLoad 函数的执行流程进行排查，核心思路是：通过 Frida 挂钩 JNI_OnLoad 的 onEnter（函数进入）和 onLeave（函数退出）两个关键时机，并打印日志，以此验证进程能否完整执行完 JNI_OnLoad 函数、顺利走到 onLeave 阶段，从而快速判定崩溃是否发生在 JNI_OnLoad 函数内部。

排查jni函数脚本：

\```
const so_name = "xxxxxxx.so";
var flag = false;
Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"), {
    onEnter: function (args) {
        // args[0] = android_dlopen_ext第一个参数 → SO文件完整路径的C字符串指针

        if (args[0].readCString().indexOf(so_name) != -1) {

            flag = true;
        }

    },
    onLeave: function (args) {
        if (flag) {
            console.log("成功加载SO文件");
            console.log("准备Hook JNI_OnLoad函数 地址 " + so_name + " 的JNI_OnLoad函数");
            const module = Process.findModuleByName(so_name);
            if (!module) {
                console.error("[-] 未找到模块: " + so_name);
                return;
            }
            const jniAddr = module.findExportByName("JNI_OnLoad");
            if (!jniAddr) {
                console.error("[-] 未找到JNI_OnLoad函数");
                return;
            }

            console.log("[+] JNI_OnLoad函数地址: " + jniAddr);
            console.log("偏移 地址: " + module.base.sub(jniAddr));
            Interceptor.attach(Module.findExportByName(so_name, "JNI_OnLoad"), {
                onEnter: function () {
                    console.log("成功开始");
                },
                onLeave: function () {
                    console.log("成功结束")
                }
            })

        }

    }
});
console.log("监控启动！操作APP看SO加载路径～");
\```

注入结果：

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_CQ9VTBUQ2FF5PP8.webp)

将上述脚本通过 Frida 注入 APP 进程（注入命令：frida -U -f 包名 -l 脚本名.js --no-pause），操作 APP 触发目标 SO 加载，观察日志输出：

从日志中可以清晰看到：脚本成功检测到目标 SO 加载，成功找到 JNI_OnLoad 函数地址，并打印“成功开始”，但始终没有打印“成功结束”。

这个现象直接印证了我的预判：进程并未成功执行完 JNI_OnLoad 函数并正常退出，崩溃发生在 JNI_OnLoad 函数内部。

因此，下一步的排查思路已十分清晰：提取 JNI_OnLoad 函数地址，dump 出完整的加固 SO 文件，通过 IDA 分析 SO 结构，再结合 Frida Stalker 追踪 JNI_OnLoad 的指令执行流，逐行分析执行流程，最终精准定位进程崩溃的“死亡点”（即加固的反调试触发点）。

想要通过 IDA 分析 SO，首先需要将内存中的 SO 文件 dump 到本地。这里的关键是选择合适的 Dump 时机——时机选择不当，可能会导致 dump 出的 SO 不完整、未解密，无法正常分析。

本次采用的 Dump 方案是：在 dlopen 的 onLeave 回调时机，筛选内存中加载的目标 SO 并直接 dump。选择这个时机的核心原因有 3 点：

1. 此时 SO 文件已完成内存解密：系统加载 SO 时，会先将 SO 文件读取到内存，完成解密（若有加密），再执行后续的初始化操作，onLeave 时机刚好处于解密完成后、初始化未完全结束前；
2. .init_array 段的代码已全部执行完毕：.init_array 是 SO 加载时优先执行的初始化段，很多加固会在该段植入反调试逻辑，若进程崩溃发生在 .init_array 段，dump 出的 SO 可能不完整；而本次进程崩溃发生在 JNI_OnLoad 阶段，说明 .init_array 中并未植入强杀检测逻辑；
3. SO 内存布局完整：此时 SO 的代码段、数据段已全部映射到内存，dump 出的 SO 文件完整性最高，能最大程度保留 SO 的原始结构。

dump脚本：

\```
var TARGET_LIBRARY = "xxxxxxx";

function dumpSo() {
    var module = Process.getModuleByName(TARGET_LIBRARY);
    if (!module) {
        console.error("[-] 未找到模块: " + TARGET_LIBRARY);
        return;
    }

    var baseAddress = module.base;
    var moduleSize = module.size;
    console.log("[+] 目标模块: " + module.name);
    console.log("[+] 内存基址: " + baseAddress);
    console.log("[+] 模块大小: " + moduleSize + " 字节 (" + ptr(moduleSize) + ")");

    var packageName = "com.foundersc.app.xf";
    var filePath = "/data/data/" + packageName + "/" + module.name + "_" + baseAddress + "02.so";
    console.log("[+] 文件保存路径: " + filePath);

    var file = new File(filePath, "wb");
    if (!file) {
        console.error("[-] 创建文件失败，请检查路径权限");
        return;
    }

    Memory.protect(baseAddress, moduleSize, 'rwx');

    var soBuffer = baseAddress.readByteArray(moduleSize);
    if (!soBuffer) {
        console.error("[-] 读取内存失败");
        file.close();
        return;
    }

    file.write(soBuffer);
    file.flush();
    file.close();
    console.log(" SO 文件 dump 成功！");
    console.log("请使用 adb pull 命令将文件导出到电脑。");
}
\```

执行结果:

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_2F8BQMSJRKF33X4.webp)

## 意识到事情的不对劲

修复后用 IDA 打开，发现该 SO 导出表仅有一个 start 函数，完全没有 JNI_OnLoad。这与我之前 Frida 能正常 Hook 到 JNI_OnLoad 的现象完全矛盾，也让我意识到：我拿到的地址根本不属于这个 SO。

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_WNU33PWMW6GPUNR.webp)

此时我立刻产生了一个猜想：难道是壳在执行完 JNI_OnLoad 函数后，对加固的 SO 进行了动态篡改，删除了导出表中的 JNI_OnLoad 信息，导致我 dump 出的 SO 没有该函数？

为了验证这个猜想，我立刻调整了 Dump 时机，将 Dump 操作放在 JNI_OnLoad 的 onEnter 阶段——也就是函数刚准备执行、还未进行任何操作时，就对 SO 进行内存 Dump。修改后的脚本核心逻辑的是：在 Hook JNI_OnLoad 的 onEnter 回调中，调用 dumpSo 函数，确保在函数执行前完成 Dump。

重新执行脚本、导出 SO 文件，再次用 IDA 打开后，结果和之前完全一致：导出表依旧只有一个 start 函数，没有 JNI_OnLoad。

这就排除了“壳动态篡改导出表”的猜想，也让我更加确定：问题出在 Frida 获取函数地址的底层流程上，壳一定篡改了符号查找的逻辑，导致 Frida 拿到了虚假的函数地址。

为了弄清楚壳到底是如何篡改符号查找逻辑的，这里给大家详细拆解 Frida 获取函数地址的底层细节，也为后面分析壳的篡改手法做足铺垫——我刚才脚本中获取 JNI_OnLoad 地址的方式，看似只有两行代码，背后却涉及系统 linker、soinfo 结构体、dlsym 函数的完整交互流程，具体拆解如下：

我脚本中核心的两行代码，负责获取 JNI_OnLoad 的内存地址，也是逆向分析中最常用的符号查找方式：

\```
// 第一步：根据 SO 文件名，定位目标模块，获取模块核心信息
const module = Process.findModuleByName(so_name);
// 第二步：根据函数名，在目标模块中查找 JNI_OnLoad 的内存地址
const jniAddr = module.findExportByName("JNI_OnLoad");
\```

这两行代码的底层执行流程，并非 Frida 自身实现，而是完全依赖 Linux/Android 系统的动态链接机制，具体可以分为 4 个步骤，每一步都至关重要，也是壳篡改的核心靶点：

### 步骤 1：Process.findModuleByName(so_name) —— 定位模块

这行代码的核心作用，是遍历当前进程内核态维护的“已加载模块链表”（该链表由系统 linker 维护，记录了所有已加载到进程内存中的动态库信息），根据传入的 SO 文件名（so_name），匹配到目标 SO 模块，并返回一个包含该模块所有核心信息的对象。

返回的 module 对象中，最关键的两个信息是：

            module.base：目标 SO 的内存基址，即 SO 被映射到进程虚拟内存中的起始地址，所有函数、数据的地址都基于该基址偏移；

            module.handle：目标 SO 的模块句柄（本质是一个指针），这个句柄是后续查找函数地址的“钥匙”，用于定位系统 linker 维护的 soinfo 结构体。

简单来说，这一步相当于“找到目标 SO 在系统中的位置，并拿到它的id”，为后续查找函数地址做好准备。

### 步骤 2：module.findExportByName("JNI_OnLoad") —— 调用系统 dlsym 函数，发起符号查询

这是最核心的一步，也是壳篡改的主要环节。很多朋友误以为这是 Frida 自身的函数查找逻辑，其实不然——该方法底层会直接调用 Android 系统的 dlsym 函数（定义在 libdl.so 中，是 Linux/Android 标准的动态符号查找函数），并传入两个核心参数：

1. 第一个参数：目标 SO 的 handle 句柄（即步骤 1 中获取的 module.handle）；
2. 第二个参数：需要查找的符号名（这里是 "JNI_OnLoad"）。

dlsym 函数的作用，就是根据传入的 handle 句柄，找到对应的符号（函数名、变量名），并返回该符号在进程内存中的绝对地址。

### 步骤 3：通过 handle 句柄，定位 soinfo 结构体

dlsym 函数收到 handle 句柄后，会通过该句柄，找到系统 linker 为每一个加载的 SO 所维护的 soinfo 结构体——这个结构体是 SO 加载到内存后的“身份档案”，记录了 SO 的所有运行时信息，包括：

1.SO 的内存基址、模块大小；

2.SO 的运行时符号表（与 SO 文件中的静态导出表不同，运行时符号表是 SO 加载到内存后，由 linker 解析生成的，用于动态查找符号）；

3.SO 的代码段、数据段地址范围；

4. 其他与 SO 运行相关的核心信息。

这里有一个关键知识点，也是我之前容易混淆的地方，重点强调：soinfo 是系统 linker 维护的运行时结构体，壳无法篡改或销毁系统内部的真实 soinfo——因为一旦篡改或销毁，会导致 linker 无法正常管理该 SO，进而引发进程崩溃，这是壳无法规避的内核级限制。但壳可以通过 Hook dlsym 函数，篡改传入的 handle 句柄，或者伪造 dlsym 的返回地址，让上层工具（如 Frida）以为地址来自当前模块，实际上却指向内存中另一块隐藏区域。

### 步骤 4：查询运行时符号表，返回函数地址

找到 soinfo 结构体后，dlsym 函数会遍历该结构体中的运行时符号表，根据传入的符号名（"JNI_OnLoad"），匹配到对应的函数条目，进而获取该函数在进程内存中的绝对地址，并将该地址返回给 Frida，最终赋值给 jniAddr 变量。

 重点提醒：这个流程完全不依赖 SO 文件的静态导出表！

也就是说，无论 SO 文件的静态导出表（即我们用 IDA 看到的导出表）是否被篡改、删除、加密，只要 soinfo 结构体正常、dlsym 函数未被劫持，Frida 就能通过这个流程，找到 JNI_OnLoad 的真实地址——这也是为什么很多加固会删除静态导出表，但依然能被 Frida  Hook 到函数的原因。

上面拆解的，是系统未被篡改时的标准正常流程。但结合我们之前的异常现象（dump 出的 SO 没有 JNI_OnLoad 导出，却能通过 Frida 找到该函数地址），我意识到：壳一定篡改了这个流程。

为了验证这个猜想，我做了一个关键操作：打印 JNI_OnLoad 函数的地址和目标 SO 的模块基址，将两个地址进行比对，结果惊讶地发现了一个极度反常的现象：返回的 JNI_OnLoad 地址 < SO 模块基址。

这里给大家补充一个底层内存布局规则，帮大家理解这个现象的反常性：

正常情况下，SO 被加载到进程内存后，其内存布局遵循“基址 + 偏移”的规则——SO 的代码段（text）、数据段（data）等所有内容，都会被映射到模块基址之后的内存区间，因此，SO 中所有函数的地址，都必然落在 [模块基址, 模块基址 + 模块大小) 的合法区间内，且函数地址一定大于模块基址（因为函数位于代码段，代码段在基址之后）。

而我们发现的“JNI_OnLoad 地址 < 模块基址”，意味着该地址完全不属于当前 SO 模块，这是典型的地址伪造，也直接坐实了壳对底层函数查找机制和内存映射的恶意篡改。

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_W2FE8ME5UHPXERD.webp)

结合前面的分析，我高度怀疑：壳通过劫持系统底层的 dlsym 函数，篡改了传入的 handle 句柄，或者直接伪造了函数地址，导致 Frida 拿到的 JNI_OnLoad 地址是虚假的，并非来自 dump 出的“壳 SO”，而是来自内存中隐藏的真实业务 SO。

为了实锤这个猜想，我编写了 Frida 脚本，Hook 系统的 dlsym 函数，打印每次调用的 handle 句柄、查询的符号名，以及 dlsym 返回的函数地址，重点监控与 JNI_OnLoad 相关的调用，以此捕获壳的篡改证据。

注入脚本:

\```
function hook_dlsym() {
    const dlsym_addr = Module.findExportByName("libdl.so", "dlsym");
    if (!dlsym_addr) {
        console.error("[-] 未找到 dlsym");
        return;
    }

    Interceptor.attach(dlsym_addr, {
        onEnter: function (args) {
            // dlsym 参数：void *handle, const char *symbol
            this.handle = args[0];
            this.symbol = args[1].readCString();

            console.log("========================================");
            console.log("[dlsym] 调用");
            console.log("[dlsym] handle: " + this.handle);
            console.log("[dlsym] symbol: " + this.symbol);
        },
        onLeave: function (retval) {
            const func_addr = retval;

            console.log("[dlsym] 返回地址: " + func_addr);

            // 只关注 JNI_OnLoad 相关，方便看关键证据
            if (this.symbol.indexOf("JNI_OnLoad") != -1) {
                // 查找这个地址属于哪个模块
                const module = Process.findModuleByAddress(func_addr);
                if (module) {
                    console.log("[!] JNI_OnLoad 归属模块: " + module.name);
                    console.log("[!] 模块基址: " + module.base);
                    console.log("[!] 函数地址 < 模块基址 ? => " + (func_addr < module.base));
                } else {
                    console.log("[!] 警告: JNI_OnLoad 地址不属于任何已知模块！");
                }
            }
        }
    });
}

// 执行 hook
hook_dlsym();
console.log("[+] dlsym hook 已启动，等待调用...");
\```

执行结果:![image](https://bbs.kanxue.com/upload/attach/202604/1068038_BPBHDX3QP6DUFTG.webp)

将上述脚本注入 APP 进程，操作 APP 触发目标 SO 加载，观察日志输出，得到了关键证据：

当 dlsym 函数被调用查询 JNI_OnLoad 符号时，返回的函数地址完全不在任何已知模块的内存区间内——Process.findModuleByAddress(func_addr) 无法找到该地址所属的模块，直接打印“警告: JNI_OnLoad 地址不属于任何已知模块！地址伪造实锤！”。

这个结果直接印证了我的核心猜想，也彻底敲定了真相：

壳 SO 对系统 dlsym 函数做了劫持中转。正常情况下，dlsym 会根据传入的 handle 句柄，遍历目标模块的 soinfo 符号表查询函数地址；但这款加固壳专门拦截了 JNI_OnLoad 的查询请求，直接跳过了系统标准流程，转而跳转到自身私自隐藏加载的真实业务 SO 中进行查询，最终返回了一个虚假的内存地址——这个地址不属于任何已知模块，自然也不会落在 dump 出的“壳 SO”的内存区间内，这也是我们之前发现“地址倒挂”的根本原因。

到这里，我们已经明确了壳的核心防护手法：伪造壳 SO + 劫持 dlsym + 隐藏真实 SO。接下来，我们的核心任务就是：从内存中，把被壳隐藏的真实业务 SO 给“钓”出来。

## hook mmap以及mmprotect函数来钓出隐藏so文件

### 1. mmap 内存映射函数——SO 加载的“基石”

mmap 是 Linux/Android 内核级的内存映射核心接口，也是加载可执行文件（SO、ELF）的底层基石，没有任何替代方案。

**函数作用**：将文件数据（如 SO 文件）或匿名内存，映射到当前进程的虚拟地址空间，分配一段连续的虚拟内存，并返回该内存的起始地址。简单来说，就是“给 SO 分配一块内存空间，让它能 在进程中运行”。

**系统标准用法**：系统 linker 加载 SO 时，必须通过 mmap 函数，将 SO 的代码段（text）、数据段（data）、只读数据段（rodata）等内容，逐一映射到进程内存中，这是 SO 能正常运行的第一步——没有 mmap 分配内存，SO 就无法被 CPU 访问和执行。

**加固壳的死穴**：壳为了隐藏真实业务 SO，会绕开系统 linker 私自加载（避免被 linker 记录到已加载模块链表中），但它绝对无法绕过 mmap 函数！这是内核级限制，无论壳的防护多强，要让真实 SO 运行，就必须调用 mmap 为其分配内存、写入解密后的代码和数据。

**关键价值**：每次调用 mmap 函数，都会返回内存基址（分配的内存起始地址）和映射大小（分配的内存长度），这两个信息正是我们定位隐藏 SO 的核心数据——只要捕获到符合壳特征的 mmap 调用，就能拿到隐藏 SO 的内存地址和大小。

### 2. mprotect 内存权限修改函数——SO 执行的“前提”

mprotect 是专门用于修改内存页访问权限的内核函数，也是 SO 代码能够被 CPU 执行的前提条件，同样无法被绕过。

**函数作用**：为指定的内存区间，设置可读（R）、可写（W）、可执行（X）三种权限的组合（如 RW、RX、R、W、X 等）。

**核心必要性**：SO 的代码段（text）必须拥有“可读 + 可执行（RX）”权限，才能被 CPU 读取并执行；如果没有 RX 权限，CPU 会拒绝执行该内存中的代码，程序会直接崩溃。壳将隐藏 SO 解密并通过 mmap 映射到内存后，默认分配的内存权限通常是“可读 + 可写（RW）”（用于写入解密后的代码数据），之后必须调用 mprotect 函数，将代码段的权限修改为 RX，否则隐藏 SO 无法正常运行。

**关键特征**：隐藏 SO 完成内存映射（mmap）后，一定会紧跟一次 mprotect 调用，且 mprotect 设置的权限为 RX（可读 + 可执行）——这是我们筛选目标 mmap 调用、定位隐藏 SO 的核心标识，能帮我们从大量 mmap 调用中，快速筛选出壳加载隐藏 SO 的操作。

### 3. 监控脚本编写：Hook mmap + mprotect + memcpy

基于上述分析，我们编写 Frida 监控脚本，同时 Hook mmap、mprotect、memcpy 三个函数（memcpy 用于捕获壳解密后的数据拷贝行为，辅助验证隐藏 SO 加载），核心逻辑是：

**Hook mmap**：筛选“大块内存（大于 0x10000，即 64KB，符合 SO 大小特征）+ 只读/读写权限 + 匿名内存（fd = -1，壳加载隐藏 SO 常用匿名内存，避免被关联到具体文件）”的调用，打印内存基址、大小、权限、调用栈，定位隐藏 SO 的内存分配行为；
**Hook mprotect**：筛选“权限为 RX（可读 + 可执行，权限值为 5）”的调用，打印目标地址、修改大小，捕获壳修改隐藏 SO 权限的行为；
**Hook memcpy**：筛选“大块数据拷贝（大于 0x10000）”的调用，打印源地址、目标地址、拷贝大小，辅助验证壳将解密后的 SO 数据写入 mmap 内存的行为。

同时，在 Hook mmap 的 onEnter 阶段，抓取原始的 x30、x29 寄存器并回溯堆栈，从根源规避壳后续伪造堆栈、篡改回溯线索的可能，确保我们捕获到的调用栈是真实的，能定位到壳的加载逻辑。

具体监控脚本如下（已脱敏，可直接使用）：

只要壳SO敢玩弄劫持、伪造地址这类手段，就必然会留下无法掩盖的痕迹，我们直接Hook内核级的mmap函数，在onEnter阶段、函数尚未执行的瞬间抓取原始的x30、x29寄存器并回溯堆栈，从根源规避壳后续伪造堆栈、篡改回溯线索的可能，再结合内存分配的权限与大小特征综合分析，无论上层如何伪装，内核级内存行为无法隐藏，这是我们破局的关键。

注入脚本:

\```
console.log("[+] 开始监控壳的底层行为...");

// Hook mmap + 堆栈回溯
Interceptor.attach(Module.findExportByName(null, "mmap"), {
    onEnter: function (args) {
        // 保存mmap六个参数
        this.addr = args[0];
        this.length = args[1];
        this.prot = parseInt(args[2]);
        this.flags = parseInt(args[3]);
        this.fd = parseInt(args[4]);
        this.offset = args[5];

        // 解析内存权限
        this.protStr = "";
        if (this.prot & 1) this.protStr += "R ";
        if (this.prot & 2) this.protStr += "W ";
        if (this.prot & 4) this.protStr += "X ";
        this.protStr = this.protStr.trim() || "NONE";
    },
    onLeave: function (retval) {
        const len = parseInt(this.length);
        // 过滤壳特征：大块内存 + 只读/读写 + 匿名内存
        if (len > 0x10000 && (this.prot === 1 || this.prot === 3)) {
            console.log("\n======================================");
            console.log("[mmap 申请内存（壳特征）]");
            console.log("返回地址 =", retval);
            console.log("申请大小 =", this.length, "(" + (len / 1024 / 1024).toFixed(2) + "MB)");
            console.log("内存权限 =", this.prot, "(" + this.protStr + ")");
            console.log("完整参数 → fd:", this.fd, "flags:", this.flags, "offset:", this.offset);
            console.log("铁证判定 →", this.fd === -1 ? "匿名内存(壳专用)" : "文件映射");

            // 调用栈回溯
            console.log("\n调用者栈回溯:");
            const stack = Thread.backtrace(this.context, Backtracer.FUZZY);
            stack.forEach((addr, idx) => {
                const debug = DebugSymbol.fromAddress(addr);
                console.log("  " + (idx + 1) + ". " + addr + " | " + (debug.moduleName || "未知模块") + " | " + (debug.functionName || "未知函数"));
            });
            console.log("======================================");
        }
    }
});

// Hook mprotect
Interceptor.attach(Module.findExportByName(null, "mprotect"), {
    onEnter: function (args) {
        this.addr = args[0];
        this.length = args[1];
        this.prot = parseInt(args[2]);

        // RX权限：壳解密SO特征
        if (this.prot === 5) {
            console.log("\n======================================");
            console.log("[mprotect 修改权限为 RX（壳解密特征）]");
            console.log("目标地址 =", this.addr);
            console.log("修改大小 =", this.length);
            console.log("======================================");
        }
    }
});

// Hook memcpy
Interceptor.attach(Module.findExportByName(null, "memcpy"), {
    onEnter: function (args) {
        this.dst = args[0];
        this.src = args[1];
        this.n = parseInt(args[2]);
    },
    onLeave: function (retval) {
        // 过滤大段数据拷贝
        if (this.n > 0x10000) {
            console.log("\n======================================");
            console.log("[memcpy 拷贝大段数据（壳特征）]");
            console.log("目标地址 =", this.dst);
            console.log("来源地址 =", this.src);
            console.log("拷贝大小 =", this.n, "(" + (this.n / 1024 / 1024).toFixed(2) + "MB)");
            console.log("======================================");
        }
    }
});

console.log("[+] 监控脚本安装完成！");
\```

执行结果:

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_62YK3XMACC3TGE9.webp)

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_PP2HR4C8348TASX.webp)

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_9JXRBWFCFWJSY2K.webp)

将监控脚本注入 APP 进程，操作 APP 触发壳加载隐藏 SO，观察日志输出，发现了一个极度反常、足以直接实锤的关键行为：

在壳 SO 的调用栈范围内，程序通过 mmap 申请了一段匿名内存（fd = -1），内存大小约为 1-2MB（符合常规 SO 大小），初始权限为 RW（可读写）；之后，通过 memcpy 向该内存拷贝了大块数据（约 1-2MB）；最后，通过 mprotect 将该内存的权限修改为 RX（可读可执行）。

这套“先分配匿名内存（mmap）→ 写入解密数据（memcpy）→ 修改为可执行权限（mprotect）”的操作，完全违背了系统标准的 SO 加载流程——系统 linker 加载 SO 时，会直接映射 SO 文件，不会采用“匿名内存 + 手动拷贝 + 权限修改”的方式。

从底层原理上，我们可以确凿判定：这段操作正是壳在手动解密、加载并执行隐藏的真实业务 SO 文件——mmap 分配内存，memcpy 写入解密后的 SO 数据，mprotect 修改权限让 SO 可以执行，这三个步骤环环相扣，缺一不可，也是壳无法隐藏的核心行为。

合之前的监控脚本逻辑，编写匿名内存 Dump 脚本，核心功能是：Hook mprotect 函数（当检测到 RX 权限修改时，说明隐藏 SO 已解密完成、权限已设置，此时 Dump 内存完整性最高），获取隐藏 SO 的内存地址和大小，读取内存数据并写入文件，具体脚本如下

执行脚本:

\```
let s = new Set();

function f(a, b) {
    let r = Process.findRangeByAddress(a);
    if (!r) return null;
    let p = r.protection;
    let t = false;
    if (!p.includes('r')) {
        try {
            Memory.protect(a, b, 'rwx');
            t = true;
        } catch (e) {
            return null;
        }
    }
    let c = 0x10000;
    let d = [];
    let o = 0;
    while (o < b) {
        let n = Math.min(c, b - o);
        try {
            let ch = a.add(o).readByteArray(n);
            if (ch === null) {
                if (t) Memory.protect(a, b, p);
                return null;
            }
            d.push(ch);
        } catch (e) {
            if (t) Memory.protect(a, b, p);
            return null;
        }
        o += n;
    }
    if (t) {
        try {
            Memory.protect(a, b, p);
        } catch (e) {}
    }
    let u = new Uint8Array(b);
    let pos = 0;
    for (let ch of d) {
        u.set(new Uint8Array(ch), pos);
        pos += ch.byteLength;
    }
    return u;
}

Interceptor.attach(Module.findExportByName(null, "mmap"), {
    onEnter: function(a) {
        this.l = a[1].toInt32();
        this.pr = a[2].toInt32();
    },
    onLeave: function(rv) {
        if (this.l > 0x10000 && (this.pr & 0x1 || this.pr & 0x2)) {
        }
    }
});

Interceptor.attach(Module.findExportByName(null, "mprotect"), {
    onEnter: function(a) {
        this.ad = a[0];
        this.l = a[1].toInt32();
        this.pr = a[2].toInt32();
    },
    onLeave: function(rv) {
        if ((this.pr & 0x4) && this.l > 0x10000) {
            let k = this.ad.toString();
            if (s.has(k)) return;
            s.add(k);
            setTimeout(() => {
                let dt = f(this.ad, this.l);
                if (dt === null) return;
                let fn = `/sdcard/dump_${this.ad}_${Date.now()}.bin`;
                try {
                    let fl = new File(fn, "wb");
                    fl.write(dt);
                    fl.close();
                } catch (e) {
                    try {
                        let fb = `/data/local/tmp/dump_${this.ad}_${Date.now()}.bin`;
                        let fl2 = new File(fb, "wb");
                        fl2.write(dt);
                        fl2.close();
                    } catch (e2) {}
                }
            }, 100);
        }
    }
});
\```

执行结果:

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_WNC3AKQVP68WJVM.webp)

我们检查dump到的内存块头部，发现这是一个标准的 ARM64 ELF 动态库文件，即被壳隐藏的真实业务 SO

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_38M9FQ2DT9JEXAH.webp)

拖入ida分析

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_B2FD8D6YDGGV5RJ.webp)

这个so和一开始dump到的壳so，虽然都只有一个start函数，但是含义完全不一样，之前那个纯粹就是障眼法

之前的壳so的start：

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_ZFEXBFZ3GAGBJ3R.webp)

本次dump到的start

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_F3H8JFG2VJKEGK6.webp)

但是还是没有jni_onload函数的踪迹，可能是被做了函数分块跳转，我们来验证一下

我们接下来对代码偏移的精准计算与后续分析。接下来，我将借助 Stalker 追踪 JNI_OnLoad 的实际执行流程，以此硬核验证：当前捕获到的 JNI_OnLoad 函数，正是已转储（dump）隐藏 SO 文件中的一段核心指令片段

## stalker跟踪jni_onload指令流证明猜想

为了验证我们对内存偏移、隐藏 SO 结构与代码位置的全部推断，接下来我们将使用Frida Stalker 对 `JNI_OnLoad` 函数进行指令级动态追踪。Frida Stalker 是 Frida 框架内置的高性能代码跟踪引擎，能够在不修改程序、不重启进程的前提下，实时捕获目标线程的每一条 CPU 指令执行流，精准还原函数的完整运行路径。通过将 Stalker 捕获的动态指令序列，与我们 dump 出的隐藏 SO 静态代码进行逐行比对，即可 100% 验证 `JNI_OnLoad` 正是该隐藏 SO 中的一段核心指令片段，同时确认我们的偏移分析完全准确。同时，我们并行运行 mmap 监控脚本，实时捕获壳在解密阶段申请的匿名内存块基地址与大小。

执行脚本:

\```
const m = "xxxxxx.so";
var s = false;
Interceptor.attach(Module.findExportByName(null, "android_dlopen_ext"), {
    onEnter: function (a) {
        try {
            if (a[0].readCString().indexOf(m) != -1) s = true;
        } catch (e) { }
    },
    onLeave: function () {
        if (s) {
            const m0 = Process.findModuleByName(m);
            if (!m0) return;
            const j = m0.findExportByName("JNI_OnLoad");
            if (!j) return;
            Interceptor.attach(j, {
                onEnter: function () {
                    var t = Process.getCurrentThreadId();
                    var st = j;
                    var ed = j.add(0x10000);
                    try {
                        var art = Process.getModuleByName("libart.so");
                        Stalker.exclude({ base: art.base, size: art.size });
                    } catch (e) { }
                    Stalker.follow(t, {
                        events: {
                            call: false,
                            ret: false,
                            exec: true,
                            block: true,
                            compile: true
                        },
                        onReceive: function () { },
                        transform: function (i) {
                            var ins = i.next();
                            while (ins) {
                                var addr = ins.address;
                                if (addr.compare(st) >= 0 && addr.compare(ed) <= 0) {
                                    console.log(addr, ins);
                                }
                                i.keep();
                                ins = i.next();
                            }
                        }
                    });
                },
                onLeave: function () { }
            });
        }
    }
});
\```

执行结果:

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_SF5PWHRCN9HEAWZ.webp)

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_J2JYBWTKHKUQPYK.webp)

我们通过脚本捕获到隐藏 SO 被 mmap 映射的内存基地址，再结合 Stalker 追踪到的指令运行时绝对地址，通过基地址与指令地址做差，精准计算出每条指令在隐藏 SO 中的文件偏移。拿到偏移后，我们直接在 IDA 中跳转到对应位置

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_FR9SJA643TMVS4G.webp)

可以看到，和指令流完全一样，接下来，我们就可以进一步进行分析为什么在jni_onload里面函数的自杀触发点了 ，后续过程本贴不演示了，排查方法我有一个帖子有讲到，大家可以去参考

但这里我想提一嘴的是：很多常规的 Stalker 追踪脚本，都是基于导出函数、命名函数、函数入口来触发打印与跟踪逻辑的。而加壳 SO 会故意把原本属于同一个函数内部的代码片段，包装成独立的 “伪函数”，通过跳转执行。这就导致：常规脚本只能追踪到 “外层函数”，一旦执行流跳转到这些内部包装的伪函数，触发条件不满足，打印逻辑直接中断，线索就此断掉，无法完整追踪真实执行流。

![image](https://bbs.kanxue.com/upload/attach/202604/1068038_V8K9BDDR4T8UBCW.webp)

这里就能看出来，**这块代码根本没有标准的函数序言**。正常函数开头都会有压栈、设置栈帧之类的指令，比如 `stp x29, x30, [sp, #-0x10]!`，但它完全没有。

这说明什么？说明这个所谓的 `JNI_OnLoad` 并不是一个完整、正规的函数，只是壳从真实逻辑里抽出来的一段指令碎片。

现在很多高强度加固的检测函数都是这么处理的：不保留完整函数结构，不按正常 ELF 符号导出，切成碎片散在内存里，然后通过各种跳转、跳板把这些碎片串起来执行，跑到最后就是反调试、自杀、进程销毁那套逻辑。

所以你在 IDA 里翻导出表、找函数列表是找不到的，因为它本身就不是一个 “函数”，只是一段被壳调度执行的指令碎片

后续也是成功把这个加固检测过掉了哈哈，stalker真是一个好用的工具，直接上帝视角随意修改分支，定位检测函数 ，后续出个帖子分享

本文到此分析结束，通过这个案例，我自己也认识到了底层知识对逆向的重要性，如果有错误之处，恳请大佬指出。

---

# 回复

## 回复 by mb_ldbucrik (#2)

*2026-4-4 16:18*

感谢分享

## 回复 by jyotidwi (#3)

*2026-4-4 16:32*

tql

## 回复 by 东方玻璃 (#4)

*2026-4-4 16:33*

思路不错, mprotect改匿名R-X段太明显了![image](https://bbs.kanxue.com/view/img/face/065.gif) 我文章给的脚本可以配合hook dlopen, 匹配到目标so名后在onLeave中扫内存, 可以得到解密后的so, 即自定义linker和目标so同名. 估计自定义linker在init/init_array/JNI_OnLoad执行了解密操作, onLeave时解密完成所以可以dump.

## 回复 by reserve_zhou (#5)

*2026-4-4 16:40*

>
> [东方玻璃](https://bbs.kanxue.com/user-968342.htm)
>  思路不错, mprotect改匿名R-X段太明显了[em_065] 我文章给的脚本可以配合hook dlopen, 匹配到目标so名后在onLeave中扫内存, 可以得到解密后的so, 即自定义lin ...
>

谢谢大佬指点！回头就去试试这个好方法

## 回复 by mb_asiwnxyv (#6)

*2026-4-4 19:54*

感谢分享

## 回复 by mb_cfjwplfo (#7)

*2026-4-4 20:16*

大佬，如何找到dumpso的JNI_OnLoad的地址啊

## 回复 by Zepp7289 (#8)

*2026-4-4 20:18*

tql

## 回复 by 嘎嘎真的很棒 (#9)

*2026-4-4 20:23*

感谢分享

## 回复 by reserve_zhou (#10)

*2026-4-4 20:24*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  大佬，如何找到dumpso的JNI_OnLoad的地址啊
>

frida官方有一个专门查全局函数的API在文档里面有体现，你先把这个jnionload绝对地址给查出来  和他申请的匿名内存块的绝对地址进行相减，就能得到它的真实偏移了  他把jnionload函数重定位到隐藏so了

## 回复 by 嘎嘎真的很棒 (#11)

*2026-4-4 20:27*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  大佬，如何找到dumpso的JNI_OnLoad的地址啊
>

hook dlsym

## 回复 by mb_cfjwplfo (#12)

*2026-4-4 20:32*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  frida官方有一个专门查全局函数的API在文档里面有体现，你先把这个jnionload绝对地址给查出来 和他申请的匿名内存块的绝对地址进行相减，就能得到它的真实偏移了 他把jnionload函数 ...
>

大佬我发现你文章那个jnionload算错了，偏移应该是函数减基地址，你算的是基址减偏移，函数地址是大于基址的

## 回复 by reserve_zhou (#13)

*2026-4-4 20:33*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  大佬我发现你文章那个jnionload算错了，偏移应该是函数减基地址，你算的是基址减偏移，函数地址是大于基址的
>

并没有算错 就是因为函数小于这个地址，才有了这篇文章 因为他把这个重定向到了另外一块地址

## 回复 by reserve_zhou (#14)

*2026-4-4 20:35*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  大佬我发现你文章那个jnionload算错了，偏移应该是函数减基地址，你算的是基址减偏移，函数地址是大于基址的
>

然后看一下我文章的开头前言，因为这个可能是对地址做了一下重定位  他把这个linker给劫持了

## 回复 by mb_cfjwplfo (#15)

*2026-4-4 20:36*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  然后看一下我文章的开头前言，因为这个可能是对地址做了一下重定位 他把这个linker给劫持了
>

我问了ai，而图片中给出的偏移是 0xfffffffffb5cd114，这实际上是 -0x4a32eec 的补码表示（即基址减函数地址的结果）。因此，偏移计算的方向反了，得出的结果不正确。正确的偏移应为正数 0x4a32eec

## 回复 by reserve_zhou (#16)

*2026-4-4 20:37*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  我问了ai，而图片中给出的偏移是 0xfffffffffb5cd114，这实际上是 -0x4a32eec 的补码表示（即基址减函数地址的结果）。因此，偏移计算的方向反了，得出的结果不正确。正确的偏移应 ...
>

正因为它劫持了 Linker，导致  JNI_OnLoad  不在正常 ELF 段内，才出现了这种反常值。所谓的“正数偏移”在此场景下并不成立，这不是计算错误，是内存布局被篡改的典型现象。

## 回复 by reserve_zhou (#17)

*2026-4-4 20:38*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  我问了ai，而图片中给出的偏移是 0xfffffffffb5cd114，这实际上是 -0x4a32eec 的补码表示（即基址减函数地址的结果）。因此，偏移计算的方向反了，得出的结果不正确。正确的偏移应 ...
>

你把我的开头喂给AI让AI帮你讲解一下，应该就能得到你想要的答案了

## 回复 by mb_cfjwplfo (#18)

*2026-4-4 20:40*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>
>
>
>  mb_cfjwplfo
>
>  我问了ai，而图片中给出的偏移是 0xfffffffffb5cd114，这实际上是 -0x4a32eec 的补码表示（即基址减函数地址 ...
>

你用了基址减函数这个偏移一定是负数。
看这里文章的这里，jni是0x70fe，基址是0x70f9
而我们发现的“JNI_OnLoad 地址 < 模块基址”，

## 回复 by bisoso (#19)

*2026-4-4 20:49*

感谢分享！！

## 回复 by reserve_zhou (#20)

*2026-4-4 21:09*

>
> [mb_cfjwplfo](https://bbs.kanxue.com/user-1009544.htm)
>  你用了基址减函数这个偏移一定是负数。
> 看这里文章的这里，jni是0x70fe，基址是0x70f9
> 而我们发现的“JNI_OnLoad 地址 < 模块基址”，
>

感谢指正！刚刚的图片在复现时的情况和第一次不一样，第一次遇到情况时，匿名so块的基本地址小于壳so的基本地址，所以才会出现jni_onload重定位到小于base地址的情况！我写帖子复现时出现了第二种结果，匿名so块的基本地址大于壳so基本地址，所以出现了图片的有悖情况！现已将图片替换成第一种情况方便大家确认偏移的异常！但是本质都是劫持linker，这是文章的重点，再次感谢指正！

## 回复 by wx_妳还是不懂 (#21)

*2026-4-4 21:50*

大佬，遇到防止hook的壳怎么办，会直接卡第一屏，检测很厉害

## 回复 by reserve_zhou (#22)

*2026-4-4 22:09*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  大佬，遇到防止hook的壳怎么办，会直接卡第一屏，检测很厉害
>

我有一篇帖子专门讲了过检测的思路，还在脱敏 应该过一阵会放出来。这篇帖子就是过检测的前置

## 回复 by Imxz (#23)

*2026-4-4 23:13*

rbq

## 回复 by tonykros (#24)

*2026-4-4 23:42*

666

## 回复 by Gryffindoss (#25)

*2026-4-5 20:17*

++

## 回复 by Kill_Log (#26)

*2026-4-5 20:21*

6666666666

## 回复 by 墨穹呢 (#27)

*2026-4-5 20:25*

感谢分享

## 回复 by nianchu (#28)

*2026-4-5 20:51*

梆梆厂商 连夜改代码

## 回复 by reserve_zhou (#29)

*2026-4-5 21:05*

>
> [nianchu](https://bbs.kanxue.com/user-949800.htm)
>  梆梆厂商 连夜改代码
>
>

夸张了，哈哈，后续分析没放出来呢

## 回复 by 小迷糊ddd (#30)

*2026-4-5 21:17*

感谢分享，学习一下。

## 回复 by mb_cqcrdwgm (#31)

*2026-4-5 21:55*

666

## 回复 by MaYil (#32)

*2026-4-5 22:09*

感谢分享

## 回复 by git_55111Empycity (#33)

*2026-4-5 23:20*

66

## 回复 by 沭阳 (#34)

*2026-4-6 10:39*

666

## 回复 by 桐人dx (#35)

*2026-4-6 12:33*

666

## 回复 by HSQ (#36)

*2026-4-6 17:15*

感谢分享

## 回复 by 院士 (#37)

*2026-4-6 18:08*

这个厉害，留个记号先。

## 回复 by lackone (#38)

*2026-4-6 18:25*

66666

## 回复 by 悟 (#39)

*2026-4-6 20:10*

1111

## 回复 by wx_妳还是不懂 (#40)

*2026-4-6 20:11*

![图片描述](https://bbs.kanxue.com/upload/attach/202604/913925_FCZEDBGNUTSHMBR.webp) ![图片描述](https://bbs.kanxue.com/upload/attach/202604/913925_UXF45PNYNVJBVAP.webp)这加固检测太强了

## 回复 by 黑屏 (#41)

*2026-4-6 20:40*

666

## 回复 by mb_ysikfhxt (#42)

*2026-4-6 22:22*

666

## 回复 by 鞠婧祎 (#43)

*2026-4-6 23:37*

看看

## 回复 by reserve_zhou (#44)

*2026-4-7 00:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  这加固检测太强了
>
>

扁平化了，你追踪下死亡函数或者执行流，你试试使用stalker

## 回复 by wx_妳还是不懂 (#45)

*2026-4-7 01:00*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  扁平化了，你追踪下死亡函数或者执行流，你试试使用stalker
>
>

都是用SVC 和异步校验 非法内存访问 老是杀frida ，我都不知道怎么跟踪了

## 回复 by pingsky (#46)

*2026-4-7 01:39*

666

## 回复 by reserve_zhou (#47)

*2026-4-7 01:57*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  都是用SVC 和异步校验 非法内存访问 老是杀frida ，我都不知道怎么跟踪了
>

其实只要有一个so文件 能确定它的死亡范围 理论上是可以猜透他的死亡分支的 你先试着缩小范围 锁定一个死亡函数 stalker追踪指令运行 回调慢慢改分支 慢慢改 别着急

## 回复 by reserve_zhou (#48)

*2026-4-7 02:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  都是用SVC 和异步校验 非法内存访问 老是杀frida ，我都不知道怎么跟踪了
>

对照stalker指令流 和汇编代码一起看 慢慢的甚至可以找到脱壳业务分支 慢慢去改  在stalker副本运行的时候去掉无用代码或者死亡分支  我其实说实话还没遇到过你这种难度的 我也还是新手

## 回复 by buluo533 (#49)

*2026-4-7 08:26*

学习了，大佬

## 回复 by ldehua (#50)

*2026-4-7 09:20*

666

## 回复 by dsr000 (#51)

*2026-4-7 09:36*

666

## 回复 by GEKEZYX (#52)

*2026-4-7 09:46*

666

## 回复 by wx_weggfkdk (#53)

*2026-4-7 09:51*

666

## 回复 by 我就是小熊猫 (#54)

*2026-4-7 10:11*

666

## 回复 by mb_pesxllvn (#55)

*2026-4-7 10:25*

666

## 回复 by XCicada (#56)

*2026-4-7 12:26*

666

## 回复 by 一栋奥特曼 (#57)

*2026-4-7 12:29*

666

## 回复 by mb_vkqcleyo (#58)

*2026-4-7 14:03*

66666

## 回复 by 独一无二_370133 (#59)

*2026-4-7 14:10*

6666

## 回复 by mb_hfjfruhl (#60)

*2026-4-7 15:06*

1

## 回复 by Crack999 (#61)

*2026-4-7 15:37*

666

## 回复 by mb_hfpmtthz (#62)

*2026-4-7 19:33*

666

## 回复 by SomeMx (#63)

*2026-4-7 21:18*

学习一下

## 回复 by Gryffindoss (#64)

*2026-4-7 22:02*

666

## 回复 by 菜鸟逆向 (#65)

*2026-4-7 23:03*

![image](https://bbs.kanxue.com/view/img/face/001.gif)666

## 回复 by wx_妳还是不懂 (#66)

*2026-4-8 00:22*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  其实只要有一个so文件 能确定它的死亡范围 理论上是可以猜透他的死亡分支的 你先试着缩小范围 锁定一个死亡函数 stalker追踪指令运行 回调慢慢改分支 慢慢改 别着急
>

你能看一下么，这个绕过了libxloader.so 但是它居然还要传递数据给下一个libnllvm.so，结果libnllvm.so崩了

## 回复 by wx_妳还是不懂 (#67)

*2026-4-8 00:35*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  对照stalker指令流 和汇编代码一起看 慢慢的甚至可以找到脱壳业务分支 慢慢去改 在stalker副本运行的时候去掉无用代码或者死亡分支 我其实说实话还没遇到过你这种难度的 我也还是新手
>

我放弃了，不想研究了，我才是新手的新手，过个检测都这么难

## 回复 by reserve_zhou (#68)

*2026-4-8 00:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  我放弃了，不想研究了，我才是新手的新手，过个检测都这么难
>

上来别整这么难的 别放弃 先找个简单点的收费加固 把指令汇编玩透 其实你把过检测吃透了 对汇编什么so层分析会有很大帮助  再看加解密过签也会容易一点

## 回复 by reserve_zhou (#69)

*2026-4-8 00:42*

这个帖子的检测我过了 是追踪指令一个一个调的 后面出个教程

## 回复 by reserve_zhou (#70)

*2026-4-8 00:43*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  wx_妳还是不懂](https://bbs.kanxue.com/user-913925.htm)
>  我放弃了，不想研究了，我才是新手的新手，过个检测都这么难
>

这个帖子的检测我过了 是追踪指令一个一个调的 后面出个教程

## 回复 by iBa0 (#71)

*2026-4-8 10:15*

666

## 回复 by mb_euhyowpw (#72)

*2026-4-8 10:38*

666

## 回复 by wx_Huber Barrientos (#73)

*2026-4-8 12:50*

感谢分享！！

## 回复 by mb_ybvqgbkl (#74)

*2026-4-8 17:54*

666666

## 回复 by 吖銮 (#75)

*2026-4-9 10:41*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  这个帖子的检测我过了 是追踪指令一个一个调的 后面出个教程
>

催更！！！！！非常想学习大佬的思路![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by reserve_zhou (#76)

*2026-4-9 10:59*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  吖銮](https://bbs.kanxue.com/user-1072095.htm)
>  催更！！！！！非常想学习大佬的思路[em_065]
>

很高兴你能对我的思路感兴趣 在此之前 你可以先学习一下fridastalker 追踪的底层原理 比如说怎么实现异常控制的 为什么到svc或者调用系统so比如说libc.so容易跟丢 副本运行机制 都了解一下

## 回复 by mb_uvyukvot (#77)

*2026-4-9 16:53*

666

## 回复 by mb_cbgtaveo (#78)

*2026-4-10 16:15*

66666666666

## 回复 by huangbof (#79)

*2026-4-10 16:51*

—没有 mmap 分配内存，SO 就无法被 CPU 访问和执行

## 回复 by wx_Deity (#80)

*2026-4-11 21:20*

666

## 回复 by 上官兮唐 (#81)

*2026-4-11 23:33*

看看

## 回复 by wx_宇克鴻 (#82)

*2026-4-11 23:45*

6666

## 回复 by mb_yyvcbkli (#83)

*2026-4-13 11:48*

学习一下先进经验

## 回复 by 不具名的悲伤 (#84)

*2026-4-13 13:51*

6

## 回复 by mb_jnmxfjku (#85)

*2026-4-13 17:30*

666

## 回复 by 呆萌的小白 (#86)

*2026-4-13 18:20*

学了,学不会,所以收藏了

## 回复 by 奇奇怪怪 (#87)

*2026-4-14 10:50*

66

## 回复 by uni7corn (#88)

*2026-4-14 14:19*

感谢分享

## 回复 by mb_zuiylqkn (#89)

*2026-4-15 15:50*

谢谢分享

## 回复 by mb_bzkmcyjt (#90)

*2026-4-15 16:31*

666

## 回复 by woaiziyou (#91)

*2026-4-15 17:21*

学习一下

## 回复 by 飆汗吉米 (#92)

*2026-4-15 23:46*

667

## 回复 by 菜鸟9527 (#93)

*2026-4-16 00:04*

6666666

## 回复 by cpannn (#94)

*2026-4-17 20:59*

学习了

## 回复 by pangzibupang (#95)

*2026-4-17 21:58*

感谢分享

## 回复 by mb_agxdcibq (#96)

*2026-4-18 12:26*

666

## 回复 by mb_dqvhswyr (#97)

*2026-4-19 16:26*

1

## 回复 by git_14248bibinocode (#98)

*2026-4-20 11:16*

66666

## 回复 by 斗转南see雪 (#99)

*2026-4-20 14:53*

666

## 回复 by mb_ggnpkuap (#100)

*2026-4-20 18:04*

大佬有样本吗？

## 回复 by apxar (#101)

*2026-4-20 22:21*

1

## 回复 by mb_dcjxxhsk (#102)

*2026-4-20 23:41*

666

## 回复 by mb_yjiuccxa (#103)

*2026-4-21 14:30*

学习

## 回复 by 我是小奥 (#104)

*2026-4-21 16:46*

感谢分享！！

## 回复 by 木魚· (#105)

*2026-4-21 16:59*

66666666

## 回复 by wx_插曲 (#106)

*2026-4-23 18:00*

666

## 回复 by xeiyu (#107)

*2026-4-23 18:28*

666

## 回复 by niama (#108)

*2026-5-4 07:38*

666

## 回复 by shuangmou (#109)

*2026-5-4 12:51*

感谢分享

## 回复 by 胡了个三 (#110)

*2026-5-4 20:45*

++++

## 回复 by mb_xbgppumd (#111)

*2026-5-5 01:16*

666

## 回复 by 寻梦之璐 (#112)

*2026-5-5 22:49*

666

## 回复 by mb_qlbmqqmd (#113)

*2026-5-6 09:54*

++

## 回复 by mb_lzotvdxv (#114)

*2026-5-9 20:16*

请在 Telegram 上联系我，有个重要的 2000 美元任务。
 Telegram：@dlopenext

## 回复 by 雪国的冬天 (#115)

*2026-5-10 00:14*

感谢大佬分享

## 回复 by xguang4xy (#116)

*2026-5-12 17:30*

tql，学到了学到了

## 回复 by 莫名其妙abc (#117)

*2026-5-12 18:57*

感谢分享！！

## 回复 by mb_nzmpaifg (#118)

*2026-5-12 20:46*

学习学习

## 回复 by mb_rirvdrlh (#119)

*2026-5-13 00:47*

6666666

## 回复 by mb_hcadvceu (#120)

*2026-5-16 23:14*

6666

## 回复 by mb_lhxrckiu (#121)

*2026-5-16 23:43*

看看

## 回复 by 一一映射 (#122)

*2026-5-19 11:20*

必须点个赞，????????

## 回复 by ADR66 (#123)

*2026-5-19 11:28*

6666

## 回复 by mb_xmrlajmj (#124)

*2026-5-22 20:32*

666

## 回复 by mb_sqetvntx (#125)

*2026-5-23 09:18*

学习

## 回复 by mb_sqetvntx (#126)

*2026-6-1 15:51*

xx

## 回复 by wltqqzsglg (#127)

*2026-6-5 10:15*

好，但是在基础点就更好了

## 回复 by mb_ezmrnfsu (#128)

*2026-6-9 22:49*

666

## 回复 by wx_小白_266 (#129)

*2026-6-17 10:35*

看看

## 回复 by mb_audxeeaj (#130)

*2026-6-17 16:19*

感谢分享

## 回复 by git_73275XuanLong18 (#131)

*2026-6-24 16:27*

666

## 回复 by dob_C (#132)

*2026-6-24 16:44*

感谢分享

## 回复 by mb_gjhmacqd (#133)

*2026-7-5 15:01*

666

## 回复 by mb_qqihqaoo (#134)

*2026-7-5 15:03*

6666666

## 回复 by 奋斗der小鸟 (#135)

*2026-7-5 16:05*

1

## 回复 by 斗转南see雪 (#136)

*2026-7-6 17:02*

666

## 回复 by wx_coddvccwyh (#137)

*2026-7-7 04:08*

66666

## 回复 by mb_bwxyybya (#138)

*2026-7-7 10:21*

666

## 回复 by mb_paopxhtx (#139)

*2026-7-8 11:43*

66666

## 回复 by 斗转南see雪 (#140)

*2026-7-8 18:01*

>_<

## 回复 by wx_kx92911 (#141)

*2026-7-8 18:22*

感谢分析

## 回复 by mb_fafswnif (#142)

*2026-7-14 16:14*

感谢分享

## 回复 by scllqk (#143)

*2026-7-20 14:54*

学习

## 回复 by upcj (#144)

*2026-7-20 17:25*

tql

## 回复 by mb_hktfsykj (#145)

*2026-7-21 21:20*

佬，我在过的时候发现根据路径判断so结果调用了两次call_constructors，是不是也可以作为一个判断依据啊

## 回复 by reserve_zhou (#146)

*2026-7-22 12:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_hktfsykj](https://bbs.kanxue.com/user-1020272.htm)
>  佬，我在过的时候发现根据路径判断so结果调用了两次call_constructors，是不是也可以作为一个判断依据啊
>

很久没有看过这个案例了， 不过壳已经把后续全部流程劫持了 。也就是说后续怎么加载解析隐藏so都是他说了算 ，他可以调用linker提供的api callconstructor 也可以自己手动解析so， 创建soinfo ，然后自己调用。不过mmap是必须执行的虚拟映射 ，这个不调用是不行的 也就是必然特征

## 回复 by reserve_zhou (#147)

*2026-7-22 13:03*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_hktfsykj](https://bbs.kanxue.com/user-1020272.htm)
>  佬，我在过的时候发现根据路径判断so结果调用了两次call_constructors，是不是也可以作为一个判断依据啊
>

关于我刚刚说的这些 我也很久没复习底层了 可能会有错误的地方

## 回复 by mb_hktfsykj (#148)

*2026-7-27 09:23*

>
> [reserve_zhou](https://bbs.kanxue.com/user-1068038.htm)
>  很久没有看过这个案例了， 不过壳已经把后续全部流程劫持了 。也就是说后续怎么加载解析隐藏so都是他说了算 ，他可以调用linker提供的api callconstructor 也可以自己手动解析so， ...
>

好的，谢谢佬

## 回复 by mb_jhohnbzu (#149)

*2026-7-27 10:07*

666

## 回复 by ben_ (#150)

学习
