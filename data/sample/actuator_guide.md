# Virtual actuator — Fictional ROS 2 exercise guide

The virtual actuator is a one-dimensional simulation. It does not operate a physical robot.

## Goals and feedback
The action endpoint is /slew_to_setpoint. A goal contains a numeric target position. Feedback contains current and error. The result contains success, total_time, and message. Position updates are published on /position while the actuator is moving.

## Parameters
The virtual actuator default max_velocity is 0.5 position units per second. The default tolerance is 0.05 position units. The default rate_hz is 10.0. Runtime max_velocity updates must be strictly positive; zero and negative values are rejected. These defaults are examples, not measurements from Assem's ROS repository.

## Scope
The exercise does not provide torque ratings, motor voltage, mechanical safety certification, or an emergency-stop procedure.
