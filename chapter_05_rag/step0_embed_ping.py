"""测试中转渠道是否支持 embedding 接口。

OpenAI 兼容渠道通常实现两个接口：
  - /v1/chat/completions  ← 你已经验证支持（前 4 章在用）
  - /v1/embeddings        ← 这里测试

如果支持 → 我们的 RAG 用它做 embedding，无需任何本地模型下载。
如果不支持 → 要找别的方案（用代理 / 换渠道 / 本地模型挂代理下载）。

运行：uv run python chapter_05_rag/step0_embed_ping.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.client import get_client  # noqa: E402

client = get_client()

# 常见的 embedding 模型名（不同中转站可能不同）
CANDIDATES = [
    "text-embedding-v4",   # OpenAI 主流，便宜
    "text-embedding-3-large",   # OpenAI，质量更高
    "text-embedding-ada-002",   # OpenAI 老版本，很多中转站还在用
    "voyage-3",                 # Anthropic 推荐
    "bge-m3",                   # 开源多语言
]

print("🔍 测试中转渠道支持哪些 embedding 模型...\n")

supported = []
for model in CANDIDATES:
    try:
        resp = client.embeddings.create(
            model=model,
            input="测试文本：agent 的三大支柱",
        )
        dim = len(resp.data[0].embedding)
        print(f"  ✅ {model}  (维度: {dim})")
        supported.append((model, dim))
    except Exception as e:
        # 摘要错误信息（去掉冗长堆栈）
        err = str(e).split("\n")[0][:120]
        print(f"  ❌ {model}  → {err}")

print()
if supported:
    print(f"🎉 你的渠道支持 {len(supported)} 个 embedding 模型。")
    print(f"   推荐用: {supported[0][0]}")
    print(f"\n   把这行加到 .env 里:")
    print(f"   EMBED_MODEL={supported[0][0]}")
else:
    print("⚠️ 没有任何 embedding 模型可用。")
    print("   下一步：要么换支持 embedding 的中转站，要么本地模型 + 代理下载。")
