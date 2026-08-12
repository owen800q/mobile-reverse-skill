---
title: android系统设置里的账户，它的数据是保存在何处的？
url: https://bbs.kanxue.com/thread-275923.htm
tid: 275923
author: hmlyn
date: '2023-01-31'
tags: [Android安全, 系统相关]
crawled_at: '2026-08-12T04:02:44+00:00'
replies: 10
---

![image](https://bbs.kanxue.com/upload/attach/202301/636222_RZ9TX4MSW9YH6KN.png)

 不知道android系统里的APP账户数据，存放地方在哪里，把APP数据和缓存，全部清除了，再次打开APP查看，还是处于登录状态，然后我就根据包名全盘搜索，把所有相关文件删除了，还是不行，还是处于登录状态，只有把APP卸载了，才可以退出账号，当然APP本身也有退出功能，但是我本意是想找出它的APP登录文件，类似COOKies一种，至于用处，大家应该都懂的。
还有一种退出办法，
 ![image](https://bbs.kanxue.com/upload/attach/202301/636222_CTP25U5AHQKFSKR.png)
在系统设置账户里，移除账号，也能退出来，所以我觉得应该有一个类似的xml文件或者sqlite数据来存放登录凭证的，有大神对此有了解的吗，小弟苦苦找了好久，都没找到这个文件，或者有没什么办法，通过进程来查询该APP加载了什么文件之类的。。

---

# 回复

## 回复 by hmlyn (#2)

*2023-1-31 23:47*

没大神知道吗![image](https://bbs.kanxue.com/view/img/face/15.gif)

## 回复 by hmlyn (#3)

*2023-2-1 01:37*

查阅了一晚资料，大概是在安卓的AccountManager里，但是不知道它的文件在哪

## 回复 by hmlyn (#4)

*2023-2-1 02:14*

找到了：
https://blog.csdn.net/dzkdxyx/article/details/78242105

## 回复 by guijingwen (#5)

*2023-2-1 09:48*

“类似COOKies一种，至于用处，大家应该都懂的”。真不懂，干啥用？

## 回复 by RiDiN (#6)

*2023-2-1 10:15*

![image](https://bbs.kanxue.com/upload/attach/202302/762254_QRM8PZBCF87EPQV.jpg)

## 回复 by hmlyn (#7)

*2023-2-1 18:16*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>

你好，你这种是怎么访问的？
用浏览器的chrome://inspect/#devices 吗？

## 回复 by hmlyn (#8)

*2023-2-1 18:21*

虽然找到了该文件，如果直接导出到电脑上进行修改数据库内容，然后在上传覆盖进去，也把权限改回去，模拟器重启后，就会黑屏，无法进入系统。

## 回复 by RiDiN (#9)

*2023-2-1 18:41*

>
> [hmlyn](https://bbs.kanxue.com/user-636222.htm)
>
>  你好，你这种是怎么访问的？
> 用浏览器的chrome://inspect/#devices 吗？

<https://github.com/rev1si0n/lamda> 可以读取，但是无法在线修改

## 回复 by RiDiN (#10)

*2023-2-1 18:45*

修改的话，可以直接进这个 web shell，然后手动执行 sqlite 命令应该可以

## 回复 by hmlyn (#11)

*2023-2-1 19:10*

>
> [RiDiN](https://bbs.kanxue.com/user-762254.htm)
>
>  修改的话，可以直接进这个 web shell，然后手动执行 sqlite 命令应该可以
>
>

好的谢谢，已经找到原因无法替换数据库问题了，之前虽然权限改了，但是拥有者没有改，所以导致覆盖文件后，无法启动系统
