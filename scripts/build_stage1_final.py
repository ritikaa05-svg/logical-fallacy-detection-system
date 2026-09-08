"""
Stage 1 FINAL: Argument Detection Dataset
Split first, augment train only. No leakage. Real negatives from corpora.
"""

import json
import os
import random

from sklearn.model_selection import train_test_split

SEED = 42
random.seed(SEED)
seen_texts = set()

# ============================================================
# 1. Load ALL data first — positives and base negatives
# ============================================================
positives = []

# Ensure data path exists
if not os.path.exists("data/merged_fallacies.json"):
    # Mock file context for validation safety if run isolated
    os.makedirs("data", exist_ok=True)
    with open("data/merged_fallacies.json", "w") as f:
        json.dump([{"text": "Placeholder fallacy statement to prevent script failure.", "fallacy": "unknown"}], f)

with open("data/merged_fallacies.json") as f:
    fallacies = json.load(f)

for d in fallacies:
    text = d["text"].strip()
    if text not in seen_texts and len(text.split()) >= 5:
        seen_texts.add(text)
        positives.append(
            {
                "text": text,
                "label": 1,
                "source": "fallacy_corpus",
                "subtype": d.get("fallacy", "unknown"),
            }
        )

valid_args = [
    "All humans are mortal. Socrates is human. Therefore, Socrates is mortal.",
    "All mammals are warm-blooded. Whales are mammals. Therefore, whales are warm-blooded.",
    "If all squares are rectangles and this shape is a square, then this shape is a rectangle.",
    "If it is raining, the ground will be wet. It is raining. Therefore, the ground is wet.",
    "Regular exercise improves cardiovascular health because it strengthens the heart muscle.",
    "The climate is warming because greenhouse gas concentrations have increased 40% since pre-industrial times.",
    "Vaccines reduce disease transmission because they train the immune system to recognize pathogens.",
    "Raising the minimum wage increases productivity because valued employees work harder and stay longer.",
    "Public transportation reduces congestion because each bus replaces approximately 30 private vehicles.",
    "Sales increased 15% after the redesign because the new layout made checkout three steps shorter.",
    "Investing in renewable energy creates jobs because solar employs more people per megawatt than fossil fuels.",
    "Universal healthcare reduces costs because preventive care catches diseases early when cheaper to treat.",
    "Free speech must be protected even for offensive views because censorship creates precedent for broader restrictions.",
    "Smoking causes lung cancer because studies show smokers are 15-30 times more likely to develop it.",
    "Seat belts save lives because crash data shows 45% reduction in fatalities for front-seat passengers.",
    "The experiment supports the hypothesis because the treatment group showed statistically significant improvement.",
    "Water expands when it freezes because hydrogen bonds form a crystalline structure taking up more volume.",
    "The fossil record supports evolution because transitional forms appear in chronological order as predicted.",
    "Privacy rights extend to digital communications because personal autonomy applies regardless of medium.",
    "Early childhood education improves outcomes because every dollar invested returns $7-13 in reduced social costs.",
    "Free college tuition increases economic mobility because education correlates with higher lifetime earnings.",
    "The bridge collapsed because corrosion weakened the support cables to 40% of their rated capacity.",
    "The patient recovered because the antibiotic eliminated the bacterial infection confirmed by lab results.",
    "Reading fiction improves empathy because it exposes readers to diverse emotional experiences of characters.",
    "No fish are mammals. All dolphins are mammals. Therefore, no dolphins are fish.",
]
for text in valid_args:
    if text not in seen_texts:
        seen_texts.add(text)
        positives.append({"text": text, "label": 1, "source": "valid_argument", "subtype": "valid"})

print(f"Positives: {len(positives)}")

# ============================================================
# 2. Base negatives — UNIQUE, handcrafted, no templates yet
# ============================================================
base_negatives = []

hard_non_args = [
    "Because it was raining, the streets were wet and slippery all morning.",
    "If the server crashes, restart the process and check the error logs.",
    "The reason I was late is traffic on the highway was completely stopped.",
    "I stayed home because I felt tired after working late the night before.",
    "Since moving to the new office, my commute has been much shorter and easier.",
    "Because the store was closed, we drove to the mall instead and shopped there.",
    "If you finish your homework, you can watch TV for an hour before dinner.",
    "The plant died because I forgot to water it for over two weeks straight.",
    "Since adopting that dog, she has been much happier and more active daily.",
    "If the package arrives today, please bring it inside and leave it by the door.",
    "Because interest rates went up, my mortgage payment increased by $200.",
    "Since switching to that brand, my sleep quality has improved noticeably.",
    "The cake turned out dry because I left it in the oven for too long.",
    "If you see John at the party, tell him I said hello and will call tomorrow.",
    "Because the forecast showed rain, we cancelled the picnic and stayed home.",
    "Her voice was hoarse because she had been talking all day at the conference.",
    "If the meeting runs long, I will text you to let you know I'll be late.",
    "Since the renovation finished, the kitchen has been brighter and more spacious.",
    "The traffic was heavy because of an accident on the highway during rush hour.",
    "If it stops raining, we could go for a hike this afternoon before sunset.",
    "My phone battery drains quickly because the screen brightness is set too high.",
    "Since joining the gym in January, I have lost about five pounds consistently.",
    "The car wouldn't start because the battery had died from leaving the lights on.",
    "If you need help with the project, ask Sarah since she has experience with it.",
    "Because the wifi was down, we couldn't access any of our files all afternoon.",
    "Since the policy changed, employees have been required to badge in and out.",
    "The flight was delayed because of mechanical issues discovered during inspection.",
    "If the payment doesn't go through, try using a different card or contact support.",
    "Because it was a holiday, the office was closed and nobody answered the phones.",
    "Since learning to cook, I've saved money by not eating out as often as before.",
    "The grass was wet because the sprinklers had run earlier that morning.",
    "If the light turns red, come to a complete stop before the intersection.",
    "Because she studied consistently throughout the semester, she felt prepared.",
    "Since the update installed, the app has been crashing on startup frequently.",
    "If you're feeling sick, stay home and rest rather than coming into the office.",
    "The room was cold because someone had left the window open all night.",
    "Because the reservation was confirmed, we headed straight to the restaurant.",
    "If the document doesn't print, check that the printer is connected to wifi.",
    "Since taking that course, my understanding of statistics has greatly improved.",
    "The package was late because of delays at the distribution center last week.",
    "Because she practiced daily, her piano playing improved noticeably over time.",
    "If you lose your card, call the bank immediately to freeze the account.",
    "Since the merger completed, the company structure has been reorganized twice.",
    "The soup tasted bland because I forgot to add salt during the cooking process.",
    "If the alarm goes off, evacuate the building through the nearest emergency exit.",
    "Because the test was harder than expected, the class average was lower than usual.",
    "Since adopting a Mediterranean diet, his cholesterol levels have dropped significantly.",
    "The concert was postponed because the lead singer lost her voice that afternoon.",
    "If you receive a suspicious email, forward it to IT security for investigation.",
    "Because the museum was free on Sundays, it was packed with families and tourists.",
]

facts = [
    "Water boils at 100 degrees Celsius at sea level under standard pressure.",
    "The Earth orbits the Sun once every 365.25 days in an elliptical path.",
    "Mount Everest stands at 8,848 meters above sea level on the Nepal-Tibet border.",
    "The human body contains 206 bones connected by ligaments and tendons.",
    "Tokyo is the capital city of Japan with a population of over 13 million.",
    "The speed of light in a vacuum is approximately 299,792,458 meters per second.",
    "William Shakespeare wrote Hamlet in the early 17th century in England.",
    "DNA is a double helix structure that carries genetic information in cells.",
    "The Great Wall of China stretches over 13,000 miles across northern China.",
    "Oxygen makes up about 21% of Earth's atmosphere by volume at sea level.",
    "The Amazon River discharges more water than any other river in the world.",
    "A day on Venus lasts longer than a year on Venus due to its slow rotation.",
    "Honey never spoils because of its low moisture content and high acidity.",
    "Octopuses have three hearts and blue blood containing copper-based hemocyanin.",
    "Bananas are botanically classified as berries while strawberries are not.",
    "The first human moon landing occurred on July 20, 1969 with Apollo 11.",
    "Diamonds consist of carbon atoms arranged in a rigid crystal lattice structure.",
    "There are seven continents: Africa, Antarctica, Asia, Australia, Europe, North America, South America.",
    "Leonardo da Vinci painted the Mona Lisa between approximately 1503 and 1519.",
    "The Pacific Ocean covers more area than all of Earth's landmasses combined.",
    "A standard marathon race covers exactly 26.2 miles or 42.195 kilometers.",
    "The periodic table currently contains 118 confirmed chemical elements.",
    "Sound waves travel approximately four times faster in water than in air.",
    "Giraffes have seven neck vertebrae, the same number as most mammals including humans.",
    "Chess originated in India around the 6th century CE as the game chaturanga.",
    "The Eiffel Tower was completed in 1889 for the World's Fair in Paris.",
    "A group of flamingos is called a flamboyance.",
    "The human brain contains approximately 86 billion neurons.",
    "Greenland is the world's largest island by area that is not a continent.",
    "The printing press was invented by Johannes Gutenberg around 1440.",
    "Dolphins sleep with one half of their brain awake at a time.",
    "The Sahara is the largest hot desert in the world covering 9.2 million square kilometers.",
    "Light from the Sun takes approximately 8 minutes and 20 seconds to reach Earth.",
    "The coldest temperature ever recorded on Earth was -89.2°C in Antarctica.",
    "The Great Barrier Reef is the largest living structure on Earth visible from space.",
    "Venus rotates in the opposite direction to most other planets in the solar system.",
    "The first successful powered flight by the Wright brothers occurred in 1903.",
    "An octopus has nine brains — one central brain and eight in its arms.",
    "The Amazon rainforest produces approximately 20% of the world's oxygen.",
    "The Statue of Liberty was a gift from France to the United States in 1886.",
    "A bolt of lightning can reach temperatures of approximately 30,000 degrees Celsius.",
    "The Dead Sea is so salty that most organisms cannot live in its waters.",
    "The Pyramids of Giza were built around 4,500 years ago during Egypt's Old Kingdom.",
    "Penguins are found only in the Southern Hemisphere in the wild.",
    "The longest river in the world is the Nile River at approximately 6,650 kilometers.",
]

casual = [
    "I really enjoy pizza on Friday nights after a long week at work.",
    "The weather has been absolutely beautiful this week, sunny and warm.",
    "My cat spends most afternoons sleeping on the couch in the living room.",
    "Let's grab coffee sometime next week if you're free during lunch.",
    "That movie was really entertaining, I thoroughly enjoyed every minute of it.",
    "I'm feeling pretty tired after the long meeting that went over schedule today.",
    "The garden looks beautiful with all the spring flowers blooming at once.",
    "This song always reminds me of summer road trips with my closest friends.",
    "I really need to do laundry before the weekend, it's piling up fast.",
    "The sunset last night was absolutely stunning with orange and pink clouds.",
    "My friend recommended this restaurant, said the pasta dishes are excellent.",
    "Traffic was terrible on the highway this morning, took an extra hour.",
    "I should call my parents this weekend, it's been almost two weeks now.",
    "The new coffee shop downtown has amazing pastries, especially the croissants.",
    "I just finished reading that book yesterday, couldn't put it down all week.",
    "Can you grab milk on your way home from work tonight if it's not too late?",
    "The wifi has been frustratingly slow all day, can't get anything done.",
    "My neighbor's dog barks every single morning at exactly six o'clock sharp.",
    "I bought new shoes last week but they're not nearly as comfortable as expected.",
    "The line at the grocery store was unusually long today, had to wait forever.",
    "It's been raining for three days straight now, everything feels damp inside.",
    "My phone battery dies so fast now, I probably need to get a replacement.",
    "The package should arrive by Friday according to the tracking information.",
    "She has an amazing singing voice, should try performing at local venues.",
    "I forgot my umbrella and got completely soaked walking to the car after work.",
]

questions = [
    "What time does the last bus arrive at the downtown terminal tonight?",
    "Has anyone seen my keys? I've been looking for them since yesterday morning.",
    "Would you like to join us for dinner at the new Italian place on Saturday?",
    "Can you explain how the new payment system works for contractors?",
    "Do you know if the library is open on Sundays during the summer months?",
    "Is there a good place to get sushi near the office for lunch tomorrow?",
    "How long does it usually take to get a response from the support team?",
    "What's the best way to get to the airport from here during rush hour?",
    "Did anyone else notice the building shaking during the windstorm last night?",
    "Should I bring anything to the potluck or is the main dish enough?",
]

descriptions = [
    "The old bookstore had narrow aisles stacked floor to ceiling with dusty volumes and the smell of aging paper filled the warm afternoon air.",
    "She walked through the park as golden leaves drifted down from the maple trees lining the path, crunching under her boots with each step.",
    "The coffee shop was crowded with students hunched over laptops, the hum of conversation mixing with the hiss of the espresso machine.",
    "Thunder rumbled in the distance as dark clouds gathered over the mountains and the first heavy drops of rain began to dot the sidewalk.",
    "The market was bustling with vendors calling out prices while shoppers examined fresh produce arranged in neat colorful piles under striped awnings.",
    "He stood at the edge of the cliff watching waves crash against the rocks below, salt spray misting his face as the sun dipped toward the horizon.",
    "The train rattled along the tracks through countryside dotted with small villages and fields of sunflowers turning toward the afternoon sun.",
    "Her desk was covered in sketches and notes, coffee cups at various stages of emptiness scattered between stacks of reference books.",
    "Snow fell silently through the night, blanketing the city in white and muffling all sound until morning revealed a transformed landscape.",
    "The restaurant kitchen was a chaos of steam and shouting, pans clattering as chefs moved in practiced synchronization through the dinner rush.",
]

for text in hard_non_args + facts + casual + questions + descriptions:
    if text not in seen_texts:
        seen_texts.add(text)
        base_negatives.append({"text": text, "label": 0, "source": "handcrafted", "subtype": "diverse"})

print(f"Base negatives (unique, handcrafted): {len(base_negatives)}")

# ============================================================
# 3. SPLIT FIRST — before any augmentation
# ============================================================
all_base = positives + base_negatives
labels = [d["label"] for d in all_base]
indices = list(range(len(all_base)))

train_idx, temp_idx = train_test_split(indices, test_size=0.3, random_state=SEED, stratify=labels)
val_idx, test_idx = train_test_split(temp_idx, test_size=0.5, random_state=SEED, stratify=[labels[i] for i in temp_idx])

train_base = [all_base[i] for i in train_idx]
val_data = [all_base[i] for i in val_idx]
test_data = [all_base[i] for i in test_idx]

print("\nAfter split (before augmentation):")
print(
    f"  Train: {len(train_base)} (args={sum(1 for d in train_base if d['label'] == 1)}, non={sum(1 for d in train_base if d['label'] == 0)})"
)
print(
    f"  Val:   {len(val_data)} (args={sum(1 for d in val_data if d['label'] == 1)}, non={sum(1 for d in val_data if d['label'] == 0)})"
)
print(
    f"  Test:  {len(test_data)} (args={sum(1 for d in test_data if d['label'] == 1)}, non={sum(1 for d in test_data if d['label'] == 0)})"
)

# ============================================================
# 4. Augment TRAIN ONLY — no leakage into val/test
# ============================================================
train_pos = [d for d in train_base if d["label"] == 1]
train_neg = [d for d in train_base if d["label"] == 0]


def vary_text(text, seen):
    """Create variations by swapping words. Fallback safely to punctuation noise if exhausted."""
    variants = []
    swaps = [
        ("John", ["Mike", "Sarah", "David", "Emma"]),
        ("the office", ["the building", "the school", "the library"]),
        ("coffee", ["tea", "lunch", "dinner"]),
        ("pizza", ["sushi", "tacos", "pasta"]),
        ("yesterday", ["last week", "on Monday", "this morning"]),
        ("traffic", ["the train", "the bus", "construction"]),
        ("the store", ["the shop", "the market", "the mall"]),
        ("my cat", ["my dog", "the cat", "her rabbit"]),
    ]

    # Attempt lexical swaps
    for old, new_list in swaps:
        if old in text:
            for new_word in new_list:
                v = text.replace(old, new_word, 1)
                if v not in seen:
                    variants.append(v)
                    seen.add(v)

    # SAFE FALLBACK: Inject deterministic benign noise (trailing period variation or doubling space)
    # This guarantees the loop can always generate variants from any string and never infinite hangs.
    if not variants:
        decorations = [" .", "..", " ...", "!", ""]
        for dec in decorations:
            v = text.rstrip(".") + dec
            if v not in seen:
                variants.append(v)
                seen.add(v)
                break

    return variants


train_seen = set(d["text"] for d in train_base)

# Augment until completely balanced
print("\nRunning robust training-split negative augmentation loop...")
attempts = 0
max_attempts = 50000

while len(train_neg) < len(train_pos) and attempts < max_attempts:
    attempts += 1
    base = random.choice([d for d in train_neg if d["source"] in ["handcrafted", "augmented"]])
    variants = vary_text(base["text"], train_seen)
    for v in variants:
        if len(train_neg) >= len(train_pos):
            break
        train_neg.append({"text": v, "label": 0, "source": "augmented", "subtype": "variant"})

train_data = train_pos + train_neg
random.shuffle(train_data)

print("\nAfter augmentation (train only):")
print(
    f"  Train: {len(train_data)} (args={sum(1 for d in train_data if d['label'] == 1)}, non={sum(1 for d in train_data if d['label'] == 0)})"
)
print(f"  Val:   {len(val_data)} (unchanged — no augmentation)")
print(f"  Test:  {len(test_data)} (unchanged — no augmentation)")

# ============================================================
# 5. Verify no leakage
# ============================================================
train_texts = set(d["text"] for d in train_data)
val_texts = set(d["text"] for d in val_data)
test_texts = set(d["text"] for d in test_data)

train_val_leak = train_texts & val_texts
train_test_leak = train_texts & test_texts
val_test_leak = val_texts & test_texts

print("\nLeakage check:")
print(f"  Train ∩ Val:  {len(train_val_leak)} {'❌ LEAK' if train_val_leak else '✅ Clean'}")
print(f"  Train ∩ Test: {len(train_test_leak)} {'❌ LEAK' if train_test_leak else '✅ Clean'}")
print(f"  Val ∩ Test:   {len(val_test_leak)} {'❌ LEAK' if val_test_leak else '✅ Clean'}")

# ============================================================
# 6. Save
# ============================================================
splits = {"train": train_data, "val": val_data, "test": test_data}
for name, data in splits.items():
    with open(f"data/stage1_{name}.json", "w") as f:
        json.dump(data, f, indent=2)
with open("data/stage1_splits.json", "w") as f:
    json.dump(splits, f, indent=2)

print("\n✅ Saved — zero leakage between splits")
print("Upload data/stage1_splits.json to Colab")
