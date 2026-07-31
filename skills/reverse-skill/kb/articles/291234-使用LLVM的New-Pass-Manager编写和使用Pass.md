---
title: '[原创]使用LLVM的New Pass Manager编写和使用Pass'
url: https://bbs.kanxue.com/thread-291234.htm
tid: 291234
author: 白衣23
date: '2026-05-16'
tags: [Android安全, 原创, 混淆加固]
crawled_at: '2026-07-31T15:06:17+08:00'
replies: 14
---

目录- 环境
- 在LLVM源码中创建和编译LLVM Pass
- 创建工作目录
- 编写CMakeLists.txt
- add_llvm_pass_plugin
- CMake配置
- 建立CMake连接
- 编写源代码
- 功能源码
- 插件注册源码
- 顶层结构
- 返回的插件元数据
- 插件注册回调（核心）
- registerPipelineStartEPCallback
- `MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));`
- ModuleToFunctionPassAdaptor
- std::move(FPM)
- 注意
- registerPipelineParsingCallback
- 回调函数参数
- 导出给 LLVM 插件的入口函数
- extern "C"
- LLVM_ATTRIBUTE_WEAK
- ::llvm::PassPluginLibraryInfo
- llvmGetPassPluginInfo()
- return getPluginInfo();
- 编译
- 使用
- 在LLVM源码外创建和编译LLVM Pass
- 构建一个llvm项目
- 编译Pass
- 创建Pass项目
- 配置CMake
- 使用Pass
- 通过clang/clang++使用Pass
- 将Pass嵌入opt/clang/clang++
- CMake配置
- 创建项目
- add_llvm_component_library
- 注册Pass
- opt
- clang/clang++
- 把 Pass 内建进 clang/clang++ 的 O2/O3
- 通过`-mllvm`控制是否启用Pass
- 链接LLVMPasses
- 使用
- opt
- clang/clang++
- 参考
`LLVM`中所有的`Pass`都继承自`llvm::Pass`类或其子类。

# 环境

Ubuntu22.04.5
CLion2026.1
clang22

# 在LLVM源码中创建和编译LLVM Pass

## 创建工作目录

在`llvm-project\llvm\lib\Transforms`路径下新建一个目录，名称任意，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_3UY6DMA98Q59GU2.webp)

然后在新建的目录下创建一个`cpp`文件和`CMakeLists.txt`文件如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_BN9PNUFV6PF7GDR.webp)

## 编写CMakeLists.txt

在CMakeLists.txt中写入下面这些内容：

```plain
add_llvm_pass_plugin(LLVMEncodeFunction EncodeFunction.cpp)
```

其中`LLVMEncodeFunction`就是生成的插件文件的名称。`EncodeFunction.cpp`是`Pass`实现的源文件。

### add_llvm_pass_plugin

这是 LLVM 自定义 CMake 宏，定义在：`llvm/cmake/modules/AddLLVM.cmake`，它是专门为 Pass 插件设计的宏

它会自动帮你做：

| 功能 | 原因 |
|-|-|
| 生成 `.so / .dylib / .dll` | Pass 插件必须是动态库 |
| 设置 `-fPIC` | 位置无关代码 |
| 关闭 RTTI / exceptions | 与 LLVM 主库 ABI 一致 |
| 链接 LLVM 库 | 否则 Pass 无法运行 |
| 导出插件符号 | `llvmGetPassPluginInfo` |
| 处理平台差异 | Linux / macOS / Windows |

## CMake配置

```plain
-G Ninja
-DLLVM_ENABLE_PROJECTS="clang"
-DBUILD_SHARED_LIBS=ON
-DCMAKE_BUILD_TYPE=Release
-DCMAKE_C_COMPILER=clang
-DCMAKE_CXX_COMPILER=clang++
```

如果没有clang和clang++，那么需要下载clang/clang++。

## 建立CMake连接

在LLVM源码中编译Pass时，CLion的`CMake`会根据`CMakeLists.txt`文件生成对应的 `Makefile / build.ninja`文件，用于指导编译。而一个项目中有多个`CMakeLists.txt`，就需要建立`CMake`连接。

这里新建了一个`CMakeLists.txt`文件，但是并没有与原来项目的`CMake`连接起来，构建时不会自动寻找新建目录下的`CMakeLists.txt`进行加载，但是`llvm-project\llvm\lib\Transforms`路径下的`CMakeLists.txt`文件与LLVM的`CMake`是连接的，所以我们可以将新建目录添加到这个`CMakeLists.txt`文件中。

在`llvm-project\llvm\lib\Transforms`路径下的`CMakeLists.txt`文件中添加一行`add_subdirectory(<新建的目录>)`，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_4WCEUJ4QCC2VE6Y.webp)

`add_subdirectory(EncodeFunction)`的作用是：让 `CMake` 在处理当前 `CMakeLists.txt`时，进入 `EncodeFunction/`这个子目录，并加载该目录下的 CMakeLists.txt。

## 编写源代码

`Pass`的源码分成两部分：`Pass`功能源码和插件注册源码。

在新 Pass 管理器中：

| Pass 类型 | run() 签名 |
|-|-|
| **Function Pass** | `PreservedAnalyses run(Function &F, FunctionAnalysisManager &FAM)` |
| **Module Pass** | `PreservedAnalyses run(Module &M, ModuleAnalysisManager &MAM)` |
| **Loop Pass** | `PreservedAnalyses run(Loop &L, LoopAnalysisManager &LAM)` |
| **CGSCC Pass** | `PreservedAnalyses run(LazyCallGraph::SCC &SCC, CGSCCAnalysisManager &CGAM)` |
| **Region Pass**（较少用） | `PreservedAnalyses run(Region &R, RegionAnalysisManager &RAM)` |

下面的源码都要在同一个`cpp`源文件中。

### 功能源码

```cpp
#include "llvm/Pass.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
using namespace llvm;
namespace{
    class HelloWorldPass : public PassInfoMixin<HelloWorldPass> {
    public:
        PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM){
            std::cout << F.getName().str() << "\n";
            return PreservedAnalyses::all();
        }
        static bool isRequired() { return true; }
    };
}
```

这段代码就是一个`Function Pass`的功能源码，它的功能就是打印出函数名。

`static bool isRequired() { return true; }`在 LLVM 新 Pass 管理器（New PM） 里是一个强制策略声明，它的作用是告诉 LLVM：这个 Pass 是“必需 Pass”，在任何情况下都不允许被跳过。

即使出现以下情况：

| 场景 | 普通 Pass | `isRequired() == true` |
|-|-|-|
| `-O0` | ❌ 不跑 | ✅ 跑 |
| `__attribute__((optnone))` | ❌ 不跑 | ✅ 跑 |
| `optnone`函数 | ❌ 跳过 | ✅ 强制执行 |
| Pass Manager 认为“没必要” | ❌ 跳过 | ✅ 强制执行 |

其中`optnone`函数是最常见的，**在 **`**-O0**`**（Debug 模式）下编译的函数，就有 **`**optnone**`。

-O0的语义是：不要做任何优化或变换，方便调试。

而使用`clang/clang++`将`C/C++`转换成`ll`文件时，如果不指定其它的优化等级，那么就会默认是`-O0`。

而LLVM自带的Pass，比如`llvm/lib/Transforms/Utils`中的`HelloWorld.cpp`，它就没有`static bool isRequired() { return true; }`，这就导致使用`opt -passes=helloworld test.ll -o test.bc`不会报错，但是也不和预期一样打印出`test.ll`文件中的函数名。

### 插件注册源码

```cpp
llvm::PassPluginLibraryInfo getPluginInfo() {
    return {
        LLVM_PLUGIN_API_VERSION, "MyPass", LLVM_VERSION_STRING,
        [](llvm::PassBuilder &PB) {
            // 用这个以支持clang使用
            PB.registerPipelineStartEPCallback(
                [](ModulePassManager &MPM, OptimizationLevel Level) {
                    FunctionPassManager FPM;
                    FPM.addPass(HelloWorldPass());
                    MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
                }
            );
            PB.registerPipelineParsingCallback(
                [](
                    llvm::StringRef Name, llvm::ModulePassManager &MPM,
                    llvm::ArrayRef <llvm::PassBuilder::PipelineElement>
                ) {
                    if (Name == "about-option") {
                        MPM.addPass(createModuleToFunctionPassAdaptor(HelloWorldPass()));
                        return true;
                    }
                    return false;
                }
            );
        }
    };
}
```

#### 顶层结构

```plain
llvm::PassPluginLibraryInfo getPluginInfo() {
```

它是**插件入口函数，**由 `llvmGetPassPluginInfo()`调用，在 `opt`/ `clang`加载 `.so`时执行

#### 返回的插件元数据

```plain
return {
    LLVM_PLUGIN_API_VERSION, "MyPass", LLVM_VERSION_STRING,
```

这是一个 `PassPluginLibraryInfo`结构体，包含：

| 字段 | 含义 |
|-|-|
| `LLVM_PLUGIN_API_VERSION` | 插件 API 版本（必须与 LLVM 主版本一致） |
| `"MyPass"` | 插件名称 |
| `LLVM_VERSION_STRING` | LLVM 版本字符串 |
| 最后一个字段 | **回调函数（最重要）** |

#### 插件注册回调（核心）

```plain
[](llvm::PassBuilder &PB) {
```

**当插件被加载后：**

- **LLVM 会把 **`**PassBuilder**`**传进来**
- **在这里 注册 Pass 的使用方式**

它是 **Lambda 表达式**，在 `C++`中是 **匿名函数对象**。

```plain
[](llvm::PassBuilder &PB) {
    PB.registerPipelineStartEPCallback(...);
}
```

#### registerPipelineStartEPCallback

```cpp
PB.registerPipelineStartEPCallback([](ModulePassManager &MPM, OptimizationLevel Level) {
    FunctionPassManager FPM;
    FPM.addPass(HelloWorldPass());
    MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
});
```

registerPipelineStartEPCallback主要是为 clang（或任何构建默认优化管线的驱动）准备的。只有clang才能触发这个Pass，如果要通过opt加载Pass，可以删除。

回调函数内容：

`MPM`：当前正在构建的模块级 Pass 管理器

`Level`：-O0 ~ -O3

`FunctionPassManager FPM;`的作用是创建一个 `Function Pass` 管理器

`FPM.addPass(HelloWorldPass());`的作用是把你的 Pass 加入 Function Pass 管线

##### `MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));`

它的作用是把 `ModuleToFunctionPassAdaptor`对象存入 MPM 的内部容器

在 LLVM 新 PM 中：

| Pass 类型 | 管理者 |
|-|-|
| ModulePass | `ModulePassManager` |
| FunctionPass | `FunctionPassManager` |
| LoopPass | `LoopPassManager` |

这里的`Pass` 是 `Function Pass` 只能被`FunctionPassManager FPM;`管理。但这里的`Pass`要放到`MPM` 层面 ，也就是`MPM.addPass()`，这里的 `MPM`是`ModulePassManager`， 不能直接往 `MPM` 里塞 `Function Pass`。

`createModuleToFunctionPassAdaptor`的作用是把一个 `FunctionPassManager`适配成一个“看起来像 Module Pass 的东西”，也就是`ModuleToFunctionPassAdaptor`。

##### ModuleToFunctionPassAdaptor

`ModuleToFunctionPassAdaptor`的声明：`class ModuleToFunctionPassAdaptor : public ModulePass`。

`ModuleToFunctionPassAdaptor`是 ModulePass，所以可以放进 `ModulePassManager`

##### std::move(FPM)

`FPM`的声明：`FunctionPassManager FPM;`，它是 LLVM 的新 Pass 管理器。

而LLVM的新Pass管理器都具有如下特点：

1. **不可拷贝（non-copyable）**
2. **只能移动（movable）**
3. **持有 Pass 和 AnalysisManager 的状态**

所以不能`createModuleToFunctionPassAdaptor(FPM);`，即使是其它函数也不能直接将`FPM`作为参数传递给函数，因为在`C++`中直接以对象为参数时会触发拷贝构造函数，对对象进行拷贝，所以不能直接将`FPM`作为参数传递给函数。

`createModuleToFunctionPassAdaptor(std::move(FPM));`本质上是：

```plain
FunctionPassManager &&tmp = std::move(FPM);
createModuleToFunctionPassAdaptor(tmp);
```

`std::move`的作用是将`FunctionPassManager`类型转换成`FunctionPassManager&&`类型，这时候不会新创建任何对象，`FunctionPassManager&&`还是原来的对象

`FunctionPassManager&`是“左值引用”，表示“我借用你，不动你”，通过它可以引用对象，来修改或读取对象数据

`FunctionPassManager&&`是“右值引用”，表示“我不仅可以借，还可以直接拿走你的资源”，通过它也可以引用对象，来修改或读取对象数据。但是它也可以移动对象。

在以它为参数调用构造函数时，就会触发移动构造函数，比如`FunctionPassManager newFPM(std::move(oldFPM));`这样，使用`FunctionPassManager&&`创建一个新的`FunctionPassManager`对象，它会将普通成员(int/bool等类型的成员)的值拷贝给新对象，并将指针成员所指的数据复制到新对象的指针成员所指的内存中，然后将旧对象的成员指针变成`nullptr`。这就是移动拷贝。

##### 注意

这里的：

```cpp
FPM.addPass(HelloWorldPass());
MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
```

可以直接和下面的一样变成：

```cpp
MPM.addPass(createModuleToFunctionPassAdaptor(HelloWorldPass()));
```

`MPM.addPass(createModuleToFunctionPassAdaptor(HelloWorldPass()))`在执行过程中，内部一定会把 `HelloWorldPass()`加入到某个 `FunctionPassManager`中。

#### registerPipelineParsingCallback

```cpp
PB.registerPipelineParsingCallback([](llvm::StringRef Name, llvm::ModulePassManager &MPM, llvm::ArrayRef <llvm::PassBuilder::PipelineElement>) {
    if (Name == "about-option") {
        MPM.addPass(createModuleToFunctionPassAdaptor(HelloWorldPass()));
        return true;
    }
    return false;
});
```

这段代码的作用是：注册一个“管线解析回调”，当 LLVM 解析 `-passes=`字符串时，可以获取这个字符串并调用回调函数。通过下面的指令使用Pass

```cpp
opt -load-pass-plugin=./libMyPass.so \
    -passes=about-option \
    -disable-output \
    input.ll
```

第一种只需要加载so文件就会直接使用Pass，这种还需要再指明Pass的名称。

##### 回调函数参数

`llvm::StringRef Name`：-passes=里的一个名字。

`llvm::ModulePassManager &MPM`：当前正在构建的模块级 `Pass` 管线

`llvm::ArrayRef<llvm::PassBuilder::PipelineElement>`表示管线元素的上下文（嵌套管线），大多数简单 Pass 用不到，可以忽略。

#### 导出给 LLVM 插件的入口函数

```plain
extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
llvmGetPassPluginInfo() {
    return getPluginInfo();
}
```

这段代码的作用是让 LLVM 在加载你的 `.so / .dylib`插件时能够**发现并初始化这个 Pass 插件**。

##### extern "C"

它的作用是：

- 禁止 C++ 的名字修饰（name mangling）
- 确保 LLVM 能用 **C ABI** 找到这个函数

LLVM 是通过 `dlsym()`/ `LoadLibrary`动态查找符号名的，如果不是 `extern "C"`，函数名会被编译器改掉，导致找不到。

##### LLVM_ATTRIBUTE_WEAK

它的作用是：将该函数标记为 弱符号（weak symbol），允许插件中存在该函数，但主程序（opt / clang）中也可以没有该函数。可以避免链接冲突，并支持插件可选加载。

##### ::llvm::PassPluginLibraryInfo

它表示从「最外层（全局）命名空间」开始，找到 `llvm`命名空间，再找到其中的 `PassPluginLibraryInfo`

`PassPluginLibraryInfo`是一个结构体，通常包含：

```plain
struct PassPluginLibraryInfo {
  uint32_t APIVersion;          // LLVM Pass API 版本
  const char *PluginName;
  const char *PluginVersion;

  void (*RegisterPass)(PassRegistry&); // 或类似注册逻辑
};
```

在 **New Pass Manager** 中，它的核心作用是告诉 LLVM：这个插件支持的 API 版本，以及如何注册 Pass（通常通过 `PassBuilder`）

##### llvmGetPassPluginInfo()

这是 **固定函数名**，不能随便改。

LLVM 内部会做类似的事情：

```plain
auto *Fn = (decltype(&llvmGetPassPluginInfo))
           dlsym(Lib, "llvmGetPassPluginInfo");

if (Fn) {
    auto Info = Fn();
    Info.RegisterPass(...);
}
```

自动调用`llvmGetPassPluginInfo`函数来注册Pass，如果你不提供这个函数，Pass插件将无法被识别。

##### return getPluginInfo();

`getPluginInfo`就是上面的插件注册源码，他会返回 `PassPluginLibraryInfo`结构体，包含：

| 字段 | 含义 |
|-|-|
| `LLVM_PLUGIN_API_VERSION` | 插件 API 版本（必须与 LLVM 主版本一致） |
| `"MyPass"` | 插件名称 |
| `LLVM_VERSION_STRING` | LLVM 版本字符串 |
| 最后一个字段 | **回调函数（最重要）** |

用于让LLVM识别和注册插件。

## 编译

如果在CLion的运行配置中可以找到Pass项目，那么直接选中项目，进行构建即可。

如果找不到的话，在`llvm`目录下的`bulid`(就是构建目录，名称未必是`bulid`)执行命令`ninja EncodeFunctionName`，在`bulid`目录下的`lib`目录中就会出现`EcodeFunctionName.so`文件。

## 使用

```plain
opt -load-pass-plugin=/home/xiaopangguo/Tool/LLVM/llvm-project-22.1.5.src/llvm/cmake-build-release/lib/EncodeFunctionName.so
-passes=about-option
test.ll
-o output.ll
```

通过这个指令可以使用插件Pass。

# 在LLVM源码外创建和编译LLVM Pass

## 构建一个llvm项目

想要在LLVM源码外创建和编译LLVM Pass，需要先构建一个llvm项目，也就是构建`llvm-project/llvm`中的一个工具，比如`clang`或`opt`或者是前面的操作，如果已经做过了，可以跳过这一步。

先以项目的形式打开`llvm-project/llvm/CMakeLists.txt`，选择构建类型，在windows中工具链必须选择`Visual Studio`，Linux中使用默认的即可，并设置CMake选项为：

```plain
-G Ninja
-S llvm-project\llvm   //它可以省略
注意上面所说的llvm-project\llvm，是指llvm-project/llvm的完整路径。
```

它的作用是：Configure（配置）具体干了这些事：

1. **检测你的编译器**（MSVC / clang-cl）
2. **读取 **`**llvm-project/llvm/CMakeLists.txt**`
3. **生成 Ninja 构建文件**（`build.ninja`）到 `llvm-build`
4. **准备所有 LLVM 工具、库、头文件的编译规则**

**注意：这一步并不会生成任何 **`**.exe**`**或 **`**.lib**`**文件！**

然后设置构建目录，可以使用默认的（会创建`cmake-bulid-release-visual-studio`目录在`llvm-project/llvm`目录），也可以自己设置。如下所示：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_E79HBH2EMEGAMMG.webp)

然后点击确定即可，CLion会自动加载llvm项目的CMake

## 编译Pass

### 创建Pass项目

<font style="color:rgb(0, 0, 0);">可以从 LLVM 的源代码树外部开发 LLVM passes（针对于已安装或构建的 LLVM）。下面提供了一个项目布局的示例。</font>

```plain
<project dir>/
    |
    CMakeLists.txt
    <pass name>/
        |
        CMakeLists.txt
        Pass.cpp
        ...
```

然后使用CLion以项目形式打开`<projecct dir>/CMakeLists.txt`如下图所示：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_Z85K43HHJSAHWPH.webp)

<project dir>/CMakeLists.txt 的内容如下：

```plain
find_package(LLVM REQUIRED CONFIG)

separate_arguments(LLVM_DEFINITIONS_LIST NATIVE_COMMAND ${LLVM_DEFINITIONS})
add_definitions(${LLVM_DEFINITIONS_LIST})
include_directories(${LLVM_INCLUDE_DIRS})

add_subdirectory(<pass name>)
```

注意这里的`<pass name>`就是在项目下新建的目录名称`HelloPass`，如下图所示：
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_NTFYURCCQWGW8GS.webp)

<project dir>/CMakeLists.txt 的内容如下：

```plain
add_llvm_pass_plugin(<plugin name> <source file name>)
```

`<plugin name>`是生成的Pass文件的名称，`<source file name>`是Pass的源文件，也就是`<pass name>`目录下的`cpp`文件。如下图所示：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_4PCP8DBNCYEC3CX.webp)

### 配置CMake

使用的CMake配置如下：

```plain
-G Ninja
-DLLVM_DIR=llvm-project/llvm/cmake-bulid-release-visual-studio/lib/cmake/llvm"
```

如下所示：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_QMTSUMMCQMUEA3T.webp)
然后点击确定，CLion会自动加载CMake，但是这是会出现许多报错如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_FWJERZA29ZQ52Z5.webp)

这个报错只需要将`project(ProjectName)`添加到`<project dir>/CMakeLists.txt`中的`find_package(LLVM ...)`的上面，并将`ProjectName`改成`<project dir>`的名称。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_98VVCACCDPGRXGF.webp)

整个报错只需要在`<project dir>/CMakeLists.txt`中添加`include(AddLLVM)`，并且要添加到`find_package(LLVM ...)`之后。

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_KZ2XD4MTD7GFCJX.webp)

这个报错只需呀将`cmake_minimum_required(VERSION 4.2)`添加到`<project dir>/CMakeLists.txt`中，并且要添加到`project(ProjectName)`上面。

修改后的`<project dir>/CMakeLists.txt`的内容如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_7H2BT5V2B2N47UV.webp)

可能还有其它的报错但是不用管，通常只要将这几个报错解决了就可以正常加载`CMake`了。

然后在CLion的运行配置中找到`<plugin name>`，选中然后点击确定，如下
 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_FQZ6A965HG38JN7.webp)
然后点击构建。就会在`build`目录创建一个`<plugin name>`目录，在这个目录会有一个so文件，这个so文件的名称与在`<project dir>/<pass name>/CMakeLists.txt`中设置的名称一样，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_VYDMJ9W9ZU6MGTU.webp)

## 使用Pass

通过下面指令使用Pass：

```plain
opt -load-pass-plugin=/home/xiaopangguo/Study/ollvm/outpass/cmake-build-release/HelloPass/LLVMHello.so
    -passes=about-option
    test.ll
```

其中`-load-pass-plugin=`的后面是生成的so文件的完整路径。

# 通过clang/clang++使用Pass

上面介绍了如何通过`opt`使用插件式Pass，在LLVM中`clang/clang++`也是可以使用插件式Pass的。

通过`opt`使用Pass，需要先使用`clang/clang++`将源码转换成`ll`文件。如果通过`clang/clang++`使用Pass，可以在生成可执行文件的过程中，执行Pass。想要让Pass的插件文件可以被`clang/clang++`使用，就必须在`llvm::PassPluginLibraryInfo getPluginInfo() {}`中添加下面这段代码

```plain
PB.registerPipelineStartEPCallback([](ModulePassManager &MPM, OptimizationLevel Level) {
    FunctionPassManager FPM;
    FPM.addPass(HelloWorldPass());
    MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
});
```

通过`clang/clang++`使用Pass，使用下面的指令：

```plain
clang++ -fpass-plugin=/home/xiaopangguo/Study/ollvm/outpass/cmake-build-release/HelloPass/LLVMHello.so
        test.cpp -o demo_test
```

```plain
clang++ -fpass-plugin=/home/xiaopangguo/Study/ollvm/outpass/cmake-build-release/HelloPass/LLVMHello.so
        test.cpp -o demo_test
```

# 将Pass嵌入opt/clang/clang++

我的`Ubuntu22.04.5`虚拟机太卡了，所以这一章节`Windows`系统中的`CLion`进行操作，`Windows`对内嵌式的`Pass`是支持的。

## CMake配置

CMake的配置如下：

```cpp
-G Ninja
-DLLVM_ENABLE_PROJECTS="clang"
-DCMAKE_BUILD_TYPE=Release
-DCMAKE_CXX_FLAGS="/utf-8"
```

在`Linux`环境中，还使用上面的CMake配置应该是没有问题的。`Linux`和`Windows`的操作都是一样的。如果有难以解决的问题，可以发到评论区让我看一下。

## 创建项目

在`llvm-project/llvm/lib/Transforms/`目录创建一个目录`<Pass Dir>`，名称随意，并在该目录下创建一个`CMakeLists.txt`文件和`.cpp`文件，如下所示：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_E7M5AK9FHDNDWQ4.webp)

注意：这里之所以选择`llvm-project/llvm/lib/Transforms/`是因为要想内建`Pass`，就必须将`Pass`项目加入到`LLVM`的`CMake`，而这个目录是`LLVM`官方推荐的目录，直接在`llvm-project/llvm/lib/Transforms/CMakeLists.txt`中添加下面这行内容：

```plain
add_subdirectory(<Pass Dir>)
```

这里的`<Pass Dir>`就是你在`Transforms`目录下新建的目录的名称。如果你比较熟悉`LLVM`项目，可以选择再其它目录下进行操作。

然后在`llvm-project/llvm/include/llvm`目录找到地方创建一个`h`文件，通常选择在`llvm-project/llvm/include/llvm/Transforms/`目录下创建一个目录，然后在新建目录中创建一个`h`文件。只要这个`h`文件在`llvm-project/llvm/include/llvm`目录下就行。如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_EM3CMNK98GA2QER.webp)

`h`文件的内容如下：

```plain
#include "llvm/IR/PassManager.h"

namespace llvm {

    class EncodeFunctionName : public PassInfoMixin<EncodeFunctionName> {
    public:
        PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM);
        static bool isRequired();
    };
} // namespace llvm
```

`llvm-project/llvm/lib/Transforms/EncodeFunctionName/EncodeFunctionName.cpp`的内容如下：

```cpp
#include "llvm/Transforms/EncodeFunctionName/EncodeFunctionName.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Transforms/EncodeFunctionName/EncodeFunctionName.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
using namespace llvm;
PreservedAnalyses llvm::EncodeFunctionName::run(Function &F, FunctionAnalysisManager &AM){
  errs() << "EncodeFunctionName: " <<F.getName() << " -> ";
  if (F.getName().compare("main") != 0) {
    llvm::MD5 Hasher;
    llvm::MD5::MD5Result Hash;
    Hasher.update("guoshuyu");
    Hasher.update(F.getName());
    Hasher.final(Hash);

    SmallString<32> HexString;
    llvm::MD5::stringifyResult(Hash, HexString);
    F.setName(HexString);
  }
  errs() << F.getName() << "\r\n";

  return PreservedAnalyses::all();
}

bool llvm::EncodeFunctionName::isRequired() { return true; }
```

`llvm-project/llvm/lib/Transforms/EncodeFunctionName/CMakeLists.txt`的内容如下：

```plain
add_llvm_component_library(<target file name> <source file>)
```

注意这里的`<target file name>`是生成的库文件的名称，这里的这个名称必须以`LLVM开头`

### add_llvm_component_library

`add_llvm_component_library`和`add_llvm_pass_plugin`的作用一样都是声明一个库文件，只是`add_llvm_pass_plugin`的作用倾向于生成一个插件动态库。而`add_llvm_component_library`就是生成库文件，包括静态库和动态库。

`add_llvm_component_library`最后生成的是动态库*(`.so/.dll`)还是静态库(`.a/.lib`)，由 `BUILD_SHARED_LIBS`决定，如果`BUILD_SHARED_LIBS=ON`，那么最后生成的即使动态库，反之就是静态库。

要注意：当`BUILD_SHARED_LIBS=ON`时，虽然生成的是动态库，但是，这个动态库不一定是插件，除非导出`llvmGetPassPluginInfo`。这是插件与动态库的区别。

它通常用于“内置 Pass”（编进 LLVM / opt），因为内置的Pass都是静态链接到程序中的

## 注册Pass

要想将`Pass`嵌入到`opt/clang/clang++`，前面的步骤都是相同的，但是到注册`Pass`它们的操作是不一样的。

### opt

现在为了“注册” Pass，需要将其添加到几个地方。将以下内容添加到 `llvm-project/llvm/lib/Passes/PassRegistry.def`的`FUNCTION_PASS` 部分

```plain
FUNCTION_PASS("encode-function-name", EncodeFunctionName())
```

这时`EncodeFunctionName()`会报错。还需要再在`llvm-project/llvm/lib/Passes/PassBuilder.cpp`中，引入`EncodeFunctionName.h`头文件，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_GFCHHK549KPV8YN.webp)

并在`llvm-project\llvm\tools\opt\CMakeLists.txt`文件中的`set(LLVM_LINK_COMPONENTS ...)`中将Pass库添加进去，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_KZ6W3ZQKPGQRE3K.webp)

这里的`EncodeFunctionName`要替换成`<Pass Dir>/CMakeLists.txt`中设置的库文件名称去掉`LLVM`后的名称。因为`LLVM_LINK_COMPONENTS`是 `LLVM` 自己的 `component` 依赖机制，它做的事情是：根据你写的 `component` 名自动找到对应的 LLVMXXX.lib，并设置 `include` 路径，处理 `inter-library dependencies`。

### clang/clang++

#### 把 Pass 内建进 clang/clang++ 的 O2/O3

在`llvm-project/llvm/lib/Passes/PassBuilderPipelines.cpp`文件中引入`Pass`的头文件。如果是`Function Pass`就在`llvm-project/llvm/lib/Passes/PassBuilderPipelines.cpp`文件中寻找`void PassBuilder::buildFunctionSimplificationPipelin`函数，然后在该函数中`FunctionPassManager FPM;`的下面添加代码：

```cpp
FPM.addPass(MyPass()); // 这里的MyPass是类名
```

任何位置都可以，关键是要确保这段代码在`FunctionPassManager FPM;`下面，并函数执行时一定会执行这行代码。

如果是`Module Pass`就寻找`void PassBuilder::buildModuleOptimizationPipeline`函数，然后在该函数中添加下面的代码：

```cpp
MPM.addPass(MyPass());
```

`clang/clang++` 使用 `-O2/-O3`时会自动跑`Pass`，不需要额外的参数。如果你想可以控制是否启动`Pass`，那么可以看下面的内容：`通过-mllvm`控制是否启用Pass

#### 通过`-mllvm`控制是否启用Pass

如果想要`clang/clang++`通过`-mllvm`控制是否启用`Pass`，那么处理上面的操作还要修改`Pass`的`cpp`源文件。

首先要在`Pass`的`cpp`源文件中添加下面的代码：

```cpp
static cl::opt<bool>
MyPassEnabled("enable-pass",	// 这是pass的标识，要启用哪个pass就输入哪个pass的标识
             cl::init(false),	// 设置MyPassEnabled的初始值为false
             cl::desc("Enable my pass"));// 这是pass的描述
```

注意这段代码要添加到`Pass`的`run`函数的上面，而且要添加到全局作用域中。这段代码是在创建一个变量`EnableMyPass`，这个变量的类型是`cl::opt<bool>`对象，它是LLVM 的全局命令行参数注册对象，它是一个布尔类型的对象，而`()`中的三个值就是这个对象的构造参数。

只有在执行`clang -O2 -mllvm -enable-pass target.c`这种使用`-O2 -mllvm -enable-pass`指定要使用这个`Pass`的情况下，才会使得`MyPassEnabled`的值变成`true`

然后再添加下面的代码：

```cpp
if (!MyPassEnabled)
    return PreservedAnalyses::all();
```

这段代码要添加到`run`函数中，而且要添加到`run`函数的开头。这段代码是控制`Pass`启用的核心。如果`clang/clang++ -O2/O3`命令中指定使用`enable-pass`这个`Pass`，那么`MyPassEnabled`的值就是`true`，所以可以正常执行`Pass`。反之，`MyPassEnabled`的值就是`false`，所以直接返回`PreservedAnalyses::all()`结束`Pass`的运行，不执行`Pass`的核心代码，使得`Pass`无法发挥作用

#### 链接LLVMPasses

做完上面这些内容后，还需要将Pass的源码链接到`LLVMPasses`库文件中。在`llvm-project\llvm\lib\Passes\CMakeLists.txt`中的`add_llvm_component_library(LLVMPasses ... LINK_COMPONENTS ...)`中的`LINK_COMPONENTS`的下面添加去掉`LLVM`的`Pass`的库文件名称，如下：

 ![图片描述](https://bbs.kanxue.com/upload/attach/202605/973331_PN2TM92MFHRATMN.webp)

## 使用

然后编译`opt/clang/clang++`就可以使用了。注意：编译`clang`是会自动编译`clang++`

### opt

通过下面的指令使用`Pass`：

```cpp
opt -passes=encode-function-name
    "C:\Users\86150\Desktop\ARM64汇编逆向学习\C++\cpp-rev\cpp-rev\test.ll"
```

这里的`encode-function-name`就是注册的Pass名称。

### clang/clang++

通过下面的指令使用`Pass`:

```cpp
clang -O2 -mllvm -enable-pass test.cpp -o test.exe
```

`-mllvm`的作用是：把后面的字符串原样传递给 `LLVM` 的命令行解析系统，由该系统去匹配并赋值给对应的 `cl::opt`变量。

注意，这里的`-O2`不能省略，因为`Pass`是构建在`clang/clang++`的优化管道(`-O2/O3`)中的，使用`-O0`是不会构建这个`Pass`，所以即使Pass源码中有`bool llvm::EncodeFunctionName::isRequired() { return true; }`在`-O0`的情况下也不会执行Pass。

# 参考

https://llvm.gnu.ac.cn/docs/CMake.html#developing-llvm-passes-out-of-source
https://www.bilibili.com/video/BV1Bf3neVEnN/?spm_id_from=333.337.search-card.all.click&vd_source=ecea8ce2739562dba212ce5b61f070bc
https://github.com/urlyy/llvm-new-pass-tutor

---

# 回复

## 回复 by 温泉划水鱼 (#2)

*2026-5-16 10:58*

1

## 回复 by SomeMx (#3)

*2026-5-16 15:01*

学习一下

## 回复 by jw8888 (#4)

*2026-5-16 15:40*

111

## 回复 by mb_xjdhrmck (#5)

*2026-5-17 23:39*

666

## 回复 by huangjw (#6)

*2026-5-18 09:15*

有空还要再复习下，很久没用了

## 回复 by B.M.K (#7)

*2026-5-22 20:17*

66

## 回复 by 呆萌的小白 (#8)

*2026-5-23 16:25*

表哥牛逼

## 回复 by 简单的简单 (#9)

*2026-5-24 23:46*

666

## 回复 by mb_uvyukvot (#10)

*2026-5-26 11:07*

666

## 回复 by mb_aopnnvxb (#11)

*2026-5-28 13:52*

mark

## 回复 by mb_fcfcydvu (#12)

*2026-6-3 00:20*

6999999

## 回复 by ulong9527 (#13)

*2026-6-26 09:44*

感谢分享，学习一下

## 回复 by iBa0 (#14)

*2026-7-7 21:05*

1

## 回复 by wx_kx92911 (#15)

*2026-7-9 10:06*

感谢分析
