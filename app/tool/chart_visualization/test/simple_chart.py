import asyncio

from app.agent.data_analysis import DataAnalysis
from app.logger import logger

prefix = "帮我生成图表并保存在本地./data下，具体为:"
tasks = [
    {
        "prompt": "帮我展示不同区域各商品销售额",
        "data": """商品名称,region,销售额
可乐,south,2350
可乐,east,1027
可乐,west,1027
可乐,north,1027
雪碧,south,215
雪碧,east,654
雪碧,west,159
雪碧,north,28
芬达,south,345
芬达,east,654
芬达,west,2100
芬达,north,1679
醒目,south,1476
醒目,east,830
醒目,west,532
醒目,north,498
""",
    },
    {
        "prompt": "展示各品牌市场占有率",
        "data": """品牌名称,市场份额,平均价格,净利润
Apple,0.5,7068,314531
Samsung,0.2,6059,362345
Vivo,0.05,3406,234512
Nokia,0.01,1064,-1345
Xiaomi,0.1,4087,131345""",
    },
    {
        "prompt": "请帮我展示各产品的销售趋势",
        "data": """date,type,value
2023-01-01,产品 A,52.9
2023-01-01,产品 B,63.6
2023-01-01,产品 C,11.2
2023-01-02,产品 A,45.7
2023-01-02,产品 B,89.1
2023-01-02,产品 C,21.4
2023-01-03,产品 A,67.2
2023-01-03,产品 B,82.4
2023-01-03,产品 C,31.7
2023-01-04,产品 A,80.7
2023-01-04,产品 B,55.1
2023-01-04,产品 C,21.1
2023-01-05,产品 A,65.6
2023-01-05,产品 B,78
2023-01-05,产品 C,31.3
2023-01-06,产品 A,75.6
2023-01-06,产品 B,89.1
2023-01-06,产品 C,63.5
2023-01-07,产品 A,67.3
2023-01-07,产品 B,77.2
2023-01-07,产品 C,43.7
2023-01-08,产品 A,96.1
2023-01-08,产品 B,97.6
2023-01-08,产品 C,59.9
2023-01-09,产品 A,96.1
2023-01-09,产品 B,100.6
2023-01-09,产品 C,66.8
2023-01-10,产品 A,101.6
2023-01-10,产品 B,108.3
2023-01-10,产品 C,56.9 """,
    },
    {
        "prompt": "展示搜索关键词热度",
        "data": """关键词,热度
热词,1000
燥了我们,800
娆贱货,400
我的心愿是世界和平,400
咻咻咻,400
神舟十一号,400
百鸟朝风,400
中国女排,400
我的关呐,400
腿咚,400
火锅英雄,400
宝宝心里苦,400
奥运会,400
厉害了我的哥,400
诗和远方,400
宋仲基,400
PPAP,400
蓝瘦香菇,400
雨露均沾,400
友谊的小船说翻就翻就翻,400
北京瘫,400
敬业,200
Apple,200
狗带,200
老司机,200
吃瓜群众,200
疯狂动物城,200
城会玩,200
套路,200
水逆,200
你咋不上天呢,200
蛇精男,200
你咋不上天呢,200
三星爆炸门,200
小李子奥斯卡,200
人丑就要多读书,200
男友力,200
一脸懵逼,200
太阳的后裔,200""",
    },
    {
        "prompt": "帮我比较不同电动汽车品牌性能，使用散点图",
        "data": """续航里程,充电时间,品牌名称,平均价格
2904,46,品牌1,2350
1231,146,品牌2,1027
5675,324,品牌3,1242
543,57,品牌4,6754
326,234,品牌5,215
1124,67,品牌6,654
3426,81,品牌7,159
2134,24,品牌8,28
1234,52,品牌9,345
2345,27,品牌10,654
526,145,品牌11,2100
234,93,品牌12,1679
567,94,品牌13,1476
789,45,品牌14,830
469,75,品牌15,532
5689,54,品牌16,498
""",
    },
    {
        "prompt": "展示各个流程转化率",
        "data": """流程,转化率,Month
Step1,100,1
Step2,80,1
Step3,60,1
Step4,40,1""",
    },
    {
        "prompt": "展示男女早餐饭量不同",
        "data": """时间,男-早餐,女-早餐
周一,15,22
周二,12,10
周三,15,20
周四,10,12
周五,13,15
周六,10,15
周日,12,14""",
    },
    {
        "prompt": "帮我展示这个人在不同方面的绩效，他是否是六边形战士",
        "data": """dimension,performance
Strength,5
Speed,5
Shooting,3
Endurance,5
Precision,5
Growth,5""",
    },
    {
        "prompt": "展示数据流动",
        "data": """始发地,终点站,value
Node A,Node 1,10
Node A,Node 2,5
Node B,Node 2,8
Node B,Node 3,2
Node C,Node 2,4
Node A,Node C,2
Node C,Node 1,2""",
    },
]


async def main():
    for index, item in enumerate(tasks):
        logger.info(f"Begin task {index} / {len(tasks)}!")
        agent = DataAnalysis()
        await agent.run(
            f"{prefix},chart_description:{item["prompt"]},Data:{item["data"]}"
        )
        logger.info(f"Finish with {item["prompt"]}")


if __name__ == "__main__":
    asyncio.run(main())
