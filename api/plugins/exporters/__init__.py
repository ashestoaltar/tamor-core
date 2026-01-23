"""
Exporter Plugins

Phase 6.3: Plugin Framework

This package contains all exporter plugins. Each plugin is auto-discovered
and registered by the PluginRegistry when load_plugins() is called.

Available exporters:
- zip_download: Download all project files as a ZIP archive
- json_export: Export structured project data as JSON
"""
