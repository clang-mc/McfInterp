# -*- coding: utf-8 -*-
"""CLI 前端：装配后端 + 评估器，打印指令数/外部命令/热点函数报告。

用法：
    python -m src <数据包目录|pack.zip>
    python -m src                          # 默认脚本上级目录的 namespace.zip
"""
import io
import sys

from .evaluator import evaluate
from .loader import load_all, resolve_root

# 默认计数入口（可按需修改）
ENTRY = 'namespace:namespace/main'


def main(argv=None):
    argv = sys.argv if argv is None else argv
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass  # 已包装或不支持时忽略

    path = argv[1] if len(argv) > 1 else None
    root = resolve_root(path)
    funcs = load_all(root)
    print('已加载函数数:', len(funcs))

    ev = evaluate(funcs, ENTRY)

    print('入口:', ev.entry)
    print('返回:', ev.ret)
    print('指令数 (INSTRUCTION COUNT):', ev.counter)
    print('外部/原版叶子命令数:', len(ev.external))
    for c in ev.external:
        print('   EXT>', c)
    print('进入的不同函数数:', len(ev.fn_entries))
    print('函数体执行总次数:', sum(ev.fn_entries.values()))
    print('最热的 15 个函数（进入次数）:')
    for fn, c in ev.fn_entries.most_common(15):
        print(f'   {c:>7}  {fn}')


if __name__ == '__main__':
    main()
