import numpy as np
import matplotlib.pyplot as plt
import math

# ==========================================
# 1. Pipeline Configuration
# ==========================================
FOCAL_LENGTH_PX = 800  # Camera focal length in pixels
IMG_WIDTH = 640  # Image resolution
IMG_HEIGHT = 480
SITE_SIZE_M = 100  # 100x100 meter construction site
GRID_RES_M = 0.5  # Each pixel on our final map represents 0.5 meters

# Initialize the global accumulator map (Heatmap)
grid_shape = (int(SITE_SIZE_M / GRID_RES_M), int(SITE_SIZE_M / GRID_RES_M))
site_map = np.zeros(grid_shape)

# ==========================================
# 2. Core Georeferencing Functions
# ==========================================
def project_pixels_to_ground(u, v, drone_x, drone_y, drone_z, yaw_deg=0):
    """
    Projects image pixel coordinates (u, v) to global ground coordinates (X, Y).
    """
    # 1. Convert pixels to metric offsets from the camera center
    dx = (u - IMG_WIDTH / 2) * (drone_z / FOCAL_LENGTH_PX)
    dy = (v - IMG_HEIGHT / 2) * (drone_z / FOCAL_LENGTH_PX)

    # 2. Apply Drone Yaw (Rotation)
    yaw_rad = math.radians(yaw_deg)
    rot_dx = dx * math.cos(yaw_rad) - dy * math.sin(yaw_rad)
    rot_dy = dx * math.sin(yaw_rad) + dy * math.cos(yaw_rad)

    # 3. Translate to global drone position
    global_x = drone_x + rot_dx
    global_y = drone_y + rot_dy

    return global_x, global_y


def accumulate_to_map(global_x, global_y, confidence=1.0):
    """
    Takes global X, Y coordinates and votes into the discretized site map.
    """
    global site_map

    # Convert metric coordinates to map grid indices
    grid_x = (global_x / GRID_RES_M).astype(int)
    grid_y = (global_y / GRID_RES_M).astype(int)

    # Filter out detections that fall outside our site boundaries
    valid_mask = (
        (grid_x >= 0)
        & (grid_x < grid_shape[1])
        & (grid_y >= 0)
        & (grid_y < grid_shape[0])
    )

    # Add votes to the accumulator map
    np.add.at(site_map, (grid_y[valid_mask], grid_x[valid_mask]), confidence)


# ==========================================
# 3. Synthetic Validation (The Self-Test)
# ==========================================
# Simulate a drone flying a grid pattern at 30m altitude
drone_path = [
    {"x": 40, "y": 45, "z": 30, "yaw": 0},
    {"x": 50, "y": 45, "z": 30, "yaw": 10},  # Slight rotation
    {"x": 60, "y": 45, "z": 30, "yaw": 0},
]

# Simulate a segmented mask for each frame
# Let's pretend the segmentation model found a pile of materials in the center of the image
for frame in drone_path:
    # 1. Generate fake segmented pixels (e.g., output of a lightweight UNet/SAM)
    # Creating a 50x50 pixel "blob" in the middle of the camera view
    u_coords, v_coords = np.meshgrid(np.arange(300, 350), np.arange(220, 270))
    u_flat = u_coords.flatten()
    v_flat = v_coords.flatten()

    # 2. Georeference the mask
    ground_x, ground_y = project_pixels_to_ground(
        u=u_flat,
        v=v_flat,
        drone_x=frame["x"],
        drone_y=frame["y"],
        drone_z=frame["z"],
        yaw_deg=frame["yaw"],
    )

    # 3. Accumulate into the map
    accumulate_to_map(ground_x, ground_y, confidence=1)

# ==========================================
# 4. Visualization
# ==========================================
plt.figure(figsize=(8, 8))
plt.title(
    "Accumulated Construction Site Map\n(Overlapping frames create high-confidence zones)"
)
# Display the heatmap (transpose so X is horizontal, Y is vertical)
plt.imshow(
    site_map, origin="lower", extent=[0, SITE_SIZE_M, 0, SITE_SIZE_M], cmap="inferno"
)
plt.colorbar(label="Detection Confidence (Overlaps)")

# Plot the drone flight path
drone_xs = [p["x"] for p in drone_path]
drone_ys = [p["y"] for p in drone_path]
plt.plot(drone_xs, drone_ys, "w--", marker="o", label="Drone Path")

plt.xlabel("Site X (meters)")
plt.ylabel("Site Y (meters)")
plt.legend()
plt.savefig("site_map.png", dpi=300, bbox_inches="tight")
print("Saved map to site_map.png")
