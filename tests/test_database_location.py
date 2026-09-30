import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import app


class DatabaseLocationTests(unittest.TestCase):
    def test_windows_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(app.sys, "platform", "win32"), patch.dict(app.os.environ, {"LOCALAPPDATA": tmp}):
            self.assertEqual(app.database_path(), Path(tmp) / "SeatingOrder" / "seating_app.db")

    def test_legacy_database_migrates_once_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "seating_app.db"
            target = root / "user" / "SeatingOrder" / "seating_app.db"
            with closing(sqlite3.connect(legacy)) as conn, conn:
                conn.execute("CREATE TABLE sample (value TEXT)")
                conn.execute("INSERT INTO sample VALUES ('original')")
            with patch.object(app.sys, "platform", "win32"), patch.object(app, "APP_DIR", root), patch.object(app.sys, "frozen", False, create=True):
                app.prepare_database(target)
                with closing(sqlite3.connect(target)) as conn, conn:
                    self.assertEqual(conn.execute("SELECT value FROM sample").fetchone()[0], "original")
                    conn.execute("UPDATE sample SET value='user data'")
                app.prepare_database(target)
            with closing(sqlite3.connect(target)) as conn, conn:
                self.assertEqual(conn.execute("SELECT value FROM sample").fetchone()[0], "user data")
            self.assertTrue(legacy.exists())

    def test_new_install_creates_writable_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "SeatingOrder" / "seating_app.db"
            with patch.object(app.sys, "platform", "win32"), patch.object(app, "APP_DIR", Path(tmp) / "Program Files"):
                app.prepare_database(target)
            db = app.Database(target)
            try:
                db.create_classroom("9.A", 1, 1)
            finally:
                db.close()
            self.assertTrue(target.is_file())

    def test_migration_closes_connections_before_renaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with closing(sqlite3.connect(root / "seating_app.db")) as conn, conn:
                conn.execute("CREATE TABLE sample (value TEXT)")
            connections = []
            real_connect = sqlite3.connect
            real_replace = Path.replace

            def connect(*args, **kwargs):
                connection = real_connect(*args, **kwargs)
                connections.append(connection)
                return connection

            def replace(source, target):
                for connection in connections:
                    with self.assertRaises(sqlite3.ProgrammingError):
                        connection.execute("SELECT 1")
                return real_replace(source, target)

            with patch.object(app.sys, "platform", "win32"), patch.object(app, "APP_DIR", root), patch.object(app.sqlite3, "connect", side_effect=connect), patch.object(Path, "replace", replace):
                app.prepare_database(root / "user" / "seating_app.db")

    def test_frozen_app_reads_legacy_database_beside_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exe_dir = root / "install"
            exe_dir.mkdir()
            legacy = exe_dir / "seating_app.db"
            with closing(sqlite3.connect(legacy)) as conn, conn:
                conn.execute("CREATE TABLE sample (value TEXT)")
                conn.execute("INSERT INTO sample VALUES ('installed')")
            target = root / "profile" / "SeatingOrder" / "seating_app.db"
            with patch.object(app.sys, "platform", "win32"), patch.object(app.sys, "frozen", True, create=True), patch.object(app.sys, "executable", str(exe_dir / "SeatingOrder.exe")):
                app.prepare_database(target)
            with closing(sqlite3.connect(target)) as conn, conn:
                self.assertEqual(conn.execute("SELECT value FROM sample").fetchone()[0], "installed")


if __name__ == "__main__":
    unittest.main()
