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


from ctypes import *
import functools
import logging

from .utils.structures import wmWindow, wmEventHandler

import bpy


logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
_handler = logging.StreamHandler()
_handler.setLevel(logging.NOTSET)
_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
_handler.setFormatter(_formatter)
logger.addHandler(_handler)


class ModalHandlerManager:
    """
    常時バックグラウンドで動作する({'PASS_THROUGH'}を返す)ようなModalOperator
    を補助する。

    効果:
    ほぼ全てのイベントでmodal()が呼び出されるようになる。
    全てのWindowに対して自動でオペレータを起動する。

    副作用、注意点:
    常時監視する為負荷が増える。
    wmWindow.modalhandlersを並び替えるので落ちる可能性がある。
    基本的にこのクラスを継承して使用しない事。
    bl_optionsで'UNDO'を有効にしてはならない。
    """

    RENDERING_TIMER_STEP = 1.0 / 60  # min: 0.005s

    _render_timers = {}
    _is_rendering = False

    managers = []  # 全てのインスタンス
    """:type: list[ModalHandlerManager]"""

    NORMAL = 0
    AUTO_START = 2

    # invokeの返り値に含めることでModalHandlerManagerでの処理を飛ばす
    SKIP_MANAGER = 'SKIP_MANAGER'

    def __init__(self, idname, all_windows=True, callback=None,
                 args=('INVOKE_DEFAULT',), kwargs=None,
                 render_timer_step=RENDERING_TIMER_STEP):
        """
        :param idname: ModalOperator e.g. 'mod.function'
        :type idname: str
        :param all_windows: 新規Windowに対して自動でオペレータを起動し、
            ModalHandlerを追加する。
        :type all_windows: bool
        :param callback: 再起動・自動起動の際に実行。
            第一引数にcontext, 第ニ引数にevent, 第三引数に新規operator。
            再起動の場合は第四引数にそのwindowで動作中のoperator、
            自動起動の場合は第四引数はNoneとなる。
        :type callback: collections.abc.Callable
        :param args: operator実行時に渡す引数
        :type args: list | tuple
        :param kwargs: operator実行時に渡す引数
        :type kwargs: dict
        :param render_timer_step:
        :type render_timer_step: float
        """

        # idname: TRANSFORM_OT_translate
        # idname_py: transform.translate
        if '.' not in idname and '_OT_' in idname:
            mod, func = idname.split('_OT_')
            idname_py = mod.lower() + '.' + func
        else:
            idname_py = idname
            mod, func = idname_py.split('.')
            idname = mod.upper() + '_OT_' + func
        self.idname = idname
        self.idname_py = idname_py
        self.args = args
        self.kwargs = kwargs
        self.all_windows = all_windows

        self.callback = callback
        self.render_timer_step = render_timer_step

        # 値がNoneとなるのはinvoke()の時のみ
        self.operators = {}
        """:type: dict[int, T]"""

        self.status = self.NORMAL

        self.managers.append(self)

    def sort_modal_handlers(self, window):
        if not window:
            return

        win = wmWindow.cast(window)
        ptr = wmEventHandler.cast(win.modalhandlers.first, contents=False)

        import time
        i = 0
        indices = []
        while ptr:
            # http://docs.python.jp/3/library/ctypes.html#surprises
            # この辺りの事には注意する事
            handler = ptr.contents
            if handler.op:
                op = handler.op.contents
                ot = op.type.contents
                if ot.idname:
                    idname = ot.idname.decode()
                    if idname == self.idname:
                        indices.append(i)
                        # return op.py_instance == self
            ptr = handler.next
            i += 1
        if indices:
            handlers = win.modalhandlers
            for count, index in enumerate(indices):
                if index != count:
                    prev = handlers.find(index - 2)
                    handler = handlers.find(index)
                    handlers.remove(handler)
                    handlers.insert_after(prev, handler)

    @staticmethod
    def _operator_call(op, args=None, kwargs=None, scene_update=True):
        from _bpy import ops as ops_module

        if isinstance(op, str):
            mod, func = op.split('.')
            op = getattr(getattr(bpy.ops, mod), func)

        BPyOpsSubModOp = op.__class__
        op_call = ops_module.call
        context = bpy.context

        # Get the operator from blender
        wm = context.window_manager

        # run to account for any rna values the user changes.
        if scene_update:
            BPyOpsSubModOp._scene_update(context)

        if not args:
            args = ()
        if not kwargs:
            kwargs = {}
        if args:
            C_dict, C_exec, C_undo = BPyOpsSubModOp._parse_args(args)
            ret = op_call(op.idname_py(), C_dict, kwargs, C_exec, C_undo)
        else:
            ret = op_call(op.idname_py(), None, kwargs)

        if 'FINISHED' in ret and context.window_manager == wm:
            if scene_update:
                BPyOpsSubModOp._scene_update(context)

        return ret

    def _parse_args(self, context, override_context=None):
        override = op_context = undo = None
        if self.args:
            for arg in self.args:
                if isinstance(arg, dict):
                    override = arg
                elif isinstance(arg, str):
                    op_context = arg
                elif isinstance(arg, bool):
                    undo = arg

        # override
        if override_context:
            if not override:
                override = context.copy()
            else:
                override = override.copy()
            override.update(override_context)
        # operator context
        if not op_context or not op_context.startswith('INVOKE'):
            op_context = 'INVOKE_DEFAULT'
        # merge
        args = []
        for value in (override, op_context, undo):
            if value is not None:
                args.append(value)

        return args

    def _auto_start_do(self, context, window):
        """必要無ければ自動起動を行わない"""
        addr = window.as_pointer()
        if addr in self.operators:
            return

        override = {}
        screen = context.screen
        scene = context.scene
        if not (context.window == window and screen and scene and
                screen == window.screen and scene == screen.scene):
            override['window'] = window
            override['screen'] = window.screen
            override['scene'] = window.screen.scene
            override['area'] = None
            override['region'] = None
        args = self._parse_args(context, override)

        # Call invoke()
        logger.debug('Auto Start')
        self.status = self.AUTO_START
        self._operator_call(self.idname_py, args, self.kwargs,
                            scene_update=False)
        self.status = self.NORMAL

    @classmethod
    def _scene_update_pre(cls, scn):
        """再起動及び新規windowへの自動起動"""
        context = bpy.context
        window = context.window
        screen = context.screen
        scene = context.scene
        if not window:
            return

        addr = window.as_pointer()
        running_any = False
        for m in cls.managers:
            m._cleanup(context)
            m.sort_modal_handlers(window)
            if m.is_running(context):
                running_any = True
                if addr not in m.operators:
                    if m.all_windows:
                        if (window and screen and scene and
                                screen == window.screen and
                                scene == screen.scene == scn):
                            # メインループなら必ずこれが一致する
                            m._auto_start_do(context, window)
        if not running_any:
            handlers = bpy.app.handlers.scene_update_pre
            if cls._scene_update_pre in handlers:
                handlers.remove(cls._scene_update_pre)
                logger.debug('Remove scene handler')

    @classmethod
    def _render_timer_add(cls):
        context = bpy.context
        wm = context.window_manager

        steps = [m.render_timer_step for m in cls.managers
                 if m.is_running(context)]
        if not steps or set(steps) == {0.0}:
            return
        else:
            step = min([f for f in steps if f != 0.0])

        for window in wm.windows:
            addr = window.as_pointer()
            if addr not in cls._render_timers:
                timer = wm.event_timer_add(step, window)
                cls._render_timers[addr] = timer
                logger.debug('Add timer')

    @classmethod
    def _render_init(cls, dummy):
        """bpy.app.handlers.render_init.append(_render_init)とだけ行い、
        他のhandlerの追加・削除はレンダリング完了／中断時に自動で行われる
        """
        if 0:
            cls._render_timer_add()
        cls._is_rendering = True

        # add render handlers
        # complete
        render_complete = bpy.app.handlers.render_complete
        if cls._render_complete not in render_complete:
            render_complete.append(cls._render_complete)
        # cancel
        render_cancel = bpy.app.handlers.render_cancel
        if cls._render_cancel not in render_cancel:
            render_cancel.append(cls._render_cancel)

        logger.debug('Add render complete/cancel handler')

        # NOTE: BLI_callback_exec(re->main, (ID *)scene,
        #                         BLI_CB_EVT_RENDER_INIT);

    @classmethod
    def _render_complete(cls, dummy):
        context = bpy.context
        if 0:
            wm = context.window_manager
            for timer in cls._render_timers.values():
                wm.event_timer_remove(timer)
                logger.debug('Remove timer')
            cls._render_timers.clear()
        cls._is_rendering = False

        # remove render handlers
        # init
        running = any([m.is_running(context) for m in cls.managers])
        if not running:
            render_init = bpy.app.handlers.render_init
            if cls._render_init in render_init:
                render_init.remove(cls._render_init)
        # complete
        render_complete = bpy.app.handlers.render_complete
        if cls._render_complete in render_complete:
            render_complete.remove(cls._render_complete)
        # cancel
        render_cancel = bpy.app.handlers.render_cancel
        if cls._render_cancel in render_cancel:
            render_cancel.remove(cls._render_cancel)
        logger.debug('Remove render handlers')

    @classmethod
    def _render_cancel(cls, dummy):
        cls._render_complete(dummy)

    @classmethod
    def _add_handlers(cls):
        # 削除は自動
        # Scene
        handlers = bpy.app.handlers.scene_update_pre
        if cls._scene_update_pre not in handlers:
            handlers.append(cls._scene_update_pre)
            logger.debug('Add scene handler')

        # Render
        handlers = bpy.app.handlers.render_init
        if cls._render_init not in handlers:
            handlers.append(cls._render_init)
            logger.debug('Add render int handler')

    @classmethod
    def terminate(cls):
        """handler,timer,operator全てを強制削除"""
        context = bpy.context
        wm = context.window_manager

        # Scene update handler
        handlers = bpy.app.handlers.scene_update_pre
        if cls._scene_update_pre in handlers:
            handlers.remove(cls._scene_update_pre)

        # Render handlers
        render_init = bpy.app.handlers.render_complete
        if cls._render_init in render_init:
            render_init.remove(cls._render_init)
        render_complete = bpy.app.handlers.render_complete
        if cls._render_complete in render_complete:
            render_complete.remove(cls._render_complete)
        render_cancel = bpy.app.handlers.render_cancel
        if cls._render_cancel in render_cancel:
            render_cancel.remove(cls._render_cancel)
        logger.debug('Remove render handlers')

        # Render timers
        for timer in cls._render_timers.values():
            wm.event_timer_remove(timer)
        cls._render_timers.clear()

        # operators
        for m in cls.managers:
            m.operators.clear()
            m.status = m.NORMAL

    def _exit(self, context, window=None):
        """self.all_windowsが真の場合は全てのoperatorを、そうでないなら
        context.windowのoperatorのみを修了させる。
        """
        if window:
            addr = window.as_pointer()
            if addr in self.operators:
                del self.operators[addr]
        else:
            self.operators.clear()

    def _cleanup(self, context):
        """無効なwindowのoperatorとexit_timerの削除"""
        wm = context.window_manager
        addrs = {win.as_pointer() for win in wm.windows}
        for addr in list(self.operators.keys()):
            if addr not in addrs:
                del self.operators[addr]

        if not self.operators:
            self.status = self.NORMAL

    def is_rendering(self):
        return self._is_rendering

    def is_running(self, context, window=None):
        wm = context.window_manager
        if window:
            return window.as_pointer() in self.operators
        else:
            addrs = {win.as_pointer() for win in wm.windows}
            return bool(addrs & set(self.operators.keys()))

    @staticmethod
    def active_window(context):
        wm = context.window_manager
        for window in wm.windows:
            win = wmWindow.cast(window)
            if win.active:
                return window

    def modal(self, func):
        @functools.wraps(func)
        def _modal(self_, context, event):
            wm = context.window_manager
            window = context.window
            addr = window.as_pointer()

            self._cleanup(context)

            if addr not in self.operators or self.operators[addr] != self_:
                logger.debug('Unnecessary operator cancelled')
                return {'CANCELLED', 'PASS_THROUGH'}

            r = func(self_, context, event)
            if r & {'FINISHED', 'CANCELLED'}:
                win = None if self.all_windows else context.window
                self._exit(context, win)
            else:
                if self._is_rendering:
                    # レンダリング中はscene_updateが行われない為、
                    # Auto Start
                    if self.all_windows:
                        for window in wm.windows:
                            if window != context.window:
                                self._auto_start_do(context, window)
                    # Timer
                    if self.all_windows:
                        self._render_timer_add()
            return r

        return _modal

    def invoke(self, func):
        @functools.wraps(func)
        def _invoke(self_, context, event):
            window = context.window
            addr = window.as_pointer()

            self._cleanup(context)

            manage = True
            if self.is_running(context) and self.status == self.AUTO_START:
                context.window_manager.modal_handler_add(self_)
                if self.callback:
                    if self.status == self.AUTO_START:
                        self.callback(context, event, self_, None)
                r = {'RUNNING_MODAL', 'PASS_THROUGH'}
            else:
                # Operator.invoke()
                r = func(self_, context, event)
                manage = self.SKIP_MANAGER not in r
                r.discard(self.SKIP_MANAGER)

            if not manage:
                return r
            elif r & {'FINISHED', 'CANCELLED'}:
                win = None if self.all_windows else context.window
                self._exit(context, win)
                return r
            else:
                self.operators[addr] = self_
                self._add_handlers()
                return r

        return _invoke
