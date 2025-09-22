# Curio Tracker

This tool allows you to quickly take a screenshot of the grand heist curio displays and save them as rewards data so
that you can quickly analyze the kind of loot you found during your runs.

F5 - Captures the current layout (i.e layout: Prohibited Library, ilvl: 83), should always start with this when entering
the Grand Heist as it will make every reward saved bound to that layout and ilvl.

F2 - Screen capture the entire screen, it will take a screenshot of the current screen, read the text on it and save the
data in a .csv output, it reads duplicates (in the last 60 seconds) and doesn't save them in the file.

F4 - Provides you with a small snippet tool in case you like to manually take a screenshot of the item name/enchant and
allows for duplicate values so if a wing had 2 or more of the same reward this is recommended.

F3 - Well every tool needs a way to exit it, so this is all it does, closes the tool.

### Example Usages of the tool:

<img width="1919" height="1024" alt="image" src="https://github.com/user-attachments/assets/c6d1ff86-6313-4a88-a5c0-97adc2509689" />

## Toasts when capturing a curio that showcase the captured item(s) in the top right of the screen:

<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/343496ad-6b80-4e1d-b11d-80cfa1b08a9a" />
<img width="1919" height="1079" alt="image" src="https://github.com/user-attachments/assets/ce8faa22-eb30-4c74-8be2-b63939fcd878" />

## Sorting

<img width="1918" height="1030" alt="image" src="https://github.com/user-attachments/assets/68bb3ee9-4a90-406b-8484-fb7c7fe7dcce" />

It will save the data in a `.csv` file (`saves/matches.csv`) like the following (supported by google sheets, excel and
so on)
<img width="1263" height="713" alt="image" src="https://github.com/user-attachments/assets/04e8fd60-4c86-4b40-9ddb-c4471e1fb97e" />

Example `matches.csv` output:
<img width="1284" height="766" alt="image" src="https://github.com/user-attachments/assets/5447ab65-7bad-47e1-a058-d5afb381f2b1" />

## Light Mode

<img width="1918" height="1029" alt="image" src="https://github.com/user-attachments/assets/a7107fe2-f117-4967-a3c0-f3bd9d2d5cfb" />

# Extras

- Real-time data correction:
    - Allows deletion of entries via the tree view, just select the item and press the delete btn.
    - Allows correcting stack size in case an incorrect value was captured via the UI, it saves automatically and
      updates the estimated value.
- Economy Support (Estimated Value) - Pulls from poe.ninja the item's estimated value
- Support for older data sets, automatically converts the old matches.csv versions into an up-to-date supported version.

# SETUP (Quick)

Go to releases https://github.com/sokratis12GR/Curio-Tracker/releases, download the latest `Heist Curio Tracker.exe`

# Video on how to use:

https://youtu.be/BW5GyrDTVss

# Troubleshooting

In case the app crashes or has an error image, please do not hesitate to create an issue ticket
at [Create Issue](https://github.com/sokratis12GR/Curio-Tracker/issues/new).

- Provide a screenshot, or a detailed explanation of the issue

***Appreciate any feedback ^^***







