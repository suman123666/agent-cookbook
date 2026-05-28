"""LangChain 核心抽象的可运行示例（4 step 递进）。

跟我们前 5 章的"手写 agent"对照看，能直观理解每个概念。

运行：uv run python chapter_06_langchain/basic_demo.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import MODEL  # 沿用前几章的模型配置  # noqa: E402

from langchain_openai import ChatOpenAI  # noqa: E402
from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402

# 通过 base_url 走中转渠道（跟我们的 .env 配置共用）
model = ChatOpenAI(
    model=MODEL,
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0,
)


# ═══════════════════════════════════════════════════════════
# STEP 1: 最基础——ChatModel.invoke()
# ═══════════════════════════════════════════════════════════
def step1_chat_model():
    """对照手写版：client.chat.completions.create(messages=...)
    LangChain 版：model.invoke(messages)

    区别：messages 用 LangChain 的消息对象（HumanMessage / SystemMessage），
    返回值是 AIMessage 对象（不是 dict）
    """
    print("\n" + "═" * 60)
    print("STEP 1: ChatModel.invoke() —— 最基础")
    print("═" * 60)

    messages = [
        SystemMessage("你是 Python 教练"),
        HumanMessage("一句话解释什么是装饰器"),
    ]

    response = model.invoke(messages)

    # response 是 AIMessage 对象
    print(f"返回类型: {type(response).__name__}")
    print(f"完整对象: {response!r}")
    print(f".content: {response.content}")


# ═══════════════════════════════════════════════════════════
# STEP 2: 加 PromptTemplate
# ═══════════════════════════════════════════════════════════
def step2_prompt_template():
    """对照手写版：messages = [{"role":"system", "content": f"你是{role}"}, ...]
    LangChain 版：prompt = ChatPromptTemplate.from_messages([...])

    优势：prompt 是个对象，能复用、能 .save() 持久化
    """
    print("\n" + "═" * 60)
    print("STEP 2: PromptTemplate —— prompt 变成对象")
    print("═" * 60)

    # 定义 prompt 模板（变量用 {} 占位）
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}"),
        ("user", "{question}"),
    ])

    print(f"prompt 对象: {type(prompt).__name__}")

    # ★ prompt 本身也是 Runnable，能 .invoke()——这就是 Runnable 的统一性
    rendered = prompt.invoke({"role": "Python 教练", "question": "一句话解释 generator"})
    print(f"\nprompt.invoke() 渲染结果:")
    for msg in rendered.messages:
        print(f"  [{msg.type}] {msg.content}")

    # 再传给 model
    response = model.invoke(rendered)
    print(f"\n模型回复: {response.content}")


# ═══════════════════════════════════════════════════════════
# STEP 3: LCEL 拼装——这是 LangChain 的"灵魂"
# ═══════════════════════════════════════════════════════════
def step3_lcel_chain():
    """对照 STEP 2：手动 model.invoke(prompt.invoke(...))
    LangChain 版：用 `|` 拼装成 chain

    一旦拼成 chain，自动获得 invoke / batch / stream / async 4 种调用方式。
    """
    print("\n" + "═" * 60)
    print("STEP 3: LCEL —— prompt | model | parser")
    print("═" * 60)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是{role}"),
        ("user", "{question}"),
    ])
    parser = StrOutputParser()  # 把 AIMessage 解析成纯字符串

    # ★ 用 | 拼装！chain 本身又是个 Runnable
    chain = prompt | model | parser

    print("chain = prompt | model | parser\n")

    # ── 1. 同步 invoke ───────────────────────────────
    print(">>> chain.invoke(...)")
    result = chain.invoke({"role": "Python 教练", "question": "一句话解释 list comprehension"})
    print(f"    {result}")

    # ── 2. 流式 stream ───────────────────────────────
    print("\n>>> chain.stream(...)  （流式输出，逐字打印）")
    print("    ", end="")
    for chunk in chain.stream({"role": "Python 教练", "question": "一句话解释 lambda"}):
        print(chunk, end="", flush=True)
    print()

    # ── 3. 批量 batch ────────────────────────────────
    print("\n>>> chain.batch([...])  （批量调用）")
    results = chain.batch([
        {"role": "Python 教练", "question": "什么是 yield？一句话"},
        {"role": "数学家", "question": "什么是质数？一句话"},
        {"role": "厨师", "question": "什么是糖醋里脊？一句话"},
    ])
    for i, r in enumerate(results, 1):
        print(f"    [{i}] {r}")

    print("\n💡 注意：以上 3 种调用方式都是 chain 自动获得的——")
    print("   你只写了 `prompt | model | parser`，没写任何流式/批量逻辑。")


# ═══════════════════════════════════════════════════════════
# STEP 4: 替换模型——展示"换模型不改业务"
# ═══════════════════════════════════════════════════════════
def step4_swap_model():
    """同一个 chain，换不同模型，业务代码一行不改。"""
    print("\n" + "═" * 60)
    print("STEP 4: 换模型不改 chain")
    print("═" * 60)

    prompt = ChatPromptTemplate.from_messages([
        ("user", "{question}"),
    ])
    parser = StrOutputParser()

    # 同一个 chain 模板，注入不同 model
    chain_v1 = prompt | model | parser
    # 如果你想换模型，只需要换 model 这个变量——chain 本身不变：
    # chain_v2 = prompt | ChatAnthropic(...) | parser
    # chain_v3 = prompt | ChatOllama(model="llama3") | parser

    print("演示：同一个 chain 表达式，换 model 即可换厂商。")
    print("（这里只跑一次，注释里有换 Claude / Ollama 的写法）\n")

    result = chain_v1.invoke({"question": "一句话推荐一个 Python 库"})
    print(f"模型回复: {result}")


if __name__ == "__main__":
    step1_chat_model()
    step2_prompt_template()
    step3_lcel_chain()
    step4_swap_model()

    print("\n" + "═" * 60)
    print("✅ Demo 完成")
    print("═" * 60)
    print("""
关键认知（对照前 5 章的手写版）：
  1. ChatModel.invoke()   = client.chat.completions.create()
  2. PromptTemplate       = 把 f-string 换成对象，能复用/持久化
  3. LCEL `|` 拼装        = 链式组合，自动获得 stream/batch/async
  4. 换模型一行改          = ChatOpenAI 换 ChatAnthropic，chain 不变

LangChain 的本质：把你已经手写过的"标准件"统一接口（Runnable），
然后用 `|` 拼装——少写胶水代码，但多一层抽象需要适应。
""")
