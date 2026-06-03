# 第 3 章 · 工具与记忆 · 知识要点

## 本章解决什么问题

第 2 章 agent 能跑，但"裸 agent"在真实场景有 4 种翻车模式：

```
🤖 调错工具、传错参数      ← 工具描述写得不够好
💥 一报错就崩盘            ← 错误处理不到位
🧠 失忆——对话长了就忘事    ← 短期上下文管理失败
🐠 金鱼记忆——上次说过又问   ← 没有长期记忆
```

本章把 agent 从"能跑"升级到"好用"。

---

# 🛠 3.1 工具系统设计

## ① 工具粒度：粗 vs 细

| 维度 | 细粒度（read_file, write_file...） | 粗粒度（summarize_directory）|
|------|-----------------------------------|----------------------------|
| 灵活性 | ✅ 高 | ❌ 低 |
| 完成简单任务的轮数 | ❌ 多 | ✅ 少 |
| 成本/延迟 | ❌ 高 | ✅ 低 |
| 应对新需求 | ✅ 能组合 | ❌ 没覆盖就抓瞎 |

**黄金法则**：按用户最常见的高频操作设计「粗」工具，留「细」工具兜底。

参考：Claude Code = Read/Write/Edit/Bash（细）+ Grep/Glob（半粗）。

---

## ② 工具描述黄金法则

> **写给 LLM 看的「说明书」，不是写给人看的注释。**

### 6 要素清单

```
☐ 这工具干什么？（功能）
☐ 输入什么、返回什么？（接口）
☐ 什么场景下用？（适用）
☐ 什么场景下"不要"用？（反场景，最常被忽略！）
☐ 出错时的提示长什么样？（预期错误）
☐ 1-2 个具体例子（示例最有效）
```

**反场景最关键**——告诉模型"不要在 X 情况用"，比告诉它"在 Y 情况用"更能减少误调用。

---

## ③ 错误处理：让 agent 自愈

### 反模式
```python
def read_file(path):
    return open(path).read()  # 文件不存在 → 整个 agent 崩溃
```

### 正模式
```python
def run_tool(name, args):
    try:
        return func(**args)
    except Exception as e:
        return f"工具执行出错：{type(e).__name__}: {e}"
```

**核心思想**：错误信息也是给模型的"输出"。模型看到错误，会自己改策略重试——这就是 agent 的**自愈能力**。

### 错误信息要"含信息量"

| 等级 | 例子 |
|------|------|
| 差 | `Error` |
| 中 | `FileNotFoundError` |
| 好 | `File 'notes/foo.md' not found. Use list_dir to check available files in 'notes/'` |

**给错误信息附"下一步建议"**，agent 命中率显著提升。

### 三类错误的处理

| 错误类型 | 处理 |
|---------|------|
| 用户错（参数错） | 喂回 → agent 改参数重试 |
| 环境错（文件不存在） | 喂回 → agent 改策略 |
| 不可恢复（API key 失效） | 抛出来让外层处理 |

---

## ④ 权限隔离：危险工具必须有边界

### 按破坏力分级
```
🟢 只读类（read_file, list_dir）      → 随便调
🟡 修改类（write_file, edit_file）     → 路径白名单
🔴 不可逆（delete, drop_table, send）  → 必须 human-in-the-loop
```

### 三种隔离机制
1. **路径白名单**（我们的 `_safe_path`）
2. **操作黑名单**（拒绝 `rm -rf /`、`sudo`）
3. **用户确认**（弹 `[y/N]` 让人决定）

---

# 🧠 3.2 记忆系统

## 三种记忆一览

```
┌──────────────────────────────────────────────────────────┐
│  类型        │ 类比          │ 存哪          │ 活多久    │
├──────────────────────────────────────────────────────────┤
│  短期记忆     │ 当下对话      │ messages 列表 │ 单次会话  │
│  长期记忆     │ 跨会话档案    │ 文件/数据库   │ 永久      │
│  工作记忆     │ 解题草稿纸    │ scratchpad    │ 单次任务  │
└──────────────────────────────────────────────────────────┘
```

---

## 短期记忆 = 上下文窗口管理

### 三大问题

| 问题 | 后果 |
|------|------|
| Token 爆炸 | 成本 = O(轮数²) |
| 超出窗口 | Claude 200K、GPT-4 128K 也会被截断 |
| Lost in the middle | 长上下文里**中间**信息容易被忽略（论文实证）|

### 三种压缩策略

| 策略 | 做法 | 优 | 缺 |
|------|------|-----|-----|
| A 滑动窗口 | 只保留最近 N 轮 | 简单可控 | 早期信息直接丢 |
| B 摘要压缩 | 早期对话 → LLM 摘要 | 保留关键信息 | 摘要花 token + 可能漏细节 |
| C 分段加载 | 早期对话存向量库按需检索 | 理论无限 | 复杂（第 5 章 RAG）|

**生产组合**：A + B —— 保留最近 K 轮 + 把更早的摘要成一段。
Claude Code 的 **context compaction** 就是这种实现。

---

## 长期记忆 = 跨会话持久化

### 写入触发的三种模式
1. 用户显式要求："记住 X"
2. Agent 主动判断（需要 `save_memory` 工具）
3. 会话结束自动总结

### 读取的两种模式
1. **自动注入**：启动时全部塞 system prompt（数据少时）
2. **按需检索**：给 agent `search_memory` 工具（数据多时）

---

## Think Tool 模式 ⭐

让 agent 显式思考再行动，**工具本身什么都不做**：

```python
def think(thought: str) -> str:
    return "已记录思考。继续。"
```

### 为什么有效？
- 调用 `think` 时，LLM 被迫输出推理过程
- 推理进入对话历史，影响后续决策
- **思考本身改变了行为**

### 实证
Anthropic 论文：think tool 让复杂任务正确率提升 **15-40%**。

### 关键认知
> LLM 不缺推理能力，缺的是"被强制推理"的机会。Tool calling 模式天然鼓励"直接行动"，think tool 把"先想"作为合法行动选项。

---

# 🆚 Think Tool vs 模型自带 thinking

```
模型自带 thinking  =  模型在「输出之前」自己内部推理（在模型层）
Think tool        =  模型在「Agent 循环里」主动调一个 no-op 工具（在应用层）
```

| 维度 | 模型自带 thinking | Think tool |
|------|------------------|------------|
| 实现层次 | 训练在模型权重里 | 应用层设计 |
| 触发控制 | API 参数（reasoning_effort）| Prompt + 工具描述 |
| 思考可见性 | 不可见 / 可选 | 完全可见，进 messages |
| 触发频率 | 每次响应前一次 | 循环里可多次 |
| 计费 | reasoning tokens（贵）| 普通 tool call |
| OpenAI 兼容渠道 | ❌ 不支持 | ✅ 永远可用 |

**关键洞察**：自带 thinking 是「一次性推理」，think tool 是「持续可观察的推理流」。Agent 场景里两者**互补**，生产里通常都用。

---

# 🏭 生产系统的记忆架构

## 4 层架构（任何生产 agent）

```
层 1：会话内短期记忆     → messages 列表 + 压缩
层 2：跨会话长期记忆     → 文件 / K-V / 向量库
层 3：显式指令/规则       → 配置文件（CLAUDE.md）
层 4：临时工作记忆       → scratchpad / think tool
```

## Claude Code 的实际架构

```
~/.claude/                        ← Windows 是 C:\Users\<你的用户名>\.claude\
├── CLAUDE.md                    ← 用户级显式指令（跨项目）
└── projects/<project>/memory/
    ├── MEMORY.md                ← 索引（每次必加载，前 200 行）
    ├── user_*.md                ← 用户档案
    ├── feedback_*.md            ← 偏好与反馈
    ├── project_*.md             ← 项目上下文
    └── reference_*.md           ← 外部资源指针
```

**反直觉设计**：Claude Code 用**纯文件 + Markdown**，不用向量库。理由：
- 个人记忆量小（几十~几百条）
- 人类可读 = 用户可审计/编辑/git
- LLM 看索引 + 按需 read 比 cos 相似度更准
- 复杂度永远不要超过实际需要

## 业界对比

| 系统 | 长期记忆方案 |
|------|--------------|
| Claude Code | 纯文件 + Markdown 索引 |
| ChatGPT Memory | 每用户 K-V 池 |
| Cursor | `.cursorrules` 文件 + Codebase 向量库 |
| MemGPT / Letta | 分层：main context + 外部向量库 |
| OpenAI Assistants | Threads + Files API（向量库 RAG）|

---

# 📦 选型：文件 vs K-V vs 向量库

## 真正的分界线 = 数据量级（不是"个人 vs 企业"）

```
量级 A：几十~几百条          量级 B：几千~几万条       量级 C：十万条+
       ↓                            ↓                          ↓
   能全部塞进 prompt          塞不进，但可索引         必须语义检索
       ↓                            ↓                          ↓
   文件                       K-V 数据库              向量库 / 混合
       ↓                            ↓                          ↓
   Claude Code、项目 2        ChatGPT Memory          企业知识库
```

## 反直觉事实

> **数据少时，文件 + 让 LLM 直接看，比向量库召回更准、更便宜、更易调试。**

```
向量库 ≠ 升级版文件
向量库 =  为了解决"塞不下"的妥协方案
```

向量库带来的复杂度：embedding 模型 + 向量基础设施 + chunk size + reranker + 难调试。

## 文件 vs K-V 数据库

| 维度 | JSON 文件 | K-V DB（SQLite/Redis）|
|------|-----------|---------------------|
| 读单条 | 必须读全文 → 解析 → 取那条 | 直接按 key 索引 |
| 写单条 | 读全文 → 改 → **重写整个文件** | 只改那一条 |
| 数据量上限 | 几 MB | GB 级 |
| 并发 | ❌ 同时写会冲突 | ✅ 内置锁/事务 |
| 查询能力 | 只能按 key | 索引 + 范围查询 + 过滤 |
| 人类编辑 | ✅ | ❌ |
| git 追踪 | ✅ | ❌ |

**SQLite 是最佳折中**：物理上一个文件（无需服务器），但有数据库的能力（索引、原子）。生产里记忆类应用几乎永远是 SQLite > JSON。

---

# 🎯 实战项目 2：带记忆的文件助手

## 文件结构
```
shared\memory.py                          ← 长期记忆（JSON 持久化）
chapter_03_tools_memory\
├── tools.py                              ← 文件工具 + save_memory + think
├── agent.py                              ← 交互式 agent（多轮对话）
└── memory.json (项目根，自动生成)         ← 长期记忆数据
```

## 关键设计
1. **启动时加载**：`load_memory()` → 注入 system prompt
2. **运行时写入**：agent 调 `save_memory(key, value)` 主动存
3. **跨会话保留**：JSON 文件，重启 agent 自动加载
4. **显式思考**：`think(thought)` 工具供 agent 在复杂任务前规划

## 验证：跑两次会话
- 第一次：告诉 agent "我叫张三，喜欢简洁"→ exit
- 第二次：新启动，问"我是谁？"→ 看是否记得

---

# ✅ 自检清单

- [ ] 工具描述的「6 要素」中"反场景"为什么重要？
- [ ] 错误信息为什么要"喂回"模型而不是抛出？
- [ ] 短期记忆压缩 A+B 组合是怎么工作的？
- [ ] Think tool 为什么"什么都不做"反而能提升正确率？
- [ ] Think tool 和模型自带 thinking 的本质差别？
- [ ] 为什么说"个人 agent 用文件，企业搜索才用向量"不够准确？
- [ ] 什么时候 JSON 文件就撑不住了，必须换 SQLite？

---

# 🎓 本章产出

- `shared/memory.py` —— 长期记忆 K-V 存取
- `chapter_03_tools_memory/tools.py` —— 5 工具集（文件 + save_memory + think）
- `chapter_03_tools_memory/agent.py` —— 交互式 agent，整合三种记忆
- `memory.json` —— 跨会话持久化数据（项目根）


---

◀ 上一章：[第 2 章 · 最小 Agent](../chapter_02_minimal_agent/NOTES.md)
▶ 下一章：[第 4 章 · 规划与反思](../chapter_04_planning_reflection/NOTES.md)

🏠 [回到课程首页](../README.md)
