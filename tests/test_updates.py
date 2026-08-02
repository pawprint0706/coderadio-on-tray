from __future__ import annotations

import coderadio_tray.updates as updates


def test_version_comparison() -> None:
    assert updates.is_newer_version("v0.5.0", "0.4.3")
    assert updates.is_newer_version("0.4.10", "0.4.9")
    assert not updates.is_newer_version("v0.4.3", "0.4.3")
    assert not updates.is_newer_version("invalid", "0.4.3")


def test_fetch_latest_release_uses_github_payload(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, str]:
            return {
                "tag_name": "v0.5.0",
                "html_url": "https://github.com/example/releases/tag/v0.5.0",
            }

    monkeypatch.setattr(updates.httpx, "get", lambda *_args, **_kwargs: Response())

    release = updates.fetch_latest_release()

    assert release.version == "0.5.0"
    assert release.url.endswith("/v0.5.0")
