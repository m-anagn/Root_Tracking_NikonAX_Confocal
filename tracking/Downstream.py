# IMPORTANT: 'limjob' must be imported like this (not from nor as)
import limjob
import os
import json
from datetime import datetime

# Directories
LOG_DIR = r'Your_Path\logs'
OUTPUT_DIR = r'Your_Path\analysis'
LOG_FILE = os.path.join(LOG_DIR, 'tip_positions.json')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Settings
Z_STACK_SIZE = 5
SHARP_MIN_RANGE = 1000
MAX_MOVE_UM = 500.0


def _best_z(stack: list) -> dict:
    tip_idxs = [i for i, r in enumerate(stack) if r.get('Tip_found', False)]

    if not tip_idxs:
        c = len(stack) // 2
        return {
            "best_slice_idx": c,
            "best_z_um": float(stack[c].get('Stage_z_um', 0.0)),
            "reason": "no tip - centre slice",
            "tip_found": False,
            "sharpness": None,
            "brightness": None,
            "tip_abs_x_um": None,
            "tip_abs_y_um": None,
        }

    sharps = [float(stack[i]['Sharpness']) for i in tip_idxs]
    brights = [float(stack[i]['Brightness']) for i in tip_idxs]
    sharp_range = max(sharps) - min(sharps)

    if sharp_range >= SHARP_MIN_RANGE:
        best_local = sharps.index(max(sharps))
        reason = f"sharpness (range={sharp_range:.1f})"
    else:
        best_local = brights.index(max(brights))
        reason = f"brightness fallback (sharpness range={sharp_range:.1f} < {SHARP_MIN_RANGE})"

    best_global = tip_idxs[best_local]
    best_rec = stack[best_global]

    return {
        "best_slice_idx": best_global,
        "best_z_um": float(best_rec.get('Stage_z_um', 0.0)),
        "reason": reason,
        "tip_found": True,
        "sharpness": sharps[best_local],
        "brightness": brights[best_local],
        "tip_abs_x_um": best_rec.get('Tip_abs_x_um'),
        "tip_abs_y_um": best_rec.get('Tip_abs_y_um'),
    }


# Text log
def _write_log(path, stacks_results, ref_x, ref_y, ref_z,
               target_x, target_y, target_z):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"Root tracking - {datetime.now().isoformat()}\n\n")
        f.write(f"Reference     : X={ref_x:+.3f}  Y={ref_y:+.3f}  Z={ref_z:+.3f} um\n")
        f.write(f"Target        : X={target_x:+.3f}  Y={target_y:+.3f}  Z={target_z:+.3f} um\n")
        f.write(f"Move          : dX={target_x - ref_x:+.3f}  dY={target_y - ref_y:+.3f}"
                f"  dZ={target_z - ref_z:+.3f} um\n\n")
        for i, r in enumerate(stacks_results, 1):
            f.write(f"Stack {i}: slices {r['slice_range']}  "
                    f"best-Z={r['best_z_um']:+.3f} um  ({r['reason']})\n")
            if r['tip_found']:
                f.write(f"  Tip abs XY: X={r['tip_abs_x_um']:+.3f}  Y={r['tip_abs_y_um']:+.3f} um\n")
                f.write(f"  Sharpness={r['sharpness']:.2f}  Brightness={r['brightness']:.2f}\n")


# Process
def run(imgs: tuple[limjob.Image], Job: limjob.JobParam,
        macro: limjob.MacroParam, ctx: limjob.RunContext) -> None:
    session = datetime.now().strftime('%d%m%Y_%H%M%S')
    print(f"Downstream  {session}")

    if not os.path.isfile(LOG_FILE):
        print(f"Log not found: {LOG_FILE}")
        return

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        records = json.load(f)
    records = [r for r in records if 'Slice_idx' in r]
    print(f"Loaded {len(records)} slice records")

    if len(records) < Z_STACK_SIZE:
        print(f"Need at least {Z_STACK_SIZE} slices, only have {len(records)}.")
        return

    # Group into Z-stacks
    stacks = [records[i: i + Z_STACK_SIZE]
              for i in range(0, len(records), Z_STACK_SIZE)]
    print(f"Z_STACK_SIZE={Z_STACK_SIZE}  {len(stacks)} stack(s)\n")

    stacks_results = []
    for n, stack in enumerate(stacks, 1):
        idxs = [r['Slice_idx'] for r in stack]
        res = _best_z(stack)
        res['stack_number'] = n
        res['slice_range'] = f"{idxs[0]}-{idxs[-1]}"
        stacks_results.append(res)
        print(f"Stack {n} (slices {res['slice_range']}): "
              f"best Z={res['best_z_um']:+.3f} um  [{res['reason']}]")
        if res['tip_found']:
            print(f"  Tip abs XY: X={res['tip_abs_x_um']:+.3f}  Y={res['tip_abs_y_um']:+.3f} um  "
                  f"Sharp={res['sharpness']:.2f}  Bright={res['brightness']:.2f}")

    last = stacks_results[-1]
    ref_rec = stacks[-1][0]
    ref_x = float(ref_rec.get('Stage_x_um', 0.0))
    ref_y = float(ref_rec.get('Stage_y_um', 0.0))
    ref_z = float(ref_rec.get('Stage_z_um', 0.0))

    if ref_x == 0.0 and ref_y == 0.0:
        print("Reference position is zero ")
    if last['tip_found']:
        best_rec = stacks[-1][last['best_slice_idx']]
        tip_x = float(best_rec.get('Tip_abs_x_um', ref_x))
        tip_y = float(best_rec.get('Tip_abs_y_um', ref_y))
        cen_x = float(best_rec.get('Center_abs_x_um', ref_x))
        cen_y = float(best_rec.get('Center_abs_y_um', ref_y))

        offset_x = tip_x - cen_x
        offset_y = tip_y - cen_y
        target_x = ref_x + offset_x
        target_y = ref_y + offset_y
        # Sanity check
        max_um = 512 * float(best_rec.get('Calibration_um_per_px', 0.863))
        if abs(offset_x) > max_um or abs(offset_y) > max_um:
            print(f"WARNING: offset ({offset_x:+.1f}, {offset_y:+.1f} um) exceeds")
        xy_src = "Center_abs + tip-to-center offset (best-focus slice)"
    else:
        target_x = ref_x
        target_y = ref_y
        xy_src = "no tip found"

    # Target Z
    target_z = last['best_z_um']

    print(f"\nReference (first slice, last stack): "
          f"X={ref_x:+.3f}  Y={ref_y:+.3f}  Z={ref_z:+.3f} um")
    print(f"XY source: {xy_src}")
    print(f"Target: X={target_x:+.3f}  Y={target_y:+.3f}  Z={target_z:+.3f} um")
    print(f"Move:   dX={target_x - ref_x:+.3f}  dY={target_y - ref_y:+.3f}"
          f"  dZ={target_z - ref_z:+.3f} um\n")

    # Save text log
    log_path = os.path.join(OUTPUT_DIR, f'positions_{session}.txt')
    _write_log(log_path, stacks_results, ref_x, ref_y, ref_z,
               target_x, target_y, target_z)
    print(f"Log saved: {log_path}" if os.path.isfile(log_path) else "WARNING: log not saved")

    # Save analysis JSON
    out = {
        "session": session,
        "timestamp": datetime.now().isoformat(),
        "z_stack_size": Z_STACK_SIZE,
        "n_stacks": len(stacks_results),
        "stacks": stacks_results,
        "ref_x_um": ref_x, "ref_y_um": ref_y, "ref_z_um": ref_z,
        "target_x_um": target_x, "target_y_um": target_y, "target_z_um": target_z,
    }
    json_path = os.path.join(OUTPUT_DIR, f'analysis_{session}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=2)
    print(f"JSON saved: {json_path}" if os.path.isfile(json_path) else "WARNING: JSON not saved")
    target_x = float(target_x)
    target_y = float(target_y)
    target_z = float(target_z)
    ref_x = float(ref_x)
    ref_y = float(ref_y)
    ref_z = float(ref_z)
    dX = target_x - ref_x
    dY = target_y - ref_y
    dZ = target_z - ref_z

    # Clamp
    xy_clamped = abs(dX) > MAX_MOVE_UM or abs(dY) > MAX_MOVE_UM
    z_clamped = abs(dZ) > MAX_MOVE_UM

    # Zero-guard
    if target_x == 0.0 and target_y == 0.0 and (ref_x != 0.0 or ref_y != 0.0):
        xy_clamped = True
        print(f"ZERO-GUARD: target XY is (0,0) but ref is ({ref_x:+.3f}, {ref_y:+.3f}) "
              f" XY move suppressed")
    if target_z == 0.0 and ref_z != 0.0:
        z_clamped = True
        print(f"ZERO-GUARD: target Z is 0.0 but ref is {ref_z:+.3f} "
              f" Z move suppressed")

    if xy_clamped:
        print(f"CLAMP: XY delta ({dX:+.1f}, {dY:+.1f} um) exceeds {MAX_MOVE_UM:.0f} um "
              f" XY move suppressed, retaining X={ref_x:+.3f}  Y={ref_y:+.3f} um")
    if z_clamped:
        print(f"CLAMP: Z delta ({dZ:+.1f} um) exceeds {MAX_MOVE_UM:.0f} um "
              f" Z move suppressed, retaining Z={ref_z:+.3f} um")

    print(f"Pre-move: target X={target_x:+.3f}  Y={target_y:+.3f}  Z={target_z:+.3f} um ")

    try:
        if not xy_clamped:
            XY_Move(target_x, target_y)
            print(f"XY moved to X={target_x:+.3f}  Y={target_y:+.3f} um")
        if not z_clamped:
            Z_Move(target_z)
            print(f"Z  moved to Z={target_z:+.3f} um")
        if xy_clamped and z_clamped:
            print("Stage move skipped (both axes clamped).")
        elif xy_clamped or z_clamped:
            print("Stage partially moved (one axis clamped).")
        else:
            print("Stage moved.")
    except Exception as e:
        print(f"Stage move failed: {e}")

    print("Done & Dusted.\n")

