# A library for text to speechh conversion
import time
import win32com.client
import datetime
import wikipedia
import speech_recognition as sr
import webbrowser
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SPOTIFY_CLIENT_ID = 'e8962aec09aa4d24aace46f0bf3a0f0a'
SPOTIFY_CLIENT_SECRET = 'd710ee25cb3947f0a85708170b3496ff'
SPOTIFY_REDIRECT_URL = 'http://127.0.0.1:8888/callback'
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
        
        elif 'on spotify' in query:
            song = query.replace('on spotify','').replace('play','').strip()
            if song:
                try:
                    scope = "user-modify-playback-state user-read-playback-state"
                    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIFY_CLIENT_ID,client_secret=SPOTIFY_CLIENT_SECRET,redirect_uri=SPOTIFY_REDIRECT_URL,scope=scope))
                    Music_results = sp.search(q=song,limit=1)
                    if not Music_results['tracks']['items']:
                        speak(f"Sorry, I could not find the song {song} on spotify.")
                    else:
                        track = Music_results['tracks']['items'][0]
                        track_uri = track['uri']
                        sp.start_playback(uris=[track_uri])
                        speak(f"Playing {track['name']} by {track['artists'][0]['name']} on Spotify")
                except Exception as e:
                    speak("Could not connect to Spotify. Please make sure it is opened before this code started running")
                    print(f"Error: {e}")
            else:
                speak("What song would u like to play on Spotify?")

            speak(f"Searching for {song} on Spotify")
            webbrowser.open(f"https://open.spotify.com/search/SONG%20NAME")
