# tool/planning.py
from typing import Dict, List, Literal, Optional

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolResult
from extensions.output import Output


_PLANNING_TOOL_DESCRIPTION = """
A planning tool that allows the agent to create and manage plans for solving complex tasks.
The tool provides functionality for creating plans, updating plan steps, and tracking progress.
Plans are organized into sections, with each section containing multiple steps.
"""


class PlanningTool(BaseTool):
    """
    A planning tool that allows the agent to create and manage plans for solving complex tasks.
    The tool provides functionality for creating plans, updating plan steps, and tracking progress.
    Plans are organized into sections, with each section containing multiple steps.
    """

    name: str = "planning"
    description: str = _PLANNING_TOOL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The command to execute. Available commands: create, update, get.",
                "enum": [
                    "create",
                    "update",
                    "get",
                ],
                "type": "string",
            },
            "plan_id": {
                "description": "Unique identifier for the plan. Required for create, update, set_active, and delete commands. Optional for get and mark_step (uses active plan if not specified).",
                "type": "string",
            },
            "title": {
                "description": "Title for the plan. Required for create command, optional for update command.",
                "type": "string",
            },
            "sections": {
                "description": "List of sections, each containing a title, steps and types of steps. Required for create command, optional for update command.",
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "types": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["title", "steps"]
                }
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    plans: dict = {}  # Dictionary to store plans by plan_id
    _current_plan_id: Optional[str] = None  # Track the current active plan

    async def execute(
        self,
        *,
        command: Literal[
            "create", "update", "list", "get", "set_active", "mark_step", "delete"
        ],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        sections: Optional[List[Dict]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[
            Literal["not_started", "in_progress", "completed", "blocked"]
        ] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ):
        """
        Execute the planning tool with the given command and parameters.

        Parameters:
        - command: The operation to perform
        - plan_id: Unique identifier for the plan
        - title: Title for the plan (used with create command)
        - sections: List of sections, each containing a title and steps (used with create command)
        - step_index: Index of the step to update (used with mark_step command)
        - step_status: Status to set for a step (used with mark_step command)
        - step_notes: Additional notes for a step (used with mark_step command)
        """

        if command == "create":
            return self._create_plan(plan_id, title, sections)
        elif command == "update":
            return self._update_plan(plan_id, title, sections)
        elif command == "list":
            return self._list_plans()
        elif command == "get":
            return self._get_plan(plan_id)
        elif command == "set_active":
            return self._set_active_plan(plan_id)
        elif command == "mark_step":
            return self._mark_step(plan_id, step_index, step_status, step_notes)
        elif command == "delete":
            return self._delete_plan(plan_id)
        else:
            raise ToolError(
                f"Unrecognized command: {command}. Allowed commands are: create, update, list, get, set_active, mark_step, delete"
            )

    def _create_plan(
        self, plan_id: Optional[str], title: Optional[str], sections: Optional[List[Dict]]
    ) -> ToolResult:
        """Create a new plan with the given ID, title, and sections."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: create")

        if plan_id in self.plans:
            raise ToolError(
                f"A plan with ID '{plan_id}' already exists. Use 'update' to modify existing plans."
            )

        if not title:
            raise ToolError("Parameter `title` is required for command: create")

        if not sections or not isinstance(sections, list):
            raise ToolError(
                "Parameter `sections` must be a non-empty list for command: create"
            )

        # Validate sections structure
        for section in sections:
            if not isinstance(section, dict) or "title" not in section or "steps" not in section:
                raise ToolError("Each section must be a dictionary with 'title' and 'steps' keys")
            if not isinstance(section["steps"], list) or not all(isinstance(step, str) for step in section["steps"]):
                raise ToolError("Each section's steps must be a list of strings")

        # Create a new plan with initialized step statuses and notes
        plan = {
            "plan_id": plan_id,
            "title": title,
            "sections": sections,
            "step_statuses": [],
            "step_notes": [],
        }

        # Initialize statuses and notes for all steps
        for section in sections:
            for _ in section["steps"]:
                plan["step_statuses"].append("not_started")
                plan["step_notes"].append("")

        Output.print(
            type="createPlan",
            text=f"计划 {plan_id} 创建完毕",
            data=plan,
        )

        self.plans[plan_id] = plan
        self._current_plan_id = plan_id  # Set as active plan

        return ToolResult(
            output=f"Plan created successfully with ID: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _update_plan(
        self, plan_id: Optional[str], title: Optional[str], sections: Optional[List[Dict]]
    ) -> ToolResult:
        """Update an existing plan with new title or sections."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: update")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]

        if title:
            plan["title"] = title

        if sections:
            if not isinstance(sections, list):
                raise ToolError("Parameter `sections` must be a list for command: update")

            # Validate sections structure
            for section in sections:
                if not isinstance(section, dict) or "title" not in section or "steps" not in section:
                    raise ToolError("Each section must be a dictionary with 'title' and 'steps' keys")
                if not isinstance(section["steps"], list) or not all(isinstance(step, str) for step in section["steps"]):
                    raise ToolError("Each section's steps must be a list of strings")

            # Preserve existing step statuses and notes
            old_sections = plan["sections"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]

            # Create new step statuses and notes
            new_statuses = []
            new_notes = []

            # Map old steps to their indices
            old_step_map = {}
            current_index = 0
            for section in old_sections:
                for step in section["steps"]:
                    old_step_map[step] = current_index
                    current_index += 1

            # Create new statuses and notes, preserving existing ones where possible
            for section in sections:
                for step in section["steps"]:
                    if step in old_step_map:
                        old_idx = old_step_map[step]
                        new_statuses.append(old_statuses[old_idx])
                        new_notes.append(old_notes[old_idx])
                    else:
                        new_statuses.append("not_started")
                        new_notes.append("")

            plan["sections"] = sections
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        Output.print(
            type="updatePlan",
            text=f"Plan {plan_id} updated",
            data=plan,
        )

        return ToolResult(
            output=f"Plan updated successfully: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _list_plans(self) -> ToolResult:
        """List all available plans."""
        if not self.plans:
            return ToolResult(
                output="No plans available. Create a plan with the 'create' command."
            )

        output = "Available plans:\n"
        for plan_id, plan in self.plans.items():
            current_marker = " (active)" if plan_id == self._current_plan_id else ""
            completed = sum(
                1 for status in plan["step_statuses"] if status == "completed"
            )
            total = sum(len(section["steps"]) for section in plan["sections"])
            progress = f"{completed}/{total} steps completed"
            output += f"• {plan_id}{current_marker}: {plan['title']} - {progress}\n"

        Output.print(
            type="listPlans",
            text=f"{output}",
            data=self.plans,
        )

        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Get details of a specific plan."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]

        Output.print(
            type="getPlan",
            text=f"Plan {plan_id} details",
            data=plan,
        )

        return ToolResult(output=self._format_plan(plan))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Set a plan as the active plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: set_active")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        self._current_plan_id = plan_id

        Output.print(
            type="setActivePlan",
            text=f"Plan {plan_id} set as active",
            data=self.plans[plan_id],
        )

        return ToolResult(
            output=f"Plan '{plan_id}' is now the active plan.\n\n{self._format_plan(self.plans[plan_id])}"
        )

    def _mark_step(
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """Mark a step with a specific status and optional notes."""
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        if step_index is None:
            raise ToolError("Parameter `step_index` is required for command: mark_step")

        plan = self.plans[plan_id]
        total_steps = sum(len(section["steps"]) for section in plan["sections"])

        if step_index < 0 or step_index >= total_steps:
            raise ToolError(
                f"Invalid step_index: {step_index}. Valid indices range from 0 to {total_steps-1}."
            )

        if step_status and step_status not in [
            "not_started",
            "in_progress",
            "completed",
            "blocked",
        ]:
            raise ToolError(
                f"Invalid step_status: {step_status}. Valid statuses are: not_started, in_progress, completed, blocked"
            )

        if step_status:
            plan["step_statuses"][step_index] = step_status

        if step_notes:
            plan["step_notes"][step_index] = step_notes

        Output.print(
            type="markPlanStep",
            text=f"Step {step_index} updated in plan '{plan_id}'",
            data=plan,
        )

        return ToolResult(
            output=f"Step {step_index} updated in plan '{plan_id}'.\n\n{self._format_plan(plan)}"
        )

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Delete a plan."""
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: delete")

        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        del self.plans[plan_id]

        # If the deleted plan was the active plan, clear the active plan
        if self._current_plan_id == plan_id:
            self._current_plan_id = None

        Output.print(
            type="deletePlan",
            text=f"Plan '{plan_id}' has been deleted.",
            data=self.plans,
        )

        return ToolResult(output=f"Plan '{plan_id}' has been deleted.")

    def _format_plan(self, plan: Dict) -> str:
        """Format a plan for display."""
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"

        # Calculate progress statistics
        total_steps = sum(len(section["steps"]) for section in plan["sections"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(
            1 for status in plan["step_statuses"] if status == "in_progress"
        )
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        not_started = sum(
            1 for status in plan["step_statuses"] if status == "not_started"
        )

        output += f"Progress: {completed}/{total_steps} steps completed "
        if total_steps > 0:
            percentage = (completed / total_steps) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"

        output += f"Status: {completed} completed, {in_progress} in progress, {blocked} blocked, {not_started} not started\n\n"

        # Add each section with its steps
        current_step_index = 0
        for section in plan["sections"]:
            output += f"## {section['title']}\n"
            for step in section["steps"]:
                status = plan["step_statuses"][current_step_index]
                notes = plan["step_notes"][current_step_index]

                status_symbol = {
                    "not_started": "[ ]",
                    "in_progress": "[→]",
                    "completed": "[✓]",
                    "blocked": "[!]",
                }.get(status, "[ ]")

                output += f"  {status_symbol} {step}\n"
                if notes:
                    output += f"     Notes: {notes}\n"

                current_step_index += 1
            output += "\n"

        return output
