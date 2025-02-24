import os
import json
import time
import re
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

def get_olx_items(search_query, category):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
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
                title = offer.find('h6').text.strip() if offer.find('h6') else "Brak tytułu"
                price = offer.find('p', {'data-testid': 'ad-price'}).text.strip() if offer.find('p', {'data-testid': 'ad-price'}) else "Brak ceny"
                location = offer.find('p', {'data-testid': 'location-date'}).text.strip() if offer.find('p', {'data-testid': 'location-date'}) else "Brak lokalizacji"
                link_element = offer.find('a')
                link = "https://www.olx.pl" + link_element['href'] if link_element else "Brak linku"
                results.append({'title': title, 'price': price, 'location': location, 'link': link})
            except Exception:
                continue

        try:
            next_button = driver.find_element(By.CSS_SELECTOR, '[data-cy="pagination-forward"]')
            if not next_button.is_enabled():
                break
        except NoSuchElementException:
            break

        page_number += 1

    driver.quit()
    df = pd.DataFrame(results)
    df.to_csv(f"results_{search_query}.csv", index=False)
    print(f"Zapisano wyniki dla {search_query}")

if __name__ == "__main__":
    games_df = pd.read_csv("games.csv")
    for _, row in games_df.iterrows():
        last_scraped = datetime.strptime(row['last_scraped'], "%Y-%m-%d %H:%M:%S")
        if (datetime.now() - last_scraped).total_seconds() >= 7200:
            get_olx_items(row['game'], row['category'])
            games_df.at[_, 'last_scraped'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            games_df.to_csv("games.csv", index=False)
