# Add project root to path to import trinoDatatableServiceApi
import os
import sys
import csv
import json
import time
from typing import Dict, List, Optional
from app.tool.base import BaseTool
from extensions.tool.datatable_client.trino_client import TrinoDataTableClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../workspace")))


class DataSource(BaseTool):
    name: str = "datasource"
    description: str = """
Interact with external datasources only. All managed external datasources are repesented here as a table. Use this tool to list all tables, retrieve schemas and query tables using SQL. 
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "(required) The operation to perform on the data source.",
                "enum": [
                    "list_tables",
                    "get_table_by_id",
                    "get_table_by_name",
                    "get_table_schema",
                    "query_data",
                ],
            },
            "table_id": {
                "type": "string",
                "description": "(optional) The ID of the table to operate on.",
            },
            "table_name": {
                "type": "string",
                "description": "(optional) The name of the table to operate on or create.",
            },
            "sql_query": {
                "type": "string",
                "description": "(optional) SQL query to execute on the data source.",
            },
            "fields": {
                "type": "array",
                "description": "(optional) Array of field definitions for creating or recreating a table.",
                "items": {
                    "type": "object",
                    "properties": {
                        "DisplayName": {"type": "string"},
                        "FieldType": {
                            "type": "string",
                            "enum": ["TEXT", "NUMBER", "REAL", "DATE"],
                        },
                    },
                },
            },
            "data": {
                "type": "string",
                "description": "(optional) JSON string containing data to upload to a table.",
            },
        },
        "required": ["operation"],
    }

    def __init__(self):
        super().__init__()
        self._api = TrinoDataTableClient()

    async def execute(
        self,
        operation: str,
        table_id: Optional[str] = None,
        table_name: Optional[str] = None,
        sql_query: Optional[str] = None,
        fields: Optional[List[Dict[str, str]]] = None,
        data: Optional[str] = None,
    ) -> str:
        """
        Execute data source operations.

        Args:
            operation (str): The operation to perform on the data source.
            table_id (str, optional): The ID of the table to operate on.
            table_name (str, optional): The name of the table to operate on or create.
            sql_query (str, optional): SQL query to execute on the data source.
            fields (List[Dict[str, str]], optional): Array of field definitions for creating or recreating a table.
            data (str, optional): Data string to upload to a table.

        Returns:
            str: A JSON string containing the result of the operation.
        """
        try:
            result = None

            if operation == "list_tables":
                # Call the API method to list all tables
                result = self._api.list_tables()

            elif operation == "get_table_by_id":
                if not table_id:
                    return json.dumps(
                        {"error": "Table ID is required for get_table_by_id operation"}
                    )
                result = self._api.get_table_by_id(table_id)

            elif operation == "get_table_by_name":
                if not table_name:
                    return json.dumps(
                        {
                            "error": "Table name is required for get_table_by_name operation"
                        }
                    )
                result = self._api.get_table_by_name(table_name)

            elif operation == "get_table_schema":
                if not table_id:
                    if table_name:
                        # handle common LLM error
                        _, result = self._api.get_table_by_name(table_name)
                    else:
                        return json.dumps(
                        {"error": "Table ID is required for get_table_schema operation"}
                        )
                else:
                    result = self._api.get_table_schema(table_id)

            elif operation == "query_data":
                if not sql_query:
                    return json.dumps(
                        {"error": "SQL query is required for query_data operation"}
                    )
                result = self._api.query_data(sql_query)

                # Generate unique filename with timestamp
                timestamp = int(time.time())
                csv_filename = f"query_result_{timestamp}.csv"

                # Write results to CSV file
                with open(csv_filename, "w", newline="") as f:
                    if result and len(result) > 0:
                        writer = csv.DictWriter(f, fieldnames=result[0].keys())
                        writer.writeheader()
                        writer.writerows(result)

                # Get preview of first 5 rows
                preview = result[:5] if result else []

                result = {
                    "csv_filename": csv_filename,
                    "preview": preview,
                    "total_rows": len(result) if result else 0,
                }

            else:
                return json.dumps({"error": f"Unknown operation: {operation}"})

            return json.dumps(
                {"data": result},
                default=lambda o: (
                    str(o)
                    if not isinstance(
                        o, (dict, list, str, int, float, bool, type(None))
                    )
                    else o
                ),
            )

        except Exception as e:
            return json.dumps({"error": str(e)})
