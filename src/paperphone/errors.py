from __future__ import annotations


class PaperphoneError(Exception):
    """Base class for errors that the CLI reports without a traceback."""

    exit_code = 1


class ConfigError(PaperphoneError):
    exit_code = 2


class UsageError(PaperphoneError):
    exit_code = 2


class RuntimeFailure(PaperphoneError):
    exit_code = 1
