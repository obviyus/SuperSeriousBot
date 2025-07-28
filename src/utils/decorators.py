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


def description(desc: str) -> Callable[[F], F]:
    return _add_attribute("description", desc)


def usage(usage_doc: str) -> Callable[[F], F]:
    return _add_attribute("usage", usage_doc)


def example(example_doc: str) -> Callable[[F], F]:
    return _add_attribute("example", example_doc)


def api_key(name: str) -> Callable[[F], F]:
    return _add_attribute("api_key_name", name)


def deprecated(message: str) -> Callable[[F], F]:
    return _add_attribute("deprecated", message)
