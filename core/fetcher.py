import requests
import logging
from config.settings import Config


def fetch_active_markets():
    """从 API 拉取活跃市场数据"""
    try:
        # 获取活跃且未关闭的市场，限制 100 条测试
        params = {"active": "true", "closed": "false", "limit": 100}
        response = requests.get(Config.API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"API 请求失败: {e}")
        return []
