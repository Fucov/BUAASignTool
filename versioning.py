import re


CURRENT_VERSION = "2.4.0"
GITHUB_LATEST_RELEASE_API = (
    "https://api.github.com/repos/Fucov/BUAASignTool/releases/latest"
)
GITHUB_RELEASES_PAGE = "https://github.com/Fucov/BUAASignTool/releases"


def parse_version(value):
    """Return a comparable numeric tuple from tags such as v2.4 or 2.4.1."""
    if not value:
        return None
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)", str(value))
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer_version(latest, current=CURRENT_VERSION):
    latest_parts = parse_version(latest)
    current_parts = parse_version(current)
    if latest_parts is None or current_parts is None:
        return False
    width = max(len(latest_parts), len(current_parts))
    return latest_parts + (0,) * (width - len(latest_parts)) > (
        current_parts + (0,) * (width - len(current_parts))
    )
