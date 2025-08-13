# Curio Tracker

This tool allows you to quickly take a screenshot of the grand heist curio displays and save them as rewards data so that you can quickly analyze the kind of loot you found during your runs.

F5 - Captures the current layout (i.e layout: Prohibited Library, ilvl: 83), should always start with this when entering the Grand Heist as it will make every reward saved bound to that layout and ilvl.

F2 - Screen capture the entire screen, it will take a screenshot of the current screen, read the text on it and save the data in a .csv output, it reads duplicates (in the last 60 seconds) and doesn't save them in the file.

F4 - Provides you with a small snippet tool in case you like to manually take a screenshot of the item name/enchant and allows for duplicate values so if a wing had 2 or more of the same reward this is recommended.

F3 - Well every tool needs a way to exit it, so this is all it does, closes the tool.

### Example Usages of the tool:
<img width="1008" height="929" alt="image" src="https://github.com/user-attachments/assets/29c2f1b4-f185-4708-94b9-229a71b55de6" />

### Example using 0.1.5:
<img width="1104" height="655" alt="image" src="https://github.com/user-attachments/assets/8f0b766a-2ec3-49a3-9dd8-b98171fd88d5" />

It will save the data in a .csv file (saves/matches.csv) like the following (supported by google sheets, excel and so on)
<img width="1277" height="739" alt="image" src="https://github.com/user-attachments/assets/b06361f1-4ef5-4cdb-841c-e41cb623a158" />

Example import in google sheets:
<img width="1357" height="677" alt="image" src="https://github.com/user-attachments/assets/fe50a549-d2a0-4ee5-ac95-920426bfba2a" />


# SETUP (Quick)

Go to releases https://github.com/sokratis12GR/Curio-Tracker/releases, download the latest `.exe` file available alongside the `user_settings.ini` and replace as needed (Go to CONFIG SETUP)

# SETUP (Manual Python way - Step by Step)

## Download the ZIP of this repository
#### By clicking the green "<> Code" btn.
<img width="376" height="333" alt="image" src="https://github.com/user-attachments/assets/080c3f2e-2f20-4771-93fa-89688b696749" />

#### Or via the releases page download the 'Curio-Tracker-V#.#.#.zip' folder and extract it at an accessible location:

Once downloaded, continue follow the CONFIG SETUP steps.

# CONFIG SETUP `user_settings.ini`
Update the following entries

`poe_league = 3.26` to the current league

`poe_user = sokratis12GR` to the player that's running the blueprints

### Keybinds
If you dislike the current set of keys used, you can change them here just type in the key you want to use instead of the 'f2-5' keys
```
capture_key = f2
exit_key = f3
snippet_key = f4
layout_capture_key = f5
```

# Usage (.EXE)

Once config is setup, run the executable and enjoy recording data, the keybinds and everything will always be shown on launch, to reset the 5 wings separator could restart the tool.
Temporarily: For currencies the stack sizes is not always correctly captured, it may require an additional edit every so often.

# DEV/TESTING SETUP VIA PYTHON

## 1. Python 
This program runs on python, you will need to have it on your system, you can get it via the following ways:

### 1: Go to https://www.python.org/downloads/ and install latest

#### 1.1 **Important**: During installation
Check the box `"Add Python to PATH"`

#### 1.2 Python Libraries

To use the tool we will need to download some libraries, run the following command in cmd (make sure the prior step is followed):
> pip install keyboard pyautogui opencv-python numpy pytesseract pillow pygetwindow termcolor

## 2. Tesseract OCR
We will need the OCR to capture the screen and read the text from the captured image.

To download it use the following link: https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.0 and get the `.exe` file from "Assets", **install it inside a folder located inside the directory of this script called `tesseract` by itself**.

Once installed replace the following in the script with your installation path of Tesseract-OCR located in the `user_settings.init` file.

# DEBUGGING
By default the debugging of the tool is set to `False`, could be changed to `True` via a keybind `enable_debugging_key = ctrl+alt+d`
What it does it logs all characters found on screen into a file in /logs and then it also shows a popup of what was screencaptured at the moment alongside the keywords and so on.


# DEV/TESTING USAGE

To use simply open cmd via the location of the script by right clicking the folder and selecting the following option:
<img width="264" height="35" alt="image" src="https://github.com/user-attachments/assets/315ab833-0e31-4582-b218-74933a05d6a9" />
Afterwards just type `py curio_tracker.py`

Otherwise can use `py PATH/TO/CURIO/TRACKER/curio_tracker.py`

# Troubleshooting
In case the app crashes or has an error image, please do not hesitate to create an issue ticket at [Create Issue](https://github.com/sokratis12GR/Curio-Tracker/issues/new).
- Provide a screenshot, or a detailed explanation of the issue

***Appreciate any feedback ^^***



