import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from openai import OpenAI
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access the OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')

# Define the entire function to scrape and extract metadata
def process_url(url, max_tokens_per_chunk=500):
    def scrape_full_page(url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        body_content = soup.body

        if body_content:
            for tag in body_content(["script", "style", "nav", "aside", "footer", "header", "noscript"]):
                tag.extract()

        remove_all_attributes_except_href(body_content)
        remove_empty_tags(body_content)
        clean_content = remove_tags(str(soup.body))
        return str(clean_content)

    def remove_all_attributes_except_href(soup):
        for tag in soup.find_all(True):
            if "href" in tag.attrs:
                tag.attrs = {"href": tag.attrs["href"]}
            else:
                tag.attrs = {}

    def remove_empty_tags(soup):
        for tag in soup.find_all(True):
            if tag.name == 'a':
                continue
            if not tag.get_text(strip=True) and not tag.attrs:
                tag.decompose()
            elif len(tag.contents) == 1 and isinstance(tag.contents[0], str):
                tag.unwrap()

    def remove_tags(html_content):
        clean_content = re.sub(r'</?(div|body|button|li|ul|section|span|p|svg|ol)\s*[^>]*>', '', html_content)
        return clean_content

    def extract_metadata(text):
        client = OpenAI()
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an experienced news article scraper."},
                {
                    "role": "user",
                    "content": f"""
                    Here is the html structure from a news article:
                    {text}

                    Please extract:
                    - Title of the article
                    - URL of the article
                    - Published date (if available)

                    for all articles from the beginning

                    give the output in JSON format.
                    """
                }
            ]
        )
        return completion.choices[0].message

    def chunk_data(text, max_tokens_per_chunk):
        chunks = []
        current_chunk = []
        current_token_count = 0

        def estimate_token_count(text):
            return len(text.split())

        words = text.split()

        for word in words:
            token_count = estimate_token_count(word)
            if current_token_count + token_count > max_tokens_per_chunk:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_token_count = token_count
            else:
                current_chunk.append(word)
                current_token_count += token_count

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    full_text = scrape_full_page(url)
    chunks = chunk_data(full_text, max_tokens_per_chunk)

    metadata_list = []
    for chunk in chunks:
        metadata = extract_metadata(chunk)
        metadata_list.append(metadata.content)

    return metadata_list


# Streamlit app interface
def main():
    st.title("News Scraper")
    url_input = st.text_input("Enter the URL of a news site:")
    
    if url_input:
        st.write("Fetching and processing data...")
        data = process_url(url_input)
        
        # Remove the ` ```json ` and ` \n ` formatting from each chunk
        cleaned_json_strings = [chunk.replace('```json', '').replace('```', '').strip() for chunk in data]

        articles_list = []
        for json_str in cleaned_json_strings:
            # Parse the JSON string into a Python list of dictionaries
            articles_list.extend(json.loads(json_str))

        for article in articles_list:
            st.write(article)

if __name__ == "__main__":
    main()
