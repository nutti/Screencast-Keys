from ctypes import (
    c_void_p, c_char, c_short, c_int, c_int8,
    addressof, cast, pointer,
    Structure,
    POINTER,
)


# pylint: disable=C0103
class eWM_EventHandlerType:
    """Defined in $source/blender/windowmanager/wm_event_system.h"""

    WM_HANDLER_TYPE_GIZMO = 1
    WM_HANDLER_TYPE_UI = 2
    WM_HANDLER_TYPE_OP = 3
    WM_HANDLER_TYPE_DROPBOX = 4
    WM_HANDLER_TYPE_KEYMAP = 5


# pylint: disable=W0201
class Link(Structure):
    """Defined in $source/blender/makesdna/DNA_listBase.h"""


# pylint: disable=W0212
Link._fields_ = [
    ("next", POINTER(Link)),
    ("prev", POINTER(Link)),
]


# pylint: disable=W0201
class ListBase(Structure):
    """Defined in $source/blender/makesdna/DNA_listBase.h"""

    def remove(self, vlink):
        """Ref: BLI_remlink"""

        link = vlink
        if not vlink:
            return

        if link.next:
            link.next.contents.prev = link.prev
        if link.prev:
            link.prev.contents.next = link.next

        if self.last == addressof(link):
            self.last = cast(link.prev, c_void_p)
        if self.first == addressof(link):
            self.first = cast(link.next, c_void_p)

    def find(self, number):
        """Ref: BLI_findlink"""

        link = None
        if number >= 0:
            link = cast(c_void_p(self.first), POINTER(Link))
            while link and number != 0:
                number -= 1
                link = link.contents.next
        return link.contents if link else None

    def insert_after(self, vprevlink, vnewlink):
        """Ref: BLI_insertlinkafter"""

        prevlink = vprevlink
        newlink = vnewlink

        if not newlink:
            return

        def gen_ptr(link):
            if isinstance(link, (int, type(None))):
                return cast(c_void_p(link), POINTER(Link))
            else:
                return pointer(link)

        if not self.first:
            self.first = self.last = addressof(newlink)
            return

        if not prevlink:
            newlink.prev = None
            newlink.next = gen_ptr(self.first)
            newlink.next.contents.prev = gen_ptr(newlink)
            self.first = addressof(newlink)
            return

        if self.last == addressof(prevlink):
            self.last = addressof(newlink)

        newlink.next = prevlink.next
        newlink.prev = gen_ptr(prevlink)
        prevlink.next = gen_ptr(newlink)
        if newlink.next:
            newlink.next.prev = gen_ptr(newlink)


# pylint: disable=W0212
ListBase._fields_ = [
    ("first", c_void_p),
    ("last", c_void_p),
]


# pylint: disable=W0201
class ScrAreaMap(Structure):
    """Defined in $source/blender/makesdna/DNA_screen_types.h"""


# pylint: disable=W0212
ScrAreaMap._fields_ = [
    ("vertbase", ListBase),
    ("edgebase", ListBase),
    ("areabase", ListBase),
]


# pylint: disable=W0201
class wmWindow(Structure):
    """Defined in $source/blender/makesdna/DNA_windowmanager_types.h"""


# pylint: disable=W0212
wmWindow._fields_ = [
    ("next", POINTER(wmWindow)),
    ("prev", POINTER(wmWindow)),
    ("ghostwin", c_void_p),
    ("gpuctx", c_void_p),
    ("parent", POINTER(wmWindow)),
    # Scene
    ("scene", c_void_p),
    # Scene
    ("new_scene", c_void_p),
    ("view_layer_name", c_char * 64),
    # Scene
    ("unpinned_scene", c_void_p),
    # WorkSpaceInstanceHook
    ("workspace_hook", c_void_p),
    ("global_areas", ScrAreaMap),
    # bScreen
    ("screen", c_void_p),
    ("winid", c_int),
    ("posx", c_short),
    ("posy", c_short),
    ("sizex", c_short),
    ("sizey", c_short),
    ("windowstate", c_char),
    ("active", c_char),
    ("cursor", c_short),
    ("lastcursor", c_short),
    ("modalcursor", c_short),
    ("grabcursor", c_short),
    ("addmousemove", c_char),
    ("tag_cursor_refresh", c_char),
    ("event_queue_check_click", c_char),
    ("event_queue_check_drag", c_char),
    ("event_queue_check_drag_handled", c_char),
    ("_pad0", c_char * 1),
    ("pie_event_type_lock", c_short),
    ("pie_event_type_last", c_short),
    # wmEvent
    ("eventstate", c_void_p),
    # wmEvent
    ("event_last_handled", c_void_p),
    # wmIMEData
    ("ime_data", c_void_p),
    ("event_queue", ListBase),
    ("handlers", ListBase),
    ("modalhandlers", ListBase),
    ("gesture", ListBase),
    # Stereo3dFormat
    ("stereo3d_format", c_void_p),
    ("drawcalls", ListBase),
    ("cursor_keymap_status", c_void_p),
]


# pylint: disable=W0201
class wmOperator(Structure):
    """Defined in $source/blender/makesdna/DNA_windowmanager_types.h"""


# pylint: disable=W0212
wmOperator._fields_ = [
    ("next", POINTER(wmOperator)),
    ("prev", POINTER(wmOperator)),
    ("idname", c_char * 64),
    # IDProperty
    ("properties", c_void_p),
    # wmOperatorType
    ("type", c_void_p),
    ("customdata", c_void_p),
    ("py_instance", c_void_p),
    # PointerRNA
    ("ptr", c_void_p),
    # ReportList
    ("reports", c_void_p),
    ("macro", ListBase),
    ("opm", POINTER(wmOperator)),
    # uiLayout
    ("layout", c_void_p),
    ("flag", c_short),
    ("_pad", c_char * 6),
]


# pylint: disable=W0201
class wmEventHandler(Structure):
    """Defined in $source/blender/windowmanager/wm_event_system.h"""


# pylint: disable=W0212
wmEventHandler._fields_ = [
    ("next", POINTER(wmEventHandler)),
    ("prev", POINTER(wmEventHandler)),
    # eWM_EventHandlerType
    ("type", c_int8),
    ("flag", c_char),
    # EventHandlerPoll
    ("poll", c_void_p),
    ("op", POINTER(wmOperator)),
]
