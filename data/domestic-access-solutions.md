# 国内访问 AI 服务的解决方案

> 检测到 GitHub 访问超时 + 多个海外 AI 网络受限的目标
> 生成时间：2026-07-01

---

## 一、国内直接可达的平台（无需代理）

### 无需代理即可访问
| 平台 | 可访问性 | 备注 |
|------|---------|------|
| 硅基流动 SiliconFlow | ✅ 畅通 | 已收录 |
| Coze 扣子 | ✅ 畅通 | 已收录 |
| 火山引擎 | ✅ 畅通 | 需补充 |
| 智谱 GLM | ✅ 畅通 | 已收录 |
| Qoder | ✅ 畅通 | 已收录 |
| 通义灵码 LINGMA | ✅ 畅通 | 已收录 |
| TRAE | ✅ 畅通 | 已收录 |
| ZCode (中信) | ✅ 畅通 | 已收录 |
| WorkBuddy (腾讯) | ✅ 畅通 | 已收录 |
| 小米 MiMo / MiMO CODE | ✅ 畅通 | 已收录 |
| NVIDIA API | ✅ 畅通 | 需补充 |
| Kiro IDE | ✅ 畅通 | 需补充 |

### 已知被墙/超时
| 平台 | 现象 | 解决方案 |
|------|------|---------|
| GitHub (raw) | 超时 | ghproxy.net / gitclone.com |
| GitHub (主站) | 403/超时 | ghproxy.net / gitclone.com |
| x.ai (Grok) | 无法直连 | Cloudflare Workers 中转 |
| v0.dev | 预计被墙 | Cloudflare Workers 中转 |
| Windsurf 下载 | 可能受阻 | 需验证 |

---

## 二、Cloudflare 生态解决方案（重点）

### Cloudflare AI Gateway
- **网址**: https://gateway.ai.cloudflare.com
- **免费 tier**: 每月 1000 万次请求（不限模型）
- **用途**: 将 OpenAI/Claude/Gemini 请求通过 CF 代理发出，国内访问 CF 域名通畅
- **优势**: 统一端点、缓存、限速、分析
- **代码示例**: 将 api.openai.com 替换为 gateway.ai.cloudflare.com/v1/{account-id}

### Cloudflare Workers AI (Workers AI)
- **免费 tier**: 每天 10,000 neurons
- **内置模型**: Llama 3.2、Mistral、Gemma 2、Phi-3、Qwen 1.5 等开源模型
- **国内可访问**: workers.dev 域名国内直连
- **部署**: 将 AI 推理任务放在边缘节点

### Cloudflare Workers 反向代理
- **热门开源项目**:
  - [QImageLab/cf-proxy](https://github.com/QImageLab/cf-proxy) ★147 — 零配置，一键代理 OpenAI/Claude/Gemini
  - [tingxifa/claude_proxy](https://github.com/tingxifa/claude_proxy) ★214 — Claude ↔ OpenAI 格式互转
- **搭建流程**:
  1. Fork 项目 → 部署到 Cloudflare Workers
  2. 绑定自定义域名（或使用 workers.dev 子域名）
  3. 请求发往 `https://your-worker.workers.dev/v1/chat/completions`
  4. Worker 转发到真实 API（OpenAI/Claude/Gemini）
- **费用**: Workers 免费 tier = 10 万请求/天，够个人使用
- **优势**: workers.dev 域名在国内可访问（Cloudflare 三网优化）

---

## 三、GitHub 访问方案

### ghproxy.net
```
# 下载 release
https://ghproxy.net/https://github.com/owner/repo/releases/download/v1.0/file.zip

# 克隆仓库
git clone https://ghproxy.net/https://github.com/owner/repo.git
```

### gitclone.com
```
git clone https://gitclone.com/github.com/owner/repo.git
```

### 其他镜像
- https://hub.fastgit.xyz (已停服)
- https://gh.api.99988866.xyz
- https://github.moeyy.xyz

---

## 四、推荐策略

### 对普通用户
1. **优先使用国内平台** — 已有 8 个国内平台在使用
2. **NVIDIA API / Kiro** — 国内可直接访问，优先推荐
3. **Cloudflare Workers 中转** — 教用户自建中转站，成本为零

### 对你的 AI-free 项目
1. **分类平台** — 在 platforms.json 增加 `access` 字段: "domestic" | "international" | "cf-proxy"
2. **优先收录** 国内 + Cloudflare 可达的平台
3. **附加部署教程** — 为被墙平台提供 Cloudflare Workers 部署指南
4. **自动检测** — 在 `check_sources.py` 中加入国内可达性检测

### 对你自己的开发
- 使用 ghproxy.net / gitclone.com 拉 GitHub 仓库
- 配置 Cloudflare Workers AI 中转来调 Claude/OpenAI
- 或者继续用硅基流动做中转

---

## 五、国内可达性自动检测

```bash
# 测试某个域名是否能从国内访问
curl -s --connect-timeout 5 -o /dev/null -w "%{http_code}" https://example.com

# 或使用 last30days-cn 的 diagnose 命令
python scripts/last30days.py --diagnose
```

