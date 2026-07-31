---
title: '[原创]Frida-Hook-Java层操作大全'
url: https://bbs.kanxue.com/thread-280758.htm
tid: 280758
author: Shangwendada
date: '2024-03-04'
tags: [Android安全, 原创, 其他, HOOK注入]
crawled_at: '2026-07-31T14:30:48+08:00'
replies: 14
---

## 附件下载

<https://github.com/DERE-ad2001/Frida-Labs>

## 前期准备

1. 使用 jadx 进行逆向工程的基础知识。
2. 应具备理解 Java 代码的能力。
3. 具备编写小型 JavaScript 代码片段的能力。
4. 熟悉 adb。
5. 设备已 root。
6. [Frida环境配置](https://shangwendada.top/index.php/2024/02/17/fridafrida%e7%8e%af%e5%a2%83%e9%85%8d%e7%bd%ae/)

## Hook（Hooking）简介

让我们从非常基础的知识开始。

**什么是钩子？**

**Hook**是指拦截和修改应用程序或Android系统中函数或方法行为的过程。例如，我们可以钩取我们应用程序中的一个方法，并通过插入我们自己的实现来改变其功能。

现在，让我们尝试在一个应用程序中钩取一个方法。我们将使用JavaScript API 来完成这个任务，但值得注意的是，Frida也支持Python。

## 1、使用Hook修改被调用的方法的逻辑，返回值，传入参数

### 基本模板

首先让我提供给你一个模板，然后我们一步步来解释。

| 123456789101112 | `Java.perform(``function``() {` `var` `<class_reference> = Java.use(``"<package_name>.<class>"``);``<class_reference>.<method_to_hook>.implementation =` `function``(<args>) {` `/*``我们自己的方法实现``*/` `}` `})` |
|-|-|

- `Java.perform` 是 Frida 中用于创建一个特殊上下文的函数，让你的脚本能够与 Android 应用程序中的 Java 代码进行交互。它就像是打开了一扇门，让你能够访问并操纵应用程序内部运行的 Java 代码。一旦进入这个上下文，你就可以执行诸如钩取方法或访问 Java 类等操作来控制或观察应用程序的行为。
- `var <class_reference> = Java.use("<package_name>.<class>");`
在这里，你声明一个变量 `<class_reference>` 来表示目标 Android 应用程序中的一个 Java 类。你使用 `Java.use` 函数指定要使用的类，该函数接受类名作为参数。`<package_name>` 表示 Android 应用程序的包名，`<class>` 表示你想要与之交互的类。
`<package_name>` ：
![file](https://bbs.kanxue.com/upload/attach/202403/979679_8WE6R2XB6KDSNU8.jpg)
- `<class_reference>.<method_to_hook>.implementation = function(<args>) {}`
在所选的类内部，通过 `<class_reference>.<method_to_hook>` 符号访问你想要钩取的方法。这是你可以定义自己的逻辑以在钩取的方法被调用时执行的地方。`<args>` 表示传递给函数的参数。

### 例题Frida-Labs 0x1

通过Jadx分析Frida-labs 0x1

#### onCreate方法

| 123456789101112131415161718 | `public` `void` `onCreate(Bundle bundle) {``super``.onCreate(bundle);``setContentView(C0570R.layout.activity_main);``final` `EditText editText = (EditText) findViewById(C0570R.C0573id.editTextTextPassword);``this``.f103t1 = (TextView) findViewById(C0570R.C0573id.textview1);``final` `int` `i = get_random();``((Button) findViewById(C0570R.C0573id.button)).setOnClickListener(``new` `View.OnClickListener() {` `// from class: com.ad2001.frida0x1.MainActivity.1``@Override` `// android.view.View.OnClickListener``public` `void` `onClick(View view) {``String obj = editText.getText().toString();``if` `(TextUtils.isDigitsOnly(obj)) {``MainActivity.``this``.check(i, Integer.parseInt(obj));``}` `else` `{``Toast.makeText(MainActivity.``this``.getApplicationContext(),` `"Enter a valid number !!"``,` `1``).show();``}``}``});``}` |
|-|-|

可以发现，在onCreate方法中，有一个监听事件，监听了button的点击，当按钮点击下去之后，程序首先判断输入是不是数字，是数字的话，就将其从string转化为int，再进入check中与i比较，因此我们需要检查check方法。

#### check方法

| 123456789101112131415161718192021222324252627282930 | `void` `check(``int` `i,` `int` `i2) {``if` `((i *` `2``) +` `4` `== i2) {``Toast.makeText(getApplicationContext(),` `"Yey you guessed it right"``,` `1``).show();``StringBuilder sb =` `new` `StringBuilder();``for` `(``int` `i3 =` `0``; i3 <` `20``; i3++) {``char` `charAt =` `"AMDYV{WVWT_CJJF_0s1}"``.charAt(i3);``if` `(charAt <` `'a'` `\|\| charAt >` `'z'``) {``if` `(charAt >=` `'A'``) {``if` `(charAt <=` `'Z'``) {``charAt = (``char``) (charAt -` `21``);``if` `(charAt >=` `'A'``) {``}``charAt = (``char``) (charAt +` `26``);``}``}``sb.append(charAt);``}` `else` `{``charAt = (``char``) (charAt -` `21``);``if` `(charAt >=` `'a'``) {``sb.append(charAt);``}``charAt = (``char``) (charAt +` `26``);``sb.append(charAt);``}``}``this``.f103t1.setText(sb.toString());``return``;``}``Toast.makeText(getApplicationContext(),` `"Try again"``,` `1``).show();``}` |
|-|-|

本方法显而易见就是检查输入是否能够满足i*2 + 4 == i2,如果满足则将flag输出到f103t1所绑定的textView控件上,其中用于判断的i则来自get_random。

#### get_random

| 123 | `int` `get_random() {``return` `new` `Random().nextInt(``100``);``}` |
|-|-|

显而易见，本方法就只是普通的返回一个随机数。

#### Hook begin!

对于本样例程序，我们有两种方法去解决，首先我们可以直接hook程序逻辑。更改随机产生的值为一个固定值。或者hook check方法更改check方法传入的参数

##### Hook get_random方法

###### 实现代码

| 1234567891011121314 | `function` `hook(){``var` `MainActivity = Java.use(``"com.ad2001.frida0x1.MainActivity"``);``MainActivity.get_random.implementation =` `function` `(){``return` `0;``}``}` `function` `main(){``Java.perform(``function` `(){``hook();``})``}` `setImmediate(main);` |
|-|-|

代码解释如下：

1. 首先定义了一个名为`hook`的JavaScript函数，其中包含了对目标应用特定方法的hook逻辑。

	- `hook`函数通过Frida的Java API来获取目标应用中的`MainActivity`类。
	- 然后，它通过`Java.use()`方法获取了`MainActivity`类的引用，使得我们可以访问该类的方法。
	- 最后，`hook`函数将`MainActivity`类中的`get_random`方法进行了修改。它用自定义的实现替换了原有方法的实现，使得每次调用`get_random`方法时都返回固定值0。
2. 接着定义了一个名为`main`的JavaScript函数，其中包含了Frida的`Java.perform()`方法，用于执行指定的hook逻辑。
3. 最后，通过`setImmediate()`函数调用`main`函数，确保在Frida脚本启动后立即执行。

##### hook check方法

如果我们检查check函数的参数，第一个参数i表示随机数，而第二个参数i2对应于用户输入的数字。让我们使用Frida来捕获并转储这两个参数。

在处理具有参数的方法时，重要的是使用overload(arg_type)关键字指定预期的参数类型。此外，在钩入方法时确保包括这些指定的参数在你的实现中。在这里，我们的check()函数接受两个整数参数，所以我们可以这样指定：

| 12345 | `a.check.overload(int, int).implementation =` `function``(a, b) {` `...` `}` |
|-|-|

| 123456789101112131415 | `function` `hook2(){``var` `MainActivity = Java.use(``"com.ad2001.frida0x1.MainActivity"``);``MainActivity.check.overload(``'int'``,``'int'``).implementation =` `function` `(a,b){``console.log(``"Origin i and i2 = "``,a,b);``return` `this``.check(a,b);``}``}` `function` `main(){``Java.perform(``function` `(){``hook2();``})``}` `setImmediate(main);` |
|-|-|

我们可以使用console.log查看传入的a与b是什么
![file](https://bbs.kanxue.com/upload/attach/202403/979679_SRBPYSGTZHAFAZD.jpg)

在`this.check(a,b);`中的a,b改为自己设定的值就可以了。
![file](https://bbs.kanxue.com/upload/attach/202403/979679_5P43JRC5DF77VA4.jpg)

## 2、Hook调用静态的未被调用的方法

在之前讲到的Java.use Api中，如果我们指定的类中包含了静态的方法，则我们可以直接调用该方法。模板如下：

| 1234 | `Java.perform(``function` `(){``var` `<class_reference> = Java.use(``"<package_name>.<class>"``);``a.``function``(val);``})` |
|-|-|

### 例题Frida-labs 0x2

#### MainActivity类

| 12345678910111213141516171819202122232425262728293031323334353637383940 | `package` `com.ad2001.frida0x2;` `import` `android.os.Bundle;``import` `android.util.Base64;``import` `android.widget.TextView;``import` `androidx.appcompat.app.AppCompatActivity;``import` `javax.crypto.Cipher;``import` `javax.crypto.spec.IvParameterSpec;``import` `javax.crypto.spec.SecretKeySpec;` `/* loaded from: classes3.dex */``public class MainActivity extends AppCompatActivity {` `/* renamed from: t1 */``static TextView f103t1;` `/* JADX INFO: Access modifiers changed from: protected */``@Override` `// androidx.fragment.app.FragmentActivity, androidx.activity.ComponentActivity, androidx.core.app.ComponentActivity, android.app.Activity``public` `void` `onCreate(Bundle savedInstanceState) {``super``.onCreate(savedInstanceState);``setContentView(C0569R.layout.activity_main);``f103t1 = (TextView) findViewById(C0569R.C0572id.textview);``}` `public` `static` `void` `get_flag(``int` `a) {``if` `(a ==` `4919``) {``try` `{``SecretKeySpec secretKeySpec =` `new` `SecretKeySpec(``"HILLBILLWILLBINN"``.getBytes(),` `"AES"``);``Cipher cipher = Cipher.getInstance(``"AES/CBC/PKCS5Padding"``);``IvParameterSpec iv =` `new` `IvParameterSpec(``new` `byte``[``16``]);``cipher.init(``2``, secretKeySpec, iv);``byte``[] decryptedBytes = cipher.doFinal(Base64.decode(``"q7mBQegjhpfIAr0OgfLvH0t/D0Xi0ieG0vd+8ZVW+b4="``,` `0``));``String decryptedText =` `new` `String(decryptedBytes);``f103t1.setText(decryptedText);``}` `catch` `(Exception e) {``e.printStackTrace();``}``}``}``}` |
|-|-|

本用例程序就一个MainActivity类，类中存在一个未被使用的静态方法get_flag，在get_flag中比较了传入的参数，如果传入的参数为4919则解密flag，设置给txtView控件，那么根据之前给出的调用模板，我们hook代码如下：

#### Hook代码：

| 123456789101112 | `function hook(){``var MainActivity = Java.use(``"com.ad2001.frida0x2.MainActivity"``);``MainActivity.get_flag(``4919``);``}` `function main(){``Java.perform(function (){``hook();``})``}` `setImmediate(main);` |
|-|-|

但是我们发现如果使用的是setIMMediate(main)的话我们使用
`frida -U -f com.ad2001.frida0x2 -l .\Hook.js`
可能会导致hook不上的情况。
![file](https://bbs.kanxue.com/upload/attach/202403/979679_N9YPPZGHRVSMYZF.jpg)

##### 解决方法1

我们事先启动Frida 0x2应用程序。然后使用如下命令注入我们的脚本
`frida -U 'Frida 0x2' -l .\Hook.js`
![file](https://bbs.kanxue.com/upload/attach/202403/979679_2TV9RC2K8SVQ9S8.jpg)
本方法与之前的方法不同之处是该方法是直接hook入我们后台正在启动的程序，而之前的方法是根据包名再启动一个程序。

##### 解决方法2

当我们发现使用`解决方法1`能够成功hook的时候，就可以推断出，是由于我们启动main函数使用的是setImmediate(main)，是立即启动可能会导致脚本注入的速度比程序启动的速度快。因此我们可以改用`setTimeout(main,1000)`，也就是延迟1秒钟启动程序。
详情可见<https://www.cnblogs.com/fsjohnhuang/p/4151595.html>
![file](https://bbs.kanxue.com/upload/attach/202403/979679_E3TDAFGKFK5ASTF.jpg)

## 3、更改类中的静态变量

类似于如下写法static int code = 0;
使用static 修饰的变量则为静态变量。我们可以用如下方法更改静态变量。

| 123456 | `Java.perform(``function` `(){` `var` `<class_reference> = Java.use(``"<package_name>.<class>"``);``<class_reference>.<variable>.value = <value>;` `})` |
|-|-|

### 例题 Frida-labs 0x3

MainActivity类
![file](https://bbs.kanxue.com/upload/attach/202403/979679_HX9UXV2VP5BCJX5.jpg)
标记处我们可以发现，当Checker.code为512的时候点击按钮，程序则会解密并且将textView控件设置为Flag。

### Hook代码

| 1234567891011 | `function` `hook(){``var` `a = Java.use(``"com.ad2001.frida0x3.Checker"``);``a.code.value = 512;``}` `function` `main(){``Java.perform(``function` `(){``hook();``})``}``setImmediate(main);` |
|-|-|

## 4、调用非MainActivity,非静态方法

在JAVA代码中，如果创建了一个非静态的类，当我们需要使用这个类的时候需要new一个类的对象出来我们才能使用这个类的功能。类似代码如下：

| 12 | `Check ch =` `new` `Check();``String flag = ch.get_flag(``1337``);` |
|-|-|

那么在Java源码中需要new出来的实例，我们怎么使用Frida来实现呢？
模板如下：

| 1234567 | `Java.perform(``function``() {` `var` `<class_reference> = Java.use(``"<package_name>.<class>"``);``var` `<class_instance> = <class_reference>.$``new``();` `// Class Object``<class_instance>.<method>();` `// 调用方法` `})` |
|-|-|

### 例题Frida-labs 0x4

#### MainActivity：

![file](https://bbs.kanxue.com/upload/attach/202403/979679_6ASNSA37NURDUNJ.jpg)
MainActivity中没有任何东西。

#### Checker

![file](https://bbs.kanxue.com/upload/attach/202403/979679_NKBMPTNC6U5SBQ7.jpg)
Checker中出现了get_flag方法，返回了flag。则我们使用之前的模板来Hook

#### Hook代码：

| 12345678910111213141516 | `function` `hook(){``console.log(``"Hook Success!"``);``var` `Check = Java.use(``"com.ad2001.frida0x4.Check"``);``var` `Check_obj = Check.$``new``();``var` `String = Check_obj.get_flag(1337);``console.log(String);``}` `function` `main(){``Java.perform(``function` `(){``hook();` `})``}` `setImmediate(main);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_464DK4JS8S7FP7S.jpg)

## 5、调用MainActivity中的非静态方法

前面有提到过如果不是MainActivity中的方法我们使用.$new()可以创建一个实例。那么如果我们将这个使用到MainActivity会发生什么呢?

| 1234 | `function` `hook(){``var` `MainActivity = Java.use(``"com.ad2001.frida0x5"``);``var` `MainActivity_obj = MainActivity.$``new``();``}` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_TQARDHKX7HNDXTZ.jpg)
好吧，它崩溃了。那么这是什么原因呢？

直接使用Frida创建`MainActivity`或任何Android组件可能会很棘手，因为Android的生命周期和线程规则。Android组件，如`Activity`子类，依赖于应用程序上下文进行正确运行。在Frida中，您可能缺少必要的上下文。Android UI组件通常需要具有关联`Looper`的特定线程。如果涉及UI任务，请确保在具有活动`Looper`的主线程上执行。活动是较大的Android应用程序生命周期的一部分。创建`MainActivity`的实例可能需要应用处于特定状态，并且通过Frida管理整个生命周期可能并不直接。总之，为`MainActivity`创建实例并不是一个好主意。

那么这里的解决方案是什么呢？

当Android应用程序启动时，系统会创建`MainActivity`的一个实例（或AndroidManifest.xml文件中指定的启动器活动）。创建`MainActivity`实例是Android应用程序生命周期的一部分。因此，我们可以使用frida获取`MainActivity`的实例，然后调用`flag()`方法来获取我们的标志。

### 在现有实例上调用方法

在现有实例上调用方法可以很容易地通过Frida完成。为此，我们将使用两个API。

- `Java.performNow`：用于在Java运行时环境中执行代码的函数。
- `Java.choose`：在运行时枚举指定Java类（作为第一个参数提供）的实例。

让我展示一个模板给你。

| 12345678 | `Java.performNow(``function``() {``Java.choose(``'<包名>.<类名>'``, {``onMatch:` `function``(instance) {``// 待办事项``},``onComplete:` `function``() {}``});``});` |
|-|-|

这里有两个回调函数：

- **onMatch**
	- `onMatch`回调函数在`Java.choose`操作期间找到指定类的每个实例时执行。
	- 这个回调函数接收当前实例作为它的参数。
	- 您可以在`onMatch`回调中定义自定义操作，以在每个实例上执行。
	- `function(instance) {}`，`instance`参数表示目标类的每个匹配实例。您可以使用任何其他名称。
- **onComplete**
	- `onComplete`回调在`Java.choose`操作完成后执行操作或清理任务。此块是可选的，如果您在搜索完成后不需要执行任何特定操作，则可以选择将其留空。

### 例题Frida-labs 0x5

#### MainActivity

![file](https://bbs.kanxue.com/upload/attach/202403/979679_B34DXNNZTRSZHYV.jpg)
可以发现其中flag方法是未被调用的方法，并且是解密密文将Flag输出到TextView控件上。

#### BeginHook！

现在我们知道如何使用`Java.choose` API，让我们开始编写我们的frida脚本。

- 包名：`com.ad2001.frida0x5`
- 类名：`MainActivity`
- 函数名：`flag`

| 12345678 | `Java.performNow(``function``() {``Java.choose(``'com.ad2001.frida0x5.MainActivity'``, {``onMatch:` `function``(instance) {``// 待办事项``},``onComplete:` `function``() {}``});``});` |
|-|-|

让我们在成功找到`MainActivity`实例时包含一个`console.log`语句以打印一条消息。由于在枚举完成后我们没有任何特定的操作要执行，我们可以将`onComplete`块留空。

| 12345678 | `Java.performNow(``function``() {``Java.choose(``'com.ad2001.frida0x5.MainActivity'``, {``onMatch:` `function``(instance) {``console.log(``"找到实例"``);``},``onComplete:` `function``() {}``});``});` |
|-|-|

让我们启动Frida并注入我们的脚本。
![file](https://bbs.kanxue.com/upload/attach/202403/979679_Y9XDGKD3T8SZWCK.jpg)

#### Hook代码

| 12345678910111213141516171819 | `function` `hook(){``Java.choose(``'com.ad2001.frida0x5.MainActivity'``,{``onMatch:``function` `(MainActivity){``MainActivity.flag(1337);``console.log(``"Hook Success!"``);``},onComplete:``function` `(){` `}``})``}` `function` `main(){` `Java.perform(``function` `(){``hook();``})``}` `setImmediate(main);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_QDETCSVT4M94T9B.jpg)

## 6、MainActivity中非静态并且参数为非静态变量方法调用

### 例题Frida-labs 0x6

![file](https://bbs.kanxue.com/upload/attach/202403/979679_9SR734JYHJE6ZAB.jpg)
我们之前已经解决过类似的问题了。在这种情况下，我们有一个`get_flag()`方法，在应用程序中没有被调用。如果调用此方法，它将使用`AES`解密标志，并将标志设置在Textview中。如果我们检查`get_flag`方法，它只接受一个参数，这个参数是`Checker`类的一个实例。参数被命名为`A`，其类型是`Checker`。

| 123 | `public` `void` `get_flag(Checker A)` `throws` `NoSuchPaddingException, NoSuchAlgorithmException, InvalidKeyException, IllegalBlockSizeException, BadPaddingException {``// 方法体``}` |
|-|-|

在方法内部，它检查`A.num1`是否等于`1234`，以及`A.num2`是否等于`4321`。如果条件成立，该方法将继续使用AES解密加密字符串，并将解密后的结果设置在TextView中。因此，让我们检查一下Checker类。

![file](https://bbs.kanxue.com/upload/attach/202403/979679_NW4432SJY4QN9EE.jpg)

在Checker类中，我们有两个变量。

- num1
- num2

`num1`应该等于`1234`，`num2`应该等于`4321`，以满足`if`条件执行解密并设置标志的代码块。请记住，这个类也没有实例。

#### 解决方案

这个问题很容易解决，因为我们之前已经在上一篇帖子中做过了，唯一的区别是`get_flag`方法的参数是`Checker`类的一个对象。我将总结解决这个问题的步骤如下：

- 创建一个`Checker`类的实例。
- 将`num1`设置为1234，`num2`设置为4321。
- 获取`MainActivity`的实例。
- 使用实例作为参数调用`get_flag`方法。

让我们开始编写我们的frida脚本。

首先让我们创建`Checker`类的实例。

| 12 | `var` `checker = Java.use(``"com.ad2001.frida0x6.Checker"``);``var` `checker_obj = checker.$``new``();` `// 类对象` |
|-|-|

设置`num1`和`num2`的值。

| 12 | `checker_obj.num1.value = 1234;``checker_obj.num2.value = 4321;` |
|-|-|

现在让我们获取`MainActivity`的实例。我们可以使用`Java.performNow`和`Java.choose`API。我们在之前的挑战中已经做过了。

| 123456789 | `Java.performNow(``function``() {``Java.choose(``'com.ad2001.frida0x6.MainActivity'``, {``onMatch:` `function``(instance) {``console.log(``"找到实例"``);` `},``onComplete:` `function``() {}``});``})` |
|-|-|

让我们更新脚本，加入`Checker`类的实例。

| 1234567891011121314 | `Java.performNow(``function``() {``Java.choose(``'com.ad2001.frida0x6.MainActivity'``, {``onMatch:` `function``(instance) {``console.log(``"找到实例"``);` `var` `checker = Java.use(``"com.ad2001.frida0x6.Checker"``);``var` `checker_obj  = checker.$``new``();` `// 类对象``checker_obj.num1.value = 1234;``checker_obj.num2.value = 4321;` `},``onComplete:` `function``() {}``});``});` |
|-|-|

现在唯一要做的是通过传递`Checker`类的实例来调用`get_flag`方法。

| 123456789101112131415 | `Java.performNow(``function``() {``Java.choose(``'com.ad2001.frida0x6.MainActivity'``, {``onMatch:` `function``(instance) {``console.log(``"找到实例"``);` `var` `checker = Java.use(``"com.ad2001.frida0x6.Checker"``);``var` `checker_obj  = checker.$``new``();` `// 类对象``checker_obj.num1.value = 1234;` `// num1``checker_obj.num2.value = 4321;` `// num2``instance.get_flag(checker_obj);` `// 调用get_flag方法` `},``onComplete:` `function``() {}``});``});` |
|-|-|

让我们启动frida并运行我们的脚本。

| 1 | `PS C:\Users\ajind> frida` `-``U` `-``f com.ad2001.frida0x6` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_4WEU9NER55A2WXD.jpg)

当我们检查我们的手机时，TextView将显示标志。

## 7、Hook构造函数

**如果在ARM64 设备上不工作请看issue：<https://github.com/frida/frida/issues/1575>**

挂钩构造函数十分简单，与挂钩方法类似。让我为您提供一个模板。

| 12345678910 | `Java.perform(``function``() {``var` `<class_reference> = Java.use(``"<package_name>.<class>"``);``<class_reference>.$init.implementation =` `function``(<args>){` `/*` `*/` `}``});` |
|-|-|

我们可以看到，为了挂钩构造函数，我们可以使用`$init`关键字。

### 例题Frida-labs 0x7

#### MainActivity

![file](https://bbs.kanxue.com/upload/attach/202403/979679_SE7WW3P5NGCFYR3.jpg)
可以看到程序在使用flag方法判断之前，首先使用 Checker ch = new Checker(123, 321); 创建了一个Checker实例，则123 ， 321 分别对应A.num1与 A.num2。
那么我们只需要钩住构造函数即可。

#### Hook代码

| 123456789101112131415 | `function hook(){``var Checker = Java.use(``"com.ad2001.frida0x7.Checker"``);``Checker.$init.implementation = function (a,b){``console.log(``"Origin num"``,a,b);``this``.$init(``600``,``600``);``console.log(``"Hook Success"``);``}``}` `function main(){``Java.perform(function (){``hook();``})``}``setImmediate(main);` |
|-|-|

![file](https://bbs.kanxue.com/upload/attach/202403/979679_4FVPC754RNN4BJX.jpg)

---

# 回复

## 回复 by 秋狝 (#2)

*2024-3-4 10:53*

感谢分享

## 回复 by huangjw (#3)

*2024-3-4 11:50*

native层的操作大全也来一篇，还有最重要的检查frida的各自姿势在罗列下就更顶了

## 回复 by b!@nk (#4)

*2024-3-4 16:14*

通俗易懂

## 回复 by tian_chen (#5)

*2024-3-4 18:58*

大佬 Failure [INSTALL_FAILED_OLDER_SDK: Failed parse during installPackageLI: /data/app/vmdl1704171809.tmp/base.apk (at Binary XML file line #7): Requires newer sdk version #28 (current version is #27)] 这种只能换手机重新root吗

## 回复 by Shangwendada (#6)

*2024-3-4 19:38*

晚点会总结Native层的

## 回复 by Shangwendada (#7)

*2024-3-4 19:39*

>
> [tian_chen](https://bbs.kanxue.com/user-941362.htm)
>
>  大佬 Failure [INSTALL_FAILED_OLDER_SDK: Failed parse during installPackageLI: /data/app/vmdl1704171809 ...
>
>

安卓系统低了，换个高点的

## 回复 by devil_1 (#8)

*2024-3-6 21:12*

感谢大爹

## 回复 by mb_plkucays (#9)

*2024-3-16 04:12*

大神能帮忙解决风控的问题吗

## 回复 by ArmVMP (#10)

*2024-3-21 11:33*

楼主, Android 11(低版本正常)上获取大部分系统方法如android.hardware.camera.stopPreview的方法和android.telephony.TelephonyManager.getNeighboringCellInfo获取的都是同一个地址, 但是frida能够正常hook上面任意一个方法却不会互相影响(hook命中打印日志已知).一直没搞明白咋回事, 有什么建议吗? 或者说在11上有没有好的方法能获取到像低版本一样的正确地址?

## 回复 by ArmVMP (#11)

*2024-3-21 11:35*

11上获取的都是这个地址![image](https://bbs.kanxue.com/upload/attach/202403/927420_VYPW8DW3GDVRPK2.webp)

## 回复 by Shangwendada (#12)

*2024-3-21 21:06*

>
> [ArmVMP](https://bbs.kanxue.com/user-927420.htm)
>
>  11上获取的都是这个地址
>
>

没太了解过这个![image](https://bbs.kanxue.com/view/img/face/5.gif)

## 回复 by 浮虚千年 (#13)

*2024-4-1 17:39*

>
> [devil_1](https://bbs.kanxue.com/user-969875.htm)
>
>  感谢大爹
>
>

？好好好被我抓到了吧

## 回复 by 养只猫不好么 (#14)

*2024-7-12 18:05*

感谢分享

## 回复 by shanzj (#15)

*2024-12-7 22:53*

佬，我想请问一下protected这个修饰符咋hook啊![image](https://bbs.kanxue.com/view/img/face/006.gif)
