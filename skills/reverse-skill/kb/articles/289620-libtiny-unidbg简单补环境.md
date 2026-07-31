---
title: '[原创] libtiny unidbg简单补环境'
url: https://bbs.kanxue.com/thread-289620.htm
tid: 289620
author: Tubbs
date: '2025-12-30'
tags: [Android安全, 原创, 其他]
crawled_at: '2026-07-31T15:16:51+08:00'
replies: 131
---

模拟执行`libtiny.so`计算`x-mini`相关的参数。

## 准备

1. 下载unidbg-0.9.8源码。
2. xhs app版本 8590914。
3. frida hook结果。前几次是初始化相关的，在hook计算相关参数前的全当成初始化调用。

## unidbg

先搭建基础框架, 代码如下：

| 123456789101112131415161718192021222324252627282930313233343536 | `public` `class` `Xhs859Tiny` `extends` `AbstractJni {``private` `final` `AndroidEmulator emulator;``private` `final` `VM vm;``private` `final` `Module module;` `private` `final` `DvmClass tinyT;` `Xhs859Tiny() {``// 创建模拟器``emulator = AndroidEmulatorBuilder.for64Bit()``.setProcessName(``"com.xingin.xhs"``)``.addBackendFactory(``new` `Unicorn2Factory(``true``))``.build();` `final` `Memory memory = emulator.getMemory();` `// 模拟器的内存操作接口``memory.setLibraryResolver(``new` `AndroidResolver(``23``));` `// 设置系统类库解析` `vm = emulator.createDalvikVM(``new` `File(``"data/xhs8_59_0.apk"``));` `// 创建安卓虚拟机``vm.setVerbose(``true``);` `// 设置是否打印Jni调用细节``vm.setJni(``this``);` `new` `MediaNdkModule(emulator, vm).register(memory);``new` `AndroidModule(emulator, vm).register(memory);``new` `JniGraphics(emulator, vm).register(memory);` `DalvikModule dm = vm.loadLibrary(``"tiny"``,` `true``);``module = dm.getModule();` `// 加载好的libttEncrypt.so对应为一个模块``dm.callJNI_OnLoad(emulator);``tinyT = vm.resolveClass(``"com/xingin/tiny/internal/t"``);``}` `public` `static` `void` `main(String[] args) {``Xhs859Tiny demo =` `new` `Xhs859Tiny();` `}``}` |
|-|-|

运行结果：

![image](https://bbs.kanxue.com/upload/attach/202603/951135_UHM4H9QRZ2YCBMB.png)

### 初始化调用

按照hook顺序调用初始化函数，

| 12345678 | `public` `void` `callInit() {``String method =` `"a(I[Ljava/lang/Object;)Ljava/lang/Object;"``;``int` `i =` `1853701372``;``ArrayObject objArr =` `new` `ArrayObject();``// 返回结果应该是null``DvmObject result = tinyT.callStaticJniMethodObject(emulator, method, i, objArr);``System.out.println(result);``}` |
|-|-|

运行需要补充的环境：

![image](https://bbs.kanxue.com/upload/attach/202603/951135_BNNG925HQ2U8A37.png)

这是主要需要补充的函数之一，也是开始比较重要的点, 先简单补充如下，通过第一个参数int来写分支补充不同的功能。

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `// 补环境``@Override``public` `DvmObject<?> callStaticObjectMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch` `(signature) {``case` `"com/xingin/tiny/internal/t->b(I[Ljava/lang/Object;)Ljava/lang/Object;"``: {``int` `i = vaList.getIntArg(``0``);``System.out.println(``"Tiny.t.b i="` `+ i);``switch` `(i) {``case` `-``1939572706``: {``ArrayObject arrayObject = vaList.getObjectArg(``1``);``DvmClass clazz = (DvmClass) arrayObject.getValue()[``0``];``String methodName = (String) arrayObject.getValue()[``1``].getValue();``DvmObject[] signatureArgs = (DvmObject[]) arrayObject.getValue()[``2``].getValue();``System.out.println(signatureArgs);` `StringBuilder methodSignature =` `new` `StringBuilder(``"("``);``for` `(DvmObject signatureArg : signatureArgs) {``if` `(signatureArg.getValue().getClass() == String.``class``) {``System.out.println(signatureArg.getValue().getClass().getName());``methodSignature.append(``"L"``)``.append(signatureArg.getValue().getClass().getName().replaceAll(``"\\."``,` `"/"``))``.append(``";"``);``}` `else` `{``methodSignature.append(signatureArg.getValue().getClass().getName());``}``}``methodSignature.append(``")Ljava/lang/Object;"``);``System.out.println(methodName +` `" "` `+ methodSignature);``DvmMethod dvmMethod =` `new` `DvmMethod(clazz, methodName, methodSignature.toString(),` `true``);``DvmObject result = vm.resolveClass(``"java/lang/reflect/Method"``).newObject(dvmMethod);``clazz.setMethodId(result.hashCode(), dvmMethod);` `System.out.println(``"setMethodId "` `+ Integer.toHexString(result.hashCode()));``return` `result;``}``}``}``}``return` `super``.callStaticObjectMethodV(vm, dvmClass, signature, vaList);``}` |
|-|-|

这样补充，有报错，需要把`DvmMethod`类的构造函数权限改成`public`, 接着给`DvmClass`函数中增加一个`setMethodId`的函数，

| 12345678 | `public` `void` `setMethodID(``int` `methodID, DvmMethod dvmMethod) {``if` `(!staticMethodMap.containsKey(methodID)) {``staticMethodMap.put(methodID, dvmMethod);``}``if` `(!methodMap.containsKey(methodID)) {``methodMap.put(methodID, dvmMethod);``}``}` |
|-|-|

仿造`DvmClass`中getMethodID相关的函数，简单粗暴的给添加到对应的map中。

![image](https://bbs.kanxue.com/upload/attach/202603/951135_YVDYV2QGUYKB3CV.png)

补充之后报错如上所示

![image](https://bbs.kanxue.com/upload/attach/202603/951135_G2X9C75E4MJ8RFX.png)

进入第一层报错信息，代码如上所示，这里没有实现，直接抛出异常，接下来尝试补全这里的实现，

![image](https://bbs.kanxue.com/upload/attach/202603/951135_J2PEHW9CXNYZ4RQ.png)

大致仿造函数`_ToReflectedMethod`函数的实现和需要补充的函数，猜测这里可能需要从`DvmMethod`对象获取到`MethodID`long类型。所以补充如下：

| 123456789 | `Pointer _FromReflectedMethod = svcMemory.registerSvc(``new` `Arm64Svc() {``@Override``public` `long` `handle(Emulator<?> emulator) {``RegisterContext context = emulator.getContext();``UnidbgPointer jmethodID = context.getPointerArg(``1``);``return` `jmethodID.toIntPeer();``//                throw new UnsupportedOperationException();``}``});` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/951135_SFXQK59X3XSEGFY.png)

补充之后运行结果如上，第一个初始化函数成功执行完成。

继续第二个初始化函数

| 1234567891011121314151617181920 | `public` `void` `callInit2() {``String method =` `"a(I[Ljava/lang/Object;)Ljava/lang/Object;"``;``int` `i = -``1681571521``;``ArrayObject objArr =` `new` `ArrayObject(``new` `StringObject(vm,` `"ECFAAF01"``),``new` `StringObject(vm,` `"vivo"``),``DvmInteger.valueOf(vm,` `0``),``DvmBoolean.valueOf(vm,` `true``),``DvmBoolean.valueOf(vm,` `false``),``DvmBoolean.valueOf(vm,` `false``),``vm.resolveClass(``"java/lang/Float"``).newObject(``1.0``),``DvmBoolean.valueOf(vm,` `false``),``DvmBoolean.valueOf(vm,` `false``),``DvmBoolean.valueOf(vm,` `false``),``DvmBoolean.valueOf(vm,` `false``),``DvmBoolean.valueOf(vm,` `false``)``);``DvmObject result = tinyT.callStaticJniMethodObject(emulator, method, i, objArr);``System.out.println(result);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_FBN29GES4U9TFDM.png)

开补：

| 123456789 | `@Override``public` `float` `callFloatMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"java/lang/Float->floatValue()F"``:{``return` `((Double) dvmObject.getValue()).floatValue();``}``}``return` `super``.callFloatMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_V769D7MVPQSMEGR.png)

补

| 123456789 | `@Override``public` `boolean` `callBooleanMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"java/lang/Boolean->booleanValue()Z"``: {``return` `(``boolean``) dvmObject.getValue();``}``}``return` `super``.callBooleanMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_C96QPBKEA4CPAUK.png)

补

| 123 | `case` `1004337890``: {``return` `new` `StringObject(vm,` `"/data/user/0/com.xingin.xhs"``);``}` |
|-|-|

![image](https://bbs.kanxue.com/upload/attach/202603/951135_Z6XPRPY77DMCK86.png)

第二个初始化函数执行完成。

第三个初始化函数

| 12345678 | `public` `void` `callInit3() {``String method =` `"a(I[Ljava/lang/Object;)Ljava/lang/Object;"``;``int` `i =` `830009223``;``ArrayObject objArr =` `new` `ArrayObject();``DvmObject result = tinyT.callStaticJniMethodObject(emulator, method, i, objArr);``System.out.println(result);` `}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_A4JBJPS4R9AM5X8.png)

不用补，直接能执行。

### 计算调用

初始化函数调用完成之后，正式进入参数计算相关的调用。

| 12345678910111213 | `public` `void` `callX() {``//        emulator.traceCode();``String method =` `"a(I[Ljava/lang/Object;)Ljava/lang/Object;"``;``int` `i =` `828356434``;``ArrayObject objArr =` `new` `ArrayObject(``new` `StringObject(vm,` `"GET"``),``new` `StringObject(vm,` `"https://www.xiaohongshu.com/api/sns/v3/system_service/flag_exp?fetchSceneTag="``),``new` `ByteArray(vm,` `new` `byte``[``0``])``);``DvmObject result = tinyT.callStaticJniMethodObject(emulator, method, i, objArr);``HashMap<String, String> map = (HashMap<String, String>) result.getValue();``System.out.println(map);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_YXUTFMY5BFDBHFH.png)

补

| 123 | `case` `-``364968294``: {``return` `vm.resolveClass(``"android/content/Context"``).newObject(vm);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_2NKRR6RYU2TVDQB.png)

补

| 123 | `case` `1678768061``: {``return` `vm.resolveClass(``"android/content/pm/PackageInfo"``).newObject(vm);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_3VM8DEPMUG4ZU3F.png)

补, `DvmField`类构造函数权限public

| 123456789101112 | `case` `1375189957``: {``ArrayObject arrayObject = vaList.getObjectArg(``1``);` `DvmClass clazz = (DvmClass) arrayObject.getValue()[``0``];``String fieldName = (String) arrayObject.getValue()[``1``].getValue();``System.out.println(``"fieldName "` `+ fieldName);``if` `(fieldName.equals(``"CREATOR"``)) {``return` `null``;``}``DvmField dvmField =` `new` `DvmField(clazz, fieldName,` `"Ljava/lang/Object;"``,` `true``);``return` `vm.resolveClass(``"java/lang/reflect/Field"``).newObject(dvmField);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_H268EMYRNBUQB5D.png)

补

| 123456789 | `@Override``public` `DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch` `(signature) {``case` `"android/content/pm/PackageInfo->packageName:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"com.xingin.xhs"``);``}``}``return` `super``.getObjectField(vm, dvmObject, signature);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_8RE4EV3ZP4QTAC9.png)

补

| 123 | `case` `"android/content/pm/PackageInfo->versionName:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"8590914"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_JBZH24QY2NQ74ZZ.png)

补

| 123456789 | `@Override``public` `long` `getLongField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch` `(signature) {``case` `"android/content/pm/PackageInfo->firstInstallTime:J"``: {``return` `1742976047391L;``}``}``return` `super``.getLongField(vm, dvmObject, signature);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_8CSZEVTWKNMDRYR.png)

补

| 123 | `case` `"android/content/pm/PackageInfo->lastUpdateTime:J"``: {``return` `System.currentTimeMillis();``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_AAEQ8MGEYMXD8N3.png)

补

| 123 | `case` `"android/content/pm/PackageInfo->applicationInfo:Landroid/content/pm/ApplicationInfo;"``: {``return` `vm.resolveClass(``"android/content/pm/ApplicationInfo"``).newObject(vm);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_Y9KRBW48DB7623P.png)

补

| 123456789 | `@Override``public` `int` `getIntField(BaseVM vm, DvmObject<?> dvmObject, String signature) {``switch` `(signature) {``case` `"android/content/pm/ApplicationInfo->targetSdkVersion:I"``: {``return` `23``;``}``}``return` `super``.getIntField(vm, dvmObject, signature);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_7PSMQH5WS6MEEJ6.png)

补

| 123 | `case` `"android/content/pm/ApplicationInfo->publicSourceDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/user/0/com.xingin.xhs"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_VQK467YSBUPPPJE.png)

补

| 123 | `case` `"android/content/pm/ApplicationInfo->dataDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/data/com.xingin.xhs"``);``}` |
|-|-|

运行
![image](https://bbs.kanxue.com/upload/attach/202603/951135_AM28QBEH2VN4V5K.png)

补

| 123 | `case` `"android/content/pm/ApplicationInfo->nativeLibraryDir:Ljava/lang/String;"``: {``return` `new` `StringObject(vm,` `"/data/app/~~SIH8_S_phQLm2etlRFaJgw==/com.xingin.xhs-YqL1zdzYkIykiQ7RagLamw==/lib/arm64"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_X475UQ743ZXH42C.png)

补

| 123 | `case` `"android/content/pm/ApplicationInfo->flags:I"``: {``return` `0``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_42V3MW6JCKV548C.png)

补，这里注意有特殊情况

| 123456789 | `case` `196173915``: {``ArrayObject arrayObject = vaList.getObjectArg(``1``);``String clazzName = (String) arrayObject.getValue()[``0``].getValue();``System.out.println(``"clazzName "` `+ clazzName);``if` `(clazzName.equals(``"WifiManager"``)) {``return` `vm.resolveClass(``"android/net/wifi/WifiManager"``);``}``return` `vm.resolveClass(clazzName.replaceAll(``"\\."``,` `"/"``));``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_AN4APDKKCTX5XCJ.png)

补

| 123 | `case` `"android/app/ActivityThread->currentProcessName()Ljava/lang/Object;"``: {``return` `new` `StringObject(vm,` `"com.xingin.xhs"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_PZCD6TJAXJYUZHW.png)

补

| 123456789 | `@Override``public` `DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/content/Context->getContentResolver()Landroid/content/ContentResolver;"``: {``return` `vm.resolveClass(``"android/content/ContentResolver"``).newObject(``null``);``}``}``return` `super``.callObjectMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_44AATBM533R2VY5.png)

补，这里注意输入参数

| 123456789101112131415 | `@Override``public` `int` `callStaticIntMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/provider/Settings$System->getInt(Landroid/content/ContentResolver;Ljava/lang/String;)I"``: {``String arg1 = (String) vaList.getObjectArg(``1``).getValue();``System.out.println(``"Settings$System arg1="` `+ arg1);``if` `(arg1.equals(``"screen_brightness"``)) {``return` `85``;``}` `else` `if` `(arg1.equals(``"screen_brightness_mode"``)) {``return` `0``;``}``}``}``return` `super``.callStaticIntMethodV(vm, dvmClass, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_KTJWFAFUEJM3QR3.png)

补

| 123456789 | `case` `"android/provider/Settings$Secure->getInt(Landroid/content/ContentResolver;Ljava/lang/String;)I"``: {``String arg1 = (String) vaList.getObjectArg(``1``).getValue();``System.out.println(``"Settings$Secure arg1="` `+ arg1);``if` `(arg1.equals(``"accessibility_enabled"``)) {``return` `1``;``}` `else` `if` `(arg1.equals(``"location_mode"``)) {``return` `1``;``}``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_QTGV85KSW4MQJVY.png)

补

| 1234567 | `case` `"android/provider/Settings$Global->getInt(Landroid/content/ContentResolver;Ljava/lang/String;)I"``: {``String arg1 = (String) vaList.getObjectArg(``1``).getValue();``System.out.println(``"Settings$Global arg1="` `+ arg1);``if` `(arg1.equals(``"adb_enabled"``)) {``return` `0``;``}``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_PU7EUCPWTX2CH8A.png)

进入报错位置，看到报错是因为`dvmMehtod`是null，并且根据前面的日志，大概率是和`android/content/Intent`相关的问题，但是并没有补充过，这个类相关的环境，继续向前看，应该是分支环境没有补充，

![image](https://bbs.kanxue.com/upload/attach/202603/951135_HFAU6EZ6B9A9KH2.png)

看到`309143350`情况没有补全，顺带将其他没有补全的情况也都给补全。

| 123456 | `case` `655253934``: {``return` `new` `StringObject(vm,` `"1080,2280,440"``);``}``case` `309143350``: {``return` `vm.resolveClass(``"android/content/Intent"``).newObject(``null``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_Q9Q2MU3V8KVK58F.png)

补

| 123 | `case` `"android/content/Intent->getBooleanExtra(Ljava/lang/String;Z)Z"``: {``return` `true``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_GEW6YXU8QSV2WEQ.png)

补

| 123456789 | `@Override``public` `int` `callIntMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/content/Intent->getIntExtra(Ljava/lang/String;I)I"``: {``return` `0``;``}``}``return` `super``.callIntMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_Y4BX9799WQCGKDT.png)

补, 注意这里的调用又是有参数的

| 123456789101112131415 | `case` `"android/content/Context->getSystemService(Ljava/lang/String;)Ljava/lang/Object;"``: {``String arg = (String) vaList.getObjectArg(``0``).getValue();``System.out.println(``"Context.getSystemService arg="` `+ arg);``if` `(arg.equals(``"phone"``)) {``return` `vm.resolveClass(``"android/telephony/TelephonyManager"``).newObject(``null``);``}` `else` `if` `(arg.equals(``"wifi"``)) {``return` `vm.resolveClass(``"android/net/wifi/WifiManager"``).newObject(``null``);``}` `else` `if` `(arg.equals(``"audio"``)) {``return` `vm.resolveClass(``"android/media/AudioManager"``).newObject(``null``);``}` `else` `if` `(arg.equals(``"batterymanager"``)) {``return` `vm.resolveClass(``"android/os/BatteryManager"``).newObject(``null``);``}` `else` `{``return` `null``;``}``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_UPEWCKJQMJFGYFV.png)

补

| 123 | `case` `"android/telephony/TelephonyManager->getSimState()Ljava/lang/Object;"``: {``return` `1``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_FTY8BAER52FF52S.png)

补

| 123 | `case` `"android/telephony/TelephonyManager->getSimOperator()Ljava/lang/Object;"``: {``return` `new` `StringObject(vm,` `"06"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_QJRT9PJWB8YJ7U2.png)

补

| 123 | `case` `"android/telephony/TelephonyManager->getSimOperatorName()Ljava/lang/Object;"``: {``return` `new` `StringObject(vm,` `"中国联通"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_MTFHGEAGGNZ5NTY.png)

补

| 123456789 | `@Override``public` `boolean` `callStaticBooleanMethodV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/app/ActivityManager->isUserAMonkey()Z"``: {``return` `false``;``}``}``return` `super``.callStaticBooleanMethodV(vm, dvmClass, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_7QUUN259E9FKUG8.png)

补

| 123 | `case` `"android/net/wifi/WifiManager->isWifiEnabled()Ljava/lang/Object;"``: {``return` `true``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_JGPT7NRW47KETWN.png)

补

| 123456789 | `@Override``public` `long` `callLongMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {``switch` `(signature) {``case` `"android/os/BatteryManager->getLongProperty(Ljava/lang/String;)Ljava/lang/Object;"``: {``return` `100L;``}``}``return` `super``.callLongMethodV(vm, dvmObject, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_FFYJBQJFSMHGTHQ.png)

补

| 123 | `case` `"android/telephony/TelephonyManager->getNetworkCountryIso()Ljava/lang/Object;"``: {``return` `new` `StringObject(vm,` `"CN"``);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_99Q8FA4AV47C2PN.png)

补

| 123 | `case` `"android/media/AudioManager->getStreamVolume(Ljava/lang/String;)Ljava/lang/Object;"``: {``return` `1``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_YE8VVZYHVTA64XZ.png)

补

| 123 | `case` `"android/media/AudioManager->getStreamMaxVolume(Ljava/lang/String;)Ljava/lang/Object;"``: {``return` `100``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_27TNNAFMSQCPNR6.png)

补

| 123 | `case` `"android/telephony/TelephonyManager->getPhoneType()Ljava/lang/Object;"``: {``return` `1``;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_PG9S62XEMZCQCWS.png)

从上图中可以看出，出错的位置是`prctl`系统调用中有不支持的`option`类型，简单粗暴无脑补全即可，网上搜索`prctl.h`对应头文件简单看一下对应的值，

![image](https://bbs.kanxue.com/upload/attach/202603/951135_TURKE76XHAHD8B6.png)

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_EMCE7WGVKUZDTVN.png)

补

![image](https://bbs.kanxue.com/upload/attach/202603/951135_AKAFTYF7M6JUVPU.png)

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_WYUDUKQMV42WT25.png)

补

| 12345678910 | `@Override``public` `DvmObject<?> newObjectV(BaseVM vm, DvmClass dvmClass, String signature, VaList vaList) {``switch` `(signature) {``case` `"java/util/HashMap-><init>()V"``: {``HashMap<String, String> map =` `new` `LinkedHashMap<>();``return` `ProxyDvmObject.createObject(vm, map);``}``}``return` `super``.newObjectV(vm, dvmClass, signature, vaList);``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_628E54ZAPH2KVX3.png)

补

| 12345678 | `case` `"java/util/Map->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;"``: {``DvmObject<?> key = vaList.getObjectArg(``0``);``DvmObject<?> value = vaList.getObjectArg(``1``);``System.out.println(``"Map.put key="` `+ key +` `" value="` `+ value);``HashMap<String, String> map = (HashMap<String, String>) dvmObject.getValue();``map.put((String) key.getValue(), (String) value.getValue());``return` `value;``}` |
|-|-|

运行

![image](https://bbs.kanxue.com/upload/attach/202603/951135_YTVC9BK78MZNAKK.png)

完成。

## 总结

一切都以能跑出结果为主。

---

# 回复

## 回复 by mb_roiscepd (#2)

*2025-12-30 14:04*

666

## 回复 by mb_fidppcok (#3)

*2025-12-30 14:59*

666

## 回复 by mb_asiwnxyv (#4)

*2025-12-30 16:27*

666

## 回复 by mb_mlyojneh (#5)

*2025-12-30 16:29*

666

## 回复 by k4y0z (#6)

*2025-12-30 16:55*

666

## 回复 by mb_ldbucrik (#7)

*2025-12-30 20:06*

感谢分享

## 回复 by 带带弟弟吧 (#8)

*2025-12-30 20:41*

111

## 回复 by MaYil (#9)

*2025-12-30 21:28*

感谢分享

## 回复 by KanXue_NG (#10)

*2025-12-30 22:29*

感谢分享

## 回复 by wx_插曲 (#11)

*2025-12-31 09:22*

666

## 回复 by 1sfans (#12)

*2025-12-31 09:28*

6666

## 回复 by FindCall (#13)

*2025-12-31 10:54*

666

## 回复 by kingking888 (#14)

*2025-12-31 11:02*

666

## 回复 by mb_cbgtaveo (#15)

*2025-12-31 11:11*

666666666

## 回复 by mb_ykavguun (#16)

*2025-12-31 12:07*

1111

## 回复 by mb_pmgifpme (#17)

*2025-12-31 15:27*

1

## 回复 by mb_uvyukvot (#18)

*2025-12-31 17:52*

666

## 回复 by mb_qimctavn (#19)

*2025-12-31 18:08*

6

## 回复 by 温泉划水鱼 (#20)

*2025-12-31 20:56*

6

## 回复 by mb_euhyowpw (#21)

*2025-12-31 22:27*

1

## 回复 by mb_pobqzscg (#22)

*2025-12-31 23:12*

666

## 回复 by hacker521 (#23)

*2026-1-1 13:38*

666

## 回复 by 五彩斑斓的黑 (#24)

*2026-1-1 14:03*

666

## 回复 by git_27068Lych1e1 (#25)

*2026-1-1 16:00*

6666

## 回复 by jw8888 (#26)

*2026-1-1 18:55*

66666666

## 回复 by wx_故事与酒 (#27)

*2026-1-2 02:30*

666666666666666666

## 回复 by zylyy (#28)

*2026-1-2 11:39*

666

## 回复 by mb_apynwbms (#29)

*2026-1-2 11:42*

6666

## 回复 by tubecityman (#30)

*2026-1-2 14:55*

6666

## 回复 by XCicada (#31)

*2026-1-2 18:48*

666

## 回复 by Imxz (#32)

*2026-1-3 09:05*

tql

## 回复 by kupei (#33)

*2026-1-3 14:29*

666

## 回复 by pythonSpider (#34)

*2026-1-3 20:27*

6666

## 回复 by huangjw (#35)

*2026-1-4 09:29*

学习了，好文章

## 回复 by 小辣鸡的id (#36)

*2026-1-4 10:34*

666

## 回复 by mb_ygxdlbdi (#37)

*2026-1-4 13:38*

6666666666

## 回复 by 丶咖啡猫丶 (#38)

*2026-1-4 15:22*

666

## 回复 by 铭天星 (#39)

*2026-1-4 17:10*

666

## 回复 by mb_bhsrdtqf (#40)

*2026-1-4 17:19*

666

## 回复 by mb_fywmigrm (#41)

*2026-1-5 14:50*

1

## 回复 by mb_nggigxxl (#42)

*2026-1-6 08:33*

666

## 回复 by 做好事不留名 (#43)

*2026-1-6 10:24*

补的比较新的一个版本，签名出来了，但是只要开trace就死循环

## 回复 by fenfei331 (#44)

*2026-1-6 11:59*

666

## 回复 by mb_lxotxkix (#45)

*2026-1-6 16:15*

111111

## 回复 by mb_chjjqnap (#46)

*2026-1-6 17:38*

补，补，补

## 回复 by APT_华生 (#47)

*2026-1-6 18:07*

66

## 回复 by mb_ssnabqqf (#48)

*2026-1-7 17:42*

222

## 回复 by 墨点 (#49)

*2026-1-10 10:56*

666

## 回复 by wx_lll_652 (#50)

*2026-1-11 07:43*

学习学习学习

## 回复 by mb_uoktlvrn (#51)

*2026-1-14 11:10*

111

## 回复 by 淡定小胖子 (#52)

*2026-1-14 11:17*

666

## 回复 by 茄子不茄 (#53)

*2026-1-15 21:00*

666

## 回复 by iBa0 (#54)

*2026-1-16 09:50*

123

## 回复 by 4Chan (#55)

*2026-1-16 11:13*

666

## 回复 by mb_aiyhfydo (#56)

*2026-1-16 18:07*

so逆向太难了

## 回复 by wx_忆雨星辰 (#57)

*2026-1-22 16:40*

老哥牛！

## 回复 by mb_aiyhfydo (#58)

*2026-1-24 15:27*

有个问题：我执行了代码，生成的x-mini-mua是短的。然后我在unidbg监听libtiny.so的io文件读取指令, 发现libtiny.so 会读取 /data/user/0/com.xingin.xhs/.tistore 信息, 这个文件应该有设备的上报信息之类的, 然后我雷电模拟器的这个文件拷贝出来, 补真机环境时配置上, 运行程序就退出了

| ``` BiliIOResolver IOResolver<AndroidFileIO> { FileResult<AndroidFileIO> (Emulator<AndroidFileIO> emulator, String pathname, oflags) { System..println(+ pathname + + oflags); (pathname) { : { [] bytes = FileUtil.(); FileResult.(ByteArrayFileIO(oflags, pathname, bytes)); } } ; } } () { = AndroidEmulatorBuilder.() .setProcessName() .addBackendFactory(DynarmicFactory()) .build(); .getSyscallHandler().addIOResolver(BiliIOResolver()); Memory memory = .getMemory(); memory.setLibraryResolver(AndroidResolver()); SystemPropertyHook systemPropertyHook = SystemPropertyHook(); systemPropertyHook.setPropertyProvider(SystemPropertyProvider() { String (String key) { System..println(+ key); (key){ : ; : ; : ; } ; } }); memory.addHookListener(systemPropertyHook); = .createDalvikVM(File()); .setVerbose(); .setJni(); MediaNdkModule(, ).register(memory); AndroidModule(, ).register(memory); JniGraphics(, ).register(memory); DalvikModule dm = .loadLibrary(, ); = dm.getModule(); dm.callJNI_OnLoad(); = .resolveClass(); } ``` |
|-|

![image](https://bbs.kanxue.com/upload/attach/202601/977458_Q5WA476EJYHT7VC.webp)

![image](https://bbs.kanxue.com/upload/attach/202601/977458_GKT8NCAMA2Z7X5V.webp)

![image](https://bbs.kanxue.com/upload/attach/202601/977458_C24AY8JEDTQJHQM.webp)

## 回复 by mb_wxvjqniz (#59)

*2026-1-25 16:53*

6666

## 回复 by mb_cbgtaveo (#60)

*2026-1-25 19:03*

6666666666

## 回复 by 带壳的蜗牛 (#61)

*2026-1-28 15:19*

666

## 回复 by CheRevir (#62)

*2026-1-29 19:03*

666

## 回复 by Evil0ctal (#63)

*2026-2-1 20:32*

感谢分享，顺带提问一下，今天研究了一下xhs V9.1版本的libtiny.so，使用unidbg在补环境的时候f248291e一直返回null，老大有空研究一下呗，关键代码：

  // lz9/f.java - 签名生成入口
  public static Map<String, String> k(String method, String url, byte[] body) {
      // 关键检查：f248291e 必须为 true
      if (!f248291e) {
          return null;  // SDK未初始化，直接返回null
      }
      // 调用Native生成签名
      return (Map) d3.b(-1739140872, method, host, path, query, body);
  }

## 回复 by maxcl (#64)

*2026-2-2 09:51*

6666

## 回复 by mb_nmyiwtzp (#65)

*2026-2-2 10:25*

6666

## 回复 by 小今朝 (#66)

*2026-2-2 15:41*

666

## 回复 by mb_uzmffdbw (#67)

*2026-2-3 14:11*

666

## 回复 by jasonxgw (#68)

*2026-2-6 11:21*

tql

## 回复 by mb_fglogyec (#69)

*2026-2-7 13:00*

6666

## 回复 by mb_jwsrquaj (#70)

*2026-2-9 22:36*

6666

## 回复 by mb_ijumdife (#71)

*2026-2-11 01:05*

666666666666

## 回复 by mb_kfdusnod (#72)

*2026-2-14 09:26*

![image](https://bbs.kanxue.com/view/img/face/004.gif)

## 回复 by mb_uzmffdbw (#73)

*2026-2-14 10:13*

6

## 回复 by 魂焱 (#74)

*2026-2-18 01:01*

6666666

## 回复 by wx_Huber Barrientos (#75)

*2026-2-18 05:13*

为你点赞！

## 回复 by Ivory0 (#76)

*2026-2-19 01:44*

>
> [Evil0ctal](https://bbs.kanxue.com/user-1001799.htm)
>
>  感谢分享，顺带提问一下，今天研究了一下xhs V9.1版本的libtiny.so，使用unidbg在补环境的时候f248291e一直返回null，老大有空研究一下呗，关键代码： ...
>
>

我看了好几篇帖子，他们说是没有初始化，我现在还在找初始化部分的代码

## 回复 by wx_huhu_859 (#77)

*2026-2-19 02:32*

11

## 回复 by Xnxin (#78)

*2026-2-24 07:29*

这个有点东西的啊！

## 回复 by mb_ilyviizj (#79)

*2026-2-26 01:28*

111

## 回复 by mb_gqzoivfx (#80)

*2026-3-5 15:21*

6666

## 回复 by 开胃小菜Wx (#81)

*2026-3-5 17:11*

学习学习

## 回复 by 兰小娟 (#82)

*2026-3-7 15:53*

主动调用怎么调用？

## 回复 by daiviswang (#83)

*2026-3-8 19:58*

11111

## 回复 by goobey (#84)

*2026-3-10 16:32*

需要看看

## 回复 by PanzerT (#85)

*2026-3-11 19:35*

66666

## 回复 by mb_cvbvxsvd (#86)

*2026-3-15 11:49*

66666

## 回复 by 悟 (#87)

*2026-3-18 22:10*

1111111

## 回复 by 天地一逆旅 (#88)

*2026-3-19 11:38*

666666

## 回复 by mb_ojmwlzvk (#89)

*2026-3-19 21:49*

1

## 回复 by xeiyu (#90)

*2026-3-20 20:46*

666

## 回复 by git_73766huu899283-beep (#91)

*2026-3-23 16:25*

1

## 回复 by mb_stdlrcgp (#92)

*2026-3-29 01:28*

66666

## 回复 by dob_C (#93)

*2026-3-30 14:04*

感谢分享

## 回复 by mb_yedelpbl (#94)

*2026-3-31 20:40*

666

## 回复 by mb_tjsboqui (#95)

*2026-4-2 01:01*

666

## 回复 by mb_grkcgjyc (#96)

*2026-4-4 10:51*

6666

## 回复 by mb_ncfbmciq (#97)

*2026-4-4 17:33*

666

## 回复 by 新手入门% (#98)

*2026-4-6 11:12*

666

## 回复 by git_56402Syy040316 (#99)

*2026-4-8 23:12*

1

## 回复 by mb_kkdrurym (#100)

*2026-4-12 23:49*

666

## 回复 by mb_mgmaxnuw (#101)

*2026-4-14 15:06*

666

## 回复 by MuitiHub (#102)

*2026-4-16 21:14*

6666666

## 回复 by mb_agxdcibq (#103)

*2026-4-17 11:17*

好文 补的到位

## 回复 by mb_jcwakofc (#104)

*2026-4-17 15:32*

666

## 回复 by mb_rzyawund (#105)

*2026-4-17 20:16*

6666

## 回复 by mb_uikdudgo (#106)

*2026-4-18 19:08*

12121

## 回复 by mb_zcfhleoj (#107)

*2026-4-22 16:39*

感谢分享

## 回复 by mb_ehrbohcl (#108)

*2026-4-23 16:36*

6666

## 回复 by shmilyaxy (#109)

*2026-4-24 18:21*

666

## 回复 by mb_ysikfhxt (#110)

*2026-4-27 15:11*

111

## 回复 by mb_evapxmjh (#111)

*2026-5-8 00:29*

6666

## 回复 by mb_cqabxiww (#112)

*2026-5-9 10:19*

6666

## 回复 by Topdayplus (#113)

*2026-5-9 10:24*

666

## 回复 by leijeo (#114)

*2026-5-14 23:46*

666 学习了

## 回复 by maomaolk (#115)

*2026-5-15 12:23*

666

## 回复 by 信心风暴 (#116)

*2026-5-17 13:11*

999

## 回复 by mb_farzbkyi (#117)

*2026-5-26 13:15*

666

## 回复 by mb_ifyzpddv (#118)

*2026-6-1 17:55*

66666

## 回复 by zhangminnn (#119)

*2026-6-5 14:17*

666

## 回复 by wx_归期_856 (#120)

*2026-6-6 09:24*

1

## 回复 by woasion (#121)

*2026-6-9 21:52*

1

## 回复 by AyonA333 (#122)

*2026-6-16 09:33*

666

## 回复 by Freax (#123)

*2026-6-16 16:28*

666

## 回复 by mb_xzwzvabc (#124)

*2026-6-17 16:25*

看看

## 回复 by ldz666 (#125)

*2026-6-18 17:27*

666

## 回复 by rock123321 (#126)

*2026-6-22 16:08*

1

## 回复 by Akira_ (#127)

*2026-6-27 02:53*

666

## 回复 by mb_owolhjgd (#128)

*2026-7-1 01:31*

6666

## 回复 by jayce.1 (#129)

*2026-7-10 10:32*

666

## 回复 by mb_lfwgtxdb (#130)

*2026-7-14 17:08*

感谢分享

## 回复 by mb_yvuzbfvo (#131)

*2026-7-18 18:04*

看看

## 回复 by git_81484chinasoul (#132)

*2026-7-22 15:05*

![image](https://bbs.kanxue.com/view/img/face/003.gif)
