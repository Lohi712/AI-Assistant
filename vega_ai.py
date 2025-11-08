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
import pyautogui
from googlesearch import search as google_search
import smtplib
import google.generativeai as genai
import pvporcupine
import pyaudio
import struct
from ddgs import DDGS
import re

# Function to speak
def speak(audio):
    speaker = win32com.client.Dispatch("SAPI.SpVoice")  # "SAPI.SpVoice" is the official name of the Microsoft Speech API voice feature.
    speaker.speak(audio)

def wake_up():
    keyword_path = 'Hey-Vega_en_windows_v3_0_0.ppn'
    try:
        porcupine = pvporcupine.create(access_key= os.getenv('PICOVOICE_ACCESS_KEY'),keyword_paths=[keyword_path])
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(rate= porcupine.sample_rate,channels=1,format=pyaudio.paInt16,input=True,frames_per_buffer=porcupine.frame_length)
        print("Listening for wake word ('VEGA')...")

        while True:
            # Continuously reads small chunks of audio data from the microphone
            pcm= audio_stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" *porcupine.frame_length,pcm)      # "h" = short integer)

            keyword_index = porcupine.process(pcm)

            if keyword_index >= 0:
                print(f"Wake word detected: {keyword_path}")
                audio_stream.close()
                pa.terminate()
                porcupine.delete()
                return True
    except Exception as e:
        print(F"Error in wake up function: {e}")
        return False
def cmd_format(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # remove bold
    text = re.sub(r'\* ', '- ', text)             # convert bullet
    return text

def wish():
    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak("Good Morning Sir!!")
    elif hour >= 12 and hour < 18:
        speak("Good Afternoon Sir!!")
    else:
        speak("Good Evening Sir!!")
    speak("This is VEGA (your Virtual Enhanced General Assistant), How may I help you today!")

def conversation(query):
    conv_api = os.getenv("GOOGLE_AI_API_KEY")
    if not conv_api:
        return "API key is missing."
    try:
        genai.configure(api_key=conv_api)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(query)
        r = cmd_format(response.text)
        return r
    except Exception as e:
        print(f"AI Error: {e}")
        return "Sorry my brain is not working"

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source,duration=1)
        r.pause_threshold = 1
        try:
            audio = r.listen(source,timeout=5,phrase_time_limit=15)
        except sr.WaitTimeoutError:
            speak("I didn't hear anything please try again")
            return "None"   

    try:
        print("Recognizing...")
        query = r.recognize_google(audio,language='en-in')
        print(f"User said: {query}")
    except Exception as e:
        print("Say that again pleasee...")
        return "None"
    return query

def mail(to,subject,body):
    gmail_user = 'quantmech19@gmail.com'
    gmail_psw = os.getenv('GMAIL_APP_PASSWORD')
    if not gmail_psw:
        # This message will tell you if the variable is missing
        print("CRITICAL ERROR: The GMAIL_APP_PASSWORD environment variable was not found.")
        speak("I could not find the password environment variable. Please set it in the terminal before running the script.")
        return False
    try:
        message = f"Subject: {subject}\n\n{body}"
        server = smtplib.SMTP('smtp.gmail.com',587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user,gmail_psw)
        server.sendmail(gmail_user,to,message)
        server.close()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# main function
if __name__ == "__main__": 
    while True:
        if wake_up():
            wish()
            print(f"Currently using google-generativeai version: {genai.__version__}")
            while True:
                query = listen().lower()
                if 'wikipedia' in query:
                    speak("Searching Wikipedia...")
                    stop_words = ['search','for','the','country','in','item','on','wikipedia','about','tell','me','who','is','what','an']
                    query_words = query.split()
                    clean_words = []
                    for word in query_words:
                        if word not in stop_words:
                            clean_words.append(word)
                    clean_query = " ".join(clean_words)
                    print(clean_query)
                    if not clean_words:
                        speak("I can hear you saying Wikipedia but i couldn't get the topic for which i have to search. Please try again")
                        continue

                    try:
                        Wikiresults = wikipedia.summary(clean_query,sentences = 2, auto_suggest = True)
                        speak("According to Wikipedia..")
                        print(Wikiresults)
                        speak(Wikiresults)
                    except wikipedia.exceptions.DisambiguationError as e:
                        speak(f"Your search for {clean_query} is ambiguous. It could refer to many things.")
                        print(f"Disambiguation Error: {clean_query} may refer to: ")
                        print(e.options)
                        speak("Please be more specific..")
                    except wikipedia.exceptions.PageError:
                        speak(f"Sorry couldn't find page for {clean_query} in wikipedia")
                    except Exception as e:
                        speak(f"Sorry some error occurred while searching in wikipedia")
                        print(f"Wikipiedia error: {e}")

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
                    if not search_term:
                        speak("What would u like to search?")
                        continue
                    
                    speak(f"Searching the web for {search_term} and summarizing")
                    try:
                        with DDGS() as ddgs:
                            search_results = list(ddgs.text(search_term,num_results=1))
                        if not search_results:
                            speak("Sorry, I couldn't find any results")
                            continue
                        first_result = search_results[0]
                        page_title = first_result['title']
                        summary = first_result['body']
                        first_url = first_result['href']

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

                elif 'whatsapp' in query:
                    speak("Who should i send the message to?")
                    reciptent_name = input("Enter the reciptent name: ")
                    speak(f"Got it. What message do  wanna send to {reciptent_name}")
                    print(f"Listening the message for {reciptent_name}")
                    message = input("Enter the message: ")

                    while message == "None":
                        speak("Sorry, I didn't catch the message. Say it again")
                        message = listen()
                        continue
                    speak(f"Preparing to send the message to {reciptent_name}")

                    try:
                        pyautogui.press('win')
                        time.sleep(1)
                        pyautogui.write('Whatsapp')
                        time.sleep(1)
                        pyautogui.press('enter')
                        time.sleep(2)
                        pyautogui.hotkey('ctrl','f')
                        time.sleep(1)
                        pyautogui.write(reciptent_name)
                        time.sleep(1)
                        pyautogui.press('enter')
                        time.sleep(1)
                        pyautogui.press('tab')
                        time.sleep(1)
                        pyautogui.press('enter')
                        time.sleep(1)
                        text_box_loc = pyautogui.locateCenterOnScreen('WhatsappTextBox.png',confidence=0.8)
                        if text_box_loc:
                            pyautogui.click(text_box_loc)
                            time.sleep(1)
                        else:
                            speak("Sorry i couldn't get the textbox")
                            continue
                        pyautogui.write(message)
                        time.sleep(1)
                        pyautogui.press('enter')

                        speak("The Message has been sent")
                        time.sleep(2)
                        pyautogui.hotkey('alt','f4')

                    except Exception as e:
                        speak("Sorry, I encountered an error while trying to control whatsapp")
                        print(f"Whatsapp error: {e}")

                elif 'email' in query:
                    speak("Who is the receiptent? Please type their email address")
                    reciptent_email = input("Enter reciptent's email: ")
                    speak("What is the subject of the email?")
                    subject = listen()
                    while subject == "None":
                        speak("I didn't catch the subject please try again")
                        subject = listen()
                    speak("Now lets say the body of your email")
                    body = listen()
                    while body == "None":
                        speak("Sorry didn't got the body, please try again")
                        body = listen()

                    speak("Authenticating and sending email...")
                    if mail(reciptent_email,subject,body):
                        speak("email has been sent")
                    else:
                        speak("Sorry email couldn't be sent")

                elif 'go to sleep' in query or 'bye' in query or 'exit' in query:
                    speak("GoodBye Sir. Shutting Down")
                    break

                else:
                    if query and query != "none":
                        speak("Let me think about that")
                        ai_resp = conversation(query)
                        print(f"VEGA: {ai_resp}")
                        speak(ai_resp)
