# Changelog

## 2.1.0 - 2026-06-22

### Added
- **Date range**: `start_date` / `end_date` (`YYYY-MM-DD`) with post-filter fallback
- **Domain filters**: `exclude_sites`; Volcengine `Filter.Sites` / `BlockHosts`
- **Platform shortcuts**: `platforms` — xiaohongshu, wechat, weibo, zhihu, bilibili, douyin, gov, arxiv
- **Quality / category**: `auth_level` (0/1), `topic` (general/news/finance)

### Changed
- **Routing**: quick/normal → 1 API call; deep → at most 2 providers
- Skip providers without configured API keys
- Domestic platform context avoids unnecessary overseas backends

## 2.0.0

- Multi-provider merge (Bailian / Tavily / Volcengine Search Infinity)
- Volcengine via `open.feedcoopapi.com` + `WEB_SEARCH_API_KEY`
