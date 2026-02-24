import logging
from database.db_pool import get_db_connection


def analyze_and_store(markets):
    """分析套利空间并写入 MySQL"""
    conn = get_db_connection()
    cursor = conn.cursor()
    opportunity_count = 0

    try:
        for market in markets:
            market_id = market.get('id')
            question = market.get('question')
            outcome_prices = market.get('outcomePrices')

            # 过滤无效数据
            if not outcome_prices or len(outcome_prices) != 2:
                continue

            try:
                yes_price = float(outcome_prices[0])
                no_price = float(outcome_prices[1])
                total_price = yes_price + no_price

                # 1. 记录原始价格到流水表
                cursor.execute('''
                    INSERT INTO market_prices (market_id, question, yes_price, no_price, total_price)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (market_id, question, yes_price, no_price, total_price))

                # 2. 逻辑判断：Yes + No <= 0.98 则视为套利机会
                if 0 < total_price <= 0.98:
                    profit_margin = 1.0 - total_price
                    # 获取传递过来的流动性，如果没有则默认为 0
                    liquidity = market.get('available_liquidity', 0)

                    logging.info(f"🚨 发现实盘套利空间! 利润: {profit_margin:.2%} | 容量: ${liquidity:.2f} | {question}")

                    # 插入数据时加上 available_liquidity 字段
                    cursor.execute('''
                                        INSERT INTO arbitrage_opportunities (market_id, question, total_price, profit_margin, available_liquidity)
                                        VALUES (%s, %s, %s, %s, %s)
                                    ''', (market_id, question, total_price, profit_margin, liquidity))
                    opportunity_count += 1

            except ValueError:
                continue

        # 批量提交事务
        conn.commit()
    except Exception as e:
        logging.error(f"数据库写入错误: {e}")
        conn.rollback()
    finally:
        # 释放资源，将连接归还给连接池
        cursor.close()
        conn.close()

    return opportunity_count
