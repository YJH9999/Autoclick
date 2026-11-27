import unittest
from unittest.mock import patch

from autoclicker.hotkeys import HotkeyError, HotkeyManager, normalize_hotkey, validate_hotkeys
from autoclicker.models import DEFAULT_HOTKEYS


class FakeListener:
    instances = []
    def __init__(self, mapping):
        self.mapping = mapping
        self.daemon = False
        self.started = False
        self.stopped = False
        self.__class__.instances.append(self)
    def start(self):
        self.started = True
    def stop(self):
        self.stopped = True


class HotkeyTests(unittest.TestCase):
    def test_normalize_function_and_combination(self):
        self.assertEqual(normalize_hotkey(" F6 "), "<f6>")
        self.assertEqual(normalize_hotkey("Ctrl+Shift+K"), "<ctrl>+<shift>+k")

    def test_invalid_and_duplicate_hotkeys_are_rejected(self):
        with self.assertRaises(HotkeyError):
            normalize_hotkey("not_a_key")
        values = dict(DEFAULT_HOTKEYS)
        values["pause"] = values["toggle"]
        with self.assertRaises(HotkeyError):
            validate_hotkeys(values)

    def test_listener_dispatch_and_restart(self):
        FakeListener.instances.clear()
        manager = HotkeyManager(listener_factory=FakeListener)
        calls = []
        manager.on("toggle", lambda: calls.append("toggle"))
        manager.start(DEFAULT_HOTKEYS)
        self.assertTrue(manager.active)
        FakeListener.instances[-1].mapping["<f6>"]()
        self.assertEqual(calls, ["toggle"])
        manager.start(DEFAULT_HOTKEYS)
        self.assertTrue(FakeListener.instances[0].stopped)
        self.assertEqual(len(FakeListener.instances), 2)
        manager.stop()
        self.assertFalse(manager.active)

    def test_start_failure_is_visible(self):
        class BrokenListener(FakeListener):
            def start(self):
                raise OSError("denied")
        manager = HotkeyManager(listener_factory=BrokenListener)
        with self.assertRaises(HotkeyError):
            manager.start(DEFAULT_HOTKEYS)
        self.assertFalse(manager.active)
