"""
QQ机器人启动器 - 一键启动机器人和桌面控制台

使用方法：
    python start_bot.py

这会启动主程序，主程序内部会同时运行：
1. 机器人主循环（后台线程）
2. 桌面浮动控制台（主线程）
"""
import sys
import os
import subprocess

if sys.platform == "win32":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass


def main():
    print("=" * 50)
    print("QQ机器人启动器")
    print("=" * 50)

    script_path = os.path.join(os.path.dirname(__file__), "main.py")
    python_exe = sys.executable

    print(f"\n正在启动: {script_path}")
    print("按 Ctrl+C 停止\n")

    try:
        subprocess.run([python_exe, script_path])
    except KeyboardInterrupt:
        print("\n已退出")


if __name__ == "__main__":
    main()
