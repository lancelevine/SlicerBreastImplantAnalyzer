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
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Lance Levine (University of Miami Miller School of Medicine)", "Marc Levine (Penn State University College of Medicine)", "Dr. Wrood Kassira (University of Miami Department of Plastic & Reconstructive Surgery)"] 
    self.parent.helpText = """
This module calculates the size of a breast implant from breast MRI data. Use the 3D Slicer DICOM manager (purple arrow button at the top) to input a DICOM.
Select the input data from the drop down and click 'apply'.
You may adjust contrast first to make the implants easier to see.
You will be asked to click inside the implant, please click close to the center.
On all future clicks, select outside the implant, but not too close to the border of the implant.
If too much of the surrounding tissue is highlighted, try increasing 'Seed Locality' under the Advanced menu.
"""  # TODO: update with short description of the module
    self.parent.helpText += self.getDefaultModuleDocumentationLink()  # TODO: verify that the default URL is correct or change it to the actual documentation
    self.parent.acknowledgementText = """
This module was written by Lance Levine and Marc Levine, with the help of Dr. Kassira.
"""  # TODO: replace with organization, grant and thanks.

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

    # Example of adding widgets dynamically (without Qt designer).
    # This approach is not recommended, but only shown as an illustrative example.
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "More"
    parametersCollapsibleButton.collapsed = True
    self.layout.addWidget(parametersCollapsibleButton)
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)
    #self.invertedOutputSelector = slicer.qMRMLNodeComboBox()
    #self.invertedOutputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    #self.invertedOutputSelector.addEnabled = True
    #self.invertedOutputSelector.removeEnabled = True
    #self.invertedOutputSelector.noneEnabled = True
    #self.invertedOutputSelector.setMRMLScene(slicer.mrmlScene)
    #self.invertedOutputSelector.setToolTip("Result with inverted threshold will be written into this volume")
    #parametersFormLayout.addRow("Inverted output volume: ", self.invertedOutputSelector)

    # Create a new parameterNode
    # This parameterNode stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.logic = BreastImplantAnalyzerLogic()
    self.ui.parameterNodeSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
    self.setParameterNode(self.logic.getParameterNode())

    # Connections
    self.ui.parameterNodeSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.setParameterNode)
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.contrastButton.connect('clicked(bool)', self.onContrastButton)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    #self.ui.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
    self.ui.imageThresholdSliderWidget.connect("valueChanged(double)", self.updateParameterNodeFromGUI)
    #self.ui.invertOutputCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    #self.invertedOutputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

    # Initial GUI update
    self.updateGUIFromParameterNode()
    
    self.phase_zero = 1
    self.phase_one = 0
    self.phase_two = 0
    self.phase_three = 0
    self.phase_four = 0
    
    self.oldLayout = 0
    
    self.autodisplay = False
    self.inputDisplayWindow = 0.0
    self.inputDisplayLevel = 0.0
    
    self.selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    self.selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
    slicer.modules.markups.logic().AddFiducial()
    self.fidNode = slicer.util.getNode("vtkMRMLMarkupsFiducialNode1")
    self.initial_fiducial_count = self.fidNode.GetNumberOfFiducials()
    coords = [0.0, 0.0, 0.0]
    self.fidNode.GetNthFiducialPosition(self.initial_fiducial_count-1, coords)
    self.fidNode.GetDisplayNode().SetVisibility(False)
    #logging.info(str(coords))
    #self.fidNode.RemoveAllMarkups()
    self.observerTag = self.fidNode.AddObserver(self.fidNode.PointAddedEvent, self.onPointAddedEvent)
    
    logging.info("Loaded module")

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()
    self.fidNode.RemoveObserver(self.observerTag)
    logging.info("cleaning up")

  def setParameterNode(self, inputParameterNode):
    """
    Adds observers to the selected parameter node. Observation is needed because when the
    parameter node is changed then the GUI must be updated immediately.
    """

    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)

    # Set parameter node in the parameter node selector widget
    wasBlocked = self.ui.parameterNodeSelector.blockSignals(True)
    self.ui.parameterNodeSelector.setCurrentNode(inputParameterNode)
    self.ui.parameterNodeSelector.blockSignals(wasBlocked)

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

    wasBlocked = self.ui.inputSelector.blockSignals(True)
    self.ui.inputSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
    self.ui.inputSelector.blockSignals(wasBlocked)

    #wasBlocked = self.ui.outputSelector.blockSignals(True)
    #self.ui.outputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolume"))
    #self.ui.outputSelector.blockSignals(wasBlocked)

    #wasBlocked = self.invertedOutputSelector.blockSignals(True)
    #self.invertedOutputSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputVolumeInverse"))
    #self.invertedOutputSelector.blockSignals(wasBlocked)

    wasBlocked = self.ui.imageThresholdSliderWidget.blockSignals(True)
    self.ui.imageThresholdSliderWidget.value = float(self._parameterNode.GetParameter("Threshold"))
    logging.info(self._parameterNode.GetParameter("Threshold"))
    self.ui.imageThresholdSliderWidget.blockSignals(wasBlocked)

    #wasBlocked = self.ui.invertOutputCheckBox.blockSignals(True)
    #self.ui.invertOutputCheckBox.checked = (self._parameterNode.GetParameter("Invert") == "true")
    #self.ui.invertOutputCheckBox.blockSignals(wasBlocked)

    # Update buttons states and tooltips
    #if self._parameterNode.GetNodeReference("InputVolume") and self._parameterNode.GetNodeReference("OutputVolume"):
    if self._parameterNode.GetNodeReference("InputVolume"):
    #  self.ui.applyButton.toolTip = "Compute output volume"
        self.ui.applyButton.enabled = True
        self.ui.contrastButton.enabled = True
    else:
    #  self.ui.applyButton.toolTip = "Select input and output volume nodes"
        self.ui.applyButton.toolTip = "Select input volume node"
        self.ui.applyButton.enabled = False
        self.ui.contrastButton.enabled = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """

    if self._parameterNode is None:
      return

    self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputSelector.currentNodeID)
    #self._parameterNode.SetNodeReferenceID("OutputVolume", self.ui.outputSelector.currentNodeID)
    self._parameterNode.SetParameter("Threshold", str(self.ui.imageThresholdSliderWidget.value))
    #self._parameterNode.SetParameter("Invert", "true" if self.ui.invertOutputCheckBox.checked else "false")
    #self._parameterNode.SetNodeReferenceID("OutputVolumeInverse", self.invertedOutputSelector.currentNodeID)

  @vtk.calldata_type(vtk.VTK_INT)
  def onPointAddedEvent(self, caller, event, call_data):
    #logging.info(str(self.fidNode.GetNumberOfFiducials()))
    #logging.info("marked")
    #logging.info(str(self.phase_zero) + str(self.phase_one) + str(self.phase_two) + str(self.phase_three))
    layoutManager = slicer.app.layoutManager()
    red = layoutManager.sliceWidget('Red')
    redLogic = red.sliceLogic()
    dimen = self.ui.inputSelector.currentNode().GetImageData().GetDimensions()
    #logging.info("init " + str(self.initial_fiducial_count))
    #logging.info("num " + str(self.fidNode.GetNumberOfFiducials()))
    import numpy as np
    points = np.zeros((6,1 ))
    redLogic.GetVolumeSliceBounds(self.ui.inputSelector.currentNode(), points)
    slicedim = abs(points[4]) + abs(points[5])
    
    #logging.info("slicedim: " + str(slicedim))
    
    #logging.info("dimen " + str(points[0]) + str(points[1]) + str(points[2]) + str(points[3]) + str(points[4]) + str(points[5]))
    
    #redLogic.SetSliceOffset(int(dimen[2] / 2))

    #if self.phase_one is 1 and self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+3):
    #    #redLogic.SetSliceOffset(int(dimen[2] / 2))
     #   self.phase_one = 1
    if self.phase_zero:
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+1):
            self.ui.final_volume_label.text = "Click OUTSIDE the boundary of the implant " + str(5-(self.fidNode.GetNumberOfFiducials()-(self.initial_fiducial_count+1))) + " times"
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+5):
            #redLogic.SetSliceOffset(int(dimen[2] / 10))
            redLogic.SetSliceOffset((slicedim / 10) + points[4]) 
            self.phase_zero = 0
            self.phase_one = 1
        
    if self.phase_one:
        self.ui.final_volume_label.text = "Click OUTSIDE the boundary of the implant " + str(2-(self.fidNode.GetNumberOfFiducials()-(self.initial_fiducial_count+5))) + " times"
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+6):
            redLogic.SetSliceOffset((slicedim / 4) + points[4]) 
            self.phase_one = 0
            self.phase_two = 1
            
    if self.phase_two:
        self.ui.final_volume_label.text = "Click OUTSIDE the boundary of the implant " + str(4-(self.fidNode.GetNumberOfFiducials()-(self.initial_fiducial_count+6))) + " times"
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+9):
            redLogic.SetSliceOffset((3 * slicedim / 4) + points[4])
            self.phase_two = 0
            self.phase_three = 1 

    if self.phase_three:
        self.ui.final_volume_label.text = "Click OUTSIDE the boundary of the implant " + str(4-(self.fidNode.GetNumberOfFiducials()-(self.initial_fiducial_count+9))) + " times"
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+12):
            redLogic.SetSliceOffset((9 * slicedim / 10) + points[4])
            self.phase_three = 0
            self.phase_four = 1 
    
    if self.phase_four:
        self.ui.final_volume_label.text = "Click OUTSIDE the boundary of the implant " + str(2-(self.fidNode.GetNumberOfFiducials()-(self.initial_fiducial_count+12))) + " times"
        if self.fidNode.GetNumberOfFiducials() > (self.initial_fiducial_count+13):
            self.ui.final_volume_label.text = "Calculating implant volume..." 
            redLogic.SetSliceOffset(int(dimen[2] / 4))
            self.phase_four = 0
            #switch back
    
            interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
            interactionNode.SwitchToViewTransformMode()
            # also turn off place mode persistence if required
            interactionNode.SetPlaceModePersistence(0)
            
            # Calculate segmentation
            try:
                final_volume = self.logic.run(self.ui.inputSelector.currentNode(), self.ui.inputSelector.currentNode(), self.ui.imageThresholdSliderWidget.value, self.fidNode, self.initial_fiducial_count)
                #if self.invertedOutputSelector.currentNode():
                # If additional output volume is selected then result with inverted threshold is written there
                #self.logic.run(self.ui.inputSelector.currentNode(),
                #    self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)
                # Determine multiplier

                dim = self.ui.inputSelector.currentNode().GetImageData().GetDimensions()

                dim_multiplier = dim[0] / 256
                dim_multiplier *= (dim[1] / 256)
                
                dim_multiplier = 1
                
                #logging.info(dim_multiplier)

                self.ui.final_volume_label.text = "Implant Volume: " + '{:.2f}'.format((float(final_volume) * int(dim_multiplier))) + "cc"
                
                layoutManager.setLayout(self.oldLayout)

                #self.ui.final_volume_label.text = "Implant Volume: " + str((float(final_volume) * int(dim_multiplier))) + "cc"
                #self.ui.final_volume_label.text = "Implant Volume: " + str((float(final_volume) * float(3.78))) + " cc"

                if dim[0] % 256 != 0 or dim[1] % 256 != 0:
                    self.ui.error_label.text = "Invalid image dimensions, results may be skewed..."
                
                
                logging.info(dim[0])
            except Exception as e:
                slicer.util.errorDisplay("Failed to compute results: "+str(e))
                import traceback
                traceback.print_exc()
      

    
  def onContrastButton(self):
   logging.info("Contrast button pressed" + str(self.inputDisplayWindow))
   volumeNode = self.ui.inputSelector.currentNode()
   displayNode = volumeNode.GetDisplayNode()
   if self.autodisplay is False:
    self.inputDisplayWindow = displayNode.GetWindow()
    self.inputDisplayLevel = displayNode.GetLevel()
    displayNode.AutoWindowLevelOn()
    self.autodisplay = True
   else:
    displayNode.AutoWindowLevelOff()
    displayNode.SetWindow(self.inputDisplayWindow)
    displayNode.SetLevel(self.inputDisplayLevel)
    self.autodisplay = False

  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    dim = self.ui.inputSelector.currentNode().GetImageData().GetDimensions()
    layoutManager = slicer.app.layoutManager()
    self.oldLayout = layoutManager.layout
    #logging.info("Layout: " + str(layoutManager.layout))
    red = layoutManager.sliceWidget('Red')
    redLogic = red.sliceLogic()
    
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
    customLayoutId=503

    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId, customLayout)                                         

    # Switch to the new custom layout 
    layoutManager.setLayout(customLayoutId)
    
    red.sliceController().fitSliceToBackground()
    
    import numpy as np
    points = np.zeros((6,1 ))
    redLogic.GetVolumeSliceBounds(self.ui.inputSelector.currentNode(), points)
    slicedim = abs(points[4]) + abs(points[5])
    
    #redLogic.SetSliceOffset(int(dim[2]/4))
    
    #redLogic.SetSliceOffset(int(dim[2] / 2))
    redLogic.SetSliceOffset((slicedim / 2) + points[4])
    
    self.ui.final_volume_label.text = "Click INSIDE the center of the implant"
    
    self.initial_fiducial_count = self.fidNode.GetNumberOfFiducials()
    
    self.phase_zero = 1
    self.phase_one = 0
    self.phase_two = 0
    self.phase_three = 0
    
    #selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    #selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
    #fidNode = slicer.util.getNode("vtkMRMLMarkupsFiducialNode1")
    #fidNode.SetFiducialWorldCoordinates((1,0,5))
    #fidNode.AddObserver(slicer.vtkMRMLMarkupsNode.MarkupAddedEvent, markupAdded())
    interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    placeModePersistence = 1
    interactionNode.SetPlaceModePersistence(placeModePersistence)
    # mode 1 is Place, can also be accessed via slicer.vtkMRMLInteractionNode().Place
    interactionNode.SetCurrentInteractionMode(1)
    #logging.info("int mode")
    
    
    """try:
      final_volume = self.logic.run(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
        self.ui.imageThresholdSliderWidget.value, self.ui.invertOutputCheckBox.checked)
      if self.invertedOutputSelector.currentNode():
        # If additional output volume is selected then result with inverted threshold is written there
        self.logic.run(self.ui.inputSelector.currentNode(), self.invertedOutputSelector.currentNode(),
          self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()
      

    # Determine multiplier

    dim = self.ui.inputSelector.currentNode().GetImageData().GetDimensions()

    dim_multiplier = dim[0] / 256
    dim_multiplier *= (dim[1] / 256)
    
    logging.info(dim_multiplier)

    self.ui.final_volume_label.text = "Implant Volume: " + str((float(final_volume) * int(dim_multiplier))) + "cc"


    if dim[0] % 256 != 0 or dim[1] % 256 != 0:
        self.ui.error_label.text = "Invalid image dimensions, results may be skewed..."
    
    
    logging.info(dim[0])"""

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

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    if not parameterNode.GetParameter("Threshold"):
      parameterNode.SetParameter("Threshold", "0.0")
    if not parameterNode.GetParameter("Invert"):
      parameterNode.SetParameter("Invert", "false")

  def run(self, inputVolume, outputVolume, imageThreshold, fidNode, initial_fiducial_count, showResult=True):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """

    if not inputVolume:
      raise ValueError("Input volume is invalid")

    logging.info('Processing started')

    # Compute the thresholded output volume using the Threshold Scalar Volume CLI module
    #cliParams = {
    #  'InputVolume': inputVolume.GetID(),
    #  'OutputVolume': outputVolume.GetID(),
    #  'ThresholdValue' : imageThreshold,
    #  'ThresholdType' : 'Above' if invert else 'Below'
    #  }
    #cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)

    masterVolumeNode = inputVolume
    
    # Create segmentation
    #segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    #segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    #segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)
    #addedSegmentID = segmentationNode.GetSegmentation().AddEmptySegment("skin")

    # Create segment editor to get access to effects
    #segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    #segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
    #segmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    #segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
    #segmentEditorWidget.setSegmentationNode(segmentationNode)
    #segmentEditorWidget.setMasterVolumeNode(masterVolumeNode)

    # Thresholding
    #segmentEditorWidget.setActiveEffectByName("Threshold")
    #effect = segmentEditorWidget.activeEffect()
    #effect.setParameter("MinimumThreshold","10")
    #effect.setParameter("MaximumThreshold","75")
    #effect.self().onApply()
    
    # Create segmentation
    segmentationNode = slicer.vtkMRMLSegmentationNode()
    slicer.mrmlScene.AddNode(segmentationNode)
    segmentationNode.CreateDefaultDisplayNodes() # only needed for display
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(masterVolumeNode)

    #slicer.modules.markups.logic().AddFiducial()
    #placeModePersistence = 1
    #slicer.modules.markups.logic().StartPlaceMode(placeModePersistence)
    #selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
    #selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
    #interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
    #placeModePersistence = 1
    #interactionNode.SetPlaceModePersistence(placeModePersistence)
    # mode 1 is Place, can also be accessed via slicer.vtkMRMLInteractionNode().Place
    #interactionNode.SetCurrentInteractionMode(1)

    # Create seed segment inside tumor
    tumorSeed = vtk.vtkSphereSource()
    #tumorSeed.SetCenter(127, 241, 98)
    centerpoint = [0,0,0]
    fidNode.GetNthFiducialPosition(initial_fiducial_count, centerpoint)
    logging.info("center: " + str(centerpoint))
    tumorSeed.SetCenter(centerpoint)
    tumorSeed.SetRadius(5)
    tumorSeed.Update()
    segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tumorSeed.GetOutput(), "Tumor", [1.0,0.0,0.0])

    import numpy as np
    nOfFiduciallPoints = fidNode.GetNumberOfFiducials()
    #points = np.zeros([3,nOfFiduciallPoints])
    points = np.zeros((nOfFiduciallPoints-initial_fiducial_count-2,3 ))
    #logging.info(str(points[0]))
    for i in range(nOfFiduciallPoints-initial_fiducial_count-2):
        #logging.info(str(i))
        fidNode.GetNthFiducialPosition(i+initial_fiducial_count+1, points[i])
        #logging.info(str(points[i]))
    #self.fidNode.GetNthFiducialPosition(self.initial_fiducial_count-1, coords)
    #logging.info(str(points))
    # Create seed segment outside tumor
    #backgroundSeedPositions = [[151,303,98], [64,204,98], [158, 183, 98], [142,180,177], [127,211,18], [93, 168, 41]]
    backgroundSeedPositions = points
    append = vtk.vtkAppendPolyData()
    for backgroundSeedPosition in backgroundSeedPositions:
      backgroundSeed = vtk.vtkSphereSource()
      backgroundSeed.SetCenter(backgroundSeedPosition)
      backgroundSeed.SetRadius(3)
      backgroundSeed.Update()
      append.AddInputData(backgroundSeed.GetOutput())

    append.Update()
    backgroundSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(append.GetOutput(), "Background", [0.0,1.0,0.0])

    # Run filter
    ################################################

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
    effect.setParameter("Seed locality", imageThreshold)
    effect.self().onPreview()
    effect.self().onApply()

    # Clean up and show results
    ################################################

    # Clean up
    slicer.mrmlScene.RemoveNode(segmentEditorNode)

    # Make segmentation results nicely visible in 3D
    segmentationDisplayNode = segmentationNode.GetDisplayNode()
    segmentationDisplayNode.SetSegmentVisibility(backgroundSegmentId, False)
    #segmentationNode.CreateClosedSurfaceRepresentation()
    
    
    # Compute segment volumes
    resultsTableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode')
    import SegmentStatistics
    segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
    segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    segStatLogic.getParameterNode().SetParameter("ScalarVolume", masterVolumeNode.GetID())
    segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.voxel_count.enabled","False")
    segStatLogic.getParameterNode().SetParameter("ScalarVolumeSegmentStatisticsPlugin.volume_mm3.enabled","False")
    segStatLogic.computeStatistics()
    segStatLogic.exportToTable(resultsTableNode)
    #segStatLogic.showTable(resultsTableNode)
    logging.info("result: " + resultsTableNode.GetCellText(0,4))    

    
    return resultsTableNode.GetCellText(0,1)
    
    logging.info('Processing completed')
    

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

    # Get/create input data

    import SampleData
    inputVolume = SampleData.downloadFromURL(
      nodeNames='MRHead',
      fileNames='MR-Head.nrrd',
      uris='https://github.com/Slicer/SlicerTestingData/releases/download/MD5/39b01631b7b38232a220007230624c8e',
      checksums='MD5:39b01631b7b38232a220007230624c8e')[0]
    self.delayDisplay('Finished with download and loading')

    inputScalarRange = inputVolume.GetImageData().GetScalarRange()
    self.assertEqual(inputScalarRange[0], 0)
    self.assertEqual(inputScalarRange[1], 279)

    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    threshold = 50

    # Test the module logic

    logic = BreastImplantAnalyzerLogic()

    # Test algorithm with non-inverted threshold
    #logic.run(inputVolume, threshold, True)
    #outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    #self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    #self.assertEqual(outputScalarRange[1], threshold)

    # Test algorithm with inverted threshold
    #logic.run(inputVolume, outputVolume, threshold, False)
    #outputScalarRange = outputVolume.GetImageData().GetScalarRange()
    #self.assertEqual(outputScalarRange[0], inputScalarRange[0])
    #self.assertEqual(outputScalarRange[1], inputScalarRange[1])

    self.delayDisplay('Test passed')
