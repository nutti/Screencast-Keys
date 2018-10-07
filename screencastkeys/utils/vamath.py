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

"""
Numpy is called in get_bounding_box(vecs)
install numpy (linux):
% git clone git://github.com/numpy/numpy.git numpy
% cd numpy
% python3.1 setup.py build
% python3.1 setup.py install --prefix=$HOME/.local  # or --prefix=/usr
"""

import math
from collections import OrderedDict
import itertools
from itertools import combinations  # , permutations
from functools import reduce

try:
    import numpy as np
except:
    pass

import bpy
from bpy.props import *
import mathutils
from mathutils import Euler, Matrix, Quaternion, Vector
from mathutils import geometry as geom

from .. import localutils

from . import vautils as vau


class NONE:
    """引数の初期値にNoneが使えない場合に"""
    pass

MIN_NUMBER = 1E-8

XAXIS = Vector([1, 0, 0])
YAXIS = Vector([0, 1, 0])
ZAXIS = Vector([0, 0, 1])
# FLAT_IDENTITY_MAXRIX_3 = (1, 0, 0,
#                           0, 1, 0,
#                           0, 0, 1)
# FLAT_IDENTITY_MAXRIX_4 = (1, 0, 0, 0,
#                           0, 1, 0, 0,
#                           0, 0, 1, 0,
#                           0, 0, 0, 1)

# nan = float('nan')
# inf = float('inf')


# 平面の方程式 ################################################################
class PlaneVector(Vector):
    """
    三次元平面を表す四次元ベクトル。
    
    attributes:
        location (Vector):
            平面の位置ベクトル。
        normal (Vector):
            平面の法線ベクトル。
    
    tip:
        参考: http://marupeke296.com/COL_Basic_No3_WhatIsPlaneEquation.html
        法線ベクトル= [a, b, c]  # need normalize
        位置ベクトル = [xo, yo, zo]
        
        平面の方程式。
        a(x -  xo) + b(y - yo) + c(z - zo) = 0
        これは[a, b, c]と[(x - xo),(y - yo),(z - zo)]の内積と見ることも出来る。
        
        上式を展開
        ax + by + cz - (a * xo + b * yo + c * zo) = 0
        
        平面を表す四次元ベクトル pvec = [a, b, c, - (a * xo + b * yo + c * zo)]
        平面とベクトルの距離 = dot_v4v4(vec, pvec)
    
    caution:
        normalの正規化は、__new__(), update(), _normal_set()でしか行われない。
        スライスを使った変更(normal[:] = [1.0, 0.0, 0.0])をやると正規化が行われない。
        
        copy()以外の、normalized()やto_3d()等は只のVector型になってしまうので注意
    """

    def __new__(cls, location=Vector(), normal=ZAXIS, rotation=Quaternion()):
        loc = Vector(location)
        nor = Vector(normal).normalized()
        vector = nor.to_4d()
        vector[3] = -nor.dot(loc)
        return Vector.__new__(cls, vector)

    def __init__(self, location=Vector(), normal=ZAXIS, rotation=None):
        """
        location: <Vector>
        normal: <Vector>
        rotation: <Quaternion> or <None>
        """
        self._location = Vector(location)
        self._normal = Vector(normal).normalized()
        if rotation:
            self._rotation = Quaternion(rotation)
        else:
            self._rotation = ZAXIS.rotation_difference(self._normal)

    @property
    def normal_isnan(self):
        return any((math.isnan(f) for f in self.normal))

    @property
    def location_isnan(self):
        return any((math.isnan(f) for f in self.location))

    def copy(self, other=None):
        return self.__class__(self.location, self.normal, self.rotation)

    def copy_to(self, other):
        """other: <PlaneVector>: 対象へ値を複製する"""
        other[:] = self[:]
        other._location[:] = self._location
        other._normal[:] = self._normal
        other._rotation[:] = self._rotation

    def update(self):
        """self.location,self.normal,self.rotationを変更した際に呼び出される。
        x, y, z = self._location
        a, b, c = self._normal
        self[:] = [a, b, c, -(a * x + b * y + c * z)]
        """
        self._normal.normalize()
        self[:3] = self._normal
        self[3] = -self._normal.dot(self._location)

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, value):
        """スライスで代入"""
        # self._location = Vector(value)
        self._location[:] = value
        self.update()

    @property
    def normal(self):
        return self._normal

    @normal.setter
    def normal(self, value):
        """スライスで代入"""
        # self._normal = Vector(value).normalized()
        self._normal[:] = value
        self.update()
        self._rotation = ZAXIS.rotation_difference(self._normal)

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        self._rotation[:] = value
        self._normal[:] = self._rotation * ZAXIS
        self.update()

    def distance(self, other:Vector):
        """平面とVectorの距離を返す"""
        return self.dot(other.to_4d())

    def distance_normal(self, other:Vector):
        """normalの直線とVectorの距離を返す"""
        self.update()
        return self.normal.cross(other - self.location)

    def project(self, other:Vector):
        """上書き。Vectorを平面に投影する"""
        self.update()
        v = other - self.location
        return (v - v.project(self.normal)) + self.location

    def intersect(self, v1, v2):
        """平面とv1-v2からなる直線の交点を求める"""
        return geom.intersect_line_plane(v1, v2, self.location, self.normal)

    def same_radius_vectors(self, radius, num):
        """平面上にあってlocationを中心にした同一距離のベクトルを返す。"""
        if num == 0:
            return []
        quat = ZAXIS.rotation_difference(self.normal)
        vectors = []
        a = math.pi / 2  # 90度の位置から始める
        for i in range(num):
            vec = Vector((radius * math.cos(a), radius * math.sin(a), 0))
            vectors.append(quat * vec + self.location)
            a -= math.pi * 2 / num  # 反時計回り
        return vectors

    def to_matrix(self, use_rotation=False):
        """plane.normalがZ軸になるような行列。
        PlaneVector.to_matrix().inverted() * Vectorでworld->plane座標への変換が
        出来る。
        use_rotation: <bool>: self.rotationを使う。
        """
        locmat = Matrix.Translation(self.location)
        if use_rotation:
            quat = self.rotation
        else:
            quat = ZAXIS.rotation_difference(self.normal)
        rotmat = quat.to_matrix().to_4x4()
        return locmat * rotmat


# 階乗とか ####################################################################
# def nI(n):
#     # 階乗
#     m = n
#     x = n - 1
#     while x >= 1:
#         m *= x
#         x -= 1
#     return m

nI = math.factorial


def nPm(n, m):
    # n個の中からm個を取り出す順列の総数（重複無し）
    return nI(n) / nI(n - m)


def nCm(n, m):
    # n個の中からm個を取り出す組み合わせの総数（重複無し）:
    return nI(n) / (nI(m) * nI(n - m))


def nHr(n, r):
    # 重複組合せ（ちょうふくくみあわせ、repeated combination）
    # n 種のものから、重複 (repetition) を許して r 個のものを取り出す組合せ
    return nI(n + r - 1) / (nI(r) * nI(n - 1))


# 三角関数 ####################################################################
def saacos(fac):
    if fac <= -1.0:
        return math.pi
    elif fac >= 1.0:
        return 0.0
    else:
        return math.acos(fac)


def saasin(fac):
    if fac <= -1.0:
        return -math.pi / 2.0
    elif fac >= 1.0:
        return math.pi / 2.0
    else:
        return math.asin(fac)


def cross2d(v1, v2):
    return v1[0] * v2[1] - v1[1] * v2[0]


def dot2d(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]


# def axis_angle_to_quat(axis, angle):
#     # Vector(0, 0, 0)を正規化してもVector(nan, nan, nan)にならなくなった
#     # Quaternion(axis, angle)で置換可能
#     # if axis.length < MIN_NUMBER:
#     #    return Quaternion([1, 0, 0, 0])
#     nor = axis.normalized()
#     ha = angle / 2
#     si = math.sin(ha)
#     return Quaternion([math.cos(ha), nor[0] * si, nor[1] * si, nor[2] * si])


def removed_same_coordinate(vecs):
    d = OrderedDict(zip((tuple(v) for v in vecs), range(len(vecs))))
    return [vecs[i] for i in d.values()]


def normal(*vecs):
    # 3~4個のVectorのNormalを求める
    if len(vecs) == 3:
        return geom.normal(*vecs)
    elif len(vecs) == 4:
        n1 = geom.normal(vecs[0], vecs[1], vecs[3])
        n2 = geom.normal(vecs[1], vecs[2], vecs[3])
        if n1.dot(n2) < 0:
            n2.negate()
        return (n1 + n2).normalized()

normal_v3v4 = normal

"""
def vecs_angle_cw(vec1, vec2, axis=Vector([0, 0, -1]), ccw=False,
                  negative=False):
    # v1からv2への時計回りでの角度
    if len(vec1) == 2:
        vec1 = vec1.to_3d()
    if len(vec2) == 2:
        vec2 = vec2.to_3d()
    v1 = vec1 - vec1.project(axis)
    v2 = vec2 - vec2.project(axis)
    angle = v1.angle(v2)
    cvec = v1.cross(v2)
    if cvec.length:
        if ccw is False and cvec.dot(axis) < 0.0 or \
           ccw is True and cvec.dot(axis) > 0.0:
            if negative:
                angle = -angle
            else:
                angle = math.pi * 2 - angle
    return angle
"""


def vecs_angle(vec1, vec2, axis=None, positive=False, fallback=None):
    """
    vec1とvec2が2D:
        反時計回りを正とした角度を返す。
    vec1とvec2が3D:
        axisを指定:
            axisを法線とする平面にv1とv2を投影してv1とv2の成す角度を求める。
            軸を視線とし、v1からv2への向きが時計回りなら正の値を返す。
            反時計回りなら負。
        指定しない:
            vec1.angle(vec2)を返す。
    positiveがTrueなら0 ~ math.pi*2の値に直す。
    """
    vec1_size = len(vec1)
    vec2_size = len(vec2)

    if vec1_size != vec2_size or vec1.length == 0.0 or vec2.length == 0.0:
        return fallback

    if vec1_size == 3:
        if axis:
            if axis.length > 0.0:
                v1 = vec1 - vec1.project(axis)
                v2 = vec2 - vec2.project(axis)
                angle = v1.angle(v2, None)
                negative = v1.cross(v2).dot(axis) < 0.0
            else:
                return fallback
        else:
            return vec1.angle(vec2)
    elif vec1_size == 2:
        angle = vec1.angle(vec2)
        negative = cross2d(vec1, vec2) < 0
    else:
        return fallback

    if negative:
        angle = -angle
    if positive and angle < 0.0:
        angle += math.pi * 2

    return angle


def normalize_angle(angle):
    while angle < 0.0:
        angle += math.pi * 2
    while angle > math.pi * 2:
        angle -= math.pi * 2
    return angle


def to_ln_quat(quat):
    """Quaternionの対数を求める
    Quaternion.to_exponential_map()との違い：
        q1 = to_ln_quat(q)
        v = q.to_exponential_map()  # Vector
        q1 == Quaternion([0] + list(v * 2))
    """
    quat = quat.normalized()
    # Quaternion.to_exponential_map()では/2を行っていない
    axis = quat.axis * (quat.angle / 2)
    return Quaternion([0.0] + list(axis))


def from_ln_quat(ln_quat):
    """対数Quaternionから通常のQuaternionを求める。
    Quaternion(vector)でも変換できるがto_ln_quat()でも書いたような違いが有る。
    """
    a05 = ln_quat.magnitude  # θ/ 2 == math.sqrt(ln_quat.dot(ln_quat))
    value = [math.cos(a05), 0, 0, 0]
    a = math.sin(a05)
    for i in range(1, 4):
        f = ln_quat[i] / a05
        value[i] = f * a
    return Quaternion(value).normalized()


def interp_quats(quats, weights=None):
    """複数のQuaternionを合成し、正規化したものを返す
    :type quats: list[Quaternion]
    :type weights: list[float]
    """
    if 0:
        ln_quat = Quaternion([0, 0, 0, 0])
    else:  # Quaternionに新たに追加されたメソッドを使う
        to_ln_quat = Quaternion.to_exponential_map
        from_ln_quat = Quaternion
        ln_quat = Vector([0, 0, 0])
    if weights:
        f = sum(weights)
        if f != 0.0:
            weights = [w / f for w in weights]
        for quat, w in zip(quats, weights):
            ln_quat += to_ln_quat(quat) * w
    else:
        w = 1.0 / len(quats)
        for quat in quats:
            ln_quat += to_ln_quat(quat) * w
    return from_ln_quat(ln_quat)


# 凸形状 ######################################################################
def convex_vecs_2d(vectors):
    """
    xが最小となるベクトルから、反時計回りに凸形状となるようなインデックスのリストを返す。
    """

    # 修正前。最後のnew_orders追加前の仕様。
    """
    xが最小となるベクトルから、反時計回りに凸形状となるようなインデックスのリストを返す。-1は内側を表す。
    e.g.: 返り値が[2, -1, 0, 1]の場合、vectors[2], vectors[3], vectors[0]と辿ればいい。
    """

    vnum = len(vectors)

    if vnum == 0:
        return []
    elif vnum == 1:
        return [0]

    # 念のため2D化
    vecs = [v.to_2d() for v in vectors]

    orders = [-1 for i in range(vnum)]
    order = 0

    angles = [0.0 for i in range(vnum)]
    lengths = [0.0 for i in range(vnum)]

    ray = Vector([0, -1])
    ray_orig = None  # ray_origからorigtへのベクトルを正規化した物がray
    ray_orig_index = -1

    orig = min(vecs, key=lambda v: v.x)
    orig_index = vecs.index(orig)
    orders[orig_index] = order
    order += 1

    for cnt in range(vnum):
        for i, vec in enumerate(vecs):
            v = vec - orig
            if i in (orig_index, ray_orig_index):
                angles[i] = 0.0  # 誤差が出てしまうため、直接0を代入
            else:
                dot = ray.x * v.x + ray.y * v.y
                cross = ray.x * v.y - ray.y * v.x
                if v.length:
                    x = dot / v.length
                    y = cross / v.length
                    angles[i] = math.atan2(y, x)
                    # if angles[i] < 0.0:
                    #    angles[i] = math.pi * 2 - angles[i]
                else:
                    angles[i] = 0.0  # 誤差が出てしまうため、直接0を代入
            lengths[i] = v.length

        sorted_indices = list(range(vnum))
        sorted_indices.sort(key=lambda i: angles[i])

        # angleの最小値を求める (orig_indexとray_orig_indexは除外)
        for index in sorted_indices:
            if index != orig_index and index != ray_orig_index:
                min_angle = angles[index]
                break

        # 同一angleの頂点を処理。
        same_angle_indices = []  # origと重ならないray上の頂点 (origとray_orig以外)
        for index in sorted_indices:
            if angles[index] == min_angle:
                if index != orig_index and index != ray_orig_index:
                    same_angle_indices.append(index)
        same_angle_indices.sort(key=lambda i: lengths[i])
        changed = 0
        for index in same_angle_indices:
            if orders[index] == -1:
                orders[index] = order
                order += 1
                changed += 1

        if changed == 0:
            # 外周全て番号付け終了。
            break

        if lengths[same_angle_indices[-1]] == 0.0:
            # min_angleの指す先が重なった頂点だった場合、新しいmin_angleを求める。
            for index in sorted_indices:
                if index != orig_index and index != ray_orig_index:
                    if angles[index] != min_angle:
                        break
            else:
                # 要るか？
                break
            ray_orig = orig
            ray_orig_index = orig_index
            orig_index = index
            orig = vecs[orig_index]
            ray = (orig - ray_orig).normalized()
        else:
            ray_orig = orig
            ray_orig_index = orig_index
            orig_index = same_angle_indices[-1]
            orig = vecs[orig_index]
            ray = (orig - ray_orig).normalized()

    # 読みやすい形式に変換。
    inside_num = orders.count(-1)
    new_orders = [-1 for i in range(vnum - inside_num)]
    for i, index in enumerate(orders):
        if index != -1:
            new_orders[index] = i

    return new_orders


# Destance ####################################################################
def distance_point_to_plane_2d(point:'[x, y]', box:'[x, y, width, height]'):
    """Boxと頂点の距離を求める。外側なら正、内側なら負の符号を付けた値を返す。
    """
    x, y = point
    xmin, ymin, w, h = box
    xmax = xmin + w
    ymax = ymin + h
    if x <= xmin and y <= ymin:  # 左下
        length = math.sqrt((xmin - x) ** 2 + (ymin - y) ** 2)
    elif x >= xmax and y <= ymin:  # 右下
        length = math.sqrt((xmax - x) ** 2 + (ymin - y) ** 2)
    elif x >= xmax and y >= ymax:# 右上
        length = math.sqrt((xmax - x) ** 2 + (ymax - y) ** 2)
    elif x <= xmin and y >= ymax:  # 左上
        length = math.sqrt((xmin - x) ** 2 + (ymax - y) ** 2)
    elif x <= xmin:
        length = xmin - x
    elif y <= ymin:
        length = ymin - y
    elif x >= xmax:
        length = x - xmax
    elif y >= ymax:
        length = y - ymax
    else:  # 内側
        length = max(xmin - x, ymin - y, x - xmax, y - ymax)
    return length


# Intersect ###################################################################
"""
intersect_***: ベクトル若しくはベクトルのリストを返す。
inside_***: -1, 0, 1の何れかを返す。
collision_***: 真偽値を返す。
"""


def intersect_line_line(v1, v2, v3, v4, threshold=1e-6):
    """三次元での直線同士の交差判定。平行だった場合、中間地点を求める。
    二次元が与えられたら三次元に拡張する。
    parallel_threshold:
        平行であるとする閾値
    """
    v1 = v1.to_3d()
    v2 = v2.to_3d()
    v3 = v3.to_3d()
    v4 = v4.to_3d()
    vec1 = v2 - v1
    vec2 = v4 - v3

    # 両方点
    if vec1.length == 0.0 and vec2.length == 0.0:
        return None

    # v1-v2が直線、v3-v4が点
    elif vec2.length == 0.0:
        return (v3 - v1).project(vec1) + v1, v3

    # v1-v2が点、v3-v4が直線
    elif vec1.length == 0.0:
        return v1, (v1 - v3).project(vec2) + v3

    # 平行
    elif vec1.normalized().cross(v3 - v1).length < threshold and \
       vec1.normalized().cross(v4 - v1).length < threshold:
        d1 = vec1.dot(v3 - v1)
        d2 = vec1.dot(v4 - v1)
        if d1 > d2:
            d1, d2 = d2, d1
            v3, v4 = v4, v3
            vec2.negate()
        # v3,v4が両方v1側 or v3がv1側, v4がv1-v2間
        if d2 <= 0 or (d1 <= 0 and 0 <= d2 <= vec1.length):
            mid = (v1 + v4) / 2
        # v3,v4が両方v2側 or v3がv1-v2間, v4がv2側
        elif d1 >= vec1.length or \
           (0 <= d1 <= vec1.length and d2 >= vec1.length):
            mid = (v2 + v3) / 2
        # v3,v4がv1-v2間
        elif 0 <= d1 <= vec1.length and 0 <= d2 <= vec1.length:
            mid = (v2 + v3) / 2
        # v1,v2がv3-v4間
        else:
            mid = (v1 + v4) / 2
        isect1 = (mid - v1).project(vec1) + v1
        isect2 = (mid - v3).project(vec2) + v3
        return isect1, isect2

    else:
        result = geom.intersect_line_line(v1, v2, v3, v4)
        if result is not None:
            # isect1, isect2 = result
            # if not math.isnan(isect1[0]) and not math.isnan(isect2[0]):
            #     return isect1, isect2
            return result

    return None


def intersect_line_tri_2d(v1, v2, tv1, tv2, tv3):
    """三角形と線分の交点を求める。 返り値のリストは0~2の長さ。"""
    vec1 = geom.intersect_line_line_2d(v1, v2, tv1, tv2)
    vec2 = geom.intersect_line_line_2d(v1, v2, tv2, tv3)
    vec3 = geom.intersect_line_line_2d(v1, v2, tv3, tv1)
    return [v for v in (vec1, vec2, vec3) if v is not None]


def intersect_tri_tri_2d(v1, v2, v3, v4, v5, v6):
    """三角形同士の交点を求める。
    返り値が可変長で最大6つになり、順番も揃って無いので、主に交差しているか
    否かだけを求める場合に使う。
    """
    vecs1 = intersect_line_tri_2d(v4, v5, v1, v2, v3)
    vecs2 = intersect_line_tri_2d(v5, v6, v1, v2, v3)
    vecs3 = intersect_line_tri_2d(v6, v4, v1, v2, v3)
    return vecs1 + vecs2 + vecs3


def inside_tri_tri_2d(v1, v2, v3, v4, v5, v6):
    """(v1, v2, v3)が(v4,v5,v6)の内側に在る場合1を返す(重なる場合も含む)。
    逆なら-1(重なる場合も含む), 重ならない場合は0を返す。
    """
    if geom.intersect_point_tri_2d(v1, v4, v5, v6):
        if geom.intersect_point_tri_2d(v2, v4, v5, v6):
            if geom.intersect_point_tri_2d(v3, v4, v5, v6):
                return 1
    if geom.intersect_point_tri_2d(v4, v1, v2, v3):
        if geom.intersect_point_tri_2d(v5, v1, v2, v3):
            if geom.intersect_point_tri_2d(v6, v1, v2, v3):
                return -1
    return 0


def collision_tri_quat_2d(v1, v2, v3, v4, v5, v6, v7):
    """二次元の三角形と四角形の衝突を判定。内側に在る場合もTrueを返す。
    vec1から反時計回り、若しくは時計回り
    """
    v1 = v1.to_2d()
    v2 = v2.to_2d()
    v3 = v3.to_2d()
    v4 = v4.to_2d()
    v5 = v5.to_2d()
    v6 = v6.to_2d()
    v7 = v7.to_2d()

    # 三角形に分割
    q = (v4, v5, v6, v7)
    convex_indices = convex_vecs_2d(q)
    for i in range(4):
        if i not in convex_indices:
            break
    tri_pair = ((q[i - 2], q[i - 1], q[i]), (q[i], q[i - 3], q[i - 2]))


    # 分割後の三角形で衝突判定
    collision = False
    t1 = (v1, v2, v3)
    for i in range(2):
        t2 = tri_pair[i]
        if intersect_tri_tri_2d(*(t1 + t2)):
            collision = True
        else:
            if inside_tri_tri_2d(*(t1 + t2)) != 0:
                collision = True
    return collision


def collision_quad_quat_2d(v1, v2, v3, v4, v5, v6, v7, v8):
    """二次元の四角形の衝突を判定。内側に在る場合もTrueを返す。
    vec1から反時計回り、若しくは時計回り
    """
    v1 = v1.to_2d()
    v2 = v2.to_2d()
    v3 = v3.to_2d()
    v4 = v4.to_2d()
    v5 = v5.to_2d()
    v6 = v6.to_2d()
    v7 = v7.to_2d()
    v8 = v8.to_2d()

    q1 = (v1, v2, v3, v4)
    convex_indices = convex_vecs_2d(q1)
    for i in range(4):
        if i not in convex_indices:
            break
    q2 = (v5, v6, v7, v8)
    convex_indices = convex_vecs_2d(q2)
    for j in range(4):
        if j not in convex_indices:
            break
    tris = (((q1[i - 2], q1[i - 1], q1[i]), (q1[i], q1[i - 3], q1[i - 2])),
            ((q2[j - 2], q2[j - 1], q2[j]), (q2[j], q2[j - 3], q2[j - 2])))

    # 分割後の三角形で衝突判定
    collision = False
    for i in range(2):
        for j in range(2):
            t1 = tris[0][i]
            t2 = tris[1][j]
            if intersect_tri_tri_2d(*(t1 + t2)):
                collision = True
            else:
                if inside_tri_tri_2d(*(t1 + t2)) != 0:
                    collision = True
        if collision:
            break
    return collision


def intersect_point_line_2d(pt, line1, line2, clip=False):
    eps = 1e-7
    line = line2 - line1
    line_length = line.length
    a = pt - line1
    d = cross2d(line, a) / line_length
    if abs(d) < eps:
        l = dot2d(line, a) / line_length
        if not clip or 0 <= l <= line_length:
            return line1 + l * line / line_length
    return None


def intersect_line_line_2d(a1, a2, b1, b2, clip=False):
    """a1とa2を通る直線（線分）とb1とb2を通る直線（線分）の交点を計算する"""
    #             a2
    #            /   |
    #  b1-------------- b2
    #     |    /     |
    #   d1|   /      |d2
    #        a1
    eps = 1e-7
    a = a2 - a1
    b = b2 - b1
    # 点か否か
    if a.length == 0.0:
        if b.length == 0.0:
            if a1 == b1:
                return a1.copy()
            else:
                return None
        else:
            return intersect_point_line_2d(a1, b1, b2, clip)
    elif b.length == 0.0:
        return intersect_point_line_2d(b1, a1, a2, clip)
    # 平行か否か
    elif abs(cross2d(a, b)) < eps:
        return None
    # 線分だったばあい、その範囲で交差するか否か
    if clip and (cross2d(a, b1 - a1) * cross2d(a, b2 - a1) > eps or
                 cross2d(b, a1 - b1) * cross2d(b, a2 - b1) > eps):
        return None

    d1 = cross2d(b, b1 - a1)  # 省略 '/ b.length'
    d2 = cross2d(b, a)  # 省略 '/ b.length'
    return a1 + (d1 / d2) * a


def test_intersect_line_line_2d():
    def test(a1, a2, b1, b2, clip, result):
        r = intersect_line_line_2d(
            Vector(a1), Vector(a2), Vector(b1), Vector(b2), clip)
        if result is None:
            return r is None
        else:
            return r is not None and (r - Vector(result)).length < 1e-6

    # 点(線分)
    print(test((0, 0), (0, 0), (-1, 0), (1, 0), True, (0, 0)))
    print(test((-1, 0), (1, 0), (0, 0), (0, 0), True, (0, 0)))
    print(test((-1, 0), (1, 0), (0, 1), (0, 1), True, None))
    print(test((-1, 0), (1, 0), (2, 0), (2, 0), True, None))
    # 点(直線)
    print(test((-1, 0), (1, 0), (2, 0), (2, 0), False, (2, 0)))
    # 直線
    print(test((-2, 0), (2, 0), (-1, -1), (1, 1), False, (0, 0)))
    print(test((-2, 0), (2, 0), (-2, -2), (-1, -1), False, (0, 0)))
    print(test((-1, 0), (1, 0), (-1.1, -1), (-1.1, 1), False, (-1.1, 0)))
    # 直線　平行
    print(test((-2, 0), (2, 0), (-2, 0), (2, 0), False, None))
    # 線分
    print(test((-1, 0), (1, 0), (-1, -1), (-1, 1), True, (-1, 0)))
    print(test((-1, 0), (1, 0), (-1.1, -1), (-1.1, 1), True, None))
    print(test((-1.1, -1), (-1.1, 1), (-1, 0), (1, 0), True, None))
    pass


def intersect_line_quad_2d(line_p1, line_p2,
                           quad_p1, quad_p2, quad_p3, quad_p4, clip=False):
    """二次元の直線（線分）を凸包の四角形で切り取る。quad_p1~4は反時計回り
    :rtype: None | (Vector, Vector)
    """
    eps = 1e-8
    p1, p2 = line_p1.copy(), line_p2.copy()
    quad = [quad_p1, quad_p2, quad_p3, quad_p4]

    # lineが点の場合
    if p1 == p2:
        if geom.intersect_point_quad_2d(p1, *quad) == 1:
            return p1, p2
        else:
            return None
    # quadが点の場合
    if quad_p1 == quad_p2 == quad_p3 == quad_p4:
        line = p2 - p1
        f = cross2d(line, quad_p1 - p1)
        if f < eps:
            # p = (quad_p1 - p1).project(line) + p1
            d = dot2d(line, quad_p1 - p1)
            l = line.length
            f = d / l ** 2
            if clip and (f < 0 or f > 1):
                return None
            p = f * line + p1
            return p, p.copy()
        else:
            return None
    # lineがquadの内側に有る場合
    if clip:
        if geom.intersect_point_quad_2d(p1, *quad) == 1:
            if geom.intersect_point_quad_2d(p2, *quad) == 1:
                return p1, p2

    # quadの各辺との判定
    intersected = False
    for i in range(4):
        q1 = quad[i - 1]
        q2 = quad[i]
        if q1 == q2:
            # TODO: 何かしらの処理が要る？
            continue

        line = p2 - p1
        edge = q2 - q1

        # 平行
        if abs(cross2d(line, edge)) < eps:
            continue

        f1 = cross2d(edge, p1 - q1)
        f2 = cross2d(edge, p2 - q1)
        f3 = cross2d(line, q1 - p1)
        f4 = cross2d(line, q2 - p1)

        # 交点計算
        # if clip:
        #     # 線分が外側
        #     if f1 < 0 and f2 < 0:
        #         return None
        #     # NOTE:
        #     #     intersect_line_line_2d()は線分同士の判定を行う。
        #     #     平行でも線分同士が片方の頂点だけで重なるならその座標が返る
        #     #     (0, 0), (1, 0), (1, 0), (2, 0) -> (1, 0)
        #     p = geom.intersect_line_line_2d(p1, p2, q1, q2)
        # else:
        #     if f3 * f4 <= 0:  # edge上で交差
        #         d1 = cross2d(edge, q1 - p1)  # 省略 '/ edge.length'
        #         d2 = cross2d(edge, line)  # 省略 '/ edge.length'
        #         p = p1 + (d1 / d2) * line
        #     else:
        #         p = None
        if clip and f1 < 0 and f2 < 0:  # 線分が外側
            return None
        if (f1 * f2 <= 0 or not clip) and f3 * f4 <= 0:
            d1 = cross2d(edge, q1 - p1)  # 省略 '/ edge.length'
            d2 = cross2d(edge, line)  # 省略 '/ edge.length'
            p = p1 + (d1 / d2) * line
        else:
            p = None

        if p:
            if clip:
                if f1 < 0:  # p1が外側
                    p1 = p
                if f2 < 0:  # p2が外側
                    p2 = p.copy()
            else:
                if f1 < f2:
                    p1 = p
                else:
                    p2 = p
            if p1 == p2:
                return p1, p2
            intersected = True

    if intersected:
        return p1, p2
    else:
        return None


def intersect_aabb(*args):
    """from isect_aabb_aabb_v3()
    args: (aabb1, aabb2) or (min1, max1, min2, max2)
    """
    if len(args) == 2:
        min1 = args[0][:2]
        max1 = args[0][2:]
        min2 = args[1][:2]
        max2 = args[1][2:]
    else:
        min1, max1, min2, max2 = args
    for i in range(len(min1)):
        if max1[i] < min2[i] or max2[i] < min1[i]:
            return False
    return True


def test_intersect_line_quad_2d():
    V = Vector
    def test(p1, p2, q1, q2, q3, q4, clip, result, msg):
        eps = 1e-6
        r = intersect_line_quad_2d(
            V(p1), V(p2), V(q1), V(q2), V(q3), V(q4), clip)
        msg = msg + ': result -> ' + str(r)
        if result is None:
            assert r is None, msg
        elif isinstance(result, tuple):
            assert isinstance(r, tuple), msg
            re1 = V(result[0])
            re2 = V(result[1])
            r1, r2 = r
            assert ((re1 - r1).length < eps and (re2 - r2).length < eps or
                    (re1 - r2).length < eps and (re2 - r1).length < eps) , msg
        else:
            assert isinstance(r, Vector)
            assert (r - V(result)).length < eps, msg

    test((5, 5), (5, 5), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((5, 5), (5, 5)), '線分が点で内側')
    test((20, 5), (20, 5), (0, 0), (10, 0), (10, 10), (0, 10), True,
         None, '線分が点で外側')
    test((0, 0), (0, 0), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 0), (0, 0)), '線分が点で変と重なる')

    test((-5, 0), (0, 0), (1, 0), (1, 0), (1, 0), (1, 0), True,
        None, '線分。quadが点')
    test((2, 0), (5, 0), (1, 0), (1, 0), (1, 0), (1, 0), True,
        None, '線分。quadが点')
    test((-5, 0), (1, 0), (1, 0), (1, 0), (1, 0), (1, 0), True,
        ((1, 0), (1, 0)), '線分。quadが点')
    test((-1, 0), (2, 0), (1, 0), (1, 0), (1, 0), (1, 0), False,
        ((1, 0), (1, 0)), '直線。quadが点')

    test((5, 5), (6, 6), (0, 0), (10, 0), (10, 10), (0, 10), True,
         ((5, 5), (6, 6)), '線分が内側で交差しない')
    test((11, 5), (12, 6), (0, 0), (10, 0), (10, 10), (0, 10), True,
         None, '線分が外側で交差しない')
    test((-1, 5), (20, 5), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 5), (10, 5)), '線分の両頂点が外側で四角形と交差')
    test((5, 5), (20, 5), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((5, 5), (10, 5)), '線分の片方の頂点が外側で四角形と交差')
    test((0, 0), (5, 0), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 0), (5, 0)), '線分が辺上1')
    test((0, 0), (20, 0), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 0), (10, 0)), '線分が辺上2')
    test((-10, 0), (20, 0), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 0), (10, 0)), '線分が辺上3')
    test((-10, 0), (0, 0), (0, 0), (10, 0), (10, 10), (0, 10), True,
        ((0, 0), (0, 0)), '線分が外側にあり、片方の頂点は辺と接する')

    test((1, 1), (2, 1), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((0, 1), (10, 1)), '直線が内側')
    test((1, 1), (20, 1), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((0, 1), (10, 1)), '直線の片方の頂点が内側')
    test((-1, 1), (20, 1), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((0, 1), (10, 1)), '直線が外側。交差1')
    test((-10, -10), (20, 20), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((0, 0), (10, 10)), '直線が外側。交差2')
    test((11, 5), (12, 6), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((6, 0), (10, 4)), '線分が外側で交差')
    test((1, 0), (5, 0), (0, 0), (10, 0), (10, 10), (0, 10), False,
        ((0, 0), (10, 0)), '直線が辺上')
    print('ok')


###############################################################################
# 外接円
###############################################################################
def center_of_circumscribed_circle_tri(v1, v2, v3):
    """三角形の外接円の中心点を求める"""
    if v1 != v2 and v2 != v3 and v3 != v1:
        # 垂直二等分線の交差点を求める
        v12 = v2 - v1
        v13 = v3 - v1
        med12 = (v1 + v2) / 2
        med13 = (v1 + v3) / 2
        per12 = v13 - v13.project(v12)
        per13 = v12 - v12.project(v13)
        inter = geom.intersect_line_line(med12, med12 + per12,
                                        med13, med13 + per13)
        if inter:
            return (inter[0] + inter[1]) / 2
    return None


###############################################################################
# PCA
###############################################################################
def pca(vecs:'list of Vector or np.ndarray (2D or 3D)',
        to_rotation:'bool blender用の回転行列に変換する'=False):
    """
    主成分分析 (principal_component_analysis)
    分散が最小となり基底ベクトルを返す。
    返り値のvは基底ベクトルを並べた行列。基底座標系の回転行列を表す。
    X-Y-Zの順にソートする
    """

    if len(vecs) == 0:
        return None, None

    is_numpy_array = True if isinstance(vecs, np.ndarray) else False

    if is_numpy_array:
        arr = vecs
    else:
        arr = np.array(vecs)

    """ 主成分分析 """
    # arr_relative: 平均値を引いて、相対座標を求める。共分散行列 (引数axis=0:each column)
    arr_relative = arr - arr.mean(axis=0)
    w, v = np.linalg.eig(np.dot(arr_relative.T, arr_relative))

    if to_rotation:
        # X-Y-Zの順にsort
        v_bak = v.copy()
        o = w.argsort()
        col_num = v.shape[1]
        for i in range(col_num):
            v[:, i] = v_bak[:, o[col_num - 1 - i]]
        w.sort()

        if v.size == 9:  # 3d
            xvec = v[:, 0]
            yvec = v[:, 1]
            zvec = v[:, 2]
            if np.dot(np.cross(xvec, yvec), zvec) < 0.0:
                # 左手系になってしまうので、右手系に修正
                zvec[:] = -zvec
            if zvec[2] < 0.0:  # Zが上を向くように
                yvec[:] = -yvec
                zvec[:] = -zvec

    if is_numpy_array:
        return w, v
    else:
        # %return list(w), Matrix(v.transpose())  # 行優先から列優先への変換。
        return list(w), Matrix(v)


###############################################################################
# Bounding Box
###############################################################################
def get_obb(vectors):
    """
    Return OBB.
    vectors: list of Vector(2d or 3d) or
             2d array (shape=(-1, 3) or (-1, 2)) (row-major)
    return: (rotation and translation matrix, bounding box scale)
    X軸,Y軸,Z軸の順に長くなるようにソートしてある。
    """
    if len(vectors) == 0:
        return None, None

    # np.ndarrayに変換して計算
    size = 3 if len(vectors[0]) == 3 else 2
    is_numpy_array = isinstance(vectors, np.ndarray)
    if is_numpy_array:
        arr = vectors
    else:
        arr = np.array(vectors)
    w, rotmat = pca(arr, to_rotation=True)  # rotmatはObject.matrix_worldと同じように考えればいい

    # world座標のarrを、rotmat座標に変換。(world座標->local座標への変換と考えればいい)
    # vec * matの順で計算したいならrotmatを転値する必要がある
    invmat = np.linalg.inv(rotmat)
    arr_in_rotmat_coordinate = np.dot(arr, invmat.transpose())

    max_vals = np.max(arr_in_rotmat_coordinate, axis=0)
    min_vals = np.min(arr_in_rotmat_coordinate, axis=0)
    bb_location = np.dot((max_vals + min_vals) / 2, rotmat.transpose())
    bb_scale = max_vals - min_vals

    # convert
    if is_numpy_array:
        obb_matrix = np.identity(size + 1)
        obb_matrix[:size, :size] = rotmat[:size, :size]
        # %元から間違ってた？obb_matrix[size, :size] = bb_location
        obb_matrix[:size, size] = bb_location
    else:
        if size == 3:
            # %obb_matrix = Matrix(rotmat.transpose()).to_4x4()
            obb_matrix = Matrix(rotmat).to_4x4()
        else:
            # %obb_matrix = Matrix(rotmat.transpose())
            obb_matrix = Matrix(rotmat)
            obb_matrix.resize_4x4()
            obb_matrix = obb_matrix.to_3x3()  # bug? need ->4->3
        # %obb_matrix[size][:size] = bb_location
        obb_matrix.col[size][:size] = bb_location
        bb_scale = list(bb_scale)

    return obb_matrix, bb_scale


def get_aabb(vecs, matrix=None):
    """
    Return AABB.
    vecs: 2次元か3次元のVectorのリスト。Vectorの他にnp.dnarray, list, tupleが使える。
    matrix: この座標系に回転・拡縮したAABBで計算する。(返り値のbb_matrixはworld座標系のまま)
    retrurn: (rotation and translation matrix, bounding box scale)
    """
    if len(vecs) == 0:
        return None, None

    dim = 2 if len(vecs[0]) == 2 else 3
    is_numpy_array = True if isinstance(vecs, np.ndarray) else False
    arr = np.array(vecs) if not is_numpy_array else vecs

    if matrix:
        mat = np.array(matrix)[:dim, :dim]
        invmat = np.linalg.inv(mat)
        arr_bb = np.dot(arr, invmat)
        max_vals = np.max(arr_bb, axis=0)
        min_vals = np.min(arr_bb, axis=0)
        bb_location = np.dot((max_vals + min_vals) / 2, mat)
    else:
        mat = np.identity(dim)
        max_vals = np.max(arr, axis=0)
        min_vals = np.min(arr, axis=0)
        bb_location = (max_vals + min_vals) / 2
    bb_scale = max_vals - min_vals

    # arr -> py
    if is_numpy_array:
        bb_matrix = np.identity(dim + 1)
        bb_matrix[:dim, :dim] = mat[:dim, :dim]
        # %bb_matrix[dim, :dim] = bb_location
        bb_matrix[:dim, dim] = bb_location
    else:
        if dim == 3:
            bb_matrix = Matrix(mat).to_4x4()
        else:
            bb_matrix = Matrix(mat)
            bb_matrix.resize_4x4()
            bb_matrix = bb_matrix.to_3x3()  # bug? need ->4->3
        # %bb_matrix[dim][:dim] = bb_location
        bb_matrix.col[dim][:dim] = bb_location
        bb_scale = list(bb_scale)
    return bb_matrix, bb_scale


def get_cbb_center(vecs):
    # circular type bounding box.  計算方法間違ってる？
    # vecs: 2D vector list
    if len(vecs) == 1:
        return vecs[0]
    elif len(vecs) == 2:
        return (vecs[0] + vecs[1]) / 2
    median = reduce(lambda a, b: a + b, vecs, Vector()) * (1 / len(vecs))
    v1 = max(vecs, key=lambda v: (v - median).length)
    v2 = max(vecs, key=lambda v: (v - v1).length)
    v1 = max(vecs, key=lambda v: (v - v2).length)
    v2 = max(vecs, key=lambda v: (v - v1).length)
    vc = (v1 + v2) / 2

    v3 = None
    length = 0.0
    for v in (v for v in vecs if not (v is v1) and not (v is v2)):
        f = (v - vc).length
        if f > length:
            length = f
            v3 = v
    r = (v2 - v1).length / 2
    if v3 and length > r:
        d = (v3 - vc).length - r
        return vc + (v3 - vc).normalized() * d
    else:
        return vc


def check_obb_intersection_2d(mat1, scale1, mat2, scale2):
    """
    参考: http://marupeke296.com/COL_3D_No13_OBBvsOBB.html
    :param mat1: 3x3 Matrix. 各軸は直行していなくてもいい
    :type mat1: Matrix
    :param scale1: 2d Vector
    :type scale1: list | tuple | Vector
    :param mat2: 3x3 Matrix. 各軸は直行していなくてもいい
    :type mat2: Matrix
    :param scale2: 2d Vector
    :type scale2: list | tuple | Vector
    """
    xaxis1 = mat1.col[0].to_2d().normalized()
    yaxis1 = mat1.col[1].to_2d().normalized()
    loc1 = mat1.col[2].to_2d()
    sx1 = scale1[0] / 2
    sy1 = scale1[1] / 2

    xaxis2 = mat2.col[0].to_2d().normalized()
    yaxis2 = mat2.col[1].to_2d().normalized()
    loc2 = mat2.col[2].to_2d()
    sx2 = scale2[0] / 2
    sy2 = scale2[1] / 2

    for mat in (mat1, mat2):
        for i in range(2):
            axis = mat.col[i].to_2d()
            r1 = abs(axis.dot(xaxis1 * sx1)) + abs(axis.dot(yaxis1 * sy1))
            r2 = abs(axis.dot(xaxis2 * sx2)) + abs(axis.dot(yaxis2 * sy2))
            d12 = (loc1.project(axis) - loc2.project(axis)).length
            if d12 > r1 + r2:
                return False
    return True


def check_obb_intersection_3d(mat1, scale1, mat2, scale2):
    """
    参考: http://marupeke296.com/COL_3D_No13_OBBvsOBB.html
    :param mat1: 4x4 Matrix. 各軸は直行していなくてもいい
    :type mat1: Matrix
    :param scale1: 3d Vector
    :type scale1: list | tuple | Vector
    :param mat2: 4x4 Matrix. 各軸は直行していなくてもいい
    :type mat2: Matrix
    :param scale2: 3d Vector
    :type scale2: list | tuple | Vector
    """
    axes = []
    mat1_3x3 = mat1.to_3x3().normalized()
    mat2_3x3 = mat2.to_3x3().normalized()
    mat1_loc = mat1.col[3].to_3d()
    mat2_loc = mat2.col[3].to_3d()
    # 分離軸 方向ベクトル
    for mat in (mat1_3x3, mat2_3x3):
        for i in range(3):
            axes.append(mat.col[i])
    # 分離軸 双方の方向ベクトルに垂直
    for i in range(3):
        for j in range(3):
            axis = mat1_3x3.col[i].cross(mat2_3x3.col[j])
            if axis.length > 0.0:
                axes.append(axis.normalized())

    for axis in axes:
        if axis.length == 0.0:
            continue
        # obb1を分離軸に投影した時の長さ / 2
        r1 = 0
        for i in range(3):
            r1 += abs(axis.dot(mat1_3x3.col[i] * scale1[i] / 2))
        # obb2を分離軸に投影した時の長さ / 2
        r2 = 0
        for i in range(3):
            r2 += abs(axis.dot(mat2_3x3.col[i] * scale2[i] / 2))

        # obb1とobb2の中心をそれぞれ分離軸に投影した時の距離
        d12 = (mat1_loc.project(axis) - mat2_loc.project(axis)).length
        if d12 > r1 + r2:  # obb同士の間に隙間がある
            return False
    return True


def check_obb_intersection(mat1, scale1, mat2, scale2):
    if len(mat1) == 4:
        return check_obb_intersection_3d(mat1, scale1, mat2, scale2)
    else:
        return check_obb_intersection_2d(mat1, scale1, mat2, scale2)


def group_masses(masses, group_type='aabb', expand=0.0):
    """
    massesの要素毎にバウンドボックスを作って交差判定。交差するものをまとめたインデックスリストを返す。
    masses: [[Vector, ...], [Vector, ...], ...]
    expand: expand boundBox size
    返り値: e.g. [[0, 3, 2], [1, 4], [5]]
    """
    if not masses:
        return []
    dimension = 3 if len(masses[0][0]) == 3 else 2
    if group_type == 'aabb':
        bbs = [get_aabb(mass) for mass in masses]
    else:
        bbs = [get_obb(mass) for mass in masses]
    for bb in bbs:
        mat, scale = bb
        for i in range(len(scale)):
            scale[i] += expand * 2
    # d = {i:[] for i in range(len(bbs))}
    # for i, j in combinations(range(len(bbs)), 2):
    #     bb1 = bbs[i]
    #     bb2 = bbs[j]
    #     if dimension == 3:
    #         cross = check_obb_intersection_3d(bb1[0], bb1[1], bb2[0], bb2[1])
    #     else:
    #         cross = check_obb_intersection_2d(bb1[0], bb1[1], bb2[0], bb2[1])
    #     if cross:
    #         d[i].append(j)
    #         d[j].append(i)
    # # groups: 2D-list of indices of d.keys()
    # groups = vau.dict_to_linked_items_list(d)
    # TODO: 上記をコメントアウトして下記のものに書き換えたが動作未確認
    def key(bb1, bb2):
        if dimension == 3:
            return check_obb_intersection_3d(bb1[0], bb1[1], bb2[0], bb2[1])
        else:
            return check_obb_intersection_2d(bb1[0], bb1[1], bb2[0], bb2[1])
    groups = []
    localutils.utils.groupwith(bbs, key, order=groups)

    return groups


###############################################################################
# UV
###############################################################################
def calc_t(vec, v1, v2, v3, v4):
    v5 = v1 - v2 + v3 - v4
    v6 = -v1 + v4
    v7 = v1 - v2
    v8 = vec - v1

    a = v5.x * v7.y - v5.y * v7.x
    b = (v5.x * v8.y + v6.x * v7.y) - (v5.y * v8.x + v6.y * v7.x)
    c = v6.x * v8.y - v6.y * v8.x

    if a != 0:
        D = b ** 2 - 4 * a * c
        # delta2 = (b **2 - 4 * a* c) / a ** 2
        if D > 0.0:
            t1 = (-b + math.sqrt(D)) / (2.0 * a)
            t2 = (-b - math.sqrt(D)) / (2.0 * a)
            # t1 = -b / (2 * a) + math.sqrt(delta2) / 2
            # t2 = -b / (2 * a) - math.sqrt(delta2) / 2
            if 0.0 <= t1 <= 1.0:
                t = t1
            elif 0.0 <= t2 <= 1.0:
                t = t2
            else:  # 0.5に近い方を使う。
                if abs(t1 - 0.5) <= abs(t2 - 0.5):
                    t = t1
                else:
                    t = t2
        elif D == 0.0:
            t = -b / (2 * a)
        else:
            return None
    else:
        if b != 0:
            t = -c / b
        else:  # uv_in_tri_2dでvec==v3の場合
            if vec == v1 or vec == v4:
                return 0.0
            elif vec == v2 or vec == v3:
                return 1.0
            else:
                return None
    return t


def uv_in_quad_2d(vec, v1, v2, v3, v4):
    """
    四つのベクトルから成る四角形の中に有るベクトルのUVを求める。
    四角形のベクトルは反時計回りに渡す。
    v1->v2(v4->v3)方向がU, v1->v4(v2->v3)方向がV。
    v4 ------ v3
     |  vec   |
    v1 ----- v2

    X = (v4 - v1) * (1 - t) + (v3 - v2) * t
    Y = vec - v1 - (v2 - v1) * t
    X.cross(Y) == 0 となればいい。


    X -(展開)-> (v1 - v2 + v3 - v4) * t - v1 + v4 -(置換)-> a * t + d
    Y -(展開)-> (v1 - v2) * t + vec - v1          -(置換)-> c * t + d

    外積
    (at + b).x * (ct + d).y - (at + b).y * (ct + d).x =
    a.x * c.y * t**2 + a.x * d.y * t + b.x * c.y * t + b.x * d.y - (
    a.y * c.x * t**2 + a.y * d.x * t + b.y * c.x * t + b.y * d.x
    ) =
    a.x * c.y * t**2 + (a.x * d.y + b.x * c.y) * t + b.x * d.y - (
    a.y * c.x * t**2 + (a.y * d.x + b.y * c.x) * t + b.y * d.x
    ) =
    (a.x * c.y - a.y * c.x) * t**2 +
    ((a.x * d.y + b.x * c.y) - (a.y * d.x + b.y * c.x)) * t +
    b.x * d.y - b.y * d.x
    """

    u = calc_t(vec, v1, v2, v3, v4)
    v = calc_t(vec, v2, v3, v4, v1)
    if u is None or v is None:
        return None
    else:
        return u, v


def uv_in_tri_2d(vec, v1, v2, v3):
    """
    v1->v2方向がU
        v3
      / vec \
    v1 ----- v2
         p
    """

    u = calc_t(vec, v1, v2, v3, v3)
    if u is not None:
        p = (v2 - v1) * u + v1
        if (v3 - p).length > 0.0:
            v = (vec - p).length / (v3 - p).length
        else:
            v = 0.0
        return u, v
    return None


###############################################################################
# 空間分割
###############################################################################
# 2D --------------------------------------------------------------------------
def bit_saparete_32(n):
    # ビット分割関数
    n = (n | n << 8) & 0x00ff00ff
    n = (n | n << 4) & 0x0f0f0f0f
    n = (n | n << 2) & 0x33333333
    return (n | n << 1) & 0x55555555


def get_2d_morton_number(x, y):
    # 2D空間のモートン番号を算出

    bx = bit_saparete_32(x)
    by = bit_saparete_32(y)
    return bx | by << 1


def point_to_morton_number(x, y, sx, sy, level):
    """
    x, y: type:float. coordinate
    sx, sy: type:float. bounding box size
    level: subdivide level. 0 <= level <= 8
    """
    w = sx / 2 ** level
    xi = int(x / w)
    w = sy / 2 ** level
    yi = int(y / w)
    return get_2d_morton_number(xi, yi)


# 3D --------------------------------------------------------------------------
def bit_saparete_for_3d(n):
    # 3ビット毎に間隔を開ける関数
    n = (n | n << 8) & 0x0000f00f
    n = (n | n << 4) & 0x000c30c3
    n = (n | n << 2) & 0x00249249
    return n


def get_3d_morton_number(x, y, z):
    # 8分木モートン順序算出関数
    bx = bit_saparete_for_3d(x)
    by = bit_saparete_for_3d(y)
    bz = bit_saparete_for_3d(z)
    return bx | by << 1 | bz << 2


def get_morton_number_3d(x, y, z, sx, sy, sz, level):
    """
    x, y, z: type:float. coordinate
    sx, sy, sz: type:float. bounding box size
    level: subdivide level. 0 <= level <= 8
    """
    w = sx / 2 ** level
    xi = int(x / w)
    w = sy / 2 ** level
    yi = int(y / w)
    w = sz / 2 ** level
    zi = int(z / w)
    return get_3d_morton_number(xi, yi, zi)


def get_poly_morton_number_3d(vecs, sx, sy, sz, level):
    """
    vecs: type:list of Vector (tri or quad)
    sx, sy, sz: type:float. bounding box size
    level: subdivide level. 0 <= level <= 8
    return: (SpaceLevel, MortonNumber of SpaceLevel)
    """
    x = [v[0] for v in vecs]
    y = [v[1] for v in vecs]
    z = [v[2] for v in vecs]
    mmin = get_morton_number_3d(min(x), min(y), min(z), sx, sy, sz, level)
    mmax = get_morton_number_3d(max(x), max(y), max(z), sx, sy, sz, level)
    xor = mmin ^ mmax
    """
    if level == 3: lv = 1
    bit   000 001 000
    level   0   1   2   3
    """
    mask = 0b111 << (3 * (level - 1))
    for lv in range(level):
        if xor & mask:
            break
        mask >>= 3
    else:
        lv = level
    number = mmin >> (3 * lv)
    return lv, number


def make_liner_octree_call(polygons, bbox_min, bbox_max, level=4):
    """
    pylogons: 2d list of Vector. [(Vector, Vector, Vector), ...]
    bbox_min: (xmin, ymin, zmin)
    bbox_max: (xmax, ymax, zmax])
    level: int. bbox subdivide level
    """
    liner_octree_size = sum_geometric_progression(1, 8, level)
    liner_octree = [[] for i in range(liner_octree_size)]
    bbox_min = Vector(bbox_min)
    bbox_max = Vector(bbox_max)
    sx, sy, sz = bbox_max - bbox_min
    for poly in polygons:
        vecs = [v - bbox_min for v in poly]
        lv, morton_number = get_poly_morton_number_3d(vecs, sx, sy, sz, level)
        i = sum_geometric_progression(1, 8, lv - 1) + morton_number
        liner_octree[i].append(poly)


class Face:
    def __init__(self):
        self.e1 = None  # ptr
        self.e2 = None
        self.e3 = None


class Edge:
    def __init__(self):
        self.f = 0  # flag
        self.v1 = None  # ptr
        self.v2 = None
        self.v3 = None


def make_liner_octree(obs):
    pass


def sum_geometric_progression(a, r, f1, f2=None):
    """
    等比数列の和
        式 a*r**0 + a*r**1 + ... a*r**n
    0項 - n+1項
        a(1 - r ** (n + 1)) / (1 - r)
    m+1項 - n+1項
        a(r ** m - r ** (n + 1)) / (1 - r)
    """
    # f1,f2は0から始まるインデックス番号
    if f2 is None:
        n = f1
        return a * (1 - r ** (n + 1)) / (1 - r)
    else:
        m = f1
        n = f2
        return a * (r ** m - r ** (n + 1)) / (1 - r)


# m1 * m2 = m3
# m1 = m3 * m2.inverted()
# m2 = m1.inverted() * m3
