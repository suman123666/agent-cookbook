"""第 9 章实战：把 chapter_05_rag 的 agent 部署成 HTTP 服务。

学习目标：
  - 把脚本式 agent（while + input）重构成「可复用纯函数」
  - 用 FastAPI 暴露 HTTP 接口
  - 用内存 dict 维护多用户会话隔离（生产里换成 Redis）
  - 看到「同一个 agent 同时服务多个 user」的效果

启动：
  uv run uvicorn chapter_09_production.server:app --port 8000 --reload

测试：见同目录 test.ps1 / 或本文件底部注释
"""
import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 复用第 5 章的 RAG 工具（search_knowledge + 索引好的向量库）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "chapter_05_rag"))

from shared.client import get_client, MODEL  # noqa: E402
from tools import TOOLS, run_tool  # noqa: E402  来自 chapter_05_rag/tools.py

client = get_client()

SYSTEM_PROMPT = """你是一个带私有知识库的学习助手。
- 知识题（agent 概念、ReAct、RAG 等）→ 优先调 search_knowledge
- 闲聊/无关问题 → 直接回答，不调工具，不瞎编"""

MAX_ROUNDS = 10  # 早退机制：防 agent 卡死烧钱


# ═══════════════════════════════════════════════════════════
# ① Agent 核心：从脚本提炼成「纯函数」
#    这是部署的第一步——任何要上线的 agent，先把逻辑从 I/O
#    解耦出来，外层才能换成 HTTP / WebSocket / 任务队列。
# ═══════════════════════════════════════════════════════════
def run_agent_turn(history: list) -> tuple[str, int]:
    """跑一回合 agent（可能内含多次工具调用），返回 (回复文本, LLM 轮数)。

    入参 history 会被原地追加 assistant 和 tool 消息——
    所以 caller 拿到的 history 自然保留了完整对话上下文。
    """
    rounds = 0
    for _ in range(MAX_ROUNDS):
        rounds += 1
        resp = client.chat.completions.create(
            model=MODEL, messages=history, tools=TOOLS, temperature=0,
        )
        choice = resp.choices[0]
        msg = choice.message
        history.append(msg)

        if choice.finish_reason != "tool_calls":
            return msg.content or "", rounds

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args, _ = json.JSONDecoder().raw_decode(tc.function.arguments)
            result = run_tool(tc.function.name, args)
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    return "(达到最大轮数限制)", rounds


# ═══════════════════════════════════════════════════════════
# ② 会话状态（内存 dict）
#    生产里必须换成 Redis / 数据库 —— 否则服务重启就清零。
#    这里用内存只是为了让你直观看到「多 user 独立会话」效果。
# ═══════════════════════════════════════════════════════════
sessions: dict[str, list] = {}


def get_session_history(session_id: str) -> list:
    """获取/创建会话历史。新会话自动注入 system prompt。"""
    if session_id not in sessions:
        sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return sessions[session_id]


# ═══════════════════════════════════════════════════════════
# ③ FastAPI 路由层
# ═══════════════════════════════════════════════════════════
app = FastAPI(title="RAG Agent Service", version="0.1")


class ChatRequest(BaseModel):
    session_id: str   # 用来隔离不同用户的对话
    message: str


class ChatResponse(BaseModel):
    reply: str
    rounds: int       # 这次后端跑了几个 LLM 轮
    history_len: int  # 当前会话累计多少条消息（含 system）


@app.get("/")
async def root():
    """健康检查 —— 上线后用 K8s liveness probe 打这个。"""
    return {
        "status": "ok",
        "model": MODEL,
        "active_sessions": len(sessions),
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """对话端点。"""
    if not req.message.strip():
        raise HTTPException(400, "message 不能为空")

    history = get_session_history(req.session_id)
    history.append({"role": "user", "content": req.message})

    reply, rounds = run_agent_turn(history)

    return ChatResponse(
        reply=reply,
        rounds=rounds,
        history_len=len(history),
    )


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """清空某个会话 —— 退出登录或「重新开始」按钮调这个。"""
    if session_id in sessions:
        del sessions[session_id]
        return {"deleted": True}
    return {"deleted": False, "reason": "session not found"}


@app.get("/sessions")
async def list_sessions():
    """列出所有活跃会话 —— 调试用，生产里要鉴权或下线。"""
    return {
        sid: {"messages": len(hist)}
        for sid, hist in sessions.items()
    }
