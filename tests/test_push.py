import importlib
import os
import tempfile
import unittest

from tests import context  # noqa: F401


class PublishGuardTest(unittest.TestCase):
    """개발 PC나 스모크에서 실수로 push 되지 않는지 확인한다."""

    def setUp(self):
        self._saved = {
            k: os.environ.get(k) for k in ("BRE_SKIP_PUSH", "BRE_DATA_DIR")
        }
        self.module = importlib.import_module("push_to_github")

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_skip_push_recognises_truthy_values(self):
        for value in ("1", "true", "True"):
            os.environ["BRE_SKIP_PUSH"] = value
            self.assertTrue(self.module.skip_push(), value)

        for value in ("0", "false", "", "no"):
            os.environ["BRE_SKIP_PUSH"] = value
            self.assertFalse(self.module.skip_push(), value)

    def test_push_is_skipped_when_flag_set(self):
        os.environ["BRE_SKIP_PUSH"] = "1"
        self.assertFalse(self.module.push_to_github())
        self.assertFalse(self.module.prepare_publish())

    def test_push_is_skipped_outside_a_git_work_tree(self):
        """BRE_DATA_DIR 이 clone 이 아니면 조용히 실패하지 말고 건너뛴다."""
        os.environ.pop("BRE_SKIP_PUSH", None)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["BRE_DATA_DIR"] = tmp
            self.assertFalse(self.module.is_git_repo())
            self.assertFalse(self.module.push_to_github())

    def test_tracked_files_are_the_two_published_artifacts(self):
        self.assertEqual(
            self.module.TRACKED_FILES, ["data/status.json", "last_state.json"]
        )


if __name__ == "__main__":
    unittest.main()
