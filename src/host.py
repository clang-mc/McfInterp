# -*- coding: utf-8 -*-
"""Host：后端执行引擎与外部世界（原版 MC）之间的接缝。

核心 Interpreter 只建模数据包语义（storage/scoreboard/function/execute/return/宏）。
任何它不建模的命令——原版叶子命令（tellraw/kill/loot/setblock/summon/tp/...）、
`data modify` 到非 storage 的目标、`set from|string` 源非 storage、未知函数——都委托给
注入的 Host，由 Host 决定「记录、忽略还是真实派发到 MC 服务器」。

后端负责**检测**（sh 命令是否可建模，沿用 dpvm.py 的判定）；Host 负责**策略**。
默认实现忽略一切外部命令并返回 1（表示成功），使核心 VM 可脱离任何前端独立运行。
"""


class Host:
    def external(self, cmd):
        """处理一条后端不建模的完整命令，返回其整型结果（默认成功=1）。"""
        return 1

    def call_missing(self, name):
        """调用了未知函数目标 name，返回其整型结果。"""
        return self.external('function ' + name)
