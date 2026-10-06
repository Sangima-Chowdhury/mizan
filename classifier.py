import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

CLASSIFIER_SYSTEM_PROMPT = """You are a classification assistant for a campaign intake system for an Islamic crowdfunding platform. Read the campaign's title and description and classify it into exactly one of these categories:

- zakat: Obligatory almsgiving under Islamic law. Must primarily benefit an eligible recipient category (e.g. the poor, the needy, those in debt). Campaigns explicitly labeled Zakat, or clearly restricted to Zakat-eligible recipients, belong here.
- sadaqah: Voluntary charitable giving that isn't Zakat-restricted and isn't a permanent endowment. Covers general humanitarian aid, disaster relief, medical bills, community support and Sadaqah Jariyah (giving with long lasting impact, such as digging a well or installing water pump for shared community use and planting olive trees for farmers who lost their land or trees, e.g. in Palestine) - these remain Sadaqah, not Waqf, because there is no preserved principal being managed, only a lasting effect from a single act of giving.
- waqf: A formally structured, named perpetual endowment fund, where donors contribute to a preserved principal that is professionally managed and only its proceeds are spent (e.g. a named "Waqf Fund" or cash waqf account, an income-generating property endowed to fund a mosque indefinitely). Reserve this category for campaigns explicitly describing this kind of managed endowment structure, not standalone community projects.
- lillah: General giving "for the sake of Allah" - commonly mosque construction, operating costs of Islamic institutions, or causes that don't clearly fit under three.
- uncategorized: Use this whenever the campaign is ambiguous, lacks enough detail, or genuinely doesn't fit any category above. Do not guess.

Respond with ONLY valid JSON, no text before or after it, in this exact shape:
{"category": "<one of the five values above>", "confidence": <integer 0-100>, "reasoning": "<one short sentence explaining the choice>"}"""


def classify_campaign(title, description):
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=CLASSIFIER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Title: {title}\n\nDescription: {description}"}
        ]
    )

    raw_text = message.content[0].text

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {
            "category": "uncategorized",
            "confidence": 0,
            "reasoning": "Classifier response could not be parsed as JSON."
        }

    return {
        "category": parsed.get("category", "uncategorized"),
        "confidence": parsed.get("confidence", 0),
        "raw_response": raw_text
    }
