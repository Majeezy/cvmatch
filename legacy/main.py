"""
Job Application Assistant — CLI entry point.

Usage:
    python scripts/main.py --job job_descriptions/acme_engineer.txt
    python scripts/main.py --job job_descriptions/acme_engineer.pdf --cv master_cv/my_cv.docx
    python scripts/main.py --list
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

console = Console()


def find_cv() -> Path:
    """Auto-detect a CV file in master_cv/. Prompts if multiple exist."""
    from config import MASTER_CV_DIR

    candidates = list(MASTER_CV_DIR.glob("*.pdf")) + list(MASTER_CV_DIR.glob("*.docx"))
    if not candidates:
        console.print(
            "[red]No CV found in master_cv/. Add your CV (.pdf or .docx) and try again.[/red]"
        )
        sys.exit(1)
    if len(candidates) == 1:
        return candidates[0]

    console.print("[yellow]Multiple CVs found:[/yellow]")
    for i, p in enumerate(candidates):
        console.print(f"  [{i}] {p.name}")
    choice = int(Prompt.ask("Choose CV index", default="0"))
    return candidates[choice]


def run_pipeline(job_path: Path, cv_path: Path | None) -> None:
    from scripts.extract import extract_text
    from scripts.analyzer import analyze_job
    from scripts.tailor_cv import tailor_cv, save_tailored_cv
    from scripts.cover_letter import generate_cover_letter, save_cover_letter
    from scripts.tracker import add_application

    console.rule("[bold blue]Job Application Assistant[/bold blue]")

    # 1. Resolve CV
    if cv_path is None:
        cv_path = find_cv()
    console.print(f"[dim]CV:[/dim] {cv_path.name}")

    # 2. Extract text
    with console.status("Extracting job description..."):
        job_text = extract_text(job_path)
    console.print(f"[green]✓[/green] Job description extracted ({len(job_text.split())} words)")

    with console.status("Extracting CV text..."):
        cv_text = extract_text(cv_path)
    console.print(f"[green]✓[/green] CV extracted ({len(cv_text.split())} words)")

    # 3. Analyze job
    with console.status("Analyzing job requirements (Claude)..."):
        job_analysis = analyze_job(job_text)

    title = job_analysis.get("title", "Unknown Role")
    company = job_analysis.get("company") or "Unknown Company"
    keywords = job_analysis.get("keywords", [])
    required = job_analysis.get("required_skills", [])

    console.print(Panel(
        f"[bold]{title}[/bold] @ [bold cyan]{company}[/bold cyan]\n"
        f"[dim]Seniority:[/dim] {job_analysis.get('seniority_level', 'N/A')}\n"
        f"[dim]Required:[/dim] {', '.join(required[:6])}{'...' if len(required) > 6 else ''}\n"
        f"[dim]Keywords:[/dim] {', '.join(keywords[:8])}{'...' if len(keywords) > 8 else ''}",
        title="Job Analysis",
        border_style="blue",
    ))

    # 4. Confirm / correct details
    title = Prompt.ask("Job title (confirm or edit)", default=title)
    company = Prompt.ask("Company name (confirm or edit)", default=company)
    applicant_name = Prompt.ask("Your full name (for cover letter)", default="")

    # Update analysis with confirmed values
    job_analysis["title"] = title
    job_analysis["company"] = company

    # 5. Tailor CV
    with console.status("Tailoring CV (Claude)..."):
        tailored_text = tailor_cv(cv_text, job_analysis)
    cv_out = save_tailored_cv(tailored_text, title, company)
    console.print(f"[green]✓[/green] Tailored CV saved → [cyan]{cv_out}[/cyan]")

    # 6. Cover letter
    if Confirm.ask("Generate cover letter?", default=True):
        with console.status("Generating cover letter (Claude)..."):
            letter_text = generate_cover_letter(cv_text, job_analysis)
        cl_out = save_cover_letter(letter_text, title, company, applicant_name)
        console.print(f"[green]✓[/green] Cover letter saved → [cyan]{cl_out}[/cyan]")
    else:
        cl_out = None

    # 7. Update tracker
    add_application({
        "company": company,
        "job_title": title,
        "seniority_level": job_analysis.get("seniority_level", ""),
        "cv_path": str(cv_out),
        "cover_letter_path": str(cl_out) if cl_out else "",
        "job_description_path": str(job_path),
    })
    console.print(f"[green]✓[/green] Application tracker updated")
    console.rule("[bold green]Done![/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Job Application Assistant — tailor your CV and generate cover letters"
    )
    parser.add_argument(
        "--job", type=Path, help="Path to job description file (.txt, .pdf)"
    )
    parser.add_argument(
        "--cv", type=Path, default=None, help="Path to your CV (.pdf, .docx). Auto-detected if omitted."
    )
    parser.add_argument(
        "--list", action="store_true", help="List all tracked applications"
    )
    args = parser.parse_args()

    if args.list:
        from scripts.tracker import list_applications
        list_applications()
        return

    if not args.job:
        parser.print_help()
        sys.exit(1)

    if not args.job.exists():
        console.print(f"[red]Job description file not found: {args.job}[/red]")
        sys.exit(1)

    run_pipeline(args.job, args.cv)


if __name__ == "__main__":
    main()
