"""Shared filesystem paths for Claude Chakra configuration.

The managed config directory was renamed from ``~/.fcc`` to ``~/.chakra``.
:func:`legacy_env_paths` still surfaces the old location so a one-time copy
runs at startup (see ``cli.entrypoints._migrate_legacy_env_if_missing``).
"""

from pathlib import Path

CHAKRA_CONFIG_DIRNAME = ".chakra"
CHAKRA_ENV_FILENAME = ".env"
LEGACY_FCC_CONFIG_DIRNAME = ".fcc"
LEGACY_REPO_DIRNAME = "free-claude-code"
LEGACY_XDG_CONFIG_DIRNAME = ".config"
CLAUDE_WORKSPACE_DIRNAME = "agent_workspace"
CHAKRA_LOGS_DIRNAME = "logs"
SERVER_LOG_FILENAME = "server.log"

# Backwards-compatible aliases (kept so external imports and tests do not break).
FCC_CONFIG_DIRNAME = CHAKRA_CONFIG_DIRNAME
FCC_ENV_FILENAME = CHAKRA_ENV_FILENAME
FCC_LOGS_DIRNAME = CHAKRA_LOGS_DIRNAME


def config_dir_path() -> Path:
    """Return the default user config directory (``~/.chakra``)."""

    return Path.home() / CHAKRA_CONFIG_DIRNAME


def managed_env_path() -> Path:
    """Return the default user-managed env file path."""

    return config_dir_path() / CHAKRA_ENV_FILENAME


def legacy_env_paths() -> tuple[Path, ...]:
    """Return env paths that can be migrated to ``~/.chakra/.env``.

    Ordered most-recent-format first. Migration consumes the first existing
    file in this tuple, so a stale ``~/.fcc/.env`` will be copied over.
    """

    home = Path.home()
    return (
        home / LEGACY_FCC_CONFIG_DIRNAME / CHAKRA_ENV_FILENAME,
        home / LEGACY_REPO_DIRNAME / CHAKRA_ENV_FILENAME,
        home / LEGACY_XDG_CONFIG_DIRNAME / LEGACY_REPO_DIRNAME / CHAKRA_ENV_FILENAME,
    )


def default_claude_workspace_path() -> Path:
    """Return the default Claude workspace path."""

    return config_dir_path() / CLAUDE_WORKSPACE_DIRNAME


def server_log_path() -> Path:
    """Return the canonical server log path."""

    return config_dir_path() / CHAKRA_LOGS_DIRNAME / SERVER_LOG_FILENAME
