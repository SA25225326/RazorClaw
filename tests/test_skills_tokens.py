"""测试 Skills 系统 Token 节省效果"""

import sys
from pathlib import Path

# 确保能找到项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poiclaw.skills import Skill, SkillLoader, SkillRegistry

SKILLS_DIR = PROJECT_ROOT / "skills"


def count_tokens(text: str) -> int:
    """估算 token 数量（4 字符 ≈ 1 token）"""
    return len(text) // 4


def test_skill_parsing():
    """测试 Skill 解析"""
    print("=" * 50)
    print("1. Skill 解析测试")
    print("=" * 50)

    skill_path = SKILLS_DIR / "commit.md"
    if not skill_path.exists():
        print(f"   跳过: {skill_path} 不存在")
        return

    content = skill_path.read_text(encoding="utf-8")
    skill = Skill.from_markdown(content, skill_path)

    print(f"   名称: {skill.name}")
    print(f"   触发条件: {skill.trigger_conditions[:50]}...")
    print(f"   指令: {skill.instructions[:50]}...")
    print(f"   示例: {skill.examples[:50]}...")
    print("   [OK] 解析成功")


def test_skill_loader():
    """测试 Skill 加载器"""
    print("\n" + "=" * 50)
    print("2. SkillLoader 测试")
    print("=" * 50)

    loader = SkillLoader(SKILLS_DIR)
    skills = loader.load_all()

    print(f"   加载数量: {len(skills)}")
    for skill in skills:
        print(f"   - {skill.name}")
    print("   [OK] 加载成功")


def test_skill_registry():
    """测试 Skill 注册表"""
    print("\n" + "=" * 50)
    print("3. SkillRegistry 测试")
    print("=" * 50)

    registry = SkillRegistry()
    count = registry.load_from_dir(SKILLS_DIR)

    print(f"   加载数量: {count}")
    print(f"   技能列表: {registry.get_all_names()}")

    skill = registry.get("commit")
    if skill:
        print(f"   获取 commit: [OK]")
    else:
        print(f"   获取 commit: [FAIL]")

    brief = registry.to_brief_list()
    print(f"\n   简介内容:\n{brief}")

    print("\n   [OK] 注册表测试通过")


def test_skills_token_savings():
    """测试 Token 节省效果"""
    print("\n" + "=" * 50)
    print("4. Token 节省测试")
    print("=" * 50)

    registry = SkillRegistry()
    count = registry.load_from_dir(SKILLS_DIR)

    if count == 0:
        print("   跳过: 没有加载到技能")
        return

    # 简介长度
    brief = registry.to_brief_list()
    brief_tokens = count_tokens(brief)

    # 完整内容长度
    full_parts = []
    for skill in registry.get_all():
        full_parts.append(skill.to_full_prompt())
    full_content = "\n\n".join(full_parts)
    full_tokens = count_tokens(full_content)

    # 计算节省
    if full_tokens > 0:
        saved = (full_tokens - brief_tokens) / full_tokens * 100
    else:
        saved = 0

    print(f"   加载技能数: {count}")
    print(f"   简介长度: {len(brief)} 字符 (~{brief_tokens} tokens)")
    print(f"   完整长度: {len(full_content)} 字符 (~{full_tokens} tokens)")
    print(f"   Token 节省: {saved:.1f}%")
    print(f"   节省绝对值: {full_tokens - brief_tokens} tokens")

    if saved > 50:
        print("   [OK] 渐进式加载效果显著 (>50%)")
    else:
        print("   [WARN] 渐进式加载效果一般")


def test_skill_brief_format():
    """测试 Skill 简介格式"""
    print("\n" + "=" * 50)
    print("5. Skill 简介格式测试")
    print("=" * 50)

    registry = SkillRegistry()
    registry.load_from_dir(SKILLS_DIR)

    for skill in registry.get_all():
        brief = skill.to_brief()
        print(f"   {brief}")

    print("   [OK] 格式测试完成")


def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("Skills 系统 Token 测试")
    print("=" * 50)

    test_skill_parsing()
    test_skill_loader()
    test_skill_registry()
    test_skills_token_savings()
    test_skill_brief_format()

    print("\n" + "=" * 50)
    print("所有测试完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
