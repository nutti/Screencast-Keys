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
              "Gaia Clary, Pablo Vazquez, chromoly, Nutti, Hawkpath",
    "version": (3, 1, 0),
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
    importlib.reload(utils)
    utils.bl_class_registry.BlClassRegistry.cleanup()
    importlib.reload(preferences)
    importlib.reload(ops)
    importlib.reload(ui)
else:
    import bpy
    from . import utils
    from . import preferences
    from . import ops
    from . import ui

import os

import bpy


addon_keymaps = []


@bpy.app.handlers.persistent
def load_pre_handler(scene):
    """ScreencastKeys_OT_Main operation will remain running status when new .blend file is loaded.
       It seems that events from timer is not issued after loading .blend file, but we could not
       find the essential cause.
       Instead, we solve this issue by using handler called at load_pre (i.e. before loading
       .blend file)."""

    if ops.ScreencastKeys_OT_Main.is_running():
        # Call invoke method also cleanup event handlers and draw handlers, so on.
        bpy.ops.wm.screencast_keys('INVOKE_REGION_WIN')


def register_updater(bl_info):
    config = utils.addon_updator.AddonUpdatorConfig()
    config.owner = "nutti"
    config.repository = "Screencast-Keys"
    config.current_addon_path = os.path.dirname(os.path.realpath(__file__))
    config.branches = ["master"]
    config.addon_directory = config.current_addon_path[:config.current_addon_path.rfind("/")]
    config.min_release_version = bl_info["version"]
    config.target_addon_path = "src/screencast_keys"
    updater = utils.addon_updator.AddonUpdatorManager.get_instance()
    updater.init(bl_info, config)


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


def register():
    register_updater(bl_info)
    utils.bl_class_registry.BlClassRegistry.register()
    register_shortcut_key()
    bpy.app.handlers.load_pre.append(load_pre_handler)

    # Apply preferences of the panel location.
    context = bpy.context
    prefs = context.preferences.addons[__package__].preferences
    preferences.SK_Preferences.panel_category_update_fn(prefs, context)
    preferences.SK_Preferences.panel_space_type_update_fn(prefs, context)


def unregister():
    bpy.app.handlers.load_pre.remove(load_pre_handler)
    unregister_shortcut_key()
    utils.bl_class_registry.BlClassRegistry.unregister()


if __name__ == "__main__":
    register()
