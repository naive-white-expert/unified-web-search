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

## 快速开始

```python
from web_search import search

# 快速查询
result = search("北京天气", intensity="quick")

# 一般查询 + 时效筛选
result = search("AI新闻", intensity="normal", freshness=7)

# 深度查询 + 站点限定
result = search("政策分析", intensity="deep", sites=["gov.cn"])

# 使用结果
if result["success"]:
    print(result["answer"])      # 答案文本
    print(result["sources"])     # 来源列表
else:
    print(result["error"])       # 错误信息
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
    "sources": [{"title": "...", "url": "...", "snippet": "..."}],
    "provider": ["bailian", "ark"],  # 使用的服务商
    "alerts": [{"provider": "tavily", "error": "..."}]  # 失败告警
}
```

## 配置密钥

### 方式 1：环境变量

```bash
export BAILIAN_API_KEY="sk-eb..."
export TAVILY_API_KEY="tvly-dev-..."
export ARK_API_KEY="..."
```

### 方式 2：配置文件

创建 `~/.unified-web-search/config.yaml`：

```yaml
bailian:
  api_key: sk-eb...
tavily:
  api_key: tvly-dev-...
ark:
  api_key: ...
```

## 服务商说明

| 服务商 | 适用场景 | 特点 |
|--------|----------|------|
| 百炼（Bailian） | 国内搜索 | 阿里云，中文优化，速度快 |
| Tavily | 海外搜索 | 专为 AI 设计，结果质量高 |
| 火山引擎（Ark） | 国内搜索 | 字节跳动，稳定可靠 |

## 开发

```bash
# 克隆仓库
git clone https://github.com/yourusername/unified-web-search.git
cd unified-web-search

# 安装依赖
pip install -r requirements.txt

# 运行测试
python -m pytest tests/
```

## License

MIT