# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software; you can redistribute it and/or
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


import math
import re
from collections import namedtuple, OrderedDict
import decimal
from decimal import Decimal
D = Decimal
from fractions import Fraction
from . import utils as _utils


class UnitError(ValueError):
    def __init__(self, value=''):
        self.value = value

    def __str__(self):
        return repr(self.value)


class _void:
    def __bool__(self):
        return False


# B_UNIT_DEF_NONE
UNIT_NONE = 0
# B_UNIT_DEF_SUPPRESS
# Use for units that are not used enough to be translated into for common use
UNIT_SUPPRESS = 1 << 0
# B_UNIT_DEF_TENTH
# Display a unit even if its value is 0.1, eg 0.1mm instead of 100um
UNIT_TENTH = 1 << 1
# base unit
UNIT_BASE = 1 << 2

# source/blender/blenkernel/intern/unit.c
# Unit = namedtuple('Unit', ('name', 'plural', 'symbol', 'symbol_alt',
#                            'display', 'scalar', 'flag'))
Unit = namedtuple('Unit', ('symbol', 'scalar', 'flag', 'symbol_alt'))
# _default_unit = Unit('', '', '', None, '', D(1), None)


class Units(list):
    """
    >>> unit_to_num('1m 2cm 3.4mm', 'mixed')
    1.0234
    >>> units = metric_units.copy()
    >>> units.extend([['bu', 1.0], ['px', 10.0]])
    >>> units.update()
    >>> unit_to_num('1m 2cm 3.4mm + 5bu + 6px', units)
    66.0234
    """
    UNIT_NONE = 0
    UNIT_SUPPRESS = 1 << 0
    UNIT_TENTH = 1 << 1
    UNIT_BASE = 1 << 2

    def __init__(self, elements=()):
        super().__init__(())

        # {symbol: Unit, ...}
        self.symbols = OrderedDict()
        # {symbol: Unit, symbol_alt: Unit, ...}
        self.all_symbols = OrderedDict()
        # {symbol: Unit, ...}  ※UNIT_SUPPRESSでは無い物
        self.basic_symbols = OrderedDict()

        self.base = None

        self.update(elements)

    def update(self, elements=None):
        """要素を変更した際に呼ぶ"""
        # 自身の要素を更新
        if elements is None:
            elements = list(self)
        else:
            if isinstance(elements, dict):
                elements = [Unit(symbol, scalar, UNIT_NONE, None)
                            for symbol, scalar in elements.items()]
            elif isinstance(elements, (list, tuple)):
                pass
            else:
                raise TypeError()
        self.clear()
        for i, elem in enumerate(elements):
            if isinstance(elem, Unit):
                self.append(elem)
            else:
                # [[symbol, scalar[, flag, symbol_alt]], ...]
                symbol, scalar, *options = elem
                symbol_alt = None
                flag = 0
                for option in options:
                    if isinstance(option, int):
                        flag = option
                    else:
                        symbol_alt = option
                self.append(Unit(symbol, scalar, flag, symbol_alt))

        # symbols, basic_symbols, all_symbolsの更新
        # symbolに重複が合った場合、先頭の方が優先される
        self.symbols.clear()
        self.basic_symbols.clear()
        self.all_symbols.clear()
        symbols = {}
        all_symbols = {}
        for unit in self:
            if unit.symbol not in symbols:
                symbols[unit.symbol] = unit
            if unit.symbol not in all_symbols:
                all_symbols[unit.symbol] = unit
            if unit.symbol_alt and unit.symbol_alt not in all_symbols:
                all_symbols[unit.symbol_alt] = unit
        # scalarの大きい順に並び替え
        # all_symbols
        ls = sorted(all_symbols, key=lambda name: -all_symbols[name].scalar)
        for symbol in ls:
            self.all_symbols[symbol] = all_symbols[symbol]
        # symbols, basic_symbols
        ls = sorted(symbols, key=lambda name: -symbols[name].scalar)
        for symbol in ls:
            self.symbols[symbol] = symbols[symbol]
            if symbols[symbol].flag & UNIT_SUPPRESS == 0:
                self.basic_symbols[symbol] = symbols[symbol]

        # baseの更新
        for unit in self:
            if unit.flag & UNIT_BASE:
                self.base = unit
                break
        else:
            self.base = None

    def copy(self):
        return self.__class__(self)

    def is_basic(self, unit):
        """ユーザー定義のものか、SUPPRESSフラグが立ってない場合に真を返す。
        :param unit: unitか、symbol若しくはsymbol_altを表す文字列
        :type unit: Unit | str
        :rtype: bool
        """
        if isinstance(unit, Unit):
            return unit.flag & UNIT_SUPPRESS == 0
        elif unit in self.all_symbols:
            return self.all_symbols[unit].flag & UNIT_SUPPRESS == 0
        else:
            raise ValueError("'{}' not in Units".format(unit))

    def scalar(self, unit):
        # if name and not isinstance(name, str):
        #     raise TypeError('must be str, not {}'.format(str(type(name))))
        if isinstance(unit, Unit):
            return unit.scalar
        elif unit in self.all_symbols:
            return self.all_symbols[unit].scalar
        else:
            raise ValueError("'{}' not in Units".format(unit))

    def symbol(self, name):
        """シンボルからUnitを探して返す
        :param name: symbolかsymbol_alt
        :type name: str
        :rtype: Unit
        """
        if name in self.all_symbols:
            return self.all_symbols[name].symbol
        else:
            return None

    def next_basic(self, unit, use_current=True):
        """次のsymbolを返す。SUPPRESSは無視される。
        :param unit: Unitかsymbolを表す文字列。symbol_altは不可
        :type: unit: Unit | str
        :param use_current: 偽ならunitの次から検索する
        :type use_current: bool
        :rtype: str
        """
        if isinstance(unit, Unit):
            name = unit.symbol
        else:
            name = unit
            if name not in self.symbols:
                raise ValueError("'{}' not in self.symbols".format(name))

        symbols = list(self.symbols)
        i = symbols.index(name)
        max_i = len(self) - 1
        if not use_current:
            if i == max_i:
                return None
            i += 1
            name = symbols[i]
        while not self.is_basic(name):
            if i == max_i:
                return None
            i += 1
            name = symbols[i]
        return name

    def unit_to_num(self, string, scale_length=1, use_decimal=False):
        kwargs = dict(locals())
        del kwargs['self']
        kwargs['unit_system'] = self
        return unit_to_num(**kwargs)

    def num_to_unit(
            self, value, scale_length=1, use_separate=True,
            start=None, end='mm', verbose=False, rounding_exp=None,
            rounding=None, normalize=False, eps=None, use_decimal=False):
        kwargs = dict(locals())
        del kwargs['self']
        kwargs['unit_system'] = self
        return num_to_unit(**kwargs)


# ('name', 'plural', 'symbol', 'symbol_alt', 'display', 'scalar', 'flag'))
# metric_units = Units([
#     ('kilometer', 'kilometers', 'km',  None, 'Kilometers',
#      D('1e3'), 0),
#     ('hectometer', 'hectometers', 'hm',  None, '100 Meters',
#      D('1e2'), SUPPRESS),
#     ('dekameter', 'dekameters', 'dam', None, '10 Meters',
#      D('1e1'), SUPPRESS),
#     ('meter', 'meters', 'm', None, 'Meters',
#      D('1'), BASE),  # base unit
#     ('decimeter', 'decimeters', 'dm',  None, '10 Centimeters',
#      D('1e-1'), SUPPRESS),
#     ('centimeter', 'centimeters', 'cm',  None, 'Centimeters',
#      D('1e-2'), 0),
#     ('millimeter', 'millimeters', 'mm',  None, 'Millimeters',
#      D('1e-3'), TENTH),
#     ('micrometer', 'micrometers', 'µm', 'um', 'Micrometers',
#      D('1e-6'), 0),  # U+00B5 "µ: micro sign"
#     ('nanometer', 'Nanometers', 'nm', None, 'Nanometers',
#      D('1e-9'), 0),
#     ('picometer', 'Picometers', 'pm', None, 'Picometers',
#      D('1e-12'), 0),
# ])
#
# imperial_units = Units([
#     ('mile', 'miles', 'mi', 'm', 'Miles', D('1609.344'), 0),
#     ('furlong', 'furlongs', 'fur', None, 'Furlongs', D('201.168'), SUPPRESS),
#     ('chain', 'chains', 'ch', None, 'Chains', D('20.1168'), SUPPRESS),
#     ('yard', 'yards', 'yd', None, 'Yards', D('0.9144'), SUPPRESS),
#     ('foot', 'feet', '\'', 'ft', 'Feet', D('0.3048'), BASE),  # base unit
#     ('inch', 'inches', '"', 'in', 'Inches', D('0.0254'), 0),
#     ('thou', 'thou', 'thou', 'mil', 'Thou', D('0.0000254'), 0),
# ])

metric_units = Units(
    [('km', D('1e3'), UNIT_NONE, None),
     ('hm', D('1e2'), UNIT_SUPPRESS, None),
     ('dam', D('1e1'), UNIT_SUPPRESS, None),
     ('m', D('1'), UNIT_BASE, None),  # base unit
     ('dm', D('1e-1'), UNIT_SUPPRESS, None),
     ('cm', D('1e-2'), UNIT_NONE, None),
     ('mm', D('1e-3'), UNIT_TENTH, None),
     ('µm', D('1e-6'), UNIT_NONE, 'um'),  # U+00B5 "µ: micro sign"
     ('nm', D('1e-9'), UNIT_NONE, None),
     ('pm', D('1e-12'), UNIT_NONE, None),
     ])

imperial_units = Units([
    ('mi', D('1609.344'), UNIT_NONE, 'm'),
    ('fur', D('201.168'), UNIT_SUPPRESS, None),
    ('ch', D('20.1168'), UNIT_SUPPRESS, None),
    ('yd', D('0.9144'), UNIT_SUPPRESS, None),
    ('\'', D('0.3048'), UNIT_BASE, 'ft'),  # base unit
    ('"', D('0.0254'), UNIT_NONE, 'in'),
    ('thou', D('0.0000254'), UNIT_NONE, 'mil'),
])

mixed_units = Units(metric_units + imperial_units)

empty_units = Units([])


def _get_units_from_string(unit_system):
    unit_system = unit_system.lower()
    if unit_system == 'metric':
        return metric_units
    elif unit_system == 'imperial':
        return imperial_units
    elif unit_system == 'mixed':
        return mixed_units
    else:
        return empty_units


###############################################################################
# unit_to_num()
###############################################################################
def unit_to_num(string, unit_system='mixed', scale_length=1, use_decimal=False):
    """単位付きの文字列を数値に変換する。失敗したらNoneを返す
    :type string: str
    :param unit_system: 'metric' or 'imperial' or 'mixed'(両方有効) or Units.
        それ以外だと単位の置換を行わず、文字列をそのままeval()に渡す
    :type unit_system: str | Units
    :param scale_length: 単位はscale_lengthで割られる。この引数はDecimalの引数
        として有効な値が使える。
        unit_to_num('2m', scale_length=1) -> 2
        unit_to_num('2m', scale_length=2) -> 1
        unit_to_num('10bu', units={'bu': 2}, scale_length=2) -> 10
    :type scale_length: int | float | Decimal | str| list | tuple
    :param use_decimal: decimalモジュールを使用する。浮動小数点数の箇所を
        Decimal()で囲う。
        '1m 2.3cm 4e-5mm'
        -> 1m (Decimal(str(2.3)))cm (Decimal(str(4e-5)))mm
        -> (1 * Decimal(str(1)) / Decimal(str(1)) + \
           (Decimal(str(2.3))) * Decimal(str(0.01)) / Decimal(str(1)) + \
           (Decimal(str(4e-5))) * Decimal(str(0.001)) / Decimal(str(1)))
        -> 1.02300004
        但し、演算結果が浮動小数点数になる場合はエラーとなる。
        '1m (2 / 3)cm'
        -> (1 * Decimal(str(1)) / Decimal(str(1)) + \
           (2 / 3) * Decimal(str(0.01)) / Decimal(str(1)))
        この場合は、Decimal型を渡すことでエラーを回避できる。
        '1m (Decimal((0, (2,), 0)) / 3)cm'
        ※ ' " はinch, foot に使われるので Decimal('2') とは出来無い
    :type use_decimal: bool
    :rtype int | float | Decimal | None
    """

    if not isinstance(scale_length, (int, float, Decimal, str, list, tuple)):
        raise TypeError()

    if isinstance(unit_system, str):
        units = _get_units_from_string(unit_system)
    elif isinstance(unit_system, Units):
        units = unit_system
    else:
        units = empty_units
    unit_names = units.all_symbols.copy()

    if use_decimal:
        pattern = '(^|(?<=[^a-zA-Z_]))' + \
                  '(?P<float>(\d+\.?\d*|\d*\.\d+)(?P<e>[eE][+-]?\d+|))'# + \
                  # '(?=[^a-zA-Z_]|$)'
        def func(match):
            float_string = match.group('float')
            if '.' in float_string or match.group('e'):
                return '(Decimal(str(' + float_string + ')))'
            else:
                return float_string
        string = re.sub(pattern, func, string)

    bracket_indices = _utils.find_brackets(string, quotations=[], old_style=True)
    for st, ed in bracket_indices:
        if st is None or ed is None:
            bracket_indices = None
            break

    unit_spans = []  # [[match, start, end], ...]
    if unit_names:
        pattern = '(^|(?<=[^a-zA-Z_]))(?P<unit>' + \
                  '|'.join(unit_names.keys()) + ')(?=[^a-zA-Z_]|$)'
        unit_matches = list(re.finditer(pattern, string))
        for i, unit_match in enumerate(unit_matches):
            part_string = string[:unit_match.start()]
            match = re.match('(.*?)(\d+\.?\d*|\d*\.\d+)([eE][+-]?\d+|)\s*$',
                             part_string)
            if match:
                # 単位の直前(スペースの有無は問わず)が数字
                unit_spans.append([unit_match, match.start(2), match.end(3)])
            elif bracket_indices:
                match = re.match('.*?(\))\s*$', part_string)
                # 単位の直前(スペースの有無は問わず)が括弧
                if match:
                    bracket_close = match.start(1)
                    for st, ed in bracket_indices:
                        if ed - 1 == bracket_close:
                            unit_spans.append([unit_match, st, ed])
                            break

    replaces = []
    connected_unit_spans = []  # temp
    for i, elem in enumerate(unit_spans):
        connected_unit_spans.append(elem)

        match, _start, _end = elem

        # 次のマッチとの間に文字が無ければ繋がっていると見做し、
        # connected_unit_spansに要素を追加していく
        if i == len(unit_spans) - 1:
            connected_next = False
        else:
            next_start = unit_spans[i + 1][1]
            connected_next = not bool(string[match.end(): next_start].strip())
        if connected_next:
            continue

        # connected_unit_spansを処理する
        unit_string = '('
        for j, (match, start, end) in enumerate(connected_unit_spans):
            if j != 0:
                unit_string += ' + '
            scalar = units.scalar(match.group('unit'))
            unit_string += string[start: end] + ' * '
            if use_decimal:
                unit_string += 'Decimal(str(' + str(scalar) + ')) / ' \
                             'Decimal(str(' + str(scale_length) + '))'
            else:
                unit_string += str(scalar) + ' / ' + str(scale_length)
        unit_string += ')'

        replace_start = connected_unit_spans[0][1]
        replace_end = connected_unit_spans[-1][0].end()
        replaces.append([replace_start, replace_end, unit_string])
        connected_unit_spans.clear()

    # 置換。string -> eval_string
    length = len(string)
    eval_string = string
    for start, end, unit_string in replaces:
        offset = len(eval_string) - length
        head = eval_string[:start + offset]
        tail = eval_string[end + offset:]
        eval_string = head + unit_string + tail

    # eval()
    try:
        result = eval(eval_string)
    except Exception:
        result = None
    if not isinstance(result, (int, float, complex, D, Fraction)):
        result = None
    return result


###############################################################################
# float用関数
###############################################################################
def _rounded_float_mantissa(value, rounding_exp=None,
                            rounding=decimal.ROUND_HALF_EVEN):
    """expで指定した指数でvalueを丸め、その数値の仮数部をintで返す。
    これに 10 ** exp を掛けると丸めたfloatが得られる。
    >>> exp = -1
    >>> x = _rounded_float_mantissa(-0.16, exp)
    >>> x
    2
    >>> x * 10 ** exp
    -0.2

    :type value: int | float
    :type rounding_exp: int
    :param rounding: 'ROUND_HALF_EVEN', 'ROUND_UP', 'ROUND_DOWN',
        'ROUND_CEILING', 'ROUND_FLOOR', 'ROUND_05UP', 'ROUND_HALF_UP',
        'ROUND_HALF_DOWN'
    :type rounding: str
    :return: 仮数部を表す数字。
    :rtype: int
    """
    if rounding_exp is None:
        rounding_exp = 0
    value /= 10 ** rounding_exp

    if not rounding:
        rounding = decimal.ROUND_HALF_EVEN
    if rounding == decimal.ROUND_HALF_EVEN:
        val = round(value)
    elif rounding == decimal.ROUND_HALF_UP:
        f, _i = math.modf(value)
        if f == 0.5:
            val = math.copysign(math.ceil(abs(value)), value)
        else:
            val = round(value)
    elif rounding == decimal.ROUND_HALF_DOWN:
        f, _i = math.modf(value)
        if f == 0.5:
            val = math.copysign(math.floor(abs(value)), value)
        else:
            val = round(value)
    elif rounding == decimal.ROUND_05UP:
        val = math.copysign(math.floor(abs(value)), value)
        if val % 5 == 0.0 or val % 10 == 0.0:
            val += 1
    elif rounding == decimal.ROUND_UP:
        val = math.copysign(math.ceil(abs(value)), value)
    elif rounding == decimal.ROUND_DOWN:
        val = math.copysign(math.floor(abs(value)), value)
    elif rounding == decimal.ROUND_CEILING:
        val = math.ceil(value)
    elif rounding == decimal.ROUND_FLOOR:
        val = math.floor(value)
    else:
        raise ValueError("invalid <rounding> argument. got " + str(rounding))
    return int(val)


def _mantissa_exp_to_str(mantissa, exp, normalize=False):
    """floatを表す仮数部と指数部を文字列に変換する。
    :param mantissa: floatを表す仮数部
    :type mantissa: int
    :param exp: floatを表す指数部
    :type exp: int
    :param normalize: 小数部右端に連続するの0を除去する。0.10 -> 0.1, 0.00 -> 0
    :type normalize: bool
    """
    if exp >= 0:
        if mantissa == 0:
            return '0'
        else:
            return str(int(mantissa)) + '0' * exp
    else:
        m = str(abs(int(mantissa)))
        if abs(exp) >= len(m):
            t = '0.' + '0' * (-exp - len(m)) + m
        else:
            i = len(m) + exp
            t = m[:i] + '.' + m[i:]
        if mantissa < 0:
            t = '-' + t
        # 小数部の0を消す
        if normalize:
            while '.' in t and (t[-1] == '0' or t[-1] == '.'):
                t = t[:-1]
        return t


"""未使用"""
def _round_float(value, rounding_exp=None, rounding=None):
    if rounding_exp is None:
        rounding_exp = 0
    mantissa = _rounded_float_mantissa(value, rounding_exp, rounding)
    return mantissa * 10 ** rounding_exp


###############################################################################
# num_to_unit()
###############################################################################
def _round_decimal(value, rounding_exp=None, rounding=None):
    """
    :param value:
    :type value:
    :param rounding_exp: 0以下の値  # TODO: 0以上にも対応
    :type rounding_exp: int
    :param rounding: Decimal.quantize()のrounding引数
    :type rounding: str | None
    :rtype: Decimal
    """
    # 整数部分の桁数を求める
    _sign, digits, e = value.as_tuple()
    if e >= 0:
        num = len(digits) + e
    else:
        num = max(0, len(digits) + e)

    if rounding_exp is None:
        exp = 0
    else:
        exp = rounding_exp
    ctx = decimal.getcontext()
    prec = ctx.prec
    ctx.prec = max(1, num, num - exp + 1)  # +1は繰り上げで桁が増えるので

    if rounding_exp is not None:
        # quantize()はas_tuple()における指数を揃えたものを返す
        # e.g. Decimal('1234.5').quantize(Decimal('1e1')) -> Decimal('1.23E+3')
        value = value.quantize(D('1e' + str(rounding_exp)), rounding)
        # if rounding_exp > 0:  # TODO: 必要なさそうなので削除。要確認
        #     value = value.quantize(Decimal('0'))

    ctx.prec = prec
    return value


def _removed_exponent_string(value):
    """指数表記を用いない文字列を返す。Decimal('1.23E+4') -> '12300'
    仮数が0で指数が正なら正規化を行う。
    (例) Decimal('-0E+6') -> '-0', Decimal('0E-4') -> '0.000'
    :type value: Decimal
    :rtype: str
    """
    sign, digits, exp = value.as_tuple()
    if digits == (0,) and exp > 0:  # 0E+6 -> 0
        exp = 0
    num = ''.join([str(i) for i in digits])
    if exp >= 0:
        num += '0' * exp
    else:
        e = -exp
        if e >= len(num):
            num = '0.' + '0' * (e - len(num)) + num
        else:
            num = num[:exp] + '.' + num[exp:]
    if sign:
        num = '-' + num
    return num


def _rounding_exp_from_string(units, scalar, rounding_exp):
    """与えられたsymbolに対応する丸めを行う際の指数を返す。
    rounding_expがsymbolを表すstrではなくintならそのまま返す。
    (units, 0.1, 'mm') -> -2, (units, 1.0, 'km') -> 0
    :type scalar: int | float | Decimal
    :type rounding_exp: int | str
    """
    if isinstance(rounding_exp, str):  # unit symbol
        f = units.scalar(rounding_exp)
        if f is not None:
            if isinstance(scalar, Decimal):
                rounding_exp = (f / scalar).adjusted()
            else:
                e = math.log10(float(f) / scalar)
                rounding_exp = math.floor(e)
            # TODO: 仕様変更により確認必要
            # rounding_exp = min(rounding_exp, 0)
        else:
            rounding_exp = None
    return rounding_exp


def _divmod_eps(a, b, eps):
    """div, mod = divmod(a, b)を行い、modがeps以内であれば誤差と見做し、
    mod = 0とし、a,bの符号により必要であればdivを±1する。
    Decimalを使う場合、a, b, eps の全てがDecimalでないといけない。
    >>> _divmod_eps(10.1, 1, 0.05))
    (10.0, 0.09999999999999964)
    >>> _divmod_eps(10.1, 1, 1))
    (10.0, 0.0)
    >>> _divmod_eps(-10.9, 1, 1))
    (-11.0, -0.0)
    >>> _divmod_eps(D('-10.9'), D(-1), D(1)))
    (Decimal('11'), Decimal('-0.0'))
    >>> _divmod_eps(-10.1, -1, 1))
    (10.0, -0.0)

    :type a: int | float | Decimal
    :type b: int | float | Decimal
    :param eps: 誤差と見做す値。正の数でないといけない。Noneだと処理を行わない
    :type eps: int | float | Decimal | None
    :rtype: (int, int | float) | (Decimal, Decimal)

    NOTE: A, B = divmod(X, Y)
          Decimal:     A: X / Y の符号, B: Xの符号  # math.fmod()もこの規則
          int / float: A: X / Y の符号, B: Yの符号
    Decimalでのdivmodとfloatでの//の結果を同じにする為、絶対値で計算する
    """

    is_decimal = isinstance(a, D)
    neg_a = a < 0
    neg_b = b < 0
    a = abs(a)
    b = abs(b)
    if is_decimal:
        div, mod = divmod(a, b)
    else:
        div = a // b
        mod = math.fmod(a, b)
    if eps is not None:
        eps = min(abs(eps), b / 2)
        if mod <= eps or mod >= b - eps:
            if mod >= b / 2:
                div += 1
            if is_decimal:
                mod = D('0').quantize(mod)  # quantize()は必要か?
            elif isinstance(a, float):
                mod = 0.0
            else:
                mod = 0
    if neg_a ^ neg_b:
        div *= -1
    if neg_a:
        mod *= -1
    return div, mod


def _num_to_unit_single(
        value, unit_system, base_unit=None, scale_length=1, rounding_exp=None,
        rounding=None, normalize=False, eps=None, use_decimal=True):
    if use_decimal:
        value = D(value) * D(scale_length)
    else:
        value = float(value) * float(scale_length)
    if isinstance(unit_system, str):
        units = _get_units_from_string(unit_system)
    else:
        units = unit_system

    unit_name = quot = None
    if base_unit:
        name = units.symbol(base_unit)
        if name is not None:
            unit_name = name
            scalar = units.scalar(base_unit)
            if not use_decimal:
                scalar = float(scalar)
            quot = value / scalar
    else:
        if value == 0:
            if use_decimal:
                # TODO: dicmalでも単位にBASEの物を使う？
                for name in units.basic_symbols:
                    scalar = units.scalar(name)
                    q = value / scalar
                    if unit_name and q.as_tuple()[2] > 0:
                        break
                    unit_name = name
                    quot = q
            else:
                if units.base:
                    unit_name = units.base.symbol
                    quot = 0.0
                else:
                    for unit_name in units.basic_symbols:
                        scalar = units.scalar(unit_name)
                        break
                    quot = 0.0

        else:
            last_symbol = list(units.basic_symbols)[-1]
            for name in units.basic_symbols:
                scalar = units.scalar(name)
                if not use_decimal:
                    scalar = float(scalar)
                q = value / scalar
                if eps is not None:
                    div, mod = _divmod_eps(value, scalar, eps)
                    if mod == 0:
                        q = div
                if abs(q) >= 1 or name == last_symbol:
                    unit_name = name
                    quot = q
                    break

    scalar = units.scalar(unit_name)
    rounding_exp = _rounding_exp_from_string(units, scalar, rounding_exp)

    if use_decimal:
        if rounding_exp is not None:
            quot = _round_decimal(quot, rounding_exp, rounding)
            if normalize:
                quot = quot.normalize()

        # 指数を用いない表現に変換
        s = _removed_exponent_string(quot)
    else:
        if rounding_exp is not None:
            mantissa = _rounded_float_mantissa(quot, rounding_exp, rounding)
            s = _mantissa_exp_to_str(mantissa, rounding_exp, normalize)
        else:
            s = str(quot)

    return s + unit_name


def num_to_unit(
        value, unit_system='metric', scale_length=1, use_separate=True,
        start=None, end='mm', verbose=False, rounding_exp=None, rounding=None,
        normalize=False, eps=None, use_decimal=False):
    """
    :param value: Decimalの引数として有効な値である事
    :type value: int | float | str | tuple | Decimal
    :param unit_system: 'metric' or 'imperial' or Units
    :type unit_system: str | Units
    :param scale_length: Decimalの引数として有効な値。
        num_to_unit(1, scale_length=2) -> 2m
    :type scale_length: int | float | Decimal | str| list | tuple
    :param use_separate: 複数の単位で表す。引数startで単位の指定が可能。
        e.g. True: '1m 23cm 4mm', False: '1.234m'
    :type use_separate: bool
    :param start: num_to_unit('123.456', start='cm') -> 12345cm 6mm
        num_to_unit('123.456', use_separate=True, start='')   -> 123.456m
        num_to_unit('123.456', use_separate=True, start='km') -> 0.123456km
        SUPPRESSならより小さい単位に変更する
    :type start: str
    :param end: num_to_unit('123.456', end='cm') -> 123m 45.6cm
        SUPPRESSならより小さい単位に変更する
    :type end: str
    :param verbose: 0を省略しない。True -> '1km 0m 0cm 2mm'
        [True, False, True] -> '0km 1m 2cm 0mm'
    :type verbose: bool | tuple[bool] | list
    :param rounding_exp: 丸める際の指数(0以下)。symbolかsymbol_altも使える。
    :type rounding_exp: int | str | None
    :param rounding:
        decimal.ROUND_CEILING: Infinity 方向に丸める。
        decimal.ROUND_DOWN: ゼロ方向に丸める。
        decimal.ROUND_FLOOR: -Infinity 方向に丸める。
        decimal.ROUND_HALF_DOWN: 近い方に、引き分けはゼロ方向に向けて丸める。
        decimal.ROUND_HALF_EVEN: 近い方に、引き分けは偶数整数方向に向けて丸める。
        decimal.ROUND_HALF_UP: 近い方に、引き分けはゼロから遠い方向に向けて丸める。
        decimal.ROUND_UP: ゼロから遠い方向に丸める。
        decimal.ROUND_05UP: ゼロ方向に丸めた後の最後の桁が 0 または 5 ならば
            ゼロから遠い方向に、そうでなければゼロ方向に丸める。
    :type rounding: str | None
    :param normalize: 小数部分右側の0を除去する。0.0 -> 0, 1.2300 -> 1.23
    :type normalize: bool
    :param eps: 浮動小数点数の誤差と見做す。Decimalの引数として有効な
        正の値である事。
    :type eps: float | str | tuple | Decimal | None
    """

    if not use_separate:
        return _num_to_unit_single(
            value, unit_system, start, scale_length, rounding_exp, rounding,
            normalize, eps, use_decimal)

    if use_decimal:
        value = D(value) * D(scale_length)
        if eps is not None:
            eps = abs(D(eps))
    else:
        value = float(value) * float(scale_length)
        if eps is not None:
            eps = abs(float(eps))

    if isinstance(unit_system, str):
        units = _get_units_from_string(unit_system)
    else:
        units = unit_system
    start = units.symbol(start)
    end = units.symbol(end)
    if start:
        if units.is_basic(start):
            start_basic = start
        else:
            start_basic = units.next_basic(start)
    else:
        start_basic = None
    if end:
        if units.is_basic(end):
            end_basic = end
        else:
            end_basic = units.next_basic(end)
    else:
        end_basic = None

    unit_names_clipped = list(units.basic_symbols)
    if start_basic:
        i = unit_names_clipped.index(start_basic)
        unit_names_clipped = unit_names_clipped[i:]
    if end_basic and end_basic in unit_names_clipped:
        i = unit_names_clipped.index(end_basic)
        unit_names_clipped = unit_names_clipped[:i + 1]

    separated_values = []

    if value == 0:
        # 関数呼び出し前に値が0か確認して、そこで処理したほうがいいかも
        if not use_separate and start_basic:
            separated_values.append((start_basic, '0'))
        else:
            if units.base:
                unit = units.base
                f = unit.scalar
                # start==km: 0m, start==cm: 0cm
                if f > units.scalar(unit_names_clipped[0]):
                    name = unit_names_clipped[0]
                elif f < units.scalar(unit_names_clipped[-1]):
                    name = unit_names_clipped[-1]
                else:
                    name = unit.symbol
                separated_values.append((name, '0'))
    else:
        val = abs(value)
        for i, name in enumerate(unit_names_clipped):
            scalar = units.scalar(name)
            if not use_decimal:
                scalar = float(scalar)
            div, mod = _divmod_eps(val, scalar, eps)

            end_loop = i == len(unit_names_clipped) - 1
            if use_separate:
                if name == end_basic:
                    end_loop = True
            else:
                if div >= 1 or start_basic and name == start_basic:
                    end_loop = True

            # break
            if end_loop:
                end_value = div + mod / scalar
                rounding_exp = _rounding_exp_from_string(units, scalar,
                                                         rounding_exp)
                if use_decimal:
                    _, digits, exp = end_value.as_tuple()
                    if exp == 0 and ''.join(map(str, digits)) == '0' and \
                            separated_values:
                        s = None
                    else:
                        if rounding_exp is not None:
                            end_value = _round_decimal(
                                end_value, rounding_exp, rounding)
                            if normalize:
                                end_value = end_value.normalize()
                        s = _removed_exponent_string(end_value)
                else:
                    if rounding_exp is not None:
                        mantissa = _rounded_float_mantissa(
                            end_value, rounding_exp, rounding)
                        s = _mantissa_exp_to_str(mantissa, rounding_exp,
                                                 normalize)
                    else:
                        s = str(end_value)
                if s:
                    separated_values.append((name, s))
                break

            if div != 0:
                separated_values.append((name, str(int(div))))

            if mod == 0:
                break

            val = mod

    # 0の追加
    if verbose and use_separate:
        if isinstance(verbose, bool):
            verbose = [verbose] * 3

        if verbose[1] and len(separated_values) > 1:
            i = unit_names_clipped.index(separated_values[0][0])
            j = 0
            while j <= len(separated_values) - 1:
                name = unit_names_clipped[i]
                if name != separated_values[j][0]:
                    separated_values.insert(j, (name, '0'))
                j += 1
                i += 1

        if verbose[0]:
            i = unit_names_clipped.index(separated_values[0][0])
            separated_values[:0] = [(name, '0')
                                    for name in unit_names_clipped[:i]]

        if verbose[2]:
            i = unit_names_clipped.index(separated_values[-1][0])
            separated_values[len(separated_values):] = [
                (name, '0') for name in unit_names_clipped[i + 1:]]

    # 文字列結合
    result_string = ''
    for name, val in separated_values:
        if result_string:
            result_string += ' '
        result_string += str(val) + name
    if value < 0:
        result_string = '-' + result_string
    return result_string


###############################################################################
# nose test...
###############################################################################
def test():
    import nose
    import nose.tools
    from nose.tools import eq_, ok_

    def test_unit_to_num():
        eq_(unit_to_num('10m', scale_length=2), 5)
        # eq_(unit_to_num('2m 10bu', units={'bu': 2}, scale_length=2), 11)

    def test_round_float():
        eq_(_rounded_float_mantissa(1.5, 0, decimal.ROUND_HALF_EVEN), 2)
        eq_(_rounded_float_mantissa(2.5, 0, decimal.ROUND_HALF_EVEN), 2)
        eq_(_rounded_float_mantissa(2.5, 0, decimal.ROUND_UP), 3)
        eq_(_rounded_float_mantissa(2.5, 0, decimal.ROUND_DOWN), 2)
        eq_(_rounded_float_mantissa(2.5, 0, decimal.ROUND_CEILING), 3)
        eq_(_rounded_float_mantissa(2.5, 0, decimal.ROUND_FLOOR), 2)

        eq_(_rounded_float_mantissa(-1.5, 0, decimal.ROUND_HALF_EVEN), -2)
        eq_(_rounded_float_mantissa(-2.5, 0, decimal.ROUND_HALF_EVEN), -2)
        eq_(_rounded_float_mantissa(-2.5, 0, decimal.ROUND_UP), -3)
        eq_(_rounded_float_mantissa(-2.5, 0, decimal.ROUND_DOWN), -2)
        eq_(_rounded_float_mantissa(-2.5, 0, decimal.ROUND_CEILING), -2)
        eq_(_rounded_float_mantissa(-2.5, 0, decimal.ROUND_FLOOR), -3)

        eq_(_rounded_float_mantissa(-0.16, -1, decimal.ROUND_HALF_EVEN), -2)  # -0.15は誤差が出る

    def test_mantissa_exp_to_str():
        eq_(_mantissa_exp_to_str(1234, 2), '123400')
        eq_(_mantissa_exp_to_str(1234, -1), '123.4')
        eq_(_mantissa_exp_to_str(-1234, -5), '-0.01234')
        eq_(_mantissa_exp_to_str(0, -2), '0.00')

    def test_rounding_exp_from_string():
        eq_(_rounding_exp_from_string(metric_units, 1.0, 'mm'), -3)
        eq_(_rounding_exp_from_string(metric_units, 0.1, 'mm'), -2)
        eq_(_rounding_exp_from_string(metric_units, 1.0, 'km'), 3)

    def setup_func():
        "set up test fixtures"

    def teardown_func():
        "tear down test fixtures"

    @nose.with_setup(setup_func, teardown_func)
    def test_num_to_unit():
        # raise ValueError()
        # assert False
        eq_(num_to_unit('12345.67890123', 'metric', use_decimal=True),
            '12km 345m 67cm 8.90123mm')
        eq_(num_to_unit('12345.67890123', 'metric', start='m', end='cm',
                        use_decimal=True),
            '12345m 67.890123cm')

        val = num_to_unit('1.00456', 'metric', start='km', end='pm',
                          verbose=True, use_decimal=True)
        eq_(val, '0km 1m 0cm 4mm 560µm 0nm 0pm')

        val = num_to_unit('1.00456', 'metric', start='km', end='pm',
                          verbose=[False, True, False], use_decimal=True)
        eq_(val, '1m 0cm 4mm 560µm')

        val = num_to_unit('1.00456', 'metric', start='km', end='pm',
                          verbose=[True, False, True], use_decimal=True)
        eq_(val, '0km 1m 4mm 560µm 0nm 0pm')

        eq_(num_to_unit('12345.67890123', 'metric', use_separate=False,
                        use_decimal=True),
            '12.34567890123km')

        eq_(num_to_unit('10', 'metric', scale_length=2, use_decimal=True),
            '20m')

        eq_(num_to_unit(Decimal('000000'), 'metric', use_decimal=True,
                        use_separate=False),
            '0m')

    def test_divmod_eps():
        eq_(_divmod_eps(10.1, 1, 0.05), (divmod(10.1, 1)))
        eq_(_divmod_eps(10.1, 1, 1), (10.0, 0.0))
        eq_(_divmod_eps(-10.9, 1, 1), (-11.0, 0.0))
        eq_(_divmod_eps(-10.1, -1, 1), (10.0, 0.0))

        d, m = _divmod_eps(D('-10.9'), D(-1), D(1))
        eq_(d.as_tuple(), Decimal('11').as_tuple())
        eq_(m.as_tuple(), Decimal('-0.0').as_tuple())

    test_round_float()
    test_mantissa_exp_to_str()
    test_rounding_exp_from_string()
    test_unit_to_num()
    test_num_to_unit()
    test_divmod_eps()


if __name__ == '__main__':
    test()
