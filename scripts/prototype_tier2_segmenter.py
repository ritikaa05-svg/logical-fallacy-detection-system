import re


class Tier2PrototypeSegmenter:
    """
    Isolated prototype of the Tier 2 Discourse Marker Segmenter.
    Uses expanded signatures and boundary detection.
    """

    FALLACY_SIGNATURES_EXTENDED = {
        "ad_hominem": [
            r"\byou\s+(are|re)\s+(a|an|the)?\s*(\w+\s+)?(idiot|liar|shill|loser|hypocrite|bigot)",
            r"\bwho\s+(are|is)\s+you\b",
            r"\byour\s+(opinion|view|argument)\s+doesn't\s+count\b",
            r"\byou\b.{0,30}\b(wrong|bad|idiot|liar|trust|biased)",
        ],
        "tu_quoque": [r"\byou\s+(also|too|did|do)\b", r"\bwhat\s+about\s+you\b", r"\byou're\s+one\s+to\s+talk\b"],
        "straw_man": [
            r"\bso\s+you('re|\s+are)\s+saying\b",
            r"\byou\s+(claim|said|think)\s+that\b",
            r"\bwhat\s+I\s+hear\s+is\b",
            r"\bmisrepresent\b",
            r"\bdistort\b",
        ],
        "false_cause": [
            r"\b(because|since|leads\s+to|results\s+in|causes)\b",
            r"\b(after|following)\s+this\b.{0,20}\btherefore\b",
            r"\blinked\s+to\b",
            r"\bconnected\s+with\b",
        ],
        "appeal_to_emotion": [
            r"\b(children|families|innocent|victims)\b.{0,40}\b(suffer|die|hurt|fear|danger)",
            r"\bthink\s+of\s+the\b",
            r"\bhow\s+can\s+you\s+not\s+feel\b",
        ],
        "red_herring": [
            r"\bwhat\s+about\b",
            r"\bbut\s+(look|consider|think)\s+about\b",
            r"\bthat's\s+all\s+well\s+and\s+good\s+but\b",
            r"\bdivert\b",
            r"\birrelevant\b",
        ],
    }

    def _split_segments(self, text: str) -> list[tuple[str, int, int]]:
        """Splits text into clauses based on discourse markers and punctuation."""
        results = []
        # Split by sentence first
        sentences = re.split(r"(?<=[.!?])\s+", text)
        curr_pos = 0
        for sent in sentences:
            start = text.find(sent, curr_pos)
            if start == -1:
                start = text.find(sent)  # fallback

            # Further split into clauses
            clauses = re.split(r"[,;:]", sent)
            clause_curr = start
            for clause in clauses:
                c_start = text.find(clause, clause_curr)
                if c_start != -1:
                    results.append((clause.strip(), c_start, c_start + len(clause)))
                    clause_curr = c_start + len(clause)
            curr_pos = start + len(sent)
        return results

    def extract_evidence(self, text: str, fallacy: str) -> tuple[str, int, int]:
        """Core extraction logic for prototype."""
        # Special handling for broader fallacies: prefer sentence-level
        if fallacy in ["false_cause", "appeal_to_emotion"]:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            signatures = self.FALLACY_SIGNATURES_EXTENDED.get(fallacy, [])
            for sent in sentences:
                if any(re.search(sig, sent, re.IGNORECASE) for sig in signatures):
                    start = text.find(sent)
                    return sent, start, start + len(sent)
            # Fallback to last sentence
            if sentences:
                last = sentences[-1]
                start = text.find(last)
                return last, start, start + len(last)

        segments = self._split_segments(text)
        if not segments:
            return text, 0, len(text)

        signatures = self.FALLACY_SIGNATURES_EXTENDED.get(fallacy, [])

        # 1. Signature Matching
        for clause, start, end in segments:
            for sig in signatures:
                if re.search(sig, clause, re.IGNORECASE):
                    return clause, start, end

        # 2. Ranking Fallback (Recency + Length)
        # Favor clauses in the second half of the text that aren't too short
        best_idx = 0
        max_score = -1.0
        for i, (clause, start, end) in enumerate(segments):
            score = (i / len(segments)) * 0.5  # Recency
            if 15 < len(clause) < 150:
                score += 1.0  # Optimal length

            if score > max_score:
                max_score = score
                best_idx = i

        return segments[best_idx]


prototype_segmenter = Tier2PrototypeSegmenter()
