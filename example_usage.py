#!/usr/bin/env python3
"""
Example usage of the GitLab Large File Analyzer

This script demonstrates how to use the GitLabAnalyzer class programmatically
instead of through the command line interface.
"""

import os
from dotenv import load_dotenv
from gitlab_analyzer import GitLabAnalyzer

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Configuration
    GITLAB_URL = os.getenv('GITLAB_URL', 'https://gitlab.com')  # From env or default
    ACCESS_TOKEN = os.getenv('GITLAB_TOKEN')  # Get from environment variable
    
    if not ACCESS_TOKEN:
        print("ERROR: GitLab token is required.")
        print("\nPlease set GITLAB_TOKEN in one of these ways:")
        print("1. Create a .env file with: GITLAB_TOKEN=your_token_here")
        print("2. Export environment variable: export GITLAB_TOKEN='your_token_here'")
        return
    
    # Initialize analyzer
    analyzer = GitLabAnalyzer(
        gitlab_url=GITLAB_URL,
        access_token=ACCESS_TOKEN,
        file_size_threshold_mb=25.0  # 25MB threshold
    )
    
    print("Starting GitLab analysis...")
    
    # Run analysis (limit to 5 repos for demo)
    results = analyzer.run_analysis(max_repos=5)
    
    # Print some results
    print(f"\nFound {results['summary']['total_large_files_found']} large files")
    
    if results['large_files']:
        print("\nLargest files found:")
        # Sort by size and show top 5
        sorted_files = sorted(results['large_files'], key=lambda x: x['size_mb'], reverse=True)
        for file_info in sorted_files[:5]:
            print(f"  {file_info['repository']}: {file_info['file_path']} ({file_info['size_mb']} MB)")
    
    # Save results
    analyzer.save_results("example_output")
    print("\nResults saved to example_output/ directory")

if __name__ == '__main__':
    main()
