"""
QQ机器人 - 桌面浮动控制台（纯桌面版，无Web）

功能：
- 显示当前运行状态
- 一键设置截图区域
- 暂停/恢复自动回复
- 手动发送消息
- 配置管理
- 查看聊天记录
- 查看日志
- 测试API连接
"""
import sys
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, Toplevel, Label, Entry, Button, Frame, StringVar, IntVar, DoubleVar, BooleanVar, Checkbutton, OptionMenu


class ConfigWindow:
    """配置管理子窗口（带滚动条）"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("配置管理")
        self.window.geometry("440x520")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        # 当前配置
        self.config = controller.get_config() or {}

        self.build_ui()
        self.load_values()

    def build_ui(self):
        # 外层容器（固定大小）
        outer = Frame(self.window)
        outer.pack(fill="both", expand=True)

        # Canvas + 滚动条
        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 可滚动内容 Frame
        container = Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw", width=410)

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=event.width)

        container.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        # 鼠标滚轮
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ====== 内容区（左右留边距）======
        pad = Frame(container)
        pad.pack(fill="x", expand=True, padx=10, pady=10)

        # 大模型配置
        self._section(pad, "大模型配置")
        self.entry_url = self._field(pad, "API地址:")
        self.entry_key = self._field(pad, "API密钥:", show="*")
        self.entry_model = self._field(pad, "模型名称:")
        self.entry_temp = self._field(pad, "温度:")
        self.entry_tokens = self._field(pad, "最大Token:")

        # 机器人配置
        self._section(pad, "机器人配置")
        self.entry_bot_name = self._field(pad, "机器人昵称:")
        self.entry_reply_prob = self._field(pad, "回复概率:")
        self.entry_system_prompt = self._text_field(pad, "系统提示词:", height=4)

        # 截图配置
        self._section(pad, "截图配置")
        row_mode = Frame(pad)
        row_mode.pack(fill="x", pady=2)
        Label(row_mode, text="运行模式:", width=12, anchor="w").pack(side="left")
        self.var_mode = StringVar(value="region")
        OptionMenu(row_mode, self.var_mode, "region", "manual", "auto").pack(side="left", fill="x", expand=True)

        self.entry_interval = self._field(pad, "截图间隔(秒):")
        self.entry_area_ratio = self._field(pad, "消息区域比例:")
        self.var_debug = BooleanVar()
        Checkbutton(pad, text="保存调试用截图", variable=self.var_debug, anchor="w").pack(fill="x", pady=2)

        # 过滤与记忆
        self._section(pad, "过滤与记忆")
        self.var_ignore_me = BooleanVar()
        Checkbutton(pad, text="忽略自己的消息", variable=self.var_ignore_me, anchor="w").pack(fill="x", pady=2)
        self.var_memory = BooleanVar()
        Checkbutton(pad, text="开启聊天记录保存", variable=self.var_memory, anchor="w").pack(fill="x", pady=2)
        self.entry_max_hist = self._field(pad, "最大历史消息:")
        self.entry_load_recent = self._field(pad, "加载近期记忆:")

        # 按钮
        btn_frame = Frame(pad)
        btn_frame.pack(pady=15)

        Button(btn_frame, text="保存配置", command=self.on_save, bg="#667eea", fg="white", width=12).pack(side="left", padx=5)
        Button(btn_frame, text="测试API", command=self.on_test_api, bg="#48bb78", fg="white", width=12).pack(side="left", padx=5)
        Button(btn_frame, text="关闭", command=self.window.destroy, width=10).pack(side="left", padx=5)

        self._canvas = canvas

    def _section(self, parent, title):
        Label(parent, text=title, font=("Microsoft YaHei", 10, "bold"), fg="#667eea", anchor="w").pack(
            fill="x", pady=(12, 4)
        )

    def _field(self, parent, label, show=None):
        row = Frame(parent)
        row.pack(fill="x", pady=2)
        Label(row, text=label, width=12, anchor="w").pack(side="left")
        entry = Entry(row, show=show)
        entry.pack(side="left", fill="x", expand=True, padx=(5, 0))
        return entry

    def _text_field(self, parent, label, height=3):
        row = Frame(parent)
        row.pack(fill="x", pady=2)
        Label(row, text=label, width=12, anchor="nw").pack(side="left", anchor="n")
        text = tk.Text(row, height=height, wrap="word")
        text.pack(side="left", fill="x", expand=True, padx=(5, 0))
        return text

    def load_values(self):
        llm = self.config.get("llm", {})
        self.entry_url.insert(0, llm.get("base_url", ""))
        self.entry_key.insert(0, llm.get("api_key", ""))
        self.entry_model.insert(0, llm.get("model", ""))
        self.entry_temp.insert(0, str(llm.get("temperature", 0.7)))
        self.entry_tokens.insert(0, str(llm.get("max_tokens", 500)))

        bot = self.config.get("bot", {})
        self.entry_bot_name.insert(0, bot.get("name", ""))
        self.entry_reply_prob.insert(0, str(bot.get("reply_probability", 1.0)))
        self.entry_system_prompt.insert("1.0", bot.get("system_prompt", "你是一个 helpful assistant."))

        capture = self.config.get("capture", {})
        self.var_mode.set(capture.get("mode", "region"))
        self.entry_interval.insert(0, str(capture.get("interval", 3)))
        self.entry_area_ratio.insert(0, str(capture.get("message_area_ratio", 0.7)))
        self.var_debug.set(capture.get("debug_screenshots", False))

        filter_cfg = self.config.get("filter", {})
        self.var_ignore_me.set(filter_cfg.get("ignore_my_messages", True))
        self.entry_max_hist.insert(0, str(filter_cfg.get("max_history_messages", 10)))

        memory = self.config.get("memory", {})
        self.var_memory.set(memory.get("enabled", True))
        self.entry_load_recent.insert(0, str(memory.get("load_recent", 20)))

    def on_save(self):
        try:
            new_config = {
                "llm": {
                    "base_url": self.entry_url.get().strip(),
                    "api_key": self.entry_key.get().strip(),
                    "model": self.entry_model.get().strip(),
                    "temperature": float(self.entry_temp.get() or 0.7),
                    "max_tokens": int(self.entry_tokens.get() or 500),
                },
                "bot": {
                    "name": self.entry_bot_name.get().strip(),
                    "reply_probability": float(self.entry_reply_prob.get() or 1.0),
                    "system_prompt": self.entry_system_prompt.get("1.0", "end").strip(),
                },
                "capture": {
                    "mode": self.var_mode.get(),
                    "interval": int(self.entry_interval.get() or 3),
                    "message_area_ratio": float(self.entry_area_ratio.get() or 0.7),
                    "debug_screenshots": self.var_debug.get(),
                    "window_title_keywords": ["QQ"],
                    "debug_dir": "debug_screenshots",
                    "screenshot_dir": "screenshots",
                },
                "filter": {
                    "ignore_my_messages": self.var_ignore_me.get(),
                    "max_history_messages": int(self.entry_max_hist.get() or 10),
                },
                "memory": {
                    "enabled": self.var_memory.get(),
                    "load_recent": int(self.entry_load_recent.get() or 20),
                    "data_dir": "data",
                    "split_by_date": True,
                },
                "desktop": self.config.get("desktop", {"enabled": True, "desktop_name": "QQ机器人"}),
            }

            # 保留已有区域配置
            if self.config.get("capture", {}).get("read_rect"):
                new_config["capture"]["read_rect"] = self.config["capture"]["read_rect"]
            if self.config.get("capture", {}).get("reply_pos"):
                new_config["capture"]["reply_pos"] = self.config["capture"]["reply_pos"]

            if self.controller.save_config(new_config):
                messagebox.showinfo("成功", "配置已保存并生效")
            else:
                messagebox.showerror("错误", "保存配置失败")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")

    def on_test_api(self):
        result = self.controller.test_api()
        if result:
            messagebox.showinfo("API测试", "连接成功！")
        else:
            messagebox.showerror("API测试", "连接失败，请检查API地址和密钥")


class SendWindow:
    """手动发送消息子窗口"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("发送消息")
        self.window.geometry("360x160")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        Label(self.window, text="消息内容:", anchor="w").pack(fill="x", padx=10, pady=(10, 2))

        self.text = tk.Text(self.window, height=3, wrap="word")
        self.text.pack(fill="x", padx=10, pady=2)
        self.text.focus()

        btn_frame = Frame(self.window)
        btn_frame.pack(pady=8)

        Button(btn_frame, text="发送", command=self.on_send, bg="#667eea", fg="white", width=10).pack(side="left", padx=5)
        Button(btn_frame, text="关闭", command=self.window.destroy, width=10).pack(side="left", padx=5)

        self.text.bind("<Return>", lambda e: self.on_send())

    def on_send(self):
        msg = self.text.get("1.0", "end").strip()
        if not msg:
            return
        self.controller.send_message(msg)
        self.text.delete("1.0", "end")


class MessagesWindow:
    """聊天记录子窗口（支持搜索、导出）"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("聊天记录")
        self.window.geometry("560x450")
        self.window.transient(parent)

        # 工具栏
        toolbar = Frame(self.window)
        toolbar.pack(fill="x", padx=5, pady=5)

        Button(toolbar, text="刷新", command=self.load).pack(side="left", padx=2)

        self.search_var = tk.StringVar()
        Entry(toolbar, textvariable=self.search_var, width=15).pack(side="left", padx=2)
        Button(toolbar, text="搜索", command=self.load).pack(side="left", padx=2)

        Button(toolbar, text="导出JSON", command=self.on_export, bg="#4299e1", fg="white").pack(side="left", padx=2)
        Button(toolbar, text="清空历史", command=self.on_clear, bg="#f56565", fg="white").pack(side="left", padx=2)

        # 消息列表
        self.text = scrolledtext.ScrolledText(self.window, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=5, pady=5)

        self.load()

    def load(self):
        msgs = self.controller.get_messages(count=200)
        query = self.search_var.get().strip().lower()

        if query:
            msgs = [m for m in msgs if query in m.get("content", "").lower() or query in m.get("sender", "").lower()]

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        if not msgs:
            self.text.insert("end", "暂无记录\n")
        else:
            for m in msgs:
                sender = m.get("sender", "未知")
                content = m.get("content", "")
                ts = m.get("timestamp", "")
                flag = "[BOT] " if m.get("is_bot") else ""
                self.text.insert("end", f"[{ts}] {flag}{sender}: {content}\n\n")

        self.text.configure(state="disabled")
        self.text.see("end")

    def on_export(self):
        from datetime import datetime
        filename = f"chat_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        if self.controller.export_messages(filename):
            messagebox.showinfo("导出成功", f"聊天记录已导出到:\n{os.path.abspath(filename)}")
        else:
            messagebox.showerror("导出失败", "导出聊天记录失败")

    def on_clear(self):
        if not messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            return
        self.controller.clear_history()
        self.load()


class MemoryWindow:
    """记忆管理子窗口"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("记忆管理")
        self.window.geometry("500x400")
        self.window.transient(parent)

        toolbar = Frame(self.window)
        toolbar.pack(fill="x", padx=5, pady=5)

        Button(toolbar, text="刷新", command=self.load).pack(side="left", padx=2)
        Button(toolbar, text="清空记忆", command=self.on_clear, bg="#f56565", fg="white").pack(side="left", padx=2)

        self.text = scrolledtext.ScrolledText(self.window, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=5, pady=5)

        self.load()

    def load(self):
        records = self.controller.get_memory_records(count=100)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        if not records:
            self.text.insert("end", "暂无记忆记录\n")
        else:
            for r in records:
                sender = r.get("sender", "未知")
                content = r.get("content", "")
                ts = r.get("timestamp", "")
                flag = "[BOT] " if r.get("is_bot") else ""
                self.text.insert("end", f"[{ts}] {flag}{sender}: {content}\n\n")

        self.text.configure(state="disabled")
        self.text.see("end")

    def on_clear(self):
        if not messagebox.askyesno("确认", "确定要清空所有记忆吗？"):
            return
        self.controller.clear_history()
        self.load()


class StreamWindow:
    """实时消息流子窗口"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("实时消息流")
        self.window.geometry("450x400")
        self.window.transient(parent)

        toolbar = Frame(self.window)
        toolbar.pack(fill="x", padx=5, pady=5)
        Label(toolbar, text="新消息和机器人回复会实时显示在这里").pack(side="left")

        self.text = scrolledtext.ScrolledText(self.window, wrap="word", state="disabled", height=20)
        self.text.pack(fill="both", expand=True, padx=5, pady=5)

        self.start_poll()

    def add_message(self, sender, content, is_bot=False, timestamp=""):
        self.text.configure(state="normal")
        flag = "[BOT] " if is_bot else ""
        ts = timestamp or time.strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {flag}{sender}: {content}\n\n")
        self.text.configure(state="disabled")
        self.text.see("end")

    def start_poll(self):
        last_count = 0
        def poll():
            nonlocal last_count
            while True:
                try:
                    time.sleep(2)
                    if not self.window.winfo_exists():
                        break
                    msgs = self.controller.get_messages(count=20)
                    if len(msgs) != last_count:
                        last_count = len(msgs)
                        self.window.after(0, lambda: self._refresh(msgs[-10:]))
                except Exception:
                    break
        t = threading.Thread(target=poll, daemon=True)
        t.start()

    def _refresh(self, msgs):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for m in msgs:
            sender = m.get("sender", "未知")
            content = m.get("content", "")
            ts = m.get("timestamp", "")
            flag = "[BOT] " if m.get("is_bot") else ""
            self.text.insert("end", f"[{ts}] {flag}{sender}: {content}\n\n")
        self.text.configure(state="disabled")
        self.text.see("end")


class LogsWindow:
    """日志查看子窗口"""

    def __init__(self, parent, controller):
        self.controller = controller
        self.window = Toplevel(parent)
        self.window.title("运行日志")
        self.window.geometry("600x400")
        self.window.transient(parent)

        toolbar = Frame(self.window)
        toolbar.pack(fill="x", padx=5, pady=5)

        Button(toolbar, text="刷新", command=self.load).pack(side="left", padx=2)
        Button(toolbar, text="清空显示", command=self.clear).pack(side="left", padx=2)
        Button(toolbar, text="下载日志", command=self.on_download, bg="#4299e1", fg="white").pack(side="left", padx=2)

        self.text = scrolledtext.ScrolledText(self.window, wrap="word", state="disabled")
        self.text.pack(fill="both", expand=True, padx=5, pady=5)

        self.load()
        self.start_poll()

    def load(self):
        logs = self.controller.get_logs(lines=200)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")

        if not logs:
            self.text.insert("end", "暂无日志\n")
        else:
            for line in logs:
                self.text.insert("end", line if line.endswith("\n") else line + "\n")

        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def on_download(self):
        from datetime import datetime
        dest = f"bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            import shutil
            shutil.copy("bot.log", dest)
            messagebox.showinfo("下载成功", f"日志已复制到:\n{os.path.abspath(dest)}")
        except Exception as e:
            messagebox.showerror("下载失败", str(e))

    def start_poll(self):
        def poll():
            while True:
                try:
                    time.sleep(3)
                    if not self.window.winfo_exists():
                        break
                    self.window.after(0, self.load)
                except Exception:
                    break

        t = threading.Thread(target=poll, daemon=True)
        t.start()


class DesktopWidget:
    """桌面浮动控制台主窗口"""

    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("QQ机器人")
        self.root.geometry("240x500")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{sw - 260}+20")

        self._drag_start_x = 0
        self._drag_start_y = 0

        self.build_ui()
        self.start_status_poll()

    def build_ui(self):
        # ====== 标题栏（可拖动） ======
        title_frame = Frame(self.root, bg="#667eea", height=32)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)

        title_frame.bind("<Button-1>", self.on_drag_start)
        title_frame.bind("<B1-Motion>", self.on_drag_move)

        Label(title_frame, text="QQ机器人", bg="#667eea", fg="white",
              font=("Microsoft YaHei", 10, "bold")).pack(side="left", padx=10, pady=2)

        close_lbl = Label(title_frame, text="x", bg="#667eea", fg="white",
                          font=("Microsoft YaHei", 10), cursor="hand2")
        close_lbl.pack(side="right", padx=10, pady=2)
        close_lbl.bind("<Button-1>", lambda e: self.on_exit())

        # ====== 主体 ======
        body = Frame(self.root, bg="white")
        body.pack(fill="both", expand=True)

        # 状态区
        self.status_label = Label(body, text="状态: 初始化...", bg="white", fg="#333",
                                   font=("Microsoft YaHei", 9, "bold"))
        self.status_label.pack(pady=(10, 2))

        self.mode_label = Label(body, text="模式: -", bg="white", fg="#666", font=("Microsoft YaHei", 8))
        self.mode_label.pack(pady=1)

        self.window_label = Label(body, text="QQ窗口: -", bg="white", fg="#666", font=("Microsoft YaHei", 8))
        self.window_label.pack(pady=1)

        self.capture_label = Label(body, text="最后捕获: -", bg="white", fg="#666", font=("Microsoft YaHei", 8))
        self.capture_label.pack(pady=1)

        self.reply_label = Label(body, text="最后回复: -", bg="white", fg="#666", font=("Microsoft YaHei", 8))
        self.reply_label.pack(pady=1)

        self.count_label = Label(body, text="消息数: 0", bg="white", fg="#666", font=("Microsoft YaHei", 8))
        self.count_label.pack(pady=1)

        # 按钮区
        btn_frame = Frame(body, bg="white")
        btn_frame.pack(pady=10)

        Button(btn_frame, text="设置区域", command=self.on_set_region,
               width=12, bg="#667eea", fg="white", relief="flat", cursor="hand2").pack(pady=2)

        self.btn_toggle = Button(btn_frame, text="暂停", command=self.on_toggle,
                                  width=12, bg="#ed8936", fg="white", relief="flat", cursor="hand2")
        self.btn_toggle.pack(pady=2)

        Button(btn_frame, text="发送消息", command=self.on_send_msg,
               width=12, bg="#4299e1", fg="white", relief="flat", cursor="hand2").pack(pady=2)

        Button(btn_frame, text="配置", command=self.on_config,
               width=12, bg="#805ad5", fg="white", relief="flat", cursor="hand2").pack(pady=2)

        sub_frame = Frame(btn_frame, bg="white")
        sub_frame.pack(pady=2)

        Button(sub_frame, text="记录", command=self.on_messages,
               width=5, bg="#38b2ac", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        Button(sub_frame, text="记忆", command=self.on_memory,
               width=5, bg="#38b2ac", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        Button(sub_frame, text="日志", command=self.on_logs,
               width=5, bg="#38b2ac", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        Button(sub_frame, text="测试", command=self.on_test_api,
               width=5, bg="#48bb78", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        Button(sub_frame, text="清空", command=self.on_clear,
               width=5, bg="#f56565", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        sub_frame2 = Frame(btn_frame, bg="white")
        sub_frame2.pack(pady=2)

        Button(sub_frame2, text="消息流", command=self.on_stream,
               width=8, bg="#9f7aea", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        Button(sub_frame2, text="切桌面", command=self.on_switch_desktop,
               width=8, bg="#ed8936", fg="white", relief="flat", cursor="hand2").pack(side="left", padx=1)

        # 最近识别消息（排查用）
        detect_frame = Frame(body, bg="white")
        detect_frame.pack(fill="x", padx=8, pady=(2, 0))
        Label(detect_frame, text="识别:", bg="white", fg="#999", font=("Microsoft YaHei", 7), anchor="w").pack(side="left")
        self.detect_label = Label(detect_frame, text="-", bg="white", fg="#666", font=("Microsoft YaHei", 7), anchor="w", wraplength=210)
        self.detect_label.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # 快捷键提示
        hotkey_frame = Frame(body, bg="white")
        hotkey_frame.pack(pady=(2, 0))
        Label(hotkey_frame, text="Ctrl+Q=退出  Ctrl+P=暂停", bg="white", fg="#999", font=("Microsoft YaHei", 7)).pack()

        # tkinter 快捷键绑定（窗口有焦点时生效）
        self.root.bind("<Control-q>", lambda e: self.on_exit())
        self.root.bind("<Control-p>", lambda e: self.on_toggle())

    def on_drag_start(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()

    def on_drag_move(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def on_set_region(self):
        self.controller.start_region_picker()

    def on_toggle(self):
        if self.controller.state.paused:
            self.controller.resume()
            self.btn_toggle.config(text="暂停", bg="#ed8936")
            self.status_label.config(text="状态: 运行中", fg="#48bb78")
        else:
            self.controller.pause()
            self.btn_toggle.config(text="恢复", bg="#48bb78")
            self.status_label.config(text="状态: 已暂停", fg="#ed8936")

    def on_send_msg(self):
        SendWindow(self.root, self.controller)

    def on_config(self):
        ConfigWindow(self.root, self.controller)

    def on_messages(self):
        MessagesWindow(self.root, self.controller)

    def on_memory(self):
        MemoryWindow(self.root, self.controller)

    def on_logs(self):
        LogsWindow(self.root, self.controller)

    def on_stream(self):
        StreamWindow(self.root, self.controller)

    def on_switch_desktop(self):
        result = self.controller.switch_desktop()
        if result:
            messagebox.showinfo("切换桌面", "已切换到QQ虚拟桌面")
        else:
            messagebox.showwarning("切换桌面", "虚拟桌面功能不可用或未启用")

    def on_test_api(self):
        result = self.controller.test_api()
        if result:
            messagebox.showinfo("API测试", "连接成功！")
        else:
            messagebox.showerror("API测试", "连接失败，请检查配置")

    def on_clear(self):
        if not messagebox.askyesno("确认", "确定要清空所有历史记录吗？"):
            return
        self.controller.clear_history()
        messagebox.showinfo("完成", "已清空")

    def on_exit(self):
        self.controller.state.running = False
        self.root.destroy()

    def update_status(self):
        status = self.controller.get_status()
        paused = status.get("paused", False)
        mode = status.get("mode", "auto")
        window = status.get("window_title", "")
        online = status.get("window_online", False)
        last_cap = status.get("last_capture", "")
        last_reply = status.get("last_reply", "")
        count = status.get("message_count", 0)

        mode_map = {"region": "区域模式", "manual": "手动模式", "auto": "自动窗口"}

        if paused:
            self.status_label.config(text="状态: 已暂停", fg="#ed8936")
            self.btn_toggle.config(text="恢复", bg="#48bb78")
        else:
            if online:
                self.status_label.config(text="状态: 运行中", fg="#48bb78")
            else:
                self.status_label.config(text="状态: 离线", fg="#f56565")
            self.btn_toggle.config(text="暂停", bg="#ed8936")

        self.mode_label.config(text=f"模式: {mode_map.get(mode, mode)}")
        self.window_label.config(text=f"QQ窗口: {window[:12] if window else '未检测'} {'在线' if online else '离线'}")
        self.capture_label.config(text=f"最后捕获: {last_cap or '-'}")
        self.reply_label.config(text=f"最后回复: {last_reply[:20] if last_reply else '-'}")
        self.count_label.config(text=f"消息数: {count}")

        last_detected = status.get("last_detected", "")
        self.detect_label.config(text=last_detected or "-")

    def start_status_poll(self):
        def poll():
            while True:
                try:
                    time.sleep(2)
                    if not self.root.winfo_exists():
                        break
                    self.root.after(0, self.update_status)
                except Exception:
                    break

        t = threading.Thread(target=poll, daemon=True)
        t.start()

    def run(self):
        self.root.mainloop()


def main():
    print("=" * 40)
    print("QQ机器人 - 桌面控制台")
    print("=" * 40)
    print("\n浮动窗口已启动（屏幕右上角）")
    print("可以拖动标题栏移动位置")
    print("关闭窗口会停止机器人\n")

    from main import BotController
    controller = BotController()
    if not controller.init():
        print("初始化失败，请检查 config.yaml 和依赖")
        return

    bot_thread = threading.Thread(target=controller.run_loop, daemon=True)
    bot_thread.start()

    widget = DesktopWidget(controller)
    widget.run()


if __name__ == "__main__":
    main()
