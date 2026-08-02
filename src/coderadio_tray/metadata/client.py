from __future__ import annotations

from dataclasses import dataclass

import httpx

from coderadio_tray.config import NOWPLAYING_URL, USER_AGENT


def _clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() == "unknown" else text


def _split_song_text(text: str) -> tuple[str, str]:
    """Extract missing fields from AzuraCast's conventional display text."""
    for separator in (" — ", " – ", " - "):
        if separator in text:
            artist, title = text.split(separator, 1)
            return _clean(artist), _clean(title)
    return "", ""


@dataclass(frozen=True)
class TrackInfo:
    title: str = "Unknown"
    artist: str = "Unknown"
    album: str = ""
    art_url: str = ""
    text: str = "Unknown"

    @property
    def display(self) -> str:
        artist = _clean(self.artist)
        title = _clean(self.title)
        if artist and title:
            return f"{artist} — {title}"
        if title:
            return title
        if artist:
            return artist

        text = _clean(self.text)
        if text[:1] in {"-", "—", "–"}:
            text = text[1:].strip()
        return text or "Unknown"


@dataclass(frozen=True)
class StationSnapshot:
    is_online: bool
    track: TrackInfo
    stream_128: str
    stream_64: str
    listen_url: str
    listeners_current: int = 0

    def stream_for_bitrate(self, bitrate: str) -> str:
        if bitrate == "64" and self.stream_64:
            return self.stream_64
        return self.stream_128 or self.listen_url


def _song_from(payload: dict | None) -> TrackInfo:
    song = (payload or {}).get("song") or {}
    text = _clean(song.get("text"))
    artist = _clean(song.get("artist"))
    title = _clean(song.get("title"))
    text_artist, text_title = _split_song_text(text)
    artist = artist or text_artist
    title = title or text_title
    return TrackInfo(
        title=title or "Unknown",
        artist=artist or "Unknown",
        album=_clean(song.get("album")),
        art_url=_clean(song.get("art")),
        text=text or "Unknown",
    )


def _mount_url(station: dict, prefer_low: bool) -> str:
    mounts = station.get("mounts") or []
    for mount in mounts:
        name = str(mount.get("name") or "").lower()
        url = str(mount.get("url") or "")
        if not url:
            continue
        if prefer_low and ("64" in name or "low" in name):
            return url
        if not prefer_low and mount.get("is_default"):
            return url
    for mount in mounts:
        url = str(mount.get("url") or "")
        if url:
            return url
    return str(station.get("listen_url") or "")


class MetadataClient:
    def __init__(self, url: str = NOWPLAYING_URL, timeout: float = 10.0) -> None:
        self._url = url
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def fetch(self) -> StationSnapshot:
        response = self._client.get(self._url)
        response.raise_for_status()
        data = response.json()
        station = data.get("station") or {}
        now = data.get("now_playing") or {}
        listeners = data.get("listeners") or {}
        try:
            listeners_current = max(0, int(listeners.get("current") or 0))
        except (TypeError, ValueError):
            listeners_current = 0
        return StationSnapshot(
            is_online=bool(data.get("is_online", True)),
            track=_song_from(now),
            stream_128=_mount_url(station, prefer_low=False),
            stream_64=_mount_url(station, prefer_low=True),
            listen_url=str(station.get("listen_url") or ""),
            listeners_current=listeners_current,
        )
