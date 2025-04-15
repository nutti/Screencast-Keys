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

# <pep8 compliant>

import os
import bpy
import gpu


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


class ShaderManager:
    shader_instances = {}

    SHADER_FILES = {
        'IMAGE_COLOR': {
            "vertex": "image_color_vert.glsl",
            "fragment": "image_color_frag.glsl",
        },
        'IMAGE_COLOR_SCISSOR': {
            "vertex": "image_color_vert.glsl",
            "fragment": "image_color_scissor_frag.glsl",
        },
        'UNIFORM_COLOR_SCISSOR': {
            "vertex": "uniform_color_scissor_vert.glsl",
            "fragment": "uniform_color_scissor_frag.glsl",
        },
        'POLYLINE_UNIFORM_COLOR_SCISSOR': {
            "vertex": "polyline_uniform_color_scissor_vert.glsl",
            "fragment": "polyline_uniform_color_scissor_frag.glsl",
            "geometry": "polyline_uniform_color_scissor_geom.glsl",
        },
    }

    @classmethod
    def register_shaders(cls):
        if hasattr(gpu, "platform") and \
                hasattr(gpu.platform, "backend_type_get") and \
                gpu.platform.backend_type_get() != 'OPENGL':
            return

        # From Blender 4.5, creating a shader with calling gpu.types.GPUShader
        # constructor is not supported. Use builtin shaders instead.
        if check_version(4, 5, 0) >= 0:
            return

        for shader_name, shader_files in cls.SHADER_FILES.items():
            vert_code = None
            frag_code = None
            geom_code = None
            for category, filename in shader_files.items():
                filepath = f"{os.path.dirname(__file__)}/shaders/{filename}"
                with open(filepath, "r", encoding="utf-8") as f:
                    code = f.read()

                if category == "vertex":
                    vert_code = code
                elif category == "fragment":
                    frag_code = code
                elif category == 'geometry':
                    geom_code = code
            if geom_code is not None:
                instance = gpu.types.GPUShader(
                    vert_code, frag_code, geocode=geom_code)
            else:
                instance = gpu.types.GPUShader(vert_code, frag_code)
            cls.shader_instances[shader_name] = instance

    @classmethod
    def unregister_shaders(cls):
        if hasattr(gpu, "platform") and \
                hasattr(gpu.platform, "backend_type_get") and \
                gpu.platform.backend_type_get() != 'OPENGL':
            return

        for instance in cls.shader_instances.values():
            del instance
        cls.shader_instances = {}

    @classmethod
    def get_shader(cls, shader_name):
        if hasattr(gpu, "platform") and \
                hasattr(gpu.platform, "backend_type_get") and \
                gpu.platform.backend_type_get() != 'OPENGL':
            return None

        return cls.shader_instances.get(shader_name)

    @classmethod
    def is_supported(cls, shader_name):
        shader = cls.get_shader(shader_name)

        return shader is not None
