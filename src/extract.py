"""
SAP -> ADaM Spec Extractor (v0.1)
Day 1: Minimal working pipeline.
"""
import argparse
import json
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv


load_dotenv()

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a senior ADaM statistical programmer with 10+ \
years of experience implementing CDISC ADaM IG v1.3.

Your task: given a SAP excerpt, extract structured ADaM variable specifications.

Critical rules:
1. Only reference SDTM source variables that are explicitly mentioned in the \
SAP text. Do NOT invent source variables.
2. If the SAP description is ambiguous or incomplete, populate the \
"ambiguities" field -- DO NOT guess. Flagging uncertainty is more valuable \
than fabricating completeness.
3. Follow ADaM IG naming conventions (TRTSDT, TRTEDT, AVAL, BASE, CHG, \
ANL01FL, SAFFL, ITTFL, etc.).
4. Derivation logic must be expressed as both pseudocode AND a one-sentence \
natural-language description.
5. Extract only variables whose derivation or direct copy rule is defined in \
the excerpt. If a variable is mentioned only as an input, condition, or \
already-existing reference, include it in sdtm_sources or derivation text as \
appropriate, but do NOT create a separate variable specification for it.

Output strictly valid JSON matching the requested schema. No prose outside JSON."""

USER_PROMPT_TEMPLATE = """SAP EXCERPT:
\"\"\"
{sap_text}
\"\"\"

Extract every ADaM variable defined or derived in this excerpt.

Return JSON with this exact structure:
{{
  "variables": [
    {{
      "variable_name": "string (ADaM convention, e.g. TRTSDT)",
      "variable_label": "string (human-readable label)",
      "type": "Num | Char",
      "adam_dataset": "string (e.g. ADSL, ADAE)",
      "sdtm_sources": ["list of SDTM variables referenced, e.g. EX.EXSTDTC"],
      "derivation_pseudocode": "string (concise pseudocode)",
      "derivation_natural_language": "string (one sentence)",
      "ambiguities": ["list of specific things the SAP did NOT clarify"],
      "sap_excerpt_quote": "string (the exact sentence(s) from SAP this is based on)",
      "confidence": {{
        "sap_clarity": 0,
        "sdtm_source_identifiable": 0,
        "naming_compliance": 0,
        "ig_alignment": 0,
        "total": 0
      }}
    }}
  ]
}}

Each confidence sub-score is 0-25. Total is the sum (0-100).
Confidence rubric:
- sap_clarity: how unambiguously the SAP defines this variable
- sdtm_source_identifiable: whether SDTM source is named or clearly inferable
- naming_compliance: whether variable name follows ADaM IG conventions
- ig_alignment: whether derivation matches standard ADaM patterns

Return ONLY the JSON, no markdown fences, no commentary."""


def extract_spec(sap_text: str, use_mock: bool = False) -> dict:
    """Call Claude to extract ADaM specs from SAP text."""
    if use_mock:
        return _mock_extract_spec()

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env before running the extractor."
        )

    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(sap_text=sap_text),
            }
        ],
    )
    raw_text = response.content[0].text.strip()

    # JSON recovery: direct parse, markdown-fence cleanup, then object slicing.
    return _robust_json_parse(raw_text)


def _robust_json_parse(text: str) -> dict:
    """Try multiple strategies to recover JSON from LLM output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM output:\n{text[:500]}")


def _mock_extract_spec() -> dict:
    """Return a deterministic Day 1 sample for no-key local demos."""
    return {
        "variables": [
            {
                "variable_name": "TRTSDT",
                "variable_label": "Date of First Exposure to Treatment",
                "type": "Num",
                "adam_dataset": "ADSL",
                "sdtm_sources": ["EX.EXSTDTC", "EX.EXDOSE"],
                "derivation_pseudocode": (
                    "For each subject, set TRTSDT to min(input(EXSTDTC)) "
                    "where EXDOSE > 0; set missing if no positive-dose EX record exists."
                ),
                "derivation_natural_language": (
                    "TRTSDT is the first study drug administration date from EX "
                    "among records with a positive dose."
                ),
                "ambiguities": [],
                "sap_excerpt_quote": (
                    "TRTSDT is defined as the minimum EXSTDTC value across all "
                    "exposure records for a given subject where EXDOSE > 0."
                ),
                "confidence": {
                    "sap_clarity": 24,
                    "sdtm_source_identifiable": 24,
                    "naming_compliance": 25,
                    "ig_alignment": 20,
                    "total": 93,
                },
            },
            {
                "variable_name": "TRTEDT",
                "variable_label": "Date of Last Exposure to Treatment",
                "type": "Num",
                "adam_dataset": "ADSL",
                "sdtm_sources": ["EX.EXENDTC", "EX.EXDOSE"],
                "derivation_pseudocode": (
                    "For each subject, set TRTEDT to max(input(EXENDTC)) + 1 "
                    "where EXDOSE > 0."
                ),
                "derivation_natural_language": (
                    "TRTEDT is the last actual study drug exposure end date plus "
                    "one day among positive-dose EX records."
                ),
                "ambiguities": [
                    (
                        "The SAP states plus one day to reflect the end of the "
                        "dosing interval, but does not clarify whether this applies "
                        "to all dosing schedules."
                    )
                ],
                "sap_excerpt_quote": (
                    "TRTEDT will be derived as the date of last study drug "
                    "administration plus one day... based on the maximum EXENDTC "
                    "value across all exposure records where EXDOSE > 0."
                ),
                "confidence": {
                    "sap_clarity": 21,
                    "sdtm_source_identifiable": 24,
                    "naming_compliance": 25,
                    "ig_alignment": 18,
                    "total": 88,
                },
            },
        ]
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract ADaM specs from a SAP excerpt.")
    parser.add_argument(
        "sap_file",
        nargs="?",
        default="data/sap_excerpts/treatment_dates.txt",
        help="Path to a SAP excerpt text file.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic sample output without calling the Anthropic API.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    sap_file = Path(args.sap_file)
    sap_text = sap_file.read_text()

    print(f"📄 Processing: {sap_file.name}")
    print(f"   Length: {len(sap_text)} chars\n")
    if args.mock:
        print("Mode: mock output (no Anthropic API call)\n")

    result = extract_spec(sap_text, use_mock=args.mock)

    out_path = Path("outputs") / f"{sap_file.stem}_spec.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"✅ Extracted {len(result.get('variables', []))} variable(s)")
    print(f"   Saved to: {out_path}\n")

    for var in result.get("variables", []):
        conf = var.get("confidence", {}).get("total", 0)
        status = "🟢" if conf >= 75 else "🟡" if conf >= 50 else "🔴"
        print(
            f"{status} {var['variable_name']:10} | conf={conf:3} | "
            f"{var['variable_label']}"
        )
        if var.get("sdtm_sources"):
            print(f"   📥 sources: {', '.join(var['sdtm_sources'])}")
        if var.get("ambiguities"):
            for ambiguity in var["ambiguities"]:
                print(f"   ⚠️  {ambiguity}")


if __name__ == "__main__":
    main()
