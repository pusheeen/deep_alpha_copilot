"""
Email notification utility for BigQuery data pipeline.
Sends daily summary reports about data ingestion.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class EmailNotifier:
    """Send email notifications for pipeline status."""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("EMAIL_SENDER")
        self.sender_password = os.getenv("EMAIL_PASSWORD")  # App-specific password
        self.recipient_email = os.getenv("EMAIL_RECIPIENT", "")

    def send_summary_email(self, summary_stats, errors=None):
        """
        Send a summary email with data ingestion statistics.

        Args:
            summary_stats: Dictionary with upload statistics
            errors: List of errors encountered (optional)
        """
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured in .env file")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"BigQuery Data Pipeline Summary - {datetime.now().strftime('%Y-%m-%d')}"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email

            # Create email body
            html_body = self._generate_html_report(summary_stats, errors)
            text_body = self._generate_text_report(summary_stats, errors)

            # Attach both plain text and HTML versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"✅ Summary email sent to {self.recipient_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _generate_text_report(self, stats, errors):
        """Generate plain text email report."""
        report = []
        report.append("=" * 70)
        report.append("BIGQUERY DATA PIPELINE SUMMARY")
        report.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 70)
        report.append("")

        # Overall status
        status = "✅ SUCCESS" if not errors else "⚠️ COMPLETED WITH ERRORS"
        report.append(f"Status: {status}")
        report.append("")

        # Data uploaded
        report.append("DATA UPLOADED:")
        report.append("-" * 70)

        if stats.get('ceo_profiles'):
            report.append(f"CEO Profiles: {stats['ceo_profiles']['new']} new, {stats['ceo_profiles']['skipped']} skipped")

        if stats.get('quarterly_earnings'):
            report.append(f"Quarterly Earnings: {stats['quarterly_earnings']['new']} new, {stats['quarterly_earnings']['skipped']} skipped")

        if stats.get('financial_statements'):
            report.append(f"Financial Statements: {stats['financial_statements']['new']} new rows")

        if stats.get('stock_prices'):
            report.append(f"Stock Prices: {stats['stock_prices']['new']} new, {stats['stock_prices']['skipped']} skipped")

        if stats.get('sector_metrics'):
            report.append(f"Sector Metrics: {stats['sector_metrics']['new']} records")

        if stats.get('company_metrics'):
            report.append(f"Company Metrics: {stats['company_metrics']['new']} records")

        if stats.get('reddit_posts'):
            report.append(f"Reddit Posts: {stats['reddit_posts']['new']} new")

        if stats.get('x_posts'):
            report.append(f"X/Twitter Posts: {stats['x_posts']['new']} new")

        report.append("")

        # Errors section
        if errors and len(errors) > 0:
            report.append("ERRORS ENCOUNTERED:")
            report.append("-" * 70)
            for error in errors:
                report.append(f"• {error}")
            report.append("")

        # Summary
        report.append("=" * 70)
        report.append(f"Total new records: {self._count_total_new(stats)}")
        project_id = os.getenv("GCP_PROJECT_ID", "unknown-project")
        report.append(f"Project: {project_id}.deep_alpha_copilot")
        report.append("=" * 70)

        return "\n".join(report)

    def _generate_html_report(self, stats, errors):
        """Generate HTML email report."""
        status_color = "#28a745" if not errors else "#ffc107"
        status_text = "✅ SUCCESS" if not errors else "⚠️ COMPLETED WITH ERRORS"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .header {{ background-color: #4285f4; color: white; padding: 20px; border-radius: 8px 8px 0 0; margin: -30px -30px 20px -30px; }}
                .status {{ background-color: {status_color}; color: white; padding: 15px; border-radius: 4px; margin-bottom: 20px; text-align: center; font-size: 18px; font-weight: bold; }}
                .section {{ margin-bottom: 25px; }}
                .section-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; border-bottom: 2px solid #4285f4; padding-bottom: 5px; }}
                .data-table {{ width: 100%; border-collapse: collapse; }}
                .data-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
                .data-table td:first-child {{ font-weight: bold; color: #555; width: 200px; }}
                .data-table td:last-child {{ color: #333; text-align: right; }}
                .error-box {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 10px 0; }}
                .error-item {{ margin: 5px 0; color: #856404; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; color: #999; font-size: 12px; }}
                .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
                .metric-value {{ font-size: 32px; font-weight: bold; color: #4285f4; }}
                .metric-label {{ font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">BigQuery Data Pipeline Summary</h1>
                    <p style="margin: 5px 0 0 0;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>

                <div class="status">{status_text}</div>

                <div class="section">
                    <div class="metric">
                        <div class="metric-value">{self._count_total_new(stats)}</div>
                        <div class="metric-label">Total New Records</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{len(errors) if errors else 0}</div>
                        <div class="metric-label">Errors</div>
                    </div>
                </div>

                <div class="section">
                    <div class="section-title">Data Uploaded</div>
                    <table class="data-table">
        """

        # Add data rows
        if stats.get('ceo_profiles'):
            html += f"""
                        <tr>
                            <td>CEO Profiles</td>
                            <td>{stats['ceo_profiles']['new']} new, {stats['ceo_profiles']['skipped']} skipped</td>
                        </tr>
            """

        if stats.get('quarterly_earnings'):
            html += f"""
                        <tr>
                            <td>Quarterly Earnings</td>
                            <td>{stats['quarterly_earnings']['new']} new, {stats['quarterly_earnings']['skipped']} skipped</td>
                        </tr>
            """

        if stats.get('financial_statements'):
            html += f"""
                        <tr>
                            <td>Financial Statements</td>
                            <td>{stats['financial_statements']['new']} new rows</td>
                        </tr>
            """

        if stats.get('stock_prices'):
            html += f"""
                        <tr>
                            <td>Stock Prices</td>
                            <td>{stats['stock_prices']['new']} new, {stats['stock_prices']['skipped']} skipped</td>
                        </tr>
            """

        if stats.get('sector_metrics'):
            html += f"""
                        <tr>
                            <td>Sector Metrics</td>
                            <td>{stats['sector_metrics']['new']} records</td>
                        </tr>
            """

        if stats.get('company_metrics'):
            html += f"""
                        <tr>
                            <td>Company Metrics</td>
                            <td>{stats['company_metrics']['new']} records</td>
                        </tr>
            """

        if stats.get('reddit_posts'):
            html += f"""
                        <tr>
                            <td>Reddit Posts</td>
                            <td>{stats['reddit_posts']['new']} new</td>
                        </tr>
            """

        if stats.get('x_posts'):
            html += f"""
                        <tr>
                            <td>X/Twitter Posts</td>
                            <td>{stats['x_posts']['new']} new</td>
                        </tr>
            """

        html += """
                    </table>
                </div>
        """

        # Errors section
        if errors and len(errors) > 0:
            html += """
                <div class="section">
                    <div class="section-title">Errors Encountered</div>
                    <div class="error-box">
            """
            for error in errors:
                html += f'<div class="error-item">• {error}</div>'
            html += """
                    </div>
                </div>
            """

        html += f"""
                <div class="footer">
                    <p>BigQuery Project: <strong>{os.getenv('GCP_PROJECT_ID', 'unknown-project')}.deep_alpha_copilot</strong></p>
                    <p>This is an automated report from your deep_alpha_copilot data pipeline.</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _count_total_new(self, stats):
        """Count total new records across all data types."""
        total = 0
        for data_type, counts in stats.items():
            if isinstance(counts, dict) and 'new' in counts:
                total += counts['new']
        return total


if __name__ == "__main__":
    # Test email sending
    notifier = EmailNotifier()

    # Sample stats
    test_stats = {
        'ceo_profiles': {'new': 5, 'skipped': 10},
        'quarterly_earnings': {'new': 20, 'skipped': 32},
        'financial_statements': {'new': 1500},
        'stock_prices': {'new': 1255, 'skipped': 0},
        'sector_metrics': {'new': 1},
        'company_metrics': {'new': 10},
        'reddit_posts': {'new': 5},
        'x_posts': {'new': 100},
    }

    test_errors = [
        "Failed to fetch X posts for TSLA: API rate limit exceeded",
    ]

    notifier.send_summary_email(test_stats, test_errors)
