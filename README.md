# NEJM Cardiology Podcast Automation

NEJM（New England Journal of Medicine）の循環器領域の最新論文を自動で収集し、AI（Gemini）による要約と音声解説（Podcast）を生成して配信するシステムです。

## 主な機能

- **ハイブリッド情報収集**: NEJM の RSS フィードを基点とし、**PubMed**（厳密な抄録データ）と **Tavily API**（広範な Web コンテキスト）を組み合わせて情報を収集。
- **タイムリーな処理**: PubMed への抄録登録を待たずに、Tavily を通じて最新の臨床情報をいち早くキャッチアップ。
- **AI 構造化解析**: Gemini (`gemini-3.6-flash`) を使用し、医学的事実（Fact）と臨床的背景（Context）を Pydantic で構造化して抽出。
- **マルチスピーカー音声生成**: Gemini 2.5 Flash (TTS) を使用し、男女2人のホストによる対話形式の Podcast を生成。
- **詳細レポート & ラベル機能**: Markdown レポート内で「NEJM 論文」か「その他の論文」かを自動判定して明記。
- **構造化データのエクスポート**: 処理した論文のメタデータや解析内容を JSON フォーマットで `outputs/` に自動保存。
- **クラウド保存 & 通知**: 生成物は Google Drive にアップロードされ、関係者に Gmail で通知。
- **GitHub Actions による自動化**: 毎週の定期実行（自動化）に対応。

## セットアップ

詳細な設定手順（Google API, GitHub Secrets など）については、[SETUP_GUIDE.md](./SETUP_GUIDE.md) を参照してください。

### 必要条件
- Python 3.11+
- Google Cloud プロジェクト (Drive / Gmail API)
- **Gemini API キー**
- **Tavily API キー**

### ローカルでの実行
1. リポジトリをクローン
2. 依存関係のインストール: `pip install -r requirements.txt`
3. `.env` ファイルを作成し、必要な環境変数を設定（`GEMINI_API_KEY`, `TAVILY_API_KEY`, `PUBMED_EMAIL` 等）
4. 実行: `python main_local.py`（テスト用）または `python main.py`（本番フロー用）

## リポジトリの構成
- `main.py`: メインの実行スクリプト（Drive/Gmail 連携あり）
- `main_local.py`: ローカルテスト用のスクリプト
- `src/modules/`: 
  - `fetcher.py`: RSS/PubMed/Tavily からの論文情報取得
  - `generator.py`: Gemini による構造化データ・レポート・台本の生成
  - `tts_engine.py`: 音声合成処理
  - `storage.py` / `notifier.py`: 保存と通知
- `outputs/`: 生成物（レポート、音声、構造化 JSON）および既読 DOI の管理
- `.github/workflows/`: 自動実行設定
