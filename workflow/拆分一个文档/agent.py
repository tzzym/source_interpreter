from google.adk.agents.llm_agent import Agent

my_skill = load_skill_from_dir(
    pathlib.Path(__file__).parent / "拆分一个文档"
)

my_skill_toolset = skill_toolset.SkillToolset(
    skills=[my_skill],
)

root_agent = Agent(
    model='deepseek/deepseek-v4-pro',
    name='拆分一个文档',
    instruction="You are a helpful assistant. 请使用“拆分一个文档”技能。",
    tools=[my_skill_toolset,],
)