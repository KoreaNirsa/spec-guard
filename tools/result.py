from __future__ import annotations

from dataclasses import dataclass, field

from tools.ux import bold, cyan, green, red, yellow


@dataclass
class CheckResult:
    name: str
    ok: bool = True
    messages: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    details: dict[str, int] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        self.ok = False
        self.messages.append(message)

    def add_info(self, message: str) -> None:
        self.messages.append(message)

    def add_next_step(self, message: str) -> None:
        self.next_steps.append(message)

    def print(self) -> None:
        status = "PASS" if self.ok else "FAIL"
        status_line = f"[{status}] {self.name}"
        print(green(bold(status_line)) if self.ok else red(bold(status_line)))
        for message in self.messages:
            line = f"- {message}"
            if "[READY]" in message:
                print(green(line))
            elif "[NOT READY]" in message or "Blocked by" in message:
                print(red(line))
            elif message.startswith("Generated") or message.startswith("Reused") or message.startswith("Prepared"):
                print(cyan(line))
            elif message.startswith("Kept"):
                print(yellow(line))
            else:
                print(line)
        if self.next_steps:
            print("")
            print(bold("Next steps:"))
            for step in self.next_steps:
                print(yellow(f"- {step}"))
