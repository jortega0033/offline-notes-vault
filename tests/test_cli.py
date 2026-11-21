import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from notes_vault import __main__ as cli
from notes_vault import __version__, config, storage


class ConfigTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def parse(self, argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            try:
                return config.parse_args(argv), 0, err.getvalue()
            except SystemExit as exc:
                return None, exc.code, err.getvalue()

    def test_version(self):
        self.assertEqual(__version__, "0.1.0")

    def test_valid_args_create_nested_dir(self):
        target = self.tmp / "a" / "b"
        result, code, _ = self.parse(["--data-dir", str(target), "--port", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(result, (target.resolve(), 0))
        self.assertTrue(target.is_dir())

    def test_existing_dir_reused_and_default_port(self):
        result, code, _ = self.parse(["--data-dir", str(self.tmp)])
        self.assertEqual((code, result[1]), (0, config.DEFAULT_PORT))

    def test_invalid_ports_exit_2(self):
        for port in ("-1", "65536", "abc", "", "1.5"):
            with self.subTest(port=port):
                result, code, err = self.parse(["--data-dir", str(self.tmp), "--port", port])
                self.assertEqual((result, code), (None, 2))
                self.assertIn("port", err)
        self.assertEqual(self.parse(["--data-dir", str(self.tmp), "--port", "65535"])[1], 0)
        self.assertEqual(self.parse(["--data-dir", str(self.tmp), "--port", "1"])[1], 0)

    def test_bad_data_dirs_exit_2(self):
        a_file = self.tmp / "file.txt"
        a_file.write_text("x")
        for value in ("", "   ", str(a_file), str(a_file / "child")):
            with self.subTest(value=value):
                result, code, err = self.parse(["--data-dir", value])
                self.assertEqual((result, code), (None, 2))
                self.assertIn("data", err)
        self.assertEqual(a_file.read_text(), "x")

    def test_missing_data_dir_exit_2(self):
        self.assertEqual(self.parse([])[1], 2)

    def test_unwritable_dir_rejected(self):
        with mock.patch("tempfile.TemporaryFile", side_effect=PermissionError(13, "denied")):
            with self.assertRaises(config.ConfigError):
                config.validate_data_dir(self.tmp)


class MainTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_ctrl_c_exits_zero_and_closes(self):
        fake = mock.Mock()
        fake.server_address = ("127.0.0.1", 4321)
        fake.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch.object(cli, "create_server", return_value=fake) as create:
            code, out, _ = self.run_main(["--data-dir", str(self.tmp), "--port", "4321"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Offline Notes Vault listening on http://127.0.0.1:4321/")
        create.assert_called_once_with(self.tmp.resolve(), 4321)
        fake.close.assert_called_once()

    def test_future_schema_exit_2(self):
        c = sqlite3.connect(self.tmp / storage.DB_NAME)
        c.execute("PRAGMA user_version=42")
        c.close()
        code, out, err = self.run_main(["--data-dir", str(self.tmp), "--port", "0"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("schema version", err)

    def test_corrupt_database_exit_2(self):
        (self.tmp / storage.DB_NAME).write_bytes(b"this is not a sqlite database" * 100)
        code, _, err = self.run_main(["--data-dir", str(self.tmp), "--port", "0"])
        self.assertEqual(code, 2)
        self.assertIn("error", err)

    def test_port_in_use_exit_2(self):
        from notes_vault.server import create_server
        with tempfile.TemporaryDirectory() as other:
            busy = create_server(other, 0)
            self.addCleanup(busy.close)
            code, _, err = self.run_main(["--data-dir", str(self.tmp), "--port", str(busy.server_address[1])])
        self.assertEqual(code, 2)
        self.assertIn("error", err)


if __name__ == "__main__":
    unittest.main()
