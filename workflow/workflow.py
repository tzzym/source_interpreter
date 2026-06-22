"""DFS 文件层迭代。

SKILL.md 3.1 递归步骤的 Python 实现：
  步骤1：进入目录 → 列出条目，先文件后子目录
  步骤2：处理文件 → 提取结构 → 语句分析 → 函数分析 → 类分析 → 文件汇总
  步骤3：子目录递归 → 汇总目录级
  步骤4：回退根目录 → 项目级汇总
"""

import os
import json
import logging
import asyncio

from ..ai_client import client
from .split_document.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types # For creating message Content/Parts

logger = logging.getLogger(__name__)


def _parse_json(raw: str, default=None):
    """解析 API 返回的 JSON，自动处理 markdown 代码块包裹。"""
    raw = (raw or "").strip()
    if not raw:
        return default
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"JSON 解析失败，模型返回无法被机器识别为 JSON。完整原始内容:\n{raw}")
        return default

# 加载系统提示词
_PROMPT_DIR = os.path.dirname(__file__)
with open(os.path.join(_PROMPT_DIR, "codefile_system_prompt.txt"), "r", encoding="utf-8") as f:
    system_prompt = f.read()
with open(os.path.join(_PROMPT_DIR, "class_structure_system_prompt.txt"), "r", encoding="utf-8") as f:
    class_structure_prompt = f.read()

# 代码文件扩展名
_CODE_EXTENSIONS = {
    ".cpp", ".cc", ".cxx", ".c++", ".hpp", ".h", ".hxx", ".c",
    ".py", ".pyx",
    ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".go", ".rs", ".cs",
    ".swift", ".kt", ".kts", ".rb", ".php",
}

# 跳过的目录
_SKIP_DIRS = {".git", ".svn", ".hg", "__pycache__", "node_modules", ".解读", "build", "dist", "target"}


def _is_code_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in _CODE_EXTENSIONS


def _detect_language(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    ext_map = {
        ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".c++": "cpp",
        ".c": "c",
        ".hpp": "cpp", ".h": "cpp", ".hxx": "cpp",
        ".py": "python", ".pyx": "python",
        ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".ts": "typescript", ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cs": "csharp",
    }
    return ext_map.get(ext, "unknown")


# ---------------------------------------------------------------------------
# 文件处理管道（步骤2）
# ---------------------------------------------------------------------------

async def _call_split_agent(source_code: str) -> str:
    """通过 ADK Runner 调用"拆分一个文档"智能体，返回其文本输出。

    这是 Google ADK agent-team delegation 模式的实现：
    process_file()（根）→ 委托结构提取任务 → root_agent（子智能体）

    使用固定的 session ID + create_session() / delete_session() 管理生命周期。
    每次调用前显式创建，调用后立即删除，确保不同文件互不干扰。
    """
    APP_NAME = "source_interpreter"
    USER_ID = "workflow"
    SESSION_ID = "split_document"  # 固定 session，通过 create/delete 控制生命周期

    session_service = InMemorySessionService()

    # ---- 参考 ADK 官方写法，显式创建 session ----
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Prepare the user's message in ADK format
    content = types.Content(role='user', parts=[types.Part(text=source_code)])

    try:
        # ---- 向智能体发送源代码，等待最终响应 ----
        # 参考 ADK 官方 is_final_response() 写法：
        #   只在 agent 给出最终回复时取文本，中间 tool-call 等 event 自动跳过
        final_text = ""
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    final_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                break  # 拿到最终响应后立即停止，不再处理后续 event
    finally:
        # ---- 删除 session，清理上下文 ----
        await session_service.delete_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID,
        )
    return final_text


def process_file(file_path: str) -> None:
    """处理单个文件：提取结构 → 自底向上分析 → 写入 .解读/ 树。"""
    print('process_file ', file_path)

    language = _detect_language(file_path)
    logger.info(f"处理文件：{file_path} ({language})")

    # 读取源码
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()
    if not code.strip():
        return

    # ---- 2.1 结构提取（委托给"拆分一个文档"智能体） ----
    # Google ADK agent-team delegation 模式：
    #   process_file()  = 根智能体（协调者，负责后续函数/类/文件汇总分析）
    #   root_agent      = 子智能体（专门做代码结构拆分，在 agent.py 中定义）
    #   Session 由 _call_split_agent 内部用 create/delete 管理，固定 ID，自动清理
    try:
        raw_output = asyncio.run(_call_split_agent(code))
    except RuntimeError:
        # 已有 event loop 运行时降级为手动管理 loop
        loop = asyncio.new_event_loop()
        raw_output = loop.run_until_complete(_call_split_agent(code))
        loop.close()
    # output_schema 保证 agent 输出 {"elements": [{"类型": "...", "content": "..."}]}
    # _parse_json 解析后取出 elements 列表；也兼容直接数组格式作为降级
    parsed = _parse_json(raw_output, default={})
    if isinstance(parsed, list):
        elements = parsed
    elif isinstance(parsed, dict) and "elements" in parsed:
        elements = parsed["elements"]
    else:
        elements = []

    # ---- 2.2 按类型分发 ----
    macros = []
    globals_ = []
    functions = []
    classes = []

    for elem in elements:
        t = elem["类型"]
        # "拆分一个文档"智能体可能返回"代码引入"（如 #include），
        # 与原来的"宏"类型一并归入依赖项，供后续文件级汇总使用
        if t == "宏" or t == "代码引入":
            macros.append(elem["内容"])
        elif t == "全局变量":
            globals_.append(elem["内容"])
        elif t == "函数":
            functions.append(elem)
        elif t.startswith("结构体数据类型") or t == "enum":
            classes.append(elem)

    # ---- 2.3 自底向上分析 ----
    file_analyses = []

    for func in functions:
        # 返回dict类型，包含function类型的声明
        func_analysis = _process_one_function(func, language, file_path)
        if func_analysis:
            file_analyses.append(func_analysis)

    for cls in classes:
        cls_analysis = _process_one_class(cls, language, file_path)
        if cls_analysis:
            file_analyses.append(cls_analysis)

    # ---- 2.4 文件级汇总 ----
    file_overview = _analyze_file(file_path, macros, file_analyses)

    # ---- 写入文件概述 ----
    base_dir = os.path.join(
        os.path.dirname(file_path),
        os.path.basename(file_path) + ".解读",
    )
    os.makedirs(base_dir, exist_ok=True)
    with open(os.path.join(base_dir, f"{os.path.basename(file_path)}.解读.md"), "w", encoding="utf-8") as f:
        f.write(file_overview)
    logger.info(f"  已写入文件概述：{base_dir}")


def _process_one_function(func: dict, language: str, file_path: str, class_dir: str = None) -> dict | None:
    """分析单个函数：AI 提取元信息 → 拆语句 → 语句分析 → 函数概述 → 写入文件。

    class_dir: 可选，成员方法所属的类名，写入 <文件名>.解读/<class_dir>/ 下。
    """

    with open(os.path.join(_PROMPT_DIR, "func_meta_system_prompt.txt"), "r", encoding="utf-8") as f:
        func_meta_system_prompt = f.read()

    content = func["content"]

    # ---- AI 提取函数元信息（函数名、签名、参数、返回类型） ----
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": func_meta_system_prompt},
            {"role": "user", "content": content},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    meta = _parse_json(response.choices[0].message.content, default={})
    func_name = meta.get("函数名", "unknown")
    logger.info(f"  函数：{func_name}")

    # ---- AI 语句拆解 ----
    with open(os.path.join(_PROMPT_DIR, "stmt_analysis_system_prompt.txt"), "r", encoding="utf-8") as f:
        stmt_analysis_system_prompt = f.read()

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": stmt_analysis_system_prompt},
            {"role": "user", "content": content},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    statements = _parse_json(response.choices[0].message.content, default=[])

    # ---- 逐条语句深度解读 ----
    for stmt in statements:
        _process_one_statement(stmt)

    # ---- 本层分析：函数级正式解读 ----
    func_analysis = _analyze_function(meta, content, statements)

    # ---- 写入 .解读/ 树 ----
    _write_function_output(file_path, func_name, func_analysis['分析'], statements, class_dir)

    return {
        "name": func_name,
        "type": "function",
        "meta": meta,
        "analysis": func_analysis['分析'],
        "目标" : func_analysis['目标']
    }


def _analyze_function(meta: dict, source_code: str, statements: list) -> dict:
    """AI 函数级正式分析：算法概述、逻辑块、前置/后置条件、调用关系。"""

    print('analyse function', meta)

    with open(os.path.join(_PROMPT_DIR, "func_analysis_system_prompt.txt"), "r", encoding="utf-8") as f:
        func_analysis_system_prompt = f.read()

    func_input = json.dumps({
        "元数据": meta,
        "源代码": source_code,
        "语句分析": statements,
    }, ensure_ascii=False)

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": func_analysis_system_prompt},
            {"role": "user", "content": func_input},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    return {"目标" : func_input, "分析" : response.choices[0].message.content}


def _write_function_output(file_path: str, func_name: str, analysis: str, statements: list, class_dir: str = None) -> None:
    """将函数解读结果写入 .解读/ 目录树。"""
    safe_name = func_name.replace(":", "_").replace("/", "_").replace("\\", "_")
    base_dir = os.path.join(os.path.dirname(file_path), os.path.basename(file_path) + ".解读")
    if class_dir:
        base_dir = os.path.join(base_dir, class_dir)
    func_dir = os.path.join(base_dir, f"{safe_name}().解读")
    os.makedirs(func_dir, exist_ok=True)

    # ---- 函数概述（AI 直接输出的 Markdown） ----
    with open(os.path.join(func_dir, f"{safe_name}().解读.md"), "w", encoding="utf-8") as f:
        f.write(analysis)

    # ---- 语句分析 ----
    stmt_text = f"# 语句分析：{func_name}\n\n"
    for stmt in statements:
        stmt_text += f"### 语句 {stmt['行号']}：`{stmt.get('代码', '')}`\n"
        if stmt.get("深度解读"):
            stmt_text += stmt["深度解读"] + "\n\n"

    with open(os.path.join(func_dir, "语句分析.md"), "w", encoding="utf-8") as f:
        f.write(stmt_text)

    logger.info(f"  已写入：{func_dir}")


def _process_one_statement(stmt: dict) -> None:
    """对单条语句进行深度解读，AI 直接输出 Markdown。"""

    with open(os.path.join(_PROMPT_DIR, "stmt_deep_system_prompt.txt"), "r", encoding="utf-8") as f:
        stmt_deep_system_prompt = f.read()

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": stmt_deep_system_prompt},
            {"role": "user", "content": stmt["代码"]},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    stmt["深度解读"] = response.choices[0].message.content


def _process_one_class(cls: dict, language: str, file_path: str) -> dict | None:
    """分析类/结构体/enum：提取内部方法 → 递归分析每个方法 → 类级汇总。"""
    import re

    content = cls["content"]
    class_type = cls["类型"]

    # 提取类名
    name_match = re.search(r'(?:class|struct|enum)\s+(\w+)', content)
    class_name = name_match.group(1) if name_match else "unknown"
    logger.info(f"  {class_type}：{class_name}")

    # ---- AI 提取类内部结构（成员变量 + 成员方法） ----
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": class_structure_prompt},
            {"role": "user", "content": content},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    elements = _parse_json(response.choices[0].message.content, default=[])

    # ---- 收集成员变量 + 递归分析每个成员方法 ----
    members = []
    method_analyses = []
    for elem in elements:
        if elem["类型"] == "成员变量":
            members.append(elem)
        elif elem["类型"] == "成员方法":
            func = {"类型": "函数", "content": elem["content"]}
            result = _process_one_function(func, language, file_path, class_dir=class_name)
            if result:
                method_analyses.append(result)

    # ---- AI 类级汇总 ----
    class_overview = _analyze_class(class_name, class_type, content, members, method_analyses)

    # ---- 写入类概述 ----
    safe_name = class_name.replace(":", "_").replace("/", "_").replace("\\", "_")
    base_dir = os.path.join(os.path.dirname(file_path), os.path.basename(file_path) + ".解读")
    class_dir = os.path.join(base_dir, safe_name)
    os.makedirs(class_dir, exist_ok=True)
    with open(os.path.join(class_dir, f"{safe_name}.解读.md"), "w", encoding="utf-8") as f:
        f.write(class_overview)
    logger.info(f"  已写入：{class_dir}")

    return {"name": class_name, "type": class_type, "analysis": class_overview, '目标' : class_name}


def _analyze_class(name: str, class_type: str, source_code: str, members: list, methods: list) -> str:
    """AI 类级分析：职责、成员、设计模式。"""
    import json

    member_info = json.dumps(members, ensure_ascii=False)
    method_summaries = json.dumps([
        {"名称": m["name"], "分析": m.get("analysis", "")[:300]}
        for m in methods
    ], ensure_ascii=False)

    class_prompt = f"""请分析以下{class_type}的整体设计。返回 Markdown 格式：

# {class_type}解读：{name}

## 职责
（由成员方法和成员变量推导）

## 成员变量
| 变量名 | 类型 | 访问 | 含义 |
|--------|------|------|------|

## 方法清单
| 方法 | 说明 |
|------|------|
"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": class_prompt},
            {"role": "user", "content": f"成员变量：\n{member_info}\n\n方法分析：\n{method_summaries}"},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# 目录遍历（步骤1+3）
# ---------------------------------------------------------------------------

def walk_directory(dir_path: str, max_files: int = None) -> dict:
    """DFS 遍历目录，返回处理结果摘要。
    本函数功能类似于dir命令
    在本程序中控制往下递归的方向

    Args:
        dir_path: 目录路径
        max_files: 最大文件数（超过阈值时提示分步）

    Returns:
        {"total_files": int, "files": list[path], "subdirs": list[path]}
    """
    result = {"total_files": 0, "files": [], "subdirs": []}

    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        logger.warning(f"无权限访问：{dir_path}")
        return result

    # 收集代码文件
    code_files = []
    # 枚举所有子目录
    subdirs = []
    # 权限检查
    for entry in entries:
        if entry.startswith(".") or entry in _SKIP_DIRS:
            continue
        full = os.path.join(dir_path, entry)
        if os.path.isdir(full):
            subdirs.append(full)
        elif os.path.isfile(full) and _is_code_file(entry):
            code_files.append(full)

    result["total_files"] = len(code_files)
    result["files"] = code_files
    result["subdirs"] = subdirs

    # 大项目提示
    if max_files and result["total_files"] > max_files:
        logger.warning(f"目录 {dir_path} 包含 {result['total_files']} 个代码文件（超过 {max_files}），建议分步处理")

    return result


def iterate_project(project_path: str) -> None:
    """对整个项目执行 DFS 文件层迭代。

    按「先文件、后子目录」顺序处理：
      1. 处理当前目录所有代码文件
      2. 递归进入子目录
    """
    logger.info(f"开始迭代项目：{project_path}")
    # 当前目录下的文件和子目录
    info = walk_directory(project_path)
    logger.info(f"共 {info['total_files']} 个代码文件")

    # 再递归子目录（步骤3）
    for subdir in info["subdirs"]:
        iterate_project(subdir)

    # 先处理文件（步骤2）
    for file_path in info["files"]:
        try:
            process_file(file_path)
        except Exception as e:
            logger.error(f"处理文件失败：{file_path} - {e}")

    # ---- 目录级汇总（步骤3.2） ----  info就是 walk_directory 里列出来的，当前目录的文件和子目录
    _summarize_directory(project_path, info)


# ---------------------------------------------------------------------------
# 目录级汇总（步骤3.2）
# ---------------------------------------------------------------------------

def _summarize_directory(dir_path: str, info: dict) -> None:
    """汇总当前目录下所有文件和子目录的分析结果，生成模块概述。"""
    import json

    # 收集文件概述。file_analyses列表包含“文件名”“分析”两个字段
    file_analyses = []
    for file_path in info["files"]:
        base = os.path.join(
            os.path.dirname(file_path),
            os.path.basename(file_path) + ".解读",
        )
        # 加载解读文件路径
        overview_path = os.path.join(base, f"{os.path.basename(file_path)}.解读.md")
        # 把代码文件的整个分析文档加载出来
        content = _read_file_safe(overview_path)
        if content:
            file_analyses.append({"文件名": os.path.basename(file_path), "分析": content})

    # 收集子目录概述
    subdir_analyses = []
    for subdir in info["subdirs"]:
        dname = os.path.basename(subdir)
        overview_path = os.path.join(subdir, f"{dname}.解读.md")
        content = _read_file_safe(overview_path)
        if content:
            subdir_analyses.append({"目录名": dname, "分析": content})

    if not file_analyses and not subdir_analyses:
        return

    # AI 目录级汇总
    dir_input = json.dumps({
        "目录名": os.path.basename(dir_path) or dir_path,
        "文件分析": file_analyses,
        "子目录分析": subdir_analyses,
    }, ensure_ascii=False)

    prompt = f"""请根据目录下各文件和子目录的分析摘要，对目录进行整体解读。用 Markdown 格式输出：

# 模块解读：{os.path.basename(dir_path)}

## 模块职责
（汇总所有文件职责，用一两句话概括）

## 文件清单
| 文件 | 职责摘要 |
|------|---------|

## 子目录
| 目录 | 职责 |
|------|------|"""

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": dir_input},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    overview = response.choices[0].message.content

    # 写入
    dname = os.path.basename(dir_path.rstrip("/").rstrip("\\"))
    # 目录级解读存放的路径（不包含文件本身）
    dir_output = os.path.join(dir_path)
    os.makedirs(dir_output, exist_ok=True)
    # 目录级解读的文件
    with open(os.path.join(dir_output, f"{dname}.解读.md"), "w", encoding="utf-8") as f:
        f.write(overview)
    logger.info(f"  已写入目录概述：{dir_output}")


def _read_file_safe(path: str) -> str:
    """安全读取文件，不存在则返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _split_statements(code: str) -> list[str]:
    """启发式拆分函数体为语句列表。"""
    statements = []
    for line in code.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        if stripped in ("{", "}", "};"):
            continue
        statements.append(stripped)
    return statements


# ---------------------------------------------------------------------------
# AI 调用占位（ai_tasks.py 完成后替换）
# ---------------------------------------------------------------------------

def _analyze_file(file_path: str, macros: list, analyses: list) -> str:
    """AI 文件级汇总：职责概述、依赖关系、公开接口。"""
    import json

    with open(os.path.join(_PROMPT_DIR, "file_analysis_system_prompt.txt"), "r", encoding="utf-8") as f:
        file_analysis_prompt = f.read()

    # 区分外部和内部依赖
    external = [m for m in macros if m.startswith(("#include <", "import ", "from ")) and '"' not in m]
    internal = [m for m in macros if m not in external]

    # 提取函数/类摘要：直接传完整 analysis markdown
    func_summaries = []
    # analyses元素的类型，取决于_process_one_function()和process_one_class()的返回值。
    for a in analyses:
        func_summaries.append({
            "名称": a["name"],
            "类型": a.get("type", "function"),
            "分析": a.get("analysis", ""),
            "目标": a.get("目标", "") 
        })

    file_input = json.dumps({
        "文件名": os.path.basename(file_path),
        "依赖": {"外部": external, "内部": internal},
        "函数分析": func_summaries,
    }, ensure_ascii=False)

    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": file_analysis_prompt},
            {"role": "user", "content": file_input},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    print('文件 ', file_path, ' 已分析')
    return response.choices[0].message.content