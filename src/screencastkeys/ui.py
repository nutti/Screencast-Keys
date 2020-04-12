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

from .ops import ScreencastKeys_OT_Main
from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat


@BlClassRegistry()
class ScreencastKeys_PT_Main(bpy.types.Panel):
    bl_idname = "WM_PT_screencast_keys"
    bl_label = "Screencast Keys"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Screencast Keys"

    def draw_header(self, context):
        layout = self.layout
        layout.prop(context.window_manager, "enable_screencast_keys", text="")

    def draw(self, context):
        layout = self.layout
        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences

        column = layout.column()

        column.prop(prefs, "color")
        column.prop(prefs, "color_shadow")
        column.prop(prefs, "font_size")
        column.prop(prefs, "display_time")

        column.separator()

        column.prop(prefs, "origin")
        row = column.row()
        row.prop(prefs, "offset")
        column.operator("wm.screencast_keys_set_origin", text="Set Origin")
        column.prop(prefs, "show_mouse_events")
        column.prop(prefs, "show_last_operator")

    @classmethod
    def register(cls):
        def get_func(self):
            return ScreencastKeys_OT_Main.running

        def set_func(self, value):
            pass

        def update_func(self, context):
            bpy.ops.wm.screencast_keys('INVOKE_REGION_WIN')

        bpy.types.WindowManager.enable_screencast_keys = \
            bpy.props.BoolProperty(
                name="Screencast Keys",
                get=get_func,
                set=set_func,
                update=update_func,
            )

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.enable_screencast_keys
