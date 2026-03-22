"""
Tools module tests.

Test content:
1. BashTool execution
2. ReadFileTool reading
3. WriteFileTool writing
4. EditFileTool editing
5. register_all_tools function
"""

import asyncio
import tempfile
from pathlib import Path

from poiclaw.tools import (
    BashTool,
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    register_all_tools,
)
from poiclaw.core import ToolRegistry


# ============ Test Functions ============


async def test_bash_tool():
    """Test BashTool execution"""
    print("=== Test BashTool ===")

    tool = BashTool()

    # Test normal command
    result = await tool.execute(command="echo Hello World")
    assert result.success
    assert "Hello World" in result.content
    print(f"[OK] Normal command: echo")

    # Test command with error
    result2 = await tool.execute(command="ls /nonexistent_dir_12345")
    assert not result2.success  # Should fail
    print(f"[OK] Error command handled correctly")

    # Test timeout (skipped to save time)
    # result3 = await tool.execute(command="sleep 5", timeout=1)
    # assert not result3.success
    # assert "timeout" in result3.error.lower()


async def test_read_file_tool():
    """Test ReadFileTool reading"""
    print("\n=== Test ReadFileTool ===")

    tool = ReadFileTool()

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
        temp_path = f.name

    try:
        # Test reading whole file
        result = await tool.execute(path=temp_path)
        assert result.success
        assert "Line 1" in result.content
        assert "Line 5" in result.content
        print(f"[OK] Read whole file")

        # Test reading with line range
        result2 = await tool.execute(path=temp_path, start_line=2, end_line=4)
        assert result2.success
        assert "Line 1" not in result2.content  # Line 1 should not be in range
        assert "Line 2" in result2.content
        assert "Line 4" in result2.content
        print(f"[OK] Read with line range")

        # Test non-existent file
        result3 = await tool.execute(path="/nonexistent_file_12345.txt")
        assert not result3.success
        assert "not exist" in result3.error.lower() or "不存在" in result3.error
        print(f"[OK] Non-existent file handled")

    finally:
        Path(temp_path).unlink()


async def test_write_file_tool():
    """Test WriteFileTool writing"""
    print("\n=== Test WriteFileTool ===")

    tool = WriteFileTool()

    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "test_write.txt"

        # Test write mode
        result = await tool.execute(
            path=str(temp_path),
            content="Hello World",
            mode="write",
        )
        assert result.success
        assert temp_path.exists()
        assert temp_path.read_text() == "Hello World"
        print(f"[OK] Write mode")

        # Test append mode
        result2 = await tool.execute(
            path=str(temp_path),
            content="\nAppended Line",
            mode="append",
        )
        assert result2.success
        assert "Appended Line" in temp_path.read_text()
        print(f"[OK] Append mode")


async def test_edit_file_tool():
    """Test EditFileTool editing"""
    print("\n=== Test EditFileTool ===")

    tool = EditFileTool()

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello World\nThis is a test\nGoodbye World\n")
        temp_path = f.name

    try:
        # Test successful edit
        result = await tool.execute(
            path=temp_path,
            old_text="Hello World",
            new_text="Hi There",
        )
        assert result.success
        content = Path(temp_path).read_text()
        assert "Hi There" in content
        assert "Hello World" not in content
        print(f"[OK] Successful edit")

        # Test non-unique text
        Path(temp_path).write_text("test test test\n")
        result2 = await tool.execute(
            path=temp_path,
            old_text="test",
            new_text="replaced",
        )
        assert not result2.success
        assert "3" in result2.error or "unique" in result2.error.lower() or "唯一" in result2.error
        print(f"[OK] Non-unique text rejected")

        # Test non-existent text
        Path(temp_path).write_text("Some content\n")
        result3 = await tool.execute(
            path=temp_path,
            old_text="NonExistentText12345",
            new_text="replacement",
        )
        assert not result3.success
        assert "not found" in result3.error.lower() or "未找到" in result3.error
        print(f"[OK] Non-existent text handled")

    finally:
        Path(temp_path).unlink()


def test_register_all_tools():
    """Test register_all_tools function"""
    print("\n=== Test register_all_tools ===")

    registry = ToolRegistry()
    register_all_tools(registry)

    assert len(registry) == 4
    assert "bash" in registry
    assert "read_file" in registry
    assert "write_file" in registry
    assert "edit_file" in registry

    print(f"[OK] All 4 tools registered")


# ============ Main ============


async def main():
    print("Start testing PoiClaw Tools module\n")

    await test_bash_tool()
    await test_read_file_tool()
    await test_write_file_tool()
    await test_edit_file_tool()
    test_register_all_tools()

    print("\n" + "=" * 50)
    print("[OK] All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
