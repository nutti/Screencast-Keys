# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


from collections import deque
import collections
import itertools
# import types
# import builtins
import inspect
import warnings

try:
    import nose
    from nose.tools import eq_, ok_, raises
except:
    pass

import tempfile, os, cProfile, pstats


__all__ = ('flatten', 'groupwith', 'xproperty', 'find_brackets',
           'generate_signature_bind_function',
           'generate_signature_bind_string',
           'generate_function',
           'profile')


def _list_or_tuple(x):
    return isinstance(x, (list, tuple))


def _is_iterable(x):
    """list_or_tuple()の代わり"""
    return (isinstance(x, collections.abc.Sequence) and
            not isinstance(x, (str, bytes, bytearray, memoryview)))


def flatten(sequence, to_expand=_is_iterable, dimension=0):
    """
    入れ子の要素を順に返すジェネレータ
    Python Cookbook 第二版 第四章第六節 入れ子になったシーケンスの平滑化
    :param sequence: 平坦化するシーケンス
    :type sequence: collections.abc.Iterable
    :param to_expand: 平坦化するオブジェクトか判定する
    :type to_expand: types.FunctionType -> bool
    :param dimension: sequenceの次元を指定して平坦化を制限する。
        [0, [1, [2, 3], 4], 5] ->
             0: (0, 1, 2, 3, 4, 5)  # 全て展開
             1: (0, [1, [2, 3], 4], 5)  # そのまま
             2: (0, 1, [2, 3], 4, 5)  # 二次元と見做し、一回だけ展開
    :type dimension: int
    :rtype: types.GeneratorType
    """
    for item in sequence:
        if dimension != 1 and to_expand(item):
            for sub_item in flatten(item, to_expand, dimension - 1):
                yield sub_item
        else:
            yield item


def groupwith(iterable, key=None, data=None, order=None):
    """key関数の結果に従ってグループ化する。並び順は保証される。
    :param iterable: 対象のシーケンス。
    :type iterable: collections.abc.Iterable
    :param key: 比較用の関数。引数を二つ取って真偽値を返す。key(A, B)。
                デフォルトは == で比較する。
    :type key: type.FunctionType -> bool
    :param data: None以外ならkey関数に引数として渡す。key(A, B, data)
    :param order: このリストの中身を並び順を表すインデックスで更新する
    :type order: list
    :return: 二次元リスト
    :rtype: list

    key = lambda a, b: set(a).intersection(b)
    indices = []
    groups = groupwith([('A', 'B'), ('C', 'D'), ('D', 'C'), ('B', 'A')],
                       key, indices)
    groups
    >> [[('A', 'B'), ('B', 'A')], [('C', 'D'), ('D', 'C')]]
    indices
    >> [[0, 3], [1, 2]]
    """
    # if isinstance(iterable, types.GeneratorType):
    #     seq = tuple(iterable)
    # else:
    #     seq = iterable
    seq = tuple(iterable)

    if len(seq) == 0:
        if order is not None:
            order[:] = []
        return []
    elif len(seq) == 1:
        if order is not None:
            order[:] = [[0]]
        return [[seq[0]]]


    if key is None:
        key = lambda a, b: a == b
        data = None

    indices = deque()
    dic = {}
    for i, j in itertools.combinations(range(len(seq)), 2):
        if data is not None:
            is_same_group = key(seq[i], seq[j], data)
        else:
            is_same_group = key(seq[i], seq[j])
        if is_same_group:
            if i in dic and j in dic:
                # groupの結合。前側のgroupに後側のgroupの要素を追加した後で
                # 後側のgroupを消す。
                group_i = dic[i]
                group_j = dic[j]
                if group_i is not group_j:
                    if len(group_j) > len(group_i):
                        group_i, group_j = group_j, group_i
                    group_i.extend(group_j)
                    # indices.remove(group_j)だと == で要素を比較する為不適
                    for k, g in enumerate(indices):
                        if g is group_j:
                            break
                    indices.rotate(-k)
                    indices.popleft()
                    indices.rotate(k)
                    for m in group_j:
                        dic[m] = group_i
            elif i in dic:
                dic[i].append(j)
                dic[j] = dic[i]
            elif j in dic:
                dic[j].append(i)
                dic[i] = dic[j]
            else:
                group = [i, j]
                indices.append(group)
                dic[i] = dic[j] = group
        else:
            if i not in dic:
                group = [i]
                indices.append(group)
                dic[i] = group
            if j not in dic:
                group = [j]
                indices.append(group)
                dic[j] = group

    for group in indices:
        group.sort()

    if order is not None:
        order[:] = indices

    return [[seq[i] for i in group] for group in indices]


def find_brackets(text, brackets=(('(', ')'), ('[', ']'), ('{', '}')),
                  quotations=("'''", '"""', "'", '"'),
                  old_style=False):
    """文字列中のブラケット及びクォーテーションのペアを探す。
    対応するブラケットが見つけられないならインデックスはNoneになる。

    >> text = "print({'A': '''B\"C\"'''}['A'])"
    >> r = find_brackets(text)
    >> r
    ((5, '(', 28, ')'),
     (6, '{', 22, '}'),
     (7, "'", 9, "'"),
     (12, "'''", 19, "'''"),
     (23, '[', 27, ']'),
     (24, "'", 26, "'"))
    >> for i, t, j, u in r:
    >>     print(text[slice(i, j + len(u))])
    ({'A': '''B"C"'''}['A'])
    {'A': '''B"C"'''}
    'A'
    '''B"C"'''
    ['A']
    'A'

    >> find_brackets("eval(\'print(\\\'test\\\')\')")
    ((4, '(', 22, ')'), (5, "'", 21, "'"))

    >> find_brackets("({)'")
    ((0, '(', None, ')'),
     (1, '{', None, '}'),
     (None, '(', 2, ')'),
     (3, "'", None, "'"))

    >> find_brackets("<class> $$ABC¥¥", brackets=[['$$', '¥¥'], ['<', '>']])
    ((0, '<', 6, '>'), (8, '$$', 13, '¥¥'))

    :type text: str
    :param brackets: 対象を指定。先頭から順に処理するので順序には注意
    :type brackets: list | tuple
    :param quotations: 対象を指定。先頭から順に処理するので順序には注意
        例 ["'", "'''"] と ["'''", "'"] では結果が異なる
    :type quotations: list | tuple
    :param old_style: 互換性維持の為。
    :type old_style: bool
    :return: old_styleが偽の場合:
                 ((先頭インデックス, 先頭token,
                   末尾インデックス(末尾tokenの開始位置), 末尾token), ...)
             old_styleが真の場合:
                 ((先頭インデックス,
                   末尾インデックス(末尾tokenの開始位置 + len(末尾token)), ...)
    :rtype: tuple
    """

    match_tokens = {}  # {start index: [start token, end index, end token],...}
    tmp = []  # [[start index], ...]

    invalid = False
    i = 0
    length = len(text)
    while i < length:
        if tmp:
            j = tmp[-1]
            last_token = match_tokens[j][0]
        else:
            j = 0
            last_token = ''

        # ' " ''' """
        match = False
        for quot in quotations:
            if text[i: i + len(quot)] != quot:
                continue
            if i > 0 and text[i - 1] == '\\':
                continue
            if tmp and last_token in quotations and last_token != quot:
                # 文字列中では別の文字列を開始しない
                continue
            # close
            if tmp and last_token == quot:
                match_tokens[j][1] = i
                tmp.pop()
            # start
            else:
                match_tokens[i] = [quot, None, quot]
                tmp.append(i)
            match = True
            i += len(quot)
            break
        if match:
            continue

        if last_token in quotations:
            i += 1
            continue

        # ( ) [ ] { }
        match = False
        for token_start, token_end in brackets:
            # close
            if text[i: i + len(token_end)] == token_end:
                if invalid:
                    match_tokens[i] = [token_start, i, token_end]
                elif tmp and last_token == token_start:
                    match_tokens[j][1] = i
                    tmp.pop()
                else:
                    invalid = True
                    match_tokens[i] = [token_start, i, token_end]
                i += len(token_end)
                match = True
                break
            # start
            elif text[i: i + len(token_start)] == token_start:
                match_tokens[i] = [token_start, None, token_end]
                tmp.append(i)
                i += len(token_start)
                match = True
                break
        if not match:
            i += 1

    if old_style:
        retval = []
        for i, (t, j, u) in sorted(match_tokens.items()):
            if i == j:
                i = None
            if j:
                j += len(u)
            retval.append((i, j))
        retval = tuple(retval)
    else:
        retval = tuple(((i, t, j, u) if i != j else (None, t, j, u)
                       for i, (t, j, u) in sorted(match_tokens.items())))
    return retval


def find_pair_tokens(
        text,
        bracket=(('(', ')'), ('[', ']'), ('{', '}')),
        shortstring=("'", '"'),
        longstring=("'''", '"""'),
        comment=('#',),
        incorrect_closing=False):
    """トークンの組を探す。
    :param text: 文字列か、'\n'で分割した文字列のリスト
    :type text: str | list | tuple
    :param bracket:
    :type param: list | tuple
    :param shortstring: 通常の文字列。行の最後が'\'なら次の行へも継続できる
    :type shortstring: list | tuple
    :param longstring: 改行しても継続できる文字列
    :type longstring: list | tuple
    :param comment: コメントを表す文字。一文字ならインライン、文字列が二つの
        タプルならブロックコメント。e.g. comment=('//', ('/*', '*/'))
    :type comment: list | tuple
    :param incorrect_closing: '[(])': False -> ((0, None), (1, 4), (None, 3))
                                      True  -> ((0, 3), (1, None), (None, 4))
    :type incorrect_closing: bool
    :return: 要素が (開始インデックス, 終了インデックス) となるタプルを返す。
        textにリストを指定した場合は、リストインデックスと文字列インデックスの
        ペアとなる。
        e.g. '012[45]7' -> ((3, 7), )
             ['01[3', '456]8'] -> (((0, 2), (1, 4)), )

    :rtype: tuple
    """

    if bracket:
        bracket = sorted(bracket, key=lambda st_ed: -len(st_ed[0]))
    else:
        bracket = []

    string = []  # [((start, end), is_longstring), ...]
    if shortstring:
        for elem in shortstring:
            pair = (elem, elem) if isinstance(elem, str) else elem
            string.append((pair, False))
    if longstring:
        for elem in longstring:
            pair = (elem, elem) if isinstance(elem, str) else elem
            string.append((pair, True))
    string.sort(key=lambda x: (-len(x[0][0]), -int(x[1])))

    if comment:
        block_comment = [elem for elem in comment if not isinstance(elem, str)]
        block_comment.sort(key=lambda st_ed: -len(st_ed[0]))
        inline_comment = [elem for elem in comment if isinstance(elem, str)]
        inline_comment.sort(key=lambda st: -len(st))
    else:
        block_comment = ()
        inline_comment = ()

    tokens_start = set()
    for st, ed in bracket:
        tokens_start.add(st[0])
        tokens_start.add(ed[0])
    for (st, ed), flag in string:
        tokens_start.add(st[0])
        tokens_start.add(ed[0])
    for st, ed in block_comment:
        tokens_start.add(st[0])
        tokens_start.add(ed[0])
    for st in inline_comment:
        tokens_start.add(st[0])

    spans = []  # result
    stack = []  # [(span, end_string), ...]

    if not isinstance(text, str):
        text_string = '\n'.join(text)
    else:
        text_string = text

    length = len(text_string)

    def prev_back_slash_num(index):
        """index及びその前方に連続するバックスラッシュの数を返す"""
        num = 0
        while index >= 0:
            if text_string[index] == '\\':
                num += 1
            else:
                break
            index -= 1
        return num

    def find_block_comment_end(index, span, end_string):
        while index < length:
            end_index = index + len(end_string)
            s = text_string[index: end_index]
            if s == end_string:
                if prev_back_slash_num(index - 1) % 2 == 0:
                    span[1] = end_index
                    return end_index
            index += 1
        return index

    def find_inline_comment_end(index, span):
        while index < length:
            s = text_string[index]
            if s == '\n':
                span[1] = index
                return index + 1
            index += 1
        span[1] = index
        return index

    def find_string_end(index, span, end_string, is_long=False):
        while index < length:
            end_index = index + len(end_string)
            s = text_string[index: end_index]
            if s == end_string:
                if prev_back_slash_num(index - 1) % 2 == 0:
                    span[1] = end_index
                    return end_index
            elif not is_long and s[0] == '\n':
                if prev_back_slash_num(index - 1) % 2 != 1:
                    return index + 1
            index += 1
        return index

    def find_start(index):
        """シーク済みのインデックスを返す"""
        if text_string[index] not in tokens_start:
            return index

        # ブロックコメント
        for st, ed in block_comment:
            t = text_string[index: index + len(st)]
            if t == st:
                span = [index, None]
                spans.append(span)
                return find_block_comment_end(index + len(st), span, ed)
        # インラインコメント
        for st in inline_comment:
            t = text_string[index: index + len(st)]
            if t == st:
                span = [index, None]
                spans.append(span)
                return find_inline_comment_end(index + len(st), span)
        # 文字列
        for (st, ed), is_long in string:
            t = text_string[index: index + len(st)]
            if t == st:
                span = [index, None]
                spans.append(span)
                return find_string_end(index + len(st), span, ed, is_long)

        # 括弧
        for st, ed in bracket:
            t = text_string[index: index + len(st)]
            if t == st:
                span = [index, None]
                spans.append(span)
                if incorrect_closing:
                    stack.append((span, ed))
                    return find_bracket(index + len(st))
                else:
                    return find_bracket(index + len(st), span, ed)

        return index

    def find_bracket(index, span=None, end_string=None):
        while index < length:
            i = find_start(index)
            if i != index:
                index = i
                continue

            if span:
                end_index = index + len(end_string)
                if text_string[index: end_index] == end_string:
                    span[1] = end_index
                    return end_index

            for st, ed in bracket:
                end_index = index + len(ed)
                if text_string[index: end_index] == ed:
                    for j, (stack_span, stack_ed) in enumerate(stack[::-1]):
                        if ed == stack_ed:
                            stack_span[1] = end_index
                            stack[-j - 1:] = []
                            return end_index
                    invalid_span = [None, end_index]
                    spans.append(invalid_span)
                    break
            index += 1
        return index

    # メインループ
    find_bracket(0)

    # return。'\n'で分割した文字列リストを引数で受け取っていた場合は、
    # ((リストインデックス, 文字列インデックス), ...) の形式に変換する。
    if isinstance(text, str):
        return tuple((tuple(span) for span in spans))

    else:
        line_positions = []
        i = 0
        for line in text:
            line_positions.append((i, i + len(line)))
            i += len(line) + 1  # '\n'文字も足す

        span_list = []
        i = 0
        line_positions_iter = iter(line_positions)
        st, ed = next(line_positions_iter)
        for start, end in spans:
            if start is not None:
                while not (st <= start <= ed):
                    i += 1
                    st, ed = next(line_positions_iter)
                span_start = (i, start - st)
            else:
                span_start = (None, None)
            if end is not None:
                while not (st <= end <= ed):
                    i += 1
                    st, ed = next(line_positions_iter)
                span_end = (i, end - st)
            else:
                span_end = (None, None)
            span_list.append((span_start, span_end))
        return tuple(span_list)


def xproperty(fget=None, fset=None, fdel=None, doc=None):
    """
    prorpertyのラッパー
    fget and fset must be a str or a int or a function.
    参考: Pythonクックブック第二版 p255
    fgetとfsetに関数以外を指定する場合:
        fget='data':    return self.data
        fget='data.x':  return self.data.x
        fget=3:         return self[3]
        fget="['key']": return self['key']
        fget="('arg')": return self('arg')  # この形式はfsetには不可
        fget='.data':   return self.data
    """
    if isinstance(fget, str):
        if fget.startswith(('[', '(', '.')):
            def fget_func(self):
                return eval('self' + fget)
        elif '.' in fget:
            def fget_func(self):
                return eval('self.' + fget)
        else:
            def fget_func(self):
                return getattr(self, fget)
    elif isinstance(fget, int):
        def fget_func(self):
            return self[fget]
    else:
        fget_func = fget

    if isinstance(fset, str):
        if fget.startswith(('[', '.')):
            def fset_func(self, val):
                exec('self' + fget + ' = val')
        elif '.' in fset:
            def fset_func(self, val):
                exec('self.' + fset + ' = val')
        else:
            def fset_func(self, val):
                setattr(self, fset, val)
    elif isinstance(fset, int):
        def fset_func(self, val):
            self[fset] = val
    else:
        fset_func = fset

    return property(fget_func, fset_func, fdel, doc)


def generate_signature_bind_function(signature):
    """locals()で得られた辞書を引数とし、
    (args, kwargs) を返す関数を生成する。
    :type signature: inspect.Signature
    """
    text = 'def func(local_dict):\n'
    text += '    args = []\n'
    text += '    kwargs = {}\n'
    for name, param in signature.parameters.items():
        # POSITIONAL_ONLYパラメータはユーザー定義出来無いが
        # abs()等の組み込みには存在する。
        # 組み込みからSignatureオブジェクトは作れないので本当は下の分岐は不要。
        if param.kind == param.POSITIONAL_ONLY:
            text += '    args.append(local_dict["{}"])\n'.format(name)
        elif param.kind == param.POSITIONAL_OR_KEYWORD:
            text += '    args.append(local_dict["{}"])\n'.format(name)
        elif param.kind == param.VAR_POSITIONAL:
            text += '    args.extend(local_dict["{}"])\n'.format(name)
        elif param.kind == param.KEYWORD_ONLY:
            text += '    kwargs["{0}"] = local_dict["{0}"]\n'.format(name)
        elif param.kind == param.VAR_KEYWORD:
            text += '    kwargs.update(local_dict["{}"])\n'.format(name)
    text += '    return args, kwargs\n'
    exec(text)
    return locals()['func']


def generate_signature_bind_string(signature):
    """generate_signature_bind_function()の姉妹版。
    exec()用の文字列に埋め込む為の文字列を返す。
    -> '(a, *b, c, **d)'
    :type signature: inspect.Signature
    """
    text = ''
    for name, param in signature.parameters.items():
        if param.kind == param.POSITIONAL_ONLY:
            text += name + ', '
        elif param.kind == param.POSITIONAL_OR_KEYWORD:
            text += name + ', '
        elif param.kind == param.VAR_POSITIONAL:
            text += '*' + name + ', '
        elif param.kind == param.KEYWORD_ONLY:
            text += name + '=' + name + ', '
        elif param.kind == param.VAR_KEYWORD:
            text += '**' + name + ', '
    if text and text.endswith(', '):
        text = text.rstrip(', ')
    text = '(' + text + ')'
    return text


def generate_function(name, args, lines=None, symbol_table=None):
    """文字列から関数を作る
    _generate_function('hoge', '(a, b)')
    -> def hoge(a, b):
           pass
    :param name: function name
    :type name: str
    :param args: function arguments. e.g. '(a, b=0, *c, **d)'
    :type args: str
    :param lines: 関数内のコード。改行を含まない文字列のリスト。
    :type lines: list[str]
    :param symbol_table: exec()実行時に渡す
    :type symbol_table: abc.Mapping
    :rtype: types.FunctionType
    """
    # 型チェック
    if not isinstance(args, str):
        raise TypeError('args except str')
    if not isinstance(lines, (list, tuple, type(None))):
        raise TypeError('lines except list or tuple or None')
    if not isinstance(symbol_table, (dict, type(None))):
        raise TypeError('symbol_table except dict or None')

    if args.startswith('(') ^ args.endswith(')'):
        # raise ValueError('Mismatch bracket: \'{}\''.format(args))
        # こういうの↓があるのでraiseはやめる。
        # '(rv3d: bpy.types.RegionView3D) -> bpy.types.Region'
        pass
    if not args.startswith('('):
        args = '(' + args
        args += ')'
    exec_string = 'def {}{}:\n'
    if lines:
        exec_string += '\n'.join(['    ' + line for line in lines]) + '\n'
    else:
        exec_string += '    pass\n'
    exec_string = exec_string.format(name, args)
    local_dict = {}
    exec(exec_string, symbol_table, local_dict)
    return local_dict[name]


def exec_local(code_string, globals=None, locals=None, verbose=False):
    """localsの要素を引数に持つ関数でcode_stringをラップする。
    localsに'_exec_local'がゴミとして残る。
    返り値はラップ関数のlocals()辞書。
    :type code_string: str
    :type globals: dict
    :type locals: dict
    :type verbose: bool
    :rtype: dict
    """
    if not isinstance(code_string, str):
        raise TypeError('argument \'code_string\' must be str')

    if locals is None:
        locals = {}

    func_name = '_exec_local'
    while ((globals is not None and func_name in globals) or
           (locals is not None and func_name in locals)):
        func_name += '_'

    code_str = (
        'def {name}({args}):\n'
        '{code}\n'
        '    if isinstance(__builtins__, dict):\n'
        '        return __builtins__["locals"]()\n'
        '    else:\n'
        '        return __builtins__.locals()\n'
    ).format(name=func_name,
             args=', '.join([k + '=' + k for k in locals]),
             code='\n'.join(['    ' + s for s in code_string.split('\n')]))

    if verbose:
        print(code_str)

    exec(code_str, globals, locals)
    symbol_table = locals[func_name]().copy()
    return symbol_table


def profile(column='time', list=5):
    def _profile(function):
        def __profile(*args, **kwargs):
            s = tempfile.mktemp()
            profiler = cProfile.Profile()
            try:
                return profiler.runcall(function, *args, **kwargs)
            finally:
                profiler.dump_stats(s)
                p = pstats.Stats(s)
                p.sort_stats(column).print_stats(list)
                p.print_callers('isinstance')
        return __profile
    return _profile


def _solve_dependency(element, depend_on, returned, cyclic_check=None):
    if element not in returned:
        if cyclic_check is None:
            cyclic_check = []
        cyclic_check.append(element)
        for elem in depend_on(element):
            if elem in cyclic_check:
                # raise ValueError('cyclic! {}'.format(element))
                msg = 'Dependency cycle detected: {}'.format(element)
                warnings.warn(msg)
                cyclic_check.pop()
                yield element
                return
            for e in _solve_dependency(elem, depend_on, returned,
                                       cyclic_check):
                if e not in returned:
                    yield e
        cyclic_check.pop()
        yield element


def sorted_dependency(elements, depend_on, all=False):
    """依存関係を解決した並び順で返す
    :param elements: シーケンス
    :type elements: abc.Iterable
    :param depend_on: 引数を１つ取り、それが依存するオブジェクトのリストを
                      返す関数。返り値の最初の要素から再帰的に探索する。
    :type depend_on: types.FunctionType
    :param all: 依存関係にあるがelementsに含まれないものも返り値に含める。
    :return: elementsを並び替えたリスト
    :rtype: list
    """
    elements = tuple(elements)
    returned = set()
    result = []
    for element in elements:
        for elem in _solve_dependency(element, depend_on, returned):
            returned.add(elem)
            result.append(elem)

    if not all:
        elems = set(elements)
        return [elem for elem in result if elem in elems]
    else:
        return result


def mro(obj, function=None, _cyclic_check=None):
    """メソッド解決順序(Method Resolution Order)
    root側の物がリストの後ろの方になる
    """
    if not function:
        def function(obj):
            return obj.__bases__

    if _cyclic_check is None:
        _cyclic_check = []
    _cyclic_check.append(obj)
    result = [obj]

    sequence2d = []
    for item in function(obj):
        if item == obj:
            continue
        if item in _cyclic_check:
            msg = 'Dependency cycle detected: {}'.format(obj)
            warnings.warn(msg)
            _cyclic_check.pop()
            return tuple(result)
        sequence2d.append(list(mro(item, function, _cyclic_check)))

    while True:
        seq2d = [seq for seq in sequence2d if seq]
        if not seq2d:
            break

        # シーケンスの先頭の要素で、かつ全てのシーケンスの二番目以降に無い物
        head = None
        for seq in seq2d:
            head = seq[0]
            for s in seq2d:
                if head in s[1:]:
                    head = None
                    break
            if head:
                break
        if not head:
            raise TypeError('階層・依存関係に矛盾')

        result.append(head)
        for seq in seq2d:
            if seq[0] == head:
                seq.pop(0)

    _cyclic_check.pop()
    return tuple(result)


# オリジナル: http://code.activestate.com/recipes/577748-calculate-the-mro-of-a-class/
# def mro(*bases):
#     """Calculate the Method Resolution Order of bases using the C3 algorithm.
#
#     Suppose you intended creating a class K with the given base classes. This
#     function returns the MRO which K would have, *excluding* K itself (since
#     it doesn't yet exist), as if you had actually created the class.
#
#     Another way of looking at this, if you pass a single class K, this will
#     return the linearization of K (the MRO of K, *including* itself).
#     """
#     seqs = [list(C.__mro__) for C in bases] + [list(bases)]
#     res = []
#     while True:
#         non_empty = list(filter(None, seqs))
#         if not non_empty:
#             # Nothing left to process, we're done.
#             return tuple(res)
#         for seq in non_empty:  # Find merge candidates among seq heads.
#             candidate = seq[0]
#             not_head = [s for s in non_empty if candidate in s[1:]]
#             if not_head:
#                 # Reject the candidate.
#                 candidate = None
#             else:
#                 break
#         if not candidate:
#             raise TypeError("inconsistent hierarchy, no C3 MRO is possible")
#         res.append(candidate)
#         for seq in non_empty:
#             # Remove candidate.
#             if seq[0] == candidate:
#                 del seq[0]


# def mro(*objects):
#     """Method Resolution Order"""
#     def func(obj):
#         return obj.__mro__
#     return dro(objects, func, all=True)


def mro_test():
    # Run self-tests. Prints nothing if they succeed.
    O = object
    class SeriousOrderDisagreement:
        class X(O): pass
        class Y(O): pass
        class A(X, Y): pass
        class B(Y, X): pass
        bases = (A, B)

    try:
        x = mro(*SeriousOrderDisagreement.bases)
    except TypeError:
        pass
    else:
        print("failed test, mro should have raised but got %s instead" % (x,))

    class Example0:  # Trivial single inheritance case.
        class A(O): pass
        class B(A): pass
        class C(B): pass
        class D(C): pass
        tester = D
        expected = (D, C, B, A, O)

    class Example1:
        class F(O): pass
        class E(O): pass
        class D(O): pass
        class C(D, F): pass
        class B(D, E): pass
        class A(B, C): pass
        tester = A
        expected = (A, B, C, D, E, F, O)

    class Example2:
        class F(O): pass
        class E(O): pass
        class D(O): pass
        class C(D, F): pass
        class B(E, D): pass
        class A(B, C): pass
        tester = A
        expected = (A, B, E, C, D, F, O)

    class Example3:
        class A(O): pass
        class B(O): pass
        class C(O): pass
        class D(O): pass
        class E(O): pass
        class K1(A, B, C): pass
        class K2(D, B, E): pass
        class K3(D, A): pass
        class Z(K1, K2, K3): pass

        assert mro(A) == (A, O)
        assert mro(B) == (B, O)
        assert mro(C) == (C, O)
        assert mro(D) == (D, O)
        assert mro(E) == (E, O)
        assert mro(K1) == (K1, A, B, C, O)
        assert mro(K2) == (K2, D, B, E, O)
        assert mro(K3) == (K3, D, A, O)

        tester = Z
        expected = (Z, K1, K2, K3, D, A, B, C, E, O)

    for example in [Example0, Example1, Example2, Example3]:
        # First test that the expected result is the same as what Python
        # actually generates.
        assert example.expected == example.tester.__mro__
        # Now check the calculated MRO.
        assert mro(example.tester) == example.expected


def test_solve_dependence():
    """
           a
          /|
         b f g
        / \|/
       c   d
       |   |
       e   h
    :return: a, b, f, g, d, h, c, e
    """
    class Node:
        def __init__(self, name):
            self.name = name
            self.depend = []
        def __str__(self):
            return self.name
        def __repr__(self):
            return "Node('{}')".format(self.name)

    a = Node('a')
    b = Node('b')
    c = Node('c')
    d = Node('d')
    e = Node('e')
    f = Node('f')
    g = Node('g')
    h = Node('h')

    b.depend.append(a)
    c.depend.append(b)
    d.depend.extend((b, f, g))
    e.depend.append(c)
    f.depend.append(a)
    h.depend.append(d)

    # cyclic test
    # g.depend.append(h)

    elements = [h, a, b, c, d, e, f, g]

    result = sorted_dependency(elements, lambda node: node.depend)
    print(result)
    # [Node('a'), Node('b'), Node('f'), Node('g'), Node('d'), Node('h'),
    #  Node('c'), Node('e')]



def test_groupwith():
    key = lambda a, b: set(a).intersection(b)
    ls = []
    eq_(groupwith([('A', 'B'), ('C', 'D'), ('E', 'F')], key, None, ls),
        [[('A','B')], [('C', 'D')], [('E', 'F')]])
    eq_(ls, [[0], [1], [2]])

    ls = []
    eq_(groupwith([('A', 'B'), ('B', 'C'), ('C', 'E')], key, None, ls),
        [[('A','B'), ('B', 'C'), ('C', 'E')]])
    eq_(ls, [[0, 1, 2]])

    ls = []
    eq_(groupwith([('D', 'B'), ('B', 'C'), ('E', 'F'), ('A', 'E', 'B')], key, None, ls),
        [[('D', 'B'), ('B', 'C'), ('E', 'F'), ('A', 'E', 'B')]])
    eq_(ls, [[0, 1, 2, 3]])

    ls = []
    eq_(groupwith([('A', 'B'), ('C', 'D'), ('D', 'C'), ('B', 'A')], key, None, ls),
        [[('A', 'B'), ('B', 'A')], [('C', 'D'), ('D', 'C')]])
    eq_(ls, [[0, 3], [1, 2]])

    ls = [0, 1, 2, 3]
    data = {0: [2, 3], 1: [2, 3], 2: [0, 1], 3: [0, 1]}
    def func(a, b, data):
        return a in data[b] or b in data[a]
    eq_(groupwith(ls, func, data), [[0, 1, 2, 3]])


def test_generate_signature_bind_string():
    import inspect
    def hoge(a, b=100, *c, d=0, **e):
        return a, b, c, d, e
    sig = inspect.signature(hoge)
    text = generate_signature_bind_string(sig)
    eq_(text, '(a, b, *c, d=d, **e)')


def test_exec_local():
    l = {'a': 0, 'gen_func': None}
    d = exec_local('def hoge():\n    print(a)', globals(), l, True)
    print(d)
    l.clear()
    func = d['hoge']
    func()


def test():
    test_solve_dependence()
    # test_groupwith()
    # test_generate_signature_bind_string()
    # test_exec_local()
    mro_test()

if __name__ == '__main__':
    test()
