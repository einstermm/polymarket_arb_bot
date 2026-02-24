import time
import logging
from core.fetcher import fetch_active_markets
from core.analyzer import analyze_and_store

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_bot():
    logging.info("启动 Polymarket MySQL 监控机器人...")
    while True:
        try:
            markets = fetch_active_markets()
            if markets:
                count = analyze_and_store(markets)
                logging.info(f"扫描完毕: 发现 {count} 个套利机会。")
        except Exception as e:
            logging.error(f"运行出错: {e}")

        time.sleep(60)

if __name__ == "__main__":
    run_bot()