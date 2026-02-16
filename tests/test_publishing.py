from __future__ import annotations

from temp_inversion_bot.publishing.bluesky import BlueskyPublisher
from temp_inversion_bot.publishing.dry_run import DryRunPublisher


def test_dry_run_publisher_returns_uri() -> None:
    publisher = DryRunPublisher()
    uri = publisher.publish("hello")
    assert uri is not None
    assert uri.startswith("dry-run://")


def test_bluesky_publisher_uses_client_login_and_send(monkeypatch) -> None:  # noqa: ANN001
    events: list[tuple[str, str]] = []

    class FakeResponse:
        uri = "at://did:plc:123/app.bsky.feed.post/abc"

    class FakeClient:
        def __init__(self, base_url: str) -> None:
            events.append(("init", base_url))

        def login(self, handle: str, password: str) -> None:
            events.append(("login", f"{handle}:{password}"))

        def send_post(self, text: str):
            events.append(("send_post", text))
            return FakeResponse()

    monkeypatch.setattr("temp_inversion_bot.publishing.bluesky.Client", FakeClient)

    publisher = BlueskyPublisher(handle="bot.bsky.social", app_password="app-pass")
    uri = publisher.publish("test post")

    assert uri == "at://did:plc:123/app.bsky.feed.post/abc"
    assert ("login", "bot.bsky.social:app-pass") in events
    assert ("send_post", "test post") in events
