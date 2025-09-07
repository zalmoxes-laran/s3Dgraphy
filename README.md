# s3Dgraphy

[![PyPI version](https://badge.fury.io/py/s3dgraphy.svg)](https://badge.fury.io/py/s3dgraphy)
[![Python](https://img.shields.io/pypi/pyversions/s3dgraphy.svg)](https://pypi.org/project/s3dgraphy/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**s3Dgraphy** is a Python library for creating and managing multitemporal, 3D knowledge graphs, with a focus on archaeological and heritage applications. It provides tools for stratigraphic data management, temporal modeling, and graph-based analysis of archaeological contexts.

## 🚀 Features

- **Multitemporal Graphs**: Handle temporal relationships and chronological sequences
- **Stratigraphic Modeling**: Specialized nodes and edges for archaeological stratigraphy  
- **Flexible Data Import**: Support for GraphML, XLSX, and custom formats
- **Visual Layouts**: Generate 2D layouts for graph visualization (requires NetworkX)
- **Extended Matrix Integration**: Native support for EM (Extended Matrix) methodology
- **Blender Compatible**: Designed to work seamlessly with Blender 3D and EMtools

## 📦 Installation

### Standard Installation
```bash
pip install s3dgraphy
```

### With Optional Dependencies
```bash
# For graph visualization layouts
pip install s3dgraphy[networkx]

# For development
pip install s3dgraphy[dev]

# For documentation building  
pip install s3dgraphy[docs]
```

## 🔧 Quick Start

### Basic Graph Creation
```python
from s3dgraphy import Graph, Node, Edge

# Create a new graph
graph = Graph("archaeological_site")
graph.description = {"en": "Stratigraphic sequence from excavation"}

# Add stratigraphic nodes
layer1 = Node("US001", "Topsoil layer", "stratigraphic_unit") 
layer2 = Node("US002", "Medieval layer", "stratigraphic_unit")
layer3 = Node("US003", "Roman foundation", "stratigraphic_unit")

graph.add_node(layer1)
graph.add_node(layer2) 
graph.add_node(layer3)

# Add temporal relationships (stratigraphic sequence)
graph.add_edge("rel1", "US002", "US001", "is_before")  # US002 is before (older than) US001
graph.add_edge("rel2", "US003", "US002", "is_before")  # US003 is before (older than) US002

print(f"Graph has {len(graph.nodes)} nodes and {len(graph.edges)} edges")
```

### Loading from GraphML
```python
from s3dgraphy import load_graph_from_file

# Load existing GraphML file
graph = load_graph_from_file("site_data.graphml", overwrite=True)

# Access nodes and edges
for node in graph.nodes:
    print(f"Node: {node.name} (Type: {node.node_type})")

for edge in graph.edges:
    print(f"Edge: {edge.edge_source} → {edge.edge_target} ({edge.edge_type})")
```

### Visual Layout Generation
```python
from s3dgraphy.utils.visual_layout import generate_layout

# Generate 2D coordinates for visualization (requires NetworkX)
try:
    layout = generate_layout(graph)
    for node_id, (x, y) in layout.items():
        print(f"Node {node_id}: position ({x:.2f}, {y:.2f})")
except ImportError:
    print("NetworkX required for layout generation")
```

## 🏛️ Archaeological Applications

s3Dgraphy is particularly suited for:

- **Stratigraphic Analysis**: Model archaeological layers and their relationships
- **Temporal Sequences**: Track changes over time in archaeological contexts
- **Site Documentation**: Create structured records of excavation data
- **3D Integration**: Seamless integration with 3D modeling workflows (Blender)
- **Data Exchange**: Standards-compliant data export for research collaboration

## 🔗 Integration with EMtools

s3Dgraphy is the core library powering [EMtools](https://github.com/zalmoxes-laran/EM-blender-tools), a Blender extension for Extended Matrix methodology:

```python
# In Blender with EMtools
import bpy
from s3dgraphy import get_active_graph

# Access the currently active graph in Blender
graph = get_active_graph()
if graph:
    print(f"Working with: {graph.name}")
```

## 📚 Documentation

- **Full Documentation**: [docs.extendedmatrix.org/projects/s3dgraphy](https://docs.extendedmatrix.org/projects/s3dgraphy/)
- **API Reference**: [API Docs](https://docs.extendedmatrix.org/projects/s3dgraphy/en/latest/api.html)
- **Examples**: See `examples/` directory in the repository

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

```bash
# Development setup
git clone https://github.com/zalmoxes-laran/s3dgraphy.git
cd s3dgraphy
pip install -e .[dev]

# Run tests
pytest

# Format code
black src/
```

## 📋 Requirements

- **Python**: 3.8 or higher
- **Core**: pandas, networkx (optional), numpy
- **Compatible**: Works with Blender 4.0+ Python environment

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.

## 🏆 Credits

**Lead Developer**: Emanuel Demetrescu (CNR-ISPC)  
**Project**: Extended Matrix Framework  
**Institution**: CNR - Istituto di Scienze del Patrimonio Culturale

## 🔗 Related Projects

- [EMtools](https://github.com/zalmoxes-laran/EM-blender-tools) - Blender extension using s3Dgraphy
- [Extended Matrix](https://www.extendedmatrix.org) - Official methodology website
- [ATON Framework](https://github.com/phoenixbf/aton) - 3D web visualization platform

## 📞 Support

- 📧 **Email**: emanuel.demetrescu@cnr.it
- 🐛 **Issues**: [GitHub Issues](https://github.com/zalmoxes-laran/s3dgraphy/issues)
- 💬 **Community**: [Extended Matrix Telegram](https://t.me/UserGroupEM)

---

<p align="center">
  Part of the Extended Matrix Framework<br>
  Made with ❤️ for the Cultural Heritage community
</p>