"""BOM handling: read_md drops a leading BOM and validate_single flags it."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from site_utils.file_utils import read_md  # noqa: E402

DOC = "# Title\n\nBody.\n"


class ReadMdBomTest(unittest.TestCase):
    def test_leading_bom_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_bytes(b"\xef\xbb\xbf" + DOC.encode("utf-8"))
            self.assertEqual(read_md(path), DOC)

    def test_plain_file_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_bytes(DOC.encode("utf-8"))
            self.assertEqual(read_md(path), DOC)


class ValidateBomTest(unittest.TestCase):
    def test_validate_single_flags_bom(self):
        from hv_mcp import validation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doc.md").write_bytes(b"\xef\xbb\xbf" + DOC.encode("utf-8"))
            original = validation.HYPERSPACE_ROOT
            validation.HYPERSPACE_ROOT = root
            try:
                result = validation.validate_single("doc.md")
            finally:
                validation.HYPERSPACE_ROOT = original
        rules = [v["rule"] for v in result.get("violations", [])]
        self.assertIn("encoding-bom", rules)
        self.assertNotIn("structure-missing-title", rules)


if __name__ == "__main__":
    unittest.main()
