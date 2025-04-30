import os
import json
from pathlib import Path
from typing import Optional, List
from app.tool.base import BaseTool, ToolResult
from pydantic import Field
import asyncio
from enum import Enum

class DeliverableType(str, Enum):
    WEBPAGE = "webpage"
    CHART = "chart"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DATA = "data"
    OTHER = "other"

class ResultReporter(BaseTool):
    """Tool for reporting deliverables."""

    name: str = "result_reporter"
    description: str = (
        "Adds and reports deliverables including reports, slides, dashboards, charts, markdown, HTML, and other types. "
        "<guidelines>"
        "1. for json and image files having the same name, report only once as chart with the json filename. The image with same name is ignored"
        "2. for html/css/js that work together, report only once as webpage with the html filename. "
        "</guidelines>"
        "Use this tool to report final results and deliverables at the end of a plan execution."
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "The action to perform: report_deliverables",
                "enum": ["report_deliverables"],
            },
            "deliverables": {
                "type": "array",
                "description": "List of deliverables to report",
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "is_main": {"type": "boolean"},
                        "type": {
                            "type": "string",
                            "enum": [t.value for t in DeliverableType]
                        }
                    },
                    "required": ["filename", "title", "description", "type"]
                }
            }
        },
        "required": ["action", "deliverables"],
    }

    deliverables: List[dict] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)

    async def execute(
        self,
        action: str,
        deliverables: List[dict],
    ) -> ToolResult:
        """
        Executes the specified action to manage deliverables.

        Args:
            action: The action to perform
            deliverables: List of deliverables to report

        Returns:
            ToolResult: Contains status and results
        """
        try:
            if action == "report_deliverables":
                result = await self._report_deliverables(deliverables)
            else:
                return ToolResult(error=f"Unknown action: {action}")

            if result.get("success", False):
                return ToolResult(data=result)
            else:
                return ToolResult(error=result.get("error", "Unknown error"))
        except Exception as e:
            return ToolResult(error=str(e))

    async def _report_deliverables(self, deliverables: List[dict]) -> dict:
        """Reports multiple deliverables."""
        try:
            reported_deliverables = []
            for deliverable in deliverables:
                if not all(key in deliverable for key in ["filename", "title", "description", "type"]):
                    return {
                        "success": False,
                        "error": f"Missing required fields in deliverable: {deliverable}"
                    }
                
                # Validate type
                try:
                    deliverable_type = DeliverableType(deliverable["type"])
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid type '{deliverable['type']}' in deliverable: {deliverable}"
                    }
                
                processed_deliverable = {
                    "filename": deliverable["filename"],
                    "title": deliverable["title"],
                    "description": deliverable["description"],
                    "is_main": deliverable.get("is_main", False),
                    "type": deliverable_type.value
                }
                self.deliverables.append(processed_deliverable)
                reported_deliverables.append(processed_deliverable)

            return {
                "success": True,
                "reported_count": len(reported_deliverables),
                "deliverables": reported_deliverables
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to report deliverables: {str(e)}"
            }
