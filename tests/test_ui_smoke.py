import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autoclicker.app import AutoClickerApp
from autoclicker.config import ConfigStore
from autoclicker.hotkeys import HotkeyManager


@unittest.skipUnless(os.name == "nt", "主窗口冒烟测试仅在 Windows 上运行")
class UISmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = ConfigStore(Path(self.temporary.name) / "config.json")
        self.hotkey_patch = patch.object(HotkeyManager, "start", lambda self, values=None: None)
        self.hotkey_patch.start()
        self.app = AutoClickerApp(store=self.store)
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        if self.app and not self.app._closing:
            self.app.quit()
        self.hotkey_patch.stop()
        self.temporary.cleanup()

    def test_main_controls_and_coordinate_editing(self):
        self.assertTrue(self.app.start_button.winfo_exists())
        self.assertTrue(self.app.pause_button.winfo_exists())
        self.assertGreater(self.app.start_button.winfo_rooty(), self.app.status_frame.winfo_rooty())
        self.app._set_entry(self.app.x_entry, "123")
        self.app._set_entry(self.app.y_entry, "456")
        self.app._apply_coordinates()
        self.assertEqual((self.app.config["x"], self.app.config["y"]), (123, 456))

    def test_theme_follow_mode_and_validation(self):
        previous = self.app.config["theme"]
        self.app.toggle_theme()
        self.assertNotEqual(self.app.config["theme"], previous)
        self.app.position_mode.set("跟随鼠标")
        self.app._position_mode_changed("跟随鼠标")
        self.assertEqual(self.app.point_button.cget("state"), "disabled")
        self.app.interval.set("invalid")
        with self.assertRaises(ValueError):
            self.app._collect_config()

    def test_quit_persists_valid_configuration(self):
        self.app.interval.set("125")
        self.app.quit()
        self.assertTrue(self.store.path.exists())
        loaded, warning = self.store.load()
        self.assertEqual(warning, "")
        self.assertEqual(loaded["interval_ms"], 125)
