import json
import random
from collections import Counter

DATA_PATH = "data/unified_training_data.json"


# ----------------------------
# Core IO
# ----------------------------
def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)


def hr(title=None):
    print("\n" + "=" * 70)
    if title:
        print(title)
        print("=" * 70)


def show_item(item, idx=None):
    if idx is not None:
        print(f"[{idx}]")
    print(json.dumps(item, indent=2))
    print("-" * 70)


# ----------------------------
# Search / Filter
# ----------------------------
def search(data, query):
    q = query.lower()
    return [d for d in data if q in json.dumps(d).lower()]


def filter_by_label(data, label):
    return [d for d in data if d.get("fallacy") == label]


def filter_by_source(data, source):
    return [d for d in data if d.get("source") == source]


# ----------------------------
# Stats
# ----------------------------
def print_table(counter, col1="Key", col2="Count"):
    print(f"{col1:<40}{col2}")
    print("-" * 55)
    for k, v in counter.most_common():
        print(f"{str(k):<40}{v}")


def label_stats(data):
    hr("LABEL DISTRIBUTION")
    counts = Counter(d.get("fallacy", "unknown") for d in data)
    print_table(counts)


def source_stats(data):
    hr("SOURCE DISTRIBUTION")
    counts = Counter(d.get("source", "unknown") for d in data)
    print_table(counts)


# ----------------------------
# Sampling
# ----------------------------
def sample_data(data, n):
    hr(f"RANDOM SAMPLE ({n})")
    for i, item in enumerate(random.sample(data, min(n, len(data)))):
        show_item(item, i)


# ----------------------------
# Drill down
# ----------------------------
def drill_down(data, label):
    subset = filter_by_label(data, label)
    hr(f"DRILL DOWN: {label} ({len(subset)} samples)")
    for item in subset[:20]:
        show_item(item)


# ----------------------------
# Export
# ----------------------------
def export(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    hr("EXPORT COMPLETE")
    print(f"Saved -> {path} ({len(data)} records)")


# ----------------------------
# Menu
# ----------------------------
def menu():
    data = load_data()

    while True:
        hr("DATASET EXPLORER")

        print("1  - Label statistics")
        print("2  - Source statistics")
        print("3  - Search dataset")
        print("4  - Filter by label")
        print("5  - Filter by source")
        print("6  - Random sample")
        print("7  - Drill down label")
        print("8  - Export data")
        print("9  - Exit")

        print("-" * 70)
        choice = input("Select option: ").strip()

        if choice == "1":
            label_stats(data)

        elif choice == "2":
            source_stats(data)

        elif choice == "3":
            q = input("Search query: ")
            res = search(data, q)
            hr(f"SEARCH RESULTS ({len(res)})")
            for i, r in enumerate(res[:20]):
                show_item(r, i)

        elif choice == "4":
            label = input("Label: ")
            res = filter_by_label(data, label)
            hr(f"FILTER: {label} ({len(res)})")
            for i, r in enumerate(res[:20]):
                show_item(r, i)

        elif choice == "5":
            src = input("Source: ")
            res = filter_by_source(data, src)
            hr(f"SOURCE FILTER: {src} ({len(res)})")
            for i, r in enumerate(res[:20]):
                show_item(r, i)

        elif choice == "6":
            n = int(input("Sample size: "))
            sample_data(data, n)

        elif choice == "7":
            label = input("Label: ")
            drill_down(data, label)

        elif choice == "8":
            mode = input("Export mode (all/label/search): ").strip()

            if mode == "all":
                export(data, "export_all.json")

            elif mode == "label":
                label = input("Label: ")
                export(filter_by_label(data, label), f"export_{label}.json")

            elif mode == "search":
                q = input("Query: ")
                export(search(data, q), "export_search.json")

        elif choice == "9":
            hr("EXIT")
            break

        else:
            print("Invalid option")


if __name__ == "__main__":
    menu()
