import os
from google_auth_oauthlib.flow import InstalledAppFlow

# OAuth2 Scopes for Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    client_id = input("G_CLIENT_ID を入力してください: ").strip()
    client_secret = input("G_CLIENT_SECRET を入力してください: ").strip()

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # Open local browser for authorization
    creds = flow.run_local_server(port=0)

    print("\n" + "="*50)
    print("以下の情報を .env または GitHub Secrets に設定してください。")
    print("="*50)
    print(f"G_CLIENT_ID={client_id}")
    print(f"G_CLIENT_SECRET={client_secret}")
    print(f"G_REFRESH_TOKEN={creds.refresh_token}")
    print("="*50)

if __name__ == "__main__":
    main()
