"""The checked-in contract is generated from the actual typed FastAPI boundary."""

import importlib.util
from pathlib import Path


def test_member_openapi_has_no_generation_drift():
    spec = importlib.util.spec_from_file_location(
        "export_openapi", Path("scripts/export_openapi.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert Path("packages/contracts/openapi.json").read_text() == module.export()
