# sample_notes/ 总结

## llm_api.md
- 消息由 system/user/assistant/tool 四种角色构成，用于控制模型行为与对话流程。
- 关键调用参数包括 model、messages、temperature、max_tokens 和 tools。
- finish_reason 字段指示生成终止原因：stop（正常结束）、length（超长截断）、tool_calls（需调用工具）。

## python_basics.md
- Python 是动态类型、解释型语言，强调代码可读性与简洁性。
- 变量无需声明类型；内置常用类型如 int、str、list、dict 等；函数支持多种参数形式。
- 推荐使用虚拟环境（如 uv）隔离依赖，避免版本冲突，提升开发效率。

## what_is_agent.md
- Agent 是能自主决策、调用工具、通过反馈循环持续执行的 LLM 应用。
- 与固定路径的 Workflow 不同，Agent 的执行路径由 LLM 在运行时动态生成。
- 构成 Agent 的三大要素是：LLM（大脑）、工具集（手脚）、反馈循环（心跳）。