---
title: '[原创]Frida源码分析之frida-core篇'
url: https://bbs.kanxue.com/thread-291156.htm
tid: 291156
author: gal2xy
date: '2026-05-09'
tags: [Android安全, 原创]
crawled_at: '2026-07-31T13:53:02+08:00'
replies: 1
---

本文分析的是`frida-core`源码，其中很多关键代码使用vala语言编写，再借助编译器转换成C语言代码。`frida-core` 封装了跨平台通信、进程管理和注入逻辑，包含如下关键模块：

- `frida-server`：运行在目标设备（如安卓、iOS）上，负责接收来自 PC 端的指令。
- `frida-agent`：注入到目标App的一个共享库，负责与`frida-server`通信，执行hook工作。
- `frida-gadget`：一个共享库。在无法获取 Root 权限的情况下，通过将此库集成到 App 中来实现自注入。

# frida-server

frida-server的启动入口在`server/server.vala`文件中。

```
private static int main (string[] args) {
    //初始化运行环境
    Environment.init ();

    ...

    Environment.configure ();

    ...
    return run_application (device_id, endpoint_params, options, on_ready);
}
```

解析参数，初始化运行环境，最终调用`run_application()`启动`frida-server`。

```
private static int run_application (string? device_id, EndpointParameters endpoint_params, ControlServiceOptions options, ReadyHandler on_ready) {
    //设置临时目录，这个目录用于存放 Frida 运行时需要落地的临时二进制、资源等文件。
    TemporaryDirectory.always_use ((directory != null) ? directory : DEFAULT_DIRECTORY);
    TemporaryDirectory.use_sysroot (options.sysroot);
    // 创建frida-server的application
    application = new Application (device_id, endpoint_params, options);

    ...

    return application.run ();
}
```

设置临时目录，用于存放 Frida 运行时需要落地的临时二进制、资源等文件，默认目录名为`re.frida.server`。然后创建`Application`对象并调用其`run()`方法。

`Application`的定义在 `server/server.vala` 265行处。

```
public int run () {
    Idle.add (() => {
        start.begin ();
        return false;
    });

    exit_code = 0;

    loop.run ();

    return exit_code;
}
```

先把“启动服务”的异步任务投递到 GLib 主循环，然后进入主循环，让主循环去调度并驱动这个任务。因此真正启动服务的逻辑不在 `run()` 里，而是在它调度的 `start()` 方法里：

```
private async void start () {
    try {
        if (device_id != null && device_id != "local") {// 非本地设备
            // 创建设备管理对象
            manager = new DeviceManager.with_nonlocal_backends_only ();
            // 查找设备，监听设备丢失事件
            var device = yield manager.get_device_by_id (device_id, 0, io_cancellable);
            device.lost.connect (on_device_lost);
            // 基于指定设备创建控制服务
            service = yield new ControlService.with_device (device, endpoint_params, options);
        } else {
            // 创建一个直接服务当前机器/当前进程环境的 ControlService
            service = new ControlService (endpoint_params, options);
        }
        // ControlService的start方法
        yield service.start (io_cancellable);
    }
    ...
}
```

这里如果`frida-server`启动时没有指定`--device`，就会调用`new ControlService()`创建`ControlService`实例，并调用它的`start()`方法。该类定义在 `src/control-service.vala` 中，`ControlService`的初始化函数如下：

```
public ControlService (EndpointParameters endpoint_params, ControlServiceOptions? options = null) throws Error {
#if HAVE_LOCAL_BACKEND
    ControlServiceOptions opts = (options != null) ? options : new ControlServiceOptions ();

    HostSession session;
    //...
#if LINUX
    // 创建临时目录
    var tempdir = new TemporaryDirectory ();
    // 创建 LinuxHostSession
    session = new LinuxHostSession (new LinuxHelperProcess (tempdir), tempdir, opts.report_crashes);
#endif
    //...
    Object (
        endpoint_params: endpoint_params,
        options: opts
    );
    // 把HostSession注册到ControlService中，并连接各种信号。
    assign_session (session, new PrecreatedLocalHostSessionProvider ((LocalHostSession) session));
    //...
}
```

创建临时目录，接着创建`LinuxHostSession`并调用`assign_session()`把它注册到`ControlService`中，以及连接各种信号。`LinuxHostSession` 是本地 Frida 功能的核心入口之一，提供了应用枚举、进程枚举、进程注入、进程启动等功能。

现在回到`ControlService.start()`方法中。

```
public async void start (Cancellable? cancellable = null) throws Error, IOError {
    if (state != STOPPED)
        throw new Error.INVALID_OPERATION ("Invalid operation");
    state = STARTING;

    main_context = MainContext.ref_thread_default ();
    // 此处的service是WebService
    // 监听 WebService 的新连接
    // 当有 Frida 客户端连接到 server 时，会触发 incoming 信号，然后调用 on_server_connection 处理连接。
    service.incoming.connect (on_server_connection);

    try {
        // 让 frida-server 开始监听控制端口，并准备接收客户端 WebSocket/DBus 连接
        yield service.start (cancellable);

        if (options.enable_preload) {
            var base_host_session = host_session as LocalHostSession;
            if (base_host_session != null)
                base_host_session.preload.begin (io_cancellable);
        }

        state = STARTED;
    } finally {
        if (state != STARTED)
            state = STOPPED;
    }
}
```

此处的`service`是`WebService`，这里给 `WebService.incoming` 信号绑定 `on_server_connection()`函数。当有 Frida 客户端连接到 `frida-server`时，会调用该绑定函数。接下来通过`service.start()`启动`WebService`，该函数定义在`lib\base\socket.vala` 237行处。

```
public async void start (Cancellable? cancellable) throws Error, IOError {
    frida_context = MainContext.ref_thread_default ();
    dbus_context = yield get_dbus_context ();//获取 DBus 线程上下文

    cancellable.set_error_if_cancelled ();

    var start_request = new Promise<SocketAddress> ();
    schedule_on_dbus_thread (() => {
        // 把真正的启动逻辑调度到 DBus 线程执行
        handle_start_request.begin (start_request, cancellable);
        return Source.REMOVE;
    });
    // 保存监听地址
    _listen_address = yield start_request.future.wait_async (cancellable);
}
```

`handle_start_request()`会继续调用 `do_start()`，里面会解析监听地址，默认情况下是`127.0.0.1:27042`，之后`WebService` 内部的 `ConnectionHandler` 会创建 Soup server，并注册 WebSocket 路径 `/ws`，客户端脸上 `/ws`后，触发`incoming`信号，回调之前注册的`on_server_connection()`

```
private void on_server_connection (IOStream connection, SocketAddress remote_address, DynamicInterface? dynamic_iface) {
    //...
    ConnectionHandler handler;
    unowned string iface_name = dynamic_iface?.name;
    if (iface_name != null) {
        handler = dynamic_interface_handlers[iface_name];
        if (handler == null) {
            handler = new ConnectionHandler (this, dynamic_iface);
            dynamic_interface_handlers[iface_name] = handler;
        }
    } else {
        handler = main_handler;
    }

    handler.handle_server_connection.begin (connection);
}
```

这里视情况选择不同的`ConnectionHandler`，然后调用`handle_server_connection()`启动该连接的 DBus/认证处理流程。

```
public async void handle_server_connection (IOStream raw_connection) throws GLib.Error {
    // 把IOStream包装成DBus通信
    var connection = yield new DBusConnection (raw_connection, null, DELAY_MESSAGE_PROCESSING, null,
                                               io_cancellable);
    connection.on_closed.connect (on_connection_closed);
    // 根据有无鉴权选择不同的Channel
    AuthenticationService? auth_service = parent.endpoint_params.auth_service;
    peers[connection] = (auth_service != null)
        ? (Peer) new AuthenticationChannel (this, connection, auth_service)
        : (Peer) new ControlChannel (this, connection);
    // 启动 DBus 消息处理
    connection.start_message_processing ();
}
```

把`IOStream`包装成`DBusConnection`。有鉴权的情况下（比如说配置了token参数）创建`AuthenticationChannel`，只有认证成功后才能升级为`ControlChannel`，无鉴权的情况下创建`ControlChannel`，能直接调用 `HostSession` 的 `spawn/attach/kill/...` 等方法。

# 进程注入

`frida-server`启动之后，接下来就是`spawn/attach`模式附加到目标进程中。`spawn`模式下启动目标程序后，并没有进行agent的注入，反而是后续调用`attach`进行注入的。这部分可以参考`frida-tools`项目，在`\frida_tools\application.py` 607行处：

```python
elif target_type == "file":
    argv = target_value
    if not self._quiet:
        self._update_status(f"Spawning `{' '.join(argv)}`...")

    aux_kwargs = {}
    if self._aux is not None:
        aux_kwargs = dict([parse_typed_option(o) for o in self._aux])
    # spawn获取pid
    self._spawned_pid = self._device.spawn(argv, stdio=self._stdio, **aux_kwargs)
    self._spawned_argv = argv
    attach_target = self._spawned_pid
else:
    attach_target = target_value
    if not isinstance(attach_target, numbers.Number):
        # attach获取pid
        attach_target = self._device.get_process(attach_target).pid
    if not self._quiet:
        self._update_status("Attaching...")
spawning = False
# 调用_attach
self._attach(attach_target)
```

他们最终都是通过`perform_attach_to()`函数实现`frida-agent`注入的，代码路径在`src\linux\linux-host-session.vala` 387行处。

```
protected override async Future<IOStream> perform_attach_to (uint pid, HashTable<string, Variant> options,
                                                             Cancellable? cancellable, out Object? transport) throws Error, IOError {
    uint id;
    string entrypoint = "frida_agent_main";
    string parameters = make_agent_parameters (pid, "", options);
    AgentFeatures features = CONTROL_CHANNEL;
    var linjector = (Linjector) injector;
    // frida-agent注入
#if HAVE_EMBEDDED_ASSETS
    id = yield linjector.inject_library_resource (pid, agent, entrypoint, parameters, features, cancellable);
#else
    id = yield linjector.inject_library_file_with_template (pid, PathTemplate (Config.FRIDA_AGENT_PATH), entrypoint,
                                                            parameters, features, cancellable);
#endif
    injectee_by_pid[pid] = id;

    var stream_request = new Promise<IOStream> ();
    IOStream stream = yield linjector.request_control_channel (id, cancellable);
    stream_request.resolve (stream);

    transport = null;

    return stream_request.future;
}
```

先解释一下`HAVE_EMBEDDED_ASSETS`宏定义，当它为真时，在编译时 Frida 时会将`frida-agent.so`嵌入到 `frida-core`中，然后在运行时将内置的 agent 释放出来并使用，这部分在`src\linux\linux-host-session.vala` 62行处。

```
#if HAVE_EMBEDDED_ASSETS
    var blob32 = Frida.Data.Agent.get_frida_agent_32_so_blob ();
    var blob64 = Frida.Data.Agent.get_frida_agent_64_so_blob ();
    var emulated_arm = Frida.Data.Agent.get_frida_agent_arm_so_blob ();
    var emulated_arm64 = Frida.Data.Agent.get_frida_agent_arm64_so_blob ();
    agent = new AgentDescriptor (PathTemplate ("frida-agent-<arch>.so"),
                new Bytes.static (blob32.data),
                new Bytes.static (blob64.data),
                new AgentResource[] {
                    new AgentResource ("frida-agent-arm.so", new Bytes.static (emulated_arm.data), tempdir),
                    new AgentResource ("frida-agent-arm64.so", new Bytes.static (emulated_arm64.data), tempdir),
                },
                AgentMode.INSTANCED,
                tempdir);
#endif
```

回到`perform_attach_to()`函数中，它的代码逻辑是通过 `Linjector` 注入 `frida-agent.so`，注入成功后通过 `request_control_channel()` 获取与目标进程内 agent 通信的 `IOStream`。根据`HAVE_EMBEDDED_ASSETS`宏定义，调用了`Linjector`的不同方法，具体如下：

```
// src\linux\linjector.vala L84
public async uint inject_library_resource (uint pid, AgentDescriptor agent, string entrypoint, string data,
                                           AgentFeatures features, Cancellable? cancellable) throws Error, IOError {
    // 系统支持memfd（匿名内存文件）
    if (MemoryFileDescriptor.is_supported ()) {
        // 优先走内存文件描述符方式。memfd 可以创建一个匿名内存文件，不需要把 .so 真正落地到普通磁盘路径。
        unowned string arch_name = arch_name_from_pid (pid);
        // 根据架构构建agent名称并从内嵌资源中查找
        string name = agent.name_template.expand (arch_name);
        AgentResource? resource = agent.resources.first_match (r => r.name == name);
        if (resource == null) {
            throw new Error.NOT_SUPPORTED ("Unable to handle %s-bit processes due to build configuration",
                                           arch_name);
        }
        // 把内嵌 agent 资源转换成 memfd，然后交给 inject_library_fd() 注入目标进程。
        return yield inject_library_fd (pid, resource.get_memfd (), entrypoint, data, features, cancellable);
    }
    // 系统不支持memfd
    ensure_tempdir_prepared ();//准备临时目录
    // 与HAVE_EMBEDDED_ASSETS为false的情况相同
    // 通过 agent.get_path_template() 把内嵌 agent 写成临时 .so 文件，再按文件路径方式注入。
    return yield inject_library_file_with_template (pid, agent.get_path_template (), entrypoint, data, features,
                                                    cancellable);
}
// src\linux\linjector.vala L48
public async uint inject_library_file_with_template (uint pid, PathTemplate path_template, string entrypoint, string data,
                                                     AgentFeatures features, Cancellable? cancellable) throws Error, IOError {
    string path = path_template.expand (arch_name_from_pid (pid));
    // 打开agent文件
    int fd = Posix.open (path, Posix.O_RDONLY);
    if (fd == -1)
        throw new Error.INVALID_ARGUMENT ("Unable to open library: %s", strerror (errno));
    var library_so = new UnixInputStream (fd, true);
    // 最终调用inject_library_fd()
    return yield inject_library_fd (pid, library_so, entrypoint, data, features, cancellable);
}
```

最终调用的都是`inject_library_fd`函数

```
public async uint inject_library_fd (uint pid, UnixInputStream library_so, string entrypoint, string data,
                                     AgentFeatures features, Cancellable? cancellable) throws Error, IOError {
    uint id = next_injectee_id++;
    yield helper.inject_library (pid, library_so, entrypoint, data, features, id, cancellable);

    pid_by_id[id] = pid;

    return id;
}
```

调用的是helper的`inject_library()`方法，代码位于`src\linux\frida-helper-backend.vala` 300行处。

```
public async void inject_library (uint pid, UnixInputStream library_so, string entrypoint, string data,
                                  AgentFeatures features, uint id, Cancellable? cancellable) throws Error, IOError {
    var spec = new InjectSpec (library_so, entrypoint, data, features, id);
    var task = new InjectTask (this, spec);
    RemoteAgent agent = yield perform (task, pid, cancellable);
    take_agent (agent);
}
```

`perform()`函数最终调用的是`InjectTask`对象的`run()`方法

```
public async RemoteAgent run (uint pid, Cancellable? cancellable) throws Error, IOError {
    PausedSyscallSession? pss = backend.paused_syscalls[pid];
    if (pss != null)
        yield pss.interrupt (cancellable);
       // 重点
    var session = yield InjectSession.open (pid, cancellable);
    RemoteAgent agent = yield session.inject (spec, cancellable);
    if (session.was_group_stopped)
        backend.suspended_by_inject[pid] = session;
    else
        session.close ();
    return agent;
}
```

`InjectSession.open()` 会通过 `ptrace` attach 到目标进程并保存寄存器状态。然后 `session.inject()` 才是真正做注入工作的。

`InjectSession.open()`调用链：

```python
InjectSession.open(pid)
    -> SeizeSession.init_async()
        -> ptrace(SEIZE/ATTACH)
        -> 中断/等待目标线程停止
        -> get_regs(&saved_regs)
```

`InjectSession.inject()`代码位于`src\linux\frida-helper-backend.vala` 880行处。

```
public async RemoteAgent inject (InjectSpec spec, Cancellable? cancellable) throws Error, IOError {
    string fallback_address = make_fallback_address ();
    // 计算要写入目标进程的内存布局
    LoaderLayout loader_layout = compute_loader_layout (spec, fallback_address);
    // 在目标进程里分配一块可执行内存
    BootstrapResult bootstrap_result = yield bootstrap (loader_layout.size, cancellable);
    uint64 loader_base = (uintptr) bootstrap_result.context.allocation_base;// 远程调用入口

    try {
        // 取出 Frida 预编译的 loader 机器码，对应的是 src/linux/helpers/loader.c 编译出来的小型加载器
        unowned uint8[] loader_code = Frida.Data.HelperBackend.get_loader_bin_blob ().data;
        // 把 loader 写进目标进程内存
        write_memory (loader_base, loader_code);
        maybe_fixup_helper_code (loader_base, loader_code);// 做架构相关修正，例如重定位
        // 构造loader的上下文（运行参数）
        var loader_ctx = HelperLoaderContext ();
        loader_ctx.ctrlfds = bootstrap_result.context.ctrlfds;
        loader_ctx.agent_entrypoint = (string *) (loader_base + loader_layout.agent_entrypoint_offset);
        loader_ctx.agent_data = (string *) (loader_base + loader_layout.agent_data_offset);
        loader_ctx.fallback_address = (string *) (loader_base + loader_layout.fallback_address_offset);
        loader_ctx.libc = (HelperLibcApi *) (loader_base + loader_layout.libc_api_offset);
        // 相关值写入
        write_memory (loader_base + loader_layout.ctx_offset, (uint8[]) &loader_ctx);
        write_memory (loader_base + loader_layout.libc_api_offset, (uint8[]) &bootstrap_result.libc);
        write_memory_string (loader_base + loader_layout.agent_entrypoint_offset, spec.entrypoint);
        write_memory_string (loader_base + loader_layout.agent_data_offset, spec.data);
        write_memory_string (loader_base + loader_layout.fallback_address_offset, fallback_address);
        // 远程执行loader
        return yield launch_loader (FROM_SCRATCH, spec, bootstrap_result, null, fallback_address, loader_layout,
                                    cancellable);
    }
    //...
}
```

注入loader到目标进程中，然后通过`launch_loader`远程启动它，让它完成 `frida-agent`的加载和入口调用。

```
private async RemoteAgent launch_loader (LoaderLaunch launch, InjectSpec spec, BootstrapResult bres, UnixConnection? agent_ctrl, string fallback_address, LoaderLayout loader_layout, Cancellable? cancellable) throws Error, IOError {
    // 与 helper建立通信连接
    Future<RemoteAgent> future_agent =
        establish_connection (launch, spec, bres, agent_ctrl, fallback_address, cancellable);
    // 构造 loader 调用环境
    uint64 loader_base = (uintptr) bres.context.allocation_base;// loader入口地址
    GPRegs regs = saved_regs;//被ptrace stop时保存的目标进程寄存器
    regs.stack_pointer = bres.allocated_stack.stack_root;//更改栈指针指向新分配的栈
    var call_builder = new RemoteCallBuilder (loader_base, regs);// 构建远程调用构建器, 从loader_base开始执行
    call_builder.add_argument (loader_base + loader_layout.ctx_offset);// 添加参数，类型为HelperLoaderContext*
    RemoteCall loader_call = call_builder.build (this);// 构建远程调用
    RemoteCallResult loader_result = yield loader_call.execute (cancellable);// 执行远程调用
    // ...

    var establish_cancellable = new Cancellable ();
    var main_context = MainContext.get_thread_default ();

    var timeout_source = new TimeoutSource.seconds (5);
    timeout_source.set_callback (() => {
        establish_cancellable.cancel ();
        return Source.REMOVE;
    });
    timeout_source.attach (main_context);

    var cancel_source = new CancellableSource (cancellable);
    cancel_source.set_callback (() => {
        establish_cancellable.cancel ();
        return Source.REMOVE;
    });
    cancel_source.attach (main_context);

    RemoteAgent agent = null;
    try {
        agent = yield future_agent.wait_async (establish_cancellable);
    }
    // ...

    agent.ack ();//发送 ACK，允许 loader 进入 agent main

    return agent;
}
```

构造loader入口函数的远程调用，让目标进程自己执行 loader 代码。之后的代码逻辑就是在`src\linux\helpers\loader.c`中，入口是`frida_load()`，里面通过线程启动`frida_main()`方法，在后者中，通过`dlopen()` 加载 agent，通过 `dlsym()` 找到 `frida_agent_main`，最后调用 agent 入口函数。

# frida-agent

在上节中， `perform_attach_to()`函数指定了注入动态库后执行的函数符号为 `frida_agent_main`，该函数的定义在 `lib/agent/agent.vala` 中：

```
public void main (string agent_parameters, ref Frida.UnloadPolicy unload_policy, void * injector_state) {
    if (Runner.shared_instance == null)// Runner.shared_instance初始化为null
        Runner.create_and_run (agent_parameters, ref unload_policy, injector_state);
    else
        Runner.resume_after_transition (ref unload_policy, injector_state);
}
```

首次启动时调用`Runner.create_and_run()`初始化agent并运行。

```
public static void create_and_run (string agent_parameters, ref Frida.UnloadPolicy unload_policy,
                                   void * opaque_injector_state) {
    // 初始化 agent 运行环境
    Environment._init ();

    {
        Gum.MemoryRange? mapped_range = null;
        //...

        if (cached_agent_path == null) {
            // 找出当前 agent.so 在目标进程中的内存范围和路径，进行缓存
            cached_agent_range = detect_own_range_and_path (mapped_range, out cached_agent_path);
            Gum.Cloak.add_range (cached_agent_range);
        }
        // 获取文件描述符表
        var fdt_padder = FileDescriptorTablePadder.obtain ();

#if LINUX || FREEBSD
        var injector_state = (PosixInjectorState *) opaque_injector_state;
        if (injector_state != null) {
            fdt_padder.move_descriptor_if_needed (ref injector_state.fifo_fd);
            Gum.Cloak.add_file_descriptor (injector_state.fifo_fd);
        }
#endif

#if LINUX
        var linjector_state = (LinuxInjectorState *) opaque_injector_state;
        string? agent_parameters_with_transport_uri = null;
        if (linjector_state != null) {
            int agent_ctrlfd = linjector_state->agent_ctrlfd;
            //-1表示所有权已经转移给agent
            linjector_state->agent_ctrlfd = -1;

            fdt_padder.move_descriptor_if_needed (ref agent_ctrlfd);
            //构建参数，后面 Runner.start() 会解析它，用这个 fd 建立 DBus 通信
            agent_parameters_with_transport_uri = "socket:%d%s".printf (agent_ctrlfd, agent_parameters);
            agent_parameters = agent_parameters_with_transport_uri;
        }
#endif

        var ignore_scope = new ThreadIgnoreScope (FRIDA_THREAD);
        // 创建全局单例Runner
        shared_instance = new Runner (agent_parameters, cached_agent_path, cached_agent_range);

        try {
            // 启动Runner
            shared_instance.run ((owned) fdt_padder);
        } catch (Error e) {
            GLib.info ("Unable to start agent: %s", e.message);
        }
        //...
        ignore_scope = null;
    }

    Environment._deinit ();
}
```

初始化 agent 环境，构建资源标识符`uri`为 `socket:<fd><parameters>` 格式，然后创建全局单例 `Runner`，并调用`run()`方法启动。

```
private void run (owned FileDescriptorTablePadder padder) throws Error {
    main_context.push_thread_default ();
    // 调用自身的start()方法
    start.begin ((owned) padder);
    // 开启主循环阻塞，处理事件
    main_loop.run ();

    main_context.pop_thread_default ();

    if (start_error != null)
        throw start_error;
}
```

启动异步函数 `start()`，该函数负责真正初始化agent。

```
private async void start (owned FileDescriptorTablePadder padder) {
    // agent_parameters的格式为 "socket:%d%s"
    string[] tokens = agent_parameters.split ("|");
    unowned string transport_uri = tokens[0]; // socket:<fd>，例如socket:123
    bool enable_exceptor = true;// 异常处理/异常拦截相关能力

    bool enable_exit_monitor = true;// 监控进程退出、exec 等终止行为
    bool enable_thread_suspend_monitor = true;// 监控线程挂起相关行为
    bool enable_unwind_sitter = true;// 栈回溯/异常恢复辅助相关组件
    // 遍历启动参数，设置启动选项
    foreach (unowned string option in tokens[1:]) {
        if (option == "eternal")
            ensure_eternalized ();
        else if (option == "sticky")
            stop_thread_on_unload = false;
        else if (option == "exceptor:off")
            enable_exceptor = false;
        else if (option == "exit-monitor:off")
            enable_exit_monitor = false;
        else if (option == "thread-suspend-monitor:off")
            enable_thread_suspend_monitor = false;
        else if (option == "unwind-sitter:off")
            enable_unwind_sitter = false;
    }

    if (!enable_exceptor)
        Gum.Exceptor.disable ();
    // 根据启动选项，初始化相关组件
    {
        var interceptor = Gum.Interceptor.obtain ();
        interceptor.begin_transaction ();

        if (enable_exit_monitor)
            exit_monitor = new ExitMonitor (this, main_context);

        if (enable_thread_suspend_monitor)
            thread_suspend_monitor = new ThreadSuspendMonitor (this);

        if (enable_unwind_sitter)
            unwind_sitter = new UnwindSitter (this);

        this.interceptor = interceptor;
        this.exceptor = Gum.Exceptor.obtain ();

        interceptor.end_transaction ();
    }
    // 用传入的 Unix socket fd 建立通信连接
    try {
        yield setup_connection_with_transport_uri (transport_uri);
    } catch (Error e) {
        start_error = e;
        main_loop.quit ();
        return;
    }

    Gum.ScriptBackend.get_scheduler ().push_job_on_js_thread (Priority.DEFAULT, () => {
        schedule_idle (start.callback);
    });
    yield;

    padder = null;
}
```

解析 agent 启动参数，启用/禁用关键监控组件，调用`setup_connection_with_transport_uri()`函数建立与 `frida-server` 的 DBus 通信连接，最后切换到 JS 线程完成一次调度同步，确保JS 线程已经初始化到可用状态。

```
private async void setup_connection_with_transport_uri (string transport_uri) throws Error {
    IOStream stream;// 双向输入输出流。后续 DBusConnection 会基于这个流进行通信
    try {
        if (transport_uri.has_prefix ("socket:")) {
            // 取出文件描述符fd，建立socket通信
            var socket = new Socket.from_fd (int.parse (transport_uri[7:]));
            stream = SocketConnection.factory_create_connection (socket);
        } else if (transport_uri.has_prefix ("pipe:")) {
            stream = yield Pipe.open (transport_uri, null).wait_async (null);
        } else {
            throw new Error.INVALID_ARGUMENT ("Invalid transport URI: %s", transport_uri);
        }
    } catch (GLib.Error e) {
        if (e is Error)
            throw (Error) e;
        throw new Error.TRANSPORT ("%s", e.message);
    }
    // 基于stream创建DBusConnection
    yield setup_connection_with_stream (stream);
}
```

Android 上主要走 `socket:<fd>` 分支，把注入阶段传入的 Unix socket fd 包装成 `IOStream`通信流，然后再交给 `setup_connection_with_stream()` 用于建立 DBus 通信。

```
private async void setup_connection_with_stream (IOStream stream) throws Error {
    try {
        // 用传入的 IOStream 建立一条 DBus 连接
        connection = yield new DBusConnection (stream, null, AUTHENTICATION_CLIENT | DELAY_MESSAGE_PROCESSING);
        connection.on_closed.connect (on_connection_closed);// 注册关闭回调
        filter_id = connection.add_filter (on_connection_message); // 给 DBus 消息加过滤器
        // 注册 AgentSessionprovider。注册后，宿主端就可以通过 DBus 调用 agent 的方法
        AgentSessionProvider provider = this;
        registration_id = connection.register_object (ObjectPath.AGENT_SESSION_PROVIDER, provider);
        // 获取宿主端 controller proxy。这个 controller 是 agent 反向调用 frida-server/helper 的接口
        controller = yield connection.get_proxy (null, ObjectPath.AGENT_CONTROLLER, DO_NOT_LOAD_PROPERTIES, null);
        // 开始处理 DBus 消息
        connection.start_message_processing ();
    } catch (GLib.Error e) {
        throw new Error.TRANSPORT ("%s", e.message);
    }
}
```

基于 `IOStream` 建立 DBus 通道。然后把当前 `Runner` 注册成 `AgentSessionProvider`，这样`frida-server`就可以通过 DBus 通信调用 agent 的方法。之后通过 DBus 通信获取`frida-server`的`AgentController`代理，这样`frida-agent`也同样可以通过 DBus 通信反向调用`frida-server`的方法。

# frida-gadget

Frida的Gadget是一个共享库，用于免root注入hook脚本。frida持久化是借助`frida-gadget`来进行的，主要方式有App重打包、源码定制等，详细分析可见[[原创]小菜花的frida-gadget持久化方案汇总](https://bbs.kanxue.com/thread-268256-1.htm)。

`frida-gadget`的入口函数在`lib\gadget\gadget.vala` 379行处。

```
public void load (Gum.MemoryRange? mapped_range, string? config_data, int * result) {
    // ...

    // Location 包含当前可执行文件名、Gadget 路径、模块内存范围，以及 asset 目录解析能力。后续脚本路径、证书路径、配置路径都会基于它解析相对路径。
    location = detect_location (mapped_range);
    // 读取gadget配置文件
    try {
        config = (config_data != null)
            ? parse_config (config_data)
            : load_config (location);
    } catch (Error e) {
        log_warning (e.message);
        return;
    }
    // 把配置里的策略下发给 Gum
    Gum.Process.set_teardown_requirement (config.teardown);
    Gum.Process.set_code_signing_policy (config.code_signing);

    Gum.Cloak.add_range (location.range);

    interceptor = Gum.Interceptor.obtain ();
    interceptor.begin_transaction ();
    // ...

    exceptor = Gum.Exceptor.obtain ();
    // 根据配置文件选择交互方式
    try {
        var interaction = config.interaction;
        if (interaction is ScriptInteraction) {
            controller = new ScriptRunner (config, location);// 加载单个 JS/bytecode 脚本，启动成功后自动 Frida.Gadget.resume()
        } else if (interaction is ScriptDirectoryInteraction) {
            controller = new ScriptDirectoryRunner (config, location);// 扫描目录里的 .js，按每个脚本旁边的配置过滤当前进程，启动成功后自动 resume
        } else if (interaction is ListenInteraction) {
            controller = new ControlServer (config, location);// 在目标进程内启动 Frida control server，外部 frida-tools 可以 attach 到这个进程
        } else if (interaction is ConnectInteraction) {
            controller = new ClusterClient (config, location);//主动连接 portal/cluster，由远端通过信号决定 resume/kill。
        } else {
            throw new Error.NOT_SUPPORTED ("Invalid interaction specified");
        }
    }
    // ...
    interceptor.end_transaction ();

    if (controller == null)
        return;

    wait_for_resume_needed = true;

    var listen_interaction = config.interaction as ListenInteraction;
    if (listen_interaction != null && listen_interaction.on_load == ListenInteraction.LoadBehavior.RESUME) {
        wait_for_resume_needed = false;
    }

    if (!wait_for_resume_needed)
        resume ();
    // 完成初始化并进入主循环处理后续消息事件
    if (wait_for_resume_needed && Environment.can_block_at_load_time ()) {
        var scheduler = Gum.ScriptBackend.get_scheduler ();

        scheduler.disable_background_thread ();

        wait_for_resume_context = scheduler.get_js_context ();

        var ignore_scope = new ThreadIgnoreScope (APPLICATION_THREAD);

        start (request);

        var loop = new MainLoop (wait_for_resume_context, true);
        wait_for_resume_loop = loop;

        wait_for_resume_context.push_thread_default ();
        loop.run ();
        wait_for_resume_context.pop_thread_default ();

        scheduler.enable_background_thread ();

        ignore_scope = null;
    } else {
        start (request);
    }
    // ...
}
```

参考[官方文档](https://frida.re/docs/gadget/)，gadget 启动时会去指定路径搜索配置文件，该配置文件应与gadget二进制文件同名，但文件扩展名为`.config`。然后根据配置文件的`interaction`字段进入不同的交互模式，可用的交互方式有：

1. **Listen模式**

默认的交互方式。配置文件最低要求如下：

```json
{
  "interaction": {
    "type": "listen",
    "address": "127.0.0.1",		// ip
    "port": 27042,				// 端口
    "on_port_conflict": "fail",	// 端口冲突时的操作
    "on_load": "wait"		// gadget加载后的操作
  }
}
```
2. **Connect模式**

连接到指定`ip:port`处的`frida-portal` ，并成为其进程集群中的一个节点。配置文件最低要求如下：

```json
{
  "interaction": {
    "type": "connect",
    "address": "127.0.0.1",	// Portal集群所在主机
    "port": 27052			// Portal集群接口的暴露位置
  }
}
```
3. **Script模式**

gadget启动后，在目标App执行前加载指定 JS 脚本。配置文件最低要求如下：

```json
{
  "interaction": {
    "type": "script",
    "path": "/home/oleavr/explore.js"	// JS 文件路径
  }
}
```
4. **ScriptDirectory模式**

gadget启动后，在目标App执行前从指定目录中加载 JS 脚本。与gadget二进制文件同名的配置文件最低要求如下：

```json
{
  "interaction": {
    "type": "script-directory",
    "path": "/usr/local/frida/scripts"	//  JS文件所在目录路径
  }
}
```

该目录下的每个 JS 脚本都可以配置一个同名的`.json`文件，用于决定相应 JS 脚本是否加载（比如仅在特定程序启动时才加载）。例如：

```json
{
  "filter": {
    "executables": ["Twitter"],		// 可执行文件名是Twitter
    "bundles": ["com.twitter.twitter-mac"], // 捆绑包标识符是com.twitter.twitter-mac（App包名）
    "objc_classes": ["Twitter"]				// 加载了一个名为 的 Objective-C 类Twitter
  }
}
```

当应用程序满足如上任意一个条件时，才会加载相应 JS 脚本。

# 总结

`frida-server` 负责在目标设备上启动控制服务，监听来自 PC 端 Frida 客户端的连接，并通过 `ControlService`、`WebService`、`DBusConnection` 等组件把外部操作转换成对本地 `HostSession` 的调用。客户端执行 `spawn`、`attach`、`kill` 等操作时，最终都会进入对应平台的 `HostSession` 实现。

在 Linux/Android 场景下，真正的注入流程主要由 `LinuxHostSession`、`Linjector` 和 `frida-helper-backend` 完成。`attach` 时 Frida 会选择合适的 `frida-agent.so`，通过文件路径或内嵌资源方式交给 injector，再由 helper 使用 `ptrace` 控制目标进程，写入 loader 代码并初始化运行环境，远程执行 loader，最终在目标进程中使用 `dlopen()` 加载 agent 并调用 `frida_agent_main`。

`frida-agent` 被加载后会初始化自身运行环境，建立与 `frida-server` 的通信通道，并把自身注册为 `AgentSessionProvider`。之后 PC 端加载脚本、发送消息、调用 RPC 等操作，都会通过这条 DBus 通道转发到目标进程内的 agent，由 agent 调用 Gum/JS 引擎完成实际 Hook 逻辑。

`frida-gadget` 不依赖 `frida-server` 主动注入，而是作为共享库提前集成到目标 App 中。gadget 启动时读取同目录下的同名 `.config` 配置文件，用户可以自定义配置文件，实现特定应用的批量持久化Hook功能。

---

参考：

[Frida Internal - Part 2: 核心组件 frida-core - 有价值炮灰](https://evilpan.com/2022/04/09/frida-core/)

[[原创] Frida-Core 源代码速通笔记](https://bbs.kanxue.com/thread-278533.htm)

https://binhack.readthedocs.io/zh/latest/os/linux/syscall/ptrace.html

https://frida.re/docs/gadget/

https://lief.re/doc/latest/tutorials/09_frida_lief.html

[[原创]小菜花的frida-gadget持久化方案汇总](https://bbs.kanxue.com/thread-268256-1.htm)

---

# 回复

## 回复 by Imxz (#2)

*2026-5-11 15:21*

tql
