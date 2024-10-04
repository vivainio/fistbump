from argparse import ArgumentParser
import glob
import subprocess
import semver
from pathlib import Path
import re


def git_find_tag():
    try:
        return (
            subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"])
            .strip()
            .decode("utf-8")
        )
    except subprocess.CalledProcessError:
        return None


def parse_version(tag: str) -> tuple[semver.VersionInfo, str]:
    prefix = ""
    if tag.startswith("v"):
        prefix = "v"
        tag = tag[1:]

    return semver.VersionInfo.parse(tag, optional_minor_and_patch=True), prefix


def is_working_directory_clean():
    try:
        subprocess.check_output(["git", "diff", "--quiet"])
        return True
    except subprocess.CalledProcessError:
        return False


def is_file_tracked_by_git(file: str):
    try:
        subprocess.check_output(
            ["git", "ls-files", "--error-unmatch", file], stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False


def collect_file_updates(new_version: str):
    updates = {}
    version_files = glob.glob("**/version.txt", recursive=True)
    updates.update({f: new_version for f in version_files})

    toml = Path("pyproject.toml")
    if toml.exists():
        cont = toml.read_text()
        new_cont = re.sub(
            r"version\s*=\s*\"\d+.*?\"", f'version = "{new_version}"', cont
        )
        if new_cont != cont:
            updates["pyproject.toml"] = new_cont
    return updates


def main():
    parser = ArgumentParser()

    parser.add_argument("--minor", help="Bump minor version", action="store_true")
    parser.add_argument("--major", help="Bump major version", action="store_true")
    parser.add_argument("--patch", help="Bump patch version", action="store_true")
    parser.add_argument(
        "--pre",
        help="Create a pre-release version. Changes will NOT be committed or tagged",
        action="store_true",
    )
    parser.add_argument(
        "--force",
        help="Force the modifications even if working directory is not clean",
        action="store_true",
    )
    parser.add_argument(
        "--dry",
        help="Dry run. Do not modify anything, just show what would be done",
        action="store_true",
    )

    current_tag = git_find_tag()
    if current_tag is None:
        print("No tags found")
        return
    parsed_version, prefix = parse_version(current_tag)

    args = parser.parse_args()
    print(f"Current version: {prefix}{parsed_version}")

    if args.minor:
        new_version = parsed_version.bump_minor()
    elif args.major:
        new_version = parsed_version.bump_major()
    elif args.patch:
        new_version = parsed_version.bump_patch()
    elif args.pre:
        new_version = parsed_version.bump_prerelease("dev")
    else:
        print("No version bump requested, consider --major, --minor or --patch")
        return

    new_version_tag = f"{prefix}{new_version}"
    print(f"New version: {new_version}")
    if str(new_version) != new_version_tag:
        print(f"New tag: {new_version_tag}")

    if not is_working_directory_clean() and not args.force:
        print(
            "Working directory is not clean, commit changes before proceeding or use the --force"
        )
        return

    ran_commands = []
    def run_command(cmd):
        ran_commands.append(" ".join(cmd))
        subprocess.run(cmd, check=True)

    updates = collect_file_updates(f"{prefix}{new_version}")
    for file, content in updates.items():
        print(f"######### File: {file}")
        print(content)
        print()
    prompt = "Proceed with changes and tagging? [y/N] " if not args.pre else "Tagging won't be done because of --pre. Proceed with changes? [y/N] "
    ok = input(prompt) == "y"
    if not ok:
        print("Aborted by user request")
        return
    commit_needed = False
    for file, content in updates.items():
        print(f"Updating {file}")
        if not args.dry:
            Path(file).write_text(content)
            if is_file_tracked_by_git(file):
                print("git add", file)
                run_command(["git", "add", file])
                commit_needed = True
            else:
                print(f"File {file} is not tracked by git, skipping add")

    if commit_needed:
        run_command(
            ["git", "commit", "-m", f"Bump version to {new_version}"]
        )
    if not args.pre:
        run_command(["git", "tag", new_version_tag])
    else:
        print("Pre-release version, not tagging")

    print("All done!")
    print("Commands ran:")
    for cmd in ran_commands:
        print(cmd)
