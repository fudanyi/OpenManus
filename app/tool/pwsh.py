import asyncio
import codecs
import os
from typing import Optional

from app.exceptions import ToolError
from app.tool.base import BaseTool, CLIResult
from extensions.output import Output

_POWERSHELL_DESCRIPTION = """Execute a powershell command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
* Interactive: If a powershell command returns exit code `-1`, this means the process is not yet finished. The assistant must then send a second call to terminal with an empty `command` (which will retrieve any additional logs), or it can send additional text (set `command` to the text) to STDIN of the running process, or it can send command=`ctrl+c` to interrupt the process.
* Timeout: If a command execution result says "Command timed out. Sending SIGINT to the process", the assistant should retry running the command in the background.
"""


class _PowershellSession:
    """A session of a powershell shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "powershell.exe"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False

    async def start(self):
        if self._started:
            return

        # 在 Windows 系统上不使用 os.setsid
        preexec_fn = None
        if os.name != "nt":  # 如果不是 Windows 系统
            preexec_fn = os.setsid

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            preexec_fn=preexec_fn,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True

    def stop(self):
        """Terminate the powershell shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """Execute a command in the powershell shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"powershell has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: powershell has not returned in {self._timeout} seconds and must be restarted",
            )

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()

        # read output from the process, until the sentinel is found
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    # if we read directly from stdout/stderr, it will wait forever for
                    # EOF. use the StreamReader buffer directly instead.
                    try:
                        output = self._process.stdout._buffer.decode("utf-8")
                    except UnicodeDecodeError:
                        # 如果 UTF-8 解码失败，尝试使用 GBK 编码
                        try:
                            output = self._process.stdout._buffer.decode("gbk")
                        except UnicodeDecodeError:
                            # 如果 GBK 也失败，使用 'ignore' 错误处理
                            output = self._process.stdout._buffer.decode(
                                "utf-8", errors="ignore"
                            )

                    if self._sentinel in output:
                        # strip the sentinel and break
                        output = output[: output.index(self._sentinel)]
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"timed out: powershell has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]

        try:
            error = self._process.stderr._buffer.decode("utf-8")
        except UnicodeDecodeError:
            try:
                error = self._process.stderr._buffer.decode("gbk")
            except UnicodeDecodeError:
                error = self._process.stderr._buffer.decode("utf-8", errors="ignore")

        if error.endswith("\n"):
            error = error[:-1]

        Output.print(
            type="powershell",
            text=f"Powershell command output: {output}",
            data={
                "command": command,
                "output": output,
                "error": error,
            },
        )

        # clear the buffers so that the next output can be read correctly
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        return CLIResult(output=output, error=error)


class Powershell(BaseTool):
    """A tool for executing powershell commands"""

    name: str = "powershell"
    description: str = _POWERSHELL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The powershell command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
        },
        "required": ["command"],
    }

    _session: Optional[_PowershellSession] = None

    async def execute(
        self, command: str | None = None, restart: bool = False, **kwargs
    ) -> CLIResult:
        if restart:
            if self._session:
                self._session.stop()
            self._session = _PowershellSession()
            await self._session.start()

            return CLIResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _PowershellSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("no command provided.")


if __name__ == "__main__":
    powershell = Powershell()
    rst = asyncio.run(powershell.execute("ls -l"))
    print(rst)
