"""
炒股高手 AI 智能体 - 主程序入口
基于 LangChain 构建的股票分析 Agent
"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# 导入配置
from config import API_KEY, BASE_URL, MODEL_NAME, TEMPERATURE

# 导入工具
from tools.stock_data import get_stock_info, get_realtime_quote, search_stock, get_kline_data, calculate_indicators, get_stock_news, get_financial_data, analyze_trend

# 导入提示词
from prompts.system import STOCK_AGENT_PROMPT


def create_stock_agent():
    """创建炒股高手 AI 智能体"""

    # 1. 初始化 LLM (使用阿里云百炼 API)
    llm = ChatOpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL_NAME,
        temperature=TEMPERATURE,
    )

    # 2. 定义工具列表
    tools = [
        get_stock_info,
        get_realtime_quote,
        search_stock,
        get_kline_data,
        calculate_indicators,
        get_stock_news,
        get_financial_data,
        analyze_trend,
    ]

    # 3. 使用 LangGraph 创建 ReAct Agent
    agent = create_react_agent(
        model=llm,
        tools=tools,
    )

    return agent


def chat_with_agent():
    """与炒股高手 AI 交互的主循环"""

    print("=" * 60)
    print("🤖 炒股高手 AI 智能体 v1.0")
    print("=" * 60)
    print("欢迎使用！我是您的专属股票分析助手。")
    print("您可以问我：")
    print("  - 查询股票行情：'帮我查一下贵州茅台的实时行情'")
    print("  - 搜索股票：'搜索一下银行股'")
    print("  - 股票分析：'分析一下000001平安银行'")
    print("  - 输入 'quit' 或 'exit' 退出程序")
    print("=" * 60)

    # 创建 Agent
    agent = create_stock_agent()

    # 对话历史
    chat_history = []

    while True:
        try:
            # 获取用户输入
            user_input = input("\n👤 您: ").strip()

            # 退出检测
            if user_input.lower() in ['quit', 'exit', 'q', '退出']:
                print("\n👋 感谢使用，祝您投资顺利！")
                break

            if not user_input:
                continue

            print("\n🤖 AI助手思考中...\n")

            # 构建消息，包含系统提示词
            messages = [SystemMessage(content=STOCK_AGENT_PROMPT)] + chat_history + [HumanMessage(content=user_input)]

            # 调用 Agent
            result = agent.invoke({"messages": messages})

            # 获取最后的 AI 回复
            ai_message = result["messages"][-1]
            output = ai_message.content

            # 输出结果
            print(f"\n🤖 AI助手: {output}")

            # 更新对话历史
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=output))

        except KeyboardInterrupt:
            print("\n\n👋 程序已中断，再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生错误: {str(e)}")
            print("请重试或换一个问题。")


if __name__ == "__main__":
    chat_with_agent()
