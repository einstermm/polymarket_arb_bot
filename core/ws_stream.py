import json
import logging
import requests
import websocket
from config.settings import Config
from core.analyzer import analyze_and_store
from core.trader import PolymarketTrader  # <-- 新增：导入交易模块

# Polymarket 订单簿 WebSocket 地址
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class PolymarketStreamer:
    def __init__(self):
        self.market_map = {}  # 用于映射 Token ID 和对应的市场信息
        self.current_prices = {}  # 缓存在内存中的实时价格
        self.trader = PolymarketTrader()  # <-- 新增：初始化自动交易员

    def build_watchlist(self):
        """拉取活跃市场，并提取 Yes 和 No 对应的 Token ID"""
        logging.info("正在通过 REST API 构建监控清单...")
        try:
            params = {"active": "true", "closed": "false", "limit": 20}
            response = requests.get(Config.API_URL, params=params, timeout=10)
            response.raise_for_status()
            markets = response.json()

            tokens_to_subscribe = []

            for m in markets:
                try:
                    # 1. 提取并解析 Token IDs
                    raw_tokens = m.get('clobTokenIds') or m.get('tokens')
                    if not raw_tokens:
                        continue

                    # 如果 API 返回的是字符串，则将其解析为列表
                    if isinstance(raw_tokens, str):
                        token_list = json.loads(raw_tokens)
                    else:
                        token_list = raw_tokens

                    # 2. 提取并解析 价格 (Prices)
                    raw_prices = m.get('outcomePrices')
                    if isinstance(raw_prices, str):
                        price_list = json.loads(raw_prices)
                    else:
                        price_list = raw_prices or ['0', '0']

                    # 确保解析后是一个有且仅有 2 个选项的二元市场
                    if token_list and len(token_list) == 2:

                        # 兼容 Polymarket 两种不同的数据结构
                        if isinstance(token_list[0], dict):
                            yes_token = token_list[0]['token_id']
                            no_token = token_list[1]['token_id']
                        else:
                            yes_token = str(token_list[0])
                            no_token = str(token_list[1])

                        # 建立反向映射
                        self.market_map[yes_token] = {'market_id': m['id'], 'question': m['question'], 'type': 'Yes', 'pair_token': no_token}
                        self.market_map[no_token] = {'market_id': m['id'], 'question': m['question'], 'type': 'No', 'pair_token': yes_token}

                        tokens_to_subscribe.extend([yes_token, no_token])

                        # 初始化内存价格
                        self.current_prices[yes_token] = {'price': float(price_list[0]), 'size': 0}
                        self.current_prices[no_token] = {'price': float(price_list[1]), 'size': 0}

                except Exception as inner_e:
                    logging.warning(f"解析单个市场数据出错，跳过该市场。ID: {m.get('id')}, 错误: {inner_e}")
                    continue

            logging.info(f"监控清单构建完成，共监控 {len(markets)} 个市场，成功提取 {len(tokens_to_subscribe)} 个 Token。")
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

                    # 提取最佳买价 (Best Bid) 和对应的可成交量 (Size)
                    if 'bids' in tick and len(tick['bids']) > 0:
                        best_bid = float(tick['bids'][0]['price'])
                        best_size = float(tick['bids'][0]['size'])

                        if token_id in self.market_map:
                            # 1. 更新内存中的最新价格和容量
                            # 我们将 value 改为一个包含 price 和 size 的字典
                            self.current_prices[token_id] = {'price': best_bid, 'size': best_size}

                            # 2. 获取对应的配对 Token 数据
                            pair_token = self.market_map[token_id]['pair_token']
                            pair_data = self.current_prices.get(pair_token, {'price': 0, 'size': 0})
                            pair_price = pair_data['price']
                            pair_size = pair_data['size']

                            # 3. 核心计算：只有当配对价格已经存在时才计算
                            if pair_price > 0:
                                total_price = best_bid + pair_price

                                # 取双方中较小的流动性作为交易瓶颈 (木桶效应)
                                available_liquidity = min(best_size, pair_size)

                                # 策略条件：利润空间 > 2% 且 该价位支撑至少 50 USDC 的交易量
                                if 0 < total_price <= 0.98 and available_liquidity >= 50:
                                    market_info = self.market_map[token_id]
                                    logging.info(
                                        f"⚡ [实盘级套利] 总价: {total_price:.4f} | "
                                        f"最大可容纳资金: ${available_liquidity:.2f} | "
                                        f"市场: {market_info['question']}"
                                    )

                                    # 将深度数据也存入，方便后续复盘
                                    mock_market_data = [{
                                        'id': market_info['market_id'],
                                        'question': market_info['question'],
                                        'outcomePrices': [best_bid, pair_price] if market_info['type'] == 'Yes' else [pair_price, best_bid],
                                        'available_liquidity': available_liquidity
                                    }]
                                    analyze_and_store(mock_market_data)

                                    # ==========================================
                                    # 👇 新增：终极实盘开火指令 (自动化执行)
                                    # ==========================================
                                    TRADE_SIZE = 10  # 测试阶段，每次只买 10 份

                                    logging.info(f"🔫 正在自动发射订单！买入 {TRADE_SIZE} 份 {market_info['question']}")

                                    # 买入第一条腿 (当前触发的 Token)
                                    leg1_success = self.trader.execute_arbitrage(
                                        token_id=token_id,
                                        price=best_bid,
                                        size=TRADE_SIZE
                                    )

                                    # 买入第二条腿 (配对的 Token)
                                    leg2_success = self.trader.execute_arbitrage(
                                        token_id=pair_token,
                                        price=pair_price,
                                        size=TRADE_SIZE
                                    )

                                    if leg1_success and leg2_success:
                                        logging.info("🎉 双腿套利完美成交！等待事件结算锁定利润！")
                                    else:
                                        logging.warning("⚠️ 存在单腿成交风险，请登录 Polymarket 检查订单簿。")

        except Exception as e:
            pass  # 忽略非价格类的心跳包解析错误

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
