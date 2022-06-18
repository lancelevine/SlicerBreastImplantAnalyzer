cmake_minimum_required(VERSION 3.13.4)

project(BreastImplantAnalyzer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/BreastImplantAnalyzer")
set(EXTENSION_CATEGORY "Quantification")
set(EXTENSION_CONTRIBUTORS "Lance Levine (University of Miami Miller School of Medicine), Marc Levine, Dr. Wrood Kassira (University of Miami Department of Plastic Surgery)")
set(EXTENSION_DESCRIPTION "This is an example of a simple extension")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/lancelevine/SlicerBreastImplantAnalyzer/master/BreastImplantAnalyzer.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/lancelevine/SlicerBreastImplantAnalyzer/master/Screenshot01.PNG")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(BreastImplantAnalyzer)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
