from quota_dash.plugins import discover_plugins


def test_discover_no_directory(tmp_path):
    """Non-existent directory returns empty dict."""
    result = discover_plugins(tmp_path / "nonexistent")
    assert result == {}


def test_discover_empty_directory(tmp_path):
    """Empty directory returns empty dict."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    result = discover_plugins(plugin_dir)
    assert result == {}


def test_discover_valid_plugin(tmp_path):
    """Valid plugin .py file with Provider subclass is discovered."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    plugin_code = '''
from quota_dash.providers.base import ManualProvider

class MyCustomProvider(ManualProvider):
    name = "custom"
    _default_model = "custom-model"
    _max_context = 32000
'''
    (plugin_dir / "custom_provider.py").write_text(plugin_code)

    result = discover_plugins(plugin_dir)
    assert "custom" in result
    assert result["custom"].name == "custom"


def test_discover_skips_underscore_files(tmp_path):
    """Files starting with _ are skipped."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "_helper.py").write_text("x = 1")
    result = discover_plugins(plugin_dir)
    assert result == {}


def test_discover_skips_broken_plugin(tmp_path):
    """Broken plugin files are skipped with warning, not crash."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "broken.py").write_text("import nonexistent_module_xyz")
    result = discover_plugins(plugin_dir)
    assert result == {}


def test_discover_skips_non_provider_classes(tmp_path):
    """Classes that don't subclass Provider are ignored."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "not_provider.py").write_text("class Foo:\n    name = 'foo'\n")
    result = discover_plugins(plugin_dir)
    assert result == {}


def test_discover_multiple_plugins(tmp_path):
    """Multiple valid plugins are all discovered."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    for i in range(3):
        code = f'''
from quota_dash.providers.base import ManualProvider

class Provider{i}(ManualProvider):
    name = "plugin{i}"
    _default_model = "model-{i}"
    _max_context = 32000
'''
        (plugin_dir / f"provider_{i}.py").write_text(code)

    result = discover_plugins(plugin_dir)
    assert len(result) == 3
    assert "plugin0" in result
    assert "plugin1" in result
    assert "plugin2" in result


def test_discover_skips_provider_base_class(tmp_path):
    """The Provider base class itself is not returned even if imported."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    plugin_code = '''
from quota_dash.providers.base import Provider, ManualProvider

class MyPlugin(ManualProvider):
    name = "myplugin"
    _default_model = "my-model"
    _max_context = 16000
'''
    (plugin_dir / "myplugin.py").write_text(plugin_code)

    result = discover_plugins(plugin_dir)
    # Only the concrete subclass should be found, not Provider itself
    assert "myplugin" in result
    # Provider base class has empty name so it won't be in results
    assert len(result) == 1


def test_discover_skips_class_without_name(tmp_path):
    """Classes subclassing Provider but missing a name attribute are skipped."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    plugin_code = '''
from quota_dash.providers.base import ManualProvider

class NoNameProvider(ManualProvider):
    # name is inherited as "" from ManualProvider — falsy, should be skipped
    _default_model = "model"
    _max_context = 16000
'''
    (plugin_dir / "noname.py").write_text(plugin_code)

    result = discover_plugins(plugin_dir)
    assert result == {}
