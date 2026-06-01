# MedSafety - SPEC

> Historical reference. The shipped product diverged from this spec:
> auth / accounts have been removed, the instance is single-tenant
> (one patient = one server), and the User table was replaced with a
> single Patient row pinned to id=1. The endpoint shapes and severity
> model below are still accurate.

## 1. Domain and motivation

Polypharmacy is a routine outcome of a fragmented care system. A patient who sees
a cardiologist, a primary care physician, and a psychiatrist within the same
quarter typically walks out with prescriptions written from three different
charts, none of which contain a complete current medication list. Pharmacy
software catches some of this at dispense time, but only when every prescription
flows through the same pharmacy chain - and patients increasingly do not. The
gap that remains is the patient-side check: is the combination of pills already
in my drawer safe to keep taking together? Consumer "did you take your pill?"
apps do not answer that question. MedSafety does. It maintains a user's active
prescription list, runs a pairwise interaction check across every drug pair on
that list whenever the list changes, ranks the results by clinical severity
(contraindicated, major, moderate, minor), and uses an LLM to turn each clinical
mechanism into a two-paragraph plain-English explanation a non-clinician can act
on. Daily dose reminders and an adherence streak are included so the same app
also handles the easier half of the problem.

## 2. Stack

| Layer        | Choice                                                             |
|--------------|--------------------------------------------------------------------|
| Backend      | Python 3.12, Flask 3, SQLAlchemy 2, Flask-JWT-Extended, bcrypt, gunicorn (gthread, 2x4) |
| Persistence  | SQLite at `medsafety/data/medsafety.db`                            |
| Container    | `python:3.12-alpine`, `tini` entrypoint, non-root user `meds`      |
| Port         | 8004                                                               |
| Frontend     | Vue 3 ESM build from CDN, no build step, no npm, no `.vue` files. Single `index.html` plus `app.js` with inline template-string components. Tailwind CSS via the CDN play build. Small `styles.css` for overrides only. |
| State        | One module-scoped `reactive()` store object exported from `app.js`. No Pinia, no Vuex. |
| Icons        | Heroicons Outline 24px, inlined as SVG. Required set: pill, calendar, alert-triangle, shield-check, plus, x-mark, check, clock, magnifying-glass, user, arrow-right-on-rectangle (logout), trash. |
| Fonts        | Google Fonts: `Plus Jakarta Sans` 400/500/600/700 (UI) and `Space Mono` 400/700 (dosage numerals, drug codes). No other fonts. |
| HTTP client  | Backend uses `urllib.request` only. No `requests`, no `httpx`. Same module is used for RxNorm and for the LLM providers. |
| Schemas      | `pydantic` v2 for request/response validation. Pick once and stay consistent across all modules. Do not also import `marshmallow`. |

### Theme palette (light, clinical)

| Token             | Hex        | Use                                |
|-------------------|------------|------------------------------------|
| bg                | `#ffffff`  | page background                    |
| surface           | `#f8fafc`  | cards, drawer panels               |
| border            | `#e2e8f0`  | hairlines, input borders           |
| text              | `#0f172a`  | primary text                       |
| text-muted        | `#64748b`  | secondary text, captions           |
| primary           | `#0369a1`  | primary buttons, links             |
| primary-hover     | `#075985`  | hover state                        |
| sev-contra-fg     | `#7f1d1d`  | contraindicated label              |
| sev-contra-bg     | `#fee2e2`  | contraindicated chip background    |
| sev-major-fg      | `#dc2626`  | major label                        |
| sev-major-bg      | `#fef2f2`  | major chip background              |
| sev-moderate-fg   | `#d97706`  | moderate label                     |
| sev-moderate-bg   | `#fef3c7`  | moderate chip background           |
| sev-minor-fg      | `#0369a1`  | minor label                        |
| sev-minor-bg      | `#dbeafe`  | minor chip background              |

Cards: 8px radius, shadow `0 1px 3px rgba(0,0,0,0.06)`. Numbers (dosage mg,
streak days, take rate) render with `font-variant-numeric: tabular-nums` in
`Space Mono`. Whitespace is generous: 24px section padding, 16px between cards.

## 3. Disclaimer

The following copy is part of the spec and must appear verbatim:

> MedSafety is a demonstration. Drug interaction data is a curated subset for
> development only and is not medical advice. Always consult a pharmacist or
> physician.

Placements:
1. Fixed footer on every page of the Vue app (below the main content,
   `text-muted`, small caps optional, never hidden behind a "dismiss" button).
2. First paragraph of `README.md`, in a `> blockquote`.
3. First content block under the "Interactions" tab, above the severity tiles,
   in `sev-minor-bg` with `text` color.
4. Top of the LLM-rendered explanation panel, prefixed with a small
   `alert-triangle` icon.

The disclaimer is never collapsed, dismissed, or moved behind a click.

## 4. RxNorm contract

Base URL: `https://rxnav.nlm.nih.gov/REST/`. No API key, no auth. All calls
have a 4-second timeout. All calls are server-side; the browser does not talk
to RxNorm directly.

### Endpoints used

| Purpose              | Endpoint                                          |
|----------------------|---------------------------------------------------|
| Name search          | `GET /drugs.json?name={q}`                        |
| Active ingredient    | `GET /rxcui/{cui}/related.json?tty=IN`            |

### Response fields consumed

From `/drugs.json`:
- `drugGroup.conceptGroup[].conceptProperties[].rxcui`   -> stored as `Drug.rxnorm_cui`
- `drugGroup.conceptGroup[].conceptProperties[].name`    -> stored as `Drug.name`
- `drugGroup.conceptGroup[].conceptProperties[].synonym` -> used to populate `Drug.generic_name` if missing
- `drugGroup.conceptGroup[].tty`                         -> only `SBD`, `SCD`, `IN`, `BN` rows are kept

From `/rxcui/{cui}/related.json?tty=IN`:
- `relatedGroup.conceptGroup[0].conceptProperties[0].name` -> `Drug.generic_name`
- `relatedGroup.conceptGroup[0].conceptProperties[0].rxcui` -> stored alongside generic name for later mapping

Drug class is NOT served by RxNorm in a usable form for this demo, so
`Drug.drug_class` is filled from the curated seed table (section 5) and is
never overwritten by an RxNorm response.

### Fallback policy

Trigger conditions for fallback: `URLError`, `socket.timeout`, HTTP status not
in `200..299`, JSON decode error, or empty `conceptGroup`. On any of these the
server returns results from the local curated drug table (section 5) filtered
by case-insensitive substring match on `name` or `generic_name`, ordered by
shortest-name first, capped at 20 rows. A `source` field is included on every
`/api/drugs/search` result: `"rxnorm"` or `"local"`. The frontend renders a
small "Offline drug list" caption when any result is `local`.

The fallback path must run with zero network access (mock/demo mode).

## 5. Interaction dataset

The curated drug list is 50 entries. Every drug has a known RxNorm CUI so the
seed runs offline. The list spans the 10 classes the spec calls out:

### Drug list (name / generic / class / RxNorm CUI)

| # | Brand or common name | Generic           | Class                   | RxCUI   |
|---|----------------------|-------------------|-------------------------|---------|
|  1| Coumadin             | warfarin          | anticoagulant           | 11289   |
|  2| Xarelto              | rivaroxaban       | anticoagulant           | 1114195 |
|  3| Eliquis              | apixaban          | anticoagulant           | 1364430 |
|  4| Pradaxa              | dabigatran        | anticoagulant           | 1037045 |
|  5| Plavix               | clopidogrel       | antiplatelet            | 32968   |
|  6| Aspirin              | aspirin           | antiplatelet / NSAID    | 1191    |
|  7| Advil                | ibuprofen         | NSAID                   | 5640    |
|  8| Aleve                | naproxen          | NSAID                   | 7258    |
|  9| Celebrex             | celecoxib         | NSAID (COX-2)           | 140587  |
| 10| Mobic                | meloxicam         | NSAID                   | 6915    |
| 11| Toradol              | ketorolac         | NSAID                   | 35827   |
| 12| Prozac               | fluoxetine        | SSRI                    | 4493    |
| 13| Zoloft               | sertraline        | SSRI                    | 36437   |
| 14| Lexapro              | escitalopram      | SSRI                    | 321988  |
| 15| Celexa               | citalopram        | SSRI                    | 2556    |
| 16| Paxil                | paroxetine        | SSRI                    | 32937   |
| 17| Effexor              | venlafaxine       | SNRI                    | 39786   |
| 18| Cymbalta             | duloxetine        | SNRI                    | 72625   |
| 19| Tramadol             | tramadol          | opioid                  | 10689   |
| 20| OxyContin            | oxycodone         | opioid                  | 7804    |
| 21| Vicodin              | hydrocodone       | opioid                  | 5489    |
| 22| MS Contin            | morphine          | opioid                  | 7052    |
| 23| Lipitor              | atorvastatin      | statin                  | 83367   |
| 24| Crestor              | rosuvastatin      | statin                  | 301542  |
| 25| Zocor                | simvastatin       | statin                  | 36567   |
| 26| Pravachol            | pravastatin       | statin                  | 42463   |
| 27| Lopressor            | metoprolol        | beta-blocker            | 6918    |
| 28| Tenormin             | atenolol          | beta-blocker            | 1202    |
| 29| Coreg                | carvedilol        | beta-blocker            | 20352   |
| 30| Inderal              | propranolol       | beta-blocker            | 8787    |
| 31| Prinivil             | lisinopril        | ACE inhibitor           | 29046   |
| 32| Vasotec              | enalapril         | ACE inhibitor           | 3827    |
| 33| Altace               | ramipril          | ACE inhibitor           | 35296   |
| 34| Cozaar               | losartan          | ARB                     | 52175   |
| 35| Diovan               | valsartan         | ARB                     | 69749   |
| 36| Z-Pak                | azithromycin      | macrolide antibiotic    | 18631   |
| 37| Biaxin               | clarithromycin    | macrolide antibiotic    | 21212   |
| 38| Cipro                | ciprofloxacin     | fluoroquinolone         | 2551    |
| 39| Levaquin             | levofloxacin      | fluoroquinolone         | 82122   |
| 40| Bactrim              | sulfamethoxazole-trimethoprim | sulfonamide | 10180  |
| 41| Amoxil               | amoxicillin       | penicillin antibiotic   | 723     |
| 42| Benadryl             | diphenhydramine   | first-gen antihistamine | 3498    |
| 43| Claritin             | loratadine        | second-gen antihistamine| 28889   |
| 44| Zyrtec               | cetirizine        | second-gen antihistamine| 20610   |
| 45| Prilosec             | omeprazole        | PPI                     | 7646    |
| 46| Nexium               | esomeprazole      | PPI                     | 283742  |
| 47| Protonix             | pantoprazole      | PPI                     | 40790   |
| 48| Xanax                | alprazolam        | benzodiazepine          | 596     |
| 49| Ativan               | lorazepam         | benzodiazepine          | 6470    |
| 50| Synthroid            | levothyroxine     | thyroid hormone         | 10582   |

### Interaction matrix

Implemented in `app/interactions_db.py` as a Python list of tuples
`(generic_a, generic_b, severity, mechanism)`. The seed script resolves the
generic names to `Drug.id` and inserts rows with `drug_a_id < drug_b_id`.
Target size: roughly 200 pair entries. The 30 anchor pairs below are
prescriptive; the implementer fills the remaining ~170 from common
clinical-reference patterns (NSAID x ACE/ARB, statin x macrolide,
antidepressant x antidepressant, opioid x benzodiazepine, etc.).

| #  | Pair                                     | Severity         | Mechanism (one line, clinical)                                                          |
|----|------------------------------------------|------------------|-----------------------------------------------------------------------------------------|
|  1 | warfarin + ibuprofen                     | major            | NSAID inhibition of platelet aggregation plus gastric mucosal injury increases bleeding |
|  2 | warfarin + aspirin                       | major            | Additive antiplatelet effect on top of anticoagulation                                  |
|  3 | warfarin + naproxen                      | major            | Same NSAID mechanism as ibuprofen, longer half-life                                     |
|  4 | warfarin + azithromycin                  | moderate         | Macrolide displacement and CYP effects raise INR                                        |
|  5 | warfarin + ciprofloxacin                 | major            | Fluoroquinolone inhibition of CYP1A2/3A4 raises warfarin levels                         |
|  6 | warfarin + sulfamethoxazole-trimethoprim | major            | TMP-SMX inhibits CYP2C9, sharply raising INR                                            |
|  7 | warfarin + fluoxetine                    | moderate         | SSRI CYP2C9 inhibition and platelet serotonin depletion                                 |
|  8 | apixaban + ibuprofen                     | major            | Combined anticoagulant and antiplatelet bleeding risk                                   |
|  9 | rivaroxaban + clarithromycin             | major            | Strong CYP3A4 and P-gp inhibition increases rivaroxaban exposure                        |
| 10 | clopidogrel + omeprazole                 | moderate         | PPI inhibition of CYP2C19 reduces clopidogrel activation                                |
| 11 | clopidogrel + aspirin                    | moderate         | Additive antiplatelet effect, sometimes intentional, must be reviewed                   |
| 12 | ibuprofen + lisinopril                   | moderate         | NSAID blunts ACE inhibitor antihypertensive effect, raises kidney risk                  |
| 13 | naproxen + losartan                      | moderate         | NSAID plus ARB raises hyperkalemia and AKI risk                                         |
| 14 | ibuprofen + aspirin                      | moderate         | Ibuprofen blocks aspirin's antiplatelet binding site                                    |
| 15 | celecoxib + warfarin                     | major            | COX-2 selective NSAID still raises INR via CYP2C9                                       |
| 16 | fluoxetine + sertraline                  | contraindicated  | Two SSRIs - serotonin syndrome risk, never co-prescribed                                |
| 17 | fluoxetine + tramadol                    | major            | Serotonergic plus seizure-threshold lowering                                            |
| 18 | sertraline + tramadol                    | major            | Same serotonergic risk                                                                  |
| 19 | escitalopram + duloxetine                | major            | SSRI plus SNRI - serotonin syndrome risk                                                |
| 20 | paroxetine + metoprolol                  | moderate         | Paroxetine inhibits CYP2D6, raises metoprolol levels and bradycardia risk               |
| 21 | simvastatin + clarithromycin             | contraindicated  | Strong CYP3A4 inhibition causes statin myopathy and rhabdomyolysis                      |
| 22 | atorvastatin + clarithromycin            | major            | CYP3A4 inhibition raises atorvastatin levels                                            |
| 23 | simvastatin + azithromycin               | moderate         | Weak CYP3A4 effect, monitor for muscle pain                                             |
| 24 | oxycodone + alprazolam                   | contraindicated  | Opioid plus benzodiazepine respiratory depression                                       |
| 25 | hydrocodone + lorazepam                  | contraindicated  | Same opioid plus benzo CNS depression                                                   |
| 26 | tramadol + alprazolam                    | major            | CNS depression plus seizure-threshold lowering                                          |
| 27 | diphenhydramine + lorazepam              | moderate         | Additive sedation and anticholinergic burden                                            |
| 28 | ciprofloxacin + levothyroxine            | moderate         | Cation chelation reduces thyroxine absorption                                           |
| 29 | omeprazole + levothyroxine               | minor            | Reduced gastric acid mildly lowers thyroxine absorption                                 |
| 30 | metoprolol + propranolol                 | contraindicated  | Two beta-blockers - additive bradycardia and AV block                                   |

The 30 above are mandatory. The implementer extends to ~200 by applying the
same patterns across the rest of each class (every NSAID against every
anticoagulant, every macrolide against every statin, every SSRI against every
SSRI or SNRI, every opioid against every benzodiazepine, NSAID against every
ACE inhibitor and every ARB, fluoroquinolone against every anticoagulant,
PPI against every clopidogrel-like agent and against levothyroxine). Mechanism
strings are short, single-line, clinically phrased; the LLM is what turns them
into prose.

## 6. LLM contract

### Model selection order

1. OpenRouter, model from `OPENROUTER_MODEL` (default `meta-llama/llama-3.3-70b-instruct:free`), key `OPENROUTER_API_KEY`. Endpoint `https://openrouter.ai/api/v1/chat/completions`. 12 s timeout.
2. Anthropic, model from `ANTHROPIC_MODEL` (default `claude-haiku-4-5`), key `ANTHROPIC_API_KEY`. Endpoint `https://api.anthropic.com/v1/messages`. 12 s timeout.
3. Local template fallback (always available, no network).

Selection is per-call and lazy: if OpenRouter returns a non-2xx or times out,
Anthropic is tried; if Anthropic also fails, the template fires. `GET /api/health`
returns the engine the next call would use without actually calling it.

### Prompt template

Stored as a constant in `app/ai.py`. Variables interpolated by `.format()`.

```
Drugs: {drug_a_name} ({drug_a_class}) + {drug_b_name} ({drug_b_class})
Interaction severity: {severity}
Mechanism (clinical): {mechanism}

Write a 2-paragraph patient-friendly explanation. Plain English, no jargon.
Paragraph 1: what happens in the body when these two are combined.
Paragraph 2: what symptoms to watch for, and when to call a doctor versus
when it's a "mention at next visit" concern.
No bullet lists, no emojis. End with one short sentence reminding the
reader to consult their pharmacist if unsure.
```

System prompt for both providers:

```
You are a clinical pharmacology writer. Your job is to translate drug
interaction mechanisms into clear, calm, two-paragraph patient explanations.
You never invent severity. You never give dosing advice. You always end with
a one-sentence reminder to consult a pharmacist.
```

Generation params:
- `temperature` 0.4
- `max_tokens` 450
- No streaming. The response is fully consumed before returning.

### Fallback templates

Four templates, one per severity bucket. Each takes the same variables as
the prompt. Each produces exactly two paragraphs of plain English.
Mechanism is interpolated verbatim into paragraph 1. Paragraph 2 is bucket-
specific: contraindicated -> "stop and call prescriber now"; major -> "call
within 24 hours, watch for X Y Z"; moderate -> "mention at next visit, watch
for X"; minor -> "no action needed, useful to know". Each template ends
with: `If you are unsure, ask your pharmacist - they will check this
combination for you.`

### Caching

Cached on `Interaction.llm_explanation` keyed by interaction id. `llm_model`
records which engine produced it (`openrouter:<model>`, `anthropic:<model>`,
or `template`). The explain endpoint returns the cached value when present
unless `?refresh=true` is passed; refresh requires JWT and is the only way
to overwrite. Cache is never invalidated by edits to the prescription list -
the explanation is about the drug pair, not the patient.

## 7. Database schema

SQLAlchemy 2 declarative. SQLite, foreign keys enabled
(`PRAGMA foreign_keys=ON` at connection). All timestamps stored as ISO 8601
UTC strings via SQLAlchemy `DateTime(timezone=False)`.

```
User
  id              INTEGER PK
  email           TEXT UNIQUE NOT NULL
  password_hash   TEXT NOT NULL          (bcrypt, 10 rounds)
  full_name       TEXT NOT NULL
  created_at      DATETIME NOT NULL DEFAULT now()

Drug
  id              INTEGER PK
  rxnorm_cui      TEXT UNIQUE NULLABLE
  name            TEXT NOT NULL
  generic_name    TEXT NOT NULL
  drug_class      TEXT NOT NULL

Prescription
  id              INTEGER PK
  user_id         INTEGER FK -> User.id   NOT NULL
  drug_id         INTEGER FK -> Drug.id   NOT NULL
  dosage_mg       REAL NOT NULL
  schedule        TEXT NOT NULL           ("morning,evening" | "every 8h" | "as needed")
  started_at      DATETIME NOT NULL
  ended_at        DATETIME NULLABLE
  active          BOOLEAN NOT NULL DEFAULT 1
  notes           TEXT NULLABLE

Interaction
  id              INTEGER PK
  drug_a_id       INTEGER FK -> Drug.id   NOT NULL
  drug_b_id       INTEGER FK -> Drug.id   NOT NULL
  severity        TEXT NOT NULL           CHECK in ('contraindicated','major','moderate','minor')
  mechanism       TEXT NOT NULL
  llm_explanation TEXT NULLABLE
  llm_model       TEXT NULLABLE
  UNIQUE(drug_a_id, drug_b_id)
  CHECK(drug_a_id < drug_b_id)

Reminder
  id              INTEGER PK
  prescription_id INTEGER FK -> Prescription.id  NOT NULL
  scheduled_at    DATETIME NOT NULL
  taken_at        DATETIME NULLABLE
  skipped         BOOLEAN NOT NULL DEFAULT 0
  created_at      DATETIME NOT NULL DEFAULT now()
```

Indexes:
- `ix_prescription_user_active`        on `Prescription(user_id, active)`
- `ix_interaction_pair`                on `Interaction(drug_a_id, drug_b_id)` (covered by UNIQUE but declared explicitly for query planner clarity)
- `ix_reminder_prescription_scheduled` on `Reminder(prescription_id, scheduled_at)`

Pair normalization: every write to `Interaction` and every lookup goes
through a helper `pair_ids(a, b) -> (min, max)`. The CHECK constraint is the
last line of defense.

## 8. API

All routes are JSON. All request bodies validated via pydantic v2. All
JWT-protected routes require `Authorization: Bearer <token>`. Errors return:

```
{ "error": "human readable message", "code": "MACHINE_TAG" }
```

with status 400 / 401 / 403 / 404 / 409 / 422 / 500. Error codes used:
`VALIDATION`, `AUTH_REQUIRED`, `AUTH_BAD`, `NOT_FOUND`, `FORBIDDEN`,
`CONFLICT`, `RXNORM_UNAVAILABLE`, `AI_UNAVAILABLE`, `SERVER`.

### Auth

| Method | Path                  | JWT | Request                                  | Response                                       |
|--------|-----------------------|:---:|------------------------------------------|------------------------------------------------|
| POST   | `/api/auth/register`  |  -  | `{email, password, full_name}`           | `{token, user:{id,email,full_name}}` (201)     |
| POST   | `/api/auth/login`     |  -  | `{email, password}`                      | `{token, user:{id,email,full_name}}`           |
| GET    | `/api/auth/me`        |  Y  | -                                        | `{id, email, full_name, created_at}`           |

Password rules: minimum 8 characters, at least one letter and one digit.
Email is lowercased on write. Duplicate email -> 409 `CONFLICT`. JWT TTL
30 days, HS256, signed with `JWT_SECRET_KEY`.

### Drugs

| Method | Path                      | JWT | Request   | Response                                                                                  |
|--------|---------------------------|:---:|-----------|-------------------------------------------------------------------------------------------|
| GET    | `/api/drugs/search?q=`    |  Y  | -         | `{ source: "rxnorm"|"local", results: [{id?, rxnorm_cui, name, generic_name, drug_class}] }` |
| GET    | `/api/drugs/<id>`         |  Y  | -         | `{id, rxnorm_cui, name, generic_name, drug_class}`                                        |

`q` minimum length 2. Search results from RxNorm that are not yet in the
local `Drug` table are returned with `id: null`; calling
`POST /api/me/prescriptions` with such a result triggers an upsert by
`rxnorm_cui`.

### Prescriptions

| Method | Path                              | JWT | Request                                                              | Response                                                                                                |
|--------|-----------------------------------|:---:|----------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| GET    | `/api/me/prescriptions?active=`   |  Y  | -                                                                    | `[{id, drug:{id,name,generic_name,drug_class}, dosage_mg, schedule, started_at, ended_at, active, notes}]` |
| POST   | `/api/me/prescriptions`           |  Y  | `{drug_id? | rxnorm_cui?, dosage_mg, schedule, started_at, notes?}`  | created prescription record                                                                             |
| PATCH  | `/api/me/prescriptions/<id>`      |  Y  | any subset of `{dosage_mg, schedule, notes, active}`                 | updated record                                                                                          |
| DELETE | `/api/me/prescriptions/<id>`      |  Y  | -                                                                    | `{ok: true}` (soft delete: `active=false`, `ended_at=now`)                                              |

Constraint: a `POST` must include either `drug_id` (existing local drug) or
`rxnorm_cui` (will resolve / upsert via the drug list and RxNorm fallback).
On any change to the active prescription set for a user, the server
recomputes the user's interaction view on-demand at GET time; there is no
materialized per-user interaction table.

### Interactions

| Method | Path                                         | JWT | Request | Response                                                                                                                                |
|--------|----------------------------------------------|:---:|---------|-----------------------------------------------------------------------------------------------------------------------------------------|
| GET    | `/api/me/interactions`                       |  Y  | -       | `{counts:{contraindicated, major, moderate, minor}, groups:{contraindicated:[...], major:[...], moderate:[...], minor:[...]}}` items: `{interaction_id, drug_a:{id,name}, drug_b:{id,name}, severity, mechanism, has_explanation: bool}` |
| POST   | `/api/me/interactions/<id>/explain?refresh=` |  Y  | -       | `{interaction_id, explanation: "...two paragraphs...", model: "openrouter:..." | "anthropic:..." | "template", cached: bool}`           |

Group order in the response is always contraindicated, major, moderate,
minor. Within a group, items are sorted by drug A name then drug B name.
The interaction set is computed by joining the user's active prescriptions
to `Interaction` pairwise: an interaction row counts only if both drugs are
in the user's active list.

### Reminders

| Method | Path                                   | JWT | Request | Response                                                                                                       |
|--------|----------------------------------------|:---:|---------|----------------------------------------------------------------------------------------------------------------|
| GET    | `/api/me/reminders?date=YYYY-MM-DD`    |  Y  | -       | `{date, blocks:{morning:[...], midday:[...], evening:[...], night:[...]}, totals:{taken, skipped, pending}}`   |
| POST   | `/api/me/reminders/<id>/taken`         |  Y  | -       | updated reminder                                                                                               |
| POST   | `/api/me/reminders/<id>/skip`          |  Y  | -       | updated reminder                                                                                               |

Reminders for a date are generated on first GET for that date by expanding
each active prescription's `schedule`. The generation is idempotent: a
second GET for the same date returns the same row ids. Time-block mapping:
morning 05:00-10:59, midday 11:00-14:59, evening 15:00-20:59, night
21:00-04:59. Free-text schedules map: `"morning"` -> 08:00, `"midday"` ->
12:00, `"evening"` -> 18:00, `"night"` -> 22:00. `"every Nh"` produces
floor(24/N) doses starting at 08:00. `"as needed"` produces zero reminders.

### Adherence

| Method | Path                          | JWT | Request | Response                                                          |
|--------|-------------------------------|:---:|---------|-------------------------------------------------------------------|
| GET    | `/api/me/adherence?days=30`   |  Y  | -       | `{window_days, taken, skipped, missed, take_rate, streak_days}`   |

`missed` = scheduled - taken - skipped where `scheduled_at < now`.
`take_rate` = round(taken / max(1, taken+skipped+missed) * 100). `streak_days`
= consecutive days ending yesterday on which every scheduled dose was either
taken or marked skipped (skipped counts as adherent for the streak).

### Health

| Method | Path           | JWT | Response                                                                                                |
|--------|----------------|:---:|---------------------------------------------------------------------------------------------------------|
| GET    | `/api/health`  |  -  | `{ok: true, ai: "openrouter"|"anthropic"|"template", rxnorm: "live"|"local", drug_count, interaction_count}` |

## 9. Frontend

Single `static/index.html` with `<div id="app"></div>`. `static/app.js`
defines components as `defineComponent({ template: "...", setup() {} })`,
imported into a root `App` component. No build step. Tailwind play CDN
provides utility classes; `styles.css` contains the ~30 lines of overrides
that Tailwind cannot do cleanly (focus rings, severity chip combinations,
table tabular-nums).

### Routing

Hash routing: `#/today`, `#/medications`, `#/interactions`, `#/profile`,
`#/auth`. Default is `#/today` when authenticated, `#/auth` otherwise.
Route changes are watched by a single `window.addEventListener('hashchange', ...)`.

### Store

A module-scoped `reactive({})` holding `token`, `user`, `medications`,
`interactions`, `todayReminders`, `adherence`, `drugSearchResults`,
`toasts`, `loading.{key}`, `errors.{key}`. Persisted slice: `token` only,
in `localStorage` under `medsafety.token`.

### Auth view

Centered card, 420px max width. Tabs: Login / Register. Login fields:
email, password. Register fields: full_name, email, password,
password_confirm. Submit button shows spinner while pending. Errors
inline below the relevant field for 422, top-of-card banner for 401/409.
On success, token stored, route set to `#/today`. Disclaimer footer is
visible even before login.

Copy:
- Tagline above the card: "Personal medication safety check."
- Login button: "Sign in"
- Register button: "Create account"
- Login error: "Email or password is incorrect."
- Register conflict: "An account with that email already exists."

### Top nav (authenticated)

Left: brand `MedSafety` in Plus Jakarta Sans 600, with the shield-check
icon. Center: tabs Today, Medications, Interactions, Profile. Right:
user's first name plus logout icon (arrow-right-on-rectangle). The active
tab has `text-primary` and a 2px underline.

### Today view

Top card: Adherence summary.
- Big number: streak days, in Space Mono 700, 32px.
- Sub-row: take rate 28 days, taken count, skipped count, missed count.
- Caption: "Streak counts days where every dose was taken or explicitly skipped."

Below: four block sections (Morning, Midday, Evening, Night). Each block
header has its time range. Each row in a block: drug name, dosage
(Space Mono), scheduled time, two buttons "Take" and "Skip" (or, when
already actioned, "checked Taken at HH:MM" with a check glyph, or
"crossed Skipped" with a cross glyph). The check and cross ASCII
characters are the only allowed status glyphs.

Empty state: "No doses scheduled for today. Add a medication to get
started." with a button that takes the user to Medications and opens the
add drawer.

### Medications view

Header row with "+ Add medication" button on the right.

List of cards, one per active prescription:
- Drug name (Plus Jakarta Sans 600)
- Class chip (e.g. "NSAID") in `surface` background
- Dosage (Space Mono): `{dosage_mg} mg`
- Schedule (plain text)
- Started date (formatted "Mar 12, 2026")
- Buttons: Edit (small text "Edit" link), Stop (trash icon, secondary color)

Stop action: confirmation modal "Stop taking {name}?", confirms with
`DELETE /api/me/prescriptions/<id>`.

Add medication drawer (slides in from the right, 480px wide):
1. Drug search input (magnifying-glass icon), typeahead with 250 ms
   debounce, hits `/api/drugs/search?q=`. Results dropdown shows name,
   generic, class. "Offline drug list" caption shown when `source ===
   "local"`.
2. Selected drug pill with x-mark to clear.
3. Dosage input, mg suffix, numeric, Space Mono.
4. Schedule input, free text with helper text showing valid forms.
5. Started date input, defaults today.
6. Notes textarea, optional.
7. Save button (primary). Cancel link.

On save, drawer closes, list reloads, and a toast appears top-right:
"Added {name}. Interaction matrix updated." If the new prescription
triggers a contraindicated or major interaction, the toast severity is
`sev-major-bg`, persists 8 s instead of 4, and includes a button "Review"
that switches to the Interactions tab.

### Interactions view

Disclaimer block at top (see section 3).

Severity tiles row: four cards, one per bucket, large count number in
Space Mono, severity color background. Tiles are clickable and scroll to
the matching section below.

Sectioned list, contraindicated -> major -> moderate -> minor. Each
section has a header with count. Each row: drug A name + "x" + drug B
name, mechanism summary, severity chip, "Explain" button on the right.

Clicking Explain:
- If `has_explanation` is true: expands the row in place, fetches the
  cached two paragraphs from `POST /api/me/interactions/<id>/explain`,
  renders them, shows the `Generated by {model}` caption with a "Refresh"
  link that re-calls with `?refresh=true`.
- If false: same call, but shows the loading skeleton (3 lines of
  shimmer) for the duration.
- On `AI_UNAVAILABLE`: still renders the template fallback (the server
  guarantees that), with caption "Generated locally (no LLM key set)."

Empty state when the user has fewer than 2 active prescriptions: "Add at
least two medications to see interaction checks."

Empty state when 2+ prescriptions but zero interactions found: a
shield-check icon and "No interactions found across your current list.
This means none of the pairs are in the curated dataset - it does not
guarantee safety."

Loading skeleton: 4 placeholder rows with shimmering bars at the heights
of (chip, drug pair, mechanism line).

### Profile view

- Name (read-only label) and Email (read-only label).
- Change password form: current password, new password, confirm.
- Danger zone block at the bottom, `border` outlined, "Delete account"
  button grey, disabled, with caption "Coming soon".

### Toasts and errors

Top-right stack. One reactive list, max 3 visible. Network error from any
fetch -> red toast "Network error. Please check your connection.". 401
from any protected route -> token cleared, route forced to `#/auth`,
toast "Your session expired. Please sign in again." Severity colors
match palette.

### Footer

Sticky at bottom of main content area, not the viewport. Disclaimer copy
in `text-muted`, 12px.

## 10. Seed data

`app/seed.py` runs on container start if the `User` table is empty. Steps:

1. Insert all 50 drugs from section 5 with their RxNorm CUIs.
2. Insert every pair in `interactions_db.py` (target ~200), normalized
   to `drug_a_id < drug_b_id`, with severity and mechanism. No
   `llm_explanation` at seed time.
3. Insert one demo user:
   - email: `$DEMO_EMAIL` if set, else `demo@medsafety.local`.
   - password: `$DEMO_PASSWORD` if set, else a generated 12-character
     password (letters+digits, no ambiguous chars). The chosen password
     is printed to stdout exactly once on first boot, framed as:
     ```
     ============================================================
     MedSafety demo user created
       email:    demo@medsafety.local
       password: <generated>
     This message will not be shown again.
     ============================================================
     ```
   - full_name: "Demo Patient"
4. Insert 6 active prescriptions for the demo user that are *guaranteed*
   to trigger at least 2 known interactions from the anchor list:
   - warfarin 5 mg, schedule "evening", started 90 days ago
   - ibuprofen 400 mg, schedule "every 8h", started 14 days ago
     -> triggers pair #1 (warfarin + ibuprofen, major)
   - lisinopril 10 mg, schedule "morning", started 365 days ago
     -> with ibuprofen triggers pair #12 (ibuprofen + lisinopril, moderate)
   - atorvastatin 20 mg, schedule "evening", started 200 days ago
   - clarithromycin 500 mg, schedule "every 12h", started 5 days ago
     -> with atorvastatin triggers pair #22 (atorvastatin + clarithromycin, major)
   - omeprazole 20 mg, schedule "morning", started 60 days ago
5. Generate the last 7 days of reminders for the demo user. Adherence
   pattern: 92% taken, 5% skipped, 3% missed. Specifically, exactly two
   missed doses spread across day -5 and day -2, and four explicit
   skips spread across day -6, -4, -3, -1. The remainder are taken at a
   time within +/- 8 minutes of the scheduled slot. Streak for the demo
   user calculated from this data should be 7 (every day has every dose
   either taken or skipped).

Seed is idempotent: re-running with the table non-empty is a no-op apart
from a log line.

## 11. File layout

```
medsafety/
  app/
    __init__.py            Flask factory, JWT setup, blueprint registration, error handlers
    auth.py                /api/auth/{register,login,me}
    drugs.py               /api/drugs/{search,<id>}
    prescriptions.py       /api/me/prescriptions/*
    interactions.py        /api/me/interactions and /api/me/interactions/<id>/explain
    reminders.py           /api/me/reminders/*
    adherence.py           /api/me/adherence
    health.py              /api/health
    models.py              SQLAlchemy 2 declarative ORM (User, Drug, Prescription, Interaction, Reminder)
    schemas.py             pydantic v2 request/response models
    rxnorm.py              RxNorm client (urllib) + local-fallback search
    interactions_db.py     curated ~200-pair list of (generic_a, generic_b, severity, mechanism)
    ai.py                  OpenRouter -> Anthropic -> template, urllib only, system + user prompt constants
    seed.py                first-boot seeding (drugs, interactions, demo user, demo reminders)
    security.py            bcrypt hashing, password rules, JWT helpers
  wsgi.py                  gunicorn entry: `from app import create_app; app = create_app()`
  requirements.txt         pinned: Flask, SQLAlchemy, Flask-JWT-Extended, bcrypt, pydantic, gunicorn
  static/
    index.html             Vue 3 ESM + Tailwind play CDN, mounts #app
    app.js                 Vue components inline, store, hash router
    styles.css             ~30 lines of overrides
  data/                    SQLite volume, gitignored
  Dockerfile               python:3.12-alpine, non-root `meds`, tini, gunicorn
  docker-compose.yml       port 8004, env_file .env, volume ./data:/app/data
  .env.example             all env vars with safe defaults / placeholders
  .gitignore               data/, .env, __pycache__/, *.pyc, .venv/
  SPEC.md                  this document
  README.md                see section 14
```

## 12. Dev workflow

### Without Docker

```
cd medsafety
python -m venv .venv
. .venv/Scripts/Activate.ps1            # Windows PowerShell
# or: source .venv/bin/activate         # bash
pip install -r requirements.txt
$env:JWT_SECRET_KEY = "dev-only-not-secret"   # PowerShell
flask --app wsgi run --port 8004 --no-debugger
```

First run: seed fires, drug list and interactions populated, demo user
printed to stdout. Open <http://localhost:8004>.

### With docker-compose

```
cd medsafety
cp .env.example .env       # edit if you want LLM keys
docker compose up --build -d
```

Image is `python:3.12-alpine`. `tini` is PID 1. gunicorn runs as user
`meds` (uid 1000), workers `gthread`, 2 workers x 4 threads, bind
`0.0.0.0:8004`. The SQLite file lives at `/app/data/medsafety.db`,
mapped to `./data/medsafety.db` on the host. Removing `./data/` resets
all state.

Healthcheck: `wget -qO- http://localhost:8004/api/health | grep '"ok": true'`,
every 30 s, 3 retries.

## 13. Env vars

| Variable                | Default                                      | Notes |
|-------------------------|----------------------------------------------|-------|
| `JWT_SECRET_KEY`        | none - **server refuses to start without it in non-dev**. In dev (`FLASK_DEBUG=1`), a fixed string `dev-only-not-secret` is used and a loud warning is logged on every request. | HS256 signing key, 30-day TTL. |
| `OPENROUTER_API_KEY`    | empty                                        | If empty, OpenRouter step is skipped. |
| `OPENROUTER_MODEL`      | `meta-llama/llama-3.3-70b-instruct:free`     |       |
| `ANTHROPIC_API_KEY`     | empty                                        | If empty, Anthropic step is skipped. |
| `ANTHROPIC_MODEL`       | `claude-haiku-4-5`                           |       |
| `DEMO_EMAIL`            | `demo@medsafety.local`                       | Seed only. |
| `DEMO_PASSWORD`         | (generated)                                  | Seed only. Printed to stdout once. |
| `DB_PATH`               | `/app/data/medsafety.db` in container, `./data/medsafety.db` outside | Override for tests. |
| `RXNORM_BASE_URL`       | `https://rxnav.nlm.nih.gov/REST/`            | Override for offline tests. |
| `RXNORM_TIMEOUT_S`      | `4`                                          |       |
| `AI_TIMEOUT_S`          | `12`                                         |       |
| `BCRYPT_ROUNDS`         | `10`                                         |       |

`.env` is loaded by `python-dotenv` at app factory time. `.env` is in
`.gitignore`; `.env.example` is committed with placeholders.

## 14. README outline

One line per section. The README is patient-facing-leaning, terse, no
emojis except the literal check / cross characters where they appear as
UI affordances.

1. Title: `MedSafety`.
2. Disclaimer blockquote (verbatim from section 3).
3. One-paragraph problem statement (the cross-specialist polypharmacy
   gap).
4. `Run` - the two-line docker compose snippet and the URL.
5. `Sign in` - demo user note: email is `demo@medsafety.local`, password
   is printed in the container log on first boot.
6. `What's in scope` - three bullet items: my medications, interaction
   matrix, daily reminders.
7. `API` - condensed table of routes, JWT column.
8. `Configuration` - the env block from section 13.
9. `Auth notes` - bcrypt rounds, JWT TTL, HttpOnly cookie disclaimer.
10. `Layout` - file tree from section 11 abbreviated to one level.
11. `Stack` - the bullet list from section 2.
12. `Local dev (without Docker)` - venv snippet.
13. `Reset` - `docker compose down -v && rm -rf data`.
14. `Out of scope` - the list in section 15.
15. `License` - MIT.

## 15. Out of scope

The implementer must not add any of the following. They are excluded
deliberately to keep the demo tight:

- SMS, push, or email notifications. Reminders are display-only.
- Real prescriber, pharmacy, or EHR sync.
- Allergy tracking (drug-allergy interaction is a separate problem).
- Condition / diagnosis tracking, ICD codes.
- Insurance, formulary, refill, or pharmacy-pickup tracking.
- Multi-language UI. English only.
- Dark theme.
- Per-day customised schedules (e.g. "Mon/Wed/Fri only"). Only the four
  free-text schedule forms in section 8 are parsed.
- A real medication interaction database. The curated 200-pair table is
  the entire dataset. The disclaimer in section 3 makes this explicit.
- Account deletion. Button is disabled with "coming soon".
