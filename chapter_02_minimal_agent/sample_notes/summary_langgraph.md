# LLM API 调用要点
- 消息由 system/user/assistant/tool 四种角色构成，用于控制模型行为与对话流程。
- 关键参数包括 model、messages、temperature、max_tokens 和 tools，决定调用行为与输出特性。
- finish_reason 字段指示停止原因：stop（正常结束）、length（超出长度限制）、tool_calls（需调用工具）。

# Python 基础要点
- 变量动态类型，无需声明；内置类型丰富，如 int、str、list、dict 等。
- 函数支持默认参数、*args、**kwargs；函数为一等对象，可传递和返回。
- 推荐使用虚拟环境（如 uv）隔离依赖，提升项目稳定性和管理效率。

# AI Agent 核心要点
- Agent 能自主决策、调用工具、循环执行；Workflow 则路径固定、由代码硬编码。
- 三大支柱：LLM（大脑）、工具集（手脚）、反馈循环（心跳），三者缺一不可。
- 仅当任务步骤不可预知、需动态决策、且可容忍一定失败率时，才适合使用 Agent。