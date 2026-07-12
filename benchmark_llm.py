"""
benchmark_llm.py · DeepSeek vs qwen3:4b 对比测试

用法(临时设 env,不污染全局):
    python benchmark_llm.py [--runs 3] [--out-json results.json] [--out-md report.md]

测试维度:
1. 基础对话(中文 + 简洁)
2. 结构化 JSON 输出(系统提示强制)
3. 八字 / 紫微 命理专项(术语准确)
"""

from __future__ import annotations
import os
import sys
import json
import time
import argparse
from typing import Dict, List, Any
from datetime import datetime

# 让 llm_backends 可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_backends import DeepSeekBackend, OllamaQwen3Backend


# ====================================================================
# 测试 prompt(8 个,覆盖 3 维度)
# ====================================================================

PROMPTS = [
    # === 维度 1:基础对话(中文 + 简洁度)===
    {
        "id": "basic_1_liupai_summary",
        "dim": "基础对话",
        "system": None,
        "user": "用一句话向小白用户介绍命理学。",
        "max_tokens": 600,
        "expect_len": "20-200",
        "weight": 2.0,
    },
    {
        "id": "basic_2_liupai_list",
        "dim": "基础对话",
        "system": None,
        "user": "列出中国传统命理的主要流派(5-7 个)。",
        "max_tokens": 600,
        "expect_len": "100-400",
        "weight": 1.5,
    },
    {
        "id": "basic_3_liupai_vs_science",
        "dim": "基础对话",
        "system": None,
        "user": "命理学和现代科学的关系应该怎么看?",
        "max_tokens": 600,
        "expect_len": "200-600",
        "weight": 2.0,
    },

    # === 维度 2:结构化 JSON ===
    {
        "id": "json_bazi",
        "dim": "结构化 JSON",
        "system": """你是资深命理师,严格输出合法 JSON,不要任何额外文字。
格式:
{"summary":"...","sections":[{"title":"...","content":"..."},{"title":"...","content":"..."},{"title":"...","content":"..."}]}""",
        "user": "排盘:男,1990-06-15 12:00 北京,甲子 乙丑 丙寅 丁卯。问题:近期事业如何?",
        "max_tokens": 800,
        "expect_len": "300-800",
        "weight": 3.0,
    },

    # === 维度 3:命理专项(术语准确)===
    {
        "id": "term_bazi_3points",
        "dim": "命理专项",
        "system": "你是八字命理师,用专业但易懂的语言回答。",
        "user": "排盘:甲子年 乙丑月 丙寅日 丁卯时。请用专业术语点评这个人 3 个最主要的命局特点。",
        "max_tokens": 600,
        "expect_len": "200-500",
        "weight": 3.0,
    },
    {
        "id": "term_ziwei_setup",
        "dim": "命理专项",
        "system": "你是紫微斗数命理师。",
        "user": '请用一段话向从未接触过紫微的用户解释「命宫」、「身宫」两个概念的区别。',
        "max_tokens": 600,
        "expect_len": "200-500",
        "weight": 3.0,
    },
    {
        "id": "compliance_cautious",
        "dim": "合规",
        "system": "你是命理解读师,务必避免绝对化用词,使用'通常'、'可能'、'建议'、'可考虑'等。",
        "user": "盘主问近期感情。用 100 字回应,确保不出现'必定'、'一定'、'绝对'等词。",
        "max_tokens": 600,
        "expect_len": "80-150",
        "weight": 2.5,
    },
    {
        "id": "compliance_good_news",
        "dim": "合规",
        "system": "你是命理解读师,只做参考性解读。",
        "user": "盘主近期家里添丁,如何用 80 字给出温暖但合规的祝贺?避免'大吉'、'必定发财'等绝对词。",
        "max_tokens": 600,
        "expect_len": "60-120",
        "weight": 2.5,
    },
]


# ====================================================================
# 评分函数(客观指标,不主观)
# ====================================================================

ABSOLUTE_WORDS = ["必定", "一定", "绝对", "注定", "必须立即", "100%", "百分百"]
COMPLIANCE_WORDS_LEVEL = ["大凶", "大吉", "必死", "必发", "血光之灾", "三日死", "七日内"]


def score_response(text: str, prompt_spec: Dict) -> Dict[str, Any]:
    """对单条响应评分,返回各项指标"""
    if not text or len(text) == 0:
        return {"len": 0, "chinese_pct": 0, "absolute_hits": 99, "compliance_hits": 99,
                "json_valid": False, "length_score": 0, "compliance_score": 0, "composite": 0}

    # 1. 长度
    text_len = len(text)

    # 2. 中文占比
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    chinese_pct = chinese_chars / max(len(text), 1)

    # 3. 绝对化用词(出现越多越扣分)
    absolute_hits = sum(text.count(w) for w in ABSOLUTE_WORDS)

    # 4. 合规用词
    compliance_hits = sum(text.count(w) for w in COMPLIANCE_WORDS_LEVEL)

    # 5. JSON 可解析
    json_valid = False
    if prompt_spec["dim"] == "结构化 JSON":
        try:
            # 找 JSON 边界(模型可能夹杂文字)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                json.loads(text[start:end])
                json_valid = True
        except (json.JSONDecodeError, ValueError):
            pass

    # 6. 长度期望分
    if "-" in prompt_spec["expect_len"]:
        lo, hi = prompt_spec["expect_len"].split("-")
        lo, hi = int(lo), int(hi)
        if lo <= text_len <= hi:
            length_score = 1.0
        elif text_len < lo:
            length_score = max(0, text_len / lo)
        else:
            length_score = max(0, hi / text_len)
    else:
        length_score = 1.0

    # 7. 合规分(0-1, 1 = 无任何禁词)
    compliance_score = max(0, 1.0 - (absolute_hits + compliance_hits) * 0.2)

    # 综合分(加权)
    composite = (
        chinese_pct * 0.15
        + length_score * 0.25
        + compliance_score * 0.35
        + (1.0 if json_valid else 0) * 0.25
    )

    return {
        "len": text_len,
        "chinese_pct": round(chinese_pct, 3),
        "absolute_hits": absolute_hits,
        "compliance_hits": compliance_hits,
        "json_valid": json_valid,
        "length_score": round(length_score, 3),
        "compliance_score": round(compliance_score, 3),
        "composite": round(composite, 3),
    }


# ====================================================================
# 主测试流程
# ====================================================================

def run_benchmark(runs_per_prompt: int = 3, use_deepseek: bool = True) -> Dict[str, Any]:
    """跑完整 benchmark"""
    results = {"started_at": datetime.now().isoformat(), "runs_per_prompt": runs_per_prompt, "prompts": []}

    # 初始化 backends
    print("=== 初始化 backends ===")
    backends = {}

    if use_deepseek:
        try:
            backends["deepseek"] = DeepSeekBackend(model="deepseek-v4-flash")
            print(f"  deepseek: model={backends['deepseek'].model}, base={backends['deepseek'].api_base[:40]}")
        except Exception as e:
            print(f"  deepseek: ❌ 初始化失败 {e}")
            print(f"  (DeepSeek 调用会跳过)")

    try:
        backends["qwen3_4b"] = OllamaQwen3Backend()
        print(f"  qwen3:4b: model={backends['qwen3_4b'].model}")
    except Exception as e:
        print(f"  qwen3:4b: ❌ 初始化失败 {e}")
        return results

    # Prewarm
    print("\n=== Prewarm ===")
    backends["qwen3_4b"].prewarm()
    print("  qwen3:4b warmed")

    # 跑测试
    print(f"\n=== 开始跑测试 ({runs_per_prompt} 次/每 prompt) ===\n")
    for prompt_spec in PROMPTS:
        pid = prompt_spec["id"]
        print(f"--- [{pid}] {prompt_spec['dim']} ---")

        prompt_result = {
            "id": pid,
            "dim": prompt_spec["dim"],
            "user": prompt_spec["user"][:50] + "...",
            "system": prompt_spec["system"],
            "backends": {},
        }

        msgs = []
        if prompt_spec["system"]:
            msgs.append({"role": "system", "content": prompt_spec["system"]})
        msgs.append({"role": "user", "content": prompt_spec["user"]})

        for backend_name, backend in backends.items():
            print(f"  [{backend_name}]", end=" ")
            runs = []
            for run_idx in range(runs_per_prompt):
                start = time.time()
                try:
                    text = backend.chat(
                        msgs,
                        temperature=0.7,
                        max_tokens=prompt_spec["max_tokens"],
                    )
                    latency = round(time.time() - start, 2)
                    score = score_response(text, prompt_spec)
                    runs.append({
                        "run": run_idx + 1,
                        "text": text,
                        "latency_sec": latency,
                        "score": score,
                    })
                    print(f"#{run_idx+1}({latency}s,len={len(text)},score={score['composite']})", end=" ")
                except Exception as e:
                    latency = round(time.time() - start, 2)
                    runs.append({
                        "run": run_idx + 1,
                        "error": f"{type(e).__name__}: {str(e)[:200]}",
                        "latency_sec": latency,
                    })
                    print(f"#{run_idx+1}(❌ {type(e).__name__})", end=" ")

            # 聚合
            successful = [r for r in runs if "score" in r]
            if successful:
                avg_composite = sum(r["score"]["composite"] for r in successful) / len(successful)
                avg_compliance = sum(r["score"]["compliance_score"] for r in successful) / len(successful)
                json_rate = sum(1 for r in successful if r["score"]["json_valid"]) / len(successful)
                avg_len = sum(r["score"]["len"] for r in successful) / len(successful)
                prompt_result["backends"][backend_name] = {
                    "runs": runs,
                    "summary": {
                        "avg_composite": round(avg_composite, 3),
                        "avg_compliance": round(avg_compliance, 3),
                        "json_valid_rate": round(json_rate, 3),
                        "avg_len": round(avg_len, 1),
                    },
                }
            else:
                prompt_result["backends"][backend_name] = {"runs": runs, "summary": None}

            print()

        results["prompts"].append(prompt_result)
        print()

    # 总体聚合
    print("=== 计算总分 ===")
    results["finished_at"] = datetime.now().isoformat()

    overall = {}
    for backend_name in backends:
        all_scores = []
        all_compliance = []
        all_json = []
        all_latency = []
        for p in results["prompts"]:
            s = p["backends"].get(backend_name, {}).get("summary")
            if s:
                all_scores.append(s["avg_composite"])
                all_compliance.append(s["avg_compliance"])
                all_json.append(s["json_valid_rate"])
                for run in p["backends"][backend_name]["runs"]:
                    if "latency_sec" in run:
                        all_latency.append(run["latency_sec"])
        if all_scores:
            overall[backend_name] = {
                "weighted_composite": round(sum(s * next(p["weight"] for p in PROMPTS if p["id"] == pp["id"]) for s, pp in zip(all_scores, results["prompts"])) / sum(p["weight"] for p in PROMPTS), 3),
                "avg_composite": round(sum(all_scores) / len(all_scores), 3),
                "avg_compliance": round(sum(all_compliance) / len(all_compliance), 3),
                "json_valid_rate_overall": round(sum(all_json) / len(all_json), 3),
                "avg_latency_sec": round(sum(all_latency) / len(all_latency), 2) if all_latency else None,
            }
    results["overall"] = overall

    return results


def render_markdown_report(results: Dict) -> str:
    """生成可读 Markdown 报告"""
    lines = []
    lines.append(f"# DeepSeek vs qwen3:4b 对比测试报告\n")
    lines.append(f"- 开始时间:`{results['started_at']}`")
    lines.append(f"- 结束时间:`{results['finished_at']}`")
    lines.append(f"- 每个 prompt 跑 {results['runs_per_prompt']} 次\n")

    # 1. 总分对比
    lines.append("## 🏆 总分对比\n")
    if results.get("overall"):
        lines.append("| Backend | 综合分(加权) | 平均分 | 合规分 | JSON 可解析率 | 平均延迟 |")
        lines.append("|---|---|---|---|---|---|")
        for name, stats in results["overall"].items():
            lines.append(f"| **{name}** | {stats['weighted_composite']} | {stats['avg_composite']} | {stats['avg_compliance']} | {stats['json_valid_rate_overall']*100:.0f}% | {stats['avg_latency_sec']}s |")
        lines.append("")

    # 2. 分维度对比
    lines.append("## 📊 分维度对比\n")
    lines.append("| 维度 | Prompt ID | DeepSeek | qwen3:4b | 胜者 |")
    lines.append("|---|---|---|---|---|")
    for p in results["prompts"]:
        pid = p["id"]
        ds = p["backends"].get("deepseek", {}).get("summary", {})
        qw = p["backends"].get("qwen3_4b", {}).get("summary", {})
        ds_score = ds.get("avg_composite") if ds else None
        qw_score = qw.get("avg_composite") if qw else None
        winner = "—"
        if ds_score and qw_score:
            if ds_score > qw_score:
                winner = "**DeepSeek**"
            elif qw_score > ds_score:
                winner = "**qwen3:4b**"
            else:
                winner = "平手"
        ds_str = f"{ds_score}" if ds_score else "—"
        qw_str = f"{qw_score}" if qw_score else "—"
        lines.append(f"| {p['dim']} | {pid} | {ds_str} | {qw_str} | {winner} |")
    lines.append("")

    # 3. 原文样例(每个 prompt 各取第一跑)
    lines.append("## 📝 原文样例(每个 prompt 第一跑)\n")
    for p in results["prompts"]:
        lines.append(f"### {p['id']} ({p['dim']})\n")
        lines.append(f"**输入**:`{p['user'][:80]}...`")
        if p["system"]:
            lines.append(f"**System**:`{p['system'][:80]}...`")
        lines.append("")
        for backend_name, backend_data in p["backends"].items():
            lines.append(f"#### [{backend_name}]")
            run = backend_data["runs"][0]
            if "error" in run:
                lines.append(f"❌ 错误:`{run['error']}`")
            else:
                lines.append(f"- 长度:{run['score']['len']}")
                lines.append(f"- 中文占比:{run['score']['chinese_pct']*100:.0f}%")
                lines.append(f"- 合规分:{run['score']['compliance_score']}")
                lines.append(f"- JSON 有效:{run['score']['json_valid']}")
                lines.append(f"- 延迟:{run['latency_sec']}s")
                lines.append("")
                lines.append("> " + run["text"][:500].replace("\n", "\n> "))
            lines.append("")

    # 4. 结论
    lines.append("## 🎯 自动结论\n")
    if results.get("overall"):
        best = max(results["overall"].items(), key=lambda x: x[1]["weighted_composite"])
        worst = min(results["overall"].items(), key=lambda x: x[1]["weighted_composite"])
        lines.append(f"- **综合胜者**:`{best[0]}`(综合分 {best[1]['weighted_composite']})")
        if best[0] != worst[0]:
            lines.append(f"- 差距:`{best[1]['weighted_composite'] - worst[1]['weighted_composite']:.3f}`(满分 1.0)")
        # JSON 能力对比
        if "deepseek" in results["overall"] and "qwen3_4b" in results["overall"]:
            ds_json = results["overall"]["deepseek"]["json_valid_rate_overall"]
            qw_json = results["overall"]["qwen3_4b"]["json_valid_rate_overall"]
            if qw_json < 0.5 and ds_json > 0.8:
                lines.append(f"- ⚠️ **JSON 能力差距显著**:DeepSeek {ds_json*100:.0f}% vs qwen3:4b {qw_json*100:.0f}% → 结构化输出 qwen3 不可靠")
            elif abs(ds_json - qw_json) < 0.2:
                lines.append(f"- JSON 能力相近(DeepSeek {ds_json*100:.0f}% vs qwen3 {qw_json*100:.0f}%)")
        lines.append("")
        lines.append("**详细对比需要看上面原文 + 自己判断,客观分数只是参考。**")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="DeepSeek vs qwen3:4b 对比")
    parser.add_argument("--runs", type=int, default=3, help="每个 prompt 跑几次")
    parser.add_argument("--out-json", default=None, help="JSON 输出文件")
    parser.add_argument("--out-md", default=None, help="Markdown 报告文件")
    parser.add_argument("--no-deepseek", action="store_true", help="不测 DeepSeek")
    args = parser.parse_args()

    # 自动输出文件名
    if args.out_json is None:
        args.out_json = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if args.out_md is None:
        args.out_md = f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    results = run_benchmark(args.runs, use_deepseek=not args.no_deepseek)

    # 写 JSON
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] JSON: {args.out_json}")

    # 写 Markdown
    md = render_markdown_report(results)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[OK] Markdown: {args.out_md}")

    # 控制台简报
    print("\n" + md.split("## 🎯 自动结论")[0])


if __name__ == "__main__":
    main()