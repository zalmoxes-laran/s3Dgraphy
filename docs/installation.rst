Installation
============

System Requirements
-------------------

- **Python**: 3.8 or higher
- **Operating System**: Cross-platform (Windows, macOS, Linux)
- **Memory**: 512MB RAM minimum
- **Storage**: 50MB available space

Install from PyPI
-----------------

The easiest way to install s3dgraphy is using pip:

.. code-block:: bash

   pip install s3dgraphy

Development Installation
------------------------

For development or to get the latest features:

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/zalmoxes-laran/s3dgraphy.git
   cd s3dgraphy
   
   # Install in development mode
   pip install -e .[dev]

Optional Dependencies
--------------------

Install additional features:

.. code-block:: bash

   # For visualization features
   pip install s3dgraphy[visualization]
   
   # For development tools
   pip install s3dgraphy[dev]
   
   # For documentation building
   pip install s3dgraphy[docs]

Verify Installation
-------------------

Test your installation:

.. code-block:: python

   import s3dgraphy
   print(f"s3dgraphy version: {s3dgraphy.__version__}")
   
   # Create a simple graph
   from s3dgraphy import Graph
   graph = Graph("test")
   print("Installation successful!")

Troubleshooting
---------------

**Common Issues:**

1. **Import Error**: Make sure you're using Python 3.8+
2. **Permission Error**: Use `pip install --user s3dgraphy`
3. **Network Issues**: Try `pip install --trusted-host pypi.org s3dgraphy`

**For Blender Integration:**

s3dgraphy works with Blender 4.0+ through the EMtools extension.
