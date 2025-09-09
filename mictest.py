import speech_recognition as sr

r = sr.Recognizer()

try:
    with sr.Microphone() as source:
        print("Calibrating... Please be quiet for a moment.")
        r.adjust_for_ambient_noise(source, duration=2)
        print("Calibration complete. Say something!")
        
        audio = r.listen(source, timeout=10)
        
        # Save the audio to a file
        with open("my_audio.wav", "wb") as f:
            f.write(audio.get_wav_data())
        print("Audio saved to my_audio.wav. Please listen to it.")

        print("Now recognizing...")
        text = r.recognize_google(audio)
        print(f"I heard you say: '{text}'")

except Exception as e:
    print(f"An error occurred: {e}")