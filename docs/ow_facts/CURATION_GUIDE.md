# Curation Guide — raw → curated SSOT

Read alongside [`SCHEMA.md`](./SCHEMA.md). This guide is the SOP for going
from a `docs/ow_facts/raw/<tier>/<Page>.json` to its curated equivalent.

## Audience

- **AJ (final auditor)**: pages I cannot resolve myself.
- **The extraction script** (`src/extract_facts.py`, to be written): a
  best-effort first pass that produces curated drafts. The script can
  do everything in §1–§3 below. §4 and §5 require human judgment.

## Language

**English only.** This was decided on 2026-05-28 in favor of accuracy
over readability:

- Outer Wilds has no official Chinese localization; community translations
  diverge ("信号镜" vs "信号探测器" vs "信号望远镜" all exist for Signalscope).
- The fandom wiki, in-game text, and r/outerwilds are all English.
- Our baseline test prompts are English.
- The pretrained Qwen3-8B has stronger Outer Wilds knowledge in English.

Chinese-language interaction is a Layer 3 application concern. The fact
store itself stays in English to maintain a single, unambiguous reference
to game entities.

## Mental model

The raw wikitext is encyclopedia-style: written for a human reading
top-to-bottom. The curated form is database-style: written for a machine
that may grab any single fact in isolation. **Every curated string must
stand alone.**

Bad (works only in context):
> "When alerted they can move faster than the player's ship."

Good:
> "When alerted, anglerfish can move faster than the player's spaceship."

This is the single most important rule. The script will sometimes fail
this — that's a flag for the human auditor.

---

## §1 — Strip wiki markup

Drop entirely:

| Markup | Reason |
|---|---|
| `{{Infobox …}}`, `{{Spoiler}}`, any `{{Template}}` | wiki rendering only |
| `<ref …>…</ref>`, `<ref name=foo/>` | citation markers |
| `<gallery>…</gallery>` | image lists |
| `[[File:…]]`, `[[Image:…]]` | images |
| `[[Category:…]]` | already captured in `categories` field |
| `{{DISPLAYTITLE:…}}` | rendering hint |
| `== References ==`, `== Notes & Trivia ==`, `== Gallery ==`, `== See also ==` whole sections | not factual content |

Convert (do not drop):

| Markup | Convert to |
|---|---|
| `[[Dark Bramble]]` | `Dark Bramble` (keep the link target as plain text) |
| `[[Dark Bramble\|the bramble]]` | `the bramble` (the alias/visible text) |
| `'''bold'''`, `''italic''` | unwrap |
| `''[[Echoes of the Eye]]''` | `Echoes of the Eye` |
| `&nbsp;`, HTML entities | space / actual char |

Sections like `== History ==`, `== Description ==`, `== Tactics ==` should
be **removed as headings** but their content is what we extract from. We
re-bucket the content per the schema, not per the wiki's sectioning.

---

## §2 — Identify the entity

Three fields to fill before extracting facts:

### `entity`
The canonical wiki page title. Copy verbatim from the raw JSON's `page`
field. (E.g. "Anglerfish", not "anglerfish" or "Anglerfishes".)

### `entity_type`
Pick from the [SCHEMA enum](./SCHEMA.md#entity_type-enum). Heuristics:

- The raw `categories` field is usually decisive. `Category:Creatures` →
  `creature`. `Category:Nomai` → `character`. `Category:Planets` → `planet`.
- DLC pages (any with `Category:Echoes of the Eye`) → `dlc_entity` unless
  they have a more specific category that fits.
- If a page belongs to multiple categories (common), pick the most
  specific. E.g. Hearthian has `Hearthians` and `Races` → it's the page
  *about* the race, so `entity_type = race`. Solanum is `Nomai` (the
  category for individual Nomai) → `character`, not `race`.

### `aliases`
List of strings that should resolve to this entity but aren't its title.
Common sources:

- **Wiki redirects.** If "Ember Twin" redirects to "Hourglass Twins", then
  `Ember Twin` is an alias of `Hourglass Twins`. (Note: in our raw dumps,
  redirects were followed automatically, so the alias info is partially
  lost — we may need to manually add common in-game names.)
- **Bold variants at the top of the page.** Many pages open with
  `'''The Stranger''' is …` and never use just `Stranger`. If the page
  title is `Stranger` but the in-game text says "The Stranger", add
  `The Stranger` as alias.
- **In-text alternatives.** The Anglerfish page says "anglerfish" (lower)
  and "Anglerfishes" (plural). Add plural form.

Be conservative — alias bloat hurts retrieval more than it helps.

---

## §3 — Extract facts per bucket

For each `== Section ==` in the raw wikitext, split into sentences and
distribute. Use the [bucket table in SCHEMA](./SCHEMA.md#facts-buckets-—-what-goes-where).

### Atomicity rule

One sentence-shaped fact per list item. If wiki text bundles two facts
together with "and", split them:

> "Anglerfish are blind and hunt using sound."

becomes two facts:

> - "Anglerfish are blind."
> - "Anglerfish hunt using sound."

### Self-containment rule

Replace pronouns and "the player" with concrete referents:

> wiki: "They will release an audible growl when they detect movement."
> curated: "Anglerfish release an audible growl when they detect movement."

If the entity is the subject, leading "The X" is fine but redundant —
just say it directly when natural.

### Strip the advice (rule from §4 of SCHEMA)

Wiki sentences often combine a fact with a player tactic. Extract the
fact only:

> wiki: "Branches within Dark Bramble can also be used to the player's
> advantage. By weaving between branches, any pursuing Anglerfish are
> likely to get stuck on the branches due to their larger size."
> curated (mechanics): "Pursuing anglerfish can get stuck on the
> branches of Dark Bramble due to their larger size."

The "weave between branches" is tactic — drop it.

### When wiki contradicts itself

Pick the most authoritative statement; mark page `confidence: medium` or
`low`; consider adding a note in the `summary` field. Don't try to
arbitrate in `facts`.

---

## §4 — Extract related entities

Walk the raw wikitext, find every `[[Other Page]]` link. For each:

1. Is the other page in your raw dump? If not, **drop it** (cross-link
   to a page we don't have facts for is dead weight).
2. What's the relation? Pick from the [relation enum](./SCHEMA.md#related_entities-—-relation-enum).
3. If the relation isn't obvious, default to `related_to` and flag for
   human audit.

The script can do (1) automatically; (2) is a heuristic mess —
the script should output `related_to` for everything and let the human
re-label.

**Dedupe.** Each related entity appears once. Pick the most specific
relation (e.g. `lives_in` beats `related_to`).

---

## §5 — Final pass (human-only)

The script gets you 80% there. The remaining 20% require AJ's judgment:

1. **Read the summary** out loud. Does it convey what this entity *is*
   in one sentence? If not, rewrite.
2. **Scan each bucket.** Are any facts:
   - Walkthrough disguised as fact? (Move out or delete.)
   - Subjective? (Delete or qualify with "wiki claims …".)
   - Duplicating another bucket's fact? (Pick one.)
3. **Sanity-check relations.** Did the script tag `mentioned_by` when the
   actual relation is `apprentice_of`?
4. **Confidence call.** If anything felt sketchy during audit, set
   `confidence: medium` or `low`.
5. **Flip the audit bit.** Set `audited_by_human: true` and `audit_date`
   to today.

---

## §6 — FAQ: boundary calls from real audits

These rules emerged during real curation work. They override §1–§5 where
they conflict, and they should be revisited as new edge cases appear.

### Wiki "Notes" / "Trivia" sections — community-derived measurements

> Example: "The earliest the Ash Twin Project can be reached through its
> Warp Tower is 7:50 minutes after spawning."

**Verdict: NOT a fact.** These are community-derived timing measurements,
playthrough optimizations, or speedrun notes. They are not part of the
game's design and can shift with patches. Drop them.

### Bug, glitch, and softlock notes

> Example: "Meditating after removing the Advanced Warp Core soft-locks
> the Game on Xbox One." or "If the Little Scout is used in the Ash Twin
> Project, the the exit teleporter may not work."

**Verdict: NOT a fact.** Engine bugs, platform-specific issues, and
unintended interactions are not facts about the game world. The wiki
records them as helpful warnings; we drop them. (If a "bug" is so
load-bearing that the community has formalized it into a technique, treat
it as a separate question — usually still drop, possibly with
`confidence: low`.)

### Ending and core-plot mechanics

> Example: "During the Self ending, the player character themselves
> becomes the inhabitant of the Ash Twin Project."

**Verdict: IS a fact.** The SSOT does not perform spoiler judgment.
If the wiki describes a mechanic, location, or sequence — even a
spoiler-heavy one — it is part of the game's truth and belongs in
curated facts. Reveal control happens in the policy layer (Layer 2),
not here.

### Infobox fields that hint at lore

> Example: "Ash Twin Project infobox: `inhabitants = None (Self during
> the Self ending)`"

**Verdict: IS a fact** — extract the underlying claim into the
appropriate bucket (here, `location`: "During the Self ending, the
player character themselves becomes the inhabitant of the Ash Twin
Project"). Infobox values are no less authoritative than prose.

### "How to do X" walkthrough text

> Example: "To avoid being pulled out, it is recommended for the player
> to seek shelter under the bridge outside or under the small intact
> sections of the tower's ceiling…"

**Verdict: NOT a fact.** Strip walkthrough advice. Extract the
underlying mechanic instead: "the warp tower for the Ash Twin Project
only becomes traversable when Ember Twin is directly above and the
tower is uncovered by sand." The advice ("shelter under the bridge")
is gameplay technique, not game mechanic.

### Real-world physics analogies the wiki throws in

> Example: "In real-world physics, black holes most commonly form
> through the gravitational collapse of a massive star."

**Verdict: IS a fact** (with `lore` bucket). It's clearly framed as
external context and harmless. Marginal value but no cost. Keep if the
wiki includes it.

### Quotes / dialogue presented inline

> Example: `YARROW: Today we finished the excavation of Ash Twin…`

**Verdict: Extract the underlying claim, drop the quote.** The fact is
"Yarrow led the excavation of Ash Twin." Never preserve the dialogue
verbatim — it's noisy and doesn't survive sentence-level retrieval.

### "Mentioned by" vs "built by"

When an entity is constructed by a group AND specific individuals from
that group are named:

- `built_by` → the **group** (e.g. `Nomai`)
- `mentioned_by` → the **individual NPCs** whose dialogue appears on the page

This keeps the relation graph clean while still recording NPC-page links.

---

## What to do when stuck

Common confusing cases:

**"This sentence is half-fact half-tactic."**
→ Extract only the fact half. Discard the tactic.

**"This 'fact' is actually two distinct claims."**
→ Split into two list items.

**"The wiki is wrong about something I remember from the game."**
→ Override with what you know to be true. Set `confidence: low` and
note in summary. (You're the auditor; wiki isn't sacred.)

**"This page is mostly dialogue quotes."**
→ Extract the underlying facts the dialogue reveals. Don't preserve
quotes. (Example: Annona page is heavy with `<ref>…dialogue…</ref>` —
we want the fact "Annona designed the warp core", not the actual lines.)

**"I genuinely don't know which bucket this belongs in."**
→ Pick one (the most natural-feeling), move on. Bucket choice is not
fatal; cross-bucket search will still find facts.

**"This is a stub page with one sentence."**
→ Single fact in the most fitting bucket. `confidence` stays high if
the wiki sentence is clear. Don't try to bulk it up by inventing.
