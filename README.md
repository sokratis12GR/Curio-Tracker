# Curio Tracker

This tool allows you to quickly take a screenshot of the grand heist curio displays and save them as rewards data so that you can quickly analyze the kind of loot you found during your runs.

F5 - Captures the current layout (i.e layout: Prohibited Library, ilvl: 83), should always start with this when entering the Grand Heist as it will make every reward saved bound to that layout and ilvl.

F2 - Screen capture the entire screen, it will take a screenshot of the current screen, read the text on it and save the data in a .csv output, it reads duplicates (in the last 60 seconds) and doesn't save them in the file.

F4 - Provides you with a small snippet tool in case you like to manually take a screenshot of the item name/enchant and allows for duplicate values so if a wing had 2 or more of the same reward this is recommended.

F3 - Well every tool needs a way to exit it, so this is all it does, closes the tool.

Example Usages of the tool:
<img width="1008" height="929" alt="image" src="https://github.com/user-attachments/assets/29c2f1b4-f185-4708-94b9-229a71b55de6" />

It will save the data in a .csv file (saves/matches.csv) like the following (supported by google sheets, excel and so on)
<img width="1754" height="908" alt="image" src="https://github.com/user-attachments/assets/7dddb6e3-2cf8-4b3c-8af6-3f6dcb57014e" />

Example import in google sheets:
<img width="1882" height="815" alt="image" src="https://github.com/user-attachments/assets/bbdb43bf-6688-495a-af2c-2f9a173c4116" />


# SETUP

## Download the ZIP of this repository
#### By clicking the green "<> Code" btn.
<img width="376" height="333" alt="image" src="https://github.com/user-attachments/assets/080c3f2e-2f20-4771-93fa-89688b696749" />

#### Or via the releases page download the '.zip' folder and extract it at an accessible location:


Once downloaded, extract in a folder of preference, to continue follow the next steps.

## Python 
This program runs on python, you will need to have it on your system, you can get it via the following link: https://www.python.org/downloads/

**Important**: During installation, check the box `"Add Python to PATH"`

### Python Libraries

To use the tool we will need to download some libraries, run the following command in cmd (make sure the prior step is followed):
> pip install keyboard pyautogui opencv-python numpy pytesseract pillow pygetwindow termcolor

## Tesseract OCR
We will need the OCR to capture the screen and read the text from the captured image.

To download it use the following link: https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.0 and get the `.exe` file from "Assets", **install it inside a folder by itself**.

Once installed replace the following in the script with your installation path of Tesseract-OCR located in the `user_settings.py` file.

Open with a text editor and search for `tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"`:
> `tesseract_path = r"YOUR/PATH/TO/tesseract.exe"`

## CONFIG (TL;DR) `user_settings.py`
Update the following entries

`poe_league = "3.26"` to the current league

`poe_user = "sokratis12GR"` to the player that's running the blueprints

### Keybinds
If you dislike the current set of keys used, you can change them here just type in the key you want to use instead of the 'f2-5' keys
```
capture_key = "f2"
exit_key = "f3"
snippet_key = "f4"
layout_capture_key = "f5"
```

# DEBUGGING
By default the debugging of the tool is set to `False`, could be changed to `True` inside the config.py file.
What it does it logs all characters found on screen into a file in /logs and then it also shows a popup of what was screencaptured at the moment alongside the keywords and so on.

# Usage

To use simply open cmd via the location of the script by right clicking the folder and selecting the following option:
<img width="264" height="35" alt="image" src="https://github.com/user-attachments/assets/315ab833-0e31-4582-b218-74933a05d6a9" />

Afterwards just type `py curio_tracker.py`

Otherwise can use `py PATH/TO/CURIO/TRACKER/curio_tracker.py`

# Appreciate any feedback ^^
