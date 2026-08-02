from __future__ import annotations

from coderadio_tray.metadata.client import MetadataClient, TrackInfo, _song_from


def test_track_display_with_artist_and_title() -> None:
    track = TrackInfo(artist="  Artist  ", title="  Title  ")

    assert track.display == "Artist — Title"


def test_track_display_uses_title_without_leading_separator_when_artist_is_missing() -> None:
    track = _song_from(
        {
            "song": {
                "artist": "",
                "title": "fly",
                "text": " - fly",
            }
        }
    )

    assert track.artist == "Unknown"
    assert track.display == "fly"


def test_track_display_treats_whitespace_artist_as_missing() -> None:
    track = TrackInfo(artist="   ", title="Song", text=" - Song")

    assert track.display == "Song"


def test_song_parser_can_recover_missing_artist_from_text() -> None:
    track = _song_from(
        {
            "song": {
                "artist": "",
                "title": "Funkaholic",
                "text": "Flitz&Suppe - Funkaholic",
            }
        }
    )

    assert track.artist == "Flitz&Suppe"
    assert track.title == "Funkaholic"
    assert track.display == "Flitz&Suppe — Funkaholic"


def test_track_text_fallback_removes_orphaned_leading_separator() -> None:
    track = TrackInfo(artist="Unknown", title="Unknown", text=" — Untagged track")

    assert track.display == "Untagged track"


def test_empty_song_falls_back_to_unknown() -> None:
    track = _song_from(None)

    assert track.display == "Unknown"


def test_metadata_client_reads_current_listener_count() -> None:
    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "is_online": True,
                "station": {"listen_url": "https://example/radio.mp3"},
                "now_playing": {"song": {"artist": "Artist", "title": "Title"}},
                "listeners": {"current": 321},
            }

    class Client:
        def get(self, _url: str) -> Response:
            return Response()

    client = MetadataClient.__new__(MetadataClient)
    client._url = "https://example/api"
    client._client = Client()

    snapshot = client.fetch()

    assert snapshot.listeners_current == 321
