#!/usr/bin/env python3
"""Riscrive le righe di mapping di docs/s3dgraphy_json_config.rst dai datamodel.

Quella pagina elencava a mano, per ogni tipo di nodo e di arco, la classe o il
predicato CIDOC e il vecchio prefisso CIDOC-S3D. Un elenco scritto a mano accanto
a un datamodel che si muove diverge, e aveva divergiato: al 24 settembre 2026
venticinque voci su cinquanta dicevano qualcosa che il datamodel non diceva piu',
e cinque nominavano tipi che non esistono.

Questo script non inventa nulla: legge i due datamodel e riscrive SOLO le righe
`- CIDOC-CRM:`, `- CIDOC-S3D:`, `- CRMem:` e `- Extension:` di ciascun blocco.
Tutto il resto della pagina — prosa, attributi, sorgenti, bersagli — resta dov'e'.
Le voci che non esistono piu' nei datamodel vengono segnalate e non toccate.
Un blocco preceduto da una riga `.. sync: manual` viene lasciato stare: serve per
le poche voci in cui la prosa scritta a mano dice piu' della riga generata.

    python3 docs/_tools/sync_json_config_mappings.py [--check]
"""
import json, re, sys, io, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = ROOT / "src" / "s3dgraphy" / "JSON_config"
PAGE = ROOT / "docs" / "s3dgraphy_json_config.rst"

def load():
    conn = json.loads((CFG / "s3Dgraphy_connections_datamodel.json").read_text(encoding="utf-8"))
    node = json.loads((CFG / "s3Dgraphy_node_datamodel.json").read_text(encoding="utf-8"))
    nodemap = {}
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict) and isinstance(v.get("mapping"), dict):
                    nodemap[k] = v["mapping"]
                    if v.get("class"):
                        nodemap[v["class"]] = v["mapping"]
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(node)
    return conn["edge_types"], nodemap

def keys_for(name):
    out = [name.split("(")[0].strip()]
    m = re.search(r"\(([^)]+)\)", name)
    if m:
        out.append(m.group(1).strip())
    out += [x.strip() for x in name.split("/")]
    return out

def lines_for(mapping):
    cidoc = (mapping.get("cidoc") or "").strip()
    ext = (mapping.get("extension_mapping") or "").strip()
    out = []
    if cidoc:
        out.append("   - CIDOC-CRM: ``%s``" % cidoc)
    else:
        out.append("   - CIDOC-CRM: *none holds — declared absent, see* :doc:`crmem`")
    if ext.startswith("em:"):
        out.append("   - CRMem: ``%s``" % ext)
    elif ext:
        out.append("   - Extension: ``%s``" % ext)
    return out

def main(check=False):
    edges, nodes = load()
    text = PAGE.read_text(encoding="utf-8")
    lines = text.split("\n")
    out, i, changed, missing = [], 0, 0, []
    cur = None
    manual = False
    while i < len(lines):
        ln = lines[i]
        if ln.strip() == ".. sync: manual":
            manual = True
        m = re.match(r"\*\*([^*]+)\*\*\s*$", ln)
        if m:
            cur = m.group(1)
        if re.match(r"\s*- CIDOC-(CRM|S3D):", ln) or re.match(r"\s*- CRMem:", ln) or re.match(r"\s*- Extension:", ln):
            block = []
            while i < len(lines) and (re.match(r"\s*- CIDOC-(CRM|S3D):", lines[i])
                                      or re.match(r"\s*- CRMem:", lines[i])
                                      or re.match(r"\s*- Extension:", lines[i])):
                block.append(lines[i]); i += 1
            mp = None
            for k in keys_for(cur or ""):
                if k in edges: mp = edges[k]["mapping"]; break
                if k in nodes: mp = nodes[k]; break
            if mp is None or manual:
                if mp is None:
                    missing.append(cur)
                out.extend(block)
            else:
                new = lines_for(mp)
                if new != block: changed += 1
                out.extend(new)
            continue
        out.append(ln); i += 1
    new_text = "\n".join(out)
    if check:
        print("blocchi che cambierebbero:", changed)
    elif new_text != text:
        PAGE.write_text(new_text, encoding="utf-8")
        print("riscritti %d blocchi in %s" % (changed, PAGE.name))
    else:
        print("nessuna differenza")
    if missing:
        print("\n⚠ voci non piu' presenti nei datamodel (NON toccate, da sistemare a mano):")
        for x in dict.fromkeys(missing):
            print("   -", x)
    return 1 if missing else 0

if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
