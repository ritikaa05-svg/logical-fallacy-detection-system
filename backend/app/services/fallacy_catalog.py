# Centralized catalog for fallacy definitions.
# 'short' is used for hover cards/tooltips.
# 'extended' is used for sidebar cards and detailed explanations.
FALLACY_DEFINITIONS: dict[str, dict[str, str]] = {
    "ad_hominem": {
        "short": "Attacks the person, not their argument.",
        "extended": "Rather than addressing the argument's logic or evidence, the speaker attacks the character, motive, or personal attributes of the person making it.",
    },
    "affirming_consequent": {
        "short": "Assumes a result proves its cause.",
        "extended": "If A implies B, and B is true, this fallacy incorrectly concludes A must be true. Many causes can produce the same effect.",
    },
    "appeal_to_authority": {
        "short": "Claiming truth based solely on an authority figure.",
        "extended": "Arguing that a claim is true because an authority figure or institution says so, without providing logical support.",
    },
    "appeal_to_emotion": {
        "short": "Manipulating emotions instead of using logic.",
        "extended": "Attempting to win an argument by eliciting an emotional response (fear, pity, joy) instead of presenting valid evidence.",
    },
    "appeal_to_nature": {
        "short": "Arguing that natural is always good and unnatural is bad.",
        "extended": "Assuming that something is inherently good because it is 'natural' or inherently bad because it is 'unnatural'.",
    },
    "appeal_to_ignorance": {
        "short": "Assuming a claim is true because it hasn't been disproven.",
        "extended": "Arguing that a proposition must be true (or false) simply because no one has proven otherwise, shifting the burden of proof instead of providing evidence.",
    },
    "appeal_to_tradition": {
        "short": "Arguing that something is right because it has always been done that way.",
        "extended": "Assuming that a policy or belief is correct simply because it has a long history or tradition.",
    },
    "bandwagon": {
        "short": "Arguing that something is true because many people believe it.",
        "extended": "Claiming that a proposition is true because of its popularity or because many people accept it.",
    },
    "begging_the_question": {
        "short": "Assuming the conclusion in the premise.",
        "extended": "An argument where the conclusion is already assumed in one of the premises, creating circular reasoning.",
    },
    "composition": {
        "short": "Assuming what is true of parts is true of the whole.",
        "extended": "Assuming that what is true for individual members of a group or parts of a system must also be true for the group or system as a whole.",
    },
    "denying_antecedent": {
        "short": "Incorrectly assuming that if the cause is false, the result must also be false.",
        "extended": "A formal fallacy: If A then B. Not A. Therefore, not B. This ignores that B could be caused by something else.",
    },
    "division": {
        "short": "Assuming what is true of the whole is true of parts.",
        "extended": "Assuming that what is true for a whole must also be true for each of its individual parts.",
    },
    "equivocation": {
        "short": "Using a word with multiple meanings to mislead.",
        "extended": "Using a particular word or phrase in multiple senses within an argument to mislead the audience into a false conclusion.",
    },
    "false_cause": {
        "short": "Assuming a relationship between two things that doesn't exist.",
        "extended": "Assuming that because one event followed another, the first must have caused the second (Post Hoc Ergo Propter Hoc).",
    },
    "false_dilemma": {
        "short": "Presenting only two options when more exist.",
        "extended": "Presenting a choice between two mutually exclusive options as if they were the only possibilities, when others exist.",
    },
    "hasty_generalization": {
        "short": "Drawing a broad conclusion from a small sample size.",
        "extended": "Making a sweeping claim based on insufficient evidence or a non-representative sample.",
    },
    "moving_goalposts": {
        "short": "Changing the requirements of an argument after they have been met.",
        "extended": "Demanding new evidence or changing the criteria for proof after the initial conditions have been satisfied.",
    },
    "no_true_scotsman": {
        "short": "Excluding a counterexample by redefining a term.",
        "extended": "Protecting a universal generalization from counterexamples by changing the definition in an ad hoc way to exclude them.",
    },
    "red_herring": {
        "short": "Introducing irrelevant information to distract.",
        "extended": "Attempting to divert the attention from the original argument by introducing an irrelevant topic.",
    },
    "slippery_slope": {
        "short": "Arguing a small step lead to a chain of negative events.",
        "extended": "Claiming that a relatively small first step will inevitably lead to a chain of related (and usually negative) events.",
    },
    "straw_man": {
        "short": "Misrepresenting an argument to make it easier to attack.",
        "extended": "Distorting or oversimplifying an opponent's position to make it easier to refute or mock.",
    },
    "tu_quoque": {
        "short": "Deflecting criticism by pointing out the critic's hypocrisy.",
        "extended": "Dismissing someone's argument by pointing out that they have acted inconsistently with their own conclusion.",
    },
    "tu_quoque_contextual": {
        "short": "Pointing out hypocrisy within the current conversation.",
        "extended": "Pointing out that the interlocutor has committed the same error or used the same tactic earlier in the current discussion.",
    },
}


def get_definition(fallacy: str, mode: str = "short") -> str:
    """Returns the requested definition mode for a given fallacy key."""
    key = fallacy.lower().replace(" ", "_")
    entry = FALLACY_DEFINITIONS.get(key, {})
    return entry.get(mode, entry.get("short", "Logical reasoning error detected."))
