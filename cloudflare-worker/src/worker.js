/**
 * Cloudflare Workers AI Gateway
 * 国内直连的 AI API 中转服务
 * 支持模式：cf_ai | siliconflow | nous | custom
 * 兼容 OpenAI API 格式
 */

export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const auth = request.headers.get('Authorization') || '';
    if (!auth.startsWith('Bearer ') || auth.slice(7) !== env.API_GATEWAY_KEY) {
      return new Response(
        JSON.stringify({ error: { message: 'Invalid API Key', type: 'auth_error' } }),
        { status: 401, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const url = new URL(request.pathname, 'http://localhost');

    // 模型列表端点
    if (url.pathname === '/v1/models') {
      return listModels(env, corsHeaders);
    }

    // 聊天完成端点
    if (url.pathname === '/v1/chat/completions') {
      switch (env.AI_MODE) {
        case 'cf_ai': return handleCloudflareAI(request, env, corsHeaders);
        case 'siliconflow': return handleSiliconFlow(request, env, corsHeaders);
        case 'nous': return handleNousPortal(request, env, corsHeaders);
        default: return handleGenericProxy(request, env, corsHeaders);
      }
    }

    // 健康检查
    return new Response(
      JSON.stringify({
        status: 'ok',
        mode: env.AI_MODE,
        gateway: 'cf-ai-gateway',
        docs: 'https://github.com/ccbq2010/AI-free'
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
};

async function handleCloudflareAI(request, env, corsHeaders) {
  try {
    const body = await request.json();
    const { model = 'llama', messages, max_tokens } = body;
    const cfModel = model.startsWith('@cf/') ? model : mapToCfModel(model);

    const cfResponse = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CF_ACCOUNT_ID}/ai/run/${cfModel}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.CF_AI_TOKEN || ''}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ messages, max_tokens: max_tokens || 1024 })
      }
    );

    const result = await cfResponse.json();
    if (!result.success) {
      return new Response(
        JSON.stringify({ error: result.errors?.[0]?.message || 'CF AI Error' }),
        { status: 500, headers: corsHeaders }
      );
    }

    const openAiResponse = {
      id: 'cf-' + Date.now(),
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: model,
      choices: [{
        index: 0,
        message: { role: 'assistant', content: result.result?.response || '' },
        finish_reason: 'stop'
      }],
      usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
    };

    return new Response(
      JSON.stringify(openAiResponse),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: e.message }),
      { status: 500, headers: corsHeaders }
    );
  }
}

async function handleSiliconFlow(request, env, corsHeaders) {
  const body = await request.json();
  const sfResponse = await fetch(`${env.SILICONFLOW_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.SILICONFLOW_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: mapToSiliModel(body.model),
      messages: body.messages,
      max_tokens: body.max_tokens || 2048,
      temperature: body.temperature
    })
  });
  const result = await sfResponse.json();
  return new Response(
    JSON.stringify(result),
    { status: sfResponse.status, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
}

async function handleNousPortal(request, env, corsHeaders) {
  const body = await request.json();
  const nousResponse = await fetch(`${env.NOUS_API_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.NOUS_AGENT_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: body.model || 'hermes-4',
      messages: body.messages,
      max_tokens: body.max_tokens || 2048
    })
  });
  const result = await nousResponse.json();
  return new Response(
    JSON.stringify(result),
    { status: nousResponse.status, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
}

async function handleGenericProxy(request, env, corsHeaders) {
  const body = await request.json();
  const targetUrl = env.TARGET_URL || 'https://api.openai.com/v1/chat/completions';
  const response = await fetch(targetUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.TARGET_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  const result = await response.json();
  return new Response(
    JSON.stringify(result),
    { status: response.status, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
}

function listModels(env, corsHeaders) {
  const models = {
    cf_ai: [
      { id: 'llama', name: 'Llama 3.1 8B', provider: 'Meta (via CF)' },
      { id: 'mistral', name: 'Mistral 7B', provider: 'Mistral (via CF)' },
      { id: 'gemma', name: 'Gemma 2B', provider: 'Google (via CF)' },
      { id: 'qwen', name: 'Qwen 1.5', provider: 'Alibaba (via CF)' },
      { id: 'phi', name: 'Phi-2', provider: 'Microsoft (via CF)' },
      { id: 'deepseek', name: 'DeepSeek R1', provider: 'DeepSeek (via CF)' }
    ],
    siliconflow: [
      { id: 'qwen', name: 'Qwen 2.5 7B', provider: 'SiliconFlow' },
      { id: 'deepseek', name: 'DeepSeek V3', provider: 'SiliconFlow' },
      { id: 'glm', name: 'GLM-4 9B', provider: 'SiliconFlow' },
      { id: 'llama', name: 'Llama 3.1 8B', provider: 'SiliconFlow' }
    ],
    nous: [
      { id: 'hermes-4', name: 'Hermes 4', provider: 'Nous Research' },
      { id: 'mimo', name: 'MiMo v2 Pro', provider: 'Xiaomi (via Nous)' }
    ]
  };

  const mode = env.AI_MODE || 'cf_ai';
  const list = models[mode] || models.cf_ai;

  return new Response(
    JSON.stringify({ data: list, object: 'list' }),
    { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
  );
}

function mapToCfModel(name) {
  const map = {
    'llama': '@cf/meta/llama-3.1-8b-instruct',
    'mistral': '@cf/mistral/mistral-7b-instruct-v0.1',
    'gemma': '@cf/google/gemma-2b-it-lora',
    'qwen': '@cf/qwen/qwen1.5-0.5b-chat',
    'phi': '@cf/microsoft/phi-2',
    'deepseek': '@cf/deepseek-ai/deepseek-r1-distill-qwen-32b'
  };
  for (const [k, v] of Object.entries(map)) {
    if (name.toLowerCase().includes(k)) return v;
  }
  return '@cf/meta/llama-3.1-8b-instruct';
}

function mapToSiliModel(name) {
  const map = {
    // 旗舰推理
    'deepseek-v3': 'deepseek-ai/DeepSeek-V3.2',
    'deepseek-v3.1': 'deepseek-ai/DeepSeek-V3.1-Terminus',
    'deepseek': 'deepseek-ai/DeepSeek-V3.2',
    'qwen3.5-35b': 'Qwen/Qwen3.5-35B-A3B',
    'qwen3.5-27b': 'Qwen/Qwen3.5-27B',
    'qwen3.5-9b': 'Qwen/Qwen3.5-9B',
    'qwen3.5': 'Qwen/Qwen3.5-27B',
    // 代码推理
    'deepseek-r1': 'deepseek-ai/DeepSeek-R1',
    'deepseek-v3-old': 'deepseek-ai/DeepSeek-V3',
    'qwen-coder': 'Qwen/Qwen3-Coder-30B-A3B-Instruct',
    'qwen3-30b': 'Qwen/Qwen3-30B-A3B-Instruct-2507',
    // 多模态（视觉语言）
    'qwen-vl-32b': 'Qwen/Qwen3-VL-32B-Instruct',
    'qwen-vl-32b-think': 'Qwen/Qwen3-VL-32B-Thinking',
    'qwen-vl-8b': 'Qwen/Qwen3-VL-8B-Instruct',
    'qwen-vl-8b-think': 'Qwen/Qwen3-VL-8B-Thinking',
    'qwen-vl': 'Qwen/Qwen3-VL-32B-Instruct',
    'qwen-vl-flash': 'Qwen/Qwen3-VL-30B-A3B-Instruct',
    'qwen-vl-flash-think': 'Qwen/Qwen3-VL-30B-A3B-Thinking',
    'qwen-omni': 'Qwen/Qwen3-Omni-30B-A3B-Instruct',
    'qwen-omni-think': 'Qwen/Qwen3-Omni-30B-A3B-Thinking',
    'glm-v': 'zai-org/GLM-4.5V',
    'glm-4.5': 'zai-org/GLM-4.5-Air',
    'glm-4.32b': 'THUDM/GLM-4-32B-0414',
    // 轻量快速
    'ling-flash': 'inclusionAI/Ling-flash-2.0',
    'ling-mini': 'inclusionAI/Ling-mini-2.0',
    'hunyuan': 'tencent/Hunyuan-A13B-Instruct',
    // 图片生成
    'qwen-image': 'Qwen/Qwen-Image',
    'qwen-image-edit': 'Qwen/Qwen-Image-Edit-2509',
    'qwen-image-edit-v1': 'Qwen/Qwen-Image-Edit',
    // 视频生成
    'wan-i2v': 'Wan-AI/Wan2.2-I2V-A14B',
    'wan-t2v': 'Wan-AI/Wan2.2-T2V-A14B',
    // Embedding
    'bge-m3': 'BAAI/bGE-M3',
    'bge-reranker': 'BAAI/bGE-Reranker-v2-m3',
    'qwen-embed-8b': 'Qwen/Qwen3-Embedding-8B',
    'qwen-embed-4b': 'Qwen/Qwen3-Embedding-4B',
    'qwen-embed-0.6b': 'Qwen/Qwen3-Embedding-0.6B',
    'qwen-reranker-8b': 'Qwen/Qwen3-Reranker-8B',
    'qwen-reranker-4b': 'Qwen/Qwen3-Reranker-4B',
    'qwen-reranker-0.6b': 'Qwen/Qwen3-Reranker-0.6B',
    // 兼容旧值
    'llama': 'meta-llama/Meta-Llama-3.1-8B-Instruct',
    'qwen': 'Qwen/Qwen2.5-72B-Instruct',
    'glm': 'THUDM/GLM-4-32B-0414',
    'gemma': 'google/gemma-2-9b-it',
    'mistral': 'mistralai/Mistral-7B-Instruct-v0.3'
  };
  for (const [k, v] of Object.entries(map)) {
    if (name.toLowerCase().includes(k)) return v;
  }
  return 'deepseek-ai/DeepSeek-V3.2';
}
