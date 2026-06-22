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
import re
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse

# ============================================================================
# 配置管理
# ============================================================================

CONFIG_DIR = Path.home() / ".unified-web-search"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# 平台别名 → 域名（合并进 sites；Volcengine/Tavily/Bailian 按各自能力路由）
_PLATFORM_SITES: Dict[str, List[str]] = {
    "xiaohongshu": ["xiaohongshu.com", "xhslink.com"],
    "xhs": ["xiaohongshu.com", "xhslink.com"],
    "wechat": ["mp.weixin.qq.com"],
    "weixin": ["mp.weixin.qq.com"],
    "weibo": ["weibo.com", "weibo.cn"],
    "zhihu": ["zhihu.com"],
    "bilibili": ["bilibili.com", "b23.tv"],
    "douyin": ["douyin.com"],
    "gov": ["gov.cn"],
    "arxiv": ["arxiv.org"],
}

_FRESHNESS_BUCKETS = (7, 30, 180, 365)

# 纯国内平台别名（命中则不必调 Tavily）
_DOMESTIC_PLATFORM_KEYS = frozenset({
    "xiaohongshu", "xhs", "wechat", "weixin", "weibo", "zhihu", "bilibili", "douyin", "gov",
})

# 火山引擎 time_range 枚举（freshness 天数 → TimeRange；180 天无精确档位，走 OneYear）
_FRESHNESS_TO_TIMERANGE = {
    7: "OneWeek",
    30: "OneMonth",
    180: "OneYear",
    365: "OneYear",
}


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
# 参数解析与后处理
# ============================================================================

def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _freshness_bucket_for_span(span_days: int) -> int:
    for bucket in _FRESHNESS_BUCKETS:
        if span_days <= bucket:
            return bucket
    return 365


def _resolve_time_filters(
    freshness: Optional[int],
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    """统一日期/时效参数 → 各后端可用的规格 + 后处理窗口。"""
    start = _parse_iso_date(start_date)
    end = _parse_iso_date(end_date)
    today = date.today()

    if start and not end:
        end = today
    if end and not start:
        start = end - timedelta(days=6)

    if start and end and start > end:
        start, end = end, start

    effective_freshness = freshness
    if start and end:
        span = (end - start).days + 1
        if effective_freshness is None:
            effective_freshness = _freshness_bucket_for_span(span)

    return {
        "start": start,
        "end": end,
        "freshness": effective_freshness,
        "has_exact_range": bool(start and end),
        "volc_time_range": (
            f"{start.isoformat()}..{end.isoformat()}" if start and end else None
        ),
    }


def _expand_platforms(
    sites: Optional[List[str]], platforms: Optional[List[str]]
) -> Optional[List[str]]:
    merged: List[str] = []
    seen = set()
    for item in sites or []:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(item.strip())
    for platform in platforms or []:
        key = platform.strip().lower()
        for domain in _PLATFORM_SITES.get(key, [platform.strip()]):
            dkey = domain.lower()
            if dkey and dkey not in seen:
                seen.add(dkey)
                merged.append(domain)
    return merged or None


def _sites_pipe(sites: Optional[List[str]]) -> str:
    if not sites:
        return ""
    return "|".join(s.strip() for s in sites if s and str(s).strip())


def _domain_from_url(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _domain_matches_site(host: str, site: str) -> bool:
    site = site.strip().lower().lstrip(".")
    if not site or not host:
        return False
    if site.startswith("*."):
        return host == site[2:] or host.endswith("." + site[2:])
    if site.startswith("."):
        return host.endswith(site) or host == site[1:]
    return host == site or host.endswith("." + site)


def _source_in_sites(source: dict, sites: List[str]) -> bool:
    host = _domain_from_url(source.get("url", ""))
    site_name = (source.get("site_name") or "").lower()
    return any(
        _domain_matches_site(host, s) or s.lower() in site_name for s in sites
    )


def _source_in_exclude(source: dict, exclude_sites: List[str]) -> bool:
    host = _domain_from_url(source.get("url", ""))
    site_name = (source.get("site_name") or "").lower()
    return any(
        _domain_matches_site(host, s) or s.lower() in site_name for s in exclude_sites
    )


def _parse_source_date(source: dict) -> Optional[date]:
    for key in ("published_date", "publish_time", "published"):
        raw = source.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        if not text:
            continue
        # ISO datetime
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            pass
        # YYYY-MM-DD prefix
        m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                pass
    return None


def _post_filter_sources(
    sources: List[dict],
    *,
    start: Optional[date],
    end: Optional[date],
    sites: Optional[List[str]],
    exclude_sites: Optional[List[str]],
    auth_level: int = 0,
) -> List[dict]:
    filtered = []
    for src in sources:
        if sites and not _source_in_sites(src, sites):
            continue
        if exclude_sites and _source_in_exclude(src, exclude_sites):
            continue
        if auth_level > 0:
            level = src.get("auth_info_level")
            if level is not None and int(level) < auth_level:
                continue
        if start and end:
            pub = _parse_source_date(src)
            if pub is not None and (pub < start or pub > end):
                continue
        filtered.append(src)
    return filtered


def _apply_post_filters(result: dict, filters: Dict[str, Any]) -> dict:
    if not result.get("success"):
        return result
    sources = _post_filter_sources(
        list(result.get("sources") or []),
        start=filters.get("start"),
        end=filters.get("end"),
        sites=filters.get("post_filter_sites"),
        exclude_sites=filters.get("post_filter_exclude"),
        auth_level=filters.get("post_filter_auth_level") or 0,
    )
    result = dict(result)
    result["sources"] = sources
    if filters.get("provider_notes"):
        result["filter_notes"] = filters["provider_notes"]
    return result


# ============================================================================
# 搜索实现
# ============================================================================

def _bailian_search(
    query: str,
    strategy: str = "max",
    freshness: int = None,
    sites: list = None,
) -> dict:
    """百炼搜索（阿里云）— 不支持精确日期、exclude_sites、auth_level"""
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


def _tavily_search(
    query: str,
    freshness: int = None,
    sites: list = None,
    exclude_sites: list = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    topic: str = "general",
) -> dict:
    """Tavily 搜索 — 支持精确日期、include/exclude domains、topic"""
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
        "topic": topic if topic in ("general", "news", "finance") else "general",
    }
    if start_date and end_date:
        payload["start_date"] = start_date.isoformat()
        payload["end_date"] = end_date.isoformat()
    elif freshness:
        payload["days"] = min(freshness, 30)
    if sites:
        payload["include_domains"] = sites
    if exclude_sites:
        payload["exclude_domains"] = exclude_sites

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
                    "published_date": item.get("published_date", ""),
                })
            return {"success": True, "answer": answer, "sources": sources, "provider": "tavily"}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}", "provider": "tavily"}
    except Exception as e:
        return {"success": False, "error": str(e), "provider": "tavily"}


def _volcengine_search(
    query: str,
    count: int = 5,
    time_range: str = None,
    auth_level: int = 0,
    sites: list = None,
    exclude_sites: list = None,
) -> dict:
    """火山引擎联网搜索（Search Infinity API）"""
    api_key = _get_volcengine_search_key()
    if not api_key:
        return {
            "success": False,
            "error": "火山引擎联网搜索密钥未配置（需设置 WEB_SEARCH_API_KEY）",
            "provider": "volcengine",
        }

    endpoint = "https://open.feedcoopapi.com/search_api/web_search"
    volc_filter: Dict[str, Any] = {}
    sites_pipe = _sites_pipe(sites)
    block_pipe = _sites_pipe(exclude_sites)
    if sites_pipe:
        volc_filter["Sites"] = sites_pipe
    if block_pipe:
        volc_filter["BlockHosts"] = block_pipe
    if auth_level > 0:
        volc_filter["AuthInfoLevel"] = auth_level

    payload = {
        "Query": query,
        "SearchType": "web",
        "Count": count,
        "NeedSummary": True,
    }
    if time_range:
        payload["TimeRange"] = time_range
    if volc_filter:
        payload["Filter"] = volc_filter

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

            error = (raw.get("ResponseMetadata") or {}).get("Error")
            if error:
                code = error.get("Code", "")
                msg = error.get("Message", "")
                return {"success": False, "error": f"[{code}] {msg}", "provider": "volcengine"}

            result = raw.get("Result", {})
            summaries = []
            sources = []

            for item in result.get("WebResults") or []:
                summary = item.get("Summary") or item.get("Snippet", "")
                if summary:
                    summaries.append(summary)
                publish_time = item.get("PublishTime") or ""
                sources.append({
                    "title": item.get("Title", ""),
                    "url": item.get("Url", ""),
                    "snippet": (item.get("Summary") or item.get("Snippet", ""))[:300],
                    "site_name": item.get("SiteName", ""),
                    "auth_info": item.get("AuthInfoDes", ""),
                    "auth_info_level": item.get("AuthInfoLevel", 0),
                    "publish_time": publish_time,
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


def _volc_time_range_from_filters(time_spec: Dict[str, Any]) -> Optional[str]:
    if time_spec.get("volc_time_range"):
        return time_spec["volc_time_range"]
    freshness = time_spec.get("freshness")
    return _FRESHNESS_TO_TIMERANGE.get(freshness) if freshness else None


def _build_filter_plan(
    time_spec: Dict[str, Any],
    sites: Optional[List[str]],
    exclude_sites: Optional[List[str]],
    auth_level: int,
    topic: str,
) -> Dict[str, Any]:
    """按后端能力决定：原生传参 vs 后处理。"""
    notes = []
    post_sites = None
    post_exclude = None
    post_auth = 0

    # Bailian: no native exclude/date/auth — post-filter when needed
    if exclude_sites:
        post_exclude = exclude_sites
        notes.append("bailian: exclude_sites via post-filter")
    if sites:
        notes.append("bailian: sites via assigned_site_list")
    if time_spec.get("has_exact_range"):
        notes.append("bailian: exact dates via freshness fallback + post-filter")
    if auth_level > 0:
        notes.append("bailian: auth_level not supported natively")

    return {
        "start": time_spec.get("start"),
        "end": time_spec.get("end"),
        "freshness": time_spec.get("freshness"),
        "volc_time_range": _volc_time_range_from_filters(time_spec),
        "sites": sites,
        "exclude_sites": exclude_sites,
        "auth_level": auth_level,
        "topic": topic,
        # Post-filter only where native API didn't apply (per-provider handled in merge)
        "post_filter_sites": post_sites,
        "post_filter_exclude": post_exclude,
        "post_filter_auth_level": post_auth,
        "provider_notes": notes,
    }


def _available_providers() -> List[str]:
    """仅返回已配置密钥的后端，避免无效请求。"""
    out: List[str] = []
    if _get_bailian_key():
        out.append("bailian")
    if _get_tavily_key():
        out.append("tavily")
    if _get_volcengine_search_key():
        out.append("volcengine")
    return out


def _is_domestic_domain(site: str) -> bool:
    s = site.strip().lower()
    markers = (
        ".cn", "gov.cn", "edu.cn", "xiaohongshu.com", "xhslink.com",
        "weibo.com", "weibo.cn", "zhihu.com", "mp.weixin.qq.com",
        "bilibili.com", "douyin.com", "b23.tv",
    )
    return any(m in s for m in markers)


def _is_domestic_only_context(
    merged_sites: Optional[List[str]], platforms: Optional[List[str]]
) -> bool:
    if platforms and all(p.strip().lower() in _DOMESTIC_PLATFORM_KEYS for p in platforms):
        return True
    if merged_sites and all(_is_domestic_domain(s) for s in merged_sites):
        return True
    return False


def _provider_count_for_intensity(intensity: str) -> int:
    return {"quick": 1, "normal": 1, "deep": 2}.get(intensity, 1)


def _select_providers(
    intensity: str,
    is_domestic: bool,
    domestic_only: bool,
    plan: Dict[str, Any],
    available: List[str],
) -> List[str]:
    """
    按强度 / 地域 / 参数能力选后端，控制 API 次数：
    quick/normal → 1 家；deep → 最多 2 家。
    """
    if not available:
        return []

    topic = plan.get("topic", "general")
    auth_level = plan.get("auth_level") or 0
    max_n = _provider_count_for_intensity(intensity)

    # Tavily 独占：海外 + (news/finance topic)
    tavily_exclusive = (
        topic in ("news", "finance")
        and not is_domestic
        and "tavily" in available
    )
    if tavily_exclusive:
        return ["tavily"][:max_n]

    chosen: List[str] = []

    def add(name: str) -> None:
        if name in available and name not in chosen:
            chosen.append(name)

    if is_domestic or domestic_only:
        # 国内：火山优先（sources+摘要+站点/日期/权威）；deep 再补百炼（answer 质量）
        if auth_level > 0:
            add("volcengine")
        else:
            add("volcengine")
            if intensity == "deep":
                add("bailian")
        if not chosen:
            add("bailian")
        if not chosen:
            add("tavily")
    else:
        # 海外：Tavily 单点；deep 不再叠火山（边际低、浪费额度）
        add("tavily")
        if intensity == "deep":
            add("bailian")
        if not chosen:
            add("volcengine")

    return chosen[:max_n]


def _run_provider(
    provider: str,
    query: str,
    *,
    strategy: str,
    plan: Dict[str, Any],
    time_spec: Dict[str, Any],
    merged_sites: Optional[List[str]],
    exclude_sites: Optional[List[str]],
    auth_level: int,
    eff_topic: str,
    intensity: str,
) -> dict:
    eff_freshness = plan.get("freshness")
    volc_tr = plan.get("volc_time_range")
    t_start = time_spec.get("start")
    t_end = time_spec.get("end")
    count = {"quick": 3, "normal": 5, "deep": 10}.get(intensity, 5)

    if provider == "bailian":
        return _bailian_search(query, strategy, eff_freshness, merged_sites)
    if provider == "tavily":
        return _tavily_search(
            query, eff_freshness, merged_sites, exclude_sites,
            t_start, t_end, eff_topic,
        )
    if provider == "volcengine":
        return _volcengine_search(
            query, count=count, time_range=volc_tr,
            auth_level=auth_level, sites=merged_sites, exclude_sites=exclude_sites,
        )
    return {"success": False, "error": f"unknown provider: {provider}", "provider": provider}


def _provider_needs_post_filter(provider: str, plan: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """返回该 provider 结果是否需要额外后处理及过滤条件。"""
    pf: Dict[str, Any] = {}
    needed = False

    if provider == "bailian":
        # sites 已由 assigned_site_list 原生传入，勿重复滤
        if plan.get("exclude_sites"):
            pf["exclude_sites"] = plan["exclude_sites"]
            needed = True
        if plan.get("start") and plan.get("end"):
            pf["start"] = plan["start"]
            pf["end"] = plan["end"]
            needed = True
        if plan.get("auth_level", 0) > 0:
            pf["auth_level"] = plan["auth_level"]
            needed = True
    elif provider == "tavily":
        if plan.get("start") and plan.get("end"):
            pf["start"] = plan["start"]
            pf["end"] = plan["end"]
            needed = True
    elif provider == "volcengine":
        if plan.get("start") and plan.get("end"):
            pf["start"] = plan["start"]
            pf["end"] = plan["end"]
            needed = True

    return needed, pf


# ============================================================================
# 统一接口
# ============================================================================

def search(
    query: str,
    intensity: str = "normal",
    freshness: int = None,
    sites: list = None,
    start_date: str = None,
    end_date: str = None,
    exclude_sites: list = None,
    platforms: list = None,
    auth_level: int = 0,
    topic: str = "general",
) -> dict:
    """
    联网搜索 - 多服务商并行搜索，合并结果

    Args:
        query: 搜索问题
        intensity: 搜索强度 (quick/normal/deep)
        freshness: 时效筛选天数 (7/30/180/365)；与 start_date/end_date 二选一或组合
        sites: 限定站点/域名列表
        start_date: 起始日期 YYYY-MM-DD（与 end_date 搭配精确窗口，如「昨天+今天」）
        end_date: 结束日期 YYYY-MM-DD
        exclude_sites: 排除域名列表（Tavily/火山原生支持；百炼走后处理）
        platforms: 平台别名，如 xiaohongshu/wechat/weibo — 展开为 sites
        auth_level: 权威度 0=默认 1=高权威（仅火山原生；其他忽略）
        topic: Tavily 话题 general/news/finance

    Returns:
        {"success": True/False, "answer": "...", "sources": [...]}
    """
    strategy_map = {"quick": "turbo", "normal": "max", "deep": "agent"}
    strategy = strategy_map.get(intensity, "max")

    merged_sites = _expand_platforms(sites, platforms)
    time_spec = _resolve_time_filters(freshness, start_date, end_date)
    plan = _build_filter_plan(
        time_spec, merged_sites, exclude_sites, auth_level or 0, topic or "general"
    )

    is_domestic = _is_domestic_query(query, merged_sites)
    domestic_only = _is_domestic_only_context(merged_sites, platforms)
    eff_topic = plan.get("topic", "general")
    if eff_topic == "general" and time_spec.get("has_exact_range"):
        t_start = time_spec.get("start")
        t_end = time_spec.get("end")
        span = (t_end - t_start).days + 1 if t_start and t_end else 0
        if span <= 7 and not is_domestic:
            eff_topic = "news"

    available = _available_providers()
    selected = _select_providers(
        intensity, is_domestic, domestic_only, plan, available,
    )
    if not selected:
        return {
            "success": False,
            "error": "无可用搜索密钥（需配置 BAILIAN/TAVILY/WEB_SEARCH_API_KEY 之一）",
            "alerts": [],
        }

    results = [
        _run_provider(
            p, query,
            strategy=strategy,
            plan=plan,
            time_spec=time_spec,
            merged_sites=merged_sites,
            exclude_sites=exclude_sites,
            auth_level=auth_level or 0,
            eff_topic=eff_topic,
            intensity=intensity,
        )
        for p in selected
    ]

    # Per-provider post-filter where native API lacks support
    processed = []
    for r in results:
        provider = r.get("provider", "")
        needed, pf = _provider_needs_post_filter(provider, plan)
        if needed and r.get("success"):
            sources = _post_filter_sources(list(r.get("sources") or []), **pf)
            r = dict(r)
            r["sources"] = sources
        processed.append(r)

    merged = _merge_results(processed)

    meta = {"routing": {"intensity": intensity, "providers": selected, "domestic": is_domestic}}
    if time_spec.get("has_exact_range"):
        meta["date_range"] = {
            "start": time_spec["start"].isoformat(),
            "end": time_spec["end"].isoformat(),
        }
    if merged_sites:
        meta["sites"] = merged_sites
    if exclude_sites:
        meta["exclude_sites"] = exclude_sites
    if platforms:
        meta["platforms"] = platforms
    if meta:
        merged["filters_applied"] = meta

    return merged


def _is_domestic_query(query: str, sites: list = None) -> bool:
    """判断是否是国内搜索"""
    domestic_keywords = ["中国", "北京", "上海", "政策", "gov.cn", "人民币", "A股", "国内", "天气"]
    overseas_keywords = ["US", "美国", "OpenAI", "Google", "美股", "美元"]

    if sites:
        domestic_domains = [".cn", "gov.cn", "edu.cn", "xiaohongshu.com", "weibo.com", "zhihu.com", "mp.weixin.qq.com"]
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
