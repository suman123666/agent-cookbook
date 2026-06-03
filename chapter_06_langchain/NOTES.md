# 第 6 章 · 框架进阶 LangChain + LangGraph · 知识要点

## 本章定位

前 5 章手写 agent（纯 SDK），本章学工业级框架。
**先手写再学框架**，框架才透明——你能预测它在干什么，不被"黑魔法"困住。

> ⚠️ 自评状态：概念理解到位，但尚未独立编码。后续需通过动手强化（见约定）。

---

# 🧩 6.1 LangChain 核心抽象

## 设计哲学

把 LLM 应用的"标准件"（模型/Prompt/Parser/Tool/Retriever）统一接口，像乐高拼装。

## 核心概念

### Runnable —— 一个"约定"（接口/协议）

```
只要实现 5 个方法（invoke/batch/stream/ainvoke/abatch），就是 Runnable
类比：Python 的 Iterable —— 实现 __iter__ 就能被 for 遍历
```

所有组件（ChatModel/Prompt/Parser/Tool/Retriever）都是 Runnable，所以能：
- 统一调用（都用 .invoke）
- 用 `|` 拼装
- 自动获得 4 种调用方式

### LCEL —— 用 `|` 拼装 Runnable

```python
chain = prompt | model | parser
# 写完自动获得：invoke / stream / batch / async 4 种调用
```

### ChatModel —— 模型统一抽象

```python
ChatOpenAI() / ChatAnthropic() / ChatOllama()  # 接口一致
# 换模型不改业务代码（核心价值）
```

中转渠道：`ChatOpenAI(base_url=..., api_key=...)` 走 OpenAI 兼容接口。

### PromptTemplate —— prompt 变对象

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}"),
    ("user", "{question}"),
])
```

价值：prompt 是对象 → 可复用、可持久化、可 A/B test（不是硬编码 f-string）。

### Tool —— @tool 装饰器

```python
@tool
def search(query: str) -> str:
    """工具描述（自动从 docstring + 类型注解生成 schema）"""
    ...
model.bind_tools([search])  # 绑定给模型
```

省去手写 `{"type":"function", "function":{...}}` 一大坨 schema。

## 5 个反模式

```
1. 过度抽象（5 层 RunnableLambda 包一行逻辑）
2. 滥用 chain（简单 if/else 硬塞 RunnableBranch）
3. 不理解就用（copy 文档示例，出错无从下手）
4. 忽视版本（0.1→0.2→0.3 API 大改，认准最新文档）
5. 所有项目都用（简单脚本用裸 SDK 更稳）
```

**核心态度**：能不用 LangChain 就别用，30 行手写循环往往更可控。学它是因为 LangGraph 依赖它 + 行业标准。

---

# 🔧 6.2 LangGraph —— 真正核心

## 思想：从「循环」到「状态机」

```
手写版：你「亲手开车」—— 自己写 for/if/break/append
LangGraph：你「画地图 + 设规则」—— 框架按图自己开
```

**关键区分（最容易卡住的点）**：

```
手写代码：   从上往下读 = 执行顺序     （命令式）
LangGraph： 从上往下读 ≠ 执行顺序     （声明式）
   - 定义阶段：写 node/edge/图（不执行业务）
   - 执行阶段：agent.stream() 才真正按图跑
```

## 4 个核心概念

| 概念 | 是什么 | 对照手写版 |
|------|--------|-----------|
| **State** | 流动的数据（dict） | history 列表 |
| **Node** | 函数：读 state → 返回更新 | 循环体里的一段 |
| **Edge** | 节点连接 | 控制流 |
| **Conditional Edge** | 按 state 决定走哪 | `if finish_reason...` |

## State + Reducer（核心中的核心）

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
              └─ 类型     └─ reducer：更新时「追加」而非「覆盖」
```

- `TypedDict`：state 是带类型的字典
- `Annotated[类型, 元数据]`：给字段贴"便利贴"，LangGraph 读元数据
- `add_messages`：reducer，决定新旧值怎么合并（追加）

**没 reducer = 覆盖**（agent 失忆）；**add_messages = 追加**（= 手写版 `history.append()`）。

证据：跑 react_agent 看到"messages 数 2→4→8 一路涨"，就是 add_messages 在追加。

节点只返回**增量**：`return {"messages": [new_msg]}`，reducer 负责合并。

## 执行模型：super-step（来自 Pregel/BSP）

```
super-step = 图执行的"一轮"
  ① 计算：本轮节点并行执行（线性图里就 1 个）
  ② 路由：评估出边，决定下一轮（should_continue 在这）
  ③ 同步屏障：等全跑完，更新 state，yield event

线性 ReAct 图：每个 super-step 1 个节点（感受不到 super）
并行多 agent：一个 super-step 跑多个节点（第 7 章见威力）
```

**为什么 `🟦🔶` 打印在 `【原始 event】` 之前**：
节点(🟦)和路由(🔶)是 super-step 内部执行的，event 是屏障后才 yield 的。
→ 铁证：`for event in stream()` 是「观察者」，不是「驱动者」。

## stream vs invoke

```
agent.invoke(state)  → 闷头跑完，返回最终 state（看不到中间）
agent.stream(state)  → 每个 super-step 屏障处 yield 一个 event（能观察每步）

event = {节点名: 该节点的 state 更新}   一个字典
event.items() → (node_name, state_update)
recursion_limit → 限制循环次数（= 手写版 MAX_ITERATIONS）
```

## 手写版 ↔ LangGraph 对照表

| 手写 agent loop | LangGraph |
|----------------|-----------|
| `for round in range(MAX)` | `add_edge("tools","llm")` 回头边造成循环 |
| `resp = create(...)` | `call_llm` 节点 |
| `if finish != "tool_calls": break` | `should_continue` 返回 END |
| `for tc in tool_calls` | `call_tools` 节点 |
| `history.append()` | `add_messages` reducer |
| `MAX_ITERATIONS` | `recursion_limit` |
| `if resp.finish_reason == "tool_calls"` | `if hasattr(msg,"tool_calls") and msg.tool_calls` |

## LangGraph 的杀手锏（手写难做的）

### Checkpoint —— 状态持久化 + 断点续跑

```python
agent = graph.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "demo-1"}}
agent.invoke(state, config)   # 每个 super-step 边界自动存 state
```

### Human-in-the-loop —— interrupt 审批

```python
agent = graph.compile(checkpointer=..., interrupt_before=["tools"])
agent.invoke(initial, config)         # 跑到 tools 前暂停
snapshot = agent.get_state(config)    # snapshot.next = 待执行节点；为空=完成
agent.invoke(None, config)            # 传 None = 从断点恢复
```

这是 Claude Code "危险命令需确认" 的底层机制。

### 何时该用 LangGraph

```
✅ 循环类 agent / Checkpoint / human-in-the-loop / 多 agent / 要可视化
❌ 单次调用 / 纯线性 chain（用 LCEL）/ 个人小脚本（手写更直接）
```

---

# 🎯 关键认知

```
1. Runnable = 统一接口约定，让组件能拼装（类比 Iterable）
2. LCEL `|` = 拼装 Runnable，自动获得 4 种调用
3. LangGraph = 把 agent 从「循环+条件」翻译成「状态机/图」
4. State + Reducer = 状态显式化，add_messages 自动追加消息
5. super-step = 一轮图执行，event 在屏障后 yield
6. stream 的 for = 观察者，不是驱动者（🟦🔶 在 event 前为证）
7. Checkpoint + interrupt = 断点续跑/人工审批（手写难做的核心价值）
```

---

# ✅ 自检清单

- [ ] Runnable 为什么能让组件用 `|` 拼装？
- [ ] LangGraph 代码"从上往下读 ≠ 执行顺序"，为什么？
- [ ] `Annotated[list, add_messages]` 三部分各是什么？没有 reducer 会怎样？
- [ ] super-step 是什么？为什么 🟦🔶 打印在 event 之前？
- [ ] `for event in agent.stream()` 是驱动还是观察 agent？
- [ ] Checkpoint + interrupt_before 能实现什么？invoke(None) 是什么意思？

---

# 🎓 本章产出

- `chapter_06_langchain/basic_demo.py` —— LangChain 4 step 递进（ChatModel/Prompt/LCEL/换模型）
- `chapter_06_langchain/react_agent.py` —— 用 LangGraph 重写第 2 章 agent（带执行追踪打印）
- `chapter_06_langchain/checkpoint_demo.py` —— Checkpoint + human-in-the-loop 审批

# 📌 待强化（约定）

- LangGraph 目前是"读懂"，未"独立写"
- 后续章节穿插「30 秒小动作」保持手感
- 第 10 章综合项目务必用户主导编码（老师当教练）


---

◀ 上一章：[第 5 章 · RAG 与知识增强](../chapter_05_rag/NOTES.md)
▶ 下一章：[第 7 章 · 多 Agent 系统](../chapter_07_multi_agent/NOTES.md)

🏠 [回到课程首页](../README.md)
