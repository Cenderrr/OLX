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
# Pobierz zmienną środowiskową z kluczem
credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])

# Utwórz poświadczenia z pliku JSON
creds = service_account.Credentials.from_service_account_info(credentials_info, scopes=['https://www.googleapis.com/auth/drive'])

# Użyj API Google Drive
drive_service = build('drive', 'v3', credentials=creds)

# 📁 Nazwa folderu w Google Drive
FOLDER_NAME = "OLX Scrap"

# 🔍 Znalezienie folderu na Google Drive
def get_drive_folder_id(folder_name):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = response.get('files', [])
    return folders[0]['id'] if folders else None

# 📁 Nazwa folderu w Google Drive
FOLDER_NAME = "OLX Scrap"

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
def upload_file_to_drive_UN(local_path, drive_filename, folder_name):
    folder_id = get_drive_folder_id(folder_name)
    file_metadata = {
        'name': drive_filename,
        'mimeType': 'text/csv',
        'parents': [folder_id]  # Dodaj folder_id tutaj
    }
    media = MediaFileUpload(local_path, mimetype='text/csv', resumable=True)

    # Sprawdź, czy plik już istnieje w folderze
    query = f"name='{drive_filename}' and '{folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id)").execute()
    existing_files = response.get('files', [])

    if existing_files:
        # Jeśli plik istnieje, zaktualizuj go
        file_id = existing_files[0]['id']
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print(f"Zaktualizowano plik: {drive_filename}")
    else:
        # Jeśli plik nie istnieje, utwórz nowy
        drive_service.files().create(body=file_metadata, media_body=media).execute()
        print(f"Przesłano nowy plik: {drive_filename}")

# 🔍 Pobranie ofert z OLX
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
        time.sleep(15)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        offers = soup.find_all('div', {'data-cy': 'l-card'})
        print(f"Szukam oferty dla: {search_query}")
        print(f"Strona {page_number}")

        if not offers:
            print("Brak ofert na stronie. Przerywam przeszukiwanie.")
            break

        for offer in offers:
            try:
                # Tytuł oferty (z atrybutu alt obrazka)
                img_element = offer.find('img', {'class': 'css-8wsg1m'})  # Zaktualizowany selektor
                title = img_element['alt'] if img_element and 'alt' in img_element.attrs else "Brak tytułu"

                # Jeśli tytuł nie został znaleziony, pobierz go z linku
                if title == "Brak tytułu":
                    link_element = offer.find('a')
                    if link_element:
                        link = link_element['href']
                        # Przekształć link w tytuł
                        title = re.sub(r'^/d/oferta/', '', link)  # Usuń początek linku
                        title = re.sub(r'-CID\d+-ID\w+\.html$', '', title)  # Usuń końcówkę linku
                        title = re.sub(r'-', ' ', title)  # Zamień myślniki na spacje
                        title = title.capitalize()  # Pierwsza litera wielka
                    else:
                        title = "Brak tytułu"
            
                price_element = offer.find('p', {'data-testid': 'ad-price'})
                price = price_element.get_text(strip=True) if price_element else "Brak ceny"

                location_element = offer.find('p', {'data-testid': 'location-date'})
                location = location_element.get_text(strip=True) if location_element else "Brak lokalizacji"
                
                link_element = offer.find('a')
                link = "https://www.olx.pl" + link_element['href'] if link_element else "Brak linku"

                results.append({
                    'title': title,
                    'price': price,
                    'location': location,
                    'link': link
                })

            except Exception as e:
                print(f"Błąd podczas parsowania oferty: {e}")
                continue

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '[data-cy="pagination-forward"]')
            if not next_button.is_enabled():
                print("Osiągnięto ostatnią stronę. Przerywam przeszukiwanie.")
                break
        except NoSuchElementException:
            print("Brak przycisku 'Następna strona'. Przerywam przeszukiwanie.")
            break

        # Przejdź do następnej strony
        page_number += 1

    # Zamknij przeglądarkę
    driver.quit()
    return results

# 📊 Przetwarzanie i zapis danych
# 📊 Przetwarzanie i zapis danych
def process_and_save_results(results, search_query):
    now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Ścieżki do plików
    base_dir = '/tmp'
    file_path = os.path.join(base_dir, 'results.csv')
    backup_dir = os.path.join(base_dir, 'Backup')
    scrap_dir = os.path.join(base_dir, 'Scrap')

    # Utwórz katalogi, jeśli nie istnieją
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(scrap_dir, exist_ok=True)

    backup_path = os.path.join(backup_dir, f'results_backup_{now}.csv')
    scrap_path = os.path.join(scrap_dir, f'scrap_{search_query}_{now}.csv')

    # Sprawdź, czy plik już istnieje i utwórz kopię zapasową
    if os.path.exists(file_path):
        os.rename(file_path, backup_path)

        upload_file_to_drive_UN(backup_path, f'results_backup_{now}.csv', "Backup")
        print(f"Utworzono kopię zapasową: {backup_path}")

    # Utwórz DataFrame na podstawie listy `results`
    df = pd.DataFrame(results)

    # Zapisz surowe dane do pliku CSV
    df.to_csv(scrap_path, index=False)
    '''
download_file_from_drive("results.csv", "/tmp/results.csv")
results_file = "/tmp/results.csv"
results = pd.read_csv(results_file)
#results.loc[1, 'game'] = 'gra x'
results.to_csv(results_file, index=False)
upload_file_to_drive(results_file, "results.csv")
'''
    upload_file_to_drive_UN(scrap_path, f'scrap_{search_query}_{now}.csv', "Scrap")
    print(f"Zapisano surowe dane do pliku: {scrap_path}")

    # Usuń duplikaty w kolumnie link
    df = df.drop_duplicates(subset=['link'])

    # Przetwarzanie tytułów
    keywords = re.sub(r'[^\w\s]', '', search_query).split()
    keywords = [word for word in keywords if word.lower() != "gra"]
    df = df[df['title'].str.contains('|'.join(keywords), case=False, na=False)]

    # Usuń wiersze zawierające "extended_search" w linku
    df = df[~df['link'].str.contains('extended_search')]

    # Dodanie kolumny daty
    df['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Wyciągnięcie ID z linku
    df['ID'] = df['link'].str.extract(r'ID(\w+)\.html')

    # Dodanie kolumny game
    df['game'] = search_query

    # Czyszczenie i konwersja cen
    df['price'] = df['price'].str.replace(',', '.', regex=False)
    df['price'] = df['price'].str.replace(r'[^0-9.]', '', regex=True)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.dropna(subset=['price'])

    # Parsowanie daty z location
    df['date_posted'] = df['location'].str.extract(r'(\d+\s+\w+\s+\d+)')
    months = {"stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04", "maja": "05", "czerwca": "06", "lipca": "07", "sierpnia": "08", "września": "09", "października": "10", "listopada": "11", "grudnia": "12"}

    def convert_date(date_str):
        try:
            day, month_name, year = date_str.split()
            month = months.get(month_name.lower(), "00")
            return f"{year}-{month}-{day}"
        except Exception:
            return datetime.datetime.now().strftime("%Y-%m-%d")

    df['date_posted'] = df['date_posted'].apply(convert_date)
    #df['date_posted'] = pd.to_datetime(df['date_posted'], format='%Y-%m-%d', errors='coerce')

    # Czyszczenie kolumny location
    df['location'] = df['location'].str.split('-', n=1).str[0]
    df['location'] = df['location'].str.split(',', n=1).str[0]
    df['location'] = df['location'].str.strip()

    # Kolejność kolumn
    df = df[['game', 'date', 'ID', 'date_posted', 'title', 'price', 'location', 'link']]

    # Wyświetl podsumowanie
    print(f"Topic: {search_query}")
    print(f"Liczba wierszy: {len(df)}")

    # Wczytaj istniejące dane, jeśli plik istnieje
    download_file_from_drive("results.csv", "/tmp/results_prev.csv")
    results_prev_file = "/tmp/results_prev.csv"
    results_prev = pd.read_csv(results_prev_file)
    #print("results_prev:")
    #print(results_prev)
    #print("-----------------------------------------------")
    #print("df:")
    #print(df)
    #print("-----------------------------------------------")
    df = pd.concat([results_prev, df], ignore_index=True)
    #print("df - po concacie:")
    #print(df)
    #print("-----------------------------------------------")



    '''
    download_file_from_drive("results.csv", "/tmp/results.csv")
    results_file = "/tmp/results.csv"
    results = pd.read_csv(results_file)
'''
    # Zapisz przetworzone dane do pliku
    df.to_csv(file_path, index=False)
    print(f"Zapisano dane do pliku: {file_path}")
    upload_file_to_drive_UN(file_path, 'results.csv', "OLX Scrap")

    
# 📥 Pobranie listy gier z Google Drive
def scrape_games_from_drive():
    games_file = "/tmp/games.csv"
    success = False

    while not success:
        try:
            if not download_file_from_drive("games.csv", games_file):
                print("Plik games.csv nie istnieje. Tworzę nowy...")
                df_games = pd.DataFrame(columns=['game', 'category', 'last_scraped'])
                df_games.to_csv(games_file, index=False)
                upload_file_to_drive_UN(games_file, "games.csv", "OLX Scrap")
                return

            df_games = pd.read_csv(games_file)


            for index, row in df_games.iterrows():
                last_scraped_str = row.get('last_scraped', '')

                if last_scraped_str:
                    try:
                        last_scraped = datetime.datetime.strptime(last_scraped_str, "%Y-%m-%d %H:%M:%S")
                        now = datetime.datetime.now()
                        if (now - last_scraped).total_seconds() < 3600:
                            print(f"Wyniki dla {row['game']} są aktualne.")
                            continue
                    except ValueError:
                        print(f"Błędny format daty w last_scraped dla {row['game']}, aktualizacja...")

                results = get_olx_items(row['game'], row['category'])
                # stop 1 - get olx items - search querry - row kategoria stop 1 #
                if results:
                    # stop 2 - process and save - results
                    process_and_save_results(results, row['game'])
                    now = datetime.datetime.now()
                    df_games.at[index, 'last_scraped'] = now.strftime("%Y-%m-%d %H:%M:%S")
                    df_games.to_csv(games_file, index=False)
                    upload_file_to_drive_UN(games_file, "games.csv", "OLX Scrap")

                    print(f"Zapisano wyniki dla {row['game']} i zaktualizowano plik games.csv.")

            success = True

        except Exception as e:
            print(f"Wystąpił błąd: {e}. Ponawiam pętlę...")
            time.sleep(30)

    print("✅ Scrapowanie zakończone pomyślnie.")
    
# 🚀 Uruchomienie skryptu
if __name__ == "__main__":
    scrape_games_from_drive()
