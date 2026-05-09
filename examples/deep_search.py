"""
示例：深度查询 + 时效筛选
"""
from web_search import search

# 搜索最近7天的AI新闻
result = search("AI最新进展", intensity="deep", freshness=7)

if result["success"]:
    print("答案:", result["answer"])
    print("\n来源:")
    for source in result["sources"]:
        print(f"  - {source['title']}: {source['url']}")
    
    if result.get("alerts"):
        print("\n告警:", result["alerts"])
else:
    print("错误:", result["error"])