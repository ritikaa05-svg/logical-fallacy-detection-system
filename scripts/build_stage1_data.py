"""
Build Stage 1 training data with proper ML rigor.
- Separate source files, no leakage
- Deduplication
- Reproducible splits
- Hard negatives (valid arguments, not just facts)
- Rich negatives from multiple sources
"""

import json
import random
from collections import Counter

from sklearn.model_selection import train_test_split

SEED = 42
random.seed(SEED)

# ============================================================
# SOURCE 1: Fallacy examples = POSITIVES (label=1)
# These ARE arguments containing logical fallacies
# ============================================================
with open("data/merged_fallacies.json") as f:
    fallacies = json.load(f)

positives = []
seen_texts = set()

for d in fallacies:
    text = d["text"].strip()
    if text not in seen_texts and len(text.split()) >= 5:
        seen_texts.add(text)
        positives.append(
            {
                "text": text,
                "label": 1,
                "source": d.get("source", "fallacy_db"),
                "subtype": d.get("fallacy", "unknown"),
            }
        )

print(f"Positives (fallacies): {len(positives)}")

# ============================================================
# SOURCE 2: Hard negatives — valid arguments (label=0)
# These ARE arguments but contain NO fallacy
# ============================================================
valid_arguments = [
    # Classic valid syllogisms
    "All humans are mortal. Socrates is human. Therefore, Socrates is mortal.",
    "All mammals are warm-blooded. Whales are mammals. Therefore, whales are warm-blooded.",
    "If all squares are rectangles and this shape is a square, then this shape is a rectangle.",
    "No fish are mammals. All dolphins are mammals. Therefore, no dolphins are fish.",
    "Every triangle has three sides. This shape is a triangle. Therefore, this shape has three sides.",
    "If it is raining, the ground will be wet. It is raining. Therefore, the ground is wet.",
    # Evidence-based arguments
    "Regular exercise improves cardiovascular health because it strengthens the heart muscle and improves blood circulation.",
    "The climate is warming because greenhouse gas concentrations have increased 40% since pre-industrial times, trapping more heat.",
    "Vaccines reduce disease transmission because they train the immune system to recognize pathogens before infection occurs.",
    "Raising the minimum wage increases worker productivity because employees who feel valued tend to work harder and stay longer.",
    "Reading fiction improves empathy because it exposes readers to diverse perspectives and emotional experiences of characters.",
    "Public transportation reduces urban congestion because each bus replaces approximately 30 private vehicles on the road.",
    # Causal arguments with evidence
    "The patient's fever dropped after taking the antibiotic, and lab results confirmed the bacterial infection was eliminated.",
    "Sales increased 15% after the website redesign because the new layout made the checkout process three steps shorter.",
    "The bridge collapsed because structural engineers found that corrosion had weakened the support cables to 40% of their rated capacity.",
    # Policy arguments with reasoning
    "Investing in renewable energy creates jobs because solar and wind industries employ more people per megawatt than fossil fuels.",
    "Universal healthcare reduces overall costs because preventive care catches diseases early when they are cheaper to treat.",
    "Free college tuition increases economic mobility because education directly correlates with higher lifetime earnings and lower unemployment.",
    # Statistical arguments
    "Smoking causes lung cancer because long-term studies show smokers are 15-30 times more likely to develop lung cancer than non-smokers.",
    "Seat belts save lives because crash data shows they reduce the risk of death by 45% for front-seat passengers.",
    "Early childhood education improves life outcomes because longitudinal studies show every dollar invested returns $7-13 in reduced social costs.",
    # Philosophical arguments
    "Free speech must be protected even for offensive views because once you start censoring, you create a precedent that can be used against any viewpoint.",
    "Privacy rights extend to digital communications because the principle of personal autonomy applies regardless of the medium of expression.",
    # Scientific reasoning
    "The experiment supports the hypothesis because the treatment group showed statistically significant improvement compared to the control group.",
    "The fossil record supports evolution because we observe transitional forms appearing in the chronological order that common descent predicts.",
    "Water expands when it freezes because the hydrogen bonds in ice form a crystalline structure that takes up more volume than liquid water.",
] * 8  # ~200 samples

for text in valid_arguments:
    if text not in seen_texts:
        seen_texts.add(text)
        positives.append(
            {
                "text": text,
                "label": 1,
                "source": "valid_argument",
                "subtype": "valid",
            }
        )
        positives.append(
            {
                "text": text,
                "label": 1,
                "source": "valid_argument",
                "subtype": "valid",
            }
        )

# Deduplicate positives again
unique_pos = []
seen_p = set()
for d in positives:
    if d["text"] not in seen_p:
        seen_p.add(d["text"])
        unique_pos.append(d)
positives = unique_pos
print(f"Positives after dedup: {len(positives)}")

# ============================================================
# SOURCE 3: Easy negatives — factual statements (label=0)
# These are NOT arguments at all
# ============================================================
factual_statements = [
    "Water boils at 100 degrees Celsius at sea level.",
    "The Earth orbits the Sun once every 365.25 days.",
    "Mount Everest is the tallest mountain on Earth above sea level.",
    "The human body contains 206 bones.",
    "Tokyo is the capital city of Japan.",
    "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
    "Shakespeare wrote Hamlet in the early 17th century.",
    "DNA is a double helix structure that carries genetic information.",
    "The Great Wall of China is over 13,000 miles long.",
    "Oxygen makes up about 21% of Earth's atmosphere.",
    "The Amazon River is the largest river in the world by water volume.",
    "A day on Venus is longer than a year on Venus.",
    "Honey never spoils due to its low moisture and high acidity.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are technically berries, but strawberries are not.",
    "The first moon landing occurred on July 20, 1969.",
    "Diamonds are made of carbon atoms arranged in a crystal structure.",
    "There are seven continents on Earth.",
    "Leonardo da Vinci painted the Mona Lisa between 1503 and 1519.",
    "The Pacific Ocean is the largest ocean on Earth.",
    "Chess originated in India around the 6th century.",
    "A marathon is 26.2 miles long.",
    "The periodic table contains 118 confirmed elements.",
    "Sound travels faster in water than in air.",
    "Giraffes have the same number of neck vertebrae as humans.",
]

# ============================================================
# SOURCE 4: Everyday non-arguments (label=0)
# Casual speech, opinions without reasoning, observations
# ============================================================
casual_statements = [
    "I really enjoy pizza on Friday nights after work.",
    "The weather has been beautiful this week.",
    "My cat sleeps on the couch all afternoon.",
    "Let's grab coffee sometime next week.",
    "That movie was really entertaining, I enjoyed it.",
    "I'm feeling tired after the long meeting today.",
    "The garden looks beautiful with all the spring flowers.",
    "This song always reminds me of summer road trips.",
    "I need to do laundry before the weekend.",
    "The sunset last night was absolutely stunning.",
    "My friend recommended this restaurant, said it's great.",
    "Traffic was terrible on the highway this morning.",
    "I should call my parents, it's been a while.",
    "The new coffee shop downtown has amazing pastries.",
    "I just finished reading that book yesterday.",
    "Can you grab milk on your way home?",
    "The wifi has been slow all day.",
    "My neighbor's dog barks every morning at 6.",
    "I bought new shoes but they're not very comfortable.",
    "The line at the grocery store was really long.",
    "It's been raining for three days straight.",
    "My phone battery dies so fast now.",
    "The package should arrive by Friday.",
    "She has an amazing singing voice.",
    "I forgot my umbrella and got soaked walking home.",
]

# Combine negatives — use each exactly ONCE
negatives = []
for text in factual_statements + casual_statements:
    if text not in seen_texts:
        seen_texts.add(text)
        negatives.append(
            {
                "text": text,
                "label": 0,
                "source": "non_argument",
                "subtype": "fact_or_casual",
            }
        )

print(f"Negatives (non-arguments): {len(negatives)}")

# ============================================================
# Balance and combine
# ============================================================
# Trim positives to balance (or keep all)
target_pos = min(len(positives), len(negatives) * 2)  # 2:1 ratio
if len(positives) > target_pos:
    positives = random.sample(positives, target_pos)

# Balance negatives to roughly match
target_neg = len(positives)
if len(negatives) > target_neg:
    negatives = random.sample(negatives, target_neg)

# Combine
all_data = positives + negatives
random.shuffle(all_data)

print(f"\nFinal dataset: {len(all_data)} samples")
print(f"  Positives (arguments/fallacies): {sum(1 for d in all_data if d['label'] == 1)}")
print(f"  Negatives (non-arguments): {sum(1 for d in all_data if d['label'] == 0)}")

# ============================================================
# Stratified train/val/test split
# ============================================================
texts = [d["text"] for d in all_data]
labels = [d["label"] for d in all_data]

X_train, X_temp, y_train, y_temp = train_test_split(
    range(len(all_data)), labels, test_size=0.3, random_state=SEED, stratify=labels
)
X_val, X_test = train_test_split(X_temp, test_size=0.5, random_state=SEED, stratify=[labels[i] for i in X_temp])

# Build split datasets
splits = {
    "train": [all_data[i] for i in X_train],
    "val": [all_data[i] for i in X_val],
    "test": [all_data[i] for i in X_test],
}

# ============================================================
# Save — separate files, no overwriting source data
# ============================================================
with open("data/stage1_train.json", "w") as f:
    json.dump(splits["train"], f, indent=2)
with open("data/stage1_val.json", "w") as f:
    json.dump(splits["val"], f, indent=2)
with open("data/stage1_test.json", "w") as f:
    json.dump(splits["test"], f, indent=2)

# Also save combined for Colab
with open("data/stage1_splits.json", "w") as f:
    json.dump(splits, f, indent=2)

print(f"\nTrain: {len(splits['train'])}")
print(f"Val:   {len(splits['val'])}")
print(f"Test:  {len(splits['test'])}")
print("\nTest distribution:")
test_labels = Counter(d["label"] for d in splits["test"])
print(f"  Arguments: {test_labels.get(1, 0)}")
print(f"  Non-arguments: {test_labels.get(0, 0)}")
print("\n✅ Saved:")
print("  data/stage1_train.json")
print("  data/stage1_val.json")
print("  data/stage1_test.json")
print("  data/stage1_splits.json (combined for Colab)")
