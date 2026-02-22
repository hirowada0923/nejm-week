# NEJM Cardiology Podcast Automation

NEJM（New England Journal of Medicine）の循環器領域の最新論文を自動で収集し、AI（Gemini）による要約と音声解説（Podcast）を生成して配信するシステムです。

## 主な機能

- **自動収集**: NEJM の RSS フィードから循環器系の「Original Article」を自動でピックアップ。
- **AI 要約 & 台本作成**: Gemini 3.0 Flash を使用し、論文の要旨を日本語で分かりやすく解説。
- **マルチスピーカー音声生成**: Gemini 2.5 Flash (TTS) を使用し、男女2人のホストによる対話形式の Podcast を生成。
- **クラウド保存**: 生成された音声とレポートは自動的に Google Drive にアップロード。
- **多宛先通知**: 指定した複数のメールアドレスに Gmail 経由で通知を送信。
- **GitHub Actions による自動化**: 毎週月曜日の朝 04:00 (JST) に完全自動で実行。
- **アトミック処理 & クリーンアップ**: 失敗時のリトライ機能を備え、実行後の不要な一時ファイルは自動削除。
- **モバイル最適化**: iPhone 等のモバイルブラウザで直接再生可能なリンク形式を採用。

## セットアップ

詳細な設定手順（Google API, GitHub Secrets など）については、[SETUP_GUIDE.md](./SETUP_GUIDE.md) を参照してください。

### 必要条件
- Python 3.11+
- Google Cloud プロジェクト (Compute / Drive / Gmail API)
- Gemini API キー

### ローカルでの実行
1. リポジトリをクローン
2. 依存関係のインストール: `pip install -r requirements.txt`
3. `.env` ファイルを作成し、必要な環境変数を設定
4. 実行: `python main.py`

## リポジトリの構成
- `main.py`: メインの実行スクリプト（自動化用）
- `main_local.py`: ローカルテスト用の軽量スクリプト
- `src/modules/`: 各種機能モジュール（取得、生成、保存、通知）
- `outputs/`: 処理済み記事の履歴管理
- `.github/workflows/`: GitHub Actions の設定ファイル
