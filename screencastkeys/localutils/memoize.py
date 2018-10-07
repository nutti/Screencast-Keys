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


import pickle as _pickle
import hashlib as _hashlib
import functools as _functools
import inspect as _inspect
import collections as _collections
import itertools as _itertools
import types as _types


if __name__ == '__main__':
    import utils as _utils
else:
    from . import utils as _utils


__all__ = ('Memoize', )


class _void:
    def __bool__(self):
        return False


class _id_self:
    pass

class _self_cache:
    pass


exec_template = """\
def _memo_gen_func({wraps}=wraps,
                   {self}=self,
                   {function}=function,
                   {key}=key,
                   {cache}=cache,
                   {self_id_instance}=self_id_instance):
    @{wraps}({function})
    def {function_name}{args}:
        if {use_instance}:
            {id_of_instance} = id({args0})
            try:
                {current_cache} = {cache}[{id_of_instance}]
            except KeyError:
                {current_cache} = {cache}[{id_of_instance}] = {{}}
                {self_id_instance}[{id_of_instance}] = {args0}
        else:
            {current_cache} = {cache}

        if {use_func_param}:  # use_func_param
            {k} = {key}({function}, {bind_string})
        else:
            {k} = {key}({bind_string})

        if {self}.read:
            if {k} in {current_cache}:
                return {current_cache}[{k}]

        result = {function}({bind_string})
        if {self}.write:
            {current_cache}[{k}] = result

        return result

    return {function_name}
"""


def _is_instance(obj):
    # if not hasattr(obj, '__dict__'):
    #     return False
    if _inspect.isroutine(obj) or _inspect.isclass(obj):
        return False
    return True


class Memoize:
    """デコレータとして使用。
    キャッシュは関数毎に独立している。
    use_instance引数を真にする事でインスタンス毎にも独立させる事が出来る。
    デコレート前の関数は memoize.functions[function] で取得できる。
    memoize = Memoize()
    class Hoge:
        def __init__(self):
            pass
        @memoize(key=lambda self, a: a,
                 use_instance=True)
        def test(self, a):
            import random
            return random.randint(-1000, 1000)

    hoge1 = Hoge()
    hoge2 = Hoge()
    print(hoge1.test('A'))
    print(hoge1.test('A'))
    print(hoge1.test('B'))
    print(hoge2.test('A'))
    memoize.clear(hoge1)
    print(hoge1.test('A'))
    print(hoge2.test('A'))

    >>> -312
    >>> -312
    >>> 53
    >>> -256
    >>> 936
    >>> -256
    """

    @staticmethod
    def cache_key(*args, **kw):
        """キャッシュに格納する際のキーを作る。
        >> key = pickle.dumps((('hoge', [0,1,2]), {'edit': True}))
        >> key
        "((S'hoge'\np0\n(lp1\nI0\naI1\naI2\natp2\n(dp3\nS'piyo'\np4\nI01\nstp5\n."
        >> hashlib.sha1(key).hexdigest()
        '6f30c538ee4f2a96911c79559d2ef754db11aebd'
        """
        dumped_args = _pickle.dumps((args, kw))
        return _hashlib.sha512(dumped_args).hexdigest()

    @staticmethod
    def cache_key_ex(_func, *args, **kw):
        dumped_args = _pickle.dumps((args, kw))
        return _hashlib.sha512(dumped_args).hexdigest()

    def __init__(self, key=None, use_instance=False, use_func_param=False):
        """
        :param key: 辞書のキーを返す関数。引数はデコレート対象の関数に合わせる
        :type key: types.FunctionType -> T
        :param use_instance: id(self)でキャッシュを分割する。クラスメソッドには
            使わないこと。
        :type use_instance: bool
        :param use_func_param: key関数の引数の最初にデコレート対象の
            関数オブジェクトを渡す
        :type use_func_param: bool
        :rtype: types.FunctionType
        """

        self.key = key
        self.use_func_param = use_func_param
        self.use_instance = use_instance

        self.id_instance = {}  # {id(instance): instance, ...}
        self.func_cache = {}  # {ラップ前の関数: cache, ...}
        self.func_instance_cache = {}  # {ラップ前の関数: {id: cache, ...}, ...}
        self.functions = {}  # {ラップ済み: ラップ前, ...}

        # キャッシュからの読み込み・書き込みを一時的に切り替える。
        # 但しclear()時には無視される。
        self.read = True
        self.write = True
        # TODO: self毎にread, writeを切り替え出来るようにする

    def __call__(self, key=_void, use_instance=_void, use_func_param=_void):
        def _memoize(function):
            """ラップ後の関数の引数をラップ前のそれと同じにする為、ちょっと
            面倒な事をする
            """
            nonlocal self, key, use_func_param, use_instance  # local変数/global変数に存在しないから

            is_user_defined = hasattr(function, '__globals__')
            try:
                sig = _inspect.signature(function)
            except ValueError:
                is_user_defined = False
                sig = None

            wraps = _functools.wraps

            kw = {name: name for name in
                  ('wraps', 'self', 'function', 'key', 'cache',
                   'self_id_instance', 'id_of_instance', 'current_cache', 'k')}

            # 関数名と引数
            if is_user_defined:
                function_name = function.__name__
                function_args = str(sig)
                bind_string = _utils.generate_signature_bind_string(sig)
                bind_string = bind_string[1:-1]  # 先頭末尾の()を除去
                args0 = list(sig.parameters.keys())[0]  # 'self' or 'cls'
                # 変数が関数の引数と衝突をしないように修正する
                for k in kw:
                    while (kw[k] in sig.parameters or
                           kw[k] == function.__name__):
                        kw[k] += '_'
            else:
                function_name = '__memoize'
                function_args = '(*args, **kwargs)'
                bind_string = '*args, **kwargs'
                args0 = 'args[0]'

            # use_func_param
            if use_func_param is _void:
                use_func_param = self.use_func_param

            # key
            if key is _void:
                key = self.key
            if key is None:
                if use_func_param:
                    key = self.cache_key_ex
                else:
                    key = self.cache_key

            # cache
            if use_instance is _void:
                use_instance = self.use_instance
            if use_instance:
                cache = self.func_instance_cache[function] = {}
            else:
                cache = self.func_cache[function] = {}
            self_id_instance = self.id_instance

            # 関数の生成
            exec_string = exec_template.format(
                function_name=function_name,
                args=function_args,
                bind_string=bind_string,
                args0=args0,
                use_func_param=use_func_param,
                use_instance=use_instance,
                **kw)
            # print(exec_string)
            exec(exec_string, function.__globals__, locals())
            __memoize = locals()['_memo_gen_func']()

            __memoize._memoize = self

            self.functions[__memoize] = function

            return __memoize

        return _memoize

    @classmethod
    def memoize(cls, key=None, use_instance=False, use_func_param=False):
        inst = cls(key=key,
                   use_instance=use_instance,
                   use_func_param=use_func_param)

        return inst()

    def clear(self, obj=None):
        """キャッシュをクリアする。
        :param obj: 削除対象の関数を指定する。use_instanceが真の場合にメソッド、
            クラス、インスタンスが指定できる。
            メソッドを受け取った場合、そのインスタンスのメソッドのキャッシュに限り
            削除する。
            クラスを受け取った場合、そのクラスの全てのインスタンスメソッドの
            キャッシュを削除する。
            インスタンスを受け取った場合、そのインスタンスの全メソッドに関する
            キャッシュを削除する。
        """

        func = slf = cls = None

        if isinstance(obj, _types.MethodType) and _is_instance(obj.__self__):
            # __self__がクラスになっていたらclassmethod
            slf = obj.__self__
            func = self.functions.get(obj.__func__, obj.__func__)
        elif isinstance(obj, _types.FunctionType):
            func = self.functions.get(obj, obj)
        elif _inspect.isclass(obj):
            cls = obj
        elif _is_instance(obj):
            slf = obj

        if slf is not None:
            remove_ids = {id(slf)}
        elif cls is not None:
            remove_ids = {i for i, s in self.id_instance.items()
                          if isinstance(s, cls)}
        else:
            remove_ids = set()

        # clear cache
        removed_ids = set()
        if slf is not None or cls is not None:
            for f, cache in self.func_instance_cache.items():
                if func is None or f == func:
                    for i in (remove_ids & cache.keys()):
                        del cache[i]
                        removed_ids.add(i)
        elif func is not None:
            if func in self.func_cache:
                self.func_cache[func].clear()
            if func in self.func_instance_cache:
                cache = self.func_instance_cache[func]
                removed_ids.update(cache)
                cache.clear()
        else:
            for cache in self.func_cache.values():
                cache.clear()
            for cache in self.func_instance_cache.values():
                cache.clear()
            self.id_instance.clear()

        # clear self.id_instance
        all_ids = set(_itertools.chain.from_iterable(
            self.func_instance_cache.values()))
        for i in removed_ids:
            if i not in all_ids:
                del self.id_instance[i]


def _test():
    memoize = Memoize()

    class Hoge:
        def __init__(self):
            pass

        @memoize(key=lambda self, a: a,
                 use_func_param=False,
                 use_instance=True,
        )
        def func_a(self, a):
            import random
            return random.randint(-1000, 1000)

        @memoize(key=lambda self, a: a,
                 use_instance=True,
                 use_func_param=False,
        )
        def func_b(self, a):
            import random
            return random.randint(-1000, 1000)

    hoge1 = Hoge()
    hoge2 = Hoge()

    # memoize test
    assert hoge1.func_a('A1') != hoge1.func_a('A2')
    assert hoge1.func_a('A1') == hoge1.func_a('A1')
    assert hoge1.func_b('A1') != hoge1.func_b('A2')
    assert hoge1.func_b('A1') == hoge1.func_b('A1')
    assert hoge1.func_a('A1') != hoge1.func_b('A1')
    assert hoge1.func_a('A1') != hoge2.func_a('A1')

    # clear test: instance
    a = hoge1.func_a('A')
    b = hoge1.func_b('B')
    c = hoge2.func_a('C')
    memoize.clear(hoge1)
    assert a != hoge1.func_a('A')
    assert b != hoge1.func_b('B')
    assert c == hoge2.func_a('C')

    # clear test: class
    a = hoge1.func_a('A')
    b = hoge1.func_b('B')
    c = hoge2.func_a('C')
    memoize.clear(Hoge)
    assert a != hoge1.func_a('A')
    assert b != hoge1.func_b('B')
    assert c != hoge2.func_a('C')

    # clear test: method
    a = hoge1.func_a('A')
    b = hoge1.func_b('B')
    c = hoge2.func_a('C')
    memoize.clear(hoge1.func_a)
    assert a != hoge1.func_a('A')
    assert b == hoge1.func_b('B')
    assert c == hoge2.func_a('C')

    # clear test: function
    a = hoge1.func_a('A')
    b = hoge1.func_b('B')
    c = hoge2.func_a('C')
    memoize.clear(Hoge.func_a)
    assert a != hoge1.func_a('A')
    assert b == hoge1.func_b('B')
    assert c != hoge2.func_a('C')

    # clear test: all
    a = hoge1.func_a('A')
    b = hoge1.func_b('B')
    c = hoge2.func_a('C')
    memoize.clear()
    assert a != hoge1.func_a('A')
    assert b != hoge1.func_b('B')
    assert c != hoge2.func_a('C')


if __name__ == '__main__':
    _test()
