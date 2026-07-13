# -*- coding: utf-8 -*-
"""后端执行引擎：Interpreter。

纯执行核心——运行 mcfunction 逻辑行，处理 storage/scoreboard/execute/function/return/宏，
把不建模的命令委托给注入的 Host。对「计数/外部命令列表/热点分析」一无所知：那是前端
（evaluator）的事，仅通过可选的 profiler 钩子与 Host 注入接入，默认零开销。

尾调用优化：run_top 用 while 循环消解 `return run function ...` 的尾调用，避免深递归。
"""
import sys

from .commands import CommandsMixin
from .store import Store, Scoreboard
from .host import Host

# mcfunction 递归/尾调用可能极深，放宽 Python 递归上限。
sys.setrecursionlimit(2_000_000)


class Interpreter(CommandsMixin):
    """一个可复用的数据包执行实例。

    funcs:   dict[str, list[str]]   函数键(ns:name) -> 逻辑行列表（已去注释/空行、已合并续行）
    host:    Host                   外部世界接缝（默认忽略外部命令）
    profiler: 可选对象，具 on_enter(name) 与 on_instr()，用于计数/热点；None 则零开销
    """

    def __init__(self, funcs, host=None, profiler=None):
        self.funcs = funcs
        self.store = Store()
        self.score = Scoreboard()
        self.host = host if host is not None else Host()
        self.profiler = profiler

    # ---------------- 行执行 ----------------
    def exec_line(self, instr, macro):
        if instr.macro:
            # 宏行：拼接模板段后再分词（结果串是动态的，无法预分词）
            line = self.render_parts(instr.parts, macro)
            argv = line.split()
            head = argv[0]
        else:
            line = instr.raw
            argv = instr.argv
            head = instr.head
        if head == 'scoreboard' or head == 'data':
            self.exec_value(line, argv)
            return None
        if head == 'function':
            self.call_function(line, argv)
            return None
        if head == 'execute':
            return self.handle_execute(line, argv, macro)
        if head == 'return':
            return self.do_return(line, argv, macro)
        if head == 'schedule':
            return None
        # 其它顶层命令（loot/kill/tellraw/setblock/...）→ 外部叶子
        self.exec_value(line, argv)
        return None

    # ---------------- 函数运行循环（尾调用消解） ----------------
    def run_top(self, name, macro):
        prof = self.profiler
        funcs = self.funcs
        cur = name
        curmacro = macro
        while True:
            if prof is not None:
                prof.on_enter(cur)
            body = funcs.get(cur)
            if body is None:
                return self.host.call_missing(cur)
            sig = None
            for instr in body:
                if prof is not None:
                    prof.on_instr()
                sig = self.exec_line(instr, curmacro)
                if sig is not None:
                    break
            if sig is None:
                return 0
            if sig[0] == 'return':
                return sig[1]
            cur = sig[1]  # tailcall
            curmacro = None
