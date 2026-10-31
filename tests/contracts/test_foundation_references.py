"""External reference checkouts must not become Arbit planning artifacts."""

import importlib.util
import shutil
import subprocess
from pathlib import Path


def test_external_checkout_is_excluded_but_project_links_are_checked(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    tracked = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        .decode()
        .split("\0")
    )
    for name in filter(None, tracked):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    spec = importlib.util.spec_from_file_location(
        "foundation", root / "scripts/validate_foundation.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    foreign = tmp_path / ".references/vendor"
    foreign.mkdir(parents=True)
    (foreign / "foreign.json").write_text("This is not an Arbit JSON artifact")
    (foreign / "README.md").write_text("[External instructions](not-shipped.md)")
    scratch = tmp_path / "data/research"
    scratch.mkdir(parents=True)
    (scratch / "pending-capture.json").write_text("")
    errors, _ = module.validate(tmp_path)
    assert errors == []
    (tmp_path / "docs/broken.md").write_text("[Missing project artifact](missing.md)")
    errors, _ = module.validate(tmp_path)
    assert any("docs/broken.md: broken local link" in error for error in errors)
