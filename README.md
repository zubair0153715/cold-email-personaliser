# AI Cold Email Personaliser — skeleton (v0)

Original, minimal CLI. Pasted prospect text (or a public company homepage URL)
in → 3 personalised cold-email opening lines (EN) + 1 Roman-Urdu variant out.
Every line is annotated with the input fact it used.

## Install

No dependencies beyond Python 3.8+ (stdlib only). No API key needed.

```bash
cd cold-email-personaliser
python3 personaliser.py --input-file samples/sample_clinic.txt
```

## Usage

```bash
# Pasted text (e.g. a clinic homepage paragraph, or a LinkedIn "about"
# paragraph the user pasted themselves):
python3 personaliser.py --input "BrightSmile Dental Clinic, based in Lahore. We specialise in orthodontics..."

# Public company website URL (homepage text only, no login):
python3 personaliser.py --input https://example.com

# From a file:
python3 personaliser.py --input-file samples/sample_store.txt

# Skip the Roman-Urdu variant:
python3 personaliser.py --input-file samples/sample_clinic.txt --no-urdu
```

## Examples

Example 1 — fictional dental clinic (see `samples/sample_clinic.txt`):

```
Source: file: samples/sample_clinic.txt
Facts found in input: name = BrightSmile Dental Clinic, location = Lahore,
service = orthodontics, service = dental implants, experience = 12 years of
experience, offering = online booking, offering = 24/7 availability

Line 1: I noticed BrightSmile Dental Clinic specialises in orthodontics — ...
  [Used fact: service = 'orthodontics' (from input text)]
...
Roman-Urdu variant: Maine dekha ke BrightSmile Dental Clinic Lahore me
orthodontics ki khidmat deta hai — ...
```

Example 2 — thin input (see `samples/sample_thin.txt`): the tool says the
input had too little usable detail and labels its fallback lines GENERIC
instead of inventing personalisation.

## Honest limits (v0)

- **Template-based, not AI.** Lines come from fixed templates filled with
  facts extracted by regex/keyword rules. An LLM generator may be added later
  as an OPTIONAL path behind an env var; v0 deliberately runs with zero keys.
- **Grounded or labelled.** A line either traces to a fact found in the
  input, or is explicitly marked GENERIC. It never invents names, numbers,
  awards, or claims about the prospect.
- **No sending.** This tool writes lines to stdout only. It never sends an
  email or message to anyone.
- **No LinkedIn scraping.** LinkedIn input means text the user pasted
  themselves. URL fetching is limited to a public homepage; if a fetch fails
  (bot check, login wall, network error) the tool says so and asks for
  pasted text instead of working around it.
- **Extraction is heuristic.** Name/location/service detection uses patterns
  and keyword lists; unusual phrasing may be missed, in which case the tool
  falls back to GENERIC lines rather than guessing.
