"""走中转渠道的 embedding 函数，符合 chromadb 的 EmbeddingFunction 接口。

把"调用 embedding 接口"封装在一处——后面所有章节都能 from shared.embeddings 用。
"""
import os

from .client import get_client

# 从 .env 读取 embedding 模型名（与 MODEL 同样的配置方式）
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")

# 不同渠道对每次请求的 batch size 上限不同：
#   - OpenAI:           2048
#   - 阿里通义:          10
#   - 大部分中转站:      取最小值最稳
# 默认 10（保守值）；OpenAI 渠道可改大提升吞吐
EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "10"))


class RouterEmbedding:
    """走中转渠道的 embedding 实现，符合 chromadb embedding function 协议。

    chromadb 要求 embedding function 是个可调用对象：
      __call__(input: list[str]) -> list[list[float]]
    """

    def __init__(self, model: str = EMBED_MODEL):
        self._client = get_client()
        self._model = model

    def __call__(self, input):
        """批量 embedding（chromadb 索引时调用）。"""
        # chromadb 传入的 input 是字符串列表（也可能是单个字符串）
        if isinstance(input, str):
            input = [input]
        inputs = list(input)

        # 分批调用——绕过中转渠道的 batch size 限制（如阿里通义限制 10/批）
        all_embeddings = []
        for i in range(0, len(inputs), EMBED_BATCH_SIZE):
            batch = inputs[i:i + EMBED_BATCH_SIZE]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            all_embeddings.extend(d.embedding for d in resp.data)
        return all_embeddings

    def embed_query(self, input):
        """查询 embedding（chromadb 1.x 查询时调用）。

        注意：尽管名字是 "embed_query"，chromadb 实际把返回值当 query_embeddings
        （list[list[float]]）传给底层。所以这里要返回"包含一个 embedding 的列表"，
        而不是单个 embedding。直接复用 __call__ 最稳。
        """
        return self(input)

    def embed_documents(self, input):
        """文档批量 embedding，部分 chromadb 版本会用这个名字调用。"""
        return self(input)

    @staticmethod
    def name() -> str:
        # 部分 chromadb 版本会调这个方法记 telemetry
        return "router-embedding"


def get_embedder() -> RouterEmbedding:
    return RouterEmbedding()
