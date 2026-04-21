#!/usr/bin/env python3
import os
import sys
import json
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
        # Компиляция регекспа для поиска asm один раз
        self.asm_pattern = re.compile(r'\basm\b|__asm__|__asm', re.IGNORECASE)
        
    def search_repos(self, language: str, max_results: int = 50) -> List[Dict]:
        """Поиск репозиториев по языку"""
        query = f"language:{language} stars:1..500 size:<50000"
        query += " -topic:qt -topic:gtk -topic:gui -topic:electron"
        
        url = f"{self.base_url}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "asc",
            "per_page": min(max_results, 100)
        }
        
        repos = []
        page = 1
        while len(repos) < max_results:
            params["page"] = page
            try:
                resp = self.session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                # Проверка на лимиты API
                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    print("  ⚠ Rate limit hit, waiting 60s...")
                    time.sleep(60)
                    continue
                    
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                repos.extend(items)
                page += 1
                if len(items) < 100:
                    break
                # Пауза чтобы не словить бан от GitHub
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                print(f"  Error searching: {e}")
                time.sleep(5)
                break
        return repos[:max_results]

    def _has_inline_asm(self, filepath: Path) -> bool:
        """Проверка файла на наличие inline assembly"""
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            return bool(self.asm_pattern.search(content))
        except:
            return False

    def check_and_clone(self, repo_url: str, target_dir: Path) -> Optional[Dict]:
        """Клонирование и проверка проекта на соответствие требованиям"""
        if target_dir.exists():
            shutil.rmtree(target_dir)
            
        try:
            # Клонирование сразу в целевую директорию
            subprocess.run(
                ["git", "clone", "--depth", "1", "--quiet", repo_url, str(target_dir)],
                capture_output=True, 
                timeout=90,
                check=True
            )
            
            # Проверка наличия файлов
            has_c = len(list(target_dir.rglob("*.c"))) > 0
            has_cpp = len(list(target_dir.rglob("*.cpp"))) > 0
            has_header = len(list(target_dir.rglob("*.h"))) + len(list(target_dir.rglob("*.hpp"))) > 0
            has_makefile = (target_dir / "Makefile").exists()
            has_cmake = (target_dir / "CMakeLists.txt").exists()
            
            # Базовые требования
            if not (has_c or has_cpp) or not has_header or not (has_makefile or has_cmake):
                shutil.rmtree(target_dir, ignore_errors=True)
                return None
            
            # Проверка на inline asm во всех исходниках
            for ext in ["*.c", "*.cpp", "*.h", "*.hpp", "*.cc", "*.cxx"]:
                for f in target_dir.rglob(ext):
                    if self._has_inline_asm(f):
                        shutil.rmtree(target_dir, ignore_errors=True)
                        return None
            
            # Определение языка
            language = "cpp" if has_cpp and not has_c else "c"
            
            return {
                "url": repo_url,
                "language": language,
                "has_makefile": has_makefile,
                "has_cmake": has_cmake,
            }
                
        except subprocess.TimeoutExpired:
            print(f"  Skip (timeout): {repo_url}")
            shutil.rmtree(target_dir, ignore_errors=True)
            return None
        except Exception as e:
            print(f"  Skip (error): {e}")
            shutil.rmtree(target_dir, ignore_errors=True)
            return None

    def generate_info(self, repo_data: Dict, project_name: str) -> str:
        """Генерация info.txt"""
        build_system = "make" if repo_data["has_makefile"] else "cmake"
        lang_map = {"c": "C", "cpp": "C++"}
        
        return f"""Name: {project_name}
Language: {lang_map.get(repo_data['language'], 'Unknown')}
Build: {build_system}
Output: auto
Description: Auto-imported from {repo_data['url']}
"""

    def save_project(self, repo_data: Dict, target_dir: Path, project_name: str):
        """очистка и создание info.txt"""
        # Удаление артефактов сборки
        for d in ["build", "bin", ".git"]:
            shutil.rmtree(target_dir / d, ignore_errors=True)
        for o in target_dir.rglob("*.o"):
            o.unlink()
            
        # Создание info.txt
        info_content = self.generate_info(repo_data, project_name)
        (target_dir / "info.txt").write_text(info_content, encoding="utf-8")
        
        print(f"  ✓ Added: {project_name} ({repo_data['language']})")

def main():
    base_dir = Path("dataset_sources")
    base_dir.mkdir(exist_ok=True)
    
    token = os.getenv("GITHUB_TOKEN")
    finder = ProjectFinder(token)
    
    languages = ["c", "cpp"]
    max_per_lang = 5  # Сколько проектов собирать на язык
    
    for lang in languages:
        print(f"\n Searching {lang.upper()} projects...")
        # Ищем с запасом, т.к. многие отсеются по фильтрам
        repos = finder.search_repos(lang, max_results=max_per_lang * 5)
        
        added = 0
        for i, repo in enumerate(repos, 1):
            if added >= max_per_lang:
                break
                
            repo_name = repo["name"]
            print(f"  [{i}/{len(repos)}] Processing {repo_name}...")
            
            # Целевая папка для проекта
            target_dir = base_dir / lang / repo_name
            
            result = finder.check_and_clone(repo["html_url"], target_dir)
            
            if result:
                finder.save_project(result, target_dir, repo_name)
                added += 1
            else:
                print(f"  ✗ Rejected: {repo_name}")
                    
        print(f"Added {added}/{max_per_lang} {lang.upper()} projects")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n Interrupted by user")
        sys.exit(1)