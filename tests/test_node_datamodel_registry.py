"""Guard: the generated node registry must stay in sync with the node classes.

The class hierarchy is part of the datamodel (the JSONs are the source of
truth for every EM consumer — Python and non-Python alike). It lives in the
generated ``JSON_config/node_registry.generated.json``. If this test fails,
run:

    python -m s3dgraphy.tools.sync_node_datamodel
"""

from s3dgraphy.tools.sync_node_datamodel import sync


def test_node_registry_in_sync():
    assert sync(check_only=True) == 0, (
        "node_registry.generated.json is out of sync with the node classes; "
        "run: python -m s3dgraphy.tools.sync_node_datamodel"
    )
