# A library for text to speechh conversion
import pyttsx3
import datetime

engine = pyttsx3.init('sapi5')          # "init" - initialization of the engine, sapi5 - Microsofts built in speech engine

voices = engine.getProperty('voices')   # getting list of all voices available in our device which cam from Microsoft Speech API
#print(voices)

engine.setProperty('voice',voices[0].id) # selecting the voice for our AI from our system
print(voices[1].id)

# Function to speak
def speak(audio):
    engine.say(audio)
    engine.runAndWait()

def wish():
    hour = int(datetime.datetime.now().hour)
    if hour >= 0 and hour < 12:
        speak("Good Morning")
    elif hour >= 12 and hour < 18:
        speak("Good Afternoon")
    else:
        speak("Good Evening")


# main function
if __name__ == "__main__":
    speak("Lohith is a good boy")

