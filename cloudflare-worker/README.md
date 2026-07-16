# Cloudflare Workers AI Gateway

> 🇨🇳 国内直连 · 零成本部署 · 兼容 OpenAI API 格式

基于 Cloudflare Workers 的 AI API 中转服务。通过 `*.workers.dev` 域名在国内直接访问，无需代理即可调用各类大模型。

## 为什么需要这个？

| 问题 | 解决方案 |
|------|---------|
| 海外 API (OpenAI/Claude/Gemini) 国内被墙 | 通过 `*.workers.dev` 域名中转，国内可直接访问 |
| 服务器成本高 | Cloudflare Workers 免费 tier = **10 万次请求/天** |
| 模型选择少 | 支持 4 种模式，覆盖国内外 15+ 模型 |

## 支持的模型

### 模式 1：Cloudflare Workers AI（默认）
| 模型 | 说明 |
|------|------|
| Llama 3.1 8B | Meta 开源，综合能力强 |
| Mistral 7B | 欧洲开源，代码生成优秀 |
| Gemma 2B | Google 开源，轻量快速 |
| Qwen 1.5 | 阿里开源，中文能力强 |
| Phi-2 | 微软开源，推理能力强 |
| DeepSeek R1 | 深度求索，推理模型 |

**免费额度**：每天 10,000 Neurons

### 模式 2：SiliconFlow 硅基流动
| 模型 | 说明 |
|------|------|
| Qwen 2.5 7B | 阿里最新开源 |
| DeepSeek V3 | 深度求索最新 |
| GLM-4 9B | 智谱开源 |
| Llama 3.1 8B | Meta |

### 模式 3：Nous Research Portal
| 模型 | 说明 |
|------|------|
| Hermes 4 | Nous 旗舰推理模型 |
| MiMo v2 Pro | 小米开源，Nous 托管 |

### 模式 4：通用代理（OpenAI 格式）
可代理任意 OpenAI 兼容的 API 端点。

## 快速部署

### 前置条件
- 一个 Cloudflare 账号（免费）
- 安装了 Node.js 和 npm

### 部署步骤

```bash
# 1. 克隆并进入目录
cd cloudflare-worker

# 2. 安装 Wrangler CLI
npm install -g wrangler

# 3. 登录 Cloudflare
wrangler login

# 4. 获取 Account ID
# 访问 https://dash.cloudflare.com -> 右侧栏 Account ID

# 5. 修改 wrangler.toml 中的 account_id
# 或通过环境变量: export CF_ACCOUNT_ID=xxx

# 6. 设置安全密钥（切勿把密钥写进 wrangler.toml，该文件已公开）
wrangler secret put API_GATEWAY_KEY      # 网关访问密钥（客户端调用时携带，任意字符串）
wrangler secret put SILICONFLOW_API_KEY  # SiliconFlow API Key（siliconflow 模式必填）

# 7. 部署
wrangler publish
```

### 部署后会得到
```
https://cf-ai-gateway.your-subdomain.workers.dev
```

## 使用方法

### 方式 1：OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://cf-ai-gateway.your-subdomain.workers.dev/v1",
    api_key="sk-cf-gateway-change-me"  # 你设置的 API_GATEWAY_KEY
)

response = client.chat.completions.create(
    model="llama",  # 或 qwen, mistral, deepseek 等
    messages=[{"role": "user", "content": "你好！"}]
)
print(response.choices[0].message.content)
```

### 方式 2：curl
```bash
curl https://cf-ai-gateway.your-subdomain.workers.dev/v1/chat/completions \
  -H "Authorization: Bearer sk-cf-gateway-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 方式 3：其他工具兼容
任何支持自定义 OpenAI API 的工具都可以接入：
- **沉浸式翻译**：设置 base URL 为你的 workers.dev 域名
- **ChatBox / NextChat**：选择 OpenAI 兼容，填入自定义端点
- **Cursor / Windsurf**：通过环境变量 `OPENAI_BASE_URL` 指向你的 Workers

## 配置环境变量

```bash
# 默认模式（必填）
wrangler secret put AI_MODE  # cf_ai | siliconflow | nous | custom

# Cloudflare AI 模式
wrangler secret put CF_AI_TOKEN  # Cloudflare AI API Token

# SiliconFlow 模式
wrangler secret put SILICONFLOW_API_KEY  # SiliconFlow 的 API Key

# Nous Portal 模式
wrangler secret put NOUS_AGENT_KEY  # Nous Portal 的 Agent Key

# 通用代理模式
wrangler secret put TARGET_URL  # 目标 API URL，如 https://api.openai.com/v1/chat/completions
wrangler secret put TARGET_API_KEY  # 目标 API 的 Key
```

## 自定义域名（推荐）

`*.workers.dev` 域名的国内访问速度可能不够理想。建议绑定自己的域名：

1. 在 Cloudflare 添加域名
2. 修改 `wrangler.toml` 中的 route:
```toml
routes = [
  { pattern = "ai-gate.yourdomain.com/*", zone_name = "yourdomain.com" }
]
```
3. 重新 `wrangler publish`

绑定国内 DNS 托管的域名后，访问速度会显著提升。

## 费用

| 层级 | 请求量 | 费用 |
|------|--------|------|
| Workers 免费版 | 100,000 请求/天 | 免费 |
| Workers 付费版 | 1000 万次/月 | $5/月 |
| Cloudflare AI | 每天 10,000 Neurons | 免费 |
| SiliconFlow | 各模型不同 | 有免费额度 |

**个人使用**：Workers 免费版 + Cloudflare AI 模式 = 完全免费

## 故障排查

```bash
# 查看实时日志
wrangler tail

# 本地开发测试
wrangler dev

# 检查环境变量
wrangler secret list
```

## License

MIT
