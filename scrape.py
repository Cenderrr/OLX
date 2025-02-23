import datetime
import os
import json
import pandas as pd
import re
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

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

# Konfiguracja Selenium
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Uruchom w trybie bezgłowym
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.binary_location = "/usr/bin/google-chrome"

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

        print(f"Szukam oferty dla: {search_query}")
        print(f"Strona {page_number}")

        if not offers:
            print("Brak ofert na stronie. Przerywam przeszukiwanie.")
            break

        for offer in offers:
            try:
                img_element = offer.find('img', {'class': 'css-8wsg1m'})
                title = img_element['alt'] if img_element and 'alt' in img_element.attrs else "Brak tytułu"

                if title == "Brak tytułu":
                    link_element = offer.find('a')
                    if link_element:
                        link = link_element['href']
                        title = re.sub(r'^/d/oferta/', '', link)
                        title = re.sub(r'-CID\d+-ID\w+\.html$', '', title)
                        title = re.sub(r'-', ' ', title)
                        title = title.capitalize()
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

        page_number += 1

    driver.quit()

    if show_results:
        if results:
            for item in results:
                print(f"Tytuł: {item['title']}")
                print(f"Cena: {item['price']}")
                print(f"Lokalizacja: {item['location']}")
                print(f"Link: {item['link']}")
                print("-" * 40)
        else:
            print("Nie znaleziono żadnych ofert.")

    file_path = '/content/drive/My Drive/OLX Scrap/results.csv'
    backup_path = '/content/drive/My Drive/OLX Scrap/Backup/results_backup.csv'
    scrap_path = '/content/drive/My Drive/OLX Scrap/Scrap/scrap.csv'

    if os.path.exists(file_path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f'/content/drive/My Drive/OLX Scrap/Backup/results_backup_{search_query}_{timestamp}.csv'
        os.rename(file_path, backup_path)
        print(f"Utworzono kopię zapasową: {backup_path}")

    df = pd.DataFrame(results)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    scrap_path = f'/content/drive/My Drive/OLX Scrap/Scrap/scrap_{timestamp}.csv'
    df.to_csv(scrap_path, index=False)
    print(f"Zapisano surowe dane do pliku: {scrap_path}")

    df = df.drop_duplicates(subset=['link'])
    keywords = re.sub(r'[^\w\s]', '', search_query).split()
    keywords = [word for word in keywords if word.lower() != "gra"]
    df = df[df['title'].str.contains('|'.join(keywords), case=False, na=False)]
    df = df[~df['link'].str.contains('extended_search')]
    df['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df['ID'] = df['link'].str.extract(r'ID(\w+)\.html')
    df['game'] = search_query
    df['price'] = df['price'].str.replace(',', '.', regex=False)
    df['price'] = df['price'].str.replace(r'[^0-9.]', '', regex=True)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df = df.dropna(subset=['price'])
    df['date_posted'] = df['location'].str.extract(r'(\d+\s+\w+\s+\d+)')

    months = {
        "stycznia": "01", "lutego": "02", "marca": "03", "kwietnia": "04", "maja": "05",
        "czerwca": "06", "lipca": "07", "sierpnia": "08", "września": "09", "października": "10",
        "listopada": "11", "grudnia": "12"
    }

    def convert_date(date_str):
        try:
            day, month_name, year = date_str.split()
            month = months.get(month_name.lower(), "00")
            formatted_date = f"{year}-{month}-{day}"
            return formatted_date
        except Exception as e:
            return datetime.datetime.now().strftime("%Y-%m-%d")

    df['date_posted'] = df['date_posted'].apply(convert_date)
    df['date_posted'] = pd.to_datetime(df['date_posted'], format='%Y-%m-%d', errors='coerce')

    df['location'] = df['location'].str.split('-', n=1).str[0]
    df['location'] = df['location'].str.split(',', n=1).str[0]
    df['location'] = df['location'].str.strip()

    df = df[['game', 'date', 'ID', 'date_posted', 'title', 'price', 'location', 'link']]

    if os.path.exists(backup_path):
        existing_df = pd.read_csv(backup_path)
        df = pd.concat([existing_df, df], ignore_index=True)

    df.to_csv(file_path, index=False)
    print(f"Zapisano dane do pliku: {file_path}")
    print(f"Topic: {search_query}")
    print(f"Liczba wierszy: {len(df)}")
    df = pd.DataFrame()

success = False

while not success:
    try:
        df_games = pd.read_csv('/content/drive/My Drive/OLX Scrap/games.csv')

        for index, row in df_games.iterrows():
            last_scraped_time = datetime.datetime.strptime(row['last_scraped'], "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            time_diff = now - last_scraped_time

            if time_diff.total_seconds() < 3600:
                print(f"Wyniki {row['game']} są aktualne (mniej niż 1 godzina od ostatniego scrapowania).")
                pass
            else:
                get_olx_items(row['game'], row['category'], show_results=False)

                df_games.at[index, 'last_scraped'] = now.strftime("%Y-%m-%d %H:%M:%S")
                df_games.to_csv('/content/drive/My Drive/OLX Scrap/games.csv', index=False)
                print(f"Zapisano wyniki {row['game']} do pliku games.csv")

        success = True
    except Exception as e:
        print(f"Wystąpił błąd: {e}. Ponawiam pętlę...")
        time.sleep(30)

print("Scrap zakończony pomyślnie")
