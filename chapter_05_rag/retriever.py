"""查询器：把用户问题转向量，从 Chroma 召回 top-K 个最相关 chunk。

这是 RAG 的"检索"环节——后面 rag_demo.py 和 agent 都会用这个函数。
"""
import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.embeddings import get_embedder  # noqa: E402

CHAPTER_DIR = Path(__file__).resolve().parent
DB_DIR = CHAPTER_DIR / "chroma_db"
COLLECTION_NAME = "agent_notes"


def _get_collection():
    """每次调用都新建 client/collection 实例。
    Chroma 内部有缓存，性能不是问题。"""
    client = chromadb.PersistentClient(path=str(DB_DIR))
    return client.get_collection(name=COLLECTION_NAME, embedding_function=get_embedder())


def search(query: str, top_k: int = 5) -> list[dict]:
    """检索 top-K 个最相关 chunk。

    返回值：list of dict，按相似度从高到低排列。
    每条含：content / source / chunk_index / similarity（0-1，越大越相似）
    """
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=top_k)

    chunks = []
    for i in range(len(results["ids"][0])):
        # Chroma 返回的是 cosine distance（越小越相似），转成相似度（越大越相似）
        distance = results["distances"][0][i]
        chunks.append({
            "content": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "chunk_index": results["metadatas"][0][i]["chunk_index"],
            "similarity": 1 - distance,  # 1 - cosine_distance ≈ cosine_similarity
        })
    return chunks


if __name__ == "__main__":
    # 手动测试一下
    query = "agent 的三大支柱是什么？"
    print(f"测试查询: {query}")
    for i, c in enumerate(search(query, top_k=3), 1):
        print(f"\n[{i}] 来源: {c['source']} | 相似度: {c['similarity']:.3f}")
        print(f"    {c['content'][:120]}...")
