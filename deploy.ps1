# 部署OpenManus到服务器 /home/ubuntu/demo/python 下

# 获取今天修改的Python文件
$today = Get-Date -Format "yyyy-MM-dd"
$files = Get-ChildItem -Recurse -File -Filter "*.py" | Where-Object { $_.LastWriteTime -gt (Get-Date).Date }

# 创建远程目录（如果不存在）
ssh agent "mkdir -p /home/ubuntu/demo/python"

# 传输文件到服务器
foreach ($file in $files) {
    $relativePath = $file.FullName.Substring((Get-Location).Path.Length + 1)
    $remotePath = "/home/ubuntu/demo/python/$relativePath"
    
    # 确保远程目录存在
    $remoteDir = Split-Path $remotePath -Parent
    $remoteDir = $remoteDir.Replace("\", "/")  # 将反斜杠转换为正斜杠
    Write-Host "创建远程目录: $remoteDir"
    ssh agent "mkdir -p $remoteDir"
    
    # 传输文件
    scp $file.FullName "agent:$remotePath"
    Write-Host "传输文件: $relativePath"
}

Write-Host "部署完成！" 
