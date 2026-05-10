import asyncio
import json
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
import os
import logging
import yaml
import sys
import lark_oapi as lark
from lark_oapi.api.im.v1 import *

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# API配置 - 从YAML文件动态读取
def load_config():
    """加载YAML配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'file.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_config(config_data: dict):
    """保存配置到YAML文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'file.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)
    # 注意：这里不能使用 log_and_print，因为它可能还未定义
    print(f"配置已保存到 {config_path}")


# 加载配置
config = load_config()
token = config.get('token', '')

# 飞书配置
feishu_config = config.get('feishu', {})
FEISHU_APP_ID = feishu_config.get('app_id', '')
FEISHU_APP_SECRET = feishu_config.get('app_secret', '')
FEISHU_RECEIVE_ID = feishu_config.get('receive_id', '')


headers = {
    'Content-Type': 'application/json'
}


def setup_logger() -> logging.Logger:
    """初始化日志记录器"""
    logger = logging.getLogger("gold_monitor")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "gold_monitor.log")

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()


def log_and_print(message: str, level: str = "info"):
    """同时打印并写入日志文件"""
    print(message)
    if level == "error":
        logger.error(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "debug":
        logger.debug(message)
    else:
        logger.info(message)


# 邮箱功能
import random
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 邮箱功能
email_config = config.get('email', {})
MAIL_CONFIGS = [
    {
        'host': email_config.get('host', 'smtp.qq.com'),
        'user': email_config.get('user', ''),
        'pass': email_config.get('pass', ''),
        'sender': email_config.get('sender', '')
    }
]
receivers_list_config = email_config.get('receivers', [])


def send_email(subject: str, from_name: str, text: str, try_times: int = 6):
    message = MIMEMultipart()
    message_text = MIMEText(text, 'plain', 'utf-8')
    message.attach(message_text)
    message['Subject'] = subject

    # 随机选择一个邮箱配置
    mail_config = random.choice(MAIL_CONFIGS)
    sender = mail_config['sender']
    message['From'] = f'{sender}'
    message['To'] = ','.join(receivers_list_config)
    log_and_print(str(message))

    for _ in range(try_times):
        try:
            # 使用SMTP_SSL并指定465端口
            smtpObj = smtplib.SMTP_SSL(mail_config['host'], 465)
            smtpObj.login(mail_config['user'], mail_config['pass'])
            smtpObj.sendmail(sender, receivers_list_config, message.as_string())
            smtpObj.quit()
            log_and_print('send email success')
            break
        except smtplib.SMTPException as e:
            log_and_print(f'send email error: {e}', level='error')


class GoldPriceMonitor:
    def __init__(self):
        self.current_price = None
        self.last_price = 0.0
        self.last_print_time = None
        self.last_print_price = None
        self.last_min_time = time.time()
        self._feishu_client = None

        # 目标价格列表：3个上涨目标，3个下跌目标
        self.target_prices = {
            'up': [4950, 4980, 5000, 5030, 5080, 5100, 5200 ],  # 上涨目标价格
            'down': [4900,4880,4800, 4720, 4700, 4650, 4600, 4500]  # 下跌目标价格
        }

        # 已触发的目标价格（避免重复打印）
        self.triggered_targets = set()

        # 连续涨跌检测相关变量
        self.last_trend_check_time = time.time()
        self.trend_prices = []  # 存储5分钟内的价格数据
        self.max_trend_prices = 30  # 最多存储5个价格点（5分钟，每分钟一个） # 30s 一个
        self.trend_thresholds = [10, 20, 30, 40, 50]  # 连续涨跌阈值：10点和20点

        # 小米通知管理器
        # self.xiaomi_notifier = XiaomiNotificationManager()

    def _get_feishu_client(self):
        """获取飞书客户端单例"""
        if self._feishu_client is None:
            self._feishu_client = lark.Client.builder() \
                .app_id(FEISHU_APP_ID) \
                .app_secret(FEISHU_APP_SECRET) \
                .log_level(lark.LogLevel.INFO) \
                .build()
            log_and_print("飞书客户端初始化完成")
        return self._feishu_client

    def send_feishu_message(self, content: str, reason: str = "") -> bool:
        """
        发送飞书消息

        Args:
            content: 消息内容
            reason: 触发原因

        Returns:
            bool: 发送是否成功
        """
        try:
            # 使用类内单例客户端
            client = self._get_feishu_client()

            # 构造消息内容
            message_content = {
                "text": f"【黄金价格提醒】\n触发原因: {reason}\n{content}"
            }

            # 构造请求对象
            request = CreateMessageRequest.builder() \
                .receive_id_type("open_id") \
                .request_body(CreateMessageRequestBody.builder()
                              .receive_id(FEISHU_RECEIVE_ID)
                              .msg_type("text")
                              .content(json.dumps(message_content, ensure_ascii=False))
                              .build()) \
                .build()

            # 发起请求
            response = client.im.v1.message.create(request)

            # 处理响应
            if response.success():
                log_and_print(f"飞书消息发送成功: {reason}")
                return True
            else:
                log_and_print(
                    f"飞书消息发送失败, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}",
                    level='error'
                )
                return False

        except Exception as e:
            log_and_print(f"飞书消息发送异常: {e}", level='error')
            return False

    def get_gold_price(self) -> Optional[Dict]:
        """
        获取黄金最新价格
        """
        base_url = "https://quote.alltick.io/quote-b-api"
        url = f"{base_url}/trade-tick"

        query_data = {
            "trace": "gold_monitor_tick",
            "data": {
                "symbol_list": [{"code": "GOLD"}]
            }
        }

        query_json = json.dumps(query_data)
        params = {
            "token": token,
            "query": query_json
        }

        try:
            response = requests.get(url=url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()
                if data.get('ret') == 200 and data.get('data', {}).get('tick_list'):
                    tick_data = data['data']['tick_list'][0]
                    return {
                        'price': float(tick_data['price']),
                        'tick_time': tick_data['tick_time'],
                        'volume': tick_data.get('volume', '0'),
                        'trade_direction': tick_data.get('trade_direction', 0)
                    }
            else:
                log_and_print(f"API请求失败，状态码: {response.status_code}", level='warning')
                if response.status_code in [401]:
                    time.sleep(36000)
                elif response.status_code in [605]:
                    time.sleep(600)
                return None

        except requests.exceptions.RequestException as e:
            log_and_print(f"请求异常: {e}", level='error')
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            log_and_print(f"数据解析异常: {e}", level='error')
            return None

    def check_price_change(self, current_price: float) -> bool:
        """
        检查价格是否发生整数变化（±10）
        """
        if self.last_price is None:
            self.last_price = current_price
            return False

        # 计算整数价格
        current_int = int(current_price)
        last_int = int(self.last_price)

        # 检查是否发生整数变化
        if abs(current_int - last_int) >= 10:
            self.last_price = current_price
            return True

        return False

    def check_target_prices(self, current_price: float) -> Optional[str]:
        """
        检查是否达到目标价格
        """
        current_int = int(current_price)

        # 检查上涨目标
        for target in self.target_prices['up']:
            if current_int >= target and target not in self.triggered_targets:
                self.triggered_targets.add(target)
                return f"上涨目标 {target} 已达成"

        # 检查下跌目标
        for target in self.target_prices['down']:
            if current_int <= target and target not in self.triggered_targets:
                self.triggered_targets.add(target)
                return f"下跌目标 {target} 已达成"

        return None

    def get_direction_text(self, trade_direction: int) -> str:
        """
        获取交易方向文本
        """
        if trade_direction == 1:
            return "上涨"
        elif trade_direction == -1:
            return "下跌"
        else:
            return "平盘"

    def format_tick_time(self, tick_time: str) -> str:
        """
        格式化时间戳
        """
        try:
            # 将毫秒时间戳转换为秒
            timestamp = int(tick_time) / 1000
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return tick_time

    async def print_price_info(self, price_data: Dict, reason: str, debug: bool = False):
        """
        打印价格信息

        Args:
            price_data: 价格数据字典
            reason: 触发原因
            debug: 是否为调试模式，调试模式下不更新上次打印时间
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_tick_time = self.format_tick_time(price_data['tick_time'])

        log_and_print(f"\n{'=' * 60}")
        log_and_print(f"触发原因: {reason}")
        log_and_print(f"当前时间: {current_time}")
        log_and_print(f"数据时间: {formatted_tick_time}")
        log_and_print(f"当前价格: {price_data['price']}")

        if self.last_print_time and self.last_print_price:
            log_and_print(f"上次打印时间: {self.last_print_time}")
            log_and_print(f"上次打印价格: {self.last_print_price}")
            log_and_print(f"当前价格: {price_data['price']}")

        feishu_content = f"""当前时间: {current_time}\n数据时间: {formatted_tick_time}\n当前价格: {price_data['price']}\n上次打印时间: {self.last_print_time}\n上次打印价格: {self.last_print_price}\n"""
        self.send_feishu_message(feishu_content.strip(), reason)

        # 更新上次打印信息
        if not debug:
            self.last_print_time = current_time
            self.last_print_price = price_data['price']
            subject = f'黄金价格提醒 - {reason},当前价格{price_data["price"]}'
            text = f"""
            黄金价格监控提醒
            触发原因: {reason}
            当前时间: {current_time}
            数据时间: {formatted_tick_time}
            当前价格: {price_data['price']}
            已触发目标: {list(self.triggered_targets)}

            上次打印时间: {self.last_print_time}
            上次打印价格: {self.last_print_price}  当前价格: {price_data['price']}
            """
            # 发送邮件
            send_email(subject=subject,
                       text=text,
                       from_name='huangjin',
                       )


        log_and_print(f"{'=' * 60}\n")

    def check_min_timer(self, interval_seconds: int = 600) -> bool:
        """
        检查是否到了指定时间间隔的定时打印时间

        Args:
            interval_seconds: 时间间隔（秒），默认600秒（10分钟）
        """
        current_time = time.time()
        if current_time - self.last_min_time >= interval_seconds:
            self.last_min_time = current_time
            return True
        return False

    def add_price_to_trend(self, price: float):
        """
        将价格添加到趋势检测队列

        Args:
            price: 当前价格
        """
        current_time = time.time()

        # 添加当前价格和时间戳
        self.trend_prices.append({
            'price': price,
            'timestamp': current_time
        })

        # 保持队列大小不超过max_trend_prices
        if len(self.trend_prices) > self.max_trend_prices:
            self.trend_prices.pop(0)

    def check_consecutive_trend(self) -> Optional[str]:
        """
        检查连续涨跌趋势

        Returns:
            如果检测到连续涨跌，返回描述信息；否则返回None
        """
        if len(self.trend_prices) < 2:
            return None

        # 计算价格变化
        first_price = self.trend_prices[0]['price']
        last_price = self.trend_prices[-1]['price']
        total_change = last_price - first_price

        # 判断是连续上涨还是连续下跌
        is_consecutive_up = all(
            self.trend_prices[i]['price'] <= self.trend_prices[i + 1]['price']
            for i in range(len(self.trend_prices) - 1)
        )
        is_consecutive_down = all(
            self.trend_prices[i]['price'] >= self.trend_prices[i + 1]['price']
            for i in range(len(self.trend_prices) - 1)
        )

        # 检查是否达到阈值
        for threshold in self.trend_thresholds:
            if is_consecutive_up and total_change >= threshold:
                return f"连续上涨{len(self.trend_prices)}次，累计上涨{total_change:.2f}点（超过{threshold}点阈值）"
            elif is_consecutive_down and abs(total_change) >= threshold:
                return f"连续下跌{len(self.trend_prices)}次，累计下跌{abs(total_change):.2f}点（超过{threshold}点阈值）"

        return None

    def should_check_trend(self, trend_check_interval) -> bool:
        """
        检查是否应该进行趋势检测（每5分钟检查一次）

        Returns:
            是否应该检查趋势
        """
        current_time = time.time()
        if current_time - self.last_trend_check_time >= trend_check_interval:
            self.last_trend_check_time = current_time
            return True
        return False

    async def run_monitor_async(self):
        """
        运行监控主循环（异步版本）
        """
        log_and_print("黄金价格监控系统启动...")
        log_and_print(f"上涨目标价格: {self.target_prices['up']}")
        log_and_print(f"下跌目标价格: {self.target_prices['down']}")

        last_token_update = time.time()
        token_update_interval = 1800  # 30分钟

        log_and_print("监控开始...\n")
        # 创建价格显示窗口
        while True:
            now = datetime.now()
            # 检查是否为周日 或者 周六且凌晨2点之后
            is_monday_before_2am = (now.weekday() == 0) and (now.hour <= 2)
            is_weekday_off_hours = (0 <= now.weekday() <= 4) and (2 <= now.hour < 8)
            is_saturday_after_2am = (now.weekday() == 5) and (now.hour >= 2)
            is_sunday_all_day = (now.weekday() == 6)

            if is_monday_before_2am or is_weekday_off_hours or is_saturday_after_2am or is_sunday_all_day:
                current_time = now.strftime("%Y-%m-%d %H:%M:%S")
                log_and_print(f"[{current_time}] 处于休眠时间（周六凌晨2点后和周日全天），暂停监控...")
                # 等待1小时后再次检查
                await asyncio.sleep(3600)
                continue

            try:
                # 定期更新 token
                current_time = time.time()
                if current_time - last_token_update >= token_update_interval:
                    last_token_update = current_time

                # 等待90秒后继续监控
                await asyncio.sleep(100)
                # 获取当前价格
                price_data = self.get_gold_price()
                if price_data is None:
                    log_and_print("获取价格失败，等待60秒后重试...", level='warning')
                    await asyncio.sleep(60)
                    continue

                await self.print_price_info(price_data, "打印调试", debug=True)
                current_price = price_data['price']

                # 将价格添加到趋势检测队列
                self.add_price_to_trend(current_price)

                # 检查连续涨跌趋势（每5分钟检查一次）
                if self.should_check_trend(100):
                    trend_reason = self.check_consecutive_trend()
                    if trend_reason:
                        await self.print_price_info(price_data, f"1 级连续涨跌检测: {trend_reason}")
                        continue

                # 检查连续涨跌趋势（每5分钟检查一次）
                if self.should_check_trend(300):
                    trend_reason = self.check_consecutive_trend()
                    if trend_reason:
                        await self.print_price_info(price_data, f"2 级连续涨跌检测: {trend_reason}")
                        continue

                # 检查10分钟定时打印
                if self.check_min_timer(interval_seconds=600):
                    await self.print_price_info(price_data, "10分钟定时打印")
                    continue

                # 检查目标价格
                target_reason = self.check_target_prices(current_price)
                if target_reason:
                    await self.print_price_info(price_data, target_reason)
                    continue

                # 检查价格变化（±10整数变化）
                direction = "上涨" if current_price > self.last_price else "下跌"
                if self.check_price_change(current_price):
                    await self.print_price_info(price_data, f"价格{direction}超过整数变化")
                    continue


            except KeyboardInterrupt:
                log_and_print("\n监控系统已停止", level='warning')
                break
            except Exception as e:
                log_and_print(f"监控异常: {e}", level='error')
                await asyncio.sleep(5)

    def run_monitor(self):
        """
        运行监控主循环（同步包装器）
        """
        asyncio.run(self.run_monitor_async())


def start_event_listener(monitor):
    """
    启动事件监听器，处理飞书消息
    """
    try:
        import lark_oapi as lark
        from lark_oapi.ws import Client
        
        # 创建事件处理器类
        class MessageHandler:
            def __init__(self, monitor):
                self.monitor = monitor
            
            def do_without_validation(self, data):
                """处理收到的消息"""
                try:
                    log_and_print(f"收到原始消息: {data}")
                    
                    # 处理字节类型消息
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    
                    # 处理字符串类型消息
                    if isinstance(data, str):
                        data = json.loads(data)
                    
                    # 解析消息内容
                    if isinstance(data, dict):
                        # 处理JSON格式消息
                        event = data.get("event", {})
                        message = event.get("message", {})
                        content = message.get("content", "{}")
                        content_dict = json.loads(content)
                        text = content_dict.get("text", "")
                        sender = event.get("sender", {})
                        sender_id = sender.get("sender_id", {})
                        open_id = sender_id.get("open_id", "")
                    else:
                        # 处理对象类型消息
                        try:
                            message = data.message
                            content = message.content
                            content_dict = json.loads(content)
                            text = content_dict.get("text", "")
                            sender = data.sender
                            open_id = sender.sender_id.open_id
                        except Exception as e:
                            log_and_print(f"处理对象类型消息失败: {e}", level='error')
                            # 尝试作为字典处理
                            if hasattr(data, '__dict__'):
                                data_dict = data.__dict__
                                event = data_dict.get("event", {})
                                message = event.get("message", {})
                                content = message.get("content", "{}")
                                content_dict = json.loads(content)
                                text = content_dict.get("text", "")
                                sender = event.get("sender", {})
                                sender_id = sender.get("sender_id", {})
                                open_id = sender_id.get("open_id", "")
                            else:
                                log_and_print("无法处理消息格式", level='error')
                                return
                    
                    log_and_print(f"收到消息: {text} 来自: {open_id}")
                    
                    # 根据消息内容响应
                    if "价格" in text:
                        # 获取当前黄金价格
                        price_data = self.monitor.get_gold_price()
                        if price_data:
                            current_price = price_data['price']
                            response_text = f"当前黄金价格: {current_price}"
                        else:
                            response_text = "获取价格失败，请稍后重试"
                    elif "帮助" in text:
                        response_text = "我是黄金价格监控机器人，您可以回复'价格'查询当前黄金价格。"
                    else:
                        response_text = "您好！我是黄金价格监控机器人，您可以回复'价格'查询当前黄金价格。"
                    
                    # 发送响应消息
                    self.monitor.send_feishu_message(response_text, "用户消息回复")
                except Exception as e:
                    log_and_print(f"处理消息异常: {e}", level='error')
        
        # 创建消息处理器实例
        handler = MessageHandler(monitor)
        
        # 直接创建WS客户端，传递消息处理对象
        client = Client(
            app_id=FEISHU_APP_ID,
            app_secret=FEISHU_APP_SECRET,
            event_handler=handler
        )
        
        log_and_print("事件监听器启动成功")
        client.start()
        
    except Exception as e:
        log_and_print(f"启动事件监听器失败: {e}", level='error')
        # 尝试使用最基础的方式
        try:
            import lark_oapi.ws
            log_and_print(f"ws模块内容: {dir(lark_oapi.ws)}")
            log_and_print(f"ws.Client 类: {dir(lark_oapi.ws.Client)}")
        except Exception as e2:
            log_and_print(f"检查ws模块失败: {e2}", level='error')

def main():
    """
    主函数
    """
    # 确保有有效的 token
    #asyncio.run(ensure_api_token())

    # 启动监控
    monitor = GoldPriceMonitor()
    
    # 启动事件监听器（长连接）
    import threading
    listener_thread = threading.Thread(target=start_event_listener, args=(monitor,), daemon=True)
    listener_thread.start()
    
    try:
        monitor.run_monitor()
    finally:
        # 清理资源
        pass


if __name__ == "__main__":
    main()
