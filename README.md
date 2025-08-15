# GitLab to GitHub Migration Analyzer

A comprehensive Python script that analyzes GitLab repositories via API calls to identify files that may cause issues during GitHub migration. Provides detailed analysis of GitHub compatibility, migration blockers, and Git LFS recommendations.

## Features

- **GitHub Migration Focus**: Specifically designed to identify GitHub compatibility issues
- **Migration Risk Assessment**: Categorizes files as blockers (>100MB), LFS candidates (50-100MB), or migration-ready
- **Full API Integration**: Uses GitLab REST API v4 for comprehensive repository analysis
- **GitHub Limit Detection**: Identifies files exceeding GitHub's 100MB hard limit
- **Git LFS Recommendations**: Suggests files that should use Git LFS for optimal performance
- **Multiple Output Formats**: Separate CSVs for blockers, LFS candidates, plus JSON and detailed reports
- **Migration Readiness Summary**: Clear overview of which repositories are ready to migrate
- **Actionable Recommendations**: Specific steps to resolve migration issues
- **Rate Limiting**: Built-in rate limiting to respect GitLab API limits
- **Flexible Filtering**: Analyze specific groups, users, or all accessible repositories
- **Progress Tracking**: Real-time progress updates with migration-specific alerts

## Prerequisites

- Python 3.6 or higher
- GitLab Personal Access Token with appropriate permissions
- Network access to your GitLab instance

## Installation

1. Clone or download this project
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## GitLab API Token Setup

1. Go to your GitLab instance (e.g., gitlab.com)
2. Navigate to **User Settings** → **Access Tokens**
3. Create a new Personal Access Token with these scopes:
   - `read_api` (required)
   - `read_repository` (required)
   - `read_user` (optional, for user-specific analysis)

## Configuration

The analyzer supports configuration through environment variables, which can be set in multiple ways:

### Method 1: Using .env file (Recommended)

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your configuration:
```bash
# Required: Your GitLab token
GITLAB_TOKEN=your_gitlab_token_here

# Optional: GitLab instance URL (for self-hosted instances)
# GITLAB_URL=https://gitlab.company.com

# Optional: Analyze a specific group (e.g., PowerSchool Group)
GITLAB_GROUP_URL=https://gitlab.com/powerschoolgroup
# Or use group name directly:
# GITLAB_GROUP_URL=powerschoolgroup
# Or use group ID:
# GITLAB_GROUP_ID=12345
```

### Method 2: Export environment variables

```bash
export GITLAB_TOKEN='your_gitlab_token_here'
# Optional: Set custom GitLab URL
export GITLAB_URL='https://gitlab.company.com'
# Optional: Set group to analyze
export GITLAB_GROUP_URL='https://gitlab.com/powerschoolgroup'
```

## Usage

### Basic Usage

```bash
# With token from .env file or environment variable
python gitlab_analyzer.py

# Or provide token directly (overrides environment)
python gitlab_analyzer.py --token YOUR_GITLAB_TOKEN
```

### Advanced Usage

```bash
# Analyze specific group by ID (e.g., PowerSchool Group)
python gitlab_analyzer.py --group-id 93415483

# Analyze specific group by name or URL
python gitlab_analyzer.py --group-name powerschoolgroup

# With environment variables set in .env
# GITLAB_GROUP_URL=https://gitlab.com/powerschoolgroup
# or GITLAB_GROUP_ID=93415483
python gitlab_analyzer.py

# Analyze specific user's repositories
python gitlab_analyzer.py --token YOUR_TOKEN --user-id 67890

# Custom file size threshold (25MB for more sensitive analysis)
python gitlab_analyzer.py --token YOUR_TOKEN --threshold 25.0

# Limit analysis to first 10 repositories
python gitlab_analyzer.py --token YOUR_TOKEN --max-repos 10

# Use custom GitLab instance
python gitlab_analyzer.py --token YOUR_TOKEN --gitlab-url https://gitlab.company.com

# Custom output directory
python gitlab_analyzer.py --token YOUR_TOKEN --output-dir ./my_results
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--token` | GitLab personal access token | From GITLAB_TOKEN env var |
| `--gitlab-url` | GitLab instance URL | From GITLAB_URL env var or https://gitlab.com |
| `--threshold` | File size threshold in MB for analysis | 50.0 (GitHub warning level) |
| `--group-id` | Analyze specific group ID only | All accessible repos |
| `--user-id` | Analyze specific user ID only | All accessible repos |
| `--max-repos` | Maximum number of repositories to analyze | No limit |
| `--output-dir` | Output directory for results | ./migration_analysis |

## Output Files

The script generates multiple output files focused on GitHub migration analysis:

### 1. Complete JSON Results (`gitlab_analysis_TIMESTAMP.json`)
Contains all analysis data including:
- Repository details and migration risk assessments
- Complete list of files categorized by migration status
- GitHub-specific migration summary metrics
- Analysis timing and error information

### 2. GitHub Migration Blockers (`github_migration_blockers_TIMESTAMP.csv`)
**CRITICAL**: Files >100MB that will block GitHub migration:
- Repository name and URL
- File path and direct URL
- File size and migration status
- Specific remediation recommendations

### 3. Git LFS Candidates (`git_lfs_candidates_TIMESTAMP.csv`)
**RECOMMENDED**: Files 50-100MB that should use Git LFS:
- Repository and file details
- Performance recommendations
- Migration status information

### 4. All Large Files (`all_large_files_TIMESTAMP.csv`)
Complete list of all files above the analysis threshold with migration status

### 5. Migration Analysis Report (`analysis_report_TIMESTAMP.txt`)
Comprehensive human-readable report including:
- 🚨 Migration readiness summary with clear status indicators
- 🚫 Critical migration blockers requiring immediate action
- ⚠️ Git LFS recommendations for optimal performance
- 📋 Step-by-step migration recommendations
- 📚 Links to GitHub documentation and resources

## Example Output

```
GitLab to GitHub Migration Analysis Report
=======================================================

Analysis completed: 2024-08-15T18:33:45
Duration: 245.3 seconds
GitHub file limit: 100 MB (hard limit)
GitHub warning threshold: 50 MB (LFS recommended)

🚨 MIGRATION READINESS SUMMARY:
• Total repositories analyzed: 25
• ✅ Migration-ready repositories: 20
• ⚠️  High-risk repositories (need LFS): 3
• 🚫 BLOCKED repositories (>100MB files): 2

📊 FILE ANALYSIS:
• Migration blocker files (>100MB): 3
• Git LFS candidate files (50-100MB): 8
• Total large files found: 23
• Largest file found: 156.3 MB

🚫 CRITICAL: MIGRATION BLOCKERS (Files >100MB)
These files MUST be addressed before GitHub migration:
• mygroup/frontend-app: assets/video/demo.mp4 (156.3 MB)
  → Must use Git LFS or split file before migration

📋 MIGRATION RECOMMENDATIONS:
IMMEDIATE ACTIONS REQUIRED:
1. Address migration blocker files (>100MB) using one of these options:
   - Convert to Git LFS before migration
   - Split large files into smaller chunks
   - Remove files if no longer needed
   - Store large files in external storage (AWS S3, etc.)
```

## Performance Considerations

- **API Rate Limits**: The script includes built-in rate limiting (100ms between requests)
- **Large Repositories**: Analysis is limited to the first 50 files per repository to avoid excessive API calls
- **Memory Usage**: Results are stored in memory during analysis; very large datasets may require adjustment
- **Network**: Analysis time depends on repository count and network latency to GitLab

## Troubleshooting

### Common Issues

**Authentication Errors**
- Verify your access token has correct permissions (`read_api`, `read_repository`)
- Check token hasn't expired
- Ensure token has access to the repositories you're trying to analyze

**Rate Limiting**
- Script automatically handles rate limits with exponential backoff
- If you see frequent rate limiting, consider reducing concurrent operations

**Empty Results**
- Check if repositories have files above the threshold
- Verify repositories aren't empty
- Some repositories may have access restrictions

**Network Errors**
- Verify GitLab URL is correct and accessible
- Check firewall/proxy settings
- Ensure stable internet connection

### Debug Mode

For debugging, you can modify the script to increase verbosity by editing the logging level or adding print statements.

## Security Notes

- **Never commit your access token to version control**
- Use environment variables for tokens in production:
  ```bash
  export GITLAB_TOKEN="your_token_here"
  python gitlab_analyzer.py --token $GITLAB_TOKEN
  ```
- Tokens should have minimal required permissions
- Regularly rotate access tokens

## API Endpoints Used

The script uses these GitLab API v4 endpoints:
- `/projects` - List repositories
- `/groups/{id}/projects` - Group-specific repositories  
- `/users/{id}/projects` - User-specific repositories
- `/projects/{id}/repository/tree` - Repository file tree
- `/projects/{id}/repository/files/{file_path}` - File metadata

## License

This script is provided as-is for educational and operational purposes. Modify as needed for your environment.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve this tool.
