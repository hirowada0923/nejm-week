import os
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import email.utils
import logging
import re
from Bio import Entrez
from tavily import TavilyClient

class NEJMFetcher:
    RSS_URL = "https://onesearch-rss.nejm.org/api/specialty/rss?context=nejm&specialty=cardiology"

    def __init__(self, email):
        Entrez.email = email
        self.logger = logging.getLogger(__name__)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        if self.tavily_api_key:
            self.tavily = TavilyClient(api_key=self.tavily_api_key)
        else:
            self.logger.warning("TAVILY_API_KEY not found in environment.")
            self.tavily = None

    def get_date_range(self):
        """
        Calculate date range: Last Thursday to this Wednesday.
        """
        today = datetime.date.today()
        # weekday(): Monday=0, ..., Wednesday=2, Thursday=3, ..., Sunday=6
        # Find this Wednesday (most recent Wednesday <= today)
        days_since_wednesday = (today.weekday() - 2) % 7
        this_wednesday = today - datetime.timedelta(days=days_since_wednesday)
        last_thursday = this_wednesday - datetime.timedelta(days=6)
        
        return last_thursday, this_wednesday

    def parse_rss_date(self, date_str):
        if not date_str:
            return None
        try:
            return email.utils.parsedate_to_datetime(date_str)
        except Exception:
            pass
        try:
            dt = datetime.datetime.strptime(date_str.split('T')[0], "%Y-%m-%d")
            return dt.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass
        return None

    def fetch_abstract_via_pubmed(self, url):
        """
        Fetch the abstract from PubMed using the DOI extracted from the URL.
        """
        try:
            doi_match = re.search(r'10\.1056/[A-Za-z0-9.]+', url)
            if not doi_match:
                return None
            
            doi = doi_match.group(0)
            self.logger.info(f"Fetching abstract from PubMed for DOI: {doi}")
            
            search_handle = Entrez.esearch(db="pubmed", term=f"{doi}[doi]")
            search_results = Entrez.read(search_handle)
            search_handle.close()
            
            id_list = search_results.get("IdList")
            if not id_list:
                return None
            
            pmid = id_list[0]
            fetch_handle = Entrez.efetch(db="pubmed", id=pmid, rettype="medline", retmode="text")
            medline_data = fetch_handle.read()
            fetch_handle.close()
            
            # Extract Abstract (AB field) and clean it up
            ab_match = re.search(r'^AB\s*-\s*(.*?)(?=\n[A-Z]{2,}\s*-|\n\n|\Z)', medline_data, re.MULTILINE | re.DOTALL)
            if ab_match:
                abstract_text = ab_match.group(1)
                abstract_text = re.sub(r'\n\s+', ' ', abstract_text).strip()
                return abstract_text
            return None
        except Exception as e:
            self.logger.error(f"Error fetching abstract from PubMed: {e}")
            return None

    def search_tavily_for_context(self, title, doi):
        """
        Fetch rich context and abstract info via Tavily.
        """
        if not self.tavily:
            return None
        
        try:
            self.logger.info(f"Searching Tavily for: {title} ({doi})")
            query = f'"{title}" {doi} clinical significance and abstract dosage methodology'
            search_result = self.tavily.search(
                query=query,
                search_depth="advanced",
                include_answer=True,
                max_results=5
            )
            
            context_text = "\n".join([r['content'] for r in search_result['results']])
            tavily_answer = search_result.get('answer', '')
            
            return {
                "answer": tavily_answer,
                "context": context_text
            }
        except Exception as e:
            self.logger.error(f"Error searching Tavily: {e}")
            return None

    def _get_processed_ids(self, output_dir):
        """Load processed article DOIs from a file."""
        file_path = os.path.join(output_dir, "processed_articles.txt")
        if not os.path.exists(file_path):
            return set()
        with open(file_path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())

    def _save_processed_id(self, output_dir, article_id):
        """Append a processed article DOI to the file if not already present."""
        file_path = os.path.join(output_dir, "processed_articles.txt")
        os.makedirs(output_dir, exist_ok=True)
        
        existing_ids = self._get_processed_ids(output_dir)
        if article_id in existing_ids:
            return

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{article_id}\n")

    def mark_as_processed(self, ids, output_dir="outputs"):
        """Public method to commit multiple article IDs as processed."""
        if not ids:
            return
        self.logger.info(f"Marking {len(ids)} articles as processed.")
        for doi in ids:
            self._save_processed_id(output_dir, doi)

    def fetch_papers_via_rss(self, days=30, output_dir="outputs"):
        """
        Fetch papers from NEJM RSS and get abstracts via PubMed for Original Articles.
        Returns a tuple of (papers_text, newly_processed_ids).
        Does NOT mark them as processed in the persistent storage yet.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now - datetime.timedelta(days=days)
        
        self.logger.info(f"Checking RSS for unprocessed papers (looking back {days} days)")
        
        processed_ids = self._get_processed_ids(output_dir)
        
        try:
            req = urllib.request.Request(self.RSS_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                rss_data = response.read()
            
            root = ET.fromstring(rss_data)
            items = root.findall(".//item")
            
            valid_papers = []
            newly_processed_ids = []
            
            for item in items:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                
                # Extract DOI as unique ID
                doi_match = re.search(r'10\.1056/[A-Za-z0-9.]+', link)
                if not doi_match:
                    continue
                doi = doi_match.group(0)

                # Skip if already processed
                if doi in processed_ids or doi in newly_processed_ids:
                    continue

                # Get date
                pub_date_tag = item.find("pubDate")
                dc_date_tag = item.find("{http://purl.org/dc/elements/1.1/}date")
                date_str = pub_date_tag.text if pub_date_tag is not None else (dc_date_tag.text if dc_date_tag is not None else None)
                
                pub_date = self.parse_rss_date(date_str)
                
                # Check date (secondary safety filter)
                if pub_date and pub_date >= start_dt:
                    # Check if Original Article
                    if "NEJMoa" in link:
                        self.logger.info(f"Found new Original Article: {title}")
                        
                        # Primary: PubMed (for facts)
                        abstract = self.fetch_abstract_via_pubmed(link)
                        
                        # Enrichment: Tavily (for context & missing abstracts)
                        tavily_data = self.search_tavily_for_context(title, doi)
                        
                        if abstract or (tavily_data and tavily_data['answer']):
                            # Combine data into a structured format for generator
                            # We keep pseudo-MEDLINE-ish tags but add context fields
                            paper_record = f"TI  - {title}\nAB  - {abstract if abstract else ''}\nDOI - {doi}\nLINK - {link}\nDP  - {pub_date.strftime('%Y %b %d')}"
                            if tavily_data:
                                paper_record += f"\nTAV_ANS - {tavily_data['answer']}\nTAV_CTX - {tavily_data['context']}"
                            
                            valid_papers.append(paper_record)
                            newly_processed_ids.append(doi)
                        else:
                            self.logger.warning(f"No source (PubMed/Tavily) found for: {title}. Skipping for retry.")
                    else:
                        # For non-original articles, we still want to mark them as "seen" 
                        # so they don't reappear in future runs.
                        newly_processed_ids.append(doi)
            
            if not valid_papers and not newly_processed_ids:
                self.logger.info("No new articles found.")
                return None, []

            papers_text = "\n\n".join(valid_papers) if valid_papers else None
            
            if papers_text and output_dir:
                os.makedirs(output_dir, exist_ok=True)
                save_path = os.path.join(output_dir, "pubmed_data.txt")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(papers_text)
                self.logger.info(f"Fetched RSS/Tavily/PubMed data saved to {save_path}")

            return papers_text, newly_processed_ids

        except Exception as e:
            self.logger.error(f"Error in RSS fetcher: {e}")
            return None, []

    def fetch_papers(self, max_results=5, output_dir="outputs"):
        """
        Standard entry point. Now uses RSS as the primary method with persistence.
        Returns (papers_text, newly_processed_ids).
        """
        return self.fetch_papers_via_rss(output_dir=output_dir)
