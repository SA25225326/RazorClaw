"""
Skills 模块 - 渐进式技能加载系统。

提供按需加载的能力包，遵循 Agent Skills 标准。
每个 Skill 是一个 Markdown 文件，包含触发条件、指令和示例。

用法：
    from poiclaw.skills import SkillRegistry, Skill, SkillLoader

    # 从目录加载
    registry = SkillRegistry()
    count = registry.load_from_dir("skills/")

    # 获取简介（注入 system prompt）
    brief = registry.to_brief_list()

    # 按需获取完整内容
    skill = registry.get("commit")
    if skill:
        print(skill.to_full_prompt())
"""

from .loader import SkillLoader
from .models import Skill
from .registry import SkillRegistry

__all__ = [
    "Skill",
    "SkillLoader",
    "SkillRegistry",
]
