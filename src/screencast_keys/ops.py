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


import os
import platform
import math
import collections
import enum
import time
from ctypes import (
    c_void_p,
    cast,
    POINTER,
)

import blf
import bpy
import bpy.props
import gpu

from . import common
from .common import (debug_print, fix_modifier_display_text,
                     output_debug_log, use_3d_polyline)
from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat
from . import c_structure as cstruct
from .gpu_utils import imm


event_type_enum_items = bpy.types.Event.bl_rna.properties["type"].enum_items
EventType = enum.IntEnum(
    "EventType",
    [(e.identifier, e.value) for e in event_type_enum_items]
)
EventType.names = {e.identifier: e.name for e in event_type_enum_items}


def draw_default_mouse(x, y, w, h, left_pressed, right_pressed, middle_pressed,
                       color, round_radius, fill=False, fill_color=None,
                       line_thickness=1):
    mouse_body = [x, y, w, h / 2]
    left_mouse_button = [x, y + h / 2, w / 3, h / 2]
    middle_mouse_button = [x + w / 3, y + h / 2, w / 3, h / 2]
    right_mouse_button = [x + 2 * w / 3, y + h / 2, w / 3, h / 2]

    # Mouse body.
    if fill:
        draw_rounded_box(mouse_body[0], mouse_body[1],
                         mouse_body[2], mouse_body[3],
                         round_radius,
                         fill=True, color=fill_color,
                         round_corner=[True, True, False, False],
                         line_thickness=line_thickness)
    draw_rounded_box(mouse_body[0], mouse_body[1],
                     mouse_body[2], mouse_body[3],
                     round_radius,
                     fill=False, color=color,
                     round_corner=[True, True, False, False],
                     line_thickness=line_thickness)

    # Left button.
    if fill:
        draw_rounded_box(
            left_mouse_button[0], left_mouse_button[1],
            left_mouse_button[2], left_mouse_button[3],
            round_radius / 2,
            fill=True, color=fill_color,
            round_corner=[False, False, False, True],
            line_thickness=line_thickness)
    draw_rounded_box(
        left_mouse_button[0], left_mouse_button[1],
        left_mouse_button[2], left_mouse_button[3],
        round_radius / 2,
        fill=False, color=color,
        round_corner=[False, False, False, True],
        line_thickness=line_thickness)
    if left_pressed:
        draw_rounded_box(
            left_mouse_button[0], left_mouse_button[1],
            left_mouse_button[2], left_mouse_button[3],
            round_radius / 2,
            fill=True, color=color,
            round_corner=[False, False, False, True],
            line_thickness=line_thickness)

    # Middle button.
    if fill:
        draw_rounded_box(
            middle_mouse_button[0], middle_mouse_button[1],
            middle_mouse_button[2], middle_mouse_button[3],
            round_radius / 2,
            fill=True, color=fill_color,
            round_corner=[False, False, False, False],
            line_thickness=line_thickness)
    draw_rounded_box(
        middle_mouse_button[0], middle_mouse_button[1],
        middle_mouse_button[2], middle_mouse_button[3],
        round_radius / 2,
        fill=False, color=color,
        round_corner=[False, False, False, False],
        line_thickness=line_thickness)
    if middle_pressed:
        draw_rounded_box(
            middle_mouse_button[0], middle_mouse_button[1],
            middle_mouse_button[2], middle_mouse_button[3],
            round_radius / 2,
            fill=True, color=color,
            round_corner=[False, False, False, False],
            line_thickness=line_thickness)

    # Right button.
    if fill:
        draw_rounded_box(
            right_mouse_button[0], right_mouse_button[1],
            right_mouse_button[2], right_mouse_button[3],
            round_radius / 2,
            fill=True, color=fill_color,
            round_corner=[False, False, True, False],
            line_thickness=line_thickness)
    draw_rounded_box(
        right_mouse_button[0], right_mouse_button[1],
        right_mouse_button[2], right_mouse_button[3],
        round_radius / 2,
        fill=False, color=color,
        round_corner=[False, False, True, False],
        line_thickness=line_thickness)
    if right_pressed:
        draw_rounded_box(
            right_mouse_button[0], right_mouse_button[1],
            right_mouse_button[2], right_mouse_button[3],
            round_radius / 2,
            fill=True, color=color,
            round_corner=[False, False, True, False],
            line_thickness=line_thickness)


def draw_custom_mouse(x, y, w, h, left_pressed, right_pressed, middle_pressed,
                      image_name_base, image_name_overlay_lmouse,
                      image_name_overlay_rmouse,
                      image_name_overlay_mmouse):
    def draw_image(img, positions, tex_coords):
        gpu_img = gpu.texture.from_image(img)
        original_state = gpu.state.blend_get()
        gpu.state.blend_set('ALPHA')

        imm.immSetTexture(gpu_img)
        imm.immBegin(imm.GL_QUADS)
        imm.immColor4f(1.0, 1.0, 1.0, 1.0)
        for (v1, v2), (u, v) in zip(positions, tex_coords):
            imm.immTexCoord2f(u, v)
            imm.immVertex2f(v1, v2)
        imm.immEnd()
        imm.immSetTexture(None)

        gpu.state.blend_set(original_state)

    positions = [
        [x, y],
        [x, y + h],
        [x + w, y + h],
        [x + w, y],
    ]
    tex_coords = [
        [0.0, 0.0],
        [0.0, 1.0],
        [1.0, 1.0],
        [1.0, 0.0],
    ]

    common.ensure_custom_mouse_images()

    if image_name_base in bpy.data.images:
        draw_image(bpy.data.images[image_name_base], positions, tex_coords)
    if left_pressed and (image_name_overlay_lmouse in bpy.data.images):
        draw_image(bpy.data.images[image_name_overlay_lmouse], positions,
                   tex_coords)
    if right_pressed and (image_name_overlay_rmouse in bpy.data.images):
        draw_image(bpy.data.images[image_name_overlay_rmouse], positions,
                   tex_coords)
    if middle_pressed and (image_name_overlay_mmouse in bpy.data.images):
        draw_image(bpy.data.images[image_name_overlay_mmouse], positions,
                   tex_coords)


def draw_rounded_box(x, y, w, h, round_radius, fill=False,
                     color=None, round_corner=None, line_thickness=1):
    """round_corner: [Right Bottom, Left Bottom, Right Top, Left Top]"""

    if color is None:
        color = [1.0, 1.0, 1.0, 1.0]
    if round_corner is None:
        round_corner = [True, True, True, True]

    def circle_verts_num(r):
        """Get number of verticies for circle optimized for drawing."""

        num_verts = 32
        threshold = 2.0  # pixcel
        while True:
            if r * 2 * math.pi / num_verts > threshold:
                return num_verts
            num_verts -= 4
            if num_verts < 1:
                return 1

    num_verts = circle_verts_num(round_radius)
    n = int(num_verts / 4) + 1
    dangle = math.pi * 2 / num_verts

    radius = [round_radius if rc else 0 for rc in round_corner]

    x_origin = [
        x + radius[0],
        x + w - radius[1],
        x + w - radius[2],
        x + radius[3],
    ]
    y_origin = [
        y + radius[0],
        y + radius[1],
        y + h - radius[2],
        y + h - radius[3],
    ]
    angle_start = [
        math.pi * 1.0,
        math.pi * 1.5,
        math.pi * 0.0,
        math.pi * 0.5,
    ]

    imm.immColor4f(*color)
    imm.immLineWidth(line_thickness)

    if fill:
        imm.immBegin(imm.GL_TRIANGLE_FAN)
    else:
        imm.immBegin(imm.GL_LINE_LOOP)
    for x0, y0, angle, r in zip(x_origin, y_origin, angle_start, radius):
        for _ in range(n):
            x = x0 + r * math.cos(angle)
            y = y0 + r * math.sin(angle)
            if not fill and use_3d_polyline(line_thickness):
                imm.immVertex3f(x, y, 0)
            else:
                imm.immVertex2f(x, y)
            angle += dangle
    imm.immEnd()

    imm.immLineWidth(1.0)
    imm.immColor4f(1.0, 1.0, 1.0, 1.0)


def draw_rect(x1, y1, x2, y2, color):
    imm.immColor4f(*color)

    imm.immBegin(imm.GL_QUADS)
    imm.immVertex2f(x1, y1)
    imm.immVertex2f(x1, y2)
    imm.immVertex2f(x2, y2)
    imm.immVertex2f(x2, y1)
    imm.immEnd()

    imm.immColor4f(1.0, 1.0, 1.0, 1.0)


def draw_text_background(text, font_id, x, y, background_color,
                         margin=0, round_radius=0):
    width = blf.dimensions(font_id, text)[0]
    height = blf.dimensions(font_id, "Hy|")[1]
    correction = height * 0.2

    if round_radius == 0:
        draw_rect(x - margin, y - correction - margin,
                  x + width + margin, y + height - correction + margin,
                  background_color)
    else:
        draw_rounded_box(x - margin, y - correction - margin,
                         width + margin * 2, height + margin * 2,
                         round_radius, True, background_color)


def draw_text(text, font_id, color, shadow=False, shadow_color=None):
    blf.enable(font_id, blf.SHADOW)

    # Draw shadow.
    if shadow:
        blf.shadow_offset(font_id, 3, -3)
        blf.shadow(font_id, 5, *shadow_color)

    # Draw text.
    blf.color(font_id, *color)
    blf.draw(font_id, text)

    blf.disable(font_id, blf.SHADOW)


def draw_line(p1, p2, color, shadow=False, shadow_color=None,
              line_thickness=1):
    # Draw shadow.
    if shadow:
        imm.immLineWidth(line_thickness + 3.0)
        imm.immColor4f(*shadow_color)
        imm.immBegin(imm.GL_LINES)
        if use_3d_polyline(line_thickness):
            imm.immVertex3f(p1[0], p1[1], 0.0)
            imm.immVertex3f(p2[0], p2[1], 0.0)
        else:
            imm.immVertex2f(*p1)
            imm.immVertex2f(*p2)
        imm.immEnd()

    # Draw line.
    imm.immLineWidth(line_thickness + 2.0 if shadow else line_thickness)
    imm.immColor4f(*color)

    imm.immBegin(imm.GL_LINES)
    if use_3d_polyline(line_thickness):
        imm.immVertex3f(p1[0], p1[1], 0.0)
        imm.immVertex3f(p2[0], p2[1], 0.0)
    else:
        imm.immVertex2f(*p1)
        imm.immVertex2f(*p2)
    imm.immEnd()

    imm.immLineWidth(1.0)
    imm.immColor4f(1.0, 1.0, 1.0, 1.0)


def intersect_aabb(min1, max1, min2, max2):
    """Check intersection using AABB method."""

    for mi1, ma1, mi2, ma2 in zip(min1, max1, min2, max2):
        if (ma1 < mi2) or (ma2 < mi1):
            return False

    return True


def get_window_region_rect(area):
    """Return 'WINDOW' region rectangle."""

    rect = [99999, 99999, 0, 0]
    for region in area.regions:
        if region.type == 'WINDOW':
            rect[0] = min(rect[0], region.x)
            rect[1] = min(rect[1], region.y)
            rect[2] = max(region.x + region.width - 1, rect[2])
            rect[3] = max(region.y + region.height - 1, rect[3])

    return rect


def get_region_rect_on_v3d(context, area=None, region=None):
    """On VIEW_3D, we need to handle region overlap.
       This function takes into accout this, and return rectangle.
    """

    if not area:
        area = context.area
    if not region:
        region = context.region

    # We don't need to handle non-'WINDOW' region which is not effected by
    # region overlap. So we can return region rectangle as it is.
    if region.type != 'WINDOW':
        return [region.x, region.y,
                region.x + region.width, region.y + region.height]

    # From here, we handle 'WINDOW' region with considering region overlap.
    window = region
    tools = ui = None
    for ar in area.regions:
        # We need to dicard regions whose width is 1.
        if ar.width > 1:
            if ar.type == 'WINDOW':
                if ar == window:
                    window = ar
            elif ar.type == 'TOOLS':
                tools = ar
            elif ar.type == 'UI':
                ui = ar

    xmin, _, xmax, _ = get_window_region_rect(area)
    sys_pref = context.preferences.system
    if sys_pref.use_region_overlap:
        left_width = right_width = 0

        if tools and ui:
            r1, r2 = sorted([tools, ui], key=lambda ar: ar.x)
            if r1.x == area.x:
                # 'TOOLS' and 'UI' are located on left side.
                if r2.x == r1.x + r1.width:
                    left_width = r1.width + r2.width
                # 'TOOLS' and 'UI' are located on each side.
                else:
                    left_width = r1.width
                    right_width = r2.width
            # 'TOOLS' and 'UI' are located on right side.
            else:
                right_width = r1.width + r2.width

        elif tools:
            # 'TOOLS' is located on left side.
            if tools.x == area.x:
                left_width = tools.width
            # 'TOOLS' is located on right side.
            else:
                right_width = tools.width

        elif ui:
            # 'UI' is located on left side.
            if ui.x == area.x:
                left_width = ui.width
            # 'TOOLS' is located on right side.
            else:
                right_width = ui.width

        # Clip 'UI' and 'TOOLS' region from 'WINDOW' region, which enables us
        # to show only 'WINDOW' region.
        xmin = max(xmin, area.x + left_width)
        xmax = min(xmax, area.x + area.width - right_width - 1)

    ymin = window.y
    ymax = window.y + window.height - 1

    return xmin, ymin, xmax, ymax


def get_display_event_text(event_id):
    user_prefs = bpy.context.preferences
    prefs = user_prefs.addons[__package__].preferences

    if not prefs.enable_display_event_text_aliases:
        if EventType[event_id] in SK_OT_ScreencastKeys.MODIFIER_EVENT_TYPES:
            return fix_modifier_display_text(EventType.names[event_id])
        else:
            return EventType.names[event_id]

    for prop in prefs.display_event_text_aliases_props:
        if prop.event_id == event_id:
            if prop.alias_text == "":
                return prop.default_text
            else:
                return prop.alias_text

    return "UNKNOWN"


def show_mouse_hold_status(prefs):
    if not prefs.show_mouse_events:
        return False
    return prefs.mouse_events_show_mode in ['HOLD_STATUS',
                                            'EVENT_HISTORY_AND_HOLD_STATUS']


def show_mouse_event_history(prefs):
    if not prefs.show_mouse_events:
        return False
    return prefs.mouse_events_show_mode in ['EVENT_HISTORY',
                                            'EVENT_HISTORY_AND_HOLD_STATUS']


def show_text_background(prefs):
    if not prefs.background:
        return False
    return prefs.background_mode == 'TEXT'


def show_draw_area_background(prefs):
    if not prefs.background:
        return False
    return prefs.background_mode == 'DRAW_AREA'


@BlClassRegistry()
class SK_OT_ScreencastKeys(bpy.types.Operator):
    # pylint: disable=R0904
    bl_idname = "wm.sk_screencast_keys"
    bl_label = "Screencast Keys"
    bl_description = "Display keys pressed"
    bl_options = {'REGISTER'}

    # Last save time by auto save.
    last_auto_saved_time = 0
    # Flag for exclusive execution of auto save.
    auto_saving = False

    # Hold modifier keys.
    hold_modifier_keys = []
    # Hold mouse buttons.
    hold_mouse_buttons = {
        'LEFTMOUSE': False,
        'RIGHTMOUSE': False,
        'MIDDLEMOUSE': False,
    }
    # Event history.
    # Format: [time, event_type, modifiers, repeat_count]
    event_history = []
    # Operator history.
    # Format: [time, bl_label, idname_py, addr]
    operator_history = []

    MODIFIER_EVENT_TYPES = [
        EventType.LEFT_SHIFT,
        EventType.RIGHT_SHIFT,
        EventType.LEFT_CTRL,
        EventType.RIGHT_CTRL,
        EventType.LEFT_ALT,
        EventType.RIGHT_ALT,
        EventType.OSKEY
    ]

    MOUSE_EVENT_TYPES = {
        EventType.LEFTMOUSE,
        EventType.MIDDLEMOUSE,
        EventType.RIGHTMOUSE,
        EventType.BUTTON4MOUSE,
        EventType.BUTTON5MOUSE,
        EventType.BUTTON6MOUSE,
        EventType.BUTTON7MOUSE,
        EventType.TRACKPADPAN,
        EventType.TRACKPADZOOM,
        EventType.MOUSEROTATE,
        EventType.WHEELUPMOUSE,
        EventType.WHEELDOWNMOUSE,
        EventType.WHEELINMOUSE,
        EventType.WHEELOUTMOUSE,
    }

    SPACE_TYPES = compat.get_all_space_types()

    # Height ratio for separator (against text height).
    HEIGHT_RATIO_FOR_SEPARATOR = 0.6

    # Height ratio for hold mouse status (against width).
    HEIGHT_RATIO_FOR_MOUSE_HOLD_STATUS = 1.3

    # Margin ratio for hold modifier keys box (against text height).
    MARGIN_RATIO_FOR_MODIFIER_KEYS_BOX = 0.2

    # Width ratio for separator between hold mouse status and
    # hold modifier keys (against mouse width).
    WIDTH_RATIO_FOR_SEPARATOR = 0.4

    # Draw area margin.
    DRAW_AREA_MARGIN_LEFT = 15
    DRAW_AREA_MARGIN_RIGHT = 15
    DRAW_AREA_MARGIN_TOP = 15
    DRAW_AREA_MARGIN_BOTTOM = 15

    # Interval for 'TIMER' event (redraw).
    TIMER_STEP = 0.1

    # Maximum interval for ignoring same event.
    INTERVAL_FOR_IGNORE_EVENT = 0.05

    # Previous redraw time.
    prev_time = 0.0

    # Timer handlers.
    # Format: {Window.as_pointer(): Timer}
    timers = {}

    # Draw handlers.
    # Format: {(Space, Region.type): handle}
    handlers = {}

    # Regions which are drawing in previous redraw.
    # Format: {Region.as_pointer()}
    draw_regions_prev = set()

    # Draw target.
    origin = {
        "window": "",       # Window.as_pointer()
        "area": "",         # Area.as_pointer()
        "space": "",        # Space.as_pointer()
        "region_type": "",  # Region.type
    }

    # Area - Space mapping.
    # Format: {Area.as_pointer(), [Space.as_pointer(), ...]}
    # TODO: Clear when this model is finished.
    area_spaces = collections.defaultdict(set)

    # Check if this operator is running.
    # TODO: We can check it with the valid of event handler.
    running = False

    # Should screencast be restarted
    restart: bpy.props.BoolProperty(
        default=False
    )

    # Current mouse coordinate.
    current_mouse_co = [0.0, 0.0]

    @classmethod
    def is_running(cls):
        return cls.running

    @classmethod
    def is_modifier_event(cls, event):
        """Return True if event came from modifier key."""

        event_type = EventType[event.type]
        return event_type in cls.MODIFIER_EVENT_TYPES

    @classmethod
    def sorted_modifier_keys(cls, modifiers):
        """Sort and unique modifier keys."""

        def key_fn(event_type):
            if event_type in cls.MODIFIER_EVENT_TYPES:
                return cls.MODIFIER_EVENT_TYPES.index(event_type)
            else:
                return 100

        modifiers = sorted(modifiers, key=key_fn)
        names = []
        for mod in modifiers:
            name = get_display_event_text(mod.name)
            assert mod in cls.MODIFIER_EVENT_TYPES, \
                "{} must be modifier types".format(name)

            # Unique.
            if name not in names:
                names.append(name)

        return names

    @classmethod
    def removed_old_event_history(cls):
        """Return event history whose old events are removed."""

        user_prefs = bpy.context.preferences
        prefs = user_prefs.addons[__package__].preferences
        current_time = time.time()

        event_history = []
        for item in cls.event_history:
            event_time = item[0]
            t = current_time - event_time
            if t <= prefs.display_time:
                event_history.append(item)

        if len(event_history) >= prefs.max_event_history:
            event_history = event_history[-prefs.max_event_history:]

        return event_history

    @classmethod
    def removed_old_operator_history(cls):
        """Return operator history whose old operators are removed."""
        # TODO: Control number of history from Preferences.

        return cls.operator_history[-32:]

    @classmethod
    def get_alignment_offset(cls, context, width, margin=0):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        dw, _ = cls.draw_area_size(context)
        dw -= cls.DRAW_AREA_MARGIN_LEFT + cls.DRAW_AREA_MARGIN_RIGHT

        offset_x = cls.DRAW_AREA_MARGIN_LEFT
        offset_y = cls.DRAW_AREA_MARGIN_BOTTOM + margin
        if prefs.align == 'LEFT':
            offset_x += margin
        elif prefs.align == 'CENTER':
            offset_x += (dw - width) / 2.0 + margin
        elif prefs.align == 'RIGHT':
            offset_x += dw - width + margin

        return offset_x, offset_y

    @classmethod
    def get_text_offset_for_alignment(cls, context, font_id, text, margin=0):
        tw = blf.dimensions(font_id, text)[0]

        return cls.get_alignment_offset(context, tw, margin)

    @classmethod
    def get_origin(cls, context):
        """Get draw target.
           Retrun value: (Window, Area, Region, x, y)
        """

        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        def is_window_match(window):
            return window.as_pointer() == cls.origin["window"]

        def is_area_match(area):
            if area.as_pointer() == cls.origin["area"]:
                # Area is just same as user specified area.
                return True
            elif area.spaces.active.as_pointer() == cls.origin["space"]:
                # Area is not same, but active space information is same.
                return True
            else:
                area_p = area.as_pointer()
                if area_p in cls.area_spaces:
                    spaces_p = {s.as_pointer() for s in area.spaces}
                    if cls.origin["space"] in spaces_p:
                        # Exists in inactive space information.
                        return True
            return False

        def is_region_match(region):
            return region.type == cls.origin["region_type"]

        window = None
        for window in context.window_manager.windows:
            if is_window_match(window):
                break
        else:
            return None, None, None, 0, 0

        # Calculate draw offset
        draw_area_width, draw_area_height = cls.draw_area_size(context)
        if prefs.align == 'LEFT':
            x, y = prefs.offset
            if prefs.origin == 'CURSOR':
                x += cls.current_mouse_co[0] - draw_area_width / 2
                y += cls.current_mouse_co[1] - draw_area_height
        elif prefs.align == 'CENTER':
            x, y = prefs.offset
            if prefs.origin == 'WINDOW':
                x += (window.width - draw_area_width) / 2
            elif prefs.origin == 'AREA':
                for area in window.screen.areas:
                    if is_area_match(area):
                        x += (area.width - draw_area_width) / 2
                        break
            elif prefs.origin == 'REGION':
                found = False
                for area in window.screen.areas:
                    if found:
                        break
                    if not is_area_match(area):
                        continue
                    for region in area.regions:
                        if not is_region_match(region):
                            continue
                        if area.type == 'VIEW_3D':
                            rect = get_region_rect_on_v3d(
                                context, area, region)
                            x += (rect[2] - rect[0] - draw_area_width) / 2
                        else:
                            x += (region.width - draw_area_width) / 2
                        found = True
                        break
            elif prefs.origin == 'CURSOR':
                x += cls.current_mouse_co[0] - draw_area_width / 2
                y += cls.current_mouse_co[1] - draw_area_height
        elif prefs.align == 'RIGHT':
            x, y = prefs.offset
            if prefs.origin == 'WINDOW':
                x += window.width - draw_area_width
            elif prefs.origin == 'AREA':
                for area in window.screen.areas:
                    if is_area_match(area):
                        x += area.width - draw_area_width
                        break
            elif prefs.origin == 'REGION':
                found = False
                for area in window.screen.areas:
                    if found:
                        break
                    if not is_area_match(area):
                        continue
                    for region in area.regions:
                        if not is_region_match(region):
                            continue
                        if area.type == 'VIEW_3D':
                            rect = get_region_rect_on_v3d(
                                context, area, region)
                            x += rect[2] - rect[0] - draw_area_width
                        else:
                            x += region.width - draw_area_width
                        found = True
                        break
            elif prefs.origin == 'CURSOR':
                x += cls.current_mouse_co[0] - draw_area_width / 2
                y += cls.current_mouse_co[1] - draw_area_height

        if prefs.origin in ('WINDOW', 'CURSOR'):
            return window, None, None, x, y
        elif prefs.origin == 'AREA':
            for area in window.screen.areas:
                if is_area_match(area):
                    return window, area, None, x + area.x, y + area.y
        elif prefs.origin == 'REGION':
            for area in window.screen.areas:
                if not is_area_match(area):
                    continue
                for region in area.regions:
                    if is_region_match(region):
                        if area.type == 'VIEW_3D':
                            rect = get_region_rect_on_v3d(
                                context, area, region)
                            x += rect[0]
                            y += rect[1]
                        else:
                            x += region.x
                            y += region.y
                        return window, area, region, x, y

        return None, None, None, 0, 0

    @classmethod
    def text_area_width(cls, text, font_id):
        return blf.dimensions(font_id, text)[0]

    @classmethod
    def text_area_height(cls, font_id):
        return blf.dimensions(font_id, "Hy|")[1]

    @classmethod
    def _area_size_last_operator_layer(cls, context, font_id):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        operator_history = cls.removed_old_operator_history()
        sh = cls.text_area_height(font_id) + prefs.margin * 2

        if not operator_history:
            layer_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR
            return 0, layer_height

        current_time = time.time()
        time_, bl_label, idname_py, _ = operator_history[-1]
        if current_time - time_ > prefs.display_time:
            layer_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR
            return 0, layer_height

        operator_text = ""
        if prefs.last_operator_show_mode == 'LABEL':
            operator_text += bpy.app.translations.pgettext_iface(
                bl_label, "Operator")
        elif prefs.last_operator_show_mode == 'IDNAME':
            operator_text += "{}".format(idname_py)
        elif prefs.last_operator_show_mode == 'LABEL_AND_IDNAME':
            operator_text += bpy.app.translations.pgettext_iface(
                bl_label, "Operator")
            operator_text += " ('{}')".format(idname_py)

        layer_width = cls.text_area_width(operator_text, font_id) \
            + prefs.margin * 2
        layer_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR

        return layer_width, layer_height

    @classmethod
    def _area_size_mouse_and_modifier_keys_layer(cls, context, font_id):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        drawing = False  # TODO: Need to check if drawing is now on progress.
        modifier_keys_box_margin = cls.text_area_height(font_id) * \
            cls.MARGIN_RATIO_FOR_MODIFIER_KEYS_BOX

        # Setup hold modifier keys text
        modifier_keys_text = ""
        if cls.hold_modifier_keys or drawing:
            mod_keys = cls.sorted_modifier_keys(cls.hold_modifier_keys)
            if drawing:
                modifier_keys_text = ""
            else:
                modifier_keys_text = " + ".join(mod_keys)

        mouse_width = 0.0
        mouse_height = 0.0
        hold_modifier_keys_width = 0.0
        hold_modifier_keys_height = 0.0
        separator_width = 0.0
        if show_mouse_hold_status(prefs):
            if prefs.use_custom_mouse_image:
                mouse_width = prefs.custom_mouse_size[0]
                mouse_height = prefs.custom_mouse_size[1]
            else:
                mouse_width = prefs.mouse_size
                mouse_height = \
                    prefs.mouse_size * cls.HEIGHT_RATIO_FOR_MOUSE_HOLD_STATUS
        if cls.hold_modifier_keys:
            hold_modifier_keys_width = \
                cls.text_area_width(modifier_keys_text, font_id) \
                + modifier_keys_box_margin * 2
            hold_modifier_keys_height = \
                cls.text_area_height(font_id) + modifier_keys_box_margin * 2

        if prefs.align == 'CENTER':
            hold_modifier_keys_width = max(
                hold_modifier_keys_width, prefs.font_size * 8)
            separator_width = \
                mouse_width * cls.WIDTH_RATIO_FOR_SEPARATOR + prefs.margin
        if show_mouse_hold_status(prefs) and cls.hold_modifier_keys:
            separator_width = \
                mouse_width * cls.WIDTH_RATIO_FOR_SEPARATOR + prefs.margin

        layer_width = mouse_width + separator_width + \
            hold_modifier_keys_width + prefs.margin * 2
        layer_height = \
            max(mouse_height, hold_modifier_keys_height) + prefs.margin * 2

        return layer_width, layer_height

    @classmethod
    def _area_size_event_history_layer(cls, context, font_id):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        sh = cls.text_area_height(font_id) + prefs.margin * 2

        layer_width = 0.0
        layer_height = 0.0

        event_history = cls.removed_old_event_history()
        layer_height += cls.text_area_height(font_id) * \
            cls.HEIGHT_RATIO_FOR_SEPARATOR
        for _, event_type, modifiers, repeat_count in event_history[::-1]:
            text = get_display_event_text(event_type.name)
            if modifiers:
                mod_keys = cls.sorted_modifier_keys(modifiers)
                text = "{} + {}".format(" + ".join(mod_keys), text)
            if repeat_count > 1:
                text += " x{}".format(repeat_count)

            text_width = cls.text_area_width(text, font_id) + prefs.margin * 2
            layer_width = max(text_width, layer_width)
            layer_height += sh

        return layer_width, layer_height

    @classmethod
    def draw_area_size(cls, context):
        """Return draw area size.

        Draw format:

            Overview:
                ....
                Event history[-3]
                Event history[-2]
                Event history[-1]

                Mouse hold status  Hold modifier key list
                ----------------
                Operator history

            Event history format:
                With count: {key} x{count}
                With modifier key: {modifier key} + {key}

            Hold modifier key list format:
                 --------------     --------------
                |{modifier key}| + |{modifier key}|
                 --------------     --------------
        """

        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        font_size = prefs.font_size
        font_id = 0         # TODO: font_id should be constant.
        dpi = user_prefs.system.dpi
        blf.size(font_id, font_size, dpi)

        # Calculate width/height of draw area.
        draw_area_width = 0
        draw_area_height = 0

        # Last operator.
        if prefs.show_last_operator:
            w, h = cls._area_size_last_operator_layer(context, font_id)
            draw_area_width = max(w, draw_area_width)
            draw_area_height += h

        # Hold mouse status / Hold modifier keys.
        w, h = cls._area_size_mouse_and_modifier_keys_layer(context, font_id)
        draw_area_width = max(w, draw_area_width)
        draw_area_height += h

        # Event history.
        w, h = cls._area_size_event_history_layer(context, font_id)
        draw_area_width = max(w, draw_area_width)
        draw_area_height += h

        # Add margin.
        draw_area_width += \
            cls.DRAW_AREA_MARGIN_LEFT + cls.DRAW_AREA_MARGIN_RIGHT
        draw_area_height += \
            cls.DRAW_AREA_MARGIN_TOP + cls.DRAW_AREA_MARGIN_BOTTOM

        return draw_area_width, draw_area_height

    @classmethod
    def draw_area_rect(cls, context):
        """Return draw area rectangle."""

        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        # Get draw target.
        window, area, region, x, y = cls.get_origin(context)
        if not window:
            return None

        # Calculate width/height of draw area.
        draw_area_width, draw_area_height = cls.draw_area_size(context)

        if prefs.origin in ('WINDOW', 'CURSOR'):
            return (x,
                    y,
                    x + draw_area_width,
                    y + draw_area_height)
        elif prefs.origin == 'AREA':
            xmin = area.x
            ymin = area.y
            xmax = area.x + area.width - 1
            ymax = area.y + area.height - 1
            return (max(x, xmin),
                    max(y, ymin),
                    min(x + draw_area_width, xmax),
                    min(y + draw_area_height, ymax))
        elif prefs.origin == 'REGION':
            xmin = region.x
            ymin = region.y
            xmax = region.x + region.width - 1
            ymax = region.y + region.height - 1
            return (max(x, xmin),
                    max(y, ymin),
                    min(x + draw_area_width, xmax),
                    min(y + draw_area_height, ymax))

        assert False, "Invalid 'prefs.origin' (value={}).".format(prefs.origin)
        return None

    @classmethod
    def find_redraw_regions(cls, context):
        """Find regions to redraw."""

        rect = cls.draw_area_rect(context)
        if not rect:
            return []       # No draw target.

        draw_area_min_x, draw_area_min_y, draw_area_max_x, draw_area_max_y = \
            rect
        width = draw_area_max_x - draw_area_min_x
        height = draw_area_max_y - draw_area_min_y
        if width == height == 0:
            return []       # Zero size region.

        draw_area_min = [draw_area_min_x, draw_area_min_y]
        draw_area_max = [draw_area_max_x - 1, draw_area_max_y - 1]

        # Collect regions which overlaps with draw area.
        regions = []
        for area in context.screen.areas:
            for region in area.regions:
                if region.type == '':
                    continue    # Skip region with no type.
                region_min = [region.x, region.y]
                region_max = [region.x + region.width - 1,
                              region.y + region.height - 1]
                if intersect_aabb(region_min, region_max,
                                  draw_area_min, draw_area_max):
                    regions.append((area, region))

        return regions

    @classmethod
    def _draw_last_operator_layer(cls, context, font_id, x, y):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        operator_history = cls.removed_old_operator_history()
        sh = cls.text_area_height(font_id) + prefs.margin * 2

        if not operator_history:
            layer_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR
            return 0, layer_height, False

        current_time = time.time()
        time_, bl_label, idname_py, _ = operator_history[-1]
        if current_time - time_ > prefs.display_time:
            layer_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR
            return 0, layer_height, False

        blf.color(font_id, *prefs.color)

        # Setup operator text.
        operator_text = ""
        if prefs.last_operator_show_mode == 'LABEL':
            operator_text += bpy.app.translations.pgettext_iface(
                bl_label, "Operator")
        elif prefs.last_operator_show_mode == 'IDNAME':
            operator_text += "{}".format(idname_py)
        elif prefs.last_operator_show_mode == 'LABEL_AND_IDNAME':
            operator_text += bpy.app.translations.pgettext_iface(
                bl_label, "Operator")
            operator_text += " ('{}')".format(idname_py)

        # Setup draw target position
        operator_start_x = x
        operator_start_y = y
        operator_width = \
            cls.text_area_width(operator_text, font_id) + prefs.margin * 2
        operator_height = sh + sh * cls.HEIGHT_RATIO_FOR_SEPARATOR * 0.2
        separator_start_x = operator_start_x
        separator_start_y = operator_start_y + operator_height
        separator_line_width = blf.dimensions(font_id, "Left Mouse")[0]
        separator_width = separator_line_width + prefs.margin * 2
        separator_height = sh * cls.HEIGHT_RATIO_FOR_SEPARATOR * 0.8

        layer_width = max(operator_width, separator_width)
        layer_height = operator_height + separator_height

        operator_offset_x, operator_offset_y = \
            cls.get_alignment_offset(context, operator_width, prefs.margin)
        separator_offset_x, separator_offset_y = \
            cls.get_alignment_offset(context, separator_width, prefs.margin)
        operator_start_x += operator_offset_x
        operator_start_y += operator_offset_y
        separator_start_x += separator_offset_x
        separator_start_y += separator_offset_y

        # Draw operator history.
        blf.position(font_id, operator_start_x, operator_start_y, 0)
        if show_text_background(prefs):
            draw_text_background(operator_text, font_id,
                                 operator_start_x,
                                 operator_start_y,
                                 prefs.background_color, prefs.margin,
                                 prefs.background_rounded_corner_radius)
        draw_text(operator_text, font_id, prefs.color,
                  prefs.shadow, prefs.shadow_color)

        # Draw separator.
        draw_line(
            [separator_start_x, separator_start_y],
            [separator_start_x + separator_line_width, separator_start_y],
            prefs.color, prefs.shadow, prefs.shadow_color,
            prefs.line_thickness)

        return layer_width, layer_height, True

    @classmethod
    def _draw_mouse_and_modifier_keys_layer(cls, context, font_id, x, y):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        drawing = False  # TODO: Need to check if drawing is now on progress.
        blf.color(font_id, *prefs.color)
        modifier_keys_box_margin = cls.text_area_height(font_id) * \
            cls.MARGIN_RATIO_FOR_MODIFIER_KEYS_BOX
        region_redraw = False

        # Setup hold modifier keys text
        modifier_keys_text = ""
        if cls.hold_modifier_keys or drawing:
            mod_keys = cls.sorted_modifier_keys(cls.hold_modifier_keys)
            if drawing:
                modifier_keys_text = ""
            else:
                modifier_keys_text = " + ".join(mod_keys)

        # Setup draw target position
        mouse_start_x = 0.0
        mouse_start_y = 0.0
        mouse_icon_width = 0.0
        mouse_icon_height = 0.0
        mouse_width = 0.0
        mouse_height = 0.0
        hold_modifier_keys_start_x = 0.0
        hold_modifier_keys_start_y = 0.0
        hold_modifier_keys_width = 0.0
        hold_modifier_keys_height = 0.0
        separator_width = 0.0
        if show_mouse_hold_status(prefs):
            mouse_start_x = x
            mouse_start_y = y
            if prefs.use_custom_mouse_image:
                mouse_icon_width = prefs.custom_mouse_size[0]
                mouse_icon_height = prefs.custom_mouse_size[1]
            else:
                mouse_icon_width = prefs.mouse_size
                mouse_icon_height = \
                    prefs.mouse_size * cls.HEIGHT_RATIO_FOR_MOUSE_HOLD_STATUS
            mouse_width = mouse_icon_width
            mouse_height = mouse_icon_height
        if cls.hold_modifier_keys:
            hold_modifier_keys_start_x = x
            hold_modifier_keys_start_y = y
            hold_modifier_keys_text_width = \
                cls.text_area_width(modifier_keys_text, font_id) + \
                modifier_keys_box_margin * 2
            hold_modifier_keys_text_height = \
                cls.text_area_height(font_id) + modifier_keys_box_margin * 2
            hold_modifier_keys_width = hold_modifier_keys_text_width
            hold_modifier_keys_height = hold_modifier_keys_text_height

        if prefs.align == 'CENTER':
            hold_modifier_keys_width = max(hold_modifier_keys_width,
                                           prefs.font_size * 8)
            separator_width = \
                mouse_width * cls.WIDTH_RATIO_FOR_SEPARATOR + prefs.margin
        if show_mouse_hold_status(prefs) and cls.hold_modifier_keys:
            separator_width = \
                mouse_width * cls.WIDTH_RATIO_FOR_SEPARATOR + prefs.margin
            if prefs.align == 'RIGHT':
                mouse_start_x += hold_modifier_keys_width + separator_width
            elif prefs.align in ('LEFT', 'CENTER'):
                hold_modifier_keys_start_x += \
                    mouse_icon_width + separator_width

        layer_width = mouse_width + separator_width + \
            hold_modifier_keys_width + prefs.margin * 2
        layer_height = max(mouse_height, hold_modifier_keys_height) + \
            prefs.margin * 2

        offset_x, offset_y = cls.get_alignment_offset(
            context, layer_width, prefs.margin)
        mouse_start_x += offset_x
        mouse_start_y += offset_y
        hold_modifier_keys_start_x += offset_x
        hold_modifier_keys_start_y += offset_y

        if mouse_height > hold_modifier_keys_height:
            hold_modifier_keys_start_y += \
                (mouse_height - hold_modifier_keys_height) / 2
        else:
            mouse_start_y += (hold_modifier_keys_height - mouse_height) / 2

        # Draw hold mouse status.
        if show_mouse_hold_status(prefs):
            if prefs.use_custom_mouse_image:
                draw_custom_mouse(mouse_start_x, mouse_start_y,
                                  mouse_icon_width, mouse_icon_height,
                                  cls.hold_mouse_buttons['LEFTMOUSE'],
                                  cls.hold_mouse_buttons['RIGHTMOUSE'],
                                  cls.hold_mouse_buttons['MIDDLEMOUSE'],
                                  common.CUSTOM_MOUSE_IMG_BASE_NAME,
                                  common.CUSTOM_MOUSE_IMG_LMOUSE_NAME,
                                  common.CUSTOM_MOUSE_IMG_RMOUSE_NAME,
                                  common.CUSTOM_MOUSE_IMG_MMOUSE_NAME)
            else:
                draw_default_mouse(mouse_start_x, mouse_start_y,
                                   mouse_icon_width, mouse_icon_height,
                                   cls.hold_mouse_buttons['LEFTMOUSE'],
                                   cls.hold_mouse_buttons['RIGHTMOUSE'],
                                   cls.hold_mouse_buttons['MIDDLEMOUSE'],
                                   prefs.color,
                                   prefs.mouse_size * 0.5,
                                   fill=prefs.background,
                                   fill_color=prefs.background_color,
                                   line_thickness=prefs.line_thickness)

        # Draw hold modifier keys.
        if cls.hold_modifier_keys or drawing:
            hold_modifier_keys_text_start_x = \
                hold_modifier_keys_start_x + modifier_keys_box_margin
            hold_modifier_keys_text_start_y = \
                hold_modifier_keys_start_y + modifier_keys_box_margin

            if show_text_background(prefs):
                draw_text_background(
                    modifier_keys_text,
                    font_id,
                    hold_modifier_keys_text_start_x,
                    hold_modifier_keys_text_start_y + modifier_keys_box_margin,
                    prefs.background_color, prefs.margin,
                    prefs.background_rounded_corner_radius)
            else:
                # Draw rounded box.
                draw_rounded_box(
                    hold_modifier_keys_start_x,
                    hold_modifier_keys_start_y,
                    hold_modifier_keys_text_width,
                    hold_modifier_keys_text_height,
                    hold_modifier_keys_text_height * 0.2,
                    show_text_background(prefs),
                    prefs.background_color if show_text_background(prefs)
                    else prefs.color,
                    line_thickness=prefs.line_thickness)

            # Draw modifier key text.
            blf.position(
                font_id,
                hold_modifier_keys_text_start_x,
                hold_modifier_keys_text_start_y + modifier_keys_box_margin,
                0)
            draw_text(
                modifier_keys_text, font_id, prefs.color,
                prefs.shadow, prefs.shadow_color)
            imm.immColor4f(*prefs.color)

            region_redraw = True

        return layer_width, layer_height, region_redraw

    @classmethod
    def _draw_event_history_layer(cls, context, font_id, x, y):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        sh = cls.text_area_height(font_id) + prefs.margin * 2
        region_drawn = False
        color = prefs.color
        blf.color(font_id, *color)

        layer_width = 0.0
        layer_height = 0.0
        event_start_x = x
        event_start_y = y

        event_history = cls.removed_old_event_history()
        layer_height += \
            cls.text_area_height(font_id) * cls.HEIGHT_RATIO_FOR_SEPARATOR
        event_start_y += \
            cls.text_area_height(font_id) * cls.HEIGHT_RATIO_FOR_SEPARATOR
        for _, event_type, modifiers, repeat_count in event_history[::-1]:
            text = get_display_event_text(event_type.name)
            if modifiers:
                mod_keys = cls.sorted_modifier_keys(modifiers)
                text = "{} + {}".format(" + ".join(mod_keys), text)
            if repeat_count > 1:
                text += " x{}".format(repeat_count)

            text_width = \
                cls.text_area_width(text, font_id) + prefs.margin * 2
            offset_x, offset_y = cls.get_alignment_offset(
                context, text_width, prefs.margin)
            blf.position(font_id, event_start_x + offset_x,
                         event_start_y + offset_y, 0)
            if show_text_background(prefs):
                draw_text_background(text, font_id,
                                     event_start_x + offset_x,
                                     event_start_y + offset_y,
                                     prefs.background_color, prefs.margin,
                                     prefs.background_rounded_corner_radius)
            draw_text(text, font_id, prefs.color, prefs.shadow,
                      prefs.shadow_color)

            layer_width = max(text_width, layer_width)
            layer_height += sh
            event_start_y += sh

            region_drawn = True

        return layer_width, layer_height, region_drawn

    @classmethod
    def draw_callback(cls, context):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        if context.window.as_pointer() != cls.origin["window"]:
            return      # Not match target window.

        rect = cls.draw_area_rect(context)
        if not rect:
            return      # No draw target.

        draw_area_min_x, draw_area_min_y, draw_area_max_x, draw_area_max_y = \
            rect
        _, _, _, origin_x, origin_y = cls.get_origin(context)
        draw_area_width = draw_area_max_x - origin_x
        draw_area_height = draw_area_max_y - origin_y
        if draw_area_width == draw_area_height == 0:
            return

        region = context.region
        area = context.area
        if region.type == 'WINDOW':
            region_min_x, region_min_y, region_max_x, region_max_y = \
                get_window_region_rect(area)
        else:
            region_min_x = region.x
            region_min_y = region.y
            region_max_x = region.x + region.width - 1
            region_max_y = region.y + region.height - 1
        if not intersect_aabb(
                [region_min_x, region_min_y], [region_max_x, region_max_y],
                [draw_area_min_x + 1, draw_area_min_y + 1],
                [draw_area_max_x - 1, draw_area_max_y - 1]):
            # We don't need to draw if draw area is not overlapped with region.
            return

        region_drawn = False

        font_size = prefs.font_size
        font_id = 0
        dpi = context.preferences.system.dpi
        blf.size(font_id, font_size, dpi)

        # Clip 'TOOLS' and 'UI' region from 'WINDOW' region if need.
        # This prevents from drawing multiple time when
        # user_preferences.system.use_region_overlap is True.
        if context.area.type == 'VIEW_3D' and region.type == 'WINDOW':
            x_min, y_min, x_max, y_max = get_region_rect_on_v3d(context)
            # Convert absolute coordinate to region local coordinate.
            region_x_min = x_min - region.x
            region_y_min = y_min - region.y
            region_x_max = x_max - region.x + 1
            region_y_max = y_max - region.y + 1
            imm.immSetScissor(
                [region_x_min, region_y_min, region_x_max, region_y_max])

        # Get start position to render.
        x = origin_x - region.x
        y = origin_y - region.y

        # Warm up rendering.
        # This is needed to render the line with more than 1.5 thickness
        # properly.
        draw_rect(0, 0, 0, 0, [0.0, 0.0, 0.0, 0.0])

        # Draw draw area based background.
        if show_draw_area_background(prefs):
            draw_rounded_box(draw_area_min_x - region.x,
                             draw_area_min_y - region.y,
                             draw_area_max_x - draw_area_min_x,
                             draw_area_max_y - draw_area_min_y,
                             prefs.background_rounded_corner_radius,
                             True,
                             prefs.background_color)

        def check_draw_status(cls, context, font_id, layer_name, calc_fn,
                              draw_x, draw_y, draw_w, draw_h):
            user_prefs = bpy.context.preferences
            prefs = user_prefs.addons[__package__].preferences
            if prefs.display_draw_area:
                offset_x, offset_y = cls.get_alignment_offset(context, draw_w)
                draw_rounded_box(draw_x + offset_x,
                                 draw_y + offset_y,
                                 draw_w, draw_h, 0, color=[1.0, 0.0, 0.0, 1.0])
            if output_debug_log():
                calc_w, calc_h = calc_fn(context, font_id)
                mismatch_width = abs(draw_w - calc_w) >= 0.0001
                mismatch_height = abs(draw_h - calc_h) >= 0.0001
                if mismatch_width or mismatch_height:
                    debug_print("Draw area size mismatch. "
                                "[Layer: {} -> (w, h) = ({}, {}), "
                                "(calc_w, calc_h) = ({}, {})]"
                                .format(layer_name, draw_w, draw_h,
                                        calc_w, calc_h))

        # Draw last operator.
        if prefs.show_last_operator:
            w, h, rd = cls._draw_last_operator_layer(context, font_id, x, y)
            check_draw_status(cls, context, font_id, "Last Operator",
                              cls._area_size_last_operator_layer,
                              x, y, w, h)
            y += h
            region_drawn = region_drawn if region_drawn else rd

        # Draw mouse and hold modifier keys
        w, h, rd = cls._draw_mouse_and_modifier_keys_layer(
            context, font_id, x, y)
        check_draw_status(cls, context, font_id,
                          "Mouse and Hold Modifier Keys",
                          cls._area_size_mouse_and_modifier_keys_layer,
                          x, y, w, h)
        y += h
        region_drawn = region_drawn if region_drawn else rd

        # Draw event history.
        w, h, rd = cls._draw_event_history_layer(context, font_id, x, y)
        check_draw_status(cls, context, font_id, "Event History",
                          cls._area_size_event_history_layer,
                          x, y, w, h)
        y += h
        region_drawn = region_drawn if region_drawn else rd

        imm.immSetScissor(None)

        if region_drawn:
            cls.draw_regions_prev.add(region.as_pointer())

    @staticmethod
    @bpy.app.handlers.persistent
    def auto_save(_):
        cls = SK_OT_ScreencastKeys
        context = bpy.context
        prefs = context.preferences

        if not prefs.filepaths.use_auto_save_temporary_files:
            return

        current_time = time.time()
        save_interval = prefs.filepaths.auto_save_time * 60
        if current_time - cls.last_auto_saved_time < save_interval:
            elapsed_time = current_time - cls.last_auto_saved_time
            debug_print("Does not reached save interval (Save interval is "
                        f"{save_interval}, but elapsed time is "
                        f"{elapsed_time})")
            return

        # Perform auto save only if the modal operator is executed from
        # Screencast Keys.
        do_auto_save = False
        for w in bpy.context.window_manager.windows:
            window = cast(
                c_void_p(w.as_pointer()), POINTER(cstruct.wmWindow)).contents
            handler_ptr = cast(
                window.modalhandlers.first, POINTER(cstruct.wmEventHandler))
            while handler_ptr:
                handler = handler_ptr.contents
                if handler.type == \
                        cstruct.eWM_EventHandlerType.WM_HANDLER_TYPE_OP:
                    do_auto_save = True
                    op = handler.op.contents
                    idname = op.idname.decode()
                    op_prefix, op_name = idname.split("_OT_")
                    idname_py = "{}.{}".format(op_prefix.lower(), op_name)
                    if idname_py != SK_OT_ScreencastKeys.bl_idname:
                        debug_print(f"Modal operator '{idname_py}' is "
                                    "running. Skip auto save")
                        return
                handler_ptr = cast(
                    handler.next, POINTER(cstruct.wmEventHandler))

        if not do_auto_save:
            debug_print("No modal operator is running. Skip auto save")
            return

        if bpy.data.is_saved:
            filename = os.path.basename(bpy.data.filepath)
            save_basename = os.path.splitext(filename)[0] + ".blend"
        else:
            pid = os.getpid()
            save_basename = f"{pid}.blend"

        save_dir = os.path.normpath(
            os.path.join(bpy.app.tempdir, os.path.pardir))
        if platform.system() == 'Windows' and not os.path.exists(save_dir):
            save_dir = bpy.utils.user_resource('AUTOSAVE')
        save_path = os.path.join(save_dir, save_basename)

        # If .blend file is updated from other methods, update
        # last_auto_saved_time.
        if os.path.exists(save_path):
            stat = os.stat(save_path)
            if cls.last_auto_saved_time < stat.st_mtime:
                cls.last_auto_saved_time = stat.st_mtime
                debug_print(f"Auto saved file '{save_path}'is updated")
            if current_time - cls.last_auto_saved_time < save_interval:
                elapsed_time = current_time - cls.last_auto_saved_time
                debug_print("Does not reached save interval (Save interval is "
                            f"{save_interval}, but elapsed time is "
                            f"{elapsed_time})")
                return

        # Create directory to store auto save .blend file.
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            # pylint: disable=W0702
            except:     # noqa
                debug_print(f"Unable to create directory '{save_dir}'")
                return

        # auto_save function can be called from multiple threads.
        # auto_saving variable makes sure that saving mainfile is called from
        # only 1 thread.
        if cls.auto_saving:
            return
        cls.auto_saving = True

        # Check again if the current time overs save interval.
        if current_time - cls.last_auto_saved_time < save_interval:
            elapsed_time = current_time - cls.last_auto_saved_time
            debug_print("Does not reached save interval (Save interval is "
                        f"{save_interval}, but elapsed time is "
                        f"{elapsed_time})")
            cls.auto_saving = False
            return

        # Save .blend file.
        try:
            bpy.ops.wm.save_as_mainfile(filepath=save_path, copy=True)
        # pylint: disable=W0703
        except Exception as e:
            debug_print(f"Unable to save '{save_path}' (Reason: {e})")
            cls.auto_saving = False
            return

        debug_print(f"Auto saved '{save_path}'")
        cls.last_auto_saved_time = os.stat(save_path).st_mtime
        prefs.filepaths.auto_save_time = prefs.filepaths.auto_save_time
        cls.auto_saving = False

    @staticmethod
    @bpy.app.handlers.persistent
    def sort_modalhandlers(_):
        """Sort modalhandlers registered on wmWindow.
           This makes SK_OT_ScreencastKeys.model method enable to get events
           consumed by other modalhandlers."""

        user_preferences = bpy.context.preferences
        if user_preferences is None:
            return

        prefs = user_preferences.addons[__package__].preferences
        if not prefs.get_event_aggressively:
            return

        for w in bpy.context.window_manager.windows:
            window = cast(
                c_void_p(w.as_pointer()), POINTER(cstruct.wmWindow)).contents
            handler_ptr = cast(
                window.modalhandlers.first, POINTER(cstruct.wmEventHandler))
            indices = []
            i = 0
            debug_print("====== HANDLER_LIST ======")
            has_ui_handler = False
            while handler_ptr:
                handler = handler_ptr.contents
                if handler.type == \
                        cstruct.eWM_EventHandlerType.WM_HANDLER_TYPE_OP:
                    op = handler.op.contents
                    idname = op.idname.decode()
                    op_prefix, op_name = idname.split("_OT_")
                    idname_py = "{}.{}".format(op_prefix.lower(), op_name)
                    if idname_py == SK_OT_ScreencastKeys.bl_idname:
                        indices.append(i)
                    debug_print(
                        "  TYPE: WM_HANDLER_TYPE_OP ({})"
                        .format(idname_py))
                elif handler.type == \
                        cstruct.eWM_EventHandlerType.WM_HANDLER_TYPE_UI:
                    has_ui_handler = True
                    debug_print("  TYPE: WM_HANDLER_TYPE_UI")
                else:
                    debug_print("  TYPE: {}".format(handler.type))

                handler_ptr = cast(
                    handler.next, POINTER(cstruct.wmEventHandler))
                i += 1
            debug_print("==========================")

            # Blender will crash when we change the space type while Screencast
            # Key is running. This issue is caused by changing order of
            # WM_HANDLER_TYPE_UI handler.
            # So, do nothing if there is a WM_HANDLER_TYPE_UI handler.
            # TODO: Sort only WM_HANDLER_TYPE_OP handlers.
            if has_ui_handler:
                return

            if indices:
                handlers = window.modalhandlers
                for count, index in enumerate(indices):
                    if index != count:
                        prev = handlers.find(index - 2)
                        handler = handlers.find(index)
                        handlers.remove(handler)
                        handlers.insert_after(prev, handler)

    def update_hold_modifier_keys(self, event):
        """Update hold modifier keys."""

        self.hold_modifier_keys.clear()

        if event.shift:
            self.hold_modifier_keys.append(EventType.LEFT_SHIFT)
        if event.oskey:
            self.hold_modifier_keys.append(EventType.OSKEY)
        if event.alt:
            self.hold_modifier_keys.append(EventType.LEFT_ALT)
        if event.ctrl:
            self.hold_modifier_keys.append(EventType.LEFT_CTRL)

        if EventType[event.type] == EventType.WINDOW_DEACTIVATE:
            self.hold_modifier_keys.clear()

    def update_hold_mouse_buttons(self, event):
        """Update hold mouse buttons."""

        is_hold_mouse_event = event.type in self.hold_mouse_buttons.keys()
        if event.type != 'MOUSEMOVE' and not is_hold_mouse_event:
            return

        # Note: This is not complete solution.
        # Release event is not fired in specific cases (ex. open context menu,
        # mouse drag, ...).
        # To solve this issue, use 'MOUSEMOVE' event which will not be fired
        # when some mouse key is not pressed.
        if event.type == 'MOUSEMOVE':
            reset = False
            if compat.check_version(3, 2, 0) < 0:
                if event.value == 'RELEASE':
                    reset = True
            else:
                reset = True

            if reset:
                for k in self.hold_mouse_buttons.keys():
                    self.hold_mouse_buttons[k] = False

        if event.value in ('PRESS', 'CLICK_DRAG'):
            self.hold_mouse_buttons[event.type] = True
        elif event.value == 'RELEASE':
            self.hold_mouse_buttons[event.type] = False

    def is_ignore_event(self, event, prefs=None):
        """Return True if event will not be shown."""

        event_type = EventType[event.type]
        if event_type in {EventType.NONE, EventType.MOUSEMOVE,
                          EventType.INBETWEEN_MOUSEMOVE,
                          EventType.WINDOW_DEACTIVATE, EventType.TEXTINPUT}:
            return True
        elif (prefs is not None) and \
                (not show_mouse_event_history(prefs)) and \
                (event_type in self.MOUSE_EVENT_TYPES):
            return True
        elif event_type.name.startswith("EVT_TWEAK"):
            return True
        elif event_type.name.startswith("TIMER"):
            return True

        return False

    def modal(self, context, event):
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        if not self.__class__.is_running():
            return {'FINISHED'}

        if event.type == '':
            # Many events that should be identified as 'NONE', instead are
            # identified as '' and raise KeyErrors in EventType
            # (i.e. caps lock and the spin tool in edit mode)
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            self.__class__.current_mouse_co = [event.mouse_x, event.mouse_y]

        event_type = EventType[event.type]

        current_time = time.time()

        # Update Area - Space mapping.
        for area in context.screen.areas:
            for space in area.spaces:
                self.area_spaces[area.as_pointer()].add(space.as_pointer())

        # Update hold modifiers keys.
        self.update_hold_modifier_keys(event)
        current_mod_keys = self.hold_modifier_keys.copy()
        if event_type in current_mod_keys:
            # Remove modifier key which is just pressed.
            current_mod_keys.remove(event_type)

        # Update hold mouse buttons.
        self.update_hold_mouse_buttons(event)

        # Update event history.
        if not self.is_ignore_event(event, prefs=prefs) and \
                not self.__class__.is_modifier_event(event) and \
                event.value == 'PRESS':
            current_event = [current_time, event_type, current_mod_keys, 1]

            if self.event_history:
                last_event = self.event_history[-1]
                delta_time = current_time - last_event[0]
                is_same = last_event[1:-1] == current_event[1:-1]
                # If events are raised in short time (e.g. Double Click), the
                # additional events will be raised from the Internal of
                # Blender. This check avoids not to count such events.
                if is_same and delta_time < self.INTERVAL_FOR_IGNORE_EVENT:
                    pass
                # If this event has same event_type and modifiers, we increment
                # repeat_count. However, we reset repeat_count if event
                # interval overs display time.
                elif prefs.repeat_count and is_same and \
                        delta_time < prefs.display_time:
                    last_event[0] = current_time
                    last_event[-1] += 1
                else:
                    self.event_history.append(current_event)
            else:
                self.event_history.append(current_event)
        self.event_history[:] = self.removed_old_event_history()

        # Update operator history.
        operators = list(context.window_manager.operators)
        if operators:
            # Find last operator which detects in previous modal call.
            if self.operator_history:
                addr = self.operator_history[-1][-1]
            else:
                addr = None
            prev_last_op_index = 0
            for i, op in enumerate(operators[::-1]):
                if op.as_pointer() == addr:
                    prev_last_op_index = len(operators) - i
                    break

            # Add operators to history.
            for op in operators[prev_last_op_index:]:
                op_prefix, op_name = op.bl_idname.split("_OT_")
                idname_py = "{}.{}".format(op_prefix.lower(), op_name)
                self.operator_history.append(
                    [current_time, op.bl_label, idname_py, op.as_pointer()])
        self.operator_history[:] = self.removed_old_operator_history()

        # Redraw regions which we want.
        prev_time = self.prev_time
        if not self.is_ignore_event(event, prefs=prefs) or \
                prev_time and current_time - prev_time >= self.TIMER_STEP:
            regions = self.find_redraw_regions(context)

            # If regions which are drawn at previous time, is not draw target
            # at this time, we don't need to redraw anymore.
            # But we raise redraw notification to make sure there are no
            # updates on their regions.
            # If there is update on the region, it will be added to
            # self.draw_regions_prev in draw_callback function.
            for area in context.screen.areas:
                for region in area.regions:
                    if region.as_pointer() in self.draw_regions_prev:
                        region.tag_redraw()
                        self.draw_regions_prev.remove(region.as_pointer())

            # Redraw all target regions.
            # If there is no draw handler attached to the region, we add it to.
            for area, region in regions:
                space_type = self.SPACE_TYPES[area.type]
                handler_key = (space_type, region.type)
                if handler_key not in self.handlers:
                    self.handlers[handler_key] = space_type.draw_handler_add(
                        self.draw_callback, (context, ), region.type,
                        'POST_PIXEL')
                region.tag_redraw()
                self.draw_regions_prev.add(region.as_pointer())

            self.__class__.prev_time = current_time

        return {'PASS_THROUGH'}

    @classmethod
    def draw_handler_remove_all(cls):
        for (space_type, region_type), handle in cls.handlers.items():
            space_type.draw_handler_remove(handle, region_type)
        cls.handlers.clear()

    @classmethod
    def event_timer_add(cls, context):
        wm = context.window_manager

        # Add timer to all windows.
        for window in wm.windows:
            key = window.as_pointer()
            if key not in cls.timers:
                cls.timers[key] = wm.event_timer_add(cls.TIMER_STEP,
                                                     window=window)

    @classmethod
    def event_timer_remove(cls, context):
        wm = context.window_manager

        # Delete timer from all windows.
        for win in wm.windows:
            key = win.as_pointer()
            if key in cls.timers:
                wm.event_timer_remove(cls.timers[key])
        cls.timers.clear()

    @classmethod
    def start(cls, self, context, event, prefs):
        common.reload_custom_mouse_image(prefs, context)
        self.update_hold_modifier_keys(event)
        self.event_timer_add(context)
        context.window_manager.modal_handler_add(self)
        self.origin["window"] = context.window.as_pointer()
        self.origin["area"] = context.area.as_pointer()
        self.origin["space"] = context.space_data.as_pointer()
        self.origin["region_type"] = context.region.type
        context.area.tag_redraw()
        if prefs.get_event_aggressively:
            bpy.app.handlers.depsgraph_update_pre.append(
                cls.sort_modalhandlers)
        if prefs.auto_save:
            bpy.app.handlers.depsgraph_update_pre.append(cls.auto_save)

        cls.running = True

    @classmethod
    def stop(cls, self, context):
        if cls.sort_modalhandlers in bpy.app.handlers.depsgraph_update_pre:
            bpy.app.handlers.depsgraph_update_pre.remove(
                cls.sort_modalhandlers)
        if cls.auto_save in bpy.app.handlers.depsgraph_update_pre:
            bpy.app.handlers.depsgraph_update_pre.remove(cls.auto_save)
        self.event_timer_remove(context)
        self.draw_handler_remove_all()
        self.hold_modifier_keys.clear()
        self.event_history.clear()
        self.operator_history.clear()
        self.draw_regions_prev.clear()
        context.area.tag_redraw()

        cls.running = False

    def invoke(self, context, event):
        cls = self.__class__
        user_prefs = context.preferences
        prefs = user_prefs.addons[__package__].preferences

        if self.restart:
            self.stop(self, context)
            self.start(self, context, event, prefs)

            return {'RUNNING_MODAL'}
        else:
            if cls.is_running():
                self.stop(self, context)
                return {'CANCELLED'}
            else:
                self.start(self, context, event, prefs)
                return {'RUNNING_MODAL'}


@BlClassRegistry()
class SK_OT_SetOrigin(bpy.types.Operator):
    bl_idname = "wm.sk_set_origin"
    bl_label = "Screencast Keys Set Origin"
    bl_description = ""
    bl_options = {'REGISTER'}

    # Draw handlers.
    # Format: {(Space, Region.type): handle}
    handlers = {}

    # Previous mouseovered area.
    area_prev = None

    # Mouseovered region.
    mouseovered_region = None

    def draw_callback(self, context):
        region = context.region
        if region and region == self.mouseovered_region:
            original_state = gpu.state.blend_get()
            gpu.state.blend_set('ALPHA')
            imm.immColor4f(1.0, 0.0, 0.0, 0.3)
            imm.immRecti(0, 0, region.width, region.height)
            imm.immColor4f(1.0, 1.0, 1.0, 1.0)
            gpu.state.blend_set(original_state)

    def draw_handler_add(self, context):
        for area in context.screen.areas:
            space_type = SK_OT_ScreencastKeys.SPACE_TYPES[area.type]
            for region in area.regions:
                if region.type == "":
                    continue
                key = (space_type, region.type)
                if key not in self.handlers:
                    handle = space_type.draw_handler_add(
                        self.draw_callback, (context,), region.type,
                        'POST_PIXEL')
                    self.handlers[key] = handle

    def draw_handler_remove_all(self):
        for (space_type, region_type), handle in self.handlers.items():
            space_type.draw_handler_remove(handle, region_type)
        self.handlers.clear()

    def get_mouseovered_region(self, context, event):
        """Get mouseovered area and region."""

        x, y = event.mouse_x, event.mouse_y
        for area in context.screen.areas:
            for region in area.regions:
                if region.type == "":
                    continue
                within_x = region.x <= x < region.x + region.width
                within_y = region.y <= y < region.y + region.height
                if within_x and within_y:
                    return area, region

        return None, None

    def modal(self, context, event):
        area, region = self.get_mouseovered_region(context, event)

        # Redraw previous mouseovered area.
        if self.area_prev:
            self.area_prev.tag_redraw()

        if area:
            area.tag_redraw()

        self.mouseovered_region = region
        self.area_prev = area

        if event.type in {'LEFTMOUSE', 'SPACE', 'RET', 'NUMPAD_ENTER'}:
            if event.value == 'PRESS':
                # Set origin.
                origin = SK_OT_ScreencastKeys.origin
                origin["window"] = context.window.as_pointer()
                origin["area"] = area.as_pointer()
                origin["space"] = area.spaces.active.as_pointer()
                origin["region_type"] = region.type
                self.draw_handler_remove_all()
                return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # Canceled.
            self.draw_handler_remove_all()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, _):
        self.area_prev = None
        self.mouseovered_region = None
        self.draw_handler_add(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


@BlClassRegistry()
class SK_OT_WaitBlenderInitializedAndStartScreencastKeys(bpy.types.Operator):
    bl_idname = "wm.sk_wait_blender_initialized_and_start_screencast_keys"
    bl_label = "Wait For Blender Initialized And Start Screencast Keys"

    initialization_handler = None

    def get_first_space_class(self, context):
        space_to_class = {
            'VIEW_3D': bpy.types.SpaceView3D,
            'IMAGE_EDITOR': bpy.types.SpaceImageEditor,
            'NODE_EDITOR': bpy.types.SpaceNodeEditor,
            'SEQUENCE_EDITOR': bpy.types.SpaceSequenceEditor,
            'CLIP_EDITOR': bpy.types.SpaceClipEditor,
            'DOPESHEET_EDITOR': bpy.types.SpaceDopeSheetEditor,
            'GRAPH_EDITOR': bpy.types.SpaceGraphEditor,
            'NLA_EDITOR': bpy.types.SpaceNLA,
            'TEXT_EDITOR': bpy.types.SpaceTextEditor,
            'CONSOLE': bpy.types.SpaceConsole,
            'INFO': bpy.types.SpaceInfo,
            'OUTLINER': bpy.types.SpaceOutliner,
            'PROPERTIES': bpy.types.SpaceProperties,
            'FILE_BROWSER': bpy.types.SpaceFileBrowser,
            'SPREADSHEET': bpy.types.SpaceSpreadsheet,
            'PREFERENCES': bpy.types.SpacePreferences,
        }

        area_types = []
        for area in context.screen.areas:
            if area.type in space_to_class.keys():
                area_types.append(area.type)
        if len(area_types) == 0:
            return None

        area_types.sort(key=lambda t: list(space_to_class.keys()).index(t))

        return space_to_class[area_types[0]]

    def execute(self, context):
        cls = self.__class__
        space_class = self.get_first_space_class(context)
        if space_class is None:
            debug_print(
                "Failed to call "
                "SK_OT_WaitBlenderInitializedAndStartScreencastKeys because "
                "the space candidate not found.")
            return {'CANCELLED'}

        # If we call bpy.ops.wm.sk_screencast_keys directly, no changes are
        # made because bpy.context.area is not loaded at that moment.
        # Therefore, we need to call bpy.ops.wm.sk_screencast_keys with delay
        # via co-routine method.
        cls.initialization_handler = space_class.draw_handler_add(
            cls.intialization_callback, (space_class, None),
            'WINDOW', 'POST_PIXEL')
        debug_print("SK_OT_WaitBlenderInitializedAndStartScreencastKeys "
                    "handler address: " + str(cls.initialization_handler))
        return {'FINISHED'}

    @classmethod
    def intialization_callback(cls, space_class, ___):
        if bpy.context.area is not None:
            bpy.ops.wm.sk_screencast_keys('INVOKE_REGION_WIN', restart=True)
            if cls.initialization_handler is not None:
                space_class.draw_handler_remove(
                    cls.initialization_handler, 'WINDOW')
