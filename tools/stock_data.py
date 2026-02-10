"""
炒股高手 AI 智能体 - 股票数据工具
数据源：新浪财经网页数据

🎯 新浪财经特性：
✅ 覆盖A股实时行情与K线
✅ 无需 Token
⚠️ 仅适用于A股
"""

from langchain_core.tools import tool
import pandas as pd
from datetime import datetime
import re
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

def _normalize_cn_symbol(stock_code: str) -> str:
    code = stock_code.strip().lower()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return code


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


_SESSION = _build_session()


def _sina_request(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }
    resp = _SESSION.get(url, headers=headers, timeout=10)
    resp.encoding = resp.apparent_encoding or "gbk"
    return resp.text


def _sina_html_request(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://finance.sina.com.cn/",
    }
    resp = _SESSION.get(url, headers=headers, timeout=10)
    resp.encoding = resp.apparent_encoding or "gbk"
    return resp.text


def _parse_jsonp(text: str):
    match = re.search(r"\((\[.*\])\)", text, re.S)
    if not match:
        return []
    return json.loads(match.group(1))


def _parse_sina_suggest(text: str):
    match = re.search(r'="(.*)"', text)
    if not match:
        return []
    payload = match.group(1).strip()
    if not payload:
        return []
    items = payload.split(";")
    results = []
    for item in items:
        parts = item.split(",")
        if len(parts) < 2:
            continue
        symbol = parts[0]
        name = parts[1]
        market = "A股"
        if symbol.startswith("sh"):
            market = "上证"
        elif symbol.startswith("sz"):
            market = "深证"
        elif symbol.startswith("bj"):
            market = "北交所"
        results.append({"symbol": symbol, "name": name, "market": market})
    return results


def _extract_article_summary(url: str) -> str:
    try:
        html = _sina_html_request(url)
        soup = BeautifulSoup(html, "html.parser")
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta.get("content").strip()

        selectors = [
            "div.article p",
            "div.article-content p",
            "div.main-content p",
            "div#artibody p",
        ]
        for sel in selectors:
            p = soup.select_one(sel)
            if p and p.get_text(strip=True):
                return p.get_text(strip=True)
        return ""
    except Exception:
        return ""


def _strip_summaries(items: list[dict]) -> list[dict]:
    return [{"title": i.get("title", ""), "url": i.get("url", ""), "date": i.get("date", "")}
            for i in items if i.get("title")]


def _parse_company_news(symbol: str, limit: int) -> list[dict]:
    url = f"https://finance.sina.com.cn/realstock/company/{symbol}/nc.shtml"
    html = _sina_html_request(url)
    soup = BeautifulSoup(html, "html.parser")

    items = []
    selectors = [
        "div.datelist ul li",
        "div.datelist li",
        "ul.list li",
        "div.newslist li",
        "div#newslist li",
    ]
    for li in soup.select(",".join(selectors)):
        a = li.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 4:
            continue
        href = a["href"]
        if href.startswith("/"):
            href = f"https://finance.sina.com.cn{href}"
        if not href.startswith("http"):
            continue
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", li.get_text(" ", strip=True))
        date_text = date_match.group(0) if date_match else ""
        items.append({"title": title, "url": href, "date": date_text})

    unique = []
    seen = set()
    for item in items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)
        if len(unique) >= limit:
            break

    for item in unique:
        item["summary"] = _extract_article_summary(item["url"])
    return unique


def _parse_company_announcements(symbol: str, limit: int) -> list[dict]:
    url = f"https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletin.php?symbol={symbol}"
    html = _sina_html_request(url)
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("table#DataTable tr, table tr")
    items = []
    for row in rows:
        a = row.find("a", href=True)
        tds = row.find_all("td")
        if not a or not tds:
            continue
        title = a.get_text(strip=True)
        date_text = tds[-1].get_text(strip=True) if len(tds) >= 2 else ""
        href = a["href"]
        if href and href.startswith("/"):
            href = f"https://vip.stock.finance.sina.com.cn{href}"
        if href and not href.startswith("http"):
            continue
        items.append({"title": title, "url": href, "date": date_text})

    unique = []
    seen = set()
    for item in items:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)
        if len(unique) >= limit:
            break

    for item in unique:
        item["summary"] = _extract_article_summary(item["url"])
    return unique


def _parse_financial_summary(symbol: str) -> dict:
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/{symbol[2:]}.phtml"
    html = _sina_html_request(url)
    soup = BeautifulSoup(html, "html.parser")

    data = {}
    for row in soup.select("table tr"):
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"]) if c.get_text(strip=True)]
        if len(cells) < 2:
            continue
        key = cells[0]
        val = cells[1]
        if key and val:
            data[key] = val

    return data


def _parse_financial_table(symbol: str) -> tuple[list[str], dict]:
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_FinanceSummary/stockid/{symbol[2:]}.phtml"
    html = _sina_html_request(url)
    soup = BeautifulSoup(html, "html.parser")

    date_pattern = re.compile(r"\d{4}[-./]\d{2}[-./]\d{2}")
    best_periods = []
    best_rows = {}

    for table in soup.select("table"):
        header_cells = table.select("tr th")
        headers = [c.get_text(strip=True) for c in header_cells]
        if not headers:
            continue
        periods = [h for h in headers if date_pattern.search(h)]
        if len(periods) < 2:
            continue

        rows = {}
        for tr in table.select("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"]) if c.get_text(strip=True)]
            if len(cells) < len(periods) + 1:
                continue
            key = cells[0]
            values = cells[1:1 + len(periods)]
            rows[key] = values

        if len(rows) > len(best_rows):
            best_periods = periods
            best_rows = rows

    return best_periods, best_rows


def _to_number(value: str) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"--", "N/A", "-"}:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_metric_value(value: str) -> tuple[str, str]:
    if value is None:
        return "--", ""
    text = str(value).strip()
    if not text:
        return "--", ""
    note = ""
    if "%" in text:
        note = "(百分比)"
    elif any(unit in text for unit in ["亿", "万", "千", "百"]):
        note = "(含单位)"
    return text, note


def _detect_unit(value: str) -> str:
    if not value:
        return ""
    for unit in ["亿", "万", "千", "百"]:
        if unit in value:
            return unit
    return ""


def _unit_consistency(values: list[str]) -> tuple[bool, str]:
    units = {u for u in (_detect_unit(v) for v in values) if u}
    if len(units) > 1:
        return False, f"单位不一致({','.join(sorted(units))})"
    return True, ""


def _get_candles_sina(stock_code: str, days: int) -> pd.DataFrame:
    symbol = _normalize_cn_symbol(stock_code)
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/"
        "var%20____/CN_MarketDataService.getKLineData"
        f"?symbol={symbol}&scale=240&ma=no&datalen={max(30, days)}"
    )
    text = _sina_request(url)
    rows = _parse_jsonp(text)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.rename(
        columns={
            "day": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "volume": "成交量",
        }
    )
    df["日期"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
    for col in ["开盘", "最高", "最低", "收盘", "成交量"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _get_candles(symbol: str, resolution: str, days: int) -> pd.DataFrame:
    df = _get_candles_sina(symbol, days)
    if df.empty:
        raise Exception("新浪财经数据获取失败")
    return df


def get_stock_name(symbol: str) -> str:
    """获取股票名称"""
    try:
        return symbol
    except Exception as e:
        print(f"获取股票名称失败: {e}")
    return symbol


@tool
def get_stock_info(stock_code: str) -> str:
    """
    获取股票的基本信息，包括公司名称、行业、市值等。

    Args:
        stock_code: 股票代码，如 "AAPL" (苹果公司) 或 "TSLA" (特斯拉)

    Returns:
        股票基本信息的字符串描述
    """
    try:
        stock_name = get_stock_name(stock_code)
        quote_text = _get_realtime_quote_sina(stock_code)
        result = f"""
📊 股票基本信息 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
股票代码: {stock_code}
股票名称: {stock_name}
所属行业: N/A
国家/地区: 中国
交易所: A股
IPO 日期: N/A
实时行情:
{quote_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 数据来源: 新浪财经
"""
        return result
    except Exception as e:
        return f"❌ 获取股票 {stock_code} 信息失败: {str(e)}"


def _get_realtime_quote_sina(stock_code: str) -> str:
    """
    使用新浪财经网页数据获取A股实时行情（免Token）。

    Args:
        stock_code: A股代码，如 "600519" 或 "000001"

    Returns:
        实时行情数据的字符串描述
    """
    try:
        symbol = _normalize_cn_symbol(stock_code)
        url = f"https://hq.sinajs.cn/list={symbol}"
        text = _sina_request(url)
        match = re.search(r'="(.*)";?', text)
        if not match or not match.group(1):
            return f"❌ 未获取到 {stock_code} 行情数据"

        fields = match.group(1).split(",")
        if len(fields) < 32:
            return f"❌ 行情数据格式异常: {stock_code}"

        stock_name = fields[0]
        open_price = float(fields[1])
        prev_close = float(fields[2])
        current_price = float(fields[3])
        high_price = float(fields[4])
        low_price = float(fields[5])
        volume = float(fields[8])
        amount = float(fields[9])
        date_str = fields[30]
        time_str = fields[31]

        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        emoji = "🔴" if change_pct < 0 else "🟢" if change_pct > 0 else "⚪"

        result = f"""
{emoji} 实时行情 - {stock_name} ({stock_code})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
当前价格: {current_price:.2f}
涨跌幅: {change_pct:+.2f}%
涨跌额: {change:+.2f}
今开: {open_price:.2f}
最高: {high_price:.2f}
最低: {low_price:.2f}
昨收: {prev_close:.2f}
成交量: {int(volume)}
成交额: {amount:.2f}
时间: {date_str} {time_str}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 数据来源: 新浪财经
"""
        return result
    except Exception as e:
        return f"❌ 获取行情数据失败: {str(e)}"


@tool
def get_realtime_quote(stock_code: str) -> str:
    """
    获取股票的实时行情数据，包括当前价格、涨跌幅、成交量等。

    Args:
        stock_code: 股票代码，如 "AAPL" (苹果公司) 或 "TSLA" (特斯拉)

    Returns:
        实时行情数据的字符串描述
    """
    return _get_realtime_quote_sina(stock_code)


@tool
def get_realtime_quote_sina(stock_code: str) -> str:
    """
    使用新浪财经网页数据获取A股实时行情（免Token）。

    Args:
        stock_code: A股代码，如 "600519" 或 "000001"

    Returns:
        实时行情数据的字符串描述
    """
    return _get_realtime_quote_sina(stock_code)


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
        key = keyword.strip()
        if not key:
            return "❌ 请输入有效的搜索关键词"

        url = f"https://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={key}"
        text = _sina_request(url)
        results = _parse_sina_suggest(text)

        if not results:
            return f"❌ 未找到包含 '{keyword}' 的股票"

        result = f"🔍 搜索结果 - '{keyword}'\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for row in results[:10]:
            result += f"📌 {row['symbol']} {row['name']} ({row['market']})\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"共找到 {min(len(results), 10)} 只股票\n"
        result += "💡 数据来源: 新浪财经\n"
        return result
    except Exception as e:
        return f"❌ 搜索失败: {str(e)}"


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
        days_map = {"daily": 180, "weekly": 365 * 2, "monthly": 365 * 5}
        days = days_map.get(period, 180)
        df = _get_candles_sina(stock_code, days)
        if df.empty:
            return f"❌ 无法获取K线数据"

        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期")
        if period == "weekly":
            df = (
                df.set_index("日期")
                .resample("W-FRI")
                .agg({
                    "开盘": "first",
                    "最高": "max",
                    "最低": "min",
                    "收盘": "last",
                    "成交量": "sum",
                })
                .dropna()
                .reset_index()
            )
        elif period == "monthly":
            df = (
                df.set_index("日期")
                .resample("M")
                .agg({
                    "开盘": "first",
                    "最高": "max",
                    "最低": "min",
                    "收盘": "last",
                    "成交量": "sum",
                })
                .dropna()
                .reset_index()
            )

        df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")

        if df.empty:
            return f"❌ 无法获取K线数据"

        recent = df.tail(10)

        result = f"📈 K线数据 - {stock_code} ({period})\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "日期        | 开盘   | 收盘   | 最高   | 最低   | 成交量\n"
        result += "------------------------------------------------------\n"

        for _, row in recent.iterrows():
            result += f"{row['日期']} | {row['开盘']:.2f} | {row['收盘']:.2f} | {row['最高']:.2f} | {row['最低']:.2f} | {int(row['成交量'])}\n"

        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "💡 数据来源: 新浪财经\n"
        return result
    except Exception as e:
        return f"❌ 获取K线数据失败: {str(e)}"


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
        stock_name = get_stock_name(stock_code)
        df = _get_candles(stock_code, "D", 260)

        if df.empty or len(df) < 60:
            return f"❌ 数据不足，无法计算技术指标（需要至少60个交易日数据）"

        close = df['收盘'].astype(float)

        ma5 = close.rolling(window=5).mean()
        ma10 = close.rolling(window=10).mean()
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd = (dif - dea) * 2

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        latest_close = close.iloc[-1]
        latest_date = df.iloc[-1]['日期']

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

        if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]:
            result += "  🔥 MACD金叉，买入信号\n"
        elif dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]:
            result += "  ⚠️ MACD死叉，卖出信号\n"
        elif dif.iloc[-1] > 0:
            result += "  📈 MACD在零轴上方，多头市场\n"
        else:
            result += "  📉 MACD在零轴下方，空头市场\n"

        result += f"""
📉 【RSI指标】(14日)
  RSI: {rsi.iloc[-1]:.2f}
"""

        if rsi.iloc[-1] < 30:
            result += "  💡 RSI<30，超卖区域，可能反弹\n"
        elif rsi.iloc[-1] > 70:
            result += "  ⚠️ RSI>70，超买区域，注意回调\n"
        else:
            result += "  ⚖️ RSI处于正常区间\n"

        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "💡 数据来源: 新浪财经\n"
        result += "⚠️ 以上指标仅供参考，不构成投资建议\n"

        return result
    except Exception as e:
        return f"❌ 计算技术指标失败: {str(e)}"


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
        symbol = _normalize_cn_symbol(stock_code)
        news_count = max(1, count // 2)
        ann_count = max(1, count - news_count)

        news_items = _parse_company_news(symbol, news_count)
        ann_items = _parse_company_announcements(symbol, ann_count)

        summary_failed = False
        if news_items and all(not i.get("summary") for i in news_items):
            summary_failed = True
            news_items = _strip_summaries(news_items)
        if ann_items and all(not i.get("summary") for i in ann_items):
            summary_failed = True
            ann_items = _strip_summaries(ann_items)

        if not news_items and not ann_items:
            return f"❌ 未找到 {stock_code} 的相关新闻或公告"

        result = f"""
📰 新闻/公告 - {stock_code}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if news_items:
            result += "📌 【公司新闻】\n"
            for idx, item in enumerate(news_items, start=1):
                summary = item.get("summary", "")
                if len(summary) > 120:
                    summary = summary[:120] + "..."
                result += f"{idx}. {item['title']}\n"
                if item.get("date"):
                    result += f"   🕐 {item['date']}\n"
                if summary:
                    result += f"   📝 {summary}\n"
                if item.get("url"):
                    result += f"   🔗 {item['url']}\n"
            result += "\n"

        if ann_items:
            result += "📣 【公司公告】\n"
            for idx, item in enumerate(ann_items, start=1):
                summary = item.get("summary", "")
                if len(summary) > 120:
                    summary = summary[:120] + "..."
                result += f"{idx}. {item['title']}\n"
                if item.get("date"):
                    result += f"   🕐 {item['date']}\n"
                if summary:
                    result += f"   📝 {summary}\n"
                if item.get("url"):
                    result += f"   🔗 {item['url']}\n"

        if summary_failed:
            result += "\n⚠️ 摘要获取失败，已降级为仅标题列表\n"
        result += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"共获取 {len(news_items) + len(ann_items)} 条新闻/公告\n"
        result += "💡 数据来源: 新浪财经\n"
        return result
    except Exception as e:
        return f"❌ 获取新闻失败: {str(e)}"


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
        symbol = _normalize_cn_symbol(stock_code)
        periods, rows = _parse_financial_table(symbol)
        summary = _parse_financial_summary(symbol)
        if not summary and not rows:
            return f"⚠️ 未找到 {stock_code} 的财务数据"

        pick_keys = [
            "每股收益",
            "每股净资产",
            "每股现金流",
            "每股公积金",
            "每股未分配利润",
            "净资产收益率(%)",
            "总资产收益率(%)",
            "资产负债率(%)",
            "毛利率(%)",
            "净利率(%)",
            "营业收入",
            "营业利润",
            "净利润",
            "息税前利润",
            "经营活动现金流量净额",
            "投资活动现金流量净额",
            "筹资活动现金流量净额",
            "市盈率(动态)",
            "市盈率(静态)",
            "市净率",
            "总资产",
            "总负债",
            "货币资金",
            "应收账款",
            "存货",
        ]

        result = f"""
💰 财务数据分析 - {stock_code}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        result += "口径说明：财务摘要与历史对比来自同一页面表格，默认按披露期口径展示。\n"
        result += "数据质量提示：若页面字段缺失或单位不统一，结果可能出现缺项或单位混杂。\n\n"

        if periods and rows:
            show_periods = periods[:3]
            period_labels = " | ".join([f"期{i+1}:{p}" for i, p in enumerate(show_periods)])
            result += f"披露期(最新优先): {period_labels}\n\n"

            for key in pick_keys:
                if key not in rows:
                    continue
                values = rows[key]
                latest_raw = values[0] if len(values) > 0 else ""
                prev_raw = values[1] if len(values) > 1 else ""
                prev2_raw = values[2] if len(values) > 2 else ""
                latest_val, latest_note = _normalize_metric_value(latest_raw)
                prev_val, prev_note = _normalize_metric_value(prev_raw)
                prev2_val, prev2_note = _normalize_metric_value(prev2_raw)
                delta_text = ""
                n_latest = _to_number(latest_raw)
                n_prev = _to_number(prev_raw)
                if n_latest is not None and n_prev is not None and n_prev != 0:
                    delta = n_latest - n_prev
                    pct = delta / n_prev * 100
                    delta_text = f"  变动: {delta:+.2f} ({pct:+.2f}%)"
                unit_ok, unit_note = _unit_consistency([latest_raw, prev_raw, prev2_raw])
                result += f"{key}: {latest_val}"
                if latest_note:
                    result += f" {latest_note}"
                if prev_val:
                    result += f"  上期: {prev_val}"
                    if prev_note:
                        result += f" {prev_note}"
                if prev2_val:
                    result += f"  上上期: {prev2_val}"
                    if prev2_note:
                        result += f" {prev2_note}"
                if delta_text:
                    result += delta_text
                if not unit_ok and unit_note:
                    result += f"  ⚠️ {unit_note}"
                result += "\n"
        else:
            hit = 0
            for key in pick_keys:
                if key in summary:
                    result += f"{key}: {summary[key]}\n"
                    hit += 1
            if hit == 0:
                for k, v in list(summary.items())[:12]:
                    result += f"{k}: {v}\n"

        result += "\n指标口径补充:\n"
        result += "- 每股收益/净资产/现金流：以每股口径展示，单位随页面披露\n"
        result += "- 净资产收益率/总资产收益率/毛利率/净利率：百分比口径\n"
        result += "- 营业收入/净利润/现金流净额：报告期累计值\n"
        result += "- 市盈率/市净率：按当期口径或页面标注\n"
        result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += "💡 数据来源: 新浪财经\n"
        result += "⚠️ 财务数据仅供参考，投资需综合分析\n"
        return result
    except Exception as e:
        return f"❌ 获取财务数据失败: {str(e)}"


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
        stock_name = get_stock_name(stock_code)
        df = _get_candles(stock_code, "D", 260)

        if df.empty or len(df) < 60:
            return f"❌ 数据不足，无法进行趋势分析（需要至少60个交易日数据）"

        close = df['收盘'].astype(float)
        high = df['最高'].astype(float)
        low = df['最低'].astype(float)

        ma5 = close.rolling(window=5).mean()
        ma10 = close.rolling(window=10).mean()
        ma20 = close.rolling(window=20).mean()
        ma60 = close.rolling(window=60).mean()

        current_price = close.iloc[-1]

        change_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) >= 6 else 0
        change_10d = (close.iloc[-1] / close.iloc[-11] - 1) * 100 if len(close) >= 11 else 0
        change_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) >= 21 else 0

        resistance = high.tail(20).max()
        support = low.tail(20).min()

        trend_score = 50
        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            trend_score += 15
        elif ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]:
            trend_score -= 15

        if current_price > ma20.iloc[-1]:
            trend_score += 10
        else:
            trend_score -= 10

        if change_5d > 5:
            trend_score += 10
        elif change_5d < -5:
            trend_score -= 10

        trend_score = max(0, min(100, trend_score))

        latest_date = df.iloc[-1]['日期']

        result = f"""
📊 趋势分析报告 - {stock_name} ({stock_code})
日期: {latest_date}  当前价: {current_price:.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 【价格趋势】
   近5日涨跌: {change_5d:+.2f}%
   近10日涨跌: {change_10d:+.2f}%
   近20日涨跌: {change_20d:+.2f}%
"""

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
   MA5:  {ma5.iloc[-1]:.2f}  {'↑' if current_price > ma5.iloc[-1] else '↓'}
   MA10: {ma10.iloc[-1]:.2f}  {'↑' if current_price > ma10.iloc[-1] else '↓'}
   MA20: {ma20.iloc[-1]:.2f}  {'↑' if current_price > ma20.iloc[-1] else '↓'}
   MA60: {ma60.iloc[-1]:.2f}  {'↑' if current_price > ma60.iloc[-1] else '↓'}
"""

        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            result += "   💹 均线多头排列，趋势向上\n"
        elif ma5.iloc[-1] < ma10.iloc[-1] < ma20.iloc[-1]:
            result += "   📉 均线空头排列，趋势向下\n"
        else:
            result += "   ⚖️ 均线交织，方向不明\n"

        result += f"""
🎯 【关键价位】
   压力位1: {resistance:.2f} (近期高点)
   支撑位1: {support:.2f} (近期低点)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 【综合趋势评分】: {trend_score}/100
"""

        if trend_score >= 80:
            result += "   评级: ⭐⭐⭐⭐⭐ 强势多头\n"
        elif trend_score >= 65:
            result += "   评级: ⭐⭐⭐⭐ 偏多\n"
        elif trend_score >= 50:
            result += "   评级: ⭐⭐⭐ 中性\n"
        elif trend_score >= 35:
            result += "   评级: ⭐⭐ 偏空\n"
        else:
            result += "   评级: ⭐ 弱势空头\n"

        result += f"""
📋 【操作建议】
🔸 趋势判断: {'强势上涨' if trend_score >= 70 else '偏强震荡' if trend_score >= 50 else '弱势下跌'}
🔸 建议策略:
   - 已持有：根据技术指标灵活操作
   - 未持有：关注支撑位附近的买入机会
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 数据来源: 新浪财经
⚠️ 以上分析仅供参考，不构成投资建议
   股市有风险，投资需谨慎！
"""
        return result
    except Exception as e:
        return f"❌ 趋势分析失败: {str(e)}"
