# 黄金价格监控系统

一个基于Python的黄金价格实时监控系统，支持飞书和邮件通知提醒。

## 功能特点

- **实时价格监控**：自动获取黄金最新价格
- **多渠道通知**：支持飞书消息和邮件通知
- **目标价格提醒**：可设置上涨/下跌目标价格，达到目标时自动提醒
- **价格变化检测**：检测价格整数变化（±10点）并触发提醒
- **连续涨跌趋势检测**：检测连续上涨/下跌趋势
- **定时报告**：每10分钟定时报告当前价格
- **休眠模式**：自动识别非交易时间并暂停监控
- **飞书消息交互**：支持通过飞书消息查询当前价格

## 技术栈

- **Python 3.10+**
- **requests** - HTTP请求库
- **PyYAML** - YAML配置文件解析
- **lark-oapi** - 飞书API SDK
- **smtplib** - 邮件发送

## 安装步骤

```bash
# 克隆项目
git clone <repository-url>
cd gold

# 安装依赖
pip install -r requirements.txt
```

## 配置说明

在 `file.yaml` 文件中配置相关参数：

```yaml
# API Token（用于获取黄金价格）
token: your_api_token

# 飞书配置
feishu:
  app_id: your_feishu_app_id
  app_secret: your_feishu_app_secret
  receive_id: your_feishu_receive_id

# 邮箱配置
email:
  host: smtp.qq.com
  user: your_email@qq.com
  pass: your_email_password
  sender: your_email@qq.com
  receivers:
    - receiver1@example.com
    - receiver2@example.com
```

## 使用方法

### 启动监控

```bash
python gold_monitor_feishu.py
```

### 飞书消息交互

在飞书聊天中发送以下消息：
- `价格` - 查询当前黄金价格
- `帮助` - 获取帮助信息

## 项目结构

```
gold/
├── gold_monitor_feishu.py   # 主程序文件
├── file.yaml                 # 配置文件
├── requirements.txt          # 依赖列表
├── logs/                     # 日志目录
│   └── gold_monitor.log      # 日志文件
└── README.md                 # 项目说明文档
```

## 监控规则

### 目标价格设置

系统预设以下目标价格：

**上涨目标**：4950, 4980, 5000, 5030, 5080, 5100, 5200

**下跌目标**：4900, 4880, 4800, 4720, 4700, 4650, 4600, 4500

### 触发条件

1. **目标价格触发**：价格达到预设目标时发送提醒
2. **价格变化触发**：价格变化超过10点整数时发送提醒
3. **连续涨跌触发**：检测到连续涨跌超过阈值时发送提醒
4. **定时触发**：每10分钟发送一次价格报告

### 休眠时间

系统会在以下时间段自动暂停监控：
- 周六凌晨2点后
- 周日全天
- 周一凌晨2点前
- 工作日凌晨2点至8点

## 日志记录

系统会自动记录运行日志到 `logs/gold_monitor.log` 文件中，包含：
- 价格获取记录
- 提醒发送记录
- 异常错误信息

## License

MIT License

## 注意事项

1. 请确保配置文件中的API Token、飞书配置和邮箱配置正确
2. 建议使用虚拟环境运行项目
3. 定期检查日志文件，确保系统正常运行
