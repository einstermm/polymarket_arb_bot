import logging
from core.ws_stream import PolymarketStreamer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def run_bot():
    logging.info("🚀 启动 Polymarket 极速 WebSocket 监听机器人...")
    streamer = PolymarketStreamer()

    # run_forever 是阻塞的，会一直保持监听
    while True:
        try:
            streamer.start()
        except Exception as e:
            logging.error(f"主进程异常崩溃，5 秒后重启: {e}")
            import time
            time.sleep(5)


if __name__ == "__main__":
    run_bot()
