# 第 2 章 · 最小 Agent · 知识要点

## 核心：Agent Loop 5 步往返

理解了下面这 5 步，就理解了所有 agent 的本质：

```
   你的代码                          模型 (Claude via OpenAI-compat)
      │                                    │
      │ ①【第1次请求】问题 + 工具清单 ──────→│
      │                                    │ 思考：得调工具
      │←──────── ② "我要调 read_file" ──────│  finish_reason=tool_calls
      │            (附带 tool_call_id)      │
      │                                    │
      │ ③ 本地执行 read_file()             │
      │    拿到文件内容                     │
      │                                    │
      │ ④ 把结果包成 role:"tool" 消息       │
      │   (带上同一个 tool_call_id 配对)    │
      │                                    │
      │ ⑤【第2次请求】带着结果再问 ─────────→│
      │                                    │ 基于内容回答
      │←──────────── 最终答案 ─────────────│  finish_reason=stop
```

**关键认知**：模型自己不执行任何代码。它只会"请求"调用工具，**真正干活的是你的 Python**。执行权始终在你手里——这就是 agent 既强大又可控的根本原因。

---

## 1. `finish_reason` 三种取值

| 值 | 含义 | 你该做什么 |
|----|------|----------|
| `stop` | 模型正常说完话 | 结束循环 |
| `tool_calls` | 模型要求调用工具 | 执行工具、把结果喂回、再请求 |
| `length` | 输出达到 max_tokens 上限 | 增大 max_tokens 或分段处理 |

---

## 2. `tool_call_id` 配对机制

模型每次工具请求带一个 `id`，你喂回结果时**必须带上同一个 id**：

```python
# 模型请求
tc.id = "call_abc123"
tc.function.name = "read_file"

# 你喂回
{"role": "tool", "tool_call_id": "call_abc123", "content": "..."}
```

**为什么要配对**：一次模型响应可能并行返回多个 `tool_calls`，没有 id 配对模型不知道哪个结果对应哪次调用。

---

## 3. 工具的「三段式」组织（工业级标准）

```
① 真身（Python 函数）  read_file()  write_file()  list_dir()
② 说明书（schema 列表） TOOLS = [{...}, {...}, {...}]
③ 派发表（名字→函数）   TOOL_FUNCTIONS = {"read_file": read_file, ...}
                                  ↓
                            run_tool(name, args)
```

后面 LangChain、Claude Agent SDK 本质都是这个结构的封装。

---

## 4. Agent Loop 的 4 个关键设计

```python
for round_idx in range(MAX_ITERATIONS):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=history,
        tools=TOOLS,
        temperature=0,              # ② 决策稳定
    )
    history.append(resp.choices[0].message)
    if resp.choices[0].finish_reason != "tool_calls":
        break                       # 模型说完了
    for tc in msg.tool_calls:       # ③ 并行工具调用天然支持
        result = run_tool(tc.function.name, json.loads(tc.function.arguments))
        history.append({"role": "tool", "tool_call_id": tc.id, "content": result})
```

| 设计 | 为什么 |
|------|--------|
| ① `MAX_ITERATIONS` 兜底 | 防无限循环。生产里通常 20–50 |
| ② `temperature=0` | Agent 决策要稳定，不要创造性 |
| ③ 遍历 `tool_calls` 列表 | 模型可能一次返回多个工具调用（并行） |
| ④ system prompt 引导 | 没它 agent 会瞎猜文件名、不会停 |

---

## 5. 路径安全：`_safe_path`

```python
def _safe_path(path: str) -> Path:
    target = (BASE_DIR / path).resolve()
    if not target.is_relative_to(BASE_DIR):
        raise ValueError(f"路径越界：{path}")
    return target
```

**Agent 安全的第一课**：给工具划边界，模型再聪明也跳不出去。第 9 章会系统讲。

---

## 6. 深度知识：function calling 为什么这么稳？

### 原生 vs Prompt-based：机制相似，效果差距巨大

| 维度 | 原生 function calling | Prompt-based |
|------|----------------------|--------------|
| 格式可靠性 | API 层保证结构化 `tool_calls` | 自由文本，可能多解释、漏引号 |
| 参数类型 | JSON Schema 强约束 | 全靠 prompt 描述 |
| 训练对齐 | 见过几百万样本，"母语" | 临时学，"外语" |
| 并行调用 | 原生支持 | 自己设计协议 |

### 三层保障（从软到硬）

```
第 3 层（最硬）│ 约束解码 (Constrained Decoding)  │  强制正确
第 2 层（中）  │ 特殊 token + 训练对齐            │  模型"学过"
第 1 层（最软）│ JSON Schema 注入到 prompt        │  告诉规则
```

### 约束解码：核心机制

在「概率分布 → 采样」之间硬塞过滤——把所有违反 schema 的 token 概率改成 `-∞`。

```
模型给词表算分：     [{, 今天, path, name, hello, ...]
原始概率：           [0.5, 0.01, 0.4,  0.005, 0.001, ...]
                            ↓
【schema 状态机】当前位置只允许 "{"
                            ↓
非法 token 概率改 -∞：[0.5, -∞,   -∞,   -∞,    -∞,    ...]
归一化后采样：       100% 抽到 "{"
```

**机制**：把 JSON Schema 编译成有限状态机，每步采样时过滤掉违反规则的 token。模型连"想错"的机会都没有。

主流实现：Outlines / llguidance / xgrammar / vLLM / SGLang / OpenAI Structured Outputs。

---

## 7. LLM 工作原理（4 个最小概念）

理解约束解码、temperature 所需的全部 LLM 知识：

```
概念 1：LLM 一次只生成一个 token（不是一段话）
概念 2：词表是固定的有限集合（约 10 万个 token）
概念 3：模型输出的是"下一个 token 的概率分布"（logits → softmax）
概念 4：采样 = 按概率"抽奖"（temperature 控制抽奖的偏向）
```

**够用就行**——agent 是工程领域，深入算法不需要。

---

## 8. Temperature 实践指南

```
T = 0     │ 永远选最高分 token（确定性）
T = 0.1   │ 99% 选最高分（高度稳定）
T = 1.0   │ 默认，按原概率采样
T = 2.0   │ 概率分布被压扁，更随机
```

**Agent 场景必备**：

| 场景 | 推荐 T |
|------|--------|
| Agent 工具调用 | **0 ~ 0.2** ★ |
| 代码生成 | 0 ~ 0.3 |
| 事实问答 / RAG | 0 ~ 0.3 |
| 创意写作 | 0.7 ~ 1.0 |
| 头脑风暴 | 1.0 ~ 1.5 |

**别同时调 temperature 和 top_p**——互相干扰难调试。

---

## 9. 自检清单

- [ ] 能逐句解释 step3 的 agent loop 在干什么
- [ ] 能说出 `finish_reason` 三种取值的含义
- [ ] 能解释 `tool_calls` 与 `role:"tool"` 消息如何通过 `tool_call_id` 配对
- [ ] 知道为什么 agent 决策要 `temperature=0`
- [ ] 能说出工具「三段式」组织各自的作用
- [ ] 理解约束解码"在解码层硬约束格式"的核心思想

---

## 10. 本章产出

- `shared/client.py` —— 统一的 LLM 客户端
- `chapter_02_minimal_agent/step0_ping.py` —— 连通性 + function calling 能力预检
- `chapter_02_minimal_agent/step1_no_tools.py` —— 伪 agent（对照组）
- `chapter_02_minimal_agent/step2_single_tool.py` —— 手动走完一次工具调用
- `chapter_02_minimal_agent/step3_agent_loop.py` —— 完整 agent 循环
- `chapter_02_minimal_agent/tools.py` —— 工具集（三段式组织 + 路径安全）

**典型运行轨迹**（4 轮完成任务）：
```
第1轮: list_dir          → 探目录
第2轮: read×3 (并行)      → 并行读取所有文件
第3轮: write_file        → 写入汇总
第4轮: finish_reason=stop → 一句话收尾
```


---

◀ 上一章：[第 1 章 · 认知地基](../chapter_01_concepts/NOTES.md)
▶ 下一章：[第 3 章 · 工具与记忆](../chapter_03_tools_memory/NOTES.md)

🏠 [回到课程首页](../README.md)
