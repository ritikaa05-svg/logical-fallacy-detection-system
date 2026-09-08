import json
import random

# --- Vocabulary and Domains ---
DOMAINS = {
    "Legal": ["statute", "precedent", "clause", "defendant", "plaintiff", "jurisdiction", "liability"],
    "Science": ["hypothesis", "variable", "empirical", "correlation", "entropy", "spectrum", "protocol"],
    "Medicine": ["diagnosis", "prognosis", "symptom", "efficacy", "contraindication", "dosage", "pathogen"],
    "Programming": ["function", "recursion", "asynchronous", "deployment", "dependency", "latency", "schema"],
    "Engineering": ["structural", "load-bearing", "torque", "tolerance", "redundancy", "aerodynamics", "prototype"],
    "Politics": ["policy", "constituency", "legislation", "diplomacy", "sanction", "referendum", "partisan"],
    "Education": ["pedagogy", "curriculum", "assessment", "literacy", "cognition", "standardized", "didactic"],
    "Philosophy": ["ontology", "epistemology", "dialectic", "axiom", "categorical", "solipsism", "ethics"],
}

STYLES = [
    "Formal report: ",
    "During the debate, it was noted that ",
    "In a casual conversation: ",
    "According to the technical manual, ",
    "The court found that ",
    "Research indicates that ",
    "Wait, let's consider ",
    "I disagree, because ",
    "On the other hand, ",
    "Strictly speaking, ",
]

# --- Templates ---


def gen_valid_deductive():
    """Modus Ponens, Modus Tollens, Syllogisms."""
    domain = random.choice(list(DOMAINS.keys()))
    v = DOMAINS[domain]
    random.shuffle(v)

    types = [
        f"If the {v[0]} is active, then the {v[1]} will increase. The {v[0]} is active. Therefore, the {v[1]} will increase.",  # MP
        f"Whenever a {v[0]} occurs, a {v[1]} must follow. A {v[0]} occurred. So, a {v[1]} followed.",  # MP Var
        f"If the {v[0]} was valid, the {v[1]} would be detectable. But the {v[1]} is not detectable. Thus, the {v[0]} is not valid.",  # MT
        f"All {v[0]}s are required for {v[1]}. This specific item is a {v[0]}. It follows that it is required for {v[1]}.",  # Syllogism
        f"Either the {v[0]} is {v[1]} or it is {v[2]}. It is not {v[1]}. Consequently, it must be {v[2]}.",  # Disjunctive
    ]
    return random.choice(types)


def gen_factual_complex():
    """Factual statements with logical terminology."""
    domain = random.choice(list(DOMAINS.keys()))
    v = DOMAINS[domain]
    random.shuffle(v)

    statements = [
        f"The {v[0]} is a {v[1]} used in {domain} to manage {v[2]} and ensure {v[3]}.",
        f"In the context of {domain}, {v[0]} is often defined by its relationship to {v[1]}.",
        f"The current {v[0]} results in a significant increase in {v[1]} across all {v[2]} sectors.",
        f"A typical {v[0]} consists of a {v[1]}, a {v[2]}, and a primary {v[3]}.",
        f"Version 2.0 of the {v[0]} includes support for {v[1]} and improved {v[2]} metrics.",
    ]
    return random.choice(statements)


def gen_conditional_non_fallacy():
    """If P then Q where it's not a claim of truth of P or Q."""
    domain = random.choice(list(DOMAINS.keys()))
    v = DOMAINS[domain]
    random.shuffle(v)

    types = [
        f"If you encounter a {v[0]} error, you should check the {v[1]} configuration.",
        f"If the {v[0]} exceeds the {v[1]} limit, the system will automatically trigger a {v[2]}.",
        f"Users might experience {v[0]} if the {v[1]} is not properly calibrated.",
        f"If the {v[0]} is accepted, then the {v[1]} will be updated in the next cycle.",
    ]
    return random.choice(types)


def gen_affirming_consequent_hard():
    """Hard negatives targeting affirming_consequent."""
    domain = random.choice(list(DOMAINS.keys()))
    v = DOMAINS[domain]
    random.shuffle(v)

    types = [
        f"Because the {v[0]} is {v[1]}, we assume the {v[2]} caused the {v[3]}.",
        f"The {v[0]} is present, which usually happens when the {v[1]} is active, so the {v[0]} must be active.",
        f"Successful {v[0]} leads to {v[1]}. We have {v[1]}, so the {v[0]} was definitely successful.",
        f"If the {v[0]} failed, the {v[1]} would be zero. The {v[1]} is zero. Therefore, the {v[0]} failed.",
    ]
    return random.choice(types)


def generate_hard_negatives():
    data = []

    # 500 Valid Deductive
    for _ in range(500):
        text = random.choice(STYLES) + gen_valid_deductive()
        data.append({"text": text, "fallacy": "valid_reasoning", "source": "hard_negative_gen"})

    # 300 Factual Complex
    for _ in range(300):
        text = random.choice(STYLES) + gen_factual_complex()
        data.append({"text": text, "fallacy": "factual_statement", "source": "hard_negative_gen"})

    # 300 Conditional Non-Fallacy
    for _ in range(300):
        text = random.choice(STYLES) + gen_conditional_non_fallacy()
        data.append({"text": text, "fallacy": "factual_statement", "source": "hard_negative_gen"})

    # 300 Formal Implication (Non-causal) -> Factual
    for _ in range(300):
        text = gen_factual_complex()  # Reusing for similarity
        data.append({"text": text, "fallacy": "factual_statement", "source": "hard_negative_gen"})

    # 300 Hard Affirming Consequent
    for _ in range(300):
        text = gen_affirming_consequent_hard()
        data.append({"text": text, "fallacy": "affirming_consequent", "source": "hard_negative_gen"})

    # Quality filter: Deduplicate and validate
    unique_texts = set()
    final_data = []
    for d in data:
        if d["text"] not in unique_texts:
            final_data.append(d)
            unique_texts.add(d["text"])

    return final_data


if __name__ == "__main__":
    new_data = generate_hard_negatives()
    with open("data/hard_negatives_phase4_4.json", "w") as f:
        json.dump(new_data, f, indent=2)
    print(f"✅ Generated {len(new_data)} hard negatives.")
