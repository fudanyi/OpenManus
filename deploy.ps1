# 部署OpenManus到服务器 /home/ubuntu/demo/python 下

# 直接在远程拉取git代码
ssh agent "cd /home/ubuntu/demo/python && git pull || echo '部署失败'"

Write-Host "Deployment completed!" 