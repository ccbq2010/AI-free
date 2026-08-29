# 免费 AI 资源信息来源

## 一级来源（可直接自动化抓取）

### GitHub 聚合仓库

| 仓库 | 内容 | 抓取方式 |
|------|------|----------|
| [xx025/carrot](https://github.com/xx025/carrot) | 收录免费 AI 工具，列出免费额度详情 | GitHub API 或 raw README |
| [awesome-free-ai](https://github.com/ai-zerol/free-ai) | 免费 LLM API 和工具 | GitHub API |

### 官方/产品信息

| 来源 | 内容 | 抓取方式 |
|------|------|----------|
| OpenRouter | API 提供商定价/免费模型 | 官方 API |
| Product Hunt | 新 AI 工具发布的免费额度促销 | Product Hunt API |
| Hacker News | AI 工具和优惠讨论 | HN Algolia API |

## 二级来源（需要人工筛选或半自动化）

### 中文社区

| 来源 | 说明 |
|------|------|
| V2EX 创造发现 / 程序员节点 | 不定期有"XXX平台注册送XXX额度"帖子 |
| 少数派 sspai | AI 工具评测，常带促销信息 |
| 微信公众号：AI 产品黄Feed、量子位、机器之心 | 平台动态和福利公告 |
| Hao.AI / 大作 | 国内 AI 工具导航 |
| 即刻 App AI 圈子 | KOL 分享最新免费额度 |
| 小红书 / 抖音搜索"免费AI额度" | 实时营销活动 |

### 海外社区

| 来源 | 说明 |
|------|------|
| Reddit r/LocalLLaMA | Free credit posts |
| Twitter/X (搜索 "free AI credits") | 各平台官方促销推文 |
| Discord 各 AI 社区 | announcements 频道 |

## 自动化方案

1. **GitHub Actions 每天运行** `check_sources.py` 检查固定源
2. **Product Hunt API** 检查新发布的 AI 工具（需申请 API key）
3. **Issue 驱动**：发现新平台 → 自动创建 Issue → 人工确认后合并 PR
4. **邮件监控**（可选）：对关注平台的官方促销邮件设置关键词提醒指纹

## 监控脚本现状

- `scripts/check_sources.py` 每周四运行，检查 GitHub 聚合仓库并对比现有 platform ids
- 发现新候选 → 创建 GitHub Issue

## v2 自动化通道（2026-08 新增）

针对「老产品改福利政策」和「社交平台才能拿到的信息」两类盲区，v2 管线新增三个通道：

### 1. 搜索引擎发现源（`v2/fetchers/search_engine.py`）

小红书/公众号/即刻的羊毛帖会被搜索引擎索引——本源对发现型关键词
（"AI 平台 新用户 注册送 token 免费额度"等）定期跑搜索，把聚合文章
捞回来交给 LLM 抽取官方 URL 和福利。

- 后端链：Serper（可选付费，`SERPER_API_KEY`）→ DuckDuckGo → SearXNG 公共实例 → Bing 兜底
- 实测：DDG 对发现型查询召回最好；Bing 反爬时会返回与查询无关的固定结果，由宽网过滤拦截
- 抽取出的是内容平台文章链接时，`auto_pr_v2` 的 `ARTICLE_DOMAINS` 兜底拦截，防止文章页混进平台数据

### 2. 微信公众号 RSS 桥（`v2/fetchers/wechat_rss.py`）

微信没有公开 API，经由社区桥接服务转成标准 RSS 后订阅**平台官方号**
（智谱 AI、腾讯 CodeBuddy、硅基流动、火山引擎等），活动公告第一时间可得。

- 配置：`data/wechat_rss.json` 的 `feeds` 数组
- 生成订阅：wechat2rss.xlab.app → 搜索公众号 → 生成 RSS → 填入 feed 地址
- 未配置时自动跳过，不影响其余管线

### 3. 官方活动页 diff 监控（`scripts/v2/check_promo_pages.py`）

最可靠的政策变更感知：直接 diff 官方活动/定价页（智谱上新活动、
ZCode changelog、硅基流动动态、TRAE/Kiro 定价等）。内容变化 →
自动创建 Issue。快照存于 `data/promo_snapshots.json` 并随 workflow 提交。

