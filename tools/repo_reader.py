import os


IMPORTANT_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    "README.md",
    "main.py",
    "app.py",
}


def scan_repository(repo_path: str):
    tree_lines = []
    key_contents = []
    evidence = []

    for root, dirs, files in os.walk(repo_path):
        level = root.replace(repo_path, "").count(os.sep)
        indent = "  " * level
        tree_lines.append(f"{indent}{os.path.basename(root)}/")

        for file in files:
            tree_lines.append(f"{indent}  {file}")

            if file in IMPORTANT_FILES:
                try:
                    full_path = os.path.join(root, file)
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()[:3000]

                    key_contents.append(
                        f"\n### FILE: {file}\n{content}"
                    )
                    evidence.append(full_path)
                except Exception:
                    pass

    return "\n".join(tree_lines), "\n".join(key_contents), evidence
