"""
Cloud Scheduler job definitions for automated data updates.
These jobs can be triggered via HTTP endpoints or Cloud Scheduler.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Data update frequencies (in hours or cron format)
UPDATE_SCHEDULES = {
    "scoring_data": {
        "frequency": "quarterly",  # Every 3 months
        "cron": "0 2 1 */3 *",  # 2am PST on 1st day of quarter (Jan, Apr, Jul, Oct)
        "description": "Financial statements, earnings, prices (quarterly)"
    },
    "sentiment_data": {
        "frequency": "weekly",  # Once per week
        "cron": "0 2 * * 1",  # 2am PST every Monday
        "description": "Reddit and X/Twitter sentiment (weekly)"
    },
    "news_data": {
        "frequency": "daily",  # Daily at 2am PST
        "cron": "0 2 * * *",  # 2am PST every day
        "description": "Latest news (past 72 hours, refreshed daily)"
    },
    "institutional_flow": {
        "frequency": "quarterly",  # Every 3 months
        "cron": "0 2 1 */3 *",  # 2am PST on 1st day of quarter
        "description": "Institutional ownership and flow data (quarterly)"
    },
    "openrouter_data": {
        "frequency": "weekly",  # Once per week
        "cron": "0 2 * * 1",  # 2am PST every Monday
        "description": "OpenRouter model updates (weekly)"
    },
    "momentum_data": {
        "frequency": "daily",  # Daily at 2am PST
        "cron": "0 2 * * *",  # 2am PST every day
        "description": "Price data, technical indicators for momentum strategy (daily)"
    }
}


def get_last_updated_timestamp(data_type: str) -> Optional[datetime]:
    """
    Get the last updated timestamp for a data type.
    Reads from a metadata file in GCS or local storage.
    """
    try:
        from storage_helper import get_storage_manager
        storage_manager = get_storage_manager()
        
        # Try to load from local cache first
        metadata_file = f"data/metadata/{data_type}_last_updated.json"
        local_path = Path(metadata_file)
        
        if local_path.exists():
            with local_path.open("r") as f:
                data = json.load(f)
                return datetime.fromisoformat(data.get("last_updated"))
        
        # Try to download from GCS if in production
        if storage_manager.is_production and storage_manager.bucket:
            try:
                blob = storage_manager.bucket.blob(f"data/metadata/{data_type}_last_updated.json")
                if blob.exists():
                    content = blob.download_as_text()
                    data = json.loads(content)
                    return datetime.fromisoformat(data.get("last_updated"))
            except Exception as e:
                logger.debug(f"Could not load timestamp from GCS: {e}")
        
        return None
    except Exception as e:
        logger.error(f"Error getting last updated timestamp for {data_type}: {e}")
        return None


def update_last_updated_timestamp(data_type: str) -> bool:
    """
    Update the last updated timestamp for a data type.
    Saves to both local storage and GCS.
    """
    try:
        from pathlib import Path
        from storage_helper import get_storage_manager
        
        timestamp = datetime.now(timezone.utc)
        metadata = {
            "data_type": data_type,
            "last_updated": timestamp.isoformat(),
            "description": UPDATE_SCHEDULES.get(data_type, {}).get("description", "")
        }
        
        # Save locally
        metadata_dir = Path("data/metadata")
        metadata_dir.mkdir(parents=True, exist_ok=True)
        local_path = metadata_dir / f"{data_type}_last_updated.json"
        with local_path.open("w") as f:
            json.dump(metadata, f, indent=2)
        
        # Upload to GCS if in production
        storage_manager = get_storage_manager()
        if storage_manager.is_production and storage_manager.bucket:
            try:
                blob = storage_manager.bucket.blob(f"data/metadata/{data_type}_last_updated.json")
                blob.upload_from_string(json.dumps(metadata, indent=2), content_type="application/json")
                logger.info(f"✅ Updated timestamp for {data_type} in GCS")
            except Exception as e:
                logger.warning(f"Could not upload timestamp to GCS: {e}")
        
        return True
    except Exception as e:
        logger.error(f"Error updating timestamp for {data_type}: {e}")
        return False


def create_cloud_scheduler_jobs(project_id: str, region: str = "us-central1"):
    """
    Create Cloud Scheduler jobs for all data update frequencies.
    Returns a list of gcloud commands to run.
    """
    service_url = os.getenv("CLOUD_RUN_SERVICE_URL", "https://deep-alpha-copilot-420930943775.us-central1.run.app")
    
    commands = []
    
    for data_type, schedule in UPDATE_SCHEDULES.items():
        job_name = f"update-{data_type.replace('_', '-')}"
        endpoint = f"{service_url}/api/scheduler/update/{data_type}"
        cron = schedule["cron"]
        description = schedule["description"]
        
        cmd = f"""gcloud scheduler jobs create http {job_name} \\
    --location={region} \\
    --schedule="{cron}" \\
    --uri="{endpoint}" \\
    --http-method=POST \\
    --description="{description}" \\
    --time-zone="America/Los_Angeles" \\
    --attempt-deadline=3600s"""
        
        commands.append({
            "job_name": job_name,
            "command": cmd,
            "schedule": cron,
            "description": description
        })
    
    return commands

