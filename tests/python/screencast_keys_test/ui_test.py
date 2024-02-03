from . import common


class TestUI(common.TestBase):
    module_name = "ui"
    idname = [
        ('PANEL', 'SK_PT_ScreencastKeys'),
    ]

    # this test can not be done because area always NoneType in console run
    def test_nothing(self):
        pass
