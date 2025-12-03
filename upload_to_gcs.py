#!/usr/bin/env python3
"""
Script to upload local data/ directory to Google Cloud Storage.
Can be run from local development environment.

Usage:
    python upload_to_gcs.py
    python upload_to_gcs.py --bucket-name custom-bucket-name
    python upload_to_gcs.py --project-id your-project-id
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from google.cloud import storage
except ImportError:
    print("❌ Error: google-cloud-storage not installed")
    print("   Install it with: pip install google-cloud-storage")
    sys.exit(1)

import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def upload_data_to_gcs(
    bucket_name: str = "deep-alpha-copilot-data",
    project_id: str = None,
    local_data_dir: Path = None,
    dry_run: bool = False
) -> int:
    """
    Upload local data directory to Google Cloud Storage.
    
    Args:
        bucket_name: GCS bucket name
        project_id: GCP project ID (from env var if not provided)
        local_data_dir: Local data directory (defaults to ./data)
        dry_run: If True, only show what would be uploaded without actually uploading
    
    Returns:
        Number of files uploaded
    """
    # Get project ID from environment if not provided
    if not project_id:
        project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            logger.error("❌ GCP_PROJECT_ID not found in environment variables")
            logger.error("   Set it with: export GCP_PROJECT_ID=your-project-id")
            logger.error("   Or pass it with: --project-id your-project-id")
            return 0
    
    # Get local data directory
    if local_data_dir is None:
        local_data_dir = Path(__file__).parent / "data"
    
    if not local_data_dir.exists():
        logger.error(f"❌ Data directory not found: {local_data_dir}")
        return 0
    
    logger.info(f"📤 Uploading data from {local_data_dir} to gs://{bucket_name}/data/")
    logger.info(f"   Project: {project_id}")
    logger.info(f"   Bucket: {bucket_name}")
    
    if dry_run:
        logger.info("   [DRY RUN MODE - No files will be uploaded]")
    
    # Initialize GCS client
    try:
        client = storage.Client(project=project_id)
    except Exception as e:
        logger.error(f"❌ Failed to initialize GCS client: {e}")
        logger.error("   Make sure you're authenticated: gcloud auth application-default login")
        return 0
    
    # Get or create bucket
    try:
        bucket = client.get_bucket(bucket_name)
        logger.info(f"✅ Using existing bucket: {bucket_name}")
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            if dry_run:
                logger.info(f"   [Would create bucket: {bucket_name}]")
                bucket = None
            else:
                logger.info(f"   Bucket {bucket_name} not found, creating...")
                try:
                    bucket = client.create_bucket(bucket_name, location="us-central1")
                    logger.info(f"✅ Created new bucket: {bucket_name}")
                except Exception as create_error:
                    logger.error(f"❌ Failed to create bucket: {create_error}")
                    return 0
        else:
            logger.error(f"❌ Error accessing bucket: {e}")
            return 0
    
    if bucket is None and not dry_run:
        return 0
    
    # Upload files (excluding ML models)
    count = 0
    total_size = 0
    excluded_count = 0
    
    # Exclude patterns
    exclude_patterns = [
        '**/saved_models/**',  # ML model files
        '**/*.joblib',  # Any joblib files
        '**/models/**',  # Any models directory
    ]
    
    try:
        for local_file in local_data_dir.rglob("*"):
            if local_file.is_file():
                # Skip ML model files
                if 'saved_models' in str(local_file) or local_file.suffix == '.joblib':
                    excluded_count += 1
                    continue
                
                # Calculate relative path
                try:
                    relative_path = local_file.relative_to(local_data_dir)
                    cloud_path = f"data/{relative_path}"
                except ValueError:
                    cloud_path = f"data/{local_file.name}"
                
                file_size = local_file.stat().st_size
                total_size += file_size
                
                if dry_run:
                    logger.info(f"   [Would upload] {relative_path} ({file_size:,} bytes)")
                else:
                    try:
                        blob = bucket.blob(cloud_path)
                        blob.upload_from_filename(str(local_file))
                        count += 1
                        
                        if count % 10 == 0:
                            logger.info(f"   Uploaded {count} files...")
                    except Exception as upload_error:
                        logger.error(f"   ❌ Failed to upload {relative_path}: {upload_error}")
        
        if dry_run:
            logger.info(f"   [Would upload] {count} files ({total_size:,} bytes total)")
            logger.info(f"   [Would exclude] {excluded_count} ML model files")
            return 0
        else:
            logger.info(f"✅ Uploaded {count} files ({total_size:,} bytes) to Cloud Storage")
            if excluded_count > 0:
                logger.info(f"⏭️  Excluded {excluded_count} ML model files (as requested)")
            return count
            
    except Exception as e:
        logger.error(f"❌ Error uploading files: {e}")
        return count


def main():
    parser = argparse.ArgumentParser(
        description="Upload local data/ directory to Google Cloud Storage"
    )
    parser.add_argument(
        "--bucket-name",
        default="deep-alpha-copilot-data",
        help="GCS bucket name (default: deep-alpha-copilot-data)"
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="GCP project ID (default: from GCP_PROJECT_ID env var)"
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        type=Path,
        help="Local data directory (default: ./data)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading"
    )
    
    args = parser.parse_args()
    
    # Check authentication
    try:
        from google.auth import default
        credentials, project = default()
        if not args.project_id:
            args.project_id = project
        logger.info(f"✅ Authenticated as: {credentials.service_account_email if hasattr(credentials, 'service_account_email') else 'User credentials'}")
    except Exception as e:
        logger.warning(f"⚠️  Could not verify authentication: {e}")
        logger.warning("   Run: gcloud auth application-default login")
    
    # Upload data
    count = upload_data_to_gcs(
        bucket_name=args.bucket_name,
        project_id=args.project_id,
        local_data_dir=args.data_dir,
        dry_run=args.dry_run
    )
    
    if count > 0:
        logger.info(f"\n✅ Successfully uploaded {count} files!")
        logger.info(f"   View in console: https://console.cloud.google.com/storage/browser/{args.bucket_name}/data")
    elif not args.dry_run:
        logger.warning("\n⚠️  No files were uploaded. Check the errors above.")
    
    return 0 if count > 0 or args.dry_run else 1


if __name__ == "__main__":
    sys.exit(main())

