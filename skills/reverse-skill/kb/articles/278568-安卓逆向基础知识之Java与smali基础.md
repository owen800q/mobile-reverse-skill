---
title: '[原创]安卓逆向基础知识之Java与smali基础'
url: https://bbs.kanxue.com/thread-278568.htm
tid: 278568
author: 黎明与黄昏
date: '2023-08-24'
tags: [Android安全, 原创, 基础理论]
crawled_at: '2026-07-31T14:39:02+08:00'
replies: 9
---

## 一、Java基础

Java作为一种面向对象语言。最为重要的两个概念那就是类和对象：

**类**：类是一个模板，它描述一类对象的行为和状态。

**对象**：对象是类的一个实例，有状态和行为。

类和对象之间的关系就像人类和某个人之间的关系，人类拥有一些行为和状态，这些行为和状态作为了人类的特征；用面向对象的思维来说，每个人可以说是人类这个类实例化的对象，在拥有人类的行为和状态下还拥有各自的特点。

### 基础数据类型

数据类型分为四大类八种，四大类是：整形、浮点型、字符型、布尔型；整形可以细分为byte、short、int、long；浮点可以细分为float、double。

1、整数类型默认为int类型，占4字节，当使用字节大小是大于它的long类型时，除了需要定义变量为long类型，还需要在值后面加L或者l才能将该变量表示为long类型。如：long l = 123456789l;

2、浮点类型默认为double类型，占8字节，在值后面加上F/f就是float类型了。如：float f = 3.14f;

### 类型转换

| 123456789101112131415161718192021222324252627282930313233343536373839404142 | `package` `com.java.TypeDome;` `public` `class` `TypeDome {``public` `static` `void` `main(String[] args) {``// 1、自动类型转换``// 占内存小的类型的变量可以赋值给内存占的大的类型的变量``byte` `a =` `10``;``int` `b = a;` `// 发生了自动的类型转换``System.out.println(a);``System.out.println(b);` `System.out.println(``"---------------------------------------------"``);` `// 2、表达式的自动类型转换``// 表达式的最终结果类型由表达式中的最高类型决定``int` `i =` `10``;``int` `j =` `10``;``double` `ij =` `1.0``;``// int ji = i + j + ij;  java: 不兼容的类型: 从double转换到int可能会有损失``double` `ji = i + j + ij;``System.out.println(ji);``// 在表达式中，byte、short、char是直接转换成int类型参与运算的``byte` `one =` `20``;``byte` `two =` `25``;``// byte three = one + two;  java: 不兼容的类型: 从int转换到byte可能会有损失``int` `three = one + two;``System.out.println(three);` `System.out.println(``"---------------------------------------------"``);` `// 3、强制类型转换``// 强制类型转换可能造成数据的丢失``// 下面的数据都为有符号位``int` `o =` `1500``;` `// 00000101 11011100``byte` `t = (``byte``) o;` `// 11011100``System.out.println(t);` `// 输出结果：-36``// 小数强制转换为整数是直接舍弃小数保留整数``double` `dou =` `81.5``;``int` `interesting = (``int``) dou;``System.out.println(interesting);` `// 输出结果：81``}``}` |
|-|-|

### 修饰符

Java提供了两类修饰符。分别是访问修饰符和非访问修饰符。

#### 访问修饰符

访问修饰符是一种用来限制类、接口、类成员（字段、方法、构造函数等）访问权限的关键字，主要包括以下四种：

1. public：公共访问修饰符，表示该类或类成员可以被任何其他类访问。
2. private：私有访问修饰符，表示该类或类成员只能在本类中被访问，其他类无法访问。
3. protected：受保护的访问修饰符，表示该类或类成员只能在本类和其子类中被访问，其他类无法访问。
4. default（默认，即不写访问修饰符）：默认访问修饰符，表示该类或类成员只能在同一包内被访问，其他包中的类无法访问。

#### 非访问修饰符

为了实现一些其他的功能，Java 提供了很多非访问修饰符，如：

1. static：静态修饰符，表示该类成员是静态的，可以直接通过类名调用而不需要创建实例。
2. final：最终修饰符，表示该类、方法或变量是不可修改的，一旦被赋值则无法再次修改。
3. abstract：抽象修饰符，表示该类或方法是抽象的，不能被实例化或调用，只能被子类继承或实现。
4. synchronized：同步修饰符，表示该方法或代码块是同步的，多个线程不能同时访问，保证线程安全。
5. transient：瞬态修饰符，表示该变量在序列化时会被忽略，即不会被保存到文件中。
6. volatile：易失修饰符，表示该变量是易失的，多个线程对其进行操作时不会进行缓存，保证可见性和原子性。

### 运算符

```
package com.java.operator;

public class Operators {
    public static void main(String[] args) {
        // 1、运算符有+、-、*、/、%，和c、和python中的运算符一模一样
        // 2、+除了做基本的数学运算符，在与字符串进行+运算时会被当成连接符，其结果还是字符串；加法口诀：能算则算，不能算则拼接成字符串
        int i = 10;
        String str = "Thank You";
        System.out.println((str + i));  // 输出显示：Thank You10

        System.out.println("---------------------------------------------");

        // 3、自增运算符++和自减运算符--的运算规则：++或者--在变量的前面表示先自增或者自减后再运算，在变量的后面表示先运算再自增或者自减
        int m = 10;
        int n = m++;
        System.out.println(m);  // 11
        System.out.println(n);  // 10

        System.out.println("---------------------------------------------");

        // 4、赋值运算符：+=、-=、*=、/=、%=；赋值运算符格式：变量 赋值运算符 (变量的类型) 值
        int o = 10;
        double t = 20.0;
        o += t;
        System.out.println(o);  // 显示结果：30

        System.out.println("---------------------------------------------");

        // 5、条件运算符：==、!=、>=、<=、>、<；如果条件成立就返回true，条件不成立就返回false
        int d1 = 10;
        int d2 = 5;
        System.out.println(d1 == d2);  // 显示结果：false

        System.out.println("---------------------------------------------");

        // 6、逻辑运算符：逻辑与(&)、逻辑或(|)、逻辑非(!)、逻辑异或(^)、短路与(&&)、短路或(||);
        // 逻辑与：必须都为true，有一个false就为false，但前一个为false后一个依旧执行
        System.out.println((d1 <= d2) & (++d2 >= 10));
        System.out.println(d2);
        // 短路与：必须都为true，有一个false就为false，但前一个为false后一个就不执行
        System.out.println((d1 <= d2) && (++d2 >= 10));
        System.out.println(d2);
        // 逻辑或：得有一个为true，全部为false就为false。但前一个为true后一个依旧执行
        // 短路或：得有一个为true，全部为false就为false。但前一个为true后一个就不执行
        // 逻辑非：取反
        // 逻辑异或：相同是false，不同是true

        System.out.println("---------------------------------------------");

        // 7、三元运算符格式：条件表达式？条件表达式为true时返回的值: 条件表达式为false时返回的值；
        int zhen = d1 >= d2? d1: d2;
        System.out.println(zhen);
    }
}
```

### 流程控制语句

#### if……else……语句

| 12345678910111213141516171819202122232425262728293031 | `package` `com.java.ProcessControl;` `import` `java.util.Scanner;` `public` `class` `IfElse {``public` `static` `void` `main(String[] args) {``// if(条件表达式1) {``//  条件表达式1返回值为true时执行的代码……``// } else if(条件表达式2) {``//  条件表达式1不成立但条件表达式2成立时执行的代码``// }……else {``//  如果上面的所有条件表达式都不成立时执行的代码``// }``Scanner sca =` `new` `Scanner(System.in);``System.out.println(``"请输入该同学的成绩："``);``int` `grades = sca.nextInt();``if` `(grades <` `0` `\|\| grades >` `100``) {``System.out.println(``"成绩不存在"``);``}``else`  `if` `(grades >=` `90``) {``System.out.println(``"该同学必成龙凤！！"``);``}``else` `if` `(grades >=` `80``) {``System.out.println(``"该同学成绩优秀"``);``}``else` `if` `(grades >=` `70``) {``System.out.println(``"该同学成绩一般"``);``}``else` `if` `(grades >=` `60``) {``System.out.println(``"该同学成绩及格，还需努力！"``);``}``else` `{``System.out.println(``"挂科"``);``}``}``}` |
|-|-|

#### switch语句

switch case 语句判断一个变量与一系列值中某个值是否相等，每个值称为一个分支。

```
package com.java.ProcessControl;

import java.util.Scanner;

public class SwitchCase {
    public static void main(String[] args) {
        Scanner s = new Scanner(System.in);
        System.out.println("请输入当前汽车挡位");
        int i = s.nextInt();  // 输入一个整形数据
        switch (i) {  // switch (表达式) {}中表达式不支持double、float、long类型
            case 1:  // case给出的值不允许重复，且只能是字符串常量或字面量。
                System.out.println("很稳健！");
                break;  // 不要忘记写break，不然会往下执行，直到退出switch
            case 2:
                System.out.println("你准备加速了!");
                break;
            case 3:
                System.out.println("请注意别超速");
                break;
            case 4:
                System.out.println("请注意减速！");
                break;
            case 5:
                System.out.println("你开的太快了！");
                break;
            case '6':
                System.out.println("此车没有倒挡！");
                break;
            default:
                System.out.println("没有此挡位！");
        }
    }
}
```

switch case 执行时，一定会先进行匹配，匹配成功就开始执行case 语句之后的语句，再根据是否有 break，判断是否继续输出，或是跳出判断。

#### 循环语句

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354 | `package` `com.java.circulate;` `public` `class` `Circulate {``public` `static` `void` `main(String[] args) {``/*``* for (初始化数据语句;循环条件;迭代语句) {``*   循环代码;``* }``* */``int sum=0;``for (int i=1;i<6;i++) {``sum += i;``}``System.out.println(sum);` `/*``* while (循环条件) {``*   循环语句;``*   迭代语句;``* }``* */``int i=1;``while (i<=1000) {``int num=1;``int j=i;``for (;i!=0;i/=10) {``num*=(i%10);``}``i=j;``if (num == i) {``System.out.println(i);``}``i++;``}` `/*``* do {``*   循环语句;``*   迭代语句;``* } while (循环条件);``* do{}while循环的特点：一定会先执行一次循环体里的内容。``* */``int n=1;``do {``System.out.println("我是" + n);``n++;``}while (n%2==0);` `/*``* break:跳出并结束当前所在循环的执行，或者结束所在switch分支的执行``* continue：用于跳出当前循环的当次执行，进入下一次循环，只能在循环中使用``* */``}``}` |
|-|-|

### 数组

```
package com.java.ArrayDemo;

public class JavaArray {
    public static void main(String[] args) {
        // 数据类型[] 数组名称 = new 数据类型[]{元素1、元素2……}  // new代表创建的意思
        int[] arr1 = new int[] {1,2,3,4,5,6};

        // 简化写法：
        int[] arr2 = {7,8,9,10,11,12,13,14,15};

        // 取值：数组名[索引];
        System.out.println(arr2[5]);
        int i = arr1[3];
        System.out.println(i);

        // 赋值：数组名[索引] = 值;
        arr2[3] = 100;
        System.out.println(arr2[3]);

        // 获取数组最大的长度：数组名.length;
        System.out.println(arr2.length);

        // 数组其他写法：数据类型 数组名称[]
        int arr3[] = {1,2,3,4,5};

        // 什么类型的数组只能存放什么类型的数据
        // 数组一旦定义出来之后，类型和长度也就固定了

        /*
        * 动态初始化数组：当前还不清楚要存哪些数据就使用动态初始化数组
        * byte、short、char、int、long动态初始化默认值为0；float、double动态初始化默认值为0.0；boolean动态初始化默认值为false
        * 类、API接口、数组、String动态初始化数组为null
        * */
        int[] arr4 = new int[3];
        System.out.println(arr4[0]); // 0
        System.out.println(arr4[1]); // 0
        arr4[2] = 100;
        System.out.println(arr4[2]); // 100
    }
}
```

### 方法

```
package com.java.method;

public class Methods {
    public static void main(String[] args) {
        /* 方法格式：
        *修饰符 返回值类型 方法名(形参列表){
        *   方法中要执行的代码
        *   return 要返回的值;  // 方法声明了具体的返回值类型，内部必须使用return返回对应的数据类型的数据
        * }
        * 注意：基本类型数据传入到方法中是传入的值，修改传入到方法的值是不会影响到全局变量；
        * 而引用类型数据传入到方法中的是地址，修改方法内的值是会改变全局变量的
        * */
        int s = sum(100,200);
        System.out.println(s);
    }
    public  static int sum(int a,int b) {
        return a+b;
    }
}
```

### 面向对象

面向对象是Java的重中之重，之间简单介绍了对象和类的关系，现在正式来讲解一下面向对象相关知识。

#### 构造器

每个类都有构造器。如果没有主动的为类定义构造器，Java 编译器将会为该类提供一个默认的无参构造器。构造器的主要作用是初始化对象的数据成员，在创建一个对象时，构造器会被自动调用来为对象的各个数据成员赋初值。

面向对象基础实例：

ClassMethod.java文件

```
package com.java.ClassObject;

/*
 * JAVA类声明中关键字public起到什么作用呢？如下ClassMethod类的声明:
 * 按着字面的意思理解是：ClassMethod类是公共的，要求ClassMethod类与类文件名必须保持一致，并且一个java文件中只能有一个public关键字声明的类。
 * public是表示公有的，private是表示私有的，私有的只能在面向对象中访问。
 * */

/*
* Java面向对象底层原理：
* Java面向对象底层是由三个区域组成，分别是方法区、栈内存、堆内存，执行流程大概如下所示：
* 1、将类加载到方法区
* 2、将类中的main方法压入栈内存当中
* 3、执行main方法中的代码，如果创建对象又会将对象对应的类加载到方法区，并且将对象的相对偏移地址压入栈内存中存储，而对象在堆内存中存储。
* 4、堆内存中的对象不仅可以存储属性数据，还可以存储方法（即对象的方法），但方法是以引用地址的形式存储在堆内存当中，方法代码需要通过引用地址去方法区调用。
* 5、方法区中存储了类的结构信息，包括类的属性、方法、常量池等。
* */

public class ClassMethod {
    public static void main(String[] args) {
        // 创建对象：类名 对象名 = new 类名();
        Zoo z = new Zoo("市中心动物园", 10);
        z.n = 1;
        z.main("长颈鹿", 11.4, 0.8);
    }
}
```

Zoo.java文件

```
package com.java.ClassObject;

public class Zoo {
    public String name;
    public int num;

    // 定义无参数构造器，构造器就是对面向对象属性进行初始化
    public Zoo() {
        System.out.println("这是无参数构造器！");
    }

    // 定义有参数构造器
    public Zoo(String name, int num) {
        this.name = name;  // this关键字代表用于存储当前对象的存储地址
        this.num = num;
        System.out.println("动物园叫" + name + "，动物园有" + num + "动物园区");
        System.out.println("这是有参数构造器！");
    }

    // 定义/初始化变量：修饰符 数据类型 变量名称 = 初始化值;
    public int n;
    public static void dong_wu(String name,double h,double w) {
        System.out.println("在动物园看到了" + name + ",它身高有" + h + "米，它宽度有" + w + "米");
    }
    public void main(String z, double h, double w) {
        for (;n!=0;n--) {
            dong_wu(z, h, w);
        }
    }
}
```

#### 面向对象三大特性之封装

封装指的是将数据和操作数据的方法封装在一个单元内部，并通过访问权限控制来限制外部对该单元的访问。

例如，下面是一个简单的Java类，它封装了一个学生的姓名和年龄：

| 1234567891011121314151617181920 | `public` `class` `Student {``private` `String name;``private` `int` `age;` `public` `String getName() {``return` `name;``}` `public` `void` `setName(String name) {``this``.name = name;``}` `public` `int` `getAge() {``return` `age;``}` `public` `void` `setAge(``int` `age) {``this``.age = age;``}``}` |
|-|-|

可以看到在这个类中，姓名和年龄都是私有成员变量，只能通过公开的getter和setter方法来访问和修改。这样，我们就可以在外部控制和限制对这些成员变量的访问。

#### 面向对象三大特性之继承

继承就是子类继承父类的特征和行为，使得子类对象（实例）具有父类的实例域和方法，或子类从父类继承方法，使得子类具有父类相同的行为。

Java中的继承是单继承的，也就是说每个子类只能继承一个父类。Java中通过使用关键字"extends"来实现继承。

继承的语法格式如下所示：

```
class SubClass extends SuperClass {
    // SubClass 类的属性和方法
}
```

其中，SubClass是子类，SuperClass是父类。子类可以继承父类的属性和方法，同时可以添加自己的属性和方法。

Java中的所有类都继承自Object类。因此，如果没有指定父类，Java中的类默认继承自Object类。

Java中的继承关系可以形成继承层次结构，也就是说一个子类可以成为另一个子类的父类。Java中的继承层次结构可以使用继承关系图来表示。

在子类继承父类后，构造器会有以下特点：

1. 子类中所有的构造器默认都会先访问父类中无参的构造器，再执行自己。这是因为子类在初始化的时候，有可能会使用到父类中的数据，如果父类没有完成初始化，子类将无法使用父类的数据。
2. 如果父类中没有无参的构造器，子类必须使用super关键字显式调用父类的构造器，并传入相应的参数。例如：

```
public class SubClass extends SuperClass {
   public SubClass(int x, int y) {
      super(x); // 调用父类的有参构造器
      // 子类的构造器逻辑
   }
}
```
3. 子类通过this(...)去调用本类的其他构造器，本类其他构造器会通过super去手动调用父类的构造器，最终还是会调用父类构造器的。例如：

```
public class SubClass extends SuperClass {
   public SubClass(int x) {
      this(x, 0); // 调用本类的有参构造器
   }

   public SubClass(int x, int y) {
      super(x); // 调用父类的有参构造器
      // 子类的构造器逻辑
   }
}
```
4. 注意：this(...)和super(...)都只能放在构造器的第一行，所以二者不能共存在同一个构造器中。

继承的优点在于它可以提高代码的重用性和可维护性，同时可以使代码更加灵活和可扩展。通过继承，子类可以继承父类的属性和方法，从而减少了代码的编写量。此外，继承也可以使代码更加灵活，能够更好地适应需求的变化。

继承的缺点在于它可能会引入过多的复杂性，使程序难以维护和扩展。如果继承关系设计不当，会导致代码的耦合性过高，增加了代码的复杂度和维护成本。因此，在设计继承关系时，需要仔细考虑继承的层次，避免出现过多的继承关系。

#### 面向对象三大特性之多态

在 Java 中，多态是一种基于继承、多态和重载的特性。它允许同一种类型的对象在不同的场景下表现出不同的行为。

Java 实现多态的方式主要有两种：继承和接口。

1. 继承实现多态

子类可以继承父类的方法，并且可以重写父类的方法，从而实现多态。当子类重写了父类的方法后，当通过父类对象调用该方法时，实际上会调用子类重写后的方法。

示例代码：

```
class Animal {
    public void makeSound() {
        System.out.println("未知的叫声");
    }
}

class Dog extends Animal {
    public void makeSound() {
        System.out.println("汪汪汪");
    }
}

class Cat extends Animal {
    public void makeSound() {
        System.out.println("喵喵喵");
    }
}

public class Test {
    public static void main(String[] args) {
        Animal animal = new Animal();
        Animal dog = new Dog();
        Animal cat = new Cat();

        animal.makeSound();
        dog.makeSound();
        cat.makeSound();
    }
}
```

输出结果：

| 123 | `未知的叫声``汪汪汪``喵喵喵` |
|-|-|

1. 接口实现多态

接口是一种规范，它定义了一组方法，但并不提供方法的具体实现。不同的类可以实现同一个接口，并且每个类都可以根据自己的实际情况来实现接口中的方法，从而实现多态。

示例代码：

```
interface Animal {
    void makeSound();
}

class Dog implements Animal {
    public void makeSound() {
        System.out.println("汪汪汪");
    }
}

class Cat implements Animal {
    public void makeSound() {
        System.out.println("喵喵喵");
    }
}

public class Test {
    public static void main(String[] args) {
        Animal dog = new Dog();
        Animal cat = new Cat();

        dog.makeSound();
        cat.makeSound();
    }
}
```

输出结果：

| 12 | `汪汪汪``喵喵喵` |
|-|-|

无论是通过继承还是接口实现多态，都可以使代码更加灵活、可扩展性更强。

##### 虚方法

虚函数的存在是为了多态，虚方法是实现多态的重要手段，可以使不同的子类对象调用同一个方法时产生不同的行为。虽然Java 中没有虚方法这个概念，但是Java中每个方法都是虚方法，除了被 final 关键字修饰的方法。

在Java中，虚方法的实现依赖于方法表和虚方法表。方法表是每个类的一部分，它包含了该类所有的方法的信息，包括方法名、参数类型、返回值类型等。虚方法表是每个类的一个隐藏的数据结构，它包含了该类所有的虚方法的信息，包括方法的地址、偏移量等。每个对象在内存中都有一个指向其所属类的虚方法表的指针，称为vtable指针。

当调用一个虚方法时，Java虚拟机首先根据对象的实际类型找到其对应的虚方法表，然后根据方法的偏移量找到要调用的方法的地址，并执行该方法。如果子类重写了父类的虚方法，则子类的虚方法表中会覆盖父类相应的方法地址，从而实现了多态。

以下是一个示例代码：

```
class Animal {
    public void eat() {
        System.out.println("Animal is eating");
    }
}

class Cat extends Animal {
    public void eat() {
        System.out.println("Cat is eating");
    }
}

class Dog extends Animal {
    public void eat() {
        System.out.println("Dog is eating");
    }
}

public class Main {
    public static void main(String[] args) {
        Animal a = new Animal();
        Animal b = new Cat();
        Animal c = new Dog();

        a.eat(); // Animal is eating
        b.eat(); // Cat is eating
        c.eat(); // Dog is eating
    }
}
```

在上面的代码中，Animal、Cat和Dog都有一个eat方法，但是它们的行为不同。在main方法中，分别创建了一个Animal、一个Cat和一个Dog对象，并调用它们的eat方法。由于eat方法是虚方法，因此在运行时会根据对象的实际类型来确定要调用哪个方法，从而实现了多态。

#### 方法重写

方法重写指的是在子类中定义一个与父类方法名、返回类型、参数列表都相同的方法，但是方法体不同的过程。

当子类对象调用被重写的方法时，将优先调用子类中的方法，而不是父类中的方法。

方法重写的条件为：

1. 方法名、返回类型、参数列表必须与父类中被重写的方法相同。
2. 访问权限不能低于父类中被重写的方法的访问权限。
3. 子类方法抛出的异常不能大于父类方法抛出的异常。
4. 静态方法不能被重写，但是可以被隐藏。

下面是一个方法重写的例子：

```
public class Animal {
    public void move() {
        System.out.println("动物在移动");
    }
}

public class Dog extends Animal {
    @Override
    public void move() {
        System.out.println("狗在奔跑");
    }
}

public class Test {
    public static void main(String[] args) {
        Animal animal = new Animal();
        animal.move(); // 输出：动物在移动

        Dog dog = new Dog();
        dog.move(); // 输出：狗在奔跑
    }
}
```

在上面的例子中，Animal类中定义了一个move()方法，输出“动物在移动”。在Dog类中重写了这个方法，并输出“狗在奔跑”。当我们调用animal.move()时，输出的是父类Animal中的move()方法的内容；当我们调用dog.move()时，输出的是子类Dog中重写的move()方法的内容。

#### static修饰符

static是静态的意思，可以修饰成员变量和成员方法；static修饰的成员变量和成员方法在内存中只用存储一份，因为可以被类和对象共享访问、修改。

static注意事项：

1、静态方法只能访问静态成员(静态变量或者静态方法)，不能直接访问实例成员，因为静态成员是属于类的，而不是直接属于对象的，静态成员会同类一同创建。

2、实例方法可以访问静态成员，也可以访问实例成员，因为静态成员是可以被共享访问的。

3、静态方法中不可以出现this关键字，因为this只能代表当前对象，而静态方法不一定使用对象调用。

4、静态方法中也不能使用super关键字，因为super关键字代表父类对象，而静态方法没有对象的概念。

5、静态方法也不能被子类重写，因为静态方法是属于类的，而不是属于对象的。

```
package com.java.day1_static;

public class User {
    public static int usernum;

    public static int Val(int num1, int num2) {
        return Math.max(num1, num2);
    }
}
```

#### 静态代码块

```
package com.java.day2_static_code;

public class StaticCode {
    // 静态代码块：如果在启动系统时对静态资源进行初始化，则建议使用静态代码块完成数据的初始化作用
    public static String username;

    static {
        System.out.println("静态代码块对静态资源进行初始化啦！");
        username = "张三";
    }

    public static void main(String[] args) {
        System.out.println("main方法开始执行了！");
    }
}
```

#### 抽象类

抽象类是不能被实例化的类，如果你是新手，那你是不是很疑惑，一个类不能被实例化那还有什么卵用？

别急嘛！抽象类的存在主要是为了被子类继承和实现。抽象类中可以包含抽象方法，抽象方法是一种没有实现的方法，只有方法的声明，没有方法体。

抽象类的特点如下：

1. 抽象类不能被实例化，只能被继承。
2. 抽象类可以包含抽象方法和非抽象方法。
3. 抽象方法必须被子类通过方法重写实现，否则子类也必须声明为抽象类。
4. 抽象类可以拥有构造方法，但抽象类不能被用来创建对象。

下面是一个抽象类的例子：

```
public abstract class Animal {  // abstract表示该类是抽象类
    private String name;

    public Animal(String name) {
        this.name = name;
    }

    public abstract void move();

    public void eat() {
        System.out.println(name + "在吃东西");
    }

    public String getName() {
        return name;
    }

}

public class Dog extends Animal {
    public Dog(String name) {
        super(name);
    }

    @Override
    public void move() {
        System.out.println(super.getName() + "在奔跑");
    }

}

public class Test {
    public static void main(String[] args) {
        Animal animal = new Dog("小狗");
        animal.move();
        animal.eat();
    }
}
```

在上面的例子中，Animal类是一个抽象类，它包含了一个抽象方法move()、一个非抽象方法eat()和一个非抽象方法getName()。在Dog类中继承了Animal类，并实现了move()方法。在Test类中，我们创建了一个Animal类型的对象，实际上是一个Dog对象，然后调用了它的move()、eat()和getName()方法。由于Dog类重写了move()方法，因此输出的是“小狗在奔跑”，而eat()方法是从父类继承而来，输出的是“小狗在吃东西”，getName()方法也是从父类继承而来，用来获取动物的名称。

#### 接口

接口是一种特殊的抽象类，它只包含了抽象方法和常量，没有任何实现。接口中的所有方法都是公共的，不能包含实例域或构造器，因此不能被实例化。

一个类可以实现多个接口，但只能继承一个类。

接口的定义格式如下：

```
public interface 接口名 {
    // 常量定义
    // 方法声明
}
```

接口中的方法默认为public abstract类型，可以省略这两个关键字。接口中的常量必须是public static final类型的(这三个修饰符表示该变量是公共的、静态的、不可改变的，也叫该变量为常量)，可以省略这三个关键字。接口中的方法不能包含方法体，必须由实现类去实现。

下面是一个接口的例子：

```
public interface Animal {
    int LEGS = 4;

    void move();
}

public class Dog implements Animal {
    @Override
    public void move() {
        System.out.println("狗在奔跑");
    }
}

public class Test {
    public static void main(String[] args) {
        Animal animal = new Dog();
        animal.move();
        System.out.println("狗有" + Animal.LEGS + "条腿");
    }
}
```

在上面的例子中，Animal是一个接口，包含了一个常量LEGS和一个抽象方法move()。Dog类实现了Animal接口，并实现了move()方法。在Test类中，我们创建了一个Animal类型的对象，实际上是一个Dog对象，然后调用了它的move()方法。由于Dog类实现了Animal接口，因此可以使用Animal类型来引用Dog对象，从而实现了多态性。输出的结果为“狗在奔跑，狗有4条腿”。

#### 内部类

内部类其实就是在一个类里面再定义一个类，内部类可以访问其外部类的所有成员，包括私有成员。内部类可以分为成员内部类、静态内部类、局部内部类和匿名内部类。

1. 成员内部类

成员内部类就是在一个类的内部定义的另一个类，它可以访问外部类的所有成员，包括私有成员，并且可以使用外部类的引用来访问外部类的成员。成员内部类的定义格式如下：

```
public class Outer {
    private int x = 10;
    public class Inner {
        public void print() {
            System.out.println("x = " + x);
        }
    }
}
```

在上面的例子中，Inner是Outer的成员内部类，它可以访问Outer的私有成员x。在外部类中创建Inner对象的方法如下：

```
Outer outer = new Outer();
Outer.Inner inner = outer.new Inner();
inner.print();
```

 2.静态内部类

静态内部类是在一个类的内部定义的静态类，它和普通的类一样，不依赖于外部类的实例，因此可以直接通过类名来访问。静态内部类不能访问外部类的非静态成员，只能访问外部类的静态成员。静态内部类的定义格式如下：

```
public class Outer {
    private static int x = 10;
    public static class Inner {
        public void print() {
            System.out.println("x = " + x);
        }
    }
}
```

在上面的例子中，Inner是Outer的静态内部类，它可以访问Outer的静态成员x。在外部类中创建Inner对象的方法如下：

| 12 | `Outer.Inner inner =` `new` `Outer.Inner();``inner.print();` |
|-|-|

1. 局部内部类

局部内部类是定义在方法内部的类，它只能在该方法内部使用，对外部不可见。局部内部类可以访问外部类的所有成员，包括私有成员。局部内部类的定义格式如下：

```
public class Outer {
    private int x = 10;
    public void test() {
        class Inner {
            public void print() {
                System.out.println("x = " + x);
            }
        }
        Inner inner = new Inner();
        inner.print();
    }
}
```

在上面的例子中，Inner是Outer方法内部的局部内部类，它可以访问Outer的私有成员x。在方法内部创建Inner对象的方法如下：

```
Outer outer = new Outer();
outer.test();
```

1. 匿名内部类

匿名内部类是没有名字的内部类，它通常用于创建一个只需要使用一次的类。匿名内部类可以继承一个类或者实现一个接口，它没有构造方法，但可以使用构造代码块进行初始化。匿名内部类的定义格式如下：

```
new 父类构造器/接口() {
    // 匿名内部类的内容
}
```

在上面的例子中，父类构造器可以是有参数的构造器，也可以是无参数的构造器；接口可以是有多个方法的接口，也可以是只有一个方法的接口。下面是一个使用匿名内部类实现接口的例子：

```
public interface Animal {
    void move();
}

public class Test {
    public static void main(String[] args) {
        Animal animal = new Animal() {
            @Override
            public void move() {
                System.out.println("动物在移动");
            }
        };
        animal.move();
    }
}
```

在上面的例子中，我们创建了一个实现Animal接口的匿名内部类，并实现了move()方法。在main方法中，我们创建了一个Animal类型的对象，实际上是一个匿名内部类的对象，然后调用了它的move()方法。输出的结果为“动物在移动”。

### 异常

Java中的异常指程序在运行过程中出现的错误或异常情况，例如类型错误、数组下标越界等。Java提供了异常处理机制来处理这些异常情况。

#### 异常的体系：

1. JAVA设计的所有异常类都是有一个祖宗的，这个祖宗类叫Java.lang.Throwable，代表这些异常对象都是可以向外抛出去的。
2. 这个祖宗类有两个子类分支，分别是Error和Exception。
3. Error：代表系统级别的错误，属于严重的错误，比如系统出现问题，甲骨文公司就会把这些问题封装成Error对象给抛出来。所以说这个不是给开发者用的。
4. Exception：这个才是我们熟知的异常，才是代表开发者可能会出现的问题，开发者一般都是使用该类以及其子类来封装程序出现的问题。
5. Exception的子类有两类异常，分别是运行时异常和编译时异常。
6. 运行时异常：RuntimeException类以及其子类，编译时(写代码的时候)不会出现错误提醒，运行时才会抛出异常。
7. 编译时异常：写代码时会出现错误提醒。

#### 自定义异常并简单处理异常：

Java能提供的异常类是有限的，不可能为全世界出现的问题提供异常类来代表出现的问题。如果某个企业出现自己的问题，想要通过异常类来表示，那就需要自己来定义异常类了。接下来我们自己自定义异常类，假设我们需要收集每个用户合理的年龄，如果检测到某个用户输入的年龄不合理就抛出我们自定义的异常。

自定义运行时异常类：

```
package com.java.day5_exception;

// 1、自定义运行时异常类必须让这个类继承RuntimeException，这样才可以成为一个运行时异常类
// 2、需要重写构造器，当我们创建异常对象时可能需要将参数传给有参构造器进行初始化
public class AgeUnreasonableRuntimeException extends RuntimeException{
    public AgeUnreasonableRuntimeException() {
    }

    public AgeUnreasonableRuntimeException(String message) {  // message参数是用来封装我们自定义异常出现的原因
        // 将封装我们自定义异常出现的原因的参数传给父类的有参构造器，最后由父类来封装我们自定义异常出现的原因
        super(message);
    }
}
```

自定义编译时异常类：

```
package com.java.day5_exception;

// 1、自定义编译时异常类必须让这个类继承Exception，这样才可以成为一个编译时异常类
// 2、需要重写构造器，当我们创建异常对象时可能需要将参数传给有参构造器进行初始化
public class AgeUnreasonableException extends Exception{
    public AgeUnreasonableException() {
    }

    public AgeUnreasonableException(String message) {  // message参数是用来封装我们自定义异常出现的原因
        // 将封装我们自定义异常出现的原因的参数传给父类的有参构造器，最后由父类来封装我们自定义异常出现的原因
        super(message);
    }
}
```

创建一个Java类，用于实现收集每个用户合理的年龄，如果检测到某个用户输入的年龄不合理就抛出我们自定义的异常：

```
package com.java.day5_exception;

import java.util.Scanner; //导入 java.util 包下的 Scanner 类。

public class ExceptionOne {
    public static void main(String[] args) {
        // try……catch用于捕获和处理可能出现的异常。
        try {
            System.out.println("请输入合理的年龄：");
            // 创建了一个Scanner对象，并将System.in作为其参数。System.in取得用户输入的内容后,交给Scanner来作一些处理。
            Scanner scan = new Scanner(System.in);
            // nextInt()方法会等待用户输入一个整数，并将其返回。如果用户输入的内容不是一个有效的整数，则会抛出InputMismatchException异常。
            int num = scan.nextInt();
            // 调用detection方法，如果年龄符合我们定义的合理年龄就正常执行，如果不合理detection方法就会向这里抛出AgeUnreasonableRuntimeException异常
            detection(num);
        } catch (RuntimeException e) { // 如果执行try中代码捕获到RuntimeException异常类以及其子类的对象，那就会执行catch中的代码
            // 打印异常信息
            e.printStackTrace();
        }

        try {
            System.out.println("请输入合理的年龄：");
            Scanner scan2 = new Scanner(System.in);
            int num2 = scan2.nextInt();
            // 调用detection2方法，如果年龄符合我们定义的合理年龄就正常执行，如果不合理detection2方法就会向这里抛出AgeUnreasonableException异常
            detection2(num2);
        } catch (Exception e) {  // 如果执行try中代码捕获到Exception异常类以及其子类的对象，那就会执行catch中的代码
            // 打印异常信息
            e.printStackTrace();
        }
    }

    // 编译时异常
    public static void detection2(int age) throws AgeUnreasonableException{
        if (age>0 && age<150) {
            System.out.println(age + "岁年龄是合理的");
        }else {
            // 用一个编译时异常对象封装这个问题。那我们就需要自己创建一个编译时异常类，所以我创建了一个编译时异常类AgeUnreasonableRuntimeException
            // throw：用于抛出这个异常对象，它会将异常对象先抛到方法的入口这里，再抛给方法的调用者。
            // 所以我们自定义异常会将编译时异常对象先抛到detection方法入口处，再抛给detection方法的调用者。
            // 我们将需要自定义编译时异常类抛出的异常信息作为参数传给了我们自定义的编译时异常类的有参构造器并创建一个编译时异常对象，并将创建的编译时异常对象抛出去。
            // 编译时异常写代码的时候就会强烈提醒你，所以我们自定义编译时异常类被实例化的时候报错是正常的。想要解决这个报错需要用到throws
            // throws：用在方法上，它会将方法内部的异常抛给调用该方法的上层。如果用在main方法上，那就会将main方法内部的异常抛给JVM虚拟机。
            throw new AgeUnreasonableException("The age you entered is" + age +  "years old is not reasonable");
        }
    }

    // 运行时异常
    public static void detection(int age) {
        if (age>0 && age<150) {
            System.out.println(age + "岁年龄是合理的");
        }else {
            // 用一个运行时异常对象封装这个问题。那我们就需要自己创建一个运行时异常类，所以我创建了一个运行时异常类AgeUnreasonableRuntimeException
            // throw：用于抛出这个异常对象，它会将异常对象先抛到方法的入口这里，再抛给方法的调用者。
            // 所以我们自定义异常会将运行时异常对象先抛到detection方法入口处，再抛给detection方法的调用者。
            // 我们将需要自定义运行时异常类抛出的异常信息作为参数传给了我们自定义的运行时异常类的有参构造器并创建一个运行时异常对象，并将创建的运行时异常对象抛出去。
            throw new AgeUnreasonableRuntimeException("The age you entered is" + age +  "years old is not reasonable");
        }
    }
}
```

当输入的年龄合理时：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_JBVF2S6VPTH87BR.png)

当输入的年龄不合理时：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_GH3CP47DV3Z98XS.png)

#### 开发中处理异常的几种方式：

虽说当将异常对象抛给main方法或者main方法出现异常都可以将异常对象抛给JVM虚拟机，然后JVM虚拟机会进行处理后将异常信息抛给用户，这对于用户来说是极其影响体验的，所以接下来讲讲开发中一般会怎么处理异常。一般情况下处理异常会用以下几种方式：

第一种、捕获异常，然后将合适的信息响应给用户。

第二种、捕获异常，然后尝试修复异常。

在前面我们简单处理异常的时候，如果用户输入非int型的数据，那肯定是会抛出异常的。所以我们还是围绕收集每个用户合理的年龄这个主题，使用这两种异常处理的方式将之前的代码完善。

捕获异常，然后将合适的信息响应给用户：

```
package com.java.day5_exception;

import java.util.Scanner;

public class ExceptionTwo {
    public static void main(String[] args) {
        try {
            runs();
        } catch (Exception e) { // 如果调用runs方法因为输入非int型的数据触发了Exception异常就打印对应的中文异常信息
            System.out.println("您需要输入整数型数据，而非其他类型数据！");
        }
    }

    public static void runs() throws Exception{
        System.out.println("请输入合理的年龄：");
        Scanner scan = new Scanner(System.in);
        int num = scan.nextInt();
        try {
            detection(num);
            detection2(num);
        } catch (AgeUnreasonableRuntimeException e) { // 如果出现我们自定义的运行时异常就打印对应的中文异常信息提醒用户
            System.out.println("您输入的年龄不合理！触发了运行时异常。");
        } catch (AgeUnreasonableException e) { // 如果出现我们自定义的编译时异常就打印对应的中文异常信息提醒用户
            System.out.println("您输入的年龄不合理！触发了编译时异常。");
        }
    }

    // 编译时异常
    public static void detection2(int age) throws AgeUnreasonableException{
        if (age>0 && age<150) {
            System.out.println(age + "岁年龄是合理的");
        }else {
            throw new AgeUnreasonableException("The age you entered is" + age +  "years old is not reasonable");
        }
    }

    // 运行时异常
    public static void detection(int age) {
        if (age>0 && age<150) {
            System.out.println(age + "岁年龄是合理的");
        }else {
            throw new AgeUnreasonableRuntimeException("The age you entered is" + age +  "years old is not reasonable");
        }
    }
}
```

我们进行输入测试结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_9SR2MKFG264949S.png)

捕获异常，然后尝试修复异常：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `package` `com.java.day5_exception;` `import` `java.util.Scanner;` `public` `class` `ExceptionThree {``public` `static` `void` `main(String[] args) {``// 捕获到下层抛来的异常对象就告诉用户需要重新输入，并重新执行runs方法，直到用户输入的int型数据合理就会break``while` `(``true``) {``try` `{``runs();``break``;``}` `catch` `(Exception e) {``System.out.println(``"您需要输入整数型数据，而非其他类型数据，需要您重新输入！"``);``}``}``}` `// 如果捕获到AgeUnreasonableRuntimeException、AgeUnreasonableException异常对象就让用户重新输入。``// 想要终止输入，就需要用户输入的int型数据合理就会break``// 如果捕获到Exception异常对象而非我们自定义的异常对象，就将Exception异常对象抛给上层调用者。``public` `static` `void` `runs()` `throws` `Exception{``while` `(``true``) {``System.out.println(``"请输入合理的年龄："``);``Scanner scan =` `new` `Scanner(System.in);``int` `num = scan.nextInt();``try` `{``detection(num);``detection2(num);``break``;``}` `catch` `(AgeUnreasonableRuntimeException e) {``System.out.println(``"您输入的年龄不合理！触发了运行时异常。"``);``}` `catch` `(AgeUnreasonableException e) {``System.out.println(``"您输入的年龄不合理！触发了编译时异常。"``);``}``}``}` `// 编译时异常``public` `static` `void` `detection2(``int` `age)` `throws` `AgeUnreasonableException{``if` `(age>``0` `&& age<``150``) {``System.out.println(age +` `"岁年龄是合理的"``);``}``else` `{``throw` `new` `AgeUnreasonableException(``"The age you entered is"` `+ age +` `"years old is not reasonable"``);``}``}` `// 运行时异常``public` `static` `void` `detection(``int` `age) {``if` `(age>``0` `&& age<``150``) {``System.out.println(age +` `"岁年龄是合理的"``);``}``else` `{``throw` `new` `AgeUnreasonableRuntimeException(``"The age you entered is"` `+ age +` `"years old is not reasonable"``);``}``}``}` |
|-|-|

我们进行输入测试结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_CUY35GVJJ57HMDG.png)

### 反射

问：Java中的反射是什么呢？

答：在Java中，反射是指在程序运行时能够动态地获取类的信息并操作类的成员（属性、方法、构造方法等）的机制。

问：那Java中的反射需要学习些什么呢？

答：

反射学习第一步：将类的字节码文件加载到内存中，然后获取类的class对象。因为Java提供了一个class对象来代表字节码，所以获取类的字节码其实就是获取类的class对象，class对象会封装类的各种信息。

反射学习第二步：获取类的构造器，而构造器也是一个对象，去获取类中的构造器，那就会返回一个constructor对象，该对象就会封装构造器的各种信息。

反射学习第三步：获取类的成员变量和成员方法等，而成员变量和成员方法等都是一种对象。比如去获取类中的成员变量，会返回一个Field对象，就可以获取该对象的各种信息或者操作该对象；去获取类中的成员方法，会返回一个Method对象，就可以获取该对象的各种信息或者操作该对象。

总结起来反射就是学习动态地获取类的信息并学习如何操作它们。接下来我们一步一步讲。

反射学习第一步：将类的字节码文件加载到内存中，然后获取类的class对象：

获取class对象的几种方式：

```
package com.java.day6_reflect;

import com.java.day5_exception.ExceptionThree;

public class ReflectClass {
    public static void main(String[] args) throws Exception{
        // 第一种方式：Class<这里需要获取的Class对象的类名，不知道就可以填?> 变量名 = 类名.class;
        Class<ExceptionThree> a = ExceptionThree.class;
        System.out.println(a.getName());  // 获取class对象的完整类名

        // 第二种方式：调用Class提供的方法获取类的class对象。
        // 格式：Class<?> 变量名 = Class.forName(类的完整路径);
        Class<?> b = Class.forName("com.java.day5_exception.ExceptionThree");
        System.out.println(b.getSimpleName());  // 获取class对象的类名

        // 第三种方式：通过类的对象调用Object提供的getClass方法获取类的class对象。
        ExceptionThree c = new ExceptionThree();
        Class<?> d = c.getClass();  // 格式：Class<?> 变量名 = Object.getClass();

        // 这三种方式获取的ExceptionThree类的class对象是同一份class对象，只是获取方式不一样。
        // 因为ExceptionThree类的class对象在内存中肯定只有一份
        if (a == b) {
            System.out.println("这三种方式获取类的class对象是同一份class对象");
        }else {
            System.out.println("这三种方式获取类的class对象不是同一份class对象");
        }
    }
}
```

接下来通过运行结果来验证结果是否正确：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_7E7BXKUPSCW6MBP.png)

反射学习第二步：获取类的构造器：

Class对象既然代表类，那么Class肯定会提供相应的方法去获取类的各种信息。所以获取类的构造器有以下几种方法：

首先我们需要写一个简单的类来学习：

```
package com.java.day6_reflect;

public class Zoon {
    public String name;
    public int age;

    public Zoon(String name, int age) {
        this.name = name;
        this.age = age;
    }

    private Zoon(){
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public int getAge() {
        return age;
    }

    public void setAge(int age) {
        this.age = age;
    }
}
```

第一种方式：获取全部构造器(只能获取public修饰的)：

| 1 | `Class<?> a` `=` `Zoon.``class``;` `/``/` `想要完成反射第二步、第三步，那都需要得到类的Class对象` |
|-|-|

得到类的Class对象后，可以通过Class对象调用类的getConstructors方法得到类的全部构造器。但是这个方法会把类的每一个构造器都封装成构造器对象，然后把所有构造器对象放到一个构造器数组里面去。所以要使用以下方式获取类的全部构造器：

| 1 | `Constructor[] b` `=` `a.getConstructors();` |
|-|-|

我们获取类的全部构造器后，可以进行验证：遍历构造器数组中的每一个构造器对象，并打印构造器名称和参数个数。

| 123 | `for` `(Constructor constructor : b) {``System.out.println(``"这是第一种方式获得的构造器对象："``+``constructor.getName()``+``"，这个构造器有"``+``constructor.getParameterCount()``+``"个参数！"``);``}` |
|-|-|

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_NDNMXRGT6QZBTRP.png)

可以看到只打印出了一个有参数构造器，而无参数构造器并没有打印出来，因为getConstructors方法虽然可以得到类的全部构造器，但是只能获取public修饰的。

第二种方式：获取全部构造器(只要存在就能拿到)：

| 1 | `Class<?> a` `=` `Zoon.``class``;` `/``/` `想要完成反射第二步、第三步，那都需要得到类的Class对象` |
|-|-|

得到类的Class对象后，想要通过Class对象得到类的全部构造器且只要存在就能拿到，那就需要使用getDeclaredConstructors方法。但是这个方法也会把类的每一个构造器都封装成构造器对象，然后把所有构造器对象放到一个构造器数组里面去。所以要使用以下方式获取类的全部构造器：

| 1 | `Constructor[] c` `=` `a.getDeclaredConstructors();` |
|-|-|

验证：遍历构造器数组中的每一个构造器对象，并打印构造器名称和参数个数。

| 123 | `for` `(Constructor constructor : c) {``System.out.println(``"这是第二种方式获得的构造器对象："``+``constructor.getName()``+``"，这个构造器有"``+``constructor.getParameterCount()``+``"个参数！"``);``}` |
|-|-|

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_XH8GHAN3JZ6GGU6.png)

这次可以看到将所有的构造器全部都拿到了，没有了只能获取public修饰的构造器这种限制。

剩下的两种方式与前两种方式类似，我就简单讲讲。

第三种方式：获取某一个构造器(只能获取public修饰的)：

```
Class<?> a = Zoon.class;  // 不管怎样，想要获取Class对象中的各种信息，第一步永远是获取类的Class对象
```

得到类的Class对象后，想要通过Class对象得到类的某一个构造器，可以通过getConstructor方法获取到，但是问题也是只能获取public修饰的。那怎么精准获取到想要的类的构造器呢？那就需要通过参数的差别：

获取某一个构造器的格式：Constructor 变量 = 类的class.getConstructor(Class<?>... parameterTypes);

获取有参数构造器：

```
// 获取有参构造器需要往getConstructor方法中填写对应有参构造器的参数类型来匹配有参构造器
Constructor e = a.getConstructor(String.class, int.class);
System.out.println("这是第三种方式获得的有参构造器对象："+e.getName()+"，这个构造器有"+e.getParameterCount()+"个参数！");
```

获取无参数构造器：

```
Constructor d = a.getConstructor();
System.out.println("这是第三种方式获得的无参构造器对象："+d.getName());
```

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_6U2TPY8TXK74M6H.png)

可以看到打印出来了有参数构造器对象的名称和参数个数，但是获取无参数构造器却报错了，因为这个方式能获取public修饰的，而无参构造器却是private修饰的，所以获取不到报错了！

第四种方式：获取某一个构造器(只要存在就能拿到)：

```
Class<?> a = Zoon.class;
```

得到类的Class对象后，使用getConstructor方法去获取类的某一个构造器最大的问题就是只能获取public修饰的，而使用getDeclaredConstructor方法去获取类的某一个构造器就没有这个问题，因为getDeclaredConstructor方法也是只要存在就能拿到。

获取某一个构造器的格式：Constructor 变量 = 类的class.getDeclaredConstructor(Class<?>... parameterTypes);

获取有参数构造器：

```
// 获取有参构造器需要往getDeclaredConstructor方法中填写对应有参构造器的参数类型来匹配有参构造器
Constructor e = a.getDeclaredConstructor(String.class, int.class);
System.out.println("这是第四种方式获得的有参构造器对象："+e.getName()+"，这个构造器有"+e.getParameterCount()+"个参数！");
```

获取无参数构造器：

```
Constructor d = a.getDeclaredConstructor();
System.out.println("这是第四种方式获得的无参构造器对象："+d.getName());
```

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_BWH93VSS6AWV78Q.png)

这次可以看到不管是public修饰的构造器还是private修饰的构造器都打印出来了，没有了只能获取public修饰的构造器这种限制。

这四种获取类的构造器的方式全部讲完了，以下是完整代码：

```
package com.java.day6_reflect;

import org.junit.Test;

import java.lang.reflect.Constructor;

public class ReflectConstructors {
    // @Test注释是JUnit框架中用于标记测试方法的注释。通过使用@Test注释，JUnit可以识别并执行被标记的方法作为测试用例。
    // 在使用@Test注释之前，需要引入JUnit框架。可以通过在项目中添加JUnit依赖来实现。
    // 被@Test修饰的方法必须是公共的、方法必须不能带有参数、方法必须没有返回值。
    // 被@Test注释标记的方法不能抛出任何异常。如果测试方法需要测试某个异常情况，可以使用@Test注释的expected参数来指定期望的异常类型。
    @Test
    public void test() {
        // 第一种方式：获取全部构造器(只能获取public修饰的)
        Class<?> a = Zoon.class;  // 想要完成反射第二步、第三步，那都需要得到类的Class对象
        // 调用类的getConstructors方法，可以得到类的全部构造器。但是这个方法会把类的每一个构造器都封装成构造器对象，然后把所有构造器对象放到一个构造器数组里面去。
        Constructor[] b = a.getConstructors();
        // 验证：遍历构造器数组中的每一个构造器对象，并打印构造器名称和参数个数
        for (Constructor constructor : b) {
            System.out.println("这是第一种方式获得的构造器对象："+constructor.getName()+"，这个构造器有"+constructor.getParameterCount()+"个参数！");
        }
    }

    @Test
    public void test1() {
        // 第二种方式：获取全部构造器(只要存在就能拿到)
        Class<?> a = Zoon.class;
        Constructor[] c = a.getDeclaredConstructors();
        // 验证：遍历构造器数组中的每一个构造器对象，并打印构造器名称和参数个数
        for (Constructor constructor : c) {
            System.out.println("这是第二种方式获得的构造器对象："+constructor.getName()+"，这个构造器有"+constructor.getParameterCount()+"个参数！");
        }
    }

    @Test
    public void test2() throws Exception{
        // 第三种方式：获取某一个构造器(只能获取public修饰的)
        Class<?> a = Zoon.class;
        // 格式：Constructor 变量 = 类的class.getConstructor(Class<?>... parameterTypes);
        // 获取有参构造器
        // 获取有参构造器需要往getConstructor方法中填写对应有参构造器的参数类型来匹配有参构造器
        Constructor e = a.getConstructor(String.class, int.class);
        System.out.println("这是第三种方式获得的有参构造器对象："+e.getName()+"，这个构造器有"+e.getParameterCount()+"个参数！");

        Constructor d = a.getConstructor(); // 获取无参构造器
        System.out.println("这是第三种方式获得的无参构造器对象："+d.getName());
    }

    @Test
    public void test3() throws Exception{
        // 第四种方式：获取某一个构造器(只要存在就能拿到)
        Class<?> a = Zoon.class;
        // 格式：Constructor 变量 = 类的class.getDeclaredConstructor(Class<?>... parameterTypes);
        Constructor d = a.getDeclaredConstructor(); // 获取无参构造器
        System.out.println("这是第四种方式获得的无参构造器对象："+d.getName());

        // 获取有参构造器
        // 获取有参构造器需要往getDeclaredConstructor方法中填写对应有参构造器的参数类型来匹配有参构造器
        Constructor e = a.getDeclaredConstructor(String.class, int.class);
        System.out.println("这是第四种方式获得的有参构造器对象："+e.getName()+"，这个构造器有"+e.getParameterCount()+"个参数！");
    }
}
```

我们获取到了构造器自然要使用，而反射获取构造器的作用主要是初始化对象并返回。要怎么使用呢？我简单的讲解一下，我先把Zoon类的有参数构造器从public修饰变为private修饰，然后如下使用反射获取的构造器：

```
@Test
public void test4() throws Exception{
    Class<?> a = Zoon.class;
    Constructor f = a.getDeclaredConstructor(String.class, int.class);
    f.setAccessible(true);  // 将构造器对象方法setAccessible的flag参数设置为true，表示禁止检查访问控制(暴力反射)。简而言之：就算是修饰为私有的，我也能在外面访问。
    // 通过newInstance构造器对象方法调用此构造器对象表示的构造器，并传入参数，完成对象的初始化并返回
    Zoon f2 = (Zoon) f.newInstance("长颈鹿", 3);  // 因为我们在获取类的构造器的时候，接收构造器对象的变量在接收时并不知道这个构造器是哪个类的构造器，导致构造器对象返回的类型还是Object类型，所以需要在这里强转类型。
}
```

现在反射第二步也算是完成了。

反射学习第三步：获取类的成员变量和成员方法：

获取类的成员变量和成员方法与获取类的构造器类似，我就简单讲讲。

我先把Zoon类的成员变量age和成员方法setName从public修饰的变为了private修饰的。

获取并使用类的成员变量：

```
package com.java.day6_reflect;

import org.junit.Test;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;

public class ReflectField {
    @Test
    public void fields1() throws Exception{
        // 第一种方式：获取类的全部成员变量(只能获取public修饰的)
        Class<?> a = Zoon.class;
        // 调用类的getFields方法，可以得到类的全部成员变量。但是这个方法会把类的每一个成员变量都封装成成员变量对象，然后把所有成员变量对象放到一个成员变量数组中去，只是只能获取public修饰的成员变量。
        Field[] b = a.getFields();
        // 验证：遍历成员变量数组中的每一个成员变量对象，并打印成员变量名称和成员变量类型
        for (Field field : b) {
            System.out.println("这是第一种方式获得的成员变量对象" + "成员变量名称：" + field.getName() + "，" + "成员变量类型：" + field.getType());
        }
    }

    @Test
    public void fields2() throws Exception{
        // 第二种方式：获取类的全部成员变量(只要存在就能拿到)
        Class<?> a = Zoon.class;
        // 调用类的getDeclaredFields方法，可以得到类的全部成员变量。这个方法也会把类的每一个成员变量都封装成成员变量对象，然后把所有成员变量对象放到一个成员变量数组中去，但是只要存在就能拿到。
        Field[] b = a.getDeclaredFields();
        // 验证：遍历成员变量数组中的每一个成员变量对象，并打印成员变量名称和成员变量类型
        for (Field field : b) {
            System.out.println("这是第二种方式获得的成员变量对象" + "成员变量名称：" + field.getName() + "，" + "成员变量类型：" + field.getType());
        }
    }

    @Test
    public void fields3() throws Exception{
        // 第三种方式：获取类的某个成员变量(只能获取public修饰的)
        Class<?> a = Zoon.class;
        // 调用类的getField方法，可以得到类的某个成员变量。这个方法想要获取到某个成员变量，就需要告诉它要获取的成员变量的名字，只是只能获取public修饰的成员变量。
        Field b = a.getField("name");
        // 验证：打印获取到的某个成员变量的成员变量名称和成员变量类型
        System.out.println("这是第三种方式获得的成员变量对象" + "成员变量名称：" + b.getName() + "，" + "成员变量类型：" + b.getType());
    }

    @Test
    public void fields4() throws Exception {
        // 第四种方式：获取类的某个成员变量(只要存在就能拿到)
        Class<?> a = Zoon.class;
        // 调用类的getDeclaredField方法，可以得到类的某个成员变量。这个方法想要获取到某个成员变量，就需要告诉它要获取的成员变量的名字，但是只要存在就能拿到。
        Field b = a.getDeclaredField("name");
        Field c = a.getDeclaredField("age");
        // 验证：打印获取到的某个成员变量的成员变量名称和成员变量类型
        System.out.println("这是第四种方式获得的成员变量对象" + "成员变量名称：" + b.getName() + "，" + "成员变量类型：" + b.getType());
        System.out.println("这是第四种方式获得的成员变量对象" + "成员变量名称：" + c.getName() + "，" + "成员变量类型：" + c.getType());
    }

    @Test
    public void fields5() throws Exception{
        // 使用类的成员变量
        Class<?> a = Zoon.class;
        Field[] b = a.getDeclaredFields();
        Zoon c = new Zoon();
        for (Field field : b) {
            // 在使用Field类来设置值或获取值时，都需要先获取到该成员变量的对象，然后通过Field对象来进行操作。
            // 而且不管是设置值、还是获取值，都需要告诉Field对象需要对哪个对象的这个成员变量进行操作。
            if (field.getName().equals("age")) {
                field.setAccessible(true); // 禁止检查访问控制(暴力反射)
                field.set(c, 5);  // Field类.set(需要设置值的成员变量所属对象, 想要设置的值)
            }else {
                field.set(c, "老虎");
            }
            System.out.println(field.get(c));
        }
    }
}
```

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_H3J8Q5JU3G3GBW8.png)

获取类的成员方法并执行：

```
package com.java.day6_reflect;

import org.junit.Test;

import java.lang.reflect.Method;

public class ReflectMethod {
    @Test
    public void methods1() throws Exception{
        // 第一种方式：获取类的全部成员方法(只能获取public修饰的)
        Class<?> a = Zoon.class;
        // 调用类的getMethods方法，可以得到类的全部成员方法。但是这个方法会把类的每一个成员方法都封装成成员方法对象，然后把所有成员方法对象放到一个成员方法数组中去，只是只能获取public修饰的成员方法。
        Method[] b = a.getMethods();
        // 验证：遍历成员方法数组中的每一个成员方法对象，并打印成员方法名称和成员方法参数个数以及成员方法返回值类型
        for (Method method : b) {
            System.out.println("这是第一种方式获得的成员方法对象" + "成员方法名称：" + method.getName() + "，"
                    + "成员方法参数个数：" + method.getParameterCount() + "，"
                    + "成员方法返回值类型：" + method.getReturnType());
        }
    }

    @Test
    public void methods2() throws Exception{
        // 第二种方式：获取类的全部成员方法(只要存在就能拿到)
        Class<?> a = Zoon.class;
        // 调用类的getDeclaredMethods方法，可以得到类的全部成员方法。这个方法也会把类的每一个成员方法都封装成成员方法对象，然后把所有成员方法对象放到一个成员方法数组中去，但是只要存在就能拿到。
        Method[] b = a.getDeclaredMethods();
        // 验证：遍历成员方法数组中的每一个成员方法对象，并打印成员方法名称和成员方法参数个数以及成员方法返回值类型
        for (Method method : b) {
            System.out.println("这是第二种方式获得的成员方法对象" + "成员方法名称：" + method.getName() + "，"
                    + "成员方法参数个数：" + method.getParameterCount() + "，"
                    + "成员方法返回值类型：" + method.getReturnType());
        }
    }

    @Test
    public void methods3() throws Exception{
        // 第三种方式：获取类的某个成员方法(只能获取public修饰的)
        Class<?> a = Zoon.class;
        // 调用类的getMethod方法，可以得到类的某个成员方法。getMethod方法想要获取到某个成员方法，就需要告诉它要获取的成员方法的名字以及参数类型，只是只能获取public修饰的成员方法。
        Method b = a.getMethod("getName");
        // 验证：打印获取到的某个成员方法的成员方法名称和成员方法参数个数以及成员方法返回值类型
        System.out.println("这是第三种方式获得的成员方法对象" + "成员方法名称：" + b.getName() + "，"
                + "成员方法参数个数：" + b.getParameterCount() + "，"
                + "成员方法返回值类型：" + b.getReturnType());
    }

    @Test
    public void methods4() throws Exception {
        // 第四种方式：获取类的某个成员方法(只要存在就能拿到)
        Class<?> a = Zoon.class;
        // 调用类的getDeclaredMethod方法，可以得到类的某个成员方法。getDeclaredMethod方法想要获取到某个成员方法，就需要告诉它要获取的成员方法的名字以及参数类型，但是只要存在就能拿到。
        Method b = a.getDeclaredMethod("setName", String.class);
        // 验证：打印获取到的某个成员方法的成员方法名称和成员方法参数个数以及成员方法返回值类型
        System.out.println("这是第四种方式获得的成员方法对象" + "成员方法名称：" + b.getName() + "，"
                + "成员方法参数个数：" + b.getParameterCount() + "，"
                + "成员方法返回值类型：" + b.getReturnType());
    }

    @Test
    public void methods5() throws Exception{
        // 触发类的成员方法执行
        Class<?> a = Zoon.class;
        // 在使用Method类来触发类的成员方法执行时，需要先获取到该成员方法的对象，然后通过Method对象来进行操作。
        // 而且想要触发某个类的成员方法执行都需要告诉Method对象需要对哪个对象的这个成员方法进行操作。
        Method b = a.getDeclaredMethod("getName");
        Method c = a.getDeclaredMethod("setName", String.class);
        Zoon d = new Zoon();
        c.setAccessible(true); // 禁止检查访问控制(暴力反射)
        c.invoke(d, "熊猫");  // Method类.invoke(需要执行的成员方法所属对象, 执行成员方法所需参数)
        System.out.println(b);
    }
}
```

打印结果：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_GFWJJF8ZY9A42PU.png)

到这我们就将反射全部讲解完毕，我们已经充分认识了什么是反射，以及反射的核心作用是用来获取类的各个组成部分并执行他们。

## 二、smali基础语法

#### dalvik字节码

1、先来了解一下dalvik虚拟机：

dalvik虚拟机是Android 5.0以前用于运行安卓应用的虚拟机，从 Android 4.4 开始，Google 开始引入了全新的虚拟机 ART（Android Runtime），直到Android5.0开始ART虚拟机就替代了dalvik虚拟机。既然dalvik虚拟机被ART虚拟机替代了，那我们还有学的必要吗？ART 是向下兼容的，ART虚拟机对DEX字节码的运行是兼容的，因此针对 Dalvik 开发的应用也能在 ART 环境中运作。但是Dalvik 采用的一些技术并不适用于 ART，但不妨碍我们了解和学习dalvik字节码。

2、我们再来了解一下dalvik寄存器和寄存器的命名方法：

Dalvik寄存器中的寄存器都是32位大小，支持所有类型，对于小于或等于32位的类型，使用一个寄存器就可以了；对于64位(long和double)类型，需要使用两个相邻的寄存器来存储。

寄存器的命名方法有两种：v命名法和p命名法：

 v命名法：局部变量寄存器用v开头数字结尾的符号来表示，如v0、 v1、v2。

 p命名法：函数参数寄存器则使用p开头数字结尾的符号来表示，如p0、p1、p2。

特别注意的是，p0不一定是函数中的第一个参数，在非static函数中，p0代指“this"，p1表示函数的第一个 参数，p2代表函数中的第二个参数。而在static函数中p0才对应第一个参数(因为Java的static方法中没有this方法）

寄存器赋值：

| 123 | `const``/``4` `p5,` `0x1` `/``/``p5赋值``1` `const``/``16` `v0,` `0xa` `/``/``v0赋值``10``，在``16``进制里a表示``10` |
|-|-|

const/4和const/16是表示定义一个4位和16位值，这里只是修饰一下，记住Dalvik寄存器是32位寄存器，这只是表示32位寄存器中存的值是4位和16位而已，不要被这个给影响了。

3、再来了解一下dalvik字节码的类型与Java数据类型的对应关系：

数据类型对应：

| smali类型 | java类型 | 注释 |
|-|-|-|
| V | void | 无返回值 |
| Z | boolean | 布尔值类型，返回0或1 |
| B | byte | 字节类型，返回字节 |
| S | short | 短整数类型，返回数字 |
| C | char | 字符类型，返回字符 |
| I | int | 整数类型，返回数字 |
| J | long （64位 需要2个寄存器存储） | 长整数类型，返回数字 |
| F | float | 单浮点类型，返回数字 |
| D | double （64位 需要2个寄存器存储） | 双浮点类型，返回数字 |
| string | String | 文本类型，返回字符串 |
| Lxxx/xxx/xxx | object | 对象类型，返回对象 |

long类型和double类型都是64位，需要两个寄存器来存储，有时在smali代码中，原本从0到n的寄存器在中间少了一个，那就有可能是其中有数据是long类型或者double类型的，在赋值代码中虽然用到了两个寄存器，但隐藏了其中一个。

4、了解smali和Java之间的转换流程：

xxx.java ==> xxx.class ==> 使用dx工具将.class打包成.dex文件 ==> 使用baksmali工具将.dex文件反编译成.smali文件 ==> 反编译成smali文件后对该文件进行修改成功 ==> 使用samli工具将.smali文件打包成.dex文件(回编译)

5、了解dalvik方法：

```
//一个私有、静态、不可变的方法   方法名
.method private static final onCreate$lambda-2([Ljava/lang/String;)Z//(这里面是方法的参数)这里是方法返回值类型，表示布尔值类型，返回假或真
```

.method表示定义了一个方法；

private、static、final表示该方法是一个一个私有、静态、不可变的方法；

onCreate$lambda-2是该方法定义的方法名，方法名后面括号中是该方法的参数；

[Ljava/lang/String;该参数表示接收字符串类型的一维数组，其中[表示一维数组，在smali的方法参数中每一个[就表示一维数组，比如[[就表示二维数组；java中类是一种数据类型，类用L表示，L后面接的是完整类名，也就是包名和类名。

6、了解dalvik字段：

dalvik创建字段需要指定字段的访问标志(修饰符)、字段名、字段类型和初始值等信息。下面是一个示例字段的创建代码：

.field private static count:I = 0

上述代码创建了一个名为count的私有静态字段，类型为整型，初始值为0。

#### dalvik指令集

1、dalvik指令集格式：

基础字节码-名称后缀/字节码后缀 目的寄存器 源寄存器/常量

- Dalvik指令集中参数采用从源寄存器到目标寄存器的方式。
- 根据dalvik字节码的大小与类型不同，可能会添加名称后缀以消除岐义。具体来说，字节码的类型可以分为常规类型和特殊类型，根据类型的不同添加的后缀也不同，常规类型的字节码不添加任何后缀，而特殊类型的字节码根据具体类型添加后缀，可能是以下几种后缀之一：

	- -boolean：布尔类型
	- -byte：字节类型
	- -char：字符类型
	- -short：短整型
	- -int：整型
	- -long：长整型
	- -float：浮点型
	- -double：双精度浮点型
	- -object：对象类型
	- -string：字符串类型
	- -class：类类型
	- -void：无返回值类型
- 常规类型的字节码主要有以下几种：

	- move：将一个寄存器的值复制到另一个寄存器中
	- add：将两个寄存器的值相加，并将结果存储到目标寄存器中
	- sub：将两个寄存器的值相减，并将结果存储到目标寄存器中
	- mul：将两个寄存器的值相乘，并将结果存储到目标寄存器中
	- div：将两个寄存器的值相除，并将结果存储到目标寄存器中
	- rem：将两个寄存器的值取余，并将结果存储到目标寄存器中
	- neg：将一个寄存器的值取反，并将结果存储到目标寄存器中
	- and：将两个寄存器的值进行按位与操作，并将结果存储到目标寄存器中
	- or：将两个寄存器的值进行按位或操作，并将结果存储到目标寄存器中
	- xor：将两个寄存器的值进行按位异或操作，并将结果存储到目标寄存器中
	- shl：将一个寄存器的值左移指定位数，并将结果存储到目标寄存器中
	- shr：将一个寄存器的值右移指定位数，并将结果存储到目标寄存器中
	- ushr：将一个寄存器的值无符号右移指定位数，并将结果存储到目标寄存器中
	- not：将一个寄存器的值进行按位取反操作，并将结果存储到目标寄存器中
	- cmp：比较两个寄存器的值，并将结果存储到目标寄存器中
- 此外，根据字节码的大小与布局的不同，也可能添加字节码后缀以消除岐义。这些后缀通过在字节码主名称后添加斜杠“/”来分隔开。例如，一些指令可能会添加以下后缀：

	- -wide：64位宽度
	- -from16：源为16位寄存器引用
	- -to16：目标为16位寄存器引用
	- -range：指示该指令的操作数是一个范围。
- 32位常规类型的字节码没有添加任何后缀。
- 64位常规类型的字节码添加 -wide后缀。
- 例如这条指令：“move-wide/from16 vAA, vBBBB”：

	- 这条指令是移动命令，用于将源寄存器中存储的数据移动到目标寄存器中。
	- 其中“wide”表示数据宽度为64位，“from16”表示源寄存器为一个16位寄存器引用，vAA表示目标寄存器，它的取值范围是v0v65535。
	- Dalvik指令集中的大多数指令都需要使用寄存器作为源操作数或目的操作数。其中，A/B/C/D/E/F/G/H表示一个4位数值，可以表示0v15的寄存器。AA/BB/CC/DD/EE/FF/GG/HH表示一个8位数值，可以表示0v255的寄存器。AAAA/BBBB/CCCC/DDDD/EEEE/FFFF/GGGG/HHHH表示一个16位数值，可以表示0v65535的寄存器。

2、dalvik指令集的使用：

- 空操作指令

	- 空操作指令的助记符为nop。它的值为00，通常nop指令被用来作对齐代码之用，无实际操作，就和空格差不多。
- 数据操作指令

	- move指令的三种作用：

		- 第一种作用：进行赋值操作
		- 第二种作用：move-result接收方法返回值操作
		- 第三种作用：处理异常的操作
	- move指令集的使用：

		- move vx, vy 指令将寄存器vy中的值移动到寄存器vx中。例如，move v1, v2表示将寄存器v2中的值移动到寄存器v1中，源寄存器与目的寄存器都为4位。
		- move/from16 vx, vy 指令将16位寄存器vy中的值移动到寄存器vx中。例如，move/from16 v1, v2表示将16位寄存器v2中的值移动到寄存器v1中，源寄存器为16位，目的寄存器为8位(范围必须在256以内)。注意，寄存器中存储的是值的引用，也可以理解为存储的是值的地址。
		- move-wide/from16 vx, vy 指令用于移动long/double类型的数据，将其从16位寄存器vy移动到范围必须在256内(8位)的寄存器vx中。例如，move-wide/from16 v1, v2表示将16位寄存器v2中的long/double类型的值移动到8位寄存器v1中。注意，寄存器中存储的是值的引用，也可以理解为存储的是值的地址。
		- move/16 vx, vy 指令将寄存器vy的值移动到寄存器vx中。例如，move/16 v1,v2表示将16位寄存器v2中的值移动到16位寄存器v1中，源寄存器与目的寄存器都为16位。
		- move-object vx, vy 指令将一个对象引用从寄存器vy移动到寄存器vx中。例如，move-object v1, v2表示将对象引用从寄存器v2移动到寄存器v1中。
		- move-object/from16 vx, vy 指令将对象引用从16位寄存器vy移动到寄存器vx中。例如，move-object/from16 v1, v2表示将对象引用从16位寄存器v2移动到寄存器v1中。
		- move-result vx 操作将上一条指令的返回值存储到指令中的目标寄存器vx中。例如，move-result v1表示将上一条指令的返回值移动到寄存器v1中。
		- move-result-wide vx 操作与move-result类似，但是用于保存长整数或双精度浮点数类型的返回值。例如，move-result-wide v1表示将长整数或双精度浮点数类型的返回值移动到寄存器v1中。
		- move-result-object vx 操作与move-result类似，但是用于保存引用类型的返回值。例如，move-result-object v1表示将引用类型的返回值移动到寄存器v1中。
		- move-exception vx 操作用于捕获异常对象并将其移动到指定寄存器vx中。例如，move-exception v1表示将异常对象移动到寄存器v1中。
	- 返回指令(重点)

		- return-void：用于表示函数从一个void方法中返回，返回值为空。例如，return-void表示从当前方法中返回值为空。
		- return vx：用于返回一个整数类型的值，该值存储在寄存器vx中。例如，return v1表示从当前方法中返回寄存器v1中存储的整数类型的值。
		- return-wide vx：用于返回一个长整数或双精度浮点数类型的值，该值存储在寄存器vx和vx+1中。例如，return-wide v1表示从当前方法中返回寄存器v1和v2中存储的长整数或双精度浮点数类型的值。
		- return-object vx：用于返回一个对象引用类型的值，该值存储在寄存器vx中。例如，return-object v1表示从当前方法中返回寄存器v1中存储的对象引用类型的值。
		- return-boolean vx：用于返回一个布尔类型的值，该值存储在寄存器vx中。例如，return-boolean v1表示从当前方法中返回寄存器v1中存储的布尔类型的值。
		- return-byte vx：用于返回一个字节类型的值，该值存储在寄存器vx中。例如，return-byte v1表示从当前方法中返回寄存器v1中存储的字节类型的值。
		- return-char vx：用于返回一个字符类型的值，该值存储在寄存器vx中。例如，return-char v1表示从当前方法中返回寄存器v1中存储的字符类型的值。
		- return-short vx：用于返回一个短整数类型的值，该值存储在寄存器vx中。例如，return-short v1表示从当前方法中返回寄存器v1中存储的短整数类型的值。
	- 数据定义指令(重点)

		- const/4 vA,#+B：用于将一个4位的数值符号扩展为32后赋值给寄存器vA。其中，vA表示目标寄存器，#+B表示常量值，取值范围为-8到7。
		- const/16 vAA, #+BBBB：用于将一个16位的数据符号扩展为32位后赋给寄存器vAA。其中，vAA表示目标寄存器，#+BBBB表示常量值，取值范围为-32768到32767。
		- const vAA, #+BBBBBBBB：用于将一个32位的数值赋给寄存器vAA。其中，vAA表示目标寄存器，#+BBBBBBBB表示常量值，取值范围为-2147483648到2147483647。
		- const/high16 vAA, #+BBBB0000：用于将一个高16位的数值以低16位为零的方式扩展为32位后赋给寄存器vAA。其中，vAA表示目标寄存器，#+BBBB0000表示常量值的高16位。
		- const-wide/16 vAA,#+BBBB：用于将16位的数值符号扩展为64位后赋值给寄存器vAA和vAA+1。其中，vAA和vAA+1表示目标寄存器(因为dalvik寄存器是32位的，所以存储64位数据需要两个寄存器存储)，#+BBBB表示常量值，取值范围为-32768到32767。
		- const-wide/32 vAA, #+BBBBBBBB：用于将32位的数值符号扩展为64位后赋值给寄存器vAA和vAA+1。其中，vAA和vAA+1表示目标寄存器，#+BBBBBBBB表示常量值。
		- const-wide vAA, #+BBBBBBBBBBBBBBBB：用于将64位的数值赋给寄存器vAA和vAA+1。其中，vAA和vAA+1表示目标寄存器，#+BBBBBBBBBBBBBBBB表示常量值。
		- const-wide/high16 vAA, #+BBBB000000000000：用于将一个高16位的数值以其他位为零的方式扩展为64位后赋给寄存器vAA和vAA+1。其中，vAA和vAA+1表示目标寄存器，#+BBBB000000000000表示常量值的高16位。
		- const-string vAA,string@BBBB：用于将字符串常量引用存储到寄存器vAA中，通过字符串ID或字符串。其中，vAA表示目标寄存器，string@BBBB表示字符串在常量池中的索引。
		- const-string/jumbo vAA, string@BBBBBBBB：与const-string类似，但用于存储较长的字符串常量引用。
		- const-class vAA,type@BBBB：用于将类对象常量存储到寄存器vAA中，通过类型ID或类型(如Object.class)。其中，vAA表示目标寄存器，type@BBBB表示类在常量池中的索引。
		- const-class/jumbo vAAAA, type@BBBBBBBB：与const-class类似，但const-class/jumbo指令占用两个字节，值为0xooff，并且其操作数比常规的const-class指令操作数更大。这是Android4.0中新增的指令。
	- 实例操作指令

		- new-instance vAA, type@BBBB：根据类型或者类型ID新建一个对象实例，并将新建的对象的引用存入目标寄存器vAA中。
		- instance-of vA, vB, type@CCCC：检查vB寄存器中的对象引用是否是type@CCCC对应类型的实例，如果是vA寄存器存入非零值，否则vA寄存器存入零。
		- check-cast vAA, type@BBBB：检查vAA寄存器中的对象引用是否可以转换成type@BBBB对应类型的实例。如不可转换，抛出ClassCastException异常，否则继续执行。另外还有一点需要注意，该指令只能用于转换成引用类型，不能用于转换成基本类型。
		- instance-of/jumbo vAAAA, vBBBB, type@CCCCCCCC：指令功能与“instance-of vA, vB, type@CCCC”相同，只是寄存器值与指令的索引取值范围更大。
		- new-instance/jumbo vAAAA, type@BBBBBBBB：指令功能与“new-instance vAA, type@BBBB”相同，只是寄存器值与指令的索引取值范围更大。
	- 数组操作指令

		- array-length vA, vB：计算vB寄存器中数组引用的元素长度并将长度存入vA寄存器。
		- new-array vA, vB, type@CCCC：根据指定类型或类型ID(type@CCCC)与大小(vB寄存器存入数组的长度)构造一个数组，并将数组的引用赋给vA寄存器。
		- filled-new-array {vC, vD, vE, vF, vG}, type@BBBB：根据指定类型或类型ID(type@BBBB)与大小(vA)构造一个数组并填充数组内容，vA寄存器是隐含使用的，除了指定数组的大小外还指定了参数的个数，vC~vG是使用到的参数寄存器序号。指令会将寄存器 vC 到 vG 中的值填充到新数组中，并将新数组引用保存到寄存器 vA 中。还有一点需要注意，filled-new-array 指令创建的数组是一个新的对象，它与原数组没有任何关系。另外，该指令只能用于创建引用类型的数组，不能用于创建基本类型的数组。
		- filled-new-array/range {vCCCC .. vNNNN}, type@BBBB：filled-new-array/range 指令与 filled-new-array 指令非常类似，只是它的参数寄存器是以范围形式给出的，vCCCC 和 vNNNN 分别表示参数寄存器的起始位置和结束位置，type@BBBB 表示数组元素的类型。vC 是 filled-new-array/range 指令的第一个参数寄存器，表示数组大小。N=A+C-1 表示参数寄存器的结束位置，其中 A 表示数组大小，C 表示第一个参数寄存器的编号。因为 filled-new-array/range 指令的参数寄存器是连续的一段，所以 N 的值等于 A+C-1，即参数寄存器的结束位置。例如，如果 filled-new-array/range {v2 .. v5}, type@BBBB 指令被执行，那么数组大小为 v2 中存储的整数值，参数寄存器的编号为 v2、v3、v4、v5，因此 N=A+C-1=4+v2-1=3+v2。
		- fill-array-data vAA, 偏移量：用指定的字面量数组数据填充到目标数组中，字面量数组数据的位址是当前指令位址加偏移量的和。该指令填充的数组类型必须为基本类型的数组和字符串数组，其中基本类型包括 boolean、byte、short、char、int、float 和 double。填充数组时，字面量数组数据的每个元素都必须与目标数组的元素类型相同。另外，该指令只能用于填充已经创建的目标数组，不能用于创建新的数组对象。

		举个例子，假设有如下代码：

		| 1234567891011121314 | `...``fill``-``array``-``data v0, :array_0` `/``/` `将字面量数组数据填充到 v0 寄存器所代表的数组中，:array_0为字面量数组数据的偏移地址(偏移量)``...``:array_0``.array``-``data` `2`            `/``/` `表示每个数组元素占用两个字节``0x14ebs`             `/``/` `数组元素值为` `0x14eb``（short 类型）``0x15f0s`             `/``/` `数组元素值为` `0x15f0``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``0x15c7s`             `/``/` `数组元素值为` `0x15c7``（short 类型）``...` |
		|-|-|
	- 异常指令

		- throw vAA：抛出异常对象，异常对象的引用在vAA寄存器。
	- 跳转指令(重点)

		- 无条件跳转指令

			- goto 目标：通过短偏移量无条件跳转到目标。
		- 分支跳转指令

			- packed-switch vAA, 索引表偏移量：实现一个switch语句，case常量是连续的，这个指令使用索引表，vAA是在表中找到具体case的指令偏移量的索引，如果无法在表中找到vAA对应的索引将继续执行下一个指令(即default case)，执行完case中的代码后，如果Java源代码设置了break强制跳出switch，就会无条件跳转到所有case的出口处，如果没有强制跳出switch，就会执行完default case中的代码后再跳转到所有case的出口处继续执行代码。

			举个例子，假设有如下代码：

			Java代码：

			```
			switch (this.mType) {
			            case 1:
			                return Math.signum(0.5d - (getP(d) % 1.0d));
			            case 2:
			                abs = Math.abs((((getP(d) * 4.0d) + 1.0d) % 4.0d) - 2.0d);
			                break;
			            case 3:
			                return (((getP(d) * 2.0d) + 1.0d) % 2.0d) - 1.0d;
			            case 4:
			                abs = ((getP(d) * 2.0d) + 1.0d) % 2.0d;
			                break;
			            case 5:
			                return Math.cos(this.PI2 * getP(d));
			            case 6:
			                double abs2 = 1.0d - Math.abs(((getP(d) * 4.0d) % 4.0d) - 2.0d);
			                abs = abs2 * abs2;
			                break;
			            default:
			                return Math.sin(this.PI2 * getP(d));
			        }
			```

			smali代码：

			| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172737475767778798081828384858687888990919293949596979899100101102103104105106107108109110111112113114115116117118119120121122123124125126127128129130131132133134135136 | `packed``-``switch v0, :pswitch_data_5e` `# 带着v0寄存器中的值跳转到索引表偏移量:pswitch_data_5e位址寻找对应的case指令偏移量的索引` `.line` `120``# default分支语句``iget``-``wide v0, p0, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>PI2:D` `invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `v0, p1` `invoke``-``static {v0, v1}, Ljava``/``lang``/``Math;``-``>sin(D)D` `move``-``result``-``wide p1` `return``-``wide p1` `.line` `132``:pswitch_17` `# case 6``invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `p1, v1` `rem``-``double``/``2addr` `p1, v1` `sub``-``double``/``2addr` `p1, v3` `invoke``-``static {p1, p2}, Ljava``/``lang``/``Math;``-``>``abs``(D)D` `move``-``result``-``wide p1` `sub``-``double p1, v5, p1` `mul``-``double``/``2addr` `p1, p1` `:goto_25` `# 所有case的出口，也可以说是在case中执行break后跳转到此处``sub``-``double``/``2addr` `v5, p1` `return``-``wide v5` `.line` `130``:pswitch_27` `# case 5``iget``-``wide v0, p0, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>PI2:D` `invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `v0, p1` `invoke``-``static {v0, v1}, Ljava``/``lang``/``Math;``-``>cos(D)D` `move``-``result``-``wide p1` `return``-``wide p1` `.line` `128``:pswitch_33` `# case 4``invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `p1, v3` `add``-``double``/``2addr` `p1, v5` `rem``-``double``/``2addr` `p1, v3` `goto :goto_25` `# 跳转到偏移量为goto_25的目标位址` `.line` `126``:pswitch_3b` `# case 3``invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `p1, v3` `add``-``double``/``2addr` `p1, v5` `rem``-``double``/``2addr` `p1, v3` `sub``-``double``/``2addr` `p1, v5` `return``-``wide p1` `.line` `124``:pswitch_44` `# case2``invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `mul``-``double``/``2addr` `p1, v1` `add``-``double``/``2addr` `p1, v5` `rem``-``double``/``2addr` `p1, v1` `sub``-``double``/``2addr` `p1, v3` `invoke``-``static {p1, p2}, Ljava``/``lang``/``Math;``-``>``abs``(D)D` `move``-``result``-``wide p1` `goto :goto_25` `# 跳转到偏移量为goto_25的目标位址` `:pswitch_51` `# case 1``const``-``wide``/``high16 v0,` `0x3fe0000000000000L`    `# 0.5` `.line` `122``invoke``-``virtual {p0, p1, p2}, Landroidx``/``constraintlayout``/``motion``/``utils``/``Oscillator;``-``>getP(D)D` `move``-``result``-``wide p1` `rem``-``double``/``2addr` `p1, v5` `sub``-``double``/``2addr` `v0, p1` `invoke``-``static {v0, v1}, Ljava``/``lang``/``Math;``-``>signum(D)D` `move``-``result``-``wide p1` `return``-``wide p1` `:pswitch_data_5e``.packed``-``switch` `0x1` `# 索引表，case常量从1开始，依次递增``:pswitch_51` `# case 1``:pswitch_44` `# case 2``:pswitch_3b` `# case 3``:pswitch_33` `# case 4``:pswitch_27` `# case 5``:pswitch_17` `# case 6``.end packed``-``switch` |
			|-|-|
			- sparse-switch vAA, 查询表偏移量：实现一个switch语句，case常量是非连续的，这个指令使用查询表，用于表示case常量和每个case常量的偏移量。如果vAA寄存器中的值无法在表中匹配将继续执行下一个指令(即default case)。执行完case中的代码后，如果Java源代码设置了break强制跳出switch，就会无条件跳转到所有case的出口处，如果没有强制跳出switch，就会执行完default case中的代码后再跳转到所有case的出口处继续执行代码。

			举个例子，假设有如下代码：

			Java代码：

			| 12345678910 | `switch` `(transit) {``case` `4097``:``return` `8194``;``case` `4099``:``return` `4099``;``case` `8194``:``return` `4097``;``default``:``return` `0``;``}` |
			|-|-|

			smali代码：

			| 123456789101112131415161718192021222324252627282930 | `sparse``-``switch p0, :sswitch_data_e` `# sparse-switch指令，传入寄存器p0的值作为查找表的索引，:sswitch_data_e是查询表的偏移量` `.line` `2025`                    `# 源代码的行号``:goto_4` `# 这里是所有case的出口，如果case常量没匹配上查询表中的值，那么v0寄存器中的值就为0，这里就返回零，也就是default下的代码return 0;``return` `v0` `# 返回v0寄存器中的值` `.line` `2016`                    `# 源代码的行号``:sswitch_5` `# 标签，对应表中的第一个case常量0x1001``const``/``16` `v0,` `0x2002`           `# 将0x2002赋值给v0寄存器` `.line` `2017`                    `# 源代码的行号``goto :goto_4` `# 无条件跳转到:goto_4标签处执行` `.line` `2019`                    `# 源代码的行号``:sswitch_8` `# 标签，对应表中的第三个case常量0x2002``const``/``16` `v0,` `0x1001`           `# 将0x1001赋值给v0寄存器` `.line` `2020`                    `# 源代码的行号` `goto :goto_4` `# 无条件跳转到:goto_4标签处执行`  `.line` `2022`                    `# 源代码的行号` `:sswitch_b` `# 标签，对应表中的第二个case常量0x1003``const``/``16` `v0,` `0x1003`           `# 将0x1003赋值给v0寄存器` `goto :goto_4` `# 无条件跳转到:goto_4标签处执行` `.line` `2014`                    `# 源代码的行号``:sswitch_data_e` `# 标签，作为查询表的偏移量``.sparse``-``switch` `# 表示接下来是一个查询表``0x1001` `-``> :sswitch_5` `# case常量0x1001跳转到标签:sswitch_5处执行``0x1003` `-``> :sswitch_b` `# case常量0x1003跳转到标签:sswitch_b处执行``0x2002` `-``> :sswitch_8` `# case常量0x2002跳转到标签:sswitch_8处执行``.end sparse``-``switch` `# 标志着查询表的结束` |
			|-|-|
		- 条件跳转指令

		if-eq vA, vB, 目标：如果vA == vB，跳转到目标。

		if-ne vA, vB, 目标：如果vA != vB，跳转到目标。

		if-lt vA, vB, 目标：如果vA < vB，跳转到目标。

		if-ge vA, vB, 目标：如果vA >= vB，跳转到目标。

		if-gt vA, vB, 目标：如果vA > vB，跳转到目标。

		if-le vA, vB, 目标：如果vA <= vB，跳转到目标。

		if-eqz vA, 目标：如果vA == 0，跳转到目标。

		if-nez vA, 目标：如果vA != 0，跳转到目标。

		if-ltz vA, 目标：如果vA < 0，跳转到目标。

		if-gez vA, 目标：如果vA >= 0，跳转到目标。

		if-gtz vA, 目标：如果vA > 0，跳转到目标。

		if-lez vA, 目标：如果vA <= 0，跳转到目标。
	- 比较指令

		- cmpl-float vAA,vBB,vCC：比较vBB和vCC的float值并在vAA存入int型返回值。非数值默认为小于，如果参数为非数值将返回-1。如果vBB寄存器大于vCC寄存器，则结果为-1，相等则结果为0，小于则结果为1。
		- cmpg-float vAA,vBB,vCC：比较vBB和vCC的float值并在vAA存入int型返回值。非数值默认为大于，如果参数为非数值将返回1。如果vBB寄存器大于vCC寄存器，则结果为1，相等则结果为0，小于则结果为-1。
		- cmpl-double vAA,vBB,vCC：比较vBB和vCC的double值并在vAA存入int型返回值。非数值默认为小于，如果参数为非数值将返回-1。如果vBB,vBB+1寄存器的值大于vCC,vCC+1寄存器的值，则结果为-1，相等则结果为0，小于则结果为1。
		- cmpg-double vAA,vBB,vCC：比较vBB和vCC的double值并在vAA存入int型返回值。非数值默认为大于，如果参数为非数值将返回1。如果vBB,vBB+1寄存器的值大于vCC,vCC+1寄存器的值，则结果为1，相等则结果为0，小于则结果为-1。
		- cmp-long vAA,vBB,vCC：比较vBB和vCC的long值并在vAA存入int型返回值。如果vBB寄存器大于vCC寄存器，则结果为1，相等则结果为0，小则结果为-1。
	- 字段操作指令

		- iput-object vAA,vBB,字段ID：根据字段ID将vAA寄存器的值存入实例的对象引用字段，vBB寄存器中是该实例的引用。例如：

		| 1 | `iput``-``object` `v0, p0, Lbin``/``mt``/``apksignaturekillerplus``/``HookApplication;``-``>appPkgName:Ljava``/``lang``/``String;` |
		|-|-|

		可以看到例子中将v0寄存器中Ljava/lang/String;类型的值(实例的对象引用)存入到p0寄存器中，p0寄存器中是Lbin/mt/apksignaturekillerplus/HookApplication;类型下字段名为appPkgName的实例字段，并且实例字段appPkgName的存储值类型为Ljava/lang/String;
		- iput-boolean vAA,字段ID：根据字段ID将vAA寄存器的值存入实例的boolean型字段，vBB寄存器中是该实例的引用。例如：

		| 1 | `iput``-``boolean p1, p0, Lbin``/``mt``/``plugin``/``api``/``translation``/``TranslationEngine$Configuration;``-``>acceptTranslated:Z` |
		|-|-|

		可以看到例子中将p1寄存器中boolean型的值存入到p0寄存器中，p0寄存器中是Lbin/mt/plugin/api/translation/TranslationEngine$Configuration;类型下字段名为acceptTranslated的实例字段，并且实例字段acceptTranslated的存储值类型为boolean。
		- iput-wide vAA,vBB,字段ID：根据字段ID将vAA,vAA+1寄存器的值存入实例的double/long型字段，vBB寄存器中是该实例的引用。例如：

		| 1 | `iput``-``wide v1, p0, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``l;``-``>e:J` |
		|-|-|

		可以看到例子中将v1,v2寄存器中long型的值存入到p0寄存器中，p0寄存器中是Lcom/alipay/android/phone/mrpc/core/l;类型下字段名为e的实例字段，并且实例字段e的存储值类型为long。
		- iput vAA,vBB,字段ID：根据字段ID将vAA寄存器的值存入实例的int型字段，vBB寄存器中是该实例的引用。例如：

		| 1 | `iput v0, p0, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``e;``-``>a:I` |
		|-|-|

		可以看到例子中将v0寄存器中int型的值存入到p0寄存器中，p0寄存器中是Lcom/alipay/android/phone/mrpc/core/e;类型下字段名为a的实例字段，并且实例字段a的存储值类型为boolean。
		- iget-object vAA,vBB,字段ID：根据字段ID读取一个实例的对象引用字段到vAA，vBB寄存器中是该实例的引用。例如：

		| 1 | `iget``-``object` `v4, p0, Lbin``/``mt``/``apksignaturekillerplus``/``HookApplication;``-``>appPkgName:Ljava``/``lang``/``String;` |
		|-|-|

		可以看到例子中将p0寄存器中Ljava/lang/String;类型的值(实例的对象引用)存入到v4寄存器中，p0寄存器中是Lbin/mt/apksignaturekillerplus/HookApplication;类型下字段名为appPkgName的实例字段，并且实例字段appPkgName的存储值类型为Ljava/lang/String;
		- iget-boolean vAA,vBB,字段ID：根据字段ID读取实例的boolean型字段到vAA，vBB寄存器中是该实例的引用。例如：

		| 1 | `iget``-``boolean v1, p0, Lbin``/``mt``/``plugin``/``api``/``translation``/``TranslationEngine$ConfigurationBuilder;``-``>acceptTranslated:Z` |
		|-|-|

		可以看到例子中将p0寄存器中boolean型的值存入到v1寄存器中，p0寄存器中是Lbin/mt/plugin/api/translation/TranslationEngine$ConfigurationBuilder;类型下字段名为acceptTranslated的实例字段，并且实例字段acceptTranslated的存储值类型为boolean。
		- iget-wide vAA,vBB,字段ID：根据字段ID读取实例的double/long型字段到vAA,vAA+1，vBB寄存器中是该实例的引用。例如：

		| 1 | `iget``-``wide v3, p0, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``l;``-``>g:J` |
		|-|-|

		可以看到例子中将p0寄存器中long型的值存入到v3,v4寄存器中，p0寄存器中是Lcom/alipay/android/phone/mrpc/core/l;类型下字段名为g的实例字段，并且实例字段g的存储值类型为long。
		- iget vAA,vBB,字段ID：根据字段ID读取实例的int型字段到vAA，vBB寄存器中是该实例的引用。例如：

		| 1 | `iget v1, v8, Landroid``/``util``/``TypedValue;``-``>data:I` |
		|-|-|

		可以看到例子中将v8寄存器中int型的值存入到v1寄存器中，v8寄存器中是Landroid/util/TypedValue;类型下字段名为data的实例字段，并且实例字段data的存储值类型为int。
		- sput-object vAA,字段ID：根据字段ID将vAA寄存器中的对象引用赋值到对象引用静态字段。例如：

		| 1 | `sput``-``object` `v0, Lbin``/``tools``/``inject``/``InjectedLog;``-``>TIME_FORMAT1:Ljava``/``text``/``SimpleDateFormat;` |
		|-|-|

		可以看到例子中将v0寄存器中Ljava/text/SimpleDateFormat;类型的值(对象引用)存入到Lbin/tools/inject/InjectedLog;类型下的存储值为Ljava/text/SimpleDateFormat;类型的对象引用静态字段TIME_FORMAT1中。
		- sput-boolean vAA,字段ID：根据字段ID将vAA寄存器中的值赋值到boolean型静态字段。例如：

		| 1 | `sput``-``boolean v6, Lcom``/``alipay``/``sdk``/``cons``/``a;``-``>r:Z` |
		|-|-|

		可以看到例子中将v6寄存器中boolean类型的值存入到Lcom/alipay/sdk/cons/a;类型下的存储值为boolean类型的静态字段r中。
		- sput-wide vAA,字段ID：根据字段ID将vAA,vAA+1寄存器中的值赋值到double/long型静态字段。例如：

		| 1 | `sput``-``wide v0, Lcom``/``alipay``/``sdk``/``app``/``PayTask;``-``>i:J` |
		|-|-|

		可以看到例子中将v0,v1寄存器中long类型的值存入到Lcom/alipay/sdk/app/PayTask;类型下的存储值为long类型的静态字段i中。
		- sput vAA,字段ID：根据字段ID将vAA寄存器中的值赋值到int型静态字段。例如：

		| 1 | `sput v0, Lcom``/``google``/``android``/``material``/``appbar``/``AppBarLayout;``-``>DEF_STYLE_RES:I` |
		|-|-|

		可以看到例子中将v0寄存器中int类型的值存入到Lcom/google/android/material/appbar/AppBarLayout;类型下的存储值为int类型的静态字段DEF_STYLE_RES中。
		- sget-object vAA,字段ID：根据字段ID读取静态对象引用字段到vAA。例如：

		| 1 | `sget``-``object` `v17, Ljava``/``lang``/``System;``-``>out:Ljava``/``io``/``PrintStream;` |
		|-|-|

		可以看到例子中将Ljava/lang/System;类型下的静态字段out中的Ljava/io/PrintStream;类型的值(对象引用)存入v17寄存器中。
		- sget-boolean vAA,字段ID：根据字段ID读取静态boolean型字段到vAA。例如：

		| 1 | `sget``-``boolean v1, Lbin``/``mt``/``plus``/``Features;``-``>ۘf:Z` |
		|-|-|

		可以看到例子中将Lbin/mt/plus/Features;类型下的静态字段f中的boolean类型的值存入v1寄存器中。
		- sget-wide vAA,字段ID：根据字段ID读取静态double/long型字段到vAA,vAA+1。例如：

		| 1 | `sget``-``wide v2, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``b;``-``>a:J` |
		|-|-|

		可以看到例子中将Lcom/alipay/android/phone/mrpc/core/b;类型下的静态字段a中的long类型的值存入v2,v3寄存器中。
		- sget vAA,字段ID：根据字段ID读取静态int型字段到vAA。例如：

		| 1 | `sget v0, Landroid``/``os``/``Build$VERSION;``-``>SDK_INT:I` |
		|-|-|

		可以看到例子中将Landroid/os/Build$VERSION;类型下的静态字段SDK_INT中的int类型的值存入v0寄存器中。
	- 方法调用指令(重点)

		- invoke-virtual {参数},方法名：调用带参数的实例的虚方法(虚方法相当于Java中的普通方法)。
		- invoke-virtual/range {vAA .. vBB},方法名：调用以寄存器范围为参数的虚方法。该指令第一个寄存器和寄存器的数量将会传递给方法。该指令与普通的invoke-virtual指令相比，可以同时传递多个参数，提高了效率。例如：

		| 12345 | `sget``-``object` `v17, Ljava``/``lang``/``System;``-``>out:Ljava``/``io``/``PrintStream;` `const``-``string``/``jumbo v18,` `"PmsHook success."` `invoke``-``virtual``/``range` `{v17 .. v18}, Ljava``/``io``/``PrintStream;``-``>println(Ljava``/``lang``/``String;)V` |
		|-|-|

		在这条指令中，寄存器范围为{v17 .. v18}，调用java.io.PrintStream类的println(String)方法，该方法需要一个参数，参数类型为java.lang.String，并且不返回任何值。该指令的第一个寄存器为v17，寄存器的数量为2，因此v17和v18两个寄存器都将作为参数传递给方法，其中v18存储了传递给println()方法的参数值，v17则存储了PrintStream对象的引用。在执行该指令之前，需要先将参数值存储在寄存器v18中，将PrintStream对象的引用存储在寄存器v17中。该虚方法的作用是将参数值打印到控制台上。在Dalvik字节码中，方法的参数和返回值都是通过寄存器进行传递的。
		- invoke-super {参数},方法名：调用带参数的直接父类的虚方法。
		- invoke-super/range {vAA .. vBB},方法名：调用以寄存器范围为参数的直接父类的虚方法。该指令第一个寄存器和寄存器的数量将会传递给方法。
		- invoke-direct {参数},方法名：不解析直接调用带参数的方法，例如构造方法、静态语句块。
		- invoke-direct/range {vAA .. vBB},方法名：不解析直接调用以寄存器范围为参数的方法。该指令第一个寄存器和寄存器的数量将会传递给方法。
		- invoke-static {参数},方法名：调用带参数的静态方法。
		- invoke-static/range {vAA .. vBB},方法名：调用以寄存器范围为参数的静态方法。该指令第一个寄存器和寄存器的数量将会传递给方法。
		- invoke-interface {参数},方法名：调用带参数的接口方法。
		- invoke-interface/range {vAA .. vBB},方法名：调用以寄存器范围为参数的接口方法。该指令第一个寄存器和寄存器的数量将会传递给方法。
	- 数据转换指令

		- neg-int：对整型数求补。取补指令是按位取反后加1，即将二进制数中的0变为1，1变为0，然后再加1。在Dalvik指令集中，取补指令的格式为“neg vA, vB”，表示将vB寄存器中的值按位取反后加1后存储到vA寄存器中。
		- not-int：对整型数求反。取反指令是按位取反，即将二进制数中的0变为1，1变为0。在Dalvik指令集中，取反指令的格式为“not vA, vB”，表示将vB寄存器中的值按位取反后存储到vA寄存器中。
		- neg-long：对长整型数求补。
		- not-long：对长整型数求反。
		- neg-float：对单精度浮点型数求补。
		- neg-double：对双精度浮点型数求补。
		- int-to-byte：将整型数转换为字节型。格式为“int-to-byte vA, vB”，表示将vB寄存器中的整型数转换为字节型后存放到vA寄存器中。需要注意的是，由于字节型数的范围是-128到127，因此在转换时可能会出现溢出情况。
		- int-to-char：将整型数转换为字符型。格式为“int-to-char vA, vB”，表示将vB寄存器中的整型数转换为字符型后存放到vA寄存器中。因为char类型是无符号的，大小为两个字节，所以可以表示的最大值就是2^16-1=65535。字符型数的范围是0到65535，在转换时可能会出现溢出情况。
		- int-to-short：将整型数转换为短整型。格式为“int-to-short vA, vB”，表示将vB寄存器中的整型数转换为短整型后存放到vA寄存器中。短整型数的范围是-32768到32767，因此在转换时可能会出现溢出情况。
		- long-to-int：将长整型数转换为整型数。格式为“long-to-int vA, vB”，表示将vB寄存器中的长整型数转换为整型数后存放到vA寄存器中。需要注意的是，由于长整型数的范围比整型数大，因此在转换时可能会出现溢出情况。
		- long-to-float：将长整型数转换为单精度浮点型数。格式为“long-to-float vA, vB”，表示将vB寄存器中的长整型数转换为单精度浮点型数后存放到vA寄存器中。
		- long-to-double：将长整型数转换为双精度浮点型数。格式为“long-to-double vA, vB”，表示将vB寄存器中的长整型数转换为双精度浮点型数后存放到vA寄存器中。
		- float-to-int：将单精度浮点型数转换为整型数。格式为“float-to-int vA, vB”，表示将vB寄存器中的单精度浮点型数转换为整型数后存放到vA寄存器中。需要注意的是，由于单精度浮点型数的范围比整型数大，因此在转换时可能会出现溢出情况。
		- float-to-long：将单精度浮点型数转换为长整型数。格式为“float-to-long vA, vB”，表示将vB寄存器中的单精度浮点型数转换为长整型数后存放到vA寄存器中。
		- float-to-double：将单精度浮点型数转换为双精度浮点型数。格式为“float-to-double vA, vB”，表示将vB寄存器中的单精度浮点型数转换为双精度浮点型数后存放到vA寄存器中。
		- double-to-int：将双精度浮点型数转换为整型数。格式为“double-to-int vA, vB”，表示将vB寄存器中的双精度浮点型数转换为整型数后存放到vA寄存器中。需要注意的是，由于双精度浮点型数的范围比整型数大，因此在转换时可能会出现溢出情况。
		- double-to-long：将双精度浮点型数转换为长整型数。格式为“double-to-long vA, vB”，表示将vB寄存器中的双精度浮点型数转换为长整型数后存放到vA寄存器中。
		- double-to-float：将双精度浮点型数转换为单精度浮点型数。格式为“double-to-float vA, vB”，表示将vB寄存器中的双精度浮点型数转换为单精度浮点型数后存放到vA寄存器中。需要注意的是，由于单精度浮点型数的范围比双精度浮点型数小，因此在转换时可能会出现精度损失的情况。
		- int-to-byte：将整型数转换为字节型。格式为“int-to-byte vA, vB”，表示将vB寄存器中的整型数转换为字节型后存放到vA寄存器中。
		- int-to-char：将整型数转换为字符型。格式为“int-to-char vA, vB”，表示将vB寄存器中的整型数转换为字符型后存放到vA寄存器中。
		- int-to-short：将整型数转换为短整型。格式为“int-to-short vA, vB”，表示将vB寄存器中的整形数转换为短整形后存放到vA寄存器中。
	- 数据运算指令

		- add-type：进行加法运算。格式为“add-int vA, vB, vC”，表示将vB寄存器中的整型数与vC寄存器中的整型数相加，结果存放到vA寄存器中。
		- sub-type：进行减法运算。格式为“sub-int vA, vB, vC”，表示将vB寄存器中的整型数减去vC寄存器中的整型数，结果存放到vA寄存器中。
		- mul-type：进行乘法运算。格式为“mul-int vA, vB, vC”，表示将vB寄存器中的整型数与vC寄存器中的整型数相乘，结果存放到vA寄存器中。
		- div-type：进行除法运算。格式为“div-int vA, vB, vC”，表示将vB寄存器中的整型数除以vC寄存器中的整型数，结果存放到vA寄存器中。
		- rem-type：进行取余运算。格式为“rem-int vA, vB, vC”，表示将vB寄存器中的整型数除以vC寄存器中的整型数的余数，结果存放到vA寄存器中。
		- and-type：进行按位与运算。格式为“and-int vA, vB, vC”，表示将vB寄存器中的整型数与vC寄存器中的整型数进行按位与运算，结果存放到vA寄存器中。
		- or-type：进行按位或运算。格式为“or-int vA, vB, vC”，表示将vB寄存器中的整型数与vC寄存器中的整型数进行按位或运算，结果存放到vA寄存器中。
		- xor-type：进行按位异或运算。格式为“xor-int vA, vB, vC”，表示将vB寄存器中的整型数与vC寄存器中的整型数进行按位异或运算，结果存放到vA寄存器中。
		- shl-type：有符号左移。格式为“shl-type vA, vB, vC”，表示将vB寄存器中的有符号整型数左移vC位，结果存放到vA寄存器中。左移时，低位补0，高位舍弃。
		- shr-type：有符号右移。格式为“shr-type vA, vB, vC”，表示将vB寄存器中的有符号整型数右移vC位，结果存放到vA寄存器中。右移时，高位补符号位，低位舍弃。
		- ushr-type：无符号右移。格式为“ushr-type vA, vB, vC”，表示将vB寄存器中的无符号整型数右移vC位，结果存放到vA寄存器中。右移时，高位补0，低位舍弃。

#### smali文件

无论是普通类、抽象类、接口类还是内部类，在反编译出来的代码中，它们都是以单独的smali文件进行存放的。每个smali文件中的语句都遵循着一套语法规范，这里想要讲解的正是这套smali文件中的语法规范。

- Smali中开头的包信息以及包信息格式：

**.class <访问权限> [修饰关键字] <类名>**

**.super <父类名>**

**.source <源文件名>**

例如：

| 1234 | `.``class` `public interface abstract Landroid``/``support``/``v4``/``os``/``IResultReceiver;``/``/` `这个类是android.support.v4.os这个包下名为IResultReceiver的接口类``.``super` `Ljava``/``lang``/``Object``;` `/``/` `该类继承了父类java.lang.``Object``.source` `"IResultReceiver.java"` `/``/` `这个smali文件在还是Java文件时，文件名为IResultReceiver.java` |
|-|-|
- 静态字段定义

格式：

| 1 | `*``*``.field <访问权限> static [修饰关键字] <字段名>:<字段类型>``*``*` |
|-|-|

例如：

| 1 | `.field private static final PARAMETER_BUFFER:Ljava``/``lang``/``ThreadLocal;` |
|-|-|
- 实例字段定义（java中的普通字段）

相比起静态字段定义，实例字段就少了一个静态修饰符static而已，格式：

| 1 | `.field <访问权限> [修饰关键字] <字段名>:<字段类型>` |
|-|-|

例如：

| 1 | `.field public final mConstructorArgs:[Ljava``/``lang``/``Object``;` |
|-|-|
- 直接方法定义

| 123456789 | `# direct methods``.method <访问权限> [修饰关键字] <方法名称、参数还有返回值>``<.registers>` `/``/` `指定了方法中寄存器的总数，这个数量是参数寄存器和本地寄存器的总和。``<.local>` `/``/` `这个指令表明方法中非参数寄存器(本地寄存器)的个数``[.param]` `/``/` `表明了方法的参数，每个.param指令表示一个参数，方法使用了几个参数就有几个.param指令。``[.prologue]` `/``/` `表明了方法中代码的开始处``[.line]` `/``/` `表名了该处代码在源代码中的行号``<代码体>``.end method` |
|-|-|

例如：

| 123456789101112131415161718192021222324 | `.method public static spatialSampling(Landroid``/``gesture``/``Gesture;IZ)[F``/``/` `定义一个公共静态方法，返回一个浮点数数组``/``/` `方法名为spatialSampling，参数为Gesture对象、整型bitmapSize和布尔型keepAspectRatio``.``locals` `0``/``/` `定义本地寄存器数为``0` `.param p0,` `"gesture"`    `# Landroid/gesture/Gesture;``/``/` `定义一个参数p0，类型为Gesture，表示手势对象``.param p1,` `"bitmapSize"`    `# I``/``/` `定义一个参数p1，类型为整型，表示位图大小``.param p2,` `"keepAspectRatio"`    `# Z``/``/` `定义一个参数p2，类型为布尔型，表示是否保持宽高比` `new``-``instance p0, Ljava``/``lang``/``RuntimeException;``/``/` `创建一个RuntimeException对象，将其引用赋值给p0` `invoke``-``direct {p0}, Ljava``/``lang``/``RuntimeException;``-``><init>()V``/``/` `调用RuntimeException对象的构造方法，初始化该对象` `throw p0``/``/` `抛出RuntimeException对象` `.end method``/``/` `方法结束` |
|-|-|
- 虚方法(java中的普通方法)

| 123456789 | `# virtual methods``.method <访问权限> [修饰关键字] <方法名称、参数还有返回值>``<.registers>` `/``/` `指定了方法中寄存器的总数，这个数量是参数寄存器和本地寄存器的总和。``<.local>` `/``/` `这个指令表明方法中非参数寄存器(本地寄存器)的个数``[.param]` `/``/` `表明了方法的参数，每个.param指令表示一个参数，方法使用了几个参数就有几个.param指令。``[.prologue]` `/``/` `表明了方法中代码的开始处``[.line]` `/``/` `表名了该处代码在源代码中的行号``<代码体>``.end method` |
|-|-|

除了顶头的注释和直接方法不同，其他没什么区别，我们来看一个例子，例如：

| 1234567891011121314151617181920 | `# virtual methods``/``/` `定义虚方法` `.method public final createConnectionKeepAliveStrategy()Lorg``/``apache``/``http``/``conn``/``ConnectionKeepAliveStrategy;``/``/` `方法名为createConnectionKeepAliveStrategy，返回值类型为ConnectionKeepAliveStrategy对象``/``/` `final关键字表示该方法不能被子类重写``.``locals` `1``/``/` `定义本地寄存器数为``1` `new``-``instance v0, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``f;``/``/` `创建一个com.alipay.android.phone.mrpc.core.f类的实例对象，并将其引用赋值给v0` `invoke``-``direct {v0, p0}, Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``f;``-``><init>(Lcom``/``alipay``/``android``/``phone``/``mrpc``/``core``/``d;)V``/``/` `调用v0对象的构造方法，将p0对象作为参数传入。``/``/` `这里要注意v0寄存器中存放的是com.alipay.android.phone.mrpc.core.f类的实例对象，也可以说是java中的this。` `return``-``object` `v0``/``/` `将v0对象返回``.end method``/``/` `方法结束` |
|-|-|
- 接口

| 123 | `# interfaces` `.implements <接口名>` |
|-|-|

例如：

| 1234 | `# interfaces` `.implements Ljava``/``lang``/``reflect``/``InvocationHandler;``/``/` `当前类实现了接口Ljava``/``lang``/``reflect``/``InvocationHandler;` |
|-|-|
- 注解

在讲注解之前先解释一下什么是类型签名：在Java中，每个类、接口、数组、枚举、注解和基本类型都有一个唯一的类型签名。类型签名是一个字符串，用来描述该类型的全限定名、类型参数、维度等信息。类型签名的格式如下：

| 123456789 | `<``type` `signature> ::``=` `<``class` `type``> \| <array` `type``> \| <``type` `variable>``<``class` `type``> ::``=` `L <fully qualified` `class` `name> ; <``type` `arguments>``*``<array` `type``> ::``=` `[ <``type``>``<``type` `variable> ::``=` `T <identifier> ;``<``type` `arguments> ::``=` `<``type` `argument>``*``<``type` `argument> ::``=` `<wildcard> \| <reference` `type``>``<wildcard> ::``=` `? <wildcard bound>?``<wildcard bound> ::``=` `extends <reference` `type``> \|` `super` `<reference` `type``>``<reference` `type``> ::``=` `<``class` `type``> \| <``type` `variable>` |
|-|-|

下面是类型签名的详细解释：

	1. `<type signature>`：表示一个类型签名。它可以是`<class type>`、`<array type>`或`<type variable>`。
	2. `<class type>`：表示一个类类型。它的格式为`L <fully qualified class name> ; <type arguments>*`，其中`<fully qualified class name>`是类的全限定名，使用斜杠（/）分隔包名和类名，例如`java/lang/String`。`<type arguments>`表示类的泛型参数，可以有多个。
	3. `<array type>`：表示一个数组类型。它的格式为`[ <type>`，其中`<type>`是数组元素的类型。
	4. `<type variable>`：表示一个类型变量。它的格式为`T <identifier> ;`，其中`<identifier>`是类型变量的标识符。
	5. `<type arguments>`：表示一个或多个类型参数。它的格式为`<type argument>*`，即可以有零个或多个类型参数。
	6. `<type argument>`：表示一个类型参数。它可以是`<wildcard>`或`<reference type>`。
	7. `<wildcard>`：表示一个通配符类型参数。它的格式为`? <wildcard bound>?`，其中`<wildcard bound>`表示通配符的上界或下界。
	8. `<wildcard bound>`：表示通配符的上界或下界。它可以是`extends <reference type>`或`super <reference type>`，表示通配符的上界或下界是某个参考类型。
	9. `<reference type>`：表示一个参考类型。它可以是`<class type>`或`<type variable>`。在Smali代码中，类型签名的格式与Java基本一致，只是用L来表示类类型，用[来表示数组类型，用T来表示类型变量。例如，类型签名Ljava/lang/Deprecated表示的是Java内置类Deprecated的类型签名。

注解的格式：

| 1234 | `# annotation``.annotation [注解属性] <注解类名>``[注解字段` `=` `值]``.end annotation` |
|-|-|

在Smali中，可以使用注解来提供额外的信息和指令给编译器和虚拟机。

以下是Smali注解的一些常见规范和详解：

	1. `.annotation`：用于声明一个注解类型。语法为`.annotation <visibility> <annotation_type> {<element>}` ，其中`<visibility>`可以是`public`、`protected`、`private`或`package`，`<annotation_type>`是注解类型的全限定名，`<element>`是注解的元素。
	2. `.subannotation`：用于声明一个嵌套注解类型。语法为`.subannotation <visibility> <annotation_type> {<element>}` ，与`.annotation`类似。
	3. `.end annotation`：用于结束一个注解类型的声明。
	4. `.enum`：用于声明一个枚举类型。语法为`.enum <visibility> <enum_type> {<enum_element>}` ，其中`<visibility>`可以是`public`、`protected`、`private`或`package`，`<enum_type>`是枚举类型的全限定名，`<enum_element>`是枚举的元素。
	5. `.end enum`：用于结束一个枚举类型的声明。
	6. `.field`：用于为字段添加注解。语法为`.field <field_spec> {<annotation>}` ，其中`<field_spec>`是字段的声明，`<annotation>`是字段的注解。
	7. `.method`：用于为方法添加注解。语法为`.method <method_spec> {<annotation>}` ，其中`<method_spec>`是方法的声明，`<annotation>`是方法的注解。
	8. `.parameter`：用于为方法参数添加注解。语法为`.parameter <parameter_index> <annotation>`，其中`<parameter_index>`是参数的索引，从0开始，`<annotation>`是参数的注解。
	9. `.prologue`：用于指定方法的前导代码。
	10. `.line`：用于指定源代码中的行号。
	11. `.end method`：用于结束一个方法的声明。
	12. `.catch`：用于捕获异常。语法为`.catch <exception_type> {<handler>}` ，其中`<exception_type>`是异常类型的全限定名，`<handler>`是捕获异常后的处理代码。
	13. `.catchall`：用于捕获所有异常。语法为`.catchall {<handler>}` ，其中`<handler>`是捕获异常后的处理代码。
	14. `.locals`：用于指定方法中的本地变量数量。语法为`.locals <count>`，其中`<count>`是本地变量的数量。
	15. `.end`：用于结束一个代码块或注解的声明。注解的作用范围可以是类、方法或者字段。

如果注解的作用范围是类，".annotation"指令会直接定义在smali文件中，例如：

| 123456789101112131415161718 | `.``class` `public interface abstract annotation Ll``/``۬ۘ;``.``super` `Ljava``/``lang``/``Object``;``.source` `"H5TW"` `# annotation``/``/` `定义注解``.annotation runtime Ljava``/``lang``/``annotation``/``Retention;``/``/` `定义一个运行时注解Retention``/``/` `runtime表示该注解在运行时可见，即可以通过反射获取该注解信息``/``/` `Ljava``/``lang``/``annotation``/``Retention表示Retention注解的类型签名``value` `=` `.enum Ljava``/``lang``/``annotation``/``RetentionPolicy;``-``>CLASS:Ljava``/``lang``/``annotation``/``RetentionPolicy;``/``/` `枚举类型，表示Retention注解的保留策略为CLASS``/``/` `.enum表示定义一个枚举类型``/``/` `Ljava``/``lang``/``annotation``/``RetentionPolicy表示RetentionPolicy枚举的类型签名``/``/` `-``>表示枚举类型的访问符``/``/` `CLASS表示RetentionPolicy枚举的一个值，表示注解保留在类文件中，但在运行时不可见``.end annotation``/``/` `注解定义结束` |
|-|-|

如果是方法或字段，".annotation"指令则会包含在方法或字段中定义。

注解方法，例如：

| 12345678910111213 | `.method public onTouch(Landroid``/``view``/``View;Landroid``/``view``/``MotionEvent;)Z``.``locals` `0``.annotation build Landroid``/``annotation``/``SuppressLint;``/``/` `定义一个编译时注解SuppressLint``/``/` `build表示该注解是Android SDK提供的注解``/``/` `Landroid``/``annotation``/``SuppressLint表示SuppressLint注解的类型签名``value` `=` `{``"ClickableViewAccessibility"``}``/``/` `定义注解的属性value，表示需要忽略的lint警告类型``/``/` `"ClickableViewAccessibility"``表示需要忽略的lint警告类型，即点击事件缺少无障碍支持``.end annotation``/``/` `注解定义结束` |
|-|-|

注解字段，例如：

| 123456789 | `.field public top:F``.annotation runtime Ljava``/``lang``/``Deprecated;``/``/` `定义一个运行时注解Deprecated``/``/` `runtime表示该注解在运行时可见，即可以通过反射获取该注解信息``/``/` `Ljava``/``lang``/``Deprecated表示Deprecated注解的类型签名``.end annotation``/``/` `注解定义结束` `.end field` |
|-|-|

到此Java和smali基础已经学习结束，接下来我们一起学习写一个简单的安卓APP，写完后我们一起把我们写的这个安卓APP逆向分析后破解掉，这样我们就会对安卓逆向和安卓开发之间的关系也有一定了解，并且也会提升我们的逆向水平。孙子曰：“知彼知己者，百战不殆；不知彼而知己，一胜一负，不知彼，不知己，每战必殆。”

那我们开始写一个简单的安卓APP吧！我们使用的工具是Android Studio，在写之前，我们需要安装Android Studio并创建一个项目：

安装Android Studio并创建项目可以参考这篇帖子：

[Android studio安装与创建第一个helloworld项目_安卓helloworld项目下载_王 三 二的博客-CSDN博客](https://blog.csdn.net/quickefficient/article/details/114633788)

但是我们不使用empty activity项目类型，而是使用empty views activity项目类型，因为我的empty activity项目类型的项目和网上的完全不一样，反而是empty views activity项目类型的项目和网上的empty activity项目类型的项目是一致的，所以我就创建empty views activity项目类型的项目了。

配置好环境后我们就来写一个简单的安卓APP，作用就是从主Activity跳转到我们创建的Activity。

写一个安卓APP与写一个网站颇有相似之处，第一步我们需要去编写布局文件，下面是主Activity布局的XML代码：

| 12345678910111213141516171819 | `<?``xml` `version``=``"1.0"` `encoding``=``"utf-8"``?>``<``LinearLayout` `xmlns:android``=``"http://schemas.android.com/apk/res/android"``android:layout_width``=``"match_parent"``android:layout_height``=``"match_parent"``android:orientation``=``"vertical"``android:gravity``=``"center"``>` `<``TextView``android:layout_width``=``"wrap_content"``android:layout_height``=``"wrap_content"``android:text``=``"Hello World!"` `/>` `<``Button``android:id``=``"@+id/skip"``android:layout_width``=``"wrap_content"``android:layout_height``=``"wrap_content"``android:text``=``"跳转"` `/>` `</``LinearLayout``>` |
|-|-|

让我们逐行解释每个元素的作用：

1. `<?xml version="1.0" encoding="utf-8"?>`：这是XML文件的声明，指定了文件的版本和编码。
2. `<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"`是根视图的开始标签，并使用`xmlns:android`属性定义了一个XML命名空间。这个命名空间是用来引用Android的命名空间，以便可以使用Android提供的特定属性和元素。
3. `android:layout_width="match_parent"`和`android:layout_height="match_parent"`：这两个属性设置根视图的宽度和高度为与父容器相匹配，即填充整个屏幕。
4. `android:orientation="vertical"`：这个属性指定了子视图在LinearLayout中的排列方向为垂直方向。
5. `android:gravity="center"`：这个属性指定了子视图在LinearLayout中的对齐方式为居中对齐。
6. `<TextView>`：这是一个TextView视图，用于显示文本内容。
7. `android:layout_width="wrap_content"`和`android:layout_height="wrap_content"`：这两个属性设置TextView的宽度和高度为根据内容自适应。
8. `android:text="Hello World!"`：这个属性设置TextView显示的文本内容为"Hello World!"。
9. `<Button>`：这是一个Button视图，用于显示按钮。
10. `android:id="@+id/skip"`：这个属性为Button指定了一个唯一的ID。
11. `android:layout_width="wrap_content"`和`android:layout_height="wrap_content"`：这两个属性设置Button的宽度和高度为根据内容自适应。
12. `android:text="跳转"`：这个属性设置Button显示的文本内容为"跳转"。
13. `</LinearLayout>`：这是LinearLayout的闭合标签，表示LinearLayout的定义结束。

既然我们需要从主Activity跳转到我们创建的Activity，那么第二步我们就创建我们自己的Activity，那自然需要先去编写布局文件，下面是我们需要创建的Activity的布局文件：

| 123456789101112 | `<?``xml` `version``=``"1.0"` `encoding``=``"utf-8"``?>``<``LinearLayout` `xmlns:android``=``"http://schemas.android.com/apk/res/android"``android:layout_width``=``"match_parent"``android:layout_height``=``"match_parent"``android:orientation``=``"vertical"``android:gravity``=``"center"``>` `<``TextView``android:layout_width``=``"wrap_content"``android:layout_height``=``"wrap_content"``android:text``=``"@string/my_activity1"``/>``</``LinearLayout``>` |
|-|-|

让我们逐行解释每个元素的作用：

1. `<?xml version="1.0" encoding="utf-8"?>`：这是XML文件的声明，指定了文件的版本和编码。
2. `<LinearLayout>`：这是根视图，使用了LinearLayout作为布局容器。
3. `xmlns:android="http://schemas.android.com/apk/res/android"`：这是Android命名空间的声明。
4. `android:layout_width="match_parent"`和`android:layout_height="match_parent"`：这两个属性设置根视图的宽度和高度为与父容器相匹配，即填充整个屏幕。
5. `android:orientation="vertical"`：这个属性设置LinearLayout的子视图在垂直方向上排列。
6. `android:gravity="center"`：这个属性设置LinearLayout的子视图在垂直和水平方向上居中对齐。
7. `<TextView>`：这是一个TextView视图，用于显示文本内容。
8. `android:layout_width="wrap_content"`和`android:layout_height="wrap_content"`：这两个属性设置TextView的宽度和高度根据内容自适应。
9. `android:text="@string/my_activity1"`：这个属性设置TextView显示的文本内容为字符串资源中的"my_activity1"。

这个Activity的需要显示字符串被我写到了res/values/strings.xml文件中：

| 1234 | `<``resources``>``<``string` `name``=``"app_name"``>My Application</``string``>``<``string` `name``=``"my_activity1"``>My First Activity</``string``>``</``resources``>` |
|-|-|

写完了我们需要创建的Activity布局文件，第三步我们需要在Java代码里面完成交互的逻辑编写：

```
package com.example.myapplication;

import android.os.Bundle;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

public class MyActivity extends AppCompatActivity {
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_my);
    }
}
```

让我们逐行解释每个元素的作用：

1. `public class MyActivity extends AppCompatActivity`：这是MyActivity类的定义，它继承自AppCompatActivity类。
2. `@Override`：这是一个注解，表示该方法是对父类方法的重写。
3. `protected void onCreate(@Nullable Bundle savedInstanceState)`：这是MyActivity类的onCreate()方法，它是活动的入口点，会在活动被创建时被调用。
4. `super.onCreate(savedInstanceState)`：这是调用父类的onCreate()方法，确保父类的初始化工作得到执行。
5. `setContentView(R.layout.activity_my)`：这个方法设置活动的布局文件为"activity_my.xml"，通过传入布局文件的资源ID来实现。

我们完成了我们自己创建的Activity在Java代码里面的交互逻辑编写，第四步是主Activity在Java代码里面的交互逻辑编写：

```
package com.example.myapplication;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        Button skip = findViewById(R.id.skip);
        skip.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent intent = new Intent();
                intent.setClass(MainActivity.this, MyActivity.class);
                startActivity(intent);
            }
        });
    }
}
```

让我们逐行解释每个元素的作用：

1. `public class MainActivity extends AppCompatActivity`：这是MainActivity类的定义，它继承自AppCompatActivity类。
2. `@Override`：这是一个注解，表示该方法是对父类方法的重写。
3. `protected void onCreate(Bundle savedInstanceState)`：这是MainActivity类的onCreate()方法，它是活动的入口点，会在活动被创建时被调用。
4. `super.onCreate(savedInstanceState)`：这是调用父类的onCreate()方法，确保父类的初始化工作得到执行。
5. `setContentView(R.layout.activity_main)`：这个方法设置活动的布局文件为"activity_main.xml"，通过传入布局文件的资源ID来实现。
6. `Button skip = findViewById(R.id.skip)`：这行代码通过调用findViewById()方法，找到布局文件中的Button视图，并将其实例化为名为"skip"的Button对象。
7. `skip.setOnClickListener(new View.OnClickListener() {...})`：这行代码为Button视图设置了一个点击事件的监听器，当用户点击按钮时，监听器中的代码会被执行。
8. `Intent intent = new Intent()`：这行代码创建了一个Intent对象，用于启动另一个活动。
9. `intent.setClass(MainActivity.this, MyActivity.class)`：这行代码设置Intent的目标活动为MyActivity类。
10. `startActivity(intent)`：这行代码启动了目标活动，即启动了MyActivity。

现在完成了主Activity在Java代码里面的交互逻辑编写，最后一步便是将我们自己编写的Activiity在应用清单文件中声明：

| 123456789101112131415161718192021222324252627 | `<?``xml` `version``=``"1.0"` `encoding``=``"utf-8"``?>``<``manifest` `xmlns:android``=``"http://schemas.android.com/apk/res/android"``xmlns:tools``=``"http://schemas.android.com/tools"``>` `<``application``android:allowBackup``=``"true"``android:dataExtractionRules``=``"@xml/data_extraction_rules"``android:fullBackupContent``=``"@xml/backup_rules"``android:icon``=``"@mipmap/ic_launcher"``android:label``=``"@string/app_name"``android:roundIcon``=``"@mipmap/ic_launcher_round"``android:supportsRtl``=``"true"``android:theme``=``"@style/Theme.MyApplication"``tools:targetApi``=``"31"``>``<``activity``android:name``=``".MainActivity"``android:exported``=``"true"``>``<``intent-filter``>``<``action` `android:name``=``"android.intent.action.MAIN"` `/>` `<``category` `android:name``=``"android.intent.category.LAUNCHER"` `/>``</``intent-filter``>``</``activity``>``<``activity` `android:name``=``".MyActivity"``/>``</``application``>` `</``manifest``>` |
|-|-|

到现在简单的安卓APP已经写完了，下面让我们看看我们自己编写的简单的安卓APP：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_83R9UDQAKPJ4PNB.png)

点击跳转后：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_4A9UC42VJ4E6CVZ.png)

从结果来看，这个简单的安卓APP是编写成功了。但是我们开发安卓APP还未结束，还需将APK进行打包才可以将其安装在手机或者模拟器上，Android Studio打包APK可以参考下面这篇文章：

[Android开发之打包APK详解_android打包apk_不服输的小乌龟的博客-CSDN博客](https://blog.csdn.net/qq_61963074/article/details/126513419)

将APK打包成功后便可以成功安装在我们自己的手机或者模拟器上了，到此我们自己写的这个简单的安卓APP也就编写完成了。

下一步我们需要将自己写的安卓APP逆向了做一件事情——>那就是替换掉点击跳转按钮后跳转的Activity。

首先软件逆向第一步找到关键代码的位置是重中之重，而我们要完成替换掉点击跳转按钮后跳转的Activity那首先需要先找到跳转按钮，如果我们需要找的内容并未写在Native层，没有被加密，也不是从服务器返回的，那就主要从这几个方向找：首先肯定是直接搜索字符串；其次通过工具获取到要找内容的资源ID后再去资源文件夹寻找相关的资源调用；还有就是通过一些相关的消息框、按钮等这些控件的调用代码来寻找位置；最次就是从程序入口处一步步往下追去寻得蛛丝马迹。

而我们写的安卓APP简单，后三者皆可使用，要问我为什么第一种在这不好使，那是因为显示在屏幕上的字符串全写在了资源文件中。这里我就打算使用最次的方法，因为我们写的这个简单，而且还好运用刚刚学会的smali汇编语言。

首先我们可以直接通过MT管理器的Activity记录功能直接获得入口点Activity的类名，然后便可搜索类名"com.example.myapplication.MainActivity"寻到以下内容：

| 12345678910111213141516171819202122232425262728293031323334353637383940414243444546474849505152535455 | `# classes3.dex` `.``class` `public Lcom``/``example``/``myapplication``/``MainActivity;``.``super` `Landroidx``/``appcompat``/``app``/``AppCompatActivity;``.source` `"MainActivity.java"`  `# direct methods` `.method public constructor <init>()V``.registers` `1` `.line` `10``invoke``-``direct {p0}, Landroidx``/``appcompat``/``app``/``AppCompatActivity;``-``><init>()V` `return``-``void` `.end method`  `# virtual methods` `.method protected onCreate(Landroid``/``os``/``Bundle;)V``.registers` `4``.param p1,` `"savedInstanceState"`  `# Landroid/os/Bundle;` `.line` `14``invoke``-``super` `{p0, p1}, Landroidx``/``appcompat``/``app``/``AppCompatActivity;``-``>onCreate(Landroid``/``os``/``Bundle;)V` `.line` `15``sget v0, Lcom``/``example``/``myapplication``/``R$layout;``-``>activity_main:I` `invoke``-``virtual {p0, v0}, Lcom``/``example``/``myapplication``/``MainActivity;``-``>setContentView(I)V` `.line` `16``sget v0, Lcom``/``example``/``myapplication``/``R$``id``;``-``>skip:I` `invoke``-``virtual {p0, v0}, Lcom``/``example``/``myapplication``/``MainActivity;``-``>findViewById(I)Landroid``/``view``/``View;` `move``-``result``-``object` `v0` `check``-``cast v0, Landroid``/``widget``/``Button;` `.line` `17``.local v0,` `"skip"``:Landroid``/``widget``/``Button;``new``-``instance v1, Lcom``/``example``/``myapplication``/``MainActivity$``1``;` `invoke``-``direct {v1, p0}, Lcom``/``example``/``myapplication``/``MainActivity$``1``;``-``><init>(Lcom``/``example``/``myapplication``/``MainActivity;)V` `invoke``-``virtual {v0, v1}, Landroid``/``widget``/``Button;``-``>setOnClickListener(Landroid``/``view``/``View$OnClickListener;)V` `.line` `25``return``-``void` `.end method` |
|-|-|

让我们逐行解释以上代码：

1. `.class public Lcom/example/myapplication/MainActivity;`：定义了一个公共类MainActivity，它位于com.example.myapplication包中。
2. `.super Landroidx/appcompat/app/AppCompatActivity;`：指定MainActivity的父类为AppCompatActivity类，这是一个支持兼容性的Android活动基类。
3. `.source "MainActivity.java"`：指定源代码文件为MainActivity.java。
4. `method public constructor <init>()V`：定义了MainActivity的构造函数。
5. `invoke-direct {p0}, Landroidx/appcompat/app/AppCompatActivity;-><init>()V`：调用父类AppCompatActivity的构造函数。
6. `method protected onCreate(Landroid/os/Bundle;)V`：定义了MainActivity的onCreate()方法，该方法在活动创建时被调用。
7. `invoke-super {p0, p1}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(Landroid/os/Bundle;)V`：调用父类AppCompatActivity的onCreate()方法。
8. `sget v0, Lcom/example/myapplication/R$layout;->activity_main:I`：获取activity_main布局资源的标识符，并将其存储在寄存器v0中。
9. `invoke-virtual {p0, v0}, Lcom/example/myapplication/MainActivity;->setContentView(I)V`：调用MainActivity的setContentView()方法，将activity_main布局设置为活动的内容视图。
10. `sget v0, Lcom/example/myapplication/R$id;->skip:I`：获取skip按钮的标识符，并将其存储在寄存器v0中。
11. `invoke-virtual {p0, v0}, Lcom/example/myapplication/MainActivity;->findViewById(I)Landroid/view/View;`：调用MainActivity的findViewById()方法，查找具有给定标识符的视图。
12. `move-result-object v0`：将查找到的视图对象存储在寄存器v0中。
13. `check-cast v0, Landroid/widget/Button;`：将寄存器v0中的对象强制转换为Button类型。
14. `new-instance v1, Lcom/example/myapplication/MainActivity$1;`：创建MainActivity$1的新实例，并将其存储在寄存器v1中。
15. `invoke-direct {v1, p0}, Lcom/example/myapplication/MainActivity$1;-><init>(Lcom/example/myapplication/MainActivity;)V`：调用MainActivity$1的构造函数，将MainActivity的实例作为参数传递。
16. `invoke-virtual {v0, v1}, Landroid/widget/Button;->setOnClickListener(Landroid/view/View$OnClickListener;)V`：调用Button的setOnClickListener()方法，将MainActivity$1的实例设置为按钮的点击监听器。
17. `return-void`：返回void类型。

分析完以上代码后，我们下一步就需要将我们要替换成的Activity的新布局文件给写出来。

| 1234567891011121314 | `<?``xml` `version``=``"1.0"` `encoding``=``"utf-8"``?>``<``LinearLayout` `xmlns:android``=``"http://schemas.android.com/apk/res/android"``android:layout_width``=``"match_parent"``android:layout_height``=``"match_parent"``android:orientation``=``"vertical"``>` `<``TextView``android:layout_width``=``"wrap_content"``android:layout_height``=``"wrap_content"``android:text``=``"Reverse the first software！"``android:textSize``=``"24sp"``android:layout_gravity``=``"center"` `/>` `</``LinearLayout``>` |
|-|-|

我并不打算去改Java代码，而是去添加一个布局文件供MyActivity类调用，你可能会问为什么不将这个布局文件替换掉原先的布局文件，这不是更加轻松吗？确实这样就不用去声明新添加资源的资源ID了，但是我们主要是要讲smali代码如何在实战中运用，当然要给smali代码多点戏份了。

点击跳转按钮后会触发MainActivityMainActivity1的实例，那下一步我们去看看MainActivity1的实例，那下一步我们去看看MainActivity1的实例：

| 123456789101112131415161718192021222324252627282930313233343536373839404142434445464748495051525354555657585960616263646566676869707172 | `# classes3.dex` `.``class` `Lcom``/``example``/``myapplication``/``MainActivity$``1``;``.``super` `Ljava``/``lang``/``Object``;``.source` `"MainActivity.java"` `# interfaces` `.implements Landroid``/``view``/``View$OnClickListener;`  `# annotations` `.annotation system Ldalvik``/``annotation``/``EnclosingMethod;``value` `=` `Lcom``/``example``/``myapplication``/``MainActivity;``-``>onCreate(Landroid``/``os``/``Bundle;)V``.end annotation` `.annotation system Ldalvik``/``annotation``/``InnerClass;``accessFlags` `=` `0x0``name` `=` `null``.end annotation`  `# instance fields` `.field final synthetic this$``0``:Lcom``/``example``/``myapplication``/``MainActivity;`  `# direct methods` `.method constructor <init>(Lcom``/``example``/``myapplication``/``MainActivity;)V``.registers` `2``.param p1,` `"this$0"`  `# Lcom/example/myapplication/MainActivity;` `.line` `17``iput``-``object` `p1, p0, Lcom``/``example``/``myapplication``/``MainActivity$``1``;``-``>this$``0``:Lcom``/``example``/``myapplication``/``MainActivity;` `invoke``-``direct {p0}, Ljava``/``lang``/``Object``;``-``><init>()V` `return``-``void` `.end method`  `# virtual methods` `.method public onClick(Landroid``/``view``/``View;)V``.registers` `5``.param p1,` `"v"`  `# Landroid/view/View;` `.line` `20``new``-``instance v0, Landroid``/``content``/``Intent;` `invoke``-``direct {v0}, Landroid``/``content``/``Intent;``-``><init>()V` `.line` `21``.local v0,` `"intent"``:Landroid``/``content``/``Intent;``iget``-``object` `v1, p0, Lcom``/``example``/``myapplication``/``MainActivity$``1``;``-``>this$``0``:Lcom``/``example``/``myapplication``/``MainActivity;` `const``-``class` `v2, Lcom``/``example``/``myapplication``/``MyActivity;` `invoke``-``virtual {v0, v1, v2}, Landroid``/``content``/``Intent;``-``>setClass(Landroid``/``content``/``Context;Ljava``/``lang``/``Class;)Landroid``/``content``/``Intent;` `.line` `22``iget``-``object` `v1, p0, Lcom``/``example``/``myapplication``/``MainActivity$``1``;``-``>this$``0``:Lcom``/``example``/``myapplication``/``MainActivity;` `invoke``-``virtual {v1, v0}, Lcom``/``example``/``myapplication``/``MainActivity;``-``>startActivity(Landroid``/``content``/``Intent;)V` `.line` `23``return``-``void` `.end method` |
|-|-|

让我们逐行解释以上代码：

1. `.class Lcom/example/myapplication/MainActivity$1;`：定义了名为`MainActivity$1`的类，它是`MainActivity`的内部类。
2. `.super Ljava/lang/Object;`：指定`MainActivity$1`类的父类为`java.lang.Object`。
3. `.source "MainActivity.java"`：指定源代码文件为MainActivity.java。
4. `.implements Landroid/view/View$OnClickListener;`：指定`MainActivity$1`类实现了`android.view.View.OnClickListener`接口。
5. `.annotation system Ldalvik/annotation/EnclosingMethod;`：指定该注解是关于封闭方法的。
6. `value = Lcom/example/myapplication/MainActivity;->onCreate(Landroid/os/Bundle;)V`：指定该内部类是在MainActivity的onCreate()方法内部定义的。
7. `.end annotation`：结束注解。
8. `.annotation system Ldalvik/annotation/InnerClass;`：指定该注解是关于内部类的。
9. `accessFlags = 0x0`：指定内部类的访问标志。
10. `name = null`：指定内部类的名称为空。
11. `.end annotation`：结束注解。
12. `.field final synthetic this$0:Lcom/example/myapplication/MainActivity;`：定义了一个名为`this$0`的final synthetic字段，类型为`com.example.myapplication.MainActivity`。这个字段用于引用外部类`MainActivity`的实例。
13. `.method constructor <init>(Lcom/example/myapplication/MainActivity;)V`：定义了`MainActivity$1`的构造函数。
14. `.registers 2`：指定该方法使用2个寄存器。
15. `.param p1, "this$0"`：指定构造函数的参数，命名为`this$0`，类型为`com.example.myapplication.MainActivity`。
16. `iput-object p1, p0, Lcom/example/myapplication/MainActivity$1;->this$0:Lcom/example/myapplication/MainActivity;`：将构造函数的参数`this$0`存储到`this$0`字段中。
17. `invoke-direct {p0}, Ljava/lang/Object;-><init>()V`：调用`java.lang.Object`的构造函数。
18. `return-void`：返回void类型。
19. `.method public onClick(Landroid/view/View;)V`：定义了`MainActivity$1`的onClick()方法，该方法在点击事件发生时被调用。
20. `.registers 5`：指定该方法使用5个寄存器。
21. `.param p1, "v"`：指定onClick()方法的参数，命名为`v`，类型为`android.view.View`。
22. `new-instance v0, Landroid/content/Intent;`：创建一个新的`Intent`实例，并将其存储在寄存器`v0`中。
23. `invoke-direct {v0}, Landroid/content/Intent;-><init>()V`：调用`Intent`的构造函数。
24. `.local v0, "intent":Landroid/content/Intent;`：将寄存器`v0`中的对象命名为`intent`。
25. `iget-object v1, p0, Lcom/example/myapplication/MainActivity$1;->this$0:Lcom/example/myapplication/MainActivity;`：获取`this$0`字段的值，并将其存储在寄存器`v1`中。
26. `const-class v2, Lcom/example/myapplication/MyActivity;`：将`com.example.myapplication.MyActivity`类的引用存储在寄存器`v2`中。
27. `invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClass(Landroid/content/Context;Ljava/lang/Class;)Landroid/content/Intent;`：调用`Intent`的`setClass()`方法，将`MainActivity`的实例和`com.example.myapplication.MyActivity`类作为参数传递。
28. `iget-object v1, p0, Lcom/example/myapplication/MainActivity$1;->this$0:Lcom/example/myapplication/MainActivity;`：再次获取`this$0`字段的值，并将其存储在寄存器`v1`中。
29. `invoke-virtual {v1, v0}, Lcom/example/myapplication/MainActivity;->startActivity(Landroid/content/Intent;)V`：调用`MainActivity`的`startActivity()`方法，将`intent`作为参数传递。
30. `return-void`：返回void类型。

分析完以上代码，我们可以去看看MyActivity类被反编译成smali代码后是什么样：

| 1234567891011121314151617181920212223242526272829303132333435363738 | `# classes3.dex` `.``class` `public Lcom``/``example``/``myapplication``/``MyActivity;``.``super` `Landroidx``/``appcompat``/``app``/``AppCompatActivity;``.source` `"MyActivity.java"`  `# direct methods` `.method public constructor <init>()V``.registers` `1` `.line` `8``invoke``-``direct {p0}, Landroidx``/``appcompat``/``app``/``AppCompatActivity;``-``><init>()V` `return``-``void` `.end method`  `# virtual methods` `.method protected onCreate(Landroid``/``os``/``Bundle;)V``.registers` `3``.param p1,` `"savedInstanceState"`  `# Landroid/os/Bundle;` `.line` `11``invoke``-``super` `{p0, p1}, Landroidx``/``appcompat``/``app``/``AppCompatActivity;``-``>onCreate(Landroid``/``os``/``Bundle;)V` `.line` `12``sget v0, Lcom``/``example``/``myapplication``/``R$layout;``-``>activity_my:I` `invoke``-``virtual {p0, v0}, Lcom``/``example``/``myapplication``/``MyActivity;``-``>setContentView(I)V` `.line` `13``return``-``void` `.end method` |
|-|-|

让我们逐行解释以上代码：

1. `.class public Lcom/example/myapplication/MyActivity;`：定义了一个公共类`com.example.myapplication.MyActivity`。
2. `.super Landroidx/appcompat/app/AppCompatActivity;`：指定该类继承自`androidx.appcompat.app.AppCompatActivity`。
3. `.source "MyActivity.java"`：指定该类的源文件为"MyActivity.java"。
4. `.method public constructor <init>()V`：定义了`MyActivity`的构造函数。
5. `.registers 1`：指定该方法使用1个寄存器。
6. `invoke-direct {p0}, Landroidx/appcompat/app/AppCompatActivity;-><init>()V`：调用`androidx.appcompat.app.AppCompatActivity`的构造函数。
7. `return-void`：返回void类型。
8. `.end method`：结束构造函数的定义。
9. `.method protected onCreate(Landroid/os/Bundle;)V`：定义了`MyActivity`的`onCreate()`方法，该方法在活动创建时被调用。
10. `.registers 3`：指定该方法使用3个寄存器。
11. `.param p1, "savedInstanceState" # Landroid/os/Bundle;`：指定`onCreate()`方法的参数，命名为`savedInstanceState`，类型为`android.os.Bundle`。
12. `invoke-super {p0, p1}, Landroidx/appcompat/app/AppCompatActivity;->onCreate(Landroid/os/Bundle;)V`：调用父类`onCreate()`方法。
13. `sget v0, Lcom/example/myapplication/R$layout;->activity_my:I`：获取`activity_my`布局的资源ID，并将其存储在寄存器`v0`中。
14. `invoke-virtual {p0, v0}, Lcom/example/myapplication/MyActivity;->setContentView(I)V`：调用`setContentView()`方法，将布局资源ID作为参数传递。
15. `return-void`：返回void类型。
16. `.end method`：结束`onCreate()`方法的定义。

因为我们是给这个类替换一个新的布局文件，所以我们先不改它，我们需要先去将新的布局文件声明好，这我们需要做三件事情：

第一件：将新的布局文件丢res/layout文件夹里去；

第二件：在values\public.xml文件中声明我们新的布局文件的资源ID；

第三件：在R$layout类中声明我们新的布局文件的资源ID；

我们完成以上步骤后，我们需要将MyActivity类中的activity_my替换成activity_new：

| 1 | `sget v0, Lcom``/``example``/``myapplication``/``R$layout;``-``>activity_new:I` |
|-|-|

以上寄存器要联系上下文，比如以上代码是将`activity_new`布局的资源ID储在寄存器`v0`中，再将v0寄存器中的资源ID作为参数传递给`setContentView`方法。所以寄存器要联系上下文，不要直接复制粘贴。

然后回编译成功后，再使用MT管理器对修改后的apk文件进行重新签名，让我们来看看最终的结果如何：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_NDA5P2JX48W35CK.png)

点击跳转后：

 ![image](https://bbs.kanxue.com/upload/attach/202308/926486_H29Q3B78T5PNK42.png)

从结果来看我们成功完成了替换掉点击跳转按钮后跳转的Activity！现在这篇文章也到此结束，这篇文章重点是让大家对Java基础、smali汇编基础、安卓开发基础有简单的了解，最后还是那句话：“知彼知己者，百战不殆；不知彼而知己，一胜一负，不知彼，不知己，每战必殆。”

上传的附件：
- My Application.apk

（3.09MB，18次下载）

---

# 回复

## 回复 by 秋狝 (#2)

*2023-8-24 14:13*

感谢分享

## 回复 by 院士 (#3)

*2023-8-25 12:51*

收藏学习。

## 回复 by 微微T52G25 (#4)

*2023-8-25 15:46*

写的挺好的，感谢

## 回复 by mb_ecsiujxp (#5)

*2023-8-28 08:53*

收藏了

## 回复 by yangtt57 (#6)

*2024-2-23 23:31*

非常适合入门者学习，感谢！

## 回复 by 椰子汁 (#7)

*2024-2-27 16:47*

抽象类的例子里少了个getName方法

## 回复 by 黎明与黄昏 (#8)

*2024-2-28 22:22*

>
> [![image](https://bbs.kanxue.com/view/img/avatar.png)
>
>  椰子汁](https://bbs.kanxue.com/user-972877.htm)
>
>  抽象类的例子里少了个getName方法
>
>

我的疏忽，确实少了个getName方法，感谢提醒![image](https://bbs.kanxue.com/view/img/face/63.gif)

## 回复 by Samwe (#9)

*2024-11-7 21:04*

不错，学习了

## 回复 by 黎明与黄昏 (#10)

*2025-8-29 11:45*

其中“wide”表示数据宽度为64位，“from16”表示源寄存器为一个16位寄存器引用，vAA表示目标寄存器，它的取值范围是v0v65535。
这一段有缺失，发布出来和编辑时结果不同存在缺失，原意为：
其中“wide”表示数据宽度为64位，“from16”表示源寄存器为一个16位寄存器引用，vAA表示目标寄存器，它的取值范围是v0~v255，vBBBB表示源寄存器，它的取值范围是v0~v65535。
