import asyncio
import os
import sys
from typing import Any, Dict, List
import json
import httpx
from mcp.server.fastmcp import FastMCP

from app.config import WORKSPACE_ROOT
from extensions.output import Output

# Initialize FastMCP server
mcp = FastMCP("metabase")

# Constants
METABASE_URL = "http://111.231.167.99:3000"
METABASE_USER = "silver.sun@encootech.com"
METABASE_PASSWORD = "y79S6djYpqUdCA"
METABASE_DATABASE_ID = 2
METABASE_PUBLIC_URL = "http://agent.bottime.com:8888/metabase"
OC_TOKEN = "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IjIzOEQ3RkNEMEJEMDczNDk5NjZDQ0E1NUQ4MkZCQkNGRERBRUE5QkIiLCJ0eXAiOiJKV1QifQ.eyJ1c2VyaWQiOiJiZDI0YmRlOS0zODAyLTRjNWYtYmU1Ni04ZWJiNTk2OTYzYWMiLCJkZWZhdWx0X3RpbWV6b25laWQiOiJDaGluYSBTdGFuZGFyZCBUaW1lIiwic3ViIjoiMjciLCJjbGllbnRfaWQiOiJ0cmlub19hYmNfZGV2IiwiY2xpZW50X25hbWUiOiJ0cmlub19hYmNfZGV2IiwicGhvbmVfbnVtYmVyIjoiMTczMjExMjkxNDEiLCJlbWFpbCI6IiIsInNjb3BlIjpbIm9mZmxpbmVfYWNjZXNzIiwib3BlbmlkIiwicHJvZmlsZSIsImFwaWdhdGV3YXkiLCJjb25zb2xlX2FkbWluIl0sIm5iZiI6MTc0NTk5MTIxNCwiZXhwIjoyMDYxNTQ3MjAwLCJpc3MiOiJodHRwczovL2FiY2F1dGgtZGV2LmJvdHRpbWUuY29tIiwiYXVkIjoiYXBpZ2F0ZXdheSJ9.Mt9n1UAU1wkEKo7RYFPBPQblg_c3TM8icE17IxWypf-Q3TUSKJza22YTDNKNTazipZJroVu2VrLLsbXfro059vQX_7YUeiMACVI8dVpA4EX3V6Il7oP3MaNNoJ0k0scrgQ3lbXX9Hr5ojPa5OddOY55mpS-3tzOpHmj5MgXmLU7knMj4kS1Iq9EfMXxsbZb9_AWL97oW_b8hAJNGI3RJjC9JJusIJO-RGrbaIJ6IlgJBWENDc9d3uKqb-bJapRt9RxtgnsK1VZOJi67FZH3oIjkOGSWhZUQFlc_H1DRUKSrynPZtzFRco6Ao8Dp9D0a3cL0-cNb2afNHFMquLpyTEQ"
OC_URL = "https://abcapi-dev.bottime.com"


def log_debug(message: str):
    """输出调试日志到stderr"""
    print(message, file=sys.stderr)


async def execute_query(sql_query: str) -> Dict[str, Any]:
    """
    Execute SQL query and return the result data

    Args:
        sql_query: SQL query to execute

    Returns:
        Dict containing query result data and metadata
    """
    try:
        if not await metabase_api.authenticate():
            return {
                "error": "Failed to connect to Metabase, please check authentication"
            }

        # Get database ID
        database_id = METABASE_DATABASE_ID

        # Execute query
        question_data = {
            "type": "native",
            "native": {"query": sql_query, "template-tags": {}},
            "database": database_id,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{METABASE_URL}/api/dataset",
                json=question_data,
                headers=metabase_api.headers,
            )
            response.raise_for_status()
            data = response.json()

            return {
                "data": data.get("data", {}).get("rows", []),
                "columns": data.get("data", {}).get("cols", []),
                "row_count": len(data.get("data", {}).get("rows", [])),
                "column_count": len(data.get("data", {}).get("cols", [])),
            }
    except Exception as e:
        return {"error": f"Failed to execute query: {str(e)}"}


async def get_table_structure(table_name: str):
    """通过Metabase API获取表结构和前10条数据"""
    try:
        log_debug(
            f"\n[get_table_structure] Starting to get table structure for: {table_name}"
        )

        # 认证
        if not hasattr(metabase_api, "session_token") or not metabase_api.session_token:
            await metabase_api.authenticate()

        # 获取列信息
        columns = []
        column_query = await convert_sql(f"show columns from {table_name}")
        result = await execute_query(column_query)
        for row in result["data"]:
            if len(row) >= 2:
                columns.append([row[0], row[1]])
            else:
                log_debug(f"Skipping invalid row with insufficient data: {row}")
        # 获取样例数据
        sample_query = await convert_sql(f"SELECT * FROM {table_name} LIMIT 10")
        sample_result = await execute_query(sample_query)
        sample_rows = sample_result["data"]

        return {"columns": columns, "sample_data": sample_rows}
    except Exception as e:
        log_debug(f"\n[get_table_structure] Failed to get table structure:")
        log_debug(f"- Error type: {type(e).__name__}")
        log_debug(f"- Error message: {str(e)}")
        import traceback

        log_debug(f"- Error stack: {traceback.format_exc()}")
        raise


async def get_oss_presigned_url(session_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        client.headers.update(
            {"Authorization": OC_TOKEN, "x-jwt-payload-sub": "27", "x-jwt-auth": "true"}
        )
        response = await client.get(f"{OC_URL}/trino/metabase/presignUrl/{session_id}")
        return response.json()

async def create_table(session_id: str, key: str, fileds: list[dict], table_name: str):
    async with httpx.AsyncClient(timeout=30) as client:
        client.headers.update(
            {
                "Authorization": OC_TOKEN,
                "x-jwt-payload-sub": "27",
                "x-jwt-auth": "true",
                "Content-Type": "application/json",
            }
        )
        response = await client.post(
            f"{OC_URL}/trino/metabase/table/{session_id}?fileKey={key}&tableName={table_name}", json=fileds
        )
        return response.json()

async def convert_sql(sql: str):
    async with httpx.AsyncClient(timeout=30) as client:
        client.headers.update(
            {
                "Authorization": OC_TOKEN,
                "x-jwt-payload-sub": "27",
                "x-jwt-auth": "true",
                "Content-Type": "text/plain",
            }
        )
        response = await client.post(
            f"{OC_URL}/trino/metabase/converterQuery", json=sql
        )
        sql_result = response.json()['sql']
        return sql_result.strip().lstrip('"').rstrip('"')

class MetabaseAPI:
    def __init__(self):
        self.session_token = None
        self.headers = {"Content-Type": "application/json"}

    async def authenticate(self) -> bool:
        """Authenticate with Metabase and get session token."""
        auth_url = f"{METABASE_URL}/api/session"
        auth_data = {"username": METABASE_USER, "password": METABASE_PASSWORD}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(auth_url, json=auth_data)
                response.raise_for_status()
                self.session_token = response.json()["id"]
                self.headers["X-Metabase-Session"] = self.session_token
                return True
            except Exception as e:
                Output.print(type="dash_maker",text=f"Authentication failed: {str(e)}")
                return False

    async def create_dashboard(self, name: str, description: str) -> Dict[str, Any]:
        """Create a new dashboard in Metabase."""
        if not self.session_token:
            await self.authenticate()

        dashboard_data = {"name": name, "description": description}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{METABASE_URL}/api/dashboard",
                json=dashboard_data,
                headers=self.headers,
            )
            return response.json()

    async def make_public(self, dashboard_id: int) -> Dict[str, Any]:
        """Make a dashboard public"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{METABASE_URL}/api/dashboard/{dashboard_id}/public_link",
                headers=self.headers,
            )
            return response.json()

    async def get_question_details(self, card_id: int) -> Dict[str, Any]:
        """Get question details"""
        try:
            if not self.session_token:
                await self.authenticate()

            log_debug(f"Getting details for question {card_id}...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/card/{card_id}", headers=self.headers
                )
                response.raise_for_status()
                details = response.json()
                log_debug(f"Successfully retrieved question {card_id} details")
                return details
        except Exception as e:
            log_debug(f"Failed to get question details: {str(e)}")
            return None

    async def check_dashboard_exists(self, dashboard_id: int) -> bool:
        """Check if dashboard exists"""
        try:
            if not self.session_token:
                await self.authenticate()

            log_debug(f"Checking if dashboard {dashboard_id} exists...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}", headers=self.headers
                )
                exists = response.status_code == 200
                log_debug(f"Dashboard {dashboard_id} exists: {exists}")
                return exists
        except Exception as e:
            log_debug(f"Failed to check dashboard existence: {str(e)}")
            return False

    async def check_question_exists(self, question_id: int) -> bool:
        """Check if question exists"""
        try:
            if not self.session_token:
                await self.authenticate()

            log_debug(f"Checking if question {question_id} exists...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/card/{question_id}", headers=self.headers
                )
                exists = response.status_code == 200
                log_debug(f"Question {question_id} exists: {exists}")
                return exists
        except Exception as e:
            log_debug(f"Failed to check question existence: {str(e)}")
            return False

    async def get_dashboard_cards(self, dashboard_id: int) -> List[Dict[str, Any]]:
        """Get all cards from a dashboard"""
        try:
            if not self.session_token:
                await self.authenticate()

            log_debug(f"\nGetting cards from dashboard {dashboard_id}...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}", headers=self.headers
                )
                response.raise_for_status()
                dashboard_data = response.json()
                cards = dashboard_data.get("dashcards", [])
                log_debug(f"Found {len(cards)} cards in dashboard {dashboard_id}")

                # Log details of each existing card
                for i, card in enumerate(cards):
                    log_debug(f"\nCard {i+1} details:")
                    log_debug(f"- ID: {card.get('id')}")
                    log_debug(f"- Card ID: {card.get('card_id')}")
                    log_debug(f"- Position: ({card.get('col')}, {card.get('row')})")
                    log_debug(f"- Size: {card.get('size_x')}x{card.get('size_y')}")

                return cards
        except Exception as e:
            log_debug(f"Failed to get dashboard cards: {str(e)}")
            return []

    async def add_card_to_dashboard(
        self,
        dashboard_id: int,
        card_id: int,
        size_x: int = None,
        size_y: int = None,
        col: int = None,
        row: int = None,
    ) -> Dict[str, Any]:
        """Add a card to a dashboard with optional position and size parameters.

        Args:
            dashboard_id: Dashboard ID
            card_id: Card/Question ID
            size_x: Optional width of the card (default: auto-calculated)
            size_y: Optional height of the card (default: auto-calculated)
            col: Optional column position (default: auto-calculated)
            row: Optional row position (default: auto-calculated)

        Note:
            Dashboard uses a 24-column grid layout. Default sizes and layout rules for different chart types:
            - Table: 8x8, can fit 3 horizontally
            - Bar/Line/Area charts: 12x12, can fit 2 horizontally
            - Pie chart: 8x8, can fit 3 horizontally
            - Scatter plot: 16x12, can fit only 1 horizontally
            When there is not enough space in the current row, the chart will automatically move to the next row.
        """
        try:
            log_debug(f"\nStarting to add card {card_id} to dashboard {dashboard_id}")

            if not self.session_token:
                log_debug("No session token, authenticating...")
                await self.authenticate()

            # Check if dashboard exists
            log_debug(f"Step 1: Verifying dashboard {dashboard_id} exists")
            if not await self.check_dashboard_exists(dashboard_id):
                raise ValueError(f"Dashboard ID {dashboard_id} does not exist")

            # Check if question exists
            log_debug(f"Step 2: Verifying question {card_id} exists")
            if not await self.check_question_exists(card_id):
                raise ValueError(f"Question ID {card_id} does not exist")

            # Get question details
            log_debug(f"Step 3: Getting question {card_id} details")
            question_details = await self.get_question_details(card_id)
            if not question_details:
                raise ValueError(f"Failed to get question details for ID {card_id}")

            # Determine card size based on question type if not provided
            log_debug("Step 4: Determining card size")
            display_type = question_details.get("display", "table")
            visualization_settings = question_details.get("visualization_settings", {})

            # Use provided size or calculate default
            final_size_x = size_x
            final_size_y = size_y

            if final_size_x is None or final_size_y is None:
                # Default size
                final_size_x = size_x or 8
                final_size_y = size_y or 8

                # Adjust size based on display type if not provided
                if display_type == "table":
                    row_count = visualization_settings.get("table.row_count", 10)
                    final_size_y = size_y or min(16, max(8, (row_count // 5) + 4))
                elif display_type in ["bar", "line", "area"]:
                    final_size_x = size_x or 12
                    final_size_y = size_y or 12
                elif display_type == "pie":
                    final_size_x = size_x or 8
                    final_size_y = size_y or 8
                elif display_type == "scatter":
                    final_size_x = size_x or 16
                    final_size_y = size_y or 12

            # Get existing cards and determine position if not provided
            log_debug("\nStep 5: Getting existing cards and determining position")
            existing_cards = await self.get_dashboard_cards(dashboard_id)

            # 初始化位置变量
            final_row = row
            final_col = col

            if (final_row is None or final_col is None) and existing_cards:
                log_debug(f"Found {len(existing_cards)} existing cards")
                # 打印所有现有卡片的信息
                for i, card in enumerate(existing_cards):
                    log_debug(
                        f"Card {i+1}: row={card.get('row', 0)}, col={card.get('col', 0)}, size_x={card.get('size_x', 0)}, size_y={card.get('size_y', 0)}"
                    )

                # 找到所有卡片的最大行数
                max_row = max(
                    card.get("row", 0) + card.get("size_y", 0)
                    for card in existing_cards
                )
                log_debug(f"Maximum row found: {max_row}")

                # 获取最后一行的所有卡片
                last_row_cards = [
                    card for card in existing_cards if card.get("row", 0) == max_row - 1
                ]
                log_debug(f"Found {len(last_row_cards)} cards in the last row")

                if last_row_cards:
                    # 计算最后一行的总宽度
                    last_row_width = sum(
                        card.get("size_x", 0) for card in last_row_cards
                    )
                    log_debug(f"Last row total width: {last_row_width}")

                    # 如果当前行有足够空间（24列）
                    if last_row_width + final_size_x <= 24:
                        # 找到最后一行的最右边位置
                        rightmost_col = max(
                            card.get("col", 0) + card.get("size_x", 0)
                            for card in last_row_cards
                        )
                        final_row = max_row - 1
                        final_col = rightmost_col
                        log_debug(
                            f"Adding card horizontally at column {final_col} in row {final_row}"
                        )
                    else:
                        # 当前行空间不足，换到下一行
                        final_row = max_row
                        final_col = 0
                        log_debug(f"Adding card on a new row {final_row}")
                else:
                    # 如果没有最后一行的卡片，检查当前行是否有空间
                    current_row_cards = [
                        card for card in existing_cards if card.get("row", 0) == 0
                    ]
                    if current_row_cards:
                        current_row_width = sum(
                            card.get("size_x", 0) for card in current_row_cards
                        )
                        if current_row_width + final_size_x <= 24:
                            # 在当前行添加
                            rightmost_col = max(
                                card.get("col", 0) + card.get("size_x", 0)
                                for card in current_row_cards
                            )
                            final_row = 0
                            final_col = rightmost_col
                            log_debug(
                                f"Adding card horizontally at column {final_col} in row {final_row}"
                            )
                        else:
                            # 换到下一行
                            final_row = max_row
                            final_col = 0
                            log_debug(f"Adding card on a new row {final_row}")
                    else:
                        # 如果当前行也没有卡片，从第一行开始
                        final_row = 0
                        final_col = 0
                        log_debug("Adding card at the beginning of the dashboard")
            else:
                # 如果仪表板是空的或提供了位置，使用提供的值或默认值
                final_row = row or 0
                final_col = col or 0
                log_debug(
                    f"Using provided or default position: row={final_row}, col={final_col}"
                )

            log_debug(f"\nFinal position and size for new card:")
            log_debug(f"- Row: {final_row}")
            log_debug(f"- Column: {final_col}")
            log_debug(f"- Size X: {final_size_x}")
            log_debug(f"- Size Y: {final_size_y}")

            # Prepare new card data
            new_card = {
                "id": -1,
                "card_id": card_id,
                "dashboard_id": dashboard_id,
                "parameter_mappings": [],
                "visualization_settings": visualization_settings,
                "col": final_col,
                "row": final_row,
                "size_x": final_size_x,
                "size_y": final_size_y,
                "series": [],
            }

            # Combine existing cards with new card
            all_cards = []

            # 处理现有卡片
            for card in existing_cards:
                # 只保留必要的字段
                existing_card = {
                    "id": card.get("id"),
                    "card_id": card.get("card_id"),
                    "dashboard_id": dashboard_id,
                    "parameter_mappings": card.get("parameter_mappings", []),
                    "visualization_settings": card.get("visualization_settings", {}),
                    "col": card.get("col", 0),
                    "row": card.get("row", 0),
                    "size_x": card.get("size_x", 0),
                    "size_y": card.get("size_y", 0),
                    "series": card.get("series", []),
                }
                all_cards.append(existing_card)

            # 添加新卡片
            all_cards.append(new_card)

            card_data = {"cards": all_cards}

            log_debug(f"\nStep 7: Sending request to add card to dashboard")
            log_debug(f"Total cards in request: {len(all_cards)}")
            log_debug(f"Request body: {card_data}")
            async with httpx.AsyncClient() as client:
                # First try to get the dashboard to verify access
                log_debug(f"Step 7.1: Verifying dashboard access")
                dashboard_response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}", headers=self.headers
                )
                if dashboard_response.status_code != 200:
                    raise ValueError(
                        f"Failed to access dashboard {dashboard_id}. Status code: {dashboard_response.status_code}"
                    )

                # Then try to add the card using PUT request
                log_debug(f"Step 7.2: Adding card to dashboard using PUT request")
                response = await client.put(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                    json=card_data,
                    headers=self.headers,
                )

                response.raise_for_status()
                result = response.json()
                log_debug(
                    f"\nSuccessfully added card {card_id} to dashboard {dashboard_id}"
                )
                log_debug(f"Response: {result}")
                return result
        except httpx.HTTPError as e:
            log_debug(f"HTTP error occurred: {str(e)}")
            if e.response is not None:
                log_debug(f"Response status code: {e.response.status_code}")
                log_debug(f"Response body: {e.response.text}")
                if e.response.status_code == 404:
                    raise ValueError(
                        f"Failed to add card. Please verify that:\n1. Dashboard ID {dashboard_id} exists\n2. Question ID {card_id} exists\n3. You have permission to access both the dashboard and question"
                    )
                elif e.response.status_code == 403:
                    raise ValueError("You don't have permission to perform this action")
                else:
                    raise ValueError(f"Failed to add card: {str(e)}")
            else:
                raise ValueError(f"Failed to add card: {str(e)}")
        except Exception as e:
            log_debug(f"Unexpected error occurred: {str(e)}")
            import traceback

            log_debug(f"Error stack: {traceback.format_exc()}")
            raise ValueError(f"Failed to add card: {str(e)}")

    async def add_text_card_to_dashboard(
        self,
        dashboard_id: int,
        text: str,
        text_type: str = "text",  # "text" or "heading"
        text_align: str = "left",  # "left", "center", "right"
        size_x: int = 24,
        size_y: int = 1,
        col: int = 0,
        row: int = 0,
    ) -> Dict[str, Any]:
        """Add a text or heading card to a dashboard.

        Args:
            dashboard_id: Dashboard ID
            text: Text content to display
            text_type: Type of text card ("text" or "heading")
            text_align: Text alignment ("left", "center", or "right")
            size_x: Width of the card (default: 24 for full width)
            size_y: Height of the card (default: 1)
            col: Column position (default: 0)
            row: Row position (default: 0)
        """
        try:
            if not self.session_token:
                await self.authenticate()

            # Check if dashboard exists
            if not await self.check_dashboard_exists(dashboard_id):
                raise ValueError(f"Dashboard ID {dashboard_id} does not exist")

            # Get existing cards
            existing_cards = await self.get_dashboard_cards(dashboard_id)

            # Prepare text card data
            text_card = {
                "id": -1,
                "card_id": None,
                "dashboard_id": dashboard_id,
                "parameter_mappings": [],
                "visualization_settings": {
                    "text": text,
                    "text.align_vertical": "middle",
                    "text.align_horizontal": text_align,
                    "dashcard.background": False,
                    "virtual_card": {"archived:": False, "display": "text"},
                },
                "col": col,
                "row": row,
                "size_x": size_x,
                "size_y": size_y,
                "series": [],
            }

            # Set text type specific settings
            if text_type == "heading":
                text_card["visualization_settings"]["virtual_card"].update(
                    {"display": "heading"}
                )

            # Combine existing cards with new card
            all_cards = []
            for card in existing_cards:
                existing_card = {
                    "id": card.get("id"),
                    "card_id": card.get("card_id"),
                    "dashboard_id": dashboard_id,
                    "parameter_mappings": card.get("parameter_mappings", []),
                    "visualization_settings": card.get("visualization_settings", {}),
                    "col": card.get("col", 0),
                    "row": card.get("row", 0),
                    "size_x": card.get("size_x", 0),
                    "size_y": card.get("size_y", 0),
                    "series": card.get("series", []),
                }
                all_cards.append(existing_card)

            all_cards.append(text_card)

            card_data = {"cards": all_cards}

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                    json=card_data,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log_debug(f"Failed to add text card to dashboard: {str(e)}")
            raise


metabase_api = MetabaseAPI()


@mcp.tool()
async def create_dashboard(dashboard_name: str, description: str) -> str:
    """
    Create a new dashboard

    Args:
        dashboard_name: Dashboard name
        description: Dashboard description
    """
    if not await metabase_api.authenticate():
        return "Failed to connect to Metabase, please check authentication"

    dashboard = await metabase_api.create_dashboard(dashboard_name, description)
    public_link_result = await metabase_api.make_public(dashboard["id"])
    uuid = public_link_result["uuid"]
    public_link = f"{METABASE_PUBLIC_URL}/public/dashboard/{uuid}"

    return f"Successfully created dashboard '{dashboard_name}', ID: {dashboard['id']}, view link: {public_link}"


@mcp.tool()
async def create_question(
    question_name: str,
    sql_query: str,
    display_type: str = None,
    visualization_settings: Dict[str, Any] = None,
) -> str:
    """
    Create a new question (query)

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
    """
    try:
        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        database_id = METABASE_DATABASE_ID
        if not isinstance(database_id, int):
            raise ValueError(
                f"数据库ID必须是整数，但得到的是 {type(database_id)}: {database_id}"
            )
        
        question_sql = await convert_sql(sql_query)
        if display_type and visualization_settings:
            question_data = {
                "name": question_name,
                "dataset_query": {
                    "type": "native",
                    "native": {"query": question_sql, "template-tags": {}},
                    "database": database_id,
                },
                "display": display_type,
                "visualization_settings": visualization_settings,
            }
        else:
            log_debug(f"visualization_settings and display_type is required")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{METABASE_URL}/api/card",
                json=question_data,
                headers=metabase_api.headers,
            )
            response.raise_for_status()
            result = response.json()

            if not isinstance(result, dict):
                raise ValueError(f"API返回的数据格式错误: {result}")

            return (
                f"Successfully created question '{question_name}', ID: {result['id']}"
            )
    except httpx.HTTPError as e:
        log_debug(f"HTTP错误: {str(e)}")
        if hasattr(e, "response") and e.response is not None:
            log_debug(f"响应内容: {e.response.text}")
        raise
    except Exception as e:
        log_debug(f"创建问题失败: {str(e)}")
        raise


@mcp.tool()
async def add_question_to_dashboard(
    dashboard_id: int,
    question_id: int,
    size_x: int = None,
    size_y: int = None,
    col: int = None,
    row: int = None,
) -> str:
    """
    Add a question to dashboard

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
    """
    try:
        log_debug(
            f"\nStarting to add question {question_id} to dashboard {dashboard_id}"
        )

        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        # Verify dashboard exists
        log_debug(f"Step 1: Verifying dashboard {dashboard_id} exists")
        if not await metabase_api.check_dashboard_exists(dashboard_id):
            return f"Dashboard ID {dashboard_id} does not exist"

        # Verify question exists
        log_debug(f"Step 2: Verifying question {question_id} exists")
        if not await metabase_api.check_question_exists(question_id):
            return f"Question ID {question_id} does not exist"

        log_debug(f"Step 3: Adding question to dashboard")
        result = await metabase_api.add_card_to_dashboard(
            dashboard_id, question_id, size_x=size_x, size_y=size_y, col=col, row=row
        )
        return f"Successfully added question to dashboard, ID: {dashboard_id}"
    except ValueError as e:
        log_debug(f"Value error occurred: {str(e)}")
        return str(e)
    except Exception as e:
        log_debug(f"Unexpected error occurred: {str(e)}")
        import traceback

        log_debug(f"Error stack: {traceback.format_exc()}")
        return f"Failed to add question to dashboard: {str(e)}"


@mcp.tool()
async def get_table_info(table_name: str) -> str:
    """
    Get table structure and sample data

    Args:
        table_name: Table name
    """
    try:
        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        table_info = await get_table_structure(table_name)
        # Format output
        result = f"Table '{table_name}' structure:\n\n"
        result += "Columns:\n"
        for col in table_info["columns"]:
            result += f"- {col[0]}: {col[1]}"
            if col[2]:
                result += f" (max length: {col[2]})"
            result += "\n"

        result += "\nSample data (first 10 rows):\n"
        for row in table_info["sample_data"]:
            result += f"{row}\n"

        return result
    except Exception as e:
        import traceback

        return f"Failed to get table info: {str(e)}"


@mcp.tool()
async def add_text_to_dashboard(
    dashboard_id: int,
    text: str,
    text_type: str = "text",
    text_align: str = "left",  # "left", "center", "right"
    size_x: int = 24,
    size_y: int = 1,
    col: int = 0,
    row: int = 0,
) -> str:
    """
    Add a text or heading card to a dashboard

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
        - Text cards can be positioned anywhere in the grid
    """
    try:
        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        if not await metabase_api.check_dashboard_exists(dashboard_id):
            return f"Dashboard ID {dashboard_id} does not exist"

        result = await metabase_api.add_text_card_to_dashboard(
            dashboard_id, text, text_type, text_align, size_x, size_y, col, row
        )
        return f"Successfully added {text_type} to dashboard, ID: {dashboard_id}"
    except Exception as e:
        return f"Failed to add text to dashboard: {str(e)}"


@mcp.tool()
async def create_dash_table(
    table_name: str, file_name: str, table_structure: str
) -> str:
    """
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
    session_id = Output._current_session_id
    presign_url_data = await get_oss_presigned_url(session_id)
    key = presign_url_data["data"]["key"]
    url = presign_url_data["data"]["url"]
    file_path = os.path.join(WORKSPACE_ROOT + "/", file_name)
    with httpx.Client(timeout=30) as client:
        with open(file_path, "rb") as f:
            response = client.put(url, data=f.read())
            Output.print(
                type="dash_maker",text=f"File {file_name} uploaded to OSS successfully: {response.status_code}"
            )
    table_columns = json.loads(table_structure)
    json_result = await create_table(session_id, key, table_columns, table_name)

    if json_result and 'data' in json_result:
        result_data = json_result['data']
        if 'table_name' in result_data and result_data['table_name']:
            table_result = result_data['table_name']

    result = f"Successfully created table '{table_result}' "
    # Format output
    if table_result != table_name:
        result = f"Duplicated table '{table_name}', new table name is '{table_result}'. Please use the new table '{table_result}' for next steps"

    return result


if __name__ == "__main__":
    try:
        log_debug("Starting MCP server...")
        mcp.run(transport="stdio")
    except Exception as e2:
        log_debug(f"All transport methods failed: {str(e2)}")
