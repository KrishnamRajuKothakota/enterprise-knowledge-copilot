"""
LLM-as-Judge nightly batch job.
Scores unrated feedback entries using Qwen3-8B as judge.
Writes faithfulness + relevance scores to feedback.llm_judge_score.
Also triggers BM25/FAISS weight rebalancing signal based on feedback patterns.

Usage:
  python scripts/llm_judge_batch.py           # score all unscored feedback
  python scripts/llm_judge_batch.py --dry-run # show what would be scored
  python scripts/llm_judge_batch.py --limit 20 # score max 20 entries
"""
import sys, os, argparse, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from datetime import datetime
from src.ekc.db.session import SessionLocal
from src.ekc.db.models import Feedback, QueryLog, FeedbackRating
from src.ekc.llm.client import get_llm_client
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError


JUDGE_SYSTEM_PROMPT = """You are an objective evaluator of AI assistant responses.
Score the response on two criteria. Reply ONLY in this exact format:
FAITHFULNESS: <0.0-1.0>
RELEVANCE: <0.0-1.0>
EXPLANATION: <one sentence>"""


def score_response(llm, query: str, response: str, chunks_context: str) -> float:
    """Ask Qwen3 to score a query-response pair. Returns combined score 0-1."""
    judge_prompt = f"""QUERY: {query}

RETRIEVED CONTEXT:
{chunks_context[:800]}

RESPONSE GIVEN:
{response[:600]}

Score this response:
- FAITHFULNESS: Does the response only use information from the context? (1.0 = fully grounded, 0.0 = hallucinated)
- RELEVANCE: Does the response directly answer the query? (1.0 = directly answers, 0.0 = off-topic)"""

    try:
        result = llm.generate(JUDGE_SYSTEM_PROMPT, judge_prompt, max_tokens=100)

        # Parse scores
        faithfulness = 0.5
        relevance = 0.5

        for line in result.split('\n'):
            line = line.strip()
            if line.startswith('FAITHFULNESS:'):
                try:
                    faithfulness = float(line.split(':')[1].strip())
                    faithfulness = min(1.0, max(0.0, faithfulness))
                except ValueError:
                    pass
            elif line.startswith('RELEVANCE:'):
                try:
                    relevance = float(line.split(':')[1].strip())
                    relevance = min(1.0, max(0.0, relevance))
                except ValueError:
                    pass

        combined = (faithfulness + relevance) / 2
        logger.debug(f"  Judge scores: faithfulness={faithfulness:.2f} relevance={relevance:.2f} combined={combined:.2f}")
        return combined

    except (LLMTimeoutError, LLMUnavailableError) as e:
        logger.warning(f"LLM unavailable for judging: {e}")
        return None
    except Exception as e:
        logger.warning(f"Judge error: {e}")
        return None


def compute_weight_rebalancing(db) -> dict:
    """
    Analyse feedback patterns to produce weight rebalancing signals.
    Returns suggested BM25/FAISS weight adjustments per query category.
    """
    # Get all scored feedback
    scored = db.query(Feedback, QueryLog).join(
        QueryLog, Feedback.query_id == QueryLog.query_id
    ).filter(
        Feedback.llm_judge_score.isnot(None)
    ).all()

    if len(scored) < 5:
        return {}

    # Categorise by query type
    categories = {
        'sop_procedure': [],
        'ticket_lookup': [],
        'k8s_docker': [],
        'other': [],
    }

    for feedback, query_log in scored:
        q = query_log.query_text.lower()
        score = feedback.llm_judge_score
        # User rating bonus: thumbs up adds 0.1, thumbs down subtracts 0.1
        user_bonus = 0.1 if feedback.rating == FeedbackRating.up else -0.1
        adjusted_score = min(1.0, max(0.0, score + user_bonus))

        if any(w in q for w in ['sop', 'procedure', 'escalat', 'sla', 'onboard', 'leaver']):
            categories['sop_procedure'].append(adjusted_score)
        elif any(w in q for w in ['ticket', 'jira', 'inc-', 'jra-', 'resolve']):
            categories['ticket_lookup'].append(adjusted_score)
        elif any(w in q for w in ['kubernetes', 'kubectl', 'docker', 'k8s', 'pod', 'deploy']):
            categories['k8s_docker'].append(adjusted_score)
        else:
            categories['other'].append(adjusted_score)

    # Compute average scores per category
    signals = {}
    for cat, scores in categories.items():
        if scores:
            avg = sum(scores) / len(scores)
            signals[cat] = {
                'avg_score': round(avg, 3),
                'n': len(scores),
                # If score < 0.6: increase BM25 weight (keyword search better for this category)
                # If score > 0.8: current balance is good
                # If score 0.6-0.8: slight vector increase
                'suggested_bm25_weight': 0.6 if avg < 0.6 else (0.4 if avg > 0.8 else 0.5),
                'suggested_vector_weight': 0.4 if avg < 0.6 else (0.6 if avg > 0.8 else 0.5),
            }

    return signals


def main():
    parser = argparse.ArgumentParser(description='LLM-as-Judge nightly batch')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=50)
    args = parser.parse_args()

    db = SessionLocal()
    llm = get_llm_client()

    try:
        # Find unscored feedback with query logs
        unscored = db.query(Feedback, QueryLog).join(
            QueryLog, Feedback.query_id == QueryLog.query_id
        ).filter(
            Feedback.llm_judge_score.is_(None),
            QueryLog.response_text.isnot(None),
            QueryLog.status != 'fallback',
        ).limit(args.limit).all()

        logger.info(f"Found {len(unscored)} unscored feedback entries")

        if not unscored:
            logger.info("Nothing to score. All feedback already judged.")
            # Still run weight rebalancing on existing data
            signals = compute_weight_rebalancing(db)
            if signals:
                logger.info("Weight rebalancing signals (based on existing scored feedback):")
                for cat, data in signals.items():
                    logger.info(f"  {cat}: avg={data['avg_score']:.3f} n={data['n']} "
                               f"→ BM25={data['suggested_bm25_weight']:.1f} "
                               f"Vector={data['suggested_vector_weight']:.1f}")
            return

        if args.dry_run:
            logger.info("DRY RUN — would score:")
            for fb, ql in unscored:
                logger.info(f"  [{fb.rating}] {ql.query_text[:60]}")
            return

        # Score each entry
        scored_count = 0
        failed_count = 0

        for i, (feedback, query_log) in enumerate(unscored):
            logger.info(f"[{i+1}/{len(unscored)}] Scoring: {query_log.query_text[:55]}...")

            # Build context summary from chunk IDs
            chunk_ids = query_log.retrieved_chunk_ids or []
            context_summary = f"Retrieved {len(chunk_ids)} chunks"
            if chunk_ids:
                from src.ekc.db.models import Chunk as ChunkModel
                chunks = db.query(ChunkModel).filter(
                    ChunkModel.chunk_id.in_(chunk_ids[:3])
                ).all()
                context_summary = "\n".join(
                    f"[{c.section_title}] {c.content[:200]}"
                    for c in chunks
                )

            score = score_response(
                llm,
                query_log.query_text,
                query_log.response_text or "",
                context_summary,
            )

            if score is not None:
                feedback.llm_judge_score = score
                scored_count += 1
                logger.info(f"  → score: {score:.3f} (user rating: {feedback.rating})")
            else:
                failed_count += 1
                logger.warning(f"  → failed to score")

            # Commit every 5 entries
            if (i + 1) % 5 == 0:
                db.commit()
                logger.info(f"  Committed batch of 5")

        db.commit()

        # Run weight rebalancing analysis
        logger.info("")
        logger.info("Computing weight rebalancing signals...")
        signals = compute_weight_rebalancing(db)

        if signals:
            logger.info("Weight rebalancing signals:")
            for cat, data in signals.items():
                logger.info(f"  {cat}: avg_score={data['avg_score']:.3f} n={data['n']} "
                           f"→ suggested BM25={data['suggested_bm25_weight']:.1f} "
                           f"Vector={data['suggested_vector_weight']:.1f}")

            # Save signals to file for the retrieval engine to pick up
            import json
            signals_path = "data/eval/weight_signals.json"
            with open(signals_path, 'w') as f:
                json.dump({
                    'generated_at': datetime.utcnow().isoformat(),
                    'signals': signals,
                }, f, indent=2)
            logger.info(f"Signals saved to {signals_path}")

        logger.info("")
        logger.info("=" * 50)
        logger.info("LLM-AS-JUDGE BATCH COMPLETE")
        logger.info(f"  Scored:  {scored_count}")
        logger.info(f"  Failed:  {failed_count}")
        logger.info(f"  Total:   {len(unscored)}")
        logger.info("=" * 50)

    finally:
        db.close()


if __name__ == "__main__":
    main()
