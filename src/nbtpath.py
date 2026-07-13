# -*- coding: utf-8 -*-
"""NBT 路径解析与在 compound 根上的导航/读写。纯函数，无全局状态。

去全局化：所有函数接收一个 ``root``（命名空间根 compound，dict），而非 dpvm.py 的
``ns`` + 全局 STORE。这样解析层可单测、可 memoize，Store 容器只负责 ns→root 映射。

路径段（parse_path 的输出，元素为元组）：
    ('key', name)   compound 键
    ('idx', int)    列表下标（支持负）
    ('all',)        列表通配 []
    ('match', dict) compound 子集匹配 {...}

写操作返回 **修改计数**（Minecraft 语义）：值真正改变返回 1，no-op（已相等）或失败返回 0。
``execute store success/result run data modify ...`` 依赖此计数——namespace.zip 的字符串
相等比较正是用「set 到相同值是否发生修改」实现的。
"""
import copy
from functools import lru_cache

from .snbt import snbt


class Missing(Exception):
    """路径在当前存储中不存在。"""


@lru_cache(maxsize=None)
def parse_path(path):
    """把 NBT 路径串解析为段元组（memoize：路径串集有限，热点是 dnt:ram 系列）。"""
    segs = []
    i = 0
    n = len(path)
    while i < n:
        c = path[i]
        if c == '{':
            depth = 0
            j = i
            while i < n:
                if path[i] == '{':
                    depth += 1
                elif path[i] == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            segs.append(('match', snbt(path[j:i])))
        elif c == '.':
            i += 1
        elif c == '"' or c == "'":
            q = c
            i += 1
            buf = []
            while path[i] != q:
                if path[i] == '\\':
                    buf.append(path[i + 1])
                    i += 2
                    continue
                buf.append(path[i])
                i += 1
            i += 1
            segs.append(('key', ''.join(buf)))
        elif c == '[':
            i += 1
            if path[i] == ']':
                i += 1
                segs.append(('all',))
            elif path[i] == '{':
                depth = 0
                j = i
                while path[i] != ']' or depth != 0:
                    if path[i] == '{':
                        depth += 1
                    elif path[i] == '}':
                        depth -= 1
                    i += 1
                segs.append(('match', snbt(path[j:i])))
                i += 1
            else:
                j = i
                while path[i] != ']':
                    i += 1
                segs.append(('idx', int(path[j:i])))
                i += 1
        else:
            j = i
            while i < n and path[i] not in '.[{':
                i += 1
            segs.append(('key', path[j:i]))
    return tuple(segs)


def _match(val, m):
    if not isinstance(val, dict):
        return False
    for k, v in m.items():
        if k not in val:
            return False
        if isinstance(v, dict):
            if not _match(val[k], v):
                return False
        elif val[k] != v:
            return False
    return True


def nav(root, segs):
    """定位到 segs 指向的值；缺失抛 Missing。'all' 段返回其所在列表，交调用方处理。"""
    cur = root
    for s in segs:
        if s[0] == 'key':
            if not isinstance(cur, dict) or s[1] not in cur:
                raise Missing()
            cur = cur[s[1]]
        elif s[0] == 'idx':
            idx = s[1]
            if not isinstance(cur, list):
                raise Missing()
            if idx < 0:
                idx += len(cur)
            if idx < 0 or idx >= len(cur):
                raise Missing()
            cur = cur[idx]
        elif s[0] == 'all':
            if not isinstance(cur, list):
                raise Missing()
            return cur
        elif s[0] == 'match':
            if not _match(cur, s[1]):
                raise Missing()
    return cur


def get(root, path):
    return nav(root, parse_path(path))


def exists(root, path):
    try:
        segs = parse_path(path)
        v = nav(root, segs)
        if segs and segs[-1][0] == 'all':
            return len(v) > 0
        return True
    except Missing:
        return False


def count(root, path):
    """if/store data 的匹配计数：末段 [] → 列表长度；否则存在=1、缺失=0。"""
    try:
        segs = parse_path(path)
        v = nav(root, segs)
        if segs and segs[-1][0] == 'all':
            return len(v)
        return 1
    except Missing:
        return 0


def setv(root, path, value):
    """设置路径为 value，自动创建中间 compound。返回修改计数（改变=1，no-op/失败=0）。"""
    segs = parse_path(path)
    cur = root
    for s in segs[:-1]:
        if s[0] == 'key':
            if not isinstance(cur, dict):
                return 0
            cur = cur.setdefault(s[1], {})
        elif s[0] == 'idx':
            idx = s[1]
            if not isinstance(cur, list):
                return 0
            if idx < 0:
                idx += len(cur)
            if idx < 0 or idx >= len(cur):
                return 0
            cur = cur[idx]
        else:
            return 0
    last = segs[-1]
    if last[0] == 'key':
        if isinstance(cur, dict):
            if last[1] in cur and cur[last[1]] == value:
                return 0
            cur[last[1]] = value
            return 1
    elif last[0] == 'idx':
        idx = last[1]
        if isinstance(cur, list):
            if idx < 0:
                idx += len(cur)
            if 0 <= idx < len(cur):
                if cur[idx] == value:
                    return 0
                cur[idx] = value
                return 1
    return 0


def mergev(root, path, comp):
    """把 compound comp 合并进目标。返回发生改变的键数。"""
    try:
        cur = get(root, path)
    except Missing:
        setv(root, path, copy.deepcopy(comp))
        return len(comp) if comp else 1
    if isinstance(cur, dict):
        changed = 0
        for k, v in comp.items():
            nv = copy.deepcopy(v)
            if k not in cur or cur[k] != nv:
                cur[k] = nv
                changed += 1
        return changed
    setv(root, path, copy.deepcopy(comp))
    return 1


def appendv(root, path, value):
    """向列表末尾追加。返回 1（追加总是一次修改）。"""
    try:
        cur = get(root, path)
    except Missing:
        cur = []
        setv(root, path, cur)
    if isinstance(cur, list):
        cur.append(value)
        return 1
    return 0


def removev(root, path):
    """删除路径。返回删除计数（0 或 1）。"""
    segs = parse_path(path)
    try:
        parent = nav(root, segs[:-1]) if len(segs) > 1 else root
    except Missing:
        return 0
    last = segs[-1]
    if last[0] == 'key':
        if isinstance(parent, dict) and last[1] in parent:
            del parent[last[1]]
            return 1
    elif last[0] == 'idx':
        idx = last[1]
        if isinstance(parent, list):
            if idx < 0:
                idx += len(parent)
            if 0 <= idx < len(parent):
                parent.pop(idx)
                return 1
    return 0
