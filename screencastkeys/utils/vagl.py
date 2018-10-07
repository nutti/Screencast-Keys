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


import math
import contextlib
import functools
import inspect

try:
    import OpenGL
    has_openge_module = True
except ImportError:
    has_openge_module = False

import bpy
import blf
from mathutils import Euler, Vector, Quaternion, Matrix
import bgl

from . import vamath as vam


"""
NOTE:
RegionView3D.view_matrix == modelview_matrix
RegionView3D.perspective_matrix == projection_matrix * modelview_matrix
persmat = winmat * viewmat

glColor(): GL_CURRENT_COLOR
glStencilMask(): GL_STENCIL_WRITEMASK
"""


GLA_PIXEL_OFS = 0.375


class Buffer:
    def __new__(self, type, dimensions=0, template=None):
        """
        :param type: GL_BYTE('bool','byte'), GL_SHORT('short'),
            GL_INT('int'), GL_FLOAT('float') or GL_DOUBLE('double')
        :type type: int | str
        :param dimensions: array size.
            e.g. 3:      [0, 0, 0]
                 [4, 2]: [(0, 0), (0, 0), (0, 0), (0, 0)]
        :type dimensions: int | list | tuple
        :param template: Used to initialize the Buffer
            e.g. list: [1, 2, 3], int: bgl.GL_BLEND
        :type template: None | sequence | int
        :return:
        :rtype:
        """
        if isinstance(type, str):
            type = type.lower()
            if type in ('bool', 'byte'):
                type = bgl.GL_BYTE
            elif type == 'short':
                type = bgl.GL_SHORT
            elif type == 'int':
                type = bgl.GL_INT
            elif type == 'float':
                type = bgl.GL_FLOAT
            elif type == 'double':
                type = bgl.GL_DOUBLE
            else:
                type = None

        return_int = isinstance(dimensions, int) and dimensions < 1
        if return_int:
            dim = 1
        else:
            dim = dimensions
        if template is None:
            buf = bgl.Buffer(type, dim)
        elif isinstance(template, int):
            if type == bgl.GL_BYTE:
                glGet = bgl.glGetBooleanv
            elif type == bgl.GL_SHORT:
                glGet = bgl.glGetIntegerv
            elif type == bgl.GL_INT:
                glGet = bgl.glGetIntegerv
            elif type == bgl.GL_FLOAT:
                glGet = bgl.glGetFloatv
            elif type == bgl.GL_DOUBLE:
                glGet = bgl.glGetDoublev
            else:
                msg = "invalid first argument type, should be one of " \
                      "GL_BYTE('bool','byte'), GL_SHORT('short'), " \
                      "GL_INT('int'), GL_FLOAT('float') or GL_DOUBLE('double')"
                raise AttributeError(msg)
            buf = bgl.Buffer(type, dim)
            glGet(template, buf)
        else:
            buf = bgl.Buffer(type, dim, template)

        if return_int:
            return buf[0]
        else:
            return buf


def glSwitch(attr, value):
    if value:
        bgl.glEnable(attr)
    else:
        bgl.glDisable(attr)


class GLSettings:
    def __init__(self, context, view_matrix=None, perspective_matrix=None):
        """
        :type context: bpy.types.Context
        :type view_matrix: mathutils.Matrix
        :type perspective_matrix: mathutils.Matrix
        """
        rv3d = context.region_data
        if view_matrix is None:
            if rv3d:
                view_matrix = rv3d.view_matrix
            else:
                view_matrix = Matrix.Identity(4)
        if perspective_matrix is None:
            if rv3d:
                perspective_matrix = rv3d.perspective_matrix
            else:
                perspective_matrix = Matrix.Identity(4)
        window_matrix = perspective_matrix * view_matrix.inverted()

        # type: <mathutils.Matrix>
        self.view_matrix = view_matrix
        self.window_matrix = window_matrix
        self.perspective_matrix = perspective_matrix

        # type: <bgl.Buffer>
        self.modelview_matrix = Buffer(
            'double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        self.projection_matrix = Buffer(
            'double', (4, 4), bgl.GL_PROJECTION_MATRIX)

        self._modelview_stack = []  # used in pop(), push()
        self._projection_stack = []  # used in pop(), push()

        region = context.region
        self.region_size = region.width, region.height
        window = context.window
        self.window_size = window.width, window.height

        # staticmethod
        self.Buffer = Buffer
        self.glSwitch = glSwitch

    # @staticmethod
    # def Buffer(type, dimensions=0, template=None):
    #     return Buffer(type, dimensions, template)

    # @staticmethod
    # def glSwitch(attr, value):
    #     glSwitch(attr, value)

    @staticmethod
    def mul_4x4_matrixd(m1, m2):
        """double型で大きさが16のBuffer同士の積"""
        matrix_mode = Buffer('int', 0, bgl.GL_MATRIX_MODE)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)  # GL_MAX_MODELVIEW_STACK_DEPTH: 32
        bgl.glPushMatrix()
        bgl.glLoadMatrixd(m1)
        bgl.glMultMatrixd(m2)
        mat = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        bgl.glPopMatrix()
        bgl.glMatrixMode(matrix_mode)
        return mat

    @classmethod
    def get_matrix(cls, matrix_type, buffer=False):
        """GL_MODELVIEW_MATRIX, GL_PROJECTION_MATRIX を元にしたMatrixを返す。
        self.modelview_matrix等のインスタンス属性は使用しない。
        Spaceのコールバック関数の中でこのメソッドを呼んだ場合、
        PRE_VIEW / POST_VIEW と POST_PIXEL で違いがあるので十分注意すること。
        :param buffer: TrueだとBufferオブジェクトを返す。
        :rtype: Matrix | Buffer
        """
        if isinstance(matrix_type, int):
            if matrix_type == bgl.GL_MODELVIEW_MATRIX:
                matrix_type = 'modelview'
            elif matrix_type == bgl.GL_PROJECTION_MATRIX:
                matrix_type = 'projection'
            else:
                return None
        elif isinstance(matrix_type, str):
            matrix_type = matrix_type.lower()
        else:
            return None

        modelview = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        vmat = Matrix(modelview).transposed()
        if matrix_type.startswith(('model', 'view')):
            if buffer:
                return modelview
            else:
                return vmat
        else:
            projection = Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX)
            wmat = Matrix(projection).transposed()
            if matrix_type.startswith(('proj', 'win')):
                if buffer:
                    return projection
                else:
                    return wmat
            elif matrix_type.startswith('pers'):
                if buffer:
                    return cls.mul_4x4_matrixd(projection, modelview)
                else:
                    return wmat * vmat

    @staticmethod
    def font_size(id=0, size=11, dpi=None):
        if dpi is None:
            dpi = bpy.context.user_preferences.system.dpi
        blf.size(id, size, dpi)

    @classmethod
    def _load_matrix(cls, modelview=None, projection=None):
        matrix_mode = Buffer('int', 0, bgl.GL_MATRIX_MODE)
        if modelview:
            bgl.glMatrixMode(bgl.GL_MODELVIEW)
            bgl.glLoadIdentity()  # glLoadMatrix()にも必須
            if isinstance(modelview, bgl.Buffer):
                bgl.glLoadMatrixd(modelview)
        if projection:
            bgl.glMatrixMode(bgl.GL_PROJECTION)
            bgl.glLoadIdentity()  # glLoadMatrix()にも必須
            if isinstance(projection, bgl.Buffer):
                bgl.glLoadMatrixd(projection)
        bgl.glMatrixMode(matrix_mode)

    def push(self, mask=bgl.GL_ALL_ATTRIB_BITS):
        """glPushAttrib()で状態変数を保存しておく。
        glPushMatrix(), glPopMatrix() は GL_MAX_MODELVIEW_STACK_DEPTH が 32
        なのに対し、GL_MAX_PROJECTION_STACK_DEPTH が 4 しか無い為、使用しない。
        """
        bgl.glPushAttrib(mask)
        self._modelview_stack.append(
            Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX))
        self._projection_stack.append(
            Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX))

    def pop(self):
        """push()時の状態に戻す。"""
        self._load_matrix(self._modelview_stack.pop(),
                          self._projection_stack.pop())
        bgl.glPopAttrib()

    @classmethod
    @contextlib.contextmanager
    def push_attrib(cls, mask=bgl.GL_ALL_ATTRIB_BITS, matrix=True):
        """with文で使用する。
        with GLSettings.push_attrib():
            ...
        """

        bgl.glPushAttrib(mask)
        modelview = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        projection = Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX)

        yield

        if matrix:
            cls._load_matrix(modelview, projection)
        bgl.glPopAttrib()

    @contextlib.contextmanager
    def region_view3d_space(self):
        """with文、又はデコレータとして使用
        """
        modelview_mat = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        projection_mat = Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX)
        view_mat = Buffer('double', (4, 4), self.view_matrix.transposed())
        win_mat = Buffer('double', (4, 4), self.window_matrix.transposed())
        self._load_matrix(view_mat, win_mat)

        yield

        self._load_matrix(modelview_mat, projection_mat)

    @contextlib.contextmanager
    def region_pixel_space(self):
        """with文、又はデコレータとして使用

        NOTE: Z値の範囲: near 〜 far
        perspective_matrix * vec4d / w: -1.0 〜 +1.0
        gluProject: 0.0 〜 +1.0
        POST_PIXEL: +100 〜 -100
        Z-Buffer: 0.0 〜 +1.0
        """

        modelview_mat = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        projection_mat = Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX)
        matrix_mode = Buffer('int', 1, bgl.GL_MATRIX_MODE)

        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glLoadIdentity()  # 必須
        w, h = self.region_size
        # wmOrtho2_region_pixelspace(), wmOrtho2() 参照
        ofs = -0.01
        bgl.glOrtho(ofs, w + ofs, ofs, h + ofs, -100, 100)

        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glLoadIdentity()

        bgl.glMatrixMode(matrix_mode[0])

        yield

        self._load_matrix(modelview_mat, projection_mat)

    @contextlib.contextmanager
    def window_pixel_space(self):
        """with文、又はデコレータとして使用
        """

        win_width, win_height = self.window_size

        modelview_mat = Buffer('double', (4, 4), bgl.GL_MODELVIEW_MATRIX)
        projection_mat = Buffer('double', (4, 4), bgl.GL_PROJECTION_MATRIX)
        matrix_mode = Buffer('int', 1, bgl.GL_MATRIX_MODE)
        viewport = Buffer('int', 4, bgl.GL_VIEWPORT)

        bgl.glViewport(0, 0, win_width, win_height)
        bgl.glMatrixMode(bgl.GL_PROJECTION)
        bgl.glLoadIdentity()
        ofs = -0.01
        bgl.glOrtho(ofs, win_width + ofs, ofs, win_height + ofs, -100, 100)
        bgl.glMatrixMode(bgl.GL_MODELVIEW)
        bgl.glLoadIdentity()
        bgl.glMatrixMode(matrix_mode[0])

        yield

        bgl.glViewport(*viewport)
        self._load_matrix(modelview_mat, projection_mat)

        # NOTE:
        # PyOpenGLの場合
        # modelview_mat = (ctypes.c_double * 16)()
        # glGetDoublev(GL_MODELVIEW_MATRIX, ctypes.byref(modelview_mat))
        #
        # glMatrixMode()等でパラメーターにGLenumが要求される場合は
        # c_uintでなければならない
        # matrix_mode = ctypes.c_uint()
        # glGetIntegerv(GL_MATRIX_MODE, ctypes.byref(matrix_mode))
        # glMatrixMode(matrix_mode)


def gluProject(vec):
    """bgl.gluProjectを呼ぶ。
    返り値は左手系の座標系になり、Z値は0.0~1.0にクリッピングされる
    """
    modelview = Buffer('double', 16, bgl.GL_MODELVIEW_MATRIX)
    projection = Buffer('double', 16, bgl.GL_PROJECTION_MATRIX)
    # viewport = Buffer('int', 4, bgl.GL_VIEWPORT)
    region = bpy.context.region
    viewport = Buffer('int', 4, [0, 0, region.width, region.height])
    x = Buffer('double', 1)
    y = Buffer('double', 1)
    z = Buffer('double', 1)
    bgl.gluProject(vec[0], vec[1], vec[2],
                   modelview, projection, viewport,
                   x, y, z)
    return Vector((x[0], y[0], z[0]))


def draw_circle(x, y, radius, subdivide, poly=False):
    r = 0.0
    dr = math.pi * 2 / subdivide
    if poly:
        subdivide += 1
        bgl.glBegin(bgl.GL_TRIANGLE_FAN)
        bgl.glVertex2f(x, y)
    else:
        bgl.glBegin(bgl.GL_LINE_LOOP)
    for i in range(subdivide):
        bgl.glVertex2f(x + radius * math.cos(r), y + radius * math.sin(r))
        r += dr
    bgl.glEnd()


def draw_box(xmin, ymin, w, h, angle=0.0, poly=False, colors=None):
    """左下から反時計回りに描画。
    :param angle: 0.0以外なら(xmin, ymin)を中心に回転する
    :param colors: 各頂点に色を指定する[[R,G,B], ...] or [[R,G,B,A], ...]
    """
    coords = ((xmin, ymin),
              (xmin + w, ymin),
              (xmin + w, ymin + h),
              (xmin, ymin + h))
    if angle != 0.0:
        m = Matrix.Rotation(angle, 2)
        v = Vector(coords[0])
        coords = [m * (Vector(co) - v) + v for co in coords]

    bgl.glBegin(bgl.GL_QUADS if poly else bgl.GL_LINE_LOOP)
    if colors:
        glColor = bgl.glColor3f if len(colors[0]) == 3 else bgl.glColor4f
        for co, col in zip(coords, colors):
            glColor(*col)
            bgl.glVertex2f(*co)
    else:
        for co in coords:
            bgl.glVertex2f(*co)
    bgl.glEnd()


def draw_triangle(v1, v2, v3, poly=False):
    if len(v1) == 3:
        func = bgl.glVertex3f
    else:
        func = bgl.glVertex2f
    if poly:
        bgl.glBegin(bgl.GL_TRIANGLES)
    else:
        bgl.glBegin(bgl.GL_LINE_LOOP)
    func(*v1)
    func(*v2)
    func(*v3)
    bgl.glEnd()


def draw_triangle_relative(base, base_length, top_relative, poly=False):
    v0 = Vector(base)
    v = (Vector([-top_relative[1], top_relative[0]])).normalized()
    v *= base_length / 2
    v1 = v0 + v
    v2 = v0 - v
    v3 = v0 + Vector(top_relative)
    draw_triangle(v1, v2, v3, poly)


def draw_trapezoid_get_vectors(base, top_relative, base_length, top_length):
    # base左, base右, top右, top左
    v0 = Vector(base)
    v = (Vector([-top_relative[1], top_relative[0]])).normalized()
    vb = v * base_length / 2
    v1 = v0 + vb
    v2 = v0 - vb
    vt = v * top_length / 2
    v3 = v0 + Vector(top_relative) - vt
    v4 = v0 + Vector(top_relative) + vt
    return v1, v2, v3, v4


def draw_trapezoid(base, top_relative, base_length, top_length, poly=False):
    # base左, base右, top右, top左
    v1, v2, v3, v4 = draw_trapezoid_get_vectors(base, top_relative,
                                                base_length, top_length)
    bgl.glBegin(bgl.GL_QUADS if poly else bgl.GL_LINE_LOOP)
    bgl.glVertex2f(*v1)
    bgl.glVertex2f(*v2)
    bgl.glVertex2f(*v3)
    bgl.glVertex2f(*v4)
    bgl.glEnd()


def draw_arc12(x, y, radius, start_angle, end_angle, subdivide):  # いずれ削除
    # 十二時から時計回りに描画
    v = Vector([0, 1, 0])
    e = Euler((0, 0, -start_angle))
    m = e.to_matrix()
    v = m * v
    if end_angle >= start_angle:
        a = (end_angle - start_angle) / (subdivide + 1)
    else:
        a = (end_angle + math.pi * 2 - start_angle) / (subdivide + 1)
    e = Euler((0, 0, -a))
    m = e.to_matrix()

    bgl.glBegin(bgl.GL_LINE_STRIP)
    for i in range(subdivide + 2):
        v1 = v * radius
        bgl.glVertex2f(x + v1[0], y + v1[1])
        v = m * v
    bgl.glEnd()


def draw_quad_fan(x, y, inner_radius, outer_radius,
                  start_angle, end_angle, edgenum=16):
    # 三時から反時計回りに描画
    start = vam.normalize_angle(start_angle)
    end = vam.normalize_angle(end_angle)
    if end < start:
        end += math.pi * 2
    d = (end - start) / edgenum
    a = start
    bgl.glBegin(bgl.GL_QUAD_STRIP)
    for i in range(edgenum + 1):
        bgl.glVertex2f(x + inner_radius * math.cos(a),
                       y + inner_radius * math.sin(a))
        bgl.glVertex2f(x + outer_radius * math.cos(a),
                       y + outer_radius * math.sin(a))
        a += d
    bgl.glEnd()


def draw_arc_get_vectors(x, y, radius, start_angle, end_angle, edgenum=16):
    # 三時から反時計回り angle:radians
    start = vam.normalize_angle(start_angle)
    end = vam.normalize_angle(end_angle)
    if end < start:
        end += math.pi * 2
    d = (end - start) / edgenum
    a = start
    l = []
    for i in range(edgenum + 1):
        l.append(Vector([x + radius * math.cos(a), y + radius * math.sin(a)]))
        a += d
    return l


def draw_arc(x, y, radius, start_angle, end_angle, edgenum=16):
    # 三時から反時計回りに描画 angle:radians
    l = draw_arc_get_vectors(x, y, radius, start_angle, end_angle, edgenum)
    bgl.glBegin(bgl.GL_LINE_STRIP)
    for v in l:
        bgl.glVertex2f(*v)
    bgl.glEnd()


def draw_arrow(nockx, nocky, headx, heady, headlength=10,
               headangle=math.radians(70), headonly=False):
    """
    nockx, nocky: 筈
    headx, heady: 鏃
    headangle: 0 <= headangle <= 180
    headlength: nockとhead上での距離
    """
    if nockx == headx and nocky == heady or headonly and headlength == 0:
        return
    angle = max(min(math.pi / 2, headangle / 2), 0)  # 箆との角度
    vn = Vector((nockx, nocky))
    vh = Vector((headx, heady))
    # if headonly:
    #     vh = vh + (vh - vn).normalized() * headlength
    #     headx, heady = vh

    bgl.glBegin(bgl.GL_LINES)
    # shaft
    if not headonly:
        bgl.glVertex2f(nockx, nocky)
        bgl.glVertex2f(headx, heady)
    # head
    if headlength:
        length = headlength / math.cos(angle)
        vec = (vn - vh).normalized() * length
        vec.resize_3d()
        q = Quaternion((0, 0, 0, -1))
        q.angle = angle
        v = q * vec
        bgl.glVertex2f(headx, heady)
        bgl.glVertex2f(headx + v[0], heady + v[1])
        q.angle = -angle
        v = q * vec
        bgl.glVertex2f(headx, heady)
        bgl.glVertex2f(headx + v[0], heady + v[1])
    bgl.glEnd()


def draw_sun(x, y, radius, subdivide=16, raydirections=(),
             raylength=10, raystartoffset=0):
    draw_circle(x, y, radius, subdivide)
    bgl.glBegin(bgl.GL_LINES)
    if isinstance(raylength, (int, float)):
        llist = [raylength for i in range(len(raydirections))]
    else:
        llist = raylength
    for i, angle in enumerate(raydirections):
        bgl.glVertex2f(x + (radius + raystartoffset) * math.cos(angle), \
                       y + (radius + raystartoffset) * math.sin(angle))
        bgl.glVertex2f(x + (radius + llist[i]) * math.cos(angle), \
                       y + (radius + llist[i]) * math.sin(angle))
    bgl.glEnd()


# def draw_rounded_box(xmin, ymin, xmax, ymax, round_radius, poly=False):
#     r = min(round_radius, (xmax - xmin) / 2, (ymax - ymin) / 2)
#     bgl.glBegin(bgl.GL_POLYGON if poly else bgl.GL_LINE_LOOP)
#     if round_radius > 0.0:
#         pi = math.pi
#         l = []
#         # 左下
#         l += draw_arc_get_vectors(xmin + r, ymin + r, r, pi, pi * 3 / 2, 4)
#         # 右下
#         l += draw_arc_get_vectors(xmax - r, ymin + r, r, pi * 3 / 2, 0.0, 4)
#         # 右上
#         l += draw_arc_get_vectors(xmax - r, ymax - r, r, 0.0, pi / 2, 4)
#         # 左上
#         l += draw_arc_get_vectors(xmin + r, ymax - r, r, pi / 2, pi, 4)
#         for v in l:
#             bgl.glVertex2f(*v)
#     else:
#         bgl.glVertex2f(xmin, ymin)
#         bgl.glVertex2f(xmax, ymin)
#         bgl.glVertex2f(xmax, ymax)
#         bgl.glVertex2f(xmin, ymax)
#     bgl.glEnd()


def blend_color(col1, col2, fac):
    f = 1.0 - fac
    return [c1 * fac + c2 * f for c1, c2 in zip(col1, col2)]


def shade_color(color, shadetop, shadedown):
    color = list(color)
    f1 = shadetop / 255.
    f2 = shadedown / 255.
    top = [max(0.0, min(f + f1, 1.0)) for f in color[:3]] + color[3:4]
    down = [max(0.0, min(f + f2, 1.0)) for f in color[:3]] + color[3:4]
    return top, down


def thin_color(color, alpha:'0.0 ~ 1.0'):
    return [color[0], color[1], color[2], color[3] * alpha]


def draw_rounded_box(x, y, w, h, round_radius, poly=False,
                     shade_color_top=None, shade_color_bottom=None):
    def circle_verts_num(r):
        """描画に最適な？円の頂点数を求める"""
        n = 32
        threshold = 2.0  # pixcel
        while True:
            if r * 2 * math.pi / n > threshold:
                return n
            n -= 4
            if n < 1:
                return 1

    num = circle_verts_num(round_radius)
    n = int(num / 4) + 1
    pi = math.pi
    angle = pi * 2 / num
    use_shade = shade_color_top and shade_color_bottom
    if use_shade:
        glColorFunc = getattr(bgl, 'glColor' + str(len(shade_color_top)) + 'f')
        def set_color(yco):
            f1 = (yco - y) / h
            f2 = 1.0 - f1
            col = [a * f1 + b * f2
                   for a, b in zip(shade_color_top, shade_color_bottom)]
            glColorFunc(*col)
        shade_model = Buffer('int', 0, bgl.GL_SHADE_MODEL)
        bgl.glShadeModel(bgl.GL_SMOOTH)
    if poly:
        bgl.glBegin(bgl.GL_QUAD_STRIP)
        x0 = x + round_radius
        x1 = x + w - round_radius
        for y0, a0, a1 in ((y, pi * 1.5, pi * 1.5), (y + h, pi, 0.0)):
            for i in range(n):
                if y0 == y:
                    yco = y0 + round_radius + round_radius * math.sin(a0)
                else:
                    yco = y0 - round_radius + round_radius * math.sin(a0)
                if use_shade:
                    set_color(yco)
                bgl.glVertex2f(x0 + round_radius * math.cos(a0), yco)
                bgl.glVertex2f(x1 + round_radius * math.cos(a1), yco)
                a0 -= angle
                a1 += angle
        bgl.glEnd()
    else:
        bgl.glBegin(bgl.GL_LINE_LOOP)
        for x0, y0, a in ((x + round_radius, y + round_radius, pi),
                          (x + w - round_radius, y + round_radius, pi * 1.5),
                          (x + w - round_radius, y + h - round_radius, 0.0),
                          (x + round_radius, y + h - round_radius, pi * 0.5)):
            for i in range(n):
                xco = x0 + round_radius * math.cos(a)
                yco = y0 + round_radius * math.sin(a)
                if use_shade:
                    set_color(yco)
                bgl.glVertex2f(xco, yco)
                a += angle
        bgl.glEnd()
    if use_shade:
        bgl.glShadeModel(shade_model)


def make_PBO(size, data=None):
    import ctypes as ct
    from OpenGL import GL
    from OpenGL.raw.GL.ARB.pixel_buffer_object import GL_PIXEL_PACK_BUFFER_ARB
    from OpenGL.raw.GL.ARB.vertex_buffer_object import (
        glBufferDataARB, glBindBufferARB, GL_STREAM_READ_ARB,
        GL_DYNAMIC_READ_ARB, GL_STATIC_READ_ARB, glGenBuffersARB,
        GL_STREAM_COPY_ARB, GL_STREAM_DRAW_ARB, GL_STATIC_COPY_ARB)
    if 0:
        pbo_id = GL.glGenBuffers(1)  # glGenBuffersARB(1, ct.c_int())
    else:
        pbo_id_ = ct.c_int()
        glGenBuffersARB(1, pbo_id_)
        pbo_id = pbo_id_.value
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, pbo_id)
    if data is None:
        # data = (ct.c_byte * size)()
        data = ct.c_void_p()
    glBufferDataARB(GL_PIXEL_PACK_BUFFER_ARB, size, data,
                    GL_STREAM_COPY_ARB)
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, 0)
    return pbo_id


def delete_PBO(pbo_id):
    from OpenGL import GL
    from OpenGL.raw.GL.ARB.vertex_buffer_object import glDeleteBuffersARB
    if 0:
        GL.glDeleteBuffers(1, [pbo_id])  # glDeleteBuffersARB(1, [pbo_id])
    else:
        glDeleteBuffersARB(1, [pbo_id])


def make_PBO_map_buffer(pbo_id):
    from OpenGL.raw.GL.ARB.pixel_buffer_object import GL_PIXEL_PACK_BUFFER_ARB
    from OpenGL.raw.GL.ARB.vertex_buffer_object import (
        glBindBufferARB, GL_READ_ONLY_ARB, GL_READ_WRITE_ARB, glMapBufferARB)
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, pbo_id)
    addr = glMapBufferARB(GL_PIXEL_PACK_BUFFER_ARB, GL_READ_WRITE_ARB)
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, 0)
    return addr


def delete_PBO_map_buffer(pbo_id):
    from OpenGL.raw.GL.ARB.pixel_buffer_object import GL_PIXEL_PACK_BUFFER_ARB
    from OpenGL.raw.GL.ARB.vertex_buffer_object import (
        glBindBufferARB, glUnmapBufferARB)
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, pbo_id)
    glUnmapBufferARB(GL_PIXEL_PACK_BUFFER_ARB)
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, 0)


# FIXME: 使用間隔が短いと画像が乱れる
def screenshot_raw(x, y, w, h, pbo_id,
                   mode=bgl.GL_FRONT, format=bgl.GL_RGBA, type=bgl.GL_BYTE):
    """スクリーンショットを撮ってRGBAのバッファを返す
    :param x: Window.x
    :type x: int
    :param y: Window.y
    :type y: int
    :param w: Window.width
    :type w: int
    :param h: Window.height
    :type h: int
    :param mode: 読み込み先
    :type mode: int
    :param format: bgl.GL_RGBA, bgl.RGB, ...
    :type format: int
    :param type: バッファの型。bgl.GL_BYTE, bgl.GL_INT, ...
    :type type: int
    :rtype: ct._CData
    """
    import ctypes as ct
    from OpenGL import GL
    from OpenGL.raw.GL.ARB.pixel_buffer_object import GL_PIXEL_PACK_BUFFER_ARB
    from OpenGL.raw.GL.ARB.vertex_buffer_object import (
        glBindBufferARB, glMapBufferARB, glUnmapBufferARB, GL_READ_ONLY_ARB,
        glBufferDataARB, GL_STREAM_READ_ARB
    )

    formats = {
        bgl.GL_RGBA: GL.GL_RGBA,
        bgl.GL_BGRA: GL.GL_BGRA,
        bgl.GL_RGB: GL.GL_RGB,
        bgl.GL_BGR: GL.GL_BGR,
        # TODO: 他の値
    }
    types = {
        bgl.GL_BYTE: (ct.c_byte, GL.GL_BYTE),
        bgl.GL_UNSIGNED_BYTE: (ct.c_ubyte, GL.GL_UNSIGNED_BYTE),
        bgl.GL_SHORT: (ct.c_short, GL.GL_SHORT),
        bgl.GL_UNSIGNED_SHORT: (ct.c_ushort, GL.GL_UNSIGNED_SHORT),
        bgl.GL_INT: (ct.c_int, GL.GL_INT),
        bgl.GL_UNSIGNED_INT: (ct.c_uint, GL.GL_UNSIGNED_INT),
        bgl.GL_FLOAT: (ct.c_float, GL.GL_FLOAT),
        bgl.GL_DOUBLE: (ct.c_double, GL.GL_DOUBLE),
    }

    if format in {bgl.GL_RGBA, bgl.GL_BGRA}:
        depth = 4
    elif format in {bgl.GL_RGB, bgl.GL_BGR}:
        depth = 3
    else:
        depth = 1
    ct_array_type = types[type][0] * (w * h * depth)

    alignment_bak = bgl.Buffer(bgl.GL_INT, 1)
    bgl.glGetIntegerv(bgl.GL_PACK_ALIGNMENT, alignment_bak)
    if format in {bgl.GL_RGBA, bgl.GL_BGRA}:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 4)
    elif format in {bgl.GL_RGB, bgl.GL_BGR}:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 1)
    else:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 1)

    mode_bak = bgl.Buffer(bgl.GL_INT, 1)
    bgl.glGetIntegerv(bgl.GL_READ_BUFFER, mode_bak)
    bgl.glReadBuffer(mode)

    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, pbo_id)

    # read
    GL.glReadBuffer(GL.GL_FRONT)
    GL.glReadPixels(x, y, w, h, formats[format], types[type][1], ct.c_void_p())
    # GL.glFinish()

    addr = glMapBufferARB(GL_PIXEL_PACK_BUFFER_ARB, GL_READ_ONLY_ARB)
    if addr:
        p = ct.c_void_p(addr)
        arr = ct.cast(p, ct.POINTER(ct_array_type)).contents
        ct_arr = ct_array_type.from_buffer_copy(arr)
        glUnmapBufferARB(GL_PIXEL_PACK_BUFFER_ARB)
    else:
        ct_arr = None
    glBindBufferARB(GL_PIXEL_PACK_BUFFER_ARB, 0)

    # Restore
    bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, alignment_bak[0])
    bgl.glReadBuffer(mode_bak[0])

    return ct_arr


def screenshot_image_raw(x, y, w, h, pbo_id, name=''):
    """スクリーンショットを撮ってImageを生成する。
    :param x: Window.x
    :type x: int
    :param y: Window.y
    :type y: int
    :param w: Window.width
    :type w: int
    :param h: Window.height
    :type h: int
    :param name: Image名
    :type name: str
    :rtype: ct._CData
    """
    ct_array = screenshot_raw(x, y, w, h, pbo_id, type=bgl.GL_FLOAT)
    img = bpy.data.images.new(name, w, h)
    if ct_array:
        print("OK")
    else:
        print("Err")
    img.pixels = list(ct_array)
    return img


def screenshot(x, y, w, h, mode=bgl.GL_FRONT, format=bgl.GL_RGBA,
               type=bgl.GL_BYTE, buffer=None):
    """スクリーンショットを撮ってRGBAのバッファを返す
    :param x: Window.x
    :type x: int
    :param y: Window.y
    :type y: int
    :param w: Window.width
    :type w: int
    :param h: Window.height
    :type h: int
    :param mode: 読み込み先
    :type mode: int
    :param format: bgl.GL_RGBA, bgl.RGB, ...
    :type format: int
    :param type: バッファの型。bgl.GL_BYTE, bgl.GL_INT, ...
    :type type: int
    :param buffer: バッファ
    :type buffer: Buffer
    :return: スクリーンショット。float RGBA
    :rtype: bgl.Buffer
    """
    # Note: GL_BYTE, GL_SHORT, GL_INTの場合は取得する値が1/2になっている
    #       GL_UNSIGNED_BYTE: 153 -> GL_BYTE: 76
    if buffer is None:
        if type == bgl.GL_UNSIGNED_BYTE:
            t = bgl.GL_BYTE
        elif type == bgl.GL_UNSIGNED_SHORT:
            t = bgl.GL_SHORT
        elif type == bgl.GL_UNSIGNED_INT:
            t = bgl.GL_INT
        else:
            t = type
        if format in {bgl.GL_RGBA, bgl.GL_BGRA}:
            size = 4
        elif format in {bgl.GL_RGB, bgl.GL_BGR}:
            size = 3
        else:
            size = 1
        buffer = bgl.Buffer(t, w * h * size)

    alignment_bak = bgl.Buffer(bgl.GL_INT, 1)
    bgl.glGetIntegerv(bgl.GL_PACK_ALIGNMENT, alignment_bak)
    if format in {bgl.GL_RGBA, bgl.GL_BGRA}:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 4)
    elif format in {bgl.GL_RGB, bgl.GL_BGR}:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 1)
    else:
        bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, 1)

    mode_bak = bgl.Buffer(bgl.GL_INT, 1)
    bgl.glGetIntegerv(bgl.GL_READ_BUFFER, mode_bak)
    bgl.glReadBuffer(mode)

    bgl.glReadPixels(x, y, w, h, format, type, buffer)
    bgl.glFinish()

    bgl.glPixelStorei(bgl.GL_PACK_ALIGNMENT, alignment_bak[0])
    bgl.glReadBuffer(mode_bak[0])
    return buffer


def screenshot_image(x, y, w, h, name='', buffer=None):
    """スクリーンショットを撮ってImageを生成する。
    :param x: Window.x
    :type x: int
    :param y: Window.y
    :type y: int
    :param w: Window.width
    :type w: int
    :param h: Window.height
    :type h: int
    :param name: Image名
    :type name: str
    :param buffer: バッファ
    :type buffer: Buffer
    :return: Imageオブジェクト
    :rtype: bpy.types.Image
    """
    buffer = screenshot(x, y, w, h, type=bgl.GL_FLOAT, buffer=buffer)
    img = bpy.data.images.new(name, w, h)
    img.pixels = buffer
    return img


# blf #########################################################################
def blf_draw(fontid, txt):
    """GL_BLENDとGL_TEXTURE_2Dが描画前に有効になり、描画後に無効になる。
    source/blender/blenfont/internblf.c: 557
    void BLF_draw(int fontid, const char *str, size_t len)
    """
    blend = Buffer('bool', 0, bgl.GL_BLEND)
    tex2d = Buffer('bool', 0, bgl.GL_TEXTURE_2D)
    blf.draw(fontid, txt)
    glSwitch(bgl.GL_BLEND, blend)
    glSwitch(bgl.GL_TEXTURE_2D, tex2d)


"""
NOTE:
print('r', vagl.glgetvalue(bgl.GL_RED_BITS, 'int'))
print('g', vagl.glgetvalue(bgl.GL_GREEN_BITS, 'int'))
print('b', vagl.glgetvalue(bgl.GL_BLUE_BITS, 'int'))
print('a', vagl.glgetvalue(bgl.GL_ALPHA_BITS, 'int'))
print('depth', vagl.glgetvalue(bgl.GL_DEPTH_BITS, 'int'))
print('stencil', vagl.glgetvalue(bgl.GL_STENCIL_BITS, 'int'))
print('accum r', vagl.glgetvalue(bgl.GL_ACCUM_RED_BITS, 'int'))
print('accum g', vagl.glgetvalue(bgl.GL_ACCUM_GREEN_BITS, 'int'))
print('accum b', vagl.glgetvalue(bgl.GL_ACCUM_BLUE_BITS, 'int'))
print('accum a', vagl.glgetvalue(bgl.GL_ACCUM_ALPHA_BITS, 'int'))

# Stencil
GL_NEVER：すべて不合格
GL_LESS：( ref & mask ) < ( stencil & mask ) で合格
GL_LEQUAL：( ref & mask ) <= ( stencil & mask ) で合格
GL_GREATER：( ref & mask ) > ( stencil & mask ) で合格
GL_GEQUAL：( ref & mask ) >= ( stencil & mask ) で合格
GL_EQUAL：( ref & mask ) = ( stencil & mask ) で合格
GL_NOTEQUAL：( ref & mask ) != ( stencil & mask ) で合格
GL_ALWAYS：すべて合格

GL_KEEP
    現在の値を保持する。 
GL_ZERO
    ステンシルバッファの値として 0 を設定する。 
GL_REPLACE
    ステンシルバッファの値として ref を設定する。 ref は glStencilFunc を使って指定する。 
GL_INCR
    ステンシルバッファの現在値をインクリメントする。 上限は表現可能な符号なしの値の最大値に制限される。 
GL_DECR
    ステンシルバッファの現在値をデクリメントする。 下限は 0 に制限される。 
GL_INVERT
    ステンシルバッファの現在値をビット単位で反転させる。 ステンシルバッファの値は符号付き整数として扱われる。 インクリメントやデクリメントを行う際には、値は 0 と $2 sup n - 1$ の 間の値に制限される。 ここで $n$ は GL_STENCIL_BITS の問い合わせに対して返される 値である。 glStencilOp の残りのふたつの引き数は、 ステンシルテストの後に行われる深さバッファテストが 成功(zpass)したか失敗(zfail)したかによって変わる ステンシルバッファのアクションを指定する(glDepthFunc を参照)。 アクションは fail と同じ 6 種類のシンボル定数を 使って指定する。 深さバッファがない場合、または深さバッファが有効状態でない場合 には zfail は無視される。 これらの場合には、fail はステンシルテストに失敗した場合の アクションを指定し、zpass は成功した場合のアクションを 指定する。 
    
# 方形でクリッピング
#bgl.glEnable(bgl.GL_SCISSOR_TEST)  # defaultでON
bgl.glScissor(region.x, region.y,
              region.x + region.width, region.y + region.height))
#bgl.glDisable(bgl.GL_SCISSOR_TEST)

# Clip Plane
# 画面中心から右方向のみ描画
p = vam.PlaneVector(Vector((sx / 2, sy / 2, 0)), Vector((1, 0, 0)))
plane = bgl.Buffer(bgl.GL_DOUBLE, 4)
for i in range(4):
    plane[i] = p[i]
bgl.glEnable(bgl.GL_CLIP_PLANE5)  # GL_CLIP_PLANE0 ~ GL_CLIP_PLANE5
bgl.glClipPlane(bgl.GL_CLIP_PLANE5, plane)
bgl.glDisable(bgl.GL_CLIP_PLANE5)

#Pixcel毎の値を取得
#bgl.glReadBuffer(bgl.GL_FRONT)
buf = bgl.Buffer(bgl.GL_FLOAT, 400)  # GL_DOUBLE使用不可
bgl.glReadPixels(0, 0, 20, 20, bgl.GL_DEPTH_COMPONENT, bgl.GL_FLOAT, buf)
bgl.glReadPixels(0, 0, 10, 10, bgl.GL_RGBA, bgl.GL_FLOAT, buf)
print(set(buf))
"""
