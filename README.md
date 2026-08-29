# 🎁 AI 新用户福利合集

> 🚀 GLM-5.3 时代（2026-08-14 发布）：智谱新用户礼包 2500 万 Tokens · WorkBuddy Hy4 preview 限免 · TRAE/扣子已并入豆包

---

## 在线查看

- 网页版：https://ccbq2010.github.io/AI-free/
- 分享版（带二维码）：https://ccbq2010.github.io/AI-free/qr.html

## 平台一览

| # | 平台 | 福利 | GLM |
|---|------|------|-----|
| 1 | **智谱 GLM** | 🎁 新用户注册即领 2500 万 Tokens 礼包 · 邀请双方各得 2000 万 | ✅ 5.3 原厂 |
| 2 | **WorkBuddy** | 🎁 注册送 2000 积分 · Hy3 免费至 9/30 · Hy4 preview 限免（邀请活动 8/31 截止） | ✅ |
| 3 | **TRAE（豆包旗下）** | 🎁 新用户 14 天 Pro 免费 · 免费版每月 500 积分 | ✅ |
| 4 | **NVIDIA API** | 🎁 注册即用 · 200+ 模型速率限制内基本免费 | |
| 5 | **Kiro IDE** | 🎁 50 credits/月 · Claude 系列模型 | |
| 6 | **小米 MiMo** | 🎁 注册即得 ¥10 API 体验金 · 邀请双方各 ¥10（长期） | |
| 7 | **ZCode（智谱）** | 🎁 免费用 5 天 × 每天 800 万 GLM Tokens · 不定期全员活动（周末曾送 3 亿） | ✅ 5.3 |
| 8 | **硅基流动** | 🎁 实名领 ¥16 代金券 + 注册 ¥14 免费额度 · 邀请双方各 ¥16 | ✅ |
| 9 | **GitHub Copilot** | 🎁 学生/教师免费 Pro · 支持 Cloudflare 中转 | |
| 10 | **火山引擎 API** | 🎁 方舟每日单模型最高 500 万免费 Tokens | |
| 11 | **OpenCode** | 🔥 开源免费终端（免费模型已缩水 · Go $10/月 可用 GLM-5.3-Flash） | ✅ |
| 12 | **OpenRouter** | 🎁 一个 API 免费调用约 20 个模型（含 GLM-5.2） | ✅ |
| 13 | **豆包学生优惠** | 🎁 学生认证 2.5 倍免费额度 + 专业版 ¥38/月 | |
| 14 | **Groq** | 🎁 注册免费额度 · 超高速 LPU 推理 | |

## 推荐奖励

详见 [REFERRALS.md](./REFERRALS.md)，包含各平台邀请码和收益详情（2026-08-29 已核验更新）。

## 数据来源

详见 [SOURCES.md](./SOURCES.md)，记录了可自动抓取的信息源和监控策略。

## 目录结构

```
.
├── data/
│   ├── platforms-v2.json           ← 线上构建源（build.yml 使用 --source v2）
│   ├── platforms.json              ← v1 遗留（与 v2 保持同步）
│   ├── platforms-verification.json ← 待验证候选
│   └── review_blacklist.json       ← 已拒绝候选
├── templates/
│   ├── index.html                  ← 主页面模板（含隐藏大额专区）
│   └── qr.html                     ← 二维码分享页模板
├── scripts/
│   ├── build.py                    ← 一键构建生成全部产物
│   ├── v2/                         ← v2 自动发现管线（巡查/LLM 抽取/自动 PR/过期检测）
│   ├── check_sources.py            ← v1 巡查脚本（遗留）
│   ├── check_expiry.py             ← 过期检测脚本
│   ├── extract_with_llm.py         ← LLM 辅助结构化抽取
│   └── fetchers/                   ← 信息源抓取器模块
├── api.json                        ← 公开 JSON API（纯净 URL，无 UTM）
├── feed.xml                        ← RSS 2.0 订阅源
├── cloudflare-worker/              ← 国内访问中转
├── .github/workflows/
│   ├── build.yml                   ← 每日 08:00 (CST) 自动构建部署（--source v2）
│   ├── check-sources-v2.yml        ← 每日 10:00 (CST) 新平台巡查 → 自动 PR
│   ├── check-expiry.yml            ← 每周一过期检测
│   └── check-sources.yml           ← 每周四 v1 巡查（遗留）
└── requirements.txt                ← Python 依赖
```

## 如何添加新平台

1. 编辑 `data/platforms-v2.json`（线上构建源），在数组中追加一个新对象：
   ```json
   {
     "id": "platform-id",
     "name": "平台名",
     "provider": "厂商 · 一句话介绍",
     "benefit": "福利描述文字",
     "benefit_highlight": ["需要高亮的关键词数组"],
     "url": "https://注册链接",
     "tags": ["GLM-5.3"],
     "deadline": "2026-12-31",
     "referral": { "type": "invite_code", "code": "xxx" },
     "status": "active"
   }
   ```
2. 运行 `python build.py --source v2` 重新生成 HTML
3. 推送 / 提 PR（如需保留 v1，请同步修改 `data/platforms.json`）

## 自动化

- **每日 08:00 (CST) 自动重建**: `build.yml` 以 v2 数据源重建并部署，日期/状态/文案自动更新
- **每日 10:00 (CST) v2 巡查**: `check-sources-v2.yml` 扫描信息源 → LLM 结构化抽取 → 自动提 PR
- **每周一过期检测**: `check-expiry.yml` 对每个 URL 做 HEAD + 内容检查，标记可能过期平台
- **每周四 v1 巡查（遗留）**: `check-sources.py` 对比 GitHub 聚合仓库，发现新候选自动创建 Issue

## 贡献

欢迎 PR 补充或通过 [Issues](https://github.com/ccbq2010/AI-free/issues) 反馈。
