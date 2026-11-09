"""Split a unified PR diff per file and drop files not worth reviewing."""

from pathlib import PurePosixPath

NOISE_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", "poetry.lock"}
NOISE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".mp4", ".mp3",
    ".pdf", ".zip", ".tar", ".gz",
}
NOISE_DIRS = {"dist", "build", ".next"}


def is_noise_file(filename: str) -> bool:
    path = PurePosixPath(filename.lower())
    return (
        path.name in NOISE_FILENAMES
        or path.suffix in NOISE_EXTENSIONS
        or any(part in NOISE_DIRS for part in path.parts[:-1])
    )


def reviewable_diff(raw_diff: str) -> str:
    """Return the diff with noise files removed; empty string if nothing is left."""
    kept = []
    for chunk in raw_diff.split("diff --git ")[1:]:
        # First line looks like: "a/src/index.ts b/src/index.ts"
        first_line = chunk.split("\n", 1)[0]
        _, _, filename = first_line.partition(" b/")
        if not is_noise_file(filename or first_line):
            kept.append(f"diff --git {chunk}")
    return "".join(kept)
