from threading import Lock

import bpy
import bgl
# pylint: disable=C0414,W0611
from bgl import Buffer as Buffer
import gpu
from gpu_extras.batch import batch_for_shader

GL_LINES = 0
GL_LINE_STRIP = 1
GL_LINE_LOOP = 2
GL_TRIANGLES = 5
GL_TRIANGLE_FAN = 6
GL_QUADS = 4


def check_version(major, minor, _):
    """
    Check blender version
    """

    if bpy.app.version[0] == major and bpy.app.version[1] == minor:
        return 0
    if bpy.app.version[0] > major:
        return 1
    if bpy.app.version[1] > minor:
        return 1
    return -1


def primitive_mode_is_line(mode):
    return mode in [GL_LINES, GL_LINE_STRIP, GL_LINE_LOOP]


def is_shader_supported(shader_name):
    try:
        gpu.shader.from_builtin(shader_name)
        return True
    except ValueError:
        return False


class InternalData:
    # pylint: disable=W0201
    __inst = None
    __lock = Lock()

    def __init__(self):
        raise NotImplementedError("Not allowed to call constructor")

    @classmethod
    def __internal_new(cls):
        inst = super().__new__(cls)
        inst.color = [1.0, 1.0, 1.0, 1.0]
        inst.line_width = 1.0

        return inst

    @classmethod
    def get_instance(cls):
        if not cls.__inst:
            with cls.__lock:
                if not cls.__inst:
                    cls.__inst = cls.__internal_new()

        return cls.__inst

    def init(self):
        self.clear()

    def set_prim_mode(self, mode):
        self.prim_mode = mode

    def set_dims(self, dims):
        self.dims = dims

    def add_vert(self, v):
        self.verts.append(v)

    def add_tex_coord(self, uv):
        self.tex_coords.append(uv)

    def set_color(self, c):
        self.color = c

    def set_line_width(self, width):
        self.line_width = width

    def clear(self):
        self.prim_mode = None
        self.verts = []
        self.dims = None
        self.tex_coords = []

    def get_verts(self):
        return self.verts

    def get_dims(self):
        return self.dims

    def get_prim_mode(self):
        return self.prim_mode

    def get_color(self):
        return self.color

    def get_line_width(self):
        return self.line_width

    def get_tex_coords(self):
        return self.tex_coords


# pylint: disable=C0103
def glLineWidth(width):
    inst = InternalData.get_instance()
    inst.set_line_width(width)

    bgl.glLineWidth(width)


# pylint: disable=C0103
def glColor3f(r, g, b):
    inst = InternalData.get_instance()
    inst.set_color([r, g, b, 1.0])


# pylint: disable=C0103
def glColor4f(r, g, b, a):
    inst = InternalData.get_instance()
    inst.set_color([r, g, b, a])


# pylint: disable=C0103
def glRecti(x0, y0, x1, y1):
    glBegin(GL_QUADS)
    glVertex2f(x0, y0)
    glVertex2f(x0, y1)
    glVertex2f(x1, y1)
    glVertex2f(x1, y0)
    glEnd()


# pylint: disable=C0103
def glBegin(mode):
    inst = InternalData.get_instance()
    inst.init()
    inst.set_prim_mode(mode)


def _get_transparency_shader():
    vertex_shader = '''
    uniform mat4 modelViewMatrix;
    uniform mat4 projectionMatrix;

    in vec2 pos;
    in vec2 texCoord;
    out vec2 uvInterp;

    void main()
    {
        uvInterp = texCoord;
        gl_Position = projectionMatrix * modelViewMatrix
                          * vec4(pos.xy, 0.0, 1.0);
        gl_Position.z = 1.0;
    }
    '''

    fragment_shader = '''
    uniform sampler2D image;
    uniform vec4 color;
    uniform bool useTextureAlpha;

    in vec2 uvInterp;
    out vec4 fragColor;

    void main()
    {
        fragColor = texture(image, uvInterp);
        fragColor.a = useTextureAlpha ? fragColor.a : color.a;
    }
    '''

    return vertex_shader, fragment_shader


# pylint: disable=C0103
def glEnd():
    inst = InternalData.get_instance()

    color = inst.get_color()
    coords = inst.get_verts()
    tex_coords = inst.get_tex_coords()
    use_3d_polyline = False
    use_texture_alpha = False
    if inst.get_dims() == 2:
        if len(tex_coords) == 0:
            shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        else:
            vert_shader, frag_shader = _get_transparency_shader()
            shader = gpu.types.GPUShader(vert_shader, frag_shader)
            use_texture_alpha = True
    elif inst.get_dims() == 3:
        if len(tex_coords) == 0:
            if primitive_mode_is_line(inst.get_prim_mode()):
                if is_shader_supported('3D_POLYLINE_UNIFORM_COLOR'):
                    shader = gpu.shader.from_builtin(
                        '3D_POLYLINE_UNIFORM_COLOR')
                    use_3d_polyline = True
                else:
                    shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
            else:
                shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        else:
            raise NotImplementedError(
                "Texture is not supported in get_dims() == 3")
    else:
        raise NotImplementedError("get_dims() != 2")

    if len(tex_coords) == 0:
        data = {
            "pos": coords,
        }
    else:
        data = {
            "pos": coords,
            "texCoord": tex_coords
        }

    if inst.get_prim_mode() == GL_LINES:
        indices = []
        for i in range(0, len(coords), 2):
            indices.append([i, i + 1])
        batch = batch_for_shader(shader, 'LINES', data, indices=indices)

    elif inst.get_prim_mode() == GL_LINE_STRIP:
        batch = batch_for_shader(shader, 'LINE_STRIP', data)

    elif inst.get_prim_mode() == GL_LINE_LOOP:
        data["pos"].append(data["pos"][0])
        batch = batch_for_shader(shader, 'LINE_STRIP', data)

    elif inst.get_prim_mode() == GL_TRIANGLES:
        indices = []
        for i in range(0, len(coords), 3):
            indices.append([i, i + 1, i + 2])
        batch = batch_for_shader(shader, 'TRIS', data, indices=indices)

    elif inst.get_prim_mode() == GL_TRIANGLE_FAN:
        indices = []
        for i in range(1, len(coords) - 1):
            indices.append([0, i, i + 1])
        batch = batch_for_shader(shader, 'TRIS', data, indices=indices)

    elif inst.get_prim_mode() == GL_QUADS:
        indices = []
        for i in range(0, len(coords), 4):
            indices.extend([[i, i + 1, i + 2], [i + 2, i + 3, i]])
        batch = batch_for_shader(shader, 'TRIS', data, indices=indices)
    else:
        raise NotImplementedError(
            "get_prim_mode() != (GL_LINES|GL_TRIANGLES|GL_QUADS)")

    shader.bind()
    if len(tex_coords) != 0:
        shader.uniform_float("modelViewMatrix",
                             gpu.matrix.get_model_view_matrix())
        shader.uniform_float("projectionMatrix",
                             gpu.matrix.get_projection_matrix())
        shader.uniform_int("image", 0)
    if use_3d_polyline:
        shader.uniform_float("lineWidth", inst.get_line_width())
        if check_version(2, 92, 0) >= 1:
            region = bpy.context.region
            shader.uniform_float("viewportSize", (region.width, region.height))
    shader.uniform_float("color", color)
    if use_texture_alpha:
        shader.uniform_bool("useTextureAlpha", (use_texture_alpha, ))
    batch.draw(shader)

    inst.clear()


# pylint: disable=C0103
def glVertex2f(x, y):
    inst = InternalData.get_instance()
    inst.add_vert([x, y])
    inst.set_dims(2)


# pylint: disable=C0103
def glVertex3f(x, y, z):
    inst = InternalData.get_instance()
    inst.add_vert([x, y, z])
    inst.set_dims(3)


# pylint: disable=C0103
def glTexCoord2f(u, v):
    inst = InternalData.get_instance()
    inst.add_tex_coord([u, v])


GL_BLEND = bgl.GL_BLEND
GL_LINE_SMOOTH = bgl.GL_LINE_SMOOTH
GL_INT = bgl.GL_INT
GL_SCISSOR_BOX = bgl.GL_SCISSOR_BOX
GL_TEXTURE_2D = bgl.GL_TEXTURE_2D
GL_TEXTURE0 = bgl.GL_TEXTURE0
GL_DEPTH_TEST = bgl.GL_DEPTH_TEST

GL_TEXTURE_MIN_FILTER = 0
GL_TEXTURE_MAG_FILTER = 0
GL_LINEAR = 0
GL_TEXTURE_ENV = 0
GL_TEXTURE_ENV_MODE = 0
GL_MODULATE = 0


# pylint: disable=C0103
def glEnable(cap):
    bgl.glEnable(cap)


# pylint: disable=C0103
def glDisable(cap):
    bgl.glDisable(cap)


# pylint: disable=C0103
def glScissor(x, y, width, height):
    bgl.glScissor(x, y, width, height)


# pylint: disable=C0103
def glGetIntegerv(pname, params):
    bgl.glGetIntegerv(pname, params)


# pylint: disable=C0103
def glActiveTexture(texture):
    bgl.glActiveTexture(texture)


# pylint: disable=C0103
def glBindTexture(target, texture):
    bgl.glBindTexture(target, texture)


# pylint: disable=C0103,W0613
def glTexParameteri(target, pname, param):
    pass


# pylint: disable=C0103,W0613
def glTexEnvi(target, pname, param):
    pass
