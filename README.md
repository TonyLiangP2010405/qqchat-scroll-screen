# QQ群聊自动回复机器人（桌面版）

一个完全基于桌面的 QQ 群聊自动回复机器人，无需 Web 界面，通过屏幕区域截图 + OCR 识别 + 大模型 API 实现自动回复。

## 功能特性

- **区域截图模式**：拖拽选择 QQ 聊天消息区域和输入框位置
- **自动回复**：识别新消息后自动调用大模型 API 生成回复并发送
- **桌面浮动控制台**：始终置顶的可拖动窗口，所有功能一键操作
- **OCR 文字识别**：使用 PaddleOCR，中文识别效果好
- **概率控制**：可设置回复概率，避免每条消息都回复
- **消息去重**：相似度检测，防止 OCR 微小差异导致重复回复
- **全局快捷键**：Ctrl+Q 退出，Ctrl+P 暂停/恢复
- **配置管理**：图形化配置窗口，实时修改 API、模型、概率等
- **聊天记录**：查看、搜索、导出历史记录
- **实时消息流**：实时显示识别到的消息和机器人回复
- **虚拟桌面切换**：一键切换到 QQ 所在虚拟桌面

## 系统要求

- Windows 10/11
- Python 3.10+
- QQ 桌面客户端
- 足够的屏幕分辨率（建议 1920x1080 及以上）

## 安装步骤

### 1. 克隆/下载项目

```bash
cd qqchat-scroll-screen
```

### 2. 创建 conda 环境（推荐）

```bash
conda create -n alpha python=3.10
conda activate alpha
```

### 3. 安装依赖

```bash
pip install pyautogui pyperclip pywin32 keyboard pynput pillow pyyaml openai easyocr

# PaddleOCR 及其依赖（中文识别效果更好）
pip install paddlepaddle==2.6.2 paddleocr==2.7.3
pip install numpy==1.26.4
```

### 4. 配置 config.yaml

编辑 `config.yaml`，填入你的大模型 API 信息：

```yaml
llm:
  base_url: https://api.deepseek.com/v1    # API 地址
  api_key: sk-xxxxxxxxxxxxxxxxxxxxxxxxx    # API 密钥
  model: deepseek-chat                      # 模型名称
  temperature: 0.7
  max_tokens: 120                           # 回复长度（约60-80汉字）

bot:
  name: 小助手                              # 机器人昵称
  reply_probability: 0.3                    # 回复概率 0.0-1.0
  system_prompt: '你是一个活跃的QQ群友...'   # 角色设定
```

## 使用方法

### 首次启动

```bash
python main.py
```

### 1. 设置截图区域

1. 打开 QQ 聊天窗口，调整到合适大小和位置
2. 点击浮动窗口的**"设置区域"**按钮
3. **第一步**：拖拽选择消息阅读区域（显示聊天消息的地方）
4. 点击**"下一步"**
5. **第二步**：点击 QQ 输入框位置（光标会闪烁的地方）
6. 点击**"确认"**保存

### 2. 启动自动回复

1. 确保 QQ 聊天窗口在消息区域后方可见
2. 浮动窗口显示"状态: 运行中"即表示正常工作
3. 机器人会自动截图 → OCR 识别 → 调用大模型 → 自动发送回复

### 3. 暂停/恢复

- 点击浮动窗口的**"暂停/恢复"**按钮
- 或按全局快捷键 **Ctrl+P**

### 4. 退出程序

- 点击浮动窗口右上角的 **x**
- 或按全局快捷键 **Ctrl+Q**

## 浮动控制台按钮说明

| 按钮 | 功能 |
|------|------|
| 设置区域 | 重新选择消息区域和输入框位置 |
| 暂停/恢复 | 暂停或恢复自动回复 |
| 发送消息 | 手动输入并发送消息 |
| 配置 | 打开配置管理窗口（API、概率、提示词等） |
| 记录 | 查看聊天记录（支持搜索、导出） |
| 记忆 | 查看记忆存储的上下文 |
| 日志 | 查看运行日志（支持下载） |
| 测试 | 测试 API 连接是否正常 |
| 清空 | 清空所有历史记录 |
| 消息流 | 实时消息流窗口 |
| 切桌面 | 切换到 QQ 所在虚拟桌面 |

## 配置文件详解

### config.yaml

```yaml
llm:
  base_url: https://api.deepseek.com/v1    # 大模型 API 地址
  api_key: sk-xxx                           # API 密钥
  model: deepseek-chat                      # 模型名称
  temperature: 0.7                          # 创造性 0-2
  max_tokens: 120                           # 最大回复长度

bot:
  name: 小助手                              # 机器人昵称（用于过滤自己消息）
  reply_probability: 1.0                    # 回复概率 1.0=100%
  system_prompt: '...'                      # 角色设定/系统提示词

capture:
  mode: region                              # 模式：region=区域截图
  interval: 10                              # 截图间隔（秒）
  read_rect: [x1, y1, x2, y2]              # 消息阅读区域坐标
  reply_pos: [x, y]                         # 输入框点击坐标
  message_area_ratio: 0.7                   # 消息区域裁剪比例
  debug_screenshots: false                  # 是否保存调试图

filter:
  ignore_my_messages: true                  # 是否忽略机器人自己发的消息
  max_history_messages: 10                  # 上下文历史消息数

memory:
  enabled: true                             # 是否保存聊天记录
  data_dir: data                            # 数据目录
  split_by_date: true                       # 按日期分割文件
  load_recent: 20                           # 加载近期记忆条数
```

## 项目结构

```
qqchat-scroll-screen/
├── main.py                  # 主入口，BotController 控制逻辑
├── config.yaml              # 配置文件
├── desktop_widget.py        # 桌面浮动控制台（tkinter）
├── region_picker_gui.py     # 区域选择器
├── test_send.py             # 自动发送测试脚本
├── test_typer.py            # 键盘鼠标测试脚本
├── record_input.py          # 输入录制工具
├── modules/
│   ├── ocr_engine.py        # OCR 引擎（PaddleOCR）
│   ├── auto_typer.py        # 自动输入（pyautogui）
│   ├── llm_client.py        # 大模型 API 客户端
│   ├── message_parser.py    # 消息解析与去重
│   ├── screenshot.py        # 截图工具
│   ├── window_finder.py     # QQ 窗口查找
│   ├── memory_store.py      # 聊天记录存储
│   ├── desktop_manager.py   # 虚拟桌面管理
│   └── __init__.py
├── data/                    # 聊天记录存储目录
├── screenshots/             # 截图保存目录
└── bot.log                  # 运行日志
```

## 核心模块说明

### OCR 引擎（modules/ocr_engine.py）

使用 PaddleOCR 进行中文文字识别。支持 PIL Image 和 numpy array 输入。

**注意**：首次运行会自动下载模型文件（约 100MB），请确保网络畅通。

### 自动输入（modules/auto_typer.py）

使用 pyautogui + pyperclip 实现自动输入中文消息：
1. 点击指定坐标进入输入框
2. 复制消息到剪贴板
3. Ctrl+V 粘贴
4. 按回车发送

### 消息解析（modules/message_parser.py）

- 将 OCR 结果按行分组
- 提取发送者昵称（支持 QQ 等级格式如 LV100）
- 相似度去重（防止 OCR 微小差异导致重复）
- 过滤机器人自己的消息

### LLM 客户端（modules/llm_client.py）

兼容 OpenAI 格式的大模型 API。支持：
- 自定义 base_url、api_key、model
- 系统提示词（长提示词自动合并到首条消息）
- 温度、最大 token 数控制

## 常见问题

### Q: 机器人不发消息怎么办？

1. 检查 `config.yaml` 中的 API 地址和密钥是否正确
2. 点击浮动窗口"测试"按钮验证 API 连接
3. 检查 `read_rect` 和 `reply_pos` 是否正确设置
4. 运行 `python test_send.py` 测试自动输入功能
5. 查看 `bot.log` 日志排查错误

### Q: 重复发消息/乱发消息怎么办？

1. 检查 OCR 识别质量：看浮动窗口"识别:"标签显示的内容
2. 调整截图区域，只框住聊天消息，不要包含其他 UI 元素
3. 降低 `reply_probability` 减少回复频率
4. 增加 `interval` 截图间隔

### Q: OCR 识别效果差？

1. 确保截图区域光线充足、文字清晰
2. 尝试调整 QQ 窗口大小，让文字更大
3. PaddleOCR 首次运行后，后续识别会更快更准确

### Q: 如何更换大模型？

修改 `config.yaml`：
```yaml
llm:
  base_url: https://你的API地址/v1
  api_key: sk-你的密钥
  model: 你的模型名
```

支持所有 OpenAI 格式的 API（DeepSeek、NVIDIA、阿里云等）。

### Q: 程序占用鼠标键盘？

发送消息时会短暂使用鼠标点击输入框、使用键盘粘贴。发送完成后会恢复鼠标位置。可以使用 Ctrl+P 随时暂停，Ctrl+Q 退出。

## 注意事项

1. **QQ 窗口位置**：设置区域后请勿移动 QQ 窗口，否则坐标会失效
2. **管理员权限**：如果 pyautogui 无法点击 QQ 窗口，尝试以管理员身份运行程序
3. **API 费用**：自动回复会消耗大模型 API 的 token，请注意额度
4. **频率限制**：建议 `interval` 不要设置太短（至少 5-10 秒），避免频繁截图和 API 调用
5. **隐私安全**：API 密钥保存在本地 `config.yaml` 中，请勿上传到公共仓库

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Q | 退出程序 |
| Ctrl+P | 暂停/恢复 |

## 更新日志

- 支持 PaddleOCR（中文识别效果更好）
- 支持回复概率控制
- 支持相似度去重
- 支持 NVIDIA API 等大模型提供商
- 浮动控制台支持滚动配置窗口
- 实时识别内容显示

## License

MIT License
