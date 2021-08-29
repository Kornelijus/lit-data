import requests
from bs4 import BeautifulSoup
url = "https://koronastop.lrv.lt/"
page = BeautifulSoup(requests.get(url).content, 'html-parser')
stats = page.find('div', class_='stats_list').find_all('div', class_='stats_item')

def parse_field_value(index):
    return int(stats[index].find('div', class_="value").text.strip())

def get_stats():
    stats_arr = []
    for stat in stats:
        title = stat.find('div', class_='title')
        value = stat.find('div', class_='value')
        stats_arr.append(f'{title.text}: {value.text.strip()}')
    return stats_arr

def get_cases():
    return parse_field_value(0)

def get_deaths():
    return parse_field_value(1)

def get_positive_percentage():
    return float(stats[3].find('div', class_="value").text.strip().replace(',','.')[:-1])

def get_vaccinated():
    return parse_field_value(4)


