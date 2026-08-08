---
title: '[原创]一种基于 ART 内存特征的 LSPosed/Xposed/分身环境 完美检测方案'
url: https://bbs.kanxue.com/thread-289567.htm
tid: 289567
author: 世界美景
date: '2025-12-25'
tags: [Android安全, 原创, 混淆加固, HOOK注入, 其他]
crawled_at: '2026-08-08T10:34:30+00:00'
replies: 282
---

## 前言：猫鼠游戏的困局

在 Android 反作弊（Anti-Cheat）的战场上，检测 Xposed 类框架（LSPosed, EdXposed 等）一直是最核心的对抗环节。

传统的检测手段通常依赖于：

1. **文件检测**：扫描 /data/app 下的异常 APK 或 /proc/self/maps 中的异常 SO。
2. **符号检测**：尝试 dlopen 或 dlsym 寻找框架特有的导出函数。
3. **堆栈回溯**：[在 Java /JNI层制造异常](https://bbs.kanxue.com/thread-289531.htm)，检测堆栈中是否有 LSPHooker 或 XposedBridge。

然而，随着 **Shamiko** 等隐藏模块的出现，以及 **Magisk/KernelSU** 带来的内核级隐藏能力，上述手段正变得越来越无力。攻击者可以 Hook open、read、dlopen 甚至系统调用，给反作弊 SDK 返回一份“完美”的虚假数据。

**我们是否能跳出 API 调用的维度，直接从虚拟机内存的物理本质上抓出作弊框架？**

答案是肯定的。本文将分享一种 **Tier 0 级别** 的检测方案：**基于 ART 内存布局特征的 ClassLoader 计数检测**。

核心原理：ART 的软肋与死局

### 1. ClassLinker：虚拟机的“户籍办”

在 Android 的 ART 虚拟机中，Runtime 结构体持有一个核心组件——**ClassLinker**。它的职责是管理所有的类加载器（ClassLoader）和类。

在 ClassLinker 的 C++ 对象内部，维护了一个链表：**class_loaders_**。
这是一个 std::list，记录了当前进程中所有 **存活** 的 ClassLoader。

### 2. LSPosed 的“生存悖论” (The GC Paradox)

LSPosed 要实现模块注入，必须创建自己的 PathClassLoader 或 DexClassLoader 来加载模块代码。

这里存在一个**无法解决的死局**：

- **为了生存**：LSPosed 创建的 ClassLoader 必须被注册到 ClassLinker 的 class_loaders_ 链表中。如果它试图将自己从链表中移除（隐藏），ART 的垃圾回收机制（GC）会认为该 ClassLoader 不可达，进而将其回收。**一旦回收，模块代码被卸载，Hook 瞬间失效，甚至导致 App 崩溃。**
- **为了隐藏**：它必须从链表中消失。

**结论**：LSPosed **不得不** 赖在这个链表里。只要它在，我们就能抓到它。

## 技术实现：内存盲扫 (Blind Memory Scanning)

为了绕过所有的 Hook（包括 PLT Hook, Inline Hook, Syscall Hook），本方案**不调用任何系统 API**（如 GetClassLinker），而是直接进行**C++ 内存指针运算**。

### Step 1: 寻找 Runtime (The Entry)

通过标准的 JNI 接口获取 JavaVM，进而拿到 Runtime 指针。这是极其稳定的，几乎所有 Android 版本通用。

| 123 | `JavaVM* vm = nullptr;``env->GetJavaVM(&vm);``void``* runtime = *((``void``**)((``uintptr_t``)vm +``sizeof``(``void``*)));` |
|-|-|

### tep 2: 全动态特征扫描 (The Scanner)

由于不同 Android 版本和厂商 ROM 的 Runtime 结构体布局不同，硬编码偏移量（Offset）是不可靠的。我们采用**运行时特征扫描**：

**特征 A：VTable 校验**
ClassLinker 是一个 C++ 对象，其首地址一定是虚函数表（VTable）指针。该 VTable 地址必然位于 libart.so 的只读数据段（.rodata）内。

**特征 B：双向循环链表**
class_loaders_ 是 std::list，其底层是双向循环链表。必然满足以下指针关系：

| 12 | `node->next->prev == node``node->prev->next == node` |
|-|-|

**特征 C：数量合理性**
正常的 App 启动后，至少包含 BootClassLoader 和 PathClassLoader。因此，链表节点数必然 >= 2。

结合上述特征，我们在 Runtime 内存范围内进行暴力搜索：

| 1234567891011 | `// 伪代码演示``for` `(``int` `offset = 0; offset < 0x500; offset += PTR_SIZE) {``void``* candidate = *(``void``**)(runtime + offset);``if` `(IsVTableValid(candidate)) {``// 特征A``if` `(HasValidList(candidate)) {``// 特征B & C``// 锁定 ClassLinker 和 List 的偏移！``g_ClassLinkerOffset = offset;``break``;``}``}``}` |
|-|-|

### Step 3: 计数判定 (The Verdict)

一旦锁定链表位置，直接遍历并计数。

- **纯净环境**：通常只有 **2-3** 个 ClassLoader（Boot + App + WebView）。
- **注入环境**：LSPosed 会为框架自身、每个模块、以及沙箱环境创建额外的 ClassLoader。
- 在实际测试中，LSPosed 环境下的 ClassLoader 数量通常高达 **13-15 个，分身环境实测只会比正常环境+1**。

**判定逻辑**：Count > 10 即视为异常。

检测代码 (C++):

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200 | `//通过内存暴力搜索，找到 Runtime 对象中的 ClassLinker 指针，再进一步定位 class_loaders_ 链表。``namespace` `anti_ClassLinker {` `// 1. 基础结构与工具``// =============================================================` `// 双向链表节点 (64位)``struct` `ListNode {``ListNode* next;``ListNode* prev;``};` `// 全局静态变量：缓存扫描到的偏移量``// 初始化为 -1，表示尚未扫描``static` `int` `g_ClassLinkerOffset = -1;``static` `int` `g_ListOffset = -1;` `// 内存安全检查：防止读取非法地址导致 SIGSEGV``static` `bool` `IsAddressReadable(``void``* addr) {``if` `(!addr)``return` `false``;``unsigned``char` `vec = 0;``size_t` `page_size = getpagesize();``// 对齐到页边界``uintptr_t` `align_addr = (``uintptr_t``)addr & ~(page_size - 1);``// mincore 检查该页是否在物理内存中``return` `mincore((``void``*)align_addr, page_size, &vec) == 0 && (vec & 1);``}` `// 解析 /proc/self/maps 获取 libart.so 的内存范围``// 用于校验 VTable 是否合法``static` `bool` `GetArtMemoryRange(``uintptr_t``* start,``uintptr_t``* end) {``FILE``* fp =``fopen``(``"/proc/self/maps"``,``"r"``);``if` `(!fp)``return` `false``;``char` `line[512];``bool` `found =``false``;``while` `(``fgets``(line,``sizeof``(line), fp)) {``if` `(``strstr``(line,``"/libart.so"``)) {``// 匹配 libart.so 路径``unsigned``long` `s, e;``if` `(``sscanf``(line,``"%lx-%lx"``, &s, &e) == 2) {``if` `(!found) *start = s;``// 记录起始地址``*end = e;``// 不断更新结束地址，直到最后一段``found =``true``;``}``}``}``fclose``(fp);``return` `found;``}` `// =============================================================``// 2. 核心扫描逻辑 (只在初始化时运行一次)``// =============================================================` `// 在 Runtime 内存中暴力搜索 ClassLinker 和 class_loaders_ 链表``static` `void` `ScanOffsets(``void``* runtime) {``uintptr_t` `art_start = 0, art_end = 0;``if` `(!GetArtMemoryRange(&art_start, &art_end)) {``LOGE(``"[-] 无法获取 libart.so 内存映射"``);``return``;``}` `LOGD(``" [初始化] 开始全动态扫描 Art 内存特征..."``);``uintptr_t` `runtime_addr = (``uintptr_t``)runtime;` `// --- 外层循环：扫描 Runtime 成员，寻找疑似 ClassLinker ---``// 范围：0 ~ 0x500 (通常在 0x200-0x350 之间)``for` `(``int` `cl_off = 0; cl_off < 0x500; cl_off += 8) {``void``** ptr_candidate = (``void``**)(runtime_addr + cl_off);``if` `(!IsAddressReadable(ptr_candidate))``continue``;` `void``* potential_obj = *ptr_candidate;``if` `(!IsAddressReadable(potential_obj))``continue``;` `// [特征1] 验证 VTable``// C++ 对象的头 8 字节是指向 VTable 的指针``void``** vptr = (``void``**)potential_obj;``if` `(!IsAddressReadable(vptr))``continue``;``uintptr_t` `vtable = (``uintptr_t``)*vptr;` `// VTable 地址必须落在 libart.so 的内存区间内``if` `(vtable < art_start \|\| vtable > art_end)``continue``;` `// --- 内层循环：在疑似对象中寻找 class_loaders_ 链表 ---``// 范围：0 ~ 0x500 (通常在 0x50-0x300 之间)``uintptr_t` `obj_addr = (``uintptr_t``)potential_obj;``for` `(``int` `list_off = 0; list_off < 0x500; list_off += 8) {``ListNode* head = (ListNode*)(obj_addr + list_off);``if` `(!IsAddressReadable(head))``continue``;` `ListNode* next = head->next;``ListNode* prev = head->prev;` `if` `(!IsAddressReadable(next) \|\| !IsAddressReadable(prev))``continue``;` `// [特征2] 双向链表闭环检测``// head->next->prev == head  且  head->prev->next == head``if` `(next->prev == head && prev->next == head) {` `// 排除空链表 (next == head)，因为 class_loaders_ 必不为空``if` `(next == head)``continue``;` `// [特征3] 节点数量验证``// 正常的 App 至少有 2 个 Loader (Boot + Path)``int` `count = 0;``ListNode* curr = next;``bool` `is_valid_list =``true``;` `// 遍历计数，同时防止死循环``while` `(curr != head) {``count++;``if` `(count > 200) { is_valid_list =``false``;``break``; }``if` `(!IsAddressReadable(curr) \|\| !IsAddressReadable(curr->next)) {``is_valid_list =``false``;``break``;``}``curr = curr->next;``}` `if` `(is_valid_list && count >= 2) {``//  完美匹配！同时满足 VTable 合法 + 链表结构合法 + 数量合理``g_ClassLinkerOffset = cl_off;``g_ListOffset = list_off;` `LOGD(``"✅ [锁定] 动态偏移计算完成!"``);``LOGD(``"    -> ClassLinker Offset: 0x%x"``, g_ClassLinkerOffset);``LOGD(``"    -> List Offset: 0x%x"``, g_ListOffset);``LOGD(``"    -> 当前 Loader 数量: %d"``, count);``return``;``// 找到即停止``}``}``}``}``LOGE(``"[-] 扫描失败，未找到符合特征的结构"``);``}` `// =============================================================``// 3. 对外接口：获取 ClassLoader 数量``// =============================================================` `int` `getClassLoaderCount(JNIEnv* env) {` `// 1. 获取 Runtime 实例 (JavaVM + sizeof(void*))``JavaVM* vm = nullptr;``if` `(env->GetJavaVM(&vm) != JNI_OK \|\| !vm)``return` `-1;``void``* runtime = *((``void``**)((``uintptr_t``)vm +``sizeof``(``void``*)));``if` `(!IsAddressReadable(runtime))``return` `-1;` `// 2. 如果偏移未初始化，执行一次扫描``if` `(g_ClassLinkerOffset == -1 \|\| g_ListOffset == -1) {``ScanOffsets(runtime);``// 如果扫完还是 -1，说明失败``if` `(g_ClassLinkerOffset == -1)``return` `-1;``}` `// 3. 极速读取模式 (直接利用偏移)``void``* class_linker = *(``void``**)((``uintptr_t``)runtime + g_ClassLinkerOffset);``if` `(!IsAddressReadable(class_linker))``return` `-1;` `ListNode* head = (ListNode*)((``uintptr_t``)class_linker + g_ListOffset);``if` `(!IsAddressReadable(head))``return` `-1;` `// 4. 遍历链表``// 再次校验链表完整性，防止运行时结构变化``if` `(!IsAddressReadable(head->next) \|\| head->next->prev != head) {``LOGE(``"[-] 链表结构在运行时损坏，重置偏移"``);``g_ClassLinkerOffset = -1;``// 触发下次重新扫描``return` `-1;``}` `int` `count = 0;``ListNode* curr = head->next;``while` `(curr != head) {``count++;``if` `(count > 500)``break``;``// 防死循环` `curr = curr->next;``}` `return` `count;``}`  `}`   `//调用部分``int` `count = anti_ClassLinker::getClassLoaderCount(env);` `if` `(count > 0) {``// 简单的判定逻辑打印``if` `(count > 10) {``LOGE(``"???????????? 异常! 发现 %d 个 ClassLoader (正常值 5)"``, count);``}``else` `{``LOGD(``"✅ 正常. 发现 %d 个 ClassLoader"``, count);``}``}``else` `{``LOGE(``"[-] 获取失败"``);``}` `return` `count;` |
|-|-|

---

## 稳定性评估与风险控制：在“暴力”中寻找平衡

必须承认，**内存盲扫（Memory Scanning）** 即使在 PC 端反作弊中也属于激进（Aggressive）手段，在碎片化极度严重的 Android 生态中更是如此。虽然我在理论层面构建了多重防护，但面对魔改的 ROM 和千奇百怪的设备，**我保持极度谨慎的态度，反正我的SDK目前不敢上线使用哈哈哈**。

### 1. 理论层面的“三道护盾”

为了将 Crash 风险降至最低，我在代码实现上极其克制：

- **系统级护盾 (**：这是最核心的安全机制。在对任何指针进行解引用（Dereference）之前，强制调用 mincore 系统检测该内存页是否映射在物理内存中。这从根本上阻断了 99% 因访问野指针或非法地址导致的 SIGSEGV 崩溃。
- **零侵入（Read-Only）**：全程仅进行“读取”操作，绝不尝试写入或修改任何内存数据，确保不会破坏 ART 虚拟机的内部状态。
- **去符号化**：完全移除对 xdl、dlsym 或私有系统库的依赖，规避了 Android 7.0+ 命名空间隔离带来的兼容性崩坏，也减少了因系统库版本差异导致的符号查找失败。

### 2. 现实世界的挑战（Risk Warning）

尽管有上述防护，但 **“全量上线”仍需三思**。由于我们采用了暴力枚举（从 Runtime 指针偏移 0 扫到 0x500）的方式，以下风险客观存在：

- **OEM 厂商魔改**：部分深度定制的 ROM（如某些游戏手机或车机系统）可能大幅修改了 Runtime 或 ClassLinker 的内存布局，导致特征扫描误判，虽然不会崩，但可能导致**检测失效**（返回 -1）。
- **并发竞争（Race Condition）**：在遍历链表时，尽管有 mincore 保护，但理论上存在极低概率的“Time-of-Check to Time-of-Use”风险，即在检测可读和实际读取的微小时间窗内，内存页被系统回收（虽然在主线程或加锁环境下极少发生）。
- **性能抖动**：在 App 启动瞬间进行内存扫描，虽然耗时通常在毫秒级，但在某些低端机型上可能会产生极其微弱的 CPU 峰值。

-

---

## 为什么 Shamiko 无法隐藏？

Shamiko 的隐藏原理主要是 Hook 系统查询接口（如隐藏文件、隐藏 Maps 条目）。

但是，本方案**直接读取的是堆内存中的 C++ 对象**。

- 攻击者无法 Hook CPU 的内存加载指令（LDR）。
- 攻击者无法在不破坏 GC 的前提下修改 ART 内部链表结构。
- **除非攻击者针对本 App 的检测函数进行专门的逆向和 Inline Hook**（成本极高），否则在通用隐藏层面，这是一个**无解的死局**。

## 总结

反作弊与作弊的对抗螺旋上升。当 API 层的 Hook 已经泛滥时，下沉到虚拟机内存布局层面进行**“降维打击”**，往往能收到奇效。

通过**动态计算偏移 + 内存特征校验**，我们实现了一个无需权限、无需符号、难以隐藏的通用检测方案。只要 ART 虚拟机还是用 C++ 写的，只要 GC 机制还在运行，这套逻辑就依然有效。

**额外说明：只在魅族21（安卓14）Google Pixel 7（安卓13 ）Root 环境:  Magisk 测试过   市面上这么多设备百分百存在误检测 只是给大家提供一个思路**

**如追求检测稳定性 请看我另一篇文章****[揭秘某企业级加固的 LSPosed 检测新姿势](https://bbs.kanxue.com/thread-289531.htm)**

(注：本文仅供安全研究与技术交流，请勿用于恶意用途)

---

# 回复

## 回复 by fjqisba (#2)

*2025-12-25 16:41*

111

## 回复 by wx_插曲 (#3)

*2025-12-25 16:46*

111

## 回复 by 希梦☆奈何 (#4)

*2025-12-25 16:48*

学习

## 回复 by 猫子 (#5)

*2025-12-25 19:36*

感谢分享

## 回复 by mb_dcjxxhsk (#6)

*2025-12-25 19:43*

666

## 回复 by mb_tewbhakr (#7)

*2025-12-25 19:57*

看看

## 回复 by hanhaochi (#8)

*2025-12-25 20:47*

打工人何苦为难打工人

## 回复 by 莱茵 (#9)

*2025-12-25 20:53*

感谢

## 回复 by mb_hpnnkjnq (#10)

*2025-12-25 21:09*

学习

## 回复 by Ascend_202904 (#11)

*2025-12-25 22:15*

666666666666666

## 回复 by mb_hcadvceu (#12)

*2025-12-25 22:55*

谢谢分享

## 回复 by mb_mlyojneh (#13)

*2025-12-25 23:39*

111

## 回复 by 恋一世的爱 (#14)

*2025-12-25 23:51*

看看

## 回复 by mb_ldbucrik (#15)

*2025-12-26 00:00*

感谢分享

## 回复 by 带带木木 (#16)

*2025-12-26 03:16*

12321312

## 回复 by 带带木木 (#17)

*2025-12-26 03:24*

请问如果使用了magisk的隐藏root，还能检测出来magisk吗

## 回复 by 曰你 (#18)

*2025-12-26 07:31*

![image](https://bbs.kanxue.com/view/img/face/002.gif)

## 回复 by fei3ei (#19)

*2025-12-26 09:39*

学习

## 回复 by CCC_ (#20)

*2025-12-26 09:42*

学习

## 回复 by cobe (#21)

*2025-12-26 09:54*

666

## 回复 by Imxz (#22)

*2025-12-26 10:16*

tql

## 回复 by Circ1e (#23)

*2025-12-26 10:20*

666

## 回复 by Ankeys (#24)

*2025-12-26 10:24*

看看

## 回复 by KanXue_NG (#25)

*2025-12-26 10:25*

学习学习

## 回复 by fangliangz (#26)

*2025-12-26 10:27*

厉害????

## 回复 by mb_lizfxfno (#27)

*2025-12-26 10:33*

学习学习

## 回复 by 夜惜风雨 (#28)

*2025-12-26 10:42*

6666666

## 回复 by Kk一刀 (#29)

*2025-12-26 10:42*

1

## 回复 by StriveMario (#30)

*2025-12-26 10:50*

好文 但是AI味好浓啊哈哈

## 回复 by Thehepta (#31)

*2025-12-26 10:54*

11

## 回复 by mb_peeqldfc (#32)

*2025-12-26 11:02*

666

## 回复 by Thehepta (#33)

*2025-12-26 11:14*

感谢分享，你这个技术点确实很好，又学到了，但是你这个方向有点生不逢时了，目前xp属于老版本，基本就不谈了，lsp的话，检测他的方式太多了，就目前我研究的情况，有很多方案，比你这个更简单，更容易，更能直指核心本质。而你这个方案，难以对抗魔改，或者是注入式xp

## 回复 by apxar (#34)

*2025-12-26 11:19*

1

## 回复 by 肉蚌葱鸡 (#35)

*2025-12-26 11:42*

学习学习

## 回复 by baitongling (#36)

*2025-12-26 11:52*

66666

## 回复 by wangzehua (#37)

*2025-12-26 11:53*

学习了

## 回复 by 随风而行aa (#38)

*2025-12-26 11:53*

看看

## 回复 by 随风而行aa (#39)

*2025-12-26 11:56*

检测思路不错的，确实这类检测方案，线上的稳定性是一个需要重要关注的事情

## 回复 by 九黎 (#40)

*2025-12-26 11:58*

tpl

## 回复 by mb_xuxrtytf (#41)

*2025-12-26 12:59*

学习

## 回复 by mb_pmgifpme (#42)

*2025-12-26 13:57*

1

## 回复 by 世界美景 (#43)

*2025-12-26 14:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  Thehepta](https://bbs.kanxue.com/user-767217.htm)
>
>  感谢分享，你这个技术点确实很好，又学到了，但是你这个方向有点生不逢时了，目前xp属于老版本，基本就不谈了，lsp的话，检测他的方式太多了，就目前我研究的情况，有很多方案，比你这个更简单，更容易，更能直 ...
>
>

这个只是一种思路下的试验玩具  市面上各大安全厂商以及大厂的所有的lposed检测我基本都有

## 回复 by 嘎嘎真的很棒 (#44)

*2025-12-26 15:56*

学习学习

## 回复 by xianhuimin (#45)

*2025-12-26 16:12*

看看

## 回复 by Aar0n (#46)

*2025-12-26 16:27*

这种方法是否存在误判，在未使用lsp的真机上检测到了100+的classloader![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by 世界美景 (#47)

*2025-12-26 16:59*

>
> [Aar0n](https://bbs.kanxue.com/user-985355.htm)
>
>  这种方法是否存在误判，在未使用lsp的真机上检测到了100+的classloader[em_055]
>
>

肯定存在误判了  我只在自己的几台测试机测试过  各品牌ROM以及安卓版本的libart差异很大的

## 回复 by 世界美景 (#48)

*2025-12-26 17:00*

>
> [StriveMario](https://bbs.kanxue.com/user-773600.htm)
>
>  好文 但是AI味好浓啊哈哈
>
>

有了AI后 人都变懒了 ![image](https://bbs.kanxue.com/view/img/face/039.gif)

## 回复 by mb_sqetvntx (#49)

*2025-12-26 17:13*

学习

## 回复 by SomeMx (#50)

*2025-12-26 18:17*

过来瞧瞧

## 回复 by k4y0z (#51)

*2025-12-26 19:03*

666

## 回复 by 啊你好哇123 (#52)

*2025-12-26 22:25*

学习学习

## 回复 by AMy_德友 (#53)

*2025-12-27 03:03*

嘟嘟嘟的

## 回复 by jyotidwi (#54)

*2025-12-27 14:41*

learn

## 回复 by wx_IT_717 (#55)

*2025-12-27 16:25*

没有了root，没有了乐趣

## 回复 by CCTV9 (#56)

*2025-12-27 18:56*

66666

## 回复 by virjar (#57)

*2025-12-27 21:32*

学习学习

## 回复 by pigsub (#58)

*2025-12-27 21:36*

666

## 回复 by wen55444 (#59)

*2025-12-27 22:24*

学习学习

## 回复 by 温泉划水鱼 (#60)

*2025-12-28 01:49*

666

## 回复 by 问心无愧 (#61)

*2025-12-28 08:37*

学习学习

## 回复 by mb_uwscobdl (#62)

*2025-12-28 10:23*

![image](https://bbs.kanxue.com/view/img/face/014.gif)

## 回复 by 我不是卷王 (#63)

*2025-12-28 10:23*

666

## 回复 by uni7corn (#64)

*2025-12-28 10:47*

感谢分享。

## 回复 by mb_vymbqugn (#65)

*2025-12-28 11:55*

学习学习

## 回复 by xDragonZ (#66)

*2025-12-28 12:02*

谢谢

## 回复 by huangjw (#67)

*2025-12-28 12:30*

火钳刘明

## 回复 by 寄予蓝y (#68)

*2025-12-28 12:42*

1

## 回复 by mb_fprfytok (#69)

*2025-12-28 12:43*

我们梆梆可以借鉴加入了

## 回复 by X66iaM (#70)

*2025-12-28 12:53*

你补药检测我的lsposed啊![image](https://bbs.kanxue.com/view/img/face/016.gif)

## 回复 by shutu (#71)

*2025-12-28 13:08*

？？？，

## 回复 by guijingwen (#72)

*2025-12-28 13:52*

666

## 回复 by mb_cbgtaveo (#73)

*2025-12-28 15:07*

666666666666666

## 回复 by torrent选手 (#74)

*2025-12-29 08:55*

学习一下

## 回复 by artake (#75)

*2025-12-29 09:16*

求放过

## 回复 by mb_xjdhrmck (#76)

*2025-12-29 10:41*

6666

## 回复 by 简单的简单 (#77)

*2025-12-29 10:50*

学习学习

## 回复 by 简单的简单 (#78)

*2025-12-29 10:51*

搬走搬走

## 回复 by rookie江 (#79)

*2025-12-29 10:56*

111

## 回复 by iamshy (#80)

*2025-12-29 13:33*

学习学习

## 回复 by wx_weggfkdk (#81)

*2025-12-29 13:54*

看看

## 回复 by ClPrada (#82)

*2025-12-29 13:59*

学习下

## 回复 by tjytjy (#83)

*2025-12-29 18:04*

学习学习

## 回复 by FindCall (#84)

*2025-12-29 19:33*

666

## 回复 by mb_ucbmgqsi (#85)

*2025-12-29 20:26*

大佬

## 回复 by dreameriii (#86)

*2025-12-29 20:32*

太牛逼了，学习一下

## 回复 by caydemlendi (#87)

*2025-12-30 06:43*

666

## 回复 by mb_pobqzscg (#88)

*2025-12-30 11:31*

666

## 回复 by 不具名的悲伤 (#89)

*2025-12-30 17:04*

6

## 回复 by 9527vv7 (#90)

*2025-12-30 19:04*

1

## 回复 by jdong (#91)

*2025-12-30 19:22*

学习学习

## 回复 by dædalus (#92)

*2025-12-30 22:10*

66

## 回复 by ldehua (#93)

*2025-12-31 13:58*

学习学习

## 回复 by mb_uvyukvot (#94)

*2025-12-31 18:02*

666

## 回复 by 寒号鸟二代 (#95)

*2025-12-31 19:53*

66666

## 回复 by mb_euhyowpw (#96)

*2025-12-31 22:26*

666

## 回复 by 飆汗吉米 (#97)

*2026-1-1 15:06*

666

## 回复 by REerr (#98)

*2026-1-1 18:31*

学习学习思路

## 回复 by Ford_ (#99)

*2026-1-2 21:44*

学习

## 回复 by pyth0nDev (#100)

*2026-1-2 22:25*

666

## 回复 by veluboii (#101)

*2026-1-3 14:56*

nice

## 回复 by 29o (#102)

*2026-1-3 15:04*

学习

## 回复 by git_66480p0-tato (#103)

*2026-1-5 10:18*

666

## 回复 by chenwitch (#104)

*2026-1-5 13:38*

666

## 回复 by Crack999 (#105)

*2026-1-5 13:54*

既生瑜何生亮

## 回复 by huangbof (#106)

*2026-1-5 14:35*

习学习

## 回复 by CheRevir (#107)

*2026-1-5 14:40*

6666

## 回复 by ugvnui (#108)

*2026-1-6 08:15*

学习学习

## 回复 by rookie江 (#109)

*2026-1-7 16:51*

那有什么好的过检测的方案

## 回复 by mb_syldwcdi (#110)

*2026-1-7 17:12*

学习学习

## 回复 by 易始 (#111)

*2026-1-7 19:31*

![image](https://bbs.kanxue.com/view/img/face/0100.gif)

## 回复 by 飞机上唱山歌 (#112)

*2026-1-8 15:30*

1

## 回复 by 孤梦拾遗 (#113)

*2026-1-8 16:32*

666666666

## 回复 by Old_Yuan (#114)

*2026-1-8 19:56*

看了下一些对classloader的调用，visitclassloaders是直接使用classlinker + imm1访问classloaders的，上层函数里访问classlinker其实是从artRuntimeInstance + imm2访问的。所以通过解析特定函数指令能够拿到这两个偏移，进而实现稳定访问。不过需要适配不同的Android版本

## 回复 by mb_jnmxfjku (#115)

*2026-1-9 16:51*

666

## 回复 by mb_yxskextg (#116)

*2026-1-13 14:56*

学习

## 回复 by GuL1ng (#117)

*2026-1-13 15:12*

xuexixuexi

## 回复 by mb_uxxdrffh (#118)

*2026-1-13 16:17*

6666

## 回复 by lookaside (#119)

*2026-1-13 16:50*

可能有误报，比如用了插件化框架的场景

## 回复 by lookaside (#120)

*2026-1-13 16:51*

还有比如动态加载的场景

## 回复 by mb_gmvlvzfn (#121)

*2026-1-14 02:42*

看看学习下

## 回复 by 妖友 (#122)

*2026-1-14 18:33*

看看

## 回复 by l140w4n9 (#123)

*2026-1-16 10:13*

66666

## 回复 by mb_rbaigqfb (#124)

*2026-1-16 13:12*

看看师傅分享

## 回复 by 4Chan (#125)

*2026-1-16 15:38*

学习了

## 回复 by ivy1 (#126)

*2026-1-16 16:49*

学习学习

## 回复 by asm_zhang (#127)

*2026-1-17 18:18*

666

## 回复 by mb_lfvhycml (#128)

*2026-1-18 20:47*

6

## 回复 by linix (#129)

*2026-1-18 20:56*

感谢分享

## 回复 by mb_rewimxhj (#130)

*2026-1-19 07:29*

看看

## 回复 by mb_auylfslb (#131)

*2026-1-19 10:09*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 大魔头 (#132)

*2026-1-19 10:13*

666

## 回复 by Dem0li (#133)

*2026-1-19 10:31*

1

## 回复 by 千谦 (#134)

*2026-1-19 23:01*

666

## 回复 by mb_armzgbpd (#135)

*2026-1-20 15:56*

666

## 回复 by 斗转南see雪 (#136)

*2026-1-23 10:21*

学习

## 回复 by leon_sec (#137)

*2026-1-23 10:34*

学习学习

## 回复 by Gryffindoss (#138)

*2026-1-23 10:41*

666

## 回复 by mb_bcfbphwt (#139)

*2026-1-23 16:55*

向大佬学习

## 回复 by comingundone (#140)

*2026-1-26 10:44*

1

## 回复 by mb_anbthlub (#141)

*2026-1-29 13:42*

111

## 回复 by mb_mrgbywba (#142)

*2026-2-2 03:16*

学习

## 回复 by tcc0lin (#143)

*2026-2-2 16:05*

谢谢分享

## 回复 by mb_fnxpmwzu (#144)

*2026-2-2 16:18*

学习

## 回复 by zzw_xjx (#145)

*2026-2-2 20:20*

学习学习

## 回复 by 寻梦之璐 (#146)

*2026-2-2 22:34*

111

## 回复 by Zepp7289 (#147)

*2026-2-2 23:28*

打工人何苦为难打工人

## 回复 by wx_kx24508 (#148)

*2026-2-3 16:57*

1111

## 回复 by wonhurry (#149)

*2026-2-3 17:08*

先mark再学习

## 回复 by AYHMO (#150)

*2026-2-3 21:54*

6666

## 回复 by buluo533 (#151)

*2026-2-3 22:24*

学习

## 回复 by 无视红绿灯 (#152)

*2026-2-4 09:06*

6666

## 回复 by mb_nxfmrrll (#153)

*2026-2-4 14:07*

学习

## 回复 by wx_郑泽科 (#154)

*2026-2-6 10:08*

6666

## 回复 by 章余割 (#155)

*2026-2-6 15:46*

666

## 回复 by xinhu (#156)

*2026-2-6 17:42*

666

## 回复 by mb_mykwpyev (#157)

*2026-2-8 01:46*

看看

## 回复 by kylinokok (#158)

*2026-2-9 10:52*

学习学习

## 回复 by wx_微笑_280 (#159)

*2026-2-10 14:00*

1

## 回复 by 小宏快跑 (#160)

*2026-2-10 16:48*

学习

## 回复 by 一只鸭子 (#161)

*2026-2-10 19:33*

学习

## 回复 by didiid (#162)

*2026-2-12 14:55*

666

## 回复 by mb_dwksysag (#163)

*2026-2-12 21:23*

11

## 回复 by mb_hezlzfil (#164)

*2026-2-13 09:44*

学习

## 回复 by 毛毛毛毛虫 (#165)

*2026-2-13 20:06*

学习一下

## 回复 by 筹码 (#166)

*2026-2-15 18:03*

看看

## 回复 by Ace_Heng (#167)

*2026-2-15 18:19*

看看

## 回复 by mb_vfmuxabf (#168)

*2026-2-25 01:26*

看看

## 回复 by mb_lgbrcvmf (#169)

*2026-2-25 02:44*

666

## 回复 by 军哥i (#170)

*2026-2-25 14:34*

学习一下

## 回复 by 枯藤舍 (#171)

*2026-2-25 14:42*

11

## 回复 by mb_irhdtnzm (#172)

*2026-3-2 13:05*

1

## 回复 by mb_hkqnanbs (#173)

*2026-3-2 15:00*

666

## 回复 by Am1re (#174)

*2026-3-2 15:03*

学习

## 回复 by Am1re (#175)

*2026-3-2 15:03*

学习

## 回复 by Am1re (#176)

*2026-3-2 15:03*

学习

## 回复 by mb_sqetvntx (#177)

*2026-3-3 15:08*

xx

## 回复 by wx_茄子豆角伴芹菜 (#178)

*2026-3-3 15:15*

学习学习

## 回复 by puppet_w (#179)

*2026-3-3 15:25*

学习

## 回复 by mb_resywadw (#180)

*2026-3-3 18:47*

学习学习

## 回复 by tcc0lin (#181)

*2026-3-3 20:17*

>
> [Aar0n](https://bbs.kanxue.com/user-985355.htm)
>
>  这种方法是否存在误判，在未使用lsp的真机上检测到了100+的classloader[em_055]
>
>

确实存在误判的情况，实际测试redmi note12r时，class_linker位置定位到了前0x20字节位置的MonitorList* monitor_list_;，可能是因为这个导致计算的cl个数达到100+，跳转偏移后正常情况也是小于10的

## 回复 by git_43131MobileResearcher (#182)

*2026-3-4 03:38*

Thanks!

## 回复 by wx_lll_652 (#183)

*2026-3-4 03:42*

学习学习

## 回复 by mb_lbplalyw (#184)

*2026-3-4 12:30*

感谢分享，学习一下

## 回复 by Steve2280 (#185)

*2026-3-4 12:42*

学习学习

## 回复 by mb_qimctavn (#186)

*2026-3-4 12:50*

6

## 回复 by Ayuer (#187)

*2026-3-4 15:41*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by mb_gkazhfpu (#188)

*2026-3-5 22:41*

666

## 回复 by qkcoder (#189)

*2026-3-8 02:26*

6666

## 回复 by mb_thtlsvqy (#190)

*2026-3-8 13:06*

学习学习

## 回复 by mb_pnyyaazf (#191)

*2026-3-8 15:30*

1

## 回复 by mb_fyfuomwx (#192)

*2026-3-9 01:58*

6

## 回复 by mb_blhyvqfj (#193)

*2026-3-9 12:23*

学习

## 回复 by 秃顶 (#194)

*2026-3-9 17:03*

赞

## 回复 by mb_ndotvqat (#195)

*2026-3-11 15:56*

666

## 回复 by mJqalJqN (#196)

*2026-3-11 16:49*

1

## 回复 by 刻骨柔情 (#197)

*2026-3-11 22:35*

111

## 回复 by mb_eaoluppm (#198)

*2026-3-12 07:53*

666

## 回复 by mb_zmjeaykk (#199)

*2026-3-13 03:26*

xuexi

## 回复 by mb_hcqpswwu (#200)

*2026-3-14 02:38*

看看

## 回复 by mb_lovhtcda (#201)

*2026-3-14 18:42*

markmark

## 回复 by mb_joablzkk (#202)

*2026-3-16 09:01*

1

## 回复 by wohowo (#203)

*2026-3-16 10:33*

1

## 回复 by FMNS (#204)

*2026-3-16 23:11*

6666

## 回复 by mb_cvtgkrbe (#205)

*2026-3-16 23:22*

666

## 回复 by mb_bmkfgrxv (#206)

*2026-3-17 16:58*

![image](https://bbs.kanxue.com/view/img/face/001.gif)学习学习

## 回复 by wx_听书人 (#207)

*2026-3-17 17:38*

1111

## 回复 by mb_eflgweyp (#208)

*2026-3-18 11:54*

厉害了

## 回复 by mb_4nrpVMxJ (#209)

*2026-3-18 15:00*

学习

## 回复 by XCicada (#210)

*2026-3-18 15:21*

666

## 回复 by git_372062272017501 (#211)

*2026-3-19 03:11*

学习

## 回复 by mb_kloqbidc (#212)

*2026-3-19 11:03*

1

## 回复 by mb_ghcouuzx (#213)

*2026-3-19 17:53*

看看看看

## 回复 by jamlops (#214)

*2026-3-20 00:24*

来了来了

## 回复 by mb_hhnxiwgr (#215)

*2026-3-20 23:59*

学习学习

## 回复 by wx_故事与酒 (#216)

*2026-3-23 01:13*

学习学习

## 回复 by 木槿any (#217)

*2026-3-23 18:53*

6666

## 回复 by mb_iqkkgktq (#218)

*2026-3-24 21:39*

学习一下

## 回复 by tonykros (#219)

*2026-3-24 23:35*

666

## 回复 by mb_ghcouuzx (#220)

*2026-3-25 00:11*

揭秘某企业级加固的 LSPosed 检测新姿势，这个文章没有啊，特别想看看呢

## 回复 by 世界美景 (#221)

*2026-3-25 10:07*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  mb_ghcouuzx](https://bbs.kanxue.com/user-1017226.htm)
>  揭秘某企业级加固的 LSPosed 检测新姿势，这个文章没有啊，特别想看看呢
>

版主给挪移到 会员专区了  大部分人没权限看不了。。

## 回复 by Zkeleven (#222)

*2026-3-25 16:45*

666666

## 回复 by shenzhigang (#223)

*2026-3-25 17:49*

看看

## 回复 by Xx_gg (#224)

*2026-3-25 17:53*

6666

## 回复 by Palonsong (#225)

*2026-3-26 19:36*

学习一下

## 回复 by 八嘎boy (#226)

*2026-3-26 20:21*

666

## 回复 by wx_岁月真好_475628 (#227)

*2026-3-27 08:55*

6666

## 回复 by 龙飞雪 (#228)

*2026-3-27 11:53*

学习了

## 回复 by tiger4777 (#229)

*2026-4-3 14:15*

学习学习

## 回复 by wx_妳还是不懂 (#230)

*2026-4-5 13:00*

非常感谢

## 回复 by A0x01 (#231)

*2026-4-5 14:13*

666

## 回复 by Dimole (#232)

*2026-4-6 12:53*

学习一下

## 回复 by 小迷糊ddd (#233)

*2026-4-7 09:15*

感谢分享，学习一下。

## 回复 by wx_^(oo)^ (#234)

*2026-4-13 03:32*

66666

## 回复 by iBa0 (#235)

*2026-4-13 09:32*

123

## 回复 by mb_egsgqdnl (#236)

*2026-4-15 16:04*

1111

## 回复 by mb_chjjqnap (#237)

*2026-4-24 21:54*

学习

## 回复 by mb_dqctdtly (#238)

*2026-4-25 19:55*

66666

## 回复 by lamboo (#239)

*2026-4-29 20:36*

66666

## 回复 by lamboo (#240)

*2026-4-29 20:36*

66666

## 回复 by 有的是钱啊 (#241)

*2026-4-30 11:02*

学习学习

## 回复 by 有的是钱啊 (#242)

*2026-4-30 11:03*

学习学习v吧v吧v吧![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by 纸片人 (#243)

*2026-4-30 11:06*

1

## 回复 by 特洛伊Troye (#244)

*2026-4-30 15:02*

学习一下

## 回复 by mb_eumnbkwy (#245)

*2026-5-1 20:30*

看看

## 回复 by ~时光荏苒 (#246)

*2026-5-6 20:44*

66666

## 回复 by mb_ssjlfpnk (#247)

*2026-5-7 10:20*

学习学习

## 回复 by mb_lzsjiukj (#248)

*2026-5-8 20:54*

666

## 回复 by mb_fdskejlh (#249)

*2026-5-16 21:11*

牛啊牛啊

## 回复 by 086Love (#250)

*2026-5-18 11:22*

学习

## 回复 by mb_czeiyidu (#251)

*2026-5-19 16:07*

![image](https://bbs.kanxue.com/view/img/face/001.gif) 学习学习

## 回复 by mb_enbuhisq (#252)

*2026-5-19 16:28*

66666666666

## 回复 by shuaiaimei (#253)

*2026-5-19 16:53*

看下隐藏

## 回复 by baichisi (#254)

*2026-5-19 17:01*

666

## 回复 by 葱葱葱 (#255)

*2026-5-19 17:22*

学习一下

## 回复 by wx_hubert_270063 (#256)

*2026-5-19 19:39*

学习

## 回复 by wx_！_336 (#257)

*2026-5-19 21:22*

111

## 回复 by 偶尔.c (#258)

*2026-5-31 00:20*

学习一下

## 回复 by mb_dovsgrdo (#259)

*2026-5-31 14:38*

>
> [带带木木](https://bbs.kanxue.com/user-957931.htm)
>  请问如果使用了magisk的隐藏root，还能检测出来magisk吗
>
>

他这是偏向于检测lsp而不是magisk本身

## 回复 by fuqiuluo73 (#260)

*2026-6-1 14:05*

111

## 回复 by mb_xasbwwii (#261)

*2026-6-3 13:43*

看看

## 回复 by mb_ezmrnfsu (#262)

*2026-6-6 14:46*

666

## 回复 by git_74197luban110 (#263)

*2026-6-8 08:55*

666

## 回复 by SInnon (#264)

*2026-6-8 16:33*

6666666

## 回复 by mb_sajaoega (#265)

*2026-6-14 17:31*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by Gamer_Lee6 (#266)

*2026-6-16 11:39*

学习

## 回复 by mb_qqihqaoo (#267)

*2026-6-16 12:54*

6666

## 回复 by 盖伦爸爸 (#268)

*2026-6-16 14:19*

学习学习

## 回复 by mb_bfghjvta (#269)

*2026-6-16 15:40*

学习学习

## 回复 by git_29595xiaozhimengmengda (#270)

*2026-6-16 16:26*

学习下

## 回复 by wx_小白_266 (#271)

*2026-6-17 10:40*

看看

## 回复 by mb_ewhhgcuy (#272)

*2026-6-18 01:59*

学习学习

## 回复 by 逆向小龙 (#273)

*2026-6-26 11:48*

1111

## 回复 by TheLuckyOne (#274)

*2026-6-27 20:14*

tql

## 回复 by haris4687 (#275)

*2026-6-27 20:46*

666

## 回复 by 祝今朝 (#276)

*2026-6-29 18:39*

666

## 回复 by mb_dswynejo (#277)

*2026-7-1 20:25*

学习一下

## 回复 by Arsylk (#278)

*2026-7-1 20:49*

Very cool

## 回复 by cantalou (#279)

*2026-7-10 11:57*

1

## 回复 by simpleness (#280)

*2026-7-16 19:35*

6

## 回复 by mb_tuvjxchk (#281)

*2026-7-18 01:05*

感谢你的积极参与，期待更多精彩内容！

## 回复 by 倔强石头 (#282)

*2026-7-28 10:49*

感谢分享

## 回复 by mr梁 (#283)

学习学习
