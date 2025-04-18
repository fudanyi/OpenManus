import sys
from typing import Any, Dict, List
from app.tool.base import BaseTool, ToolResult
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx  # 添加 httpx 库的导入
import json

# Metabase 配置
METABASE_URL = "http://10.10.10.138:3000"  # 替换为你的 Metabase 地址
METABASE_USERNAME = "guomingyang@encootech.com"  # 替换为你的 Metabase 用户名
METABASE_PASSWORD = "Encootech123"  # 替换为你的 Metabase 密码

# Database configuration
DB_CONFIG = {
    "host": "10.10.10.90",
    "port": 5432,
    "database": "amazon",
    "user": "sync",
    "password": "encoo123",
    "table": "amazon_sales_data",
    "metabase_database_name": "Amazon Sales",  # 添加Metabase中的数据库名称
}

class Metabase(BaseTool):
    name: str = "metabase"
    description: str = """
    Use Metabase to complete tasks related to database queries, dashboard creation, question management, and table structure retrieval.
    This tool can:
    - Retrieve the structure of a database table.
    - Create a question based on a SQL query and automatically determine the appropriate visualization type.
    - Create a dashboard to organize and display questions.
    - Add questions to a dashboard with specified positioning and size.
    - Retrieve the ID of a database by its name."""
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_table_structure", "create_question", "create_dashboard", "add_question_to_dashboard", "get_database_id"],
            },
            "arguments": {
                "type": "object",
                "oneOf": [
                    {
                        "description": "Parameters for retrieving table structure",
                        "properties": {
                            "table_name": {"type": "string"},
                        },
                        "required": ["table_name"],
                    },
                    {
                        "description": "Parameters for creating a question",
                        "properties": {
                            "question_name": {"type": "string"},
                            "query": {"type": "string"},
                        },
                        "required": ["question_name", "query"],
                    },
                    {
                        "description": "Parameters for creating a dashboard",
                        "properties": {
                            "dashboard_name": {"type": "string"},
                            "description": {"type": "string", "default": ""},
                        },
                        "required": ["dashboard_name"],
                    },
                    {
                        "description": "Parameters for adding a question to a dashboard",
                        "properties": {
                            "dashboard_id": {"type": "integer"},
                            "question_id": {"type": "integer"},
                        },
                        "required": ["dashboard_id", "question_id"],
                    },
                    {
                        "description": "Parameters for getting a database ID",
                        "properties": {
                            "db_name": {"type": "string"},
                        },
                        "required": ["db_name"],
                    },
                ],
            },
        },
        "required": ["action", "arguments"],
    }
    session_token: str = None
    headers: dict = {
        "Content-Type": "application/json"
    }
    async def execute(self, action: str, arguments: dict) -> ToolResult:
        if action == "get_table_structure":
            return ToolResult(output=json.dumps(self.get_table_structure(arguments["table_name"])))
        elif action == "create_question":
            return ToolResult(output=json.dumps(await self.create_question(arguments["question_name"], arguments["query"])))
        elif action == "create_dashboard":
            return ToolResult(output=json.dumps(await self.create_dashboard(arguments["dashboard_name"], arguments.get("description", ""))))
        elif action == "add_question_to_dashboard":
            return ToolResult(output=json.dumps(await self.add_question_to_dashboard(arguments["dashboard_id"], arguments["question_id"])))
        elif action == "get_database_id":
            return ToolResult(output=json.dumps(await self.get_database_id()))
        else:
            raise ToolResult(error=f"Unknown action: {action}")

    def get_db_connection(self):
        """获取数据库连接"""
        return psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )

    def get_table_structure(self, table_name: str):
        """获取表结构信息"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 获取表结构
                cur.execute(
                    f"""
                    SELECT column_name, data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position;
                """
                )
                columns = cur.fetchall()

                # 获取表前10条数据
                cur.execute(f"SELECT * FROM {table_name} LIMIT 10;")
                sample_data = cur.fetchall()

                return {"columns": columns, "sample_data": sample_data}
        finally:
            conn.close()

    async def authenticate(self) -> bool:
        """Authenticate with Metabase and get session token."""
        auth_url = f"{METABASE_URL}/api/session"
        auth_data = {
            "username": METABASE_USERNAME,
            "password": METABASE_PASSWORD
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(auth_url, json=auth_data)
                response.raise_for_status()
                self.session_token = response.json()["id"]
                self.headers["X-Metabase-Session"] = self.session_token
                return True
            except Exception as e:
                print(f"Authentication failed: {str(e)}", file=sys.stderr)
                return False

    async def get_database_id(self) -> dict:
        """获取数据库ID"""
        try:
            if not self.session_token:
                await self.authenticate()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/database",
                    headers=self.headers
                )
                response.raise_for_status()
                response_data = response.json()

                if not isinstance(response_data, dict) or 'data' not in response_data:
                    raise ValueError(f"API返回的数据格式错误: {response_data}")

                databases = response_data['data']
                if not isinstance(databases, list):
                    raise ValueError(f"API返回的数据库列表格式错误: {databases}")

                for db in databases:
                    if db["name"] == DB_CONFIG["metabase_database_name"]:
                        db_id = db.get("id")
                        if not isinstance(db_id, int):
                            raise ValueError(f"数据库ID必须是整数，但得到的是 {type(db_id)}: {db_id}")
                        return db

                raise Exception(f"未找到数据库: {DB_CONFIG['metabase_database_name']}")
        except httpx.HTTPError as e:
            print(f"HTTP错误: {str(e)}", file=sys.stderr)
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应内容: {e.response.text}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"获取数据库ID失败: {str(e)}", file=sys.stderr)
            raise

    async def analyze_query_data(self, query: str) -> Dict[str, Any]:
        """Analyze query data to determine the best visualization type"""
        try:
            print(f"\nStarting data analysis...", file=sys.stderr)
            print(f"Query: {query}", file=sys.stderr)

            if not self.session_token:
                await self.authenticate()

            # Get database ID
            database_id = (await self.get_database_id())['id']
            print(f"Database ID: {database_id}", file=sys.stderr)

            # Execute sample query
            sample_query = f"WITH sample AS ({query}) SELECT * FROM sample LIMIT 1000"
            print(f"Sample query: {sample_query}", file=sys.stderr)

            question_data = {
                "type": "native",
                "native": {
                    "query": sample_query,
                    "template-tags": {}
                },
                "database": database_id
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{METABASE_URL}/api/dataset",
                    json=question_data,
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("data", {}).get("rows"):
                    print("Warning: Query returned empty result", file=sys.stderr)
                    return {"display": "table", "visualization_settings": {}}

                rows = data["data"]["rows"]
                columns = data["data"]["cols"]
                print(f"\nData characteristics:", file=sys.stderr)
                print(f"- Total rows: {len(rows)}", file=sys.stderr)
                print(f"- Total columns: {len(columns)}", file=sys.stderr)

                # Create column name to index mapping
                col_name_to_idx = {col["name"]: idx for idx, col in enumerate(columns)}

                # Analyze data characteristics
                numeric_columns = []
                date_columns = []
                categorical_columns = []

                print("\nColumn type analysis:", file=sys.stderr)
                for col in columns:
                    print(f"- Column: {col['name']}, Type: {col['base_type']}", file=sys.stderr)
                    if col["base_type"] in ["type/Integer", "type/Float", "type/Decimal"]:
                        numeric_columns.append(col["name"])
                    elif col["base_type"] == "type/DateTime":
                        date_columns.append(col["name"])
                    else:
                        categorical_columns.append(col["name"])

                print(f"\nNumeric columns: {numeric_columns}", file=sys.stderr)
                print(f"Date columns: {date_columns}", file=sys.stderr)
                print(f"Categorical columns: {categorical_columns}", file=sys.stderr)

                # Analyze numeric column distributions
                numeric_distributions = {}
                for col in numeric_columns:
                    col_idx = col_name_to_idx[col]
                    values = [row[col_idx] for row in rows if row[col_idx] is not None]
                    if values:
                        min_val = min(values)
                        max_val = max(values)
                        avg_val = sum(values) / len(values)
                        std_dev = (sum((x - avg_val) ** 2 for x in values) / len(values)) ** 0.5
                        numeric_distributions[col] = {
                            "min": min_val,
                            "max": max_val,
                            "avg": avg_val,
                            "std_dev": std_dev,
                            "range": max_val - min_val
                        }
                        print(f"\n{col} statistics:", file=sys.stderr)
                        print(f"- Min: {min_val}", file=sys.stderr)
                        print(f"- Max: {max_val}", file=sys.stderr)
                        print(f"- Avg: {avg_val}", file=sys.stderr)
                        print(f"- Std Dev: {std_dev}", file=sys.stderr)
                        print(f"- Range: {max_val - min_val}", file=sys.stderr)

                # Analyze categorical column cardinalities
                categorical_cardinalities = {}
                for col in categorical_columns:
                    col_idx = col_name_to_idx[col]
                    values = [row[col_idx] for row in rows if row[col_idx] is not None]
                    unique_values = len(set(values))
                    categorical_cardinalities[col] = unique_values
                    print(f"\n{col} unique values count: {unique_values}", file=sys.stderr)

                # Determine visualization type
                print("\nSelecting visualization type:", file=sys.stderr)
                if len(date_columns) == 1 and len(numeric_columns) >= 1:
                    if len(numeric_columns) == 1:
                        print("Selected: Line chart - Single metric over time", file=sys.stderr)
                        return {
                            "display": "line",
                            "visualization_settings": {
                                "graph.dimensions": date_columns,
                                "graph.metrics": numeric_columns[:1]
                            }
                        }
                    else:
                        print("Selected: Area chart - Multiple metrics over time", file=sys.stderr)
                        return {
                            "display": "area",
                            "visualization_settings": {
                                "graph.dimensions": date_columns,
                                "graph.metrics": numeric_columns[:3]
                            }
                        }
                elif len(categorical_columns) >= 1 and len(numeric_columns) >= 1:
                    if len(numeric_columns) == 1:
                        if categorical_cardinalities.get(categorical_columns[0], 0) <= 10:
                            print("Selected: Pie chart - Small number of categories", file=sys.stderr)
                            return {
                                "display": "pie",
                                "visualization_settings": {
                                    "pie.dimension": categorical_columns[0],
                                    "pie.metric": numeric_columns[0]
                                }
                            }
                        else:
                            print("Selected: Bar chart - Large number of categories", file=sys.stderr)
                            return {
                                "display": "bar",
                                "visualization_settings": {
                                    "graph.dimensions": categorical_columns[:1],
                                    "graph.metrics": numeric_columns[:1]
                                }
                            }
                    else:
                        print("Selected: Stacked bar chart - Multiple metrics by category", file=sys.stderr)
                        return {
                            "display": "bar",
                            "visualization_settings": {
                                "graph.dimensions": categorical_columns[:1],
                                "graph.metrics": numeric_columns[:3],
                                "stackable.stack_type": "stacked"
                            }
                        }
                elif len(numeric_columns) == 2:
                    col1, col2 = numeric_columns
                    col1_idx = col_name_to_idx[col1]
                    col2_idx = col_name_to_idx[col2]
                    dist1 = numeric_distributions[col1]
                    dist2 = numeric_distributions[col2]

                    values1 = [row[col1_idx] for row in rows if row[col1_idx] is not None and row[col2_idx] is not None]
                    values2 = [row[col2_idx] for row in rows if row[col1_idx] is not None and row[col2_idx] is not None]

                    if len(values1) > 1:
                        mean1 = sum(values1) / len(values1)
                        mean2 = sum(values2) / len(values2)
                        covariance = sum((x - mean1) * (y - mean2) for x, y in zip(values1, values2)) / len(values1)
                        correlation = covariance / (dist1["std_dev"] * dist2["std_dev"])
                        print(f"\n{col1} and {col2} correlation: {correlation}", file=sys.stderr)

                        if abs(correlation) > 0.5:
                            print("Selected: Scatter plot - Strong correlation", file=sys.stderr)
                            return {
                                "display": "scatter",
                                "visualization_settings": {
                                    "scatter.dimension": col1,
                                    "scatter.metric": col2,
                                    "scatter.show_trendline": True
                                }
                            }

                print("Selected: Table - Default visualization", file=sys.stderr)
                return {
                    "display": "table",
                    "visualization_settings": {
                        "table.pivot": False,
                        "table.cell_column": None
                    }
                }

        except Exception as e:
            print(f"\nData analysis failed: {str(e)}", file=sys.stderr)
            import traceback
            print(f"Error stack: {traceback.format_exc()}", file=sys.stderr)
            return {"display": "table", "visualization_settings": {}}

    async def create_question(self, name: str, query: str) -> Dict[str, Any]:
        """Create a new question (query) in Metabase."""
        try:
            if not self.session_token:
                await self.authenticate()

            # 获取数据库ID
            database_id = (await self.get_database_id())['id']
            if not isinstance(database_id, int):
                raise ValueError(f"数据库ID必须是整数，但得到的是 {type(database_id)}: {database_id}")

            # 分析数据以确定最佳展示方式
            display_settings = await self.analyze_query_data(query)

            question_data = {
                "name": name,
                "dataset_query": {
                    "type": "native",
                    "native": {
                        "query": query,
                        "template-tags": {}
                    },
                    "database": database_id
                },
                "display": display_settings["display"],
                "visualization_settings": display_settings["visualization_settings"]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{METABASE_URL}/api/card",
                    json=question_data,
                    headers=self.headers
                )
                response.raise_for_status()
                result = response.json()

                if not isinstance(result, dict):
                    raise ValueError(f"API返回的数据格式错误: {result}")

                return result
        except httpx.HTTPError as e:
            print(f"HTTP错误: {str(e)}", file=sys.stderr)
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应内容: {e.response.text}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"创建问题失败: {str(e)}", file=sys.stderr)
            raise

    async def create_dashboard(self, name: str, description: str) -> Dict[str, Any]:
        """Create a new dashboard in Metabase."""
        if not self.session_token:
            await self.authenticate()

        dashboard_data = {
            "name": name,
            "description": description
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{METABASE_URL}/api/dashboard",
                json=dashboard_data,
                headers=self.headers
            )
            return response.json()

    async def get_question_details(self, card_id: int) -> Dict[str, Any]:
        """Get question details"""
        try:
            if not self.session_token:
                await self.authenticate()

            print(f"Getting details for question {card_id}...", file=sys.stderr)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/card/{card_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                details = response.json()
                print(f"Successfully retrieved question {card_id} details", file=sys.stderr)
                return details
        except Exception as e:
            print(f"Failed to get question details: {str(e)}", file=sys.stderr)
            return None

    async def check_dashboard_exists(self, dashboard_id: int) -> bool:
        """Check if dashboard exists"""
        try:
            if not self.session_token:
                await self.authenticate()

            print(f"Checking if dashboard {dashboard_id} exists...", file=sys.stderr)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
                )
                exists = response.status_code == 200
                print(f"Dashboard {dashboard_id} exists: {exists}", file=sys.stderr)
                return exists
        except Exception as e:
            print(f"Failed to check dashboard existence: {str(e)}", file=sys.stderr)
            return False

    async def check_question_exists(self, question_id: int) -> bool:
        """Check if question exists"""
        try:
            if not self.session_token:
                await self.authenticate()

            print(f"Checking if question {question_id} exists...", file=sys.stderr)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/card/{question_id}",
                    headers=self.headers
                )
                exists = response.status_code == 200
                print(f"Question {question_id} exists: {exists}", file=sys.stderr)
                return exists
        except Exception as e:
            print(f"Failed to check question existence: {str(e)}", file=sys.stderr)
            return False

    async def get_dashboard_cards(self, dashboard_id: int) -> List[Dict[str, Any]]:
        """Get all cards from a dashboard"""
        try:
            if not self.session_token:
                await self.authenticate()

            print(f"\nGetting cards from dashboard {dashboard_id}...", file=sys.stderr)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                dashboard_data = response.json()
                cards = dashboard_data.get("dashcards", [])
                print(f"Found {len(cards)} cards in dashboard {dashboard_id}", file=sys.stderr)

                # Log details of each existing card
                for i, card in enumerate(cards):
                    print(f"\nCard {i+1} details:", file=sys.stderr)
                    print(f"- ID: {card.get('id')}", file=sys.stderr)
                    print(f"- Card ID: {card.get('card_id')}", file=sys.stderr)
                    print(f"- Position: ({card.get('col')}, {card.get('row')})", file=sys.stderr)
                    print(f"- Size: {card.get('size_x')}x{card.get('size_y')}", file=sys.stderr)

                return cards
        except Exception as e:
            print(f"Failed to get dashboard cards: {str(e)}", file=sys.stderr)
            return []

    async def add_question_to_dashboard(self, dashboard_id: int, question_id: int) -> Dict[str, Any]:
        """Add a card to a dashboard"""
        try:
            print(f"\nStarting to add card {question_id} to dashboard {dashboard_id}", file=sys.stderr)

            if not self.session_token:
                print("No session token, authenticating...", file=sys.stderr)
                await self.authenticate()

            # Check if dashboard exists
            print(f"Step 1: Verifying dashboard {dashboard_id} exists", file=sys.stderr)
            if not await self.check_dashboard_exists(dashboard_id):
                raise ValueError(f"Dashboard ID {dashboard_id} does not exist")

            # Check if question exists
            print(f"Step 2: Verifying question {question_id} exists", file=sys.stderr)
            if not await self.check_question_exists(question_id):
                raise ValueError(f"Question ID {question_id} does not exist")

            # Get question details
            print(f"Step 3: Getting question {question_id} details", file=sys.stderr)
            question_details = await self.get_question_details(question_id)
            if not question_details:
                raise ValueError(f"Failed to get question details for ID {question_id}")

            # Determine card size based on question type
            print("Step 4: Determining card size", file=sys.stderr)
            display_type = question_details.get("display", "table")
            visualization_settings = question_details.get("visualization_settings", {})

            # Default size
            size_x = 8
            size_y = 8

            # Adjust size based on display type
            if display_type == "table":
                row_count = visualization_settings.get("table.row_count", 10)
                size_y = min(16, max(8, (row_count // 5) + 4))
            elif display_type in ["bar", "line", "area"]:
                size_x = 12
                size_y = 12
            elif display_type == "pie":
                size_x = 8
                size_y = 8
            elif display_type == "scatter":
                size_x = 16
                size_y = 12

            # Get existing cards and determine position for new card
            print("\nStep 5: Getting existing cards and determining position", file=sys.stderr)
            existing_cards = await self.get_dashboard_cards(dashboard_id)

            # 初始化位置变量
            new_row = 0
            new_col = 0

            if existing_cards:
                print(f"Found {len(existing_cards)} existing cards", file=sys.stderr)
                # 打印所有现有卡片的信息
                for i, card in enumerate(existing_cards):
                    print(f"Card {i+1}: row={card.get('row', 0)}, col={card.get('col', 0)}, size_x={card.get('size_x', 0)}, size_y={card.get('size_y', 0)}", file=sys.stderr)

                # 找到所有卡片的最大行数
                max_row = max(card.get("row", 0) + card.get("size_y", 0) for card in existing_cards)
                print(f"Maximum row found: {max_row}", file=sys.stderr)

                # 获取最后一行的所有卡片
                last_row_cards = [card for card in existing_cards if card.get("row", 0) == max_row - 1]
                print(f"Found {len(last_row_cards)} cards in the last row", file=sys.stderr)

                if last_row_cards:
                    # 计算最后一行的总宽度
                    last_row_width = sum(card.get("size_x", 0) for card in last_row_cards)
                    print(f"Last row total width: {last_row_width}", file=sys.stderr)

                    # 如果当前行有足够空间（24列）
                    if last_row_width + size_x <= 24:
                        # 找到最后一行的最右边位置
                        rightmost_col = max(card.get("col", 0) + card.get("size_x", 0) for card in last_row_cards)
                        new_row = max_row - 1
                        new_col = rightmost_col
                        print(f"Adding card horizontally at column {new_col} in row {new_row}", file=sys.stderr)
                    else:
                        # 当前行空间不足，换到下一行
                        new_row = max_row
                        new_col = 0
                        print(f"Adding card on a new row {new_row}", file=sys.stderr)
                else:
                    # 如果没有最后一行的卡片，检查当前行是否有空间
                    current_row_cards = [card for card in existing_cards if card.get("row", 0) == 0]
                    if current_row_cards:
                        current_row_width = sum(card.get("size_x", 0) for card in current_row_cards)
                        if current_row_width + size_x <= 24:
                            # 在当前行添加
                            rightmost_col = max(card.get("col", 0) + card.get("size_x", 0) for card in current_row_cards)
                            new_row = 0
                            new_col = rightmost_col
                            print(f"Adding card horizontally at column {new_col} in row {new_row}", file=sys.stderr)
                        else:
                            # 换到下一行
                            new_row = max_row
                            new_col = 0
                            print(f"Adding card on a new row {new_row}", file=sys.stderr)
                    else:
                        # 如果当前行也没有卡片，从第一行开始
                        new_row = 0
                        new_col = 0
                        print("Adding card at the beginning of the dashboard", file=sys.stderr)
            else:
                # 如果仪表板是空的，从第一行开始
                new_row = 0
                new_col = 0
                print("Adding first card to empty dashboard", file=sys.stderr)

            print(f"\nCalculated position for new card:", file=sys.stderr)
            print(f"- New row: {new_row}", file=sys.stderr)
            print(f"- New column: {new_col}", file=sys.stderr)

            print(f"\nStep 6: Preparing card data (size: {size_x}x{size_y}, position: {new_col},{new_row})", file=sys.stderr)

            # Prepare new card data
            new_card = {
                "id": -1,
                "card_id": question_id,
                "dashboard_id": dashboard_id,
                "parameter_mappings": [],
                "visualization_settings": visualization_settings,
                "col": new_col,
                "row": new_row,
                "size_x": size_x,
                "size_y": size_y,
                "series": []
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
                    "series": card.get("series", [])
                }
                all_cards.append(existing_card)

            # 添加新卡片
            all_cards.append(new_card)

            card_data = {
                "cards": all_cards
            }

            print(f"\nStep 7: Sending request to add card to dashboard", file=sys.stderr)
            print(f"Total cards in request: {len(all_cards)}", file=sys.stderr)
            print(f"Request body: {card_data}", file=sys.stderr)
            async with httpx.AsyncClient() as client:
                # First try to get the dashboard to verify access
                print(f"Step 7.1: Verifying dashboard access", file=sys.stderr)
                dashboard_response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
                )
                if dashboard_response.status_code != 200:
                    raise ValueError(f"Failed to access dashboard {dashboard_id}. Status code: {dashboard_response.status_code}")

                # Then try to add the card using PUT request
                print(f"Step 7.2: Adding card to dashboard using PUT request", file=sys.stderr)
                response = await client.put(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                    json=card_data,
                    headers=self.headers
                )

                response.raise_for_status()
                result = response.json()
                print(f"\nSuccessfully added card {question_id} to dashboard {dashboard_id}", file=sys.stderr)
                print(f"Response: {result}", file=sys.stderr)
                return result
        except httpx.HTTPError as e:
            print(f"HTTP error occurred: {str(e)}", file=sys.stderr)
            if e.response is not None:
                print(f"Response status code: {e.response.status_code}", file=sys.stderr)
                print(f"Response body: {e.response.text}", file=sys.stderr)
                if e.response.status_code == 404:
                    raise ValueError(f"Failed to add card. Please verify that:\n1. Dashboard ID {dashboard_id} exists\n2. Question ID {question_id} exists\n3. You have permission to access both the dashboard and question")
                elif e.response.status_code == 403:
                    raise ValueError("You don't have permission to perform this action")
                else:
                    raise ValueError(f"Failed to add card: {str(e)}")
            else:
                raise ValueError(f"Failed to add card: {str(e)}")
        except Exception as e:
            print(f"Unexpected error occurred: {str(e)}", file=sys.stderr)
            import traceback
            print(f"Error stack: {traceback.format_exc()}", file=sys.stderr)
            raise ValueError(f"Failed to add card: {str(e)}")

