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


import re
from functools import reduce
from collections import defaultdict

try:
    import bpy
    from bpy.props import *
    import mathutils as Math
    from mathutils import Matrix, Euler, Vector, Quaternion
    import blf
    import bgl
    from bgl import glRectf
except:
    pass

### Print ###
# P = type('',(),{'__or__':(lambda s,o:print(o))})()


event_types = [
    'NONE', 'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE', 'BUTTON4MOUSE',
    'BUTTON5MOUSE', 'ACTIONMOUSE', 'SELECTMOUSE', 'MOUSEMOVE',
    'INBETWEEN_MOUSEMOVE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE',
    'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE',
    'BUTTON6MOUSE', 'BUTTON7MOUSE', 'BUTTON8MOUSE', 'BUTTON9MOUSE',
    'BUTTON10MOUSE', 'BUTTON11MOUSE', 'BUTTON12MOUSE', 'BUTTON13MOUSE',
    'BUTTON14MOUSE', 'BUTTON15MOUSE', 'BUTTON16MOUSE', 'BUTTON17MOUSE',

    'EVT_TWEAK_L', 'EVT_TWEAK_M', 'EVT_TWEAK_R', 'EVT_TWEAK_A', 'EVT_TWEAK_S',

    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O',
    'P',
    'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',

    'ZERO', 'ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT',
    'NINE',
    'LEFT_CTRL', 'LEFT_ALT', 'LEFT_SHIFT', 'RIGHT_ALT', 'RIGHT_CTRL',
    'RIGHT_SHIFT', 'OSKEY',

    'GRLESS', 'ESC', 'TAB', 'RET', 'SPACE', 'LINE_FEED', 'BACK_SPACE', 'DEL',
    'SEMI_COLON', 'PERIOD', 'COMMA', 'QUOTE', 'ACCENT_GRAVE', 'MINUS', 'SLASH',
    'BACK_SLASH', 'EQUAL', 'LEFT_BRACKET', 'RIGHT_BRACKET',

    'LEFT_ARROW', 'DOWN_ARROW', 'RIGHT_ARROW', 'UP_ARROW',

    'NUMPAD_2', 'NUMPAD_4', 'NUMPAD_6', 'NUMPAD_8', 'NUMPAD_1', 'NUMPAD_3',
    'NUMPAD_5', 'NUMPAD_7', 'NUMPAD_9', 'NUMPAD_PERIOD', 'NUMPAD_SLASH',
    'NUMPAD_ASTERIX', 'NUMPAD_0', 'NUMPAD_MINUS', 'NUMPAD_ENTER',
    'NUMPAD_PLUS',

    'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
    'F13', 'F14', 'F15', 'F16', 'F17', 'F18', 'F19',

    'PAUSE', 'INSERT', 'HOME', 'PAGE_UP', 'PAGE_DOWN', 'END', 'MEDIA_PLAY',
    'MEDIA_STOP', 'MEDIA_FIRST', 'MEDIA_LAST',

    'WINDOW_DEACTIVATE',

    'TIMER', 'TIMER0', 'TIMER1', 'TIMER2',

    'NDOF_BUTTON_MENU', 'NDOF_BUTTON_FIT', 'NDOF_BUTTON_TOP',
    'NDOF_BUTTON_BOTTOM',
    'NDOF_BUTTON_LEFT', 'NDOF_BUTTON_RIGHT', 'NDOF_BUTTON_FRONT',
    'NDOF_BUTTON_BACK', 'NDOF_BUTTON_ISO1', 'NDOF_BUTTON_ISO2',
    'NDOF_BUTTON_ROLL_CW', 'NDOF_BUTTON_ROLL_CCW', 'NDOF_BUTTON_SPIN_CW',
    'NDOF_BUTTON_SPIN_CCW', 'NDOF_BUTTON_TILT_CW', 'NDOF_BUTTON_TILT_CCW',
    'NDOF_BUTTON_ROTATE', 'NDOF_BUTTON_PANZOOM', 'NDOF_BUTTON_DOMINANT',
    'NDOF_BUTTON_PLUS', 'NDOF_BUTTON_MINUS', 'NDOF_BUTTON_1', 'NDOF_BUTTON_2',
    'NDOF_BUTTON_3', 'NDOF_BUTTON_4', 'NDOF_BUTTON_5', 'NDOF_BUTTON_6',
    'NDOF_BUTTON_7', 'NDOF_BUTTON_8', 'NDOF_BUTTON_9', 'NDOF_BUTTON_10'
]  # 変更不可だけど、check_argumentsの為にリストにしておく


#==============================================================================
# 何か
#==============================================================================
# def get_inrange(seq, index):
#     """
#     ls[-1]や、例外を出すインデックスを修正する。
#     """
#     try:
#         return seq[index]
#     except IndexError as index_err:
#         length = len(seq)
#         if length == 0:
#             raise index_err
#         while index < 0 or index >= length:
#             if index < 0:
#                 index += length
#             else:
#                 index -= length
#         return seq[index]


def list_get(seq, index, default=None, inrange=True):
    if inrange:
        length = len(seq)
        if length > 0:
            while index < 0 or index >= length:
                if index < 0:
                    index += length
                else:
                    index -= length
            return seq[index]
        return default
    else:
        if -len(seq) <= index < len(seq):
            return seq[index]
        else:
            return default


def inrange(index, ls_or_int:'sequence or int'):
    """
    引数の順番など、見直しの必要あり？
    ls[-1]や、例外を出すインデックスを修正する。
    """
    if isinstance(ls_or_int, int):
        length = ls_or_int
    else:
        length = len(ls_or_int)
    if length == 0:
        return index
    while index < 0 or index >= length:
        if index < 0:
            index += length
        else:
            index -= length
    return index


# Save Properties #############################################################
class SaveProperties:
    """全オペレータのプロパティを一括管理。
    """

    def __init__(self):
        self.data = {}

    def update(self, operator, attrs=None):
        name = operator.__class__.bl_idname
        vals = self.data.setdefault(name, {})
        if attrs is not None:
            for attr in attrs:
                val = getattr(operator, attr, None)
                if hasattr(val, '__iter__'):
                    # BoolVectorProperty等。
                    # そのまま渡すと次オペレータの読み込み時に落ちる
                    val = val[:]
                vals[attr] = val
        else:
            for attr in vals.keys():
                val = getattr(operator, attr, None)
                if hasattr(val, '__iter__'):
                    val = val[:]
                vals[attr] = val

    def read(self, operator, attrs=None):
        name = operator.__class__.bl_idname
        if name in self.data:
            if attrs is not None:
                for attr in attrs:
                    if attr in self.data[name]:
                        setattr(operator, attr, self.data[name][attr])
                    else:
                        if hasattr(operator, attr):
                            self.data[name][attr] = getattr(operator, attr)
                        else:
                            self.data[name][attr] = None
                            setattr(operator, attr, None)
            else:
                for attr, value in self.data[name].items():
                    setattr(operator, attr, value)
        else:
            self.update(operator, attrs)

    def get(self, operator, attr):
        name = operator.__class__.bl_idname
        if name in self.data:
            if attr in self.data[name]:
                return self.data[name][attr]
        return None

    def set(self, operator, attr, value):
        name = operator.__class__.bl_idname
        if hasattr(value, '__iter__'):
            value = value[:]
        if name in self.data:
            self.data[name][attr] = value
        else:
            self.data[name] = {attr: value}


op_prop_values = SaveProperties()


class WatchProperties:
    """オペレータの実行中にプロパティの変更を監視"""

    def __init__(self, operator, attrs):
        self.operator = operator
        self.attrs = attrs
        for attr in attrs:
            setattr(self, attr, getattr(operator, attr))

    def update(self):
        operator = self.operator
        changed = set()
        for attr in self.attrs:
            if getattr(self, attr) != getattr(operator, attr):
                changed.add(attr)
            setattr(self, attr, getattr(operator, attr))
        return changed


# Rename ######################################################################
def get_basename(name, only_remove_numbers=False):
    if only_remove_numbers:
        m = re.match('^(.*)\.(\d+)$', name)
        if m:
            basename, d = m.groups()
        else:
            basename = name
    else:
        basename = name.split('.')[0]
    return basename


def no_overlap_name_eval(string, global_dict, local_dict, names,
                         replace=None, search_smaller=False,
                         number_pattern='(^.*\.)(?P<i>\d+)(\.D+$|$)'):
    """
    expressin: evalで使う文字列。
    global_dict, local_dict: evalで使う辞書。
                             local_dictはここで変更する為、あらかじめ複製しておくこと
    replace: (pattern, target, count)
    """
    LIM_LOOP_CNT = 10  # この回数同じ名前になるならループを、抜ける。

    try:
        name = eval(string, global_dict, local_dict)
    except Exception as err:
        return err
    if replace:
        pattern, target, count = replace
        try:
            name = re.sub(pattern, name, target, count)
        except Exception as err:
            return err
        if name not in names:
            return name
    elif name not in names:
        return name
    match = None
    if search_smaller and number_pattern:
        match = re.match(number_pattern, name)
    if match:
        # nameから数値を探し、0から連番を付ける。無ければ通常処理。
        groups = match.groups()
        number = match.group('i')
        pre = ''.join(groups[:groups.index(number)])
        post = ''.join(groups[groups.index(number) + 1:])
        column = len(number)
        cnt = 0
        while True:
            newnumber = '{0:0{1}d}'.format(cnt, column)
            newname = pre + newnumber + post
            if newname not in names:
                break
            elif newnumber == '9' * column:
                column += 1
                cnt = 0
            cnt += 1
        return newname
    else:
        # Hoge -> Piyo -> Huga ... (use eval())
        local_i_bak = local_dict['i']
        newnames = {name}
        cnt = 0
        while True:
            local_dict['i'] += 1
            try:
                name = eval(string, global_dict, local_dict)
            except Exception as err:
                return err
            if replace:
                #pattern, target, count = replace
                name = re.sub(pattern, name, target, count)
            if name not in names:
                return name
            elif name in newnames:
                cnt += 1
            if cnt >= LIM_LOOP_CNT:  # 自己循環と判断
                break
            newnames.add(name)

        # Hoge.000 -> Hoge.001 -> Hoge.002 ... (add tail number)
        local_dict['i'] = local_i_bak
        try:
            name = eval(string, global_dict, local_dict)
        except Exception as err:
            return err
        if replace:
            name = re.sub(pattern, name, target, count)
        period = '.' if not name.endswith('.') else ''
        column = 3
        cnt = 0
        while True:
            newnumber = '{0:0{1}d}'.format(cnt, column)
            newname = name + period + newnumber
            if newname not in names:
                return newname
            elif newnumber == '9' * column:
                column += 1
                cnt = 0
            else:
                cnt += 1


def no_overlap_name(name, names, search_smaller=False,
                    number_pattern='(^.*\.)(?P<i>\d+)(\.\D+$|$)'):
    """
    search_smaller: 名前を変更する場合、***.000から順に空きを探す。
    number_pattern: '(^.*\.)(?P<i>\d+)(\.\D+$|$)'
                    重複があった場合に、数値とみなして増減する。
                    全部グループ化し、数値には必ずiを名付けておく事。
    """
    if name not in names:
        return name

    try:
        match = re.match(number_pattern, name) if number_pattern else None
    except Exception as err:
        return err
    if match:
        groups = match.groups()
        number = match.group('i')
        pre = ''.join(groups[:groups.index(number)])
        post = ''.join(groups[groups.index(number) + 1:])
    else:
        number = '000'
        pre = name if name.endswith('.') else name + '.'
        post = ''

    column = len(number)
    cnt = 0 if search_smaller or not match else int(number) + 1
    while True:
        newnumber = '{0:0{1}d}'.format(cnt, column)
        newname = pre + newnumber + post
        if newname not in names:
            break
        elif newnumber == '9' * column:
            column += 1
            cnt = 0
        else:
            cnt += 1
    return newname


# Snap ########################################################################
def get_matrix_element_square(mat, center, r):
    """
    # centerの周り、r距離分の要素を左上から順に返す。
    mat = [[ 0, 1, 2, 3],
           [ 4, 5, 6, 7],
           [ 8, 9,10,11],
           [12,13,14,15]]
    print([i for i in get_matrix_fuga(mat, (1,2), 1)]) #center==6
    > [1, 2, 3, 7, 11, 10, 9, 5]
    print([i for i in get_matrix_fuga(mat, (0,2), 2)]) #center==2
    > [11, 10, 9, 8, 4, 0]
    """
    row = center[0] - r
    col = center[1] - r
    cnt = 0
    while True:
        if cnt != 0 and cnt >= 8 * r:
            raise StopIteration
        if 0 <= row < len(mat) and 0 <= col < len(mat[0]):
            yield mat[row][col]
        if cnt < 2 * r:
            col += 1
        elif cnt < 4 * r:
            row += 1
        elif cnt < 6 * r:
            col -= 1
        elif cnt < 8 * r:
            row -= 1
        cnt += 1


# Utils #######################################################################
def the_other(ls, item):
    return ls[ls.index(item) - 1]


def prev_item(ls, item):
    return ls[ls.index(item) - 1]


def next_item(ls, item):
    return ls[ls.index(item) + 1 - len(ls)]


def oppo_item(ls, item, one_side):  # opposite
    """one_sideがitemの後ろならitemの一つ前の要素を返す"""
    i = ls.index(item)
    if ls[i - 1] == one_side:  # prev is one_side. return next
        return ls[i + 1 - len(ls)]
    elif ls[i + 1 - len(ls)] == one_side:  # next is one_side. return prev
        return ls[i - 1]
    else:
        raise IndexError


def copy_attributes(obj_tag, obj_src, attrs=None):
    if attrs is None:
        attrs = dir(obj_src)
    for attr in attrs:
        try:
            setattr(obj_tag, attr, getattr(obj_src, attr))
        except:
            pass


def exclude_continuance(ls):
    """連続した同じ値を複数返さない"""
    if len(ls) == 0:
        raise StopIteration
    tmp = None if ls[0] != None else False  # 仮
    for i in ls:
        if i == tmp:
            continue
        yield i
        tmp = i


def exclude_duplicate(ls):
    """重複した値を複数返さない"""
    if len(ls) == 0:
        raise StopIteration
    s = set()
    #tmp = None if ls[0] != None else False  # 仮
    for i in ls:
        if i in s:
            continue
        yield i
        s.add(i)


def flatten_matrix(mat):
    """列優先"""
    return reduce(lambda x, y: x[:] + y[:], mat.col)


# def array_to_3x3matrix(arr):
#     # ID Array等に利用
#     mat = Matrix([[arr[i] for i in range(0, 3)],
#                   [arr[i] for i in range(3, 6)],
#                   [arr[i] for i in range(6, 9)]])
#     return mat
#
#
# def arrays_to_3x3matrix(arrs):
#     # (ID Array, ID Array, ID Array)
#     mat = Matrix([[arrs[0][i] for i in range(0, 3)],
#                   [arrs[1][i] for i in range(0, 3)],
#                   [arrs[2][i] for i in range(0, 3)]])
#     return mat


# localutils.utils.groupwith()に置き換え
# def dict_to_linked_items_list(dic, secure=False):
#     """
#     {a: [b, c], b: [a], c: [a], d: [], e: [e]} -> [[a, b, c], [d], [e]]
#     secure==Trueだとdicのチェックを行う。
#     va.mesh.linked_vertices_list等で使用する。
#     順番は無視される
#     """
#
#     if secure:  # チェック
#         d = {k: list(v) for k, v in dic.items()}
#         for key_item, items in d.items():
#             for item in items:
#                 if key_item not in d[item]:
#                     d[item].append(key_item)
#     else:
#         d = dict(dic)  # shallow copy パフォーマンスの心配ほぼ無し
#
#     flags = {item: 0 for item in d.keys()}
#     groups = []
#     while d:
#         for key_item, items in d.items(): # 適当な頂点を開始点とする為のループなので、すぐbreak
#             flags[key_item] = 2
#             for item in items:
#                 flags[item] = 1
#             break
#         finish = False
#         while finish is False:
#             finish = True
#             for key_item, items in d.items():
#                 if flags[key_item] == 1:
#                     flags[key_item] = 2
#                     for item in items:
#                         if flags[item] == 0:
#                             flags[item] = 1
#                     finish = False
#         group = [item for item in d.keys() if flags[item] == 2]
#         groups.append(group)
#         for item in group:
#             del (d[item])
#     return groups


def pair_items_to_list(pair_items, order:list=None, secure=False):
    """
    pair_items: [[A, B], [B, C], [A, C]]
                A, B, C, D は辞書のキーとして有効なオブジェクトであること。
                secure=Trueとすると、多少低速だがそれ以外でも動作するようになる。
    order: リストを渡すと、並び替えた後のインデックスが得られる。
    e.g.
        pair_items = [['C', 'A'], ['C', 'B'], ['B', 'A']]
        order = []
        result = vau.pair_items_to_list(pair_items, order)
        print(result, order)
        >> ['B', 'A', 'C', 'B'] [2, 0, 1]
        
        pair_items = [[[4], 'D'], [[4], 'B'], ['B', 'A']]
        order = []
        result = vau.pair_items_to_list(pair_items, order, secure=True)
        print(result, order)
        >> ['D', [4], 'B', 'A'] [0, 1, 2]
    
    cyclicなら先頭と末尾は同じ値になる。
    一つのリストに連結できない場合はNoneを返す。
    """

    class Tmp:
        def __init__(self, value):
            self.value = value

    if len(pair_items) == 0:
        return []

    if secure:
        d = {}
        for i, pair in enumerate(pair_items):
            for j, item in enumerate(pair):
                for tmp in d.values():
                    if tmp.value == item:
                        d[(i, j)] = tmp
                        break
                else:
                    tmp = Tmp(item)
                    d[(i, j)] = tmp
        pair_items = [(d[(i, 0)], d[i, 1]) for i in range(len(pair_items))]

    item_count = defaultdict(int)
    for pair in pair_items:
        for item in pair:
            item_count[item] += 1

    end_items = []
    for item, count in item_count.items():
        if count == 1:
            end_items.append(item)
        elif count > 2:
            return None
    if len(end_items) > 2:
        return None

    if end_items:
        item = end_items[0]
    result = [item]
    pair_index_dict = {tuple(pair): i for i, pair in enumerate(pair_items)}
    while pair_index_dict:
        for pair in pair_index_dict:
            if item in pair:
                break
            #item = pair[0] if pair[0] != item else pair[1]
        item = the_other(pair, item)
        result.append(item)
        if order is not None:
            order.append(pair_index_dict[pair])
        del pair_index_dict[pair]

    if secure:
        result = [tmp.value for tmp in result]

    return result


# def str_to_args(s, *dicts):
#     """
#     文字列から変数を取得。
#     args, kw = str_to_args('hoge, piyo, huga=0.1', globals(), locals())
#     dicts: globals()、locals()を指定
#     """
#
#     def auto_args(*args, **kw):
#         return args, kw
#
#     if len(dicts) == 2:  # (globals, locals)
#         d = dict(locals())
#         d.update(dicts[1])
#         dicts = (dicts[0], d)
#     args, kw = eval('auto_args(' + s + ')', *dicts)
#     return args, kw


# print #######################################################################
def print_mat(label, matrix, column=4):
    if isinstance(matrix[0], (float, int)):
        # buffer用
        if len(matrix) == 16:
            mat = [matrix[:4], matrix[4:8], matrix[8:12], matrix[12:16]]
            matrix = Matrix(mat)
        elif len(matrix) == 9:
            matrix = Matrix([matrix[:3], matrix[3:6], matrix[6:9]])
        elif len(matrix) == 4:
            matrix = Matrix([matrix[:2], matrix[2:4]])

    print(label)
    t2 = 'row{0} [{1:>{5}.{6}f}, {2:>{5}.{6}f}]'
    t3 = 'row{0} [{1:>{5}.{6}f}, {2:>{5}.{6}f}, {3:>{5}.{6}f}]'
    t4 = 'row{0} [{1:>{5}.{6}f}, {2:>{5}.{6}f}, {3:>{5}.{6}f}, {4:>{5}.{6}f}]'
    m = matrix.transposed()
    for cnt, row in enumerate(m):
        if len(row) == 2:
            print(t2.format(cnt, row[0], row[1], 0, 0, column + 3, column))
        elif len(row) == 3:
            print(t3.format(cnt, row[0], row[1], row[2], 0,
                            column + 3, column))
        else:
            print(t4.format(cnt, row[0], row[1], row[2], row[3],
                            column + 3, column))


def print_vec(label='', vec=[0.0, 0.0, 0.0], column=4, end='\n'):
    if len(vec) == 2:
        txt = '[{1:>{5}.{6}f}, {2:>{5}.{6}f}]'
        if label:
            txt = '{0} ' + txt
        print(txt.format(label, vec[0], vec[1], 0, 0, column + 3, column),
              end=end)
    elif len(vec) == 3:
        txt = '[{1:>{5}.{6}f}, {2:>{5}.{6}f}, {3:>{5}.{6}f}]'
        if label:
            txt = '{0} ' + txt
        print(txt.format(label, vec[0], vec[1], vec[2], 0, column + 3, column),
              end=end)
    elif len(vec) == 4:
        txt = '[{1:>{5}.{6}f}, {2:>{5}.{6}f}, {3:>{5}.{6}f}, {4:>{5}.{6}f}]'
        if label:
            txt = '{0} ' + txt
        print(txt.format(label, vec[0], vec[1], vec[2], vec[3], column + 3,
                         column), end=end)


def print_event(event):
    if event.type == 'NONE':
        return
    modlist = []
    if event.ctrl:
        modlist.append('ctrl')
    if event.shift:
        modlist.append('shift')
    if event.alt:
        modlist.append('alt')
    if event.oskey:
        modlist.append('oskey')
    mods = ' + '.join(modlist)

    if event.type in ('MOUSEMOVE'):
        if modlist:
            print(mods)
    else:
        if event.value == 'PRESS':
            if event.type not in ('LEFT_SHIFT', 'RIGHT_SHIFT',
                                  'LEFT_CTRL', 'RIGHT_CTRL',
                                  'LEFT_ALT', 'RIGHT_ALT', 'COMMAND'):
                if mods:
                    text = mods + ' + ' + event.type
                else:
                    text = event.type
                print(text)


def register():
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


if __name__ == '__main__':
    register()
