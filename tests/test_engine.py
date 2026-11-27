import threading
import time
import unittest

from autoclicker.engine import ClickEngine
from autoclicker.models import DEFAULT_CONFIG, ClickSettings


class FakeMouse:
    def __init__(self):
        self.position = (77, 88)
        self.clicks = []
        self.moves = []

    def click(self, button, count=1):
        self.clicks.append((button, count, self.position))


class BrokenMouse(FakeMouse):
    def click(self, button, count=1):
        raise OSError("backend unavailable")


class ClickEngineTests(unittest.TestCase):
    def settings(self, **changes):
        return ClickSettings.from_mapping({**DEFAULT_CONFIG, "interval_ms": 2, **changes})

    def wait_until_idle(self, engine, timeout=3):
        deadline = time.monotonic() + timeout
        while engine.running and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertFalse(engine.running, "点击线程未及时退出")

    def test_limit_and_completion_callback(self):
        mouse, reasons = FakeMouse(), []
        engine = ClickEngine(mouse=mouse)
        engine.on_stopped = reasons.append
        self.assertTrue(engine.start(self.settings(limit=3)))
        self.wait_until_idle(engine)
        self.assertEqual(engine.count, 3)
        self.assertEqual(len(mouse.clicks), 3)
        self.assertEqual(reasons, ["completed"])
        self.assertTrue(engine.start(self.settings(limit=1)))
        self.wait_until_idle(engine)
        self.assertEqual(engine.count, 1)

    def test_double_click_counts_one_operation(self):
        mouse = FakeMouse()
        engine = ClickEngine(mouse=mouse)
        engine.start(self.settings(limit=2, click_mode="double", button="right"))
        self.wait_until_idle(engine)
        self.assertEqual(engine.count, 2)
        self.assertEqual([item[1] for item in mouse.clicks], [2, 2])
        self.assertTrue(all(item[0] == "right" for item in mouse.clicks))

    def test_pause_resume_and_stop_while_paused(self):
        mouse = FakeMouse()
        engine = ClickEngine(mouse=mouse)
        engine.start(self.settings())
        time.sleep(0.03)
        engine.pause()
        time.sleep(0.02)
        count = engine.count
        time.sleep(0.04)
        self.assertEqual(engine.count, count)
        self.assertTrue(engine.paused)
        engine.resume()
        time.sleep(0.03)
        self.assertGreater(engine.count, count)
        self.assertFalse(engine.paused)
        engine.pause()
        started = time.monotonic()
        engine.stop()
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertFalse(engine.running)

    def test_restore_cursor(self):
        mouse = FakeMouse()
        engine = ClickEngine(mouse=mouse)
        engine.start(self.settings(limit=2, x=10, y=20, restore_cursor=True))
        self.wait_until_idle(engine)
        self.assertEqual(mouse.position, (77, 88))
        self.assertEqual(mouse.clicks[0][2], (10, 20))

    def test_follow_mouse_does_not_move_pointer(self):
        mouse = FakeMouse()
        engine = ClickEngine(mouse=mouse)
        engine.start(self.settings(limit=1, position_mode="follow"))
        self.wait_until_idle(engine)
        self.assertEqual(mouse.clicks[0][2], (77, 88))
        self.assertEqual(mouse.moves, [])

    def test_area_jitter_stays_inside_area(self):
        engine = ClickEngine(mouse=FakeMouse())
        settings = self.settings(area=(-100, -50, 100, 50), jitter_pct=100)
        for _ in range(300):
            x, y = engine.random_position(settings)
            self.assertTrue(-100 <= x <= 100)
            self.assertTrue(-50 <= y <= 50)

    def test_backend_error_stops_and_reports(self):
        reasons = []
        engine = ClickEngine(mouse=BrokenMouse())
        engine.on_stopped = reasons.append
        engine.start(self.settings())
        self.wait_until_idle(engine)
        self.assertEqual(reasons, ["error"])
        self.assertIn("backend unavailable", engine.last_error)

    def test_smart_monitor_created_and_closed_on_worker(self):
        main_thread = threading.get_ident()
        events = []
        class Monitor:
            check_every = 1000
            def __init__(self):
                events.append(("create", threading.get_ident()))
            def check(self, *args):
                return ""
            def close(self):
                events.append(("close", threading.get_ident()))
        engine = ClickEngine(mouse=FakeMouse(), smart_factory=Monitor)
        engine.start(self.settings(limit=1, smart_stop=True))
        self.wait_until_idle(engine)
        self.assertNotEqual(events[0][1], main_thread)
        self.assertEqual(events[-1][0], "close")
