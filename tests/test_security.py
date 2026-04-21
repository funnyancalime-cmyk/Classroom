import tempfile
import unittest
from pathlib import Path

from app import Database, PIN_HASH_SETTING_KEY, hash_pin


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_path = Path(self.tmp.name)
        self.tmp.close()
        self.db = Database(self.tmp_path)

    def tearDown(self):
        try:
            self.db.close()
        finally:
            self.tmp_path.unlink(missing_ok=True)

    def test_hash_pin_is_stable_and_non_plaintext(self):
        hashed = hash_pin("1234")
        self.assertEqual(hashed, hash_pin("1234"))
        self.assertNotEqual(hashed, "1234")
        self.assertEqual(len(hashed), 64)

    def test_setting_roundtrip_for_pin_hash(self):
        self.assertIsNone(self.db.get_setting(PIN_HASH_SETTING_KEY))
        self.db.set_setting(PIN_HASH_SETTING_KEY, hash_pin("9876"))
        value = self.db.get_setting(PIN_HASH_SETTING_KEY)
        self.assertIsInstance(value, str)
        self.assertEqual(len(value), 64)

    def test_replace_settings_roundtrip(self):
        self.db.set_setting("theme", "light")
        self.db.replace_settings({"theme": "dark", "lang": "cs"})
        settings = self.db.list_settings()
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(settings["lang"], "cs")


if __name__ == "__main__":
    unittest.main()
