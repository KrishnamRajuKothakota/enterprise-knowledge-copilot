"""
RAGAS evaluation runner — configured for local Ollama on P4000.
Uses RunConfig to set long timeouts and low concurrency.
Usage: python scripts/run_eval.py
"""
import sys, os, json, logging
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

EVAL_PATH = "data/eval/eval_dataset.json"
SAMPLE_SIZE = 15


def load_eval_dataset(path, n):
    with open(path) as f:
        data = json.load(f)
    pairs = data if isinstance(data, list) else data.get("questions", [])
    return pairs[:n]


def run_retrieval_and_generation(pairs):
    db = SessionLocal()
    engine = get_engine(db)
    llm = get_llm_client()

    questions, answers, contexts, ground_truths = [], [], [], []

    for i, pair in enumerate(pairs):
        question = pair.get("question", "")
        ground_truth = pair.get("ground_truth", "")
        if not question:
            continue

        print(f"  [{i+1}/{len(pairs)}] {question[:60]}...")

        try:
            chunks, _ = engine.hybrid_search(
                question,
                user_role=UserRole.junior_engineer,
                top_k=5,          # was 3
                use_cache=False,
            )

            if not chunks:
                contexts.append(["No context retrieved."])
                answers.append("I don't have enough information to answer this reliably.")
                questions.append(question)
                ground_truths.append(ground_truth)
                continue

            system_prompt, user_message = build_prompt(
                question, chunks, UserRole.junior_engineer
            )
            answer = llm.generate(system_prompt, user_message, max_tokens=400)  # was 250

            contexts.append([c.content[:400] for c in chunks])
            answers.append(answer)
            questions.append(question)
            ground_truths.append(ground_truth)

        except Exception as e:
            print(f"    skipping: {e}")
            continue

    db.close()
    return {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    }


def main():
    print(f"Loading {SAMPLE_SIZE} Q&A pairs from {EVAL_PATH}")
    pairs = load_eval_dataset(EVAL_PATH, SAMPLE_SIZE)
    print(f"Loaded {len(pairs)} pairs")

    print("\nRunning retrieval + generation...")
    data = run_retrieval_and_generation(pairs)
    print(f"Generated {len(data['question'])} answers\n")

    if len(data['question']) == 0:
        print("ERROR: no answers generated")
        return

    # Configure local LLM judge with generous timeouts
    print("Configuring RAGAS with local Ollama (this takes 20-40 minutes)...")

    local_llm = Ollama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        temperature=0.1,
    )
    local_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    ragas_llm = LangchainLLMWrapper(local_llm)
    ragas_embeddings = LangchainEmbeddingsWrapper(local_embeddings)

    # RunConfig: long timeout, single thread — avoids timeout storm on P4000
    run_config = RunConfig(
        timeout=300,        # 5 min — Qwen3 on P4000 sometimes needs it
        max_retries=3,
        max_wait=60,
        max_workers=1,
    )

    # Assign LLM to each metric explicitly
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    for m in metrics:
        m.llm = ragas_llm
    answer_relevancy.embeddings = ragas_embeddings

    dataset = Dataset.from_dict(data)

    print("Running evaluation...")
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_embeddings,
        run_config=run_config,
        raise_exceptions=False,
    )

    print()
    print("=" * 52)
    print("RAGAS EVALUATION RESULTS")
    print("=" * 52)
    print(f"  Sample size:       {len(data['question'])}")

    scores = {}
    for key in ["faithfulness", "context_precision", "answer_relevancy", "context_recall"]:
        val = result.get(key, float("nan"))
        scores[key] = val if val == val else 0.0  # nan check

    targets = {
        "faithfulness": 0.88,
        "context_precision": 0.85,
        "answer_relevancy": 0.85,
        "context_recall": 0.80,
    }
    for k, v in scores.items():
        target = targets[k]
        status = "✅" if v >= target else "⚠️"
        print(f"  {k:22s} {v:.3f}  {status} (target >{target})")
    print("=" * 52)

    # Save to DB
    db = SessionLocal()
    import uuid
    from datetime import datetime
    db.add(RagasEvaluation(
        eval_id=str(uuid.uuid4()),
        run_date=datetime.utcnow(),
        faithfulness=scores["faithfulness"],
        context_precision=scores["context_precision"],
        answer_relevancy=scores["answer_relevancy"],
        context_recall=scores["context_recall"],
        sample_size=len(data["question"]),
        notes=f"Local Qwen3-8B judge, n={len(data['question'])}, RunConfig timeout=180",
    ))
    db.commit()
    db.close()
    print("Saved to database.")

    # Save JSON
    os.makedirs("data/eval", exist_ok=True)
    report = {
        "run_date": datetime.utcnow().isoformat(),
        "sample_size": len(data["question"]),
        **scores,
        "targets": targets,
    }
    with open("data/eval/ragas_results.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Saved to data/eval/ragas_results.json")


if __name__ == "__main__":
    main()