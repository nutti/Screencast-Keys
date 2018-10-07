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


import bpy


def register_class(cls):
    if hasattr(cls, 'register_pre'):
        cls.register_pre()
    bpy.utils.register_class(cls)
    if hasattr(cls, 'register_post'):
        cls.register_post()


def unregister_class(cls):
    if hasattr(cls, 'unregister_pre'):
        cls.unregister_pre()
    bpy.utils.unregister_class(cls)
    if hasattr(cls, 'unregister_post'):
        cls.unregister_post()


def register_module(module=None, verbose=False, ignore=()):
    """
    :type module: str
    :type verbose: bool
    :type ignore: list[str]
    """
    if verbose:
        print("bpy.utils.register_module(%r): ..." % module)
    root_module = module.split('.')[0]
    is_registered = False
    for cls in bpy.utils._bpy_module_classes(root_module, is_registered=False):
        if not cls.__module__.startswith(module):
            continue
        is_submodule = False
        for submodule in ignore:
            if cls.__module__.startswith(module + '.' + submodule):
                is_submodule = True
                break
        if is_submodule:
            continue

        if verbose:
            print("    %r" % cls)
        try:
            register_class(cls)
        except:
            print("bpy.utils.register_module(): "
                  "failed to registering class %r" % cls)
            import traceback
            traceback.print_exc()
        is_registered = True
    if verbose:
        print("done.\n")
    if not is_registered:
        raise Exception("register_module(%r): defines no classes" % module)


def unregister_module(module=None, verbose=False, ignore=()):
    """bpy.utils.unregister_module()がそのままでは使えないのでその改変。
    :type module: str
    :type verbose: bool
    :type ignore: list[str]
    """
    if verbose:
        print("bpy.utils.unregister_module(%r): ..." % module)
    root_module = module.split('.')[0]

    for cls in bpy.utils._bpy_module_classes(root_module, is_registered=True):
        if not cls.__module__.startswith(module):
            continue
        is_submodule = False
        for submodule in ignore:
            if cls.__module__.startswith(module + '.' + submodule):
                is_submodule = True
                break
        if is_submodule:
            continue

        if verbose:
            print("    %r" % cls)
        try:
            bpy.utils.unregister_class(cls)
        except:
            print("bpy.utils.unregister_module(): "
                  "failed to unregistering class %r" % cls)
            import traceback
            traceback.print_exc()
    if verbose:
        print("done.\n")


def get_keymap(name, keyconfig='addon'):
    """KeyMaps.new()の結果を返す。name以外の引数は勝手に補間してくれる。

    ※ registerinfo._AddonRegisterInfoKeyMap.get_keymapメソッドと一緒。

    :type name: str
    :param keyconfig: 'addon' or 'user' or 'blender' or 'default'
    :type keyconfig: str
    :rtype: bpy.types.KeyMap
    """
    import bpy_extras.keyconfig_utils

    # Documentは無いのでblenderを起動してis_modalを確認するしか方法が無い
    modal_keymaps = {
        'View3D Gesture Circle', 'Gesture Border',
        'Gesture Zoom Border', 'Gesture Straight Line',
        'Standard Modal Map', 'Knife Tool Modal Map',
        'Transform Modal Map', 'Paint Stroke Modal', 'View3D Fly Modal',
        'View3D Walk Modal', 'View3D Rotate Modal', 'View3D Move Modal',
        'View3D Zoom Modal', 'View3D Dolly Modal', }

    keyconfigs = bpy.context.window_manager.keyconfigs
    if keyconfig == 'addon':  # 'Blender Addon'
        kc = keyconfigs.addon
    elif keyconfig == 'user':  # 'Blender User'
        kc = keyconfigs.user
    elif keyconfig in {'default', 'blender'}:  # 'Blender'
        kc = keyconfigs.default
    else:
        raise ValueError()
    if not kc:
        return None

    # if 'INVALID_MODAL_KEYMAP' and name in modal_keymaps:
    #     msg = "not support modal keymap: '{}'".format(name)
    #     raise ValueError(msg)

    def get(ls, name):
        for keymap_name, space_type, region_type, children in ls:
            if keymap_name == name:
                is_modal = keymap_name in modal_keymaps
                return kc.keymaps.new(keymap_name, space_type=space_type,
                                      region_type=region_type,
                                      modal=is_modal)
            elif children:
                km = get(children, name)
                if km:
                    return km

    km = get(bpy_extras.keyconfig_utils.KM_HIERARCHY, name)
    if not km:
        msg = "Keymap '{}' not in builtins".format(name)
        raise ValueError(msg)
    return km


def py_idname(name):
    """WM_operator_py_idname
    SOME_OT_op -> some.op
    """
    if '_OT_' in name:
        mod, func = name.split('_OT_')
        return mod.lower() + '.' + func
    else:
        return name


def bl_idname(name):
    """WM_operator_bl_idname
    some.op -> SOME_OT_op
    """
    if '.' in name:
        mod, func = name.split('.')
        return mod.upper() + '_OT_' + func
    else:
        return name


def operator_call(op, *args, _scene_update=True, **kw):
    """vawmより
    operator_call(bpy.ops.view3d.draw_nearest_element,
                  'INVOKE_DEFAULT', type='ENABLE', _scene_update=False)
    """
    import bpy
    from _bpy import ops as ops_module

    BPyOpsSubModOp = op.__class__
    op_call = ops_module.call
    context = bpy.context

    # Get the operator from blender
    wm = context.window_manager

    # run to account for any rna values the user changes.
    if _scene_update:
        BPyOpsSubModOp._scene_update(context)

    if args:
        C_dict, C_exec, C_undo = BPyOpsSubModOp._parse_args(args)
        ret = op_call(op.idname_py(), C_dict, kw, C_exec, C_undo)
    else:
        ret = op_call(op.idname_py(), None, kw)

    if 'FINISHED' in ret and context.window_manager == wm:
        if _scene_update:
            BPyOpsSubModOp._scene_update(context)

    return ret


def is_main_loop_scene_update(context, scene):
    """bpy.app.handlers.scene_update_pre(post) へ追加した関数の中で呼ぶ。
    それがメインループから呼ばれたものか否かを返す。完全な判定は期待できない。
    :type context: bpy.types.Context
    :param scene: bpy.app.handlers.scene_update_pre(post) の引数。
    :type scene: bpy.types.Scene
    :rtype: bool
    """
    win = context.window
    scr = context.screen
    scn = context.scene
    if win and scr and scn:
        if scr == win.screen and scn == scr.scene == scene:
            if not context.region:  # wm_event_do_notifiers()参照
                return True
    return False


class AutoSaveManager:
    """
    modal operator の実行中は auto save が無効化されるので、このクラスを使って
    ファイルを保存する。

    例:

    class ModalOperator(bpy.types.Operator):
        def modal(self, context, event):
            auto_save_manager.save(context)

    auto_save_manager = utils.AutoSaveManager()

    def register():
        auto_save_manager.register()

    def unregister():
        auto_save_manager.unregister()

    """

    ignore_operators = [
        'VIEW3D_OT_region_ruler',
        'VIEW3D_OT_draw_nearest_element',
        'WM_OT_screencast_keys',
    ]

    ATTR = [bpy.types.WindowManager, 'auto_save_manager']

    # @classmethod
    # def get_callback(cls):
    #     handlers = bpy.app.handlers.scene_update_pre
    #     for func in handlers:
    #         if hasattr(func, '__func__'):
    #             f = func.__func__
    #             if hasattr(f, '__qualname__'):
    #                 if f.__qualname__ == cls.__qualname__ + '.callback':
    #                     return func

    # TODO: クラスメソッドにする
    def global_instance(self, create=True):
        """
        :rtype: AutoSaveManager
        """
        wm_type, attr = self.ATTR
        inst = getattr(wm_type, attr, None)
        if not inst and create:
            setattr(wm_type, attr, self)
            inst = self
        return inst

    def users_load(self):
        self_ = self.global_instance(create=False)
        return [obj for obj in self_.users if obj.registered_load]

    def users_scene_update(self):
        self_ = self.global_instance(create=False)
        return [obj for obj in self_.users if obj.registered_scene_update]

    def register(self, load=True, scene_update=False):
        if not self.registered:
            self.registered = True
            self_ = self.global_instance()
            self_.users.append(self)
            if load:
                if not self.registered_load:
                    self.registered_load = True
                    if len(self_.users_load()) == 1:
                        bpy.app.handlers.load_post.append(self_.load_callback)
            if scene_update:
                if not self.registered_scene_update:
                    self.registered_scene_update = True
                    if len(self_.users_scene_update()) == 1:
                        bpy.app.handlers.scene_update_pre.append(
                            self_.scene_update_callback)

    def unregister(self):
        if self.registered:
            self.registered = False
            self_ = self.global_instance()
            self_.users.remove(self)
            # 不要なコールバックの削除
            if self.registered_load:
                self.registered_load = False
                if not self_.users_load():
                    bpy.app.handlers.load_post.remove(self_.load_callback)
            if self.registered_scene_update:
                self.registered_scene_update = False
                if not self_.users_scene_update():
                    bpy.app.handlers.scene_update_pre.remove(
                        self_.scene_update_callback)

            # 入れ替え
            wm_type, attr = self_.ATTR
            if self_.users:
                other = self_.users[0]
                other.path = self_.path
                other.save_time = self_.save_time
                other.failed_count = self_.failed_count
                other.users[:] = self_.users
                if self_.users_load():
                    bpy.app.handlers.load_post.remove(self_.load_callback)
                    bpy.app.handlers.load_post.append(other.load_callback)
                if self_.users_scene_update():
                    bpy.app.handlers.scene_update_pre.remove(
                        self_.scene_update_callback)
                    bpy.app.handlers.scene_update_pre.append(
                        other.scene_update_callback)
                setattr(wm_type, attr, other)
            else:
                delattr(wm_type, attr)

    @property
    def load_callback(self):
        # persistentのデコレート対象は関数限定(メソッド不可)で、一番外側で
        # デコレートしていないと無意味って事でわざわざこんな事してる。
        if not self._load_callback:
            @bpy.app.handlers.persistent
            def load_callback(scene):
                import time
                self_ = self.global_instance()
                self_.save_time = time.time()
                self_.failed_count = 0
            self._load_callback = load_callback
        return self._load_callback

    @property
    def scene_update_callback(self):
        if not self._scene_update_callback:
            @bpy.app.handlers.persistent
            def scene_update_callback(scene):
                if is_main_loop_scene_update(bpy.context, scene):
                    self_ = self.global_instance()
                    self_.save(bpy.context)
            self._scene_update_callback = scene_update_callback
        return self._scene_update_callback

    def __init__(self):
        import logging
        import time

        self.logger = logger = logging.getLogger(__name__).getChild(
            self.__class__.__name__)
        """:type: logging.Logger"""
        logger.propagate = False
        logger.setLevel(logging.WARNING)
        handler = logging.StreamHandler()
        handler.setLevel(logging.NOTSET)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] '
            '[%(name)s.%(funcName)s():%(lineno)d]: '
            '%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self.users = []

        self.path = ''
        self.save_time = time.time()
        self.failed_count = 0

        self.registered = False
        self.registered_load = False
        self.registered_scene_update = False

        self._load_callback = None
        self._scene_update_callback = None

    def save(self, context):
        """
        :type context: bpy.context
        :rtype: bool
        """
        import os
        import platform
        import time
        import traceback

        try:
            from . import structures
        except:
            traceback.print_exc()
            structures = None

        file_prefs = context.user_preferences.filepaths
        if not file_prefs.use_auto_save_temporary_files:
            return None

        self_ = self.global_instance()

        cur_time = time.time()
        save_interval = file_prefs.auto_save_time * 60
        ofs_time = 10.0 * self_.failed_count
        # 指定時間に達しているか確認
        if cur_time - self_.save_time < save_interval + ofs_time:
            return None

        if structures:
            system_auto_save = True
            for win in context.window_manager.windows:
                handlers = structures.wmWindow.modal_handlers(
                    win)
                for handler, idname, sa, ar, rt in handlers:
                    if handler.op:
                        system_auto_save = False
                        if idname not in self_.ignore_operators:
                            self_.logger.debug(
                                "Modal operator <{}> is running. "
                                "Skip auto save".format(idname))
                            return None
            if system_auto_save:
                return None

        # 保存先となるパスを生成。wm_autosave_location()参照
        if bpy.data.is_saved:
            file_name = os.path.basename(bpy.data.filepath)
            save_base_name = os.path.splitext(file_name)[0] + '.blend'
        else:
            if platform.system() not in ('Linux', 'Windows'):
                # os.gitpid()が使用出来ず、ファイル名が再現出来無い為
                return None
            pid = os.getpid()
            save_base_name = str(pid) + '.blend'
        save_dir = os.path.normpath(
            os.path.join(bpy.app.tempdir, os.path.pardir))
        if platform.system() == 'Windows' and not os.path.exists(save_dir):
            save_dir = bpy.utils.user_resource('AUTOSAVE')
        save_path = self_.path = os.path.join(save_dir, save_base_name)

        # 既にファイルが存在して更新時間がself.save_timeより進んでいたら
        # その時間と同期する
        if os.path.exists(save_path):
            st = os.stat(save_path)
            if self_.save_time < st.st_mtime:
                self_.save_time = st.st_mtime
                self_.logger.debug("Auto saved file '{}' is updated".format(
                    save_path))
            if cur_time - self_.save_time < save_interval + ofs_time:
                return None

        self_.logger.debug("Try auto save '{}' ...".format(save_path))

        # ディレクトリ生成
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except:
                self_.logger.error("Unable to save '{}'".format(save_dir),
                                   exc_info=True)
                self_.failed_count += 1
                return False

        # cyclesレンダリング直後の場合、サムネイル作成でよく落ちるので切る。
        use_save_preview = file_prefs.use_save_preview_images
        file_prefs.use_save_preview_images = False
        # Save
        try:
            bpy.ops.wm.save_as_mainfile(
                False, filepath=save_path, compress=False, relative_remap=True,
                copy=True, use_mesh_compat=False)
        except:
            self_.logger.error("Unable to save '{}'".format(save_dir),
                               exc_info=True)
            self_.failed_count += 1
            saved = False
        else:
            self_.logger.info("Auto Save '{}'".format(save_path))
            # 設定し直す事で内部のタイマーがリセットされる
            self_.save_time = os.stat(save_path).st_mtime
            self_.failed_count = 0
            file_prefs.auto_save_time = file_prefs.auto_save_time
            saved = True
        file_prefs.use_save_preview_images = use_save_preview
        return saved
