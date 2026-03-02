"""Shared utilities for Sentinel."""


def mask_key(key: str) -> str:
    """Mask API key showing only prefix and last 4 chars. e.g., 'sk-s...x4f2'"""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"
