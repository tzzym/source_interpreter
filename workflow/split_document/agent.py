import pathlib
from typing import Literal
from pydantic import BaseModel, Field
from google.adk import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

my_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "split-document"
)

my_skill_toolset = skill_toolset.SkillToolset(
    skills=[my_skill],
)


# ---------------------------------------------------------------------------
# output_schema：强制智能体输出严格的 JSON 结构
# ADK 会注入 schema 到提示词，并用 model_validate_json 验证输出
# 如果模型输出不符合 schema，ADK 会自动重试
# 参考 https://adk.dev/agents/llm-agents/#data-handling
# ---------------------------------------------------------------------------

class CodeElement(BaseModel):
    """源代码中的一个顶层片段，类型由 SKILL.md 定义"""
    类型: Literal[
        "代码引入",
        "宏",
        "全局变量",
        "结构体数据类型或实例",
        "enum",
        "函数",
    ] = Field(description="该代码片段所属的类型")
    content: str = Field(description="代码片段原文，保留原始缩进、换行和注释")


class SplitDocumentOutput(BaseModel):
    """拆分一个文档的输出：按源代码顺序排列的代码元素列表"""
    elements: list[CodeElement] = Field(
        description="按顺序排列的代码元素，按此顺序拼接后应恰好等于原始源代码"
    )


root_agent = Agent(
    model='deepseek/deepseek-v4-pro',
    name='split_document',
    instruction=(
        "请使用'split_document'技能分析用户提供的源代码，"
        "然后以严格的 JSON 格式输出结果。不要添加任何解释性文字。"
    ),
    tools=[my_skill_toolset],
    output_schema=SplitDocumentOutput,
)
