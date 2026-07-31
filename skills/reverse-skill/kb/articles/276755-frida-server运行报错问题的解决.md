---
title: '[原创]frida-server运行报错问题的解决'
url: https://bbs.kanxue.com/thread-276755.htm
tid: 276755
author: madsu
date: '2023-04-04'
tags: [Android安全, 原创, 源码框架]
crawled_at: '2026-07-31T14:50:44+08:00'
replies: 7
---

刚刚开始学Android逆向，发现Frida是个好东西，于是赶紧下载研究一番。
下载源码编译，切换到最新版16.0.11, 编译之前注意先更新nodejs

| 12 | `wget` `-``qO``-` `https:``/``/``deb.nodesource.com``/``setup_16.x \| sudo` `-``E bash` `-``sudo apt``-``get install` `-``y nodejs` |
|-|-|

然后执行

| 12 | `make core``-``android``-``arm64` `make tools``-``linux``-``x86_64 PYTHON``=``$HOME``/``miniconda3``/``bin``/``python` |
|-|-|

就可以成功生成frida-server以及frida相关tools，于是push到手机上执行

| 12 | `redfin:``/``data``/``local``/``tmp` `# ./frida-server` `{``"type"``:``"error"``,``"description"``:``"Error: Java API not available"``,``"stack"``:``"Error: Java API not available\n    at _checkAvailable (frida/node_modules/frida-java-bridge/index.js:298:1)\n    at _.perform (frida/node_modules/frida-java-bridge/index.js:203:1)\n    at /internal-agent.js:490:6"``,``"fileName"``:``"frida/node_modules/frida-java-bridge/index.js"``,``"lineNumber"``:``298``,``"columnNumber"``:``1``}` |
|-|-|

报错了...额，继续往下试试

 把手机上的名为com.example.myapplication的demo app放到前台，然后注入一个helloword级别的js

| 123456789 | `setTimeout(``function() {``Java.perform(function() {``console.log(``"Hello frida!"``)``})``}``)` `/``/``test.js` |
|-|-|

然后执行

| 12345678910111213 | `(base)` `/``data``/``code``/``OpenSource``/``crack``/``frida``/``build``/``frida``-``linux``-``x86_64``/``bin` `(``16.0``.``11` `✔) .``/``frida` `-``U` `-``l ..``/``..``/``..``/``..``/``frida_script``/``test.js com.example.myapplication``____``/` `_  \|   Frida` `16.0``.``11` `-` `A world``-``class` `dynamic instrumentation toolkit``\| (_\| \|``> _  \|   Commands:``/``_``/` `\|_\|` `help`      `-``> Displays the` `help` `system``. . . .` `object``?` `-``> Display information about` `'object'``. . . .       exit``/``quit` `-``> Exit``. . . .``. . . .   More info at https:``/``/``frida.re``/``docs``/``home``/``. . . .``. . . .   Connected to AOSP on redfin (``id``=``0A051FDD4003BW``)``Failed to spawn: cannot read properties of undefined (reading` `'getRunningAppProcesses'``)` |
|-|-|

咳，出师不利，不过反正我也是做c++开发的，虽然不懂javascript, 连蒙带猜也能看个差不多，那就研究研究报错原因吧。

 从现有信息来看，第一怀疑对象应该是那个报错"Error: Java API not available", 也指明了报错位置at _checkAvailable (frida/node*modules/frida-java-bridge/index.js:298:1) at* .perform (frida/node_modules/frida-java-bridge/index.js:203:1)\n ，那就在源码里搜索下。
发现这个index.js位于build/tmp-android-arm64/frida-gum/bindings/gumjs/node_modules/frida-java-bridge目录,
然后看下perform实现

| 12345678910111213141516 | `perform (fn) {``this._checkAvailable();` `if` `(!this._isAppProcess() \|\| this.classFactory.loader !``=``=` `null) {``try` `{``this.vm.perform(fn);``} catch (e) {``Script.nextTick(()` `=``> { throw e; });``}``}` `else` `{``this._pendingVmOps.push(fn);``if` `(this._pendingVmOps.length` `=``=``=` `1``) {``this._performPendingVmOpsWhenReady();``}``}``}` |
|-|-|

这个函数第一行就是_checkAvailable,跟进去看看

| 12345 | `_checkAvailable () {``if` `(!this.available) {``throw new Error(``'Java API not available'``);``}``}` |
|-|-|

果然报错就是在这里，那么关键的判断就是available了，再跳过去看看

| 123456789101112131415161718192021222324252627282930313233343536 | `get available () {``return` `this._tryInitialize();``}` `_tryInitialize () {``if` `(this._initialized) {``return` `true;``}` `if` `(this._apiError !``=``=` `null) {``throw this._apiError;``}` `let api;``try` `{``api` `=` `getApi();``this.api` `=` `api;``} catch (e) {``this._apiError` `=` `e;``throw e;``}``if` `(api` `=``=``=` `null) {``return` `false;` `/``/``只有这里返回为false``}` `const vm` `=` `new VM(api);``this.vm` `=` `vm;` `Types.initialize(vm);``ClassFactory._initialize(vm, api);``this.classFactory` `=` `new ClassFactory();` `this._initialized` `=` `true;` `return` `true;``}` |
|-|-|

那么只有一种可能，就是getApi()返回为null，再跟进去看看，这个getApi的有几层跳转如下

| 123456789101112131415161718192021222324252627282930 | `/``/` `index.js``const getApi` `=` `require(``'./lib/api'``);` `/``/` `.``/``lib``/``api.js``let { getApi, getAndroidVersion }` `=` `require(``'./android'``);``try` `{``getAndroidVersion();``} catch (e) {``getApi` `=` `require(``'./jvm'``).getApi;``}``module.exports` `=` `getApi;` `/``/` `.``/``lib``/``android.js``function getApi () {``if` `(cachedApi` `=``=``=` `null) {``cachedApi` `=` `_getApi();``}``return` `cachedApi;``}` `function _getApi () {``const vmModules` `=` `Process.enumerateModules()``.``filter``(m` `=``>` `/``^lib(art\|dvm).so$``/``.test(m.name))``.``filter``(m` `=``> !``/``\``/``system\``/``fake``-``libs``/``.test(m.path));``if` `(vmModules.length` `=``=``=` `0``) {``return` `null;` `/``/` `这里返回了null``}` `/``/``以下代码省略...``}` |
|-|-|

看代码的意思是进程内没找到加载的libart.so或者libdvm.so，真奇怪了，你可是android进程，没有虚拟机咋跑的？

 那就看下这个进程加载了什么，首先找到进程id

| 123 | `redfin:``/` `# ps -ef \| grep com.example.myapplication` `u0_a108` `27168` `21776` `0` `11``:``18``:``29` `?` `00``:``00``:``03` `com.example.myapplication``root` `28255` `28250` `35` `14``:``11``:``06` `pts``/``1` `00``:``00``:``00` `grep com.example.myapplication` |
|-|-|

然后检查下maps

| 12 | `redfin:``/` `# cat /proc/27168/maps \| grep libart.so` `1``\|redfin:``/` `#` |
|-|-|

果然没有，见鬼了,我把maps的输出保存下来，在编辑器里查看才发现了端倪，原来进程加载的so里有一个libartd.so，因为这个手机是pixel5,系统是我自己下载AOSP编译的，选择的是eng版，这样编出来的系统so都是debug版，也就意味着后缀都有一个d，难怪frida找不到。

 知道了原因，那解决方案就简单了，把那段查找libart.so的代码改成查找libartd.so即可。不过还有一个问题，这个frida-java-bridge是编译的时候从网上下载的，我们本地修改会被覆盖，那么就得研究下frida的编译系统了，让它使用我们本地的frida-java-bridge。

 首先在源码里搜索frida-java-bridge,果不其然，是在一个generate-runtime.py里面，代码如下

| 12345678910111213141516171819202122232425262728293031323334 | `XACT_DEPS` `=` `{``"frida-java-bridge"``:` `"6.2.3"``,``"frida-objc-bridge"``:` `"7.0.2"``,``"frida-swift-bridge"``:` `"2.0.6"``}`  `def` `generate_runtime(backends, arch, endian, input_dir, gum_dir, capstone_incdir, libtcc_incdir, quickcompile, output_dir):``frida_compile` `=` `output_dir` `/` `"node_modules"` `/` `".bin"` `/` `make_script_filename(``"frida-compile"``)``if` `not` `frida_compile.exists():``pkg_files` `=` `[output_dir` `/` `"package.json"``, output_dir` `/` `"package-lock.json"``]``for` `f` `in` `pkg_files:``if` `f.exists():``f.unlink()``(output_dir` `/` `"tsconfig.json"``).write_text(``"{ \"files\": [], \"compilerOptions\": { \"typeRoots\": [] } }"``, encoding``=``"utf-8"``)` `node_modules` `=` `output_dir` `/` `"node_modules"``if` `node_modules.exists():``shutil.rmtree(node_modules)` `npm` `=` `os.environ.get(``"NPM"``, make_script_filename(``"npm"``))``try``:``subprocess.run([npm,` `"init"``,` `"-y"``],``capture_output``=``True``,``cwd``=``output_dir,``check``=``True``)``subprocess.run([npm,` `"install"``]` `+` `[f``"{name}@{version_spec}"` `for` `name, version_spec` `in` `RELAXED_DEPS.items()],``capture_output``=``True``,``cwd``=``output_dir,``check``=``True``)``subprocess.run([npm,` `"install"``,` `"-E"``]` `+` `[f``"{name}@{version_spec}"` `for` `name, version_spec` `in` `EXACT_DEPS.items()],``capture_output``=``True``,``cwd``=``output_dir,``check``=``True``) <``=``=``=``=``=``=``=``=``=``这里下载了EXACT_DEPS里面的依赖项` |
|-|-|

看来是编译的时候，用npm install -E把frida-java-bridge下载下来了，那么接下来就是要把这个依赖项改成我们本地的。
首先下载一个到本地

| 1 | `git clone https:``/``/``github.com``/``frida``/``frida``-``java``-``bridge.git` |
|-|-|

然后全局查找libart.so，改成libartd.so
 ![改代码](https://bbs.kanxue.com/upload/attach/202304/975816_RDSF2Q3P83D2CVD.png)

 这时候需要用到npm link把我们本地的frida-java-bridge注册到系统中

| 1234567891011121314 | `(base)` `/``data``/``code``/``OpenSource``/``crack``/``frida``/``frida``-``java``-``bridge (main ✗) npm link` `up to date, audited` `3` `packages` `in` `574ms` `found` `0` `vulnerabilities` `(base)` `/``data``/``code``/``OpenSource``/``crack``/``frida``/``frida``-``java``-``bridge (main ✗) npm install`  `added` `214` `packages,` `and` `audited` `215` `packages` `in` `1s` `62` `packages are looking` `for` `funding``run `npm fund`` `for` `details` `found` `0` `vulnerabilities` |
|-|-|

然后要让frida中的编译脚本指向我们这个，也就是不要用npm install了，需要改成npm link, 修改generate-runtime.py代码如下
 ![runtime](https://bbs.kanxue.com/upload/attach/202304/975816_BKAA6RB5RWD39PZ.png)

 然后再重新编译, 生成后推到手机执行
 ![无报错](https://bbs.kanxue.com/upload/attach/202304/975816_8W5T82K3WEGTNKE.png)

 果然没有报错了，非常完美！

---

# 回复

## 回复 by madsu (#2)

*2023-4-5 00:25*

为啥我发的贴一直是待验证啊？

## 回复 by Editor (#3)

*2023-4-5 09:50*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  madsu](https://bbs.kanxue.com/user-975816.htm)
>
>  为啥我发的贴一直是待验证啊？
>
>

新人发帖需要版主审核验证显示，现在可以了

## 回复 by madsu (#4)

*2023-4-5 10:45*

>
> [Editor](https://bbs.kanxue.com/user-236762.htm)
>
>  新人发帖需要版主审核验证显示，现在可以了
>
>

可以了，感谢版主

## 回复 by madsu (#5)

*2023-4-5 12:17*

<https://www.52pojie.cn/thread-1652946-1-1.html>

后面准备研究研究这个，借宝地收藏一下，话说看雪怎么收藏外部资料呢？

## 回复 by 你瞒我瞒 (#6)

*2023-4-6 09:43*

我很早之前就注册了，上一年年底发帖，也是待验证，验证了几个月有一篇文章发出去了，但是还有一篇还是待验证，不知道是不是在等年终奖才能发，所以，我决定，未来都不会再发帖。

## 回复 by madsu (#7)

*2023-4-6 10:26*

>
> [你瞒我瞒](https://bbs.kanxue.com/user-748979.htm)
>
>  我很早之前就注册了，上一年年底发帖，也是待验证，验证了几个月有一篇文章发出去了，但是还有一篇还是待验证，不知道是不是在等年终奖才能发，所以，我决定，未来都不会再发帖。
>
>

我刚注册，后来看了下版规才知道需要审核，不过版主也很快给我通过了，看雪移动端相关版块人气远远不如PC版块，还是要多多发贴啊![image](https://bbs.kanxue.com/view/img/face/13.gif)

## 回复 by 果冻大砍刀 (#8)

*2023-4-6 20:30*

强![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)![image](https://bbs.kanxue.com/view/img/face/63.gif)
