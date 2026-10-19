import os
import logging
from dotenv import load_dotenv
from src.modules.fetcher import NEJMFetcher
from src.modules.generator import ScriptGenerator
from src.modules.tts_engine import TTSEngine
from src.modules.storage import GoogleDriveStorage
from src.modules.notifier import GmailNotifier

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    # Configuration from Environment Variables
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    pubmed_email = os.getenv("PUBMED_EMAIL")
    g_client_id = os.getenv("G_CLIENT_ID")
    g_client_secret = os.getenv("G_CLIENT_SECRET")
    g_refresh_token = os.getenv("G_REFRESH_TOKEN")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID") # Optional
    gmail_sender = os.getenv("GMAIL_SENDER_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient_emails = os.getenv("NOTIFICATION_RECIPIENT_EMAIL")

    if not all([gemini_api_key, pubmed_email, g_client_id, g_client_secret, g_refresh_token, gmail_sender, gmail_password, recipient_emails]):
        missing = [k for k, v in {
            "GEMINI_API_KEY": gemini_api_key,
            "PUBMED_EMAIL": pubmed_email,
            "G_CLIENT_ID": g_client_id,
            "G_CLIENT_SECRET": g_client_secret,
            "G_REFRESH_TOKEN": g_refresh_token,
            "GMAIL_SENDER_ADDRESS": gmail_sender,
            "GMAIL_APP_PASSWORD": gmail_password,
            "NOTIFICATION_RECIPIENT_EMAIL": recipient_emails
        }.items() if not v]
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return

    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    import datetime
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    # Step 1: Fetch Papers
    logger.info("--- Step 1: Fetching Papers ---")
    fetcher = NEJMFetcher(email=pubmed_email)
    papers_data, processed_ids = fetcher.fetch_papers(max_results=5)
    
    if not processed_ids:
        logger.info("No new articles to process.")
        return

    if not papers_data:
        # This could happen if articles were found but they weren't "Original Articles"
        # In this case, we can still mark them as processed to avoid re-checking.
        logger.info("Non-original articles found. Marking as seen.")
        fetcher.mark_as_processed(processed_ids)
        return

    # Step 2: Generate Content (Script + Report)
    logger.info("--- Step 2: Generating Content (Script + Report) ---")
    generator = ScriptGenerator(api_key=gemini_api_key)
    content = generator.generate_content(papers_data)
    
    if not content or "script" not in content or "report" not in content:
        logger.error("Failed to generate complete content.")
        return
    
    script = str(content["script"])
    report = str(content["report"])
    
    script_path = os.path.join(output_dir, f"podcast_script_{today_str}.txt")
    with open(script_path, "w") as f:
        f.write(script)
        
    report_path = os.path.join(output_dir, f"nejm_report_{today_str}.md")
    with open(report_path, "w") as f:
        f.write(report)
    
    logger.info(f"Script and Report saved to {output_dir}")

    # Step 3: Generate Audio (TTS)
    logger.info("--- Step 3: Generating Audio (TTS) ---")
    tts = TTSEngine(api_key=gemini_api_key)
    audio_path = os.path.join(output_dir, f"podcast_audio_{today_str}.wav")
    if not tts.generate_audio(script, audio_path):
        logger.error("Failed to generate audio.")
        return

    # Step 4: Storage (Google Drive)
    logger.info("--- Step 4: Uploading to Google Drive ---")
    storage = GoogleDriveStorage(g_client_id, g_client_secret, g_refresh_token)
    audio_data = storage.upload_file(audio_path, folder_id=folder_id, mime_type="audio/wav")
    # Convert markdown to Google Docs on Drive so it renders perfectly on iOS/mobile
    report_data = storage.upload_file(report_path, folder_id=folder_id, mime_type="text/markdown", convert_to_docs=True)

    if not audio_data or not report_data:
        logger.error("Failed to upload files to Google Drive.")
        return
    
    # previewLink is better for mobile browsers to play directly
    audio_url = audio_data.get("previewLink")
    report_url = report_data.get("webViewLink")

    # Step 5: Notification (Gmail)
    logger.info("--- Step 5: Sending Notification ---")
    notifier = GmailNotifier(gmail_sender, gmail_password)
    subject = "今週の NEJM 循環器論文 Podcast & レポートが完成しました"
    
    # Plain text fallback
    body = f"""今週の NEJM 循環器領域の論文解説が完成しました。内容は以下のリンクまたは本メール本文からご確認いただけます。

【今週のニュースレター（Googleドキュメント）】
{report_url}

【音声解説（Podcast）直リンク】
{audio_url}

--------------------------------------------------
{report}
--------------------------------------------------

日々の診療の合間や通勤時間に、読み物、または音声としてお役立てください。
"""

    # HTML body with mobile-friendly typography and embedded report
    import markdown
    html_report_content = markdown.markdown(report, extensions=['extra'])
    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.6;
    color: #24292e;
    max-width: 680px;
    margin: 0 auto;
    padding: 16px;
    background-color: #ffffff;
  }}
  .action-box {{
    background-color: #f6f8fa;
    border: 1px solid #e1e4e8;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 24px;
  }}
  .button {{
    display: inline-block;
    padding: 10px 18px;
    margin: 6px 8px 6px 0;
    background-color: #0366d6;
    color: #ffffff !important;
    text-decoration: none;
    border-radius: 6px;
    font-weight: bold;
    font-size: 14px;
  }}
  .button-secondary {{
    background-color: #2ea44f;
  }}
  h1 {{
    font-size: 20px;
    border-bottom: 2px solid #eaecef;
    padding-bottom: 8px;
    margin-top: 24px;
    color: #1a1a1a;
  }}
  h2 {{
    font-size: 18px;
    border-bottom: 1px solid #eaecef;
    padding-bottom: 6px;
    margin-top: 20px;
    color: #2c3e50;
  }}
  h3 {{
    font-size: 16px;
    margin-top: 18px;
    color: #1b6acb;
  }}
  h4 {{
    font-size: 14px;
    margin-top: 12px;
    margin-bottom: 4px;
    color: #444;
  }}
  ul, ol {{
    padding-left: 20px;
  }}
  li {{
    margin-bottom: 4px;
  }}
  a {{
    color: #0366d6;
    text-decoration: underline;
  }}
  hr {{
    border: 0;
    height: 1px;
    background: #e1e4e8;
    margin: 24px 0;
  }}
  .footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #eee;
    font-size: 12px;
    color: #6a737d;
  }}
</style>
</head>
<body>
  <div class="action-box">
    <p style="margin: 0 0 12px 0; font-size: 15px; font-weight: bold;">今週の NEJM 循環器論文解説が完成しました。</p>
    <div>
      <a href="{audio_url}" class="button">🎧 音声解説（Podcast）を聴く</a>
      <a href="{report_url}" class="button button-secondary">📄 Google Docsで開く</a>
    </div>
  </div>

  <div class="report-content">
    {html_report_content}
  </div>

  <div class="footer">
    <p>日々の診療の合間や通勤時間に、読み物、または音声としてお役立てください。</p>
  </div>
</body>
</html>"""

    if notifier.send_notification(recipient_emails, subject, body, html_body=html_body):
        logger.info("All steps completed successfully. Committing processed IDs.")
        fetcher.mark_as_processed(processed_ids)
        
        # Cleanup local files
        logger.info("Cleaning up local temporary files...")
        temp_files = [script_path, report_path, audio_path, os.path.join(output_dir, "pubmed_data.txt")]
        for f_path in temp_files:
            try:
                if os.path.exists(f_path):
                    os.remove(f_path)
                    logger.debug(f"Deleted: {f_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {f_path}: {e}")
    else:
        logger.error("Failed to send notification. Articles will not be marked as processed.")

if __name__ == "__main__":
    main()
