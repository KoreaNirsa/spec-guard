from __future__ import annotations

from dataclasses import dataclass, field


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
        print(f"[{status}] {self.name}")
        for message in self.messages:
            print(f"- {message}")
        if self.next_steps:
            print("")
            print("Next steps:")
            for step in self.next_steps:
                print(f"- {step}")
