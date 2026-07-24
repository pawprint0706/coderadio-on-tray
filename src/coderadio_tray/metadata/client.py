from __future__ import annotations

from dataclasses import dataclass

import httpx

from coderadio_tray.config import NOWPLAYING_URL, USER_AGENT


@dataclass(frozen=True)
class TrackInfo:
    title: str = "Unknown"
    artist: str = "Unknown"
    album: str = ""
    art_url: str = ""
    text: str = "Unknown"

    @property
    def display(self) -> str:
        if self.artist and self.artist != "Unknown" and self.title:
            return f"{self.artist} — {self.title}"
        return self.text or self.title or "Unknown"


@dataclass(frozen=True)
class StationSnapshot:
    is_online: bool
    track: TrackInfo
    stream_128: str
    stream_64: str
    listen_url: str

    def stream_for_bitrate(self, bitrate: str) -> str:
        if bitrate == "64" and self.stream_64:
            return self.stream_64
        return self.stream_128 or self.listen_url


def _song_from(payload: dict | None) -> TrackInfo:
    song = (payload or {}).get("song") or {}
    return TrackInfo(
        title=str(song.get("title") or "Unknown"),
        artist=str(song.get("artist") or "Unknown"),
        album=str(song.get("album") or ""),
        art_url=str(song.get("art") or ""),
        text=str(song.get("text") or ""),
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
        return StationSnapshot(
            is_online=bool(data.get("is_online", True)),
            track=_song_from(now),
            stream_128=_mount_url(station, prefer_low=False),
            stream_64=_mount_url(station, prefer_low=True),
            listen_url=str(station.get("listen_url") or ""),
        )
