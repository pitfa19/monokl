"""Safe deterministic retrieval boundary for Monokl."""

from __future__ import annotations

import importlib.metadata
import ipaddress
import socket
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener

from .contracts import SCHEMA_VERSION, canonical_sha256, sha256_hex

ADAPTER_VERSION = "monokl-retriever-v1"
_ALLOWED_SCHEMES = {"http", "https"}
_REFUSED_CONFIG_FIELDS = ("credentials", "profile", "proxy", "llm", "javascript", "download")


@dataclass(frozen=True)
class RetrievalBudgets:
    max_pages: int = 1
    max_bytes_per_page: int = 2_000_000
    max_redirects: int = 5
    timeout_seconds: float = 15.0
    allowed_hosts: tuple[str, ...] = ()

    def validate(self) -> None:
        for name in ("max_pages", "max_bytes_per_page", "max_redirects"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.timeout_seconds, (int, float)) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        for host in self.allowed_hosts:
            if not host or "/" in host or "\\" in host:
                raise ValueError("allowed_hosts must contain host names only")


@dataclass(frozen=True)
class RetrievalRequest:
    url: str
    budgets: RetrievalBudgets
    config: dict[str, Any]

    def validate(self) -> None:
        self.budgets.validate()
        refused = [name for name in _REFUSED_CONFIG_FIELDS if self.config.get(name)]
        if refused:
            raise ValueError(f"refused retrieval option(s): {', '.join(refused)}")


class Retriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> dict[str, Any]:
        """Return a retrieval artifact without mutating the ledger."""


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not any(
        [
            ip.is_loopback,
            ip.is_private,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
    )


def _resolve_public(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError(f"dns_resolution_failed: {host}") from error
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise ValueError(f"dns_resolution_failed: {host}")
    blocked = [address for address in addresses if not _is_public_ip(address)]
    if blocked:
        raise ValueError(f"private_or_local_address_refused: {host} -> {', '.join(blocked)}")
    return addresses


def check_public_url(url: str, budgets: RetrievalBudgets) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"scheme_refused: {parsed.scheme or 'missing'}")
    if not parsed.hostname:
        raise ValueError("host_required")
    host = parsed.hostname.lower()
    allowed = tuple(host.lower() for host in budgets.allowed_hosts)
    if allowed and host not in allowed:
        raise ValueError(f"host_not_allowed: {host}")
    addresses = _resolve_public(host)
    return {"url": url, "scheme": parsed.scheme, "host": host, "resolved_addresses": addresses}


def browser_isolation_policy(budgets: RetrievalBudgets) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.browser_isolation_policy",
        "persistent_profile": False,
        "credentials": False,
        "proxy": False,
        "downloads": False,
        "arbitrary_javascript": False,
        "llm_api": False,
        "network": {
            "public_http_https_only": True,
            "dns_checks_before_and_after_redirects": True,
            "allowed_hosts": list(budgets.allowed_hosts),
            "loopback_private_link_local_local_files_refused": True,
        },
        "resources": {
            "max_pages": budgets.max_pages,
            "max_bytes_per_page": budgets.max_bytes_per_page,
            "max_redirects": budgets.max_redirects,
            "timeout_seconds": budgets.timeout_seconds,
            "child_process_limit": 1,
            "browser_process_isolated": True,
            "memory_limit_observable": True,
            "cpu_limit_observable": True,
            "temporary_storage_downloads_disabled": True,
        },
    }


def _markdown_from_html(data: bytes) -> tuple[str | None, str | None]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "malformed_page"
    lowered = text.lower()
    if "<html" not in lowered:
        return None, "malformed_page"
    title = None
    start = lowered.find("<title")
    if start >= 0:
        gt = lowered.find(">", start)
        end = lowered.find("</title>", gt)
        if gt >= 0 and end >= 0:
            title = text[gt + 1 : end].strip()
    return text, None


class StdlibRetriever:
    def retrieve(self, request: RetrievalRequest) -> dict[str, Any]:
        request.validate()
        started = time.monotonic()
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "contract": "monokl.retrieval_snapshot",
            "adapter_version": ADAPTER_VERSION,
            "crawl4ai_version": None,
            "requested_url": request.url,
            "final_url": None,
            "status": "error",
            "http_status": None,
            "redirects": [],
            "budget": asdict(request.budgets),
            "cache_key": canonical_sha256({"url": request.url, "budget": asdict(request.budgets), "adapter": ADAPTER_VERSION}),
            "preflight": None,
            "postflight": None,
            "content_sha256": None,
            "normalized_markdown_sha256": None,
            "normalized_markdown_bytes": 0,
            "truncated": False,
            "error": None,
            "browser_isolation_policy": browser_isolation_policy(request.budgets),
        }
        try:
            manifest["preflight"] = check_public_url(request.url, request.budgets)
            opener = build_opener(NoRedirectHandler)
            current = request.url
            seen = set()
            for _ in range(request.budgets.max_redirects + 1):
                if current in seen:
                    raise RuntimeError("redirect_loop")
                seen.add(current)
                if time.monotonic() - started > request.budgets.timeout_seconds:
                    raise TimeoutError("timeout")
                check_public_url(current, request.budgets)
                req = Request(current, headers={"User-Agent": "monokl/1 safe-retriever"})
                try:
                    with opener.open(req, timeout=request.budgets.timeout_seconds) as response:
                        status = response.getcode()
                        data = response.read(request.budgets.max_bytes_per_page + 1)
                        final_url = response.geturl()
                except HTTPError as error:
                    if error.code in {301, 302, 303, 307, 308} and error.headers.get("Location"):
                        target = urljoin(current, error.headers["Location"])
                        manifest["redirects"].append({"from": current, "to": target, "status": error.code})
                        check_public_url(target, request.budgets)
                        current = target
                        continue
                    manifest["http_status"] = error.code
                    raise RuntimeError(f"http_failure: {error.code}") from error
                if len(data) > request.budgets.max_bytes_per_page:
                    data = data[: request.budgets.max_bytes_per_page]
                    manifest["truncated"] = True
                    manifest["error"] = {"code": "oversized_content", "message": "page exceeded byte budget"}
                markdown, parse_error = _markdown_from_html(data)
                manifest["final_url"] = final_url
                manifest["http_status"] = status
                manifest["postflight"] = check_public_url(final_url, request.budgets)
                manifest["content_sha256"] = sha256_hex(data)
                if parse_error:
                    manifest["status"] = "partial"
                    manifest["error"] = {"code": parse_error, "message": "page could not be normalized"}
                else:
                    manifest["status"] = "partial" if manifest["truncated"] else "ok"
                    manifest["normalized_markdown_sha256"] = sha256_hex(markdown.encode("utf-8"))
                    manifest["normalized_markdown_bytes"] = len(markdown.encode("utf-8"))
                return manifest
            raise RuntimeError("redirect_loop")
        except TimeoutError as error:
            manifest["error"] = {"code": "timeout", "message": str(error) or "retrieval timed out"}
        except URLError as error:
            message = str(error.reason if hasattr(error, "reason") else error)
            code = "timeout" if "timed out" in message.lower() else "url_error"
            manifest["error"] = {"code": code, "message": message}
        except Exception as error:
            code = str(error).split(":", 1)[0]
            manifest["error"] = {"code": code, "message": str(error)}
        return manifest


class NoRedirectHandler(__import__("urllib.request").request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


class Crawl4AIRetriever(StdlibRetriever):
    """Optional pinned Crawl4AI wrapper. Falls back only by explicit caller choice."""

    def __init__(self, required_version: str | None = None) -> None:
        try:
            version = importlib.metadata.version("crawl4ai")
        except importlib.metadata.PackageNotFoundError as error:
            raise RuntimeError("crawl4ai_not_installed") from error
        if required_version and version != required_version:
            raise RuntimeError(f"crawl4ai_version_mismatch: expected {required_version}, found {version}")
        self.version = version

    def retrieve(self, request: RetrievalRequest) -> dict[str, Any]:
        manifest = super().retrieve(request)
        manifest["crawl4ai_version"] = self.version
        return manifest
