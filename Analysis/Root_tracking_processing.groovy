import ij.IJ
import ij.ImagePlus
import ij.WindowManager
import ij.gui.WaitForUserDialog
import ij.plugin.frame.RoiManager


 
// Helper methods
def currentImage() {
    return WindowManager.getCurrentImage()
}
def waitForUser(String title, String message) {
    new WaitForUserDialog(title, message).show()
}
 
// Start with original timelapse
 
ImagePlus original = currentImage()

if (original == null) {
    throw new IllegalStateException("No image is open.")
}


// Show image information
 
IJ.run(original, "Show Info...", "")


// Duplicate
 
IJ.run(original, "Duplicate...", "duplicate")
ImagePlus dup1 = currentImage()
 
// Apply Fire LUT
 
IJ.run(dup1, "Fire", "")

// Maximum intensity projection
 
IJ.run(dup1, "Z Project...", "projection=[Max Intensity] all")
ImagePlus projected = currentImage()

// MANUAL BLEACH CORRECTION

// run("Bleach Correction Selection");

IJ.run(projected, "Bleach Correction Selection", "")

waitForUser(
    "Bleach correction",
    "Adjust the bleach correction selection as needed.\n\n" +
    "When satisfied, " + "click OK here to continue."
)


 
// Linear Stack Alignment with SIFT
 

IJ.run(
    projected,
    "Linear Stack Alignment with SIFT",
    "initial_gaussian_blur=1.60 " +
    "steps_per_scale_octave=3 " +
    "minimum_image_size=64 " +
    "maximum_image_size=1024 " +
    "feature_descriptor_size=4 " +
    "feature_descriptor_orientation_bins=8 " +
    "closest/next_closest_ratio=0.92 " +
    "maximal_alignment_error=25 " +
    "inlier_ratio=0.05 " +
    "expected_transformation=Translation " +
    "interpolate " +
    "show_transformation_matrix"
)

// Duplicate aligned image
 
ImagePlus aligned = currentImage()

IJ.run(aligned, "Duplicate...", "duplicate")
ImagePlus dup2 = currentImage()

// Gaussian blur

IJ.run(dup2, "Gaussian Blur...", "sigma=10 stack")
 
// MANUAL THRESHOLD SELECTION

IJ.run(dup2, "Threshold...", "")

waitForUser(
    "Adjust the threshold on the stack as needed, then click OK here to continue.\n\n" +
    "DO NOT CLICK Apply in the Threshold window - the script converts to mask next."
)


// Convert thresholded image to binary mask
 
IJ.run(
    dup2,
    "Convert to Mask",
    "background=Dark calculate black"
)
 
// Skeletonize
 
ImagePlus skeletonInput = currentImage()

IJ.run(skeletonInput, "Skeletonize", "stack")

// Analyze Skeleton
 
IJ.run(
    skeletonInput,
    "Analyze Skeleton (2D/3D)",
    "prune=none calculate display"
)
 
// Select skeleton-analysis output images 

ImagePlus longestShortestPaths =
    WindowManager.getImage("Longest shortest paths")

ImagePlus alignedLabeledSkeletons =
    WindowManager.getImage("Aligned-labeled-skeletons")

ImagePlus taggedSkeleton =
    WindowManager.getImage("Tagged skeleton")

 
// MANUAL THRESHOLD SELECTION ON TAGGED SKELETON

if (taggedSkeleton == null) {
    throw new IllegalStateException(
        "Could not find the image window 'Tagged skeleton'."
    )
}

IJ.selectWindow(taggedSkeleton.getTitle())

IJ.run(taggedSkeleton, "Threshold...", "")

waitForUser(
    "Adjust the threshold on the Tagged skeleton image as needed, " +
    "then click OK here to continue.\n\n" +
    "Do NOT CLICK Apply in the Threshold window - the script convert the result to a mask next."
)


 
// Convert Tagged skeleton to mask
 

IJ.run(
    taggedSkeleton,
    "Convert to Mask",
    "background=Dark calculate black"
)


 
// Close Tagged skeleton
 
IJ.run(taggedSkeleton, "Close", "")
 
// Analyze particles
 

IJ.run(
    taggedSkeleton,
    "Analyze Particles...",
    "add stack"
)


 
// ROI Manager
 

RoiManager rm = RoiManager.getInstance()

if (rm == null) {
    rm = new RoiManager()
}

// Obtain measurements

waitForUser(
    "After selecting the ROI " +
    " click >> and press Multi Measure to obtain measurements.\n\n" 
)
