from functools import wraps
from typing import Any, Callable, List, TypeVar, Union, cast

F = TypeVar("F", bound=Callable[..., Any])


def triggers(trigger_command: Union[str, List[str]]):
    """Trigger decorator for commands.

    :param trigger_command: The command trigger(s) for the command.
    :return: The decorated function.
    """
    if isinstance(trigger_command, str):
        trigger_command = [trigger_command]

    if not isinstance(trigger_command, list):
        raise TypeError(
            f"Triggers must be a string or a list of strings, not {type(trigger_command)}"
        )

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.triggers = trigger_command  # type: ignore
        return cast(F, wrapper)

    return decorator


def _add_attribute(attr_name: str, attr_value: str):
    """Generic decorator for adding attributes to functions."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        setattr(wrapper, attr_name, attr_value)
        return cast(F, wrapper)

    return decorator


description = lambda desc: _add_attribute("description", desc)
usage = lambda usage_doc: _add_attribute("usage", usage_doc)
example = lambda example_doc: _add_attribute("example", example_doc)
api_key = lambda name: _add_attribute("api_key_name", name)
deprecated = lambda message: _add_attribute("deprecated", message)

# Type hints for the decorators
description.__annotations__["return"] = Callable[[F], F]
usage.__annotations__["return"] = Callable[[F], F]
example.__annotations__["return"] = Callable[[F], F]
api_key.__annotations__["return"] = Callable[[F], F]
deprecated.__annotations__["return"] = Callable[[F], F]
