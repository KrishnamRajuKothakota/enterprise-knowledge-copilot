"""
Batched RAGAS evaluation with incremental saves and resume.
Usage:
  python scripts/run_eval_batched.py --limit 3    # smoke test
  python scripts/run_eval_batched.py              # full run (overnight)
"""
import sys, os, json, time, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING)

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from ragas.run_config import RunConfig
from langchain_community.llms import Ollama
from langchain_community.embeddings import HuggingFaceEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from src.ekc.db.session import SessionLocal
from src.ekc.retrieval.engine import get_engine
from src.ekc.llm.client import get_llm_client
from src.ekc.llm.prompt import build_prompt
from src.ekc.db.models import UserRole, RagasEvaluation
from src.ekc.core.config import settings

EVAL_PATH = "data/eval/eval_dataset_100.json"
GEN_PATH = "data/eval/ragas_n100_generations.json"
PARTIAL_PATH = "data/eval/ragas_n100_partial.json"
FINAL_PATH = "data/eval/ragas_results_n100.json"
BATCH = 10


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_pairs(limit=None):
    with open(EVAL_PATH) as f:
        pairs = json.load(f)
    return pairs[:limit] if limit else pairs


def generate_answers(pairs):
    """Phase 1: retrieval + answer generation for every pair. Saved incrementally."""
    done = {}
    if os.path.exists(GEN_PATH):
        with open(GEN_PATH) as f:
            done = {r["idx"]: r for r in json.load(f)}
        log(f"Resuming generation: {len(done)} already done")

    db = SessionLocal()
    engine = get_engine(db)
    llm = get_llm_client()
    rows = list(done.values())

    for i, p in enumerate(pairs):
        if i in done:
            continue
        log(f"GEN [{i+1}/{len(pairs)}] {p['question'][:60]}")
        try:
            chunks, _ = engine.hybrid_search(
                p["question"], user_role=UserRole.junior_engineer,
                top_k=5, use_cache=False,
            )
            contexts = [c.content[:400] for c in chunks] or ["(no chunks retrieved)"]
            system_prompt, user_message = build_prompt(
                p["question"], chunks, UserRole.junior_engineer
            )
            answer = llm.generate(system_prompt, user_message, max_tokens=400)
        except Exception as e:
            log(f"  generation failed: {e}")
            contexts, answer = ["(generation error)"], "(generation error)"
        rows.append({
            "idx": i,
            "question": p["question"],
            "ground_truth": p["ground_truth"],
            "category": p.get("category", "unknown"),
            "answer": answer,
            "contexts": contexts,
        })
        if (i + 1) % 5 == 0 or i == len(pairs) - 1:
            with open(GEN_PATH, "w") as f:
                json.dump(sorted(rows, key=lambda r: r["idx"]), f, indent=2)
    db.close()
    rows.sort(key=lambda r: r["idx"])
    with open(GEN_PATH, "w") as f:
        json.dump(rows, f, indent=2)
    log(f"Generation complete: {len(rows)} answers")
    return rows


def evaluate_batches(rows):
    """Phase 2: RAGAS judging in batches of BATCH, partial save after each."""
    scored = []
    if os.path.exists(PARTIAL_PATH):
        with open(PARTIAL_PATH) as f:
            scored = json.load(f)
        log(f"Resuming judging: {len(scored)} rows already scored")
    scored_idx = {r["idx"] for r in scored}
    todo = [r for r in rows if r["idx"] not in scored_idx]

    judge = LangchainLLMWrapper(
        Ollama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=0)
    )
    emb = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    run_config = RunConfig(timeout=300, max_retries=2, max_workers=1)
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    for b in range(0, len(todo), BATCH):
        batch = todo[b:b + BATCH]
        log(f"JUDGE batch {b//BATCH + 1}: rows {batch[0]['idx']}..{batch[-1]['idx']}")
        ds = Dataset.from_dict({
            "question":     [r["question"] for r in batch],
            "answer":       [r["answer"] for r in batch],
            "contexts":     [r["contexts"] for r in batch],
            "ground_truth": [r["ground_truth"] for r in batch],
        })
        try:
            result = evaluate(ds, metrics=metrics, llm=judge, embeddings=emb,
                              run_config=run_config)
            df = result.to_pandas()
            for j, r in enumerate(batch):
                scored.append({
                    "idx": r["idx"],
                    "category": r["category"],
                    "question": r["question"][:80],
                    "faithfulness": _f(df, j, "faithfulness"),
                    "answer_relevancy": _f(df, j, "answer_relevancy"),
                    "context_precision": _f(df, j, "context_precision"),
                    "context_recall": _f(df, j, "context_recall"),
                })
        except Exception as e:
            log(f"  batch failed entirely: {e}")
            for r in batch:
                scored.append({"idx": r["idx"], "category": r["category"],
                               "question": r["question"][:80], "error": str(e)[:120]})
        with open(PARTIAL_PATH, "w") as f:
            json.dump(sorted(scored, key=lambda r: r["idx"]), f, indent=2)
        log(f"  saved partial: {len(scored)} rows total")
    return scored


def _f(df, j, col):
    try:
        v = float(df.iloc[j][col])
        return None if v != v else round(v, 4)  # NaN -> None
    except Exception:
        return None


def aggregate(scored, n_requested):
    def mean(col):
        vals = [r[col] for r in scored if r.get(col) is not None]
        return (round(sum(vals) / len(vals), 4), len(vals)) if vals else (None, 0)

    summary = {"run_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "sample_size_requested": n_requested,
               "rows_scored": len(scored), "metrics": {}, "by_category": {}}
    for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        val, n = mean(m)
        nan_count = sum(1 for r in scored if r.get(m) is None)
        summary["metrics"][m] = {"score": val, "valid_n": n, "failed_n": nan_count}
    for cat in sorted({r["category"] for r in scored}):
        rows_c = [r for r in scored if r["category"] == cat]
        summary["by_category"][cat] = {"n": len(rows_c)}
        for m in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            vals = [r[m] for r in rows_c if r.get(m) is not None]
            summary["by_category"][cat][m] = round(sum(vals)/len(vals), 4) if vals else None

    with open(FINAL_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    log(json.dumps(summary["metrics"], indent=2))
    log(f"Per-category: {json.dumps(summary['by_category'], indent=2)}")

    # Write to DB
    try:
        db = SessionLocal()
        db.add(RagasEvaluation(
            faithfulness=summary["metrics"]["faithfulness"]["score"] or 0,
            context_precision=summary["metrics"]["context_precision"]["score"] or 0,
            answer_relevancy=summary["metrics"]["answer_relevancy"]["score"] or 0,
            context_recall=summary["metrics"]["context_recall"]["score"] or 0,
            sample_size=summary["rows_scored"],
        ))
        db.commit(); db.close()
        log("DB row written to RAGAS_EVALUATION")
    except Exception as e:
        log(f"DB write failed (results still in JSON): {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pairs = load_pairs(args.limit)
    log(f"Evaluating {len(pairs)} pairs from {EVAL_PATH}")
    rows = generate_answers(pairs)
    scored = evaluate_batches(rows)
    aggregate(scored, len(pairs))
    log("DONE")
