---
title: '[原创]初探Android Linker 动态库SO的加载流程（1）'
url: https://bbs.kanxue.com/thread-289304.htm
tid: 289304
author: Ayuer
date: '2025-12-02'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:00:27+08:00'
replies: 94
---

这部分会比较难，比较复杂，建议学习过ELF文件结构的再来读这份代码，这里推荐读完《程序员的自我修养——链接、装载与库》，以及《ARM汇编与逆向工程 蓝狐卷 基础知识》的第二章知识，然后再来看，这一系列文章。

从这篇文章开始，基于aosp8.1加载SO源码的部分研究，打算将分为3篇写完7个加载步骤，流程十分长，学完对ELF的认识就不会只停留在书籍上了，对研究ELF文件格式、so加固将会有所帮助。

还有一篇番外篇，关于自定义Linker的现实，以及结合开源的so脱壳脚本分析。

## 直接从find_libraries讲起，一共分为7部分，每一部分就是按照每一步来写，根据源码的注释划分来讲解。

## step 0

第一次调用该方法的加载目标so时候，我后面都称为目标so，传递的参数，如下。

**代码如下**

| 1 | `find_libraries(ns,needed_by,&name,1,&si,nullptr,0,rtld_flags,extinfo,``false``,``true``,readers_map)` |
|-|-|

so的加载都会被封装成一个LoadTask，load_tasks是本次加载任务链表，是一个链表结构，library_names_count是为1，所在在load_tasks当前只有目标so，下面的代码是为soinfo = nullptr，参数传递的是nullptr。进行soinfo空间分配。

代码如下

| 1234567891011121314151617181920212223242526 | `// Step 0: prepare.``/**``* 步骤 0``*/``LoadTaskList load_tasks;` `/**``* 创建一个加载任务LoadTask``*/``for` `(``size_t` `i = 0; i < library_names_count; ++i) {``const` `char``* name = library_names[i];``load_tasks.push_back(LoadTask::create(name, start_with, ns, &readers_map));``}` `// If soinfos array is null allocate one on stack.``// The array is needed in case of failure; for example``// when library_names[] = {libone.so, libtwo.so} and libone.so``// is loaded correctly but libtwo.so failed for some reason.``// In this case libone.so should be unloaded on return.``// See also implementation of failure_guard below.``//分配so info空间``if` `(soinfos == nullptr) {``size_t` `soinfos_size =``sizeof``(soinfo*)*library_names_count;``soinfos =``reinterpret_cast``<soinfo**>(alloca(soinfos_size));``memset``(soinfos, 0, soinfos_size);``}` |
|-|-|

## Step 1

load_tasks的大小还是只有1，遍历load_tasks然后调用task->get_needed_by();，needed_by代表的是哪个库需要我。举个例子libA -> libB，A依赖B，此时如果加载的task是libB，则get_needed_by得到的则是libA。needed_by是一个链表结构。

根据结果设置task的属性。find_library_internal，方法会把task和load_tasks传递进去

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657 | `// Step 1: expand the list of load_tasks to include``// all DT_NEEDED libraries (do not load them just yet)``/**``* 步骤1：展开load_tasks列表以包含``* 所有DT_NEEED库（暂时不要加载）``*/``for` `(``size_t` `i = 0; i<load_tasks.size(); ++i) {``LoadTask* task = load_tasks[i];``/**``* 假如A->B，此时是加载的是B，则needed_by是A，代表当前si被谁需要``* 获取获取被依赖的库``*/``soinfo* needed_by = task->get_needed_by();` `//为true``bool` `is_dt_needed = needed_by != nullptr && (needed_by != start_with \|\| add_as_children);``task->set_extinfo(is_dt_needed ? nullptr : extinfo);``task->set_dt_needed(is_dt_needed);` `// try to find the load.``// Note: start from the namespace that is stored in the LoadTask. This namespace``// is different from the current namespace when the LoadTask is for a transitive``// dependency and the lib that created the LoadTask is not found in the``// current namespace but in one of the linked namespace.``/**``* 查找是否已经加载，没加载就加载，系统调用open，得到fd文件描述符``* find_library_internal``*/``if` `(!find_library_internal(``const_cast``<android_namespace_t*>(task->get_start_from()),``task,``&zip_archive_cache,``&load_tasks,``rtld_flags,``search_linked_namespaces \|\| is_dt_needed)) {``return` `false``;``}` `soinfo* si = task->get_soinfo();` `if` `(is_dt_needed) {``needed_by->add_child(si);` `if` `(si->is_linked()) {``si->increment_ref_count();``}``}` `// When ld_preloads is not null, the first``// ld_preloads_count libs are in fact ld_preloads.``if` `(ld_preloads != nullptr && soinfos_count < ld_preloads_count) {``ld_preloads->push_back(si);``}` `if` `(soinfos_count < library_names_count) {``soinfos[soinfos_count++] = si;``}``}` |
|-|-|

find_library_internal方法的代码如下，这里关注主分支代码，find_loaded_library_by_soname获取的不到，然后会往下走，调用load_library方法，如果上面load_library加载不成功，就会到linked_namespaces进去加载load_library是否存在该so，这里不分析linked_namespaces这部分。

代码如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `/**``* find_library_internal``*/``static` `bool` `find_library_internal(android_namespace_t* ns,``LoadTask* task,``ZipArchiveCache* zip_archive_cache,``LoadTaskList* load_tasks,``int` `rtld_flags,``bool` `search_linked_namespaces) {``soinfo* candidate;` `if` `(find_loaded_library_by_soname(ns, task->get_name(), search_linked_namespaces, &candidate)) {``task->set_soinfo(candidate);``return` `true``;``}` `// Library might still be loaded, the accurate detection``// of this fact is done by load_library.``TRACE(``"[ \"%s\" find_loaded_library_by_soname failed (*candidate=%s@%p). Trying harder...]"``,``task->get_name(), candidate == nullptr ?``"n/a"` `: candidate->get_realpath(), candidate);` `/**``* load_library``*/``if` `(load_library(ns, task, zip_archive_cache, load_tasks, rtld_flags, search_linked_namespaces)) {``return` `true``;``}` `/**``* 如果上面load_library加载不成功，就会寻找linked_namespaces是否存在该so``*/``if` `(search_linked_namespaces) {``// if a library was not found - look into linked namespaces``for` `(``auto``& linked_namespace : ns->linked_namespaces()) {``if` `(find_library_in_linked_namespace(linked_namespace,``task)) {``if` `(task->get_soinfo() == nullptr) {``// try to load the library - once namespace boundary is crossed``// we need to load a library within separate load_group``// to avoid using symbols from foreign namespace while.``//``// However, actual linking is deferred until when the global group``// is fully identified and is applied to all namespaces.``// Otherwise, the libs in the linked namespace won't get symbols from``// the global group.``if` `(load_library(linked_namespace.linked_namespace(), task, zip_archive_cache, load_tasks, rtld_flags,``false``)) {``return` `true``;``}``// lib was not found in the namespace. Try next linked namespace.``}``else` `{``// lib is already loaded``return` `true``;``}``}``}``}` `return` `false``;``}` |
|-|-|

我们继续看load_library方法的代码，方法有两个重载。我看先看第一个重载的方法。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `/**``* 1``*/``static` `bool` `load_library(android_namespace_t* ns,``LoadTask* task,``ZipArchiveCache* zip_archive_cache,``LoadTaskList* load_tasks,``int` `rtld_flags,``bool` `search_linked_namespaces) {``const` `char``* name = task->get_name();``soinfo* needed_by = task->get_needed_by();``const` `android_dlextinfo* extinfo = task->get_extinfo();` `off64_t file_offset;``std::string realpath;``if` `(extinfo != nullptr && (extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD) != 0) {``file_offset = 0;``if` `((extinfo->flags & ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET) != 0) {``file_offset = extinfo->library_fd_offset;``}` `if` `(!realpath_fd(extinfo->library_fd, &realpath)) {``PRINT(``"warning: unable to get realpath for the library \"%s\" by extinfo->library_fd. "``"Will use given name."``, name);``realpath = name;``}` `task->set_fd(extinfo->library_fd,``false``);``task->set_file_offset(file_offset);``return` `load_library(ns, task, load_tasks, rtld_flags, realpath, search_linked_namespaces);``}` `// Open the file.``/**``* Open the file.``* open_library``* 场景 1：SO 被打包在其他文件中（如静态库、镜像文件、加壳后的壳 SO）：比如加壳 SO 中，原始 SO（Payload）的 ELF 数据被加密后存储在壳 SO 的数据段，有固定的文件偏移；``* 场景 2：共享库的 “片段加载”：极少数情况下，SO 可能被分割成多个片段存储，加载时需指定片段在文件中的起始偏移；``* file_offset不是所有要加载的 SO 都是 “独立的 .so 文件”—— 存在以下场景，SO 数据并非从文件起始位置开始：``*/``int` `fd = open_library(ns, zip_archive_cache, name, needed_by, &file_offset, &realpath);``if` `(fd == -1) {``DL_ERR(``"library \"%s\" not found"``, name);``return` `false``;``}` `/**``* 赋值fd，以及file_offset``*/``task->set_fd(fd,``true``);``task->set_file_offset(file_offset);` `return` `load_library(ns, task, load_tasks, rtld_flags, realpath, search_linked_namespaces);``}` |
|-|-|

我们关注主分支流程open_library方法

strchr(name, '/') != nullptr根据注释这里说明如果路径包含斜杠/，则去尝试加载，这里我们不分析。然后往下这里分为三部分。

1. 第一部分是ns->get_ld_library_paths()，获取的是LD_LIBRARY_PATH，尝试到这里去加载so
2. 第二部分是ns->get_default_library_paths()，获取的是默认路径（如 /system/lib /apex/...）
3. 第三部分是g_default_namespace.get_default_library_paths()，获取的是系统默认 namespace 的路径（灰名单机制），这个就是防止app种直接dlopen系统库的限制，但是还是开放了一部分的系统运行用户加载，我那时研究的加载libart.so，这个路径我在第一份实习公司的时候涉及修改研究这部分内容

这里有一篇文章写得非常好，<https://www.52pojie.cn/thread-948942-1-1.html>，关于Android7.0以上命名空间详解(dlopen限制)。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172 | `/**``* open_library``*/``static` `int` `open_library(android_namespace_t* ns,``ZipArchiveCache* zip_archive_cache,``const` `char``* name, soinfo *needed_by,``off64_t* file_offset, std::string* realpath) {``TRACE(``"[ opening %s at namespace %s]"``, name, ns->get_name());` `// If the name contains a slash, we should attempt to open it directly and not search the paths.``if` `(``strchr``(name,``'/'``) != nullptr) {``int` `fd = -1;` `if` `(``strstr``(name, kZipFileSeparator) != nullptr) {``fd = open_library_in_zipfile(zip_archive_cache, name, file_offset, realpath);``}` `if` `(fd == -1) {``fd = TEMP_FAILURE_RETRY(open(name, O_RDONLY \| O_CLOEXEC));``if` `(fd != -1) {``*file_offset = 0;``if` `(!realpath_fd(fd, realpath)) {``PRINT(``"warning: unable to get realpath for the library \"%s\". Will use given path."``, name);``*realpath = name;``}``}``}` `return` `fd;``}` `/**``* 3 级搜索路径体系``*``* 1``* 应用/namespace 可以自定义的路径``* 否则，我们先尝试LD_LIBRARY_PATH，然后回退到默认库路径``*/``// Otherwise we try LD_LIBRARY_PATH first, and fall back to the default library path``int` `fd = open_library_on_paths(zip_archive_cache, name, file_offset, ns->get_ld_library_paths(), realpath);``if` `(fd == -1 && needed_by != nullptr) {``fd = open_library_on_paths(zip_archive_cache, name, file_offset, needed_by->get_dt_runpath(), realpath);``// Check if the library is accessible``if` `(fd != -1 && !ns->is_accessible(*realpath)) {``fd = -1;``}``}` `/**``* 2``* namespace 默认路径（如 /system/lib /apex/...）``* get_default_library_paths``*/``if` `(fd == -1) {``fd = open_library_on_paths(zip_archive_cache, name, file_offset, ns->get_default_library_paths(), realpath);``}` `/**``* 3``* 系统默认 namespace 的路径（灰名单机制）``* g_default_namespace的get_default_library_paths``*/``// TODO(dimitry): workaround for http://b/26394120 (the grey-list)``if` `(fd == -1 && ns->is_greylist_enabled() && is_greylisted(ns, name, needed_by)) {``// try searching for it on default_namespace default_library_path``fd = open_library_on_paths(zip_archive_cache, name, file_offset,``g_default_namespace.get_default_library_paths(), realpath);``}``// END OF WORKAROUND` `return` `fd;``}` |
|-|-|

然后接下来直接看open_library_on_paths方法，该方法中，kZipFileSeparator是const char* const kZipFileSeparator = "!/";不是我们分析的类型，不会走该分支，只有是该分支才会走open_library_in_zipfile，

接下来是调用open(buf, O_RDONLY | O_CLOEXEC)，这是Linux系统调用，用于打开文件获取文件描述符fd，然后返回。

代码如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `/**``* open_library_on_paths``* @param zip_archive_cache``* @param name``* @param file_offset``* @param paths``* @param realpath``*/``static` `int` `open_library_on_paths(ZipArchiveCache* zip_archive_cache,``const` `char``* name, off64_t* file_offset,``const` `std::vector<std::string>& paths,``std::string* realpath) {``for` `(``const` `auto``& path : paths) {``char` `buf[512];``if` `(!format_path(buf,``sizeof``(buf), path.c_str(), name)) {``continue``;``}` `int` `fd = -1;``if` `(``strstr``(buf, kZipFileSeparator) != nullptr) {``fd = open_library_in_zipfile(zip_archive_cache, buf, file_offset, realpath);``}` `/**``* 使用了open系统调用``* open(buf, O_RDONLY \| O_CLOEXEC)``*/``if` `(fd == -1) {``fd = TEMP_FAILURE_RETRY(open(buf, O_RDONLY \| O_CLOEXEC));``if` `(fd != -1) {``*file_offset = 0;``if` `(!realpath_fd(fd, realpath)) {``PRINT(``"warning: unable to get realpath for the library \"%s\". Will use given path."``, buf);``*realpath = buf;``}``}``}` `if` `(fd != -1) {``return` `fd;``}``}` `return` `-1;``}` |
|-|-|

到此，我们继续回到load_library方法，

load_library方法代码片段如下

| 12345 | `/**``* 赋值fd，以及file_offset``*/``task->set_fd(fd,``true``);``task->set_file_offset(file_offset);` |
|-|-|

然后设置task的fd。以及文件偏移。结合AI分析

1. * 场景 1：SO 被打包在其他文件中（如静态库、镜像文件、加壳后的壳 SO）：比如加壳 SO 中，原始 SO（Payload）的 ELF 数据被加密后存储在壳 SO 的数据段，有固定的文件偏移；
2. * 场景 2：共享库的 “片段加载”：极少数情况下，SO 可能被分割成多个片段存储，加载时需指定片段在文件中的起始偏移；
* file_offset不是所有要加载的 SO 都是 “独立的 .so 文件”—— 存在以下场景，SO 数据并非从文件起始位置开始。

那这部分对于普通的so应该就是0。

接着load_library方法开始调用load_library的第二个重载

首先是soinfo_alloc，分配soinfo，task->set_soinfo(si);

然后核心是，task调用read方法，这里说结论，read方法会去读取的内容如下

1. **ELF文件头，验证文件头，对应代码ReadElfHeader()，VerifyElfHeader()**
2. **程序头表，对应代码ReadProgramHeaders()**
3. **节头表，对应代码ReadSectionHeaders()**
4. **dynamic节头表，对应代码ReadDynamicSection()**

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667 | `/**``* 2``*/``static` `bool` `load_library(android_namespace_t* ns,``LoadTask* task,``LoadTaskList* load_tasks,``int` `rtld_flags,``const` `std::string& realpath,``bool` `search_linked_namespaces) {``off64_t file_offset = task->get_file_offset();``const` `char``* name = task->get_name();``const` `android_dlextinfo* extinfo = task->get_extinfo();` `/*``* 中间省略代码，我们之关注主分支代码``*/` `//分配soinfo``soinfo* si = soinfo_alloc(ns, realpath.c_str(), &file_stat, file_offset, rtld_flags);``if` `(si == nullptr) {``return` `false``;``}` `//set_soinfo``task->set_soinfo(si);` `/**``* Read the ELF header and some of the segments.``*``*/``//if (ReadElfHeader() &&//读取ELF文件头``//VerifyElfHeader() &&//验证文件头``//ReadProgramHeaders() &&//程序头表``//ReadSectionHeaders() &&//节头表``//ReadDynamicSection()) {//dynamic节头表``//did_read_ = true;``//}``// Read the ELF header and some of the segments.``if` `(!task->read(realpath.c_str(), file_stat.st_size)) {``soinfo_free(si);``task->set_soinfo(nullptr);``return` `false``;``}` `// find and set DT_RUNPATH and dt_soname``// Note that these field values are temporary and are``// going to be overwritten on soinfo::prelink_image``// with values from PT_LOAD segments.``const` `ElfReader& elf_reader = task->get_elf_reader();``for` `(``const` `ElfW(Dyn)* d = elf_reader.dynamic(); d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_RUNPATH) {``si->set_dt_runpath(elf_reader.get_string(d->d_un.d_val));``}``if` `(d->d_tag == DT_SONAME) {``si->set_soname(elf_reader.get_string(d->d_un.d_val));``}``}` `/**``* 加载当前库被哪个库依赖LoadTask``*/``for_each_dt_needed(task->get_elf_reader(), [&](``const` `char``* name) {``load_tasks->push_back(LoadTask::create(name, si, ns, task->get_readers_map()));``});` `return` `true``;``}` |
|-|-|

我们直接来到该方法看看这些方法具体怎么做，该方法处于linker_phdr.cpp中

代码如下

| 1234567891011121314151617181920212223242526 | `/**``* 读取ELF``* @param name``* @param fd``* @param file_offset``* @param file_size``*/``bool` `ElfReader::Read(``const` `char``* name,``int` `fd, off64_t file_offset, off64_t file_size) {``if` `(did_read_) {``return` `true``;``}``name_ = name;``fd_ = fd;``file_offset_ = file_offset;``file_size_ = file_size;` `if` `(ReadElfHeader() &&``//读取ELF文件头``VerifyElfHeader() &&``//验证文件头``ReadProgramHeaders() &&``//程序头表``ReadSectionHeaders() &&``//节头表``ReadDynamicSection()) {``//dynamic节头表``did_read_ =``true``;``}` `return` `did_read_;``}` |
|-|-|

我们挨个进去看，***ReadElfHeader***

pread64就是read系统调用，这里会进行读取fd_，然后读取的大小是sizeof(header_)，文件头的大小，读到header_指针处当中，大小是ElfW(Ehdr)类型是elf文件头的大小。VerifyElfHeader则是验证文件头magic、是32-bit还是64-bit、little-endian等等，比较简单就不贴代码了

代码如下

| 1234567891011121314 | `bool` `ElfReader::ReadElfHeader() {``ssize_t rc = TEMP_FAILURE_RETRY(pread64(fd_, &header_,``sizeof``(header_), file_offset_));``if` `(rc < 0) {``DL_ERR(``"can't read file \"%s\": %s"``, name_.c_str(),``strerror``(``errno``));``return` `false``;``}` `if` `(rc !=``sizeof``(header_)) {``DL_ERR(``"\"%s\" is too small to be an ELF executable: only found %zd bytes"``, name_.c_str(),``static_cast``<``size_t``>(rc));``return` `false``;``}``return` `true``;``}` |
|-|-|

接下来看看***ReadProgramHeaders***

该方法读取ProgramHeaders，第一个if，说明phdr_num_不得超过2个字节65536，然后根据elf的phdr_num，来计算size_t size = phdr_num_ * sizeof(ElfW(Phdr));，phdr_fragment_.Map会去调用mmap将ProgramHeaders部分映射到内存中，具体的映射结果的地址以及大小，保存在phdr_fragment_类型是 MappedFileFragment当中，至此，程序头表映射完毕。

代码如下

| 123456789101112131415161718192021222324252627282930 | `// Loads the program header table from an ELF file into a read-only private``// anonymous mmap-ed block.``bool` `ElfReader::ReadProgramHeaders() {``phdr_num_ = header_.e_phnum;` `// Like the kernel, we only accept program header tables that``// are smaller than 64KiB.``if` `(phdr_num_ < 1 \|\| phdr_num_ > 65536/``sizeof``(ElfW(Phdr))) {``DL_ERR(``"\"%s\" has invalid e_phnum: %zd"``, name_.c_str(), phdr_num_);``return` `false``;``}` `// Boundary checks``size_t` `size = phdr_num_ *``sizeof``(ElfW(Phdr));``if` `(!CheckFileRange(header_.e_phoff, size, alignof(ElfW(Phdr)))) {``DL_ERR_AND_LOG(``"\"%s\" has invalid phdr offset/size: %zu/%zu"``,``name_.c_str(),``static_cast``<``size_t``>(header_.e_phoff),``size);``return` `false``;``}` `if` `(!phdr_fragment_.Map(fd_, file_offset_, header_.e_phoff, size)) {``DL_ERR(``"\"%s\" phdr mmap failed: %s"``, name_.c_str(),``strerror``(``errno``));``return` `false``;``}` `phdr_table_ =``static_cast``<ElfW(Phdr)*>(phdr_fragment_.data());``return` `true``;``}` |
|-|-|

| 1234567891011121314151617 | `class` `MappedFileFragment {``public``:``MappedFileFragment();``~MappedFileFragment();` `bool` `Map(``int` `fd, off64_t base_offset,``size_t` `elf_offset,``size_t` `size);` `void``* data()``const` `{``return` `data_; }``size_t` `size()``const` `{``return` `size_; }``private``:``void``* map_start_;``size_t` `map_size_;``void``* data_;``size_t` `size_;` `DISALLOW_COPY_AND_ASSIGN(MappedFileFragment);``};` |
|-|-|

接下来看***ReadSectionHeaders***方法具体做了什么

读取section表，节区表的数量，计算size_t size = shdr_num_ * sizeof(ElfW(Shdr));调用shdr_fragment_.Map，和上面的代码一样，这里就不赘述了。

接下来是最后的ReadDynamicSection方法

方法开始就是遍历section表，寻找section的sh_type为***SHT_DYNAMIC***设置dynamic_shdr，然后遍历program表，寻找p_type为***PT_DYNAMIC***，设置pt_dynamic_offset = phdr->p_offset;和pt_dynamic_filesz = phdr->p_filesz;

然后开始校验dynamic_shdr是否和pt_dynamic_offset相同，然后后面还是一些校验逻辑，就不分析了，直接看主分支的核心流程。

dynamic_shdr是section类型，我们查看资料，可以看到，其中sh_link是获取dynamic section字符串表的在section表的位置，即strtab section。

然后设置到ElfReader当中dynamic_，上面获取的地址，都是设置ElfReader当中。

最后将程序头类型是dynamic，映射到内存当中。

这里联系结合《程序员的自我修养——链接、装载与库》书中的知识

![image](https://bbs.kanxue.com/upload/attach/202512/93CM8HURU59EUCK.jpg)

代码如下

| 12345678910111213141516171819202122232425 | `bool` `ElfReader::ReadSectionHeaders() {``shdr_num_ = header_.e_shnum;` `if` `(shdr_num_ == 0) {``DL_ERR_AND_LOG(``"\"%s\" has no section headers"``, name_.c_str());``return` `false``;``}` `size_t` `size = shdr_num_ *``sizeof``(ElfW(Shdr));``if` `(!CheckFileRange(header_.e_shoff, size, alignof(``const` `ElfW(Shdr)))) {``DL_ERR_AND_LOG(``"\"%s\" has invalid shdr offset/size: %zu/%zu"``,``name_.c_str(),``static_cast``<``size_t``>(header_.e_shoff),``size);``return` `false``;``}` `if` `(!shdr_fragment_.Map(fd_, file_offset_, header_.e_shoff, size)) {``DL_ERR(``"\"%s\" shdr mmap failed: %s"``, name_.c_str(),``strerror``(``errno``));``return` `false``;``}` `shdr_table_ =``static_cast``<``const` `ElfW(Shdr)*>(shdr_fragment_.data());``return` `true``;``}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445 | `bool` `ElfReader::ReadDynamicSection() {``// 1. Find .dynamic section (in section headers)``const` `ElfW(Shdr)* dynamic_shdr = nullptr;``for` `(``size_t` `i = 0; i < shdr_num_; ++i) {``if` `(shdr_table_[i].sh_type == SHT_DYNAMIC) {``dynamic_shdr = &shdr_table_ [i];``break``;``}``}``//省略校验相关代码` `// Make sure dynamic_shdr offset and size matches PT_DYNAMIC phdr``size_t` `pt_dynamic_offset = 0;``size_t` `pt_dynamic_filesz = 0;``for` `(``size_t` `i = 0; i < phdr_num_; ++i) {``const` `ElfW(Phdr)* phdr = &phdr_table_[i];``if` `(phdr->p_type == PT_DYNAMIC) {``pt_dynamic_offset = phdr->p_offset;``pt_dynamic_filesz = phdr->p_filesz;``}``}` `//省略校验相关代码`  `/**``* dynamic_shdr是section类型其中sh_link是获取dynamic section字符串表的在section表的位置，即strtab section``*/``const` `ElfW(Shdr)* strtab_shdr = &shdr_table_[dynamic_shdr->sh_link];` `//省略校验相关代码` `if` `(!dynamic_fragment_.Map(fd_, file_offset_, dynamic_shdr->sh_offset, dynamic_shdr->sh_size)) {``DL_ERR(``"\"%s\" dynamic section mmap failed: %s"``, name_.c_str(),``strerror``(``errno``));``return` `false``;``}` `dynamic_ =``static_cast``<``const` `ElfW(Dyn)*>(dynamic_fragment_.data());` `//省略校验相关代码` `strtab_ =``static_cast``<``const` `char``*>(strtab_fragment_.data());``strtab_size_ = strtab_fragment_.size();``return` `true``;``}` |
|-|-|

至此，ElfReader::***Read***方法到此结束 ，回到read调用处，就是上文的load_library方法的第二个重载方法，接着开始。

for_each_dt_needed方法是模板方法，该方法获取了dynamic地址，开始遍历，寻找DT_NEEDED类型，就是目标so依赖了哪些库，开始调用外部的lambda函数，加入到load_tasks当中，至此，此时load_tasks包含目标so、以及目标so被哪些库依赖、以及need的so

代码如下

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162636465 | `/**``* 2``*/``static` `bool` `load_library(android_namespace_t* ns,``LoadTask* task,``LoadTaskList* load_tasks,``int` `rtld_flags,``const` `std::string& realpath,``bool` `search_linked_namespaces) {``off64_t file_offset = task->get_file_offset();``const` `char``* name = task->get_name();``const` `android_dlextinfo* extinfo = task->get_extinfo();` `//省略代码` `//分配soinfo``soinfo* si = soinfo_alloc(ns, realpath.c_str(), &file_stat, file_offset, rtld_flags);``if` `(si == nullptr) {``return` `false``;``}` `//set_soinfo``task->set_soinfo(si);` `/**``* Read the ELF header and some of the segments.``*``*/``//if (ReadElfHeader() &&//读取ELF文件头``//VerifyElfHeader() &&//验证文件头``//ReadProgramHeaders() &&//程序头表``//ReadSectionHeaders() &&//节头表``//ReadDynamicSection()) {//dynamic节头表``//did_read_ = true;``//}``// Read the ELF header and some of the segments.``if` `(!task->read(realpath.c_str(), file_stat.st_size)) {``soinfo_free(si);``task->set_soinfo(nullptr);``return` `false``;``}` `// find and set DT_RUNPATH and dt_soname``// Note that these field values are temporary and are``// going to be overwritten on soinfo::prelink_image``// with values from PT_LOAD segments.``const` `ElfReader& elf_reader = task->get_elf_reader();``for` `(``const` `ElfW(Dyn)* d = elf_reader.dynamic(); d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_RUNPATH) {``si->set_dt_runpath(elf_reader.get_string(d->d_un.d_val));``}``if` `(d->d_tag == DT_SONAME) {``si->set_soname(elf_reader.get_string(d->d_un.d_val));``}``}` `/**``* 加载当前库被哪个库依赖LoadTask``*/``for_each_dt_needed(task->get_elf_reader(), [&](``const` `char``* name) {``load_tasks->push_back(LoadTask::create(name, si, ns, task->get_readers_map()));``});` `return` `true``;``}` |
|-|-|

| 12345678 | `template``<``typename` `F>``static` `void` `for_each_dt_needed(``const` `ElfReader& elf_reader, F action) {``for` `(``const` `ElfW(Dyn)* d = elf_reader.dynamic(); d->d_tag != DT_NULL; ++d) {``if` `(d->d_tag == DT_NEEDED) {``action(fix_dt_needed(elf_reader.get_string(d->d_un.d_val), elf_reader.name()));``}``}``}` |
|-|-|

至此find_library_internal方法到此结束，find_library_internal最后部分的尾巴，是在当load_library方法加载失败，再去linked_namespaces去查找，然后调用load_library，这部分不关注。

回到find_libraries方法当中，到此，Step 1结束。

## 总结

这两个步骤的，比较关注的是**如何进行加载so，映射了程序头表、节头表、dynamic section 到内存地址中**，这些地址都保存在了ElfReader当中。

最后笔者能力有限，本文难免存在疏漏或者理解错误，恳请读者不吝赐教与指正。

---

# 回复

## 回复 by KanXue_NG (#2)

*2025-12-3 09:49*

学习学习

## 回复 by guijingwen (#3)

*2025-12-3 10:35*

66

## 回复 by 李啊啊 (#4)

*2025-12-3 10:54*

66666666

## 回复 by Sharp_Wang (#5)

*2025-12-3 13:54*

666

## 回复 by Imxz (#6)

*2025-12-3 14:22*

TQL

## 回复 by mb_shndajve (#7)

*2025-12-3 14:38*

666

## 回复 by mb_jnmxfjku (#8)

*2025-12-3 14:46*

1

## 回复 by iBa0 (#9)

*2025-12-3 17:49*

123

## 回复 by onlythis (#10)

*2025-12-3 21:03*

66666666

## 回复 by 夜惜风雨 (#11)

*2025-12-3 21:06*

66666666

## 回复 by 带带弟弟吧 (#12)

*2025-12-3 21:20*

112345

## 回复 by mb_irhdtnzm (#13)

*2025-12-4 09:14*

666

## 回复 by huangjw (#14)

*2025-12-4 09:31*

很ok的

## 回复 by mb_pmgifpme (#15)

*2025-12-4 09:52*

1

## 回复 by LQ6H (#16)

*2025-12-4 10:20*

666

## 回复 by lqfcugo (#17)

*2025-12-4 10:21*

看看

## 回复 by xingbing (#18)

*2025-12-4 14:41*

看看

## 回复 by mb_uvyukvot (#19)

*2025-12-4 17:27*

666

## 回复 by TL549007501 (#20)

*2025-12-4 17:59*

666666666666

## 回复 by 掀起你的头盖骨 (#21)

*2025-12-4 18:01*

学习

## 回复 by buluo533 (#22)

*2025-12-5 08:16*

66666666

## 回复 by GEKEZYX (#23)

*2025-12-5 10:01*

666

## 回复 by uni7corn (#24)

*2025-12-5 12:26*

感谢分享。

## 回复 by bbpk (#25)

*2025-12-5 13:09*

6666

## 回复 by mb_fhpfcoqp (#26)

*2025-12-5 14:11*

666

## 回复 by yarobot (#27)

*2025-12-6 17:16*

666

## 回复 by mb_euhyowpw (#28)

*2025-12-6 21:06*

111

## 回复 by G33k3r (#29)

*2025-12-7 08:56*

大佬

## 回复 by supercuglong (#30)

*2025-12-7 23:58*

666666666666666

## 回复 by Heiyiren123 (#31)

*2025-12-8 02:34*

666，感谢分享！

## 回复 by mb_nhgfbijk (#32)

*2025-12-8 08:26*

666

## 回复 by wx-小萌新 (#33)

*2025-12-8 09:25*

6666

## 回复 by mb_pesxllvn (#34)

*2025-12-8 11:30*

666

## 回复 by mb_undsjfmp (#35)

*2025-12-8 16:43*

1

## 回复 by 沫水. (#36)

*2025-12-9 08:24*

学习

## 回复 by Ace_Heng (#37)

*2025-12-9 10:22*

看看

## 回复 by mb_jexyddof (#38)

*2025-12-12 14:55*

学习学习

## 回复 by mb_olonogae (#39)

*2025-12-13 15:26*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by godiand (#40)

*2025-12-13 19:46*

学习一下

## 回复 by ulong9527 (#41)

*2025-12-15 15:33*

6

## 回复 by mb_rrwegvyc (#42)

*2025-12-16 19:23*

66666666

## 回复 by daimubai (#43)

*2025-12-17 11:08*

学习了

## 回复 by mb_advzsyem (#44)

*2025-12-17 13:04*

感谢分享

## 回复 by JOE_TR13 (#45)

*2025-12-21 01:07*

学习一下

## 回复 by user_adb (#46)

*2025-12-24 09:14*

666

## 回复 by aceding (#47)

*2025-12-28 23:01*

感谢分享

## 回复 by 0x25519 (#48)

*2025-12-29 18:06*

学习学习

## 回复 by Bileton (#49)

*2026-1-3 00:42*

666

## 回复 by wx_coddvccwyh (#50)

*2026-1-3 02:04*

666

## 回复 by 温泉划水鱼 (#51)

*2026-1-5 01:09*

66

## 回复 by SkyerHw (#52)

*2026-1-8 11:49*

6666

## 回复 by Whoami默 (#53)

*2026-1-14 22:36*

666

## 回复 by 去玩儿童 (#54)

*2026-1-19 05:04*

666

## 回复 by 北辰清影 (#55)

*2026-1-19 09:40*

66

## 回复 by Dem0li (#56)

*2026-1-19 10:38*

1

## 回复 by XCicada (#57)

*2026-1-24 20:46*

回复来看看，先谢过楼主！

## 回复 by mingyeqf (#58)

*2026-1-26 19:27*

666

## 回复 by 独一无二_370133 (#59)

*2026-2-5 14:37*

1122

## 回复 by mb_ugryjzdr (#60)

*2026-2-6 16:58*

666

## 回复 by birdcard (#61)

*2026-2-7 21:38*

6666666666

## 回复 by 落花为谁 (#62)

*2026-2-10 14:36*

学习了

## 回复 by qq戚导 (#63)

*2026-2-11 18:06*

666

## 回复 by mb_kxikBxpy (#64)

*2026-2-11 18:14*

6666

## 回复 by superlahm (#65)

*2026-2-11 19:17*

666666

## 回复 by XJ。 (#66)

*2026-2-12 11:30*

1

## 回复 by qig (#67)

*2026-2-13 07:54*

学习学习

## 回复 by 饮岁 (#68)

*2026-2-24 10:10*

666

## 回复 by dsr000 (#69)

*2026-2-25 16:39*

666

## 回复 by K4NG (#70)

*2026-2-25 21:24*

学习

## 回复 by mb_uzmffdbw (#71)

*2026-2-26 15:58*

666

## 回复 by Cure. (#72)

*2026-2-26 20:55*

666

## 回复 by YOLO199393 (#73)

*2026-2-26 23:09*

66

## 回复 by wx_Y_786749 (#74)

*2026-2-28 10:45*

nice

## 回复 by 周凡_693405 (#75)

*2026-3-2 11:29*

666

## 回复 by jaefern (#76)

*2026-3-4 08:20*

666

## 回复 by 俱往矣 (#77)

*2026-3-5 21:36*

6

## 回复 by mb_stdlrcgp (#78)

*2026-3-5 21:45*

6666

## 回复 by SomeMx (#79)

*2026-3-6 02:36*

学习一下

## 回复 by mb_yfmtnfii (#80)

*2026-3-6 16:35*

1

## 回复 by Hidd3n_c0d3r (#81)

*2026-3-6 17:32*

666

## 回复 by mb_hziqyrum (#82)

*2026-3-7 18:40*

666

## 回复 by Elice (#83)

*2026-3-10 11:23*

666

## 回复 by 菜鸟9527 (#84)

*2026-3-16 20:01*

6666

## 回复 by mb_mihutdve (#85)

*2026-3-18 20:48*

666

## 回复 by 晴空万里丶 (#86)

*2026-3-21 00:12*

学习下

## 回复 by devil_1 (#87)

*2026-3-21 19:47*

66

## 回复 by mb_foxyttcl (#88)

*2026-3-23 10:08*

666666

## 回复 by sleep4r (#89)

*2026-3-29 17:10*

666

## 回复 by 星辰北天 (#90)

*2026-3-29 17:34*

学习一下

## 回复 by 小迷糊ddd (#91)

*2026-4-5 21:18*

感谢分享，认真学习。

## 回复 by maomaolk (#92)

*2026-6-9 15:38*

6666

## 回复 by afcentry (#93)

*2026-7-14 15:26*

6

## 回复 by mb_fafswnif (#94)

*2026-7-14 15:35*

感谢分享

## 回复 by mb_qtffppvh (#95)

*2026-7-20 21:53*

666666
