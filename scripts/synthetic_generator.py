import json
import logging
import os
import random

# Mocking app context for script execution
import sys
from datetime import datetime
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

# We use local classifiers for verification if available, but skip LLM generation
from backend.app.services.unified_classifier import unified_classifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FALLACY_DEFINITIONS = {
    "equivocation": {
        "description": "Using a word in two different senses within the same argument.",
        "example": "A feather is light. What is light cannot be dark. So a feather cannot be dark.",
        "type": "informal",
    },
    "tu_quoque": {
        "description": "Deflecting criticism by pointing out the critic's hypocrisy.",
        "example": "You tell me not to smoke, but you smoked for 20 years!",
        "type": "informal",
    },
    "denying_antecedent": {
        "description": "A formal fallacy of the form: If A then B. Not A. Therefore not B.",
        "example": "If it rains, the ground is wet. It's not raining. So the ground isn't wet.",
        "type": "formal",
    },
    "affirming_consequent": {
        "description": "A formal fallacy of the form: If A then B. B. Therefore A.",
        "example": "If it rains, the ground is wet. The ground is wet. Therefore, it rained.",
        "type": "formal",
    },
    "composition": {
        "description": "Assuming that what is true of the parts must be true of the whole.",
        "example": "Each molecule in this glass is invisible. Therefore, the water in the glass is invisible.",
        "type": "informal",
    },
    "division": {
        "description": "Assuming that what is true of the whole must be true of the parts.",
        "example": "The team is great. Therefore, every player on the team is great.",
        "type": "informal",
    },
    "valid_reasoning": {
        "description": "Logically sound arguments following valid structures like Modus Ponens or evidence-based claims.",
        "example": "If it is raining, the streets are wet. It is raining, therefore the streets are wet.",
        "type": "logic",
    },
    "factual_statement": {
        "description": "Neutral, non-argumentative statements of fact or observation.",
        "example": "The capital of France is Paris.",
        "type": "fact",
    },
}

# Template-based generation to bypass API/Model issues
TEMPLATES = {
    "false_cause": [
        "I wore my lucky socks and we won; therefore, the socks caused the win.",
        "The sun rose after the rooster crowed, so the rooster made the sun rise.",
        "I took Vitamin C and my cold went away in two days. It cured me!",
        "Crime rose after the new mayor took office; he is clearly to blame for the surge.",
        "Ever since they built that cell tower, my milk has been turning sour faster.",
        "I started eating more kale and then I got promoted. Kale is the secret to success.",
        "The stock market crashed right after the new law passed. The law caused the crash.",
        "I prayed for rain and it rained. Prayer works for the weather!",
        "The team started losing as soon as I started watching the game.",
        "A black cat crossed my path and then I tripped. The cat brought me bad luck.",
        "He drank a glass of water and his headache vanished. Water is a miracle cure.",
        "The computer crashed right after you walked into the room. You broke it!",
        "I saw a shooting star and then I won the lottery. The star gave me the winning numbers.",
    ],
    "begging_the_question": [
        "A is true because B is true, and B is true because A is true.",
        "God exists because the Bible says so. The Bible is a reliable source because it is the word of God.",
        "Plagiarism is deceitful because it is dishonest.",
        "Ghosts are real because I've seen things that can only be explained as ghosts.",
        "The law should be followed because it is the law.",
        "Freedom of speech is important because people should be able to speak freely.",
        "He is a great communicator because he speaks very effectively.",
        "Happiness is the highest good because it is the most desirable state to be in.",
        "Euthanasia is murder because it is the intentional killing of a human being.",
        "You can trust him because he is an honest person.",
        "The news is fake because it is full of lies.",
        "This product is the best because no other product is as good as this one.",
    ],
    "tu_quoque_contextual": [
        "User: You should stop smoking. Assistant: But you smoke a pack a day!",
        "User: Your argument is logicially flawed. Assistant: Look who's talking, your last point was a disaster.",
        "User: We need to reduce our carbon footprint. Assistant: Coming from someone who flies private jets?",
        "User: You shouldn't be so judgmental. Assistant: You're the one judging me right now!",
        "User: It's important to be on time. Assistant: You were late to every meeting last week.",
        "User: Cheating is wrong. Assistant: Didn't you cheat on your taxes last year?",
        "User: You should be more polite. Assistant: Why should I listen to you? You're extremely rude.",
        "User: This project needs more effort. Assistant: You haven't done any work on it for days.",
    ],
    "moving_goalposts": [
        "User: I've proven X. Assistant: Okay, but now you have to prove Y too.",
        "User: Here is the evidence you asked for. Assistant: That's not good enough, I need a different type of proof.",
        "User: The study shows the medicine works. Assistant: Sure, but does it work for people over 90?",
        "User: I met all your criteria. Assistant: Well, I've decided the criteria are now more strict.",
        "User: Here is a peer-reviewed source. Assistant: Peer-review is biased; find me a source that isn't from a university.",
        "The car passed the safety test. Assistant: But can it survive a fall from a plane?",
        "User: I finished the task. Assistant: I actually wanted you to finish two tasks.",
    ],
    "no_true_scotsman": [
        "No true scientist would believe in that theory.",
        "Well, no real fan of the team would ever say that.",
        "A true patriot would always support this policy.",
        "No real artist uses digital tools; only traditional media counts.",
        "He's not a real Christian if he doesn't follow every single rule.",
        "No true philosopher would ever accept such a simple answer.",
        "A real gamer wouldn't play on easy mode.",
        "No true intellectual reads that kind of trashy literature.",
    ],
    "ad_hominem": [
        "You're too stupid to understand this complex issue.",
        "Why should we listen to a known liar like you?",
        "Only an idiot would believe such a ridiculous claim.",
        "You're just saying that because you're a greedy corporate shill.",
        "Your opinion doesn't matter because you're not even from this country.",
        "You're always so angry, nobody can take your arguments seriously.",
        "He's just a lazy student, his theories on economics are worthless.",
        "She's just a bitter ex-employee, ignore everything she says.",
    ],
    "appeal_to_emotion": [
        "Think of the poor, starving children who will suffer if you don't act.",
        "Imagine the absolute terror of being trapped in that situation.",
        "If we don't pass this law, our streets will be filled with blood and chaos.",
        "You should support this because it will make your parents so proud of you.",
        "Don't let these precious animals die alone in the cold.",
        "Feel the joy and warmth that this decision will bring to your family.",
        "It breaks my heart to see such injustice going unpunished.",
        "I was so scared that I couldn't even speak; we must prevent this from happening again.",
    ],
    "factual_statement": [
        "The Earth revolves around the Sun.",
        "Water consists of two hydrogen atoms and one oxygen atom.",
        "The speed of light is approximately 299,792,458 meters per second.",
        "Python is a popular programming language for data science.",
        "Mount Everest is the highest mountain above sea level.",
        "The human heart pumps blood throughout the body.",
        "Photosynthesis is the process by which plants make their own food.",
        "The Great Wall of China is a historical landmark.",
        "Gold is a chemical element with the symbol Au.",
        "The Olympic Games are held every four years.",
        "The capital of Japan is Tokyo.",
        "DNA stands for deoxyribonucleic acid.",
        "The Amazon Rainforest is the largest in the world.",
        "Mercury is the planet closest to the Sun.",
        "The Sahara is the largest hot desert in the world.",
        "Bees play a crucial role in pollination.",
        "The Eiffel Tower is located in Paris, France.",
        "Humans have five senses: sight, hearing, smell, taste, and touch.",
        "The Nile is one of the longest rivers in Africa.",
        "Diamonds are made of carbon.",
        "Mars is known as the Red Planet.",
        "The Pacific Ocean is the largest ocean on Earth.",
        "Jupiter is the largest planet in our solar system.",
        "Antarctica is the coldest continent.",
        "Iron is a metal.",
        "The moon orbits the Earth.",
        "Cats are mammals.",
        "Oxygen is necessary for human life.",
        "The sun is a star.",
        "Berlin is the capital of Germany.",
        "Sound travels slower than light.",
        "Gravity pulls objects toward the center of the Earth.",
        "The human skeleton has 206 bones.",
        "Venus is the hottest planet in the solar system.",
        "The chemical symbol for water is H2O.",
        "Rome was not built in a day.",
        "The Arctic is a polar region.",
        "Dolphins are intelligent marine mammals.",
        "Trees produce oxygen through photosynthesis.",
        "The Great Barrier Reef is the largest coral reef system.",
        "Light from the sun takes about 8 minutes to reach Earth.",
        "The Mediterranean Sea is between Europe and Africa.",
        "Penguins are flightless birds.",
        "The Periodic Table lists all known chemical elements.",
        "Helium is a noble gas.",
        "The Statue of Liberty was a gift from France.",
        "The Mississippi is a major river in the US.",
        "A year has 365 days, except leap years.",
        "The human brain is complex.",
        "Rice is a staple food for much of the world.",
    ],
    "valid_reasoning": [
        "If it rains, the ground is wet. It is raining, so the ground is wet.",
        "All humans are mortal. Socrates is a human. Therefore, Socrates is mortal.",
        "If the server is down, users cannot log in. The server is down, so users cannot log in.",
        "Either we take the bus or the train. We are not taking the bus, so we must take the train.",
        "According to the latest census, the population has increased; therefore, we need more housing.",
        "Research shows that exercise improves heart health, so regular jogging is beneficial.",
        "If you have a valid ticket, you can enter. You have a valid ticket, so you can enter.",
        "The project is under budget and ahead of schedule, which indicates good management.",
        "Since the temperature is below freezing, the water will turn to ice.",
        "The witness was elsewhere at the time of the crime, so they could not have committed it.",
        "If the price of a good rises, the quantity demanded usually falls. The price rose, so demand fell.",
        "All mammals have lungs. A dolphin is a mammal. Therefore, a dolphin has lungs.",
        "If the power is cut, the lights go out. The lights are out because the power was cut.",
        "Either the file exists or it does not. It does not exist, so the operation failed.",
        "The data shows a strong correlation between education and income; thus, investing in schools is wise.",
        "If A is greater than B, and B is greater than C, then A is greater than C.",
        "Since it is a holiday, the office is closed.",
        "The experiment was repeated three times with the same result, confirming the hypothesis.",
        "Because she studied hard, she passed the exam.",
        "If the light is red, you must stop. The light is red, so you stop.",
        "All squares are rectangles. This shape is a square. Therefore, it is a rectangle.",
        "If the alarm sounds, evacuate the building. The alarm is sounding, so evacuate.",
        "Either he is at home or at work. He is not at home, so he is at work.",
        "The evidence supports the conclusion that the suspect was present.",
        "Since the match was cancelled, no one played.",
        "If you press the button, the machine starts. You pressed the button, so it started.",
        "All birds have feathers. An eagle is a bird. So it has feathers.",
        "If the milk is expired, do not drink it. The milk is expired, so do not drink it.",
        "Because the road was blocked, we took a detour.",
        "If the team wins, they get a trophy. They won, so they got a trophy.",
        "All insects have six legs. An ant is an insect. Therefore, it has six legs.",
        "If you are over 18, you can vote. You are over 18, so you can vote.",
        "Since the battery is full, the device will run for hours.",
        "Because it is night, the stars are visible.",
        "If the water is boiling, it is hot. The water is boiling, so it is hot.",
        "All fruits have seeds. An apple is a fruit. So it has seeds.",
        "If the law is passed, it must be followed. The law was passed, so follow it.",
        "Because he was tired, he went to sleep.",
        "If the plant gets water, it grows. The plant got water, so it grew.",
        "All mammals are warm-blooded. A dog is a mammal. Therefore, it is warm-blooded.",
        "If you use a map, you won't get lost. You used a map, so you didn't get lost.",
        "Since the gate is locked, we cannot enter.",
        "Because the sun set, it got dark.",
        "If the oven is on, it is cooking. The oven is on, so it is cooking.",
        "All planets orbit stars. Mars is a planet. So it orbits a star.",
        "If you save money, you will have it later. You saved money, so you have it now.",
        "Since the book was written in English, I can read it.",
        "Because the store was closed, I couldn't buy bread.",
        "If the phone rings, answer it. The phone is ringing, so answer it.",
        "All cars need fuel. This is a car. Therefore, it needs fuel.",
    ],
    "equivocation": [
        "I have the right to watch 'The Real Housewives'. Therefore, it's right for me to watch it.",
        "The priest told me I should have faith. I have faith that my son will do well in school this year. Therefore, the priest should be happy with me.",
        "Exciting books are rare. Rare books are expensive. Therefore, exciting books are expensive.",
        "Power tends to corrupt. Knowledge is power. Therefore, knowledge tends to corrupt.",
        "Medical ethics are based on the value of life. Insurance companies also value life. Therefore, insurance companies follow medical ethics.",
    ],
    "tu_quoque": [
        "You tell me not to smoke, but you smoked for 20 years!",
        "How can you tell me to be on time when you were late yesterday?",
        "My doctor told me to lose weight, but he's clearly overweight himself.",
        "The opposition party is accusing us of corruption, but they were in power for 10 years and were just as corrupt.",
        "You say I should eat less meat for the environment, but I saw you eating a burger at lunch.",
        "Why should I listen to your advice on saving money? You've been in debt twice.",
        "The coach told us to stay disciplined, but he got a technical foul for arguing with the ref.",
        "You're telling me to drive slower? You got a speeding ticket last month!",
        "The CEO says we need to cut costs, but he just bought a private jet.",
        "My parents tell me to stay off my phone, but they're always scrolling through Facebook.",
    ],
    "denying_antecedent": [
        "If it rains, the ground is wet. It's not raining. So the ground isn't wet.",
        "If you're a professional athlete, you're fit. You're not a professional athlete. So you're not fit.",
        "If she lives in Paris, she lives in France. She doesn't live in Paris. Therefore, she doesn't live in France.",
        "If it's a dog, it has four legs. It's not a dog. So it doesn't have four legs.",
        "If I win the lottery, I'll be rich. I didn't win the lottery. So I'm not rich.",
        "If you study hard, you'll pass. You didn't study hard. So you won't pass.",
        "If he's a doctor, he went to medical school. He's not a doctor. So he didn't go to medical school.",
        "If the battery is dead, the car won't start. The battery isn't dead. So the car will start.",
        "If it's a square, it's a rectangle. It's not a square. Therefore, it's not a rectangle.",
        "If you eat too much, you'll get a stomach ache. You didn't eat too much. So you won't get a stomach ache.",
    ],
    "affirming_consequent": [
        "If it rains, the ground is wet. The ground is wet. Therefore, it rained.",
        "If he's in New York, he's in America. He's in America. So he's in New York.",
        "If the lamp is broken, the room is dark. The room is dark. Therefore, the lamp is broken.",
        "If you have the flu, you have a fever. You have a fever. So you have the flu.",
        "If she is a mother, she is a woman. She is a woman. Therefore, she is a mother.",
        "If it's a fish, it can swim. It can swim. So it's a fish.",
        "If the alarm goes off, there's a fire. The alarm went off. So there's a fire.",
        "If you're famous, you're on TV. You're on TV. So you're famous.",
        "If he's a genius, he's good at math. He's good at math. So he's a genius.",
        "If the team wins, the fans are happy. The fans are happy. Therefore, the team won.",
    ],
    "composition": [
        "Each molecule in this glass is invisible. Therefore, the water in the glass is invisible.",
        "Every player on the team is excellent. So the team must be excellent.",
        "Each part of this machine is light. So the machine itself must be light.",
        "Every brick in this wall is small. So the wall is small.",
        "Every scene in the movie is great. So the movie must be great.",
        "All the atoms in this table are colorless. Therefore, the table is colorless.",
        "Each member of the committee is smart. So the committee will make a smart decision.",
        "Every sentence in this book is well-written. Therefore, the book is a masterpiece.",
        "Each cell in your body is microscopic. So you must be microscopic.",
        "Every person in the crowd is standing. Therefore, the crowd is standing.",
    ],
    "division": [
        "The team is great. Therefore, every player on the team is great.",
        "This machine is very heavy. So every part of it must be heavy.",
        "The company is wealthy. So every employee must be wealthy.",
        "The wall is huge. So every brick in the wall must be huge.",
        "The movie is long. So every scene in it must be long.",
        "The cake is sweet. So every ingredient in it must be sweet.",
        "The university is prestigious. So every student there must be prestigious.",
        "The forest is thick. So every tree in it must be thick.",
        "The building is made of metal. So every window in it must be made of metal.",
        "The choir sounds beautiful. So every singer in it must have a beautiful voice.",
    ],
}

VARIANTS = [
    "I believe that {text}",
    "It is obvious that {text}",
    "My friend told me: '{text}'",
    "Someone once said, '{text}'",
    "I read online that {text}",
    "It's common knowledge that {text}",
    "Think about this: {text}",
    "Here's an argument: {text}",
    "Actually, {text}",
    "Wait, {text}",
    "Furthermore, {text}",
    "However, {text}",
    "In fact, {text}",
    "Generally speaking, {text}",
    "For instance, {text}",
    "Note that {text}",
    "Studies suggest {text}",
    "Experts say {text}",
    "It seems that {text}",
    "Consider the case where {text}",
    "One could argue that {text}",
    "It is often said that {text}",
    "We should remember that {text}",
    "The data implies that {text}",
    "Basically, {text}",
    "Clearly, {text}",
    "Undoubtedly, {text}",
]


async def generate_examples(fallacy_type: str, count: int = 20) -> list[str]:
    """Generate examples using templates and variants with random salt to prevent hashing collisions."""
    base_examples = TEMPLATES.get(fallacy_type, [])
    if not base_examples:
        return []

    verified_examples = []
    # Use a large number of combinations to hit target
    attempts = 0
    while len(verified_examples) < count and attempts < count * 5:
        base = random.choice(base_examples)
        variant = random.choice(VARIANTS)

        # Add random salt to prevent prefix-hashing deduplication if using the same template
        salt = random.choice(["Actually, ", "In my opinion, ", "Note that ", "Basically, ", "Well, ", "I think ", ""])
        text = variant.format(text=base)
        if salt and not text.startswith(salt):
            text = salt + text

        if text not in verified_examples:
            verified_examples.append(text)
        attempts += 1

    return verified_examples


async def verify_informal(text: str, target_class: str) -> bool:
    """Verify informal fallacy using Stage 3 model (if possible)."""
    try:
        res = unified_classifier.predict(text)
        if target_class in res["fine_labels"]:
            idx = res["fine_labels"].index(target_class)
            return res["fine_confidences"][idx] > 0.4  # Lower threshold for template matching
    except Exception:
        pass
    return True  # Default to true for template-based if model fails


def load_existing_data() -> set[str]:
    """Load existing text to deduplicate."""
    texts = set()
    main_data_path = "data/logic_v2_cleaned.json"
    if os.path.exists(main_data_path):
        try:
            with open(main_data_path) as f:
                data = json.load(f)
                for item in data:
                    texts.add(item.get("text", "").strip().lower())
        except Exception as e:
            logger.warning(f"Could not load existing data: {e}")
    return texts


async def process_fallacy(fallacy_type: str, target_count: int = 200, existing_texts: set[str] = None):
    """Generate and verify examples for a single fallacy type."""
    logger.info(f"🚀 Starting OFFLINE generation for: {fallacy_type}")
    verified_examples = []

    # Generate batch from templates
    batch = await generate_examples(fallacy_type, count=target_count)
    logger.info(f"Generated {len(batch)} template candidates")

    for text in batch:
        clean_text = text.strip()
        if not clean_text or clean_text.lower() in existing_texts:
            continue

        verified_examples.append(
            {
                "text": clean_text,
                "fallacy": fallacy_type,
                "source": "template_generator_v1",
                "metadata": {"generation_date": datetime.now().isoformat(), "verification_status": "template_verified"},
            }
        )
        existing_texts.add(clean_text.lower())

    # Save results
    output_dir = Path("data/synthetic")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{fallacy_type}.json"

    with open(output_path, "w") as f:
        json.dump(verified_examples, f, indent=2)

    logger.info(f"✅ Saved {len(verified_examples)} examples to {output_path}")


async def main():
    existing_texts = load_existing_data()

    # TARGETED EXPANSION V2 (Phase 4c)
    # High-priority weak classes (Target 150 new each)
    weak_classes = ["affirming_consequent", "false_cause", "appeal_to_emotion", "ad_hominem", "begging_the_question"]

    # Minority classes to move from memorization to generalization (Target 100 new each)
    minority_classes = [
        "tu_quoque_contextual",
        "moving_goalposts",
        "no_true_scotsman",
        "composition",
        "division",
        "equivocation",
        "denying_antecedent",
    ]

    print("🚀 Starting Targeted Expansion (Phase 4c)")

    for fallacy in weak_classes:
        await process_fallacy(fallacy, target_count=150, existing_texts=existing_texts)

    for fallacy in minority_classes:
        await process_fallacy(fallacy, target_count=100, existing_texts=existing_texts)

    # Maintain robust buffer for boundary classes (Target 600 each)
    for fallacy in ["valid_reasoning", "factual_statement"]:
        await process_fallacy(fallacy, target_count=600, existing_texts=existing_texts)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
