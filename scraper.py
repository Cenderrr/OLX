#
import os
import json
import time
import pandas as pd
import datetime
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 🔑 Uwierzytelnienie do Google Drive
credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = service_account.Credentials.from_service_account_info(
    credentials_info, scopes=['https://www.googleapis.com/auth/drive']
)
drive_service = build('drive', 'v3', credentials=creds)

# 📁 Nazwa folderu w Google Drive
FOLDER_NAME = "OLX Scrap"

# 🔍 Znalezienie folderu na Google Drive
def get_drive_folder_id(folder_name):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = response.get('files', [])
    return folders[0]['id'] if folders else None

folder_id = get_drive_folder_id(FOLDER_NAME)
if not folder_id:
    raise FileNotFoundError(f"Folder '{FOLDER_NAME}' nie istnieje w Google Drive!")

# 📌 Pobranie pliku z Google Drive
def download_file_from_drive(file_name, local_path):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get('files', [])
    if not files:
        print(f"Plik '{file_name}' nie istnieje. Tworzę nowy...")
        return False
    file_id = files[0]['id']
    
    request = drive_service.files().get_media(fileId=file_id)
    with open(local_path, "wb") as f:
        f.write(request.execute())
    print(f"Pobrano plik: {file_name}")
    return True

# 📤 Wysyłanie pliku do Google Drive
def upload_file_to_drive(local_path, drive_filename):
    file_metadata = {
        'name': drive_filename,
        'mimeType': 'text/csv',
        'parents': [folder_id]
    }
    media = MediaFileUpload(local_path, mimetype='text/csv', resumable=True)
    
    query = f"name='{drive_filename}' and '{folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id)").execute()
    existing_files = response.get('files', [])

    if existing_files:
        file_id = existing_files[0]['id']
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print(f"Zaktualizowano plik: {drive_filename}")
    else:
        drive_service.files().create(body=file_metadata, media_body=media).execute()
        print(f"Przesłano nowy plik: {drive_filename}")

# 🔍 Pobranie ofert z OLX
def get_olx_items(search_query, category):
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
            break

        for offer in offers:
            try:
                img_element = offer.find('img', {'class': 'css-8wsg1m'})
                title = img_element['alt'] if img_element else "Brak tytułu"
                price = offer.find('p', {'data-testid': 'ad-price'}).get_text(strip=True) if offer.find('p', {'data-testid': 'ad-price'}) else "Brak ceny"
                location = offer.find('p', {'data-testid': 'location-date'}).get_text(strip=True) if offer.find('p', {'data-testid': 'location-date'}) else "Brak lokalizacji"
                link_element = offer.find('a')
                link = "https://www.olx.pl" + link_element['href'] if link_element else "Brak linku"

                results.append({'title': title, 'price': price, 'location': location, 'link': link})
            except Exception as e:
                print(f"Błąd: {e}")
                continue

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '[data-cy="pagination-forward"]')
            if not next_button.is_enabled():
                break
        except NoSuchElementException:
            break

        page_number += 1

    driver.quit()
    return results

# 📊 Przetwarzanie i zapis danych
def process_and_save_results(results, search_query):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    local_file = f"/tmp/results_{now}.csv"

    df = pd.DataFrame(results)
    df.to_csv(local_file, index=False)
    
    upload_file_to_drive(local_file, "results.csv")

    print(f"✅ Zapisano wyniki dla: {search_query}")

# 📥 Pobranie listy gier z Google Drive
def scrape_games_from_drive():
    games_file = "/tmp/games.csv"
    success = False

    def scrape_games_from_drive():
    games_file = "/tmp/games.csv"
    success = False

    while not success:
        try:
            if not download_file_from_drive("games.csv", games_file):
                print("Plik games.csv nie istnieje. Tworzę nowy...")
                df_games = pd.DataFrame(columns=['game', 'category', 'last_scraped'])
                df_games.to_csv(games_file, index=False)
                upload_file_to_drive(games_file, "games.csv")
                return

            df_games = pd.read_csv(games_file)
            now = datetime.datetime.now()

            for index, row in df_games.iterrows():
                last_scraped_str = row.get('last_scraped', '')
                
                if last_scraped_str:
                    try:
                        last_scraped = datetime.datetime.strptime(last_scraped_str, "%Y-%m-%d %H:%M:%S")
                        if (now - last_scraped).total_seconds() < 3600:
                            print(f"Wyniki dla {row['game']} są aktualne.")
                            continue
                    except ValueError:
                        print(f"Błędny format daty w last_scraped dla {row['game']}, aktualizacja...")
                
                results = get_olx_items(row['game'], row['category'])
                if results:
                    process_and_save_results(results, row['game'])
                    
                    df_games.at[index, 'last_scraped'] = now.strftime("%Y-%m-%d %H:%M:%S")
                    df_games.to_csv(games_file, index=False)
                    upload_file_to_drive(games_file, "games.csv")
                    
                    print(f"Zapisano wyniki dla {row['game']} i zaktualizowano plik games.csv.")

            success = True
        
        except Exception as e:
            print(f"Wystąpił błąd: {e}. Ponawiam pętlę...")
            time.sleep(30)

    print("✅ Scrapowanie zakończone pomyślnie.")

# 🚀 Uruchomienie skryptu
if __name__ == "__main__":
    scrape_games_from_drive()
