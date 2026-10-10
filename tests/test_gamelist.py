"""Unit tests for the EmulationStation Ports menu entry updater."""
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ports"))
from update_gamelist import remove_weread, upsert_weread


class GamelistUpdateTest(unittest.TestCase):
    def test_inserts_weread_entry_without_touching_existing_games(self):
        source = """<?xml version="1.0"?>
<gameList>
  <game><path>./Other.sh</path><name>Other</name></game>
</gameList>
""".encode()
        result = upsert_weread(source)
        root = ET.fromstring(result)
        games = root.findall("game")
        self.assertEqual(len(games), 2)
        self.assertEqual(games[0].findtext("name"), "Other")
        weread = next(game for game in games if game.findtext("path") == "./Weread.sh")
        self.assertEqual(weread.findtext("name"), "微信读书")
        self.assertEqual(weread.findtext("image"), "./media/Weread.png")
        self.assertIn("手柄导航", weread.findtext("desc"))

    def test_updates_existing_weread_entry_idempotently(self):
        source = """<gameList>
  <game><path>./Weread.sh</path><name>Weread</name><image></image></game>
</gameList>
""".encode()
        first = upsert_weread(source)
        second = upsert_weread(first)
        root = ET.fromstring(second)
        games = [game for game in root.findall("game")
                 if game.findtext("path") == "./Weread.sh"]
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0].findtext("name"), "微信读书")
        self.assertEqual(games[0].findtext("genre"), "阅读工具")
        self.assertEqual(games[0].findtext("image"), "./media/Weread.png")

    def test_remove_keeps_other_games(self):
        source = """<gameList>
  <game><path>./Weread.sh</path><name>微信读书</name></game>
  <game><path>./Other.sh</path><name>Other</name></game>
</gameList>
""".encode()
        root = ET.fromstring(remove_weread(source))
        self.assertEqual([game.findtext("name") for game in root.findall("game")], ["Other"])


if __name__ == "__main__":
    unittest.main()