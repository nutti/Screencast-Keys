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

import sys
import bpy
import blf


def check_version(major, minor, _):
    """
    Check blender version
    """

    if bpy.app.version[0] == major and bpy.app.version[1] == minor:
        return 0
    if bpy.app.version[0] > major:
        return 1
    if bpy.app.version[0] < major:
        return -1
    if bpy.app.version[1] > minor:
        return 1
    return -1


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


def blf_size(font_id, font_size, dpi):
    try:
        blf.size(font_id, font_size)
    except TypeError:
        blf.size(font_id, font_size, dpi)
