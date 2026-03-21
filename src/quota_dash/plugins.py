from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Type

from quota_dash.providers.base import Provider

logger = logging.getLogger(__name__)

PLUGIN_DIR = Path.home() / ".config" / "quota-dash" / "plugins"


def discover_plugins(plugin_dir: Path | None = None) -> dict[str, Type[Provider]]:
    """Scan plugin directory for Provider subclasses.

    Returns dict of {provider_name: ProviderClass}.
    """
    directory = plugin_dir or PLUGIN_DIR
    plugins: dict[str, Type[Provider]] = {}

    if not directory.exists():
        return plugins

    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"quota_dash_plugin_{py_file.stem}", py_file
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]

            # Find all Provider subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, Provider)
                    and attr is not Provider
                    and hasattr(attr, "name")
                    and attr.name  # must have a non-empty name
                ):
                    plugins[attr.name] = attr
                    logger.info(
                        "Loaded plugin provider: %s from %s", attr.name, py_file.name
                    )
        except Exception:
            logger.warning(
                "Failed to load plugin: %s", py_file.name, exc_info=True
            )

    return plugins
