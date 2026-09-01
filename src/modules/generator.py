import os
import logging
import json
import re
from typing import Optional, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# --- Data Models ---

class PaperInfo(BaseModel):
    title: str
    doi: str
    published_date: str = Field(description="論文の発行日（DPフィールド等の値）")
    abstract_core: str = Field(description="投与量やP値を含む核心的な抄録内容")
    methodology: str    = Field(description="サンプルサイズ、期間、投与スケジュール等")
    conclusion: str     = Field(description="主要アウトカムの具体的な数値結果")
    original_abstract: Optional[str] = Field(description="MEDLINEフォーマットのABフィールドの内容（背景、方法、結果、結論の構成維持のため）")

class SupplementaryContext(BaseModel):
    clinical_significance: str = Field(description="歴史的背景、他の試験との比較、臨床的意義")
    patient_stories: Optional[str] = Field(description="ニュース等で見つかった患者視点や社会的な影響")
    expert_comments: Optional[str] = Field(description="編集後記やニュースセクション、SNS等での専門家の見解")

class ArticleData(BaseModel):
    paper_info: PaperInfo
    supplementary_context: SupplementaryContext
    source_url: str

class ScriptGenerator:
    def __init__(self, api_key, model_name=None):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.logger = logging.getLogger(__name__)

    def _extract_rich_data(self, paper_record: str) -> Optional[ArticleData]:
        """
        Uses Gemini to parse the pseudo-MEDLINE + Tavily record into structured Pydantic.
        """
        prompt = f"""
あなたは医学専門のシニアエディターです。以下の情報を元に、論文の「厳密な事実（Fact）」と「臨床的背景（Context）」を「完全なJSON形式」で抽出してください。

【入力情報】
{paper_record}

【指示】
以下の階層構造を持つJSONオブジェクトのみを出力してください。rootに直接文字列を置かないでください。

1. paper_info (Object): 
   - title (String): 論文タイトル
   - doi (String): DOI番号
   - published_date (String): DPフィールド等にある発行日（例: 2026 Mar 05）
   - abstract_core (String): 投与量やP値を含む核心的な抄録内容
   - methodology (String): サンプルサイズ、期間、投与スケジュール、対象患者等の詳細
   - conclusion (String): 主要アウトカムの具体的な数値結果
   - original_abstract (String): ABフィールド（抄録）の全文
2. supplementary_context (Object): 
   - clinical_significance (String): 歴史的背景、他の試験との比較、臨床的意義
   - patient_stories (String): ニュース等で見つかった患者視点や社会的な影響
   - expert_comments (String): 専門家の見解やSNS等での議論

【制約】
- **JSONのキー名はすべて小文字で上記を厳守してください。**
- **paper_info と supplementary_context は必ず「オブジェクト（辞書）」にしてください。**
- 医学的事実として、ABフィールド（PubMed抄録）にある数値を最優先してください。
- [自分の名前]などのプレースホルダーは一切含めないでください。
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            raw_text = response.text.strip()
            
            # Robust JSON extraction
            try:
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}')
                if start_index != -1 and end_index != -1:
                    json_text = raw_text[start_index:end_index + 1]
                    data_dict = json.loads(json_text)
                else:
                    data_dict = json.loads(raw_text)
            except json.JSONDecodeError:
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    data_dict = json.loads(match.group(0))
                else:
                    raise

            # Find the source URL from the record
            source_url = ""
            url_match = re.search(r'LINK - (https?://[^\n]+)', paper_record)
            if url_match:
                source_url = url_match.group(1).strip()
            
            data_dict["source_url"] = source_url
            return ArticleData(**data_dict)
        except Exception as e:
            self.logger.error(f"Error extracting rich data: {e}")
            self.logger.debug(f"Raw text that failed in extraction: {raw_text if 'raw_text' in locals() else 'N/A'}")
            return None

    def generate_content(self, papers_text):
        """
        Main entry point to generate Japanese script and report.
        """
        # Use the robust separator introduced in fetcher.py
        separator = "---END_OF_PAPER---"
        raw_records = [r.strip() for r in papers_text.split(separator) if r.strip()]
        
        self.logger.info(f"Splitting content into {len(raw_records)} records using {separator}")
        
        processed_articles = []
        for i, record in enumerate(raw_records):
            # Basic validation: must contain a title field
            if "TI  - " not in record:
                self.logger.warning(f"Record {i+1} seems malformed (no title tag). Skipping.")
                continue
                
            self.logger.info(f"Structured extraction for record {i+1}/{len(raw_records)}...")
            article_data = self._extract_rich_data(record)
            if article_data:
                processed_articles.append(article_data)
        
        if not processed_articles:
            self.logger.warning("No articles successfully structured.")
            return None

        paper_count = len(processed_articles)
        
        # Build articles context for the final generation
        articles_context = ""
        for i, art in enumerate(processed_articles):
            is_nejm = "nejm.org" in art.source_url or art.paper_info.doi.startswith("10.1056/")
            label = "(NEJM論文)" if is_nejm else "(その他の論文)"
            
            articles_context += f"""
【論文 {i+1}】
タイトル: {art.paper_info.title} {label}
DOI: {art.paper_info.doi}
発行日: {art.paper_info.published_date}
URL: {art.source_url}

[事実 (Facts)]
- 結論: {art.paper_info.conclusion}
- 背景/方法: {art.paper_info.methodology}
- 抄録核心: {art.paper_info.abstract_core}
- 抄録全文（参考）: {art.paper_info.original_abstract or "N/A"}

[臨床的背景 (Context)]
- 臨床的意義: {art.supplementary_context.clinical_significance}
- 人間味のある要素: {art.supplementary_context.patient_stories or "N/A"}
- 専門家の見解: {art.supplementary_context.expert_comments or "N/A"}
---
"""

        prompt = f"""
あなたは医学系メディアの編集長兼ラジオ番組のディレクターです。
最新のNEJM論文（計 {paper_count} 件）を元に、Podcast用音声台本と医療従事者向けのレポートを作成してください。

【構成ルール】
1. Podcast用音声台本 (キー: "script")
   - 登場人物: MaleHost（落ち着いた男性）, FemaleHost（明るい女性）
   - 形式: **必ず各行を「MaleHost: 」または「FemaleHost: 」で始めてください。**
   - 言語: 日本語。
   - ルール: 
     - **ハルシネーションの禁止**: 事実セクションの数値は正確に伝えてください。
     - **文脈の活用**: 臨床的背景や専門家の声を、話の導入や深掘りとして自然に使ってください。
     - **プレースホルダーの禁止**: [自分の名前]などの記号は一切含めず、そのまま放送できる台本にしてください。自己紹介が必要な場合は「NEJM Weekly解説チームです」などの一般名を使ってください。

2. ニュースレポート (キー: "report")
   - 形式: Markdown形式。以下の構成を厳守してください。
     # [インパクトのあるタイトル]
     ## 今週のハイライト
     - [全論文を通じた要点を箇条書きで1-2点]
     ## 論文要約
     ### [論文タイトル] (NEJM論文) または (その他の論文)
     #### 背景と方法
     [詳細かつ分かりやすい解説]
     #### 結果
     [具体的な数値やP値を含む結果]
     #### 結論
     [論文の結び]
     **発行日:** [発行日]  
     **論文リンク:** [[URL]]([URL])
     ## 臨床的意義
     [日本の臨床現場やガイドラインを踏まえた、専門的かつ深い考察]

【論文データ】
{articles_context}
"""
        try:
            self.logger.info("Generating final script and report...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            raw_text = response.text.strip()
            
            # Robust JSON extraction
            try:
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}')
                if start_index != -1 and end_index != -1:
                    json_text = raw_text[start_index:end_index + 1]
                    content = json.loads(json_text)
                else:
                    content = json.loads(raw_text)
            except json.JSONDecodeError:
                # Fallback: regex search
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    content = json.loads(match.group(0))
                else:
                    raise

            # Robust extraction of script and report strings
            res = {}
            for key in ["script", "report"]:
                if key in content:
                    if isinstance(content[key], list):
                        res[key] = "\n".join([str(x) for x in content[key]])
                    else:
                        res[key] = str(content[key])
            
            # Export structured JSON data to output folder
            try:
                import datetime
                today_str = datetime.date.today().strftime("%Y-%m-%d")
                output_dir = "outputs"
                os.makedirs(output_dir, exist_ok=True)
                json_path = os.path.join(output_dir, f"nejm_structured_data_{today_str}.json")
                
                # Convert Pydantic models to dicts for JSON serialization
                serializable_data = [art.dict() for art in processed_articles]
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(serializable_data, f, ensure_ascii=False, indent=2)
                self.logger.info(f"Structured data exported to {json_path}")
            except Exception as e:
                self.logger.warning(f"Failed to export structured JSON: {e}")

            return res
        except Exception as e:
            self.logger.error(f"Error in final content generation: {e}")
            self.logger.debug(f"Raw text that failed: {raw_text if 'raw_text' in locals() else 'N/A'}")
            return None
