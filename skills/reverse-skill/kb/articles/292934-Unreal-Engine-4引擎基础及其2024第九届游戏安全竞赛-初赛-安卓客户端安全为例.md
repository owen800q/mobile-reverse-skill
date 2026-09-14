---
title: '[原创]Unreal Engine 4引擎基础及其2024第九届游戏安全竞赛-初赛-安卓客户端安全为例'
url: https://bbs.kanxue.com/thread-292934.htm
tid: 292934
author: dayDReam_10
date: ''
tags: [Android安全, 原创, 基础理论, 逆向分析, 源码框架, 工具脚本]
crawled_at: '2026-09-14T01:53:28+00:00'
replies: 5
attachments:
- {filename: Hook_SetCollisionEnabled.js, aid: '405094', path: ../attachments/292934/Hook_SetCollisionEnabled.js, url: 'https://bbs.kanxue.com/attach-download-405094-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 1.15kb，5次下载, downloaded: false}
- {filename: Hook_SetActorLocation.js, aid: '405093', path: ../attachments/292934/Hook_SetActorLocation.js, url: 'https://bbs.kanxue.com/attach-download-405093-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 0.96kb，5次下载, downloaded: false}
- {filename: Hook_SetActorHiddenInGame.js, aid: '405092', path: ../attachments/292934/Hook_SetActorHiddenInGame.js, url: 'https://bbs.kanxue.com/attach-download-405092-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 2.29kb，5次下载, downloaded: false}
- {filename: getClassName.js, aid: '405091', path: ../attachments/292934/getClassName.js, url: 'https://bbs.kanxue.com/attach-download-405091-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 0.64kb，5次下载, downloaded: false}
- {filename: GetAddrByName.js, aid: '405090', path: ../attachments/292934/GetAddrByName.js, url: 'https://bbs.kanxue.com/attach-download-405090-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 5.38kb，5次下载, downloaded: false}
- {filename: FindAddrInGWorld.js, aid: '405089', path: ../attachments/292934/FindAddrInGWorld.js, url: 'https://bbs.kanxue.com/attach-download-405089-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 2.67kb，5次下载, downloaded: false}
- {filename: FindActorsContains.js, aid: '405088', path: ../attachments/292934/FindActorsContains.js, url: 'https://bbs.kanxue.com/attach-download-405088-265880756ad991b36b4d52c29bda5927@R0NZkT1ToZ34YP4/KQ3pZg==.htm', size: 2.71kb，5次下载, downloaded: false}
---

# Unreal Engine4引擎逆向基础

本文以 2024 第九届腾讯游戏安全竞赛安卓初赛题目（com.tencent.ace.match2024）为例，完整记录一次 UE4 手游的逆向过程。内容从 GUObjectArray、GWorld、GName 三大核心结构体的源码分析讲起，便于对 UE 引擎对象系统不熟悉的逆向入门者学习

ps:小白初次写文章，大佬们多多指教

使用工具：IDA 9.4Pro、Frida 17、ue4dumper

环境：Android 64 位，UE4.27

## 0.关键结构体基本认识

### GUObjectArray(FUObjectArray)

`UE`中所有东西都继承自`UObject`,引擎会维护一个全局对象数组`GUObjectArray`，里面存储了所有`UObject`对象的指针，通过这个数组可以遍历引擎中的每一个类，可以读取类的属性以及在内存中的偏移

#### 我们从理解源代码开始

```cpp
//EpicGames/UnrealEngine/blob/4.27/Engine/Source/Runtime/CoreUObject/Public/UObject/UObjectArray.h#L1056
class FUObjectArray
{
//后文提到extern COREUOBJECT_API FUObjectArray GUObjectArray所以直接找这里了
//FUObjectArray的内存布局
private:
    typedef FChunkedFixedUObjectArray TUObjectArray;

    int32 ObjFirstGCIndex;//4Bytes
    int32 ObjLastNonGCIndex;//4Bytes
    int32 MaxObjectsNotConsideredByGC;//4Bytes
    bool OpenForDisregardForGC;//1Byte
    //此处有padding 3Bytes
    TUObjectArray ObjObjects;//offset=0x10
    //...
};
// 关键显然是TUObjectArray ObjObjects 利用typedef 追FChunkedFixedUObjectArray

//EpicGames/UnrealEngine/blob/4.27/Engine/Source/Runtime/CoreUObject/Public/UObject/UObjectArray.h#L359
class FChunkedFixedUObjectArray
{
 enum
 {
  NumElementsPerChunk = 64 * 1024,
 };//此处不属于布局

 /** Master table to chunks of pointers **/
 FUObjectItem** Objects;//Chunk 指针表，通过它找到具体 Chunk
 //可以理解为一个指向“指针数组”的指针
 // Objects (FUObjectItem**)
 //     │
 //     └──→ 指向一个数组（因为数组也就是一个指针指向的）（块指针表）
 //             │
 //             ├─ [0] 是 FUObjectItem*，指向 Chunk 0
 //             ├─ [1] 是 FUObjectItem*，指向 Chunk 1
 //             ├─ [2] 是 FUObjectItem*，指向 Chunk 2
 //             └─ ...
 //而1 个 Chunk = 65536(0x10000) 个 FUObjectItem
 //Chunk[i]
 // ├── FUObjectItem[0]
 // ├── FUObjectItem[1]
 // ├── FUObjectItem[2]
 // ├── ...
 // └── FUObjectItem[65535]
 //因为 UObject 数量可能很多，UE4 不能把所有 FUObjectItem 强行放在一个连续数组里，而是分成一块一块的
 /** If requested, a contiguous memory where all objects are allocated **/
 FUObjectItem* PreAllocatedObjects;//连续预分配的 FUObjectItem 内存
 /** Maximum number of elements **/
 int32 MaxElements;
 /** Number of elements we currently have **/
 int32 NumElements;
 /** Maximum number of chunks **/
 int32 MaxChunks;
 /** Number of chunks we currently have **/
 int32 NumChunks;
}

//EpicGames/UnrealEngine/blob/4.27/Engine/Source/Runtime/CoreUObject/Public/UObject/UObjectArray.h#L26
struct FUObjectItem
//注意64位下 sizeof(FUObjectItem) = 0x18，尾部有一个4的padding
//32位下 sizeof(FUObjectItem) = 0x10 可以自己动手算算？
{
    UObjectBase* Object;   // +0x00
    int32 Flags;           // +0x08
    int32 ClusterRootIndex;// +0x0C
    int32 SerialNumber;    // +0x10
};

//Engine/Source/Runtime/CoreUObject/Public/UObject/UObjectBase.h line210
class COREUOBJECT_API UObjectBase
{
private:
//virtual ~UObjectBase()此类有虚析构函数
// 64 位下，指针 = 8 字节，vptr = 8 字节
// 8 + 4 + 4 + 8 + 8 + 8 = 40 = 0x28
// 32 位下，指针 = 4 字节，vptr = 4 字节
// 4 (vptr) + 4 (ObjectFlags) + 4 (InternalIndex) + 4 (ClassPrivate) + 8 (NamePrivate) + 4 (OuterPrivate) = 28 = 0x1C
 /** Flags used to track and report various object states. This needs to be 8 byte aligned on 32-bit
     platforms to reduce memory waste */
 EObjectFlags     ObjectFlags;//0x08 //大小4字节
 /** Index into GObjectArray...very private. */
 int32       InternalIndex;//0x0C
 /** Class the object belongs to. */
 UClass*       ClassPrivate;//0x10
 /** Name of this object */
 FName       NamePrivate;//64位下8 + 4 + 4 + 8 32位下 4 + 4 + 4 + 4
 /** Object this object resides in. */
 //...
 virtual ~UObjectBase();
};

class CORE_API FName//Engine/Source/Runtime/Core/Public/UObject/NameTypes.h line906
{
 private:

 /** Index into the Names array (used to find String portion of the string/number pair used for comparison) */
 FNameEntryId ComparisonIndex;//用于忽略大小写的比较
#if WITH_CASE_PRESERVING_NAME
 /** Index into the Names array (used to find String portion of the string/number pair used for display) */
 FNameEntryId DisplayIndex;//用于输出和展示
#endif // WITH_CASE_PRESERVING_NAME
 /** Number portion of the string/number pair (stored internally as 1 more than actual, so zero'd memory will be the default, no-instance case) */
 uint32   Number;// 数字后缀
}

//Engine/Source/Runtime/Core/Public/UObject/NameTypes.h line78
struct FNameEntryId
{
private:
 uint32 Value;
 //uint32 block  = Value >> 16;
 //uint32 offset = Value & 0xFFFF;

 CORE_API static FNameEntryId FromValidEName(EName Ename);
};

//Engine/Source/Runtime/Core/Public/UObject/NameTypes.h line180
class FNameEntry
//FNameEntry 是 FNamePool(Gname) 中存储一个名字（Name）的基本/最小条目
{
private:
#if WITH_CASE_PRESERVING_NAME//这个宏可能会影响后续反查
 FNameEntryId ComparisonId;//用于大小写机制:4 Byte
#endif
 FNameEntryHeader Header;//记录长度等信息//2 Byte
//  位布局（UE4.27，关闭 WITH_CASE_PRESERVING_NAME 时）：

//   15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
//  ┌─────────────────────────────────────┬────┬──┐
//  │              Len (10位)             │ xx │W │
//  └─────────────────────────────────────┴────┴──┘
//                                           ↑    ↑
//                                          保留  IsWide (最低位)
//这一条用于确认下面的字符串是哪种类型
 union
 {//真正存储字符串的地方
  ANSICHAR AnsiName[NAME_SIZE];//两种方法
  WIDECHAR WideName[NAME_SIZE];
 };
}
\```

### GWorld(UWorld)

`UE`引擎中有一个全局变量`GWorld`，代表当前游戏的世界状态，通过`GWorld`可以访问到当前游戏中的所有关卡、角色、物品等信息，获取运行时数据实例，并且是一个指针变量，指向`Uworld`

#### 一样的看源代码

```cpp
//Engine/Source/Runtime/Engine/Classes/Engine/World.h line894
class UWorld : public UObject, public FNetworkNotify
//当 UWorld 继承 UObject 时，UWorld 对象在内存里的顺序:
// [ UObject 基类的所有成员 ]      ← 先放
// [ FNetworkNotify 部分，FNetworkNotify 是多态次基类，它的虚函数集合与 UObject 的虚表无法合并，因此它携带自己的 vptr，额外贡献 8 字节（64 位）或 4 字节（32 位）]
// [ UWorld 自己的成员 ]           ← 后放
//     PersistentLevel
//     NetDriver
//即：
// [ UObject 子对象 ]                   ← 主基类，偏移 0 开始
//     +0x00 vptr
//     +0x08 ObjectFlags
//     +0x0C InternalIndex
//     +0x10 ClassPrivate
//     +0x18 NamePrivate
//     +0x20 OuterPrivate
//     → 到 0x28 结束

// [ FNetworkNotify 子对象 ]            ← 多态次基类
//     +0x28 它自己的 vptr（8 字节，64 位下）
//     （没有数据成员）
//     → 到 0x30 结束

// [ UWorld 自己的成员 ]                 ← 从这里开始
//     +0x30 PersistentLevel
//     +0x38 NetDriver
//     ...
{
//     64位与32位差别：
//     64 位:
// +0x00  UObject vptr            8
// +0x08  ObjectFlags             4
// +0x0C  InternalIndex           4
// +0x10  ClassPrivate            8
// +0x18  NamePrivate             8
// +0x20  OuterPrivate            8
// +0x28  FNetworkNotify vptr     8
// +0x30  PersistentLevel         ←
//     32位：
// +0x00  UObject vptr             4
// +0x04  ObjectFlags              4
// +0x08  InternalIndex            4
// +0x0C  ClassPrivate             4
// +0x10  NamePrivate              8
// +0x18  OuterPrivate             4
// --------------------------------
//       sizeof(UObject) = 0x1C
// +0x1C  FNetworkNotify vptr      4
// +0x20  PersistentLevel          ←
ULevel* PersistentLevel;
// 64位: +0x30
// 32位: +0x20
// World 主 Level

AGameModeBase* AuthorityGameMode;
// 64位: +0x118
// 32位: +0x98
// GameMode

AGameStateBase* GameState;
// 64位: +0x120
// 32位: +0x9C
// GameState

TArray<ULevel*> Levels;
// 64位: +0x138
// 32位: +0xB0
// 当前 World 中的 Level 集合

FSceneInterface* Scene;
// 64位: +0x188
// 32位: +0xE0
// 渲染 Scene

TArray<TWeakObjectPtr<AController>> ControllerList;
// 64位: +0x198
// 32位: +0xE4
// Controller

TArray<TWeakObjectPtr<APlayerController>> PlayerControllerList;
// 64位: +0x1A8
// 32位: +0xF0
// PlayerController
};
//要点是Ulevel
//4.27/Engine/Source/Runtime/Engine/Classes/Engine/Level.h#L412
UCLASS(MinimalAPI)
class ULevel : public UObject, public IInterface_AssetUserData
{
    GENERATED_BODY()

public:
    FURL URL;//要找Actors就得先找FURL
    //这里FURL无重要元素，直接给出布局
    //     64位下ULevel
    // │
    // ├─ +0x00 UObject
    // │
    // ├─ +0x28 IInterface_AssetUserData
    // │
    // ├─ +0x30 FURL URL
    // │      ├─ +0x00 Protocol
    // │      ├─ +0x10 Host
    // │      ├─ +0x20 Port
    // │      ├─ +0x24 Valid
    // │      ├─ +0x28 Map
    // │      ├─ +0x38 RedirectURL
    // │      ├─ +0x48 Op
    // │      └─ +0x58 Portal 十字节
    // │
    // ├─ +0x98 Actors

    // 32位下 ULevel
    //
    // ├─ +0x00  UObjectBase                    0x1C
    // │
    // ├─ +0x1C  IInterface_AssetUserData       0x04
    // │
    // ├─ +0x20  FURL                           0x50
    // │      ├─ +0x00  Protocol                0x0C
    // │      ├─ +0x0C  Host                    0x0C
    // │      ├─ +0x18  Port                    0x04
    // │      ├─ +0x1C  Valid                   0x04
    // │      ├─ +0x20  Map                     0x0C
    // │      ├─ +0x2C  RedirectURL             0x0C
    // │      ├─ +0x38  Op                      0x0C
    // │      └─ +0x44  Portal                  0x0C
    // │
    // ├─ +0x70  Actors                         0x0C

    TArray<AActor*> Actors;
    TArray<AActor*> ActorsForGC;

    static TMap<FName, TWeakObjectPtr<UWorld> > StreamedLevelsOwningWorld;

    UPROPERTY(Transient)
    UWorld* OwningWorld;

    UPROPERTY()
    class UModel* Model;

    UPROPERTY()
    TArray<class UModelComponent*> ModelComponents;

    UPROPERTY(Transient, DuplicateTransient, NonTransactional)
    ULevelActorContainer* ActorCluster;

    //...
};

class TArray//Engine/Source/Runtime/Core/Public/Containers/Array.h line2665
{
protected:
    /** 分配器实例，内部就是数据指针 Data */
    ElementAllocatorType AllocatorInstance;//+0x00
    /** 当前元素个数 */
    SizeType             ArrayNum;//+0x08
    /** 当前已分配的容量 */
    SizeType             ArrayMax;//+0x0C
}
\```

### GName(FNamePool)

UE 不会在每个对象中存储字符串，而是将所有的字符串存储在一个全局的字符串池中，并给每个字符串分配一个唯一的索引 id，有了 GName，就可以将在内存中看到一个个整数映射回字符串，是FNamePool类型的全局唯一实例对象

#### 确认源代码

```cpp
//Engine/Source/Runtime/Core/Private/UObject/UnrealNames.cpp line989
class FNamePool
{
private:
 enum { MaxENames = 512 };

 FNameEntryAllocator Entries;//这里是寻找字符串的关键

#if WITH_CASE_PRESERVING_NAME
 FNamePoolShard<ENameCase::CaseSensitive> DisplayShards[FNamePoolShards];
#endif
 FNamePoolShard<ENameCase::IgnoreCase> ComparisonShards[FNamePoolShards];

 // Put constant lookup on separate cache line to avoid it being constantly invalidated by insertion
 alignas(PLATFORM_CACHE_LINE_SIZE) FNameEntryId ENameToEntry[NAME_MaxHardcodedNameIndex] = {};
 uint32 LargestEnameUnstableId;
 TMap<FNameEntryId, EName, TInlineSetAllocator<MaxENames>> EntryToEName;
};
//Engine/Source/Runtime/Core/Private/UObject/UnrealNames.cpp line273
class FNameEntryAllocator
{
private:
 mutable FRWLock Lock;//锁，注意到大小并不固定，32+Android 0x28 //64+Android 0x38等等
 uint32 CurrentBlock = 0;//size_of_lock+4//当前Block[]下标值，也可以理解为当前Block已用的计数
 uint32 CurrentByteCursor = 0;//+8//当前字节偏移的指针，指向Block[CurrentBlock]中最后一个字符串的末尾。记录下一个字符串的起始位置
 //即在64下 offset+40可找到Block数组
 //Block是一个块，存了不同长度的FNameEntry
    // FNamePool
    // │
    // └── Blocks[index]
    //      │
    //      ├── [0] ──→ Block 0
    //      │             ├─ Entry
    //      │             ├─ Entry
    //      │             └─ Entry
    //      │
    //      ├── [1] ──→ Block 1
    //      │             ├─ Entry
    //      │             ├─ Entry
    //      │             └─ Entry
    //      │
    //      └── [2] ──→ Block 2
    //那么怎么取出第几块(Block_index)以及块中的偏移(offset)呢
    //往下连起来看下面两个类
 uint8* Blocks[FNameMaxBlocks] = {};// FNameMaxBlocks = 8192
 //数组指针，指向即将开辟的真正存储字符串的堆内存空间
 //且分布并不连续
}
class CORE_API FName//Engine/Source/Runtime/Core/Public/UObject/NameTypes.h line906
{
 private:

 /** Index into the Names array (used to find String portion of the string/number pair used for comparison) */
 FNameEntryId ComparisonIndex;//用于忽略大小写的比较
#if WITH_CASE_PRESERVING_NAME
 /** Index into the Names array (used to find String portion of the string/number pair used for display) */
 FNameEntryId DisplayIndex;//用于输出和展示
#endif // WITH_CASE_PRESERVING_NAME
 /** Number portion of the string/number pair (stored internally as 1 more than actual, so zero'd memory will be the default, no-instance case) */
 uint32   Number;
}
//Engine/Source/Runtime/Core/Public/UObject/NameTypes.hL#78
struct FNameEntryId
{
private:
 uint32 Value;

 CORE_API static FNameEntryId FromValidEName(EName Ename);
};
//通过这两个类找到一个Value 通过
//BlockIndex = (Value >> 16) & 0x1FFF
//BlockPtr =*(GName + 0x40 + BlockIndex * 0x08)
//Value首先就是这么规定，所以>>16取高位
// ┌────────────────┬────────────────┐
// │ BlockIndex     │ EntryIndex     │
// │    高位        │     低16位      │
// └────────────────┴────────────────┘
//*(GName + 0x40 + BlockIndex * 0x08)
//这个就完全是 C++ 数组寻址 0x40是FNmaePool->Block的偏移 8是指针大小
//InnerOffset=(Value & 0xFFFF) * 0x02，0x02哪来的呢，往下看

inline FNameEntryHandle Allocate(uint32 Bytes)
{
    uint32 ByteOffset = CurrentByteCursor;
    uint32 Step = Align(Bytes, alignof(FNameEntry));
    CurrentByteCursor += Step;
    return FNameEntryHandle(CurrentBlock, ByteOffset / Stride);  // ← 除以 Stride 才存
}
//可以看到Value低16记载的不是ByteOffset本身，而是ByteOffset / Stride，且Stride是2

class FNameEntry//Engine/Source/Runtime/Core/Public/UObject/NameTypes.h line180
{//FNameEntry是真正存储的最小单元
private:
#if WITH_CASE_PRESERVING_NAME
 FNameEntryId ComparisonId;//用于大小写机制:4 Byte
#endif
 FNameEntryHeader Header;//记录长度等信息//2 Byte
 union
 {
  ANSICHAR AnsiName[NAME_SIZE];//两种展示方法//是真正存储字符串的地方
  WIDECHAR WideName[NAME_SIZE];
 };
}
\```

## 1.关于UE的SDK dump流程

我使用的工具是`ue4dumper`，这个工具需要`Gworld`,`GUObjectArray`,`GName`的地址

推荐一下这位师傅的文章https://www.cnblogs.com/revercc/p/17641855.html

网上也多有此类教程，大多写的很好，不再赘述

## 2.关于拥有SDK时反查指定运行对象地址

学习了上述结构体的基础布局之后

我们很容易知道两种思路(附件中均有实现，可以配合注释慢慢学习，分别是`GetAddrByName`，`FindAddrInGWorld`)

### 1 遍历 GUObjectArray

通过完全遍历 GUObjectArray，依次对比当前 Object 的名字与所需名字，若成立则返回 Object。

范围：全引擎所有 UObject（Actor、UClass、UFunction、UPackage、CDO 等）

优点：通用，什么都能找

缺点：慢；同名对象多（CDO 和实例），可能命中错的

适用：找非 Actor 对象（UClass、UFunction 等），或不确定目标在哪时全局搜索。

### 2 GWorld → PersistentLevel → Actors

获取 GWorld 后，沿 GWorld -> PersistentLevel -> ActorList 这条链，遍历 Actors 数组，依次比对名字，命中则返回地址。

范围：当前关卡的 Actor（几百个）

优点：快，全是实例，不会命中 CDO

缺点：只能找 Actor，找不到 UClass、UFunction 这类非 Actor 对象

适用：找场景里的实际物体（玩家、敌人、墙、道具），操作运行时状态

# 2024第九届游戏安全竞赛-初赛-安卓客户端安全

初步学习完关键结构体，我们取`2024第九届游戏安全竞赛-初赛-安卓客户端安全`为例子，一步步深入，附件在最后

### Section0

初步游玩可以发现一碰墙就生命值归零，在dump出的SDK中寻找`生命值`字样

 ![image](https://bbs.kanxue.com/upload/attach/202609/1073886_QYUVZYN26AYA4UW.webp)

在此可以找出偏移`0x510`

这时我们需要根据给定字符串找到运行时实例对象地址

我上述的第一思路是:

遍历GUObjectArray,根据上述结构体知识查出每个Object的名字，再匹配检查

后面能发现不太对，因为找出来的对象不处于Uworld中

故我们需要寻找当前Uworld下的

那么思路是寻找Gworld->PersistentLevel->ActorList->AActor(又已知这个继承于UObject)

实现看附件`FindAddrInGWorld.js`，具体原理是差不多的

且该脚本验证了Actor偏移问题

获取了之后接上`setInterval`即可

```js
var player = FindAddrInGWorld("FirstPersonCharacter_C");

setInterval(function () {
    if (!player || player.isNull()) return;
    try { player.add(0x510).writeFloat(999999.0); } catch (e) {}
}, 10);
\```

### Section0其他解法1

不与门触碰，所以我们需要说穿墙

首先我们可以看见`Class: FirstPersonCharacter_C`继承于`Character.Pawn.Actor.Object`

<https://zhuanlan.zhihu.com/p/1893965007970075448>

 ![image](https://bbs.kanxue.com/upload/attach/202609/1073886_GYS3JTUMNFNUZ38.webp)

而`CapsuleComponent`又继承于`PrimitiveComponent`，`PrimitiveComponent`内部的结构体`BodyInstance`

 ![image](https://bbs.kanxue.com/upload/attach/202609/1073886_882Z83GPXFFVSBK.webp)

可以发现这里有我们角色的碰撞处理点，写frida脚本处理掉却发现人物卡死了，原因是地面其他点也被该位置控制

转换思路变成改掉`Wall`的碰撞处理点即可

<https://ask.csdn.net/questions/8370688>

看这篇文章启发我们可以去hook`SetCollisionEnabled`

SDK中搜索得到偏移0x98edb3c

在ida中查找其指向的真实函数

`return (*(__int64 (__fastcall **)(__int64, _QWORD))(*(_QWORD *)a1 + 0x660LL))(a1, a2: v6[0]);`

发现是虚函数，那么首先查找`SetCollisionEnabled`的父类

那么我们要获取`wall`的实际类名

```js
var cls = wall.add(0x10).readPointer();          // wall 的 ClassPrivate（指向 UClass）
var ci  = cls.add(0x18).readU32();               // UClass 的 NamePrivate.ComparisonIndex
var blockIndex = (ci >>> 16) & 0x1FFF;
var entry = GNames.add(0x40).add(blockIndex * 8).readPointer()
                   .add((ci & 0xFFFF) * 2);
var header = entry.readU16();
var len = header >>> 6;
console.log("wall 的类:", entry.add(0x02).readCString(len));
\```

输出：StaticMeshActor

那么去SDK中查询StaticMeshActor追踪其StaticMeshComponent

发现其的确继承了PrimitiveComponent

那我们尝试hook这个函数

具体实现看`Hook_SetCollisionEnabled.js`

### Section0其他解法2

我们可以采取瞬移的方法过门，上网查询发现`SetActorLocation`该函数

在SDK中查询找到对应点，再在ida中查询

 ![image](https://bbs.kanxue.com/upload/attach/202609/1073886_GJUZYDU3N54ZP6H.webp)

咨询ai得知 v6 v8 v9 即为坐标 那么我们直接内存读出即可，实现请看`Hook_SetActorLocation.js`

当然碰到墙还是会死哈

### Section1

ai问一下使得组件不可见的手段有哪些，注意到了`SetActorHiddenInGame`和`SetVisibility`

采取处理`Actor`的`SetActorHiddenInGame`不起作用，转而尝试处理`SetVisibility`，这是因为`Setvisibility`是组件级

`SetActorHiddenInGame` 改的是 `Actor` 的 `bHidden`，而渲染器实际看的是组件的 `bVisible`，要`bHidden`+`bVisible`都到位了才能看到

确认SDK中`Setvisibility`的位置，ida发现真函数地址，且需要传入`SceneComponent`作为pointer，先回头查看`Shape_Pipe_Flag`是`StaticMeshActor`类，SDK中查找确认继承于`Actor.Object`，在Actor中查找`SceneComponent`确认偏移是`0x130`，由此我们得知`Shape_Pipe_Flag+0x130`即为需要传入的`ptr`

实现如下:

```js
var libUE4 = Process.findModuleByName("libUE4.so");

var fn = new NativeFunction(
    libUE4.base.add(0x8E619BC),       // SetVisibility 真实函数
    'void',
    ['pointer', 'bool', 'int']
);

var shapes = FindActorsContains("Shape_Pipe_Flag");
for (var i = 0; i < shapes.length; i++) {
    var rootComp = shapes[i].addr.add(0x130).readPointer();   // this
    if (rootComp.isNull()) continue;
    fn(rootComp, 1, 2);   // 显示 + 传给子组件
}
\```

解出Part1为`8939`

### Section2

目标是使得立方体不可穿透，那不就是前文所提到的穿墙的逆反处理，不过要先找到对象，我们可以把人物和立方体重合，然后所有`Actor`查询坐标，发现是这个`Cube2`

小改`Hook_SetCollisionEnabled.js`即可获取第二段答案

`Part2=008`

### Section3

老方法，直接人走过去看看到底是谁，是个叫`Actor`的，不知道什么玩意

采取frida脚本试探一下：

```js
var target = FindAddrInGWorld("Actor");
console.log("Actor =", target);
console.log("类:", getClassName(target));
\```

还是不确定，直接把碰撞关了试一下：

```js
var libUE4 = Process.findModuleByName("libUE4.so");

var fn = new NativeFunction(
    libUE4.base.add(0x8C21320),   // SetActorEnableCollision
    'void',
    ['pointer', 'bool']
);

fn(target, 0);
console.log("MyActor 碰撞已关");
\```

确实是这个，上SDK一查得到

\```
Class: MyActor.Actor.Object
    bool getlastflag();// 0x6a91fec
\```

上ida找一找，追入`sub_6A91A40`

 ![image](https://bbs.kanxue.com/upload/attach/202609/1073886_929HE6XUVTY276X.webp)

打开`libplay.so`稍微逆一下：

发现逻辑并不难，就是一个换表base64，处理好xor即可：

给出脚本：

```py
#!/usr/bin/env python3

# ==================== 数据 ====================
# key + number_0x9F8D (原始)
raw_key = bytes([
    0xD8, 0x98, 0x54, 0xC1, 0x64, 0x93, 0x56, 0x84,
    0x38, 0x4F, 0x60, 0xBB, 0xA9, 0xA4, 0xCC, 0x88,
    0x8D, 0x9F
])

# key 的 XOR 常量 (来自 get_last_flag)
key_xors = [
    0xD2, 0x94, 0x5A, 0xC1, 0x35, 0x85, 0x71, 0xBC,
    0x71, 0x55, 0x5B, 0xE7, 0x84, 0xEA, 0xA3, 0x72,
    0x71, 0x61
]

# byte_3E30 原始数据 (比较目标)
raw_target = bytes([
    0x9D, 0x43, 0xB0, 0xD7, 0xD4, 0x53, 0x1C, 0x7D,
    0xB4, 0xB6, 0xF6, 0x37, 0x23, 0x66, 0xDB, 0x92,
    0x19, 0xDF, 0xCF, 0xF9, 0x9A, 0x92, 0xF2, 0x3C
])

# byte_3E30 的 XOR 常量
target_xors = [
    0xC8, 0x17, 0x81, 0xB1, 0xB7, 0x63, 0x7B, 0x34,
    0xED, 0xF2, 0xB7, 0x45, 0x47, 0x1C, 0xE3, 0xA2,
    0x43, 0xEF, 0x97, 0x9C, 0xF7, 0xA6, 0xC4, 0x76
]

# byte_3DE0 原始数据 (自定义 base64 字母表)
raw_alphabet = bytes([
    0x31, 0xBB, 0x87, 0x09, 0xF8, 0xE4, 0xE7, 0x90,
    0xF4, 0x99, 0xCC, 0x69, 0x5F, 0x04, 0x46, 0x89,
    0x75, 0x5C, 0xF0, 0xCC, 0xBD, 0x2E, 0xA3, 0x68,
    0x0F, 0xD6, 0xDC, 0x4E, 0x7A, 0x4D, 0x63, 0xD0,
    0x60, 0x24, 0x2D, 0x75, 0x3C, 0x16, 0xFC, 0x41,
    0x1D, 0x6E, 0xDF, 0xA4, 0x0D, 0xD3, 0xA6, 0x9D,
    0xB9, 0x58, 0x88, 0xB2, 0xBB, 0x8D, 0x9F, 0x25,
    0x1B, 0x11, 0xB0, 0x41, 0x2F, 0xCD, 0x10, 0xB6, 0x84
])

# byte_3DE0 的 XOR 常量 (注意顺序与反汇编一致)
alphabet_xors = [0] * 65
alphabet_xors[0]  = 0x70
alphabet_xors[1]  = 0xF8
alphabet_xors[2]  = 0xC2
alphabet_xors[3]  = 0x39
alphabet_xors[4]  = 0xBA
alphabet_xors[5]  = 0xA0
alphabet_xors[6]  = 0xA1
alphabet_xors[7]  = 0xD7
alphabet_xors[8]  = 0xBC
alphabet_xors[9]  = 0xD0
alphabet_xors[10] = 0x86
alphabet_xors[11] = 0x22
alphabet_xors[12] = 0x13
alphabet_xors[13] = 0x49
alphabet_xors[14] = 0x08
alphabet_xors[15] = 0xC6
alphabet_xors[16] = 0x25
alphabet_xors[17] = 0x0D
alphabet_xors[18] = 0xA2
alphabet_xors[19] = 0x9F
alphabet_xors[20] = 0xE9
alphabet_xors[21] = 0x7B   # 3DF5
alphabet_xors[22] = 0xF5   # 3DF6
alphabet_xors[23] = 0x3F   # 3DF7
alphabet_xors[24] = 0x57   # 3DF8
alphabet_xors[25] = 0x8F   # 3DF9
alphabet_xors[26] = 0x86   # 3DFA
alphabet_xors[27] = 0x2F   # 3DFB
alphabet_xors[28] = 0x18   # 3DFC
alphabet_xors[29] = 0x2E   # 3DFD
alphabet_xors[30] = 0x07   # 3DFE
alphabet_xors[31] = 0xB5   # 3DFF
alphabet_xors[32] = 0x06
alphabet_xors[33] = 0x43
alphabet_xors[34] = 0x45
alphabet_xors[35] = 0x1C
alphabet_xors[36] = 0x56
alphabet_xors[37] = 0x7D
alphabet_xors[38] = 0x90
alphabet_xors[39] = 0x2C
alphabet_xors[40] = 0x73
alphabet_xors[41] = 0x01   # 3E09
alphabet_xors[42] = 0xAF   # 3E0A
alphabet_xors[43] = 0xD5   # 3E0B
alphabet_xors[44] = 0x7F
alphabet_xors[45] = 0xA0
alphabet_xors[46] = 0xD2
alphabet_xors[47] = 0xE8
alphabet_xors[48] = 0xCF   # 3E10
alphabet_xors[49] = 0x2F   # 3E11
alphabet_xors[50] = 0xF0   # 3E12
alphabet_xors[51] = 0xCB   # 3E13
alphabet_xors[52] = 0xC1   # 3E14
alphabet_xors[53] = 0xBC
alphabet_xors[54] = 0xAD
alphabet_xors[55] = 0x16
alphabet_xors[56] = 0x2F
alphabet_xors[57] = 0x24
alphabet_xors[58] = 0x86
alphabet_xors[59] = 0x76
alphabet_xors[60] = 0x17
alphabet_xors[61] = 0xF4
alphabet_xors[62] = 0x3B
alphabet_xors[63] = 0x99
alphabet_xors[64] = 0x84

# ==================== 还原 ====================
def xor_bytes(data, keys):
    return bytes(a ^ b for a, b in zip(data, keys))

# 1. 还原自定义 base64 字母表
alphabet = xor_bytes(raw_alphabet, alphabet_xors)[:64]
print("[+] Custom base64 alphabet:")
print("   ", alphabet.decode())
print()

# 2. 还原比较目标 (byte_3E30)
target = xor_bytes(raw_target, target_xors)
print("[+] Decrypted target (byte_3E30):")
print("   ", target.decode())
print()

# 3. 自定义 base64 解码
rev = {c: i for i, c in enumerate(alphabet)}
def custom_b64decode(data: bytes) -> bytes:
    res = bytearray()
    for i in range(0, len(data), 4):
        n = (rev[data[i]] << 18) | (rev[data[i+1]] << 12) | \
            (rev[data[i+2]] << 6) | rev[data[i+3]]
        res.append((n >> 16) & 0xff)
        res.append((n >> 8) & 0xff)
        res.append(n & 0xff)
    return bytes(res)

intermediate = custom_b64decode(target)
print("[+] Intermediate after custom base64 decode:")
print("   ", intermediate.hex())
print()

# 4. 还原 key 数据
a1 = xor_bytes(raw_key, key_xors)
print("[+] Decrypted key data (a1):")
print("   ", a1.hex())
print()

# 5. 恢复重复密钥 (sub_E4C 的 key)
#    intermediate[i] = a1[i] ^ key[i % len]
flag = xor_bytes(intermediate, a1)
print("[+] Recovered flag (XOR key):")
print("   ", flag.decode())
print()

print("=" * 50)
print("Flag:", flag.decode())
print("=" * 50)
\```

得到Part3=_Anti_Cheat_Expert

## 附件

- [Hook_SetCollisionEnabled.js](../attachments/292934/Hook_SetCollisionEnabled.js) — 1.15kb，5次下载
- [Hook_SetActorLocation.js](../attachments/292934/Hook_SetActorLocation.js) — 0.96kb，5次下载
- [Hook_SetActorHiddenInGame.js](../attachments/292934/Hook_SetActorHiddenInGame.js) — 2.29kb，5次下载
- [getClassName.js](../attachments/292934/getClassName.js) — 0.64kb，5次下载
- [GetAddrByName.js](../attachments/292934/GetAddrByName.js) — 5.38kb，5次下载
- [FindAddrInGWorld.js](../attachments/292934/FindAddrInGWorld.js) — 2.67kb，5次下载
- [FindActorsContains.js](../attachments/292934/FindActorsContains.js) — 2.71kb，5次下载

---

# 回复

## 回复 by dayDReam_10 (#2)

比赛附件太大了无法上传，有想要的请私聊

## 回复 by 墨穹呢 (#3)

感谢分享，文件太大可以试着上传github

## 回复 by HAzC (#4)

师傅好强，看完醍醐灌顶![image](https://bbs.kanxue.com/view/img/face/086.gif)

## 回复 by Je2em1ah (#5)

强强

## 回复 by Imxz (#6)

tql
