# Automated Smart Microscopy Workflow for Root Tracking & Analysis

## Overview

Heat stress (HS) is an important environmental factor affecting plant growth and productivity. Plants respond to elevated temperatures through multiple mechanisms that protect cellular homeostasis, including the induction of Heat Shock Proteins (HSPs). HSP70 proteins function as molecular chaperones and contribute to the maintenance of proteostasis. Plants can also retain information from a previous moderate heat exposure (priming) during a memory phase, which can influence their response to a subsequent heat treatment (triggering).

Roots are highly sensitive to temperature fluctuations, but their continuous growth presents a challenge for long-term live-cell imaging because the root tip progressively moves out of the microscope field of view. Conventional horizontal microscope configurations can additionally introduce gravitropic effects. Automated vertical confocal imaging can address these limitations by continuously tracking the growing root tip during time-lapse acquisition.

This repository contains a smart microscopy workflow developed for automated root-tip tracking and subsequent fluorescence analysis in *Arabidopsis thaliana*. The workflow was implemented in the JOBS environment of NIS-Elements for a Nikon AX confocal microscope using a vertical imaging configuration.

## Workflow

The workflow consists of three main components:

1. **Upstream root-tracking script**
   Processes individual images acquired during a Z-stack, detects the root tip, and records its position together with image quality parameters.

2. **Downstream root-tracking script**
   Groups acquired images into Z-stacks, identifies the optimal Z-position based on root-tip detection and image quality, calculates the required stage repositioning, and returns the root tip to the centre of the field of view.

3. **Image-analysis script**
   Post-acquisition time-lapse datasets in Fiji/ImageJ to align the images, identify the root region, and quantify fluorescence intensity within the resulting regions of interest (ROIs).

The tracking workflow was developed to support long-term imaging during a thermomemory assay and was used to investigate the temporal response of an HSP70-4-GFP reporter in the root apex.

## Repository Structure

```text
.
├── tracking/
│   ├── upstream.py
│   └── downstream.py
│
├── analysis/
│   └── Root_tracking_processing.groovy
│
└── README.md
```

## Requirements

### Microscopy

* Nikon AX confocal microscope
* Vertical stage configuration
* NIS-Elements AR with the JOBS module
* Python support within the NIS-Elements environment
* Fiji/ImageJ for post-acquisition image analysis

### Biological material

The workflow was developed using *Arabidopsis thaliana* roots and an HSP70-4-GFP fluorescent reporter line.

## Experimental Workflow

The imaging workflow combines a vertical confocal configuration with automated root tracking.

The thermomemory experiment consists of control (C), triggered (T), and primed&triggered (PT) conditions. The workflow allows time-lapse imaging during the relevant stages of the experiment while maintaining the root apex within the field of view.

### JOBS configuration

Create the JOBS workflow in NIS-Elements as follows:

1. Open **JOBS > JOBS Explorer**.
2. Create a new project using **New** in the Project section.
3. Create a new JOB within the project.
4. Select the JOB and choose **Edit**.
5. Add the following tasks:

   * `ZStackDefinition`
   * `CaptureDefinition`
   * `NewPointSet`
   * `Time Loop`
6. Nest a **Point Loop** within the **Time Loop**.
7. Nest a **Z-Stack Loop** and a **Python Script** within the **Point Loop**.
8. Nest a **Capture** task and a **Python Script** within the **Z-Stack Loop**.
9. Add the **Upstream** tracking script to the Python Script within the Z-Stack Loop.
10. Add the **Downstream** tracking script to the Python Script within the Point Loop.
11. Adjust the workflow parameters to match the imaging configuration and experiment.
12. Save the JOB.
13. Start the experiment using **Run**.
14. When acquisition is complete, select **Finish**.
15. Save the resulting time-lapse dataset using the sample ID and upload the dataset to the appropriate OMERO repository.

Before starting a new JOB run, move or archive the previous log and debug directories. This prevents previous tracking records from being incorrectly incorporated into subsequent acquisitions.

## Tracking Parameters

The following parameters must be adjusted according to the experimental configuration:

```python
Z_STACK_SIZE = 5
SHARP_MIN_RANGE = 1000
MAX_MOVE_UM = 500.0
```

### `Z_STACK_SIZE`

Defines the number of consecutive images treated as a single Z-stack.

### `SHARP_MIN_RANGE`

Defines the minimum sharpness range used by the downstream script to determine whether sharpness provides sufficient variation for selecting the optimal Z-position. If the range is below this value, brightness is used as a fallback criterion.

### `MAX_MOVE_UM`

Defines the maximum permitted stage displacement in micrometres. Movements exceeding this threshold are suppressed as a safety measure.

Brightness and sharpness thresholds can be modified according to the imaging conditions and experimental requirements.

## Upstream Tracking

The upstream script is executed for each image acquired within a Z-stack.

The script:

1. Extracts the acquired image and calibration information.
2. Records the current microscope stage position.
3. Calculates the image centre.
4. Applies Gaussian filtering and Otsu thresholding.
5. Skeletonizes the segmented root.
6. Identifies skeleton endpoints as candidate root-tip positions.
7. Selects the endpoint closest to the image centre.
8. Calculates the root-tip position in pixel and stage coordinates.
9. Records image sharpness and brightness.
10. Saves the results to the tracking log and diagnostic files.

The resulting records are used by the downstream script to determine the optimal Z-position and stage displacement.

## Downstream Tracking

The downstream script processes the records generated by the upstream script.

For each Z-stack, it:

1. Groups the corresponding slice records.
2. Identifies slices in which a root tip was detected.
3. Selects the optimal Z-position based primarily on sharpness.
4. Uses brightness as a fallback criterion when the sharpness range is insufficient.
5. Determines the absolute position of the detected root tip.
6. Calculates its displacement from the image centre.
7. Calculates the target X, Y, and Z stage positions.
8. Applies movement and zero-value safety checks.
9. Repositions the microscope stage when the calculated movement is within the defined limits.
10. Saves the tracking and analysis results.

If no root tip is detected within a Z-stack, the centre slice is used as a fallback for Z-position selection and stage repositioning is suppressed where appropriate.

## Image Analysis

Post-acquisition image analysis script is available as a Groovy script for Fiji/ImageJ.

Following manual import of the time-lapse, the script performs the following processing steps:

1. Maximum-intensity projection.
2. Bleach correction.
3. Image registration.
4. Gaussian filtering of the registered stack.
5. Thresholding and binarization.
6. Skeletonization.
7. Skeleton analysis.
8. Generation and thresholding of the tagged skeleton.
9. Particle analysis to generate regions of interest (ROIs).
10. Measurement of fluorescence intensity within the resulting ROIs.
11. Export of measurements as `.csv` files according to the selected labels.

The script includes user prompts before bleach correction and thresholding, allowing processing parameters to be adjusted according to the dataset.

## Potential Applications

The workflow provides a framework for automated long-term imaging of growing plant roots and can be adapted to investigate spatial and temporal responses to environmental stimuli.

Potential applications include:

* Heat stress and thermomemory experiments
* Analysis of fluorescent stress reporters
* Long-term tracking while imaging
* Pharmacological treatments
* Mutant or reporter-line comparisons
* Automated monitoring of root responses to various environmental perturbations

Further development could enable simultaneous tracking of multiple roots and adaptation of the workflow to other organisms, species, or biological systems, and microscope configurations.

## Limitations and Future Development

The current workflow was developed and evaluated using a specific vertical Nikon AX confocal configuration and an *Arabidopsis thaliana* root-tracking application. Performance may therefore depend on microscope configuration, image quality, root morphology, and experimental conditions.

Future development should focus on:

* Increasing the robustness of root-tip detection across different reporter lines and imaging conditions.
* Supporting simultaneous tracking of multiple roots.
* Improving flexibility across microscope configurations.
* Extending compatibility to other organisms and experimental systems.
* Further validating automated tracking under diverse experimental conditions.


## Acknowledgements

This work was conducted using the confocal laser scanning microscope of the Microscopy Unit, Institute of Biology Leiden (IBL), Leiden University.
Many thanks Dr. Joost Willemse, Dr. Bas Laan and Dr. Bastienne Vriesendorp to for the opportunity to undertake this project, as well as for providing valuable support, guidance and encouragement throughout.
