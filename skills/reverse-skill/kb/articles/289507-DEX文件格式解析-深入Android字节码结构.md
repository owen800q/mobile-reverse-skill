---
title: '[原创]DEX文件格式解析：深入Android字节码结构'
url: https://bbs.kanxue.com/thread-289507.htm
tid: 289507
author: A0tem
date: '2025-12-20'
tags: [Android安全, 原创, 基础理论, 逆向分析]
crawled_at: '2026-07-31T13:58:42+08:00'
replies: 6
---

(技术交流可加A0tem_ 备注看雪)

# 大体框架

Dex（Dalvik Executable）是Android系统中Java字节码的优化格式，相比传统的class文件，Dex具有更高的执行效率和更小的文件体积。

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_HH697ZYEXT9EAXT.png)

Dex文件整体架构

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_XV6BX3FF5SK34TS.png)

Dex文件采用索引+数据的分离设计，所有索引区在前，实际数据在后。这种设计优化了内存访问和加载速度。

| 123456789101112 | `文件偏移    区域名称           作用``0x00       dex_header        文件头信息``0x70       string_ids        字符串索引表``...        type_ids          类型索引表` `...        proto_ids         方法原型索引表``...        field_ids         字段索引表``...        method_ids        方法索引表``...        class_defs        类定义表``...        call_site_ids     调用点索引表(API 26+)``...        method_handles    方法句柄表(API 26+)``...        data              实际数据区``...        link_data         链接数据(可选)` |
|-|-|

# 数据类型

下面是解析Dex结构可能用到的数据类型

Android源码 定义了dex文件用到的数据结构

| 自定义类型 | 原类型 | 含义 |
|-|-|-|
| s1 | int8_t | 有符号单字节 |
| u1 | uint8_t | 无符号单字节 |
| s2 | int16_t |  |
| u2 | uint16_t |  |
| s4 | int32_t |  |
| u4 | uint32_t |  |
| s8 | int64_t |  |
| u8 | uint64_t |  |
| sleb128 | 无 | 有符号LEB128,可变长度 |
| uleb128 | 无 | 无符号LEB128,可变长度 |
| uleb128p1 | 无 | 等于ULEB128加1,可变长度 |

## LEB128

sleb128、uleb128、uleb128p1是**Dex文件中特有的LEB128类型**.在下述Android源码位置可以找到LEB128的实现.

sleb128:有符号LEB128

uleb128:无符号LEB128

uleb128p1:uleb128+1

每个LEB128由1-5字节组成,所有字节组合在一起表示一个32位的数据, 每个字节只有**低7位为有效位**,**最高位标识是否需要使用额外字节**

如果第1个字节的最高位为1,表示LEB128需要使用第2个字节,如果第2个字节的最高位为1,表示会使用第3个字节,依次类推,直到最后一个字节的最高位为0

uleb128读取代码如下

值得注意的是参数为二级指针,也就是说,调用该函数时会移动一级指针,一级指针的偏移量即为读取到的uleb128的大小

| 1234567891011121314151617181920212223242526272829 | `int readUnsignedLeb128(const u1** pStream) {``const u1* ptr = *pStream;   //初始化``int result = *(ptr++);      //获取第一个字节` `if (result > 0x7f) {        //如果第一个字节大于0x7f，那么就还有第二个字节``int cur = *(ptr++);     //第二个字节``result = (result & 0x7f) \| ((cur & 0x7f) << 7); //把两个字节合并``if (cur > 0x7f) {       //继续处理``cur = *(ptr++);``result \|= (cur & 0x7f) << 14;``if (cur > 0x7f) {``cur = *(ptr++);``result \|= (cur & 0x7f) << 21;``if (cur > 0x7f) {``/*``* Note: We don't check to see if cur is out of``* range here, meaning we tolerate garbage in the``* high four-order bits.``*/``cur = *(ptr++);``result \|= cur << 28;``}``}``}``}` `*pStream = ptr;``return result;``}` |
|-|-|

将LEB128编码的字节序列解码为32位无符号整数。

合并两个字节的操作十分巧妙:

| 1234567891011121314151617181920212223 | `步骤1：result & 0x7f``result = 0xAC = 1010 1100``0x7f   = 0x7F = 0111 1111``result & 0x7f = 0010 1100 = 0x2C = 44``作用：去掉第一个字节的继续标志，只保留数据位` `步骤2：cur & 0x7f``cur = 0x02 = 0000 0010` `0x7f = 0x7F = 0111 1111``cur & 0x7f = 0000 0010 = 0x02 = 2``作用：去掉第二个字节的继续标志（虽然本来就是0）` `步骤3：(cur & 0x7f) << 7``(cur & 0x7f) = 2 = 0000 0010``左移7位后 = 0000 0010 0000 0000 = 256``作用：将第二个字节的数据放到正确的位置（bit 7-13）` `步骤4：最终合并` `(result & 0x7f) = 44  =        0000 0000 0010 1100``((cur & 0x7f) << 7) = 256 =    0000 0001 0000 0000``─────────────────────``最终result = 44 \| 256 = 300 =  0000 0001 0010 1100` |
|-|-|

## encode_value

encoded_value是Dex文件中用于**存储常量值**的通用编码格式。它可以表示各种类型的常量数据，如数字、字符串、类型引用等。

1. 注解参数值：@MyAnnotation(name="test", value=42)
2. 静态字段初始值：public static final String TAG = "MyClass"
3. 数组常量：public static final int[] NUMBERS = {1,2,3}

| 1234567 | `// encoded_value不是固定结构体，而是变长的数据格式``// 由头字节 + 可变长度数据组成` `struct encoded_value {``u1 type_and_arg;        // 头字节：(value_arg << 5) \| value_type``u1 data[];              // 可变长度数据，根据类型和参数决定长度``};` |
|-|-|

### 编码结构解析

头字节解析(1字节)

| 12345678910 | `// 格式：(value_arg << 5) \| value_type``// 位布局：AAA TTTTT``// A = value_arg（高3位，0-7）``// T = value_type（低5位，0-31）` `u1 header = (value_arg << 5) \| value_type;` `// 解析方式``u1 value_type = header & 0x1F;        // 提取低5位``u1 value_arg = (header >> 5) & 0x07;  // 提取高3位` |
|-|-|

value_type含义(低五位)

指定数据的类型格式：

| 123456789101112131415161718 | `#define VALUE_BYTE          0x00    // 字节值``#define VALUE_SHORT         0x02    // 短整型``#define VALUE_CHAR          0x03    // 字符``#define VALUE_INT           0x04    // 整型``#define VALUE_LONG          0x06    // 长整型``#define VALUE_FLOAT         0x10    // 浮点数``#define VALUE_DOUBLE        0x11    // 双精度浮点数``#define VALUE_METHOD_TYPE   0x15    // 方法类型``#define VALUE_METHOD_HANDLE 0x16    // 方法句柄``#define VALUE_STRING        0x17    // 字符串索引``#define VALUE_TYPE          0x18    // 类型索引``#define VALUE_FIELD         0x19    // 字段索引``#define VALUE_METHOD        0x1A    // 方法索引``#define VALUE_ENUM          0x1B    // 枚举值``#define VALUE_ARRAY         0x1C    // 数组``#define VALUE_ANNOTATION    0x1D    // 注解``#define VALUE_NULL          0x1E    // null值``#define VALUE_BOOLEAN       0x1F    // 布尔值` |
|-|-|

value_arg函数(高3位)

根据类型不同，含义不同：

对于数值类型：value_arg = 字节数 - 1

| 12345 | `// 整数42只需1字节存储``value_arg = 1 - 1 = 0` `// 整数65536需要3字节存储` `value_arg = 3 - 1 = 2` |
|-|-|

对于布尔类型：value_arg直接表示值

| 12 | `// true: value_arg = 1``// false: value_arg = 0` |
|-|-|

对于索引类型(STRING、TYPE、FIELD、METHOD)

value_arg = 索引字节数 - 1

| 123456789 | `// 字符串索引15，需要1字节``value_type = VALUE_STRING (0x17)``value_arg = 1 - 1 = 0``header = (0 << 5) \| 0x17 = 0x17` `// 字符串索引300，需要2字节``value_type = VALUE_STRING (0x17)``value_arg = 2 - 1 = 1``header = (1 << 5) \| 0x17 = 0x37` |
|-|-|

对于特殊类型(NULL,ARRAY等)

value_arg通常为0或有特殊含义

| 123456789 | `// NULL值``value_type = VALUE_NULL (0x1E)``value_arg = 0  // 固定为0``header = (0 << 5) \| 0x1E = 0x1E` `// 数组``value_type = VALUE_ARRAY (0x1C)``value_arg = 0  // 固定为0，大小用uleb128单独编码``header = (0 << 5) \| 0x1C = 0x1C` |
|-|-|

## encoded_array

encoded_array是Dex文件中用于存储数组常量的数据结构，主要用于：

1. 静态字段初始值数组
2. 注解参数中的数组值
3. 枚举值列表

数据结构定义:

| 1234 | `encoded_array {``uleb128 size;              // 数组元素个数``encoded_value values[];    // 数组元素，每个都是encoded_value``}` |
|-|-|

| 名称 | 格式 | 说明 |
|-|-|-|
| size | uleb128 | 数组中的元素数量 |
| values | encoded_value[size] | 采用本部分所指定格式的一系列 `size`<br/>`encoded_value`<br/> 字节序列；依序串联。 |

 由于encoded_array.values数组元素为encoded_value,所以每个元素的大小不固定,不能当作一般的数组解析

## encoded_annotation

encoded_annotation是Dex文件中用于**存储注解实例**的数据结构，它表示一个具体的注解及其参数值。

| 12345678910 | `encoded_annotation {``uleb128 type_idx;                    // 注解类型的type_ids索引``uleb128 size;                        // 注解元素个数``annotation_element elements[];       // 注解元素数组``}` `annotation_element {``uleb128 name_idx;                    // 元素名称的string_ids索引``encoded_value value;                 // 元素值``}` |
|-|-|

 该类型主要在DexClassDef的Annotations部分使用,此处仅做介绍

| 名称 | 格式 | 说明 |
|-|-|-|
| type_idx | uleb128 | 注释的类型。这种类型必须是“类”（而非“数组”或“基元”）。 |
| size | uleb128 | 此注解中 name-value 映射的数量 |
| elements | annotation_element[size] | 注解的元素，直接以内嵌形式（不作为偏移量）表示。元素必须按 `string_id`<br/> 索引以升序进行排序。 |

注解是什么?

| 1234567891011121314 | `@Override  // 这是注解``public String toString() {``return "MyClass";``}` `@MyAnnotation(value = "test", count = 42)  // 带参数的注解``public class MyClass {` `@Nullable  // 标记可能为null``private String name;` `@Inject    // 依赖注入标记``private UserService userService;``}` |
|-|-|

特点：

- 编译后保留在字节码中
- 程序运行时可以读取和处理
- 影响程序的实际行为
- 可以携带参数和数据

# 文件头

官方好像不支持头文件，所以我们需要手搓或者偷一个，这里直接去安卓源码copy一下

<https://android.googlesource.com/platform/dalvik/+/refs/heads/master/libdex/DexFile.h>

<https://android.googlesource.com/platform/art/+/refs/heads/master/libdexfile/dex/dex_file.h>

copy之后还需要修改，让ai来即可

| 12345678910111213141516171819202122232425262728293031323334 | `struct dex_header {``// 文件标识部分``uint8_t  magic[8];           // "dex\n035\0" 魔数标识``uint32_t checksum;           // 文件完整性校验``uint8_t  signature[20];      // SHA-1数字签名` `// 文件基本信息``uint32_t file_size;          // 整个dex文件大小``uint32_t header_size;        // 头部大小(固定0x70)``uint32_t endian_tag;         // 字节序标记` `// 链接信息``uint32_t link_size;          // 链接段大小``uint32_t link_off;           // 链接段偏移``uint32_t map_off;            // 映射表偏移` `// 各索引区的大小和位置``uint32_t string_ids_size;    // 字符串数量``uint32_t string_ids_off;     // 字符串索引偏移``uint32_t type_ids_size;      // 类型数量` `uint32_t type_ids_off;       // 类型索引偏移``uint32_t proto_ids_size;     // 方法原型数量``uint32_t proto_ids_off;      // 方法原型偏移``uint32_t field_ids_size;     // 字段数量``uint32_t field_ids_off;      // 字段索引偏移``uint32_t method_ids_size;    // 方法数量``uint32_t method_ids_off;     // 方法索引偏移``uint32_t class_defs_size;    // 类定义数量``uint32_t class_defs_off;     // 类定义偏移` `// 数据区信息``uint32_t data_size;          // 数据段大小``uint32_t data_off;           // 数据段偏移``};` |
|-|-|

| 123456789101112131415161718 | `Hello, Welcome to DexHeader Analyse``Magic: dex``035``Version: 035``Checksum: 0x9d09f34b``Signature: 1ec3d2fc52b75c887f9f4fd540e7d7366ce53740``File size: 3028 bytes``Header size: 112 bytes``Endian tag: 0x12345678``Link size: 0``Link offset: 0x00000000``Map offset: 0x00000b04``String IDs size: 60``String IDs offset: 0x00000070``Type IDs size: 20``Type IDs offset: 0x00000160``Proto IDs size: 4``Proto IDs offset: 0x000001b0` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_A8A9S3APA5E5SP3.png)

## 文件头字段解析字段解析

**Magic**

魔数和版本

| 1 | `u1 magic[8];  // "dex\n035\0" 或 "dex\n038\0"` |
|-|-|

作用：标识文件类型和DEX格式版本

格式：

| 123 | `1.` `前``4``字节：``"dex\n"` `(``0x64` `0x65` `0x78` `0x0A``)` `-` `文件标识``2.` `中``3``字节：版本号，如` `"035"` `(Android` `5.0``-``7.1``) 或` `"038"` `(Android` `8.0``+``)``3.` `最后``1``字节：\``0` `空字符` |
|-|-|

用途：快速识别文件是否为DEX文件，以及使用的格式版本

**checksum校验和**

| 1 | `u4 checksum;  // Adler-32校验和` |
|-|-|

作用：验证文件完整性

计算范围：从signature字段开始到文件末尾的所有数据

算法：Adler-32（比CRC32更快但稍弱的校验算法）

用途：检测文件是否被损坏或篡改

**signature[20]-sha1签名**

| 1 | `u1 signature[20];  // SHA-1哈希值` |
|-|-|

作用：文件的唯一标识和完整性验证

计算范围：从file_size字段开始到文件末尾

算法：SHA-1（160位/20字节）

用途：

| 123 | `1.` `唯一标识DEX文件``2.` `更强的完整性验证``3.` `用于签名验证和缓存机制` |
|-|-|

**filesize-文件大小**

| 1 | `u4 file_size;  // 整个DEX文件的大小（字节）` |
|-|-|

作用：记录DEX文件的总大小

用途：

1. 内存分配
2. 文件完整性检查
3. 确定文件边界

**Header_size-头部大小**

| 1 | `u4 header_size;  // 固定为0x70 (112字节)` |
|-|-|

作用：DEX头部结构的大小

固定值：0x70 (112字节)

用途：

1. 向后兼容性
2. 确定数据区的起始位置

**endian_tag-字节序标记**

| 1 | `u4 endian_tag;  // 0x12345678 (小端) 或 0x78563412 (大端)` |
|-|-|

作用：标识文件使用的字节序

标准值：0x12345678（小端序，Android标准）

用途：

1. 跨平台兼容性
2. 确定如何读取多字节数据
3. Android DEX文件统一使用小端序

**link_size & link_off 链接段**

| 12 | `u4 link_size;  // 链接段大小``u4 link_off;   // 链接段偏移` |
|-|-|

作用：静态链接数据（很少使用）

通常值：都为0

用途：预留给静态链接的DEX文件使用（实际很少见）

m**ap_off-映射表偏移**

| 1 | `u4 map_off;  // 映射表的文件偏移` |
|-|-|

作用：指向DEX文件的映射表（map_list）

用途：

1. 描述DEX文件的整体结构
2. 列出所有数据区的类型、大小和位置
3. 用于验证和解析DEX文件

| 1234 | `struct map_list {``u4 size;                     // 映射条目数量``struct map_item list[];      // 映射条目数组``};` |
|-|-|

| 1234567 | `// 映射表项``struct map_item {``u2 type;                     // 数据类型``u2 unused;                   // 未使用，对齐填充``u4 size;                     // 该类型的条目数量``u4 offset;                   // 该数据区在文件中的偏移``};` |
|-|-|

映射表具体指的是什么:映射表是Dex文件的完整目录

映射表在文件末尾（例子中在 0x00000b04），它会列出所有数据区：

| 1234567891011121314 | `HEADER_ITEM          → DEX头部``STRING_ID_ITEM       → 字符串索引表``STRING_DATA_ITEM     → 字符串实际内容 ← Header没有！``TYPE_ID_ITEM         → 类型索引表``TYPE_LIST            → 参数类型列表 ← Header没有！``PROTO_ID_ITEM        → 方法原型表``FIELD_ID_ITEM        → 字段表``METHOD_ID_ITEM       → 方法表``CLASS_DEF_ITEM       → 类定义表``CLASS_DATA_ITEM      → 类的具体数据 ← Header没有！``CODE_ITEM            → 字节码 ← Header没有！``DEBUG_INFO_ITEM      → 调试信息 ← Header没有！``ANNOTATION_ITEM      → 注解 ← Header没有！``MAP_LIST             → 映射表自己` |
|-|-|

假设要找字符串"hello world"

方法一:只用Header

| 123 | `1. 读Header → string_ids_off = 0x70``2. 去0x70位置 → 找到string_id_item[5] = 0x000001f8``3. 0x000001f8是什么？不知道！Header没说字符串数据在哪` |
|-|-|

方法二:用映射表

| 12345 | `1. 读Header → map_off = 0xb04``2. 去0xb04读映射表 → 找到TYPE_STRING_DATA_ITEM在0x1e0``3. 读Header → string_ids_off = 0x70``4. 去0x70位置 → 找到string_id_item[5] = 0x000001f8``5. 去0x1f8位置 → 读到 "Hello World"` |
|-|-|

---

解析代码

| 123456789101112131415161718192021222324 | `void AnalyseMapList(struct dex_header* header)``{``u4 map_off = header->map_off;` `// 定位到map_list``struct map_list* map = (struct map_list*)(dex_data + map_off);` `printf("\n========== Map List (Mapping table) ==========\n");``printf("Mapping table offset: 0x%08x\n", map_off);``printf("Number of mapping entries: %u\n\n", map->size);` `printf("%-30s  %-10s  %-10s\n", "TYPE", "SIZE", "OFFSET");``printf("------------------------------------------------------\n");` `for (u4 i = 0; i < map->size; i++) {``const char* type_name = get_map_type_name(map->list[i].type);``u4 size = map->list[i].size;``u4 offset = map->list[i].offset;` `printf("%-30s  %-10u  0x%08x\n", type_name, size, offset);``}` `return;``}` |
|-|-|

| 1234567891011121314151617181920212223242526 | `const char* get_map_type_name(u2 type)``{``switch (type) {``case TYPE_HEADER_ITEM:                return "HEADER_ITEM";``case TYPE_STRING_ID_ITEM:             return "STRING_ID_ITEM";``case TYPE_TYPE_ID_ITEM:               return "TYPE_ID_ITEM";``case TYPE_PROTO_ID_ITEM:              return "PROTO_ID_ITEM";``case TYPE_FIELD_ID_ITEM:              return "FIELD_ID_ITEM";``case TYPE_METHOD_ID_ITEM:             return "METHOD_ID_ITEM";``case TYPE_CLASS_DEF_ITEM:             return "CLASS_DEF_ITEM";``case TYPE_CALL_SITE_ID_ITEM:          return "CALL_SITE_ID_ITEM";``case TYPE_METHOD_HANDLE_ITEM:         return "METHOD_HANDLE_ITEM";``case TYPE_MAP_LIST:                   return "MAP_LIST";``case TYPE_TYPE_LIST:                  return "TYPE_LIST";``case TYPE_ANNOTATION_SET_REF_LIST:    return "ANNOTATION_SET_REF_LIST";``case TYPE_ANNOTATION_SET_ITEM:        return "ANNOTATION_SET_ITEM";``case TYPE_CLASS_DATA_ITEM:            return "CLASS_DATA_ITEM";``case TYPE_CODE_ITEM:                  return "CODE_ITEM";``case TYPE_STRING_DATA_ITEM:           return "STRING_DATA_ITEM";``case TYPE_DEBUG_INFO_ITEM:            return "DEBUG_INFO_ITEM";``case TYPE_ANNOTATION_ITEM:            return "ANNOTATION_ITEM";``case TYPE_ENCODED_ARRAY_ITEM:         return "ENCODED_ARRAY_ITEM";``case TYPE_ANNOTATIONS_DIRECTORY_ITEM: return "ANNOTATIONS_DIRECTORY_ITEM";``default:                              return "UNKNOWN";``}``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_6GWUUUR228MHJFZ.png)

**string_ids_size & string_ids_off-字符串索引表**

| 12 | `u4 string_ids_size;  // 字符串数量``u4 string_ids_off;   // 字符串索引表偏移` |
|-|-|

作用：管理DEX中所有的字符串

内容：类名、方法名、字段名、常量字符串等

结构：每个条目4字节，指向实际字符串数据

用途：

1. 字符串去重（所有相同字符串只存储一次）
2. 通过索引快速访问字符串

**type_ids_size&type_ids_off-类型索引表**

| 12 | `u4 type_ids_size;  // 类型数量``u4 type_ids_off;   // 类型索引表偏移` |
|-|-|

作用：存储所有类型描述符

内容：类类型、基本类型、数组类型等

格式：每个条目4字节，指向string_ids中的类型描述符

**proto_ids_size & proto_ids_off-方法原型索引表**

| 12 | `u4 proto_ids_size;  // 方法原型数量``u4 proto_ids_off;   // 方法原型索引表偏移` |
|-|-|

作用：存储方法签名（参数类型+返回类型）

内容：方法的参数列表和返回类型组合

结构：每个条目12字节

用途：

| 12 | `1.` `方法签名去重``2.` `快速匹配方法调用` |
|-|-|

** field_ids_size & field_ids_off - 字段索引表**

| 12 | `u4 field_ids_size;  // 字段数量``u4 field_ids_off;   // 字段索引表偏移` |
|-|-|

作用：**存储所有字段的引用**

内容：所属类、字段类型、字段名

结构：每个条目8字节

用途：字段访问和引用

**method_ids_size & method_ids_off - 方法索引表**

| 12 | `u4 method_ids_size;  // 方法数量``u4 method_ids_off;   // 方法索引表偏移` |
|-|-|

作用：**存储所有方法的引用**

内容：所属类、方法原型、方法名

结构：每个条目8字节

用途：

1. 方法调用
2. 方法查找
3. Hook点定位（逆向分析重点）

**class_defs_size & class_defs_off - 类定义表**

| 12 | `u4 class_defs_size;  // 类定义数量``u4 class_defs_off;   // 类定义表偏移` |
|-|-|

作用：存储DEX中定义的所有类

内容：类的完整信息（字段、方法、访问标志等）

结构：每个条目32字节

用途：

1. 类加载
2. 反射
3. 逆向分析的主要目标

**data_size & data_off - 数据段**

| 12 | `u4 data_size;  // 数据段大小``u4 data_off;   // 数据段偏移` |
|-|-|

作用：存储实际的代码和数据

内容：

1. 字节码指令
2. 字符串数据
3. 注解
4. 调试信息等

特点：通常占DEX文件的大部分空间

直接打印即可

| 12345678910111213141516171819202122232425 | `void AnalyseDexHeader(struct dex_header* header)``{``printf("Hello, Welcome to DexHeader Analyse\n");``printf("Magic: %.8s\n", header->magic);``printf("Version: %.3s\n", &header->magic[4]);  // 版本号在magic字段的第4-6字节``printf("Checksum: 0x%08x\n", header->checksum);``printf("Signature: ");``for (int i = 0; i < 20; i++) {``printf("%02x", header->signature[i]);``}``printf("\n");``printf("File size: %u bytes\n", header->file_size);``printf("Header size: %u bytes\n", header->header_size);``printf("Endian tag: 0x%08x\n", header->endian_tag);``printf("Link size: %u\n", header->link_size);``printf("Link offset: 0x%08x\n", header->link_off);``printf("Map offset: 0x%08x\n", header->map_off);``printf("String IDs size: %u\n", header->string_ids_size);``printf("String IDs offset: 0x%08x\n", header->string_ids_off);``printf("Type IDs size: %u\n", header->type_ids_size);``printf("Type IDs offset: 0x%08x\n", header->type_ids_off);``printf("Proto IDs size: %u\n", header->proto_ids_size);``printf("Proto IDs offset: 0x%08x\n", header->proto_ids_off);``return;``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_6R7BQSY8XUQA69Y.png)

# 索引区

## string_ids字符串索引区

| 123 | `struct string_id_item {``uint32_t string_data_off;    // 指向data区中字符串数据的偏移``};` |
|-|-|

实际字符串数据格式(在data区)

| 1234 | `struct string_data_item {``uleb128 utf16_size;          // UTF-16长度``uint8_t data[];              // MUTF-8编码的字符串 + 0x00结尾``};` |
|-|-|

utf16_size:

数据类型：ULEB128变长编码
含义：字符串的UTF-16字符数量（不是字节数）
为什么用UTF-16长度：因为Java内部使用UTF-16编码，这个长度对应Java String的length()方法返回值
举例：字符串"Hello"的utf16_size = 5，中文"你好"的utf16_size = 2

data[]字段:

编码格式：MUTF-8 (Modified UTF-8)

结尾标记：必须以0x00字节结尾

长度：变长，实际字节数取决于字符内容和编码

什么是MUTF-8编码?

MUTF-8 (Modified UTF-8) 是Java虚拟机使用的一种UTF-8变体，与标准UTF-8有几个关键区别

1. MUTF-8使用1~3字节编码
2. 大于16位的Unicode编码U+10000~U+10ffff使用3字节编码
3. U+000采用2字节编码
4. 以0x00空字符作为字符串结尾

需要注意MUTF-8编码和UTF-8编码不同的情况只有:

1. 遇到NULL字符
2. 遇到四字节字符如emoji

MUTF-8字符串头部保存的是字符串长度,是uleb128类型

二级索引结构

| 12345678910111213141516171819202122 | `DEX文件``┌─────────────────────────────────────────────────────┐``│ Header                                              │``│   string_ids_size = 60                              │``│   string_ids_off = 0x70  ──────────────┐            │``├─────────────────────────────────────────│───────────┤``│ 0x70: String IDs 表（索引表）           │            │``│   ┌─────────────────────────────────────┘           │``│   ↓                                                 │``│   string_id_item[0].string_data_off = 0x3a8 ───┐    │``│   string_id_item[1].string_data_off = 0x3b0 ───│─┐  │``│   string_id_item[2].string_data_off = 0x3b8 ───│─│─┐│``│   ...                                          │ │ ││``├────────────────────────────────────────────────│─│─│┤``│ 0x3a8: String Data（实际字符串内容）           │ │ ││``│   ┌────────────────────────────────────────────┘ │ ││``│   ↓                                              │ ││``│   0x3a8: [len=3] "dex"                           │ ││``│   0x3b0: [len=3] "035"  ←─────────────────────────┘ ││``│   0x3b8: [len=1] "V"    ←────────────────────────────┘│``│   ...                                               │``└─────────────────────────────────────────────────────┘` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_EFQXWBF2AYNGGYU.png)

所以0x70就是string_id的起始位置，0x3C转换即为60，也就是string_id的数量

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_MCVWG2NZ42J6M7E.png)

可以看到存储的字符串为"1.0"

我们看一下第一个字符串

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_ATTR2SKEGU5GXN5.png)

可以看到string_data_off为0x542

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_HEPAXVC5Y7CP4AU.png)

03 31 2E 30 00

0x3表示长度为UTF-16字符长度为3

MUTF-8编码的字符串数据为"1.0"结尾为00

我们再以一个最长的为例子

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_2WM226PW9HNCHZR.png)

| 123456 | `58 7E 7E 44 38 7B 22 63 6F 6D 70 69 6C 61 74 69``6F 6E 2D 6D 6F 64 65 22 3A 22 72 65 6C 65 61 73``65 22 2C 22 68 61 73 2D 63 68 65 63 6B 73 75 6D``73 22 3A 66 61 6C 73 65 2C 22 6D 69 6E 2D 61 70``69 22 3A 32 32 2C 22 76 65 72 73 69 6F 6E 22 3A``22 32 2E 30 2E 38 38 22 7D 00` |
|-|-|

首先第一个字节0x58即为后面data的长度88,由于结尾还有00，即为89

解析代码

| 123456789101112131415 | `void AnalyseDexString(struct dex_header* header)``{``u4 string_ids_size = header->string_ids_size;` `printf("\n========== String IDs (String table) ==========\n");``printf("Total number of strings: %u\n\n", string_ids_size);` `// 遍历每个字符串，使用辅助函数``for (u4 i = 0; i < string_ids_size; i++) {``const char* str = get_string_by_idx(i);``printf("String[%u]: \"%s\"\n", i, str);``}` `return;``}` |
|-|-|

辅助函数为:

| 12345678910111213141516 | `const char* get_string_by_idx(u4 string_idx)``{``if (string_idx >= header->string_ids_size) {``return "INVALID_STRING_INDEX";``}` `struct string_id_item* string_ids = (struct string_id_item*)(dex_data + header->string_ids_off);``u4 string_data_off = string_ids[string_idx].string_data_off;``u1* ptr = dex_data + string_data_off;` `// 跳过ULEB128长度``while (*ptr & 0x80) ptr++;``ptr++;` `return (const char*)ptr;``}` |
|-|-|

辅助函数处理不同长度的data[]利用了c语言字符串以NULL结尾的特性。

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_US83KNVGBPV4FTJ.png)

## type_ids类型索引区

| 123 | `struct type_id_item {``uint32_t descriptor_idx;     // 指向string_ids的索引``};` |
|-|-|

作用：类型系统的核心

- 基本类型：I(int), Z(boolean), V(void)
- 对象类型：Ljava/lang/String;
- 数组类型：[I(int数组)

和string一样，读取的只是索引

| 12345678910111213141516 | `Type IDs表 (0x160)          String IDs表 (0x70)         String Data``┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐``│ type_ids[0]     │         │ string_ids[0]   │         │                 │``│   descriptor_idx│──┐      │   string_data_off│        │                 │``│   = 15          │  │      ├─────────────────┤         │                 │``├─────────────────┤  │      │ string_ids[1]   │         │                 │``│ type_ids[1]     │  │      │   ...           │         │                 │``│   descriptor_idx│  │      ├─────────────────┤         │                 │``│   = 23          │  │      │ ...             │         │                 │``├─────────────────┤  │      ├─────────────────┤         ├─────────────────┤``│ ...             │  └─────>│ string_ids[15]  │────────>│ "Ljava/lang/    │``└─────────────────┘         │   string_data_off│        │  Object;"       │``│   = 0x2a0       │         ├─────────────────┤``├─────────────────┤         │                 │``│ ...             │         │                 │``└─────────────────┘         └─────────────────┘` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_S954ZKGXM7EJNKP.png)

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_79P7V4A2XCR8NMN.png)

所以我们直接读取字符串即可获取类型了

| 12345 | `1. 读取 type_ids[i].descriptor_idx = 15``↓``2. 用15作为索引，读取 string_ids[15].string_data_off = 0x2a0``↓``3. 去0x2a0位置读取字符串 = "Ljava/lang/Object;"` |
|-|-|

| 123456789101112131415 | `void AnalyseTypeId(struct dex_header* header)``{``u4 type_ids_size = header->type_ids_size;` `printf("\n========== Type IDs (Type descriptor) ==========\n");``printf("Total number of types: %u\n\n", type_ids_size);` `// 遍历每个类型，使用辅助函数``for (u4 i = 0; i < type_ids_size; i++) {``const char* type_desc = get_type_by_idx(i);``printf("Type[%u]: %s\n", i, type_desc);``}` `return;``}` |
|-|-|

辅助函数

| 12345678910 | `const char* get_type_by_idx(u4 type_idx)``{``//安全性检查``if (type_idx >= header->type_ids_size) {``return "INVALID_TYPE_INDEX";``}` `struct type_id_item* type_ids = (struct type_id_item*)(dex_data + header->type_ids_off);``return get_string_by_idx(type_ids[type_idx].descriptor_idx);``}` |
|-|-|

这个辅助函数其实还是调用get_string_by_idx函数，只需要传进去正确的索引即可

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_RDE77ATMFNXAWQ7.png)

## proto_ids方法原型索引区

| 12345 | `struct proto_id_item {``uint32_t shorty_idx;         // 简短描述符的string_ids索引→ String IDs → "LLL"``uint32_t return_type_idx;    // 返回类型的type_ids索引→ Type IDs → "Ljava/lang/String;"``uint32_t parameters_off;     // 参数列表偏移(指向type_list)→ type_list → 参数类型列表``};` |
|-|-|

shorty_idx和return_type_idx其实我们已经知道是什么了，那么parameters_off呢？

参数列表结构：

| 12345678 | `struct type_list {``uint32_t size;               // 参数个数``struct type_item list[];     // 参数类型数组``};` `struct type_item {``uint16_t type_idx;           // type_ids索引``};` |
|-|-|

其实这个还是指向type_ids

在我们逆向的时候，ProtoIDs就是我们见到的

| 1 | `String concat(String str1, String str2)` |
|-|-|

对应的type_list

| 1234 | `struct type_list {``size = 2,                    // 两个参数``list = [17, 17]             // 都指向type_ids[17] = "Ljava/lang/String;"``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_35RNKNNMPXTK8BX.png)

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_9WBZ272P4K368SM.png)

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_5QVBTSRME7W8KZN.png)

第一个在字符串的索引为9，第二个type_idx为0，那么就按照type_idx的解析方式解析，type_idx为0，对应的string为I

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_HAUGV7B2PWFWCKF.png)

现在我们去找一下uint parameters_off值为0x52C

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_HMP37V3CH5R9XPA.png)

0x11也就是17，即

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_32UUDZMB3MZAE3A.png)

可以和上图对照验证

解析代码

| 12345678910111213141516171819202122232425262728293031323334353637383940414243 | `void AnalyseProtoId(struct dex_header* header)``{``u4 proto_ids_size = header->proto_ids_size;``u4 proto_ids_off = header->proto_ids_off;` `// 定位到proto_ids表``struct proto_id_item* proto_ids = (struct proto_id_item*)(dex_data + proto_ids_off);` `printf("\n========== Proto IDs (Method prototype) ==========\n");``printf("Total number of method prototypes: %u\n\n", proto_ids_size);` `for (u4 i = 0; i < proto_ids_size; i++) {``// 获取简短描述符 (shorty)``const char* shorty = get_string_by_idx(proto_ids[i].shorty_idx);` `// 获取返回类型``const char* return_type = get_type_by_idx(proto_ids[i].return_type_idx);` `// 获取参数列表偏移``u4 parameters_off = proto_ids[i].parameters_off;` `printf("Proto[%u]:\n", i);``printf("  Shorty: %s\n", shorty);``printf("  Return: %s\n", return_type);` `// 解析参数列表``if (parameters_off == 0) {``printf("  Params: (none)\n");``} else {``struct type_list* params = (struct type_list*)(dex_data + parameters_off);``printf("  Params: (");``for (u4 j = 0; j < params->size; j++) {``const char* param_type = get_type_by_idx(params->list[j]);``printf("%s", param_type);``if (j < params->size - 1) printf(", ");``}``printf(")\n");``}``printf("\n");``}` `return;``}` |
|-|-|

辅助函数都是原来用过的，就不讲解了

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_E4RZHXAXQNYGMUU.png)

## field_ids字段索引区

存储所有字段的索引

| 12345 | `struct field_id_item {``uint16_t class_idx;          // 所属类的type_ids索引``uint16_t type_idx;           // 字段类型的type_ids索引``uint32_t name_idx;           // 字段名的string_ids索引``};` |
|-|-|

对应java代码

| 1234 | `public class MainActivity {``private String TAG = "test";  // Field: MainActivity -> String TAG``private int count = 0;        // Field: MainActivity -> int count``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_C87NM6YRND35XS9.png)

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_VBXU5HV9VRC26QR.png)

这个比较简单，都是我们刚才学过的概念

| 123456789101112131415161718192021222324 | `void AnalyseFieldId(struct dex_header* header)``{``u4 field_ids_size = header->field_ids_size;``u4 field_ids_off = header->field_ids_off;` `// 定位到field_ids表``struct field_id_item* field_ids = (struct field_id_item*)(dex_data + field_ids_off);` `printf("\n========== Field IDs (Field table) ==========\n");``printf("Total number of fields: %u\n\n", field_ids_size);` `for (u4 i = 0; i < field_ids_size; i++) {``// 获取所属类``const char* class_name = get_type_by_idx(field_ids[i].class_idx);``// 获取字段类型``const char* field_type = get_type_by_idx(field_ids[i].type_idx);``// 获取字段名``const char* field_name = get_string_by_idx(field_ids[i].name_idx);` `printf("Field[%u]: %s -> %s %s\n", i, class_name, field_type, field_name);``}` `return;``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_E7P78UD5V7YZ4JK.png)

## method_ids方法索引区

存储所有方法的引用

| 12345 | `struct method_id_item {``uint16_t class_idx;          // 所属类的type_ids索引``uint16_t proto_idx;          // 方法原型的proto_ids索引``uint32_t name_idx;           // 方法名的string_ids索引``};` |
|-|-|

类似

| 1234567 | `Method IDs[i]``│``├── class_idx ──→ Type IDs ──→ "Lcom/kejian/test/MainActivity;"``│``├── proto_idx ──→ Proto IDs ──→ shorty="VL", return="V", params=(Bundle)``│``└── name_idx ──→ String IDs ──→ "onCreate"` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_SKDVQFMC2WUVBDJ.png)

第二个字段proto_idx

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_PD8YAQXNWZWB5BR.png)

解析代码

| 123456789101112131415161718192021222324252627282930 | `void AnalyseMethodId(struct dex_header* header)``{``u4 method_ids_size = header->method_ids_size;``u4 method_ids_off = header->method_ids_off;` `// 定位到method_ids表``struct method_id_item* method_ids = (struct method_id_item*)(dex_data + method_ids_off);` `// 定位到proto_ids表（用于获取方法原型）``struct proto_id_item* proto_ids = (struct proto_id_item*)(dex_data + header->proto_ids_off);` `printf("\n========== Method IDs (Method table) ==========\n");``printf("Total number of methods: %u\n\n", method_ids_size);` `for (u4 i = 0; i < method_ids_size; i++) {``// 获取所属类``const char* class_name = get_type_by_idx(method_ids[i].class_idx);``// 获取方法名``const char* method_name = get_string_by_idx(method_ids[i].name_idx);``// 获取方法原型的简短描述符``u2 proto_idx = method_ids[i].proto_idx;``const char* shorty = get_string_by_idx(proto_ids[proto_idx].shorty_idx);``const char* return_type = get_type_by_idx(proto_ids[proto_idx].return_type_idx);` `printf("Method[%u]: %s -> %s %s() [%s]\n",` `i, class_name, return_type, method_name, shorty);``}` `return;``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_NE9WD6KT5P7DQ73.png)

# 数据区

**这是最复杂的部分**

## class_def(类定义)

Class Defs（类定义）是DEX文件中本DEX定义的类的完整信息。

| 12345678910 | `struct class_def_item {``u4 class_idx;           // 类名索引``u4 access_flags;        // 访问标志 (public/final/abstract等)``u4 superclass_idx;      // 父类索引``u4 interfaces_off;      // 接口列表偏移``u4 source_file_idx;     // 源文件名索引` `u4 annotations_off;     // 注解信息``u4 class_data_off;      // 类数据（字段和方法的具体定义）` `u4 static_values_off;   // 静态字段初始值``};` |
|-|-|

### **class_idx-类标识**

含义: 指向**type_ids表**，标识这个类的类型

示例: type_ids[5] → "Lcom/example/MainActivity;"

用途: 获取类的完整限定名,也就是类名

### **superclass_idx-父类**

---

含义: 指向**type_ids表**，标识父类

特殊值: 0xFFFFFFFF (DEX_NO_INDEX) 表示没有父类

注意: 只有java.lang.Object没有父类

### **source_file_idx-源文件**

---

含义: 指向**string_ids表**，表示源文件名

示例: "MainActivity.java"

可选:可能为DEX_NO_INDEX(混淆或优化时)

| 123456789101112131415161718192021222324252627282930 | `void AnalyseClassDef(struct dex_header* header)``{``u4 class_defs_size = header->class_defs_size;``u4 class_defs_off = header->class_defs_off;` `// 定位到class_defs表``struct class_def_item* class_defs = (struct class_def_item*)(dex_data + class_defs_off);` `printf("\n========== Class Defs (Class Definition table) ==========\n");``printf("Total number of class definitions: %u\n\n", class_defs_size);` `for (u4 i = 0; i < class_defs_size; i++) {``printf("==================== Class[%u] ====================\n", i);` `// 获取类名``const char* class_name = get_type_by_idx(class_defs[i].class_idx);` `// 获取父类名 (0xFFFFFFFF表示无父类，即java.lang.Object)``const char* superclass_name = "none";``if (class_defs[i].superclass_idx != DEX_NO_INDEX) {``superclass_name = get_type_by_idx(class_defs[i].superclass_idx);``}` `// 获取源文件名 (可能为空)``const char* source_file = "unknown";``if (class_defs[i].source_file_idx != DEX_NO_INDEX) {``source_file = get_string_by_idx(class_defs[i].source_file_idx);``}` `......` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_2JSQXBN9N2V58HC.png)

<font style="color:rgb(255, 255, 255);">限定名限定名限定名</font>

### **access_flags-访问标志**

---

含义: 描述类的访问权限和特性

可能的值为:

| 12345678 | `#define ACC_PUBLIC          0x00000001  // public类``#define ACC_FINAL           0x00000010  // final类``#define ACC_SUPER           0x00000020  // 使用新的invokespecial语义``#define ACC_INTERFACE       0x00000200  // 接口``#define ACC_ABSTRACT        0x00000400  // 抽象类``#define ACC_SYNTHETIC       0x00001000  // 编译器生成``#define ACC_ANNOTATION      0x00002000  // 注解类型``#define ACC_ENUM            0x00004000  // 枚举类型` |
|-|-|

| 123456789 | `#define ACC_PUBLIC          0x0001    // public``#define ACC_PRIVATE         0x0002    // private``#define ACC_PROTECTED       0x0004    // protected``#define ACC_STATIC          0x0008    // static``#define ACC_FINAL           0x0010    // final``#define ACC_VOLATILE        0x0040    // volatile``#define ACC_TRANSIENT       0x0080    // transient``#define ACC_SYNTHETIC       0x1000    // 编译器生成``#define ACC_ENUM            0x4000    // 枚举常量` |
|-|-|

| 1234567891011121314 | `#define ACC_PUBLIC          0x0001    // public``#define ACC_PRIVATE         0x0002    // private``#define ACC_PROTECTED       0x0004    // protected``#define ACC_STATIC          0x0008    // static``#define ACC_FINAL           0x0010    // final``#define ACC_SYNCHRONIZED    0x0020    // synchronized``#define ACC_BRIDGE          0x0040    // 桥接方法``#define ACC_VARARGS         0x0080    // 可变参数``#define ACC_NATIVE          0x0100    // native``#define ACC_ABSTRACT        0x0400    // abstract``#define ACC_STRICT          0x0800    // strictfp``#define ACC_SYNTHETIC       0x1000    // 编译器生成``#define ACC_CONSTRUCTOR     0x10000   // 构造函数``#define ACC_DECLARED_SYNCHRONIZED 0x20000 // 声明同步` |
|-|-|

解析代码

| 12 | `u4 access_flags = class_defs[i].access_flags;``printf("Access Flags: 0x%04x (%s)\n", access_flags, get_access_flags_string(access_flags, 0)); //此处在分析类，所以第二个参数为0` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132 | `// 获取访问标志字符串``const char* get_access_flags_string(u4 flags, int is_method)``{``static char flag_str[256];``flag_str[0] = '\0';``//如果是类的访问标志``if (flags & ACC_PUBLIC) strcat(flag_str, "public ");``if (flags & ACC_PRIVATE) strcat(flag_str, "private ");``if (flags & ACC_PROTECTED) strcat(flag_str, "protected ");``if (flags & ACC_STATIC) strcat(flag_str, "static ");``if (flags & ACC_FINAL) strcat(flag_str, "final ");``if (flags & ACC_SYNCHRONIZED) strcat(flag_str, "synchronized ");``if (flags & ACC_VOLATILE) strcat(flag_str, "volatile ");``if (flags & ACC_TRANSIENT) strcat(flag_str, "transient ");``if (flags & ACC_NATIVE) strcat(flag_str, "native ");``if (flags & ACC_INTERFACE) strcat(flag_str, "interface ");``if (flags & ACC_ABSTRACT) strcat(flag_str, "abstract ");``if (flags & ACC_STRICT) strcat(flag_str, "strictfp ");``if (flags & ACC_SYNTHETIC) strcat(flag_str, "synthetic ");``if (flags & ACC_ANNOTATION) strcat(flag_str, "annotation ");``if (flags & ACC_ENUM) strcat(flag_str, "enum ");` `//如果是方法的访问标志``if (is_method) {``if (flags & ACC_BRIDGE) strcat(flag_str, "bridge ");``if (flags & ACC_VARARGS) strcat(flag_str, "varargs ");``if (flags & ACC_CONSTRUCTOR) strcat(flag_str, "constructor ");``if (flags & ACC_DECLARED_SYNCHRONIZED) strcat(flag_str, "declared_synchronized ");``}` `return flag_str;``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_DTQJF394HS4DXPG.png)

### **interfaces_off-接口列表**

---

含义: 指向**type_list结构**的偏移，包含实现的接口列表

值为0: 表示不实现任何接口

结构: 与方法参数的type_list相同格式

| 1234 | `struct type_list {``uint32_t size;               // 接口数量``uint16_t list[size];         // 接口类型索引数组``};` |
|-|-|

| 1234567891011121314151617 | `class_def_item``┌─────────────────────┐``│ class_idx           │``│ access_flags        │``│ superclass_idx      │``│ interfaces_off ─────┼──────┐``│ ...                 │      │``└─────────────────────┘      │``▼``type_list (接口列表)``┌─────────────────────┐``│ size = 3            │  // 实现了3个接口``├─────────────────────┤``│ list[0] = 5         │  → Type[5]: Ljava/io/Serializable;``│ list[1] = 8         │  → Type[8]: Ljava/lang/Comparable;``│ list[2] = 12        │  → Type[12]: Ljava/lang/Cloneable;``└─────────────────────┘` |
|-|-|

与其他结构的关系

| 1234567891011 | `┌─────────────────────────────────────────────────────────────┐``│                      DEX 文件结构                            │``├─────────────────────────────────────────────────────────────┤``│  string_ids  →  存储所有字符串                               │``│       ↑                                                      │``│  type_ids    →  存储类型描述符 (引用 string_ids)             │``│       ↑                                                      │``│  type_list   →  接口列表 (引用 type_ids)                     │``│       ↑                                                      │``│  class_def   →  类定义 (interfaces_off 指向 type_list)       │``└─────────────────────────────────────────────────────────────┘` |
|-|-|

解析代码

| 123456 | `if (class_defs[i].interfaces_off != 0) {``printf("\n--- Interfaces ---\n");``parse_interfaces(class_defs[i].interfaces_off);``} else {``printf("Interfaces: none\n");``}` |
|-|-|

| 12345678910 | `// 解析接口列表``void parse_interfaces(u4 interfaces_off)``{``struct type_list* interfaces = (struct type_list*)(dex_data + interfaces_off);``printf("Interface count: %u\n", interfaces->size);``for (u4 i = 0; i < interfaces->size; i++) {``const char* interface_name = get_type_by_idx(interfaces->list[i]);``printf("  [%u] %s\n", i, interface_name);``}``}` |
|-|-|

### **class_data_off-类数据**

---

含义: 指向class_data_item结构

重要性: 包含类的字段和方法定义

值为0: 表示没有字段和方法（如接口的某些情况）

| 123456789101112 | `// 注意：这个结构使用 ULEB128 编码，不是固定大小！``struct class_data_item {``uleb128 static_fields_size;      // 静态字段数量``uleb128 instance_fields_size;    // 实例字段数量``uleb128 direct_methods_size;     // 直接方法数量``uleb128 virtual_methods_size;    // 虚方法数量` `encoded_field  static_fields[static_fields_size];    // 静态字段数组``encoded_field  instance_fields[instance_fields_size]; // 实例字段数组``encoded_method direct_methods[direct_methods_size];   // 直接方法数组``encoded_method virtual_methods[virtual_methods_size]; // 虚方法数组``};` |
|-|-|

| 1234 | `struct encoded_field {``uleb128 field_idx_diff;   // 字段索引差值 (相对于前一个字段)``uleb128 access_flags;     // 访问标志``};` |
|-|-|

字段索引差值是什么

| 12345 | `实际索引 = 前一个索引 + 当前差值` `示例：``字段索引序列: 3, 4, 7, 8``存储的差值:   3, 1, 3, 1  (第一个是绝对值，后面是差值)` |
|-|-|

| 12345 | `struct encoded_method {``uleb128 method_idx_diff;  // 方法索引差值 (相对于前一个方法)``uleb128 access_flags;     // 访问标志``uleb128 code_off;         // 代码偏移 (指向 code_item，0表示无代码)``};` |
|-|-|

encoded_method比encoded_field多了一个code_off

| 1234567891011121314151617 | `struct code_item {``u2 registers_size;    // 寄存器数量``u2 ins_size;          // 输入参数数量 (包括 this)``u2 outs_size;         // 调用其他方法时的参数数量``u2 tries_size;        // try-catch 块数量``u4 debug_info_off;    //  调试信息偏移``u4 insns_size;        // 指令数量 (16位单元)``u2 insns[insns_size]; //  字节码指令``// 如果 tries_size > 0，后面还有 try_item 和 handler``};` `struct debug_info_item {``uleb128 line_start;           // 起始行号``uleb128 parameters_size;      // 参数数量``uleb128 parameter_names[];    // 参数名索引数组``u1 state_machine[];           // 调试状态机操作码``};` |
|-|-|

内存布局示意图

| 1234567891011121314151617181920212223242526 | `class_def_item``│``├── class_idx ──────────→ type_ids ──→ 类名``├── superclass_idx ─────→ type_ids ──→ 父类名``├── interfaces_off ─────→ type_list ──→ 接口列表``├── annotations_off ────→ 注解目录``├── static_values_off ──→ 静态字段初始值``│``└── class_data_off``│``▼``class_data_item``│``├── static_fields[]``│       └── field_idx_diff ──→ field_ids ──→ 字段名/类型``│``├── instance_fields[]``│       └── field_idx_diff ──→ field_ids ──→ 字段名/类型``│``├── direct_methods[]``│       ├── method_idx_diff ──→ method_ids ──→ 方法名/原型``│       └── code_off ──→ code_item ──→ 字节码``│``└── virtual_methods[]``├── method_idx_diff ──→ method_ids ──→ 方法名/原型``└── code_off ──→ code_item ──→ 字节码` |
|-|-|

解析代码

| 1234567 | `// 解析类数据（字段和方法）``if (class_defs[i].class_data_off != 0) {``printf("\n--- Class Data ---\n");``parse_class_data(class_defs[i].class_data_off, class_name);``} else {``printf("Class Data: none (interface or empty class)\n");``}` |
|-|-|

| 123456789101112131415161718192021222324252627282930313233343536373839 | `// 解析类数据（字段和方法）``void parse_class_data(u4 class_data_off, const char* class_name)``{``u1* ptr = dex_data + class_data_off;``u1* data_end = dex_data + file_size;` `// 读取字段和方法数量  注意这里传递的是二级指针，修改的是ptr的地址``u4 static_fields_size = read_uleb128(&ptr, data_end);``u4 instance_fields_size = read_uleb128(&ptr, data_end);``u4 direct_methods_size = read_uleb128(&ptr, data_end);``u4 virtual_methods_size = read_uleb128(&ptr, data_end);` `printf("Static fields: %u, Instance fields: %u\n", static_fields_size, instance_fields_size);``printf("Direct methods: %u, Virtual methods: %u\n", direct_methods_size, virtual_methods_size);` `// 解析静态字段``if (static_fields_size > 0) {``printf("\n  --- Static Fields ---\n");``parse_encoded_fields(&ptr, static_fields_size, "static", class_name);``}` `// 解析实例字段``if (instance_fields_size > 0) {``printf("\n  --- Instance Fields ---\n");``parse_encoded_fields(&ptr, instance_fields_size, "instance", class_name);``}` `// 解析直接方法``if (direct_methods_size > 0) {``printf("\n  --- Direct Methods ---\n");``parse_encoded_methods(&ptr, direct_methods_size, "direct", class_name);``}` `// 解析虚方法``if (virtual_methods_size > 0) {``printf("\n  --- Virtual Methods ---\n");``parse_encoded_methods(&ptr, virtual_methods_size, "virtual", class_name);``}``}` |
|-|-|

| 123456789101112131415161718192021 | `// 读取ULEB128编码的值``u4 read_uleb128(u1** data_ptr, u1* data_end)``{``u1* ptr = *data_ptr;``u4 result = 0;``int shift = 0;` `while (ptr < data_end && shift < 35) {``u1 byte = *ptr++;``result \|= (u4)(byte & 0x7F) << shift;` `if ((byte & 0x80) == 0) {``*data_ptr = ptr;``return result;``}``shift += 7;``}` `*data_ptr = ptr;``return result;``}` |
|-|-|

为什么传递二级指针呢？

C语言是值传递，在c语言中，函数参数都是复制一份副本传入的

一级指针的情况

| 123456789 | `void func(u1* ptr) {``ptr++;  // 修改的是副本，不影响外部``}` `int main() {``u1* ptr = 0x1000;``func(ptr);``// ptr 仍然是 0x1000``}` |
|-|-|

二级指针

| 123456789 | `void func(u1** ptr_addr) {``(*ptr_addr)++;  // 通过地址修改原始值``}` `int main() {``u1* ptr = 0x1000;``func(&ptr);``// ptr 变成了 0x1001``}` |
|-|-|

这样我们就正确读取了

static_fields_size,instance_fields_size,direct_methods_size,virtual_methods_size的值,现在可以分析这四个对应的结构了

四个**字段**但是只有两个结构，因此只需要定义两个函数即可

| 1234567891011121314151617181920212223242526 | `// 解析编码字段``void parse_encoded_fields(u1** ptr, u4 count, const char* type, const char* class_name)``{``u1* data_end = dex_data + file_size;``u4 field_idx = 0;` `struct field_id_item* field_ids = (struct field_id_item*)(dex_data + header->field_ids_off);` `for (u4 i = 0; i < count; i++) {``//先读取encoded_field结构体的值``u4 field_idx_diff = read_uleb128(ptr, data_end);``u4 access_flags = read_uleb128(ptr, data_end);` `field_idx += field_idx_diff;` `if (field_idx < header->field_ids_size) {``//获取字段的名字和类型``const char* field_name = get_string_by_idx(field_ids[field_idx].name_idx);``const char* field_type = get_type_by_idx(field_ids[field_idx].type_idx);` `printf("    [%u] %s %s %s (flags: 0x%x - %s)\n",` `field_idx, get_access_flags_string(access_flags, 0),` `field_type, field_name, access_flags, type);``}``}``}` |
|-|-|

get_access_flags_string已经介绍过了

| 1234567891011121314151617181920212223242526272829303132333435 | `// 解析编码方法``void parse_encoded_methods(u1** ptr, u4 count, const char* type, const char* class_name)``{``u1* data_end = dex_data + file_size;``u4 method_idx = 0;` `struct method_id_item* method_ids = (struct method_id_item*)(dex_data + header->method_ids_off);``struct proto_id_item* proto_ids = (struct proto_id_item*)(dex_data + header->proto_ids_off);` `for (u4 i = 0; i < count; i++) {``u4 method_idx_diff = read_uleb128(ptr, data_end);``u4 access_flags = read_uleb128(ptr, data_end);``u4 code_off = read_uleb128(ptr, data_end);` `method_idx += method_idx_diff;` `if (method_idx < header->method_ids_size) {``const char* method_name = get_string_by_idx(method_ids[method_idx].name_idx);``u2 proto_idx = method_ids[method_idx].proto_idx;``const char* return_type = get_type_by_idx(proto_ids[proto_idx].return_type_idx);` `printf("    [%u] %s %s %s() (flags: 0x%x - %s)",` `method_idx, get_access_flags_string(access_flags, 1),``return_type, method_name, access_flags, type);` `if (code_off != 0) {``printf(" [code: 0x%x]\n", code_off);``// 解析代码项和调试信息``parse_code_item(code_off, method_name);``} else {``printf(" [abstract/native]\n");``}``}``}``}` |
|-|-|

解析代码项和调试信息

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `void parse_code_item(u4 code_off, const char* method_name)``{``if (code_off == 0) return;` `u1* ptr = dex_data + code_off;``u1* data_end = dex_data + file_size;` `if (ptr + 16 > data_end) return;` `struct code_item* code = (struct code_item*)ptr;` `printf("      Code Info:\n");``printf("        Registers: %u, In: %u, Out: %u, Tries: %u\n",` `code->registers_size, code->ins_size, code->outs_size, code->tries_size);``printf("        Instructions: %u (16-bit units)\n", code->insns_size);` `// 解析调试信息``if (code->debug_info_off != 0) {``printf("        Debug info at: 0x%08x\n", code->debug_info_off);``parse_debug_info(code->debug_info_off, method_name);``} else {``printf("        Debug info: none\n");``}` `// 显示字节码（前几个指令）``if (code->insns_size > 0) {``printf("        Bytecode (first 8 instructions):\n");``u2* insns = (u2*)(ptr + 16);``u4 display_count = (code->insns_size < 8) ? code->insns_size : 8;` `for (u4 i = 0; i < display_count; i++) {``if ((u1*)(insns + i) >= data_end) break;``printf("          [%04x] %04x\n", i, insns[i]);``}` `if (code->insns_size > 8) {``printf("          ... (%u more instructions)\n", code->insns_size - 8);``}``}``}` |
|-|-|

解析调试信息

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113 | `// 解析调试信息``void parse_debug_info(u4 debug_info_off, const char* method_name)``{``if (debug_info_off == 0) return;` `u1* ptr = dex_data + debug_info_off;``u1* data_end = dex_data + file_size;` `if (ptr >= data_end) return;` `printf("        Debug Info for %s:\n", method_name);` `// 读取起始行号``u4 line_start = read_uleb128(&ptr, data_end);``printf("          Line start: %u\n", line_start);` `// 读取参数数量``u4 parameters_size = read_uleb128(&ptr, data_end);``printf("          Parameters: %u\n", parameters_size);` `// 读取参数名称``for (u4 i = 0; i < parameters_size; i++) {``if (ptr >= data_end) break;` `u4 name_idx = read_uleb128(&ptr, data_end);``if (name_idx != 0) {``printf("            [%u] %s\n", i, get_string_by_idx(name_idx - 1));``} else {``printf("            [%u] (no name)\n", i);``}``}` `// 解析调试操作码序列``printf("          Debug opcodes:\n");``u4 opcode_count = 0;``u4 current_line = line_start;``u4 current_pc = 0;` `while (ptr < data_end && opcode_count < 20) { // 限制显示前20个操作码``u1 opcode = *ptr++;` `switch (opcode) {``case DBG_END_SEQUENCE:``printf("            [%u] END_SEQUENCE\n", opcode_count);``return;` `case DBG_ADVANCE_PC: {``u4 addr_diff = read_uleb128(&ptr, data_end);``current_pc += addr_diff;``printf("            [%u] ADVANCE_PC +%u (pc=0x%x)\n",` `opcode_count, addr_diff, current_pc);``break;``}` `case DBG_ADVANCE_LINE: {``s4 line_diff = read_sleb128(&ptr, data_end);``current_line += line_diff;``printf("            [%u] ADVANCE_LINE %+d (line=%u)\n",` `opcode_count, line_diff, current_line);``break;``}` `case DBG_START_LOCAL: {``u4 register_num = read_uleb128(&ptr, data_end);``u4 name_idx = read_uleb128(&ptr, data_end);``u4 type_idx = read_uleb128(&ptr, data_end);` `const char* name = (name_idx != 0) ? get_string_by_idx(name_idx - 1) : "(no name)";``const char* type = (type_idx != 0) ? get_type_by_idx(type_idx - 1) : "(no type)";` `printf("            [%u] START_LOCAL v%u %s %s\n",` `opcode_count, register_num, type, name);``break;``}` `case DBG_END_LOCAL: {``u4 register_num = read_uleb128(&ptr, data_end);``printf("            [%u] END_LOCAL v%u\n", opcode_count, register_num);``break;``}` `case DBG_SET_FILE: {``u4 name_idx = read_uleb128(&ptr, data_end);``const char* filename = (name_idx != 0) ? get_string_by_idx(name_idx - 1) : "(no name)";``printf("            [%u] SET_FILE %s\n", opcode_count, filename);``break;``}` `default:``if (opcode >= 0x0a) {``// 特殊操作码：同时调整PC和行号``u4 adjusted_opcode = opcode - 0x0a;``u4 addr_diff = adjusted_opcode / 15;``s4 line_diff = (adjusted_opcode % 15) - 4;` `current_pc += addr_diff;``current_line += line_diff;` `printf("            [%u] SPECIAL_OPCODE 0x%02x (pc+%u, line%+d) -> pc=0x%x, line=%u\n",` `opcode_count, opcode, addr_diff, line_diff, current_pc, current_line);``} else {``printf("            [%u] UNKNOWN_OPCODE 0x%02x\n", opcode_count, opcode);``}``break;``}` `opcode_count++;``}` `if (opcode_count >= 20) {``printf("            ... (more debug opcodes)\n");``}``}` |
|-|-|

### **annotations_off-注解信息**

含义: 指向 annotations_directory_item 结构的偏移

值为0: 表示没有注解

内容:类级别，字段级别，方法级别的注解信息

这个很复杂，我们需要先了解一下结构

注解是什么?注解就是java中的@标记符，用户给代码添加元数据

| 12345678910 | `@Override                           // 方法注解``public void onCreate(Bundle saved) { }` `@Deprecated                         // 类注解``public class OldClass { }` `public void test(@NonNull String s) { }  // 参数注解` `@SerializedName("user_name")        // 字段注解``private String userName;` |
|-|-|

注解系统的层级结构:

| 123456789101112131415161718192021 | `class_def_item``│``└── annotations_off``│``▼``┌─────────────────────────────────────────────────────────┐``│           annotations_directory_item (注解目录)          │``│  ┌─────────────────────────────────────────────────────┐│``│  │ class_annotations_off ──────────────────────────────┼┼──→ 类注解``│  │ fields_size                                         ││``│  │ annotated_methods_size                              ││``│  │ annotated_parameters_size                           ││``│  ├─────────────────────────────────────────────────────┤│``│  │ field_annotation[0] ────────────────────────────────┼┼──→ 字段0的注解``│  │ field_annotation[1] ────────────────────────────────┼┼──→ 字段1的注解``│  ├─────────────────────────────────────────────────────┤│``│  │ method_annotation[0] ───────────────────────────────┼┼──→ 方法0的注解``│  ├─────────────────────────────────────────────────────┤│``│  │ parameter_annotation[0] ────────────────────────────┼┼──→ 方法0参数的注解``│  └─────────────────────────────────────────────────────┘│``└─────────────────────────────────────────────────────────┘` |
|-|-|

第一层annotations_directory_item(注解目录)

一个类的所有注解的目录！

| 1234567891011 | `struct annotations_directory_item {``uint32_t class_annotations_off;      // 类注解偏移``uint32_t fields_size;               // 带注解的字段数量``uint32_t annotated_methods_size;    // 带注解的方法数量``uint32_t annotated_parameters_size; // 带注解参数的方法数量` `// 后跟数组:` `field_annotation field_annotations[fields_size];``method_annotation method_annotations[annotated_methods_size];``parameter_annotation parameter_annotations[annotated_parameters_size];``};` |
|-|-|

| 1234567891011121314 | `struct field_annotation {``u4 field_idx;         // 字段索引 (指向 field_ids)``u4 annotations_off;   // 注解集偏移 (指向 annotation_set_item)``};` `struct method_annotation {``u4 method_idx;        // 方法索引 (指向 method_ids)``u4 annotations_off;   // 注解集偏移 (指向 annotation_set_item)``};` `struct parameter_annotation {``u4 method_idx;        // 方法索引 (指向 method_ids)``u4 annotations_off;   // 注解集引用列表偏移 (指向 annotation_set_ref_list)` `};` |
|-|-|

类注解不需要索引，因为一个类只有一组注解

参数注解比较特殊，因为一个方法可能多个参数,每个参数可能都有自己的注解

| 12345678910 | `// 注解集引用列表 (参数注解专用)``struct annotation_set_ref_list {``u4 size;                              // 参数数量``annotation_set_ref_item list[size];   // 每个参数的注解集引用``};` `// 注解集引用项``struct annotation_set_ref_item {``u4 annotations_off;                   // 指向 annotation_set_item (0表示该参数无注解)``};` |
|-|-|

方法注解为:

| 123456789101112 | `//方法注解``method_annotation``│``└── annotations_off ──→ annotation_set_item (一个方法的所有注解)``//参数注解``parameter_annotation``│``└── annotations_off ──→ annotation_set_ref_list (参数列表)``│``├── list[0].annotations_off ──→ annotation_set_item (参数0的注解)``├── list[1].annotations_off ──→ annotation_set_item (参数1的注解)``└── list[2].annotations_off ──→ annotation_set_item (参数2的注解)` |
|-|-|

第二层:annotation_set_item (注解集合)

存储一组注解(一个元素可能有多个注解)

| 1234 | `struct annotation_set_item {``u4 size;                      // 注解数量``u4 entries[size];             // 每个注解的偏移``};` |
|-|-|

例如一个方法可能同时有 @Override @Deprecated

第三层:annotation_item (注解项)

| 1234 | `struct annotation_item {``u1 visibility;                // 可见性 (BUILD/RUNTIME/SYSTEM)``encoded_annotation annotation; // 注解内容``};` |
|-|-|

第4层：encoded_annotation (注解内容)

| 12345 | `struct encoded_annotation {``uleb128 type_idx;             // 注解类型 (如 @Override)``uleb128 size;                 // 参数数量``annotation_element elements[size]; // 参数列表``};` |
|-|-|

| 1234 | `struct annotation_element {``uleb128 name_idx;                    // 元素名称``encoded_value value;                 // 元素值``};` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334 | `第1层 (注解目录)                          第2层 (注解集合)                         第3层 (注解项)                           第4层 (注解内容)``┌──────────────────────────┐             ┌──────────────────────┐                ┌──────────────────────┐                ┌──────────────────────┐``│ annotations_directory    │             │ annotation_set_item  │                │ annotation_item      │                │ encoded_annotation   │``│ ┌──────────────────────┐ │             │ ┌──────────────────┐ │                │ ┌──────────────────┐ │                │ ┌──────────────────┐ │``│ │class_annotations_off─┼─┼────────────→│ │ size = 2         │ │                │ │ visibility=SYSTEM│ │                │ │ type_idx = 14    │ │``│ │                      │ │             │ ├──────────────────┤ │                │ ├──────────────────┤ │                │ │ (InnerClass)     │ │``│ │fields_size = 1       │ │             │ │ entry[0] ────────┼─┼───────────────→│ │ annotation ──────┼─┼───────────────→│ ├──────────────────┤ │``│ │                      │ │             │ ├──────────────────┤ │                │ │                  │ │                │ │ size = 2         │ │``│ │annotated_methods_size│ │             │ │ entry[1] ────────┼─┼──┐             │ └──────────────────┘ │                │ ├──────────────────┤ │``│ │= 0                   │ │             │ │                  │ │  │             └──────────────────────┘                │ │ elements[0]:     │ │``│ │                      │ │             │ └──────────────────┘ │  │                                                     │ │  name=accessFlags│ │``│ │annotated_parameters  │ │             └──────────────────────┘  │             ┌──────────────────────┐                │ │  value=25        │ │``│ │_size = 0             │ │                                       │             │ annotation_item      │                │ ├──────────────────┤ │``│ └──────────────────────┘ │                                       │             │ ┌──────────────────┐ │                │ │ elements[1]:     │ │``│                          │                                       └────────────→│ │ visibility=SYSTEM│ │                │ │  name=name       │ │``│ ┌──────────────────────┐ │                                                     │ ├──────────────────┤ │                │ │  value="color"   │ │``│ │field_annotation[0]   │ │             ┌──────────────────────┐                │ │ annotation ──────┼─┼──┐             │ └──────────────────┘ │``│ │ ┌──────────────────┐ │ │             │ annotation_set_item  │                │ │                  │ │  │             └──────────────────────┘``│ │ │ field_idx = 5    │ │ │             │ ┌──────────────────┐ │                │ └──────────────────┘ │  │``│ │ ├──────────────────┤ │ │             │ │ size = 1         │ │                └──────────────────────┘  │             ┌──────────────────────┐``│ │ │ annotations_off──┼─┼─┼────────────→│ ├──────────────────┤ │                                          │             │ encoded_annotation   │``│ │ │                  │ │ │             │ │ entry[0] ────────┼─┼──┐                                       │             │ ┌──────────────────┐ │``│ │ └──────────────────┘ │ │             │ │                  │ │  │                                       └────────────→│ │ type_idx = 13    │ │``│ └──────────────────────┘ │             │ └──────────────────┘ │  │                                                     │ │ (EnclosingClass) │ │``│                          │             └──────────────────────┘  │                                                     │ ├──────────────────┤ │``└──────────────────────────┘                                       │             ┌──────────────────────┐                │ │ size = 1         │ │``│             │ annotation_item      │                │ ├──────────────────┤ │``│             │ ┌──────────────────┐ │                │ │ elements[0]:     │ │``└────────────→│ │ visibility=RUNTIME│ │               │ │  name=value      │ │``│ ├──────────────────┤ │                │ │  value=12        │ │``│ │ annotation ──────┼─┼───────────────→│ └──────────────────┘ │``│ │                  │ │                └──────────────────────┘``│ └──────────────────┘ │``└──────────────────────┘` |
|-|-|

简化

| 12345678910111213141516171819202122 | `第1层                    第2层                    第3层                    第4层``(注解目录)               (注解集合)               (注解项)                 (注解内容)` `┌─────────────┐         ┌─────────────┐         ┌─────────────┐         ┌─────────────┐``│ directory   │         │ set_item    │         │ item        │         │ encoded     │``│             │         │             │         │             │         │ annotation  │``│ class_off ──┼────────→│ size=2      │         │ visibility  │         │             │``│             │         │ entry[0] ───┼────────→│ annotation──┼────────→│ type_idx    │``│ field[0]    │         │ entry[1] ───┼──┐      │             │         │ size        │``│  └─off ─────┼──┐      └─────────────┘  │      └─────────────┘         │ elements[]  │``│             │  │                       │                              │  name=value │``│ method[0]   │  │      ┌─────────────┐  │      ┌─────────────┐         └─────────────┘``│  └─off ─────┼──┼─────→│ set_item    │  │      │ item        │``│             │  │      │ size=1      │  └─────→│ visibility  │``│ param[0]    │  │      │ entry[0] ───┼────────→│ annotation──┼────────→ ...``│  └─off ─────┼──┼─────→└─────────────┘         └─────────────┘``└─────────────┘  │``│      ┌─────────────┐``└─────→│ set_item    │``│ size=1      │``│ entry[0] ───┼────────→ ...``└─────────────┘` |
|-|-|

解析代码,综上分析我们知道了类注解，字段注解，方法注解，可以用一套代码，但是参数注解需要多一步

| 1234567 | `// 解析注解信息``if (class_defs[i].annotations_off != 0) {``printf("\n--- Annotations ---\n");``parse_annotations_directory(class_defs[i].annotations_off);``} else {``printf("Annotations: none\n");``}` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273 | `// 解析注解目录``void parse_annotations_directory(u4 annotations_off)``{``if (annotations_off == 0) return;` `u1* ptr = dex_data + annotations_off;``u1* data_end = dex_data + file_size;` `if (ptr + 16 > data_end) return;` `struct annotations_directory_item* dir = (struct annotations_directory_item*)ptr;` `printf("Class annotations: 0x%08x\n", dir->class_annotations_off);``printf("Annotated fields: %u\n", dir->fields_size);``printf("Annotated methods: %u\n", dir->annotated_methods_size);``printf("Annotated parameters: %u\n", dir->annotated_parameters_size);` `// 解析类注解``if (dir->class_annotations_off != 0) {``printf("\n  --- Class Annotations ---\n");``parse_annotation_set(dir->class_annotations_off, "    ");``}` `// 跳过目录头部``ptr += 16;` `// 解析字段注解``if (dir->fields_size > 0) {``printf("\n  --- Field Annotations ---\n");``for (u4 i = 0; i < dir->fields_size; i++) {``if (ptr + 8 > data_end) break;` `struct field_annotation* field_ann = (struct field_annotation*)ptr;``printf("    Field[%u]: annotations at 0x%08x\n",` `field_ann->field_idx, field_ann->annotations_off);` `if (field_ann->annotations_off != 0) {``parse_annotation_set(field_ann->annotations_off, "      ");``}``ptr += 8;``}``}` `// 解析方法注解``if (dir->annotated_methods_size > 0) {``printf("\n  --- Method Annotations ---\n");``for (u4 i = 0; i < dir->annotated_methods_size; i++) {``if (ptr + 8 > data_end) break;` `struct method_annotation* method_ann = (struct method_annotation*)ptr;``printf("    Method[%u]: annotations at 0x%08x\n",` `method_ann->method_idx, method_ann->annotations_off);` `if (method_ann->annotations_off != 0) {``parse_annotation_set(method_ann->annotations_off, "      ");``}``ptr += 8;``}``}` `// 解析参数注解``if (dir->annotated_parameters_size > 0) {``printf("\n  --- Parameter Annotations ---\n");``for (u4 i = 0; i < dir->annotated_parameters_size; i++) {``if (ptr + 8 > data_end) break;` `struct parameter_annotation* param_ann = (struct parameter_annotation*)ptr;``printf("    Method[%u] parameters: annotations at 0x%08x\n",` `param_ann->method_idx, param_ann->annotations_off);``ptr += 8;``}``}``}` |
|-|-|

以解析类注解为例，概括字段注解，方法注解

| 12345 | `// 解析类注解``if (dir->class_annotations_off != 0) {``printf("\n  --- Class Annotations ---\n");``parse_annotation_set(dir->class_annotations_off, "    ");``}` |
|-|-|

解析注解集，也就是处理第二层

| 12345678910111213141516171819202122232425262728 | `// 解析注解集``void parse_annotation_set(u4 annotation_set_off, const char* prefix)``{``if (annotation_set_off == 0) return;` `u1* ptr = dex_data + annotation_set_off;``u1* data_end = dex_data + file_size;` `if (ptr + 4 > data_end) return;` `struct annotation_set_item* set = (struct annotation_set_item*)ptr;``printf("%sAnnotation set size: %u\n", prefix, set->size);` `ptr += 4;` `for (u4 i = 0; i < set->size; i++) {``if (ptr + 4 > data_end) break;` `u4 annotation_off = *(u4*)ptr;``printf("%s  [%u] Annotation at 0x%08x\n", prefix, i, annotation_off);` `if (annotation_off != 0) {``//解析注解项``parse_annotation_item(annotation_off, prefix);``}``ptr += 4;``}``}` |
|-|-|

下面该解析第三层了，也就是注解项

| 123456789101112131415161718 | `// 解析注解项``void parse_annotation_item(u4 annotation_off, const char* prefix)``{``if (annotation_off == 0) return;` `u1* ptr = dex_data + annotation_off;``u1* data_end = dex_data + file_size;` `if (ptr >= data_end) return;` `u1 visibility = *ptr++;``//打印注解项的可见性``printf("%s    Visibility: %s\n", prefix, get_visibility_string(visibility));` `printf("%s    Encoded annotation:\n", prefix);``//解析注解内容``parse_encoded_annotation(&ptr, prefix);``}` |
|-|-|

| 12345678910 | `// 获取可见性字符串``const char* get_visibility_string(u1 visibility)``{``switch (visibility) {``case VISIBILITY_BUILD:   return "BUILD";``case VISIBILITY_RUNTIME: return "RUNTIME";``case VISIBILITY_SYSTEM:  return "SYSTEM";``default:                 return "UNKNOWN";``}``}` |
|-|-|

下面第四层，解析注解内容

| 123456789101112131415161718192021222324252627 | `// 解析编码注解``void parse_encoded_annotation(u1** ptr, const char* prefix)``{``u1* data_end = dex_data + file_size;` `if (*ptr >= data_end) return;` `// 读取类型索引``u4 type_idx = read_uleb128(ptr, data_end);``printf("%s      Type: %s\n", prefix, get_type_by_idx(type_idx));` `// 读取元素数量``u4 size = read_uleb128(ptr, data_end);``printf("%s      Elements: %u\n", prefix, size);` `for (u4 i = 0; i < size; i++) {``if (*ptr >= data_end) break;` `// 读取元素名称索引``u4 name_idx = read_uleb128(ptr, data_end);``printf("%s        [%u] %s = ", prefix, i, get_string_by_idx(name_idx));` `// 读取元素值``parse_encoded_value(ptr);``printf("\n");``}``}` |
|-|-|

parse_encoded_value解析

| 1234 | `struct annotation_element {``uleb128 name_idx;                    // 元素名称``encoded_value value;                 // 元素值 ← parse_encoded_value 解析这个！``};` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 | `// 解析编码值``void parse_encoded_value(u1** ptr)``{``u1* data_end = dex_data + file_size;` `if (*ptr >= data_end) return;` `u1 type_and_arg = **ptr;``(*ptr)++;` `u1 value_type = (type_and_arg >> 5) & 0x1F;``u1 value_arg = type_and_arg & 0x1F;` `switch (value_type) {``case VALUE_BYTE:``printf("byte: %d", (s1)**ptr);``(*ptr)++;``break;` `case VALUE_SHORT: {``s2 val = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``val \|= ((s2)**ptr) << (i * 8);``(*ptr)++;``}``printf("short: %d", val);``break;``}` `case VALUE_INT: {``s4 val = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``val \|= ((s4)**ptr) << (i * 8);``(*ptr)++;``}``printf("int: %d", val);``break;``}` `case VALUE_STRING: {``u4 string_idx = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``string_idx \|= ((u4)**ptr) << (i * 8);``(*ptr)++;``}``printf("string: \"%s\"", get_string_by_idx(string_idx));``break;``}` `case VALUE_TYPE: {``u4 type_idx = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``type_idx \|= ((u4)**ptr) << (i * 8);``(*ptr)++;``}``printf("type: %s", get_type_by_idx(type_idx));``break;``}` `case VALUE_BOOLEAN:``printf("boolean: %s", value_arg ? "true" : "false");``break;` `case VALUE_NULL:``printf("null");``break;` `default:``printf("unknown_type(0x%02x)", value_type);``// 跳过未知类型的数据``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``(*ptr)++;``}``break;``}``}` |
|-|-|

### **static_values_off-静态初始值**

含义: 指向encoded_array_item，包含静态字段的初始值

值为0: 表示没有静态字段初始值

用途: 静态字段的默认值

| 1234 | `struct encoded_array_item {``uleb128 size;                // 元素数量``encoded_value values[size];  // 编码值数组``};` |
|-|-|

| 1234 | `struct encoded_value {``uint8_t type_and_arg;        // 类型（高5位）+ 参数（低3位）``uint8_t value[arg+1];        // 实际值数据``};` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_2ZKWWKRRP35QW6X.png)

解析静态值

| 12345678 | `// 解析静态值``if (class_defs[i].static_values_off != 0) {``printf("\n--- Static Values ---\n");``parse_static_values(class_defs[i].static_values_off);``} else {``printf("Static Values: none\n");``}` |
|-|-|

parse_static_values

| 123456789101112131415 | `// 解析静态值``void parse_static_values(u4 static_values_off)``{``u1* ptr = dex_data + static_values_off;``u1* data_end = dex_data + file_size;` `u4 size = read_uleb128(&ptr, data_end);``printf("Static values count: %u\n", size);` `for (u4 i = 0; i < size; i++) {``printf("  [%u] ", i);``parse_encoded_value(&ptr);``printf("\n");``}``}` |
|-|-|

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576 | `// 解析编码值``void parse_encoded_value(u1** ptr)``{``u1* data_end = dex_data + file_size;` `if (*ptr >= data_end) return;` `u1 type_and_arg = **ptr;``(*ptr)++;` `u1 value_type = (type_and_arg >> 5) & 0x1F;` `u1 value_arg = type_and_arg & 0x1F;` `switch (value_type) {``case VALUE_BYTE:``printf("byte: %d", (s1)**ptr);``(*ptr)++;``break;` `case VALUE_SHORT: {``s2 val = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``val \|= ((s2)**ptr) << (i * 8);``(*ptr)++;``}``printf("short: %d", val);``break;``}` `case VALUE_INT: {``s4 val = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``val \|= ((s4)**ptr) << (i * 8);``(*ptr)++;``}``printf("int: %d", val);``break;``}` `case VALUE_STRING: {``u4 string_idx = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``string_idx \|= ((u4)**ptr) << (i * 8);``(*ptr)++;``}``printf("string: \"%s\"", get_string_by_idx(string_idx));``break;``}` `case VALUE_TYPE: {``u4 type_idx = 0;``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``type_idx \|= ((u4)**ptr) << (i * 8);``(*ptr)++;``}``printf("type: %s", get_type_by_idx(type_idx));``break;``}` `case VALUE_BOOLEAN:``printf("boolean: %s", value_arg ? "true" : "false");``break;` `case VALUE_NULL:``printf("null");``break;` `default:``printf("unknown_type(0x%02x)", value_type);``// 跳过未知类型的数据``for (int i = 0; i <= value_arg && *ptr < data_end; i++) {``(*ptr)++;``}``break;``}``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/1060705_YMRZXGYW5RTN6AH.png)

## Data

Data区是DEX文件的核心内容区，**存储所有实际数据**，而**前面的索引表只是"目录"**

## link_data

存储静态链接信息,但是通常为空，因为Android使用**动态链接**，类和方法在运行时解析。link_data是**为早期的静态链接优化设计的**，现代Android基本不用

[参考](https://bbs.kanxue.com/thread-284995.htm)

上传的附件：
- Dex结构.zip

（70.33kb，29次下载）

---

# 回复

## 回复 by 温泉划水鱼 (#2)

*2025-12-21 02:01*

tql，学习

## 回复 by mb_asiwnxyv (#3)

*2025-12-21 11:14*

感谢分享

## 回复 by zgFree (#4)

*2025-12-21 14:54*

感谢分享 ，学习

## 回复 by huangjw (#5)

*2025-12-22 09:29*

收藏

## 回复 by Imxz (#6)

*2025-12-22 10:53*

tql

## 回复 by mb_wsvngnua (#7)

*2025-12-25 17:03*

感谢大佬分享，欢迎回踩，相互学习
