---
name: unified-web-search
description: "联网搜索统一接口 - 一个接口自动选择最优服务商（百炼/Tavily/火山引擎），支持降级、合并、告警"
version: 2.0.0
author: Kang Rui
metadata:
  openclaw:
    requires:
      env:
        - BAILIAN_API_KEY
        - TAVILY_API_KEY
        - WEB_SEARCH_API_KEY
    primaryEnv: BAILIAN_API_KEY
    homepage: "https://github.com/naive-white-expert/unified-web-search"
---

# 联网搜索

一个接口完成联网搜索，自动选择最优服务商（百炼 / Tavily / 火山引擎）。

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
    provider = result["provider"]  # 使用的服务商列表
else:
    error = result["error"]        # 错误信息
```

## 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | 必填 | 搜索问题 |
| intensity | str | `"normal"` | 搜索强度：`quick`（快速）/`normal`（平衡）/`deep`（全面） |
| freshness | int | None | 时效筛选：7/30/180/365 天 |
| sites | list | None | 限定站点：["gov.cn"]（百炼/Tavily 支持，火山引擎暂不支持） |

## 返回值

```python
{
    "success": True,
    "answer": "答案文本",
    "sources": [{"title": "...", "url": "...", "snippet": "..."}],
    "provider": ["bailian", "volcengine"],   # 实际使用的服务商
    "alerts": []                              # 失败的服务商告警
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

## 搜索强度与服务商路由

| 强度 | 国内搜索 | 海外搜索 | 耗时 |
|------|----------|----------|------|
| quick | 火山引擎 | Tavily | ~2s |
| normal | 百炼 + 火山引擎 | Tavily + 火山引擎 | ~4s |
| deep | 百炼 + 火山引擎 + Tavily | 百炼 + 火山引擎 + Tavily | ~6s |

## 配置密钥

使用前需配置至少一个服务商密钥（环境变量）：

| 环境变量 | 服务商 | 获取地址 | 说明 |
|----------|--------|----------|------|
| `BAILIAN_API_KEY` | 百炼（推荐国内） | [DashScope](https://dashscope.aliyun.com/) | 也接受 `DASHSCOPE_API_KEY` |
| `TAVILY_API_KEY` | Tavily（推荐海外） | [tavily.com](https://tavily.com/) | 专为 AI 设计的搜索 |
| `WEB_SEARCH_API_KEY` | 火山引擎联网搜索 | [联网搜索控制台](https://console.volcengine.com/search-infinity/api-key) 或 [Agent Plan 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentPlan) | 非标准 `ark-xxx` 格式 |

### 密钥配置方式

**方式 1：环境变量**

```bash
export BAILIAN_API_KEY="sk-eb..."
export TAVILY_API_KEY="tvly-dev-..."
export WEB_SEARCH_API_KEY="aZOmTh5u..."
```

**方式 2：配置文件**

创建 `~/.unified-web-search/config.yaml`：

```yaml
bailian:
  api_key: sk-eb...
tavily:
  api_key: tvly-dev-...
volcengine_search:
  api_key: aZOmTh5u...
```

## Pitfalls

### 火山引擎联网搜索 API Key ≠ Ark API Key，三者互不通用

火山引擎有三种 key，用途完全不同：

| Key 类型 | 格式 | 用途 | 端点 |
|----------|------|------|------|
| **联网搜索 API Key** | 非标准（如 `aZOmTh5u...`） | 联网搜索专用 | `open.feedcoopapi.com/search_api/web_search` |
| **agentplan key** | `ark-cdab573e-...` | 仅 Agent Plan 聊天 | `/api/plan/v3` |
| **通用 ARK API Key** | `ark-xxx`（标准格式） | 模型推理 + 搜索工具 | `/api/v3/responses` |

如果拿联网搜索 Key 调 `/api/v3/responses` 或拿 agentplan key 调搜索 API 都会返回 401。

**结论**：本 skill 的火山引擎搜索统一走 `open.feedcoopapi.com` 端点，使用 `WEB_SEARCH_API_KEY` 环境变量，不走 Ark 端点。

### 百炼搜索不返回 sources 列表
百炼 API 的 `search_info.search_results` 字段在当前测试中未返回来源（sources 为空列表），但 answer 质量很好。Tavily 和火山引擎会正常返回 sources。

### terminal 子进程不继承 .env 变量
Hermes `.env` 中的变量对 terminal 工具启动的子进程不可见。必须先 `export` 所需变量，否则脚本会报"密钥未配置"。`execute_code` 工具不受此影响（继承进程环境）。

## 其他文件

- **搜索实现** → `scripts/web_search.py`
- **服务商详情与密钥兼容性** → `references/comparison.md`
