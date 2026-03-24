"""Docker 容器管理器"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DockerSandbox:
    """
    Docker 沙箱 - 命令在容器内隔离执行。

    用法：
        sandbox = DockerSandbox(workspace="/path/to/project")
        await sandbox.start()

        # 在容器内执行命令
        exit_code, output = await sandbox.exec("ls -la")

        # 清理
        await sandbox.remove()

    特点：
        - 完全隔离：命令在 Docker 容器内执行，不影响宿主机
        - 工作目录挂载：项目目录挂载到容器的 /workspace
        - 可配置镜像：默认使用 python:3.11-slim
        - 超时控制：支持命令执行超时
    """

    def __init__(
        self,
        container_name: str = "poiclaw-sandbox",
        workspace: str | Path = ".",
        image: str = "python:3.11-slim",
    ):
        """
        初始化 Docker 沙箱。

        Args:
            container_name: 容器名称，默认 "poiclaw-sandbox"
            workspace: 工作目录（会挂载到容器的 /workspace）
            image: Docker 镜像，默认 "python:3.11-slim"
        """
        self.container_name = container_name
        self.workspace = Path(workspace).resolve()
        self.image = image
        self._started = False

    @property
    def is_running(self) -> bool:
        """检查容器是否正在运行"""
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={self.container_name}"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())

    @property
    def exists(self) -> bool:
        """检查容器是否存在（包括已停止的）"""
        result = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", f"name={self.container_name}"],
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())

    async def start(self) -> bool:
        """
        启动容器。

        如果容器已存在但停止了，会重新启动。
        如果容器不存在，会创建新容器。

        Returns:
            bool: 是否成功启动
        """
        try:
            # 检查是否已存在
            if self.exists:
                logger.info(f"容器 {self.container_name} 已存在，启动它")
                subprocess.run(
                    ["docker", "start", self.container_name],
                    capture_output=True,
                    check=True,
                )
                self._started = True
                return True

            # 创建新容器
            logger.info(f"创建新容器 {self.container_name}，镜像: {self.image}")
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self.container_name,
                    "-v",
                    f"{self.workspace}:/workspace",
                    "-w",
                    "/workspace",
                    self.image,
                    "tail",
                    "-f",
                    "/dev/null",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"容器创建成功: {result.stdout.strip()}")
            self._started = True
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"启动容器失败: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error("Docker 未安装或未启动")
            return False

    async def stop(self) -> bool:
        """
        停止容器（不删除）。

        Returns:
            bool: 是否成功停止
        """
        try:
            subprocess.run(
                ["docker", "stop", self.container_name],
                capture_output=True,
                check=False,
            )
            self._started = False
            return True
        except FileNotFoundError:
            return False

    async def remove(self) -> bool:
        """
        删除容器（包括停止）。

        Returns:
            bool: 是否成功删除
        """
        try:
            subprocess.run(
                ["docker", "rm", "-f", self.container_name],
                capture_output=True,
                check=False,
            )
            self._started = False
            return True
        except FileNotFoundError:
            return False

    async def exec(self, command: str, timeout: int | None = None) -> tuple[int, str]:
        """
        在容器内执行命令。

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒），None 表示不限制

        Returns:
            tuple[int, str]: (exit_code, output)

        Raises:
            RuntimeError: 容器未启动
            asyncio.TimeoutError: 执行超时
        """
        if not self.is_running:
            raise RuntimeError(f"容器 {self.container_name} 未运行，请先调用 start()")

        try:
            # 使用 asyncio 包装同步的 subprocess
            process = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                self.container_name,
                "bash",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += stderr.decode("utf-8", errors="replace")

            return process.returncode or 0, output

        except FileNotFoundError:
            raise RuntimeError("Docker 未安装或未启动")

    async def exec_with_stream(
        self,
        command: str,
        timeout: int | None = None,
    ):
        """
        在容器内执行命令，流式返回输出。

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）

        Yields:
            str: 输出行
        """
        if not self.is_running:
            raise RuntimeError(f"容器 {self.container_name} 未运行")

        process = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            self.container_name,
            "bash",
            "-c",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            assert process.stdout
            async for line in process.stdout:
                yield line.decode("utf-8", errors="replace")

            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return f"DockerSandbox(name={self.container_name}, status={status}, image={self.image})"
