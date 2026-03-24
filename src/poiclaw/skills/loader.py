"""Skill 加载器"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .models import Skill

if TYPE_CHECKING:
    pass


class SkillLoader:
    """
    从目录加载 Skills。

    每个 .md 文件被视为一个 Skill，文件名（不含扩展名）作为技能名称。

    用法：
        loader = SkillLoader("skills/")
        skills = loader.load_all()

        # 或加载单个文件
        skill = loader.load("commit.md")
    """

    def __init__(self, skills_dir: str | Path = "skills"):
        """
        初始化加载器。

        Args:
            skills_dir: Skills 目录路径，默认为 "skills"
        """
        self.skills_dir = Path(skills_dir)

    def load_all(self) -> list[Skill]:
        """
        加载目录下所有 .md 文件作为 Skill。

        Returns:
            list[Skill]: 加载成功的技能列表
        """
        skills: list[Skill] = []

        if not self.skills_dir.exists():
            return skills

        for md_file in self.skills_dir.glob("*.md"):
            skill = self.load(md_file)
            if skill:
                skills.append(skill)

        return skills

    def load(self, file_path: str | Path) -> Skill | None:
        """
        加载单个 Skill 文件。

        Args:
            file_path: 文件路径（相对于 skills_dir 或绝对路径）

        Returns:
            Skill | None: 加载成功返回 Skill，失败返回 None
        """
        path = Path(file_path)

        # 如果是相对路径，相对于 skills_dir
        if not path.is_absolute():
            path = self.skills_dir / path

        if not path.exists():
            return None

        if not path.suffix == ".md":
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return Skill.from_markdown(content, path)
        except Exception as e:
            print(f"[SkillLoader] 加载 {path} 失败: {e}")
            return None

    def discover_dirs(self) -> list[Path]:
        """
        发现所有可能的 Skills 目录。

        搜索顺序：
        1. 当前目录下的 skills/
        2. 当前目录下的 .poiclaw/skills/
        3. 父目录递归查找

        Returns:
            list[Path]: 存在的 Skills 目录列表
        """
        dirs: list[Path] = []

        # 候选目录
        candidates = [
            self.skills_dir,
            Path(".poiclaw/skills"),
            Path("skills"),
        ]

        # 当前目录及父目录
        current = Path.cwd()
        for _ in range(5):  # 最多向上查找 5 层
            for candidate in candidates:
                full_path = current / candidate
                if full_path.exists() and full_path.is_dir():
                    if full_path not in dirs:
                        dirs.append(full_path)

            parent = current.parent
            if parent == current:
                break
            current = parent

        return dirs
