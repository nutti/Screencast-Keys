from . import common


class TestPreferences(common.TestBase):
    module_name = "preferences"
    idname = [
        ('OPERATOR', 'wm.sk_check_addon_update'),
        ('OPERATOR', 'wm.sk_update_addon'),
        ('OPERATOR', 'wm.sk_select_custom_mouse_image'),
        ('PREFERENCES', 'screencast_keys'),
    ]

    # this test can not be done because area always NoneType in console run
    def test_nothing(self):
        pass
