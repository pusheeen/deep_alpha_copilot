# Email Notification Setup Guide

Your BigQuery data pipeline now sends daily summary emails to `yinglu1985.shanghai@gmail.com` after each run.

## Prerequisites

You need a Gmail account that will send the emails. This can be any Gmail account you control.

## Setup Steps

### 1. Enable 2-Factor Authentication on Gmail

1. Go to https://myaccount.google.com/security
2. Under "Signing in to Google", enable "2-Step Verification"
3. Follow the prompts to set it up

### 2. Create an App Password

1. Go to https://myaccount.google.com/apppasswords
2. If you don't see this option, make sure 2-Step Verification is enabled first
3. In the "Select app" dropdown, choose "Mail"
4. In the "Select device" dropdown, choose "Other (Custom name)"
5. Enter a name like "BigQuery Pipeline" or "deep_alpha_copilot"
6. Click "Generate"
7. Google will show you a 16-character password (like "xxxx xxxx xxxx xxxx")
8. Copy this password (remove the spaces)

### 3. Update Your .env File

Edit `/Users/luying/Documents/deep_alpha_copilot/.env` and add:

```bash
# Email Notification Settings
EMAIL_SENDER=your-gmail-address@gmail.com  # The Gmail account sending emails
EMAIL_PASSWORD=xxxxxxxxxxxxxxxx  # The 16-character app password (no spaces)
EMAIL_RECIPIENT=yinglu1985.shanghai@gmail.com
```

**Example:**
```bash
EMAIL_SENDER=yinglu08fall@gmail.com
EMAIL_PASSWORD=abcdabcdabcdabcd
EMAIL_RECIPIENT=yinglu1985.shanghai@gmail.com
```

## Test the Email Notification

Run the test script to verify email sending works:

```bash
cd /Users/luying/Documents/deep_alpha_copilot
python3 email_notifier.py
```

You should receive a test email at `yinglu1985.shanghai@gmail.com` with sample statistics.

## What the Email Contains

Each daily email includes:

📊 **Summary Statistics:**
- Status (Success or Errors)
- Total new records uploaded
- Number of errors

📈 **Data Uploaded:**
- CEO Profiles: X new, Y skipped
- Quarterly Earnings: X new, Y skipped
- Financial Statements: X new rows
- Stock Prices: X new, Y skipped
- Sector Metrics: X records
- Company Metrics: X records
- Reddit Posts: X new
- X/Twitter Posts: X new

⚠️ **Errors (if any):**
- List of all errors encountered

The email is sent in both plain text and HTML formats, so it looks good in any email client.

## Running the Pipeline

### Manual Run
```bash
cd /Users/luying/Documents/deep_alpha_copilot
python3 fetch_and_upload.py
```

After completion, you'll receive an email summary.

### Automated Daily Run (Cron)

To run automatically every day at 6 AM:

1. Open crontab:
```bash
crontab -e
```

2. Add this line:
```
0 6 * * * cd /Users/luying/Documents/deep_alpha_copilot && /usr/local/bin/python3 fetch_and_upload.py >> /Users/luying/Documents/deep_alpha_copilot/cron.log 2>&1
```

3. Save and exit

This will:
- Run daily at 6:00 AM
- Fetch latest data
- Upload to BigQuery
- Send you an email summary
- Log output to `cron.log`

## Troubleshooting

### "Email credentials not configured"
- Make sure you've added `EMAIL_SENDER` and `EMAIL_PASSWORD` to `.env`
- The .env file must be in the same directory as the scripts

### "Authentication failed"
- Double-check the app password (no spaces)
- Make sure you're using an **App Password**, not your regular Gmail password
- Verify 2-Step Verification is enabled on the Gmail account

### "No email received"
- Check your spam folder
- Verify `EMAIL_RECIPIENT` is correct in `.env`
- Run the test script: `python3 email_notifier.py`
- Check for errors in the console output

### "SMTPAuthenticationError"
- Your App Password might be incorrect
- Generate a new App Password and update `.env`
- Make sure you're using the Gmail account that created the App Password

## Security Notes

- **Never commit your `.env` file to git** (it's already in `.gitignore`)
- The App Password only works for this specific app
- You can revoke the App Password anytime at https://myaccount.google.com/apppasswords
- Regular Gmail password changes don't affect App Passwords

## Customizing the Email

To customize the email content, edit `/Users/luying/Documents/deep_alpha_copilot/email_notifier.py`:

- `_generate_html_report()` - HTML email format
- `_generate_text_report()` - Plain text email format

## Questions?

If you have issues, check:
1. `.env` file has all three email variables set
2. App Password is correct (16 characters, no spaces)
3. Gmail account has 2-Step Verification enabled
4. Test script works: `python3 email_notifier.py`
