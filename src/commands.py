# -*- coding: utf-8 -*-
"""命令语义（CommandsMixin）：data / scoreboard / execute / function / return / 宏。

被 vm.Interpreter 通过多继承混入，方法内以 self.store / self.score / self.host /
self.run_top 访问状态与引擎。commands.py **不 import vm**，故无循环依赖。

外部命令处理沿用 dpvm.py 的**检测**逻辑，但把**策略**下放给 self.host：
凡后端不建模的命令（原版叶子、data modify 目标非 storage、set from|string 源非 storage、
未知函数），调用 self.host.external(cmd) / self.host.call_missing(name) 取返回值。
"""
import copy
import re

from .snbt import snbt_cached, w32
from .nbtpath import Missing


class CommandsMixin:
    # ---------------- data 命令 ----------------
    def data_get(self, toks):
        # data get storage NS PATH [scale]
        ns = toks[3]
        path = toks[4]
        scale = float(toks[5]) if len(toks) >= 6 else 1.0
        try:
            v = self.store.get(ns, path)
        except Missing:
            return 0
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, (list, dict, str)):
            v = len(v)
        return int(v * scale)

    def data_cmd(self, cmd, toks):
        """执行 data 命令，返回整型结果（modify 为修改计数）。

        返回 None 表示目标/源非 storage → 该命令是外部命令，交由 exec_value 委托 host。
        """
        sub = toks[1]
        if sub == 'get':
            if toks[2] == 'storage':
                return self.data_get(toks)
            return None
        if sub == 'remove':
            if toks[2] == 'storage':
                return self.store.remove(toks[3], toks[4])
            return None
        if sub != 'modify':
            return 1
        # data modify <tgt> ...
        if toks[2] != 'storage':
            return None  # 目标非 storage（如 entity）→ 外部
        ns = toks[3]
        path = toks[4]
        op = toks[5]
        if op == 'set':
            if toks[6] == 'value':
                valstr = cmd[re.search(r'\bset value ', cmd).end():]
                return self.store.set(ns, path, copy.deepcopy(snbt_cached(valstr)))
            if toks[6] == 'from':
                if toks[7] == 'storage':
                    sns = toks[8]
                    sp = toks[9]
                    if sp.endswith('[]'):
                        try:
                            els = list(self.store.get(sns, sp[:-2]))
                        except Missing:
                            return 0
                        return self.store.set(ns, path, copy.deepcopy(els))
                    try:
                        v = copy.deepcopy(self.store.get(sns, sp))
                    except Missing:
                        return 0
                    return self.store.set(ns, path, v)
                return None  # from entity 等 → 外部
            if toks[6] == 'string':
                # set string storage SNS SPATH START [END]
                if toks[7] != 'storage':
                    return None
                sns = toks[8]
                sp = toks[9]
                try:
                    v = self.store.get(sns, sp)
                except Missing:
                    return 0
                s = str(v)
                start = int(toks[10]) if len(toks) > 10 else 0
                end = int(toks[11]) if len(toks) > 11 else None
                return self.store.set(ns, path, s[start:end] if end is not None else s[start:])
        if op == 'merge':
            if toks[6] == 'value':
                valstr = cmd[re.search(r'\bmerge value ', cmd).end():]
                return self.store.merge(ns, path, snbt_cached(valstr))  # merge 内部 deepcopy 每个值
        if op == 'append':
            if toks[6] == 'value':
                valstr = cmd[re.search(r'\bappend value ', cmd).end():]
                return self.store.append(ns, path, copy.deepcopy(snbt_cached(valstr)))
            if toks[6] == 'from' and toks[7] == 'storage':
                sns = toks[8]
                sp = toks[9]
                if sp.endswith('[]'):
                    try:
                        els = list(self.store.get(sns, sp[:-2]))
                    except Missing:
                        return 0
                    n = 0
                    for el in els:
                        n += self.store.append(ns, path, copy.deepcopy(el))
                    return n
                try:
                    v = copy.deepcopy(self.store.get(sns, sp))
                except Missing:
                    return 0
                return self.store.append(ns, path, v)
        return 1

    # ---------------- scoreboard ----------------
    def sb(self, toks):
        if toks[1] == 'objectives':
            return 0  # add/remove 忽略
        op = toks[2]
        sc = self.score
        if op == 'get':
            return sc.get(toks[3])
        if op == 'set':
            return sc.set(toks[3], int(toks[5]))
        if op == 'add':
            return sc.set(toks[3], sc.get(toks[3]) + int(toks[5]))
        if op == 'remove':
            return sc.set(toks[3], sc.get(toks[3]) - int(toks[5]))
        if op == 'operation':
            dst = toks[3]
            o = toks[5]
            src = toks[6]
            a = sc.get(dst)
            b = sc.get(src)
            if o == '=':
                r = b
            elif o == '+=':
                r = a + b
            elif o == '-=':
                r = a - b
            elif o == '*=':
                r = a * b
            elif o == '/=':
                r = a if b == 0 else a // b
            elif o == '%=':
                r = a if b == 0 else a - (a // b) * b
            elif o == '><':
                sc.set(dst, b)
                sc.set(src, a)
                return sc.get(dst)
            elif o == '<':
                r = min(a, b)
            elif o == '>':
                r = max(a, b)
            else:
                raise RuntimeError('op ' + o)
            return sc.set(dst, r)
        raise RuntimeError('sb ' + str(toks))

    # ---------------- 命令求值（返回整型结果或 None） ----------------
    def exec_value(self, cmd, toks=None):
        if toks is None:
            toks = cmd.split()
        t = toks[0]
        if t == 'scoreboard':
            return self.sb(toks)
        if t == 'data':
            r = self.data_cmd(cmd, toks)
            if r is None:  # 目标非 storage → 外部原版命令
                return self.host.external(cmd)
            return r
        if t == 'function':
            return self.call_function(cmd, toks)
        if t == 'return':
            return 1
        # 其余（loot/kill/tellraw/setblock/tp/summon/…）→ 外部叶子
        return self.host.external(cmd)

    # ---------------- 宏渲染 ----------------
    @staticmethod
    def render_parts(parts, macro):
        """把预编译的宏段列表 [str | ('k', name)] 拼成命令串（免运行期正则）。"""
        m = macro or {}
        out = []
        for p in parts:
            if type(p) is str:
                out.append(p)
            else:
                v = m.get(p[1], '')
                out.append(repr(v) if isinstance(v, float) else str(v))
        return ''.join(out)

    # ---------------- function 调用 ----------------
    def call_function(self, cmd, toks):
        target = toks[1]
        macro = None
        if 'with' in toks:
            wi = toks.index('with')
            assert toks[wi + 1] == 'storage'
            ns = toks[wi + 2]
            try:
                src = self.store.get(ns, toks[wi + 3]) if wi + 3 < len(toks) else self.store.root(ns)
            except Missing:
                src = {}
            macro = copy.deepcopy(src)
        if target not in self.funcs:
            return self.host.call_missing(target)
        return self.run_top(target, macro)

    # ---------------- execute ----------------
    @staticmethod
    def _cmp_scores(a, o, b):
        return {'<': a < b, '<=': a <= b, '=': a == b, '>': a > b, '>=': a >= b}[o]

    @staticmethod
    def _match_range(v, rng):
        if '..' in rng:
            lo, hi = rng.split('..')
            if lo != '' and v < int(lo):
                return False
            if hi != '' and v > int(hi):
                return False
            return True
        return v == int(rng)

    def _apply_stores(self, stores, val):
        for st in stores:
            mode = st[-1]
            out = (1 if val != 0 else 0) if mode == 'success' else val
            if st[0] == 'score':
                self.score.set(st[1], out)
            else:
                _, ns, path, mult, _ = st
                self.store.set(ns, path, w32(int(out * mult)))

    def handle_execute(self, cmd, toks, macro):
        i = 1
        stores = []
        last_count = 1
        n = len(toks)
        while i < n:
            t = toks[i]
            if t == 'store':
                mode = toks[i + 1]  # result | success
                assert mode in ('result', 'success')
                if toks[i + 2] == 'storage':
                    # store <mode> storage NS PATH <type> MULT
                    stores.append(('storage', toks[i + 3], toks[i + 4], float(toks[i + 6]), mode))
                    i += 7
                elif toks[i + 2] == 'score':
                    stores.append(('score', toks[i + 3], mode))
                    i += 5
                else:
                    raise RuntimeError('store ' + cmd)
            elif t == 'if' or t == 'unless':
                neg = (t == 'unless')
                if toks[i + 1] == 'score':
                    a = self.score.get(toks[i + 2])
                    op = toks[i + 4]
                    if op == 'matches':
                        res = self._match_range(a, toks[i + 5])
                        i += 6
                    else:
                        res = self._cmp_scores(a, op, self.score.get(toks[i + 5]))
                        i += 7
                elif toks[i + 1] == 'function':
                    res = (self.run_top(toks[i + 2], None) != 0)
                    i += 3
                elif toks[i + 1] == 'data':
                    assert toks[i + 2] == 'storage'
                    last_count = self.store.count(toks[i + 3], toks[i + 4])
                    res = last_count > 0
                    i += 5
                else:
                    return None  # 选择器等（仅不可达分支）
                if neg:
                    res = not res
                if not res:
                    self._apply_stores(stores, 0)  # 条件失败：store 存 0
                    return None
            elif t == 'run':
                return self.run_action(' '.join(toks[i + 1:]), stores, macro)
            elif t in ('as', 'at', 'positioned', 'align', 'anchored', 'in', 'rotated', 'facing', 'on'):
                return None  # 世界上下文选择器分支（仅不可达代码）
            else:
                raise RuntimeError('exec clause ' + t + ' :: ' + cmd)
        # 末尾无 run：`store ... if data ...` 形式，存匹配计数
        self._apply_stores(stores, last_count)
        return None

    def run_action(self, action, stores, macro):
        atoks = action.split()
        head = atoks[0]
        if head == 'return':
            return self.do_return(action, atoks, macro)
        if head == 'execute':
            return self.handle_execute(action, atoks, macro)
        val = self.exec_value(action, atoks)
        if val is None:
            val = 1
        self._apply_stores(stores, val)
        return None

    def do_return(self, action, atoks, macro):
        # return <N> | return fail | return run <cmd>
        if len(atoks) == 2:
            if atoks[1] == 'fail':
                return ('return', 0)
            return ('return', int(atoks[1]))
        assert atoks[1] == 'run'
        rest = ' '.join(atoks[2:])
        rtoks = rest.split()
        head = rtoks[0]
        if head == 'return':
            return self.do_return(rest, rtoks, macro)
        if head == 'execute':
            sig = self.handle_execute(rest, rtoks, macro)
            return sig if sig is not None else ('return', 0)
        if head == 'function' and 'with' not in rtoks:
            return ('tailcall', rtoks[1])
        val = self.exec_value(rest, rtoks)
        if val is None:
            val = 1
        return ('return', val)
