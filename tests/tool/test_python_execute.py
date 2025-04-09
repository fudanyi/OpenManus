import pytest
from app.tool.python_execute import PythonExecute

@pytest.mark.asyncio
async def test_python_execute_with_warning():
    """Test that warnings don't cause success to be False"""
    tool = PythonExecute()
    
    # 创建一个会产生 FutureWarning 的代码
    code = """
import pandas as pd
import warnings
df = pd.DataFrame({'date': ['2023-01-01', '2023-01-02']})
df['date'] = pd.to_datetime(df['date'])
df.set_index('date').resample('M').sum()  # 这里会产生 FutureWarning
"""
    
    result = await tool.execute(
        code=code,
        output_files=[],
        charts=[],
        timeout=30
    )
    
    # 验证警告不会导致 success 为 False
    assert result["success"] is True
    # 警告信息可能不会直接显示在输出中，因为我们在代码中设置了 warnings.simplefilter("ignore")

@pytest.mark.asyncio
async def test_python_execute_with_error():
    """Test that actual errors still cause success to be False"""
    tool = PythonExecute()
    
    # 创建一个会产生错误的代码
    code = """
1/0  # 这会引发 ZeroDivisionError
"""
    
    result = await tool.execute(
        code=code,
        output_files=[],
        charts=[],
        timeout=30
    )
    
    # 验证错误会导致 success 为 False
    assert result["success"] is False
    assert "division by zero" in result["observation"]  # 更新为实际的错误信息格式 