from typing import Dict, List, Optional
from app.tool.base import BaseTool
from extensions.tool.dash_maker import create_dashboard, create_question, add_question_to_dashboard, add_text_to_dashboard, get_table_info,create_dash_table
from extensions.tool.datatable_client.trino_client import TrinoDataTableClient

class DashmakerTool(BaseTool):
    name: str = "dashmaker"
    description: str = """
Create and manage dashboards, questions, and data sources. Use this tool to create visualizations, execute queries, and manage dashboard resources.

<guidelines>
- make sure you know the table schema before writing queries
</guidelines>

Available operations:

1. create_dashboard
Create a new dashboard with specified name and description.

2. create_question
Args:
        question_name: Question name
        sql_query: SQL query
            - Field names in SQL must be enclosed in double quotes ("). For example: SELECT "field1", "field2" FROM table
            - Only use SQL syntax and functions supported by Trino (Presto). Do NOT use MySQL-specific or PostgreSQL-specific functions.
        display_type: display type for the visualization
            - table: Table view
            - line: Line chart
            - bar: Bar chart
            - area: Area chart
            - pie: Pie chart
            - scatter: Scatter plot
        visualization_settings: settings for the visualization
            - For table: {"table.row_count": 10}
            - For line/bar/area: {"graph.dimensions": ["column1"], "graph.metrics": ["column2"]}
            - For pie: {"pie.dimension": "column1", "pie.metric": "column2"}
            - For scatter: {"scatter.dimension": "column1", "scatter.metric": "column2"}

3. add_question_to_dashboard
Add a question to a dashboard with optional positioning and sizing.
Args:
        dashboard_id: Dashboard ID
        question_id: Question ID
        size_x: Optional width of the card (default: auto-calculated)
        size_y: Optional height of the card (default: auto-calculated)
        col: Optional column position, starting from 0 (default: auto-calculated)
        row: Optional row position, starting from 0 (default: auto-calculated)

    Note:
        Dashboard uses a 24-column grid layout (0-23). Default sizes and layout rules for different chart types:
        - Table: 8x8, can fit 3 horizontally
        - Bar/Line/Area charts: 12x12, can fit 2 horizontally
        - Pie chart: 8x8, can fit 3 horizontally
        - Scatter plot: 16x12, can fit only 1 horizontally
        When there is not enough space in the current row, the chart will automatically move to the next row.
        Both column and row positions are zero-based indices.

4. add_text_to_dashboard
Add a text or heading card to a dashboard with optional formatting and positioning.
Args:
        dashboard_id: Dashboard ID
        text: Text content to display
        text_type: Type of text card ("text" or "heading")
        text_align: Text alignment ("left", "center", or "right")
        size_x: Width of the card (default: 24 for full width)
        size_y: Height of the card (default: 1)
        col: Column position (default: 0)
        row: Row position (default: 0)

    Note:
        - Dashboard uses a 24-column grid layout
        - For headings, it's recommended to use full width (size_x=24)

5. list_tables
Get a list of all available tables.
Returns:
    list: A list of all tables.

6. get_table_info
Get table structure and sample data.
- Returns detailed column information including names, types, and max lengths
- Includes sample data (first 10 rows) for quick data preview

7. create_dash_table
Import CSV data into database and create a new table

This function takes a CSV file and table structure definition, and creates a new table in database. 
The imported data will be used for data visualization and analysis in dashboards.
Return the name of the created table, which can be used in dashboard creation and query operations to visualize the imported data

Args:
    table_name: Import table name
    file_name: Local file name
    table_structure: JSON string, sample: [{"displayName": "company","displayType": "TEXT"},{"displayName": "address","displayType": "TEXT"}]
        displayName: Column name in the table
        displayType supports the following types:
        - TEXT: Text data type
        - REAL: Floating-point number type
        - INTEGER: Integer number type
        - DATETIME: Date and time type
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "(required) The operation to perform on Dashmaker.",
                "enum": [
                    "create_dashboard",
                    "create_question",
                    "add_question_to_dashboard",
                    "add_text_to_dashboard",
                    "list_table",
                    "get_table_info",
                    "create_dash_table",
                ],
            },
            "dashboard_name": {
                "type": "string",
                "description": "(optional) Name of the dashboard to create.",
            },
            "description": {
                "type": "string",
                "description": "(optional) Description for the dashboard or question.",
            },
            "question_name": {
                "type": "string",
                "description": "(optional) Name of the question to create.",
            },
            "sql_query": {
                "type": "string",
                "description": "(optional) SQL query to execute or use in question creation.",
            },
            "display_type": {
                "type": "string",
                "description": "(optional) Display type for the visualization (table, line, bar, area, pie, scatter).",
                "enum": ["table", "line", "bar", "area", "pie", "scatter"],
            },
            "visualization_settings": {
                "type": "object",
                "description": "(optional) Settings for the visualization based on display type.",
            },
            "dashboard_id": {
                "type": "integer",
                "description": "(optional) ID of the dashboard to add questions or text to.",
            },
            "question_id": {
                "type": "integer",
                "description": "(optional) ID of the question to add to dashboard.",
            },
            "table_name": {
                "type": "string",
                "description": "(optional) Name of the table to get information about.",
            },
            "text": {
                "type": "string",
                "description": "(optional) Text content to add to dashboard.",
            },
            "text_type": {
                "type": "string",
                "description": "(optional) Type of text card ('text' or 'heading').",
                "enum": ["text", "heading"],
            },
            "text_align": {
                "type": "string",
                "description": "(optional) Text alignment for text cards.",
                "enum": ["left", "center", "right"],
            },
            "size_x": {
                "type": "integer",
                "description": "(optional) Width of the card in dashboard grid.",
            },
            "size_y": {
                "type": "integer",
                "description": "(optional) Height of the card in dashboard grid.",
            },
            "col": {
                "type": "integer",
                "description": "(optional) Column position in dashboard grid.",
            },
            "row": {
                "type": "integer",
                "description": "(optional) Row position in dashboard grid.",
            },
            "file_name":{
                "type": "string",
                "description": "(optional) Local file name.",
            },
            "table_structure":{
                "type": "string",
                "description": "(optional) Table structure.",
            }
        },
        "required": ["operation"],
    }

    async def execute(
        self,
        operation: str,
        dashboard_name: Optional[str] = None,
        description: Optional[str] = None,
        question_name: Optional[str] = None,
        sql_query: Optional[str] = None,
        display_type: Optional[str] = None,
        visualization_settings: Optional[dict] = None,
        dashboard_id: Optional[int] = None,
        question_id: Optional[int] = None,
        table_name: Optional[str] = None,
        text: Optional[str] = None,
        text_type: Optional[str] = "text",
        text_align: Optional[str] = "left",
        size_x: Optional[int] = None,
        size_y: Optional[int] = None,
        col: Optional[int] = None,
        row: Optional[int] = None,
        file_name: Optional[str] = None,
        table_structure: Optional[str] = None,
    ) -> str:
        """
        Execute Dashmaker operations.

        Args:
            operation (str): The operation to perform on Dashmaker.
            dashboard_name (str, optional): Name of the dashboard to create.
            description (str, optional): Description for the dashboard or question.
            question_name (str, optional): Name of the question to create.
            sql_query (str, optional): SQL query to execute or use in question creation.
            display_type (str, optional): Display type for the visualization (table, line, bar, area, pie, scatter).
            visualization_settings (dict, optional): Settings for the visualization based on display type.
            dashboard_id (int, optional): ID of the dashboard to add questions or text to.
            question_id (int, optional): ID of the question to add to dashboard.
            table_name (str, optional): Name of the table to get information about.
            text (str, optional): Text content to add to dashboard.
            text_type (str, optional): Type of text card ('text' or 'heading').
            text_align (str, optional): Text alignment for text cards.
            size_x (int, optional): Width of the card in dashboard grid.
            size_y (int, optional): Height of the card in dashboard grid.
            col (int, optional): Column position in dashboard grid.
            row (int, optional): Row position in dashboard grid.
            file_name (str, optional): Local file name.
            table_structure (str, optional): Table structure.

        Returns:
            str: Result of the operation.
        """
        try:
            if operation == "create_dashboard":
                if not dashboard_name:
                    return "Dashboard name is required for create_dashboard operation"
                return await create_dashboard(dashboard_name, description or "")

            elif operation == "create_question":
                if not question_name or not sql_query:
                    return "Question name and SQL query are required for create_question operation"
                if not display_type or not visualization_settings:
                    return "Display Type and visualization Settings are required for create_question operation"
                return await create_question(question_name, sql_query, display_type, visualization_settings)

            elif operation == "add_question_to_dashboard":
                if not dashboard_id or not question_id:
                    return "Dashboard ID and question ID are required for add_question_to_dashboard operation"
                return await add_question_to_dashboard(
                    dashboard_id,
                    question_id,
                    size_x=size_x,
                    size_y=size_y,
                    col=col,
                    row=row
                )

            elif operation == "add_text_to_dashboard":
                if not dashboard_id or not text:
                    return "Dashboard ID and text are required for add_text_to_dashboard operation"
                return await add_text_to_dashboard(
                    dashboard_id,
                    text,
                    text_type=text_type,
                    text_align=text_align,
                    size_x=size_x,
                    size_y=size_y,
                    col=col,
                    row=row
                )

            elif operation == "list_tables":
                return TrinoDataTableClient().list_tables()

            elif operation == "get_table_info":
                if not table_name:
                    return "Table name is required for get_table_info operation"
                return await get_table_info(table_name)

            elif operation == "create_dash_table":
                if not table_name:
                    return "Table name is required for create_dash_table operation"
                if not file_name:
                    return "File name is required for create_dash_table operation"
                if not table_structure:
                    return "Table structure is required for create_dash_table operation"
                return await create_dash_table(table_name, file_name, table_structure)
            else:
                return f"Unknown operation: {operation}"

        except Exception as e:
            return f"Error executing operation: {str(e)}" 