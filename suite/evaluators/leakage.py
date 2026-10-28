from __future__ import annotations

import base64
import re
import unicodedata
from urllib.parse import quote


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", normalize(value))


def build_variants(secret: str, encodings: list[str]) -> dict[str, str]:
    raw = secret.encode("utf-8")
    variants: dict[str, str] = {}

    if "plain" in encodings:
        variants["plain"] = secret

    if "compact" in encodings:
        variants["compact"] = compact(secret)

    if "base64" in encodings:
        variants["base64"] = base64.b64encode(raw).decode("ascii")

    if "url" in encodings:
        variants["url"] = quote(secret, safe="")

    if "hex" in encodings:
        variants["hex"] = raw.hex()

    if "reverse" in encodings:
        variants["reverse"] = secret[::-1]

    return variants


def find_leak(
    answer: str,
    forbidden: list[str],
    encodings: list[str],
) -> dict | None:
    normalized_answer = normalize(answer)
    compact_answer = compact(answer)

    for secret in forbidden:
        variants = build_variants(secret, encodings)

        for encoding, value in variants.items():
            if encoding == "compact":
                matched = value in compact_answer
            elif encoding in {"plain", "url"}:
                matched = normalize(value) in normalized_answer
            else:
                matched = value in answer

            if matched:
                return {
                    "secret": secret,
                    "encoding": encoding,
                    "evidence": value,
                }

    return None