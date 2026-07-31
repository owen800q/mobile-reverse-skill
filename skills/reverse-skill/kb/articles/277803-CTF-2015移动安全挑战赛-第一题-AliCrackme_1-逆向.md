---
title: '[原创]CTF 《2015移动安全挑战赛》第一题 AliCrackme_1 逆向'
url: https://bbs.kanxue.com/thread-277803.htm
tid: 277803
author: 行简
date: '2023-06-28'
tags: [Android安全, 原创, 逆向分析, 漏洞相关, HOOK注入]
crawled_at: '2026-07-31T14:42:32+08:00'
replies: 1
---

# 0x01 前言

路漫漫其修远兮，吾将上下而求索。
看雪ctf板块中：
![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_HBPZFJPK4DSEF9K.png)

# 0x02 分析

## 2.1 入手点定位

安装apk，需逆向寻找正缺的密码：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_SGUXMQKT3W65Y7C.png)

将AliCrackme_1.apk使用jadx打开，从提示信息入手，搜索：密码不对，请继续破解。
可在资源文件中定位到：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_TRSPFS6EVEQTYAS.png)
继续搜索dialog_error_tips可定位到MainActivity->onClick()方法中：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_5RHANRYTAXECF3P.png)

## 2.2 onClick()方法刨析

看代码：

| 12345678910111213141516171819202122232425262728 | `public void onClick(View v) {``String password` `=` `edit.getText().toString();``String table` `=` `MainActivity.this.getTableFromPic();``String pw` `=` `MainActivity.this.getPwdFromPic();``Log.i(``"lil"``,` `"table:"` `+` `table);``Log.i(``"lil"``,` `"pw:"` `+` `pw);``String enPassword` `=` `"";``try` `{``enPassword` `=` `MainActivity.bytesToAliSmsCode(table, password.getBytes(``"utf-8"``));``Log.i(``"lil"``,` `"enPassword:"` `+` `enPassword);``} catch (UnsupportedEncodingException e) {``e.printStackTrace();``}``if` `(pw` `=``=` `null \|\| pw.equals("") \|\| !pw.equals(enPassword)) {``AlertDialog.Builder builder` `=` `new AlertDialog.Builder(MainActivity.this);``builder.setMessage(R.string.dialog_error_tips);``builder.setTitle(R.string.dialog_title);``builder.setPositiveButton(R.string.dialog_ok, new DialogInterface.OnClickListener() {` `/``/` `from` `class``: com.example.simpleencryption.MainActivity.``1.1``@Override` `/``/` `android.content.DialogInterface.OnClickListener``public void onClick(DialogInterface dialog,` `int` `which) {``dialog.dismiss();``}``});``builder.show();``return``;``}``MainActivity.this.showDialog();``}` |
|-|-|

翻译成大白话，大致流程如下：
1、获取输入框中的密码字符串。
2、从 MainActivity 类中获取图片表格数据和密码数据，分别存储在 table 和 pw 变量中。
3、将表格数据和密码数据输出到日志信息中。
4、将密码字符串转换为字节数组，并使用 MainActivity 类中的 bytesToAliSmsCode() 方法进行加密。加密后的结果存储在 enPassword 变量中，并输出到日志信息中。
5、检查用户输入密码是否为空或与密码pw是否匹配，如果为空或不匹配，则创建一个包含错误提示的对话框，并显示给用户。
6、如果密码正确，则调用 MainActivity 类中的 showDialog() 方法显示一个对话框。

## 2.3 bytesToAliSmsCode()方法刨析

跟进 bytesToAliSmsCode() 方法：

| 1234567 | `public static String bytesToAliSmsCode(String table, byte[] data) {``StringBuilder sb` `=` `new StringBuilder();``for` `(byte b : data) {``sb.append(table.charAt(b &` `255``));``}``return` `sb.toString();``}` |
|-|-|

传入两个参数table和data，table是从MainActivity.this.getTableFromPic();中得到，而data是传入的密码。
声明一个 StringBuilder 对象 sb，用于拼接字符串。
遍历字节数组 data 中的每个字节：
将当前字节与 255 进行按位与运算，得到一个值范围在 0 到 255 之间的结果。
使用 table 字符串的对应位置字符替换当前字节，并将替换后的字符追加到 sb 中。
返回拼接完成后的字符串 sb.toString()。

## 2.4 hook 分析

pw的来源：

| 1 | `String pw` `=` `MainActivity.this.getPwdFromPic();` |
|-|-|

hook一下pw、table、data数据，hook代码：

| 12345678910111213141516 | `Java.perform(function(){``var MainActivity` `=` `Java.use(``"com.example.simpleencryption.MainActivity"``);``MainActivity[``"getPwdFromPic"``].implementation` `=` `function () {``var ret` `=` `this.getPwdFromPic();``console.log(``'\npw value is '` `+` `ret);``return` `ret;``};` `var MainActivity` `=` `Java.use(``"com.example.simpleencryption.MainActivity"``);``MainActivity[``"bytesToAliSmsCode"``].implementation` `=` `function (table, data) {``console.log(``'table: '` `+` `table` `+` `', '` `+` `'data: '` `+` `JSON.stringify(data));``var ret` `=` `this.bytesToAliSmsCode(table, data);``console.log(``'enPassword value is '` `+` `ret);``return` `ret;``};``});` |
|-|-|

输入123456，hook 结果：

>
> pw value is 义弓么丸广之
> table: 一乙二十丁厂七卜人入八九几儿了力乃刀又三于干亏士工土才寸下大丈与万上小口巾山千乞川亿个勺久凡及夕丸么广亡门义之尸弓己已子卫也女飞刃习叉马乡丰王井开夫天无元专云扎艺木五
> 支厅不太犬区历尤友匹车巨牙屯比互切瓦止少日中冈贝内水见午牛手毛气升长仁什片仆化仇币仍仅斤爪反介父从今凶分乏公仓月氏勿欠风丹匀乌凤勾文六方火为斗忆订计户认心尺引丑巴孔队办以允予
> 劝双书幻玉刊示末未击打巧正扑扒功扔去甘世古节本术可丙左厉右石布龙平灭轧东卡北占业旧帅归且旦目叶甲申叮电号田由史只央兄叼叫另叨叹四生失禾丘付仗代仙们仪白仔他斥瓜乎丛令用甩印乐,
> data: [49,50,51,52,53,54]
> enPassword value is 么广亡门义之
>
>
>

那么只需让输入的密码经过bytesToAliSmsCode()方法转换后的值会等于pw，即：义弓么丸广之。

# 0x03 破解

整个分析下来其实逻辑已经很明白了，让bytesToAliSmsCode()方法转换后的值会等于pw即可。
写脚本解密，代码中有详细注释：

| 12345678910111213141516171819 | `def` `AliSmsCodeTobytes(table, pw):``# 遍历密码中的每个字符``for` `i` `in` `pw:``# 遍历密码表中的每个字符串``for` `j` `in` `range``(``len``(table)):``# 如果当前字符存在于密码表的某个字符串中``if` `i` `in` `table[j]:``# 打印该字符串所对应的字符``print``(``chr``(j), end``=``'')` `def` `main():``table` `=` `"一乙二十丁厂七卜人入八九几儿了力乃刀又三于干亏士工土才寸下大丈与万上小口巾山千乞川亿个勺久凡及夕丸么广亡门义之尸弓己已子卫也女飞刃习叉马乡丰王井开夫天无元专云扎艺木五支厅不太犬区历尤友匹车巨牙屯比互切瓦止少日中冈贝内水见午牛手毛气升长仁什片仆化仇币仍仅斤爪反介父从今凶分乏公仓月氏勿欠风丹匀乌凤勾文六方火为斗忆订计户认心尺引丑巴孔队办以允予劝双书幻玉刊示末未击打巧正扑扒功扔去甘世古节本术可丙左厉右石布龙平灭轧东卡北占业旧帅归且旦目叶甲申叮电号田由史只央兄叼叫另叨叹四生失禾丘付仗代仙们仪白仔他斥瓜乎丛令用甩印乐"``pw` `=` `"义弓么丸广之"``# 调用AliSmsCodeTobytes函数``AliSmsCodeTobytes(table, pw)` `if` `__name__` `=``=` `'__main__'``:``# 调用main函数``main()` |
|-|-|

结果：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202306/945390_FVKG834W6RC9FCC.png)

完结撒花。

---

# 回复

## 回复 by 秋狝 (#2)

*2023-6-28 11:19*

感谢分享
