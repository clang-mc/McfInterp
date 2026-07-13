# -*- coding: utf-8 -*-
"""SNBT（字符串化 NBT）解析与 32 位整数环绕。纯函数，无状态。

建模的值域（与 dpvm.py 一致，刻意简化）：
    compound -> dict
    list     -> list（类型化数组前缀 [I;/[B;/[L; 被忽略，仅取元素）
    string   -> str
    整数/布尔 -> int（true/false 归一为 1/0）
    浮点     -> float
数值的类型后缀（b/s/l/f/d）被丢弃，只保留 Python 数值——足以支撑记分板与
data get 的语义，且避免为每个标量包一层类型。
"""
import re
from functools import lru_cache


def w32(v):
    """折叠到有符号 32 位整数（Minecraft 记分板与 store int 的环绕语义）。"""
    v &= 0xFFFFFFFF
    if v >= 0x80000000:
        v -= 0x100000000
    return v


def parse_scalar(tok):
    m = re.fullmatch(r'(-?\d+)([bslBSL])?', tok)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r'(-?(?:\d+\.\d*|\.\d+|\d+))([fdFD])', tok)
    if m:
        return float(m.group(1))
    if re.fullmatch(r'-?\d+\.\d+', tok):
        return float(tok)
    if tok == 'true':
        return 1
    if tok == 'false':
        return 0
    return tok


class SNBT:
    """递归下降 SNBT 解析器。对 namespace.zip 出现的构造保持宽松容错。"""

    def __init__(self, s):
        self.s = s
        self.i = 0
        self.n = len(s)

    def ws(self):
        while self.i < self.n and self.s[self.i] in ' \t\r\n':
            self.i += 1

    def parse(self):
        self.ws()
        c = self.s[self.i]
        if c == '{':
            return self.compound()
        if c == '[':
            return self.lst()
        if c == '"' or c == "'":
            return self.string()
        return self.scalar()

    def string(self):
        q = self.s[self.i]
        self.i += 1
        out = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == '\\':
                nx = self.s[self.i + 1]
                out.append({'n': '\n', 't': '\t', 'r': '\r'}.get(nx, nx))
                self.i += 2
                continue
            if c == q:
                self.i += 1
                break
            out.append(c)
            self.i += 1
        return ''.join(out)

    def compound(self):
        self.i += 1
        d = {}
        self.ws()
        if self.s[self.i] == '}':
            self.i += 1
            return d
        while True:
            self.ws()
            if self.s[self.i] in '"\'':
                key = self.string()
            else:
                j = self.i
                while self.s[self.i] != ':':
                    self.i += 1
                key = self.s[j:self.i].strip()
            self.ws()
            assert self.s[self.i] == ':'
            self.i += 1
            d[key] = self.parse()
            self.ws()
            c = self.s[self.i]
            if c == ',':
                self.i += 1
                continue
            if c == '}':
                self.i += 1
                break
        return d

    def lst(self):
        self.i += 1
        a = []
        self.ws()
        if self.s[self.i] == ']':
            self.i += 1
            return a
        # 跳过类型化数组前缀 [I; ...]
        if self.i + 1 < self.n and self.s[self.i + 1] == ';':
            self.i += 2
        while True:
            self.ws()
            a.append(self.parse())
            self.ws()
            c = self.s[self.i]
            if c == ',':
                self.i += 1
                continue
            if c == ']':
                self.i += 1
                break
        return a

    def scalar(self):
        j = self.i
        while self.i < self.n and self.s[self.i] not in ',{}[]:':
            self.i += 1
        return parse_scalar(self.s[j:self.i].strip())


def snbt(s):
    """解析一段 SNBT 文本为 Python 值。"""
    return SNBT(s).parse()


@lru_cache(maxsize=None)
def snbt_cached(s):
    """memoize 常量 SNBT 解析（`data ... value {...}` 的值串恒定）。

    返回的对象被缓存共享，**调用方必须 deepcopy 后再入库**，否则就地修改会污染缓存。
    """
    return SNBT(s).parse()
