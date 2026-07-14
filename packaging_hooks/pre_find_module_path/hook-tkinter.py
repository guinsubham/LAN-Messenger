from pathlib import Path


def pre_find_module_path(hook_api):
    python_root = Path(r"C:\Users\PC-01-CR\.cache\codex-runtimes\codex-primary-runtime\dependencies\python")
    hook_api.search_dirs = [str(python_root / "Lib")]
