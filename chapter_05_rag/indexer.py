"""第 5 章索引器：扫描项目里所有 chapter_*/NOTES.md，切块 → embedding → 存进 Chroma。

教学意图：用我们前几章自己写的笔记当知识库——亲眼看 RAG 检索的真实效果。
建好索引后，retriever.py / rag_demo.py 才能查询。

运行：uv run python chapter_05_rag/indexer.py
"""
import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.embeddings import get_embedder, EMBED_MODEL  # noqa: E402

# ─── 配置 ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHAPTER_DIR = Path(__file__).resolve().parent
DB_DIR = CHAPTER_DIR / "chroma_db"
COLLECTION_NAME = "agent_notes"

CHUNK_SIZE = 500       # 每块约 500 字符
CHUNK_OVERLAP = 50     # 块之间重叠 50 字符（避免答案被切两半）

# Embedding 走中转渠道（在 .env 里通过 EMBED_MODEL 配置具体模型名）


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    """最简单的固定大小切块（带重叠）。

    生产里会按段落 / Markdown 标题 / 句子切，但起步用这个最易理解。
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap  # 往回退 overlap 个字符
    return chunks


def collect_documents() -> list[dict]:
    """扫描项目下所有章节的 NOTES.md，每份文档切成 chunk。"""
    docs = []
    for notes_path in sorted(PROJECT_ROOT.glob("chapter_*/NOTES.md")):
        text = notes_path.read_text(encoding="utf-8")
        chapter_name = notes_path.parent.name
        for i, chunk in enumerate(chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
            docs.append({
                "id": f"{chapter_name}_chunk_{i:03d}",
                "content": chunk,
                "source": f"{chapter_name}/NOTES.md",
                "chunk_index": i,
            })
    return docs


def build_index():
    print(f"📂 项目根目录: {PROJECT_ROOT}")
    print(f"📚 收集 NOTES.md ...")

    docs = collect_documents()
    sources = sorted(set(d["source"] for d in docs))
    print(f"   找到 {len(sources)} 份文档，切成 {len(docs)} 个 chunk")
    for s in sources:
        n = sum(1 for d in docs if d["source"] == s)
        print(f"     • {s}：{n} 个 chunk")

    if not docs:
        print("⚠️ 没找到任何 chapter_*/NOTES.md。先完成前几章笔记。")
        return

    print(f"\n🤖 准备 embedding（走中转渠道，模型: {EMBED_MODEL}）...")
    embed_fn = get_embedder()

    print(f"\n🗄️  初始化 Chroma 向量库 ({DB_DIR}) ...")
    DB_DIR.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(DB_DIR))

    # 删除旧 collection 重建，避免重复写入
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"   清除旧 collection")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},  # 用 cosine similarity 度量
    )

    print(f"\n📥 计算 embedding 并写入向量库 ...")
    collection.add(
        ids=[d["id"] for d in docs],
        documents=[d["content"] for d in docs],
        metadatas=[
            {"source": d["source"], "chunk_index": d["chunk_index"]}
            for d in docs
        ],
    )

    print(f"\n✅ 索引建立完成！共 {collection.count()} 个 chunk")
    print(f"   存储位置: {DB_DIR}")
    print(f"\n   下一步：uv run python chapter_05_rag/rag_demo.py")


if __name__ == "__main__":
    build_index()
