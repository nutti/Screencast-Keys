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
from bpy.props import (
    StringProperty,
    EnumProperty,
)

from .utils.addon_updator import AddonUpdatorManager
from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat


@BlClassRegistry()
class ScreencastKeys_OT_CheckAddonUpdate(bpy.types.Operator):
    bl_idname = "uv.muv_check_addon_update"
    bl_label = "Check Update"
    bl_description = "Check Add-on Update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        updater = AddonUpdatorManager.get_instance()
        updater.check_update_candidate()

        return {'FINISHED'}


@BlClassRegistry()
@compat.make_annotations
class ScreencastKeys_OT_UpdateAddon(bpy.types.Operator):
    bl_idname = "uv.muv_update_addon"
    bl_label = "Update"
    bl_description = "Update Add-on"
    bl_options = {'REGISTER', 'UNDO'}

    branch_name = StringProperty(
        name="Branch Name",
        description="Branch name to update",
        default="",
    )

    def execute(self, context):
        updater = AddonUpdatorManager.get_instance()
        updater.update(self.branch_name)

        return {'FINISHED'}


def get_update_candidate_branches(_, __):
    updater = AddonUpdatorManager.get_instance()
    if not updater.candidate_checked():
        return []

    return [(name, name, "") for name in updater.get_candidate_branch_names()]


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

    # for UI
    category = EnumProperty(
        name="Category",
        description="Preferences Category",
        items=[
            ('CONFIG', "Configuration", "Configuration about this add-on"),
            ('UPDATE', "Update", "Update this add-on"),
        ],
        default='CONFIG'
    )

    # for add-on updater
    updater_branch_to_update = EnumProperty(
        name="branch",
        description="Target branch to update add-on",
        items=get_update_candidate_branches
    )

    def draw(self, context):
        layout = self.layout

        layout.row().prop(self, "category", expand=True)

        if self.category == 'CONFIG':
            layout.separator()

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

        elif self.category == 'UPDATE':
            updater = AddonUpdatorManager.get_instance()

            layout.separator()

            if not updater.candidate_checked():
                col = layout.column()
                col.scale_y = 2
                row = col.row()
                row.operator(ScreencastKeys_OT_CheckAddonUpdate.bl_idname,
                             text="Check 'Screencast-Keys' add-on update",
                             icon='FILE_REFRESH')
            else:
                row = layout.row(align=True)
                row.scale_y = 2
                col = row.column()
                col.operator(ScreencastKeys_OT_CheckAddonUpdate.bl_idname,
                             text="Check 'Screencast-Keys' add-on update",
                             icon='FILE_REFRESH')
                col = row.column()
                if updater.latest_version() != "":
                    col.enabled = True
                    ops = col.operator(
                        ScreencastKeys_OT_UpdateAddon.bl_idname,
                        text="Update to the latest release version (version: {})"
                            .format(updater.latest_version()),
                        icon='TRIA_DOWN_BAR')
                    ops.branch_name = updater.latest_version()
                else:
                    col.enabled = False
                    col.operator(ScreencastKeys_OT_UpdateAddon.bl_idname,
                                 text="No updates are available.")

                layout.separator()
                layout.label(text="Manual Update:")
                row = layout.row(align=True)
                row.prop(self, "updater_branch_to_update", text="Target")
                ops = row.operator(
                    ScreencastKeys_OT_UpdateAddon.bl_idname, text="Update",
                    icon='TRIA_DOWN_BAR')
                ops.branch_name = self.updater_branch_to_update

                layout.separator()
                if updater.has_error():
                    box = layout.box()
                    box.label(text=updater.error(), icon='CANCEL')
                elif updater.has_info():
                    box = layout.box()
                    box.label(text=updater.info(), icon='ERROR')
