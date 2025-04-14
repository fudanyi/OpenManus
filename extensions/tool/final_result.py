import os
import json
from pathlib import Path
from typing import Optional
from extensions.prompt import chart, table
import plotly.io as pio
import streamlit as st
from app.tool.base import BaseTool, ToolResult
from pydantic import Field
import asyncio
import tomli
from extensions.output import Output

# Load configuration
config_path = Path(__file__).parent.parent.parent / "config/config.toml"
with open(config_path, "rb") as f:
    config = tomli.load(f)


class FinalResult(BaseTool):
    """Tool for generating final reports, slides, and dashboards."""

    name: str = "final_result"
    description: str = (
        "Generates final deliverables including reports, slides, and dashboards. "
        + table.PROMPT
        + "\n"
        + chart.PROMPT
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "The action to perform: gen_report, gen_slides, or gen_dashboard",
                "enum": ["gen_report", "gen_slides", "gen_dashboard"],
            },
            "title": {
                "type": "string",
                "description": "Short title of the final deliverable",
            },
            "content": {
                "type": "string",
                "description": 'The content to process depend on action: 1. MDX for gen_report with charts using JSX component(like <InteractivePlotly config="chart_config.json" />), 2. Slidev markdown for gen_slides and mermaid diagrams, 3. Streamlit python code for gen_dashboard)',
            },
            "filename": {
                "type": "string",
                "description": "The output filename without extension",
            },
        },
        "required": ["action", "content", "filename", "title"],
    }

    def __init__(self, **data):
        super().__init__(**data)

    async def execute(self, action: str, content: str, filename: str, title: str) -> ToolResult:
        """
        Executes the specified action to generate final deliverables.

        Args:
            action (str): The action to perform (gen_report, gen_slides, or gen_dashboard)
            content (str): The content to process
            filename (str): The output filename without extension

        Returns:
            ToolResult: Contains status and output file paths
        """
        try:

            if action == "gen_report":
                result = await self._gen_report(content, filename, title)
            elif action == "gen_slides":
                result = await self._gen_slides(content, filename, title)
            elif action == "gen_dashboard":
                result = await self._gen_dashboard(content, filename, title)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}

            if result.get("success", False):
                return result
            else:
                return {"success": False, "error": result.get("error", "Unknown error")}
        except Exception as e:
            return ToolResult(error=str(e))

    async def _gen_report(self, content: str, filename: str, title: str) -> dict:
        """Generates a final report in MDX format."""
        try:
            output_path = Path(f"{filename}.mdx")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {
                "success": True,
                "report_url": f"http://{config['servers']['mdx_host']}:{config['servers']['mdx_port']}/?filename={Path(output_path).stem}&session_id={Output._current_session_id}",
                "title": title,
            }
        except IOError as e:
            return {
                "success": False,
                "title": title,
                "error": f"Failed to write MDX file: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "title": title,
                "error": f"Unexpected error generating report: {str(e)}",
            }

    async def _gen_slides(self, content: str, filename: str, title: str) -> dict:
        """Generates slides using Slidev and exports to PPTX."""
        # Save the Slidev markdown
        # Save slides content to slides.md
        md_path = Path("slides.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Export to PPTX using slidev CLI command
        pptx_path = Path(f"{filename}.pptx")
        cmd = f"slidev export --format pptx --output {filename}.pptx"
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {
                "success": False,
                "title": title,
                "error": f"Slidev export failed: {stderr.decode()}",
            }

        return {
            "success": True,
            "title": title,
            "markdown_file": str(md_path),
            "pptx_file": str(pptx_path),
        }

    async def _gen_dashboard(self, content: str, filename: str, title: str) -> dict:
        """Saves a Streamlit dashboard implementation."""
        output_path = Path(f"{filename}.py")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "title": title,
            "dash_url": f"http://{config['servers']['streamlit_host']}:{config['servers']['streamlit_port']}/?file={Path(output_path).stem}&session_id={Output._current_session_id}",
        }
