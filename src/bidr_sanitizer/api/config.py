from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit


DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 50_000_000


@dataclass(frozen=True, slots=True)
class WebAPISettings:
    """Security and resource limits for one API process."""

    api_token: str = field(repr=False)
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    allowed_origins: tuple[str, ...] = ()
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS

    def __post_init__(self) -> None:
        if (
            not isinstance(self.api_token, str)
            or len(self.api_token) < 32
            or not self.api_token.isascii()
            or any(character.isspace() for character in self.api_token)
        ):
            raise ValueError(
                "api_token must contain at least 32 non-whitespace ASCII characters."
            )

        if isinstance(self.allowed_hosts, (str, bytes)):
            raise TypeError("allowed_hosts must be a sequence of host names.")
        hosts = tuple(self.allowed_hosts)
        if not hosts or any(
            not isinstance(host, str) or not host or "://" in host
            for host in hosts
        ):
            raise ValueError("allowed_hosts must contain host names without schemes.")
        object.__setattr__(self, "allowed_hosts", hosts)

        if isinstance(self.allowed_origins, (str, bytes)):
            raise TypeError("allowed_origins must be a sequence of origins.")
        normalized_origins: list[str] = []
        for origin in self.allowed_origins:
            if not isinstance(origin, str):
                raise TypeError("allowed_origins must contain strings.")
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "allowed_origins must contain complete HTTP(S) origins."
                )
            normalized_origins.append(f"{parsed.scheme}://{parsed.netloc}")
        object.__setattr__(self, "allowed_origins", tuple(normalized_origins))

        for field_name in ("max_upload_bytes", "max_image_pixels"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer.")
