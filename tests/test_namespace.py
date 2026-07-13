# -*- coding: utf-8 -*-
r"""namespace.zip 的验收测试。可直接 `python tests/test_namespace.py` 运行（无需 pytest）。

覆盖：主路径正确执行、字符串 concat/strcmp/strstr 走对分支、后端可脱离前端独立运行、
`\` 续行在加载期正确合并。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import Interpreter, load_all, resolve_root
from src.evaluator import Profiler, RecordingHost, evaluate

ZIP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'namespace.zip')


def _fresh_run():
    funcs = load_all(resolve_root(ZIP))
    vm = Interpreter(funcs)
    vm.run_top('namespace:literal_pool_init', None)
    vm.store.set('dnt:ram', 'in', ['', ''])
    host, prof = RecordingHost(), Profiler()
    vm.host, vm.profiler = host, prof
    ret = vm.run_top('namespace:namespace/main', None)
    return vm, host, prof, ret


def test_main_executes():
    funcs = load_all(resolve_root(ZIP))
    assert len(funcs) == 112, len(funcs)
    ev = evaluate(funcs, 'namespace:namespace/main')
    assert ev.ret == 0, ev.ret
    assert ev.counter == 844, ev.counter
    assert len(ev.external) == 4, ev.external


def test_string_semantics_take_correct_branches():
    vm, host, _, _ = _fresh_run()
    # strcat 结果
    assert vm.store.get('dovetail', 'namespace.main.s') == 'Hello, World!'
    assert vm.store.get('dovetail', 'namespace.main.fstring_9') \
        == 'strcat: "Hello, " + "World!" = Hello, World!'
    # strstr 返回 "lo, W" 在 "Hello, World!" 的索引 3
    assert vm.score.get('return_5574465504065953516') == 3
    # 4 条外部 tellraw 解析到的文本：strcmp 走「相等」、strstr 走「找到」分支
    texts = []
    for c in host.commands:
        assert c.startswith('tellraw @a '), c
        # 从 {"storage":"dovetail","nbt":"PATH"} 取 PATH 再解析
        path = c.split('"nbt":"')[1].split('"')[0]
        texts.append(vm.store.get('dovetail', path))
    assert texts == [
        'mcfunction string performance test',
        'strcat: "Hello, " + "World!" = Hello, World!',
        'strcmp: "Hello, World!" == "Hello, World!"',   # == 分支（相等）
        'strstr: "lo, W" in "Hello, World!"',           # in 分支（找到）
    ], texts


def test_backend_runs_without_frontend():
    # 默认 Host（忽略外部）、无 profiler：核心 VM 不依赖评估器即可执行
    funcs = load_all(resolve_root(ZIP))
    vm = Interpreter(funcs)
    vm.run_top('namespace:literal_pool_init', None)
    vm.store.set('dnt:ram', 'in', ['', ''])
    assert vm.run_top('namespace:namespace/main', None) == 0
    assert vm.store.get('dovetail', 'namespace.main.s') == 'Hello, World!'


def test_line_continuation_merged():
    funcs = load_all(resolve_root(ZIP))
    num = funcs['dnt:private/json/value/numeric']
    merged = [i for i in num if i.raw.startswith('execute unless data')]
    assert len(merged) == 1, len(merged)
    line = merged[0].raw
    assert chr(92) not in line               # 反斜杠已清除
    assert line.count('unless data storage') == 12  # 12 段续行合并为一条


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('PASS', name)
    print('全部通过')
