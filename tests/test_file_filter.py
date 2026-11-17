from app.services.file_filter import SUPPORTED_EXTENTION


def test_code_extensions_are_supported():
    assert {".py", ".java", ".go", ".rs"} <= SUPPORTED_EXTENTION


def test_document_and_config_extensions_are_supported():
    assert {".md", ".txt", ".json", ".yaml", ".toml"} <= SUPPORTED_EXTENTION


def test_binary_extensions_are_not_supported():
    assert ".png" not in SUPPORTED_EXTENTION
    assert ".zip" not in SUPPORTED_EXTENTION
    assert ".exe" not in SUPPORTED_EXTENTION
