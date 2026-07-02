# 免费 AI 资源调研报告

> 调研时间：2026-07-01
> 工具：B站 API 抓取 + GitHub 搜索 + 网页抓取
> 搜索关键词覆盖：免费AI额度、白嫖tokens、免费IDE、免费API、免费大模型

---

## 一、新发现平台（含有效期）

| 平台 | 免费内容 | 有效期/限制 | 类型 | 链接 |
|------|---------|------------|------|------|
| **NVIDIA API** | 6 个月免费使用 200+ 大模型（含 GLM-4.7, MiniMax, Claude 等） | **6个月限时**（需注册） | API | https://build.nvidia.com |
| **Cloudflare Workers 中转** | Cloudflare 免费额度可自建 Gemini/Claude API 中转站 | Cloudflare Workers 免费 tier：10 万请求/天 长期有效 | 中转方案 | Cloudflare dashboard |
| **xAI Grok API** | 每人每月 $25 免费额度 | 当前政策，未注明截止 | API | https://x.ai |
| **Kiro IDE** | 50 credits/月 + Claude Sonnet 4.5；当前有活动可领 $100 Pro Max | Free 层永久；**$100 限时活动** | IDE | https://kiro.dev |
| **火山引擎 API** | 多种模型免费额度（DeepSeek、豆包等） | 不同模型不同期限 | API | https://www.volcengine.com |
| **Windsurf** (Codeium) | 完全免费的 AI 编程 IDE | 当前长期免费（2026-07-01 仍有效） | IDE | https://codeium.com/windsurf |
| **Coze 扣子** | 免费使用 GPT-4 构建 Agent/工作流 | 基础功能免费 | 平台 | https://www.coze.cn |
| **通义灵码 LINGMA** | 免费 AI 编码助手 | 当前长期有效 | IDE | https://lingma.aliyun.com |
| **v0.dev** | 前端生成免费额度 | 每月有限额 | 生成器 | https://v0.dev |
| **GitHub Copilot** | 学生/教师免费 Pro | 需验证，学生身份永久 | IDE | https://education.github.com |

---

## 二、❌ 已过期/取消的活动

| 平台 | 原活动 | 截止日期 | 状态 |
|------|-------|---------|------|
| **OpenCode** | 免费接入 GLM 5.2 | **已取消**（B站 57K 播放视频确认） | 用户已付费 |
| **WorkBuddy** | 2000 积分邀请福利 | **2026-06-30 已过期** | 需更新 |

---

## 三、已收录平台到期倒计时

| 平台 | 截止日期 | 剩余天数 |
|------|---------|---------|
| TRAE AI 创造力大赛 | 2026-07-15 | ⚠️ 14 天 |
| 硅基流动推荐官计划 | 2026-12-31 | 183 天 |
| NVIDIA API 限免 | 注册起 6 个月 | 需注册后计算 |
| 小米 MiMo | 限前 30 人 | 名额未知 |

---

## 四、推荐奖励排行（含有效期）

| 排名 | 平台 | 奖励 | 有效期 |
|------|------|------|--------|
| 1 | **Qoder** | 200 Credits/人，上限 200 人 | 未注明截止 |
| 2 | **WorkBuddy** | 50 积分/人 + 实物奖品 | 6/30 已过期，需确认新政策 |
| 3 | **NVIDIA API** | 免费 6 个月 200+ 模型 | 注册起算 |
| 4 | **Kiro** | 当前活动送 $100 Pro Max | 限时，需快领 |

---

## 五、高播放量 B站视频（可看详情确认）

| 播放 | 内容 | 链接 |
|------|------|------|
| 153K | Cloudflare 中转 Gemini API 免费用 | BV1xS66YAEwm |
| 92K | 手把手教你国内调 Gemini API | BV1YjKWzHExE |
| 57K | OpenCode **取消**免费模型 | BV14B6GBjE53 |
| 49K | NVIDIA API 免费，Claude Code 用 | BV1uRZFBfEnB |
| 28K | 英伟达 API 限免 GLM-4.7/MiniMax | BV1xXkMBMEH5 |
| 18K | NVIDIA API 注册教程 | BV1ntPUzAEob |
| 187K | Qoder 1.0 正式版推倒重做 | BV1uTLA6FEMy |
| 31K | Grok API 每月 $25 免费 | BV1DWU6YbEEG |

---

## 六、下一步行动

1. **紧急** — 更新 TRAE 活动截止日期（7/15 将至）
2. **紧急** — 移除/更新 WorkBuddy（原活动已过期）
3. **新加** — NVIDIA API、Kiro（有活动）、Cloudflare 中转方案
4. **注意** — OpenCode 免费取消，如已收录需移除
5. **更新** — 火山引擎、Coze、Wingsurf 加入列表

---

## 七、验证清单

生成验证文件：`data/platforms-verification.json`（12个新平台，均带 `status: pending_verification`）

### 你需要验证的项目（按优先级）

| 平台 | 验证什么 | 如何验证 |
|------|---------|---------|
| **NVIDIA API** | 注册后能看到 $X 免费额度？6 个月计时开始？ | 注册 https://build.nvidia.com |
| **Kiro** | $100 Pro Max 活动是否还在？免费层 50 credits 能否正常使用 | 登录 https://kiro.dev 看 pricing |
| **Windsurf** | 真的完全免费吗？有没有隐藏限制 | 下载安装 https://codeium.com/windsurf |
| **Grok API** | 每月 $25 政策是否仍有效 | 登录 https://x.ai 控制台 |
| **火山引擎** | 各模型当前免费额度 | 登录 https://www.volcengine.com |
| **Coze** | GPT-4 调用是否仍免费，频率限制 | 注册 https://www.coze.cn |
| **LINGMA** | 是否有邀请奖励政策 | 注册 https://lingma.aliyun.com |
| **v0.dev** | 每月免费生成次数 | 登录 https://v0.dev |
| **Dyad** | 开源项目是否仍维护 | 访问 GitHub 仓库 |
| **GitHub Copilot** | 学生认证流程是否仍开放 | https://education.github.com |
| **Cloudflare** | Workers 免费 tier 是否能跑 AI 中转 | 需技术验证（写个 Worker） |

### 已知过期（从主站验证）

- **WorkBuddy** — 2000 积分 + 实物奖品：6/30 已过期（通过 Playwright 渲染确认）
- **OpenCode** — 免费 GLM 5.2：已取消（B站 57K 播放视频确认）

