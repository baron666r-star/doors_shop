import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://www.doors18.ru/catalog/vhodnye-dveri"
BASE_URL = "https://www.doors18.ru"

os.makedirs("static/images", exist_ok=True)
headers = {'User-Agent': 'Mozilla/5.0'}

print("Загружаем страницу...")
response = requests.get(URL, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')
products = soup.find_all('div', class_='product')
print("Найдено:", len(products))

doors_data = []

for index, prod in enumerate(products, start=1):
    try:
        name = prod.find('a', class_='name').text.strip()
        
        price_tag = prod.find('form', class_='price')
        price_text = price_tag.text.replace('р', '').replace('\xa0', '').strip()
        price_clean = "".join(filter(str.isdigit, price_text))
        price = int(price_clean) if price_clean else 0
        
        img_src = prod.find('a', class_='image').find('img')['src']
        full_img_url = urljoin(BASE_URL, img_src).replace('resize_130_276_3_0_', 'resize_203_204_2_0_')
        img_filename = f"door_{index}.jpg"
        
        img_data = requests.get(full_img_url, headers=headers).content
        with open(f"static/images/{img_filename}", 'wb') as f:
            f.write(img_data)
            
        desc_tag = prod.find('meta', itemprop='description')
        description = desc_tag['content'].strip()[:200] + "..." if desc_tag else "Нет описания."
        
        doors_data.append({
            "id": index, 
            "name": name, 
            "price": price, 
            "image": img_filename, 
            "description": description
        })
        print(f"[{index}] {name}")
    except Exception as e:
        print(f"Ошибка на {index}: {e}")

with open('doors.json', 'w', encoding='utf-8') as f:
    json.dump(doors_data, f, ensure_ascii=False, indent=4)

print(f"Готово! Обработано {len(doors_data)} дверей.")