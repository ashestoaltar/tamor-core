"""
Exporter Plugins

Phase 6.3/6.4: Plugin Framework

This package contains all exporter plugins. Each plugin is auto-discovered
and registered by the PluginRegistry when load_plugins() is called.

Available exporters:
- zip_download: Download all project files as a ZIP archive
- json_export: Export structured project data as JSON
- markdown_export: Export conversations and notes as formatted markdown
"""

from .markdown_export import MarkdownExporter

__all__ = ['MarkdownExporter']
