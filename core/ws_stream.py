import json
import logging
import time
import requests
import websocket
from config.settings import Config
from core.analyzer import analyze_and_store

# Polymarket 订单簿 WebSocket 地址
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class PolymarketStreamer:
    def __init__(self):
        self.market_map = {}  # 用于映射 Token ID 和对应的市场信息
        self.current_prices = {}  # 缓存在内存中的实时价格

    def build_watchlist(self):
        """拉取活跃市场，并提取 Yes 和 No 对应的 Token ID"""
        logging.info("正在通过 REST API 构建监控清单...")
        try:
            params = {"active": "true", "closed": "false", "limit": 20}  # 先监控 20 个热门市场测试
            response = requests.get(Config.API_URL, params=params, timeout=10)
            response.raise_for_status()
            markets = response.json()

            tokens_to_subscribe = []

            for m in markets:
                # Polymarket 的每个选项 (Yes/No) 在底层都是一个独立的 Token
                if 'tokens' in m and len(m['tokens']) == 2:
                    yes_token = m['tokens'][0]['token_id']
                    no_token = m['tokens'][1]['token_id']

                    # 建立反向映射，方便收到 WS 消息时知道是哪个市场
                    self.market_map[yes_token] = {'market_id': m['id'], 'question': m['question'], 'type': 'Yes', 'pair_token': no_token}
                    self.market_map[no_token] = {'market_id': m['id'], 'question': m['question'], 'type': 'No', 'pair_token': yes_token}

                    tokens_to_subscribe.extend([yes_token, no_token])

                    # 初始化内存价格
                    self.current_prices[yes_token] = float(m['outcomePrices'][0])
                    self.current_prices[no_token] = float(m['outcomePrices'][1])

            logging.info(f"监控清单构建完成，共监控 {len(markets)} 个市场，{len(tokens_to_subscribe)} 个 Token。")
            return tokens_to_subscribe
        except Exception as e:
            logging.error(f"构建清单失败: {e}")
            return []

    def on_message(self, ws, message):
        """接收到 WebSocket 实时价格推送时的处理逻辑"""
        try:
            data = json.loads(message)

            # 过滤出订单簿更新事件
            if isinstance(data, list) and len(data) > 0 and 'asset_id' in data[0]:
                for tick in data:
                    token_id = tick['asset_id']
                    # 提取最佳买价 (Best Bid)
                    if 'bids' in tick and len(tick['bids']) > 0:
                        best_bid = float(tick['bids'][0]['price'])

                        if token_id in self.market_map:
                            # 1. 更新内存中的最新价格
                            self.current_prices[token_id] = best_bid

                            # 2. 获取对应的配对 Token 价格
                            pair_token = self.market_map[token_id]['pair_token']
                            pair_price = self.current_prices.get(pair_token, 0)

                            # 3. 实时计算套利空间 (Yes + No < 0.98)
                            total_price = best_bid + pair_price
                            if 0 < total_price <= 0.98:
                                market_info = self.market_map[token_id]
                                logging.info(f"⚡ [极速捕获] 套利空间! 总价: {total_price:.4f} | {market_info['question']}")

                                # 将数据包装成之前 analyzer 需要的格式存入数据库
                                mock_market_data = [{
                                    'id': market_info['market_id'],
                                    'question': market_info['question'],
                                    'outcomePrices': [best_bid, pair_price] if market_info['type'] == 'Yes' else [pair_price, best_bid]
                                }]
                                analyze_and_store(mock_market_data)

        except Exception as e:
            pass  # 忽略非价格类的心跳包

    def on_error(self, ws, error):
        logging.error(f"WebSocket 错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logging.warning("WebSocket 连接已断开，准备重连...")

    def on_open(self, ws):
        logging.info("🔗 WebSocket 连接成功！正在发送订阅指令...")
        tokens = self.build_watchlist()
        if tokens:
            # Polymarket CLOB 订阅格式
            subscribe_msg = {
                "assets": tokens,
                "type": "market"
            }
            ws.send(json.dumps(subscribe_msg))

    def start(self):
        # 使用 websocket-client 的长连接应用
        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        # 启动事件循环，断开自动重连
        ws.run_forever(ping_interval=30, ping_timeout=10)
