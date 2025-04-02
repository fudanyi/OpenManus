import multiprocessing
import sys
from io import StringIO
from typing import Dict

from app.tool.base import BaseTool


class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = (
        "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results.\n"
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "output_files": {
                "type": "array",
                "description": "The files to output.",
                "items": {
                    "type": "string",
                },
            },
            "charts": {
                "type": "array", 
                "description": "The charts to output.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the chart"
                        },
                        "image_file": {
                            "type": "string", 
                            "description": "The output image file path"
                        },
                        "config_file": {
                            "type": "string",
                            "description": "The chart configuration JSON's file path"
                        }
                    },
                    "required": ["name", "image_file", "config_file"]
                }
            },
        },
        "required": ["code", "output_files", "charts"],
    }

    def _run_code(self, code: str, result_dict: dict, safe_globals: dict) -> None:
        original_stdout = sys.stdout
        try:
            output_buffer = StringIO()
            sys.stdout = output_buffer
            exec(code, safe_globals, safe_globals)
            result_dict["observation"] = output_buffer.getvalue()
            result_dict["success"] = True
        except Exception as e:
            result_dict["observation"] = str(e)
            result_dict["success"] = False
            result_dict["output_files"] = []
            result_dict["charts"] = []
        finally:
            sys.stdout = original_stdout

    async def execute(
        self,
        code: str,
        output_files: list,
        charts: list,
        timeout: int = 150,
    ) -> Dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            timeout (int): Execution timeout in seconds.
            output_files (list): The files to output.
        Returns:
            Dict: Contains 'output' with execution output or error message and 'success' status.
        """

        # Remove output files that are already in charts to avoid duplicates
        chart_files = set()
        for chart in charts:
            chart_files.add(chart["image_file"])
            chart_files.add(chart["config_file"])
        
        output_files = [f for f in output_files if f not in chart_files]

        with multiprocessing.Manager() as manager:
            result = manager.dict(
                {"observation": "", "success": False, "output_files": output_files, "charts": charts}
            )
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": __builtins__}
            else:
                safe_globals = {"__builtins__": __builtins__.__dict__.copy()}
            proc = multiprocessing.Process(
                target=self._run_code, args=(code, result, safe_globals)
            )
            proc.start()
            proc.join(timeout)

            # timeout process
            if proc.is_alive():
                proc.terminate()
                proc.join(1)
                return {
                    "observation": f"Execution timeout after {timeout} seconds",
                    "success": False,
                    "output_files": output_files,
                    "charts": charts,
                }
            return dict(result)
