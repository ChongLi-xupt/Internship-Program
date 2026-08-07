"""
本地 embedding 接入的端到端验证（临时探针，可删）。

绕开 .env / 数据库依赖，直接给 app.llm.base 注入一份内存配置，
真实加载本地模型跑完整链路。
"""
import asyncio
import sys
import time
import types
from types import SimpleNamespace

# --- 注入内存配置，避免依赖 .env 和数据库 ---
S = SimpleNamespace(
    llm_provider="deepseek",
    deepseek_api_key="sk-dummy",
    deepseek_base_url="https://api.deepseek.com/v1",
    deepseek_model="deepseek-chat",
    deepseek_light_model="deepseek-chat",
    openai_api_key="",
    openai_base_url="https://api.openai.com/v1",
    openai_model="gpt-4o-mini",
    openai_light_model="gpt-4o-mini",
    anthropic_api_key="",
    anthropic_model="",
    ollama_base_url="http://localhost:11434",
    ollama_model="qwen2.5:14b",
    embedding_provider="huggingface",
    embedding_model="text-embedding-3-small",
    embedding_api_key="",
    embedding_base_url="",
    embedding_send_dimensions=False,
    embedding_batch_size=16,
    embedding_dimensions=1024,
    hf_embedding_model="BAAI/bge-large-zh-v1.5",
    hf_embedding_device="cpu",
    hf_embedding_normalize=True,
    hf_embedding_query_instruction="为这个句子生成表示以用于检索相关文章：",
    hf_embedding_offline=True,
    hf_embedding_torch_threads=4,
)
cfg = types.ModuleType("app.config")
cfg.settings = S
sys.modules["app.config"] = cfg

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("llmbase", "app/llm/base.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(f"  {PASS if cond else FAIL}  {name}" + (f"   {detail}" if detail else ""))


def cos(a, b):
    return sum(x * y for x, y in zip(a, b))  # 已归一化，点积即余弦


async def main():
    print("\n" + "=" * 68)
    print("本地 HuggingFace Embedding 接入验证")
    print("=" * 68)

    # 1. 配置校验分支
    print("\n[1] validate_llm_config() 分支")
    probs = M.validate_llm_config()
    check("正确配置放行", not probs, str(probs) if probs else "")

    S.embedding_dimensions = 1536
    check("拦截：本地模型却留着 1536 维", any("1536" in p for p in M.validate_llm_config()))
    S.embedding_dimensions = 1024

    S.embedding_send_dimensions = True
    check("拦截：本地模型却开着 SEND_DIMENSIONS",
          any("SEND_DIMENSIONS" in p for p in M.validate_llm_config()))
    S.embedding_send_dimensions = False

    S.hf_embedding_model = "text-embedding-3-small"
    check("拦截：本地 provider 配了 OpenAI 模型名",
          any("no local weights" in p for p in M.validate_llm_config()))
    S.hf_embedding_model = "BAAI/bge-large-zh-v1.5"

    # 2. 真实加载
    print("\n[2] 模型加载（真实，离线）")
    t = time.time()
    provider = M.get_embedding_provider()
    check("provider 解析为 HuggingFace",
          type(provider).__name__ == "HuggingFaceEmbeddingProvider",
          type(provider).__name__)
    dim = M.HuggingFaceEmbeddingProvider.probe_dimensions()
    load_t = time.time() - t
    check("探测维度 == 1024", dim == 1024, f"实际 {dim}，加载耗时 {load_t:.1f}s")

    # 3. 单例：第二次不得重新加载
    t = time.time()
    M.HuggingFaceEmbeddingProvider.probe_dimensions()
    second = time.time() - t
    check("模型单例缓存生效", second < 0.05, f"二次调用 {second*1000:.1f}ms")

    # 4. async 接口
    print("\n[3] 异步接口 + 维度")
    qv = await provider.embed_query("公司去年的营业收入是多少")
    check("embed_query 返回 1024 维", len(qv) == 1024, f"实际 {len(qv)}")
    dv = await provider.embed_documents(["文档一", "文档二", "文档三"])
    check("embed_documents 批量 3 条", len(dv) == 3 and len(dv[0]) == 1024)

    norm = sum(x * x for x in qv) ** 0.5
    check("向量已归一化", abs(norm - 1.0) < 0.01, f"L2={norm:.6f}")

    # 5. BGE 指令前缀必须只作用于 query 侧
    print("\n[4] BGE 查询指令前缀（非对称性）")
    text = "营业收入统计口径说明"
    as_query = await provider.embed_query(text)
    as_doc = (await provider.embed_documents([text]))[0]
    sim = cos(as_query, as_doc)
    check("同一文本 query/doc 编码不同（前缀已生效）", sim < 0.999, f"cos={sim:.5f}")

    old = S.hf_embedding_query_instruction
    S.hf_embedding_query_instruction = ""
    plain = await provider.embed_query(text)
    check("关掉前缀后 query==doc", cos(plain, as_doc) > 0.9999, f"cos={cos(plain, as_doc):.6f}")
    S.hf_embedding_query_instruction = old

    # 6. 真实检索排序
    print("\n[5] 语义检索有效性")
    q = await provider.embed_query("公司去年第三季度营业收入多少")
    docs = [
        "2024年第三季度营业总收入为 3.2 亿元，同比增长 12%",
        "员工年假申请需提前三个工作日在 OA 系统提交",
        "第三季度销售费用率下降至 8.4%",
    ]
    dvs = await provider.embed_documents(docs)
    scored = sorted(zip([cos(q, d) for d in dvs], docs), reverse=True)
    for s, d in scored:
        print(f"        {s:.4f}  {d[:38]}")
    check("营收文档排第一", scored[0][1] is docs[0])
    check("与无关文档拉开差距", scored[0][0] - min(s for s, _ in scored) > 0.1,
          f"差值 {scored[0][0] - min(s for s, _ in scored):.4f}")

    # 7. 吞吐
    print("\n[6] CPU 吞吐（batch=16）")
    t = time.time()
    await provider.embed_documents([f"这是第 {i} 条测试文本，用于评估批量向量化性能。" for i in range(32)])
    dt = time.time() - t
    print(f"        32 条 / {dt:.2f}s  =  {32/dt:.1f} 条/秒")

    print("\n" + "=" * 68)
    ok = all(results)
    print(f"  {'全部通过' if ok else '存在失败项'}：{sum(results)}/{len(results)}")
    print("=" * 68 + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
