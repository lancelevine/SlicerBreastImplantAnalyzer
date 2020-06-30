import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# BreastImplantAnalyzer
#

class BreastImplantAnalyzer(ScriptedLoadableModule):

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Breast Implant Analyzer"
    self.parent.categories = ["Quantification"]
    self.parent.dependencies = []
    self.parent.contributors = [
      "Lance Levine (University of Miami Miller School of Medicine)",
      "Marc Levine (Penn State University College of Medicine)",
      "Dr. Wrood Kassira (University of Miami Department of Plastic & Reconstructive Surgery)"]
    self.parent.helpText = """
This module calculates the size of a breast implant from breast MRI data. Use the 3D Slicer DICOM manager (purple arrow button at the top) to input a DICOM.
Select the input data from the drop down and click 'apply'.
You may adjust contrast first to make the implants easier to see.
You will be asked to click inside the implant, please click close to the center.
On all future clicks, select outside the implant, but not too close to the border of the implant.
If too much of the surrounding tissue is highlighted, try increasing 'Seed Locality' under the Advanced menu.
See more information in <a href="https://github.com/lancelevine/SlicerBreastImplantAnalyzer#breastimplantanalyzer">module documentation</a>.
"""
    self.parent.acknowledgementText = """This module was written by Lance Levine and Marc Levine, with the help of Dr. Kassira."""
    slicer.app.connect("startupCompleted()", self.registerSampleData)

  def registerSampleData(self):
    # Add data set to Sample Data module
    iconsPath = os.path.join(os.path.dirname(self.parent.path), 'Resources/Icons')
    import SampleData
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
      category='Breast Implant Analyzer',
      sampleName='MRBreastImplant',
      uris='https://github.com/lancelevine/SlicerBreastImplantAnalyzer/raw/master/SampleData/MRBreastImplant.nrrd',
      fileNames='MRBreastImplant.nrrd',
      nodeNames='MRBreastImplant',
      thumbnailFileName=os.path.join(iconsPath, 'MRBreastImplant.png'),
      checksums = 'SHA256:4bbad3e4034005ddb06ac819bfae2ded2175838f733dfd6ee12f81787450258a'
    )

#
# BreastImplantAnalyzerWidget
#

class BreastImplantAnalyzerWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None

    customLayout = """
      <layout type="horizontal">
        <item>
        <view class="vtkMRMLSliceNode" singletontag="Red">
          <property name="orientation" action="default">Axial</property>
          <property name="viewlabel" action="default">R</property>
          <property name="viewcolor" action="default">#F34A33</property>
        </view>
        </item>
      </layout>
      """

    # Built-in layout IDs are all below 100, so you can choose any large random number
    # for your custom layout ID.
    self.customLayoutId=503
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(self.customLayoutId, customLayout)

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer)
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/BreastImplantAnalyzer.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create a new parameterNode
    # This parameterNode stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.logic = BreastImplantAnalyzerLogic()

    self.selectParameterNode()

    # Connections
    self.ui.startButton.connect('toggled(bool)', self.onStartButton)
    self.ui.contrastButton.connect('toggled(bool)', self.onContrastButton)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.seedLocalitySliderWidget.connect("valueChanged(double)", self.updateParameterNodeFromGUI)

    # Connect observers to scene events
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndImportEvent, self.onSceneEndImport)

    self.ui.resultLabel.text = ""

    # Initial GUI update
    self.updateGUIFromParameterNode()

    self.originalLayout = 0

    self.fidNode = None
    self.fidNodeObserverTag = None

    logging.info("Loaded module")

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()
    logging.info("cleaning up")

  def enter(self):
    self.selectParameterNode()

  def exit(self):
    self.stopFiducialPlacement()
    self.removeObservers()

  def selectParameterNode(self):
    # Ensure parameter node exists
    self.setParameterNode(self.logic.getParameterNode())

    # Select first volume node in the scene by default (if none is selected yet)
    if not self._parameterNode.GetNodeReference("InputVolume"):
        firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
        if firstVolumeNode:
            self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())

    self.updateGUIFromParameterNode()

  def onSceneStartClose(self, caller, event):
    self.stopFiducialPlacement()
    self._parameterNode = None
    self.ui.resultLabel.text = ""

  def onSceneEndClose(self, caller, event):
    if self.parent.isEntered:
      self.selectParameterNode()

  def onSceneEndImport(self, caller, event):
    if self.parent.isEntered:
      self.selectParameterNode()

  def setParameterNode(self, inputParameterNode):
    """
    Adds observers to the selected parameter node. Observation is needed because when the
    parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    if inputParameterNode == self._parameterNode:
      # No change
      return

    # Unobserve previusly selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    if inputParameterNode is not None:
      self.addObserver(inputParameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode

    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """

    # Disable all sections if no parameter node is selected
    self.ui.basicCollapsibleButton.enabled = self._parameterNode is not None
    self.ui.advancedCollapsibleButton.enabled = self._parameterNode is not None
    if self._parameterNode is None:
      return

    # Update each widget from parameter node
    # Need to temporarily block signals to prevent infinite recursion (MRML node update triggers
    # GUI update, which triggers MRML node update, which triggers GUI update, ...)

    inputVolume = self._parameterNode.GetNodeReference("InputVolume")

    wasBlocked = self.ui.inputSelector.blockSignals(True)
    self.ui.inputSelector.setCurrentNode(inputVolume)
    self.ui.inputSelector.blockSignals(wasBlocked)

    if self._parameterNode.GetParameter("SeedLocality"):
        wasBlocked = self.ui.seedLocalitySliderWidget.blockSignals(True)
        self.ui.seedLocalitySliderWidget.value = float(self._parameterNode.GetParameter("SeedLocality"))
        self.ui.seedLocalitySliderWidget.blockSignals(wasBlocked)

    # Update buttons states and tooltips
    if inputVolume:
        self.ui.startButton.toolTip = "Start point placement"
        self.ui.startButton.enabled = True
        self.ui.contrastButton.enabled = True
    else:
        self.ui.startButton.toolTip = "Select input volume node"
        self.ui.startButton.enabled = False
        self.ui.contrastButton.enabled = False

    wasBlocked = self.ui.contrastButton.blockSignals(True)
    self.ui.contrastButton.setChecked(self.logic.isOriginalContrastAvailable(inputVolume))
    self.ui.contrastButton.blockSignals(wasBlocked)

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
      return

    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    self._parameterNode.SetParameter("Threshold", str(self.ui.seedLocalitySliderWidget.value))

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointAddedEvent(self, caller=None, event=None, call_data=None):
    if not self.fidNode:
      # not in fiducial placement state
      return

    # Get slice logic and slider range
    layoutManager = slicer.app.layoutManager()
    red = layoutManager.sliceWidget('Red')
    redLogic = red.sliceLogic()
    import numpy as np
    sliceBounds = np.zeros(6)
    redLogic.GetVolumeSliceBounds(self.ui.inputSelector.currentNode(), sliceBounds)
    sliceOffsetStart = sliceBounds[4]
    sliceOffsetRange = abs(sliceBounds[4]-sliceBounds[5])

    numberOfPlacedFiducials = self.fidNode.GetNumberOfDefinedControlPoints()
    if numberOfPlacedFiducials == 0:  # point 0
      self.ui.resultLabel.text = "Click INSIDE the center of the implant"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.5)  # volume center
    elif numberOfPlacedFiducials < 5: # point 1-4
      self.ui.resultLabel.text = "Click OUTSIDE the implant " + str(5-numberOfPlacedFiducials) + " times"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.5)  # volume center
    elif numberOfPlacedFiducials < 6: # point 5
      self.ui.resultLabel.text = "Click OUTSIDE the implant " + str(6-numberOfPlacedFiducials) + " times"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.1)  # low 10%
    elif numberOfPlacedFiducials < 9: # point 6-8
      self.ui.resultLabel.text = "Click OUTSIDE the implant " + str(9-numberOfPlacedFiducials) + " times"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.25)  # low 25%
    elif numberOfPlacedFiducials < 12: # point 9-11
      self.ui.resultLabel.text = "Click OUTSIDE the implant " + str(12-numberOfPlacedFiducials) + " times"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.75)  # top 25%
    elif numberOfPlacedFiducials < 13: # point 12
      self.ui.resultLabel.text = "Click OUTSIDE the implant " + str(13-numberOfPlacedFiducials) + " times"
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.9)  # top 10%
    else:
      # finished placing points
      self.ui.resultLabel.text = "Calculating implant volume..."
      slicer.app.processEvents()
      # Calculate segmentation
      try:
          implantVolumeCc = self.logic.computeImplantVolumeCc(self.ui.inputSelector.currentNode(), self.fidNode, self.ui.seedLocalitySliderWidget.value)
          self.ui.resultLabel.text = "Implant Volume: " + '{:.2f}'.format(implantVolumeCc)
      except Exception as e:
          slicer.util.errorDisplay("Failed to compute results: "+str(e))
          self.ui.resultLabel.text = ""
          import traceback
          traceback.print_exc()

      layoutManager.setLayout(self.originalLayout)
      redLogic.SetSliceOffset(sliceOffsetStart + sliceOffsetRange * 0.5)  # volume center

      self.ui.startButton.text = "Start"
      wasBlocked = self.ui.startButton.blockSignals(True)  # block signals, otherwise toggle would cancel placement and clear results
      self.ui.startButton.checked = False
      self.ui.startButton.blockSignals(wasBlocked)

      # We are in a callback function of the markup fiducial, so we cannot directly
      # delete the markup now. Instead we set up a timer and delete the node when the application will becomes idle.
      qt.QTimer.singleShot(0, self.stopFiducialPlacement)

  def startFiducialPlacement(self):
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    if not self.fidNode:
      self.fidNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "BreastImplantAnalyzerSeedPoints")
      self.fidNode.SetSaveWithScene(False)  # temporary node, do not save with scene
      self.fidNode.CreateDefaultDisplayNodes()
      self.fidNode.GetDisplayNode().SetPointLabelsVisibility(False)
      self.fidNode.RemoveAllMarkups()
    if not self.fidNodeObserverTag:
      self.fidNodeObserverTag = self.fidNode.AddObserver(self.fidNode.PointPositionDefinedEvent, self.onPointAddedEvent)
    self.selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    self.selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
    interactionNode.SetPlaceModePersistence(True)
    interactionNode.SetCurrentInteractionMode(slicer.vtkMRMLInteractionNode().Place)

  def stopFiducialPlacement(self):
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    interactionNode.SwitchToViewTransformMode()
    interactionNode.SetPlaceModePersistence(0)
    if self.fidNodeObserverTag:
      self.fidNode.RemoveObserver(self.fidNodeObserverTag)
      self.fidNodeObserverTag = None
    if self.fidNode:
      slicer.mrmlScene.RemoveNode(self.fidNode)
      self.fidNode = None

  def onContrastButton(self, pushed):
    self.logic.setAutoContrast(pushed, self.ui.inputSelector.currentNode())

  def onStartButton(self, start):
    if start:
      self.ui.startButton.text = "Cancel"

      # Set custom layout
      layoutManager = slicer.app.layoutManager()
      self.originalLayout = layoutManager.layout
      layoutManager.setLayout(self.customLayoutId)

      # Fit image in red slice view
      red = layoutManager.sliceWidget('Red')
      redLogic = red.sliceLogic()
      red.sliceController().fitSliceToBackground()

      self.startFiducialPlacement()

      # initial update
      self.onPointAddedEvent()

    else:
      # Stop requested
      self.ui.startButton.text = "Start"
      self.ui.resultLabel.text = ""
      self.stopFiducialPlacement()


#
# BreastImplantAnalyzerLogic
#

class BreastImplantAnalyzerLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    ScriptedLoadableModuleLogic.__init__(self)
    self.segmentationNode = None

  def isOriginalContrastAvailable(self, volumeNode):
    if not volumeNode:
      return False
    originalWindow = volumeNode.GetAttribute("BreastImplantAnalyzer.OriginalWindow")
    originalLevel = volumeNode.GetAttribute("BreastImplantAnalyzer.OriginalLevel")
    return originalWindow and originalLevel

  def setAutoContrast(self, enable, volumeNode):
    displayNode = volumeNode.GetDisplayNode()
    if enable:
      # enable auto-contrast
      # Save original window/level to volume node
      volumeNode.SetAttribute("BreastImplantAnalyzer.OriginalWindow", str(displayNode.GetWindow()))
      volumeNode.SetAttribute("BreastImplantAnalyzer.OriginalLevel", str(displayNode.GetLevel()))
      # force recomputation of window/level
      displayNode.AutoWindowLevelOff()
      displayNode.AutoWindowLevelOn()
    else:
      # restore original window/level
      if not self.isOriginalContrastAvailable(volumeNode):
        raise ValueError("Failed to restore original window/level for volume node, previous values were not found")
      originalWindow = volumeNode.GetAttribute("BreastImplantAnalyzer.OriginalWindow")
      originalLevel = volumeNode.GetAttribute("BreastImplantAnalyzer.OriginalLevel")
      # Remove original values so that the GUI knows that the original values are used now
      volumeNode.SetAttribute("BreastImplantAnalyzer.OriginalWindow", "")
      volumeNode.SetAttribute("BreastImplantAnalyzer.OriginalLevel", "")
      displayNode.AutoWindowLevelOff()
      displayNode.SetWindow(float(originalWindow))
      displayNode.SetLevel(float(originalLevel))

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("SeedLocality"):
      parameterNode.SetParameter("SeedLocality", "0.0")

  def computeImplantVolumeCc(self, inputVolume, fidNode, seedLocality):
    """
    Compute implant volume.
    Can be used without GUI widget. Created segmentation node is saved in self.segmentationNode.
    :param inputVolume: volume to be thresholded
    :param fidNode: input points, first point is inside, others are outside
    :param seedLocality: if setting >0 value then region growing is more limited to neighborhood of provided seeds
    """

    if not inputVolume:
      raise ValueError("Input volume is invalid")

    logging.info('Processing started')

    masterVolumeNode = inputVolume

    # Create segmentation
    segmentationNode = slicer.vtkMRMLSegmentationNode()
    slicer.mrmlScene.AddNode(segmentationNode)
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)

    # Create seed segment inside implant
    tumorSeed = vtk.vtkSphereSource()
    centerpoint = [0,0,0]
    fidNode.GetNthFiducialPosition(0, centerpoint)
    logging.info("inside: " + str(centerpoint))
    tumorSeed.SetCenter(centerpoint)
    tumorSeed.SetRadius(5)
    tumorSeed.Update()
    implantSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tumorSeed.GetOutput(), "Implant", [1.0,0.0,0.0])

    # Create seed segment from points outside implant
    append = vtk.vtkAppendPolyData()
    nOfFiduciallPoints = fidNode.GetNumberOfDefinedControlPoints()
    for i in range(1, nOfFiduciallPoints):
      fidNode.GetNthFiducialPosition(i, centerpoint)
      backgroundSeed = vtk.vtkSphereSource()
      backgroundSeed.SetCenter(centerpoint)
      logging.info("outside: " + str(centerpoint))
      backgroundSeed.SetRadius(3)
      backgroundSeed.Update()
      append.AddInputData(backgroundSeed.GetOutput())
    append.Update()
    backgroundSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), "Background", [0.0,1.0,0.0])

    # Create segment editor to get access to effects
    segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    # To show segment editor widget (useful for debugging): segmentEditorWidget.show()
    segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    segmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
    slicer.mrmlScene.AddNode(segmentEditorNode)
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    segmentEditorWidget.setSegmentationNode(segmentationNode)
    segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

    # Run segmentation
    segmentEditorWidget.setActiveEffectByName("Grow from seeds")
    effect = segmentEditorWidget.activeEffect()
    # You can change parameters by calling: effect.setParameter("MyParameterName", someValue)
    # Most effect don't have onPreview, you can just call onApply
    effect.setParameter("Seed locality", seedLocality)
    effect.self().onPreview()
    effect.self().onApply()

    # Clean up
    slicer.mrmlScene.RemoveNode(segmentEditorNode)
    segmentationNode.RemoveSegment(backgroundSegmentId)
    # save the created segmentation node, just in case the caller needs it (for adjusting visualization, removing it, etc.)
    self.segmentationNode = segmentationNode

    # Compute segment volumes
    import SegmentStatistics
    segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
    segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    segStatLogic.getParameterNode().SetParameter("ScalarVolume", masterVolumeNode.GetID())
    segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled","False")
    segStatLogic.computeStatistics()
    # print(segStatLogic.getStatistics())  # prints all computed metrics
    implantVolumeCc = segStatLogic.getStatistics()[implantSegmentId,"ScalarVolumeSegmentStatisticsPlugin.volume_cm3"]
    logging.info("Processing result: " + str(implantVolumeCc))

    return implantVolumeCc


#
# BreastImplantAnalyzerTest
#

class BreastImplantAnalyzerTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_BreastImplantAnalyzer1()

  def test_BreastImplantAnalyzer1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    import numpy as np
    import numpy.testing as npt

    # Get input image
    import SampleData
    inputVolume = SampleData.downloadSample('MRBreastImplant')
    self.delayDisplay('Loaded test data set')

    # Set input seed positions
    seedPointPositions = np.array(
      [[ 90.53668037,  -9.29200187,  16.1472    ],
       [103.62091215,  25.87187103,  16.1472    ],
       [152.68678131,   2.15670093,  16.1472    ],
       [ 86.44785794, -47.72693271,  16.1472    ],
       [ 16.93787664,   0.52117196,  16.1472    ],
       [ 70.09256822,  24.23634206, -77.13263692],
       [ 83.1768    , -55.08681308, -42.15269808],
       [155.95783925, -12.56305981, -42.15269808],
       [ 71.7280972 ,  21.7830486 , -42.15269808],
       [ 83.99456449,  13.60540374,  74.44709808],
       [132.24266916, -17.46964673,  74.44709808],
       [ 43.92410467, -54.2690486 ,  74.44709808],
       [ 79.08797757, -20.74070467, 109.42703692],
       [ 81.54127103, -22.37623364, 109.42703692]])
    seedPointsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
    slicer.util.updateMarkupsControlPointsFromArray(seedPointsNode, seedPointPositions)

    # Test volume computation
    logic = BreastImplantAnalyzerLogic()
    implantVolumeCc = logic.computeImplantVolumeCc(inputVolume, seedPointsNode, 0.0)
    npt.assert_almost_equal(implantVolumeCc, 352.6, decimal = 1)

    self.delayDisplay('Test passed')
