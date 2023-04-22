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


bl_info = {
    "name": "Screencast Keys",
    "author": "Paulo Gomes, Bart Crouch, John E. Herrenyo, "
              "Gaia Clary, Pablo Vazquez, chromoly, Nutti, Hawkpath, "
              "CheeryLee, Kureii",
    "version": (3, 10, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar > Screencast Keys",
    "warning": "",
    "description": "Display keys pressed in Blender",
    "wiki_url": "https://github.com/nutti/Screencast-Keys",
    "doc_url": "https://github.com/nutti/Screencast-Keys",
    "tracker_url": "https://github.com/nutti/Screencast-Keys",
    "category": "System",
}


if "bpy" in locals():
    import importlib
    # pylint: disable=E0601
    importlib.reload(gpu_utils)
    importlib.reload(utils)
    importlib.reload(c_structure)
    utils.bl_class_registry.BlClassRegistry.cleanup()
    importlib.reload(preferences)
    importlib.reload(ops)
    importlib.reload(ui)
    importlib.reload(common)
else:
    import bpy
    from . import gpu_utils
    from . import utils
    from . import c_structure
    from . import preferences
    from . import ops
    from . import ui
    from . import common

# pylint: disable=C0413
import os


addon_keymaps = []
# pylint: disable=C0103
is_startup = True


@bpy.app.handlers.persistent
def load_post_handler(_):
    # pylint: disable=W0603
    global is_startup

    context = bpy.context
    user_prefs = context.preferences
    prefs = user_prefs.addons[__package__].preferences

    enable_on_startup = prefs.enable_on_startup and is_startup
    is_running = not is_startup and ops.SK_OT_ScreencastKeys.is_running()
    if enable_on_startup or is_running:
        bpy.ops.wm.sk_wait_blender_initialized_and_start_screencast_keys()

    is_startup = False


def register_updater(info):
    config = utils.addon_updater.AddonUpdaterConfig()
    config.owner = "nutti"
    config.repository = "Screencast-Keys"
    config.current_addon_path = os.path.dirname(os.path.realpath(__file__))
    config.branches = ["master", "develop"]
    ridx = config.current_addon_path.rfind(utils.addon_updater.get_separator())
    config.addon_directory = config.current_addon_path[:ridx]
    config.min_release_version = info["version"]
    config.default_target_addon_path = "screencast_keys"
    config.target_addon_path = {
        "master": "src{}screencast_keys".format(
            utils.addon_updater.get_separator()),
        "develop": "src{}screencast_keys".format(
            utils.addon_updater.get_separator()),
    }
    updater = utils.addon_updater.AddonUpdaterManager.get_instance()
    updater.init(config)


def register_shortcut_key():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type='VIEW_3D')
        kmi = km.keymap_items.new("wm.sk_screencast_keys", 'C', 'PRESS',
                                  shift=True, alt=True)
        addon_keymaps.append((km, kmi))


def unregister_shortcut_key():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


def call_silently(fn, *args):
    try:
        fn(*args)
    # pylint: disable=W0702
    except:     # noqa
        pass


def register_addon_enable_property():
    def get_func(_):
        return ops.SK_OT_ScreencastKeys.is_running()

    def set_func(_, __):
        pass

    def update_func(_, __):
        bpy.ops.wm.sk_screencast_keys('INVOKE_REGION_WIN')

    if not hasattr(bpy.types.WindowManager, "enable_screencast_keys"):
        bpy.types.WindowManager.enable_screencast_keys = \
            bpy.props.BoolProperty(
                name="Screencast Keys",
                get=get_func,
                set=set_func,
                update=update_func,
            )


def unregister_addon_enable_property():
    if hasattr(bpy.types.WindowManager, "enable_screencast_keys"):
        del bpy.types.WindowManager.enable_screencast_keys


def register():
    gpu_utils.shader.ShaderManager.register_shaders()
    register_updater(bl_info)
    # Register Screencast Key's enable property at here to use it in the
    # both SK_PT_ScreencastKeys Panel and SK_PT_ScreencastKeys_Overlay Panel.
    # TODO: This registration should be handled by BlClassRegistry to add
    #       the priority feature.
    register_addon_enable_property()
    # TODO: Register by BlClassRegistry
    bpy.utils.register_class(preferences.DisplayEventTextAliasProperties)
    bpy.utils.register_class(ui.SK_PT_ScreencastKeys)
    bpy.utils.register_class(ui.SK_PT_ScreencastKeys_Overlay)
    utils.bl_class_registry.BlClassRegistry.register()
    register_shortcut_key()
    bpy.app.handlers.load_post.append(load_post_handler)

    # Apply preferences of UI.
    context = bpy.context
    user_prefs = context.preferences
    prefs = user_prefs.addons[__package__].preferences
    # Only default panel location is available in < 2.80
    if utils.compatibility.check_version(2, 80, 0) < 0:
        prefs.panel_space_type = 'VIEW_3D'
        prefs.panel_category = "Screencast Key"
        prefs.show_ui_in_sidebar = True
        prefs.show_ui_in_overlay = False
    preferences.SK_Preferences.ui_in_sidebar_update_fn(prefs, context)
    preferences.SK_Preferences.ui_in_overlay_update_fn(prefs, context)

    for event in list(ops.EventType):
        item = prefs.display_event_text_aliases_props.add()
        item.event_id = event.name
        if event in ops.SK_OT_ScreencastKeys.MODIFIER_EVENT_TYPES:
            item.default_text = common.fix_modifier_display_text(
                ops.EventType.names[event.name]
            )
        else:
            item.default_text = ops.EventType.names[event.name]

    try:
        common.reload_custom_mouse_image(prefs, context)
    # pylint: disable=W0702
    except:     # noqa
        pass


def unregister():
    context = bpy.context
    user_prefs = context.preferences
    prefs = user_prefs.addons[__package__].preferences
    preferences.remove_custom_mouse_image(prefs, context)

    bpy.app.handlers.load_post.remove(load_post_handler)
    unregister_shortcut_key()
    # TODO: Unregister by BlClassRegistry
    utils.bl_class_registry.BlClassRegistry.unregister()
    call_silently(bpy.utils.unregister_class, ui.SK_PT_ScreencastKeys_Overlay)
    call_silently(bpy.utils.unregister_class, ui.SK_PT_ScreencastKeys)
    bpy.utils.unregister_class(preferences.DisplayEventTextAliasProperties)
    unregister_addon_enable_property()
    gpu_utils.shader.ShaderManager.unregister_shaders()


if __name__ == "__main__":
    register()
