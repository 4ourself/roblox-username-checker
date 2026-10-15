import importlib.util
import os
import sys

sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(ROOT, ".core", "checker_core.py")


def main():
    if not os.path.isfile(ENGINE):
        print("  a project file is missing - download the repository again.")
        return 1

    spec = importlib.util.spec_from_file_location("checker_core", ENGINE)
    core = importlib.util.module_from_spec(spec)
    sys.modules["checker_core"] = core
    spec.loader.exec_module(core)
    return core.main()


if __name__ == "__main__":
    sys.exit(main())
