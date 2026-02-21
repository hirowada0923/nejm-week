import os
import logging
import datetime
from dotenv import load_dotenv
from src.modules.fetcher import NEJMFetcher
from src.modules.generator import ScriptGenerator
from src.modules.tts_engine import TTSEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    # Configuration
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    pubmed_email = os.getenv("PUBMED_EMAIL")
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    if not gemini_api_key or not pubmed_email:
        logger.error("GEMINI_API_KEY or PUBMED_EMAIL not found in environment or .env file.")
        return

    # Step 1: Fetch Papers
    logger.info("--- Step 1: Fetching Papers ---")
    fetcher = NEJMFetcher(email=pubmed_email)
    # Return signature is now (data, ids)
    papers_data, processed_ids = fetcher.fetch_papers(max_results=3) 
    
    if not processed_ids:
        logger.info("No new articles to process.")
        return

    if not papers_data:
        logger.info("Non-original articles found. Marking as seen.")
        fetcher.mark_as_processed(processed_ids)
        return

    # Step 2: Generate Content (Script + Report)
    logger.info("--- Step 2: Generating Content (Script + Report) ---")
    generator = ScriptGenerator(api_key=gemini_api_key, model_name="gemini-3-flash-preview")
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
    tts = TTSEngine(api_key=gemini_api_key, model_name="gemini-2.5-flash-preview-tts")
    audio_path = os.path.join(output_dir, f"podcast_audio_{today_str}.wav")
    
    if tts.generate_audio(script, audio_path):
        logger.info("Pipeline completed successfully (Local Test).")
        
        # In local version, we mark as processed after TTS success 
        # (since we don't have Drive/Email steps here)
        fetcher.mark_as_processed(processed_ids)
        
        # Cleanup (Optional: uncomment if you want to delete local files after local test)
        # logger.info("Cleaning up local temporary files...")
        # for f in [script_path, report_path, audio_path, os.path.join(output_dir, "pubmed_data.txt")]:
        #     if os.path.exists(f): os.remove(f)
    else:
        logger.error("Pipeline failed at TTS generation.")

if __name__ == "__main__":
    main()
