# 🎁 AI 新用户福利合集

> GLM · TRAE · QoderWork · 硅基流动 · NVIDIA API 均已支持 GLM-5.2 旗舰模型

---

## 在线查看

- 网页版：https://ccbq2010.github.io/AI-free/
- 分享版（带二维码）：https://ccbq2010.github.io/AI-free/qr.html

## 平台一览

| # | 平台 | 福利 | GLM-5.2 |
|---|------|------|---------|
| 1 | **智谱 GLM** | 🎁 新用户注册即送 2000 万 Tokens 大礼包 | ✅ 原厂 |
| 2 | **TRAE** | 🎁 免费模型可长期使用 · 报名领 ¥99 速通 Pro 月卡 | ✅ |
| 3 | **QoderWork CN** | 🎁 首月 Pro 免费（2000 Credits） · 邀请1人得 200 Credits | ✅ |
| 4 | **NVIDIA API** | 🎁 注册即送 6 个月免费额度，涵盖 200+ 模型 | ✅ |
| 5 | **Kiro IDE** | 🎁 50 credits/月 + Claude Sonnet 4.5 · 活动送 $100 Pro Max | |
| 6 | **Coze 扣子** | 🎁 免费使用 GPT-4 / Claude 构建智能体和工作流 | |
| 7 | **小米 MiMo** | 🎁 双方各得 ¥10 API 体验金 + 首单 9 折 | |
| 8 | **MiMO CODE** | 🔥 完全免费使用 · 直接安装 | |
| 9 | **硅基流动** | 🎁 注册+实名认证领 ¥16 代金券（约 2000 万 Token） | ✅ |
| 10 | **GitHub Copilot** | 🎁 学生/教师免费 Pro · 支持 Cloudflare 中转 | |
| 11 | **Dyad** | 🔥 开源免费 · Lovable/Bolt.new 替代品 | |
| 12 | **火山引擎 API** | 🎁 DeepSeek/豆包免费 + Seedance 90秒/天 | |
| 13 | **WorkBuddy** | 🎁 注册送 2000 积分（邀请链接）· 邀请人 50+100+500 积分 · 8/31 截止 | ✅ |

## 推荐奖励

详见 [REFERRALS.md](./REFERRALS.md)，包含各平台邀请码和收益详情。

## 数据来源

详见 [SOURCES.md](./SOURCES.md)，记录了可自动抓取的信息源和监控策略。

## 目录结构

```
.
├── data/
│   ├── platforms.json      ← 编辑此文件添加/修改平台（tier=hidden_gem 显示在顶部专区）
│   ├── platforms-verification.json  ← 待验证候选
│   └── review_blacklist.json        ← 已拒绝候选
├── templates/
│   ├── index.html          ← 主页面模板（含隐藏大额专区）
│   └── qr.html             ← 二维码分享页模板
├── scripts/
│   ├── build.py            ← 一键构建生成全部产物
│   ├── check_sources.py    ← 多源巡查脚本
│   ├── check_expiry.py     ← 过期检测脚本
│   ├── extract_with_llm.py ← LLM 辅助结构化抽取
│   └── fetchers/           ← 信息源抓取器模块
├── api.json                ← 公开 JSON API（纯净 URL，无 UTM）
├── feed.xml                ← RSS 2.0 订阅源
├── cloudflare-worker/      ← 国内访问中转
├── .github/workflows/
│   ├── build.yml           ← 每周一自动构建部署
│   ├── check-sources.yml   ← 每周四自动巡查新平台
│   └── check-expiry.yml    ← 每周一过期检测
└── requirements.txt        ← Python 依赖
```

## 如何添加新平台

1. 编辑 `data/platforms.json`，在数组中追加一个新对象：
   ```json
   {
     "id": "platform-id",
     "name": "平台名",
     "provider": "厂商 · 一句话介绍",
     "benefit": "福利描述文字",
     "benefit_highlight": ["需要高亮的关键词数组"],
     "url": "https://注册链接",
     "tags": ["GLM-5.2"],
     "deadline": "2026-12-31",
     "referral": { "type": "invite_code", "code": "xxx" },
     "status": "active"
   }
   ```
2. 运行 `python build.py` 重新生成 HTML
3. 推送 / 提 PR

## 自动化

- **每周一 08:00 自动重建**: 确保日期/状态/文案更新
- **每周四 10:00 巡查新源**: 6 个信息源（GitHub 聚合仓库、HackerNews、OpenRouter、RSS、中文媒体、GitHub API）扫描候选，创建 Issue
- **过期检测**: `check_expiry.py` 对每个 URL 做 HEAD + 内容检查，标记可能过期平台

## 贡献

欢迎 PR 补充或通过 [Issues](https://github.com/ccbq2010/AI-free/issues) 反馈。
