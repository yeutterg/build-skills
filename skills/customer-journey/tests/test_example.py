"""Golden test: the example workspace renders exactly the committed audit."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "acme-kettle"


class ExampleGolden(unittest.TestCase):
    def test_render_matches_committed_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            shutil.copytree(EXAMPLE, ws, ignore=shutil.ignore_patterns("audit"))
            shutil.copy(EXAMPLE / "audit" / "data" / "history.json", tmp)  # keep history stable
            (ws / "audit" / "data").mkdir(parents=True)
            shutil.copy(Path(tmp) / "history.json", ws / "audit" / "data" / "history.json")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "journey.py"), "run", str(ws), "--date", "2026-10-15"], check=True, capture_output=True)
            for expected in sorted((EXAMPLE / "audit").rglob("*")):
                if expected.is_file():
                    actual = ws / "audit" / expected.relative_to(EXAMPLE / "audit")
                    self.assertTrue(actual.exists(), f"missing {actual}")
                    self.assertEqual(expected.read_text(), actual.read_text(), f"{expected.relative_to(ROOT)} differs")


if __name__ == "__main__":
    unittest.main()
