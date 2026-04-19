from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast


@dataclass(slots=True)
class CommandMeta:
    triggers: list[str] | None = None
    usage: str | None = None
    example: str | None = None
    description: str | None = None
    api_key: str | None = None
    deprecated: str | None = None


type CommandFunc = Callable[..., Any]


class CommandWithMeta(Protocol):
    command_meta: CommandMeta | None


_registered_commands: list[CommandFunc] = []


def get_command_meta(func: CommandFunc) -> CommandMeta | None:
    return getattr(func, "command_meta", None)


def _ensure_command_meta(func: CommandFunc) -> CommandMeta:
    meta = get_command_meta(func)
    if meta is None:
        meta = CommandMeta()
        cast(CommandWithMeta, func).command_meta = meta
    return meta


def _set_command_attr(func: CommandFunc, attr_name: str, attr_value: Any) -> None:
    setattr(func, attr_name, attr_value)
    meta = _ensure_command_meta(func)
    if hasattr(meta, attr_name):
        setattr(meta, attr_name, attr_value)


def _register_command(func: CommandFunc) -> None:
    if func not in _registered_commands:
        _registered_commands.append(func)


def get_registered_commands() -> list[CommandFunc]:
    return list(_registered_commands)


def _normalize_triggers(trigger_command: str | list[str]) -> list[str]:
    if isinstance(trigger_command, str):
        return [trigger_command]

    if not isinstance(trigger_command, list) or not all(
        isinstance(trigger, str) and trigger for trigger in trigger_command
    ):
        raise TypeError(
            "Triggers must be a non-empty string or list of non-empty strings."
        )

    return trigger_command


def command(
    *,
    triggers: str | list[str],
    usage: str,
    example: str,
    description: str,
    api_key: str | None = None,
    deprecated: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach all command metadata in one decorator."""
    normalized_triggers = _normalize_triggers(triggers)

    def decorator(func: CommandFunc) -> CommandFunc:
        _set_command_attr(func, "triggers", normalized_triggers)
        _set_command_attr(func, "usage", usage)
        _set_command_attr(func, "example", example)
        _set_command_attr(func, "description", description)
        if api_key:
            _set_command_attr(func, "api_key", api_key)
        if deprecated:
            _set_command_attr(func, "deprecated", deprecated)
        _register_command(func)
        return func

    return decorator
