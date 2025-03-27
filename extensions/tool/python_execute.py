from extensions.prompt import table, chart
from app.tool.python_execute import PythonExecute


class PythonExecute(PythonExecute):
    """Specialized version of PythonExecute tool."""

    name: str = "python_execute"
    description: str = (
        "Executes Python code string in data analysis task, save data table in csv file. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results.\n"
        + table.PROMPT + "\n"
        + chart.PROMPT
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
        },
        "required": ["code", "output_files"],
    }

    async def execute(self, code: str, output_files: list, timeout: int = 150) -> dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            output_files (list): The files to output.
            timeout (int): Execution timeout in seconds.

        Returns:
            Dict: Contains 'output' with execution output or error message and 'success' status.
        """
        return await super().execute(code, output_files, timeout)
