"""纯 RAG demo：4 个测试问题，每个走完整 RAG 流程。

不带 agent——让你看清 RAG 本身的效果（检索准不准、LLM 用得好不好），
排除掉 agent 多轮循环的干扰。下回合再叠加 agent。

运行：uv run python chapter_05_rag/rag_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client, MODEL  # noqa: E402
from retriever import search  # noqa: E402

client = get_client()

# 4 个测试问题，分别考察不同章节的检索能力
QUESTIONS = [
    "agent 的三大支柱是什么？",           # 应召回第 1 章
    "什么时候不该用 agent？",             # 第 1 章铁律
    "temperature 参数对 agent 决策有什么影响？",  # 第 2 章深度内容
    "Critic 设计的两个反模式是什么？",    # 第 4 章
]


def rag_answer(question: str, top_k: int = 3):
    print(f"\n{'═' * 64}")
    print(f"❓ 问题: {question}")
    print(f"{'─' * 64}")

    # ─── ① 检索 ────────────────────────────────────
    chunks = search(question, top_k=top_k)
    print(f"📥 召回 top-{top_k} chunk:")
    for i, c in enumerate(chunks, 1):
        preview = c["content"][:80].replace("\n", " ")
        print(f"  [{i}] {c['source']} (相似度={c['similarity']:.3f})")
        print(f"      {preview}...")

    # ─── ② 拼 prompt ─────────────────────────────
    context = "\n\n---\n".join(
        f"【来源 {i+1}: {c['source']}】\n{c['content']}"
        for i, c in enumerate(chunks)
    )

    # ─── ③ LLM 基于材料回答 ───────────────────────
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "你基于提供的【参考材料】回答问题。"
                "如果材料里没有相关信息，直接说'根据当前知识库无法回答'，不要瞎编。"
                "回答时引用具体来源（用 [来源 N] 标注）。"
                "回答简洁，不超过 200 字。"
            )},
            {"role": "user", "content": f"【参考材料】\n{context}\n\n【问题】\n{question}"},
        ],
        temperature=0,
    )
    answer = resp.choices[0].message.content
    print(f"\n🤖 回答:\n{answer}")


if __name__ == "__main__":
    for q in QUESTIONS:
        rag_answer(q, top_k=3)
    print(f"\n{'═' * 64}")
    print("✅ RAG demo 完成")
