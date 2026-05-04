from __future__ import annotations

import os


LOGO = r"""
  ____                  ____                     _
 / ___| _ __   ___  ___/ ___|_   _  __ _ _ __ __| |
 \___ \| '_ \ / _ \/ __| |  _| | | |/ _` | '__/ _` |
  ___) | |_) |  __/ (__| |_| | |_| | (_| | | | (_| |
 |____/| .__/ \___|\___|\____|\__,_|\__,_|_|  \__,_|
       |_|
"""


def _color(code: str, text: str) -> str:
    if os.getenv("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return _color("1", text)


def dim(text: str) -> str:
    return _color("2", text)


def cyan(text: str) -> str:
    return _color("36", text)


def blue(text: str) -> str:
    return _color("34", text)


def yellow(text: str) -> str:
    return _color("33", text)


def green(text: str) -> str:
    return _color("32", text)


def red(text: str) -> str:
    return _color("31", text)


def print_banner(subtitle: str | None = None) -> None:
    print(cyan(LOGO.strip("\n")))
    print(dim("Spec-first validation for AI-assisted implementation."))
    if subtitle:
        print(bold(subtitle))
    print("")


def print_section(title: str) -> None:
    print("")
    print(cyan(bold(f"== {title} ==")))


def print_hint(message: str) -> None:
    print(blue(f"> {message}"))


def print_success(message: str) -> None:
    print(green(message))


def print_warning(message: str) -> None:
    print(yellow(message))


def print_error(message: str) -> None:
    print(red(message))


def menu_item(text: str) -> str:
    return cyan(text)
