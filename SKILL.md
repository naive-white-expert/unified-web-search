---
name: unified-web-search
description: "联网搜索统一接口 - 一个接口自动选择最优服务商（百炼/Tavily/火山引擎），支持降级、合并、告警"
version: 1.0.0
author: Kang Rui
metadata:
  openclaw:
    requires:
      env:
        - BAILIAN_API_KEY
        - TAVILY_API_KEY
        - ARK_API_KEY
    primaryEnv: BAILIAN_API_KEY
    homepage: "https://github.com/naive-white-expert/unified-web-search"
---

# 联网搜索

一个接口完成联网搜索，自动选择最优服务商。

## 使用场景

- 用户需要搜索任何网络信息

## 使用流程

```
1. 判断搜索强度 → 2. 调用接口 → 3. 使用结果
```

### 1. 判断搜索强度

| 用户需求 | intensity 参数 | 说明 |
|----------|----------------|------|
| 快速查询（天气、股价） | `"quick"` | 速度最快 |
| 一般查询（新闻、常识） | `"normal"` | 平衡速度和覆盖 |
| 深度查询（研究、分析） | `"deep"` | 结果最全面 |

### 2. 调用接口

```python
from web_search import search

result = search("关键词", intensity="quick", freshness=7, sites=["gov.cn"])
```

### 3. 使用结果

```python
if result["success"]:
    answer = result["answer"]      # 答案文本
    sources = result["sources"]    # 来源列表
else:
    error = result["error"]        # 错误信息
```

## 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | 必填 | 搜索问题 |
| intensity | str | `"normal"` | 搜索强度：`quick`（快速）/`normal`（平衡）/`deep`（全面） |
| freshness | int | None | 时效筛选：7/30/180/365 天 |
| sites | list | None | 限定站点：["gov.cn"] |

## 返回值

```python
{
    "success": True,
    "answer": "答案文本",
    "sources": [{"title": "...", "url": "..."}]
}
```

## 示例

```python
from web_search import search

# 快速查询
result = search("北京天气", intensity="quick")

# 一般查询 + 时效筛选
result = search("AI新闻", intensity="normal", freshness=7)

# 深度查询 + 站点限定
result = search("政策分析", intensity="deep", sites=["gov.cn"])
```

## 配置密钥

使用前需配置至少一个服务商密钥：

```bash
# 百炼（推荐国内搜索）
export BAILIAN_API_KEY="sk-eb..."

# Tavily（推荐海外搜索）
export TAVILY_API_KEY="tvly-dev-..."

# 火山引擎（国内备用）
export ARK_API_KEY="..."
```

## 其他文件

- **搜索实现** → `scripts/web_search.py`
- **服务商详情** → `references/comparison.md`