---
name: unified-web-search
description: "联网搜索统一接口 - 一个接口自动选择最优服务商（百炼/Tavily/火山引擎），支持降级、合并、告警"
version: 2.1.0
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

# 精确日期窗口（昨天+今天）
result = search(
    "AI 行业新闻",
    start_date="2026-06-21",
    end_date="2026-06-22",
    topic="news",
)

# 平台定向（小红书 / 微信公众号）
result = search("护肤测评", platforms=["xiaohongshu"])
result = search("行业周报", platforms=["wechat"])
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
| freshness | int | None | 相对时效：7/30/180/365 天 |
| start_date | str | None | 起始日期 `YYYY-MM-DD`（与 end_date 搭配） |
| end_date | str | None | 结束日期 `YYYY-MM-DD` |
| sites | list | None | 域名白名单，如 `["gov.cn"]` |
| exclude_sites | list | None | 域名黑名单 |
| platforms | list | None | 平台别名：`xiaohongshu`/`wechat`/`weibo`/`zhihu`/`bilibili`/`douyin`/`gov`/`arxiv` |
| auth_level | int | 0 | 权威过滤：0=全部，1=高权威（火山原生） |
| topic | str | `"general"` | Tavily 话题：`general`/`news`/`finance` |

### 参数路由（按后端能力）

| 参数 | 百炼 | Tavily | 火山 |
|------|------|--------|------|
| freshness | ✅ search_options | ✅ days (≤30) | ✅ OneWeek/Month/Year |
| start_date/end_date | ⚠️ 最近档位 + 后处理 | ✅ 原生 | ✅ `YYYY-MM-DD..YYYY-MM-DD` |
| sites | ✅ assigned_site_list | ✅ include_domains | ✅ Filter.Sites |
| exclude_sites | ⚠️ 后处理 URL | ✅ exclude_domains | ✅ Filter.BlockHosts |
| auth_level | ❌ | ❌ | ✅ AuthInfoLevel |
| topic | ❌ | ✅ | ❌ |
| platforms | 展开为 sites 后同上 | 同上 | 同上 |

不支持原生参数的 backend 会：先用较宽的 `freshness` 搜索，再按日期/域名/权威度后处理过滤。

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

# 精确两天窗口
result = search("AI新闻", start_date="2026-06-21", end_date="2026-06-22")

# 深度查询 + 站点限定
result = search("政策分析", intensity="deep", sites=["gov.cn"])

# 小红书 / 微信定向
result = search("新品发布", platforms=["xiaohongshu", "wechat"], freshness=7)
```

## 搜索强度与服务商路由（v2.1 — 少次数优先）

| 强度 | API 次数 | 国内 | 海外 |
|------|----------|------|------|
| quick | 1 | 火山引擎 | Tavily |
| normal | 1 | 火山引擎 | Tavily |
| deep | ≤2 | 火山引擎 + 百炼 | Tavily + 百炼 |

- 仅调用已配置密钥的后端；`platforms` 为国内平台时不调 Tavily
- `topic=news|finance` 且海外 → 仅 Tavily
- `limit` 只截断返回条数，不增加 API 次数

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

## 调用方式（Hermes 环境）

### terminal 工具（需显式 export）

Hermes `.env` 中的变量**不会自动传递**到 terminal 子进程。调用前必须先 export：

```bash
export $(grep -v '^#' "$HOME/Library/Application Support/HermesNative/data/.env" | grep -E 'BAILIAN_API_KEY|DASHSCOPE_API_KEY|TAVILY_API_KEY|WEB_SEARCH_API_KEY' | xargs) && \
cd "<skill_dir>/scripts" && python3 -c "from web_search import search; print(search('关键词', intensity='normal'))"
```

### execute_code 工具（env 自动继承）

```python
import sys
sys.path.insert(0, '<skill_dir>/scripts')
from web_search import search
result = search("关键词", intensity="normal")
```

## 火山引擎联网搜索（高级场景）

本 skill 内置的 `_volcengine_search` 走 `open.feedcoopapi.com` 端点，暴露基础参数（query, count, time_range 等）。

如需火山引擎搜索的高级功能（权威过滤、Query 改写、图片搜索等），可直接调用同一 API 的完整参数，参考 `references/volcengine-key-types.md` 中的 API 文档链接。内置 `_volcengine_search` 函数已覆盖日常场景，高级参数可按需扩展该函数。

## 其他文件

- **搜索实现** → `scripts/web_search.py`
- **服务商详情与密钥兼容性** → `references/comparison.md`
- **火山引擎三种 Key 详解** → `references/volcengine-key-types.md`
