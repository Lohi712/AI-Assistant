import datetime
import time
import win32com.client
# A library for text to speechh conversion
import time
import requests
import win32com.client
import datetime
import wikipedia
import speech_recognition as sr
import os
import pywhatkit
from bs4 import BeautifulSoup
import webbrowser
from googlesearch import search as google_search
# Method 1: Try Windows SAPI directly
def speak(audio):
    speaker = win32com.client.Dispatch("SAPI.SpVoice")  # "SAPI.SpVoice" is the official name of the Microsoft Speech API voice feature.
    speaker.speak(audio)

def wish():
    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak("Good Morning Sir!!")
    elif hour >= 12 and hour < 18:
        speak("Good Afternoon Sir!!")
    else:
        speak("Good Evening Sir!!")
    speak("This is VEGA (your Virtual Enhanced General Assistant), How may I help you today!")

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source,duration=1)
        r.pause_threshold = 1
        
        audio = r.listen(source)

    try:
        print("Recognizing...")
        query = r.recognize_google(audio,language='en-in')
        print(f"User said: {query}")
    except Exception as e:
        print("Say that again pleasee...")
        return "None"
    return query

if __name__ == "__main__":
    print("\n🚀 Running wish function...")
    wish()
    while True:
        query = listen().lower()
        if 'search' in query:
            search_term = query.replace('search', '').strip()
            if not search_term:
                speak("What would you like me to search for?")
                continue 

            speak(f"Searching for {search_term} and summarizing the first result.")
            
            try:
                # 1. Get the URL of the first search result
                search_results = list(google_search(search_term, num_results=1))
                if not search_results:
                    speak("Sorry, I could not find any results.")
                    continue

                first_url = search_results[0]
                
                # 2. Scrape the content from that URL
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(first_url, headers=headers)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                # 3. Find the title and the first paragraph to read
                page_title = soup.find('title').get_text()
                
                # Find the first meaningful paragraph for a summary
                first_paragraph = soup.find('p')
                summary = first_paragraph.get_text().strip() if first_paragraph else "I could not find a summary on the page."

                speak(f"The first result is titled: {page_title}")
                speak("Here is a summary:")
                print(summary)
                speak(summary)

                speak("Opening the page for you now.")
                webbrowser.open(first_url)
            except Exception as e:
                # If scraping fails, just open the link as a fallback
                speak("I had trouble reading the page, but I can open it for you.")
                if 'first_url' in locals() and first_url:
                    webbrowser.open(first_url)
                print(f"Search error: {e}")

        elif 'news' in query or 'headlines' in query:
            # Replace with your key from GNews.io
            gnews_api_key = "e75c19434bd1fb1a928ff34b38378099" 
            speak("Fetching the latest news headlines.")

            try:
                # Use the GNews URL and change parameters
                # 'lang=en' for English, 'country=in' for India
                news_url = f"https://gnews.io/api/v4/top-headlines?lang=en&country=in&token={gnews_api_key}"
                
                response = requests.get(news_url)
                response.raise_for_status()
                
                news_data = response.json()
                articles = news_data.get("articles", [])
                
                if not articles:
                    speak("Sorry, I couldn't find any news headlines at the moment.")
                else:
                    speak("Here are the top headlines:")
                    # Read out the top 3 headlines
                    i = 0
                    for article in articles[:3]:
                        print(f"Headlines {i+1}: {article['title']}")
                        print(f"Description: {article['description']}")
                        print(f"Source: {article['source']['name']}")
                        speak(article['title'])
                    
                    speak("That's all for the top headlines.")

            except Exception as e:
                speak("Sorry, I encountered an error while fetching the news.")
                print(f"News error: {e}")
