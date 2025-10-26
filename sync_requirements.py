#!/usr/bin/env python3
"""
Sync script to update requirements.txt files from Poetry dependencies.
Run this script when you add new dependencies to pyproject.toml.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional


def run_command(cmd: list[str], cwd: Optional[Path] = None) -> str:
    """Run a command and return its output."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd)}: {e}")
        sys.exit(1)


def export_requirements():
    """Export Poetry dependencies to requirements.txt files using dependency groups."""
    root_dir = Path(__file__).parent

    # Define mapping of dependency groups to folders
    group_to_folder = {
        "fastapi-app": "fastapi-app",
        "batch-worker": "batch-worker",
        "batch-worker-lambda": "batch-worker-lambda",
    }

    for group_name, folder_name in group_to_folder.items():
        # Export dependencies for this group
        try:
            reqs = run_command(
                [
                    "poetry",
                    "export",
                    "--only",
                    group_name,
                    "--without-hashes",
                    "-f",
                    "requirements.txt",
                ],
                root_dir,
            )

            req_path = root_dir / folder_name / "requirements.txt"
            with open(req_path, "w") as f:
                f.write(reqs + "\n" if reqs else "")
            print(f"Updated {req_path}")

        except Exception as e:
            print(f"Warning: Could not export {group_name} group: {e}")
            # Create empty requirements.txt if group doesn't exist yet
            req_path = root_dir / folder_name / "requirements.txt"
            with open(req_path, "w") as f:
                f.write("")
            print(f"Created empty {req_path}")


def main():
    """Main function."""
    print("Syncing Poetry dependencies to requirements.txt files...")
    export_requirements()
    print("Sync complete!")


if __name__ == "__main__":
    main()
