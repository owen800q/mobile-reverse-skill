---
title: '[原创]Android一二三代壳实现'
url: https://bbs.kanxue.com/thread-291182.htm
tid: 291182
author: mb_wckjnnha
date: '2026-05-11'
tags: [Android安全, 原创, 混淆加固]
crawled_at: '2026-07-31T13:52:48+08:00'
replies: 2
---

## 一代壳

落地壳 会将文件保存到本地

```java
package com.example.myfirstshell;

import android.app.Application;
import android.content.Context;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Array;
import java.lang.reflect.Field;

import dalvik.system.DexClassLoader;

public class StubApplication extends Application {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try {
            // 在 /data/data/包名/app_payload 下创建私有目录
            File payloadDir = getDir("payload",MODE_PRIVATE);
            // 用来拼接多个解密后 dex 文件的绝对路径
            StringBuilder dexPathBuilder = new StringBuilder();
            // assets 目录下的三个加密 dex 文件
            String[] dexname = {"classes.dex","classes2.dex","classes3.dex"};
            // 循环解密
            for(String name : dexname)
            {
                // 创建新文件，存放解密后的 dex
                File dexFile = new File(payloadDir,name);
                // 打开 assets 中的加密 dex
                InputStream is = getAssets().open(name);
                // 创建输出流
                FileOutputStream fos = new FileOutputStream(dexFile);
                byte[] buffer = new byte[1024 * 8];
                int len;
                // 逐块读取
                while((len = is.read(buffer)) != -1)
                {
                    // 解密
                    for(int i = 0; i < len; i++)
                    {
                        buffer[i] ^= 0x66;
                    }
                    fos.write(buffer,0,len);
                }
                fos.flush();
                fos.close();
                is.close();

                // 拼接路径，中间使用冒号分隔
                if(dexPathBuilder.length() > 0)
                {
                    dexPathBuilder.append(File.pathSeparator);
                }
                dexPathBuilder.append(dexFile.getAbsolutePath());

            }
            // 创建 opt 目录，存放优化后的 dex 文件
            File optDir = getDir("opt",MODE_PRIVATE);
            // 实例化新的类加载器
            // ClassLoader有很多种 这里使用DexClassLoader因为它不仅可以加载已安装apk的dex文件 还可以加载未安装仁义目录的代码
            DexClassLoader myClassLoader = new DexClassLoader(
                    dexPathBuilder.toString(), // 参数1：真实 dex 文件路径
                    optDir.getAbsolutePath(), // 参数2：优化后的 dex 输出目录
                    null, // 参数3：native 库搜索路径
                    getClassLoader() // 参数4：父类加载器，遵循双亲委派机制
                    );
            // 获取当前系统的 ClassLoader
            ClassLoader sysClassLoader = getClassLoader();
            // 通过反射拿到系统底层的 BaseDexClassLoader 类
            Class<?> baseDexClassLoader = Class.forName("dalvik.system.BaseDexClassLoader");
            // 拿到 BaseDexClassLoader 中的 pathList 字段
            // pathList有两个成员变量
            // dexElements 用来保存 dex 和资源列表 nativeLibraryDirectories 用来保存 native 库列表
            Field pathListField = baseDexClassLoader.getDeclaredField("pathList");
            // 允许访问私有字段
            pathListField.setAccessible(true);

            // 获取系统 ClassLoader 和自定义 ClassLoader 中的 pathList
            Object sysPathList = pathListField.get(sysClassLoader);
            Object myPathList = pathListField.get(myClassLoader);

            // 获取 pathList 对象对应的类
            Class<?> dexPathListClass = sysPathList.getClass();
            // 拿到 DexPathList 里的核心字段 dexElements
            // 这个数组中保存着当前类加载器可识别的所有 dex 文件
            Field dexElementsField = dexPathListClass.getDeclaredField("dexElements");
            // 解除访问限制
            dexElementsField.setAccessible(true);

            // 拿到两个 ClassLoader 对应的 dexElements 数组
            Object sysElements = dexElementsField.get(sysPathList);
            Object myElements = dexElementsField.get(myPathList);

            int sysLen = Array.getLength(sysElements);
            int myLen = Array.getLength(myElements);
            // 创建新数组，长度为两个数组之和
            Object newElements = Array.newInstance(sysElements.getClass().getComponentType(),sysLen + myLen);
            // 合并数组，把真实 dex 放在前面
            // 因为类查找时会按数组顺序从前往后遍历
            for(int i = 0; i < myLen; i++)
            {
                Array.set(newElements,i,Array.get(myElements,i));
            }
            for(int i = 0; i < sysLen; i++)
            {
                Array.set(newElements,i + myLen,Array.get(sysElements,i));
            }
            // 将新数组设置回系统 ClassLoader 的 pathList 中
            dexElementsField.set(sysPathList,newElements);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

## 二代壳

不落地壳，使用InMemoryDexClassLoader加载内存中dex，无需保存到本地

```c
package com.example.myfirstshell;

import android.app.Application;
import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.nio.ByteBuffer;

import dalvik.system.DexClassLoader;
import dalvik.system.InMemoryDexClassLoader;

public class StubApplication extends Application {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try {
            // 在 /data/data/包名/app_payload 下创建私有目录
            File payloadDir = getDir("payload",MODE_PRIVATE);
            // 用来拼接多个解密后 dex 文件的绝对路径
            StringBuilder dexPathBuilder = new StringBuilder();
            // assets 目录下的三个加密 dex 文件
            String[] dexname = {"classes.dex","classes2.dex","classes3.dex"};
            // 与一代将文件保存到本地不同 二代壳在内存中解密并替换
            ByteBuffer[] dexBuffers = new ByteBuffer[dexname.length];
            for(int i = 0; i < dexname.length; i++)
            {
                String name = dexname[i];
                InputStream is = getAssets().open(name);
                ByteArrayOutputStream baos = new ByteArrayOutputStream();
                byte[] buffer = new byte[1024 * 8];
                int len;
                while((len = is.read(buffer)) != -1)
                {
                    for(int j = 0; j < len; j++)
                    {
                        buffer[j] ^= 0x66;
                    }
                    baos.write(buffer,0,len);
                }
                byte[] decBytes = baos.toByteArray();
                dexBuffers[i] = ByteBuffer.wrap(decBytes);
                baos.close();
                is.close();
            }
            // 创新新的ClassLoader
            // InMemoryDexClassLoader可以加载内存中的dex 但是在安卓8.0以后才可以用
            InMemoryDexClassLoader myClassLoader = new InMemoryDexClassLoader(
                    dexBuffers,
                    getClassLoader()
            );
            // 获取当前系统的 ClassLoader
            ClassLoader sysClassLoader = getClassLoader();
            // 通过反射拿到系统底层的 BaseDexClassLoader 类
            Class<?> baseDexClassLoader = Class.forName("dalvik.system.BaseDexClassLoader");
            // 拿到 BaseDexClassLoader 中的 pathList 字段
            // pathList有两个成员变量
            // dexElements 用来保存 dex 和资源列表 nativeLibraryDirectories 用来保存 native 库列表
            Field pathListField = baseDexClassLoader.getDeclaredField("pathList");
            // 允许访问私有字段
            pathListField.setAccessible(true);

            // 获取系统 ClassLoader 和自定义 ClassLoader 中的 pathList
            Object sysPathList = pathListField.get(sysClassLoader);
            Object myPathList = pathListField.get(myClassLoader);

            // 获取 pathList 对象对应的类
            Class<?> dexPathListClass = sysPathList.getClass();
            // 拿到 DexPathList 里的核心字段 dexElements
            // 这个数组中保存着当前类加载器可识别的所有 dex 文件
            Field dexElementsField = dexPathListClass.getDeclaredField("dexElements");
            // 解除访问限制
            dexElementsField.setAccessible(true);

            // 拿到两个 ClassLoader 对应的 dexElements 数组
            Object sysElements = dexElementsField.get(sysPathList);
            Object myElements = dexElementsField.get(myPathList);

            int sysLen = Array.getLength(sysElements);
            int myLen = Array.getLength(myElements);
            // 创建新数组，长度为两个数组之和
            Object newElements = Array.newInstance(sysElements.getClass().getComponentType(),sysLen + myLen);
            // 合并数组，把真实 dex 放在前面
            // 因为类查找时会按数组顺序从前往后遍历
            for(int i = 0; i < myLen; i++)
            {
                Array.set(newElements,i,Array.get(myElements,i));
            }
            for(int i = 0; i < sysLen; i++)
            {
                Array.set(newElements,i + myLen,Array.get(sysElements,i));
            }
            // 将新数组设置回系统 ClassLoader 的 pathList 中
            dexElementsField.set(sysPathList,newElements);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
```

## 三代壳

本壳参考了开源项目[dpt-shell](https://github.com/luoyesiqiu/dpt-shell)，对开源项目的分析可以参考我的[其他文章](https://singlehorn.github.io/2026/05/11/%E5%88%86%E6%9E%90%E5%BC%80%E6%BA%90%E9%A1%B9%E7%9B%AEDPT%E6%8A%BD%E5%8F%96%E5%A3%B3%E6%BA%90%E7%A0%81%E5%AE%9E%E7%8E%B0/)

### 指令抽取

抽取指令就是将method->code_item->insns数组中的指令全部替换为0x00，这样反编译出的方法就为空

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_R8J2U6YH3PU2J2C.png)

将抽取出的指令保存，准备运行时回填

这里我将抽出的指令保存到assets文件夹下，文件格式为：

dex数量（2字节）+ 每个dex偏移（4字节）+ 每个dex的指令结构

每个dex指令结构为：

该dex的方法数（2字节）+ codeItem

codeItem结构由每个函数的指令块组成：

方法id（4字节）+ insn大小（4字节）+ insns（insn大小）

结合代码中的结构体，让ai写了抽空dex和保存该文件结构的代码

```python
import struct
import hashlib
import zlib
import os

# ==========================================
# 1. ULEB128 解码器 (Python版)
# ==========================================
def read_uleb128(data, offset):
    val = 0
    shift = 0
    while True:
        b = data[offset]
        offset += 1
        val |= (b & 0x7f) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return val, offset

# ==========================================
# 2. Dex 指令抽取核心逻辑
# ==========================================
def extract_and_hollow_dex(dex_path):
    with open(dex_path, 'rb') as f:
        dex_bytes = bytearray(f.read()) # 使用 bytearray 以便修改内部指令

    # 读取 Header 中的 class_defs_size 和 class_defs_off
    # 0x60 是 class_defs_size, 0x64 是 class_defs_off
    class_defs_size, class_defs_off = struct.unpack_from('<II', dex_bytes, 0x60)

    extracted_methods = []

    for i in range(class_defs_size):
        # class_def_item 结构大小为 32 字节
        def_off = class_defs_off + i * 32
        class_data_off = struct.unpack_from('<I', dex_bytes, def_off + 24)[0]

        if class_data_off == 0: # 接口类或没有数据的类
            continue

        offset = class_data_off
        static_fields_size, offset = read_uleb128(dex_bytes, offset)
        instance_fields_size, offset = read_uleb128(dex_bytes, offset)
        direct_methods_size, offset = read_uleb128(dex_bytes, offset)
        virtual_methods_size, offset = read_uleb128(dex_bytes, offset)

        # 跳过字段区 (Fields)
        for _ in range(static_fields_size + instance_fields_size):
            _, offset = read_uleb128(dex_bytes, offset) # field_idx_diff
            _, offset = read_uleb128(dex_bytes, offset) # access_flags

        # 内部函数：处理方法区
        def process_methods(count, offset, dex_bytes, extracted_methods):
            method_idx = 0
            for _ in range(count):
                method_idx_diff, offset = read_uleb128(dex_bytes, offset)
                method_idx += method_idx_diff # 计算绝对 method_id

                access_flags, offset = read_uleb128(dex_bytes, offset)
                code_off, offset = read_uleb128(dex_bytes, offset)

                # 如果有代码 (不是 native 或 abstract)
                if code_off != 0:
                    # 1. 跨过 CodeItem 头部，读取指令长度
                    # CodeItem 第 12 字节开始是 insns_size (占 4 字节)
                    # 注意：Dex 里的 insns_size 是按 2 字节(16-bit word)计算的！
                    insns_size_words = struct.unpack_from('<I', dex_bytes, code_off + 12)[0]
                    insns_byte_size = insns_size_words * 2

                    # 2. 指令真实起点的绝对偏移量 (头部固定 16 字节)
                    insns_offset = code_off + 16

                    # 3. 提取真实的虚拟机指令数据
                    insns_data = dex_bytes[insns_offset : insns_offset + insns_byte_size]

                    # 4. 保存到我们自己的结构中
                    extracted_methods.append({
                        'methodId': method_idx,
                        'insnSize': insns_byte_size,
                        'insns': insns_data
                    })

                    # 5. 【极其关键】指令抽空 (Hollowing)
                    # 用 00 (NOP) 覆盖原有的指令，实现防逆向！
                    dex_bytes[insns_offset : insns_offset + insns_byte_size] = b'\x00' * insns_byte_size

            return offset

        # 依次处理直接方法和虚方法
        offset = process_methods(direct_methods_size, offset, dex_bytes, extracted_methods)
        offset = process_methods(virtual_methods_size, offset, dex_bytes, extracted_methods)

    return extracted_methods, dex_bytes

# ==========================================
# 3. 修复 Dex 校验和与签名 (极其重要)
# ==========================================
def fix_dex_header(dex_bytes):
    # 如果不修复，系统一加载就会报 Dex 损坏，根本走不到你的 C++ Hook！

    # 1. 修复 Signature (SHA-1) - 覆盖 12 到 32 字节
    m = hashlib.sha1()
    m.update(dex_bytes[32:])
    dex_bytes[12:32] = m.digest()

    # 2. 修复 Checksum (Adler32) - 覆盖 8 到 12 字节
    checksum = zlib.adler32(dex_bytes[12:]) & 0xffffffff
    dex_bytes[8:12] = struct.pack('<I', checksum)

    return dex_bytes

# ==========================================
# 4. 生成自定义 bin 协议文件
# ==========================================
def build_my_code_item_bin(all_dex_methods, out_bin_path):
    # all_dex_methods 是一个列表的列表，例如: [dex0_methods, dex1_methods]
    dexNum = len(all_dex_methods)

    # 头部长度: 2字节(dexNum) + 4字节 * dexNum
    header_size = 2 + 4 * dexNum
    current_offset = header_size

    offsets = []
    payload = bytearray()

    for methods in all_dex_methods:
        offsets.append(current_offset)

        methodNum = len(methods)
        # 组装当前 Dex 的 Data 区
        dex_data = bytearray(struct.pack('<H', methodNum))
        for m in methods:
            # 写入 methodId(4字节) 和 insnSize(4字节)
            dex_data += struct.pack('<II', m['methodId'], m['insnSize'])
            # 写入真实的指令数据
            dex_data += m['insns']

        payload += dex_data
        current_offset += len(dex_data)

    # 组装最终的文件
    final_file = bytearray(struct.pack('<H', dexNum))
    for off in offsets:
        final_file += struct.pack('<I', off)

    final_file += payload

    # 写入文件
    with open(out_bin_path, 'wb') as f:
        f.write(final_file)
    print(f"[*] 成功生成壳数据文件: {out_bin_path}，包含 {dexNum} 个 Dex 的数据。")

# ==========================================
# 主流程
# ==========================================
if __name__ == '__main__':
    # 假设你有多个 dex，按顺序排列 (classes.dex 索引必须是 0，classes2.dex 索引是 1)
    target_dex_files = ['classes.dex','classes2.dex','classes3.dex']

    all_extracted_methods = []

    for idx, dex_file in enumerate(target_dex_files):
        print(f"[*] 正在分析和抽取: {dex_file}")
        methods, hollowed_dex_bytes = extract_and_hollow_dex(dex_file)
        print(f"    - 共抽取了 {len(methods)} 个方法")

        all_extracted_methods.append(methods)

        # 修复抽空后的 Dex 并写入新文件
        hollowed_dex_bytes = fix_dex_header(hollowed_dex_bytes)
        out_dex_name = f"hollowed_{dex_file}"
        with open(out_dex_name, 'wb') as f:
            f.write(hollowed_dex_bytes)
        print(f"    - 已生成抽空后的壳 Dex: {out_dex_name}")

    # 生成最终的脱壳数据源
    build_my_code_item_bin(all_extracted_methods, 'myCodeItem.bin')
    print("[*] 所有的打包工作已完成！请将 myCodeItem.bin 放入 assets 目录。")
```

### 指令回填

原始activity如下

```java
package com.example.mysourceapp;

import android.os.Bundle;
import android.util.Log;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.d("YvY_shell","this is ture activity");
    }

}
```

创建一个新的项目，包名为`com.example.mysourceapp`，MainActivity只写一个log语句，表明正确执行到此处

现在新建我们的壳项目

ProxyApplication.java

```java
package com.example.myshell;

import android.app.Application;
import android.content.Context;
import android.content.res.AssetManager;
import com.bytedance.android.bytehook.ByteHook;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.lang.reflect.Array;
import java.lang.reflect.Field;
import java.util.Locale;

import dalvik.system.DexClassLoader;

public class ProxyApplication extends Application {

    private static native void initHooks();
    private static native void restoreCodeItem(AssetManager manger,String filename);

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        // 加载so文件
        ByteHook.init(new ByteHook.ConfigBuilder()
                .setMode(ByteHook.Mode.AUTOMATIC)
                .build());
        System.loadLibrary("myshell");
        // 保存code指令
        restoreCodeItem(base.getAssets(),"myCodeItem.bin");
        // hook DefineClass
        initHooks();
        ClassLoader sysClassLoader = base.getClassLoader();
        // 合并dexElements
        combineDexElements(base,sysClassLoader);
    }

    private void combineDexElements(Context base, ClassLoader sysClassLoader) {
        File dexDir = getDir("dex", MODE_PRIVATE);
        File optDir = getDir("opt", MODE_PRIVATE);
        File myHollowedDex = new File(dexDir, "source.zip");

        if (!myHollowedDex.exists()) {
            InputStream is = null;
            FileOutputStream fos = null;
            try {
                is = base.getAssets().open("source.zip");
                fos = new FileOutputStream(myHollowedDex);
                byte[] buffer = new byte[1024 * 4];
                int len;
                while ((len = is.read(buffer)) != -1) {
                    fos.write(buffer, 0, len);
                }
                fos.flush();
            } catch (Exception e) {
                throw new RuntimeException("释放 Dex 失败", e);
            } finally {
                try { if (is != null) is.close(); } catch (Exception ignored) {}
                try { if (fos != null) fos.close(); } catch (Exception ignored) {}
            }
        }

        if (myHollowedDex.canWrite() && !myHollowedDex.setReadOnly()) {
            throw new RuntimeException("Dex 文件设为只读失败");
        }

        try {
            DexClassLoader myClassLoader = new DexClassLoader(
                    myHollowedDex.getAbsolutePath(),
                    optDir.getAbsolutePath(),
                    null,
                    sysClassLoader
            );

            Class<?> baseDexClassLoader = Class.forName("dalvik.system.BaseDexClassLoader");
            Field pathListField = baseDexClassLoader.getDeclaredField("pathList");
            pathListField.setAccessible(true);

            Object sysPathList = pathListField.get(sysClassLoader);
            Object myPathList = pathListField.get(myClassLoader);

            Class<?> dexPathListClass = sysPathList.getClass();
            Field dexElementsField = dexPathListClass.getDeclaredField("dexElements");
            dexElementsField.setAccessible(true);

            Object sysElements = dexElementsField.get(sysPathList);
            Object myElements = dexElementsField.get(myPathList);

            int sysLen = Array.getLength(sysElements);
            int myLen = Array.getLength(myElements);
            Object newElements = Array.newInstance(sysElements.getClass().getComponentType(), sysLen + myLen);

            // 先保留宿主 APK 自己的 dex 顺序，避免 source.zip 中未恢复完整的同名 AndroidX 类优先被加载
            System.arraycopy(sysElements, 0, newElements, 0, sysLen);
            // 将 source.zip 放到后面，只为补充宿主中不存在的业务类
            System.arraycopy(myElements, 0, newElements, sysLen, myLen);

            dexElementsField.set(sysPathList, newElements);

        } catch (Exception e) {
            throw new RuntimeException("合并 dexElements 失败", e);
        }
    }

}
```

代理类没什么主要逻辑，主要逻辑放在native层中

native-lib.cpp

```
#include <jni.h>
#include <string>
#include "DexCode.h"
#include "unordered_map"
#include <android/asset_manager_jni.h>
#include "android/log.h"
#include "bytehook.h"
#include "Dobby/dobby.h"
#include "hook_function.h"

#define DLOGE(...) __android_log_print(ANDROID_LOG_ERROR, "YvYShell", __VA_ARGS__)
#define DLOGD(...) __android_log_print(ANDROID_LOG_DEBUG, "YvYShell", __VA_ARGS__)

std::unordered_map<int, std::unordered_map<uint32_t, CodeItem*>> dexMap;
static bool g_hooks_initialized = false;

extern "C"
JNIEXPORT void JNICALL
Java_com_example_myshell_ProxyApplication_initHooks(JNIEnv *env, jclass clazz) {
    if (g_hooks_initialized) {
        return;
    }
    hook_function();
    g_hooks_initialized = true;
}

extern "C"
JNIEXPORT void JNICALL
Java_com_example_myshell_ProxyApplication_restoreCodeItem(JNIEnv *env, jclass clazz,jobject assetManger,jstring filename) {
    const char *filename_cstr = env->GetStringUTFChars(filename, nullptr);
    AAssetManager *mgr = AAssetManager_fromJava(env,assetManger);
    if(mgr == nullptr)
    {
        DLOGE("获取 AAsetManger 失败");
        env->ReleaseStringUTFChars(filename,filename_cstr);
        return;
    }

    AAsset *asset = AAssetManager_open(mgr,filename_cstr,AASSET_MODE_BUFFER);
    env->ReleaseStringUTFChars(filename,filename_cstr);
    if(asset == nullptr)
    {
        DLOGE("打开文件失败");
        return;
    }

    off_t data_len = AAsset_getLength(asset);
    uint8_t* data = new uint8_t [data_len];
    AAsset_read(asset,data,data_len);
    AAsset_close(asset);
    DexCode::init(data,data_len);
    uint16_t dexNum = DexCode::readDexNum();

    dexMap.reserve(dexNum);
    // 遍历dex数量
    for(int i = 0; i < dexNum; i++)
    {
        uint32_t dexOffset = DexCode::readDexOffset(i);
        uint16_t methodNum = DexCode::readUint16(dexOffset);
        std::unordered_map<uint32_t ,CodeItem*> methodMap;
        methodMap.reserve(methodNum);
        uint32_t codeItemOffset = dexOffset + 2;
        // 遍历dex中的方法数量
        for(int j = 0; j < methodNum; j++)
        {
            CodeItem *codeItem = DexCode::initCodeItem(&codeItemOffset);
            uint32_t methodId = codeItem->getMethodId();
            methodMap[methodId] = codeItem;
        }
        // 保存至dexMap
        dexMap[i]  = methodMap;
    }
    DLOGD("code指令已保存");
}
```

在代码中使用了一些工具类和函数

DexCode.cpp

```
#include <stdint.h>
#include <string.h>
#include "DexCode.h"

// dexNum(2) + dexOffset(4) + [methodNum(2) + codeItem] + [...] + [...] ...
uint8_t* DexCode::my_buffer = nullptr;
size_t DexCode::my_size = 0;

void DexCode::init(uint8_t* buffer,size_t size)
{
    my_buffer = buffer;
    my_size = size;
}

uint16_t DexCode::readDexNum()
{
    uint16_t dexNum = readUint16(0);
    return dexNum;
}

uint32_t DexCode::readDexOffset(int dexIdx)
{
    uint32_t offset = 2 + dexIdx * 4;
    uint32_t dexOffset = readUint32(offset);
    return dexOffset;
}

uint16_t DexCode::readUint16(uint32_t offset)
{
    uint16_t num = 0;
    memcpy(&num,my_buffer + offset,sizeof(uint16_t));
    return num;
}

uint32_t DexCode::readUint32(uint32_t offset)
{
    uint32_t num = 0;
    memcpy(&num,my_buffer + offset,sizeof(uint32_t));
    return num;
}

// methodId(4) + insnSize(4) + insns(insnSize)
CodeItem* DexCode::initCodeItem(uint32_t* offset)
{
    uint32_t methodId = readUint32(*offset);
    uint32_t insnSize = readUint32(*offset + 4);
    auto* insns = my_buffer + (*offset) + 8;
    *offset += insnSize + 8;
    auto* item = new CodeItem(methodId,insnSize,insns);
    return item;
}
```

这里需要和结合刚刚自定义的文件结构理解，代码比较简单

保存code指令以后，什么时候回填呢，为了实现运行时回填的效果，需要hook defineClass函数

hook框架使用了dobby和bytehook

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_7RAVQAR77T3Z34N.png)

dobby框架需要自己编译，bytehook和shadowhook网上可以找到。将他们放到项目中，对应的CMakeList.txt如下

```cmake
include_directories(${CMAKE_SOURCE_DIR}/Dobby)
include_directories(${CMAKE_SOURCE_DIR}/include)
add_library(bytehook SHARED IMPORTED)
set_target_properties(bytehook PROPERTIES IMPORTED_LOCATION
        ${CMAKE_SOURCE_DIR}/../jniLibs/${ANDROID_ABI}/libbytehook.so)
add_library(dobby STATIC IMPORTED)
set_target_properties(dobby PROPERTIES IMPORTED_LOCATION
        ${CMAKE_SOURCE_DIR}/Dobby/libdobby.a)
target_link_libraries(${CMAKE_PROJECT_NAME}
        # List libraries link to the target library
        android
        dobby
        bytehook
        log)
```

如果编译报错可以让ai改改

hook_function.cpp

```
#include <string.h>
#include <cstdint>
#include <dlfcn.h>
#include <link.h>
#include <elf.h>
#include <iostream>
#include <unordered_map>
#include <map>
#include <vector>
#include <unistd.h>

#include "hook_function.h"
#include "android/log.h"
#include "Dobby/dobby.h"
#include "dexFile.h"
#include "CodeItem.h"
#include "bytehook.h"
#include "sys/mman.h"

#if defined(__LP64__)
#define LIB_DIR "lib64"
#else
#define LIB_DIR "lib"
#endif

#define DLOGE(...) __android_log_print(ANDROID_LOG_ERROR, "YvYShell", __VA_ARGS__)
#define DLOGD(...) __android_log_print(ANDROID_LOG_DEBUG, "YvYShell", __VA_ARGS__)

extern std::unordered_map<int, std::unordered_map<uint32_t, CodeItem*>> dexMap;
typedef void* (*mmap_func_t)(void*, size_t, int, int, int, off_t);

bool hook_defineClass();
void hook_execve();
void hook_mmap();

static uint32_t gnu_hash(const char *s) {
    uint32_t h = 5381;
    for (unsigned char c = static_cast<unsigned char>(*s); c != 0; c = static_cast<unsigned char>(*++s)) {
        h = (h << 5) + h + c;
    }
    return h;
}

struct SymbolResolveContext {
    const char *soname;
    const char *symbol;
    void *address;
    bool matchedLibrary;
};

static int resolve_symbol_from_loaded_so(struct dl_phdr_info *info, size_t size, void *data) {
    auto *ctx = reinterpret_cast<SymbolResolveContext *>(data);
    if (info == nullptr || info->dlpi_name == nullptr || strstr(info->dlpi_name, ctx->soname) == nullptr) {
        return 0;
    }
    ctx->matchedLibrary = true;

    const ElfW(Phdr) *dynamic_phdr = nullptr;
    for (ElfW(Half) i = 0; i < info->dlpi_phnum; ++i) {
        if (info->dlpi_phdr[i].p_type == PT_DYNAMIC) {
            dynamic_phdr = &info->dlpi_phdr[i];
            break;
        }
    }
    if (dynamic_phdr == nullptr) {
        DLOGE("PT_DYNAMIC not found. soname=%s", info->dlpi_name);
        return 0;
    }

    const ElfW(Dyn) *dyn = reinterpret_cast<const ElfW(Dyn) *>(info->dlpi_addr + dynamic_phdr->p_vaddr);
    const ElfW(Sym) *symtab = nullptr;
    const char *strtab = nullptr;
    const uint32_t *hash = nullptr;
    const uint32_t *gnuHash = nullptr;
    size_t syment = sizeof(ElfW(Sym));

    for (const ElfW(Dyn) *entry = dyn; entry->d_tag != DT_NULL; ++entry) {
        switch (entry->d_tag) {
            case DT_SYMTAB:
                symtab = reinterpret_cast<const ElfW(Sym) *>(info->dlpi_addr + entry->d_un.d_ptr);
                break;
            case DT_STRTAB:
                strtab = reinterpret_cast<const char *>(info->dlpi_addr + entry->d_un.d_ptr);
                break;
            case DT_HASH:
                hash = reinterpret_cast<const uint32_t *>(info->dlpi_addr + entry->d_un.d_ptr);
                break;
            case DT_GNU_HASH:
                gnuHash = reinterpret_cast<const uint32_t *>(info->dlpi_addr + entry->d_un.d_ptr);
                break;
            case DT_SYMENT:
                syment = entry->d_un.d_val;
                break;
            default:
                break;
        }
    }

    if (symtab == nullptr || strtab == nullptr || syment != sizeof(ElfW(Sym))) {
        return 0;
    }

    if (hash != nullptr) {
        uint32_t nchain = hash[1];
        for (uint32_t i = 0; i < nchain; ++i) {
            const ElfW(Sym) *sym = reinterpret_cast<const ElfW(Sym) *>(reinterpret_cast<const char *>(symtab) + i * syment);
            const char *name = strtab + sym->st_name;
            if (strcmp(name, ctx->symbol) == 0) {
                ctx->address = reinterpret_cast<void *>(info->dlpi_addr + sym->st_value);
                return 1;
            }
        }
    }

    if (gnuHash != nullptr) {
        uint32_t nbuckets = gnuHash[0];
        uint32_t symoffset = gnuHash[1];
        uint32_t bloom_size = gnuHash[2];
        const ElfW(Addr) *bloom = reinterpret_cast<const ElfW(Addr) *>(gnuHash + 4);
        const uint32_t *buckets = reinterpret_cast<const uint32_t *>(bloom + bloom_size);
        const uint32_t *chain = buckets + nbuckets;
        uint32_t hashValue = gnu_hash(ctx->symbol);
        uint32_t bucket = buckets[hashValue % nbuckets];
        if (bucket >= symoffset) {
            for (uint32_t i = bucket;; ++i) {
                uint32_t chainValue = chain[i - symoffset];
                if ((chainValue | 1U) == (hashValue | 1U)) {
                    const ElfW(Sym) *sym = reinterpret_cast<const ElfW(Sym) *>(reinterpret_cast<const char *>(symtab) + i * syment);
                    const char *name = strtab + sym->st_name;
                    if (strcmp(name, ctx->symbol) == 0) {
                        ctx->address = reinterpret_cast<void *>(info->dlpi_addr + sym->st_value);
                        return 1;
                    }
                }
                if ((chainValue & 1U) != 0) {
                    break;
                }
            }
        }
    }

    //DLOGE("symbol not found in loaded so. soname=%s symbol=%s", info->dlpi_name, ctx->symbol);

    return 0;
}

void* fakeDefineClass(void* thiz, void* self,
                      const char* descriptor,
                      size_t hash,
                      void* class_loader,
                      const void* dex_file,
                      const void* dex_class_def);

void patchClass(const char *descriptor, const void *dex_file, const void *dex_class_def);
void patchMethod(uint8_t *begin, const char *location, uint64_t dexSize, int dexIndex, uint32_t method_idx, uint32_t code_off);

void hook_function() {
    hook_execve();
    hook_mmap();
    bool hook_res = hook_defineClass();
    if (!hook_res) {
        DLOGE("hook defineClass failed");
        return;
    }
    DLOGD("hook defineClass success");
}

void* fake_mmap(void* addr, size_t size, int prot, int flags, int fd, off_t offset) {
    BYTEHOOK_STACK_SCOPE();
    int new_prot = prot | PROT_WRITE;
    return BYTEHOOK_CALL_PREV(fake_mmap, addr, size, new_prot, flags, fd, offset);
}

// hook mmap是为了修改权限 使dex变为可写
void hook_mmap() {
    bytehook_stub_t stub = bytehook_hook_single("/apex/com.android.art/" LIB_DIR "/libart.so",
                                                "libc.so",
                                                "mmap",
                                                (void *)fake_mmap,
                                                nullptr,
                                                nullptr);
    if (stub != nullptr) {
        DLOGD("hook mmap success");
    } else {
        DLOGE("hook mmap failed");
    }
}

int fake_execve(const char *pathname, char *const argv[], char *const envp[]) {
    BYTEHOOK_STACK_SCOPE();
    if (pathname != nullptr && strstr(pathname, "dex2oat") != nullptr) {
        DLOGD("blocked dex2oat: %s", pathname);
        return -1;
    }
    return BYTEHOOK_CALL_PREV(fake_execve, pathname, argv, envp);
}

// 拦截dex2oat 强制系统走解释执行
void hook_execve() {
    bytehook_stub_t stub = bytehook_hook_single("/apex/com.android.art/" LIB_DIR "/libart.so",
                                                "libc.so",
                                                "execve",
                                                (void *)fake_execve,
                                                nullptr,
                                                nullptr);
    if (stub != nullptr) {
        DLOGD("hook execve success");
    } else {
        DLOGE("hook execve failed");
    }
}

// hook defineClass函数 对dex中的类、方法进行指令回填
bool hook_defineClass() {
    const char *sym = "_ZN3art11ClassLinker11DefineClassEPNS_6ThreadEPKcmNS_6HandleINS_6mirror11ClassLoaderEEERKNS_7DexFileERKNS_3dex8ClassDefE";

    void *defineClassAddress = dlsym(RTLD_DEFAULT, sym);
    if (defineClassAddress != nullptr) {
        DLOGD("defineClassAddress 获取成功");
    } else {
        DLOGD("defineClassAddress 获取失败");
    }
    if (defineClassAddress == nullptr) {
        SymbolResolveContext ctx = {"libart.so", sym, nullptr, false};
        dl_iterate_phdr(resolve_symbol_from_loaded_so, &ctx);
        defineClassAddress = ctx.address;
        if (!ctx.matchedLibrary) {
            DLOGE("dl_iterate_phdr did not match any loaded libart.so");
        }
    }
    if (defineClassAddress == nullptr) {
        DLOGE("resolve DefineClass failed. symbol=%s", sym);
        return false;
    }

    int hookRes = DobbyHook(defineClassAddress, (void *)fakeDefineClass, (void **)&origDefineClass);
    if (hookRes != 0) {
        DLOGE("DobbyHook DefineClass failed: %d", hookRes);
        return false;
    }
    return true;
}

void* fakeDefineClass(void* thiz, void* self,
                      const char* descriptor,
                      size_t hash,
                      void* class_loader,
                      const void* dex_file,
                      const void* dex_class_def) {
    if (origDefineClass != nullptr) {
        patchClass(descriptor, dex_file, dex_class_def);
        void* result = origDefineClass(thiz, self, descriptor, hash, class_loader, dex_file, dex_class_def);
        return result;
    }
    return nullptr;
}

// 回填class
void patchClass(const char *descriptor, const void *dex_file, const void *dex_class_def) {
    if (dex_file != nullptr) {
        // 编写一个标准dexFile类
        auto* dexFile = (dex::dexFile*)dex_file;
        std::string location = dexFile->location;
        // 只回填 source.zip 中的抽壳业务类，避免误改宿主 base.apk 里的 AndroidX/系统类
        if (location.find("source.zip") == std::string::npos) {
            //DLOGD("不为source.zip中业务类");
            return;
        }
        uint8_t* begin = (uint8_t*)dexFile->begin;
        uint64_t dexSize = dexFile->header->file_size;
        auto* class_def = (dex::classDef*)dex_class_def;
        int dexIndex = 0;
        std::string locStr(location);
        size_t pos = locStr.find("classes");
        if (pos != std::string::npos) {
            size_t dotPos = locStr.find(".dex", pos);
            if (dotPos != std::string::npos && dotPos > pos + 7) {
                std::string numStr = locStr.substr(pos + 7, dotPos - (pos + 7));
                dexIndex = std::stoi(numStr) - 1;
            }
        }
        // 因为使用了变长编码 所以要对实际使用的字节做解析
        if (class_def->class_data_off != 0) {
            size_t num = 0;
            auto* class_data = (uint8_t*)((uint8_t*)begin + class_def->class_data_off);
            uint64_t static_fields_size = 0;
            num += DexFile::readUleb128((class_data + num), &static_fields_size);
            uint64_t instance_fields_size = 0;
            num += DexFile::readUleb128((class_data + num), &instance_fields_size);
            uint64_t direct_methods_size = 0;
            num += DexFile::readUleb128((class_data + num), &direct_methods_size);
            uint64_t virtual_methods_size = 0;
            num += DexFile::readUleb128((class_data + num), &virtual_methods_size);
            num += DexFile::getFieldSize((class_data + num), static_fields_size);
            num += DexFile::getFieldSize((class_data + num), instance_fields_size);

            // 重点为class_def的直接方法和虚方法 获取它们
            auto* directMethods = new dex::Method[direct_methods_size];
            num += DexFile::readMethod((class_data + num), directMethods, direct_methods_size);
            auto* virtualMethods = new dex::Method[virtual_methods_size];
            num += DexFile::readMethod((class_data + num), virtualMethods, virtual_methods_size);

            // 循环 对刚刚的方法回填指令
            for (uint64_t i = 0; i < direct_methods_size; i++) {
                auto method = directMethods[i];
                patchMethod(begin, location.c_str(), dexSize, dexIndex, method.method_idx_diff, method.code_off);
            }
            for (uint64_t i = 0; i < virtual_methods_size; i++) {
                auto method = virtualMethods[i];
                patchMethod(begin, location.c_str(), dexSize, dexIndex, method.method_idx_diff, method.code_off);
            }
            delete[] virtualMethods;
            delete[] directMethods;
        }
    }
}

// 将之前保存的指令回填到方法中
void patchMethod(uint8_t *begin, const char *location, uint64_t dexSize, int dexIndex, uint32_t method_idx, uint32_t code_off) {
    if (code_off == 0) {
        return;
    }

    if (dexMap.find(dexIndex) == dexMap.end()) {
        return;
    }

    auto &methodMap = dexMap[dexIndex];
    auto it = methodMap.find(method_idx);
    if (it == methodMap.end()) {
        return;
    }

    CodeItem* item = it->second;
    if (item == nullptr) {
        return;
    }

    uint8_t* realCodeItemAddr = begin + code_off;
    uint8_t* realInsnsAddr = realCodeItemAddr + 16;
    // 目标 dex 页默认只读，写回指令前先临时打开写权限，避免 SEGV_ACCERR
    size_t pageSize = static_cast<size_t>(sysconf(_SC_PAGESIZE));
    uintptr_t pageStart = reinterpret_cast<uintptr_t>(realInsnsAddr) & ~(pageSize - 1);
    uintptr_t pageEnd = (reinterpret_cast<uintptr_t>(realInsnsAddr) + item->getInsnsSize() + pageSize - 1) & ~(pageSize - 1);
    size_t pageLen = pageEnd - pageStart;
    if (mprotect(reinterpret_cast<void *>(pageStart), pageLen, PROT_READ | PROT_WRITE) != 0) {
        DLOGE("patchMethod mprotect rw failed. dexIndex=%d methodId=%u addr=%p len=%zu", dexIndex, method_idx, realInsnsAddr, pageLen);
        return;
    }
    memcpy(realInsnsAddr, item->getInsns(), item->getInsnsSize());
    // 写回后恢复只读，减少对 ART 后续行为的影响
    if (mprotect(reinterpret_cast<void *>(pageStart), pageLen, PROT_READ) != 0) {
        DLOGE("patchMethod mprotect ro failed. dexIndex=%d methodId=%u addr=%p len=%zu", dexIndex, method_idx, realInsnsAddr, pageLen);
    }
}
```

这是我们最核心最关键的地方，将保存的指令还原。因为需要解析dexFile，找到关键的struct class_def_item_list dex_class_defs，struct class_data_item class_data等，所以还是要单独写工具类

dexFile.h

```
#include <iostream>
#include <stdint.h>
#ifndef MYSHELL_DEXFILE_H
#define MYSHELL_DEXFILE_H

namespace dex
{
    struct Header{
        uint8_t magic[8];
        uint32_t checksum;
        uint8_t signature[20];
        uint32_t file_size;
        uint32_t header_size;
        uint32_t endian_tag;
        uint32_t link_size;
        uint32_t link_off;
        uint32_t map_off;
        uint32_t string_ids_size;
        uint32_t string_ids_off;
        uint32_t type_ids_size;
        uint32_t type_ids_off;
        uint32_t proto_ids_size;
        uint32_t proto_ids_off;
        uint32_t field_ids_size;
        uint32_t field_ids_off;
        uint32_t method_ids_size;
        uint32_t method_ida_off;
        uint32_t class_defs_size;
        uint32_t class_defs_off;
        uint32_t data_size;
        uint32_t data_off;
    };

    struct StringId{
        uint32_t string_data_off;
    };

    struct TypeId{
        uint32_t descriptor_idx;
    };

    struct FieldId{
        uint16_t class_idx;
        uint16_t type_idx;
        uint16_t name_idx;
    };

    struct MethodId{
        uint16_t class_idx;
        uint16_t proto_idx;
        uint32_t name_idx;
    };

    struct ProtoId{
        uint32_t shorty_idx;
        uint16_t return_type_idx;
        uint16_t pad;
        uint32_t parameters_off;
    };

    struct Method{
    public:
        uint32_t method_idx_diff;
        uint32_t access_flags;
        uint32_t code_off;
        Method(uint32_t method_idx_diff,uint32_t access_flags,uint32_t code_off):method_idx_diff(method_idx_diff),access_flags(access_flags),code_off(code_off){};
        Method():method_idx_diff(0),access_flags(0),code_off(0){};
    };

    struct Field{
        uint32_t field_idx_diff;
        uint32_t access_flags;
        Field(uint32_t field_idx_diff,uint32_t access_flags):field_idx_diff(field_idx_diff),access_flags(access_flags){};
        Field():field_idx_diff(0),access_flags(0){};
    };

    struct classDef{
    public:
        uint32_t class_idx;
        uint32_t access_flags;
        uint32_t superclass_idx;
        uint32_t interfaces_off;
        uint32_t source_file_idx;
        uint32_t annotations_off;
        uint32_t class_data_off;
        uint32_t static_values_off;
    };

    struct dexFile{
        void *vtable;
        const uint8_t *const begin;
        const size_t size;
        const uint8_t *const data_begin;
        const size_t data_size;
        const std::string location;
        const uint32_t location_checksum;
        const dex::Header* const header;
        std::unique_ptr<void*> mem_map;
        const dex::StringId* const string_ids;
        const dex::TypeId* const type_ids;
        const dex::FieldId* const field_ids;
        const dex::MethodId* const method_ids;
        const dex::ProtoId* const proto_ids;
        const dex::classDef* const class_defs;
    };
}

class DexFile{
public:
    static size_t readUleb128(uint8_t const *const data, uint64_t* const val);
    static size_t readFields(uint8_t* data,dex::Field* field,uint64_t count);
    static size_t readMethod(uint8_t* data,dex::Method* method,uint64_t count);
    static size_t getFieldSize(uint8_t* data,uint64_t count);
};

#endif //MYSHELL_DEXFILE_H
```

这涉及到dex文件结构，如果对dex文件结构不熟悉也可以打开010使用dex模板

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_23D743MKVTHGXC8.png)

保存指令->还原指令->合并dexElements，主要就是这三步，经测试，在Android13上可以正常运行

![image](https://bbs.kanxue.com/upload/attach/202605/1008445_BCP6WG83MQUPBCY.png)

## 最后

安卓蒟蒻一枚~，出于对安卓壳学习的目的，尝试自己写了落地壳不落地壳和抽取壳，如果文中有不对的地方，还请各位大佬指出

---

# 回复

## 回复 by 菜鸟9527 (#2)

*2026-5-11 22:05*

向大佬学习

## 回复 by Liv_T (#3)

*2026-5-16 12:04*

学习学习
