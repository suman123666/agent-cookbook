"""统一的 LLM 客户端，所有章节共用。

我们走 OpenAI 兼容接口（通过中转渠道调用 Claude），所以用 openai 库，
把 base_url 指向中转站。这样后面切换到 LangChain 也很平滑——
因为 LangChain 底层也是这套 OpenAI 协议。
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 加载项目根目录下的 .env（无论从哪个章节目录运行脚本都能找到）
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

# 模型名按你的中转渠道实际命名来；默认值仅作占位
MODEL = os.environ.get("MODEL", "claude-sonnet-4-6")


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if not api_key:
        raise RuntimeError(
            "缺少 OPENAI_API_KEY。请把项目根目录的 .env.example 复制为 .env 并填入配置。"
        )
    return OpenAI(api_key=api_key, base_url=base_url)
