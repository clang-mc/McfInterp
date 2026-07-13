# -*- coding: utf-8 -*-
r"""数据包加载：zip 解压、递归发现 data/ 包、mcfunction 逻辑行提取。

逻辑行提取顺序（关键）：先在**物理行**层合并 `\` 续行，再 strip、丢弃空行与 `#` 注释。
`\` 续行是 1.21+ mcfunction 语法（如 dnt json/value/numeric.mcfunction 的多行 execute），
dpvm.py 未处理，必须在此合并，否则续行会被当成独立命令误解析。
"""
import atexit
import glob
import os
import re
import shutil
import tempfile
import zipfile

_MACRO_RE = re.compile(r'\$\(([^)]*)\)')


class Instr:
    """一条预编译的逻辑行。

    加载期一次性完成分词与宏模板拆分，执行期免重复 split/正则：
      非宏行： head=首 token，argv=已 split 的 token 列表，raw=原串
      宏行（$）： macro=True，parts=[str | ('k', 名)] 段列表，运行期直接拼接
    """

    __slots__ = ('raw', 'head', 'argv', 'macro', 'parts')

    def __init__(self, raw):
        self.raw = raw
        if raw[0] == '$':
            self.macro = True
            self.head = None
            self.argv = None
            self.parts = _compile_macro(raw[1:])
        else:
            self.macro = False
            self.argv = raw.split()
            self.head = self.argv[0]
            self.parts = None


def _compile_macro(tmpl):
    """把宏模板拆成 [字面串 | ('k', 变量名)] 段列表，避免运行期反复正则替换。"""
    parts = []
    last = 0
    for m in _MACRO_RE.finditer(tmpl):
        if m.start() > last:
            parts.append(tmpl[last:m.start()])
        parts.append(('k', m.group(1)))
        last = m.end()
    if last < len(tmpl):
        parts.append(tmpl[last:])
    return parts


def resolve_root(path=None):
    """把命令行给的路径归一为一个含 data/ 的根目录。

    .zip → 解压到临时目录（进程退出时清理）；目录 → 原样；None → 脚本同目录 namespace.zip。
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'namespace.zip')
    if path.lower().endswith('.zip'):
        tmp = tempfile.mkdtemp(prefix='mcfvm_')
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        atexit.register(shutil.rmtree, tmp, ignore_errors=True)
        return tmp
    return path


def _logical_lines(text):
    """把一个 .mcfunction 文本转为逻辑行：合并续行 → 去注释/空行。"""
    # 1) 物理行层合并 `\` 续行
    raw = text.splitlines()
    merged = []
    buf = None
    for ln in raw:
        r = ln.rstrip()
        if r.endswith('\\'):
            piece = r[:-1]
            buf = piece if buf is None else buf + ' ' + piece.strip()
        else:
            if buf is not None:
                merged.append(buf + ' ' + r.strip())
                buf = None
            else:
                merged.append(ln)
    if buf is not None:  # 文件末尾悬挂的续行
        merged.append(buf)
    # 2) strip、丢弃空行与注释
    out = []
    for ln in merged:
        s = ln.strip()
        if s and not s.startswith('#'):
            out.append(s)
    return out


def load_pack(data_dir, funcs):
    """把一个 data/ 目录下的所有函数加载进 funcs（键 ns:name，值 list[Instr]）。"""
    for f in glob.glob(os.path.join(data_dir, '**', '*.mcfunction'), recursive=True):
        rel = os.path.relpath(f, data_dir).replace('\\', '/').split('/')
        ns = rel[0]
        assert rel[1] == 'function', rel
        name = '/'.join(rel[2:])[:-len('.mcfunction')]
        with open(f, encoding='utf-8') as fh:
            funcs[ns + ':' + name] = [Instr(ln) for ln in _logical_lines(fh.read())]


def load_all(root):
    """递归发现 root 下所有 data/ 包（覆盖内嵌库包），返回 funcs 字典。"""
    funcs = {}
    for dirpath, _dirs, _files in os.walk(root):
        if os.path.basename(dirpath) == 'data' and os.path.isdir(dirpath):
            load_pack(dirpath, funcs)
    return funcs
