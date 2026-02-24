import os
import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, BalanceAllowanceParams, AssetType
from dotenv import load_dotenv

# 👇 新增这一行，强制显示 INFO 级别的日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# 从环境变量读取私钥 (绝对不要明文写在代码里!)
PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY")
POLYGON_CHAIN_ID = 137


class PolymarketTrader:
    def __init__(self):
        # 1. 初始化 CLOB 客户端
        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=POLYGON_CHAIN_ID,
            funder=self._get_wallet_address()  # 你的钱包公钥地址
        )
        self.setup_client()

    def _get_wallet_address(self):
        # 通过 web3.py 从私钥推导出公钥地址
        from web3 import Web3
        from eth_account import Account
        Account.enable_unaudited_hdwallet_features()
        account = Account.from_key(PRIVATE_KEY)
        return account.address

    def setup_client(self):
        """生成二层网络的 API Key 并授权"""
        logging.info("正在验证交易凭证...")

        # 2. 创建或获取 L2 API Keys
        self.client.set_api_creds(self.client.create_or_derive_api_creds())

        # 3. 检查 USDC 授权额度 (新版 API 写法)
        # 指定我们要查询和授权的是 COLLATERAL (即 USDC 抵押品)
        params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        allowance_info = self.client.get_balance_allowance(params)

        # 兼容处理返回的数据格式 (字典或对象)
        allowance_value = allowance_info.get('allowance', "0") if isinstance(allowance_info, dict) else getattr(allowance_info, 'allowance', "0")

        if str(allowance_value) == "0":
            logging.warning("USDC 未授权！正在向区块链发送授权交易，请稍候...")
            # 使用新版更新授权的方法
            self.client.update_balance_allowance(params=params)
            logging.info("USDC 授权成功！")
        else:
            logging.info("USDC 已授权，可以交易。")

    def execute_arbitrage(self, token_id, price, size):
        """
        执行买入操作
        :param token_id: 你要买的选项的 Token ID (比如 Yes 的 ID)
        :param price: 你的买入价格 (比如 0.45)
        :param size: 你想买多少份份额 (比如你想投 45 USDC，那就是 100 份)
        """
        logging.info(f"🚀 发起交易 -> Token: {token_id} | 价格: {price} | 份数: {size}")

        try:
            # 构建订单参数
            order_args = OrderArgs(
                price=price,
                size=size,
                side="BUY",
                token_id=token_id
            )

            # 创建订单并用 L2 Key 签名
            signed_order = self.client.create_order(order_args)

            # 发送到撮合引擎 (FOK = Fill or Kill，全部成交否则全部取消，防止部分成交造成的套利失败)
            response = self.client.post_order(signed_order, orderType=OrderType.FOK)

            if response.get('success'):
                logging.info(f"✅ 交易成功！订单 ID: {response['orderID']}")
                return True
            else:
                logging.error(f"❌ 交易失败: {response.get('errorMsg')}")
                return False

        except Exception as e:
            logging.error(f"下单异常: {e}")
            return False


# 测试入口
if __name__ == "__main__":
    # 确保你的 .env 文件里有 WALLET_PRIVATE_KEY=你的私钥
    trader = PolymarketTrader()
    print("交易模块初始化完成！")
