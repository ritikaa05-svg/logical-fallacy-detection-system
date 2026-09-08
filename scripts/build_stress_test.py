import json
from pathlib import Path

# Stress Test Dataset Definitions
ADVERSARIAL_CATEGORIES = {
    "expert_quoting": {
        "mimics": "appeal_to_authority",
        "reason": "Authority is relevant and references empirical evidence.",
        "templates": [
            "According to {expert}, {claim} because of {evidence}.",
            "The {institution} reported that {claim}, citing {evidence}.",
            "Evidence from {study} suggests that {claim}, as confirmed by {expert}.",
        ],
        "data": [
            ("Dr. Anthony Fauci", "vaccines are safe and effective", "Phase 3 clinical trial data"),
            (
                "The Intergovernmental Panel on Climate Change (IPCC)",
                "global temperatures are rising",
                "satellite measurements and ice core samples",
            ),
            (
                "Dr. Jennifer Doudna",
                "CRISPR technology can edit specific gene sequences",
                "peer-reviewed biochemical assays",
            ),
            (
                "The American Heart Association",
                "reducing sodium intake lowers blood pressure",
                "decades of longitudinal dietary studies",
            ),
            ("NASA", "the Martian atmosphere is 95% carbon dioxide", "mass spectrometer data from the Curiosity rover"),
            (
                "Dr. Stephen Hawking",
                "black holes emit thermal radiation",
                "mathematical derivations combining general relativity and quantum mechanics",
            ),
            (
                "The World Health Organization",
                "handwashing reduces the spread of infectious diseases",
                "randomized controlled trials in hospital settings",
            ),
            (
                "Dr. Andrew Ng",
                "deep learning requires large datasets for high accuracy",
                "benchmarking across ImageNet and other standard datasets",
            ),
            (
                "The Federal Reserve",
                "inflation impacts consumer purchasing power",
                "Consumer Price Index (CPI) tracking",
            ),
            ("Dr. Jane Goodall", "chimpanzees use tools in the wild", "decades of direct ethological observation"),
            (
                "The Mayo Clinic",
                "regular exercise reduces the risk of type 2 diabetes",
                "clinical observation of insulin sensitivity improvement",
            ),
            (
                "Dr. Robert Oppenheimer",
                "nuclear fission releases massive amounts of energy",
                "experimental verification of the E=mc² relationship",
            ),
            (
                "The Royal Society",
                "biodiversity is critical for ecosystem stability",
                "long-term ecological monitoring projects",
            ),
            (
                "Dr. Esther Duflo",
                "micro-loans have complex impacts on poverty",
                "large-scale randomized controlled trials in developing economies",
            ),
            (
                "The National Institutes of Health",
                "sleep deprivation impairs cognitive function",
                "fMRI studies of brain activity during exhaustion",
            ),
            (
                "Dr. Richard Feynman",
                "quantum particles exhibit wave-particle duality",
                "the results of the double-slit experiment",
            ),
            (
                "The Smithsonian Institution",
                "dinosaurs were the dominant terrestrial vertebrates for 135 million years",
                "the fossil record across multiple geological strata",
            ),
            (
                "Dr. Alice Ball",
                "chaulmoogra oil was an effective treatment for leprosy",
                "chemical isolation of the active fatty acids",
            ),
            (
                "The Max Planck Institute",
                "the universe's expansion is accelerating",
                "observations of Type Ia supernovae",
            ),
            ("Dr. Marie Curie", "radium is naturally radioactive", "the isolation of isotopes from pitchblende ore"),
        ],
    },
    "genuine_dilemma": {
        "mimics": "false_dilemma",
        "reason": "The choice presented is a true logical or practical binary.",
        "templates": [
            "In this {context}, you must choose either {opt1} or {opt2}.",
            "Either {opt1} or {opt2} must be true, as they are {relation}.",
            "We are faced with a choice: {opt1} or {opt2}. There is no third option in this {context}.",
        ],
        "data": [
            ("binary election", "candidate A", "candidate B", "mutually exclusive"),
            ("logic test", "true", "false", "contradictories"),
            ("coin flip", "heads", "tails", "exhaustive"),
            ("digital circuit", "on", "off", "opposites"),
            ("legal verdict", "guilty", "not guilty", "defined by law"),
            ("biological sex in most mammals", "male", "female", "primary categories"),
            ("matter state in this experiment", "solid", "liquid", "constrained"),
            ("chess move", "move the piece", "leave it where it is", "exhaustive"),
            ("parking rule", "authorized", "unauthorized", "binary"),
            ("battery state", "charged", "depleted", "functional binary"),
            ("integer parity", "even", "odd", "exhaustive"),
            ("pregnancy test", "positive", "negative", "biological binary"),
            ("mortality", "alive", "dead", "binary state"),
            ("membership", "member", "non-member", "definitional"),
            ("software license", "active", "expired", "system binary"),
            ("door position", "open", "closed", "physical binary"),
            ("truth value", "correct", "incorrect", "logical binary"),
            ("attendance", "present", "absent", "binary"),
            ("electricity", "conductive", "insulative", "physical property"),
            ("direction", "clockwise", "counter-clockwise", "rotational binary"),
        ],
    },
    "statistical_correlation": {
        "mimics": "false_cause",
        "reason": "Causation is supported by controlled studies, not just sequence.",
        "templates": [
            "{action} led to {result}, and {evidence} confirms the causal link.",
            "Studies show that {action} causes {result} by {mechanism}.",
            "We observed {result} after {action}; {expert} verified the causation.",
        ],
        "data": [
            ("The tax increase", "reduced smoking rates", "econometric modeling"),
            ("Regular exercise", "lower resting heart rates", "cardiovascular physiology"),
            ("Antibiotic treatment", "the clearing of the infection", "bacterial culture monitoring"),
            ("Increased CO2", "ocean acidification", "chemical analysis of pH levels"),
            ("Chlorofluorocarbons", "ozone depletion", "atmospheric chemistry modeling"),
            ("Vaccination", "the eradication of smallpox", "global epidemiological records"),
            ("Seat belt use", "fewer traffic fatalities", "crash test data and insurance statistics"),
            ("Deforestation", "local soil erosion", "topographic runoff studies"),
            ("High sugar intake", "increased insulin resistance", "metabolic blood panels"),
            ("Lead exposure", "cognitive developmental delays", "longitudinal pediatric studies"),
            ("Sleep apnea", "increased stroke risk", "sleep lab monitoring and follow-up"),
            ("Tectonic plate movement", "seismic activity", "seismograph readings"),
            ("Standardized testing", "curriculum alignment", "educational outcome data"),
            ("Irrigation", "increased crop yields", "controlled agricultural trials"),
            ("Urbanization", "the urban heat island effect", "thermal satellite imaging"),
            ("Aspirin use", "reduced prostaglandin production", "biochemical pathway mapping"),
            ("Social distancing", "lowered viral transmission rates", "network contact tracing data"),
            ("Acid rain", "damage to freshwater ecosystems", "limnological surveys"),
            ("Vitamin C deficiency", "scurvy", "controlled nutritional experiments"),
            ("Invasive species introduction", "native population decline", "field ecological surveys"),
        ],
    },
    "legitimate_slippery_slope": {
        "mimics": "slippery_slope",
        "reason": "The predicted consequence is based on historical precedent or logical necessity.",
        "templates": [
            "If we {action}, then {result} will likely follow based on {precedent}.",
            "{action} often leads to {result}, as seen in {example}.",
            "We must consider that {action} creates a path to {result} because {reason}.",
        ],
        "data": [
            ("remove all border controls", "undocumented immigration will increase", "historical migration patterns"),
            (
                "increase the money supply excessively",
                "hyperinflation will occur",
                "the Weimar Republic and Zimbabwe cases",
            ),
            (
                "ignore small leaks in the dam",
                "a catastrophic failure will occur",
                "fluid dynamics and structural fatigue",
            ),
            ("stop maintaining the road network", "transportation costs will rise", "increased vehicle wear and tear"),
            ("allow antibiotic overuse", "multi-drug resistant bacteria will emerge", "evolutionary biology"),
            ("fail to rotate crops", "soil fertility will collapse", "agricultural history"),
            ("permit monopolies to form", "consumer prices will eventually rise", "standard economic theory"),
            ("reduce cybersecurity spending", "data breaches will increase", "industry-wide security trends"),
            ("overfish the breeding grounds", "the fishery will collapse", "population dynamics"),
            (
                "neglect early childhood education",
                "long-term crime rates may rise",
                "sociological longitudinal studies",
            ),
            (
                "abandon the gold standard without a plan",
                "currency volatility will increase",
                "historical economic transitions",
            ),
            ("increase carbon emissions unchecked", "sea levels will rise", "glaciology and thermal expansion"),
            ("leave standing water in tropical areas", "mosquito-borne diseases will spread", "public health records"),
            ("ignore software patches", "system vulnerabilities will be exploited", "known exploit cycles"),
            ("allow the permafrost to melt", "massive methane release will accelerate warming", "climatology"),
            ("remove all traffic lights", "accident rates will increase", "urban planning simulations"),
            ("fail to exercise regularly", "muscle atrophy will occur", "human physiology"),
            ("stop funding basic research", "innovation in the tech sector will slow", "historical patent data"),
            (
                "allow invasive vines to grow unchecked",
                "the local forest canopy will be destroyed",
                "botanical observations",
            ),
            ("disregard fire safety codes", "the risk of building-wide fires will increase", "actuarial data"),
        ],
    },
    "valid_generalization": {
        "mimics": "hasty_generalization",
        "reason": "The sample size is exhaustive or statistically representative.",
        "templates": [
            "Every {subject} in this {set} {property}, therefore all {subject}s in the {set} {property}.",
            "Based on a {size} survey of {total}, we can conclude {conclusion}.",
            "Observation of {count} cases shows {property}, which is consistent across the {total} population.",
        ],
        "data": [
            ("planet", "solar system", "orbits the Sun", "exhaustive"),
            ("10,000", "12,000", "voters support the measure", "statistically representative"),
            ("every", "periodic table", "element has an atomic number", "exhaustive"),
            ("all 50", "United States", "states have a capital city", "exhaustive"),
            ("each", "human heart", "has four chambers", "biological universal"),
            ("every", "triangle", "has three sides", "definitional"),
            ("all", "mammals", "produce milk for their young", "biological definition"),
            ("each", "molecule of water", "contains two hydrogen atoms", "chemical identity"),
            ("every", "chess board", "has 64 squares", "standardized definition"),
            ("all", "noble gases", "are relatively unreactive", "periodic property"),
            ("each", "prime number greater than 2", "is odd", "mathematical proof"),
            ("every", "standard deck", "contains four aces", "exhaustive count"),
            ("all", "insects", "have six legs", "biological classification"),
            ("each", "continent", "is surrounded at least partially by water", "geographical fact"),
            ("every", "leap year", "has 366 days", "calendrical rule"),
            ("all", "visible light colors", "have different wavelengths", "physical property"),
            ("each", "cell in the body", "contains DNA", "biological universal"),
            ("every", "oxygen atom", "has 8 protons", "atomic definition"),
            ("all", "planets in the solar system", "have elliptical orbits", "Kepler's laws"),
            ("each", "day in a week", "has 24 hours", "temporal definition"),
        ],
    },
}


def build_dataset():
    dataset = []

    for cat_name, info in ADVERSARIAL_CATEGORIES.items():
        templates = info["templates"]
        data_rows = info["data"]
        mimics = info["mimics"]
        reason = info["reason"]

        for i, row in enumerate(data_rows):
            template = templates[i % len(templates)]

            # Fill template
            if len(row) == 3:
                text = template.format(expert=row[0], institution=row[0], study=row[0], claim=row[1], evidence=row[2])
            elif len(row) == 4:
                text = template.format(
                    context=row[0],
                    opt1=row[1],
                    opt2=row[2],
                    relation=row[3],
                    action=row[0],
                    result=row[1],
                    precedent=row[2],
                    example=row[2],
                    reason=row[3],
                    subject=row[0],
                    set=row[1],
                    property=row[2],
                    size=row[0],
                    total=row[1],
                    conclusion=row[2],
                    count=row[0],
                )

            dataset.append(
                {
                    "text": text,
                    "label": "valid_argument",
                    "mimicked_fallacy": mimics,
                    "validity_reason": reason,
                    "category": cat_name,
                }
            )

    output_path = Path("data/adversarial_stress_test.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"✅ Created adversarial stress test with {len(dataset)} examples.")
    print(f"📍 Location: {output_path}")


if __name__ == "__main__":
    build_dataset()
