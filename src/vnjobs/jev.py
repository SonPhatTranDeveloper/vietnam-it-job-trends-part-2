"""Client and resumable cache for Jev (TypeSafe, ``jev-latest``), shared by the Jev steps.

Jev answers a *choice question* from a short piece of text. Steps 04 (is it a tech job) and 06
(which role) both send only a job title and cache every answer in a JSONL file, so a stopped
run loses nothing and a re-run never pays twice for the same title.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from tqdm import tqdm

from vnjobs.common import PROJECT_ROOT

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
COST_PER_CALL = 0.000022  # dollars, from part 1's own estimate
MAX_ATTEMPTS = 5
REQUEST_TIMEOUT_S = 60
RETRY_STATUS = {429, 500, 502, 503, 504}
CACHE_LOCK = threading.Lock()  # workers append to one file from many threads


def load_key() -> str:
    """Read the TypeSafe API key from the environment or ``.env.local``.

    Returns:
        The API key.

    Raises:
        SystemExit: If no key is configured.
    """
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    env_file = PROJECT_ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.strip().partition("=")
            if name == "TYPESAFE_API_KEY" and value:
                return value
    sys.exit("No TYPESAFE_API_KEY (environment or .env.local)")


def request_once(body: bytes, key: str, question: str) -> dict[str, Any]:
    """Send one request to Jev.

    Args:
        body: The JSON request body.
        key: The API key.
        question: Name of the question whose answer to return.

    Returns:
        Jev's answer to that question (``choice`` and ``confidence``).
    """
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    request = urllib.request.Request(ENDPOINT, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        return json.load(response)["answers"][question]


def is_retryable(error: Exception) -> bool:
    """Say whether a failed request is worth retrying.

    Args:
        error: The exception raised by the request.

    Returns:
        True for network errors and for rate-limit / server-side HTTP statuses.
    """
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRY_STATUS
    return isinstance(error, urllib.error.URLError)


def ask(title: str, questions: dict[str, Any], question: str, key: str) -> dict[str, Any]:
    """Ask Jev one question about a title, retrying with exponential backoff.

    Args:
        title: The cleaned job title (the only thing Jev sees).
        questions: The ``questions`` object of the request.
        question: Which question in ``questions`` to read the answer of.
        key: The API key.

    Returns:
        Jev's answer.

    Raises:
        Exception: The last error, once it is not retryable or attempts run out.
    """
    payload = {"model": MODEL, "state": f"Title: {title}", "questions": questions}
    body = json.dumps(payload).encode()
    for attempt in range(MAX_ATTEMPTS):
        try:
            return request_once(body, key, question)
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            if not is_retryable(error) or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(2**attempt)  # 1s, 2s, 4s, 8s
    raise RuntimeError("unreachable")  # pragma: no cover


def read_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Load every answered title from a cache file.

    Args:
        path: The JSONL cache file.

    Returns:
        A mapping from lower-cased cleaned title to its cached answer.
    """
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return cache
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line cut short by a kill; that title is simply asked again
        cache[record["title_key"]] = record
    return cache


def append_cache(path: Path, record: dict[str, Any]) -> None:
    """Append one answer to a cache file, safely from many threads.

    Args:
        path: The JSONL cache file.
        record: ``{title_key, title, label, conf}``.
    """
    with CACHE_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def classify_title(
    item: tuple[str, str], questions: dict[str, Any], question: str, cache_path: Path, key: str
) -> None:
    """Ask Jev about one title and cache the answer; failures are logged, not cached.

    Args:
        item: ``(title_key, title)``.
        questions: The ``questions`` object of the request.
        question: Which question's answer to cache.
        cache_path: The JSONL cache file.
        key: The API key.
    """
    title_key, title = item
    try:
        answer = ask(title, questions, question, key)
    except Exception as error:
        print(f"\nfailed: {title!r}: {error}", file=sys.stderr)
        return
    record = {
        "title_key": title_key,
        "title": title,
        "label": answer.get("choice"),
        "conf": float(answer.get("confidence") or 0),
    }
    append_cache(cache_path, record)


def run_calls(
    todo: list[tuple[str, str]],
    questions: dict[str, Any],
    question: str,
    cache_path: Path,
    workers: int,
) -> None:
    """Classify every pending title in parallel, with a progress bar.

    Args:
        todo: ``(title_key, title)`` pairs to ask Jev about.
        questions: The ``questions`` object of the request.
        question: Which question's answer to cache.
        cache_path: The JSONL cache file.
        workers: How many requests to run in parallel.
    """
    key = load_key()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    def one(item: tuple[str, str]) -> None:
        classify_title(item, questions, question, cache_path, key)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(tqdm(pool.map(one, todo), total=len(todo)))
    elapsed = time.time() - started
    print(f"{len(todo)} calls in {elapsed:.0f}s ({len(todo) / max(elapsed, 1e-9):.1f}/s)")
