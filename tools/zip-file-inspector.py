from __future__ import annotations

import base64
import hashlib
import io
import json
import mimetypes
import re
import zipfile
from typing import Any, Generator

import requests
from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage


class ZipFileInspectorTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        file_url: str = str(tool_parameters.get("file_url") or "").strip()
        include_content_b64: bool = bool(tool_parameters.get("include_content_b64") or False)
        max_files_value: Any = tool_parameters.get("max_files")
        try:
            max_files: int | None = int(max_files_value) if max_files_value is not None else None
        except Exception:
            max_files = None

        if not file_url:
            yield self.create_text_message("Missing required parameter: file_url")
            yield self.create_json_message({"error": "invalid_file_url"})
            return

        try:
            zip_bytes = self._download_url(file_url)
        except Exception as download_err:
            yield self.create_text_message(f"Download failed: {download_err}")
            yield self.create_json_message({"error": "download_failed", "detail": str(download_err)})
            return

        if not self._looks_like_zip(zip_bytes):
            yield self.create_text_message("Provided file is not a ZIP archive")
            yield self.create_json_message({"error": "not_zip"})
            return

        try:
            file_list = self._extract_metadata(zip_bytes, include_content_b64=include_content_b64, max_files=max_files)
        except Exception as unzip_err:
            yield self.create_text_message(f"Unzip failed: {unzip_err}")
            yield self.create_json_message({"error": "unzip_failed", "detail": str(unzip_err)})
            return

        result = {
            "zip": {
                "source_url": file_url,
                "num_files": len(file_list),
            },
            "files": file_list,
        }

        yield self.create_text_message(f"Found {len(file_list)} files in ZIP")
        yield self.create_json_message(result)

    def _download_url(self, url: str) -> bytes:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def _looks_like_zip(self, blob: bytes) -> bool:
        # ZIP local file header signature PK\x03\x04
        return len(blob) >= 4 and blob[:4] == b"PK\x03\x04"

    def _extract_metadata(self, zip_blob: bytes, include_content_b64: bool, max_files: int | None) -> list[dict[str, Any]]:
        file_list: list[dict[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(zip_blob)) as zf:
            members = [i for i in zf.infolist() if not i.is_dir()]
            if max_files is not None:
                members = members[: max_files]
            for info in members:
                with zf.open(info) as fp:
                    data = fp.read()
                sha256 = hashlib.sha256(data).hexdigest()
                mime_type, _ = mimetypes.guess_type(info.filename)
                mime_type = mime_type or "application/octet-stream"
                ext_match = re.search(r"\.([A-Za-z0-9]+)$", info.filename)
                extension = ext_match.group(1).lower() if ext_match else ""

                file_obj: dict[str, Any] = {
                    "filename": info.filename,
                    "size": len(data),
                    "mime_type": mime_type,
                    "extension": extension,
                    "sha256": sha256,
                    # No upload performed here; downstream can decide how to host or consume.
                    "url": None,
                }
                if include_content_b64:
                    file_obj["content_base64"] = base64.b64encode(data).decode("utf-8")

                file_list.append(file_obj)
        return file_list


