"""源码与打包程序共用入口：python run.py"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

if "--self-test" in sys.argv or "--selftest" in sys.argv:
    # 自检无需加载 UI、托盘或全局输入监听。
    from autoclicker.diagnostics import self_test
    raise SystemExit(0 if self_test() else 1)

from autoclicker.__main__ import main

if __name__ == "__main__":
    main()
