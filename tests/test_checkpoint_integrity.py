"""Focused integrity checks for the small reference checkpoint format."""
from pathlib import Path
import random
import tempfile
import unittest

from cellsim_v2.checkpoint import save_checkpoint
from cellsim_v2.state import World


class CheckpointIntegrityTests(unittest.TestCase):
    def test_private_state_that_json_would_change_is_rejected_before_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_checkpoint(path, World(), random.Random(7), "reference/1",
                            {"history": [1.0, 2.0]})
            original = path.read_bytes()

            for private_state in (
                {"history": (1.0, 2.0)},
                {"history": [{1: "cell-a"}]},
            ):
                with self.subTest(private_state=private_state):
                    with self.assertRaisesRegex(ValueError, "private state"):
                        save_checkpoint(path, World(), random.Random(7),
                                        "reference/1", private_state)
                    self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
