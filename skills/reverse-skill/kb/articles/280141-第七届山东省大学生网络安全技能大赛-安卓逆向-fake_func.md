---
title: '[原创]第七届山东省大学生网络安全技能大赛. 安卓逆向 fake_func'
url: https://bbs.kanxue.com/thread-280141.htm
tid: 280141
author: zhenwo
date: '2024-01-08'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:33:53+08:00'
replies: 1
---

# 第七届山东省大学生网络安全技能大赛. 安卓逆向 fake_func

其实这个刚开始认为很简单，直接静态分析了安卓层的代码和so代码直接一看stcmp函数，天真的以为就是上下文中看到的base64的字符串，结果提交错误，把字符串解码提交也不对。

故认真搞了一下，学到了不少东西。

大家先不急着往下看，可以自己使用jadx和IDA分析下，看看会不会被绕进去。

## 观察

后缀是apk，先拖入夜神模拟器看看。只有个输入框。随便输入些字符串，看看效果。木有什么按钮，一通tab加回车，居然可以触发逻辑，应该还有个按钮。

 ![image](https://bbs.kanxue.com/upload/attach/202401/396123_FKEH7MYVNERKME3.webp)

## 逆向

### 安卓层面逆向分析

直接拖入jadx中，找到MainActivity，代码逻辑很清晰。

| 123456789101112131415161718 | `public` `class` `MainActivity` `extends` `AppCompatActivity {``/* JADX INFO: Access modifiers changed from: protected */``@Override` `// android.support.v7.app.AppCompatActivity, android.support.v4.app.FragmentActivity, android.support.v4.app.SupportActivity, android.app.Activity``public` `void` `onCreate(Bundle bundle) {``super``.onCreate(bundle);``setContentView(R.layout.activity_main);``((Button) findViewById(R.id.button)).setOnClickListener(``new` `View.OnClickListener() {` `// from class: com.example.p7xxtmx_g.fakefunc.MainActivity.1``@Override` `// android.view.View.OnClickListener``public` `void` `onClick(View view) {``if` `(check.checkflag(((EditText) MainActivity.``this``.findViewById(R.id.editText)).getText().toString())) {``Toast.makeText(MainActivity.``this``,` `"you are right~!"``,` `1``).show();``}` `else` `{``Toast.makeText(MainActivity.``this``,` `"wrong!"``,` `1``).show();``}``}``});``}``}` |
|-|-|

代码解读：

- button点击时：获取editText字符串传输check.checkflag函数，返回true或false，有不同的提示。

### c/c++逆向分析

关键就是check.checkflag函数，双击checkflag函数，可以看到如下代码

| 1234567 | `public` `class` `check {``public` `static` `native` `boolean` `checkflag(String str);` `static` `{``System.loadLibrary(``"checkso"``);``}``}` |
|-|-|

从代码可以看出，真正的逻辑来自native层的so库。根据以往开发经验，so文件会打包在资源中。

so在资源文件->lib->armeabi-v7a文件夹下，保存libchecso.so到本地。

用IDA64分析so文件。通过导出表很快定位到函数。

| Name | Address Ordinal |
|-|-|
| JNI_OnLoad | 0000000000000E84 |
| Java_com_example_p7xxtmx_1g_fakefunc_check_checkflag | 0000000000000E54 |
| inlineHook | 0000000000001DCC |
| inlineUnHook | 0000000000001A98 |
| registerInlineHook | 00000000000018BC |
| relocateInstruction | 0000000000001FA8 |
| inlineUnHookAll | 0000000000001D60 |
| inlineHookAll | 0000000000001ED8 |

checkflag函数如下

```
.text:00000E54 Java_com_example_p7xxtmx_1g_fakefunc_check_checkflag
.text:00000E54                                         ; DATA XREF: LOAD:00000230↑o
.text:00000E54 ; __unwind {
.text:00000E54                 PUSH            {R4,R6,R7,LR}
.text:00000E56                 ADD             R7, SP, #8
.text:00000E58                 MOV             R1, R2
.text:00000E5A                 LDR             R2, [R0]
.text:00000E5C                 LDR.W           R3, [R2,#0x2A4]
.text:00000E60                 MOVS            R2, #0
.text:00000E62                 BLX             R3
.text:00000E64                 MOV             R4, R0
.text:00000E66                 BL              sub_E08
.text:00000E6A                 LDR             R0, =(off_6004 - 0xE70) ; "c2RuaXNjc2RuaXNjYWJjZA=="
.text:00000E6C                 ADD             R0, PC  ; off_6004
.text:00000E6E                 LDR             R1, [R0] ; "c2RuaXNjc2RuaXNjYWJjZA=="
.text:00000E70                 MOV             R0, R4  ; char *
.text:00000E72                 BLX             strcmp
.text:00000E76                 CLZ.W           R0, R0
.text:00000E7A                 LSRS            R0, R0, #5
.text:00000E7C                 POP             {R4,R6,R7,PC}
.text:00000E7C ; End of function Java_com_example_p7xxtmx_1g_fakefunc_check_checkflag
```

看到了strcmp函数感觉，找到关键点了。对arm的传参约定做了下功课，逻辑应该是这样strcmp(r0,r1)。十有八九字符串“c2RuaXNjc2RuaXNjYWJjZA==”就是flag，保存到txt文档，感觉很简单草草记录下过程，关闭文件夹，做下一题了。

## 题如其名《假的函数》

闲暇之际，把flag提交了，把积分兑一下。其他2个顺利的拿到了积分。这个却翻了车，试了好次都不行，又分析了下，发现还有个base64的字符，又拿去试了也不行，看来不是这么简单。

### 展露头角

把导出表又看了下，有几个和hook相关的函数，再结合下题名，应该用到了hook，开始追踪，这几个函数函数的调用，IDA中一通交叉引用，感觉都不对。

### 误打误撞

感觉IDA7.5对arm支持的不太好，没有f5的IDA看着真不好。既然IDA不行，试试其他反汇编工具，先后试了下ninja和Ghidra感觉c代码还原都有那么点意思。

Ninja

| 123456789 | `00000e54`  `uint32_t Java_com_example_p7xxtmx_1g_fakefunc_check_checkflag(int32_t``*` `arg1)``00000e62`      `char``*` `r0` `=` `(``*``(``*``arg1` `+` `0x2a4``))()``00000e66`      `sub_e08()``00000e76`      `int32_t temp0` `=` `0``00000e76`      `int32_t i` `=` `strcmp(r0, data_6004)``00000e76`      `while` `(i !``=` `0``)``00000e76`          `i` `=` `i u>>` `1``00000e76`          `temp0` `=` `temp0` `+` `1``00000e7c`      `return` `(``0x20` `-` `temp0) u>>` `5` |
|-|-|

Ghidra,我标注了些函数名，还导入了些java的相关数据类型。安卓逆向之自动化JNI静态分析

| 123456789101112 | `void Java_com_example_p7xxtmx_1g_fakefunc_check_checkflag(JNIEnv` `*``env,jclass clazz,jstring a1)` `{``char` `*``__s1;``int` `iVar1;` `__s1` `=` `(``*``(``*``env)``-``>GetStringUTFChars)((JNIEnv` `*``)env,a1,(jboolean` `*``)``0x0``);``base64De_16004();``iVar1` `=` `strcmp(__s1,PTR_DAT_00016004);``count_leading_zeroes(iVar1);``return``;``}` |
|-|-|

继续上面的疑虑，在ninja和Ghidra中对hook相关函数进行引用追踪，ninja没有找到什么有用的线索和信息。

但是Ghidra中有了线索。

### 峰回路转

在Ghidra中查看导出函数时，无意间双击到了_INIT_0_函数，居然调用了registerInlineHook，然后gooogle了_INIT_0_，随后这一'__DT_INIT_ARRAY'关键字进入了我的视野，[https://docs.oracle.com/cd/E19683-01/816-1386/6m7qcobks/index.html。](https://docs.oracle.com/cd/E19683-01/816-1386/6m7qcobks/index.html%E3%80%82)

| 12345 | `在将控制权转移到应用程序之前，运行时链接器会处理应用程序及其依赖项中找到的任何初始化部分。.preinit_array 、.init_array和.init节是在构建动态对象时由链接编辑器创建的。这些部分分别标有.dynamic标签DT_PREINIT_ARRAY、DT_INIT_ARRAY和DT_INIT。请参阅“初始化和终止部分”。` `地址包含在DT_PREINIT_ARRAY和DT_INIT_ARRAY指定的数组中的函数由运行时链接器按照其地址在数组中出现的顺序执行。如果对象同时包含DT_INIT和DT_INIT_ARRAY条目，则DT_INIT条目引用的函数将在该对象的DT_INIT_ARRAY条目引用的函数之前处理。` `动态可执行文件可以在.preinit_array部分提供预初始化函数。这些函数在运行时链接器构建进程映像并执行重定位之后但在任何其他初始化函数之前执行。共享对象中不允许使用预初始化函数` |
|-|-|

so在加载时会调用这些初始化函数。

### 柳暗花明

| 1234567891011121314 | `int` `_INIT_0(void)``{``int` `iVar1;` `iVar1` `=` `registerInlineHook(strcmp,FUN_00010e28` `+` `1``,&DAT_00016008_orgFun);``if` `(iVar1 !``=` `0``) {``return` `0xffffffff``;``}``iVar1` `=` `inlineHook(strcmp);``if` `(iVar1 !``=` `0``) {``iVar1` `=` `-``1``;``}``return` `iVar1;``}` |
|-|-|

通过代码可以猜测出，函数strcmp被劫持了，通过观察对strcmp和jstrcmp的引用，可以确定so中只有一处对strcmp的调用就是 checkflag函数。

那么这样就会改变函数流程，strcmp不是比较字符串这么简单了。

根据第二参数FUN_00010e28 + 1找到函数如下

| 123456789101112 | `void Proc_00010e28(undefined4 strKey)` `{``undefined4 uVar1;` `uVar1` `=` `base64De_16004();``uVar1` `=` `EncryptEncode(strKey,uVar1);``/``*` `WARNING: Could` `not` `recover jumptable at` `0x00010e48``. Too many branches` `*``/``/``*` `WARNING: Treating indirect jump as call` `*``/``(``*``strcmp_jmp)(uVar1,``"K4/7/faihmk9/WEMlfuFdpgrP86ckd4oQQ/UeAiZdx8="``);``return``;``}` |
|-|-|

### 又一村

对hook的回调进行深入分析后，感觉后面的代码看不明白了，感觉后面应该是加密算法，因为需要base64解码，不是对常规的字符串进行处理，应该就是对称算法。

几款PE的查加密算法都不好用，这里直接借助IDA8.3 findcrypt插件，找到了相关线索。

| Address | Rules file | Name | String | Value |
|-|-|-|-|-|
| .rodata:00004255 | global | RijnDael_AES_CHAR_4255 | $c0 | b'c\|w{\xf2ko\xc50\x01g+\xfe\xd7\xabv\xca\x82\xc9}\xfaYG\xf0\xad\xd4\xa2\xaf\x9c\xa4r\xc0' |
| .rodata:00004255 | global | RijnDael_AES_LONG_4255 | $c0 | b'c\|w{\xf2ko\xc50\x01g+\xfe\xd7\xabv\xca\x82\xc9}\xfaYG\xf0\xad\xd4\xa2\xaf\x9c\xa4r\xc0' |
| .rodata:00004355 | global | RijnDael_AES_LONG_inv_4355 | $c0 | b'R\tj\xd506\xa58\xbf@\xa3\x9e\x81\xf3\xd7\xfb |
| .rodata:00004156 | global | RijnDael_AES_RCON_4156 | $c0 | b'\x8d\x01\x02\x04\x08\x10 @\x80\x1b6l\xd8\xabM\x9a' |
| .rodata:00004189 | global | RijnDael_AES_RCON_4189 | $c0 | b'\x8d\x01\x02\x04\x08\x10 @\x80\x1b6l\xd8\xabM\x9a' |
| .rodata:000041BC | global | RijnDael_AES_RCON_41BC | $c0 | b'\x8d\x01\x02\x04\x08\x10 @\x80\x1b6l\xd8\xabM\x9a' |
| .rodata:000041EF | global | RijnDael_AES_RCON_41EF | $c0 | b'\x8d\x01\x02\x04\x08\x10 @\x80\x1b6l\xd8\xabM\x9a' |
| .rodata:00004222 | global | RijnDael_AES_RCON_4222 | $c0 | b'\x8d\x01\x02\x04\x08\x10 @\x80\x1b6l\xd8\xabM\x9a' |
| .rodata:00004455 | global | BASE64_table_4455 | $c0 | b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/' |

根据ADES提示,以及查阅《加密与解密》书籍，逐步确定了AES_SBOX相关数据。

| 123456789101112131415161718 | `AES_SBOX                                        XREF[``5``]:     FUN_00010f24:``00010ff2``(R),` `FUN_0001105c:``000110d2``(R),` `FUN_0001105c:``000110d8``(R),` `FUN_0001105c:``000110dc``(R),` `FUN_0001105c:``000110e0``(R)` `00014255` `63`              `??` `63h`    `c``00014256` `7c`              `??` `7Ch`    `\|``00014257` `77`              `??` `77h`    `w``00014258` `7b`              `??` `7Bh`    `{``00014259` `f2              ??         F2h``0001425a` `6b`              `??` `6Bh`    `k``0001425b` `6f`              `??` `6Fh`    `o``0001425c` `c5              ??         C5h``0001425d` `30`              `??` `30h`    `0``0001425e` `01`              `??` `01h``0001425f` `67`              `??` `67h`    `g``00014260` `2b`              `??` `2Bh`    `+``00014261` `fe              ??         FEh` |
|-|-|

根据AES_SBOX相关的引用确定应用了AES的加密运算。函数 FUN_00010f24 部分代码。

| 123456789 | `while` `(iVar12 != 4) {``iVar16 = 0;``while` `(iVar16 != 4) {``*(undefined *)(iVar15 + iVar16 * 4) = (&AES_SBOX)[*(byte *)(iVar15 + iVar16 * 4)];``iVar16 = iVar16 + 1;``}``iVar15 = iVar15 + 1;``iVar12 = iVar12 + 1;``}` |
|-|-|

以上位4 x 4 的subBytes操作。

这样通过梳理都能说的过去了。

| 123456789101112 | `void` `Proc_00010e28(undefined4 strInput)` `{``undefined4 uVar1;` `uVar1 = base64De_16004();``uVar1 = EncryptEncode(strInput,uVar1);``/* WARNING: Could not recover jumptable at 0x00010e48. Too many branches */``/* WARNING: Treating indirect jump as call */``(*strcmp_jmp)(uVar1,``"K4/7/faihmk9/WEMlfuFdpgrP86ckd4oQQ/UeAiZdx8="``);``return``;``}` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `undefined4 EncryptEncode(``char` `*param_1,undefined4 param_2)` `{``size_t` `sVar1;``void` `*__ptr;``int` `iVar2;``void` `*__ptr_00;``undefined4 uVar3;``char` `*pcVar4;``char` `cVar5;``int` `iVar6;``size_t` `__size;` `sVar1 =` `strlen``(param_1);``if` `((``int``)sVar1 < 0x10) {``__ptr =` `malloc``(0x10);``iVar2 = 0;``while` `(iVar2 != 0x10) {``pcVar4 = &UNK_00014156 + -sVar1;``if` `(iVar2 < (``int``)sVar1) {``pcVar4 = param_1 + iVar2;``}``*(``char` `*)((``int``)__ptr + iVar2) = *pcVar4;``iVar2 = iVar2 + 1;``}``__size = 0x10;``}``else` `{``__size = sVar1 + 0x10 & 0xfffffff0;``__ptr =` `malloc``(__size);``iVar2 = 0;``while` `(iVar2 < (``int``)__size) {``if` `(iVar2 < (``int``)sVar1) {``pcVar4 = param_1 + iVar2;``LAB_00011402:``cVar5 = *pcVar4;``}``else` `{``pcVar4 = &DAT_00014146 + (__size - sVar1);``if` `((sVar1 & 0xf) != 0)` `goto` `LAB_00011402;``cVar5 =` `'\x10'``;``}``*(``char` `*)((``int``)__ptr + iVar2) = cVar5;``iVar2 = iVar2 + 1;``}``}``__ptr_00 =` `malloc``(__size);``iVar6 = 0;``iVar2 = 0;``while` `(iVar2 < (``int``)(__size + ((uint)((``int``)__size >> 0x1f) >> 0x1c)) >> 4) {``AesEncrypt((``int``)__ptr + iVar6,param_2,(``int``)__ptr_00 + iVar6);``iVar6 = iVar6 + 0x10;``iVar2 = iVar2 + 1;``}``uVar3 = base64Encode(__ptr_00,__size);``free``(__ptr);``free``(__ptr_00);``return` `uVar3;``}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293 | `void` `AesEncrypt(``int` `param_1,undefined4 param_2,``int` `param_3)` `{``byte bVar1;``undefined uVar2;``undefined uVar3;``undefined uVar4;``byte bVar5;``byte bVar6;``undefined uVar7;``undefined uVar8;``byte bVar9;``byte bVar10;``byte bVar11;``int` `iVar12;``uint uVar13;``int` `iVar14;``int` `iVar15;``int` `iVar16;``uint local_2c;``int` `*local_30;` `iVar15 = 0;``while` `(iVar15 != 0x10) {``*(undefined *)(param_3 + iVar15) = *(undefined *)(param_1 + iVar15);``iVar15 = iVar15 + 1;``}``local_30 = &DAT_000160bc;``DAT_000160bc = param_3;``DAT_000160c0 = param_2;``FUN_0001105c();``FUN_00011524(0);``uVar13 = 1;``while``(` `true` `) {``iVar14 = *local_30;``iVar12 = 0;``iVar15 = iVar14;``while` `(iVar12 != 4) {``iVar16 = 0;``while` `(iVar16 != 4) {``*(undefined *)(iVar15 + iVar16 * 4) = (&AES_SBOX)[*(byte *)(iVar15 + iVar16 * 4)];``iVar16 = iVar16 + 1;``}``iVar15 = iVar15 + 1;``iVar12 = iVar12 + 1;``}``uVar2 = *(undefined *)(iVar14 + 1);``uVar7 = *(undefined *)(iVar14 + 2);``uVar8 = *(undefined *)(iVar14 + 3);``uVar3 = *(undefined *)(iVar14 + 0xd);``*(undefined *)(iVar14 + 1) = *(undefined *)(iVar14 + 5);``uVar4 = *(undefined *)(iVar14 + 6);``*(undefined *)(iVar14 + 5) = *(undefined *)(iVar14 + 9);``*(undefined *)(iVar14 + 0xd) = uVar2;``*(undefined *)(iVar14 + 9) = uVar3;``*(undefined *)(iVar14 + 2) = *(undefined *)(iVar14 + 10);``*(undefined *)(iVar14 + 10) = uVar7;``*(undefined *)(iVar14 + 6) = *(undefined *)(iVar14 + 0xe);``*(undefined *)(iVar14 + 0xe) = uVar4;``*(undefined *)(iVar14 + 3) = *(undefined *)(iVar14 + 0xf);``*(undefined *)(iVar14 + 0xf) = *(undefined *)(iVar14 + 0xb);``*(undefined *)(iVar14 + 0xb) = *(undefined *)(iVar14 + 7);``*(undefined *)(iVar14 + 7) = uVar8;``if` `(9 < (uVar13 & 0xff))` `break``;``iVar15 = 0;``while` `(iVar15 != 4) {``iVar12 = iVar14 + iVar15 * 4;``bVar9 = *(byte *)(iVar14 + iVar15 * 4);``bVar5 = *(byte *)(iVar12 + 1);``bVar6 = *(byte *)(iVar12 + 2);``bVar10 = bVar5 ^ bVar9;``bVar1 = *(byte *)(iVar12 + 3);``bVar11 = bVar10 ^ bVar6 ^ bVar1;``*(byte *)(iVar14 + iVar15 * 4) =``bVar9 ^ bVar10 << 1 ^ (byte)((uint)(``int``)(``char``)bVar10 >> 7) & 0x1b ^ bVar11;``iVar15 = iVar15 + 1;``*(byte *)(iVar12 + 2) =``bVar10 ^ bVar1 ^ (bVar1 ^ bVar6) << 1 ^``(byte)((uint)(``int``)(``char``)(bVar1 ^ bVar6) >> 7) & 0x1b;``*(byte *)(iVar12 + 3) =``(byte)((uint)(``int``)(``char``)(bVar1 ^ bVar9) >> 7) & 0x1b ^``bVar10 ^ bVar6 ^ (bVar1 ^ bVar9) << 1;``*(byte *)(iVar12 + 1) =``bVar11 ^ bVar5 ^ (bVar6 ^ bVar5) << 1 ^``(byte)((uint)(``int``)(``char``)(bVar6 ^ bVar5) >> 7) & 0x1b;``}``local_2c = uVar13;``FUN_00011524();``uVar13 = local_2c + 1;``}``FUN_00011524(10,local_30,local_2c,iVar14);``return``;``}` |
|-|-|

## 梳理代码逻辑

- so加载时hook strcmp
- 当执行checkfalg中的strcmp时被劫持到了Proc_00010e28
- 然后base64decode 还原AES的key
- 将输入的code，进行AES-ECB加密，然后base64encode
- 再返回到真正的strcmp函数实现对结果和“K4/7/faihmk9/WEMlfuFdpgrP86ckd4oQQ/UeAiZdx8=”比较

## 最终的keygen

既然知道了结果和key，很容易解密出输入的字符串。

[在线AES解密](https://gchq.github.io/CyberChef/#recipe=From_Base64()

 ![image](https://bbs.kanxue.com/upload/attach/202401/396123_FQ8XC9WJUZVKX4H.webp)

上传的附件：
- fake-func.zip

（1.80MB，31次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2024-1-9 10:10*

感谢分享
