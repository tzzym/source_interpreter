---
name: 拆解一个程序
description: 当用户要求把程序文件按照逻辑拆成片段的时候运行本技能
---

# 主要目标

一个程序文件由很多部分组成。本技能要把整篇代码文件拆分成全局的、最外层定义的[对象](.\references\parts\README.md)。

# 输出要求

必须只包含一个格式完整的 [JSON数组](.\references\JSON\JSON-array.md) 。

这个数组必须满足 [具体要求](.\references\json-output-structure\L1-JSON-array.md) 。

# 输入、输出样例

- 样例输入 `.\assets\Input_template.json`
- 样例输出 `.\assets\Output_json_template.json`
