import pymysql
from dbutils.pooled_db import PooledDB
from config.settings import Config

# 创建全局的 MySQL 连接池
mysql_pool = PooledDB(
    creator=pymysql,  # 使用 pymysql
    maxconnections=10,  # 最大连接数
    mincached=2,  # 初始化时创建的空闲连接
    host=Config.MYSQL_HOST,
    port=Config.MYSQL_PORT,
    user=Config.MYSQL_USER,
    password=Config.MYSQL_PASSWORD,
    database=Config.MYSQL_DB,
    autocommit=True,  # 自动提交事务
    cursorclass=pymysql.cursors.DictCursor
)


def get_db_connection():
    """从连接池获取一个连接"""
    return mysql_pool.connection()
