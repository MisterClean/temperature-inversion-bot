from __future__ import annotations

import logging

from atproto import Client

from temp_inversion_bot.retry import RetryError, retry_call


class BlueskyPublisher:
    def __init__(
        self,
        *,
        handle: str,
        app_password: str,
        service_url: str = "https://bsky.social",
        attempts: int = 2,
        logger: logging.Logger | None = None,
    ) -> None:
        self._handle = handle
        self._app_password = app_password
        self._service_url = service_url
        self._attempts = attempts
        self._logger = logger or logging.getLogger(__name__)
        self._client: Client | None = None

    def publish(self, text: str) -> str | None:
        def _send() -> str | None:
            client = self._ensure_client()
            response = client.send_post(text=text)
            uri = getattr(response, "uri", None)
            self._logger.info("Bluesky post created: uri=%s", uri)
            return uri

        try:
            return retry_call(
                _send,
                attempts=self._attempts,
                exceptions=(Exception,),
                logger=self._logger,
                context="bluesky publish",
            )
        except RetryError:
            raise

    def _ensure_client(self) -> Client:
        if self._client is not None:
            return self._client

        client = Client(base_url=self._service_url)
        client.login(self._handle, self._app_password)
        self._client = client
        self._logger.info("Authenticated Bluesky client for %s", self._handle)
        return client
