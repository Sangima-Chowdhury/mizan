import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

RISK_SYSTEM_PROMPT = """You are a fraud and policy risk assessment assistant in a campaign intake system for an Islamic crowdfunding platform. Read a campaign's title and description and assess two separate, independent types of risk.

FRAUD RISK (0-100): How likely is this campaign to be fabricated, exaggerated, or a scam, based on the text alone? Consider:
- Vague or generic beneficiary details (no name, no specific, checkable circumstances)
- Urgency or pressure language stacked with a lack of concrete detail ("act now," "share immediately," with nothing to verify)
- Unverifiable claims — no location, no named institution (hospital, school, mosque), nothing a moderator could actually check
- A requested amount that doesn't match the stated need, or no clear breakdown of how funds will be used
- Generic, templated-sounding language that could apply to any campaign, rather than specific circumstances

POLICY RISK (0-100): How likely is this campaign to violate reasonable platform policy for a charitable crowdfunding site, independent of fraud? Consider:
- Requests that aren't for a charitable purpose (e.g. personal profit, commercial business funding)
- Political campaigning or content unrelated to charitable giving
- Mentions of illegal activity or funds intended for anything other than the stated charitable purpose
- Requests to individuals with no transparency about fund distribution or accountability

Score each dimension independently — a campaign can be high fraud risk and low policy risk, or the reverse. A vague but clearly charitable campaign is fraud-risk-elevated but policy-fine. A well-documented but non-charitable request is policy-risk-elevated but not necessarily fraudulent.

List specific risk_flags as short snake_case strings describing exactly what you noticed (e.g. "vague_beneficiary_details", "unverifiable_location", "non_charitable_purpose"). Include only flags that genuinely apply — an empty list is a valid, good answer for a clean campaign.

Respond with ONLY valid JSON, no text before or after it, in this exact shape:
{"fraud_risk_score": <integer 0-100>, "policy_risk_score": <integer 0-100>, "risk_flags": ["<flag>", ...], "reasoning": "<one short sentence summarizing the assessment>"}
"""


def score_risk(title, description, category):
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        system=RISK_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"category: {category}\n\nTitle: {title}\n\nDescription: {description}"
            }
        ]
    )

    raw_text = message.content[0].text

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {
            "fraud_risk_score": 100,
            "policy_risk_score": 100,
            "risk_flags": ["risk_assesment_failed"],
            "reasoning": "Risk assessment could not be parsed. Flagged at maximum risk to force human review as precaution."
        }

    return {
        "fraud_risk_score": parsed.get("fraud_risk_score", 100),
        "policy_risk_score": parsed.get("policy_risk_score", 100),
        "risk_flags": parsed.get("risk_flags", []),
        "raw_response": raw_text
    }
