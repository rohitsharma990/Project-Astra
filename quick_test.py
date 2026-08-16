#!/usr/bin/env python3
"""Quick test to see if AI response flow works"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Suppress comtypes logs
import logging
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("comtypes.client").setLevel(logging.WARNING)
logging.getLogger("comtypes._post_coinit").setLevel(logging.WARNING)

from app import speaker, ui

print("\n[1] Testing simple TTS speak...")
speaker.speak("Hello Test", block=True, force=True)
print("[OK] Simple TTS works\n")

print("[2] Testing AI response display + speak flow...")
print("  Simulating: ask_ai returns response -> ui.assistant_message -> speak")

# Simulate what happens
test_response = "This is a test response from the AI"
print(f"  Response text: '{test_response}'")

print("  Calling ui.assistant_message (will print and call speak)...")
ui.assistant_message(test_response, speak_force=True)

print("[OK] AI response flow works!")
print("\nNow try with real AI by running: python -c \"from app.parser import parse_command; parse_command('What is Python')\"")
