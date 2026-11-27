import unittest

from PIL import Image

from autoclicker.overlays import geometry
from autoclicker.platform import VirtualScreen
from autoclicker.smart import SmartStopMonitor


class FakeCapturer:
    def __init__(self, images):
        self.images = iter(images)
        self.regions = []
    def grab(self, region):
        self.regions.append(region)
        return next(self.images)


class ScreenTests(unittest.TestCase):
    def test_negative_virtual_screen_mapping(self):
        screen = VirtualScreen(-1920, -100, 3520, 1180)
        self.assertEqual(screen.clamp(-5000, 5000), (-1920, 1079))
        x, y = screen.from_relative(0, 0)
        self.assertEqual((x, y), (-1920, -100))
        self.assertEqual(screen.to_relative(-1920, -100), (0, 0))

    def test_overlay_geometry_has_signed_origin(self):
        self.assertEqual(geometry(None, VirtualScreen(-1920, 0, 3520, 1080)), "3520x1080-1920+0")


class SmartStopTests(unittest.TestCase):
    def test_detects_no_change(self):
        frames = [Image.new("RGB", (48, 48), "black") for _ in range(10)]
        monitor = SmartStopMonitor(capturer=FakeCapturer(frames))
        reasons = [monitor.check(10, 10) for _ in range(10)]
        self.assertIn("no_change", reasons)

    def test_detects_changed_frame(self):
        monitor = SmartStopMonitor(capturer=FakeCapturer([
            Image.new("RGB", (48, 48), "black"), Image.new("RGB", (48, 48), "white")
        ]))
        self.assertEqual(monitor.check(0, 0), "")
        self.assertEqual(monitor.check(0, 0), "changed")

    def test_uses_negative_coordinates_without_clamping_to_primary_screen(self):
        capture = FakeCapturer([Image.new("RGB", (48, 48), "black")])
        monitor = SmartStopMonitor(capturer=capture)
        monitor.check(-500, -100)
        self.assertEqual(capture.regions[0]["left"], -524)
        self.assertEqual(capture.regions[0]["top"], -124)

    def test_large_area_capture_is_bounded(self):
        capture = FakeCapturer([Image.new("RGB", (256, 256), "black")])
        monitor = SmartStopMonitor(capturer=capture)
        monitor.check(0, 0, (0, 0, 4000, 2000))
        self.assertEqual(capture.regions[0]["width"], 256)
        self.assertEqual(capture.regions[0]["height"], 256)
