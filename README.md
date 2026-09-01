# bw弹幕姬

基于 python 的 Windows 端弹幕应用

从 Onebot 协议 WebSocket 服务器 / QQ 官方机器人 WebSocket 获取群消息，并结合 B站直播弹幕，通过 tkinter 全屏透明窗口显示。

## 功能特性

- **多数据源支持**：同时接收 Onebot 群消息、QQ 官方机器人群消息和 B站直播弹幕
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

### QQ 官方机器人配置

通过 [QQ 开放平台](https://bot.q.qq.com/) 的官方机器人（API v2）接收群消息。
先在 [QQ 开放平台控制台](https://q.qq.com/) 创建机器人并获取 AppID / AppSecret，
然后把机器人拉入目标群。

```yaml
qqbot:
  appid: "your AppId"               # 机器人的 AppID
  appsecret: "your AppSecret"       # 机器人的 AppSecret
  group_id: 123456789               # 群号（仅供参考）
  # group_openid: "your group_openid"  # 可选：只接收指定群（QQ 官方 API 用 openid 标识群）
  fetch_nickname: true              # 是否拉取群成员昵称（需要额外 API 调用，带缓存）
```

说明：
- 机器人会通过官方 WebSocket 网关接收 `GROUP_AT_MESSAGE_CREATE`（群@机器人消息，
  默认可用）和 `GROUP_MESSAGE_CREATE`（全量群消息，需申请权限）两类事件。
- `group_openid` 是 QQ 官方 API 中标识群聊的 openid，可在机器人收到的消息日志中查看，
  或通过「获取用户可访问的群列表」接口获取。不填则接收所有已授权群的消息。
- 群消息事件中不直接携带成员昵称，若需要展示昵称请开启 `fetch_nickname`
  （首次遇到某成员时会调用成员信息接口，之后有缓存）。

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
- **生产者**：Onebot 消息客户端、QQ 官方机器人客户端和 B站弹幕客户端
- **消费者**：tkinter 弹幕显示窗口
- **数据传输**：线程安全队列

## License

MIT License
