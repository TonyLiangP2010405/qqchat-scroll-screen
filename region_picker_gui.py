"""
浮动窗口区域选择工具

使用方法：
1. 确保QQ窗口可见
2. 运行: python region_picker_gui.py
3. 点击 [截取屏幕]，有3秒时间切换到QQ窗口
4. 在全屏截图上拖拽框选消息区域
5. 点击回复输入框位置
6. 点击 [保存配置]
"""
import sys
import time

from modules.platform_utils import enable_dpi_awareness

if sys.platform == "win32":
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass
    enable_dpi_awareness()

import tkinter as tk
from tkinter import messagebox


def load_yaml():
    import yaml
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def save_yaml(config):
    import yaml
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


class RegionPickerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QQ机器人 - 区域设置")
        self.root.geometry("360x260")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        # 放屏幕右下角
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - 380}+{sh - 300}")

        self.read_rect = None
        self.reply_pos = None
        self.step = 0
        self.fullscreen = None

        self.build_ui()

    def build_ui(self):
        pad = {"padx": 12, "pady": 4}

        tk.Label(
            self.root,
            text="设置截图区域",
            font=("Microsoft YaHei", 13, "bold"),
            fg="#333"
        ).pack(pady=(10, 4))

        tk.Label(
            self.root,
            text="1. 确保QQ窗口可见\n2. 点击 [截取屏幕]\n3. 框选消息区域，点击输入框位置",
            font=("Microsoft YaHei", 9),
            fg="#666",
            justify=tk.LEFT
        ).pack(**pad)

        self.status_var = tk.StringVar(value="点击 [截取屏幕] 开始")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Microsoft YaHei", 9, "bold"),
            fg="#667eea"
        ).pack(**pad)

        self.read_var = tk.StringVar(value="消息区域: 未设置")
        self.reply_var = tk.StringVar(value="回复位置: 未设置")
        tk.Label(self.root, textvariable=self.read_var, font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=16)
        tk.Label(self.root, textvariable=self.reply_var, font=("Microsoft YaHei", 9)).pack(anchor=tk.W, padx=16)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        self.btn_capture = tk.Button(
            btn_frame, text="截取屏幕", command=self.on_capture_click,
            width=12, bg="#667eea", fg="white", font=("Microsoft YaHei", 9, "bold")
        )
        self.btn_capture.pack(side=tk.LEFT, padx=4)

        self.btn_save = tk.Button(
            btn_frame, text="保存配置", command=self.on_save_click,
            width=12, state=tk.DISABLED, font=("Microsoft YaHei", 9)
        )
        self.btn_save.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="关闭", command=self.root.destroy,
            width=8, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=4)

    def on_capture_click(self):
        self.btn_capture.config(state=tk.DISABLED)
        self.status_var.set("3秒后截图，请切换到QQ窗口...")
        self.countdown(3)

    def countdown(self, n):
        if n > 0:
            self.status_var.set(f"{n}秒后截图，请切换到QQ窗口...")
            self.root.after(1000, lambda: self.countdown(n - 1))
        else:
            self.do_capture()

    def do_capture(self):
        try:
            from PIL import ImageGrab, ImageTk, Image
            screenshot = ImageGrab.grab()
            self.screenshot_img = screenshot
        except Exception as e:
            messagebox.showerror("错误", f"截图失败: {e}")
            self.btn_capture.config(state=tk.NORMAL)
            self.status_var.set("截图失败，请重试")
            return

        # 全屏选择窗口
        self.fullscreen = tk.Toplevel(self.root)
        self.fullscreen.attributes("-fullscreen", True)
        self.fullscreen.attributes("-topmost", True)
        self.fullscreen.configure(bg="black")

        # 解决 Windows DPI 缩放：用 tkinter 报告的屏幕尺寸，截图缩放到匹配
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if screenshot.size != (sw, sh):
            screenshot = screenshot.resize((sw, sh), Image.Resampling.LANCZOS)

        self.photo = ImageTk.PhotoImage(screenshot)

        canvas = tk.Canvas(
            self.fullscreen,
            width=sw,
            height=sh,
            highlightthickness=0,
            cursor="crosshair"
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)

        # 提示文字
        self.hint_id = canvas.create_text(
            sw // 2, 40,
            text="第一步：拖拽框选消息区域",
            font=("Microsoft YaHei", 18, "bold"),
            fill="red",
            tags="hint"
        )

        tk.Label(
            self.fullscreen,
            text="Esc 取消 | 拖拽框选 | 点击标记",
            font=("Microsoft YaHei", 10),
            fg="white",
            bg="black"
        ).place(x=10, y=10)

        self.canvas = canvas
        self.step = 1
        self.start_x = None
        self.start_y = None
        self.rect_id = None

        canvas.bind("<Button-1>", self.on_mouse_down)
        canvas.bind("<B1-Motion>", self.on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        # ESC 绑定到 canvas 和 fullscreen 确保一定能收到
        canvas.bind("<Escape>", lambda e: self.on_cancel())
        self.fullscreen.bind("<Escape>", lambda e: self.on_cancel())
        self.fullscreen.bind("<KeyPress-Escape>", lambda e: self.on_cancel())
        self.fullscreen.focus_set()

    def on_mouse_down(self, event):
        if self.step == 1:
            self.start_x = event.x
            self.start_y = event.y
            self.rect_id = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#ff0000", width=3, tags="sel"
            )
        elif self.step == 2:
            self.start_x = event.x
            self.start_y = event.y
            self.rect_id = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#00aa00", width=3, tags="sel"
            )

    def on_mouse_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_mouse_up(self, event):
        coords = self.canvas.coords(self.rect_id)
        if len(coords) < 4:
            return
        x1, y1, x2, y2 = coords
        w = abs(x2 - x1)
        h = abs(y2 - y1)

        if self.step == 1:
            # 如果矩形太小（误点击），忽略
            if w < 10 or h < 10:
                self.canvas.delete(self.rect_id)
                self.rect_id = None
                return
            self.read_rect = [int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2))]
            self.read_var.set(f"消息区域: {self.read_rect}")

            # 进入第二步
            self.step = 2
            self.canvas.itemconfig(self.hint_id, text="第二步：拖拽框选回复输入框区域")
            self.canvas.itemconfig(self.hint_id, fill="#00aa00")

        elif self.step == 2:
            if w < 5 or h < 5:
                # 如果是单击（没拖拽），直接以点击位置为中心点
                cx, cy = event.x, event.y
            else:
                # 框选了区域，取中心点
                cx = int((min(x1, x2) + max(x1, x2)) / 2)
                cy = int((min(y1, y2) + max(y1, y2)) / 2)
                # 保留绿色框
                self.rect_id = None

            self.reply_pos = [cx, cy]
            self.reply_var.set(f"回复位置: {self.reply_pos}")

            # 画红点标记中心点
            r = 8
            self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#ff4444", outline="white", width=3, tags="point"
            )
            self.canvas.create_text(
                cx, cy - 18,
                text="回复位置",
                fill="#ff4444", font=("Microsoft YaHei", 12, "bold"),
                tags="point"
            )

            # 显示确认按钮，不自动关闭
            self.show_confirm_buttons()

    def show_confirm_buttons(self):
        self.canvas.itemconfig(self.hint_id, text="确认位置无误后点击 [确认]")
        self.canvas.itemconfig(self.hint_id, fill="#00aa00")

        btn_w = 80
        btn_h = 32
        cx = self.root.winfo_screenwidth() // 2
        cy = self.root.winfo_screenheight() - 80

        self.canvas.create_rectangle(
            cx - btn_w - 10, cy - btn_h // 2,
            cx - 10, cy + btn_h // 2,
            fill="#667eea", outline="white", width=2, tags="confirm"
        )
        self.canvas.create_text(
            cx - btn_w // 2 - 5, cy,
            text="确认", fill="white", font=("Microsoft YaHei", 12, "bold"),
            tags="confirm"
        )

        self.canvas.create_rectangle(
            cx + 10, cy - btn_h // 2,
            cx + btn_w + 10, cy + btn_h // 2,
            fill="#f56565", outline="white", width=2, tags="confirm"
        )
        self.canvas.create_text(
            cx + btn_w // 2 + 5, cy,
            text="重选", fill="white", font=("Microsoft YaHei", 12, "bold"),
            tags="confirm"
        )

        # 绑定点击
        self.canvas.bind("<Button-1>", self.on_confirm_click)

    def on_confirm_click(self, event):
        cx = self.root.winfo_screenwidth() // 2
        cy = self.root.winfo_screenheight() - 80
        btn_w = 80
        btn_h = 32

        # 点击了"确认"
        if (cx - btn_w - 10 <= event.x <= cx - 10 and
                cy - btn_h // 2 <= event.y <= cy + btn_h // 2):
            self.close_fullscreen()
            self.status_var.set("区域设置完成，点击 [保存配置]")
            self.btn_save.config(state=tk.NORMAL)
            return

        # 点击了"重选"
        if (cx + 10 <= event.x <= cx + btn_w + 10 and
                cy - btn_h // 2 <= event.y <= cy + btn_h // 2):
            self.step = 1
            self.read_rect = None
            self.reply_pos = None
            self.canvas.delete("sel")
            self.canvas.delete("point")
            self.canvas.delete("confirm")
            self.canvas.itemconfig(self.hint_id, text="第一步：拖拽框选消息区域")
            self.canvas.itemconfig(self.hint_id, fill="red")
            self.canvas.bind("<Button-1>", self.on_mouse_down)
            self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
            return

    def close_fullscreen(self):
        if self.fullscreen:
            self.fullscreen.destroy()
            self.fullscreen = None

    def on_cancel(self):
        """ESC 取消选择"""
        self.close_fullscreen()
        self.step = 0
        self.read_rect = None
        self.reply_pos = None
        self.read_var.set("消息区域: 未设置")
        self.reply_var.set("回复位置: 未设置")
        self.status_var.set("已取消，点击 [截取屏幕] 重新开始")
        self.btn_capture.config(state=tk.NORMAL)
        self.btn_save.config(state=tk.DISABLED)

    def on_save_click(self):
        if not self.read_rect:
            messagebox.showwarning("提示", "请先设置区域")
            return

        try:
            config = load_yaml()
            if "capture" not in config:
                config["capture"] = {}

            config["capture"]["mode"] = "region"
            config["capture"]["read_rect"] = self.read_rect
            config["capture"]["reply_pos"] = self.reply_pos

            save_yaml(config)
            messagebox.showinfo("成功", "区域配置已保存到 config.yaml\n机器人将在几秒后自动加载新配置。")
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def run(self):
        self.root.mainloop()


def main():
    print("=" * 50)
    print("QQ机器人 - 区域设置工具")
    print("=" * 50)
    print("\n浮动窗口已启动（屏幕右下角）")
    print("如果没有出现，请检查是否已安装 tkinter\n")
    app = RegionPickerApp()
    app.run()


if __name__ == "__main__":
    main()
