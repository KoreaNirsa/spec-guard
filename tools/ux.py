from __future__ import annotations


LOGO = r"""
  ____                  ____                     _
 / ___| _ __   ___  ___/ ___|_   _  __ _ _ __ __| |
 \___ \| '_ \ / _ \/ __| |  _| | | |/ _` | '__/ _` |
  ___) | |_) |  __/ (__| |_| | |_| | (_| | | | (_| |
 |____/| .__/ \___|\___|\____|\__,_|\__,_|_|  \__,_|
       |_|
"""


def print_banner(subtitle: str | None = None) -> None:
    print(LOGO.strip("\n"))
    print("Spec-first validation for AI-assisted implementation.")
    if subtitle:
        print(subtitle)
    print("")


def print_section(title: str) -> None:
    print("")
    print(f"== {title} ==")


def print_hint(message: str) -> None:
    print(f"> {message}")


def green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def red(text: str) -> str:
    return f"\033[31m{text}\033[0m"
