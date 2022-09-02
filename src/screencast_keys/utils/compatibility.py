# <pep8-80 compliant>

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

__author__ = "Nutti <nutti.metro@gmail.com>"
__status__ = "production"
__version__ = "5.2"
__date__ = "17 Nov 2018"


import sys

import bpy
import bgl
import blf


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


def make_annotations(cls):
    if check_version(2, 80, 0) < 0:
        return cls

    # make annotation from attributes
    props = {k: v
             for k, v in cls.__dict__.items()
             if isinstance(v, getattr(bpy.props, '_PropertyDeferred', tuple))}
    if props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in props.items():
            annotations[k] = v
            delattr(cls, k)

    return cls


class ChangeRegionType:
    def __init__(self, *_, **kwargs):
        self.region_type = kwargs.get('region_type', False)

    def __call__(self, cls):
        if check_version(2, 80, 0) >= 0:
            return cls

        cls.bl_region_type = self.region_type

        return cls


def matmul(m1, m2):
    if check_version(2, 80, 0) < 0:
        return m1 * m2

    return m1 @ m2


def layout_split(layout, factor=0.0, align=False):
    if check_version(2, 80, 0) < 0:
        return layout.split(percentage=factor, align=align)

    return layout.split(factor=factor, align=align)


def get_user_preferences(context):
    if hasattr(context, "user_preferences"):
        return context.user_preferences

    if hasattr(context, "preferences"):
        return context.preferences

    return None


def get_object_select(obj):
    if check_version(2, 80, 0) < 0:
        return obj.select

    return obj.select_get()


def set_active_object(obj):
    if check_version(2, 80, 0) < 0:
        bpy.context.scene.objects.active = obj
    else:
        bpy.context.view_layer.objects.active = obj


def get_active_object(context):
    if check_version(2, 80, 0) < 0:
        return context.scene.active_object
    else:
        return context.active_object


def object_has_uv_layers(obj):
    if check_version(2, 80, 0) < 0:
        return hasattr(obj.data, "uv_textures")
    else:
        return hasattr(obj.data, "uv_layers")


def get_object_uv_layers(obj):
    if check_version(2, 80, 0) < 0:
        return obj.data.uv_textures
    else:
        return obj.data.uv_layers


def icon(icon_name):
    if icon_name == 'IMAGE':
        if check_version(2, 80, 0) < 0:
            return 'IMAGE_COL'

    return icon_name


def set_blf_font_color(font_id, r, g, b, a):
    if check_version(2, 80, 0) >= 0:
        blf.color(font_id, r, g, b, a)
    else:
        bgl.glColor4f(r, g, b, a)


def set_blf_blur(font_id, radius):
    if check_version(2, 80, 0) < 0:
        blf.blur(font_id, radius)


def get_all_space_types():
    def add_if_exist(cls_name, space_name, space_types):
        try:
            cls = getattr(sys.modules["bpy.types"], cls_name)
            space_types[space_name] = cls
        except AttributeError as _:
            pass

    space_types = {}
    add_if_exist("SpaceView3D", 'VIEW_3D', space_types)
    add_if_exist("SpaceClipEditor", 'CLIP_EDITOR', space_types)
    add_if_exist("SpaceConsole", 'CONSOLE', space_types)
    add_if_exist("SpaceDopeSheetEditor", 'DOPESHEET_EDITOR', space_types)
    add_if_exist("SpaceFileBrowser", 'FILE_BROWSER', space_types)
    add_if_exist("SpaceGraphEditor", 'GRAPH_EDITOR', space_types)
    add_if_exist("SpaceImageEditor", 'IMAGE_EDITOR', space_types)
    add_if_exist("SpaceInfo", 'INFO', space_types)
    add_if_exist("SpaceLogicEditor", 'LOGIC_EDITOR', space_types)
    add_if_exist("SpaceNLA", 'NLA_EDITOR', space_types)
    add_if_exist("SpaceNodeEditor", 'NODE_EDITOR', space_types)
    add_if_exist("SpaceOutliner", 'OUTLINER', space_types)
    add_if_exist("SpacePreferences", 'PREFERENCES', space_types)
    add_if_exist("SpaceUserPreferences", 'PREFERENCES', space_types)
    add_if_exist("SpaceProperties", 'PROPERTIES', space_types)
    add_if_exist("SpaceSequenceEditor", 'SEQUENCE_EDITOR', space_types)
    add_if_exist("SpaceSpreadsheet", 'SPREADSHEET', space_types)
    add_if_exist("SpaceTextEditor", 'TEXT_EDITOR', space_types)
    add_if_exist("SpaceTimeline", 'TIMELINE', space_types)

    return space_types
