---
title: '[原创]初探Android Linker 动态库SO的加载流程（3）'
url: https://bbs.kanxue.com/thread-289306.htm
tid: 289306
author: Ayuer
date: '2025-12-02'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:00:02+08:00'
replies: 26
---

接着上篇（2），目前讲解了step 2，step 3，回到find_libraries方法中，继续分析。

## Step 4

下面是find_libraries的代码片段，我们先看注释。这部分挺容易的。

下面这段结合AI分析，得出的结论

先明确核心背景：Android Linker 支持 “命名空间（Namespace）” 机制，默认情况下，一个命名空间内的库只能访问本命名空间内的符号（隔离性）；而 `Global Group` 是 “打破隔离” 的特殊机制，加入该组的库，其符号会被所有命名空间共享。

目标就是**全局符号组（Global Group）构建** 让标记为 `DF_1_GLOBAL` 的库，其全局符号对全进程所有 “命名空间（Namespace）” 可见。

到这里，就是为了构建全局符号表，为后续的重定位和链接做准备。注释都写得很清楚了。

#### Step 4-1：强制为 LD_PRELOAD 库设置 DF_1_GLOBAL 标志

- **目的**：确保 `LD_PRELOAD` 预加载库的符号 “全局可见”。
- **逻辑解析**：
1. `LD_PRELOAD` 是用户 / 系统指定的 “优先加载库”（比如用于 hook、调试），其设计初衷就是要覆盖其他库的符号，因此必须强制加入 Global Group；
2. `si->get_dt_flags_1()`：获取库当前的动态段标志位（`DT_FLAGS_1`，ELF 动态段条目，存储扩展标志）；
3. `| DF_1_GLOBAL`：通过位或运算，强制设置 `DF_1_GLOBAL` 标志（不影响其他已有标志）；
4. `set_dt_flags_1()`：将修改后的标志位写回 `soinfo`。
- **核心结论**：预加载库默认全局可见，无论其自身是否编译时设置 `DF_1_GLOBAL`。

#### Step 4-2：筛选本次加载的 DF_1_GLOBAL 库

- **目的**：收集本次加载过程中（比如 `dlopen` 一个库时，连带加载的依赖库），本身带有 `DF_1_GLOBAL` 标志且 “未完成链接” 的库，作为 Global Group 的新成员。
- **关键条件解析**：
1. `!si->is_linked()`：筛选 “未完成链接” 的库。Linker 加载库的流程是 “先加载文件→再解析依赖→最后链接（符号绑定、重定位）”，这里确保只处理 “本次加载周期中新增的、还没完成链接的库”（避免重复处理已存在的全局库）；
2. `(si->get_dt_flags_1() & DF_1_GLOBAL) != 0`：筛选本身带有 `DF_1_GLOBAL` 标志的库（该标志通常是库编译时，通过链接器参数或属性设置的，比如系统库 `libc.so` 编译时就会带该标志）。
- **结果**：`new_global_group_members` 列表存储了 “本次加载的、需要加入全局组的新库”。

#### Step 4-3：将新全局库加入所有已链接的命名空间

- **目的**：让新加入 Global Group 的库，其符号对全进程所有命名空间可见（核心步骤）。
- **关键概念与逻辑解析**：
1. `si->get_primary_namespace()`：每个库都有一个 “主命名空间”（加载该库时所在的命名空间，比如 APP 加载的库默认在 APP 命名空间）；
2. `linked_ns`：进程中所有已 “链接完成” 的命名空间（比如系统命名空间、APP 命名空间、其他动态创建的命名空间）；
3. 条件 `si->get_primary_namespace() != linked_ns`：避免重复添加（库已在主命名空间中，无需再次加入）；
4. `linked_ns->add_soinfo(si)`：将该库加入目标命名空间的 “库列表”—— 命名空间会维护一个所有可见库的集合，后续该命名空间内的库解析符号时，会遍历这个集合；
5. `si->add_secondary_namespace(linked_ns)`：记录该库被 “附加” 到的次要命名空间 —— 用于后续库卸载、命名空间管理（比如知道该库被哪些命名空间引用，避免提前释放）。
- **核心效果**：比如系统库 `libc.so` 带有 `DF_1_GLOBAL` 标志，加载后会被加入所有命名空间。此时，无论哪个命名空间中的库（比如 APP 自己的库、第三方 SDK 库），解析 `printf`、`malloc` 等符号时，都能找到 `libc.so` 中的实现。

代码如下

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `// Step 4: Construct the global group. Note: DF_1_GLOBAL bit of a library is``// determined at step 3.``// Step 4: 构建 Global Group（与 symbol visibility 相关）` `// Step 4-1: DF_1_GLOBAL bit is force set for LD_PRELOADED libs because they``// must be added to the global group``/**``* 如果 A 是 Global Group 成员，B 在 link 时可以访问 A 的全局符号。``*/``if` `(ld_preloads != nullptr) {``for` `(``auto``&& si : *ld_preloads) {``si->set_dt_flags_1(si->get_dt_flags_1() \| DF_1_GLOBAL);``}``}` `// Step 4-2: Gather all DF_1_GLOBAL libs which were newly loaded during this``// run. These will be the new member of the global group``// Step 4-2: 将本次加载的库中带 DF_1_GLOBAL 标记的筛出来``soinfo_list_t new_global_group_members;``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``if` `(!si->is_linked() && (si->get_dt_flags_1() & DF_1_GLOBAL) != 0) {``new_global_group_members.push_back(si);``}``}` `// Step 4-3: Add the new global group members to all the linked namespaces``/**``* Step 4-3: 把这些“new global members”加入所有其它 namespace``* 这些库的符号对 全进程所有 namespace 可见``* 典型例子：libc.so, libm.so, libdl.so``*/``for` `(``auto` `si : new_global_group_members) {``for` `(``auto` `linked_ns : *namespaces) {``if` `(si->get_primary_namespace() != linked_ns) {``linked_ns->add_soinfo(si);``si->add_secondary_namespace(linked_ns);``}``}``}` |
|-|-|

### 总结

至此，分析完成，AI总结得出。核心是 **“构建全局符号共享机制”**

1. 强制预加载库（LD_PRELOAD）成为全局库；
2. 筛选本次加载的、自带 `DF_1_GLOBAL` 标志的新库；
3. 将这些新全局库 “同步” 到所有已链接的命名空间，实现符号全局可见。

本质是平衡 “命名空间的隔离性” 和 “核心库的共享性”—— 大部分库默认隔离，只有标记为 `DF_1_GLOBAL` 的库（系统核心库、预加载库）才全局共享，既保证了进程稳定性，又满足了通用符号的共享需求。

## Step 5

接下来分析，Step 5的代码片段。在讲解这段代码之前，我们需要知道，每个so都有自己的**Primary Namespace** 主命名空，存在`soinfo` 结构体当中。然后可以有都多个次命名空间。Linker 的命名空间（Namespace）核心是 “隔离性”—— 每个命名空间有自己的 **库搜索路径**（比如 `app` 命名空间搜索 `/data/app/xxx/lib/`，`platform` 命名空间搜索 `/system/lib/`）和 **可见库集合**。

if (si->get_primary_namespace() != ns)满足这个条件才会进去分支

只处理“主命名空间 != 当前目标命名空间”的库（跨命名空间引用），就会递归调用find_libraries，去到so的主命名空间进行加载。举个例子：如果一个 so 是在其他 namespace 找到的，但它是我需要的依赖，那我必须在那个 namespace 再执行一遍依赖解析（find_libraries）。

对于soinfo* needed_by = task->get_needed_by();获取的是“谁需要我”，例如有一个依赖关系为libA -> libB，此时加载的B，get_needed_by获取到就是A，所以，在needed_by->get_primary_namespace()条件下，如果等于ns，这个ns指的是B的name space，所以如果相等的话，那就是A依赖B，所以对于此时的si（也就是libB）它的引用数要加1，跨域依赖的引用计数递增（防止误卸载）

至此，大概的流程就是如此，讲解完毕。

代码如下

| 1234567891011121314151617181920212223242526272829303132 | `// Step 5: link libraries that are not destined to this namespace.``// Do this by recursively calling find_libraries on the namespace where the lib``// was found during Step 1.``/**``* Step 5: 处理「跨 namespace 引用」的库（递归调用 find_libraries）``* 如果一个 so 是在其他 namespace 找到的，但它是我需要的依赖，那我必须在那个 namespace 再执行一遍依赖解析（find_libraries）。``* 关键知识点：为什么需要递归 find_libraries？``* 不同 namespace 有不同 search path``* namespace app {/data/app/.../lib/}``* namespace platform {/system/lib/}``*/``for` `(``auto``&& task : load_tasks) {``soinfo* si = task->get_soinfo();``if` `(si->get_primary_namespace() != ns) {``const` `char``* name = task->get_name();``if` `(find_libraries(si->get_primary_namespace(), task->get_needed_by(), &name, 1,``nullptr``/* soinfos */``, nullptr``/* ld_preloads */``, 0``/* ld_preload_count */``,``rtld_flags, nullptr``/* extinfo */``,``false` `/* add_as_children */``,``false` `/* search_linked_namespaces */``, readers_map, namespaces)) {``// If this lib is directly needed by one of the libs in this namespace,``// then increment the count``// needed_by 是“依赖我”的库 A->B``soinfo* needed_by = task->get_needed_by();``if` `(needed_by != nullptr && needed_by->get_primary_namespace() == ns && si->is_linked()) {``// 如果 si 是被 ns namespace 中的库引用的，那么它的引用计数要 +1。这是防止卸载时错误卸载跨 namespace 依赖。``si->increment_ref_count();``}``}``else` `{``return` `false``;``}``}``}` |
|-|-|

### 总结

结合AI分析，得出结论

核心结论：

1. 每个加载成功的 `.so` 都有 **唯一的主命名空间**，存储在 `soinfo` 中；
2. 主命名空间由 “第一次加载该库的发起者命名空间” 决定，一旦确定永不改变；
3. 间接加载（依赖）的库，默认继承父库的主命名空间，但若库已在其他命名空间加载，则复用原主命名空间；
4. 主命名空间是 Linker 实现依赖解析、隔离性、生命周期管理的核心依据。

## Step 6

这里开始讲解最后一步，前面经历了这么长的流程，终于到了，重定位和链接的阶段，实际上这部分是核心重点，也是难点。我们结合《程序员的自我修养——链接、装载与库》这本书来，理解一些关键流程。

| 123456789101112131415161718192021222324252627282930313233343536 | `// Step 6: link libraries in this namespace``// Step 6: 真正执行 link / relocation``soinfo_list_t local_group;``walk_dependencies_tree(``(start_with != nullptr && add_as_cdhildren) ? &start_with : soinfos,``(start_with != nullptr && add_as_children) ? 1 : soinfos_count,``[&] (soinfo* si) {``if` `(ns->is_accessible(si)) {``local_group.push_back(si);``return` `kWalkContinue;``}``else` `{``return` `kWalkSkip;``}``});` `soinfo_list_t global_group = ns->get_global_group();``bool` `linked = local_group.visit([&](soinfo* si) {``if` `(!si->is_linked()) {``if` `(!si->link_image(global_group, local_group, extinfo) \|\|``!get_cfi_shadow()->AfterLoad(si, solist_get_head())) {``return` `false``;``}``}` `return` `true``;``});` `if` `(linked) {``local_group.for_each([](soinfo* si) {``if` `(!si->is_linked()) {``si->set_linked();``}``});` `failure_guard.Disable();``}` |
|-|-|

先看walk_dependencies_tree方法，我们看一下注解的内容，在一开始第一次调用的时候，传递进来的root_soinfos，只有我们要加载的目标so一个，root_soinfos_size = 1

所以visit_list当中只有目标so，这时候，出栈visit_list，然后获取目标so，调用action，为前面传递的闭包函数，调用ns（当前命名空间）的is_accessible，来判断是否有权限访问这个 so  。is_accessible方法后面介绍。

然后到了下面的代码

| 123 | `si->get_children().for_each([&](soinfo* child) {``visit_list.push_back(child);``});` |
|-|-|

获取到need库，也就是依赖的so，方法结束后visited类型是SoinfoLinkedList就是深度优先遍历得到的结果。传入的闭包函数。local_group最后的结果就是深度优先遍历得到的结果。

举个例子：A.so 被 dlopen()

A.so → B.so → D.so

A.so → C.so → D.so

local_group =  [A.so, B.so, D.so, C.so]    // 顺序视 DFS 而定，但保证拓扑合法

| 12345678 | `[&] (soinfo* si) {``if` `(ns->is_accessible(si)) {``local_group.push_back(si);``return` `kWalkContinue;``}``else` `{``return` `kWalkSkip;``}``})` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041 | `// This function walks down the tree of soinfo dependencies``// in breadth-first order and``//   * calls action(soinfo* si) for each node, and``//   * terminates walk if action returns kWalkStop``//   * skips children of the node if action``//     return kWalkSkip``//``// walk_dependencies_tree returns false if walk was terminated``// by the action and true otherwise.``template``<``typename` `F>``static` `bool` `walk_dependencies_tree(soinfo* root_soinfos[],``size_t` `root_soinfos_size, F action) {``SoinfoLinkedList visit_list;``SoinfoLinkedList visited;` `for` `(``size_t` `i = 0; i < root_soinfos_size; ++i) {``visit_list.push_back(root_soinfos[i]);``}` `soinfo* si;``while` `((si = visit_list.pop_front()) != nullptr) {``if` `(visited.contains(si)) {``continue``;``}` `walk_action_result_t result = action(si);` `if` `(result == kWalkStop) {``return` `false``;``}` `visited.push_back(si);` `if` `(result != kWalkSkip) {``si->get_children().for_each([&](soinfo* child) {``visit_list.push_back(child);``});``}``}` `return` `true``;``}` |
|-|-|

find_libraries方法，继续往下看，主库所在 namespace 的 preloaded 全局符号库，global_group 就是前面添加到，在上一篇文章（2）中的step 4，linked_ns->add_soinfo(si);local_group.visit：逐个 link 每个 so，判断条件是如果so还没有link就会调用link_image，开始进行链接。

| 12345678910111213141516171819202122232425262728293031 | `/**``* 主库所在 namespace 的 preloaded 全局符号库``* global_group 就是前面添加到，step 4中，linked_ns->add_soinfo(si);``* local_group.visit：逐个 link 每个 so，判断条件是如果so还没有link``* 就会调用link_image``*/``soinfo_list_t global_group = ns->get_global_group();``bool` `linked = local_group.visit([&](soinfo* si) {``if` `(!si->is_linked()) {``if` `(!si->link_image(global_group, local_group, extinfo) \|\|``!get_cfi_shadow()->AfterLoad(si, solist_get_head())) {``return` `false``;``}``}` `return` `true``;``});` `/**``* 链接成功``* local_group全部设置成set_linked，已经链接状态``*/``if` `(linked) {``local_group.for_each([](soinfo* si) {``if` `(!si->is_linked()) {``si->set_linked();``}``});` `failure_guard.Disable();``}` |
|-|-|

接下来我们重点查看link_image方法，动态链接，是如何做的。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146 | `bool` `soinfo::link_image(``const` `soinfo_list_t& global_group,``const` `soinfo_list_t& local_group,``const` `android_dlextinfo* extinfo) {` `local_group_root_ = local_group.front();``if` `(local_group_root_ == nullptr) {``local_group_root_ =``this``;``}` `if` `((flags_ & FLAG_LINKER) == 0 && local_group_root_ ==``this``) {``target_sdk_version_ = get_application_target_sdk_version();``}` `VersionTracker version_tracker;` `if` `(!version_tracker.init(``this``)) {``return` `false``;``}` `#``if` `!defined(__LP64__)``if` `(has_text_relocations) {``// Fail if app is targeting M or above.``if` `(get_application_target_sdk_version() >= __ANDROID_API_M__) {``DL_ERR_AND_LOG(``"\"%s\" has text relocations (https://android.googlesource.com/platform/"``"bionic/+/master/android-changes-for-ndk-developers.md#Text-Relocations-"``"Enforced-for-API-level-23)"``, get_realpath());``return` `false``;``}``// Make segments writable to allow text relocations to work properly. We will later call``// phdr_table_protect_segments() after all of them are applied.``DL_WARN(``"\"%s\" has text relocations (https://android.googlesource.com/platform/"``"bionic/+/master/android-changes-for-ndk-developers.md#Text-Relocations-Enforced-"``"for-API-level-23)"``, get_realpath());``add_dlwarning(get_realpath(),``"text relocations"``);``if` `(phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif` `if` `(android_relocs_ != nullptr) {``// check signature``if` `(android_relocs_size_ > 3 &&``android_relocs_[0] ==``'A'` `&&``android_relocs_[1] ==``'P'` `&&``android_relocs_[2] ==``'S'` `&&``android_relocs_[3] ==``'2'``) {``DEBUG(``"[ android relocating %s ]"``, get_realpath());` `bool` `relocated =``false``;``const` `uint8_t* packed_relocs = android_relocs_ + 4;``const` `size_t` `packed_relocs_size = android_relocs_size_ - 4;` `relocated = relocate(``version_tracker,``packed_reloc_iterator<sleb128_decoder>(``sleb128_decoder(packed_relocs, packed_relocs_size)),``global_group, local_group);` `if` `(!relocated) {``return` `false``;``}``}``else` `{``DL_ERR(``"bad android relocation header."``);``return` `false``;``}``}` `#``if` `defined(USE_RELA)``if` `(rela_ != nullptr) {``DEBUG(``"[ relocating %s ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(rela_, rela_count_), global_group, local_group)) {``return` `false``;``}``}``if` `(plt_rela_ != nullptr) {``DEBUG(``"[ relocating %s plt ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(plt_rela_, plt_rela_count_), global_group, local_group)) {``return` `false``;``}``}``#``else``if` `(rel_ != nullptr) {``DEBUG(``"[ relocating %s ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(rel_, rel_count_), global_group, local_group)) {``return` `false``;``}``}``if` `(plt_rel_ != nullptr) {``DEBUG(``"[ relocating %s plt ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(plt_rel_, plt_rel_count_), global_group, local_group)) {``return` `false``;``}``}``#endif` `#if defined(__mips__)``if` `(!mips_relocate_got(version_tracker, global_group, local_group)) {``return` `false``;``}``#endif` `DEBUG(``"[ finished linking %s ]"``, get_realpath());` `#if !defined(__LP64__)``if` `(has_text_relocations) {``// All relocations are done, we can protect our segments back to read-only.``if` `(phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't protect segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif` `// We can also turn on GNU RELRO protection if we're not linking the dynamic linker``// itself --- it can't make system calls yet, and will have to call protect_relro later.``if` `(!is_linker() && !protect_relro()) {``return` `false``;``}` `/* Handle serializing/sharing the RELRO segment */``if` `(extinfo && (extinfo->flags & ANDROID_DLEXT_WRITE_RELRO)) {``if` `(phdr_table_serialize_gnu_relro(phdr, phnum, load_bias,``extinfo->relro_fd) < 0) {``DL_ERR(``"failed serializing GNU RELRO section for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``else` `if` `(extinfo && (extinfo->flags & ANDROID_DLEXT_USE_RELRO)) {``if` `(phdr_table_map_gnu_relro(phdr, phnum, load_bias,``extinfo->relro_fd) < 0) {``DL_ERR(``"failed mapping GNU RELRO section for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}` `notify_gdb_of_load(``this``);``return` `true``;``}` |
|-|-|

条件编译分支中!defined(__LP64__)意思是，**32 位架构**才会成立，这里贴出了代码，作为了解一下，我们主要看`**AArch64**`，分析64位叫架构。

if (has_text_relocations) 否判断是否有可重定位rel.text段，这里so中肯定有的可重定位的text section，进来分支查看，调用了phdr_table_unprotect_segments

| 1234567891011121314151617181920212223 | `if` `(has_text_relocations) {``// Fail if app is targeting M or above.``if` `(get_application_target_sdk_version() >= __ANDROID_API_M__) {``DL_ERR_AND_LOG(``"\"%s\" has text relocations (https://android.googlesource.com/platform/"``"bionic/+/master/android-changes-for-ndk-developers.md#Text-Relocations-"``"Enforced-for-API-level-23)"``, get_realpath());``return` `false``;``}``// Make segments writable to allow text relocations to work properly. We will later call``// phdr_table_protect_segments() after all of them are applied.``DL_WARN(``"\"%s\" has text relocations (https://android.googlesource.com/platform/"``"bionic/+/master/android-changes-for-ndk-developers.md#Text-Relocations-Enforced-"``"for-API-level-23)"``, get_realpath());``add_dlwarning(get_realpath(),``"text relocations"``);``/**``* 解除内存保护权限，unprotect``*/``if` `(phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}` |
|-|-|

继续分析phdr_table_unprotect_segments做了，什么，代码的实现在linker_phdr.cpp中，我们看看注释的内容说了些什么。

/*将内存中所有加载段的保护更改为可写。

*这在执行重新定位之前很有用。一旦完成，你

*必须调用phdr_table_protect_segments来恢复原始状态

*所有分段上的保护标志。

*

*请注意，一些可写段也可以转换其内容

*通过调用phdr_table_protect_gnu_relro将其设置为只读。这不是

*在这里表演。

*

*输入：

*phdr_table->程序头表

*phdr_count->表中的条目数

*load_bias->负载偏差

*返回：

*0表示错误，-1表示失败（错误代码为errno）。

*/

| 1234567891011121314151617181920 | `/* Change the protection of all loaded segments in memory to writable.``* This is useful before performing relocations. Once completed, you``* will have to call phdr_table_protect_segments to restore the original``* protection flags on all segments.``*``* Note that some writable segments can also have their content turned``* to read-only by calling phdr_table_protect_gnu_relro. This is no``* performed here.``*``* Input:``*   phdr_table  -> program header table``*   phdr_count  -> number of entries in tables``*   load_bias   -> load bias``* Return:``*   0 on error, -1 on failure (error code in errno).``*/``int` `phdr_table_unprotect_segments(``const` `ElfW(Phdr)* phdr_table,``size_t` `phdr_count, ElfW(Addr) load_bias) {``return` `_phdr_table_set_load_prot(phdr_table, phdr_count, load_bias, PROT_WRITE);``}` |
|-|-|

继续进入_phdr_table_set_load_prot

| 1234567891011121314151617181920212223242526272829303132 | `/* Used internally. Used to set the protection bits of all loaded segments``* with optional extra flags (i.e. really PROT_WRITE). Used by``* phdr_table_protect_segments and phdr_table_unprotect_segments.``*/``static` `int` `_phdr_table_set_load_prot(``const` `ElfW(Phdr)* phdr_table,``size_t` `phdr_count,``ElfW(Addr) load_bias,``int` `extra_prot_flags) {``const` `ElfW(Phdr)* phdr = phdr_table;``const` `ElfW(Phdr)* phdr_limit = phdr + phdr_count;` `for` `(; phdr < phdr_limit; phdr++) {``if` `(phdr->p_type != PT_LOAD \|\| (phdr->p_flags & PF_W) != 0) {``continue``;``}` `ElfW(Addr) seg_page_start = PAGE_START(phdr->p_vaddr) + load_bias;``ElfW(Addr) seg_page_end   = PAGE_END(phdr->p_vaddr + phdr->p_memsz) + load_bias;` `int` `prot = PFLAGS_TO_PROT(phdr->p_flags);``if` `((extra_prot_flags & PROT_WRITE) != 0) {``// make sure we're never simultaneously writable / executable``prot &= ~PROT_EXEC;``}` `int` `ret = mprotect(``reinterpret_cast``<``void``*>(seg_page_start),``seg_page_end - seg_page_start,``prot \| extra_prot_flags);``if` `(ret < 0) {``return` `-1;``}``}``return` `0;``}` |
|-|-|

遍历程序头表，找到p_type为PT_LOAD，然后设置添加权限

extra_prot_flags传进来的是PROT_WRITE，先从 ELF 程序头（`phdr`）提取编译时定义的基础权限，再通过 `extra_prot_flags` 施加安全限制（禁止 “同时可写可执行”），最终确定内存映射时的权限（`prot` 参数将传给 `mmap` 系统调用），这个操作就是为了，解除内存保护，然后进行text重定位。到这里，

---

回到link_image方法，后面的***__LP32__***都将跳过，不讲解，往下分析，结合AI分析android_relocs_ != nullptr的时候，该分支的作用。

普通 ELF 重定位表 `.rel.dyn` 或 `.rela.dyn` 较大，例如每个 entry 在 arm64 可能 24 字节。

而 Android 中大量 APK embedded so 非常多 → 增加 APK 体积 + 加载更慢。

为解决：

Google 定义了一个 Android 专用的**压缩重定位格式 APS2**，可把重定位表压缩 50%～80%。

源码逻辑逐行解释

if (android_relocs_ != nullptr) {

so 里如果存在 `DT_ANDROID_RELSZ` 和 `DT_ANDROID_REL`（或 RELA 版本），则 android_relocs_ 非空。

---

这里我们不关心，so 里如果存在 `DT_ANDROID_RELSZ` 和 `DT_ANDROID_REL`（或 RELA 版本），则 android_relocs_ 非空。我们加载的普通so一般都会存在rela的。这里了解一下即可。

| 123456789101112131415161718192021222324252627 | `if` `(android_relocs_ != nullptr) {``// check signature``if` `(android_relocs_size_ > 3 &&``android_relocs_[0] ==``'A'` `&&``android_relocs_[1] ==``'P'` `&&``android_relocs_[2] ==``'S'` `&&``android_relocs_[3] ==``'2'``) {``DEBUG(``"[ android relocating %s ]"``, get_realpath());` `bool` `relocated =``false``;``const` `uint8_t* packed_relocs = android_relocs_ + 4;``const` `size_t` `packed_relocs_size = android_relocs_size_ - 4;` `relocated = relocate(``version_tracker,``packed_reloc_iterator<sleb128_decoder>(``sleb128_decoder(packed_relocs, packed_relocs_size)),``global_group, local_group);` `if` `(!relocated) {``return` `false``;``}``}``else` `{``DL_ERR(``"bad android relocation header."``);``return` `false``;``}``}` |
|-|-|

---

接下来分析继续往下分析，重定位表可以是两种格式之一：REL或RELA。我们关心USE_RELA和rela和rel类型的的重定位。这里我们只分析RELA类型的重定位。代码中是对rela_以及plt_rela_进行重定位，调用**relocate**方法，这个方法就是重定位的核心了。

直接来到#if defined(USE_RELA)，rela_以及plt_rela_这些都是在prelink_image之前初始化了的，可以看前面的文章中有举例。

| 12345678910111213141516171819202122232425262728293031 | `#if defined(USE_RELA)``if` `(rela_ != nullptr) {``DEBUG(``"[ relocating %s ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(rela_, rela_count_), global_group, local_group)) {``return` `false``;``}``}``if` `(plt_rela_ != nullptr) {``DEBUG(``"[ relocating %s plt ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(plt_rela_, plt_rela_count_), global_group, local_group)) {``return` `false``;``}``}``#else``if` `(rel_ != nullptr) {``DEBUG(``"[ relocating %s ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(rel_, rel_count_), global_group, local_group)) {``return` `false``;``}``}``if` `(plt_rel_ != nullptr) {``DEBUG(``"[ relocating %s plt ]"``, get_realpath());``if` `(!relocate(version_tracker,``plain_reloc_iterator(plt_rel_, plt_rel_count_), global_group, local_group)) {``return` `false``;``}``}``#endif` |
|-|-|

---

我们看一下，调用relocate之前，这个plain_reloc_iterator是一个类。传入了，rela的地址（本质是一个数组rel_array）和size。

| 123456789101112131415161718192021222324 | `class` `plain_reloc_iterator {``#if defined(USE_RELA)``typedef` `ElfW(Rela) rel_t;``#else``typedef` `ElfW(Rel) rel_t;``#endif``public``:``plain_reloc_iterator(rel_t* rel_array,``size_t` `count)``: begin_(rel_array), end_(begin_ + count), current_(begin_) {}` `bool` `has_next() {``return` `current_ < end_;``}` `rel_t* next() {``return` `current_++;``}``private``:``rel_t*``const` `begin_;``rel_t*``const` `end_;``rel_t* current_;` `DISALLOW_COPY_AND_ASSIGN(plain_reloc_iterator);``};` |
|-|-|

---

接下来我们分析relocate方法，看看做了什么，可以看到，是一个模板方法。方法中用了很多的条件编译#if#elif#endif，来区分不同的cpu架构，这不同的cpu都有不同的特性，重定位的的细节也会有所不同，我们只看__aarch64__的。对其他架构感兴趣的可以自行研究。

可以看到，方法的开始处，有一个大的for循环。for (size_t idx = 0; rel_iterator.has_next(); ++idx) ，对rel进行遍历。具体做了什么分点来解释。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390391392393394395396397398399400401402403404405406407 | `template``<``typename` `ElfRelIteratorT>``bool` `soinfo::relocate(``const` `VersionTracker& version_tracker, ElfRelIteratorT&& rel_iterator,``const` `soinfo_list_t& global_group,``const` `soinfo_list_t& local_group) {``for` `(``size_t` `idx = 0; rel_iterator.has_next(); ++idx) {``const` `auto` `rel = rel_iterator.next();``if` `(rel == nullptr) {``return` `false``;``}` `// 重定位类型``ElfW(Word) type = ELFW(R_TYPE)(rel->r_info);``// 符号索引``ElfW(Word) sym = ELFW(R_SYM)(rel->r_info);` `//重定位rela的地址，符号地址``ElfW(Addr) reloc =``static_cast``<ElfW(Addr)>(rel->r_offset + load_bias);` `ElfW(Addr) sym_addr = 0;``const` `char``* sym_name = nullptr;``// 获取出来，rel的addend，我们关注的是rela格式的重定位表自然就是r_addend``ElfW(Addr) addend = get_addend(rel, reloc);` `DEBUG(``"Processing \"%s\" relocation at index %zd"``, get_realpath(), idx);``if` `(type == R_GENERIC_NONE) {``continue``;``}` `// 代表将要查找的符号``const` `ElfW(Sym)* s = nullptr;``soinfo* lsi = nullptr;` `if` `(sym != 0) {``// 获取符号的名字``sym_name = get_string(symtab_[sym].st_name);``const` `version_info* vi = nullptr;` `/**``* 在 Linux 等系统中，共享库（.so）会存在 “版本迭代”（比如 libc.so.6 是 libc 的第 6 个大版本）。``* 为了兼容旧程序（比如旧程序依赖 libc.so.6 的旧版本符号，而系统安装了更新版 libc），ELF 引入了 符号版本控制 机制``* 同一个符号名可能对应多个版本（比如 printf@GLIBC_2.2.5 和 printf@GLIBC_2.34）``* 程序链接时会记录 “依赖的符号版本”，运行时动态链接器必须找到完全匹配版本的符号，否则可能因接口不兼容导致程序崩溃。``*/``if` `(!lookup_version_info(version_tracker, sym, sym_name, &vi)) {``return` `false``;``}` `/**``* 在全局global_group中查找符号，以及local_group依赖的so中查找符号``*/``if` `(!soinfo_do_lookup(``this``, sym_name, vi, &lsi, global_group, local_group, &s)) {``return` `false``;``}` `/**``* 没查找到符号。``*/``if` `(s == nullptr) {``// We only allow an undefined symbol if this is a weak reference...``// 如果这是一个弱符号，我们允许使用未定义的符号。``s = &symtab_[sym];``// 判断是不是弱符号``if` `(ELF_ST_BIND(s->st_info) != STB_WEAK) {``DL_ERR(``"cannot locate symbol \"%s\" referenced by \"%s\"..."``, sym_name, get_realpath());``return` `false``;``}` `/* IHI0044C AAELF 4.5.1.1:` `Libraries are not searched to resolve weak references.``It is not an error for a weak reference to remain unsatisfied.` `During linking, the value of an undefined weak reference is:``- Zero if the relocation type is absolute``- The address of the place if the relocation is pc-relative``- The address of nominal base address if the relocation``type is base-relative.``*/` `switch` `(type) {``case` `R_GENERIC_JUMP_SLOT:``case` `R_GENERIC_GLOB_DAT:``case` `R_GENERIC_RELATIVE:``case` `R_GENERIC_IRELATIVE:``#if defined(__aarch64__)``/**``* 匹配绝对地址重定位``*/``case` `R_AARCH64_ABS64:``case` `R_AARCH64_ABS32:``case` `R_AARCH64_ABS16:``#elif defined(__x86_64__)``case` `R_X86_64_32:``case` `R_X86_64_64:``#elif defined(__arm__)``case` `R_ARM_ABS32:``#elif defined(__i386__)``case` `R_386_32:``#endif``/*``* The sym_addr was initialized to be zero above, or the relocation``* code below does not care about value of sym_addr.``* No need to do anything.``*/``// 保持0，不处理``break``;``#if defined(__x86_64__)``case` `R_X86_64_PC32:``sym_addr = reloc;``break``;``#elif defined(__i386__)``case` `R_386_PC32:``/**``* sym_addr = reloc;``*/``sym_addr = reloc;``break``;``#endif``default``:``DL_ERR(``"unknown weak reloc type %d @ %p (%zu)"``, type, rel, idx);``return` `false``;``}``}``else` `{``// We got a definition.``/**``* 进去该分支，说明查找到符号了，s != nullptr``*/``#if !defined(__LP64__)// 32架构处理逻辑，不分析``// When relocating dso with text_relocation .text segment is``// not executable. We need to restore elf flags before resolving``// STT_GNU_IFUNC symbol.``bool` `protect_segments = has_text_relocations &&``lsi ==``this` `&&``ELF_ST_TYPE(s->st_info) == STT_GNU_IFUNC;``if` `(protect_segments) {``if` `(phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't protect segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``/**``* 解析出符号的地址``*/``sym_addr = lsi->resolve_symbol_address(s);``#if !defined(__LP64__) // 32架构处理逻辑，不分析``if` `(protect_segments) {``if` `(phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``}``//       enum RelocationKind {``//            kRelocAbsolute = 0,``//            kRelocRelative,``//            kRelocCopy,``//            kRelocSymbol,``//            kRelocMax``//        };``// 重定位的类型枚举，设置成符号依赖``/**``* 统计需要重定位的类型，以及计数``*/``count_relocation(kRelocSymbol);``}` `switch` `(type) {``case` `R_GENERIC_JUMP_SLOT:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO JMP_SLOT %16p <- %16p %s\n"``,``reinterpret_cast``<``void``*>(reloc),``reinterpret_cast``<``void``*>(sym_addr + addend), sym_name);` `*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``break``;``case` `R_GENERIC_GLOB_DAT:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO GLOB_DAT %16p <- %16p %s\n"``,``reinterpret_cast``<``void``*>(reloc),``reinterpret_cast``<``void``*>(sym_addr + addend), sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``break``;``case` `R_GENERIC_RELATIVE:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO RELATIVE %16p <- %16p\n"``,``reinterpret_cast``<``void``*>(reloc),``reinterpret_cast``<``void``*>(load_bias + addend));``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (load_bias + addend);``break``;``case` `R_GENERIC_IRELATIVE:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO IRELATIVE %16p <- %16p\n"``,``reinterpret_cast``<``void``*>(reloc),``reinterpret_cast``<``void``*>(load_bias + addend));``{``#if !defined(__LP64__)``// When relocating dso with text_relocation .text segment is``// not executable. We need to restore elf flags for this``// particular call.``if` `(has_text_relocations) {``if` `(phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't protect segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``ElfW(Addr) ifunc_addr = call_ifunc_resolver(load_bias + addend);``#if !defined(__LP64__)``// Unprotect it afterwards...``if` `(has_text_relocations) {``if` `(phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = ifunc_addr;``}``break``;` `#if defined(__aarch64__)``case` `R_AARCH64_ABS64:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO ABS64 %16llx <- %16llx %s\n"``,``reloc, sym_addr + addend, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend;``break``;``case` `R_AARCH64_ABS32:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO ABS32 %16llx <- %16llx %s\n"``,``reloc, sym_addr + addend, sym_name);``{``const` `ElfW(Addr) min_value =``static_cast``<ElfW(Addr)>(INT32_MIN);``const` `ElfW(Addr) max_value =``static_cast``<ElfW(Addr)>(UINT32_MAX);``if` `((min_value <= (sym_addr + addend)) &&``((sym_addr + addend) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend;``}``else` `{``DL_ERR(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_ABS16:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO ABS16 %16llx <- %16llx %s\n"``,``reloc, sym_addr + addend, sym_name);``{``const` `ElfW(Addr) min_value =``static_cast``<ElfW(Addr)>(INT16_MIN);``const` `ElfW(Addr) max_value =``static_cast``<ElfW(Addr)>(UINT16_MAX);``if` `((min_value <= (sym_addr + addend)) &&``((sym_addr + addend) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``}``else` `{``DL_ERR(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_PREL64:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO REL64 %16llx <- %16llx - %16llx %s\n"``,``reloc, sym_addr + addend, rel->r_offset, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``break``;``case` `R_AARCH64_PREL32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO REL32 %16llx <- %16llx - %16llx %s\n"``,``reloc, sym_addr + addend, rel->r_offset, sym_name);``{``const` `ElfW(Addr) min_value =``static_cast``<ElfW(Addr)>(INT32_MIN);``const` `ElfW(Addr) max_value =``static_cast``<ElfW(Addr)>(UINT32_MAX);``if` `((min_value <= (sym_addr + addend - rel->r_offset)) &&``((sym_addr + addend - rel->r_offset) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``}``else` `{``DL_ERR(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend - rel->r_offset, min_value, max_value);``return` `false``;``}``}``break``;``case` `R_AARCH64_PREL16:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO REL16 %16llx <- %16llx - %16llx %s\n"``,``reloc, sym_addr + addend, rel->r_offset, sym_name);``{``const` `ElfW(Addr) min_value =``static_cast``<ElfW(Addr)>(INT16_MIN);``const` `ElfW(Addr) max_value =``static_cast``<ElfW(Addr)>(UINT16_MAX);``if` `((min_value <= (sym_addr + addend - rel->r_offset)) &&``((sym_addr + addend - rel->r_offset) <= max_value)) {``*``reinterpret_cast``<ElfW(Addr)*>(reloc) = sym_addr + addend - rel->r_offset;``}``else` `{``DL_ERR(``"0x%016llx out of range 0x%016llx to 0x%016llx"``,``sym_addr + addend - rel->r_offset, min_value, max_value);``return` `false``;``}``}``break``;` `case` `R_AARCH64_COPY:``/*``* ET_EXEC is not supported so this should not happen.``*``* http://infocenter.arm.com/help/topic/com.arm.doc.ihi0056b/IHI0056B_aaelf64.pdf``*``* Section 4.6.11 "Dynamic relocations"``* R_AARCH64_COPY may only appear in executable objects where e_type is``* set to ET_EXEC.``*/``DL_ERR(``"%s R_AARCH64_COPY relocations are not supported"``, get_realpath());``return` `false``;``case` `R_AARCH64_TLS_TPREL64:``TRACE_TYPE(RELO,``"RELO TLS_TPREL64 *** %16llx <- %16llx - %16llx\n"``,``reloc, (sym_addr + addend), rel->r_offset);``break``;``case` `R_AARCH64_TLS_DTPREL32:``TRACE_TYPE(RELO,``"RELO TLS_DTPREL32 *** %16llx <- %16llx - %16llx\n"``,``reloc, (sym_addr + addend), rel->r_offset);``break``;``#elif defined(__x86_64__)``case` `R_X86_64_32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO R_X86_64_32 %08zx <- +%08zx %s"``,``static_cast``<``size_t``>(reloc),``static_cast``<``size_t``>(sym_addr), sym_name);``*``reinterpret_cast``<Elf32_Addr*>(reloc) = sym_addr + addend;``break``;``case` `R_X86_64_64:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO R_X86_64_64 %08zx <- +%08zx %s"``,``static_cast``<``size_t``>(reloc),``static_cast``<``size_t``>(sym_addr), sym_name);``*``reinterpret_cast``<Elf64_Addr*>(reloc) = sym_addr + addend;``break``;``case` `R_X86_64_PC32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO R_X86_64_PC32 %08zx <- +%08zx (%08zx - %08zx) %s"``,``static_cast``<``size_t``>(reloc),``static_cast``<``size_t``>(sym_addr - reloc),``static_cast``<``size_t``>(sym_addr),``static_cast``<``size_t``>(reloc), sym_name);``*``reinterpret_cast``<Elf32_Addr*>(reloc) = sym_addr + addend - reloc;``break``;``#elif defined(__arm__)``case` `R_ARM_ABS32:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO ABS %08x <- %08x %s"``, reloc, sym_addr, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) += sym_addr;``break``;``case` `R_ARM_REL32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO REL32 %08x <- %08x - %08x %s"``,``reloc, sym_addr, rel->r_offset, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) += sym_addr - rel->r_offset;``break``;``case` `R_ARM_COPY:``/*``* ET_EXEC is not supported so this should not happen.``*``* http://infocenter.arm.com/help/topic/com.arm.doc.ihi0044d/IHI0044D_aaelf.pdf``*``* Section 4.6.1.10 "Dynamic relocations"``* R_ARM_COPY may only appear in executable objects where e_type is``* set to ET_EXEC.``*/``DL_ERR(``"%s R_ARM_COPY relocations are not supported"``, get_realpath());``return` `false``;``#elif defined(__i386__)``case` `R_386_32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO R_386_32 %08x <- +%08x %s"``, reloc, sym_addr, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) += sym_addr;``break``;``case` `R_386_PC32:``count_relocation(kRelocRelative);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO R_386_PC32 %08x <- +%08x (%08x - %08x) %s"``,``reloc, (sym_addr - reloc), sym_addr, reloc, sym_name);``*``reinterpret_cast``<ElfW(Addr)*>(reloc) += (sym_addr - reloc);``break``;``#endif``default``:``DL_ERR(``"unknown reloc type %d @ %p (%zu)"``, type, rel, idx);``return` `false``;``}``}``return` `true``;``}` |
|-|-|

---

在讲解之前，我们看一下elf.h头文件是如何定义，**目标文件 / 可执行文件 / 共享库。**这里的重定位，我们只靠考虑共享库的动态重定位。ELF文件分为三种。这里的符号索引，不同的文件类型也是不同的，在**共享库**是指向dynamic表中的strtab的索引。下面的代码是relocate代码的片段。

这里我们先来《ARM汇编与逆向工程 蓝狐卷 基础知识》这本书中的第二章，讲解了程序重定位一些知识。推荐阅读了，再来看。

| 1234567891011121314151617181920212223 | `// Relocation entry with explicit addend.``struct` `Elf64_Rela {``// 重定位目标地址``Elf64_Addr  r_offset;``// Location (file byte offset, or program virtual addr).``// 高32位符号索引 + 低32位重定位类型``Elf64_Xword  r_info;``// Symbol table index and type of relocation to apply.``// 显式加数（重定位计算时的固定偏移）``Elf64_Sxword r_addend;``// Compute value for relocatable field by adding this.` `// These accessors and mutators correspond to the ELF64_R_SYM, ELF64_R_TYPE,``// and ELF64_R_INFO macros defined in the ELF specification:``// 1. 获取符号表索引（r_info 的高 32 位）``Elf64_Word getSymbol()``const` `{``return` `(r_info >> 32); }``// 2. 获取重定位类型（r_info 的低 32 位）``Elf64_Word getType()``const` `{``return` `(Elf64_Word) (r_info & 0xffffffffL);``}``void` `setSymbol(Elf64_Word s) { setSymbolAndType(s, getType()); }``void` `setType(Elf64_Word t) { setSymbolAndType(getSymbol(), t); }``void` `setSymbolAndType(Elf64_Word s, Elf64_Word t) {``r_info = ((Elf64_Xword)s << 32) + (t&0xffffffffL);``}``};` |
|-|-|

看到第一个方法***lookup_version_info，***该方法是跟符号版本管理相关的，想了解这部分的，可以看我推荐看的书《程序员的自我修养——链接、装载与库》，这里面有关于符号版本管理。

/**
 * 在 Linux 等系统中，共享库（.so）会存在 “版本迭代”（比如 libc.so.6 是 libc 的第 6 个大版本）。
 * 为了兼容旧程序（比如旧程序依赖 libc.so.6 的旧版本符号，而系统安装了更新版 libc），ELF 引入了 符号版本控制 机制
 * 同一个符号名可能对应多个版本（比如 printf@GLIBC_2.2.5 和 printf@GLIBC_2.34）
 * 程序链接时会记录 “依赖的符号版本”，运行时动态链接器必须找到完全匹配版本的符号，否则可能因接口不兼容导致程序崩溃。
 */

开始讲解第一个核心方法soinfo_do_lookup，该方法根据符号名字，来查找符号所在so的符号，值得注意的是，这就是为什么so不能抹除so的动态符号表，动态字符串表。忽略has_DT_SYMBOLIC的判断，感兴趣的可以去了解一下，AI分析一下，就是执行符号查找的优先级。

然后就到了方法中的注释// 1. Look for it in global_group，很容易知道，这个是在全局库当中查找符号，如libc.so等就是全局库**global_group**。

调用了global_group的visit方法，传入的闭包函数。我们接着分析一下这个闭包函数做了什么。调用了global_si->find_symbol_by_name(symbol_name, vi, &s)，查找当前的soinfo，根据名字查找符号。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104 | `/**``* 在全局global_group中查找符号，以及local_group依赖的so中查找符号``* 传递的参数（this, sym_name, vi, &lsi, global_group, local_group, &s）``* si_from为当前so``* sym_name为需要查找符号的名字``* vi是符号版本``* lsi是待查找符号所在库``* global_group是全局库``* local_group是当前依赖的库``* s是待查找的符号``*/``bool` `soinfo_do_lookup(soinfo* si_from,``const` `char``* name,``const` `version_info* vi,``soinfo** si_found_in,``const` `soinfo_list_t& global_group,``const` `soinfo_list_t& local_group,``const` `ElfW(Sym)** symbol) {``//将符号名字封装成SymbolName``SymbolName symbol_name(name);``const` `ElfW(Sym)* s = nullptr;` `/* "This element's presence in a shared object library alters the dynamic linker's``* symbol resolution algorithm for references within the library. Instead of starting``* a symbol search with the executable file, the dynamic linker starts from the shared``* object itself. If the shared object fails to supply the referenced symbol, the``* dynamic linker then searches the executable file and other shared objects as usual."``*``* http://www.sco.com/developers/gabi/2012-12-31/ch5.dynamic.html``*``* Note that this is unlikely since static linker avoids generating``* relocations for -Bsymbolic linked dynamic executables.``*/``if` `(si_from->has_DT_SYMBOLIC) {``DEBUG(``"%s: looking up %s in local scope (DT_SYMBOLIC)"``, si_from->get_realpath(), name);``if` `(!si_from->find_symbol_by_name(symbol_name, vi, &s)) {``return` `false``;``}` `if` `(s != nullptr) {``*si_found_in = si_from;``}``}` `// 1. Look for it in global_group``if` `(s == nullptr) {``bool` `error =``false``;``global_group.visit([&](soinfo* global_si) {``DEBUG(``"%s: looking up %s in %s (from global group)"``,``si_from->get_realpath(), name, global_si->get_realpath());``if` `(!global_si->find_symbol_by_name(symbol_name, vi, &s)) {``error =``true``;``return` `false``;``}` `if` `(s != nullptr) {``*si_found_in = global_si;``return` `false``;``}` `return` `true``;``});` `if` `(error) {``return` `false``;``}``}` `// 2. Look for it in the local group``if` `(s == nullptr) {``bool` `error =``false``;``local_group.visit([&](soinfo* local_si) {``if` `(local_si == si_from && si_from->has_DT_SYMBOLIC) {``// we already did this - skip``return` `true``;``}` `DEBUG(``"%s: looking up %s in %s (from local group)"``,``si_from->get_realpath(), name, local_si->get_realpath());``if` `(!local_si->find_symbol_by_name(symbol_name, vi, &s)) {``error =``true``;``return` `false``;``}` `if` `(s != nullptr) {``*si_found_in = local_si;``return` `false``;``}` `return` `true``;``});` `if` `(error) {``return` `false``;``}``}` `if` `(s != nullptr) {``TRACE_TYPE(LOOKUP,``"si %s sym %s s->st_value = %p, "``"found in %s, base = %p, load bias = %p"``,``si_from->get_realpath(), name,``reinterpret_cast``<``void``*>(s->st_value),``(*si_found_in)->get_realpath(),``reinterpret_cast``<``void``*>((*si_found_in)->base),``reinterpret_cast``<``void``*>((*si_found_in)->load_bias));``}` `*symbol = s;``return` `true``;``}` |
|-|-|

我们继续分析find_symbol_by_name方法，看看是如何实现的。这里有一个is_gnu_hash，这个就是判断是否存在gnu_hash这个section，我们知道，这个section是用来加速符号查找的，底层类似红黑数这种结构。这里我们看一下**elf_lookup**是如何实现的。

代码如下

| 123456789101112131415 | `bool` `soinfo::find_symbol_by_name(SymbolName& symbol_name,``const` `version_info* vi,``const` `ElfW(Sym)** symbol)``const` `{``uint32_t symbol_index;``bool` `success =``is_gnu_hash() ?``gnu_lookup(symbol_name, vi, &symbol_index) :``elf_lookup(symbol_name, vi, &symbol_index);` `if` `(success) {``*symbol = symbol_index == 0 ? nullptr : symtab_ + symbol_index;``}` `return` `success;``}` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `bool` `soinfo::elf_lookup(SymbolName& symbol_name,``const` `version_info* vi,``uint32_t* symbol_index)``const` `{``// 根据符号计算处hash值``uint32_t hash = symbol_name.elf_hash();` `TRACE_TYPE(LOOKUP,``"SEARCH %s in %s@%p h=%x(elf) %zd"``,``symbol_name.get_name(), get_realpath(),``reinterpret_cast``<``void``*>(base), hash, hash % nbucket_);`  `// Verneed（需要的版本）``ElfW(Versym) verneed = 0;``// 查找所需符号的版本（Verneed）``if` `(!find_verdef_version_index(``this``, vi, &verneed)) {``//返回true就说明版本符合``return` `false``;``}` `// 哈希取模法，取出符号所在的chain，然后遍历chain，寻找符号``for` `(uint32_t n = bucket_[hash % nbucket_]; n != 0; n = chain_[n]) {``// 这里的symtab_是动态符号表``// 当前遍历的符号 s``ElfW(Sym)* s = symtab_ + n;``// 当前遍历符号的版本（来自 .gnu.version）``const` `ElfW(Versym)* verdef = get_versym(n);` `// skip hidden versions when verneed == 0``// 如果 verneed=0（不需要版本），跳过“隐藏版本”``if` `(verneed == kVersymNotNeeded && is_versym_hidden(verdef)) {``continue``;``}` `// 检查符号版本、名字和属性``/**``* 判断3个条件：``* 检查 Verneed index 是否与 symbol 的 Verdef 匹配。``* 符号名称是否相同。``* 是否是全局符号（GLOBAL / WEAK）是否在当前 so 定义（非 undefined）``*/``if` `(check_symbol_version(verneed, verdef) &&``strcmp``(get_string(s->st_name), symbol_name.get_name()) == 0 &&``is_symbol_global_and_defined(``this``, s)) {``TRACE_TYPE(LOOKUP,``"FOUND %s in %s (%p) %zd"``,``symbol_name.get_name(), get_realpath(),``reinterpret_cast``<``void``*>(s->st_value),``static_cast``<``size_t``>(s->st_size));``// 进入该分支，说明找到符号了``*symbol_index = n;``return` `true``;``}``}` `TRACE_TYPE(LOOKUP,``"NOT FOUND %s in %s@%p %x %zd"``,``symbol_name.get_name(), get_realpath(),``reinterpret_cast``<``void``*>(base), hash, hash % nbucket_);` `*symbol_index = 0;``return` `true``;``}` |
|-|-|

我们继续回到soinfo_do_lookup方法中，来往下看，

// 2. Look for it in the local group代码上注释写得很清除，在global_group还是找不到符号，就去 local group， local group当中保存的是依赖的so。dfs依赖顺序的序列。和上面的方法同理，就不赘述了。

到此符号的查找流程结束，我们继续回到***relocate***方法当中，接着判断，s 符号是否查找成功。

**符号没找到，s = nullptr，**进入该分支，判断是不是弱符号。是的话，就开始进入switch中，匹配type，这个tpye是前面的代码中，是表示重定位类型。

这里只匹配绝对地址重定位。sym_addr = reloc;然后代码直接break。就允许该符号的地址保持0。

代码如下

| 12345678 | `/**``* 匹配绝对地址重定位``*/``case` `R_AARCH64_ABS64:``case` `R_AARCH64_ABS32:``case` `R_AARCH64_ABS16:``sym_addr = reloc;``//保持原本的地址一般都是0，这种绝对定位``break``;` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202512/DRDF57EZ24XEEVS.jpg)

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `switch` `(type) {``case` `R_GENERIC_JUMP_SLOT:``case` `R_GENERIC_GLOB_DAT:``case` `R_GENERIC_RELATIVE:``case` `R_GENERIC_IRELATIVE:``#``if` `defined(__aarch64__)``/**``* 匹配绝对地址重定位``*/``case` `R_AARCH64_ABS64:``case` `R_AARCH64_ABS32:``case` `R_AARCH64_ABS16:``#elif defined(__x86_64__)``case` `R_X86_64_32:``case` `R_X86_64_64:``#elif defined(__arm__)``case` `R_ARM_ABS32:``#elif defined(__i386__)``case` `R_386_32:``#endif``/*``* The sym_addr was initialized to be zero above, or the relocation``* code below does not care about value of sym_addr.``* No need to do anything.``*/``// 保持0，不处理``break``;``#``if` `defined(__x86_64__)``case` `R_X86_64_PC32:``sym_addr = reloc;``break``;``#elif defined(__i386__)``case` `R_386_PC32:``sym_addr = reloc;``break``;``#endif``default``:``DL_ERR(``"unknown weak reloc type %d @ %p (%zu)"``, type, rel, idx);``return` `false``;``}` |
|-|-|

**符号找到，s ！= nullptr，**我们接着看，进去该分支，说明找到了符号，

sym_addr = lsi->resolve_symbol_address(s);然后调用该方法，解析出符号的地址。获取了计算处符号的地址，s->st_value + load_bias

代码如下

| 123456789101112131415161718192021222324252627282930313233 | `{``// We got a definition.``/**``* 进去该分支，说明查找到符号了，s != nullptr``*/``#``if` `!defined(__LP64__)``// 32架构处理逻辑，不分析``// When relocating dso with text_relocation .text segment is``// not executable. We need to restore elf flags before resolving``// STT_GNU_IFUNC symbol.``bool` `protect_segments = has_text_relocations &&``lsi ==``this` `&&``ELF_ST_TYPE(s->st_info) == STT_GNU_IFUNC;``if` `(protect_segments) {``if` `(phdr_table_protect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't protect segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``/**``* 解析出符号的地址``*/``sym_addr = lsi->resolve_symbol_address(s);``#``if` `!defined(__LP64__)``// 32架构处理逻辑，不分析``if` `(protect_segments) {``if` `(phdr_table_unprotect_segments(phdr, phnum, load_bias) < 0) {``DL_ERR(``"can't unprotect loadable segments for \"%s\": %s"``,``get_realpath(),``strerror``(``errno``));``return` `false``;``}``}``#endif``}` |
|-|-|

| 1234567 | `ElfW(Addr) soinfo::resolve_symbol_address(``const` `ElfW(Sym)* s)``const` `{``if` `(ELF_ST_TYPE(s->st_info) == STT_GNU_IFUNC) {``return` `call_ifunc_resolver(s->st_value + load_bias);``}` `return` `static_cast``<ElfW(Addr)>(s->st_value + load_bias);``}` |
|-|-|

终于要到尾声了，接着到了relocate最后的阶段，这是一个很大的switch (type) {}，匹配重定位的类型。这里我们挑选两个重定位类型来讲解一下。

这里将符号地址sym_addr + addend，设置到reloc。

代码如下

| 123456789 | `case` `R_GENERIC_JUMP_SLOT:``count_relocation(kRelocAbsolute);``MARK(rel->r_offset);``TRACE_TYPE(RELO,``"RELO JMP_SLOT %16p <- %16p %s\n"``,``reinterpret_cast``<``void``*>(reloc),``reinterpret_cast``<``void``*>(sym_addr + addend), sym_name);` `*``reinterpret_cast``<ElfW(Addr)*>(reloc) = (sym_addr + addend);``break``;` |
|-|-|

最后感兴趣其他架构的可以去结合AI学习。下面交给AI讲解的重定位类型，都对应上了。

笔者能力有限

下面我给你 **多个真实且典型的 ELF 重定位示例**，让你彻底理解各种重定位（`JUMP_SLOT`、`GLOB_DAT`、`RELATIVE`、`ABS`、`COPY`）是如何作用到内存的。

每个例子都包含：

- 重定位项 r_offset / r_info
- 重定位类型
- 涉及的符号
- linker 最终如何修改内存
- 用图表示

这些例子适用于 ARM64 / x86 / ARM，只是具体类型名字略有不同。

---

###  **示例 1：R_GENERIC_JUMP_SLOT（修复函数地址）**

PLT/GOT 表项的函数重定位。

### 假设：

GOT 中某个 entry 需要解析 `printf`：

- GOT entry 地址：`0x7f10001000`
- `printf` 的真实地址：`0x7f20005000`

### 重定位项（.rela.plt）：

| 字段 | 内容 |
|-|-|
| `r_offset` | 0x1000 |
| `r_info` | (symbol: printf, type: JUMP_SLOT) |
| `r_addend` | 0 |

### linker 做的事：

| 1 | `*(0x7f10001000) = 0x7f20005000` |
|-|-|

### 图表示：

| 1 | `[GOT entry: 0x7f10001000]  ←写入—  [``printf` `实际地址: 0x7f20005000]` |
|-|-|

调用函数时：

| 1 | `BLX [GOT entry] → 跳到 0x7f20005000（真正的``printf``）` |
|-|-|

###

---

### **示例 2：R_GENERIC_GLOB_DAT（修复变量地址）**

这是全局变量的地址绑定。

例如：

| 1 | `extern` `int` `errno``;``// 需要从 libc.so 引入` |
|-|-|

### 假设：

- GOT entry 地址：`0x7f10002000`
- errno 在 libc 中的实际地址：`0x7f2000A000`

### `.rela.dyn`：

| 字段 | 内容 |
|-|-|
| `r_offset` | 0x2000 |
| `r_info` | (symbol: errno, type: GLOB_DAT) |
| `r_addend` | 0 |

### linker 做的事情：

| 1 | `*(0x7f10002000) = 0x7f2000A000` |
|-|-|

### 图：

| 1 | `[GOT``errno` `entry] ← 0x7f2000A000 (``errno``的实际地址)` |
|-|-|

---

### **示例 3：R_GENERIC_RELATIVE（修复自身数据段地址）**

这个重定位不涉及符号，只是：

把 r_offset 地址写成 (base + addend)

例如 shared library load bias = `0x7f10000000`

### `.rela.dyn`：

| 字段 | 内容 |
|-|-|
| `r_offset` | 0x3000 |
| `r_info` | (type: RELATIVE) |
| `r_addend` | 0x5000 |

### linker 操作：

| 1 | `*(base + r_offset) = base + addend` |
|-|-|

即：

| 1 | `*(0x7f10000000 + 0x3000) = 0x7f10000000 + 0x5000` |
|-|-|

### 图：

| 1 | `address 0x7f10003000 ← 0x7f10005000` |
|-|-|

用途：

- 修复静态数据指针
- vtable 指针
- 字符串指针

比符号查找快得多。

---

### **示例 4：R_GENERIC_ABS（修复绝对地址引用）**

用于代码或数据段中包含符号的 **绝对地址**。

例子：

| 12 | `extern` `int` `global_value;``void``* p = &global_value;``// 需要一个绝对地址` |
|-|-|

假设：

- 指向 p 的内存位置：`0x7f10004000`
- global_value 地址：`0x7f20008000`

### `.rela.dyn`：

| 字段 | 内容 |
|-|-|
| `r_offset` | 0x4000 |
| `r_info` | (symbol: global_value, type: ABS) |
| `r_addend` | 0 |

### linker：

| 1 | `*(0x7f10004000) = 0x7f20008000` |
|-|-|

---

### **示例 5：R_GENERIC_COPY（只发生在可执行程序）**

它要求：

把共享库的变量内容复制到可执行程序的 BSS 段。

例子：

可执行文件：

| 1 | `int` `global_var = 0;` |
|-|-|

共享库中：

| 1 | `extern` `int` `global_var;` |
|-|-|

### 在可执行文件的 `.rela.dyn`：

| 字段 | 内容 |
|-|-|
| `r_offset` | 地址：0x6000（exe 中的 global_var） |
| `r_info` | (symbol: global_var, type: COPY) |

### linker 做的事：

| 1 | `memcpy``(exe.global_var, libc.global_var,``sizeof``(``int``));` |
|-|-|

---

### **总结对比表**

| 重定位类型 | 场景 | 是否查找符号 | 写入内容 | 举例 |
|-|-|-|-|-|
| **JUMP_SLOT** | 函数调用（PLT/GOT） | ✔ | GOT = 符号地址 | printf |
| **GLOB_DAT** | 全局变量 | ✔ | GOT = 符号地址 | errno |
| **RELATIVE** | 自身数据指针 | ✘ | *(base+offset) = base+addend | 静态指针 |
| **ABS** | 绝对地址引用 | ✔ | *(addr) = 符号地址 | &global |
| **COPY** | exe 复制共享库变量 | ✔ | memcpy() | 全局变量初始化 |

## 总结

Step 4 决定哪些库的符号是全局可见的（构建 Global Group）；
Step 5 处理跨 namespace 加载的依赖（并维护引用计数）；
Step 6 执行真正的符号解析与重定位（link_image），让 so 可运行。

最后笔者能力有限，本文难免存在疏漏或者理解错误，恳请读者不吝赐教与指正。

---

# 回复

## 回复 by KanXue_NG (#2)

*2025-12-3 09:50*

学习学习

## 回复 by Imxz (#3)

*2025-12-3 14:22*

TQL

## 回复 by mb_jnmxfjku (#4)

*2025-12-3 15:09*

11

## 回复 by LQ6H (#5)

*2025-12-4 10:44*

666

## 回复 by iBa0 (#6)

*2025-12-4 10:45*

1

## 回复 by 掀起你的头盖骨 (#7)

*2025-12-5 13:28*

学习

## 回复 by mb_undsjfmp (#8)

*2025-12-8 16:50*

1

## 回复 by 后来_797333 (#9)

*2025-12-8 20:21*

666

## 回复 by Ace_Heng (#10)

*2025-12-9 10:31*

看看

## 回复 by mb_uvyukvot (#11)

*2025-12-9 11:32*

666

## 回复 by 我心向山 (#12)

*2025-12-22 20:29*

666

## 回复 by aceding (#13)

*2025-12-28 23:10*

感谢分享

## 回复 by 0x25519 (#14)

*2025-12-29 18:07*

学习学习

## 回复 by GEKEZYX (#15)

*2025-12-30 10:00*

666

## 回复 by 温泉划水鱼 (#16)

*2026-1-5 01:13*

555

## 回复 by mb_hziqyrum (#17)

*2026-1-24 19:50*

666

## 回复 by XCicada (#18)

*2026-1-24 20:45*

回复来看看，先谢过楼主！

## 回复 by superlahm (#19)

*2026-2-11 19:16*

666

## 回复 by qig (#20)

*2026-2-13 11:36*

学习学习

## 回复 by 饮岁 (#21)

*2026-2-24 10:14*

666

## 回复 by dsr000 (#22)

*2026-2-25 16:40*

666

## 回复 by 晴空万里丶 (#23)

*2026-3-21 17:09*

学习下

## 回复 by devil_1 (#24)

*2026-3-21 19:48*

66

## 回复 by 小迷糊ddd (#25)

*2026-4-7 09:17*

感谢分享，学习一下。

## 回复 by fzyspark (#26)

*2026-4-23 12:13*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_vxjviech (#27)

*2026-6-7 08:50*

666
