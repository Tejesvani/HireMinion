"""
retrieve_job.py — Retrieve job details and resume PDF from archive

Usage:
    python backend/retrieve_job.py
    python backend/retrieve_job.py --company "Abbott" --role "Data Engineer"
    python backend/retrieve_job.py --company "Stripe" --role "Senior Backend"
    python backend/retrieve_job.py --list
"""

import sys
import os
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
ARCHIVE_FILE = PROJECT_ROOT / "resume_archive" / "archive.jsonl"
DOWNLOADED_DIR = PROJECT_ROOT / "downloaded"
OUTPUT_DIR = PROJECT_ROOT / "output"
RETRIEVAL_DIR = PROJECT_ROOT / "retrieved"

sys.path.insert(0, str(PROJECT_ROOT / "backend"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_archive() -> list[dict]:
    """Load all records from the JSONL archive."""
    if not ARCHIVE_FILE.exists():
        print("✗ No archive file found at resume_archive/archive.jsonl")
        print("  Run a scrape first to build the archive.")
        sys.exit(1)

    records = []
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  ⚠ Skipping malformed line {i}: {e}")

    return records


def search_records(records: list[dict], company: str, role: str) -> list[dict]:
    """Search archive by partial company and role match (case-insensitive)."""
    matches = []
    for r in records:
        jd = r.get("job_details", {})
        company_match = company.lower() in jd.get("company", "").lower()
        role_match = role.lower() in jd.get("role", "").lower()
        if company_match and role_match:
            matches.append(r)
    return matches


def list_all_jobs(records: list[dict]):
    """Print a summary table of all archived jobs."""
    if not records:
        print("No jobs in archive.")
        return

    print(f"\n{'#':<4} {'Date':<12} {'Company':<25} {'Role':<35} {'Applied':<10}")
    print("─" * 90)

    for i, r in enumerate(records, 1):
        jd = r.get("job_details", {})
        date = r.get("archived_at", "")[:10]
        company = jd.get("company", "Unknown")[:24]
        role = jd.get("role", "Unknown")[:34]
        applied = "✓ Yes" if r.get("applied") else "○ No"
        print(f"{i:<4} {date:<12} {company:<25} {role:<35} {applied:<10}")

    print(f"\nTotal: {len(records)} jobs archived")
    applied_count = sum(1 for r in records if r.get("applied"))
    print(f"Applied: {applied_count} | Pending: {len(records) - applied_count}")


def print_job_details(jd: dict):
    """Print formatted job details."""
    print("\n" + "═" * 60)
    print("  JOB DETAILS")
    print("═" * 60)

    fields = [
        ("Company",          "company"),
        ("Role",             "role"),
        ("Location",         "location"),
        ("Work Type",        "work_type"),
        ("Employment",       "employment_type"),
        ("Industry",         "industry"),
        ("Experience",       "experience_years"),
        ("Min Salary",       "min_salary"),
        ("Max Salary",       "max_salary"),
        ("Job Number",       "job_number"),
        ("Posted",           "posted_date"),
        ("Clearance",        "clearance"),
    ]

    for label, key in fields:
        value = jd.get(key)
        if value and value != "null":
            print(f"  {label:<16}: {value}")

    # Required skills
    required = jd.get("required_skills", [])
    if isinstance(required, str):
        try:
            required = json.loads(required)
        except Exception:
            required = [required]
    if required:
        print(f"\n  {'Required Skills':<16}:")
        for skill in required:
            print(f"    • {skill}")

    # Nice to have
    nice = jd.get("nice_to_have", [])
    if isinstance(nice, str):
        try:
            nice = json.loads(nice)
        except Exception:
            nice = [nice]
    if nice:
        print(f"\n  {'Nice to Have':<16}:")
        for skill in nice:
            print(f"    • {skill}")

    # Short description
    desc = jd.get("short_description")
    if desc:
        print(f"\n  {'Description':<16}:")
        # Word-wrap at 60 chars
        words = desc.split()
        line = "    "
        for word in words:
            if len(line) + len(word) + 1 > 64:
                print(line)
                line = "    " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(line)

    # URL
    url = jd.get("url")
    if url:
        print(f"\n  {'URL':<16}: {url}")

    print("═" * 60)


def print_resume_summary(resume: dict):
    """Print a readable summary of the tailored resume."""
    print("\n" + "═" * 60)
    print("  TAILORED RESUME SUMMARY")
    print("═" * 60)

    summary = resume.get("summary", "")
    if summary:
        print(f"\n  SUMMARY\n  {summary}\n")

    personal = resume.get("personal_info", {})
    if personal:
        print(f"  Location : {personal.get('location', '')}")

    experience = resume.get("experience", [])
    if experience:
        print(f"\n  EXPERIENCE")
        for exp in experience:
            print(f"\n  {exp.get('company', '')} | {exp.get('title', '')}")
            print(f"  {exp.get('start_date', '')} – {exp.get('end_date', '')} | {exp.get('location', '')}")
            for b in exp.get("bullets", []):
                # Word-wrap bullets at 58 chars
                print(f"    • {b[:110]}")

    projects = resume.get("projects", [])
    if projects:
        print(f"\n  PROJECTS")
        for p in projects:
            print(f"\n  {p.get('name', '')} | {p.get('tech_stack', '')}")
            for b in p.get("bullets", p.get("description", "").split(". ")):
                print(f"    • {b}")

    skills = resume.get("skills", {})
    if skills and isinstance(skills, dict):
        print(f"\n  SKILLS")
        for category, items in skills.items():
            label = category.replace("_", " ").title()
            if isinstance(items, list):
                print(f"    {label}: {', '.join(items)}")
            else:
                print(f"    {label}: {items}")

    print("═" * 60)


def restore_to_downloaded(record: dict):
    """Write job details and resume back to downloaded/ for recompilation."""
    DOWNLOADED_DIR.mkdir(exist_ok=True)
    jd = record.get("job_details", {})
    resume = record.get("tailored_resume", {})
    cover = record.get("tailored_cover", {})

    with open(DOWNLOADED_DIR / "job_details.json", "w", encoding="utf-8") as f:
        json.dump(jd, f, indent=2)
    with open(DOWNLOADED_DIR / "tailored_resume.json", "w", encoding="utf-8") as f:
        json.dump(resume, f, indent=2)
    if cover:
        with open(DOWNLOADED_DIR / "tailored_cover.json", "w", encoding="utf-8") as f:
            json.dump(cover, f, indent=2)

    print("  ✓ Restored job_details.json")
    print("  ✓ Restored tailored_resume.json")
    if cover:
        print("  ✓ Restored tailored_cover.json")


def compile_pdf(template_name: str) -> Path | None:
    """Run the LaTeX compiler to regenerate the PDF."""
    print(f"\n  Compiling PDF for template: {template_name}...")

    # Write a minimal metadata.json so auto_compile knows which template to use
    metadata = {
        "options": {
            "resumeFile": f"{template_name}.tex",
            "resume": True,
            "coverLetter": False
        }
    }
    with open(DOWNLOADED_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    try:
        result = subprocess.run(
            [sys.executable, "backend/latex_compiler.py", "auto"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=180
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)

        pdf_path = OUTPUT_DIR / f"{template_name}.pdf"
        if pdf_path.exists():
            return pdf_path
        return None
    except subprocess.TimeoutExpired:
        print("  ✗ PDF compilation timed out")
        return None
    except Exception as e:
        print(f"  ✗ PDF compilation error: {e}")
        return None


def save_retrieved_files(record: dict, company: str, role: str, pdf_path: Path | None):
    """Save all retrieved assets to retrieved/ folder."""
    RETRIEVAL_DIR.mkdir(exist_ok=True)

    # Sanitize name for filesystem
    safe_name = f"{company}_{role}".replace(" ", "_").replace("/", "-")[:60]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    folder = RETRIEVAL_DIR / f"{safe_name}_{timestamp}"
    folder.mkdir(exist_ok=True)

    # Save job details JSON
    with open(folder / "job_details.json", "w", encoding="utf-8") as f:
        json.dump(record.get("job_details", {}), f, indent=2)

    # Save tailored resume JSON
    with open(folder / "tailored_resume.json", "w", encoding="utf-8") as f:
        json.dump(record.get("tailored_resume", {}), f, indent=2)

    # Save cover letter JSON if present
    cover = record.get("tailored_cover", {})
    if cover:
        with open(folder / "tailored_cover.json", "w", encoding="utf-8") as f:
            json.dump(cover, f, indent=2)

    # Copy PDF if compiled
    if pdf_path and pdf_path.exists():
        dest = folder / pdf_path.name
        shutil.copy(pdf_path, dest)
        print(f"  ✓ PDF saved to: {dest}")

    print(f"  ✓ All files saved to: {folder}")
    return folder


def pick_template(jd: dict) -> str:
    """
    Infer which resume template to use based on the role in job details.
    Falls back to DE template if no match found.
    """
    templates_dir = PROJECT_ROOT / "templates"
    available = [f.stem for f in templates_dir.glob("*.tex")]

    role = jd.get("role", "").lower()

    # Role → template suffix mapping
    role_map = {
        "data engineer":      "_DE",
        "analytics engineer": "_AE",
        "data analyst":       "_DA",
        "master":             "_MASTER",
    }

    for keyword, suffix in role_map.items():
        if keyword in role:
            for t in available:
                if t.endswith(suffix):
                    return t

    # Fallback — pick first available non-master template
    for t in sorted(available):
        if "MASTER" not in t.upper() and t.startswith("Tejesvani"):
            return t

    return available[0] if available else "TejesvaniMupparaVijayaram_DE"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Retrieve job details and resume from HireMinion archive"
    )
    parser.add_argument(
        "--company", "-c",
        type=str,
        help='Company name to search for (partial match). Example: "Abbott"'
    )
    parser.add_argument(
        "--role", "-r",
        type=str,
        help='Role to search for (partial match). Example: "Data Engineer"'
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all archived jobs"
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF recompilation (faster, just dumps JSON)"
    )
    parser.add_argument(
        "--template", "-t",
        type=str,
        help="Override template name for PDF compilation"
    )

    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  HIREMINION — JOB RETRIEVAL")
    print("═" * 60)

    records = load_archive()

    # ── List mode ────────────────────────────────────────────
    if args.list:
        list_all_jobs(records)
        return

    # ── Interactive mode if no args ──────────────────────────
    if not args.company and not args.role:
        list_all_jobs(records)
        print()
        args.company = input("Enter company name (partial ok): ").strip()
        args.role    = input("Enter role (partial ok):         ").strip()

    if not args.company or not args.role:
        print("✗ Both --company and --role are required.")
        sys.exit(1)

    # ── Search ───────────────────────────────────────────────
    print(f"\n  Searching for: '{args.company}' + '{args.role}'...")
    matches = search_records(records, args.company, args.role)

    if not matches:
        print(f"\n  ✗ No matches found for company='{args.company}' role='{args.role}'")
        print("\n  All archived companies:")
        seen = set()
        for r in records:
            c = r.get("job_details", {}).get("company", "Unknown")
            if c not in seen:
                print(f"    • {c}")
                seen.add(c)
        sys.exit(1)

    # ── Multiple matches ─────────────────────────────────────
    if len(matches) > 1:
        print(f"\n  Found {len(matches)} matches:\n")
        for i, r in enumerate(matches, 1):
            jd = r.get("job_details", {})
            date = r.get("archived_at", "")[:10]
            applied = "✓ Applied" if r.get("applied") else "○ Pending"
            print(f"  [{i}] {date} | {jd.get('company')} | {jd.get('role')} | {applied}")
        print()
        choice = input(f"  Select [1-{len(matches)}] (default 1): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        idx = max(0, min(idx, len(matches) - 1))
        record = matches[idx]
    else:
        record = matches[0]

    jd = record.get("job_details", {})
    print(f"\n  ✓ Found: {jd.get('company')} | {jd.get('role')}")
    print(f"  Archived: {record.get('archived_at', '')[:10]}")
    print(f"  Applied: {'Yes' if record.get('applied') else 'No'}")

    # ── Print job details ─────────────────────────────────────
    print_job_details(jd)

    # ── Print resume summary ──────────────────────────────────
    resume = record.get("tailored_resume", {})
    if resume:
        print_resume_summary(resume)
    else:
        print("\n  ⚠ No tailored resume found in this archive record")

    # ── Compile PDF ───────────────────────────────────────────
    if not args.no_pdf:
        print("\n  Restoring files to downloaded/...")
        restore_to_downloaded(record)

        template = args.template or pick_template(jd)
        print(f"  Using template: {template}")

        pdf_path = compile_pdf(template)

        if pdf_path:
            print(f"\n  ✓ PDF compiled: {pdf_path}")
        else:
            print("\n  ✗ PDF compilation failed — JSON files restored to downloaded/")
            print("     Run manually: python backend/latex_compiler.py auto")
            pdf_path = None
    else:
        print("\n  Skipping PDF compilation (--no-pdf)")
        pdf_path = None

    # ── Save to retrieved/ folder ─────────────────────────────
    output_folder = save_retrieved_files(record, args.company, args.role, pdf_path)

    print(f"\n  Done. Files saved to: {output_folder}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()