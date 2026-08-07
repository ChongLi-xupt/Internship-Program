"""
LLM / Embedding 配置连通性自检。

用法:
    cd backend
    python -m scripts.check_llm

它会依次验证:
  1. 配置项本身是否自洽（最常见错误：DeepSeek 没配独立 embedding）
  2. 对话模型能否真实调通
  3. 对话模型能否稳定输出 JSON（问数链路强依赖）
  4. 向量化模型能否调通 + 实际维度 == EMBEDDING_DIMENSIONS + 是否归一化
     （维度不一致会导致写 Qdrant 直接失败）
  5. 语义检索是否真的有效——相关文档得分必须高于无关文档
     （维度对但指令前缀配错时，检索会静默失效，只测维度查不出来）

任何一步失败都会打印可执行的修复建议，而不是抛原始堆栈。
"""

import asyncio
import math
import sys
import time

from app.config import settings
from app.llm.base import get_llm, get_embedding_provider, validate_llm_config

OK = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"


def _hdr(title: str) -> None:
    print(f"\n{'─' * 62}\n{title}\n{'─' * 62}")


def _mask(secret: str) -> str:
    if not secret:
        return "(空)"
    return f"{secret[:6]}...{secret[-4:]}" if len(secret) > 12 else "***"


def _is_local_hf() -> bool:
    return settings.embedding_provider.lower() in ("huggingface", "hf", "local")


async def check_config() -> bool:
    _hdr("1. 配置自检")
    print(f"  LLM_PROVIDER        = {settings.llm_provider}")
    if settings.llm_provider.lower() == "deepseek":
        print(f"  DEEPSEEK_MODEL      = {settings.deepseek_model}")
        print(f"  DEEPSEEK_BASE_URL   = {settings.deepseek_base_url}")
        print(f"  DEEPSEEK_API_KEY    = {_mask(settings.deepseek_api_key)}")
    print(f"  EMBEDDING_PROVIDER  = {settings.embedding_provider}")

    if _is_local_hf():
        print(f"  HF_EMBEDDING_MODEL  = {settings.hf_embedding_model or settings.embedding_model}")
        print(f"  HF_EMBEDDING_DEVICE = {settings.hf_embedding_device or '(自动检测)'}")
        print(f"  HF_..._NORMALIZE    = {settings.hf_embedding_normalize}")
        print(f"  HF_..._OFFLINE      = {settings.hf_embedding_offline}")
        instr = settings.hf_embedding_query_instruction
        print(f"  HF_..._QUERY_INSTR  = {instr[:24] + '…' if len(instr) > 24 else (instr or '(无)')}")
    else:
        print(f"  EMBEDDING_MODEL     = {settings.embedding_model}")
        print(
            f"  EMBEDDING_BASE_URL  = "
            f"{settings.embedding_base_url or settings.openai_base_url + '  (回退自 OPENAI_BASE_URL)'}"
        )
        print(
            f"  EMBEDDING_API_KEY   = "
            f"{_mask(settings.embedding_api_key or settings.openai_api_key)}"
        )
    print(f"  EMBEDDING_DIMENSIONS= {settings.embedding_dimensions}")

    problems = validate_llm_config()
    if problems:
        for p in problems:
            print(f"\n  {FAIL} {p}")
        return False
    print(f"\n  {OK} 配置自洽")
    return True


async def check_chat() -> bool:
    _hdr("2. 对话模型连通性")
    try:
        llm = get_llm()
        resp = await llm.ainvoke("只回答两个字：正常")
        text = (resp.content or "").strip()
        print(f"  {OK} 调用成功，返回: {text[:60]!r}")
        return True
    except Exception as e:
        print(f"  {FAIL} 调用失败: {type(e).__name__}: {e}")
        print("\n  排查方向:")
        print("    · 401 / Authentication → API Key 错误或已失效")
        print("    · 404 Not Found        → base_url 写错（DeepSeek 应为 https://api.deepseek.com/v1）")
        print("    · Model not exist      → 模型名写错（deepseek-chat / deepseek-reasoner）")
        print("    · 402 / Insufficient   → DeepSeek 账户余额不足")
        return False


async def check_json_mode() -> bool:
    _hdr("3. JSON 结构化输出（问数链路依赖）")
    try:
        llm = get_llm(json_mode=True) if settings.llm_provider.lower() == "deepseek" else get_llm()
        resp = await llm.ainvoke(
            'Return a json object with exactly one key "status" whose value is "ok".'
        )
        raw = (resp.content or "").strip()
        import json

        cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)
        print(f"  {OK} JSON 解析成功: {data}")
        return True
    except Exception as e:
        print(f"  {WARN} JSON 模式异常: {type(e).__name__}: {e}")
        print("    问数的 nl_understand / sql_compile 节点依赖 JSON 输出，")
        print("    若此处失败，这两个节点会频繁解析报错。")
        return False


async def check_embedding() -> bool:
    _hdr("4. 向量化模型连通性 + 维度校验")
    if _is_local_hf():
        print("  本地模型首次加载需要几十秒（要把权重读进内存），请稍候…")
    try:
        t0 = time.time()
        provider = get_embedding_provider()
        vec = await provider.embed_query("连通性测试")
        elapsed = time.time() - t0
        actual = len(vec)
        print(f"  {OK} 调用成功，实际返回维度 = {actual}   (耗时 {elapsed:.1f}s)")

        if actual != settings.embedding_dimensions:
            print(f"\n  {FAIL} 维度不匹配！配置值 {settings.embedding_dimensions} ≠ 实际 {actual}")
            print(f"    修复: 把 .env 里 EMBEDDING_DIMENSIONS 改为 {actual}")
            print("    注意: 若 Qdrant 已建过 collection，改维度后必须删除重建，")
            print("          否则写入会报 vector dimension error。")
            return False

        print(f"  {OK} 维度与配置一致")

        # 归一化检查：向量库按余弦相似度检索时，未归一化会让打分失真
        norm = math.sqrt(sum(x * x for x in vec))
        if abs(norm - 1.0) < 0.01:
            print(f"  {OK} 向量已归一化 (L2={norm:.4f})")
        else:
            print(f"  {WARN} 向量未归一化 (L2={norm:.4f})，余弦检索打分可能失真")

        return True
    except Exception as e:
        print(f"  {FAIL} 调用失败: {type(e).__name__}: {e}")
        print("\n  排查方向:")
        if _is_local_hf():
            print("    · No module named 'sentence_transformers'")
            print("        → pip install sentence-transformers")
            print("    · 找不到模型 / offline 报错")
            print("        → 模型不在本地缓存里。先下载:")
            print("          huggingface-cli download BAAI/bge-large-zh-v1.5")
            print("        → 或把 HF_EMBEDDING_MODEL 改成模型目录的绝对路径")
            print("    · CUDA / device 报错")
            print("        → 显存不足或 torch 是 CPU 版，设 HF_EMBEDDING_DEVICE=cpu")
        elif "deepseek" in (settings.embedding_base_url or settings.openai_base_url).lower():
            print("    · 你把 embedding 指向了 DeepSeek —— DeepSeek 没有 embedding 接口。")
            print("      改用本地模型 / 硅基流动 / 百炼，见 .env.example 方案 A~E。")
        else:
            print("    · 404          → base_url 或模型名不对")
            print("    · 401          → EMBEDDING_API_KEY 无效（注意它和对话 Key 可能不是同一个）")
            print("    · dimensions   → 部分服务不支持该参数，设 EMBEDDING_SEND_DIMENSIONS=false")
        return False


async def check_retrieval_sanity() -> bool:
    """
    语义检索有效性抽查。

    只验维度是不够的——模型加载错、指令前缀配错、归一化关掉，
    都会让维度正确但检索质量崩掉。这里用一组同义/异义句做排序验证。
    """
    _hdr("5. 语义检索有效性抽查")
    try:
        provider = get_embedding_provider()
        query = "公司去年的营业收入是多少"
        related = "本年度营业总收入较上年同期增长 12%"
        unrelated = "员工年假申请需提前三个工作日提交"

        qv = await provider.embed_query(query)
        dv = await provider.embed_documents([related, unrelated])

        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(x * x for x in b))
            return dot / (na * nb) if na and nb else 0.0

        s_rel, s_unrel = cos(qv, dv[0]), cos(qv, dv[1])
        print(f"  查询   : {query}")
        print(f"  相关文档: {s_rel:.4f}  ← {related}")
        print(f"  无关文档: {s_unrel:.4f}  ← {unrelated}")

        if s_rel > s_unrel:
            print(f"\n  {OK} 相关文档排序在前，语义检索正常 (差值 {s_rel - s_unrel:.4f})")
            if s_rel - s_unrel < 0.05:
                print(f"  {WARN} 区分度偏低，检索质量可能不稳定。中文场景建议换 BGE 系列模型。")
            return True

        print(f"\n  {FAIL} 无关文档打分更高——检索会失效！")
        print("    常见原因:")
        print("      · 用了 BGE 模型却没配 HF_EMBEDDING_QUERY_INSTRUCTION")
        print("      · 用了非 BGE 模型却保留了 BGE 的指令前缀（应留空）")
        print("      · 模型本身不支持中文（如英文单语模型）")
        return False
    except Exception as e:
        print(f"  {WARN} 抽查跳过: {type(e).__name__}: {e}")
        return True  # 非致命


async def main() -> int:
    print("\n🔍 LLM / Embedding 配置自检")

    results = [await check_config()]
    if results[0]:
        results.append(await check_chat())
        if results[-1]:
            await check_json_mode()  # 非致命，不计入结果
        emb_ok = await check_embedding()
        results.append(emb_ok)
        if emb_ok:
            results.append(await check_retrieval_sanity())

    _hdr("结果")
    if all(results):
        print(f"  {OK} 全部通过，可以启动服务：uvicorn app.main:app --reload\n")
        return 0
    print(f"  {FAIL} 存在问题，请按上方提示修复后重试\n")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
