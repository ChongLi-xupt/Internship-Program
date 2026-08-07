# RAG Smart Query · 企业级 RAG 问答与智慧问数系统

> 一套系统，两个引擎：**私有知识库检索问答（RAG）** + **业务数据自然语言查询（Text-to-SQL）**
>
> 基于 FastAPI + LangGraph 构建，面向企业级场景设计——多租户隔离、RBAC 权限、SQL 安全网关、全链路审计。

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi\&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2.50+-1C3C3C)
![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react\&logoColor=black)
![License](https://img.shields.io/badge/License-Internal-lightgrey)

***

## 目录

- [这是什么](#这是什么)
- [核心设计理念](#核心设计理念)
- [系统架构](#系统架构)
- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [两条工作流详解](#两条工作流详解)
- [SQL 安全网关](#sql-安全网关)
- [权限模型](#权限模型)
- [常见问题](#常见问题)
- [Roadmap](#roadmap)

***

## 这是什么

企业内部两类高频提问，这套系统各用一条独立通道来回答：

| 提问类型    | 举例                   | 走哪条通道  | 数据来源             |
| ------- | -------------------- | ------ | ---------------- |
| **知识型** | "报销超过 5000 元需要哪些审批？" | RAG 引擎 | 制度文档、手册、合同（非结构化） |
| **数据型** | "上季度华东区销售额同比增长多少？"   | 智慧问数引擎 | 业务数据库（结构化）       |

用户在前端只看到一个对话框，后端由意图路由分发到对应引擎。

***

## 核心设计理念

### 1. RAG 和智慧问数是两套系统，不是一套

两者的**正确性标准根本不同**：

- RAG 答得"有依据、不编造"就算合格，可以模糊、可以给多个候选
- 问数**错一位数字就是决策事故**，必须精确、可复现、可审计

所以本项目**内核完全独立**，只共享外壳（认证接入、对话编排、模型服务、治理底座）。把问数当成"对数据库做 RAG"是最常见的架构错误。

### 2. 问数的准确率天花板由语义层决定，不由大模型决定

让模型直接面对几百张物理表裸写 SQL，真实企业环境准确率通常只有 **40%–60%**，交付不了。

本项目采用**语义层中介模式**，把模型的任务从"写 SQL"降级为"填写查询意图槽位"：

```
自然语言  →  结构化意图（指标 + 维度 + 过滤 + 时间粒度）  →  确定性模板编译  →  SQL
          ↑ LLM 只负责这一步                            ↑ 这一步无 LLM 参与，完全可控
```

好处：准确率可做到 **85%–95%**，且生成的 SQL 形态完全在掌控之中，不会出现"模型突然写了个 7 表 JOIN"的情况。

### 3. 权限过滤必须前置，不能靠模型"记得别说"

- RAG：权限过滤下沉到**向量检索阶段**，无权限的分块根本不会进入上下文
- 问数：行级权限条件在 **SQL 编译后、执行前**强制注入 WHERE 子句
- 缓存 Key **必须包含权限上下文**，否则 A 部门会命中 B 部门的缓存结果（高危越权）

***

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     React 前端 (Vite + Ant Design)               │
│   RAG 对话  │  智慧问数面板  │  知识库管理  │  语义层  │  审计   │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST + SSE (流式)
┌────────────────────────────▼────────────────────────────────────┐
│                    FastAPI 接入层 (/api/v1)                      │
│   JWT 认证  │  多租户隔离中间件  │  RBAC 鉴权  │  限流  │  审计   │
└──────────────┬──────────────────────────────┬───────────────────┘
               │                              │
    ┌──────────▼──────────┐        ┌──────────▼──────────────────┐
    │   RAG 工作流         │        │   智慧问数工作流             │
    │   (LangGraph)       │        │   (LangGraph)               │
    │                     │        │                             │
    │  query_rewrite      │        │  intent_recognize           │
    │       ↓             │        │       ↓                     │
    │  retrieval          │        │  nl_understand ← 语义层      │
    │  (向量+关键词混合)   │        │       ↓                     │
    │       ↓             │        │  example_retrieve (Few-shot)│
    │  rerank             │        │       ↓                     │
    │       ↓             │        │  sql_compile (模板编译)      │
    │  context_assemble   │        │       ↓                     │
    │       ↓             │        │  ⚠ sql_guard (7 层安全)     │
    │  generation (LLM)   │        │       ↓                     │
    │       ↓             │        │  sql_execute (只读沙箱)      │
    │  citation (溯源)     │        │       ↓                     │
    │                     │        │  result_analyze (LLM 解读)   │
    │                     │        │       ↓                     │
    │                     │        │  chart_recommend            │
    │                     │        │       ↓                     │
    │                     │        │  response_format            │
    └──────────┬──────────┘        └──────────┬──────────────────┘
               │                              │
┌──────────────▼──────────────────────────────▼───────────────────┐
│                          存储与依赖层                             │
│  PostgreSQL   │   Qdrant    │    Redis     │   LLM Provider     │
│  (元数据/审计) │  (向量索引)  │ (缓存/会话)   │ (OpenAI/本地模型)   │
└─────────────────────────────────────────────────────────────────┘
```

***

## 功能特性

### RAG 知识问答

- **多格式文档接入**：PDF / DOCX / XLSX / HTML / Markdown，表格结构保留
- **智能分块**：递归分块 + 语义边界感知，可配置 chunk\_size / overlap
- **混合检索**：向量语义检索 + 关键词检索，结果融合
- **重排序**：Cross-Encoder 精排，提升 Top-K 相关性
- **引用溯源**：每条回答标注来源文档、页码、原文片段，可点击展开
- **流式输出**：SSE 推送，首字延迟目标 < 1.5s

### 智慧问数（Text-to-SQL）

- **语义层建模**：指标（Metric）/ 维度（Dimension）/ 业务术语库 / SQL 示例库
- **业务术语翻译**："GMV"→ `sum(order_amount)`、"华东区"→ `region_code IN (...)`
- **Few-shot 检索**：从已验证的 SQL 示例库中检索相似案例注入提示词
- **SQL 安全网关**：7 层防护链（详见下文），LLM 生成的 SQL 无法绕过
- **执行沙箱**：只读账号 + 超时熔断 + 行数上限 + 结果集脱敏
- **结果解读**：LLM 分析数据趋势，输出自然语言结论
- **图表推荐**：基于数据形态（维度基数 / 时间序列 / 占比）规则推荐图表类型，ECharts 渲染

### 企业级能力

| 能力          | 实现方式                                      |
| ----------- | ----------------------------------------- |
| **多租户隔离**   | 所有表带 `tenant_id`，ORM 层自动注入过滤条件，跨租户查询直接抛异常 |
| **RBAC 权限** | 4 级角色 × 18 项细粒度权限，装饰器式声明                  |
| **数据加密**    | 数据源连接凭据 AES-256-GCM 加密存储                  |
| **数据脱敏**    | 敏感列（手机/身份证/银行卡）按角色自动脱敏                    |
| **审计日志**    | 全量记录：谁、何时、问了什么、生成什么 SQL、返回多少行             |
| **限流控制**    | 对话 / 上传 / SQL 执行 三档独立限流 + 单用户并发上限         |
| **可替换性**    | LLM、向量库、存储均走抽象层，任一组件可在两周内替换               |

***

## 技术栈

### 后端

| 组件     | 选型                                                  | 说明                  |
| ------ | --------------------------------------------------- | ------------------- |
| Web 框架 | FastAPI 0.115+                                      | 异步、自动 OpenAPI 文档    |
| 工作流编排  | LangGraph 0.2.50+                                   | 状态机式 DAG，支持条件分支与检查点 |
| ORM    | SQLAlchemy 2.0 (async)                              | 配合 asyncpg 驱动       |
| 迁移     | Alembic                                             | <br />              |
| 主数据库   | PostgreSQL 16                                       | 元数据、对话历史、审计日志       |
| 向量库    | Qdrant 1.12                                         | 支持元数据过滤的 HNSW 索引    |
| 缓存     | Redis 7                                             | 会话、查询缓存、限流计数        |
| SQL 解析 | sqlglot 26+                                         | AST 级校验与改写，多方言支持    |
| 文档解析   | pdfplumber / python-docx / openpyxl / BeautifulSoup | <br />              |
| 认证     | python-jose (JWT) + passlib (bcrypt)                | <br />              |
| 日志     | structlog                                           | 结构化日志               |

### 前端

| 组件       | 选型                              |
| -------- | ------------------------------- |
| 框架       | React 18.3 + TypeScript 5.5     |
| 构建       | Vite 7                          |
| UI       | Ant Design 5.21                 |
| 状态管理     | Zustand 4.5                     |
| 图表       | ECharts 5.5 + echarts-for-react |
| Markdown | react-markdown + remark-gfm     |
| 请求       | Axios（含 SSE 流式处理）               |

***

## 快速开始

### 方式一：Docker Compose（推荐）

一条命令拉起全部 6 个服务（PostgreSQL / Redis / Qdrant / Backend / Frontend / Nginx）。

> 项目根目录已自带 `.env` 文件，包含 DeepSeek API Key 和本地 HuggingFace Embedding 配置，开箱即用。如需自定义，编辑 `rag-smart-query/.env` 即可。

***

#### 前置条件

**Windows**

1. 安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 启动 Docker Desktop，确保右下角 Docker 图标显示 "running"
3. 确认 WSL2 后端已启用（Docker Desktop 安装时默认启用）
4. 打开 **PowerShell** 或 **Git Bash** 作为终端

```powershell
# 验证 Docker 已就绪
docker --version
docker compose version

# 预下载 HuggingFace Embedding 模型（约 1.3GB，仅首次需要）
# 模型会缓存在宿主机上，容器以只读方式挂载，不会打包进镜像
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-zh-v1.5')"
```

**Linux (Ubuntu / Debian / CentOS)**

1. 安装 Docker Engine + Docker Compose 插件：

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 将当前用户加入 docker 组（免 sudo）
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version
docker compose version
```

1. 预下载 HuggingFace Embedding 模型：

```bash
# 安装 huggingface-cli
pip install -U "huggingface_hub[cli]"

# 下载模型到默认缓存目录 ~/.cache/huggingface
huggingface-cli download BAAI/bge-large-zh-v1.5
```

***

#### 配置环境变量

项目根目录的 `.env` 文件已被 `docker compose` 自动读取。关键配置项：

```bash
# ── 对话模型（DeepSeek，已配置好）──
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx                    # 替换为你的 Key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# ── 向量化模型（本地 HuggingFace，离线零成本）──
EMBEDDING_PROVIDER=huggingface
HF_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
HF_CACHE_DIR=~/.cache/huggingface          # ⚠️ Windows 用户改为实际路径

# ── Redis 端口（默认 6380 避免冲突）──
REDIS_HOST_PORT=6380

# ── 安全密钥（生产环境务必更换）──
SECRET_KEY=dev-secret-key-change-me-in-production-32b
ENCRYPTION_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# ── 初始管理员（首次启动自动创建）──
INIT_ADMIN_USERNAME=admin
INIT_ADMIN_PASSWORD=admin123456
```

> **Windows 用户注意**：`HF_CACHE_DIR` 需要指向你本机的 HuggingFace 缓存目录。如果你用 PowerShell 下载了模型，默认缓存在 `C:/Users/<你的用户名>/.cache/huggingface`。请将 `.env` 中的 `HF_CACHE_DIR` 改为此路径（使用正斜杠 `/`）。

***

#### 启动服务

**Windows (PowerShell / Git Bash)**

```powershell
# 进入项目目录
cd "D:\桌面\实习\RAG知识库+智慧问数\rag-smart-query"

# 构建并启动全部服务（首次构建约 5-10 分钟，主要是 pip install torch）
docker compose up -d --build

# 查看运行状态
docker compose ps

# 跟踪后端日志（等待 "Application startup complete" 出现）
docker compose logs -f backend
```

**Linux (Bash)**

```bash
# 进入项目目录
cd /path/to/rag-smart-query

# 构建并启动全部服务
docker compose up -d --build

# 查看运行状态
docker compose ps

# 跟踪后端日志
docker compose logs -f backend
```

> 后端容器启动时会自动执行 `python -m scripts.init_db` 创建数据库表并初始化管理员账号，随后启动 `uvicorn`。首次启动等待约 30-60 秒。

***

#### 启动后访问

| 服务             | 地址                                | 说明                         |
| -------------- | --------------------------------- | -------------------------- |
| 前端界面           | <http://localhost:3000>           | React + Ant Design         |
| 后端 API         | <http://localhost:8000>           | FastAPI                    |
| **Swagger 文档** | <http://localhost:8000/docs>      | 交互式 API 文档                 |
| 健康检查           | <http://localhost:8000/health>    | 返回 `{"status": "healthy"}` |
| Qdrant 控制台     | <http://localhost:6333/dashboard> | 向量库管理界面                    |
| Nginx 入口       | <http://localhost:80>             | 统一入口（代理前后端）                |

默认管理员账号：`admin` / `admin123456`

***

#### 常用 Docker 命令

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f                    # 全部服务
docker compose logs -f backend            # 仅后端
docker compose logs -f frontend           # 仅前端

# 停止服务（数据保留在 volume 中，不会丢失）
docker compose stop

# 重新启动
docker compose start

# 停止并删除容器（volume 数据保留）
docker compose down

# 停止并删除容器 + 数据卷（⚠️ 清空所有数据，不可恢复）
docker compose down -v

# 仅重建后端（修改后端代码后）
docker compose up -d --build backend

# 仅重建前端
docker compose up -d --build frontend

# 进入后端容器调试
docker compose exec backend bash

# 手动执行数据库初始化
docker compose exec backend python -m scripts.init_db

# 检查后端健康状态
docker compose exec backend curl -fsS http://localhost:8000/health
```

***

#### Docker 故障排查

<details>
<summary><b>Windows: HF_CACHE_DIR 挂载失败 / 容器找不到模型</b></summary>

`.env` 中的 `HF_CACHE_DIR` 必须使用正斜杠且指向实际存在的路径。检查方法：

```powershell
# 确认路径存在
Test-Path "C:/Users/$env:USERNAME/.cache/huggingface"

# 如果不存在，手动下载模型
pip install sentence-transformers
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-zh-v1.5')"
```

然后在 `.env` 中设置：

```
HF_CACHE_DIR=C:/Users/你的用户名/.cache/huggingface
```

</details>

<details>
<summary><b>端口被占用（5432 / 6380 / 6333 / 8000 / 3000 / 80）</b></summary>

```bash
# 查看哪个进程占用了端口
# Linux:
sudo lsof -i :8000
# Windows:
netstat -ano | findstr :8000

# 方案一：停掉占用端口的进程
# 方案二：修改 docker-compose.yml 中的端口映射（左侧改为主机空闲端口）
```

Redis 默认映射到宿主机 `6380` 端口（已在 `.env` 中通过 `REDIS_HOST_PORT=6380` 避开本机 Redis）。

</details>

<details>
<summary><b>后端启动后立即退出 / 健康检查失败</b></summary>

```bash
# 查看后端退出日志
docker compose logs backend

# 常见原因：
# 1. DeepSeek API Key 无效 → 后端启动时 validate_llm_config() 失败
# 2. PostgreSQL 未就绪 → 等待 healthcheck 通过即可
# 3. HuggingFace 模型未下载 → 按上面的步骤预下载
```

</details>

<details>
<summary><b>首次构建很慢 / pip install 超时</b></summary>

后端 Dockerfile 会先安装 CPU 版 PyTorch（约 200MB），再安装其余依赖。如果网络不佳：

```bash
# 配置 Docker BuildKit pip 缓存（Dockerfile 已内置 --mount=type=cache）
# 确保 Docker 使用 BuildKit
export DOCKER_BUILDKIT=1          # Linux
$env:DOCKER_BUILDKIT=1            # Windows PowerShell

# 或者配置国内 pip 镜像源（在 backend/Dockerfile 的 pip install 前加）
# pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ...
```

</details>

<details>
<summary><b>Linux: permission denied while trying to connect to Docker</b></summary>

```bash
# 将用户加入 docker 组并刷新
sudo usermod -aG docker $USER
newgrp docker

# 或者临时用 sudo
sudo docker compose up -d --build
```

</details>

### 方式二：本地开发

**前置依赖**：Python 3.11+、Node.js 18+，以及运行中的 PostgreSQL / Redis / Qdrant。

中间件可以只用 Docker 起：

```bash
docker compose up -d postgres redis qdrant
```

**后端**：

```bash
cd backend

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env               # 编辑填入 API Key

# 初始化数据库
alembic upgrade head

# 启动（热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端**：

```bash
cd frontend

npm install
npm run dev                        # http://localhost:5173
```

Vite 已配置代理，`/api` 请求自动转发到 `http://localhost:8000`。

### 首次使用流程

1. 打开前端 → 注册账号（首个注册用户自动成为 `tenant_admin`）
2. **知识库管理** → 新建知识库 → 上传文档 → 等待处理完成（状态变为 `completed`）
3. 切到 **RAG 对话** → 提问，验证能否检索到内容并给出引用
4. **数据源管理** → 添加数据库连接 → 测试连接 → 同步表结构
5. **语义层** → 定义指标和维度 → **术语库** 补充业务黑话 → **SQL 示例库** 录入典型问答对
6. 切到 **智慧问数** → 提问，观察右侧面板的 SQL / 数据表 / 图表 / AI 解读

> **重要**：跳过第 5 步直接问数，准确率会很难看。语义层是这套系统的地基。

***

## 配置说明

核心环境变量（完整列表见 `backend/.env.example`）：

```bash
# ── 应用 ──
SECRET_KEY=                        # JWT 签名密钥，生产环境务必改成随机 32 字节
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# ── 数据库 ──
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rag_smart_query
REDIS_URL=redis://localhost:6379/0

# ── 向量库 ──
VECTOR_STORE=qdrant
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION_PREFIX=kb_

# ── 对话模型（openai / deepseek / anthropic / ollama）──
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# 私有化部署走 Ollama
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2.5:14b

# ── Embedding（与对话模型独立配置）──
# ⚠️ DeepSeek 没有 embedding 接口，必须单独指向本地模型或别的服务

# 方案一：本地模型（推荐，完全离线、零 API 成本）
EMBEDDING_PROVIDER=huggingface
HF_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
HF_EMBEDDING_QUERY_INSTRUCTION=为这个句子生成表示以用于检索相关文章：
HF_EMBEDDING_TORCH_THREADS=4

# 方案二：云端 API（免装 torch，吞吐高）
# EMBEDDING_PROVIDER=openai
# EMBEDDING_MODEL=BAAI/bge-m3
# EMBEDDING_API_KEY=sk-your-siliconflow-key
# EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
# EMBEDDING_DIMENSIONS=1024
# EMBEDDING_SEND_DIMENSIONS=false

# ── 安全 ──
ENCRYPTION_KEY=                    # 32 字节，用于数据源凭据 AES-256-GCM 加密

# ── 限流 ──
RATE_LIMIT_CHAT_PER_MINUTE=60
RATE_LIMIT_SQL_PER_HOUR=300
MAX_CONCURRENT_QUERY_PER_USER=3

# ── SQL 网关 ──
SQL_GUARD_MAX_ROWS=10000
SQL_GUARD_TIMEOUT_SECONDS=30
```

> ⚠️ **Embedding 模型不可随意更换**。更换后必须全量重建向量索引，架构支持双索引灰度切换，但请提前规划。

***

## 项目结构

```
rag-smart-query/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口 + 生命周期
│   │   ├── config.py                  # Pydantic Settings 配置
│   │   ├── database.py                # 异步 Session 工厂
│   │   ├── dependencies.py            # 依赖注入（当前用户/租户/DB）
│   │   │
│   │   ├── core/                      # ── 基础设施 ──
│   │   │   ├── security.py            # JWT 签发校验、密码哈希、AES 加解密
│   │   │   ├── tenant.py              # 多租户隔离过滤器
│   │   │   ├── rbac.py                # 权限枚举 + 角色映射
│   │   │   ├── audit.py               # 审计日志写入
│   │   │   └── cache.py               # Redis 缓存（权限感知 Key）
│   │   │
│   │   ├── models/                    # ── ORM 模型（15 张表）──
│   │   │   ├── user.py                # tenants, users
│   │   │   ├── knowledge.py           # knowledge_bases, documents, chunks
│   │   │   ├── datasource.py          # datasources, table_metas
│   │   │   ├── semantic.py            # semantic_layers, metrics, dimensions,
│   │   │   │                          #   terminologies, sql_examples
│   │   │   ├── conversation.py        # conversations, messages
│   │   │   └── audit.py               # audit_logs
│   │   │
│   │   ├── schemas/                   # Pydantic 请求/响应模型
│   │   │
│   │   ├── graph/                     # ── LangGraph 工作流 ──
│   │   │   ├── rag_graph.py           # RAG DAG 装配
│   │   │   ├── query_graph.py         # 问数 DAG 装配
│   │   │   ├── state/                 # 工作流状态定义
│   │   │   └── nodes/
│   │   │       ├── rag/               # 6 个 RAG 节点
│   │   │       └── query/             # 9 个问数节点
│   │   │
│   │   ├── api/                       # ── REST 路由 ──
│   │   │   ├── auth.py                # 登录/注册/刷新/改密
│   │   │   ├── users.py               # 用户管理
│   │   │   ├── knowledge.py           # 知识库 CRUD
│   │   │   ├── ingestion.py           # 文档上传与处理
│   │   │   ├── chat.py                # 对话（SSE 流式）★
│   │   │   ├── datasource.py          # 数据源管理
│   │   │   ├── semantic.py            # 语义层/术语库/SQL 示例
│   │   │   └── admin.py               # 审计日志/统计/租户
│   │   │
│   │   ├── ingestors/                 # 文档解析器 + 分块器
│   │   ├── services/                  # 业务服务层
│   │   ├── vector/                    # 向量存储抽象层
│   │   ├── llm/                       # LLM 抽象层
│   │   └── utils/                     # 数据脱敏等工具
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    # 路由定义
│   │   ├── api/client.ts              # Axios 实例 + SSE 流式封装
│   │   ├── stores/                    # Zustand（认证 / 对话）
│   │   ├── components/
│   │   │   ├── Layout/                # 主布局 + 侧边导航
│   │   │   ├── ChatMessage.tsx        # 消息渲染（Markdown/引用/表格）
│   │   │   └── ChartPanel.tsx         # ECharts 图表面板
│   │   └── pages/
│   │       ├── Login.tsx
│   │       ├── Dashboard.tsx
│   │       ├── chat/RagChat.tsx       # RAG 对话
│   │       ├── chat/SmartQuery.tsx    # 智慧问数面板 ★
│   │       ├── knowledge/             # 知识库管理
│   │       ├── data/                  # 数据源 / 术语库 / SQL 示例
│   │       └── admin/AuditLog.tsx     # 审计日志
│   │
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docker-compose.yml
└── nginx.conf                         # 反向代理（含 SSE 长连接配置）
```

***

## API 概览

全部接口挂载在 `/api/v1` 前缀下，完整交互式文档见 <http://localhost:8000/docs>

### 认证 `/auth`

| 方法   | 路径               | 说明                           |
| ---- | ---------------- | ---------------------------- |
| POST | `/auth/login`    | 登录，返回 access + refresh token |
| POST | `/auth/register` | 注册                           |
| POST | `/auth/refresh`  | 刷新 token                     |
| GET  | `/auth/me`       | 当前用户信息                       |
| PUT  | `/auth/password` | 修改密码                         |

### 知识库与文档

| 方法             | 路径                                          | 说明           |
| -------------- | ------------------------------------------- | ------------ |
| POST/GET       | `/knowledge-bases`                          | 创建 / 列表      |
| GET/PUT/DELETE | `/knowledge-bases/{kb_id}`                  | 详情 / 更新 / 删除 |
| POST           | `/knowledge-bases/{kb_id}/documents/upload` | 批量上传文档       |
| GET            | `/knowledge-bases/{kb_id}/documents`        | 文档列表（含处理状态）  |
| GET/DELETE     | `/documents/{doc_id}`                       | 文档详情 / 删除    |

### 对话 `/chat` ★

| 方法     | 路径                              | 说明                 |
| ------ | ------------------------------- | ------------------ |
| POST   | `/chat/messages`                | **发送消息（SSE 流式响应）** |
| GET    | `/chat/conversations`           | 会话列表               |
| DELETE | `/chat/conversations/{conv_id}` | 删除会话               |

**SSE 事件类型**（前端按 `event:` 字段分发）：

| 事件                     | 触发时机        | payload                         |
| ---------------------- | ----------- | ------------------------------- |
| `thinking`             | 各阶段进度提示     | `{content}`                     |
| `retrieval_result`     | RAG 检索完成    | `{sources[]}`                   |
| `query_intent`         | 问数意图解析完成    | `{intent}`                      |
| `sql_generated`        | SQL 生成并通过网关 | `{sql}`                         |
| `sql_executing`        | 开始执行 SQL    | `{}`                            |
| `result_data`          | 查询结果返回      | `{columns, rows, row_count}`    |
| `chart_recommendation` | 图表类型推荐      | `{chart_type, config}`          |
| `message_delta`        | 文本流式增量      | `{content}`                     |
| `message_done`         | 结束（含元数据/用量） | `{message_id, metadata, usage}` |

### 数据源 `/datasources`

| 方法             | 路径                                     | 说明           |
| -------------- | -------------------------------------- | ------------ |
| POST/GET       | `/datasources`                         | 创建 / 列表      |
| GET/PUT/DELETE | `/datasources/{ds_id}`                 | 详情 / 更新 / 删除 |
| POST           | `/datasources/{ds_id}/test-connection` | 测试连接         |
| GET            | `/datasources/{ds_id}/tables`          | 表结构元数据       |

### 语义层 `/semantic`

| 方法       | 路径                                   | 说明      |
| -------- | ------------------------------------ | ------- |
| POST     | `/semantic/layers`                   | 创建语义层   |
| GET/POST | `/semantic/layers/{id}/metrics`      | 指标管理    |
| GET/POST | `/semantic/layers/{id}/dimensions`   | 维度管理    |
| GET/POST | `/semantic/terminology`              | 业务术语库   |
| POST     | `/semantic/terminology/batch-import` | 术语批量导入  |
| GET/POST | `/semantic/sql-examples`             | SQL 示例库 |
| POST     | `/semantic/sql-examples/{id}/verify` | 标记示例已验证 |

### 系统管理 `/admin`

| 方法  | 路径                  | 说明                 |
| --- | ------------------- | ------------------ |
| GET | `/admin/audit-logs` | 审计日志查询（支持多维过滤）     |
| GET | `/admin/stats`      | 系统统计               |
| GET | `/admin/users`      | 用户列表               |
| GET | `/admin/tenants`    | 租户列表（super\_admin） |

***

## 两条工作流详解

### RAG 工作流（6 节点）

```
query_rewrite → retrieval → rerank → context_assemble → generation → citation
```

| 节点                 | 职责                        | 是否调用 LLM |
| ------------------ | ------------------------- | -------- |
| `query_rewrite`    | 指代消解、多轮上下文补全、查询扩展         | ✅ 轻量模型   |
| `retrieval`        | 向量检索 + 关键词检索并行，**带权限过滤**  | ❌        |
| `rerank`           | Cross-Encoder 精排，截断 Top-K | ❌        |
| `context_assemble` | 去重、按 token 预算裁剪、拼装提示词     | ❌        |
| `generation`       | 基于上下文生成回答，流式输出            | ✅ 主模型    |
| `citation`         | 抽取引用标记，映射回源文档与页码          | ❌        |

### 智慧问数工作流（9 节点）

```
intent_recognize → nl_understand → example_retrieve → sql_compile
      → sql_guard → sql_execute → result_analyze → chart_recommend → response_format
```

| 节点                 | 职责                                    | 是否调用 LLM |
| ------------------ | ------------------------------------- | -------- |
| `intent_recognize` | 判断是否为数据查询、识别所需数据源                     | ✅ 轻量模型   |
| `nl_understand`    | **核心**：结合语义层与术语库，输出结构化意图（指标/维度/过滤/时间） | ✅ 主模型    |
| `example_retrieve` | 从已验证 SQL 示例库检索相似案例（Few-shot）          | ❌ 向量检索   |
| `sql_compile`      | 结构化意图 → SQL，**模板编译，无 LLM 参与**         | ❌        |
| `sql_guard`        | **7 层安全防护链**（见下节）                     | ❌        |
| `sql_execute`      | 只读连接执行，超时熔断 + 行数上限                    | ❌        |
| `result_analyze`   | 分析数据趋势，生成自然语言结论                       | ✅ 主模型    |
| `chart_recommend`  | 基于数据形态规则推荐图表类型                        | ❌        |
| `response_format`  | 组装最终响应（SQL + 数据 + 图表 + 解读）            | ❌        |

> 注意 LLM 只出现在 3 个节点。SQL 的**生成形态**由模板决定，模型只填槽位——这是准确率和安全性的关键。

***

## SQL 安全网关

`sql_guard` 节点是整个问数链路的**生死线**。任何 LLM 输出的 SQL 都必须完整通过 7 层检查才能执行：

| # | 层            | 检查内容                                                                     | 违规处理 |
| - | ------------ | ------------------------------------------------------------------------ | ---- |
| 1 | **语法校验**     | sqlglot AST 解析，语法错误直接拦截                                                  | 拒绝   |
| 2 | **禁止语句**     | `DROP` / `DELETE` / `UPDATE` / `INSERT` / `TRUNCATE` / `ALTER` / `GRANT` | 拒绝   |
| 3 | **危险函数**     | 文件读写、系统命令、动态执行类函数                                                        | 拒绝   |
| 4 | **只读强制**     | 校验根节点必须是 `SELECT`，禁止 CTE 中夹带写操作                                          | 拒绝   |
| 5 | **行级权限注入**   | 按用户所属组织/部门，强制注入 `WHERE` 条件                                               | 改写   |
| 6 | **LIMIT 强制** | 无 LIMIT 或超过 `SQL_GUARD_MAX_ROWS` 时强制截断                                   | 改写   |
| 7 | **敏感列脱敏**    | 手机号/身份证/银行卡等列按角色包裹脱敏函数                                                   | 改写   |

第 1–4 层任一失败 → 直接终止，返回友好错误，**不执行**。
第 5–7 层做 SQL 改写，改写后的最终 SQL 会记入审计日志。

执行层额外保障：

- 数据源使用**独立只读账号**，数据库层面兜底
- 单次查询超时熔断（默认 30s）
- 单用户并发查询上限（默认 3）

***

## 权限模型

### 角色

| 角色             | 说明                        |
| -------------- | ------------------------- |
| `super_admin`  | 平台超管，拥有全部权限，可跨租户          |
| `tenant_admin` | 租户管理员，管理本租户的知识库、数据源、用户、审计 |
| `editor`       | 内容编辑，可建知识库、传文档、写语义层、问答问数  |
| `viewer`       | 只读用户，可查看知识库、进行问答问数        |

### 权限清单（18 项）

```
知识库   kb:read       kb:write      kb:delete     kb:manage
文档     doc:upload    doc:delete
对话     chat:rag      chat:query
数据源   ds:read       ds:write      ds:query      ds:manage
语义层   semantic:read semantic:write
管理     admin:users   admin:tenants admin:audit   admin:settings
```

### 多租户隔离

- 所有业务表带 `tenant_id` 字段
- ORM 层自动注入 `tenant_id` 过滤条件（`app/core/tenant.py`）
- JWT payload 中携带 `tenant_id`，请求全程透传
- 跨租户访问在依赖注入层直接抛 403，不依赖业务代码自觉

***

## 常见问题

<details>
<summary><b>Q: 文档上传后一直是 processing 状态？</b></summary>

检查后端日志。常见原因：

1. Embedding API Key 无效或额度耗尽
2. Qdrant 未启动或连接不通（`curl http://localhost:6333/healthz`）
3. PDF 是扫描件，无文字层——需要接入 OCR

```bash
docker compose logs -f backend | grep -i ingestion
```

</details>

<details>
<summary><b>Q: 智慧问数生成的 SQL 总是不对？</b></summary>

**90% 的情况是语义层没建好**，不是模型不行。按优先级排查：

1. **术语库**：业务黑话有没有录进去？"GMV"、"动销率"、"华东区"这类词模型不可能猜对
2. **指标定义**：指标的口径（分子/分母/过滤条件）是否明确
3. **SQL 示例库**：至少录 20–30 条典型问答对，Few-shot 效果立竿见影
4. **表注释**：数据源同步的表结构里，字段注释是否完整

调试技巧：前端问数面板会展示 `query_intent` 事件的结构化意图。如果意图解析就错了，问题在语义层；如果意图对但 SQL 错，问题在模板编译。

</details>

<details>
<summary><b>Q: 用 DeepSeek 的 API 要怎么配？</b></summary>

对话部分很简单，DeepSeek 走 OpenAI 协议：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

**但 DeepSeek 官方没有 embedding 接口**，向量化必须单独指向别的服务，否则一上传文档就报 404：

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_KEY=sk-your-siliconflow-key
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
```

配完跑自检确认通了再启动服务：

```bash
cd backend && python -m scripts.check_llm
```

完整说明（含四种 embedding 方案对比、维度陷阱、成本估算）见 [`docs/DeepSeek配置指南.md`](docs/DeepSeek配置指南.md)。

</details>

<details>
<summary><b>Q: 想换成本地模型私有化部署？</b></summary>

改 `.env` 即可，代码不用动：

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false
```

Embedding 换模型后**必须重建全部向量索引**（维度通常不一致）。

问数任务对模型能力要求较高，14B 以下的模型建议先小规模验证准确率再推广。

</details>

<details>
<summary><b>Q: SSE 流式响应在 Nginx 后面断流？</b></summary>

`nginx.conf` 已配置好，如果自建反代注意这几项：

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 300s;
proxy_set_header Connection '';
proxy_http_version 1.1;
```

</details>

<details>
<summary><b>Q: 如何保证 A 部门看不到 B 部门的数据？</b></summary>

三道防线：

1. **RAG 侧**：向量检索时带 `tenant_id` + 部门标签过滤，无权限分块不进上下文
2. **问数侧**：`sql_guard` 第 5 层强制注入行级权限 WHERE 条件
3. **缓存侧**：缓存 Key 包含用户权限指纹，杜绝跨权限命中

**不要**依赖提示词里写"不要透露 XX 部门数据"——那等于没有权限控制。

</details>

***

## Roadmap

已完成（v0.1）：

- [x] 双引擎架构（RAG + 智慧问数）
- [x] LangGraph 工作流编排
- [x] 多租户 + RBAC + 审计
- [x] SQL 7 层安全网关
- [x] SSE 流式对话
- [x] React 完整前端
- [x] Docker Compose 一键部署

计划中：

- [ ] Alembic 迁移脚本补全
- [ ] 单元测试（SQL Guard 用例集、工作流节点）
- [ ] 自动化评测框架（RAG: 命中率/忠实度；问数: 执行结果准确率）
- [ ] 多轮对话上下文管理增强
- [ ] 知识库增量更新与向量索引灰度切换
- [ ] 更多数据源方言（MySQL / ClickHouse / Doris）
- [ ] 移动端适配

***

## 相关文档

| 文档        | 位置                                | 内容                               |
| --------- | --------------------------------- | -------------------------------- |
| 架构规划与实施分析 | `../企业级RAG问答与智慧问数系统_架构规划与实施分析.md` | 架构分层、企业级能力、选型准则、里程碑排期、风险清单       |
| 开发技术文档    | `../开发技术文档.md`                    | 数据库 Schema、API 详细设计、工作流 DAG、部署方案 |

***

## 免责与提醒

- `.env.example` 中的密钥均为占位值，**生产环境必须全部替换**
- 数据源请务必配置**只读账号**，不要用管理员账号连生产库
- 上线前请完成：安全评审、压测、评测集基线建立
- 大模型输出存在不确定性，涉及财务、法务等关键决策的数据请人工复核

***

**Built with FastAPI · LangGraph · React**
