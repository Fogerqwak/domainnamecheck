import subprocess
import sys
from pathlib import Path

steps = [
    ("Checking .com domains", "check_com.py"),
    ("Checking .ai domains", "check_ai.py"),
    ("Comparing results", "compare.py"),
]

for title, script in steps:
    print("=" * 60)
    print(title)
    print("=" * 60)

    if not Path(script).exists():
        print(f"Missing: {script}")
        sys.exit(1)

    result = subprocess.run([sys.executable, script])

    if result.returncode != 0:
        print(f"{script} failed.")
        sys.exit(result.returncode)

print()
print("=" * 60)
print("Done!")
print("Results saved to available_both.txt")
print("=" * 60)
