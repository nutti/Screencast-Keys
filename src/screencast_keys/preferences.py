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

from .ops import show_mouse_hold_status
from .ui import SK_PT_ScreencastKeys, SK_PT_ScreencastKeys_Overlay
from .utils import compatibility as compat
from .utils.addon_updater import AddonUpdaterManager
from .utils.bl_class_registry import BlClassRegistry
from . import common
from . import c_structure as cstruct


@BlClassRegistry()
class SK_OT_CheckAddonUpdate(bpy.types.Operator):
    bl_idname = "wm.sk_check_addon_update"
    bl_label = "Check Update"
    bl_description = "Check Add-on Update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, _):
        updater = AddonUpdaterManager.get_instance()
        updater.check_update_candidate()

        return {'FINISHED'}


@BlClassRegistry()
class SK_OT_UpdateAddon(bpy.types.Operator):
    bl_idname = "wm.sk_update_addon"
    bl_label = "Update"
    bl_description = "Update Add-on"
    bl_options = {'REGISTER', 'UNDO'}

    branch_name: StringProperty(
        name="Branch Name",
        description="Branch name to update",
        default="",
    )

    def execute(self, _):
        updater = AddonUpdaterManager.get_instance()
        updater.update(self.branch_name)

        return {'FINISHED'}


@BlClassRegistry()
class SK_OT_SelectCustomMouseImage(bpy.types.Operator):
    bl_idname = "wm.sk_select_custom_mouse_image"
    bl_label = "Select Custom Mouse Image"
    bl_description = "Select custom mouse image"
    bl_options = {'REGISTER', 'UNDO'}

    target: bpy.props.EnumProperty(
        name="Target",
        description="Target for opening image file",
        items=[
            ('BASE', "Base", "Base image for custom mouse image"),
            ('OVERLAY_LEFT_MOUSE', "Overlay Left Mouse",
             "Overlay left mouse for custom mouse image"),
            ('OVERLAY_RIGHT_MOUSE', "Overlay Right Mouse",
             "Overlay right mouse for custom mouse image"),
            ('OVERLAY_MIDDLE_MOUSE', "Overlay Middle Mouse",
             "Overlay middle mouse for custom mouse image"),
        ],
        default='BASE',
    )

    filepath: bpy.props.StringProperty(
        subtype="FILE_PATH"
    )

    def invoke(self, context, _):
        wm = context.window_manager
        wm.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        if self.target == 'BASE':
            prefs.custom_mouse_image_base = self.filepath
        elif self.target == 'OVERLAY_LEFT_MOUSE':
            prefs.custom_mouse_image_overlay_left_mouse = self.filepath
        elif self.target == 'OVERLAY_RIGHT_MOUSE':
            prefs.custom_mouse_image_overlay_right_mouse = self.filepath
        elif self.target == 'OVERLAY_MIDDLE_MOUSE':
            prefs.custom_mouse_image_overlay_middle_mouse = self.filepath

        return {'FINISHED'}


# pylint: disable=W0613
def get_update_candidate_branches(self, _):
    updater = AddonUpdaterManager.get_instance()
    if not updater.candidate_checked():
        return []

    return [(name, name, "") for name in updater.get_candidate_branch_names()]


class DisplayEventTextAliasProperties(bpy.types.PropertyGroup):
    alias_text: bpy.props.StringProperty(name="Alias Text", default="")
    default_text: bpy.props.StringProperty(options={'HIDDEN'})
    event_id: bpy.props.StringProperty(options={'HIDDEN'})


# pylint: disable=W0613
def remove_custom_mouse_image(self, _):
    def remove_image(image_name):
        if image_name in bpy.data.images:
            image = bpy.data.images[image_name]
            bpy.data.images.remove(image)

    remove_image(common.CUSTOM_MOUSE_IMG_BASE_NAME)
    remove_image(common.CUSTOM_MOUSE_IMG_LMOUSE_NAME)
    remove_image(common.CUSTOM_MOUSE_IMG_RMOUSE_NAME)
    remove_image(common.CUSTOM_MOUSE_IMG_MMOUSE_NAME)


def update_custom_mouse_size(self, _):
    if "use_custom_mouse_image_size" not in self:
        return

    if not self["use_custom_mouse_image_size"]:
        return

    if common.CUSTOM_MOUSE_IMG_BASE_NAME in bpy.data.images:
        image = bpy.data.images[common.CUSTOM_MOUSE_IMG_BASE_NAME]
        self["custom_mouse_size"] = image.size


@BlClassRegistry()
class SK_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    category: EnumProperty(
        name="Category",
        description="Preferences Category",
        items=[
            ('CONFIG', "Configuration", "Configuration about this add-on"),
            ('DISPLAY_EVENT_TEXT_ALIAS', "Display Event Text Alias",
             "Event text aliases for display"),
            ('UPDATE', "Update", "Update this add-on"),
        ],
        default='CONFIG'
    )

    # for Config.
    color: bpy.props.FloatVectorProperty(
        name="Color",
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR_GAMMA',
        size=4,
    )

    shadow: bpy.props.BoolProperty(
        name="Shadow",
        default=False
    )

    shadow_color: bpy.props.FloatVectorProperty(
        name="Shadow Color",
        default=(0.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR',
        size=4,
    )

    background: bpy.props.BoolProperty(
        name="Background",
        default=False
    )

    background_mode: bpy.props.EnumProperty(
        name="Background Mode",
        items=[
            ('TEXT', "Text", ""),
            ('DRAW_AREA', "Draw Area", ""),
        ],
        default='DRAW_AREA',
    )

    background_color: bpy.props.FloatVectorProperty(
        name="Background Color",
        default=(0.0, 0.0, 0.0, 1.0),
        min=0.0,
        max=1.0,
        subtype='COLOR',
        size=4,
    )

    background_rounded_corner_radius: bpy.props.IntProperty(
        name="Background Rounded Corner Radius",
        description="Radius of a Rounded Radius for a Background",
        default=0,
        min=0,
        max=100,
    )

    font_size: bpy.props.IntProperty(
        name="Font Size",
        default=int(bpy.context.preferences.ui_styles[0].widget.points),
        min=6,
        max=1000
    )

    margin: bpy.props.IntProperty(
        name="Margin",
        description="Margin",
        default=0,
        min=0,
        max=1000
    )

    line_thickness: bpy.props.FloatProperty(
        name="Line Thickness",
        default=1,
        min=1,
        max=100
    )

    mouse_size: bpy.props.IntProperty(
        name="Mouse Size",
        default=int(bpy.context.preferences.ui_styles[0].widget.points * 3),
        min=18,
        max=1000,
    )

    origin: bpy.props.EnumProperty(
        name="Origin",
        items=[
            ('REGION', "Region", ""),
            ('AREA', "Area", ""),
            ('WINDOW', "Window", ""),
            ('CURSOR', "Cursor", ""),
        ],
        default='REGION',
    )

    offset: bpy.props.IntVectorProperty(
        name="Offset",
        default=(20, 80),
        size=2,
        subtype='XYZ',
    )

    align: bpy.props.EnumProperty(
        name="Align",
        items=[
            ('LEFT', "Left", ""),
            ('CENTER', "Center", ""),
            ('RIGHT', "Right", ""),
        ],
        default='LEFT'
    )

    display_time: bpy.props.FloatProperty(
        name="Display Time",
        default=3.0,
        min=0.5,
        max=10.0,
        step=10,
        subtype='TIME'
    )

    max_event_history: bpy.props.IntProperty(
        name="Max Event History",
        description="Maximum number of event history to display",
        default=5,
        min=1,
        step=1,
    )

    repeat_count: bpy.props.BoolProperty(
        name="Repeat Count",
        default=True,
    )

    show_mouse_events: bpy.props.BoolProperty(
        name="Show Mouse Events",
        default=True,
    )

    mouse_events_show_mode: bpy.props.EnumProperty(
        name="Mouse Events",
        items=[
            ('EVENT_HISTORY', "Event History", ""),
            ('HOLD_STATUS', "Hold Status", ""),
            ('EVENT_HISTORY_AND_HOLD_STATUS', "Event History + Hold Status",
             ""),
        ],
        default='HOLD_STATUS',
    )

    use_custom_mouse_image: bpy.props.BoolProperty(
        name="Use Custom Mouse Image",
        default=False,
        update=common.reload_custom_mouse_image,
    )

    custom_mouse_image_base: bpy.props.StringProperty(
        name="Custom Mouse Image (Base)",
        description="Custom mouse image which is always rendered",
        default="",
        update=common.reload_custom_mouse_image,
    )

    custom_mouse_image_overlay_left_mouse: bpy.props.StringProperty(
        name="Custom Mouse Image (Overlay - Left Mouse)",
        description="Custom mouse image which is rendered when the left "
                    "button is clicked",
        default="",
        update=common.reload_custom_mouse_image,
    )

    custom_mouse_image_overlay_right_mouse: bpy.props.StringProperty(
        name="Custom Mouse Image (Overlay - Right Mouse)",
        description="Custom mouse image which is rendered when the right "
                    "button is clicked",
        default="",
        update=common.reload_custom_mouse_image,
    )

    custom_mouse_image_overlay_middle_mouse: bpy.props.StringProperty(
        name="Custom Mouse Image (Overlay - Middle Mouse)",
        description="Custom mouse image which is rendered when the middle "
                    "button is clicked",
        default="",
        update=common.reload_custom_mouse_image,
    )

    use_custom_mouse_image_size: bpy.props.BoolProperty(
        name="Use Custom Mouse Image Size",
        description="Use custom mouse image size",
        default=False,
        update=update_custom_mouse_size,
    )

    custom_mouse_size: bpy.props.IntVectorProperty(
        name="Custom Mouse Image Size",
        description="Custom mouse image size",
        default=(
            int(bpy.context.preferences.ui_styles[0].widget.points * 3),
            int(bpy.context.preferences.ui_styles[0].widget.points * 3)
        ),
        min=18,
        max=1000,
        size=2,
        subtype='XYZ',
    )

    show_last_operator: bpy.props.BoolProperty(
        name="Show Last Operator",
        default=False,
    )

    last_operator_show_mode: bpy.props.EnumProperty(
        name="Last Operator",
        items=[
            ('LABEL', "Label", ""),
            ('IDNAME', "ID Name", ""),
            ('LABEL_AND_IDNAME', "Label + ID Name", ""),
        ],
        default='LABEL_AND_IDNAME',
    )

    get_event_aggressively: bpy.props.BoolProperty(
        name="Get Event Aggressively",
        description="(Experimental) Get events which will be dropped by the"
                    "other modalhandlers. This may make blender unstable",
        default=not cstruct.NOT_SUPPORTED,
    )

    auto_save: bpy.props.BoolProperty(
        name="Auto Save",
        description="(Experimental) Enable custom auto save while modal "
                    "operator is running. This may make blender unstable",
        default=False,
    )

    output_debug_log: bpy.props.BoolProperty(
        name="Output Debug Log",
        description="(Debug) Output log messages",
        default=False
    )

    display_draw_area: bpy.props.BoolProperty(
        name="Display Draw Area",
        description="(Debug) Display draw area",
        default=False
    )

    # for UI.
    def panel_space_type_items_fn(self, _):
        space_types = compat.get_all_space_types()
        items = []
        for i, (identifier, space) in enumerate(space_types.items()):
            space_name = space.bl_rna.name
            space_name = space_name.replace(" Space", "")
            space_name = space_name.replace("Space ", "")
            items.append((identifier, space_name, space_name, i))
        return items

    def ui_in_sidebar_update_fn(self, _):
        has_panel = hasattr(bpy.types, SK_PT_ScreencastKeys.bl_idname)
        if has_panel:
            try:
                bpy.utils.unregister_class(SK_PT_ScreencastKeys)
            # pylint: disable=W0702
            except:     # noqa
                pass

        if self.show_ui_in_sidebar:
            SK_PT_ScreencastKeys.bl_space_type = self.panel_space_type
            SK_PT_ScreencastKeys.bl_category = self.panel_category
            bpy.utils.register_class(SK_PT_ScreencastKeys)

    panel_space_type: bpy.props.EnumProperty(
        name="Space",
        description="Space to show ScreencastKey panel",
        items=panel_space_type_items_fn,
        update=ui_in_sidebar_update_fn,
    )

    panel_category: bpy.props.StringProperty(
        name="Category",
        description="Category to show ScreencastKey panel",
        default="Screencast Keys",
        update=ui_in_sidebar_update_fn,
    )

    enable_on_startup: bpy.props.BoolProperty(
        name="Enable On Startup",
        description="Automatically enable Screencast Keys "
                    "when blender is starting up",
        default=False
    )

    show_ui_in_sidebar: bpy.props.BoolProperty(
        name="Sidebar",
        description="Show UI in Sidebar",
        default=True,
        update=ui_in_sidebar_update_fn,
    )

    def ui_in_overlay_update_fn(self, _):
        has_panel = hasattr(bpy.types, SK_PT_ScreencastKeys_Overlay.bl_idname)
        if has_panel:
            try:
                bpy.utils.unregister_class(SK_PT_ScreencastKeys_Overlay)
            # pylint: disable=W0702
            except:     # noqa
                pass
        if self.show_ui_in_overlay:
            bpy.utils.register_class(SK_PT_ScreencastKeys_Overlay)

    show_ui_in_overlay: bpy.props.BoolProperty(
        name="Overlay",
        description="Show UI in Overlay",
        default=False,
        update=ui_in_overlay_update_fn,
    )

    # for display event text alias
    enable_display_event_text_aliases: bpy.props.BoolProperty(
        name="Enable Display Event Text Aliases",
        description="Enable display event text aliases",
        default=False,
        update=ui_in_overlay_update_fn,
    )

    display_event_text_aliases_props: bpy.props.CollectionProperty(
        type=DisplayEventTextAliasProperties
    )

    # for add-on updater
    updater_branch_to_update: EnumProperty(
        name="branch",
        description="Target branch to update add-on",
        items=get_update_candidate_branches
    )

    def draw(self, _):
        layout = self.layout

        layout.row().prop(self, "category", expand=True)

        if self.category == 'CONFIG':
            layout.separator()

            layout.prop(self, "enable_on_startup")

            column = layout.column()
            split = column.split()
            col = split.column()
            col.prop(self, "color")
            col.separator()
            col.prop(self, "shadow")
            if self.shadow:
                col.prop(self, "shadow_color", text="")
            col.separator()
            col.prop(self, "background")
            if self.background:
                sp = col.split(factor=0.5)
                sp.prop(self, "background_mode", text="")
                sp = sp.split(factor=1.0)
                sp.prop(self, "background_color", text="")
                col.prop(self, "background_rounded_corner_radius",
                         text="Corner Radius")
            col.separator()
            col.prop(self, "font_size")
            col.prop(self, "margin")
            col.prop(self, "line_thickness")

            col = split.column()
            col.prop(self, "origin")

            col.separator()
            col.prop(self, "align")
            col.separator()
            col.prop(self, "offset")
            col.separator()
            col.prop(self, "display_time")

            col = split.column()
            col.prop(self, "max_event_history")
            col.separator()
            col.prop(self, "repeat_count")
            col.separator()
            col.prop(self, "show_mouse_events")
            if self.show_mouse_events:
                col.prop(self, "mouse_events_show_mode")
            col.separator()
            col.prop(self, "show_last_operator")
            if self.show_last_operator:
                col.prop(self, "last_operator_show_mode")

            layout.prop(self, "use_custom_mouse_image")
            if show_mouse_hold_status(self):
                if self.use_custom_mouse_image:
                    row = layout.row()
                    r = row.row()
                    r.prop(self, "use_custom_mouse_image_size",
                           text="Use Image Size")
                    r = row.row()
                    r.prop(self, "custom_mouse_size", text="Size")
                    r.enabled = not self.use_custom_mouse_image_size

                    column = layout.column()
                    split = column.split()

                    col = split.column()
                    col.label(text="Base:")
                    r = col.row(align=True)
                    r.prop(self, "custom_mouse_image_base", text="")
                    ops = r.operator(SK_OT_SelectCustomMouseImage.bl_idname,
                                     text="", icon='FILEBROWSER')
                    ops.target = 'BASE'
                    if common.CUSTOM_MOUSE_IMG_BASE_NAME in bpy.data.images:
                        image = bpy.data.images[
                            common.CUSTOM_MOUSE_IMG_BASE_NAME]
                        col.template_icon(image.preview.icon_id, scale=2.0)

                    col = split.column()
                    col.label(text="Overlay (Left)")
                    r = col.row(align=True)
                    r.prop(self, "custom_mouse_image_overlay_left_mouse",
                           text="")
                    ops = r.operator(SK_OT_SelectCustomMouseImage.bl_idname,
                                     text="", icon='FILEBROWSER')
                    ops.target = 'OVERLAY_LEFT_MOUSE'
                    if common.CUSTOM_MOUSE_IMG_LMOUSE_NAME in bpy.data.images:
                        image = bpy.data.images[
                            common.CUSTOM_MOUSE_IMG_LMOUSE_NAME]
                        col.template_icon(image.preview.icon_id, scale=2.0)

                    col = split.column()
                    col.label(text="Overlay (Right)")
                    r = col.row(align=True)
                    r.prop(self, "custom_mouse_image_overlay_right_mouse",
                           text="")
                    ops = r.operator(SK_OT_SelectCustomMouseImage.bl_idname,
                                     text="", icon='FILEBROWSER')
                    ops.target = 'OVERLAY_RIGHT_MOUSE'
                    if common.CUSTOM_MOUSE_IMG_RMOUSE_NAME in bpy.data.images:
                        image = bpy.data.images[
                            common.CUSTOM_MOUSE_IMG_RMOUSE_NAME]
                        col.template_icon(image.preview.icon_id, scale=2.0)

                    col = split.column()
                    col.label(text="Overlay (Middle)")
                    r = col.row(align=True)
                    r.prop(self, "custom_mouse_image_overlay_middle_mouse",
                           text="")
                    ops = r.operator(SK_OT_SelectCustomMouseImage.bl_idname,
                                     text="", icon='FILEBROWSER')
                    ops.target = 'OVERLAY_MIDDLE_MOUSE'
                    if common.CUSTOM_MOUSE_IMG_MMOUSE_NAME in bpy.data.images:
                        image = bpy.data.images[
                            common.CUSTOM_MOUSE_IMG_MMOUSE_NAME]
                        col.template_icon(image.preview.icon_id, scale=2.0)
                else:
                    column = layout.split(factor=0.5)
                    row = column.row()
                    row.prop(self, "mouse_size")

            layout.separator()

            layout.label(text="UI:")
            col = layout.column()
            col.prop(self, "show_ui_in_sidebar")

            if self.show_ui_in_sidebar:
                col.label(text="Panel Location:")
                col.prop(self, "panel_space_type")
                col.prop(self, "panel_category")

            col.separator()

            col.prop(self, "show_ui_in_overlay")

            layout.separator()

            layout.label(text="Experimental:")
            col = layout.column()
            col.prop(self, "get_event_aggressively")
            col.prop(self, "auto_save")

            layout.separator()

            layout.label(text="Development:")
            col = layout.column()
            col.prop(self, "output_debug_log")
            col.prop(self, "display_draw_area")

        elif self.category == 'DISPLAY_EVENT_TEXT_ALIAS':
            layout.separator()

            layout.prop(self, "enable_display_event_text_aliases")

            layout.separator()

            if self.enable_display_event_text_aliases:
                sp = layout.split(factor=0.33)
                col = sp.column()
                col.label(text="Event ID")
                sp = sp.split(factor=0.5)
                col = sp.column()
                col.label(text="Default Text")
                sp = sp.split(factor=1.0)
                col = sp.column()
                col.label(text="Alias Text")

                layout.separator()

                for d in self.display_event_text_aliases_props:
                    sp = layout.split(factor=0.33)
                    col = sp.column()
                    col.label(text=d.event_id)
                    sp = sp.split(factor=0.5)
                    col = sp.column()
                    col.label(text=d.default_text)
                    sp = sp.split(factor=1.0)
                    col = sp.column()
                    col.prop(d, "alias_text", text="")

        elif self.category == 'UPDATE':
            updater = AddonUpdaterManager.get_instance()

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
                        text="Update to the latest release version "
                             "(version: {})".format(updater.latest_version()),
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
