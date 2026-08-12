---
title: '[分享]nike wtoken'
url: https://bbs.kanxue.com/thread-279374.htm
tid: 279374
author: 一只笨猫
date: '2023-10-27'
tags: [Android安全, 分享, 逆向分析, 其他]
crawled_at: '2026-08-12T04:02:07+00:00'
replies: 10
---

![图片描述](https://bbs.kanxue.com/upload/attach/202310/890609_9EH4K8EBT9DJZFX.webp)

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190 | `package wtoken;` `import` `com.github.unidbg.AndroidEmulator;``import` `com.github.unidbg.Emulator;` `import` `com.github.unidbg.arm.context.EditableArm32RegisterContext;``import` `com.github.unidbg.``file``.FileResult;``import` `com.github.unidbg.``file``.IOResolver;``import` `com.github.unidbg.``file``.linux.AndroidFileIO;``import` `com.github.unidbg.linux.android.AndroidARMEmulator;``import` `com.github.unidbg.linux.android.AndroidEmulatorBuilder;``import` `com.github.unidbg.linux.android.AndroidResolver;``import` `com.github.unidbg.linux.android.dvm.``*``;``import` `com.github.unidbg.linux.android.dvm.array.ByteArray;``import` `com.github.unidbg.linux.``file``.ByteArrayFileIO;``import` `com.github.unidbg.linux.``file``.DumpFileIO;``import` `com.github.unidbg.memory.Memory;``import` `com.github.unidbg.memory.SvcMemory;``import` `com.github.unidbg.spi.SyscallHandler;``import` `com.github.unidbg.unix.UnixSyscallHandler;``import` `com.sun.jna.Pointer;` `import` `java.io.``File``;``import` `java.io.IOException;``import` `java.nio.charset.StandardCharsets;``import` `java.util.concurrent.ThreadLocalRandom;`  `public` `class` `TigerTallyAPI extends AbstractJni implements IOResolver<AndroidFileIO> {``private final AndroidEmulator emulator;``private final VM vm;``AndroidEmulatorBuilder androidEmulatorBuilder` `=` `new AndroidEmulatorBuilder(false) {``@Override``public AndroidEmulator build() {``return` `new AndroidARMEmulator(``"com.nike.snkrs"``,rootDir,backendFactories) {``@Override``protected UnixSyscallHandler createSyscallHandler(SvcMemory svcMemory) {``return` `new PddArmSysCallHand(svcMemory);``}``};``}``};``public` `class` `PddArmSysCallHand extends com.github.unidbg.linux.ARM32SyscallHandler {``public PddArmSysCallHand(SvcMemory svcMemory) {``super``(svcMemory);``}``@Override``protected boolean handleUnknownSyscall(Emulator emulator,` `int` `NR) {``switch (NR) {``case` `190``:``vfork(emulator);``return` `true;``case` `359``:``pipe2(emulator);``return` `true;``}` `return` `super``.handleUnknownSyscall(emulator, NR);``}``private void vfork(Emulator<?> emulator) {``EditableArm32RegisterContext context` `=` `(EditableArm32RegisterContext) emulator.getContext();``int` `childPid` `=` `emulator.getPid()` `+` `ThreadLocalRandom.current().nextInt(``256``);``int` `r0` `=` `0``;``r0` `=` `childPid;``System.out.println(``"vfork pid="` `+` `r0);``context.setR0(r0);``}`  `@Override``protected` `int` `pipe2(Emulator<?> emulator) {``EditableArm32RegisterContext context` `=` `(EditableArm32RegisterContext) emulator.getContext();``Pointer pipefd` `=` `context.getPointerArg(``0``);``int` `flags` `=` `context.getIntArg(``1``);``int` `write` `=` `getMinFd();``this.fdMap.put(write, new DumpFileIO(write));``int` `read` `=` `getMinFd();``String stdout` `=` `"2a6dffba-811a-43e5-96ee-638e71784cb7"``;``this.fdMap.put(read, new ByteArrayFileIO(``0``,` `"pipe2_read_side"``, stdout.getBytes()));``pipefd.setInt(``0``, read);``pipefd.setInt(``4``, write);``System.out.println(``"pipe2 pipefd="` `+` `pipefd` `+` `", flags=0x"` `+` `flags` `+` `", read="` `+` `read` `+` `", write="` `+` `write` `+` `", stdout="` `+` `stdout);``context.setR0(``0``);``return` `0``;``}``}``public TigerTallyAPI(String apkPath) {``emulator` `=` `androidEmulatorBuilder.build();``SyscallHandler<AndroidFileIO> syscallHandler` `=``emulator.getSyscallHandler();``syscallHandler.setVerbose(true);``syscallHandler.addIOResolver(this);``Memory memory` `=` `emulator.getMemory();``memory.setLibraryResolver(new AndroidResolver(``23``));``vm` `=` `emulator.createDalvikVM(new` `File``(apkPath));``vm.setJni(this);``vm.setVerbose(true);`  `}``public static void main(String[] args) {``TigerTallyAPI tigerTallyAPI` `=` `new TigerTallyAPI(``"F:\\Project\\WTOKEN\\nike.apk"``);``AndroidEmulator emulator` `=` `tigerTallyAPI.emulator;``DalvikModule dalvikModule` `=` `tigerTallyAPI.vm.loadLibrary(new` `File``(``"F:\\Project\\WTOKEN\\libtiger_tally.so"``), true);``dalvikModule.callJNI_OnLoad(emulator);``VM vm` `=` `tigerTallyAPI.vm;``DvmClass dvmClass` `=` `vm.resolveClass(``"com/aliyun/TigerTally/t/B"``);``dvmClass.callStaticJniMethodObject(emulator,``"genericNt1(ILjava/lang/String;)I"``,``1``,new StringObject(vm,``"j0m4PjXNgOX_A_ZJXjBNgJ0DRtp_VQWwEMS5DkAJUJsKPR-0r8PqOkWMrhwymjZCoyOzBW2aqkrY8Tw9Cbwyl9fMOlOMPTC7_sOho2t_mOpdhkcQrWAc8fv_EATLX5DSrlve4QlMpMZtIuTfry6bm4VRSapMNRLn_dOCZ06VbLQ="``));``dvmClass.callStaticJniMethodObject(emulator,``"genericNt2(ILjava/lang/String;)I"``,``2``,new StringObject(vm,``"F5ulsYPu9bEb+ZoPdcd/wZxh7LGkq2jguP1rn2f5KYoOwggyQCbyJWB5xvZB1Z/vPiRsAIRa9iwncJmK0dO/xQ=="``));``DvmObject<?> dvmObject` `=` `dvmClass.callStaticJniMethodObject(emulator,``"genericNt3(I[B)Ljava/lang/String;"``,``1``,new ByteArray(vm,``"2a6dffba-811a-43e5-96ee-638e71784cb7"``.getBytes(StandardCharsets.UTF_8)));``System.out.println(dvmObject.getValue().toString());``tigerTallyAPI.destroy();` `}``@Override``public DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch (signature){``case` `"com/aliyun/TigerTally/s/A->ct()Landroid/content/Context;"``:``return` `vm.resolveClass(``"android/app/Application"``,vm.resolveClass(``"android/content/ContextWrapper"``,vm.resolveClass(``"android/content/Context"``))).newObject(signature);``case` `"com/aliyun/TigerTally/A->pb(Ljava/lang/String;[B)Ljava/lang/String;"``:``return` `new StringObject(vm,``"F5ulsYPu9bEb+ZoPdcd/wZxh7LGkq2jguP1rn2f5KYoOwggyQCbyJWB5xvZB1Z/vPiRsAIRa9iwncJmK0dO/xQ=="``);``}``return` `super``.callStaticObjectMethodV(vm, dvmClass, signature, vaList);``}` `@Override``public DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch (signature){``case` `"android/content/pm/PackageManager->getApplicationInfo(Ljava/lang/String;I)Landroid/content/pm/ApplicationInfo;"``:``return` `vm.resolveClass(``"Landroid/content/pm/ApplicationInfo;"``).newObject(signature);``case` `"android/content/pm/PackageManager->getApplicationLabel(Landroid/content/pm/ApplicationInfo;)Ljava/lang/CharSequence;"``:``return` `new StringObject(vm,``"Ljava/lang/CharSequence;"``);``case` `"android/app/Application->getFilesDir()Ljava/io/File;"``:``return` `vm.resolveClass(``"Ljava/io/File;"``);``case` `"java/lang/String->getAbsolutePath()Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/app/Application->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;"``:``return` `vm.resolveClass(``"Landroid/content/SharedPreferences;"``);``case` `"java/lang/Class->getAbsolutePath()Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"java/lang/Class->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/app/Application->getPackageCodePath()Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"com/aliyun/TigerTally/s/A$AA->en(Ljava/lang/String;)Ljava/lang/String;"``:``return` `new StringObject(vm,``"eb32139f977b4e12abca93113c3d8486557dfeb"``);``case` `"com/aliyun/TigerTally/s/A$BB->en(Ljava/lang/String;)Ljava/lang/String;"``:``return` `new StringObject(vm,``"eb32139f977b4e12abca93113c3d8486557dfeb"``);` `}``return` `super``.callObjectMethodV(vm, dvmObject, signature, vaList);``}``@Override``public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {``switch (signature){``case` `"android/os/Build->BRAND:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build->MODEL:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build$VERSION->RELEASE:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``case` `"android/os/Build->DEVICE:Ljava/lang/String;"``:``return` `new StringObject(vm,``"Ljava/lang/String;"``);``}``return` `super``.getStaticObjectField(vm,dvmClass,signature);``}``public void destroy() {``try` `{``emulator.close();``} catch (IOException e) {``e.printStackTrace();``}``}``@Override``public DvmObject<?> newObjectV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch (signature){``case` `"com/aliyun/TigerTally/s/A$AA-><init>()V"``:``return` `vm.resolveClass(``"com/aliyun/TigerTally/s/A$AA"``).newObject(signature);``case` `"com/aliyun/TigerTally/s/A$BB-><init>()V"``:``return` `vm.resolveClass(``"com/aliyun/TigerTally/s/A$BB"``).newObject(signature);` `}``return` `super``.newObjectV(vm,dvmClass,signature,vaList);``}``@Override``public FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname,` `int` `oflags) {``return` `null;``}` `}` |
|-|-|

---

# 回复

## 回复 by 淡定小胖子 (#2)

*2023-10-28 11:04*

过不了吧你这个

## 回复 by 秋狝 (#3)

*2023-10-28 23:28*

感谢分享

## 回复 by 一只笨猫 (#4)

*2023-10-29 16:45*

>
> [淡定小胖子](https://bbs.kanxue.com/user-781457.htm)
>
>  过不了吧你这个
>
>

思路 肯定不会直接放能过的出来

## 回复 by 未露姓名陈某 (#5)

*2023-11-3 14:30*

阿里的那个安全sdk吗

## 回复 by mb_ddzpjlyg (#6)

*2024-6-4 16:56*

有能过的方案吗？有chang

## 回复 by mb_fprfytok (#7)

*2024-6-4 22:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_ddzpjlyg](https://bbs.kanxue.com/user-985346.htm)
>
>  有能过的方案吗？有chang
>
>

最近搞某空搞定了这个

## 回复 by mb_zekgiifu (#8)

*2024-6-26 15:59*

怎么联系

## 回复 by zhanyong174 (#9)

*2024-9-13 04:16*

>
> [猫盾科技](https://bbs.kanxue.com/user-890609.htm)
>
>  思路 肯定不会直接放能过的出来
>
>

找你有点东西做下

## 回复 by zhanyong174 (#10)

*2024-9-19 02:53*

>
> [秋狝](https://bbs.kanxue.com/user-825507.htm)
>
>  感谢分享
>
>

你能过？

## 回复 by mb_nqzvgcge (#11)

*2024-10-12 14:55*

nzcv: N=0, Z=0, C=1, V=0, EL0, use SP_EL0
    [libtiger_tally.so 0x084eb0] [ab0bcdf2] 0x12084eb0: "movk x11, #0x685d, lsl #32"
=> *[libtiger_tally.so*0x084eb4]*[48e03bd5]*0x12084eb4:*"mrs x8, cntvct_el0"
    [libtiger_tally.so 0x084eb8] [09e03bd5] 0x12084eb8: "mrs x9, cntfrq_el0"
这个位置应该是获取计时失败，求能解决办法
