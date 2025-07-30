# SETUP

## Download the ZIP of this repository by clicking the green "<> Code" btn:
<img width="376" height="333" alt="image" src="https://github.com/user-attachments/assets/080c3f2e-2f20-4771-93fa-89688b696749" />


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

Once installed replace the following in the script with your installation path of Tesseract-OCR located in the `config.py` file.

Open with a text editor and search for `tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"`:
> `tesseract_path = r"YOUR/PATH/TO/tesseract.exe"`

## CONFIG (TL;DR)
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
