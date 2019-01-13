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


import math
import collections
import enum
import re
import string
import time

import blf
import bpy
import bpy.props

from .utils.bl_class_registry import BlClassRegistry
from .utils import compatibility as compat

if compat.check_version(2, 80, 0) >= 0:
    from .compat import bglx as bgl
else:
    import bgl


def draw_rounded_box(x, y, w, h, round_radius):
    def circle_verts_num(r):
        """描画に最適な？円の頂点数を求める"""
        n = 32
        threshold = 2.0  # pixcel
        while True:
            if r * 2 * math.pi / n > threshold:
                return n
            n -= 4
            if n < 1:
                return 1

    num = circle_verts_num(round_radius)
    n = int(num / 4) + 1
    pi = math.pi
    angle = pi * 2 / num
    bgl.glBegin(bgl.GL_LINE_LOOP)
    for x0, y0, a in ((x + round_radius, y + round_radius, pi),
                      (x + w - round_radius, y + round_radius,
                       pi * 1.5),
                      (x + w - round_radius, y + h - round_radius, 0.0),
                      (x + round_radius, y + h - round_radius,
                       pi * 0.5)):
        for i in range(n):
            xco = x0 + round_radius * math.cos(a)
            yco = y0 + round_radius * math.sin(a)
            bgl.glVertex2f(xco, yco)
            a += angle
    bgl.glEnd()


event_type_enum_items = bpy.types.Event.bl_rna.properties['type'].enum_items

EventType = enum.IntEnum(
    'EventType',
    [(e.identifier, e.value) for e in event_type_enum_items])

EventType.names = {e.identifier: e.name for e in event_type_enum_items}


def intersect_aabb(min1, max1, min2, max2):
    """from isect_aabb_aabb_v3()
    """
    for i in range(len(min1)):
        if max1[i] < min2[i] or max2[i] < min1[i]:
            return False
    return True


def region_window_rectangle(area):
    rect = [99999, 99999, 0, 0]
    for region in area.regions:
        if region.type == 'WINDOW':
            rect[0] = min(rect[0], region.x)
            rect[1] = min(rect[1], region.y)
            rect[2] = max(region.x + region.width - 1, rect[2])
            rect[3] = max(region.y + region.height - 1, rect[3])
    return rect


def region_rectangle_v3d(context, area=None, region=None):
    """
    for Region Overlap
    return window coordinates (xmin, ymin, xmax, ymax)
    """
    if not area:
        area = context.area
    if not region:
        region = context.region

    if region.type != 'WINDOW':
        return (region.x, region.y,
                region.x + region.width, region.y + region.height)

    window = tools = tool_props = ui = None
    for ar in area.regions:
        if ar.width > 1:
            if ar.type == 'WINDOW':
                if ar == region:
                    region = ar
            elif ar.type == 'TOOLS':
                tools = ar
            elif ar.type == 'TOOL_PROPS':
                tool_props = ar
            elif ar.type == 'UI':
                ui = ar

    xmin, _, xmax, _ = region_window_rectangle(area)
    sys_pref = compat.get_user_preferences(context).system
    if sys_pref.use_region_overlap:
        left_widht = right_widht = 0
        if tools and ui:
            r1, r2 = sorted([tools, ui], key=lambda ar: ar.x)
            if r1.x == area.x:
                # 両方左
                if r2.x == r1.x + r1.width:
                    left_widht = r1.width + r2.width
                # 片方ずつ
                else:
                    left_widht = r1.width
                    right_widht = r2.width
            # 両方右
            else:
                right_widht = r1.width + r2.width

        elif tools:
            if tools.x == area.x:
                left_widht = tools.width
            else:
                right_widht = tools.width

        elif ui:
            if ui.x == area.x:
                left_widht = ui.width
            else:
                right_widht = ui.width

        xmin = max(xmin, area.x + left_widht)
        xmax = min(xmax, area.x + area.width - right_widht - 1)

    ymin = region.y
    ymax = region.y + region.height - 1
    return xmin, ymin, xmax, ymax


@BlClassRegistry()
class ScreencastKeysStatus(bpy.types.Operator):
    bl_idname = 'wm.screencast_keys'
    bl_label = 'Screencast Keys'
    bl_description = 'Display keys pressed'
    bl_options = {'REGISTER'}


    # hold modifier keys
    hold_modifier_keys = []

    event_log = []  # [[time, event_type, mod, repeat], ...]
    operator_log = []  # [[time, bl_label, idname_py, addr], ...]

    modifier_event_types = [
        EventType.LEFT_SHIFT,
        EventType.RIGHT_SHIFT,
        EventType.LEFT_CTRL,
        EventType.RIGHT_CTRL,
        EventType.LEFT_ALT,
        EventType.RIGHT_ALT,
        EventType.OSKEY
    ]

    space_types = compat.get_all_space_types()

    SEPARATOR_HEIGHT = 0.6  # フォント高の倍率

    TIMER_STEP = 0.1
    prev_time = 0.0
    timers = {}  # {Window.as_pointer(): Timer, ...}

    handlers = {}  # {(Space, region_type): handle, ...}

    draw_regions_prev = set()  # {region.as_pointer(), ...}
    origin = {'window': '', 'area': '', 'space': '', 'region_type': ''}
    # {area_addr: [space_addr, ...], ...}
    area_spaces = collections.defaultdict(set)

    running = False

    @classmethod
    def sorted_modifiers(cls, modifiers):
        """modifierを並び替えて重複を除去した名前を返す"""

        def sort_func(et):
            if et in cls.modifier_event_types:
                return cls.modifier_event_types.index(et)
            else:
                return 100

        modifiers = sorted(modifiers, key=sort_func)
        names = []
        for mod in modifiers:
            name = mod.names[mod.name]
            if mod in cls.modifier_event_types:
                name = re.sub('(Left |Right )', '', name)
            if name not in names:
                names.append(name)
        return names

    @classmethod
    def removed_old_event_log(cls):
        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences
        """:type: ScreenCastKeysPreferences"""
        current_time = time.time()
        event_log = []
        for item in cls.event_log:
            event_time = item[0]
            t = current_time - event_time
            if t <= prefs.display_time:
                event_log.append(item)
        return event_log

    @classmethod
    def removed_old_operator_log(cls):
        return cls.operator_log[-32:]

    @classmethod
    def get_origin(cls, context):
        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences
        """:type: ScreenCastKeysPreferences"""

        def match(area):
            # for area in context.screen.areas:
            if area.as_pointer() == cls.origin['area']:
                return True
            elif area.spaces.active.as_pointer() == cls.origin['space']:
                return True
            else:
                addr = area.as_pointer()
                if addr in cls.area_spaces:
                    addrs = {sp.as_pointer() for sp in area.spaces}
                    if cls.origin['space'] in addrs:
                        return True
            return False

        x, y = prefs.offset
        for win in context.window_manager.windows:
            if win.as_pointer() == cls.origin['window']:
                break
        else:
            return None, None, None, 0, 0

        if prefs.origin == 'WINDOW':
            return win, None, None, x, y
        elif prefs.origin == 'AREA':
            for area in win.screen.areas:
                if match(area):
                    return win, area, None, x + area.x, y + area.y
        elif prefs.origin == 'REGION':
            for area in win.screen.areas:
                if match(area):
                    for region in area.regions:
                        if region.type == cls.origin['region_type']:
                            if area.type == 'VIEW_3D':
                                rect = region_rectangle_v3d(context, area,
                                                            region)
                                x += rect[0]
                                y += rect[1]
                            else:
                                x += region.x
                                y += region.y
                            return win, area, region, x, y
        return None, None, None, 0, 0

    @classmethod
    def calc_draw_rectangle(cls, context):
        """(xmin, ymin, xmax, ymax)というwindow座標を返す。
        該当する描画範囲がないならNoneを返す。
        """

        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences
        """:type: ScreenCastKeysPreferences"""

        font_size = prefs.font_size
        font_id = 0
        dpi = compat.get_user_preferences(context).system.dpi
        blf.size(font_id, font_size, dpi)

        th = blf.dimensions(0, string.printable)[1]

        win, area, region, x, y = cls.get_origin(context)
        if not win:
            return None

        w = h = 0

        if prefs.show_last_operator:
            operator_log = cls.removed_old_operator_log()
            if operator_log:
                t, name, idname_py, addr = operator_log[-1]
                text = bpy.app.translations.pgettext(name, 'Operator')
                text += " ('{}')".format(idname_py)
                tw = blf.dimensions(font_id, text)[0]
                w = max(w, tw)
            h += th + th * cls.SEPARATOR_HEIGHT

        if cls.hold_modifier_keys:
            mod_names = cls.sorted_modifiers(cls.hold_modifier_keys)
            text = ' + '.join(mod_names)
            tw = blf.dimensions(font_id, text)[0]
            w = max(w, tw)
            h += th

        event_log = cls.removed_old_event_log()

        if cls.hold_modifier_keys or event_log:
            tw = blf.dimensions(font_id, 'Left Mouse')[0]
            w = max(w, tw)
            h += th * cls.SEPARATOR_HEIGHT

        for event_time, event_type, modifiers, count in event_log[::-1]:
            text = event_type.names[event_type.name]
            if modifiers:
                mod_names = cls.sorted_modifiers(modifiers)
                text = ' + '.join(mod_names) + ' + ' + text
            if count > 1:
                text += ' x' + str(count)

            w = max(w, blf.dimensions(font_id, text)[0])
            h += th

        h += th

        if prefs.origin == 'WINDOW':
            return x, y, x + w, y + h
        else:
            if prefs.origin == 'AREA':
                xmin = area.x
                ymin = area.y
                xmax = area.x + area.width - 1
                ymax = area.y + area.height - 1
            else:
                xmin = region.x
                ymin = region.y
                xmax = region.x + region.width - 1
                ymax = region.y + region.height - 1
            return (max(x, xmin), max(y, ymin),
                    min(x + w, xmax), min(y + h, ymax))

    @classmethod
    def find_redraw_regions(cls, context):
        """[(area, region), ...]"""

        rect = cls.calc_draw_rectangle(context)
        if not rect:
            return []
        x, y, xmax, ymax = rect
        w = xmax - x
        h = ymax - y
        if w == h == 0:
            return []

        regions = []
        for area in context.screen.areas:
            for region in area.regions:
                # TODO: region.id is not available in Blender 2.8
                min1 = (region.x, region.y)
                max1 = (region.x + region.width - 1,
                        region.y + region.height - 1)
                if intersect_aabb(min1, max1, (x, y),
                                  (x + w - 1, y + h - 1)):
                    regions.append((area, region))
        return regions

    @classmethod
    def draw_callback(cls, context):
        # FIXME: 起動中にaddonを無効にした場合,get_instance()が例外を吐く
        prefs = compat.get_user_preferences(context).addons["screencastkeys"].preferences

        if context.window.as_pointer() != cls.origin['window']:
            return
        rect = cls.calc_draw_rectangle(context)
        if not rect:
            return
        xmin, ymin, xmax, ymax = rect
        win, _area, _region, x, y = cls.get_origin(context)
        w = xmax - x
        h = ymax - y
        if w == h == 0:
            return
        region = context.region
        area = context.area
        if region.type == 'WINDOW':
            r_xmin, r_ymin, r_xmax, r_ymax = region_window_rectangle(area)
        else:
            r_xmin, r_ymin, r_xmax, r_ymax = (
                region.x,
                region.y,
                region.x + region.width - 1,
                region.y + region.height - 1)
        if not intersect_aabb(
                (r_xmin, r_ymin), (r_xmax, r_ymax),
                (xmin + 1, ymin + 1), (xmax - 1, ymax - 1)):
            return

        current_time = time.time()
        draw_any = False

        font_size = prefs.font_size
        font_id = 0
        dpi = compat.get_user_preferences(context).system.dpi
        blf.size(font_id, font_size, dpi)

        def draw_text(text):
            col = prefs.color_shadow
            compat.set_blf_font_color(font_id, *col[:3], col[3] * 20)
            compat.set_blf_blur(font_id, 5)
            blf.draw(font_id, text)
            compat.set_blf_blur(font_id, 0)

            compat.set_blf_font_color(font_id, *prefs.color, 1.0)
            blf.draw(font_id, text)

        def draw_line(p1, p2):
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glEnable(bgl.GL_LINE_SMOOTH)

            bgl.glLineWidth(3.0)
            bgl.glColor4f(*prefs.color_shadow)
            bgl.glBegin(bgl.GL_LINES)
            bgl.glVertex2f(*p1)
            bgl.glVertex2f(*p2)
            bgl.glEnd()

            bgl.glLineWidth(1.0 if prefs.color_shadow[-1] == 0.0 else 1.5)
            bgl.glColor3f(*prefs.color)
            bgl.glBegin(bgl.GL_LINES)
            bgl.glVertex2f(*p1)
            bgl.glVertex2f(*p2)
            bgl.glEnd()

            bgl.glLineWidth(1.0)
            bgl.glDisable(bgl.GL_LINE_SMOOTH)

        # user_preferences.system.use_region_overlapが真の場合に、
        # 二重に描画されるのを防ぐ
        glscissorbox = bgl.Buffer(bgl.GL_INT, 4)
        bgl.glGetIntegerv(bgl.GL_SCISSOR_BOX, glscissorbox)
        if context.area.type == 'VIEW_3D' and region.type == 'WINDOW':
            xmin, ymin, xmax, ymax = region_rectangle_v3d(context)
            bgl.glScissor(xmin, ymin, xmax - xmin + 1, ymax - ymin + 1)

        th = blf.dimensions(0, string.printable)[1]
        px = x - region.x
        py = y - region.y

        operator_log = cls.removed_old_operator_log()
        if prefs.show_last_operator and operator_log:
            t, name, idname_py, addr = operator_log[-1]
            if current_time - t <= prefs.display_time:
                color = prefs.color
                compat.set_blf_font_color(font_id, *color, 1.0)

                text = bpy.app.translations.pgettext_iface(name, 'Operator')
                text += " ('{}')".format(idname_py)

                blf.position(font_id, px, py, 0)
                draw_text(text)
                py += th + th * cls.SEPARATOR_HEIGHT * 0.2
                tw = blf.dimensions(font_id, 'Left Mouse')[0]  # 適当
                draw_line((px, py), (px + tw, py))
                py += th * cls.SEPARATOR_HEIGHT * 0.8

                draw_any = True

            else:
                py += th + th * cls.SEPARATOR_HEIGHT

        compat.set_blf_font_color(font_id, *prefs.color, 1.0)
        margin = th * 0.2
        if cls.hold_modifier_keys or False:   # is_rendering
            col = prefs.color_shadow[:3] + (prefs.color_shadow[3] * 2,)
            mod_names = cls.sorted_modifiers(cls.hold_modifier_keys)
            if False:    # is_rendering
                if 0:
                    text = '- - -'
                else:
                    text = ''
            else:
                text = ' + '.join(mod_names)

            ofsy = -th * 0.0
            box_h = th + margin * 2
            blf.position(font_id, px, py + margin, 0)
            draw_text(text)
            w, h = blf.dimensions(font_id, text)
            draw_rounded_box(px - margin, py - margin + ofsy,
                             w + margin * 2, box_h, box_h * 0.2)
            draw_any = True
        py += th + margin * 2

        event_log = cls.removed_old_event_log()

        py += th * cls.SEPARATOR_HEIGHT

        for event_time, event_type, modifiers, count in event_log[::-1]:
            color = prefs.color
            compat.set_blf_font_color(font_id, *color, 1.0)

            text = event_type.names[event_type.name]
            if modifiers:
                mod_names = cls.sorted_modifiers(modifiers)
                text = ' + '.join(mod_names) + ' + ' + text
            if count > 1:
                text += ' x' + str(count)
            blf.position(font_id, px, py, 0)
            draw_text(text)

            py += th
            draw_any = True

        bgl.glDisable(bgl.GL_BLEND)
        bgl.glScissor(*glscissorbox)
        bgl.glLineWidth(1.0)

        if draw_any:
            cls.draw_regions_prev.add(region.as_pointer())

    def update_hold_modifier_keys(self, event):

        self.hold_modifier_keys.clear()

        mod_keys = []
        if event.shift:
            mod_keys.append(EventType.LEFT_SHIFT)
        if event.oskey:
            mod_keys.append(EventType.OSKEY)
        if event.alt:
            mod_keys.append(EventType.LEFT_ALT)
        if event.ctrl:
            mod_keys.append(EventType.LEFT_CTRL)

        if EventType[event.type] == EventType.WINDOW_DEACTIVATE:
            mod_keys = []

        self.hold_modifier_keys.extend(mod_keys)

    def is_ignore_event(self, event):
        event_type = EventType[event.type]
        if event_type in {EventType.NONE, EventType.MOUSEMOVE,
                          EventType.INBETWEEN_MOUSEMOVE,
                          EventType.WINDOW_DEACTIVATE, EventType.TEXTINPUT}:
            return True
        elif event_type.name.startswith('EVT_TWEAK'):
            return True
        elif event_type.name.startswith('TIMER'):
            return True

    def is_modifier_event(self, event):
        event_type = EventType[event.type]
        return event_type in self.modifier_event_types

    def modal(self, context, event):
        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences

        if not self.__class__.running:
            return {'FINISHED'}

        event_type = EventType[event.type]
        current_time = time.time()

        # update cls.area_spaces
        for area in context.screen.areas:
            for space in area.spaces:
                self.area_spaces[area.as_pointer()].add(space.as_pointer())

        # update hold modifiers keys
        self.update_hold_modifier_keys(event)
        current_mod = self.hold_modifier_keys.copy()
        if event_type in current_mod:
            current_mod.remove(event_type)

        # event_log
        if (not self.is_ignore_event(event) and
                not self.is_modifier_event(event) and event.value == 'PRESS'):
            last = self.event_log[-1] if self.event_log else None
            current = [current_time, event_type, current_mod, 1]
            if (last and last[1:-1] == current[1:-1] and
                    current_time - last[0] < prefs.display_time):
                last[0] = current_time
                last[-1] += 1
            else:
                self.event_log.append(current)
        self.event_log[:] = self.removed_old_event_log()

        # operator_log
        operators = list(context.window_manager.operators)

        if operators:
            if self.operator_log:
                addr = self.operator_log[-1][-1]
            else:
                addr = None
            j = 0
            for i, op in enumerate(operators[::-1]):
                if op.as_pointer() == addr:
                    j = len(operators) - i
                    break

            for op in operators[j:]:
                m, f = op.bl_idname.split('_OT_')
                idname_py = m.lower() + '.' + f
                self.operator_log.append(
                    [current_time, op.bl_label, idname_py, op.as_pointer()])
        self.operator_log[:] = self.removed_old_operator_log()

        # redraw
        prev_time = self.prev_time
        if (not self.is_ignore_event(event) or
                prev_time and current_time - prev_time >= self.TIMER_STEP):
            regions = self.find_redraw_regions(context)

            # 前回描画した箇所でregionsに含まれないものは再描画
            for area in context.screen.areas:
                for region in area.regions:
                    if region.as_pointer() in self.draw_regions_prev:
                        # TODO: region.id is not available in Blender 2.8
                        region.tag_redraw()
                        self.draw_regions_prev.remove(region.as_pointer())


            # 再描画
            for area, region in regions:
                space_type = self.space_types[area.type]
                h_key = (space_type, region.type)
                if h_key not in self.handlers:
                    self.handlers[h_key] = space_type.draw_handler_add(
                        self.draw_callback, (context,), region.type,
                        'POST_PIXEL')
                region.tag_redraw()
                self.draw_regions_prev.add(region.as_pointer())

            self.__class__.prev_time = current_time

        return {'PASS_THROUGH'}

    @classmethod
    def draw_handler_remove(cls):
        for (space_type, region_type), handle in cls.handlers.items():
            space_type.draw_handler_remove(handle, region_type)
        cls.handlers.clear()

    @classmethod
    def event_timer_add(cls, context):
        wm = context.window_manager
        for win in wm.windows:
            key = win.as_pointer()
            if key not in cls.timers:
                cls.timers[key] = wm.event_timer_add(cls.TIMER_STEP, window=win)

    @classmethod
    def event_timer_remove(cls, context):
        wm = context.window_manager
        for win in wm.windows:
            key = win.as_pointer()
            if key in cls.timers:
                wm.event_timer_remove(cls.timers[key])
        cls.timers.clear()

    def invoke(self, context, event):
        cls = self.__class__
        if cls.running:
            self.event_timer_remove(context)
            self.draw_handler_remove()
            self.hold_modifier_keys.clear()
            self.event_log.clear()
            self.operator_log.clear()
            self.draw_regions_prev.clear()
            context.area.tag_redraw()
            cls.running = False
            return {'CANCELLED'}
        else:
            self.update_hold_modifier_keys(event)
            self.event_timer_add(context)
            context.window_manager.modal_handler_add(self)
            self.origin['window'] = context.window.as_pointer()
            self.origin['area'] = context.area.as_pointer()
            self.origin['space'] = context.space_data.as_pointer()
            self.origin['region_type'] = context.region.type
            context.area.tag_redraw()
            cls.running = True
            return {'RUNNING_MODAL'}


@BlClassRegistry()
class ScreencastKeysStatusSetOrigin(bpy.types.Operator):
    bl_idname = 'wm.screencast_keys_set_origin'
    bl_label = 'Screencast Keys Set Origin'
    bl_description = ''
    bl_options = {'REGISTER'}

    color = (1.0, 0.0, 0.0, 0.3)
    handles = {}  # {(space_type, region_type): handle, ...}

    def draw_callback(self, context):
        region = context.region
        if region and region == self.region:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glColor4f(*self.color)
            bgl.glRecti(0, 0, region.width, region.height)
            bgl.glDisable(bgl.GL_BLEND)
            bgl.glColor4f(1.0, 1.0, 1.0, 1.0)  # 初期値ってこれだっけ？

    def draw_handler_add(self, context):
        for area in context.screen.areas:
            space_type = ScreencastKeysStatus.space_types[area.type]
            for region in area.regions:
                # TODO: region.id is not available in Blender 2.8
                if region.type != "":
                    key = (space_type, region.type)
                    if key not in self.handles:
                        handle = space_type.draw_handler_add(
                            self.draw_callback, (context,), region.type,
                            'POST_PIXEL')
                        self.handles[key] = handle

    def draw_handler_remove(self):
        for (space_type, region_type), handle in self.handles.items():
            space_type.draw_handler_remove(handle, region_type)
        self.handles.clear()

    def current_region(self, context, event):
        x, y = event.mouse_x, event.mouse_y
        for area in context.screen.areas:
            for region in area.regions:
                # TODO: region.id is not available in Blender 2.8
                if region.x <= x < region.x + region.width:
                    if region.y <= y < region.y + region.height:
                        return area, region
        return None, None

    def modal(self, context, event):
        area, region = self.current_region(context, event)
        if self.area_prev:
            self.area_prev.tag_redraw()
        if area:
            area.tag_redraw()
        self.region = region
        if event.type in {'LEFTMOUSE', 'SPACE', 'RET', 'NUMPAD_ENTER'}:
            if event.value == 'PRESS':
                origin = ScreencastKeysStatus.origin
                origin['window'] = context.window.as_pointer()
                origin['area'] = area.as_pointer()
                origin['space'] = area.spaces.active.as_pointer()
                origin['region_type'] = region.type
                self.draw_handler_remove()
                return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.draw_handler_remove()
            return {'CANCELLED'}
        self.area_prev = area
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.area_prev = None
        self.region = None
        self.draw_handler_add(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


@BlClassRegistry()
class ScreencastKeysPanel(bpy.types.Panel):
    bl_idname = 'WM_PT_screencast_keys'
    bl_label = 'Screencast Keys'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Screencast Keys"

    def draw_header(self, context):
        layout = self.layout
        layout.prop(context.window_manager, 'enable_screencast_keys',
                    text='')

    def draw(self, context):
        layout = self.layout
        prefs = compat.get_user_preferences(bpy.context).addons["screencastkeys"].preferences

        column = layout.column()

        column.prop(prefs, 'color')
        column.prop(prefs, 'color_shadow')
        column.prop(prefs, 'font_size')
        column.prop(prefs, 'display_time')

        column.separator()

        column.prop(prefs, 'origin')
        row = column.row()
        row.prop(prefs, 'offset')
        column.operator('wm.screencast_keys_set_origin',
                        text='Set Origin')
        column.prop(prefs, 'show_last_operator', text='Last Operator')

    @classmethod
    def register(cls):
        def get_func(self):
            return ScreencastKeysStatus.running

        def set_func(self, value):
            pass

        def update_func(self, context):
            bpy.ops.wm.screencast_keys('INVOKE_REGION_WIN')

        bpy.types.WindowManager.enable_screencast_keys = \
            bpy.props.BoolProperty(
                name='Screencast Keys',
                get=get_func,
                set=set_func,
                update=update_func,
            )

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.enable_screencast_keys
