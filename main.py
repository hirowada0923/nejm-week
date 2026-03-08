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
    report_data = storage.upload_file(report_path, folder_id=folder_id, mime_type="text/markdown")

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
    body = f"""今週の NEJM 循環器領域の論文解説が完成しました。内容は以下のリンクからご確認いただけます。

【今週のニュースレター（レポート）】
{report_url}

【音声解説（Podcast）直リンク】
{audio_url}

日々の診療の合間や通勤時間に、読み物、または音声としてお役立てください。
"""
    if notifier.send_notification(recipient_emails, subject, body):
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
