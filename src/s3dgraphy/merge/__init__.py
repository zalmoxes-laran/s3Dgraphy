"""
Merge module for s3dgraphy.

Provides graph comparison and conflict detection for merge workflows.
"""

from .graph_merger import GraphMerger, Conflict

__all__ = ['GraphMerger', 'Conflict']
