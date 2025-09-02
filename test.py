import datetime
import time
import win32com.client

# Method 1: Try Windows SAPI directly
try:
    import win32com.client
    
    def speak(audio):
        print(f"🗣️ Speaking: {audio}")
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(audio)
        print("✅ Speech completed")
    
    print("✅ Using Windows SAPI (win32com)")
    
except ImportError:
    print("⚠️ win32com not available, install with: pip install pywin32")
    
    # Fallback: Try subprocess with Windows built-in speech
    import subprocess
    import os
    
    def speak(audio):
        print(f"🗣️ Speaking: {audio}")
        try:
            # Use Windows built-in speech via PowerShell
            command = f'powershell -Command "Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Speak(\'{audio}\')"'
            subprocess.run(command, shell=True, check=True)
            print("✅ Speech completed")
        except Exception as e:
            print(f"❌ PowerShell speech failed: {e}")
            # Last resort: Print only
            print(f"📢 WOULD SAY: {audio}")

def wish():
    hour = int(datetime.datetime.now().hour)
    
    if hour >= 0 and hour < 12:
        speak("Good Morning")
    elif hour >= 12 and hour < 18:
        speak("Good Afternoon")
    else:
        speak("Good Evening")
    
    time.sleep(0.5)  # Short pause
    speak("Sir, How may I help you today!")

def test_multiple():
    """Test multiple speeches"""
    speeches = [
        "This is test number one",
        "This is test number two", 
        "This is test number three",
        "All tests completed"
    ]
    
    for i, speech in enumerate(speeches, 1):
        print(f"\n--- Test {i} ---")
        speak(speech)
        time.sleep(0.5)  # Pause between speeches

if __name__ == "__main__":
    print("🚀 Testing Windows SAPI method...")
    test_multiple()
    print("\n🚀 Running wish function...")
    wish()