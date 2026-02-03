"""
炒股高手 AI 智能体 - 股票数据工具
使用 AKShare 获取 A股数据
"""

from langchain_core.tools import tool
import akshare as ak
import pandas as pd
import time


def retry_request(func, max_retries=3, delay=1):
    """带重试机制的请求包装器"""
    last_error = None
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if i < max_retries - 1:
                time.sleep(delay * (i + 1))  # 递增延迟
    raise last_error


@tool
def get_stock_info(stock_code: str) -> str:
    """
    获取股票的基本信息，包括公司名称、行业、市值等。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)

    Returns:
        股票基本信息的字符串描述
    """
    try:
        # 获取个股信息
        stock_info = ak.stock_individual_info_em(symbol=stock_code)

        # 转换为字典格式
        info_dict = dict(zip(stock_info['item'], stock_info['value']))

        result = f"""
📊 股票基本信息 - {stock_code}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
股票名称: {info_dict.get('股票简称', 'N/A')}
所属行业: {info_dict.get('行业', 'N/A')}
总市值: {info_dict.get('总市值', 'N/A')}
流通市值: {info_dict.get('流通市值', 'N/A')}
市盈率(动态): {info_dict.get('市盈率(动态)', 'N/A')}
市净率: {info_dict.get('市净率', 'N/A')}
上市时间: {info_dict.get('上市时间', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return result
    except Exception as e:
        return f"获取股票信息失败: {str(e)}"


@tool
def get_realtime_quote(stock_code: str) -> str:
    """
    获取股票的实时行情数据，包括当前价格、涨跌幅、成交量等。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)

    Returns:
        实时行情数据的字符串描述
    """
    try:
        # 首先获取股票名称
        try:
            info_df = retry_request(lambda: ak.stock_individual_info_em(symbol=stock_code), max_retries=2)
            info_dict = dict(zip(info_df['item'], info_df['value']))
            stock_name = info_dict.get('股票简称', stock_code)
        except:
            stock_name = stock_code

        # 尝试获取实时行情
        try:
            df = retry_request(lambda: ak.stock_bid_ask_em(symbol=stock_code), max_retries=3, delay=2)

            if not df.empty:
                # 转换为字典
                data = dict(zip(df['item'], df['value']))

                current_price = float(data.get('最新', 0))
                prev_close = float(data.get('昨收', 0))
                change_pct = float(data.get('涨幅', 0))
                change = float(data.get('涨跌', 0))

                # 涨跌emoji
                emoji = "🔴" if change_pct < 0 else "🟢" if change_pct > 0 else "⚪"

                result = f"""
{emoji} 实时行情 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前价格: ¥{current_price:.2f}
涨跌幅: {change_pct:+.2f}%
涨跌额: ¥{change:+.2f}
今开: ¥{data.get('今开', 0):.2f}
最高: ¥{data.get('最高', 0):.2f}
最低: ¥{data.get('最低', 0):.2f}
昨收: ¥{prev_close:.2f}
成交量: {int(data.get('总手', 0))} 手
成交额: ¥{data.get('金额', 0)/10000:.2f} 万
换手率: {data.get('换手', 0):.2f}%
涨停价: ¥{data.get('涨停', 0):.2f}
跌停价: ¥{data.get('跌停', 0):.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                return result
        except:
            pass

        # 备用方案：从K线数据获取最新行情
        try:
            kline_df = retry_request(lambda: ak.stock_zh_a_hist(symbol=stock_code, period="daily", adjust="qfq"), max_retries=2)

            if not kline_df.empty:
                latest = kline_df.iloc[-1]
                prev = kline_df.iloc[-2] if len(kline_df) >= 2 else latest

                current_price = float(latest['收盘'])
                prev_close = float(prev['收盘'])
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100 if prev_close > 0 else 0

                emoji = "🔴" if change_pct < 0 else "🟢" if change_pct > 0 else "⚪"

                result = f"""
{emoji} 行情数据 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 日期: {latest['日期']}
当前价格: ¥{current_price:.2f}
涨跌幅: {change_pct:+.2f}%
涨跌额: ¥{change:+.2f}
今开: ¥{latest['开盘']:.2f}
最高: ¥{latest['最高']:.2f}
最低: ¥{latest['最低']:.2f}
昨收: ¥{prev_close:.2f}
成交量: {int(latest['成交量'])} 手
成交额: ¥{latest['成交额']/10000:.2f} 万
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 数据来源: 日K线（非实时）
"""
                return result
        except:
            pass

        return f"获取 {stock_name}({stock_code}) 行情数据失败，网络连接不稳定，请稍后重试"

    except Exception as e:
        print(f"Error in get_realtime_quote: {str(e)}")
        return f"获取实时行情失败，请稍后重试: {str(e)}"


@tool
def search_stock(keyword: str) -> str:
    """
    根据关键词搜索股票，可以是股票名称或代码的一部分。

    Args:
        keyword: 搜索关键词，如 "茅台"、"银行"、"000001"

    Returns:
        匹配的股票列表
    """
    try:
        # 使用股票列表接口
        df = ak.stock_info_a_code_name()

        # 按名称或代码搜索
        mask = df['name'].str.contains(keyword, na=False) | df['code'].str.contains(keyword, na=False)
        results = df[mask].head(10)

        if results.empty:
            return f"未找到包含 '{keyword}' 的股票"

        result = f"🔍 搜索结果 - '{keyword}'\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        for _, row in results.iterrows():
            result += f"📌 {row['code']} {row['name']}\n"

        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "提示：使用股票代码查询详细行情\n"
        return result
    except Exception as e:
        return f"搜索股票失败: {str(e)}"


@tool
def get_kline_data(stock_code: str, period: str = "daily") -> str:
    """
    获取股票的K线数据，用于技术分析。

    Args:
        stock_code: 股票代码，如 "000001" 或 "600519"
        period: K线周期，可选 "daily"(日线), "weekly"(周线), "monthly"(月线)

    Returns:
        最近的K线数据摘要
    """
    try:
        period_map = {
            "daily": "daily",
            "weekly": "weekly",
            "monthly": "monthly"
        }

        # 获取K线数据
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period=period_map.get(period, "daily"),
            adjust="qfq"  # 前复权
        )

        # 取最近10条数据
        recent = df.tail(10)

        result = f"📈 K线数据 - {stock_code} ({period})\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "日期        | 开盘   | 收盘   | 最高   | 最低   | 成交量\n"
        result += "------------------------------------------------------\n"

        for _, row in recent.iterrows():
            result += f"{row['日期']} | {row['开盘']:.2f} | {row['收盘']:.2f} | {row['最高']:.2f} | {row['最低']:.2f} | {row['成交量']}\n"

        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        return result
    except Exception as e:
        return f"获取K线数据失败: {str(e)}"


@tool
def calculate_indicators(stock_code: str) -> str:
    """
    计算股票的技术指标，包括均线(MA)、MACD、KDJ、RSI、布林带(BOLL)等。
    用于辅助技术分析和趋势判断。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)

    Returns:
        技术指标分析结果的字符串描述
    """
    try:
        # 获取最近120个交易日的K线数据（确保有足够数据计算指标）
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            adjust="qfq"
        )

        if len(df) < 60:
            return f"数据不足，无法计算技术指标（需要至少60个交易日数据）"

        # 获取股票名称
        info_df = ak.stock_individual_info_em(symbol=stock_code)
        info_dict = dict(zip(info_df['item'], info_df['value']))
        stock_name = info_dict.get('股票简称', stock_code)

        # 准备数据
        close = df['收盘'].astype(float)
        high = df['最高'].astype(float)
        low = df['最低'].astype(float)
        volume = df['成交量'].astype(float)

        # ========== 1. 计算均线 MA ==========
        ma5 = close.rolling(window=5).mean()
        ma10 = close.rolling(window=10).mean()
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()

        # ========== 2. 计算 MACD ==========
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd = (dif - dea) * 2

        # ========== 3. 计算 KDJ ==========
        low_list = low.rolling(window=9).min()
        high_list = high.rolling(window=9).max()
        rsv = (close - low_list) / (high_list - low_list) * 100
        rsv = rsv.fillna(50)

        k = pd.Series(index=df.index, dtype=float)
        d = pd.Series(index=df.index, dtype=float)
        k.iloc[0] = 50
        d.iloc[0] = 50

        for i in range(1, len(df)):
            k.iloc[i] = 2/3 * k.iloc[i-1] + 1/3 * rsv.iloc[i]
            d.iloc[i] = 2/3 * d.iloc[i-1] + 1/3 * k.iloc[i]

        j = 3 * k - 2 * d

        # ========== 4. 计算 RSI ==========
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # ========== 5. 计算布林带 BOLL ==========
        boll_mid = close.rolling(window=20).mean()
        boll_std = close.rolling(window=20).std()
        boll_upper = boll_mid + 2 * boll_std
        boll_lower = boll_mid - 2 * boll_std

        # 获取最新值
        latest = df.iloc[-1]
        latest_close = close.iloc[-1]
        latest_date = latest['日期']

        # ========== 生成分析结果 ==========
        result = f"""
📊 技术指标分析 - {stock_name} ({stock_code})
日期: {latest_date}  收盘价: ¥{latest_close:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 【均线系统 MA】
  MA5:  ¥{ma5.iloc[-1]:.2f}  {'↑' if latest_close > ma5.iloc[-1] else '↓'}
  MA10: ¥{ma10.iloc[-1]:.2f}  {'↑' if latest_close > ma10.iloc[-1] else '↓'}
  MA20: ¥{ma20.iloc[-1]:.2f}  {'↑' if latest_close > ma20.iloc[-1] else '↓'}
  MA60: ¥{ma60.iloc[-1]:.2f}  {'↑' if latest_close > ma60.iloc[-1] else '↓'}
"""

        # 均线多头/空头判断
        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            result += "  💹 均线呈多头排列，趋势向上\n"
        elif ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]:
            result += "  📉 均线呈空头排列，趋势向下\n"
        else:
            result += "  ⚖️ 均线交织，趋势不明朗\n"

        result += f"""
📊 【MACD指标】
  DIF:  {dif.iloc[-1]:.3f}
  DEA:  {dea.iloc[-1]:.3f}
  MACD: {macd.iloc[-1]:.3f}
"""
        # MACD 信号判断
        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            result += "  🔥 MACD金叉，买入信号\n"
        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
            result += "  ⚠️ MACD死叉，卖出信号\n"
        elif dif.iloc[-1] > 0 and dea.iloc[-1] > 0:
            result += "  📈 MACD在零轴上方，多头市场\n"
        else:
            result += "  📉 MACD在零轴下方，空头市场\n"

        result += f"""
📈 【KDJ指标】
  K值: {k.iloc[-1]:.2f}
  D值: {d.iloc[-1]:.2f}
  J值: {j.iloc[-1]:.2f}
"""
        # KDJ 信号判断
        if k.iloc[-1] < 20 and d.iloc[-1] < 20:
            result += "  💡 KDJ处于超卖区，可能反弹\n"
        elif k.iloc[-1] > 80 and d.iloc[-1] > 80:
            result += "  ⚠️ KDJ处于超买区，注意风险\n"
        elif k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
            result += "  🔥 KDJ金叉，买入信号\n"
        elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
            result += "  ⚠️ KDJ死叉，卖出信号\n"

        result += f"""
📉 【RSI指标】(14日)
  RSI: {rsi.iloc[-1]:.2f}
"""
        # RSI 信号判断
        if rsi.iloc[-1] < 30:
            result += "  💡 RSI<30，超卖区域，可能反弹\n"
        elif rsi.iloc[-1] > 70:
            result += "  ⚠️ RSI>70，超买区域，注意回调\n"
        else:
            result += "  ⚖️ RSI处于正常区间\n"

        result += f"""
📊 【布林带 BOLL】
  上轨: ¥{boll_upper.iloc[-1]:.2f}
  中轨: ¥{boll_mid.iloc[-1]:.2f}
  下轨: ¥{boll_lower.iloc[-1]:.2f}
"""
        # 布林带位置判断
        if latest_close > boll_upper.iloc[-1]:
            result += "  ⚠️ 股价突破上轨，注意超买风险\n"
        elif latest_close < boll_lower.iloc[-1]:
            result += "  💡 股价跌破下轨，可能超卖\n"
        elif latest_close > boll_mid.iloc[-1]:
            result += "  📈 股价在中轨上方，偏强势\n"
        else:
            result += "  📉 股价在中轨下方，偏弱势\n"

        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "⚠️ 以上指标仅供参考，不构成投资建议\n"

        return result

    except Exception as e:
        return f"计算技术指标失败: {str(e)}"


@tool
def get_stock_news(stock_code: str, count: int = 10) -> str:
    """
    获取股票相关的最新新闻资讯，用于了解市场动态和舆情。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)
        count: 返回的新闻数量，默认10条

    Returns:
        股票相关新闻列表的字符串描述
    """
    try:
        # 获取股票名称
        info_df = ak.stock_individual_info_em(symbol=stock_code)
        info_dict = dict(zip(info_df['item'], info_df['value']))
        stock_name = info_dict.get('股票简称', stock_code)

        # 获取股票新闻
        df = ak.stock_news_em(symbol=stock_code)

        if df.empty:
            return f"未找到 {stock_name}({stock_code}) 的相关新闻"

        # 取前N条新闻
        news_list = df.head(count)

        result = f"""
📰 股票新闻 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        for idx, row in news_list.iterrows():
            title = row['新闻标题']
            time = row['发布时间']
            source = row['文章来源']
            content = row['新闻内容']

            # 截取摘要（前100字）
            summary = content[:100] + "..." if len(content) > 100 else content

            result += f"""
📌 【{idx + 1}】{title}
   🕐 {time} | 📍 {source}
   📝 {summary}
"""

        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"共获取 {len(news_list)} 条相关新闻\n"

        return result

    except Exception as e:
        return f"获取股票新闻失败: {str(e)}"


@tool
def get_financial_data(stock_code: str) -> str:
    """
    获取股票的财务数据，包括营收、净利润、ROE、毛利率等核心财务指标。
    用于基本面分析和价值投资判断。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)

    Returns:
        财务数据分析结果的字符串描述
    """
    try:
        # 获取股票名称
        info_df = ak.stock_individual_info_em(symbol=stock_code)
        info_dict = dict(zip(info_df['item'], info_df['value']))
        stock_name = info_dict.get('股票简称', stock_code)

        # 获取财务摘要数据（同花顺）
        df = ak.stock_financial_abstract_ths(symbol=stock_code, indicator="按报告期")

        if df.empty:
            return f"未找到 {stock_name}({stock_code}) 的财务数据"

        # 获取最近4个季度的数据
        recent = df.tail(4).iloc[::-1]  # 倒序，最新的在前

        result = f"""
💰 财务数据分析 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 【最近财报摘要】
"""

        for idx, row in recent.iterrows():
            report_date = row['报告期']
            revenue = row['营业总收入'] if pd.notna(row['营业总收入']) else 'N/A'
            net_profit = row['净利润'] if pd.notna(row['净利润']) else 'N/A'
            profit_growth = row['净利润同比增长率'] if pd.notna(row['净利润同比增长率']) else 'N/A'
            revenue_growth = row['营业总收入同比增长率'] if pd.notna(row['营业总收入同比增长率']) else 'N/A'

            result += f"""
📅 {report_date}
   营业收入: {revenue}  (同比: {revenue_growth})
   净利润: {net_profit}  (同比: {profit_growth})
"""

        # 获取最新一期的详细数据
        latest = df.iloc[-1]

        result += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 【核心财务指标】(截至 {latest['报告期']})

💵 盈利能力:
   净资产收益率(ROE): {latest.get('净资产收益率', 'N/A')}
   销售净利率: {latest.get('销售净利率', 'N/A')}
   净资产收益率(摊薄): {latest.get('净资产收益率-摊薄', 'N/A')}

📊 每股指标:
   基本每股收益: {latest.get('基本每股收益', 'N/A')}
   每股净资产: {latest.get('每股净资产', 'N/A')}
   每股资本公积: {latest.get('每股资本公积金', 'N/A')}
   每股未分配利润: {latest.get('每股未分配利润', 'N/A')}
   每股经营现金流: {latest.get('每股经营现金流', 'N/A')}

🏦 偿债能力:
   资产负债率: {latest.get('资产负债率', 'N/A')}
   流动比率: {latest.get('流动比率', 'N/A')}
   速动比率: {latest.get('速动比率', 'N/A')}

📦 运营能力:
   存货周转天数: {latest.get('存货周转天数', 'N/A')}
   应收账款周转天数: {latest.get('应收账款周转天数', 'N/A')}
"""

        # 增长趋势分析
        if len(df) >= 2:
            prev = df.iloc[-2]
            curr = df.iloc[-1]

            result += "\n📊 【增长趋势判断】\n"

            # 净利润增长判断
            try:
                curr_growth = str(curr.get('净利润同比增长率', '0'))
                if '%' in curr_growth:
                    growth_val = float(curr_growth.replace('%', ''))
                    if growth_val > 20:
                        result += "   ✅ 净利润高速增长(>20%)，成长性良好\n"
                    elif growth_val > 0:
                        result += "   📈 净利润正增长，业绩稳定\n"
                    elif growth_val > -20:
                        result += "   ⚠️ 净利润小幅下滑，需关注\n"
                    else:
                        result += "   🔴 净利润大幅下滑(>20%)，风险较高\n"
            except:
                pass

            # ROE 判断
            try:
                roe = str(latest.get('净资产收益率', '0'))
                if '%' in roe:
                    roe_val = float(roe.replace('%', ''))
                    if roe_val > 15:
                        result += "   ✅ ROE优秀(>15%)，盈利能力强\n"
                    elif roe_val > 10:
                        result += "   📈 ROE良好(10-15%)，盈利能力较强\n"
                    elif roe_val > 5:
                        result += "   ⚖️ ROE一般(5-10%)，盈利能力中等\n"
                    else:
                        result += "   ⚠️ ROE较低(<5%)，盈利能力较弱\n"
            except:
                pass

            # 负债率判断
            try:
                debt = str(latest.get('资产负债率', '0'))
                if '%' in debt:
                    debt_val = float(debt.replace('%', ''))
                    if debt_val < 40:
                        result += "   ✅ 资产负债率较低(<40%)，财务稳健\n"
                    elif debt_val < 60:
                        result += "   ⚖️ 资产负债率适中(40-60%)，财务正常\n"
                    else:
                        result += "   ⚠️ 资产负债率较高(>60%)，注意债务风险\n"
            except:
                pass

        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "⚠️ 财务数据仅供参考，投资需综合分析\n"

        return result

    except Exception as e:
        return f"获取财务数据失败: {str(e)}"


@tool
def analyze_trend(stock_code: str) -> str:
    """
    综合分析股票的趋势，包括价格趋势、成交量、支撑压力位、买卖信号等。
    给出综合的趋势判断和操作建议。

    Args:
        stock_code: 股票代码，如 "000001" (平安银行) 或 "600519" (贵州茅台)

    Returns:
        综合趋势分析结果和操作建议
    """
    try:
        # 获取股票名称
        info_df = ak.stock_individual_info_em(symbol=stock_code)
        info_dict = dict(zip(info_df['item'], info_df['value']))
        stock_name = info_dict.get('股票简称', stock_code)

        # 获取K线数据（最近120个交易日）
        df = ak.stock_zh_a_hist(
            symbol=stock_code,
            period="daily",
            adjust="qfq"
        )

        if len(df) < 60:
            return f"数据不足，无法进行趋势分析（需要至少60个交易日数据）"

        # 准备数据
        close = df['收盘'].astype(float)
        high = df['最高'].astype(float)
        low = df['最低'].astype(float)
        volume = df['成交量'].astype(float)

        # 获取实时行情
        quote_df = ak.stock_bid_ask_em(symbol=stock_code)
        quote_dict = dict(zip(quote_df['item'], quote_df['value']))
        current_price = float(quote_dict.get('最新', close.iloc[-1]))

        # ========== 1. 计算均线 ==========
        ma5 = close.rolling(window=5).mean()
        ma10 = close.rolling(window=10).mean()
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()

        # ========== 2. 计算趋势指标 ==========
        # 近期涨跌幅
        change_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
        change_10d = (close.iloc[-1] / close.iloc[-11] - 1) * 100 if len(close) >= 11 else 0
        change_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0

        # ========== 3. 计算支撑位和压力位 ==========
        recent_20 = df.tail(20)
        recent_high = recent_20['最高'].astype(float).max()
        recent_low = recent_20['最低'].astype(float).min()

        # 使用最近的高低点作为关键位置
        resistance_1 = recent_high  # 近期压力位
        support_1 = recent_low  # 近期支撑位

        # 使用均线作为动态支撑压力
        ma20_val = ma20.iloc[-1]
        ma60_val = ma60.iloc[-1]

        # ========== 4. 成交量分析 ==========
        vol_ma5 = volume.rolling(window=5).mean()
        vol_ma20 = volume.rolling(window=20).mean()
        vol_ratio = volume.iloc[-1] / vol_ma20.iloc[-1] if vol_ma20.iloc[-1] > 0 else 1

        # ========== 5. 趋势判断 ==========
        # 均线多空判断
        ma_bullish = ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]
        ma_bearish = ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]

        # 价格与均线位置
        above_ma20 = current_price > ma20_val
        above_ma60 = current_price > ma60_val

        # 趋势强度评分 (0-100)
        trend_score = 50  # 基准分

        if ma_bullish:
            trend_score += 15
        elif ma_bearish:
            trend_score -= 15

        if above_ma20:
            trend_score += 10
        else:
            trend_score -= 10

        if above_ma60:
            trend_score += 10
        else:
            trend_score -= 10

        if change_5d > 5:
            trend_score += 10
        elif change_5d < -5:
            trend_score -= 10

        if vol_ratio > 1.5:
            trend_score += 5 if change_5d > 0 else -5

        # 限制在0-100之间
        trend_score = max(0, min(100, trend_score))

        # ========== 6. 生成分析报告 ==========
        latest_date = df.iloc[-1]['日期']

        result = f"""
📊 趋势分析报告 - {stock_name} ({stock_code})
日期: {latest_date}  当前价: ¥{current_price:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 【价格趋势】
   近5日涨跌: {change_5d:+.2f}%
   近10日涨跌: {change_10d:+.2f}%
   近20日涨跌: {change_20d:+.2f}%
"""

        # 趋势方向判断
        if change_5d > 3 and change_10d > 5:
            result += "   🔥 短期强势上涨趋势\n"
        elif change_5d > 0 and change_10d > 0:
            result += "   📈 温和上涨趋势\n"
        elif change_5d < -3 and change_10d < -5:
            result += "   📉 短期明显下跌趋势\n"
        elif change_5d < 0 and change_10d < 0:
            result += "   ⬇️ 温和下跌趋势\n"
        else:
            result += "   ⚖️ 震荡整理走势\n"

        result += f"""
📊 【均线系统】
   MA5:  ¥{ma5.iloc[-1]:.2f}  {'↑' if current_price > ma5.iloc[-1] else '↓'}
   MA10: ¥{ma10.iloc[-1]:.2f}  {'↑' if current_price > ma10.iloc[-1] else '↓'}
   MA20: ¥{ma20.iloc[-1]:.2f}  {'↑' if current_price > ma20.iloc[-1] else '↓'}
   MA60: ¥{ma60.iloc[-1]:.2f}  {'↑' if current_price > ma60.iloc[-1] else '↓'}
"""

        if ma_bullish:
            result += "   💹 均线多头排列，趋势向上\n"
        elif ma_bearish:
            result += "   📉 均线空头排列，趋势向下\n"
        else:
            result += "   ⚖️ 均线交织，方向不明\n"

        result += f"""
🎯 【关键价位】
   压力位1: ¥{resistance_1:.2f} (近期高点)
   压力位2: ¥{ma20_val:.2f} (MA20)
   ━━━━━━━━━━━
   支撑位1: ¥{support_1:.2f} (近期低点)
   支撑位2: ¥{ma60_val:.2f} (MA60)
"""

        # 当前位置判断
        if current_price > resistance_1 * 0.98:
            result += "   ⚠️ 当前接近压力位，注意突破或回调\n"
        elif current_price < support_1 * 1.02:
            result += "   💡 当前接近支撑位，关注是否企稳\n"
        else:
            result += "   ⚖️ 当前处于支撑与压力之间\n"

        result += f"""
📊 【成交量分析】
   今日成交: {volume.iloc[-1]/10000:.2f} 万手
   5日均量: {vol_ma5.iloc[-1]/10000:.2f} 万手
   20日均量: {vol_ma20.iloc[-1]/10000:.2f} 万手
   量比: {vol_ratio:.2f}
"""

        if vol_ratio > 2:
            result += "   🔥 成交量显著放大，关注异动\n"
        elif vol_ratio > 1.5:
            result += "   📈 成交量温和放大\n"
        elif vol_ratio < 0.5:
            result += "   📉 成交量明显萎缩\n"
        else:
            result += "   ⚖️ 成交量正常\n"

        result += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 【综合趋势评分】: {trend_score}/100
"""

        # 趋势评级
        if trend_score >= 80:
            result += "   评级: ⭐⭐⭐⭐⭐ 强势多头\n"
            trend_desc = "强势上涨"
        elif trend_score >= 65:
            result += "   评级: ⭐⭐⭐⭐ 偏多\n"
            trend_desc = "偏强震荡"
        elif trend_score >= 50:
            result += "   评级: ⭐⭐⭐ 中性\n"
            trend_desc = "横盘整理"
        elif trend_score >= 35:
            result += "   评级: ⭐⭐ 偏空\n"
            trend_desc = "偏弱震荡"
        else:
            result += "   评级: ⭐ 弱势空头\n"
            trend_desc = "弱势下跌"

        result += f"""
📋 【操作建议】

🔸 趋势判断: {trend_desc}
"""

        # 操作建议
        if trend_score >= 70:
            result += f"""🔸 建议策略:
   - 已持有：继续持有，设置止盈位 ¥{resistance_1:.2f}
   - 未持有：可考虑逢低买入，止损位 ¥{support_1:.2f}
"""
        elif trend_score >= 50:
            result += f"""🔸 建议策略:
   - 已持有：持有观望，关注方向选择
   - 未持有：观望为主，等待趋势明朗
"""
        else:
            result += f"""🔸 建议策略:
   - 已持有：考虑减仓或止损，止损位 ¥{support_1:.2f}
   - 未持有：暂不建议买入，等待企稳信号
"""

        result += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 以上分析仅供参考，不构成投资建议
   股市有风险，投资需谨慎！
"""

        return result

    except Exception as e:
        return f"趋势分析失败: {str(e)}"
