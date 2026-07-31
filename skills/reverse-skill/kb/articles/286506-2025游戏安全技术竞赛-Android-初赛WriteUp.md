---
title: '[原创]2025游戏安全技术竞赛-Android-初赛WriteUp'
url: https://bbs.kanxue.com/thread-286506.htm
tid: 286506
author: Je2em1ah
date: '2025-04-16'
tags: [Android安全, 原创, 逆向分析, HOOK注入]
crawled_at: '2026-07-31T14:11:28+08:00'
replies: 4
---

## 附件说明

| 文件名称 | 功能 |
|-|-|
| decode.py | 处理字符串解密 |
| hack.js | 实现修复功能的Frida脚本 |
| SDK.txt | Dump得到的游戏SDK |
| Actor.txt | Dump得到的Actorlist |

hack.js的用法为：终端输入

| 1 | `frida -U -f com.ACE2025.Game -l hack.js` |
|-|-|

等待游戏启动之后继续在终端输入: my_hack()调用my_hack函数

## 获取UE4三件套

用frida-ue4dumper得到`base: 0x764bd2f000, GUObjectArray: undefined, GName: 0x7656b1f7c0`
得到**GName**偏移：`0xADF07C0`
**GWorld**: `0xAFAC398` (通过字符串`SeamlessTravel FlushLevelStreaming`定位)
**GUObject**: `0xAE34A98` (通过字符串`Max UObject count is invalid. It must be a number that is greater than 0.`定位)

dumpSDK

| 1 | `.``/ue4dumper64` `--package com.ACE2025.Game --ptrdec --sdku --gname 0xADF07C0 --guobj 0xAE34A98 --output` `/data/local/tmp` `--newue+` |
|-|-|

dumpActors

| 1 | `.``/ue4dumper64` `-- package com.ACE2025.Game --ptrdec --actors --gname 0xADF07C0 --gworld 0xAFAC398 --output` `/data/local/tmp/actors``.txt --newue+` |
|-|-|

dump libUE4.so

| 1234567891011121314151617 | `[INFO] RootService: Service connected` `Process : com.ACE2025.Game``PID: 15801``FILE: libUE4.so``Start Address: 764bd2f000``End Address: 7656a3d000``Size Memory: 173MB (181460992)``[INFO] Fixing...``[INFO] Fixer output :``Rebuilding Elf(So)``warning load size [185078944] is bigger than so size [181460992], dump maybe incomplete!!!``warning DT_HASH not found,try to detect dynsym size...``fixed so has write to /sdcard/PADumper/com.ACE2025.Game/764bd2f000-7656a3d000-libUE4_fix.so``Rebuilding Complete``Output: /sdcard/PADumper/com.ACE2025.Game``[INFO] Dump Success` |
|-|-|

## 分析外挂加载逻辑

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_44Y7PMTHVMAGE79.png)

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_2ZN4HH8SEA32C9B.png)

直接删掉libGame.so再启动游戏会crash，查看log可以定位到`libGame.so`是在`libUE4.so`加载的时候加载的，并且发现libUE4.so的依赖中包含了libGame.so，可以确认是**ELF感染注入**
通过readelf可以看到libGame.so是libUE4.so的依赖，具体的实现逻辑应该是通过修改`DT_NEEDED`标签来加载这个so.

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_KAMM9SMRE6QY5NW.png)

检查PHT数组中**p_tag**为`PT_DYNAMIC`的元素，并找到其中**d_tag**为`DT_STRTAB`的元素，其值就是字符串表在文件中的偏移，**d_tag**为`DT_STRSZ`的元素的值是字符串表的长度，将两者相加即为字符串表末尾的地址，发现字符串表中有`libGame.so`，并且**DT_NEEDED**条目中包含了`libGame.so`，当**linker**加载libUE4.so时，会解析libUE4.so的**dynamic**段，并遍历DT_NEEDED条目，生成新的 `LoadTask`，递归加载所有依赖库

## 外挂逻辑实现

libGame.so的函数都被CFF混淆过了，用D810插件可以有比较不错的去混淆效果，起码算是能看了
libGame.so的init_array段中会调用一个函数，追踪这个函数的调用链可以发现sub_27F0会创建一个线程，那么这个线程执行的函数就是外挂逻辑的实现了
![image](https://bbs.kanxue.com/upload/attach/202504/1009684_KAPYYRTSQVA33GS.png)

### 字符串解密

0x1B9C函数是主要执行外挂逻辑的函数

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_8MRX7TTXFV4QTGE.png)

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_E62KY7PSPNFFQYS.png)

在libGame.so里面还有几个字符串解密函数，由于数量不是很多所以我并没有写一个一次性解密所有字符串的函数，如果需要解密字符串可以通过**特征匹配**的思路来解决，字符串解密函数的第一个参数存放解密后的字符串，第二个参数是密文，**这种字符串解密函数的特征就是前n个字节做密钥，后面的则是密文**，字符串的长度就是if条件中的值，如果使用特征匹配的话思路就是匹配`^`,`%`, `if == n`这样的式子来**获取字符串长度和密钥长度**，然后查找字符串函数的交叉引用，提取参数中的地址，并用IDA的api读取指定地址的数据，然后复现解密函数进行批量解密

我这里为了不复杂化就写一个解密函数来手动修改长度和数据

| 1234567 | `data` `=` `[``0xA5``,` `0x05``,` `0x5E``,` `0x29``,` `0xE2``,` `0x9A``,` `0xBB``,` `0x6E``,` `0x08``,` `0x42``,` `0xC3``,` `0x55``,` `0xEC``,` `0x01``,` `0x7C``,` `0xA9``,` `0x96``,` `0xD3``,` `0x59``,` `0xA8``,` `0x91``,` `0xCF``,` `0x89``,` `0x11``,` `0x24``,` `0xD6``,` `0xC9``,` `0x6C``,` `0x3C``,` `0x7C``,` `0xA7``,` `0xAE``,` `0x95``,` `0x1D``,` `0x67``,` `0x42``]``count` `=` `0``for` `i` `in` `range``(``len``(data)):``print``(``chr``(data[i` `+` `0x1A``] ^ data[i` `%` `0x1A``]), end``=``'')``count` `+``=` `1``if` `count` `=``=` `0x9``:``break` |
|-|-|

于是可以得到字符串信息

| 地址 | 字符串 |
|-|-|
| 0xB658 | `libUE4.so` |
| 0xB650 | `-` |
| 0xB648 | `r` |
| 0xB634 | `/proc/%d/maps` |
| 0xB620 | `/proc/self/maps` |

### sub_B80(获取libUE4基址)

sub_B80函数是寻找libUE4.so的基址，具体实现流程如下:通过fopen函数打开proc/pid/maps文件打开程序的虚拟内存空间，通过fgets函数遍历maps文件的每一行字符串，通过strstr函数筛选包含`libUE4.so`字符串的行，然后通过strtok函数以字符`-`分割文本，提取字符串，最后使用`strtoul`函数讲字符串转换成unsigned long int类型的整数，通过Fridahook可以很容易分析出来这一函数

| 12345678910111213141516171819202122 | `function` `hook_strstr() {``const targetModule =` `"libGame.so"``;``const strstrPtr = Module.getExportByName(``null``,` `"strstr"``);` `Interceptor.attach(strstrPtr, {``onEnter:` `function``(args) {``const returnAddress =` `this``.returnAddress;``const module = Process.findModuleByAddress(returnAddress);``if` `(!module \|\| module.name !== targetModule)` `return``;` `const mainStr = Memory.readCString(args[0]);``const subStr = Memory.readCString(args[1]);``console.log(`[${targetModule}] strstr(``"${mainStr}"``,` `"${subStr}"``)`);``}``});``}` `const waitForGameLib = setInterval(() => {``if` `(Module.findBaseAddress(``"libGame.so"``)) {``clearInterval(waitForGameLib);``hook_strstr();``}``}, 100);` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_BXXMYYDTT8BN63P.png)

### 获取GWorld

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_72UU9PSKWEQKYZX.png)

发现这里和之前找到的GWorld偏移一致，可以知道这里获取了GWorld的地址

### 获取PersistentLevel

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_R7SM3NVMTN8969V.png)

这里获取了**持久关卡**的指针，这是UWorld类中的一个重要成员，存放了`Actors`等数据，是遍历玩家角色的关键成员变量

### 获取Actors和Actors的数量

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_NY5Y7MBXFN7CUCP.png)

这里获取了Actor的数组和长度，用于下面遍历Actor获取目标对象

### 遍历Actors

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_6WZ4K6QA9YS82D2.png)
![image](https://bbs.kanxue.com/upload/attach/202504/1009684_MS39P5DJSKWTJSA.png)

此处遍历Actor并获取指定对象，这里的0xA63BE28是对象的虚标指针，UE4中每个类的虚表（vtable）在`libUE4.so`中的偏移是固定的。通过比对虚表偏移，判断当前 Actor 是否为目标对象

| 123456789101112 | `function` `my_hack(){``getlibue4();``var` `actorsAddr = getActorsAddr();``var` `base = Module.getBaseAddress(``"libUE4.so"``);``for` `(``var` `key` `in` `actorsAddr) {``//console.log("[+] current actor is : ", key);``//console.log("UE4 base = ", base);``if` `(actorsAddr[key].readPointer() - base == 0xA63BE28) {``console.log(``"[+] Successful Get target Actor : "``, key);``}``}``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_MA9C94YT4C2RD44.png)

通过frida脚本可以发现程序寻找的Actor为: `FirstPersonCharacter_C`

### 修改移速和后坐力

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_PNR5B2J2KFFDT94.png)

这里可以看到外挂寻找了几个当前对象的偏移

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_S6RJPMFPSRKPXSM.png)

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_R779NGQDMVSJKFF.png)

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_U4QWXUV8JD8TQ7Y.png)

可以在SDK找到这几个偏移对应的变量

| 偏移 | 类 | 对象 |
|-|-|-|
| 0x538 | `MyProjectCharacter.Character.Pawn.Actor.Object` | **RecoilAccumulationRate** |
| 0x288 | `Character.Pawn.Actor.Object` | **CharacterMovementComponent** |
| 0x1A0 | `CharacterMovementComponent.PawnMovementComponent....` | **MaxAcceleration** |

| 123456789101112131415161718 | `function` `my_hack(){``getlibue4();``var` `actorsAddr = getActorsAddr();``var` `base = Module.getBaseAddress(``"libUE4.so"``);``for` `(``var` `key` `in` `actorsAddr) {``//console.log("[+] current actor is : ", key);``//console.log("UE4 base = ", base);``if` `(actorsAddr[key].readPointer() - base == 0xA63BE28) {``console.log(``"[+] Successful Get target Actor : "``, key);``var` `player_addr = actorsAddr[key];``var` `RecoilAccumulationRate = player_addr.add(0x538);``var` `CharacterMovementComponent = player_addr.add(0x288).readPointer();``var` `MaxAcceleration = CharacterMovementComponent.add(0x1A0);``Memory.writeFloat(MaxAcceleration, 1000);``Memory.writeFloat(RecoilAccumulationRate, 5);``}``}``}` |
|-|-|

通过修改对应的内存值可以发现`RecoilAccumulationRate`实际上是计算枪口抖动的系数，外挂中把此处修改成了0，改成非0的值就可以发现开枪之后枪口会上调
`MaxAcceleration` 是人物移动速度的变量，程序把这里的值修改成了1000000000，把值改成1000则可以使人物正常行走

### 自瞄

仔细观察游戏会发现，每次开枪的时候准星都会锁定在**一个箱子**那里，无论是重启游戏还是移动角色或者箱子到不同位置，准星始终在一个箱子身上，于是先寻找出来是哪一个箱子，在之前dump的Actor列表中发现有名为`EditorCube`的对象，一共有14个，数了一下箱子的数量也是14个，那么基本可以确定箱子就是这个对象，然后通过输出所有箱子的`vector`的值获取坐标，再移动目标箱子就可以比对出来是哪一个箱子

| 1234567891011121314151617181920212223242526272829303132333435363738 | `class Vector {``//设置向量对象``constructor(x, y, z) {``this``.x = x;``this``.y = y;``this``.z = z;``}``// 将向量转换为字符串``toString() {``return` ``(${``this``.x}, ${``this``.y}, ${``this``.z})`;``}``}``function` `dumpVector(addr) {``// dumpAddr('firstPersion_RootComponent',firstPersion_RootComponent_ptr,0x152)``// 从地址空间中读取三个浮点数``const values = Memory.readByteArray(addr, 3 * 4);` `// 3个float共占12个字节``// 解析浮点数并初始化 Vector 对象``const vec =` `new` `Vector(``new` `Float32Array(values, 0, 1)[0],` `// 读取第一个浮点数``new` `Float32Array(values, 4, 1)[0],` `// 读取第二个浮点数``new` `Float32Array(values, 8, 1)[0]` `// 读取第三个浮点数``);``console.log(``"[+] 坐标："``, vec);` `//打出坐标。``}``function` `get_box_vec(){``getlibue4();``var` `base = Module.getBaseAddress(``"libUE4.so"``);``var` `actorsAddr = getActorsAddr();``for` `(``var` `key` `in` `actorsAddr) {``if` `(key.includes(``"EditorCube"``)){``var` `actor_addr = actorsAddr[key];``var` `RootComponent = actor_addr.add(0x130).readPointer();``var` `Location = RootComponent.add(0x11C);``console.log(``"[+]Actor: "``, key);``dumpVector(Location);``}``}``}` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859 | `Part 1 :``[+]Actor:  EditorCube8``[+] 坐标： (843.998779296875, -1169.60498046875, 295.23797607421875)``[+]Actor:  EditorCube9``[+] 坐标： (1464.425537109375, -657.312744140625, 245.24537658691406)``[+]Actor:  EditorCube10``[+] 坐标： (1464.425537109375, -46.785343170166016, 245.24537658691406)``[+]Actor:  EditorCube11``[+] 坐标： (860.821533203125, -46.78565216064453, 245.23817443847656)``[+]Actor:  EditorCube12``[+] 坐标： (1307.8231201171875, 714.8047485351563, 245.24351501464844)``[+]Actor:  EditorCube13``[+] 坐标： (1310.8233642578125, 874.9715576171875, 245.2435302734375)``[+]Actor:  EditorCube14``[+] 坐标： (1310.8233642578125, 790.3173828125, 395.24346923828125)``[+]Actor:  EditorCube15``[+] 坐标： (-896.7808227539063, 828.98193359375, 245.21722412109375)``[+]Actor:  EditorCube16``[+] 坐标： (-1034.357666015625, 746.9696655273437, 245.21559143066406)``[+]Actor:  EditorCube17``[+] 坐标： (-961.6449584960938, 790.31689453125, 395.21636962890625)``[+]Actor:  EditorCube18``[+] 坐标： (-1439.8385009765625, -811.4144897460937, 245.21078491210937)``[+]Actor:  EditorCube19``[+] 坐标： (-1439.401123046875, -811.4213256835937, 395.2096862792969)``[+]Actor:  EditorCube20``[+] 坐标： (-1309.3416748046875, -373.11163330078125, 295.2123107910156)``[+]Actor:  EditorCube21``[+] 坐标： (-1123.3922119140625, 153.2134246826172, 245.2145233154297)` `Part 2:``[+]Actor:  EditorCube8``[+] 坐标： (859.3866577148438, -1172.3924560546875, 295.2377624511719)``[+]Actor:  EditorCube9``[+] 坐标： (1464.425537109375, -657.312744140625, 245.24537658691406)``[+]Actor:  EditorCube10``[+] 坐标： (1464.425537109375, -46.785343170166016, 245.24537658691406)``[+]Actor:  EditorCube11``[+] 坐标： (860.821533203125, -46.78565216064453, 245.23817443847656)``[+]Actor:  EditorCube12``[+] 坐标： (1307.8231201171875, 714.8047485351563, 245.24351501464844)``[+]Actor:  EditorCube13``[+] 坐标： (1310.8233642578125, 874.9715576171875, 245.2435302734375)``[+]Actor:  EditorCube14``[+] 坐标： (1310.8233642578125, 790.3173828125, 395.24346923828125)``[+]Actor:  EditorCube15``[+] 坐标： (-896.7808227539063, 828.98193359375, 245.21722412109375)``[+]Actor:  EditorCube16``[+] 坐标： (-1034.357666015625, 746.9696655273437, 245.21559143066406)``[+]Actor:  EditorCube17``[+] 坐标： (-961.6449584960938, 790.31689453125, 395.21636962890625)``[+]Actor:  EditorCube18``[+] 坐标： (-1439.8385009765625, -811.4144897460937, 245.21078491210937)``[+]Actor:  EditorCube19``[+] 坐标： (-1439.401123046875, -811.4213256835937, 395.2096862792969)``[+]Actor:  EditorCube20``[+] 坐标： (-1309.3416748046875, -373.11163330078125, 295.2123107910156)``[+]Actor:  EditorCube21``[+] 坐标： (-1123.3922119140625, 153.2134246826172, 245.2145233154297)` |
|-|-|

通过上述方法比对之后不难发现只有`EditorCube8`的值发生了变化，那么可以确定这个就是我们的目标Actor，接下来寻找这个箱子的世界坐标并给坐标下硬件断点打印调用栈

通过Frida hook 我们可以获取角色视角的Vector的值，通过`PlayerController + 0x288`的偏移处可以获取到`ControlRotation`的地址，其中后续的12个字节就是角色的相机的位置信息，即`FRotator`结构体，其成员变量分别是`Pitch`，`Yaw`，`Roll`，使用`stackplz`给此处下硬件断点(w)并打印调用栈可回溯到写入此内存地址的函数的调用栈

| 123456789101112131415161718192021222324252627282930 | `function` `my_hack(){``getlibue4();``var` `actorsAddr = getActorsAddr();``var` `base = Module.getBaseAddress(``"libUE4.so"``);``console.log(``"[+] UE4 base = "``, base);``hook_addr(base.add(0x670f3f8));``for` `(``var` `key` `in` `actorsAddr) {``//console.log("[+] current actor is : ", key);``//console.log("UE4 base = ", base);``if` `(actorsAddr[key].readPointer() - base == 0xA63BE28) {``console.log(``"[+] Successful Get target Actor : "``, key);``var` `player_addr = actorsAddr[key];``var` `RecoilAccumulationRate = player_addr.add(0x538);``var` `CharacterMovementComponent = player_addr.add(0x288).readPointer();``var` `MaxAcceleration = CharacterMovementComponent.add(0x1A0);``Memory.writeFloat(MaxAcceleration, 1000);``Memory.writeFloat(RecoilAccumulationRate, 0);``}``if` `(key ==` `"PlayerController"``){``console.log(``"[+] Successful Get target Actor : "``, key);``var` `ControlRotation = actorsAddr[key].add(0x288);``var` `Pitch = ControlRotation.add(0x0).readFloat();``var` `Yaw = ControlRotation.add(0x4).readFloat();``var` `Roll = ControlRotation.add(0x8).readFloat();``console.log(``"[+] Pitch = {}, Yaw = {}, Roll = {}"``, Pitch, Yaw, Roll);``console.log(``"[+] ControlRotation = "``, ControlRotation);` `}``}``}` |
|-|-|

下断点

| 1 | `.``/stackplz` `--brk 0x758eb0f5c8:w --brk-len 4 --stack -o pitch.log` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435 | `[23330\|23381] event_addr:0x758eb0f5c8 hit_count:1, Backtrace:``#00 pc 0000000008b387c0  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#01 pc 000000000670f3f8  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#02 pc 000000000670feac  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#03 pc 0000000009268e34  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#04 pc 0000000009266e00  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#05 pc 0000000008fa0588  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#06 pc 0000000008f9f6f0  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#07 pc 0000000008f9f370  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#08 pc 0000000008fa7354  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#09 pc 00000000091fdb88  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#10 pc 00000000067cebac  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#11 pc 00000000067ce72c  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#12 pc 00000000067cde20  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#13 pc 00000000091f9c00  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#14 pc 00000000091f73b8  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#15 pc 0000000008d3b75c  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#16 pc 0000000008c068ec  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#17 pc 0000000005af53b8  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#18 pc 0000000005af3510  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so` `[23330\|23381] event_addr:0x758eb0f5c8 hit_count:2, Backtrace:``#00 pc 0000000008b387c0  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#01 pc 0000000008f9b600  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#02 pc 0000000008fa7354  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#03 pc 00000000091fdb88  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#04 pc 00000000067cebac  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#05 pc 00000000067ce72c  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#06 pc 00000000067cde20  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#07 pc 00000000091f9c00  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#08 pc 00000000091f73b8  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#09 pc 0000000008d3b75c  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#10 pc 0000000008c068ec  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#11 pc 0000000005af53b8  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so``#12 pc 0000000005af3510  /data/app/~~10p5bElEgTHlqQoqeGftBw==/com.ACE2025.Game-INpbz7MxpBsqqBF6R0aTwA==/lib/arm64/libUE4.so` |
|-|-|

得到调用栈信息，经过分析发现`0x8b387c0`位置的函数是向`FRotator`结构体的成员变量写入坐标的，而`0x670f3f8`貌似是处理用户交互的函数，也就是**处理射击**这一行为的函数，使用Frida将这一处的调用Patch成NOP可以实现**自瞄的去除**

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_MPFRQVA6QRATBG2.png)

可以看到这里会对坐标进行一些计算，之后就调用函数`0x8b387c0`将坐标写入到对应结构体中，patch此处函数调用即可使外挂只计算而不写入坐标信息

| 1234567 | `function` `patch_addr(Addr){``Memory.protect(Addr, 4,` `'rwx'``);``Memory.patchCode(Addr, 4,` `function` `(code) {``code.writeByteArray([0x1F, 0x20, 0x03, 0xD5]);``});``}``patch_addr(0x)` |
|-|-|

### 弹道

考虑到自瞄实现的逻辑中，角色视角和子弹弹道的改变应该同时处理，所以在前面修改角色视角的函数中同样实现了修改子弹弹道的具体实现逻辑

分析Actorlist可以知道子弹的对象是`FirstPersonProjectile_C`,这个类继承自`ProjectileMovementComponent.MovementComponent.ActorComponent.Object` 通过hook打印这个类的`InitialSpeed`和`MaxSpeed`可以发现这两个值都是**3000**说明子弹速度并没有被修改

在函数`sub_670F110`中继续分析可以看到前面patch的地方的后面就是处理子弹弹道的逻辑
![image](https://bbs.kanxue.com/upload/attach/202504/1009684_FMGP5J8NTMEE7UD.png)

其中`ChangeCorner`函数(已改名)是用来**控制子弹弹道随机化**的(-30°到30°)

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_72TXDYJSHANH4B6.png)

sub8D2ED80函数是控制枪口Location和Rotation的关键逻辑，函数调用链为`sub_8D2ED80->sub_8D2E214`，sub_8D2E214是处理spawnactor的函数，见下图

![image](https://bbs.kanxue.com/upload/attach/202504/1009684_DS8KCMNN7SN7BG7.png)

阅读UE4官方文档可以知道子弹对象的生成逻辑和发射方向的逻辑

| 12345678910111213141516 | `UWorld* World = GetWorld();``if` `(World)``{``FActorSpawnParameters SpawnParams;``SpawnParams.Owner =` `this``;``SpawnParams.Instigator = GetInstigator();` `// 在枪口位置生成发射物。``AFPSProjectile* Projectile = World->SpawnActor<AFPSProjectile>(ProjectileClass, MuzzleLocation, MuzzleRotation, SpawnParams);``if` `(Projectile)``{``// 设置发射物的初始轨迹。``FVector LaunchDirection = MuzzleRotation.Vector();``Projectile->FireInDirection(LaunchDirection);``}``}` |
|-|-|

可以看到`MuzzleLocation`是枪口的**位置信息**，`MuzzleRotation`是枪口的**朝向信息**，而发射物的初始轨迹就是通过`MuzzleRotation`来设置的，通过Frida hook获取 sub_8D2ED80函数调用前的寄存器信息可以知道其第三和第四个参数就是我们需要的Location和Rotation

| 123456789101112131415161718192021222324252627 | `Interceptor.attach(base.add(0x670F6B8), {``onEnter:` `function``(args) {``var` `X2 =` `this``.context.x2;``var` `X3 =` `this``.context.x3;``var` `X4 =` `this``.context.x4;``console.log(``"[+] dump Muzzle location"``);``dumpVector(X2);``console.log(``"[+] dump Muzzle rotation"``);``dumpVector(X3);``},``onLeave:` `function``(retval) {``}``});``/*``[+] dump Muzzle location``[+] 坐标： (-156.2298126220703, -194.9197540283203, 398.4053649902344)``[+] dump Muzzle rotation``[+] 坐标： (-0.8549373745918274, -45.907772064208984, 0)``[+] dump Muzzle location``[+] 坐标： (-156.7232666015625, -193.81390380859375, 397.9298095703125)``[+] dump Muzzle rotation``[+] 坐标： (-0.8514755964279175, -45.91944122314453, 0)``[+] dump Muzzle location``[+] 坐标： (-156.3829803466797, -194.585205078125, 398.2392272949219)``[+] dump Muzzle rotation``[+] 坐标： (-0.8617335557937622, -45.91222381591797, 0)``*/` |
|-|-|

通过控制变量多次调整角色的位置并触发hook可以知道我们的分析没有问题，下面只需要把子弹的`Rotation`换成摄像机的Rotation即可,在onEnter回调中动态获取角色的Rotation并修改进去即可,Frida脚本如下

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960 | `function` `changeVector(addr, x, y, z) {` `//修改向量` `Memory.writeFloat(addr, x);` `Memory.writeFloat(addr.add(4), y);` `Memory.writeFloat(addr.add(8), z);` `}` `function` `my_hack(){``getlibue4();``var` `actorsAddr = getActorsAddr();``var` `base = Module.getBaseAddress(``"libUE4.so"``);``console.log(``"[+] UE4 base = "``, base);``patch_addr(base.add(0x670f3f8));` `// 修复角色视角自瞄``patch_addr(base.add(0x670F644));` `// 修复子弹随机分布``for` `(``var` `key` `in` `actorsAddr) {``//console.log("[+] current actor is : ", key);``//console.log("UE4 base = ", base);``if` `(actorsAddr[key].readPointer() - base == 0xA63BE28) {``//瞬移及后座力修复``console.log(``"[+] Successful Get target Actor : "``, key);``var` `player_addr = actorsAddr[key];``var` `RecoilAccumulationRate = player_addr.add(0x538);``var` `CharacterMovementComponent = player_addr.add(0x288).readPointer();``var` `MaxAcceleration = CharacterMovementComponent.add(0x1A0);``Memory.writeFloat(MaxAcceleration, 1000);``Memory.writeFloat(RecoilAccumulationRate, 0);``}``if` `(key ==` `"PlayerController"``){``console.log(``"[+] Successful Get target Actor : "``, key);``var` `ControlRotation = actorsAddr[key].add(0x288);``var` `Pitch = ControlRotation.add(0x0).readFloat();``var` `Yaw = ControlRotation.add(0x4).readFloat();``var` `Roll = ControlRotation.add(0x8).readFloat();``//changeVector(ControlRotation, 0, 0, 0);``console.log(``"[+] Pitch = {}, Yaw = {}, Roll = {}"``, Pitch, Yaw, Roll);``console.log(``"[+] ControlRotation = "``, ControlRotation);``}` `}``// Interceptor.replace(base.add(0x670FBAC), new NativeCallback(() => {``//     return 0.0; // 返回零散布角度``// }, 'float', ['pointer']));``// 修复弹道``Interceptor.attach(base.add(0x670F6B8), {``onEnter:` `function``(args) {``var` `player_rotation = ControlRotation;``var` `PlayerPitch = player_rotation.add(0x0).readFloat();``var` `PlayerYaw = player_rotation.add(0x4).readFloat();``var` `PlayerRoll = player_rotation.add(0x8).readFloat();``var` `X2 =` `this``.context.x2;``var` `X3 =` `this``.context.x3;``// console.log("[+] dump Muzzle location");``// dumpVector(X2);``// console.log("[+] dump Muzzle rotation");``// dumpVector(X3);``changeVector(X3, PlayerPitch, PlayerYaw, PlayerRoll);``},``onLeave:` `function``(retval) {``}``});``}` |
|-|-|

### 透视(未实现)

观察游戏中透视的特征可以发现无视了墙壁直接渲染在我们的视角中，说明他可能修改了材质的`bDisableDepthTest`的值为**True**，使得人物模型可以透过墙壁看见，也可能是**修改了模型的渲染顺序**使得玩家的模型最后渲染，并且人物变成了**红色高亮**状态，这通常会调用`SetVectorParameterValue`函数对材质的RGB值进行修改。

通过类成员变量之间的引用，可以找到一条获取`Material`对象的指针链：**Character -> SkeletalMeshComponent - >SkinnedMeshComponent -> SkeletalMesh -> SkeletalMaterial -> MaterialInterface -> Material**；获取到Material之后就可以修改他的成员变量`bDisableDepthTest`，经过Frida hook之后也确实发现这个值是True，但是修改成False之后透视效果依然存在，也想过可能是这个bool变量只会读取一次，但是实在是找不到hook时机来修改这一点

| 1234567891011121314151617181920212223242526272829303132 | `function` `get_material(Name){``getlibue4();``var` `ThirdPerson = getActorAddr(Name);``var` `SkeletalMeshComponent = ThirdPerson.add(0x280).readPointer();``// var bCollideWithEnvironment = SkeletalMeshComponent.add(0x8C0).readU8() & 0x80;``// console.log("[+] bCollideWithEnvironment = ", bCollideWithEnvironment);``// Memory.protect(SkeletalMeshComponent.add(0x8C0), 4, 'rwx');``// const newByteValue_1 = SkeletalMeshComponent.add(0x8C0).readU8() ^ 0x80;``// SkeletalMeshComponent.add(0x8C0).writeU8(newByteValue_1);``console.log(``"[+] bCollideWithEnvironment Patched = "``, SkeletalMeshComponent.add(0x8C0).readU8() & 0x80);``var` `SkeletalMesh =  SkeletalMeshComponent.add(0x478).readPointer();``var` `SkeletalMaterial_array = SkeletalMesh.add(0xD8);``var` `dataPtr = SkeletalMaterial_array.readPointer();``var` `count = SkeletalMaterial_array.add(0x8).readU32();``console.log(``"[+] SkeletalMaterial count = "``, count);``console.log(`Materials数组: 数量=${count}, 指针=0x${dataPtr.toString(16)}`);``var` `getMaterial =` `new` `NativeFunction(Module.getBaseAddress(``"libUE4.so"``).add(0x94e8370),` `'pointer'``, [``'pointer'``]);``for` `(``var` `i = 0; i < count; i++) {``if` `(i == 0){``var` `MaterialInterface = dataPtr.add(i * 8).readPointer();``var` `Material = getMaterial(MaterialInterface);``console.log(``"[+] bDisableDepthTest = "``, Material.add(0x1f8).readU8() & 0x1)``var` `bDisableDepthTest = (Material.add(0x1f8).readU8() & 0x1) == 0;``//console.log(`Material[${i}] = 0x${Material.toString(16)}, bDisableDepthTest = ${bDisableDepthTest}`);``Memory.protect(Material.add(0x1f8), 4,` `'rwx'``);``const newByteValue = Material.add(0x1f8).readU8() ^ 0x1;` `// 按异或或操作``Material.add(0x1f8).writeU8(newByteValue);``console.log(``"[+] bDisableDepthTest Patched = "``, Material.add(0x1f8).readU8() & 0x1)``//console.log(`Material[${i}] = 0x${Material.toString(16)}, bDisableDepthTest = ${bDisableDepthTest}`);``}``}``}` |
|-|-|

也尝试了去修改`bCollideWithEnvironment`的值，然而也是没有效果，实在是想不到还有哪些地方会修改了

## 总结

这次比赛的题目主要是考验对UE4引擎的熟悉程度，逆向的部分占比不算特别大，也没有出什么比较难的混淆加壳之类的，虽然已经做出了大部分的内容，但是还是需要加深对UE4引擎的理解，如果对UE4足够熟悉，应该能减少很多在寻找各个类之间的关系和所需的成员变量上。

上传的附件：
- hack.js

（16.28kb，29次下载）

---

# 回复

## 回复 by ngiokweng (#2)

*2025-4-16 20:39*

tql!!!

## 回复 by 墨穹呢 (#3)

*2025-4-17 03:04*

感谢分享

## 回复 by mb_kgfqphsx (#4)

*2025-4-17 09:45*

大佬，getActorsAddr函数的逻辑有吗

## 回复 by Je2em1ah (#5)

*2025-4-17 12:42*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_kgfqphsx](https://bbs.kanxue.com/user-999343.htm)
>
>  大佬，getActorsAddr函数的逻辑有吗
>
>

我放附件了 你再看看呢
