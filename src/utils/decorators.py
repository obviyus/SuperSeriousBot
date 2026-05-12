from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Protocol, cast


@dataclass(slots=True)
class CommandMeta:
    triggers: list[str]
    usage: str
    example: str
    description: str
    api_key: str | None = None


type CommandFunc = Callable[..., Coroutine[object, object, None]]


class CommandWithMeta(Protocol):
    command_meta: CommandMeta


_registered_commands: list[CommandFunc] = []


def get_command_meta(func: CommandFunc) -> CommandMeta:
    meta = getattr(func, "command_meta", None)
    if meta is None:
        module_name = getattr(func, "__module__", func.__class__.__module__)
        command_name = getattr(func, "__name__", func.__class__.__name__)
        raise RuntimeError(f"{module_name}.{command_name} is not a decorated command.")
    return meta


def get_registered_commands() -> list[CommandFunc]:
    return list(_registered_commands)


def command(
    *,
    triggers: str | list[str],
    usage: str,
    example: str,
    description: str,
    api_key: str | None = None,
) -> Callable[[CommandFunc], CommandFunc]:
    if isinstance(triggers, str):
        normalized_triggers = [triggers]
    elif isinstance(triggers, list) and all(
        isinstance(trigger, str) and trigger for trigger in triggers
    ):
        normalized_triggers = triggers
    else:
        raise TypeError(
            "Triggers must be a non-empty string or list of non-empty strings."
        )

    def decorator(func: CommandFunc) -> CommandFunc:
        cast(CommandWithMeta, func).command_meta = CommandMeta(
            triggers=normalized_triggers,
            usage=usage,
            example=example,
            description=description,
            api_key=api_key,
        )
        if func not in _registered_commands:
            _registered_commands.append(func)
        return func

    return decorator
