# DeepSeek API 配置指南

> 面向本项目（RAG 知识库 + 智慧问数）的 DeepSeek 接入说明。
> 读完你会知道该填什么、为什么这么填、以及哪几个地方一填就错。

---

## 一、先说结论：一个必须知道的前提

**DeepSeek 官方 API 只提供对话（chat）接口，不提供向量化（embedding）接口。**

这意味着你**不能**只把 `OPENAI_BASE_URL` 改成 DeepSeek 就完事。本项目里 RAG 的文档入库和检索强依赖 embedding，如果向量化请求打到 DeepSeek，会直接返回 `404 Not Found`——而且这个错误要等你上传第一份文档时才暴露，很容易浪费半天排查。

所以正确的配法是**两套配置分开填**：

| 用途 | 服务商 | 配置前缀 |
|---|---|---|
| 对话推理（RAG 生成、问数解析、SQL 编译） | DeepSeek | `DEEPSEEK_*` |
| 向量化（文档入库、语义检索） | 另选一家 | `EMBEDDING_*` |

代码层面已经做了解耦：`app/llm/base.py` 里 chat provider 和 embedding provider 各自独立解析配置，embedding 不会继承 chat 的 `base_url`。

---

## 二、对话模型配置（DeepSeek）

DeepSeek 完全兼容 OpenAI 协议，项目直接复用 `ChatOpenAI` 客户端，无需额外 SDK。

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_LIGHT_MODEL=deepseek-chat
```

密钥在 [platform.deepseek.com](https://platform.deepseek.com/) 的 API Keys 页面创建。

### base_url 带不带 `/v1`？

两种写法官方都接受（`https://api.deepseek.com` 和 `https://api.deepseek.com/v1` 等价）。**但本项目请统一写带 `/v1` 的版本**——LangChain 的 `ChatOpenAI` 会在 base_url 后拼接 `/chat/completions`，不带 `/v1` 在某些版本下会拼出错误路径。

### 两个模型怎么选

| 模型 | 特点 | 本项目建议 |
|---|---|---|
| `deepseek-chat` | V3 系列，响应快，支持 temperature / JSON 模式 | **默认全流程用它** |
| `deepseek-reasoner` | R1 系列，先输出思维链再给答案 | 谨慎使用，见下 |

`deepseek-reasoner` 在本项目里有三个明确的坑：

1. **首字延迟高**。它要先生成一大段推理过程。RAG 对话是流式输出的，用户会盯着空白屏幕等好几秒，体验直接崩坏。README 里定的性能目标是首字延迟 < 1.5s，reasoner 基本达不到。
2. **忽略采样参数**。`temperature` / `top_p` 传了不生效。项目里多处依赖 `temperature=0.1` 来保证 SQL 生成的稳定性，换成 reasoner 后输出会变得不可控。代码里已经对这类模型做了参数剥离处理，避免部分代理网关直接报 400。
3. **成本更高**，且思维链 token 也计费。

真要用，只建议单独给 `sql_compile` 这一个节点用——多表 join 的复杂查询确实能提升准确率。改法是在 `app/graph/nodes/query/sql_compile.py` 里把 `get_llm()` 换成 `get_llm(model="deepseek-reasoner")`，其他节点保持 `deepseek-chat`。

### 关于 JSON 输出

问数链路的 `nl_understand`（自然语言 → 结构化意图）和 `sql_compile` 节点依赖模型输出合法 JSON。DeepSeek 支持 `response_format={"type":"json_object"}`，项目已封装为 `get_llm(json_mode=True)`。

有个官方限制要注意：**开启 JSON 模式时，提示词里必须出现 "json" 这个词**，否则 DeepSeek 会拒绝请求。项目现有提示词已满足，你自己改提示词时留意别把它删掉。

---

## 三、Embedding 配置（四选一）

### ⚠️ 动手前先记住：维度是硬约束

`EMBEDDING_DIMENSIONS` 必须等于所选模型的真实输出维度。而且——

**Qdrant 的 collection 在创建时就锁定了维度，之后不能改。** 如果你先用 1536 维建了库，后来改成 1024 维，写入会直接报 `vector dimension error`。此时唯一的办法是删除 collection 并**重新向量化全部文档**。

所以：**在导入任何文档之前就把 embedding 模型定下来。**

---

### 方案 A：硅基流动 SiliconFlow（推荐）

国内直连不用代理，有免费额度，OpenAI 协议兼容，中文效果好。

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_KEY=sk-你的硅基流动密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
```

注意最后一行。`dimensions` 是 OpenAI text-embedding-3 系列特有的参数，BGE 模型不认，传过去会 400。项目为此加了 `EMBEDDING_SEND_DIMENSIONS` 开关，**用 BGE 系列时必须设为 `false`**。

BGE-m3 的另一个好处是同时支持中英文和长文本（8192 tokens），适合企业文档场景。

---

### 方案 B：阿里云百炼 DashScope

有企业采购渠道或已在用阿里云的话选它，走兼容模式端点。

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_API_KEY=sk-你的百炼密钥
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=true
```

`text-embedding-v3` 支持指定维度（1024 / 768 / 512），所以这里可以开着。

---

### 方案 C：本地 Ollama（完全离线、零成本）

内网部署或对数据外发敏感时用这个。文档内容不出本机。

```bash
# 先拉模型
ollama pull bge-m3
```

```bash
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
```

代价是向量化速度取决于本机硬件。纯 CPU 跑 bge-m3，几百页的 PDF 入库可能要几分钟。批量导入前建议先测一下吞吐。

依赖已加入 `requirements.txt`（`langchain-ollama`）。

---

### 方案 D：OpenAI 原生

能稳定访问 OpenAI 的话，效果最稳但要额外一份海外账号。

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_API_KEY=sk-你的openai密钥
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_DIMENSIONS=1536
EMBEDDING_SEND_DIMENSIONS=true
```

---

### 维度速查表

| 模型 | 维度 | `SEND_DIMENSIONS` |
|---|---|---|
| `BAAI/bge-m3` | 1024 | `false` |
| `BAAI/bge-large-zh-v1.5` | 1024 | `false` |
| `text-embedding-v3`（百炼） | 1024 | `true` |
| `text-embedding-3-small` | 1536 | `true` |
| `text-embedding-3-large` | 3072 | `true` |
| `nomic-embed-text`（Ollama） | 768 | `false` |

---

## 四、完整 .env 参考（DeepSeek + 硅基流动）

这是最省事的组合，两个 Key 都能在国内直接申请。

```bash
# ── 应用 ──
APP_ENV=development
DEBUG=true
SECRET_KEY=换成随机32字节
ENCRYPTION_KEY=换成随机32字节

# ── 存储 ──
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rag_smart_query
REDIS_URL=redis://localhost:6379/0
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_PREFIX=kb_

# ── 对话模型：DeepSeek ──
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的deepseek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_LIGHT_MODEL=deepseek-chat

# ── 向量化：硅基流动 ──
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_KEY=sk-你的硅基流动密钥
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
EMBEDDING_BATCH_SIZE=32
```

---

## 五、配置完先自检

别急着启动服务。跑自检脚本，它会一次性验证配置自洽性、对话连通性、JSON 输出能力、向量化连通性和维度匹配：

```bash
cd backend
python -m scripts.check_llm
```

正常输出：

```
✓ 配置自洽
✓ 调用成功，返回: '正常'
✓ JSON 解析成功: {'status': 'ok'}
✓ 调用成功，实际返回维度 = 1024
✓ 维度与配置一致
✓ 全部通过，可以启动服务
```

任何一项失败，脚本会直接打印对应的修复建议，不用去翻堆栈。

此外，服务启动时 `app/main.py` 也会调用 `validate_llm_config()` 做一次静态检查，配置明显矛盾（比如 embedding 指向了 DeepSeek）会在启动日志里打警告。

---

## 六、Docker 部署

`docker-compose.yml` 已透传相关变量，在项目根目录建一个 `.env`：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
SECRET_KEY=xxx
ENCRYPTION_KEY=xxx
```

然后 `docker compose up -d`。

注意这个 `.env` 在项目根目录（compose 读），和 `backend/.env`（本地开发时 pydantic-settings 读）是两个文件，别搞混。

---

## 七、常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 对话 `401 Authentication Fails` | Key 错 / 失效 | 重新生成 Key，注意别把 embedding 的 Key 填到 `DEEPSEEK_API_KEY` |
| 对话 `402 Insufficient Balance` | DeepSeek 余额不足 | 充值 |
| 对话 `Model Not Exist` | 模型名拼错 | 只有 `deepseek-chat` / `deepseek-reasoner` |
| **上传文档时 `404 Not Found`** | **embedding 打到了 DeepSeek** | **按第三节配独立 embedding** |
| embedding `400 dimensions not supported` | BGE 类模型不认该参数 | `EMBEDDING_SEND_DIMENSIONS=false` |
| 写 Qdrant 报 `vector dimension error` | 配置维度与 collection 不符 | 删 collection 重建 + 重新导入文档 |
| 问数节点频繁 JSON 解析失败 | 提示词里没有 "json" 字样 | 检查提示词，或关掉 json_mode 走文本解析 |
| 大批量导入偶发 429 | 触发服务商限流 | 调小 `EMBEDDING_BATCH_SIZE` |

---

## 八、成本参考

DeepSeek 的价格优势明显，本项目的典型消耗：

- **RAG 单次问答**：约 2 次 LLM 调用（query_rewrite + generation），上下文 3-6K tokens
- **问数单次查询**：约 3 次 LLM 调用（nl_understand + sql_compile + result_analyze）

其中 `query_rewrite` 和 `intent_recognize` 属于低价值调用，项目提供了 `get_light_llm()` 走 `DEEPSEEK_LIGHT_MODEL`。DeepSeek 目前只有一档主力模型，两者填一样即可；将来若切到多档位模型（或混用 OpenAI），这个分流点已经预留好了。

真正的大头是**首次文档入库的 embedding 费用**，与文档总量成正比，和查询次数无关。用硅基流动的免费额度通常够跑通 PoC。

---

## 九、涉及的代码位置

想进一步调整时看这几个文件：

| 文件 | 作用 |
|---|---|
| `backend/app/config.py` | 所有配置项定义与默认值 |
| `backend/app/llm/base.py` | Provider 抽象、DeepSeek 实现、embedding 解耦、启动校验 |
| `backend/scripts/check_llm.py` | 连通性自检脚本 |
| `backend/.env.example` | 配置模板（含四种 embedding 方案） |
| `backend/app/main.py` | 启动时调用 `validate_llm_config()` |
| `docker-compose.yml` | 容器环境变量透传 |

业务代码（各 LangGraph 节点）一律通过 `get_llm()` / `get_light_llm()` / `get_embedding_provider()` 获取模型，**不直接引用任何厂商 SDK**。所以换模型厂商只改 `.env`，不动业务逻辑。
