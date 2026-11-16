import tempfile
from pathlib import Path
import unittest
import zipfile
from prepare_windows_updaters import build_archive, validate_archive


class WindowsUpdaterArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.installer = self.root / "HelixNotes_1.3.8_x64-setup.exe"
        self.installer.write_bytes(b"MZ" + b"synthetic installer payload\n" * 100)
        self.archive = self.root / "update.zip"

    def test_generated_archive_is_stored_and_preserves_exact_installer(self):
        build_archive(self.installer, self.archive)
        validate_archive(self.archive, self.installer)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(archive.infolist()[0].compress_type, zipfile.ZIP_STORED)
            self.assertEqual(archive.read(self.installer.name), self.installer.read_bytes())

    def test_deflate_is_rejected_even_when_python_can_extract_it(self):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.installer, self.installer.name)
        with self.assertRaisesRegex(ValueError, "ZIP_STORED"):
            validate_archive(self.archive, self.installer)

    def test_nested_installer_is_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.write(self.installer, "nested/" + self.installer.name)
        with self.assertRaisesRegex(ValueError, "root-level"):
            validate_archive(self.archive, self.installer)

    def test_changed_installer_is_rejected(self):
        build_archive(self.installer, self.archive)
        self.installer.write_bytes(b"different payload")
        with self.assertRaisesRegex(ValueError, "differs"):
            validate_archive(self.archive, self.installer)


if __name__ == "__main__":
    unittest.main()
