# SAP → ADaM Spec Drafter

An AI-assisted tool that converts Statistical Analysis Plan (SAP) narrative into
structured ADaM specification drafts, with explicit uncertainty flagging and
full SAP-to-spec traceability.

**Built for biostatisticians and statistical programmers working in
CDISC-compliant clinical trial pipelines.**

---

## Why

ADaM specification authoring is one of the most time-consuming, mechanical
tasks in clinical trial statistical programming — typically 2–4 weeks of senior
programmer time per study. This tool aims to compress that to hours, while
preserving full traceability and human review.

The design philosophy is **human-in-the-loop, not AI-replaces-human**:

- Every spec entry traces back to the exact SAP sentence it came from
- The model is explicitly instructed to flag uncertainty rather than fabricate
- A 4-dimensional confidence rubric (SAP clarity, SDTM source identifiability,
  naming compliance, IG alignment) tells reviewers where to focus

---

## Status

🚧 **Day 1 of 7-day MVP sprint complete.** A working extraction pipeline that
takes SAP narrative and produces structured ADaM variable specifications with
confidence scoring, ambiguity surfacing, and SAP excerpt traceability.

---

## Day 1 Results

Built a working SAP → ADaM spec extraction pipeline using Claude Sonnet 4.5.
Processed 3 SAP excerpts covering **9 ADSL variables** (treatment dates,
analysis population flags, demographics). **Zero hallucinated SDTM source
variables** — every source reference traces back to the SAP text. The model
surfaces non-obvious ambiguities (e.g. cross-variable dependency between
`BASEWT` and `TRTSDT`, undefined "efficacy-impacting deviation" criteria for
`PPROTFL`) that experienced ADaM programmers typically catch only during
downstream review.

### Design note: scoping rule

One subtle but important prompt rule emerged from output review: the extractor
must distinguish between variables that are *defined* in an excerpt vs. those
merely *referenced* as inputs or conditions. Without this rule, the LLM
duplicates definitions of cross-section variables (e.g. `TRTSDT` referenced
inside the `BASEWT` derivation), polluting the downstream spec library and
breaking the variable dependency graph. This rule encodes a piece of "default
knowledge" that experienced ADaM programmers carry implicitly.

### Variables extracted

| Excerpt | Variable | Confidence | Notable ambiguity surfaced |
|---|---|---|---|
| `treatment_dates.txt` | `TRTSDT` | 97 | Partial-date handling for EXSTDTC |
| `treatment_dates.txt` | `TRTEDT` | 95 | Whether `+1 day` applies before or after handling missing dates |
| `analysis_populations.txt` | `SAFFL` | 92 | How "randomized status" is determined (not specified in excerpt) |
| `analysis_populations.txt` | `ITTFL` | 97 | Whether RSDTC validity matters or only non-missing |
| `analysis_populations.txt` | `PPROTFL` | 89 | Specific DVDECOD values for "efficacy-impacting deviation" not listed |
| `demographics.txt` | `AGE` | 95 | "Year-month-day convention" references external SAP shell |
| `demographics.txt` | `SEX` | 100 | (None — direct copy from DM.SEX) |
| `demographics.txt` | `RACE` | 89 | "Supplemental demographics domain" not explicitly identified (SUPPDM?) |
| `demographics.txt` | `BASEWT` | 90 | **Cross-variable dependency:** references `TRTSDT` which must be derived first |

### What "0 hallucinations" means here

Every `sdtm_sources` entry across all 9 variables (`EX.EXSTDTC`, `EX.EXDOSE`,
`EX.EXENDTC`, `RS.RSDTC`, `DV.DVCAT`, `DV.DVDECOD`, `DM.AGE`, `DM.BRTHDTC`,
`DM.RFICDTC`, `DM.SEX`, `DM.RACE`, `VS.VSSTRESN`, `VS.VSTESTCD`, `VS.VSDTC`)
is explicitly named in the source SAP text. The model also correctly **omitted**
variables that were not in the input (e.g. `AGEGR1` was not in the demographics
excerpt and was not invented).

---

## Quick start

```bash
# 1. Clone and set up
git clone <this-repo>
cd sap-to-adam
bash setup.sh

# 2. Configure API key
# edit .env and paste your Anthropic API key

# 3. Run on a sample SAP excerpt
source venv/bin/activate
python src/extract.py

# Or process a specific file
python src/extract.py data/sap_excerpts/analysis_populations.txt
```

Expected terminal output:

```text
📄 Processing: treatment_dates.txt
   Length: 835 chars

✅ Extracted 2 variable(s)
   Saved to: outputs/treatment_dates_spec.json

🟢 TRTSDT     | conf= 97 | Date of First Exposure to Treatment
   📥 sources: EX.EXSTDTC, EX.EXDOSE
🟢 TRTEDT     | conf= 95 | Date of Last Exposure to Treatment
   📥 sources: EX.EXENDTC, EX.EXDOSE
   ⚠️  SAP does not specify whether the '+1 day' adjustment should
       occur before or after handling missing values
```

---

## Approach

Multi-stage LLM pipeline using Claude Sonnet 4.5:

1. **Domain-grounded system prompt** — model is anchored as a senior ADaM
   programmer with explicit no-fabrication rules
2. **Structured-output design** — JSON schema enforced via prompt with
   multi-strategy JSON recovery (direct parse → markdown strip → bracket
   extraction)
3. **Confidence scoring** — 4 sub-scores (0–25 each) producing a 0–100 total
4. **Explicit ambiguity surfacing** — model is rewarded for saying "I don't
   know" rather than guessing

---

## Roadmap

- [x] **Day 1** — Minimal pipeline: SAP excerpt → JSON spec with confidence (9 variables, 0 hallucinations)
- [ ] **Day 2** — Pydantic schema validation + batch processing + Excel export
- [ ] **Day 3** — Confidence recalibration + non-standard variable name suggestions + dependency-aware review flags
- [ ] **Day 4** — Streamlit review UI: side-by-side SAP text and spec table with hover-to-highlight traceability
- [ ] **Day 5** — Evaluation against CDISC Pilot Project ground truth
- [ ] **Day 6** — Demo video + writeup
- [ ] **Day 7** — Public launch (LinkedIn / blog)

---

## Project structure

```text
sap-to-adam/
├── README.md
├── setup.sh
├── requirements.txt
├── .env.example
├── data/
│   └── sap_excerpts/
│       ├── treatment_dates.txt
│       ├── analysis_populations.txt
│       └── demographics.txt
├── src/
│   └── extract.py              # Day 1 minimal pipeline
└── outputs/                    # Generated JSON specs
```

---

## Notes on the design

**Why not just fine-tune?** ADaM derivations are highly study-specific. Every
SAP defines "baseline", "treatment-emergent", and analysis populations
slightly differently. A general LLM with strong prompt anchoring + per-study
SAP context outperforms a fine-tuned model on tasks where the specification
itself is the input.

**Why confidence scoring?** Statistical programmers will not trust opaque
AI output for regulatory deliverables. Surfacing per-dimension confidence
makes the model's reasoning legible and gives reviewers a triage signal.

**Why traceability?** Every CDISC submission requires full lineage from raw
data to analysis result. A tool that breaks this chain cannot be used in
production. Each generated spec entry stores the exact SAP sentence(s) it
was derived from.

---

## Author

Yuji Chen — biostatistician, AI tooling for clinical trials.
[Personal site](https://ycycycycyc.github.io/personalwebsite) ·
[GitHub](https://github.com/ycycycycyc)
