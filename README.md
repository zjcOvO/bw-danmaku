# bw弹幕姬

基于 python 的 Windows 端弹幕应用

从 Onebot 协议 WebSocket 服务器获取群消息，并结合 B站直播弹幕，通过 tkinter 全屏透明窗口显示。

## 功能特性

- **双数据源支持**：同时接收 Onebot 群消息和 B站直播弹幕
- **全屏透明弹幕**：使用 tkinter 实现全屏透明弹幕显示窗口
- **灵活配置**：支持 YAML 配置文件

## 安装说明

### 环境要求

- Python 环境

### 安装步骤

1. 克隆项目并进入目录：
```bash
git clone <repository-url>
cd py_danmaku
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv .venv
.venv\Scripts\activate
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
  group_id: ...                     # 指定获取弹幕的群聊
  access_token: ...                 # 访问令牌（可选）
```

### B站 配置

```yaml
bilibili:
  room_id: 0       # 直播间房间号
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

### 查看帮助

```bash
python main.py --help
```

## 技术架构

采用生产者-消费者模式：
- **生产者**：Onebot 消息客户端和 B站弹幕客户端
- **消费者**：tkinter 弹幕显示窗口
- **数据传输**：线程安全队列

## License

MIT License
