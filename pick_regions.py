"""
坐标选取工具 - 帮助获取QQ消息区域和回复输入框的屏幕坐标

使用方法：
1. 打开QQ群聊窗口
2. 运行: python pick_regions.py
3. 按照提示将鼠标移到对应位置，按回车记录坐标
4. 将输出的坐标复制到 config.yaml 中
"""
import sys
import time

if sys.platform == "win32":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

try:
    import pyautogui
except ImportError:
    print("请先安装 pyautogui: pip install pyautogui")
    sys.exit(1)


def get_position(prompt):
    """提示用户将鼠标移到指定位置，按回车记录坐标"""
    print(f"\n{prompt}")
    print("  将鼠标移到目标位置，然后按回车键记录坐标...")
    input("  (按回车键记录)")
    pos = pyautogui.position()
    print(f"  已记录: x={pos.x}, y={pos.y}")
    return pos


def main():
    print("=" * 60)
    print("QQ聊天机器人 - 坐标选取工具")
    print("=" * 60)
    print("\n步骤说明：")
    print("1. 请确保QQ群聊窗口已打开并可见")
    print("2. 按照提示将鼠标移到对应位置")
    print("3. 按回车键记录坐标")
    print("4. 最后将坐标复制到 config.yaml 中")
    print("\n提示：QQ NT客户端布局通常为：")
    print("  - 左侧：联系人列表")
    print("  - 中间：消息显示区域（你要截取的部分）")
    print("  - 右侧：群成员列表")
    print("  - 底部：消息输入框")

    # 获取消息区域
    print("\n" + "=" * 60)
    print("第一步：定义消息阅读区域")
    print("=" * 60)
    print("请框选QQ聊天窗口中显示消息的区域")
    print("（避开左侧联系人和右侧成员列表）")

    top_left = get_position("将鼠标移到消息区域的左上角")
    bottom_right = get_position("将鼠标移到消息区域的右下角")

    read_rect = [top_left.x, top_left.y, bottom_right.x, bottom_right.y]

    # 获取回复输入框位置
    print("\n" + "=" * 60)
    print("第二步：定义回复输入框位置")
    print("=" * 60)
    print("将鼠标移到QQ聊天窗口底部的消息输入框中央")
    print("（这是机器人点击后输入回复的位置）")

    reply = get_position("将鼠标移到输入框中央")
    reply_pos = [reply.x, reply.y]

    # 输出结果
    print("\n" + "=" * 60)
    print("坐标获取完成！")
    print("=" * 60)
    print("\n请将以下内容复制到 config.yaml 的 capture 部分：")
    print()
    print("capture:")
    print(f"  mode: region")
    print(f"  interval: 3")
    print(f"  read_rect: {read_rect}")
    print(f"  reply_pos: {reply_pos}")
    print(f"  # ... 其他配置保留 ...")
    print()
    print("然后重启机器人即可使用区域模式。")
    print("=" * 60)


if __name__ == "__main__":
    main()
