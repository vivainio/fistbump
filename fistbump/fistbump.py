import glob
import re
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

import semver


def git_check_tagged() -> bool:
    try:
        got = subprocess.check_output(["git", "describe", "--tags"], text=True).strip()
        return not "-" in got
    except subprocess.CalledProcessError:
        return False


def git_find_tag():
    try:
        return (
            subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"])
            .strip()
            .decode("utf-8")
        )
    except subprocess.CalledProcessError:
        return None


def git_get_head_tags():
    try:
        return (
            subprocess.check_output(["git", "tag", "--points-at", "HEAD"])
            .strip()
            .decode("utf-8")
            .split("\n")
        )
    except subprocess.CalledProcessError:
        return []


def is_version_parseable(tag: str) -> bool:
    try:
        parse_version(tag)
        return True
    except ValueError:
        return False


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


def is_path_tracked_by_git(file: str):
    try:
        subprocess.check_output(
            ["git", "ls-files", "--error-unmatch", file], stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False


def collect_file_updates(new_version: str):
    updates = {}
    version_files = Path().glob("**/version.txt")
    updates.update(
        {f: new_version for f in version_files if is_path_tracked_by_git(f.parent)}
    )

    toml = Path("pyproject.toml")
    if toml.exists():
        cont = toml.read_text()
        new_cont = re.sub(
            r"version\s*=\s*\"\d+.*?\"", f'version = "{new_version}"', cont
        )
        if new_cont != cont:
            updates["pyproject.toml"] = new_cont
    return updates


def get_version():
    return open(Path(__file__).absolute().parent / "version.txt").read().strip()


def main():
    parser = ArgumentParser()

    parser.add_argument("--minor", help="Bump minor version", action="store_true")
    parser.add_argument("--major", help="Bump major version", action="store_true")
    parser.add_argument("--patch", help="Bump patch version", action="store_true")
    parser.add_argument(
        "--set-version",
        help="Set the version directly to a specific value, instead of bumping",
        type=str,
    )
    parser.add_argument(
        "--version",
        "-v",
        help="Show the version of fistbump itself",
        action="store_true",
    )
    parser.add_argument(
        "--pre",
        help="Create a pre-release version. Changes will NOT be committed or tagged. The minor version will be bumped and the pre-release tag will be set to 'dev'",
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
    parser.add_argument(
        "--check",
        help="Check if the repository is properly tagged before publishing. Returns error if it's not.",
        action="store_true",
    )

    args = parser.parse_args()
    if args.version:
        print("fistbump " + get_version())
        return

    if args.check:
        if not is_working_directory_clean():
            print("Working directory is not clean, commit changes before proceeding")
            sys.exit(2)
        if not git_check_tagged():
            print("Current version is not tagged, need to run 'fistbump' first")
            sys.exit(2)
        return 0

    current_tag = git_find_tag()
    if current_tag is None:
        print("No tags found")
        return

    parsed_version, prefix = parse_version(current_tag)
    print(f"Current version: {prefix}{parsed_version}")

    if args.minor:
        new_version = parsed_version.bump_minor()
    elif args.major:
        new_version = parsed_version.bump_major()
    elif args.patch:
        new_version = parsed_version.bump_patch()
    elif args.set_version:
        new_version = semver.VersionInfo.parse(args.set_version)
    elif args.pre:
        new_version = parsed_version.bump_minor().bump_prerelease("dev")
    else:
        print(
            "No version bump requested, consider --major, --minor, --patch, --set-version or --pre"
        )
        return None

    new_version_tag = f"{prefix}{new_version}"
    print(f"New version: {new_version}")
    if str(new_version) != new_version_tag:
        print(f"New tag: {new_version_tag}")

    ran_commands = []

    def run_command(cmd, check_dry=False):
        if check_dry and args.dry:
            print("DRY RUN:", " ".join(cmd))
            return
        # we don't log commands that are run even in dry runs, as non-mutating
        if not check_dry:
            ran_commands.append(" ".join(map(str, cmd)))
        subprocess.run(cmd, check=True)

    if not is_working_directory_clean():
        run_command(["git", "status", "-s"])
        if args.pre:
            print("Working directory is not clean, but proceeding because of --pre")
        elif not args.force:
            print(
                "Working directory is not clean, commit changes before proceeding or use the --force"
            )
            return

    current_head_tags = git_get_head_tags()
    if not args.force and any(is_version_parseable(tag) for tag in current_head_tags):
        print(
            "Current HEAD is tagged with a version tag(s). Refusing to proceed without --force: "
            + ",".join(current_head_tags)
        )
        return
    updates = collect_file_updates(str(new_version))
    for file, content in updates.items():
        print(f"######### File: {file}")
        print(content)
        print()
    prompt = (
        "Proceed with changes and tagging? [y/N] "
        if not args.pre
        else "Tagging won't be done because of --pre. Proceed with changes? [y/N] "
    )
    ok = input(prompt) == "y"
    if not ok:
        print("Aborted by user request")
        return
    commit_needed = False
    for file, content in updates.items():
        print(f"Updating {file}")
        if not args.dry:
            Path(file).write_text(content)
            if is_path_tracked_by_git(file) and not args.pre:
                print("git add", file)
                run_command(
                    ["git", "add", file],
                )
                commit_needed = True
            else:
                print(f"File {file} is not tracked by git, skipping add")

    if commit_needed:
        run_command(
            ["git", "commit", "-m", f"Bump version to {new_version}"], check_dry=True
        )
    if not args.pre:
        run_command(["git", "tag", new_version_tag], check_dry=True)
    else:
        print("Pre-release version, not tagging")

    print("All done!")
    print("Commands ran:")
    for cmd in ran_commands:
        print(cmd)
