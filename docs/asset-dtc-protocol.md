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
   `em-server` consults before serving the bytes. Enrichment that this reader
   cannot see is enrichment that changed nothing.

## Where the act is normally triggered

**At upload.** The moment bytes reach the object store is when the asset first
exists as a thing anybody can point at, and it is the natural place to say what
it is: EMStudio does exactly this (PUT the bytes → sha256 → `ResourceNode`
(`residency: "resident"`) → this protocol). It is not the only place: the same
call, later, from a catalogue or an ingest, is the same act with a later
timestamp — which is the point.

## What this is not

* **Not a provenance editor.** The full DTC chain (which instrument acquired
  what, through which process) is `docs/dtc-profile.md`.
* **Not enforcement.** What the licence *permits* is not imposed by anything
  here; em-server exposes it and transports it (`X-EM-License`, the IIIF
  `requiredStatement`) and gates only the embargo, which is a date.
* **Not identity verification.** Whether an ORCID belongs to who says it does is
  the identity layer's question (`claim now, verify later`), unchanged.
