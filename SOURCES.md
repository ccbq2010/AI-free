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
