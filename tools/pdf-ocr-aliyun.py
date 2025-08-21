from collections.abc import Generator
from typing import Any, List, Optional

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from openai import OpenAI
from urllib.parse import urlparse
import mimetypes
import base64
import requests
import io
import pypdfium2 as pdfium
from PIL import Image


class PdfOcrAliyunTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        prompt: str = str(tool_parameters.get("prompt") or "").strip()
        raw_image_value: Any = tool_parameters.get("image_url")
        image_url: str = self._extract_image_url(raw_image_value)

        # Allow relative paths from upstream, build absolute with optional base
        # Build absolute image URL from env/provider if needed
        auto_base = self._get_auto_base_url()
        image_url = self._absolutize_url(image_url, auto_base)

        if not prompt:
            yield self.create_text_message("Missing required parameter: prompt")
            return
        if not image_url:
            yield self.create_text_message("Missing required parameter: image_url")
            return
        # Basic URL validation to avoid provider 400s
        if not (image_url.startswith("http://") or image_url.startswith("https://")):
            yield self.create_json_message({
                "error": "invalid_image_url",
                "detail": "`image_url` must start with http:// or https://",
                "value": image_url,
            })
            return

        # Allow per-call api_key and model override; fallback to provider credentials
        override_key = tool_parameters.get("api_key")
        api_key = str((override_key if override_key is not None else self.runtime.credentials.get("api_key")) or "").strip()
        base_url = str(self.runtime.credentials.get("base_url") or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
        
        override_model = tool_parameters.get("model")
        model = str((override_model if override_model is not None else self.runtime.credentials.get("model")) or "qwen-vl-ocr").strip()

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        contents: List[dict[str, Any]] = [{"type": "text", "text": prompt}]

        pdf_bytes: Optional[bytes] = None
        if self._is_pdf_resource(image_url):
            try:
                pdf_bytes = self._download_bytes(image_url)
            except Exception:
                pdf_bytes = None
        if pdf_bytes is None:
            # Attempt to detect PDF by headers/magic for local file URLs
            pdf_bytes = self._try_download_pdf(image_url)

        if pdf_bytes is not None:
            images = self._convert_pdf_to_data_urls(pdf_bytes)
            if not images:
                yield self.create_json_message({
                    "error": "pdf_convert_failed",
                    "detail": "no images rendered from pdf",
                })
                return

            pages_result: List[dict[str, Any]] = []
            for idx, data_url in enumerate(images, start=1):
                page_messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": data_url},
                        ],
                    }
                ]
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=page_messages,
                        response_format={"type": "json_object"},
                        max_tokens=4096,
                    )
                    page_text = "{}"
                    if getattr(resp, "choices", None):
                        try:
                            page_text = resp.choices[0].message.content or "{}"
                        except Exception:
                            page_text = "{}"
                    pages_result.append({"page": idx, "content": self.safe_json_loads(page_text)})
                except Exception as e:
                    pages_result.append({"page": idx, "error": str(e)})

            unified = {"pages": pages_result}
            # Also emit text so "Direct Reply" can bind to it
            try:
                import json as _json
                text_payload = _json.dumps(unified, ensure_ascii=False)
            except Exception:
                text_payload = str(unified)
            yield self.create_text_message(text_payload)
            yield self.create_json_message(unified)
            return
        else:
            image_value = self._download_to_data_url_if_needed(image_url) or image_url
            contents.append({"type": "image_url", "image_url": image_value})

        messages = [
            {
                "role": "user",
                "content": contents,
            }
        ]

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
        except Exception as e:
            yield self.create_json_message({
                "error": "request_failed",
                "detail": str(e),
            })
            return

        output_text = "{}"
        if getattr(response, "choices", None):
            try:
                output_text = response.choices[0].message.content or "{}"
            except Exception:
                output_text = "{}"

        parsed = self.safe_json_loads(output_text)
        unified = {"pages": [{"page": 1, "content": parsed}]}
        # Emit text for Direct Reply, plus json for json output var
        try:
            import json as _json
            text_payload = _json.dumps(unified, ensure_ascii=False)
        except Exception:
            text_payload = str(unified)
        yield self.create_text_message(text_payload)
        yield self.create_json_message(unified)

    @staticmethod
    def safe_json_loads(s: str) -> Any:
        try:
            import json
            return json.loads(s)
        except Exception:
            return {"raw": s}

    def _extract_image_url(self, value: Any) -> str:
        # Accept direct string
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ""
            # Try JSON decoding if looks like JSON
            if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
                try:
                    import json
                    decoded = json.loads(text)
                    return self._extract_image_url(decoded)
                except Exception:
                    return text
            return text

        # Accept dict with common url fields
        if isinstance(value, dict):
            for key in ("url", "image_url", "image", "src", "href", "value"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
                if isinstance(candidate, dict) or isinstance(candidate, list):
                    extracted = self._extract_image_url(candidate)
                    if extracted:
                        return extracted
            return ""

        # Accept list/tuple and take first resolvable
        if isinstance(value, (list, tuple)):
            for item in value:
                extracted = self._extract_image_url(item)
                if extracted:
                    return extracted
            return ""

        # Fallback to empty
        return ""

    def _absolutize_url(self, url: str, base_override: str) -> str:
        if not url:
            return url
        # Already absolute
        if url.startswith("http://") or url.startswith("https://"):
            return url
        # Strip quotes if mistakenly included
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1]
        # Ensure a single leading slash
        if not url.startswith("/"):
            url = f"/{url}"

        # Prefer explicit base if provided
        base = base_override
        if not base:
            # Try to use provider-configured file host base
            base = str(self.runtime.credentials.get("file_host_base") or "").strip()

        if base:
            # Remove trailing slash to avoid double slashes
            while base.endswith("/"):
                base = base[:-1]
            return f"{base}{url}"

        # If no base available, return as-is (will be caught by validator)
        return url

    def _get_auto_base_url(self) -> str:
        # Prefer environment injected by Dify if present
        try:
            import os
            # Common envs used by Dify plugin daemon / deployments
            for key in (
                "FILES_URL",
                "INTERNAL_FILES_URL",
            ):
                v = os.getenv(key)
                if v and (v.startswith("http://") or v.startswith("https://")):
                    # Remove trailing slash
                    while v.endswith("/"):
                        v = v[:-1]
                    return v

            # Development heuristic: if connected to local plugin-daemon, assume local web at 3000
            remote = os.getenv("REMOTE_INSTALL_URL", "")
            if remote and ("localhost" in remote or "127.0.0.1" in remote):
                return "http://localhost"
        except Exception:
            pass
        return ""

    def _download_to_data_url_if_needed(self, abs_url: str) -> str:
        try:
            parsed = urlparse(abs_url)
            host = (parsed.hostname or "").lower()
            # If host is localhost/private, Aliyun cannot fetch it; download and embed
            is_local = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local")
            if is_local:
                resp = requests.get(abs_url, timeout=20)
                resp.raise_for_status()
                content_type = (
                    resp.headers.get("Content-Type")
                    or mimetypes.guess_type(parsed.path)[0]
                    or "image/jpeg"
                )
                return f"data:{content_type};base64,{base64.b64encode(resp.content).decode('utf-8')}"
        except Exception:
            return ""
        return ""

    def _download_bytes(self, abs_url: str) -> bytes:
        r = requests.get(abs_url, timeout=30)
        r.raise_for_status()
        return r.content

    def _is_pdf_resource(self, abs_url: str) -> bool:
        try:
            path = urlparse(abs_url).path.lower()
            if path.endswith(".pdf"):
                return True
            guessed, _ = mimetypes.guess_type(path)
            return guessed == "application/pdf"
        except Exception:
            return False

    def _try_download_pdf(self, abs_url: str) -> Optional[bytes]:
        """Try to determine if the resource is a PDF and return bytes if so.
        Strategy: HEAD for content-type, then GET and magic bytes check for local hosts.
        """
        try:
            parsed = urlparse(abs_url)
            host = (parsed.hostname or "").lower()
            # Prefer HEAD to avoid large downloads
            try:
                h = requests.head(abs_url, timeout=10, allow_redirects=True)
                ctype = (h.headers.get("Content-Type") or "").lower()
                if "application/pdf" in ctype:
                    return self._download_bytes(abs_url)
            except Exception:
                pass

            # For local/private hosts, fetch and check magic
            if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
                data = self._download_bytes(abs_url)
                if data[:5] == b"%PDF-":
                    return data
        except Exception:
            return None
        return None

    def _convert_pdf_to_data_urls(self, pdf_bytes: bytes) -> List[str]:
        data_urls: List[str] = []
        with io.BytesIO(pdf_bytes) as bio:
            pdf = pdfium.PdfDocument(bio)
            page_count = len(pdf)
            for index in range(page_count):
                page = pdf[index]
                bitmap = page.render(scale=2.0).to_pil()
                if not isinstance(bitmap, Image.Image):
                    continue
                buf = io.BytesIO()
                bitmap.save(buf, format="PNG")
                data_urls.append(f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}")
        return data_urls
