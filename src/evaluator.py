# -*- coding: utf-8 -*-
"""评估器前端：在通用后端之上做指令计数、外部叶子命令收集与热点函数分析。

与后端解耦——仅通过注入 RecordingHost（外部命令策略=记录）与 Profiler（观察钩子）接入。
换掉这两个注入件，同一个 Interpreter 就能接到真实 MC 服务器或别的前端。

复刻 dpvm.py 的两段式：先用忽略型 Host、无 profiler 跑引导（literal_pool_init + 手动种子），
再换上 RecordingHost + Profiler 对入口函数计数执行。
"""
from collections import Counter

from .host import Host
from .vm import Interpreter

MAXI = 500_000_000


class RecordingHost(Host):
    """把后端委托来的外部命令按执行序记录下来（策略=记录，返回成功=1）。"""

    def __init__(self):
        self.commands = []

    def external(self, cmd):
        self.commands.append(cmd)
        return 1

    # call_missing 继承自 Host：默认转调 external('function ' + name)


class Profiler:
    """观察钩子：累加总指令数与各函数进入次数，并做失控保护。"""

    def __init__(self, max_instructions=MAXI):
        self.counter = 0
        self.fn_entries = Counter()
        self.max_instructions = max_instructions

    def on_enter(self, name):
        self.fn_entries[name] += 1

    def on_instr(self):
        self.counter += 1
        if self.counter > self.max_instructions:
            raise RuntimeError('exceeded max instructions')


class Evaluation:
    """一次评估的结果聚合。"""

    def __init__(self, entry, ret, profiler, host):
        self.entry = entry
        self.ret = ret
        self.counter = profiler.counter
        self.fn_entries = profiler.fn_entries
        self.external = host.commands


def evaluate(funcs, entry, bootstrap='namespace:literal_pool_init'):
    """引导 + 计数执行入口函数，返回 Evaluation。"""
    vm = Interpreter(funcs)  # 引导阶段：忽略型 Host、无 profiler
    if bootstrap in funcs:
        vm.run_top(bootstrap, None)
    vm.store.set('dnt:ram', 'in', ['', ''])  # initializer 里的种子

    host = RecordingHost()
    prof = Profiler()
    vm.host = host
    vm.profiler = prof
    ret = vm.run_top(entry, None)
    return Evaluation(entry, ret, prof, host)
