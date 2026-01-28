from scrape import scrape_data
from clean import clean_data, save_data, load_data

def main():
    raw_data = scrape_data()

    cleaned_data = clean_data(raw_data)

    save_data(cleaned_data)

if __name__ == '__main__':
    main()