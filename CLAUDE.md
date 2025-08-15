# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python-based GitLab repository analyzer designed to identify files that may cause issues during GitHub migration. The tool uses the GitLab API to scan repositories and categorizes files based on GitHub's size limits (100MB hard limit, 50MB warning threshold).

## Commands

### Running the Analyzer

```bash
# Basic usage with all accessible repositories
python gitlab_analyzer.py --token YOUR_GITLAB_TOKEN

# Analyze specific group
python gitlab_analyzer.py --token YOUR_TOKEN --group-id 12345

# Analyze with custom threshold
python gitlab_analyzer.py --token YOUR_TOKEN --threshold 25.0

# Custom GitLab instance
python gitlab_analyzer.py --token YOUR_TOKEN --gitlab-url https://gitlab.company.com
```

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run example usage script
python example_usage.py
```

## Architecture

### Core Components

**GitLabAnalyzer Class** (`gitlab_analyzer.py`)
- Main analysis engine that interfaces with GitLab API
- Handles rate limiting with exponential backoff
- Categorizes files into three migration risk levels:
  - **Blockers** (>100MB): Cannot migrate to GitHub
  - **LFS Candidates** (50-100MB): Should use Git LFS
  - **Migration Ready** (<50MB): No issues

### Key Methods

- `get_repositories()`: Fetches repositories based on group/user filters
- `analyze_repository()`: Scans individual repository for large files
- `run_analysis()`: Orchestrates full analysis workflow
- `save_results()`: Generates multiple output formats (JSON, CSV, TXT reports)

### Data Flow

1. **Authentication**: Uses GitLab personal access token
2. **Repository Discovery**: Fetches accessible repositories via API
3. **File Analysis**: Iterates through repository trees to identify large files
4. **Categorization**: Classifies files based on GitHub migration thresholds
5. **Reporting**: Generates migration-focused reports in multiple formats

### Output Structure

The analyzer creates timestamped output files in the specified directory:
- `gitlab_analysis_TIMESTAMP.json`: Complete analysis data
- `github_migration_blockers_TIMESTAMP.csv`: Critical files >100MB
- `git_lfs_candidates_TIMESTAMP.csv`: Files needing Git LFS (50-100MB)
- `all_large_files_TIMESTAMP.csv`: All files above threshold
- `analysis_report_TIMESTAMP.txt`: Human-readable migration report

### API Integration

Uses GitLab API v4 endpoints:
- `/projects`: Repository listing
- `/groups/{id}/projects`: Group repositories
- `/users/{id}/projects`: User repositories
- `/projects/{id}/repository/tree`: File tree traversal
- `/projects/{id}/repository/files/{path}`: File metadata

Rate limiting is handled automatically with configurable delays between requests.