from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from coderadio_tray.config import LATEST_RELEASE_API, RELEASES_URL, USER_AGENT


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    url: str


def version_key(version: str) -> tuple[int, ...]:
    match = re.match(r"^v?(\d+(?:\.\d+)*)", version.strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_key = version_key(candidate)
    current_key = version_key(current)
    return bool(candidate_key and current_key and candidate_key > current_key)


def fetch_latest_release(timeout: float = 10.0) -> ReleaseInfo:
    response = httpx.get(
        LATEST_RELEASE_API,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    payload = response.json()
    tag = str(payload.get("tag_name") or "").strip()
    if not version_key(tag):
        raise ValueError("Latest GitHub release has no valid version tag")
    return ReleaseInfo(
        version=tag.removeprefix("v"),
        url=str(payload.get("html_url") or RELEASES_URL),
    )
