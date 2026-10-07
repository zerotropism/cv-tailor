"""Every declared console script must resolve: `cv-tailor` pointed at a missing module."""

from importlib.metadata import entry_points


def test_console_scripts_resolve() -> None:
    scripts = [
        ep for ep in entry_points(group="console_scripts") if ep.value.startswith("cv_tailor.")
    ]
    assert sorted(ep.name for ep in scripts) == [
        "cv-tailor",
        "cv-tailor-api",
        "cv-tailor-eval",
        "cv-tailor-mcp",
    ]
    for ep in scripts:
        assert callable(ep.load())
