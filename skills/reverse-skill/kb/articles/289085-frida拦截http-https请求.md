---
title: frida拦截http、https请求
url: https://bbs.kanxue.com/thread-289085.htm
tid: 289085
author: wx_老夫_473
date: '2025-11-14'
tags: [Android安全, 工具脚本, 协议分析, 逆向分析]
crawled_at: '2026-08-08T10:38:42+00:00'
replies: 165
---

最近为了抓住app请求，通过Fiddler代理获取数据，还是抓不到数据，
报：

| 1 | `java.security.cert.CertPathValidatorException: Trust anchor` `for` `certification path` `not` `found.` |
|-|-|

反复去看app内部的证书校验，使用了okhttp请求，但是压根没看到添加证书校验的逻辑，一个app就如此，如果还要获取别的app数据得搞到猴年马月。最后被搞烦了，就想着能不能通过frida直接hook底层代码，直接拿到数据。于是就有了如下代码：

hook_net.js

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136137138139140141142143144145146147148149150151152153154155156157158159160161162163164165166167168169170171172173174175176177178179180181182183184185186187188189190191192193194195196197198199200201202203204205206207208209210211212213214215216217218219220221222223224225226227228229230231232233234235236237238239240241242243244245246247248249250251252253254255256257258259260261262263264265266267268269270271272273274275276277278279280281282283284285286287288289290291292293294295296297298299300301302303304305306307308309310311312313314315316317318319320321322323324325326327328329330331332333334335336337338339340341342343344345346347348349350351352353354355356357358359360361362363364365366367368369370371372373374375376377378379380381382383384385386387388389390391392393394395396397398399400401402403404405406407408409410411412413414415416417418419420421422423424425426427428429430431432433434435436437438439440441442443444445446447448449450451452453454455456457458459460461462463464465466467468469470471472473474475476477478479480481482483484485486487488489490491492493494495496497498499500501 | `function showStacks(str_tag) {``var Exception` `=` `Java.use(``"java.lang.Exception"``);``var ins` `=` `Exception.$new(``"Exception"``);``var straces` `=` `ins.getStackTrace();` `if` `(undefined` `=``=` `straces \|\| null` `=``=` `straces) {``return``;``}``/``/` `var all_string` `=` `straces.toString();``/``/` `if` `(all_string.indexOf(``'com.adjust.sdk.sig.NativeLibHelper.nSign'``) <` `0``) {``/``/`     `return``;``/``/` `}``console.log(``"============================="` `+` `str_tag` `+` `" Stack strat======================="``);`  `for` `(var i` `=` `0``; i < straces.length; i``+``+``) {``var` `str` `=` `"   "` `+` `straces[i].toString();``console.log(``str``);``}` `console.log(``"============================="` `+` `str_tag` `+` `" Stack end=======================\r\n"``);``Exception.$dispose();``}` `function getStacksInfo() {``var Exception` `=` `Java.use(``"java.lang.Exception"``);``var ins` `=` `Exception.$new(``"Exception"``);``var straces` `=` `ins.getStackTrace();``var result` `=` `"";` `/``/` `用于存储拼接后的调用栈信息``if` `(undefined` `=``=` `straces \|\| null` `=``=` `straces) {``return``;``}` `for` `(var i` `=` `0``; i < straces.length; i``+``+``) {``var` `str` `=` `"   "` `+` `straces[i].toString();``/``/` `console.log(``str``);``result` `+``=` `str` `+` `"\n"``;` `/``/` `将每一行调用栈信息拼接到结果字符串中``}` `Exception.$dispose();``return` `result;` `/``/` `返回拼接后的调用栈信息``}` `function getSocketData(fd) {``if` `(false)` `return` `"";``console.log(``"fd:"``, fd);``var socketType` `=` `Socket.``type``(fd)``if` `(socketType !``=` `null) {``var res` `=` `"type:"` `+` `socketType` `+` `",loadAddress:"` `+` `JSON.stringify(Socket.localAddress(fd))` `+` `",peerAddress"` `+` `JSON.stringify(Socket.peerAddress(fd));``return` `res;``}` `else` `{``return` `"type:"` `+` `socketType;``}``}` `function getSocketData2(stream) {``var data0` `=` `stream.this$``0.value``;``var sockdata` `=` `data0.socket.value;``return` `sockdata;``}` `function bytesToHex(bytes) {``var hexString` `=` `'';``var arr` `=` `new Uint8Array(bytes);``for` `(var i` `=` `0``; i < arr.length; i``+``+``) {``hexString` `+``=` `(``'0'` `+` `arr[i].toString(``16``)).``slice``(``-``2``);``}``return` `hexString;``}` `function getContentLength(responseHeaders) {``/``/` `使用正则表达式获取 Content``-``Length 的值``const regex` `=` `/``Content``-``Length:\s``*``(\d``+``)``/``i;``const match` `=` `responseHeaders.match(regex);` `if` `(match && match[``1``]) {``return` `parseInt(match[``1``],` `10``);` `/``/` `转换为整数``}` `else` `{``return` `null;` `/``/` `如果未找到 Content``-``Length，返回 null``}``}` `function hasTransferEncodingChunked(responseHeaders) {``/``/` `将响应头分成每一行``var headers` `=` `responseHeaders.split(``'\r\n'``);``/``/` `遍历每一行，检查是否包含 Transfer``-``Encoding: chunked``for` `(var i` `=` `0``; i < headers.length; i``+``+``) {``if` `(headers[i].toLowerCase().startsWith(``'transfer-encoding:'``)) {``/``/` `检查该行是否包含` `'chunked'``return` `headers[i].toLowerCase().includes(``'chunked'``);``}``}` `/``/` `如果没有找到，返回 false``return` `false;``}` `function get_content(r, size) {``/``/` `使用readUtf8String读取有时候会有错误，采用反射java代码``var StringClass` `=` `Java.use(``'java.lang.String'``);``var CharsetClass` `=` `Java.use(``'java.nio.charset.Charset'``);``var bytes2` `=` `r.readByteArray(size);``/``/` `将 byte[] 转换为 Java 字符串``var byteArray` `=` `Java.array(``'byte'``, new Uint8Array(bytes2));``var stringData` `=` `StringClass.$new(byteArray, CharsetClass.forName(``'UTF-8'``));``return` `stringData;``}` `function isTargetRequest(key, myMap, tag) {``var value` `=` `myMap.get(key);``if` `(value !``=` `null) {``return` `(value.indexOf(tag) >``=` `0``);``}` `else` `{``return` `false;``}``}` `function print_finish_result(myMap, chunkMap, key) {``var request_value` `=` `myMap.get(key);``if` `(request_value !``=` `null) {``console.log(key` `+` `" 请求:"``);``console.log(request_value);``console.log(``"\n"``);``myMap.delete(key);``}` `var last_content` `=` `chunkMap.get(key);``console.log(``"\n"` `+` `key` `+` `" 响应:"``);``console.log(last_content);``chunkMap.delete(key);``}` `/``/``jni的ssl的加密数据hook``function hook_jni_ssl_enc() {``/``/` `var writePtr` `=` `Module.getExportByName(``"libc.so"``,` `"write"``);``/``/` `var readPtr` `=` `Module.getExportByName(``"libc.so"``,` `"read"``);``var writePtr` `=` `Process.getModuleByName(``'libc.so'``).getExportByName(``'write'``)``var readPtr` `=` `Process.getModuleByName(``'libc.so'``).getExportByName(``'read'``)``console.log(``"write:"``, writePtr,` `",read:"``, readPtr);``Interceptor.attach(writePtr, {``onEnter: function (args) {``var fd` `=` `args[``0``];``var buff` `=` `args[``1``];``var size` `=` `args[``2``];``if` `(size >` `20``) {``var sockdata` `=` `getSocketData(fd.toInt32());``if` `(sockdata.indexOf(``"tcp"``)) {``console.log(sockdata);``/``/` `console.log(hexdump(buff, { length: size.toInt32() }));``}``}` `},``onLeave: function (retval) {` `}``});``Interceptor.attach(readPtr, {``onEnter: function (args) {``this.fd` `=` `args[``0``];``this.buff` `=` `args[``1``];``this.size` `=` `args[``2``];``},``onLeave: function (retval) {``if` `(this.size >` `20``) {``var sockdata` `=` `getSocketData(this.fd.toInt32());``if` `(sockdata.indexOf(``"tcp"``)) {``console.log(sockdata);``/``/` `console.log(hexdump(this.buff, { length: this.size.toInt32() }));``}``}` `}``});``}` `/``/``处理https请求``function hook_jni_ssl() {` `Java.perform(function () {``/``/` `Process.getModuleByName(``'libc.so'``).getExportByName(``'recvfrom'``)``var sslWritePtr` `=` `Process.getModuleByName(``'libssl.so'``).getExportByName(``'SSL_write'``)``var sslReadPtr` `=` `Process.getModuleByName(``'libssl.so'``).getExportByName(``'SSL_read'``)``console.log(``"sslWrite:"``, sslWritePtr,` `",sslRead:"``, sslReadPtr);``var sslGetFdPtr` `=` `Process.getModuleByName(``'libssl.so'``).getExportByName(``'SSL_get_rfd'``)``var sslGetFdFunc` `=` `new NativeFunction(sslGetFdPtr,` `'int'``, [``'pointer'``]);` `/``/` `创建一个` `Map``var myMap` `=` `new` `Map``();``var chunkMap` `=` `new` `Map``();``/``/``int` `SSL_write(SSL` `*``ssl, const void` `*``buf,` `int` `num)``Interceptor.attach(sslWritePtr, {``onEnter: function (args) {``this.sslPtr` `=` `args[``0``];``this.buff` `=` `args[``1``];``this.size` `=` `args[``2``];``},``onLeave: function (retval) {``var headerInfo` `=` `ptr(this.buff).readByteArray(``4``);``var hexHeaderInfo` `=` `bytesToHex(headerInfo).toLowerCase();``/``/` `if` `(!hexHeaderInfo.startsWith(``'00000000'``)) {``if` `(hexHeaderInfo.startsWith(``'504f5354'``)``/``/``各种请求，如POST，GET等``\|\| hexHeaderInfo.startsWith(``'474554'``)``\|\| hexHeaderInfo.startsWith(``'505554'``)``\|\| hexHeaderInfo.startsWith(``'44454c455445'``)``\|\| hexHeaderInfo.startsWith(``'48454144'``)``\|\| hexHeaderInfo.startsWith(``'4f5054494f4e53'``)``\|\| hexHeaderInfo.startsWith(``'5041544348'``)``\|\| hexHeaderInfo.startsWith(``'434f4e4e454354'``)``\|\| hexHeaderInfo.startsWith(``'505249'``)``) {``var bytes` `=` `ptr(this.buff).readByteArray(this.size.toInt32());``var arr` `=` `new Uint8Array(bytes);``for` `(var i` `=` `0``; i < arr.length; i``+``+``) {``if` `(arr[i]` `=``=` `0x0d` `&& arr[i` `+` `1``]` `=``=` `0x0a` `&& arr[i` `+` `2``]` `=``=` `0x0d` `&& arr[i` `+` `3``]` `=``=` `0x0a``) {``var` `buffer` `=` `ptr(this.buff).readUtf8String(i);``var content_length` `=` `getContentLength(``buffer``);``var real_len` `=` `this.size.toInt32();``if` `(content_length` `=``=` `null) {``real_len` `=` `i;``}` `else` `{``real_len` `=` `i` `+` `4` `+` `content_length;``}``var stringData` `=` `get_content(ptr(this.buff), real_len);``myMap.``set``(this.sslPtr.toString(), stringData);``console.log(``"请求数量:"` `+` `this.sslPtr.toString()` `+` `"="` `+` `stringData.substring(``0``, stringData.indexOf(``'\n'``)))``break``;``}``}``}``}``});` `/``/``int` `SSL_read(SSL` `*``ssl, void` `*``buf,` `int` `num)``Interceptor.attach(sslReadPtr, {``onEnter: function (args) {``this.sslPtr` `=` `args[``0``];``this.buff` `=` `args[``1``];``this.size` `=` `args[``2``];``/``/` `var` `buffer`  `=`  `ptr(args[``1``]).readUtf8String(args[``2``].toInt32());``/``/` `console.log(``buffer``);``},``onLeave: function (retval) {``var headerInfo` `=` `ptr(this.buff).readByteArray(``4``);``var hexHeaderInfo` `=` `bytesToHex(headerInfo).toLowerCase();` `var fd_str` `=` `this.sslPtr.toString();` `/``/` `if` `(isTargetRequest(fd_str, myMap,` `"/api/interface/version1.2/customer"``)) {``/``/`     `console.log(fd_str` `+` `" retval:"` `+` `retval.toInt32())``/``/` `}` `if` `(chunkMap.get(fd_str) !``=` `null) {``/``/``处理块``if` `(retval.toInt32() >` `0``) {``var chunkedContent` `=` `get_content(ptr(this.buff), retval.toInt32());``var new_content` `=` `chunkMap.get(fd_str)` `+` `chunkedContent;``chunkMap.``set``(fd_str, new_content);``/``/` `console.log(hexdump(ptr(this.buff).add( retval.toInt32()``-``4``), { length:` `4` `}));``if` `(retval.toInt32() >``=` `5``) {``var bytes` `=` `ptr(this.buff).add(retval.toInt32()` `-` `5``).readByteArray(``5``);``var arr` `=` `new Uint8Array(bytes);``if` `(arr[``0``]` `=``=` `0x30` `&& arr[``1``]` `=``=` `0x0d` `&& arr[``2``]` `=``=` `0x0a` `&& arr[``3``]` `=``=` `0x0d` `&& arr[``4``]` `=``=` `0x0a``) {``print_finish_result(myMap, chunkMap, fd_str);``}``}` `else` `{``/``/``正常不回出现这种情况``print_finish_result(myMap, chunkMap, fd_str);``}` `}` `else` `{``print_finish_result(myMap, chunkMap, fd_str);``}` `}``var head_end` `=` `0``;``/``/` `if` `(!hexHeaderInfo.startsWith(``'00000000'``)) {``if` `(hexHeaderInfo.startsWith(``'48545450'``)) {` `var bytes` `=` `ptr(this.buff).readByteArray(this.size.toInt32());``var arr` `=` `new Uint8Array(bytes);``for` `(var i` `=` `0``; i < arr.length; i``+``+``) {``if` `(arr[i]` `=``=` `0x0d` `&& arr[i` `+` `1``]` `=``=` `0x0a` `&& arr[i` `+` `2``]` `=``=` `0x0d` `&& arr[i` `+` `3``]` `=``=` `0x0a``) {``head_end` `=` `i;``try` `{``var` `buffer` `=` `ptr(this.buff).readUtf8String(i);``/``/``这里使用readUtf8String ，因为已经确定了响应头不会出现乱七八糟的字符``console.log(``"响应数量:"` `+` `this.sslPtr.toString()` `+` `"="` `+` `buffer``.substring(``0``,` `buffer``.indexOf(``'\n'``)))``var hasChunked` `=` `hasTransferEncodingChunked(``buffer``);``console.log(``"hasChunked = "` `+` `hasChunked` `+` `","` `+` `this.sslPtr.toString()` `+` `" retval:"``, retval.toInt32());``/``/` `console.log(fd_str` `+` `" retval:"``, retval.toInt32());``/``/` `console.log(fd_str` `+` `" size:"``, this.size.toInt32());` `if` `(hasChunked) {``/``/` `console.log(hexdump(this.buff, { length: retval.toInt32() }));``var stringData` `=` `get_content(ptr(this.buff), retval.toInt32());``chunkMap.``set``(fd_str, stringData);``/``/` `if` `(isTargetRequest(this.sslPtr.toString(), myMap,` `"/api/interface/version1.2/customer"``)) {``/``/`     `console.log(this.sslPtr.toString()` `+` `":"` `+` `stringData)``/``/`     `console.log(hexdump(this.buff, { length: retval.toInt32()` `+` `5` `}));``/``/` `}``if` `(retval.toInt32() >``=` `5``) {``var end_bytes` `=` `ptr(this.buff).add(retval.toInt32()` `-` `5``).readByteArray(``5``);``var end_arr` `=` `new Uint8Array(end_bytes);``if` `(end_arr[``0``]` `=``=` `0x30` `&& end_arr[``1``]` `=``=` `0x0d` `&& end_arr[``2``]` `=``=` `0x0a` `&& end_arr[``3``]` `=``=` `0x0d` `&& end_arr[``4``]` `=``=` `0x0a``) {``print_finish_result(myMap, chunkMap, fd_str);``}` `else` `{``print_finish_result(myMap, chunkMap, fd_str);``}``}``/``/` `console.log(hexdump(ptr(this.buff).add(retval.toInt32()``-``10``), { length:` `20` `}));``}` `else` `{``/``/``没有分块，直接读取全部``/``/` `var chunkedContent` `=` `ptr(this.buff).readUtf8String(retval.toInt32());``var chunkedContent` `=` `get_content(ptr(this.buff), retval.toInt32());``chunkMap.``set``(fd_str, stringData);``print_finish_result(myMap, chunkMap, fd_str);``}` `} catch (error) {``var tmp_size` `=` `this.size.toInt32();``if` `(tmp_size <` `30000``) {``/``/` `console.log(hexdump(this.buff, { length: this.size.toInt32() }));``}``console.log(``"捕获到错误 retval:"``, retval.toInt32());``console.log(``"捕获到错误 size:"``, this.size.toInt32());``console.log(``"捕获到错误:"``, error.stack);``var content` `=` `ptr(this.buff).readUtf8String(head_end);``/``/` `console.log(hexdump(this.buff, { length: retval.toInt32() }));``console.log(content);`  `}` `finally` `{``/``/` `可选的代码，无论是否发生异常都会执行``}``break``;``}``}``}``}``});` `});`  `}` `/``/``处理http请求``function hook_jni_tcp() {` `Java.perform(function () {``/``/` `var sendtoPtr` `=` `Module.getExportByName(``"libc.so"``,` `"sendto"``);``/``/` `var recvfromPtr` `=` `Module.getExportByName(``"libc.so"``,` `"recvfrom"``);` `var sendtoPtr` `=` `Process.getModuleByName(``'libc.so'``).getExportByName(``'sendto'``)``var recvfromPtr` `=` `Process.getModuleByName(``'libc.so'``).getExportByName(``'recvfrom'``)``console.log(``"sendto:"``, sendtoPtr,` `",recvfrom:"``, recvfromPtr);` `/``/` `创建一个` `Map``var myMap` `=` `new` `Map``();``var chunkMap` `=` `new` `Map``();``/``/``sendto(``int` `fd, const void` `*``buf, size_t n,` `int` `flags, const struct sockaddr` `*``addr, socklen_t addr_len)``Interceptor.attach(sendtoPtr, {``onEnter: function (args) {``this.sslPtr` `=` `args[``0``];``this.buff` `=` `args[``1``];``this.size` `=` `args[``2``];``},``onLeave: function (retval) {``var headerInfo` `=` `ptr(this.buff).readByteArray(``4``);``var hexHeaderInfo` `=` `bytesToHex(headerInfo).toLowerCase();``/``/` `if` `(!hexHeaderInfo.startsWith(``'00000000'``)) {``if` `(hexHeaderInfo.startsWith(``'504f5354'``)``\|\| hexHeaderInfo.startsWith(``'474554'``)``\|\| hexHeaderInfo.startsWith(``'505554'``)``\|\| hexHeaderInfo.startsWith(``'44454c455445'``)``\|\| hexHeaderInfo.startsWith(``'48454144'``)``\|\| hexHeaderInfo.startsWith(``'4f5054494f4e53'``)``\|\| hexHeaderInfo.startsWith(``'5041544348'``)``\|\| hexHeaderInfo.startsWith(``'434f4e4e454354'``)``\|\| hexHeaderInfo.startsWith(``'505249'``)``) {``var bytes` `=` `ptr(this.buff).readByteArray(this.size.toInt32());``var arr` `=` `new Uint8Array(bytes);``for` `(var i` `=` `0``; i < arr.length; i``+``+``) {``if` `(arr[i]` `=``=` `0x0d` `&& arr[i` `+` `1``]` `=``=` `0x0a` `&& arr[i` `+` `2``]` `=``=` `0x0d` `&& arr[i` `+` `3``]` `=``=` `0x0a``) {``var` `buffer` `=` `ptr(this.buff).readUtf8String(i);``var content_length` `=` `getContentLength(``buffer``);``var real_len` `=` `this.size.toInt32();``if` `(content_length` `=``=` `null) {``real_len` `=` `i;``}` `else` `{``real_len` `=` `i` `+` `4` `+` `content_length;``}``var stringData` `=` `get_content(ptr(this.buff), real_len);``/``/` `console.log(stringData.toString());``myMap.``set``(this.sslPtr.toString(), stringData);``break``;``}``}``}``}``});``/``/``recvfrom(``int` `fd, void` `*``buf, size_t n,` `int` `flags, struct sockaddr` `*``addr, socklen_t` `*``addr_len)``Interceptor.attach(recvfromPtr, {``onEnter: function (args) {``this.sslPtr` `=` `args[``0``];``this.buff` `=` `args[``1``];``this.size` `=` `args[``2``];``},``onLeave: function (retval) {``var headerInfo` `=` `ptr(this.buff).readByteArray(``4``);``var hexHeaderInfo` `=` `bytesToHex(headerInfo).toLowerCase();` `var fd_str` `=` `this.sslPtr.toString();``if` `(chunkMap.get(fd_str) !``=` `null) {``/``/``处理块``if` `(retval.toInt32() >` `0``) {``var chunkedContent` `=` `get_content(ptr(this.buff), retval.toInt32());``var new_content` `=` `chunkMap.get(fd_str)` `+` `chunkedContent;``chunkMap.``set``(fd_str, new_content);``/``/` `console.log(hexdump(ptr(this.buff).add( retval.toInt32()``-``4``), { length:` `4` `}));``if` `(retval.toInt32() >``=` `5``) {``var bytes` `=` `ptr(this.buff).add(retval.toInt32()` `-` `5``).readByteArray(``5``);``var arr` `=` `new Uint8Array(bytes);``if` `(arr[``0``]` `=``=` `0x30` `&& arr[``1``]` `=``=` `0x0d` `&& arr[``2``]` `=``=` `0x0a` `&& arr[``3``]` `=``=` `0x0d` `&& arr[``4``]` `=``=` `0x0a``) {``print_finish_result(myMap, chunkMap, fd_str);``}``}` `else` `{``/``/``正常不回出现这种情况``print_finish_result(myMap, chunkMap, fd_str);``}` `}` `else` `{``/``/``正常不回出现这种情况``print_finish_result(myMap, chunkMap, fd_str);``}` `}``var head_end` `=` `0``;``/``/` `if` `(!hexHeaderInfo.startsWith(``'00000000'``)) {``if` `(hexHeaderInfo.startsWith(``'48545450'``)) {``var bytes` `=` `ptr(this.buff).readByteArray(this.size.toInt32());``var arr` `=` `new Uint8Array(bytes);``for` `(var i` `=` `0``; i < arr.length; i``+``+``) {``if` `(arr[i]` `=``=` `0x0d` `&& arr[i` `+` `1``]` `=``=` `0x0a` `&& arr[i` `+` `2``]` `=``=` `0x0d` `&& arr[i` `+` `3``]` `=``=` `0x0a``) {``head_end` `=` `i;``try` `{``var` `buffer` `=` `ptr(this.buff).readUtf8String(i);``/``/``这里使用readUtf8String ，因为已经确定了响应头不会出现乱七八糟的字符` `var hasChunked` `=` `hasTransferEncodingChunked(``buffer``);``console.log(``"hasChunked = "``, hasChunked);``/``/` `console.log(fd_str` `+` `" retval:"``, retval.toInt32());``/``/` `console.log(fd_str` `+` `" size:"``, this.size.toInt32());` `if` `(hasChunked) {``var stringData` `=` `get_content(ptr(this.buff), retval.toInt32());``chunkMap.``set``(fd_str, stringData);``if` `(retval.toInt32() >``=` `5``) {``var end_bytes` `=` `ptr(this.buff).add(retval.toInt32()` `-` `5``).readByteArray(``5``);``var end_arr` `=` `new Uint8Array(end_bytes);``if` `(end_arr[``0``]` `=``=` `0x30` `&& end_arr[``1``]` `=``=` `0x0d` `&& end_arr[``2``]` `=``=` `0x0a` `&& end_arr[``3``]` `=``=` `0x0d` `&& end_arr[``4``]` `=``=` `0x0a``) {``print_finish_result(myMap, chunkMap, fd_str);``}``}` `else` `{``/``/``正常不回出现这种情况``print_finish_result(myMap, chunkMap, fd_str);``}``/``/` `console.log(hexdump(ptr(this.buff).add(retval.toInt32()``-``10``), { length:` `20` `}));``}` `else` `{``var chunkedContent` `=` `get_content(ptr(this.buff), retval.toInt32());``chunkMap.``set``(fd_str, chunkedContent);``print_finish_result(myMap, chunkMap, fd_str);``}` `} catch (error) {``var tmp_size` `=` `this.size.toInt32();``if` `(tmp_size <` `30000``) {``/``/` `console.log(hexdump(this.buff, { length: this.size.toInt32() }));``}``console.log(``"捕获到错误 retval:"``, retval.toInt32());``console.log(``"捕获到错误 size:"``, this.size.toInt32());``console.log(``"捕获到错误:"``, error.stack);``var content` `=` `ptr(this.buff).readUtf8String(head_end);``/``/` `console.log(hexdump(this.buff, { length: retval.toInt32() }));``console.log(content);`  `}` `finally` `{``/``/` `可选的代码，无论是否发生异常都会执行``}``break``;``}``}``}``}``});``});` `}`  `function hook_java_net() {``hook_jni_ssl();``hook_jni_tcp();``/``/` `hook_jni_ssl_enc();``}` `setImmediate(hook_java_net);` |
|-|-|

**http**
1、通过hook Process.getModuleByName('libc.so').getExportByName('sendto') 获取发送请求
2、通过hook Process.getModuleByName('libc.so').getExportByName('recvfrom')获取响应
最后整理两者的对应关系

 **https**
1、通过hook Process.getModuleByName('libssl.so').getExportByName('SSL_write') 获取请求
2、通过hook Process.getModuleByName('libssl.so').getExportByName('SSL_read')获取响应
和http一样，最后处理两者关系

主要麻烦是处理响应数据头有Transfer-Encoding: chunked 情况的，会多次回调 recvfrom与SSL_read函数

灵感来源:[android抓包学习的整理和归纳](https://bbs.kanxue.com/thread-267940.htm#msg_header_h2_2)

---

# 回复

## 回复 by huluxia (#2)

*2025-11-14 08:19*

66666

## 回复 by 善翁 (#3)

*2025-11-14 09:06*

谢谢分享

## 回复 by style (#4)

*2025-11-14 09:09*

666

## 回复 by 日暮归途 (#5)

*2025-11-14 09:12*

666

## 回复 by wx_插曲 (#6)

*2025-11-14 09:18*

666

## 回复 by iBa0 (#7)

*2025-11-14 09:49*

123

## 回复 by kingking888 (#8)

*2025-11-14 10:00*

666

## 回复 by mb_qimctavn (#9)

*2025-11-14 10:10*

6

## 回复 by azd放 (#10)

*2025-11-14 10:13*

666

## 回复 by kxblah (#11)

*2025-11-14 10:13*

666

## 回复 by baogu (#12)

*2025-11-14 10:14*

好

## 回复 by mb_jofnsvty (#13)

*2025-11-14 10:18*

666

## 回复 by mb_pmgifpme (#14)

*2025-11-14 10:20*

1

## 回复 by mb_phnoemiu (#15)

*2025-11-14 10:34*

66666

## 回复 by 机车王子 (#16)

*2025-11-14 10:39*

这个讨论对我很有帮助，谢谢！

## 回复 by mb_asiwnxyv (#17)

*2025-11-14 10:45*

谢谢分享

## 回复 by 小辣鸡的id (#18)

*2025-11-14 10:46*

666

## 回复 by 魔童 (#19)

*2025-11-14 10:53*

666666666

## 回复 by mb_irhdtnzm (#20)

*2025-11-14 11:07*

6

## 回复 by 小尘0000 (#21)

*2025-11-14 11:13*

666

## 回复 by GEKEZYX (#22)

*2025-11-14 11:15*

666

## 回复 by LQ6H (#23)

*2025-11-14 11:40*

666

## 回复 by mb_ldbucrik (#24)

*2025-11-14 12:14*

感谢分享

## 回复 by mb_ykavguun (#25)

*2025-11-14 12:16*

1111

## 回复 by MaYil (#26)

*2025-11-14 13:55*

感谢分享

## 回复 by PPTV (#27)

*2025-11-14 14:23*

66

## 回复 by mb_hrowzezq (#28)

*2025-11-14 14:43*

![image](https://bbs.kanxue.com/view/img/face/067.gif)

## 回复 by xianhuimin (#29)

*2025-11-14 14:48*

感谢分享

## 回复 by 踏水流 (#30)

*2025-11-14 15:32*

66

## 回复 by mb_cbgtaveo (#31)

*2025-11-14 15:32*

66666

## 回复 by mb_rbaigqfb (#32)

*2025-11-14 16:53*

感谢分享

## 回复 by Tanuyoki0 (#33)

*2025-11-14 17:28*

学习

## 回复 by zylyy (#34)

*2025-11-14 19:08*

感谢分享

## 回复 by zylyy (#35)

*2025-11-14 19:11*

感谢分享

## 回复 by jyotidwi (#36)

*2025-11-15 01:34*

66666

## 回复 by mb_4nrpVMxJ (#37)

*2025-11-15 07:23*

111

## 回复 by Metzkerson (#38)

*2025-11-15 13:55*

学习学习

## 回复 by mb_mlyojneh (#39)

*2025-11-15 14:34*

感谢分享思路

## 回复 by mb_ghebfkzn (#40)

*2025-11-15 14:51*

1

## 回复 by bisoso (#41)

*2025-11-15 22:53*

学习下！！！！！！！

## 回复 by cpannn (#42)

*2025-11-15 23:23*

666666

## 回复 by wx_Huber Barrientos (#43)

*2025-11-15 23:53*

非常支持你的观点！

## 回复 by 筹码 (#44)

*2025-11-16 08:08*

6666

## 回复 by huangjw (#45)

*2025-11-16 12:48*

学习了，好文章

## 回复 by mb_iunhvspv (#46)

*2025-11-17 07:06*

可以的，666

## 回复 by 胡家二少 (#47)

*2025-11-17 08:50*

学习一下

## 回复 by leilei_9527 (#48)

*2025-11-17 09:17*

感谢分享

## 回复 by Imxz (#49)

*2025-11-17 10:31*

tql

## 回复 by wdone (#50)

*2025-11-17 11:05*

谢谢分享

## 回复 by 呼吸24K纯氧 (#51)

*2025-11-17 11:09*

感谢分享

## 回复 by mb_atdqqbte (#52)

*2025-11-17 11:30*

牛啊

## 回复 by axpol (#53)

*2025-11-17 14:47*

666

## 回复 by wx_霿凇 (#54)

*2025-11-17 16:24*

666

## 回复 by 2445809596 (#55)

*2025-11-17 17:25*

6

## 回复 by 梦_魇 (#56)

*2025-11-17 17:34*

6

## 回复 by 寻梦之璐 (#57)

*2025-11-17 17:43*

11

## 回复 by mb_xflcgdik (#58)

*2025-11-17 18:59*

1

## 回复 by mb_ysegxpmv (#59)

*2025-11-17 21:09*

特来学习

## 回复 by mb_twyjzbcv (#60)

*2025-11-17 23:18*

11111111

## 回复 by 9494 (#61)

*2025-11-18 00:00*

感谢你的积极参与，期待更多精彩内容！

## 回复 by 灌者为王 (#62)

*2025-11-18 00:04*

学习一下frida

## 回复 by mb_tcandlos (#63)

*2025-11-18 09:12*

111

## 回复 by mb_nntqdxvc (#64)

*2025-11-18 16:34*

6666

## 回复 by Evangeliner (#65)

*2025-11-19 10:29*

感谢分享

## 回复 by wx_IT_717 (#66)

*2025-11-19 10:40*

很好的教程，感谢分享

## 回复 by pyth0nDev (#67)

*2025-11-19 12:06*

666

## 回复 by FindCall (#68)

*2025-11-19 19:39*

666

## 回复 by mb_akowpmjs (#69)

*2025-11-19 19:44*

![image](https://bbs.kanxue.com/view/img/face/001.gif)

## 回复 by mb_birmgglx (#70)

*2025-11-19 19:46*

111111111111111111111111

## 回复 by 文西哥 (#71)

*2025-11-19 21:20*

![image](https://bbs.kanxue.com/view/img/face/003.gif)

## 回复 by 去玩儿童 (#72)

*2025-11-19 22:56*

22

## 回复 by hacker521 (#73)

*2025-11-20 08:46*

666

## 回复 by birdcard (#74)

*2025-11-20 08:55*

666666

## 回复 by guijingwen (#75)

*2025-11-20 10:12*

66

## 回复 by mb_euhyowpw (#76)

*2025-11-20 10:25*

111

## 回复 by babyrjw (#77)

*2025-11-20 10:58*

感谢分享

## 回复 by git_92258 (#78)

*2025-11-20 11:43*

666

## 回复 by 上官兮唐 (#79)

*2025-11-20 21:14*

看看

## 回复 by benlei (#80)

*2025-11-21 14:46*

666，感谢分享

## 回复 by 会飞的锅 (#81)

*2025-11-21 15:30*

感谢分享

## 回复 by mb_fhpfcoqp (#82)

*2025-11-21 16:16*

6666

## 回复 by mb_gvpkossd (#83)

*2025-11-24 09:41*

666

## 回复 by mb_umfqcneh (#84)

*2025-11-24 11:03*

666

## 回复 by mb_fqzjlpub (#85)

*2025-11-24 13:04*

666

## 回复 by mb_mrjjcxgk (#86)

*2025-11-24 14:19*

666

## 回复 by linghaien (#87)

*2025-11-24 15:07*

学习一下

## 回复 by 李啊啊 (#88)

*2025-11-25 10:35*

111

## 回复 by 野生的强大 (#89)

*2025-11-25 11:41*

感谢分享

## 回复 by jmzqwh (#90)

*2025-11-25 13:40*

111

## 回复 by mb_mhkvahza (#91)

*2025-11-25 15:03*

![image](https://bbs.kanxue.com/view/img/face/039.gif)1111

## 回复 by 烬奇小云 (#92)

*2025-11-26 08:53*

666

## 回复 by zhuzhu_biu (#93)

*2025-11-26 12:01*

adjust 在安卓上面用ecapture基本没啥问题的

## 回复 by mb_bdcqybve (#94)

*2025-11-26 16:33*

感谢分享![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by scpczc (#95)

*2025-11-26 17:23*

66666

## 回复 by iao (#96)

*2025-11-26 17:51*

66666

## 回复 by amwpecel (#97)

*2025-11-26 18:17*

试试看效果

## 回复 by wx_随波逐流、 (#98)

*2025-11-27 07:52*

666666666

## 回复 by mb_roytviwx (#99)

*2025-11-27 09:37*

111

## 回复 by 我心向山 (#100)

*2025-11-27 14:16*

1111

## 回复 by 无情铁手 (#101)

*2025-11-27 15:11*

6666

## 回复 by wx_五十度灰 (#102)

*2025-11-27 15:38*

666

## 回复 by mb_fogbfnnb (#103)

*2025-11-28 00:39*

666

## 回复 by xeiyu (#104)

*2025-11-28 04:14*

666

## 回复 by mb_hfizjsds (#105)

*2025-11-28 11:49*

666

## 回复 by godiand (#106)

*2025-11-28 13:47*

牛逼666

## 回复 by mb_hhtamnlw (#107)

*2025-11-30 10:56*

666

## 回复 by 云觞 (#108)

*2025-12-2 09:22*

感谢分享

## 回复 by mb_frspcrqz (#109)

*2025-12-3 02:54*

666

## 回复 by darkya (#110)

*2025-12-4 14:29*

看看大佬的操作

## 回复 by zylyy (#111)

*2025-12-4 14:38*

6666

## 回复 by mb_uzmffdbw (#112)

*2025-12-5 15:47*

666

## 回复 by sir678 (#113)

*2025-12-5 16:11*

![image](https://bbs.kanxue.com/view/img/face/079.gif)

## 回复 by mb_uikdudgo (#114)

*2025-12-5 19:21*

1111

## 回复 by mb_xyntbivj (#115)

*2025-12-7 10:12*

666

## 回复 by System's (#116)

*2025-12-7 22:10*

感谢分享

## 回复 by xhybb (#117)

*2025-12-8 22:53*

666

## 回复 by Sharp_Wang (#118)

*2025-12-9 11:19*

666

## 回复 by 屁屁 (#119)

*2025-12-9 13:32*

測試看看

## 回复 by mb_ckfmrnqa (#120)

*2025-12-9 14:23*

看看和r0capture有啥区别

## 回复 by 蕉仔889 (#121)

*2025-12-9 16:24*

2222

## 回复 by git_94730eaydwshawke-gif (#122)

*2025-12-9 17:44*

6666666

## 回复 by mb_tsjpnnxs (#123)

*2025-12-14 20:31*

111

## 回复 by wx_coddvccwyh (#124)

*2025-12-18 23:57*

6666

## 回复 by bingkuaiiii (#125)

*2025-12-23 14:14*

666

## 回复 by zkbutt (#126)

*2025-12-23 23:34*

学习

## 回复 by wx_故事与酒 (#127)

*2025-12-24 13:35*

6666666666666666666

## 回复 by gcodeer (#128)

*2025-12-24 13:40*

感谢分享，刚好当前项目需要

## 回复 by wx_K4i. (#129)

*2025-12-24 13:43*

感谢分享

## 回复 by unxeer (#130)

*2025-12-25 20:43*

学习一下

## 回复 by mb_hcadvceu (#131)

*2025-12-25 23:05*

路过看看

## 回复 by whoo2 (#132)

*2025-12-26 09:21*

感谢大佬分享

## 回复 by mb_yyvcbkli (#133)

*2025-12-26 09:54*

学习一下先进经验

## 回复 by baitongling (#134)

*2025-12-26 10:59*

666

## 回复 by mb_ssnabqqf (#135)

*2025-12-26 11:10*

222

## 回复 by ..._579212 (#136)

*2025-12-26 14:05*

感谢分享

## 回复 by 胖虎汇邦 (#137)

*2025-12-30 13:36*

666

## 回复 by 胖虎汇邦 (#138)

*2025-12-30 13:58*

只是sendto还是不够呢，sendmsg和recvmsg也需要补充上

## 回复 by mb_wymesltt (#139)

*2025-12-31 15:46*

6666

## 回复 by wfvw126 (#140)

*2026-1-1 13:54*

3333

## 回复 by 川美 (#141)

*2026-1-1 14:26*

是不是所有都可以这样干

## 回复 by mb_yvuwqxei (#142)

*2026-1-4 00:51*

666

## 回复 by mb_dqwgdsem (#143)

*2026-1-4 07:56*

666

## 回复 by upcj (#144)

*2026-1-4 09:42*

1

## 回复 by 小童net (#145)

*2026-1-8 01:40*

![image](https://bbs.kanxue.com/view/img/face/001.gif)![image](https://bbs.kanxue.com/view/img/face/007.gif)

## 回复 by wx_李威威 (#146)

*2026-1-15 21:40*

111

## 回复 by mb_jhohnbzu (#147)

*2026-1-30 16:44*

666

## 回复 by mb_ucbmgqsi (#148)

*2026-1-30 17:07*

6

## 回复 by 牛牛很牛 (#149)

*2026-1-30 18:07*

6666

## 回复 by wx_king of the world (#150)

*2026-1-30 19:16*

666

## 回复 by zhaozhangyun (#151)

*2026-2-5 10:24*

666666666666666

## 回复 by 随风而行aa (#152)

*2026-2-5 10:51*

1111

## 回复 by mb_ghcouuzx (#153)

*2026-3-2 20:42*

看看看

## 回复 by 涂tu (#154)

*2026-3-2 20:59*

1111

## 回复 by FMNS (#155)

*2026-3-2 21:29*

感谢分享

## 回复 by Zepp7289 (#156)

*2026-3-3 11:14*

有些app会无视proxy设置，需要通过vpn抓，也有部分app不走系统的ssl库自己带一个

## 回复 by pingsky (#157)

*2026-3-7 09:15*

6666

## 回复 by 我不是卷王 (#158)

*2026-3-8 07:30*

6666

## 回复 by 陳學城 (#159)

*2026-4-2 10:10*

11

## 回复 by 逆向小龙 (#160)

*2026-4-4 21:39*

11111

## 回复 by 星落黎明 (#161)

*2026-4-7 15:32*

感谢分享

## 回复 by mb_uiqcqgnl (#162)

*2026-5-10 11:49*

感谢分享

## 回复 by mb_gzmqijnf (#163)

*2026-5-10 18:19*

n

## 回复 by mb_cxmjsgrw (#164)

*2026-5-13 20:37*

111

## 回复 by mb_nygkmzbw (#165)

*2026-5-13 21:02*

谢谢分享

## 回复 by wx_宇克鴻 (#166)

*2026-7-22 23:43*

感谢分享
