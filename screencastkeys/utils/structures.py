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


"""
>>> import ctypes
>>> blend_cdll = ctypes.CDLL('')
>>> # call function
>>> EDBM_vert_find_nearest_ex = blend_cdll.EDBM_vert_find_nearest_ex
>>> EDBM_vert_find_nearest_ex.restype = POINTER(BMVert)
>>> eve = EDBM_vert_find_nearest_ex(ctypes.byref(vc), ctypes.byref(dist), \
                                    ctypes.c_bool(1), use_cycle)
>>> # address -> function
>>> # WARNING! wrong code -> addr = ctypes.addressof(EDBM_vert_find_nearest_ex)
>>> addr = ctypes.cast(EDBM_vert_find_nearest_ex, ctypes.c_void_p).value
>>> functype = ctypes.CFUNCTYPE(POINTER(BMVert), POINTER(ViewContext),
                   POINTER(ctypes.c_float), ctypes.c_bool, ctypes.c_bool)
>>> func = functype(addr)
>>> eve = func(ctypes.byref(vc), ctypes.byref(dist), ctypes.c_bool(1), \
               use_cycle)
"""


import ctypes as ct
from ctypes import CDLL, Structure, Union, POINTER, addressof, cast, \
    c_bool, c_char, c_char_p, c_double, c_float, c_short, c_int, c_void_p, \
    py_object, c_ssize_t, c_uint, c_int8, c_uint8, CFUNCTYPE, byref, \
    sizeof, c_ubyte, cdll
from ctypes.util import find_library
import enum
import numpy as np
import platform
import re

import bpy


version = bpy.app.version


class c_void:
    pass


def fields(*field_items):
    """:rtype: list"""
    r_fields = []

    type = None
    for item in field_items:
        if isinstance(item, str):
            if type is None:
                raise ValueError('最初の要素は型でないといけない')
            m = re.match('(\**)(\w+)([\[\d\]]+)?$', item)  # 括弧は未対応
            if not m:
                raise ValueError('メンバ指定文字が間違ってる: {}'.format(item))
            ptr, name, num = m.groups()
            t = type
            if t is c_void:
                if ptr:
                    t = c_void_p
                    ptr = ptr[1:]
                else:
                    raise ValueError('c_voidを使う場合はポインタ表記必須')
            if ptr:
                for _ in range(len(ptr)):
                    t = POINTER(t)
            if num:
                # cとctypesでは逆になる
                for n in reversed(re.findall('\[(\d+)\]', num)):
                    t *= int(n)
            r_fields.append((name, t))
        else:
            type = item

    return r_fields


def set_fields(cls, *field_items):
    """'_fields_'のスペルミス多発の為"""
    cls._fields_ = fields(*field_items)


class Cast:
    @classmethod
    def cast(cls, obj, contents=True):
        if not obj:
            return None
        if isinstance(obj, int):
            addr = obj
        elif hasattr(obj, 'as_pointer'):
            addr = obj.as_pointer()
        else:
            addr = obj
        if contents:
            return ct.cast(addr, ct.POINTER(cls)).contents
        else:
            return ct.cast(addr, ct.POINTER(cls))

    def to_pointer(self):
        return cast(addressof(self), POINTER(self.__class__))

    def recast(self):
        return cast(addressof(self), POINTER(self.__class__)).contents


###############################################################################
# Python Header
###############################################################################
class PyObject_HEAD(ct.Structure):
    _fields_ = [
        # py_object, '_ob_next', '_ob_prev';  # When Py_TRACE_REFS is defined
        ('ob_refcnt', ct.c_ssize_t),
        ('ob_type', ct.c_void_p),
    ]

class PyObject_VAR_HEAD(ct.Structure):
    _fields_ = [
        # py_object, '_ob_next', '_ob_prev';  # When Py_TRACE_REFS is defined
        ('ob_refcnt', ct.c_ssize_t),
        ('ob_type', ct.c_void_p),
        ('ob_size', ct.c_ssize_t),
    ]


###############################################################################
# メモリ操作
###############################################################################
def _get_malloc_calloc_free():
    p = platform.platform().split('-')[0].lower()
    if p == 'linux':
        libc = CDLL(find_library('c'))
        malloc = libc.malloc
        malloc.restype = c_void_p
        calloc = libc.calloc
        calloc.restype = c_void_p
        free = libc.free
        free.argtypes = [c_void_p]
    elif p == 'windows':
        malloc = cdll.msvcrt.malloc
        malloc.restype = c_void_p
        calloc = cdll.msvcrt.calloc
        calloc.restype = c_void_p
        free = cdll.msvcrt.free
        free.argtypes = [c_void_p]
    else:  # 'darwin'
        malloc = calloc = free = None
    return malloc, calloc, free


malloc, calloc, free = _get_malloc_calloc_free()


class MemHead(Structure):
    _fields_ = [
        ('len', c_ssize_t),
    ]


def _SIZET_ALIGN_4(length):
    return (length + 3) // 4 * 4


def MEM_freeN(vmemh):
    """mallocn_lockfree_impl.c: 132: MEM_lockfree_freeN"""
    # TODO: 未完成


def MEM_callocN(length):
    """mallocn_lockfree_impl.c: 280: MEM_lockfree_callocN
    :type length: int
    :rtype: int
    """
    length = _SIZET_ALIGN_4(length)
    memh_p = calloc(1, length + sizeof(MemHead))
    if memh_p:
        memh = cast(memh_p, POINTER(MemHead)).contents
        memh.len = length
        # 以下の関数は再現不可
        # atomic_add_u(&totblock, 1);
        # atomic_add_z(&mem_in_use, len);
        # update_maximum(&peak_mem, mem_in_use);
        return memh_p + sizeof(MemHead)
    else:
        return None


def MEM_mallocN(length):
    """mallocn_lockfree_impl.c: 301: MEM_lockfree_mallocN
    :type length: int
    :rtype: int
    """
    length = _SIZET_ALIGN_4(length)
    memh_p = calloc(1, length + sizeof(MemHead))
    if memh_p:
        memh = cast(memh_p, POINTER(MemHead)).contents
        memh.len = length
        # 以下の関数は再現不可
        # atomic_add_u(&totblock, 1);
        # atomic_add_z(&mem_in_use, len);
        # update_maximum(&peak_mem, mem_in_use);
        return memh_p + sizeof(MemHead)
    else:
        return None


###############################################################################
# ListBase
###############################################################################
class Link(Structure):
    """source/blender/makesdna/DNA_listBase.h: 47"""

Link._fields_ = fields(
    Link, '*next', '*prev',
)


class ListBase(Structure):
    """source/blender/makesdna/DNA_listBase.h: 59"""
    _fields_ = fields(
        c_void_p, 'first', 'last',
    )

    def __len__(self):
        link_p = cast(self.first, POINTER(Link))
        i = 0
        while link_p:
            i += 1
            link_p = link_p.contents.next
        return i

    def to_list(self, link_type=None):
        """各要素のcontentsからなるlistを返す"""
        elems = []
        ptr = cast(self.first, POINTER(Link))
        while ptr:
            link = ptr.contents
            if link_type is not None:
                elems.append(cast(ptr, POINTER(link_type)).contents)
            else:
                elems.append(link)
            ptr = link.next
        return elems

    def remove(self, vlink):
        """
        void BLI_remlink(ListBase *listbase, void *vlink)
        {
            Link *link = vlink;

            if (link == NULL) return;

            if (link->next) link->next->prev = link->prev;
            if (link->prev) link->prev->next = link->next;

            if (listbase->last == link) listbase->last = link->prev;
            if (listbase->first == link) listbase->first = link->next;
        }
        """
        if vlink:
            link = cast(addressof(vlink), POINTER(Link)).contents
        else:
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
        """
        void *BLI_findlink(const ListBase *listbase, int number)
        {
            Link *link = NULL;

            if (number >= 0) {
                link = listbase->first;
                while (link != NULL && number != 0) {
                    number--;
                    link = link->next;
                }
            }

            return link;
        }
        """
        link_p = None
        if number >= 0:
            link_p = cast(self.first, POINTER(Link))
            while link_p and number != 0:
                number -= 1
                link_p = link_p.contents.next
        return link_p.contents if link_p else None

    def insert_after(self, vprevlink, vnewlink):
        """
        void BLI_insertlinkafter(ListBase *listbase, void *vprevlink, void *vnewlink)
        {
            Link *prevlink = vprevlink;
            Link *newlink = vnewlink;

            /* newlink before nextlink */
            if (newlink == NULL) return;

            /* empty list */
            if (listbase->first == NULL) {
                listbase->first = newlink;
                listbase->last = newlink;
                return;
            }

            /* insert at head of list */
            if (prevlink == NULL) {
                newlink->prev = NULL;
                newlink->next = listbase->first;
                newlink->next->prev = newlink;
                listbase->first = newlink;
                return;
            }

            /* at end of list */
            if (listbase->last == prevlink) {
                listbase->last = newlink;
            }

            newlink->next = prevlink->next;
            newlink->prev = prevlink;
            prevlink->next = newlink;
            if (newlink->next) {
                newlink->next->prev = newlink;
            }
        }
        """
        if vprevlink:
            prevlink = cast(addressof(vprevlink),
                            POINTER(Link)).contents
        else:
            prevlink = None
        if vnewlink:
            newlink = cast(addressof(vnewlink),
                           POINTER(Link)).contents
        else:
            newlink = None

        if not newlink:
            return

        def gen_ptr(link):
            if isinstance(link, (int, type(None))):
                return cast(link, POINTER(Link))
            else:
                return ct.pointer(link)

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
            newlink.next.contents.prev = gen_ptr(newlink)

    def insert(self, i, vlink):
        if i < 0:
            i = len(self) - i
        self.insert_after(self.find(i - 1), vlink)

    def append(self, vlink):
        self.insert_after(self.find(len(self) - 1), vlink)

    def find_string(self, identifier, offset):
        """
        void *BLI_findstring(const ListBase *listbase, const char *id, const int offset)
        {
            Link *link = NULL;
            const char *id_iter;

            for (link = listbase->first; link; link = link->next) {
                id_iter = ((const char *)link) + offset;

                if (id[0] == id_iter[0] && STREQ(id, id_iter)) {
                    return link;
                }
            }

            return NULL;
        }

        :type identifier: bytes
        :type offset: int
        :rtype: int | None
        """
        link_p = cast(self.first, POINTER(Link))
        while link_p:
            link_addr = addressof(link_p.contents)
            id_iter = cast(link_addr + offset, c_char_p).value
            if identifier == id_iter:
                return link_addr
            link_p = link_p.contents.next
        return None

    def test(self):
        link1 = Link()
        link2 = Link()
        self.insert_after(None, link1)
        # self.insert_after(link1, link2)
        self.insert(1, link2)
        def eq(a, b):
            return addressof(a) == addressof(b)
        assert (self.first == addressof(link1))
        assert (self.last == addressof(link2))
        assert (eq(link1.next.contents, link2))
        assert (eq(link2.prev.contents, link1))
        assert (eq(link1.next.contents.prev.contents, link1))
        assert (eq(link2.prev.contents.next.contents, link2))

        self.remove(link2)
        assert(self.last == addressof(link1))
        assert(not link1.next)


###############################################################################
# PropertyRNA
###############################################################################
class _PointerRNA_id(Structure):
    """makesrna/RNA_types.h"""
    _fields_ = fields(
        c_void_p, 'data',
    )


class PointerRNA(Cast, Structure):
    """makesrna/RNA_types.h"""
    _fields_ = fields(
        _PointerRNA_id, 'id',
        c_void_p, 'type',  # <StructRNA> &RNA_Operator 等の値
        c_void_p, 'data',
    )


RNA_MAX_ARRAY_DIMENSION = 3  # rna_internal_types.h: 54


class PropertyRNA(Structure):
    """rna_internal_types.h: 155"""

PropertyRNA._fields_ = fields(
    PropertyRNA, '*next', '*prev',

    # magic bytes to distinguish with IDProperty
    c_int, 'magic',

    # unique identifier
    # c_char, '*identifier',  # <const char>
    c_char_p, 'identifier',
    # various options
    c_int, 'flag',

    # user readable name
    c_char, '*name',  # <const char>
    # single line description, displayed in the tooltip for example
    c_char, '*description',  # <const char>
    # icon ID
    c_int, 'icon',
    # context for translation
    c_char, '*translation_context',  # <const char>

    # property type as it appears to the outside
    c_int, 'type',  # <enum: PropertyType>
    # subtype, 'interpretation' of the property
    c_int, 'subtype',  # <enum: PropertySubType>
    # if non-NULL, overrides arraylength. Must not return 0?
    c_void_p, 'getlength',  # <PropArrayLengthGetFunc>
    # dimension of array
    c_uint, 'arraydimension',  # <unsigned int>
    # array lengths lengths for all dimensions (when arraydimension > 0)
    c_uint, 'arraylength[3]',
    # <unsigned int> arraylength[RNA_MAX_ARRAY_DIMENSION]
    c_uint, 'totarraylength',  # <unsigned int>

    # callback for updates on change
    c_void_p, 'update',  # <UpdateFunc>
    c_int, 'noteflag',

    # callback for testing if editable
    c_void_p, 'editable',  # <EditableFunc>
    # callback for testing if array-item editable (if applicable)
    c_void_p, 'itemeditable',  # <ItemEditableFunc>

    # raw access
    c_int, 'rawoffset',
    c_int, 'rawtype',  # <enum: RawPropertyType>

    # This is used for accessing props/functions of this property
    # any property can have this but should only be used for collections and arrays
    # since python will convert int/bool/pointer's
    c_void, '*srna',
    # <StructRNA>  # attributes attached directly to this collection

    # python handle to hold all callbacks
    # * (in a pointer array at the moment, may later be a tuple)
    c_void, '*py_data',
)


class FloatPropertyRNA(Structure):
    """rna_internal_types.h: 252"""

PropFloatGetFunc = CFUNCTYPE(c_float, POINTER(PointerRNA))
PropFloatSetFunc = CFUNCTYPE(c_int, POINTER(PointerRNA), c_float)
PropFloatArrayGetFunc = CFUNCTYPE(c_int, POINTER(PointerRNA),
                                  POINTER(c_float))
PropFloatArraySetFunc = CFUNCTYPE(c_int, POINTER(PointerRNA),
                                  POINTER(c_float))
PropFloatRangeFunc = CFUNCTYPE(c_int, POINTER(PointerRNA),
                               c_float, c_float, c_float, c_float)

FloatPropertyRNA._fields_ = fields(
    PropertyRNA, 'property',

    PropFloatGetFunc, 'get',
    PropFloatSetFunc, 'set',
    PropFloatArrayGetFunc, 'getarray',
    PropFloatArraySetFunc, 'setarray',
    PropFloatRangeFunc, 'range',

    # PropFloatGetFuncEx, 'get_ex',
    # PropFloatSetFuncEx, 'set_ex',
    # PropFloatArrayGetFuncEx, 'getarray_ex',
    # PropFloatArraySetFuncEx, 'setarray_ex',
    # PropFloatRangeFuncEx, 'range_ex',
    #
    # c_float, 'softmin', 'softmax',
    # c_float, 'hardmin', 'hardmax',
    # c_float, 'step',
    # c_int, 'precision',
    #
    # c_float, 'defaultvalue',
    # c_float, '*defaultarray',   # <cost float>
)


class BPy_StructRNA(Cast, Structure):
    """python/intern/bpy_rna.h"""
    _fields_ = fields(
        PyObject_HEAD, 'head',
        PointerRNA, 'ptr',
    )


class BPy_PropertyRNA(Structure):
    """python/intern/bpy_rna.h"""
    _fields_ = fields(
        PyObject_HEAD, 'head',
        PointerRNA, 'ptr',
        PropertyRNA, '*prop',
    )


class BPy_PropertyArrayRNA(Cast, Structure):
    """python/intern/bpy_rna.h"""
    _fields_ = fields(
        PyObject_HEAD, 'head',
        PointerRNA, 'ptr',
        PropertyRNA, '*prop',
        c_int, 'arraydim',
        c_int, 'arrayoffset',
    )


def RNA_property_float_get_array(ptr, prop, values):
    """
    :param ptr: PointerRNA *ptr
    :type ptr: POINTER(PointerRNA)
    :param prop: PropertyRNA *prop
    :type prop: POINTER(PropertyRNA)
    :param values: float *values
    :type values: POINTER(c_float)
    """
    fprop = cast(prop, POINTER(FloatPropertyRNA)).contents
    fprop.getarray(ptr, cast(values, POINTER(c_float)))


def RNA_property_float_set_array(ptr, prop, values):
    """
    :param ptr: PointerRNA *ptr
    :type ptr: POINTER(PointerRNA)
    :param prop: PropertyRNA *prop
    :type prop: POINTER(PropertyRNA)
    :param values: float *values
    :type values: POINTER(c_float)
    """
    fprop = cast(prop, POINTER(FloatPropertyRNA)).contents
    fprop.setarray(ptr, cast(values, POINTER(c_float)))


###############################################################################
# StructRNA
###############################################################################
class ContainerRNA(Structure):
    """rna_internal_types.h"""
    _fields_ = fields(
        c_void_p, 'next', 'prev',
        c_void_p, 'prophash',  # struct GHash *prophash
        ListBase, 'properties',
    )


RNA_MAX_ARRAY_DIMENSION = 3


class StructRNA(Structure):
    """rna_internal_types.h

    bl_rna = bpy.types.VIEW3D_OT_cursor3d.bl_ran
    addr = bl_rna.as_pointer()
    srna = ct.cast(addr, ct.POINTER(structures.StructRNA)).contents
    """

StructRNA._fields_ = fields(
    ContainerRNA, 'cont',

    c_char_p, 'identifier',

    c_void_p, 'py_type',
    c_void_p, 'blender_type',

    c_int, 'flag',

    c_char_p, 'name',
    c_char_p, 'description',
    c_char_p, 'translation_context',
    c_int, 'icon',

    PropertyRNA, '*nameproperty',

    PropertyRNA, '*iteratorproperty',

    StructRNA, '*base',

    StructRNA, '*nested',

    c_void_p, 'refine',

    c_void_p, 'path',

    c_void_p, 'reg',  # StructRegisterFunc
    c_void_p, 'unreg',  # StructUnregisterFunc
    c_void_p, 'instance',  # StructInstanceFunc

    c_void_p, 'idproperties',  # IDPropertiesFunc

    ListBase, 'functions',
)


class ExtensionRNA(Structure):
    _fields_ = fields(
        c_void, '*data',
        StructRNA, '*srna',
        c_void_p,'call',  # <StructCallbackFunc>
        c_void_p,'free'  # <StructFreeFunc>
    )


class FunctionRNA(Structure):
    """rna_internal_types.h: 135

    func = bpy.types.UILayout.bl_rna.functions['label']
    function_rna = ct.cast(func.as_pointer(), ct.POINTER(st.FunctionRNA)).contents

    UILayout.label()を取得する場合:
    コンパイル時のrna_ui_gen.cのUILayout_label_callとか参照
    uiLayout *_self = ptr->data
    char *_data = _parms->data
    # ↓_dataの中身
    # text, text_ctxt, translate, icon, icon_value
    # 8, 8, 4, 4, 4, (char *, char *, int, int, int)

    ptr = PointerRNA()
    ptr.data = layout.as_pointer()
    params = ParameterList()
    data = c_char * (8 + 8 + 4 + 4 + 4)

    function_rna.call(context.as_pointer(), None, ct.byref(ptr), ct.byref(params))

    """
    _fields_ = fields(
        ContainerRNA, 'cont',
        c_char_p, 'identifier',
        c_int, 'flag',
        c_char_p, 'description',
        # typedef void (*CallFunc)(struct bContext *C, struct ReportList *reports, PointerRNA *ptr, ParameterList *parms);
        CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p, c_void_p), 'call',
        PropertyRNA, '*c_ret'
    )


class ParameterList(Structure):
    _fields_ = fields(
        # storage for parameters
        c_void, '*data',

        # function passed at creation time
        FunctionRNA, '*func',

        # store the parameter size
        c_int, 'alloc_size',

        c_int, 'arg_count', 'ret_count'
    )


###############################################################################
# blenkernel / makesdna / windowmanager/ editors
###############################################################################
class ID(Structure):
    """DNA_ID.h"""

ID._fields_ = fields(
    c_void_p, 'next', 'prev',
    ID, '*newid',
    c_void_p, 'lib',  # <struct Library>
    c_char, 'name[66]',  # MAX_ID_NAME
    c_short, 'flag',
    c_int, 'us',
    c_int, 'icon_id', 'pad2',
    c_void_p, 'properties',  # <IDProperty>
)


class rcti(Structure):
    """DNA_vec_types.h: 86
    NOTE: region.width == ar.winrct.xmax - ar.winrct.xmin + 1
    """
    _fields_ = fields(
        c_int, 'xmin', 'xmax',
        c_int, 'ymin', 'ymax',
    )


class rctf(Structure):
    """DNA_vec_types.h: 92"""
    _fields_ = fields(
        c_float, 'xmin', 'xmax',
        c_float, 'ymin', 'ymax',
    )


"""
typedef struct UserDef {
    /* UserDef has separate do-version handling, and can be read from other files */
    int versionfile, subversionfile',

    int flag, dupflag',
    int savetime',
    char tempdir[768]',    /* FILE_MAXDIR length */
    char fontdir[768]',
    char renderdir[1024]', /* FILE_MAX length */
    /* EXR cache path */
    char render_cachedir[768]',  /* 768 = FILE_MAXDIR */
    char textudir[768]',
    char pythondir[768]',
    char sounddir[768]',
    char i18ndir[768]',
    char image_editor[1024]',    /* 1024 = FILE_MAX */
    char anim_player[1024]',        /* 1024 = FILE_MAX */
    int anim_player_preset',

    short v2d_min_gridsize',        /* minimum spacing between gridlines in View2D grids */
    short timecode_style',        /* style of timecode display */

    short versions',
    short dbl_click_time',

    short gameflags',
    short wheellinescroll',
    int uiflag, uiflag2',
    int language',
    short userpref, viewzoom',

    int mixbufsize',
    int audiodevice',
    int audiorate',
    int audioformat',
    int audiochannels',

    int scrollback',    /* console scrollback limit */
    int dpi',           /* range 48-128? */
    float ui_scale',     /* interface scale */
    int pad1',
    char node_margin',  /* node insert offset (aka auto-offset) margin, but might be useful for later stuff as well */
    char pad2',
    short transopts',
    short menuthreshold1, menuthreshold2',

    struct ListBase themes',
    struct ListBase uifonts',
    struct ListBase uistyles',
    struct ListBase keymaps  DNA_DEPRECATED', /* deprecated in favor of user_keymaps */
    struct ListBase user_keymaps',
    struct ListBase addons',
    struct ListBase autoexec_paths',
    char keyconfigstr[64]',

    short undosteps',
    short undomemory',
    short gp_manhattendist, gp_euclideandist, gp_eraser',
    short gp_settings',
    short tb_leftmouse, tb_rightmouse',
    struct SolidLight light[3]',
    short tw_hotspot, tw_flag, tw_handlesize, tw_size',
    short textimeout, texcollectrate',
    short wmdrawmethod', /* removed wmpad */
    short dragthreshold',
    int memcachelimit',
    int prefetchframes',
    float pad_rot_angle', /* control the rotation step of the view when PAD2, PAD4, PAD6&PAD8 is use */
    short frameserverport',
    short pad4',
    short obcenter_dia',
    short rvisize',            /* rotating view icon size */
    short rvibright',        /* rotating view icon brightness */
    short recent_files',        /* maximum number of recently used files to remember  */
    short smooth_viewtx',    /* miliseconds to spend spinning the view */
    short glreslimit',
    short curssize',
    short color_picker_type',
    char  ipo_new',            /* interpolation mode for newly added F-Curves */
    char  keyhandles_new',    /* handle types for newly added keyframes */
    char  gpu_select_method',
    char  view_frame_type',

    int view_frame_keyframes', /* number of keyframes to zoom around current frame */
    float view_frame_seconds', /* seconds to zoom around current frame */

    short scrcastfps',        /* frame rate for screencast to be played back */
    short scrcastwait',        /* milliseconds between screencast snapshots */

    short widget_unit',        /* private, defaults to 20 for 72 DPI setting */
"""

class View2D(Structure):
    """DNA_view2d_types.h: 40"""

View2D._fields_ = fields(
    rctf, 'tot', 'cur',  # tot - area that data can be drawn in cur - region of tot that is visible in viewport
    rcti, 'vert', 'hor',  # vert - vertical scrollbar region hor - horizontal scrollbar region
    rcti, 'mask',  # region (in screenspace) within which 'cur' can be viewed

    c_float, 'min[2]', 'max[2]',  # min/max sizes of 'cur' rect (only when keepzoom not set)
    c_float, 'minzoom', 'maxzoom',  # allowable zoom factor range (only when (keepzoom & V2D_LIMITZOOM)) is set

    c_short, 'scroll',  # scroll - scrollbars to display (bitflag)
    c_short, 'scroll_ui',  # scroll_ui - temp settings used for UI drawing of scrollers

    c_short, 'keeptot',  # keeptot - 'cur' rect cannot move outside the 'tot' rect?
    c_short, 'keepzoom',  # keepzoom - axes that zooming cannot occur on, and also clamp within zoom-limits
    c_short, 'keepofs',  # keepofs - axes that translation is not allowed to occur on

    c_short, 'flag',  # settings
    c_short, 'align',  # alignment of content in totrect

    c_short, 'winx', 'winy',  # storage of current winx/winy values, set in UI_view2d_size_update
    c_short, 'oldwinx', 'oldwiny',  # storage of previous winx/winy values encountered by UI_view2d_curRect_validate(), for keepaspect

    c_short, 'around',  # pivot point for transforms (rotate and scale)

    c_float, '*tab_offset',  # different offset per tab, for buttons
    c_int, 'tab_num',  # number of tabs stored
    c_int, 'tab_cur',  # current tab

    # animated smooth view
    c_void_p, 'sms',  # struct SmoothView2DStore
    c_void_p, 'smooth_timer',  # struct wmTimer
)


# DNA_space_types.h: 1350: typedef enum eSpace_Type
# SpaceType.spaceid
class eSpace_Type(enum.IntEnum):
    SPACE_EMPTY = 0
    SPACE_VIEW3D = 1
    SPACE_IPO = 2
    SPACE_OUTLINER = 3
    SPACE_BUTS = 4
    SPACE_FILE = 5
    SPACE_IMAGE = 6
    SPACE_INFO = 7
    SPACE_SEQ = 8
    SPACE_TEXT = 9
    # ifdef DNA_DEPRECATED
    SPACE_IMASEL = 10  # deprecated
    SPACE_SOUND = 11  # Deprecated
    # endif
    SPACE_ACTION = 12
    SPACE_NLA = 13
    # TO DO: fully deprecate
    SPACE_SCRIPT = 14  # Deprecated
    SPACE_TIME = 15
    SPACE_NODE = 16
    SPACE_LOGIC = 17
    SPACE_CONSOLE = 18
    SPACE_USERPREF = 19
    SPACE_CLIP = 20
    SPACEICONMAX = SPACE_CLIP


class RNAEnumSpaceTypeItems(enum.IntEnum):
    """EnumPropertyItem rna_enum_space_type_items
    bpy.types.Area.typeで使われる名前と値
    """
    EMPTY = eSpace_Type.SPACE_EMPTY
    VIEW_3D = eSpace_Type.SPACE_VIEW3D
    TIMELINE = eSpace_Type.SPACE_TIME
    GRAPH_EDITOR = eSpace_Type.SPACE_IPO
    DOPESHEET_EDITOR = eSpace_Type.SPACE_ACTION
    NLA_EDITOR = eSpace_Type.SPACE_NLA
    IMAGE_EDITOR = eSpace_Type.SPACE_IMAGE
    SEQUENCE_EDITOR = eSpace_Type.SPACE_SEQ
    CLIP_EDITOR = eSpace_Type.SPACE_CLIP
    TEXT_EDITOR = eSpace_Type.SPACE_TEXT
    NODE_EDITOR = eSpace_Type.SPACE_NODE
    LOGIC_EDITOR = eSpace_Type.SPACE_LOGIC
    PROPERTIES = eSpace_Type.SPACE_BUTS
    OUTLINER = eSpace_Type.SPACE_OUTLINER
    USER_PREFERENCES = eSpace_Type.SPACE_USERPREF
    INFO = eSpace_Type.SPACE_INFO
    FILE_BROWSER = eSpace_Type.SPACE_FILE
    CONSOLE = eSpace_Type.SPACE_CONSOLE


# DNA_screen_types.h: 376:
class eRegion_Type(enum.IntEnum):
    RGN_TYPE_WINDOW = 0
    RGN_TYPE_HEADER = 1
    RGN_TYPE_CHANNELS = 2
    RGN_TYPE_TEMPORARY = 3
    RGN_TYPE_UI = 4
    RGN_TYPE_TOOLS = 5
    RGN_TYPE_TOOL_PROPS = 6
    RGN_TYPE_PREVIEW = 7


class RNAEnumRegionTypeItems(enum.IntEnum):
    """EnumPropertyItem rna_enum_region_type_items
    """
    WINDOW = eRegion_Type.RGN_TYPE_WINDOW
    HEADER = eRegion_Type.RGN_TYPE_HEADER
    CHANNELS = eRegion_Type.RGN_TYPE_CHANNELS
    TEMPORARY = eRegion_Type.RGN_TYPE_TEMPORARY
    UI = eRegion_Type.RGN_TYPE_UI
    TOOLS = eRegion_Type.RGN_TYPE_TOOLS
    TOOL_PROPS = eRegion_Type.RGN_TYPE_TOOL_PROPS
    PREVIEW = eRegion_Type.RGN_TYPE_PREVIEW


class ARegionType(Structure):
    """BKE_screen.h: 116"""

ARegionType._fields_ = fields(
    ARegionType, '*next', '*prev',

    c_int, 'regionid',  # unique identifier within this space, defines RGN_TYPE_xxxx

    # add handlers, stuff you only do once or on area/region type/size changes
    c_void_p, 'init',
    # exit is called when the region is hidden or removed
    c_void_p, 'exit',
    # draw entirely, view changes should be handled here
    c_void_p, 'draw',
    # contextual changes should be handled here
    c_void_p, 'listener',

    c_void_p, 'free',

    # split region, copy data optionally
    c_void_p, 'duplicate',

    # register operator types on startup
    c_void_p, 'operatortypes',
    # add own items to keymap
    c_void_p, 'keymap',
    # allows default cursor per region
    c_void_p, 'cursor',

    # return context data
    c_void_p, 'context',

    # custom drawing callbacks
    ListBase, 'drawcalls',

    # panels type definitions
    ListBase, 'paneltypes',

    # header type definitions
    ListBase, 'headertypes',

    # hardcoded constraints, smaller than these values region is not visible
    c_int, 'minsizex', 'minsizey',
    # when new region opens (region prefsizex/y are zero then
    c_int, 'prefsizex', 'prefsizey',
    # default keymaps to add
    c_int, 'keymapflag',
    # return without drawing. lock is set by region definition, and copied to do_lock by render. can become flag
    c_short, 'do_lock', 'lock',
    # call cursor function on each move event
    c_short, 'event_cursor',
)


BKE_ST_MAXNAME = 64


class PanelType(Cast, Structure):
    """BKE_screen.h: 173"""

PanelType._fields_ = fields(
    PanelType, '*next', '*prev',

    c_char * BKE_ST_MAXNAME, 'idname',  # unique name
    c_char * BKE_ST_MAXNAME, 'label',  # for panel header
    c_char * BKE_ST_MAXNAME, 'translation_context',
    c_char * BKE_ST_MAXNAME, 'context',  # for buttons window
    c_char * BKE_ST_MAXNAME, 'category',  # for category tabs
    c_int, 'space_type',
    c_int, 'region_type',

    c_int, 'flag',

    # verify if the panel should draw or not
    # int (*poll)(const struct bContext *, struct PanelType *);
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'poll',
    # draw header (optional)
    # void (*draw_header)(const struct bContext *, struct Panel *);
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'draw_header',
    # draw entirely, view changes should be handled here
    # void (*draw)(const struct bContext *, struct Panel *);
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'draw',

    ExtensionRNA, 'ext',
)


class Panel(Cast, Structure):
    """DNA_screen_types.h: 96"""

Panel._fields_ = fields(
    Panel, '*next', '*prev',

    PanelType, '*type',
    c_void, '*layout',  # uiLayout

    c_char, 'panelname[64]', 'tabname[64]',
    c_char, 'drawname[64]',
    c_int, 'ofsx', 'ofsy', 'sizex', 'sizey',
    c_short, 'labelofs', 'pad',
    c_short, 'flag', 'runtime_flag',
    c_short, 'control',
    c_short, 'snap',
    c_int, 'sortorder',  # panels are aligned according to increasing sortorder
    Panel, '*paneltab',  # this panel is tabbed in *paneltab
    c_void, '*activedata',  # runtime for panel manipulation
)


class PanelCategoryDyn(Structure):
    """DNA_screen_types.h: 131"""

PanelCategoryDyn._fields_ = fields(
    PanelCategoryDyn, '*next', '*prev',
    c_char, 'idname[64]',
    rcti, 'rect'
)


# region stack of active tabs
class PanelCategoryStack(Structure):
    """DNA_screen_types.h: 137"""

PanelCategoryStack._fields_ = fields(
    PanelCategoryStack, '*next', '*prev',
    c_char, 'idname[64]'
)


class SpaceType(Structure):
    """BKE_screen.h: 66"""

SpaceType._fields_ = fields(
    SpaceType, '*next', '*prev',

    c_char * BKE_ST_MAXNAME, 'name',  # for menus
    c_int, 'spaceid',  # unique space identifier
    c_int, 'iconid',  # icon lookup for menus

    # initial allocation, after this WM will call init() too
    # struct SpaceLink    *(*new)(const struct bContext *C)
    c_char_p, 'new',
    # not free spacelink itself
    # void (*free)(struct SpaceLink *)
    c_void_p, 'free',

    # init is to cope with file load, screen (size) changes, check handlers
    # void (*init)(struct wmWindowManager *, struct ScrArea *)
    c_void_p, 'init',
    # exit is called when the area is hidden or removed
    # void (*exit)(struct wmWindowManager *, struct ScrArea *)
    c_void_p, 'exit',
    # Listeners can react to bContext changes
    # void (*listener)(struct bScreen *sc, struct ScrArea *, struct wmNotifier *)
    c_void_p, 'listener',

    # refresh context, called after filereads, ED_area_tag_refresh()
    # void (*refresh)(const struct bContext *, struct ScrArea *)
    c_void_p, 'refresh',

    # after a spacedata copy, an init should result in exact same situation
    # struct SpaceLink    *(*duplicate)(struct SpaceLink *)
    c_void_p, 'duplicate',

    # register operator types on startup
    # void (*operatortypes)(void)
    c_void_p, 'operatortypes',
    # add default items to WM keymap
    # void (*keymap)(struct wmKeyConfig *)
    c_void_p, 'keymap',
    # on startup, define dropboxes for spacetype+regions
    # void (*dropboxes)(void)
    c_void_p, 'dropboxes',

    # return context data
    # int (*context)(const struct bContext *, const char *, struct bContextDataResult *)
    c_void_p, 'context',

    # Used when we want to replace an ID by another (or NULL).
    # void (*id_remap)(struct ScrArea *, struct SpaceLink *, struct ID *, struct ID *);
    c_void_p, 'id_remap',

    # region type definitions
    ListBase, 'regiontypes',

    # tool shelf definitions
    ListBase, 'toolshelf',

    # read and write...

    # default keymaps to add
    c_int, 'keymapflag'
)


class bScreen(Cast, Structure):
    """DNA_screen_types.h: 48"""

bScreen._fields_ = fields(
    ID, 'id',

    ListBase, 'vertbase',
    ListBase, 'edgebase',
    ListBase, 'areabase',
    ListBase, 'regionbase',

    c_void_p, '*scene',
)


class ScrArea(Cast, Structure):
    """DNA_screen_types.h: 202"""

ScrArea._fields_ = fields(
    ScrArea, '*next', '*prev',

    c_void_p, 'v1', 'v2', 'v3', 'v4',  # ordered (bl, tl, tr, br)

    c_void_p, 'full',  # <bScreen> if area==full, this is the parent

    rcti, 'totrct',  # rect bound by v1 v2 v3 v4

    c_char, 'spacetype', 'butspacetype',  # SPACE_..., butspacetype is button arg
    c_short, 'winx', 'winy',  # size

    c_short, 'headertype',  # OLD! 0=no header, 1= down, 2= up
    c_short, 'do_refresh',  # private, for spacetype refresh callback
    c_short, 'flag',
    c_short, 'region_active_win',  # index of last used region of 'RGN_TYPE_WINDOW'
                                   # runtime variable, updated by executing operators
    c_char, 'temp', 'pad',

    SpaceType, '*type',  # callbacks for this space type

    ListBase, 'spacedata',  # SpaceLink
    ListBase, 'regionbase',  # ARegion
    ListBase, 'handlers',  # wmEventHandler

    ListBase, 'actionzones',  # AZone
)


class ARegion(Cast, Structure):
    """DNA_screen_types.h: 229"""

ARegion._fields_ = fields(
    ARegion, '*next', '*prev',

    View2D, 'v2d',  # 2D-View scrolling/zoom info (most regions are 2d anyways)
    rcti, 'winrct',  # coordinates of region
    rcti, 'drawrct',  # runtime for partial redraw, same or smaller than winrct
    c_short, 'winx', 'winy',  # size

    c_short, 'swinid',
    c_short, 'regiontype',  # window, header, etc. identifier for drawing
    c_short, 'alignment',  # how it should split
    c_short, 'flag',  # hide, ...

    c_float, 'fsize',  # current split size in float (unused)
    c_short, 'sizex', 'sizey',  # current split size in pixels (if zero it uses regiontype)

    c_short, 'do_draw',  # private, cached notifier events
    c_short, 'do_draw_overlay',  # private, cached notifier events
    c_short, 'swap',  # private, indicator to survive swap-exchange
    c_short, 'overlap',  # private, set for indicate drawing overlapped
    c_short, 'flagfullscreen',  # temporary copy of flag settings for clean fullscreen
    c_short, 'pad',

    ARegionType, '*type',  # callbacks for this region type

    ListBase, 'uiblocks',  # uiBlock
    ListBase, 'panels',  # Panel
    ListBase, 'panels_category_active',  # Stack of panel categories
    ListBase, 'ui_lists',  # uiList
    ListBase, 'ui_previews',  # uiPreview
    ListBase, 'handlers',  # wmEventHandler
    ListBase, 'panels_category',  # Panel categories runtime

    c_void_p, 'regiontimer',  # <struct wmTimer>  # blend in/out

    c_char_p, 'headerstr',  # use this string to draw info  最大:UI_MAX_DRAW_STR:400
    c_void_p, 'regiondata',  # XXX 2.50, need spacedata equivalent?
)


#未使用
UI_MAX_DRAW_STR = 400  # UI_interface.h
UI_MAX_NAME_STR = 128
UI_MAX_SHORTCUT_STR = 16

class uiBlock(Structure):
    """interface_intern.h: 355"""

uiBlock._fields_ = fields(
    uiBlock, '*next', '*prev',

    ListBase, 'buttons',
    Panel, '*panel',
    uiBlock, '*oldblock',

    ListBase, 'butstore',  # UI_butstore_* runtime function

    ListBase, 'layouts',
    c_void, '*curlayout',  # struct uiLayout

    ListBase, 'contexts',

    c_char * UI_MAX_NAME_STR, 'name',

    c_float, 'winmat[4][4]',

    rctf, 'rect',
    c_float, 'aspect',

    c_uint, 'puphash',  # popup menu hash for memory

    c_void_p, 'func',  # uiButHandleFunc
    c_void, '*func_arg1',
    c_void, '*func_arg2',

    c_void_p, 'funcN',  # uiButHandleNFunc
    c_void, '*func_argN',

    c_void_p, 'butm_func',  # uiMenuHandleFunc
    c_void, '*butm_func_arg',

    c_void_p, 'handle_func',  # uiBlockHandleFunc
    c_void, '*handle_func_arg',

    # custom extra handling
    # int (*block_event_func)(const struct bContext *C, struct uiBlock *, const struct wmEvent *)
    c_void, '*block_event_func',

    # extra draw function for custom blocks
    # void (*drawextra)(const struct bContext *C, void *idv, void *arg1, void *arg2, rcti *rect);
    c_void, '*drawextra',
    c_void, '*drawextra_arg1',
    c_void, '*drawextra_arg2',

    c_int, 'flag',
    c_short, 'alignnr',

    c_char, 'direction',
    c_char, 'dt',  # drawtype: UI_EMBOSS, UI_EMBOSS_NONE ... etc, copied to buttons
    c_bool, 'auto_open',
    c_char, '_pad[7]',
    c_double, 'auto_open_last',

    c_char_p, 'lockstr',

    c_char, 'lock',
    c_uint8, 'active',  # c_char # to keep blocks while drawing and free them afterwards
    c_char, 'tooltipdisabled',  # to avoid tooltip after click
    c_char, 'endblock',  # UI_block_end done?

    c_int, 'bounds_type',  # enum eBlockBoundsCalc
    c_int, 'mx', 'my',
    c_int, 'bounds', 'minbounds',
)
#
#
# class SpaceLink(Structure):
#     """DNA_space_types.h: 78"""
#
# SpaceLink._fields_ = fields(
#     SpaceLink, '*next', '*prev',
#     ListBase, 'regionbase',  # storage of regions for inactive spaces
#     c_int, 'spacetype',
#     c_float, 'blockscale',  # DNA_DEPRECATED       XXX make deprecated
#     c_short, 'blockhandler[8]',  # DNA_DEPRECATED  XXX make deprecated
# )
#
#
# class SpaceButs(Cast, Structure):
#     """DNA_space_types.h: 114"""
#
# SpaceButs._fields_ = fields(
#     SpaceLink, '*next', '*prev',
#     ListBase, 'regionbase',  # storage of regions for inactive spaces
#     c_int, 'spacetype',
#     c_float, 'blockscale',  # DNA_DEPRECATED
#
#     c_short, 'blockhandler[8]',  # DNA_DEPRECATED
#
#     View2D, 'v2d',  # DNA_DEPRECATE  deprecated, copied to region
#
#     c_short, 'mainb', 'mainbo', 'mainbuser',  # context tabs
#     c_short, 're_align', 'align',          # align for panels
#     c_short, 'preview',                  # preview is signal to refresh
#     # texture context selector (material, lamp, particles, world, other)
#     c_short, 'texture_context', 'texture_context_prev',
#     c_char, 'flag', 'pad[7]',
#
#     c_void, '*path',                     # runtime
#     c_int, 'pathflag', 'dataicon',         # runtime
#     ID, '*pinid',
#
#     c_void, '*texuser',
# )


class RegionView3D(Cast, Structure):
    """DNA_view3d_types.h: 86"""

RegionView3D._fields_ = fields(
    c_float, 'winmat[4][4]',  # GL_PROJECTION matrix
    c_float, 'viewmat[4][4]',  # GL_MODELVIEW matrix
    c_float, 'viewinv[4][4]',  # inverse of viewmat
    c_float, 'persmat[4][4]',  # viewmat*winmat
    c_float, 'persinv[4][4]',  # inverse of persmat
    c_float, 'viewcamtexcofac[4]',  # offset/scale for camera glsl texcoords

    # viewmat/persmat multiplied with object matrix, while drawing and selection
    c_float, 'viewmatob[4][4]',
    c_float, 'persmatob[4][4]',

    # user defined clipping planes
    c_float, 'clip[6][4]',
    c_float, 'clip_local[6][4]',  # clip in object space, means we can test for clipping in editmode without first going into worldspace
    c_void_p, 'clipbb',  # struct BoundBox

    RegionView3D, '*localvd',  # allocated backup of its self while in localview
    c_void_p, 'render_engine',  # struct RenderEngine
    c_void_p, 'depths',  # struct ViewDepths
    c_void_p, 'gpuoffscreen',

    # animated smooth view
    c_void_p, 'sms',  # struct SmoothView3DStore
    c_void_p, 'smooth_timer',  # struct wmTimer

    # transform widget matrix
    c_float, 'twmat[4][4]',

    c_float, 'viewquat[4]',  # view rotation, must be kept normalized
    c_float, 'dist',  # distance from 'ofs' along -viewinv[2] vector, where result is negative as is 'ofs'
    c_float, 'camdx', 'camdy',  # camera view offsets, 1.0 = viewplane moves entire width/height
    c_float, 'pixsize',  # runtime only
    c_float, 'ofs[3]',  # view center & orbit pivot, negative of worldspace location, also matches -viewinv[3][0:3] in ortho mode.
    c_float, 'camzoom',  # viewport zoom on the camera frame, see BKE_screen_view3d_zoom_to_fac
    c_char, 'is_persp',   # check if persp/ortho view, since 'persp' cant be used for this since
                            # it can have cameras assigned as well. (only set in view3d_winmatrix_set)
    c_char, 'persp',
    c_char, 'view',
    c_char, 'viewlock',
    c_char, 'viewlock_quad',  # options for quadview (store while out of quad view)
    c_char, 'pad[3]',
    c_float, 'ofs_lock[2]',  # normalized offset for locked view: (-1, -1) bottom left, (1, 1) upper right

    c_short, 'twdrawflag',
    c_short, 'rflag',

    # last view (use when switching out of camera view)
    c_float, 'lviewquat[4]',
    c_short, 'lpersp', 'lview',  # lpersp can never be set to 'RV3D_CAMOB'

    c_float, 'gridview',
    c_float, 'tw_idot[3]',  # manipulator runtime: (1 - dot) product with view vector (used to check view alignment)

    # active rotation from NDOF or elsewhere
    c_float, 'rot_angle',
    c_float, 'rot_axis[3]',

    c_void_p, 'compositor',  # struct GPUFX
)


class GPUFXSettings(Structure):
    """DNA_gpu_types.h"""
    _fields_ = fields(
        c_void_p, 'dof',  # GPUDOFSettings
        c_void_p, 'ssao',  # GPUSSAOSettings
        c_char, 'fx_flag',  # eGPUFXFlags
        c_char, 'pad[7]',
        )


class View3D(Structure):
    """DNA_view3d_types.h: 153"""

View3D._fields_ = fields(
    c_void_p, 'next', 'prev',  # struct SpaceLink *next, *prev
    ListBase, 'regionbase',  # storage of regions for inactive spaces
    c_int, 'spacetype',
    c_float, 'blockscale',
    c_short, 'blockhandler[8]',

    c_float, 'viewquat[4]',  # DNA_DEPRECATED
    c_float, 'dist',  # DNA_DEPRECATED

    c_float, 'bundle_size',  # size of bundles in reconstructed data
    c_char, 'bundle_drawtype',  # display style for bundle
    c_char, 'pad[3]',

    c_uint, 'lay_prev',  # for active layer toggle
    c_uint, 'lay_used',  # used while drawing

    c_short, 'persp',  # DNA_DEPRECATED
    c_short, 'view',  # DNA_DEPRECATED

    c_void_p, 'camera', 'ob_centre',  # struct Object
    rctf, 'render_border',

    ListBase, 'bgpicbase',
    c_void_p, 'bgpic',  # <struct BGpic> DNA_DEPRECATED # deprecated, use bgpicbase, only kept for do_versions(...)

    View3D, '*localvd',  # allocated backup of its self while in localview

    c_char, 'ob_centre_bone[64]',  # optional string for armature bone to define center, MAXBONENAME

    c_uint, 'lay',
    c_int, 'layact',

    #  * The drawing mode for the 3d display. Set to OB_BOUNDBOX, OB_WIRE, OB_SOLID,
    #  * OB_TEXTURE, OB_MATERIAL or OB_RENDER
    c_short, 'drawtype',
    c_short, 'ob_centre_cursor',        # optional bool for 3d cursor to define center
    c_short, 'scenelock', 'around',
    c_short, 'flag', 'flag2',

    c_float, 'lens', 'grid',
    c_float, 'near', 'far',
    c_float, 'ofs[3]',  #  DNA_DEPRECATED  # XXX deprecated
    c_float, 'cursor[3]',

    c_short, 'matcap_icon',  # icon id

    c_short, 'gridlines',
    c_short, 'gridsubdiv',  # Number of subdivisions in the grid between each highlighted grid line
    c_char, 'gridflag',

    # transform widget info
    c_char, 'twtype', 'twmode', 'twflag',

    c_short, 'flag3',

    # afterdraw, for xray & transparent
    ListBase, 'afterdraw_transp',
    ListBase, 'afterdraw_xray',
    ListBase, 'afterdraw_xraytransp',

    # drawflags, denoting state
    c_char, 'zbuf', 'transp', 'xray',

    c_char, 'multiview_eye',  # multiview current eye - for internal use

    # built-in shader effects (eGPUFXFlags)
    c_char, 'pad3[4]',

    # note, 'fx_settings.dof' is currently _not_ allocated,
    # instead set (temporarily) from camera
    GPUFXSettings, 'fx_settings',

    c_void_p, 'properties_storage',  # Nkey panel stores stuff here (runtime only!)
    c_void_p, 'defmaterial',    # <struct Material> used by matcap now

    # # XXX deprecated?
    # struct bGPdata *gpd  DNA_DEPRECATED        # Grease-Pencil Data (annotation layers)
    #
    # short usewcol, dummy3[3]
    #
    #  # multiview - stereo 3d
    # short stereo3d_flag
    # char stereo3d_camera
    # char pad4
    # float stereo3d_convergence_factor
    # float stereo3d_volume_alpha
    # float stereo3d_convergence_alpha
    #
    # # local grid
    # char localgrid, cursor_snap_grid, dummy[2]
    # float lg_loc[3], dummy2[2] // orign(x,y,z)
    # float lg_quat[4] // rotation(x,y,z)
)


class wmSubWindow(Cast, Structure):
    """windowmanager/intern/wm_subwindow.c: 67"""

wmSubWindow._fields_ = fields(
    wmSubWindow, '*next', '*prev',
    rcti, 'winrct',
    c_int, 'swinid',
)


class wmEvent(Cast, Structure):
    """windowmanager/WM_types.h: 431"""

    def is_timer_event(self, timer):
        """
        :type timer: bpy.types.Timer | int
        :rtype: bool
        """
        TIMER = 272  # 'TIMER'
        if isinstance(timer, int):
            addr = timer
        elif isinstance(timer, bpy.types.Timer):
            addr = timer.as_pointer()
        else:
            raise TypeError()
        return self.type == TIMER and self.customdata == addr

wmEvent._fields_ = fields(
    wmEvent, '*next', '*prev',

    c_short, 'type',
    c_short, 'val',
    c_int, 'x', 'y',
    c_int, 'mval[2]',
    c_char, 'utf8_buf[6]',

    c_char, 'ascii',
    c_char, 'pad',

    c_short, 'prevtype',
    c_short, 'prevval',
    c_int, 'prevx', 'prevy',
    c_double, 'prevclicktime',
    c_int, 'prevclickx', 'prevclicky',

    c_short, 'shift', 'ctrl', 'alt', 'oskey',
    c_short, 'keymodifier',

    c_short, 'check_click',

    c_char_p, 'keymap_idname',  # const char

    c_void_p, 'tablet_data',  # const struct wmTabletData

    c_short, 'custom',
    c_short, 'customdatafree',
    c_int, 'pad2',
    c_void_p, 'customdata',
)


# operator type return flags: exec(), invoke() modal(), return values
OPERATOR_RUNNING_MODAL = 1 << 0
OPERATOR_CANCELLED = 1 << 1
OPERATOR_FINISHED = 1 << 2
# add this flag if the event should pass through
OPERATOR_PASS_THROUGH = 1 << 3
# in case operator got executed outside WM code... like via fileselect
OPERATOR_HANDLED = 1 << 4
# used for operators that act indirectly (eg. popup menu)
# note: this isn't great design (using operators to trigger UI) avoid where
#       possible.
OPERATOR_INTERFACE = 1 << 5
OPERATOR_FLAGS_ALL = (
    OPERATOR_RUNNING_MODAL |
    OPERATOR_CANCELLED |
    OPERATOR_FINISHED |
    OPERATOR_PASS_THROUGH |
    OPERATOR_HANDLED |
    OPERATOR_INTERFACE |
    0)

# wmOperatorType.flag
OPTYPE_REGISTER = (1 << 0)  # register operators in stack after finishing
OPTYPE_UNDO = (1 << 1)  # do undo push after after
OPTYPE_BLOCKING = (1 << 2)  # let blender grab all input from the WM (X11)
OPTYPE_MACRO = (1 << 3)
OPTYPE_GRAB_CURSOR = (1 << 4)  # grabs the cursor and optionally enables
                               # continuous cursor wrapping
OPTYPE_PRESET = (1 << 5)  # show preset menu

# some operators are mainly for internal use
# and don't make sense to be accessed from the
# search menu, even if poll() returns true.
# currently only used for the search toolbox */
OPTYPE_INTERNAL = (1 << 6)

OPTYPE_LOCK_BYPASS = (1 << 7)  # Allow operator to run when interface is locked
PTYPE_UNDO_GROUPED = (1 << 8)  # Special type of undo which doesn't store
                               #  itself multiple times


class wmOperatorType(Structure):
    """source/blender/windowmanager/WM_types.h: 518"""

wmOperatorType_fields = fields(
    c_char_p, 'name',
    c_char_p, 'idname',
    c_char_p, 'translation_context',
    c_char_p, 'description'
)

if (bpy.app.version[1] >= 79 or
        bpy.app.version[1] == 78 and bpy.app.version[2] >= 4):
    wmOperatorType_fields += fields(
        # commit: 69470e36d6b17042260b06f26ca3c2f702747324
        # Tue Nov 15 19:50:11 2016
        c_char_p, 'undo_group',
    )
wmOperatorType_fields += fields(
    # int (*exec)(struct bContext *, struct wmOperator *) ATTR_WARN_UNUSED_RESULT;
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'exec',
    # bool (*check)(struct bContext *, struct wmOperator *);
    CFUNCTYPE(c_bool, c_void_p, c_void_p), 'check',
    # int (*invoke)(struct bContext *, struct wmOperator *, const struct wmEvent *) ATTR_WARN_UNUSED_RESULT;
    CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p), 'invoke',
    # void (*cancel)(struct bContext *, struct wmOperator *);
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'cancel',
    # int (*modal)(struct bContext *, struct wmOperator *, const struct wmEvent *) ATTR_WARN_UNUSED_RESULT;
    CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p), 'modal',

    # int (*poll)(struct bContext *) ATTR_WARN_UNUSED_RESULT;
    CFUNCTYPE(c_int, c_void_p), 'poll',

    # void (*ui)(struct bContext *, struct wmOperator *);
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'ui',

    StructRNA, '*srna',

    c_void_p, 'last_properties',  # <IDProperty>

    PropertyRNA, '*prop',  # <PropertyRNA>

    ListBase, 'macro',

    c_void_p, 'modalkeymap',  # <wmKeyMap>

    # int (*pyop_poll)(struct bContext *, struct wmOperatorType *ot) ATTR_WARN_UNUSED_RESULT;
    CFUNCTYPE(c_int, c_void_p, c_void_p), 'pyop_poll',

    ExtensionRNA, 'ext',

    c_short, 'flag',
)

wmOperatorType._fields_ = wmOperatorType_fields


class wmOperator(Cast, Structure):
    """source/blender/makesdna/DNA_windowmanager_types.h: 344

    pythonインスタンスからの取得方法:
    # python/intern/bpy_operator.c: 423: pyop_getinstance()
    pyop = bpy.ops.wm.splash
    opinst = pyop.get_instance()
    pyrna = ct.cast(id(opinst), ct.POINTER(structures.BPy_StructRNA)).contents
    # wmOperator
    op = ct.cast(pyrna.ptr.data,
                 ct.POINTER(structures.wmOperator)).contents
    # wmOperatorType
    ot = op.type.contents
    """

wmOperator._fields_ = fields(
    wmOperator, '*next', '*prev',

    c_char, 'idname[64]',
    c_void_p, 'properties',  # IDProperty

    wmOperatorType, '*type',
    c_void_p, 'customdata',
    py_object, 'py_instance',  # python stores the class instance here

    c_void_p, 'ptr',  # PointerRNA
    c_void_p, 'reports',  # ReportList

    ListBase, 'macro',
    wmOperator, '*opm',
    c_void_p, 'layout',  # uiLayout
    c_short, 'flag', c_short * 3, 'pad',
)


class wmEventHandler(Cast, Structure):
    """source/blender/windowmanager/wm_event_system.h: 45"""

wmEventHandler._fields_ = fields(
    wmEventHandler, '*next', '*prev',

    c_char, 'type',  # WM_HANDLER_DEFAULT, ...
    c_char, 'flag',  # WM_HANDLER_BLOCKING, ...

    # keymap handler
    c_void_p, 'keymap',  # <wmKeyMap> pointer to builtin/custom keymaps
    c_void_p, 'bblocal', 'bbwin',  # <const rcti> optional local and windowspace bb

    # modal operator handler
    wmOperator, '*op',  # for derived/modal handlers
    ScrArea, '*op_area',  # for derived/modal handlers
    ARegion, '*op_region',  # for derived/modal handlers
    c_short, 'op_region_type',  # for derived/modal handlers

    # ui handler
    c_void_p, 'ui_handle',  # <function: wmUIHandlerFunc> callback receiving events
    c_void_p, 'ui_remove',  # <function: wmUIHandlerRemoveFunc> callback when handler is removed
    c_void_p, 'ui_userdata',  # user data pointer
    ScrArea, '*ui_area',  # for derived/modal handlers
    ARegion, '*ui_region',  # for derived/modal handlers
    ARegion, '*ui_menu',  # for derived/modal handlers

    # drop box handler
    ListBase, '*dropboxes',
)

# wmEventHandler.flag
WM_HANDLER_DO_FREE = 1 << 7


class wmWindow(Cast, Structure):
    """source/blender/makesdna/DNA_windowmanager_types.h: 175"""

    @classmethod
    def modal_handlers(cls, window):
        """ctypesを使い、windowに登録されている modal handlerのリストを返す。
        idnameはUIなら 'UI'、認識できない物なら 'UNKNOWN' となる。
        :type window: bpy.types.Window
        :rtype: list[(Structures.wmEventHandler, str, int, int, int)]
        """
        if not window:
            return []

        addr = window.as_pointer()
        win = cast(addr, POINTER(wmWindow)).contents

        handlers = []

        ptr = wmEventHandler.cast(win.modalhandlers.first, contents=False)
        while ptr:
            # http://docs.python.jp/3/library/ctypes.html#surprises
            # この辺りの事には注意する事
            handler = ptr.contents
            area = handler.op_area  # NULLの場合はNone
            region = handler.op_region  # NULLの場合はNone
            idname = 'UNKNOWN'
            if handler.ui_handle:
                idname = 'UI'
            if handler.op:
                op = handler.op.contents
                ot = op.type.contents
                if ot.idname:
                    idname = ot.idname.decode()
            handlers.append((handler, idname, area, region,
                             handler.op_region_type))
            ptr = handler.next

        return handlers

wmWindow._fields_ = fields(
    wmWindow, '*next', '*prev',

    c_void_p, 'ghostwin',

    bScreen, '*screen',
    bScreen, '*newscreen',
    c_char, 'screenname[64]',

    c_short, 'posx', 'posy', 'sizex', 'sizey',
    c_short, 'windowstate',
    c_short, 'monitor',
    c_short, 'active',
    c_short, 'cursor',
    c_short, 'lastcursor',
    c_short, 'modalcursor',
    c_short, 'grabcursor',  # GHOST_TGrabCursorMode
    c_short, 'addmousemove',
    c_short, 'multisamples',
    c_short, 'pad[3]',

    c_int, 'winid',

    # internal, lock pie creation from this event until released
    c_short, 'lock_pie_event',
    # exception to the above rule for nested pies, store last pie event for operators
    # that spawn a new pie right after destruction of last pie
    c_short, 'last_pie_event',

    wmEvent, '*eventstate',

    wmSubWindow, '*curswin',

    c_void_p, 'tweak',  # struct wmGesture

    c_void_p, 'ime_data',  # struct wmIMEData

    c_int, 'drawmethod', 'drawfail',
    ListBase, 'drawdata',

    ListBase, 'queue',
    ListBase, 'handlers',
    ListBase, 'modalhandlers',  # wmEventHandler

    ListBase, 'subwindows',
    ListBase, 'gesture',

    c_void_p, 'stereo3d_format',  # struct Stereo3dFormat
)


class ReportList(Structure):
    _fields_ = fields(
        ListBase, 'list',
        c_int, 'printlevel',  # ReportType
        c_int, 'storelevel',  # ReportType
        c_int, 'flag', 'pad',
        c_void, '*reporttimer'  # <struct wmTimer>
    )


class wmWindowManager(Cast, Structure):
    """source/blender/makesdna/DNA_windowmanager_types.h: 127"""
    pass

wmWindowManager._fields_ = fields(
    ID, 'id',

    wmWindow, '*windrawable', '*winactive',  # separate active from drawable
    ListBase, 'windows',

    c_int, 'initialized',           #  set on file read
    c_short, 'file_saved',          # indicator whether data was saved
    c_short, 'op_undo_depth',       # operator stack depth to avoid nested undo pushes

    ListBase, 'operators',          # operator registry

    ListBase, 'queue',              # refresh/redraw wmNotifier structs

    ReportList, 'reports',   # information and error reports

    ListBase, 'jobs',               # threaded jobs manager

    ListBase, 'paintcursors',       # extra overlay cursors to draw, like circles

    ListBase, 'drags',              # active dragged items

    ListBase, 'keyconfigs',         # known key configurations
    c_void, '*defaultconf',         # <struct wmKeyConfig>  # default configuration
    c_void, '*addonconf',           # <struct wmKeyConfig>  # addon configuration
    c_void, '*userconf',            # <struct wmKeyConfig>  # user configuration

    ListBase, 'timers',             # active timers
    c_void, '*autosavetimer',       # <struct wmTimer>  # timer for auto save

    c_char, 'is_interface_locked',  # indicates whether interface is locked for user interaction
    c_char, 'par[7]',
)


class SpaceText(Cast, Structure):
    """source/blender/makesdna/DNA_space_types.h: 981"""

SpaceText._fields_ = fields(
    SpaceText, '*next', '*prev',
    ListBase, 'regionbase',  # storage of regions for inactive spaces
    c_int, 'spacetype',
    c_float, 'blockscale',  # DNA_DEPRECATED
    c_short, 'blockhandler[8]',  # DNA_DEPRECATED

    c_void_p, 'text',  # struct Text

    c_int, 'top', 'viewlines',
    c_short, 'flags', 'menunr',

    c_short, 'lheight',  # user preference, is font_size!
    c_char, 'cwidth', 'linenrs_tot',  # runtime computed, character width and the number of chars to use when showing line numbers
    c_int, 'left',
    c_int, 'showlinenrs',
    c_int, 'tabnumber',

    c_short, 'showsyntax',
    c_short, 'line_hlight',
    c_short, 'overwrite',
    c_short, 'live_edit',  # run python while editing, evil
    c_float, 'pix_per_line',

    rcti, 'txtscroll', 'txtbar',

    c_int, 'wordwrap', 'doplugins',

    c_char, 'findstr[256]',  # ST_MAX_FIND_STR
    c_char, 'replacestr[256]',  # ST_MAX_FIND_STR

    c_short, 'margin_column',  # column number to show right margin at
    c_short, 'lheight_dpi',  # actual lineheight, dpi controlled
    c_char, 'pad[4]',

    c_void_p, 'drawcache',  # cache for faster drawing

    c_float, 'scroll_accum[2]',  # runtime, for scroll increments smaller than a line
)


class bContext(Cast, Structure):
    """source/blender/blenkernel/intern/context.c:61"""
    class bContext_wm(Structure):
        _fields_ = fields(
            c_void_p, 'manager',  # struct wmWindowManager
            wmWindow, '*window',
            bScreen, '*screen',
            ScrArea, '*area',
            ARegion, '*region',
            ARegion, '*menu',
            c_void_p, 'store',  # struct bContextStore
            c_char_p, 'operator_poll_msg',  # reason for poll failing
        )

    class bContext_data(Structure):
        _fields_ = fields(
            c_void_p, 'main',  # struct Main
            c_void_p, 'scene',  # struct Scene

            c_int, 'recursion',
            c_int, 'py_init',  # true if python is initialized
            c_void_p, 'py_context',
        )

    _fields_ = fields(
        c_int, 'thread',

        # windowmanager context
        bContext_wm, 'wm',

        # data context
        bContext_data, 'data',
    )

    @classmethod
    def wm_window_set(cls, window):
        """CTX_wm_window_set"""
        ctx = cls.cast(bpy.context)

        if window:
            ctx.wm.window = wmWindow.cast(window, False)
        else:
            ctx.wm.window = None
        if window and window.screen:
            ctx.wm.screen = window.screen.as_pointer()
        else:
            ctx.wm.screen = None
        if ctx.wm.screen:
            ctx.data.scene = ctx.wm.screen.scene
        ctx.wm.area = None
        ctx.wm.region = None

    @classmethod
    def wm_screen_set(cls, screen):
        """CTX_wm_screen_set"""
        ctx = cls.cast(bpy.context)

        if screen:
            ctx.wm.screen = bScreen.cast(screen, False)
        else:
            ctx.wm.screen = None
        if ctx.wm.screen:
            ctx.data.scene = ctx.wm.screen.scene
        ctx.wm.area = None
        ctx.wm.region = None

    @classmethod
    def wm_area_set(cls, area):
        """CTX_wm_area_set"""
        ctx = cls.cast(bpy.context)

        if area:
            ctx.wm.area = ScrArea.cast(area, False)
        else:
            ctx.wm.area = None
        ctx.wm.region = None

    @classmethod
    def wm_region_set(cls, region, calc_mouse=False):
        """CTX_wm_region_set"""
        ctx = cls.cast(bpy.context)

        if region:
            ctx.wm.region = ARegion.cast(region, False)
        else:
            ctx.wm.region = None
        if calc_mouse:
            cls.calc_mouse()

    @classmethod
    def calc_mouse(cls):
        context = bpy.context
        ctx = cls.cast(context)
        win_p = ctx.wm.window
        if win_p:
            win = win_p.contents
            event = win.eventstate.contents
            region = context.region
            if region:
                event.mval[0] = event.x - region.x
                event.mval[1] = event.y - region.y
            else:
                event.mval[0] = event.mval[1] = 0


class Text(Cast, Structure):
    """makesdna/DNA_text_types.h: 50"""
    _fields_ = fields(
        ID, 'id',

        c_char_p, 'name',

        c_int, 'flags', 'nlines',

        ListBase, 'lines',
        c_void_p, 'curl', 'sell',  # <TextLine>
        c_int, 'curc', 'selc',

        c_char_p, 'undo_buf',
        c_int, 'undo_pos', 'undo_len',

        c_void_p, 'compiled',
        c_double, 'mtime',
    )


# 未使用
'''
class Material(Structure):
    """DNA_material_types.h"""

Material._fields_ = fields(
    ID, 'id',
)
'''


class DerivedMesh(Structure):
    """blenkernel/BKE_DerivedMesh.h: 177"""


class BMEditMesh(Structure):
    """blenkernel/BKE_editmesh.h: 53"""


# tessellation face, see MLoop/MPoly for the real face data
class MFace(Structure):
    """DNA_meshdata_types.h: 41"""
    _fields_ = fields(
        c_uint, 'v1', 'v2', 'v3', 'v4',
        c_short, 'mat_nr',
        c_char, 'edcode', 'flag',  # we keep edcode, for conversion to edges draw flags in old files
    )


class MEdge(Structure):
    """DNA_meshdata_types.h: 47"""
    _fields_ = fields(
        c_uint, 'v1', 'v2',
        c_char, 'crease', 'bweight',
        c_short, 'flag',
    )


class MDeformWeight(Structure):
    """DNA_meshdata_types.h: 53"""
    _fields_ = fields(
        c_int, 'def_nr',
        c_float, 'weight',
    )


class MDeformVert(Structure):
    """DNA_meshdata_types.h: 58"""
    _fields_ = fields(
        c_void, '*dw',  # struct MDeformWeight
        c_int, 'totweight',
        c_int, 'flag',  # flag only in use for weightpaint now
    )


class MVert(Structure):
    """DNA_meshdata_types.h: 64"""
    _fields_ = fields(
        c_float, 'co[3]',
        c_short, 'no[3]',
        c_char, 'flag', 'bweight',
    )


# * tessellation vertex color data.
# * at the moment alpha is abused for vertex painting and not used for transparency, note that red and blue are swapped
class MCol(Structure):
    _fields_ = fields(
        c_uint8, 'a', 'r', 'g', 'b'  # unsigned char
    )


# new face structure, replaces MFace, which is now only used for storing tessellations.
class MPoly(Structure):
    _fields_ = fields(
        # offset into loop array and number of loops in the face
        c_int, 'loopstart',
        c_int, 'totloop',  # keep signed since we need to subtract when getting the previous loop
        c_short, 'mat_nr',
        c_char, 'flag', 'pad',
    )

# the e here is because we want to move away from relying on edge hashes.
class MLoop(Structure):
    _fields_ = fields(
        c_uint, 'v',  # vertex index
        c_uint, 'e',  # edge index
    )


class MLoopTri(Structure):
    _fields_ = fields(
        c_uint, 'tri[3]',
        c_uint, 'poly',
    )


class Mesh(Structure):
    """DNA_mesh.types.h: 55"""
    _fields_ = fields(
        ID, 'id',
        c_void, '*adt',  # struct AnimData  # animation data (must be immediately after id for utilities to use it)

        c_void, '*bb',  # struct BoundBox

        c_void, '*ipo',  # struct Ipo  # DNA_DEPRECATED  # old animation system, deprecated for 2.5
        c_void, '*key',  # struct Key
        c_void, '**mat',  # struct Material
        c_void, '*mselect',  # struct MSelect

        # BMESH ONLY
        #new face structures
        c_void, '*mpoly',  # struct MPoly
        c_void, '*mtpoly',  # struct MTexPoly
        c_void, '*mloop',  # struct MLoop
        c_void, '*mloopuv',  # struct MLoopUV
        c_void, '*mloopcol',  # struct MLoopCol
        # END BMESH ONLY

        # mface stores the tessellation (triangulation) of the mesh,
        # real faces are now stored in nface.
        c_void, '*mface',  # struct MFace  # array of mesh object mode faces for tessellation
        c_void, '*mtface',  # struct MTFace  # store tessellation face UV's and texture here
        c_void, '*tface',  # struct TFace  # DNA_DEPRECATED   # deprecated, use mtface
        c_void, '*mvert',  # struct MVert  # array of verts
        c_void, '*medge',  # struct MEdge  # array of edges
        c_void, '*dvert',  # struct MDeformVert  # deformgroup vertices

        # array of colors for the tessellated faces, must be number of tessellated
        # faces * 4 in length
        c_void, '*mcol',  # struct MCol
        c_void, '*texcomesh',  # struct Mesh

        # When the object is available, the preferred access method is: BKE_editmesh_from_object(ob)
        BMEditMesh, '*edit_btmesh',  # not saved in file!

        # 以下略
    )


BMEditMesh._fields_ = fields(
    c_void_p, 'bm',  # BMesh
    # this is for undoing failed operations
    BMEditMesh, '*emcopy',
    c_int, 'emcopyusers',

    # we store tessellations as triplets of three loops,
    # which each define a triangle.
    c_void_p, 'looptris',  # struct BMLoop *(*looptris)[3]
    c_int, 'tottri',

    # derivedmesh stuff
    DerivedMesh, '*derivedFinal', '*derivedCage',

    # 以下略
)


class CustomDataLayer(Structure):
    _fields_ = fields(
        c_int, 'type',       # type of data in layer
        c_int, 'offset',     # in editmode, offset of layer in block
        c_int, 'flag',       # general purpose flag
        c_int, 'active',     # number of the active layer of this type
        c_int, 'active_rnd', # number of the layer to render
        c_int, 'active_clone', # number of the layer to render
        c_int, 'active_mask', # number of the layer to render
        c_int, 'uid',        # shape keyblock unique id reference
        c_char, 'name[64]',  # layer name, MAX_CUSTOMDATA_LAYER_NAME
        c_void, '*data',     # layer data
    )


class CustomData(Structure):
    _fields_ = fields(
        CustomDataLayer, '*layers',  # CustomDataLayers, ordered by type
        c_int, 'typemap[42]',  # runtime only! - maps types to indices of first layer of that type,
                               # MUST be >= CD_NUMTYPES, but we cant use a define here.
                               # Correct size is ensured in CustomData_update_typemap assert()
        c_int, 'pad_i1',
        c_int, 'totlayer', 'maxlayer',        # number of layers, size of layers array
        c_int, 'totsize',                   # in editmode, total size of all data layers
        c_void, '*pool',  # struct BLI_mempool  # (BMesh Only): Memory pool for allocation of blocks
        c_void, '*external',  # CustomDataExternal  # external file storing customdata layers
    )


class _DerivedMesh_looptris(Structure):
    _fields_ = fields(
        c_void, '*array',  # struct MLoopTri
        c_int, 'num',
        c_int, 'num_alloc',
    )


DerivedMesh._fields_ = fields(
    # * Private DerivedMesh data, only for internal DerivedMesh use
    CustomData, 'vertData', 'edgeData', 'faceData', 'loopData', 'polyData',
    c_int, 'numVertData', 'numEdgeData', 'numTessFaceData', 'numLoopData', 'numPolyData',
    c_int, 'needsFree',  # checked on ->release, is set to 0 for cached results
    c_int, 'deformedOnly',  # set by modifier stack if only deformed from original
    c_void, '*bvhCache',  # typedef struct LinkNode *BVHCache
    c_void, '*drawObject',  # struct GPUDrawObject
    c_int, 'type',  # DerivedMeshType
    c_float, 'auto_bump_scale',
    c_int, 'dirty',  # DMDirtyFlag
    c_int, 'totmat',  # total materials. Will be valid only before object drawing.
    c_void, '**mat',  # struct Material  # material array. Will be valid only before object drawing

    # warning Typical access is done via #getLoopTriArray, #getNumLoopTri.
    _DerivedMesh_looptris, 'looptris',

    # use for converting to BMesh which doesn't store bevel weight and edge crease by default
    c_char, 'cd_flag',

    #* Calculate vert and face normals
    c_void, '*calcNormals',  # void (*calcNormals)(DerivedMesh * dm)

    #* Calculate loop (split) normals
    c_void, '*calcLoopNormals',  # void (*calcLoopNormals)(DerivedMesh * dm, const bool use_split_normals, const float split_angle)

    #* Calculate loop (split) normals, and returns split loop normal spacearr.
    c_void, '*calcLoopNormalsSpaceArray',  # void (*calcLoopNormalsSpaceArray)(DerivedMesh * dm, const bool use_split_normals, const float split_angle,
                                           #       struct MLoopNorSpaceArray *r_lnors_spacearr)

    c_void, '*calcLoopTangents',  # void (*calcLoopTangents)(DerivedMesh * dm)

    # * Recalculates mesh tessellation
    c_void, '*recalcTessellation',  # void (*recalcTessellation)(DerivedMesh * dm)

    # * Loop tessellation cache
    CFUNCTYPE(c_int, POINTER(DerivedMesh)),  '*recalcLoopTri',  # void (*recalcLoopTri)(DerivedMesh * dm)
    # * accessor functions
    CFUNCTYPE(POINTER(MLoopTri), POINTER(DerivedMesh)), '*getLoopTriArray',  #const struct MLoopTri *(*getLoopTriArray)(DerivedMesh * dm)
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), '*getNumLoopTri',  # int (*getNumLoopTri)(DerivedMesh *dm)

    # Misc. Queries

    # Also called in Editmode
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), 'getNumVerts',  # int (*getNumVerts)(DerivedMesh *dm)
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), 'getNumEdges',  # int (*getNumEdges)(DerivedMesh *dm)
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), 'getNumTessFaces',  # int (*getNumTessFaces)(DerivedMesh *dm)
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), 'getNumLoops',  # int (*getNumLoops)(DerivedMesh *dm)
    CFUNCTYPE(c_int, POINTER(DerivedMesh)), 'getNumPolys',  # int (*getNumPolys)(DerivedMesh *dm)

    # * Copy a single vert/edge/tessellated face from the derived mesh into
    # * ``*r_{vert/edge/face}``. note that the current implementation
    # * of this function can be quite slow, iterating over all
    # * elements (editmesh)

    c_void, '*getVert',  # void (*getVert)(DerivedMesh * dm, int index, struct MVert * r_vert)
    c_void, '*getEdge',  # void (*getEdge)(DerivedMesh * dm, int index, struct MEdge * r_edge)
    c_void, '*getTessFace',  # void (*getTessFace)(DerivedMesh * dm, int index, struct MFace * r_face)

    # * Return a pointer to the entire array of verts/edges/face from the
    # * derived mesh. if such an array does not exist yet, it will be created,
    # * and freed on the next ->release(). consider using getVert/Edge/Face if
    # * you are only interested in a few verts/edges/faces.

    CFUNCTYPE(POINTER(MVert), POINTER(DerivedMesh)), 'getVertArray',  # struct MVert *(*getVertArray)(DerivedMesh * dm)
    CFUNCTYPE(POINTER(MEdge), POINTER(DerivedMesh)), 'getEdgeArray',  # struct MEdge *(*getEdgeArray)(DerivedMesh * dm)
    CFUNCTYPE(POINTER(MFace), POINTER(DerivedMesh)), 'getTessFaceArray',  # struct MFace *(*getTessFaceArray)(DerivedMesh * dm)
    CFUNCTYPE(POINTER(MLoop), POINTER(DerivedMesh)), 'getLoopArray',  # struct MLoop *(*getLoopArray)(DerivedMesh * dm)
    CFUNCTYPE(POINTER(MPoly), POINTER(DerivedMesh)), 'getPolyArray',  # struct MPoly *(*getPolyArray)(DerivedMesh * dm)

    # * Copy all verts/edges/faces from the derived mesh into
    # * *{vert/edge/face}_r (must point to a buffer large enough)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), POINTER(MVert)), 'copyVertArray',  # void (*copyVertArray)(DerivedMesh *dm, struct MVert *r_vert);
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), POINTER(MEdge)), 'copyEdgeArray',  # void (*copyEdgeArray)(DerivedMesh *dm, struct MEdge *r_edge);
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), POINTER(MFace)), 'copyTessFaceArray',  # void (*copyTessFaceArray)(DerivedMesh *dm, struct MFace *r_face);
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), POINTER(MLoop)), 'copyLoopArray',  # void (*copyLoopArray)(DerivedMesh *dm, struct MLoop *r_loop);
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), POINTER(MPoly)), 'copyPolyArray',  # void (*copyPolyArray)(DerivedMesh *dm, struct MPoly *r_poly);

    # * Return a copy of all verts/edges/faces from the derived mesh
    # * it is the caller's responsibility to free the returned pointer
    c_void, '*dupVertArray',  # struct MVert *(*dupVertArray)(DerivedMesh * dm);
    c_void, '*dupEdgeArray',  # struct MEdge *(*dupEdgeArray)(DerivedMesh * dm);
    c_void, '*dupTessFaceArray',  # struct MFace *(*dupTessFaceArray)(DerivedMesh * dm);
    c_void, '*dupLoopArray',  # struct MLoop *(*dupLoopArray)(DerivedMesh * dm);
    c_void, '*dupPolyArray',  # struct MPoly *(*dupPolyArray)(DerivedMesh * dm);

    # * Return a pointer to a single element of vert/edge/face custom data
    # * from the derived mesh (this gives a pointer to the actual data, not
    # * a copy)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int, c_int), 'getVertData',  # void *(*getVertData)(DerivedMesh *dm, int index, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int, c_int), 'getEdgeData',  # void *(*getEdgeData)(DerivedMesh *dm, int index, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int, c_int), 'getTessFaceData',  # void *(*getTessFaceData)(DerivedMesh *dm, int index, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int, c_int), 'getPolyData',  # void *(*getPolyData)(DerivedMesh *dm, int index, int type)

    # * Return a pointer to the entire array of vert/edge/face custom data
    # * from the derived mesh (this gives a pointer to the actual data, not
    # * a copy)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int), 'getVertDataArray',  # void *(*getVertDataArray)(DerivedMesh *dm, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int), 'getEdgeDataArray',  # void *(*getEdgeDataArray)(DerivedMesh *dm, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int), 'getTessFaceDataArray',  # void *(*getTessFaceDataArray)(DerivedMesh *dm, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int), 'getLoopDataArray',  # void *(*getLoopDataArray)(DerivedMesh *dm, int type)
    CFUNCTYPE(c_void_p, POINTER(DerivedMesh), c_int), 'getPolyDataArray',  # void *(*getPolyDataArray)(DerivedMesh *dm, int type)

    # /** Retrieves the base CustomData structures for
    #  * verts/edges/tessfaces/loops/facdes*/
    # CustomData *(*getVertDataLayout)(DerivedMesh * dm);
    # CustomData *(*getEdgeDataLayout)(DerivedMesh * dm);
    # CustomData *(*getTessFaceDataLayout)(DerivedMesh * dm);
    # CustomData *(*getLoopDataLayout)(DerivedMesh * dm);
    # CustomData *(*getPolyDataLayout)(DerivedMesh * dm);
    c_void_p, 'getVertDataLayout',
    c_void_p, 'getEdgeDataLayout',
    c_void_p, 'getTessFaceDataLayout',
    c_void_p, 'getLoopDataLayout',
    c_void_p, 'getPolyDataLayout',

    # /** Copies all customdata for an element source into dst at index dest */
    # void (*copyFromVertCData)(DerivedMesh *dm, int source, CustomData *dst, int dest);
    # void (*copyFromEdgeCData)(DerivedMesh *dm, int source, CustomData *dst, int dest);
    # void (*copyFromFaceCData)(DerivedMesh *dm, int source, CustomData *dst, int dest);
    c_void_p, 'copyFromVertCData',
    c_void_p, 'copyFromEdgeCData',
    c_void_p, 'copyFromFaceCData',

    # /** Optional grid access for subsurf */
    # int (*getNumGrids)(DerivedMesh *dm);
    # int (*getGridSize)(DerivedMesh *dm);
    # struct CCGElem **(*getGridData)(DerivedMesh * dm);
    # int *(*getGridOffset)(DerivedMesh * dm);
    # void (*getGridKey)(DerivedMesh *dm, struct CCGKey *key);
    # DMFlagMat *(*getGridFlagMats)(DerivedMesh * dm);
    # unsigned int **(*getGridHidden)(DerivedMesh * dm);
    c_void_p, 'getNumGrids',
    c_void_p, 'getGridSize',
    c_void_p, 'getGridData',
    c_void_p, 'getGridOffset',
    c_void_p, 'getGridKey',
    c_void_p, 'getGridFlagMats',
    c_void_p, 'getGridHidden',

    # /** Iterate over each mapped vertex in the derived mesh, calling the
    #  * given function with the original vert and the mapped vert's new
    #  * coordinate and normal. For historical reasons the normal can be
    #  * passed as a float or short array, only one should be non-NULL.
    #  */
    # void (*foreachMappedVert)(DerivedMesh *dm,
    #                           void (*func)(void *userData, int index, const float co[3],
    #                                        const float no_f[3], const short no_s[3]),
    #                           void *userData,
    #                           DMForeachFlag flag);
    c_void_p, 'foreachMappedVert',

    # /** Iterate over each mapped edge in the derived mesh, calling the
    #  * given function with the original edge and the mapped edge's new
    #  * coordinates.
    #  */
    # void (*foreachMappedEdge)(DerivedMesh *dm,
    #                           void (*func)(void *userData, int index,
    #                                        const float v0co[3], const float v1co[3]),
    #                           void *userData);
    c_void_p, 'foreachMappedEdge',

    # /** Iterate over each mapped loop in the derived mesh, calling the given function
    #  * with the original loop index and the mapped loops's new coordinate and normal.
    #  */
    # void (*foreachMappedLoop)(DerivedMesh *dm,
    #                           void (*func)(void *userData, int vertex_index, int face_index,
    #                                        const float co[3], const float no[3]),
    #                           void *userData,
    #                           DMForeachFlag flag);
    c_void_p, 'foreachMappedLoop',

    # /** Iterate over each mapped face in the derived mesh, calling the
    #  * given function with the original face and the mapped face's (or
    #  * faces') center and normal.
    #  */
    # void (*foreachMappedFaceCenter)(DerivedMesh *dm,
    #                                 void (*func)(void *userData, int index,
    #                                              const float cent[3], const float no[3]),
    #                                 void *userData,
    #                                 DMForeachFlag flag);
    CFUNCTYPE(c_int,
              POINTER(DerivedMesh),
              CFUNCTYPE(c_int, c_void_p, c_int, c_void_p, c_void_p),
              c_void_p,
              c_int),
    'foreachMappedFaceCenter',

    # * Iterate over all vertex points, calling DO_MINMAX with given args.
    # *
    # * Also called in Editmode
    # void (*getMinMax)(DerivedMesh *dm, float r_min[3], float r_max[3]);
    c_void_p, 'getMinMax',

    # * Direct Access Operations
    #  * - Can be undefined
    # * - Must be defined for modifiers that only deform however

    # * Get vertex location, undefined if index is not valid
    # void (*getVertCo)(DerivedMesh *dm, int index, float r_co[3]);
    CFUNCTYPE(c_int, POINTER(DerivedMesh), c_int, c_void_p), 'getVertCo',

    # * Fill the array (of length .getNumVerts()) with all vertex locations
    # void (*getVertCos)(DerivedMesh *dm, float (*r_cos)[3]);
    CFUNCTYPE(c_int, POINTER(DerivedMesh), c_void_p), 'getVertCos',

    # # * Get smooth vertex normal, undefined if index is not valid
    # void (*getVertNo)(DerivedMesh *dm, int index, float r_no[3]);
    # void (*getPolyNo)(DerivedMesh *dm, int index, float r_no[3]);

    # 以下略

)


class ViewContext(Structure):
    """editors/include/ED_view3d.h"""

if version[1] > 76 or version[1] == 76 and version[2] >= 11:
    ViewContext._fields_ = fields(
        c_void_p, 'scene',
        c_void_p, 'obact',
        c_void_p, 'obedit',
        c_void_p, 'ar',
        c_void_p, 'v3d',
        c_void_p, 'win',
        c_void_p, 'rv3d',
        BMEditMesh, '*em',
        c_int, 'mval[2]',
    )
else:
    ViewContext._fields_ = fields(
        c_void_p, 'scene',
        c_void_p, 'obact',
        c_void_p, 'obedit',
        c_void_p, 'ar',
        c_void_p, 'v3d',
        c_void_p, 'rv3d',
        BMEditMesh, '*em',
        c_int, 'mval[2]',
    )


###############################################################################
# BMesh
###############################################################################
# class c_int8_(c_int8):
#     """サブクラス化することでPython型へ透過的に変換しなくなる"""
#     pass


class BMHeader(Structure):
    _fields_ = fields(
        c_void_p, 'data',
        c_int, 'index',
        c_char, 'htype',
        # c_char, 'hflag',
        # c_int8_, 'hflag',
        c_int8, 'hflag',  # ビット演算の為int型にする
        c_char, 'api_flag',
    )


class BMElem(Structure):
    _fields_ = fields(
        BMHeader, 'head',
    )


class BMVert(Structure):
    pass


class BMEdge(Structure):
    pass


class BMFace(Structure):
    pass


class BMLoop(Structure):
    pass


class BMDiskLink(Structure):
    _fields_ = fields(
        BMEdge, '*next',
        BMEdge, '*prev',
    )


BMVert._fields_ = fields(
    BMHeader, 'head',
    c_void_p, 'oflags',  # BMFlagLayer
    c_float, 'co[3]',
    c_float, 'no[3]',
    BMEdge, '*e',
)

BMEdge._fields_ = fields(
    BMHeader, 'head',
    c_void_p, 'oflags',  # BMFlagLayer
    BMVert, '*v1',
    BMVert, '*v2',
    BMLoop, '*l',
    BMDiskLink, 'v1_disk_link',
    BMDiskLink, 'v2_disk_link',
)

BMLoop._fields_ = fields(
    BMHeader, 'head',

    BMVert, '*v',
    BMEdge, '*e',
    BMFace, '*f',

    BMLoop, '*radial_next',
    BMLoop, '*radial_prev',

    BMLoop, '*next',
    BMLoop, '*prev',
)


class BMFace(Structure):
    _fields_ = fields(
        BMHeader, 'head',
        c_void_p, 'oflags',  # BMFlagLayer
        c_void_p, 'l_first',  # BMLoop
        c_int, 'len',
        c_float, 'no[3]',
        c_short, 'mat_nr',
    )


class BMesh(Structure):
    _fields_ = fields(
        c_int, 'totvert', 'totedge', 'totloop', 'totface',
        c_int, 'totvertsel', 'totedgesel', 'totfacesel',

        c_char, 'elem_index_dirty',

        c_char, 'elem_table_dirty',

        c_void, '*vpool', '*epool', '*lpool', '*fpool',  # BLI_mempool

        BMVert, '**vtable',
        BMEdge, '**etable',
        BMFace, '**ftable',

        c_int, 'vtable_tot',
        c_int, 'etable_tot',
        c_int, 'ftable_tot',

        c_void, '*vtoolflagpool', '*etoolflagpool', '*ftoolflagpool',  # struct BLI_mempool

        c_int, 'toolflag_index',
        c_void, '*currentop',  # struct BMOperator

        CustomData, 'vdata', 'edata', 'ldata', 'pdata',
    )


class BMWalker(Structure):
    _fields_ = fields(
        c_char, 'begin_htype',  # only for validating input
        c_void_p, 'begin',  # void  (*begin) (struct BMWalker *walker, void *start)
        c_void_p, 'step',  # void *(*step)  (struct BMWalker *walker)
        c_void_p, 'yield',  # void *(*yield) (struct BMWalker *walker)
        c_int, 'structsize',
        c_int, 'order',  # enum BMWOrder
        c_int, 'valid_mask',

        # runtime
        c_int, 'layer',

        BMesh, '*bm',
        c_void_p, 'worklist',  # BLI_mempool
        ListBase, 'states',

        # these masks are to be tested against elements BMO_elem_flag_test(),
        # should never be accessed directly only through BMW_init() and bmw_mask_check_*() functions
        c_short, 'mask_vert',
        c_short, 'mask_edge',
        c_short, 'mask_face',

        c_int, 'flag',  # enum BMWFlag

        c_void_p, 'visit_set',  # struct GSet *visit_set
        c_void_p, 'visit_set_alt',  # struct GSet *visit_set_alt
        c_int, 'depth',

        c_int, 'dummy[4]',  # enumのサイズが不明な為
    )


###############################################################################
# Node
###############################################################################
class bNodeSocket(Cast, Structure):
    """DNA_node_types.h: 86"""
    # 選択状態は flag & SELECT

bNodeSocket._fields_ = fields(
    bNodeSocket, '*next', '*prev', '*new_sock',
    c_void, '*prop',  # IDProperty

    c_char, 'identifier[64]',

    c_char, 'name[64]',

    c_void, '*storage',

    c_short, 'type', 'flag',
    c_short, 'limit',
    c_short, 'in_out',
    c_void, '*typeinfo',  # struct bNodeSocketType
    c_char, 'idname[64]',

    c_float, 'locx', 'locy',

    # 以下略
)


class bNode(Cast, Structure):
    """DNA_node_types.h: 86"""
    # 選択状態は flag & SELECT


bNode._fields_ = fields(
    bNode, '*next', '*prev', '*new_node',

    c_void, '*prop',  # IDProperty  # user-defined properties

    c_void, '*typeinfo',  # struct bNodeType  # runtime type information
    c_char, 'idname[64]',  # runtime type identifier

    c_char, 'name[64]',  # MAX_NAME
    c_int, 'flag',
    c_short, 'type', 'pad',
    c_short, 'done', 'level',  # both for dependency and sorting
    c_short, 'lasty', 'menunr',  # lasty: check preview render status, menunr: browse ID blocks
    c_short, 'stack_index',  # for groupnode, offset in global caller stack
    c_short, 'nr',  # number of this node in list, used for UI exec events
    c_float, 'color[3]',  # custom user-defined color

    ListBase, 'inputs', 'outputs',
    bNode, '*parent',  # parent node
    ID, '*id',  # optional link to libdata
    c_void, '*storage',  # custom data, must be struct, for storage in file
    bNode, '*original',  # the original node in the tree (for localized tree)
    ListBase, 'internal_links',  # list of cached internal links (input to output), for muted nodes and operators

    c_float, 'locx', 'locy',  # root offset for drawing (parent space)
    c_float, 'width', 'height',  # node custom width and height
    c_float, 'miniwidth',  # node width if hidden
    c_float, 'offsetx', 'offsety',  # additional offset from loc
    c_float, 'anim_init_locx',  # initial locx for insert offset animation
    c_float, 'anim_ofsx',  # offset that will be added to locx for insert offset animation

    c_int, 'update',  # update flags

    c_char, 'label[64]',  # custom user-defined label, MAX_NAME
    c_short, 'custom1', 'custom2',  # to be abused for buttons
    c_float, 'custom3', 'custom4',

    c_short, 'need_exec', 'exec',  # need_exec is set as UI execution event, exec is flag during exec
    c_void, '*threaddata',  # optional extra storage for use in thread (read only then!)
    rctf, 'totr',  # entire boundbox (worldspace)
    rctf, 'butr',  # optional buttons area
    rctf, 'prvr',  # optional preview area

    c_short, 'preview_xsize', 'preview_ysize',  # reserved size of the preview rect
    c_int, 'pad2',
    c_void, '*block',  # struct uiBlock  # runtime during drawing
)


# 未使用
# class bNodeTree(Cast, Structure):
#     """DNA_node_types.h: 329"""
#
# bNodeTree._fields_ = fields(
#     ID, 'id',
#     c_void, '*adt',  # struct AnimData  # animation data (must be immediately after id for utilities to use it)
#
#     c_void, '*typeinfo',  # struct bNodeTreeType  # runtime type information
#     c_char, 'idname[64]',  # runtime type identifier
#
#     c_void, '*interface_type',  # struct StructRNA  # runtime RNA type of the group interface
#
#     c_void, '*gpd',  # struct bGPdata  # grease pencil data
#     c_float, 'view_center[2]',  # node tree stores own offset for consistent editor view
#
#     ListBase, 'nodes', 'links',
#
#     # 以下略
# )


###############################################################################
#
###############################################################################
def image_pixels_get(image):
    """Image.pixelsをnumpy.ndarrayとして返す。
    :type image: bpy.types.Image
    :return: 要素の型はfloat32でshapeは(row, col)。
    :rtype: numpy.ndarray
    """

    if not isinstance(image, bpy.types.Image):
        raise TypeError()

    image_pixels = image.pixels  # インスタンスは終わるまで残しとかないと駄目
    addr = id(image_pixels)
    bpy_prop = BPy_PropertyArrayRNA.cast(addr)
    ptr = cast(addressof(bpy_prop.ptr), POINTER(PointerRNA))
    prop = bpy_prop.prop
    pixels = np.zeros(len(image.pixels), dtype=np.float32)
    RNA_property_float_get_array(ptr, prop, c_void_p(pixels.ctypes.data))
    return pixels


def image_pixels_set(image, pixels):
    """Image.pixelsをpixelsで上書きする。
    :type image: bpy.types.Image
    :param pixels: 要素の型はfloat32にしておく必要がある。それ以外だと変換される。
        要素数の確認は行わないので注意。
    :type pixels: numpy.ndarray
    """

    if not isinstance(image, bpy.types.Image):
        raise TypeError()
    if not isinstance(pixels, np.ndarray):
        raise TypeError()
    if pixels.dtype != np.float32:
        pixels = pixels.astype(np.float32)

    image_pixels = image.pixels
    addr = id(image_pixels)
    bpy_prop = cast(addr, POINTER(BPy_PropertyArrayRNA)).contents
    ptr = cast(addressof(bpy_prop.ptr), POINTER(PointerRNA))
    prop = bpy_prop.prop
    RNA_property_float_set_array(ptr, prop, c_void_p(pixels.ctypes.data))


###############################################################################
def context_py_dict_get(context):
    """CTX_py_dict_get
    :type context: bpy.types.Context
    """
    addr = c_void_p(context.__class__.as_pointer(context))
    C = cast(addr, POINTER(bContext)).contents
    if C.data.py_context is None:  # NULL
        return None
    else:
        return cast(C.data.py_context, py_object).value


def context_py_dict_set(context, py_dict):
    """CTX_py_dict_set
    :type context: bpy.types.Context
    :type py_dict: dict | None
    :rtype: dict
    """
    py_dict_bak = context_py_dict_get(context)

    addr = c_void_p(context.__class__.as_pointer(context))
    C = cast(addr, POINTER(bContext)).contents
    if isinstance(py_dict, dict):
        C.data.py_context = c_void_p(id(py_dict))
    else:
        C.data.py_context = None  # NULL
    return py_dict_bak


def test_platform():
    return (platform.platform().split('-')[0].lower()
            not in {'darwin', 'windows'})


def context_py_dict_get_linux(context):
    """ctypes.CDLLを用いる方法"""

    if not test_platform():
        raise OSError('Linux only')
    blend_cdll = CDLL('')
    CTX_py_dict_get = blend_cdll.CTX_py_dict_get
    CTX_py_dict_get.restype = c_void_p
    addr = context.__class__.as_pointer(context)  # 警告抑制の為
    C = cast(addr, POINTER(bContext))
    ptr = CTX_py_dict_get(C)
    if ptr is not None:  # int
        return cast(ptr, py_object).value
    else:
        return None


def context_py_dict_set_linux(context, py_dict):
    """ctypes.CDLLを用いる方法"""

    if not test_platform():
        raise OSError('Linux only')
    blend_cdll = CDLL('')
    CTX_py_dict_set = blend_cdll.CTX_py_dict_set
    addr = context.__class__.as_pointer(context)  # 警告抑制の為
    C = cast(addr, POINTER(bContext))
    context_dict_back = context_py_dict_get(context)
    if py_dict is not None:
        CTX_py_dict_set(C, py_object(py_dict))
    else:
        # CTX_py_dict_set(C, py_object())
        CTX_py_dict_set(C, None)
    return context_dict_back


###############################################################################
class _Buffer_buf(ct.Union):
    _fields_ = [
        ('asbyte', ct.POINTER(ct.c_char)),
        ('asshort', ct.POINTER(ct.c_short)),
        ('asint', ct.POINTER(ct.c_int)),
        ('asfloat', ct.POINTER(ct.c_float)),
        ('asdouble', ct.POINTER(ct.c_double)),

        ('asvoid', ct.c_void_p),
    ]


class Buffer(ct.Structure):
    _anonymous_ = ('_head',)
    _fields_ = [
        ('_head', PyObject_VAR_HEAD),
        ('parent', ct.py_object),

        # type:
        #     GL_BYTE: 5120, GL_SHORT: 5122, GL_INT: 5124, GL_FLOAT: 5126
        #     GL_DOUBLE: 5130
        ('type', ct.c_int),
        ('ndimensions', ct.c_int),
        ('dimensions', ct.POINTER(ct.c_int)),

        ('buf', _Buffer_buf),
    ]


def buffer_to_ctypes(buf):
    import ctypes as ct
    import bgl
    c_buf_p = ct.cast(id(buf), ct.POINTER(Buffer))
    c_buf = c_buf_p.contents
    types = {
        bgl.GL_BYTE: ct.c_byte,
        bgl.GL_SHORT: ct.c_short,
        bgl.GL_INT: ct.c_int,
        bgl.GL_FLOAT: ct.c_float,
        bgl.GL_DOUBLE: ct.c_double
    }
    t = types[c_buf.type]
    n = c_buf.ndimensions
    for i in range(n - 1, -1, -1):
        t *= c_buf.dimensions[i]
    ct_buf = ct.cast(c_buf.buf.asvoid, ct.POINTER(t)).contents
    return ct_buf


def buffer_to_ndarray(buf):
    import numpy as np
    return np.ctypeslib.as_array(buffer_to_ctypes(buf))


###############################################################################
# ポインタアドレスからpythonオブジェクトを生成する。
# bpy.context.active_object.as_pointer() -> int の逆の動作。

# class BlenderRNA(Structure):
#     _fields_ = [
#         ('structs', ListBase),
#     ]

# 未使用
def create_python_object(id_addr, type_name, addr):
    """アドレスからpythonオブジェクトを作成する。
    area = create_python_object(C.screen.as_pointer(), 'Area',
                                C.area.as_pointer())
    obj = create_python_object(C.active_object.as_pointer(), 'Object',
                               C.active_object.as_pointer())

    :param id_addr: id_dataのアドレス。自身がIDオブジェクトならそれを指定、
        そうでないなら所属するIDオブジェクトのアドレスを指定する。
        AreaならScreen、ObjectならObjectのアドレスとなる。無い場合はNone。
        正しく指定しないと予期しない動作を起こすので注意。
    :type id_addr: int | None
    :param type_name: 型名。'Area', 'Object' 等。
        SpaceView3D等のSpaceのサブクラスは'Space'でよい。
    :type type_name: str
    :param addr: オブジェクトのアドレス。
    :type addr: int
    :rtype object
    """

    class _PointerRNA_id(Structure):
        _fields_ = [
            ('data', c_void_p),
        ]

    class PointerRNA(Structure):
        _fields_ = [
            ('id', _PointerRNA_id),
            ('type', c_void_p),  # StructRNA
            ('data', c_void_p),
        ]

    if (not isinstance(id_addr, (int, type(None))) or
            not isinstance(type_name, str) or
            not isinstance(addr, int)):
        raise TypeError('引数の型が間違ってる。(int, str, int)')

    blend_cdll = CDLL('')
    RNA_pointer_create = blend_cdll.RNA_pointer_create
    RNA_pointer_create.restype = None
    pyrna_struct_CreatePyObject = blend_cdll.pyrna_struct_CreatePyObject
    pyrna_struct_CreatePyObject.restype = py_object
    try:
        RNA_type = getattr(blend_cdll, 'RNA_' + type_name)
    except AttributeError:
        raise ValueError("型名が間違ってる。'{}'".format(type_name))

    ptr = PointerRNA()
    RNA_pointer_create(c_void_p(id_addr), RNA_type, c_void_p(addr), byref(ptr))
    return pyrna_struct_CreatePyObject(byref(ptr))


class SnapObjects:
    """
    使用例:
    class Operator(bpy.types.Operator):
        def modal(self, context, event):
            mval = event.mouse_region_x, event.mouse_region_y
            r = self.snap_objects.snap(context, mval, 'VERTEX')
            if r:
                # keys: 'location', 'normal', 'index', 'object'
                # location,normalはworld座標
                ...

            # mesh等が更新されたらキャッシュ等を再生成
            self.snap_objects.update()

            # オペレーター終了時には開放を忘れない。
            __del__で開放するようにしているが、context.modeの変更で落ちる為
            手動で行う。
            self.snap_objects.free()
            return {'FINISHED'}

        def invoke(self, context, event):
            self.snap_objects = SnapObjects(context)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}

    このクラスを丸々コピペして動くようにcreate_python_object等を
    メソッドにしている

    """

    # enum SnapSelect
    SNAP_ALL = 0
    SNAP_NOT_SELECTED = 1
    SNAP_NOT_ACTIVE = 2

    SNAP_MIN_DISTANCE = 30

    SNAP_OBJECT_USE_CACHE = 1 << 0

    # tool_settings.snap_mode
    # SCE_SNAP_MODE_INCREMENT = 0
    SCE_SNAP_MODE_VERTEX = 1
    SCE_SNAP_MODE_EDGE = 2
    SCE_SNAP_MODE_FACE = 3
    # SCE_SNAP_MODE_VOLUME = 4
    # SCE_SNAP_MODE_NODE_X = 5
    # SCE_SNAP_MODE_NODE_Y = 6
    # SCE_SNAP_MODE_NODE_XY = 7
    # SCE_SNAP_MODE_GRID = 8

    BM_ELEM_SELECT = 1 << 0
    BM_ELEM_HIDDEN = 1 << 1

    def __init__(self, context=None):
        self.object_context = None
        if context:
            self.ensure(context)

    def __del__(self):
        self.free()

    def snap_object_context_create_view3d(self, context):
        import bpy
        import ctypes as ct
        cdll = ct.CDLL('')
        func = cdll.ED_transform_snap_object_context_create_view3d
        func.restype = ct.c_void_p

        # area = context.area
        # if not area:
        #     raise ValueError('context.areaがNone')
        # if area.type != 'VIEW_3D':
        #     raise ValueError("context.areaが3DViewではない")

        region = context.region
        if not region:
            raise ValueError('context.regionがNone')
        if region.type != 'WINDOW':
            raise ValueError("context.region.typeが'WINDOW'ではない")
        ar = ct.c_void_p(region.as_pointer())

        view3d = context.space_data
        if not isinstance(view3d, bpy.types.SpaceView3D):
            raise ValueError('context.space_dataがSpaceView3Dではない')
        v3d = ct.c_void_p(view3d.as_pointer())

        bl_main = ct.c_void_p(bpy.data.as_pointer())
        scn = ct.c_void_p(context.scene.as_pointer())
        object_context = func(bl_main, scn, self.SNAP_OBJECT_USE_CACHE, ar, v3d)
        return ct.c_void_p(object_context)

    def ensure(self, context):
        if not self.object_context:
            self.object_context = self.snap_object_context_create_view3d(
                context)

    def update(self, context):
        if self.object_context:
            self.free()
        self.object_context = self.snap_object_context_create_view3d(context)

    def free(self):
        # 開放前にcontext.modeを切り替えてはならない。落ちる。
        import ctypes as ct
        cdll = ct.CDLL('')
        if self.object_context:
            cdll.ED_transform_snap_object_context_destroy(self.object_context)
            self.object_context = None

    def set_editmesh_callbacks(self):
        # ED_transform_snap_object_context_set_editmesh_callbacks(
        #     object_context,
        #        (bool(*)(BMVert *, void *))
        # BM_elem_cb_check_hflag_disabled,
        # bm_edge_is_snap_target,
        # bm_face_is_snap_target,
        # SET_UINT_IN_POINTER((BM_ELEM_SELECT | BM_ELEM_HIDDEN)))

        import ctypes as ct
        cdll = ct.CDLL('')
        func = cdll.ED_transform_snap_object_context_set_editmesh_callbacks
        vfunc = ct.c_void_p(ct.addressof(cdll.BM_elem_cb_check_hflag_disabled))
        # FIXME: efunc,ffuncはstatucで参照出来ない為このコードは動かない
        efunc = ct.c_void_p(ct.addressof(cdll.bm_edge_is_snap_target))
        ffunc = ct.c_void_p(ct.addressof(cdll.bm_face_is_snap_target))

        user_data = ct.c_void_p(self.BM_ELEM_SELECT | self.BM_ELEM_HIDDEN)
        func(self.object_context, vfunc, efunc, ffunc, user_data)

    def create_python_object(self, id_addr, type_name, addr):
        """アドレスからpythonオブジェクトを作成する。
        area = create_python_object(C.screen.as_pointer(), 'Area',
                                    C.area.as_pointer())
        obj = create_python_object(C.active_object.as_pointer(), 'Object',
                                   C.active_object.as_pointer())

        :param id_addr: id_dataのアドレス。自身がIDオブジェクトならそれを指定、
            そうでないなら所属するIDオブジェクトのアドレスを指定する。
            AreaならScreen、ObjectならObjectのアドレスとなる。無い場合はNone。
            正しく指定しないと予期しない動作を起こすので注意。
        :type id_addr: int | None
        :param type_name: 型名。'Area', 'Object' 等。
            SpaceView3D等のSpaceのサブクラスは'Space'でよい。
        :type type_name: str
        :param addr: オブジェクトのアドレス。
        :type addr: int
        :rtype object
        """

        import ctypes as ct

        class _PointerRNA_id(ct.Structure):
            _fields_ = [
                ('data', ct.c_void_p),
            ]

        class PointerRNA(ct.Structure):
            _fields_ = [
                ('id', _PointerRNA_id),
                ('type', ct.c_void_p),  # StructRNA
                ('data', ct.c_void_p),
            ]

        if (not isinstance(id_addr, (int, type(None))) or
                not isinstance(type_name, str) or
                not isinstance(addr, int)):
            raise TypeError('引数の型が間違ってる。(int, str, int)')

        cdll = ct.CDLL('')
        RNA_pointer_create = cdll.RNA_pointer_create
        RNA_pointer_create.restype = None
        pyrna_struct_CreatePyObject = cdll.pyrna_struct_CreatePyObject
        pyrna_struct_CreatePyObject.restype = ct.py_object
        try:
            RNA_type = getattr(cdll, 'RNA_' + type_name)
        except AttributeError:
            raise ValueError("型名が間違ってる。'{}'".format(type_name))

        ptr = PointerRNA()
        RNA_pointer_create(ct.c_void_p(id_addr), RNA_type, ct.c_void_p(addr),
                           ct.byref(ptr))
        return pyrna_struct_CreatePyObject(ct.byref(ptr))

    def snap(self, context, mval, snap_element=None, snap_select='ALL',
             dist_px=SNAP_MIN_DISTANCE):
        import ctypes as ct
        from mathutils import Vector

        cdll = ct.CDLL('')

        if not self.object_context:
            self.ensure(context)

        mval = (ct.c_float * 2)(*mval)
        dist_px = ct.c_float(dist_px)
        r_loc = (ct.c_float * 3)()
        r_no = (ct.c_float * 3)()
        r_index = ct.c_int()
        r_ob = ct.c_void_p()
        actob = context.active_object

        class SnapObjectParams(ct.Structure):
            _fields_ = [
                ('snap_select', ct.c_char),
                ('use_object_edit_cage', ct.c_ubyte),  # unsigned int
            ]

        if snap_select not in {'ALL', 'NOT_SELECTED', 'NOT_ACTIVE'}:
            raise ValueError(
                "snap_select not in {'ALL', 'NOT_SELECTED', 'NOT_ACTIVE'}")
        d = {'ALL': self.SNAP_ALL,
             'NOT_SELECTED': self.SNAP_NOT_SELECTED,
             'SNAP_NOT_ACTIVE': self.SNAP_NOT_ACTIVE
             }
        snap_select = d[snap_select]
        params = SnapObjectParams(snap_select, actob and actob.mode == 'EDIT')

        # self.set_editmesh_callbacks()

        if snap_element:
            snap_mode = snap_element
        else:
            snap_mode = context.tool_settings.snap_element
        if snap_mode not in {'VERTEX', 'EDGE', 'FACE'}:
            if snap_element:
                raise ValueError(
                    "snap_element not in {'VERTEX', 'EDGE', 'FACE'}")
            else:
                return None
        d = {
            # 'INCREMENT': SCE_SNAP_MODE_INCREMENT,
            'VERTEX': self.SCE_SNAP_MODE_VERTEX,
            'EDGE': self.SCE_SNAP_MODE_EDGE,
            'FACE': self.SCE_SNAP_MODE_FACE,
            # 'VOLUME': SCE_SNAP_MODE_VOLUME,
        }
        snap_to = d[snap_mode]

        found = cdll.ED_transform_snap_object_project_view3d_ex(
            self.object_context, snap_to, ct.byref(params), mval,
            ct.byref(dist_px), None, r_loc, r_no, ct.byref(r_index),
            ct.byref(r_ob),
        )

        if found:
            ob = self.create_python_object(r_ob.value, 'Object', r_ob.value)
            return {'location': Vector(r_loc),
                    'normal': Vector(r_no),
                    'index': r_index.value,
                    'object': ob}
        else:
            return None
