from importlib import util as importlib_util
from pathlib import Path


def load_module_from_path(module_name: str, module_path: Path):
    spec = importlib_util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {module_path}")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_all_modules():
    base_dir = Path(__file__).resolve().parent
    module_files = sorted(base_dir.glob("module_*.py"))

    results = {}
    errors = {}

    for module_file in module_files:
        module_name = module_file.stem
        case_suffix = module_name.split("_")[-1].lstrip("0") or "0"
        func_name = f"case_{case_suffix}"

        try:
            module = load_module_from_path(module_name, module_file)
            func = getattr(module, func_name)
            results[module_name] = func()
        except Exception as exc:  # noqa: BLE001
            errors[module_name] = str(exc)

    print("=== Call Results ===")
    for name, value in results.items():
        print(f"{name}: {value}")

    print("\n=== Errors ===")
    if not errors:
        print("No errors")
    else:
        for name, message in errors.items():
            print(f"{name}: {message}")

    print(f"\nTotal modules: {len(module_files)}")
    print(f"Success: {len(results)}")
    print(f"Failed: {len(errors)}")


if __name__ == "__main__":
    call_all_modules()
