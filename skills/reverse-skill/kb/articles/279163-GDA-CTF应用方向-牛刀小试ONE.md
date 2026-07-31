---
title: '[原创]GDA CTF应用方向：牛刀小试ONE'
url: https://bbs.kanxue.com/thread-279163.htm
tid: 279163
author: 梦幻的彼岸
date: '2023-10-09'
tags: [Android安全, 原创, 基础理论, 工具脚本]
crawled_at: '2026-07-31T14:37:33+08:00'
replies: 1
---

# 简介

首发：<https://sec-in.com/article/2269>

作者：梦幻的彼岸

测试程序来源：<https://github.com/num1r0/android_crackmes>

本篇文章涉及工具：GDA

# crackme_0x01

通过快捷按钮进入APK入口点进行分析，如下图所示：

![image](https://bbs.kanxue.com/upload/attach/202310/767964_396RKXEG4BY4W8D.webp)

## 入口点代码

![image](https://bbs.kanxue.com/upload/attach/202310/767964_QZ3VZDFYE2NUEQP.webp)

- 代码解析

这段代码定义了一个名为MainActivity的Android应用程序类，它继承自AppCompatActivity。此类中定义了两个私有字段，name和description，分别用于存储应用程序的名称和描述。MainActivity的构造函数中，对这两个字段进行了初始化。

follow_clicked方法用于处理点击事件，它尝试打开一个指向特定Twitter用户的链接。如果第一种方式失败，它会尝试使用另一种方式打开链接。

onCreate方法是Android应用程序的生命周期方法之一，在应用程序启动时运行。在这个函数中，隐藏了应用程序的ActionBar，设置了应用程序的布局，并设置了一个点击监听器，当用户点击'submit'按钮时，会执行MainActivity$1类的实例的onClick方法。

## 关键点MainActivity$1

![image](https://bbs.kanxue.com/upload/attach/202310/767964_QQMTT2PZ5SC3JX8.webp)

代码内容

![image](https://bbs.kanxue.com/upload/attach/202310/767964_NMCN7THVTD7CRB6.webp)

- 代码解析

这段代码是一个名为MainActivity$1的Java的匿名内部类，它实现了View$OnClickListener接口，这个接口是Android开发中用于处理点击事件的。

分析一下这个类的各个部分：

1. final MainActivity this$0和 final EditText val$edtTxt这两个字段是构造函数MainActivity$1(MainActivity p0,EditText p1)的参数，其中this$0是对包含它的外部类MainActivity的引用，val$edtTxt是一个EditText对象，可能是用户在界面上输入的文本框。并调用 super() 方法初始化其他类属性
2. onClick(View p0) 方法是View.OnClickListener接口的一部分，当用户点击时，它会被调用。在这个方法中，通过FlagGuard类的getFlag方法获取一个名为flag的字符串，并进行判断，如果flag不为null，那么创建一个AlertDialogBuilder 实例，将显示一个标题为"Congratulations!"，内容为"The flag is: "加上返回字符串的对话框。否则，将显示一个标题为"Nope!"，内容为"Wrong password -> No flag :))"的对话框。对于这两个对话框，都设置了PositiveButton，并且为这个按钮设置了点击事件处理器。这两个点击事件处理器是MainActivity$1$1和MainActivity$1$2，它们是MainActivity$1的子类，可能是用来处理点击"OK"按钮的事件。

这里找到了关键判断方法getFlag，双击进入查看

## 关键点getFlag

- 代码内容

![image](https://bbs.kanxue.com/upload/attach/202310/767964_JB3RCCJ4UTAHEUU.webp)

- 解析代码

这段代码定义了一个名为FlagGuard的Java类，它具有以下功能：

1. 成员变量：
- flag：一个用于存储解密的字符串的变量。
- pad：一个包含小写字母的字符串，用于解密过程。
- scr_flag：一个包含混淆字符的字符串，这些字符将被解密。

3. 构造方法：
- 当创建一个新的FlagGuard对象时，构造方法会初始化pad和scr_flag变量，并将flag变量设置为空字符串。

5. unscramble() 方法：
- 一个私有方法，用于解码字符串。这个方法首先定义了一个 StringBuilder 对象 str，然后从"qw4r_q0c_nc4nvx3_0i01_srq82q8mx"字符串中遍历每个字符，将其与"abcdefghijklmnopqrstuvwxyz"字符串中的字符进行比较，计算它们在字母表中的位置，并将结果添加到 StringBuilder 对象 str 中。最后，返回 str 字符串。

7. getFlag(String p0) 方法：
- 一个公共方法，用于获取 flag 字符串。这个方法首先检查参数 p0 是否等于 Data 类的 getData() 方法返回的字符串，如果是，则调用 unscramble() 方法解码字符串并返回结果；否则，返回 null。

又看到关键点了用来判断并输出内容，思路，更改判断不输出null,或查看getData方法涉及内容以查找对比的字符串很多概率就是flag

## 修改判断

现在修改位置右键点击切换代码功能

![image](https://bbs.kanxue.com/upload/attach/202310/767964_7NXC227HSNXTPXR.webp)

smail代码

![image](https://bbs.kanxue.com/upload/attach/202310/767964_6T978S5R5QBJCZM.webp)

这里两个思路一个是NOP填充判断或修改判断指令将if-eqz修改为if-nez

两种修改思路都演示下

- NOP

在要NOP的位置右键点NOP按钮

![image](https://bbs.kanxue.com/upload/attach/202310/767964_92XWJQKG2SWWJ8Z.webp)

修改后的效果

![image](https://bbs.kanxue.com/upload/attach/202310/767964_NHQNEA8J6EB8F3Z.webp)

此时按r键保存修改

![image](https://bbs.kanxue.com/upload/attach/202310/767964_Z6X66EUTGDNG44Z.webp)

点击OK进行之后的安装测试步骤

选择链接的设备

![image](https://bbs.kanxue.com/upload/attach/202310/767964_KZP64K5W6PNQQS3.webp)

![image](https://bbs.kanxue.com/upload/attach/202310/767964_35NAT7AYB9DXBFT.webp)

安装完毕

![image](https://bbs.kanxue.com/upload/attach/202310/767964_WQMZ7MCZ6UW5P9Z.webp)

![image](https://bbs.kanxue.com/upload/attach/202310/767964_G32Z7Y463VTZQC9.webp)

输入测试

![image](https://bbs.kanxue.com/upload/attach/202310/767964_HZZ33SQB7EBHJ8F.webp)

弹出了flag

![image](https://bbs.kanxue.com/upload/attach/202310/767964_MBQBW8Y56AMQD8Z.webp)

- 修改指令

因之前NOP填充过，此时需要恢复DEX数据重新加载

![image](https://bbs.kanxue.com/upload/attach/202310/767964_5DUBADRSFYAH9QN.webp)

恢复并重新加载后

![image](https://bbs.kanxue.com/upload/attach/202310/767964_C497UZ73FE4H24N.webp)

在要修改的位置按M进入修改模式或右键修改指令功能

![image](https://bbs.kanxue.com/upload/attach/202310/767964_HFMUGR555E6MSMT.webp)

回车确定修改后的效果

![image](https://bbs.kanxue.com/upload/attach/202310/767964_RRG4XS6XZ6RE8FX.webp)

这里解析下

if-nez: 对比如果不相等则跳转

if-eqz: 对比如果相等则跳转

这里修改为if-nez后达到输入错误的flag导致对比不先等以输出内容的目的

保存安装测试

![image](https://bbs.kanxue.com/upload/attach/202310/767964_T6AENAXBW3C4YXH.webp)

同样获取到flag

## 查看getData

getData位置双击

- 代码如下

![image](https://bbs.kanxue.com/upload/attach/202310/767964_7CDJD7RDTQJPW5M.webp)

- 代码分析

这是一个名为 Data 的 Java 类，它包含一个私有权限的 String 类型的变量 secret，以及两个公共方法：Data() 构造函数和 getData() 方法，但是，`getData` 方法并没有返回 `secret` 字段的值，而是返回了一个硬编码的字符串("s3cr37_p4ssw0rd_1337")。

前后分析，这个字符串就是对比的关键了

修改判断apk测试

![image](https://bbs.kanxue.com/upload/attach/202310/767964_42PDSBUH28CQT7E.webp)

看这样就是关键内容了，和正确的结果对比返回了错误的数据，

安装未修改apk验证

![image](https://bbs.kanxue.com/upload/attach/202310/767964_QW669N57Z67E3YD.webp)

验证成功

# crackme_0x02

## 入口函数

同样的方法入口点查看

![image](https://bbs.kanxue.com/upload/attach/202310/767964_VJ78KPBAXT9SUT5.webp)

这里代码和之前类似就不讲解了

## 关键点MainActivity$1

![image](https://bbs.kanxue.com/upload/attach/202310/767964_HE4FNCY8YVRS64H.webp)

这里代码和之前类似就不讲解了

## 关键点getFlag

- 代码内容

![image](https://bbs.kanxue.com/upload/attach/202310/767964_7GMV69SMKEPP3QY.webp)

- 代码解析

这段代码定义了一个名为 FlagGuard 的Java类。以下是对这个类的详细解析：

1. 成员变量：
- c1: 一个整型变量。
- c2: 一个双精度浮点型变量。
- flag: 一个字符串变量，用于存储解密的标志。
- pad: 一个字符串，包含小写字母，用于解密过程。
- scr_flag: 一个字符串，包含混淆的字符，这些字符将被解密。

3. 构造方法：
- 当一个新的 FlagGuard 对象被创建时，构造方法会被调用。它会初始化 pad 和 scr_flag 变量，并将 flag 变量设置为空字符串。同时，它也会设置 c1 和 c2 的值。

5. unscramble() 方法：
- 这是一个私有方法，用于解密 scr_flag。
- 它通过遍历 scr_flag 中的每个字符，然后查找该字符在 pad 中的位置，并用该位置减去一个固定值（这个值是通过一些复杂的计算得出的，包括 c1 和 c2 的乘积）来得到一个索引。然后使用此索引从 pad 中选择一个字符，并添加到结果字符串中。
- 如果字符在 pad 中找不到（即索引小于0），则直接将该字符添加到结果字符串中。
- 最后，该方法返回解密后的字符串。在整个过程中，该方法会使用 Log.e 打印一些调试信息。

7. getFlag(Context p0, String p1) 方法：
- 这是一个公共方法，接受一个 Context 对象和一个字符串作为参数。
- 如果传入的字符串与另一个类（可能是 Data）的 getData(p0) 方法返回的字符串相同，则调用 unscramble() 方法并返回解密后的字符串。
- 如果传入的字符串不匹配，则返回null。

同样思路测试

![image](https://bbs.kanxue.com/upload/attach/202310/767964_PJE9F4V82DQTGAJ.webp)

![image](https://bbs.kanxue.com/upload/attach/202310/767964_HQNYYT298H2WHYP.webp)

轻松获得flag

## 关键点getDate

![image](https://bbs.kanxue.com/upload/attach/202310/767964_6V7R9BS7GE67H7T.webp)

这段 Java 代码定义了一个名为Data的类，位于com.entebra.crackme0x02.Data包中。该类有以下内容：

导入了一些所需的类：

java.lang.Object：继承自 Java 的基类Object。

android.content.Context：表示 Android 应用程序中的上下文对象，用于访问应用程序的资源。

java.lang.String：表示 Java 中的字符串类型。

1. 成员变量：
- secret：这是一个私有字符串变量，它存储了一个秘密字符串。

3. 构造方法：
- public void Data()：这是类的构造方法，它没有参数。在这个方法中，调用了父类的构造方法（super()），并将secret初始化为一个空字符串。

5. 方法：
- public String getData(Context p0)：这是一个公共方法，它接收一个Context类型的参数，名为p0。这个方法从Context对象中获取字符串资源R.string.secret的值，并将其赋值给secret。然后返回secret的值。
- 这个资源文件的路径通常是在`res/values/strings.xml`

![image](https://bbs.kanxue.com/upload/attach/202310/767964_877FNM7YENGYUHJ.webp)

```
<string name="secret">s0m3_0th3r_s3cr3t_passw0rd</string>
```

`验证`

![image](https://bbs.kanxue.com/upload/attach/202310/767964_DUKZGZEFV9DA25H.webp)

# crackme_0x03

## 入口函数

同样通过快捷按键进入

![image](https://bbs.kanxue.com/upload/attach/202310/767964_GM57B79ZQ3AYWEA.webp)

## 关键点MainActivity$1

![image](https://bbs.kanxue.com/upload/attach/202310/767964_86PQ6WQG2ASJQM8.webp)

## 关键点getFlag

![image](https://bbs.kanxue.com/upload/attach/202310/767964_33KCG3RJZKJYTG3.webp)

- 代码解析

这段 Java 代码定义了一个名为 FlagGuard 的类。该类包含一个名为 flag 的字符数组，以及一个名为 generate 的私有方法。generate 方法的主要目的是生成一个字符串，该字符串基于输入的字符串 p0（在 getFlag 方法中使用）。

首先，代码导入了所需的类，如 Object、String、StringBuilder 和 android.os.Build$VERSION 等。

 接下来，FlagGuard 类的构造函数创建了一个名为 uocharArray 的字符数组，并将其赋值给 this.flag。

generate 方法开始时，定义了几个整数变量，然后创建了一个名为 ointArray 的整数数组。接着，创建了一个名为 str 的字符串构建器，用于存储生成的字符串。同时，创建了一个名为 ointArray1 的整数数组，用于在后续的循环中进行操作。

在 if 语句中，检查 Build$VERSION.CODENAME 的长度是否大于 0。如果满足条件，将执行一个 while 循环。在循环中，对 ointArray1 数组的元素进行了一系列操作，如赋值、移位、相加等。这些操作的具体目的尚不明确，可能与生成字符串有关。

在另一个 if 语句中，如果输入字符串 p0 满足 Data 类的 isPasswordOk 方法，则调用 generate 方法生成字符串。

在 generate 方法中，首先检查输入字符串 p0 是否满足条件。如果满足，将执行一个 for 循环，遍历整数数组 ointArray，并将每个元素的值存储在 flag 数组中。最后，将 flag 数组拼接到字符串构建器 str 中，并返回结果。

总之，这段代码的主要目的是生成一个字符串，该字符串可能与密码验证有关。具体的生成逻辑涉及到一系列复杂的数学运算，但具体含义尚不明确。

总结：可修改判断或查看 generate 方法生成字符串或isPasswordOk内容

## 修改

![image](https://bbs.kanxue.com/upload/attach/202310/767964_N6WQ5MQ9982UHUZ.webp)

轻松获取flag

![image](https://bbs.kanxue.com/upload/attach/202310/767964_7MWSPJSK64W5HSK.webp)

## 关键点generate

![image](https://bbs.kanxue.com/upload/attach/202310/767964_VSDMZ9MNQVGS5S5.webp)

- 代码解析

这段 Java 代码的主要功能是生成一个字符串，其中包含一个整数数组和一些特定的操作。以下是代码的详细解析：

1. 定义变量：定义了一些整数变量和 StringBuilder 变量。
2. 创建整数数组：创建一个名为 ointArray1 的整数数组，其长度为 i（20），并用数组初始化列表初始化。
3. 设置数组元素：将数组 ointArray1 的所有元素设置为 27。
4. 判断条件：判断 Build$VERSION.CODENAME 的长度是否大于 0，如果大于 0，则执行以下操作；否则，执行第 9 行的代码。
5. 循环：使用一个 while 循环，当 i2 小于 i3（5）时，执行循环体。在循环体内，根据 i2 的值进行不同的操作，包括设置数组元素、交换元素位置等。每次循环结束后，i2 自增 1。当 i2 大于等于 i3 时，跳出循环。
6. 设置数组元素：将数组 ointArray1 的 i5（10）个元素设置为 73，将数组 ointArray1 的 13、12、i4（11）个元素分别设置为 79，将数组 ointArray1 的 7 个元素设置为 79 - 2。
7. 循环：使用一个 while 循环，当 i2 小于 i（20）时，执行循环体。在循环体内，根据 i2 的值进行不同的操作，包括设置数组元素、交换元素位置等。每次循环结束后，i2 自增 1。当 i2 大于等于 i 时，跳出循环。
8. 返回结果：返回 StringBuilder 变量 str 的值，即生成的字符串。
整个函数通过复杂的循环和条件语句，对整数数组进行了一系列操作，最终生成了一个包含特定字符的字符串。

## 关键点isPasswordOk

![image](https://bbs.kanxue.com/upload/attach/202310/767964_KF34YPTV5YNVJ6U.webp)

- 代码解析

这段 Java 代码定义了一个名为 Data 的类，主要用于处理密码验证。以下是代码的解析：

1. 类定义和静态代码块：定义了一个名为 Data 的类，同时定义了一个静态的 lastError 变量，默认为"Unknown error..."。
2. 构造函数：Data 类的构造函数，设置了以下属性：
- short_password_message：密码太短的消息
- long_password_message：密码太长的消息
- wrong_password_message：输入错误的密码的消息
- password_length：密码长度，默认为 6
- password_hash：用于验证密码的 MD5 哈希值，默认为"ac43bb53262e4edd82c0e82a93c84755"

4. MD5Compare 方法：用于比较两个字符串的 MD5 哈希值是否相等。如果相等，返回 true；否则返回 false。
5. getData 方法：返回 Data 类的 MD5 哈希值，即"ac43bb53262e4edd82c0e82a93c84755"
6. getLastError 方法：返回 lastError 变量的值，用于显示最后一个错误信息

看了这里要通过反解md5来获取关键信息

![image](https://bbs.kanxue.com/upload/attach/202310/767964_ZYPBYG4JMJ93DN9.webp)

---

# 回复

## 回复 by 秋狝 (#2)

*2023-10-12 09:29*

感谢分享
