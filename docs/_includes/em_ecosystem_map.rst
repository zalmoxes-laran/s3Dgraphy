.. _em-ecosystem-map:

Where this fits — the Extended Matrix ecosystem
================================================

.. note::

   *Extended Matrix* is the name of **the broader project** —
   a formal language, an open-source tool family and a community.
   Each individual component below has its own name and its own
   manual. When you see *Extended Matrix* (or *EM*) **without a
   qualifier**, the surrounding context normally tells you whether
   the reference is to the project as a whole or to the formal
   language specifically. The table below disambiguates the
   components.

.. list-table::
   :header-rows: 1
   :widths: 22 38 40

   * - Name
     - What it is
     - Where to learn it
   * - **EM language**
     - The *formal language* (the notation itself) used to document
       stratigraphy and reconstruction processes. Drawn in yEd
       (with the EM palette) or produced from an ``em_data.xlsx``
       worksheet. This is what the *EM language manual* on
       ``docs.extendedmatrix.org`` documents — node types,
       connectors, paradata, canvas conventions, formal semantics.
     - `EM language manual <https://docs.extendedmatrix.org>`_
   * - **EM Tools**
     - The *Blender add-on* that connects an EM graph to 3D content —
       proxies, representation models, exports.
     - `EM Tools manual <https://docs.extendedmatrix.org/projects/EM-tools/>`_
   * - **s3dgraphy**
     - The *Python library* that powers EM Tools — graph data
       structures, GraphML / XLSX / SQLite import/export, JSON for
       web platforms. Usable standalone outside Blender.
     - `s3dgraphy manual <https://docs.extendedmatrix.org/projects/s3dgraphy/>`_
   * - **3DSC**
     - A complementary Blender add-on for high-quality *3D survey*
       processing (photogrammetry, LOD, Cesium tilesets) that feeds
       EM Tools.
     - `3DSC manual <https://docs.extendedmatrix.org/projects/3DSC/>`_
   * - **Heriverse**
     - The *Heritage Science Metaverse* — web-based publication and
       collaborative VR for EM-aware scenes. The natural endpoint of
       what you author in EM Tools.
     - `Heriverse manual <https://docs.extendedmatrix.org/projects/heriverse/>`_

**If you are unsure which one you need:** start from the **EM
language** if you have *evidence to organize*; come to **EM Tools**
if you have *3D content to annotate*; reach for **3DSC** if you have
*raw survey data to clean and align*; open **Heriverse** when your
work is *ready to be published on the web*. The Extended Matrix
site at `extendedmatrix.org <https://www.extendedmatrix.org>`_ is
the discovery and orchestration layer above all the manuals — start
there if you are not sure which manual to open first. For
methodological end-to-end paths that cross multiple tools (a
photogrammetric pipeline, an anastylosis workflow, a web
publication), see the
`Workflows <https://www.extendedmatrix.org/workflows/>`_ collection
on the site.

.. note::

   This map is identical in every Extended Matrix manual (EM
   language, EM Tools, s3dgraphy, 3DSC, Heriverse). Wherever you
   land, you can orient yourself in the broader ecosystem from this
   table.
