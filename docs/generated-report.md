(generated-report)=

# Generated figures

<!-- GENERATED, do not edit by hand. Regenerated on every documentation build; see docs/conf.py. -->

Every figure on this page is read off the datamodels and the installed package at build time. **No count in this documentation is written by hand**; where another page needs one, it links here.

## Declared coherence horizon

| Component | Version |
| --- | --- |
| s3dgraphy (library) | 1.6.0.dev18 |
| nodes datamodel | 1.6.6 |
| connections datamodel | 1.6.17 |
| qualia datamodel | 1.6.1 |
| CIDOC-CRM | 7.1.3 |
| CRMarchaeo | 2.1.1 |
| CRMsci | 3.2 |
| CRMdig | 5.0 |
| CRMgeo | 1.2 |
| CRMinf | 1.2.1 |
| HDT-O | 1.0 |
| PROV-O | W3C Recommendation 2013-04-30 |
| CRMem | 1.6.2 |

> ⚠ The generated node registry declares node datamodel version `1.6.5` while the node datamodel itself is at `1.6.6`. The registry's `--check` mode compares class entries only, so a version drift like this one passes unnoticed. Regenerate with `python -m s3dgraphy.tools.sync_node_datamodel`.

## Node types

The three populations, named apart — see this module's docstring for why there is no single number.

| What | Count |
| --- | --- |
| declared in the node datamodel | 55 |
| — of which authorable types | 51 |
| — of which abstract family bases | 4 |
| field-level mapping blocks (not node types) | 3 |
| entries with no mapping block | 0 |

Abstract family bases: `GroupNode`, `Node`, `ParadataNode`, `StratigraphicNode`.

## Edge types

| What | Count |
| --- | --- |
| declared in the connections datamodel | 56 |
| — of which live (not deprecated) | 55 |
| — declaring a named reverse direction | 49 |

## Python classes

| What | Count |
| --- | --- |
| Python node classes in the generated registry | 58 |
| — of which abstract (no own node_type) | 2 |
| present in the registry, absent from the datamodel | 3 |

Abstract classes (no own `node_type`): `DTCNode`, `VirtualStratigraphicUnit`.

Classes present in the registry with no entry in the node datamodel, and therefore with no declared CIDOC projection: `DTCNode`, `RepresentationNode`, `VirtualStratigraphicUnit`.

## Other surfaces

| What | Count |
| --- | --- |
| public API callables | 166 |
| test modules in tests/ | 89 |
| test modules in tests/*/ | 66 |

## Alignment by ontology

Of the 55 node types declared, **13 reuse a class from an existing ontology unchanged** and **42 declare a class in the Extended Matrix namespace**. Every one of the latter keeps a CIDOC anchor, so the table below covers all of them.

Node types, by the ontology of the CIDOC class they are anchored to:

| Ontology | Node types |
| --- | --- |
| crm | 29 |
| crmarchaeo | 13 |
| crmdig | 6 |
| hdto | 4 |
| crminf | 3 |

Edge types, by the ontology of the CIDOC predicate they emit. An edge with no CIDOC predicate is a *declared absence*: the family has no term for that relation and the edge is emitted on its extension predicate alone.

| Ontology | Edge types |
| --- | --- |
| crm | 32 |
| (none declared) | 9 |
| hdto | 6 |
| crmdig | 5 |
| crmarchaeo | 2 |
| prov | 2 |

Edge types carrying a second, extension predicate beside (or instead of) the CIDOC one:

| Ontology | Edge types |
| --- | --- |
| CRMarchaeo | 10 |
| CIDOC-S3D | 9 |
| em | 9 |
| CIDOC-CRM | 8 |
| prov | 4 |
| CRMdig | 2 |
| CRMinf | 2 |

> ⚠ **Extension prefixes the RDF exporter cannot resolve.** A predicate declared under a prefix that is not in the exporter's prefix table resolves to nothing and is never emitted — no error is raised anywhere. These declarations are inert:

> * `CIDOC-S3D:` — on 9 edge types: `contrasts_with`, `has_paradata_nodegroup`, `has_representation_model`, `has_representation_model_doc`, `has_representation_model_sf`, `has_semantic_shape`, `has_timebranch`, `is_in_paradata_nodegroup`, `is_in_timebranch`

