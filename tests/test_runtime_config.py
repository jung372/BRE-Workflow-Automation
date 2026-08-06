import importlib
import os
import tempfile
import unittest
from pathlib import Path

from tests import context  # noqa: F401


ENV_KEYS = ("BRE_DATA_DIR", "BRE_RUNTIME_DIR", "BRE_ENV_FILE", "BRE_NODE_ROLE")


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        self.module = importlib.reload(importlib.import_module("runtime_config"))

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(importlib.import_module("runtime_config"))

    def _reload(self):
        self.module = importlib.reload(self.module)
        return self.module

    def test_unset_falls_back_to_project_root(self):
        """개발 PC는 환경변수를 설정하지 않으므로 기존 동작이 유지되어야 한다."""
        mod = self._reload()
        self.assertEqual(mod.get_data_dir(), mod.PROJECT_ROOT)
        self.assertEqual(mod.get_runtime_dir(), mod.PROJECT_ROOT)
        self.assertEqual(mod.get_state_file(), mod.PROJECT_ROOT / "last_state.json")
        self.assertEqual(
            mod.get_status_file(), mod.PROJECT_ROOT / "data" / "status.json"
        )

    def test_data_and_runtime_dirs_are_independent(self):
        with tempfile.TemporaryDirectory() as data_dir, \
             tempfile.TemporaryDirectory() as runtime_dir:
            os.environ["BRE_DATA_DIR"] = data_dir
            os.environ["BRE_RUNTIME_DIR"] = runtime_dir
            mod = self._reload()

            self.assertEqual(mod.get_data_dir(), Path(data_dir).resolve())
            self.assertEqual(mod.get_runtime_dir(), Path(runtime_dir).resolve())
            self.assertEqual(mod.get_log_dir(), Path(runtime_dir).resolve() / "logs")
            # 상태파일은 데이터 쪽, 로그는 런타임 쪽으로 갈라져야 한다.
            self.assertEqual(
                mod.get_state_file(), Path(data_dir).resolve() / "last_state.json"
            )

    def test_blank_env_var_is_treated_as_unset(self):
        os.environ["BRE_DATA_DIR"] = "   "
        mod = self._reload()
        self.assertEqual(mod.get_data_dir(), mod.PROJECT_ROOT)

    def test_env_file_precedence(self):
        with tempfile.TemporaryDirectory() as runtime_dir:
            runtime_env = Path(runtime_dir) / ".env"
            runtime_env.write_text("A=1", encoding="utf-8")
            os.environ["BRE_RUNTIME_DIR"] = runtime_dir
            mod = self._reload()
            self.assertEqual(mod.get_env_file(), runtime_env.resolve())

            explicit = Path(runtime_dir) / "explicit.env"
            explicit.write_text("A=2", encoding="utf-8")
            os.environ["BRE_ENV_FILE"] = str(explicit)
            mod = self._reload()
            self.assertEqual(mod.get_env_file(), explicit.resolve())

    def test_env_file_falls_back_to_project_root_when_runtime_env_absent(self):
        with tempfile.TemporaryDirectory() as runtime_dir:
            os.environ["BRE_RUNTIME_DIR"] = runtime_dir
            mod = self._reload()
            self.assertEqual(mod.get_env_file(), mod.PROJECT_ROOT / ".env")

    def test_is_server_node(self):
        mod = self._reload()
        self.assertFalse(mod.is_server_node())

        os.environ["BRE_NODE_ROLE"] = "server"
        self.assertTrue(mod.is_server_node())

        os.environ["BRE_NODE_ROLE"] = "Server"
        self.assertTrue(mod.is_server_node())

        os.environ["BRE_NODE_ROLE"] = "development"
        self.assertFalse(mod.is_server_node())


if __name__ == "__main__":
    unittest.main()
