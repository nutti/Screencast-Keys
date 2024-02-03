from . import common


class TestOps(common.TestBase):
    module_name = "ops"
    idname = [
        ('OPERATOR', 'wm.sk_screencast_keys'),
        ('OPERATOR', 'wm.sk_set_origin'),
        ('OPERATOR',
         'wm.sk_wait_blender_initialized_and_start_screencast_keys'),
    ]

    # this test can not be done because area always NoneType in console run
    def test_nothing(self):
        pass
