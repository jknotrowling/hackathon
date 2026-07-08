import urx
import math
from urx.urrobot import URRobot

rob = urx.Robot("169.254.14.99")

def transform_location(location: list[float]) -> list[float]:
    out_location = location.copy()
    out_location[0] = math.sin(math.radians(-135)) *location[0] + math.cos(math.radians(-135)) * location[1]
    out_location[1] = math.cos(math.radians(-135)) * location[0] - math.sin(math.radians(-135)) * location[1]
    return out_location

def reverse_transform_location(location: list[float]) -> list[float]:
    out_location = location.copy()
    out_location[0] = math.sin(math.radians(135)) * location[0] - math.cos(math.radians(135)) * location[1]
    out_location[1] = math.cos(math.radians(135)) * location[0] + math.sin(math.radians(135)) * location[1]
    return out_location

try:
    location = transform_location(URRobot.getl(rob))
    
    print("Current pose:", location)

    location[0] += 0.01

    location = reverse_transform_location(location)

    # Move 1 cm in X relative to the current TCP pose.
    # Call URRobot.movex directly: Robot.movel/movex pass PoseVector objects
    # that newer math3d versions do not treat as iterable.
    URRobot.movex(rob, "movel", location, relative=True, wait=False)

    print("New pose:", URRobot.getl(rob))
finally:
    URRobot.close(rob)
