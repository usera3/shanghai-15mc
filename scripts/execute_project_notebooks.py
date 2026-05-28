from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
PYDEPS = WORKSPACE_ROOT / "pydeps"
if str(PYDEPS) not in sys.path:
    sys.path.insert(0, str(PYDEPS))

import nbformat
from nbclient import NotebookClient


KERNEL_NAME = "codex-shanghai-15mc"


def ensure_kernel() -> None:
    from ipykernel.kernelspec import install

    jupyter_path = WORKSPACE_ROOT / ".jupyter"
    jupyter_path.mkdir(exist_ok=True)
    os.environ["JUPYTER_PATH"] = str(jupyter_path)
    os.environ["PYTHONPATH"] = str(PYDEPS)
    os.environ["MPLBACKEND"] = "Agg"

    install(
        user=False,
        prefix=str(WORKSPACE_ROOT / ".kernel"),
        kernel_name=KERNEL_NAME,
        display_name="Codex Shanghai 15MC Kernel",
        env={"PYTHONPATH": str(PYDEPS), "MPLBACKEND": "Agg"},
    )
    os.environ["JUPYTER_PATH"] = os.pathsep.join(
        [
            str(PYDEPS / "share" / "jupyter"),
            str(WORKSPACE_ROOT / ".kernel" / "share" / "jupyter"),
            os.environ["JUPYTER_PATH"],
        ]
    )


def execute_notebook(path: Path) -> Path:
    nb = nbformat.read(path, as_version=4)
    nb.metadata.setdefault("kernelspec", {})
    nb.metadata["kernelspec"].update(
        {
            "display_name": "Codex Shanghai 15MC Kernel",
            "language": "python",
            "name": KERNEL_NAME,
        }
    )
    client = NotebookClient(
        nb,
        kernel_name=KERNEL_NAME,
        timeout=1800,
        resources={"metadata": {"path": str(ROOT / "notebooks")}},
    )
    client.execute()
    out = path.with_name(path.stem + ".executed.ipynb")
    nbformat.write(nb, out)
    return out


def main() -> None:
    ensure_kernel()
    outputs = []
    for path in sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb")):
        if path.stem.endswith(".executed"):
            continue
        outputs.append(str(execute_notebook(path)))
    print(json.dumps({"executed": outputs}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
