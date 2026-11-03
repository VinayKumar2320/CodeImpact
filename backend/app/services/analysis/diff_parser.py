from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    base_start: int
    base_length: int
    head_start: int
    head_length: int
    # Specific modified line numbers in head (1-indexed)
    head_added_lines: list[int] = field(default_factory=list)
    # Specific deleted line numbers in base (1-indexed)
    base_deleted_lines: list[int] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str | None
    new_path: str | None
    status: str  # modified, added, deleted, renamed
    additions: int = 0
    deletions: int = 0
    hunks: list[DiffHunk] = field(default_factory=list)

    @property
    def file_path(self) -> str:
        return self.new_path or self.old_path or ""

    @property
    def extension(self) -> str:
        _, ext = os.path.splitext(self.file_path)
        return ext.lower()

    @property
    def is_test_file(self) -> bool:
        path = self.file_path.lower()
        parts = path.split("/")
        filename = parts[-1]
        return (
            "test" in parts
            or "tests" in parts
            or filename.startswith("test_")
            or filename.endswith("_test.py")
            or filename.endswith(".test.ts")
            or filename.endswith(".spec.ts")
            or filename.endswith(".test.js")
            or filename.endswith(".spec.js")
        )

    @property
    def is_config_file(self) -> bool:
        filename = os.path.basename(self.file_path).lower()
        ext = self.extension
        config_names = {
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            "package.json",
            "tsconfig.json",
            "dockerfile",
            "docker-compose.yml",
            "alembic.ini",
            ".env.example",
        }
        return (
            filename in config_names
            or ext in {".yml", ".yaml", ".toml", ".ini", ".cfg"}
            or "config" in filename
        )

    @property
    def is_documentation(self) -> bool:
        path = self.file_path.lower()
        ext = self.extension
        return "docs/" in path or ext in {".md", ".rst", ".txt"}

    @property
    def modified_head_lines(self) -> set[int]:
        """
        Return the set of line numbers in the new file that were added or modified.
        """
        lines = set()
        for h in self.hunks:
            lines.update(h.head_added_lines)
        return lines

    @property
    def modified_base_lines(self) -> set[int]:
        """
        Return the set of line numbers in the old file that were deleted or modified.
        """
        lines = set()
        for h in self.hunks:
            lines.update(h.base_deleted_lines)
        return lines


@dataclass
class ParsedDiff:
    files: list[FileDiff] = field(default_factory=list)

    @property
    def files_changed_count(self) -> int:
        return len(self.files)

    @property
    def lines_added(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def lines_deleted(self) -> int:
        return sum(f.deletions for f in self.files)

    @property
    def change_size(self) -> int:
        return self.lines_added + self.lines_deleted

    @property
    def test_files_changed_count(self) -> int:
        return sum(1 for f in self.files if f.is_test_file)

    @property
    def config_files_changed_count(self) -> int:
        return sum(1 for f in self.files if f.is_config_file)

    @property
    def file_types(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.files:
            ext = f.extension or "no_ext"
            counts[ext] = counts.get(ext, 0) + 1
        return counts

    def get_file(self, path: str) -> FileDiff | None:
        for f in self.files:
            if f.file_path == path:
                return f
        return None


class UnifiedDiffParser:
    """
    Parses standard unified git diff format into structured hunks and line ranges.
    """

    HUNK_HEADER_REGEX = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    def parse(self, diff_text: str) -> ParsedDiff:
        if not diff_text or not diff_text.strip():
            return ParsedDiff()

        files: list[FileDiff] = []
        current_file: FileDiff | None = None
        current_hunk: DiffHunk | None = None

        head_line_counter = 0
        base_line_counter = 0

        for line in diff_text.splitlines():
            # New file header
            if line.startswith("diff --git "):
                if current_file:
                    if current_hunk:
                        current_file.hunks.append(current_hunk)
                        current_hunk = None
                    files.append(current_file)

                # Parse file paths
                parts = line.split(" ")
                old_path = parts[2].removeprefix("a/") if len(parts) >= 3 else None
                new_path = parts[3].removeprefix("b/") if len(parts) >= 4 else None

                current_file = FileDiff(
                    old_path=old_path,
                    new_path=new_path,
                    status="modified",
                )
                continue

            if not current_file:
                continue

            # Detect file status
            if line.startswith("new file mode"):
                current_file.status = "added"
                current_file.old_path = None
            elif line.startswith("deleted file mode"):
                current_file.status = "deleted"
                current_file.new_path = None
            elif line.startswith("similarity index"):
                current_file.status = "renamed"
            elif line.startswith("--- "):
                path = line.removeprefix("--- ").removeprefix("a/").strip()
                if path != "/dev/null" and not current_file.old_path:
                    current_file.old_path = path
            elif line.startswith("+++ "):
                path = line.removeprefix("+++ ").removeprefix("b/").strip()
                if path != "/dev/null" and not current_file.new_path:
                    current_file.new_path = path

            # Hunk header
            elif line.startswith("@@ "):
                if current_hunk:
                    current_file.hunks.append(current_hunk)

                match = self.HUNK_HEADER_REGEX.match(line)
                if match:
                    base_start = int(match.group(1))
                    base_len = int(match.group(2)) if match.group(2) else 1
                    head_start = int(match.group(3))
                    head_len = int(match.group(4)) if match.group(4) else 1

                    current_hunk = DiffHunk(
                        base_start=base_start,
                        base_length=base_len,
                        head_start=head_start,
                        head_length=head_len,
                    )
                    base_line_counter = base_start
                    head_line_counter = head_start
                continue

            # Content inside hunk
            if current_hunk is not None:
                current_hunk.raw_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk.head_added_lines.append(head_line_counter)
                    head_line_counter += 1
                    current_file.additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    current_hunk.base_deleted_lines.append(base_line_counter)
                    base_line_counter += 1
                    current_file.deletions += 1
                else:
                    # Context line
                    head_line_counter += 1
                    base_line_counter += 1

        if current_file:
            if current_hunk:
                current_file.hunks.append(current_hunk)
            files.append(current_file)

        return ParsedDiff(files=files)


diff_parser = UnifiedDiffParser()
