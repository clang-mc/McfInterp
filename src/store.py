# -*- coding: utf-8 -*-
"""状态容器：多命名空间 NBT 存储 Store 与记分板 Scoreboard。

薄封装——把 ns→root 映射和 player→分值表独立出来，纯解析逻辑在 nbtpath/snbt。
"""
from . import nbtpath
from .snbt import w32


class Store:
    """多命名空间 storage：ns -> 根 compound(dict)。

    读写方法委托给 nbtpath，在对应 ns 的根上操作。写方法返回修改计数。
    """

    def __init__(self):
        self.roots = {}

    def root(self, ns):
        return self.roots.setdefault(ns, {})

    def get(self, ns, path):
        return nbtpath.get(self.root(ns), path)

    def exists(self, ns, path):
        return nbtpath.exists(self.root(ns), path)

    def count(self, ns, path):
        return nbtpath.count(self.root(ns), path)

    def set(self, ns, path, value):
        return nbtpath.setv(self.root(ns), path, value)

    def merge(self, ns, path, comp):
        return nbtpath.mergev(self.root(ns), path, comp)

    def append(self, ns, path, value):
        return nbtpath.appendv(self.root(ns), path, value)

    def remove(self, ns, path):
        return nbtpath.removev(self.root(ns), path)


class Scoreboard:
    """记分板：player -> 有符号 32 位整数。忽略 objective（dovetail 玩家名无冲突）。"""

    def __init__(self):
        self.scores = {}

    def get(self, player):
        return self.scores.get(player, 0)

    def set(self, player, v):
        self.scores[player] = w32(int(v))
        return self.scores[player]
