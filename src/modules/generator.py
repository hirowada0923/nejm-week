import os
import logging
import json
import re
from google import genai
from google.genai import types

class ScriptGenerator:
    def __init__(self, api_key, model_name="gemini-3-flash-preview"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)

    def generate_content(self, papers_text):
        """
        Generates both a podcast script and a readable report.
        Strictly filters for papers with abstracts to prevent hallucinations.
        """
        # Layer 2: Implement programmatic abstract check
        # Split MEDLINE raw text into individual records
        records = re.split(r'\n\s*\n', papers_text.strip())
        valid_papers = []
        for record in records:
            if "TI  - " in record and "AB  - " in record:
                valid_papers.append(record)
        
        if not valid_papers:
            self.logger.warning("No papers with abstracts found for content generation.")
            return None

        paper_count = len(valid_papers)
        filtered_text = "\n\n".join(valid_papers)

        prompt = f"""
あなたは医学系メディアの編集長兼ラジオ番組のディレクターです。以下のNEJM（New England Journal of Medicine）の循環器領域の論文アブストラクト（計 {paper_count} 件）を元に、2種類のコンテンツを作成してください。

【最重要ルール：ハルシネーションの禁止】
- **提供されたアブストラクト（ABフィールド）に記載されている情報のみ**を根拠にしてください。
- 試験の症例数、P値、具体的な数値、主要評価項目などは、テキストに明記されていない場合は絶対に作り出さないでください。
- 情報が不足している場合は「具体的なデータは公開されていません」と述べるか、その項目をスキップしてください。

1. 【Podcast用音声台本】
   - 登場人物: MaleHost（落ち着いた男性）, FemaleHost（明るい女性）
   - 形式: **必ず各行を「MaleHost: 」または「FemaleHost: 」で始めてください（システムが話者を識別するために必須です）。**
   - 構成ルール: 
     - **名前の名乗り禁止**: 台本の内容（話す言葉）の中で、自分のことを「MaleHost」や「FemaleHost」と呼んだり、名乗ったりしないでください。
     - **自然な会話**: 司会者としての自然な掛け合いにしてください。日本の鍵括弧（「」）は使用しないでください。
   - 内容: 
     - 挨拶は最小限に。冒頭で「今週は {paper_count} 件の最新論文を紹介します」と伝えてください。
     - **各論文1分〜2分程度**で解説してください。
     - 専門医にとって常識的な背景知識は省き、具体的な結果（数値）、結論、Take-home messageに集中してください。
     - 難解な用語の補足は、正確性を損なわない範囲で行ってください。

2. 【読者用ニュースレター・レポート】
   - 構成: 
     - 今週のハイライト（計 {paper_count} 件）
     - 各論文の要約（背景は最小限。結果・数値を詳述）
     - **発行日**（提供されたデータの DP フィールドを記載してください）
     - **論文リンク**（提供されたデータの LINK フィールドを記載してください）
     - 臨床的意義（日本の医師にとっての意義）
   - 形式: Markdown形式。

【出力形式】
JSON形式（キー: "script", "report"）で出力してください。

【論文データ】
{filtered_text}
"""
        try:
            self.logger.info("Generating content (Script + Report) with Gemini...")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            raw_text = response.text.strip()
            
            # Robust JSON extraction: look for the first '{' and the last '}'
            # This handles cases where Gemini might include markdown blocks or extra text
            try:
                # Find start and end of JSON if it's wrapped in other text
                start_index = raw_text.find('{')
                end_index = raw_text.rfind('}')
                if start_index != -1 and end_index != -1:
                    json_text = raw_text[start_index:end_index + 1]
                    content = json.loads(json_text)
                else:
                    content = json.loads(raw_text)
            except json.JSONDecodeError as jde:
                self.logger.error(f"JSON parsing error: {jde}")
                self.logger.debug(f"Raw response text: {raw_text}")
                # Try simple regex extraction as a last resort
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    content = json.loads(match.group(0))
                else:
                    raise
            
            # Ensure contents are strings (sometimes Gemini returns lists of strings or objects in JSON mode)
            for key in ["script", "report"]:
                if key in content:
                    if isinstance(content[key], list):
                        processed_lines = []
                        for item in content[key]:
                            if isinstance(item, dict):
                                # If it's a dict, try to combine key-values into a string
                                # e.g., {"speaker": "MaleHost", "text": "..."} -> "MaleHost: ..."
                                # or {"title": "...", "content": "..."} for report
                                if "speaker" in item and "text" in item:
                                    processed_lines.append(f"{item['speaker']}: {item['text']}")
                                else:
                                    processed_lines.append(": ".join([str(v) for v in item.values()]))
                            else:
                                processed_lines.append(str(item))
                        content[key] = "\n".join(processed_lines)
                    elif not isinstance(content[key], str):
                        content[key] = str(content[key])
            
            return content
        except Exception as e:
            self.logger.error(f"Error in content generation or parsing: {e}")
            self.logger.debug(f"Raw text that failed: {raw_text if 'raw_text' in locals() else 'N/A'}")
            return None
