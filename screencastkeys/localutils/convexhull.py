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
Convex Hull:
    indices = convex_hull(vectors, eps=1e-6)  # 2D/3D
OBB:
    obb_matrix, obb_size = OBB(vecs, eps=1e-6)  # 2D/3D
"""

import math as _math
from collections import defaultdict as _defaultdict
from functools import reduce as _reduce
from itertools import chain as _chain, repeat as _repeat
import sys as _sys
import numpy as _np
import multiprocessing as _mp

from . import memoize as _memoize


__all__ = ['convex_hull', 'OBB']


_dot = _np.dot
_cross = _np.cross
_norm = _np.linalg.norm
_r_ = _np.r_  # 低速なので_np.insert()や_np.hstack()を使う
_array = _np.array


def _cross_2d(a, b):
    """_np.crossより速い"""
    return a[0] * b[1] - a[1] * b[0]


def _cross_3d(a, b):
    """_np.crossより速い"""
    return _array([a[1] * b[2] - a[2] * b[1],
                      a[2] * b[0] - a[0] * b[2],
                      a[0] * b[1] - a[1] * b[0]])


def _dot_2d(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _dot_3d(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _dot_4d(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + + a[3] * b[3]


# 高速化が見込めなかった為
_dot_2d = _dot_3d = _dot_4d = _dot


# @_memoize.Memoize.memoize(key=lambda v: tuple(v))
def _normalized(vec):
    # return vec / _norm(vec)
    if len(vec) == 2:
        return vec / _math.sqrt(vec[0] ** 2 + vec[1] ** 2)
    else:
        return vec / _math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)


def _normal_tri(v1, v2, v3):
    n1 = v2 - v1
    n2 = v3 - v2
    return _normalized(_cross_3d(n1, n2))


def _normal_quad(v1, v2, v3, v4):
    n1 = v3 - v1
    n2 = v4 - v2
    return _normalized(_cross_3d(n1, n2))


def _plane(plane_co, plane_no):
    no = _normalized(plane_no)
    w = -_dot_3d(no, plane_co)
    # return _np.append(no, w)
    return _array((no[0], no[1], no[2], w))


def _distance_point_to_plane(co, *args):
    """頂点と平面の距離を求める。法線の反対側だと負の値になる"""
    if len(args) == 1:
        plane = args[0]
    else:
        plane_co, plane_no = args
        no = _normalized(plane_no)
        w = -_dot_3d(no, plane_co)
        # plane = _np.append(no, w)
        plane = _array((no[0], no[1], no[2], w))
    if len(co) == 3:
        # co = _np.append(co, 1.0)
        co = _array((co[0], co[1], co[2], 1.0))
    return _dot_3d(plane, co)


def _saasin(fac):
    return _math.asin(max(-1.0, min(fac, 1.0)))


def _angle_normalized_v3v3(v1, v2):
    # this is the same as acos(dot_v3v3(v1, v2)), but more accurate
    if _dot_3d(v1, v2) >= 0.0:
        return 2.0 * _saasin(_norm(v1 - v2) / 2.0)
    else:
        return _math.pi - 2.0 * _saasin(_norm(v1 + v2) / 2.0)


def _axis_angle_to_quat(axis, angle):
    if _norm(axis) != 0.0:
        axis = _normalized(axis)
        phi = 0.5 * angle
        si = _math.sin(phi)
        co = _math.cos(phi)
        return _np.append(co, axis * si)
    else:
        return _array((1., 0., 0., 0.))


def _ortho_v3(v):
    """直行するベクトルを返す"""
    i = _np.argmax(v)
    if i == 0:
        return _array([-v[1] - v[2], v[0], v[0]])
    elif i == 1:
        return _array([v[1], -v[0] - v[2], v[1]])
    else:
        return _array([v[2], v[2], -v[0] - v[1]])


def _rotation_difference_v3v3(v1, v2):
    """v1からv2への回転を表す四元数を返す"""
    v1 = _normalized(v1)
    v2 = _normalized(v2)
    axis = _cross_3d(v1, v2)
    eps = _sys.float_info.epsilon
    if _norm(axis) > eps:
        angle = _angle_normalized_v3v3(v1, v2)
        quat = _axis_angle_to_quat(axis, angle)
    else:
        # degenerate case
        if _dot_3d(v1, v2) > 0.0:
            # Same vectors, zero rotation...
            quat = _array([1.0, 0.0, 0.0, 0.0])
        else:
            # Colinear but opposed vectors, 180 rotation...
            axis = _ortho_v3(v1)
            quat = _axis_angle_to_quat(axis, _math.pi)
    return quat


def _invert_qt(q):
    q = q.copy()
    f = _dot_3d(q, q)
    if f == 0.0:
        return q
    # conjugate_qt
    q[1:] *= -1
    # mul_qt_fl
    return q / f


def _mul_qt_qt(q1, q2):
    w1 = q1[0]
    v1 = q1[1:]
    w2 = q2[0]
    v2 = q2[1:]

    w = w1 * w2 - _dot_3d(v1, v2)
    v = w1 * v2 + w2 * v1 + _cross_3d(v1, v2)
    # return _np.append(w, v)
    # NOTE:
    # _np.append()を使うよりこの方が速い
    q = _array((w, 0., 0., 0.))
    q[1:] = v
    return q


def _mul_qt_v3(q, v):
    """時計回りに回転"""
    r = q.copy()
    r[1:] *= -1
    # p = _np.append(0.0, v)
    p = _np.zeros(4)
    p[1:] = v
    # 反時計回り
    # vec = _array(_mul_qt_qt(_mul_qt_qt(r, p), q)[1:])
    # 時計回り
    vec = _array(_mul_qt_qt(_mul_qt_qt(q, p), r)[1:])
    return vec


def _mul_mat_vec(mat, v):
    # 積の後のwの値は捨てる
    if len(mat) == 4 and len(v) in (3, 4):
        if len(v) == 3:
            # vec = _np.append(v, 1.0)
            vec = _np.ones(4)
            vec[:3] = v
            vec.shape = (4, 1)
        else:
            vec = _np.reshape(v, (4, 1))
        # return _np.resize(_dot_4d(mat, vec), 3)
        return _dot_4d(mat, vec).reshape(-1)[:3]
    elif len(mat) == 3 and len(v) == 3:
        vec = _dot_3d(mat, _np.reshape(v, (3, 1)))
        vec.shape = 3
        return vec
    elif len(mat) == 2 and len(v) == 2:
        vec = _dot_3d(mat, _np.reshape(v, (2, 1)))
        vec.shape = 2
        return vec


def _mul_mat_array(mat, v):
    """_mul_mat_vecと違い、ndarrayでのみ動作する。
    :type mat: _np.ndarray
    :type v: _np.ndarray
    """
    if v.ndim == 2:
        vec_size = v.shape[1]
    else:
        vec_size = v.size
    if mat.size == 16 and vec_size == 3:
        if v.ndim == 2:
            v = _np.insert(v, 3, 1.0, axis=1)
        else:
            v = _np.insert(v, 3, 1.0)
    if v.ndim == 2:
        result = _dot(mat, v.transpose()).transpose()
        if mat.size == 16 and vec_size == 3:
            result = result[:, :3]
    else:
        result = _dot(mat, _np.reshape(v, (v.size, 1))).reshape(v.size)
        if mat.size == 16 and vec_size == 3:
            result = result[:3]
    return result


def _quat_to_mat3(q):
    m = _np.identity(3)

    sqrt2 = _math.sqrt(2)
    q0 = sqrt2 * q[0]
    q1 = sqrt2 * q[1]
    q2 = sqrt2 * q[2]
    q3 = sqrt2 * q[3]

    qda = q0 * q1
    qdb = q0 * q2
    qdc = q0 * q3
    qaa = q1 * q1
    qab = q1 * q2
    qac = q1 * q3
    qbb = q2 * q2
    qbc = q2 * q3
    qcc = q3 * q3

    m[0][0] = 1.0 - qbb - qcc
    m[0][1] = qdc + qab
    m[0][2] = -qdb + qac

    m[1][0] = -qdc + qab
    m[1][1] = 1.0 - qaa - qcc
    m[1][2] = qda + qbc

    m[2][0] = qdb + qac
    m[2][1] = -qda + qbc
    m[2][2] = 1.0 - qaa - qbb

    return m.T


def _project_v3(v1, v2):
    v = _normalized(v2)
    d = _dot_3d(v1, v)
    return v * d


# class _MulQtArray:
#     def __init__(self, quat):
#         self.quat = quat
#     def mul_qt_v3(self, vec):
#         return _mul_qt_v3(self.quat, vec)[:2]
#     def calc(self, vecs):
#         pool = _mp.Pool()
#         return pool.map(self.mul_qt_v3, vecs)


###############################################################################
# Convex Hull 2D
###############################################################################
class _Vert:
    __slots__ = ['index', 'co', 'co4d']
    def __init__(self, index, co):
        self.index = index
        self.co = co
        if len(co) == 3:
            # self.co4d = _np.append(co, 1.0)
            self.co4d = _np.ones(4)
            self.co4d[:3] = co
        else:
            self.co4d = None


def _convex_hull_2d(vecs, eps=1e-6):
    """二次元の凸包(反時計回り)を求める。
    :param vecs: 2d array
    :param eps: 距離がこれ以下なら同一平面と見做す
    """
    n = len(vecs)
    if n == 0:
        return []
    elif n == 1:
        return [0]

    verts = [_Vert(i, v) for i, v in enumerate(vecs)]

    # なるべく離れている二頂点を求める
    # medium = _reduce(lambda a, b: a + b, vecs) / len(vecs)
    # v1 = max(verts, key=lambda v: _norm(v.co - medium))
    # v2 = max(verts, key=lambda v: _norm(v.co - v1.co))
    medium = _np.sum(vecs, axis=0) / len(vecs)
    v1 = verts[_norm(vecs - medium, axis=1).argmax()]
    v2 = verts[_norm(vecs - v1.co, axis=1).argmax()]
    line = v2.co - v1.co
    if _norm(line) <= eps:  # 全ての頂点が重なる
        return [0]
    if len(verts) == 2:
        return [v1.index, v2.index]

    # 三角形を構成する為の頂点を求める。v1-v2-v3は反時計回り。
    line = _normalized(line)
    # verts.sort(key=lambda v: abs(_cross(line, v.co - v1.co)))
    # v3 = verts[-1]
    v3 = verts[_np.abs(_cross(line, vecs - v1.co)).argmax()]

    dist = _cross_2d(line, v3.co - v1.co)
    if abs(dist) <= eps:
        # 全ての頂点が同一線上にある
        return [v1.index, v2.index]
    elif dist < 0:
        v1, v2 = v2, v1

    verts.remove(v1)
    verts.remove(v2)
    verts.remove(v3)

    loop = [v1, v2, v3]  # 反時計回り
    edge_verts = [[], [], []]  # 各辺の外側にある頂点 [v1-v2, v2-v3, v3-v1]
    # 最初にvertsをedge_vertsに分配する
    edge_lines = [_normalized(loop[(i + 1) % 3].co - loop[i].co)
                  for i in range(3)]
    for v in verts:
        for i in range(3):
            line = edge_lines[i]
            if _cross_2d(line, v.co - loop[i].co) < -eps:
                edge_verts[i].append(v)
                break

    num = len(loop)
    i = 0
    while True:
        if i > num - 1:
            break
        if not edge_verts[i]:
            i += 1
            continue

        v1 = loop[i]
        v2 = loop[(i + 1) % num]

        line = _normalized(v2.co - v1.co)
        # v3: 最も外側の頂点
        v3 = min(edge_verts[i], key=lambda v: _cross_2d(line, v.co - v1.co))
        if _cross_2d(line, v3.co - v1.co) < -eps:
            # ループへの挿入とedge_vertsの分割・再配置
            loop.insert(i + 1, v3)
            ed_verts = edge_verts[i][:]
            ed_verts.remove(v3)
            edge_verts[i] = []
            edge_verts.insert(i + 1, [])
            line1 = _normalized(v3.co - v1.co)
            line2 = _normalized(v2.co - v3.co)
            for v in ed_verts:
                if _cross_2d(line1, v.co - v1.co) < -eps:
                    edge_verts[i].append(v)
                elif _cross_2d(line2, v.co - v3.co) < -eps:
                    edge_verts[i + 1].append(v)
            num += 1
        else:
            edge_verts[i] = []
            i += 1

    return [v.index for v in loop]


###############################################################################
# Convex Hull 3D
###############################################################################
class _Face:
    __slots__ = ['verts', 'normal', 'edge_keys', 'outer_verts', 'plane']
    def __init__(self, v1, v2, v3):
        self.verts = [v1, v2, v3]
        self.normal = _normal_tri(v1.co, v2.co, v3.co)
        self.edge_keys = [tuple(sorted((self.verts[i - 1], self.verts[i]),
                                       key=lambda v: v.index))
                          for i in range(3)]
        self.outer_verts = []

        w = -_dot_3d(self.normal, self.verts[0].co)
        # self.plane = _np.append(self.normal, w)
        n = self.normal
        self.plane = _array((n[0], n[1], n[2], w))

    def distance(self, v):
        return _dot_3d(self.plane, _array((v[0], v[1], v[2], 1.0)))

    def distance4d(self, v):
        return _dot_4d(self.plane, v)



def _divide_outer_verts(faces, verts, eps):
    """vertsを各面に分配する"""
    for v in verts:
        for face in faces:
            if face.distance4d(v.co4d) > eps:
                face.outer_verts.append(v)
                break


def _find_remove_faces_re(remove_faces, vec4d, face, edge_faces, eps):
    """vecから見えている面をremove_facesに追加していく"""
    remove_faces.add(face)
    for ekey in face.edge_keys:
        pair = edge_faces[ekey]
        f = pair[1] if pair[0] == face else pair[0]
        if f not in remove_faces:
            if f.distance4d(vec4d) > eps:
                _find_remove_faces_re(remove_faces, vec4d, f, edge_faces, eps)


def _convex_hull_3d(vecs, eps=1e-6):
    """三次元の凸包を求める
    :param vecs: list of 3D array
    :type vecs: list | tuple | numpy.ndarray
    :param eps: 距離がこれ以下なら同一平面と見做す
    """

    n = len(vecs)
    if n == 0:
        return []
    elif n == 1:
        return [0]

    verts = [_Vert(i, v) for i, v in enumerate(vecs)]

    # なるべく離れている二頂点を求める
    # medium = _reduce(lambda a, b: a + b, vecs) / len(vecs)
    medium = _np.sum(vecs, axis=0) / len(vecs)

    # v1 = max(verts, key=lambda v: _norm(v.co - medium))
    # v2 = max(verts, key=lambda v: _norm(v.co - v1.co))
    v1 = verts[_norm(vecs - medium, axis=1).argmax()]
    v2 = verts[_norm(vecs - v1.co, axis=1).argmax()]
    line = v2.co - v1.co
    if _norm(line) <= eps:  # 全ての頂点が重なる
        return [0]
    if len(verts) == 2:
        return [v1.index, v2.index]

    # 三角形を構成する為の頂点を求める
    # v3 = max(verts, key=lambda v: _norm(_cross(line, v.co - v1.co)))
    v3 = verts[_norm(_cross(line, vecs - v1.co), axis=1).argmax()]
    # NOTE:
    # np.cross(vec, mat)[0] == np.cross(vec, mat[0])
    # np.cross(mat, vec)[0] == np.cross(mat[0], vec)

    if _norm(_cross_3d(_normalized(line), v3.co - v1.co)) <= eps:
        # 全ての頂点が同一線上にある
        return [v1.index, v2.index]
    if len(verts) == 3:
        return [v1.index, v2.index, v3.index]

    verts.remove(v1)
    verts.remove(v2)
    verts.remove(v3)

    pool = _mp.Pool()

    # 四面体を構成する為の頂点を求める
    normal = _normal_tri(v1.co, v2.co, v3.co)
    plane = _plane(v1.co, normal)
    def key_func(v):
        return abs(_distance_point_to_plane(v.co4d, plane))
    v4 = max(verts, key=key_func)
    if key_func(v4) <= eps:
        # 全ての頂点が平面上にある
        quat = _rotation_difference_v3v3(normal, _array([0., 0., 1.]))
        # vecs_2d = [_np.resize(_mul_qt_v3(quat, v), 2) for v in vecs]
        # vecs_2d = [_mul_qt_v3(quat, v)[:2] for v in vecs]
        result = pool.starmap_async(_mul_qt_v3, zip(_repeat(quat), vecs))
        vecs_2d = [v[:2] for v in result.get()]
        return _convex_hull_2d(vecs_2d, eps)
    verts.remove(v4)

    # 四面体作成
    #       ^ normal
    #    v3 |
    #     / |\
    # v1 /____\ v2
    #    \    /
    #     \  /
    #     v4
    if _distance_point_to_plane(v4.co, v1.co, normal) < 0.0:
        faces = [_Face(v1, v2, v3),
                 _Face(v1, v4, v2), _Face(v2, v4, v3), _Face(v3, v4, v1)]
    else:
        faces = [_Face(v1, v3, v2),
                 _Face(v1, v2, v4), _Face(v2, v3, v4), _Face(v3, v1, v4)]

    # 残りの頂点を各面に分配
    _divide_outer_verts(faces, verts, eps)

    # edge_faces作成
    edge_faces = _defaultdict(list)
    for face in faces:
        for ekey in face.edge_keys:
            edge_faces[ekey].append(face)

    while True:
        added = False
        for i in range(len(faces)):
            try:
                face = faces[i]
            except:
                break
            if not face.outer_verts:
                continue

            v1 = max(face.outer_verts, key=lambda v: face.distance4d(v.co4d))

            if face.distance4d(v1.co4d) > eps:
                # 凸包になるようにv1から放射状に面を貼る
                added = True

                # 隠れて不要となる面を求める
                remove_faces = set()
                _find_remove_faces_re(remove_faces, v1.co4d, face, edge_faces,
                                      eps)

                # remove_facesを多面体から除去して穴を開ける
                for f in remove_faces:
                    for ekey in f.edge_keys:
                        edge_faces[ekey].remove(f)
                    faces.remove(f)

                # 穴に面を貼る
                new_faces = []
                ekey_count = _defaultdict(int)
                for f in remove_faces:
                    for ekey in f.edge_keys:
                        ekey_count[ekey] += 1
                for ekey, cnt in ekey_count.items():
                    if cnt != 1:
                        continue
                    linkface = edge_faces[ekey][0]
                    v2, v3 = ekey
                    if linkface.verts[linkface.verts.index(v2) - 1] != v3:
                        v2, v3 = v3, v2
                    new_face = _Face(v1, v2, v3)
                    for key in new_face.edge_keys:
                        edge_faces[key].append(new_face)
                    new_faces.append(new_face)
                faces.extend(new_faces)

                # 頂点の再分配
                outer_verts = _reduce(lambda a, b: a + b,
                                      (f.outer_verts for f in remove_faces))
                if v1 in outer_verts:
                    outer_verts.remove(v1)
                _divide_outer_verts(new_faces, outer_verts, eps)

            else:
                face.outer_verts = []

        if not added:
            break

    # 忘れるべからず
    pool.close()
    pool.join()

    return [[v.index for v in f.verts] for f in faces]


###############################################################################
# Convex Hull
###############################################################################
def convex_hull(vecs, eps=1e-6):
    """三次元又は二次元の凸包を求める
    :param vecs: list of 2D/3D array
    :type vecs: list | tuple | numpy.ndarray
    :param eps: 距離がこれ以下なら同一平面と見做す
    """
    n = len(vecs)
    if n == 0:
        return []
    elif n == 1:
        return [0]

    # if not isinstance(vecs, _np.ndarray):
    #     vecs = _array(vecs, dtype=_np.float64)
    vecs = _np.asanyarray(vecs, dtype=_np.float64)

    if len(vecs[0]) == 2:
        return _convex_hull_2d(vecs, eps)
    else:
        return _convex_hull_3d(vecs, eps)


###############################################################################
# OBB
###############################################################################
def _closest_axis_on_plane(vecs, indices):
    """
    バウンディングボックスが最も小さくなる時、短い辺の方向を表す単位ベクトルを
    返す。
    """
    if len(vecs) == 0:
        return None
    dim = len(vecs[0])
    axis = None
    dist = 0.0
    for i in range(len(indices)):
        idx1 = indices[i - 1]
        idx2 = indices[i]
        v1 = vecs[idx1]
        v2 = vecs[idx2]
        line = _normalized(v2 - v1)
        dist_tmp = None
        for idx3 in indices:
            if idx3 == idx1 or idx3 == idx2:
                continue
            v3 = vecs[idx3]
            v13 = v3 - v1
            if dim == 3:
                d = _norm(_cross_3d(line, v13))
            else:
                d = abs(_cross_2d(line, v13))
            if dist_tmp is None or d > dist_tmp:
                dist_tmp = d
                axis_tmp = _normalized(v13 - _project_v3(v13, line))
        if axis is None or dist_tmp < dist:
            dist = dist_tmp
            axis = axis_tmp
    return axis


# @profile(column='tottime', list=50)
def OBB(vecs, r_indices=None, eps=1e-6):
    """Convex hull を用いたOBBを返す。
    Z->Y->Xの順で長さが最少となる軸を求める。
    :param vecs: list of 2D/3D array
    :type vecs: list | tuple | numpy.ndarray
    :param r_indices: listを渡すとconvexhullの結果を格納する
    :type r_indices: None | list
    :param eps: 種々の計算の閾値
    :return:
        (matrix, obb_size)
        matrix:
            OBBの回転と中心座標を表す。OBBが二次元ベクトルの場合は3x3、
            三次元なら4x4。
        obb_size:
            OBBの各軸の長さ。OBBと同じ次元。
    :rtype: (numpy.ndarray, numpy.ndarray)
    """

    if len(vecs) == 0:
        return None, None

    # if not isinstance(vecs, _np.ndarray):
    #     vecs = _array(vecs, dtype=_np.float64)
    vecs = _np.asanyarray(vecs, dtype=_np.float64)

    # 2D ----------------------------------------------------------------------
    if len(vecs[0]) == 2:
        mat = _np.identity(3)
        bb_size = _array([0., 0.])

        indices = _convex_hull_2d(vecs, eps)
        if r_indices:
            r_indices[:] = indices

        if len(indices) == 1:
            mat[:2, 2] = vecs[0]
        elif len(indices) == 2:
            v1 = vecs[indices[0]]
            v2 = vecs[indices[1]]
            xaxis = _normalized(v2 - v1)
            angle = _math.atan2(xaxis[1], xaxis[0])
            s = _math.sin(angle)
            c = _math.cos(angle)
            mat2 = _array([[c, -s], [s, c]])
            mat[:2, 0] = mat2[:, 0]
            mat[:2, 1] = mat2[:, 1]
            mat[:2, 2] = (v1 + v2) / 2
            bb_size[0] = _norm(v2 - v1)
        else:
            yaxis = _closest_axis_on_plane(vecs, indices)
            angle = _math.atan2(yaxis[1], yaxis[0]) - _math.pi / 2  # X軸
            s = _math.sin(angle)
            c = _math.cos(angle)
            mat2 = _array([[c, -s], [s, c]])
            s = _math.sin(-angle)
            c = _math.cos(-angle)
            imat2 = _array([[c, -s], [s, c]])

            rotvecs = _mul_mat_array(imat2, vecs)
            min_vec = rotvecs.min(axis=0)
            max_vec = rotvecs.max(axis=0)
            bb_size = max_vec - min_vec
            loc = (min_vec + max_vec) / 2

            mat[:2, 0] = mat2[:, 0]
            mat[:2, 1] = mat2[:, 1]
            mat[:2, 2] = _mul_mat_vec(mat2, loc)
        return mat, bb_size

    # 3D ----------------------------------------------------------------------
    pool = _mp.Pool()

    mat = _np.identity(4)
    bb_size = _array([0., 0., 0.])

    indices = _convex_hull_3d(vecs, eps)

    if r_indices:
        r_indices[:] = indices

    if isinstance(indices[0], int):  # 2d
        if len(indices) == 1:
            mat[:3, 3] = vecs[0]
            return mat, bb_size

        elif len(indices) == 2:
            # 同一線上
            v1 = vecs[indices[0]]
            v2 = vecs[indices[1]]
            xaxis = _normalized(v2 - v1)
            quat = _rotation_difference_v3v3(_array([1., 0., 0.]), xaxis)
            mat = _np.identity(4)
            mat[:3, :3] = _quat_to_mat3(quat)
            mat[:3, 3] = (v1 + v2) / 2
            bb_size[0] = _norm(v2 - v1)
            return mat, bb_size

        else:
            # 同一平面上
            medium = _np.sum(vecs, axis=0) / len(vecs)
            v1 = vecs[_norm(vecs - medium, axis=1).argmax()]
            v2 = vecs[_norm(vecs - v1, axis=1).argmax()]
            line = v2 - v1
            v3 = vecs[_norm(_cross(line, vecs - v1), axis=1).argmax()]

            zaxis = _normal_tri(v1, v2, v3)
            if zaxis[2] < 0.0:
                zaxis *= -1

            quat = _rotation_difference_v3v3(zaxis, _array([0., 0., 1.]))
            # rotvecs = [_mul_qt_v3(quat, v)[:2] for v in vecs]
            result = pool.starmap_async(_mul_qt_v3, zip(_repeat(quat), vecs))
            rotvecs = [v[:2] for v in result.get()]
            indices_2d = indices

    else:  # 3d
        indices_set = set(_chain.from_iterable(indices))
        zaxis = None
        dist = 0.0
        # 最も距離の近い面（平面）と頂点を求める
        for tri in indices:
            v1, v2, v3 = [vecs[i] for i in tri]
            normal = _normal_tri(v1, v2, v3)
            plane = _plane(v1, normal)
            d = 0.0
            for v4 in (vecs[i] for i in indices_set if i not in tri):
                f = abs(_distance_point_to_plane(v4, plane))
                d = max(f, d)
            if zaxis is None or d < dist:
                zaxis = -normal
                dist = d

        quat = _rotation_difference_v3v3(zaxis, _array([0., 0., 1.]))
        # rotvecs = [_np.resize(_mul_qt_v3(quat, v), 2) for v in vecs]
        # rotvecs = [_mul_qt_v3(quat, v)[:2] for v in vecs]
        result = pool.starmap_async(_mul_qt_v3, zip(_repeat(quat), vecs))
        rotvecs = [v[:2] for v in result.get()]
        indices_2d = _convex_hull_2d(rotvecs, eps)


    yaxis = _closest_axis_on_plane(rotvecs, indices_2d)
    yaxis = _mul_qt_v3(_invert_qt(quat), _np.append(yaxis, 0))

    xaxis = _cross_3d(yaxis, zaxis)
    xaxis = _normalized(xaxis)  # 不要？

    mat[:3, 0] = xaxis
    mat[:3, 1] = yaxis
    mat[:3, 2] = zaxis

    # OBBの大きさと中心を求める
    imat = _np.linalg.inv(mat)
    rotvecs = _mul_mat_array(imat, vecs)
    min_vec = rotvecs.min(axis=0)
    max_vec = rotvecs.max(axis=0)
    bb_size = max_vec - min_vec
    loc = (min_vec + max_vec) / 2
    mat[:3, 3] = _mul_mat_vec(mat, loc)

    pool.close()
    pool.join()
    return mat, bb_size


###############################################################################
# Test
###############################################################################
def _test(cnt):
    import random
    import time
    # coords = [_np.random.randn(2) for i in range(cnt)]
    coords = [[random.random() for i in range(3)] for i in range(cnt)]

    # coords = [[random.random() for i in range(2)] + [0.0] for i in range(cnt)]

    t = time.time()

    # indices = convex_hull(coords)

    obb_mat, obb_scale = OBB(coords)

    # print(indices[:5], '...')
    # print(obb_mat, obb_scale)

    # mat = _np.random.random(16).reshape((4, -1))
    # arr = _np.random.random(12).reshape((-1, 3))
    # vec = _np.random.random(3)
    # arr[0] = vec
    # print(_mul_mat_array(mat, arr)[0])
    # print(_mul_mat_array(mat, vec))
    # print(_mul_mat_vec(mat, vec))

    print(str(time.time() - t) + ' s')


if __name__ == '__main__':
    # _test(1000)
    import subprocess
    import cProfile
    cProfile.run('_test(50000)', 'convexhull.stats')
    subprocess.Popen('python3 ~/bin/gprof2dot.py -f pstats convexhull.stats '
                     '| dot -Tpng -o convexhull.png', shell=True)