# ImplantSizer
A 3D Slicer extension for measuring the volume of breast implants

![Alt text](Screenshot01.PNG?raw=true "ImplantSizer User Interface")

## Installation

* Download and install the latest preview release version of 3D Slicer (https://download.slicer.org).
* Start 3D Slicer application, open the Extension Manager (menu: View / Extension manager)
* Install ImplantSizer extension.

## Tutorial

1. Start 3D Slicer

2. Load a DICOM: Click the DICOM module button

![Alt text](img/DICOM.PNG?raw=true "Load DICOM")

3. Load a DICOM: Click the import button and select the breast MRI to load

![Alt text](img/Import.PNG?raw=true "Import DICOM")

4. Load a DICOM: Load the selected study (you may need to attempt multiple studies and find the one with the best contrast between the implant and outside tissue)

![Alt text](img/Load.PNG?raw=true "Load DICOM")

5. Switch to the ImplantSizer module

![Alt text](img/module.PNG?raw=true "Switch to module")

6. Select the input volume of the DICOM you imported. It should match the name listed in the viewport.

![Alt text](img/input.PNG?raw=true "Select input volume")

7. Adjust contrast if needed. Further contrast modifications can be made in the Volumes module.

![Alt text](img/adjust.PNG?raw=true "Select input volume")

8. Click 'apply'

9. Click inside the implant

![Alt text](img/inside.PNG?raw=true "Select inside the implant")

10. Follow the directions to click outside the implant. Example clicks are shown. Do not click too close to the implant as a sphere of 3 pixel radius is placed.

![Alt text](img/outside.PNG?raw=true "Select inside the implant")

11. Follow the same directions for the remaining clicks.

12. The final volume calculation is then presented. Examine the implant in the viewports to ensure it looks right and the algorithm ran properly.

![Alt text](img/volume.PNG?raw=true "The final volume calculation")


## Developers
Developed by Lance Levine and Marc Levine. Special thanks to Dr. Wrood Kassira.
