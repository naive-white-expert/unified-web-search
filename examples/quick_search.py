"""
示例：快速查询
"""
from web_search import search

result = search("北京天气", intensity="quick")

if result["success"]:
    print("答案:", result["answer"])
    print("来源数:", len(result["sources"]))
    print("服务商:", result["provider"])
else:
    print("错误:", result["error"])