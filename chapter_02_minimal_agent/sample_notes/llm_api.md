# 调用 LLM API 要点

调用大模型 API 的核心是构造 messages 列表并处理返回。

## 消息角色
对话由带角色的消息组成：system（设定行为）、user（用户输入）、assistant（模型回复）、tool（工具执行结果）。

## 关键参数
常用参数包括 model（选哪个模型）、messages（对话历史）、temperature（随机性）、max_tokens（最大输出长度）、tools（可调用的工具列表）。

## 停止原因
返回里的 finish_reason 告诉你模型为何停下：stop 表示正常结束，length 表示达到长度上限，tool_calls 表示模型要求调用工具。
