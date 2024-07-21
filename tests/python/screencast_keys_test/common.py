import sys
import unittest
import os

import bpy


TESTEE_FILE = f"{os.path.dirname(os.path.abspath(__file__))}/testee.blend"


def check_version(major, minor, _):
    """
    Check blender version
    """

    if bpy.app.version[0] == major and bpy.app.version[1] == minor:
        return 0
    if bpy.app.version[0] > major:
        return 1
    if bpy.app.version[1] > minor:
        return 1
    return -1


def get_user_preferences(context):
    if hasattr(context, "user_preferences"):
        return context.user_preferences

    return context.preferences


def check_addon_enabled(mod):
    if check_version(2, 80, 0) < 0:
        result = bpy.ops.wm.addon_enable(module=mod)
    else:
        result = bpy.ops.preferences.addon_enable(module=mod)
    assert (result == {'FINISHED'}), "Failed to enable add-on %s" % (mod)
    assert (mod in get_user_preferences(bpy.context).addons.keys()), \
        "Failed to enable add-on %s" % (mod)


def check_addon_disabled(mod):
    if check_version(2, 80, 0) < 0:
        result = bpy.ops.wm.addon_disable(module=mod)
    else:
        result = bpy.ops.preferences.addon_disable(module=mod)
    assert (result == {'FINISHED'}), "Failed to disable add-on %s" % (mod)
    assert (mod not in get_user_preferences(bpy.context).addons.keys()), \
        "Failed to disable add-on %s" % (mod)


def operator_exists(idname):
    try:
        from bpy.ops import op_as_string    # pylint: disable=C0415
        op_as_string(idname)
        return True
    except:     # pylint: disable=W0702 # noqa
        try:
            from bpy.ops import _op_as_string   # pylint: disable=C0415
            _op_as_string(idname)
            return True
        except:     # pylint: disable=W0702 # noqa
            return False


def menu_exists(idname):
    return idname in dir(bpy.types)


def panel_exists(idname):
    return idname in dir(bpy.types)


def preferences_exists(name):
    if name in get_user_preferences(bpy.context).addons.keys():
        return True

    fullname = f"bl_ext.user_default.{name}"
    if fullname in get_user_preferences(bpy.context).addons.keys():
        return True

    return False


class TestBase(unittest.TestCase):

    package_name = "bl_ext.user_default.screencast_keys"
    module_name = ""
    submodule_name = None
    idname = []

    @classmethod
    def setUpClass(cls):
        if cls.submodule_name is not None:
            print("\n======== Module Test: {}.{} ({}) ========"
                  .format(cls.package_name, cls.module_name,
                          cls.submodule_name))
        else:
            print("\n======== Module Test: {}.{} ========"
                  .format(cls.package_name, cls.module_name))
        try:
            bpy.ops.wm.read_factory_settings()
            check_addon_enabled(cls.package_name)
            for op in cls.idname:
                if op[0] == 'OPERATOR':
                    assert operator_exists(op[1]), \
                        "Operator {} does not exist".format(op[1])
                elif op[0] == 'MENU':
                    assert menu_exists(op[1]), \
                        "Menu {} does not exist".format(op[1])
                elif op[0] == 'PANEL':
                    assert panel_exists(op[1]), \
                        "Panel {} does not exist".format(op[1])
                elif op[0] == 'PREFERENCES':
                    assert preferences_exists(op[1]), \
                        "Preferences {} does not exist".format(op[1])
            bpy.ops.wm.save_as_mainfile(filepath=TESTEE_FILE)
        except AssertionError as e:
            print(e)
            sys.exit(1)

    @classmethod
    def tearDownClass(cls):
        try:
            check_addon_disabled(cls.package_name)
            for op in cls.idname:
                if op[0] == 'OPERATOR':
                    assert not operator_exists(op[1]), \
                           "Operator {} exists".format(op[1])
                elif op[0] == 'MENU':
                    assert not menu_exists(op[1]), \
                           "Menu {} exists".format(op[1])
        except AssertionError as e:
            print(e)
            sys.exit(1)

    def setUp(self):
        bpy.ops.wm.open_mainfile(filepath=TESTEE_FILE)
        self.setUpEachMethod()

    def setUpEachMethod(self):      # pylint: disable=C0103
        pass

    def tearDown(self):
        self.tearDownEachMethod()

    def tearDownEachMethod(self):   # pylint: disable=C0103
        pass
