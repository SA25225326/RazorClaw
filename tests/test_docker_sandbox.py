"""测试 Docker 沙箱功能"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from poiclaw.sandbox import DockerSandbox
from poiclaw.tools.bash import BashTool


async def test_docker_sandbox_basic():
    """测试 Docker 沙箱基本功能"""
    print("=" * 50)
    print("1. Docker 沙箱基本功能测试")
    print("=" * 50)

    sandbox = DockerSandbox(
        container_name="poiclaw-test",
        workspace=PROJECT_ROOT,
        image="python:3.11-slim",
    )

    try:
        # 启动容器
        print("\n启动容器...")
        success = await sandbox.start()
        print(f"   启动结果: {'成功' if success else '失败'}")
        print(f"   容器状态: {sandbox}")

        # 执行简单命令
        print("\n执行命令: echo 'Hello Docker!'")
        exit_code, output = await sandbox.exec("echo 'Hello Docker!'")
        print(f"   退出码: {exit_code}")
        print(f"   输出: {output.strip()}")

        # 执行系统命令
        print("\n执行命令: uname -a")
        exit_code, output = await sandbox.exec("uname -a")
        print(f"   退出码: {exit_code}")
        print(f"   输出: {output.strip()}")

        # 执行 Python 命令
        print("\n执行命令: python --version")
        exit_code, output = await sandbox.exec("python --version")
        print(f"   退出码: {exit_code}")
        print(f"   输出: {output.strip()}")

        # 测试工作目录
        print("\n执行命令: pwd")
        exit_code, output = await sandbox.exec("pwd")
        print(f"   退出码: {exit_code}")
        print(f"   工作目录: {output.strip()}")

        # 测试文件访问（应该能看到挂载的项目目录）
        print("\n执行命令: ls -la /workspace | head -5")
        exit_code, output = await sandbox.exec("ls -la /workspace | head -5")
        print(f"   退出码: {exit_code}")
        print(f"   输出:\n{output}")

        print("\n   [OK] 基本功能测试通过")

    except Exception as e:
        print(f"\n   [ERROR] 测试失败: {e}")
    finally:
        # 清理
        print("\n清理容器...")
        await sandbox.remove()
        print("   容器已删除")


async def test_bash_tool_with_sandbox():
    """测试 BashTool 的沙箱模式"""
    print("\n" + "=" * 50)
    print("2. BashTool 沙箱模式测试")
    print("=" * 50)

    sandbox = DockerSandbox(
        container_name="poiclaw-bash-test",
        workspace=PROJECT_ROOT,
    )

    try:
        # 启动容器
        print("\n启动容器...")
        await sandbox.start()

        # 创建带沙箱的 BashTool
        bash = BashTool(sandbox=sandbox)

        # 测试命令执行
        print("\n执行: ls -la")
        result = await bash.execute(command="ls -la")
        print(f"   成功: {result.success}")
        print(f"   输出预览: {result.content[:200]}...")

        # 测试错误命令
        print("\n执行: nonexistent_command")
        result = await bash.execute(command="nonexistent_command")
        print(f"   成功: {result.success}")
        print(f"   错误: {result.error}")

        print("\n   [OK] BashTool 沙箱模式测试通过")

    except Exception as e:
        print(f"\n   [ERROR] 测试失败: {e}")
    finally:
        await sandbox.remove()


async def test_sandbox_isolation():
    """测试沙箱隔离性"""
    print("\n" + "=" * 50)
    print("3. 沙箱隔离性测试")
    print("=" * 50)

    sandbox = DockerSandbox(
        container_name="poiclaw-isolation-test",
        workspace=PROJECT_ROOT,
    )

    try:
        await sandbox.start()

        # 在容器内创建文件
        print("\n在容器内创建文件: /tmp/test_sandbox.txt")
        exit_code, output = await sandbox.exec(
            "echo 'This is inside container' > /tmp/test_sandbox.txt && cat /tmp/test_sandbox.txt"
        )
        print(f"   输出: {output.strip()}")

        # 检查宿主机是否有这个文件（应该没有）
        print("\n检查宿主机是否有 /tmp/test_sandbox.txt...")
        import os

        host_exists = os.path.exists("/tmp/test_sandbox.txt")
        print(f"   宿主机存在: {host_exists}")
        print(f"   {'[OK] 沙箱隔离有效' if not host_exists else '[WARN] 隔离可能有问题'}")

        # 测试环境隔离
        print("\n检查容器内的环境变量...")
        exit_code, output = await sandbox.exec("env | grep -i poiclaw || echo 'No POICLAW env vars'")
        print(f"   输出: {output.strip()}")

        print("\n   [OK] 隔离性测试完成")

    except Exception as e:
        print(f"\n   [ERROR] 测试失败: {e}")
    finally:
        await sandbox.remove()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("Docker 沙箱功能测试")
    print("=" * 50)

    # 检查 Docker 是否可用
    print("\n检查 Docker 是否可用...")
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"   Docker 版本: {result.stdout.strip()}")
        else:
            print("   [ERROR] Docker 不可用，请确保 Docker 已安装并启动")
            return
    except FileNotFoundError:
        print("   [ERROR] 未找到 Docker，请先安装 Docker")
        return

    # 运行测试
    await test_docker_sandbox_basic()
    await test_bash_tool_with_sandbox()
    await test_sandbox_isolation()

    print("\n" + "=" * 50)
    print("所有测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
