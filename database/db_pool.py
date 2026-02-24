import time
import logging
import pymysql
from dbutils.pooled_db import PooledDB
from config.settings import Config

# 设置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

mysql_pool = None


def init_db_pool():
    """初始化数据库连接池，带有重试机制"""
    global mysql_pool
    max_retries = 10
    retry_delay = 3  # 每次重试间隔3秒

    for attempt in range(max_retries):
        try:
            mysql_pool = PooledDB(
                creator=pymysql,
                maxconnections=10,
                mincached=2,
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                autocommit=True,
                cursorclass=pymysql.cursors.DictCursor
            )
            logging.info("✅ 成功连接到 MySQL 数据库并建立连接池！")
            return
        except Exception as e:
            logging.warning(f"⏳ 数据库尚未就绪，等待重试... (尝试 {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

    # 如果 10 次都失败了，再抛出异常让程序退出
    raise ConnectionError("❌ 无法连接到数据库，已达到最大重试次数。")


# 在模块被导入时，执行初始化
init_db_pool()


def get_db_connection():
    """从连接池获取一个可用连接"""
    if mysql_pool is None:
        raise Exception("数据库连接池未正确初始化。")
    return mysql_pool.connection()
