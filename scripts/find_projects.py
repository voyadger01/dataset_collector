#!/usr/bin/env python3
import os
import sys
import shutil
import requests
import subprocess
import time
import re
from pathlib import Path
from typing import List, Dict, Optional

class ProjectFinder:
    def __init__(self, github_token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.asm_pattern = re.compile(r'\basm\b|__asm__|__asm', re.IGNORECASE)

    def search_repos_page(self, language: str, page: int = 1, per_page: int = 20) -> List[Dict]:
        query = f"language:{language} stars:1..500 size:<50000"
        query += " -topic:qt -topic:gtk -topic:gui -topic:electron"
        url = f"{self.base_url}/search/repositories"
        params = {"q": query, "sort": "stars", "order": "asc", "per_page": per_page, "page": page}
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                print("  Rate limit exceeded. Pausing for 60 seconds.")
                time.sleep(60)
                return []
            return resp.json().get("items", [])
        except requests.exceptions.RequestException:
            return []

    def _has_inline_asm(self, filepath: Path) -> bool:
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            return bool(self.asm_pattern.search(content))
        except Exception:
            return False

    def _has_binary_dependencies(self, target_dir: Path) -> bool:
        for ext in ["*.a", "*.so", "*.so.*", "*.dll", "*.lib", "*.dylib"]:
            if list(target_dir.rglob(ext)):
                return True
        for config_file in [target_dir / "CMakeLists.txt", target_dir / "Makefile"]:
            if config_file.exists():
                try:
                    content = config_file.read_text().lower()
                    if any(keyword in content for keyword in ["find_library", "pkg_check_modules"]):
                        if not all(lib in content for lib in ["pthread", "m", "dl", "rt"]):
                            return True
                except Exception:
                    continue
        return False

    def _validate_project_structure(self, target_dir: Path) -> Dict[str, bool]:
        has_c = len(list(target_dir.rglob("*.c"))) > 0
        has_cpp = len(list(target_dir.rglob("*.cpp"))) > 0
        has_header = len(list(target_dir.rglob("*.h"))) + len(list(target_dir.rglob("*.hpp"))) > 0
        has_makefile = (target_dir / "Makefile").exists()
        has_cmake = (target_dir / "CMakeLists.txt").exists()
        return {
            "has_c": has_c, "has_cpp": has_cpp, "has_header": has_header,
            "has_makefile": has_makefile, "has_cmake": has_cmake
        }

    def _determine_language(self, structure: Dict[str, bool]) -> Optional[str]:
        if not (structure["has_c"] or structure["has_cpp"]): return None
        if not structure["has_header"]: return None
        if not (structure["has_makefile"] or structure["has_cmake"]): return None
        if structure["has_c"] and structure["has_cpp"]: return "mixed"
        return "cpp" if structure["has_cpp"] else "c"

    def _cleanup_artifacts(self, target_dir: Path):
        for directory in ["build", "bin", ".git"]:
            shutil.rmtree(target_dir / directory, ignore_errors=True)
        for obj_file in target_dir.rglob("*.o"):
            obj_file.unlink()

    def check_and_clone(self, repo_url: str, target_dir: Path) -> Optional[Dict]:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", repo_url, str(target_dir)],
                capture_output=True, timeout=90, check=True
            )
            structure = self._validate_project_structure(target_dir)
            language = self._determine_language(structure)
            if language is None:
                shutil.rmtree(target_dir, ignore_errors=True)
                return None
            if self._has_binary_dependencies(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
                return None
            for ext in ["*.c", "*.cpp", "*.h", "*.hpp", "*.cc", "*.cxx"]:
                for source_file in target_dir.rglob(ext):
                    if self._has_inline_asm(source_file):
                        shutil.rmtree(target_dir, ignore_errors=True)
                        return None
            self._cleanup_artifacts(target_dir)
            return {
                "url": repo_url, "language": language,
                "has_makefile": structure["has_makefile"], "has_cmake": structure["has_cmake"]
            }
        except subprocess.TimeoutExpired:
            shutil.rmtree(target_dir, ignore_errors=True)
            return None
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            return None

    def generate_info_content(self, repo_data: Dict, project_name: str) -> str:
        build_system = "make" if repo_data["has_makefile"] else "cmake"
        language_display = {"c": "C", "cpp": "C++", "mixed": "C/C++"}
        return (
            f"Name: {project_name}\n"
            f"Language: {language_display.get(repo_data['language'], 'Unknown')}\n"
            f"Build: {build_system}\n"
            f"Output: auto\n"
            f"Description: Auto-imported from {repo_data['url']}\n"
        )

    def save_project(self, repo_data: Dict, target_dir: Path, project_name: str):
        info_content = self.generate_info_content(repo_data, project_name)
        (target_dir / "info.txt").write_text(info_content, encoding="utf-8")

    def collect_projects(self, base_dir: Path, languages: List[str], target_count: int):
        base_dir.mkdir(exist_ok=True)
        token = os.getenv("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"token {token}"

        for language in languages:
            added = 0
            page = 1
            checked = 0
            max_checks = 500

            print(f"\nCollecting {language.upper()} (target: {target_count})...")

            while added < target_count and checked < max_checks:
                repos = self.search_repos_page(language, page=page, per_page=20)
                if not repos:
                    break

                for repo in repos:
                    if added >= target_count or checked >= max_checks:
                        break
                    checked += 1
                    repo_name = repo["name"]

                    if any((base_dir / lang / repo_name).exists() for lang in ["c", "cpp", "mixed"]):
                        continue

                    temp_dir = base_dir / "temp_clone"
                    result = self.check_and_clone(repo["html_url"], temp_dir)

                    if result:
                        final_dir = base_dir / result["language"] / repo_name
                        shutil.move(temp_dir, final_dir)
                        self.save_project(result, final_dir, repo_name)
                        added += 1
                        print(f"  [{added}/{target_count}] {repo_name}")
                    else:
                        shutil.rmtree(temp_dir, ignore_errors=True)

                page += 1

            print(f"Completed {language.upper()}: found {added}/{target_count}")

def main():
    base_directory = Path("dataset_sources")
    languages_to_search = ["c", "cpp"]
    TARGET_PROJECTS_PER_LANGUAGE = 100
    
    finder = ProjectFinder()
    finder.collect_projects(base_directory, languages_to_search, TARGET_PROJECTS_PER_LANGUAGE)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)