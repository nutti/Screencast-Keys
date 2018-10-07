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


from .utils import *


"""
NOTE:
Type Hinting in PyCharm


Foo # Class Foo visible in the current scope
x.y.Bar # Class Bar from x.y module
Foo | Bar # Foo or Bar
(Foo, Bar) # Tuple of Foo and Bar
list[Foo] # List of Foo elements
dict[Foo, Bar] # Dict from Foo to Bar
T # Generic type (T-Z are reserved for generics)
T <= Foo # Generic type with upper bound Foo
Foo[T] # Foo parameterized with T
(Foo, Bar) -> Baz # Function of Foo and Bar that returns Baz
list[dict[str, datetime]] # List of dicts from str to datetime (nested arguments)


Type hinting with docstrings/comments
With Sphinx


# Function Parameter, Type, Return
:param x: this is comment
:type x: str
:param str x: param & type inline
:return: this is comment
:rtype: int


# Local variable

# docstringを変数直後の行に挿入する。間に空行を入れる事は可、コメント行は不可。
# 同時に複数の変数のtypeを定義することは出来無い
x = func()
''':type x: str'''  # 単一/三連のシングル/ダブルクォート全て可
# a, b = 1, 2 といった形式は不可
# 変数名は省略可。というか上記の条件から変数名はほぼ不要。
x = func()
':type: str'

# コメントアウトを使う場合は変数直前の行。空行を入れる事は可、コメント行は不可。
#: :type a: int
a = func()

# isinstance()を使うとその型と見做してくれる



"""
