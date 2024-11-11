import os
import argparse
from pathlib import Path
import git
import logging
from typing import List, Dict, Set
from dataclasses import dataclass
import yaml
import sys

@dataclass
class AdditionalCheck:
    name: str
    hours: float
    description: str

class CodeReviewEstimator:
    LINES_PER_HOUR = 80
    
    # Files to ignore
    IGNORE_PATTERNS = {
        'node_modules',
        'venv',
        '.git',
        'package-lock.json',
        'yarn.lock',
        '.env',
        '.gitignore',
        '.dockerignore',
        'requirements.txt',
        'package.json'
    }
    
    # File extensions to analyze
    TARGET_EXTENSIONS = {
        '.js', '.ts', '.jsx', '.tsx',  # JavaScript/TypeScript
        '.py',  # Python
        '.java',  # Java
        '.cpp', '.hpp', '.c', '.h',  # C/C++
        '.cs',  # C#
        '.go',  # Go
        '.rb',  # Ruby
        '.php',  # PHP
        '.swift',  # Swift
        '.rs'  # Rust
    }

    DEFAULT_CHECKS_CONFIG = {
        "configuration": {
            "name": "Configuration Review",
            "description": "Review of configuration files, environment variables, and settings",
            "default_hours": 1.0
        },
        "dependencies": {
            "name": "Dependency Analysis",
            "description": "Review of project dependencies, versions, and security implications",
            "default_hours": 1.5
        },
        "security": {
            "name": "Security & Cryptography",
            "description": "Review of security implementations, crypto usage, and potential vulnerabilities",
            "default_hours": 2.0
        },
        "architecture": {
            "name": "Architecture Review",
            "description": "High-level architecture and design pattern review",
            "default_hours": 1.5
        }
    }
    
    def __init__(self):
        self.logger = self._setup_logger()
        self.additional_checks: List[AdditionalCheck] = []
        
    def _setup_logger(self) -> logging.Logger:
        """Configure logging for the estimator."""
        logger = logging.getLogger('CodeReviewEstimator')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def prompt_for_checks(self):
        """Prompt user for additional check timings."""
        print("\n=== Additional Review Checks Configuration ===")
        print("Enter the time (in hours) for each additional check.")
        print("Press Enter to use the default value, or '0' to skip the check.\n")
        
        for check_id, check_info in self.DEFAULT_CHECKS_CONFIG.items():
            while True:
                try:
                    default = check_info['default_hours']
                    response = input(
                        f"{check_info['name']} ({check_info['description']})\n"
                        f"Default time: {default} hours\n"
                        f"Enter hours (or press Enter for default): "
                    ).strip()
                    
                    if response == "":
                        hours = default
                    else:
                        hours = float(response)
                        
                    if hours < 0:
                        print("Please enter a non-negative number.")
                        continue
                        
                    if hours > 0:
                        self.additional_checks.append(AdditionalCheck(
                            name=check_info['name'],
                            hours=hours,
                            description=check_info['description']
                        ))
                    break
                    
                except ValueError:
                    print("Please enter a valid number.")
        
        # Allow custom checks
        while True:
            custom_name = input("\nAdd custom check? (Enter name or press Enter to finish): ").strip()
            if not custom_name:
                break
                
            description = input("Enter description: ").strip()
            while True:
                try:
                    hours = float(input("Enter hours: ").strip())
                    if hours < 0:
                        print("Please enter a non-negative number.")
                        continue
                    break
                except ValueError:
                    print("Please enter a valid number.")
            
            self.additional_checks.append(AdditionalCheck(
                name=custom_name,
                hours=hours,
                description=description
            ))

    def clone_repository(self, repo_url: str, target_dir: str) -> str:
        """Clone a GitHub repository to a local directory."""
        try:
            self.logger.info(f"Cloning repository from {repo_url}")
            git.Repo.clone_from(repo_url, target_dir)
            return target_dir
        except git.GitCommandError as e:
            self.logger.error(f"Failed to clone repository: {e}")
            raise
    
    def should_analyze_file(self, file_path: str) -> bool:
        """Determine if a file should be analyzed based on patterns and extensions."""
        path = Path(file_path)
        
        # Check if file path contains any ignore patterns
        if any(pattern in str(path) for pattern in self.IGNORE_PATTERNS):
            return False
        
        # Check if file extension is in target extensions
        return path.suffix in self.TARGET_EXTENSIONS
    
    def count_lines(self, file_path: str) -> int:
        """Count the number of non-empty lines in a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return sum(1 for line in file if line.strip())
        except UnicodeDecodeError:
            self.logger.warning(f"Failed to read file {file_path} - skipping")
            return 0
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            return 0
    
    def analyze_directory(self, directory: str) -> Dict[str, int]:
        """Analyze all files in a directory and return line counts by file type."""
        self.logger.info(f"Starting analysis of directory: {directory}")
        extension_counts: Dict[str, int] = {}
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                
                if self.should_analyze_file(file_path):
                    extension = Path(file_path).suffix
                    lines = self.count_lines(file_path)
                    
                    if lines > 0:
                        extension_counts[extension] = extension_counts.get(extension, 0) + lines
        
        return extension_counts
    
    def estimate_review_time(self, total_lines: int) -> tuple[float, float, float]:
        """Calculate estimated review time in hours and days, including additional checks."""
        code_review_hours = total_lines / self.LINES_PER_HOUR
        additional_hours = sum(check.hours for check in self.additional_checks)
        total_hours = code_review_hours + additional_hours
        days = total_hours / 8  # Assuming 8-hour workdays
        return code_review_hours, additional_hours, days
    
    def generate_report(self, extension_counts: Dict[str, int]) -> str:
        """Generate a formatted report of the analysis."""
        total_lines = sum(extension_counts.values())
        code_review_hours, additional_hours, days = self.estimate_review_time(total_lines)
        
        report = [
            "\n=== Code Review Estimation Report ===\n",
            "Lines of Code by File Type:"
        ]
        
        for ext, count in sorted(extension_counts.items()):
            report.append(f"  {ext}: {count:,} lines")
        
        report.extend([
            f"\nTotal Lines of Code: {total_lines:,}",
            f"Code Review Speed: {self.LINES_PER_HOUR} lines/hour",
            f"Base Code Review Time: {code_review_hours:.1f} hours"
        ])
        
        if self.additional_checks:
            report.append("\nAdditional Checks:")
            for check in self.additional_checks:
                report.append(f"  {check.name}: {check.hours:.1f} hours")
                report.append(f"    Description: {check.description}")
            
            report.append(f"\nAdditional Checks Total Time: {additional_hours:.1f} hours")
        
        report.extend([
            f"\nTotal Estimated Review Time: {code_review_hours + additional_hours:.1f} hours",
            f"Working Days Required: {days:.1f} (8-hour days)"
        ])
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='Estimate code review time for a repository.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', help='GitHub repository URL')
    group.add_argument('--path', help='Local repository path')
    
    args = parser.parse_args()
    
    estimator = CodeReviewEstimator()
    
    try:
        # Prompt for additional checks configuration
        estimator.prompt_for_checks()
        
        if args.url:
            # Create a temporary directory for cloning
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = estimator.clone_repository(args.url, temp_dir)
                extension_counts = estimator.analyze_directory(repo_path)
        else:
            extension_counts = estimator.analyze_directory(args.path)
        
        report = estimator.generate_report(extension_counts)
        print(report)
        
    except Exception as e:
        estimator.logger.error(f"Error during execution: {e}")
        raise

if __name__ == "__main__":
    main()
