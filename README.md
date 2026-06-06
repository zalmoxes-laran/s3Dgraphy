# s3dgraphy

[![PyPI version](https://badge.fury.io/py/s3dgraphy.svg)](https://badge.fury.io/py/s3dgraphy)
[![Python versions](https://img.shields.io/pypi/pyversions/s3dgraphy.svg)](https://pypi.org/project/s3dgraphy/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Downloads](https://pepy.tech/badge/s3dgraphy)](https://pepy.tech/project/s3dgraphy)
[![Publish to PyPI](https://github.com/zalmoxes-laran/s3dgraphy/actions/workflows/publish.yml/badge.svg)](https://github.com/zalmoxes-laran/s3dgraphy/actions/workflows/publish.yml)

## 3D Stratigraphic Graph Management Library

s3dgraphy is a Python library for creating and managing multitemporal, 3D knowledge graphs, with a focus on archaeological and heritage applications. It provides tools for stratigraphic data management, temporal modeling, and graph-based analysis of archaeological contexts.

Part of the [Extended Matrix Framework](https://www.extendedmatrix.org), s3dgraphy implements the formal language Extended Matrix (EM) for archaeological documentation and 3D reconstruction workflows.

## 🚀 Installation

```bash
# From PyPI (stable releases)
pip install s3dgraphy

# From TestPyPI (development versions)
pip install --index-url https://test.pypi.org/simple/ s3dgraphy

# With optional dependencies
pip install s3dgraphy[visualization]  # For plotting features
pip install s3dgraphy[full]          # All optional dependencies
```

## 🔧 Quick Start

```python
from s3dgraphy import Graph
from s3dgraphy.nodes import StratigraphicUnit, DocumentNode

# Create a new stratigraphic graph (graph_id is required)
graph = Graph("my_excavation")

# Build node objects, then add them with add_node()
wall = StratigraphicUnit("US001", name="US001", description="Stone wall foundation")
floor = StratigraphicUnit("US002", name="US002", description="Mosaic floor")
graph.add_node(wall)
graph.add_node(floor)

# Add a stratigraphic relationship.
# Canonical direction is recent -> ancient: the floor (US002) is more
# recent than the wall (US001), so US002 is_after US001.
graph.add_edge("e1", "US002", "US001", "is_after")

# Attach documentation
doc = DocumentNode("DOC001", name="DOC001", description="Field photo")
graph.add_node(doc)
graph.add_edge("e2", "US001", "DOC001", "has_documentation")

# Query the graph
print(f"Graph contains {len(graph.nodes)} nodes and {len(graph.edges)} edges")
us_units = graph.get_nodes_by_type("US")

# Export to GraphML (yEd round-trip) — the exporter takes the graph directly
from s3dgraphy.exporter.graphml import GraphMLExporter
GraphMLExporter(graph).export("my_excavation.graphml")
```

> **Note on the API.** Nodes are *objects* (`StratigraphicUnit`,
> `DocumentNode`, …) created first and then added with `graph.add_node()`.
> Edges are created with `graph.add_edge(edge_id, source_id, target_id,
> edge_type)` using a **canonical** edge type from the connections
> datamodel (e.g. `is_after`, `has_property`, `has_documentation`). Invalid
> connections are downgraded to `generic_connection` with a warning rather
> than silently accepted. See the
> [API reference](https://docs.extendedmatrix.org/projects/s3dgraphy/) for
> the full node and edge catalogs.

## 📚 Core Features

### 🏛️ Archaeological Stratigraphic Modeling
- **Stratigraphic Units (US)**: Physical layers and contexts
- **Stratigraphic Volumes (USV)**: 3D spatial representations
- **Surfaces (SF)**: Interface documentation
- **Temporal Relationships**: Before/after, contemporary, uncertain

### 🔗 Extended Matrix Integration
- **EM Language Support**: Full implementation of Extended Matrix formal language
- **Visual Rules**: JSON-based styling and visualization rules
- **CIDOC-CRM Mapping**: Semantic web compatibility
- **Connection Rules**: Automated relationship inference

### 📊 Graph Operations
- **Multitemporal Analysis**: Handle complex temporal sequences
- **Graph Traversal**: Navigate stratigraphic relationships
- **Filtering & Querying**: Find specific contexts and relationships
- **Validation**: Check stratigraphic consistency

### 💾 Data Exchange
- **GraphML Import/Export**: Industry standard graph format
- **JSON/YAML Support**: Lightweight data exchange
- **Excel Integration**: Tabular data import
- **3D Model Integration**: GLTF/GLB support for 3D contexts

## 🎯 Use Cases

### Archaeological Projects
- **Excavation Documentation**: Record stratigraphic sequences
- **Site Analysis**: Understand temporal relationships
- **3D Reconstruction**: Link physical evidence to 3D models
- **Publication**: Generate stratigraphic matrices and diagrams

### Heritage Applications
- **Monument Analysis**: Document construction phases
- **Conservation Planning**: Track intervention history
- **Virtual Archaeology**: Create interactive 3D experiences
- **Research Integration**: Connect archaeological data with other disciplines

## Mapping JSON files

The `src/s3dgraphy/mappings/` folder contains JSON templates that describe how
to import data from external tabular sources (SQLite tables from PyArchInit,
XLSX files from EMdb, generic CSVs, etc.) into an s3dgraphy graph.

Two template files live at the root of the folder for reference:

- `template_pyarchinit_mapping.json` — for SQLite-based tables (PyArchInit-style)
- `template_emdb_mapping.json` — for XLSX-based tables (EMdb-style)

These templates are NOT loaded automatically by `MappingRegistry`, which only
scans the `pyarchinit/`, `emdb/`, and `generic/` subdirectories. To use one as
a starting point, copy it to the appropriate subdirectory and adapt it to your
table structure.

The templates document the schema inline. In addition to `is_id`,
`is_description`, `is_attribute`, and `node_type`, 1.6 introduces two new
optional flags on each `column_mappings` entry:

- `is_filter` — marks the column as a candidate filter. Importers expose these
  via `get_filter_columns()` so a consumer application can present a dropdown
  before triggering the import.
- `filter_required` — when `true`, the consumer is expected to force the user
  to pick a value (no "All values" option). When `false`, the filter is
  optional.

Each importer (`PyArchInitImporter`, `MappedXLSXImporter`, `XLSXImporter`) now
accepts a `filters={col: value, ...}` kwarg with AND semantics, and exposes a
`get_distinct_values(col)` helper for populating the dropdown. The semantics
are deliberately library-side and make no assumption about who renders the
filter UI.

**Full schema reference:**
[Mapping JSON Schema Reference](https://docs.extendedmatrix.org/projects/s3dgraphy/en/latest/importers/mapping_schema.html)
documents every key (`table_settings`, `column_mappings`, `relations`) and the
1.6 filter flags in detail.

### Consumer-side quick start

```python
from s3dgraphy.importer.pyarchinit_importer import PyArchInitImporter

# 1) Probe the mapping: discover filter columns and their values.
probe = PyArchInitImporter(
    filepath="excavation.sqlite",
    mapping_name="pyarchinit_us_mapping",
)
for spec in probe.get_filter_columns():
    column = spec["column"]
    label = spec["display_name"]
    required = spec["filter_required"]
    values = probe.get_distinct_values(column)
    print(f"{label} ({'required' if required else 'optional'}): {values}")

# 2) Import only the subset the user picked.
importer = PyArchInitImporter(
    filepath="excavation.sqlite",
    mapping_name="pyarchinit_us_mapping",
    filters={"sito": "Pompei", "area": "A"},
)
graph = importer.parse()
```

`filters` defaults to `None` (no filtering), so all existing code continues
to work unchanged. Multiple entries are combined with logical AND; values
match exactly and case-sensitively. The same flow applies to
`MappedXLSXImporter` and `XLSXImporter` for XLSX sources.

## 📖 Documentation

- **[User Guide](https://docs.extendedmatrix.org/projects/s3dgraphy/)** - Complete documentation
- **[API Reference](https://docs.extendedmatrix.org/projects/s3dgraphy/api.html)** - Detailed API docs
- **[Examples](https://github.com/zalmoxes-laran/s3dgraphy/tree/main/examples)** - Code examples and tutorials
- **[Extended Matrix](https://www.extendedmatrix.org)** - Framework overview

## 🔧 Development

### Setting up Development Environment

```bash
# Clone the repository
git clone https://github.com/zalmoxes-laran/s3dgraphy.git
cd s3dgraphy

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Run linting
black src/
flake8 src/
```

### Release Process

```bash
# Bump version and create tag
bump2version patch  # or minor, major

# Push to GitHub
git push --follow-tags

# Create release on GitHub to auto-publish to PyPI
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution
- **New Node Types**: Archaeological contexts, dating methods
- **Import/Export Formats**: Additional data exchange formats  
- **Visualization**: Enhanced 3D layouts and rendering
- **Analysis Tools**: Statistical analysis, pattern recognition
- **Documentation**: Examples, tutorials, case studies

## 🏛️ Extended Matrix Ecosystem

s3dgraphy is part of a larger ecosystem:

- **[EM-tools for Blender](https://github.com/zalmoxes-laran/EM-blender-tools)** - 3D visualization and modeling
- **[3D Survey Collection (3DSC)](https://docs.extendedmatrix.org/projects/3DSC/)** - 3D model preparation
- **[ATON Framework](https://www.aton3d.org)** - Web-based 3D presentation
- **[Extended Matrix Documentation](https://github.com/zalmoxes-laran/ExtendedMatrix)** - Formal language specification

## 🏛 Production users & integrations

**[PyArchInit](https://github.com/pyarchinit/pyarchinit)** — first production
consumer of s3Dgraphy. PyArchInit is an open-source QGIS plugin for
archaeological data management with particular strength in **2D GIS
visualization of stratigraphic data**, maintained by an active community led
by [Luca Mandolesi](https://github.com/pyarchinit). It is used in production
by archaeology teams across Europe, and brings existing PyArchInit projects
into the Extended Matrix workflow as an auxiliary data source through
s3Dgraphy — referencing records live or baking them into the graph.

The PyArchInit integration drove the design of the LocationNodeGroup in
s3Dgraphy 0.1.41 (insight from
[issue #5](https://github.com/zalmoxes-laran/s3Dgraphy/issues/5) by
[Enzo Cocca](https://github.com/enzococca)).

To request inclusion in this list, see the [Ecosystem page](https://docs.extendedmatrix.org/en/latest/ecosystem.html) of the Extended Matrix manual.

### Open invitation

s3Dgraphy is designed to be consumed by independent tools. **Revit**,
**Unreal Engine**, **Houdini**, **PostgreSQL/PostGIS**, and other
domain-specific tools are natural candidates for similar bridges into the
Extended Matrix ecosystem. If you maintain such a project and want to
explore an integration, open a discussion at
[github.com/zalmoxes-laran/s3Dgraphy/discussions](https://github.com/zalmoxes-laran/s3Dgraphy/discussions)
or look at the PyArchInit integration as a worked example.

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

The GPL-3.0 license ensures that s3dgraphy remains free and open source, promoting transparency and collaboration in archaeological research and heritage preservation.

## 🏛️ Citation

If you use s3dgraphy in your research, please cite:

```bibtex
@software{s3dgraphy,
  title={s3dgraphy: 3D Stratigraphic Graph Management Library},
  author={Demetrescu, Emanuel},
  year={2026},
  url={https://github.com/zalmoxes-laran/s3dgraphy},
  version={1.6.0},
  institution={CNR-ISPC (National Research Council - Institute of Heritage Science)}
}
```

## 👥 Credits

**Author & Maintainer**: [Emanuel Demetrescu](https://github.com/zalmoxes-laran) (CNR-ISPC)

**Institution**: National Research Council of Italy - Institute of Heritage Science (CNR-ISPC)

**Funding**: This research has been supported by various archaeological and heritage preservation projects.

## 🔗 Links

- **GitHub Repository**: https://github.com/zalmoxes-laran/s3dgraphy
- **PyPI Package**: https://pypi.org/project/s3dgraphy/
- **Documentation**: https://docs.extendedmatrix.org/projects/s3dgraphy/
- **Extended Matrix Website**: https://www.extendedmatrix.org
- **Bug Reports**: https://github.com/zalmoxes-laran/s3dgraphy/issues

---

*s3dgraphy - Bringing archaeological stratigraphy into the digital age* 🏛️✨