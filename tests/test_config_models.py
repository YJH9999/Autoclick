from pathlib import Path
import tempfile
import unittest

from autoclicker.config import ConfigError, ConfigStore, normalize_config
from autoclicker.models import DEFAULT_CONFIG, ClickSettings, parse_int


class SettingsTests(unittest.TestCase):
    def test_defaults_and_area_normalization(self):
        settings = ClickSettings.from_mapping(DEFAULT_CONFIG)
        self.assertEqual(settings.interval_ms, 100)
        area = ClickSettings.from_mapping({**DEFAULT_CONFIG, "area": [20, 30, -10, 5]}).area
        self.assertEqual(area, (-10, 5, 20, 30))

    def test_invalid_values_raise_chinese_errors(self):
        for value in ("abc", 0, 1.5, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_int(value, "间隔", 1, 100)
        with self.assertRaises(ValueError):
            ClickSettings.from_mapping({**DEFAULT_CONFIG, "area": [1, 2, 1, 8]})

    def test_partially_damaged_config_keeps_valid_fields(self):
        cfg = normalize_config({"x": 123, "interval_ms": "bad", "theme": "light", "topmost": "yes"})
        self.assertEqual(cfg["x"], 123)
        self.assertEqual(cfg["interval_ms"], 100)
        self.assertEqual(cfg["theme"], "light")
        self.assertTrue(cfg["topmost"])


class ConfigStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = ConfigStore(self.root / "config.json")

    def tearDown(self):
        self.temporary.cleanup()

    def test_round_trip_unicode_presets_and_atomic_file(self):
        cfg = normalize_config({**DEFAULT_CONFIG, "x": -200, "presets": {"我的方案": {"interval_ms": 25}}})
        self.store.save(cfg)
        loaded, warning = self.store.load()
        self.assertEqual(warning, "")
        self.assertEqual(loaded["x"], -200)
        self.assertEqual(loaded["presets"]["我的方案"]["interval_ms"], 25)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_corrupt_json_returns_defaults_with_warning(self):
        self.store.path.write_text("{broken", encoding="utf-8")
        loaded, warning = self.store.load()
        self.assertEqual(loaded["interval_ms"], 100)
        self.assertIn("配置读取失败", warning)

    def test_export_and_import(self):
        destination = self.root / "exported.json"
        self.store.export(DEFAULT_CONFIG, destination)
        self.assertTrue(destination.exists())
        imported = self.store.import_file(destination)
        self.assertEqual(imported["cfg_version"], DEFAULT_CONFIG["cfg_version"])

    def test_import_invalid_file_raises(self):
        path = self.root / "bad.json"
        path.write_text("[]", encoding="utf-8")
        # 非对象 JSON 会安全回退；真正不可解析的内容必须报告错误。
        self.store.import_file(path)
        path.write_text("no json", encoding="utf-8")
        with self.assertRaises(ConfigError):
            self.store.import_file(path)
