# OCPP 1.6 CSMS 使用说明

## 简介

基于 Python 的 OCPP 1.6 中央管理系统（CSMS），支持充电桩 WebSocket 接入、实时报文监控、远程命令下发。

github项目地址：<a>[littlejazzcat/OCPP1.6_Server: An OCPP1.6 server like OCPP Toolkit](https://github.com/littlejazzcat/OCPP1.6_Server)</a>
## 启动

### 源码启动

```powershell
pip install -r requirements.txt
python main.py
```

### 打包版启动

双击 `dist/ocppv16_server/ocpp_server.exe`。

## 访问

| 地址 | 用途 |
|------|------|
| `http://localhost:8000` | Web 管理界面 |
| `http://localhost:8000/docs` | API 文档（Swagger） |
| `ws://localhost:9000/{id}` | 充电桩连接地址 |

## 充电桩连接

充电桩端配置 OCPP 端点地址为 `ws://{服务器IP}:9000/{充电桩ID}`。例如本机测试：

```
ws://localhost:9000/CP_001
```

连接后充电桩发送 BootNotification 即可自动注册。

## 主要功能

### 仪表盘

- 充电桩在线/离线统计
- 实时 OCPP 报文日志（支持分页、导出、清除、黑白主题切换）
- 最近交易记录

### 充电桩详情

点击充电桩进入详情页，四个标签页：

**Logs** — 实时报文监控。每页条数可调（10/25/40/50/100），支持暂停、导出、清除、黑白主题。

**Handlers** — 消息处理器配置。可设置每种消息的响应状态、Response behavior（Normal / Delay / Drop）、Certificate status 等。点 Apply 后实时生效。

**Configuration** — 充电桩基本信息和连接器状态。

**Testing** — 测试工具（预留）。

### 右侧命令栏

向充电桩下发 OCPP 命令，共 7 个分组 19 个命令：

| 分组 | 命令 |
|------|------|
| Transaction Control | Remote Start / Remote Stop |
| Device Control | Reset (Soft/Hard) / Unlock Connector |
| Configuration | Change / Get Configuration / Clear Cache |
| Firmware Management | Update Firmware / Get Diagnostics |
| Local Auth List | Get Local List Version / Send Local List |
| Smart Charging | Set / Clear Charging Profile / Get Composite Schedule |
| Remote Trigger | Trigger Message |
| Reservation | Reserve Now / Cancel Reservation |

点击命令弹出参数表单，点 Send 发送。桩回复后结果追加到报文日志并弹窗提示。

### 标签管理

管理 RFID 卡 / 用户 ID 授权白名单。未知标签首次刷卡自动注册。

### 交易记录

查看所有充电事务：开始/结束时间、电量、停止原因等。

## 模拟测试

```powershell
# 交互式（终端命令驱动）
python tests/test_simulator.py

# 自动化回归测试
python tests/test_simulator.py --auto

# 批量自动化（5 次）
python tests/test_simulator.py --auto --count 5
```

主要命令：`start` 开始充电、`stop` 停止、`status` 状态、`meter` 上报电表、`fault` 模拟故障、`quit` 退出。

## 重新打包

```powershell
build.bat
```

输出在 `dist/ocppv16_server/`。
