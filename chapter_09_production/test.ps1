# 第 9 章实战测试脚本：演示 HTTP API + 多用户会话隔离
#
# 用法：先启动服务（另开一个 PowerShell 窗口）：
#   uv run uvicorn chapter_09_production.server:app --port 8000 --reload
# 然后在本目录执行：
#   .\chapter_09_production\test.ps1

$base = "http://localhost:8000"

Write-Host "`n=== 1. 健康检查 ===" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$base/" -Method GET | ConvertTo-Json

Write-Host "`n=== 2. 用户 alice 问一个知识题 ===" -ForegroundColor Cyan
$r1 = Invoke-RestMethod -Uri "$base/chat" -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ session_id = "alice"; message = "agent 的三大支柱是什么？" } | ConvertTo-Json)
Write-Host "alice 收到回复 ($($r1.rounds) 轮，会话长度 $($r1.history_len))" -ForegroundColor Green
Write-Host $r1.reply

Write-Host "`n=== 3. 用户 bob 问完全不同的问题 ===" -ForegroundColor Cyan
$r2 = Invoke-RestMethod -Uri "$base/chat" -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ session_id = "bob"; message = "你好，今天天气如何？" } | ConvertTo-Json)
Write-Host "bob 收到回复 ($($r2.rounds) 轮，会话长度 $($r2.history_len))" -ForegroundColor Green
Write-Host $r2.reply

Write-Host "`n=== 4. 验证 alice 的会话还在（追问，看 agent 是否记得上文）===" -ForegroundColor Cyan
$r3 = Invoke-RestMethod -Uri "$base/chat" -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body (@{ session_id = "alice"; message = "第二点能再展开讲讲吗？" } | ConvertTo-Json)
Write-Host "alice 追问回复 (会话长度 $($r3.history_len) - 应明显大于 bob 的)" -ForegroundColor Green
Write-Host $r3.reply

Write-Host "`n=== 5. 列出所有活跃会话 ===" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$base/sessions" -Method GET | ConvertTo-Json

Write-Host "`n=== 6. 清空 alice 的会话 ===" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$base/session/alice" -Method DELETE | ConvertTo-Json

Write-Host "`n=== 7. 再列一次会话（alice 应该消失了）===" -ForegroundColor Cyan
Invoke-RestMethod -Uri "$base/sessions" -Method GET | ConvertTo-Json

Write-Host "`n✅ 全跑完了。`n核心观察点：" -ForegroundColor Yellow
Write-Host "  - alice 和 bob 的 history_len 各自独立增长（会话隔离生效）"
Write-Host "  - alice 第二次提问时 agent 记得上文（session 跨请求保持）"
Write-Host "  - DELETE 后 alice 的会话从 /sessions 列表消失"
