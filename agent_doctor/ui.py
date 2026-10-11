"""Terminal presentation for the Doctor's run."""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def banner():
    console.print(Panel.fit(
        "[bold cyan]AGENT DOCTOR[/]\n[dim]trace-driven diagnosis and repair for AI agents[/]", border_style="cyan"
    ))


def step(text: str):
    console.print(f"[cyan]>[/] {text}")


def ok(text: str):
    console.print(f"[bold green]✔[/] {text}")


def warn(text: str):
    console.print(f"[bold yellow]![/] {text}")


def round_header(n: int, total: int):
    console.rule(f"[bold]Treatment round {n}/{total}")


def exam_table(exam):
    by_case = {t.get("traceName", "").split(":", 1)[-1]: t for t in exam.traces}
    table = Table(show_edge=False, header_style="bold")
    for col in ("case", "result", "detail", "trace", "llm/tool calls"):
        table.add_column(col)
    for r in exam.results:
        t = by_case.get(r["id"], {})
        table.add_row(
            r["id"],
            "[green]PASS[/]" if r["passed"] else "[red]FAIL[/]",
            r["reason"][:70],
            (t.get("traceId") or "-")[:12],
            f"{t.get('llmCallsCount', '-')}/{t.get('toolCallsCount', '-')}",
        )
    console.print(table)
    color = "green" if exam.passed == len(exam.results) else "red"
    console.print(f"  [{color}]{exam.passed}/{len(exam.results)} passing[/], {exam.crashes} crashed, "
                  f"{len(exam.traces)} traces in neatlogs\n")


def diagnosis(plan: dict):
    evidence = "\n".join(f"  • {e}" for e in plan.get("evidence", []))
    console.print(Panel(
        f"[bold]{plan['diagnosis']}[/]\n\n{plan['root_cause']}\n\n[dim]Evidence from traces:[/]\n{evidence}",
        title="Diagnosis", border_style="magenta",
    ))


def patch(edits: list[dict]):
    for e in edits:
        console.print(f"[bold]Patching {e['file']}[/]")
        for line in e["find"].splitlines():
            console.print(f"[red]- {line}[/]", highlight=False)
        for line in e["replace"].splitlines():
            console.print(f"[green]+ {line}[/]", highlight=False)


def summary(first, last):
    color = "green" if last.passed == len(last.results) else "yellow"
    console.print(Panel.fit(
        f"[bold {color}]{first.passed}/{len(first.results)} -> {last.passed}/{len(last.results)} passing[/]\n"
        f"crashes {first.crashes} -> {last.crashes}",
        title="Discharge summary", border_style=color,
    ))
