# A library for text to speechh conversion
import time
import win32com.client
import datetime
import speech_recognition as sr

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
    listen()