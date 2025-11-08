"""
Cloud Storage helper for deep_alpha_copilot.
Manages data persistence between Cloud Storage and local cache.

Environment-aware:
- Local development: Skips Cloud Storage operations (uses ./data/)
- Production (Cloud Run): Syncs with Cloud Storage bucket
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Check if running in production
IS_PRODUCTION = bool(os.getenv("K_SERVICE"))

if IS_PRODUCTION:
    try:
        from google.cloud import storage
        STORAGE_AVAILABLE = True
    except ImportError:
        STORAGE_AVAILABLE = False
        logger.warning("google-cloud-storage not available")
else:
    STORAGE_AVAILABLE = False


class DataStorageManager:
    """
    Manage data persistence using Cloud Storage.

    In local development: No-op (just logs actions)
    In production: Syncs with Cloud Storage bucket
    """

    def __init__(
        self,
        bucket_name: str = "deep-alpha-copilot-data",
        project_id: Optional[str] = None,
        local_data_dir: Optional[Path] = None
    ):
        """
        Initialize storage manager.

        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID
            local_data_dir: Local data directory (auto-detected if None)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.is_production = IS_PRODUCTION
        self.local_data_dir = local_data_dir or self._get_data_dir()

        if self.is_production and STORAGE_AVAILABLE:
            try:
                self.client = storage.Client(project=self.project_id)
                self.bucket = self._get_or_create_bucket()
                logger.info(f"✅ Cloud Storage initialized: {self.bucket_name}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Cloud Storage: {e}")
                self.bucket = None
        else:
            self.client = None
            self.bucket = None
            if self.is_production:
                logger.warning("⚠️ Running in production but Cloud Storage not available")
            else:
                logger.info("ℹ️ Cloud Storage disabled (local development mode)")

    def _get_data_dir(self) -> Path:
        """Get appropriate data directory for environment."""
        if self.is_production:
            return Path("/tmp/data")
        else:
            # Local development
            return Path(__file__).parent / "data"

    def _get_or_create_bucket(self):
        """Get existing bucket or create new one."""
        try:
            bucket = self.client.get_bucket(self.bucket_name)
            logger.info(f"✅ Using existing bucket: {self.bucket_name}")
            return bucket
        except Exception as e:
            logger.info(f"Bucket {self.bucket_name} not found, creating...")
            try:
                bucket = self.client.create_bucket(
                    self.bucket_name,
                    location="us-central1"
                )
                logger.info(f"✅ Created new bucket: {self.bucket_name}")
                return bucket
            except Exception as create_error:
                logger.error(f"❌ Failed to create bucket: {create_error}")
                raise

    def download_all_data(self) -> int:
        """
        Download all data from Cloud Storage to local cache.

        Returns:
            Number of files downloaded
        """
        if not self.is_production:
            logger.info("⏭️  Skipping download (local mode - using ./data/)")
            return 0

        if not self.bucket:
            logger.warning("⚠️ Cloud Storage not available, skipping download")
            return 0

        logger.info(f"📥 Downloading data from gs://{self.bucket_name}/data/ to {self.local_data_dir}")
        self.local_data_dir.mkdir(parents=True, exist_ok=True)

        count = 0
        try:
            blobs = self.bucket.list_blobs(prefix="data/")
            for blob in blobs:
                # Skip directory markers
                if blob.name.endswith('/'):
                    continue

                # Calculate local path
                relative_path = blob.name.replace("data/", "")
                local_path = self.local_data_dir / relative_path

                # Create parent directories
                local_path.parent.mkdir(parents=True, exist_ok=True)

                # Download file
                blob.download_to_filename(str(local_path))
                count += 1

                if count % 10 == 0:
                    logger.info(f"   Downloaded {count} files...")

            logger.info(f"✅ Downloaded {count} files from Cloud Storage")
            return count

        except Exception as e:
            logger.error(f"❌ Error downloading data: {e}")
            return count

    def download_file(self, cloud_path: str, local_path: Optional[Path] = None) -> bool:
        """
        Download a single file from Cloud Storage.

        Args:
            cloud_path: Path in bucket (e.g., "data/structured/financials/NVDA.json")
            local_path: Local destination (auto-calculated if None)

        Returns:
            True if successful
        """
        if not self.is_production:
            logger.debug(f"⏭️  Skipping download (local mode): {cloud_path}")
            return False

        if not self.bucket:
            logger.warning("⚠️ Cloud Storage not available")
            return False

        try:
            if local_path is None:
                relative_path = cloud_path.replace("data/", "")
                local_path = self.local_data_dir / relative_path

            local_path.parent.mkdir(parents=True, exist_ok=True)

            blob = self.bucket.blob(cloud_path)
            blob.download_to_filename(str(local_path))
            logger.info(f"✅ Downloaded {cloud_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error downloading {cloud_path}: {e}")
            return False

    def upload_file(self, local_file_path: Path, cloud_path: Optional[str] = None) -> bool:
        """
        Upload a single file to Cloud Storage.

        Args:
            local_file_path: Local file to upload
            cloud_path: Destination in bucket (auto-calculated if None)

        Returns:
            True if successful
        """
        if not self.is_production:
            logger.debug(f"⏭️  Skipping upload (local mode): {local_file_path.name}")
            return False

        if not self.bucket:
            logger.warning("⚠️ Cloud Storage not available")
            return False

        if not local_file_path.exists():
            logger.error(f"❌ File not found: {local_file_path}")
            return False

        try:
            if cloud_path is None:
                # Auto-generate cloud path from local path
                try:
                    relative_path = local_file_path.relative_to(self.local_data_dir)
                    cloud_path = f"data/{relative_path}"
                except ValueError:
                    # If file is not under local_data_dir, use just the name
                    cloud_path = f"data/{local_file_path.name}"

            blob = self.bucket.blob(cloud_path)
            blob.upload_from_filename(str(local_file_path))
            logger.info(f"✅ Uploaded {local_file_path.name} to gs://{self.bucket_name}/{cloud_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Error uploading {local_file_path}: {e}")
            return False

    def upload_data_folder(self) -> int:
        """
        Upload entire data/ folder to Cloud Storage.

        Returns:
            Number of files uploaded
        """
        if not self.is_production:
            logger.info("⏭️  Skipping upload (local mode)")
            return 0

        if not self.bucket:
            logger.warning("⚠️ Cloud Storage not available")
            return 0

        if not self.local_data_dir.exists():
            logger.warning(f"⚠️ Data directory not found: {self.local_data_dir}")
            return 0

        logger.info(f"📤 Uploading data from {self.local_data_dir} to gs://{self.bucket_name}/data/")

        count = 0
        try:
            for local_file in self.local_data_dir.rglob("*"):
                if local_file.is_file():
                    if self.upload_file(local_file):
                        count += 1

                    if count % 10 == 0:
                        logger.info(f"   Uploaded {count} files...")

            logger.info(f"✅ Uploaded {count} files to Cloud Storage")
            return count

        except Exception as e:
            logger.error(f"❌ Error uploading data folder: {e}")
            return count

    def sync_from_cloud(self) -> int:
        """
        Sync data from Cloud Storage (download only new/updated files).

        Returns:
            Number of files downloaded
        """
        # For simplicity, just download all for now
        # Could be optimized to check timestamps/etags
        return self.download_all_data()

    def sync_to_cloud(self) -> int:
        """
        Sync data to Cloud Storage (upload only new/updated files).

        Returns:
            Number of files uploaded
        """
        # For simplicity, just upload all for now
        # Could be optimized to check timestamps
        return self.upload_data_folder()


# Global instance (initialized lazily)
_storage_manager = None


def get_storage_manager() -> DataStorageManager:
    """Get global storage manager instance."""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = DataStorageManager()
    return _storage_manager
