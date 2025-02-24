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
    local_file_path = f"/tmp/{filename}"  # GitHub Actions używa /tmp/

    # Tworzenie pustego pliku lokalnie
    with open(local_file_path, "w") as f:
        f.write("")  # Plik pusty

    # 📌 Przesyłanie pliku do folderu "OLX Scrap"
    file_metadata = {
        'name': filename,
        'mimeType': 'text/csv',
        'parents': [folder_id]
    }
    media = MediaFileUpload(local_file_path, mimetype='text/csv', resumable=True)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"✅ Utworzono plik: {filename} w folderze '{folder_name}' (ID: {uploaded_file.get('id')})")

import re
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
import re
import pandas as pd
from datetime import datetime

def get_olx_items(search_query, category, show_results=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-data-dir=/tmp/chrome_profile")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    base_url = f"https://www.olx.pl/{category}/q-{search_query.replace(' ', '-')}/"
    results = []
    page_number = 1

    while True:
        url = f"{base_url}?page={page_number}"
        driver.get(url)
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        offers = soup.find_all('div', {'data-cy': 'l-card'})

        if not offers:
            print("Brak ofert na stronie. Przerywam przeszukiwanie.")
            break

        for offer in offers:
            try:
                title = offer.find('a').get_text(strip=True) if offer.find('a') else "Brak tytułu"
                price = offer.find('p', {'data-testid': 'ad-price'}).get_text(strip=True) if offer.find('p', {'data-testid': 'ad-price'}) else "Brak ceny"
                location = offer.find('p', {'data-testid': 'location-date'}).get_text(strip=True) if offer.find('p', {'data-testid': 'location-date'}) else "Brak lokalizacji"
                link = "https://www.olx.pl" + offer.find('a')['href'] if offer.find('a') else "Brak linku"
                results.append({'title': title, 'price': price, 'location': location, 'link': link})
            except Exception as e:
                print(f"Błąd podczas parsowania oferty: {e}")
                continue

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '[data-cy="pagination-forward"]')
            if not next_button.is_enabled():
                break
        except NoSuchElementException:
            break

        page_number += 1

    driver.quit()
    
  
    
    # Definiowanie ścieżek dostosowanych do GitHub Actions
    base_path = "/tmp/OLX_Scrap"
    os.makedirs(base_path, exist_ok=True)
    
    file_path = os.path.join(base_path, "results.csv")
    backup_path = os.path.join(base_path, f"Backup/results_backup_{search_query}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    scrap_path = os.path.join(base_path, f"Scrap/scrap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    
    # Tworzenie folderów, jeśli nie istnieją
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
    os.makedirs(os.path.dirname(scrap_path), exist_ok=True)
    
    # Tworzenie kopii zapasowej, jeśli plik istnieje
    if os.path.exists(file_path):
        os.rename(file_path, backup_path)
        print(f"Utworzono kopię zapasową: {backup_path}")
    
    # Tworzenie DataFrame i zapis surowych danych
    df = pd.DataFrame(results)
    df.to_csv(scrap_path, index=False)
    print(f"Zapisano surowe dane do pliku: {scrap_path}")
    
    # Czyszczenie i filtrowanie danych
    df = df.drop_duplicates(subset=['link'])
    keywords = re.sub(r'[^\w\s]', '', search_query).split()
    keywords = [word for word in keywords if word.lower() != "gra"]
    df = df[df['title'].str.contains('|'.join(keywords), case=False, na=False)]
    df = df[~df['link'].str.contains('extended_search')]
    df['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df['ID'] = df['link'].str.extract(r'ID(\w+)\.html')
    df['game'] = search_query
    df['price'] = df['price'].str.replace(',', '.', regex=False)
    df['price'] = df['price'].str.replace(r'[^0-9.]', '', regex=True)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.dropna(subset=['price'])
    df['date_posted'] = df['location'].str.extract(r'(\d+\s+\w+\s+\d+)')
    
    # Konwersja daty z polskich nazw miesięcy
    months = {
        "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04", "maja": "05", "czerwca": "06",
        "lipca": "07", "sierpnia": "08", "września": "09", "października": "10", "listopada": "11", "grudnia": "12"
    }
    
    def convert_date(date_str):
        try:
            day, month_name, year = date_str.split()
            return f"{year}-{months.get(month_name.lower(), '00')}-{day}"
        except:
            return datetime.now().strftime("%Y-%m-%d")
    
    df['date_posted'] = df['date_posted'].apply(convert_date)
    df['date_posted'] = pd.to_datetime(df['date_posted'], errors='coerce')
    df['location'] = df['location'].str.split('-', n=1).str[0]
    df['location'] = df['location'].str.split(',', n=1).str[0].str.strip()
    df = df[['game', 'date', 'ID', 'date_posted', 'title', 'price', 'location', 'link']]
    
    # Jeśli istnieje kopia zapasowa, dołącz stare dane do nowych
    if os.path.exists(backup_path):
        df = pd.concat([pd.read_csv(backup_path), df], ignore_index=True)
    
    # Zapis wynikowego pliku
    df.to_csv(file_path, index=False)
    print(f"Zapisano dane do pliku: {file_path}")
    print(f"Topic: {search_query}")
    print(f"Liczba wierszy: {len(df)}")
    
    df = pd.DataFrame()  # Czyszczenie danych po zapisaniu
