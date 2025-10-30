import io
import base64
import zipfile
from typing import Generator

import pytest
from unittest.mock import patch, Mock

from dify_plugin.entities.tool import ToolInvokeMessage


def make_zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.fixture
def zip_tool_instance(mock_runtime, mock_session):
    from tools.zip_file_inspector import ZipFileInspectorTool

    return ZipFileInspectorTool(runtime=mock_runtime, session=mock_session)


def collect_messages(gen: Generator[ToolInvokeMessage, None, None]):
    return list(gen)


def test_missing_file_url(zip_tool_instance):
    params = {"file_url": ""}
    messages = collect_messages(zip_tool_instance._invoke(params))

    assert len(messages) == 2
    assert messages[0].type.value == "text"
    assert "Missing required parameter" in messages[0].message.text
    assert messages[1].type.value == "json"
    assert messages[1].message.json_object["error"] == "invalid_file_url"


def test_download_failed(zip_tool_instance):
    with patch("tools.zip_file_inspector.requests.get", side_effect=RuntimeError("boom")):
        params = {"file_url": "https://example.com/a.zip"}
        messages = collect_messages(zip_tool_instance._invoke(params))

    assert len(messages) == 2
    assert messages[0].type.value == "text"
    assert "Download failed" in messages[0].message.text
    assert messages[1].type.value == "json"
    assert messages[1].message.json_object["error"] == "download_failed"


def test_not_zip(zip_tool_instance):
    fake_bytes = b"not a zip"
    resp = Mock()
    resp.content = fake_bytes
    resp.raise_for_status.return_value = None

    with patch("tools.zip_file_inspector.requests.get", return_value=resp):
        params = {"file_url": "https://example.com/notzip.bin"}
        messages = collect_messages(zip_tool_instance._invoke(params))

    assert len(messages) == 2
    assert messages[0].type.value == "text"
    assert "not a ZIP" in messages[0].message.text
    assert messages[1].type.value == "json"
    assert messages[1].message.json_object["error"] == "not_zip"


def test_success_list_files(zip_tool_instance):
    zbytes = make_zip_bytes({
        "docs/readme.txt": b"hello",
        "image/logo.png": b"\x89PNG\r\n\x1a\n...",
    })
    resp = Mock()
    resp.content = zbytes
    resp.raise_for_status.return_value = None

    with patch("tools.zip_file_inspector.requests.get", return_value=resp):
        params = {"file_url": "https://example.com/archive.zip"}
        messages = collect_messages(zip_tool_instance._invoke(params))

    assert len(messages) == 2
    assert messages[0].type.value == "text"
    assert "Found 2 files" in messages[0].message.text
    assert messages[1].type.value == "json"

    data = messages[1].message.json_object
    assert data["zip"]["source_url"].endswith("archive.zip")
    assert data["zip"]["num_files"] == 2

    files = data["files"]
    assert {f["filename"] for f in files} == {"docs/readme.txt", "image/logo.png"}
    for f in files:
        assert isinstance(f["size"], int)
        assert isinstance(f["mime_type"], str)
        assert isinstance(f["extension"], str)
        assert isinstance(f["sha256"], str) and len(f["sha256"]) == 64
        assert f["url"] is None


def test_include_content_b64(zip_tool_instance):
    content = b"secret-bytes"
    zbytes = make_zip_bytes({"secret.bin": content})
    resp = Mock()
    resp.content = zbytes
    resp.raise_for_status.return_value = None

    with patch("tools.zip_file_inspector.requests.get", return_value=resp):
        params = {"file_url": "https://example.com/a.zip", "include_content_b64": True}
        messages = collect_messages(zip_tool_instance._invoke(params))

    data = messages[1].message.json_object
    files = data["files"]
    assert len(files) == 1
    assert "content_base64" in files[0]
    assert base64.b64decode(files[0]["content_base64"]) == content


def test_max_files(zip_tool_instance):
    zbytes = make_zip_bytes({
        "a.txt": b"a",
        "b.txt": b"b",
        "c.txt": b"c",
    })
    resp = Mock()
    resp.content = zbytes
    resp.raise_for_status.return_value = None

    with patch("tools.zip_file_inspector.requests.get", return_value=resp):
        params = {"file_url": "https://example.com/multi.zip", "max_files": 1}
        messages = collect_messages(zip_tool_instance._invoke(params))

    data = messages[1].message.json_object
    assert data["zip"]["num_files"] == 1
    assert len(data["files"]) == 1


