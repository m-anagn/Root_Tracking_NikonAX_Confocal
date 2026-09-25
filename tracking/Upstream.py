# IMPORTANT: 'limjob' must be imported like this (not from nor as)
import limjob
import os
import json
import time
import numpy as np
from datetime import datetime
from skimage.morphology import skeletonize
from skimage.filters import threshold_otsu
from scipy.ndimage import gaussian_filter, laplace
from scipy.signal import convolve2d
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Paths
DEBUG_DIR = r'Your_Path\debug'
LOG_DIR = r'C:Your_Path\logs'
LOG_FILE = os.path.join(LOG_DIR, 'tip_positions.json')
COUNTER_FILE = os.path.join(LOG_DIR, 'slice_counter.json')
os.makedirs(DEBUG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Stack size
Z_STACK_SIZE = 5
SIGN_X = +1
SIGN_Y = -1


# Slice counter
def _get_slice_idx() -> int:
    try:
        with open(COUNTER_FILE, 'r') as f:
            idx = int(json.load(f).get('slice_idx', 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        idx = 0
    with open(COUNTER_FILE, 'w') as f:
        json.dump({'slice_idx': idx + 1}, f)
    return idx


def reset_slice_counter() -> None:
    with open(COUNTER_FILE, 'w') as f:
        json.dump({'slice_idx': 0}, f)
    print("Slice counter reset.")


# Sharpness & Brightness
def _sharpness(img: np.ndarray) -> float:
    return float(np.var(laplace(img.astype(np.float32))))


def _brightness(img: np.ndarray) -> float:
    return float(np.mean(img.astype(np.float32)))


# JSON log
def _append(record: dict) -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append(record)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# Best tip selection
def _detect_tip(img: np.ndarray):
    blurred = gaussian_filter(img, sigma=10)
    thresh = threshold_otsu(blurred)
    skeleton = skeletonize(blurred > thresh)
    kernel = np.array([[1, 1, 1], [1, 10, 1], [1, 1, 1]], dtype=np.int32)
    nb = convolve2d(skeleton.astype(np.int32), kernel, mode='same')
    endpoints = np.argwhere((nb == 11) & skeleton)
    return endpoints, thresh, blurred, skeleton


# Debug imgs
def _save_debug(blurred, skeleton, all_tips, best_tip, center, thresh, idx, ts):
    def _save(fig, name):
        p = os.path.join(DEBUG_DIR, f'{name}_{idx:03d}_{ts}.png')
        fig.savefig(p, dpi=900, bbox_inches='tight')
        plt.close(fig)
        print(f"  Saved: {os.path.basename(p)}" if os.path.isfile(p) else f"  Failed {p}")

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(blurred, cmap='gray')
    ax.set_title(f'Slice {idx:03d} Blurred (Otsu={thresh:.1f})')
    ax.set_xlabel('X (px)');
    ax.set_ylabel('Y (px)')
    _save(fig, 'blurred')

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.imshow(skeleton, cmap='gray')
    ax.plot(center[1], center[0], 'b+', ms=15, mew=2, label='Centre')
    if len(all_tips) > 0:
        ax.plot(all_tips[:, 1], all_tips[:, 0], 'r.', ms=5,
                label=f'Endpoints ({len(all_tips)})')
    if best_tip is not None:
        ax.plot(best_tip[1], best_tip[0], 'y*', ms=12, label='Best tip')
    ax.set_title(f'Slice {idx:03d} Skeleton & Tips')
    ax.set_xlabel('X (px)');
    ax.set_ylabel('Y (px)')
    ax.legend(fontsize=9);
    ax.grid(True, alpha=0.3)
    _save(fig, 'skeleton')


# Process
def run(imgs: tuple[limjob.Image], Job: limjob.JobParam,
        macro: limjob.MacroParam, ctx: limjob.RunContext):
    img = imgs[0]
    width, height, depth = img.size
    img_data = img.array().reshape(depth, height, width)[0].astype(float)
    um_per_px = img.calibration[0]
    idx = _get_slice_idx()
    ts = time.strftime('%d%m%Y_%H%M%S')
    print(f"Slice #{idx:03d}  {ts}")
    print(f"Size (W,H,D): ({width},{height},{depth})  Shape: {img_data.shape}  Cal: {um_per_px:.4f} um/px")

    try:
        sx, sy = XY_GetPosition()
        sz = Z_GetPosition()
    except NameError:
        sx, sy, sz = 0.0, 0.0, 0.0
        print("  (testing mode - stage pos = 0)")
    print(f"Stage: X={sx:+.3f}  Y={sy:+.3f}  Z={sz:+.3f} um")

    center = np.array([img_data.shape[0] / 2.0, img_data.shape[1] / 2.0])
    # transformPxToStage
    center_abs_x, center_abs_y = img.transformPxToStage(float(center[1]), float(center[0]))
    print(f"Centre px: col={center[1]:.0f} row={center[0]:.0f}  "
          f"Centre abs: X={center_abs_x:+.3f}  Y={center_abs_y:+.3f} um")

    sharp = _sharpness(img_data)
    bright = _brightness(img_data)
    print(f"Sharpness={sharp:.2f}  Brightness={bright:.2f}")

    all_tips, thresh, blurred, skeleton = _detect_tip(img_data)
    print(f"Endpoints found: {len(all_tips)}")

    best_tip = None
    if len(all_tips) > 0:
        best_tip = all_tips[np.argmin(np.linalg.norm(all_tips - center, axis=1))]
        print(f"Best tip: row={best_tip[0]}  col={best_tip[1]}")

    _save_debug(blurred, skeleton, all_tips, best_tip, center, thresh, idx, ts)

    record = {
        "Slice_idx": idx,
        "Timestamp": datetime.now().isoformat(),
        "Stage_x_um": float(sx),
        "Stage_y_um": float(sy),
        "Stage_z_um": float(sz),
        "Calibration_um_per_px": float(um_per_px),
        "Center_px_col": float(center[1]),
        "Center_px_row": float(center[0]),
        "Center_abs_x_um": float(center_abs_x),
        "Center_abs_y_um": float(center_abs_y),
        "Sharpness": sharp,
        "Brightness": bright,
        "Tip_found": best_tip is not None,
        "Tip_px_col": None,
        "Tip_px_row": None,
        "Tip_offset_x_um": None,
        "Tip_offset_y_um": None,
        "Tip_abs_x_um": None,
        "Tip_abs_y_um": None,
    }

    if best_tip is not None:
        row, col = int(best_tip[0]), int(best_tip[1])
        dx_px = float(col) - center[1]
        dy_px = float(row) - center[0]
        dx_um = SIGN_X * dx_px * um_per_px
        dy_um = SIGN_Y * dy_px * um_per_px

        # Clamp to one field of view
        max_dx_um = (width / 2.0) * um_per_px
        max_dy_um = (height / 2.0) * um_per_px
        dx_um_c = max(-max_dx_um, min(max_dx_um, dx_um))
        dy_um_c = max(-max_dy_um, min(max_dy_um, dy_um))
        if dx_um_c != dx_um or dy_um_c != dy_um:
            print(f"CLAMPED: dx {dx_um:+.3f}->{dx_um_c:+.3f}  dy {dy_um:+.3f}->{dy_um_c:+.3f} um")
        dx_um, dy_um = dx_um_c, dy_um_c

        # transformPxToStage(x, y) = (col, row)
        abs_x, abs_y = img.transformPxToStage(float(col), float(row))

        record.update({
            "Tip_px_col": float(col),
            "Tip_px_row": float(row),
            "Tip_offset_x_um": dx_um,
            "Tip_offset_y_um": dy_um,
            "Tip_abs_x_um": float(abs_x),
            "Tip_abs_y_um": float(abs_y),
        })
        print(f"Offset: dx={dx_px:+.1f}px={dx_um:+.3f}um  dy={dy_px:+.1f}px={dy_um:+.3f}um")
        print(f"Abs:    X={abs_x:+.3f}  Y={abs_y:+.3f} um")
    else:
        print("No tip found.")

    _append(record)
    print(f"Slice #{idx:03d} done.\n")
