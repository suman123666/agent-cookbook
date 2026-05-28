# 第 5 章 · RAG 与知识增强 · 知识要点

## 本章解决什么

前 4 章 agent 只能用「模型脑子里的知识 + system prompt + 工具读硬盘」。
本章给 agent 接上**外脑** —— 私有知识库（笔记、PDF、文档）。

```
直接塞 prompt 不行：单份 PDF 50K token，100 份 = 5M token，远超上限
→ RAG：先「检索相关内容」，再让 LLM「基于内容回答」
```

---

# 📚 5.1 RAG 原理

## 核心：开卷考试模式

```
RAG = Retrieval-Augmented Generation
       检索   +  增强    +  生成

类比：LLM 是考生，向量库是参考书
     别让它凭记忆答题，让它查书答题
```

## 两阶段流程

```
═════════════════════════════════════════════════════
索引阶段（一次性）：
   文档 → Parser → Chunking → Embedding → 向量库
═════════════════════════════════════════════════════

═════════════════════════════════════════════════════
查询阶段（每次）：
   问题 → Embedding → 向量库 top-K → 拼 prompt → LLM 答
═════════════════════════════════════════════════════
```

---

## 概念 1：Embedding

**一句话**：把文本变成数字向量（通常 1024 或 1536 维），语义相似的向量距离近。

```
"我喜欢吃苹果"    → [0.123, -0.456, 0.789, ...]
"我爱吃 apple"    → [0.121, -0.443, 0.781, ...]  (相似)
"今天天气真好"    → [0.789,  0.234, 0.012, ...]  (远)
```

**衡量相似度**：Cosine Similarity（余弦相似度），值 -1 到 1。

```
0.9+      高度相似
0.7~0.9   相关（同一主题）
0.5~0.7   弱相关
< 0.5     不太相关
```

**中文场景的现实**：相似度 0.3-0.6 是常态，0.6+ 就是好结果。**别被"看起来低"吓到**。

---

## 概念 2：Chunking 切块

**为什么必须切**：整本书做一个 embedding，细节全丢；prompt 也塞不下整篇。

### 三种策略

| 策略 | 做法 | 推荐度 |
|------|------|--------|
| **A 固定大小** | 每 500 字一块，重叠 50 | ★★★ 起步首选 |
| **B 语义分块** | 按段落 / Markdown 标题切 | ★★ 进阶 |
| **C 父子分块** | 小 chunk 检索 + 大 chunk 上下文 | ★★★ 进阶 |

### Overlap 为什么必须有

```
没 overlap                    有 overlap
─────────────                ─────────────
"...苹果公司发"               "...苹果公司发布了新产品"
"布了新产品..."               "发布了新产品iPhone..."
  ↑ 切断答案                    ↑ 重叠保证连续
```

**经验值**：chunk_size=500、overlap=50 起步。几乎所有 RAG 都从这个开始。

---

## 概念 3：检索质量评估

```
Recall@K = top-K 里包含正确答案的比例
MRR      = 正确答案在 top-K 里排第几（排越前越好）
```

**核心认知**：

> **Recall@5 < 60% 时，再优化 LLM、prompt 都救不回 RAG。先解决检索问题。**

---

## 进阶概念（预告，本章未实现）

| 技术 | 解决什么 |
|------|---------|
| **Hybrid Search** | 向量检索 + BM25 关键词，弥补精确匹配缺陷 |
| **Reranker** | 二阶段精排，召回 50 → 精排 5 |
| **Query Rewriting** | 把用户问题改写成更利于检索的 query |

---

## 5 个常见 RAG 失败模式

```
1. Chunking 切坏 → 答案被切在两块之间
2. 关键词漏召回 → 人名、产品型号等精确匹配失败
3. Lost in the middle → 召回到但 LLM 没"看到"
4. 答案分散 → 单 chunk 信息不全
5. 文档版本冲突 → 多版本共存导致召回矛盾
```

---

# 🧠 RAG 与 Memory 的关系（核心洞察）

**两者本质上是同一种机制：「外部存储 + 按需取用」**。

## 区别只是侧重点

| 维度 | Memory 倾向 | RAG 倾向 |
|------|------------|----------|
| 关于谁 | 关于"我"（用户档案、偏好） | 关于"世界"（知识、文档） |
| 数据量 | 少（几百） | 多（几千+） |
| 写入 | 用户/agent 滴灌 | 工程师批量导入 |
| 多用户隔离 | 必须 | 通常共享 |
| 写入频率 | 频繁 | 偶尔 |

## 温度谱（统一视角）

```
立即可见         按需检索        永久外部
─────────       ─────────       ─────────
system          热 memory       冷 memory      RAG 知识库
prompt          (注入)          (向量库/文件)   (向量库/文件)
                                  
归属      工程师对所有用户  单用户独享      单用户独享     所有用户共享
更新方        工程师          用户/agent      用户/agent     工程师
检索方式       不检索          不检索         agent 主动查   agent 主动查
```

## Claude Code 的实际架构（活案例）

```
CLAUDE.md（用户级 + 项目级）  → 热 memory
MEMORY.md（auto-memory 索引）  → 热 memory（索引）
memory/*.md（详情文件）        → 冷 memory（文件版，不是向量库！）
```

**反直觉**：Claude Code 的冷 memory 用 **Markdown 文件 + Read 工具**，不用向量库——证明了"冷/热的区别在访问方式，不在存储介质"。

---

# 🛠 5.2 用代码实现 RAG（最简版）

## 文件分工

```
chapter_05_rag/
├── indexer.py        ← 索引器：扫 NOTES.md → chunk → embed → 存 Chroma
├── retriever.py      ← 检索器：query → embed → 查 Chroma → top-K
├── rag_demo.py       ← 纯 RAG 端到端 demo（不带 agent）
└── chroma_db/        ← Chroma 向量库存储目录
```

## 技术栈

- **Chroma**：本地嵌入式向量库（一个目录就是一个 DB）
- **text-embedding-v4**（通义）：走中转渠道的 embedding 模型
- **shared/embeddings.py**：跨章节复用的 embedding 抽象

---

# 🐛 OpenAI 兼容渠道的 5 个坑（实战经验值）

```
1. tool_calls.arguments 多 JSON 拼接   → 用 raw_decode 容错
2. response_format={"json_object"} 不支持
3. tool_choice 可能不支持
4. embeddings batch size 各家不同      → OpenAI 2048 / 通义 10
                                         默认 10 最保险
5. chromadb 的 embed_query 返回值需要
   是 list[list[float]] 而非 list[float]
```

**通用应对**：永远写防御性代码，别假设格式严格符合 OpenAI 规范。

---

# 🤖 5.3 把 RAG 接入 Agent

## 核心设计：让 agent 自主决定何时查

```python
# tools.py - search_knowledge 工具描述里写明：
"""
**何时使用**：用户问 agent 概念、设计、原理、回顾等
**何时不要使用**：闲聊、问候、答案已在历史里
"""
```

**关键认知**：好的 RAG agent 不是"啥都查"，而是"该查才查"。
工具描述里的「反场景」决定了 agent 的克制力。

## 文件分工

```
chapter_05_rag/
├── tools.py     ← search_knowledge 工具 + 工具描述
└── agent.py     ← 交互式 agent loop，复用前几章模式
```

## 验证的两类场景

| 测试类型 | 期望行为 |
|---------|---------|
| 知识题（"agent 三大支柱"）| ✅ 调 search_knowledge，引用来源 |
| 综合题（"我学了什么"）| ✅ 一次 search + top_k=5，综合输出 |
| 闲聊（"今天天气"）| ✅ 不调任何工具，直接回答 + 优雅承认能力边界 |

---

# 🎯 第 5 章关键认知

```
1. RAG = 索引（一次）+ 查询（每次）
2. Embedding 把语义映射成向量距离 —— 距离近 = 语义近
3. Chunking 是地基（fixed 500 + overlap 50 起步）
4. 中文 RAG 相似度 0.3-0.6 是常态，别误判为"失败"
5. 把 search 包成 tool —— 让 agent 自主决定何时查
6. 工具描述里的「反场景」决定 agent 的克制力
7. RAG 和 Memory 本质同源 —— 外部存储 + 检索的不同侧面
```

---

# ✅ 自检清单

- [ ] Embedding 是什么？为什么能比较"语义相似度"？
- [ ] Chunking 为什么必须有 overlap？
- [ ] Recall@5 = 60% 说明什么？能靠改 LLM 救回来吗？
- [ ] 中文 RAG 相似度 0.4 算高还是低？为什么？
- [ ] 为什么不让 agent 每次都查？工具描述该怎么写？
- [ ] Memory 和 RAG 的本质区别是什么？
- [ ] Claude Code 的冷 memory 为什么不用向量库？
- [ ] 热 memory 和冷 memory 的"温度"由什么决定？

---

# 🎓 本章产出

- `shared/embeddings.py` —— 走中转渠道的 embedding 封装（含 batch 分组）
- `chapter_05_rag/step0_embed_ping.py` —— embedding 接口预检
- `chapter_05_rag/indexer.py` —— 索引构建器
- `chapter_05_rag/retriever.py` —— 检索函数
- `chapter_05_rag/rag_demo.py` —— 纯 RAG demo
- `chapter_05_rag/tools.py` —— search_knowledge 工具
- `chapter_05_rag/agent.py` —— 带 RAG 工具的 agent
- `chapter_05_rag/chroma_db/` —— 向量库存储（前 4 章 NOTES.md 的索引）

**典型 agent 行为**：
```
知识题 → 1 次 search 命中 → 引用来源回答
综合题 → 1 次 search + top_k=5 → 整合多 chunk
闲聊  → 0 次 search → 直接回答 + 优雅说明边界
```
