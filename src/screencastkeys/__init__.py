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
    'name': 'Screencast Keys',
    'author': 'Paulo Gomes, Bart Crouch, John E. Herrenyo, '
              'Gaia Clary, Pablo Vazquez, chromoly, Nutti',
    'version': (3, 0, 0),
    'blender': (2, 80, 0),
    'location': '3D View > Properties Panel > Screencast Keys',
    'warning': '',
    'description': 'Display keys pressed in Blender',
    'wiki_url': 'http://wiki.blender.org/index.php/Extensions:2.6/'
                'Py/Scripts/3D_interaction/Screencast_Key_Status_Tool',
    'tracker_url': 'https://github.com/nutti/Screencast-Keys',
    'category': 'System',
}


if "bpy" in locals():
    import importlib
    importlib.reload(utils)
    utils.bl_class_registry.BlClassRegistry.cleanup()
    importlib.reload(preferences)
    importlib.reload(ops)
else:
    import bpy
    from . import utils
    from . import preferences
    from . import ops

import os

import bpy


def register_updater(bl_info):
    config = utils.addon_updator.AddonUpdatorConfig()
    config.owner = "nutti"
    config.repository = "Screencast-Keys"
    config.current_addon_path = os.path.dirname(os.path.realpath(__file__))
    config.branches = ["master", "develop"]
    config.addon_directory = config.current_addon_path[:config.current_addon_path.rfind("/")]
    config.min_release_version = bl_info["version"]
    config.target_addon_path = "src/screencastkeys"
    updater = utils.addon_updator.AddonUpdatorManager.get_instance()
    updater.init(bl_info, config)


def register():
    register_updater(bl_info)
    utils.bl_class_registry.BlClassRegistry.register()

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new('wm.screencast_keys', 'C', 'PRESS',
                                  shift=True, alt=True)


def unregister():
    utils.bl_class_registry.BlClassRegistry.unregister()


if __name__ == '__main__':
    register()
