# -*- coding: utf-8 -*-
"""轻量 mcfunction 解释器（Minecraft 1.21.4）。

后端：通用高效执行引擎（Interpreter + Host 接缝），只建模数据包语义，外部命令委托 Host。
前端：evaluator（指令计数/外部命令收集/热点分析）、cli。前后端解耦，仅经 Host/Profiler 注入交互。

公共 API::

    from src import Interpreter, Host, load_all, resolve_root
    funcs = load_all(resolve_root('namespace.zip'))
    vm = Interpreter(funcs)            # 默认忽略型 Host，可独立执行
    vm.run_top('namespace:namespace/main', None)
"""
from .host import Host
from .loader import load_all, load_pack, resolve_root
from .store import Scoreboard, Store
from .vm import Interpreter

__all__ = [
    'Interpreter',
    'Host',
    'Store',
    'Scoreboard',
    'load_all',
    'load_pack',
    'resolve_root',
]
