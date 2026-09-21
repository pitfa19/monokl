"""Safe deterministic retrieval boundary for Monokl."""

from __future__ import annotations

import importlib.metadata
import ipaddress
import json
import os
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, build_opener

from .contracts import SCHEMA_VERSION, canonical_sha256, sha256_hex

ADAPTER_VERSION = "monokl-retriever-v2"
_ALLOWED_SCHEMES = {"http", "https"}
_REFUSED_CONFIG_FIELDS = ("credentials", "profile", "proxy", "llm", "javascript", "download", "cdp", "storage")
_DEFAULT_CPU_SECONDS = 20
_DEFAULT_MEMORY_BYTES = 768 * 1024 * 1024
_DEFAULT_TEMP_BYTES = 64 * 1024 * 1024


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


def _normalized_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    netloc = host
    if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def check_public_url(url: str, budgets: RetrievalBudgets) -> dict[str, Any]:
    normalized = _normalized_url(url)
    parsed = urlparse(normalized)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"scheme_refused: {parsed.scheme or 'missing'}")
    if not parsed.hostname:
        raise ValueError("host_required")
    host = parsed.hostname.lower()
    allowed = tuple(host.lower() for host in budgets.allowed_hosts)
    if allowed and host not in allowed:
        raise ValueError(f"host_not_allowed: {host}")
    addresses = _resolve_public(host)
    return {"url": normalized, "scheme": parsed.scheme, "host": host, "resolved_addresses": addresses}


def crawl4ai_config_digest(budgets: RetrievalBudgets) -> str:
    return canonical_sha256(_crawl4ai_config_identity(budgets))


def _crawl4ai_config_identity(budgets: RetrievalBudgets) -> dict[str, Any]:
    return {
        "browser_config": {
            "headless": True,
            "browser_type": "chromium",
            "use_persistent_context": False,
            "user_data_dir": None,
            "proxy_config": None,
            "downloads_path": None,
            "ignore_https_errors": False,
            "java_script_enabled": False,
            "use_managed_browser": False,
            "cdp_url": None,
        },
        "crawler_run_config": {
            "cache_mode": "BYPASS",
            "word_count_threshold": 0,
            "js_code": None,
            "excluded_tags": ["script", "style"],
            "scan_full_page": False,
            "process_iframes": False,
            "remove_overlay_elements": True,
            "magic": False,
        },
        "network_policy": {
            "allowed_hosts": list(budgets.allowed_hosts),
            "public_http_https_only": True,
            "enforce_after_browser_resolution_and_redirects": True,
        },
    }


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
        "cdp": False,
        "storage_state": False,
        "ignore_https_errors": False,
        "cache_mode": "BYPASS",
        "crawl4ai_config_digest": crawl4ai_config_digest(budgets),
        "network": {
            "public_http_https_only": True,
            "dns_checks_before_and_after_redirects": True,
            "browser_request_interception": True,
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


def _base_manifest(request: RetrievalRequest, *, crawl4ai_version: str | None) -> dict[str, Any]:
    normalized = _normalized_url(request.url)
    config_digest = crawl4ai_config_digest(request.budgets)
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "monokl.retrieval_snapshot",
        "adapter_version": ADAPTER_VERSION,
        "crawl4ai_version": crawl4ai_version,
        "crawl4ai_config_digest": config_digest,
        "requested_url": request.url,
        "normalized_url": normalized,
        "final_url": None,
        "status": "error",
        "http_status": None,
        "redirects": [],
        "budget": asdict(request.budgets),
        "cache_key": canonical_sha256({"normalized_url": normalized, "budget": asdict(request.budgets), "adapter": ADAPTER_VERSION, "crawl4ai_version": crawl4ai_version, "crawl4ai_config_digest": config_digest}),
        "preflight": None,
        "postflight": None,
        "content_sha256": None,
        "normalized_markdown_sha256": None,
        "normalized_markdown_bytes": 0,
        "truncated": False,
        "error": None,
        "browser_isolation_policy": browser_isolation_policy(request.budgets),
        "observed_limits": None,
    }


def _markdown_from_html(data: bytes) -> tuple[str | None, str | None]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "malformed_page"
    lowered = text.lower()
    if "<html" not in lowered:
        return None, "malformed_page"
    return text, None


class StdlibRetriever:
    def retrieve(self, request: RetrievalRequest) -> dict[str, Any]:
        request.validate()
        started = time.monotonic()
        manifest = _base_manifest(request, crawl4ai_version=None)
        try:
            manifest["preflight"] = check_public_url(request.url, request.budgets)
            opener = build_opener(NoRedirectHandler)
            current = request.url
            seen = set()
            for _ in range(request.budgets.max_redirects + 1):
                normalized_current = _normalized_url(current)
                if normalized_current in seen:
                    raise RuntimeError("redirect_loop")
                seen.add(normalized_current)
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
                        manifest["redirects"].append({"from": _normalized_url(current), "to": _normalized_url(target), "status": error.code})
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
                manifest["final_url"] = _normalized_url(final_url)
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


class Crawl4AIRetriever:
    """Optional pinned Crawl4AI wrapper executed in a scrubbed isolated subprocess."""

    def __init__(self, required_version: str | None = None) -> None:
        try:
            version = importlib.metadata.version("crawl4ai")
        except importlib.metadata.PackageNotFoundError as error:
            raise RuntimeError("crawl4ai_not_installed") from error
        if required_version and version != required_version:
            raise RuntimeError(f"crawl4ai_version_mismatch: expected {required_version}, found {version}")
        self.version = version

    def retrieve(self, request: RetrievalRequest) -> dict[str, Any]:
        request.validate()
        manifest = _base_manifest(request, crawl4ai_version=self.version)
        try:
            manifest["preflight"] = check_public_url(request.url, request.budgets)
            result = _run_crawl4ai_subprocess(request, self.version)
            manifest["observed_limits"] = result.get("observed_limits")
            if result.get("status") != "ok":
                manifest["error"] = result.get("error", {"code": "crawl4ai_error", "message": "crawl4ai failed"})
                return manifest
            final_url = result.get("final_url") or request.url
            manifest["postflight"] = check_public_url(final_url, request.budgets)
            manifest["final_url"] = _normalized_url(final_url)
            manifest["http_status"] = result.get("http_status")
            manifest["redirects"] = result.get("redirects", [])
            markdown = (result.get("markdown") or "").encode("utf-8")
            if len(markdown) > request.budgets.max_bytes_per_page:
                markdown = markdown[: request.budgets.max_bytes_per_page]
                manifest["truncated"] = True
                manifest["error"] = {"code": "oversized_content", "message": "page exceeded byte budget"}
            manifest["content_sha256"] = result.get("content_sha256") or sha256_hex(markdown)
            manifest["normalized_markdown_sha256"] = sha256_hex(markdown)
            manifest["normalized_markdown_bytes"] = len(markdown)
            manifest["status"] = "partial" if manifest["truncated"] else "ok"
        except Exception as error:
            manifest["error"] = {"code": str(error).split(":", 1)[0], "message": str(error)}
        return manifest


def _run_crawl4ai_subprocess(request: RetrievalRequest, crawl4ai_version: str) -> dict[str, Any]:
    payload = {"url": request.url, "budgets": asdict(request.budgets), "config_identity": _crawl4ai_config_identity(request.budgets), "crawl4ai_version": crawl4ai_version}
    timeout = max(1.0, float(request.budgets.timeout_seconds))
    cpu_seconds = max(1, min(_DEFAULT_CPU_SECONDS, int(timeout) + 2))
    memory_bytes = _DEFAULT_MEMORY_BYTES
    temp_bytes = _DEFAULT_TEMP_BYTES
    observed_limits = {"timeout_seconds": timeout, "cpu_seconds": cpu_seconds, "memory_bytes": memory_bytes, "temp_bytes": temp_bytes, "process_group": True}
    code = _crawl4ai_worker_code()
    with tempfile.TemporaryDirectory(prefix="monokl-crawl4ai-") as temp_dir:
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": os.environ.get("PYTHONPATH", ""), "HOME": temp_dir, "TMPDIR": temp_dir}

        def limit_child() -> None:
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_FSIZE, (temp_bytes, temp_bytes))
            resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))

        proc = subprocess.Popen(
            [sys.executable, "-I", "-c", code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=temp_dir,
            preexec_fn=limit_child,
        )
        try:
            stdout, stderr = proc.communicate(json.dumps(payload), timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return {"status": "error", "observed_limits": observed_limits, "error": {"code": "timeout", "message": "crawl4ai subprocess timed out and process group was killed"}}
        if proc.returncode != 0:
            return {"status": "error", "observed_limits": observed_limits, "error": {"code": "crawl4ai_subprocess_failed", "message": stderr[-1000:] or f"exit {proc.returncode}"}}
        result = json.loads(stdout)
        result["observed_limits"] = observed_limits
        return result


def _crawl4ai_worker_code() -> str:
    return textwrap.dedent(
        r'''
        import asyncio, hashlib, ipaddress, json, socket, sys
        from urllib.parse import urlparse, urlunparse

        def normalized_url(url):
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
            host = (parsed.hostname or '').lower()
            netloc = host
            if parsed.port and not ((scheme == 'http' and parsed.port == 80) or (scheme == 'https' and parsed.port == 443)):
                netloc = f'{host}:{parsed.port}'
            return urlunparse((scheme, netloc, parsed.path or '/', '', parsed.query, ''))

        def is_public(address):
            ip = ipaddress.ip_address(address)
            return ip.is_global and not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)

        def check_url(url, allowed_hosts):
            parsed = urlparse(normalized_url(url))
            if parsed.scheme not in {'http', 'https'}:
                raise RuntimeError(f'scheme_refused: {parsed.scheme or "missing"}')
            host = (parsed.hostname or '').lower()
            if not host:
                raise RuntimeError('host_required')
            allowed = tuple(h.lower() for h in allowed_hosts)
            if allowed and host not in allowed:
                raise RuntimeError(f'host_not_allowed: {host}')
            addresses = sorted({info[4][0] for info in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
            blocked = [address for address in addresses if not is_public(address)]
            if blocked:
                raise RuntimeError(f'private_or_local_address_refused: {host} -> {", ".join(blocked)}')
            return normalized_url(url)

        async def main():
            payload = json.loads(sys.stdin.read())
            budgets = payload['budgets']
            allowed_hosts = tuple(budgets.get('allowed_hosts') or [])
            url = check_url(payload['url'], allowed_hosts)
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
            browser_config = BrowserConfig(
                headless=True,
                browser_type='chromium',
                use_persistent_context=False,
                user_data_dir=None,
                proxy_config=None,
                downloads_path=None,
                ignore_https_errors=False,
                java_script_enabled=False,
                use_managed_browser=False,
                cdp_url=None,
            )
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=0,
                js_code=None,
                excluded_tags=['script', 'style'],
                scan_full_page=False,
                process_iframes=False,
                remove_overlay_elements=True,
                magic=False,
            )
            async with AsyncWebCrawler(config=browser_config) as crawler:
                strategy = getattr(crawler, 'crawler_strategy', None)
                if strategy is None or not hasattr(strategy, 'set_hook'):
                    raise RuntimeError('browser_interception_unavailable')
                async def on_page_context_created(page, context, **kwargs):
                    async def guard(route, request):
                        try:
                            check_url(request.url, allowed_hosts)
                            await route.continue_()
                        except Exception:
                            await route.abort()
                    await page.route('**/*', guard)
                    return page
                strategy.set_hook('on_page_context_created', on_page_context_created)
                result = await crawler.arun(url=url, config=run_config)
            final_url = normalized_url(getattr(result, 'url', None) or url)
            check_url(final_url, allowed_hosts)
            markdown = getattr(result, 'markdown', '') or getattr(result, 'cleaned_html', '') or ''
            body = markdown.encode('utf-8')
            status_code = getattr(result, 'status_code', None)
            success = bool(getattr(result, 'success', True))
            if not success:
                raise RuntimeError(getattr(result, 'error_message', 'crawl4ai_error'))
            print(json.dumps({'status': 'ok', 'final_url': final_url, 'http_status': status_code, 'redirects': [], 'markdown': markdown, 'content_sha256': hashlib.sha256(body).hexdigest()}, sort_keys=True))
        try:
            asyncio.run(main())
        except Exception as error:
            print(json.dumps({'status': 'error', 'error': {'code': str(error).split(':', 1)[0], 'message': str(error)}}, sort_keys=True))
        '''
    )
