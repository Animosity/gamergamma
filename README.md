# gamergamma
## Developed with colorblind gamers in mind. 
This tool provides user-configurable hotkeys to adjust the hardware (monitor) gamma and 
NVIDIA color/digital vibrance settings dynamically in any application. 

EXTERNAL DEPENDENCIES: [`ddcutil` (for monitor/hardware gamma control)](https://github.com/rockowitz/ddcutil), [`nvibrant-bin` (NVIDIA-only)](https://github.com/Tremeschin/nvibrant)

**How to use:**
1. Install external dependencies:
   -  [`ddcutil` (for monitor/hardware gamma control)](https://github.com/rockowitz/ddcutil)
   -  [`nvibrant-bin` (NVIDIA-only)](https://github.com/Tremeschin/nvibrant)

2. Install python dependencies in your environment of choice (`pip install -r requirements.txt`)
3. Run: `python3 gamergamma.py` (or, use the compiled binary from the [Releases](https://github.com/Animosity/gamergamma/releases))

4. Select your primary gaming display/monitor from the dropdown. 
5. Adjust the gamma and/or vibrance sliders to your preference, and select Apply to test it.
6. Select Save Preset to write the settings to local file (gg_presets.json)
7. Click the Preset # (<HotKey>) title to reconfigure the preset's hotkey to your choice.
8. Use your hotkeys in any game/app of your choice.

![](https://private-user-images.githubusercontent.com/105494/530158312-52ee5ebc-fd68-4723-852e-b1b2dbdc751e.gif?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3NjY2NDY1NzksIm5iZiI6MTc2NjY0NjI3OSwicGF0aCI6Ii8xMDU0OTQvNTMwMTU4MzEyLTUyZWU1ZWJjLWZkNjgtNDcyMy04NTJlLWIxYjJkYmRjNzUxZS5naWY_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUxMjI1JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MTIyNVQwNzA0MzlaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT02MGZjYTZhZThkOGFkODAwNGQ2NDMwNWJkYWYxNGM5YjU4MGFjYTc4ODM0OGZmODZjYTM0MmI1MGVkMjZkYWJmJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.M_GATETZv7_teyyS6MKhaWnKKFlwwbgwBnvDt2s3OT8)

NOTES:
- Releases are lazily packaged using `pyinstaller --onefile`
- Developer test environment is LIMITED. Proven on CachyOS with KDE Plasma/Wayland,
  using applications launched via proton (e.g. Steam games), including using gamescope in 
  Steam game launch parameters.



DEVELOPERS/DEBUGGING:  
- The apply_presets() function is vital and is where compatibilty will absolutely break.
Your pull requests are equally vital to universal support.

- This function only supports monitors implementing MCCS (Monitor Control
Command Set) over I2C, and therefore can be controlled via ddcutil.

- The purpose of this function (and application) is to dynamically adjust the
hardware gamma configuration (only using command 0x72 - Gamma) of the
primary gaming monitor. Additionally, it is to adjust the digital vibrance
dynamically for the color-challenged users.

Problems:
* Destructive settings - Does not store original monitor configuration
* nvibrant parameters are structured for the formatted output of (`nvibrant`)
  using a singular GPU RTX30XX-series presence with one HDMI and 3 DP outputs.
* ddcutil 0x72 value packing is tailored to Dell S2716DG (see Notes)
* *FIXED 24DEC2025* -- NVIBRANT call doesn't use Monitor index (always #2)
* NVIDIA-only support for vibrance control

Development reference:
- `Dell S2716DG` only uses the MSByte of the gamma value. 
- Writing LSByte != 0x00 can cause CRC Verify errors.
- The scheme of only writing MSByte has not been
tested on other monitors.

Output of nvibrant ("Normal output" upon which its usage is based):
    
    ❯ nvibrant
            Driver version: (580.105.08)

            Display 0:
            • (0, HDMI) • Set vibrance (    0) • None
            • (1, DP  ) • Set vibrance (    0) • Success
            • (2, DP  ) • Set vibrance (    0) • None
            • (3, DP  ) • Set vibrance (    0) • Success
            • (4, DP  ) • Set vibrance (    0) • None
            • (5, DP  ) • Set vibrance (    0) • Success
            • (6, DP  ) • Set vibrance (    0) • None
            busno=4. Monitor apparently returns -EIO for unsupported features. This cannot be relied on.
    


  THEREFORE:
  - the command structure is: `nvibrant 0 <vibrance_monitor1> 0 <vibrance_monitor2> 0 <vibrance_monitor3>`
  - Vibrance value for the respective monitor index shall be inserted at position 2*index-1 in the command parameters.

        
## TODO
- quality: non-destructive settings (save monitor's settings)
- polish: minimize to tray
- flair: preset pane title reactions to global hotkey recognition
- quality: better compatibility (need users)
