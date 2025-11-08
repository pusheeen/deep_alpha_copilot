#!/usr/bin/env python3
"""Quick script to verify and find correct YouTube channel IDs"""

import os
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

youtube_api_key = os.getenv('YOUTUBE_API_KEY')
youtube = build('youtube', 'v3', developerKey=youtube_api_key)

companies = [
    ('NVDA', 'NVIDIA'),
    ('AMD', 'AMD'),
    ('TSM', 'TSMC'),
    ('ORCL', 'Oracle'),
    ('AVGO', 'Broadcom'),
]

print("Searching for official YouTube channels:\n")

for ticker, company_name in companies:
    print(f"\n{ticker} - {company_name}:")
    print("-" * 60)

    # Search for channel
    search_response = youtube.search().list(
        q=f"{company_name} official",
        type='channel',
        part='id,snippet',
        maxResults=3
    ).execute()

    if search_response.get('items'):
        for i, item in enumerate(search_response['items'], 1):
            channel_id = item['id']['channelId']
            channel_title = item['snippet']['title']
            channel_desc = item['snippet'].get('description', 'N/A')[:100]

            print(f"{i}. {channel_title}")
            print(f"   ID: {channel_id}")
            print(f"   Description: {channel_desc}...")

            # Get channel details to check video count
            channel_details = youtube.channels().list(
                id=channel_id,
                part='statistics,contentDetails'
            ).execute()

            if channel_details.get('items'):
                stats = channel_details['items'][0].get('statistics', {})
                video_count = stats.get('videoCount', 'N/A')
                subscriber_count = stats.get('subscriberCount', 'N/A')
                print(f"   Videos: {video_count}, Subscribers: {subscriber_count}")
    else:
        print("   No channels found")

print("\n" + "="*60)
