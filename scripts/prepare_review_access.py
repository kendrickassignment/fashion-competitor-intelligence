"""Grant the rubric's public editor permission. Run only for this fictional review dataset."""

import os

from google.oauth2 import service_account
from googleapiclient.discovery import build


def main():
    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    with build("drive", "v3", credentials=credentials, cache_discovery=False) as api:
        permissions = api.permissions().list(fileId=spreadsheet_id, fields="permissions(id,type,role)").execute()
        public = next((p for p in permissions.get("permissions", []) if p["type"] == "anyone"), None)
        if public:
            api.permissions().update(fileId=spreadsheet_id, permissionId=public["id"],
                                     body={"role": "writer"}, fields="id,type,role").execute()
        else:
            api.permissions().create(fileId=spreadsheet_id,
                                     body={"type": "anyone", "role": "writer", "allowFileDiscovery": False},
                                     fields="id,type,role").execute()
        result = api.permissions().list(fileId=spreadsheet_id, fields="permissions(type,role)").execute()
        assert any(p["type"] == "anyone" and p["role"] == "writer" for p in result["permissions"])
        print("Verified: anyone with the link can edit the review spreadsheet.")


if __name__ == "__main__":
    main()
