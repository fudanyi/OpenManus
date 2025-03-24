import json
import os
import uuid
from datetime import datetime
import requests
from extensions.tool.datatable_client.base import DataTableClient


class TrinoDataTableClient(DataTableClient):

    def __init__(self) -> None:
        self._sub = "2847"
        self._url_prefix = "https://abcapi-dev.bottime.com"

        # if dev
        self._headers = {
            "Content-Type": "application/json",
            "x-jwt-auth": "true",
            "x-jwt-payload-sub": self._sub,
            "x-jwt-payload-email": "ignore@gmail.com",
        }
        pass

    def list_tables(self, keyword: str = None) -> list:
        """
        Get a list of all available tables.

        Args:
            keyword (str, optional): Keyword for fuzzy search on table names and display names.

        Returns:
            list: A list of all tables.
        """
        url = "https://abcapi-dev.bottime.com/trino/table"
        params = {}
        if keyword:
            params = {"keyword": keyword}
        res = requests.get(url, headers=self._headers, params=params)
        res.raise_for_status()
        json_result = res.json()
        filtered_data = []
        for item in json_result["data"]:
            filtered_item = {
                "id": item["id"],
                "userId": item["userId"],
                "tableName": item["tableName"],
                "displayName": item["displayName"],
                "description": item["description"],
                "connectionString": item["connectionString"],
                "createdFrom": item["createdFrom"],
                "fieldsCount": item["fieldsCount"],
                "rowsCount": item["rowsCount"],
                "isPublic": item["isPublic"],
                "isReadOnly": item["isReadOnly"],
                "isWeaklyTyped": item["isWeaklyTyped"],
                "createdAt": item["createdAt"],
                "latestModifyAt": item["latestModifyAt"],
            }
            filtered_data.append(filtered_item)
        return filtered_data

    def get_table_by_id(self, table_id: str) -> dict:
        url = f"/trino/table/{table_id}"
        url = f"{self._url_prefix}{url}"
        res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        json_result = res.json()
        result_data = json_result["data"]
        table_info = {
            "id": result_data["id"],
            "displayName": result_data["displayName"],
            "tableName": result_data["tableName"],
            "type": result_data["type"],
        }

        table_schema = self.get_table_schema(table_info["id"])
        return table_info, table_schema

    def get_table_by_name(self, display_name: str) -> dict:
        url = "/trino/table/byname"
        url = f"{self._url_prefix}{url}"
        params = {"tableName": display_name}
        res = requests.get(url, headers=self._headers, params=params)
        res.raise_for_status()
        json_result = res.json()
        result_data = json_result["data"]
        table_info = {
            "id": result_data["id"],
            "displayName": result_data["displayName"],
            "tableName": result_data["tableName"],
            "type": result_data["type"],
        }

        table_schema = self.get_table_schema(table_info["id"])
        return table_info, table_schema

    def get_table_schema(self, table_id: str) -> list:
        url = f"/trino/schema/{table_id}"
        url = f"{self._url_prefix}{url}"
        res = requests.get(url, headers=self._headers)
        res.raise_for_status()
        json_result = res.json()
        result_data = json_result["data"]
        return [
            {
                "fieldName": x["fieldName"],
                "displayName": x["displayName"],
                "isDeleted": x["isDeleted"],
                "fieldType": x["fieldType"],
            }
            for x in result_data
            if x["isDeleted"] == False
        ]

    def query_data(self, sql: str) -> list:
        url = "/trino/query"
        url = f"{self._url_prefix}{url}"
        try:
            res = requests.post(url, headers=self._headers, json=sql)
            res.raise_for_status()
            json_result = res.json()
            if json_result:
                result_data = json_result["data"]
                if not result_data:
                    return []
                if "data" in result_data and result_data["data"]:
                    return result_data["data"]
                else:
                    return result_data
            else:
                return []
        except requests.exceptions.HTTPError:
            error_details = res.json()["error"]
            raise Exception(f"query_table error, details:{error_details}")

    def create_table(self, table_display_name: str, fields: list[dict]) -> tuple:
        """
        [{
            ...
            "DisplayName":'Column1',
            "FieldType":"TEXT",
            ...
        }]
        """
        url = "/trino/table"
        url = f"{self._url_prefix}{url}"
        data = {
            "displayName": table_display_name,
            "tableName": table_display_name,
            "type:": "InternalDB",
            "fields": fields,
        }
        res = requests.post(url, headers=self._headers, json=data)
        res.raise_for_status()
        json_result = res.json()
        result_data = json_result["data"]
        table_info = {
            "id": result_data["id"],
            "displayName": result_data["displayName"],
            "tableName": result_data["tableName"],
        }

        schema = self.get_table_schema(table_info["id"])
        return table_info, schema

    def upload_data(self, table_id: str, data: str) -> list:
        url = f"/trino/table/{table_id}/UploadData"
        url = f"{self._url_prefix}{url}"
        headers = self._headers.copy()

        formdata = {"data": (None, data)}
        res = requests.post(url, headers=headers, files=formdata)
        res.raise_for_status()
        json_result = res.json()
        return json_result["success"]

    def recreate_table(self, table_id: str, fields: list[dict]) -> list:
        url = f"/trino/schema/conver/{table_id}"
        url = f"{self._url_prefix}{url}"
        res = requests.post(url, headers=self._headers, json=fields)
        res.raise_for_status()
        json_result = res.json()
        result_data = json_result["data"]
        table_info = {
            "id": result_data["id"],
            "displayName": result_data["displayName"],
            "tableName": result_data["tableName"],
        }
        schema = self.get_table_schema(table_info["id"])
        return table_info, schema
