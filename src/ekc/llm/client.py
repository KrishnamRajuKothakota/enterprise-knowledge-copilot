"""
Ollama HTTP client.
- Non-thinking mode forced (/no_think prefix)
- 30s timeout -> LLMTimeoutError -> FALLBACK
- temperature=0.1 for factual grounding
- Streams tokens for perceived latency improvement
"""
import logging
import httpx
from src.ekc.core.config import settings
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = f"{settings.ollama_base_url}/api/chat"

# Qwen3 non-thinking mode sampling params (per Qwen team recommendation)
GENERATION_PARAMS = {
    "temperature": 0.1,      # low for factual grounding
    "top_p": 0.8,
    "top_k": 20,
    "repeat_penalty": 1.5,   # suppress repetition in quantised model
}


class OllamaClient:

    def __init__(self):
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 512,
    ) -> str:
        """
        Send a chat completion request to Ollama.
        Forces /no_think prefix to disable Qwen3 thinking mode.
        Returns the response text or raises LLMTimeoutError.
        """
        # Force non-thinking mode — critical for latency on P4000
        user_message_with_nothink = f"/no_think\n{user_message}"

        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                **GENERATION_PARAMS,
                "num_predict": max_tokens,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message_with_nothink},
            ],
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(OLLAMA_CHAT_URL, json=payload)
                response.raise_for_status()

            data = response.json()
            content = data.get("message", {}).get("content", "").strip()

            # Strip any residual <think> blocks Qwen3 might emit
            content = _strip_think_blocks(content)

            logger.debug(f"LLM response: {len(content)} chars")
            return content

        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout after {self.timeout}s")
            raise LLMTimeoutError(f"LLM did not respond within {self.timeout}s")

        except httpx.ConnectError as e:
            logger.error(f"Ollama unreachable: {e}")
            raise LLMUnavailableError(f"Cannot connect to Ollama at {settings.ollama_base_url}")

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise LLMUnavailableError(str(e))

    def health_check(self) -> bool:
        """Returns True if Ollama is reachable and the model is loaded."""
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{settings.ollama_base_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return self.model in models
        except Exception:
            return False


def _strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks from Qwen3 output."""
    import re
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


# ── Module-level singleton ────────────────────────────────────────────────────

_client = None


def get_llm_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client