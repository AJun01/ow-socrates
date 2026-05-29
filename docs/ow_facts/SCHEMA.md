# Curated SSOT Schema (v1)

This document defines the JSON shape of every file under
`docs/ow_facts/curated/`. It is the **single source of truth for the schema**
— if the schema changes, this doc changes first, then we re-run validation
across all curated files.

## Design principle

The curated layer captures **objective facts about the game**, organized in a
way that downstream layers (policy, prompt construction, RAG retrieval,
fine-tuning data generation) can use. It contains **no product policy** —
no "should this be revealed", no "Socratic style", no "spoiler levels".
Those concerns live in higher layers and can iterate independently.

## File layout

```
docs/ow_facts/curated/<entity_slug>.json
```

- `entity_slug` = lowercased page name, spaces → `_`, apostrophes dropped.
  e.g. `Anglerfish.json` from the raw page becomes `anglerfish.json`.
  `Gabbro's Island` becomes `gabbros_island.json`.

## Schema

```jsonc
{
  // ── Identity ──────────────────────────────────────────────────────
  "entity": "Anglerfish",            // canonical page title, exactly as on wiki
  "entity_type": "creature",         // see enum below
  "aliases": [],                     // other names that should hit this page
  "categories": ["Creatures"],       // wiki categories, cleaned (no "Category:" prefix)
  "tags": ["dark_bramble"],          // free-form thematic tags, see TAG GUIDE below
  
  // ── Substance ─────────────────────────────────────────────────────
  // All text (summary, facts, related_entities) is in ENGLISH.
  // Rationale: matches in-game text, fandom wiki, community discussions,
  // and the baseline test prompts. Chinese translation is a Layer 3
  // (application) concern, not a fact-store concern.
  //
  // SUMMARY STANDARD (RAG-critical, see §summary-standard below).
  // 1-2 sentences, standalone-readable, packing the 2-3 most important
  // facts about this entity. This is the primary RAG retrieval hit point.
  "summary": "1-2 sentences, standalone, RAG-friendly.",
  "facts": {
    "biology":  ["...", "..."],      // physical traits, anatomy, diet
    "behavior": ["...", "..."],      // how it acts, AI logic, reactions
    "location": ["...", "..."],      // where it can be found
    "lore":     ["...", "..."],      // story / trivia / cross-references
    "mechanics":["...", "..."]       // game-engine rules players can exploit
  },
  
  // ── Structure ─────────────────────────────────────────────────────
  "related_entities": [
    {"entity": "Dark Bramble", "relation": "lives_in"},
    {"entity": "Observatory",  "relation": "captive_specimen_at"}
  ],
  
  // ── Cross-references (optional) ───────────────────────────────────
  // For redirect stubs: the slug(s) of the parent entity whose page
  // actually contains the full facts. RAG retrievers should pull these
  // alongside this file.
  "see_also": ["brittle_hollow"],     // optional; empty/absent for full entries
  
  // ── Provenance ────────────────────────────────────────────────────
  "source": {
    "page": "Anglerfish",
    "url": "https://outerwilds.fandom.com/wiki/Anglerfish",
    "fetched_at": "2026-05-28T10:52:20",
    "audited_by_human": false,       // flipped to true by AJ during audit
    "audit_date": null,              // ISO datetime when audit happened
    "confidence": "high",            // see CONFIDENCE LEVELS below
    "is_redirect_stub": false        // true for stubs (see §redirect-stubs)
  }
}
```

## §summary-standard — RAG retrieval target

The `summary` field is the **primary RAG retrieval target** for this
entity. When the embedding index is built, the summary tends to become a
single high-density chunk; the `facts` lists are split into multiple
smaller chunks. If the summary doesn't hit, the rest of the document may
not be retrieved at all.

**Requirements:**

1. **1-2 sentences.** Longer summaries get truncated or split by the
   chunker; shorter summaries lose retrieval recall.
2. **Standalone readable.** A reader who knows nothing about Outer Wilds
   should understand what this entity *is* and roughly its role.
3. **Pack the 2-3 most important facts.** Not the most poetic ones —
   the most *discriminating* ones. For a location: what it is, where it
   is, why it matters. For a character: species, location, role.
4. **Name yourself.** Start the summary with the entity name when
   natural. Helps both retrieval and the model's grounding.
5. **Avoid jargon for jargon's sake.** "Quantum Shard" is fine because
   it's a unique OW term; "bio-luminescent" should be paired with what
   it *is* (a lure that mimics portals).

**Good:**

> "The Black Hole Forge is a Nomai facility suspended beneath the
> Hanging City on Brittle Hollow, hanging just above the planet's core
> black hole. It is the source of every Nomai warp core in the solar
> system."

**Bad (too short, missing role):**

> "A facility on Brittle Hollow."

**Bad (poetic, not factual):**

> "Hanging above the void, the Forge whispers of ancient discoveries…"

## §redirect-stubs — handling fandom redirects

The fandom wiki frequently has multiple "pages" (e.g. *Crossroads*,
*Hanging City*, *Tower of Quantum Knowledge*) that all redirect to a
single parent page (*Brittle Hollow*) and share the same wikitext.
We track these as **redirect stubs**: minimal curated files that exist
to give the sub-entity a vector representation and a knowledge-graph
node, without duplicating facts.

**Stub file shape:**

```jsonc
{
  "entity": "Crossroads",
  "entity_type": "location",
  "aliases": ["The Crossroads"],
  "categories": ["Locations on Brittle Hollow"],
  "tags": ["brittle_hollow"],

  "summary": "A two-level central hub under Brittle Hollow's surface, …",

  "facts": {
    "biology": [], "behavior": [],
    "location": [
      "The Crossroads is a sub-location of Brittle Hollow.",
      "Full facts about the Crossroads are recorded in brittle_hollow.json (Crossroads section in location bucket)."
    ],
    "lore": [], "mechanics": []
  },

  "see_also": ["brittle_hollow"],

  "related_entities": [
    {"entity": "Brittle Hollow", "relation": "located_in"},
    // any other immediately neighboring entities, optional
  ],

  "source": {
    "page": "Crossroads",
    "url": "https://outerwilds.fandom.com/wiki/Brittle_Hollow#Crossroads",
    "fetched_at": "...",
    "audited_by_human": true,
    "audit_date": "2026-05-28",
    "confidence": "high",
    "is_redirect_stub": true
  }
}
```

**Stub rules:**

- `facts` is nearly empty; the only content is a single pointer string
  in the most relevant bucket telling the reader/RAG to consult the
  parent. **Don't duplicate parent content.**
- `summary` carries the full information density expected of any
  summary. This is where RAG retrieval happens.
- `see_also` is mandatory and points to the parent slug(s).
- `is_redirect_stub: true` in `source` so the validator knows to apply
  stub-specific rules (no minimum fact count, etc.).
- `url` uses the wiki anchor link form
  (`https://…/wiki/Parent#Sub`) so the source link goes to the
  specific section, not just the top of the parent page.

## entity_type enum

```
creature       → Anglerfish, Jellyfish
race           → Hearthian, Nomai
character      → Feldspar, Solanum, Annona, ...
planet         → Timber Hearth, Brittle Hollow, ...
moon           → Attlerock, Hollow's Lantern, Quantum Moon
location       → The Village, Sun Station, Black Hole Forge, ...
                (sub-areas inside a planet/moon)
celestial_body → Sun, Interloper, Eye of the Universe
                (things that aren't planets but aren't locations either)
technology     → Signalscope, Scout Launcher, Warp Core, Spaceship, ...
mechanic       → Ghost Matter, Supernova, Quantum Shards, ...
                (game-system concepts that aren't items)
event          → Endings, Launch codes
phenomenon     → Black Hole, White Hole
group          → Outer Wilds Ventures, Travelers, Ash Twin Project Members
dlc_entity     → anything inside Echoes of the Eye
```

When in doubt: pick the most specific that still feels honest. A wrong
type is recoverable later via a `jq` script; the value is just helping
downstream filtering.

## facts buckets — what goes where

Each bucket is a flat list of single-fact strings. **One fact per string.**
Bucket choice is intentional but not adversarial — pick the most natural
home, don't sweat overlap.

| bucket | what belongs here | example |
|---|---|---|
| `biology` | static traits — anatomy, sensory, lifecycle | "blind, hunts by sound" |
| `behavior` | dynamic actions, AI, reactions | "growls upon detecting motion" |
| `location` | where to find it (positional facts) | "Nest Node contains 5 specimens" |
| `lore` | story, history, world-building, trivia | "fossil exists at Ember Twin" |
| `mechanics` | engine rules players can use | "rotational thrusters don't trigger detection" |

**Empty buckets are fine.** A character probably won't have a `mechanics`
bucket. A piece of technology might not have `behavior`.

**Do not include** in any bucket:
- Walkthrough-style instructions ("you should drift past them")
- Subjective evaluations from the wiki ("the most consistent tactic")
- Wiki maintenance text ("see also", "trivia about real-world etymology")

Wiki write-ups often blend fact and advice in the same paragraph. When
extracting, **strip the advice clause**:

> Wiki: "The player can freely pass as close as they wish and as fast as
> they wish, as long as they are not making any sound when doing so."

Becomes:

> mechanics: "They detect motion only via sound emitted by the player."

The advice ("freely pass as close as you wish") is policy-layer guidance,
not a fact. We're storing facts.

## related_entities — relation enum

Use one of these standard relations. Add new ones to this doc rather than
inventing them ad-hoc:

```
lives_in          A lives inside B (creature → location)
located_in        A is physically inside B (location → planet)
orbits            A orbits B (moon → planet, planet → sun)
built_by          A was constructed by B (technology/location → group/race)
created_by        A was designed/invented by B (technology → character)
mentioned_by      A is referenced in dialogue/text by B
appears_at        A's signal/fossil/remnant exists at B
member_of         A belongs to group B
apprentice_of     A was trained by B
predates          A existed before B (race → race, e.g. Stranger inhabitants predate Hearthians)
near              A and B are spatially close, no stronger relation
related_to        catch-all fallback. Try to avoid.
```

## confidence levels

```
high    — directly stated in wiki, well-attested, multiple corroborating refs.
          Default for most facts.
medium  — stated in wiki but with hedging ("likely", "appears to") or only
          one ref. Or: extracted from a single dialogue quote.
low     — wiki contradicts itself, or fact is speculative trivia, or you
          (AJ) couldn't verify in-game and wiki source is unclear.
```

The `confidence` field on `source` is the **page-level minimum** — if any
fact on the page is `low`-confidence, the whole page is `low`. Per-fact
confidence is not stored; if needed later, split into two pages or use the
fact text itself ("likely feed on …").

## tags — thematic labels (free-form, but converge)

Tags help RAG retrieval pull "everything quantum-related" or "everything
in Brittle Hollow" without joining on relations. Conventions:

- Lowercase snake_case
- One tag per concept; don't tag both `quantum` and `quantum_mechanic`
- Tag the entity, not its inverse. (Tag `anglerfish` with `dark_bramble`,
  don't tag `dark_bramble` with `dangerous_creature`.)

Current standard tags (extend as needed):

```
Planet tags:        timber_hearth, brittle_hollow, giants_deep, dark_bramble,
                    hourglass_twins, quantum_moon, the_sun, interloper,
                    eye_of_the_universe
Mechanic tags:      quantum, time_loop, ghost_matter, warp, supernova,
                    cloaking, gravity
Story tags:         nomai_history, hearthian_culture, ash_twin_project,
                    eye_signal, dlc_story
Region:             dlc (anything Echoes of the Eye)
Cross-cutting:      endgame, early_game, optional
```

## entity_slug rules

Required for filename generation, alias generation, and cross-linking.

```
"Anglerfish"             → "anglerfish"
"Dark Bramble"           → "dark_bramble"
"Gabbro's Island"        → "gabbros_island"
"The Village"            → "the_village"    (keep "The")
"Tower of Quantum Trials"→ "tower_of_quantum_trials"
"Echoes of the Eye"      → "echoes_of_the_eye"
"The Stranger's inhabitants" → "the_strangers_inhabitants"
```

Algorithm:
1. Lowercase.
2. Replace each space with `_`.
3. Drop `'` (apostrophes).
4. Drop any character that isn't `[a-z0-9_]`.

## Validation

Every curated file must be valid JSON. A future `src/validate_curated.py`
will check:

- All required fields present
- `entity_type` is in the enum
- All `relation`s are in the relation enum
- `source.url` matches `https://outerwilds.fandom.com/wiki/<page>`
- `audit_date` is present iff `audited_by_human` is true
- No fact string is longer than 280 chars (split if so)
- No fact string contains `<ref` or `{{` or `[[` (wiki markup leaked through)
- No CJK characters anywhere in `summary`, `facts.*`, `related_entities.*.entity` (English-only enforcement)
- `summary` is non-empty and between 80 and 400 characters
- If `is_redirect_stub: true`, then `see_also` is non-empty
- If `see_also` references a slug, a file with that slug must exist (referential integrity)
