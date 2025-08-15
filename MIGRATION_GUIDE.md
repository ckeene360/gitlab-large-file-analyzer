# GitLab to GitHub Migration Guide

This guide helps you understand and resolve issues identified by the GitLab to GitHub Migration Analyzer.

## Understanding GitHub File Size Limits

### Hard Limits (Migration Blockers)
- **100MB per file**: Absolute maximum file size GitHub accepts
- Files larger than 100MB will **completely block** your repository push
- These files MUST be addressed before migration

### Recommended Limits (Performance Issues)
- **50MB per file**: GitHub starts showing warnings
- Files 50-100MB cause slow clone/fetch operations
- Should use Git LFS for optimal performance

## Migration Risk Categories

### 🚫 BLOCKER (>100MB)
**Status**: Cannot migrate to GitHub
**Action**: REQUIRED before migration
**Options**:
1. **Git LFS Conversion** (Recommended)
2. **File Splitting** (for data files)
3. **External Storage** (AWS S3, etc.)
4. **File Removal** (if no longer needed)

### ⚠️ HIGH RISK (50-100MB)
**Status**: Can migrate but with performance issues
**Action**: Strongly recommended
**Solution**: Convert to Git LFS

### ✅ MEDIUM/LOW RISK (<50MB)
**Status**: Migration ready
**Action**: Optional optimization

## Step-by-Step Remediation

### Option 1: Git LFS (Recommended for most cases)

#### 1. Install Git LFS
```bash
# Install Git LFS (if not already installed)
git lfs install
```

#### 2. Track Large Files
```bash
# Track specific file types
git lfs track "*.mp4"
git lfs track "*.zip"
git lfs track "*.tar.gz"

# Track specific files
git lfs track "path/to/large-file.bin"

# Track files in a directory
git lfs track "assets/videos/*"
```

#### 3. Commit Changes
```bash
# Add the .gitattributes file
git add .gitattributes

# Commit the LFS configuration
git commit -m "Configure Git LFS for large files"

# Add your large files (they'll now be tracked by LFS)
git add path/to/large-file.bin
git commit -m "Add large files with LFS"
```

#### 4. Verify LFS Setup
```bash
# Check which files are tracked by LFS
git lfs track

# Check LFS status
git lfs status

# List LFS files
git lfs ls-files
```

### Option 2: File Splitting (for data files)

#### For CSV/Data Files:
```bash
# Split large CSV files
split -l 10000 large-dataset.csv dataset-part-
```

#### For Archive Files:
```bash
# Split large archives
split -b 50M large-archive.tar.gz archive-part-
```

### Option 3: External Storage

#### Move to Cloud Storage:
1. Upload files to AWS S3, Google Cloud Storage, etc.
2. Replace files with download scripts or URLs
3. Update documentation with access instructions

### Option 4: File Removal

#### For Obsolete Files:
```bash
# Remove from Git history completely
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch path/to/large-file' --prune-empty --tag-name-filter cat -- --all

# Force push to update remote
git push origin --force --all
```

## Common File Types and Recommendations

| File Type | Size Range | Recommendation |
|-----------|------------|----------------|
| Videos (mp4, avi, mov) | >50MB | Git LFS |
| Archives (zip, tar.gz) | >50MB | Git LFS or Extract |
| Datasets (csv, json) | >50MB | Git LFS or Split |
| Binaries (exe, dll) | >50MB | Git LFS |
| Images (large PSD, TIFF) | >50MB | Git LFS |
| Documentation (PDF) | >50MB | Git LFS or Compress |
| Databases (sql, db) | Any size | External storage |

## Pre-Migration Checklist

### Before Running the Analyzer:
- [ ] Obtain GitLab personal access token with `read_api` and `read_repository` permissions
- [ ] Identify which repositories/groups you want to migrate
- [ ] Ensure you have sufficient disk space for LFS if needed

### After Running the Analyzer:
- [ ] Review migration blocker files (>100MB) - **CRITICAL**
- [ ] Plan Git LFS implementation for 50-100MB files
- [ ] Estimate Git LFS storage costs (if applicable)
- [ ] Prepare team for Git LFS workflow changes
- [ ] Test migration with a small repository first

### Before Final Migration:
- [ ] All blocker files addressed
- [ ] Git LFS properly configured and tested
- [ ] Team trained on Git LFS commands
- [ ] Backup of original GitLab repositories
- [ ] Migration timeline communicated to team

## Git LFS Workflow for Teams

### For Developers:
```bash
# Clone repository (LFS files downloaded automatically)
git clone <repository-url>

# Normal Git operations work the same
git add .
git commit -m "Update files"
git push

# Manually manage LFS if needed
git lfs pull    # Download LFS files
git lfs push    # Upload LFS files
```

### Storage Considerations:
- GitHub includes 1GB of free LFS storage per account
- Additional storage: $5/month per 50GB
- Bandwidth: 1GB free per month, then $5 per 50GB

## Troubleshooting Common Issues

### Issue: "file exceeds GitHub's file size limit of 100.00 MB"
**Solution**: File must be converted to Git LFS or removed before migration

### Issue: "this exceeds GitHub's file size limit of 100.00 MB"
**Solution**: Use Git LFS or split the file into smaller parts

### Issue: Slow clone/fetch operations
**Solution**: Convert large files (>50MB) to Git LFS

### Issue: High LFS storage costs
**Solutions**:
1. Audit files - remove unnecessary large files
2. Use external storage for archival data
3. Implement LFS file retention policies

## Testing Migration

### Test Process:
1. **Select a small, representative repository**
2. **Apply all remediation steps**
3. **Test migration to a temporary GitHub repository**
4. **Verify all files are accessible and properly tracked**
5. **Test clone/fetch performance**
6. **Scale to remaining repositories**

## Resources

- [GitHub File Size Limits Documentation](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Git LFS Documentation](https://git-lfs.github.io/)
- [GitHub Migration Guide](https://docs.github.com/en/migrations)
- [Git LFS Tutorial](https://github.com/git-lfs/git-lfs/wiki/Tutorial)

## Support

If you encounter issues during migration:
1. Check the error messages against this guide
2. Verify Git LFS installation and configuration
3. Test with a small repository first
4. Consider reaching out to GitHub Support for complex cases
