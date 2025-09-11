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
import s3dgraphy

# Create a new stratigraphic graph
graph = s3dgraphy.Graph()

# Add stratigraphic units
us1 = graph.add_node("US001", node_type="US", 
                     properties={"period": "Roman", "material": "pottery"})
us2 = graph.add_node("US002", node_type="US", 
                     properties={"period": "Medieval", "material": "stone"})

# Add stratigraphic relationships
graph.add_edge(us1, us2, edge_type="ABOVE", 
               properties={"certainty": "high"})

# Query the graph
print(f"Graph contains {len(graph.nodes)} stratigraphic units")
print(f"Relationships: {len(graph.edges)}")

# Export to different formats
graph.export_graphml("stratigraphy.graphml")
graph.export_json("stratigraphy.json")
```

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

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

The GPL-3.0 license ensures that s3dgraphy remains free and open source, promoting transparency and collaboration in archaeological research and heritage preservation.

## 🏛️ Citation

If you use s3dgraphy in your research, please cite:

```bibtex
@software{s3dgraphy2024,
  title={s3dgraphy: 3D Stratigraphic Graph Management Library},
  author={Demetrescu, Emanuel},
  year={2024},
  url={https://github.com/zalmoxes-laran/s3dgraphy},
  version={0.1.1},
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