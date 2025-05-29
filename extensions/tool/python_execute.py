from extensions.prompt import table, chart
from app.tool.python_execute import PythonExecute


class PythonExecute(PythonExecute):
    """Specialized version of PythonExecute tool."""

    name: str = "python_execute"
    description: str = (
        "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results.\n"
        + table.PROMPT
        + "\n"
        + chart.PROMPT
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Short title of the task",
            },
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "output_files": {
                "type": "array",
                "description": "The files to output, excluding files in charts parameter.",
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
                            "description": "The name of the chart",
                        },
                        "image_file": {
                            "type": "string",
                            "description": "The output image file path",
                        },
                        "config_file": {
                            "type": "string",
                            "description": "The chart configuration JSON's file path",
                        },
                    },
                    "required": ["name", "image_file", "config_file"],
                },
            },
        },
        "required": ["code", "output_files", "charts"],
    }
