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
