# shared · 公共模块

各章节复用的基础工具。**不要直接运行这里的文件**，它们是被各章节代码 import 的。

## 模块说明

### `client.py` — 统一 OpenAI 客户端

负责加载 `.env` + 创建 OpenAI 兼容的 LLM 客户端。所有章节调 LLM 都走这里。

```python
from shared.client import get_client, MODEL

client = get_client()
resp = client.chat.completions.create(model=MODEL, messages=[...])
```

读取的环境变量：
- `OPENAI_API_KEY` — API key
- `OPENAI_BASE_URL` — 接口地址
- `MODEL` — 模型名（默认 `claude-sonnet-4-6`）

---

### `memory.py` — 长期记忆（JSON 文件）

把跨会话信息存到项目根目录的 `memory.json`。第 3 章学的"长期记忆"。

```python
from shared.memory import load_memory, save_memory, format_for_prompt

mem = load_memory()                # 读全部
save_memory("user_name", "张三")    # 写一条
prompt_str = format_for_prompt(mem) # 格式化进 system prompt
```

设计原则：每次读写都直接落盘，简单可靠。生产场景请换 Redis/数据库。

---

### `embeddings.py` — Embedding 函数（chromadb 兼容）

走 OpenAI 兼容渠道做文本向量化，符合 chromadb embedding function 协议。第 5 章 RAG 用。

```python
from shared.embeddings import get_embedder

embedder = get_embedder()
vectors = embedder(["文本1", "文本2"])  # → list[list[float]]
```

读取的环境变量：
- `EMBED_MODEL` — embedding 模型名（默认 `text-embedding-3-small`）
- `EMBED_BATCH_SIZE` — 单次最大批量（默认 10，兼容通义/部分中转的限制）

---

## 为什么单独抽出来？

```
1. 复用：第 2-10 章都要用 client / memory / embeddings
2. 集中配置：环境变量只在这里读，其他地方不直接碰 os.environ
3. 隔离测试：渠道换了只改 shared/，章节代码不动
```

这是工程化最基本的「关注点分离」实践。
