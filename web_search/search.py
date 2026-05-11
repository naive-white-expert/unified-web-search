"""
联网搜索模块 - 统一接口，自动选择服务商

使用方法：
    from web_search import search

    result = search("关键词")
    if result["success"]:
        print(result["answer"])
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any

# ============================================================================
# 配置管理
# ============================================================================

CONFIG_DIR = Path.home() / ".unified-web-search"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _load_config() -> dict:
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            import yaml
            with open(CONFIG_FILE) as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _get_bailian_key() -> str:
    """获取百炼 API Key"""
    key = os.getenv("BAILIAN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if key and len(key) > 20 and "..." not in key:
        return key
    config = _load_config()
    cfg_key = config.get("bailian", {}).get("api_key", "")
    if cfg_key and "..." not in cfg_key and len(cfg_key) > 20:
        return cfg_key
    return ""


def _get_tavily_key() -> str:
    """获取 Tavily API Key"""
    key = os.getenv("TAVILY_API_KEY")
    if key and len(key) > 20 and "..." not in key:
        return key
    config = _load_config()
    cfg_key = config.get("tavily", {}).get("api_key", "")
    if cfg_key and "..." not in cfg_key and len(cfg_key) > 20:
        return cfg_key
    return ""


def _get_volcengine_search_key() -> str:
    """获取火山引擎联网搜索 API Key（WEB_SEARCH_API_KEY）"""
    key = os.getenv("WEB_SEARCH_API_KEY")
    if key and len(key) > 10 and "..." not in key:
        return key
    config = _load_config()
    cfg_key = config.get("volcengine_search", {}).get("api_key", "")
    if cfg_key and "..." not in cfg_key and len(cfg_key) > 10:
        return cfg_key
    return ""


# ============================================================================
# 搜索实现
# ============================================================================

def _bailian_search(query: str, strategy: str = "max", freshness: int = None, sites: list = None) -> dict:
    """百炼搜索（阿里云）"""
    api_key = _get_bailian_key()
    if not api_key:
        return {"success": False, "error": "百炼密钥未配置", "provider": "bailian"}
    
    endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    search_options = {"search_strategy": strategy}
    if freshness:
        search_options["freshness"] = freshness
    if sites:
        search_options["assigned_site_list"] = sites
    
    payload = {
        "model": "qwen-plus",
        "messages": [{"role": "user", "content": query}],
        "enable_search": True,
        "search_options": search_options,
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
            answer = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
            sources = []
            if "search_info" in raw.get("output", {}):
                for item in raw["output"]["search_info"].get("search_results", []):
                    sources.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                    })
            return {"success": True, "answer": answer, "sources": sources, "provider": "bailian"}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}", "provider": "bailian"}
    except Exception as e:
        return {"success": False, "error": str(e), "provider": "bailian"}


def _tavily_search(query: str, freshness: int = None, sites: list = None) -> dict:
    """Tavily 搜索"""
    api_key = _get_tavily_key()
    if not api_key:
        return {"success": False, "error": "Tavily密钥未配置", "provider": "tavily"}
    
    endpoint = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": 5,
        "search_depth": "basic",
        "include_answer": True,
    }
    if freshness:
        payload["days"] = min(freshness, 30)
    if sites:
        payload["include_domains"] = sites
    
    try:
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
            answer = raw.get("answer", "")
            sources = []
            for item in raw.get("results", []):
                sources.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", ""),
                })
            return {"success": True, "answer": answer, "sources": sources, "provider": "tavily"}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}", "provider": "tavily"}
    except Exception as e:
        return {"success": False, "error": str(e), "provider": "tavily"}


def _volcengine_search(query: str, count: int = 5, time_range: str = None, auth_level: int = 0) -> dict:
    """火山引擎联网搜索（通过 Search Infinity API）
    
    注意：此接口使用联网搜索专用 API Key（WEB_SEARCH_API_KEY），
    非 Ark API Key（ark-xxx）和 agentplan key（ark-xxx）。
    Key 从联网搜索控制台或 Agent Plan 控制台获取。
    """
    api_key = _get_volcengine_search_key()
    if not api_key:
        return {"success": False, "error": "火山引擎联网搜索密钥未配置（需设置 WEB_SEARCH_API_KEY）", "provider": "volcengine"}
    
    endpoint = "https://open.feedcoopapi.com/search_api/web_search"
    payload = {
        "Query": query,
        "SearchType": "web",
        "Count": count,
        "NeedSummary": True,
    }
    if time_range:
        payload["TimeRange"] = time_range
    if auth_level > 0:
        payload["Filter"] = {"AuthInfoLevel": auth_level}
    
    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "X-Traffic-Tag": "skill_web_search_common",
        }
        req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
            
            # Check for API errors
            error = (raw.get("ResponseMetadata") or {}).get("Error")
            if error:
                code = error.get("Code", "")
                msg = error.get("Message", "")
                return {"success": False, "error": f"[{code}] {msg}", "provider": "volcengine"}
            
            result = raw.get("Result", {})
            answer = ""
            sources = []
            
            # Build answer from summaries
            summaries = []
            for item in result.get("WebResults") or []:
                summary = item.get("Summary") or item.get("Snippet", "")
                if summary:
                    summaries.append(summary)
                sources.append({
                    "title": item.get("Title", ""),
                    "url": item.get("Url", ""),
                    "snippet": (item.get("Summary") or item.get("Snippet", ""))[:300],
                    "site_name": item.get("SiteName", ""),
                    "auth_info": item.get("AuthInfoDes", ""),
                })
            
            answer = "\n\n".join(summaries) if summaries else ""
            return {"success": True, "answer": answer, "sources": sources, "provider": "volcengine"}
    
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        return {"success": False, "error": f"HTTP {e.code}: {body}", "provider": "volcengine"}
    except Exception as e:
        return {"success": False, "error": str(e), "provider": "volcengine"}


# ============================================================================
# 统一接口
# ============================================================================

# 火山引擎时间范围映射
_FRESHNESS_TO_TIMERANGE = {
    7: "OneWeek",
    30: "OneMonth",
    365: "OneYear",
}

def search(query: str, intensity: str = "normal", freshness: int = None, sites: list = None) -> dict:
    """
    联网搜索 - 多服务商并行搜索，合并结果
    
    Args:
        query: 搜索问题
        intensity: 搜索强度 (quick/normal/deep)
        freshness: 时效筛选天数 (7/30/180/365)
        sites: 限定站点列表
    
    Returns:
        {"success": True/False, "answer": "...", "sources": [...]}
    """
    strategy_map = {"quick": "turbo", "normal": "max", "deep": "agent"}
    strategy = strategy_map.get(intensity, "max")
    is_domestic = _is_domestic_query(query, sites)
    
    # 火山引擎 time_range 参数
    time_range = _FRESHNESS_TO_TIMERANGE.get(freshness)
    
    results = []
    if intensity == "quick":
        if is_domestic:
            results = [_volcengine_search(query, count=3, time_range=time_range)]
        else:
            results = [_tavily_search(query, freshness, sites)]
    elif intensity == "normal":
        if is_domestic:
            results = [
                _bailian_search(query, strategy, freshness, sites),
                _volcengine_search(query, count=5, time_range=time_range),
            ]
        else:
            results = [
                _tavily_search(query, freshness, sites),
                _volcengine_search(query, count=5, time_range=time_range),
            ]
    else:  # deep
        results = [
            _bailian_search(query, strategy, freshness, sites),
            _volcengine_search(query, count=10, time_range=time_range),
            _tavily_search(query, freshness, sites),
        ]
    
    return _merge_results(results)


def _is_domestic_query(query: str, sites: list = None) -> bool:
    """判断是否是国内搜索"""
    domestic_keywords = ["中国", "北京", "上海", "政策", "gov.cn", "人民币", "A股", "国内", "天气"]
    overseas_keywords = ["US", "美国", "OpenAI", "Google", "美股", "美元"]
    
    if sites:
        domestic_domains = [".cn", "gov.cn", "edu.cn"]
        if all(any(d in s for d in domestic_domains) for s in sites):
            return True
    
    for kw in overseas_keywords:
        if kw.lower() in query.lower():
            return False
    for kw in domestic_keywords:
        if kw.lower() in query.lower():
            return True
    return True


def _merge_results(results: list) -> dict:
    """合并多个服务商的结果"""
    successful = [r for r in results if r.get("success")]
    alerts = [{"provider": r.get("provider"), "error": r.get("error")} 
              for r in results if not r.get("success") and r.get("error")]
    
    if not successful:
        return {"success": False, "error": results[0].get("error", "无搜索结果"), "alerts": alerts}
    
    answers = [r.get("answer", "") for r in successful if r.get("answer")]
    best_answer = max(answers, key=len) if answers else ""
    
    all_sources = []
    seen_urls = set()
    for r in successful:
        for s in r.get("sources", []):
            url = s.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_sources.append(s)
    
    return {
        "success": True,
        "answer": best_answer,
        "sources": all_sources[:10],
        "provider": [r.get("provider") for r in successful],
        "alerts": alerts,
    }
