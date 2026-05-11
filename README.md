# py_danmaku

桌面弹幕应用，从 Onebot 协议 WebSocket 服务器获取群消息，并结合 B站直播弹幕，通过 tkinter 全屏透明窗口显示。

## 功能特性

- **双数据源支持**：同时接收 Onebot 群消息和 B站直播弹幕
- **全屏透明弹幕**：使用 tkinter 实现全屏透明弹幕显示窗口
- **生产者-消费者模式**：使用线程安全队列进行数据传递
- **灵活配置**：支持 YAML 配置文件
- **命令行参数**：支持自定义配置文件和调试模式

## 项目结构

```
py_danmaku/
├── main.py                     # 应用入口
├── config.yaml                 # 配置文件
├── requirements.txt            # Python 依赖
├── py_danmaku/
│   ├── __init__.py
│   ├── config.py               # 配置管理类
│   ├── controller.py           # 主控制器
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── onebot_client.py    # Onebot 客户端
│   │   └── bilibili_client.py  # B站弹幕客户端
│   ├── display/
│   │   ├── __init__.py
│   │   └── danmaku_window.py   # tkinter 弹幕窗口
│   └── utils/
│       ├── __init__.py
│       └── logger.py           # 日志工具
└── tests/
    ├── __init__.py
    ├── test_onebot_client.py
    ├── test_bilibili_client.py
    └── test_danmaku_window.py
```

## 安装说明

### 环境要求

- Python 3.8+

### 安装步骤

1. 克隆项目并进入目录：
```bash
git clone <repository-url>
cd py_danmaku
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

## 配置说明

配置文件 `config.yaml` 包含以下部分：

### Onebot 配置

```yaml
onebot:
  ws_url: "ws://127.0.0.1:8080/ws"  # WebSocket 服务器地址
  access_token: ""                   # 访问令牌（可选）
```

### B站 配置

```yaml
bilibili:
  room_id: 0      # 直播间房间号
  cookie: ...      # B站 Cookie（可选）
```

### 显示配置

```yaml
display:
  width: 1920        # 窗口宽度
  height: 1080       # 窗口高度
  font_size: 24      # 字体大小
  font_color: "#FFFFFF"   # 字体颜色
  bg_color: "#000000"     # 背景颜色
  opacity: 0.7       # 透明度 (0-1)
  speed: 5           # 弹幕速度
```

## 使用方法

### 基本用法

```bash
python main.py
```

### 指定配置文件

```bash
python main.py --config my_config.yaml
# 或
python main.py -c my_config.yaml
```

### 启用调试模式

```bash
python main.py --debug
# 或
python main.py -d
```

### 组合使用

```bash
python main.py --config custom.yaml --debug
```

### 查看帮助

```bash
python main.py --help
```

## 运行测试

```bash
pytest tests/
```

## 依赖

- aiohttp >= 3.8.0
- websocket-client >= 1.3.0
- websockets >= 10.0
- bilibili-api >= 9.0.0
- nonebot2 >= 2.0.0
- nonebot-plugin-apscheduler >= 0.2.0
- pyyaml >= 6.0
- python-dotenv >= 0.19.0

## 技术架构

采用生产者-消费者模式：
- **生产者**：Onebot 消息客户端和 B站弹幕客户端
- **消费者**：tkinter 弹幕显示窗口
- **数据传输**：线程安全队列

## License

MIT License
