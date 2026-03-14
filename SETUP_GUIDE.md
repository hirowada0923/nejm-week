# Credentials Setup Guide

このガイドでは、本システムを GitHub Actions で動作させるために必要な設定手順を説明します。

## 1. Google Cloud プロジェクトの準備
まず、Google API を利用するためのベースとなるプロジェクトを作成します。

1.  [Google Cloud Console](https://console.cloud.google.com/) にアクセスします。
2.  「プロジェクトの選択」から「新しいプロジェクト」を作成します（例：`nejm-podcast-automation`）。
3.  **API の有効化**:
    -   サイドメニューの「API とサービス」 > 「ライブラリ」を選択。
    -   **Google Drive API** を検索し、「有効にする」をクリック。
    -   **Gmail API** を検索し、「有効にする」をクリック。

## 2. Google OAuth2 クライアント ID の作成

プログラムがあなた自身の権限で Google Drive にアクセスするための設定です。これを行うことで、個人のストレージ容量（15GB〜）を使用できます。

1.  「API とサービス」 > 「OAuth 同意画面」をクリック。
2.  「外部（External）」を選択して作成。アプリ名などは適当に入力してください。
3.  **テストユーザー**: 自分の Gmail アドレスを追加します（重要）。
4.  「API とサービス」 > 「認証情報」をクリック。
5.  「認証情報を作成」 > 「**OAuth クライアント ID**」を選択。
6.  種類で「**デスクトップ アプリ**」を選択し、作成します。
7.  表示された「**クライアント ID**」と「**クライアント シークレット**」をメモします。

## 3. リフレッシュトークンの取得

GitHub Actions などの自動実行で、ブラウザを開かずに認証を継続させるための「鍵」を取得します。

1.  リポジトリにある `get_refresh_token.py` を手元の PC で実行します。
    ```bash
    python get_refresh_token.py
    ```
2.  手順 2 で取得した「クライアント ID」と「クライアント シークレット」を入力します。
3.  ブラウザが開くので、自分のアカウントで「許可」します。
4.  ターミナルに表示された **G_REFRESH_TOKEN** をコピーします。

## 4. Gmail API の設定（重要）
サービスアカウントで Gmail API を直接使用してメールを送るには、少し複雑な設定が必要です（Google Workspace 管理権限が必要）。
個人アカウント（@gmail.com）の場合、以下のいずれかが簡単です：

-   **方法 A (推奨)**: 「アプリパスワード」を使用した SMTP 送信（Google アカウントの 2 段階認証を有効にし、アプリパスワードを生成）。
-   **方法 B**: OAuth2 のリフレッシュトークンを取得して使用。

今回は最もシンプルな **方法 A（アプリパスワード）** での実装を想定します。
1.  [Google アカウント設定](https://myaccount.google.com/security) > 「2 段階認証プロセス」。
2.  「アプリパスワード」から「その他（名前：NEJM Podcast）」としてパスワード（16 文字）を生成。これを `GMAIL_APP_PASSWORD` とします。

## 5. GitHub Secrets への登録
1.  GitHub のリポジトリの「Settings」 > 「Secrets and variables」 > 「Actions」。
2.  「New repository secret」をクリックし、以下の 3 つ（またはそれ以上）を登録します。

| Secret 名 | 内容 |
| :--- | :--- |
| `GEMINI_API_KEY` | 取得済みの Gemini API キー |
| `TAVILY_API_KEY` | 取得済みの Tavily API キー |
| `G_CLIENT_ID` | 手順 2 で取得したクライアント ID |
| `G_CLIENT_SECRET` | 手順 2 で取得したクライアント シークレット |
| `G_REFRESH_TOKEN` | 手順 3 で取得したリフレッシュトークン |
| `GOOGLE_DRIVE_FOLDER_ID` | 保存先の Google Drive フォルダ ID (URL の末尾) |
| `GMAIL_SENDER_ADDRESS` | あなたの Gmail アドレス |
| `GMAIL_APP_PASSWORD` | 手順 4 で生成したアプリパスワード |
| `NOTIFICATION_RECIPIENT_EMAIL` | 通知を受け取るメールアドレス（カンマ区切りで複数指定可） |
| `PUBMED_EMAIL` | あなたのメールアドレス（PubMed への問い合わせ用） |

これで準備完了です！
