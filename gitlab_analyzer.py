#!/usr/bin/env python3
"""GitLab to GitHub Migration Analyzer

This script analyzes GitLab repositories via API calls to identify large files
that may cause issues during GitHub migration and provides comprehensive
reporting on GitHub compatibility and Git LFS requirements.
"""

import os
import sys
import json
import time
import argparse
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import csv
from urllib.parse import urljoin, urlparse
from collections import defaultdict
from dotenv import load_dotenv
import re
import base64


class GitLabAnalyzer:
    """GitLab API client for analyzing repository file sizes and GitHub migration compatibility."""
    
    def __init__(self, gitlab_url: str, access_token: str, file_size_threshold_mb: float = 50.0):
        """
        Initialize GitLab analyzer for GitHub migration.
        
        Args:
            gitlab_url: GitLab instance URL (e.g., 'https://gitlab.com')
            access_token: GitLab personal access token
            file_size_threshold_mb: File size threshold in MB to consider "large" (default: 50MB for GitHub warning)
        """
        self.gitlab_url = gitlab_url.rstrip('/')
        self.api_base = f"{self.gitlab_url}/api/v4"
        self.access_token = access_token
        # GitHub-specific thresholds
        self.github_warning_threshold_bytes = int(50 * 1024 * 1024)  # 50MB - GitHub warning
        self.github_limit_threshold_bytes = int(100 * 1024 * 1024)   # 100MB - GitHub hard limit
        self.file_size_threshold_bytes = int(file_size_threshold_mb * 1024 * 1024)  # User-defined threshold
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        })
        
        # Rate limiting
        self.rate_limit_delay = 0.1  # seconds between requests
        self.last_request_time = 0
        
        # Analysis results
        self.results = {
            'repositories': [],
            'large_files': [],
            'github_blockers': [],    # Files >100MB that block migration
            'lfs_candidates': [],     # Files 50-100MB that should use Git LFS
            'migration_summary': {},
            'summary': {},
            'errors': []
        }
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
        """Make rate-limited API request."""
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        
        url = urljoin(self.api_base + '/', endpoint.lstrip('/'))
        
        try:
            response = self.session.get(url, params=params)
            self.last_request_time = time.time()
            
            if response.status_code == 429:  # Rate limited
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self._make_request(endpoint, params)
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed for {url}: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.results['errors'].append(error_msg)
            return None
    
    def get_repositories(self, group_id: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict]:
        """
        Get list of repositories to analyze.
        
        Args:
            group_id: Specific group ID to analyze (optional)
            user_id: Specific user ID to analyze (optional)
            
        Returns:
            List of repository dictionaries
        """
        repositories = []
        page = 1
        per_page = 100
        
        if group_id:
            endpoint = f"/groups/{group_id}/projects"
        elif user_id:
            endpoint = f"/users/{user_id}/projects"
        else:
            endpoint = "/projects"
        
        print(f"Fetching repositories from {endpoint}...")
        
        while True:
            params = {
                'page': page,
                'per_page': per_page,
                'membership': True,
                'statistics': True,
                'with_custom_attributes': False
            }
            
            response = self._make_request(endpoint, params)
            if not response:
                break
                
            repos = response.json()
            if not repos:
                break
                
            repositories.extend(repos)
            print(f"Fetched {len(repositories)} repositories so far...")
            
            # Check if we have more pages
            if len(repos) < per_page:
                break
            page += 1
        
        print(f"Total repositories found: {len(repositories)}")
        return repositories
    
    def get_repository_tree(self, project_id: int, path: str = "", ref: str = "main") -> List[Dict]:
        """Get repository file tree."""
        all_files = []
        
        try:
            # Try main branch first, then master
            for branch in [ref, "master", "main"]:
                response = self._make_request(f"/projects/{project_id}/repository/tree", {
                    'path': path,
                    'ref': branch,
                    'recursive': True,
                    'per_page': 100
                })
                
                if response:
                    tree_data = response.json()
                    if tree_data:  # Successfully got data
                        all_files = tree_data
                        break
            
        except Exception as e:
            error_msg = f"Failed to get tree for project {project_id}: {str(e)}"
            self.results['errors'].append(error_msg)
        
        return all_files
    
    def get_file_info(self, project_id: int, file_path: str, ref: str = "main") -> Optional[Dict]:
        """Get detailed file information including size."""
        try:
            for branch in [ref, "master", "main"]:
                response = self._make_request(f"/projects/{project_id}/repository/files/{requests.utils.quote(file_path, safe='')}", {
                    'ref': branch
                })
                
                if response:
                    return response.json()
                    
        except Exception as e:
            # Don't log every file error to avoid spam
            pass
        
        return None
    
    def get_repository_statistics(self, project_id: int) -> Dict:
        """Get repository statistics including commit count."""
        stats = {
            'commit_count': 0,
            'branch_count': 0,
            'tag_count': 0
        }
        
        # Get commit count from the default branch
        response = self._make_request(f'/projects/{project_id}')
        if response:
            project_data = response.json()
            # Get statistics if available
            if 'statistics' in project_data:
                stats['commit_count'] = project_data['statistics'].get('commit_count', 0)
                stats['storage_size'] = project_data['statistics'].get('storage_size', 0)
                stats['repository_size'] = project_data['statistics'].get('repository_size', 0)
                stats['lfs_objects_size'] = project_data['statistics'].get('lfs_objects_size', 0)
            
            # Get default branch
            default_branch = project_data.get('default_branch', 'main')
            
            # Try to get commit count via commits endpoint if not in statistics
            if stats['commit_count'] == 0:
                commits_response = self._make_request(
                    f'/projects/{project_id}/repository/commits',
                    params={'per_page': 1, 'page': 1}
                )
                if commits_response and 'x-total' in commits_response.headers:
                    stats['commit_count'] = int(commits_response.headers.get('x-total', 0))
        
        return stats
    
    def parse_lfs_pointer(self, file_content: str, encoding: str) -> Optional[int]:
        """Parse Git LFS pointer file to get actual file size.
        
        Args:
            file_content: Base64 encoded file content
            encoding: File encoding from GitLab API
            
        Returns:
            Actual file size in bytes if it's an LFS pointer, None otherwise
        """
        try:
            if encoding == 'base64':
                # Decode base64 content
                decoded_content = base64.b64decode(file_content).decode('utf-8')
                
                # Check if it's a Git LFS pointer file
                if 'version https://git-lfs.github.com' in decoded_content:
                    # Parse the size from LFS pointer
                    for line in decoded_content.split('\n'):
                        if line.strip().startswith('size '):
                            return int(line.strip().split(' ')[1])
        except Exception as e:
            # If we can't parse it, it's not an LFS pointer
            pass
        
        return None
    
    def analyze_repository(self, repo: Dict) -> Dict:
        """Analyze a single repository for large files and collect metrics."""
        project_id = repo['id']
        repo_name = repo['name']
        repo_path = repo['path_with_namespace']
        
        print(f"Analyzing repository: {repo_path}")
        
        repo_analysis = {
            'id': project_id,
            'name': repo_name,
            'path': repo_path,
            'url': repo['web_url'],
            'large_files': [],
            'github_blockers': [],      # Files >100MB that block migration
            'lfs_candidates': [],       # Files 50-100MB that should use Git LFS
            'migration_risk': 'low',    # low, medium, high, blocker
            'total_files': 0,
            'total_commits': 0,         # NEW: Number of commits
            'total_size_bytes': 0,      # Total size of all files analyzed
            'repository_size_bytes': 0, # NEW: Total repository size from GitLab
            'storage_size_bytes': 0,    # NEW: Total storage size including LFS
            'lfs_size_bytes': 0,        # NEW: LFS objects size
            'largest_file_size': 0,
            'errors': []
        }
        
        # Get repository statistics
        stats = self.get_repository_statistics(project_id)
        repo_analysis['total_commits'] = stats.get('commit_count', 0)
        repo_analysis['repository_size_bytes'] = stats.get('repository_size', 0)
        repo_analysis['storage_size_bytes'] = stats.get('storage_size', 0)
        repo_analysis['lfs_size_bytes'] = stats.get('lfs_objects_size', 0)
        
        # Get repository tree
        tree = self.get_repository_tree(project_id)
        
        if not tree:
            repo_analysis['errors'].append("Could not retrieve repository tree")
            return repo_analysis
        
        # Count all files recursively
        def count_files_recursive(project_id, path=""):
            """Recursively count all files in repository."""
            total = 0
            tree_items = self.get_repository_tree(project_id, path)
            if tree_items:
                for item in tree_items:
                    if item['type'] == 'blob':
                        total += 1
                    elif item['type'] == 'tree':
                        # Recursively count files in subdirectories (limit depth to avoid API overload)
                        if path.count('/') < 2:  # Limit recursion depth
                            total += count_files_recursive(project_id, item['path'])
            return total
        
        # Filter for blob files (not directories) at root level
        files = [item for item in tree if item['type'] == 'blob']
        
        # For total file count, use a more comprehensive approach
        # Try to get all files with pagination
        all_files = []
        page = 1
        per_page = 100
        while True:
            response = self._make_request(
                f'/projects/{project_id}/repository/tree',
                params={'recursive': 'true', 'per_page': per_page, 'page': page}
            )
            if response:
                items = response.json()
                file_items = [item for item in items if item['type'] == 'blob']
                all_files.extend(file_items)
                
                # Check if there are more pages
                if len(items) < per_page:
                    break
                page += 1
                
                # Limit to prevent excessive API calls
                if page > 10:  # Max 1000 files
                    break
            else:
                break
        
        repo_analysis['total_files'] = len(all_files)
        
        # Format repository size for display
        repo_size_mb = repo_analysis['repository_size_bytes'] / (1024 * 1024)
        storage_size_mb = repo_analysis['storage_size_bytes'] / (1024 * 1024)
        
        print(f"  Repository stats: {repo_analysis['total_files']} files, "
              f"{repo_analysis['total_commits']} commits, "
              f"{repo_size_mb:.1f} MB repo size, "
              f"{storage_size_mb:.1f} MB total storage")
        
        # Analyze each file for large file detection
        # Use all_files if available, otherwise use files from root
        files_to_analyze = all_files if all_files else files
        for file_item in files_to_analyze[:100]:  # Increased limit since we have better data
            file_path = file_item['path']
            
            # Get detailed file info
            file_info = self.get_file_info(project_id, file_path)
            
            if file_info and 'size' in file_info:
                file_size = file_info['size']
                encoding = file_info.get('encoding', 'unknown')
                
                # Check if this is a Git LFS pointer file
                actual_file_size = file_size
                is_lfs_pointer = False
                
                if file_size < 1000 and encoding == 'base64':  # LFS pointers are small
                    lfs_size = self.parse_lfs_pointer(file_info.get('content', ''), encoding)
                    if lfs_size is not None:
                        actual_file_size = lfs_size
                        is_lfs_pointer = True
                        print(f"    🔗 LFS POINTER DETECTED: {file_path} - Actual size: {lfs_size / (1024*1024):.2f} MB")
                
                repo_analysis['total_size_bytes'] += actual_file_size
                repo_analysis['largest_file_size'] = max(repo_analysis['largest_file_size'], actual_file_size)
                
                # Categorize files based on GitHub limits (use actual size)
                file_data = {
                    'repository': repo_path,
                    'repository_url': repo['web_url'],
                    'file_path': file_path,
                    'file_url': f"{repo['web_url']}/-/blob/main/{file_path}",
                    'size_bytes': actual_file_size,
                    'size_mb': round(actual_file_size / (1024 * 1024), 2),
                    'encoding': encoding,
                    'is_lfs_pointer': is_lfs_pointer,
                    'pointer_size_bytes': file_size if is_lfs_pointer else None
                }
                
                # GitHub migration analysis (use actual file size)
                if actual_file_size >= self.github_limit_threshold_bytes:  # >100MB - Migration blocker
                    file_data['migration_status'] = 'BLOCKER'
                    file_data['recommendation'] = 'Must use Git LFS or split file before migration'
                    repo_analysis['github_blockers'].append(file_data)
                    self.results['github_blockers'].append(file_data)
                    repo_analysis['migration_risk'] = 'blocker'
                    print(f"    🚫 MIGRATION BLOCKER: {file_path} ({file_data['size_mb']} MB) - Exceeds GitHub 100MB limit")
                
                elif actual_file_size >= self.github_warning_threshold_bytes:  # 50-100MB - LFS candidate
                    file_data['migration_status'] = 'LFS_CANDIDATE'
                    file_data['recommendation'] = 'Consider using Git LFS for better performance'
                    repo_analysis['lfs_candidates'].append(file_data)
                    self.results['lfs_candidates'].append(file_data)
                    if repo_analysis['migration_risk'] not in ['blocker', 'high']:
                        repo_analysis['migration_risk'] = 'high'
                    print(f"    ⚠️  LFS CANDIDATE: {file_path} ({file_data['size_mb']} MB) - Should use Git LFS")
                
                # Also track user-defined large files
                if actual_file_size >= self.file_size_threshold_bytes:
                    if actual_file_size < self.github_warning_threshold_bytes:
                        file_data['migration_status'] = 'OK'
                        file_data['recommendation'] = 'File size acceptable for GitHub'
                        if repo_analysis['migration_risk'] == 'low':
                            repo_analysis['migration_risk'] = 'medium'
                    repo_analysis['large_files'].append(file_data)
                    self.results['large_files'].append(file_data)
        
        return repo_analysis
    
    def run_analysis(self, group_id: Optional[int] = None, user_id: Optional[int] = None, 
                    max_repos: Optional[int] = None) -> Dict:
        """Run complete analysis on repositories."""
        print("Starting GitLab repository analysis...")
        print(f"File size threshold: {self.file_size_threshold_bytes / (1024*1024):.1f} MB")
        
        start_time = datetime.now()
        
        # Get repositories
        repositories = self.get_repositories(group_id, user_id)
        
        if max_repos:
            repositories = repositories[:max_repos]
            print(f"Limited analysis to first {max_repos} repositories")
        
        # Analyze each repository
        total_large_files = 0
        total_repos_with_large_files = 0
        migration_blocked_repos = 0
        high_risk_repos = 0
        
        for i, repo in enumerate(repositories, 1):
            print(f"\n[{i}/{len(repositories)}] Processing repository...")
            
            repo_analysis = self.analyze_repository(repo)
            self.results['repositories'].append(repo_analysis)
            
            if repo_analysis['large_files']:
                total_repos_with_large_files += 1
                total_large_files += len(repo_analysis['large_files'])
            
            # Track migration risks
            if repo_analysis['migration_risk'] == 'blocker':
                migration_blocked_repos += 1
            elif repo_analysis['migration_risk'] == 'high':
                high_risk_repos += 1
        
        # Calculate aggregate metrics
        total_commits = sum(repo['total_commits'] for repo in self.results['repositories'])
        total_files = sum(repo['total_files'] for repo in self.results['repositories'])
        total_repo_size = sum(repo['repository_size_bytes'] for repo in self.results['repositories'])
        total_storage_size = sum(repo['storage_size_bytes'] for repo in self.results['repositories'])
        
        # Generate summary
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Generate migration summary
        self.results['migration_summary'] = {
            'total_repositories_analyzed': len(repositories),
            'migration_blocked_repositories': migration_blocked_repos,
            'high_risk_repositories': high_risk_repos,
            'github_blocker_files': len(self.results['github_blockers']),
            'lfs_candidate_files': len(self.results['lfs_candidates']),
            'migration_ready_repositories': len(repositories) - migration_blocked_repos - high_risk_repos,
            'github_file_limit_mb': self.github_limit_threshold_bytes / (1024*1024),
            'github_warning_threshold_mb': self.github_warning_threshold_bytes / (1024*1024)
        }
        
        self.results['summary'] = {
            'analysis_start_time': start_time.isoformat(),
            'analysis_end_time': end_time.isoformat(),
            'analysis_duration_seconds': duration.total_seconds(),
            'total_repositories_analyzed': len(repositories),
            'repositories_with_large_files': total_repos_with_large_files,
            'total_large_files_found': total_large_files,
            'file_size_threshold_mb': self.file_size_threshold_bytes / (1024*1024),
            'largest_file_found_mb': max([f['size_mb'] for f in self.results['large_files']], default=0),
            # New aggregate metrics
            'total_files_across_repos': total_files,
            'total_commits_across_repos': total_commits,
            'total_repository_size_gb': round(total_repo_size / (1024*1024*1024), 2),
            'total_storage_size_gb': round(total_storage_size / (1024*1024*1024), 2),
            'average_files_per_repo': round(total_files / len(repositories), 1) if repositories else 0,
            'average_commits_per_repo': round(total_commits / len(repositories), 1) if repositories else 0,
            'average_repo_size_mb': round(total_repo_size / (1024*1024) / len(repositories), 1) if repositories else 0
        }
        
        return self.results
    
    def save_results(self, output_dir: str = "output"):
        """Save analysis results to files."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save complete JSON results
        json_file = f"{output_dir}/gitlab_analysis_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Complete results saved to: {json_file}")
        
        # Save repository summary CSV with new metrics
        repo_summary_csv = f"{output_dir}/repository_summary_{timestamp}.csv"
        with open(repo_summary_csv, 'w', newline='') as f:
            fieldnames = [
                'repository', 'url', 'total_files', 'total_commits', 
                'repository_size_mb', 'storage_size_mb', 'lfs_size_mb',
                'migration_risk', 'blocker_files', 'lfs_candidate_files', 'large_files'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for repo in self.results['repositories']:
                writer.writerow({
                    'repository': repo['path'],
                    'url': repo['url'],
                    'total_files': repo['total_files'],
                    'total_commits': repo['total_commits'],
                    'repository_size_mb': round(repo['repository_size_bytes'] / (1024*1024), 2),
                    'storage_size_mb': round(repo['storage_size_bytes'] / (1024*1024), 2),
                    'lfs_size_mb': round(repo['lfs_size_bytes'] / (1024*1024), 2),
                    'migration_risk': repo['migration_risk'],
                    'blocker_files': len(repo['github_blockers']),
                    'lfs_candidate_files': len(repo['lfs_candidates']),
                    'large_files': len(repo['large_files'])
                })
        print(f"Repository summary CSV saved to: {repo_summary_csv}")
        
        # Save GitHub migration blocker files CSV
        if self.results['github_blockers']:
            blockers_csv = f"{output_dir}/github_migration_blockers_{timestamp}.csv"
            with open(blockers_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'repository', 'file_path', 'size_mb', 'size_bytes', 'migration_status', 'recommendation', 'file_url',
                    'repository_url', 'encoding', 'is_lfs_pointer', 'pointer_size_bytes'
                ])
                writer.writeheader()
                writer.writerows(self.results['github_blockers'])
            print(f"GitHub migration blockers CSV saved to: {blockers_csv}")
        
        # Save Git LFS candidates CSV
        if self.results['lfs_candidates']:
            lfs_csv = f"{output_dir}/git_lfs_candidates_{timestamp}.csv"
            with open(lfs_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'repository', 'file_path', 'size_mb', 'size_bytes', 'migration_status', 'recommendation', 'file_url',
                    'repository_url', 'encoding', 'is_lfs_pointer', 'pointer_size_bytes'
                ])
                writer.writeheader()
                writer.writerows(self.results['lfs_candidates'])
            print(f"Git LFS candidates CSV saved to: {lfs_csv}")
        
        # Save all large files CSV for reference
        if self.results['large_files']:
            csv_file = f"{output_dir}/all_large_files_{timestamp}.csv"
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'repository', 'file_path', 'size_mb', 'size_bytes', 'migration_status', 'recommendation', 'file_url',
                    'repository_url', 'encoding', 'is_lfs_pointer', 'pointer_size_bytes'
                ])
                writer.writeheader()
                writer.writerows(self.results['large_files'])
            print(f"All large files CSV saved to: {csv_file}")
        
        # Save summary report
        report_file = f"{output_dir}/analysis_report_{timestamp}.txt"
        with open(report_file, 'w') as f:
            self._write_summary_report(f)
        print(f"Summary report saved to: {report_file}")
    
    def _write_summary_report(self, file_handle):
        """Write human-readable GitHub migration summary report."""
        summary = self.results['summary']
        migration = self.results['migration_summary']
        
        file_handle.write("GitLab to GitHub Migration Analysis Report\n")
        file_handle.write("=" * 55 + "\n\n")
        
        file_handle.write(f"Analysis completed: {summary['analysis_end_time']}\n")
        file_handle.write(f"Duration: {summary['analysis_duration_seconds']:.1f} seconds\n")
        file_handle.write(f"GitHub file limit: {migration['github_file_limit_mb']:.0f} MB (hard limit)\n")
        file_handle.write(f"GitHub warning threshold: {migration['github_warning_threshold_mb']:.0f} MB (LFS recommended)\n\n")
        
        file_handle.write("🚨 MIGRATION READINESS SUMMARY:\n")
        file_handle.write(f"• Total repositories analyzed: {migration['total_repositories_analyzed']}\n")
        file_handle.write(f"• ✅ Migration-ready repositories: {migration['migration_ready_repositories']}\n")
        file_handle.write(f"• ⚠️  High-risk repositories (need LFS): {migration['high_risk_repositories']}\n")
        file_handle.write(f"• 🚫 BLOCKED repositories (>100MB files): {migration['migration_blocked_repositories']}\n\n")
        
        file_handle.write("📊 FILE ANALYSIS:\n")
        file_handle.write(f"• Migration blocker files (>100MB): {migration['github_blocker_files']}\n")
        file_handle.write(f"• Git LFS candidate files (50-100MB): {migration['lfs_candidate_files']}\n")
        file_handle.write(f"• Total large files found: {summary['total_large_files_found']}\n")
        if summary['largest_file_found_mb'] > 0:
            file_handle.write(f"• Largest file found: {summary['largest_file_found_mb']:.1f} MB\n")
        file_handle.write("\n")
        
        if migration['migration_blocked_repositories'] > 0:
            file_handle.write("🚫 CRITICAL: MIGRATION BLOCKERS (Files >100MB)\n")
            file_handle.write("These files MUST be addressed before GitHub migration:\n")
            for blocker in sorted(self.results['github_blockers'], key=lambda x: x['size_mb'], reverse=True):
                file_handle.write(f"• {blocker['repository']}: {blocker['file_path']} ({blocker['size_mb']} MB)\n")
                file_handle.write(f"  → {blocker['recommendation']}\n")
            file_handle.write("\n")
        
        if migration['lfs_candidate_files'] > 0:
            file_handle.write("⚠️  RECOMMENDED: GIT LFS CANDIDATES (50-100MB Files)\n")
            file_handle.write("These files should use Git LFS for optimal performance:\n")
            for candidate in sorted(self.results['lfs_candidates'], key=lambda x: x['size_mb'], reverse=True):
                file_handle.write(f"• {candidate['repository']}: {candidate['file_path']} ({candidate['size_mb']} MB)\n")
            file_handle.write("\n")
        
        # Migration recommendations
        file_handle.write("📋 MIGRATION RECOMMENDATIONS:\n\n")
        
        if migration['migration_blocked_repositories'] > 0:
            file_handle.write("IMMEDIATE ACTIONS REQUIRED:\n")
            file_handle.write("1. Address migration blocker files (>100MB) using one of these options:\n")
            file_handle.write("   - Convert to Git LFS before migration\n")
            file_handle.write("   - Split large files into smaller chunks\n")
            file_handle.write("   - Remove files if no longer needed\n")
            file_handle.write("   - Store large files in external storage (AWS S3, etc.)\n\n")
        
        if migration['lfs_candidate_files'] > 0:
            file_handle.write("RECOMMENDED ACTIONS:\n")
            file_handle.write("1. Convert 50-100MB files to Git LFS for better performance:\n")
            file_handle.write("   - Install Git LFS: `git lfs install`\n")
            file_handle.write("   - Track file patterns: `git lfs track \"*.extension\"`\n")
            file_handle.write("   - Commit .gitattributes: `git add .gitattributes && git commit`\n\n")
        
        if migration['migration_ready_repositories'] == migration['total_repositories_analyzed']:
            file_handle.write("✅ EXCELLENT: All repositories are ready for GitHub migration!\n\n")
        
        file_handle.write("📚 ADDITIONAL RESOURCES:\n")
        file_handle.write("• GitHub file size limits: https://docs.github.com/en/repositories/working-with-files/managing-large-files\n")
        file_handle.write("• Git LFS documentation: https://git-lfs.github.io/\n")
        file_handle.write("• GitHub migration guide: https://docs.github.com/en/migrations\n\n")
        
        if self.results['errors']:
            file_handle.write("⚠️  ERRORS ENCOUNTERED:\n")
            for error in self.results['errors']:
                file_handle.write(f"• {error}\n")


def parse_group_from_url(url_or_name):
    """Parse group name or ID from GitLab URL or group name.
    
    Args:
        url_or_name: Can be:
            - Full URL: https://gitlab.com/powerschoolgroup
            - Group name: powerschoolgroup
            - Group ID: 12345
    
    Returns:
        Tuple of (group_name, group_id) where one will be None
    """
    if not url_or_name:
        return None, None
    
    # Check if it's a numeric ID
    if str(url_or_name).isdigit():
        return None, int(url_or_name)
    
    # Try to parse as URL
    if url_or_name.startswith('http'):
        parsed = urlparse(url_or_name)
        path_parts = parsed.path.strip('/').split('/')
        if path_parts and path_parts[0]:
            return path_parts[0], None
    
    # Assume it's a group name
    return url_or_name, None


def main():
    """Main entry point for GitLab to GitHub migration analysis."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Parse group from environment if provided
    env_group_url = os.getenv('GITLAB_GROUP_URL')
    env_group_name, env_group_id = parse_group_from_url(env_group_url)
    
    # Override with specific ID if provided
    if os.getenv('GITLAB_GROUP_ID'):
        env_group_id = int(os.getenv('GITLAB_GROUP_ID'))
        env_group_name = None
    
    parser = argparse.ArgumentParser(
        description='Analyze GitLab repositories for GitHub migration compatibility',
        epilog='This tool identifies files that exceed GitHub\'s limits and provides migration recommendations.'
    )
    parser.add_argument('--gitlab-url', 
                       default=os.getenv('GITLAB_URL', 'https://gitlab.com'), 
                       help='GitLab instance URL (default: https://gitlab.com or GITLAB_URL env var)')
    parser.add_argument('--token', 
                       default=os.getenv('GITLAB_TOKEN'),
                       help='GitLab personal access token (can be set via GITLAB_TOKEN env var)')
    parser.add_argument('--threshold', type=float, 
                       default=float(os.getenv('THRESHOLD_MB', '50.0')),
                       help='File size threshold in MB for analysis (default: 50.0 - GitHub warning threshold)')
    parser.add_argument('--group-id', type=int,
                       default=env_group_id,
                       help='Analyze specific group ID only (can be set via GITLAB_GROUP_URL or GITLAB_GROUP_ID env var)')
    parser.add_argument('--group-name', type=str,
                       default=env_group_name,
                       help='Analyze specific group by name (can be set via GITLAB_GROUP_URL env var)')
    parser.add_argument('--user-id', type=int,
                       help='Analyze specific user ID only')
    parser.add_argument('--max-repos', type=int,
                       help='Maximum number of repositories to analyze (useful for testing)')
    parser.add_argument('--output-dir', default='migration_analysis',
                       help='Output directory for results (default: migration_analysis)')
    
    args = parser.parse_args()
    
    # Check if token is provided
    if not args.token:
        print("ERROR: GitLab token is required. Provide via --token argument or GITLAB_TOKEN environment variable.")
        print("\nYou can set it in a .env file:")
        print("  GITLAB_TOKEN=your_token_here")
        print("\nOr export it as an environment variable:")
        print("  export GITLAB_TOKEN=your_token_here")
        sys.exit(1)
    
    # Initialize analyzer
    analyzer = GitLabAnalyzer(
        gitlab_url=args.gitlab_url,
        access_token=args.token,
        file_size_threshold_mb=args.threshold
    )
    
    # If group name is provided, we need to fetch the group ID
    group_id_to_use = args.group_id
    if args.group_name and not args.group_id:
        print(f"Looking up group '{args.group_name}'...")
        # Make API call to get group ID from name
        response = analyzer._make_request(f'/groups/{args.group_name}')
        if response:
            group_data = response.json()
            group_id_to_use = group_data.get('id')
            print(f"Found group '{args.group_name}' with ID: {group_id_to_use}")
        else:
            print(f"WARNING: Could not find group '{args.group_name}', analyzing all accessible repositories")
    
    try:
        # Run analysis
        results = analyzer.run_analysis(
            group_id=group_id_to_use,
            user_id=args.user_id,
            max_repos=args.max_repos
        )
        
        # Print summary to console
        print("\n" + "="*60)
        print("ANALYSIS COMPLETE")
        print("="*60)
        summary = results['summary']
        print(f"Repositories analyzed: {summary['total_repositories_analyzed']}")
        print(f"Large files found: {summary['total_large_files_found']}")
        print(f"Repositories with large files: {summary['repositories_with_large_files']}")
        print(f"Largest file: {summary['largest_file_found_mb']:.1f} MB")
        print(f"\nAggregate Metrics:")
        print(f"Total files: {summary['total_files_across_repos']:,}")
        print(f"Total commits: {summary['total_commits_across_repos']:,}")
        print(f"Total repository size: {summary['total_repository_size_gb']:.2f} GB")
        
        # Save results
        analyzer.save_results(args.output_dir)
        
        print(f"\nResults saved to '{args.output_dir}' directory")
        
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
