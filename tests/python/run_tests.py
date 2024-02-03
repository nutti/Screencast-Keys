import os
import sys
import unittest


def test_main():
    path = os.path.dirname(__file__)
    sys.path.append(path)

    import screencast_keys_test     # pylint: disable=C0415

    test_cases = [
        screencast_keys_test.ops_test.TestOps,
        screencast_keys_test.preferences_test.TestPreferences,
        screencast_keys_test.ui_test.TestUI,
    ]

    suite = unittest.TestSuite()
    for case in test_cases:
        suite.addTest(unittest.makeSuite(case))
    ret = unittest.TextTestRunner().run(suite).wasSuccessful()
    sys.exit(not ret)


if __name__ == "__main__":
    test_main()
