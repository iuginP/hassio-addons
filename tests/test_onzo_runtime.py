import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "onzo_smart_energy/runtime.py"
SPEC = importlib.util.spec_from_file_location("onzo_runtime", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(runtime)


class OnzoRuntimeTests(unittest.TestCase):
    def test_all_unique_hid_paths_are_returned(self):
        devices = [
            {"path": b"/dev/hidraw1"},
            {"path": b"/dev/hidraw2"},
            {"path": b"/dev/hidraw1"},
            {"serial_number": "missing path"},
        ]
        self.assertEqual(
            runtime.device_paths(devices),
            {
                b"/dev/hidraw1": b"/dev/hidraw1",
                b"/dev/hidraw2": b"/dev/hidraw2",
            },
        )


if __name__ == "__main__":
    unittest.main()
