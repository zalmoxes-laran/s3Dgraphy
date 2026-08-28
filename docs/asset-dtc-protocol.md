# Enriching an asset's DTC — the protocol

**Attribution is an act, not a field.** Who made a file, under what licence, and
until when it stays closed are things somebody *declares* — at the moment the
file is made, or long afterwards, sometimes posthumously, and very often **by
somebody who is not the creator**. A cataloguer states the licence of a
photograph taken in 1978 by a colleague who has since retired: that statement is
true, it is useful, and it is not authorship.

A data model with one "author" field cannot say that without lying. This protocol
is how the Extended Matrix says it, and it is written down here — tool-agnostic —
because more than one tool performs it: EMStudio when a file is uploaded, EMtools
in Blender, the field chatbot, and an ECHOES / ECCCH ingest that never opens
either of them. **Reusable by design**: the twin of the chatbot's tool contract,
on the asset side.

Reference implementation: `s3dgraphy.api.enrich_asset_dtc`
(`s3dgraphy/rights.py`). Reading back: `s3dgraphy.api.asset_rights`.

---

## The two people

| | who | where it goes |
|---|---|---|
| **author** | who **made** the data. May be absent, retired, or dead. | an `AuthorNode` reached by `has_author`; the iD in `data.orcid` |
| **attributor** | who **says so**, now. Signs the act. | `data.attributed_by` on the statement, with `data.attributed_at` |

They are frequently different, and the model must not flatten them. Note also
what the attributor is **not**: the editorial stamps (`created_by` /
`modified_by`, `s3dgraphy.editorial`) record the hand that touched the document.
The attributor is a claim about the world; the editorial stamp is a fact about
the file. "Somebody edited this" and "somebody vouches for this" are different
sentences and must stay so.

## Input

```
enrich_asset_dtc(graph, checksum, *,
                 attributor,                 # ORCID — REQUIRED
                 author=None,                # ORCID of who made it
                 author_name=None,           # how to display that person
                 license=None,               # e.g. "CC-BY-SA-4.0"
                 embargo=None,               # ISO date it runs until
                 reason=None,                # why (embargo only)
                 at=None)                    # when the act was made (ISO)
```

* **`checksum`** names the bytes — with or without the `sha256:` prefix, because
  both forms are in the wild (the graph stores the prefixed one, the IIIF
  identifier is the bare hex). The `ResourceNode` pointing at those bytes must
  already exist: this enriches an asset, it does not invent one. A digest nothing
  points at is a `LookupError`, never a node conjured to hold a licence.
* **`attributor` is required.** An attribution nobody signs is a rumour, and the
  whole point of the act is that somebody stands behind it.
* **`at`** defaults to now. A posthumous attribution says *when it was made*
  rather than pretending to be contemporary with the file.

### Tri-state, and why it has three states

Each of `author` / `license` / `embargo`:

| value | meaning |
|---|---|
| omitted (`None`) | **not touched**. Declaring a licence must not silently clear an embargo somebody else set |
| a value | **declared** — created, or updated in place |
| `""` (empty string) | **removed** — the statement is retracted |

"Not declared" and "declared to be nothing" are different sentences; a protocol
with two states could only say one of them.

## Output — the nodes and edges expected

```
ResourceNode(data.checksum = sha256:…)
   ├── has_author  → AuthorNode   { orcid, attributed_by, attributed_at }
   ├── has_license → LicenseNode  { license_type, attributed_by, attributed_at }
   └── has_embargo → EmbargoNode  { embargo_end, reason?, attributed_by, attributed_at }
```

The three edges already exist in the datamodel and are **reused, not duplicated**
— the same commons the DTC profile reuses (`docs/dtc-profile.md`: "EM commons are
REUSED"). `has_author`'s source list gained `ResourceNode` on 2026-08-16 for this
protocol; the mapping (`prov:wasAttributedTo`) was already domain-neutral.

The call returns what it did, per field, so a tool can report rather than guess:

```json
{"resource_id": "img-1", "digest": "abc…", "attributor": "0000-…",
 "at": "2026-08-16T20:00:00Z",
 "changed": {"author": "declared", "license": "updated"}}
```

## Invariants

1. **Attributor ≠ author** is legal, and is the normal case for anything
   catalogued after the fact.
2. **Posthumous is legal.** Nothing requires the author to be reachable, alive,
   or the person at the keyboard.
3. **Idempotent** per `(checksum, field)`: the same call twice leaves one
   statement and one signature. Re-declaring updates in place; it does not add a
   second licence beside the first.
4. **A revision re-signs.** Change a value and the signature becomes yours: an
   attribution somebody edited is theirs now, not still the first person's.
5. **Tombstones are never reused.** A removed statement is not a node to write
   the next one onto — neither when reading nor when writing. (This has bitten
   twice, in two languages, in one night: a removed embargo went on refusing a
   file in the Python reader, and re-declaring a licence wrote onto the corpse of
   the one just removed in the TypeScript writer.)
6. **The rights are read back by one reader** (`asset_rights`), which is what
   `StratiGraph Server` consults before serving the bytes. Enrichment that this reader
   cannot see is enrichment that changed nothing.

## Where the act is normally triggered

**At upload.** The moment bytes reach the object store is when the asset first
exists as a thing anybody can point at, and it is the natural place to say what
it is: EMStudio does exactly this (PUT the bytes → sha256 → `ResourceNode`
(`residency: "resident"`) → this protocol). It is not the only place: the same
call, later, from a catalogue or an ingest, is the same act with a later
timestamp — which is the point.

## The plural: a LOT, not four hundred files

Nobody attributes four hundred photographs one at a time, and a protocol that
made them do it would be obeyed once. The batch form
(`s3dgraphy.api.attribute_batch`, `s3dgraphy/dtc/ingest.py`) is the same act
performed on the **acquisition event** that brought the files in:

```
DTCAcquisitionNode (crmdig:D12)      ← the lot; ONE licence, ONE author
   ├── dtc_had_output → ResourceNode  (member 1)
   ├── dtc_had_output → ResourceNode  (member 2)   …
   ├── has_license → LicenseNode { license_type, attributed_by, attributed_at }
   └── has_author  → AuthorNode  { orcid, attributed_by, attributed_at }
```

Nothing new was needed to read it: `asset_rights` already walks from a digest to
the chunk that produced it, so **each member reads the lot's licence with
`via: "dtc"`** — inheritance, not four hundred copies of one sentence. A member
that carries its own statement wins over the lot's, because the more specific
statement is the one somebody made about *this* object.

`propagate=True` also stamps every member individually. It is **off by default**
and the reason is not performance: a stamped member keeps its licence when it
leaves the campaign, but the lot then has four hundred statements to revise the
day somebody changes their mind. Inheritance is one truth; propagation is a copy,
and a copy is a thing that can disagree.

Two granularities travel together and must not be fused:

| | granularity | where it is said |
|---|---|---|
| **attribution** (who, which licence) | the **lot** | the acquisition event |
| **provenance** (how it was made) | the single **output** | a `DTCProcessNode`, declared |

`has_author`'s source list gained `DTCNode` on 2026-08-17 (connections v1.6.11)
so the event can carry the author of its lot — the same widening already applied
to `dtc_had_input` / `dtc_had_output` for the same reason.

## The chain is DECLARED

`s3dgraphy.api.declare_derivation` records that an output came out of its inputs,
with the tool **named and nothing more** (`data.tool = {"name": …}`, a dict so
version and parameters are additions rather than a migration). Nobody infers a
derivation from matching timestamps: somebody says it, and the graph records who
and when.

An input may be a single resource — which also gets the direct
`output ─dtc_derived_from→ input` shortcut — **or a whole acquisition**, which is
the reason the serial node exists: one input edge for a campaign of five hundred
photographs, not five hundred. In RDF that case projects as `prov:wasInformedBy`
(activity → activity) rather than `prov:used` / `crmdig:L10_had_input`, which
range over digital objects and would be a false statement about a class.

## What this is not

* **Not a provenance editor.** The full DTC chain (which instrument acquired
  what, through which process) is `docs/dtc-profile.md`. The declared chain above
  is the minimum: an event, its inputs, and the name of the tool.
* **Not enforcement.** What the licence *permits* is not imposed by anything
  here; StratiGraph Server exposes it and transports it (`X-EM-License`, the IIIF
  `requiredStatement`) and gates only the embargo, which is a date.
* **Not identity verification.** Whether an ORCID belongs to who says it does is
  the identity layer's question (`claim now, verify later`), unchanged.
