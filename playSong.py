import pyMIDI
import threading
import random
from pynput.keyboard import Key, Controller, Listener
import time

global isPlaying
global infoTuple
global storedIndex
global playback_speed
global elapsedTime
global origionalPlaybackSpeed
global speedMultiplier
global legitModeActive
global heldNotes

isPlaying = False
legitModeActive = False

storedIndex = 0
elapsedTime = 0
origionalPlaybackSpeed = 1.0
speedMultiplier = 2.0
heldNotes = {}

conversionCases = {'!': '1', '@': '2', '£': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0'}

keyboardController = Controller()

key_delete = 'delete'
key_shift = 'shift'
key_end = 'end'
key_home = 'home'
key_load = 'f5'
key_speed_up = 'page_up'
key_slow_down = 'page_down'
key_legit_mode = 'insert'

def runPyMIDI():
    try:
        pyMIDI.main()
    except Exception as e:
        print(f"pyMIDI.py crashed or had a bad day: {e}\nTry checking your MIDI file or restarting the script.")

def toggleLegitMode(event):
    global legitModeActive
    legitModeActive = not legitModeActive
    status = "ON" if legitModeActive else "OFF"
    print(f"Legit Mode turned {status}")

def calculateTotalDuration(notes):
    total_duration = sum([note[0] for note in notes])
    return total_duration

def onDelPress():
    global isPlaying
    isPlaying = not isPlaying

    if isPlaying:
        print("Playing...")
        playNextNote()
    else:
        print("Stopping...")

def isShifted(charIn):
    asciiValue = ord(charIn)
    if asciiValue >= 65 and asciiValue <= 90:
        return True
    if charIn in "!@#$%^&*()_+{}|:\"<>?":
        return True
    return False

def speedUp(event):
    global playback_speed
    playback_speed *= speedMultiplier
    print(f"Speeding up: Playback speed is now {playback_speed:.2f}x")

def slowDown(event):
    global playback_speed
    playback_speed /= speedMultiplier
    print(f"Slowing down: Playback speed is now {playback_speed:.2f}x")

def pressLetter(strLetter):
    if isShifted(strLetter):
        if strLetter in conversionCases:
            strLetter = conversionCases[strLetter]
        keyboardController.release(strLetter.lower())
        keyboardController.press(Key.shift)
        keyboardController.press(strLetter.lower())
        keyboardController.release(Key.shift)
    else:
        keyboardController.release(strLetter)
        keyboardController.press(strLetter)
    return
    
def releaseLetter(strLetter):
    if isShifted(strLetter):
        if strLetter in conversionCases:
            strLetter = conversionCases[strLetter]
        keyboardController.release(strLetter.lower())
    else:
        keyboardController.release(strLetter)
    return
    
def processFile():
    global playback_speed
    try:
        with open("song.txt", "r") as macro_file:
            lines = macro_file.read().split("\n")
    except Exception as e:
        print("Couldn't open song.txt. Did you forget to put your masterpiece in the folder?\nError:", e)
        return None
    tOffsetSet = False
    tOffset = 0

    if len(lines) > 0 and "=" in lines[0]:
        try:
            playback_speed = float(lines[0].split("=")[1])
            print(f"Playback speed is set to {playback_speed:.2f}x. Fasten your seatbelt!")
        except ValueError:
            print("Oops! The playback speed in song.txt is not a number. Please fix it and try again.")
            return None
    else:
        print("First line of song.txt should look like playback_speed=1.0. Please check your file!")
        return None

    tempo = None
    processedNotes = []
    for line in lines[1:]:
        if 'tempo' in line:
            try:
                tempo = 60 / float(line.split("=")[1])
            except ValueError:
                print("Tempo value is weird. Please make sure it's a number. Example: tempo=120")
                return None
        else:
            l = line.split(" ")
            if len(l) < 2:
                continue
            try:
                waitToPress = float(l[0])
                notes = l[1]
                processedNotes.append([waitToPress, notes])
                if not tOffsetSet:
                    tOffset = waitToPress
                    tOffsetSet = True
            except ValueError:
                print(f"Note line '{line}' is not valid. Skipping this one. (Did you drop your coffee on the file?)")
                continue

    if tempo is None:
        print("No tempo found! Please add a line like 'tempo=120' in your song.txt.")
        return None

    return [tempo, tOffset, processedNotes, []]

def floorToZero(i):
    if i > 0:
        return i
    else:
        return 0

# for this method, we instead use delays as l[0] and work using indexes with delays instead of time
# we'll use recursion and threading to press keys
def parseInfo():
    if infoTuple is None or not isinstance(infoTuple[2], list) or not infoTuple[2]:
        print("No notes to parse. Maybe your song.txt is empty?")
        return []
    notes_raw = infoTuple[2] if isinstance(infoTuple[2], list) else []
    if not notes_raw:
        notes = []
    else:
        notes = notes_raw[1:] if len(notes_raw) > 1 else []
    tempo = infoTuple[0]
    i = 0
    while i < len(notes) - 1:
        note = notes[i]
        nextNote = notes[i + 1]
        if "tempo" in note[1]:
            tempo = 60 / float(note[1].split("=")[1])
            notes.pop(i)
            note = notes[i]
            if i < len(notes) - 1:
                nextNote = notes[i + 1]
        else:
            note[0] = (nextNote[0] - note[0]) * tempo
            i += 1
    if notes:
        notes[len(notes) - 1][0] = 1.00
    return notes

def adjustTempoForCurrentNote():
    global isPlaying, storedIndex, playback_speed, elapsedTime, legitModeActive
    if len(infoTuple) > 3:
        tempo_changes = infoTuple[3]

        for change in tempo_changes:
            if change[0] == storedIndex:
                new_tempo = change[1]
                playback_speed = new_tempo / origionalPlaybackSpeed
                print(f"Tempo changed: New playback speed is {playback_speed:.2f}x")

def playNextNote():
    global isPlaying, storedIndex, playback_speed, elapsedTime, legitModeActive, heldNotes
    if infoTuple is None or not isinstance(infoTuple[2], list) or not infoTuple[2]:
        print("Nothing to play. Did you forget to load a song?")
        return

    adjustTempoForCurrentNote()
    
    notes = infoTuple[2] if isinstance(infoTuple[2], list) else []
    if not isinstance(notes, list):
        notes = []
    total_duration = calculateTotalDuration(notes)

    # Track last error to avoid two in a row
    if not hasattr(playNextNote, "last_error"): playNextNote.last_error = False

    if not notes:
        isPlaying = False
        storedIndex = 0
        elapsedTime = 0
        return

    if isPlaying and storedIndex < len(notes):
        noteInfo = notes[storedIndex]
        delay = floorToZero(noteInfo[0])
        note_keys = noteInfo[1]

        if legitModeActive:
            # Micro humanization: randomize delay ±30ms, but do not slow down fast passages
            delay += random.uniform(-0.03, 0.03)
            # Sometimes (1/20) add a slight accent (simulate forte)
            accent = random.random() < 0.05
            # Smooth dynamic: sometimes a bit softer/louder (simulate crescendo/diminuendo)
            dynamic = 1.0 + random.uniform(-0.12, 0.12)
            # For chords: randomize spread between notes up to 12ms
            chord_spread = random.uniform(0.004, 0.012) if len(note_keys) > 1 else 0
            # Legato/staccato: sometimes hold a bit longer/shorter
            style_rand = random.random()
            if style_rand < 0.15 or (legitModeActive and random.randint(1, 100) == 1):
                # Sometimes (1/100) make legato imperfect
                hold_time = max(noteInfo[0] * random.uniform(0.80, 1.20), 0.04) / playback_speed
            else:
                hold_time = noteInfo[0] / playback_speed
            # Dirty pedal: sometimes delay release (1/120)
            pedal_delay = random.uniform(0.01, 0.04) if random.randint(1, 120) == 1 else 0
            # Rarely (1/400) play a short wrong note (only for single notes, not in fast passages, not after error)
            can_error = (
                len(note_keys) == 1 and
                delay > 0.09 and
                not playNextNote.last_error
            )
            if can_error and random.randint(1, 400) == 1:
                wrong_note = random.choice([n for n in 'qwertyuiopasdfghjklzxcvbnm1234567890' if n != note_keys])
                pressLetter(wrong_note)
                time.sleep(0.03)
                releaseLetter(wrong_note)
                playNextNote.last_error = True
            else:
                playNextNote.last_error = False
        else:
            accent = False
            dynamic = 1.0
            chord_spread = 0
            hold_time = noteInfo[0] / playback_speed
            pedal_delay = 0
            playNextNote.last_error = False

        elapsedTime += max(delay, 0)

        # Key press/release logic
        if "~" in note_keys:
            for n in note_keys.replace("~", ""):
                releaseLetter(n)
                if n in heldNotes:
                    del heldNotes[n]
        else:
            if legitModeActive and len(note_keys) > 1:
                for i, n in enumerate(note_keys):
                    pressLetter(n)
                    heldNotes[n] = noteInfo[0]
                    if i < len(note_keys) - 1:
                        time.sleep(chord_spread)
            else:
                for n in note_keys:
                    pressLetter(n)
                    heldNotes[n] = noteInfo[0]
            # Account for dirty pedal
            threading.Timer(hold_time + pedal_delay, releaseHeldNotes, [note_keys]).start()

        if "~" not in note_keys:
            elapsed_mins, elapsed_secs = divmod(elapsedTime, 60)
            total_mins, total_secs = divmod(total_duration, 60)
            print(f"[{int(elapsed_mins)}m {int(elapsed_secs)}s/{int(total_mins)}m {int(total_secs)}s] {note_keys}")

        storedIndex += 1
        if delay <= 0:
            playNextNote()
        else:
            threading.Timer(delay / playback_speed, playNextNote).start()
    elif storedIndex >= len(notes):
        isPlaying = False
        storedIndex = 0
        elapsedTime = 0

def releaseHeldNotes(note_keys):
    global heldNotes
    for n in note_keys:
        if n in heldNotes:
            releaseLetter(n)
            if n in heldNotes:
                del heldNotes[n]

def rewind(KeyboardEvent):
    global storedIndex
    if storedIndex - 10 < 0:
        storedIndex = 0
    else:
        storedIndex -= 10
    print("Rewound to %.2f" % storedIndex)

def skip(KeyboardEvent):
    global storedIndex
    if storedIndex + 10 > len(infoTuple[2]):
        isPlaying = False
        storedIndex = 0
    else:
        storedIndex += 10
    print("Skipped to %.2f" % storedIndex)

def onKeyPress(key):
    global isPlaying, storedIndex, playback_speed, legitModeActive
    try:
        if key == Key.delete:
            onDelPress()
        elif key == Key.home:
            rewind(None)
        elif key == Key.end:
            skip(None)
        elif key == Key.page_up:
            speedUp(None)
        elif key == Key.page_down:
            slowDown(None)
        elif key == Key.insert:
            toggleLegitMode(None)
        elif key == Key.f5:
            runPyMIDI()
        elif key == Key.esc:
            # Instead of returning False, just stop the listener
            return None
    except AttributeError:
        print("Somehow you pressed a key that doesn't exist. Impressive!")
        pass

def printControls():
    title = "Controls"
    controls = [
        ("DELETE", "Play/Pause"),
        ("HOME", "Rewind"),
        ("END", "Advance"),
        ("PAGE UP", "Speed Up"),
        ("PAGE DOWN", "Slow Down"),
        ("INSERT", "Toggle Legit Mode"),
        ("F5", "Load New Song (NOT RECOMMENDED)"),
        ("ESC", "Exit")
    ]

    print(f"\n{'=' * 20}\n{title.center(20)}\n{'=' * 20}")

    for key, action in controls:
        print(f"{key.ljust(10)} : {action}")

    print(f"{'=' * 20}\n")

def simplify_notes(notes):
    simplified = []
    # Calculate average chord size. If it's not a monster, don't touch it.
    avg_notes = sum(len(n[1]) for n in notes if '~' not in n[1]) / max(1, len([n for n in notes if '~' not in n[1]]))
    if avg_notes <= 3.2:
        return notes  # Not a Beethoven piece, skip jazz magic
    for i, (delay, note_keys) in enumerate(notes):
        # If the chord is a hand-breaker (4+ notes), let's pretend we have only 10 fingers
        if len(note_keys) > 4 and '~' not in note_keys:
            keep = random.sample(list(note_keys), random.randint(2, 4))
            note_keys = ''.join(keep)
        # Sometimes break big chords into arpeggios. Because we're not robots. (Or are we?)
        if len(note_keys) > 3 and random.random() < 0.18 and '~' not in note_keys:
            for j, n in enumerate(note_keys):
                arp_delay = delay if j == 0 else random.uniform(0.04, 0.13)  # Human fingers are not MIDI cables
                simplified.append([arp_delay, n])
            continue
        # If notes are coming at you like bullets, sometimes just... don't play one. Human error, right?
        if i > 0 and delay < 0.09 and random.random() < 0.15:
            continue
        # Sometimes simplify a chord to just an interval. Because less is more (and easier).
        if len(note_keys) > 2 and random.random() < 0.10 and '~' not in note_keys:
            keep = random.sample(list(note_keys), 2)
            note_keys = ''.join(keep)
        simplified.append([delay, note_keys])
    return simplified

def main():
    global isPlaying, infoTuple, playback_speed

    infoTuple = processFile()
    if infoTuple is None or not isinstance(infoTuple[2], list) or not infoTuple[2]:
        print("Can't start: song file is missing or broken. Time to check your song.txt!")
        return

    if not isinstance(infoTuple[2], list):
        infoTuple[2] = []
    infoTuple[2] = parseInfo() if infoTuple[2] else []
    # Only simplify if notes are present
    if infoTuple[2]:
        infoTuple[2] = simplify_notes(infoTuple[2])
    else:
        print("No notes to play. Your song is suspiciously quiet...")
        return

    printControls()

    with Listener(on_press=onKeyPress) as listener:
        listener.join()
            
if __name__ == "__main__":
    main()
