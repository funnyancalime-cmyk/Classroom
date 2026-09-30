import importlib.util
import os
import sys
import unittest
from unittest.mock import patch


def _load_gui_smoke_module():
    script_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "gui_smoke.py")
    spec = importlib.util.spec_from_file_location("gui_smoke_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GuiSmokeScriptTests(unittest.TestCase):
    def test_has_display_false_on_linux_without_display(self):
        module = _load_gui_smoke_module()
        with patch.object(module.sys, "platform", "linux"), patch.dict(module.os.environ, {}, clear=True):
            self.assertFalse(module._has_display())

    def test_has_display_true_on_windows(self):
        module = _load_gui_smoke_module()
        with patch.object(module.sys, "platform", "win32"):
            self.assertTrue(module._has_display())

    def test_main_skips_cleanly_when_no_display(self):
        module = _load_gui_smoke_module()
        with patch.object(module, "_has_display", return_value=False):
            self.assertEqual(module.main([]), 0)

    def test_main_fails_without_display_when_required(self):
        module = _load_gui_smoke_module()
        with patch.object(module, "_has_display", return_value=False):
            self.assertEqual(module.main(["--require-display"]), 1)


if __name__ == "__main__":
    unittest.main()
