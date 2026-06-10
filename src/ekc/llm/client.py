"""
Ollama HTTP client.
- thinking disabled via API-level think:false + /no_think prefix (belt & suspenders)
- empty response after think-stripping triggers fallback
- 90s timeout -> LLMTimeoutError -> FALLBACK
- temperature=0.1 for factual grounding
"""
import re
import logging
import httpx
from src.ekc.core.config import settings
from src.ekc.core.exceptions import LLMTimeoutError, LLMUnavailableError

logger = logging.getLogger(__name__)

OLLAMA_CHAT_URL = f"{settings.ollama_base_url}/api/chat"

GENERATION_PARAMS = {
    "temperature": 0.1,
    "top_p": 0.8,
    "top_k": 20,
    "repeat_penalty": 1.0,
}


class OllamaClient:

    def __init__(self):
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 350,
    ) -> str:
        # Belt-and-suspenders: API param + prompt prefix
        user_message_with_nothink = f"/no_think\n{user_message}"

        payload = {
            "model": self.model,
            "stream": False,
            "think": False,           # Ollama API-level thinking disable for Qwen3
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
            raw_content = data.get("message", {}).get("content", "").strip()
            logger.debug(f"LLM raw response length: {len(raw_content)} chars")

            content = _strip_think_blocks(raw_content)

            if not content.strip():
                logger.warning(
                    "LLM returned empty response after stripping think blocks "
                    f"(raw length={len(raw_content)}). Triggering fallback."
                )
                raise LLMTimeoutError("LLM returned empty response")

            logger.debug(f"LLM final response: {len(content)} chars")
            return content

        except httpx.TimeoutException:
            logger.warning(f"Ollama timeout after {self.timeout}s")
            raise LLMTimeoutError(f"LLM did not respond within {self.timeout}s")

        except httpx.ConnectError as e:
            logger.error(f"Ollama unreachable: {e}")
            raise LLMUnavailableError(
                f"Cannot connect to Ollama at {settings.ollama_base_url}"
            )

        except (LLMTimeoutError, LLMUnavailableError):
            raise

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise LLMUnavailableError(str(e))

    def health_check(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{settings.ollama_base_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return self.model in models
        except Exception:
            return False


def _strip_think_blocks(text: str) -> str:
    """
    Remove Qwen3 <think>...</think> blocks.
    If the entire response is a think block, return everything after
    the last </think> tag. If nothing follows, strip blocks and return
    whatever remains (may be empty — caller handles that case).
    """
    if "</think>" not in text:
        # No think blocks — return as-is
        return text.strip()

    # Return everything after the last </think>
    last_end = text.rfind("</think>")
    after = text[last_end + len("</think>"):].strip()
    if after:
        return after

    # Nothing after </think> — strip all blocks and return remainder
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return stripped


_client = None


def get_llm_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client