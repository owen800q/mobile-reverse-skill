---
title: '[原创]安卓逆向之 Autojs 加密 JS 文件提取和解密'
url: https://bbs.kanxue.com/thread-288020.htm
tid: 288020
author: 咚咚汪
date: '2025-08-13'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T14:05:06+08:00'
replies: 13
---

# 一、引言

第一次学习安卓逆向是在b站上，无意中看到了正己大佬的视频课程，于是就开始了安卓逆向学习之旅。
视频课程看了一般，觉得不过瘾，必须得找点东西练手，于是有了这篇文章。

## 1.1 Autojs

这个工具主要是用来实现安卓设备上的自动化，当然也有用到灰产的。其主要优势在于可以使用js语言实现对app的操作，用它来实现自动化脚本，对新手很友好。

## 1.2 逆向 Autojs 加密 JS 文件的意义

众所周知，autojs中的js代码都是经过加密的，因此逆向分析其加解密原理是值得学习的一件事。同时，也能通过逆向后的js源码对其脚本进行学习。
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_CX5G2U4GFFAZVK4.webp)
本次逆向选择的app为魔方xx

# 二、准备工作

## 2.1 工具选择

### Frida

用于动态hook

### jadx

反编译

### mt管理器

包提取工具

## 2.2 环境搭建

环境搭建这里不做额外说明

# 三、逆向分析流程

## 3.1 反编译 APK

通过mt管理器可以提取出apk文件，打开apk的文件夹看到对应的dex文件很小，只有几kb
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_4EK3V6DEYWYVK55.webp)
直觉告诉我没那么简单，不管3721，先拉出来瞅一眼再说；
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_8YPVGDPBB4A7QDG.webp)
果然很诡异，新手的我一脸懵逼
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_GQYVGRMX9PQQXGB.webp)
不管咋样还得打开看看源码
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_K59JKS99565VM8B.webp)
可以看出来是继承了一个Application类，代码也经过混淆的，没眼看。
后来想到一个办法，把混淆的代码丢给ai，让ai翻译一下不就好了。于是乎拿到了精简后的代码：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163 | `public` `class` `p extends Application {``public Class a` `=` `null;` `public p() {``Thread.currentThread();``}` `public static void load(String` `str``,` `File` `file``) {``ZipInputStream zipInputStream` `=` `new ZipInputStream(new FileInputStream(``str``));``for` `(ZipEntry nextEntry` `=` `zipInputStream.getNextEntry(); nextEntry !``=` `null; nextEntry` `=` `zipInputStream.getNextEntry()) {``if` `(!nextEntry.isDirectory()) {``str` `=` `nextEntry.getName();``String str2` `=` `"Ye6fiMSPw7nHlMSPLmwyaGVkw7nHlMSPZMO5xJE="``;``if` `(``str``.contains(``"libmh.so"``)) {` `/``/` `qs(str2) 替换结果``BufferedOutputStream bufferedOutputStream` `=` `new BufferedOutputStream(new FileInputStream(``file``.getAbsolutePath()));``try` `{``byte[] bArr` `=` `new byte[``4096``];``while` `(true) {``int` `read` `=` `zipInputStream.read(bArr);``if` `(read !``=` `-``1``) {``bufferedOutputStream.write(bArr,` `0``, read);``}` `else` `{``bufferedOutputStream.close();``return``;``}``}``} catch (Throwable th) {``th.addSuppressed(th);``}``}``}``zipInputStream.closeEntry();``}` `}`   `public static String qs(String` `str``) {``try` `{``String str2` `=` `new String(Base64.decode(``str``,` `0``));``String str3` `=` `"ùǔď"``;``String[] split` `=` `str2.split(str3);``str2` `=` `split[``1``];``str3` `=` `"\\'"``;``str2` `=` `str2.replace(str3,` `"'"``);``str2` `=` `str2.replace(``"\\n"``,` `"\n"``);``str2` `=` `str2.replace(``"\\r"``, "");``return` `str2;``} catch (Exception e) {``return` `str``;``}``}` `public void attachBaseContext(Context context) {``super``.attachBaseContext(context);``String` `str` `=` `"=====>"``;``str` `=` `"====loadDex:"``;` `/``/` `qs(``str``) 替换结果``String str2` `=` `"x5zHlsSTw7nHlMSPYXR0YWNoQmFzZUNvbnRleHTDuceUxI9l7p+IxJU="``;``Log.e(``str``,` `"attachBaseContext"``);` `/``/` `qs(str2) 替换结果``str2` `=` `"loadDex1:"``;` `/``/` `qs(``"ZcO6xIHDuceUxI9sb2FkRGV4MTrDuceUxI/HlmLEgw=="``) 替换结果``try` `{``String path` `=` `getCacheDir().getPath();``File` `file` `=` `new` `File``(path,` `"l2hed.dex"``);` `/``/` `qs(``"xavHnMSDw7nHlMSPbDJoZWQuZGV4w7nHlMSP7p+IY8SF"``) 替换结果``String str3` `=` `"YcO8xIXDuceUxI9sMmhlZGQuZGV4w7nHlMSPYsO6xIc="``;``File` `file2` `=` `new` `File``(path,` `"l2hedd.dex"``);` `/``/` `qs(str3) 替换结果``StringBuilder fileInputStream` `=` `new FileInputStream(str2);``fileInputStream.append(path);``Log.e(``str``, fileInputStream.toString());``/``/` `loadDex1:``/``data``/``user``/``0``/``com.duya667.mfhzplus``/``cache``if` `(!``file``.exists()) {``/``/``l2hed.dex 不存在的情况下 去读so文件里的数据``load(getApplicationInfo().sourceDir, file2);``/``/` `读取apk文件中的so 写到l2hedd.dex中 再将l2hedd.dex做位运算 写到l2hed.dex中``str2` `=` `file2.getAbsolutePath();``str3` `=` `file``.getAbsolutePath();``FileInputStream fileInputStream2` `=` `new FileInputStream(str2);``try` `{``FileOutputStream fileInputStream3` `=` `new FileInputStream(str3);``while` `(true) {``try` `{``int` `read` `=` `fileInputStream2.read();``if` `(read` `=``=` `-``1``) {``break``;``}``fileInputStream3.write((byte) ((read <<` `5``) \| (read >>` `3``)));``} catch (Throwable th) {``th.addSuppressed(th);``}``}``fileInputStream3.close();``fileInputStream2.close();``file``.setReadOnly();``file2.delete();``} catch (Throwable th2) {``th.addSuppressed(th2);``}``}``StringBuilder stringBuilder` `=` `new StringBuilder();``stringBuilder.append(``"loadDex2:"``);` `/``/` `qs(``"Zu6fiMSHw7nHlMSPbG9hZERleDI6w7nHlMSPx5TDusSJ"``) 替换结果``stringBuilder.append(path);``/``/` `loadDex2:``/``data``/``user``/``0``/``com.duya667.mfhzplus``/``cache``Log.e(``str``, stringBuilder.toString());``DexClassLoader dexClassLoader` `=` `new DexClassLoader(``file``.getAbsolutePath(), path, null, getClassLoader());``/``/``l2hed.dex``str` `=` `"l.g"``;``Class loadClass` `=` `dexClassLoader.loadClass(``str``);``this.a` `=` `loadClass;``try` `{` `str2` `=` `"a"``;``r5` `=` `new Class[``2``];``Class` `cls` `=` `Context.``class``;``r5[``0``]` `=` `cls``;``r5[``1``]` `=` `cls``;``Method method` `=` `loadClass.getMethod(str2, r5);``Object``[] objArr` `=` `new` `Object``[]{context, this};``method.invoke(null, objArr);``} catch (Exception unused) {``}``} catch (Exception e) {` `String str4` `=` `"w7nHlsSJw7nHlMSPPT09PT0+bG9hZERleEV4w7nHlMSPYcO5xIs="``;``Log.e(``"loadDexEx"``, e.getMessage());` `/``/` `qs(str4) 替换结果``e.printStackTrace();``}` `}` `public android.content.Context createPackageContext(java.lang.String r6,` `int` `r7) {``throw new UnsupportedOperationException(``"Method not decompiled: d.p.createPackageContext(java.lang.String, int):android.content.Context"``);``}` `public String getPackageName() {``String` `str` `=` `"w7nun4jEj8O5x5TEjz09PT09PsO5x5TEj2Xun4jEkQ=="``;``str` `=` `"====getPackageName:"``;` `/``/` `qs(``str``) 替换结果``String str2` `=` `"w7rHlsSRw7nHlMSPZ2V0UGFja2FnZU5hbWXDuceUxI/HlseYxJM="``;``Log.e(``str``,` `"getPackageName"``);` `/``/` `qs(str2) 替换结果``CharSequence charSequence` `=` `null;``try` `{``Class` `cls` `=` `this.a;``Method method` `=` `cls``.getMethod(``"e"``, null);``charSequence` `=` `(String) method.invoke(null, null);``} catch (Exception unused) {``}``if` `(TextUtils.isEmpty(charSequence)) {``str` `=` `super``.getPackageName();``return` `str``;``}``return` `charSequence;``}` `public void onCreate() {``super``.onCreate();``String` `str` `=` `"w7nHmsSTw7nHlMSPPT09PT0+w7nHlMSPx5bFq8SV"``;``str` `=` `"====onCreate"``;` `/``/` `qs(``str``) 替换结果``Log.e(``str``,` `"onCreate"``);` `/``/` `qs(``"YsWrxIHDuceUxI9vbkNyZWF0ZcO5x5TEj8O8x5bEgw=="``) 替换结果``try` `{``Class` `cls` `=` `this.a;``String str2` `=` `"c"``;``Class[] clsArr` `=` `new Class[]{Application.``class``};``Method method` `=` `cls``.getMethod(str2, clsArr);``Object``[] objArr` `=` `new` `Object``[]{this};``method.invoke(null, objArr);``} catch (Exception unused) {``}``}``}` |
|-|-|

从源代码中看出来实际上不止一个dex文件，和我猜想的一样，肯定还有其他dex文件。事实上和我猜想的一样，验证过程这里不多赘述，先说结论：
这个类是app的入口类，会先调用attachBaseContext方法，这个方法是在onCreate之前调用，它会找l2hed.dex文件，然后使用dex加载器加载到虚拟器，调用l.g这个类，通过反射调用a方法。而oncreate调用的是c方法。

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441442443444445446447448449450451452453454455456457458459460461462463464465466467468469470471472473474475476477478479480481482483 | `public` `class` `g {` `/``*` `renamed` `from``: a  reason: collision with root package name` `*``/``public static String f4038a;` `/``*` `renamed` `from``: b  reason: collision with root package name` `*``/``public static Application f4039b;` `/``*` `renamed` `from``: c  reason: collision with root package name` `*``/``public static boolean f4040c;` `/``*` `renamed` `from``: d  reason: collision with root package name` `*``/``public static` `int` `f4041d;` `/``*` `JADX INFO: Access modifiers changed` `from``: package``-``private` `*``/``/``*` `renamed` `from``: l.g$``1`  `reason: invalid` `class` `name` `*``/``/``*` `loaded` `from``: E:\skill\Android_skill\mofang_dex\l2hed.dex` `*``/``public` `class` `AnonymousClass1 implements Application.ActivityLifecycleCallbacks {``public static void dh(String` `str``, String str2) {``}` `public static String dsg5() {``return` `"wfv1sie46dwy43owj2a2nam"``;``}` `public static String mv(String` `str``) {``try` `{``Runtime.getRuntime();``byte[] decode` `=` `Base64.decode(``str``,` `0``);``Runtime.getRuntime();``String str2` `=` `new String(decode);``dsg5();``dh(``"ǚfď"``,` `"ǚfď"``);``String str3` `=` `str2.split(``"ǚfď"``)[``1``];``SystemClock.elapsedRealtime();``dsg5();``SystemClock.uptimeMillis();``dsg5();``Collections.emptyList();``String replace` `=` `str3.replace(``"\\'"``,` `"'");``Collections.emptyList();``dsg5();``dh("\\n", "\\n");``dsg5();``Resources.getSystem();``String replace2 = replace.replace("\\n", AbstractShell.COMMAND_LINE_END);``SystemClock.elapsedRealtime();``dsg5();``dh("\\r", "\\r");``dsg5();``dh("", "");``String replace3 = replace2.replace("\\r", "");``Collections.emptyList();``dsg5();``return replace3;``} catch (Exception e7) {``dsg5();``return str;``}``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivityCreated(Activity activity, Bundle bundle) {``dsg5();``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivityDestroyed(Activity activity) {``dsg5();``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivityPaused(Activity activity) {``dsg5();``}` `/* JADX WARN: Removed duplicated region for block: B:24:0x0130  */``@Override // android.app.Application.ActivityLifecycleCallbacks``/*``Code decompiled incorrectly, please refer to instructions dump.``To view partially-correct code enable 'Show inconsistent code' option in preferences``*/``public void onActivityResumed(android.app.Activity r12) {``/*``Method dump skipped, instructions count: 314``To view this dump change 'Code comments level' option to 'DEBUG'``*/``throw new UnsupportedOperationException("Method not decompiled: l.g.AnonymousClass1.onActivityResumed(android.app.Activity):void");``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivitySaveInstanceState(Activity activity, Bundle bundle) {``dsg5();``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivityStarted(Activity activity) {``dsg5();``}` `@Override // android.app.Application.ActivityLifecycleCallbacks``public void onActivityStopped(Activity activity) {``dsg5();``}``}` `public g() {` `}` `public static void a(Context context, Context context2) {``String packageName;``String bw = "=====>dexFiles";//dexFiles``SystemClock.uptimeMillis();``String bw2 = "getAppSignature";// getAppSignature``try {``Log.e("=====>dexFiles", "getPackageName1" + context.getPackageName());``Log.e("=====>dexFiles", "fname1:com.duya667.mfhzuplus");``Log.e("=====>dexFiles", "getAppSignature" + f(context));` `Log.e("=====>dexFiles", "sign:c512bc7caad13c98fee cb22c78b9e3acf0a56de5aa");``packageName = context.getPackageName();` `} catch (Exception e7) {``e7.printStackTrace();``}``if (packageName.equals("com.duya667.mfhzuplus")) {``if ("c512bc7caad13c98fee cb22c78b9e3acf0a56de5aa".equals(f(context))) {``f4038a = "com.duya667.mfhzuplus.App";``h(context2);``return;``}``}` `}` `/* JADX WARN: Multi-variable type inference failed */``/* JADX WARN: Type inference failed for: r0v9, types: [android.app.Application$ActivityLifecycleCallbacks, java.lang.Object] */``public static void b(Application application) {``f4041d = TimeZone.getDefault().getOffset(System.currentTimeMillis());``if (!f4040c && !TextUtils.isEmpty(f4038a)) {``String bw = "==";``Log.e(bw, "mSubjectAppName:a" + f4038a);``f4039b = (Application) Class.forName(f4038a).newInstance();` `StringBuilder sb = new StringBuilder("mSubjectApplication:a");``sb.append(f4039b != null);``Log.e(bw, sb.toString());``Context baseContext = application.getBaseContext();` `String bw2 = "attacha";``Method declaredMethod = Application.class.getDeclaredMethod(bw2, Context.class);``declaredMethod.setAccessible(true);``declaredMethod.invoke(f4039b, baseContext);` `Class<?> cls = Class.forName("android.app.ContentImage");` `Field declaredField = cls.getDeclaredField("mOuterContent");``declaredField.setAccessible(true);``declaredField.set(baseContext, f4039b);` `Field declaredField2 = cls.getDeclaredField("mMainThread");``declaredField2.setAccessible(true);``Object obj = declaredField2.get(baseContext);` `Class<?> cls2 = Class.forName("android.app.ActivityThread");` `Field declaredField3 = cls2.getDeclaredField("nInstalledApplication");``declaredField3.setAccessible(true);``declaredField3.set(obj, f4039b);` `Field declaredField4 = cls2.getDeclaredField("mAllApplications");``declaredField4.setAccessible(true);``ArrayList arrayList = (ArrayList) declaredField4.get(obj);``arrayList.remove(application);``arrayList.add(f4039b);` `Field declaredField5 = cls.getDeclaredField("mPackageInfo");``declaredField5.setAccessible(true);``Object obj2 = declaredField5.get(baseContext);` `Class<?> cls3 = Class.forName("android.app.LoadedApk");` `Field declaredField6 = cls3.getDeclaredField("mApplication");``declaredField6.setAccessible(true);``declaredField6.set(obj2, f4039b);` `Field declaredField7 = cls3.getDeclaredField("mApplicationInfo");``declaredField7.setAccessible(true);``((ApplicationInfo) declaredField7.get(obj2)).className = f4038a;``f4039b.onCreate();``f4040c = true;``Application application2 = f4039b;``if (application2 != 0) {``// 注意：此处原代码有语法错误（?? obj3 = new Object();）``Object obj3 = new Object();``application2.registerActivityLifecycleCallbacks(obj3);``}``}``}``public static String bw(String str) {``try {``byte[] decode = Base64.decode(str, 0);``String str2 = new String(decode);``String[] split = str2.split("adă");``String str3 = split[1];``String replace = str3.replace("\\'", "'"``);``String replace2` `=` `replace.replace(``"\\n"``, AbstractShell.COMMAND_LINE_END);``String replace3` `=` `replace2.replace(``"\\r"``, "");``return` `replace3;``} catch (Exception e7) {``return` `str``;``}``}` `/``*` `JADX WARN: Multi``-``variable` `type` `inference failed` `*``/``/``*` `JADX WARN:` `Type` `inference failed` `for``: r0v0, types: [android.app.Application$ActivityLifecycleCallbacks, java.lang.``Object``]` `*``/``public static void c(Application application) {``try` `{``b(application);``} catch (Exception unused) {``}``Application application2` `=` `f4039b;``if` `(application2 !``=` `0``) {``?? obj` `=` `new` `Object``();``VelocityTracker.obtain();``application2.registerActivityLifecycleCallbacks(obj);``}` `}` `public static byte[] c(String` `str``, String str2) {``byte[] bArr;``ZipInputStream zipInputStream` `=` `new ZipInputStream(new FileInputStream(``str``));``ZipEntry nextEntry` `=` `zipInputStream.getNextEntry();``while` `(true) {``bArr` `=` `null;``if` `(nextEntry` `=``=` `null) {``break``;``}` `else` `if` `(nextEntry.isDirectory() \|\| !nextEntry.getName().contains(str2)) {``zipInputStream.closeEntry();``nextEntry` `=` `zipInputStream.getNextEntry();``}` `else` `{``ByteArrayOutputStream byteArrayOutputStream` `=` `new ByteArrayOutputStream();``byte[] bArr2` `=` `new byte[``4096``];``while` `(true) {``int` `read` `=` `zipInputStream.read(bArr2);``if` `(read` `=``=` `-``1``) {``break``;``}``byteArrayOutputStream.write(bArr2,` `0``, read);``}``byte[] byteArray` `=` `byteArrayOutputStream.toByteArray();``try` `{``String formatPattern` `=` `"%016s"``;` `/``/` `bw(``"ZcO8xIlhZMSDJTEkLTE2c2FkxINh7p+IxIk="``)` `String keyPart` `=` `"dhkey"``;` `/``/` `bw(``"YsO5xIthZMSDbDJoZWFkxIPHlGPEiw=="``)``String` `format` `=` `String.``format``(formatPattern, keyPart);`  `String replace` `=` `format``.replace(``" "``,` `"0"``);` `byte[] bytes` `=` `replace.getBytes(``"UTF-8"``);` `/``/` `bw(``"xavHmsSNYWTEg3V0ZjhhZMSDY8WrxI0="``)` `SecretKeySpec secretKeySpec` `=` `new SecretKeySpec(bytes,` `"AES"``);``IvParameterSpec ivParameterSpec` `=` `new IvParameterSpec(bytes);` `Class<?>` `cls` `=` `Class.forName(``"javax.crypto.Cipher"``);` `/``/` `bw(``"w7rDvMSPYWTEg2phdmF4LmNyeXB0by5DaXBoZXJhZMSD7p+IZsSP"``)` `Method method` `=` `cls``.getMethod(``"getInstance"``, String.``class``);` `/``/` `bw(``"x5THlMSRYWTEg2dldEluc3RhbmNlYWTEg8Wrw7rEkQ=="``)` `Object``[] objArr` `=` `{``"AES/CBC/PKCS5Padding"``};` `/``/` `bw(``"x5ZlxJNhZMSDQUVTL0NCQy9QS0NTNVBhZGRpbmdhZMSDY+6fiMST"``)``Object` `invoke` `=` `method.invoke(null, objArr);` `String initMethod` `=` `"init"``;` `/``/` `bw(``"x5jFq8SVYWTEg2luaXRhZMSDx5bHmsSB"``)``Class<?>[] clsArr` `=` `{Integer.``TYPE``, Key.``class``, AlgorithmParameterSpec.``class``};``cls``.getMethod(initMethod, clsArr).invoke(invoke,` `2``, secretKeySpec, ivParameterSpec);``bArr` `=` `i((byte[])` `cls``.getMethod(``"doFinal"``, byte[].``class``).invoke(invoke, byteArray));` `/``/` `bw(``"Y8O5xINhZMSDZG9GaW5hbGFkxIPHmMO5xIM="``)``} catch (Exception unused) {``}``}``}` `return` `bArr;``}` `public static Application d() {``Application application` `=` `f4039b;` `return` `application;``}`  `public static String e() {``String` `str` `=` `f4038a;` `return` `str``;``}` `public static String f(Context context) {``Signature[] signatureArr;``try` `{``Signature[] signatureArr2` `=` `new Signature[``0``];``try` `{``signatureArr` `=` `context.getPackageManager().getPackageInfo(context.getPackageName(),` `64``).signatures;``} catch (PackageManager.NameNotFoundException e7) {``e7.printStackTrace();``}``if` `(signatureArr !``=` `null && signatureArr.length >` `0``) {``String g8` `=` `g(signatureArr[``0``]);` `return` `g8;``}``} catch (Exception e8) {``e8.printStackTrace();``}` `return` `null;``}` `public static String g(Signature signature) {``String algorithm` `=` `"SHA-1"``;` `/``/` `bw(``"Yu6fiMSFYWTEg1NIQTFhZMSDxatlxIU="``)``MessageDigest messageDigest` `=` `MessageDigest.getInstance(algorithm);``byte[] byteArray` `=` `signature.toByteArray();``messageDigest.update(byteArray);``byte[] digest` `=` `messageDigest.digest();``StringBuilder sb` `=` `new StringBuilder();``int` `length` `=` `digest.length;``for` `(``int` `i7` `=` `0``; i7 < length; i7``+``+``) {``Object``[] objArr` `=` `{Byte.valueOf(digest[i7])};``sb.append(String.``format``(``"%02x"``, objArr));` `/``/` `bw(``"w7xlxIdhZMSDJTAyeGFkxINjx5bEhw=="``)``}``String sb2` `=` `sb.toString();``return` `sb2;``}`  `public static void h(Context context) {``String logTag` `=` `"====debugFiles"``;` `/``/` `bw(``"x5ZixIlhZMSDPT09PT0+ZGV4RmlsZXNhZMSDw7xkxIk="``)``Log.e(logTag,` `"ok"``);``e();``ArrayList arrayList` `=` `new ArrayList();``File` `cacheDir` `=` `context.getCacheDir();``File``[] listFiles` `=` `cacheDir.listFiles();` `String prefix` `=` `"mh_"``;` `/``/` `bw(``"w7zDucSLYWTEg2wyaGVhZMSDx5ZkxIs="``)``if` `(listFiles !``=` `null) {``for` `(``File` `file` `: listFiles) {``if` `(``file``.isFile() &&` `file``.getName().startsWith(prefix)) {``String name` `=` `file``.getName();``/``/` `排除特定文件名``if` `(!name.equals(``"de_key.head.dex"``)) {` `/``/` `bw(``"ZGHEjWFkxINsMmhlZC5kZXhhZMSDY8O8xI0="``)``file``.setReadOnly();``arrayList.add(``file``);``}``}``}``}` `Log.e(logTag, ""` `+` `arrayList.size());``/``/` `读取 sourceDir文件夹下的 libmh_文件名开头的文件 读取到数组中``if` `(arrayList.size() <``=` `0``) {``int` `i7` `=` `0``;``while` `(i7 <` `100``) {``try` `{``String` `str` `=` `context.getApplicationInfo().sourceDir;``StringBuilder sb` `=` `new StringBuilder();``sb.append(``"libmh_"``);` `/``/` `bw(``"YceUxI9hZMSDLmwyaGVhZMSDYcO8xI8="``)``sb.append(i7);``byte[] c8` `=` `c(``str``, sb.toString());``if` `(c8` `=``=` `null) {``break``;``}``/``/` `日志标签：``=``=``=``=``encryptedDex1``Log.e(``"====encryptedDex1"``, "``" + c8.length); // bw("``x5xlxJFhZMSDPT09PT0``+``ZW5jcnlwdGVkRGV4MWFkxIPun4jDvMSR")``StringBuilder sb2` `=` `new StringBuilder();``sb2.append(prefix);``i7``+``+``;``sb2.append(i7);``sb2.append(``".dex"``);` `/``/` `bw(``"x5jFq8STYWTEgy5kZXhhZMSDZcecxJM="``)``File` `file2` `=` `new` `File``(cacheDir, sb2.toString());``FileOutputStream fileOutputStream` `=` `new FileOutputStream(file2);``fileOutputStream.write(c8);``fileOutputStream.close();``arrayList.add(file2);``} catch (Exception e7) {``/``/` `日志标签：``=``=``=``=``err1``Log.e(``"====err1"``, "``" + e7.getMessage()); // bw("``xavDvMSVYWTEgz09PT09PmUxYWTEg8Wrx5jEgQ``=``=``")``e7.printStackTrace();``}``}``}``Field field` `=` `null;``for` `(Class<?>` `cls` `=` `context.getClassLoader().getClass();` `cls` `!``=` `null;` `cls` `=` `cls``.getSuperclass()) {``try` `{``/``/` `字段名：pathList``field` `=` `cls``.getDeclaredField(``"pathList"``);` `/``/` `bw(``"x5jDvMSDYWTEg3BhdGhMaXN0YWTEg2ZjxIM="``)``field.setAccessible(true);``break``;``} catch (NoSuchFieldException unused) {``}``}``Object` `obj` `=` `field.get(context.getClassLoader());``Field field2` `=` `null;``for` `(Class<?> cls2` `=` `obj.getClass(); cls2 !``=` `null; cls2` `=` `cls2.getSuperclass()) {``try` `{``/``/` `字段名：dexElements``field2` `=` `cls2.getDeclaredField(``"dexElements"``);` `/``/` `bw(``"YcecxIVhZMSDZGV4RWxlbWVudHNhZMSDYceWxIU="``)``field2.setAccessible(true);``break``;``} catch (NoSuchFieldException unused2) {``}``}``Object``[] objArr` `=` `(``Object``[]) field2.get(obj);``Method method` `=` `null;``for` `(Class<?> cls3` `=` `obj.getClass(); cls3 !``=` `null; cls3` `=` `cls3.getSuperclass()) {``try` `{``/``/` `方法名：makePathElements``method` `=` `cls3.getDeclaredMethod(``"makePathElements"``,` `List``.``class``,` `File``.``class``,` `List``.``class``);` `/``/` `bw(``"x5run4jEh2FkxINtYWtlUGF0aEVsZW1lbnRzYWTEg8eWw7zEhw=="``)``method.setAccessible(true);``break``;``} catch (NoSuchMethodException unused3) {``}``}``/``/` `日志标签：``=``=``=``=``dexFiles1``Log.e(``"====dexFiles1"``, "``" + arrayList.size()); // bw("``7p``+``Ix5jEiWFkxIM9PT09PT5kZXhGaWxlczFhZMSDx5ZkxIk``=``")``/``/` `日志标签：``=``=``=``=``pathList``Log.e(``"====pathList"``,` `"false"``);` `/``/` `bw(``"w7rHmMSLYWTEgz09PT09PnBhdGhMaXN0YWTEg+6fiGXEiw=="``)``Log.e(logTag,` `"false"``);``StringBuilder sb3` `=` `new StringBuilder("");``sb3.append(method` `=``=` `null);``String sb4` `=` `sb3.toString();``/``/` `日志标签：``=``=``=``=``makeDexElements``Log.e(``"====makeDexElements"``, sb4);` `/``/` `bw(``"w7zHlMSNYWTEgz09PT09Pm1ha2VEZXhFbGVtZW50c2FkxIPDumbEjQ=="``)``Object``[] objArr2` `=` `(``Object``[]) method.invoke(obj, arrayList, null, null);``Object``[] objArr3` `=` `(``Object``[]) Array.newInstance(objArr.getClass().getComponentType(), objArr.length` `+` `objArr2.length);``System.arraycopy(objArr,` `0``, objArr3,` `0``, objArr.length);``System.arraycopy(objArr2,` `0``, objArr3, objArr.length, objArr2.length);``field2.``set``(obj, objArr3);``}` `public static byte[] i(byte[] bArr) {``byte[] bArr2;``byte[] bArr3` `=` `new byte[``1024``];``ByteArrayOutputStream byteArrayOutputStream` `=` `new ByteArrayOutputStream();``ZipInputStream zipInputStream` `=` `new ZipInputStream(new ByteArrayInputStream(bArr));``try` `{``try` `{``zipInputStream.getNextEntry();``while` `(true) {``int` `read` `=` `zipInputStream.read(bArr3);``if` `(read` `=``=` `-``1``) {``break``;``}``byteArrayOutputStream.write(bArr3,` `0``, read);``}``bArr2` `=` `byteArrayOutputStream.toByteArray();``try` `{``zipInputStream.close();``} catch (IOException e7) {``e7.printStackTrace();``}``} catch (IOException e8) {``e8.printStackTrace();``try` `{``zipInputStream.close();``} catch (IOException e9) {``e9.printStackTrace();``}``bArr2` `=` `null;``}` `return` `bArr2;``} catch (Throwable th) {``try` `{``zipInputStream.close();``} catch (IOException e10) {``e10.printStackTrace();``}``throw th;``}``}``}` |
|-|-|

l.g这个类主要做了签名校验，以及剩下的dex文件的加载，也就是说这个app中的类不是启动的时候就全部加载进内存了，所以我在这里使用frida进行hook的时候很多类都没办法hook到，卡了很久才弄明白这个app的dex的加载过程。
而具体的dex文件是在res文件夹下，
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_EN2XTHVRQGBQXT4.webp)
目前离真相又近了一步，这些都是傀儡，真正的入口是com.xxx.mfhzuplus.App这个类
于是将这些dex文件丢到jadx中，用关键字搜索出这个类名，拿到源码：
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_SM4G2DNDQ4EF5AP.webp)
熟悉的oncreate方法，现在已经到了山脚下，接下来就是登山时刻；
看到关键代码ProjectConfig这个类，联想到assert文件夹下也有一个这样的json文件，可以大胆猜测两个就是一回事。

| 1234 | `public final void initFingerprint(ProjectConfig projectConfig) {``b.n(projectConfig,` `"config"``);``ScriptEncryption.sInstance.initFingerprint(projectConfig);``}` |
|-|-|

通过这个方法见名知意，应该是跟加密有关系的，毕竟名字叫做指纹，肯定脱不了关系；

| 12345678910111213141516171819202122232425262728 | `public final void initFingerprint(ProjectConfig projectConfig) {``b.n(projectConfig,` `"config"``);``String I` `=` `k.I(projectConfig.packageName` `+` `projectConfig.versionName` `+` `projectConfig.mainScriptFile` `+` `projectConfig.versionCode);``StringBuilder sb` `=` `new StringBuilder();``sb.append(projectConfig.buildInfo.getBuildId());``sb.append(projectConfig.name);``String I2` `=` `k.I(sb.toString());``b.m(I2,` `"md5(config.buildInfo.buildId + config.name)"``);``String substring` `=` `I2.substring(``0``,` `16``);``b.m(substring,` `"this as java.lang.String…ing(startIndex, endIndex)"``);``this.mInitVector` `=` `substring;``b.m(I,` `"key"``);``byte[] bytes` `=` `I.getBytes(a.f2878a);``b.m(bytes,` `"this as java.lang.String).getBytes(charset)"``);``String` `str` `=` `this.mInitVector;``b.n(``str``,` `"initVector"``);``byte[] bArr` `=` `f0const;``b.n(bArr,` `"plainText"``);``SecretKeySpec secretKeySpec` `=` `new SecretKeySpec(bytes,` `"AES"``);``Cipher cipher` `=` `Cipher.getInstance(``"AES/CBC/PKCS7Padding"``);``byte[] bytes2` `=` `str``.getBytes(a.f2878a);``b.m(bytes2,` `"this as java.lang.String).getBytes(charset)"``);``cipher.init(``1``, secretKeySpec, new IvParameterSpec(bytes2));``byte[] doFinal` `=` `cipher.doFinal(bArr);``b.m(doFinal,` `"cipher.doFinal(plainText)"``);``Scription.ks` `=` `doFinal;``this.mKey` `=` `doFinal;``}` |
|-|-|

果然是和加密有关，混淆后的代码看的很吃力，但是交给AI去读就很容易了，这个方法是要初始化一个key；这个key是用来做加解密的；
这个类也定义了加解密的方法：

| 1234567891011121314151617181920212223242526272829303132 | `public final byte[] decrypt(byte[] bArr,` `int` `i6,` `int` `i7) {``b.n(bArr,` `"bytes"``);``byte[] bArr2` `=` `this.mKey;``String` `str` `=` `this.mInitVector;``b.n(bArr2,` `"key"``);``b.n(``str``,` `"initVector"``);``SecretKeySpec secretKeySpec` `=` `new SecretKeySpec(bArr2,` `"AES"``);``byte[] bytes` `=` `str``.getBytes(a.f2878a);``b.m(bytes,` `"this as java.lang.String).getBytes(charset)"``);``IvParameterSpec ivParameterSpec` `=` `new IvParameterSpec(bytes);``Cipher cipher` `=` `Cipher.getInstance(``"AES/CBC/PKCS7Padding"``);``cipher.init(``2``, secretKeySpec, ivParameterSpec);``byte[] doFinal` `=` `cipher.doFinal(bArr, i6, i7` `-` `i6);``b.m(doFinal,` `"cipher.doFinal(cipherText, start, end - start)"``);``return` `Scription.d(doFinal);``}` `public final byte[] encrypt(byte[] bArr) {``b.n(bArr,` `"bytes"``);``byte[] bArr2` `=` `this.mKey;``String` `str` `=` `this.mInitVector;``b.n(bArr2,` `"key"``);``b.n(``str``,` `"initVector"``);``SecretKeySpec secretKeySpec` `=` `new SecretKeySpec(bArr2,` `"AES"``);``Cipher cipher` `=` `Cipher.getInstance(``"AES/CBC/PKCS7Padding"``);``byte[] bytes` `=` `str``.getBytes(a.f2878a);``b.m(bytes,` `"this as java.lang.String).getBytes(charset)"``);``cipher.init(``1``, secretKeySpec, new IvParameterSpec(bytes));``byte[] doFinal` `=` `cipher.doFinal(bArr);``b.m(doFinal,` `"cipher.doFinal(plainText)"``);``return` `doFinal;``}` |
|-|-|

真是得来全不费工夫，一下子找到关键代码了；

## 3.2 实施破解

这里使用frida是没办法hook住的，因为app启动就加载，而且是动态加载，因此放弃了这个方式，选择了一种非常笨重的办法：smali字节码插桩；
具体做法是在解密方法后插入一段smali的日志打印，让其将解密后的代码打印输出；
四、案例演示
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_E4T3YUCTS5VHG25.webp)
最终得到解密后的js源码，对其进行改动后放回对应目录，重新打开app后可以绕过激活校验；
 ![dex文件](https://bbs.kanxue.com/upload/attach/202508/1016214_XS9TKVTRDXP27YQ.webp)

# 四、总结

1，frida并不是可以一把梭（可能是我学艺不精），需要结合各种方式和工具一起用；
2，这个app加壳属于一代加壳，落地加载的方式；
3，理解原理很重要，比如安卓生命周期；基础不扎实很多东西没办法理解，思维有很大局限；

# 五、 参考资料

[安卓加固方案从落地加载到类指令抽取编写报告](https://bbs.kanxue.com/thread-261939.htm)
[正己的逆向课程](https://www.bilibili.com/video/BV1wT411N7sV/?spm_id_from=333.788.videopod.sections&amp;vd_source=5b697cc86fa59dcd62a5b45364301e05)
[Android从整体加固到抽取加固的实现及原理](https://bbs.kanxue.com/thread-286929.htm)
[豆包](https://www.doubao.com/)

---

# 回复

## 回复 by 正己 (#2)

*2025-8-20 20:28*

动态加载的dex也能hook，拿到classloader照样一把梭![image](https://bbs.kanxue.com/view/img/face/065.gif)

## 回复 by mb_kgaozkzb (#3)

*2025-8-26 19:14*

厉害了

## 回复 by wangwei实施 (#4)

*2025-8-26 20:01*

smali字节码插桩，好办法，直接打印出了解密后的js代码  很厉害

## 回复 by wx_ㅤ_683 (#5)

*2025-9-7 10:29*

为什么解密后还有很多地方是乱码

## 回复 by 咚咚汪 (#6)

*2025-10-26 22:26*

>
> [正己](https://bbs.kanxue.com/user-905183.htm)
>
>  动态加载的dex也能hook，拿到classloader照样一把梭[em_065]
>
>

看来我还没学到正己老师的精髓，还在用原始插桩的办法![image](https://bbs.kanxue.com/view/img/face/054.gif)

## 回复 by 咚咚汪 (#7)

*2025-10-26 22:26*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  wx_ㅤ_683](https://bbs.kanxue.com/user-948460.htm)
>
>  为什么解密后还有很多地方是乱码
>
>

还原后都是源码了，不会乱的 除非本身就是乱码

## 回复 by 咚咚汪 (#8)

*2025-10-26 22:27*

>
> [wangwei实施](https://bbs.kanxue.com/user-292827.htm)
>
>  smali字节码插桩，好办法，直接打印出了解密后的js代码 很厉害
>
>

实在是hook不出来才用插桩的本办法![image](https://bbs.kanxue.com/view/img/face/051.gif)

## 回复 by bhhqxhq (#9)

*2025-11-7 15:33*

这是aj9那个快照加密吗

## 回复 by 一条臭咸鱼 (#10)

*2025-12-2 20:52*

感谢大佬分享,又学到不少东西

## 回复 by 咚咚汪 (#11)

*2025-12-5 16:04*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  bhhqxhq](https://bbs.kanxue.com/user-1054899.htm)
>
>  这是aj9那个快照加密吗
>
>

不是快照的，那个快照是js字节码，相当于把js重新编译了一下，论坛有类似的话题，不过没有展开说是怎么讲字节码还原成源码的。感觉需要研究一下编译原理才能弄得明白！

## 回复 by 咚咚汪 (#12)

*2025-12-5 16:04*

>
> [一条臭咸鱼](https://bbs.kanxue.com/user-909934.htm)
>
>  感谢大佬分享,又学到不少东西
>
>

学起来![image](https://bbs.kanxue.com/view/img/face/062.gif)

## 回复 by wx_ㅤ_683 (#13)

*2025-12-5 16:38*

什么时候说一下快照还原![image](https://bbs.kanxue.com/view/img/face/058.gif)![image](https://bbs.kanxue.com/view/img/face/058.gif)

## 回复 by mb_oemwwmrl (#14)

*2025-12-5 17:28*

有用的
