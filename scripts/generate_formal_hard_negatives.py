import argparse
import json
import random
from collections import Counter

DOMAINS = {
    "Legal": [
        "statute",
        "precedent",
        "clause",
        "defendant",
        "plaintiff",
        "jurisdiction",
        "liability",
        "verdict",
        "witness",
        "affidavit",
        "testimony",
        "injunction",
    ],
    "Science": [
        "hypothesis",
        "variable",
        "empirical",
        "correlation",
        "entropy",
        "spectrum",
        "protocol",
        "catalyst",
        "isotope",
        "mutation",
        "photosynthesis",
        "particle",
    ],
    "Medicine": [
        "diagnosis",
        "prognosis",
        "symptom",
        "efficacy",
        "contraindication",
        "dosage",
        "pathogen",
        "antibody",
        "metabolism",
        "pathway",
        "biopsy",
        "remission",
    ],
    "Programming": [
        "function",
        "recursion",
        "asynchronous",
        "deployment",
        "dependency",
        "latency",
        "schema",
        "endpoint",
        "middleware",
        "cache",
        "thread",
        "callback",
    ],
    "Engineering": [
        "structural",
        "load-bearing",
        "torque",
        "tolerance",
        "redundancy",
        "aerodynamics",
        "prototype",
        "actuator",
        "calibration",
        "damping",
        "pipeline",
        "manifold",
    ],
    "Politics": [
        "policy",
        "constituency",
        "legislation",
        "diplomacy",
        "sanction",
        "referendum",
        "partisan",
        "mandate",
        "ratification",
        "appropriation",
        "filibuster",
        "jurisprudence",
    ],
    "Education": [
        "pedagogy",
        "curriculum",
        "assessment",
        "literacy",
        "cognition",
        "standardized",
        "didactic",
        "placement",
        "accreditation",
        "syllabus",
        "remediation",
        "rubric",
    ],
    "Philosophy": [
        "ontology",
        "epistemology",
        "dialectic",
        "axiom",
        "categorical",
        "solipsism",
        "ethics",
        "noumenon",
        "teleology",
        "deontology",
        "relativism",
        "naturalism",
    ],
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
    "I believe that ",
    "It is obvious that ",
    "My friend told me: '",
    "Someone once said, '",
    "I read online that ",
    "It's common knowledge that ",
    "Think about this: ",
    "Here's an argument: ",
    "Actually, ",
    "Furthermore, ",
    "However, ",
    "In fact, ",
    "Generally speaking, ",
    "For instance, ",
    "Note that ",
    "Studies suggest ",
    "Experts say ",
    "It seems that ",
    "Consider the case where ",
    "One could argue that ",
    "It is often said that ",
    "We should remember that ",
    "The data implies that ",
    "Basically, ",
    "Clearly, ",
    "Undoubtedly, ",
]


def pick_domain():
    domain = random.choice(list(DOMAINS.keys()))
    v = list(DOMAINS[domain])
    random.shuffle(v)
    return domain, v


# ── Formal Fallacy Templates (existing) ───────────────────────────────────────


def gen_undistributed_middle():
    domain, v = pick_domain()
    templates = [
        f"All {v[0]}s are {v[1]}s. All {v[2]}s are {v[1]}s. Therefore, all {v[0]}s are {v[2]}s.",
        f"Every {v[0]} is classified as a {v[1]}. Every {v[2]} is also a {v[1]}. So every {v[0]} must be a {v[2]}.",
        f"All {v[0]}s possess the property of being {v[1]}. All {v[2]}s also possess {v[1]}. Hence, all {v[0]}s are {v[2]}s.",
        f"In {domain}, every instance of {v[0]} is a {v[1]}. Also, every {v[2]} is a {v[1]}. Therefore, every {v[0]} is a {v[2]}.",
        f"Anything that is a {v[0]} is necessarily a {v[1]}. And anything that is a {v[2]} is also a {v[1]}. So anything that is a {v[0]} must be a {v[2]}.",
        f"All observed {v[0]}s fall under the category of {v[1]}. Similarly, all {v[2]}s fall under {v[1]}. Thus, all {v[0]}s are actually {v[2]}s.",
        f"A {v[0]} shares the trait {v[1]} with a {v[2]}. Since both are {v[1]}, it follows that a {v[0]} is a {v[2]}.",
        f"Every {v[0]} that has been tested is {v[1]}. And every {v[2]} that has been tested is also {v[1]}. Therefore, every {v[0]} is a {v[2]}.",
        f"By definition, a {v[0]} is a type of {v[1]}. And a {v[2]} is also a type of {v[1]}. This proves that a {v[0]} is the same as a {v[2]}.",
        f"The class of {v[0]}s is a subclass of {v[1]}s. The class of {v[2]}s is also a subclass of {v[1]}s. So the class of {v[0]}s must be the same as the class of {v[2]}s.",
        f"In {domain} practice, both {v[0]} and {v[2]} are considered forms of {v[1]}. Therefore, any {v[0]} is effectively a {v[2]}.",
        f"All documented cases of {v[0]} involve {v[1]}. All documented cases of {v[2]} also involve {v[1]}. Consequently, {v[0]} is really a subtype of {v[2]}.",
    ]
    return random.choice(templates)


def gen_illicit_major():
    domain, v = pick_domain()
    templates = [
        f"All {v[0]}s are {v[1]}s. No {v[2]} is a {v[0]}. Therefore, no {v[2]} is a {v[1]}.",
        f"Every {v[0]} qualifies as a {v[1]}. Not a single {v[2]} is a {v[0]}. So no {v[2]} qualifies as a {v[1]}.",
        f"All known {v[0]} cases involve {v[1]}. Yet no {v[2]} is a {v[0]}. Hence, no {v[2]} involves {v[1]}.",
        f"In {domain}, every {v[0]} requires {v[1]}. But the {v[2]} does not contain any {v[0]}. Therefore, the {v[2]} does not require {v[1]}.",
        f"Each {v[0]} in the study exhibited {v[1]}. However, the {v[2]} was not a {v[0]}. Thus, the {v[2]} could not exhibit {v[1]}.",
        f"Every instance of a {v[0]} demonstrates {v[1]}. Since this {v[2]} is not an instance of a {v[0]}, it cannot demonstrate {v[1]}.",
        f"All certified {v[0]}s possess credential {v[1]}. This candidate is not a certified {v[0]}. Therefore, this candidate lacks credential {v[1]}.",
        f"In every trial where a {v[0]} was used, {v[1]} was observed. The current configuration has no {v[0]}. So {v[1]} will not be observed.",
        f"Any system with a {v[0]} will produce {v[1]}. This system does not contain a {v[0]}. Hence, it will not produce {v[1]}.",
        f"All patients with {v[0]} show elevated {v[1]}. This patient does not have {v[0]}. Therefore, this patient does not show elevated {v[1]}.",
        f"Every protocol that uses {v[0]} achieves {v[1]}. Our protocol does not use {v[0]}. So it will not achieve {v[1]}.",
        f"All jurisdictions that enacted statute {v[0]} saw an increase in {v[1]}. Our jurisdiction did not enact {v[0]}. Thus, we will not see an increase in {v[1]}.",
    ]
    return random.choice(templates)


def gen_illicit_minor():
    domain, v = pick_domain()
    templates = [
        f"All {v[0]}s are {v[1]}s. All {v[0]}s are {v[2]}s. Therefore, all {v[2]}s are {v[1]}s.",
        f"Every {v[0]} has property {v[1]}. Also, every {v[0]} has property {v[2]}. Thus, everything with property {v[2]} has property {v[1]}.",
        f"All {v[0]} in the dataset are tagged as {v[1]}. All {v[0]} in the dataset are also tagged as {v[2]}. Consequently, everything tagged as {v[2]} is {v[1]}.",
        f"In {domain}, any {v[0]} is a {v[1]}. Furthermore, any {v[0]} is also a {v[2]}. Therefore, any {v[2]} is necessarily a {v[1]}.",
        f"All verified {v[0]}s meet standard {v[1]}. All verified {v[0]}s also meet standard {v[2]}. So anything meeting standard {v[2]} must meet standard {v[1]}.",
        f"Every {v[0]} certified in {domain} passed the {v[1]} exam. Every {v[0]} also passed the {v[2]} exam. Therefore, anyone who passed the {v[2]} exam passed the {v[1]} exam.",
        f"All applications using {v[0]} require {v[1]}. All applications using {v[0]} also require {v[2]}. Hence, any application requiring {v[2]} requires {v[1]}.",
        f"Every study of {v[0]} confirmed the role of {v[1]}. Every study of {v[0]} also confirmed the role of {v[2]}. Thus, any study confirming {v[2]} confirms {v[1]}.",
        f"All buildings with {v[0]} installed have {v[1]}. All buildings with {v[0]} installed also have {v[2]}. Therefore, any building with {v[2]} has {v[1]}.",
        f"Each participant who received {v[0]} showed improvement in {v[1]}. Each participant who received {v[0]} also showed improvement in {v[2]}. So anyone showing improvement in {v[2]} improved in {v[1]}.",
        f"Every implementation of {v[0]} relies on {v[1]}. Every implementation of {v[0]} also relies on {v[2]}. Consequently, any implementation relying on {v[2]} relies on {v[1]}.",
        f"All policies that include {v[0]} mandate {v[1]}. All policies that include {v[0]} also mandate {v[2]}. Hence, any policy mandating {v[2]} must mandate {v[1]}.",
    ]
    return random.choice(templates)


def gen_exclusive_premises():
    domain, v = pick_domain()
    templates = [
        f"No {v[0]} is a {v[1]}. No {v[2]} is a {v[0]}. Therefore, no {v[2]} is a {v[1]}.",
        f"Not a single {v[0]} qualifies as a {v[1]}. And no {v[2]} qualifies as a {v[0]}. So no {v[2]} qualifies as a {v[1]}.",
        f"There are no {v[0]}s that are {v[1]}. Furthermore, there are no {v[2]}s that are {v[0]}. Hence, there are no {v[2]}s that are {v[1]}.",
        f"In {domain}, no {v[0]} counts as {v[1]}. Also, no {v[2]} counts as {v[0]}. So no {v[2]} counts as {v[1]}.",
        f"A {v[0]} is never a {v[1]}. A {v[2]} is never a {v[0]}. Therefore, a {v[2]} is never a {v[1]}.",
        f"No known {v[0]} exhibits {v[1]}. No known {v[2]} is a {v[0]}. Thus, no known {v[2]} exhibits {v[1]}.",
        f"None of the {v[0]} samples tested positive for {v[1]}. None of the {v[2]} samples tested positive for {v[0]}. Therefore, none of the {v[2]} samples test positive for {v[1]}.",
        f"Zero {v[0]}s in the registry are classified as {v[1]}. Zero {v[2]}s are classified as {v[0]}. Consequently, zero {v[2]}s are classified as {v[1]}.",
        f"No evidence links {v[0]} to {v[1]}. No evidence links {v[2]} to {v[0]}. Hence, no evidence links {v[2]} to {v[1]}.",
        f"There is no situation where a {v[0]} is also a {v[1]}. There is no situation where a {v[2]} is also a {v[0]}. So there is no situation where a {v[2]} is also a {v[1]}.",
        f"Not one {v[0]} in {domain} history was found to be {v[1]}. Not one {v[2]} was ever found to be a {v[0]}. Therefore, no {v[2]} can ever be {v[1]}.",
        f"No patient with {v[0]} showed {v[1]}. No patient with {v[2]} showed {v[0]}. So no patient with {v[2]} will show {v[1]}.",
    ]
    return random.choice(templates)


def gen_existential_fallacy():
    domain, v = pick_domain()
    templates = [
        f"All {v[0]}s have the property {v[1]}. Therefore, some {v[0]}s have the property {v[1]}.",
        f"Every {v[0]} in existence is capable of {v[1]}. Hence, there exists at least one {v[0]} capable of {v[1]}.",
        f"All {v[0]}s are {v[1]}s. So there must be some {v[0]}s that are {v[1]}s.",
        f"In {domain}, every known {v[0]} involves {v[1]}. Therefore, there are some {v[0]}s that involve {v[1]}.",
        f"All forms of {v[0]} require {v[1]}. Thus, at least one form of {v[0]} requires {v[1]}.",
        f"Every {v[0]} that meets the criteria will produce {v[1]}. So some {v[0]} will produce {v[1]}.",
        f"All instances of {v[0]} exhibit {v[1]}. This proves that there exist instances of {v[0]} that exhibit {v[1]}.",
        f"Any {v[0]} in the {domain} sector is subject to {v[1]}. Therefore, there exists a {v[0]} subject to {v[1]}.",
        f"All documented {v[0]} procedures include step {v[1]}. Consequently, some {v[0]} procedure includes step {v[1]}.",
        f"Every country that adopts {v[0]} also adopts {v[1]}. So some country must adopt {v[1]}.",
        f"Wherever {v[0]} is found, {v[1]} is also present. So there is somewhere {v[1]} is present.",
        f"All implementations of {v[0]} depend on {v[1]}. Hence, there exists an implementation of {v[0]} that depends on {v[1]}.",
    ]
    return random.choice(templates)


def gen_denying_antecedent_hard():
    domain, v = pick_domain()
    templates = [
        f"If the {v[0]} is properly configured, the {v[1]} will pass validation. The {v[0]} is not properly configured. So the {v[1]} will not pass validation.",
        f"When a patient presents with {v[0]}, we typically prescribe {v[1]}. This patient does not present with {v[0]}. Therefore, we should not prescribe {v[1]}.",
        f"Whenever the {v[0]} exceeds the {v[1]}, a system alert is triggered. The {v[0]} did not exceed the {v[1]}. So no system alert was triggered.",
        f"If the court rules in favor of the {v[0]}, then the {v[1]} will be overturned. The court did not rule in favor of the {v[0]}. Therefore, the {v[1]} will not be overturned.",
        f"In {domain}, if the {v[0]} test yields positive, then the {v[1]} is indicated. The {v[0]} test did not yield positive. So the {v[1]} is not indicated.",
        f"Should the {v[0]} committee approve the {v[1]}, then funding will be allocated for {v[2]}. The committee did not approve the {v[1]}. Hence, funding will not be allocated for {v[2]}.",
        f"If the {v[0]} is compiled with optimization flag {v[1]}, it will process {v[2]} efficiently. The {v[0]} was not compiled with {v[1]}. So it will not process {v[2]} efficiently.",
        f"Whenever a {v[0]} implements protocol {v[1]}, the {v[2]} rate drops below the threshold. This {v[0]} does not implement {v[1]}. Thus, the {v[2]} rate remains above threshold.",
        f"If the {v[0]} is ratified by the legislature, then the {v[1]} will receive full funding. The legislature did not ratify the {v[0]}. So the {v[1]} will not receive full funding.",
        f"Patients who receive {v[0]} show a marked increase in {v[1]} within two weeks. This patient did not receive {v[0]}. Therefore, they will not show an increase in {v[1]}.",
        f"When a {v[0]} meets the {v[1]} standard, it qualifies for {v[2]} certification. This {v[0]} does not meet the {v[1]} standard. Hence, it does not qualify for {v[2]} certification.",
        f"If the {v[0]} passes the stress test, the {v[1]} is considered safe for deployment. The {v[0]} did not pass the stress test. So the {v[1]} is not safe for deployment.",
    ]
    return random.choice(templates)


def gen_composition_hard():
    domain, v = pick_domain()
    templates = [
        f"Every component in this {v[0]} system is manufactured in {v[1]}. Therefore, the entire {v[0]} system was manufactured in {v[1]}.",
        f"Each section of the {domain} pipeline passed inspection individually. So the pipeline as a whole passed inspection.",
        f"Every clause in the {v[0]} agreement is written in plain English. Therefore, the entire {v[0]} agreement is easy to understand.",
        f"Each student in the {v[0]} program scored above 90 on the {v[1]} assessment. So the {v[0]} program as a whole scored above 90.",
        f"Every module in the {v[0]} is memory-safe. Therefore, the entire {v[0]} application is memory-safe.",
        f"All witnesses in the {v[0]} trial gave consistent testimony. So the {v[0]} trial as a whole had consistent witness testimony.",
        f"Each node in the {v[0]} cluster runs independently. Hence, the {v[0]} cluster runs independently as a whole.",
        f"Each atom in the {v[0]} molecule has been identified. Therefore, the {v[0]} molecule has been fully identified.",
        f"All members of the {v[0]} committee share the same opinion on {v[1]}. Therefore, the {v[0]} committee has a unified opinion on {v[1]}.",
        f"Each prescription under the {v[0]} protocol is effective. Thus, the {v[0]} protocol as a whole is effective.",
        f"Each door in the {v[0]} building is fire-resistant. So the entire {v[0]} building is fire-resistant.",
        f"All sentences in the {v[0]} document are grammatically correct. Therefore, the {v[0]} document as a whole is grammatically correct.",
    ]
    return random.choice(templates)


def gen_division_hard():
    domain, v = pick_domain()
    templates = [
        f"The {v[0]} pipeline processes {v[1]} very efficiently. So each stage of the pipeline must process {v[1]} efficiently.",
        f"This {domain} study produced groundbreaking results. Therefore, every data point in the study must be groundbreaking.",
        f"The {v[0]} treaty is beneficial for all signatories. Hence, every clause in the treaty must be beneficial.",
        f"The {v[0]} codebase is well-optimized. Thus, every function in the codebase must be well-optimized.",
        f"This {v[0]} patient group showed remarkable improvement. So each individual patient in the group showed remarkable improvement.",
        f"The {v[0]} organization is highly profitable. Consequently, every department within it is highly profitable.",
        f"The {v[0]} curriculum is rigorous and demanding. So each course in the curriculum must be rigorous and demanding.",
        f"The {v[0]} ecosystem is fragile. Therefore, every species within it must be fragile.",
        f"The {v[0]} bridge design is structurally sound. Hence, every beam in the design is structurally sound.",
        f"The {v[0]} argument is logically flawless. Thus, each premise in the argument must be logically flawless.",
        f"The {v[0]} software suite is user-friendly. So every application in the suite must be user-friendly.",
        f"The {v[0]} court ruling sets an important precedent. Therefore, every section of the ruling sets an important precedent.",
    ]
    return random.choice(templates)


def gen_equivocation_hard():
    domain, v = pick_domain()
    templates = [
        f"The {v[0]} is light. Things that are light cannot be dark. So the {v[0]} cannot be dark.",
        f"The {v[0]} argument has no substance. A thing without substance cannot be physically touched. Therefore, the {v[0]} argument cannot be physically touched.",
        f"The {v[0]} program runs perfectly. A runner runs fast. Therefore, the {v[0]} program runs fast.",
        "Justice is blind. Helen Keller was blind. Therefore, Helen Keller had perfect justice.",
        f"The {v[0]} circuit has a short. Short people are not tall. So the {v[0]} circuit is not tall.",
        f"The {v[0]} proposal was approved by the board. Food that is approved by the board is delicious. Hence, the {v[0]} proposal is delicious.",
        f"The {v[0]} system crashed. A crashed system cannot operate. Therefore, the {v[0]} system cannot operate a vehicle.",
        f"The {v[0]} contains a virus. A virus can infect living cells. So the {v[0]} can infect living cells.",
        f"The {v[0]} battery is dead. A dead person cannot walk. Thus, the {v[0]} battery cannot walk.",
        f"The {v[0]} source code is embedded. Something embedded is hard to remove. So the {v[0]} source code is hard to remove from its context.",
        f"The {v[0]} function returns a value. A return flight goes back. So the {v[0]} function goes back.",
        f"The {v[0]} argument is valid until midnight. A valid passport lets you travel. Therefore, the {v[0]} argument lets you travel until midnight.",
    ]
    return random.choice(templates)


# ── Near-Miss Hard Negative Templates ─────────────────────────────────────────


def gen_correlation_causation():
    domain, v = pick_domain()
    templates = [
        f"It seems like {v[0]} causes {v[1]} because {v[1]} often appears alongside {v[0]}. So we should treat {v[0]} as the cause of {v[1]}.",
        f"{v[1]} increased whenever we adjusted {v[0]}. Therefore, {v[0]} must be driving the change in {v[1]}.",
        f"Every time a {v[0]} is present in the system, {v[1]} follows shortly after. This confirms that {v[0]} leads to {v[1]}.",
        f"Patients with high {v[0]} levels also have high {v[1]} levels. Therefore, {v[0]} elevates {v[1]}.",
        f"Since {v[0]} and {v[1]} are strongly correlated in the dataset, adjusting {v[0]} will directly change {v[1]}.",
        f"All observed cases show that {v[0]} and {v[1]} move together. There is no doubt that {v[0]} is the cause of {v[1]}.",
        f"The {v[0]} reading spiked at the same time as the {v[1]} reading. So the {v[0]} spike triggered the {v[1]} spike.",
        f"Wherever we see high {v[0]} adoption, we also see high {v[1]}. This means {v[0]} adoption produces {v[1]}.",
        f"In every documented instance, {v[0]} preceded {v[1]}. Therefore, {v[0]} must have caused {v[1]}.",
        f"Countries with more {v[0]} per capita also have more {v[1]}. So increasing {v[0]} will increase {v[1]}.",
        f"The {v[1]} metric improved right after the {v[0]} change was introduced. The {v[0]} change is therefore responsible.",
        f"Data shows a clear pattern: when {v[0]} is high, {v[1]} is also high. This proves {v[0]} causes {v[1]}.",
    ]
    return random.choice(templates)


def gen_bandwagon():
    domain, v = pick_domain()
    templates = [
        f"Everyone in the {domain} field agrees that {v[0]} is the most effective approach. It is simply the right choice.",
        f"All leading institutions have adopted {v[0]}. There is no reason to question its validity.",
        f"The vast majority of professionals recommend {v[0]} for {v[1]}. That settles the matter.",
        f"People everywhere are switching to {v[0]}. You should too if you care about results.",
        f"Every reputable organization endorses the {v[0]} standard. The debate is over.",
        f"No one seriously disputes that {v[0]} is superior to {v[1]}. The consensus is overwhelming.",
        f"All the top performers in {domain} rely on {v[0]}. That alone should convince you.",
        f"It is widely accepted that {v[0]} leads to {v[1]}. Only a fringe few would deny it.",
        f"The whole industry has moved to {v[0]}. It would be foolish to stick with alternatives.",
        f"Public opinion is clear: {v[0]} is what we need. Politicians should listen to the people.",
        f"Every expert in the room nodded when {v[0]} was mentioned. That is all the evidence required.",
        f"Join the millions who trust {v[0]}. You will not regret it.",
    ]
    return random.choice(templates)


def gen_argument_ignorance():
    domain, v = pick_domain()
    templates = [
        f"No one has ever proved that {v[0]} does not cause {v[1]}. Therefore, {v[0]} must cause {v[1]}.",
        f"Scientists cannot explain why {v[0]} occurs. Hence, their theories about {v[1]} must be wrong.",
        f"There is no evidence against {v[0]}. So we should accept it as true.",
        f"After years of research, nobody has disproven the link between {v[0]} and {v[1]}. This confirms the link exists.",
        f"Critics have failed to provide a counterexample to {v[0]}. Therefore, {v[0]} is correct.",
        f"Since no study has conclusively ruled out {v[0]}, we must assume it is a real phenomenon.",
        f"You cannot prove that {v[0]} is ineffective. Therefore, you should use {v[0]}.",
        f"The defense presented no evidence that the {v[0]} was not compromised. So it must have been compromised.",
        f"No one has demonstrated that {v[0]} fails in practice. We should therefore deploy it widely.",
        f"Until someone shows me a better alternative to {v[0]}, I will stick with it as the correct solution.",
        f"The {v[0]} hypothesis has never been falsified in any experiment. It must be true.",
        f"Nobody has ever observed a case where {v[0]} did not lead to {v[1]}. So {v[0]} always leads to {v[1]}.",
    ]
    return random.choice(templates)


def gen_false_dichotomy():
    domain, v = pick_domain()
    templates = [
        f"If you cannot provide a complete explanation for {v[0]}, then {v[0]} must be incorrect.",
        f"Either you accept the {v[0]} framework, or you reject all progress in {domain}. There is no middle ground.",
        f"You are either with the {v[0]} initiative or you are against {v[1]}. Choose wisely.",
        f"Since the {v[0]} model does not perfectly predict {v[1]}, the entire model is useless.",
        f"Not everyone supports the {v[0]} proposal, which means the proposal is fundamentally flawed.",
        f"If {v[0]} were true, we would have perfect results. The results are imperfect, so {v[0]} is false.",
        f"The {v[0]} approach did not solve every problem, so we must abandon it entirely.",
        f"You either believe in {v[0]} or you believe in {v[1]}. They are mutually exclusive.",
        f"Since we cannot guarantee {v[0]} will work in every scenario, we should not use it at all.",
        f"If the {v[0]} test is not 100% accurate, then it has no value whatsoever.",
        f"The {v[0]} policy either benefits everyone or it benefits no one. These are the only possibilities.",
        f"Either {v[0]} is the complete answer, or it is worthless. Partial truths do not exist.",
    ]
    return random.choice(templates)


def gen_appeal_intuition():
    domain, v = pick_domain()
    templates = [
        f"It is obvious that {v[0]} leads to {v[1]}. Anyone can see the connection.",
        f"Just think about it. {v[0]} clearly must be the correct approach in {domain}.",
        f"Any reasonable person would agree that {v[0]} is better than {v[1]}. It is common sense.",
        f"The truth of {v[0]} is self-evident. No further proof is needed.",
        f"You do not need a study to know that {v[0]} works. It is plain to see.",
        f"Intuition alone tells us that {v[0]} cannot possibly be effective for {v[1]}.",
        f"Everyone knows deep down that {v[0]} is the right thing to do. The logic is obvious.",
        f"Look at the situation. It is clear as day that {v[0]} is the cause of {v[1]}.",
        f"We do not need data to decide this. Any person with common sense prefers {v[0]}.",
        f"It stands to reason that {v[0]} will improve {v[1]}. That is just basic logic.",
        f"Ask anyone on the street and they will tell you {v[0]} is the best option. It is intuitive.",
        f"The connection between {v[0]} and {v[1]} is obvious to anyone who thinks about it.",
    ]
    return random.choice(templates)


def gen_vague_authority():
    domain, v = pick_domain()
    templates = [
        f"Most experts in {domain} agree that {v[0]} is the best approach for achieving {v[1]}.",
        f"Leading scientists believe that {v[0]} plays a key role in {v[1]}. That should be enough.",
        f"Professionals across the field recommend {v[0]} over all other options.",
        f"According to top researchers, {v[0]} has been proven to cause {v[1]}.",
        f"Specialists universally acknowledge that {v[0]} is superior to the alternatives.",
        f"Authorities in {domain} have stated that {v[0]} should be the standard practice.",
        f"Expert opinion overwhelmingly supports the use of {v[0]} for treating {v[1]}.",
        f"The foremost minds in the discipline endorse {v[0]} without reservation.",
        f"Qualified professionals have determined that {v[0]} is necessary for proper {v[1]}.",
        f"Veteran practitioners always choose {v[0]} when faced with {v[1]}. That speaks volumes.",
        f"Industry leaders all point to {v[0]} as the key factor in achieving {v[1]}.",
        f"Recognized authorities in {domain} confirm that {v[0]} is the only viable solution.",
    ]
    return random.choice(templates)


def gen_appeal_nature():
    domain, v = pick_domain()
    templates = [
        f"{v[0]} is completely natural, so it must be beneficial for {v[1]}.",
        f"Synthetic alternatives to {v[0]} are unnatural. Therefore, {v[0]} is the healthier choice.",
        f"Since {v[0]} occurs naturally in the {domain} process, it is inherently good.",
        f"Artificial {v[1]} cannot compare to natural {v[0]}. Nature knows best.",
        f"The body naturally produces {v[0]} in response to {v[1]}. This proves it is the intended solution.",
        f"People have been using {v[0]} since ancient times without processing. It must be superior.",
        f"A natural {v[0]} is always preferable to a manufactured one. That is just how things work.",
        f"Because {v[0]} is derived from natural sources, it has no negative side effects.",
        f"The natural state of {v[0]} is to promote {v[1]}. We should not interfere with that.",
        f"Organic {v[0]} is better because it is closer to what nature intended for {v[1]}.",
        f"Nature has optimized {v[0]} over millions of years. Human-made alternatives cannot compete.",
        f"Since {v[0]} is a natural component of {domain} ecosystems, it is automatically safe and effective.",
    ]
    return random.choice(templates)


def gen_appeal_tradition():
    domain, v = pick_domain()
    templates = [
        f"People have believed in {v[0]} for centuries. That kind of enduring truth cannot be wrong.",
        f"Our ancestors always relied on {v[0]} for {v[1]}. We should continue that tradition.",
        f"The {v[0]} method has been passed down through generations. It has stood the test of time.",
        f"For as long as anyone can remember, {v[0]} has been the standard approach in {domain}.",
        f"Traditional wisdom holds that {v[0]} is essential for {v[1]}. Who are we to question it?",
        f"This {v[0]} practice has survived for hundreds of years. That alone validates its correctness.",
        f"Every culture throughout history has valued {v[0]}. There must be a universal truth behind it.",
        f"The {v[0]} technique dates back to our grandparents' time. It is proven by long usage.",
        f"Ancient texts all describe {v[0]} as the key to {v[1]}. We should respect that knowledge.",
        f"Since {v[0]} has been the accepted norm for generations, changing it would be a mistake.",
        f"Our predecessors built entire systems around {v[0]}. They cannot all have been wrong.",
        f"The fact that {v[0]} has been practiced continuously for so long is the strongest evidence for it.",
    ]
    return random.choice(templates)


def gen_slippery_slope():
    domain, v = pick_domain()
    templates = [
        f"If we allow {v[0]}, then {v[1]} will inevitably follow. And we all know {v[1]} is unacceptable.",
        f"Adopting {v[0]} will lead directly to {v[1]}. Before long, the entire {domain} system will collapse.",
        f"Once you approve {v[0]} for one case, you will have to approve it for everything. There is no stopping it.",
        f"Allowing {v[0]} in our {domain} practice is the first step toward complete deregulation.",
        f"If {v[0]} becomes accepted, then {v[1]} is sure to happen. History shows this pattern clearly.",
        f"Starting with {v[0]} might seem harmless, but it will trigger a cascade ending in total disaster.",
        f"The moment we permit {v[0]}, we open the door to {v[1]}. That door cannot be closed again.",
        f"Every time a society accepted {v[0]}, it eventually led to {v[1]}. We must not repeat that mistake.",
        f"Adopting {v[0]} means accepting {v[1]} down the line. There are no exceptions to this progression.",
        f"If this {v[0]} policy passes, the next step will be {v[1]}, and finally the complete erosion of standards.",
        f"The {v[0]} initiative is a slippery slope. Before you know it, {v[1]} will be rampant.",
        f"Once we normalize {v[0]}, there is nothing to stop {v[1]} from taking over completely.",
    ]
    return random.choice(templates)


def gen_weasel_wording():
    domain, v = pick_domain()
    templates = [
        f"Some people say that {v[0]} affects {v[1]}, and they might have a point. We should consider it.",
        f"There are those who believe {v[0]} is connected to {v[1]}. It is worth thinking about.",
        f"Certain voices in {domain} suggest that {v[0]} may be relevant. Who knows, they could be right.",
        f"I have heard it said that {v[0]} causes {v[1]}. It is not impossible.",
        f"Rumors have been circulating that {v[0]} plays a role in {v[1]}. There could be some truth to that.",
        f"Some researchers hint that {v[0]} and {v[1]} might be related. We cannot rule it out.",
        f"A few commentators have raised the possibility that {v[0]} is behind {v[1]}. Time will tell.",
        f"People are starting to wonder whether {v[0]} has an effect on {v[1]}. It is an open question.",
        f"There is a growing sentiment that {v[0]} matters for {v[1]}. Perhaps we should take it seriously.",
        f"One hears occasionally that {v[0]} influences {v[1]}. Grain of salt, but still.",
        f"The idea that {v[0]} is tied to {v[1]} has been floated by a few observers. Might be worth exploring.",
        f"Some claim that {v[0]} makes a difference in {v[1]}. We cannot say for sure either way.",
    ]
    return random.choice(templates)


def gen_common_sense():
    domain, v = pick_domain()
    templates = [
        f"It is just common sense that {v[0]} leads to {v[1]}. You do not need a study to figure that out.",
        f"Any person with basic common sense knows that {v[0]} is the right choice for {v[1]}.",
        f"Common sense tells us that if {v[0]} increases, {v[1]} will decrease. That is obvious.",
        f"Applying a little common sense here: {v[0]} simply cannot work for {v[1]}. It is obvious.",
        f"Come on, use your common sense. Everyone knows that {v[0]} is better than the alternatives.",
        f"It defies common sense to believe that {v[0]} has no effect on {v[1]}. The connection is clear.",
        f"Common sense alone should tell you that {v[0]} is the best approach in {domain}.",
        f"You do not need fancy data to see that {v[0]} will improve {v[1]}. It is just common sense.",
        f"Let us be sensible here. Any reasonable person would choose {v[0]} over {v[1]}.",
        f"Basic common sense dictates that if you want better {v[1]}, you should invest in {v[0]}.",
        f"It is common knowledge that {v[0]} matters most for success in {domain}. That is just the way it is.",
        f"Common sense says that without {v[0]}, you cannot achieve {v[1]}. It is that simple.",
    ]
    return random.choice(templates)


def gen_ad_hominem():
    domain, v = pick_domain()
    templates = [
        f"My opponent argues that {v[0]} is ineffective, but they have a financial stake in {v[1]}. Ignore them.",
        f"Critics of {v[0]} are just bitter because their own projects failed. Their opinion is worthless.",
        f"The person claiming {v[0]} does not work has no real experience in {domain}. Dismiss their argument.",
        f"Those who oppose {v[0]} are clearly biased by their ties to the {v[1]} industry.",
        f"Our competitor says {v[0]} is flawed. Of course they would say that they are trying to sell their own product.",
        f"The researcher who questions {v[0]} was funded by groups that oppose {v[1]}. Their findings are suspect.",
        f"People who doubt {v[0]} simply lack the technical background to understand it properly.",
        f"The only voices against {v[0]} come from people who have never worked in {domain}. They do not know what they are talking about.",
        f"That politician opposes {v[0]} but they accepted donations from {v[1]} lobbyists. Clearly their stance is bought.",
        f"My colleague doubts {v[0]} will work, but they are known to be overly pessimistic about everything.",
        f"Anyone who questions {v[0]} is just trying to slow down progress. Do not listen to them.",
        f"The critic has no credentials in {domain} and has never published on {v[1]}. Their opinion carries no weight.",
    ]
    return random.choice(templates)


# ── Near-Miss Registry ────────────────────────────────────────────────────────

NEAR_MISS_FUNCTIONS = {
    "correlation_causation": gen_correlation_causation,
    "bandwagon": gen_bandwagon,
    "argument_ignorance": gen_argument_ignorance,
    "false_dichotomy": gen_false_dichotomy,
    "appeal_intuition": gen_appeal_intuition,
    "vague_authority": gen_vague_authority,
    "appeal_nature": gen_appeal_nature,
    "appeal_tradition": gen_appeal_tradition,
    "slippery_slope": gen_slippery_slope,
    "weasel_wording": gen_weasel_wording,
    "common_sense": gen_common_sense,
    "ad_hominem": gen_ad_hominem,
}

# ── Fallacy Generation Logic ──────────────────────────────────────────────────

FALLACY_FUNCTIONS = {
    "undistributed_middle": gen_undistributed_middle,
    "illicit_major": gen_illicit_major,
    "illicit_minor": gen_illicit_minor,
    "exclusive_premises": gen_exclusive_premises,
    "existential_fallacy": gen_existential_fallacy,
    "denying_antecedent": gen_denying_antecedent_hard,
    "composition": gen_composition_hard,
    "division": gen_division_hard,
    "equivocation": gen_equivocation_hard,
}


def generate_for_fallacy(fallacy_type: str, samples_per_template: int = 50) -> list[dict]:
    gen_fn = FALLACY_FUNCTIONS[fallacy_type]
    seen_texts: set[str] = set()
    results: list[str] = []

    for _ in range(samples_per_template * 12):
        text = gen_fn()
        style = random.choice(STYLES)
        pick = random.random()
        if pick < 0.50:
            final = style + text
        elif pick < 0.75:
            final = text
        else:
            salt = random.choice(
                ["Actually, ", "In my opinion, ", "Note that ", "Basically, ", "Well, ", "I think ", ""]
            )
            final = salt + text

        if final not in seen_texts:
            seen_texts.add(final)
            results.append(final)

        if len(results) >= samples_per_template:
            break

    return [{"text": t, "fallacy": fallacy_type, "source": "formal_hard_negative_gen"} for t in results]


def generate_for_near_miss(miss_type: str, samples_per_template: int = 84) -> list[dict]:
    gen_fn = NEAR_MISS_FUNCTIONS[miss_type]
    seen_texts: set[str] = set()
    results: list[str] = []

    for _ in range(samples_per_template * 12):
        text = gen_fn()
        style = random.choice(STYLES)
        pick = random.random()
        if pick < 0.50:
            final = style + text
        elif pick < 0.75:
            final = text
        else:
            salt = random.choice(
                ["Actually, ", "In my opinion, ", "Note that ", "Basically, ", "Well, ", "I think ", ""]
            )
            final = salt + text

        if final not in seen_texts:
            seen_texts.add(final)
            results.append(final)

        if len(results) >= samples_per_template:
            break

    return [{"text": t, "near_miss_type": miss_type, "label": 0, "source": "near_miss_hard_negative"} for t in results]


def generate_near_miss_negatives(total_target: int = 1000) -> list[dict]:
    all_data: list[dict] = []
    types = list(NEAR_MISS_FUNCTIONS.keys())
    per_type = total_target // len(types)

    for miss_type in types:
        print(f"Generating near-miss: {miss_type}...")
        samples = generate_for_near_miss(miss_type, samples_per_template=per_type)
        all_data.extend(samples)
        print(f"  -> {len(samples)} samples")

    unique_texts: set[str] = set()
    final_data: list[dict] = []
    for d in all_data:
        if d["text"] not in unique_texts:
            final_data.append(d)
            unique_texts.add(d["text"])

    return final_data


# ── Merge Logic ───────────────────────────────────────────────────────────────


def merge_datasets(unified_path: str, negatives_path: str, output_path: str):
    with open(unified_path) as f:
        unified = json.load(f)
    with open(negatives_path) as f:
        negatives = json.load(f)

    existing_texts = {item["text"] for item in unified}
    added = 0
    for item in negatives:
        if item["text"] not in existing_texts:
            unified.append(item)
            existing_texts.add(item["text"])
            added += 1

    with open(output_path, "w") as f:
        json.dump(unified, f, indent=2)

    print("\nMerged datasets:")
    print(f"  Original (unified):          {len(unified) - added}")
    print(f"  Added from negatives:        {added}")
    print(f"  Total (unified_v1.3):        {len(unified)}")


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--near-miss", action="store_true", help="Generate near-miss hard negatives (label=0)")
    parser.add_argument("--merge", action="store_true", help="Merge with unified_training_data_v1.2.json")
    args = parser.parse_args()

    if args.near_miss:
        random.seed(42)
        print("Generating near-miss hard negatives...")
        data = generate_near_miss_negatives(total_target=1000)
        output_path = "data/formal_hard_negatives_v1.2.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\nTotal near-miss negatives generated: {len(data)}")
        counts = Counter(d["near_miss_type"] for d in data)
        for k, v in counts.most_common():
            print(f"  {k:25}: {v}")
        return

    if args.merge:
        merge_datasets(
            unified_path="data/unified_training_data_v1.2.json",
            negatives_path="data/formal_hard_negatives_v1.2.json",
            output_path="data/unified_training_data_v1.3.json",
        )
        return

    # Default: generate formal fallacies
    random.seed(42)
    all_data: list[dict] = []

    for fallacy in FALLACY_FUNCTIONS:
        print(f"Generating {fallacy}...")
        samples = generate_for_fallacy(fallacy, samples_per_template=500)
        all_data.extend(samples)
        print(f"  -> {len(samples)} samples")

    unique_texts: set[str] = set()
    final_data: list[dict] = []
    for d in all_data:
        if d["text"] not in unique_texts:
            final_data.append(d)
            unique_texts.add(d["text"])

    output_path = "data/formal_hard_negatives_v1.2.json"
    with open(output_path, "w") as f:
        json.dump(final_data, f, indent=2)

    print(f"\nTotal generated: {len(final_data)}")
    counts = Counter(d["fallacy"] for d in final_data)
    for k, v in counts.most_common():
        print(f"  {k:25}: {v}")


if __name__ == "__main__":
    main()
