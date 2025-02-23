import datetime
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Pobierz zmienną środowiskową z kluczem
credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])

# Utwórz poświadczenia z pliku JSON
creds = service_account.Credentials.from_service_account_info(credentials_info, scopes=['https://www.googleapis.com/auth/drive'])

# Użyj API Google Drive
drive_service = build('drive', 'v3', credentials=creds)

# Test - Pobranie listy plików na Google Drive
results = drive_service.files().list(pageSize=10, fields="files(id, name)").execute()
items = results.get('files', [])
if items:
    print('Pliki na Google Drive:')
    for item in items:
        print(f'{item["name"]} ({item["id"]})')
else:
    print('Brak plików w Google Drive.')

# 📌 Sprawdzenie, czy folder "OLX Scrap" istnieje
folder_name = "OLX Scrap"
query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
response = drive_service.files().list(q=query, fields="files(id, name)").execute()
folders = response.get('files', [])

if not folders:
    print(f"Folder '{folder_name}' nie istnieje! Sprawdź nazwę lub utwórz go ręcznie w Google Drive.")
    folder_id = None
else:
    folder_id = folders[0]['id']
    print(f"Znaleziono folder '{folder_name}', ID: {folder_id}")

# 📌 Utworzenie pustego pliku CSV w folderze Google Drive
if folder_id:
    now = datetime.datetime.now()
    filename = f"test-{now.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    local_file_path = f"/tmp/{filename}"  # Używamy tymczasowego folderu w GitHub Actions

    # Tworzenie pustego pliku lokalnie (potrzebne do przesłania na Drive)
    with open(local_file_path, "w") as f:
        f.write("")  # Plik pusty

    # 📌 Przesyłanie pliku do folderu "OLX Scrap"
    file_metadata = {
        'name': filename,
        'mimeType': 'text/csv',
        'parents': [folder_id]  # Umieszczenie w folderze
    }
    media = MediaFileUpload(local_file_path, mimetype='text/csv', resumable=True)

    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"✅ Utworzono plik: {filename} w folderze '{folder_name}' (ID: {uploaded_file.get('id')})")
