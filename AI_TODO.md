# AI 待实现

## 代码片段识别

`classify_target()` 层1 规则先识别 snippet：含换行符 `"\n"` 或长度 < 20 → 直接返回，不走 AI。

## local_path_type 路径纠错

| 项 | 说明 |
|----|------|
| 触发条件 | `os.path.isfile()` 和 `os.path.isdir()` 均返回 False（路径不存在） |
| AI 任务 | 分析路径字符串，推测正确路径，返回建议（如拼写纠正、路径补全等） |
