# A library for text to speechh conversion
import time
import requests
import win32com.client
import datetime
import wikipedia
import speech_recognition as sr
import webbrowser
import os
import pywhatkit
from bs4 import BeautifulSoup
from googlesearch import search as google_search
# Function to speak
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

# main function
if __name__ == "__main__": 
    wish()
    while True:
        query = listen().lower()
        if 'wikipedia' in query:
            speak("Searching Wikipedia...")
            query = query.replace("wikipedia","")
            Wikiresults = wikipedia.summary(query,sentences = 2)
            speak("According to Wikipedia..")
            print(Wikiresults)
            speak(Wikiresults)

        elif 'open youtube' in query:
            webbrowser.open("youtube.com")

        elif 'open google' in query:
            webbrowser.open("google.com")
        
        elif 'open github' in query:
            webbrowser.open('github.com')

        elif 'the time' in query:
            Time = datetime.datetime.now().strftime("%H:%M:%S")
            speak(f"Currently it is {Time}")

        elif 'open code' in query:
            codePath = r"C:\Users\USER\AppData\Local\Programs\Microsoft VS Code\Code.exe"
            os.startfile(codePath)
        
        elif 'play' in query:
            song = query.replace('play','').strip()
            if song:
                speak(f'Playing: {song} on youtube')
                pywhatkit.playonyt(song)
            else:
                speak('Couldnt found the song in Youtube')
        elif 'search' in query:
            search_term = query.replace('search','').strip()
            if search_term:
                speak(f"Searching the web for {search_term} and summarizing")
                try:
                    search_results = list(google_search(search_term,num_results=1))
                    if not search_results:
                        speak("Sorry, I couldn't find any results")
                        continue
                    first_url = search_results[0]
                    headers = {
                        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    }
                    response = requests.get(first_url,headers=headers)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text,'html.parser')
                    page_title = soup.find('title').get_text()

                    first_paragraph = soup.find('p')
                    summary = first_paragraph.get_text().strip() if first_paragraph else "I could not find a summary on the page."

                    speak(f"The first result is titled: {page_title}")
                    speak("Here is summary")
                    print(summary)
                    speak(summary)

                    speak("Opening the page for u now")
                    webbrowser.open(first_url)
                except Exception as e:
                    speak("I had trouble reading the page")
                    if 'first_url' in locals() and first_url:
                        webbrowser.open(first_url)
                    print(f"Search error: {e}")

        elif 'weather' in query:
            api_key = '1f5fb087e340634614cedb20e0715ace'
            base_url = "http://api.openweathermap.org/data/2.5/weather?"
            speak("Which city's weather would u like to know? (only say the name of city)")
            city_name = listen().lower()
            if city_name and city_name != 'none':
                complete_url = f"{base_url}appid={api_key}&q={city_name}&units=metric"
                try:
                    response = requests.get(complete_url)
                    data = response.json()
                    if data['cod'] != '404':
                        main = data["main"]
                        weather_desc = data["weather"][0]['description']
                        temp = main['temp']
                        print(f"temp: {temp} and {weather_desc}")
                        speak(f"The temperature in {city_name} is {temp} degrees celcius with {weather_desc}")

                    else:
                        speak("Sorry I couldn't find the city")
                except Exception as e:
                    speak("Sorry, I couldn;t fetch the weather deatils")
            else:
                speak("I didn't catch the city name")

        elif 'news' in query or 'headlines' in query:
            gnews_api_key = "e75c19434bd1fb1a928ff34b38378099" 
            speak("Fetching the latest news headlines.")

            try:
                news_url = f"https://gnews.io/api/v4/top-headlines?lang=en&country=in&token={gnews_api_key}"
                
                response = requests.get(news_url)
                response.raise_for_status()
                
                news_data = response.json()
                articles = news_data.get("articles", [])
                
                if not articles:
                    speak("Sorry, I couldn't find any news headlines at the moment.")
                else:
                    speak("Here are the top headlines:")
                    for i,article in enumerate(articles[:3],start=1):
                        print(f"Headlines {i}: {article['title']}")
                        print(f"Description: {article['description']}")
                        print(f"Source: {article['source']['name']}")
                        speak(article['title'])
                    
                    speak("That's all for the top headlines.")

            except Exception as e:
                
                speak("Sorry, I encountered an error while fetching the news.")
                print(f"News error: {e}")

