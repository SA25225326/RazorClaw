"""Skill 注册表"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .loader import SkillLoader
from .models import Skill

if TYPE_CHECKING:
    pass


class SkillRegistry:
    """
    Skill 注册表。

    管理所有已加载的 Skills，支持：
    - 从目录批量加载
    - 按名称查询
    - 生成简介列表（用于 system prompt）

    用法：
        registry = SkillRegistry()
        count = registry.load_from_dir("skills/")
        print(f"加载了 {count} 个技能")

        # 获取简介（注入 system prompt）
        brief = registry.to_brief_list()

        # 按需获取完整内容
        skill = registry.get("commit")
        if skill:
            print(skill.to_full_prompt())
    """

    def __init__(self) -> None:
        """初始化空注册表"""
        self._skills: dict[str, Skill] = {}

    def load_from_dir(self, skills_dir: str | Path) -> int:
        """
        从目录加载所有 Skills。

        Args:
            skills_dir: Skills 目录路径

        Returns:
            int: 成功加载的技能数量
        """
        loader = SkillLoader(skills_dir)
        skills = loader.load_all()

        for skill in skills:
            self._skills[skill.name] = skill

        return len(skills)

    def load_from_dirs(self, dirs: list[str | Path]) -> int:
        """
        从多个目录加载 Skills（后加载的会覆盖同名）。

        Args:
            dirs: 目录列表

        Returns:
            int: 总共加载的技能数量
        """
        total = 0
        seen_names: set[str] = set()

        for dir_path in dirs:
            loader = SkillLoader(dir_path)
            skills = loader.load_all()

            for skill in skills:
                if skill.name not in seen_names:
                    total += 1
                    seen_names.add(skill.name)
                self._skills[skill.name] = skill

        return total

    def register(self, skill: Skill) -> None:
        """
        注册单个 Skill。

        Args:
            skill: 要注册的技能
        """
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """
        注销 Skill。

        Args:
            name: 技能名称

        Returns:
            bool: 是否成功注销
        """
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Skill | None:
        """
        获取 Skill。

        Args:
            name: 技能名称

        Returns:
            Skill | None: 技能对象，不存在则返回 None
        """
        return self._skills.get(name)

    def has(self, name: str) -> bool:
        """
        检查 Skill 是否存在。

        Args:
            name: 技能名称

        Returns:
            bool: 是否存在
        """
        return name in self._skills

    def get_all(self) -> list[Skill]:
        """
        获取所有 Skills。

        Returns:
            list[Skill]: 所有技能列表
        """
        return list(self._skills.values())

    def get_all_names(self) -> list[str]:
        """
        获取所有技能名称。

        Returns:
            list[str]: 技能名称列表
        """
        return list(self._skills.keys())

    def to_brief_list(self) -> str:
        """
        返回所有 Skill 的简要描述（用于初始注入 system prompt）。

        这是渐进式披露的关键：只注入名称和一句话描述，
        节省 Token，需要时用 read_skill 加载完整内容。

        Returns:
            str: 简要描述列表
        """
        if not self._skills:
            return ""

        briefs = [skill.to_brief() for skill in self._skills.values()]
        return "可用技能（使用 read_skill 加载详情）:\n" + "\n".join(briefs)

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def get_all(self) -> list[Skill]:
        """获取所有技能"""
        return list(self._skills.values())
