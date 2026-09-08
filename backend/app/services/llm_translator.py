import logging
import re
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)


class LRUCache:
    """Thread-safe LRU cache with a fixed max size."""

    def __init__(self, maxsize=1024):
        self._cache = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.Lock()

    def __contains__(self, key):
        with self._lock:
            return key in self._cache

    def __getitem__(self, key):
        with self._lock:
            self._cache.move_to_end(key)
            return self._cache[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)


# Cache for LLM translation results (thread-safe LRU, max 1024 entries)
_translation_cache = LRUCache(maxsize=1024)

SMT_PROMPT_TEMPLATE = """Task: Translate a natural language argument into SMT-LIBv2 for formal verification.
The goal is to check for VALIDITY. We do this by asserting all premises are TRUE and the conclusion is FALSE.
If Z3 returns 'unsat', the argument is VALID. If 'sat', it is INVALID.

Rules:
1. Use (declare-sort Entity 0) for objects.
2. Use (declare-fun ...) for predicates.
3. Use (declare-const ...) for individuals.
4. Translate "All A are B" as (forall ((x Entity)) (=> (isA x) (isB x)))
5. Translate "If P then Q" as (=> P Q)
6. ALWAYS end with (check-sat).
7. THE LAST ASSERTION MUST BE THE NEGATION OF THE CONCLUSION: (assert (not <conclusion>))

Example 1:
Input: 'All humans are mortal. Socrates is human. Therefore, Socrates is mortal.'
Output:
(declare-sort Entity 0)
(declare-fun isHuman (Entity) Bool)
(declare-fun isMortal (Entity) Bool)
(declare-const socrates Entity)
(assert (forall ((x Entity)) (=> (isHuman x) (isMortal x))))
(assert (isHuman socrates))
(assert (not (isMortal socrates)))
(check-sat)

Example 2:
Input: 'If it rains, the ground is wet. The ground is wet. Therefore, it rained.'
Output:
(declare-const rain Bool)
(declare-const groundWet Bool)
(assert (=> rain groundWet))
(assert groundWet)
(assert (not rain))
(check-sat)

Now translate: {text}
Output SMT-LIBv2:"""


def _extract_smt_code(llm_output: str) -> str:
    """Extract SMT-LIBv2 code block from LLM response."""
    # Look for code blocks first
    code_match = re.search(r"```(?:smt2|smt)?\s*(.*?)\s*```", llm_output, re.DOTALL | re.IGNORECASE)
    if code_match:
        return code_match.group(1).strip()

    # Otherwise, look for common SMT commands
    if "(check-sat)" in llm_output:
        # Try to find the start of declarations
        start_match = re.search(r"\((?:declare|assert)", llm_output)
        if start_match:
            end_pos = llm_output.rfind("(check-sat)") + len("(check-sat)")
            return llm_output[start_match.start() : end_pos].strip()

    return llm_output.strip()


def _validate_smt_syntax(smt_code: str) -> bool:
    """Basic validation of SMT-LIBv2 syntax (balanced parentheses)."""
    if not smt_code or "(check-sat)" not in smt_code:
        return False

    # Check for balanced parentheses
    stack = []
    for char in smt_code:
        if char == "(":
            stack.append(char)
        elif char == ")":
            if not stack:
                return False
            stack.pop()
    return len(stack) == 0


async def llm_to_smt(text: str) -> tuple[str, float]:
    """
    Translate natural language to SMT-LIBv2 using LLM.
    Uses centralized llm_synthesis_service for tiered generation.
    Returns: (smt_script, confidence_score)
    """
    if text in _translation_cache:
        return _translation_cache[text]

    prompt = SMT_PROMPT_TEMPLATE.format(text=text)
    smt_script = ""
    confidence = 0.0

    try:
        from backend.app.services.llm_service import llm_synthesis_service

        # Use centralized fallback logic with deterministic settings for translation
        raw_output = await llm_synthesis_service._generate_with_fallback(
            prompt, max_new_tokens=512, temperature=0.1, do_sample=False
        )

        if raw_output:
            smt_script = _extract_smt_code(raw_output)
            if _validate_smt_syntax(smt_script):
                confidence = 0.90  # High confidence if syntax is valid
            else:
                confidence = 0.3
                logger.warning("LLM produced invalid SMT syntax.")

    except Exception as e:
        logger.warning(f"LLM SMT translation failed: {e}")

    _translation_cache[text] = (smt_script, confidence)
    return smt_script, confidence
