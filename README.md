# fistbump - easy semver publishing

Installation:

```
pip install fistbump
```

Usage:

```
usage: fistbump [-h] [--minor] [--major] [--patch] [--pre] [--force] [--dry]

options:
  -h, --help  show this help message and exit
  --minor     Bump minor version
  --major     Bump major version
  --patch     Bump patch version
  --pre       Create a pre-release version. Changes will NOT be committed or tagged
  --force     Force the modifications even if working directory is not clean
  --dry       Dry run. Do not modify anything, just show what would be done
```

# Problem

You want to create a git tag that is next version from previous git tag. You want to write the next version to any version.txt file you may have around, and also your pyproject.toml.

It's easy but it's boring, just running fistbump will do it for you.

## Example session

```
❯ fistbump --minor
Current version: 1.1.0
New version: 1.2.0
######### File: pyproject.toml
[build-system]
build-backend = "setuptools.build_meta"
requires = ["setuptools"]
...

version = "1.2.0"

...


Proceed with changes and tagging? [y/N] y
Updating pyproject.toml
git add pyproject.toml
[main bbeb2c0] Bump version to 1.2.0
 1 file changed, 1 insertion(+), 1 deletion(-)
All done!
Commands ran:
git add pyproject.toml
git commit -m Bump version to 1.2.0
git tag 1.2.0
```
