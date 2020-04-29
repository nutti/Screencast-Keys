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

from .ui import SK_PT_ScreencastKeys
from .utils.addon_updator import AddonUpdatorManager
from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat


@BlClassRegistry()
class SK_OT_CheckAddonUpdate(bpy.types.Operator):
    bl_idname = "wm.sk_check_addon_update"
    bl_label = "Check Update"
    bl_description = "Check Add-on Update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        updater = AddonUpdatorManager.get_instance()
        updater.check_update_candidate()

        return {'FINISHED'}


@BlClassRegistry()
@compat.make_annotations
class SK_OT_UpdateAddon(bpy.types.Operator):
    bl_idname = "wm.sk_update_addon"
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
class SK_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    category = EnumProperty(
        name="Category",
        description="Preferences Category",
        items=[
            ('CONFIG', "Configuration", "Configuration about this add-on"),
            ('UPDATE', "Update", "Update this add-on"),
        ],
        default='CONFIG'
    )

    # for UI
    def panel_space_type_update_fn(self, context):
        has_panel = hasattr(bpy.types, SK_PT_ScreencastKeys.bl_idname)
        if has_panel:
            try:
                bpy.utils.unregister_class(SK_PT_ScreencastKeys)
            except:
                pass

        SK_PT_ScreencastKeys.bl_space_type = self.panel_space_type
        bpy.utils.register_class(SK_PT_ScreencastKeys)

    def panel_space_type_items_fn(self, _):
        space_types = compat.get_all_space_types()
        items = []
        for i, (identifier, space) in enumerate(space_types.items()):
            space_name = space.bl_rna.name
            space_name = space_name.replace(" Space", "")
            space_name = space_name.replace("Space ", "")
            items.append((identifier, space_name, space_name, i))
        return items

    panel_space_type = bpy.props.EnumProperty(
        name="Space",
        description="Space to show ScreencastKey panel",
        items=panel_space_type_items_fn,
        update=panel_space_type_update_fn,
    )

    def panel_category_update_fn(self, context):
        has_panel = hasattr(bpy.types, SK_PT_ScreencastKeys.bl_idname)
        if has_panel:
            try:
                bpy.utils.unregister_class(SK_PT_ScreencastKeys)
            except:
                pass
        SK_PT_ScreencastKeys.bl_category = self.panel_category
        bpy.utils.register_class(SK_PT_ScreencastKeys)

    panel_category = bpy.props.StringProperty(
        name="Category",
        description="Category to show ScreencastKey panel",
        default="Screencast Keys",
        update=panel_category_update_fn,
    )

    color = bpy.props.FloatVectorProperty(
        name="Color",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR_GAMMA',
        size=3
    )
    color_shadow = bpy.props.FloatVectorProperty(
        name="Shadow Color",
        default=(0.0, 0.0, 0.0, 0.0),
        min=0.0,
        max=1.0,
        subtype='COLOR_GAMMA',
        size=4
    )
    font_size = bpy.props.IntProperty(
        name="Font Size",
        default=compat.get_user_preferences(bpy.context).ui_styles[0].widget.points,
        min=6,
        max=48
    )
    origin = bpy.props.EnumProperty(
        name="Origin",
        items=[
            ('REGION', "Region", ""),
            ('AREA', "Area", ""),
            ('WINDOW', "Window", "")
        ],
        default='REGION',
    )
    offset = bpy.props.IntVectorProperty(
        name="Offset",
        default=(20, 80),
        size=2,
    )
    display_time = bpy.props.FloatProperty(
        name="Display Time",
        default=3.0,
        min=0.5,
        max=10.0,
        step=10,
        subtype='TIME'
    )
    show_mouse_events = bpy.props.BoolProperty(
        name="Show Mouse Events",
        default=True,
    )
    show_last_operator = bpy.props.BoolProperty(
        name="Show Last Operator",
        default=False,
    )

    get_event_aggressively = bpy.props.BoolProperty(
        name="Get Event Aggressively",
        description="""Get events which will be dropped by the other
                       modalhandlers. This may make blender unstable.""",
        default=False,
    )

    debug_mode = bpy.props.BoolProperty(
        name="Debug Mode",
        description="Debug mode (Output log messages for add-on's developers)",
        default=False
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
            col.prop(self, "color")
            col.prop(self, "color_shadow")
            col.prop(self, "font_size")

            col = split.column()
            col.prop(self, "display_time")

            col = split.column()
            col.prop(self, "origin")
            col.prop(self, "offset")
            col.prop(self, "show_mouse_events")
            col.prop(self, "show_last_operator")

            # Panel location is only available in >= 2.80
            if compat.check_version(2, 80, 0) >= 0:
                layout.separator()

                layout.label(text="Panel Location:")
                col = layout.column()
                col.prop(self, "panel_space_type")
                col.prop(self, "panel_category")

            layout.separator()

            layout.label(text="Experimental:")
            col = layout.column()
            col.prop(self, "get_event_aggressively")

            layout.separator()

            layout.label(text="Development:")
            col = layout.column()
            col.prop(self, "debug_mode")

        elif self.category == 'UPDATE':
            updater = AddonUpdatorManager.get_instance()

            layout.separator()

            if not updater.candidate_checked():
                col = layout.column()
                col.scale_y = 2
                row = col.row()
                row.operator(SK_OT_CheckAddonUpdate.bl_idname,
                             text="Check 'Screencast Keys' add-on update",
                             icon='FILE_REFRESH')
            else:
                row = layout.row(align=True)
                row.scale_y = 2
                col = row.column()
                col.operator(SK_OT_CheckAddonUpdate.bl_idname,
                             text="Check 'Screencast Keys' add-on update",
                             icon='FILE_REFRESH')
                col = row.column()
                if updater.latest_version() != "":
                    col.enabled = True
                    ops = col.operator(
                        SK_OT_UpdateAddon.bl_idname,
                        text="Update to the latest release version (version: {})"
                            .format(updater.latest_version()),
                        icon='TRIA_DOWN_BAR')
                    ops.branch_name = updater.latest_version()
                else:
                    col.enabled = False
                    col.operator(SK_OT_UpdateAddon.bl_idname,
                                 text="No updates are available.")

                layout.separator()
                layout.label(text="Manual Update:")
                row = layout.row(align=True)
                row.prop(self, "updater_branch_to_update", text="Target")
                ops = row.operator(
                    SK_OT_UpdateAddon.bl_idname, text="Update",
                    icon='TRIA_DOWN_BAR')
                ops.branch_name = self.updater_branch_to_update

                layout.separator()
                if updater.has_error():
                    box = layout.box()
                    box.label(text=updater.error(), icon='CANCEL')
                elif updater.has_info():
                    box = layout.box()
                    box.label(text=updater.info(), icon='ERROR')
