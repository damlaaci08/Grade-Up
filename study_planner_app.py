from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import rich
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

app = typer.Typer(help="AP Study Planner with game-style task points")
console = Console()

data_file = Path(__file__).parent / "study_planner_data.json"

COURSE_TEMPLATES = {
    "AP Biology": {
        "topics": [
            "Cell Structure and Function",
            "Genetics and Inheritance",
            "Evolution and Natural Selection",
            "Ecology and Ecosystems",
            "Plant and Animal Physiology",
        ],
        "weekly_hours": 6,
    },
    "AP Calculus AB": {
        "topics": [
            "Limits and Continuity",
            "Derivative Rules",
            "Applications of Derivatives",
            "Integrals and Riemann Sums",
            "Fundamental Theorem of Calculus",
        ],
        "weekly_hours": 5,
    },
    "AP Calculus BC": {
        "topics": [
            "Parametric/Polar Functions",
            "Sequences and Series",
            "Taylor Polynomials",
            "Advanced Integration",
            "Differential Equations",
        ],
        "weekly_hours": 7,
    },
    "AP US History": {
        "topics": [
            "Colonial America",
            "Revolution and Constitution",
            "Civil War and Reconstruction",
            "20th Century Politics",
            "Modern U.S. Issues",
        ],
        "weekly_hours": 5,
    },
    "AP Physics 1": {
        "topics": [
            "Kinematics",
            "Newton's Laws",
            "Work and Energy",
            "Momentum",
            "Waves and Sound",
        ],
        "weekly_hours": 5,
    },
    "AP Chemistry": {
        "topics": [
            "Atomic Structure",
            "Chemical Bonding",
            "Stoichiometry",
            "Thermochemistry",
            "Equilibrium",
        ],
        "weekly_hours": 6,
    },
}

POINTS_FOR_TYPE = {
    "study": 20,
    "homework": 30,
    "review": 15,
}

LEVEL_STEP = 100


@dataclass
class Task:
    id: int
    title: str
    course: str
    task_type: str
    due_date: date
    effort: int
    points: int
    completed: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["due_date"] = self.due_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            course=data["course"],
            task_type=data["task_type"],
            due_date=datetime.fromisoformat(data["due_date"]).date(),
            effort=data["effort"],
            points=data["points"],
            completed=data["completed"],
        )


@dataclass
class PlannerState:
    courses: List[str]
    tasks: List[Task]
    points: int = 0
    created_at: str = date.today().isoformat()

    def to_dict(self) -> dict:
        return {
            "courses": self.courses,
            "tasks": [task.to_dict() for task in self.tasks],
            "points": self.points,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlannerState":
        return cls(
            courses=data.get("courses", []),
            tasks=[Task.from_dict(item) for item in data.get("tasks", [])],
            points=data.get("points", 0),
            created_at=data.get("created_at", date.today().isoformat()),
        )


def load_state() -> PlannerState:
    if data_file.exists():
        try:
            with data_file.open("r", encoding="utf-8") as handle:
                return PlannerState.from_dict(json.load(handle))
        except Exception:
            pass
    return PlannerState(courses=[], tasks=[], points=0)


def save_state(state: PlannerState) -> None:
    with data_file.open("w", encoding="utf-8") as handle:
        json.dump(state.to_dict(), handle, indent=2)


def parse_homework_input(text: str) -> List[Dict[str, str]]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        course, title = parts[0], parts[1]
        due = None
        effort = 3
        if len(parts) >= 3 and parts[2]:
            try:
                due = datetime.fromisoformat(parts[2].strip()).date()
            except ValueError:
                due = None
        if len(parts) >= 4 and parts[3].isdigit():
            effort = max(1, min(5, int(parts[3].strip())))
        items.append({"course": course, "title": title, "due": due, "effort": effort})
    return items


def create_study_plan(courses: List[str], homework_items: List[Dict[str, str]]) -> List[Task]:
    tasks: List[Task] = []
    task_id = 1
    today = date.today()
    schedule_days = 7

    for course in courses:
        template = COURSE_TEMPLATES.get(course)
        topics = template["topics"] if template else ["Review notes", "Practice problems", "Test prep"]
        weekly_hours = template["weekly_hours"] if template else 4
        study_sessions = min(len(topics), max(1, weekly_hours // 2))

        for index in range(study_sessions):
            scheduled_day = today + timedelta(days=index * (schedule_days // study_sessions))
            topic = topics[index % len(topics)]
            points = POINTS_FOR_TYPE["study"] + 5 * int(weekly_hours / 2)
            tasks.append(
                Task(
                    id=task_id,
                    title=f"Study: {course} - {topic}",
                    course=course,
                    task_type="study",
                    due_date=scheduled_day,
                    effort=3,
                    points=points,
                )
            )
            task_id += 1

    for item in homework_items:
        due = item["due"] or (today + timedelta(days=3))
        effort = item["effort"]
        base = POINTS_FOR_TYPE["homework"] + effort * 5
        tasks.append(
            Task(
                id=task_id,
                title=f"Homework: {item['title']}",
                course=item["course"],
                task_type="homework",
                due_date=due,
                effort=effort,
                points=base,
            )
        )
        task_id += 1

    extra_review = []
    for course in courses:
        review_due = today + timedelta(days=2)
        extra_review.append(
            Task(
                id=task_id,
                title=f"Review quick quiz for {course}",
                course=course,
                task_type="review",
                due_date=review_due,
                effort=2,
                points=POINTS_FOR_TYPE["review"],
            )
        )
        task_id += 1
    tasks.extend(extra_review)

    tasks.sort(key=lambda task: (task.due_date, task.task_type, task.effort), reverse=False)
    return tasks


def format_task_row(task: Task) -> List[str]:
    status = "✅" if task.completed else "⏳"
    return [str(task.id), status, task.course, task.title, task.due_date.isoformat(), str(task.effort), str(task.points)]


def show_tasks(tasks: List[Task], title: str) -> None:
    table = Table(title=title)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Done", style="green")
    table.add_column("Course", style="magenta")
    table.add_column("Task", style="white")
    table.add_column("Due", style="yellow")
    table.add_column("Effort", style="white")
    table.add_column("Points", style="bright_blue")

    for task in tasks:
        table.add_row(*format_task_row(task))

    console.print(table)


def compute_level(points: int) -> int:
    return points // LEVEL_STEP + 1


def show_status(state: PlannerState) -> None:
    level = compute_level(state.points)
    console.print(f"[bold green]Total points:[/] {state.points}")
    console.print(f"[bold blue]Current level:[/] {level}")
    remaining = LEVEL_STEP * level - state.points
    console.print(f"[bold yellow]Points until next level:[/] {remaining if remaining > 0 else 0}")
    pending = [task for task in state.tasks if not task.completed]
    completed = [task for task in state.tasks if task.completed]
    console.print(f"[bold]Courses:[/] {', '.join(state.courses) if state.courses else 'None'}")
    console.print(f"[bold]Pending tasks:[/] {len(pending)} | [bold]Completed tasks:[/] {len(completed)}")


@app.command()
def init():
    """Create a new study plan for your AP lessons and homework."""
    console.print("[bold underline]AP Study Planner Setup[/]\n")
    course_input = Prompt.ask(
        "Enter your AP lessons separated by commas (example: AP Biology, AP Calculus AB)",
        default="AP Biology, AP Calculus AB",
    )
    courses = [course.strip() for course in course_input.split(",") if course.strip()]
    if not courses:
        console.print("[red]No courses entered. Please run the command again.[/]")
        raise typer.Exit(code=1)

    console.print("\n[bold]Enter homework items. Use this format:[/] course | description | due YYYY-MM-DD | effort 1-5")
    console.print("Type a blank line to finish." )

    homework_lines: List[str] = []
    while True:
        line = Prompt.ask("Homework item", default="")
        if not line.strip():
            break
        homework_lines.append(line)

    homework_items = parse_homework_input("\n".join(homework_lines))
    tasks = create_study_plan(courses, homework_items)
    state = PlannerState(courses=courses, tasks=tasks, points=0)
    save_state(state)
    console.print("\n[bold green]Your study plan is ready![/]")
    show_tasks(state.tasks, "Weekly Task List")


@app.command()
def show():
    """Show the current task list and planner status."""
    state = load_state()
    if not state.tasks:
        console.print("[red]No plan found. Run `python study_planner.py init` first.[/]")
        raise typer.Exit(code=1)
    show_status(state)
    show_tasks(state.tasks, "Your Study Tasks")


@app.command()
def complete(task_id: int):
    """Mark one task as completed and gain points."""
    state = load_state()
    matching = [task for task in state.tasks if task.id == task_id]
    if not matching:
        console.print(f"[red]Task ID {task_id} not found.[/]")
        raise typer.Exit(code=1)
    task = matching[0]
    if task.completed:
        console.print(f"[yellow]Task {task_id} is already completed.[/]")
        raise typer.Exit(code=0)
    task.completed = True
    state.points += task.points
    save_state(state)
    console.print(f"[bold green]Great job![/] You earned [cyan]{task.points}[/] points for completing: {task.title}")
    show_status(state)


@app.command()
def daily(days: int = 7):
    """Create a daily task list for the next N days."""
    state = load_state()
    if not state.tasks:
        console.print("[red]No plan found. Run `python study_planner.py init` first.[/]")
        raise typer.Exit(code=1)
    today = date.today()
    end_date = today + timedelta(days=days)
    daily_tasks = [task for task in state.tasks if today <= task.due_date <= end_date and not task.completed]
    if not daily_tasks:
        console.print("[green]All tasks are complete or no tasks are scheduled in that window.[/]")
        raise typer.Exit(code=0)
    show_tasks(daily_tasks, f"Daily Tasks ({today.isoformat()} to {end_date.isoformat()})")


@app.command()
def reset(confirm: bool = typer.Option(False, "--confirm", help="Confirm planner reset.")):
    """Reset the planner and remove saved progress."""
    if not confirm:
        console.print("Use `--confirm` to permanently reset your study planner.")
        raise typer.Exit(code=1)
    if data_file.exists():
        data_file.unlink()
    console.print("[red]Planner reset complete.[/]")


if __name__ == "__main__":
    app()
