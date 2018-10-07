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


import builtins as _builtins
import types as _types
import inspect as _inspect
import functools as _functools
try:
    import cython as _cython
except ImportError:
    _cython = None

if __name__ == '__main__':
    import utils as _utils
else:
    from . import utils as _utils

__all__ = ('InvalidConditionError', 'CheckArgsError', 'CheckArgs')


_locals = locals  # 退避


class InvalidConditionError(Exception):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


class CheckArgsError(Exception):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text


class _List(list):
    pass


class _void:
    def __bool__(self):
        return False


class CheckArgs:
    """引数確認用のデコレータ。
    CheckArgs(*options, **conditions)

    checkargs = CheckArgs(name=str, value=((int, float),))
    @checkargs()
    def hoge(name, value):
        pass

    関数に条件で指定した引数がない場合は無視される
    checkargs = CheckArgs(name=str, value=((int, float),), options=str)
    @checkargs()
    def hoge(name):
        pass

    なおデコレートの際に空のlist,tuple,dict,setの何れかを渡すと
    その変数の条件を消すことが出来る
    checkargs = CheckArgs(name=str, value=((int, float),))
    @checkargs(name=[])
    def hoge(name, value):
        pass
    hoge(1, 2.0)

    options:
        CheckArgs(str, dict, bool, bool, [conditions...])
        順不同。但し１つ目のboolはwrap、２つ目はactiveとなる。
        str: replacement
            ビルトインやcythonでコンパイル済みの関数の場合に必要。
            これを元に仮の関数を作る。
            '(name, value=0.0)'

        dict: symbol_table
            eval(), exec() の引数のglobalsに渡す。
            指定されない場合、対象に __globals__ 属性が有ればそれを、
            無ければ globals() を用いる。

        bool: wrap
            偽だと関数をラップせずにそのまま返す。
            チェックが不要になり高速化したい場合に。
            checkargs = CheckArgs(False)
            @checkargs(a=int, b=str)
            def hoge(a, b):
                pass

        bool: active
            引数のチェックをしない。wrapと違い関数定義後に変更する事が出来る。
            wrapほどの高速化の効果は無い。

    conditions:
        name=condition
        or
        name=(condition, ...)

        class or (class, ...):
            isinstance()で判定。Noneの場合はtype(None)とする
        list:
            value in list
            valueがジェネレータなら常に真
        set:
            all([(ele in set) for ele in value])
            valueがジェネレータなら常に真
            valueが文字列なら偽
        dict:
            {name: condition, ...} or
            {name: (condition, ...), ...}
            **kwargs用。
            isinstance(value, (class1, class2)) を想定するなら
            {name: ((class1, class2),), ...} といった風にタプルで囲む。
            {name: (class1, class2), ...} と書くと
            isinstance(value, class1) and isinstance(value, class2)
            となってしまうので注意すること。
        function:
            引数を１つ受け取り真偽値を返す関数。
        str:
            'lambda ...' or 'def ...':
                関数を生成する。
            'and' or 'or' or '{0} or {1}':
                各判定の結果をeval()で結合する。str.format()の書式。
                'and' は '{} and {} and ...' となり、
                'or' は '{} or {} or ...' に変換される。
                この文字列が与えられなかった場合、'and'で結合される。
                @CheckArgs.checkargs(('value', '{0} or {1}', None, ['A', 'B']))
                def hoge(value):
                    pass
                この場合の処理はおおまかに下記のようになる
                ls = [isinstance(value, type(None)),
                      value in ['A', 'B']]
                result = eval('{0} or {1}'.format(ls))
    """

    _void = _void

    def _expand_var_positional(self, options, init=False):
        if init:
            replacement = symbol_table = None
            wrap = active = True
        else:
            replacement = self.replacement
            symbol_table = self.symbol_table
            wrap = self.wrap
            active = self.active
        wrap_found = False
        for value in options:
            if isinstance(value, str):
                replacement = value
            elif isinstance(value, dict):
                symbol_table = value
            elif isinstance(value, bool):
                if not wrap_found:
                    wrap = value
                    wrap_found = True
                else:
                    active = value
        args = {'replacement': replacement,
                'symbol_table': symbol_table,
                'wrap': wrap,
                'active': active}
        return args

    def __init__(self, *options, **conditions):
        """
        :param options:
            str: replacement
            dict: symbol_table
            bool: 1st: wrap, 2nd: active
        :param conditions:
            condition dict
        """
        args = self._expand_var_positional(options, init=True)
        self.replacement = args['replacement']
        self.symbol_table = args['symbol_table']
        self.wrap = args['wrap']
        self.active = args['active']
        self.conditions = conditions

    def _gen_arg_condition(self, conditions, symbol_table=None):
        arg_condition = _List()
        arg_condition.formatter = None
        arg_condition.source = conditions

        function_types = (_types.BuiltinFunctionType, _types.BuiltinMethodType,
                          _types.FunctionType, _types.LambdaType,
                          _types.MethodType)

        for condition in conditions:
            def gen(con, symbol_table):
                func = formatter = None

                # class type
                if con is None:
                    def func(value):
                        return value is None
                elif isinstance(con, tuple):
                    classes = tuple([(cls if cls is not None else type(None))
                                     for cls in con])

                    def func(value):
                        return isinstance(value, classes)
                elif _inspect.isclass(con):
                    def func(value):
                        return isinstance(value, con)

                # in
                elif isinstance(con, list):
                    # 引数がジェネレータなら常に真を返す
                    def func(value):
                        if isinstance(value, _types.GeneratorType):
                            return True
                        else:
                            return value in con

                # set in
                elif isinstance(con, set):
                    # 引数がジェネレータなら常に真を、strなら偽を返す
                    def func(value):
                        # list, tuple, set, dictを想定
                        if isinstance(value, _types.GeneratorType):
                            return True
                        elif isinstance(value, str):
                            return False
                        else:
                            return all(((ele in con) for ele in value))

                # **kwargs
                elif isinstance(con, dict):
                    d = {}
                    for name, prop_cons in con.items():
                        if not isinstance(prop_cons, tuple):
                            prop_cons = (prop_cons,)
                        d[name] = self._gen_arg_condition(prop_cons,
                                                          symbol_table)

                    def func(value):
                        result_all = []
                        for name, val in value.items():
                            if name in d:
                                ls = d[name]
                                results = [f(val) for f in ls]
                                if ls.formatter:
                                    r = eval(ls.formatter.format(*results),
                                             symbol_table)
                                else:
                                    r = all(results)
                                result_all.append(r)
                        return all(result_all)

                # function(str) / formatter
                elif isinstance(con, str):
                    if con.startswith('lambda '):
                        func = eval(con, symbol_table)
                    elif con.startswith('def '):
                        local_dict = {}
                        exec(con, symbol_table, local_dict)
                        if local_dict:
                            func = next(iter(local_dict.values()))
                        else:
                            msg = 'Cannot convert str -> Function' + con
                            raise InvalidConditionError(msg)
                    else:
                        formatter = con

                # function
                elif (isinstance(con, function_types) or
                      _cython and
                      _cython.typeof(con) == 'cython_function_or_method'):
                    func = con

                return func, formatter

            func, formatter = gen(condition, symbol_table)
            if func:
                arg_condition.append(func)
            if formatter:
                arg_condition.formatter = formatter

        # 'and' 'or' 以外のformatterを関数化
        formatter = arg_condition.formatter
        if formatter and formatter not in ('and', 'or'):
            try:
                text = 'def func('
                ls = ['a' + str(i) for i in range(len(arg_condition))]
                text += ', '.join(ls)
                text += '):\n'
                text += '    return '
                text += formatter.format(*ls) + '\n'
                # print(text)
                d = {}
                exec(text, globals(), d)
            except:
                msg = "bad formatter: '{}'".format(formatter)
                raise InvalidConditionError(msg)
            arg_condition.formatter = func = d['func']

        return arg_condition

    def _gen_arg_conditions(self, kwargs, signature, symbol_table=None):
        arg_conditions = {}
        for name, conditions in kwargs.items():
            if not (isinstance(conditions, tuple) and
                    conditions.__class__ == _builtins.tuple):
                conditions = (conditions,)

            param = signature.parameters[name]
            if param.kind != param.VAR_KEYWORD:
                for con in conditions:
                    if isinstance(con, dict):
                        msg = 'dict only used for **kwargs: {}={}'
                        raise InvalidConditionError(
                            msg.format(name, conditions))

            arg_condition = self._gen_arg_condition(conditions, symbol_table)
            arg_conditions[name] = arg_condition
        return arg_conditions

    def __call__(self, *options, **conditions):
        """引数にactiveが無いのは、インスタンス属性の active を参照する為"""
        args = self._expand_var_positional(options)
        replacement = args['replacement']
        _symbol_table = args['symbol_table']
        wrap = args['wrap']
        active = args['active']
        if conditions:
            if self.conditions:
                kwargs = self.conditions.copy()
                for k, v in conditions.items():
                    if k in kwargs:
                        if isinstance(v, (list, tuple, dict, set)):
                            if v.__class__ in (_builtins.list, _builtins.tuple,
                                               _builtins.dict, _builtins.set):
                                if not v:
                                    del kwargs[k]
                                    continue
                    kwargs[k] = v
            else:
                kwargs = conditions
        else:
            kwargs = self.conditions

        if not wrap:
            def wrapper(function):
                return function

            return wrapper

        # if symbol_table is None:
        #     symbol_table = globals()

        def wrapper(function):
            nonlocal _symbol_table
            if _symbol_table is None:
                if hasattr(function, '__globals__'):
                    symbol_table = function.__globals__
                else:
                    symbol_table = globals()
            else:
                symbol_table = _symbol_table

            if replacement:
                # 組込み型等の場合
                dummy = _utils.generate_function(
                    function.__name__, replacement, [], symbol_table)
                sig = _inspect.signature(dummy)
            else:
                sig = _inspect.signature(function)
            parameters_dict = dict(sig.parameters)
            parameters_tuple = tuple(sig.parameters.items())

            arg_conditions = self._gen_arg_conditions(kwargs, sig,
                                                      symbol_table)

            def check_args(local_symbol_table):
                # for name, param in sig.parameters.items():
                for name, param in parameters_tuple:
                    value = local_symbol_table[name]
                    if name not in arg_conditions:
                        continue

                    arg_condition = arg_conditions[name]
                    if (not arg_condition.formatter or
                                arg_condition.formatter == 'and'):
                        result = True
                        for f in arg_condition:
                            if not f(value):
                                result = False
                                break
                    elif arg_condition.formatter == 'or':
                        result = False
                        for f in arg_condition:
                            if f(value):
                                result = True
                                break
                    else:
                        results = [f(value) for f in arg_condition]
                        result = arg_condition.formatter(*results)

                    if not result:
                        condition = arg_condition.source
                        q = "'" if isinstance(value, str) else ''
                        text = ('Invalid argument.\n'
                                '    function   : {0}\n'
                                '                 {1}{2}\n'
                                '    argument   : {3} = {4}{5}{4}')
                        text = text.format(function, function.__name__, sig,
                                           name, q, value)
                        for i, c in enumerate(condition):
                            if i == 0:
                                text += '\n    conditions : ' + str(c)
                            else:
                                text += '\n                 ' + str(c)
                        raise CheckArgsError(text)

            # __globals__: 関数のグローバル変数の入った辞書 (への参照)。
            # __closure__: None または関数の個々の自由変数 (引数以外の変数) に
            #              対して値を結び付けているセル (cell) 群からなるタプル。
            #              コンパイル時にローカル変数として静的に定義されている
            #              変数だけ参照出来る。よってexec()で動的に生成した変数は
            #              対象にならない。
            #              globalスコープで関数を定義した場合も None となる。
            #
            # ※ locals()から動的に生成した変数を取得して同名のローカル変数に
            # 代入すると失敗する。
            # def fail():
            #     exec('x = 1')
            #     x = locals().get('x')
            #     print(x == 1)  # x is None
            # def success():
            #     exec('x = 1')
            #     y = locals().get('x')
            #     print(y == 1)
            #     locals_tmp = {}
            #     exec('x = 1', globals(), locals_tmp)
            #     y = locals_tmp.get('x')
            #     print(y == 1)
            #
            # 入れ子になった関数では、関数の__closure__が None となった時点で
            # 探索を切上げ、globalスコープの中を探索する。
            # 以下のコードはexecを抜けた後で、globalスコープ及びset_closure()の
            # ローカルスコープのみ用いた関数を生成する。

            wraps = _functools.wraps
            bind_string = _utils.generate_signature_bind_string(sig)

            if 0:
                exec_lines = [
                    'def gen_func({wraps}=wraps,',
                    '             {self}=self,',
                    '             {function}=function,',
                    '             {check_args}=check_args):',
                    '    @{wraps}({function})',
                    '    def {name}{args}:',
                    '        if {self}.active:',
                    '            {check_args}(__builtins__.locals())',
                    '        return {function}{bind_string}',
                    '    return {name}'
                ]
                # 変数が衝突しないように修正する
                names = {name: name for name in
                      ('wraps', 'self', 'function', 'check_args')}
                name = function.__name__
                for k in names:
                    while names[k] in sig.parameters or names[k] == name:
                        names[k] += '_'

                # 関数の生成
                exec_string = '\n'.join(exec_lines).format(
                    name=name, args=str(sig), bind_string=bind_string, **names)
                exec(exec_string, symbol_table, locals())
                func = locals()['gen_func']()
            else:
                symbol_names = {
                    name: name for name in
                    ('check_args', 'function', 'self', 'wraps', 'locals')}
                # 名前が衝突しないように修正する
                seen = set(sig.parameters)
                func_name = function.__name__
                while func_name in seen:
                    func_name += '_'
                seen.add(func_name)
                for name in symbol_names:
                    n = name
                    while n in seen:
                        n += '_'
                    seen.add(n)
                    symbol_names[name] = n

                ls = ["'{}': {}".format(n, n) for n in sig.parameters]
                args_dict = '{' + ' ,'.join(ls) + '}'
                code_str = (
                    '@{wraps}({function})\n'
                    'def {func_name}{args}:\n'
                    '    if {self}.active:\n'
                    '        {check_args}({args_dict})\n'
                    '    return {function}{bind_string}\n'
                ).format(func_name=func_name,
                         args=str(sig),
                         args_dict=args_dict,  # locals()の代わり
                         bind_string=bind_string,
                         **symbol_names)

                symbols = {symbol_names['wraps']: wraps,
                           symbol_names['function']: function,
                           symbol_names['self']: self,
                           symbol_names['check_args']: check_args,
                           symbol_names['locals']: _locals
                }

                result = _utils.exec_local(code_str, symbol_table, symbols)
                func = result[func_name]

            return func

        return wrapper

    @classmethod
    def checkargs(cls, *options, **conditions):
        func = cls(*options, **conditions)()
        return func


def _test():
    import time
    @CheckArgs.checkargs(False, a=int)
    def hoge(a, b, *c, d=0, **kwargs):
        x = 1 + 2
        # print(a, b, c, d, kwargs)
    @CheckArgs.checkargs(True, False, a=int)
    def piyo(a, b=1, *c, d=0, **kwargs):
        x = 1 + 2
        # print(a, b, c, d, kwargs)
    @CheckArgs.checkargs(a=(int, float, str, dict, '{} or {} or {} or {}'))
    def fuga(a, b=1, *c, d=0, **kwargs):
        x = 1 + 2
        # print(a, b, c, d, kwargs)

    # @_utils.profile('tottime', 20)
    # def tst(cnt):
    #     for i in range(cnt):
    #         fuga(1, 2, 3, 4, 9.87, x=100)
    # tst(10000)

    def tst(cnt):
        t = time.time()
        for i in range(cnt):
            hoge(1, 2, 3, 4, 9.87, x=100)
        print(time.time() - t)
        t = time.time()
        for i in range(cnt):
            piyo(1, 2, 3, 4, 9.87, x=100)
        print(time.time() - t)
        t = time.time()
        for i in range(cnt):
            fuga(1, 2, 3, 4, 9.87, x=100)
        print(time.time() - t)
    tst(100000)

    checkargs = CheckArgs(a=int)

    @checkargs(a=())
    def hoge(hoge, self=3, *self_, self__=0, **kwargs):
        x = 1 + 2
        # print(a, b, c, d, kwargs)


if __name__ == '__main__':
    _test()
