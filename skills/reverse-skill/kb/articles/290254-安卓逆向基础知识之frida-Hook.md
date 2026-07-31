---
title: '[原创]安卓逆向基础知识之frida Hook'
url: https://bbs.kanxue.com/thread-290254.htm
tid: 290254
author: 黎明与黄昏
date: '2026-03-10'
tags: [Android安全, 原创, 基础理论, HOOK注入]
crawled_at: '2026-07-31T13:56:21+08:00'
replies: 8
---

frida是一款基于JS代码编写的Hook框架，它是一款易用的、可跨平台的Hook框架，介绍我就不多做介绍了，我们直接讲这玩意该怎么用。至于frida的环境配置之类的我就不多讲了，大家可以移步去看看正己大佬的讲解：

[《安卓逆向这档事》十三、是时候学习一下Frida一把梭了(上) - 吾爱破解 - 52pojie.cn](https://www.52pojie.cn/forum.php?mod=viewthread&amp;tid=1823118&amp;highlight=%B0%B2%D7%BF%C4%E6%CF%F2)

我们就直接步入正题，环境配置好后我们需要通过启动命令来注入hook脚本，这里提一个正己大佬没提到的启动命令：

| 1 | `frida` `-``U` `-``F` `-``l hook.js` |
|-|-|

当你觉得每次都要查看进程名麻烦时你可以通过-F代替进程名，因为-F是附加到前台应用，只需要将你要注入的APP处于最前端，然后将进程名替换为-F，这样就会附加到我们要注入的APP。
那么接下来我们开始编写hook代码，我们想要hook就必须拿到我们要hook的类，而要拿到要hook的类那就需要通过以下代码获取类：

| 1 | `Java.use(``"类名"``);` |
|-|-|

我们通过Java.use这个API得到要hook的类后，通过var xxx的方式定义一个变量xxx用于接收这个API执行之后的返回值，也就是接收这个API执行后返回的类。

当我们调用 Java.use("类名") 时必须包裹在 Java.perform() 中，Java.perform(function() { ... }) 是 Frida 中用于操作 Java 环境的核心桥梁，它可以确保使用APP正确的类加载器，Java.perform() 是 Frida 操作 Java 的安全沙箱，所有涉及 Java.use()、Java.choose()、Java.scheduleOnMainThread() 等 Java 相关操作，必须包裹在 Java.perform() 回调中。代码如下：

| 123 | `Java.perform(``function``() {``......``});` |
|-|-|

接下来我们可以将要hook的方法替换为自定义函数，我举个例子：

| 1234567 | `Java.perform(``function``() {``// 获取原始方法的引用（必须在 Hook 前保存）``const Map = Java.use(``"java.util.Map"``);``Map.put.implementation =` `function``(key, value) {``......``};``});` |
|-|-|

以上代码当中将 `java.util.Map` 的 put 方法替换为自定义函数是通过这段代码实现的。注意：`Map` 是接口，实际运行时调用的是实现类（如 `HashMap`）的方法，若需拦截所有 put 调用，建议同时 Hook 具体实现类，例如 `Java.use("java.util.HashMap")`。

| 123 | `Map.put.implementation =` `function``(key, value) {``......``};` |
|-|-|

因为这段代码是对 java.util.Map 的 put 方法进行hook，function(key, value)当中的key和value就是调用put方法所要传入的两个参数，put方法在开发使用的时候大概是这样的：

```
private Map<String, String> para;
this.para.put("username", userName);
this.para.put("userPwd", pwd);
```

可以见得一共两个参数，其中第一个参数为键，第二个参数为值。所以key就是表示put方法的第一个参数，value就是表示put方法的第二个参数，如果我们需要打印这两个参数的值，就可以通过console.log方法来打印参数的值。

当我们想要获取要hook方法的返回值，那就需要调用要hook的方法从而得到其返回值，我们可以通过this去引用当前的这个类，这样便可通过this.当前这个类下要hook的方法来调用要hook的方法从而得到其返回值，就像这样：

| 1234 | `Map.put.implementation =` `function` `(key, value) {``console.log(``"key:"``, key,` `"value:"``, value);``return` `this``.put(key, value);``}` |
|-|-|

要注意的是this.put(key, value);这里是调用的原函数，而不是修改后的函数，其实就是在调用原函数前加点东西，调用原函数后，得到返回值也可以加点东西打印打印返回值。而要修改参数和返回值也很简单，在调用原函数前给参数重新赋值，在最后的return返回一个新的返回值即可。

众所周知Java是有重载函数的，那么当我们使用frida进行hook重载函数时是不是就要告诉它我们要hook哪个重载函数？如此便需要添加以下代码来指定：

| 1 | `.overload(参数1类型, 参数2类型, 参数3类型……)` |
|-|-|

这段代码一般是像下面一样添加和使用：

| 123 | `MMKV.decodeString.overload(``'long'``,` `'java.lang.String'``,` `'java.lang.String'``).implementation =` `function` `(handle, key, defaultValue) {``……``}` |
|-|-|

如果我们想要hook所有的重载函数该怎么样实现呢？其实也差不多，只不过将overload换成overloads而已，大致实现如下：

| 123456 | `var` `ClassName = Java.use(``"类名"``);``for``(``var` `i = 0; i < ClassName.MethodName.overloads.length; i++){``ClassName.MethodName.overloads[i].implementation =` `function``(){``// ... 具体实现``}``}` |
|-|-|

因为ClassName.MethodName.overloads是一个数组，包含了方法的所有重载版本。所以我们可以通过遍历这个数组，可以对每个重载版本进行 Hook。但你会发现function()当中是没有参数的，因为在js当中是没有可变的参数，所以其实需要在具体实现中去判断参数的个数和参数的类型，那这就需要引出arguments了，arguments是js内置的类数组对象，它包含了函数调用时传入的所有参数。如此我们便需要通过 arguments.length 判断方法调用时传入的参数个数，再根据参数个数进行对应的处理。

当我们遇到构造函数该如何hook呢？其实很简单，与Hook普通方法相比无非是方法名的改变，区别是通过$init来表示构造函数的。

| 123456 | `Java.perform(``function``() {``var` `ClassName = Java.use(``"类名"``);``ClassName.$init.implementation =` `function``(参数……) {``......``};``});` |
|-|-|

当然如果构造函数有多个，那么我们就得添加overload来指定我们要hook哪个重载的构造函数。会了如何hook构造函数那自然少不了如何通过hook进行实例化对象，要实例化对象需要用到$new()，用法如下：

| 123 | `var` `ClassName = Java.use(``"类名"``);``var` `newClass = ClassName.$``new``(初始化参数……);``var` `Method = newClass.对象方法();` |
|-|-|

因为这是实例化对象，所以我们进行实例化后还可以调用该对象下的方法。

我们除此之外还可以主动调用某个方法，想要主动调用也十分的简单，如果是主动调用静态方法需要先通过Java.use() 获取目标类的包装对象，这个对象代表 Java 类本身，然后通过类对象直接调用静态方法，这里无需创建实例是因为静态方法属于类本身，代码如下：

| 12 | `var` `ClassName = Java.use(``"目标类名"``);` `ClassName.方法名(``"传参"``);` |
|-|-|

参数传递是直接传递参数到方法调用，Frida 会自动处理 Java和JS 之间类型的转换。

而我们如果要主动调用非静态方法首先我们得知道Java 对象在堆内存中存在，每个对象是类的实例，非静态方法需要通过对象实例调用，这样我们便能理解主动调用非静态方法需要通过Java.choose在 Java 堆中扫描指定类的活动实例，参数为要查找的完整类名。

| 123 | `Java.choose(``"需要hook的类"``, {``// ...``});` |
|-|-|

每找到一个匹配实例后都会调用一次下面的代码，参数instance为找到的 Java 对象实例，调用方法可以通过instance.方法名("传参")在实例上调用非静态方法并传递参数，最后将返回值赋给 ret。

| 123 | `onMatch:` `function``(instance) {``var` `ret = instance.方法名(``"传参"``);``}` |
|-|-|

在所有实例处理完成后会调用以下代码，它会执行清理操作、处理最终结果、通知扫描完成。

| 123 | `onComplete:` `function``() {``……``}` |
|-|-|

完整的主动调用非静态方法如下：

| 12345678 | `Java.choose(``"需要hook的类"``, {``onMatch:` `function``(instance) {``var` `ret = instance.方法名(``"传参"``);``},``onComplete:` `function``() {``……``}``});` |
|-|-|

除了这种在 Java 堆中扫描指定类的活动实例外还有一种方法可以主动调用非静态方法，那就是新建一个实例对象去调用。这两种有什么区别呢？前面提到了上面那种主动调用非静态方法需要Java对象存在于堆内存当中，不然在堆内存中找不到Java对象，那自然也无法主动调用都没有实例化的Java对象，而下面这种方式就是我们主动实例化对象，得到对象后再主动调用对象下的方法。

| 12 | `var` `ClassName = Java.use(``"目标类名"``);` `ClassName.$``new``(``"实例化对象参数"``).方法名(``"传参"``);` |
|-|-|

这种方式和主动调用静态方法区别不大，也就多了个实例化对象的过程罢了。

现在我们学会了如何主动调用Java层的静态方法和非静态方法，这个方法也适用于调用静态native方法和非静态native方法，而主动调用so层方法待到下面讲so层hook时再讲。

接下来我们就开始讲如何hook静态字段与非静态字段，静态字段hook起来十分的容易，可以通过以下代码实现：

| 123 | `var` `ClassName = Java.use(``"类名"``);``// 可以通过ClassName.staticFieldName.value来获取静态字段的值``ClassName.staticFieldName.value =` `"静态字段要修改的值"``;` |
|-|-|

hook静态字段中frida其实是把ClassName.staticFieldName封装成了一个对象，我们要获取或者修改其值需要通过对象下的value实现。非静态字段的hook也非常简单，如下面所示：

| 12345678910111213141516 | `// 使用 Java.choose 方法在 Java 堆中查找指定类的实例``Java.choose(``"类名"``, {``// 当找到匹配的实例时调用此函数``onMatch:` `function``(obj) {``// 输出实例中名为 FieldName 的字段当前值``console.log(obj.FieldName.value);``// 将实例中名为 FieldName 的字段值设置为 9999``obj.FieldName.value = 9999;``// 当字段名和函数名重复的时候将实例中名为FieldName2的字段值设置为123456``obj._FieldName2.value = 123456;``},``// 当查找完成时调用此函数``onComplete:` `function``() {``// 查找完成后执行的操作``}``});` |
|-|-|

我们现在对静态字段和非静态字段的hook都学会了，只不过还有一个情况需要注意，那就是当字段名和函数名重复的时候，这就需要在我们要hook的字段名前面加个下划线，就像这种情况：

| 1234567 | `public class Demo {``private String name;` `public String name() {``return` `"要hook字段name需要通过._name来实现"``;``}``}` |
|-|-|

接下来我们就讲解如何hook内部类和匿名类，这里再提一下什么是内部类，什么是匿名类，其实匿名类也是内部类的一种，又称匿名内部类，内部类其实就是在一个类里面再定义一个类，内部类可以访问其外部类的所有成员，包括私有成员。而我们要hook内部类和匿名类也非常简单，只需要用到$即可，如下所示：

| 123456789101112131415161718 | `Java.perform(``function``() {``// 获取内部类的引用``var` `ClassName = Java.use(``"类名$内部类名"``);` `// Hook 构造函数``ClassName.$init.implementation =` `function``() {``console.log(``"构造函数被调用"``);``// 调用原始构造函数``this``.$init();``};` `// Hook 普通方法``ClassName.methodname.implementation =` `function``() {``console.log(``"普通方法被调用"``);``// 调用原始方法``return` `this``.methodname();``};``});` |
|-|-|

而匿名类和内部类是差不多的，但匿名类是没有名字的，这就导致匿名类的类名表达方式和smali中的一致。我们举个例子：

| 12345678910 | `public class Test {``public static void main(String[] args) {``Animal animal =` `new` `Animal() {``@Override``public void move() {``System.out.println(``"我是匿名类的move方法"``);``}``};``}``}` |
|-|-|

当执行 new Animal() { ... } 时，实际上是在运行时创建了一个继承自 Animal 类的匿名子类。这个匿名子类没有显式的类名，其类名由编译器自动生成，通常类似于 TestTest1，这个Test1，这个Test1就表示Test类中的第一个匿名类，Test$2就表示Test类中的第二个匿名类，以此类推。

接下来就继续讲如何枚举所有的类与类的所有方法，frida提供了一个API可以同步枚举所有已经加载的类，这里的同步就是等把所有已经加载的类都枚举出来再将结果返回，得到返回值后才能继续往下执行代码；既然有同步那自然少不了异步，但在这之前我们先讲讲同步怎么实现：

| 1234567891011121314151617181920212223 | `// 枚举所有已加载的 Java 类``var` `classes = Java.enumerateLoadedClassesSync();` `// 遍历所有已加载的类``for` `(``var` `i = 0; i < classes.length; i++) {``// 检查类名是否包含 "包名"，一般用于过滤掉系统类和第三方类，当然也可以不过滤，但会有很多已经加载的类，看起来比较费劲。``if` `(classes[i].indexOf(``"包名"``) != -1) {``// 输出匹配的类名``console.log(classes[i]);` `// 获取类的引用``var` `clazz = Java.use(classes[i]);` `// 获取类的所有声明方法``var` `methods = clazz.class.getDeclaredMethods();` `// 遍历所有方法``for` `(``var` `j = 0; j < methods.length; j++) {``// 输出方法信息``console.log(methods[j]);``}``}``}` |
|-|-|

可以看到在代码中使用到了Java的反射，先通过Java.use获取类的引用，然后代码中通过.class的方式获取类的class对象，有了类的class对象就可以调用下属的一些方法，代码中获取类的class对象的方法其实就是Java中通过类名.class来获取类的class对象是一致的，这里在获取到类的class对象后便调用了Java反射中的getDeclaredMethods方法得到类的全部成员方法。反射在hook当中还是很重要的，这些反射的方法我就不额外提了，有兴趣的可以自己去看看。

前面提到了还有异步枚举所有已经加载的类，以下代码可以实现：

| 123456789101112131415161718192021222324252627282930 | `// 异步枚举已加载的 Java 类``Java.enumerateLoadedClasses({``// 当找到匹配的类时调用此函数``onMatch:` `function``(name, handle) {``// 检查类名是否包含 "包名"``if` `(name.indexOf(``"包名"``) != -1) {``// 输出类名``console.log(name);` `// 获取类的引用``var` `clazz = Java.use(name);` `// 输出类的引用信息``console.log(clazz);` `// 获取类的所有声明方法``var` `methods = clazz.class.getDeclaredMethods();` `// 遍历所有方法``for` `(``var` `i = 0; i < methods.length; i++) {``// 输出方法信息``console.log(methods[i]);``}``}``},``// 当枚举完成时调用此函数``onComplete:` `function``() {``// 枚举完成后执行的操作，这里留空``}``});` |
|-|-|

可以看到代码的作用是异步枚举当前进程中已加载的所有 Java 类，筛选出指定包名下的类，并输出这些类的详细信息和所有声明方法的信息。这个和前面hook非静态字段一样都是通过这两个回调函数实现的，onMatch就是每枚举到一个类时就会将类的名字传入到onMatch: 后的函数并执行，而另外一个参数handle是类的句柄。

学会了如何实现枚举和Java中的反射，那我们就可以实现枚举所有方法并进行hook，代码如下：

| 1234567891011121314151617181920212223242526272829303132333435363738 | `// 定义 hookAll 函数，用于 Hook 指定类的指定方法的所有重载版本``function` `hookAll(mmkv, methodName) {``// 遍历方法的所有重载版本``for` `(``var` `k = 0; k < mmkv[methodName].overloads.length; k++) {``// 用局部变量保存当前重载，避免闭包中 k 被循环覆盖``var` `overload = mmkv[methodName].overloads[k];``overload.implementation =` `function``() {``// 遍历方法的所有参数并输出``for` `(``var` `i = 0; i < arguments.length; i++) {``console.log(``"参数"` `+ i +` `": "` `+ arguments[i]);``}``// 输出方法名``console.log(``"方法名称："` `+ methodName);``// 调用当前重载的原始方法并返回结果（必须用同一 overload，不能用 this[methodName]）``return` `overload.apply(``this``, arguments);``}``}``}` `function` `main() {``// 在 Java 环境中执行``Java.perform(``function``() {``// 获取指定类的引用``var` `mmkv = Java.use(``"com.tencent.mmkv.MMKV"``);` `// 获取类的所有声明方法``var` `methods = mmkv.class.getDeclaredMethods();` `// 遍历所有方法``for` `(``var` `j = 0; j < methods.length; j++) {``// 获取方法名``var` `methodName = methods[j].getName();` `// 调用 hookAll 函数对方法进行 Hook``hookAll(mmkv, methodName);``}``});``}` |
|-|-|

代码中可以看到有mmkv[methodName]等的代码，这个其实就是mmkv.methodName，但因为直接.methodName这种方式methodName是标识符，如果是mmkv.方法名称那么该方法名称就必须出现在js代码中，而mmkv[methodName]方式方法名称是一个字符串，这是不需要出现在js代码中，也就可以从methodName这个变量中取出方法名称字符串来实现hook。

我们有时候会遇到动态加载的dex，遇到这种情况前面的hook方式是会找不到类的引用的，实现动态加载dex有基于 PathClassLoader 和 DexClassLoader，也有基于插件化框架实现的，还有基于热修复框架实现的，还有一种是基于动态代理 + Instrumentation来实现的。

第一种动态加载dex实现是基于Android 系统提供了 ClassLoader 的两个子类，PathClassLoader 和 DexClassLoader 来加载 dex 文件。其中PathClassLoader 主要用于加载已经安装应用的 dex 文件， 而 DexClassLoader 可以加载指定路径下的 dex、jar、apk 文件，并生成对应的 DexFile 对象，进而加载其中的类。其核心原理是通过 ClassLoader 的 findClass 方法去寻找并加载类。当调用 DexClassLoader.loadClass 时，它会先检查缓存，如果缓存中没有，就会去指定路径下的 dex 文件中查找对应的类字节码，然后通过 JNI 调用系统方法将字节码转化为可执行的形式，加载到内存中。

如果是开发者大概会这样实现动态加载的dex：

| 123456789101112 | `// 假设 dex 文件路径为 /data/data/your.package.name/app_dex/my_dex.dex``String dexPath =` `"/data/data/your.package.name/app_dex/my_dex.dex"``;``String optimizedDirectory = getDir(``"dex"``, Context.MODE_PRIVATE).getAbsolutePath();``DexClassLoader classLoader =` `new` `DexClassLoader(dexPath, optimizedDirectory,` `null``, getClassLoader());``try` `{``Class<?> clazz = classLoader.loadClass(``"com.example.dynamic.MyDynamicClass"``);``// 反射调用类中的方法``Method method = clazz.getMethod(``"dynamicMethod"``);``method.invoke(clazz.newInstance());``}` `catch` `(Exception e) {``e.printStackTrace();``}` |
|-|-|

以上仅为示例，这种实现相对简单，是 Android 官方提供的方式，兼容性较好。但在 Android 5.0 之后，为了安全性，引入了 ART 运行时，直接使用 DexClassLoader 加载的 dex 文件不能直接运行，需要进行 dex 合并（multidex 机制），操作相对复杂；并且在加载 dex 时，对 dex 文件的合法性校验比较严格。

第二种是会先通过RePlugin自定义一个 ClassLoader，通过代理机制，在加载类时，优先从插件的 dex 文件中查找类。如果找不到，再委托给系统的 ClassLoader 去加载。因为插件中的资源（如布局、图片等）也需要进行管理。所以RePlugin 会通过 Hook 系统的资源加载机制，将插件的资源与宿主应用的资源进行整合，这样便使得插件能够正确地使用和显示资源。为了让插件能够像正常的 Android 组件一样运行，需要 Hook 一些系统方法，例如 ActivityManagerService 相关方法，在启动插件的 Activity 时，能够欺骗系统，让系统认为是在启动宿主应用内的正常组件。

这种方式首先引入 RePlugin 的依赖，然后在应用中进行初始化：

| 1 | `RePlugin.init(``this``);` |
|-|-|

初始化完后需要加载插件并启动插件中的 Activity：

| 123 | `RePlugin.preload(``"my_plugin"``);` `// 预加载插件``Intent intent = RePlugin.createIntent(``"my_plugin"``,` `"com.example.plugin.MyPluginActivity"``);``startActivity(intent);` |
|-|-|

这种方式从开发的角度上来讲可以实现真正意义上的插件化，能够动态加载并运行插件中的组件，包括 Activity、Service 等；支持插件的热更新，对应用的功能扩展和维护非常方便。但是框架相对复杂，接入成本较高；由于大量使用 Hook 技术，可能会存在兼容性问题，特别是在一些定制化的 Android 系统上。

第三种热修复框架其原理是先dex 差量修复，Tinker 会对比应用的旧版本和新版本的 dex 文件，生成一个差量包（patch.dex）。在应用运行时，将这个差量包与应用已有的 dex 文件进行合并，生成一个完整的可运行的 dex 文件。然后类加载替换通过自定义 ClassLoader，优先加载修复后的类，从而实现对应用中存在问题的类进行修复。最后资源修复，对于资源的修复，Tinker 会通过资源映射表等方式，将修复后的资源与应用原有的资源进行整合，保证资源的正确使用。

这种方式在接入 Tinker 框架后，在构建时，会生成差量包。在应用中，当检测到有修复包时，进行加载：

| 1 | `TinkerInstaller.install(``this``);` |
|-|-|

这种方式从开发者的角度来说优点有可以快速修复应用中的 Bug，不需要用户重新下载完整的应用安装包；对应用的性能影响相对较小，因为只需要合并差量包。不过缺点也有，对应用的侵入性较大，需要在构建阶段进行较多的配置；在一些复杂的场景下，如多 dex 情况、资源冲突等，修复的成功率可能会受到影响。

最后一种动态代理 + Instrumentation实现的原理是自定义一个 Instrumentation 的子类，通过反射将系统默认的 Instrumentation 替换为自定义的。在自定义的 Instrumentation 中，重写启动 Activity 等方法。当加载动态 dex 文件中的 Activity 时，通过动态代理等方式，将 Activity 的生命周期方法等转发到实际的插件 Activity 中，从而实现插件 Activity 的正常运行。最后对于类的加载，同样可以结合自定义的 ClassLoader 来实现从动态 dex 文件中加载类。

我们来看一段这种方法的实现示例代码：

| 12345678910111213141516171819202122232425 | `// 自定义 Instrumentation``public class MyInstrumentation extends Instrumentation {``// 重写相关方法，如启动 Activity 方法``@Override``public ActivityResult execStartActivity(``Context who, IBinder contextThread, IBinder token, Activity target,``Intent intent, int requestCode, Bundle options) {``// 处理启动插件 Activity 的逻辑``return` `super``.execStartActivity(who, contextThread, token, target, intent, requestCode, options);``}``}``// 在 Application 中替换 Instrumentation``public class MyApplication extends Application {``@Override``public void onCreate() {``super``.onCreate();``try` `{``Field field = ActivityThread.class.getDeclaredField(``"mInstrumentation"``);``field.setAccessible(``true``);``field.set(ActivityThread.currentActivityThread(),` `new` `MyInstrumentation());``}` `catch` `(Exception e) {``e.printStackTrace();``}``}``}` |
|-|-|

这种方式可以灵活地控制应用组件的启动和运行，对应用的侵入性相对较小。但对于开发者来说需要深入理解 Android 系统的组件启动流程和 Instrumentation 的工作原理，实现难度较大；并且在一些系统版本上可能会因为系统的变化导致兼容性问题。

市面上常见的是这四种动态加载dex的方式，那下面就讲讲如何hook动态加载dex，这是其中一种方式：

| 1234567891011121314151617181920212223242526272829303132333435 | `// Hook 动态加载的 dex 文件中的类和方法``function` `hookDex() {``Java.perform(``function``() {``// 枚举所有类加载器``Java.enumerateClassLoaders({``// 当找到匹配的类加载器时调用此函数``onMatch:` `function``(loader) {``try` `{``// 检查类加载器是否可以加载指定的类``if` `(loader.loadClass(``"动态加载的dex下的类名"``)) {``// 设置当前类加载器``Java.classFactory.loader = loader;` `// 获取指定类的引用``var` `clazz = Java.use(``"动态加载的dex下的类名"``);` `// 输出类的引用信息``console.log(clazz);` `// Hook 类中的 methodname 方法``clazz.methodname.implementation =` `function``() {``// hook成功后执行的操作，这里留空``}``}``}` `catch` `(error) {``// 捕获并忽略异常``}``},``// 当枚举完成时调用此函数``onComplete:` `function``() {``// 枚举完成后执行的操作，这里留空``}``});``});``}` |
|-|-|

这段代码的主要功能是 Hook 动态加载的 dex 文件中的类和方法。代码中使用了Java.enumerateClassLoaders来枚举所有类加载器，它可以枚举当前进程中的所有类加载器。onMatch 回调函数当每找到一个类加载器时，调用函数，其中loader是类加载器对象。函数中 `loader.loadClass("类名")` 会尝试用该加载器加载指定类：**若能加载则返回 Class 对象**（在 if 中为真），**若不能加载则会抛出 ClassNotFoundException**，被外层的 try/catch 捕获并忽略。当某个加载器能成功加载目标类时，先执行 `Java.classFactory.loader = loader`，该代码用于设置当前类加载器，这样做可以确保后续的类加载操作使用此加载器，原因是因为加载同一个类不仅要类的路径和类名相同还要是同一个类加载器进行加载的，不然就算是类的路径和类名相同但类加载器不同也不是同一个类。

只不过动态加载在开发中一般常用于加固，所以动态加载也常见于加固，加固的话直接脱壳就好了，所以hook动态加载的dex下的类也就没那么常见了。关于动态加载dex的hook如果大家有兴趣可以自己去看看这两篇，或许有所帮助。

[[原创]进阶Frida--Android逆向之动态加载dex Hook（三）（上篇）-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-229597.htm)

[[原创]进阶Frida--Android逆向之动态加载dex Hook（三）（下篇）-Android安全-看雪-安全社区|安全招聘|kanxue.com](https://bbs.kanxue.com/thread-229657.htm)

动态加载dex讲完了，下面我们就讲讲当我们遇到那些特殊类该如何进行hook，举个例子：

| 1234567891011121314151617 | `public static void onWakeMap(Map map) {``try` `{``Object obj = map.get(``"2"``);``int i = -1;``if` `(obj !=` `null``) {``i = ((Integer) obj).intValue();``}``onWake(i);``Object obj2 = map.get(``"1"``);``Context context =` `null``;``if` `(obj2 !=` `null``) {``context = (Context) obj2;``}``onWake(context, i);``}` `catch` `(Throwable unused) {``}``}` |
|-|-|

就比如这个方法的参数是Map，那我们遇到了这种参数如何打印或修改其参数与返回值，如果要 Hook 这种参数或返回值为特殊类型（如 Map、HashMap、Context等）的方法，需要结合 Java 反射 和 Frida 的 Java 层 API。

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `function` `hookOnWakeMap() {``Java.perform(``function``() {``// 获取目标类``const TargetClass = Java.use(``'com.xiaojianbang.app.YourClassName'``);` `// Hook onWakeMap 方法``TargetClass.onWakeMap.implementation =` `function``(map) {``console.log(``'[+] 进入 onWakeMap 方法'``);` `// 打印原始参数（Map）``console.log(``'[参数 Map]'``);``// entrySet()：获取 Map 的键值对集合。``const entrySet = map.entrySet();``// iterator是一个迭代器``const iterator = entrySet.iterator();``while` `(iterator.hasNext()) {``const entry = iterator.next();``console.log(`  Key: ${entry.getKey()}, Value: ${entry.getValue()}`);``}` `// 修改参数（示例：修改键 "2" 的值为 999）``const Integer = Java.use(``'java.lang.Integer'``);``map.put(``'2'``, Integer.$``new``(999));``console.log(``'[修改后] 参数 Map:'``);``const modifiedEntrySet = map.entrySet();``const modifiedIterator = modifiedEntrySet.iterator();``while` `(modifiedIterator.hasNext()) {``const entry = modifiedIterator.next();``console.log(`  Key: ${entry.getKey()}, Value: ${entry.getValue()}`);``}` `// 调用原始方法（注意：如果方法有返回值，需接收并处理）``this``.onWakeMap(map);` `// 由于原方法返回值为 void，无需处理返回值``console.log(``'[+] onWakeMap 方法执行完成'``);``};``});``}` `// 启动 Hook``setImmediate(hookOnWakeMap);` |
|-|-|

在frida的js代码中如果当我们得到Java的类型我们可以调用该Java类下的方法，你看代码中的map.entrySet();这个entrySet方法既不是frida的API也不是js的方法，而是Java中Map类下的entrySet方法，所以当我们遇到特殊类型的参数时是可以调用该类下的方法的。

现在我们需要知道几个比较好用也比较常用的方法，第一个就是通过hook获取调用堆栈，网上如何通过获取调用堆栈的方式方法很多，我这只是我列举出来的几种方式。

第一种是适用于Java层的获取调用堆栈，这种方式其实就是通过前面讲的主动调用去实现的。

| 1234567 | `function` `printStackTrace() {``// 获取 Java 层调用堆栈（更适合 Java 方法）``const stackTrace = Java.use(``"android.util.Log"``).getStackTraceString(``Java.use(``"java.lang.Throwable"``).$``new``()``);``console.log(``'Java 调用堆栈:\n'` `+ stackTrace);``}` |
|-|-|

可以看到先通过Java.use("android.util.Log")获取 Android 系统日志工具类Log的引用，然后调用Log类下的getStackTraceString方法，该方法可以生成可读性强的堆栈信息。

该方法需要传入一个java.lang.Throwable实例作为参数 ，这里通过Java.use("java.lang.Throwable").$new()创建了一个新的异常实例，其内部会自动记录当前的调用栈信息，最后getStackTraceString方法会将这个异常包含的调用栈转换为字符串返回，从而得到我们所需的 Java 层调用堆栈详情。

既然Java层可以打印调用栈信息，那么so层自然也可以，以下代码的作用是打印so层调用栈：

| 1234567891011121314151617 | `Interceptor.attach(funcAddr, {``onEnter:` `function``(args) {``……` `// 打印调用栈``console.log(``"[调用栈] 开始:"``);``// 获取当前线程调用栈（最多取10层，避免过长）``let backtrace = Thread.backtrace(``this``.context, Backtracer.ACCURATE).slice(0, 10);``backtrace.forEach((addr, index) => {``// 解析地址对应的符号（函数名+库名）``let symbol = DebugSymbol.fromAddress(addr) \|\|` `"未知符号"``;``console.log(`  [${index}] 地址: ${addr} -> 符号: ${symbol}`);``});``console.log(``"[调用栈] 结束\n"``);``},``onLeave:` `function``(retval) {``}``});` |
|-|-|

可以看到打印so层调用堆栈的核心是Thread.backtrace() 函数，在Frida的onEnter中，this.context包含了CPU寄存器的完整快照，这些寄存器保存了当前线程的执行状态，Backtracer.ACCURATE 模式通过栈帧指针遍历调用链。

第二种就是hook系统函数，当APP种的方法名被混淆的时候会对我们的hook增加不小的难度，这时我们就可以hook系统函数来帮助我们对抗混淆，毕竟系统函数并不会受到影响，除非它不使用系统函数而是使用自己实现的函数。比如说某个APP将加密前的键值对压入到了 HashMap 中，那我们就可以通过 hook **HashMap 的 put 方法**来获取到压入的键值对；put 是系统 API，就算 APP 混淆了，只要调用了该方法，我们就可以直接 hook 该方法获取压入的键值对而不受影响。

| 1234567891011121314151617 | `function` `hookMapPut() {``Java.perform(``function``() {``const HashMap = Java.use(``"java.util.HashMap"``);``// 处理 put 方法的重载（需指定参数类型）``HashMap.put.overload(``"java.lang.Object"``,` `"java.lang.Object"``).implementation =` `function``(key, value) {``// 严格判断 key 是否为目标字符串（避免类型误判）``if` `(key ==` `"username"` `\|\| key ==` `"userPwd"``) {``console.log(``"Map Key: "``, key);``console.log(``"Map Value: "``, value);``// 调用修正后的堆栈打印函数``printStackTrace();``}``// 调用原始方法``return` `this``.put(key, value);``};``});``}` |
|-|-|

以上是一个示例，hook系统函数是一个比较好用也比较常用的方法，大家可以去多试试，以下是一些经常进行hook的系统函数：

#### 1. 集合操作类

- **`java.util.Map put`**
	- 作用：向`Map`接口的实现类（如`HashMap`、`ConcurrentHashMap`）中添加键值对（`key-value`）。
	- 场景：APP 存储配置、缓存数据、参数传递时常用。
	- Hook 意义：监控敏感数据存储（如加密密钥、用户 token）。
- **`java.util.HashMap put`**
	- 作用：`HashMap`的具体`put`实现（线程不安全，效率高），底层用哈希表存储。
	- 场景：单线程环境下的键值对存储（如本地缓存）。
- **`java.util.concurrent.ConcurrentHashMap put`**
	- 作用：线程安全的`HashMap`实现，多线程环境下保证原子性。
	- 场景：多线程 APP（如后台服务、并发网络请求）的共享数据存储。
- **`java.util.ArrayList add`**
	- 作用：向动态数组`ArrayList`中添加元素（底层基于数组，支持随机访问）。
	- 场景：存储有序列表（如接口返回的数据集、临时任务队列）。

#### 2. 字符串与 JSON 操作类

- **`java.lang.StringBuilder append/toString`**
	- 作用：`append`拼接字符串（可变字符序列，效率高于`String`拼接）；`toString`返回最终字符串。
	- 场景：日志输出、数据拼接（如 URL 拼接、JSON 构造）。
	- Hook 意义：监控敏感字符串拼接（如拼接加密参数、URL 中的 token）。
- **`android.util.Pair.$init()`**
	- 作用：`Pair`类的构造方法，创建 “键值对” 对象（存储两个元素，如`Pair<String, Integer>`）。
	- 场景：简化的键值对传递（如方法返回两个结果、轻量级数据封装）。
- **`org.json.JSONObject.$init()`**
	- 作用：`JSONObject`的构造方法，初始化 JSON 对象（解析 / 生成 JSON 数据）。
	- 场景：APP 与服务端通信（JSON 是主流数据格式）、本地数据持久化。

#### 3. 工具类与基础类型

- **`java.util.Arrays toString/sort`**
	- 作用：`toString`将数组转为字符串（方便打印调试）；`sort`对数组排序（默认升序）。
	- 场景：数据调试、算法实现（如排序算法封装）。
- **`java.net.URLEncoder`**
	- 作用：对字符串进行**URL 编码**（将特殊字符转为`%XX`格式，如空格转`%20`）。
	- 场景：构造 URL 参数（如`?name=张三`需编码为`?name=%E5%BC%A0%E5%BC%82`）。
	- Hook 意义：监控 URL 中的敏感参数（如加密后的请求参数）。
- **`String`**
	- 作用：字符串操作的核心类（构造、拼接、截取、匹配等）。
	- 场景：所有涉及字符串的逻辑（如加密输入、日志输出、接口参数）。

#### 4. 反射与动态加载类

- **`java.lang.Class forName`**
	- 作用：通过类名字符串获取`Class`对象（反射的入口）。
	- Hook 意义：监控 APP 动态加载类（如加固壳解密后加载 Dex、反射调用私有方法）。
- **`java.lang.reflect.Method invoke`**
	- 作用：通过反射调用方法（可突破访问权限，如调用私有方法）。
	- Hook 意义：拦截敏感方法调用（如加密函数、验签函数）。

#### 5. 加密与安全类

- **`java.security.MessageDigest getInstance`**
	- 作用：获取哈希算法实例（如`MD5`、`SHA-1`、`SHA-256`）。
	- Hook 意义：监控数据哈希（如密码哈希、数据完整性校验）。
- **`javax.crypto.Cipher getInstance/doFinal`**
	- 作用：获取加密 / 解密器（如 AES、RSA）；`doFinal`执行加密 / 解密。
	- Hook 意义：拦截加密密钥、明文 / 密文数据（如 APP 与服务端的加密通信）。

#### 6. 网络与 IO 操作类

- **`java.net.HttpURLConnection connect`**
	- 作用：发起 HTTP 请求（建立连接）。
	- Hook 意义：监控网络请求（URL、参数、 headers）。
- **`okhttp3.OkHttpClient newCall`**
	- 作用：创建 OKHttp 请求（主流网络库，替代`HttpURLConnection`）。
	- Hook 意义：拦截 OKHttp 的请求 / 响应（如加密接口的请求参数）。
- **`java.io.FileInputStream read`**
	- 作用：读取文件数据（字节流）。
	- Hook 意义：监控敏感文件读取（如密钥文件、配置文件）。

#### 7. 线程与并发类

- **`java.lang.Runnable run`**
	- 作用：线程任务的入口方法（`Thread`或线程池执行的逻辑）。
	- Hook 意义：拦截后台线程逻辑（如异步加密、恶意代码执行）。
- **`java.util.concurrent.ExecutorService submit`**
	- 作用：向线程池提交任务（异步执行）。
	- Hook 意义：监控 APP 的并发任务（如批量加密、后台解密）。

#### 8. 系统与反射类

- **`java.lang.System loadLibrary`**
	- 作用：加载 Native 库（`.so`文件）。
	- Hook 意义：监控敏感 Native 库加载（如加固壳、反调试库）。
- **`dalvik.system.DexClassLoader loadClass`**
	- 作用：动态加载 Dex 文件并获取类（用于热更新、加固）。
	- Hook 意义：拦截动态代码加载（如解密后的 Dex 加载）。

第三种是协议头当中有的参数可能是启动的时候生成一次，但一般来说带有时间戳的参数是每次执行都会生成的。首先我们要明白时间戳是为了防止重复发送相同请求，若时间戳固定，攻击者可无限复用旧请求；若每次请求生成新时间戳，服务端可通过 “时间窗口验证”。

第四种是接触的比较少的，app有时需要判断页面是H5还是原生页面，要进行判断有很多方式可以判断，首先可以点击手机 设置 -> 开发者选项 -> 开启 “显示布局边界” ，如果是屏幕上有密密麻麻、细小的布局框，每个按钮、每段文字都有自己的边界，那这就是原生页面的特征，而H5页面特征则是整个屏幕或被一个巨大的绿色框框住，框内细节很少。

还可以开启 飞行模式 后打开 App 页面。显示404错误、网络异常或加载失败的页面就是H5页面，内容依然存在（如缓存、设置页）或显示 App 自带的静态占位图那就是原生页面。

还可以看加载进度条，仔细观察打开新页面时，顶部导航栏的位置，页面顶部常常会出现一条进度条，表示网页正在加载那就是H5页面，页面切换是“即点即开”的，没有加载进度条，除了下拉刷新那就是原生页面。

还可以在页面的文字或图片上长按，通常会出现系统自带的菜单，如“复制”、“粘贴”、“分享图片”等选项那就是H5 页面，如果长按后无任何反应，或触发 App 自定义的交互那就是原生页面。

可以尝试进入一个深层级页面后，看左上角的返回按钮。返回按钮旁边经常会出现一个 “关闭”或“X”按钮，用于直接退出网页 那就是H5 页面，如果通常只有一个返回箭头，没有多余的关闭选项那就是原生页面。

可以在下拉刷新的页面快速下拉，如果页面内容会有一个明显的“闪白”和重新渲染的过程，感觉像是整个网页刷新了那就是H5页面，刷新动画比较平滑，一般只出现原生的刷新头，页面内容不会“闪白”那就是原生页面。

可以在页面上下拉到底部或进行特定手势，有时下拉到底部会显示网页的版权信息或网址提供方，而app原生页面则不会出现任何与网址相关的信息。

如果以上方法还不能确认是不是H5页面，那将 APK 文件后缀改为 .zip 并解压，重点关注 assets 和 res资源文件夹，如果看到大量的 .html、.js、.css 文件，或者包含 cordova.js、ionic 等特定框架的文件，这几乎可以肯定是混合应用 。有时 H5 资源会被打包成离线包，逻辑类似。还可以使用Jadx等工具反编译 APK，在代码中搜索 WebView、WebChromeClient、WebViewClient 等类。如果 App 的代码中大量使用 WebView 来加载网址或本地文件，并且存在 JsBridge 相关的接口，那么它就是典型的混合应用 。

使用frida对Java层进行hook我们已经会了，那么接下来我们也该学习学习frida对so层的hook了。一般来说要完成对so层的函数进行hook首先要获取函数的地址，众所周知so层函数的地址是由so文件的基址加上函数在so文件中的偏移进行计算得到的。

我们可以通过Module类的findBaseAddress方法直接获取指定so文件的基址，再通过add方法进行基址+偏移的计算得到目标函数地址。

| 12 | `var` `ress = Module.findBaseAddress(``"libxxx.so"``);``var` `funcAddr = ress.add(0x166C);` |
|-|-|

前面提到过Thumb指令集进行hook时地址是需要加一的，而arm指令集则不需要，所以当指令集为Thumb或Thumb2指令集时我们写hook代码时的add方法中的偏移地址是要加一的！

得到so层函数的地址后我们就可以通过Interceptor.attach() 直接附加到内存中的 Native 函数，Interceptor.attach() 需要传两个参数，第一个参数便是我们so层函数的地址，第二个参数是一个对象，这个对象中有几个回调函数，Interceptor.attach() 完整语法如下：

| 1234567891011 | `Interceptor.attach(``funcAddr,` `// 参数1：要挂钩的 Native 函数在内存中的地址``{` `// 参数2：钩子配置对象（包含 onEnter 和 onLeave 两个回调）``onEnter:` `function``(args) {` `// 函数被调用“进入时”执行的逻辑（获取参数、打印日志等）``},``onLeave:` `function``(retval) {``// 函数执行“结束返回时”执行的逻辑（修改返回值、处理结果等）``},``}``);` |
|-|-|

onEnter 会在 目标 Native 函数被调用的瞬间触发，它的核心作用是 获取函数的调用参数。其参数args 是一个 NativeArgumentPointer 数组，对应目标 Native 函数的参数列表。比如目标函数是 C 语言的 int add(int a, int b)，那么 args[0] 就是 a 的值，args[1] 就是 b 的值；再比如目标函数是 char* getString(const char* key)，那么 args[0] 就是 key 的字符串指针，这就需要手动解析成字符串。

在 onEnter 回调中，this 是一个 钩子上下文对象，包含当前函数调用的额外信息，比如this.threadId表示当前调用所在的线程 ID，this.returnAddress表示函数执行完成后要返回的地址，this.args等同于参数 args。还可以通过this.xxx在 onEnter 中定义自定义属性，将函数的参数或者变量保存到 this 中，供 onLeave 回调使用。

onLeave 会在 目标 Native 函数执行完成、即将返回给调用者的瞬间触发，它的核心作用就是处理函数的返回值，其参数retval 是一个NativeReturnValue对象，代表目标函数的返回值并支持读取和修改两种操作。但需要注意的是不能直接打印 retval，因为它只是一个指针值，就是一个 jstring 类型的句柄，这个句柄指向 Java 堆中的一个 java.lang.String 对象，指向的是 Java 虚拟机内部管理的对象，并非 C 字符串数据，所以我们不能直接解引用它来读取字符串。如果要打印 retval的话需要经过 JNI 函数转换成C 字符串数据才能得到可读的内容。代码如下：

| 12345678910111213141516 | `function` `hookDump(){``var` `funcAddr = Module.findExportByName(``"libxxx.so"``,` `"methodName"``);``console.log(funcAddr);``if``(funcAddr !=` `null``){``Interceptor.attach(funcAddr,{``onEnter:` `function``(args){` `},``onLeave:` `function``(retval){``var` `env = Java.vm.tryGetEnv();``var` `cstr = env.getStringUtfChars(retval);` `//主动调用 jstr转cstr``console.log(hexdump(cstr));``}``});``}``}` |
|-|-|

可以看到代码首先在onLeave 回调中执行了var env = Java.vm.tryGetEnv();这一段代码，众所周知Java.vm 是 Frida 提供的 JavaVM 接口的封装，而tryGetEnv() 的作用是获取当前线程的 JNIEnv 指针。JNIEnv 是线程私有的，它本质上是一个指向函数表的指针，这个表里包含了所有的 JNI 函数（如 GetStringUTFChars, FindClass 等）。点击tryGetEnv函数跳转可以看到以下代码：

| 1234567891011121314151617181920212223 | `interface VM {``/**``* Ensures that the current thread is attached to the VM and calls `fn`.``* (This isn't necessary in callbacks from Java.)``*``* @param fn Function to run while attached to the VM.``*/``perform(fn: () => void): void;` `/**``* Gets a wrapper for the current thread's `JNIEnv`.``*``* Throws an exception if the current thread is not attached to the VM.``*/``getEnv(): Env;` `/**``* Tries to get a wrapper for the current thread's `JNIEnv`.``*``* Returns `null` if the current thread is not attached to the VM.``*/``tryGetEnv(): Env \|` `null``;``}` |
|-|-|

我们使用的是tryGetEnv函数这是因为如果当前线程还没有附加到 Java 虚拟机，`tryGetEnv()` 会返回 `null`，而 `getEnv()` 则会直接抛异常。这里要注意一点，tryGetEnv()要么需要被Java.perform(function(){});所包裹，要么就需要放在Interceptor.attach();中进行使用，不然的话是获取不到当前线程的 JNIEnv 指针的。我们获取JNIEnv后就执行了var cstr = env.getStringUtfChars(retval);代码，这是最核心的一步，env提供了一个 JavaScript 友好的 JNI 函数包装，而env.getStringUtfChars(jstring) 对应的是 JNI 中的 GetStringUTFChars 函数。当你调用这个方法时，Frida 内部会执行JNI函数GetStringUTFChars，JNI 函数接收 jstring 引用然后转换成C 字符串的指针cstr ，cstr 变量在 Frida 的 JS 环境中被表示为一个 NativePointer，它指向的就是这个可读的 C 字符串。既然可以将jstr转换为cstr，那么也就可以将cstr转换为jstr， env.newStringUtf("...")可以通过 JNI 函数 NewStringUTF 在 Java 堆上创建新字符串，返回 jstring 引用，说个常用的场景，转换为jstr后用 retval.replace(...) 替换原始返回值。流程大致如下：

| 123456789101112131415 | `[Java 调用]` `↓``Native 函数 xxx 被调用``↓``函数执行完毕，准备返回 (返回值在寄存器 R0 中)``↓``Frida 拦截，进入 onLeave 回调``↓``我们调用 env.newStringUtf(``"..."``)   →   JNI NewStringUTF 创建新字符串``↓``得到新 jstring 指针 newJstr``↓``retval.replace(newJstr)   →   Frida 将寄存器 R0 的值替换为 newJstr``↓``函数返回，调用者得到新的 jstring` |
|-|-|

前面提到过onLeave 会在 目标 Native 函数执行完成、即将返回给调用者的瞬间触发，而要修改返回值就要在onLeave 触发后通过 retval.replace(newJstr);来修改它，其中newJstr为返回值要修改的值。返回 jstring 引用的代码如下：

| 12345 | `onLeave:` `function``(retval) {``var` `env = Java.vm.tryGetEnv();``var` `newJstr = env.newStringUtf(``"abcdefg"``);``retval.replace(newJstr);` `// 替换为新的 jstring 引用``}` |
|-|-|

既然提到了在 onLeave 回调中修改返回值，这里retval.replace 不仅可以替换 jstring，它可以替换任何类型的返回值，包括基本类型、对象引用（jobject）、指针等，只要提供一个与原始返回值类型兼容的新值即可。有一点要注意转换为jstring之后如果还是想在so层打印值的话还是需要将jstring转换为cstr。

现在我们对so层的hook有了点了解，但具体要怎么去做可能并不清楚，我讲点比较常规的简单思路，首先当我们在分析时不用完全搞明白所有的执行流程，也不用搞明白每个方法在做什么，只要找到关键方法即可，当你分析时怀疑某个方法是我们要寻找的关键方法你可以去通过hook打印该方法的参数和返回值，再根据传进去的参数和传回来的返回值做一个简单的判断，最典型的就是当你通过hook获取到它传入的参数是一个明文，但得到的返回值是一个长度为32字节结果，那么我们就可以怀疑这个方法是进行了md5消息摘要。我们打印了参数和返回值，但如果有参数或返回值是地址我们就可以通过hexdump方法看一下结构，hexdump方法可以将指针指向的内存内容以十六进制 + ASCII 字符的格式打印，其实也就是我们常见到的左边是十六进制右边是ASCII字符的格式，这可以用于查看二进制数据的原始内容。如果确定ASCII字符是C语言字符串，那么我们就可以通过ptr(args[0]).readCString()将指针指向的内存解析为C 风格字符串，我们举例用args[0] 作为演示，先通过 ptr(args[0]) 转换为 NativePointer，再调用 readCString() 读取字符串。

ptr函数用于将参数转换为指针类型，args[0] 的原始类型是 NativeArgumentValue，也就是Frida 对函数参数的包装类型，其值本质是内存地址的整数表示（如 0x7f8a0000）。ptr函数可以将内存地址的整数包装成可操作的指针，后续可通过该指针读取 / 写入内存（如 readCString()、writeUtf8String() 等）。在修改so层函数参数时也会使用到这个ptr函数，前面提到在 Frida 的 Interceptor.attach 中，onEnter 回调的参数 args 是一个 NativePointer 对象的数组，每个元素代表目标函数的原始参数值，当我们想要修改某个参数时，需要将该参数设置为一个新的 NativePointer 对象，而不能直接赋一个 JavaScript 数字。而要将参数设置为一个新的 NativePointer 对象就需要通过ptr函数将修改值转换为指针类型，假设代码为args[2] = ptr(2000);那么ptr(2000)生成的 NativePointer 对象内部封装了整数 2000，赋值给 args[2] 后，Frida 会将该整数写入参数位置，从而改变函数实际接收到的参数值。

readCString函数是从指针指向的内存读取 C 风格字符串，从指针地址开始，逐个读取字节，直到遇到 0x00（终止符），将读取的字节转换为字符串返回。

除此之外还有readPointer函数用于从当前指针指向的内存地址，读取一个 指针类型的数据（本质是另一个内存地址）。当被 hook 的函数参数或者变量是二级指针时需用 readPointer() 读取指针指向的地址。首先二级指针其实就是在一级指针的基础上套了一层指针，假设变量a是一个指针，它存储了字符串"abc"的地址，而二级指针变量b就是存储了变量a的地址。那么在逆向的时候你得到的参数是一个二级指针，首先你将该参数通过ptr函数转换为指针类型，然后hexdump一下，可你发现没有看到什么有用的信息，ASCII字符的显示是杂乱无章的，那你怀疑该参数是二级指针，打算尝试使用readPointer函数从当前指针中读取一个指针类型的数据，读取到另一个指针的地址后再hexdump一下后你看到了有用的信息。其实第一次你看到的是二级指针存储的一级指针的地址，第二次使用readPointer函数后读取了一级指针的地址，得到一级指针的地址后hexdump一下就可以看到一级指针所指向的内容了。

既然讲到了hexdump那就详细讲讲这个函数，hexdump 函数的基本语法如下：

| 1 | `hexdump(target[, options])` |
|-|-|

target参数是必需的，这是你要查看的内存区域。可以是一个内存地址，也可以是一个包含二进制数据的 ArrayBuffer（例如用 Memory.readByteArray() 读回来的数据）。

options是可选参数，其类型是一个对象，当中包含了以下属性：
options.offset默认是为0的，这个属性表示从 target 的哪个偏移量开始dump。
options.length默认为整个 target 的尺寸，也就是要dump多少字节。
options.header这个属性是布尔类型，默认为 true。是否显示表头，也就是是否显示显示偏移地址和ASCII列标题的那一行。
options.ansi默认为 false，这个属性决定是否在输出中使用ANSI颜色。

除了hexdump查看内存数据之外还可以通过readByteArray方法来读取内存数据，readByteArray函数有两种写法，分别是：

| 特性 | `ptr.readByteArray(length)` (实例方法) | `Memory.readByteArray(address, length)` (静态方法) |
|-|-|-|
| **调用方式** | 从 `NativePointer` 对象上直接调用 | 从全局 `Memory` 对象上调用，将指针作为参数传入 |
| **设计风格** | **面向对象**风格的方法调用 | **函数式**风格的 API 调用 |
| **本质** | 是静态方法的便捷封装（语法糖） | Frida 提供的底层核心 API |
| **可读性** | 更简洁、更符合面向对象的直觉 (`address.read()`) | 更显式，一眼能看出是在操作内存模块 |

当可以看到内存数据后，我们还可以选择修改内存数据，这就需要用 Frida 提供的 Memory 系列 API，将我们准备好的新数据，写入到目标地址中去。

在继续将修改内存数据之前我们需要知道一个常见的情况，这也是在C语言当中特别喜欢用的方式，那就是在函数传递字符串、明文等数据时，通常会遵循 “输入数据指针 + 数据长度 + 输出缓冲区指针” 的这种参数设计模式。为什么要这么整呢？需要传入数据长度参数的直接原因是因为二进制数据（如图片、加密后的字节流）可能包含\0，若用strlen()计算长度会提前截断；函数无法区分 “输入数据的真实长度” 和 “意外包含的\0”，容易导致处理不完整。需要接收返回值的变量的原因是避免函数内部动态分配内存，比如函数返回char*，调用者需手动free，容易遗漏导致内存泄漏；可以由调用者根据需求分配足够大的内存，比如 Base64 编码后的数据长度是原长度的 4/3，需提前计算。还支持原地修改，如输入输出可以复用内存，可传入同一个指针。在C语言中通常还会额外传递 “输出缓冲区的最大长度”（size_t output_max_len），防止函数写入超出缓冲区范围的数据（避免缓冲区溢出漏洞）。

而修改内存数据最通用的就是Memory.writeByteArray(address, bytes)，写入的数据类型是字节数组，这个可以写入任何二进制数据。当我们要修改的目标是全局变量或已知的固定缓冲区，我们可以直接向那个地址写入新数据：

| 1234 | `// 示例：直接修改某个地址开始的16个字节``var` `targetAddr = ptr(``"0x12345678"``);` `// 内存地址``var` `newData = [0x41, 0x42, 0x43, 0x44];` `// "ABCD"``Memory.writeByteArray(targetAddr, newData);` |
|-|-|

前面我们也详细讲了C语言中很常用的方式：native 函数通过指针参数返回数据，那么针对这一情况进行内存数据的修改就有必要了，假设 native 函数原型如下：

| 1 | `void` `getData(``char``* outBuf);` `// outBuf 由调用者分配，函数向其中写入数据` |
|-|-|

在 Hook 该函数时，我们可以在 onLeave 中拿到 outputBuffer 的地址（即 args[0]），此时函数已经将原始数据写入了该缓冲区。我们的目标是用自己的数据覆盖这块内存，从而改变调用者看到的结果。我们假设要修改内存的新数据有两种类型，分别是长度为16字节的string类型以及长度为32字节的hex类型，其实这两者的长度都是一样的，只是因为hex是四个二进制位表示一字节，而string是八个二进制位表示一字节而已。我们需要将这两种类型转换为字节数据，这就需要我们自己写转换代码了，将字符串的每个字符转换成对应的字节数组：

| 1234567 | `function` `stringToBytes(str, length = 16) {``const bytes = [];``for` `(let i = 0; i < length; i++) {``bytes.push(i < str.length ? str.charCodeAt(i) : 0);``}``return` `bytes;``}` |
|-|-|

hex 字符串转换成字节数组：

| 1234567891011 | `function` `hexToBytes(hexStr) {``// 清理可能的空格和前缀 0x``hexStr = hexStr.replace(/\s+/g,` `''``).replace(/^0x/i,` `''``);``// 确保长度为偶数（此处应为 32）``if` `(hexStr.length % 2 !== 0)` `throw` `new` `Error(``"Invalid hex string length"``);``const bytes = [];``for` `(let i = 0; i < hexStr.length; i += 2) {``bytes.push(parseInt(hexStr.substr(i, 2), 16));``}``return` `bytes;``}` |
|-|-|

我们在 onLeave 中覆盖这块内存。

| 123456789101112131415161718192021222324252627282930 | `// 找到目标函数地址``var` `funcPtr = Module.findExportByName(``"libnative.so"``,` `"getData"``);` `Interceptor.attach(funcPtr, {``onEnter:` `function``(args) {``// 保存输出缓冲区指针``this``.outBuf = args[0];``console.log(``"[*] Output buffer at: "` `+` `this``.outBuf);``},``onLeave:` `function``(retval) {``// 可选：查看原始数据``console.log(``"[*] Original data:"``);``console.log(hexdump(``this``.outBuf, { length: 16 }));` `// --- 准备新数据（二选一）---``// 选项 1：16 字节字符串``var` `strData =` `"HELLO_WORLD_123"``;` `// 假设正好 16 字符``var` `newBytes = stringToBytes(strData, 16);` `// 16 字节数组` `// 选项 2：32 字符 hex 字符串 → 16 字节数组``var` `hexStr =` `"00112233445566778899aabbccddeeff"``;` `// 32 个 hex 字符``var` `newBytes = hexToBytes(hexStr);` `// 16 字节数组` `// 写入内存``Memory.writeByteArray(``this``.outBuf, newBytes);` `console.log(``"[*] After modification:"``);``console.log(hexdump(``this``.outBuf, { length: 16 }));``}``});` |
|-|-|

如何修改内存数据我们有所了解，我们如果使用frida要hook so层的导出函数可以使用findExportByName方法，该方法在指定的.so文件中，根据「模块名 + 导出函数名」查找该函数的内存地址，所以该方法有两个参数，一个是目标 SO 文件名，另一个是要查找的导出函数名，两个参数都是string类型，其返回值是一个指针类型，找到时返回函数的内存地址；未找到时返回 null。这里要谨记导出函数名不是要的导出表中的名字，而是要汇编代码中导出函数的名字，当然也可以通过获取so的基址加方法偏移地址的方式来进行hook，比如下图中的偏移地址就为5328C，汇编代码中导出函数的名字为划红线的函数名称:
 ![image](https://bbs.kanxue.com/upload/attach/202603/926486_DE2H77S4TRZ7TRS.webp)
frida还可以枚举导出表的函数、导入表的函数、符号表的函数等等，我们现在就总结性的讲讲frida中的枚举：

| 分类 | 核心API | 主要作用 | 典型使用场景 |
|-|-|-|-|
| **进程与内存** | `Process.enumerateModules()` | 列出进程加载的所有模块（如 .so, .dll, 主程序） | 定位关键库，了解模块基址，遍历所有代码区域 |
|  | `Process.enumerateThreads()` | 列出进程中当前运行的所有线程 | 监控线程创建，对特定线程进行 Trace（如 `Stalker`） |
| **Native层** | `Module.enumerateImports()` | 枚举指定模块的导入表（使用了外部哪些函数） | 分析模块依赖，Hook 外部函数调用（如 `strcmp`） |
|  | `Module.enumerateExports()` | 枚举指定模块的导出表（模块向外提供了哪些函数） | 直接定位并 Hook 模块提供的目标函数（如 `Java_*` 函数） |
|  | `Module.enumerateSymbols()` | 枚举模块的调试符号（比导出表更详细，包含未导出的内部函数） | 查找隐藏的、未导出的内部函数，用于深度分析（如在 `libart.so` 中找 JNI 函数） |
| **Java层** | `Java.enumerateLoadedClasses()` | 枚举当前 Java 虚拟机中已加载的所有类 | 发现 App 中所有的 Java 类，寻找分析目标 |
|  | `Java.enumerateClassLoaders()` | 枚举当前所有的类加载器 | 处理使用了自定义类加载器的 App，用于动态加载 Dex 的场景 |
|  | `Java.enumerateMethods()` | 根据模式匹配枚举指定类的方法 | 快速定位特定类中的所有方法，用于批量 Hook |

枚举在frida hook中有举足轻重的作用，前面讲过枚举当前所有的类加载器可以应对动态加载dex的情况，我们接下来要讲的JNI函数hook就需要用到枚举libart.so的符号表，因为libart.so的符号表里面可以找到JNI的函数。这里直接用正己大佬Hook RegisterNatives函数的代码。

| 1234567891011121314151617181920212223242526272829303132333435363738394041424344454647484950515253545556575859606162 | `function` `find_RegisterNatives(params) {``// 在 libart.so 库中枚举所有符号（函数、变量等）``let symbols = Module.enumerateSymbolsSync(``"libart.so"``);` `let addrRegisterNatives =` `null``;` `// 用于存储 RegisterNatives 方法的地址` `// 遍历所有符号来查找 RegisterNatives 方法``for` `(let i = 0; i < symbols.length; i++) {``let symbol = symbols[i];` `// 当前遍历到的符号` `// 检查符号名称是否符合 RegisterNatives 方法的特征``if` `(symbol.name.indexOf(``"art"``) >= 0 &&` `//RegisterNatives 是 ART（Android Runtime）环境的一部分``symbol.name.indexOf(``"JNI"``) >= 0 &&` `//RegisterNatives 是 JNI（Java Native Interface）的一部分``symbol.name.indexOf(``"RegisterNatives"``) >= 0 &&` `//检查符号名称中是否包含 "RegisterNatives" 字样。``symbol.name.indexOf(``"CheckJNI"``) < 0) {` `//CheckJNI 是用于调试和验证 JNI 调用的工具，如果不过滤，会有两个RegisterNatives，而带有CheckJNI的系统一般是关闭的，所有要过滤掉``addrRegisterNatives = symbol.address;` `// 保存方法地址``console.log(``"RegisterNatives is at "``, symbol.address, symbol.name);` `// 输出地址和名称``hook_RegisterNatives(addrRegisterNatives);` `// 调用hook函数``}``}``}` `function` `hook_RegisterNatives(addrRegisterNatives) {``// 确保提供的地址不为空``if` `(addrRegisterNatives !=` `null``) {``// 使用 Frida 的 Interceptor hook指定地址的函数``Interceptor.attach(addrRegisterNatives, {``// 当函数被调用时执行的代码``onEnter:` `function` `(args) {``// 打印调用方法的数量``console.log(``"[RegisterNatives] method_count:"``, args[3]);` `// 获取 Java 类并打印类名``let java_class = args[1];``let class_name = Java.vm.tryGetEnv().getClassName(java_class);` `let methods_ptr = ptr(args[2]);` `// 获取方法数组的指针``let method_count = parseInt(args[3]);` `// 获取方法数量` `// 遍历所有方法``//jni方法里包含三个部分：方法名指针、方法签名指针和方法函数指针。每个指针在内存中占用 Process.pointerSize 的空间（这是因为在 32 位系统中指针大小是 4 字节，在 64 位系统中是 8 字节）。为了提高兼容性，统一用Process.pointerSize，系统会自动根据架构来适配``for` `(let i = 0; i < method_count; i++) {``// 读取方法的名称、签名和函数指针``let name_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3));``//读取方法名的指针。这是每个方法结构体的第一部分，所以直接从起始地址读取。``let sig_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize));``//读取方法签名的指针。这是结构体的第二部分，所以在起始地址的基础上增加了一个指针的大小``let fnPtr_ptr = Memory.readPointer(methods_ptr.add(i * Process.pointerSize * 3 + Process.pointerSize * 2));``//读取方法函数的指针。这是结构体的第三部分，所以在起始地址的基础上增加了两个指针的大小（Process.pointerSize * 2）。` `// 将指针内容转换为字符串``let name = Memory.readCString(name_ptr);``let sig = Memory.readCString(sig_ptr);` `// 获取方法的调试符号``let symbol = DebugSymbol.fromAddress(fnPtr_ptr);` `// 打印每个注册的方法的相关信息``console.log(``"[RegisterNatives] java_class:"``, class_name,` `"name:"``, name,` `"sig:"``, sig,` `"fnPtr:"``, fnPtr_ptr,` `" fnOffset:"``, symbol,` `" callee:"``, DebugSymbol.fromAddress(``this``.returnAddress));``}``}``});``}``}` `setImmediate(find_RegisterNatives);` `// 立即执行 find_RegisterNatives 函数` |
|-|-|

首先Module.enumerateSymbolsSync("libart.so"); 代码枚举libart.so 库中枚举所有符号，我们IDA反编译libart.so，下图红框框住的便是所谓的符号表：
 ![image](https://bbs.kanxue.com/upload/attach/202603/926486_8CZ7WHW96ZM97J8.webp)
首先符号表中符号名必须包含 "art"，libart.so 中除了 ART 自己的符号，还可能包含其他第三方库或编译器生成的符号。代码接下来筛选符号名包含 "JNI"的符号，因为 RegisterNatives 是一个 JNI 函数，属于 JNI 子系统。ART 内部还有其他名为 RegisterNatives 的函数，比如在编译器或解释器中，但它们与 JNI 无关。接下来筛选符号名包含 "RegisterNatives"的符号，这是我们要hook的函数。最后也是最关键的一步那就是筛选符号名不能包含 "CheckJNI"的符号，为什么呢？我们先在符号表中搜索RegisterNatives，然后会得到以下结果：
 ![image](https://bbs.kanxue.com/upload/attach/202603/926486_KP2FHD2UVUUWRV3.webp)
可以看到有三个不同的RegisterNatives函数，分别是`art::JNI<true>::RegisterNatives`带检查的正式版本，模板参数`<true>`表示启用 CheckJNI 模式。`JNI<true>`版本是调试/检查模式下使用的，它会在注册方法时执行大量额外的参数验证和错误检查。而`art::JNI<false>::RegisterNatives`是不带检查的正式版本，模板参数 `<false>`表示禁用 CheckJNI 模式。最后一种art:: (anonymous namespace)::CheckJNI::RegisterNatives是CheckJNI 的辅助包装器，这个函数是一个静态辅助函数，位于 CheckJNI 命名空间内。它通常由 `JNI<true>::RegisterNatives` 调用，负责完成具体的检查逻辑。如果不过滤掉 CheckJNI，我们可能会错误地 Hook 到 `JNI<true>` 版本，而这个版本在大多数运行环境中永远不会被调用，导致 Hook 失效。

大家自个有兴趣的话可以反编译libart.so去看看，Android 12 及更高版本libart.so 位于独立的 ART APEX 模块中，64位路径是/apex/com.android.art/lib64/libart.so，32位路径是/apex/com.android.art/lib/libart.so，在高于安卓10的系统里，64位的libart.so路径是/apex/com.android.runtime/lib64/libart.so，低于10的则在system/lib64/libart.so，32位就在lib目录下而不是lib64目录。

接下来要讲so层的主动调用，这个是很重要的，我们直接先看代码：

| 1234567891011121314151617 | `function` `call_xxx() {``// 1. 定位目标函数地址（libxxx.so + 0x906c0）``var` `libBase = Module.findBaseAddress(``"libxxx.so"``);``if` `(!libBase) {``console.error(``"未找到libxxx.so"``);``return``;``}``var` `funcAddr = libBase.add(0x906c0);``console.log(``"目标函数地址: "` `+ funcAddr);` `var` `str1 =` `"aoeiuv"``var` `str2 =` `"abcdefg"``var` `aesAddr =` `new` `NativeFunction(funcAddr ,` `'pointer'``, [``'pointer'``,` `'pointer'``]);``var` `encry_text = Memory.allocUtf8String(str1);` `//开辟一个指针存放字符串` `var` `key = Memory.allocUtf8String(str2);` `console.log(aesAddr(encry_text ,key).readCString());``}` |
|-|-|

Module.findBaseAddress("libxxx.so") 遍历目标进程已加载的模块，返回指定 SO 的基址，libBase.add(0x906c0) 将基址加上偏移量，得到目标函数的绝对虚拟内存地址。

代码中new NativeFunction(funcAddr , 'pointer', ['pointer', 'pointer']);是 Frida 提供的核心 API用于声明函数指针，其中第一个参数为要主动调用函数的地址，第二个参数为返回值的类型，第三个参数为一个数组，数组里面存放的便是参数的类型，'pointer'表示参数或返回值是一个指针，其他常见类型有'void', 'int', 'uint', 'float', 'bool' 等。得到函数指针后我们可以传入两个指针参数，aesAddr(encry_text, key) 执行 Native 函数。而Memory.allocUtf8String(str) 在目标进程的堆上分配一块内存，将 JavaScript 字符串 str 转换为 UTF-8 编码的 C 字符串，并返回指向该内存的 NativePointer。函数执行完毕后，返回值被封装成一个 NativePointer 对象，最后通过 .readCString() 将该指针指向的内存作为 C 字符串读取并打印。

frida hook还可以写文件，有两种方式，第一种是通过Frida 的 File 类写文件，第二种是手动调用 libc 函数写文件。先看第一种写文件方式的代码：

| 123456 | `function` `hookTest12() {``var` `ios =` `new` `File(``"/sdcard/xxx.txt"``,` `"w"``);``ios.write(``"hahahahaha!!!\n"``);``ios.flush();``ios.close();``}` |
|-|-|

File类是 Frida 内置的 JavaScript 类，它封装了对目标设备文件系统的操作。new File("/sdcard/xxx.txt", "w")需要指定路径和模式以打开文件。路径 /sdcard/xxx.txt 是 Android 设备上的一个常见可写路径，模式 "w" 表示写入模式。ios.write("hahahahaha!!!\n") 将字符串数据写入文件，Frida 会将该字符串转换为字节，并通过目标进程的文件描述符写入文件。写入的数据会先缓存在 Frida 内部缓冲区中，而flush() 强制将缓冲区数据写入磁盘，最后close() 关闭文件描述符，释放资源。

接下来我们看看第二种写文件方式的代码：

| 123456789101112131415161718192021222324252627 | `function` `hookTest13() {``// 1. 获取函数地址``var` `addr_fopen = Module.findExportByName(``"libc.so"``,` `"fopen"``);``var` `addr_fputs = Module.findExportByName(``"libc.so"``,` `"fputs"``);``var` `addr_fclose = Module.findExportByName(``"libc.so"``,` `"fclose"``);` `// 2. 创建 NativeFunction 对象``var` `fopen =` `new` `NativeFunction(addr_fopen,` `"pointer"``, [``"pointer"``,` `"pointer"``]);``var` `fputs =` `new` `NativeFunction(addr_fputs,` `"int"``, [``"pointer"``,` `"pointer"``]);``var` `fclose =` `new` `NativeFunction(addr_fclose,` `"int"``, [``"pointer"``]);` `// 3. 准备参数字符串（在目标进程堆上分配内存）``var` `filename = Memory.allocUtf8String(``"/sdcard/xxx.txt"``);``var` `open_mode = Memory.allocUtf8String(``"w"``);``var` `buffer = Memory.allocUtf8String(``"hahaha\n"``);` `// 4. 调用 fopen 打开文件``var` `file = fopen(filename, open_mode);``console.log(``"fopen:"``, file);` `// file 是一个 FILE* 指针` `// 5. 调用 fputs 写入数据``var` `retval = fputs(buffer, file);``console.log(``"fputs:"``, retval);` `// 6. 关闭文件``fclose(file);``}` |
|-|-|

先获取函数地址，比如Module.findExportByName("libc.so", "fopen") 在目标进程的 libc.so 模块中查找导出函数 fopen 的虚拟内存地址。因为 libc.so 是每个 Android 进程都会加载的 C 库，所以这些地址是有效的。然后再声明函数指针用于主动调用fopen、fputs、fclose ，Memory.allocUtf8String(str) 还是在目标进程的堆上分配一块内存，将 JavaScript 字符串转换为 UTF-8 编码的 C 字符串，并返回指向该内存的 NativePointer。接下来调用 fopen，fopen(filename, open_mode) 执行后，会返回一个 FILE* 指针存储在 file 变量中，这个指针指向一个由 libc 管理的文件结构体，后续的 fputs 和 fclose 需要用到它。fputs(buffer, file) 将字符串写入文件。这里 buffer 是指向 "hahaha\n" 的指针，file 是之前打开的 FILE*。libc 内部会处理缓冲和写入。 最后fclose(file) 关闭文件，释放相关资源。

现在我们进行的hook主要还是针对于函数，除了hook函数之外我们还可以hook寄存器，之前讲arm汇编的时候讲过在 ARM64 架构中，函数参数和返回值通过特定寄存器传递，前8个寄存器X0到X7用于函数调用时传递参数，X0 同时用于函数返回值。下面代码就对寄存器进行hook：

| 12345678910111213141516171819202122232425262728293031 | `function` `X23Hook() {``Java.perform(``function``() {``let libsscronetAddress = Module.findBaseAddress(``'libsscronet.so'``);``console.log(``" ==> libsscronet : "` `+ libsscronetAddress);``var` `offset = ptr(0x406E98);``var` `funcAddr = libsscronetAddress.add(offset);``console.log(funcAddr);``Interceptor.attach(funcAddr, {``onEnter:` `function``(args) {``let sixSubAddr =` `this``.context.x23;``console.log(``"--> six ==> 0x"` `+ sixSubAddr.toString(16));` `let module = Process.findModuleByAddress(sixSubAddr);``if` `(module) {``console.log(``"地址属于模块: "` `+ module.name);``console.log(``"模块基址: "` `+ module.base);``console.log(``"模块⼤⼩: "` `+ module.size);``console.log(``"函数位置: 0x"` `+ (ptr(sixSubAddr).sub(module.base) ).toString(16) );``}` `else` `{``console.log(``"未找到所属模块"``);``}``},``onLeave:` `function``(retval) {``}``});``});``}` `setTimeout(() => {``X23Hook();``}, 3000);` |
|-|-|

这段代码所hook的汇编代码：

| 1234 | `.text:``0000000000406E90`                 `MOV             X0, X22``.text:``0000000000406E94`                 `MOV             X1, X21``.text:``0000000000406E98`                 `BLR             X23``.text:``0000000000406E9C`                 `MOV             X21, X0` |
|-|-|

在 libsscronet.so 中找到偏移 0x406E98 的地址，该地址处是一条 BLR X23 指令。当程序执行到 0x406E98 时，触发 onEnter，this.context 是 Frida 提供的 CPU 上下文对象，包含了所有寄存器的值，通过 this.context.x23 获取即将调用的函数地址。Process.findModuleByAddress(addr) 返回该地址所在的模块信息，这样可以动态追踪这个函数指针指向的是哪个模块内的哪个函数。

当程序执行到被 Hook 的地址时，CPU 跳转到 Frida 的拦截器入口，拦截器保存当前 CPU 的所有寄存器到内存中，形成一个 CpuContext 对象，根据 Hook 类型onEnter 或 onLeave调用对应的 JavaScript 回调，并将上下文对象作为 this.context 传递给回调，回调中可以读取或修改 this.context 中的寄存器值，回调执行完毕后，拦截器将修改后的寄存器值写回 CPU，拦截器跳转到蹦床，执行之前保存的原始指令，这一段可能会有些迷糊，其实就是当调用 Interceptor.attach(address, callbacks) 时，从 address 开始，读取足够长的指令序列，保证至少能容纳一条跳转指令，将这些原始指令复制到一块 Frida 内部管理的内存区域，称为 蹦床，蹦床的作用是稍后执行原始指令并跳回原程序流。原始指令执行完后，再跳转回原程序的下一条指令。

当时hook寄存器X23的时候还遇到一个问题，简单来说X23寄存器存储的是一个地址，而这个地址不属于当前这个so，而是属于其他so的地址，这种情况该怎么处理呢？frida提供了对应的函数来解决这个问题， Process.findModuleByAddress方法可以根据给定的地址查找模块，X23 中存放的地址通常是导入函数的地址，在动态链接过程中，当前 SO 加载时，系统会先加载它所依赖的所有 SO，并将这些外部函数的真实地址填入全局偏移表（GOT表）或直接写入指令能访问的位置。最终，X23寄存器的值就是通过这种方式获得的。但需要注意的是在当前so加载时会先去加载导入表函数所属的so模块，也可以简单理解为导入表函数所属的so模块是当前so的依赖。代码如下：

| 123456789101112131415161718192021222324252627 | `function` `X23Hook() {``Java.perform(``function``() {``let libxxxAddress = Module.findBaseAddress(``'libxxx.so'``);``console.log(``" ==> libxxx : "` `+ libxxxAddress);``var` `offset = ptr(0x424AE8);``var` `funcAddr = libxxxAddress.add(offset);``console.log(funcAddr);``Interceptor.attach(funcAddr, {``onEnter:` `function``(args) {``let sixSubAddr =` `this``.context.x23;``console.log(``"--> six ==> 0x"` `+ sixSubAddr.toString(16));` `let module = Process.findModuleByAddress(sixSubAddr);``if` `(module) {``console.log(``"地址属于模块: "` `+ module.name);``console.log(``"模块基址: "` `+ module.base);``console.log(``"模块⼤⼩: "` `+ module.size);``console.log(``"函数位置: 0x"` `+ (ptr(sixSubAddr).sub(module.base) ).toString(16) );``}` `else` `{``console.log(``"未找到所属模块"``);``}``},``onLeave:` `function``(retval) {``}``});``});``}` |
|-|-|

Process.findModuleByAddress方法它接受一个内存地址，然后遍历当前进程加载的所有模块，如果找到，返回一个包含模块信息的对象，其中包含name、base、size、path 等；否则返回 null。

既然能hook获取寄存器的值，那么就可以通过hook修改寄存器的值，以下代码实现了修改寄存器的值：

| 1234567891011121314 | `var` `sub_2858 = soAddr.add(0x2858);` `//函数地址计算 thumb+1 ARM不加``console.log(sub_2858);``if` `(sub_2858 !=` `null``) {``Interceptor.attach(sub_2858, {``onEnter:` `function` `(args) {``console.log(``this``.context.x1);``this``.context.x1 = soAddr.add(0x2C35);``console.log(``this``.context.x1);``},``onLeave:` `function` `(retval) {` `}``});``}` |
|-|-|

这段代码所hook的汇编代码：

| 1234567891011121314151617181920212223242526272829303132 | `.text:``0000000000002830``.text:``0000000000002830`                   `;` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=` `S U B R O U T I N E` `=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``=``.text:``0000000000002830``.text:``0000000000002830`                   `; Attributes: bp``-``based frame``.text:``0000000000002830``.text:``0000000000002830`                   `EXPORT Java_com_xiaojianbang_app_NativeHelper_helloFromC``.text:``0000000000002830`           `Java_com_xiaojianbang_app_NativeHelper_helloFromC``.text:``0000000000002830`                                           `; DATA XREF: LOAD:``000000000000468``↑o``.text:``0000000000002830``.text:``0000000000002830`                   `var_18` `=` `-``0x18``.text:``0000000000002830`                   `var_10` `=` `-``0x10``.text:``0000000000002830`                   `var_8` `=` `-``8``.text:``0000000000002830`                   `var_s0` `=` `0``.text:``0000000000002830``.text:``0000000000002830`                   `; __unwind {``.text:``0000000000002830` `FF C3` `00` `D1                 SUB             SP, SP,` `#0x30``.text:``0000000000002834` `FD` `7B` `02` `A9                 STP             X29, X30, [SP,``#0x20+var_s0]``.text:``0000000000002838` `FD` `83` `00` `91`                 `ADD             X29, SP,` `#0x20``.text:``000000000000283C` `08` `00` `00` `90`                 `ADRP            X8,` `#aHelloFromC@PAGE ; "hello from c!"``.text:``0000000000002840` `08` `01` `30` `91`                 `ADD             X8, X8,` `#aHelloFromC@PAGEOFF ; "hello from c!"``.text:``0000000000002844` `A0` `83` `1F` `F8                 STUR            X0, [X29,``#var_8]``.text:``0000000000002848` `E1` `0B` `00` `F9` `STR`             `X1, [SP,``#0x20+var_10]``.text:``000000000000284C` `E8` `07` `00` `F9` `STR`             `X8, [SP,``#0x20+var_18]``.text:``0000000000002850` `A0` `83` `5F` `F8                 LDUR            X0, [X29,``#var_8]``.text:``0000000000002854` `E1` `07` `40` `F9                 LDR             X1, [SP,``#0x20+var_18]``.text:``0000000000002858` `4E` `FF FF` `97`                 `BL              sub_2590``.text:``000000000000285C` `FD` `7B` `42` `A9                 LDP             X29, X30, [SP,``#0x20+var_s0]``.text:``0000000000002860` `FF C3` `00` `91`                 `ADD             SP, SP,` `#0x30``.text:``0000000000002864` `C0` `03` `5F` `D6                 RET``.text:``0000000000002864`                   `; }` `/``/` `starts at` `2830``.text:``0000000000002864`                   `; End of function Java_com_xiaojianbang_app_NativeHelper_helloFromC``.text:``0000000000002864` |
|-|-|

soAddr.add(0x2C35) 利用了so中已有的字符串，这些字符串通常位于只读数据段，在 so 加载时就已经存在于内存中，地址固定。将 x1 指向 so 内偏移 0x2C35 处的字符串。还可以通过类似以下代码修改为自定义的字符串：

| 12345678 | `Interceptor.attach(sub_2858, {``onEnter:` `function` `(args) {``// 在目标进程堆上分配内存，写入自定义字符串``var` `newStr = Memory.allocUtf8String(``"Hello, I'm new!"``);``// 将 x1 寄存器指向新字符串``this``.context.x1 = newStr;``}``});` |
|-|-|

关于寄存器hook大致如此了，关于frida hook的基础也差不多如此了，一些进阶操作和过frida检测之后再讲，江湖路远，后会有期！

---

# 回复

## 回复 by huangjw (#2)

*2026-3-12 12:50*

可以的，还有续篇吗

## 回复 by PPTV (#3)

*2026-3-12 17:21*

先收藏

## 回复 by 黎明与黄昏 (#4)

*2026-3-12 17:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>  huangjw](https://bbs.kanxue.com/user-323039.htm)
>  可以的，还有续篇吗
>

有，后面会有frida hook进阶和过frida检测相关的

## 回复 by mb_elqwyvnm (#5)

*2026-3-13 04:38*

使用的学习教程

## 回复 by 土豆爱学习 (#6)

*2026-3-24 16:15*

1

## 回复 by mb_slrassxp (#7)

*2026-4-10 11:56*

感谢大佬

## 回复 by mb_zcfhleoj (#8)

*2026-4-22 16:32*

感谢分享

## 回复 by mb_zmtxrnca (#9)

*2026-6-18 11:45*

感谢大佬
