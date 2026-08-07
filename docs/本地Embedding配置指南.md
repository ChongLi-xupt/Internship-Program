# 本地 Embedding 配置指南

> 用本机已下载的 HuggingFace 模型做向量化，完全离线、零 API 成本。
> 本文的所有数据来自在你这台机器上的实测，不是抄的官方文档。

---

## 一、你机器上已有什么

扫描 `~/.cache/huggingface/hub` 的结果：

| 模型 | 维度 | 权重大小 | 最大长度 | 状态 | 结论 |
|---|---|---|---|---|---|
| **BAAI/bge-large-zh-v1.5** | **1024** | 1241.9 MB | 512 token | ✅ 完整 | **推荐，直接用** |
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 384 | 448.8 MB | 512 token | ✅ 完整 | 中文效果差一档，仅作备选 |

运行环境：

```
Python 3.12.8  (C:\Program Files\Python312\python.exe)
torch 2.13.0+cpu     ← 纯 CPU 版本，无 CUDA
transformers 4.57.6
sentence-transformers 3.3.1
```

**选 bge-large-zh-v1.5**。它是 BAAI 专门为中文检索训练的模型，在中文 RAG 场景上明显强于多语言通用模型。MiniLM 的优势只有体积小、速度快，如果后面发现 CPU 吞吐扛不住，可以降级到它，但准确率要打折。

> ⚠️ bge-large-zh-v1.5 的缓存里有个小问题：`main` 分支的快照只有 `pytorch_model.bin`，没有 `model.safetensors`（另一个孤立快照里有，但缺配置文件）。实测加载正常，不用管。

---

## 二、直接可用的配置

编辑 `backend/.env`：

```bash
# ── 对话：DeepSeek ──
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ── 向量化：本地 bge-large-zh-v1.5 ──
EMBEDDING_PROVIDER=huggingface
HF_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false

HF_EMBEDDING_DEVICE=              # 留空自动检测；你这台机器会落到 cpu
HF_EMBEDDING_NORMALIZE=true
HF_EMBEDDING_QUERY_INSTRUCTION=为这个句子生成表示以用于检索相关文章：
HF_EMBEDDING_OFFLINE=true
HF_EMBEDDING_TORCH_THREADS=4
EMBEDDING_BATCH_SIZE=16
```

装依赖（你的系统 Python 已经装好了，Docker 里需要）：

```bash
pip install sentence-transformers
```

配完自检：

```bash
cd backend && python -m scripts.check_llm
```

---

## 三、每个参数为什么这么设

### `EMBEDDING_DIMENSIONS=1024` —— 最不能填错的一项

来自模型 `1_Pooling/config.json` 的 `word_embedding_dimension`，实测输出确认为 1024。

**Qdrant 的 collection 在创建时锁定维度，之后改不了。** 填错的后果不是启动报错，而是第一次写向量时报 `vector dimension error`，此时 collection 已经建好了，必须删掉重建。

所以顺序是：**先定死 embedding 模型 → 再导入任何文档**。

### `EMBEDDING_SEND_DIMENSIONS=false`

这是 OpenAI `text-embedding-3-*` 系列独有的截断参数。本地模型根本不走 HTTP，这个参数没有任何意义。留成 `true` 会被启动校验拦下——因为它几乎总是意味着配置是从 OpenAI 那份直接抄过来的，其他项大概率也没改。

### `HF_EMBEDDING_QUERY_INSTRUCTION` —— 删了会掉召回率

BGE 是**非对称检索模型**：查询侧要加指令前缀，文档侧不加。

实测证据（同一段文本 `"营业收入统计口径说明"`）：

```
作为 query 编码 vs 作为 document 编码   cos = 0.93063   ← 前缀生效，两者不同
把前缀置空后再比                        cos = 1.000000  ← 完全一致
```

这个差异对短查询的召回率影响很实在。**换非 BGE 模型时（MiniLM / GTE / E5）必须把它留空或改成该模型自己的格式**，否则会反向拉低效果——E5 系列用的是 `query: ` / `passage: `，格式完全不同。

代码里这个前缀只作用于 `embed_query()`，`embed_documents()` 永远不加。这一点被单测覆盖了。

### `HF_EMBEDDING_TORCH_THREADS=4`

torch 默认会吃掉所有 CPU 核心。在 Web 服务里这会让批量向量化和 API 请求抢 CPU，表现为**导入文档时整个服务卡顿**。限制到 4 个线程，牺牲一点导入速度换服务可用性。

单机压测或离线批量导入时可以设成 `0`（不限制）。

### `HF_EMBEDDING_OFFLINE=true`

强制 `HF_HUB_OFFLINE=1`。模型不在缓存里时**立刻报错**，而不是默默去连 huggingface.co 然后卡到超时——国内网络环境下后者会让你排查半天。

---

## 四、实测性能

在你这台机器（CPU 模式，`torch_threads=4`）：

| 场景 | 数据 |
|---|---|
| 模型首次加载 | **10.4 秒**（进程生命周期内只发生一次） |
| 二次获取模型 | **0.0 ms**（进程内单例缓存） |
| 短文本吞吐 | ~27.6 条/秒 |
| 长文本吞吐（chunk 级） | **~5.9 条/秒** |
| 单条查询向量化 | ~0.15 秒 |

### 这意味着什么

**查询侧完全没问题。** 单次 0.15s，相对 LLM 生成的秒级延迟可以忽略。

**导入侧要有心理预期。** 按 5.9 条/秒算：

| 文档量 | 大致 chunk 数 | 向量化耗时 |
|---|---|---|
| 10 份 PDF（各 20 页） | ~600 | **约 1.7 分钟** |
| 100 份 | ~6000 | **约 17 分钟** |
| 1000 份 | ~60000 | **约 2.8 小时** |

首次大批量导入建议：

1. 放到后台任务跑，别在 HTTP 请求里同步等
2. 临时把 `HF_EMBEDDING_TORCH_THREADS` 设为 `0`，`EMBEDDING_BATCH_SIZE` 提到 `32`
3. 量特别大就先用云端 API 完成首次建库，日常增量再切回本地——**但两边必须是同一个模型**，否则向量空间不兼容，检索会彻底失效

### 想更快

- **装 CUDA 版 torch**（如果这台机器有独显）：吞吐能提升 10~30 倍，只需把 `HF_EMBEDDING_DEVICE` 留空自动检测
- **换 MiniLM**：速度快 3 倍左右，代价是维度降到 384、中文效果下降，且需要 `EMBEDDING_DIMENSIONS=384` + 清空指令前缀 + 重建索引

---

## 五、Docker 部署

模型权重**不打进镜像**（1.3 GB，且每次重建都要重新 COPY），而是挂载宿主机缓存。

`docker-compose.yml` 已配好，Windows 下需要指定缓存路径：

```bash
# 项目根目录的 .env（不是 backend/.env）
HF_CACHE_DIR=C:/Users/小李/.cache/huggingface
EMBEDDING_PROVIDER=huggingface
HF_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSIONS=1024
DEEPSEEK_API_KEY=sk-你的密钥
```

容器内挂载点是 `/models`（只读），并设置 `HF_HOME=/models`，模型路径能自动解析。

> 注意：后端镜像需要装 `sentence-transformers`，会连带拉入 torch，**镜像会增大约 2 GB**。如果部署环境更在意镜像体积，就用云端 embedding API 方案。

---

## 六、故障排查

<details>
<summary><b>No module named 'sentence_transformers'</b></summary>

```bash
pip install sentence-transformers
```

注意确认装到了实际运行服务的那个 Python 环境。这台机器上有两个：
- `C:\Program Files\Python312\python.exe` —— 已装
- `C:\Users\小李\.workbuddy\binaries\python\...` —— 未装
</details>

<details>
<summary><b>报错说找不到模型 / offline 模式下无法下载</b></summary>

模型不在本地缓存里。三种解法：

```bash
# 1. 下载
huggingface-cli download BAAI/bge-large-zh-v1.5

# 2. 填绝对路径
HF_EMBEDDING_MODEL=D:/models/bge-large-zh-v1.5

# 3. 临时允许联网（不推荐长期开启）
HF_EMBEDDING_OFFLINE=false
```
</details>

<details>
<summary><b>写 Qdrant 报 vector dimension error</b></summary>

`EMBEDDING_DIMENSIONS` 和模型实际输出对不上，或者 collection 是用旧维度建的。

先用 `python -m scripts.check_llm` 看实际维度，改对配置后**删除 collection 重建**——维度是创建时锁定的，改不了。
</details>

<details>
<summary><b>检索结果明显不相关</b></summary>

先跑 `python -m scripts.check_llm`，第 5 步会做语义排序抽查。正常应该长这样：

```
0.6773  2024年第三季度营业总收入为 3.2 亿元，同比增长 12%
0.5464  第三季度销售费用率下降至 8.4%
0.3187  员工年假申请需提前三个工作日在 OA 系统提交
```

如果无关文档排到前面，按顺序查：
1. 用了 BGE 却没配 `HF_EMBEDDING_QUERY_INSTRUCTION`
2. 用了非 BGE 却保留了 BGE 的前缀
3. `HF_EMBEDDING_NORMALIZE` 被关掉了，而向量库按余弦检索
4. 索引是用另一个模型建的——换模型必须全量重建
</details>

<details>
<summary><b>导入文档时整个服务卡死</b></summary>

torch 抢光了 CPU。确认 `HF_EMBEDDING_TORCH_THREADS` 已设成 4（或核心数的一半），并且导入走的是后台任务而不是同步 HTTP 请求。

代码层面向量化已经通过 `run_in_executor` 从事件循环里挪出去了，所以不会阻塞其他请求——但 CPU 被占满时一样会拖慢整体响应。
</details>

---

## 七、验证脚本

`scripts/_probe_local_embedding.py` 是接入时写的端到端验证，共 14 项检查，覆盖配置校验分支、模型单例、维度、归一化、指令前缀非对称性、检索排序、吞吐。

**换模型后重跑一次**，比启动服务再上传文档试要快得多：

```bash
cd backend && python scripts/_probe_local_embedding.py
```

它不依赖 `.env` 和数据库，改脚本顶部的内存配置即可测任意模型组合。
