#!/usr/bin/env python3
"""AI Cold Email Personaliser — skeleton (v0, template-based).

Takes EITHER pasted text about a prospect OR a public company website URL
and outputs 3 personalised cold-email opening lines (EN) + 1 Roman-Urdu
variant, each annotated with the input fact it used.

HARD RULES (by design):
- Personalisation is grounded ONLY in the input text. Every line traces to a
  specific extracted fact. Nothing is invented: no fake names, numbers,
  awards, or claims.
- If the input has too little usable detail, the output says so and the
  lines are explicitly labelled generic-but-honest.
- NO email sending. NO LinkedIn scraping (LinkedIn input = user-pasted text
  only). NO contacting anyone. NO login, NO bot-check bypassing.
- Stdlib only. No API keys. (An LLM generator may be added later behind an
  env var; v0 works with zero keys.)

Usage:
    python personaliser.py --input "BrightSmile Dental Clinic, based in Lahore..."
    python personaliser.py --input https://example.com
    python personaliser.py --input-file samples/sample_clinic.txt
    python personaliser.py --input "..." --no-urdu
"""

import argparse
import html
import re
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Fact extraction (rule-based, input text only)
# ---------------------------------------------------------------------------

KNOWN_CITIES = [
    "Lahore", "Karachi", "Islamabad", "Rawalpindi", "Larkana", "Hyderabad",
    "Faisalabad", "Multan", "Peshawar", "Quetta", "Sialkot",
    "Dubai", "Abu Dhabi", "Sharjah", "Ajman", "Riyadh", "Jeddah",
    "Dammam", "Doha", "Muscat", "Kuwait City", "London", "Manchester",
]

SERVICE_KEYWORDS = [
    "orthodontics", "dental implants", "dental", "dermatology", "skin care",
    "hair transplant", "physiotherapy", "IVF", "fertility", "cardiology",
    "paediatrics", "pediatrics", "pharmacy", "optometry", "chiropractic",
    "fashion", "lawn", "formal wear", "electronics", "furniture",
    "grocery", "beauty", "salon", "fitness", "bakery", "jewellery",
    "jewelry", "automotive", "real estate", "homoeopathy", "homeopathy",
]

OFFERING_PATTERNS = [
    (r"24\s*/\s*7", "24/7 availability"),
    (r"online booking", "online booking"),
    (r"free delivery", "free delivery"),
    (r"home delivery", "home delivery"),
    (r"same-?day (?:dispatch|delivery)", "same-day dispatch/delivery"),
    (r"emergency (?:care|services?)", "emergency care"),
    (r"cash on delivery", "cash on delivery"),
]


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _find_name(text):
    """Best-effort org name from explicit patterns only. Returns None if unsure."""
    m = re.search(
        r"(?:welcome to|about)\s+([A-Z][A-Za-z0-9&'.-]{1,50}?)(?:[,.]|$)",
        text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\s+"
        r"(?:Clinic|Dental|Hospital|Pharmacy|Store|Studio|Centre|Center|"
        r"Medical|Polyclinic))\b", text)
    if m:
        return m.group(1).strip()
    return None


def extract_facts(text):
    """Return a list of facts: dicts with kind, detail, evidence (source snippet)."""
    facts = []
    seen = set()

    def add(kind, detail, evidence):
        key = (kind, detail.lower())
        if key in seen:
            return
        seen.add(key)
        facts.append({"kind": kind, "detail": detail, "evidence": evidence})

    name = _find_name(text)
    if name:
        add("name", name, "name pattern in input text")

    for city in KNOWN_CITIES:
        if re.search(r"\b" + re.escape(city) + r"\b", text):
            add("location", city, "city name appears in input text")
            break
    if not any(f["kind"] == "location" for f in facts):
        m = re.search(
            r"(?:based in|located in|serving)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)",
            text)
        if m:
            add("location", m.group(1).strip(), "location phrase in input text")

    for kw in SERVICE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            add("service", kw, "service keyword appears in input text")

    m = re.search(r"(\d+\+?\s*years?(?:\s+of experience)?)", text, re.IGNORECASE)
    if m:
        add("experience", m.group(0).strip(), "experience phrase in input text")
    else:
        m = re.search(r"\bsince\s+(\d{4})\b", text)
        if m:
            add("experience", "in business since " + m.group(1),
                "founding-year phrase in input text")

    for pattern, label in OFFERING_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            add("offering", label, "offering phrase in input text")

    for sent in _sentences(text):
        if re.search(r"speciali[sz]e|we offer|we provide|our services|expert",
                     sent, re.IGNORECASE):
            snippet = sent if len(sent) <= 140 else sent[:137] + "..."
            add("specialty_sentence", snippet, "specialty sentence from input text")
            break

    return facts


# ---------------------------------------------------------------------------
# Line generation (templates filled ONLY with extracted facts)
# ---------------------------------------------------------------------------

def _get(facts, kind):
    for f in facts:
        if f["kind"] == kind:
            return f
    return None


MEDICAL_SERVICES = {
    "orthodontics", "dental implants", "dental", "dermatology", "skin care",
    "hair transplant", "physiotherapy", "IVF", "fertility", "cardiology",
    "paediatrics", "pediatrics", "pharmacy", "optometry", "chiropractic",
    "homoeopathy", "homeopathy",
}

GENERIC_LINES = [
    "I came across your work online and wanted to reach out — could I ask "
    "how you currently handle bookings and missed calls?",
    "I found your business online and had one quick question — how do new "
    "enquiries reach you outside working hours?",
    "I wanted to reach out because I work on a problem many small businesses "
    "share: enquiries that arrive when nobody is free to answer — is that "
    "something you ever run into?",
]


def _article(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


def _business_noun(facts):
    """'practice' for clinics, 'business' otherwise — never guessed beyond that."""
    for f in facts:
        if f["kind"] == "service" and f["detail"] in MEDICAL_SERVICES:
            return "practice"
    return "business"


def generate_lines(facts):
    """Return (lines, grounded) where lines = [(line, fact_note)] and grounded
    is True when at least 2 lines trace to real input facts."""
    name_f = _get(facts, "name")
    name = name_f["detail"] if name_f else "your practice"
    service_f = _get(facts, "service")
    location_f = _get(facts, "location")
    exp_f = _get(facts, "experience")
    offering_f = _get(facts, "offering")
    noun = _business_noun(facts)
    noun_plural = "practices" if noun == "practice" else "businesses"

    lines = []

    if service_f:
        lines.append((
            "I noticed {name} specialises in {service} — I had one idea "
            "about how {noun_plural} like yours handle bookings and missed calls "
            "that I wanted to run past you.".format(
                name=name, service=service_f["detail"], noun_plural=noun_plural),
            "Used fact: service = '{}' (from input text)".format(
                service_f["detail"]),
        ))
    if location_f and service_f:
        lines.append((
            "Seeing {art} {service} {noun} serving {loc}, I wondered how "
            "your front desk copes with after-hours enquiries.".format(
                art=_article(service_f["detail"]),
                service=service_f["detail"], noun=noun,
                loc=location_f["detail"]),
            "Used facts: service = '{}', location = '{}' (from input text)".format(
                service_f["detail"], location_f["detail"]),
        ))
    elif location_f:
        lines.append((
            "I came across your work serving {loc} and wanted to ask one quick "
            "question about how new enquiries reach you.".format(
                loc=location_f["detail"]),
            "Used fact: location = '{}' (from input text)".format(
                location_f["detail"]),
        ))
    if exp_f:
        lines.append((
            "With {exp} behind {name}, your reputation clearly does a lot of "
            "the talking — I wanted to ask how you currently capture "
            "enquiries that arrive outside working hours.".format(
                exp=exp_f["detail"], name=name),
            "Used fact: experience = '{}' (from input text)".format(
                exp_f["detail"]),
        ))
    if offering_f and len(lines) < 3:
        lines.append((
            "I saw you already offer {off} — that tells me you care about "
            "making things easy for patients/customers, which is exactly why "
            "I wanted to reach out.".format(off=offering_f["detail"]),
            "Used fact: offering = '{}' (from input text)".format(
                offering_f["detail"]),
        ))

    grounded = len(lines) >= 2
    generic_idx = 0
    while len(lines) < 3:
        lines.append((
            GENERIC_LINES[generic_idx % len(GENERIC_LINES)],
            "GENERIC (labelled honest): no specific input fact used — "
            "input had too little usable detail for this line.",
        ))
        generic_idx += 1
    return lines[:3], grounded


def roman_urdu_variant(facts):
    name_f = _get(facts, "name")
    name = name_f["detail"] if name_f else "aap ka clinic/store"
    service_f = _get(facts, "service")
    location_f = _get(facts, "location")
    if service_f and location_f:
        line = ("Maine dekha ke {name} {loc} me {service} ki khidmat deta "
                "hai — kya aap ke yahan missed calls ya booking ka masla "
                "kabhi hota hai?".format(
                    name=name, loc=location_f["detail"],
                    service=service_f["detail"]))
        note = ("Used facts: service = '{}', location = '{}' "
                "(from input text)".format(
                    service_f["detail"], location_f["detail"]))
    elif service_f:
        line = ("Maine dekha ke {name} {service} me maharat rakhta hai — "
                "kya booking aur missed calls ke liye koi behtar nizam "
                "chahiye?".format(name=name, service=service_f["detail"]))
        note = ("Used fact: service = '{}' (from input text)".format(
            service_f["detail"]))
    else:
        line = ("Maine aap ka kaam online dekha aur rabta karna chaha — "
                "kya booking aur missed calls ke liye koi behtar nizam "
                "chahiye?")
        note = ("GENERIC (labelled honest): no specific input fact used.")
    return line, note


# ---------------------------------------------------------------------------
# URL fetch (public homepage text only; failures are reported, never faked)
# ---------------------------------------------------------------------------

def fetch_url_text(url, timeout=15):
    req = urllib.request.Request(
        url, headers={"User-Agent": "ColdEmailPersonaliser-skeleton/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as exc:
        return None, ("Could not fetch URL ({}). Paste the prospect's text "
                      "instead with --input \"...\".".format(exc))
    # Strip scripts/styles/tags, keep visible text only.
    raw = re.sub(r"<script.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(re.sub(r"\s+", " ", raw)).strip()
    if not text:
        return None, ("Fetched the URL but found no readable text. "
                      "Paste the prospect's text instead.")
    return text[:4000], None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Cold Email Personaliser skeleton: input text or public URL "
                    "-> 3 grounded opening lines + 1 Roman-Urdu variant.")
    parser.add_argument("--input", dest="inp", default=None,
                        help="Pasted prospect text OR a public website URL.")
    parser.add_argument("--input-file", default=None,
                        help="Read prospect text from a file instead.")
    parser.add_argument("--no-urdu", action="store_true",
                        help="Skip the Roman-Urdu variant.")
    args = parser.parse_args(argv)

    if args.input_file:
        try:
            with open(args.input_file, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print("Error: cannot read input file: {}".format(exc), file=sys.stderr)
            return 2
        source = "file: " + args.input_file
    elif args.inp:
        if args.inp.startswith(("http://", "https://")):
            text, err = fetch_url_text(args.inp)
            if err:
                print("Error: " + err, file=sys.stderr)
                return 2
            source = "URL: " + args.inp
        else:
            text, source = args.inp, "pasted text"
    else:
        parser.error("--input or --input-file is required")
        return 2

    facts = extract_facts(text)
    lines, grounded = generate_lines(facts)

    print("Source: {}".format(source))
    print("Facts found in input: {}".format(
        ", ".join("{} = {}".format(f["kind"], f["detail"]) for f in facts)
        or "none"))
    if not grounded:
        print("Note: input had too little usable detail — lines below marked "
              "GENERIC are honest fallbacks, not personalised claims.")
    print()
    for i, (line, note) in enumerate(lines, 1):
        print("Line {}: {}".format(i, line))
        print("  [{}]".format(note))
        print()
    if not args.no_urdu:
        urdu_line, urdu_note = roman_urdu_variant(facts)
        print("Roman-Urdu variant: {}".format(urdu_line))
        print("  [{}]".format(urdu_note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
