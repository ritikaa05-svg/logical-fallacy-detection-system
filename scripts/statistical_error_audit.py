import pandas as pd


def run_statistical_audit():
    # Metrics from Epoch 6 Results
    metrics = {
        "ad_hominem": {"p": 0.54, "r": 0.64, "s": 58},
        "affirming_consequent": {"p": 0.92, "r": 0.39, "s": 28},
        "appeal_to_authority": {"p": 0.75, "r": 0.73, "s": 116},
        "appeal_to_emotion": {"p": 0.50, "r": 0.56, "s": 59},
        "appeal_to_nature": {"p": 0.87, "r": 0.90, "s": 94},
        "appeal_to_tradition": {"p": 0.83, "r": 0.95, "s": 91},
        "bandwagon": {"p": 0.83, "r": 0.89, "s": 106},
        "begging_the_question": {"p": 0.68, "r": 0.54, "s": 24},
        "composition": {"p": 1.00, "r": 1.00, "s": 8},
        "denying_antecedent": {"p": 0.78, "r": 1.00, "s": 7},
        "division": {"p": 1.00, "r": 1.00, "s": 7},
        "equivocation": {"p": 1.00, "r": 1.00, "s": 8},
        "factual_statement": {"p": 0.98, "r": 1.00, "s": 84},
        "false_cause": {"p": 0.45, "r": 0.55, "s": 44},
        "false_dilemma": {"p": 0.89, "r": 0.85, "s": 101},
        "hasty_generalization": {"p": 0.63, "r": 0.54, "s": 157},
        "moving_goalposts": {"p": 1.00, "r": 0.75, "s": 4},
        "no_true_scotsman": {"p": 0.80, "r": 1.00, "s": 4},
        "red_herring": {"p": 0.81, "r": 0.62, "s": 139},
        "slippery_slope": {"p": 0.80, "r": 0.91, "s": 103},
        "straw_man": {"p": 0.86, "r": 0.94, "s": 90},
        "tu_quoque": {"p": 0.88, "r": 1.00, "s": 7},
        "tu_quoque_contextual": {"p": 1.00, "r": 1.00, "s": 4},
        "valid_reasoning": {"p": 0.94, "r": 1.00, "s": 84},
    }

    print("--- 1. CONFUSION ANALYSIS (Likeliness based on PR-Gap) ---")
    results = []
    for name, m in metrics.items():
        fn_count = int(m["s"] * (1 - m["r"]))
        fp_count = int((m["s"] * m["r"] / (m["p"] + 1e-6)) - (m["s"] * m["r"]))
        results.append({"class": name, "fn": fn_count, "fp": fp_count, "support": m["s"]})

    df = pd.DataFrame(results).sort_values("fn", ascending=False)
    print(df.to_string())

    print("\n--- 4. SMALL-CLASS RELIABILITY ---")
    small_classes = df[df["support"] < 10]
    print("Classes with < 10 validation samples (High Variance Risk):")
    print(small_classes[["class", "support"]].to_string())


if __name__ == "__main__":
    run_statistical_audit()
