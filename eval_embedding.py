#!/usr/bin/env python
"""
嵌入模型评估脚本（通义 embedding）

用法：
  python eval_embedding.py
  python eval_embedding.py --samples 50 --query-len 300

需在 config 或 .env 中配置 DASHSCOPE_API_KEY（通义 embedding）
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="嵌入模型综合评估")
    parser.add_argument("--samples", type=int, default=50, help="最大采样文档数")
    parser.add_argument("--query-len", type=int, default=300, help="模拟查询长度（字符）")
    parser.add_argument("--top-k", type=str, default="1,3,5,8,10", help="Recall@k 的 k 列表")
    parser.add_argument("--mode", choices=["prefix", "suffix", "middle"], default="prefix",
                        help="查询模式: prefix=前缀(易), suffix=后缀(严), middle=中间(严)")
    args = parser.parse_args()

    top_k_list = [int(x.strip()) for x in args.top_k.split(",") if x.strip()]
    if not top_k_list:
        top_k_list = [1, 3, 5, 8, 10]

    from knowledge_base import FAISSKnowledgeBase

    kb = FAISSKnowledgeBase()

    result = kb.evaluate_embedding_model(
        top_k_list=top_k_list,
        query_len=args.query_len,
        max_samples=args.samples,
        query_mode=args.mode,
    )

    print("=" * 60)
    print("嵌入模型评估结果")
    print("=" * 60)
    print(f"模型: {result['model']}")
    print(f"维度: {result['dimension']}")
    print(f"参与评估文档数: {result['total']}")
    print(f"查询长度: {result.get('query_len', 300)} 字符")
    print(f"查询模式: {result.get('query_mode', 'prefix')} ({result['logic']})")
    print()
    print("指标:")
    print("  Recall@k:")
    for k in top_k_list:
        r = result["recall_at_k"].get(k, 0)
        c = result["recalled_at_k"].get(k, 0)
        print(f"    Recall@{k}: {r*100:.2f}% ({c}/{result['total']})")
    print("  Precision@k:")
    for k in top_k_list:
        p = result.get("precision_at_k", {}).get(k, 0)
        print(f"    Precision@{k}: {p*100:.2f}%")
    print("  NDCG@k:")
    for k in top_k_list:
        ndcg = result.get("ndcg_at_k", {}).get(k, 0)
        print(f"    NDCG@{k}: {ndcg:.4f}")
    print(f"  Hit@1:    {result['hit_at_1']*100:.2f}%")
    print(f"  MRR:     {result['mrr']:.4f}")
    print(f"  MAP:     {result.get('map', 0):.4f}")
    print(f"  Mean Rank: {result['mean_rank']}")
    print()
    print("检测逻辑:", result["logic"])
    print("=" * 60)


if __name__ == "__main__":
    main()
