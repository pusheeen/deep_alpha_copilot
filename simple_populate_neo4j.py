#!/usr/bin/env python3
"""
Simple Neo4j population script that avoids NumPy/pandas issues
"""
import json
import os
import csv
from pathlib import Path

def load_data_to_neo4j():
    """Load basic data into Neo4j without pandas dependency"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("neo4j driver not available due to NumPy compatibility issues")
        return

    # Connect to Neo4j
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))

    def create_company_nodes(tx):
        """Create company nodes"""
        # Create NVDA company node
        tx.run("""
            MERGE (c:Company {ticker: 'NVDA'})
            SET c.name = 'NVIDIA CORP',
                c.sector = 'Technology',
                c.industry = 'Semiconductors'
        """)
        print("Created NVDA company node")

    def create_filing_nodes(tx):
        """Create filing nodes for NVDA 10-K files"""
        filing_years = [2021, 2022, 2023, 2024, 2025]

        for year in filing_years:
            filing_file = f"data/unstructured/10k/NVDA_10K_{year}.html"
            if os.path.exists(filing_file):
                # Get file size for basic metadata
                file_size = os.path.getsize(filing_file)

                tx.run("""
                    MATCH (c:Company {ticker: 'NVDA'})
                    MERGE (f:Filing {
                        ticker: 'NVDA',
                        form_type: '10-K',
                        filing_year: $year,
                        file_path: $file_path,
                        file_size: $file_size
                    })
                    MERGE (c)-[:FILED]->(f)
                """, year=year, file_path=filing_file, file_size=file_size)

                print(f"Created 10-K filing node for {year}")

    def create_price_data_chunks(tx):
        """Create sample price data chunks"""
        price_file = "data/structured/prices/NVDA_prices.csv"
        if os.path.exists(price_file):
            # Read a few lines of price data
            with open(price_file, 'r') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    if count >= 5:  # Just sample data
                        break

                    tx.run("""
                        MATCH (c:Company {ticker: 'NVDA'})
                        MERGE (p:PriceData {
                            ticker: 'NVDA',
                            date: $date,
                            close: $close,
                            volume: $volume
                        })
                        MERGE (c)-[:HAS_PRICE_DATA]->(p)
                    """,
                    date=row['Date'],
                    close=float(row['Close']),
                    volume=int(float(row['Volume']))
                    )
                    count += 1

                print(f"Created {count} price data nodes")

    def create_reddit_sentiment_nodes(tx):
        """Create Reddit sentiment summary nodes"""
        # Find latest Reddit summary file
        reddit_dir = Path("data/unstructured/reddit")
        summary_files = list(reddit_dir.glob("reddit_summary_*.json"))

        if summary_files:
            latest_summary = max(summary_files, key=lambda x: x.stat().st_mtime)

            with open(latest_summary, 'r') as f:
                reddit_data = json.load(f)

            for ticker, sentiment_data in reddit_data.items():
                tx.run("""
                    MERGE (c:Company {ticker: $ticker})
                    MERGE (s:RedditSentiment {
                        ticker: $ticker,
                        total_posts: $total_posts,
                        bullish_posts: $bullish_posts,
                        bearish_posts: $bearish_posts,
                        neutral_posts: $neutral_posts,
                        subreddits: $subreddits,
                        data_source: 'reddit_api'
                    })
                    MERGE (c)-[:HAS_SENTIMENT]->(s)
                """,
                ticker=ticker,
                total_posts=sentiment_data.get('total_posts', 0),
                bullish_posts=sentiment_data.get('bullish_posts', 0),
                bearish_posts=sentiment_data.get('bearish_posts', 0),
                neutral_posts=sentiment_data.get('neutral_posts', 0),
                subreddits=sentiment_data.get('subreddits', [])
                )

            print(f"Created Reddit sentiment nodes for {len(reddit_data)} tickers")

    try:
        with driver.session() as session:
            print("Populating Neo4j with sample data...")

            # Create company nodes
            session.execute_write(create_company_nodes)

            # Create filing nodes
            session.execute_write(create_filing_nodes)

            # Create sample price data
            session.execute_write(create_price_data_chunks)

            # Create Reddit sentiment data
            session.execute_write(create_reddit_sentiment_nodes)

            print("✅ Neo4j population completed successfully!")

    except Exception as e:
        print(f"❌ Error populating Neo4j: {e}")
    finally:
        driver.close()

def check_neo4j_data():
    """Check what data is now in Neo4j"""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))

        with driver.session() as session:
            # Check total nodes
            result = session.run('MATCH (n) RETURN count(n) as total_nodes')
            total_nodes = result.single()['total_nodes']
            print(f'\n📊 Total nodes: {total_nodes}')

            # Check node types
            result = session.run('MATCH (n) RETURN DISTINCT labels(n) as labels, count(n) as count ORDER BY count DESC')
            print('\n🏷️  Node types:')
            for record in result:
                labels = record['labels']
                count = record['count']
                print(f'   {labels}: {count}')

            # Check relationships
            result = session.run('MATCH ()-[r]->() RETURN count(r) as total_relationships')
            total_rels = result.single()['total_relationships']
            print(f'\n🔗 Total relationships: {total_rels}')

            # Check relationship types
            result = session.run('MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count ORDER BY count DESC')
            print('\n📈 Relationship types:')
            for record in result:
                rel_type = record['rel_type']
                count = record['count']
                print(f'   {rel_type}: {count}')

        driver.close()

    except Exception as e:
        print(f"Error checking Neo4j data: {e}")

if __name__ == "__main__":
    load_data_to_neo4j()
    check_neo4j_data()