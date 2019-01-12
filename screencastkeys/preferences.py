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


import bpy

from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat

@BlClassRegistry()
@compat.make_annotations
class ScreenCastKeysPreferences(bpy.types.AddonPreferences):
    bl_idname = "screencastkeys"

    color = bpy.props.FloatVectorProperty(
        name='Color',
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR_GAMMA',
        size=3
    )
    color_shadow = bpy.props.FloatVectorProperty(
        name='Shadow Color',
        default=(0.0, 0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        subtype='COLOR_GAMMA',
        size=4
    )
    font_size = bpy.props.IntProperty(
        name='Font Size',
        default=compat.get_user_preferences(bpy.context).ui_styles[0].widget.points,
        min=6,
        max=48
    )
    origin = bpy.props.EnumProperty(
        name='Origin',
        items=[('REGION', 'Region', "Region.type is 'WINDOW'"),
               ('AREA', 'Area', ''),
               ('WINDOW', 'Window', '')],
        default='REGION',
    )
    offset = bpy.props.IntVectorProperty(
        name='Offset',
        default=(20, 80),
        size=2,
    )
    display_time = bpy.props.FloatProperty(
        name='Display Time',
        default=3.0,
        min=0.5,
        max=10.0,
        step=10,
        subtype='TIME'
    )
    show_last_operator = bpy.props.BoolProperty(
        name='Show Last Operator',
        default=False,
    )

    def draw(self, context):
        layout = self.layout

        column = layout.column()
        split = column.split()
        col = split.column()
        col.prop(self, 'color')
        col.prop(self, 'color_shadow')
        col.prop(self, 'font_size')

        col = split.column()
        col.prop(self, 'display_time')

        col = split.column()
        col.prop(self, 'origin')
        col.prop(self, 'offset')
        col.prop(self, 'show_last_operator')

        self.layout.separator()
