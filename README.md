# OCPP 1.6 CSMS

基于 Python 的 OCPP 1.6 充电桩中央管理系统，支持 WebSocket 实时通信、Web 管理界面、远程命令下发。

## 快速启动

```powershell
pip install -r requirements.txt
python main.py
```

- Web UI: http://localhost:8000
- 充电桩连接: `ws://{服务器IP}:9000/{充电桩ID}`

## 主要功能

- 充电桩注册、心跳、授权、事务管理（Start/Stop Transaction）
- 实时 OCPP 报文日志（分页、主题切换、导出）
- Monta 风格 Web 管理界面
- 右侧命令栏：Remote Start/Stop、Reset、Unlock、固件升级、充电曲线、预约等
- Handler 配置：自定义每种 OCPP 消息的响应状态和延迟/Drop 行为
- 充电桩模拟器（`tests/test_simulator.py`）
- 自动更新检测（从 GitHub Release）

## 打包

```powershell
build.bat
```

## 截图

> 待补充

## License

MIT
