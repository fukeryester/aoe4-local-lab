import unittest
from unittest.mock import patch, mock_open
import app

class VersionSelectionTests(unittest.TestCase):
    def choose(self, digest):
        class Process:
            def __init__(self, pid): self.pid=pid
            def modules(self): return [{"name":"RelicCardinal.exe", "path":"game.exe"}]
            def close(self): pass
        class Reader:
            def __init__(self, pid, **kwargs): self.pid=pid; self.kwargs=kwargs
        class Hash:
            def hexdigest(self): return digest
        with patch.object(app,"game_pids",return_value=[123]), patch.object(app,"Process",Process), patch.object(app,"Reader",Reader), patch.object(app,"Reader12260",Reader), patch("builtins.open",mock_open()), patch.object(app.hashlib,"file_digest",return_value=Hash()):
            return app.open_reader()
    def test_known_profiles_and_unknown_fallback(self):
        old=self.choose(app.BUILD_SHA256)
        self.assertTrue(old.verified); self.assertEqual(old.version,"17.0.12182.0")
        latest=self.choose(app.BUILD_SHA256_12260)
        self.assertTrue(latest.verified); self.assertEqual(latest.kwargs["expected_hash"],app.BUILD_SHA256_12260)
        unknown=self.choose("unknown")
        self.assertFalse(unknown.verified); self.assertEqual(unknown.kwargs["expected_hash"],"unknown"); self.assertIn("17.0.12260.0",unknown.version)

if __name__=="__main__": unittest.main()
