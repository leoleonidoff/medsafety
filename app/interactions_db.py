"""Curated drug list and pairwise interaction table.

This is a development-only dataset. See SPEC section 3 disclaimer.
"""
from __future__ import annotations


# (name, generic, drug_class, rxnorm_cui)
DRUGS: list[tuple[str, str, str, str]] = [
    ("Coumadin", "warfarin", "anticoagulant", "11289"),
    ("Xarelto", "rivaroxaban", "anticoagulant", "1114195"),
    ("Eliquis", "apixaban", "anticoagulant", "1364430"),
    ("Pradaxa", "dabigatran", "anticoagulant", "1037045"),
    ("Plavix", "clopidogrel", "antiplatelet", "32968"),
    ("Aspirin", "aspirin", "antiplatelet / NSAID", "1191"),
    ("Advil", "ibuprofen", "NSAID", "5640"),
    ("Aleve", "naproxen", "NSAID", "7258"),
    ("Celebrex", "celecoxib", "NSAID (COX-2)", "140587"),
    ("Mobic", "meloxicam", "NSAID", "6915"),
    ("Toradol", "ketorolac", "NSAID", "35827"),
    ("Prozac", "fluoxetine", "SSRI", "4493"),
    ("Zoloft", "sertraline", "SSRI", "36437"),
    ("Lexapro", "escitalopram", "SSRI", "321988"),
    ("Celexa", "citalopram", "SSRI", "2556"),
    ("Paxil", "paroxetine", "SSRI", "32937"),
    ("Effexor", "venlafaxine", "SNRI", "39786"),
    ("Cymbalta", "duloxetine", "SNRI", "72625"),
    ("Tramadol", "tramadol", "opioid", "10689"),
    ("OxyContin", "oxycodone", "opioid", "7804"),
    ("Vicodin", "hydrocodone", "opioid", "5489"),
    ("MS Contin", "morphine", "opioid", "7052"),
    ("Lipitor", "atorvastatin", "statin", "83367"),
    ("Crestor", "rosuvastatin", "statin", "301542"),
    ("Zocor", "simvastatin", "statin", "36567"),
    ("Pravachol", "pravastatin", "statin", "42463"),
    ("Lopressor", "metoprolol", "beta-blocker", "6918"),
    ("Tenormin", "atenolol", "beta-blocker", "1202"),
    ("Coreg", "carvedilol", "beta-blocker", "20352"),
    ("Inderal", "propranolol", "beta-blocker", "8787"),
    ("Prinivil", "lisinopril", "ACE inhibitor", "29046"),
    ("Vasotec", "enalapril", "ACE inhibitor", "3827"),
    ("Altace", "ramipril", "ACE inhibitor", "35296"),
    ("Cozaar", "losartan", "ARB", "52175"),
    ("Diovan", "valsartan", "ARB", "69749"),
    ("Z-Pak", "azithromycin", "macrolide antibiotic", "18631"),
    ("Biaxin", "clarithromycin", "macrolide antibiotic", "21212"),
    ("Cipro", "ciprofloxacin", "fluoroquinolone", "2551"),
    ("Levaquin", "levofloxacin", "fluoroquinolone", "82122"),
    ("Bactrim", "sulfamethoxazole-trimethoprim", "sulfonamide", "10180"),
    ("Amoxil", "amoxicillin", "penicillin antibiotic", "723"),
    ("Benadryl", "diphenhydramine", "first-gen antihistamine", "3498"),
    ("Claritin", "loratadine", "second-gen antihistamine", "28889"),
    ("Zyrtec", "cetirizine", "second-gen antihistamine", "20610"),
    ("Prilosec", "omeprazole", "PPI", "7646"),
    ("Nexium", "esomeprazole", "PPI", "283742"),
    ("Protonix", "pantoprazole", "PPI", "40790"),
    ("Xanax", "alprazolam", "benzodiazepine", "596"),
    ("Ativan", "lorazepam", "benzodiazepine", "6470"),
    ("Synthroid", "levothyroxine", "thyroid hormone", "10582"),
]


# Class groupings (generic names) used to expand the matrix.
ANTICOAGULANTS = ["warfarin", "rivaroxaban", "apixaban", "dabigatran"]
ANTIPLATELETS = ["clopidogrel", "aspirin"]
NSAIDS = ["ibuprofen", "naproxen", "celecoxib", "meloxicam", "ketorolac", "aspirin"]
SSRIS = ["fluoxetine", "sertraline", "escitalopram", "citalopram", "paroxetine"]
SNRIS = ["venlafaxine", "duloxetine"]
OPIOIDS = ["tramadol", "oxycodone", "hydrocodone", "morphine"]
STATINS_3A4 = ["atorvastatin", "simvastatin"]
BETA_BLOCKERS = ["metoprolol", "atenolol", "carvedilol", "propranolol"]
ACE_INHIBITORS = ["lisinopril", "enalapril", "ramipril"]
ARBS = ["losartan", "valsartan"]
MACROLIDES = ["azithromycin", "clarithromycin"]
FLUOROQUINOLONES = ["ciprofloxacin", "levofloxacin"]
PPIS = ["omeprazole", "esomeprazole", "pantoprazole"]
BENZOS = ["alprazolam", "lorazepam"]
FIRST_GEN_ANTIHIST = ["diphenhydramine"]


# Anchor pairs from the SPEC. These override any pattern-expanded entries.
ANCHOR_PAIRS: list[tuple[str, str, str, str]] = [
    ("warfarin", "ibuprofen", "major",
     "NSAID inhibition of platelet aggregation plus gastric mucosal injury increases bleeding"),
    ("warfarin", "aspirin", "major",
     "Additive antiplatelet effect on top of anticoagulation"),
    ("warfarin", "naproxen", "major",
     "Same NSAID mechanism as ibuprofen, longer half-life"),
    ("warfarin", "azithromycin", "moderate",
     "Macrolide displacement and CYP effects raise INR"),
    ("warfarin", "ciprofloxacin", "major",
     "Fluoroquinolone inhibition of CYP1A2/3A4 raises warfarin levels"),
    ("warfarin", "sulfamethoxazole-trimethoprim", "major",
     "TMP-SMX inhibits CYP2C9, sharply raising INR"),
    ("warfarin", "fluoxetine", "moderate",
     "SSRI CYP2C9 inhibition and platelet serotonin depletion"),
    ("apixaban", "ibuprofen", "major",
     "Combined anticoagulant and antiplatelet bleeding risk"),
    ("rivaroxaban", "clarithromycin", "major",
     "Strong CYP3A4 and P-gp inhibition increases rivaroxaban exposure"),
    ("clopidogrel", "omeprazole", "moderate",
     "PPI inhibition of CYP2C19 reduces clopidogrel activation"),
    ("clopidogrel", "aspirin", "moderate",
     "Additive antiplatelet effect, sometimes intentional, must be reviewed"),
    ("ibuprofen", "lisinopril", "moderate",
     "NSAID blunts ACE inhibitor antihypertensive effect, raises kidney risk"),
    ("naproxen", "losartan", "moderate",
     "NSAID plus ARB raises hyperkalemia and AKI risk"),
    ("ibuprofen", "aspirin", "moderate",
     "Ibuprofen blocks aspirin's antiplatelet binding site"),
    ("celecoxib", "warfarin", "major",
     "COX-2 selective NSAID still raises INR via CYP2C9"),
    ("fluoxetine", "sertraline", "contraindicated",
     "Two SSRIs - serotonin syndrome risk, never co-prescribed"),
    ("fluoxetine", "tramadol", "major",
     "Serotonergic plus seizure-threshold lowering"),
    ("sertraline", "tramadol", "major",
     "Same serotonergic risk"),
    ("escitalopram", "duloxetine", "major",
     "SSRI plus SNRI - serotonin syndrome risk"),
    ("paroxetine", "metoprolol", "moderate",
     "Paroxetine inhibits CYP2D6, raises metoprolol levels and bradycardia risk"),
    ("simvastatin", "clarithromycin", "contraindicated",
     "Strong CYP3A4 inhibition causes statin myopathy and rhabdomyolysis"),
    ("atorvastatin", "clarithromycin", "major",
     "CYP3A4 inhibition raises atorvastatin levels"),
    ("simvastatin", "azithromycin", "moderate",
     "Weak CYP3A4 effect, monitor for muscle pain"),
    ("oxycodone", "alprazolam", "contraindicated",
     "Opioid plus benzodiazepine respiratory depression"),
    ("hydrocodone", "lorazepam", "contraindicated",
     "Same opioid plus benzo CNS depression"),
    ("tramadol", "alprazolam", "major",
     "CNS depression plus seizure-threshold lowering"),
    ("diphenhydramine", "lorazepam", "moderate",
     "Additive sedation and anticholinergic burden"),
    ("ciprofloxacin", "levothyroxine", "moderate",
     "Cation chelation reduces thyroxine absorption"),
    ("omeprazole", "levothyroxine", "minor",
     "Reduced gastric acid mildly lowers thyroxine absorption"),
    ("metoprolol", "propranolol", "contraindicated",
     "Two beta-blockers - additive bradycardia and AV block"),
]


def _norm(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def build_pairs() -> list[tuple[str, str, str, str]]:
    """Expand anchor pairs with class-pattern pairs. Anchors win on duplicates."""
    seen: dict[tuple[str, str], tuple[str, str, str, str]] = {}

    for a, b, severity, mech in ANCHOR_PAIRS:
        key = _norm(a, b)
        seen[key] = (key[0], key[1], severity, mech)

    def add(a: str, b: str, severity: str, mech: str) -> None:
        if a == b:
            return
        key = _norm(a, b)
        if key in seen:
            return
        seen[key] = (key[0], key[1], severity, mech)

    # Every NSAID against every anticoagulant.
    for nsaid in NSAIDS:
        for anti in ANTICOAGULANTS:
            add(nsaid, anti, "major",
                "NSAID antiplatelet effect plus anticoagulation raises GI and intracranial bleeding risk")

    # Antiplatelets against anticoagulants.
    for ap in ANTIPLATELETS:
        for anti in ANTICOAGULANTS:
            add(ap, anti, "major",
                "Antiplatelet on top of anticoagulant compounds bleeding risk")

    # NSAID against every ACE inhibitor.
    for nsaid in NSAIDS:
        for ace in ACE_INHIBITORS:
            add(nsaid, ace, "moderate",
                "NSAID blunts ACE inhibitor antihypertensive effect, raises AKI and hyperkalemia risk")

    # NSAID against every ARB.
    for nsaid in NSAIDS:
        for arb in ARBS:
            add(nsaid, arb, "moderate",
                "NSAID plus ARB raises hyperkalemia and acute kidney injury risk")

    # NSAID + NSAID -> additive GI / renal toxicity.
    for i, n1 in enumerate(NSAIDS):
        for n2 in NSAIDS[i + 1:]:
            add(n1, n2, "moderate",
                "Two NSAIDs together increase GI bleeding and renal injury without added benefit")

    # Every macrolide against every CYP3A4-sensitive statin.
    for mac in MACROLIDES:
        for st in STATINS_3A4:
            sev = "contraindicated" if (mac == "clarithromycin" and st == "simvastatin") else "major"
            add(mac, st, sev,
                "Macrolide CYP3A4 inhibition raises statin levels and myopathy risk")

    # Fluoroquinolone against every anticoagulant.
    for fq in FLUOROQUINOLONES:
        for anti in ANTICOAGULANTS:
            add(fq, anti, "major",
                "Fluoroquinolone CYP inhibition and gut flora disruption raise anticoagulant effect")

    # Sulfa antibiotic against every anticoagulant.
    for anti in ANTICOAGULANTS:
        add("sulfamethoxazole-trimethoprim", anti, "major",
            "TMP-SMX inhibits CYP2C9 and competes for albumin binding, raising bleeding risk")

    # SSRI + SSRI, SSRI + SNRI, SNRI + SNRI -> serotonergic.
    sero = SSRIS + SNRIS
    for i, a in enumerate(sero):
        for b in sero[i + 1:]:
            add(a, b, "major",
                "Two serotonergic agents - cumulative risk of serotonin syndrome")

    # SSRI/SNRI + tramadol -> major serotonergic + seizure.
    for s in sero:
        add(s, "tramadol", "major",
            "Serotonergic agent plus tramadol - serotonin syndrome and lowered seizure threshold")

    # Every opioid against every benzodiazepine.
    for op in OPIOIDS:
        for bz in BENZOS:
            sev = "contraindicated" if op in ("oxycodone", "hydrocodone", "morphine") else "major"
            add(op, bz, sev,
                "Opioid plus benzodiazepine causes additive CNS and respiratory depression")

    # Opioid + first-gen antihistamine -> additive sedation.
    for op in OPIOIDS:
        for ah in FIRST_GEN_ANTIHIST:
            add(op, ah, "moderate",
                "Opioid plus sedating antihistamine adds CNS depression and falls risk")

    # Benzo + first-gen antihistamine -> additive sedation.
    for bz in BENZOS:
        for ah in FIRST_GEN_ANTIHIST:
            add(bz, ah, "moderate",
                "Benzodiazepine plus sedating antihistamine adds CNS depression")

    # Beta-blocker + beta-blocker -> contraindicated.
    for i, b1 in enumerate(BETA_BLOCKERS):
        for b2 in BETA_BLOCKERS[i + 1:]:
            add(b1, b2, "contraindicated",
                "Two beta-blockers cause additive bradycardia and AV block")

    # ACE inhibitor + ARB -> major (dual RAAS).
    for ace in ACE_INHIBITORS:
        for arb in ARBS:
            add(ace, arb, "major",
                "Dual RAAS blockade raises hyperkalemia, hypotension, and renal failure risk")

    # ACE + ACE, ARB + ARB.
    for i, a in enumerate(ACE_INHIBITORS):
        for b in ACE_INHIBITORS[i + 1:]:
            add(a, b, "contraindicated",
                "Two ACE inhibitors should not be combined")
    for i, a in enumerate(ARBS):
        for b in ARBS[i + 1:]:
            add(a, b, "contraindicated",
                "Two ARBs should not be combined")

    # PPI + clopidogrel.
    for ppi in PPIS:
        sev = "moderate" if ppi in ("omeprazole", "esomeprazole") else "minor"
        add(ppi, "clopidogrel", sev,
            "PPI inhibition of CYP2C19 reduces clopidogrel activation")

    # PPI + levothyroxine -> minor.
    for ppi in PPIS:
        add(ppi, "levothyroxine", "minor",
            "Reduced gastric acid mildly lowers thyroxine absorption")

    # Fluoroquinolone + levothyroxine -> moderate (chelation).
    for fq in FLUOROQUINOLONES:
        add(fq, "levothyroxine", "moderate",
            "Cation chelation reduces thyroxine absorption when given together")

    # SSRI + NSAID -> moderate (bleeding).
    for s in SSRIS:
        for n in NSAIDS:
            add(s, n, "moderate",
                "SSRI plus NSAID increases GI bleeding risk via platelet serotonin depletion")

    # SSRI + anticoagulant -> moderate.
    for s in SSRIS:
        for a in ANTICOAGULANTS:
            add(s, a, "moderate",
                "SSRI platelet effect adds bleeding risk on top of anticoagulation")

    # SNRI + NSAID -> moderate.
    for s in SNRIS:
        for n in NSAIDS:
            add(s, n, "moderate",
                "SNRI plus NSAID increases GI bleeding risk")

    # Macrolide + benzodiazepine (CYP3A4) -> moderate.
    for mac in MACROLIDES:
        for bz in BENZOS:
            add(mac, bz, "moderate",
                "Macrolide CYP3A4 inhibition raises benzodiazepine levels and sedation")

    return sorted(seen.values(), key=lambda r: (r[0], r[1]))
