"""源码解读工具 CLI 入口。

目标分类：本地 / 远程 / 代码片段。
    层1 规则匹配（快速、零成本）→ 层2 AI 兜底（降价模型）
"""

import os
import re
import logging

from .ai_client import client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 目标分类：规则 → AI 兜底
# ---------------------------------------------------------------------------

_GIT_PATTERNS = [
    r"https?://.*github\.com",
    r"https?://.*gitlab\.",
    r"https?://bitbucket\.org",
    r"https?://gitee\.com",
    r"https?://codeberg\.org",
    r"https?://sourceforge\.net",
    r"^git@",
    r"^ssh://git@",
    r"^https://.*\.git$",
]


def classify_target(target: str) -> str:
    """判断目标类型。规则优先，无法判定时走 AI 兜底。

    Returns:
        "是本地链接" | "是Web链接" | "既不是本地链接，也不是Web链接"
    """
    # ---- 层1：规则匹配 ----

    if os.path.isdir(target) or os.path.isfile(target):
        return "是本地链接"

    if any(re.search(p, target) for p in _GIT_PATTERNS):
        return "是Web链接"

    # ---- 层2：AI 兜底 ----

    system_prompt = "请你判断用户发送给你的内容，是否为本地链接，或者为Web链接" + "\n"
    system_prompt += """
The user will provide content. You must choose one sample as your reply.

SAMPLE OUTPUT 1:
是本地链接

SAMPLE OUTPUT 2:
是Web链接

SAMPLE OUTPUT 3:
既不是本地链接，也不是Web链接
"""

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": target},
        ],
        stream=False,
        extra_body={"thinking": {"type": "enabled"}}
    )
    return response.choices[0].message.content


def local_path_type(path: str) -> str:
    """判断本地路径是文件还是文件夹。

    Returns:
        "文件" | "文件夹"
    """
    if os.path.isfile(path):
        return "文件"
    if os.path.isdir(path):
        return "文件夹"
    return "unknown"
