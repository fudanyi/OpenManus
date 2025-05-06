from typing import Any, Dict, List
import httpx
from mcp.server.fastmcp import FastMCP
import sys
import asyncio

# Initialize FastMCP server
mcp = FastMCP("metabase")

# Constants
METABASE_URL = "http://111.231.167.99:3000"
METABASE_USER = "silver.sun@encootech.com"
METABASE_PASSWORD = "y79S6djYpqUdCA"
METABASE_DATABASE_ID = 2

def log_debug(message: str):
    """输出调试日志到stderr"""
    print(message, file=sys.stderr)


async def get_table_structure(table_name: str):
    """通过Metabase API获取表结构和前10条数据"""
    try:
        log_debug(f"\n[get_table_structure] Starting to get table structure for: {table_name}")
        
        # 认证
        if not hasattr(metabase_api, 'session_token') or not metabase_api.session_token:
            await metabase_api.authenticate()

        # 使用固定的数据库ID
        database_id = METABASE_DATABASE_ID

        # 使用Metabase API获取表结构
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 获取表结构
            structure_url = f"{METABASE_URL}/api/database/{database_id}/metadata"
            log_debug(f"[get_table_structure] Requesting table structure from: {structure_url}")
            
            structure_response = await client.get(
                structure_url,
                headers=metabase_api.headers
            )
            structure_response.raise_for_status()
            structure_data = structure_response.json()
            
            # 找到目标表
            target_table = None
            for table in structure_data.get("tables", []):
                if table.get("name") == table_name:
                    target_table = table
                    break
            
            if not target_table:
                raise ValueError(f"Table {table_name} not found in database")
            
            # 获取列信息
            columns = []
            for field in target_table.get("fields", []):
                columns.append([
                    field.get("name"),
                    field.get("base_type"),
                    field.get("dimension", {}).get("max_length")
                ])
            
            log_debug(f"[get_table_structure] Start to get sample data for: {table_name}")
            # 获取样例数据
            sample_query = f"SELECT * FROM {table_name} LIMIT 10"
            sample_data = {
                "type": "native",
                "native": {
                    "query": sample_query,
                    "template-tags": {}
                },
                "database": METABASE_DATABASE_ID
            }
            sample_response = await client.post(
                f"{METABASE_URL}/api/dataset",
                json=sample_data,
                headers=metabase_api.headers
            )
            sample_response.raise_for_status()
            sample_result = sample_response.json()
            sample_rows = sample_result.get("data", {}).get("rows", [])

            log_debug(f"[get_table_structure] Successfully retrieved data:")
            log_debug(f"- Number of columns: {len(columns)}")
            log_debug(f"- Number of sample rows: {len(sample_rows)}")

            return {
                "columns": columns,
                "sample_data": sample_rows
            }
    except Exception as e:
        log_debug(f"\n[get_table_structure] Failed to get table structure:")
        log_debug(f"- Error type: {type(e).__name__}")
        log_debug(f"- Error message: {str(e)}")
        import traceback
        log_debug(f"- Error stack: {traceback.format_exc()}")
        raise

class MetabaseAPI:
    def __init__(self):
        self.session_token = None
        self.headers = {
            "Content-Type": "application/json"
        }

    async def authenticate(self) -> bool:
        """Authenticate with Metabase and get session token."""
        auth_url = f"{METABASE_URL}/api/session"
        auth_data = {
            "username": METABASE_USER,
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
                log_debug(f"Authentication failed: {str(e)}")
                return False


    async def analyze_query_data(self, query: str) -> Dict[str, Any]:
        """Analyze query data to determine the best visualization type"""
        try:
            log_debug(f"\nStarting data analysis...")
            log_debug(f"Query: {query}")
            
            if not self.session_token:
                await self.authenticate()

            # Get database ID
            database_id = METABASE_DATABASE_ID
            log_debug(f"Database ID: {database_id}")
            
            # Execute sample query
            sample_query = f"WITH sample AS ({query}) SELECT * FROM sample LIMIT 1000"
            log_debug(f"Sample query: {sample_query}")
            
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
                    log_debug("Warning: Query returned empty result")
                    return {"display": "table", "visualization_settings": {}}
                
                rows = data["data"]["rows"]
                columns = data["data"]["cols"]
                log_debug(f"\nData characteristics:")
                log_debug(f"- Total rows: {len(rows)}")
                log_debug(f"- Total columns: {len(columns)}")
                
                # Create column name to index mapping
                col_name_to_idx = {col["name"]: idx for idx, col in enumerate(columns)}
                
                # Analyze data characteristics
                numeric_columns = []
                date_columns = []
                categorical_columns = []
                
                log_debug("\nColumn type analysis:")
                for col in columns:
                    log_debug(f"- Column: {col['name']}, Type: {col['base_type']}")
                    if col["base_type"] in ["type/Integer", "type/Float", "type/Decimal"]:
                        numeric_columns.append(col["name"])
                    elif col["base_type"] == "type/DateTime":
                        date_columns.append(col["name"])
                    else:
                        categorical_columns.append(col["name"])
                
                log_debug(f"\nNumeric columns: {numeric_columns}")
                log_debug(f"Date columns: {date_columns}")
                log_debug(f"Categorical columns: {categorical_columns}")
                
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
                        log_debug(f"\n{col} statistics:")
                        log_debug(f"- Min: {min_val}")
                        log_debug(f"- Max: {max_val}")
                        log_debug(f"- Avg: {avg_val}")
                        log_debug(f"- Std Dev: {std_dev}")
                        log_debug(f"- Range: {max_val - min_val}")

                # Analyze categorical column cardinalities
                categorical_cardinalities = {}
                for col in categorical_columns:
                    col_idx = col_name_to_idx[col]
                    values = [row[col_idx] for row in rows if row[col_idx] is not None]
                    unique_values = len(set(values))
                    categorical_cardinalities[col] = unique_values
                    log_debug(f"\n{col} unique values count: {unique_values}")

                # Determine visualization type
                log_debug("\nSelecting visualization type:")
                if len(date_columns) == 1 and len(numeric_columns) >= 1:
                    if len(numeric_columns) == 1:
                        log_debug("Selected: Line chart - Single metric over time")
                        return {
                            "display": "line",
                            "visualization_settings": {
                                "graph.dimensions": date_columns,
                                "graph.metrics": numeric_columns[:1]
                            }
                        }
                    else:
                        log_debug("Selected: Area chart - Multiple metrics over time")
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
                            log_debug("Selected: Pie chart - Small number of categories")
                            return {
                                "display": "pie",
                                "visualization_settings": {
                                    "pie.dimension": categorical_columns[0],
                                    "pie.metric": numeric_columns[0]
                                }
                            }
                        else:
                            log_debug("Selected: Bar chart - Large number of categories")
                            return {
                                "display": "bar",
                                "visualization_settings": {
                                    "graph.dimensions": categorical_columns[:1],
                                    "graph.metrics": numeric_columns[:1]
                                }
                            }
                    else:
                        log_debug("Selected: Stacked bar chart - Multiple metrics by category")
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
                        log_debug(f"\n{col1} and {col2} correlation: {correlation}")
                        
                        if abs(correlation) > 0.5:
                            log_debug("Selected: Scatter plot - Strong correlation")
                            return {
                                "display": "scatter",
                                "visualization_settings": {
                                    "scatter.dimension": col1,
                                    "scatter.metric": col2,
                                    "scatter.show_trendline": True
                                }
                            }
                
                log_debug("Selected: Table - Default visualization")
                return {
                    "display": "table",
                    "visualization_settings": {
                        "table.pivot": False,
                        "table.cell_column": None
                    }
                }
                    
        except Exception as e:
            log_debug(f"\nData analysis failed: {str(e)}")
            import traceback
            log_debug(f"Error stack: {traceback.format_exc()}")
            return {"display": "table", "visualization_settings": {}}

    async def create_question(self, name: str, query: str) -> Dict[str, Any]:
        """Create a new question (query) in Metabase."""
        try:
            if not self.session_token:
                await self.authenticate()

            # 获取数据库ID
            database_id = METABASE_DATABASE_ID
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
            log_debug(f"HTTP错误: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                log_debug(f"响应内容: {e.response.text}")
            raise
        except Exception as e:
            log_debug(f"创建问题失败: {str(e)}")
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

            log_debug(f"Getting details for question {card_id}...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{METABASE_URL}/api/card/{card_id}",
                    headers=self.headers
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
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
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
                    f"{METABASE_URL}/api/card/{question_id}",
                    headers=self.headers
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
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
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
        row: int = None
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
                    log_debug(f"Card {i+1}: row={card.get('row', 0)}, col={card.get('col', 0)}, size_x={card.get('size_x', 0)}, size_y={card.get('size_y', 0)}")
                
                # 找到所有卡片的最大行数
                max_row = max(card.get("row", 0) + card.get("size_y", 0) for card in existing_cards)
                log_debug(f"Maximum row found: {max_row}")
                
                # 获取最后一行的所有卡片
                last_row_cards = [card for card in existing_cards if card.get("row", 0) == max_row - 1]
                log_debug(f"Found {len(last_row_cards)} cards in the last row")
                
                if last_row_cards:
                    # 计算最后一行的总宽度
                    last_row_width = sum(card.get("size_x", 0) for card in last_row_cards)
                    log_debug(f"Last row total width: {last_row_width}")
                    
                    # 如果当前行有足够空间（24列）
                    if last_row_width + final_size_x <= 24:
                        # 找到最后一行的最右边位置
                        rightmost_col = max(card.get("col", 0) + card.get("size_x", 0) for card in last_row_cards)
                        final_row = max_row - 1
                        final_col = rightmost_col
                        log_debug(f"Adding card horizontally at column {final_col} in row {final_row}")
                    else:
                        # 当前行空间不足，换到下一行
                        final_row = max_row
                        final_col = 0
                        log_debug(f"Adding card on a new row {final_row}")
                else:
                    # 如果没有最后一行的卡片，检查当前行是否有空间
                    current_row_cards = [card for card in existing_cards if card.get("row", 0) == 0]
                    if current_row_cards:
                        current_row_width = sum(card.get("size_x", 0) for card in current_row_cards)
                        if current_row_width + final_size_x <= 24:
                            # 在当前行添加
                            rightmost_col = max(card.get("col", 0) + card.get("size_x", 0) for card in current_row_cards)
                            final_row = 0
                            final_col = rightmost_col
                            log_debug(f"Adding card horizontally at column {final_col} in row {final_row}")
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
                log_debug(f"Using provided or default position: row={final_row}, col={final_col}")

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

            log_debug(f"\nStep 7: Sending request to add card to dashboard")
            log_debug(f"Total cards in request: {len(all_cards)}")
            log_debug(f"Request body: {card_data}")
            async with httpx.AsyncClient() as client:
                # First try to get the dashboard to verify access
                log_debug(f"Step 7.1: Verifying dashboard access")
                dashboard_response = await client.get(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}",
                    headers=self.headers
                )
                if dashboard_response.status_code != 200:
                    raise ValueError(f"Failed to access dashboard {dashboard_id}. Status code: {dashboard_response.status_code}")

                # Then try to add the card using PUT request
                log_debug(f"Step 7.2: Adding card to dashboard using PUT request")
                response = await client.put(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                    json=card_data,
                    headers=self.headers
                )
                
                response.raise_for_status()
                result = response.json()
                log_debug(f"\nSuccessfully added card {card_id} to dashboard {dashboard_id}")
                log_debug(f"Response: {result}")
                return result
        except httpx.HTTPError as e:
            log_debug(f"HTTP error occurred: {str(e)}")
            if e.response is not None:
                log_debug(f"Response status code: {e.response.status_code}")
                log_debug(f"Response body: {e.response.text}")
                if e.response.status_code == 404:
                    raise ValueError(f"Failed to add card. Please verify that:\n1. Dashboard ID {dashboard_id} exists\n2. Question ID {card_id} exists\n3. You have permission to access both the dashboard and question")
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
        row: int = 0
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
                    "virtual_card": {
                        "archived:": False,
                        "display": "text" 
                    }
                },
                "col": col,
                "row": row,
                "size_x": size_x,
                "size_y": size_y,
                "series": []
            }

            # Set text type specific settings
            if text_type == "heading":
                text_card["visualization_settings"]["virtual_card"].update({
                    "display": "heading"
                })

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
                    "series": card.get("series", [])
                }
                all_cards.append(existing_card)
            
            all_cards.append(text_card)

            card_data = {
                "cards": all_cards
            }

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
                    json=card_data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log_debug(f"Failed to add text card to dashboard: {str(e)}")
            raise

    async def create_database(
        self,
        name: str,
        engine: str,  # "mysql" or "postgres"
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: str,
        ssl: bool = False,
    ) -> Dict[str, Any]:
        """Create a new database connection in Metabase.
        
        Args:
            name: Database name in Metabase
            engine: Database type ("mysql" or "postgres")
            host: Database host
            port: Database port
            dbname: Database name
            user: Database username
            password: Database password
            ssl: Whether to use SSL connection
        """
        try:
            if not self.session_token:
                await self.authenticate()

            # Prepare database details
            details = {
                "host": host,
                "port": port,
                "dbname": dbname,
                "user": user,
                "password": password,
                "ssl": ssl,
                "advanced-options": False
            }

            # Prepare database data
            database_data = {
                "name": name,
                "engine": "mysql" if engine.lower() == "mysql" else "postgres",
                "details": details,
                "is_full_sync": True,
                "is_on_demand": False,
                "auto_run_queries": True
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{METABASE_URL}/api/database",
                    json=database_data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            log_debug(f"Failed to create database: {str(e)}")
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
    return f"Successfully created dashboard '{dashboard_name}', ID: {dashboard['id']}"

@mcp.tool()
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
            return {"error": "Failed to connect to Metabase, please check authentication"}

        # Get database ID
        database_id = METABASE_DATABASE_ID
        
        # Execute query
        question_data = {
            "type": "native",
            "native": {
                "query": sql_query,
                "template-tags": {}
            },
            "database": database_id
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{METABASE_URL}/api/dataset",
                json=question_data,
                headers=metabase_api.headers
            )
            response.raise_for_status()
            data = response.json()
            
            return {
                "data": data.get("data", {}).get("rows", []),
                "columns": data.get("data", {}).get("cols", []),
                "row_count": len(data.get("data", {}).get("rows", [])),
                "column_count": len(data.get("data", {}).get("cols", []))
            }
    except Exception as e:
        return {"error": f"Failed to execute query: {str(e)}"}

@mcp.tool()
async def create_question(
    question_name: str, 
    sql_query: str,
    display_type: str = None,
    visualization_settings: Dict[str, Any] = None
) -> str:
    """
    Create a new question (query)

    Args:
        question_name: Question name
        sql_query: SQL query
            - Field names in SQL must be enclosed in double quotes ("). For example: SELECT "field1", "field2" FROM "table"
            - Only use SQL syntax and functions supported by Trino (Presto). Do NOT use MySQL-specific or PostgreSQL-specific functions.
        display_type: Optional display type for the visualization
            - table: Table view
            - line: Line chart
            - bar: Bar chart
            - area: Area chart
            - pie: Pie chart
            - scatter: Scatter plot
        visualization_settings: Optional settings for the visualization
            - For table: {"table.row_count": 10}
            - For line/bar/area: {"graph.dimensions": ["column1"], "graph.metrics": ["column2"]}
            - For pie: {"pie.dimension": "column1", "pie.metric": "column2"}
            - For scatter: {"scatter.dimension": "column1", "scatter.metric": "column2"}

    Note:
        If display_type and visualization_settings are not provided, the system will
        automatically analyze the query result and determine the best visualization type.
    """
    try:
        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        # 获取数据库ID
        database_id = METABASE_DATABASE_ID
        if not isinstance(database_id, int):
            raise ValueError(f"数据库ID必须是整数，但得到的是 {type(database_id)}: {database_id}")

        # 如果提供了显示类型和设置，直接使用
        if display_type and visualization_settings:
            question_data = {
                "name": question_name,
                "dataset_query": {
                    "type": "native",
                    "native": {
                        "query": sql_query,
                        "template-tags": {}
                    },
                    "database": database_id
                },
                "display": display_type,
                "visualization_settings": visualization_settings
            }
        else:
            # 否则分析数据以确定最佳展示方式
            display_settings = await metabase_api.analyze_query_data(sql_query)
            question_data = {
                "name": question_name,
                "dataset_query": {
                    "type": "native",
                    "native": {
                        "query": sql_query,
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
                headers=metabase_api.headers
            )
            response.raise_for_status()
            result = response.json()
            
            if not isinstance(result, dict):
                raise ValueError(f"API返回的数据格式错误: {result}")
                
            return f"Successfully created question '{question_name}', ID: {result['id']}"
    except httpx.HTTPError as e:
        log_debug(f"HTTP错误: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
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
    row: int = None
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
        log_debug(f"\nStarting to add question {question_id} to dashboard {dashboard_id}")
        
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
            dashboard_id, 
            question_id,
            size_x=size_x,
            size_y=size_y,
            col=col,
            row=row
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
        log_debug(f"\n[get_table_info] Starting to get table info: {table_name}")

        if not await metabase_api.authenticate():
            log_debug("[get_table_info] Metabase authentication failed")
            return "Failed to connect to Metabase, please check authentication"

        log_debug(f"[get_table_info] Authentication successful, preparing to get table structure and sample data")
        table_info = await get_table_structure(table_name)
        
        # Check returned data structure
        log_debug(f"\n[get_table_info] Retrieved table structure data:")
        log_debug(f"- Has columns field: {'columns' in table_info}")
        if 'columns' in table_info:
            log_debug(f"- Number of columns: {len(table_info['columns'])}")
            log_debug(f"- Columns content: {table_info['columns']}")
        
        log_debug(f"\n[get_table_info] Retrieved sample data:")
        log_debug(f"- Has sample_data field: {'sample_data' in table_info}")
        if 'sample_data' in table_info:
            log_debug(f"- Number of sample rows: {len(table_info['sample_data'])}")
            log_debug(f"- Sample data content: {table_info['sample_data']}")

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
        
        log_debug(f"\n[get_table_info] Final result length: {len(result)}")
        return result
    except Exception as e:
        log_debug(f"\n[get_table_info] Failed to get table info:")
        log_debug(f"- Error type: {type(e).__name__}")
        log_debug(f"- Error message: {str(e)}")
        import traceback
        log_debug(f"- Error stack: {traceback.format_exc()}")
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
    row: int = 0
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
            dashboard_id,
            text,
            text_type,
            text_align,
            size_x,
            size_y,
            col,
            row
        )
        return f"Successfully added {text_type} to dashboard, ID: {dashboard_id}"
    except Exception as e:
        return f"Failed to add text to dashboard: {str(e)}"

@mcp.tool()
async def create_datasource(
    name: str,
    engine: str,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    ssl: bool = False
) -> str:
    """
    Create a new database connection in Metabase

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
    try:
        if not await metabase_api.authenticate():
            return "Failed to connect to Metabase, please check authentication"

        result = await metabase_api.create_database(
            name=name,
            engine=engine,
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            ssl=ssl
        )
        return f"Successfully created database connection '{name}', ID: {result['id']}"
    except Exception as e:
        return f"Failed to create database connection: {str(e)}"

if __name__ == "__main__":
    try:
        log_debug("Starting MCP server...")
        mcp.run(transport='stdio')
    except Exception as e2:
        log_debug(f"All transport methods failed: {str(e2)}")
