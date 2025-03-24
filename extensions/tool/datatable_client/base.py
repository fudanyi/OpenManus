class DataTableClient(object):
    """数据表客户端基类，用于与数据表服务进行交互。"""

    def __init__(self):
        """初始化数据表客户端。"""
        pass

    def list_tables(self, keyword: str = None) -> list:
        """列出所有可用的数据表。

        Args:
            keyword (str, optional): 用于模糊搜索表名的关键词。

        Returns:
            list: 表信息列表。
        """
        raise NotImplementedError("子类必须实现 list_tables 方法")

    def get_table_by_id(self, table_id: str) -> dict:
        """通过表ID获取表信息。

        Args:
            table_id (str): 表的唯一标识符。

        Returns:
            dict: 表信息。
        """
        raise NotImplementedError("子类必须实现 get_table_by_id 方法")

    def get_table_by_name(self, table_name: str) -> dict:
        """通过表名获取表信息。

        Args:
            table_name (str): 表的名称。

        Returns:
            dict: 表信息。
        """
        raise NotImplementedError("子类必须实现 get_table_by_name 方法")

    def get_table_schema(self, table_id: str) -> dict:
        """获取表的schema信息。

        Args:
            table_id (str): 表的唯一标识符。

        Returns:
            dict: 表的schema信息。
        """
        raise NotImplementedError("子类必须实现 get_table_schema 方法")

    def query_data(self, sql_query: str) -> list:
        """执行SQL查询。

        Args:
            sql_query (str): 要执行的SQL查询语句。

        Returns:
            list: 查询结果列表。
        """
        raise NotImplementedError("子类必须实现 query_data 方法")
