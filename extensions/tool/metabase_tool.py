from typing import Dict, List, Optional
from app.tool.base import BaseTool
from extensions.tool.metabase import metabase_api, execute_query, create_dashboard, create_question, add_question_to_dashboard, add_text_to_dashboard, get_table_info, create_datasource

class MetabaseTool(BaseTool):
    name: str = "metabase"
    description: str = """
Interact with Metabase to create and manage dashboards, questions, and data sources. Use this tool to create visualizations, execute queries, and manage Metabase resources.

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
            - Field names in SQL must be enclosed in double quotes ("). For example: SELECT "field1", "field2" FROM "table"
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

    Note:
        If display_type and visualization_settings are not provided, the system will
        automatically analyze the query result and determine the best visualization type.

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

5. execute_query
Execute SQL query and return the result data.
- Returns query results with data, columns, row count, and column count
- Handles errors gracefully with detailed error messages

6. get_table_info
Get table structure and sample data.
- Returns detailed column information including names, types, and max lengths
- Includes sample data (first 10 rows) for quick data preview

7. create_datasource
Create a new database connection in Metabase.
Args:
        name: Database name in Metabase
        engine: Database type ("mysql" or "postgres")
        host: Database host
        port: Database port
        dbname: Database name
        user: Database username
        password: Database password
        ssl: Whether to use SSL connection (default: False)
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "(required) The operation to perform on Metabase.",
                "enum": [
                    "create_dashboard",
                    "create_question",
                    "add_question_to_dashboard",
                    "add_text_to_dashboard",
                    "execute_query",
                    "get_table_info",
                    "create_datasource"
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
            "name": {
                "type": "string",
                "description": "(optional) Name for the data source.",
            },
            "engine": {
                "type": "string",
                "description": "(optional) Database type ('mysql' or 'postgres').",
                "enum": ["mysql", "postgres"],
            },
            "host": {
                "type": "string",
                "description": "(optional) Database host.",
            },
            "port": {
                "type": "integer",
                "description": "(optional) Database port.",
            },
            "dbname": {
                "type": "string",
                "description": "(optional) Database name.",
            },
            "user": {
                "type": "string",
                "description": "(optional) Database username.",
            },
            "password": {
                "type": "string",
                "description": "(optional) Database password.",
            },
            "ssl": {
                "type": "boolean",
                "description": "(optional) Whether to use SSL connection.",
            },
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
        name: Optional[str] = None,
        engine: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = False,
    ) -> str:
        """
        Execute Metabase operations.

        Args:
            operation (str): The operation to perform on Metabase.
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
            name (str, optional): Name for the data source.
            engine (str, optional): Database type ('mysql' or 'postgres').
            host (str, optional): Database host.
            port (int, optional): Database port.
            dbname (str, optional): Database name.
            user (str, optional): Database username.
            password (str, optional): Database password.
            ssl (bool, optional): Whether to use SSL connection.

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

            elif operation == "execute_query":
                if not sql_query:
                    return "SQL query is required for execute_query operation"
                return await execute_query(sql_query)

            elif operation == "get_table_info":
                if not table_name:
                    return "Table name is required for get_table_info operation"
                return await get_table_info(table_name)

            elif operation == "create_datasource":
                if not all([name, engine, host, port, dbname, user, password]):
                    return "All database connection details are required for create_datasource operation"
                return await create_datasource(
                    name=name,
                    engine=engine,
                    host=host,
                    port=port,
                    dbname=dbname,
                    user=user,
                    password=password,
                    ssl=ssl
                )

            else:
                return f"Unknown operation: {operation}"

        except Exception as e:
            return f"Error executing operation: {str(e)}" 