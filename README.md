# Agent Cookbook

从零开始，动手构建 AI Agent 的 10 章实践课。

面向**有 Python 基础的非程序员**（产品、运营、研究方向），目标是「能跟工程师讨论 agent 项目，能判断 agent 可行性」，而不是变成全职工程师。

---

## 课程地图

| 章节 | 主题 | 核心问题 | 项目产出 |
|------|------|---------|---------|
| 第 1 章 | 认知地基 | Agent 和 Workflow 的本质区别是什么？ | — |
| 第 2 章 | 最小 Agent | 从零手写一个 ReAct Agent 循环 | `step0` → `step3` 四步拆解 |
| 第 3 章 | 工具与记忆 | Agent 怎么记住上下文、调用多工具？ | 带持久记忆的文件管理 Agent |
| 第 4 章 | 规划与反思 | Agent 怎么自我检查、纠错重来？ | Plan-and-Execute + Reflection Agent |
| 第 5 章 | RAG | Agent 怎么从私有文档里找答案？ | 本地知识库问答 Agent（ChromaDB） |
| 第 6 章 | LangGraph | 用图来描述 Agent 流程有什么优势？ | ReAct Agent + 对话检查点 |
| 第 7 章 | 多 Agent | 什么时候需要多个 Agent 协作？ | Orchestrator-Worker 并行研究 Agent |
| 第 8 章 | 评估 | 怎么科学说"我的 Agent 比上一版好 15%"？ | 三层评估脚本（Unit / E2E / 综合） |
| 第 9 章 | 生产化 | 怎么把 Agent 脚本变成别人能用的服务？ | FastAPI HTTP 服务 + 安全分级 |
| 第 10 章 | 综合项目 | 独立完成一个完整的 Agent 产品周期 | 达人投放分析 Agent（DTC 美妆） |

---

## 快速开始

### 1. 安装依赖

本项目使用 [uv](https://docs.astral.sh/uv/)（比 pip 快 10 倍的包管理器）。

```bash
# 安装 uv（如果还没装）
pip install uv

# 安装项目依赖
uv sync
```

### 2. 配置 API Key

```bash
# 复制配置模板
cp .env.example .env
```

打开 `.env`，填入你的 API Key 和接口地址：

```
OPENAI_API_KEY=sk-xxxxxxxx        # 你的 API Key
OPENAI_BASE_URL=https://...       # 接口地址（支持 OpenAI 兼容格式）
MODEL=claude-sonnet-4-6           # 模型名称
```

### 3. 跑第一个代码

验证配置是否正确：

```bash
uv run python chapter_02_minimal_agent/step0_ping.py
```

看到模型回复说明环境 OK，然后按章节顺序走。

---

## 章节导读

### 第 1 章：认知地基

无代码。建立核心心智模型：三问决策树（什么时候该用 Agent）、三大支柱（工具 / 循环 / LLM 决策）、四大架构（ReAct / Plan-Execute / Reflection / Multi-Agent）。

> 读完 NOTES.md 就算完成本章。

### 第 2 章：最小 Agent

用 400 行代码，把 Agent 从零拆成四步：

```
step0_ping.py        → 验证 API 连通
step1_no_tools.py    → 普通对话（无工具）
step2_single_tool.py → 单次工具调用
step3_agent_loop.py  → 完整 ReAct 循环（真正的 Agent）
```

```bash
uv run python chapter_02_minimal_agent/step3_agent_loop.py
```

### 第 3 章：工具与记忆

```bash
uv run python chapter_03_tools_memory/agent.py
```

### 第 4 章：规划与反思

```bash
uv run python chapter_04_planning_reflection/agent.py
```

### 第 5 章：RAG

先建索引，再运行 Agent：

```bash
uv run python chapter_05_rag/indexer.py       # 建本地向量库
uv run python chapter_05_rag/agent.py         # 启动问答 Agent
```

### 第 6 章：LangGraph

```bash
uv run python chapter_06_langchain/react_agent.py
uv run python chapter_06_langchain/checkpoint_demo.py   # 对话记忆
```

### 第 7 章：多 Agent

```bash
uv run python chapter_07_multi_agent/research_agent.py
```

### 第 8 章：评估

```bash
uv run python chapter_08_evaluation/eval_rag_agent.py
```

输出：工具准确率 / 答案质量 / 整体成功率 / 失败 case 列表。

### 第 9 章：生产化

```bash
uv run uvicorn chapter_09_production.server:app --port 8000 --reload
```

然后访问 `http://localhost:8000/docs` 查看 API 文档。

### 第 10 章：综合项目（毕业作品）

DTC 美妆品牌 · 达人投放分析 Agent：

```bash
uv run python chapter_10_capstone/generate_data.py   # 生成演示数据
uv run python chapter_10_capstone/agent.py           # 启动分析 Agent
uv run python chapter_10_capstone/eval_runner.py     # 运行评估
```

---

## 项目结构

```
learn_agent/
├── shared/              # 各章复用的基础模块（client / memory / embeddings）
├── chapter_01_concepts/
├── chapter_02_minimal_agent/
├── chapter_03_tools_memory/
├── chapter_04_planning_reflection/
├── chapter_05_rag/
├── chapter_06_langchain/
├── chapter_07_multi_agent/
├── chapter_08_evaluation/
├── chapter_09_production/
├── chapter_10_capstone/
├── .env.example         # 配置模板
└── pyproject.toml       # 依赖声明
```

每章都有 `NOTES.md`，记录核心概念、关键决策和学习心得。

---

## 依赖说明

| 依赖 | 用途 |
|------|------|
| `openai` | Claude / OpenAI API 调用 |
| `chromadb` | 本地向量数据库（第 5 章 RAG） |
| `langchain-core` + `langchain-openai` | LangChain 基础组件（第 6-7 章） |
| `langgraph` | Agent 图编排框架（第 6-10 章） |
| `fastapi` + `uvicorn` | HTTP 服务（第 9 章） |
| `python-dotenv` | 读取 `.env` 配置 |
