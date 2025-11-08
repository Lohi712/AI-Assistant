# =============================================================================
# --- 1. IMPORTS ---
# =============================================================================
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
import smtplib
import google.generativeai as genai
import pvporcupine
import pyaudio
import struct
from ddgs import DDGS
import re
import threading # <-- Added for interruptible speech

# =============================================================================
# --- 2. GLOBAL VARIABLES & SHARED INSTANCES ---
# =============================================================================
# We create one recognizer and microphone instance to share
try:
    r = sr.Recognizer()
    m = sr.Microphone()
except Exception as e:
    print(f"Error initializing microphone: {e}")
    print("Please make sure you have a microphone connected.")
    exit()

# This Event will signal the speak function to stop
stop_speaking_flag = threading.Event()

# Create one speaker instance to share
try:
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
except Exception as e:
    print(f"Error initializing Windows SAPI5 voice: {e}")
    print("Could not connect to Windows speech. Make sure it's enabled.")
    # Create a dummy speak function to avoid crashing
    def speak(audio):
        print(f"[DUMMY SPEAK]: {audio}")
    
# =============================================================================
# --- 3. CORE FUNCTIONS (SPEAK, LISTEN, WAKE, CONVERSE) ---
# =============================================================================

def listen_for_interrupt():
    """
    Runs in a background thread to listen for a "stop" command.
    If "stop" is heard, it sets the global stop_speaking_flag.
    """
    global r, m, stop_speaking_flag
    try:
        # Use the global microphone instance
        with m as source:
            # Listen for a single word with a very short timeout
            audio = r.listen(source, timeout=0.5, phrase_time_limit=1)
        
        # Recognize the word
        word = r.recognize_google(audio, language='en-in').lower()
        
        if "stop" in word or "shut up" in word:
            print("\n[Interrupt command heard! Stopping speech.]")
            stop_speaking_flag.set() # Set the flag to signal the speak function
            
    except sr.UnknownValueError:
        pass # This is normal, means no speech was heard
    except sr.WaitTimeoutError:
        pass # This is normal, means no speech was heard
    except Exception as e:
        # Silently fail if there's an error during the interrupt check
        pass

def speak(audio):
    """
    Speaks the audio asynchronously and listens for a "stop" interrupt.
    """
    global speaker, stop_speaking_flag
    
    try:
        # Clear the flag at the start of new speech
        stop_speaking_flag.clear()
        
        # Start the speech asynchronously (SVSFlagsAsync = 1)
        speaker.Speak(audio, 1) 

        # Loop to check for interrupt
        # We'll check for the flag while the speaker's status is "running" (status=1)
        while speaker.Status.RunningState == 1:
            # Start a short-lived thread to listen for "stop"
            interrupt_thread = threading.Thread(target=listen_for_interrupt)
            interrupt_thread.daemon = True
            interrupt_thread.start()
            
            # Wait for the interrupt thread to finish (max 0.5s)
            interrupt_thread.join(0.5) 
            
            # Check if the flag was set by the interrupt thread
            if stop_speaking_flag.is_set():
                # If interrupted, stop the speech
                # 19 = SVSFPurgeBeforeSpeak + SVSFlagsAsync
                speaker.Speak("", 19) 
                print("[Speech stopped by user]")
                break
                
        # Clear the flag again after speech is done or stopped
        stop_speaking_flag.clear()
    except Exception as e:
        print(f"Error in speak function: {e}")
        stop_speaking_flag.clear()

def wake_up():
    """
    Listens silently in the background until a wake word is detected.
    """
    # 1. Get your Access Key from the environment variable
    PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY") 
    
    # 2. Make sure this filename is spelled exactly right
    keyword_path = 'Hey-Vega_en_windows_v3_0_0.ppn' 

    # --- Safety Checks ---
    if not PICOVOICE_ACCESS_KEY:
        print("CRITICAL ERROR: PICOVOICE_ACCESS_KEY environment variable not set.")
        return False
    if not os.path.exists(keyword_path):
        print(f"CRITICAL ERROR: Wake word file '{keyword_path}' not found.")
        print("Please make sure the .ppn file is in the same folder as the script.")
        return False
    # ---------------------

    try:
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            # 3. Use 'keyword_paths' (with an 's') and [brackets]
            keyword_paths=[keyword_path]
        )
        
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )
        
        print("Listening for wake word 'Hey VEGA'...")

        while True:
            # Check if the "stop speaking" flag is set (e.g., by another part of the app)
            # This prevents the wake word from being detected while speaking
            if stop_speaking_flag.is_set():
                time.sleep(0.1)
                continue

            pcm = audio_stream.read(porcupine.frame_length)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm) 

            keyword_index = porcupine.process(pcm)

            if keyword_index >= 0:
                print(f"Wake word detected!")
                audio_stream.close()
                pa.terminate()
                porcupine.delete()
                return True # Signal that the wake word was heard

    except Exception as e:
        print(f"Error in wake up function: {e}")
        return False

def cmd_format(text):
    """Formats the AI response, removing markdown."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # remove bold
    text = re.sub(r'\* ', '- ', text)            # convert bullet
    return text

def wish():
    """Greets the user based on the time of day."""
    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak("Good Morning Sir!!")
    elif hour >= 12 and hour < 18:
        speak("Good Afternoon Sir!!")
    else:
        speak("Good Evening Sir!!")
    speak("This is VEGA, your Virtual Enhanced General Assistant. How may I help you today!")

def conversation(query):
    """Sends a query to the Gemini model and gets a conversational response."""
    conv_api = os.getenv("GOOGLE_AI_API_KEY")
    
    if not conv_api:
        print("CRITICAL ERROR: GOOGLE_AI_API_KEY environment variable not found.")
        return "Sorry, my brain is not configured. The API key is missing."

    try:
        genai.configure(api_key=conv_api)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(query)
        r = cmd_format(response.text)
        return r
    except Exception as e:
        print(f"AI Error: {e}")
        return "Sorry, my brain is not working right now."

def listen():
    """
    Listens for a user command using the global recognizer.
    """
    global r, m # Use the global instances
    
    # Check if the user is trying to interrupt
    if stop_speaking_flag.is_set():
        return "None" # Don't listen for a command if user just said "stop"
        
    with m as source:
        print("Listening...")
        # Note: We are NOT adjusting for ambient noise here
        # We do it once at the very start of the script
        r.pause_threshold = 1
        audio = None
        
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            print("Listen timeout.")
            return "None" 

    try:
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}")
        return query
    except sr.UnknownValueError:
        print("Say that again please...")
        return "None"
    except Exception as e:
        print(f"Recognition error: {e}")
        return "None"

def mail(to, subject, body):
    """Sends an email using your Gmail account."""
    gmail_user = 'quantmech19@gmail.com'
    gmail_psw = os.getenv('GMAIL_APP_PASSWORD')
    if not gmail_psw:
        print("CRITICAL ERROR: The GMAIL_APP_PASSWORD environment variable was not found.")
        speak("I could not find the password environment variable. Please set it in the terminal before running the script.")
        return False
    try:
        message = f"Subject: {subject}\n\n{body}"
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(gmail_user, gmail_psw)
        server.sendmail(gmail_user, to, message)
        server.close()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# =============================================================================
# --- 4. MAIN EXECUTION LOOP ---
# =============================================================================
if __name__ == "__main__": 
    
    # --- ONE-TIME CALIBRATION ---
    print("Calibrating microphone for ambient noise... Please be quiet for a moment.")
    with m as source:
        r.adjust_for_ambient_noise(source, duration=2)
    print("Calibration complete.")
    # -------------------------------------

    while True:
        # 1. Run the low-power wake word detection
        if wake_up():
            
            # 2. Once woken up, greet the user
            wish()
            print(f"Currently using google-generativeai version: {genai.__version__}")
            
            # 3. This is your ORIGINAL main command loop
            while True:
                query = listen().lower()

                if 'wikipedia' in query:
                    speak("Searching Wikipedia...")
                    
                    # More robust stop-word list
                    stop_words = [
                        'search', 'for', 'the', 'country', 'in', 'item', 'on', 'wikipedia', 
                        'about', 'tell', 'me', 'who', 'is', 'what', 'an'
                        # We removed 'a' because it breaks words like 'avengers'
                    ]
                    
                    query_words = query.split()
                    
                    clean_words = []
                    for word in query_words:
                        if word not in stop_words:
                            clean_words.append(word)
                    
                    clean_query = " ".join(clean_words)
                    print(f"Cleaned Wikipedia query is: '{clean_query}'")
                    
                    if not clean_query:
                        speak("I can hear you saying Wikipedia but I couldn't get the topic. Please try again.")
                        continue

                    speak(f"Looking up {clean_query} on Wikipedia.")
                    
                    try:
                        # Use auto_suggest=True to fix misspellings
                        Wikiresults = wikipedia.summary(clean_query, sentences=2, auto_suggest=True)
                        
                        speak("According to Wikipedia..")
                        print(Wikiresults)
                        speak(Wikiresults)
                    
                    except wikipedia.exceptions.DisambiguationError as e:
                        speak(f"Your search for '{clean_query}' is ambiguous. It could refer to many things.")
                        print(f"Disambiguation Error: '{clean_query}' may refer to: ")
                        print(e.options)
                        speak("Please be more specific.")
                    
                    except wikipedia.exceptions.PageError:
                        speak(f"Sorry, I couldn't find a Wikipedia page for '{clean_query}'.")
                    
                    except Exception as e:
                        speak("Sorry, some error occurred while searching in Wikipedia.")
                        print(f"Wikipedia error: {e}")

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
                    search_term = query.replace('search', '').strip()
                    if not search_term:
                        speak("What would you like to search for?")
                        continue

                    speak(f"Searching for {search_term} and summarizing.")

                    try:
                        with DDGS() as ddgs:
                            search_results = list(ddgs.text(search_term, max_results=1))
                        
                        if not search_results:
                            speak("Sorry, I could not find any results for that search.")
                            continue

                        first_result = search_results[0]
                        page_title = first_result['title']
                        summary = first_result['body']
                        first_url = first_result['href']

                        speak(f"The first result is titled: {page_title}")
                        speak("Here is a summary:")
                        print(summary)
                        speak(summary)

                        speak("Opening the page for you now.")
                        webbrowser.open(first_url)

                    except Exception as e:
                        speak("Sorry, I encountered an error while searching.")
                        print(f"Search error: {e}")

                elif 'weather' in query:
                    api_key = '1f5fb087e340634614cedb20e0715ace' # Note: Be careful hardcoding keys!
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
                            speak("Sorry, I couldn't fetch the weather details")
                    else:
                        speak("I didn't catch the city name")

                elif 'news' in query or 'headlines' in query:
                    gnews_api_key = "e75c19434bd1fb1a928ff34b38378099" # Note: Be careful hardcoding keys!
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
                    recipient_name = input("Enter the recipient name: ")
                    
                    speak(f"Got it. What message do wanna send to {recipient_name}")
                    message = listen() # Changed this back to listen()

                    while message == "None":
                        speak("Sorry, I didn't catch the message. Say it again")
                        message = listen()

                    speak(f"Preparing to send the message to {recipient_name}")

                    try:
                        pyautogui.press('win')
                        time.sleep(1)
                        pyautogui.write('Whatsapp')
                        time.sleep(1)
                        pyautogui.press('enter')
                        time.sleep(10) # Wait for app to load
                        
                        pyautogui.hotkey('ctrl','f')
                        time.sleep(1)
                        pyautogui.write(recipient_name)
                        time.sleep(2)
                        pyautogui.press('enter')
                        time.sleep(3) # Wait for chat to load
                        
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
                    speak("Who is the recipient? Please type their email address")
                    recipient_email = input("Enter recipient's email: ")
                    
                    subject = "None"
                    while subject == "None":
                        speak("What is the subject of the email?")
                        subject = listen()
                        if subject == "None":
                            speak("I didn't catch the subject, please try again.")
                            
                    body = "None"
                    while body == "None":
                        speak("Now lets say the body of your email")
                        body = listen()
                        if body == "None":
                            speak("Sorry I didn't get the body, please try again.")

                    speak("Authenticating and sending email...")
                    if mail(recipient_email,subject,body):
                        speak("email has been sent")
                    else:
                        speak("Sorry email couldn't be sent")

                elif 'go to sleep' in query or 'bye' in query or 'exit' in query:
                    speak("GoodBye Sir. Going to sleep.")
                    break # This exits the INNER loop

                else:
                    if query and query != "none":
                        speak("Let me think about that")
                        ai_resp = conversation(query)
                        print(f"VEGA: {ai_resp}")
                        speak(ai_resp)

        else:
            speak("Wake word engine failed. Please check the console.")
            break # Exit the outer loop if wake_up fails