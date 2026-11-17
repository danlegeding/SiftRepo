from app.services.chunker import chunk_code


def test_chunk_code_returns_expected_keys():
    chunks = chunk_code("def add(a, b):\n    return a + b\n", chunk_size=500, overlap=50)

    assert chunks
    assert set(chunks[0]) == {"content", "start_line", "end_line", "chunk_index"}


def test_chunk_code_line_numbers_start_at_one():
    chunks = chunk_code("line1\nline2\nline3\n", chunk_size=500, overlap=50)

    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] >= 1


def test_chunk_code_respects_chunk_size():
    content = "\n".join(f"line {i}" for i in range(200))

    chunks = chunk_code(content, chunk_size=100, overlap=10)

    assert len(chunks) > 1
    assert all(len(chunk["content"]) <= 100 for chunk in chunks)


def test_chunk_code_empty_content_returns_empty_list():
    assert chunk_code("", chunk_size=500, overlap=50) == []


def test_chunk_index_is_sequential():
    content = "\n".join(f"line {i}" for i in range(300))

    chunks = chunk_code(content, chunk_size=80, overlap=10)

    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
