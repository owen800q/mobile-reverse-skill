---
title: '[原创] 淺談Cocos2djs逆向'
url: https://bbs.kanxue.com/thread-283299.htm
tid: 283299
author: ngiokweng
date: '2024-09-05'
tags: [Android安全, 原创, 基础理论, 逆向分析, 其他]
crawled_at: '2026-07-31T14:20:51+08:00'
replies: 58
---

## 前言

簡單聊一下cocos2djs手遊的逆向，有任何相關想法歡迎和我討論^^

## 一些概念

列出一些個人認為比較有用的概念：

- Cocos遊戲的兩大開發工具分別是`CocosCreator`和`CocosStudio`，區別是前者是cocos2djs專用的開發工具，後者則是cocos2d-lua、cocos2d-cpp那些。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_K3NQFC6REHUET33.webp)

- 使用`Cocos Creator 2`開發的手遊，生成的關鍵so默認名稱是`libcocos2djs.so`
- 使用`Cocos Creator 3`開發的手遊，生成的關鍵so默認名稱是`libcocos.so` ( 入口函數非`applicationDidFinishLaunching` )
- Cocos Creator在構建時可以選擇是否對`.js`腳本進行加密&壓縮，而加密算法固定是`xxtea`，還可以選擇是否使用Zip壓縮

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_MRGS5M4K93GX3WM.webp)

- `libcocos2djs.so`裡的`AppDelegate::applicationDidFinishLaunching`是入口函數，可以從這裡開始進行分析
- Cocos2djs是Cocos2d-x的一個分支，因此[https://github.com/cocos2d/cocos2d-x源碼同樣適用於Cocos2djs](https://github.com/cocos2d/cocos2d-x%E6%BA%90%E7%A2%BC%E5%90%8C%E6%A8%A3%E9%81%A9%E7%94%A8%E6%96%BCCocos2djs)

## 自己寫一個Demo

自己寫一個Demo來分析的好處是能夠快速地判斷某個錯誤是由於被檢測到？還是本來就會如此？

### 版本信息

嘗試過2.4.2、2.4.6兩個版本，都構建失敗，最終成功的版本信息如下：

- 編輯器版本：`Creator 2.4.13` ( 2系列裡的最高版本，低版本在AS編譯時會報一堆錯誤 )
- ndk版本：`23.1.7779620`
- `project/build.gradle`：`classpath 'com.android.tools.build:gradle:8.0.2'`
- `project/gradle/gradle-wrapper.properties`：`distributionUrl=https\://services.gradle.org/distributions/gradle-8.0.2-all.zip`

### Cocos Creator基礎用法

由於本人不懂cocos遊戲開發，只好直接用官方的Hello World模板。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_NDNDJYH7DJM4689.webp)

首先要設置SDK和NDK路徑

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_BFWBHHPQ4S4HFDY.webp)

然後構建的參數設置如下，主要需要設置以下兩點：

- 加密腳本：全都勾上，密鑰用默認的
- Source Map：保留符號，這樣IDA在打開時才能看到函數名

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_QRFVCM7ZTJ7K33K.webp)

我使用Cocos Creator能順利構建，但無法編譯，只好改用Android Studio來編譯。

使用Android Studio打開`build\jsb-link\frameworks\runtime-src\proj.android-studio`，然後就可以按正常AS流程進行編譯

Demo如下所示，在中心輸出了`Hello, World!`。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_88ZTD32TDCYBZMU.webp)

## jsc腳本解密

上述Demo構建中有一個選項是【加密腳本】，它會將js腳本通過xxtea算法加密成`.jsc`。

而遊戲的一些功能就會通過js腳本來實現，因此cocos2djs逆向首要事件就是將`.jsc`解密，通常`.jsc`會存放在apk內的`assets`目錄下

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_TD96UHCGK98YEEH.webp)

### 獲取解密key

方法一：從`applicationDidFinishLaunching`入手

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_6WP6MHN6MQB34B2.webp)

方法二：HOOK

1. hook `set_xxtea_key`

```
// soName: libcocos2djs.so
function hook_jsb_set_xxtea_key(soName) {
    let set_xxtea_key = Module.findExportByName(soName, "_Z17jsb_set_xxtea_keyRKNSt6__ndk112basic_stringIcNS_11char_traitsIcEENS_9allocatorIcEEEE");
    Interceptor.attach(set_xxtea_key,{
        onEnter(args){
            console.log("xxtea key: ", args[0].readCString())
        },
        onLeave(retval){

        }
    })
}
```

1. hook `xxtea_decrypt`

```
function hook_xxtea_decrypt(soName) {
    let set_xxtea_key = Module.findExportByName(soName, "xxtea_decrypt");
    Interceptor.attach(set_xxtea_key,{
        onEnter(args){
            console.log("xxtea key: ", args[2].readCString())
        },
        onLeave(retval){

        }
    })
}
```

### python加解密腳本

一次性解密`output_dir`目錄下所有`.jsc`，並在`input_dir`生成與`output_dir`同樣的目錄結構。

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455565758596061626364656667686970717273747576777879 | `# pip install xxtea-py``# pip install jsbeautifier` `import` `xxtea``import` `gzip``import` `jsbeautifier``import` `os` `KEY` `=` `"abdbe980-786e-45"` `input_dir` `=` `r``"cocos2djs_demo\assets"` `# abs path` `output_dir` `=` `r``"cocos2djs_demo\output"` `# abs path` `def` `jscDecrypt(data: bytes, needJsBeautifier` `=` `True``):``dec` `=` `xxtea.decrypt(data, KEY)``jscode` `=` `gzip.decompress(dec).decode()` `if` `needJsBeautifier:``return` `jsbeautifier.beautify(jscode)``else``:``return` `jscode` `def` `jscEncrypt(data):``compress_data` `=` `gzip.compress(data.encode())``enc` `=` `xxtea.encrypt(compress_data, KEY)``return` `enc` `def` `decryptAll():``for` `root, dirs, files` `in` `os.walk(input_dir):` `# 創建與input_dir一致的結構``for` `dir` `in` `dirs:``dir_path` `=` `os.path.join(root,` `dir``)``target_dir` `=` `output_dir` `+` `dir_path.replace(input_dir, "")``if` `not` `os.path.exists(target_dir):``os.mkdir(target_dir)` `for` `file` `in` `files:``file_path` `=` `os.path.join(root,` `file``)` `if` `not` `file``.endswith(``".jsc"``):``continue` `with` `open``(file_path, mode` `=` `"rb"``) as f:``enc_jsc` `=` `f.read()` `dec_jscode` `=` `jscDecrypt(enc_jsc)` `output_file_path` `=` `output_dir` `+` `file_path.replace(input_dir, "``").replace("``.jsc``", "``") + "``.js"` `print``(output_file_path)``with` `open``(output_file_path, mode` `=` `"w"``, encoding` `=` `"utf-8"``) as f:``f.write(dec_jscode)` `def` `decryptOne(path):``with` `open``(path, mode` `=` `"rb"``) as f:``enc_jsc` `=` `f.read()` `dec_jscode` `=` `jscDecrypt(enc_jsc,` `False``)` `output_path` `=` `path.split(``".jsc"``)[``0``]` `+` `".js"` `with` `open``(output_path, mode` `=` `"w"``, encoding` `=` `"utf-8"``) as f:``f.write(dec_jscode)` `def` `encryptOne(path):``with` `open``(path, mode` `=` `"r"``, encoding` `=` `"utf-8"``) as f:``jscode` `=` `f.read()` `enc_data` `=` `jscEncrypt(jscode)` `output_path` `=` `path.split(``".js"``)[``0``]` `+` `".jsc"` `with` `open``(output_path, mode` `=` `"wb"``) as f:``f.write(enc_data)` `if` `__name__` `=``=` `"__main__"``:``decryptAll()` |
|-|-|

## `jsc`文件的2種讀取方式

為實現對遊戲正常功能的干涉，顯然需要修改遊戲執行的js腳本。而替換`.jsc`文件是其中一種思路，前提是要找到讀取`.jsc`文件的地方。

### 方式一：從apk裡讀取

我自己編譯的Demo就是以這種方式讀取`/data/app/XXX/base.apk`裡`assets`目錄內的`.jsc`文件。

cocos引擎默認使用xxtea算法來對`.jsc`等腳本進行加密，因此讀取`.jsc`的操作定然在`xxtea_decrypt`之前。

跟[cocos2d-x源碼](https://github.com/cocos2d/cocos2d-x/blob/76903dee64046c7bfdba50790be283484b4be271/cocos/scripting/lua-bindings/manual/CCLuaStack.cpp#L782)，找使用`xxtea_decrypt`的地方，可以定位到`LuaStack::luaLoadChunksFromZIP`

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_D56DGTMMQHPVNMT.webp)

向上跟會發現它的bytes數據是由`getDataFromFile`函數獲取

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_5HUNC7BU5232XJY.webp)

繼續跟`getDataFromFile`的邏輯，它會調用`getContents`，而`getContents`裡是調用`fopen`來打開，但奇怪的是hook `fopen`卻沒有發現它有打開任何`.jsc`文件

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_JAZ4QFQEZ79VFW6.webp)

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_7KUFT82MNF3P4YY.webp)

後來發現調用的並非`FileUtils::getContents`，而是`FileUtilsAndroid::getContents`。

它其中一個分支是調用`libandroid.so`的`AAsset_read`來讀取`.jsc`數據，調用`AAssetManager_open`來打開`.jsc`文件。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_FGE9ZD7GHYW98EK.webp)

繼續對`AAssetManager_open`進行深入分析( [在線源碼](http://xrefandroid.com/android-8.1.0_r81/xref/frameworks/base/native/android/asset_manager.cpp?r=&amp;mo=2286&amp;fi=87#87) )，目的是找到能夠IO重定向的點：

`AAssetManager_open`裡調用了`AssetManager::open`函數

| 123456789101112131415161718192021222324252627282930 | `// frameworks/base/native/android/asset_manager.cpp``AAsset* AAssetManager_open(AAssetManager* amgr,` `const` `char``* filename,` `int` `mode)``{``Asset::AccessMode amMode;``switch` `(mode) {``case` `AASSET_MODE_UNKNOWN:``amMode = Asset::ACCESS_UNKNOWN;``break``;``case` `AASSET_MODE_RANDOM:``amMode = Asset::ACCESS_RANDOM;``break``;``case` `AASSET_MODE_STREAMING:``amMode = Asset::ACCESS_STREAMING;``break``;``case` `AASSET_MODE_BUFFER:``amMode = Asset::ACCESS_BUFFER;``break``;``default``:``return` `NULL;``}` `AssetManager* mgr =` `static_cast``<AssetManager*>(amgr);``// here``Asset* asset = mgr->open(filename, amMode);``if` `(asset == NULL) {``return` `NULL;``}` `return` `new` `AAsset(asset);``}` |
|-|-|

`AssetManager::open`調用`openNonAssetInPathLocked`

| 12345678910111213141516171819202122 | `// frameworks/base/libs/androidfw/AssetManager.cpp``Asset* AssetManager::open(``const` `char``* fileName, AccessMode mode)``{``AutoMutex _l(mLock);``LOG_FATAL_IF(mAssetPaths.size() == 0,` `"No assets added to AssetManager"``);``String8 assetName(kAssetsRoot);``assetName.appendPath(fileName);` `size_t` `i = mAssetPaths.size();``while` `(i > 0) {``i--;``ALOGV(``"Looking for asset '%s' in '%s'\n"``,``assetName.string(), mAssetPaths.itemAt(i).path.string());``// here``Asset* pAsset = openNonAssetInPathLocked(assetName.string(), mode, mAssetPaths.itemAt(i));``if` `(pAsset != NULL) {``return` `pAsset != kExcludedAsset ? pAsset : NULL;``}``}` `return` `NULL;``}` |
|-|-|

`AssetManager::openNonAssetInPathLocked`先判斷`assets`是位於`.gz`還是`.zip`內，而`.apk`與`.zip`基本等價，因此理應會走else分支。

| 1 | `奇怪的是當我使用frida hook驗證時，能順利hook到`openAssetFromZipLocked`，卻hook不到`getZipFileLocked`，顯然是不合理的。` |
|-|-|

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647 | `// frameworks/base/libs/androidfw/AssetManager.cpp``Asset* AssetManager::openNonAssetInPathLocked(``const` `char``* fileName, AccessMode mode,``const` `asset_path& ap)``{``Asset* pAsset = NULL;` `if` `(ap.type == kFileTypeDirectory) {``String8 path(ap.path);``path.appendPath(fileName);` `pAsset = openAssetFromFileLocked(path, mode);` `if` `(pAsset == NULL) {``/* try again, this time with ".gz" */``path.append(``".gz"``);``pAsset = openAssetFromFileLocked(path, mode);``}` `if` `(pAsset != NULL) {``//printf("FOUND NA '%s' on disk\n", fileName);``pAsset->setAssetSource(path);``}` `// run this branch``}` `else` `{``String8 path(fileName);``// here``ZipFileRO* pZip = getZipFileLocked(ap);``if` `(pZip != NULL) {` `ZipEntryRO entry = pZip->findEntryByName(path.string());``if` `(entry != NULL) {` `pAsset = openAssetFromZipLocked(pZip, entry, mode, path);``pZip->releaseEntry(entry);``}``}` `if` `(pAsset != NULL) {``pAsset->setAssetSource(``createZipSourceNameLocked(ZipSet::getPathName(ap.path.string()), String8(``""``),``String8(fileName)));``}``}` `return` `pAsset;``}` |
|-|-|

嘗試繼續跟剛剛hook失敗的`AssetManager::getZipFileLocked`，它調用的是`AssetManager::ZipSet::getZip`。

| 1 | `同樣用frida hook `getZip`，這次成功了，猜測是一些優化移除了`getZipFileLocked`而導致hook 失敗。` |
|-|-|

| 1234567 | `// frameworks/base/libs/androidfw/AssetManager.cpp``ZipFileRO* AssetManager::getZipFileLocked(``const` `asset_path& ap)``{``ALOGV(``"getZipFileLocked() in %p\n"``,` `this``);` `return` `mZipSet.getZip(ap.path);``}` |
|-|-|

`ZipSet::getZip`會調用`SharedZip::getZip`，後者直接返回`mZipFile`。

| 12345678910111213141516 | `// frameworks/base/libs/androidfw/AssetManager.cpp``ZipFileRO* AssetManager::ZipSet::getZip(``const` `String8& path)``{``int` `idx = getIndex(path);``sp<SharedZip> zip = mZipFile[idx];``if` `(zip == NULL) {``zip = SharedZip::get(path);``mZipFile.editItemAt(idx) = zip;``}``return` `zip->getZip();``}` `ZipFileRO* AssetManager::SharedZip::getZip()``{``return` `mZipFile;``}` |
|-|-|

尋找`mZipFile`賦值的地方，最終會找到是由`ZipFileRO::open(mPath.string())`賦值。

| 123456789101112131415 | `// frameworks/base/libs/androidfw/AssetManager.cpp``AssetManager::SharedZip::SharedZip(``const` `String8& path,` `time_t` `modWhen)``: mPath(path), mZipFile(NULL), mModWhen(modWhen),``mResourceTableAsset(NULL), mResourceTable(NULL)``{``if` `(kIsDebug) {``ALOGI(``"Creating SharedZip %p %s\n"``,` `this``, (``const` `char``*)mPath);``}``ALOGV(``"+++ opening zip '%s'\n"``, mPath.string());``// here``mZipFile = ZipFileRO::open(mPath.string());``if` `(mZipFile == NULL) {``ALOGD(``"failed to open Zip archive '%s'\n"``, mPath.string());``}``}` |
|-|-|

| 1 | `從`frameworks``/``base``/``libs``/``androidfw``/``Android.bp`可知上述代碼的lib文件是`libandroidfw.so`，位於```/``system``/``lib64``/```下。將其pull到本地然後用IDA打開，就能根據IDA所示的函數導出名稱``/``地址對這些函數進行hook。` |
|-|-|

### 方式二：從應用的數據目錄裡讀取

無論是方式一還是方式二，`.jsc`數據都是通過`getDataFromFile`獲取。而`getDataFromFile`裡調用了`getContents`。

| 1 | `getDataFromFile -> getContents` |
|-|-|

在方式一中，我一開始看的是`FileUtils::getContents`，但其實是`FileUtilsAndroid::getContents`才對。

只有當`fullPath[0] == '/'`時才會調用`FileUtils::getContents`，而`FileUtils::getContents`會調用`fopen`來打開`.jsc`

| 123456789101112131415 | `// https://github.com/cocos2d/cocos2d-x/blob/76903dee64046c7bfdba50790be283484b4be271/cocos/platform/android/CCFileUtils-android.cpp``FileUtils::Status FileUtilsAndroid::getContents(``const` `std::string& filename, ResizableBuffer* buffer)` `const``{``static` `const` `std::string apkprefix(``"assets/"``);``if` `(filename.empty())``return` `FileUtils::Status::NotExists;` `string fullPath = fullPathForFilename(filename);` `if` `(fullPath[0] ==` `'/'``)``// here``return` `FileUtils::getContents(fullPath, buffer);` `// 方式一會走這裡....``}` |
|-|-|

## 替換思路

正常來說有以下幾種替換腳本的思路：

1. 找到讀取`.jsc`文件的地方進行IO重定向。
2. 直接進行字節替換，即替換`xxtea_decypt`解密前的`.jsc`字節數據，或者替換`xxtea_decypt`解密後的明文`.js`腳本。

 這裡的替換是指開闢一片新內存，將新的數據放到這片內存，然後替換指針的指向。
3. 直接替換apk裡的`.jsc`，然後重打包apk。
4. 替換js明文，不是像`2`那樣開闢一片新內存，而是直接修改原本內存的明文js數據。

經測試後發現只有`1`、`3`、`4`是可行的，`2`會導致APP卡死( 原因不明？？？ )。

### 思路一實現

從上述可知第一種`.jsc`讀取方式會先調用`ZipFileRO::open(mPath.string())`來打開apk，之後再通過`AAssetManager_open`來獲取`.jsc`。

hook `ZipFileRO::open`看看傳入的參數是什麼。

```
function hook_ZipFile_open(flag) {
    let ZipFile_open = Module.getExportByName("libandroidfw.so", "_ZN7android9ZipFileRO4openEPKc");
    console.log("ZipFile_open: ", ZipFile_open)
    return Interceptor.attach(ZipFile_open,
        {
            onEnter: function (args) {
                console.log("arg0: ", args[0].readCString());
            },
            onLeave: function (retval) {

            }
        }
    );
}
```

可以看到其中一條是當前APK的路徑，顯然`assets`也是從這裡取的，因此這裡是一個可以嘗試重定向點，先需構造一個`fake.apk` push 到`/data/app/XXX/`下，然後hook IO重定向到`fake.apk`實現替換。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_Y5RDEYHURGYHDGF.webp)

對我自己編譯的Demo而言，無論是以apktool解包&重打包的方式，還是直接解壓縮&重壓縮&手動命名的方式來構建`fake.apk`都是可行的，**但要記得賦予`fake.apk`最低`644`的權限。**

以下是我使用上述方法在我的Demo中實踐的效果，成功修改中心的字符串。

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_MMC9945TCA2N3MM.webp)

但感覺這種方式的實用性較低( 什至不如直接重打包… )

### 思路二嘗試(失敗)

連這樣僅替換指針指向都會導致APP卡死？？

```
function hook_xxtea_decrypt() {
    Interceptor.attach(Module.findExportByName("libcocos2djs.so", "xxtea_decrypt"), {
        onEnter(args) {
            let jsc_data = args[0];
            let size = args[1].toInt32();
            let key = args[2].readCString();
            let key_len = args[3].toInt32();
            this.arg4 = args[4];

            let target_list = [0x15, 0x43, 0x73];
            let flag = true;
            for (let i = 0; i < target_list.length; i++) {
                if (target_list[i] != Memory.readU8(jsc_data.add(i))) {
                    flag = false;
                }
            }
            this.flag = flag;
            if (flag) {
                let new_size = size;
                let newAddress = Memory.alloc(new_size);
                Memory.protect(newAddress, new_size, "rwx")
                Memory.protect(args[0], new_size, "rwx")
                Memory.writeByteArray(newAddress, jsc_data.readByteArray(new_size))
                args[0] = newAddress;
            }

        },
        onLeave(retval) {
        }
    })

}
```

### 思路四實現

參考[這位大佬的文章](https://blog.shi1011.cn/rev/android/1422)可知cocos2djs內置的v8引擎最終通過`evalString`來執行`.jsc`解密後的js代碼。

在正式替換前，最好先通過hook `evalString`的方式保存一份目標js( 因為遊戲的熱更新策略等原因，可能導致`evalString`執行的js代碼與你從apk裡手動解密`.jsc`得到的js腳本有所不同 )。

```
function saveJscode(jscode, path) {
    var fopenPtr = Module.findExportByName("libc.so", "fopen");
    var fopen = new NativeFunction(fopenPtr, 'pointer', ['pointer', 'pointer']);
    var fclosePtr = Module.findExportByName("libc.so", "fclose");
    var fclose = new NativeFunction(fclosePtr, 'int', ['pointer']);
    var fseekPtr = Module.findExportByName("libc.so", "fseek");
    var fseek = new NativeFunction(fseekPtr, 'int', ['pointer', 'int', 'int']);
    var ftellPtr = Module.findExportByName("libc.so", "ftell");
    var ftell = new NativeFunction(ftellPtr, 'int', ['pointer']);
    var freadPtr = Module.findExportByName("libc.so", "fread");
    var fread = new NativeFunction(freadPtr, 'int', ['pointer', 'int', 'int', 'pointer']);
    var fwritePtr = Module.findExportByName("libc.so", "fwrite");
    var fwrite = new NativeFunction(fwritePtr, 'int', ['pointer', 'int', 'int', 'pointer']);

    let newPath = Memory.allocUtf8String(path);

    let openMode = Memory.allocUtf8String('w');

    let str = Memory.allocUtf8String(jscode);

    let file = fopen(newPath, openMode);
    if (file != null) {
        fwrite(str, jscode.length, 1, file)
        fclose(file);

    }
    return null;
}

function hook_evalString() {
    Interceptor.attach(Module.findExportByName("libcocos2djs.so", "_ZN2se12ScriptEngine10evalStringEPKclPNS_5ValueES2_"), {
        onEnter(args) {
            let path = args[4].readCString();
            path = path == null ? "" : path;
            let jscode = args[1];
            let size = args[2].toInt32();
            if (path.indexOf("assets/script/index.jsc") != -1) {
                saveJscode(jscode.readCString(), "/data/data/XXXXXXX/test.js");
            }
        }
    })
}
```

利用`Memory.scan`來找到修改的位置

```
function findReplaceAddr(startAddr, size, pattern) {
    Memory.scan(startAddr, size, pattern, {
        onMatch(address, size) {
            console.log("target offset: ", ptr(address - startAddr))
            return 'stop';
        },
        onComplete() {
            console.log('Memory.scan() complete');
        }
    });
}

function hook_evalString() {
    Interceptor.attach(Module.findExportByName("libcocos2djs.so", "_ZN2se12ScriptEngine10evalStringEPKclPNS_5ValueES2_"), {
        onEnter(args) {
            let path = args[4].readCString();
            path = path == null ? "" : path;
            let jscode = args[1];
            let size = args[2].toInt32();
            if (path.indexOf("assets/script/index.jsc") != -1) {
                let pattern = "76 61 72 20 65 20 3D 20 64 2E 50 6C 61 79 65 72 41 74 74 72 69 62 75 74 65 43 6F 6E 66 69 67 2E 67 65 74 44 72 65 61 6D 48 6C 70 65 49 74 65 6D 44 72 6F 70 28 29 2C";
                findReplaceAddr(jscode, size, pattern);
            }
        }
    })
}
```

最後以`Memory.writeU8`來逐字節修改，不用`Memory.writeUtf8String`的原因是它默認會在最終添加`'\0'`而導致報錯。

```
function replaceEvalString(jscode, offset, replaceStr) {
    for (let i = 0; i < replaceStr.length; i++) {
        Memory.writeU8(jscode.add(offset + i), replaceStr.charCodeAt(i))
    }
}

// 例:
function cheatAutoChopTree(jscode) {
    let replaceStr = 'true || "                                 "';
    replaceEvalString(jscode, 0x3861f6, replaceStr)
}
```

## 某砍樹手遊實踐

以某款砍樹遊戲來進行簡單的實踐。

遊戲有自動砍樹的功能，但需要符合一定條件

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_ES6S6JXU6F49CYT.webp)

如何找到對應的邏輯在哪個`.jsc`中？直接搜字符串就可以。

利用上述替換思路4來修改對應的js判斷邏輯，最終效果：

 ![image](https://bbs.kanxue.com/upload/attach/202409/946537_UQX3R2EPVDQWWRQ.webp)

## 結語

思路4那種替換手段有大小限制，不能隨意地修改，暫時還未找到能隨意修改的手段，有知道的大佬還請不嗇賜教，有任何想法也歡迎交流^^

## 後記

在評論區的一位大佬指點下，終於是找到一種更優的替換方案，相比起思路4來說要方便太多了。
最開始時我其實也嘗試過這種直接的js明文替換，但APP會卡死/閃退，現在才發現是frida的api所致，那時在開辟內存空間時使用了Memory.alloc、Memory.allocUtf8String，改成使用libc.so的malloc就不會閃退了，具體為什麼會這樣我也不清楚，看看以後有沒有機會研究下frida的源碼吧^^

---

# 回复

## 回复 by 万里星河 (#2)

*2024-9-6 00:40*

感谢分享 学习了

## 回复 by mb_eunzmkbp (#3)

*2024-9-11 22:25*

我用脚本hook evalstring没有反应，就attach上了然后就一直没反应了，是什么原因

## 回复 by ngiokweng (#4)

*2024-9-12 09:10*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  我用脚本hook evalstring没有反应，就attach上了然后就一直没反应了，是什么原因
>
>

哪個APP

## 回复 by mb_eunzmkbp (#5)

*2024-9-12 17:48*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  哪個APP
>
>

就是文章最后提到的砍树手游

## 回复 by ngiokweng (#6)

*2024-9-12 20:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  就是文章最后提到的砍树手游
>
>

可能是版本不一樣, 我測試用的是台版的

## 回复 by mb_eunzmkbp (#7)

*2024-9-13 12:26*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  可能是版本不一樣, 我測試用的是台版的
>
>

好的感谢

## 回复 by 樊辉 (#8)

*2024-9-19 12:36*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  哪個APP
>
>

寻道大千吧

## 回复 by 樊辉 (#9)

*2024-9-19 12:53*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  哪個APP
>
>

。。。

## 回复 by ngiokweng (#10)

*2024-9-19 21:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  樊辉](https://bbs.kanxue.com/user-301778.htm)
>
>
>
>
>
>
>
>  ngiokweng
>
>
>
>  哪個APP
>
>  。。。
>
>

是大小沒錯，至於替換的方式有很多種，能成功都好說

## 回复 by 樊辉 (#11)

*2024-9-20 14:38*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  是大小沒錯，至於替換的方式有很多種，能成功都好說
>
>

上面我发的代码能成功，你可以试试

## 回复 by ngiokweng (#12)

*2024-9-20 18:25*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  樊辉](https://bbs.kanxue.com/user-301778.htm)
>
>  上面我发的代码能成功，你可以试试
>
>

成功是指hook evalString嗎？這個我也可以，我失敗的那種情況是我想直接替換.jsc，但會閃退

## 回复 by 樊辉 (#13)

*2024-9-20 18:33*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  成功是指hook evalString嗎？這個我也可以，我失敗的那種情況是我想直接替換.jsc，但會閃退
>
>

```
。。。
```

## 回复 by ngiokweng (#14)

*2024-9-20 19:06*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  樊辉](https://bbs.kanxue.com/user-301778.htm)
>
>
>
>
>
>
>
>  ngiokweng
>
>
>
>  成功是指hook evalString嗎？這個我也可以，我失敗的那種情況是我想直接替換.jsc，但會閃退
>
>  。 ...
>
>

感謝分享, 我有空試試。還想請問下有沒有直接替換密文.jsc的方法？

## 回复 by 樊辉 (#15)

*2024-9-22 07:43*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  感謝分享, 我有空試試。還想請問下有沒有直接替換密文.jsc的方法？
>
>

我没试过直接替换密文，应该得往前翻源码了。

## 回复 by 纯废物 (#16)

*2024-9-24 23:15*

如果是用Java开发的要怎么弄

## 回复 by ngiokweng (#17)

*2024-9-25 10:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_rdqahqsz](https://bbs.kanxue.com/user-983635.htm)
>
>  如果是用Java开发的要怎么弄
>
>

沒看懂你的意思

## 回复 by 2666fff (#18)

*2024-10-9 22:49*

3.x试过没有 方法三的. 另外查key的so代码跟2.x有区别没

## 回复 by ngiokweng (#19)

*2024-10-10 09:35*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  2666fff](https://bbs.kanxue.com/user-906723.htm)
>
>  3.x试过没有 方法三的. 另外查key的so代码跟2.x有区别没
>
>

有樣本嗎, 我沒遇過3.x的

## 回复 by mb_eunzmkbp (#20)

*2024-10-10 14:31*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  有樣本嗎, 我沒遇過3.x的
>
>

libcocos.so的对吧，我不知道能不能直接发游戏名字，密钥倒是能直接找到就是hook不出来，不知道啥原因

## 回复 by ngiokweng (#21)

*2024-10-10 15:21*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  libcocos.so的对吧，我不知道能不能直接发游戏名字，密钥倒是能直接找到就是hook不出来，不知道啥原因
>
>

你把APP名字base64編碼下再發出來就好了

## 回复 by mb_eunzmkbp (#22)

*2024-10-10 16:29*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  你把APP名字base64編碼下再發出來就好了
>
>

taptap上下载的，56WW5a6X5qih5ouf5Zmo77ya5Lyg5om/

## 回复 by ngiokweng (#23)

*2024-10-10 22:56*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  taptap上下载的，56WW5a6X5qih5ouf5Zmo77ya5Lyg5om/
>
>

你這個樣本不是3.X吧, 我說的3.X是指Cocos Creator的版本, 生成的so名字也不叫libcocos2djs.so

## 回复 by 2666fff (#24)

*2024-10-10 23:54*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  有樣本嗎, 我沒遇過3.x的
>
>

编了一个3.8.2 的小游戏,. 最新版本是.3 应该差别不大, 我看了下so大概都被混淆了. 下面是base64编码下载地址.
6ZO+5o6lOiBodHRwczovL3Bhbi5iYWlkdS5jb20vcy8xMXEzNDZHa21ONGVXYVpTQUgtNWJ6UT9wd2Q9bXBnMiDmj5Dlj5bnoIE6IG1wZzIg5aSN5Yi26L+Z5q615YaF5a655ZCO5omT5byA55m+5bqm572R55uY5omL5py6QXBw77yM5pON5L2c5pu05pa55L6/5ZOmIAotLeadpeiHqueZvuW6pue9keebmOi2hee6p+S8muWRmHY555qE5YiG5Lqr

## 回复 by mb_eunzmkbp (#25)

*2024-10-11 01:27*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>
>
>
>
>
>
>  mb_eunzmkbp
>
>
>
>  taptap上下载的，56WW5a6X5qih5ouf5Zmo77ya5Lyg5om/
>
>  你這個樣本不是3 ...
>
>

是的呀,zuzong模拟器:传承，是libcocos.so，不是libcocos2djs

## 回复 by ngiokweng (#26)

*2024-10-11 10:00*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  是的呀,zuzong模拟器:传承，是libcocos.so，不是libcocos2djs
>
>

確實是3.X的, 我之前下載的是它的一代... key的話hook xxtea_decrypt就能得到了

## 回复 by ngiokweng (#27)

*2024-10-11 10:45*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  2666fff](https://bbs.kanxue.com/user-906723.htm)
>
>  编了一个3.8.2 的小游戏,. 最新版本是.3 应该差别不大, 我看了下so大概都被混淆了. 下面是base64编码下载地址.
> 6ZO+5o6lOiBodHRwczovL3Bhbi5iYWlkdS ...
>
>

so沒有被混淆, 只是符號被去掉而已, 找到對應的地址就能正常hook

## 回复 by mb_eunzmkbp (#28)

*2024-10-11 23:31*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  確實是3.X的, 我之前下載的是它的一代... key的話hook xxtea_decrypt就能得到了
>
>

![image](https://bbs.kanxue.com/upload/attach/202410/1005791_7NPHX9QRY3PZCYD.webp)

![image](https://bbs.kanxue.com/upload/attach/202410/1005791_4VY3NJEM6UTQ68A.webp)我这有什么问题吗，为什么连开始了都没有

## 回复 by ngiokweng (#29)

*2024-10-12 00:02*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  我这有什么问题吗，为什么连开始了都没有
>
>

不應該啊, 是不是你的調用時機有問題

## 回复 by mb_eunzmkbp (#30)

*2024-10-12 11:16*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  不應該啊, 是不是你的調用時機有問題
>
>

有讲究吗，我是打开游戏然后frida -U -l

## 回复 by ngiokweng (#31)

*2024-10-12 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  有讲究吗，我是打开游戏然后frida -U -l
>
>

當然有, 你這樣相當於是在xxtea_decrypt調用後才去hook, 顯然就晚了。要用spawn模式, 而且hook_xxtea_decrypt要等對應so加載後才執行。

## 回复 by mb_eunzmkbp (#32)

*2024-10-12 11:42*

我试过spawn，但是我的手机没办法用spawn模式来启动，搜了看他们教的，我试了还是不行一直报错Failed to spawn: unexpectedly timed out while waiting for signal from process with PID

## 回复 by ngiokweng (#33)

*2024-10-12 13:12*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_eunzmkbp](https://bbs.kanxue.com/user-1005791.htm)
>
>  我试过spawn，但是我的手机没办法用spawn模式来启动，搜了看他们教的，我试了还是不行一直报错Failed to spawn: unexpectedly timed out while waiti ...
>
>

可能是frida版本不對應, 又或者是你操作上的問題, 我也不好說, 善用Google。

## 回复 by mb_eunzmkbp (#34)

*2024-10-13 00:49*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  可能是frida版本不對應, 又或者是你操作上的問題, 我也不好說, 善用Google。
>
>

解决了，感谢![image](https://bbs.kanxue.com/view/img/face/67.gif)![image](https://bbs.kanxue.com/view/img/face/67.gif)![image](https://bbs.kanxue.com/view/img/face/67.gif)

## 回复 by ngiokweng (#36)

*2024-10-26 11:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_xxgqhqjz](https://bbs.kanxue.com/user-1010971.htm)
>
>  有没有联系方式加我q1848775629 js游戏有偿
>
>

加你了

## 回复 by koflfy (#37)

*2024-10-27 11:42*

mark

## 回复 by mb_fcujxnot (#39)

*2024-12-30 16:46*

砍树游戏，按教程从so里提取了key，但用jdc解密工具1.44无法解密jsc文件，请指教。

## 回复 by ngiokweng (#40)

*2024-12-30 21:33*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_fcujxnot](https://bbs.kanxue.com/user-1019995.htm)
>
>  砍树游戏，按教程从so里提取了key，但用jdc解密工具1.44无法解密jsc文件，请指教。
>
>

so裡寫死的key通常不太可靠, 可以嘗試hook相關函數打印key

## 回复 by a894985459 (#41)

*2025-1-8 12:01*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  so裡寫死的key通常不太可靠, 可以嘗試hook相關函數打印key
>
>

請問大佬可以協助提取key 然後解密pkm嗎？
可以的話聯繫我Q3697624914

## 回复 by mb_covdmskb (#42)

*2025-2-25 16:31*

想通过C编译Hook函数实现

## 回复 by Our_OT (#43)

*2025-2-25 16:46*

大佬，libhellolua.so也是cocos嘛

## 回复 by 陈可牛 (#44)

*2025-2-25 17:13*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_covdmskb](https://bbs.kanxue.com/user-1014811.htm)
>
>  想通过C编译Hook函数实现
>
>

什么游戏可以发我看一下![image](https://bbs.kanxue.com/view/img/face/071.gif)

## 回复 by mb_covdmskb (#45)

*2025-2-25 17:23*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  什么游戏可以发我看一下[em_071]
>
>

通用的，想试下hook游戏调用index.jsc的函数来实现，方便加下吗企鹅MTA5MDYxNDk3NA==
游戏是6Iux6ZuE5rKh5pyJ6Zeq

## 回复 by 陈可牛 (#46)

*2025-2-25 17:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_covdmskb](https://bbs.kanxue.com/user-1014811.htm)
>
>  通用的，想试下hook游戏调用index.jsc的函数来实现，方便加下吗企鹅MTA5MDYxNDk3NA==
> 游戏是6Iux6ZuE5rKh5pyJ6Zeq
>
>

一样，我试了两款都没啥问题。等有空我看一下

## 回复 by mb_covdmskb (#47)

*2025-2-25 17:31*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  一样，我试了两款都没啥问题。等有空我看一下
>
>

应该都是一个aasset_read的函数，只是不会写开辟内存改指针![image](https://bbs.kanxue.com/view/img/face/055.gif)，方便的话交流下![image](https://bbs.kanxue.com/view/img/face/088.gif)

## 回复 by 陈可牛 (#48)

*2025-2-25 19:52*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_covdmskb](https://bbs.kanxue.com/user-1014811.htm)
>
>  应该都是一个aasset_read的函数，只是不会写开辟内存改指针[em_055]，方便的话交流下[em_088]
>
>

跟之前的那个帖子一样的了，直接拿代码过来改改就好了。
https://www.bilibili.com/video/BV1vaPee9EsP/

## 回复 by ngiokweng (#49)

*2025-2-25 19:58*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  跟之前的那个帖子一样的了，直接拿代码过来改改就好了。
> https://www.bilibili.com/video/BV1vaPee9EsP/
>
>

可牛佬牛逼![image](https://bbs.kanxue.com/view/img/face/056.gif)

## 回复 by ngiokweng (#50)

*2025-2-25 20:04*

交流可以加我vx: ngiokweng

## 回复 by 陈可牛 (#51)

*2025-2-25 20:13*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>  交流可以加我vx:&nbsp;ngiokweng
>

佬有研究虚幻吗？![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_covdmskb (#52)

*2025-2-25 20:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  跟之前的那个帖子一样的了，直接拿代码过来改改就好了。
> https://www.bilibili.com/video/BV1vaPee9EsP/
>
>

密钥是明文这个我知道，主要想写成mod hook![image](https://bbs.kanxue.com/view/img/face/055.gif)

## 回复 by 陈可牛 (#53)

*2025-2-25 20:19*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_covdmskb](https://bbs.kanxue.com/user-1014811.htm)
>
>  密钥是明文这个我知道，主要想写成mod hook[em_055]
>
>

你看看下面的连接服务器那提示，这个是修改文本。上面的tips 是注入脚本。还有一些hook的输出在logcat没截图![image](https://bbs.kanxue.com/view/img/face/020.gif)

## 回复 by mb_covdmskb (#54)

*2025-2-25 20:24*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>
>
>
>
>
>
>  mb_covdmskb
>
>
>
>  密钥是明文这个我知道，主要想写成mod hook[em_055]
>
>  你看看下面的连接服务器那提示，这个是修 ...
>
>

frida吗？还是c实现的呀，我是想直接替换游戏主体jsc

## 回复 by 陈可牛 (#55)

*2025-2-25 20:29*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  mb_covdmskb](https://bbs.kanxue.com/user-1014811.htm)
>
>  frida吗？还是c实现的呀，我是想直接替换游戏主体jsc
>
>

这两个实现没有区别的吧？

## 回复 by ngiokweng (#56)

*2025-2-25 20:38*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  佬有研究虚幻吗？[em_065]
>
>

有研究過, 但沒太深入, 佬帶帶![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by 陈可牛 (#57)

*2025-2-25 20:42*

>
> [ngiokweng](https://bbs.kanxue.com/user-946537.htm)
>
>  有研究過, 但沒太深入, 佬帶帶[em_065]
>
>

刚找了demo，佬有兴趣玩玩吗？虚幻我一款都没弄过，正在瞎弄，佬带我![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by ngiokweng (#58)

*2025-2-25 20:46*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  刚找了demo，佬有兴趣玩玩吗？虚幻我一款都没弄过，正在瞎弄，佬带我[em_065]
>
>

好啊, 佬加我vx, 私聊看看![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_covdmskb (#59)

*2025-2-25 20:53*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  这两个实现没有区别的吧？
>
>

还是有的，tb上看到一个内置mod可以直接替换，研究了好久没搞出来

## 回复 by AiGame (#60)

*2025-6-19 00:30*

谢谢大佬的帖子受益匪浅!

## 回复 by 复读基 (#61)

*2025-10-28 18:16*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  陈可牛](https://bbs.kanxue.com/user-794149.htm)
>
>  跟之前的那个帖子一样的了，直接拿代码过来改改就好了。
> https://www.bilibili.com/video/BV1vaPee9EsP/
>
>

佬，码在哪啊没找见![image](https://bbs.kanxue.com/view/img/face/071.gif)
