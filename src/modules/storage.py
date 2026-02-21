import os
import json
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

class GoogleDriveStorage:
    def __init__(self, client_id, client_secret, refresh_token):
        self.scopes = ['https://www.googleapis.com/auth/drive.file']
        try:
            from google.oauth2.credentials import Credentials
            
            self.credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=self.scopes
            )
            self.service = build('drive', 'v3', credentials=self.credentials)
            self.logger = logging.getLogger(__name__)
        except Exception as e:
            logging.error(f"Failed to initialize Google Drive service with OAuth2: {e}")
            raise

    def upload_file(self, file_path, folder_id=None, mime_type=None):
        """
        Uploads a file to Google Drive and returns its webViewLink.
        """
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        try:
            self.logger.info(f"Uploading {file_name} to Google Drive...")
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # Make the file readable by anyone with the link (optional/configure as needed)
            self.service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            self.logger.info(f"File uploaded successfully. ID: {file.get('id')}")
            file_id = file.get('id')
            web_view_link = file.get('webViewLink')
            preview_link = f"https://drive.google.com/file/d/{file_id}/preview"

            return {
                "id": file_id,
                "webViewLink": web_view_link,
                "previewLink": preview_link
            }

        except Exception as e:
            self.logger.error(f"Error uploading to Google Drive: {e}")
            return None
