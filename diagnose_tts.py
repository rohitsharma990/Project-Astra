#!/usr/bin/env python3
"""
Diagnostic test for AI-TTS flow with typed input.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging

# Suppress verbose logs
logging.basicConfig(level=logging.INFO, format="%(name)s:%(levelname)s:%(message)s")
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("comtypes.client").setLevel(logging.WARNING)
logging.getLogger("comtypes._post_coinit").setLevel(logging.WARNING)

from app import speaker, ui

print("\n" + "="*70)
print("DIAGNOSTIC: AI-TTS FLOW TEST (Typed Input Simulation)")
print("="*70 + "\n")

# Test 1: Verify speaker is enabled
print("[TEST 1] Checking TTS state...")
print(f"  TTS enabled: {speaker.is_enabled()}")
if not speaker.is_enabled():
    print("  ERROR: TTS is disabled!")
    sys.exit(1)

# Test 2: Test direct speak
print("\n[TEST 2] Direct speak test...")
speaker.speak("Testing direct speak", block=True, force=True)
print("  [OK] Direct speak completed")

# Test 3: Simulate typed input flow
print("\n[TEST 3] Simulating typed input + AI response flow...")
print("  Simulating: Type 'What is Python?' -> parse_command -> AI response\n")

# Direct simulation of the typed input path
print("  1. User types: 'What is Python?'")

# Simulate what parser does
from app.ai import ask_ai

print("  2. Calling ask_ai('What is Python?')...")
try:
    ai_response = ask_ai("What is Python?")
    print(f"  3. AI Response received: {ai_response[:100]}...")

    replay = str(ai_response)
    print("  4. Calling speaker.speak(replay, block=True, force=True)...")
    speaker.speak(replay, block=True, force=True)
    print("\n[OK] AI-TTS flow completed successfully!")

except Exception as e:
    print(f"\n[ERROR] Exception during test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70 + "\n")
