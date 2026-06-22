# 联网搜索统一接口

一个接口完成联网搜索，自动选择最优服务商（百炼/Tavily/火山引擎），支持降级、合并、告警。

## 特性

- ✅ **统一接口** - 一个 `search()` 函数，自动选择服务商
- ✅ **智能路由** - 自动判断国内/海外搜索，选择最优服务商
- ✅ **多服务商并行** - 支持百炼、Tavily、火山引擎同时搜索
- ✅ **自动降级** - 主服务商失败时自动切换备用
- ✅ **结果合并** - 去重、排序、合并多个来源
- ✅ **告警机制** - 服务商失败时自动告警

## 安装

```bash
pip install unified-web-search
```

或作为 Claw Skill 使用：将本目录放入技能目录即可。

## 快速开始

```python
from web_search import search

# 快速查询
result = search("北京天气", intensity="quick")

# 一般查询 + 时效筛选
result = search("AI新闻", intensity="normal", freshness=7)

# 精确日期窗口
result = search("AI新闻", start_date="2026-06-21", end_date="2026-06-22")

# 深度查询 + 站点限定
result = search("政策分析", intensity="deep", sites=["gov.cn"])

# 平台定向（小红书 / 微信）
result = search("护肤测评", platforms=["xiaohongshu"])
result = search("行业周报", platforms=["wechat"], freshness=7)

# 使用结果
if result["success"]:
    print(result["answer"])      # 答案文本
    print(result["sources"])     # 来源列表
    print(result["provider"])    # 使用的服务商
else:
    print(result["error"])       # 错误信息
```

## 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | str | 必填 | 搜索问题 |
| intensity | str | `"normal"` | 搜索强度：`quick`/`normal`/`deep` |
| freshness | int | None | 相对时效：7/30/180/365 天 |
| start_date | str | None | 起始日期 `YYYY-MM-DD` |
| end_date | str | None | 结束日期 `YYYY-MM-DD` |
| sites | list | None | 域名白名单 |
| exclude_sites | list | None | 域名黑名单 |
| platforms | list | None | 平台别名：`xiaohongshu`/`wechat`/`weibo` 等 |
| auth_level | int | 0 | 权威过滤（火山原生） |
| topic | str | `"general"` | Tavily 话题：`general`/`news`/`finance` |

参数按后端能力路由：支持则原生传入，否则用较宽 freshness + 后处理过滤。

## 返回值

```python
{
    "success": True,
    "answer": "答案文本",
    "sources": [{"title": "...", "url": "...", "snippet": "..."}],
    "provider": ["bailian", "volcengine"],   # 使用的服务商
    "alerts": [{"provider": "tavily", "error": "..."}]  # 失败告警
}
```

## 配置密钥

### 方式 1：环境变量（推荐）

```bash
# 百炼（推荐国内搜索）
export BAILIAN_API_KEY="sk-eb..."

# Tavily（推荐海外搜索）
export TAVILY_API_KEY="tvly-dev-..."

# 火山引擎联网搜索（国内搜索，每月 500 次免费额度）
export WEB_SEARCH_API_KEY="aZOmTh5u..."
```

### 方式 2：配置文件

创建 `~/.unified-web-search/config.yaml`：

```yaml
bailian:
  api_key: sk-eb...
tavily:
  api_key: tvly-dev-...
volcengine_search:
  api_key: aZOmTh5u...
```

## 服务商说明

| 服务商 | 适用场景 | 特点 | 环境变量 |
|--------|----------|------|----------|
| 百炼（Bailian） | 国内搜索 | 阿里云，中文优化，速度快，answer 质量高 | `BAILIAN_API_KEY` |
| Tavily | 海外搜索 | 专为 AI 设计，结果质量高，自带 answer 摘要 | `TAVILY_API_KEY` |
| 火山引擎（Volcengine Search） | 国内搜索 | 字节跳动，每月 500 次免费额度，支持权威过滤和时间范围 | `WEB_SEARCH_API_KEY` |

## 搜索强度与服务商路由

| 强度 | 国内搜索 | 海外搜索 | 耗时 |
|------|----------|----------|------|
| quick | 火山引擎 | Tavily | ~2s |
| normal | 百炼 + 火山引擎 | Tavily + 火山引擎 | ~4s |
| deep | 百炼 + 火山引擎 + Tavily | 百炼 + 火山引擎 + Tavily | ~6s |

## ⚠️ 火山引擎密钥说明

火山引擎有**三种不同的 key**，用途完全不同，互不通用：

| Key 类型 | 格式 | 用途 | 本 skill 支持 |
|----------|------|------|--------------|
| 联网搜索 API Key | 非标准（如 `aZOmTh5u...`） | 联网搜索专用 | ✅ 使用 `WEB_SEARCH_API_KEY` |
| agentplan key | `ark-cdab573e-...` | 仅 Agent Plan 聊天 | ❌ |
| 通用 ARK API Key | `ark-xxx`（标准格式） | 模型推理 + 搜索工具 | ❌ |

联网搜索 API Key 获取方式：
- 个人用户：[联网搜索控制台](https://console.volcengine.com/search-infinity/api-key) → 创建 API Key
- Agent Plan 用户：[Agent Plan 控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=agentPlan) → 配置 Harness → 联网搜索 → 查看 API Key

## 开发

```bash
# 克隆仓库
git clone https://github.com/naive-white-expert/unified-web-search.git
cd unified-web-search

# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m pytest tests/
```

## License

MIT
