---
title: 分享一个ida dump so的python脚本
url: https://bbs.kanxue.com/thread-277833.htm
tid: 277833
author: iyue_t
date: '2023-06-30'
tags: [Android安全, 逆向分析, 脱壳反混淆, 工具脚本]
crawled_at: '2026-07-31T14:42:14+08:00'
replies: 2
---

# ida dump so for python

- 麻了,等半天dump不下来 还卡住，加个过程打印。

| 123456789101112131415161718192021222324 | `import` `ida_bytes` `def` `main():``ea` `=` `0x764BC46000`  `# 需对应修改``end` `=` `0x764bda5000``size` `=` `0x1000``# 别问为什么没写路径，pd或者wine跑的ida 根本找不到路径``sofile` `=` `open``(``"soname.so"``,` `"wb"``)``print``(``'collect start'``)``while` `True``:``if` `ea>end:``break``list` `=` `ida_bytes.get_bytes(ea,size)``print``(f``'collect:{hex(ea)}'``)``buf` `=` `bytearray(``list``)``sofile.write(buf)``sofile.flush()``ea` `+``=` `size``sofile.close()``print``(``'write over'``)`  `if` `__name__` `=``=` `'__main__'``:``main()` |
|-|-|

本来想在网上随便找个脚本dump以下 结果发现大部份脚本IDC PY 都是一个字节一个字节读取的太慢了.修改了某一个脚本直接一次性读取全部字节

---

# 回复

## 回复 by Nermor (#2)

*2023-11-18 00:52*

因为自己写的idc dump脚本比较卡， 搜到了这篇文章；

于是修改了一番，**结论是 一样卡**，- - !

这个写文件ida 二次转存就是**没有直接写个插件进去dump快**，凑合用吧。

[ida version > 8.0](https://hex-rays.com/products/ida/support/idapython_docs/)

```
import ida_bytes

def main():
    start_ea = ida_kernwin.ask_addr(ida_ida.inf_get_min_ea(), "Please enter the starting address for the data to be analyzed.")
    end_ea = ida_kernwin.ask_addr(ida_ida.inf_get_max_ea(), "Please enter the ending address for the data to be analyzed.")
    size = end_ea-start_ea
    file = ida_kernwin.ask_file(1, "*.*", "save file path")
    list = ida_bytes.get_bytes(start_ea,size)
    buf = bytearray(list)
    with open(file, 'wb') as fw:
        fw.write(buf)
    print('dump over')

if __name__ == '__main__':
    main()
```

## 回复 by iyue_t (#3)

*2023-11-27 17:37*

>
> [Nermor](https://bbs.kanxue.com/user-352285.htm)
>
>  因为自己写的idc dump脚本比较卡， 搜到了这篇文章；于是修改了一番，结论是 一样卡，- - !这个写文件ida 二次转存就是没有直接写个插件进去dump快，凑合用吧。ida version &a ...
>
>

等有时间可以写成插件，不过你这个也已经够用了。
