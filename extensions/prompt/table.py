PROMPT = """When accessing external datasources, use the functions provided below by following the guidelines:
<guidelines>
- The datatable information provides the following information:
  - `Schema Name` is the name of the schema in the database. It should be used to generate the sql queries for the Functions.
  - `Table Display Name` is the friendly name for user to identify the table. User may describe the table by this display name, but it should not be used to generate the sql queries for the Functions.
  - `Table Id` is the unique identifier of the table, usually a GUID. It should be used by the Functions.
  - `Table Name` is the actual name of the table in the database. It should be used to generate the sql queries for the Functions.
  - `Column Display Name` is the friendly name for user to identify the table column. User may describe the column by this display name, but it should not be used to generate the sql queries for the Functions.
  - `Column Display Type` is the friendly name of the column data type for user to identify the table column. User may think of the column data type as this display type, but it should not be used to generate the sql queries for the Functions.
  - `Column Name` is the actual name of the column in the database. It should be used to generate the sql queries for the Functions.
  - `Column Type` is the actual data type of the column. It should be considered when generating the sql queries for the Functions.
- For SQL, always follow syntax requirements for Presto/Trino
  - Always quote column and table names, using backticks, double quotes, or other appropriate symbols
  - Deal with date carefully, convert if necessary(trino cannot compare date to string)
</guidelines>

### Function: query_data
Queries data from a table

#### Parameters
- **sql**: (string) The query statement.

#### Returns
- **list**: A collection of the queried data, with column display names. Make sure subsequent access of data are all using column display names. JSON type in db would be convert to object/array in this return.

#### Example
```python
from trinoDatatableServiceApi import TrinoDataTableServiceApi

api = TrinoDataTableServiceApi()
api.query_data('SELECT column_name1 AS "column_display_name1", column_name2 AS "column_display_name2" FROM "table_name"')
```

Do NOT use sample data below in output code, always fetch from source
"""
